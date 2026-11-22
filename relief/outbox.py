"""The messages waiting to go out on Telegram and the sender (tables outbox and buttons of relief/tgdb.py). A message is sent
once, or marked "unsure" (it may have gone; nobody can tell): it never goes twice.

queue puts a message under its key, for a person linked now (links.chat_of); a key there already, in any state but dropped, is
not queued again. States: queued; sending (marked and committed before anything goes out, with nothing locked during the call);
sent; failed (Telegram refused it, every try failed, or it could not be made into a message); unsure (the request may have gone
out, or the app stopped while it was going: never tried again by itself); dropped (no longer true, or its person had no
Telegram when it was to go: as if it had never been queued, so its key may be queued again).

send_due sends what is due, oldest first, one run at a time in this copy of the app; an item is taken from queued to sending
in one statement, so two copies never send the same one either. Nothing goes, and nothing is changed, while the bot is not
connected (links.connected: no token, or another bot's) or the accounts cannot be read (nobody could be found then). Each item:
VALID(item) False drops it (tell.still_true); the chat is links.chat_of(name) at that moment, never the one it was queued with;
when either raises, it waits as after "network". An item that cannot be made into a message or marked sending is failed at
once, and the rest go on; only the store failing (sqlite3.OperationalError: locked, the disk) ends the run. Then what tg.call
answers: "network" (nothing went out) waits WAITS[tries], all five of them, so it is failed at the sixth try; "slow" puts it
back until the pause ends, no try counted; "blocked" unlinks the person, only while that chat is still theirs, and removes the
item, so that its key may be queued once they link again (the bot disconnected meanwhile: it is put back, nobody unlinked);
"unsure" is unsure and ends the run; anything else failed.

A pause Telegram asks for ("slow", in answer to a message, a file or getMe) holds everything, what is queued during it too:
until it ends (_hold; HOLD_MOST seconds at most, whatever Telegram says) nothing goes, is dropped or counted, and then the
oldest go first. After an unsure message nothing goes until Telegram has answered getMe, asked at the start of each run
(_doubt), so a dead connection makes one message unsure, not all. Both are kept in memory: a restart clears them. An item that
has been sending for over STUCK seconds (its answer could not be written, or another copy stopped) is unsure too, at each run.

The text is plain (no parse_mode) and cut at a line end when longer than LIMIT. A button's token is made for the first try
and kept with the item, so every try carries the same ones; its row in buttons is written with the item's sending and is good
for BUTTON_DAYS from when the message was queued. A button that opens an address is left out unless it is https (Telegram
refuses others).

Files follow the message once it is sent, each by sendDocument, to the same chat while it is still that person's. files_failed
counts those that have not gone: all of them when the message goes, one less as each goes, so a restart in between leaves the
truth. A file "slow" (a pause of FILE_SLOW seconds at most, waited for at once) or "network" is tried FILE_TRIES times in all;
after one that is "unsure", or a longer pause, the rest of that message's files are not tried. The message stays sent.

start is the sender: one daemon thread, recover first (whatever was sending when the app stopped is unsure), then prune, then
send_due every EVERY seconds or when woken. Failures are logged to "relief.telegram" by their kind alone: never a text, a
name, a chat, a token or a key (keys hold names)."""
import datetime, json, logging, secrets, sqlite3, threading, time

from accounts import people as _accounts
from relief import absences as _absences
from relief import files as _files
from relief import links, tg, tgdb

EVERY = 5                                       # seconds between the sender's runs
WAITS = (5, 30, 120, 600, 1800)                 # seconds before the next try, by how many have failed
HOLD_MOST, STUCK = 3600, 120
SPACING = 0.05                                  # seconds at least between two calls (tests: 0)
LIMIT, MORE = 4000, "…and more in the app."
BUTTON_DAYS, KEEP_DAYS = 30, 400
FILE_TRIES, FILE_WAIT, FILE_SLOW, FILE_TIMEOUT = 3, 2, 20, 60
ME_TIMEOUT = 5
VALID = lambda item: True                       # item: the stored message as a dict (key, name, kind, ref, text, ...)
_busy = threading.Lock()                        # one run at a time
_doubt = threading.Event()                      # a message may or may not have gone: the next waits for Telegram to answer
_hold = [0.0]                                   # when the pause Telegram asked for ends (epoch seconds)
_last = [0.0]                                   # when the last call ended (time.monotonic)
_wake, _stop = threading.Event(), threading.Event()
_sender = None
_log = logging.getLogger("relief.telegram")


def _clock(): return time.time()
def _sleep(seconds): time.sleep(seconds)


# ---- the queue
def _json(v):
    try: return json.dumps(v)
    except (TypeError, RecursionError): raise ValueError("this cannot be kept as JSON") from None


def _str(v, what):
    """v when it is text the store can hold, else ValueError"""
    if not isinstance(v, str): raise ValueError(f"{what} must be text")
    v.encode()                                                       # UnicodeEncodeError is a ValueError
    return v


def _button(b):
    """a button as it is kept, with no token yet. ValueError for what could not be: not a dict, no label (text), or a label,
    url, what, id, ckey or who that is not text (the last four may be None). Whether Telegram takes it is seen when it goes"""
    if not isinstance(b, dict): raise ValueError("a button must be a dict")
    for k in ("what", "id", "ckey", "who"):
        if b.get(k) is not None: _str(b[k], k)
    if not _str(b.get("text"), "a button's label").strip(): raise ValueError("a button needs a label")
    if "url" in b: _str(b["url"], "url")
    return {k: v for k, v in b.items() if k != "token"}


def queue(key, name, text, *, kind, buttons=(), files=(), ref=None):
    """put a message for name under key -> True, or False when the key is there (unless dropped) or name has no Telegram now;
    ValueError for what could not be kept (a text that is not a str; _button; files, a ref or an extra that is not JSON).
    buttons: rows (a button alone is its own row) of dict(text, what, id, ckey, who, extra) or dict(text, url); files:
    [dict(id, file, name)] (relief/files.py); ref: JSON, given to VALID and back by told"""
    chat = links.chat_of(name)
    if chat is None: return False
    rows = [[_button(b) for b in (row if isinstance(row, (list, tuple)) else (row,))] for row in buttons or ()]
    files = list(files or ())
    if not all(isinstance(f, dict) for f in files): raise ValueError("a file must be a dict")
    row = (key, name, chat, kind, _str(text, "text"), _json(rows), _json(files), _json(ref), _absences._now())
    with tgdb.db() as c:
        c.execute("DELETE FROM outbox WHERE key=? AND state='dropped'", (key,))
        return c.execute("INSERT OR IGNORE INTO outbox(key, name, chat, kind, text, buttons, files, ref, at, state, next_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'queued', 0)",
                         row).rowcount == 1


def _told(r):
    return dict(state=r["state"], at=(r["sent_at"] if r["state"] in ("sent", "unsure") else None) or r["at"], name=r["name"],
                ref=json.loads(r["ref"]) if r["ref"] else None, files_failed=r["files_failed"])


def told(key):
    """dict(state, at, name, ref, files_failed) of the message under key, or None; at: when it was sent (sent, unsure), else queued"""
    with tgdb.db(read=True) as c: r = c.execute("SELECT * FROM outbox WHERE key=?", (key,)).fetchone()
    return _told(r) if r else None


def told_for(prefix):
    """{key: as told} of every key starting with prefix, as it is (no wildcards: keys hold any character)"""
    with tgdb.db(read=True) as c:
        return {r["key"]: _told(r) for r in c.execute("SELECT * FROM outbox WHERE substr(key, 1, ?)=?", (len(prefix), prefix))}


# ---- one message
def _pace():
    wait = _last[0] + SPACING - time.monotonic()
    if wait > 0: _sleep(wait)


def _held(now):
    """a pause Telegram asked for is not over (a clock put back does not make one longer than HOLD_MOST)"""
    return now < _hold[0] <= now + HOLD_MOST


def _call(clock, method, params=None, **more):
    _pace()
    try: r = tg.call(method, params, **more)
    finally: _last[0] = time.monotonic()
    if r["kind"] == "slow": _hold[0] = clock() + min(HOLD_MOST, max(1, r["retry_after"] or 0))
    return r


def _valid(item):
    """whether the message is still true; None when VALID raised"""
    try: return VALID(item) is not False
    except Exception as e:
        _log.warning("a message could not be checked (%s)", type(e).__name__)
        return None


def _cut(text):
    """text, or its first lines and MORE, LIMIT characters in all at most"""
    if len(text) <= LIMIT: return text
    room = LIMIT - len(MORE)
    end = text.rfind("\n", 0, room) + 1
    return text[:end if end > 1 else room] + MORE


def _keyboard(rows):
    """Telegram's inline keyboard; an action button gets its token (kept in rows) the first time"""
    out = []
    for row in rows:
        line = []
        for b in row:
            if "url" in b:
                if str(b["url"]).lower().startswith("https://"): line.append(dict(text=b["text"], url=b["url"]))
            else: line.append(dict(text=b["text"], callback_data="b:" + b.setdefault("token", secrets.token_urlsafe(12))))
        if line: out.append(line)
    return out


def _params(item, chat):
    params = dict(chat_id=chat, text=_cut(item["text"]), disable_web_page_preview=True)
    keys = _keyboard(item["buttons"])
    if keys: params["reply_markup"] = dict(inline_keyboard=keys)
    return params


def _claim(item, chat, now):
    """queued to sending, with the chat and the buttons, in one block on the store -> False when it is not queued any more"""
    until = datetime.datetime.fromisoformat(item["at"]).timestamp() + BUTTON_DAYS * 86400
    with tgdb.db() as c:
        if c.execute("UPDATE outbox SET state='sending', chat=?, sent_at=?, claimed=?, buttons=? WHERE key=? AND state='queued'",
                     (chat, _absences._now(), now, json.dumps(item["buttons"]), item["key"])).rowcount != 1: return False
        c.executemany("INSERT OR REPLACE INTO buttons(token, name, what, id, ckey, who, extra, until) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                      [(b["token"], item["name"], b.get("what"), b.get("id"), b.get("ckey"), b.get("who"), json.dumps(b.get("extra")), until)
                       for row in item["buttons"] for b in row if "token" in b])
    return True


def _retry(c, item, now, state):
    """nothing of item (in state) went out: it waits for its next try, or is failed at the sixth -> its state"""
    if item["tries"] < len(WAITS):
        c.execute("UPDATE outbox SET state='queued', sent_at=NULL, tries=tries+1, next_at=? WHERE key=? AND state=?", (now + WAITS[item["tries"]], item["key"], state))
        return "queued"
    c.execute("UPDATE outbox SET state='failed', sent_at=NULL, tries=tries+1 WHERE key=? AND state=?", (item["key"], state))
    return "failed"


def _bad(key, e):
    """the item itself cannot be sent: failed for good"""
    _log.error("a message could not be made (%s)", type(e).__name__)
    with tgdb.db() as c: c.execute("UPDATE outbox SET state='failed', tries=tries+1 WHERE key=? AND state='queued'", (key,))
    return "failed"


def _blocked(item, chat):
    """the person blocked the bot: unlinked, and the item removed; put back when the bot is not connected any more (somebody
    else's says the same to everybody). Whatever fails here, the item does not stay sending"""
    ours = False
    try:
        ours = links.connected() is not None
        if ours: links.unlink(item["name"], chat)
    except Exception as e: _log.warning("a chat could not be unlinked (%s)", type(e).__name__)
    with tgdb.db() as c:
        if ours: c.execute("DELETE FROM outbox WHERE key=? AND state IN ('sending', 'unsure')", (item["key"],))
        else: c.execute("UPDATE outbox SET state='queued', sent_at=NULL WHERE key=? AND state='sending'", (item["key"],))
    return None if ours else "queued"


def _settle(item, chat, r, now):
    """what the answer made of a message marked sending -> its state (None: removed). Another copy of the app may have marked it
    unsure meanwhile (recover): an answer that says what became of it still counts, but it is put back to queued only from
    sending"""
    key, kind = item["key"], r["kind"]
    if kind == "blocked": return _blocked(item, chat)
    with tgdb.db() as c:
        if r["ok"]:
            n = r["result"].get("message_id") if isinstance(r["result"], dict) else None
            c.execute("UPDATE outbox SET state='sent', sent_at=?, message_id=?, files_failed=? WHERE key=? AND state IN ('sending', 'unsure')",
                      (_absences._now(), n if type(n) is int and abs(n) < 2 ** 63 else None, len(item["files"]), key))
            return "sent"
        if kind == "unsure":
            c.execute("UPDATE outbox SET state='unsure', sent_at=? WHERE key=? AND state='sending'", (_absences._now(), key))
            return "unsure"
        if kind == "slow":
            c.execute("UPDATE outbox SET state='queued', sent_at=NULL, next_at=? WHERE key=? AND state='sending'", (_hold[0], key))
            return "queued"
        if kind == "network": return _retry(c, item, now, "sending")
        c.execute("UPDATE outbox SET state='failed', sent_at=NULL WHERE key=? AND state IN ('sending', 'unsure')", (key,))
        return "failed"


def _file(name, chat, f, clock):
    """one file -> True when it went, False when it did not, None when the rest are not to be tried either"""
    try:
        p = _files.path(f["id"], f["file"])
        if p is None: return False
        with open(p, "rb") as fh: data = fh.read()
        for n in range(FILE_TRIES):
            if _held(clock()):                                       # a short pause, from this file or the one before: waited out
                _sleep(max(0, _hold[0] - clock()))
                _hold[0] = 0.0
            if links.connected() is None or links.chat_of(name) != chat: return False      # their Telegram moved: the chat may be another's now
            r = _call(clock, "sendDocument", dict(chat_id=chat), files=[("document", f["name"], data)], timeout=FILE_TIMEOUT)
            if r["ok"]: return True
            if r["kind"] == "unsure" or (r["kind"] == "slow" and _hold[0] - clock() > FILE_SLOW): return None
            if r["kind"] not in ("slow", "network"): return False
            if r["kind"] == "network" and n < FILE_TRIES - 1: _sleep(FILE_WAIT)
    except Exception as e:
        _log.warning("a file could not be sent (%s)", type(e).__name__)
    return False


def _send_files(item, chat, clock):
    left = len(item["files"])
    for f in item["files"]:
        went = _file(item["name"], chat, f, clock)
        if went is None: break
        if went:
            left -= 1
            with tgdb.db() as c: c.execute("UPDATE outbox SET files_failed=? WHERE key=?", (left, item["key"]))


def _one(key, clock):
    """one item, when it is still queued -> its state now, or None"""
    with tgdb.db(read=True) as c: r = c.execute("SELECT * FROM outbox WHERE key=? AND state='queued'", (key,)).fetchone()
    if r is None: return None
    try: item = dict(r, buttons=json.loads(r["buttons"]), files=json.loads(r["files"]), ref=json.loads(r["ref"]))
    except Exception as e: return _bad(key, e)
    _pace()                                                          # before the checks, so they are as late as can be
    true, chat = _valid(item), None
    try: chat = links.chat_of(item["name"]) if true else None
    except sqlite3.OperationalError: raise
    except Exception as e:                                           # the app's records (the timetable being published), not the item
        _log.warning("a message could not be checked (%s)", type(e).__name__)
        true = None
    if true is None:
        with tgdb.db() as c: return _retry(c, item, clock(), "queued")
    if chat is None:
        if not _accounts.readable(): return None                     # nobody can be found now: not that they are gone
        with tgdb.db() as c: c.execute("UPDATE outbox SET state='dropped' WHERE key=? AND state='queued'", (key,))
        return "dropped"
    try:
        params = _params(item, chat)
        if not _claim(item, chat, clock()): return None
    except sqlite3.OperationalError: raise
    except Exception as e: return _bad(key, e)
    r = _call(clock, "sendMessage", params)
    if r["kind"] == "unsure": _doubt.set()
    state = _settle(item, chat, r, clock())
    if state == "sent": _send_files(item, chat, clock)
    return state


# ---- the runs
def _waiting():
    with tgdb.db(read=True) as c: return c.execute("SELECT count(*) FROM outbox WHERE state='queued'").fetchone()[0]


def _may():
    """a message may go at all now"""
    return links.connected() is not None and _accounts.readable()


def _unsure_old(now):
    with tgdb.db(read=True) as c: old = c.execute("SELECT 1 FROM outbox WHERE state='sending' AND claimed<?", (now - STUCK,)).fetchone()
    if old is None: return
    with tgdb.db() as c: c.execute("UPDATE outbox SET state='unsure' WHERE state='sending' AND claimed<?", (now - STUCK,))


def _run(now, limit):
    clock, sent = _clock if now is None else (lambda: now), 0
    if not _may(): return dict(sent=0, waiting=_waiting())
    _unsure_old(clock())
    if _held(clock()): return dict(sent=0, waiting=_waiting())
    if _doubt.is_set():
        if not _call(clock, "getMe", timeout=ME_TIMEOUT)["ok"]: return dict(sent=0, waiting=_waiting())
        _doubt.clear()
    with tgdb.db(read=True) as c:
        due = [r["key"] for r in c.execute("SELECT key FROM outbox WHERE state='queued' AND next_at<=? ORDER BY at, rowid LIMIT ?", (clock(), limit))]
    for key in due:
        if _doubt.is_set() or _held(clock()) or not _may(): break
        try: sent += _one(key, clock) == "sent"
        except sqlite3.OperationalError as e:                        # the store fails: the rest would too
            _log.error("a message could not be sent (%s)", type(e).__name__)
            break
        except Exception as e:                                       # one marked sending stays so, and is unsure after STUCK seconds
            _log.error("a message could not be sent (%s)", type(e).__name__)
    return dict(sent=sent, waiting=_waiting())


def send_due(now=None, limit=50):
    """send what is due, limit messages at most -> dict(sent, waiting: how many are still queued), with busy=True at once when
    a run is going. now: the time in epoch seconds (tests), else the clock at each step"""
    if not _busy.acquire(blocking=False): return dict(sent=0, waiting=_waiting(), busy=True)
    try: return _run(now, limit)
    finally: _busy.release()


def _mark_unsure():
    with tgdb.db() as c: return c.execute("UPDATE outbox SET state='unsure' WHERE state='sending'").rowcount


def recover():
    """whatever was being sent when the app stopped may have gone: unsure -> how many. Once, when the app starts"""
    with _busy: return _mark_unsure()


def prune(now=None):
    """messages that are over and were queued more than KEEP_DAYS ago, and buttons past their time, are deleted"""
    now = _clock() if now is None else now
    tz = datetime.datetime.fromisoformat(_absences._now()).tzinfo
    before = datetime.datetime.fromtimestamp(now - KEEP_DAYS * 86400, tz).isoformat(timespec="seconds")
    with tgdb.db() as c:
        c.execute("DELETE FROM outbox WHERE state IN ('sent', 'failed', 'unsure', 'dropped') AND at<?", (before,))
        c.execute("DELETE FROM buttons WHERE until<?", (now,))


def _loop(every):
    ready = False
    while not _stop.is_set():
        try:
            if not ready:
                recover()                                            # nothing goes before this has worked
                ready = True
                prune()
            send_due()
        except Exception as e: _log.error("the message sender failed (%s)", type(e).__name__)
        _wake.wait(every); _wake.clear()


def wake():
    """there is something to send: the sender looks now"""
    _wake.set()


def start(every=EVERY):
    """the sender: a daemon thread named relief-telegram, started once (app.py, when RELIEF_JOBS=on and there is a token)"""
    global _sender
    if _sender is not None and _sender.is_alive(): return _sender
    _stop.clear()
    _sender = threading.Thread(target=_loop, args=(every,), name="relief-telegram", daemon=True)
    _sender.start()
    return _sender

"""The messages waiting to go out on Telegram and the sender (tables outbox and buttons of relief/tgdb.py). A message is sent
once, or marked "unsure" (it may have gone; nobody can tell): it never goes twice.

queue puts a message under its key, for a person linked now (links.chat_of); a key there already, in any state but dropped, is
not queued again. States: queued; sending (marked and committed before anything goes out, with nothing locked during the call);
sent; failed (Telegram refused it, or every try failed); unsure (the request may have gone out, or the app stopped while it
was going: never tried again by itself); dropped (no longer true, or its person had no Telegram when it was to go: as if it
had never been queued, so its key may be queued again).

send_due sends what is due, oldest first, one run at a time in this copy of the app; an item is taken from queued to sending
in one statement, so two copies never send the same one either. Nothing goes, and nothing is changed, while the bot is not
connected (links.connected: no token, or another bot's). Each item: VALID(item) False drops it (tell.still_true; raising, or
anything else, lets it go); the chat is links.chat_of(name) at that moment, never the one it was queued with; then what
tg.call answers: "network" (nothing went out) waits WAITS[tries] and after the last of them fails; "slow" waits as long as
Telegram says (SLOW_MOST at most, SLOWS times in all), no try counted, and ends the run, with everything else held as long
(HOLD at most); "blocked" unlinks the person, only while that chat is still theirs, and removes the item, so that its key may
be queued once they link again; "unsure" is unsure; anything else failed.

The text is plain (no parse_mode) and cut at a line end when longer than LIMIT. A button's token is made for the first try
and kept with the item, so every try carries the same ones; its row in buttons is (re)written with the item's sending, until
BUTTON_DAYS after that try. A button that opens an address is left out unless it is https (Telegram refuses others).

Files follow the message once it is sent, each by sendDocument, to the same chat while it is still that person's. files_failed
counts those that have not gone: all of them when the message goes, one less as each goes, so a restart in between leaves the
truth; a file "slow" or "network" is tried FILE_TRIES times in all, an "unsure" one once. The message stays sent.

start is the sender: one daemon thread, recover first (whatever was sending when the app stopped is unsure), then prune, then
send_due every EVERY seconds or when woken. Failures are logged to "relief.telegram" by their kind alone: never a text, a
name, a chat, a token or a key (keys hold names)."""
import datetime, json, logging, secrets, sqlite3, threading, time

from relief import absences as _absences
from relief import files as _files
from relief import links, tg, tgdb

EVERY = 5                                       # seconds between the sender's runs
WAITS = (5, 30, 120, 600, 1800)                 # seconds before the next try, by how many have failed
SLOWS, SLOW_MOST, HOLD = 20, 3600, 60
SPACING = 0.05                                  # seconds at least between two calls (tests: 0)
LIMIT, MORE = 4000, "…and more in the app."
BUTTON_DAYS, KEEP_DAYS = 30, 400
FILE_TRIES, FILE_WAIT, FILE_SLOW, FILE_TIMEOUT = 3, 2, 20, 60
VALID = lambda item: True                       # item: the stored message as a dict (key, name, kind, ref, text, ...)
_busy = threading.Lock()                        # one run at a time
_last = [0.0]                                   # when the last call ended (time.monotonic)
_wake, _stop = threading.Event(), threading.Event()
_sender = None
_log = logging.getLogger("relief.telegram")


def _clock(): return time.time()
def _sleep(seconds): time.sleep(seconds)


# ---- the queue
def _rows(buttons):
    """rows of buttons, each with its text (a button alone is its own row) and no token yet; a button that cannot be shown is
    refused here, by an exception, and not when it is to go"""
    def one(b): return {**{k: v for k, v in b.items() if k != "token"}, "text": b["text"]}
    return [[one(b) for b in (row if isinstance(row, (list, tuple)) else (row,))] for row in buttons or ()]


def queue(key, name, text, *, kind, buttons=(), files=(), ref=None):
    """put a message for name under key -> True, or False when the key is there (unless dropped) or name has no Telegram now.
    buttons: rows of dict(text, what, id, ckey, who, extra) or dict(text, url); files: [dict(id, file, name)] (relief/files.py);
    ref: JSON, given to VALID and back by told"""
    chat = links.chat_of(name)
    if chat is None: return False
    row = (key, name, chat, kind, text, json.dumps(_rows(buttons)), json.dumps([dict(f) for f in files or ()]), json.dumps(ref), _absences._now())
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


def _call(method, params, **more):
    _pace()
    try: return tg.call(method, params, **more)
    finally: _last[0] = time.monotonic()


def _valid(item):
    try: return VALID(item) is not False
    except Exception as e:
        _log.warning("a message could not be checked (%s)", type(e).__name__)
        return True


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
    with tgdb.db() as c:
        if c.execute("UPDATE outbox SET state='sending', chat=?, sent_at=?, buttons=? WHERE key=? AND state='queued'",
                     (chat, _absences._now(), json.dumps(item["buttons"]), item["key"])).rowcount != 1: return False
        c.executemany("INSERT OR REPLACE INTO buttons(token, name, what, id, ckey, who, extra, until) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                      [(b["token"], item["name"], b.get("what"), b.get("id"), b.get("ckey"), b.get("who"), json.dumps(b.get("extra")), now + BUTTON_DAYS * 86400)
                       for row in item["buttons"] for b in row if "token" in b])
    return True


def _settle(item, chat, r, now):
    """what the answer made of a message marked sending -> its state (None: removed) and whether the run ends. Another copy of
    the app may have marked it unsure meanwhile (recover): an answer that says what became of it still counts, but it is put
    back to queued only from sending"""
    key, kind = item["key"], r["kind"]
    if kind == "blocked":
        if links.connected() is not None and links.chat_of(item["name"]) == chat: links.unlink(item["name"], chat)
        with tgdb.db() as c: c.execute("DELETE FROM outbox WHERE key=? AND state IN ('sending', 'unsure')", (key,))
        return None, False
    with tgdb.db() as c:
        if r["ok"]:
            n = r["result"].get("message_id") if isinstance(r["result"], dict) else None
            c.execute("UPDATE outbox SET state='sent', sent_at=?, message_id=?, files_failed=? WHERE key=? AND state IN ('sending', 'unsure')",
                      (_absences._now(), n if type(n) is int and abs(n) < 2 ** 63 else None, len(item["files"]), key))
            return "sent", False
        if kind == "unsure":
            c.execute("UPDATE outbox SET state='unsure', sent_at=? WHERE key=? AND state='sending'", (_absences._now(), key))
            return "unsure", False
        if kind == "slow" and item["slows"] < SLOWS:
            wait = min(SLOW_MOST, max(1, r["retry_after"] or 0))
            c.execute("UPDATE outbox SET state='queued', sent_at=NULL, slows=slows+1, next_at=? WHERE key=? AND state='sending'", (now + wait, key))
            c.execute("UPDATE outbox SET next_at=max(next_at, ?) WHERE state='queued' AND key<>?", (now + min(wait, HOLD), key))
            return "queued", True
        if kind == "network" and item["tries"] < len(WAITS):
            c.execute("UPDATE outbox SET state='queued', sent_at=NULL, tries=tries+1, next_at=? WHERE key=? AND state='sending'",
                      (now + WAITS[item["tries"]], key))
            return "queued", False
        c.execute("UPDATE outbox SET state='failed', sent_at=NULL WHERE key=? AND state IN ('sending', 'unsure')", (key,))
        return "failed", kind == "slow"


def _file(name, chat, f):
    """one file sent -> True, or False when it was not (or may not have been)"""
    try:
        p = _files.path(f["id"], f["file"])
        if p is None: return False
        with open(p, "rb") as fh: data = fh.read()
        for n in range(FILE_TRIES):
            if links.connected() is None or links.chat_of(name) != chat: return False      # their Telegram moved: the chat may be another's now
            r = _call("sendDocument", dict(chat_id=chat), files=[("document", f["name"], data)], timeout=FILE_TIMEOUT)
            if r["ok"]: return True
            if r["kind"] not in ("slow", "network") or n == FILE_TRIES - 1: return False
            _sleep(min(FILE_SLOW, max(FILE_WAIT, r["retry_after"] or 0)))
    except Exception as e:
        _log.warning("a file could not be sent (%s)", type(e).__name__)
    return False


def _send_files(item, chat):
    left = len(item["files"])
    for f in item["files"]:
        if _file(item["name"], chat, f):
            left -= 1
            with tgdb.db() as c: c.execute("UPDATE outbox SET files_failed=? WHERE key=?", (left, item["key"]))


def _one(key, clock):
    """one item, when it is still queued -> its state now and whether the run ends"""
    with tgdb.db(read=True) as c: r = c.execute("SELECT * FROM outbox WHERE key=? AND state='queued'", (key,)).fetchone()
    if r is None: return None, False
    item = dict(r, buttons=json.loads(r["buttons"]), files=json.loads(r["files"]), ref=json.loads(r["ref"]))
    _pace()                                                          # before the checks, so they are as late as can be
    chat = links.chat_of(item["name"]) if _valid(item) else None
    if chat is None:
        with tgdb.db() as c: c.execute("UPDATE outbox SET state='dropped' WHERE key=? AND state='queued'", (key,))
        return "dropped", False
    params = _params(item, chat)
    if not _claim(item, chat, clock()): return None, False
    got = _settle(item, chat, _call("sendMessage", params), clock())
    if got[0] == "sent": _send_files(item, chat)
    return got


# ---- the runs
def _waiting():
    with tgdb.db(read=True) as c: return c.execute("SELECT count(*) FROM outbox WHERE state='queued'").fetchone()[0]


def _run(now, limit):
    clock, sent = _clock if now is None else (lambda: now), 0
    with tgdb.db(read=True) as c:
        due = [r["key"] for r in c.execute("SELECT key FROM outbox WHERE state='queued' AND next_at<=? ORDER BY at, rowid LIMIT ?", (clock(), limit))]
    for key in due:
        if links.connected() is None: break
        try: state, ends = _one(key, clock)
        except Exception as e:                                       # one marked sending stays so: unsure when the app next starts
            _log.error("a message could not be sent (%s)", type(e).__name__)
            state, ends = None, isinstance(e, sqlite3.Error)         # the store fails: the rest would too
        sent += state == "sent"
        if ends: break
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

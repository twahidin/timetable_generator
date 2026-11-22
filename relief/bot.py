"""An update from Telegram in, an answer out. handle(update) never raises: a failure is logged to "relief.telegram" by its kind
alone (never a code, a chat id, a name, a token or what was typed).

Only a message, or a press of a button, in a person's own (private) chat is read or answered; groups, channels, other bots and
every other kind of update are ignored. Anything shaped like a code (alone, or after /start, as Telegram's own link sends it) is tried as a link
code; when it is not a current one the message is deleted and answered BAD_CODE (BAD_CODE_KEPT when Telegram did not delete
it), the same for a real personal code and a made-up one (links.use never looks at those). The code a chat linked itself
with, sent by it again, is answered HELLO and changes nothing (links.again). A chat whose person is not there, or has no relief now
(links.name_of), is answered NOT_LINKED. Each of these two answers counts against links.tries, and a chat over it gets nothing at all: no
answer, no deleteMessage, its code not tried. The count is made with the check (_counting, never held during a call to
Telegram), so messages that come at once get no more.

/start, /help and anything else from a linked chat: HELLO. /stop unlinks. A person's link that moved is told in the old chat
(MOVED_LINK); a chat that was someone else's is told so before HELLO (TAKEN). Linking, moving and unlinking are each one
history entry by that person, via telegram (init's note), naming no chat, handle or code. A link just made asks relief.tell
for what is still to come for that person.

A press does what the same button on the page does, through the same functions (relief.cover, relief.absences), with the same
refusals, and the same history entry and what follows it (web.step_saved), by that person via telegram. It is judged when it
is pressed (_button): its token is in the table and has not run out (OLD_BUTTON), the chat is of the very person it was sent to
and they have the right it needs now (NOT_YOURS_BUTTON; ACTIONS); a chat of nobody there gets NOT_LINKED, counted as above. A
cover that is not in its absence any more is looked for by its absent teacher (_cover_of). Done, the message it was on loses its
buttons and gains a line of what was done and when. Refused in the app's own words, whether at the press or when its why was
typed, it loses them too and gains that sentence, for pressing again cannot help; unless it can (_acted: STAYS, and what the kind
has in ACTIONS). It stays as it is for a button that may not be pressed (_button) and for WENT_WRONG. Acknowledge pressed again
says the same and saves nothing.

Request to change and Not needed ask why first: a talk (table talks), one a chat, TALK_MINUTES long, the newest in place of any
other. Until it is over, what is typed there is the why, whatever it looks like (never a code), judged again as a press is; a
blank or long one is asked for again. /cancel ends it, and so do COMMANDS, which work as ever. A talk is over before its why is
acted on, so it is acted on once. When the question may not have reached the person there is no talk.

One press or line at a time (_pressing), so two at once save once. It is let go, as the absences lock is, before anything is said
to Telegram; what was saved is written down and followed up first, then the press is answered, then its message is changed. A
failure there changes nothing of what was done; one that comes before anything was done is answered WENT_WRONG."""
import collections, datetime, json, logging, re, threading, types

import store
from relief import absences as _absences
from relief import cover as _cover
from relief import fill as _fill
from relief import lessons as _lessons
from relief import links, tell, tg, tgdb
from relief import settings as _settings
from relief import web as _web

HELLO = "Linked: {name}. You'll get your reliefs here. Send /relief to ask for relief, /stop to unlink."
NOT_LINKED = "This Telegram is not linked. Open Relief in the school's app, press Link Telegram and follow the link there."
_BAD = "That code is not right or has run out. Get a new one in the app. If it was your personal code, do not send it here: it opens the app. "
BAD_CODE = _BAD + "I have deleted your message."
BAD_CODE_KEPT = _BAD + "Please delete your message now."
MOVED_LINK = "Your relief messages now go to another Telegram. If this was not you, tell the relief team."
TAKEN = "This Telegram was linked to someone else before. Their relief messages no longer come here."
STOPPED = "Unlinked. Your relief messages stop here. To link again, open Relief in the school's app and press Link Telegram."
NOT_YOURS_BUTTON = "This button is not for you."
OLD_BUTTON = "This button is no longer active."
WHY_CHANGE = "Say why in one line. Until the relief team replies, this relief is still yours."
WHY_CANCEL = "Cancel this absence? Say why in one line."
SENT_CHANGE = "Sent to the relief team. Until they reply, this relief is still yours."
SENT_CANCEL = "Cancelled. The relief team has been told."
NOTHING = "Nothing was changed."
WENT_WRONG = "Something went wrong. Try again in the app."
COMMANDS = ("/start", "/stop", "/help", "/relief")        # these end a talk
TALK_MINUTES = 15
WHY_MOST = 200                               # characters of a why (as relief.cover and relief.absences have it)
ANSWER_MOST, TEXT_MOST = 200, 4096           # characters Telegram takes of an answer to a press, and of a message
TIMEOUT = 8                                  # seconds for each call made while Telegram waits for the hook's answer
_HANDLE = re.compile(r"[A-Za-z0-9_]{1,64}")
_DATA = re.compile(r"b:([A-Za-z0-9_-]{16})")              # a button's callback data (relief/outbox.py)
STAYS = (_web.NO_PUB,)                       # a refusal that keeps any button: a publish may be swapping folders
_log = logging.getLogger("relief.telegram")
_counting = threading.Lock()
_pressing = threading.Lock()
_note = None
# what a press or a line comes to: what is answered (an alert: the person has to close it), the line its message gains, losing
# its buttons, the question asked and the talk opened for it, and what follows (the history entry and the rest), called with nothing held
_Out = collections.namedtuple("_Out", "text alert line ask talk after", defaults=(None, False, None, None, None, None))


def init(note):
    """note(what, text, absence=None, who=None, via=None): one history entry (app.py's _relief_entry)"""
    global _note
    _note = note


def reply(chat, text, buttons=None, ask=False):
    """one message to a chat; buttons: rows of Telegram's own inline buttons; ask: Telegram opens the line for the answer"""
    params = dict(chat_id=chat, text=text, disable_web_page_preview=True)
    if buttons: params["reply_markup"] = dict(inline_keyboard=buttons)
    elif ask: params["reply_markup"] = dict(force_reply=True)
    return tg.call("sendMessage", params, timeout=TIMEOUT)


def handle(update):
    try:
        u = update if isinstance(update, dict) else {}
        if isinstance(u.get("message"), dict): _message(u["message"])
        elif isinstance(u.get("callback_query"), dict): _press(u["callback_query"])
    except Exception as e:
        _log.warning("an update could not be handled (%s)", type(e).__name__)


def _noted(what, text, who):
    if _note is None: return
    try: _note(what, text, who=who, via=links.VIA)
    except Exception as e: _log.warning("a history entry could not be made (%s)", type(e).__name__)


def _private(m):
    """the chat's id when the message (or the press: its message's chat, and who pressed) is in a person's own chat with the bot, else None"""
    c, f = m.get("chat"), m.get("from")
    if not isinstance(c, dict) or c.get("type") != "private" or type(c.get("id")) is not int or not 0 < c["id"] < 2 ** 63: return None
    if isinstance(f, dict) and f.get("is_bot"): return None
    return c["id"]


def _handle(m):
    f = m.get("from")
    u = f.get("username") if isinstance(f, dict) else None
    return u if isinstance(u, str) and _HANDLE.fullmatch(u) else None


def _command(text):
    """('/start', 'the rest') of a command, its @bot name taken off; ('', text) of anything else"""
    if not text.startswith("/"): return "", text
    parts = text.split(None, 1)
    return parts[0].split("@", 1)[0].lower(), parts[1] if len(parts) > 1 else ""


def _message(m):
    chat = _private(m)
    if chat is None: return
    text = m["text"] if isinstance(m.get("text"), str) else ""
    cmd, rest = _command(text.strip())
    talk = _talk(chat)
    if talk and cmd in COMMANDS: _end(chat, talk)
    elif talk and _line(chat, talk, text, cmd): return
    if cmd == "/start" and links.shaped(rest): return _code(chat, m, rest)
    if cmd not in ("/start", "/stop", "/help") and links.shaped(text): return _code(chat, m, text)
    key = f"tg:{chat}"
    with _counting:
        if links.tries.blocked(key): return
        name = links.name_of(chat)
        was = links.unlink_chat(chat) if cmd == "/stop" else None
        if name is None: links.tries.fail(key)
    if was: _noted("telegram unlinked", "Telegram unlinked", was)
    if name is None: reply(chat, NOT_LINKED)
    elif was: reply(chat, STOPPED)
    else: reply(chat, HELLO.format(name=name))


def _code(chat, m, code):
    key, lost = f"tg:{chat}", []
    with _counting:
        if links.tries.blocked(key): return
        twice = links.again(code, chat)
        name = twice or links.use(code, chat, _handle(m), lost)
        if name is None: links.tries.fail(key)
    if name is None:
        gone = type(m.get("message_id")) is int and tg.call("deleteMessage", dict(chat_id=chat, message_id=m["message_id"]), timeout=TIMEOUT)["ok"]
        reply(chat, BAD_CODE if gone else BAD_CODE_KEPT)
        return
    moved = any(x["name"] == name for x in lost)
    if not twice: _noted("telegram linked", "Telegram linked (moved from another Telegram)" if moved else "Telegram linked", name)
    for x in lost:
        if x["name"] == name: reply(x["chat"], MOVED_LINK)
        else:
            _noted("telegram unlinked", f"Telegram unlinked for {x['name']}: the same Telegram is now {name}'s", name)
            reply(x["chat"], TAKEN)
    reply(chat, HELLO.format(name=name))
    if not twice: tell.soon()                # what is still to come for them, after HELLO


# ---- a press
def _clock():
    """now, in epoch seconds, by the app's clock (as a button's time is set)"""
    return datetime.datetime.fromisoformat(_absences._now()).timestamp()


def _hm(at):
    """'07:46': a time kept in a record, in school time"""
    return f"{_fill._when(at):%H:%M}"


def _broke(e):
    _log.warning("a press could not be done (%s)", type(e).__name__)
    return _Out(WENT_WRONG, alert=True)


def _press(q):
    m = q["message"] if isinstance(q.get("message"), dict) else {}
    chat = _private({"chat": m.get("chat"), "from": q.get("from")})
    if chat is None: return
    n, text = m.get("message_id"), m.get("text")
    message = dict(id=n if type(n) is int else None, text=text if isinstance(text, str) else None)
    try: out = _pressed(chat, q.get("data"), message)
    except Exception as e: out = _broke(e)
    if out is None: return
    _follow(out)
    lost = out.ask is not None and not reply(chat, out.ask, ask=True)["ok"]
    _answer(q, WENT_WRONG if lost else out.text, lost or out.alert)
    if lost: _end(chat, out.talk)                # what is typed next is not the answer to a question that may not have come
    if out.line: _settle(chat, message, out.line)


def _pressed(chat, data, message):
    """what the press comes to; None from a chat over the limit (nothing at all)"""
    key = f"tg:{chat}"
    with _counting:
        if links.tries.blocked(key): return None
        there = links.person(chat) is not None
        if not there: links.tries.fail(key)
    if not there: return _Out(NOT_LINKED, alert=True)
    token = _DATA.fullmatch(data) if isinstance(data, str) else None
    def do():
        b = _button(chat, token[1] if token else "")
        return _acted(b, lambda: ACTIONS[b["what"]][1](types.SimpleNamespace(chat=chat, button=b, message=message)))
    return _did(do)


def _acted(b, f):
    """what f does for button b comes to; refused by the app: its sentence, which the message gains too, unless the button is
    one to press again (STAYS, or a sentence its kind has in ACTIONS)"""
    try: return f()
    except ValueError as e:
        if type(e) is not ValueError: raise
        stays = any(str(e) == x.format(name=b["who"]) for x in (*STAYS, *ACTIONS[b["what"]][2]))
        return _Out(str(e), alert=True, line=None if stays else str(e))


def _did(f):
    """what f comes to, no other press or line going at the same time; a button that may not be pressed is its sentence"""
    try:
        with _pressing: return f()
    except Exception as e:
        return _Out(str(e), alert=True) if type(e) is ValueError else _broke(e)      # a kind of ValueError (JSON, text) is no sentence


def _follow(out):
    """what follows a save: a failure there changes nothing of what was done, or of what is answered"""
    if out.after is None: return
    try: out.after()
    except Exception as e: _log.warning("what follows a press failed (%s)", type(e).__name__)


def _answer(q, text, alert):
    if not isinstance(q.get("id"), str) or not q["id"]: return
    params = dict(callback_query_id=q["id"])
    if text: params.update(text=text[:ANSWER_MOST], show_alert=alert)
    tg.call("answerCallbackQuery", params, timeout=TIMEOUT)


def _settle(chat, message, line):
    """the message a button was on: its text and line, with no buttons; when Telegram does not do it, nothing more"""
    n, text = message["id"], message["text"]
    if n is None: return
    if text is None: tg.call("editMessageReplyMarkup", dict(chat_id=chat, message_id=n), timeout=TIMEOUT)       # too old for its text
    elif not text.endswith(line):                # it is there when it was pressed again
        tg.call("editMessageText", dict(chat_id=chat, message_id=n, text=f"{text[:TEXT_MOST - len(line) - 2]}\n\n{line}", disable_web_page_preview=True), timeout=TIMEOUT)


def _button(chat, token):
    """the button under token (its row, extra a dict), when the chat's person may press it now, else the sentence"""
    with tgdb.db(read=True) as c: r = c.execute("SELECT * FROM buttons WHERE token=?", (token,)).fetchone()
    if r is None or r["until"] < _clock() or r["what"] not in ACTIONS: raise ValueError(OLD_BUTTON)
    p = links.person(chat)
    if p is None or p["name"] != r["name"] or ACTIONS[r["what"]][0] not in links.rights_named(p["name"]): raise ValueError(NOT_YOURS_BUTTON)
    extra = json.loads(r["extra"]) if r["extra"] else None
    return dict(r, extra=extra if isinstance(extra, dict) else {})


# ---- what a press and a line do (with _pressing held)
def _published():
    pub = store.published()
    if not pub: raise ValueError(_web.NO_PUB)
    return pub


def _in(r, ckey):
    try: return (r, *_cover.find(r, ckey))
    except ValueError: return None


def _cover_of(b):
    """(record, lesson, cover) of a button: in the absence it was sent for, else (an exam's takeover moved it) in another of the
    same absent teacher's that is not cancelled, the one approved first; CHANGED when there is none"""
    with _absences._LOCK:                        # a takeover's two saves are seen whole
        own = _absences.load(b["id"])
        got = _in(own, b["ckey"]) if own else None
        if got: return got
        others = [r for r in _absences.all_records() if r.get("teacher") == b["extra"].get("absent") and not r.get("cancelled")]
    got = [v for v in (_in(r, b["ckey"]) for r in others) if v]
    if not got: raise ValueError(_absences.CHANGED)
    return min(got, key=lambda v: _cover.state(*v) not in _web.APPROVED)


def _theirs(b):
    """_cover_of, while it is the relief of the button's person, else the page's answer"""
    got = _cover_of(b)
    _cover._mine(*got, b["name"])
    return got


def _after(step, r, b, pub):
    return lambda: _web.step_saved(step, r, b["ckey"], b["name"], pub, by=(b["name"], links.VIA))


def _ack(p):
    b, pub = p.button, _published()
    r, x, c = _theirs(b)
    t = _talk(p.chat)
    if t and t["kind"] == "change":              # a request to change this very cover that waits for its why is over
        d = json.loads(t["data"])
        if (d.get("absent"), d.get("ckey")) == (b["extra"].get("absent"), b["ckey"]): _end(p.chat, t)
    first = False
    if _cover.state(r, x, c) != "acknowledged": r, first = _cover.acknowledge_once(r["id"], b["ckey"], b["name"])
    line = f"✅ Acknowledged {_hm(_cover.find(r, b['ckey'])[1]['ack']['at'])}."
    return _Out(line, line=line, after=_after("ack", r, b, pub) if first else None)


def _approve(p):
    b, pub = p.button, _published()
    r, x, c = _cover_of(b)
    settings = _settings.load(pub)
    r = _cover.approve(r["id"], b["ckey"], b["who"], b["name"], pub, settings, links=_web._links_or_none(pub, settings["calendar"]))
    line = f"✅ Approved: {b['who']}, {_hm(_cover.find(r, b['ckey'])[1]['approved']['at'])}."
    return _Out(line, line=line, after=_after("approve", r, b, pub))


def _ask_change(p):
    """what the page would refuse whatever the why is refused at once; nothing is saved"""
    _published()
    r, x, c = _theirs(p.button)
    _absences._past(x)
    if _cover.state(r, x, c) == "change": raise ValueError(_cover.ASKED_ALREADY)
    return _asked(p, "change")


def _change(b, why):
    pub = _published()
    r = _cover.ask_change(_theirs(b)[0]["id"], b["ckey"], why, b["name"])
    return _Out(SENT_CHANGE, line=f"↩ Asked to change {_hm(_cover.find(r, b['ckey'])[1]['change']['at'])}.", after=_after("change", r, b, pub))


def _ask_cancel(p):
    """as _ask_change"""
    _published()
    r = _absences._editable(p.button["id"])
    _absences._may_change(r, p.button["name"], False)
    if tell._last(r) < _lessons.today().isoformat(): raise ValueError(_absences.PAST_ABSENCE)
    return _asked(p, "cancel")


def _cancel(b, why):
    pub = _published()
    r = _absences.cancel(b["id"], why, b["name"], team=False)                    # theirs, or the one they planned: never by the team's right
    return _Out(SENT_CANCEL, line=f"❌ Cancelled {_hm(r['cancelled']['at'])}.", after=_after("cancel", r, b, pub))


# ---- talks
def _asked(p, kind):
    """a talk of that kind open in the chat, in place of any other, and its question to be asked"""
    b = p.button
    data = json.dumps(dict(id=b["id"], ckey=b["ckey"], absent=b["extra"].get("absent"), token=b["token"], message=p.message))
    talk = dict(kind=kind, data=data, until=_clock() + TALK_MINUTES * 60)
    with tgdb.db() as c: c.execute("INSERT OR REPLACE INTO talks(chat, kind, data, until) VALUES (?, ?, ?, ?)", (p.chat, kind, data, talk["until"]))
    return _Out(ask=TALKS[kind][0], talk=talk)


def _end(chat, talk):
    """the chat's talk is over -> whether it was this one, and not over before"""
    with tgdb.db() as c:
        return c.execute("DELETE FROM talks WHERE chat=? AND kind=? AND data=? AND until=?", (chat, talk["kind"], talk["data"], talk["until"])).rowcount == 1


def _talk(chat):
    """the talk that waits for a line in the chat, or None; one whose time is over is deleted, one of another kind left alone"""
    with tgdb.db(read=True) as c: r = c.execute("SELECT kind, data, until FROM talks WHERE chat=?", (chat,)).fetchone()
    if r is None: return None
    if r["until"] < _clock():
        _end(chat, r)
        return None
    return dict(r) if r["kind"] in TALKS else None


def _line(chat, talk, text, cmd):
    """what was typed while a talk waits -> whether it was for the talk (the rest is for _message)"""
    if links.tries.blocked(f"tg:{chat}"): return True                            # nothing at all
    if links.name_of(chat) is None:
        _end(chat, talk)
        return False
    if cmd == "/cancel":
        if not _end(chat, talk): return False
        reply(chat, NOTHING)
        return True
    question, f = TALKS[talk["kind"]]
    why = " ".join(text.split())                 # one line, as the page's box gives it
    if not 1 <= len(why) <= WHY_MOST:
        reply(chat, question, ask=True)
        return True
    data = {}
    def do():
        if not _end(chat, talk): return None     # over meanwhile: this line is not its why
        data.update(json.loads(talk["data"]))
        b = _button(chat, data["token"])
        return _acted(b, lambda: f(b, why))
    out = _did(do)
    if out is None: return False
    _follow(out)
    reply(chat, out.text)
    if out.line: _settle(chat, data["message"], out.line)
    return True


# what a button does, by its kind: (the right it needs, f(p) with p.chat, p.button (_button) and p.message (its id and text) ->
# _Out, the refusals that keep it: {name} is the one it shows)
ACTIONS = dict(ack=("relief", _ack, ()), change=("relief", _ask_change, ()), cancel=("relief", _ask_cancel, ()),
               approve=("relief.team", _approve, (_cover.PICK_CHANGED, _cover.NOT_FREE)))
# what a talk asks, by its kind, and what its why does: f(the button, why) -> _Out
TALKS = dict(change=(WHY_CHANGE, _change), cancel=(WHY_CANCEL, _cancel))

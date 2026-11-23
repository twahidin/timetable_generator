"""An update from Telegram in, an answer out. handle(update) never raises: a failure is logged to "relief.telegram" by its kind
alone (never a code, a chat id, a name, a token or what was typed).

Only a message, or a press of a button, in a person's own (private) chat, by that person (from has the chat's id, as Telegram
always gives it there), is read or answered; groups, channels, other bots and every other kind of update are ignored, and a message
changed after it was sent unless the person is asking for relief. Anything shaped like a code (alone, or after /start, as Telegram's
own link sends it) is tried as a link code; when it is not a current one the message is deleted and answered BAD_CODE (BAD_CODE_KEPT when Telegram did not delete
it), the same for a real personal code and a made-up one (links.use never looks at those). The code a chat linked itself
with, sent by it again, is answered HELLO and changes nothing (links.again). A chat whose person is not there, or has no relief now
(links.name_of), is answered NOT_LINKED. Each of these two answers counts against links.tries, and a chat over it gets nothing at all: no
answer, no deleteMessage, its code not tried. The count is made with the check (_counting, never held during a call to
Telegram), so messages that come at once get no more.

/start and /help from a linked chat: HELLO; anything else no conversation takes: NOT_READ (a line, a sticker, another command), but a
file or a photo is said not to be attached (asking.stray). /stop
unlinks. /relief asks for relief: relief/asking.py, which has all of that conversation (a talk of kind ASK); here it is only led to,
by /relief, a press of one of its buttons, or a message while it goes on. It ends when another talk is opened in its place or a
command is sent; when a day had been chosen by then the person is told that nothing was sent (asking.NOT_SENT), but for /relief, which
begins another. A person's link that moved is told in the old chat (MOVED_LINK); a chat that was someone else's is told so before HELLO (TAKEN). Linking, moving and unlinking are each one
history entry by that person, via telegram (init's note), naming no chat, handle or code. A link just made asks relief.tell
for what is still to come for that person.

A press does what the same button on the page does, through the same functions (relief.cover, relief.absences), with the same
refusals, and the same history entry and what follows it (web.step_saved), by that person via telegram. It is judged when it
is pressed (_button): its token is in the table and has not run out (OLD_BUTTON), the chat is of the very person it was sent to
and they have the right it needs now (NOT_YOURS_BUTTON; ACTIONS); a chat of nobody there gets NOT_LINKED, counted as above. A
cover that is not in its absence any more is looked for by its absent teacher (_cover_of). Done, the message it was on loses its
buttons and gains a line of what was done and when; after Approve it gains one button, Send out (as the page, Approve tells nobody).
Acknowledge and Request to change are the relief teacher's only once the relief has reached them (web._reached). Refused in the
app's own words, whether at the press or when its why was typed, it loses them too and gains that sentence, for pressing again
cannot help; unless it can (_acted: STAYS, and what the kind has in ACTIONS: a lesson an exam or event stops may be on again before anybody is told that it was not). It stays as it is for a
button that may not be pressed (_button) and for WENT_WRONG. Acknowledge pressed again says the same and saves nothing. Remind
them again (relief/report.py: the reliefs its report listed, its extra) never changes the report: whoever could not be reminded, it
can be pressed again later.

Request to change and Not needed ask why first: a talk (table talks), one a chat, TALK_MINUTES long, the newest in place of any
other. Until it is over, what is typed there is the why, whatever it looks like (never a code), judged again as a press is. A line
that is blank, too long or no reason (_no_reason: "No", "Ok, thanks") is nobody's why: the question is asked again. So it is, after
LAST_ONE, when the line replies to any message but the question asked last (its id is in the talk). /cancel ends the talk, and
so do COMMANDS, which work as ever. A talk that runs out is deleted when it is met, by the clock (forget) and at each start (at_start).
A request to change is sent at the why; it is refused when the relief was acknowledged since its question was asked. A talk is over before anything is done in it, so it is done once. When a question may not have reached
the person there is no talk.

An absence is cancelled by a press alone, never by a typed line (it cannot be undone). Its why is kept in the talk and shown
(SURE_CANCEL) with two buttons, TALK_MINUTES from then; another line is another why, shown again. Yes, cancel it (its token is the
talk's `yes`, a new one for each why, so it cancels for the reason it is shown with) is judged as a press is, by absences.cancel at
that moment. Keep it, on that question and on the one before (its token is the talk's `key`), ends the talk. Pressed once the
talk is over, each is OLD_BUTTON. A backup (exams) is never cancelled here, the next sync with the exams would make it again: it has
no such button, and one on an older message is refused at each step (A_DUTY).

One press or line at a time (_pressing), so two at once save once. It is let go, as the absences lock is, before anything is said
to Telegram; what was saved is written down and followed up first, then the press is answered, then its message is changed. A
failure there changes nothing of what was done; one that comes before anything was done is answered WENT_WRONG."""
import collections, datetime, json, logging, math, re, secrets, threading, types

import store
from accounts import people as _accounts
from relief import absences as _absences
from relief import cover as _cover
from relief import fill as _fill
from relief import lessons as _lessons
from relief import links, outbox, tell, tg, tgdb
from relief import report as _report
from relief import settings as _settings
from relief import web as _web
from relief import words

HELLO = "Linked: {name}. You'll get your reliefs here. Send /relief to ask for relief, /stop to unlink."
NOT_READ = "I can't read messages here. To answer a relief, press a button under it. Send /relief to ask for relief."
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
WHY_CANCEL = "Cancel this absence? Say why in one line, or press Keep it."
SURE_CANCEL = "Cancel {days}? Your reason: {why}"
KEEP, YES = "Keep it", "Yes, cancel it"
LAST_ONE = "Answer the question I asked last."
SENT_CHANGE = "Sent to the relief team. Until they reply, this relief is still yours."
SENT_CANCEL = "Cancelled. The relief team will see it."
A_DUTY = "This is for an exam or event duty, so it cannot be cancelled here. Ask the exams committee, or the event's teacher in charge."
NOTHING = "Nothing was changed."
REMINDED = "Reminded {n}."
WENT_WRONG = "Something went wrong. Try again in the app."
COMMANDS = ("/start", "/stop", "/help", "/relief")        # these end a talk
TALK_MINUTES = 15
ASK = "ask"                                  # the kind of the talk, and of its buttons, that asks for relief (relief/asking.py)
WHY_MOST = 200                               # characters of a why (as relief.cover and relief.absences have it)
NO_REASON = frozenset("no n nope yes y ok okay thanks thank you cancel keep it stop".split())       # a line of these words alone gives none
ANSWER_MOST, TEXT_MOST = 200, 4096           # characters Telegram takes of an answer to a press, and of a message
TIMEOUT = 8                                  # seconds for each call made while Telegram waits for the hook's answer
_HANDLE = re.compile(r"[A-Za-z0-9_]{1,64}")
_WORD = re.compile(r"[^\W_]+")
_DATA = re.compile(r"b:([A-Za-z0-9_-]{16})")              # a button's callback data (relief/outbox.py)
STAYS = (_web.NO_PUB,)                       # a refusal that keeps any button: a publish may be swapping folders
ANY = object()                               # in ACTIONS, in place of a kind's refusals: every refusal keeps the button
_log = logging.getLogger("relief.telegram")
_counting = threading.Lock()
_pressing = threading.Lock()
_note = None
# what a press or a line comes to: what is answered (an alert: the person has to close it), the line its message gains, losing
# its buttons, the same of the message its talk began at (also: that message, the line), the talk opened (its question is to be
# asked), what follows (the history entry and the rest), called with nothing held, what is said before its question (first),
# what is done once all this is (then), and the buttons its message gains in place of those it had (rows: Telegram's inline
# keyboard, outbox.keep_buttons)
_Out = collections.namedtuple("_Out", "text alert line also talk after first then rows", defaults=(None, False, None, None, None, None, None, None, None))


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
        elif isinstance(u.get("edited_message"), dict): _edited(u["edited_message"])
        elif isinstance(u.get("callback_query"), dict): _press(u["callback_query"])
    except Exception as e:
        _log.warning("an update could not be handled (%s)", type(e).__name__)


def _noted(what, text, who):
    if _note is None: return
    try: _note(what, text, who=who, via=links.VIA)
    except Exception as e: _log.warning("a history entry could not be made (%s)", type(e).__name__)


def _private(m):
    """the chat's id when the message (or the press: its message's chat, and who pressed) is in a person's own chat with the bot and
    by that person, else None"""
    c, f = m.get("chat"), m.get("from")
    if not isinstance(c, dict) or c.get("type") != "private" or type(c.get("id")) is not int or not 0 < c["id"] < 2 ** 63: return None
    if not isinstance(f, dict) or f.get("is_bot") or f.get("id") != c["id"]: return None
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


def _asking():
    """relief/asking.py, which reads this module at import"""
    from relief import asking
    return asking


def _message(m):
    chat = _private(m)
    if chat is None: return
    text = m["text"] if isinstance(m.get("text"), str) else ""
    cmd, rest = _command(text.strip())
    talk = _talk(chat)
    if talk and cmd in COMMANDS: _leave(chat, talk, cmd)
    elif talk and _line(chat, talk, m, text, cmd): return
    if cmd == "/start" and links.shaped(rest): return _code(chat, m, rest)
    if cmd not in COMMANDS and links.shaped(text): return _code(chat, m, text)
    key = f"tg:{chat}"
    with _counting:
        if links.tries.blocked(key): return
        name = links.name_of(chat)
        was = links.unlink_chat(chat) if cmd == "/stop" else None
        if name is None: links.tries.fail(key)
    if was: _noted("telegram unlinked", "Telegram unlinked", was)
    if name is None: reply(chat, NOT_LINKED)
    elif was: reply(chat, STOPPED)
    elif cmd == "/relief": _asking().start(chat, name)
    elif not _asking().stray(chat, m): reply(chat, HELLO.format(name=name) if cmd in ("/start", "/help") else NOT_READ)


def _edited(m):
    """a message changed after it was sent: nothing is taken from it, and who is asking for relief is told so, unless it says what is
    held already (asking.line)"""
    chat = _private(m)
    talk = _talk(chat) if chat is not None else None
    if talk and talk["kind"] == ASK and not links.tries.blocked(f"tg:{chat}"):
        name = links.name_of(chat)
        if name is not None: _asking().line(chat, name, m, edit=True)


def _leave(chat, talk, cmd):
    """a command ends the talk; a request for relief that had got as far as a day is said not to be sent (/relief begins another)"""
    if talk["kind"] != ASK: _end(chat, talk)
    else: _asking().leave(chat, quiet=cmd == "/relief")


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
    if out.first: reply(chat, out.first)
    lost = out.talk is not None and not _ask(chat, out.talk)
    _answer(q, WENT_WRONG if lost else out.text, lost or out.alert)
    if lost: _end(chat, out.talk)                # what is typed next is not the answer to a question that may not have come
    if out.line: _settle(chat, message, out.line, out.rows)
    if out.also: _settle(chat, *out.also)
    if out.then: out.then()


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


def _says(text, sentence, b):
    """text is that sentence of the app: {name} the one button b shows, {why} whatever it is"""
    head, why, tail = sentence.replace("{name}", str(b["who"])).partition("{why}")
    return text.startswith(head) and text.endswith(tail) if why else text == head


def _acted(b, f):
    """what f does for button b comes to; refused by the app: its sentence, which the message gains too, unless the button is
    one to press again (STAYS, or a sentence its kind has in ACTIONS)"""
    try: return f()
    except ValueError as e:
        if type(e) is not ValueError: raise
        keeps = ACTIONS[b["what"]][2]
        stays = keeps is ANY or any(_says(str(e), x, b) for x in (*STAYS, *keeps))
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


def _settle(chat, message, line, rows=None):
    """the message a button was on: its text and line, with no buttons but rows (Telegram's inline keyboard) when given; when
    Telegram does not do it, nothing more"""
    n, text = message["id"], message["text"]
    if n is None: return
    keys = dict(reply_markup=dict(inline_keyboard=rows)) if rows else {}
    if text is None: tg.call("editMessageReplyMarkup", dict(chat_id=chat, message_id=n, **keys), timeout=TIMEOUT)       # too old for its text
    elif not text.endswith(line):                # it is there when it was pressed again
        tg.call("editMessageText", dict(chat_id=chat, message_id=n, text=f"{text[:TEXT_MOST - len(line) - 2]}\n\n{line}", disable_web_page_preview=True, **keys), timeout=TIMEOUT)


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


def _theirs(b, reached):
    """_cover_of, while it is the relief of the button's person and has reached them (reached: web._reached), else the page's answer"""
    got = _cover_of(b)
    _cover._mine(*got, b["name"], reached)
    return got


def _after(step, r, b, pub):
    return lambda: _web.step_saved(step, r, b["ckey"], b["name"], pub, by=(b["name"], links.VIA))


def _exams(pub):
    """what approved exams and events stop, as the page has it (what can be read of a date, whatever of it cannot)"""
    return _web._links_or_none(pub, _web._cal(pub))


def _ack(p):
    b, pub = p.button, _published()
    reached = _web._reached(pub)
    r, x, c = _theirs(b, reached)
    t = _talk(p.chat)                            # a request to change this very cover that waits for its why is over
    if t and t["kind"] == "change" and (t["d"].get("absent"), t["d"].get("ckey")) == (b["extra"].get("absent"), b["ckey"]): _end(p.chat, t)
    first = False
    if _cover.state(r, x, c) != "acknowledged": r, first = _cover.acknowledge_once(r["id"], b["ckey"], b["name"], links=_exams(pub), reached=reached)
    line = f"✅ Acknowledged {_hm(_cover.find(r, b['ckey'])[1]['ack']['at'])}."
    return _Out(line, line=line, after=_after("ack", r, b, pub) if first else None)


def _approve(p):
    """as the page's Approve; the message gains the button that sends it out (as the page's Send out: Approve tells nobody)"""
    b, pub = p.button, _published()
    r, x, c = _cover_of(b)
    settings = _settings.load(pub)
    r = _cover.approve(r["id"], b["ckey"], b["who"], b["name"], pub, settings, links=_web._links_or_none(pub, settings["calendar"]))
    x, c = _cover.find(r, b["ckey"])
    line = f"✅ Approved: {b['who']}, {_hm(c['approved']['at'])}."
    short = next((q.get("short") for q in _accounts.staff(pub) if q["name"] == b["who"]), None) or b["who"]
    rows = outbox.keep_buttons(b["name"], [[dict(text=f"📤 Send out to {short}", what="sendout", id=r["id"], ckey=b["ckey"], who=b["who"],
                                                 extra=dict(absent=r["teacher"], date=x["date"], approved_at=c["approved"]["at"]))]])
    return _Out(line, line=line, after=_after("approve", r, b, pub), rows=rows)


def _send_out(p):
    """as the page's Send out, for the approval the button was made with: at once in school hours, else when it will go"""
    b, pub = p.button, _published()
    r, x, c = _cover_of(b)
    settings = _settings.load(pub)
    r = _cover.send_out(r["id"], b["ckey"], b["who"], b["name"], pub, settings, links=_web._links_or_none(pub, settings["calendar"]),
                        approved_at=b["extra"].get("approved_at"))
    x, c = _cover.find(r, b["ckey"])
    at, goes = c["sent_out"]["at"], _cover.goes_at(c, x, settings, pub)
    line = f"📤 Sent out: {b['who']}, {_hm(at)}." + (f" Will be sent at {_hm(goes)}." if goes is not None and goes > _fill._when(at) else "")
    return _Out(line, line=line, after=_after("sendout", r, b, pub))


def _remind(p):
    """as the page's Remind, for the reliefs listed in the report the button is on; refused when nobody could be, with the first
    reason that says more than that"""
    b = p.button
    got = _report.remind(b["extra"].get("date"), b["extra"].get("covers"), (b["name"], links.VIA))
    if not got["sent"]: raise ValueError(next((v["why"] for v in got["skipped"] if v["why"] != _report.NOBODY), _report.NOBODY))
    return _Out(REMINDED.format(n=got["sent"]))


def _ask_change(p):
    """what the page would refuse whatever the why is refused at once; nothing is saved"""
    pub = _published()
    r, x, c = _theirs(p.button, _web._reached(pub))
    _absences._past(x)
    _cover._happens(_exams(pub), x)
    if _cover.state(r, x, c) == "change": raise ValueError(_cover.ASKED_ALREADY)
    return _asked(p, "change")


def _change(chat, b, why, talk):
    pub = _published()
    reached = _web._reached(pub)
    r, x, c = _theirs(b, reached)
    began = talk["until"] - TALK_MINUTES * 60    # when its question was first asked
    if c.get("ack") and _fill._when(c["ack"]["at"]).timestamp() > began: raise ValueError(_absences.ACKED)        # on the page, since
    r = _cover.ask_change(r["id"], b["ckey"], why, b["name"], links=_exams(pub), reached=reached)
    return _Out(SENT_CHANGE, line=f"↩ Asked to change {_hm(_cover.find(r, b['ckey'])[1]['change']['at'])}.", after=_after("change", r, b, pub))


def _may_cancel(b):
    """the absence of the button, while its person may cancel it: theirs, or the one they planned (never by the team's right), and no
    backup now"""
    _published()
    r = _absences._editable(b["id"])
    _absences._may_change(r, b["name"], False)
    if r.get("exams"): raise ValueError(A_DUTY)
    if tell._last(r) < _lessons.today().isoformat(): raise ValueError(_absences.PAST_ABSENCE)
    return r


def _ask_cancel(p):
    """as _ask_change"""
    _may_cancel(p.button)
    return _asked(p, "cancel")


def _sure(chat, b, why, talk):
    """the why is kept and shown, with the buttons that cancel and that do not; nothing is cancelled here"""
    r, yes = _may_cancel(b), secrets.token_urlsafe(12)
    return _open(chat, "cancel", dict(talk["d"], why=why, days=words.days(r), yes=yes, question=None), b, {talk["d"]["key"]: "keep", yes: "cancel-yes"})


def _mine(p, part):
    """the chat's talk, over now, when the button is its own (part of its data holds the token); else OLD_BUTTON"""
    t = _talk(p.chat)
    if t is None or t["d"].get(part) != p.button["token"] or not _end(p.chat, t): raise ValueError(OLD_BUTTON)
    return t


def _yes(p):
    """cancels the absence, for the reason the button is shown with"""
    b, pub, d = p.button, _published(), _mine(p, "yes")["d"]
    def cancel():
        _may_cancel(b)
        r = _absences.cancel(b["id"], d["why"], b["name"], team=False)
        return _Out(SENT_CANCEL, line=SENT_CANCEL, also=f"❌ Cancelled {_hm(r['cancelled']['at'])}.", after=_after("cancel", r, b, pub))
    out = _acted(b, cancel)                      # refused: both messages say why
    return out._replace(also=(d["message"], out.also or out.line))


def _keep(p):
    """ends the talk whose question the button is on; when that is over (answered, replaced, run out) nothing is said to be kept"""
    _mine(p, "key")
    return _Out(NOTHING, line=NOTHING)


# ---- talks
def _asked(p, kind):
    """a talk of that kind for the button pressed. key: its own, and the token of its Keep it button when it has one; question:
    the id of the message that asks, once asked"""
    b, key = p.button, secrets.token_urlsafe(12)
    d = dict(id=b["id"], ckey=b["ckey"], absent=b["extra"].get("absent"), token=b["token"], message=p.message, key=key, question=None)
    return _open(p.chat, kind, d, b, {key: "keep"} if kind == "cancel" else {})


def _open(chat, kind, d, b, buttons):
    """the talk open in the chat, in place of any other, TALK_MINUTES from now, its question to be asked (_ask). buttons: those of
    its question, {token: what}, for the person of button b alone and good as long"""
    until, old = _clock() + TALK_MINUTES * 60, _talk(chat)
    talk = dict(kind=kind, data=json.dumps(d), until=until, d=d)
    first, then = _asking().replaced(chat, old["d"]) if old and old["kind"] == ASK else (None, None)
    with tgdb.db() as c:
        c.executemany("INSERT OR REPLACE INTO buttons(token, name, what, id, until) VALUES (?, ?, ?, ?, ?)", [(t, b["name"], what, b["id"], until) for t, what in buttons.items()])
        c.execute("INSERT OR REPLACE INTO talks(chat, kind, data, until) VALUES (?, ?, ?, ?)", (chat, kind, talk["data"], until))
    return _Out(talk=talk, first=first, then=then)


def _question(talk):
    """(what the talk asks now, Telegram's inline buttons under it, or None: the line opened for the answer; it takes one of these)"""
    d = talk["d"]
    if talk["kind"] == "change": return WHY_CHANGE, None
    keep = dict(text=KEEP, callback_data="b:" + d["key"])
    if "yes" not in d: return WHY_CANCEL, [[keep]]
    return SURE_CANCEL.format(days=d["days"], why=d["why"]), [[dict(text=YES, callback_data="b:" + d["yes"]), keep]]


def _ask(chat, talk):
    """the talk's question asked (again): the one a line may reply to from now on -> whether it surely came"""
    question, buttons = _question(talk)
    r = reply(chat, question, buttons=buttons, ask=buttons is None)
    if not r["ok"]: return False
    n = r["result"].get("message_id") if isinstance(r["result"], dict) else None
    try:
        with tgdb.db() as c:
            if _still(c, chat, talk): c.execute("UPDATE talks SET data=? WHERE chat=?", (json.dumps(dict(talk["d"], question=n if type(n) is int else None)), chat))
    except Exception as e:                       # a reply to it is asked for once more, then: nothing is done
        _log.warning("a question could not be noted (%s)", type(e).__name__)
    return True


def _still(c, chat, talk):
    """the talk is the chat's now (its data holds a key of its own, and its why), whatever the id of its question was noted as
    meanwhile"""
    r = c.execute("SELECT data FROM talks WHERE chat=?", (chat,)).fetchone()
    return r is not None and (r["data"] == talk["data"] or _but_question(r["data"]) == _but_question(talk["data"]))


def _but_question(data):
    return {k: v for k, v in json.loads(data).items() if k != "question"}


def _end(chat, talk):
    """the chat's talk is over -> whether it was this one, and not over before"""
    with tgdb.db() as c:
        return _still(c, chat, talk) and c.execute("DELETE FROM talks WHERE chat=?", (chat,)).rowcount == 1


def forget():
    """the talks that have run out are deleted (every minute: tell.MINUTE)"""
    tgdb.forget_talks(_clock())


def at_start():
    """once, when the app starts, whatever is on: as forget; without a token nobody can go on with a talk, so every one is. A failure
    never stops the start"""
    try: tgdb.forget_talks(_clock() if tg.on() else math.inf)
    except Exception as e: _log.warning("the talks that have run out could not be deleted (%s)", type(e).__name__)


def _talk(chat):
    """the talk that waits for a line in the chat, dict(kind, data, until, d: data read), or None; one whose time is over, or that
    cannot be read, is deleted, one of another kind left alone"""
    with tgdb.db(read=True) as c: r = c.execute("SELECT kind, data, until FROM talks WHERE chat=?", (chat,)).fetchone()
    if r is None: return None
    over, d = r["until"] < _clock(), None
    if not over and r["kind"] not in KINDS: return None
    try: d = json.loads(r["data"])
    except ValueError: over = True
    if over or not isinstance(d, dict):
        _end(chat, r)
        return None
    return dict(r, d=d)


def _replies_to(m):
    """the id of the message a line replies to; None when to none, 0 when to one that is not in this chat or has no id"""
    to = m.get("reply_to_message")
    if to is None: return None if m.get("external_reply") is None else 0
    n = to.get("message_id") if isinstance(to, dict) else None
    return n if type(n) is int else 0


def _no_reason(why):
    """nothing in the line but words of NO_REASON, in any case, whatever is around them (or no word at all)"""
    return all(w in NO_REASON for w in _WORD.findall(why.casefold()))


def _line(chat, talk, m, text, cmd):
    """what was typed (or sent) while a talk waits -> whether it was for the talk (the rest is for _message)"""
    if links.tries.blocked(f"tg:{chat}"): return True                            # nothing at all
    name, to = links.name_of(chat), _replies_to(m)
    if name is None:
        _end(chat, talk)
        return False
    if talk["kind"] == ASK: return _asking().cancel(chat) if cmd == "/cancel" else _asking().line(chat, name, m)
    if cmd == "/cancel":
        if not _end(chat, talk): return False
        reply(chat, NOTHING)
        return True
    why = " ".join(text.split())                 # one line, as the page's box gives it
    other = to is not None and to != talk["d"].get("question")
    if other: reply(chat, LAST_ONE)
    if other or not 1 <= len(why) <= WHY_MOST or _no_reason(why):
        _ask(chat, talk)
        return True
    def do():
        if not _end(chat, talk): return None     # over meanwhile: this line is not its why
        b = _button(chat, talk["d"]["token"])
        return _acted(b, lambda: TALKS[talk["kind"]](chat, b, why, talk))
    out = _did(do)
    if out is None: return False
    _follow(out)
    if out.talk is not None:
        if not _ask(chat, out.talk):
            _end(chat, out.talk)
            reply(chat, WENT_WRONG)
        return True
    reply(chat, out.text)
    if out.line: _settle(chat, talk["d"]["message"], out.line)
    return True


def _asked_for(p):
    return _asking().step(p.chat, p.button["name"], press=p)


# what a button does, by its kind: (the right it needs, f(p) with p.chat, p.button (_button) and p.message (its id and text) ->
# _Out, the refusals that keep it: {name} is the one it shows, {why} is anything, ANY is every refusal)
ACTIONS = {"ack": ("relief", _ack, (_cover.NOT_HAPPENING,)), "change": ("relief", _ask_change, (_cover.NOT_HAPPENING,)),
           "cancel": ("relief", _ask_cancel, ()), "keep": ("relief", _keep, (OLD_BUTTON,)),
           "cancel-yes": ("relief", _yes, (OLD_BUTTON,)), "approve": ("relief.team", _approve, (_cover.PICK_CHANGED, _cover.NOT_FREE, _cover.NOT_HAPPENING)),
           "sendout": ("relief.team", _send_out, (_cover.PICK_CHANGED, _cover.NOT_FREE_OUT, _cover.NOT_HAPPENING)),
           "remind": ("relief.team", _remind, ANY), ASK: ("relief", _asked_for, ANY)}
# what the why typed in a talk comes to, by its kind: f(chat, the button, why, talk) -> _Out
TALKS = dict(change=_change, cancel=_sure)
KINDS = frozenset((*TALKS, ASK))               # the kinds of talk there are: what is typed in one that asks for relief is asking.line's

"""An update from Telegram in, an answer out. handle(update) never raises: a failure is logged to "relief.telegram" by its kind
alone (never a code, a chat id, a name or what was typed).

Only a message in a person's own (private) chat is read or answered; groups, channels, other bots and every other kind of
update are ignored. Anything shaped like a code (alone, or after /start, as Telegram's own link sends it) is tried as a link
code; when it is not a current one the message is deleted and answered BAD_CODE (BAD_CODE_KEPT when Telegram did not delete
it), the same for a real personal code and a made-up one (links.use never looks at those). The code a chat linked itself
with, sent by it again, is answered HELLO and changes nothing (links.again). A chat whose person is not there, or has no relief now
(links.name_of), is answered NOT_LINKED. Each of these two answers counts against links.tries, and a chat over it gets nothing at all: no
answer, no deleteMessage, its code not tried. The count is made with the check (_counting, never held during a call to
Telegram), so messages that come at once get no more.

/start, /help and anything else from a linked chat: HELLO. /stop unlinks. A person's link that moved is told in the old chat
(MOVED_LINK); a chat that was someone else's is told so before HELLO (TAKEN). Linking, moving and unlinking are each one
history entry by that person, via telegram (init's note), naming no chat, handle or code. A link just made asks relief.tell
for what is still to come for that person."""
import logging, re, threading

from relief import links, tell, tg

HELLO = "Linked: {name}. You'll get your reliefs here. Send /relief to ask for relief, /stop to unlink."
NOT_LINKED = "This Telegram is not linked. Open Relief in the school's app, press Link Telegram and follow the link there."
_BAD = "That code is not right or has run out. Get a new one in the app. If it was your personal code, do not send it here: it opens the app. "
BAD_CODE = _BAD + "I have deleted your message."
BAD_CODE_KEPT = _BAD + "Please delete your message now."
MOVED_LINK = "Your relief messages now go to another Telegram. If this was not you, tell the relief team."
TAKEN = "This Telegram was linked to someone else before. Their relief messages no longer come here."
STOPPED = "Unlinked. Your relief messages stop here. To link again, open Relief in the school's app and press Link Telegram."
TIMEOUT = 8                                  # seconds for each call made while Telegram waits for the hook's answer
_HANDLE = re.compile(r"[A-Za-z0-9_]{1,64}")
_log = logging.getLogger("relief.telegram")
_counting = threading.Lock()
_note = None


def init(note):
    """note(what, text, absence=None, who=None, via=None): one history entry (app.py's _relief_entry)"""
    global _note
    _note = note


def reply(chat, text, buttons=None):
    """one message to a chat; buttons: rows of Telegram's own inline buttons"""
    params = dict(chat_id=chat, text=text, disable_web_page_preview=True)
    if buttons: params["reply_markup"] = dict(inline_keyboard=buttons)
    return tg.call("sendMessage", params, timeout=TIMEOUT)


def handle(update):
    try:
        m = update.get("message") if isinstance(update, dict) else None
        if isinstance(m, dict): _message(m)
    except Exception as e:
        _log.warning("an update could not be handled (%s)", type(e).__name__)


def _noted(what, text, who):
    if _note is None: return
    try: _note(what, text, who=who, via=links.VIA)
    except Exception as e: _log.warning("a history entry could not be made (%s)", type(e).__name__)


def _private(m):
    """the chat's id when the message is in a person's own chat with the bot, else None"""
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

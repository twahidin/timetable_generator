"""Telegram's routes: the hook Telegram posts each update to, a person's own link, and connecting the bot (relief settings).
Registered from app.py after init(has=..., me=..., need=..., note=...), as relief/web.py is.

POST /telegram/hook is the app's one route without a session: Telegram has none. It answers 404 while there is no token, no bot
is connected, or the token or SECRET_KEY is not the one it was connected under (links.connected), 403 unless
X-Telegram-Bot-Api-Secret-Token is tg.hook_secret() (compared with hmac.compare_digest; "" never matches), before any of the
body is read, and 413 past LIMIT (read from the stream, never more than one byte past it). With the right secret each update
is acted on once (tgdb.first_time) by bot.handle and answered 200; a body that is not an update is answered 200 and nothing is
done, or Telegram would send it again; a store that fails is 503, so that it does.

A person's own link needs relief and a person signed in by name: GET /api/relief/telegram, POST …/code (a one-time code and
the address that opens the bot with it), DELETE …/link. Relief settings (relief.save): GET …/admin, POST …/connect (points
Telegram at the app's address, _base), …/disconnect and …/unlink {name}. The relief team (relief.team, asked as relief/web.py's
team routes ask it): POST /api/relief/today/remind and GET /api/relief/summary (one week's numbers; it needs no token). No answer
holds the token, the hook's secret, a chat id or anything Telegram said."""
import hmac, json, logging, os, re, sqlite3
from functools import wraps
from urllib.parse import urlsplit

from flask import Blueprint, abort, jsonify, request

import store
from accounts import people as _accounts
from accounts import rights as _rights
from relief import absences as _absences
from relief import bot, links, report, tg, tgdb
from relief import calendar as _calendar
from relief import outbox as _outbox
from relief import lessons as _lessons
from relief import settings as _settings
from relief import summary as _summary
from relief import web as _web

bp = Blueprint("relief_tg", __name__)
HOOK = "/telegram/hook"
LIMIT = 256 * 1024                          # bytes of one update
SIGN_IN = "Please sign in again."
NOT_CONNECTED = "Telegram is not connected yet."
NO_TOKEN = "Add the bot's token in Railway variables first (TELEGRAM_BOT_TOKEN)."
NO_KEY = "Set SECRET_KEY in Railway variables first: the bot needs it."
NOT_HTTPS = "Telegram needs a secure address: open the app at its https address and press Connect there."
NO_ANSWER = "Telegram did not answer, or did not accept the bot. Check TELEGRAM_BOT_TOKEN in Railway variables and try again."
NOT_NOW = "Telegram could not be reached just now. Try again."
HALF_OFF = "Disconnected here, but Telegram did not answer. The app reads and sends nothing now."
NO_LINK = "That person has no Telegram linked."
COMMANDS = [dict(command="relief", description="Ask for relief"), dict(command="stop", description="Unlink this Telegram"),
            dict(command="help", description="What this bot does")]
_USERNAME = re.compile(r"[A-Za-z0-9_]{1,64}")
_LABEL = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?")          # one part of a host name
_log = logging.getLogger("relief.telegram")
_has = _me = _need = _note = None
_GUARDS = set()        # every right list a route here names, checked by app.py's need() in init


def init(has, me, need, note=None):
    """as relief/web.py's init; note(what, text, absence=None, who=None, via=None) also records what people do on Telegram"""
    global _has, _me, _need, _note
    _has, _me, _need, _note = has, me, need, note
    for names in _GUARDS: need(*names)
    bot.init(note)


def need(*names):
    """the route needs one of these rights: app.py's need() decides on every request; the names stay on the route as _need,
    for the route map (tests/test_routes.py)"""
    _GUARDS.add(names)
    def deco(f):
        @wraps(f)
        def inner(*a, **k): return _need(*names)(f)(*a, **k)
        inner._need = names
        return inner
    return deco


def _noted(what, text):
    """one history entry by whoever is signed in; a failure to make it never fails the change"""
    if _note is None: return
    try: _note(what, text)
    except Exception as e: _log.warning("a history entry could not be made (%s)", type(e).__name__)


# ---- the hook
def _right_secret():
    want, got = tg.hook_secret(), request.headers.get("X-Telegram-Bot-Api-Secret-Token") or ""
    return want != "" and hmac.compare_digest(got.encode("utf-8", "replace"), want.encode())


def _raw():
    """the body, or None past LIMIT, whatever Content-Length says"""
    if (request.content_length or 0) > LIMIT: return None
    out = b""
    while len(out) <= LIMIT:
        more = request.stream.read(LIMIT + 1 - len(out))
        if not more: return out
        out += more
    return None


def _update(raw):
    """the update, a dict with its update_id (a number the store can keep), or None"""
    try: d = json.loads(raw)
    except (ValueError, RecursionError): return None
    i = d.get("update_id") if isinstance(d, dict) else None
    return d if type(i) is int and abs(i) < 2 ** 63 else None


@bp.post(HOOK)
def hook():
    if links.connected() is None: abort(404)
    if not _right_secret(): return "", 403
    raw = _raw()
    if raw is None: return "", 413
    u = _update(raw)
    if u is None: return "", 200
    try: new = tgdb.first_time(u["update_id"])
    except Exception as e:
        _log.warning("an update could not be recorded (%s)", type(e).__name__)
        return "", 503
    if new: bot.handle(u)
    return "", 200


# ---- a person's own link
def _mine():
    """-> (the person's name, None) or (None, the refusing answer)"""
    p = _me()
    if p is None or not _has("relief"): return None, ({"error": SIGN_IN}, 401)
    return p["name"], None


def _status(name):
    b, x = links.connected(), links.linked().get(name)
    return jsonify(on=tg.on(), connected=b is not None, bot=b["username"] if b else None, linked=x is not None,
                   handle=x["handle"] if x else None, since=x["at"] if x else None, blocked=None if x else links.blocked(name))


@bp.get("/api/relief/telegram")
@need("relief")
def status():
    name, err = _mine()
    return err or _status(name)


@bp.post("/api/relief/telegram/code")
@need("relief")
def code():
    """a one-time code for whoever is signed in, for themselves only, and the address that opens the bot with it: in practice mode
    the word practice, which is none (there is no bot, and a bot of that name may be anybody's): the page shows the code alone"""
    name, err = _mine()
    if err: return err
    b = links.connected()
    if b is None: return {"error": NOT_CONNECTED}, 409
    c = links.new_code(name)
    return jsonify(code=c["code"], url="practice" if tg.practice() else f"https://t.me/{b['username']}?start={c['code']}", until=c["until"])


@bp.delete("/api/relief/telegram/link")
@need("relief")
def unlink_mine():
    name, err = _mine()
    if err: return err
    if links.unlink(name) is not None: _noted("telegram unlinked", "Telegram unlinked")
    return _status(name)


# ---- the relief team
@bp.post("/api/relief/today/remind")
@need("relief")
def remind():
    """{date, covers: [{id, ckey}]}: the reliefs the page showed as not acknowledged, sent again (report.remind) -> dict(sent: how
    many, skipped=[{ckey, name, why}]); one history entry when any was. NOT_NOW (503) when the store fails: what was put in the queue
    by then goes, and pressing again does not send it twice; relief.team"""
    pub, me, err = _web._gate(*_web.TEAM)
    if err: return err
    b = _web._body()
    try:
        date, covers = _web._date_in(b.get("date")), [dict(id=v["id"], ckey=v["ckey"]) for v in report.asked(b.get("covers"))]
        if links.connected() is None: return {"error": NOT_CONNECTED}, 409
        got = report.remind(date, covers, None)
    except ValueError as e: return _web._refusal(e)
    except _web.BAD_INPUT as e:
        _log.warning("a reminder could not be read (%s)", type(e).__name__)
        return {"error": _absences.WRONG}, 400
    except sqlite3.OperationalError as e:
        _log.error("a reminder could not be queued (%s)", type(e).__name__)
        return {"error": NOT_NOW}, 503
    return jsonify(got)


@bp.get("/api/relief/summary")
@need("relief")
def summary():
    """one week's numbers (summary.week): the week of ?week=YYYY-MM-DD, any date of it, or this week when left out; WRONG for what is
    no date; relief.team"""
    pub, me, err = _web._gate(*_web.TEAM)
    if err: return err
    v = request.args.get("week")
    try: date = _web._date_in(v) if v else _lessons.today()
    except ValueError as e: return _web._refusal(e)
    settings = _settings.load(pub)
    return jsonify(_summary.week(pub, settings, _absences.all_records(), date, _absences._now(), links=_web._links_or_none(pub, settings["calendar"])))


# ---- relief settings
UNSENT = dict(planned="Relief planned", remind="Reminder to acknowledge", officer="To the reporting officer", ask="Request to change", askpick="New pick for a request to change",
              kept="Relief kept", cancelled="Absence cancelled", gone="No longer needed", moved="Relief moved", stopped="Not happening", again="On again", weekly="Weekly summary",
              new="New request for today")
UNSENT_LEFT_OUT = ("relief", "report", "clear")   # a relief message has its own line on the relief page; a report and a clear are not news to anyone
UNSENT_SHOWN = 20


def _unsent():
    """dict(failed, unsure, since: the Monday, more, items: [dict(what, name, at, state)]) of the messages (not reliefs) that could not be sent, or may not
    have been, since Monday: newest first, UNSENT_SHOWN of them; None when there is none. Reads kind, name, state and times only: never a text or a key"""
    since = _calendar.week_of(_lessons.today())[0].isoformat()
    with tgdb.db(read=True) as c: rows = c.execute("SELECT kind, name, state, at, sent_at FROM outbox WHERE state IN ('failed', 'unsure')").fetchall()
    got = [dict(what=UNSENT.get(r["kind"], "Message"), name=r["name"], at=_outbox._state(r)["at"], state=r["state"]) for r in rows if r["kind"] not in UNSENT_LEFT_OUT]
    got = sorted((x for x in got if (x["at"] or "")[:10] >= since), key=lambda x: x["name"])
    got.sort(key=lambda x: x["at"], reverse=True)
    if not got: return None
    return dict(failed=sum(x["state"] == "failed" for x in got), unsure=sum(x["state"] == "unsure" for x in got), since=since, more=max(0, len(got) - UNSENT_SHOWN), items=got[:UNSENT_SHOWN])


def _admin():
    """people: how many hold relief; not_linked: which of them have no Telegram; linked: every link, so any can be taken away; unsent: _unsent()"""
    b, got = links.connected(), links.linked()
    able = sorted(p["name"] for p in _accounts.staff(store.published()) if "relief" in _rights.rights(p, links.VIA))
    return jsonify(token_set=tg.on(), practice=tg.practice(), connected=b is not None, bot=b["username"] if b else None, base=b.get("base") if b else None,
                   at=b.get("at") if b else None, linked=[dict(name=n, handle=got[n]["handle"], at=got[n]["at"]) for n in sorted(got)],
                   not_linked=[n for n in able if n not in got], people=len(able), unsent=_unsent())


@bp.get("/api/relief/telegram/admin")
@need("relief.save")
def admin(): return _admin()


def _host_name(host, least=2):
    """host is a plain host name of at least that many parts (example.org: two)"""
    labels = host.split(".")
    return len(host) <= 253 and len(labels) >= least and all(_LABEL.fullmatch(x) for x in labels)


def _base():
    """the address Telegram is pointed at: Railway's own name for the app (RAILWAY_PUBLIC_DOMAIN) when it is set and is a host
    name, so no header a browser sends can aim the hook and its secret elsewhere; else the address Connect was pressed on, when
    it is https:// and a host name, with or without a port, and nothing more (in practice http and a local name will do: nothing
    is sent anywhere); else None"""
    host = (os.environ.get("RAILWAY_PUBLIC_DOMAIN") or "").strip()
    if _host_name(host): return "https://" + host
    local = tg.practice()
    try:
        url = request.host_url                                           # reading it raises for some headers
        u = urlsplit(url)
        name, port = u.hostname or "", u.port
    except ValueError: return None
    if not (u.scheme == "https" or local) or not _host_name(name, 1 if local else 2): return None
    base = f"{u.scheme}://{name}" + (f":{port}" if port else "")
    return base if url.lower() in (base, base + "/") else None         # anything else in it (a path, a query, a user) is refused


@bp.post("/api/relief/telegram/connect")
@need("relief.save")
def connect():
    """Telegram sends this bot's updates to the app's address from now; what was waiting there is dropped. Pressed again for
    the bot connected already (the same name, token and SECRET_KEY), it stays connected since it first was: what was done
    since is still told (relief.tell)"""
    base = _base()
    if not tg.on(): return {"error": NO_TOKEN}, 409
    if not tg.hook_secret(): return {"error": NO_KEY}, 409
    if base is None: return {"error": NOT_HTTPS}, 409
    r = tg.call("getMe", timeout=8)
    username = r["result"].get("username") if r["ok"] and isinstance(r["result"], dict) else None
    if not isinstance(username, str) or not _USERNAME.fullmatch(username): return {"error": NO_ANSWER}, 502
    r = tg.call("setWebhook", dict(url=base + HOOK, secret_token=tg.hook_secret(), allowed_updates=["message", "edited_message", "callback_query"],
                                   max_connections=4, drop_pending_updates=True))
    if not r["ok"]: return {"error": NO_ANSWER}, 502
    was, key = tgdb.get_state("bot"), links.key()
    same = isinstance(was, dict) and (was.get("username"), was.get("key")) == (username, key)
    tgdb.set_state("bot", dict(username=username, base=base, at=(was.get("at") if same else None) or _absences._now(), key=key))
    tg.call("setMyCommands", dict(commands=COMMANDS), timeout=8)          # the menu only: its failure does not matter
    _noted("telegram connected", f"Telegram connected (@{username})")
    return _admin()


@bp.post("/api/relief/telegram/disconnect")
@need("relief.save")
def disconnect():
    """off here at once (the hook is 404 from now), then Telegram is told"""
    with tgdb.db() as c: was = c.execute("DELETE FROM state WHERE k='bot'").rowcount
    if was: _noted("telegram disconnected", "Telegram disconnected")
    if tg.on() and not tg.call("deleteWebhook", timeout=8)["ok"]: return {"error": HALF_OFF}, 502
    return _admin()


@bp.post("/api/relief/telegram/unlink")
@need("relief.save")
def unlink():
    """{name}: anybody's link taken away"""
    try:
        d = request.get_json(force=True, silent=True)
        name = d.get("name") if isinstance(d, dict) else None
        if not isinstance(name, str) or links.unlink(name) is None: return {"error": NO_LINK}, 404
    except (UnicodeEncodeError, RecursionError): return {"error": NO_LINK}, 404      # a name the store cannot hold, or JSON too deep to read
    _noted("telegram unlinked", f"Telegram unlinked for {name}")
    return _admin()

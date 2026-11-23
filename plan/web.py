"""Plan with AI on the server: the page and its JSON routes. Registered from app.py after init(need=..., env=..., owner=...);
nothing here imports app (decision P5) and no rule of the chat is here: those are plan/talk.py's and plan/steps.py's.

Every route needs the exams rights (app.py's need("exams", "committee"), as the exam pages), and the person's rights are
checked again at every step of a talk by the Env's may(). Without an AI on the server (ai.enabled() false) every /api/plan
route answers 404 OFF; GET /plan still gives the page, which says so.

Answers: a refusal is 400 {"error": sentence}; a talk that is unknown, closed or someone else's 410 {"error": talk.LOST}; a
body that is not a JSON object, or a wrong type in it, 400 WRONG; a fault 500 FAULT, logged as its type and frames only.
Nothing here logs or keeps what was typed. A talk's owner is app.py's: never the person's name."""
import io
import logging
import traceback
from functools import wraps

from flask import Blueprint, current_app, jsonify, request
from werkzeug.exceptions import HTTPException
from werkzeug.formparser import parse_form_data

from exams import approval as _approval
from plan import ai as _ai
from plan import facts as _facts
from plan import listread as _listread
from plan import steps as _steps
from plan import talk as _talk
from plan.steps import Refused

bp = Blueprint("plan_web", __name__)
log = logging.getLogger("plan")

CALL = None                     # an answer's AI call(messages, stop, deadline), given to talk.say: None in production; tests put a stand-in
READ = None                     # the list reader's call(text, facts), given to talk.paste: None in production; tests put a stand-in
OFF = "Plan with AI is not set up on this server."
WRONG = "Check what was sent and try again."
FAULT = "The app could not do that. Try again."
SIGN_IN = "Please sign in again."
GUARD = ("exams", "committee")
MOST_BODY = _listread.MOST_BYTES + 64 * 1024     # a list's body, file and form together

_need = _env = _owner = None


def init(need, env, owner):
    """need(*rights): app.py's route guard; env() -> the Env of this request (app.py's AppEnv of a snapshot of who is asking,
    which never reads the request again); owner(create) -> the owner of this session's talks ("p:..." or "s:..."; create:
    the shared code's session is given its own id when it has none), or None"""
    global _need, _env, _owner
    _need, _env, _owner = need, env, owner
    need(*GUARD)                                    # a wrong right name stops the app at start


def guarded(f):
    """the route needs the exams rights: app.py's need() decides on every request; the names stay on the route as _need,
    for the route map (tests/test_routes.py). The guarded function is made once, at the first request after init"""
    made = []

    @wraps(f)
    def inner(*a, **k):
        if not made:
            made.append(_need(*GUARD)(f))
        return made[0](*a, **k)
    inner._need = GUARD
    return inner


def api(f):
    """an /api/plan route: guarded, and 404 OFF without an AI on the server"""
    @wraps(f)
    def inner(*a, **k):
        if not _ai.enabled():
            return {"error": OFF}, 404
        return f(*a, **k)
    return guarded(inner)


class _Lost(Exception):
    """the talk is not there for this session"""


class _Wrong(Exception):
    """the body is not what the route takes"""


@bp.errorhandler(Refused)
def _refused(e): return {"error": str(e)}, 400


@bp.errorhandler(_Lost)
def _lost(e): return {"error": _talk.LOST}, 410


@bp.errorhandler(_Wrong)
def _wrong(e): return {"error": WRONG}, 400


@bp.errorhandler(Exception)
def _fault(e):
    """a fault: its type and frames in the log, never its text (it could hold what was typed)"""
    if isinstance(e, HTTPException):
        return e
    frames = "; ".join(f"{f.filename.rsplit('/', 1)[-1]}:{f.lineno} {f.name}" for f in traceback.extract_tb(e.__traceback__))
    log.error("plan.web fault %s at %s", type(e).__name__, frames)
    return {"error": FAULT}, 500


# ---------------------------------------------------------------- reading what was sent
def _body() -> dict:
    d = request.get_json(force=True, silent=True)
    if not isinstance(d, dict):
        raise _Wrong()
    return d


def _str(d, key, none_ok=False):
    v = d.get(key)
    if v is None and none_ok:
        return None
    if not isinstance(v, str):
        raise _Wrong()
    return v


def _count(v) -> int:
    """a line number as the page sends it: a whole number of at least 0 (or its digits); anything else counts as 0"""
    if isinstance(v, int) and not isinstance(v, bool):
        return max(v, 0)
    return int(v) if isinstance(v, str) and v.isascii() and v.isdigit() else 0


def _after(d=None) -> int:
    """the n after which the page wants the lines: the body's `after` when it has one, else ?after=; a negative or a
    non-number counts as 0"""
    if d is not None and d.get("after") is not None:
        return _count(d.get("after"))
    return _count(request.args.get("after", ""))


def _mine(id):
    """(the talk, the Env) of this session's talk id, or _Lost"""
    owner = _owner(False)
    t = _talk.get(id, owner) if owner else None
    if t is None:
        raise _Lost()
    return t, _env()


def _view(t, env, after=0):
    return jsonify(_talk.view(t, env, after))


# ---------------------------------------------------------------- the routes
@bp.get("/plan")
@guarded
def page():
    return current_app.send_static_file("plan.html")


@bp.get("/api/plan/start")
@api
def start():
    """what the page shows before a talk: what is missing, and the exams and common tests the chat may change now, newest first"""
    env = _env()
    pub, today = env.pub(), env.today()
    rows = [s for s in env.all_saved() if isinstance(s, dict) and s.get("kind") in ("exam", "test") and isinstance(s.get("id"), str)
            and _steps.editable(s, today) == ""]
    rows.sort(key=lambda s: s.get("saved_at") or s.get("created_at") or "", reverse=True)
    return jsonify(enabled=True, missing=_facts.missing(pub, env.cal(), env.settings()),
                   exams=[dict(id=s["id"], name=s.get("name"), status=_approval.label(s, today)) for s in rows])


@bp.post("/api/plan/talks")
@api
def talks():
    """{exam?} -> a new talk (on that exam when given): {id, view}"""
    exam = _str(_body(), "exam", none_ok=True)
    owner = _owner(True)
    if not owner:
        return {"error": SIGN_IN}, 401
    env = _env()
    t = _talk.open(owner, env, exam)
    return jsonify(id=t.id, view=_talk.view(t, env, 0))


@bp.get("/api/plan/talks/<id>")
@api
def talk(id):
    t, env = _mine(id)
    return _view(t, env, _after())


@bp.post("/api/plan/talks/<id>/say")
@api
def say(id):
    """{text, pick?, after?}: the answer starts and the view after `after` comes back at once"""
    t, env = _mine(id)
    d = _body()
    pick = _str(d, "pick", none_ok=True)
    text = _str(d, "text", none_ok=pick is not None)
    after = _after(d)
    _talk.say(t, env, text, pick=pick, call=CALL)
    return _view(t, env, after)


def _in_memory(*a, **k):
    """the form parser's place for a file part: memory, never Werkzeug's temp file (which goes to disk over 500 KB)"""
    return io.BytesIO()


@bp.post("/api/plan/talks/<id>/list")
@api
def paste(id):
    """{text, after?} or a multipart `file`: a list of papers. Refused from its length before it is read when too big or not
    given (a chunked body); a form is parsed in memory only, so nothing of the file is ever put on the server's disk"""
    t, env = _mine(id)
    if request.content_length is None or request.content_length > MOST_BODY:
        return {"error": _listread.BAD_FILE}, 400
    if request.mimetype == "multipart/form-data":
        _, _form, files = parse_form_data(request.environ, stream_factory=_in_memory, max_content_length=MOST_BODY)
        f = files.get("file")
        if f is None:
            raise _Wrong()
        data = f.read(_listread.MOST_BYTES + 1)
        if len(data) > _listread.MOST_BYTES:
            return {"error": _listread.BAD_FILE}, 400
        text, filename, after = None, f.filename or "", _after()
    else:
        d = _body()
        text, filename, data, after = _str(d, "text"), None, None, _after(d)
    _talk.paste(t, env, text=text, filename=filename, data=data, call=READ)
    return _view(t, env, after)


@bp.post("/api/plan/talks/<id>/list/<lid>")
@api
def confirm(id, lid):
    """{yes, after?}: the list read is put in (yes) or not"""
    t, env = _mine(id)
    d = _body()
    yes, after = d.get("yes"), _after(d)
    if not isinstance(yes, bool):
        raise _Wrong()
    _talk.confirm_list(t, env, lid, yes)
    return _view(t, env, after)


@bp.post("/api/plan/talks/<id>/undo")
@api
def undo(id):
    """{step, after?}: that step of the talk is taken back"""
    t, env = _mine(id)
    d = _body()
    step, after = _str(d, "step"), _after(d)
    _talk.undo(t, env, step)
    return _view(t, env, after)


@bp.post("/api/plan/talks/<id>/stop")
@api
def stop(id):
    t, env = _mine(id)
    _talk.stop(t)
    return _view(t, env, _after())


@bp.delete("/api/plan/talks/<id>")
@api
def close(id):
    t, _ = _mine(id)
    _talk.close(t)
    return jsonify(ok=True)


def signed_out(owners):
    """the talks of these owners are gone (the session signed out)"""
    for o in owners:
        if o:
            _talk.drop_owner(o)


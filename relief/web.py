"""The relief request routes (stage 2): a teacher asks for relief and sets work for each lesson; management and the
relief team plan relief for a colleague and choose relief teachers; the absent teacher acknowledges, sets work or
cancels; the relief team sees All Relief Requests. Registered from app.py after init(has=..., me=..., need=...).

Every route answers 401 {"error": "Please sign in again."} without a person signed in by name who has the relief right
(app.py's need("relief"), as every other route of the app), 409 with NO_PUB when nothing is published, 403 {"error":
sentence} without the narrower right (relief.plan, relief.team) and 400 {"error": sentence} on a refusal.
The absence reason reaches only the absent teacher, whoever planned it, relief.plan and relief.team: every route that
answers a record or one of its files asks _record first, and the lists are the caller's own, the caller's planned ones,
or (relief.team) everything. The remarks are for the relief team: a record sent to someone who is only its absent
teacher (not its sender, not relief.plan, not relief.team) leaves them out (_out).

Rights come from the accounts (accounts/rights.py): every permission question here goes through has(right), app.py's
`has`, passed in with init(has=..., me=..., need=...). Any teacher, school leader, HOD/SH or committee member signed in
by name has relief (an executive only with the Relief team extra); school leaders, HODs and SHs have relief.plan; the
Relief team extra gives relief, relief.plan and relief.team. The relief team's right to change any
absence (not needed, needed again, cancel) is asked here too, has("relief.team"), and passed into relief.absences as
team=...; relief.absences never reads who is on the team itself.

Bodies: POST /api/relief/absences takes relief.absences.new's fields (teacher: yourself when left out; dates, periods,
reason, reason_text, remarks, reporting_officer, lessons=[{key, needed, relief, work}]); PUT …/work takes the work
{text, link, files: [{id, name}], known: [the file ids the page started from]} (a missing or other body is refused,
never read as "no work"); POST …/not-needed and …/cancel take {why}; PUT …/relief takes {relief: a name, or
null to take the choice off}; POST …/files takes one file in the multipart field "file"; POST /api/relief/absences/seen
takes {at}: the as_of the All Relief Requests list answered (now when left out). Periods are 0-based, as in the records.

Stage 3 (relief/cover.py, pick.py, fill.py). A cover is a lesson, or one part of a split lesson, by its cover key (the
lesson's key, or key#i for part i); every list of covers is sent in time order (by p). The relief team (relief.team,
asked inside with TEAM_ONLY before the absence is opened): Today's Relief Assignments (GET /today?date=), Approve (POST …/covers/<ckey>/approve
{who: the pick the page showed}), Approve all waiting (POST /today/approve-all {date, covers: [{id, ckey, who}], the
waiting rows the page showed}), each refused or skipped with cover.PICK_CHANGED once that pick is no longer who; Send out
(POST …/covers/<ckey>/send-out {who, approved_at: the relief and the approval the page showed}) and Send out all approved
(POST /today/send-out {date, covers: [{id, ckey, who, approved_at}]}), which release an approved relief to its teacher
(cover.send_out: at once in school hours, else held until the earliest send-out time of a school day); Change
(GET …/covers/<ckey>/free, then PUT …/covers/<ckey>/relief {relief}: chosen and approved in one), Split (POST
…/lessons/<key>/split {at}: the first period of the second part) and Join again (POST …/lessons/<key>/join), Keep (POST
…/covers/<ckey>/keep), Fill now (POST /today/fill {date}), the load tracker (GET /load, /load/<name>, /load.csv, each
?week=YYYY-MM-DD or ?term=<name>). The relief teacher (relief, and the cover approved to them, else NOT_YOURS_COVER):
Reliefs I'm covering (GET /covering), Acknowledge (POST …/covers/<ckey>/acknowledge), Request to change (POST
…/covers/<ckey>/ask-change {why}); they also open the files of a lesson they relieve. Each of these is theirs only once the relief has
reached them (cover.reached: the team approved it and sent it out, and its time has come; _reached). Nothing reaches a relief teacher
before the team approves it and sends it out, and nothing they are sent carries the absence's reason, remarks, reporting officer, a pick's
reason or a cover's history. Picks are made by relief.fill in the background; a new absence, needed again and cancel ask
for a run (automatic: only with RELIEF_JOBS on), Fill now and a request to change (for its own absence alone) ask with
force, always after the save and the absences lock. Each save here is one history entry; the background picks write none.

Stage 4: each save, after its history entry, asks relief.tell (_tell_soon) what there is to say on Telegram; nothing is sent
from a route, and a message that cannot be worked out never fails the save. What a person may also do on Telegram
(relief/bot.py) has its history entry's words and what follows the save in STEPS, the same for both; so has an absence asked for there
(relief/asking.py) in created. via ("telegram") in a record: it was asked for there (All Relief Requests alone shows it)."""
import csv, datetime, io, os, threading
from functools import wraps
from zoneinfo import ZoneInfo

from flask import Blueprint, Response, current_app, g as _g, jsonify, request, send_file

import store
from accounts import people as _accounts
from exams.days import bounds, hhmm
from relief import absences as _absences
from relief import calendar as _calendar
from relief import cover as _cover
from relief import files as _files
from relief import fill as _fill
from relief import free as _free
from relief import hours as _hours
from relief import lessons as _lessons
from relief import links as _chats
from relief import settings as _settings
from relief import tell as _tell
from relief import tg as _tg
from relief import words as _words
from relief.calendar import term_of, week_of
from relief.codes import _cell

bp = Blueprint("relief_web", __name__)
NO_PUB = "Publish the timetable first: relief reads the teachers from it."
SIGN_IN = "Please sign in again."
PLAN_ONLY = "Only management and the relief team plan relief for a colleague."
CHOOSE_ONLY = "Only management and the relief team choose relief teachers."
TEAM_ONLY = "Only the relief team can open this."
NOT_YOURS = "This absence is not yours to open."
GONE = "That absence is not there any more."
NO_FILE = "That file is not there any more."
PERIODS = "Choose the periods again."
DATES = "Choose the dates again."
TERM = "Choose the term again."
STALE = _cover.NOT_FREE_OUT
OVER_ONLY = "Only teachers over a limit are free then: choose one yourself."   # the app's run leaves such a cover open
ENTIRE = _words.ENTIRE
COLUMNS = ["Date", "Absent", "Class / group", "Periods", "Time", "Relief teacher", "Remarks", "Set by"]
NOT_CHOSEN = "Not chosen yet"                          # the planned relief sheet's Relief teacher for an open cover
NOT_ON = "Not happening: {why}"                         # ... for a lesson an approved exam or event stops
WAITING_TEAM = "Waiting for the relief team"           # ... for a pick not approved yet: a name only once approved
LOAD_COLUMNS = ["Name", "Departments", "Flexi Adjunct", "Teaching this week", "Relief this week", "Exams and events this week", "Week so far",
                "Relief this term",
                "Requests to change this term"]
TEAM = ("relief.team", TEAM_ONLY)                      # the gate of the relief team's routes
APPROVED = _cover.APPROVED                             # the states in which a relief is approved to its teacher (reached once sent out and its time has come)
SEEN = os.path.join(store.DATA, "relief", "seen.json")
_SEEN_LOCK = threading.Lock()
BAD_INPUT = (TypeError, KeyError, AttributeError)     # malformed JSON never gives a 500
SLACK = 64 * 1024                                      # room for the multipart lines around one file

_class_group, _periods_text, _times, _nudge = _words.class_group, _words.periods_text, _words.times, _fill.nudge   # where they are now

_has = _me = _need = _note = None
_GUARDS = set()        # every right list a route here names, checked by app.py's need() in init


def init(has, me, need, note=None):
    """has(right) -> bool: the accounts' rights of whoever is signed in; me() -> the person signed in by name (a dict with
    name; app.py's who(), which ends the session of someone no longer on the published timetable) or None; need(*rights):
    app.py's route guard, which every route here goes through (a wrong right name stops the app at start, as there);
    note(what, text, absence id, who=None, via=None): one history entry for a relief save (app.py's _relief_entry: by the
    person who did it on Telegram when given, else by whoever is signed in)"""
    global _has, _me, _need, _note
    _has, _me, _need, _note = has, me, need, note
    for names in _GUARDS: need(*names)


def need(*names):
    """the route needs one of these rights: app.py's need() decides on every request (passed in with init); the names
    stay on the route as _need, for the route map (tests/test_routes.py)"""
    _GUARDS.add(names)
    def deco(f):
        @wraps(f)
        def inner(*a, **k): return _need(*names)(f)(*a, **k)
        inner._need = names
        return inner
    return deco


# ---- helpers
def _gate(right="relief", refused=None):
    """-> (pub, the person's name, None) or (None, None, the refusing answer)"""
    p = _me()
    if p is None or not _has("relief"): return None, None, ({"error": SIGN_IN}, 401)
    pub = store.published()
    if not pub: return None, None, ({"error": NO_PUB}, 409)
    if right != "relief" and not _has(right): return None, None, ({"error": refused}, 403)
    return pub, p["name"], None


def _sees_all():
    return _has("relief.plan") or _has("relief.team")


def _record(id, name):
    """-> (the record, None) when name may open it (the absent teacher, its planner, relief.plan, relief.team), else (None,
    the answer); someone who may not open every absence cannot tell a missing one from another teacher's"""
    r = _absences.load(id)
    if r is not None and (name in (r.get("teacher"), r.get("by")) or _sees_all()): return r, None
    if r is None and _sees_all(): return None, ({"error": GONE}, 404)
    return None, ({"error": NOT_YOURS}, 403)


def _body():
    d = request.get_json(force=True, silent=True)
    return d if isinstance(d, dict) else {}


def _cal(pub):
    return _settings.load(pub)["calendar"]


def _links(pub, cal):
    """what approved exams and events mean for relief (exams.relief_links), imported here to keep the modules apart; one per
    request (relief's routes never change a schedule)"""
    from exams.relief_links import Links
    got = _g.get("relief_links")
    if got is None or got.pub is not pub:
        got = _g.relief_links = Links.load(pub, cal)
    return got


def _links_or_none(pub, cal):
    """_links, or None, with the error logged once a request, when the exams and events cannot be read: relief works as if
    there were none"""
    if _g.get("relief_links_failed"): return None
    try: return _links(pub, cal)
    except Exception:
        _g.relief_links_failed = True
        current_app.logger.exception("relief: the exams and events could not be read")
        return None


def _reached(pub):
    """cover.reached for this request, as a callable (record, lesson, cover) -> bool: the settings read once, now at each call. A
    cover whose sending out cannot be worked out (a record changed by hand) has not reached its teacher, logged by its kind"""
    settings = _settings.load(pub)
    def reached(r, x, c):
        try: return _cover.reached(r, x, c, _absences._now(), settings, pub)
        except Exception as e:
            current_app.logger.error("relief: whether a relief has reached its teacher could not be worked out (%s)", type(e).__name__)
            return False
    return reached


def _sync_exams(pub):
    """after an absence is sent or cancelled: relief's backups in step with the approved exams and events
    (exams.relief_links.sync_all), so a lesson a cancelled own absence gives back goes to a backup again at once. Called once
    relief's own call has returned (its lock is released), inside the exams lock, imported here to keep the modules apart;
    it never fails the answer (an error is logged and the next sync puts it right)"""
    try:
        from exams import schedules
        from exams.relief_links import sync_all
        with schedules.editing():
            sync_all(pub, _cal(pub), _lessons.today())
    except Exception:
        current_app.logger.exception("relief: exams sync failed")


def _out(r, pub, me, cal=None, links=None):
    """the record as it is sent: lessons marked changed (matches_now) and stopped (why an approved exam or event stops the
    lesson, past or to come, else "", and "" in a cancelled record; links: one per request, built here when None), each with
    its covers ([{ckey, p, n, start, end, state, relief, planned}], by p: the lesson itself, or its parts); the remarks left
    out for someone who is only its absent teacher, and gone (the lessons that left a backup, with their picks and reasons)
    for everyone. The absent teacher who may not open every absence (not relief.plan, not
    relief.team) sees a relief teacher's name only once that teacher has acknowledged it (relief and relief_by None before), and no pick,
    request to change or history, on the lesson and on each part (Decision 4). Everyone else sees the relief as it is, and
    planned: the planner's own choice, waiting for the relief team or still their own approved choice (_planned, None
    otherwise), and may_choose: whether me may choose again for the lesson on the Plan page (absences.may_choose_again)."""
    cal = cal if cal is not None else _cal(pub)
    v = _absences.matches_now(r, pub, cal)
    v.pop("gone", None)
    live = not v.get("cancelled") and bool(v["lessons"])
    try:
        if live and links is None: links = _links(pub, cal)
        v["lessons"] = [dict(x, stopped=links.stopped(x) if live else "") for x in v["lessons"]]
    except Exception:          # the exams side never stops relief's own pages
        current_app.logger.exception("relief: the exams and events could not be read")
        v["lessons"] = [dict(x, stopped="") for x in v["lessons"]]
    if me == r.get("teacher") and me != r.get("by") and not _sees_all(): v.pop("remarks", None)
    hide = me == r.get("teacher") and not _sees_all()
    v["lessons"] = [_lesson_out(r, x, pub, hide, me) for x in v["lessons"]]
    return v


def _planned(r, c, s):
    """the planner's own choice for cover c: while it waits for the relief team (one from before a head's choice was approved
    at once), or while it is still the planner's own approved choice (cover.planned_by); else None"""
    if s in APPROVED: return c["relief"] if r.get("how") == "planned" and _cover.planned_by(c) else None
    p = _cover.pick_of(r, c) if s == "waiting" else None
    return c["relief"] if p and p.get("by") == "planner" else None


def _hidden(c, s):
    """cover (or lesson) c as the absent teacher alone sees it: no pick, request to change or history; the relief once its teacher
    has acknowledged it"""
    out = {k: v for k, v in c.items() if k not in ("pick", "change", "history")}
    if s != "acknowledged" and "relief" in out: out.update(relief=None, relief_by=None)
    return out


def _lesson_out(r, x, pub, hide, me=None):
    covers = []
    for i, c in enumerate(_cover.covers(x)):
        s = _cover.state(r, x, c)
        start, end = _times(pub, x, c)
        v = dict(ckey=_cover.cover_key(x, i), p=int(c["p"]), n=int(c.get("n") or 1), start=start, end=end, state=s,
                 relief=c.get("relief") if s == "acknowledged" or not hide else None)
        if not hide: v["planned"] = _planned(r, c, s)
        covers.append(v)
    covers.sort(key=lambda v: v["p"])
    # a split lesson's parts are sent in time order, each with its own ckey (cover.split puts the newest part last, so
    # outside cover.py parts[i] is never read as key#i)
    parts = sorted(({**(_hidden(c, _cover.state(r, x, c)) if hide else c), "ckey": _cover.cover_key(x, i)} for i, c in enumerate(x.get("parts") or [])),
                   key=lambda c: int(c["p"]))
    if not hide:
        out = dict(x, covers=covers, may_choose=_absences.may_choose_again(r, x, me, pub))
        if parts: out["parts"] = parts
        else: out["planned"] = covers[0]["planned"]
        return out
    out = dict(_hidden(x, _cover.state(r, x, x) if not x.get("parts") else "open"), covers=covers)
    if parts: out["parts"] = parts
    return out


def _views(records, pub, me):
    cal = _cal(pub)
    return [_out(r, pub, me, cal) for r in records]          # _links keeps one Links for the request


def _staff(pub):
    """everyone relief knows: the published timetable's teachers and the staff added in the accounts (no account field)"""
    return _accounts.listing(pub)


def _on_staff(pub, name):
    """raises the sentence new() says when name is not someone relief knows"""
    if not isinstance(name, str) or name not in {p["name"] for p in _staff(pub)}:
        raise ValueError(f"{name if isinstance(name, str) and name else 'That person'} is not on the published timetable or the staff list.")


def _noted(what, r, words, by=None):
    """the history entry for a save (the accounts design: one per relief save, naming who, what and which absence, with a
    link; never the reason, nor a why typed with it): 'Relief for <teacher> on <dates>: <words>' (words: a string, or
    a function giving it; r None: the words alone, for what is of no one absence). by: (the person's name, "telegram") when
    they did it on Telegram, else whoever is signed in"""
    if _note is None: return
    try:
        text, id = words() if callable(words) else words, None
        if r is not None: text, id = f"Relief for {r.get('teacher')} on {_words.days(r)}: {text}", r.get("id")
        if by is None: _note(what, text, id)
        else: _note(what, text, id, who=by[0], via=by[1])
    except Exception:          # the save has happened: a history entry that cannot be made never fails it
        current_app.logger.exception("relief: the history entry for %s could not be made", what)


def _lesson_words(r, key):
    """'1B, 1A Maths (G1) on Tue 13 Oct': the lesson a history entry is about"""
    x = next((x for x in r.get("lessons") or [] if x.get("key") == key), None)
    return f"{_class_group(x)} on {_words.day(x['date'])}" if x else "a lesson"


def _cover_words(r, ckey):
    """'1A Science P6–P7 on Tue 13 Oct': the cover a history entry is about"""
    try: x, c = _cover.find(r, ckey)
    except ValueError: return "a lesson"
    return f"{_class_group(x)} {_periods_text(c)} on {_words.day(x['date'])}"


def _relief_of(r, ckey):
    try: return _cover.find(r, ckey)[1].get("relief") or "Nobody"
    except ValueError: return "Nobody"


def _soon(**kw):
    """ask relief.fill for a run after a save (the absences lock is released by then); asking never fails the save"""
    try: return _fill.soon(**kw)
    except Exception as e:
        current_app.logger.error("relief: a run of the picks could not be asked for (%s)", type(e).__name__)
        return False


def _tell_soon():
    """ask relief.tell what there is to say on Telegram, after a save and its history entry (the absences lock is released
    by then); asking never fails the save"""
    try: _tell.soon()
    except Exception as e: current_app.logger.error("relief: the messages could not be asked for (%s)", type(e).__name__)


def _saved(what, r, words, after=None, by=None):
    """after a save, the absences lock released: its history entry (by as _noted), then after(), then what there is to say on
    Telegram"""
    _noted(what, r, words, by=by)
    if after: after()
    _tell_soon()


# what can be done on the page and on Telegram (relief/bot.py), by its button there: (what the history entry is called, its
# words given the saved record, the cover key and who did it, what follows given the saved record and the published timetable)
STEPS = dict(
    ack=("relief acknowledged", lambda r, ckey, me: f"{me} acknowledged {_cover_words(r, ckey)}", None),
    change=("asked to change", lambda r, ckey, me: f"{me} asked to change {_cover_words(r, ckey)}", lambda r, pub: _soon(ids=[r["id"]], force=True)),
    cancel=("cancelled", lambda r, ckey, me: "cancelled", lambda r, pub: _cancelled(r, pub)),
    approve=("approved", lambda r, ckey, me: f"{_relief_of(r, ckey)} approved for {_cover_words(r, ckey)}", None),
    sendout=("sent out", lambda r, ckey, me: f"sent out {_relief_of(r, ckey)}'s relief for {_cover_words(r, ckey)}", None))


def step_saved(step, r, ckey, me, pub, by=None):
    """_saved for one of STEPS, me having done it; by: (me, "telegram") when it was done there"""
    what, words, after = STEPS[step]
    _saved(what, r, lambda: words(r, ckey, me), after and (lambda: after(r, pub)), by)


def _period_range(pub, a, b):
    """from and to (0-based, inclusive) from the query, or None for the whole day"""
    if a in (None, "") and b in (None, ""): return None
    try: a, b = int(a), int(b)
    except (TypeError, ValueError): raise ValueError(PERIODS)
    np = (pub.get("model") or {}).get("NP")
    if not 0 <= a <= b or (isinstance(np, int) and b >= np): raise ValueError(PERIODS)
    return (a, b)


def _iso(lesson):
    return dict(lesson, date=lesson["date"].isoformat())


def _clock():
    return datetime.datetime.now(ZoneInfo(os.environ.get("SCHOOL_TZ") or "Asia/Singapore")).replace(microsecond=0)


def _time(v):
    """an ISO timestamp with its offset, or None"""
    if not isinstance(v, str): return None
    try: t = datetime.datetime.fromisoformat(v)
    except ValueError: return None
    return t if t.tzinfo is not None else None


def _refusal(e):
    return {"error": str(e) if isinstance(e, ValueError) else _absences.WRONG}, 400


def _odd(e, what):
    """the catch-all refusal for a body the checks did not expect: the person gets the plain sentence, the log the trace"""
    current_app.logger.exception("relief: %s failed on an unexpected body", what)
    return _refusal(e)


def _periods(pub):
    """every period of the day: [{p, start, end}] (0-based p, times as HH:MM)"""
    return [dict(p=i, start=hhmm(a), end=hhmm(b)) for i, (a, b) in enumerate(bounds((pub or {}).get("model") or {}))]


# ---- what a form needs
@bp.get("/api/relief/lessons")
@need("relief")
def lessons():
    """a teacher's lessons on the dates (a,b) and periods (from, to), with every period of the day ({p, start, end}) for the
    forms' "Some periods"; each lesson's others are its other teachers who are not away then (a shared lesson needs no relief
    only while one of them is there); relief for yourself, relief.plan for anyone else"""
    pub, me, err = _gate()
    if err: return err
    teacher = request.args.get("teacher") or me
    if teacher != me and not _has("relief.plan"): return {"error": PLAN_ONLY}, 403
    try:
        settings = _settings.load(pub)
        _on_staff(pub, teacher)
        dates = _absences._iso_dates([x.strip() for x in (request.args.get("dates") or "").split(",") if x.strip()], _lessons.today())
        periods = _period_range(pub, request.args.get("from"), request.args.get("to"))
        records = _absences.all_records()
        links = _links_or_none(pub, settings["calendar"])
        by_date = {d.isoformat(): [_iso(_absences.as_now(records, x, links)) for x in _lessons.on_date(pub, settings["calendar"], teacher, d, periods=periods)]
                   for d in dates}                                                          # as new() decides
        every = _periods(pub)
        duties = {d.isoformat(): links.duties(teacher, d, periods) if links is not None else [] for d in dates}
    except ValueError as e: return _refusal(e)
    return jsonify(lessons=[x for v in by_date.values() for x in v], by_date=by_date, periods=every, duties=duties)


@bp.get("/api/relief/free")
@need("relief")
def free():
    """who is free for one lesson (its key) of the absent teacher, grouped and ranked; relief.plan"""
    pub, me, err = _gate("relief.plan", CHOOSE_ONLY)
    if err: return err
    absent, key = request.args.get("absent") or "", request.args.get("key") or ""
    try:
        settings = _settings.load(pub)
        _on_staff(pub, absent)
        try: date = datetime.date.fromisoformat(key.split("/")[0])
        except ValueError: raise ValueError(_absences.CHANGED)
        lesson = next((x for x in _lessons.on_date(pub, settings["calendar"], absent, date) if x["key"] == key), None)
        if lesson is None: raise ValueError(_absences.CHANGED)
        got = _free.free_then(pub, settings, _absences.all_records(), lesson, absent, links=_links_or_none(pub, settings["calendar"]))
    except ValueError as e: return _refusal(e)
    return jsonify(got)


@bp.get("/api/relief/people")
@need("relief")
def people():
    """everyone relief knows, for the reporting officer and absent teacher pickers: [{name, depts, staff_only}]"""
    pub, me, err = _gate()
    if err: return err
    return jsonify([dict(name=p["name"], depts=p["depts"], staff_only=bool(p.get("staff_only"))) for p in _staff(pub)])


@bp.get("/api/relief/school-days")
@need("relief")
def school_days():
    """the school days from today to the end of the last term, and why each other weekday is off, for the date calendar:
    {today, days: [iso], off: {iso: reason}}"""
    pub, me, err = _gate()
    if err: return err
    cal, today = _cal(pub), _lessons.today()
    if not cal.get("terms"): return {"error": _lessons.NO_CALENDAR}, 400
    got, off = _calendar.school_days(cal, (pub.get("model") or {}).get("days") or [], today)
    if not got: return {"error": _lessons.NO_DAYS}, 400
    return jsonify(today=today.isoformat(), days=[d.isoformat() for d in got], off={d.isoformat(): why for d, why in off.items()})


# ---- absences
def created(how, r, pub, by=None):
    """what follows the save of a new absence, asked or planned, on the page or (by: the person's name, "telegram") on Telegram"""
    _noted(how, r, how, by=by)
    _sync_exams(pub)
    _soon()               # an absence for today is picked at once; its teacher stops being anyone's waiting pick
    _tell_soon()


@bp.post("/api/relief/absences")
@need("relief")
def create():
    """asked when the teacher is yourself (or left out); planned for a colleague with relief.plan"""
    pub, me, err = _gate()
    if err: return err
    data = request.get_json(force=True, silent=True)
    if not isinstance(data, dict): return {"error": _absences.WRONG}, 400
    teacher = data.get("teacher")
    if teacher is None or teacher == "": teacher = me
    plan = _has("relief.plan")
    how = "asked" if teacher == me else "planned"
    if how == "planned" and not plan: return {"error": PLAN_ONLY}, 403
    try: r = _absences.new(dict(data, teacher=teacher), pub, me, how, may_choose=plan, links=_links_or_none(pub, _cal(pub)))
    except ValueError as e: return _refusal(e)
    except BAD_INPUT as e: return _odd(e, "sending an absence")
    created(how, r, pub)
    out = _out(r, pub, me); said = _not_told(r, pub)
    if said: out["officer_not_told"] = said
    return jsonify(out)


def _not_told(r, pub):
    """the sentence for the form when the reporting officer (not the absent teacher, not who sent it) is not on Telegram, else
    None; None too when that cannot be read: never the save's failure"""
    officer = r.get("reporting_officer")
    if not officer or officer in (r["teacher"], r["by"]) or not _connected(): return None
    try:
        if officer not in _chats.reachable(pub): return _tell.NOT_TOLD.format(officer=officer)
    except Exception as e: current_app.logger.error("relief: whether the officer is on Telegram could not be read (%s)", type(e).__name__)
    return None


@bp.get("/api/relief/absences/mine")
@need("relief")
def mine():
    pub, me, err = _gate()
    if err: return err
    return jsonify(absences=_views(_absences.for_teacher(me), pub, me))


@bp.get("/api/relief/absences/planned")
@need("relief")
def planned():
    pub, me, err = _gate("relief.plan", PLAN_ONLY)
    if err: return err
    return jsonify(absences=_views(_absences.planned_by(me), pub, me))


def _seen_at(name):
    d = store.read_json(SEEN, {})
    return _time(d.get(name)) if isinstance(d, dict) else None


@bp.get("/api/relief/absences")
@need("relief")
def whats_in():
    """every absence, newest first; new = submitted, or given a lesson (a backup's changed_at), at or after the time this
    person last marked All Relief Requests as seen (never: all new); cover = dict(total, approved, waiting, open): its covers that
    need relief, each part of a split lesson one, less the lessons an exam or event stops (approved: approved, acknowledged
    or asked to change); unacked: today's reliefs that have reached their teacher and are neither acknowledged nor asked to
    change, dict(who, p, n, started) in period order; nudge: planned by
    someone else, not acknowledged, not cancelled, not over, and now past times.remind_at on the school day before its
    first lesson (fill.due_at). Reads only: the page posts /seen after showing the list."""
    pub, me, err = _gate("relief.team", TEAM_ONLY)
    if err: return err
    since, as_of = _seen_at(me), _clock().isoformat()
    settings = _settings.load(pub)
    now, today = _fill._when(None), _lessons.today()
    out, links, bad = [], _links_or_none(pub, settings["calendar"]), set()
    for r in _absences.all_records():
        v = _out(r, pub, me, settings["calendar"])                      # _links keeps one Links for the request
        at, changed = _time(v.get("at")), _time(v.get("changed_at"))
        v["new"] = since is None or at is None or at >= since or (changed is not None and changed >= since)
        v["cover"], v["nudge"] = _cover_counts(r, links), _nudge(r, pub, settings, now, today)
        v["unacked"] = _unacked(r, pub, settings, links, now, today, bad)
        out.append(v)
    if bad: current_app.logger.error("relief: today's reliefs not yet acknowledged could not all be worked out (%s)", ", ".join(sorted(bad)))
    return jsonify(absences=out, new_since=since.isoformat() if since else None, as_of=as_of)


def _cover_counts(r, links=None):
    n = dict(total=0, approved=0, waiting=0, open=0)
    for x in r.get("lessons") or []:
        if _cover.stopped(links, x): continue            # a lesson that does not happen needs no relief, past or to come
        for c in _cover.covers(x):
            s = _cover.state(r, x, c)
            if s == "cancelled": continue
            n["total"] += 1
            n["approved" if s in APPROVED else s] += 1
    return n


def _unacked(r, pub, settings, links, now, today, bad):
    """the covers of r dated today (the school's date), needed, not stopped, approved and not acknowledged nor asked to change,
    that have reached their teacher, as dict(who, p, n, started: its lesson has begun), in period order. A lesson or cover that
    cannot be read is passed over on its own (the readable ones stay) and its error's kind is added to the set bad"""
    out, day = [], today.isoformat()
    for x in r.get("lessons") or []:
        try:
            if x.get("date") != day or _cover.stopped(links, x): continue
            parts = _cover.covers(x)
        except Exception as e: bad.add(type(e).__name__); continue
        for c in parts:
            try:
                if _cover.state(r, x, c) != "approved" or not _cover.reached(r, x, c, now, settings, pub): continue
                out.append(dict(who=c["relief"], p=int(c["p"]), n=int(c.get("n") or 1), started=_hours.starts(pub, x, c) <= now))
            except Exception as e: bad.add(type(e).__name__)
    return sorted(out, key=lambda u: (u["p"], u["n"]))


@bp.post("/api/relief/absences/seen")
@need("relief")
def seen():
    """records when this person last saw All Relief Requests: the as_of posted back, never later than now"""
    pub, me, err = _gate("relief.team", TEAM_ONLY)
    if err: return err
    now, at = _clock(), _time(_body().get("at"))
    at = now if at is None or at > now else at
    iso = at.isoformat(timespec="seconds")
    with _SEEN_LOCK:
        d = store.read_json(SEEN, {})
        d = d if isinstance(d, dict) else {}
        d[me] = iso
        os.makedirs(os.path.dirname(SEEN), exist_ok=True)
        store.write_json(SEEN, d)
    return jsonify(seen=iso)


@bp.get("/api/relief/absences/<id>")
@need("relief")
def one(id):
    pub, me, err = _gate()
    if err: return err
    r, err = _record(id, me)
    if err: return err
    return jsonify(_out(r, pub, me))


def _change(id, do, what, words, right=None, refused=None, gate=("relief", None), after=None, same_is_nothing=False):
    """gate (the relief team's routes: TEAM, asked before the absence is opened, so a teacher gets TEAM_ONLY whatever the
    id), open the absence (403/404 as _record), check the right, do(record, me, pub, body) -> the saved record, then its
    history entry: what, and words(the saved record); then after(the saved record, pub) and _tell_soon, the absences lock
    released. same_is_nothing: when do answers the record as it was opened (nothing was saved), no history entry and no
    sweep"""
    pub, me, err = _gate(*gate)
    if err: return err
    r, err = _record(id, me)
    if err: return err
    if right and not _has(right): return {"error": refused}, 403
    opened = r
    try: r = do(r, me, pub, _body())
    except ValueError as e: return _refusal(e)
    except BAD_INPUT as e: return _odd(e, "changing an absence")
    if not (same_is_nothing and r == opened): _saved(what, r, lambda: words(r), after and (lambda: after(r, pub)))
    return jsonify(_out(r, pub, me))


@bp.post("/api/relief/absences/<id>/acknowledge")
@need("relief")
def acknowledge(id):
    return _change(id, lambda r, me, pub, b: _absences.acknowledge(r["id"], me), "acknowledged", lambda r: "acknowledged")


@bp.put("/api/relief/absences/<id>/lessons/<path:key>/work")
@need("relief")
def work(id, key):
    """a body that is not the work with its files and known (none, not JSON, {}) is refused by set_work: it never clears the work"""
    return _change(id, lambda r, me, pub, b: _absences.set_work(r["id"], key, b, me), "work", lambda r: f"work set for {_lesson_words(r, key)}")


@bp.post("/api/relief/absences/<id>/lessons/<path:key>/not-needed")
@need("relief")
def not_needed(id, key):
    return _change(id, lambda r, me, pub, b: _absences.not_needed(r["id"], key, b.get("why"), me, team=_has("relief.team")),
                   "not-needed", lambda r: f"{_lesson_words(r, key)} not needed")


@bp.post("/api/relief/absences/<id>/lessons/<path:key>/needed")
@need("relief")
def needed(id, key):
    return _change(id, lambda r, me, pub, b: _absences.needed_again(r["id"], key, me, team=_has("relief.team")),
                   "needed", lambda r: f"{_lesson_words(r, key)} needed again", after=lambda r, pub: _soon())


def _choose(r, key, me, pub, b):
    name = b.get("relief")
    if name is not None and not isinstance(name, str): raise ValueError(_absences.WRONG)
    return _absences.choose(r["id"], key, name or None, me, pub, links=_links_or_none(pub, _cal(pub)))


def _chosen_words(r, key):
    x = next((x for x in r.get("lessons") or [] if x.get("key") == key), {})
    return f"{x['relief']} chosen for {_lesson_words(r, key)}" if x.get("relief") else f"no relief teacher chosen for {_lesson_words(r, key)}"


@bp.put("/api/relief/absences/<id>/lessons/<path:key>/relief")
@need("relief")
def relief(id, key):
    return _change(id, lambda r, me, pub, b: _choose(r, key, me, pub, b), "relief", lambda r: _chosen_words(r, key),
                   right="relief.plan", refused=CHOOSE_ONLY, same_is_nothing=True)


def _cancelled(r, pub):
    """after a cancel: the backups back in step first (a lesson it gives back goes to one again), then the picks"""
    _sync_exams(pub)
    _soon()


@bp.post("/api/relief/absences/<id>/cancel")
@need("relief")
def cancel(id):
    what, words, after = STEPS["cancel"]
    return _change(id, lambda r, me, pub, b: _absences.cancel(r["id"], b.get("why"), me, team=_has("relief.team")), what,
                   lambda r: words(r, None, None), after=after)


# ---- work files
@bp.post("/api/relief/absences/<id>/files")
@need("relief")
def upload(id):
    """one file for the absent teacher or its planner; refused from its length before the body is read"""
    pub, me, err = _gate()
    if err: return err
    r, err = _record(id, me)
    if err: return err
    if not _absences._owner(r, me): return {"error": _absences.NOT_YOURS}, 403
    if r.get("cancelled"): return {"error": _absences.CANCELLED}, 400
    if (request.content_length or 0) > _files.MAX + SLACK: return {"error": _files.TOO_BIG}, 400
    f = request.files.get("file")
    if f is None or not f.filename: return {"error": _files.WRONG_KIND}, 400
    data = f.stream.read(_files.MAX + 1)          # never more than one byte past the limit
    try: saved = _files.save(r["id"], f.filename, data)
    except ValueError as e: return _refusal(e)
    return jsonify(saved)


@bp.get("/api/relief/files/<id>/<file>")
@need("relief")
def download(id, file):
    """the file as an attachment with the name it was given, for whoever may open the absence, and for the relief teacher
    a lesson that lists the file is approved to (its whole cover, or a part of it)"""
    pub, me, err = _gate()
    if err: return err
    r, err = _record(id, me)
    if err:
        r = _absences.load(id)
        if r is None or not _relieves(r, file, me, _reached(pub)): return err
    p = _files.path(r["id"], file)
    if not p: return {"error": NO_FILE}, 404
    names = [f.get("name") for x in r.get("lessons") or [] for f in (x.get("work") or {}).get("files") or [] if f.get("id") == file]
    resp = send_file(p, as_attachment=True, download_name=(names[0] if names and names[0] else "file" + os.path.splitext(p)[1]))
    resp.headers["Cache-Control"] = "private, no-store"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    return resp


def _relieves(r, file, me, reached):
    """me is the approved relief teacher of a lesson of r whose work lists the file, and that relief has reached me (reached:
    _reached)"""
    for x in r.get("lessons") or []:
        if not any(f.get("id") == file for f in (x.get("work") or {}).get("files") or []): continue
        if any(c.get("relief") == me and _cover.state(r, x, c) in APPROVED and reached(r, x, c) for c in _cover.covers(x)): return True
    return False


# ---- the planned relief download
def _day(v, default):
    if v in (None, ""): return default
    try: return datetime.date.fromisoformat(v)
    except ValueError: raise ValueError(DATES)


def _relief_cell(r, x, c, links=None):
    """the sheet's Relief teacher for a cover: NOT_ON when an exam or event stops the lesson, else the name once approved
    (approved, acknowledged, asked to change), else WAITING_TEAM for a pick (the AI's, the app's, a planner's) or NOT_CHOSEN"""
    why = _cover.stopped(links, x)
    if why: return NOT_ON.format(why=why)
    s = _cover.state(r, x, c)
    if s in APPROVED: return c.get("relief") or NOT_CHOSEN
    return WAITING_TEAM if s == "waiting" else NOT_CHOSEN


@bp.get("/api/relief/planned.csv")
@need("relief")
def planned_csv():
    """the lessons needing relief in every absence not cancelled, planned or asked, dated start..end (today when left out),
    so a day's sheet is complete, one row a cover (each part of a split lesson its own); Relief teacher: the name only once
    the relief team has approved it (_relief_cell); Set by = whoever sent it; never the reason"""
    pub, me, err = _gate("relief.plan", PLAN_ONLY)
    if err: return err
    try:
        today = _lessons.today()
        start = _day(request.args.get("start"), today)
        end = _day(request.args.get("end"), start)
        if end < start: raise ValueError(DATES)
    except ValueError as e: return _refusal(e)
    rows = []
    for r in _absences.all_records():
        if r.get("cancelled"): continue
        for x in r.get("lessons") or []:
            if not x.get("needed"): continue
            d = datetime.date.fromisoformat(x["date"])
            if start <= d <= end: rows += [(d, int(c["p"]), r["teacher"], x, c, r) for c in _cover.covers(x)]
    rows.sort(key=lambda t: t[:3])
    links = _links_or_none(pub, _cal(pub)) if rows else None
    buf = io.StringIO(); w = csv.writer(buf)
    w.writerow(COLUMNS)
    for d, p, teacher, x, c, r in rows:
        group = _class_group(x)
        a, b = _times(pub, x, c)
        time = f"{a}–{b}" if a and b else ""
        w.writerow([_cell(v) for v in (d.isoformat(), teacher, group, _periods_text(c), time, _relief_cell(r, x, c, links),
                                       r.get("remarks") or "", r.get("by") or "")])
    name = f"planned relief {start.isoformat()}" + (f" to {end.isoformat()}" if end != start else "") + ".csv"
    return Response("﻿" + buf.getvalue(), mimetype="text/csv", headers={"Content-Disposition": f'attachment; filename="{name}"'})


# ---- the relief team (relief stage 3): Today, approving, changing, splitting, Fill now
def _date_in(v):
    """a date sent in a body as YYYY-MM-DD; anything else is WRONG (never fromisoformat's own words)"""
    if not isinstance(v, str): raise ValueError(_absences.WRONG)
    try: return datetime.date.fromisoformat(v)
    except ValueError: raise ValueError(_absences.WRONG)


def _released(settings, pub, x, c, s, now):
    """(out, goes_at, sent_out) of a cover in state s at now, as Today's row has them: for an approved relief (approved,
    acknowledged, asked to change) out "unsent" (not sent out for this approval), "held" (sent out, its time not come) or
    "sent" (it has reached its teacher), goes_at when it goes or went (ISO, None while not sent out) and sent_out dict(by,
    at); (None, None, None) in any other state"""
    if s not in APPROVED: return None, None, None
    so = _cover.sent_out(c)
    if so is None: return "unsent", None, None
    goes = _cover.goes_at(c, x, settings, pub)
    return ("sent" if goes is not None and _fill._when(now) >= goes else "held"), goes.isoformat() if goes else None, dict(by=so.get("by"), at=so.get("at"))


def _row(pub, settings, records, r, x, c, i, links=None, now=None, light=False):
    """one cover as Today lists it. state "stopped" (stopped: why) for a lesson an approved exam or event stops: nothing is
    to be done for it, and its pick or relief (pick) is shown as it was; duty: why its teacher is not there when they are in
    school, on an exam duty or at an event (a backup's reason), else "". stale: its relief teacher (waiting or approved) is no longer free then; over_now: the
    relief takes them over a checked limit; nobody: an open cover nobody at all is free for; warn: the sentence for any of
    these, and OVER_ONLY for an open cover whose free people are all over a limit (the app picks none of them); change: a
    request to change, with its new pick (stale too when that person is no longer free); away: the relief teacher it was approved
    to, who is away then, while it is open or waiting again since (cover.was_away), else None; out, goes_at and sent_out (_released, at
    now: absences._now() when None). light: the row as it stands before who is free is worked out (stale, over_now, nobody False,
    warn None: a term's list stays quick). One free_then for the cover gives them all; never the absence's reason. told and linked:
    today() puts them there"""
    s = _cover.state(r, x, c)
    ckey, p, n = _cover.cover_key(x, i), int(c["p"]), int(c.get("n") or 1)
    start, end = _times(pub, x, c)
    w, pk = x.get("work") or {}, _cover.pick_of(r, c)
    ch = c.get("change") if s == "change" else None
    new = _cover.new_pick(c) if ch else None
    brief = lambda q: dict(who=q["who"], by=q["by"], reason=q.get("reason") or "") if q else None
    try: out, goes, so = _released(settings, pub, x, c, s, _absences._now() if now is None else now)
    except Exception as e:                       # a record changed by hand: sent out, when not known; never the page's failure
        current_app.logger.error("relief: when a relief goes could not be worked out (%s)", type(e).__name__)
        out, goes, so = "held", None, None
    row = dict(id=r["id"], ckey=ckey, key=x["key"], split=bool(x.get("parts")), absent=r["teacher"], classes=list(x.get("classes") or []),
               subject=x.get("subject") or "", group=x.get("group") or "", room=x.get("room") or "", p=p, n=n, start=start, end=end,
               work_set=bool(w.get("text") or w.get("link") or w.get("files")), state=s, pick=brief(pk) if s != "open" else None,
               approved=c.get("approved") or None, ack=c.get("ack") or None,
               change=dict(why=ch.get("why"), at=ch.get("at"), pick=brief(new), stale=False) if ch else None,
               stale=False, over_now=False, nobody=False, warn=None, stopped="", duty=(r.get("reason_text") or "") if r.get("exams") else "",
               told=None, linked=False, out=out, goes_at=goes, sent_out=so, planned_by=_cover.planned_by(c) if s in APPROVED else None,
               away=(_cover.was_away(c) or {}).get("who") if s in ("open", "waiting") else None)
    if s == "cancelled": return row
    why = _cover.stopped(links, x)
    if why: return dict(row, state="stopped", stopped=why, out=None, goes_at=None, sent_out=None)
    if light: return row
    try: got = _free.free_then(pub, settings, records, dict(x, key=ckey, p=p, n=n), r["teacher"], links=links)
    except ValueError: return row                # no longer a school day in the calendar: nothing to say
    free = {q["name"]: q for g in got["groups"] for q in g["people"]}
    if s == "open":
        if not free: row.update(nobody=True, warn=_cover.NOBODY)
        elif all(q.get("over") for q in free.values()): row["warn"] = OVER_ONLY
        return row
    who = c["relief"]
    row.update(stale=who not in free, over_now=bool(free.get(who, {}).get("over")))
    if row["stale"]: row["warn"] = (_cover.NOT_FREE if s == "waiting" else STALE).format(name=who)
    if new: row["change"]["stale"] = new["who"] not in free
    return row


def _telegram(pub):
    """(what has been said of the reliefs on Telegram, who can be reached there), read once a request; nothing and nobody while
    there is no token, or when it cannot be read: the page works without"""
    try:
        if _tg.on(): return _tell.said(), _chats.reachable(pub)
    except Exception as e: current_app.logger.error("relief: what was said on Telegram could not be read (%s)", type(e).__name__)
    return _tell.Said({}), {}


def _connected():
    """the bot is connected; False when that cannot be read: the page works without"""
    try: return _chats.connected() is not None
    except Exception as e: current_app.logger.error("relief: whether Telegram is connected could not be read (%s)", type(e).__name__)
    return False


def _told(said, r, c, row):
    """what was said of the relief in the row on Telegram (tell.Said.of); None when it has not reached its teacher (out is not
    "sent"), or cannot be worked out (a record changed by hand): never the page's failure"""
    if row["state"] not in APPROVED or row.get("out") != "sent": return None
    try: return said.of(_tell.key_of(said.told, r, c, row["ckey"]))
    except Exception as e:
        current_app.logger.error("relief: what was said of a relief could not be worked out (%s)", type(e).__name__)
        return None


def _day_hours(pub, settings, now):
    """(hours, opens): the times the page speaks of, dict(morning, send_from, cut_off, today, next_day, past_cut_off), and the
    date Today opens on when none is asked for. next_day: the next school day after today, within 30 days, else None.
    past_cut_off: today is a school day and its cut-off has come. opens: today; past the cut-off, or on a day that is not a
    school day, next_day (today when there is none)"""
    h, today = _hours.of(settings), _lessons.today()
    at = _fill._when(now)
    school = _hours.school(settings, pub, today)
    past = school and at.time() >= h.cut_off
    nxt = next((d for d in (today + datetime.timedelta(days=i) for i in range(1, 31)) if _hours.school(settings, pub, d)), None)
    hrs = dict(morning=h.morning.strftime("%H:%M"), send_from=h.send_from.strftime("%H:%M"), cut_off=h.cut_off.strftime("%H:%M"), today=today.isoformat(),
               next_day=nxt.isoformat() if nxt else None, past_cut_off=bool(past))
    return hrs, (nxt if nxt and (past or not school) else today)


def _asked_after(r, date, hrs, cut):
    """"14:10" when the absence r was sent today, for today (date), at or after today's cut-off (cut): nobody on the team was pinged
    for it; else None"""
    if not r.get("at"): return None
    try: at = _fill._when(r.get("at"))
    except (TypeError, ValueError): return None
    return at.strftime("%H:%M") if date == hrs["today"] == at.date().isoformat() and at.time() >= cut else None


def _today_left(pub, records, links, hrs, date, now):
    """how many covers of today's lessons still to come are open, waiting for approval, or approved and not sent out
    (cover.sent_out), while the page shows a later day because today's cut-off is past; 0 on today's own view, before the cut-off,
    and when there is none. Nobody is pinged for them (after the cut-off nobody is): the page says so. A cover that cannot be
    read is passed over, logged by its kind"""
    if not hrs["past_cut_off"] or date <= hrs["today"]: return 0
    at, n = _fill._when(now), 0
    for r in records:
        if r.get("cancelled"): continue
        for x in r.get("lessons") or []:
            if x.get("date") != hrs["today"] or not x.get("needed"): continue
            try:
                if _cover.stopped(links, x): continue
                for c in _cover.covers(x):
                    s = _cover.state(r, x, c)
                    n += (s in ("open", "waiting") or (s == "approved" and _cover.sent_out(c) is None)) and _hours.starts(pub, x, c) > at
            except Exception as e: current_app.logger.error("relief: a lesson of today could not be counted (%s)", type(e).__name__)
    return n


def _counts(rows):
    """dict(need, waiting, approved, unsent, held, acknowledged, change, nobody, open) of Today's rows: a cancelled or stopped row is
    not counted; an approved relief counts as unsent, held or approved by its out"""
    counts = dict(need=0, waiting=0, approved=0, unsent=0, held=0, acknowledged=0, change=0, nobody=0, open=0)
    for v in rows:
        if v["state"] in ("cancelled", "stopped"): continue
        counts["need"] += 1; counts["nobody"] += v["nobody"]
        counts[dict(unsent="unsent", held="held").get(v["out"], "approved") if v["state"] == "approved" else v["state"]] += 1
    return counts


@bp.get("/api/relief/today")
@need("relief")
def today():
    """every cover of the date's lessons that need relief (?date=YYYY-MM-DD; left out: today, or past today's cut-off on a school day,
    or on a day that is not one, the next school day, _day_hours), in time order, one row a
    cover (_row; a cancelled absence's as "cancelled", one an exam or event stops as "stopped", both out of the counts), with counts=dict(need, waiting, approved,
    unsent, held, acknowledged, change, nobody, open) (an approved relief, not acknowledged, counts as unsent, held or approved by
    its out: approved once it has reached its teacher) and filling: picks are being made (the page fetches again). On Telegram, each row: told,
    dict(state "sent" | "unsure" (it may have been) | "queued" | "failed" | "dropped", at) of the last message of the relief
    approved, its reminders too, else None (tell.Said.of; a stopped lesson's is None), and linked, its relief teacher can be
    reached, and asked_after (_asked_after: "14:10" for an absence sent today, for today, after the cut-off, else None); telegram: the
    bot is connected (the page shows neither while it is not); hours (_day_hours, with today_left: _today_left); relief.team"""
    pub, me, err = _gate(*TEAM)
    if err: return err
    settings, now = _settings.load(pub), _absences._now()
    hrs, opens = _day_hours(pub, settings, now)
    try: date = _day(request.args.get("date"), opens).isoformat()
    except ValueError as e: return _refusal(e)
    filling = _fill.filling()                   # read first: a run that ends while the rows are read is fetched again
    records, rows = _absences.all_records(), []
    cut = _hours.of(settings).cut_off
    links = _links_or_none(pub, settings["calendar"])
    said, reach = _telegram(pub)
    for r in records:
        for x in r.get("lessons") or []:
            if x.get("date") != date or not x.get("needed"): continue
            for i, c in enumerate(_cover.covers(x)):
                row = _row(pub, settings, records, r, x, c, i, links, now)
                who = c.get("relief")
                rows.append(dict(row, told=_told(said, r, c, row), linked=isinstance(who, str) and who in reach, asked_after=_asked_after(r, date, hrs, cut)))
    rows.sort(key=lambda v: (v["p"], v["absent"], v["ckey"]))
    counts = _counts(rows)
    hrs = dict(hrs, today_left=_today_left(pub, records, links, hrs, date, now))
    return jsonify(date=date, filling=filling, counts=counts, rows=rows, telegram=_connected(), hours=hrs)


@bp.get("/api/relief/ahead")
@need("relief")
def ahead():
    """the covers of every school day after today up to until (?span=weeks: today + 14 days, the default; ?span=term: the end of the
    term today is in, else of the first term that starts later, else as weeks) -> dict(as_of, span, until, days=[dict(date,
    away: how many teachers are absent that day, counts: as Today's, rows: one a cover of an absence not cancelled, _row light, in
    (p, absent, ckey) order)]); a date with no row is left out. Who is free is not worked out, and told and linked are left empty; relief.team"""
    pub, me, err = _gate(*TEAM)
    if err: return err
    settings, now = _settings.load(pub), _absences._now()
    today_ = _lessons.today()
    span = "term" if request.args.get("span") == "term" else "weeks"
    until, cal = today_ + datetime.timedelta(days=14), settings["calendar"]
    if span == "term" and isinstance(cal, dict):
        try:
            term = term_of(cal, today_) or min((t for t in cal.get("terms", []) if datetime.date.fromisoformat(str(t["start"])[:10]) > today_), key=lambda t: str(t["start"])[:10], default=None)
            if term: until = datetime.date.fromisoformat(str(term["end"])[:10])
        except (TypeError, ValueError, KeyError, AttributeError) as e: current_app.logger.error("relief: the end of the term could not be read (%s)", type(e).__name__)
    first, last = today_.isoformat(), until.isoformat()
    records = _absences.all_records()
    links = _links_or_none(pub, cal if isinstance(cal, dict) else {})
    by_day, bad = {}, set()
    for r in records:
        if r.get("cancelled"): continue
        for x in r.get("lessons") or []:
            try:
                if not x.get("needed") or not isinstance(x.get("date"), str) or not first < x["date"] <= last: continue
                for i, c in enumerate(_cover.covers(x)):
                    try: by_day.setdefault(x["date"], []).append(_row(pub, settings, records, r, x, c, i, links, now, light=True))
                    except Exception as e: bad.add(type(e).__name__)
            except Exception as e: bad.add(type(e).__name__)             # a record changed by hand: passed over, never the page's failure
    if bad: current_app.logger.error("relief: a lesson to come could not be read and was passed over (%s)", ", ".join(sorted(bad)))
    days = []
    for date in sorted(by_day):
        rows = sorted(by_day[date], key=lambda v: (v["p"], v["absent"], v["ckey"]))
        days.append(dict(date=date, away=len({v["absent"] for v in rows}), counts=_counts(rows), rows=rows))
    return jsonify(as_of=_fill._when(now).isoformat(), span=span, until=last, days=days)


@bp.post("/api/relief/absences/<id>/covers/<path:ckey>/approve")
@need("relief")
def approve(id, ckey):
    """{who}: the waiting pick, or a request to change's new pick, approved while it is still who (the name the page
    showed), else PICK_CHANGED, as for a body without who; relief.team"""
    what, words, after = STEPS["approve"]
    return _change(id, lambda r, me, pub, b: _cover.approve(r["id"], ckey, b.get("who"), me, pub, _settings.load(pub), links=_links_or_none(pub, _cal(pub))), what,
                   lambda r: words(r, ckey, None), gate=TEAM, after=after)


@bp.post("/api/relief/today/approve-all")
@need("relief")
def approve_all():
    """{date, covers: [{id, ckey, who}]}: the waiting covers of date the page showed, each approved in time order while it
    still waits for who (cover.approve_all), the others skipped -> dict(approved: how many, skipped=[{id, ckey, name, why}]);
    one history entry for each cover this call approved, and none for any other; relief.team"""
    pub, me, err = _gate(*TEAM)
    if err: return err
    b = _body()
    try:
        date = _date_in(b.get("date"))
        got = _cover.approve_all(date, b.get("covers"), me, pub, _settings.load(pub), links=_links_or_none(pub, _cal(pub)))
    except ValueError as e: return _refusal(e)
    except BAD_INPUT as e: return _odd(e, "approving all")
    records = {}
    for id, ckey, who in got["approved"]:       # exactly the covers approved under the lock, read back for the entry's words
        r = records[id] = records.get(id) or _absences.load(id)
        if r: _noted("approved", r, lambda r=r, ckey=ckey, who=who: f"{who} approved for {_cover_words(r, ckey)}")
    if got["approved"]: _tell_soon()
    return jsonify(approved=len(got["approved"]), skipped=got["skipped"])


@bp.post("/api/relief/absences/<id>/covers/<path:ckey>/send-out")
@need("relief")
def send_out(id, ckey):
    """{who, approved_at}: the approved relief the page showed sent out to its teacher (cover.send_out), at once in school
    hours, else held until the earliest send-out time; relief.team"""
    what, words, after = STEPS["sendout"]
    return _change(id, lambda r, me, pub, b: _cover.send_out(r["id"], ckey, b.get("who"), me, pub, _settings.load(pub), links=_links_or_none(pub, _cal(pub)),
                                                             approved_at=b.get("approved_at")), what, lambda r: words(r, ckey, None), gate=TEAM, after=after)


@bp.post("/api/relief/today/send-out")
@need("relief")
def send_out_all():
    """{date, covers: [{id, ckey, who, approved_at}]}: the approved covers of date the page showed, each sent out in time order
    while it is still as shown (cover.send_out_all), the others skipped -> dict(sent: how many, at: the earliest time one of
    those sent goes, when that is later than now (ISO; None when every one goes at once), skipped=[{id, ckey, name, why}]); one
    history entry for the press, of no one absence, and none when nothing was sent; relief.team"""
    pub, me, err = _gate(*TEAM)
    if err: return err
    b = _body()
    try:
        date = _date_in(b.get("date"))
        settings = _settings.load(pub)
        got = _cover.send_out_all(date, b.get("covers"), me, pub, settings, links=_links_or_none(pub, _cal(pub)))
    except ValueError as e: return _refusal(e)
    except BAD_INPUT as e: return _odd(e, "sending out all")
    n = len(got["sent"])
    if n: _noted("sent out", None, f"Sent out {n} {'relief' if n == 1 else 'reliefs'} for {_words.day(date.isoformat())}")
    now, held, records = _fill._when(None), [], {}
    for id, ckey, who in got["sent"]:           # exactly the covers sent out under the lock, read back for when they go
        try:
            r = records[id] = records.get(id) or _absences.load(id)
            x, c = _cover.find(r, ckey)
            goes = _cover.goes_at(c, x, settings, pub)
        except Exception as e:                  # saved already: when it goes is the answer's, never the save's failure
            current_app.logger.error("relief: when a relief goes could not be worked out (%s)", type(e).__name__); continue
        if goes is not None and goes > now: held.append(goes)
    if n: _tell_soon()
    return jsonify(sent=n, at=min(held).isoformat() if held else None, skipped=got["skipped"])


@bp.put("/api/relief/absences/<id>/covers/<path:ckey>/relief")
@need("relief")
def change(id, ckey):
    """Change: {relief: a name} gives the cover to them and approves it in one; relief.team"""
    return _change(id, lambda r, me, pub, b: _cover.change(r["id"], ckey, b.get("relief"), me, pub, _settings.load(pub), links=_links_or_none(pub, _cal(pub))), "changed",
                   lambda r: f"{_relief_of(r, ckey)} chosen and approved for {_cover_words(r, ckey)}", gate=TEAM)


@bp.get("/api/relief/absences/<id>/covers/<path:ckey>/free")
@need("relief")
def cover_free(id, ckey):
    """who is free for the cover's own periods (free.free_then, the cover itself taking nobody's time), for Change; relief.team"""
    pub, me, err = _gate(*TEAM)
    if err: return err
    r, err = _record(id, me)
    if err: return err
    try:
        x, c = _cover.find(r, ckey)
        if r.get("cancelled"): raise ValueError(_absences.CANCELLED)
        if not x.get("needed"): raise ValueError(_absences.NO_NEED)
        links = _links_or_none(pub, _cal(pub))
        _cover._happens(links, x)
        got = _free.free_then(pub, _settings.load(pub), _absences.all_records(), dict(x, key=ckey, p=int(c["p"]), n=int(c.get("n") or 1)), r["teacher"], links=links)
    except ValueError as e: return _refusal(e)
    return jsonify(got)


@bp.post("/api/relief/absences/<id>/lessons/<path:key>/split")
@need("relief")
def split(id, key):
    """{at}: the lesson (or the part holding period at) split so that a part starts at period at; relief.team"""
    return _change(id, lambda r, me, pub, b: _cover.split(r["id"], key, b.get("at"), me, links=_links_or_none(pub, _cal(pub))), "split",
                   lambda r: f"{_lesson_words(r, key)} split before P{int(_body().get('at')) + 1}", gate=TEAM)


@bp.post("/api/relief/absences/<id>/lessons/<path:key>/join")
@need("relief")
def join(id, key):
    """Join again: the parts made one open lesson, while none is approved; relief.team"""
    return _change(id, lambda r, me, pub, b: _cover.join(r["id"], key, me, links=_links_or_none(pub, _cal(pub))), "joined", lambda r: f"{_lesson_words(r, key)} joined again", gate=TEAM)


@bp.post("/api/relief/absences/<id>/covers/<path:ckey>/keep")
@need("relief")
def keep(id, ckey):
    """Keep: a request to change closed, the relief staying with the teacher who asked; relief.team"""
    return _change(id, lambda r, me, pub, b: _cover.keep(r["id"], ckey, me, links=_links_or_none(pub, _cal(pub))), "kept",
                   lambda r: f"{_relief_of(r, ckey)} kept for {_cover_words(r, ckey)}", gate=TEAM)


@bp.post("/api/relief/today/fill")
@need("relief")
def fill_now():
    """Fill now: picks for every open cover of {date}, due or not, in the background -> dict(date, started, filling); the
    picks write no history entry; relief.team"""
    pub, me, err = _gate(*TEAM)
    if err: return err
    try: date = _date_in(_body().get("date"))
    except ValueError as e: return _refusal(e)
    started = _soon(date=date, force=True)
    return jsonify(date=date.isoformat(), started=bool(started), filling=_fill.filling())


# ---- the relief teacher: Reliefs I'm covering, Acknowledge, Request to change
def _covering_item(pub, r, ckey):
    """a cover approved to the person asking, as they see it: never the absence's reason, remarks, reporting officer, who
    planned it, a pick (or its reason) or the cover's history; change: their own request (why, at), never its new pick;
    stopped: why an approved exam or event stops the lesson (nothing to cover then), or "" """
    x, c = _cover.find(r, ckey)
    s, (start, end), w = _cover.state(r, x, c), _times(pub, x, c), x.get("work") or {}
    ch = c.get("change") if s == "change" else None
    return dict(id=r["id"], ckey=ckey, date=x["date"], start=start, end=end, p=int(c["p"]), n=int(c.get("n") or 1),
                classes=list(x.get("classes") or []), subject=x.get("subject") or "", group=x.get("group") or "", room=x.get("room") or "",
                absent=r["teacher"], work=dict(text=w.get("text") or "", link=w.get("link") or "",
                                               files=[dict(id=f.get("id"), name=f.get("name"), size=f.get("size")) for f in w.get("files") or []]),
                state=s, ack=c.get("ack") or None, change=dict(why=ch.get("why"), at=ch.get("at")) if ch else None,
                stopped=_cover.stopped(_links_or_none(pub, _cal(pub)), x))


@bp.get("/api/relief/covering")
@need("relief")
def covering():
    """the covers approved to me (approved, acknowledged, asked to change) that have reached me (_reached), from the Monday of this
    week on, by date and period: nothing waiting for the relief team, or for its Send out or its time, is here"""
    pub, me, err = _gate()
    if err: return err
    since, out, reached = week_of(_lessons.today())[0].isoformat(), [], _reached(pub)
    for r in _absences.all_records():
        if r.get("cancelled"): continue
        for x in r.get("lessons") or []:
            if (x.get("date") or "") < since or not x.get("needed"): continue
            for i, c in enumerate(_cover.covers(x)):
                if c.get("relief") == me and _cover.state(r, x, c) in APPROVED and reached(r, x, c): out.append(_covering_item(pub, r, _cover.cover_key(x, i)))
    out.sort(key=lambda v: (v["date"], v["p"], v["absent"], v["ckey"]))
    return jsonify(covers=out)


def _yours(id, ckey, do, step):
    """a step (of STEPS) the approved relief teacher of the cover takes, once the relief has reached them: anyone else (or a cover
    not approved, not reached its teacher, gone, or of no absence) gets 403 NOT_YOURS_COVER, the same answer whatever the reason,
    before anything is read out; do(record, lesson, cover, me, body, pub, reached: _reached, to be asked again under the lock) ->
    the saved record, or None when nothing was to be saved (no history entry then)"""
    pub, me, err = _gate()
    if err: return err
    r, reached = _absences.load(id), _reached(pub)
    try: x, c = _cover.find(r, ckey) if r else (None, None)
    except ValueError: c = None
    if c is None or c.get("relief") != me or _cover.state(r, x, c) not in APPROVED or not reached(r, x, c): return {"error": _cover.NOT_YOURS_COVER}, 403
    try: saved = do(r, x, c, me, _body(), pub, reached)
    except ValueError as e: return ({"error": str(e)}, 403) if str(e) == _cover.NOT_YOURS_COVER else _refusal(e)
    except BAD_INPUT as e: return _odd(e, "answering a relief")
    if saved is None: return jsonify(_covering_item(pub, r, ckey))
    step_saved(step, saved, ckey, me, pub)
    return jsonify(_covering_item(pub, saved, ckey))


@bp.post("/api/relief/absences/<id>/covers/<path:ckey>/acknowledge")
@need("relief")
def cover_acknowledge(id, ckey):
    """the relief teacher acknowledges (once: again is the same answer, no new history entry)"""
    def do(r, x, c, me, b, pub, reached):
        if _cover.state(r, x, c) == "acknowledged": return None
        saved, first = _cover.acknowledge_once(r["id"], ckey, me, links=_links_or_none(pub, _cal(pub)), reached=reached)
        if not first: r.update(saved)            # acknowledged on Telegram since r was read: answered as it is, nothing to write down
        return saved if first else None
    return _yours(id, ckey, do, "ack")


@bp.post("/api/relief/absences/<id>/covers/<path:ckey>/ask-change")
@need("relief")
def ask_change(id, ckey):
    """{why}: a line; the relief stays theirs until the team acts, and a new pick is made at once (fill.soon for this
    absence alone, with force, after the save); the history entry never holds the why"""
    return _yours(id, ckey, lambda r, x, c, me, b, pub, reached: _cover.ask_change(r["id"], ckey, b.get("why"), me, links=_links_or_none(pub, _cal(pub)), reached=reached),
                  "change")


# ---- the load tracker (relief.team)
def _load_window(pub, cal):
    """-> (the date whose week is read, the term or None): ?term=<name> (the week of today, kept inside that term), else
    ?week=YYYY-MM-DD (today when left out) and the term holding it"""
    if not cal.get("terms"): raise ValueError(_lessons.NO_CALENDAR)
    name = request.args.get("term")
    if name not in (None, ""):
        term = next((t for t in cal["terms"] if t.get("name") == name), None)
        if term is None: raise ValueError(TERM)
        a, b = datetime.date.fromisoformat(term["start"]), datetime.date.fromisoformat(term["end"])
        return min(max(_lessons.today(), a), b), term
    d = _day(request.args.get("week"), _lessons.today())
    return d, term_of(cal, d)


def _term_dates(term):
    if not term: return []
    d, last, out = datetime.date.fromisoformat(term["start"]), datetime.date.fromisoformat(term["end"]), []
    while d <= last: out.append(d); d += datetime.timedelta(days=1)
    return out


def _load(pub):
    """-> (the date, the term, rows): every teacher with teaching, relief or exam and event duties that week, or relief that
    term: teaching (periods that week), relief (periods that week), exams (periods more that week for exam duties and events,
    less those of lessons that stop; may be below 0), week (week so far: the three), term (relief periods that term), changes
    (requests to change they made on lessons that term), counted as the free-then counts do (free.relief_periods and
    week_so_far: approved or waiting, a request to change's new pick too, never a cancelled absence, a lesson no longer
    needed or one an exam or event stops)"""
    settings = _settings.load(pub)
    cal, fat_role = settings["calendar"], settings.get("fat_role") or ""
    d, term = _load_window(pub, cal)
    week = _free._week_dates(cal, ((pub or {}).get("model") or {}).get("days") or [], d)
    tdates = _term_dates(term)
    records, changes, within = _absences.all_records(), {}, {x.isoformat() for x in tdates}
    links = _links_or_none(pub, cal)
    for r in records:
        for x in r.get("lessons") or []:
            if x.get("date") not in within: continue
            for h in list(x.get("history") or []) + [h for c in x.get("parts") or [] for h in c.get("history") or []]:
                if h.get("what") == "asked to change": changes[h.get("who")] = changes.get(h.get("who"), 0) + 1
    rows = []
    for p in _accounts.listing(pub):
        if p["staff_only"]: continue
        name = p["name"]
        teaching, relief = _lessons.teaching_periods(pub, cal, name, d), _free.relief_periods(records, name, week, links=links)
        n = _free.relief_periods(records, name, tdates, links=links) if tdates else 0
        exams = links.week_change(name, week) if links is not None else 0
        if teaching or relief or exams or n:
            rows.append(dict(name=name, depts=list(p["depts"]), fat=bool(fat_role) and p.get("role") == fat_role, teaching=teaching,
                             relief=relief, exams=exams, week=teaching + relief + exams, term=n, changes=changes.get(name, 0)))
    return d, term, rows


def _window_out(d, term):
    mon, fri = week_of(d)
    return dict(week=dict(start=mon.isoformat(), end=fri.isoformat()), term=dict(name=term["name"], start=term["start"], end=term["end"]) if term else None)


@bp.get("/api/relief/load")
@need("relief")
def load():
    """the load tracker: dict(week={start, end}, term={name, start, end} or None, rows=[{name, depts, fat, teaching, relief,
    exams, week, term, changes}]) in relief's order (by first department, none last, then name); relief.team"""
    pub, me, err = _gate(*TEAM)
    if err: return err
    try: d, term, rows = _load(pub)
    except ValueError as e: return _refusal(e)
    return jsonify(rows=rows, **_window_out(d, term))


@bp.get("/api/relief/load/<name>")
@need("relief")
def load_one(name):
    """every relief that books name in the term (?week= or ?term= as /load): reliefs=[{id, ckey, date, p, n, start, end,
    lesson, absent, state ("new pick" for a request to change's new pick, "not happening" when an exam or event stops the
    lesson: not counted in the load), by, reason (the pick's), approved_by}] by date
    and period; relief.team"""
    pub, me, err = _gate(*TEAM)
    if err: return err
    try:
        _on_staff(pub, name)
        d, term = _load_window(pub, _cal(pub))
    except ValueError as e: return _refusal(e)
    within, out = {x.isoformat() for x in _term_dates(term)}, []
    links = _links_or_none(pub, _cal(pub))
    for r in _absences.all_records():
        if r.get("cancelled"): continue
        for x in r.get("lessons") or []:
            if x.get("date") not in within or not x.get("needed"): continue
            for i, c in enumerate(_cover.covers(x)):
                if name not in _cover.booked(c): continue
                mine, off = c.get("relief") == name, _cover.stopped(links, x)
                pk = _cover.pick_of(r, c) if mine else _cover.new_pick(c)
                start, end = _times(pub, x, c)
                out.append(dict(id=r["id"], ckey=_cover.cover_key(x, i), date=x["date"], p=int(c["p"]), n=int(c.get("n") or 1), start=start, end=end,
                                lesson=f"{_class_group(x)} {_periods_text(c)}", absent=r["teacher"], state="not happening" if off else _cover.state(r, x, c) if mine else "new pick",
                                by=(pk or {}).get("by"), reason=(pk or {}).get("reason") or "",
                                approved_by=(c.get("approved") or {}).get("by") if mine else None))
    out.sort(key=lambda v: (v["date"], v["p"], v["absent"]))
    return jsonify(name=name, reliefs=out, **_window_out(d, term))


@bp.get("/api/relief/load.csv")
@need("relief")
def load_csv():
    """the load tracker's rows as a spreadsheet (every cell through _cell); relief.team"""
    pub, me, err = _gate(*TEAM)
    if err: return err
    try: d, term, rows = _load(pub)
    except ValueError as e: return _refusal(e)
    buf = io.StringIO(); w = csv.writer(buf)
    w.writerow(LOAD_COLUMNS)
    for x in rows:
        w.writerow([_cell(v) for v in (x["name"], ", ".join(x["depts"]), "Yes" if x["fat"] else "", x["teaching"], x["relief"])]
                   + [x["exams"]] + [_cell(v) for v in (x["week"], x["term"], x["changes"])])          # exams may be below 0: a number, never a formula
    name = f"relief load {week_of(d)[0].isoformat()}.csv"
    return Response("﻿" + buf.getvalue(), mimetype="text/csv", headers={"Content-Disposition": f'attachment; filename="{name}"'})

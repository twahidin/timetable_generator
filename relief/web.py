"""The relief request routes (stage 2): a teacher asks for relief and sets work for each lesson; management and the
relief team plan relief for a colleague and choose relief teachers; the absent teacher acknowledges, sets work or
cancels; the relief team sees What's in. Registered from app.py after init(has=..., me=..., role=...).

Every route answers 401 {"error": "Please sign in again."} without a person signed in with their own code, 409 with
NO_PUB when nothing is published, 403 {"error": sentence} without the right and 400 {"error": sentence} on a refusal.
The absence reason reaches only the absent teacher, whoever planned it, relief.plan and relief.team: every route that
answers a record or one of its files asks _record first, and the lists are the caller's own, the caller's planned ones,
or (relief.team) everything. The remarks are for the relief team: a record sent to someone who is only its absent
teacher (not its sender, not relief.plan, not relief.team) leaves them out (_out).

Hand-over to the accounts work: every permission question here goes through has(right), passed in with
init(has=..., me=..., role=...); app.py passes relief_has. When the accounts work merges, init(has=...) receives its
`has`: the right names (relief, relief.plan, relief.team, relief.settings, relief.save) are already the same. The relief
team's right to change any absence (not needed, needed again, cancel) is asked here too, has("relief.team"), and passed
into relief.absences as team=...; relief.absences never reads the settings' team list itself.

Bodies: POST /api/relief/absences takes relief.absences.new's fields (teacher: yourself when left out; dates, periods,
reason, reason_text, remarks, reporting_officer, lessons=[{key, needed, relief, work}]); PUT …/work takes the work
{text, link, files: [{id, name}], known: [the file ids the page started from]} (a missing or other body is refused,
never read as "no work"); POST …/not-needed and …/cancel take {why}; PUT …/relief takes {relief: a name, or
null to take the choice off}; POST …/files takes one file in the multipart field "file"; POST /api/relief/absences/seen
takes {at}: the as_of the What's in list answered (now when left out). Periods are 0-based, as in the records."""
import csv, datetime, io, os, threading
from zoneinfo import ZoneInfo

from flask import Blueprint, Response, current_app, jsonify, request, send_file

import store
from exams.days import bounds, hhmm
from relief import absences as _absences
from relief import files as _files
from relief import free as _free
from relief import lessons as _lessons
from relief import settings as _settings
from relief.codes import _cell
from relief.people import people as _people

bp = Blueprint("relief_web", __name__)
NO_PUB = "Publish the timetable first: relief reads the teachers from it."
SIGN_IN = "Please sign in again."
PLAN_ONLY = "Only management and the relief team plan relief for a colleague."
CHOOSE_ONLY = "Only management and the relief team choose relief teachers."
TEAM_ONLY = "Only the relief team can open What's in."
NOT_YOURS = "This absence is not yours to open."
GONE = "That absence is not there any more."
NO_FILE = "That file is not there any more."
PERIODS = "Choose the periods again."
DATES = "Choose the dates again."
ENTIRE = "Entire Class"
COLUMNS = ["Date", "Absent", "Class / group", "Periods", "Time", "Relief teacher", "Remarks", "Set by"]
SEEN = os.path.join(store.DATA, "relief", "seen.json")
_SEEN_LOCK = threading.Lock()
BAD_INPUT = (TypeError, KeyError, AttributeError)     # malformed JSON never gives a 500
SLACK = 64 * 1024                                      # room for the multipart lines around one file

_has = _me = _role = None


def init(has, me, role):
    """has(right) -> bool; me(pub) -> the person signed in with their own code (dict with name) or None; role() -> the session's role"""
    global _has, _me, _role
    _has, _me, _role = has, me, role


# ---- helpers
def _gate(right="relief", refused=None):
    """-> (pub, the person's name, None) or (None, None, the refusing answer)"""
    if _role() != "staff": return None, None, ({"error": SIGN_IN}, 401)
    pub = store.published()
    if not pub: return None, None, ({"error": NO_PUB}, 409)
    p = _me(pub)
    if p is None or not _has("relief"): return None, None, ({"error": SIGN_IN}, 401)
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
    """what approved exams and events mean for relief (exams.relief_links), imported here to keep the modules apart"""
    from exams.relief_links import Links
    return Links.load(pub, cal)


def _out(r, pub, me, cal=None):
    """the record as it is sent: lessons marked changed (matches_now), the remarks left out for someone who is only its absent teacher"""
    v = _absences.matches_now(r, pub, cal if cal is not None else _cal(pub))
    if me == r.get("teacher") and me != r.get("by") and not _sees_all(): v.pop("remarks", None)
    return v


def _views(records, pub, me):
    cal = _cal(pub)
    return [_out(r, pub, me, cal) for r in records]


def _on_staff(pub, settings, name):
    """raises the sentence new() says when name is not someone relief knows"""
    if not isinstance(name, str) or name not in {p["name"] for p in _people(pub, settings["extra_staff"])}:
        raise ValueError(f"{name if isinstance(name, str) and name else 'That person'} is not on the published timetable or the staff list.")


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
        _on_staff(pub, settings, teacher)
        dates = _absences._iso_dates([x.strip() for x in (request.args.get("dates") or "").split(",") if x.strip()], _lessons.today())
        periods = _period_range(pub, request.args.get("from"), request.args.get("to"))
        records = _absences.all_records()
        by_date = {d.isoformat(): [_iso(dict(x, others=_free.there_then(records, x["others"], d, x["p"], x["n"])))       # as new() decides
                                   for x in _lessons.on_date(pub, settings["calendar"], teacher, d, periods=periods)] for d in dates}
        every = _periods(pub)
    except ValueError as e: return _refusal(e)
    return jsonify(lessons=[x for v in by_date.values() for x in v], by_date=by_date, periods=every)


@bp.get("/api/relief/free")
def free():
    """who is free for one lesson (its key) of the absent teacher, grouped and ranked; relief.plan"""
    pub, me, err = _gate("relief.plan", CHOOSE_ONLY)
    if err: return err
    absent, key = request.args.get("absent") or "", request.args.get("key") or ""
    try:
        settings = _settings.load(pub)
        _on_staff(pub, settings, absent)
        try: date = datetime.date.fromisoformat(key.split("/")[0])
        except ValueError: raise ValueError(_absences.CHANGED)
        lesson = next((x for x in _lessons.on_date(pub, settings["calendar"], absent, date) if x["key"] == key), None)
        if lesson is None: raise ValueError(_absences.CHANGED)
        got = _free.free_then(pub, settings, _absences.all_records(), lesson, absent, links=_links(pub, settings["calendar"]))
    except ValueError as e: return _refusal(e)
    return jsonify(got)


@bp.get("/api/relief/people")
def people():
    """everyone relief knows, for the reporting officer and absent teacher pickers: [{name, depts}]"""
    pub, me, err = _gate()
    if err: return err
    return jsonify([dict(name=p["name"], depts=p["depts"]) for p in _people(pub, _settings.load(pub)["extra_staff"])])


# ---- absences
@bp.post("/api/relief/absences")
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
    try: r = _absences.new(dict(data, teacher=teacher), pub, me, how, may_choose=plan)
    except ValueError as e: return _refusal(e)
    except BAD_INPUT as e: return _odd(e, "sending an absence")
    return jsonify(_out(r, pub, me))


@bp.get("/api/relief/absences/mine")
def mine():
    pub, me, err = _gate()
    if err: return err
    return jsonify(absences=_views(_absences.for_teacher(me), pub, me))


@bp.get("/api/relief/absences/planned")
def planned():
    pub, me, err = _gate("relief.plan", PLAN_ONLY)
    if err: return err
    return jsonify(absences=_views(_absences.planned_by(me), pub, me))


def _seen_at(name):
    d = store.read_json(SEEN, {})
    return _time(d.get(name)) if isinstance(d, dict) else None


@bp.get("/api/relief/absences")
def whats_in():
    """every absence, newest first; new = submitted at or after the time this person last marked What's in as seen
    (never: all new). Reads only: the page posts /seen after showing the list."""
    pub, me, err = _gate("relief.team", TEAM_ONLY)
    if err: return err
    since, as_of = _seen_at(me), _clock().isoformat()
    out = []
    for v in _views(_absences.all_records(), pub, me):
        at = _time(v.get("at"))
        v["new"] = since is None or at is None or at >= since
        out.append(v)
    return jsonify(absences=out, new_since=since.isoformat() if since else None, as_of=as_of)


@bp.post("/api/relief/absences/seen")
def seen():
    """records when this person last saw What's in: the as_of posted back, never later than now"""
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
def one(id):
    pub, me, err = _gate()
    if err: return err
    r, err = _record(id, me)
    if err: return err
    return jsonify(_out(r, pub, me))


def _change(id, do, right=None, refused=None):
    """open the absence (403/404 as _record), check the right, do(record, me, pub, body) -> the saved record"""
    pub, me, err = _gate()
    if err: return err
    r, err = _record(id, me)
    if err: return err
    if right and not _has(right): return {"error": refused}, 403
    try: r = do(r, me, pub, _body())
    except ValueError as e: return _refusal(e)
    except BAD_INPUT as e: return _odd(e, "changing an absence")
    return jsonify(_out(r, pub, me))


@bp.post("/api/relief/absences/<id>/acknowledge")
def acknowledge(id):
    return _change(id, lambda r, me, pub, b: _absences.acknowledge(r["id"], me))


@bp.put("/api/relief/absences/<id>/lessons/<path:key>/work")
def work(id, key):
    """a body that is not the work with its files and known (none, not JSON, {}) is refused by set_work: it never clears the work"""
    return _change(id, lambda r, me, pub, b: _absences.set_work(r["id"], key, b, me))


@bp.post("/api/relief/absences/<id>/lessons/<path:key>/not-needed")
def not_needed(id, key):
    return _change(id, lambda r, me, pub, b: _absences.not_needed(r["id"], key, b.get("why"), me, team=_has("relief.team")))


@bp.post("/api/relief/absences/<id>/lessons/<path:key>/needed")
def needed(id, key):
    return _change(id, lambda r, me, pub, b: _absences.needed_again(r["id"], key, me, team=_has("relief.team")))


def _choose(r, key, me, pub, b):
    name = b.get("relief")
    if name is not None and not isinstance(name, str): raise ValueError(_absences.WRONG)
    return _absences.choose(r["id"], key, name or None, me, pub)


@bp.put("/api/relief/absences/<id>/lessons/<path:key>/relief")
def relief(id, key):
    return _change(id, lambda r, me, pub, b: _choose(r, key, me, pub, b), right="relief.plan", refused=CHOOSE_ONLY)


@bp.post("/api/relief/absences/<id>/cancel")
def cancel(id):
    return _change(id, lambda r, me, pub, b: _absences.cancel(r["id"], b.get("why"), me, team=_has("relief.team")))


# ---- work files
@bp.post("/api/relief/absences/<id>/files")
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
def download(id, file):
    """the file as an attachment with the name it was given, for whoever may open the absence"""
    pub, me, err = _gate()
    if err: return err
    r, err = _record(id, me)
    if err: return err
    p = _files.path(r["id"], file)
    if not p: return {"error": NO_FILE}, 404
    names = [f.get("name") for x in r.get("lessons") or [] for f in (x.get("work") or {}).get("files") or [] if f.get("id") == file]
    resp = send_file(p, as_attachment=True, download_name=(names[0] if names and names[0] else "file" + os.path.splitext(p)[1]))
    resp.headers["Cache-Control"] = "private, no-store"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    return resp


# ---- the planned relief download
def _day(v, default):
    if v in (None, ""): return default
    try: return datetime.date.fromisoformat(v)
    except ValueError: raise ValueError(DATES)


def _class_group(x):
    """'1B, 1A Maths (G1)': the classes and subject, and the group unless it is the whole class (as the pages' title)"""
    g = x.get("group") or ""
    head = " ".join(v for v in (", ".join(x.get("classes") or []), x.get("subject") or "") if v)
    return head + (f" ({g})" if g and g != ENTIRE else "")


def _periods_text(x):
    p, n = int(x["p"]), int(x.get("n") or 1)
    return f"P{p + 1}" if n == 1 else f"P{p + 1}–P{p + n}"


@bp.get("/api/relief/planned.csv")
def planned_csv():
    """the lessons needing relief in every absence not cancelled, planned or asked, dated start..end (today when left out),
    so a day's sheet is complete; Set by = whoever sent it; never the reason"""
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
            if start <= d <= end: rows.append((d, int(x["p"]), r["teacher"], x, r))
    rows.sort(key=lambda t: t[:3])
    buf = io.StringIO(); w = csv.writer(buf)
    w.writerow(COLUMNS)
    for d, p, teacher, x, r in rows:
        group = _class_group(x)
        time = f"{x['start']}–{x['end']}" if x.get("start") and x.get("end") else ""
        w.writerow([_cell(v) for v in (d.isoformat(), teacher, group, _periods_text(x), time, x.get("relief") or "Not chosen yet",
                                       r.get("remarks") or "", r.get("by") or "")])
    name = f"planned relief {start.isoformat()}" + (f" to {end.isoformat()}" if end != start else "") + ".csv"
    return Response("﻿" + buf.getvalue(), mimetype="text/csv", headers={"Content-Disposition": f'attachment; filename="{name}"'})

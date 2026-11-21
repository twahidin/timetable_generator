"""Absence records: a teacher's absence (asked by them or planned by someone else), its lessons, work and relief.
One JSON file each under DATA/relief/absences."""
import datetime, os, secrets, threading
from zoneinfo import ZoneInfo

import store
from relief import files as _files
from relief import free as _free
from relief import lessons as _lessons
from relief import settings as _settings
from relief.people import people as _people

DIR = os.path.join(store.DATA, "relief", "absences")
_LOCK = threading.Lock()
REASONS = ("Medical", "Child sick", "Course", "Other")
CHANGED = "Your timetable has changed since you opened this page. Open it again."
WRONG = "Check the absence and try again."
NOT_YOURS = "You cannot change this absence."
CANCELLED = "This absence was cancelled."
NO_FILES_YET = "Add files after the absence is sent."
SAY_WHY = "Say why in a line."
PAST_LESSON = "This lesson is in the past."
PAST_ABSENCE = "This absence is in the past."
MAX_DATES, MAX_TEXT, MAX_LINK = 10, 2000, 500


def _path(id):
    id = str(id)
    if not id.isalnum(): raise ValueError(WRONG)
    return os.path.join(DIR, f"{id}.json")


def _now():
    return datetime.datetime.now(ZoneInfo(os.environ.get("SCHOOL_TZ") or "Asia/Singapore")).isoformat(timespec="seconds")


def _say(d):
    return f"{d:%a} {d.day} {d:%b}"


def load(id):
    try: p = _path(id)
    except ValueError: return None
    r = store.read_json(p, None)
    return r if isinstance(r, dict) and r.get("id") else None


def all_records():
    out = []
    if os.path.isdir(DIR):
        for f in os.listdir(DIR):
            if f.endswith(".json"):
                r = store.read_json(os.path.join(DIR, f), None)
                if isinstance(r, dict) and r.get("id"): out.append(r)
    out.sort(key=lambda r: r.get("at") or "", reverse=True)
    return out


def for_teacher(name):
    return [r for r in all_records() if r.get("teacher") == name]


def planned_by(name):
    return [r for r in all_records() if r.get("how") == "planned" and r.get("by") == name]


def _save(r):
    os.makedirs(DIR, exist_ok=True)
    store.write_json(_path(r["id"]), r)


def _pub(pub):
    return pub if pub is not None else store.published()


def _check_work(work, allow_files=False):
    """-> clean dict(text, link, files); files are checked by the caller"""
    work = work if isinstance(work, dict) else {}
    text, link = work.get("text") or "", work.get("link") or ""
    if not isinstance(text, str) or not isinstance(link, str): raise ValueError(WRONG)
    text, link = text.strip(), link.strip()
    if link and (not link.lower().startswith(("http://", "https://")) or len(link) > MAX_LINK):
        raise ValueError("A link starts with http:// or https://.")
    if len(text) > MAX_TEXT: raise ValueError("Keep the work under 2000 characters.")
    files = work.get("files") or []
    if not isinstance(files, list): raise ValueError(WRONG)
    return dict(text=text, link=link, files=files)


def _int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _iso_dates(v, today):
    bad = ValueError("Choose up to 10 school days, today or later.")
    if not isinstance(v, (list, tuple)) or not v or len(v) > MAX_DATES: raise bad
    out = []
    for x in v:
        try: d = x if isinstance(x, datetime.date) else datetime.date.fromisoformat(str(x))
        except ValueError: raise bad
        if not isinstance(x, (str, datetime.date)) or d < today: raise bad
        if d not in out: out.append(d)
    return sorted(out)


def _no_overlap(records, teacher, lessons):
    """refuse when another absence of the teacher, not cancelled, has a needed lesson overlapping one of lessons (dicts with ISO dates)"""
    for r in records:
        if r.get("cancelled") or r.get("teacher") != teacher: continue
        for old in r["lessons"]:
            if not old.get("needed"): continue
            for x in lessons:
                if x["date"] == old["date"] and _free._overlap(x["p"], x["n"], old["p"], old["n"]):
                    raise ValueError(f"{r['by']} has already sent an absence for {teacher} on {_say(datetime.date.fromisoformat(x['date']))}.")


def new(data, pub, by, how, may_choose=False) -> dict:
    pub = _pub(pub)
    if how not in ("asked", "planned") or not isinstance(data, dict): raise ValueError(WRONG)
    settings = _settings.load(pub)
    cal = settings["calendar"]
    staff = {p["name"] for p in _people(pub, settings["extra_staff"])}
    teacher = data.get("teacher")
    if not isinstance(teacher, str) or teacher not in staff:
        raise ValueError(f"{teacher if isinstance(teacher, str) and teacher else 'That person'} is not on the published timetable or the staff list.")
    dates = _iso_dates(data.get("dates"), _lessons.today())
    for d in dates: _lessons.on_date(pub, cal, teacher, d)          # a date that is not a school day, or no calendar, raises its sentence
    periods = data.get("periods")
    if periods is not None:
        np = ((pub.get("model") or {}).get("NP"))
        ok = isinstance(periods, (list, tuple)) and len(periods) == 2 and all(_int(x) for x in periods) and 0 <= periods[0] <= periods[1]
        if ok and _int(np) and periods[1] >= np: ok = False
        if not ok: raise ValueError("Choose the periods again.")
        periods = [periods[0], periods[1]]
    reason, text = data.get("reason"), data.get("reason_text") or ""
    if reason not in REASONS or not isinstance(text, str) or len(text.strip()) > 200 or (reason == "Other" and not text.strip()):
        raise ValueError("Choose a reason; for Other, say why in a line.")
    remarks = data.get("remarks") or ""
    if not isinstance(remarks, str) or len(remarks.strip()) > 300: raise ValueError("Keep the remarks under 300 characters.")
    officer = data.get("reporting_officer") or ""
    if how == "asked" and (not isinstance(officer, str) or officer not in staff): raise ValueError("Choose your reporting officer.")
    if not isinstance(officer, str) or (officer and officer not in staff): officer = ""
    asked = data.get("lessons") or []
    if not isinstance(asked, list) or not all(isinstance(x, dict) for x in asked): raise ValueError(WRONG)
    mine = {}
    for d in dates:
        for x in _lessons.on_date(pub, cal, teacher, d, periods=tuple(periods) if periods else None):
            mine[x["key"]] = x
    asks = {}
    for x in asked:
        if x.get("key") not in mine: raise ValueError(CHANGED)
        asks[x["key"]] = x
    with _LOCK:
        records = all_records()
        built = []
        for key, x in mine.items():
            a = asks.get(key, {})
            # a shared lesson needs no relief unless the client says so, but only while one of its other teachers is there:
            # others keeps those not away then, and with none there it is an ordinary lesson (needed unless the client says not).
            # An absence sent earlier that said "{them} is there" is left as it is; this one covers the lesson.
            there = _free.there_then(records, x["others"], x["date"], x["p"], x["n"])
            if there:
                needed = a.get("needed") is True
                not_needed = None if needed else dict(by="app", why=f"{' and '.join(there)} is there")
            else:
                needed = a.get("needed") is not False
                not_needed = None if needed else dict(by=by, why="Not needed")
            built.append(dict(x, date=x["date"].isoformat(), others=there, needed=needed, not_needed=not_needed, relief=None, relief_by=None,
                              work=dict(text="", link="", files=[]), _ask=a))
        if not any(x["needed"] for x in built): raise ValueError("There are no lessons to cover in that time.")
        _no_overlap(records, teacher, [x for x in built if x["needed"]])
        pending = dict(teacher=teacher, dates=[d.isoformat() for d in dates], periods=periods, cancelled=None, lessons=[])
        if not may_choose and any(x["needed"] and x["_ask"].get("relief") for x in built):
            raise ValueError("Only management and the relief team choose relief teachers.")     # before free_then: no probing who is free
        for x in built:
            name = x["_ask"].get("relief")
            if name and x["needed"]:
                lesson = dict(x, date=datetime.date.fromisoformat(x["date"]))
                free = _free.free_then(pub, settings, records + [pending], lesson, teacher)
                if name not in [p["name"] for g in free["groups"] for p in g["people"]]:
                    raise ValueError(f"{name} is not free for {' and '.join(x['classes'])} {x['subject']} then.")
                x["relief"], x["relief_by"] = name, by
            pending["lessons"].append(x)
        for x in built:      # the work checks come last
            x["work"] = _check_work(x.pop("_ask").get("work"))
            if x["work"]["files"]: raise ValueError(NO_FILES_YET)
        r = dict(id=secrets.token_hex(6), teacher=teacher, dates=pending["dates"], periods=periods, reason=reason, reason_text=text.strip(),
                 remarks=remarks.strip(), reporting_officer=officer, by=by, how=how, at=_now(), acknowledged=None, cancelled=None,
                 lessons=pending["lessons"])
        _save(r)
    return r


def _editable(id):
    r = load(id)
    if r is None: raise ValueError(WRONG)
    if r.get("cancelled"): raise ValueError(CANCELLED)
    return r


def _lesson(r, key):
    for x in r["lessons"]:
        if x["key"] == key: return x
    raise ValueError(CHANGED)


def _owner(r, by):
    return by == r["teacher"] or (r["how"] == "planned" and by == r["by"])


def _past(x):
    """refuse a change to a lesson dated before today (the school's date)"""
    if datetime.date.fromisoformat(x["date"]) < _lessons.today(): raise ValueError(PAST_LESSON)


def _ids(v):
    """a list of file ids (strings), or WRONG"""
    if not isinstance(v, list) or len(v) > 50 or not all(isinstance(f, str) for f in v): raise ValueError(WRONG)
    return set(v)


def acknowledge(id, by):
    with _LOCK:
        r = _editable(id)
        if by != r["teacher"] or r["how"] != "planned": raise ValueError(f"Only {r['teacher']} can acknowledge this.")
        if r["acknowledged"]: raise ValueError("This was acknowledged already.")
        r["acknowledged"] = dict(at=_now())
        _save(r)
    return r


def set_work(id, key, work, by):
    """work = {text, link, files: [{id, name}], known: [the file ids on the lesson when the caller's page read it]}; a file on
    the lesson now that is not in known (someone else added it meanwhile) is kept; a file deleted is one the caller knew,
    took off, and no lesson of the absence lists any more"""
    if not isinstance(work, dict) or not isinstance(work.get("files"), list): raise ValueError(WRONG)
    known = _ids(work.get("known"))
    with _LOCK:
        r = _editable(id)
        if not _owner(r, by): raise ValueError(NOT_YOURS)
        x = _lesson(r, key)
        _past(x)
        w = _check_work(work)
        if len(w["files"]) > _files.PER_LESSON: raise ValueError("A lesson can have at most 5 files.")
        kept = []
        for f in w["files"]:
            fid = f.get("id") if isinstance(f, dict) else f
            p = _files.path(id, fid)
            if not p: raise ValueError(CHANGED)
            if fid in [k["id"] for k in kept]: continue
            old = next((o for o in x["work"]["files"] if o["id"] == fid), None)
            name = old["name"] if old else _files.clean_name(f.get("name") if isinstance(f, dict) else "")
            ext = os.path.splitext(p)[1]      # the name always ends with the stored file's own extension
            kept.append(dict(id=fid, name=name if name.lower().endswith(ext.lower()) else _files.fit(name, ext), size=os.path.getsize(p)))
        sent = {k["id"] for k in kept}
        kept += [o for o in x["work"]["files"] if o["id"] not in known and o["id"] not in sent]
        if len(kept) > _files.PER_LESSON: raise ValueError("A lesson can have at most 5 files.")
        before = {o["id"] for o in x["work"]["files"]}
        x["work"] = dict(text=w["text"], link=w["link"], files=kept)
        _save(r)
        still = {o["id"] for l in r["lessons"] for o in l["work"]["files"]}
        for fid in before - still: _files.delete(id, fid)
    return r


def _may_change(r, by, team):
    """the absent teacher, its planner, or (team: the caller has relief.team, asked by relief/web.py through has) the relief team"""
    if not _owner(r, by) and not team: raise ValueError(NOT_YOURS)


def not_needed(id, key, why, by, *, team=False):
    why = why.strip() if isinstance(why, str) else ""
    with _LOCK:
        r = _editable(id)
        _may_change(r, by, team)
        x = _lesson(r, key)
        _past(x)
        if not 1 <= len(why) <= 200: raise ValueError(SAY_WHY)
        x["needed"], x["not_needed"], x["relief"], x["relief_by"] = False, dict(by=by, why=why), None, None
        _save(r)
    return r


def needed_again(id, key, by, *, team=False):
    with _LOCK:
        r = _editable(id)
        _may_change(r, by, team)
        x = _lesson(r, key)
        _past(x)
        _no_overlap([o for o in all_records() if o["id"] != r["id"]], r["teacher"], [x])
        x["needed"], x["not_needed"] = True, None
        _save(r)
    return r


def choose(id, key, relief_name, by, pub):
    """relief_name None or "" takes the choice off; the caller checks the relief.plan right"""
    pub = _pub(pub)
    with _LOCK:
        r = _editable(id)
        x = _lesson(r, key)
        _past(x)
        if not x["needed"]: raise ValueError("This lesson does not need relief.")
        if not relief_name:
            x["relief"], x["relief_by"] = None, None
        else:
            free = _free.free_then(pub, _settings.load(pub), all_records(), dict(x, date=datetime.date.fromisoformat(x["date"])), r["teacher"])
            if relief_name not in [p["name"] for g in free["groups"] for p in g["people"]]:
                raise ValueError(f"{relief_name} is not free for {' and '.join(x['classes'])} {x['subject']} then.")
            x["relief"], x["relief_by"] = relief_name, by
        _save(r)
    return r


def cancel(id, why, by, *, team=False):
    """refused once every date of the absence is before today; an absence with a date still to come is cancelled whole"""
    why = why.strip() if isinstance(why, str) else ""
    with _LOCK:
        r = _editable(id)
        _may_change(r, by, team)
        if all(datetime.date.fromisoformat(d) < _lessons.today() for d in r["dates"]): raise ValueError(PAST_ABSENCE)
        if not 1 <= len(why) <= 200: raise ValueError(SAY_WHY)
        r["cancelled"] = dict(at=_now(), by=by, why=why)
        _save(r)
    return r


def matches_now(record, pub, cal):
    """the record with each lesson marked changed when the teacher no longer has it on the published timetable; a lesson
    dated before today is not read again (changed False): it is history, and What's in stays quick over a year of records"""
    today, out = _lessons.today(), dict(record)
    out["lessons"] = [dict(x, changed=datetime.date.fromisoformat(x["date"]) >= today and not _lessons.still_there(pub, cal, record["teacher"], x))
                      for x in record["lessons"]]
    return out

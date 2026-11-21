"""Exam and test schedules: make, check, save, list. One JSON file each under DATA/exams/schedules."""
import datetime, os, secrets, threading

import relief.people
import relief.settings
import store
from exams import approval as _approval
from exams import days as _days
from exams import papers as _papers

DIR = os.path.join(store.DATA, "exams", "schedules")
_LOCK = threading.RLock()   # one process (gunicorn: one worker, threads): held by a route from loading a schedule to saving it
WRONG = "Check the exam and try again."
NO_CALENDAR = "Set the school calendar in Relief settings first: exams need it to know which timetable day a date is."


def editing():
    """the lock a route holds from loading a schedule to saving it (and the delete), so two saves at once never undo each
    other: an approve during a Make is not lost when the Make saves the copy it loaded before"""
    return _LOCK


def _path(id):
    id = str(id)
    if not id.isalnum(): raise ValueError(WRONG)
    return os.path.join(DIR, f"{id}.json")


def _now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def _int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _texts(v):
    return isinstance(v, list) and all(isinstance(x, str) for x in v)


KINDS = ("exam", "test")
EVENT = "event"
GOING_BY = ("form teachers", "teachers then", "department", "people")
SUPERVISION = ("invigilators", "lesson")
WHO = ("level", "groups", "students")
SEATING = dict(order=("class", "name"), shared=("levels", "papers", "blocks"), spacing=("every", "gap"), home_rooms=(True, False))


def _time_or_none(v, sentence):
    """a stored time: None, or 24-hour HH:MM"""
    if v in (None, ""):
        return None
    try:
        return _days.hhmm(_days.minutes(v))
    except ValueError:
        raise ValueError(sentence)


def _all():
    out = []
    if os.path.isdir(DIR):
        for f in os.listdir(DIR):
            if f.endswith(".json"):
                s = store.read_json(os.path.join(DIR, f), None)
                if isinstance(s, dict) and s.get("id"): out.append(s)
    return out


def new(kind, name, levels, start, end, by, pub=None) -> dict:
    pub = pub if pub is not None else store.published()
    students = {s["id"] for s in ((pub or {}).get("model") or {}).get("students") or []}
    access = []
    mine = [s for s in _all() if s.get("access")]
    if mine:
        latest = max(mine, key=lambda s: s.get("created_at") or "")
        access = [dict(a) for a in latest["access"] if isinstance(a, dict) and a.get("student") in students]
    test = kind == "test"
    return dict(id=secrets.token_hex(4), kind=kind, name=name, levels=list(levels), classes=[], start=start, end=end, days={},
                times=dict(report="07:30", min_break=20, max_papers=2), papers=[], access=access,
                seating=dict(order="class", shared="levels", spacing="every", home_rooms=True),
                supervision="lesson" if test else "invigilators", scripts="", pins=dict(rooms={}, duties={}), use_anyway=[], made=None,
                status="draft", log=[], approved=None, note="", created_at=_now(), created_by=by, saved_at=None, saved_by=None)


def new_event(name, levels, classes, start, end, by, in_charge) -> dict:
    """a new event: a schedule of kind "event" (no papers, seats or duties of its own); reads no file"""
    return dict(id=secrets.token_hex(4), kind=EVENT, name=name, levels=list(levels), classes=list(classes), start=start, end=end,
                days={}, in_charge=in_charge, where="", venues=[], going=[], going_by="people", duties=[], made=None,
                status="draft", log=[], approved=None, note="", created_at=_now(), created_by=by, saved_at=None, saved_by=None)


def place(s) -> str:
    """where an event is: the words typed, else its venues, else nothing"""
    return str(s.get("where") or "").strip() or ", ".join(s.get("venues") or [])


def _named(s, noun):
    """the name must not be empty"""
    if not s["name"].strip(): raise ValueError("Give the %s a name." % noun)


def _lists_and_pick(s):
    if not _texts(s["levels"]) or not _texts(s["classes"]): raise ValueError(WRONG)
    if not s["levels"] and not s["classes"]: raise ValueError("Pick at least one level or class.")


def _when(s, model, noun):
    """the dates, the days and the levels and classes against the published timetable: shared by exams and events"""
    try:
        a, b = datetime.date.fromisoformat(s["start"]), datetime.date.fromisoformat(s["end"])
    except ValueError: raise ValueError(WRONG)
    if b < a: raise ValueError("Check the dates: the last day is before the first.")
    if (b - a).days + 1 > 31: raise ValueError("An %s can cover at most 31 days." % noun)
    bnds = _days.bounds(model)
    starts, ends = {x for x, _ in bnds}, {y for _, y in bnds}
    for date, e in s["days"].items():
        if not isinstance(e, dict): raise ValueError(WRONG)
        try: datetime.date.fromisoformat(date)
        except (TypeError, ValueError): raise ValueError(WRONG)
        if e.get("levels") is not None and not _texts(e["levels"]): raise ValueError(WRONG)
        if not isinstance(e.get("whole", True), bool): raise ValueError(WRONG)
        if e.get("whole", True):
            for k in ("from", "to"):   # not used on a whole day; kept only as a 24-hour time
                try: e[k] = _days.hhmm(_days.minutes(e[k])) if e.get(k) not in (None, "") else None
                except ValueError: e[k] = None
            continue
        try: f, t = _days.minutes(e.get("from")), _days.minutes(e.get("to"))
        except ValueError: raise ValueError(WRONG)
        if f not in starts: raise ValueError(f"{_days.hhmm(f)} is not the start of a period.")
        if t not in ends: raise ValueError(f"{_days.hhmm(t)} is not the end of a period.")
        if t <= f: raise ValueError(f"On {date} the end is before the start.")
        e["from"], e["to"] = _days.hhmm(f), _days.hhmm(t)   # one format everywhere: 24-hour HH:MM
    levels = set(model.get("levels") or [])
    for lv in s["levels"] + [x for e in s["days"].values() for x in (e.get("levels") or [])]:
        if lv not in levels: raise ValueError(f"{lv} is not a level of the published timetable.")
    classes = {c["name"] for c in model.get("classes") or []}
    for c in s["classes"]:
        if c not in classes: raise ValueError(f"{c} is not a class of the published timetable.")


def _check_event(s, pub):
    model = ((pub or {}).get("model") or {})
    for k, typ in (("name", str), ("levels", list), ("classes", list), ("days", dict), ("start", str), ("end", str),
                   ("in_charge", str), ("where", str), ("venues", list), ("going", list), ("duties", list)):
        if not isinstance(s.get(k), typ): raise ValueError(WRONG)
    if not s["name"].strip(): raise ValueError("Give the event a name.")
    if s.get("going_by") not in GOING_BY: raise ValueError(WRONG)
    _lists_and_pick(s)
    if not _texts(s["venues"]) or not _texts(s["going"]): raise ValueError(WRONG)
    for d in s["duties"]:
        if not isinstance(d, dict): raise ValueError(WRONG)
        for k in ("duty", "who", "time"):
            if d.get(k) is None: d[k] = ""
            if not isinstance(d[k], str): raise ValueError(WRONG)
    _when(s, model, "event")
    rooms = {r["name"] for r in model.get("rooms") or []}
    for v in s["venues"]:
        if v not in rooms: raise ValueError(f"{v} is not a room of the published timetable.")
    known = {p["name"] for p in relief.people.people(pub, relief.settings.load(pub)["extra_staff"])}
    for n in s["going"]:
        if n not in known: raise ValueError(f"{n} is not on the published timetable or the staff list.")
    s["going"] = list(dict.fromkeys(s["going"]))
    # an event holds no exam items: whatever came with it is emptied, so a forged copy puts none on the main site
    s.update(made=None, papers=[], access=[], times={}, seating={}, supervision="", scripts="", pins=dict(rooms={}, duties={}), use_anyway=[])


def _check(s, pub):
    if not isinstance(s, dict): raise ValueError(WRONG)
    if s.get("kind") == EVENT: return _check_event(s, pub)
    model = ((pub or {}).get("model") or {})
    for k, typ in (("name", str), ("levels", list), ("classes", list), ("days", dict), ("papers", list), ("access", list),
                   ("start", str), ("end", str)):
        if not isinstance(s.get(k), typ): raise ValueError(WRONG)
    if not isinstance(s.get("scripts", ""), str): raise ValueError(WRONG)
    _named(s, "exam")
    if s.get("kind") not in KINDS or s.get("supervision") not in SUPERVISION: raise ValueError(WRONG)
    _lists_and_pick(s)
    seating = s.get("seating")
    if not isinstance(seating, dict): raise ValueError(WRONG)
    for k, allowed in SEATING.items():
        v = seating.get(k)
        if (k == "home_rooms" and not isinstance(v, bool)) or v not in allowed: raise ValueError(WRONG)
    times = s.get("times")
    if not isinstance(times, dict): raise ValueError(WRONG)
    times["report"] = _time_or_none(times.get("report"), "Give the report time as a time such as 07:30.")
    for k, lo, sentence in (("min_break", 0, "Give a whole number of minutes between two papers."),
                            ("max_papers", 1, "Give a whole number for the most papers a day.")):
        if not _int(times.get(k)): raise ValueError(WRONG)
        if times[k] < lo: raise ValueError(sentence)
    _when(s, model, "exam")
    ids = set()
    for p in s["papers"]:
        if not isinstance(p, dict): raise ValueError(WRONG)
        for k in ("paper", "together"):   # an empty paper name or "sits with" may come as null
            if p.get(k) is None: p[k] = ""
        if not (isinstance(p.get("id"), str) and p["id"] and p["id"] not in ids): raise ValueError(WRONG)
        ids.add(p["id"])
        if not _int(p.get("minutes")) or p["minutes"] < 1: raise ValueError(f"Give {_papers.label(p)} a length in minutes.")
        if not all(isinstance(p.get(k), str) for k in ("level", "subject", "paper", "together")): raise ValueError(WRONG)
        if p.get("who") not in WHO or not _texts(p.get("students")): raise ValueError(WRONG)
        if p.get("date") in (None, ""): p["date"] = None
        else:
            try: datetime.date.fromisoformat(p["date"])
            except (TypeError, ValueError): raise ValueError(WRONG)
        p["start"] = _time_or_none(p.get("start"), f"Give {_papers.label(p)} a start time such as 08:00.")
    students = {x["id"] for x in model.get("students") or []}
    for x in s["access"]:
        if not isinstance(x, dict): raise ValueError(WRONG)
        ex = x.get("extra")
        if not isinstance(ex, (int, float)) or isinstance(ex, bool) or not 0 <= ex <= 100:
            raise ValueError(f"Extra time for {x.get('student')} must be 0 to 100 percent.")
        if x.get("student") not in students: raise ValueError(f"{x.get('student')} is not on the published timetable.")


def save(sched, pub, cal, by, check=True) -> dict:
    """check the schedule against the published timetable and write it at once. check=False: an approval action (approve,
    send back, withdraw, someone is away), which changes none of what the timetable is checked for, so a schedule
    approved before a new publish can still be withdrawn"""
    if check:
        _check(sched, pub)
    out = dict(sched, saved_at=_now(), saved_by=by)
    with _LOCK:
        os.makedirs(DIR, exist_ok=True)
        store.write_json(_path(out["id"]), out)
    return out


def load(id):
    try: s = store.read_json(_path(id), None)
    except ValueError: return None
    return s if isinstance(s, dict) else None


def all_saved() -> list:
    """every saved schedule, as stored"""
    return _all()


def listing(today, published_at=None) -> list:
    """one row per schedule, newest first; today (the caller's: app._exams_today) gives the label's 'Ended', published_at
    the 'retimed' flag"""
    rows = []
    for s in _all():
        st = s.get("status") or "draft"
        ap = s.get("approved")
        read = ap if st in ("approved", "changes") and ap else s
        rows.append(dict(id=s["id"], kind=s.get("kind"), name=s.get("name"), levels=s.get("levels"), start=s.get("start"), end=s.get("end"),
                         papers=len(s.get("papers") or []), status=s.get("status"), saved_at=s.get("saved_at"), label=_approval.label(s, today),
                         note=s.get("note") or "", sent_by=s.get("sent_by"), sent_at=s.get("sent_at"), approved_at=s.get("approved_at"),
                         on_site=[ap["start"], ap["end"]] if ap else None,
                         retimed=st in ("waiting", "approved", "changes") and _approval.retimed(read, published_at), _c=s.get("created_at") or ""))
    rows.sort(key=lambda r: r["saved_at"] or r["_c"], reverse=True)
    for r in rows: r.pop("_c")
    return rows


def delete(id):
    with _LOCK:
        try: os.remove(_path(id))
        except (FileNotFoundError, ValueError): pass


def on_site() -> list:
    """the approved copy (as a schedule) of every schedule that has one"""
    return [a for a in (_approval.as_schedule(s) for s in _all()) if a]


def copies(id) -> list:
    """for every other stored schedule, the copy the main site shows or may soon show: waiting: the working copy; approved:
    the approved copy; changes waiting: both (the approved first); draft and withdrawn: none. Each has status "waiting" or
    "approved"."""
    out = []
    for s in _all():
        if s["id"] == id:
            continue
        st = s.get("status") or "draft"
        if st == "waiting":
            out.append(dict(s, status="waiting"))
        elif st in ("approved", "changes") and s.get("approved"):
            out.append(dict(_approval.as_schedule(s), status="approved"))
            if st == "changes":
                out.append(dict(s, status="waiting"))
    return out


def event_busy(copy, model) -> list:
    """what an event holds on each date from its start to its end with classes on: the people going (one busy, with the
    classes), then each venue. Nothing when the timetable has no periods."""
    bnds = _days.bounds(model) if model else []
    if not bnds:
        return []
    out = []
    d, last = _days._date(copy["start"]), _days._date(copy["end"])
    while d <= last:
        iso = d.isoformat()
        win = _days._windows(copy, iso, model, bnds)
        d += datetime.timedelta(days=1)
        if not win:
            continue
        a, b = next(iter(win.values()))
        base = dict(id=copy["id"], name=copy.get("name"), status=copy["status"], date=iso, start=a, end=b, kind=EVENT)
        if copy.get("going"):
            out.append(dict(base, room="", names=list(copy["going"]), classes=list(win)))
        for v in copy.get("venues") or []:
            out.append(dict(base, room=v, names=[], classes=[]))
    return out


def _duty_busy(copy):
    return [dict(id=copy["id"], name=copy.get("name"), status=copy["status"], date=d["date"], start=d["start"], end=d["end"],
                 room=d["room"], names=list(d.get("names") or [])) for d in (copy.get("made") or {}).get("duties") or []]


def busies(copies, model) -> list:
    """the busy list of some copies: an exam gives one per made duty, an event what event_busy gives. A waiting copy leaves
    out the busies equal (date, start, end, room, names) to one of the approved copy of the same schedule."""
    key = lambda b: (b["date"], b["start"], b["end"], b["room"], tuple(b["names"]))
    mine = [(c, event_busy(c, model) if c.get("kind") == EVENT else _duty_busy(c)) for c in copies]
    held = {c["id"]: {key(b) for b in bs} for c, bs in mine if c["status"] == "approved"}
    return [b for c, bs in mine for b in bs if not (c["status"] == "waiting" and key(b) in held.get(c["id"], ()))]


def elsewhere(id, model=None) -> list:
    """what the other schedules hold (see busies); model None: the published timetable's"""
    if model is None:
        pub = store.published()
        model = pub["model"] if pub else None
    return busies(copies(id), model)


def shared_line(model, s, tag, date, start, end, classes) -> str:
    """"{other} ({status}) has {classes} on {date} too.": the classes of s, among the other's classes, whose window on that
    date overlaps start..end; "" when none. The one sentence behind the exam review and the event clashes."""
    bnds = _days.bounds(model)
    win = _days._windows(s, date, model, bnds)
    both = [c for c in win if c in classes and win[c][0] < end and win[c][1] > start]
    return "%s has %s on %s too." % (tag, ", ".join(both), _days.nice(date)) if both else ""

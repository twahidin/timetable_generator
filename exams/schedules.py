"""Exam and test schedules: make, check, save, list. One JSON file each under DATA/exams/schedules."""
import datetime, os, secrets, threading

import store
from exams import days as _days
from exams import papers as _papers

DIR = os.path.join(store.DATA, "exams", "schedules")
_LOCK = threading.Lock()
WRONG = "Check the exam and try again."
NO_CALENDAR = "Set the school calendar in Relief settings first: exams need it to know which timetable day a date is."


def _path(id):
    id = str(id)
    if not id.isalnum(): raise ValueError(WRONG)
    return os.path.join(DIR, f"{id}.json")


def _now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def _int(v):
    return isinstance(v, int) and not isinstance(v, bool)


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
                supervision="lesson" if test else "invigilators", pins=dict(rooms={}, duties={}), use_anyway=[], made=None,
                status="draft", created_at=_now(), created_by=by, saved_at=None, saved_by=None)


def _check(s, pub):
    if not isinstance(s, dict): raise ValueError(WRONG)
    model = ((pub or {}).get("model") or {})
    for k, typ in (("name", str), ("levels", list), ("classes", list), ("days", dict), ("papers", list), ("access", list),
                   ("start", str), ("end", str)):
        if not isinstance(s.get(k), typ): raise ValueError(WRONG)
    if not s["name"].strip(): raise ValueError("Give the exam a name.")
    if not s["levels"] and not s["classes"]: raise ValueError("Pick at least one level or class.")
    try:
        a, b = datetime.date.fromisoformat(s["start"]), datetime.date.fromisoformat(s["end"])
    except ValueError: raise ValueError(WRONG)
    if b < a: raise ValueError("Check the dates: the last day is before the first.")
    if (b - a).days + 1 > 31: raise ValueError("An exam can cover at most 31 days.")
    bnds = _days.bounds(model)
    starts, ends = {x for x, _ in bnds}, {y for _, y in bnds}
    for date, e in s["days"].items():
        if not isinstance(e, dict): raise ValueError(WRONG)
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
    for p in s["papers"]:
        if not isinstance(p, dict): raise ValueError(WRONG)
        if not _int(p.get("minutes")) or p["minutes"] < 1: raise ValueError(f"Give {_papers.label(p)} a length in minutes.")
        if p.get("start") in (None, ""): p["start"] = None
        else:
            try: p["start"] = _days.hhmm(_days.minutes(p["start"]))
            except ValueError: raise ValueError(f"Give {_papers.label(p)} a start time such as 08:00.")
    students = {x["id"] for x in model.get("students") or []}
    for x in s["access"]:
        if not isinstance(x, dict): raise ValueError(WRONG)
        ex = x.get("extra")
        if not isinstance(ex, (int, float)) or isinstance(ex, bool) or not 0 <= ex <= 100:
            raise ValueError(f"Extra time for {x.get('student')} must be 0 to 100 percent.")
        if x.get("student") not in students: raise ValueError(f"{x.get('student')} is not on the published timetable.")


def save(sched, pub, cal, by) -> dict:
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


def listing() -> list:
    rows = [dict(id=s["id"], kind=s.get("kind"), name=s.get("name"), levels=s.get("levels"), start=s.get("start"), end=s.get("end"),
                 papers=len(s.get("papers") or []), status=s.get("status"), saved_at=s.get("saved_at"), _c=s.get("created_at") or "")
            for s in _all()]
    rows.sort(key=lambda r: r["saved_at"] or r["_c"], reverse=True)
    for r in rows: r.pop("_c")
    return rows


def delete(id):
    with _LOCK:
        try: os.remove(_path(id))
        except (FileNotFoundError, ValueError): pass

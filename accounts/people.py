"""The accounts file: one record per person, keyed by name. update() is the only write path."""
import copy, datetime, os, threading
import store
from relief import people as _relief

PATH = os.path.join(store.DATA, "accounts", "people.json")
GROUPS = ("committee", "leader", "hod", "sh", "teacher", "executive")
LABELS = {"committee": "Timetable committee", "leader": "School leader", "hod": "HOD", "sh": "SH", "teacher": "Teacher", "executive": "Executive"}
MANAGEMENT = {"leader", "hod", "sh"}
HEADS = {"hod", "sh"}
SHARED = ("committee", "head", "teacher", "student")
_lock = threading.RLock()

def blank():
    return {"people": {}, "ways": {"off": {r: None for r in SHARED}, "recovery_used": []}, "moved": None}

def _defaults():
    return {"group": None, "depts": [], "extras": {"relief": False, "exams": None, "admin": False}, "username": None, "pw": None,
            "must_change": False, "google": None, "code_n": 0, "n": 0, "off": False, "added": False, "note": "", "signins": []}

class Unreadable(Exception):
    pass

UNREADABLE = "The accounts file could not be read, so nothing was changed. Ask whoever looks after the app to check it."

def _str(v):
    return v if isinstance(v, str) and v else None

def _int(v):
    return v if isinstance(v, int) and not isinstance(v, bool) else 0

def _iso(v):
    try: return datetime.date.fromisoformat(v).isoformat() if isinstance(v, str) else None
    except ValueError: return None

def _clean(got):
    """a stored record with every field forced to its proper type, so a hand-edited file cannot break callers"""
    r = _defaults()
    ex = got.get("extras") if isinstance(got.get("extras"), dict) else {}
    r["extras"] = {"relief": ex.get("relief") is True, "exams": _iso(ex.get("exams")), "admin": ex.get("admin") is True}
    r["group"] = got.get("group") if got.get("group") in GROUPS else None
    d = got.get("depts")
    r["depts"] = [x.strip() for x in d if isinstance(x, str) and x.strip()] if isinstance(d, list) else []
    s = got.get("signins")
    r["signins"] = [x for x in s if isinstance(x, (int, float)) and not isinstance(x, bool)] if isinstance(s, list) else []
    for k in ("username", "pw", "google"): r[k] = _str(got.get(k))
    for k in ("n", "code_n"): r[k] = _int(got.get(k))
    for k in ("off", "added", "must_change"): r[k] = got.get(k) is True
    r["note"] = got["note"] if isinstance(got.get("note"), str) else ""
    return r

def record(data, name):
    got = ((data or {}).get("people") or {}).get(name)
    return _clean(copy.deepcopy(got)) if isinstance(got, dict) else _defaults()

def _read():
    """-> (data, ok). ok is False when the file exists but could not be read or did not hold a dict"""
    d = store.read_json(PATH, None)
    if isinstance(d, dict): return _fill(d), True
    return blank(), not os.path.exists(PATH)

def load():
    return _read()[0]

def _fill(d):
    b = blank()
    if isinstance(d.get("people"), dict): b["people"] = d["people"]
    if isinstance(d.get("ways"), dict):
        w = d["ways"]
        if isinstance(w.get("off"), dict): b["ways"]["off"].update(w["off"])
        if isinstance(w.get("recovery_used"), list): b["ways"]["recovery_used"] = w["recovery_used"]
    b["moved"] = d.get("moved")
    return b

def update(fn):
    """under one lock: load, fn(data) changes it and returns a result, save, return the result"""
    with _lock:
        data, ok = _read()
        if not ok: raise Unreadable(UNREADABLE)
        out = fn(data)
        os.makedirs(os.path.dirname(PATH), exist_ok=True)
        store.write_json(PATH, data)
        return out

def _item(base, rec, published):
    group = rec["group"] or ("teacher" if published else "executive")
    depts = rec["depts"] if group in HEADS and rec["depts"] else base["depts"]
    last = max((s for s in rec["signins"] if isinstance(s, (int, float))), default=None)
    return dict(base, group=group, depts=list(depts), extras=rec["extras"], username=rec["username"], off=rec["off"],
                has_password=bool(rec["pw"]), last=last)

def staff(pub, data=None):
    data = load() if data is None else data
    base = _relief.people(pub, [])
    names = {p["name"] for p in base}
    extra = [dict(name=n, short=n, depts=[], role="", teaches=False, staff_only=True)
             for n, r in data["people"].items() if n not in names and isinstance(r, dict) and (r.get("added") or r.get("username"))]
    extra.sort(key=lambda p: p["name"])
    return [_item(p, record(data, p["name"]), p["name"] in names) for p in base + extra]

def find(name, pub, data=None):
    data = load() if data is None else data
    for p in staff(pub, data):
        if p["name"] == name:
            r = record(data, name)
            return dict(p, pw=r["pw"], n=r["n"], must_change=r["must_change"])
    return None

def by_username(data, username):
    u = str(username or "").strip().lower()
    if u:
        for n, r in data["people"].items():
            if isinstance(r, dict) and str(r.get("username") or "").lower() == u: return n, r
    return None, None

def admins(data):
    out = []
    for n in data["people"]:
        r = record(data, n)
        if r["group"] == "committee" and r["extras"].get("admin") and not r["off"]: out.append(n)
    return out

def sweep(data, today):
    iso, out = today.isoformat(), []
    for n, r in data["people"].items():
        ex = r.get("extras") if isinstance(r, dict) else None
        if isinstance(ex, dict) and isinstance(ex.get("exams"), str) and ex["exams"] < iso:
            ex["exams"] = None; out.append(n)
    return out

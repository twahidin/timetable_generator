"""The accounts file: one record per person, keyed by name. update() is the only write path."""
import copy, os, threading
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

def record(data, name):
    r = _defaults()
    got = ((data or {}).get("people") or {}).get(name)
    if isinstance(got, dict):
        got = copy.deepcopy(got)
        ex = dict(r["extras"]); ex.update(got.get("extras") or {}); r.update(got); r["extras"] = ex
    return r

def load():
    d = store.read_json(PATH, None)
    b = blank()
    if not isinstance(d, dict): return b
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
        data = load(); out = fn(data)
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
        if isinstance(ex, dict) and ex.get("exams") and ex["exams"] < iso:
            ex["exams"] = None; out.append(n)
    return out

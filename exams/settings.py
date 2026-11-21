"""Exams settings: the committee, the rooms' exam seats, the invigilator pool and the rules. One JSON file under DATA/exams."""
import os, threading

import store
from accounts import people as _accounts

PATH = os.path.join(store.DATA, "exams", "settings.json")
_LOCK = threading.Lock()
WRONG = "Check the settings and try again."
LISTS = ("committee", "backups", "chiefs", "never")
LABELS = dict(per_classroom="invigilators per classroom", hall_per="students per hall invigilator", arrive="arrive before",
              stay="stay after", max_per_day="duties a day")
RANGES = dict(per_classroom=(1, 10), hall_per=(1, 500), arrive=(0, 120), stay=(0, 120), max_per_day=(1, 20))


def defaults() -> dict:
    return dict(committee=[], rooms={}, backups=[], chiefs=[], never=[],
                rules=dict(per_classroom=2, hall_per=40, hall_chief=True, arrive=15, stay=10, max_per_day=None, not_own_subject=False),
                saved_at=None, saved_by=None)


def _known(pub) -> set:
    return {p["name"] for p in _accounts.staff(pub)}   # the published teachers and the staff added in the accounts


def load(pub) -> dict:
    saved = store.read_json(PATH, {})
    d = defaults()
    if isinstance(saved, dict):
        for k, v in saved.items():
            if k == "rules" and isinstance(v, dict): d["rules"].update(v)
            elif k in d: d[k] = v
    known = _known(pub)
    missing = []
    for key in LISTS:
        out = []
        for n in d[key] if isinstance(d[key], list) else []:
            if n in known: out.append(n)
            elif n not in missing: missing.append(n)
        d[key] = out
    rooms = {r["name"] for r in ((pub or {}).get("model") or {}).get("rooms") or []}
    kept, missing_rooms = {}, []
    for name, v in (d["rooms"] if isinstance(d["rooms"], dict) else {}).items():
        if name in rooms: kept[name] = v
        else: missing_rooms.append(name)
    d["rooms"], d["missing"], d["missing_rooms"] = kept, missing, missing_rooms
    return d


def _int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _check(new, pub) -> dict:
    """-> the clean dict to save; ValueError(one plain sentence) on the first problem"""
    if not isinstance(new, dict): raise ValueError(WRONG)
    base = defaults()
    known = _known(pub)
    lists = {}
    for key in LISTS:
        src = new.get(key, [])
        if not isinstance(src, list): raise ValueError(WRONG)
        out = []
        for n in src:
            if not isinstance(n, str): raise ValueError(WRONG)
            n = n.strip()
            if n not in known: raise ValueError(f"{n} is not on the published timetable or the staff list.")
            if n not in out: out.append(n)
        lists[key] = out
    have = {r["name"] for r in ((pub or {}).get("model") or {}).get("rooms") or []}
    src = new.get("rooms", {})
    if not isinstance(src, dict): raise ValueError(WRONG)
    rooms = {}
    for name, r in src.items():
        if name not in have: raise ValueError(f"{name} is not a room of the published timetable.")
        if not isinstance(r, dict): raise ValueError(WRONG)
        seats = r.get("seats")
        if seats is None or (_int(seats) and seats < 1): raise ValueError(f"Give {name} a number of exam seats.")
        if not _int(seats): raise ValueError(WRONG)
        rows, cols = r.get("rows"), r.get("cols")
        for x in (rows, cols):
            if x is not None and not (_int(x) and x >= 1): raise ValueError(WRONG)
        if rows and cols and rows * cols < seats: raise ValueError(f"{name}: rows times columns is less than its exam seats.")
        hall, access, note = r.get("hall", False), r.get("access", False), r.get("note", "")
        if not isinstance(hall, bool) or not isinstance(access, bool) or not isinstance(note, str): raise ValueError(WRONG)
        rooms[name] = dict(seats=seats, rows=rows, cols=cols, hall=hall, access=access, note=note.strip())
    rules = dict(base["rules"])
    given = new.get("rules", {})
    if not isinstance(given, dict): raise ValueError(WRONG)
    rules.update(given)
    for k, (lo, hi) in RANGES.items():
        v = rules[k]
        if v is None and k == "max_per_day": continue
        if not (_int(v) and lo <= v <= hi): raise ValueError(f"Give a whole number for {LABELS[k]}.")
    for k in ("hall_chief", "not_own_subject"):
        if not isinstance(rules[k], bool): raise ValueError(WRONG)
    return dict(committee=lists["committee"], rooms=rooms, backups=lists["backups"], chiefs=lists["chiefs"], never=lists["never"],
                rules={k: rules[k] for k in base["rules"]})


def save(data, pub, by) -> dict:
    clean = _check(data, pub)
    clean.update(saved_at=store.now(), saved_by=by)
    with _LOCK:
        os.makedirs(os.path.dirname(PATH), exist_ok=True)
        store.write_json(PATH, clean)
    return load(pub)

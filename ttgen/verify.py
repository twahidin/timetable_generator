"""Check a timetable made by an outside agent against the school's setup: every difference is a warning
(dict key, kind, text, strength, group, where, sides, ops). Periods are 0-based; day names are the setup's.
Every function that takes spec takes the checked setup (m["checked_setup"]), already derived."""
import re
from .export import ENTIRE

KINDS = ("clash", "deployment", "rule", "typed", "choice")

def warning(key, kind, text, strength="Must", group="School", where=None, sides=None, ops=None):
    """one warning in the shape the draft page lists"""
    return dict(key=key, kind=kind, text=text, strength=strength, group=group, where=where, sides=sides, ops=ops)


# ----------------------------------------------------------------------------------------------- what step 5 plans, what the timetable placed
def _name(key): return f"{key[2]} for {key[1]}" if key[0] == "C" else f"group {key[1]}"
def _kstr(key): return ":".join(key)

def planned_rows(spec):
    """key -> what step 5 plans: ("C", class, subject) for an entire-class row (one per class), ("G", code) for a group row"""
    out = {}
    for x in spec["lessons"]:
        if not x.get("periods") or not x.get("classes"): continue
        whole = x.get("code") == ENTIRE
        for c in (x["classes"] if whole else [None]):
            key = ("C", c, x["subject"]) if whole else ("G", x["code"])
            e = out.setdefault(key, dict(rows=[], teachers=set(), periods=0, room_kind=None, classes=[c] if whole else list(x["classes"]), level=x.get("level"), subject=x["subject"]))
            e["rows"].append(x); e["teachers"] |= set(x.get("teachers") or [])
            e["periods"] = e["periods"] + int(x["periods"]) if whole else int(x["periods"])   # as _model: entire-class rows add up, a group's code is one lesson
            e["room_kind"] = e["room_kind"] or x.get("room_kind")
    return out

def placed(m):
    """key -> what the timetable placed (same keys); a lesson id counts once per key"""
    out, seen = {}, set()
    def add(key, x):
        e = out.setdefault(key, dict(lessons=[], teachers=set(), periods=0, rooms=set()))
        e["lessons"].append(x); e["teachers"] |= set(x["teachers"])
        if x["room"]: e["rooms"].add(x["room"])
        if (x["id"], key) not in seen: seen.add((x["id"], key)); e["periods"] += x["n"]
    for x in m["lessons"]:
        if x["group"] == ENTIRE:
            for c in x["classes"]: add(("C", c, x["subject"]), x)
        else: add(("G", x["group"]), x)
    return out


# ----------------------------------------------------------------------------------------------- the comparison
def _ids(rows):
    """the ids of rows an op may act on; none when a row covers more than one class (the op would reach the others too)"""
    return [] if any(len(x["classes"]) > 1 for x in rows) else [x["_id"] for x in rows if x.get("_id")]

def deployment(m, spec):
    """one warning per difference between the timetable and step 5 (teachers, periods, venue kind, missing, extra)"""
    plan, got, out = planned_rows(spec), placed(m), []
    subjects = {str(s["subject"]) for s in spec["subjects"]}
    def where(key, e):
        x = e["lessons"][0]; return dict(cls=key[1] if key[0] == "C" else (x["classes"] or [""])[0], day=m["days"][x["d"]], period=x["p"])
    for key in plan:
        p, k, what = plan[key], _kstr(key), _name(key); group = p["classes"][0] if p["classes"] else "School"
        if key not in got:
            ids = _ids(p["rows"])
            out.append(warning(f"dep:{k}:missing", "deployment", f"{what} is on step 5 but not on the timetable.", group=group, ops=[["del", "lessons", i] for i in ids] or None))
            continue
        g = got[key]; w = where(key, g)
        if g["teachers"] != p["teachers"]:
            a, b = ", ".join(sorted(g["teachers"])), ", ".join(sorted(p["teachers"])); ids = _ids(p["rows"])
            out.append(warning(f"dep:{k}:teachers", "deployment", f"{what} is taught by {a} on the timetable; step 5 says {b}.", group=group, where=w,
                               sides=dict(timetable=a, step5=b), ops=[["set", "lessons", i, "teachers", sorted(g["teachers"])] for i in ids] or None))
        if g["periods"] != p["periods"]:
            out.append(warning(f"dep:{k}:periods", "deployment", f"{what}: {g['periods']} periods timetabled, {p['periods']} on step 3.", group=group, where=w,
                               sides=dict(timetable=str(g["periods"]), step5=str(p["periods"]))))
        if p["room_kind"]:
            for x in g["lessons"]:
                kind = m["room_ix"].get(x["room"], {}).get("kind") if x["room"] and x["room"] != "TBC" else None
                if kind and kind != p["room_kind"]:
                    out.append(warning(f"dep:{k}:venue", "deployment", f"{what} is in {x['room']} ({kind}); step 3 asks for {p['room_kind']}.", group=group, where=w)); break
    for key, g in got.items():
        if key in plan: continue
        k, x = _kstr(key), g["lessons"][0]
        classes = [key[1]] if key[0] == "C" else list(x["classes"])
        ops = [["add", "lessons", dict(level=x["level"], subject=x["subject"], classes=classes, teachers=sorted(g["teachers"]), block=x["block"] or None,
                                                  **({} if key[0] == "C" else dict(code_override=key[1]))), ""]] if x["subject"] in subjects else None
        out.append(warning(f"dep:{k}:extra", "deployment", f"{_name(key)} is on the timetable but not on step 5.", group=classes[0] if classes else "School", where=where(key, g), ops=ops))
    return out

def clashes(m):
    """the independent checks' problems as warnings, without the period-count lines (the comparison owns those)"""
    out, own = [], set(m.get("choice_problems") or ())   # the second-choice sentences are listed as choice warnings
    for text in m["checks"]["problems"]:
        if text.endswith("planned.") or text in own: continue
        who = re.match(r"(?:Teacher double-booked|Class clash): (.+?) on ", text)
        out.append(warning("clash:" + text, "clash", text, group=who.group(1) if who else "School"))
    return out

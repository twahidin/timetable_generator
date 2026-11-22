"""Re-fit: the fewest lesson changes that make the draft fit the setup again. Which warnings it works on is here."""
import helper, fixes
from ttgen import verify
from ttgen.export import ENTIRE
from ttgen.spec import whole as whole_n

MAX_MOVES = 3        # the most changes in one answer
MAX_NODES = 250      # the most search steps for one warning
CAND_LESSONS = 4     # the lessons tried for a change
CAND_SLOTS = 8       # the places tried for a lesson
BUDGET_S = 30.0      # the most seconds for a whole re-fit

NO_FIT = "No list of up to 3 moves fits it."
BAND = "This changes the band itself: change it on the board, or ask the agent for a new timetable."
SPLIT = "Its lessons are taught by different teachers: change them on the board."
NOT_ONE = "More than one teacher changes: change it on the board."
LATE = "Not looked at in time; run Re-fit again."

PARTS = ("teachers", "missing", "periods", "extra", "venue", "half")   # the step 5 differences it works on, in this order

def _rank(w):
    """the place of a warning in the list, or None when a re-fit does not work on it"""
    if w.get("decision"): return None
    kind = w.get("kind")
    if kind == "deployment":
        part = helper._dep_parts(w.get("key"))[1]
        return (0, PARTS.index(part)) if part in PARTS else None
    if kind == "clash": return (1, 0)
    if kind == "rule" and w.get("strength") == "Must": return (2, 0)
    return None

def targets(warnings):
    """the open warnings a re-fit works on: step 5 differences (teachers, missing, periods, extra, venue, half), then clashes, then Must rules.
    Each is dict(kind=<part, "clash" or "rule">, key, text, w). Pure: it reads only the list."""
    found = []
    for w in warnings or []:
        r = _rank(w)
        if r is not None: found.append((r, w))
    found.sort(key=lambda x: x[0])   # stable: warnings of one place keep the order the page lists them in
    return [dict(kind=PARTS[r[1]] if r[0] == 0 else "clash" if r[0] == 1 else "rule", key=w["key"], text=w["text"], w=w) for r, w in found]

def needed(warnings):
    """whether a re-fit has anything to work on (the page's and the route's check)"""
    return bool(targets(warnings))


# ----------------------------------------------------------------------------------------------- the direct change for one warning
def _band(e, rows):
    """whether the key is a band group: its planned row, or a timetabled row of it, has a block"""
    return any(r.get("block") for r in e["rows"]) or any(x.get("block") for x in rows)

def _teachers(m, spec, ks, e, rows, text):
    have = {t for x in rows for t in x["teachers"]}; want = set(e["teachers"])
    if not want: return [], text   # nobody on step 5 for the key: the warning's own words
    gone, new = have - want, want - have
    one = len(gone) == 1 and len(new) == 1
    alike = all(set(x["teachers"]) == set(rows[0]["teachers"]) for x in rows)
    if not one: return [], NOT_ONE
    if not alike: return [], SPLIT
    known = {t.get("name") for t in spec.get("teachers") or [] if isinstance(t, dict)}
    if not new <= known: return [], f"{next(iter(new))} is not on the setup's list of teachers."
    g, n = next(iter(gone)), next(iter(new))
    return [[dict(kind="teacher", key=ks, teachers=[n if t == g else t for t in rows[0]["teachers"]])]], None

def _class_of(k, e, rows=()): return k[1] if k[0] == "C" else ((e or {}).get("classes") or [c for x in rows for c in x["classes"]] or [None])[0]

def _adds(m, spec, days, pool, ks, k, e, n):
    cls = _class_of(k, e); c = fixes._ctx(m)
    busy = lambda d: len({x["id"] for x in m["lessons"] if cls in x["classes"] and x["d"] == d})   # the lessons the class already has that day
    ok = [s for s in fixes.add_slots(m, spec, days, ks, n, pool) if s["state"] == "ok"]
    ok.sort(key=lambda s: (busy(s["d"]), s["d"], s["p"]))
    return [[dict(kind="add", key=ks, d=s["d"], p=s["p"], n=n, room=fixes.add_room(m, spec, ks, s["d"], s["p"], n, c))] for s in ok]

def _deletes(m, spec, days, pool, k, e, rows):
    cls = _class_of(k, e, rows); c = fixes._ctx(m); L = m["lessons"]
    per = {}   # the periods the class has on each day
    for i, g in {x["id"]: x for x in L if cls in x["classes"]}.items(): per[g["d"]] = per.get(g["d"], 0) + g["n"]
    first = {}
    for x in rows: first.setdefault(x["id"], x)
    out = []
    for i, x in sorted(first.items(), key=lambda v: (-per.get(v[1]["d"], 0), -v[1]["d"], -v[1]["p"], v[0])):
        many = len(fixes._rows(L, i)) > 1
        f = dict(kind="delete", id=i, **({"group": ENTIRE if k[0] == "C" else k[1]} if many else {}))
        j = fixes.can_delete(m, spec, days, i, f.get("group"), pool, c)
        if j["state"] == "no" and not j["plan"]: continue   # a rule refuses it
        out.append([f])
    return out

def _wrong_rows(m, e, rows):
    """the rows in a room of another kind than step 5 asks for, as verify.deployment finds them"""
    kind_of = lambda x: m["room_ix"].get(x["room"], {}).get("kind") if x["room"] and x["room"] != "TBC" else None
    return [x for x in rows if kind_of(x) and kind_of(x) != e["room_kind"] and not (kind_of(x) == "classroom" and verify._other_week(m["days"][x["d"]], e["room_weeks"]))] if e["room_kind"] else []

def _small(m, spec, k, e, room):
    """whether a lesson of the row in this room is in one room of a combined venue that seats the group while that room does not (verify's half-venue test)"""
    parts = m.get("room_parts") or {}; n = verify._group_size(spec, k, e)
    seats = lambda r: whole_n((m["room_ix"].get(r) or {}).get("capacity"))
    return n is not None and any(room in rooms and seats(room) is not None and seats(c) is not None and seats(room) < n <= seats(c) for c, rooms in parts.items())

def _seats(m, spec, k, e, room):
    """whether the room is known to seat the group"""
    n = verify._group_size(spec, k, e); v = whole_n((m["room_ix"].get(room) or {}).get("capacity"))
    return n is not None and v is not None and v >= n

def _rooms(m, spec, days, pool, x, ok=None):
    """a room fix for the row for each "ok" room of room_options, in its order (only the rooms the test ok(room) accepts, when one is given)"""
    return [[dict(kind="room", id=x["id"], group=x["group"], room=o["room"])] for o in fixes.room_options(m, spec, days, x["id"], x["group"], pool) if o["state"] == "ok" and (ok is None or ok(o["room"]))]

def direct(m, spec, days, target, pool):
    """the change itself for one target, before any search -> (candidates, sentence): the candidate changes, each a list of fixes,
    best first; and a Needs-you sentence when the target can never be one of the app's changes, else None. clash and rule have none
    here (the search moves lessons). Never changes m or its lessons; a key step 5 no longer has gives the warning's own text"""
    text = target["text"]
    try:
        if target["kind"] in ("clash", "rule"): return [], None
        k, part = helper._dep_parts(target["key"]); plan = verify.planned_rows(spec); e = plan.get(k) if k else None; rows = helper._of_key(m["lessons"], k) if k else []
        if part == "extra":   # a key step 5 does not have: its rows are the surplus
            if k is None or e is not None or not rows: return [], text
            return ([], BAND) if any(x.get("block") for x in rows) else (_deletes(m, spec, days, pool or (), k, None, rows), None)
        if e is None: return [], text
        ks = verify._kstr(k)
        if part == "teachers": return _teachers(m, spec, ks, e, rows, text) if rows else ([], text)
        if part in ("missing", "periods") and _band(e, rows): return [], BAND
        if part in ("missing", "periods"):
            have = verify.placed(dict(m, lessons=list(m["lessons"]) + list(pool or ()))).get(k, {}).get("periods", 0)
            if have < e["periods"]:
                sh = next((x for x in fixes.short(m, spec, pool or ()) if x["key"] == ks), None)
                return (_adds(m, spec, days, pool or (), ks, k, e, sh["n"]) if sh else []), None
            if part == "periods" and have > e["periods"]: return _deletes(m, spec, days, pool or (), k, e, rows), None
            return [], text
        if part == "venue":
            wrong = _wrong_rows(m, e, rows)
            return ([c for x in wrong for c in _rooms(m, spec, days, pool or (), x)], None) if wrong else ([], text)
        if part == "half":
            out = [c for x in rows if _small(m, spec, k, e, x["room"]) for c in _rooms(m, spec, days, pool or (), x, lambda r: _seats(m, spec, k, e, r))]
            return (out, None) if out else ([], text)
        return [], text
    except Exception: return [], text

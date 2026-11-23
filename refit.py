"""Re-fit: the fewest lesson changes that make the draft fit the setup again. Here are the warnings it works on, the change
itself for each, where a lesson may go, and the search for the list of fixes that settles one warning. One list for all of
them is made by refit_plan, which imports this (nothing here knows the draft)."""
import collections, itertools, re, time
import helper, fixes
from ttgen import verify
from ttgen.export import ENTIRE
from ttgen.spec import single_rooms, whole as whole_n

MAX_MOVES = 3        # the most moves and swaps in one answer
MAX_DIRECT = 8       # the most changes of step 5 itself in one answer
MAX_GROWN = 4        # the lists of them carried on with further ones, at each number of moves
MAX_TRADES = 3       # the trades tried for a teacher change
MAX_NODES = 250      # the most search steps (lists judged) for one warning
MAX_KEPT = 40        # the timetables, each with its index, kept while looking
CAND_LESSONS = 4     # the lessons tried for a change
CAND_SLOTS = 8       # the places tried for a lesson
FAR_SLOTS = 12       # the places on other days tried for it besides, as the last resort
TAKEN_SLOTS = 6      # the places in use tried for a missing lesson when none is free
BUDGET_S = 30.0      # the most seconds for a whole re-fit

NO_FIT = "No list of up to 3 moves fits it."
BAND = "This changes the band itself: change it on the board, or ask the agent for a new timetable."
SPLIT = "Its lessons are taught by different teachers: change them on the board."
NOT_ONE = "More than one teacher changes: change it on the board."
ONE_SIDED = "A teacher is added or taken off, not changed for another: change it on the board."
NO_STAFF = "Step 5 has no teacher for it: choose one there first, then run Re-fit again."
TOO_MANY = "More than 8 changes: change it on the board."
LATE = "Not looked at in time; run Re-fit again."
NOT_PLACED = "That lesson is not placed. Place it first."   # fixes.apply_one's own words
OVER = " over the allowance."   # how fixes.judge ends a teacher's allowance line: the only Prefer reason an answer may give

PARTS = ("teachers", "missing", "periods", "extra", "venue", "half")   # the step 5 differences it works on, in this order

def _rank(w):
    """the place of a warning in the list, or None when a re-fit does not work on it"""
    if w.get("decision"): return None
    kind = w.get("kind")
    if kind == "deployment":
        part = helper._dep_parts(w.get("key"))[1]
        return (0, PARTS.index(part)) if part in PARTS else None
    if kind == "clash": return (1, 0) if w.get("crit") else None   # one that is no mistake (a double the setup allows that day) is left as it is
    if kind == "rule" and w.get("strength") == "Must": return (2, 0)
    return None

def targets(warnings):
    """the open warnings a re-fit works on: step 5 differences (teachers, missing, periods, extra, venue, half), then clashes (the critical
    ones), then Must rules. Each is dict(kind=<part, "clash" or "rule">, key, text, w). Pure: it reads only the list."""
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

def _teachers(m, spec, days, pool, plan, ks, e, rows, text):
    have = {t for x in rows for t in x["teachers"]}; want = set(e["teachers"])
    if not want: return [], text   # nobody on step 5 for the key: the warning's own words
    gone, new = have - want, want - have
    alike = all(set(x["teachers"]) == set(rows[0]["teachers"]) for x in rows); sided = len(gone) + len(new) == 1
    if not sided and not (len(gone) == 1 and len(new) == 1): return [], NOT_ONE
    if not alike: return [], SPLIT
    if sided: return [], ONE_SIDED
    known = {t.get("name") for t in spec.get("teachers") or [] if isinstance(t, dict)}
    if not new <= known: return [], f"{next(iter(new))} is not on the setup's list of teachers."
    g, n = next(iter(gone)), next(iter(new))
    return [[dict(kind="teacher", key=ks, teachers=[n if t == g else t for t in rows[0]["teachers"]])]] + [[f] for f in _trades(m, spec, days, pool, plan, ks, g, n)], None

def _trades(m, spec, days, pool, plan, ks, g, n):
    """the trades that give the key ks, g's on the timetable and n's on step 5, to n and at once to g another key of step 5 (plan) that is n's on the timetable and g's on step 5, all its
    lessons taught alike: at most MAX_TRADES, in the order of those keys; none the app would refuse (a lesson not placed is taught by the other already)"""
    out = []
    for k in sorted(k for k, e in plan.items() if g in e["teachers"] and n not in e["teachers"]):
        rows = helper._of_key(m["lessons"], k); have = set(rows[0]["teachers"]) if rows else set()
        if len(out) == MAX_TRADES: break
        if have - plan[k]["teachers"] != {n} or plan[k]["teachers"] - have != {g} or any(set(x["teachers"]) != have for x in rows): continue
        f = dict(kind="trade", a=ks, b=verify._kstr(k), x=g, y=n); L = list(m["lessons"])
        try: helper._own(L, f); fixes.apply_one(L, f, spec, days, pool=[dict(x) for x in pool])
        except ValueError: continue
        out.append(f)
    return out

def _class_of(k, e, rows=()): return k[1] if k[0] == "C" else ((e or {}).get("classes") or [c for x in rows for c in x["classes"]] or [None])[0]

def _usable(j):
    """whether a place (as add_slots or the judge gives it) is one an answer may use: ok, or over a teacher's allowance and nothing else (the judge puts the rules it gives first)"""
    return j["state"] == "ok" or (j["state"] == "prefer" and j["why"].endswith(OVER))

def _adds(m, spec, days, pool, ks, k, e, n, held):
    cls = _class_of(k, e); c = fixes._ctx(m); own = helper._of_key(m["lessons"], k)   # the lessons the key has already (one put in by the list too)
    busy = lambda d: len({x["id"] for x in m["lessons"] if cls in x["classes"] and x["d"] == d})   # the lessons the class already has that day
    slots = sorted(fixes.add_slots(m, spec, days, ks, n, pool), key=lambda s: (busy(s["d"]), s["d"], s["p"]))
    free = [[dict(kind="add", key=ks, d=s["d"], p=s["p"], n=n, room=fixes.add_room(m, spec, ks, s["d"], s["p"], n, c))] for s in slots if _usable(s) and not _meets(own, s["d"], s["p"], n)]   # none on top of a lesson of the key, which the judge allows on a day of doubles or with no teacher
    return free or _taken(m, spec, days, pool, ks, n, slots, c, held, own)

def _meets(rows, d, p, n):
    """the ids of the rows' lessons that share a period with periods p .. p+n-1 of day d"""
    return {x["id"] for x in rows if x["d"] == d and x["p"] < p + n and p < x["p"] + x["n"]}

def _taken(m, spec, days, pool, ks, n, slots, c, held, own):
    """adds at places (slots, in their order, those that meet a lesson of the key last) that are refused only for lessons there that a search may move (not a band, not in held): at most
    TAKEN_SLOTS, each one the judge lets the add have, in the room add_room gives it then, with those lessons off the timetable. A lesson of the
    key itself (own: their rows) may be one of those there, when the place is not all inside it (that lesson would only be put elsewhere, and the
    place take the turn of another); a place that meets a lesson of the key which is not in the way of the add is left out"""
    out, b = [], c["busy"]
    for s in sorted(slots, key=lambda s: bool(_meets(own, s["d"], s["p"], n))):
        if len(out) == TAKEN_SLOTS: break
        if s["state"] != "no" or any(x["d"] == s["d"] and x["p"] <= s["p"] and s["p"] + n <= x["p"] + x["n"] for x in own): continue
        f = dict(kind="add", key=ks, d=s["d"], p=s["p"], n=n, room=""); row, there = [], set(); fixes.apply_one(row, f, spec, days, new_id=c["next_id"])
        while (y := b.blocker(row, s["d"], s["p"], n, ignore=there)) is not None: there.add(y)
        usable = lambda f: _usable(fixes.judge(m, spec, days, dict(f, out=sorted(there)), c, pool=pool))
        if not there or _meets(own, s["d"], s["p"], n) - there or any(y in held or fixes._block(b.ids[y]) for y in there) or not usable(f): continue   # with no lesson there, nothing to move makes it a place
        m2 = dict(m, lessons=[x for x in m["lessons"] if x["id"] not in there]); c2 = dict(c, m=m2, busy=fixes.Busy(m2, base=b))
        f = dict(f, room=fixes.add_room(m2, spec, ks, s["d"], s["p"], n, c2))
        if usable(f): out.append([f])
    return out

def _day_periods(lessons, cls):
    """{day: the periods the class has on it}"""
    per = {}
    for g in {x["id"]: x for x in lessons if cls in x["classes"]}.values(): per[g["d"]] = per.get(g["d"], 0) + g["n"]
    return per

def _deletes(m, spec, days, pool, k, e, rows, held):
    c = fixes._ctx(m); L = m["lessons"]; per = _day_periods(L, _class_of(k, e, rows))
    first = {}
    for x in rows: first.setdefault(x["id"], x)
    out = []
    for i, x in sorted(first.items(), key=lambda v: (-per.get(v[1]["d"], 0), -v[1]["d"], -v[1]["p"], v[0])):
        if i in held: continue   # moved already: the list would undo itself
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

# ----------------------------------------------------------------------------------------------- where a lesson may go
def _musts(m, spec, rows):
    """{subject: sentence} of the Must rules the rows of one lesson break by themselves, whatever else is on the timetable"""
    return {s: w["text"] for s, w in fixes.rule_subjects(m, spec, rows).items() if w.get("strength") == "Must" and isinstance(s, tuple)}

def barred(m, spec, days, lesson_id, d, pool, memo=None):
    """whether day d is closed to the lesson itself: with only its own rows on the timetable, every start period where it fits on
    that day is refused by lesson_time (its hour outside the day, a break, a recess) or breaks a Must rule. No period that fits counts
    as barred. Rooms, clashes, other lessons and Prefer rules do not count; a lesson in the pool is not asked about (False).
    Cached by (lesson_id, d) in memo when one is given. Never changes m or its lessons"""
    key = ("barred", lesson_id, d)
    if memo is not None and key in memo: return memo[key]
    rows = [x for x in m["lessons"] if x["id"] == lesson_id]
    if not rows or any(x["id"] == lesson_id for x in pool or ()): out = False
    else:
        n = rows[0]["n"]; busy = fixes.Busy(m, [])
        def closed(p):
            moved = [dict(x, d=d, p=p) for x in rows]
            return bool(busy.lesson_time(moved, d, p, n)) or any(w.get("strength") == "Must" for w in verify.rules(dict(m, lessons=moved), spec)[0])
        out = all(closed(p) for p in range(m["NP"] - n + 1))
    if memo is not None: memo[key] = out
    return out

def day_moves(m, spec, days, lesson_id, ctx, memo, moved, limit=CAND_SLOTS, far=False, shut=None):
    """the moves and swaps of one lesson the rules allow now, best first -> [dict(fix, other, dist)]: the same day's "ok" slots nearest
    period first (a swap only with a lesson that is not a band and not in moved), or, only when the lesson's own day is barred
    (see barred), plain moves to other days (nearest day, then nearest period): at most limit of them (None: all). far: after those, the
    "ok" slots of other days that are not among them, a swap with a lesson of that day too (never one put on a day barred for it): the nearest
    day, a move before a swap, the nearest period; at most FAR_SLOTS (all when limit is None). other: how many lessons change day (an exchange
    of two days: 2); dist: the periods moved, 10 per day for another day. shut(fix): a place left out, before they are counted.
    [] for a band lesson, one in moved, or one not on the timetable. Never changes m"""
    pool = m.get("pool") or (); rows = [x for x in m["lessons"] if x["id"] == lesson_id]
    if not rows or lesson_id in moved or fixes._block(rows) or any(x["id"] == lesson_id for x in pool): return []
    d0, p0 = rows[0]["d"], rows[0]["p"]; gap = lambda s: (abs(s["d"] - d0), abs(s["p"] - p0))
    def fix(s): return dict(kind="move", id=lesson_id, d=s["d"], p=s["p"]) if s["swap"] is None else dict(kind="swap", a=lesson_id, b=s["swap"])
    def free(i): o = [x for x in m["lessons"] if x["id"] == i]; return bool(o) and not fixes._block(o) and i not in moved
    def may(s): return (s["swap"] is None or free(s["swap"])) and not (shut and shut(fix(s)))
    ok = [s for s in fixes.slots(m, spec, days, lesson_id, pool, extras=False, ctx=ctx) if s["state"] == "ok"]
    if barred(m, spec, days, lesson_id, d0, pool, memo): first = [s for s in ok if s["d"] != d0 and s["swap"] is None]   # a same-day place keeps the lesson on a barred day, where the Must rule stays broken
    else: first = [s for s in ok if s["d"] == d0]
    out = [s for s in sorted(first, key=lambda s: (gap(s)[0], s["d"], gap(s)[1], s["p"])) if may(s)][:limit]
    if far:
        had = {(s["d"], s["p"]) for s in out}; left = sorted((s for s in ok if s["d"] != d0 and (s["d"], s["p"]) not in had), key=lambda s: (gap(s)[0], s["swap"] is not None, gap(s)[1], s["d"], s["p"]))
        more = (s for s in left if may(s) and (s["swap"] is None or not barred(m, spec, days, s["swap"], d0, pool, memo)))
        out += itertools.islice(more, None if limit is None else FAR_SLOTS)
    return [dict(fix=fix(s), other=(s["d"] != d0) * (1 if s["swap"] is None else 2), dist=10 * gap(s)[0] + gap(s)[1]) for s in out]


def direct(m, spec, days, target, pool, held=()):
    """the change itself for one target, before any search -> (candidates, sentence): the candidate changes, each a list of fixes,
    best first; and a Needs-you sentence when the target can never be one of the app's changes, else None. clash and rule have none
    here (the search moves lessons). held: the ids of lessons that stay where they are (moved already): none is deleted, and no add is
    offered in the place of one. Never changes m or its lessons; a key step 5 no longer has gives the warning's own text"""
    text = target["text"]
    if target["kind"] in ("clash", "rule"): return [], None
    k, part = helper._dep_parts(target["key"]); plan = verify.planned_rows(spec); e = plan.get(k) if k else None; rows = helper._of_key(m["lessons"], k) if k else []
    if part == "extra":   # a key step 5 does not have: its rows are the surplus
        if k is None or e is not None or not rows: return [], text
        return ([], BAND) if any(x.get("block") for x in rows) else (_deletes(m, spec, days, pool or (), k, None, rows, held), None)
    if e is None: return [], text
    ks = verify._kstr(k)
    if part == "teachers": return _teachers(m, spec, days, pool or (), plan, ks, e, rows, text) if rows else ([], text)
    if part in ("missing", "periods") and _band(e, rows): return [], BAND
    if part in ("missing", "periods"):
        have = verify.placed(dict(m, lessons=list(m["lessons"]) + list(pool or ()))).get(k, {}).get("periods", 0)
        if have < e["periods"] and not e["teachers"]: return [], NO_STAFF   # a lesson nobody teaches is a mistake, which the judge does not look for
        if have < e["periods"]:
            sh = next((x for x in fixes.short(m, spec, pool or ()) if x["key"] == ks), None)
            return (_adds(m, spec, days, pool or (), ks, k, e, sh["n"], held) if sh else []), None
        if part == "periods" and have > e["periods"]: return _deletes(m, spec, days, pool or (), k, e, rows, held), None
        return [], text
    if part == "venue":
        wrong = _wrong_rows(m, e, rows)
        return ([c for x in wrong for c in _rooms(m, spec, days, pool or (), x)], None) if wrong else ([], text)
    if part == "half":
        out = [c for x in rows if _small(m, spec, k, e, x["room"]) for c in _rooms(m, spec, days, pool or (), x, lambda r: _seats(m, spec, k, e, r))]
        return (out, None) if out else ([], text)
    return [], text


# ----------------------------------------------------------------------------------------------- the search for one target
class _Stop(Exception):
    """the search has reached its limit of steps or of time"""

def _ids(fix):
    """the ids of the lessons a fix names (none for an add, a teacher change or a trade)"""
    return {fix["a"], fix["b"]} if fix["kind"] == "swap" else {fix["id"]} if "id" in fix else set()

def _refusal(c):
    """(the step, the judge's sentence) that rules a chain out, or None for one that is accepted: every step ok, or prefer for allowance lines alone"""
    if c["state"] not in helper.OK: return len(c["steps"]) - 1, c["why"]
    return next(((i, t) for i, j in enumerate(c["steps"]) for t in j["prefer"] if not t.endswith(OVER)), None)

# whether a warning is settled: helper.settles, with what it does not look at
def _room_clash(m, w):
    """(the room, the (d, q) it names) of a warning that a room is over capacity, else None"""
    g = re.match(r"clash:Room over capacity: (.+?) on ", w.get("key") or ""); slots = g and helper._clash_slots(m, w, g.group(1))
    return (g.group(1), slots) if slots else None

def _over(m, lessons, room, slots):
    """whether the room holds more lessons than it can in one of these (d, q), as export.check_model counts"""
    parts = m.get("room_parts") or {}; stands = [x for x in lessons if not fixes._no_room(x["room"]) and room in single_rooms(x["room"], parts)]
    n = collections.Counter((x["d"], q) for x in stands for q in fixes._span(x))
    return any(n[s] > m["room_cap"].get(room, 1) for s in slots)

def _settled(m, spec, days, w, lessons, before, room):
    """helper.settles, and for a room over capacity (room: its _room_clash) the room itself: settles looks only at a clash's teacher or class"""
    return helper.settles(m, spec, days, w, lessons, before) and not (room and _over(m, lessons, *room))

def _at_once(lessons, ids=None):
    """the pairs of lessons (their ids) of one key of step 5 that share a period; with ids, of the keys those lessons are of only. A whole-class
    row is of the key of each of its classes. The judge lets two lessons of a group be at once on a day of doubles or with no teacher"""
    of = lambda x: [k for k in helper._keys_of(x) if all(k)]   # none for a row without a group, a class or a subject
    keys = None if ids is None else {k for x in lessons if x["id"] in ids for k in of(x)}; at = collections.defaultdict(set)
    for x in lessons:
        for k in of(x):
            if keys is None or k in keys:
                for q in fixes._span(x): at[k, x["d"], q].add(x["id"])
    return {two for there in at.values() if len(there) > 1 for two in itertools.combinations(sorted(there), 2)}

def _gone(m, spec, days, w, before, room):
    """whether an earlier target's fixes have settled the warning on m already. settles cannot say it of a clash about one lesson
    (in a break, past the day, without a teacher): that is gone with the lesson, or, for its place, once the lesson is elsewhere"""
    wh = w.get("where") or {}
    if w.get("kind") != "clash": return helper.settles(m, spec, days, w, m["lessons"], before)
    if room: return not _over(m, m["lessons"], *room)
    if w.get("crit") == "notplaced" or w["key"].startswith("clash:bands:"): return False   # no list places a lesson or moves a band
    if wh.get("id") is None: return bool(before.get("named")) and helper.settles(m, spec, days, w, m["lessons"], before)   # a double booking
    x = next((x for x in m["lessons"] if x["id"] == wh["id"] and x["group"] == wh.get("row", x["group"])), None)
    return x is None or (w.get("crit") != "noteacher" and (m["days"][x["d"]], x["p"]) != (wh.get("day"), wh.get("period")))

def _blocker(b, days, rows, ignore):
    """(the lesson in the way of these rows where they are, why: "T1 teaches Maths for 1B on Mon period 3."), or None. It is
    b.blocker's, which names the lesson helper._alone would too"""
    x = rows[0]; y = b.blocker(rows, x["d"], x["p"], x["n"], ignore=ignore)
    if y is None: return None
    s = b.clash(rows, x["d"], x["p"], x["n"], ignore=ignore).replace(" is teaching ", " teaches ", 1); at = f" on {fixes.when(days, b.ids[y][0]['d'], b.ids[y][0]['p'])}"
    return y, s[:-len(" then.")] + at + "." if s.endswith(" then.") else s.replace(" then, ", at + ", ", 1)

def _takes(rows, f):
    """{id(row): its teachers once the teacher fix or the trade f is made} of the rows that f changes, as fixes.apply_one changes them"""
    if f["kind"] == "teacher": return {id(x): list(f["teachers"]) for x in fixes.rows_of_key(rows, fixes._key(f["key"]))}
    return {id(x): [new if t == old else t for t in x["teachers"]] for k, old, new in ((f["a"], f["x"], f["y"]), (f["b"], f["y"], f["x"])) for x in fixes.rows_of_key(rows, fixes._key(k)) if old in x["teachers"]}

def _blocked(m, spec, days, b, f):
    """the lessons of a teacher fix's key (of a trade's two keys) that a new teacher cannot take when they are, on the timetable m (b: its Busy) ->
    [(lesson id, the lesson in the way, why)]; the lesson in the way is None for a Must rule of the new teacher's, which moving another lesson does
    not help. A trade changes both keys at once: a lesson of one is in the way of another's only as it is taught after it"""
    takes = _takes(m["lessons"], f); ids = list(dict.fromkeys(x["id"] for x in m["lessons"] if id(x) in takes)); out = []
    new = {i: [dict(x, teachers=takes.get(id(x), x["teachers"])) for x in b.ids[i]] for i in ids}
    for i in ids:
        rows = b.ids[i]; now = _musts(m, spec, rows)
        rule = [t for k, t in _musts(m, spec, new[i]).items() if k not in now]
        if rule: out.append((i, None, rule[0])); continue
        had = {t for y in rows for t in y["teachers"]}   # as fixes.judge sees a teacher change: only a teacher who was not there can clash
        cand = [dict(y, teachers=[t for t in y["teachers"] if t not in had], classes=[], group=ENTIRE, rain="", room="") for y in new[i]]
        hit = _blocker(b, days, cand, set(ids))
        if not hit and f["kind"] == "trade": hit = _blocker(fixes.Busy(m, [x for j in ids if j != i for x in new[j]], base=b), days, cand, ())
        if hit: out.append((i, *hit))
    return out

def _either(blocked):
    """the lessons whose move helps blocked lessons -> [(lesson id, why)]: those in the way, then the blocked lessons themselves"""
    return [(y, why) for _, y, why in blocked if y is not None] + [(i, why) for i, _, why in blocked]

def _day_rules(m, spec, f, of=None):
    """{day: sentence} of the Must rules of a teacher's day ("Max periods in a row" and the like: their keys end |{day}) that the teacher fix or the trade f
    breaks anew on the timetable m (of: for that teacher only)"""
    takes = _takes(m["lessons"], f); names = {t for v in takes.values() for t in v}; near = [x for x in m["lessons"] if id(x) in takes or set(x["teachers"]) & names]
    was, out = fixes.rule_subjects(m, spec, near), {}
    for k, w in fixes.rule_subjects(m, spec, [dict(x, teachers=takes.get(id(x), x["teachers"])) for x in near]).items():
        if k in was or isinstance(k, tuple) or w.get("strength") != "Must": continue
        who, _, d = k.split(":", 2)[2].rpartition("|")
        if who in m["teacher_ix"] and d.isdigit() and of in (None, who): out.setdefault(int(d), w["text"])
    return out

def _in_the_way(m, spec, days, b, f, must):
    """the lessons whose move may help a refused fix on the timetable m (b: its Busy; must: the Must rules it breaks, as judged) ->
    [(lesson id, why)], in the order found: for a teacher fix or a trade those in the way of a new teacher, then the lessons of its keys that are
    blocked; when only a rule of a teacher's day refuses it, the lessons that teacher gets on the days it is broken on (all of the keys' when it names no
    day); for a move, swap or add those in the way of each lesson it places; none for a room (Busy names no lesson for one) or a delete"""
    if f["kind"] in ("teacher", "trade"):
        blocked = _blocked(m, spec, days, b, f)
        if blocked or not must: return _either(blocked)
        takes = _takes(m["lessons"], f); gets = [(x, t) for x in m["lessons"] if id(x) in takes for t in takes[id(x)] if t not in x["teachers"]]
        on = {t: _day_rules(m, spec, f, t) for t in dict.fromkeys(t for _, t in gets)}
        return [(x["id"], on[t][x["d"]]) for x, t in gets if x["d"] in on[t]] or [(x["id"], must[0]) for x, _ in gets]
    if f["kind"] not in ("move", "swap", "add"): return []
    after = helper._apply(m["lessons"], [f], spec, days); placed = after["touched"]
    hits = [_blocker(b, days, [x for x in after["lessons"] if x["id"] == i], placed) for i in sorted(placed)]
    return [h for h in hits if h]

def waiting(pool, fx):
    """what the fixes change of the lessons not placed (pool: their rows) when they are made on the draft: a teacher fix reaches every row of its
    key, a trade the rows of its two keys that the teacher who gives it up has -> (those rows as they are just before, the pool after). Nothing of pool is changed"""
    was = []
    for f in fx:
        if f["kind"] not in ("teacher", "trade"): continue
        takes = _takes(pool, f); was += [x for x in pool if id(x) in takes]
        pool = [dict(x, teachers=takes[id(x)]) if id(x) in takes else x for x in pool]
    return was, pool

def rechecked(m, spec, lessons, touched, was, fx=()):
    """the numbers of the typed rules (T1, T2 ...) that the fixes fx make one check again, sorted: verify.typed_again with these lessons on the
    timetable (touched and was: helper._apply's for the fixes) and with the lessons not placed (m["pool"]) that a teacher fix or a trade reaches"""
    return sorted({int(w["key"].split(":")[1]) for w in verify.typed_again(dict(m, lessons=lessons), spec, touched, list(was) + waiting(m.get("pool") or [], fx)[0])})

class _Search:
    """the search for one target. A list looked at is a node (moves, parts): moves the items of day_moves in it, first, each with the
    why of its lesson; parts the changes of step 5 in it after them, each (its place in direct's order, direct's candidate). The lists
    are judged in order of how many moves they have, and nothing of m or of what helper and fixes return is changed"""
    def __init__(self, m, spec, days, target, moved, deadline, stats, before, room, most, far):
        self.m, self.spec, self.days, self.target, self.w = m, spec, days, target, target["w"]
        self.moved, self.deadline, self.stats, self.before, self.room, self.most, self.far = moved, deadline, stats, before, room, most, far
        self.memo, self.bars, self.places = {}, {}, {}         # helper.chain's memo; day_moves' memo; (lesson id, candidate) -> the places it may go to
        self.seen, self.solved = set(), []                     # the lists looked at; the answers of the present number of moves
        self.refused, self.many = "", False                    # the judge's sentence about the change itself on m; whether more changes than MAX_DIRECT were needed
        self.blocked, self.own, self.given = {}, {}, {}        # for each candidate (its place) of a teacher change: _blocked on m, the lessons that get a new teacher, m with the change made

    # ------------------------------------------------------------ the change itself
    def _more(self, node, c):
        """direct's candidates on the timetable a list leaves (c: its chain): none about a lesson that an earlier target or the list itself moved or put in"""
        held = set(self.moved) | {i for x in node[0] for i in _ids(x["fix"])} | {x["id"] for x in c["lessons"] if x["id"] not in self.rows}
        return direct(dict(self.m, lessons=c["lessons"]), self.spec, self.days, self.target, self.m.get("pool") or (), held)[0]

    def _grow(self, node, c, failed):
        """a list that fits and leaves the warning open (c: its chain), carried on with one more change, the first that fits each time ->
        whether that settles it. The changes are direct's on the timetable the list leaves (a lesson still missing may be shorter, a
        day another); an add on a day the list has no add on comes first"""
        self._in_time(); more = self._more(node, c); days = {f["d"] for _, part in node[1] for f in part if f["kind"] == "add"}
        if len(node[1]) >= MAX_DIRECT: self.many |= bool(more); return False
        for j, part in sorted(enumerate(more), key=lambda x: x[1][0]["kind"] == "add" and x[1][0]["d"] in days):
            longer = (node[0], node[1] + ((j, part),))
            if not self._new(longer): continue
            how, c2 = self._look(longer)
            if how != "refused": return how == "solved" or self._grow(longer, c2, failed)
            failed.append((longer, self._ways(longer, how, c2)))
        return False

    # ------------------------------------------------------------ judging a list
    def _fixes(self, node): return [x["fix"] for x in node[0]] + [f for _, part in node[1] for f in part]
    def _cand(self, node): return node[1][0][0] if node[1] else None   # the place of a list's candidate in direct's order

    def _new(self, node):
        """whether the list was not looked at before (the same moves and changes in another order leave the same timetable, and each is allowed by itself)"""
        k = (frozenset(repr(x["fix"]) for x in node[0]), frozenset(repr(part) for _, part in node[1])); new = k not in self.seen; self.seen.add(k); return new

    def _in_time(self):
        if time.monotonic() > self.deadline: self.stats["late"] = True; raise _Stop

    def _look(self, node):
        """judge one list -> (how, its chain): "refused", "solved" (kept in self.solved) or "open": it fits and the warning stays. _Stop at a limit"""
        self._in_time()
        if self.stats["nodes"] >= MAX_NODES: raise _Stop
        self.stats["nodes"] += 1; fx = self._fixes(node); c = helper.chain(self.m, self.spec, self.days, fx, self.ctx, self.memo)
        while len(self.memo) > MAX_KEPT: del self.memo[next(iter(self.memo))]   # the oldest
        if no := _refusal(c):
            if not node[0] and no[0] == 0 and fx[0]["kind"] != "add" and (not self.refused or self._truer(node, no[1])): self.refused = no[1]   # said of the change on m as it is, not of a move or a place tried for it
            return "refused", c
        done = bool(fx) and _settled(self.m, self.spec, self.days, self.w, c["lessons"], self.before, self.room)   # the empty list is never an answer
        if (done or node[1]) and _at_once(c["lessons"], c["touched"]) - self.at_once: return "refused", c   # an answer, or a list to carry on with further changes, that puts two lessons of a key in one period
        if not done: return "open", c
        self.solved.append((node, c)); return "solved", c

    def _truer(self, node, why):
        """whether the sentence that refuses the first trade says more than the one that refuses the teacher change by itself, which may name a lesson the trade takes off the
        new teacher; not one that the teacher who gives the key up has another lesson then (that is about the other key's period)"""
        f = node[1][0][1][0]; return f["kind"] == "trade" and self._cand(node) == 1 and not why.startswith(f"{f['x']} is teaching ")

    # ------------------------------------------------------------ the lists with one move more
    def _ways(self, node, how, c):
        """the lessons whose move may help a list that is no answer -> [(lesson id, why)]: the ones in the way of the step the judge
        refused, or, where every step is allowed, the ones the clash or rule is about (no move settles a difference from step 5)"""
        if len(node[0]) >= self.most: return []   # no move may follow
        if how == "open": return [(i, f"The {self.target['kind']} needs it.") for i in helper.involved(dict(self.m, lessons=c["lessons"]), self.w)]
        if c["state"] in helper.OK: return []   # a Prefer rule, or two lessons of a key at once, rules it out: nothing is in the way
        i = len(c["steps"]) - 1; fx = self._fixes(node)
        mi, ci = (self.m, self.ctx) if i == 0 else helper._after(self.m, self.spec, self.days, fx[:i], self.memo)
        return _in_the_way(mi, self.spec, self.days, ci["busy"], fx[i], c["steps"][i]["must"])

    def _places(self, i, node):
        """lesson i's day_moves, for a list of the node's candidate. A lesson that is to have a new teacher goes by that teacher's Must rules: its day is barred, and a place left out, for those"""
        j = self._cand(node); own = i in self.own.get(j, ()); key = (i, j if own else None)
        if key not in self.places:
            self._in_time(); rows, bars, shut = self.rows[i], self.bars, None
            if own:
                d, given, now = rows[0]["d"], [x for x in self.given[j]["lessons"] if x["id"] == i], _musts(self.m, self.spec, rows)
                bars = {**bars, ("barred", i, d): barred(self.given[j], self.spec, self.days, i, d, self.m.get("pool") or ())}
                def shut(f):
                    at = (f["d"], f["p"]) if f["kind"] == "move" else (self.rows[f["b"]][0]["d"], self.rows[f["b"]][0]["p"])
                    return any(k not in now for k in _musts(self.m, self.spec, [dict(x, d=at[0], p=at[1]) for x in given]))
            self.places[key] = day_moves(self.m, self.spec, self.days, i, self.ctx, bars, self.moved, CAND_SLOTS, self.far, shut)
        return self.places[key]

    def _may(self, i):
        """whether a lesson may be moved at all: on the timetable, not a band, not moved by an earlier target"""
        return i in self.rows and i not in self.moved and not fixes._block(self.rows[i])

    def _still(self, node):
        """the blocked lessons of a list's teacher change that stay blocked after its moves, whatever else is moved: neither the lesson nor the one in its way is"""
        done = {i for x in node[0] for i in _ids(x["fix"])}
        return [b for b in self.blocked.get(self._cand(node), ()) if b[0] not in done and b[1] not in done]

    def _take_over(self, j, f):
        """work out what the moves to come for candidate j, the teacher change or trade f, go by -> whether any may help: each blocked lesson, or the one in its way, may be moved"""
        takes = _takes(self.m["lessons"], f); self.own[j] = {x["id"] for x in self.m["lessons"] if id(x) in takes}
        self.given[j] = dict(self.m, lessons=helper._apply(self.m["lessons"], [f], self.spec, self.days)["lessons"])
        self.blocked[j] = _blocked(self.m, self.spec, self.days, self.ctx["busy"], f)
        return all(self._may(y) or self._may(i) for i, y, _ in self.blocked[j])

    def _children(self, failed):
        """each list that is no answer with one move more, put first: of a lesson that may help it and that the list has not moved already.
        One with more lessons to be moved still than moves may follow is left out"""
        for (moves, parts), ways in failed:
            done = {i for x in moves for i in _ids(x["fix"])}; able = {}
            for i, why in ways:
                if i not in done and self._may(i): able.setdefault(i, why)
            for i, why in list(able.items())[:CAND_LESSONS]:
                for x in self._places(i, (moves, parts)):
                    child = ((dict(x, why=why),) + moves, parts); least = len({("in the way", y) if y is not None else ("blocked", b) for b, y, _ in self._still(child)})
                    if not _ids(x["fix"]) & done and least <= self.most - len(child[0]) and self._new(child): yield child

    def run(self, cands):
        """the best answer of the fewest moves that has one, or None"""
        self.ctx = fixes._ctx(self.m); self.rows = self.ctx["busy"].ids   # lesson id -> its rows
        self.at_once = _at_once(self.m["lessons"])   # the lessons of a key that are at once already are left so
        level = [n for n in ([((), ((j, c),)) for j, c in enumerate(cands)] or [((), ())]) if self._new(n)]
        try:
            for k in range(self.most + 1):
                failed, opened = [], []
                for node in level:
                    if still := self._still(node): self._in_time(); failed.append((node, _either(still))); continue   # the new teacher cannot take it then: the judge would refuse it
                    how, c = self._look(node)
                    if how == "open" and node[1]: opened.append((node, c))
                    elif how != "solved": failed.append((node, self._ways(node, how, c)))
                for node, c in opened[:MAX_GROWN]:
                    if self.solved or self._grow(node, c, failed) or self.many: break
                if k == 0 and opened: self.refused = ""   # a change fits by itself: what was said of another candidate is not why there is no answer
                if self.solved or k == self.most: break
                if k == 0 and self.target["kind"] == "teachers":
                    able = {j for j, (f, *_) in enumerate(cands) if self._take_over(j, f)}; failed = [x for x in failed if self._cand(x[0]) in able]   # a candidate with a lesson that stays blocked whatever moves takes nothing from the others
                    if not failed: break
                level = self._children(failed)   # made as they are looked at
        except _Stop: pass   # the best found so far
        return self._best()

    # ------------------------------------------------------------ the answer
    def _best(self):
        """the answer ranked first: the fewest lessons moved (a swap moves two), the fewest of them to another day, the fewest typed rules touched, the
        nearest moves, the fewest allowances gone over, then direct's order, then the words"""
        at = {x["id"]: (x["d"], x["p"]) for x in self.m["lessons"]}
        def entry(node, c):
            moved = {x["id"] for x in c["lessons"] if x["id"] in at and at[x["id"]] != (x["d"], x["p"])}
            moves, parts = node; other = sum(x["other"] for x in moves); fx = self._fixes(node)
            typed = set(rechecked(self.m, self.spec, c["lessons"], c["touched"], c["was"], fx))
            rank = (len(moved), other, len(typed), sum(x["dist"] for x in moves), sum(len(j["prefer"]) for j in c["steps"]), tuple(j for j, _ in parts), repr(fx))
            return rank, dict(fixes=fx, moved=moved, other=other, typed=typed, why=[x["why"] for x in moves] + [self._why(f) for _, part in parts for f in part])
        return min((entry(*s) for s in self.solved), key=lambda e: e[0])[1] if self.solved else None

    def _why(self, f):
        """why a change of step 5 itself is made"""
        row5 = verify.planned_rows(self.spec).get(helper._dep_parts(self.target["key"])[0]) or {}
        n = row5.get("periods", 0); plan = f"Step 3 plans {n} period{'' if n == 1 else 's'} of it."
        if f["kind"] == "teacher": return f"Step 5 now gives it to {fixes._names(f['teachers'])}."
        if f["kind"] == "trade": return f"Step 5 now gives {verify._name(fixes._key(f['a']))} to {f['y']} and {verify._name(fixes._key(f['b']))} to {f['x']}."
        if f["kind"] == "add": return "It was not on the timetable." if self.target["kind"] == "missing" else plan
        if f["kind"] == "delete": return plan
        return f"Step 3 asks for {row5['room_kind']}." if self.target["kind"] == "venue" else "It needs a room that seats the group."

def solve(m, spec, days, target, pool, moved, deadline, stats=None, max_moves=None, far=False):
    """the best list of fixes for one target on the timetable m as it is now (the earlier targets' fixes are in it) -> dict(fixes, moved,
    other, typed, why), or None when there is none within the limits. The list is at most max_moves (default MAX_MOVES) moves and swaps
    (never of a band or of a lesson in moved; each on its own day unless that day is barred for it or far is set), then the change itself; it puts no two
    lessons of one key of step 5 in the same period that were not on m. fixes is [] when the warning is gone already; moved: the ids of the
    lessons whose day or period changes; other: how many of them go to another day; typed: the numbers of the typed rules to check again; why:
    a plain sentence for each fix. deadline: a time.monotonic(). stats (a dict, when given) gets nodes (the lists judged), reason (the
    Needs-you sentence when there is no answer, else "") and late (the deadline came first). Nothing it is given is changed"""
    s = {} if stats is None else stats; s.update(nodes=0, reason="", late=False); w = target["w"]
    pool = m.get("pool") or pool or []; m = m if m.get("pool") is pool else dict(m, pool=pool)
    if time.monotonic() > deadline: s.update(late=True, reason=LATE); return None
    before, room = helper._before(m, spec, w), _room_clash(m, w)
    if _gone(m, spec, days, w, before, room): return dict(fixes=[], moved=set(), other=0, typed=set(), why=[])
    if w.get("crit") == "noteacher": s["reason"] = helper.NO_TEACHER; return None   # no move gives it one
    if w.get("crit") == "notplaced": s["reason"] = NOT_PLACED; return None
    if w["key"].startswith("clash:bands:"): s["reason"] = BAND; return None
    search = _Search(m, spec, days, target, moved, deadline, s, before, room, MAX_MOVES if max_moves is None else max_moves, far); cands, needs = direct(m, spec, days, target, pool, moved)
    if not cands and target["kind"] not in ("clash", "rule"): s["reason"] = needs or NO_FIT; return None
    got = search.run(cands)
    if got is not None: s["late"] = False
    else: s["reason"] = LATE if s["late"] else TOO_MANY if search.many else search.refused or NO_FIT
    return got

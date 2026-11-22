"""Re-fit: the fewest lesson changes that make the draft fit the setup again. Here are the warnings it works on, the change
itself for each, where a lesson may go, and the search for the list of fixes that settles one warning."""
import collections, re, time
import helper, fixes
from ttgen import verify
from ttgen.export import ENTIRE
from ttgen.spec import single_rooms, whole as whole_n

MAX_MOVES = 3        # the most moves and swaps in one answer
MAX_DIRECT = 8       # the most changes of step 5 itself in one answer
MAX_NODES = 250      # the most search steps (lists judged) for one warning
MAX_KEPT = 40        # the timetables, each with its index, kept while looking
CAND_LESSONS = 4     # the lessons tried for a change
CAND_SLOTS = 8       # the places tried for a lesson
BUDGET_S = 30.0      # the most seconds for a whole re-fit

NO_FIT = "No list of up to 3 moves fits it."
BAND = "This changes the band itself: change it on the board, or ask the agent for a new timetable."
SPLIT = "Its lessons are taught by different teachers: change them on the board."
NOT_ONE = "More than one teacher changes: change it on the board."
LATE = "Not looked at in time; run Re-fit again."
OVER = " over the allowance."   # how fixes.judge ends a teacher's allowance line: the only Prefer reason an answer may give

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

def _day_periods(lessons, cls):
    """{day: the periods the class has on it}"""
    per = {}
    for g in {x["id"]: x for x in lessons if cls in x["classes"]}.values(): per[g["d"]] = per.get(g["d"], 0) + g["n"]
    return per

def _deletes(m, spec, days, pool, k, e, rows):
    c = fixes._ctx(m); L = m["lessons"]; per = _day_periods(L, _class_of(k, e, rows))
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

# ----------------------------------------------------------------------------------------------- where a lesson may go
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
            if busy.lesson_time(moved, d, p, n): return True
            return any(w.get("strength") == "Must" for w in verify.rules(dict(m, lessons=moved), spec)[0])
        out = all(closed(p) for p in range(m["NP"] - n + 1))
    if memo is not None: memo[key] = out
    return out

def day_moves(m, spec, days, lesson_id, ctx, memo, moved, limit=CAND_SLOTS):
    """the moves and swaps of one lesson the rules allow now, best first -> [dict(fix, other, dist)]: the same day's "ok" slots nearest
    period first (a swap only with a lesson that is not a band and not in moved), then, only when the lesson's own day is barred
    (see barred), plain moves to other days (nearest day, then nearest period) with other=True; dist is the periods moved, 10 per
    day for another day. [] for a band lesson, one in moved, or one not on the timetable. At most limit items. Never changes m"""
    pool = m.get("pool") or (); rows = [x for x in m["lessons"] if x["id"] == lesson_id]
    if not rows or lesson_id in moved or fixes._block(rows) or any(x["id"] == lesson_id for x in pool): return []
    d0, p0 = rows[0]["d"], rows[0]["p"]
    ok = [s for s in fixes.slots(m, spec, days, lesson_id, pool, extras=False, ctx=ctx) if s["state"] == "ok"]
    same = []
    for s in ok:
        if s["d"] != d0: continue
        if s["swap"] is not None:
            o = [x for x in m["lessons"] if x["id"] == s["swap"]]
            if not o or fixes._block(o) or s["swap"] in moved: continue
            fix = dict(kind="swap", a=lesson_id, b=s["swap"])
        else: fix = dict(kind="move", id=lesson_id, d=s["d"], p=s["p"])
        same.append((abs(s["p"] - p0), s["p"], dict(fix=fix, other=False, dist=abs(s["p"] - p0))))
    out = [x[2] for x in sorted(same, key=lambda x: x[:2])]
    if barred(m, spec, days, lesson_id, d0, pool, memo):
        out = []   # a same-day place keeps the lesson on a barred day, where the Must rule stays broken
        far = sorted((s for s in ok if s["d"] != d0 and s["swap"] is None), key=lambda s: (abs(s["d"] - d0), s["d"], abs(s["p"] - p0), s["p"]))
        out += [dict(fix=dict(kind="move", id=lesson_id, d=s["d"], p=s["p"]), other=True, dist=10 * abs(s["d"] - d0) + abs(s["p"] - p0)) for s in far]
    return out[:limit]


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


# ----------------------------------------------------------------------------------------------- the search for one target
class _Stop(Exception):
    """the search has reached its limit of steps or of time"""

def _ids(fix): return {fix["a"], fix["b"]} if fix["kind"] == "swap" else {fix["id"]}

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

def _gone(m, spec, days, w, before, room):
    """whether an earlier target's fixes have settled the warning on m already. settles cannot say it of a clash about one lesson
    (in a break, past the day, without a teacher): that is gone with the lesson, or, for its place, once the lesson is elsewhere"""
    wh = w.get("where") or {}
    if w.get("kind") != "clash": return helper.settles(m, spec, days, w, m["lessons"], before)
    if room: return not _over(m, m["lessons"], *room)
    if wh.get("id") is None: return bool(before.get("named")) and helper.settles(m, spec, days, w, m["lessons"], before)   # a double booking
    x = next((x for x in m["lessons"] if x["id"] == wh["id"] and x["group"] == wh.get("row", x["group"])), None)
    return x is None or (w.get("crit") != "noteacher" and (m["days"][x["d"]], x["p"]) != (wh.get("day"), wh.get("period")))

def _blocker(b, rows, ignore):
    """(the lesson in the way of these rows where they are, why), or None: b.blocker, which names the lesson helper._alone would too"""
    x = rows[0]; y = b.blocker(rows, x["d"], x["p"], x["n"], ignore=ignore)
    return None if y is None else (y, b.clash(rows, x["d"], x["p"], x["n"], ignore=ignore).replace(" is teaching ", " teaches ", 1))

def _blocked(m, b, f):
    """the lessons of a teacher fix's key whose time a new teacher cannot take on the timetable m (b: its Busy) -> [(lesson id, the lesson in the way, why)]"""
    ids = list(dict.fromkeys(x["id"] for x in helper._of_key(m["lessons"], fixes._key(f["key"])))); out = []
    for i in ids:   # as fixes.judge sees a teacher change: only a teacher who was not there can clash
        had = {t for y in b.ids[i] for t in y["teachers"]}
        hit = _blocker(b, [dict(y, teachers=[t for t in f["teachers"] if t not in had], classes=[], group=ENTIRE, rain="", room="") for y in b.ids[i]], set(ids))
        if hit: out.append((i, *hit))
    return out

def _either(blocked):
    """the lessons whose move helps blocked lessons -> [(lesson id, why)]: those in the way, then the blocked lessons themselves"""
    return [(y, why) for _, y, why in blocked] + [(i, why) for i, _, why in blocked]

def _in_the_way(m, spec, days, b, f):
    """the lessons whose move may help a refused fix on the timetable m (b: its Busy) -> [(lesson id, why)], in the order found: for a
    teacher fix those in the way of a new teacher, then the lessons of its key they are in the way of; for a move, swap or add those in
    the way of each lesson it places; none for a room (Busy names no lesson for one), a delete or a rule"""
    if f["kind"] == "teacher": return _either(_blocked(m, b, f))
    if f["kind"] not in ("move", "swap", "add"): return []
    after = helper._apply(m["lessons"], [f], spec, days); placed = after["touched"]
    hits = [_blocker(b, [x for x in after["lessons"] if x["id"] == i], placed) for i in sorted(placed)]
    return [h for h in hits if h]

class _Search:
    """the search for one target. A list looked at is a node (moves, parts): moves the items of day_moves in it, first, each with the
    why of its lesson; parts the indexes of direct's candidates in it, after them. The lists are judged in order of how many moves
    they have, and nothing of m or of what helper and fixes return is changed"""
    def __init__(self, m, spec, days, target, cands, moved, deadline, stats, before, room):
        self.m, self.spec, self.days, self.target, self.w = m, spec, days, target, target["w"]
        self.cands, self.moved, self.deadline, self.stats, self.before, self.room = cands, moved, deadline, stats, before, room
        self.ctx = fixes._ctx(m); self.rows = self.ctx["busy"].ids   # lesson id -> its rows
        self.memo, self.bars, self.places = {}, {}, {}               # helper.chain's memo; day_moves' memo; lesson id -> its day_moves
        self.seen, self.solved, self.refused = set(), [], ""         # the lists looked at; the answers of the present depth; the judge's last sentence about the change itself
        self.blocked = []                                            # the lessons of a teacher change no new teacher can take on m, as _blocked gives them
        self.key = helper._dep_parts(target["key"])[0]; self.row5 = verify.planned_rows(spec).get(self.key) or {}
        if cands: self._about()

    # ------------------------------------------------------------ several changes of step 5 in one answer
    def _about(self):
        """self.about: for each candidate, the periods it adds or takes away, its day, the periods its class has that day (a delete) and the
        row whose room it changes; self.need: the periods the key is short of step 5's plan, or over it"""
        L, pool = self.m["lessons"], self.m.get("pool") or (); cls = _class_of(self.key, self.row5 or None, helper._of_key(L, self.key)); per = _day_periods(L, cls)
        def about(f):
            if f["kind"] == "add": return dict(n=f["n"], d=f["d"], load=None, room=None)
            if f["kind"] == "delete": x = self.rows[f["id"]][0]; return dict(n=x["n"], d=x["d"], load=per.get(x["d"], 0), room=None)
            return dict(n=0, d=None, load=None, room=(f["id"], f["group"]) if f["kind"] == "room" else None)
        self.about = [about(c[0]) for c in self.cands]
        have = verify.placed(dict(self.m, lessons=list(L) + list(pool))).get(self.key, {}).get("periods", 0); self.need = abs(self.row5.get("periods", 0) - have)

    def _more(self, parts):
        """the candidates that may follow these: none that changes the same room again or goes past the periods needed. An add on a day
        without one comes first, and the delete from the day that is then the class's fullest; else they keep direct's order"""
        used = [self.about[j] for j in parts]; n = sum(a["n"] for a in used); rooms = {a["room"] for a in used if a["room"]}
        def order(j):
            a = self.about[j]; there = [u for u in used if u["d"] == a["d"]]
            return (bool(there) if a["load"] is None else sum(u["n"] for u in there) - a["load"], j)
        left = [j for j, a in enumerate(self.about) if j not in parts and a["room"] not in rooms and n + a["n"] <= self.need]
        return sorted(left, key=order) if len(parts) < MAX_DIRECT else []

    def _grow(self, node, failed):
        """a list that fits and leaves the warning open, with further candidates put after it, the first that fits each time -> whether that settles it"""
        for j in self._more(node[1]):
            longer = (node[0], node[1] + (j,))
            if not self._new(longer): continue
            how, c = self._look(longer)
            if how != "refused": return how == "solved" or self._grow(longer, failed)
            failed.append((longer, self._ways(longer, how, c)))
        return False

    # ------------------------------------------------------------ judging a list
    def _fixes(self, node): return [x["fix"] for x in node[0]] + [f for j in node[1] for f in self.cands[j]]

    def _new(self, node):
        """whether the list was not looked at before (the same moves and changes in another order leave the same timetable, and each is allowed by itself)"""
        k = (frozenset(repr(x["fix"]) for x in node[0]), frozenset(node[1])); new = k not in self.seen; self.seen.add(k); return new

    def _in_time(self):
        if time.monotonic() > self.deadline: self.stats["late"] = True; raise _Stop

    def _look(self, node):
        """judge one list -> (how, its chain): "refused", "solved" (kept in self.solved) or "open": it fits and the warning stays. _Stop at a limit"""
        self._in_time()
        if self.stats["nodes"] >= MAX_NODES: raise _Stop
        self.stats["nodes"] += 1; fx = self._fixes(node); c = helper.chain(self.m, self.spec, self.days, fx, self.ctx, self.memo)
        while len(self.memo) > MAX_KEPT: del self.memo[next(iter(self.memo))]   # the oldest
        if no := _refusal(c):
            if no[0] >= len(node[0]): self.refused = no[1]   # what is said of a move tried for it would not be about the warning
            return "refused", c
        if not fx or not _settled(self.m, self.spec, self.days, self.w, c["lessons"], self.before, self.room): return "open", c   # the empty list is never an answer
        self.solved.append((node, c)); return "solved", c

    # ------------------------------------------------------------ the lists with one move more
    def _ways(self, node, how, c):
        """the lessons whose move may help a list that is no answer -> [(lesson id, why)]: the ones in the way of the step the judge
        refused, or, where every step is allowed, the ones the clash or rule is about (no move settles a difference from step 5)"""
        if how == "open": return [(i, f"The {self.target['kind']} needs it.") for i in helper.involved(dict(self.m, lessons=c["lessons"]), self.w)]
        if c["state"] in helper.OK: return []   # a Prefer rule rules it out: nothing is in the way
        i = len(c["steps"]) - 1; fx = self._fixes(node)
        mi, ci = (self.m, self.ctx) if i == 0 else helper._after(self.m, self.spec, self.days, fx[:i], self.memo)
        return _in_the_way(mi, self.spec, self.days, ci["busy"], fx[i])

    def _places(self, i):
        if i not in self.places: self._in_time(); self.places[i] = day_moves(self.m, self.spec, self.days, i, self.ctx, self.bars, self.moved, CAND_SLOTS)
        return self.places[i]

    def _may(self, i):
        """whether a lesson may be moved at all: on the timetable, not a band, not moved by an earlier target"""
        return i in self.rows and i not in self.moved and not fixes._block(self.rows[i])

    def _still(self, moves):
        """the blocked lessons of a teacher change that stay blocked after these moves, whatever else is moved: neither the lesson nor the one in its way is"""
        done = {i for x in moves for i in _ids(x["fix"])}
        return [b for b in self.blocked if b[0] not in done and b[1] not in done]

    def _children(self, failed):
        """each list that is no answer with one move more, put first: of a lesson that may help it and that the list has not moved already.
        One with more lessons still in the way than moves may follow is left out"""
        for (moves, parts), ways in failed:
            done = {i for x in moves for i in _ids(x["fix"])}; able = {}
            for i, why in ways:
                if i not in done and self._may(i): able.setdefault(i, why)
            for i, why in list(able.items())[:CAND_LESSONS]:
                for x in self._places(i):
                    child = ((dict(x, why=why),) + moves, parts); left = MAX_MOVES - len(child[0])
                    if not _ids(x["fix"]) & done and len({y for _, y, _ in self._still(child[0])}) <= left and self._new(child): yield child

    def run(self):
        """the best answer of the fewest moves that has one, or None"""
        level = [n for n in ([((), (j,)) for j in range(len(self.cands))] or [((), ())]) if self._new(n)]
        try:
            for k in range(MAX_MOVES + 1):
                failed, opened = [], []
                for node in level:
                    if still := self._still(node[0]): self._in_time(); failed.append((node, _either(still))); continue   # the new teacher is busy then: the judge would refuse it
                    how, c = self._look(node)
                    if how == "open" and node[1]: opened.append(node)
                    elif how != "solved": failed.append((node, self._ways(node, how, c)))
                for node in opened:
                    if self.solved or self._grow(node, failed): break
                if self.solved: break
                if k == 0 and self.target["kind"] == "teachers":
                    self.blocked = _blocked(self.m, self.ctx["busy"], self.cands[0][0])
                    if not all(self._may(y) or self._may(i) for i, y, _ in self.blocked): break   # one of them stays blocked whatever moves
                level = self._children(failed)   # made as they are looked at
        except _Stop: pass   # the best found so far
        return self._best()

    # ------------------------------------------------------------ the answer
    def _best(self):
        """the answer ranked first: the fewest lessons moved (a swap moves two), the fewest moves to another day, the fewest typed rules touched, the
        nearest moves, the fewest allowances gone over, then direct's order, then the words"""
        at = {x["id"]: (x["d"], x["p"]) for x in self.m["lessons"]}
        def entry(node, c):
            moved = {x["id"] for x in c["lessons"] if x["id"] in at and at[x["id"]] != (x["d"], x["p"])}
            typed = {int(w["key"].split(":")[1]) for w in verify.typed_again(dict(self.m, lessons=c["lessons"]), self.spec, c["touched"], c["was"])}
            moves, parts = node; other = sum(x["other"] for x in moves); fx = self._fixes(node)
            rank = (len(moved), other, len(typed), sum(x["dist"] for x in moves), sum(len(j["prefer"]) for j in c["steps"]), parts, repr(fx))
            return rank, dict(fixes=fx, moved=moved, other=other, typed=typed, why=[x["why"] for x in moves] + [self._why(f) for j in parts for f in self.cands[j]])
        return min((entry(*s) for s in self.solved), key=lambda e: e[0])[1] if self.solved else None

    def _why(self, f):
        """why a change of step 5 itself is made"""
        n = self.row5.get("periods", 0); plan = f"Step 3 plans {n} period{'' if n == 1 else 's'} of it."
        if f["kind"] == "teacher": return f"Step 5 now gives it to {fixes._names(f['teachers'])}."
        if f["kind"] == "add": return "It was not on the timetable." if self.target["kind"] == "missing" else plan
        if f["kind"] == "delete": return plan
        return f"Step 3 asks for {self.row5['room_kind']}." if self.target["kind"] == "venue" else "It needs a room that seats the group."

def solve(m, spec, days, target, pool, moved, deadline, stats=None):
    """the best list of fixes for one target on the timetable m as it is now (the earlier targets' fixes are in it) -> dict(fixes, moved,
    other, typed, why), or None when there is none within the limits. The list is at most MAX_MOVES moves and swaps (never of a band or of
    a lesson in moved; each on its own day unless that day is barred for it), then the change itself. fixes is [] when the warning is
    gone already; moved: the ids of the lessons whose day or period changes; other: how many moves go to another day; typed: the numbers
    of the typed rules to check again; why: a plain sentence for each fix. deadline: a time.monotonic(). stats (a dict, when given) gets
    nodes (the lists judged), reason (the Needs-you sentence when there is no answer, else "") and late (the deadline came first).
    Nothing it is given is changed"""
    s = {} if stats is None else stats; s.update(nodes=0, reason="", late=False); w = target["w"]
    pool = m.get("pool") or pool or []; m = m if m.get("pool") is pool else dict(m, pool=pool)
    if time.monotonic() > deadline: s.update(late=True, reason=LATE); return None
    before, room = helper._before(m, spec, w), _room_clash(m, w)
    if _gone(m, spec, days, w, before, room): return dict(fixes=[], moved=set(), other=0, typed=set(), why=[])
    if w.get("crit") == "noteacher": s["reason"] = helper.NO_TEACHER; return None   # no move gives it one
    cands, needs = direct(m, spec, days, target, pool)
    cands = [c for c in cands if not (c[0]["kind"] == "delete" and c[0]["id"] in moved)]   # an earlier target moved it: the list would undo itself
    if not cands and target["kind"] not in ("clash", "rule"): s["reason"] = needs or NO_FIT; return None
    search = _Search(m, spec, days, target, cands, moved, deadline, s, before, room); got = search.run()
    if got is not None: s["late"] = False
    else: s["reason"] = LATE if s["late"] else search.refused or NO_FIT
    return got

"""Timetable solver: OR-Tools CP-SAT over the lessons, blocks and rules of a setup spec.

Model in one paragraph: every unit (a block of groups that run together, a group on its own, or a whole-class
subject for one class) needs a set of lessons (full-length and short). Each lesson is an interval whose start is
chosen from the teaching periods of the unit's level (Day structure 'L', or 'A' after-school at a cost).
Students: for every class, each kind of student (from the Students sheet, or one per level tag) must not have two
lessons at once; whole-class lessons never overlap a banded lesson that lists the class. Teachers never overlap.
Room kinds are cumulative resources. Rules from '7 Rules' add or remove start positions, fixed busy times, per-day
limits, alignment and day separation. The objective keeps after-school use and broken 'Prefer' rules low.
Given a previous timetable, the search starts from it and each lesson that moves costs W_MOVE, so a tweak moves as few
lessons as it can (cheaper than bending a Prefer rule or pushing a lesson after school)."""
import collections, math, re, time
from ortools.sat.python import cp_model
from .reader import derive
from .spec import WEEKDAYS, family as _family, periods_by_day, trim_day

W_PREF, W_SLACK, W_MOVE = 60, 40, 10


class Problem:
    def __init__(self, spec):
        self.spec = spec; self.warn = derive(spec)
        sc = spec["school"]; self.NP = int(sc["periods_per_day"]); self.levels = list(sc["levels"])
        ds = spec["day_structure"]
        lv0 = next((lv for lv in self.levels if lv in ds), None)
        if lv0 is None: raise ValueError("Day structure is empty.")
        self.days = list(ds[lv0].keys()); self.ND = len(self.days)
        self.grid = {lv: [(ds.get(lv, {}).get(d) or "." * self.NP).ljust(self.NP, ".")[:self.NP] for d in self.days] for lv in self.levels}
        self.keep = periods_by_day(sc, self.days)   # Settings 'Lessons end by (...)': later periods are no school on those days
        self.grid = {lv: [trim_day(row, self.keep.get(d)) for d, row in zip(self.days, rows)] for lv, rows in self.grid.items()}
        self.cls = {c["class"]: c for c in spec["classes"]}
        self.level_of = {c["class"]: c["level"] for c in spec["classes"]}
        self.rows = [x for x in spec["lessons"] if x.get("periods") and x.get("classes")]
        self.tdept = {t["name"]: t.get("dept") for t in spec["teachers"]}
        self._units()
        self._rooms()

    # ---------------------------------------------------------------- rooms: kind, purpose, seats, weeks
    def _rooms(self):
        sp = self.spec; num = lambda v: int(v) if isinstance(v, (int, float)) and v > 0 else None
        self.room_kind = {v["room"]: v.get("kind") or "classroom" for v in sp["venues"]}
        self.seats = {v["room"]: num(v.get("capacity")) for v in sp["venues"]}
        self.only_for = {v["room"]: set(v.get("only_for") or []) for v in sp["venues"]}
        self.room_cap = {v["room"]: 1 for v in sp["venues"]}   # classes at once
        for r in sp.get("rules", []):
            if r.get("rule") == "At most N at once" and r.get("scope") == "Room" and r.get("target") in self.room_cap and r.get("number") \
                    and str(r.get("strength") or "Must") == "Must": self.room_cap[r["target"]] = int(r["number"])
        self.two_weeks = any(d.startswith("Even") for d in self.days)
        self.odd_day = [not d.startswith("Even") for d in self.days]
        code_n = collections.Counter(g for s in sp.get("students", []) for g in s.get("groups") or [])
        self._group_size = lambda r: code_n.get(r["code"]) or (int(r["students"]) if isinstance(r.get("students"), (int, float)) and r["students"] > 0 else None)
        self._allowed = {}

    def size(self, r, unit):
        """students in this row's group: a whole-class lesson's class size, else the Students sheet count for its code, else
        the row's Students number (None when unknown: no seat limit)"""
        if r["code"] == "Entire Class" and unit["kind"] == "class":
            n = self.cls.get(unit["classes"][0], {}).get("size"); return int(n) if isinstance(n, (int, float)) and n > 0 else None
        return self._group_size(r)

    def for_ok(self, room, r):
        f = self.only_for.get(room)
        return not f or bool({r["subject"], r.get("dept"), r["level"]} & f)

    def allowed(self, r, unit, week=None):
        """(room kind, rooms this row's group may use, size, oversize) in that week ('Odd' / 'Even' / None for any): rooms of its
        kind kept for it or for anyone, that seat it; when none seats it, every such room (oversize, flagged by the checks)"""
        kind = r["room_kind"] or "classroom"
        if r.get("room_weeks") and self.two_weeks and week and week != r["room_weeks"]: kind = "classroom"   # its other week: a classroom
        key = (id(r), unit["classes"][0] if unit["kind"] == "class" else "", kind)
        if key not in self._allowed:
            n = self.size(r, unit)
            ok = [x for x, k in self.room_kind.items() if k == kind and self.for_ok(x, r)]
            fit = [x for x in ok if n is None or self.seats[x] is None or self.seats[x] >= n]
            self._allowed[key] = (kind, frozenset(fit or ok), n, bool(ok) and not fit)
        return self._allowed[key]

    def week_limited(self, r):
        return bool(r.get("room_weeks") and self.two_weeks)

    # ---------------------------------------------------------------- units and lessons
    def _units(self):
        U = []; byblock = collections.OrderedDict()
        for r in self.rows:
            if r.get("block"): byblock.setdefault(r["block"], []).append(r)
        binfo = {b["block"]: b for b in self.spec["blocks"]}
        seen = collections.Counter()   # key: the same unit across solves, even after rows are added or removed
        for name, rs in byblock.items():
            cl = list(dict.fromkeys((binfo.get(name, {}).get("classes") or []) + [c for r in rs for c in r["classes"]]))
            U.append(dict(id=f"B:{name}", key=f"B:{name}", kind="block", name=name, level=binfo.get(name, {}).get("level") or rs[0]["level"], classes=cl, rows=rs))
        for r in self.rows:
            if r.get("block"): continue
            if r.get("code_override"):
                U.append(dict(id=f"G:{r['code']}", key=f"G:{r['code']}", kind="group", name=r["code"], level=r["level"], classes=list(r["classes"]), rows=[r]))
            else:
                for c in r["classes"]:
                    k = f"C:{c}:{r['subject']}"; seen[k] += 1
                    U.append(dict(id=f"C:{c}:{r['subject']}:{len(U)}", key=f"{k}#{seen[k]}", kind="class", name=f"{c} {r['subject']}", level=r["level"], classes=[c], rows=[r]))
        for u in U:
            cnt = collections.Counter()
            for r in u["rows"]:
                if r.get("pattern"): rc = collections.Counter(int(v) for v in r["pattern"])   # lesson lengths set by hand (Adjust: shorter / longer)
                else:
                    rc = collections.Counter({r["length"]: r["full"]})
                    if r["short"]: rc[r["length"] - 1] += r["short"]
                for ln, n in rc.items(): cnt[ln] = max(cnt[ln], n)
                r["_counts"] = rc
            u["lessons"] = [(ln, i) for ln in sorted(cnt, reverse=True) for i in range(cnt[ln])]
            if u["level"] not in self.grid: u["level"] = self.level_of.get(u["classes"][0], self.levels[0])
        self.units = U

    def starts(self, level, ln):
        ok = "LA" if self.spec["school"].get("after_school", True) else "L"   # Settings: after-school slot allowed (No: never use 'A')
        out = []
        for d, row in enumerate(self.grid[level]):
            for p in range(self.NP - ln + 1):
                seg = row[p:p + ln]
                if all(ch in ok for ch in seg): out.append((d * self.NP + p, seg.count("A")))
        return out

    # ---------------------------------------------------------------- rule helpers
    def rule_positions(self, r):
        days = [i for i, d in enumerate(self.days) if self._day_ok(d, r)]
        a = r.get("from"); b = r.get("to")
        a = int(a) if a not in (None, "") else 0; b = int(b) if b not in (None, "") else self.NP - 1
        return {d * self.NP + p for d in days for p in range(a, b + 1)}, days
    def _day_ok(self, dname, r):
        wk, dy = str(r.get("week") or "Both"), str(r.get("day") or "All")
        if wk in ("Odd", "Even") and not dname.startswith(wk): return False
        return dy == "All" or dname.split()[-1][:3] == dy[:3]

    def students_profiles(self):
        """{class: [ {unit_id: Counter(len->count)} ]}"""
        code_row = {r["code"]: r for r in self.rows if r["code"] != "Entire Class"}
        unit_of_row = {id(r): u for u in self.units for r in u["rows"]}
        prof = collections.defaultdict(list); seen = set()
        for s in self.spec.get("students", []):
            if not s.get("class") or not s.get("groups"): continue
            use = {}
            for g in s["groups"]:
                r = code_row.get(g)
                if not r: continue
                u = unit_of_row[id(r)]; c = use.setdefault(u["id"], collections.Counter())
                for ln, n in r["_counts"].items(): c[ln] = max(c[ln], n)
            key = (s["class"], tuple(sorted((k, tuple(sorted(v.items()))) for k, v in use.items())))
            if key not in seen: seen.add(key); prof[s["class"]].append(use)
        covered = set(prof)
        for c in self.cls:
            if c in covered: continue
            divs = [u for u in self.units if u["kind"] != "class" and c in u["classes"]]
            tags = collections.defaultdict(set)
            for u in divs:
                for r in u["rows"]: tags[r["tag"]].add(_family(r["subject"]))
            tl = [t for t in tags if t not in (None, "-")] or ["-"]
            for T in tl:
                use = {}
                for u in divs:
                    rs = [r for r in u["rows"] if r["tag"] == T]
                    if not rs:
                        fams = {_family(r["subject"]) for r in u["rows"]}
                        if T != "-" and fams & tags[T]: continue
                        rs = u["rows"]
                    cc = collections.Counter()
                    for r in rs:
                        for ln, n in r["_counts"].items(): cc[ln] = max(cc[ln], n)
                    use[u["id"]] = cc
                prof[c].append(use)
        return prof

def state_key(u):
    """a unit's name in a timetable state (staged solve): its block, its group code, or its class and subject"""
    return ("B", u["name"]) if u["kind"] == "block" else ("G", u["name"]) if u["kind"] == "group" else ("C", u["classes"][0], u["rows"][0]["subject"])

def units_for(P, r):
    """the units (blocks, groups, class lessons) a rule row applies to"""
    sc, tg, sj = r.get("scope"), str(r.get("target") or ""), r.get("subject")
    def sub_ok(u): return not sj or any(x["subject"] == sj for x in u["rows"])
    if sc == "Subject": return [u for u in P.units if any(x["subject"] == tg for x in u["rows"])]
    if sc == "Block": return [u for u in P.units if u["kind"] == "block" and u["name"] == tg]
    if sc == "Group": return [u for u in P.units if any(x.get("code") == tg for x in u["rows"])]
    if sc == "Class": return [u for u in P.units if tg in u["classes"] and sub_ok(u)]
    if sc == "Level": return [u for u in P.units if (u["level"] == tg or any(P.level_of.get(c) == tg for c in u["classes"])) and sub_ok(u)]
    if sc == "School": return [u for u in P.units if sub_ok(u)]
    return []

def lesson_domains(P, rules, notes):
    """every lesson of the cycle with the starts it may take (Day structure, end times and the per-lesson rules: Not
    available / Not in periods for a class, level, block or subject, Only in periods, Finish by, Fixed at on every
    day) and the cost of each start. The solver's lesson variables come from this; so do the checks on moves made by hand."""
    NP = P.NP
    def has(rule, scope=None):
        return [r for r in rules if r.get("rule") == rule and (scope is None or r.get("scope") == scope)]
    forbid = collections.defaultdict(set); pen = collections.defaultdict(collections.Counter)
    # position filters from rules
    for r in rules:
        nm, must = r.get("rule"), str(r.get("strength") or "Must") == "Must"
        if nm in ("Not available", "Not in periods") and r.get("scope") in ("Class", "Level", "Block", "Subject"):
            S, _ = P.rule_positions(r)
            for u in units_for(P, r):
                if must: forbid[u["id"]] |= S
                else:
                    for p in S: pen[u["id"]][p] += 1
        if nm == "Keep free together" and r.get("scope") == "Level":
            S, _ = P.rule_positions(r)
            for u in units_for(P, r):
                if must: forbid[u["id"]] |= S
                else:
                    for p in S: pen[u["id"]][p] += 1
    only = collections.defaultdict(list); finish = collections.defaultdict(list); fixed_all = collections.defaultdict(list)
    for r in has("Only in periods"):
        S, days = P.rule_positions(r)
        for u in units_for(P, r): only[u["id"]].append((S, str(r.get("strength") or "Must") == "Must"))
    for r in has("Finish by"):
        _, days = P.rule_positions(r); to = int(r.get("to") if r.get("to") not in (None, "") else NP - 1)
        for u in units_for(P, r): finish[u["id"]].append((set(days), to, str(r.get("strength") or "Must") == "Must"))
    for r in has("Fixed at"):
        if str(r.get("day") or "All") == "All" and r.get("from") not in (None, ""):
            for u in units_for(P, r): fixed_all[u["id"]].append(int(r["from"]))
    out = []
    nstud = lambda rs: max(1, sum(int(x.get("students") or 0) for x in rs) or 30)
    for u in P.units:
        for ln, i in u["lessons"]:
            part = [x for x in u["rows"] if x["_counts"].get(ln, 0) > i]
            vals, cost = [], {}
            for pos, ext in P.starts(u["level"], ln):
                cover = set(range(pos, pos + ln)); d, p = divmod(pos, NP)
                if cover & forbid[u["id"]]: continue
                bad = False; c = ext * (10 + nstud(part) // 2)
                for S, mst in only[u["id"]]:
                    if not cover <= S:
                        if mst: bad = True
                        else: c += W_PREF
                for dset, to, mst in finish[u["id"]]:
                    if d in dset and p + ln - 1 > to:
                        if mst: bad = True
                        else: c += W_PREF
                if fixed_all[u["id"]] and p not in fixed_all[u["id"]]: bad = True
                if bad: continue
                c += W_PREF * sum(pen[u["id"]].get(q, 0) for q in cover)
                vals.append(pos); cost[pos] = c
            if not vals:
                notes.append(f"No allowed time for {u['name']} ({ln}-period lesson): check Day structure and rules."); vals, cost = [0], {0: 0}
            out.append(dict(u=u, ln=ln, i=i, part=part, vals=vals, cost=cost, key=f"{u['key']}|{ln}|{i}"))
    return out


def solve(spec, time_limit=300, workers=8, log=print, skip=(), stop=None, previous=None, pins=None, fix=None, hint=None, params=None):
    """stop: optional threading.Event; setting it ends the search early and keeps the best timetable so far.
    previous: {lesson key: start} from an earlier solve (each returned lesson has its 'key'); lessons stay there unless they must move.
    pins: {lesson key: start} for lessons placed by hand: they stay there (unless that time is no longer allowed).
    fix / hint (the staged solve): {state_key: {(length, group codes): [day * 1000 + period]}}; the k-th lesson of a unit with
    that length and those groups takes the k-th start. fix keeps it there; hint only starts the search there.
    params: extra CP-SAT parameters"""
    P = Problem(spec); NP, ND = P.NP, P.ND
    m = cp_model.CpModel(); rules = spec.get("rules", [])
    notes = list(P.warn)
    def has(rule, scope=None):
        return [r for r in rules if r.get("rule") == rule and (scope is None or r.get("scope") == scope)]
    blocks = []
    # ---------------------------------------------------------------- lesson variables
    for D in lesson_domains(P, rules, notes):
        u, ln, i, part, vals, cost = D["u"], D["ln"], D["i"], D["part"], D["vals"], D["cost"]
        st = m.NewIntVarFromDomain(cp_model.Domain.FromValues(vals), f"s{len(blocks)}")
        iv = m.NewFixedSizeIntervalVar(st, ln, f"i{len(blocks)}")
        dy = m.NewIntVar(0, ND - 1, f"d{len(blocks)}"); m.AddDivisionEquality(dy, st, NP)
        cv = m.NewIntVar(0, max(cost.values()), f"c{len(blocks)}"); m.AddElement(st, [cost.get(q, 0) for q in range(ND * NP)], cv)
        T = sorted({t for x in part for t in x["teachers"]})
        kinds = collections.Counter((x["room_kind"] or "classroom") for x in part)
        ext = {q for q in vals if any(P.grid[u["level"]][q // NP][q % NP + k] == "A" for k in range(ln))}
        blocks.append(dict(u=u, ln=ln, i=i, part=part, st=st, iv=iv, day=dy, cost=cv, T=T, kinds=kinds, ext=ext,
                           key=D["key"], vals=set(vals)))
    if fix or hint:
        seen = collections.Counter(); kept = 0
        for b in blocks:
            pk = (b["ln"], frozenset(str(x["code"]) for x in b["part"])); k = seen[(b["u"]["id"], pk)]; seen[(b["u"]["id"], pk)] += 1
            for st_, keep in ((hint, False), (fix, True)):
                xs = sorted(((st_ or {}).get(state_key(b["u"]), {})).get(pk, []))
                if k >= len(xs): continue
                q = (xs[k] // 1000) * NP + xs[k] % 1000
                if q not in b["vals"]: continue
                if keep: m.Add(b["st"] == q); kept += 1
                else: m.AddHint(b["st"], q)
        if fix: log(f"{kept} lessons kept where they were")
    # lessons the committee placed by hand stay where they put them
    pins = pins or {}
    for b in blocks:
        if b["key"] in pins:
            if pins[b["key"]] in b["vals"]: m.Add(b["st"] == pins[b["key"]])
            else: notes.append(f"{b['u']['name']}: the time it was moved to by hand is no longer allowed, so it may move.")
    log(f"{len(P.units)} units, {len(blocks)} lessons, {len(P.days)} days x {NP} periods")
    # quick capacity checks (a full day of one lesson length cannot always be packed; these catch the obvious)
    tload = collections.Counter(); tlv = collections.defaultdict(set)
    for b in blocks:
        for t in b["T"]: tload[t] += b["ln"]; tlv[t].add(b["u"]["level"])
    for t, n in tload.items():
        slots = len({d * NP + p for lv in tlv[t] for d in range(ND) for p, ch in enumerate(P.grid[lv][d]) if ch == "L"})
        if n > slots * 0.9: notes.append(f"{t} teaches {n} periods but their levels have only {slots} lesson periods a cycle: likely too tight.")
    by_unit = collections.defaultdict(list)
    for b in blocks: by_unit[b["u"]["id"]].append(b)
    # symmetry: interchangeable lessons of a unit keep their order
    for uid, bs in by_unit.items():
        if "symmetry" in skip: break
        grp = collections.defaultdict(list)
        for b in bs: grp[(b["ln"], tuple(id(x) for x in b["part"]))].append(b)
        for lst in grp.values():
            for a, b in zip(lst, lst[1:]): m.Add(a["st"] < b["st"])
    extra_cost = []
    # day booleans (lazy)
    dbool = {}
    def isday(b, d):
        k = (id(b), d)
        if k not in dbool:
            v = m.NewBoolVar(""); m.Add(b["day"] == d).OnlyEnforceIf(v); m.Add(b["day"] != d).OnlyEnforceIf(v.Not()); dbool[k] = v
        return dbool[k]
    # spread: once a day per group (or evenly spread when there are more lessons than days)
    once = has("Once a day per group")
    once_must = any(str(r.get("strength") or "Must") == "Must" for r in once)
    for uid, bs in by_unit.items():
        n = len(bs)
        if n <= 1 or "spread" in skip: continue
        if n <= ND and once_must: m.AddAllDifferent([b["day"] for b in bs])
        elif n <= ND and once:
            for d in range(ND):
                sl = m.NewIntVar(0, n, ""); m.Add(sum(isday(b, d) for b in bs) <= 1 + sl); extra_cost.append(sl * W_PREF)
        else:
            cap = math.ceil(n / ND)
            if cap < n:
                for d in range(ND): m.Add(sum(isday(b, d) for b in bs) <= cap)
    # students
    ec = collections.defaultdict(list)
    for b in blocks:
        if b["u"]["kind"] == "class": ec[b["u"]["classes"][0]].append(b)
    prof = P.students_profiles()
    for c, plist in prof.items():
        if "students" in skip: break
        for use in plist:
            ivs = [b["iv"] for b in ec[c]]
            for uid, cnt in use.items():
                ivs += [b["iv"] for b in by_unit[uid] if cnt.get(b["ln"], 0) > b["i"]]
            m.AddNoOverlap(ivs)
    for c in P.cls:
        if "classes" in skip: break
        for u in P.units:
            if u["kind"] != "class" and c in u["classes"] and ec[c]:
                m.AddNoOverlap([b["iv"] for b in ec[c]] + [b["iv"] for b in by_unit[u["id"]]])
        if not prof.get(c): m.AddNoOverlap([b["iv"] for b in ec[c]])
    # teachers (+ not available / keep free together)
    by_t = collections.defaultdict(list)
    for b in blocks:
        for t in b["T"]: by_t[t].append(b)
    busy_t = collections.defaultdict(set); soft_t = collections.defaultdict(collections.Counter)
    for r in has("Not available", "Teacher") + has("Keep free together", "Department"):
        S, _ = P.rule_positions(r)
        who = [r["target"]] if r["scope"] == "Teacher" else [t for t, d in P.tdept.items() if d == r["target"]]
        for t in who:
            if str(r.get("strength") or "Must") == "Must": busy_t[t] |= S
            else:
                for p in S: soft_t[t][p] += 1
    for t, bs in by_t.items():
        fixed = []
        for run in _runs(sorted(busy_t.get(t, ())), NP):
            fixed.append(m.NewIntervalVar(run[0], len(run), run[0] + len(run), f"busy {t}"))
        if "teachers" not in skip: m.AddNoOverlap([b["iv"] for b in bs] + fixed)
        if soft_t.get(t):
            for b in bs:
                tbl = [W_PREF * sum(soft_t[t].get(q + k, 0) for k in range(b["ln"])) for q in range(ND * NP)]
                if max(tbl) > 0:
                    v = m.NewIntVar(0, max(tbl), ""); m.AddElement(b["st"], tbl, v); extra_cost.append(v)
    # rooms. Each group may use only some rooms (its kind, rooms kept for it or for anyone, rooms that seat it: Problem.allowed).
    # For every set of rooms some group is limited to, the groups limited to it fit in it at every period (Hall's condition per
    # set, exact when the sets nest, as seat sizes do), so the rooms can always be handed out afterwards. A group with its
    # special room on one week only needs a classroom on the other week.
    busy = collections.defaultdict(list)   # room -> runs of periods it is not available
    for r in has("Not available", "Room"):
        if r.get("target") in P.room_kind and str(r.get("strength") or "Must") == "Must":
            S, _ = P.rule_positions(r); busy[r["target"]] += _runs(sorted(S), NP)
    odd = {}
    def in_odd(b):   # true when the lesson falls in an Odd week
        if id(b) not in odd:
            v = m.NewBoolVar(""); m.AddElement(b["day"], [1 if o else 0 for o in P.odd_day], v); odd[id(b)] = v
        return odd[id(b)]
    need = collections.defaultdict(list)   # kind -> [(interval, allowed rooms, groups, block)]
    for b in blocks:
        per = collections.Counter()
        for r in b["part"]:
            for week in (("Odd", "Even") if P.week_limited(r) else (None,)):
                kind, E, _, _ = P.allowed(r, b["u"], week); per[(kind, E, week)] += 1
        for (kind, E, week), n in per.items():
            iv = b["iv"] if week is None else m.NewOptionalFixedSizeIntervalVar(b["st"], b["ln"], in_odd(b) if week == "Odd" else in_odd(b).Not(), "")
            need[kind].append((iv, E, n, b))
    for kind, lst in need.items():
        every = frozenset(x for x, k in P.room_kind.items() if k == kind)
        if not every: notes.append(f"No room of kind '{kind}' on Venues: room limits for it are not checked."); continue
        for F in {E for _, E, _, _ in lst} | {every}:
            cap = sum(P.room_cap[x] for x in F); sub = [(iv, n, b) for iv, E, n, b in lst if E <= F]
            if not sub or not cap: continue
            if F == every:
                too_big = sorted({b["u"]["name"] for _, n, b in sub if n > cap})
                if too_big: notes.append(f"{', '.join(too_big)} need more '{kind}' rooms at once than the {cap} on Venues; the extra groups are given a room marked TBC.")
            runs = [(run, P.room_cap[x]) for x in F for run in busy.get(x, [])]
            ivs = [iv for iv, _, _ in sub] + [m.NewIntervalVar(run[0], len(run), run[0] + len(run), "") for run, _ in runs]
            dem = [min(n, cap) for _, n, _ in sub] + [c for _, c in runs]
            if "rooms" not in skip: m.AddCumulative(ivs, dem, cap)
    # at most N at once (subject, or every subject of a department: e.g. PE classes at once)
    for r in has("At most N at once", "Subject") + has("At most N at once", "Department"):
        field = "subject" if r["scope"] == "Subject" else "dept"
        lst = [(b["iv"], sum(1 for x in b["part"] if x.get(field) == r["target"])) for b in blocks]
        lst = [(iv, n) for iv, n in lst if n]
        if lst and r.get("number"): m.AddCumulative([a for a, _ in lst], [n for _, n in lst], int(r["number"]))
    # max periods a day
    for r in has("Max periods a day"):
        N = int(r.get("number") or 0); must = str(r.get("strength") or "Must") == "Must"
        if not N: continue
        if r["scope"] in ("Teacher", "School"):
            groups = [by_t.get(r["target"], [])] if r["scope"] == "Teacher" else list(by_t.values())
        elif r["scope"] == "Class":
            groups = [[b for b in blocks if r["target"] in b["u"]["classes"]]]
        else:
            groups = [[b for b in blocks if c in b["u"]["classes"]] for c, lv in P.level_of.items() if lv == r["target"]]
        for bs in groups:
            if sum(b["ln"] for b in bs) <= N: continue
            for d in range(ND):
                expr = sum(b["ln"] * isday(b, d) for b in bs)
                if must: m.Add(expr <= N)
                else:
                    s = m.NewIntVar(0, 30, ""); m.Add(expr <= N + s); extra_cost.append(s * W_SLACK)
    # same time across classes
    for r in has("Same time across classes"):
        us = [u for u in P.units if u["kind"] == "class" and P.level_of.get(u["classes"][0]) == r["target"] and u["rows"][0]["subject"] == r.get("subject")]
        tl = [t for u in us for t in u["rows"][0]["teachers"]]
        if len(tl) != len(set(tl)): notes.append(f"Same time across classes ({r['target']} {r.get('subject')}): one teacher has two of these classes, so they cannot all be at the same time; skipped."); continue
        for a, b in zip(us, us[1:]):
            la, lb = by_unit[a["id"]], by_unit[b["id"]]
            if [x["ln"] for x in la] != [x["ln"] for x in lb]: notes.append(f"Same time across classes: {a['name']} and {b['name']} have different lessons; skipped."); continue
            for x, y in zip(la, lb): m.Add(x["st"] == y["st"])
    # not on the same day as
    for r in has("Not on the same day as"):
        for c in P.cls:
            A = [b for b in blocks if c in b["u"]["classes"] and any(x["subject"] == r["target"] for x in b["part"])]
            Bb = [b for b in blocks if c in b["u"]["classes"] and any(x["subject"] == r.get("subject") for x in b["part"])]
            for a in A:
                for b in Bb: m.Add(a["day"] != b["day"])
    # fixed at a given day
    for r in has("Fixed at"):
        if not units_for(P, r): notes.append(f"Fixed at: no lesson matches {r.get('target')} {r.get('subject') or ''}; skipped.".replace(" ;", ";"))
        if str(r.get("day") or "All") == "All" or r.get("from") in (None, ""): continue
        _, days = P.rule_positions(r)
        for u in units_for(P, r):
            for d in days:
                pos = d * NP + int(r["from"]); lits = []
                for b in by_unit[u["id"]]:
                    v = m.NewBoolVar(""); m.Add(b["st"] == pos).OnlyEnforceIf(v); m.Add(b["st"] != pos).OnlyEnforceIf(v.Not()); lits.append(v)
                if lits: m.AddBoolOr(lits)
    # start from the previous timetable: a lesson whose old start is still allowed stays there unless moving it pays
    if previous:
        for b in blocks:
            prev = previous.get(b["key"])
            if prev not in b["vals"]: continue
            b["mv"] = mv = m.NewBoolVar(""); m.Add(b["st"] == prev).OnlyEnforceIf(mv.Not()); extra_cost.append(mv * W_MOVE)
        log(f"starting from the previous timetable: {sum(1 for b in blocks if 'mv' in b)} of {len(blocks)} lessons can stay where they were")
    m.Minimize(sum(b["cost"] for b in blocks) + sum(extra_cost))
    s = cp_model.CpSolver(); s.parameters.max_time_in_seconds = float(time_limit); s.parameters.num_workers = int(workers)
    for k_, v_ in (params or {}).items(): setattr(s.parameters, k_, v_)
    t0 = time.time(); near = None
    if previous:
        near = _near(m, blocks, previous, busy_t, time_limit * 0.5, int(workers), log, stop)
        if near:   # a complete, valid starting timetable: the search only has to improve it
            m.Proto().solution_hint.vars.extend(range(len(near))); m.Proto().solution_hint.values.extend(near)
        else:      # none found in time: prefer the old starts while searching
            for b in blocks:
                if "mv" in b: m.AddHint(b["st"], previous[b["key"]]); m.AddHint(b["mv"], 0)
        s.parameters.max_time_in_seconds = max(10.0, time_limit - (time.time() - t0))
    class CB(cp_model.CpSolverSolutionCallback):
        def __init__(self): super().__init__()
        def on_solution_callback(self): log(f"  {time.time() - t0:5.0f}s  cost {self.ObjectiveValue():.0f}")
    st = _solve(s, m, stop, CB())
    status = s.StatusName(st)
    log(f"status {status} in {time.time() - t0:.0f}s")
    if st in (cp_model.OPTIMAL, cp_model.FEASIBLE): val, obj = s.Value, s.ObjectiveValue()
    elif near: val, obj, status = (lambda v: near[v.Index()]), None, "FEASIBLE"   # the nearby timetable is still valid
    else: return dict(status=status, problem=P, lessons=[], notes=notes + ["No timetable found: see the notes, relax a Must rule, or give more time."])
    out = [dict(unit=b["u"], ln=b["ln"], i=b["i"], part=b["part"], start=val(b["st"]), ext=val(b["st"]) in b["ext"], key=b["key"]) for b in blocks]
    unsupported = [f"'{r['rule']}' is checked after solving, not enforced." for r in rules if r.get("rule") in ("Max periods in a row", "At least one recess a day")]
    return dict(status=status, problem=P, lessons=out, notes=notes + sorted(set(unsupported)), objective=obj)

def _near(m, blocks, previous, busy_t, budget, workers, log, stop):
    """a valid timetable close to the previous one, found fast. The lessons that must move (their old time is no longer
    allowed, or a teacher is now busy then) are freed with every lesson that shares a teacher or class with them, so
    they can swap; all other lessons are fixed where they were. If that has no answer the circle widens once.
    Returns the value of every model variable, or None."""
    t_end = time.time() + budget
    must = {id(b) for b in blocks if "mv" not in b or any(q in busy_t.get(t, ()) for t in b["T"] for q in range(previous[b["key"]], previous[b["key"]] + b["ln"]))}
    if not must:   # nothing is pushed out directly: the old timetable may still work, or the solver names a lesson in the way
        sol, must = _fixed(m, blocks, set(), previous, 1, min(10.0, budget / 4), stop, core=True)
        if sol: log("the previous timetable still works as it is"); return sol
        if not must: return None
    free = set(must)
    for wide in (1, 2):
        T = {t for b in blocks if id(b) in free for t in b["T"]}; C = {c for b in blocks if id(b) in free for c in b["u"]["classes"]}
        free |= {id(b) for b in blocks if T & set(b["T"]) or C & set(b["u"]["classes"])}
        left = t_end - time.time()
        if left < 1 or (stop is not None and stop.is_set()): return None
        sol, _ = _fixed(m, blocks, free, previous, workers, left * 0.8 if wide == 1 else left, stop)
        if sol:
            log(f"found a timetable near the previous one: {len(must)} lessons had to move, {len(free)} were free to move")
            return sol
    return None

def _fixed(m, blocks, free, previous, workers, secs, stop, core=False):
    """solve a copy of the model with every lesson outside `free` kept where it was: first any valid placement of the
    free lessons (fast), then the best one from there. -> (solution or None, lessons in the way: with core=True the
    'keep' choices are assumptions, and an infeasible answer names some of them)"""
    t_end = time.time() + secs
    m2 = m.Clone(); fix = [b for b in blocks if "mv" in b and id(b) not in free]
    if core: m2.AddAssumptions([m2.GetBoolVarFromProtoIndex(b["mv"].Index()).Not() for b in fix])
    else:
        for b in fix: m2.Add(m2.GetIntVarFromProtoIndex(b["st"].Index()) == previous[b["key"]])
    best = None if core else m2.Clone()   # keeps the objective for the second pass
    m2.ClearObjective()
    s2 = cp_model.CpSolver(); s2.parameters.num_workers = workers; s2.parameters.max_time_in_seconds = secs / 2
    s2.parameters.stop_after_first_solution = True
    st = _solve(s2, m2, stop)
    if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        if not (core and st == cp_model.INFEASIBLE): return None, set()
        lit = {-b["mv"].Index() - 1: id(b) for b in fix}   # the index of 'stays where it was' (mv negated)
        return None, {lit[k] for k in s2.SufficientAssumptionsForInfeasibility() if k in lit}
    sol = list(s2.ResponseProto().solution)
    if best is None: return sol, set()
    best.Proto().solution_hint.vars.extend(range(len(sol))); best.Proto().solution_hint.values.extend(sol)
    s3 = cp_model.CpSolver(); s3.parameters.num_workers = workers; s3.parameters.max_time_in_seconds = max(0.5, t_end - time.time())
    st = _solve(s3, best, stop)
    return (list(s3.ResponseProto().solution) if st in (cp_model.OPTIMAL, cp_model.FEASIBLE) else sol), set()

def _solve(s, model, stop, cb=None):
    """s.Solve(model), ended early (keeping the best found so far) when the `stop` event is set"""
    if stop is None: return s.Solve(model, cb)
    import threading
    done = threading.Event()
    def watch():
        while not done.wait(0.5):
            if stop.is_set(): s.stop_search(); return
    threading.Thread(target=watch, daemon=True).start()
    try: return s.Solve(model, cb)
    finally: done.set()

def _runs(sorted_pos, NP):
    out, cur = [], []
    for p in sorted_pos:
        if cur and (p != cur[-1] + 1 or p // NP != cur[-1] // NP): out.append(cur); cur = []
        cur.append(p)
    if cur: out.append(cur)
    return out

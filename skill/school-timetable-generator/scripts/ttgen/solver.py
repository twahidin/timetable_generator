"""Timetable solver: OR-Tools CP-SAT over the lessons, blocks and rules of a setup spec.

Model in one paragraph: every unit (a block of groups that run together, a group on its own, or a whole-class
subject for one class) needs a set of lessons (full-length and short). Each lesson is an interval whose start is
chosen from the teaching periods of the unit's level (Day structure 'L', or 'A' after-school at a cost).
Students: for every class, each kind of student (from the Students sheet, or one per level tag) must not have two
lessons at once; whole-class lessons never overlap a banded lesson that lists the class. Teachers never overlap.
Room kinds are cumulative resources. Rules from '7 Rules' add or remove start positions, fixed busy times, per-day
limits, alignment and day separation. A recess window (Day structure 'W') holds a floating recess: an interval the solver
places for each level or each class (Settings), which that class's lessons may not overlap. The objective keeps
after-school use and broken 'Prefer' rules low.
Given a previous timetable, the search starts from it and each lesson that moves costs W_MOVE, so a tweak moves as few
lessons as it can (cheaper than bending a Prefer rule or pushing a lesson after school)."""
import collections, math, re, time
from ortools.sat.python import cp_model
from .reader import derive
from .spec import PE_KIND, RULE_TYPES, SCOPES, TYPED, WEEKDAYS, ampm, family as _family, floating_recess, names_list, periods_by_day, resolve_row, structure_vs_rules, \
    subject_test, trim_day, windows as _windows

W_PREF, W_SLACK, W_MOVE = 60, 40, 10
RECESS_KEY = "~recess"   # in a placements file: {class: [[start, length]]}, each class's floating recess


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
        fr = floating_recess(sc); self.RL, self.recess_by, self.recess_cap = fr["length"], fr["by"], fr["at_once"]
        self.windows = {lv: [_windows(row) for row in rows] for lv, rows in self.grid.items()}   # per day: [(first, last)] of each W run
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
        # 'Only in venues': a lesson that runs into the rule's periods uses only the rooms it lists (Must), or those rooms
        # when one is free (Prefer). Each: the units it covers, which of their rows, the periods and the rooms
        self.venue_rules = []
        for r in sp.get("rules", []):
            if r.get("rule") != "Only in venues": continue
            V = frozenset(x for x in names_list(r.get("venues")) if x in self.room_kind)
            if not V: continue
            sj = r.get("target") if r.get("scope") == "Subject" else r.get("subject")
            S, _ = self.rule_positions(r)
            self.venue_rules.append(dict(units={u["id"] for u in units_for(self, r)}, subject=sj, S=S, V=V, must=str(r.get("strength") or "Must") == "Must"))
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

    def venue_rules_for(self, r, unit, must=True):
        return [v for v in self.venue_rules if v["must"] == must and unit["id"] in v["units"] and (not v["subject"] or r["subject"] == v["subject"])]

    def allowed_at(self, r, unit, start, ln, week=None):
        """Problem.allowed for a lesson placed at start..start+ln-1: a Must 'Only in venues' rule whose periods it runs into
        keeps it to that rule's rooms"""
        kind, E, n, ov = self.allowed(r, unit, week)
        for v in self.venue_rules_for(r, unit):
            if any(q in v["S"] for q in range(start, start + ln)): E = E & v["V"]
        return kind, E, n, ov

    def preferred_at(self, r, unit, start, ln):
        """rooms a Prefer 'Only in venues' rule asks for at that time (handed out first when free)"""
        return frozenset(x for v in self.venue_rules_for(r, unit, must=False) if any(q in v["S"] for q in range(start, start + ln)) for x in v["V"])

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

    # ---------------------------------------------------------------- recess
    def recess_n(self, a, b):
        """periods of the floating recess in the window a..b (the whole window when it is shorter than the recess)"""
        return min(self.RL, b - a + 1)

    def lesson_periods(self, lv):
        """lesson periods a cycle for a class of this level: L, and W less the recess in each window"""
        return sum(row.count("L") + row.count("W") for row in self.grid.get(lv, [])) - sum(self.recess_n(a, b) for ws in self.windows.get(lv, []) for a, b in ws)

    def stretches(self, lv):
        """lengths of the stretches between breaks, the floating recess at the edge of its window (the most it can hold)"""
        import re
        return [len(m.group()) - sum(self.recess_n(a, b) for a, b in _windows(m.group())) for row in self.grid.get(lv, []) for m in re.finditer(r"[LW]+", row)]

    def class_rows(self, c, recess):
        """a class's Day structure rows with its floating recess (recess {class: [[start, length]]}) as R, the rest of each window as L"""
        spans = collections.defaultdict(list)
        for q, n in (recess or {}).get(c, []): spans[q // self.NP].append((q % self.NP, n))
        return [resolve_row(row, spans[d]) for d, row in enumerate(self.grid.get(self.level_of.get(c), []))]

    def break_options(self, d):
        """recess time on day d, for a teacher's break: [(first start, last start, length)]: each fixed recess (R) of a level
        with classes, whole; and the recess length anywhere inside each recess window (W)"""
        import re
        out = set()
        for lv in {self.level_of[c] for c in self.cls}:
            row = self.grid.get(lv, [""] * self.ND)[d]
            out |= {(m.start(), m.start(), len(m.group())) for m in re.finditer(r"R+", row)}
            out |= {(a, b - self.recess_n(a, b) + 1, self.recess_n(a, b)) for a, b in _windows(row)}
        return sorted(out)

    def starts(self, level, ln):
        ok = "LAW" if self.spec["school"].get("after_school", True) else "LW"   # Settings: after-school slot allowed (No: never use 'A'); W: a recess window
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

def fixed_ok(r):
    """a 'Fixed at' rule for every class of a level or the school must say which subject (else it would fix every lesson)"""
    return r.get("scope") not in ("Level", "School") or bool(r.get("subject"))

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
        if nm == "Only these subjects" and r.get("scope") in ("School", "Level", "Class") and names_list(r.get("subject")):
            ok = subject_test(r.get("subject")); S, _ = P.rule_positions(r)
            for u in units_for(P, dict(r, subject=None)):
                if all(ok(x["subject"], x.get("dept")) for x in u["rows"]): continue
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
        if str(r.get("day") or "All") == "All" and r.get("from") not in (None, "") and fixed_ok(r):
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


def rain_rooms(P, lessons):
    """[(lesson, class, home room)] for each class at PE in these lessons (a part in a PE_KIND room) whose home room is on
    Venues, when Settings says PE goes to the home room in rain. Works on solver blocks and on solved lessons alike"""
    if not P.spec["school"].get("pe_rain_home"): return []
    out = []
    for L in lessons:
        if not any((r.get("room_kind") or "") == PE_KIND for r in L["part"]): continue
        for c in L["u" if "u" in L else "unit"]["classes"]:
            h = (P.cls.get(c) or {}).get("home_room")
            if h and h in P.room_kind: out.append((L, c, h))
    return out

def recess_vars(m, P):
    """floating recess: in each recess window (Day structure 'W') the recess goes where the solver puts it, for the whole level
    or for each class (Settings 'Floating recess goes by'); the rest of the window is lesson time. Returns the recesses
    [dict(classes, n, lo, hi, st, iv)] and {class: [its recesses in day order]}"""
    NP = P.NP; recs, rec_of = [], collections.defaultdict(list)
    for lv in P.levels:
        cl = [c for c in P.cls if P.level_of[c] == lv]
        for d, wins in enumerate(P.windows.get(lv, [])):
            for a, b in wins:
                n = P.recess_n(a, b); lo, hi = d * NP + a, d * NP + b - n + 1
                for who in ([cl] if P.recess_by == "Level" else [[c] for c in cl]):
                    if not who: continue
                    st = m.NewIntVar(lo, hi, f"r{len(recs)}"); R = dict(classes=who, n=n, lo=lo, hi=hi, st=st, iv=m.NewFixedSizeIntervalVar(st, n, ""))
                    recs.append(R)
                    for c in who: rec_of[c].append(R)
    return recs, rec_of

def canteen(m, P, recs, busy, cap):
    """canteen space: Settings 'Most classes at recess at once' over the fixed (R) and floating recess. busy: {period: classes}
    already at recess outside this model (the staged solve: the other levels). cap: a number or an IntVar"""
    fixed = collections.Counter({int(q): n for q, n in (busy or {}).items()})
    for c in P.cls:
        for d, row in enumerate(P.grid.get(P.level_of[c], [])):
            for p, ch in enumerate(row):
                if ch == "R": fixed[d * P.NP + p] += 1
    ivs = [R["iv"] for R in recs] + [m.NewIntervalVar(q, 1, q + 1, "") for q in fixed]
    dem = [len(R["classes"]) for R in recs] + list(fixed.values())
    if ivs: m.AddCumulative(ivs, dem, cap)

def plan_recess(P, busy=None, time_limit=20, workers=8):
    """a floating recess for every class that keeps the canteen limit: classes that share a band (or a group) at recess
    together unless the limit splits them, each as near the middle of its window as it allows: {class: [[start, length]]},
    or None when the limit cannot be kept. A band's lessons need the same free periods in all its classes, so a split
    recess leaves them little room. The staged solve places each level with its recess here, so a level placed early
    cannot take the canteen space of the rest"""
    m = cp_model.CpModel(); recs, rec_of = recess_vars(m, P)
    if not recs or not P.recess_cap: return {}
    canteen(m, P, recs, busy, P.recess_cap)
    cost = []
    for R in recs:
        v = m.NewIntVar(0, R["hi"] - R["lo"], ""); mid = (R["lo"] + R["hi"]) // 2
        m.Add(v >= R["st"] - mid); m.Add(v >= mid - R["st"]); cost.append(v)
    root = {c: c for c in P.cls}   # classes joined by a band or group
    def find(c):
        while root[c] != c: c = root[c]
        return c
    for u in P.units:
        if u["kind"] != "class":
            for c in u["classes"][1:]:
                if c in root and u["classes"][0] in root: root[find(c)] = find(u["classes"][0])
    split = 1 + max(R["hi"] - R["lo"] for R in recs)   # one class apart from its band costs more than any move
    for c, Rs in rec_of.items():
        for R, A in zip(Rs, rec_of.get(find(c), [])):
            if R is A or (R["lo"], R["hi"]) != (A["lo"], A["hi"]): continue
            apart = m.NewBoolVar(""); m.Add(R["st"] == A["st"]).OnlyEnforceIf(apart.Not()); cost.append(split * apart)
    m.Minimize(sum(cost))
    s = cp_model.CpSolver(); s.parameters.max_time_in_seconds = time_limit; s.parameters.num_workers = workers
    if s.Solve(m) not in (cp_model.OPTIMAL, cp_model.FEASIBLE): return None
    return {c: [[int(s.Value(R["st"])), R["n"]] for R in Rs] for c, Rs in rec_of.items()}


def solve(spec, time_limit=300, workers=8, log=print, skip=(), stop=None, previous=None, pins=None, fix=None, hint=None, params=None):
    """stop: optional threading.Event; setting it ends the search early and keeps the best timetable so far.
    previous: {lesson key: start} from an earlier solve (each returned lesson has its 'key'); lessons stay there unless they must move.
    pins: {lesson key: start} for lessons placed by hand: they stay there (unless that time is no longer allowed).
    fix / hint (the staged solve): {state_key: {(length, group codes): [day * 1000 + period]}}; the k-th lesson of a unit with
    that length and those groups takes the k-th start. fix keeps it there; hint only starts the search there. A class's
    floating recess is {("R", class): {"recess": [day * 1000 + period]}}, one start per recess window in day order.
    params: extra CP-SAT parameters"""
    P = Problem(spec); NP, ND = P.NP, P.ND
    m = cp_model.CpModel(); rules = spec.get("rules", [])
    notes = list(P.warn) + structure_vs_rules(spec)   # where the Day structure and the rules disagree
    notes += [f"Rule not used as written ({rule_label(rules[i])}): {t}" for i, t in rule_problems(spec, P)] + fixed_clashes(spec, P)
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
    recs, rec_of = recess_vars(m, P)
    if P.recess_cap and recs and not fix and not hint and not previous:   # canteen limit: start from a recess plan that keeps it
        for c, v in (plan_recess(P, spec.get("_recess_busy"), workers=workers) or {}).items():
            for R, (q, _) in zip(rec_of[c], v):
                if R["classes"][0] == c: m.AddHint(R["st"], q)
    def rec_starts(state):
        """[(recess, start)] for the recesses a state ({("R", class): {"recess": [day * 1000 + period]}}) places"""
        out = []
        for c, Rs in rec_of.items():
            xs = sorted((state or {}).get(("R", c), {}).get("recess", []))
            for k, R in enumerate(Rs):
                q = (xs[k] // 1000) * NP + xs[k] % 1000 if k < len(xs) else None
                if R["classes"][0] == c and q is not None and R["lo"] <= q <= R["hi"]: out.append((R, q))   # a level's recess: from its first class
        return out
    for R, q in rec_starts(fix): m.Add(R["st"] == q)
    for R, q in rec_starts(hint): m.AddHint(R["st"], q)
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
        slots = len({d * NP + p for lv in tlv[t] for d in range(ND) for p, ch in enumerate(P.grid[lv][d]) if ch in "LW"})
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
            ivs = [b["iv"] for b in ec[c]] + [R["iv"] for R in rec_of.get(c, ())]
            for uid, cnt in use.items():
                ivs += [b["iv"] for b in by_unit[uid] if cnt.get(b["ln"], 0) > b["i"]]
            m.AddNoOverlap(ivs)
    for c in P.cls:
        if "classes" in skip: break
        for u in P.units:
            if u["kind"] != "class" and c in u["classes"] and (ec[c] or rec_of.get(c)):
                m.AddNoOverlap([b["iv"] for b in ec[c]] + [R["iv"] for R in rec_of.get(c, ())] + [b["iv"] for b in by_unit[u["id"]]])
        if not prof.get(c): m.AddNoOverlap([b["iv"] for b in ec[c]] + [R["iv"] for R in rec_of.get(c, ())])
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
    # 'At least one recess a day' (Must): each teacher has a break as long as a recess, in recess time, every day: a whole fixed
    # recess (R) or the recess length inside a recess window (W), of any level. Times the teacher is blocked out do not stop it
    taken = (spec.get("_teacher_taken") or {})   # the staged solve: the teacher's lessons in the other levels
    tr = [r for r in has("At least one recess a day") if str(r.get("strength") or "Must") == "Must"]
    if tr and "teachers" not in skip:
        who = set(by_t) if any(r.get("scope") != "Teacher" for r in tr) else {r.get("target") for r in tr} & set(by_t)
        opts = [P.break_options(d) for d in range(ND)]
        for t in sorted(who):
            brk = []
            for d in range(ND):
                if not opts[d]: continue
                lits = []
                for a, b, n in opts[d]:
                    pres = m.NewBoolVar(""); st = m.NewIntVar(d * NP + a, d * NP + b, ""); lits.append(pres)
                    brk.append(m.NewOptionalFixedSizeIntervalVar(st, n, pres, ""))
                m.AddBoolOr(lits)
            if not brk: continue
            m.AddNoOverlap([b["iv"] for b in by_t[t]] + brk)
            if taken.get(t):   # those lessons may still clash with each other (the staged solve clears that later): their periods, joined
                m.AddNoOverlap(brk + [m.NewIntervalVar(run[0], len(run), run[0] + len(run), "") for run in _runs(sorted({q + k for q, n in taken[t] for k in range(n)}), NP)])
    # canteen space: Settings 'Most classes at recess at once' over the fixed (R) and floating recess
    if P.recess_cap and "recess" not in skip: canteen(m, P, recs, spec.get("_recess_busy"), P.recess_cap)
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
                kind, E, _, _ = P.allowed(r, b["u"], week)
                at = collections.defaultdict(list)   # 'Only in venues' (Must): the rooms it may use depend on when it starts
                if P.venue_rules_for(r, b["u"]):
                    for q in sorted(b["vals"]): at[P.allowed_at(r, b["u"], q, b["ln"], week)[1]].append(q)
                    if E and frozenset() in at and len(at) > 1:   # none of the rule's rooms suits it: it may not run into those periods
                        for q in at.pop(frozenset()): m.Add(b["st"] != q)
                if len(at) <= 1: per[(kind, next(iter(at)) if at else E, week)] += 1; continue
                tbl = [0] * (ND * NP); sets = list(at)
                for gi, F_ in enumerate(sets):
                    for q in at[F_]: tbl[q] = gi
                g = m.NewIntVar(0, len(sets) - 1, ""); m.AddElement(b["st"], tbl, g)
                for gi, F_ in enumerate(sets):   # one optional interval per set of rooms; exactly one is present
                    on = m.NewBoolVar(""); m.Add(g == gi).OnlyEnforceIf(on); m.Add(g != gi).OnlyEnforceIf(on.Not())
                    if week is not None:
                        wk = in_odd(b) if week == "Odd" else in_odd(b).Not(); both = m.NewBoolVar("")
                        m.AddBoolAnd([on, wk]).OnlyEnforceIf(both); m.AddBoolOr([on.Not(), wk.Not()]).OnlyEnforceIf(both.Not()); on = both
                    need[kind].append((m.NewOptionalFixedSizeIntervalVar(b["st"], b["ln"], on, ""), F_, 1, b))
        for (kind, E, week), n in per.items():
            iv = b["iv"] if week is None else m.NewOptionalFixedSizeIntervalVar(b["st"], b["ln"], in_odd(b) if week == "Odd" else in_odd(b).Not(), "")
            need[kind].append((iv, E, n, b))
    for b, c, h in rain_rooms(P, blocks):   # Settings 'In rain, PE goes to the class's home room': it stays free during PE
        need[P.room_kind[h]].append((b["iv"], frozenset([h]), 1, b))
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
    # fixed at a given day: one of the unit's lessons starts at each fixed time. When its lessons are alike (one length, the
    # same groups) and as many times are fixed as it has lessons, the k-th lesson takes the k-th time (their order is kept
    # above), which the solver settles at once: a whole-school CCE slot fixes every class's CCE outright
    fixed_at = collections.defaultdict(set)
    for r in has("Fixed at"):
        if not fixed_ok(r) or str(r.get("day") or "All") == "All" or r.get("from") in (None, ""): continue
        _, days = P.rule_positions(r)
        for u in units_for(P, r):
            for d in days: fixed_at[u["id"]].add(d * NP + int(r["from"]))
    for uid, qs in fixed_at.items():
        bs = by_unit[uid]
        if len({(b["ln"], tuple(id(x) for x in b["part"])) for b in bs}) == 1 and len(qs) == len(bs):
            for b, q in zip(bs, sorted(qs)): m.Add(b["st"] == q)
            continue
        for pos in sorted(qs):
            lits = []
            for b in bs:
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
            old = previous.get(RECESS_KEY) or {}
            for R, q in rec_starts({("R", c): {"recess": [(q // NP) * 1000 + q % NP for q, _ in v]} for c, v in old.items()} if not hint else None):
                m.AddHint(R["st"], q)
        s.parameters.max_time_in_seconds = max(10.0, time_limit - (time.time() - t0))
    class CB(cp_model.CpSolverSolutionCallback):
        def __init__(self): super().__init__()
        def on_solution_callback(self): log(f"  {time.time() - t0:5.0f}s  cost {self.ObjectiveValue():.0f}")
    st = _solve(s, m, stop, CB())
    status = s.StatusName(st)
    log(f"status {status} in {time.time() - t0:.0f}s")
    if st in (cp_model.OPTIMAL, cp_model.FEASIBLE): val, obj = s.Value, s.ObjectiveValue()
    elif near: val, obj, status = (lambda v: near[v.Index()]), None, "FEASIBLE"   # the nearby timetable is still valid
    else: return dict(status=status, problem=P, lessons=[], recess={}, notes=notes + ["No timetable found: see the notes, relax a Must rule, or give more time."])
    out = [dict(unit=b["u"], ln=b["ln"], i=b["i"], part=b["part"], start=val(b["st"]), ext=val(b["st"]) in b["ext"], key=b["key"]) for b in blocks]
    recess = {c: [[int(val(R["st"])), R["n"]] for R in Rs] for c, Rs in rec_of.items()}
    unsupported = [f"'{r['rule']}' is checked after solving, not enforced." for r in rules if r.get("rule") == "Max periods in a row"
                   or (r.get("rule") == "At least one recess a day" and str(r.get("strength") or "Must") != "Must")]
    return dict(status=status, problem=P, lessons=out, recess=recess, notes=notes + sorted(set(unsupported)), objective=obj)

def rule_label(r):
    """a rule row in a few words, as the committee wrote it: 'School · Whole school · Physical Education · Only in venues'"""
    return " · ".join(str(x) for x in (r.get("scope"), r.get("target"), r.get("subject"), r.get("rule")) if x not in (None, ""))

UNIT_RULES = {"Fixed at", "Not in periods", "Only in periods", "Finish by", "Only these subjects", "Only in venues", "Not available", "Keep free together"}

def rule_problems(spec, P=None):
    """rule rows the solver cannot use as written: [(index in spec['rules'], what is wrong and what to do)]. A rule it
    cannot read is skipped and one that matches no lesson does nothing, so the committee is told before generating"""
    P = P or Problem(spec); sc = spec["school"]
    types = {t[0]: (set(names_list(t[1])), t[2] == "Y", t[3] == "Y") for t in RULE_TYPES}
    subjects = {str(s["subject"]) for s in spec.get("subjects", []) if s.get("subject")}
    sd = [(str(s["subject"]), s.get("dept")) for s in spec.get("subjects", []) if s.get("subject")]
    depts = {str(d) for d in (sc.get("departments") or [])} | {str(d) for _, d in sd if d} | {str(t.get("dept")) for t in spec.get("teachers", []) if t.get("dept")}
    codes = {str(x["code"]) for x in P.rows if x.get("code") and x["code"] != "Entire Class"}
    lists = dict(School={"Whole school"}, Level=set(P.levels), Class=set(P.cls), Teacher={str(t["name"]) for t in spec.get("teachers", [])}, Department=depts,
                 Subject=subjects, Block={str(b["block"]) for b in spec.get("blocks", [])}, Group=codes, Room=set(P.room_kind))
    out = []
    for i, r in enumerate(spec.get("rules", [])):
        rule, scope, target, subj = r.get("rule"), r.get("scope"), r.get("target"), r.get("subject")
        say = lambda t: out.append((i, t))
        if rule not in types:
            say(f"'{rule}' is not a rule the timetable knows, so this row is skipped. Pick one from the Rule list." if rule else "No rule picked, so this row is skipped."); continue
        can, needs_time, needs_number = types[rule]
        if scope not in can:
            say(f"{rule} cannot apply to {('a ' + str(scope).lower()) if scope else 'nothing'}; it applies to {', '.join(x for x in SCOPES if x in can)}. This row is skipped."); continue
        if target in (None, ""): say(f"Pick the {str(scope).lower()}: without one this row matches nothing."); continue
        if str(target) not in lists.get(scope, set()):
            say(f"{target} is not a{'n' if str(scope)[0] in 'AEIOU' else ''} {str(scope).lower()} on the setup, so this row matches nothing."
                + (" For every level, apply it to School." if scope == "Level" else "")); continue
        if rule == TYPED:   # honoured by the agent, not the solver: only an empty sentence is a problem
            if not str(r.get("text") or "").strip(): say("Write the rule in words: without them this row says nothing.")
            continue
        if rule == "Only these subjects":
            names = names_list(subj)
            if not names: say("List the subjects allowed in those periods under Subject, separated by commas. Without them this row does nothing."); continue
            bad = [n for n in names if not any(subject_test(n)(s_, d_) for s_, d_ in sd)]
            if bad: say(f"{', '.join(bad)}: not a subject or department on the setup, so {'it matches' if len(bad) == 1 else 'they match'} nothing.")
        elif subj and str(subj) not in subjects:
            hint = (" For a day when only some subjects are taught (an HBL day), use the rule Only these subjects and list them."
                    if "," in str(subj) or "except" in str(subj).lower() else "")
            say(f"Subject '{subj}' is not on step 3 (Subjects), so this row matches nothing.{hint}"); continue
        if rule == "Fixed at" and scope in ("Level", "School") and not subj:
            say("Pick the subject: a fixed lesson for every class needs one (without it this row is skipped)."); continue
        if rule in ("Same time across classes", "Not on the same day as") and not subj: say("Pick the Subject."); continue
        if needs_time and rule not in ("Only these subjects", "Only in venues") and r.get("from") in (None, "") and r.get("to") in (None, ""): say("Give the period(s).")
        if rule == "Finish by" and r.get("to") in (None, ""): say("Finish by uses the To period (the last period lessons may use), and it is blank, so this row changes nothing.")
        if needs_number and not r.get("number"): say("Give the Number.")
        if str(r.get("strength") or "Must") not in ("Must", "Prefer"): say(f"Must / Prefer is '{r.get('strength')}': read as Prefer. Pick Must or Prefer.")
        if rule == "Only in venues":
            vs = names_list(r.get("venues"))
            if not vs: say("List the rooms under Venues, separated by commas. Without them this row is skipped."); continue
            unknown = [v for v in vs if v not in P.room_kind]
            if unknown: say(f"{', '.join(unknown)}: not on step 1 (Venues).")
        if rule not in UNIT_RULES or scope in ("Teacher", "Room", "Department"): continue
        us = units_for(P, dict(r, subject=None) if rule == "Only these subjects" else r)
        if rule == "Only in venues":
            sj = target if scope == "Subject" else subj
            rows_ = [(x, u) for u in us for x in u["rows"] if not sj or x["subject"] == sj]
            V = {v for v in names_list(r.get("venues")) if v in P.room_kind}
            if rows_ and V and not any(P.allowed(x, u)[1] & V for x, u in rows_):
                kinds = sorted({P.allowed(x, u)[0] for x, u in rows_})
                say(f"None of {', '.join(sorted(V))} is a room these lessons may use (they need a {' or '.join(kinds)} room on step 1), so "
                    f"{'they cannot run in those periods' if str(r.get('strength') or 'Must') == 'Must' else 'this row changes nothing'}.")
            us = [u for x, u in rows_]
        if not us:
            what = f"{target} {subj}" if subj and scope != "Subject" else str(target)
            say(f"No lesson on step 5 matches {what}, so this row does nothing.")
    return out

def fixed_clashes(spec, P=None):
    """fixed lessons that no timetable can meet: one teacher, or one class, with two lessons fixed to start at the same time
    (a whole-school CCE slot when a teacher takes CCE for two classes, say), or a lesson fixed at more times than it has
    lessons. Each is a reason the solver finds nothing"""
    P = P or Problem(spec); at = collections.defaultdict(set); need = collections.defaultdict(set)   # start -> units fixed there; unit -> its fixed starts
    for r in spec.get("rules", []):
        if r.get("rule") != "Fixed at" or not fixed_ok(r) or str(r.get("day") or "All") == "All" or r.get("from") in (None, ""): continue
        _, days = P.rule_positions(r)
        for u in units_for(P, r):
            for d in days: q = d * P.NP + int(r["from"]); at[q].add(u["id"]); need[u["id"]].add(q)
    byid = {u["id"]: u for u in P.units}; sc = P.spec["school"]
    h, mm = map(int, str(sc["start_time"]).split(":")[:2])
    when = lambda q: f"{P.days[q // P.NP]} {ampm(h * 60 + mm + (q % P.NP) * int(sc['period_minutes']))}"
    T, C = collections.defaultdict(list), collections.defaultdict(list)   # (teacher or class, the lessons) -> the times they are all fixed at
    for q, ids in sorted(at.items()):
        if len(ids) < 2: continue
        tl, cl = collections.defaultdict(list), collections.defaultdict(list)
        for u in sorted((byid[i] for i in ids), key=lambda u: u["name"]):
            for t in sorted({t for x in u["rows"] for t in x["teachers"] if t}): tl[t].append(u["name"])
            for c in u["classes"]: cl[c].append(u["name"])
        for t, names in tl.items():
            if len(names) > 1: T[(t, tuple(names))].append(when(q))
        for c, names in cl.items():
            if len(names) > 1: C[(c, tuple(names))].append(when(q))
    out = [f"{t} teaches {_listing(list(names))}, but fixed lessons start {'both' if len(names) == 2 else 'them all'} at {_listing(ws)}: no timetable can do that. "
           "Give those classes different teachers for it (step 5), or fix them at different times (step 6)." for (t, names), ws in T.items()]
    out += [f"{c} has {_listing(list(names))} fixed to start at the same time ({_listing(ws)}): no timetable can do that. Fix them at different times (step 6)."
            for (c, names), ws in C.items()]
    few = collections.defaultdict(list)   # (its lessons a cycle, the times it is fixed at) -> lessons fixed at more times than they have lessons
    for uid, qs in need.items():
        if len(qs) > len(byid[uid]["lessons"]): few[(len(byid[uid]["lessons"]), tuple(sorted(qs)))].append(byid[uid]["name"])
    for (n, qs), names in few.items():
        one = len(names) == 1
        out.append(f"{_listing(sorted(names))} {'has' if one else 'each have'} {n} lesson{'s' if n != 1 else ''} a cycle, but fixed lessons start {'it' if one else 'each'} at "
                   f"{len(qs)} times ({_listing([when(q) for q in qs])}): no timetable can do that. Fix {'it' if one else 'them'} on fewer days (Week Odd or Even rather than Both), "
                   "or give more lessons.")
    return out

def _listing(a, n=4):
    return ", ".join(a[:n]) + (f" and {len(a) - n} more" if len(a) > n else "")

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

"""Staged solve for large or very tight schools.

One whole-school CP-SAT model can stall (no timetable at all after an hour) even when every level solves on its own
in seconds: the levels are only tied together by shared teachers and rooms, but the search does not split them.
This builds the same timetable in steps that each stay small:

1. Build: levels one at a time, hardest first (least spare lesson time). Each level is solved with the levels before
   it kept exactly where they are. A level that cannot fit around them is set aside.
2. Clear clashes: a set-aside level is placed with a teacher clash against another level allowed but penalised; then
   only the classes involved in the remaining clashes are re-solved (everything else kept) until no clash is left.
3. Check: the whole school is solved once more with every lesson kept, so every rule is checked together.
4. Improve: if 'No free periods for students' is on, a few classes at a time are re-solved (all else kept) and a
   change is kept only when it lowers the total.

solve_staged returns the same result as solver.solve, so report.write_timetable and the exports work unchanged.
`stop` (the committee's Stop button) and `deadline` (time.time() by which to give up) end it early.
"""
import collections, copy, re, threading, time
from .solver import solve, plan_recess, Problem, state_key

NOFREE = "No free periods for students"


_key = state_key


def _restrict(spec, classes):
    sp = copy.deepcopy(spec)
    sp["lessons"] = [x for x in sp["lessons"] if set(x["classes"]) <= classes]
    bl = {x["block"] for x in sp["lessons"] if x.get("block")}
    sp["blocks"] = [b for b in sp["blocks"] if b["block"] in bl]
    sp["classes"] = [c for c in sp["classes"] if c["class"] in classes]
    sp["students"] = [s for s in sp.get("students", []) if s.get("class") in classes]
    return sp


class _Run:
    def __init__(self, spec, time_per_step, workers, log, stop=None, deadline=None):
        self.spec, self.T, self.workers, self.log = spec, time_per_step, workers, log
        self.stop, self.deadline = stop, deadline
        self.P = Problem(spec); self.NP = self.P.NP
        self.base = copy.deepcopy(spec); self.base["rules"] = [r for r in spec.get("rules", []) if r.get("rule") != NOFREE]
        self.level_classes = collections.defaultdict(set)
        for c in spec["classes"]: self.level_classes[c["level"]].add(c["class"])
        self.levels = [lv for lv in self.P.levels if any(u["level"] == lv for u in self.P.units)]
        self.unit_level = {_key(u): u["level"] for u in self.P.units}
        self.unit_classes = {_key(u): set(u["classes"]) for u in self.P.units}
        for c, lv in self.P.level_of.items():   # a class's floating recess goes with its class
            self.unit_level[("R", c)] = lv; self.unit_classes[("R", c)] = {c}
        self.state = {}
        self.plan = {}   # with a canteen limit: a recess for every class that keeps it, the space kept for levels not yet placed
        if self.P.recess_cap:
            for c, v in (plan_recess(self.P, workers=workers) or {}).items():
                self.plan[("R", c)] = {"recess": [(q // self.NP) * 1000 + q % self.NP for q, _ in v]}

    # ---------------------------------------------------------------- helpers
    def halted(self):
        return bool(self.stop and self.stop.is_set()) or bool(self.deadline and time.time() > self.deadline)

    def tightness(self, lv):
        """largest share of the level's lesson periods that one kind of student needs"""
        P = self.P; slots = P.lesson_periods(lv)
        if not slots: return 0
        prof = P.students_profiles(); worst = 0
        for c in self.level_classes[lv]:
            wc = sum(ln for u in P.units if u["kind"] == "class" and c in u["classes"] for ln, i in u["lessons"])
            for use in prof.get(c, [{}]):
                worst = max(worst, wc + sum(k * v for cnt in use.values() for k, v in cnt.items()))
        return worst / slots

    def to_state(self, res):
        out = collections.defaultdict(lambda: collections.defaultdict(list))
        for x in res["lessons"]:
            u = x["unit"]; pk = (x["ln"], frozenset(str(r["code"]) for r in x["part"])); d, p = divmod(x["start"], self.NP)
            out[_key(u)][pk].append(d * 1000 + p)
        for c, spans in (res.get("recess") or {}).items():
            out[("R", c)]["recess"] = [(q // self.NP) * 1000 + q % self.NP for q, _ in spans]
        return out

    def placed(self, levels):
        out = []
        for u in self.P.units:
            if u["level"] not in levels: continue
            seen = collections.Counter()
            for ln, i in u["lessons"]:
                part = [x for x in u["rows"] if x["_counts"].get(ln, 0) > i]
                pk = (ln, frozenset(str(x["code"]) for x in part)); k = seen[pk]; seen[pk] += 1
                st = sorted(self.state.get(_key(u), {}).get(pk, []))
                if k < len(st): out.append((u, ln, part, (st[k] // 1000) * self.NP + st[k] % 1000))
        return out

    def clashes(self):
        """teacher periods taught twice at once (across levels), and the classes involved per level"""
        occ = collections.defaultdict(list)
        for u, ln, part, q in self.placed(self.levels):
            for t in {t for x in part for t in x["teachers"]}:
                for p in range(q, q + ln): occ[(t, p)].append(u)
        n = 0; where = collections.defaultdict(set)
        for (t, p), us in occ.items():
            if len(us) > 1:
                n += 1
                for u in us: where[u["level"]] |= set(u["classes"])
        return n, where

    def _solve(self, sp, fix=None, hint=None, patience=40, stop_at=None, tries=4):
        """solve one step. CP-SAT's time to a first timetable here is heavy-tailed (the same level can take 10 s or several
        minutes, depending on the random start), so a step without one after its share of the time restarts with a new
        seed, up to `tries` times within time_per_step"""
        t_end = time.time() + self.T; r = None
        for k in range(max(1, tries)):
            left = t_end - time.time()
            if left < 10 or self.halted(): break
            r = self._solve_once(sp, fix, hint, patience, stop_at, min(left, max(30, self.T / tries)) if k < tries - 1 else left, seed=k)
            if r["lessons"] or r["status"] == "INFEASIBLE": return r
        return r or dict(status="UNKNOWN", lessons=[], problem=self.P, notes=[])

    def _solve_once(self, sp, fix, hint, patience, stop_at, limit, seed=0):
        stop = threading.Event(); last = [None]
        def log(*a):
            msg = str(a[0]) if a else ""
            m = re.search(r"cost (\d+)", msg)
            if m:
                last[0] = time.time()
                if stop_at is not None and int(m.group(1)) <= stop_at: stop.set()
        def watch():
            while not stop.is_set():
                if (last[0] is not None and time.time() - last[0] > patience) or self.halted(): stop.set()
                time.sleep(1)
        threading.Thread(target=watch, daemon=True).start()
        params = dict({"hint_conflict_limit": 100000} if hint else {}, **({"random_seed": seed} if seed else {}))
        r = solve(sp, time_limit=limit, workers=self.workers, log=log, fix=fix, hint=hint, stop=stop, params=params or None)
        stop.set()
        return r

    def recess_of(self, levels):
        """{period: classes at recess} for the classes of these levels: their fixed (R) and floating recess so far (the planned
        one for a class not placed yet)"""
        P = self.P; out = collections.Counter()
        for o in levels:
            for c in self.level_classes[o]:
                placed = self.state.get(("R", c)) or self.plan.get(("R", c)) or {}
                for d, row in enumerate(P.grid.get(o, [])):
                    out.update(d * self.NP + p for p, ch in enumerate(row) if ch == "R")
                    for a, b in P.windows[o][d]:
                        for x in placed.get("recess", []):
                            if x // 1000 == d and a <= x % 1000 <= b: out.update(range(d * self.NP + x % 1000, d * self.NP + x % 1000 + P.recess_n(a, b)))
        return out

    def plan_of(self, lv):
        """the planned recess of this level's classes. A level is first placed with its recess there (a free recess under a
        canteen limit makes the search much slower); clearing clashes may move it later"""
        return {k: v for k, v in self.plan.items() if k[1] in self.level_classes[lv]}

    def level_spec(self, lv, soft_teachers=True):
        """spec for one level, with the other levels' lessons as busy times (teachers penalised, rooms kept free)"""
        sp = _restrict(self.base, self.level_classes[lv])
        others = [o for o in self.levels if o != lv]
        sp["_recess_busy"] = dict(self.recess_of(others))   # canteen space the other levels' recess already takes
        taken = collections.defaultdict(list)                  # a teacher's lessons in the other levels (their recess break avoids them)
        for u, ln, part, q in self.placed(others):
            for t in {t for x in part for t in x["teachers"]}: taken[t].append([q, ln])
        sp["_teacher_taken"] = dict(taken)
        for u, ln, part, q in self.placed(others):
            d, p = divmod(q, self.NP); name = self.P.days[d].split(); wk, dy = (name[0], name[-1]) if len(name) > 1 else ("Both", name[-1])
            span = {"from": p, "to": p + ln - 1}
            for t in {t for x in part for t in x["teachers"]}:
                sp["rules"].append(dict(scope="Teacher", target=t, rule="Not available", strength="Prefer" if soft_teachers else "Must", week=wk, day=dy, **span))
            week = "Odd" if self.P.odd_day[d] else "Even"
            for x in part:   # each group keeps a room it may use busy: the smallest that seats it, so bigger rooms stay free for bigger groups
                _, E, _, _ = self.P.allowed(x, u, week if self.P.week_limited(x) else None)
                if E: sp["rules"].append(dict(scope="Room", target=min(E, key=lambda r: (self.P.seats.get(r) or 0, r)), rule="Not available", strength="Must", week=wk, day=dy, **span))
        return sp

    def resolve_part(self, lv, free_classes):
        """re-solve the lessons of these classes in level lv (rest of the level kept); keep it if clashes drop"""
        n0, _ = self.clashes()
        sp = self.level_spec(lv)
        fix = {k: v for k, v in self.state.items() if self.unit_level.get(k) == lv and not (self.unit_classes.get(k, set()) & free_classes)}
        r = self._solve(sp, fix=fix, hint=dict(self.state), stop_at=0)
        if not r["lessons"]: return False
        keep = {k: v for k, v in self.state.items()}
        for k in [k for k in self.state if self.unit_level.get(k) == lv]: self.state.pop(k)
        self.state.update(self.to_state(r))
        n1, _ = self.clashes()
        if n1 > n0: self.state = keep; return False
        return n1 < n0

    # ---------------------------------------------------------------- steps
    def build(self, order):
        done, left = [], []
        for lv in order:
            if self.halted(): return False
            sp = _restrict(self.base, set().union(*(self.level_classes[x] for x in done + [lv])))
            sp["_recess_busy"] = dict(self.recess_of([o for o in self.levels if o not in done + [lv]]))   # the planned recess of the rest
            t0 = time.time(); r = self._solve(sp, fix={**self.state, **self.plan_of(lv)} or None, patience=20)
            if r["lessons"]:
                self.state = self.to_state(r); done.append(lv)
                self.log(f"  {lv}: placed around {', '.join(done[:-1]) or 'nothing'} ({time.time() - t0:.0f}s)")
            else:
                left.append(lv); self.log(f"  {lv}: does not fit around the levels already placed ({r['status']}); placing it with clashes allowed")
        for lv in left:
            if self.halted(): return False
            r = self._solve(self.level_spec(lv), fix=self.plan_of(lv) or None, hint=None, stop_at=0)
            if not r["lessons"] and self.plan_of(lv):   # its planned recess times may not suit it: let it pick, in the canteen space left
                self.log(f"  {lv}: not placed with its recess at the planned times ({r['status']}); trying with its recess free")
                r = self._solve(self.level_spec(lv), hint=None, stop_at=0)
            if not r["lessons"]:
                self.log(f"  {lv}: not placed even with clashes allowed ({r['status']})"); return False
            self.state.update(self.to_state(r))
        return True

    def clear(self, rounds):
        for rnd in range(rounds):
            if self.halted(): return False
            n, where = self.clashes()
            self.log(f"  teacher clashes between levels: {n} periods")
            if n == 0: return True
            improved = False
            for lv in sorted(where, key=lambda x: self.tightness(x)):      # levels with the most spare time first
                if self.resolve_part(lv, where[lv]): improved = True; break
            if not improved:
                for lv in sorted(where, key=lambda x: self.tightness(x)):
                    if self.resolve_part(lv, self.level_classes[lv]): improved = True; break
            if not improved: return False
        return self.clashes()[0] == 0

    def improve(self, rounds, chunk=4):
        res = solve(self.spec, time_limit=self.T, workers=self.workers, log=lambda *a: None, fix=self.state)
        best = res.get("objective")
        if best is None: return res
        self.log(f"  free-period cost {best:.0f}")
        hoods = []
        for lv in self.levels:
            cl = sorted(self.level_classes[lv]); hoods += [set(cl[i:i + chunk]) for i in range(0, len(cl), chunk)]
        for rnd in range(rounds):
            better = False
            for h in hoods:
                fix = {k: v for k, v in self.state.items() if not (self.unit_classes.get(k, set()) & h)}
                r = self._solve(self.spec, fix=fix, hint=dict(self.state), tries=1)   # improving: one long run
                o = r.get("objective")
                if r["lessons"] and o is not None and o < best:
                    self.state = self.to_state(r); best = o; res = r; better = True
                    self.log(f"  {min(h)}-{max(h)}: free-period cost {best:.0f}")
            if not better: break
        return res


def solve_staged(spec, time_per_step=180, workers=8, log=print, order=None, rounds=8, improve_rounds=2, stop=None, deadline=None):
    run = _Run(spec, time_per_step, workers, log, stop, deadline)
    order = order or sorted(run.levels, key=run.tightness, reverse=True)
    log("staged solve, levels in this order: " + ", ".join(order))
    if not run.build(order):
        if run.halted(): return dict(status="STOPPED" if stop and stop.is_set() else "UNKNOWN", problem=run.P, lessons=[], notes=["Staged solve: out of time before every level was placed."])
        return dict(status="NOT FOUND", problem=run.P, lessons=[], notes=["Staged solve: a level could not be placed even with clashes allowed."
                    + (f" The levels placed first may have taken the canteen space (at most {run.P.recess_cap} classes at recess at once)." if run.P.recess_cap else "")])
    if not run.clear(rounds):
        if run.halted(): return dict(status="STOPPED" if stop and stop.is_set() else "UNKNOWN", problem=run.P, lessons=[], notes=["Staged solve: out of time while clearing clashes between levels."])
        n, where = run.clashes()
        return dict(status="NOT FOUND", problem=run.P, lessons=[], notes=[f"Staged solve: {n} teacher clash periods left between levels "
                    f"({'; '.join(f'{lv}: ' + ', '.join(sorted(c)) for lv, c in where.items())})."])
    res = solve(spec, time_limit=time_per_step, workers=workers, log=lambda *a: None, fix=run.state, stop=stop)
    if not res["lessons"]:
        return dict(status=res["status"], problem=run.P, lessons=[], notes=["Staged solve: the joined timetable failed the whole-school check."])
    log("  every level joined; whole-school check passed")
    if any(r.get("rule") == NOFREE for r in spec.get("rules", [])) and improve_rounds:
        res = run.improve(improve_rounds)
    return res

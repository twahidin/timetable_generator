"""Will it fit? The sums done on a setup before it goes to an outside agent: every problem found without solving, as
critical (no timetable can be made until it is fixed) or a warning (a timetable can still be made; a person should look).
Class periods against the lesson periods of the day, lessons against the stretches between breaks, special rooms,
teachers' time, floating recess, and the rule rows the solver cannot use. Students are not checked here."""
import collections, re
from ttgen.reader import derive
from ttgen.spec import structure_vs_rules

WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six"}

def _packs(runs, need):
    """can lessons of these lengths ({length: count}) all go in these stretches of lesson periods? (a lesson cannot
    run across a recess or lunch, so each stretch holds whole lessons only)"""
    lens = sorted(need, reverse=True); states = {tuple(need[n] for n in lens)}
    def fill(k, left, st, nxt):
        if k == len(lens): nxt.add(st); return
        for a in range(min(st[k], left // lens[k]) + 1): fill(k + 1, left - a * lens[k], st[:k] + (st[k] - a,) + st[k + 1:], nxt)
    for n in sorted(runs, reverse=True):
        nxt = set()
        for st in states: fill(0, n, st, nxt)
        states = nxt
        if any(not any(s) for s in states): return True
    return False

def _class_fit(P):
    """each class against its level's day: what its busiest students need, and whether their lessons fit between the
    breaks. [dict(cls, level, kind, text)] for classes that are over, do not fit, have no slack, or are almost full"""
    Lcount = {lv: P.lesson_periods(lv) for lv in P.grid}   # recess windows (W) count less their recess
    Acount = {lv: sum(row.count("A") for row in rows) for lv, rows in P.grid.items()}
    runs = {lv: P.stretches(lv) for lv in P.grid}
    whole = collections.defaultdict(collections.Counter)
    for u in P.units:
        if u["kind"] == "class":
            for ln, _ in u["lessons"]: whole[u["classes"][0]][ln] += 1
    prof = P.students_profiles(); out = []
    for c, lv in P.level_of.items():
        if lv not in Lcount: continue
        sets = set()   # each kind of student in the class: {length: lessons}, whole-class lessons included
        for p in prof.get(c) or [{}]:
            cnt = whole[c].copy()
            for cc in p.values(): cnt.update(cc)
            sets.add(tuple(sorted((ln, n) for ln, n in cnt.items() if n)))
        have = Lcount[lv]; need = max((sum(ln * n for ln, n in s) for s in sets), default=0)
        row = dict(cls=c, level=lv, need=need, have=have)
        if need > have:
            out.append(dict(row, kind="over", text=f"Class {c} needs {need} periods but {lv} has {have} lesson periods a cycle (+{Acount[lv]} after-school): at least {need - have} periods must go after school.")); continue
        if not need: continue
        top = max(ln for s in sets for ln, _ in s); most = sum(n // top for n in runs[lv])   # the most top-length lessons the day holds
        desc = lambda s: " and ".join(f"{n} {WORDS.get(ln, ln)}-period" for ln, n in sorted(s, reverse=True)) + " lessons"
        near = [s for s in sets if sum(ln * n for ln, n in s) >= have - 2 * top]
        bad = next((s for s in near if not _packs(runs[lv], dict(s))), None)
        full = next((s for s in near if dict(s).get(top, 0) >= most or sum(ln * n for ln, n in s) == have), None)
        if bad:
            out.append(dict(row, kind="nofit", text=f"Class {c}: its busiest students' {desc(bad)} do not fit in the {lv} day. A lesson cannot run across a recess or lunch, "
                                                   f"and the stretches between breaks hold at most {most} {WORDS.get(top, top)}-period lessons a cycle."))
        elif full:
            n = dict(full).get(top, 0)
            out.append(dict(row, kind="tight", text=f"Class {c}: its busiest students need {n} {WORDS.get(top, top)}-period lessons ({sum(ln * k for ln, k in full)} of {have} periods), "
                            + (f"and the {lv} day holds exactly {most} between breaks, so every one of those slots must be used" if n >= most else "so every lesson period of the cycle must be used")
                            + ": a single teacher, room or student clash makes the timetable impossible."))
        elif need > 0.97 * have:
            out.append(dict(row, kind="almost", text=f"Class {c} is almost full: {need} of {have} lesson periods."))
    return out

def _room_fit(P):
    """per set of rooms some groups are limited to (Problem.allowed: kind, rooms kept for them, rooms that seat them), the
    class-periods of those groups against what the rooms hold in the lesson periods (a room holds one class at a time
    unless a Must 'At most N at once' rule says more; a special room used on alternate weeks counts half its periods).
    [dict(kind, rooms, need, have, kind_, text)]"""
    use = "LAW" if P.spec["school"].get("after_school", True) else "LW"
    fam = collections.defaultdict(set); dem = []
    for u in P.units:
        for ln, i in u["lessons"]:
            for r in (x for x in u["rows"] if x["_counts"].get(ln, 0) > i):
                weeks = ("Odd", "Even") if P.week_limited(r) else (None,)
                for week in weeks:
                    kind, E, _, _ = P.allowed(r, u, week); fam[kind].add(E); dem.append((kind, E, ln / len(weeks), u["level"]))
    out = []
    for kind, sets in fam.items():
        every = frozenset(x for x, k in P.room_kind.items() if k == kind); sets.add(every)
        for F in sorted(sets, key=len):
            c = sum(P.room_cap[x] for x in F)
            if not c: continue   # no room of this kind: the solver notes it and gives those lessons a room marked TBC
            part = [(w, lv) for k, E, w, lv in dem if k == kind and E <= F]
            if not part: continue
            n = round(sum(w for w, _ in part)); lvls = {lv for _, lv in part}
            slots = len({d * P.NP + p for lv in lvls for d, row in enumerate(P.grid.get(lv, [])) for p, ch in enumerate(row) if ch in use})
            have = c * slots; names = ", ".join(f"{x}" + (f" ({P.room_cap[x]} classes)" if P.room_cap[x] > 1 else "") for x in sorted(F))
            which = f"the {kind} rooms" if F == every else f"the {kind} rooms they may use (kept for them, or seating them)"
            row = dict(kind=kind, rooms=sorted(F), need=n, have=have)
            if n > have:
                out.append(dict(row, kind_="impossible", text=f"Lessons that need {which} add up to {n} class-periods a cycle, but those rooms ({names}) hold at most {have} "
                                                              f"({c} class{'es' if c != 1 else ''} at a time × {slots} lesson periods): no timetable is possible. A room holds one class at a time "
                                                              f"unless step 6 has a 'Room · At most N at once' rule for it."))
            elif F == every and n > 0.9 * have:
                out.append(dict(row, kind_="tight", text=f"Lessons that need a {kind} room fill {n} of the {have} class-periods its rooms ({names}) hold: very hard to fit."))
    return out

# ------------------------------------------------------------------------------- critical problems and warnings
# Every problem found before solving is one of two kinds:
#   critical: no timetable can be made until it is fixed, so solve refuses to start;
#   warning:  a timetable can still be made, but a person should look (a room that seats too few, a teacher over their
#             allowance, a lesson row left out, a class so full that it may not fit).
# Students are not checked here: the list goes in after the timetable is made, class by class.
CRITICAL, WARNING = "critical", "warning"
# input problems from ttgen.reader.derive that stop every timetable; the rest are warnings (the row is left out or the usual split is used)
_CRITICAL_INPUT = ()

def _input_level(msg):
    return CRITICAL if any(re.search(p, msg) for p in _CRITICAL_INPUT) else WARNING

def _band_teacher_clashes(spec):
    """a teacher on two groups of one band: the band's groups meet at the same time, so no timetable exists"""
    seen, out = collections.defaultdict(list), []
    for i, x in enumerate(spec["lessons"]):
        if x.get("block"):
            for t in {t for t in x.get("teachers") or [] if t}: seen[(x["block"], t)].append(i + 6)
    for (b, t), rows in sorted(seen.items()):
        if len(rows) > 1:
            out.append(f"{t} teaches {len(rows)} groups of {b} (lesson rows {', '.join(map(str, rows))}), but a band's groups meet at the same time: "
                       "give all but one of them another teacher on step 5.")
    return out

def _no_place(P):
    """lessons longer than every stretch of lesson periods in their level's day: they can go nowhere"""
    bad = collections.defaultdict(list)
    for u in P.units:
        for ln in sorted({ln for ln, _ in u["lessons"]}):
            if not P.starts(u["level"], ln): bad[(u["level"], ln)].append(u["name"])
    return [f"{len(v)} {'lessons' if len(v) != 1 else 'lesson'} of {ln} periods ({', '.join(v[:5])}{f' and {len(v) - 5} more' if len(v) > 5 else ''}) cannot fit anywhere in the {lv} day: "
            f"no stretch between breaks is that long. Shorten the lesson (lesson length on step 3, or the row's lesson pattern on step 5), or change the Day structure."
            for (lv, ln), v in sorted(bad.items())]

def findings(spec, P=None):
    """every problem found before solving, worst first: [dict(level=critical|warning, area, text)]"""
    from ttgen.solver import Problem
    probs = derive(spec); P = P or Problem(spec); out = []
    add = lambda level, area, text: out.append(dict(level=level, area=area, text=text))
    for p in probs: add(_input_level(p), "lessons", p)
    for t in _band_teacher_clashes(spec): add(CRITICAL, "lessons", t)
    A = {lv: sum(row.count("A") for row in rows) for lv, rows in P.grid.items()} if P.spec["school"].get("after_school", True) else {}
    for x in _class_fit(P):
        lv = x["level"]
        if x["kind"] == "over": level = CRITICAL if x["need"] > x["have"] + A.get(lv, 0) else WARNING   # within the after-school slots: it solves, with lessons after school
        elif x["kind"] == "nofit": level = WARNING if A.get(lv) or any(P.windows.get(lv, [])) else CRITICAL   # lessons cannot pack between the breaks
        else: level = WARNING   # tight or almost full: it may still fit
        add(level, "classes", x["text"])
    for x in _room_fit(P): add(CRITICAL if x["kind_"] == "impossible" else WARNING, "venues", x["text"])
    for t in _no_place(P): add(CRITICAL, "lessons", t)
    for t in _teacher_fit(P): add(CRITICAL, "teachers", t)
    for t in _recess_blockers(P): add(CRITICAL, "school", t)
    for area, t in _loads_and_rooms(spec, P): add(WARNING, area, t)
    for t in structure_vs_rules(spec):   # the Day structure and the rules saying different things: a fixed lesson outside lesson time can never be met
        add(*((CRITICAL, "rules") if t.startswith("Fixed lesson") else (WARNING, "school")), t)
    from ttgen.solver import fixed_clashes, rule_label, rule_problems
    for t in fixed_clashes(spec, P): add(CRITICAL, "rules", t)   # e.g. a whole-school CCE slot and a teacher with CCE for two classes
    for i, t in rule_problems(spec, P):   # a rule row the solver cannot use as written: skipped, or it matches no lesson
        add(WARNING, "rules", f"Rule {rule_label(spec['rules'][i])}: {t}")
    out.sort(key=lambda f: f["level"] != CRITICAL)   # stable: critical first, each kind in the order found
    return out

def with_fallbacks(spec):
    """Will it fit? down the give-way order: {critical: [n0, n1, ...], pass_at, items}. n_k counts the critical findings
    once the first k valid choices are taken as the second choice (a step that fails to check counts as the one before it);
    it stops at the first k with none. pass_at is that k, or None when every step still has some."""
    from ttgen import choices
    n = len(choices.ordered(spec)) - len({i for i, _ in choices.problems(spec)})
    counts = []
    for k in range(n + 1):
        try: counts.append(sum(1 for f in findings(choices.apply_all(spec, k)) if f["level"] == CRITICAL))
        except Exception:
            if not counts: raise
            counts.append(counts[-1])
        if counts[-1] == 0: break
    items = [choices.item_label(spec, c) for i, c in choices.ordered(spec) if i not in {i for i, _ in choices.problems(spec)}]
    return dict(critical=counts, pass_at=counts.index(0) if 0 in counts else None, items=items)

def _teacher_fit(P):
    """teachers with more periods of lessons than the cycle has times they can teach them: their levels' lesson (and
    after-school) periods, less the times a Must rule blocks them out. No timetable can fit them."""
    busy = collections.defaultdict(set)
    for r in P.spec.get("rules", []):
        if str(r.get("strength") or "Must") == "Must" and (r.get("rule"), r.get("scope")) in (("Not available", "Teacher"), ("Keep free together", "Department")):
            S, _ = P.rule_positions(r)
            for t in [r["target"]] if r["scope"] == "Teacher" else [t for t, d in P.tdept.items() if d == r["target"]]: busy[t] |= S
    need, lvls = collections.Counter(), collections.defaultdict(set)
    for u in P.units:
        for ln, i in u["lessons"]:
            for t in {t for x in u["rows"] if x["_counts"].get(ln, 0) > i for t in x["teachers"]}: need[t] += ln; lvls[t].add(u["level"])
    out = []
    for t, n in sorted(need.items()):
        k = len({q for lv in lvls[t] for q, _ in P.starts(lv, 1)} - busy[t])
        if n > k: out.append(f"{t} teaches {n} periods but can teach in only {k} periods of the cycle (their levels' lesson times, less the times a Must rule blocks them out): "
                             f"no timetable can fit them. Move at least {n - k} periods to other teachers on step 5.")
    return out

def _recess_blockers(P):
    """floating recess that cannot work: more classes at recess at once than Settings allows (fixed recess, or a whole level
    going together), or a recess window shorter than the recess"""
    out, cap = [], P.recess_cap
    if cap:
        at = collections.Counter()
        for c in P.cls:
            for d, row in enumerate(P.grid.get(P.level_of[c], [])): at.update(d * P.NP + p for p, ch in enumerate(row) if ch == "R")
        q = next((q for q, n in sorted(at.items()) if n > cap), None)
        if q is not None:
            out.append(f"{at[q]} classes have their fixed recess (R) on {P.days[q // P.NP]} period {q % P.NP}, more than the {cap} Settings allows at once "
                       "(Most classes at recess at once): raise it, or turn some of that recess into a recess window (W).")
        if P.recess_by == "Level":
            for lv in P.grid:
                n = sum(1 for c in P.cls if P.level_of[c] == lv)
                if n > cap and any(P.windows.get(lv, [])):
                    out.append(f"{lv} has {n} classes and its floating recess goes by level, so {n} classes are at recess at once: more than the {cap} Settings allows. "
                               "Set Floating recess goes by to Class, or raise Most classes at recess at once.")
    short = sorted({(lv, P.days[d], a, b) for lv, rows in P.windows.items() for d, ws in enumerate(rows) for a, b in ws if b - a + 1 < P.RL})
    if short:
        lv, day, a, b = short[0]
        out.append(f"The recess window on {lv} {day} (periods {a}-{b}) is shorter than the {P.RL}-period recess" + (f", and {len(short) - 1} more" if len(short) > 1 else "")
                   + ": widen the W periods on Day structure, or shorten Floating recess length on Settings.")
    return out

def _loads_and_rooms(spec, P):
    """[(area, text)]: teachers over their allowance or near-full, bands needing more special rooms at once than Venues has
    (the extra groups get a room marked TBC). None of these stops a timetable; each needs a person to decide."""
    out = []
    Lcount = {lv: P.lesson_periods(lv) for lv in P.grid}
    load, lvls = collections.Counter(), collections.defaultdict(set)
    for u in P.units:
        for r in u["rows"]:
            for t in r["teachers"]:
                load[t] += r["periods"]; lvls[t].add(u["level"])
    allow = {t["name"]: t.get("allowance") for t in spec["teachers"]}
    other = {t["name"]: int(t.get("other_duties") or 0) for t in spec["teachers"]}
    for t, n in sorted(load.items(), key=lambda x: -x[1]):
        a = allow.get(t)
        try: a = int(a)
        except (TypeError, ValueError): a = None
        avail = max(Lcount.get(lv, 0) for lv in lvls[t]) if lvls[t] else 0
        if a and n + other.get(t, 0) > a:
            out.append(("teachers", f"{t} teaches {n} periods" + (f" plus {other[t]} periods of other duties" if other.get(t) else "") + f", over their allowance of {a}."))
        if avail and n > 0.85 * avail: out.append(("teachers", f"{t} teaches {n} of the {avail} lesson periods their levels have: very hard to fit."))
    kinds = collections.Counter(v.get("kind") or "classroom" for v in spec["venues"])
    for u in P.units:
        if u["kind"] != "block": continue
        need = collections.Counter(r["room_kind"] for r in u["rows"] if r.get("room_kind") and r["room_kind"] != "classroom")
        for k, n in need.items():
            if n > kinds.get(k, 0): out.append(("venues", f"Band {u['name']} needs {n} '{k}' rooms at once; Venues has {kinds.get(k, 0)}: "
                                                          "the extra groups get a room marked TBC, for the committee to find."))
    # groups bigger than every room they may use: the solver still gives them one of those rooms (oversize), so a person must decide
    big = collections.defaultdict(list)
    for u in P.units:
        for r in u["rows"]:
            kind, rooms, n, oversize = P.allowed(r, u)
            if oversize: big[(kind, max((P.seats[x] or 0) for x in rooms))].append(f"{r['code'] if r['code'] != 'Entire Class' else u['classes'][0]} ({n})")
    for (kind, most), who in sorted(big.items()):
        who = list(dict.fromkeys(who))
        head = (f"{who[0]} has more students than the largest {kind} it may use seats ({most})" if len(who) == 1 else
                f"{len(who)} groups have more students than the largest {kind} they may use seats ({most}): {', '.join(who[:8])}{f' and {len(who) - 8} more' if len(who) > 8 else ''}")
        out.append(("venues", head + ". The timetable still gives " + ("it one of those rooms" if len(who) == 1 else "them those rooms") + "; correct the seats on step 1, or split the group."))
    return out

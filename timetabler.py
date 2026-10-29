"""The timetabler's tools. The AI (or the plain 'generate without AI' flow) calls these; they do the real work with
the ttgen solver, so the AI never places lessons itself and never runs code. Each returns a short text result."""
import collections, copy, json, os, re, time
import adjust
from ttgen.reader import derive
from ttgen.spec import RULE_TYPES, SCOPES
from ttgen.template import write_template
from store import now, write_json

SOLVE_SECONDS = int(os.environ.get("SOLVE_SECONDS") or 300)
SOLVE_MAX = int(os.environ.get("SOLVE_MAX_SECONDS") or 8 * 3600)
STAGED_CLASSES = int(os.environ.get("STAGED_FROM_CLASSES") or 30)   # fresh solves of a school this size go level by level (ttgen.staged)   # the longest the committee (or the AI) may ask a solve to run
WORKERS = int(os.environ.get("SOLVE_WORKERS") or 8)
RULE_NAMES = [r[0] for r in RULE_TYPES]

# ------------------------------------------------------------------------------------------- tool definitions
TOOLS = [
    dict(name="check_setup", description="Check the setup for input problems and do the capacity sums (class periods against the day, teacher loads, special rooms). Call this first.",
         schema=dict(type="object", properties={}, required=[])),
    dict(name="show_setup", description="Show rows of the setup so you can understand a conflict. Rows come with their index, used by change_setup.",
         schema=dict(type="object", properties=dict(
             section=dict(type="string", enum=["rules", "lessons", "teachers", "classes", "subjects", "blocks", "venues", "day_structure", "settings"]),
             filter=dict(type="string", description="only rows containing this text, e.g. a teacher, class, subject or rule name")), required=["section"])),
    dict(name="show_timetable", description="Show the latest timetable: when and where lessons are, with teachers and rooms. Use it before changing anything for a tweak, and to answer questions about the timetable. Filter by a class, teacher, room, subject, group code or block, and/or a day.",
         schema=dict(type="object", properties=dict(
             filter=dict(type="string", description="a class (exact, e.g. 1A), level, teacher, room, subject, group code or block name"),
             day=dict(type="string", description="a day as on Day structure, e.g. Mon or Odd Mon")), required=[])),
    dict(name="solve", description="Run the timetable solver on the current setup. Takes up to `seconds` (default: the time the committee chose on the Generate page). Returns whether a timetable was found, the checks, the after-school lessons and, when it started from the previous timetable, which lessons moved.",
         schema=dict(type="object", properties=dict(seconds=dict(type="integer", description=f"time limit, 60-{SOLVE_MAX}; leave it out to use the committee's choice"),
             staged=dict(type="boolean", description=f"build a fresh timetable level by level (hardest level first, then clear clashes between levels): faster for big, tight schools; default true for {STAGED_CLASSES}+ classes when there is no earlier timetable"),
             keep_previous=dict(type="boolean", description="start from the latest timetable and keep lessons where they are unless a change makes them move (default true once a timetable exists); false only when the committee wants a fresh timetable")), required=[])),
    dict(name="diagnose", description="When no timetable is found: test-solve with the Must rules removed and added back one at a time to find which rule (or the data itself) blocks the timetable. Takes a few minutes.",
         schema=dict(type="object", properties={}, required=[])),
    dict(name="ask_committee", description="Ask the timetable committee a question and wait for their answer. Give 2-4 short, concrete options; they can also type their own answer.",
         schema=dict(type="object", properties=dict(question=dict(type="string"), options=dict(type="array", items=dict(type="string"))), required=["question", "options"])),
    dict(name="change_setup", description="Change the setup, only to carry out what the committee chose. Each change: {action: set|add|delete, section, index (for set/delete), field and value (for set), row (for add)}. For day_structure use {action: set, section: day_structure, level, day, value: code string}.",
         schema=dict(type="object", properties=dict(
             changes=dict(type="array", items=dict(type="object", properties=dict(
                 action=dict(type="string", enum=["set", "add", "delete"]), section=dict(type="string"), index=dict(type="integer"), field=dict(type="string"),
                 value={}, row=dict(type="object"), level=dict(type="string"), day=dict(type="string")), required=["action", "section"])),
             reason=dict(type="string", description="what the committee agreed to")), required=["changes", "reason"])),
    dict(name="finish", description="End this round of work with a short summary for the committee (what was made, what is after school and why, anything to look at). The committee then reviews and publishes.",
         schema=dict(type="object", properties=dict(summary=dict(type="string")), required=["summary"])),
]

FIELDS = dict(
    rules=["scope", "target", "subject", "rule", "level", "week", "day", "from", "to", "number", "strength", "note"],
    lessons=["level", "subject", "block", "classes", "teachers", "students", "periods_override", "code_override", "note"],
    teachers=["name", "short", "dept", "allowance", "role", "other_duties", "can_teach", "note"],
    classes=["class", "level", "size", "home_room", "note"],
    venues=["room", "kind", "capacity", "note"],
    subjects=["subject", "code", "tag", "dept", "room_kind", "lesson_length", "periods", "note"],
    blocks=["block", "level", "classes", "note"])


# ------------------------------------------------------------------------------------------- descriptions
def rule_text(i, r):
    bits = [f"{r.get('scope')} {r.get('target') or ''}".strip()]
    if r.get("subject"): bits.append(str(r["subject"]))
    t = f"{r.get('rule')}: " + " ".join(bits)
    when = []
    if r.get("week") not in (None, "", "Both"): when.append(str(r["week"]))
    if r.get("day") not in (None, "", "All"): when.append(str(r["day"]))
    if r.get("from") not in (None, "") or r.get("to") not in (None, ""): when.append(f"periods {r.get('from', '')}-{r.get('to', '')}")
    if r.get("number") not in (None, ""): when.append(f"number {r['number']}")
    return f"[{i}] {t}" + (f" ({', '.join(when)})" if when else "") + f" [{r.get('strength') or 'Must'}]"

def row_text(section, i, x):
    if section == "rules": return rule_text(i, x)
    if section == "lessons":
        return (f"[{i}] {x.get('level')} {x.get('subject')} | block {x.get('block') or 'whole class'} | classes {', '.join(x.get('classes') or [])} | "
                f"teachers {', '.join(x.get('teachers') or []) or 'NONE'} | code {x.get('code', '')} | periods {x.get('periods', '')}")
    if section == "teachers":
        ct = "; ".join(f"{c.get('subject')}@{c.get('levels')}" for c in x.get("can_teach") or [])
        od = f" other duties {x['other_duties']}" if x.get("other_duties") else ""
        return f"[{i}] {x.get('name')} ({x.get('short')}) dept {x.get('dept')} role {x.get('role') or '-'} allowance {x.get('allowance')}{od} | can teach {ct}"
    if section == "subjects":
        return f"[{i}] {x.get('subject')} code {x.get('code')} tag {x.get('tag')} dept {x.get('dept')} room {x.get('room_kind') or 'home'} length {x.get('lesson_length') or 'standard'} periods {x.get('periods')}"
    return f"[{i}] " + ", ".join(f"{k} {v}" for k, v in x.items() if v not in (None, "", []) and not k.startswith("_"))


# ------------------------------------------------------------------------------------------- capacity sums
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
    Lcount = {lv: sum(row.count("L") for row in rows) for lv, rows in P.grid.items()}
    Acount = {lv: sum(row.count("A") for row in rows) for lv, rows in P.grid.items()}
    runs = {lv: [len(m) for row in rows for m in re.findall(r"L+", row)] for lv, rows in P.grid.items()}
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
    use = "LA" if P.spec["school"].get("after_school", True) else "L"
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
                                                              f"unless step 7 has a 'Room · At most N at once' rule for it."))
            elif F == every and n > 0.9 * have:
                out.append(dict(row, kind_="tight", text=f"Lessons that need a {kind} room fill {n} of the {have} class-periods its rooms ({names}) hold: very hard to fit."))
    return out

def impossible(spec):
    """what rules out every timetable before solving: a room kind that cannot hold its lessons, or a class with more
    periods than its lesson and after-school periods"""
    from ttgen.solver import Problem
    derive(spec); P = Problem(spec); out = [x["text"] for x in _room_fit(P) if x["kind_"] == "impossible"]
    A = {lv: sum(row.count("A") for row in rows) for lv, rows in P.grid.items()} if P.spec["school"].get("after_school", True) else {}
    out += [x["text"] for x in _class_fit(P) if x["kind"] == "over" and x["need"] > x["have"] + A.get(x["level"], 0)]
    return out

def capacity(spec, P=None, fit=None):
    from ttgen.solver import Problem
    P = P or Problem(spec); out = [x["text"] for x in (_class_fit(P) if fit is None else fit)] + [x["text"] for x in _room_fit(P)]
    Lcount = {lv: sum(row.count("L") for row in rows) for lv, rows in P.grid.items()}
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
            out.append(f"{t} teaches {n} periods" + (f" plus {other[t]} periods of other duties" if other.get(t) else "") + f", over their allowance of {a}.")
        if avail and n > 0.85 * avail: out.append(f"{t} teaches {n} of the {avail} lesson periods their levels have: very hard to fit.")
    kinds = collections.Counter(v.get("kind") or "classroom" for v in spec["venues"])
    for u in P.units:
        if u["kind"] != "block": continue
        need = collections.Counter(r["room_kind"] for r in u["rows"] if r.get("room_kind") and r["room_kind"] != "classroom")
        for k, n in need.items():
            if n > kinds.get(k, 0): out.append(f"Block {u['name']} needs {n} '{k}' rooms at once; Venues has {kinds.get(k, 0)}.")
    return out

def span_text(secs):
    return f"{secs} s" if secs < 60 else f"{secs // 60} min" + (f" {secs % 60} s" if secs % 60 else "")

def advice(spec, status, secs, notes=()):
    """when no timetable is found: why (capacity lines and solver notes) and what the committee can change.
    Returns (reasons, fixes); each fix is dict(text, go) where go is the editor step that makes the change."""
    from ttgen.solver import Problem
    derive(spec); P = Problem(spec); every = _class_fit(P)
    fit = [x for x in every if x["kind"] in ("over", "nofit", "tight")]
    cap = capacity(spec, P, every)
    reasons = cap + [n for n in notes if n not in cap and not n.startswith("No timetable found")]
    fixes = []
    if fit:
        names = ", ".join(x["cls"] for x in fit)
        fixes.append(dict(go="lessons", text=f"Give {names} some room: take a lesson (a few periods) off their busiest students, with Periods override on step 6 or fewer periods for the subject on step 3."))
        fixes.append(dict(go="school", text="Or make the day longer: a later 'Lessons end by' time or more L periods in the Day structure (School & day), or allow after-school slots."))
    if any(c.split(" teaches ")[0] in {t["name"] for t in spec["teachers"]} for c in cap if " teaches " in c):
        fixes.append(dict(go="lessons", text="Move some groups from the busiest teachers named above to other teachers on step 6."))
    if any(c.startswith("Block ") and " rooms at once" in c for c in cap):
        fixes.append(dict(go="venues", text="Add rooms of the kinds named above on step 1, or split the block on step 5."))
    for x in _room_fit(P):
        if x["kind_"] != "impossible": continue
        fixes.insert(0, dict(go="rules", text=f"Let the '{x['kind']}' rooms ({', '.join(x['rooms'])}) take more classes at once: on step 7 add a rule 'Room · {x['rooms'][0]} · At most N at once' "
                                              f"for each of them (a Settings note such as '{' and '.join(x['rooms'][:2])} take 2 classes each' does the same). "
                                              f"Or add '{x['kind']}' rooms on step 1, or give some subjects another room kind on step 3."))
    if any("matches nothing" in n or "no lesson matches" in n for n in notes):
        fixes.append(dict(go="rules", text="Remove or correct the fixed lessons that match no lesson (step 7)."))
    if any(str(r.get("strength") or "Must") == "Must" for r in spec.get("rules", [])):
        fixes.append(dict(go="rules", text="Turn off any rule the school can do without (step 7, and the rules on School & day), then generate again. "
                                           "With the AI timetabler, ask it to diagnose: it tests the rules one at a time and names any that block the timetable."))
    if status == "INFEASIBLE" and not fit and not any(x["kind_"] == "impossible" for x in _room_fit(P)):
        fixes.insert(0, dict(go="rules", text="The solver proved that no timetable exists with this setup: a rule or the data contradicts itself. Start with the rules and the lines above."))
    if status != "INFEASIBLE":
        fixes.append(dict(go="generate", text=f"Nothing was found in {span_text(secs)}, which does not prove that no timetable exists. If nothing above needs changing, "
                                              "give the solver longer: pick a longer 'Solve for up to' time on Generate & publish and generate again."))
    return reasons, fixes


# ------------------------------------------------------------------------------------------- the tools
def t_check_setup(run, args):
    run.emit("tool", text="Checking the setup and doing the capacity sums...")
    spec = run.spec
    probs = derive(spec)
    try: cap = capacity(spec)
    except Exception as e: cap = [f"Capacity sums failed: {e}"]
    counts = f"{len(spec['classes'])} classes, {len(spec['teachers'])} teachers, {len(spec['lessons'])} lesson rows, {len(spec['blocks'])} blocks, {len(spec.get('rules', []))} rules, {len(spec.get('students', []))} students."
    lines = [counts, "Input problems:" if probs else "Input problems: none."] + [f"- {p}" for p in probs[:40]]
    lines += ["Capacity:" if cap else "Capacity: nothing looks too tight."] + [f"- {c}" for c in cap[:40]]
    lines += ["Rules:"] + [f"- {rule_text(i, r)}" for i, r in enumerate(spec.get("rules", []))]
    run.emit("check", text=f"{len(probs)} input problems, {len(cap)} capacity warnings.", items=(probs + cap)[:30])
    return "\n".join(lines)

def t_show_setup(run, args):
    sec = args.get("section"); flt = str(args.get("filter") or "").lower(); spec = run.spec
    if sec == "settings":
        return "\n".join(f"{k}: {v}" for k, v in spec["school"].items())
    if sec == "day_structure":
        out = []
        for lv, days in spec["day_structure"].items():
            for d, codes in days.items():
                line = f"{lv} | {d} | {codes}"
                if not flt or flt in line.lower(): out.append(line)
        return "Codes per period (index 0 first): F assembly, L lesson, R recess, U lunch, A after-school, . none\n" + "\n".join(out[:80])
    rows = spec.get(sec)
    if rows is None: return f"Unknown section {sec}."
    lines = [row_text(sec, i, x) for i, x in enumerate(rows)]
    if flt: lines = [l for l in lines if flt in l.lower()]
    more = f"\n... {len(lines) - 60} more; use a narrower filter." if len(lines) > 60 else ""
    return ("\n".join(lines[:60]) or "No rows match.") + more

def _summary(res_status, m):
    ch = m["checks"]
    return dict(status=res_status, ok=ch["ok"], problems=ch["problems"][:12], after=ch["after_school"], notes=m["notes"][:12],
                lessons=ch["lessons"], side=ch["side_by_side"])

def _previous(run, args):
    """the latest timetable's placements {lesson key: start}, unless the AI asked for a fresh timetable"""
    if str(args.get("keep_previous", True)).lower() == "false": return None
    path = (run.solved or {}).get("placements")
    if not path: return None
    try:
        with open(path, encoding="utf-8") as f: return json.load(f)
    except (OSError, ValueError): return None

def _when(P, start, ln):
    from ttgen.report import clock
    d, p = divmod(start, P.NP); sc = P.spec["school"]
    return f"{P.days[d]} {clock(sc, p)}-{clock(sc, p + ln)}"

def t_solve(run, args):
    from ttgen.solver import solve
    from ttgen.report import write_timetable
    secs = max(20, min(SOLVE_MAX, int(args.get("seconds") or run.seconds or SOLVE_SECONDS)))
    span = f"{secs} s" if secs < 60 else f"{secs // 60} min" + (f" {secs % 60} s" if secs % 60 else "")
    previous = _previous(run, args)
    spec = copy.deepcopy(run.spec); t0 = time.time(); as_solved = json.loads(json.dumps(spec))   # the setup this timetable is made from (Adjust rebuilds it)
    pins = adjust.pins(run)   # lessons placed by hand stay where the committee put them
    # a big school's first timetable is built level by level (one whole-school model can find nothing for hours);
    # re-solves start from the latest timetable instead, so lessons stay where they are
    staged = args.get("staged")
    staged = (not previous and not pins and len(spec["classes"]) >= STAGED_CLASSES) if staged is None else bool(staged) and not previous and not pins
    run.emit("tool", text=(f"Solving level by level, hardest level first (up to {span} in all): a school with {len(spec['classes'])} classes solves faster that way. " if staged else
                           f"Solving (up to {span}){', starting from the latest timetable so lessons stay where they are unless a change moves them' if previous else ''}. ")
                          + "The best timetable so far is kept if you stop early.")
    def log(line):
        if "cost" in line:
            run.progress = f"Solving: {int(time.time() - t0)} s, best timetable so far has cost {line.split('cost')[-1].strip()} (lower is better)."
    if run.stop.is_set(): return "Stopped before solving."
    blockers = impossible(copy.deepcopy(spec))   # no timetable can exist: say why now instead of searching for hours
    if blockers:
        reasons, fixes = advice(copy.deepcopy(spec), "INFEASIBLE", secs)
        run.emit("nosolution", text="No timetable is possible with this setup, so the solver did not run.", items=reasons[:15], data=dict(status="INFEASIBLE", fixes=fixes))
        run.save()
        return "No timetable is possible with this setup, so the solver did not run:\n" + "\n".join(f"- {x}" for x in blockers) + \
               "\nSuggested fixes (shown to the committee):\n" + "\n".join(f"- {f['text']}" for f in fixes)
    if staged:
        from ttgen.staged import solve_staged
        def slog(*a):
            line = " ".join(str(x) for x in a).strip()
            if line: run.progress = f"Solving level by level, {int(time.time() - t0)} s: {line}"
        res = solve_staged(copy.deepcopy(spec), time_per_step=max(60, min(300, secs // 6)), workers=WORKERS, log=slog, stop=run.stop, deadline=t0 + secs)
        left = int(secs - (time.time() - t0))
        if not res["lessons"] and not run.stop.is_set() and left > 120:
            run.emit("tool", text=f"Level by level found no timetable ({'; '.join(res.get('notes', []))[:200]}). Trying the whole school at once for the {span_text(left)} left.")
            res = solve(spec, time_limit=left, workers=WORKERS, log=log, stop=run.stop)
    else:
        res = solve(spec, time_limit=secs, workers=WORKERS, log=log, stop=run.stop, previous=previous, pins=pins)
    run.progress = ""; run.solves += 1; n = run.solves
    setup_path = os.path.join(run.dir, f"solve{n}_setup.xlsx"); write_template(spec, setup_path)
    if not res["lessons"]:
        notes = res.get("notes", [])[:12]
        try: reasons, fixes = advice(spec, res["status"], secs, notes)
        except Exception as e: reasons, fixes = notes + [f"Could not work out why ({e})."], []
        run.emit("nosolution", text=("No timetable is possible with this setup." if res["status"] == "INFEASIBLE" else f"No timetable found in {span}."),
                 items=reasons[:15], data=dict(status=res["status"], fixes=fixes))
        run.save()
        return f"No timetable found. Solver status {res['status']} after {int(time.time() - t0)} s.\nWhy:\n" + "\n".join(f"- {x}" for x in reasons[:15]) + \
               "\nSuggested fixes (shown to the committee):\n" + "\n".join(f"- {f['text']}" for f in fixes) + \
               ("\nINFEASIBLE means a hard contradiction: call diagnose." if res["status"] == "INFEASIBLE" else "\nUNKNOWN means not found in time: try a longer solve before changing anything.")
    tt_path = os.path.join(run.dir, f"solve{n}_timetable.xlsx")
    _, _, _, m = write_timetable(res, tt_path, return_model=True)
    pl_path = os.path.join(run.dir, f"solve{n}_placements.json"); write_json(pl_path, {L["key"]: L["start"] for L in res["lessons"]})
    spec_path = os.path.join(run.dir, f"solve{n}_spec.json"); write_json(spec_path, as_solved)
    s = _summary(res["status"], m); s.update(n=n, at=now(), setup=setup_path, timetable=tt_path, placements=pl_path, spec=spec_path, seconds=int(time.time() - t0))
    run.solved = s; adjust.carry_pins(run, pins, res); run.save()
    run.emit("timetable", text=("All checks passed." if s["ok"] else f"{len(s['problems'])} problems found.") +
             (f" {len(s['after'])} lessons are after school." if s["after"] else " Nothing is after school."), data={k: v for k, v in s.items() if k not in ("setup", "timetable", "placements")})
    out = [f"Timetable found ({res['status']}) in {s['seconds']} s: {s['lessons']} lessons placed."]
    out.append("All checks passed." if s["ok"] else "Problems:\n" + "\n".join(f"- {p}" for p in s["problems"]))
    out.append("After-school lessons:\n" + "\n".join(f"- {a}" for a in s["after"]) if s["after"] else "After-school lessons: none.")
    if previous:
        P, Ls = res["problem"], sorted(res["lessons"], key=lambda L: L["start"])
        moved = [f"{L['unit']['name']}: {_when(P, previous[L['key']], L['ln'])} -> {_when(P, L['start'], L['ln'])}"
                 for L in Ls if L["key"] in previous and previous[L["key"]] != L["start"]]
        kept, new = sum(1 for L in Ls if previous.get(L["key"]) == L["start"]), sum(1 for L in Ls if L["key"] not in previous)
        head = f"Kept {kept} of {len(Ls)} lessons where they were; {len(moved)} moved" + (f", {new} new" if new else "") + "."
        run.emit("moved", text=head, items=moved[:40])
        out.append(f"Started from the previous timetable. {head}" + ("".join(f"\n- {x}" for x in moved[:20]) + (f"\n- ...and {len(moved) - 20} more" if len(moved) > 20 else "")))
    if s["notes"]: out.append("Notes (includes rules checked after solving and rules that were skipped):\n" + "\n".join(f"- {x}" for x in s["notes"]))
    return "\n".join(out)

def t_show_timetable(run, args):
    import openpyxl
    path = (run.solved or {}).get("timetable")
    if not path or not os.path.exists(path): return "There is no timetable yet: solve first."
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    if "Lessons" not in wb.sheetnames: return "The latest timetable has no Lessons sheet."
    rows = wb["Lessons"].iter_rows(values_only=True)
    ix = {str(h): i for i, h in enumerate(next(rows))}
    g = lambda row, k: "" if row[ix[k]] is None else str(row[ix[k]])
    flt, day = str(args.get("filter") or "").strip().lower(), str(args.get("day") or "").strip().lower()
    order = {d.lower(): i for lv in run.spec["day_structure"].values() for i, d in enumerate(lv)}
    hits = []
    for row in rows:
        if not row or row[0] is None: continue
        if day and day not in g(row, "Day").lower(): continue
        if flt and flt not in [c.strip().lower() for c in g(row, "Classes").split(",")] + [g(row, "Level").lower()] and \
           not any(flt in g(row, k).lower() for k in ("Teachers", "Room", "Subject", "Group", "Block")): continue
        hits.append(row)
    wb.close()
    hits.sort(key=lambda r: (order.get(g(r, "Day").lower(), 99), int(r[ix["Start period"]] or 0), g(r, "Classes")))
    lines = [f"{g(r, 'Day')} {g(r, 'Starts')}-{g(r, 'Ends')} | {g(r, 'Classes')} | {g(r, 'Subject')}" + (f" ({g(r, 'Block')})" if g(r, "Block") else "") +
             f" | {g(r, 'Group')} | {g(r, 'Teachers') or 'no teacher'} | {g(r, 'Room')}" + (" | after school" if g(r, "After school") else "") for r in hits]
    head = f"Timetable #{run.solved.get('n')} ({run.solved.get('at')}): {len(lines)} lesson rows match (one row per group; rows of a block lesson share its time)."
    more = f"\n...{len(lines) - 150} more; narrow the filter or pick a day." if len(lines) > 150 else ""
    return head + "\n" + ("\n".join(lines[:150]) or "No lessons match.") + more

def t_diagnose(run, args):
    from ttgen.solver import solve
    run.emit("tool", text="Looking for what blocks the timetable: a few short test solves, a few minutes in all...")
    base = copy.deepcopy(run.spec); rules = base.get("rules", []); t0 = time.time(); budget = 420
    must = [i for i, r in enumerate(rules) if str(r.get("strength") or "Must") == "Must"]
    def test(keep, secs):
        sp = copy.deepcopy(base); sp["rules"] = [rules[i] for i in keep]
        run.progress = f"Diagnosing: test {len(keep) + 1} of {len(must) + 1}, {int(time.time() - t0)} s so far."
        return solve(sp, time_limit=secs, workers=WORKERS, log=lambda *a: None, stop=run.stop)["status"]
    out = []
    try: out += [f"Capacity: {c}" for c in capacity(base)]
    except Exception: pass
    st = test([], 60)
    if st not in ("OPTIMAL", "FEASIBLE"):
        run.progress = ""
        return "\n".join(out + [f"Even with every rule removed there is no timetable ({st} in 60 s). The data itself does not fit: look at the capacity lines, teacher loads, special rooms and the Day structure."])
    kept = []
    for i in must:
        if run.stop.is_set() or time.time() - t0 > budget: out.append("Stopped early (time budget)."); break
        st = test(kept + [i], 40)
        if st == "INFEASIBLE": out.append(f"Blocks the timetable: {rule_text(i, rules[i])}")
        elif st == "UNKNOWN": out.append(f"Makes it much harder (nothing found in 40 s): {rule_text(i, rules[i])}")
        else: kept.append(i)
    run.progress = ""
    if not any(x.startswith(("Blocks", "Makes")) for x in out): out.append("Every Must rule fits on its own; the combination of rules with the Prefer rules or the time limit is the issue. Try a longer solve.")
    return "\n".join(out)

def t_ask_committee(run, args):
    q = str(args.get("question") or "").strip() or "How would you like to continue?"
    opts = [str(o) for o in (args.get("options") or [])][:6]
    ans = run.ask(q, opts)
    if ans is None: return "The committee stopped this run."
    return f"The committee answered: {ans}"

def _coerce(v):
    if isinstance(v, str):
        t = v.strip()
        if t.lstrip("-").isdigit(): return int(t)
    return v

def t_change_setup(run, args):
    changes = args.get("changes") or []; spec = run.spec; done, errors = [], []
    for ch in changes:
        act, sec = ch.get("action"), ch.get("section")
        try:
            if sec == "day_structure":
                lv, day, val = ch.get("level"), ch.get("day"), str(ch.get("value") or "")
                NP = int(spec["school"]["periods_per_day"])
                if lv not in spec["day_structure"] or day not in spec["day_structure"][lv]: raise ValueError(f"no Day structure row {lv} / {day}")
                if len(val) != NP or any(c not in "FLRUA." for c in val): raise ValueError(f"value must be {NP} codes from F L R U A .")
                old = spec["day_structure"][lv][day]; spec["day_structure"][lv][day] = val
                done.append(f"Day structure {lv} {day}: {old} -> {val}"); continue
            if sec not in FIELDS: raise ValueError(f"unknown section {sec}")
            rows = spec.setdefault(sec, [])
            if act == "add":
                row = {k: _coerce(v) for k, v in (ch.get("row") or {}).items() if k in FIELDS[sec]}
                if sec == "rules":
                    if row.get("rule") not in RULE_NAMES: raise ValueError(f"unknown rule {row.get('rule')}; use one of {', '.join(RULE_NAMES)}")
                    if row.get("scope") not in SCOPES: raise ValueError(f"scope must be one of {', '.join(SCOPES)}")
                    row.setdefault("strength", "Must"); row.setdefault("week", "Both"); row.setdefault("day", "All")
                rows.append(row); done.append(f"Added to {sec}: {row_text(sec, len(rows) - 1, row)}")
            elif act in ("set", "delete"):
                i = int(ch.get("index"))
                if not 0 <= i < len(rows): raise ValueError(f"{sec} has no row {i}")
                if act == "delete":
                    gone = rows.pop(i); done.append(f"Removed from {sec}: {row_text(sec, i, gone)}")
                else:
                    f, v = ch.get("field"), _coerce(ch.get("value"))
                    if f not in FIELDS[sec]: raise ValueError(f"{sec} has no field {f}; fields: {', '.join(FIELDS[sec])}")
                    if sec == "rules" and f == "strength" and v not in ("Must", "Prefer"): raise ValueError("strength is Must or Prefer")
                    if sec == "rules" and f == "rule" and v not in RULE_NAMES: raise ValueError("unknown rule name")
                    old = rows[i].get(f); rows[i][f] = v
                    done.append(f"{sec.capitalize()} row {i} ({row_text(sec, i, rows[i])[:90]}): {f} {old!r} -> {v!r}")
            else: raise ValueError(f"unknown action {act}")
        except Exception as e:
            errors.append(f"{ch}: {e}")
    if done:
        derive(spec); run.changes += [dict(at=now(), text=d, reason=args.get("reason", "")) for d in done]; run.save()
        run.emit("change", text=str(args.get("reason") or "Setup changed"), items=done)
    return ("Done:\n" + "\n".join(f"- {d}" for d in done) if done else "Nothing changed.") + ("\nNot done:\n" + "\n".join(f"- {e}" for e in errors) if errors else "")

def t_finish(run, args):
    run.emit("summary", text=str(args.get("summary") or "Finished."))
    run.finished = True
    return "Finished. The committee can now review and publish, or ask for more changes."

IMPL = dict(check_setup=t_check_setup, show_setup=t_show_setup, show_timetable=t_show_timetable, solve=t_solve, diagnose=t_diagnose,
            ask_committee=t_ask_committee, change_setup=t_change_setup, finish=t_finish)

def call_tool(run, name, args):
    f = IMPL.get(name)
    if not f: return f"Unknown tool {name}."
    try: return f(run, args or {})
    except Exception as e:
        run.emit("error", text=f"{name} failed: {e}")
        return f"{name} failed: {e}"


# ------------------------------------------------------------------------------------------- without AI
def plain_flow(run):
    """generate without AI: check, solve, report"""
    out = t_check_setup(run, {})
    if run.stop.is_set(): return
    t_solve(run, {})
    if run.solved and not run.stop.is_set():
        s = run.solved
        run.emit("summary", text=("All checks passed. " if s["ok"] else "Some checks failed: see the problems above. ") +
                 (f"{len(s['after'])} lessons fall in after-school slots." if s["after"] else "Nothing is after school.") +
                 " Preview it, then publish when the committee is happy. With an AI set up in Railway, the chat can work through conflicts with you.")
    elif not run.stop.is_set():
        run.emit("summary", text="No timetable was found. See why and how to fix it above: give a tight class some room, turn off a rule, or let the solver run longer, then generate again.")

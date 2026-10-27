"""The timetabler's tools. The AI (or the plain 'generate without AI' flow) calls these; they do the real work with
the ttgen solver, so the AI never places lessons itself and never runs code. Each returns a short text result."""
import collections, copy, json, os, time
from ttgen.reader import derive
from ttgen.spec import RULE_TYPES, SCOPES
from ttgen.template import write_template
from store import now, write_json

SOLVE_SECONDS = int(os.environ.get("SOLVE_SECONDS") or 300)
SOLVE_MAX = int(os.environ.get("SOLVE_MAX_SECONDS") or 1800)
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
    dict(name="solve", description="Run the timetable solver on the current setup. Takes up to `seconds` (default from the app). Returns whether a timetable was found, the checks, the after-school lessons and, when it started from the previous timetable, which lessons moved.",
         schema=dict(type="object", properties=dict(seconds=dict(type="integer", description="time limit, 60-1800"),
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
    rules=["scope", "target", "subject", "rule", "week", "day", "from", "to", "number", "strength", "note"],
    lessons=["level", "subject", "block", "classes", "teachers", "students", "periods_override", "code_override", "note"],
    teachers=["name", "short", "dept", "allowance", "can_teach", "note"],
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
        return f"[{i}] {x.get('name')} ({x.get('short')}) dept {x.get('dept')} allowance {x.get('allowance')} | can teach {ct}"
    if section == "subjects":
        return f"[{i}] {x.get('subject')} code {x.get('code')} tag {x.get('tag')} dept {x.get('dept')} room {x.get('room_kind') or 'home'} length {x.get('lesson_length') or 'standard'} periods {x.get('periods')}"
    return f"[{i}] " + ", ".join(f"{k} {v}" for k, v in x.items() if v not in (None, "", []) and not k.startswith("_"))


# ------------------------------------------------------------------------------------------- capacity sums
def capacity(spec):
    from ttgen.solver import Problem
    P = Problem(spec); out = []
    Lcount = {lv: sum(row.count("L") for row in rows) for lv, rows in P.grid.items()}
    Acount = {lv: sum(row.count("A") for row in rows) for lv, rows in P.grid.items()}
    units = {u["id"]: u for u in P.units}
    whole = collections.Counter()
    for u in P.units:
        if u["kind"] == "class":
            whole[u["classes"][0]] += sum(ln for ln, _ in u["lessons"])
    prof = P.students_profiles()
    for c, lv in P.level_of.items():
        if lv not in Lcount: continue
        need = whole[c] + max([sum(ln * n for uid, cnt in p.items() for ln, n in cnt.items()) for p in prof.get(c, [])] or [0])
        if need > Lcount[lv]:
            out.append(f"Class {c} needs {need} periods but {lv} has {Lcount[lv]} lesson periods a cycle (+{Acount[lv]} after-school): at least {need - Lcount[lv]} periods must go after school.")
        elif need > 0.97 * Lcount[lv]:
            out.append(f"Class {c} is almost full: {need} of {Lcount[lv]} lesson periods.")
    load, lvls = collections.Counter(), collections.defaultdict(set)
    for u in P.units:
        for r in u["rows"]:
            for t in r["teachers"]:
                load[t] += r["periods"]; lvls[t].add(u["level"])
    allow = {t["name"]: t.get("allowance") for t in spec["teachers"]}
    for t, n in sorted(load.items(), key=lambda x: -x[1]):
        a = allow.get(t)
        try: a = int(a)
        except (TypeError, ValueError): a = None
        avail = max(Lcount.get(lv, 0) for lv in lvls[t]) if lvls[t] else 0
        if a and n > a: out.append(f"{t} teaches {n} periods, over their allowance of {a}.")
        if avail and n > 0.85 * avail: out.append(f"{t} teaches {n} of the {avail} lesson periods their levels have: very hard to fit.")
    kinds = collections.Counter(v.get("kind") or "classroom" for v in spec["venues"])
    for u in P.units:
        if u["kind"] != "block": continue
        need = collections.Counter(r["room_kind"] for r in u["rows"] if r.get("room_kind") and r["room_kind"] != "classroom")
        for k, n in need.items():
            if n > kinds.get(k, 0): out.append(f"Block {u['name']} needs {n} '{k}' rooms at once; Venues has {kinds.get(k, 0)}.")
    return out


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
    secs = max(20, min(SOLVE_MAX, int(args.get("seconds") or SOLVE_SECONDS)))
    span = f"{secs} s" if secs < 60 else f"{secs // 60} min" + (f" {secs % 60} s" if secs % 60 else "")
    previous = _previous(run, args)
    run.emit("tool", text=f"Solving (up to {span}){', starting from the latest timetable so lessons stay where they are unless a change moves them' if previous else ''}. "
                          "The best timetable so far is kept if you stop early.")
    spec = copy.deepcopy(run.spec); t0 = time.time()
    def log(line):
        if "cost" in line:
            run.progress = f"Solving: {int(time.time() - t0)} s, best timetable so far has cost {line.split('cost')[-1].strip()} (lower is better)."
    if run.stop.is_set(): return "Stopped before solving."
    res = solve(spec, time_limit=secs, workers=WORKERS, log=log, stop=run.stop, previous=previous)
    run.progress = ""; run.solves += 1; n = run.solves
    setup_path = os.path.join(run.dir, f"solve{n}_setup.xlsx"); write_template(spec, setup_path)
    if not res["lessons"]:
        notes = res.get("notes", [])[:12]
        run.emit("nosolution", text=f"No timetable found ({res['status']}).", items=notes)
        run.save()
        return f"No timetable found. Solver status {res['status']} after {int(time.time() - t0)} s.\nNotes:\n" + "\n".join(f"- {x}" for x in notes) + \
               ("\nINFEASIBLE means a hard contradiction: call diagnose." if res["status"] == "INFEASIBLE" else "\nUNKNOWN means not found in time: try a longer solve before changing anything.")
    tt_path = os.path.join(run.dir, f"solve{n}_timetable.xlsx")
    _, _, _, m = write_timetable(res, tt_path, return_model=True)
    pl_path = os.path.join(run.dir, f"solve{n}_placements.json"); write_json(pl_path, {L["key"]: L["start"] for L in res["lessons"]})
    s = _summary(res["status"], m); s.update(n=n, at=now(), setup=setup_path, timetable=tt_path, placements=pl_path, seconds=int(time.time() - t0))
    run.solved = s; run.save()
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
        run.emit("summary", text="No timetable was found. Look at the notes above, relax a Must rule or give the solver more time (SOLVE_SECONDS), then generate again.")

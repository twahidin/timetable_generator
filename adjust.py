"""Changing the latest timetable by hand before it is published. The committee moves a lesson (shifts it earlier or
later, or cuts it and pastes it somewhere else); the move is checked against the rules the solver keeps, and when it
clashes they see why and the ways out: a free time, a swap, letting the solver make room (it keeps the moved lesson
there and moves as few other lessons as it can), or asking the AI (merge or split a group, change a teacher).

Moves change the run's latest timetable (its placements file); the timetable workbook is rewritten before Preview and
Publish. Lessons moved by hand are pinned: later solves in the run keep them where they were put."""
import collections, copy, math, os, threading
from ttgen.solver import Problem, lesson_domains, units_for
from ttgen.report import assign_rooms, check, clock
from store import now, read_json, write_json

_lock = threading.RLock()
_boards = {}   # (run id, solve number) -> Board


class Board:
    """the latest timetable, rebuilt from the setup it was solved from and its placements {lesson key: start}"""
    def __init__(self, spec, placements):
        self.spec = spec
        self.P = P = Problem(copy.deepcopy(spec)); self.NP = NP = P.NP; self.sc = P.spec["school"]
        self.rules = [r for r in P.spec.get("rules", []) if str(r.get("strength") or "Must") == "Must"]
        self.once = any(r.get("rule") == "Once a day per group" for r in self.rules)
        self.dom = {d["key"]: d for d in lesson_domains(P, P.spec.get("rules", []), [])}
        self.L = {k: dict(unit=d["u"], ln=d["ln"], i=d["i"], part=d["part"], start=placements[k], key=k) for k, d in self.dom.items() if k in placements}
        self.tset = {k: {t for r in L["part"] for t in r["teachers"]} for k, L in self.L.items()}
        self.by_unit = collections.defaultdict(list)
        for k, L in self.L.items(): self.by_unit[L["unit"]["id"]].append(k)
        # two lessons that are not whole-class lessons may not overlap when some student takes both (the solver's profiles)
        self.member = collections.defaultdict(set)
        for c, plist in P.students_profiles().items():
            for j, use in enumerate(plist):
                for uid, cnt in use.items():
                    for k in self.by_unit.get(uid, ()):
                        L = self.L[k]
                        if L["unit"]["kind"] != "class" and cnt.get(L["ln"], 0) > L["i"]: self.member[k].add((c, j))
        code_unit = {r["code"]: u["id"] for u in P.units for r in u["rows"] if r.get("code") and r["code"] != "Entire Class"}
        self.stu = collections.defaultdict(set)   # unit -> students on the Students sheet in it (for the counts in messages)
        for n, s in enumerate(P.spec.get("students", [])):
            for g in s.get("groups") or []:
                if g in code_unit: self.stu[code_unit[g]].add(n)
        self.busy = collections.defaultdict(dict)   # teacher -> {period: why} from Must 'Not available' / 'Keep free together'
        for r in self.rules:
            if (r.get("rule"), r.get("scope")) in (("Not available", "Teacher"), ("Keep free together", "Department")):
                S, _ = P.rule_positions(r)
                who = [r["target"]] if r["scope"] == "Teacher" else [t for t, d in P.tdept.items() if d == r["target"]]
                for t in who:
                    for q in S: self.busy[t][q] = r.get("note") or r["rule"].lower()
        rooms = collections.Counter(); cap = {v["room"]: 1 for v in P.spec["venues"]}
        for r in self.rules:
            if r.get("rule") == "At most N at once" and r.get("scope") == "Room" and r.get("target") in cap and r.get("number"): cap[r["target"]] = int(r["number"])
        for v in P.spec["venues"]: rooms[v.get("kind") or "classroom"] += cap[v["room"]]
        self.kind_cap = rooms
        self.kinds = {k: collections.Counter((x["room_kind"] or "classroom") for x in L["part"]) for k, L in self.L.items()}
        self.index()

    def index(self):
        self.at = collections.defaultdict(set)
        for k, L in self.L.items():
            for q in range(L["start"], L["start"] + L["ln"]): self.at[q].add(k)

    # ---- words
    def when(self, start, ln):
        d, p = divmod(start, self.NP)
        return f"{self.P.days[d]} {clock(self.sc, p)}–{clock(self.sc, p + ln)}"
    def name(self, k):
        u = self.L[k]["unit"]
        if u["kind"] == "class": return u["name"]
        if u["kind"] == "group": r = u["rows"][0]; return f"{r['subject']} {r['code']} ({', '.join(u['classes'])})"
        return f"{u['name']} block"

    # ---- checks
    def why_not(self, k, s):
        L = self.L[k]; u = L["unit"]
        if s not in {p for p, _ in self.P.starts(u["level"], L["ln"])}:
            return f"{self.when(s, L['ln'])} is not lesson time for {u['level']}: it is a break, after the day ends, or the {L['ln']} periods would run across a break."
        names = sorted({r["rule"] for r in self.P.spec.get("rules", []) if r.get("rule") in ("Not available", "Not in periods", "Only in periods", "Finish by", "Fixed at", "Keep free together")
                        and u["id"] in {x["id"] for x in units_for(self.P, r)}})
        return f"A rule keeps {self.name(k)} out of that time" + (f" ({', '.join(names)})." if names else ".")

    def conflicts(self, moves):
        """what goes wrong if these lessons move ({key: start}, applied together): [dict(text, keys)]"""
        P, NP = self.P, self.NP
        start = lambda k: moves.get(k, self.L[k]["start"])
        cover = lambda k: range(start(k), start(k) + self.L[k]["ln"])
        def at(q): return {k for k in self.at.get(q, ()) if k not in moves} | {k for k in moves if q in cover(k)}
        out = []; seen = set()
        def add(text, keys=()):
            if text not in seen: seen.add(text); out.append(dict(text=text, keys=sorted(keys)))
        for k in moves:
            L = self.L[k]; u = L["unit"]; s = start(k); d = s // NP; nm = self.name(k)
            if s not in self.dom[k]["vals"]: add(self.why_not(k, s))
            others = {b for q in cover(k) for b in at(q)} - {k}
            for b in sorted(others, key=lambda b: start(b)):
                B = self.L[b]; ub = B["unit"]; when = self.when(start(b), B["ln"])
                for t in sorted(self.tset[k] & self.tset[b]): add(f"{t} already teaches {self.name(b)} then ({when}).", [b])
                if u["kind"] == "class" and u["classes"][0] in ub["classes"]: add(f"{u['classes'][0]} already has {self.name(b)} then ({when}).", [b])
                elif ub["kind"] == "class" and ub["classes"][0] in u["classes"]: add(f"{ub['classes'][0]} already has {self.name(b)} then ({when}).", [b])
                elif self.member[k] & self.member[b]:
                    n = len(self.stu[u["id"]] & self.stu[ub["id"]]); cls = sorted({c for c, _ in self.member[k] & self.member[b]})
                    add((f"{n} students" if n else "Students") + f" in {', '.join(cls)} take both {nm} and {self.name(b)} ({when}).", [b])
            for t in sorted(self.tset[k]):
                why = next((self.busy[t][q] for q in cover(k) if q in self.busy.get(t, {})), None)
                if why: add(f"{t} is not available then ({why}).")
            for kind, n in self.kinds[k].items():
                capk = self.kind_cap.get(kind, 0)
                if capk and any(sum(min(self.kinds[b].get(kind, 0), capk) for b in at(q)) > capk for q in cover(k)):
                    add(f"No free {kind} then: all {capk} are in use.")
            # a group's lessons spread over the cycle: at most one a day under 'Once a day per group', and never bunched
            # when it has more lessons than days (as the solver does)
            ks = self.by_unit[u["id"]]; on_day = sum(1 for b in ks if start(b) // NP == d)
            if len(ks) > P.ND and on_day > math.ceil(len(ks) / P.ND): add(f"That puts {on_day} {nm} lessons on {P.days[d]}, more than its lessons need.")
            elif 1 < len(ks) <= P.ND and on_day > 1 and self.once: add(f"That puts two {nm} lessons on {P.days[d]} (rule: once a day per group).")
            for r in self.rules:
                nm_r = r.get("rule")
                if nm_r == "At most N at once" and r.get("scope") in ("Subject", "Department") and r.get("number"):
                    field = "subject" if r["scope"] == "Subject" else "dept"
                    if any(x.get(field) == r["target"] for x in L["part"]):
                        n = int(r["number"])
                        if any(sum(sum(1 for x in self.L[b]["part"] if x.get(field) == r["target"]) for b in at(q)) > n for q in cover(k)):
                            add(f"More than {n} {r['target']} lessons at once then (rule: at most {n} at once).")
                elif nm_r == "Max periods a day" and r.get("number"):
                    n = int(r["number"]); sc_ = r.get("scope")
                    if sc_ in ("Teacher", "School"):
                        for t in self.tset[k]:
                            if sc_ == "Teacher" and t != r["target"]: continue
                            tot = sum(self.L[b]["ln"] for b in self.L if t in self.tset[b] and start(b) // NP == d)
                            if tot > n: add(f"{t} would teach {tot} periods on {P.days[d]} (rule: at most {n} a day).")
                    else:
                        for c in u["classes"]:
                            if (sc_ == "Class" and c != r["target"]) or (sc_ == "Level" and P.level_of.get(c) != r["target"]): continue
                            tot = sum(self.L[b]["ln"] for b in self.L if c in self.L[b]["unit"]["classes"] and start(b) // NP == d)
                            if tot > n: add(f"{c} would have {tot} periods on {P.days[d]} (rule: at most {n} a day).")
                elif nm_r == "Same time across classes" and u["kind"] == "class" and P.level_of.get(u["classes"][0]) == r["target"] and u["rows"][0]["subject"] == r.get("subject"):
                    add(f"Every {r['target']} class has {r.get('subject')} at the same time (rule), so this lesson cannot move on its own.")
                elif nm_r == "Not on the same day as":
                    for c in u["classes"]:
                        mine = {x["subject"] for x in L["part"]}
                        for a, z in ((r["target"], r.get("subject")), (r.get("subject"), r["target"])):
                            if a in mine and any(c in self.L[b]["unit"]["classes"] and start(b) // NP == d and any(x["subject"] == z for x in self.L[b]["part"]) for b in self.L if b != k):
                                add(f"{c} would have {a} and {z} on the same day (rule: not on the same day).")
                elif nm_r == "Fixed at" and str(r.get("day") or "All") != "All" and r.get("from") not in (None, "") and u["id"] in {x["id"] for x in units_for(P, r)}:
                    _, days = P.rule_positions(r)
                    for dd in days:
                        pos = dd * NP + int(r["from"])
                        if not any(start(b) == pos for b in self.by_unit[u["id"]]):
                            add(f"A rule fixes {u['name']} at {self.when(pos, L['ln'])} (Fixed lessons, step 7).")
        return out

    def twins(self, k):
        """the lessons of k's group that are interchangeable with it (same length and rows), in the solver's order"""
        L = self.L[k]; sig = (L["ln"], tuple(id(x) for x in L["part"]))
        return sorted((b for b in self.by_unit[L["unit"]["id"]] if (self.L[b]["ln"], tuple(id(x) for x in self.L[b]["part"])) == sig), key=lambda b: self.L[b]["i"])

    def ordered(self, moves):
        """the same moves with interchangeable lessons kept in time order (the solver numbers them that way, so a
        lesson moved past its twin swaps labels with it): {key: start} for every lesson whose start changes"""
        out = dict(moves)
        for k in moves:
            g = self.twins(k); starts = sorted(out.get(b, self.L[b]["start"]) for b in g)
            out.update(zip(g, starts))
        return {k: s for k, s in out.items() if s != self.L[k]["start"]}

    def rekey(self, pins, moves):
        """pins {key: start} after `moves`: a pin stays on its time, whichever twin now sits there"""
        new = dict(pins); start = lambda k: moves.get(k, self.L[k]["start"])
        for g in {tuple(self.twins(k)) for k in moves}:
            held = {new.pop(x) for x in g if x in new}
            new.update({x: start(x) for x in g if start(x) in held})
        return new

    def step(self, k, d):
        """the nearest allowed start before (d < 0) or after (d > 0) the lesson's start: same day first, then the next days"""
        s = self.L[k]["start"]; vals = sorted(self.dom[k]["vals"])
        later = [v for v in vals if (v > s if d > 0 else v < s)]
        return (min(later) if d > 0 else max(later)) if later else None

    def related(self, a, b):
        A, B = self.L[a]["unit"], self.L[b]["unit"]
        return bool(self.tset[a] & self.tset[b] or set(A["classes"]) & set(B["classes"]))

    def free_times(self, k, near=None, limit=8):
        """times this lesson could move to without any clash, nearest to `near` first"""
        L = self.L[k]; ref = L["start"] if near is None else near
        ok = [s for s in self.dom[k]["vals"] if s != L["start"] and not self.conflicts({k: s})]
        ok.sort(key=lambda s: (s // self.NP != ref // self.NP, abs(s - ref)))
        return ok[:limit]

    def swaps(self, k, target, limit=4):
        """lessons at the wanted time it could swap with cleanly (same length, sharing a teacher or class)"""
        A = self.L[k]; out = []
        for b in sorted({b for q in range(target, target + A["ln"]) for b in self.at.get(q, ())} - set(self.twins(k))):   # a twin swap changes nothing
            B = self.L[b]
            if B["ln"] != A["ln"] or not self.related(k, b): continue
            if not self.conflicts({k: B["start"], b: A["start"]}): out.append(b)
        return out[:limit]

    # ---- the result, in the form the report and export code take
    def res(self):
        NP, P = self.NP, self.P
        ls = [dict(L, ext=any(P.grid[L["unit"]["level"]][L["start"] // NP][L["start"] % NP + q] == "A" for q in range(L["ln"]))) for L in self.L.values()]
        return dict(status="FEASIBLE", problem=P, lessons=ls, notes=[])

    def placements(self):
        return {k: L["start"] for k, L in self.L.items()}


# ------------------------------------------------------------------------------------------- per run
def _paths(run):
    s = run.solved
    return s["placements"], os.path.join(run.dir, f"solve{s['n']}_edits.json")

def edits(run):
    """the hand changes to the run's latest timetable: history (for undo), redo and pins {key: start}"""
    _, ep = _paths(run)
    e = read_json(ep) or {}
    return dict(history=e.get("history", []), redo=e.get("redo", []), pins=e.get("pins", {}))

def pins(run):
    return edits(run)["pins"] if run.solved else {}

def board(run):
    s = run.solved
    with _lock:
        key = (run.id, s["n"])
        b = _boards.get(key)
        if b is None:
            spec = read_json(s["spec"]) if s.get("spec") and os.path.exists(s["spec"]) else _spec_from_setup(s["setup"])
            b = Board(spec, read_json(s["placements"])); _boards.clear(); _boards[key] = b
        return b

def _spec_from_setup(path):
    """runs solved before the setup was kept as JSON: read their setup workbook"""
    from ttgen.reader import read_template, derive
    spec = read_template(path); spec = spec[0] if isinstance(spec, tuple) else spec
    derive(spec); return spec

def state(run):
    """everything the Adjust page draws: the days and periods, each level's day, and every lesson with its rooms"""
    b = board(run); P, NP = b.P, b.NP; e = edits(run)
    res = b.res(); assign_rooms(res)
    lessons = []
    for L in sorted(res["lessons"], key=lambda L: L["start"]):
        rows = [dict(subject=r["subject"], code=r["code"] if r["code"] != "Entire Class" else "", teachers=r["teachers"], room=L["rooms"].get(id(r), ""), students=r.get("students")) for r in L["part"]]
        lessons.append(dict(key=L["key"], start=L["start"], ln=L["ln"], name=b.name(L["key"]), kind=L["unit"]["kind"], level=L["unit"]["level"],
                            classes=L["unit"]["classes"], teachers=sorted(b.tset[L["key"]]), rows=rows, pinned=L["key"] in e["pins"]))
    s = run.solved
    return dict(n=s["n"], days=P.days, NP=NP, clock=[clock(b.sc, p) for p in range(NP + 1)], grid={lv: rows for lv, rows in P.grid.items()},
                classes=sorted(P.level_of), teachers=sorted({t for ts in b.tset.values() for t in ts}), rooms=sorted({v["room"] for v in P.spec["venues"]}),
                level_of=P.level_of, lessons=lessons, moves=len(e["history"]), can_undo=bool(e["history"]), can_redo=bool(e["redo"]),
                last=e["history"][-1]["label"] if e["history"] else "", busy=run.busy,
                summary=dict(ok=s.get("ok"), problems=s.get("problems", []), after=s.get("after", []), lessons=s.get("lessons"), stale=bool(s.get("stale"))))

def proposal(run, key, start):
    """a move the committee asks for: what it clashes with and the ways out"""
    b = board(run); L = b.L[key]
    con = b.conflicts({key: start})
    sw = b.swaps(key, start) if con else []
    free = b.free_times(key, near=start) if con else []
    return dict(key=key, start=start, name=b.name(key), from_=b.when(L["start"], L["ln"]), to=b.when(start, L["ln"]), conflicts=con, ok=not con,
                allowed=start in b.dom[key]["vals"],
                swaps=[dict(key=x, start=b.L[x]["start"], label=f"Swap with {b.name(x)} ({b.when(b.L[x]['start'], b.L[x]['ln'])})") for x in sw],
                free=[dict(start=s, label=b.when(s, L["ln"])) for s in free])

def apply(run, moves, label, pin=None):
    """move lessons ({key: start}), keep the change for undo, pin the lessons the committee placed (`pin`: keys of
    `moves`, default all of them), and update the checks"""
    with _lock:
        b = board(run); e = edits(run)
        full = b.ordered(moves)
        if not full: return
        pins_before = dict(e["pins"]); pins = b.rekey(e["pins"], full)
        for k in (moves if pin is None else pin):   # pin whichever twin now sits at the time asked for
            pins.update({x: moves[k] for x in b.twins(k) if full.get(x, b.L[x]["start"]) == moves[k]})
        before = {k: b.L[k]["start"] for k in full}
        for k, s in full.items(): b.L[k]["start"] = s
        b.index(); e["pins"] = pins
        e["history"].append(dict(label=label, before=before, after=full, pins_before=pins_before, pins_after=dict(pins), at=now())); e["redo"] = []
        _save(run, b, e)
    run.emit("adjusted", text=label)

def undo(run, back=True):
    with _lock:
        b = board(run); e = edits(run)
        src, dst = (e["history"], e["redo"]) if back else (e["redo"], e["history"])
        if not src: return None
        h = src.pop(); dst.append(h)
        for k, s in (h["before"] if back else h["after"]).items(): b.L[k]["start"] = s
        e["pins"] = dict(h["pins_before"] if back else h["pins_after"])
        b.index(); _save(run, b, e)
    run.emit("adjusted", text=("Undone: " if back else "Redone: ") + h["label"])
    return h

def unpin(run, key):
    with _lock:
        e = edits(run)
        if e["pins"].pop(key, None) is None: return
        b = board(run); _save(run, b, e)

def _save(run, b, e):
    pp, ep = _paths(run)
    write_json(pp, b.placements()); write_json(ep, e)
    res = b.res(); assign_rooms(res); probs, stats, post = check(res)
    s = run.solved
    s.update(ok=not probs, problems=probs[:12], lessons=stats["lessons"], edited=len(e["history"]), stale=True,
             after=[f"{b.name(L['key'])}: {b.when(L['start'], L['ln'])}" for L in res["lessons"] if L["ext"]])
    run.save()

def flush(run):
    """rewrite the timetable workbook after hand changes (Preview and Publish read it)"""
    from timetabler import _summary
    from ttgen.report import write_timetable
    with _lock:
        s = run.solved
        if not s or not s.get("stale"): return
        b = board(run)
        _, _, _, m = write_timetable(b.res(), s["timetable"], return_model=True)
        keep = {k: s[k] for k in ("n", "at", "setup", "timetable", "placements", "spec", "seconds", "edited") if k in s}
        s.update(_summary(s.get("status", "FEASIBLE"), m)); s.update(keep); s["stale"] = False
        run.save()

def carry_pins(run, old, res):
    """after a new solve in the same run: keep the pins its lessons still sit on"""
    if not old: return
    now_at = {L["key"]: L["start"] for L in res["lessons"]}
    kept = {k: s for k, s in old.items() if now_at.get(k) == s}
    _, ep = _paths(run); write_json(ep, dict(history=[], redo=[], pins=kept))

def make_room(run, key, start, seconds, workers=8):
    """the solver keeps `key` at `start` (and every pinned lesson where it is) and moves as few other lessons as it
    can; runs in the run's thread. The result is one change in the history, so Undo puts everything back."""
    from ttgen.solver import solve
    b = board(run); e = edits(run); nm, when = b.name(key), b.when(start, b.L[key]["ln"])
    full = b.ordered({key: start}); pinned = b.rekey(e["pins"], full)
    at_time = [x for x in b.twins(key) if full.get(x, b.L[x]["start"]) == start]
    pinned.update({x: start for x in at_time})
    current = b.placements(); previous = dict(current, **full)   # the solver starts from the move and repairs around it
    run.emit("tool", text=f"Making room for {nm} at {when}: the solver keeps it there and moves as few other lessons as it can (up to {seconds // 60 or 1} min)...")
    run.progress = f"Making room for {nm}..."
    res = solve(copy.deepcopy(b.spec), time_limit=seconds, workers=workers, log=lambda *a: None, stop=run.stop, previous=previous, pins=pinned)
    run.progress = ""
    if not res["lessons"]:
        run.emit("nosolution", text=f"The solver could not make room for {nm} at {when} in {seconds // 60 or 1} min.",
                 items=[], data=dict(status=res["status"], fixes=[dict(go="adjust", text="Try another time or a swap; or give the solver longer (Solve for up to, on Generate & publish) and try again; or ask the AI for other ways, such as merging or splitting a group.")]))
        return
    new = {L["key"]: L["start"] for L in res["lessons"]}
    changes = {k: s for k, s in new.items() if current.get(k) != s}
    mine = [x for x in b.twins(key) if new.get(x) == start]
    others = [k for k in changes if k not in mine and k not in full]
    apply(run, changes, f"Moved {nm} to {when}; the solver moved {len(others)} other lesson{'s' if len(others) != 1 else ''} to make room", pin=[x for x in mine if x in changes])
    run.emit("moved", text=f"Made room for {nm} at {when}: {len(others)} other lessons moved.",
             items=[f"{b.name(k)}: {b.when(current[k], b.L[k]['ln'])} -> {b.when(changes[k], b.L[k]['ln'])}" for k in others][:40])

def _pattern(r):
    """a lesson row's lesson lengths, longest first (Problem's counts for it)"""
    return sorted((ln for ln, n in r["_counts"].items() for _ in range(n)), reverse=True)

def _same_row(a, b):
    return all(a.get(f) == b.get(f) for f in ("level", "subject", "block", "classes", "code_override", "teachers"))

def resize(run, key, delta):
    """make one lesson a period shorter (delta -1) or longer (+1) where it is. That changes the plan (its group gets a
    period fewer or more a cycle), so it is made in this timetable's setup and the run's: later solves keep it. A
    whole-class row shared by several classes is split so only this class changes. The result is a new latest
    timetable with every other lesson where it was. Returns a sentence saying what changed."""
    from ttgen.reader import derive
    from ttgen.template import write_template
    with _lock:
        b = board(run); L = b.L[key]; u = L["unit"]; ln = L["ln"] + delta; nm, when = b.name(key), b.when(L["start"], L["ln"])
        if ln < 1: raise ValueError(f"{nm} is already one period long.")
        spec2 = copy.deepcopy(b.spec); idx = {id(x): i for i, x in enumerate(b.P.spec["lessons"])}
        changed = []
        for r in sorted(L["part"], key=lambda r: -idx[id(r)]):   # from the bottom, so inserted rows do not shift the others
            j = idx[id(r)]; row = spec2["lessons"][j]; pat = _pattern(r); pat.remove(L["ln"]); pat = sorted(pat + [ln], reverse=True)
            if u["kind"] == "class" and len(row["classes"]) > 1:   # only this class's lesson changes
                c = u["classes"][0]; new = copy.deepcopy(row); new["classes"] = [c]; row["classes"] = [x for x in row["classes"] if x != c]
                spec2["lessons"].insert(j + 1, new); row = new
            row["pattern"] = pat; row["periods_override"] = sum(pat)
            changed.append((row, r["periods"], sum(pat)))
        derive(spec2)
        # every lesson keeps its time. Other groups' lessons keep their keys; in the changed group, lessons with the same
        # length and the same rows are interchangeable and numbered in time order (as the solver does)
        P2 = Problem(copy.deepcopy(spec2)); place = {}
        sig = lambda unit, rows: tuple(sorted((r["subject"], r.get("code"), tuple(sorted(set(r["classes"]) & set(unit["classes"])))) for r in rows))
        refuse = ValueError(f"{nm} cannot change length on its own: its groups would then share a lesson they do not share now. Change the periods on step 6 instead.")
        for u2 in P2.units:
            if u2["key"] != u["key"]:
                for n, i in u2["lessons"]:
                    k = f"{u2['key']}|{n}|{i}"
                    if k not in b.L: raise refuse
                    place[k] = b.L[k]["start"]
                continue
            got, need = collections.defaultdict(list), collections.defaultdict(list)
            for k, x in b.L.items():
                if x["unit"]["key"] == u["key"]: got[(ln if k == key else x["ln"], sig(u, x["part"]))].append(x["start"])
            for n, i in u2["lessons"]:
                need[(n, sig(u2, [x for x in u2["rows"] if x["_counts"].get(n, 0) > i]))].append(f"{u2['key']}|{n}|{i}")
            if {s_: len(v) for s_, v in got.items()} != {s_: len(v) for s_, v in need.items()}: raise refuse
            for s_, keys in need.items(): place.update(zip(keys, sorted(got[s_])))
        if len(place) != len(b.L): raise refuse
        b2 = Board(spec2, place)
        key2 = next(k for k, x in b2.L.items() if x["unit"]["key"] == u["key"] and x["ln"] == ln and x["start"] == L["start"])
        con = b2.conflicts({key2: L["start"]})
        if con: raise ValueError(f"{nm} cannot be {ln} periods long at {when}: " + " ".join(c["text"] for c in con[:3]) + " Move it first, or move what is in the way.")
        # a new latest timetable for the run: this setup, these placements; pins follow their lessons
        e = edits(run); pins = {}
        for k, s in e["pins"].items():
            uk = k.rsplit("|", 2)[0]; k2 = next((x for x, st in place.items() if st == s and x.rsplit("|", 2)[0] == uk), None)
            if k2: pins[k2] = s
        pins[key2] = L["start"]
        n = run.solves + 1; run.solves = n; d = run.dir
        paths = dict(spec=os.path.join(d, f"solve{n}_spec.json"), placements=os.path.join(d, f"solve{n}_placements.json"),
                     setup=os.path.join(d, f"solve{n}_setup.xlsx"), timetable=os.path.join(d, f"solve{n}_timetable.xlsx"))
        write_json(paths["spec"], spec2); write_json(paths["placements"], place); write_template(copy.deepcopy(spec2), paths["setup"])
        s = dict(run.solved); s.update(paths, n=n, at=now(), edited=0); run.solved = s
        write_json(os.path.join(d, f"solve{n}_edits.json"), dict(history=[], redo=[], pins=pins))
        _boards.clear(); _boards[(run.id, n)] = b2
        # the run's own setup gets the same change, so solves from here on keep it
        for row, was, now_p in changed:
            for j, x in enumerate(run.spec["lessons"]):
                same = dict(row, classes=x["classes"]) if row["classes"] != x["classes"] and set(row["classes"]) <= set(x["classes"]) else row
                if not _same_row(x, same): continue
                if row["classes"] != x["classes"]:
                    x["classes"] = [c for c in x["classes"] if c not in row["classes"]]; run.spec["lessons"].insert(j + 1, copy.deepcopy(row))
                else: x["pattern"], x["periods_override"] = row["pattern"], row["periods_override"]
                break
        derive(run.spec)
        what = f"{nm} at {when} is now {ln} period{'s' if ln != 1 else ''} long"
        detail = [f"{r['subject']} {r['code'] if r['code'] != 'Entire Class' else ', '.join(r['classes'])}: {now_p} periods a cycle (was {was})" for r, was, now_p in changed]
        run.changes.append(dict(at=now(), text=f"{what}: " + "; ".join(detail), reason="Changed by hand on the Adjust page"))
        _save(run, b2, edits(run))
    run.emit("change", text=f"{what}.", items=detail)
    return f"{what}. " + "; ".join(detail) + "."

def ai_question(run, key, start):
    """the move and its clashes, for the AI to suggest ways out"""
    b = board(run); p = proposal(run, key, start); L = b.L[key]
    rows = "; ".join(f"{r['subject']} {r['code']} ({r.get('students') or '?'} students, {', '.join(r['teachers']) or 'no teacher'})" for r in L["part"])
    lines = [f"The committee wants to move {p['name']} from {p['from_']} to {p['to']}.", f"It is: {rows}; classes {', '.join(L['unit']['classes'])}.",
             "It clashes with:"] + [f"- {c['text']}" for c in p["conflicts"]]
    clash = sorted({k for c in p["conflicts"] for k in c["keys"]})
    if clash:
        lines.append("The clashing lessons:")
        for k in clash[:8]:
            lines.append(f"- {b.name(k)}: " + "; ".join(f"{r['subject']} {r['code']} ({r.get('students') or '?'} students, {', '.join(r['teachers'])})" for r in b.L[k]["part"]))
    if p["free"]: lines.append("Free times for it: " + ", ".join(f["label"] for f in p["free"]))
    if p["swaps"]: lines.append("Clean swaps: " + "; ".join(s["label"] for s in p["swaps"]))
    same = [u for u in b.P.units if u["id"] != L["unit"]["id"] and any(r["subject"] == L["part"][0]["subject"] for r in u["rows"]) and u["level"] == L["unit"]["level"]]
    if same: lines.append("Other groups of the same subject and level: " + "; ".join(f"{r['code']} {', '.join(r['teachers'])} ({r.get('students') or '?'} students)" for u in same[:8] for r in u["rows"] if r["subject"] == L["part"][0]["subject"]))
    return "\n".join(lines)

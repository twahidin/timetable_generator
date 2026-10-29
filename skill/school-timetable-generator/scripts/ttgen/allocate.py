"""Teacher allocation: a teacher for every lesson row the committee left without one (Teacher 1 blank). Rows that name a
teacher, co-taught rows included, are never changed.

A row may go to a teacher set to teach its subject at its level (Teachers: can_teach, 'All', the level or its band of
levels). A teacher takes at most one group of a band (its groups meet at the same time). Each teacher's load is their
lessons (a whole-class row counts once per class; a band or group row once) plus other duties; the model first keeps
every load within its allowance, then makes the highest share of allowance as low as it can (spreading the work), and
last keeps a class with the teachers it already has. CP-SAT, a few seconds."""
import collections
from ortools.sat.python import cp_model
from .reader import derive

def row_load(x):
    """periods a cycle this row gives each of its teachers"""
    return int(x.get("periods") or 0) * (1 if x.get("block") or x.get("code_override") else max(1, len(x.get("classes") or [])))

def can_teach(t, subject, level, bands):
    return any(c.get("subject") == subject and (not c.get("levels") or c["levels"] in ("All", level, bands.get(level)))
               for c in t.get("can_teach") or [])

def allocate(spec, time_limit=20, workers=8):
    """dict(assign={row index: teacher}, unfilled=[(row index, why)], loads={teacher: (before, after, allowance)})"""
    derive(spec)
    sc = spec["school"]; bands = {str(k): v for k, v in (sc.get("bands") or {}).items()}
    T = [t for t in spec["teachers"] if t.get("name")]
    rows = spec["lessons"]
    blank = [i for i, x in enumerate(rows) if not [t for t in x.get("teachers") or [] if t] and x.get("subject")]
    fixed = collections.Counter({t["name"]: int(t.get("other_duties") or 0) for t in T})
    in_band = collections.defaultdict(set)      # band -> teachers already in it
    of_class = collections.defaultdict(set)     # class -> teachers it already has
    for x in rows:
        for t in [t for t in x.get("teachers") or [] if t]:
            fixed[t] += row_load(x)
            if x.get("block"): in_band[x["block"]].add(t)
            for c in x.get("classes") or []: of_class[c].add(t)
    unfilled, choose = [], {}
    for i in blank:
        x = rows[i]
        ok = [t["name"] for t in T if can_teach(t, x["subject"], x.get("level"), bands) and t["name"] not in in_band.get(x.get("block"), ())]
        if ok: choose[i] = ok
        else: unfilled.append((i, f"no teacher is set to teach {x['subject']} at {x.get('level')}" + (f" outside band {x['block']}" if x.get("block") else "") + " (step 4, Teachers)"))
    def num(v):
        try: n = int(float(str(v))); return n if n > 0 else None
        except (TypeError, ValueError): return None
    allow = {t["name"]: num(t.get("allowance")) for t in T}
    out = dict(assign={}, unfilled=unfilled, loads={})
    if choose:
        m = cp_model.CpModel(); x_ = {(i, t): m.NewBoolVar("") for i, ts in choose.items() for t in ts}
        for i, ts in choose.items(): m.AddExactlyOne(x_[i, t] for t in ts)
        by_band = collections.defaultdict(list)
        for i in choose:
            if rows[i].get("block"): by_band[rows[i]["block"]].append(i)
        for _, idx in by_band.items():   # one group of a band per teacher
            for t in {t for i in idx for t in choose[i]}: m.Add(sum(x_[i, t] for i in idx if (i, t) in x_) <= 1)
        cand = {t for ts in choose.values() for t in ts}
        load = {t: fixed[t] + sum(row_load(rows[i]) * x_[i, t] for i in choose if (i, t) in x_) for t in cand}
        big = sum(row_load(rows[i]) for i in choose) + max(fixed.values(), default=0) + 1
        over, share = [], m.NewIntVar(0, 1000 * big, "share")
        for t in cand:
            if allow.get(t):
                o = m.NewIntVar(0, big, ""); m.Add(o >= load[t] - allow[t]); over.append(o)
                m.Add(1000 * load[t] <= share * allow[t])
        new_teacher = [x_[i, t] for i in choose for t in choose[i] if not all(t in of_class[c] for c in rows[i].get("classes") or [])]
        m.Minimize(1000 * big * sum(over) + 10 * share + sum(new_teacher))
        s = cp_model.CpSolver(); s.parameters.max_time_in_seconds = time_limit; s.parameters.num_workers = workers
        if s.Solve(m) in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            out["assign"] = {i: next(t for t in choose[i] if s.Value(x_[i, t])) for i in choose}
        else:
            out["unfilled"] += [(i, "no allocation found in time") for i in choose]
    after = collections.Counter(fixed)
    for i, t in out["assign"].items(): after[t] += row_load(rows[i])
    out["loads"] = {t: (fixed[t], after[t], allow.get(t)) for t in sorted({t for t in out["assign"].values()})}
    return out

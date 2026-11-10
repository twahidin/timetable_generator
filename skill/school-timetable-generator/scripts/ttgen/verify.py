"""Check a timetable made by an outside agent against the school's setup: every difference is a warning
(dict key, kind, text, strength, group, where, sides, ops). Periods are 0-based; day names are the setup's.
Every function that takes spec takes the checked setup (m["checked_setup"]), already derived."""
import re
from collections import Counter
from .export import ENTIRE
from .solver import rule_label
from .spec import floating_recess, names_list, subject_test, typed_rules

KINDS = ("clash", "deployment", "rule", "typed", "choice")
APPEND = "(end)"   # an add op's "after": not a row id, so sync.apply puts the row last ("" would put it first and renumber the group codes after it)

def warning(key, kind, text, strength="Must", group="School", where=None, sides=None, ops=None):
    """one warning in the shape the draft page lists"""
    return dict(key=key, kind=kind, text=text, strength=strength, group=group, where=where, sides=sides, ops=ops)


# ----------------------------------------------------------------------------------------------- what step 5 plans, what the timetable placed
def _name(key): return f"{key[2]} for {key[1]}" if key[0] == "C" else f"group {key[1]}"
def _kstr(key): return ":".join(key)

def planned_rows(spec):
    """key -> what step 5 plans: ("C", class, subject) for an entire-class row (one per class), ("G", code) for a group row"""
    out = {}
    for x in spec["lessons"]:
        if not x.get("periods") or not x.get("classes"): continue
        whole = x.get("code") == ENTIRE
        for c in (x["classes"] if whole else [None]):
            key = ("C", c, x["subject"]) if whole else ("G", x["code"])
            e = out.setdefault(key, dict(rows=[], teachers=set(), periods=0, room_kind=None, room_weeks=None, classes=[c] if whole else list(x["classes"]), level=x.get("level"), subject=x["subject"]))
            e["rows"].append(x); e["teachers"] |= set(x.get("teachers") or [])
            e["periods"] = e["periods"] + int(x["periods"]) if whole else int(x["periods"])   # as _model: entire-class rows add up, a group's code is one lesson
            e["room_kind"] = e["room_kind"] or x.get("room_kind"); e["room_weeks"] = e["room_weeks"] or x.get("room_weeks")
    return out

def placed(m):
    """key -> what the timetable placed (same keys); a lesson id counts once per key"""
    out, seen = {}, set()
    def add(key, x):
        e = out.setdefault(key, dict(lessons=[], teachers=set(), periods=0, rooms=set()))
        e["lessons"].append(x); e["teachers"] |= set(x["teachers"])
        if x["room"]: e["rooms"].add(x["room"])
        if (x["id"], key) not in seen: seen.add((x["id"], key)); e["periods"] += x["n"]
    for x in m["lessons"]:
        if x["group"] == ENTIRE:
            for c in x["classes"]: add(("C", c, x["subject"]), x)
        else: add(("G", x["group"]), x)
    return out


# ----------------------------------------------------------------------------------------------- the comparison
def _ids(rows):
    """the ids of rows an op may act on; none when a row covers more than one class (the op would reach the others too)"""
    return [] if any(len(x["classes"]) > 1 for x in rows) else [x["_id"] for x in rows if x.get("_id")]

def _del_ids(rows):
    """the ids of rows a del may remove: as _ids, and none when a row is a block row with an automatic group code (the
    codes are numbered in row order, so removing one would rename the groups after it)"""
    return [] if any(x.get("block") and not x.get("code_override") for x in rows) else _ids(rows)

def _other_week(day, weeks):
    """whether the day is in the other week of a row whose special room is on `weeks` only (Odd or Even)"""
    return weeks in ("Odd", "Even") and str(day).split()[0] in ("Odd", "Even") and not str(day).startswith(weeks)

def deployment(m, spec):
    """one warning per difference between the timetable and step 5 (teachers, periods, venue kind, missing, extra)"""
    plan, got, out = planned_rows(spec), placed(m), []
    subjects = {str(s["subject"]) for s in spec["subjects"]}
    def where(key, e):
        x = e["lessons"][0]; return dict(cls=key[1] if key[0] == "C" else (x["classes"] or [""])[0], day=m["days"][x["d"]], period=x["p"], id=x["id"], row=x["group"])
    for key in plan:
        p, k, what = plan[key], _kstr(key), _name(key); group = p["classes"][0] if p["classes"] else "School"
        if key not in got:
            ids = _del_ids(p["rows"])
            out.append(warning(f"dep:{k}:missing", "deployment", f"{what} is on step 5 but not on the timetable.", group=group, ops=[["del", "lessons", i] for i in ids] or None))
            continue
        g = got[key]; w = where(key, g)
        if g["teachers"] != p["teachers"]:
            a, b = ", ".join(sorted(g["teachers"])), ", ".join(sorted(p["teachers"])); ids = _ids(p["rows"])
            out.append(warning(f"dep:{k}:teachers", "deployment", f"{what} is taught by {a} on the timetable; step 5 says {b}.", group=group, where=w,
                               sides=dict(timetable=a, step5=b), ops=[["set", "lessons", i, "teachers", sorted(g["teachers"])] for i in ids] or None))
        if g["periods"] != p["periods"]:
            out.append(warning(f"dep:{k}:periods", "deployment", f"{what}: {g['periods']} periods timetabled, {p['periods']} on step 3.", group=group, where=w,
                               sides=dict(timetable=str(g["periods"]), step5=str(p["periods"]))))
        if p["room_kind"]:
            for x in g["lessons"]:
                kind = m["room_ix"].get(x["room"], {}).get("kind") if x["room"] and x["room"] != "TBC" else None
                if kind == "classroom" and _other_week(m["days"][x["d"]], p["room_weeks"]): continue   # as the solver: a classroom on its other week
                if kind and kind != p["room_kind"]:
                    out.append(warning(f"dep:{k}:venue", "deployment", f"{what} is in {x['room']} ({kind}); step 3 asks for {p['room_kind']}.", group=group, where=w)); break
    class_level = {str(c["class"]): str(c.get("level") or "") for c in spec["classes"]}
    for key, g in got.items():
        if key in plan: continue
        k, x = _kstr(key), g["lessons"][0]
        classes = [key[1]] if key[0] == "C" else list(x["classes"])
        level = x["level"] or next((class_level[c] for c in classes if class_level.get(c)), "")   # a workbook without a Level column: the class's level
        row = dict(level=level, subject=x["subject"], classes=classes, teachers=sorted(g["teachers"]))
        if key[0] == "G": row.update(code_override=key[1], **({"block": x["block"]} if x["block"] else {}))   # an entire-class row has no block (it would get a group code)
        ops = [["add", "lessons", row, APPEND]] if x["subject"] in subjects else None   # the row's _id is given when it is applied (draft.decide)
        out.append(warning(f"dep:{k}:extra", "deployment", f"{_name(key)} is on the timetable but not on step 5.", group=classes[0] if classes else "School", where=where(key, g), ops=ops))
    return out

def clashes(m):
    """the independent checks' problems as warnings, without the period-count lines (the comparison owns those)"""
    out, own = [], set(m.get("choice_problems") or ())   # the second-choice sentences are listed as choice warnings
    for text in m["checks"]["problems"]:
        if text.endswith("planned.") or text in own: continue
        who = re.match(r"(?:Teacher double-booked|Class clash): (.+?) on ", text)
        out.append(warning("clash:" + text, "clash", text, group=who.group(1) if who else "School"))
    return out


# ----------------------------------------------------------------------------------------------- the standard rules
def rule_days(days, r):
    """the day indexes a rule row covers (as the solver's _day_ok): Odd/Even by prefix, the day by its first three letters"""
    wk, dy = str(r.get("week") or "Both"), str(r.get("day") or "All")
    return [i for i, d in enumerate(days) if not (wk in ("Odd", "Even") and not d.startswith(wk)) and (dy == "All" or d.split()[-1][:3] == dy[:3])]

def rule_periods(r, NP):
    """the periods a rule row covers: blank From is 0, blank To is the last period"""
    a, b = r.get("from"), r.get("to")
    return range(int(a) if a not in (None, "") else 0, (int(b) if b not in (None, "") else NP - 1) + 1)

def in_scope(m, spec, r):
    """a test for lessons the rule row is about, or None when its scope is not one the checks know"""
    sc, tg = r.get("scope"), r.get("target")
    dept = lambda x: m["subjects"].get(x["subject"], {}).get("dept")
    level = lambda c: m["class_ix"].get(c, {}).get("level")
    tests = {"Teacher": lambda x: tg in x["teachers"], "Class": lambda x: tg in x["classes"], "Room": lambda x: x["room"] == tg,
             "Level": lambda x: x["level"] == tg or (bool(x["classes"]) and all(level(c) == tg for c in x["classes"])),
             "Block": lambda x: x["block"] == tg, "Subject": lambda x: subject_test(tg)(x["subject"], dept(x)),
             "Department": lambda x: dept(x) == tg, "Group": lambda x: x["group"] == tg, "School": lambda x: True}
    if sc not in tests: return None
    base, sub = tests[sc], r.get("subject")
    if not sub or r.get("rule") == "Only these subjects": return base
    return lambda x: base(x) and subject_test(sub)(x["subject"], dept(x))


def _what(x): return f"{x['subject']} for {x['classes'][0]}" if x["group"] == ENTIRE and x["classes"] else f"group {x['group']}"
def _span(x): return range(x["p"], x["p"] + x["n"])
def _pr(per): return f"periods {per[0]}-{per[-1]}"

def _hit(m, r, i, detail, sentence, group, x=None):
    """one warning for rule row i; x is the lesson it names"""
    prefer = r.get("strength") == "Prefer"
    where = dict(cls=(x["classes"] or [""])[0], day=m["days"][x["d"]], period=x["p"], id=x["id"], row=x["group"]) if x else None
    return warning(f"rule:{r.get('_id') or i}:{detail}", "rule", f"Rule {rule_label(r)}: {sentence}" + (" (Prefer)" if prefer else ""), "Prefer" if prefer else "Must", group, where)

def _lessons(m, spec, r, days):
    """the lessons in scope that sit on a rule day"""
    test = in_scope(m, spec, r)
    return [x for x in m["lessons"] if x["d"] in days and test(x)]

def _inside(x, per): return [q for q in _span(x) if q in per]
def _key(x, q=None):
    """the key detail of a hit on lesson x: class, group code (the subject for an entire-class lesson), day, period"""
    return f"{(x['classes'] or [''])[0]}|{x['subject'] if x['group'] == ENTIRE else x['group']}|{x['d']}|{x['p'] if q is None else q}"

def _not_available(m, spec, i, r, days, per):
    out = []
    for x in _lessons(m, spec, r, days):
        if (q := next(iter(_inside(x, per)), None)) is None: continue
        who = f"for {x['classes'][0]}" if x["group"] == ENTIRE and x["classes"] else f"group {x['group']}"
        group = r["target"] if r.get("scope") in ("Teacher", "Class", "Room") else (x["classes"] or ["School"])[0]
        out.append(_hit(m, r, i, _key(x, q), f"{r['target']} has {x['subject']} {who} on {m['days'][x['d']]} period {q} but is not available ({_pr(per)}).", group, x))
    return out

def _keep_free_together(m, spec, i, r, days, per):
    out, seen = [], set()
    for x in m["lessons"]:
        if x["d"] not in days or (q := next(iter(_inside(x, per)), None)) is None: continue
        if r.get("scope") == "Department": who = [t for t in x["teachers"] if m["teacher_ix"].get(t, {}).get("dept") == r["target"]]
        else: who = [c for c in x["classes"] if m["class_ix"].get(c, {}).get("level") == r["target"]]
        for w in who:
            if (w, x["d"]) in seen: continue
            seen.add((w, x["d"]))
            out.append(_hit(m, r, i, f"{w}|{x['d']}", f"{w} has {x['subject']} on {m['days'][x['d']]} period {q}; {r['target']} keeps {_pr(per)} free together.", w, x))
    return out

def _fixed_at(m, spec, i, r, days, per):
    a = int(r["from"])
    return [_hit(m, r, i, _key(x), f"{_what(x)} starts at period {x['p']} on {m['days'][x['d']]}, not period {a}.", (x["classes"] or ["School"])[0], x)
            for x in _lessons(m, spec, r, days) if x["p"] != a]

def _not_in_periods(m, spec, i, r, days, per):
    return [_hit(m, r, i, _key(x), f"{_what(x)} is in {_pr(per)} on {m['days'][x['d']]}.", (x["classes"] or ["School"])[0], x)
            for x in _lessons(m, spec, r, days) if _inside(x, per)]

def _only_in_periods(m, spec, i, r, days, per):
    return [_hit(m, r, i, _key(x), f"{_what(x)} is outside {_pr(per)} on {m['days'][x['d']]}.", (x["classes"] or ["School"])[0], x)
            for x in _lessons(m, spec, r, days) if any(q not in per for q in _span(x))]

def _finish_by(m, spec, i, r, days, per):
    to = int(r["to"])
    return [_hit(m, r, i, _key(x), f"{_what(x)} ends at period {x['p'] + x['n'] - 1} on {m['days'][x['d']]}, after period {to}.", (x["classes"] or ["School"])[0], x)
            for x in _lessons(m, spec, r, days) if x["p"] + x["n"] - 1 > to]

def _only_these_subjects(m, spec, i, r, days, per):
    ok, names = subject_test(names_list(r["subject"])), ", ".join(names_list(r["subject"]))
    return [_hit(m, r, i, _key(x), f"{_what(x)} is in {_pr(per)} on {m['days'][x['d']]}, kept for {names}.", (x["classes"] or ["School"])[0], x)
            for x in _lessons(m, spec, r, days) if _inside(x, per) and not ok(x["subject"], m["subjects"].get(x["subject"], {}).get("dept"))]

def _only_in_venues(m, spec, i, r, days, per):
    venues, out = names_list(r.get("venues")), []
    for x in _lessons(m, spec, r, days):
        q = next(iter(_inside(x, per)), None)
        if q is None or x["room"] in ("", "TBC", None) or x["room"] in venues: continue
        out.append(_hit(m, r, i, _key(x, q), f"{_what(x)} is in {x['room']} on {m['days'][x['d']]} period {q}; only {', '.join(venues)} are allowed in {_pr(per)}.", x["room"], x))
    return out

# ----------------------------------------------------------------------------------------------- counts and patterns
def _number(r):
    """the rule's Number as a whole number, or None (2 and '2.0' are 2)"""
    try: v = float(str(r.get("number"))); return int(v) if v == int(v) else None
    except (ValueError, OverflowError): return None

def _day_name(m, d): return m["days"][d]
def _teachers_by_day(m, r, test=None):
    """(teacher, d) -> the periods that teacher is in lessons; a Teacher row looks at its target only"""
    out = {}
    for x in m["lessons"]:
        if test and not test(x): continue
        for t in x["teachers"]:
            if r.get("scope") == "Teacher" and t != r["target"]: continue
            out.setdefault((t, x["d"]), set()).update(_span(x))
    return out

def _max_periods_a_day(m, spec, i, r, days, per):
    by_teacher, tally = r.get("scope") in ("Teacher", "School"), {}
    for x in _lessons(m, spec, r, days):
        if by_teacher: who = [t for t in x["teachers"] if r["scope"] == "School" or t == r["target"]]
        else: who = [c for c in x["classes"] if r["scope"] == "Class" and c == r["target"] or r["scope"] == "Level" and m["class_ix"].get(c, {}).get("level") == r["target"]]
        for w in who: tally.setdefault((w, x["d"]), set()).update(_span(x))   # the periods occupied, so parallel groups count once
    return [_hit(m, r, i, f"{w}|{d}", f"{w} has {len(ps)} periods on {_day_name(m, d)}, more than {_number(r)}.", w)
            for (w, d), ps in sorted(tally.items(), key=lambda kv: (kv[0][1], kv[0][0])) if len(ps) > _number(r)]

def _longest_run(periods):
    best = run = 0
    for q in sorted(periods): run = run + 1 if q - 1 in periods else 1; best = max(best, run)
    return best

def _max_periods_in_a_row(m, spec, i, r, days, per):
    return [_hit(m, r, i, f"{t}|{d}", f"{t} teaches {n} periods in a row on {_day_name(m, d)}, more than {_number(r)}.", t)
            for (t, d), ps in sorted(_teachers_by_day(m, r, lambda x: x["d"] in days).items(), key=lambda kv: (kv[0][1], kv[0][0]))
            if (n := _longest_run(ps)) > _number(r)]

def _free_run(row, busy, length):
    """whether the teacher (busy periods) is free for a whole R run of the day's code string row, or length periods in a row inside a W run"""
    for run_ in re.finditer(r"R+", row):
        if not busy & set(range(run_.start(), run_.end())): return True
    for run_ in re.finditer(r"W+", row):
        a, b = run_.start(), run_.end(); need = min(length, b - a)
        if any(not busy & set(range(s, s + need)) for s in range(a, b - need + 1)): return True
    return False

def _at_least_one_recess(m, spec, i, r, days, per):
    length, out = floating_recess(spec["school"])["length"], []
    for (t, d), busy in sorted(_teachers_by_day(m, r).items(), key=lambda kv: (kv[0][1], kv[0][0])):
        if d not in days: continue
        rows = [g[d] for g in (m.get("raw_grid") or m["grid"]).values() if d < len(g)]   # the raw day: m["grid"] has its recess windows as lesson time
        if any(c in row for row in rows for c in "RW") and not any(_free_run(row, busy, length) for row in rows):
            out.append(_hit(m, r, i, f"{t}|{d}", f"{t} has no recess on {_day_name(m, d)}.", t))
    return out

def _at_most_n_at_once(m, spec, i, r, days, per):
    if r.get("scope") == "Room": return []   # check_model reports room capacity
    count = Counter((x["d"], q) for x in _lessons(m, spec, r, days) for q in _span(x) if q in per)
    return [_hit(m, r, i, f"{d}|{q}", f"{_number(r)}+ {r['target']} lessons at once on {_day_name(m, d)} period {q} ({n}).", r["target"])
            for (d, q), n in sorted(count.items()) if n > _number(r)]

def _same_time_across_classes(m, spec, i, r, days, per):
    classes, times = [c for c, v in m["class_ix"].items() if v["level"] == r["target"]], {}
    for x in _lessons(m, spec, r, days):
        for c in x["classes"]: times.setdefault(c, set()).update((x["d"], q) for q in _span(x))
    sets = {c: frozenset(times[c]) for c in classes if c in times}   # a class without the subject is the deployment comparison's to report
    if not sets: return []
    common = Counter(sets.values()).most_common(1)[0][0]
    return [_hit(m, r, i, c, f"{c} has {r['subject']} at a different time from the other {r['target']} classes.", c) for c, s in sets.items() if s != common]

def _not_on_the_same_day_as(m, spec, i, r, days, per):
    dept = lambda x: m["subjects"].get(x["subject"], {}).get("dept")
    a, b, seen = subject_test(r["target"]), subject_test(r["subject"]), {}
    for x in m["lessons"]:
        if x["d"] not in days: continue
        for c in x["classes"]:
            has = seen.setdefault((c, x["d"]), [False, False])
            has[0] |= a(x["subject"], dept(x)); has[1] |= b(x["subject"], dept(x))
    return [_hit(m, r, i, f"{c}|{d}", f"{c} has {r['target']} and {r['subject']} on {_day_name(m, d)}.", c) for (c, d), h in sorted(seen.items(), key=lambda kv: (kv[0][1], kv[0][0])) if all(h)]

def _once_a_day_per_group(m, spec, i, r, days, per):
    """as the solver: once a day when a group's lessons fit in the days, else at most ceil(lessons / days) a day"""
    ids, first, every = {}, {}, {}
    for x in m["lessons"]:
        for k in ([("C", c, x["subject"]) for c in x["classes"]] if x["group"] == ENTIRE else [("G", x["group"])]): every.setdefault(k, set()).add(x["id"])
    for x in _lessons(m, spec, r, days):
        for k in ([("C", c, x["subject"]) for c in x["classes"]] if x["group"] == ENTIRE else [("G", x["group"])]):
            ids.setdefault((k, x["d"]), set()).add(x["id"]); first.setdefault((k, x["d"]), x)
    cap = lambda k: max(1, -(-len(every[k]) // max(1, m["ND"])))
    return [_hit(m, r, i, f"{_kstr(k)}|{d}", f"{_name(k)} meets {'twice' if len(s) == 2 else f'{len(s)} times'} on {_day_name(m, d)}.", (first[k, d]["classes"] or ["School"])[0])
            for (k, d), s in sorted(ids.items(), key=lambda kv: (kv[0][1], kv[0][0])) if len(s) > cap(k)]

def _avoid_after_school(m, spec, i, r, days, per):
    return [_hit(m, r, i, _key(x), f"{_what(x)} is in an after-school slot on {_day_name(m, x['d'])}.", (x["classes"] or ["School"])[0], x)
            for x in _lessons(m, spec, r, days) if x.get("ext")]

CHECKERS = {"Not available": _not_available, "Keep free together": _keep_free_together, "Fixed at": _fixed_at, "Not in periods": _not_in_periods,
            "Only in periods": _only_in_periods, "Finish by": _finish_by, "Only these subjects": _only_these_subjects, "Only in venues": _only_in_venues,
            "Max periods a day": _max_periods_a_day, "Max periods in a row": _max_periods_in_a_row, "At least one recess a day": _at_least_one_recess,
            "At most N at once": _at_most_n_at_once, "Same time across classes": _same_time_across_classes, "Not on the same day as": _not_on_the_same_day_as,
            "Once a day per group": _once_a_day_per_group, "Avoid after-school slots": _avoid_after_school}
USES = {"Max periods a day": ("Teacher", "Class", "Level", "School"), "Max periods in a row": ("Teacher", "School"), "At least one recess a day": ("Teacher", "School"),
        "At most N at once": ("Subject", "Department", "Room"), "Same time across classes": ("Level",), "Not on the same day as": ("Subject",),
        "Once a day per group": ("School", "Subject"), "Avoid after-school slots": ("School", "Level", "Class")}   # the scopes each count or pattern rule is checked for
NEEDS_NUMBER = ("Max periods a day", "Max periods in a row", "At most N at once")
NEEDS_PERIODS = ("Not available", "Keep free together", "Not in periods", "Only in periods", "Only in venues")
_BLANK = lambda v: v in (None, "")

def _whole(v):
    """a From or To cell as a whole number, or None (3, '3' and 3.0 are 3)"""
    try: f = float(str(v).strip()); return int(f) if f == int(f) else None
    except (ValueError, OverflowError): return None

def _bad_periods(r):
    """why the row's From and To cannot be used, or None; a row with good ones gets them as whole numbers"""
    for k, name in (("from", "From"), ("to", "To")):
        if _BLANK(r.get(k)): continue
        if _whole(r[k]) is None: return f"{name} is not a whole number"
    a, b = (None if _BLANK(r.get(k)) else _whole(r[k]) for k in ("from", "to"))
    if a is not None and b is not None and a > b: return "its From period is after its To period"
    return None

def rules(m, spec):
    """(warnings, not_checked): each rule row except 'In words' goes to its checker; a row that cannot be checked is listed with why"""
    out, skipped = [], []
    for i, r in enumerate(spec.get("rules") or []):
        rule = r.get("rule")
        if rule == "In words": continue
        why = _bad_periods(r)
        if why: pass
        elif rule not in CHECKERS: why = "this kind of rule is not checked here"
        elif in_scope(m, spec, r) is None: why = f"scope {r.get('scope')} is not one the check knows"
        elif rule == "Keep free together" and r.get("scope") not in ("Department", "Level"): why = f"scope {r.get('scope')} is not one this rule uses (Department or Level)"
        elif rule == "Fixed at" and _BLANK(r.get("from")): why = "it has no From period"
        elif rule == "Finish by" and _BLANK(r.get("to")): why = "it has no To period"
        elif rule in USES and r.get("scope") not in USES[rule]: why = f"scope {r.get('scope')} is not one this rule uses ({', '.join(USES[rule])})"
        elif rule in NEEDS_NUMBER and _BLANK(r.get("number")): why = "it has no Number"
        elif rule in NEEDS_NUMBER and _number(r) is None: why = "Number is not a whole number"
        elif rule in ("Same time across classes", "Not on the same day as") and not names_list(r.get("subject")): why = "it names no subject"
        elif rule in NEEDS_PERIODS and _BLANK(r.get("from")) and _BLANK(r.get("to")): why = "it has no From or To period"
        elif rule == "Only these subjects" and not names_list(r.get("subject")): why = "it names no subjects"
        elif rule == "Only in venues" and not names_list(r.get("venues")): why = "it names no venues"
        if why: skipped.append(f"{rule_label(r)}: {why}"); continue
        r = dict(r, **{k: _whole(r[k]) for k in ("from", "to") if not _BLANK(r.get(k))})   # '2' and 3.0 read as 2 and 3
        out += CHECKERS[rule](m, spec, i, r, rule_days(m["days"], r), rule_periods(r, m["NP"]))
    return out, skipped


# ----------------------------------------------------------------------------------------------- typed rules, choices, everything together
def typed(spec, report):
    """warnings from the agent's Rule report against the typed (In words) rules on step 6"""
    out, nums = [], set()
    rows = {}
    for row in report or []: rows.setdefault(row.get("no"), row)
    for n, _, r in typed_rules(spec):
        nums.add(n); row = rows.get(n); sentence = str(r.get("text") or "").strip().rstrip("."); strength = r.get("strength") or "Must"
        if row is None:
            out.append(warning(f"typed:{n}:none", "typed", f"T{n} has no line in the rule report: {sentence}.", strength)); continue
        res = str(row.get("result") or "").strip(); how = str(row.get("how") or "").strip(); says = f" The agent says: {how}" if how else ""
        if res in ("Not met", "Partly"):
            out.append(warning(f"typed:{n}:{res}", "typed", f"T{n} {res.lower()}: {sentence}." + says, strength))
        elif res != "Met":   # a blank or unknown result is not taken as met
            out.append(warning(f"typed:{n}:unclear", "typed", f"T{n}: the rule report does not say whether it was met: {sentence}." + says, strength))
    for row in report or []:
        if row.get("no") not in nums:
            out.append(warning(f"typed:{row.get('no')}:unknown", "typed", f"The rule report's line {row.get('no')} ({row.get('rule')}) is not a typed rule on step 6."))
    return out

def choices_(m):
    return [warning("choice:" + p, "choice", p) for p in m.get("choice_problems") or []]

def warnings(m, spec=None):
    """every warning for the timetable m, in KINDS order, and the rules that could not be checked"""
    spec = spec or m["checked_setup"]; rule_ws, not_checked = rules(m, spec)
    ws = clashes(m) + deployment(m, spec) + rule_ws + typed(spec, m.get("rule_report")) + choices_(m); seen = {}
    for w in ws:   # several hits can share a key (two groups in one slot): a decision belongs to one warning, so each key is made unique
        seen[w["key"]] = n = seen.get(w["key"], 0) + 1
        if n > 1: w["key"] += f"#{n}"
    return dict(warnings=ws, not_checked=not_checked)

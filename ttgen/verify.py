"""Check a timetable made by an outside agent against the school's setup: every difference is a warning
(dict key, kind, text, strength, group, where, sides, ops). Periods are 0-based; day names are the setup's.
Every function that takes spec takes the checked setup (m["checked_setup"]), already derived."""
import re
from .export import ENTIRE
from .solver import rule_label
from .spec import names_list, subject_test

KINDS = ("clash", "deployment", "rule", "typed", "choice")

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
            e = out.setdefault(key, dict(rows=[], teachers=set(), periods=0, room_kind=None, classes=[c] if whole else list(x["classes"]), level=x.get("level"), subject=x["subject"]))
            e["rows"].append(x); e["teachers"] |= set(x.get("teachers") or [])
            e["periods"] = e["periods"] + int(x["periods"]) if whole else int(x["periods"])   # as _model: entire-class rows add up, a group's code is one lesson
            e["room_kind"] = e["room_kind"] or x.get("room_kind")
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

def deployment(m, spec):
    """one warning per difference between the timetable and step 5 (teachers, periods, venue kind, missing, extra)"""
    plan, got, out = planned_rows(spec), placed(m), []
    subjects = {str(s["subject"]) for s in spec["subjects"]}
    def where(key, e):
        x = e["lessons"][0]; return dict(cls=key[1] if key[0] == "C" else (x["classes"] or [""])[0], day=m["days"][x["d"]], period=x["p"])
    for key in plan:
        p, k, what = plan[key], _kstr(key), _name(key); group = p["classes"][0] if p["classes"] else "School"
        if key not in got:
            ids = _ids(p["rows"])
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
                if kind and kind != p["room_kind"]:
                    out.append(warning(f"dep:{k}:venue", "deployment", f"{what} is in {x['room']} ({kind}); step 3 asks for {p['room_kind']}.", group=group, where=w)); break
    for key, g in got.items():
        if key in plan: continue
        k, x = _kstr(key), g["lessons"][0]
        classes = [key[1]] if key[0] == "C" else list(x["classes"])
        ops = [["add", "lessons", dict(level=x["level"], subject=x["subject"], classes=classes, teachers=sorted(g["teachers"]), block=x["block"] or None,
                                                  **({} if key[0] == "C" else dict(code_override=key[1]))), ""]] if x["subject"] in subjects else None
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
    where = dict(cls=(x["classes"] or [""])[0], day=m["days"][x["d"]], period=x["p"]) if x else None
    return warning(f"rule:{i}:{detail}", "rule", f"Rule {rule_label(r)}: {sentence}" + (" (Prefer)" if prefer else ""), "Prefer" if prefer else "Must", group, where)

def _lessons(m, spec, r, days):
    """the lessons in scope that sit on a rule day"""
    test = in_scope(m, spec, r)
    return [x for x in m["lessons"] if x["d"] in days and test(x)]

def _inside(x, per): return [q for q in _span(x) if q in per]
def _key(x, q=None): return f"{(x['classes'] or [''])[0]}|{x['d']}|{x['p'] if q is None else q}"

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

CHECKERS = {"Not available": _not_available, "Keep free together": _keep_free_together, "Fixed at": _fixed_at, "Not in periods": _not_in_periods,
            "Only in periods": _only_in_periods, "Finish by": _finish_by, "Only these subjects": _only_these_subjects, "Only in venues": _only_in_venues}
_BLANK = lambda v: v in (None, "")

def rules(m, spec):
    """(warnings, not_checked): each rule row except 'In words' goes to its checker; a row that cannot be checked is listed with why"""
    out, skipped = [], []
    for i, r in enumerate(spec.get("rules") or []):
        rule = r.get("rule")
        if rule == "In words": continue
        why = None
        if rule not in CHECKERS: why = "this kind of rule is not checked here"
        elif in_scope(m, spec, r) is None: why = f"scope {r.get('scope')} is not one the check knows"
        elif rule == "Keep free together" and r.get("scope") not in ("Department", "Level"): why = f"scope {r.get('scope')} is not one this rule uses (Department or Level)"
        elif rule == "Fixed at" and _BLANK(r.get("from")): why = "it has no From period"
        elif rule == "Finish by" and _BLANK(r.get("to")): why = "it has no To period"
        elif rule not in ("Fixed at", "Finish by", "Only these subjects") and _BLANK(r.get("from")) and _BLANK(r.get("to")): why = "it has no From or To period"
        elif rule == "Only these subjects" and not names_list(r.get("subject")): why = "it names no subjects"
        elif rule == "Only in venues" and not names_list(r.get("venues")): why = "it names no venues"
        if why: skipped.append(f"{rule_label(r)}: {why}"); continue
        out += CHECKERS[rule](m, spec, i, r, rule_days(m["days"], r), rule_periods(r, m["NP"]))
    return out, skipped

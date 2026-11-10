"""Fixes to the draft: each is one change the committee made to the timetable they uploaded, kept as a small record and
applied again, in order, to the lessons read from the file. Nothing here touches files or the setup."""
import copy
from ttgen.export import ENTIRE
from ttgen import verify

KINDS = ("move", "swap", "teacher", "room", "add", "delete")

def what(x):
    """a lesson row in words: '{subject} for {class}' for an entire-class lesson, 'group {code}' otherwise"""
    return f"{x['subject']} for {', '.join(x['classes'])}" if x["group"] == ENTIRE else f"group {x['group']}"

def when(days, d, p): return f"{days[d]} period {p}"

def _rows(lessons, i):
    rows = [x for x in lessons if x["id"] == i]
    if not rows: raise ValueError("There is no lesson with that id on the timetable.")
    return rows

def _key(s):
    """'C:{class}:{subject}' or 'G:{code}' -> the key verify.planned_rows uses"""
    return tuple(s.split(":", 2)) if s.startswith("C:") else tuple(s.split(":", 1))

def _names(names): return ", ".join(names) if names else "nobody"

def _slot(days, d, p):
    if not isinstance(d, int) or not 0 <= d < len(days) or not isinstance(p, int) or p < 0: raise ValueError("That day or period is not on the timetable.")

def apply_one(lessons, fix, spec, days):
    """change lessons (a list the caller owns) in place and return the sentence for the committee; ValueError(sentence) when the fix cannot apply"""
    kind = fix.get("kind")
    if kind == "move":
        rows = _rows(lessons, fix["id"]); _slot(days, fix["d"], fix["p"]); a = rows[0]; text = f"Moved {what(a)} from {when(days, a['d'], a['p'])} to {when(days, fix['d'], fix['p'])}."
        for x in rows: x["d"], x["p"] = fix["d"], fix["p"]
        return text
    if kind == "swap":
        ra, rb = _rows(lessons, fix["a"]), _rows(lessons, fix["b"]); a, b = ra[0], rb[0]
        if a["n"] != b["n"]: raise ValueError(f"{what(a)} and {what(b)} are not the same length, so they cannot swap places.")
        text = f"Swapped {what(a)} ({when(days, a['d'], a['p'])}) with {what(b)} ({when(days, b['d'], b['p'])})."
        (da, pa), (db, pb) = (a["d"], a["p"]), (b["d"], b["p"])
        for x in ra: x["d"], x["p"] = db, pb
        for x in rb: x["d"], x["p"] = da, pa
        return text
    if kind == "teacher":
        key = _key(fix["key"]); name = verify._name(key); known = {x["name"] for x in spec.get("teachers") or []}
        rows = [x for x in lessons if (x["group"] == ENTIRE and key[0] == "C" and key[1] in x["classes"] and x["subject"] == key[2]) or (key[0] == "G" and x["group"] == key[1])]
        if not rows: raise ValueError(f"There is no lesson of {name} on the timetable.")
        bad = [x for x in fix["teachers"] if x not in known]
        if bad: raise ValueError(f"{', '.join(bad)} {'is' if len(bad) == 1 else 'are'} not on the setup's list of teachers.")
        old = list(dict.fromkeys(t for x in rows for t in x["teachers"]))
        for x in rows: x["teachers"] = list(fix["teachers"])
        return f"{name} is now taught by {_names(fix['teachers'])}, not {_names(old)}."
    if kind == "room":
        x = next((x for x in _rows(lessons, fix["id"]) if x["group"] == fix["group"]), None)
        if x is None: raise ValueError(f"There is no row of {fix['group']} in that lesson.")
        if fix["room"] and fix["room"] not in {v["room"] for v in spec.get("venues") or []}: raise ValueError(f"{fix['room']} is not on the setup's list of rooms.")
        text = f"{what(x)} on {when(days, x['d'], x['p'])} is now in {fix['room'] or 'no room'}, not {x['room'] or 'no room'}."
        x["room"] = fix["room"]
        return text
    if kind == "add":
        key = _key(fix["key"]); e = verify.planned_rows(spec).get(key)
        if not e: raise ValueError(f"Step 5 has no lesson for {verify._name(key) if len(key) in (2, 3) else fix['key']}.")
        _slot(days, fix["d"], fix["p"])
        if not isinstance(fix["n"], int) or fix["n"] < 1: raise ValueError("A lesson is at least one period long.")
        if fix["room"] and fix["room"] not in {v["room"] for v in spec.get("venues") or []}: raise ValueError(f"{fix['room']} is not on the setup's list of rooms.")
        x = dict(id=1 + max([y["id"] for y in lessons], default=0), d=fix["d"], p=fix["p"], n=fix["n"], level=e["level"] or "", block=str(e["rows"][0].get("block") or ""),
                 classes=list(e["classes"]), subject=e["subject"], group=ENTIRE if key[0] == "C" else key[1],
                 teachers=list(dict.fromkeys(t for r in e["rows"] for t in r.get("teachers") or [])), room=fix["room"], ext=False, rain="")
        lessons.append(x)
        return f"Added {what(x)} on {when(days, x['d'], x['p'])} ({x['n']} periods) {'in ' + x['room'] if x['room'] else 'with no room'}."
    if kind == "delete":
        rows = [x for x in _rows(lessons, fix["id"]) if fix.get("group") is None or x["group"] == fix["group"]]
        if not rows: raise ValueError(f"There is no row of {fix['group']} in that lesson.")
        a = rows[0]; text = f"Deleted {what(a)} on {when(days, a['d'], a['p'])}."
        lessons[:] = [x for x in lessons if not any(x is r for r in rows)]
        return text
    raise ValueError("This kind of fix is not known.")

def apply(lessons, fixes, spec, days):
    """a copy of lessons with every fix applied in order -> dict(lessons, texts, problems, touched). A fix that cannot apply
    (the file or the setup changed since) is skipped and named in problems; touched is the ids of lessons a fix changed or added."""
    L, texts, problems, touched = copy.deepcopy(lessons), [], [], set()
    for f in fixes:
        before = copy.deepcopy(L)
        try: texts.append(apply_one(L, f, spec, days))
        except (ValueError, KeyError, TypeError) as e:
            L[:] = before; problems.append(f"A fix could not be applied: {e if isinstance(e, ValueError) else 'it is not complete.'}"); continue
        touched |= {x["id"] for x in L if x not in before} | {x["id"] for x in before if x not in L}
    return dict(lessons=L, texts=texts, problems=problems, touched=touched)

def editor(fixes, out):
    """the edit function for model_from_files: applies the fixes to the lessons read from the file and leaves texts, problems and touched in out"""
    def edit(lessons, spec, days):
        r = apply(lessons, fixes, spec, days); out.update(texts=r["texts"], problems=r["problems"], touched=r["touched"]); return r["lessons"]
    return edit

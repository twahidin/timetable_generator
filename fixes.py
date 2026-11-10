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
    k = tuple(s.split(":", 2)) if isinstance(s, str) and s.startswith("C:") else tuple(s.split(":", 1)) if isinstance(s, str) and s.startswith("G:") else ()
    if len(k) != (3 if k[:1] == ("C",) else 2) or not all(k): raise ValueError("That is not a lesson of step 5.")
    return k

def _names(names): return ", ".join(names) if names else "nobody"

def _slot(spec, days, d, p, n):
    """the lesson, n periods long from period p on day d, must be inside the day"""
    if not all(isinstance(v, int) and not isinstance(v, bool) for v in (d, p, n)) or not 0 <= d < len(days) or p < 0 or n < 1 or p + n > int(spec["school"]["periods_per_day"]): raise ValueError("That is outside the day.")

def apply_one(lessons, fix, spec, days, new_id=None, touched=None):
    """change lessons (a list the caller owns) in place and return the sentence for the committee; ValueError(sentence) when the
    fix cannot apply (every kind checks before it changes anything). new_id: the id an add takes (default 1 + the highest in
    lessons); touched: a set the ids of lessons changed or added are put into."""
    if not isinstance(fix, dict): raise ValueError("it is not complete.")
    kind = fix.get("kind"); touched = set() if touched is None else touched
    if kind == "move":
        rows = _rows(lessons, fix["id"]); _slot(spec, days, fix["d"], fix["p"], rows[0]["n"]); a = rows[0]; text = f"Moved {what(a)} from {when(days, a['d'], a['p'])} to {when(days, fix['d'], fix['p'])}."
        for x in rows: x["d"], x["p"] = fix["d"], fix["p"]
        touched.add(fix["id"]); return text
    if kind == "swap":
        ra, rb = _rows(lessons, fix["a"]), _rows(lessons, fix["b"]); a, b = ra[0], rb[0]
        if a["n"] != b["n"]: raise ValueError(f"{what(a)} and {what(b)} are not the same length, so they cannot swap places.")
        text = f"Swapped {what(a)} ({when(days, a['d'], a['p'])}) with {what(b)} ({when(days, b['d'], b['p'])})."
        (da, pa), (db, pb) = (a["d"], a["p"]), (b["d"], b["p"])
        for x in ra: x["d"], x["p"] = db, pb
        for x in rb: x["d"], x["p"] = da, pa
        touched |= {fix["a"], fix["b"]}; return text
    if kind == "teacher":
        key = _key(fix["key"]); name = verify._name(key); known = {x["name"] for x in spec.get("teachers") or []}
        rows = [x for x in lessons if (x["group"] == ENTIRE and key[0] == "C" and key[1] in x["classes"] and x["subject"] == key[2]) or (key[0] == "G" and x["group"] == key[1])]
        if not rows: raise ValueError(f"There is no lesson of {name} on the timetable.")
        bad = [x for x in fix["teachers"] if x not in known]
        if bad: raise ValueError(f"{', '.join(bad)} {'is' if len(bad) == 1 else 'are'} not on the setup's list of teachers.")
        old = list(dict.fromkeys(t for x in rows for t in x["teachers"]))
        for x in rows: x["teachers"] = list(fix["teachers"])
        touched |= {x["id"] for x in rows}
        return f"{name} is now taught by {_names(fix['teachers'])}, not {_names(old)}."
    if kind == "room":
        x = next((x for x in _rows(lessons, fix["id"]) if x["group"] == fix["group"]), None)
        if x is None: raise ValueError(f"There is no row of {fix['group']} in that lesson.")
        if fix["room"] and fix["room"] not in {v["room"] for v in spec.get("venues") or []}: raise ValueError(f"{fix['room']} is not on the setup's list of rooms.")
        text = f"{what(x)} on {when(days, x['d'], x['p'])} is now in {fix['room'] or 'no room'}, not {x['room'] or 'no room'}."
        x["room"] = fix["room"]; touched.add(x["id"])
        return text
    if kind == "add":
        key = _key(fix["key"]); e = verify.planned_rows(spec).get(key)
        if not e: raise ValueError(f"Step 5 has no lesson for {verify._name(key) if len(key) in (2, 3) else fix['key']}.")
        _slot(spec, days, fix["d"], fix["p"], fix["n"])
        if fix["room"] and fix["room"] not in {v["room"] for v in spec.get("venues") or []}: raise ValueError(f"{fix['room']} is not on the setup's list of rooms.")
        x = dict(id=new_id if new_id is not None else 1 + max([y["id"] for y in lessons], default=0), d=fix["d"], p=fix["p"], n=fix["n"], level=e["level"] or "", block=str(e["rows"][0].get("block") or ""),
                 classes=list(e["classes"]), subject=e["subject"], group=ENTIRE if key[0] == "C" else key[1],
                 teachers=list(dict.fromkeys(t for r in e["rows"] for t in r.get("teachers") or [])), room=fix["room"], ext=False, rain="")
        lessons.append(x); touched.add(x["id"])
        return f"Added {what(x)} on {when(days, x['d'], x['p'])} ({x['n']} periods) {'in ' + x['room'] if x['room'] else 'with no room'}."
    if kind == "delete":
        rows = [x for x in _rows(lessons, fix["id"]) if fix.get("group") is None or x["group"] == fix["group"]]
        if not rows: raise ValueError(f"There is no row of {fix['group']} in that lesson.")
        a = rows[0]; text = f"Deleted {what(a)} on {when(days, a['d'], a['p'])}."
        lessons[:] = [x for x in lessons if not any(x is r for r in rows)]
        if not any(x["id"] == fix["id"] for x in lessons): touched.discard(fix["id"])
        return text
    raise ValueError("This kind of fix is not known.")

def apply(lessons, fixes, spec, days):
    """a copy of lessons with every fix applied in order -> dict(lessons, texts, problems, touched). A fix that cannot apply
    (the file or the setup changed since, or it is malformed) is skipped and named in problems; touched is the ids of lessons
    a fix changed or added. An add takes 1 + the highest id as read from the file, plus one per add before it."""
    L, texts, problems, touched = copy.deepcopy(lessons), [], [], set()
    nxt = 1 + max([x["id"] for x in L], default=0)
    for f in fixes:
        try: texts.append(apply_one(L, f, spec, days, new_id=nxt, touched=touched))
        except Exception as e: problems.append(f"A fix could not be applied: {e if isinstance(e, ValueError) else 'it is not complete.'}"); continue
        if isinstance(f, dict) and f.get("kind") == "add": nxt += 1
    return dict(lessons=L, texts=texts, problems=problems, touched=touched)

def editor(fixes, out):
    """the edit function for model_from_files: applies the fixes to the lessons read from the file and leaves texts, problems and touched in out"""
    def edit(lessons, spec, days):
        r = apply(lessons, fixes, spec, days); out.update(texts=r["texts"], problems=r["problems"], touched=r["touched"]); return r["lessons"]
    return edit

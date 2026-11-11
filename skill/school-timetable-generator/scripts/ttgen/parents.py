"""The Class Parents rule (a class's form teachers and the lessons they take), the twin of static/parents.js: both run
the cases in tests/parents_cases.json, so change them together. Pure: functions over a spec dict, standard library only."""


def _blank(n):
    return n is None or str(n).strip() == ""


def _school(spec):
    return (spec or {}).get("school") or {}


def _list(spec, k):
    v = (spec or {}).get(k)
    return v if isinstance(v, list) else []


def names(row):
    """A row's teachers (or a class's parents) with blanks dropped."""
    row = row or {}
    v = row["teachers"] if row.get("teachers") is not None else row.get("parents")
    return [n for n in v if not _blank(n)] if isinstance(v, list) else []


def subjects(spec):
    """The named subjects that are on step 3, in the order the school named them."""
    named = _school(spec).get("parents_subjects")
    if not isinstance(named, list):
        return []
    have = {s.get("subject") for s in _list(spec, "subjects")}
    return [n for i, n in enumerate(named) if n in have and named.index(n) == i]


def cap(spec):
    """max(3, parents_max) where parents_max is a whole number 1 to 6 (a number or digits); anything else counts as 2."""
    v = _school(spec).get("parents_max")
    if isinstance(v, str) and v.isascii() and v.isdigit():
        v = int(v)
    n = v if isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and abs(v) != float("inf") and v == int(v) and 1 <= v <= 6 else 2
    return max(3, int(n))


def label(spec):
    return str(_school(spec).get("parents_name") or "").strip() or "Form teachers"


def staffed(spec, row):
    return bool(row) and not row.get("block") and not row.get("code_override") and row.get("subject") in subjects(spec)


def follows(spec, row):
    return staffed(spec, row) and row.get("by_hand") is not True


def want(spec, row):
    """The Class Parents of each of the row's classes, class order then box order, each name once."""
    out = []
    for cn in row.get("classes") or []:
        c = next((k for k in _list(spec, "classes") if k.get("class") == cn), None)
        for n in names(c):
            if n not in out:
                out.append(n)
    return out


def same(a, b):
    """The same people, order ignored."""
    a, b = names({"teachers": a}), names({"teachers": b})
    return all(n in b for n in a) and all(n in a for n in b)


def adopt(spec, only=None):
    """Protect typed teachers: mark by_hand on every following row with other people than the boxes give."""
    n = 0
    for r in _list(spec, "lessons"):
        if not follows(spec, r) or not names(r):
            continue
        if only and only.get("subjects") is not None and r.get("subject") not in only["subjects"]:
            continue
        if only and only.get("classes") is not None and not any(c in only["classes"] for c in r.get("classes") or []):
            continue
        w = want(spec, r)
        if not w or same(names(r), w):
            continue
        r["by_hand"] = True
        n += 1
    return n


def derive(spec):
    """Put the setup right. Returns whether anything changed."""
    changed, subs, lessons = False, subjects(spec), _list(spec, "lessons")
    for r in lessons:
        if "by_hand" in r and (r["by_hand"] is not True or not staffed(spec, r)):
            del r["by_hand"]
            changed = True
    if not subs:
        return changed
    for c in _list(spec, "classes"):
        if not c.get("_id") or not c.get("level"):
            continue
        for sn in subs:
            s = next((k for k in _list(spec, "subjects") if k.get("subject") == sn), None)
            per = s.get("periods") if s else None
            try:
                p = float((per.get(c["level"]) if isinstance(per, dict) else 0) or 0)
            except (TypeError, ValueError):
                p = 0
            if not s or not s.get("_id") or not p > 0:
                continue
            if any(r.get("subject") == sn and c.get("class") in (r.get("classes") or []) for r in lessons):
                continue
            lessons.append({"_id": "cp-" + str(c["_id"]) + "-" + str(s["_id"]), "level": c["level"], "subject": sn, "block": None,
                            "classes": [c.get("class")], "teachers": names(c), "students": None})
            changed = True
    for r in lessons:
        if not follows(spec, r):
            continue
        w = want(spec, r)
        if not w or r.get("teachers") == w:
            continue
        r["teachers"] = w
        changed = True
    return changed

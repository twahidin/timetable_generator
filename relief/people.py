"""The people relief knows: the published timetable's teachers plus staff who do not teach."""
import access
from ttgen import spec as _spec

def people(pub, extra):
    """-> [dict(name, short, depts, role, teaches, staff_only)], by first department (people with none last) then name"""
    model = ((pub or {}).get("model") or {})
    teaching = {n for L in model.get("lessons") or [] for n in L.get("teachers") or []}
    out, seen = [], set()
    for t in (model.get("setup") or {}).get("teachers") or []:
        name = str(t.get("name") or "").strip()
        if not name or name in seen: continue
        seen.add(name)
        out.append(dict(name=name, short=str(t.get("short") or name), depts=_spec.teacher_depts(t), role=str(t.get("role") or ""),
                        teaches=name in teaching, staff_only=False))
    for t in model.get("teachers") or []:
        name = str(t.get("name") or "").strip()
        if not name or name in seen: continue
        seen.add(name)
        d = str(t.get("dept") or "").strip()
        out.append(dict(name=name, short=str(t.get("short") or name), depts=[d] if d else [], role="", teaches=name in teaching, staff_only=False))
    for x in extra or []:
        name = str(x.get("name") or "").strip()
        if not name or name in seen: continue
        seen.add(name)
        out.append(dict(name=name, short=name, depts=[], role="", teaches=False, staff_only=True))
    out.sort(key=lambda p: (not p["depts"], p["depts"][0] if p["depts"] else "", p["name"]))   # no department: last
    return out

def staff_codes(people):
    """{normalised personal code: name}; empty when personal codes are off"""
    if not access.personal_codes_on(): return {}
    return {access.norm(access.staff_code(p["name"])): p["name"] for p in people}

def fake_pub(teachers, lessons=(), roles=(), days=None):
    """a minimal published dict for tests: setup teacher rows, then lesson-only names, as ttgen/export.py builds them"""
    days = list(days) if days is not None else _spec.day_names(2)
    rows = [dict(name=t["name"], dept=t.get("dept"), dept2=t.get("dept2"), role=t.get("role"), short=t.get("short")) for t in teachers]
    model_teachers = [dict(name=str(t["name"]), short=str(t.get("short") or t["name"]), dept=t.get("dept") or "", allowance="", other="") for t in rows]
    seen = {t["name"] for t in model_teachers}
    lessons = [dict(L) for L in lessons]
    for L in lessons:
        for n in L.get("teachers") or []:
            if n not in seen: seen.add(n); model_teachers.append(dict(name=n, short=n, dept="", allowance="", other=""))
    return dict(meta=dict(school="Sample School"), codes={}, views={},
                model=dict(setup=dict(teachers=rows, roles=[dict(r) for r in roles]), teachers=model_teachers, lessons=lessons, days=days,
                           school=dict(name="Sample School", weeks=2 if len(days) == 10 else 1)))

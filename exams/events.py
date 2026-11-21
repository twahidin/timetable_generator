"""Events: who goes, the lessons an event stops, the rooms it frees and what it clashes with. Pure: reads no files except
relief's settings (as invigilate.candidates does)."""
import relief.people
import relief.settings
from exams import days as _days
from exams import invigilate as _inv
from exams import schedules as _sched
from exams import seating as _seat

FREE = dict(never=[], backups=[], rules=dict(max_per_day=None))


def _people(pub):
    return relief.people.people(pub, relief.settings.load(pub)["extra_staff"])


def on_dates(pub, cal, s) -> list:
    """the dates of the event that are school days with classes on, in date order, with that day's window"""
    model = pub["model"]
    bnds = _days.bounds(model)
    out = []
    for e in _days.dates(s, cal, model):
        if e["day"] is None:
            continue
        classes = list(_days._windows(s, e["date"], model, bnds))
        if classes:
            out.append(dict(date=e["date"], day=e["day"], classes=classes, start=e["start"], end=e["end"]))
    return out


def _views(pub, cal, s):
    return [(e, _days.day_view(pub, cal, s, e["date"])) for e in on_dates(pub, cal, s)]


def _event_classes(pub, s):
    model = pub["model"]
    levels, chosen = _days.levels_of(s, model), set(s.get("classes") or [])
    return [c for c in model.get("classes") or [] if c["level"] in levels and (not chosen or c["name"] in chosen)]


def fill(pub, cal, s, way, dept="", names=()) -> list:
    """the names a way of filling the going list gives that are not going yet and are on the timetable or staff list"""
    if way not in _sched.GOING_BY:
        raise ValueError(_sched.WRONG)
    people = _people(pub)
    known = [p["name"] for p in people]
    if way == "form teachers":
        got = [n for c in _event_classes(pub, s) for n in c.get("parents") or []]
    elif way == "teachers then":
        seen = {}
        for e, view in _views(pub, cal, s):
            for l in view["lessons"]:
                if l["stopped"]:
                    for n in l["teachers"]:
                        seen.setdefault(n, (e["date"], l["stopped"][0][0], l["row"]))
        got = sorted(seen, key=seen.get)
    elif way == "department":
        if not str(dept or "").strip():
            raise ValueError("Pick a department.")
        got = [p["name"] for p in people if dept in p["depts"]]
    else:
        got = list(names)
    out, have = [], set(s.get("going") or [])
    for n in got:
        if n in known and n not in have and n not in out:
            out.append(n)
    return out


def _spans(view, name, start, end):
    return [(l, sp) for l in view["lessons"] if name in l["teachers"] for sp in l["running"] if sp[0] < end and sp[1] > start]


def going(pub, cal, s, elsewhere) -> list:
    views = _views(pub, cal, s)
    many = len(views) > 1
    parents = {}
    for c in _event_classes(pub, s):
        for n in c.get("parents") or []:
            parents.setdefault(n, []).append(c["name"])
    out = []
    for name in s.get("going") or []:
        tags = (["teacher in charge"] if name == s.get("in_charge") else []) + ["%s form teacher" % c for c in parents.get(name, [])]
        why, lessons, stops = [], [], []
        for e, view in views:
            suffix = " (%s)" % _days.nice(e["date"]) if many else ""
            reason, _ = _inv._free(name, view, e["start"], e["end"], [], FREE, elsewhere=elsewhere)
            if reason:
                why.append(reason + suffix)
                continue
            for l, sp in _spans(view, name, e["start"], e["end"]):
                lessons.append("teaches %s %s %s–%s%s" % (", ".join(l["classes"]), l["subject"], _days.hhmm(sp[0]), _days.hhmm(sp[1]), suffix))
            for l in view["lessons"]:
                if name in l["teachers"] and l["stopped"]:
                    for c in l["classes"]:
                        if c not in stops:
                            stops.append(c)
        if why:
            status, text = "not_free", why[0]
        elif lessons:
            status, text = "backup", "; ".join(lessons) + " → backup"
        else:
            status, text = "free", "free then: lessons with %s stop" % ", ".join(stops) if stops else "free then"
        out.append(dict(name=name, tag=" · ".join(tags), status=status, text=text))
    return out


def lesson_lists(pub, cal, s) -> dict:
    out = dict(none=[], backup=[], runs=[])
    goes = set(s.get("going") or [])
    for e, view in _views(pub, cal, s):
        for l in view["lessons"]:
            def item(span, note):
                return dict(date=e["date"], start=_days.hhmm(span[0]), end=_days.hhmm(span[1]), classes=list(l["classes"]),
                            subject=l["subject"], teachers=list(l["teachers"]), room=l["room"], note=note)
            for sp in l["stopped"]:
                out["none"].append(item(sp, "shortened" if l["running"] else ""))
            for sp in l["running"]:
                who = next((t for t in l["teachers"] if t in goes), None) if sp[0] < e["end"] and sp[1] > e["start"] else None
                if who:
                    out["backup"].append(item(sp, "%s is at %s" % (who, s["name"])))
                else:
                    out["runs"].append(item(sp, ""))
    return out


def _taken(pub, s):
    parts = pub["model"].get("room_parts") or {}
    out = set()
    for v in s.get("venues") or []:
        out.update(_seat._related(v, parts))
    return out


def freed(pub, cal, s) -> list:
    parts = pub["model"].get("room_parts") or {}
    taken = _taken(pub, s)
    out = []
    for e, view in _views(pub, cal, s):
        used = set(taken)
        for l in view["lessons"]:
            if any(sp[0] < e["end"] and sp[1] > e["start"] for sp in l["running"]):
                for r in (l["room"], l.get("rain")):
                    if r:
                        used.update(_seat._related(r, parts))
        rooms = sorted({l["room"] for l in view["lessons"] if l["stopped"] and l["room"] and l["room"] not in used})
        if rooms:
            out.append(dict(date=e["date"], start=_days.hhmm(e["start"]), end=_days.hhmm(e["end"]), rooms=rooms))
    return out


def flags(pub, cal, s) -> list:
    parts = pub["model"].get("room_parts") or {}
    taken = _taken(pub, s)
    rows = []
    for e, view in _views(pub, cal, s):
        for l in view["lessons"]:
            for sp in l["running"]:
                if not (sp[0] < e["end"] and sp[1] > e["start"]):
                    continue
                if l["room"] and l["room"] in taken:
                    room, wet = l["room"], ""
                elif l.get("rain") and l["rain"] in taken:
                    room, wet = l["rain"], " in wet weather"
                else:
                    continue
                rows.append((e["date"], sp[0], room, "%s %s–%s: %s with %s uses %s%s then." % (
                    _days.nice(e["date"]), _days.hhmm(sp[0]), _days.hhmm(sp[1]), l["subject"], ", ".join(l["classes"]), room, wet)))
    return [r[3] for r in sorted(rows)]


def cuts(pub, cal, s) -> list:
    out = []
    for e, view in _views(pub, cal, s):
        n = _days.edge_cuts(view)
        if n:
            out.append("On %s the event time ends in the middle of %s." % (_days.nice(e["date"]), "1 lesson" if n == 1 else "%d lessons" % n))
    return out

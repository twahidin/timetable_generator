"""Events: who goes, the lessons an event stops, the rooms it frees and what it clashes with. Pure: reads no files except
relief's settings (as invigilate.candidates does)."""
import relief.people
import relief.settings
from exams import approval as _approval
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
        raise ValueError(_sched.EVENT_WRONG)
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
            for l, sp in sorted(_spans(view, name, e["start"], e["end"]), key=lambda x: x[1][0]):
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


def _rains(l) -> list:
    """the wet-weather rooms of a lesson: the published model joins several with ", " """
    return [x.strip() for x in str(l.get("rain") or "").split(",") if x.strip()]


def freed(pub, cal, s, elsewhere=()) -> list:
    parts = pub["model"].get("room_parts") or {}
    taken = _taken(pub, s)
    out = []
    for e, view in _views(pub, cal, s):
        used = set(taken)
        for b in elsewhere:   # a room another schedule's duty or venue uses then
            if b.get("room") and b["date"] == e["date"] and b["start"] < e["end"] and b["end"] > e["start"]:
                used.update(_seat._related(b["room"], parts))
        for l in view["lessons"]:
            if any(sp[0] < e["end"] and sp[1] > e["start"] for sp in l["running"]):
                for r in [l["room"]] + _rains(l):
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
                elif any(x in taken for x in _rains(l)):
                    room, wet = next(x for x in _rains(l) if x in taken), " in wet weather"
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


def people_lines(pub, cal, s, elsewhere) -> list:
    """each person going who is not free for the event on a date, with why"""
    views = _views(pub, cal, s)
    out = []
    for name in s.get("going") or []:
        for e, view in views:
            why, _ = _inv._free(name, view, e["start"], e["end"], [], FREE, elsewhere=elsewhere)
            if why:
                out.append("%s, %s %s–%s: %s." % (name, _days.nice(e["date"]), _days.hhmm(e["start"]), _days.hhmm(e["end"]), why))
    return out


def other_lines(pub, cal, s, elsewhere, others) -> list:
    """the other schedules (copies) holding the event's classes at the same time, and using a venue it takes"""
    model = pub["model"]
    bnds = _days.bounds(model)
    parts = model.get("room_parts") or {}
    taken = _taken(pub, s)
    dates = on_dates(pub, cal, s)
    tags = sorted({(o["name"], o["status"]) for o in others} | {(b["name"], b["status"]) for b in elsewhere})
    shares, uses = [], []
    for tag in tags:
        label = "%s (%s)" % tag
        for e in dates:
            for o in (o for o in others if (o["name"], o["status"]) == tag):
                win = _days._windows(o, e["date"], model, bnds)
                line = _sched.shared_line(model, s, label, e["date"], e["start"], e["end"],
                                          [c for c, w in win.items() if w[0] < e["end"] and w[1] > e["start"]])
                if line and line not in shares:
                    shares.append(line)
            rooms = []
            for b in (b for b in elsewhere if (b["name"], b["status"]) == tag and b["date"] == e["date"] and b["room"]):
                if b["start"] < e["end"] and b["end"] > e["start"] and b["room"] in taken and b["room"] not in rooms:
                    rooms.append(b["room"])
            uses += ["%s uses %s on %s too." % (label, r, _days.nice(e["date"])) for r in rooms]
    return shares + uses


def clashes(pub, cal, s, elsewhere, others) -> list:
    return people_lines(pub, cal, s, elsewhere) + other_lines(pub, cal, s, elsewhere, others)


def send_errors(pub, cal, s, elsewhere, others) -> list:
    """what stops an event from being sent, in order (the name and the classes are checked on every save)"""
    out = []
    if not on_dates(pub, cal, s):
        out.append("Pick at least one school day for the event.")
    going = s.get("going") or []
    if not going:
        out.append("Add at least one person going with the classes.")
    if any(d.get("who") not in going for d in s.get("duties") or []):
        out.append("Pick a person going for every duty.")
    found = clashes(pub, cal, s, elsewhere, others)
    if found:
        out.append("Fix the clashes first: %s" % found[0])
    return out


def who_free(pub, cal, s, elsewhere) -> dict:
    """everyone relief knows who is not going and is free for the whole event: freed (a lesson of theirs stops then) or free"""
    views = _views(pub, cal, s)
    goes = set(s.get("going") or [])
    freed, free = [], []
    for p in sorted(_people(pub), key=lambda p: p["name"]):
        name = p["name"]
        if name in goes:
            continue
        stops, ok = [], True
        for e, view in views:
            why, _ = _inv._free(name, view, e["start"], e["end"], [], FREE, elsewhere=elsewhere)
            if why or _spans(view, name, e["start"], e["end"]):
                ok = False
                break
            for l in view["lessons"]:
                if name in l["teachers"] and any(sp[0] < e["end"] and sp[1] > e["start"] for sp in l["stopped"]):
                    stops += [c for c in l["classes"] if c not in stops]
        if not ok:
            continue
        if stops:
            freed.append(dict(name=name, reason="freed: lessons with %s stop" % ", ".join(stops)))
        else:
            free.append(dict(name=name, reason="free then"))
    return dict(freed=freed, free=free)


def _what(pub, cal, s) -> dict:
    model = pub["model"]
    dts = on_dates(pub, cal, s)
    inside = {c for e in dts for c in e["classes"]}
    entry = lambda date: (s.get("days") or {}).get(date) or {}
    venues = [dict(room=v, dates=len(dts), start=_days.hhmm(min(e["start"] for e in dts)), end=_days.hhmm(max(e["end"] for e in dts)))
              for v in sorted(s.get("venues") or []) if dts]
    ll = lesson_lists(pub, cal, s)
    return dict(kind="event", classes=[c["name"] for c in model.get("classes") or [] if c["name"] in inside],
                levels=_days.levels_of(s, model), start=s.get("start"), end=s.get("end"),
                days=[dict(date=e["date"], whole=bool(entry(e["date"]).get("whole", True)),
                           window=[_days.hhmm(e["start"]), _days.hhmm(e["end"])]) for e in dts],
                where=_sched.place(s), in_charge=s.get("in_charge"), stopped=len(ll["none"]), going=len(s.get("going") or []),
                backups=len(ll["backup"]), venues=venues, flagged=len(flags(pub, cal, s)))


def review(pub, cal, sched, elsewhere, others) -> dict:
    """what the timetable committee sees before approving an event: the copy reviewed (the approved one when approved, else
    the working copy), a summary, three checks, the change list and the replacements done without a new approval"""
    ap = _approval.as_schedule(sched) if sched.get("status") == "approved" else None
    s = ap or sched
    lines = lambda found, ok: found or [ok]
    going, vs, oth = people_lines(pub, cal, s, elsewhere), flags(pub, cal, s), other_lines(pub, cal, s, elsewhere, others)
    checks = [dict(key="going", ok=not going, lines=lines(going, "Everyone going is free then.")),
              dict(key="venues", ok=not vs, lines=lines(vs, "No running lesson uses the venues taken.")),
              dict(key="others", ok=not oth, lines=lines(oth, "No clash with other schedules."))]
    return dict(copy="approved" if ap else "working", what=_what(pub, cal, s), checks=checks,
                changes=_approval.changes(sched, pub["model"]) if sched.get("status") == "changes" else [],
                done_without=_approval.done_without(sched))

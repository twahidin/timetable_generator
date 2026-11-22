"""What approving a schedule would put on the main site, and the checks behind it. Pure: reads no files and no clock."""
from exams import approval as _approval
from exams import days as _days
from exams import invigilate as _inv
from exams import make as _make
from exams import papers as _papers
from exams import schedules as _schedules
from exams import seating as _seating


def _span(a, b) -> str:
    return "%s–%s" % (_days.hhmm(a), _days.hhmm(b))


def _what(pub, cal, s) -> dict:
    model = pub["model"]
    made = s.get("made") or {}
    duties = made.get("duties") or []
    dts = [e for e in _days.dates(s, cal, model) if e["day"] is not None]
    inside = set()
    for e in dts:
        inside.update(_days.day_view(pub, cal, s, e["date"])["window"])
    count = {}
    for d in duties:
        for n in d.get("names") or []:
            count[n] = count.get(n, 0) + 1
    most = min(count.items(), key=lambda x: (-x[1], x[0])) if count else None
    venues = {}
    for d in duties:
        v = venues.setdefault(d["room"], dict(room=d["room"], dates=set(), start=d["start"], end=d["end"]))
        v["dates"].add(d["date"])
        v["start"], v["end"] = min(v["start"], d["start"]), max(v["end"], d["end"])
    entry = lambda date: (s.get("days") or {}).get(date) or {}
    return dict(classes=[c["name"] for c in model.get("classes") or [] if c["name"] in inside],
                levels=_days.levels_of(s, model), start=s.get("start"), end=s.get("end"),
                days=[dict(date=e["date"], whole=bool(entry(e["date"]).get("whole", True)),
                           window=[_days.hhmm(e["start"]), _days.hhmm(e["end"])]) for e in dts],
                papers=len(s.get("papers") or []), stopped=len(_make.lesson_lists(pub, cal, s)["none"]),
                teachers=len(count), duties=len(duties), most=list(most) if most else None,
                backups=sum(len(d.get("backup") or {}) for d in duties),
                venues=[dict(room=r, dates=len(v["dates"]), start=_days.hhmm(v["start"]), end=_days.hhmm(v["end"]))
                        for r, v in sorted(venues.items())],
                anyway=[dict(key=x[0], room=x[1]) for x in s.get("use_anyway") or [] if x and len(x) > 1])


def _papers_check(model, cal, s, xset) -> dict:
    errors = _papers.check(s, model, cal, xset["rules"])["errors"]
    return dict(key="papers", ok=not errors,
                lines=errors or ["No student has two papers at once, and every paper is on an exam day."])


def _seats_check(s, model) -> dict:
    """students with no seat: the unseated ones, and anyone who sits a made sitting now but is in neither its seats nor its
    unseated list (a student who joined after the sitting was made)"""
    made = s.get("made") or {}
    seats, unseated = made.get("seats") or {}, made.get("unseated") or {}
    none = {sid for v in unseated.values() for sid in v}
    for sit in _seating.sittings(s):
        if sit["key"] in seats or sit["key"] in unseated:
            none |= set(_seating.sitting_students(sit, s, model)) - _make.placed(made, sit["key"])
    n = len(none)
    if not n:
        return dict(key="seats", ok=True, lines=["Every student has a seat."])
    return dict(key="seats", ok=False, lines=["1 student has no seat." if n == 1 else "%d students have no seat." % n])


def _free_check(pub, cal, s, xset, elsewhere) -> dict:
    duties = (s.get("made") or {}).get("duties") or []
    views, lines, short = {}, [], []
    for d in duties:
        view = views.get(d["date"]) or views.setdefault(d["date"], _days.day_view(pub, cal, s, d["date"]))
        where = "%s on %s %s" % (d["room"], _days.nice(d["date"]), _span(d["start"], d["end"]))
        backup = d.get("backup") or {}
        for n in d.get("names") or []:
            why, running = _inv._free(n, view, d["start"], d["end"], duties, xset, skip=d, elsewhere=elsewhere)
            if not why:
                run = [l for l in running if l["row"] not in (backup.get(n) or [])]
                why = "; ".join("teaches %s %s %s" % (", ".join(l["classes"]), l["subject"], _span(l["start"], l["end"])) for l in run)
            if why:
                lines.append("%s, %s: %s." % (n, where, why))
        if d.get("short"):
            short.append("%s is short by %d." % (where, d["short"]))
    lines += short + _make.gone_now(pub, s)
    return dict(key="free", ok=not lines, lines=lines or ["Every invigilator is free then."])


def _others_check(s, elsewhere, model) -> dict:
    """another schedule's invigilators and rooms at the same time; a combined venue and its own rooms are one room"""
    parts = model.get("room_parts") or {}
    duties = (s.get("made") or {}).get("duties") or []
    takes, uses, shares = [], [], []
    elsewhere = [b for b in elsewhere if b.get("kind") != "relief"]
    for other in sorted({(b["name"], b["status"]) for b in elsewhere}):
        mine = [b for b in elsewhere if (b["name"], b["status"]) == other]
        for date in sorted({b["date"] for b in mine}):
            names, rooms = set(), []
            for b in (b for b in mine if b["date"] == date):
                for d in (d for d in duties if d["date"] == date and d["start"] < b["end"] and d["end"] > b["start"]):
                    names |= set(b["names"]) & set(d["names"])
                    if b["room"] in _seating._related(d["room"], parts) and b["room"] not in rooms:
                        rooms.append(b["room"])
            tag = "%s (%s)" % other
            if names:
                takes.append("%s takes %d of these invigilators on %s." % (tag, len(names), _days.nice(date)))
            uses += ["%s uses %s on %s too." % (tag, r, _days.nice(date)) for r in rooms]
            for b in (b for b in mine if b["date"] == date and b.get("classes")):
                line = _schedules.shared_line(model, s, tag, date, b["start"], b["end"], b["classes"])
                if line and line not in shares:
                    shares.append(line)
    lines = takes + uses + shares
    return dict(key="others", ok=not lines, lines=lines or ["No clash with other schedules."])


def _timetable_check(pub, s) -> dict:
    now = _make.published_at(pub)
    if (s.get("made") or {}).get("published_at") == now:
        return dict(key="timetable", ok=True, lines=["Made from the timetable on the main site now."])
    when = " on %s" % _days.nice(now) if now else ""
    return dict(key="timetable", ok=False, lines=["The timetable changed since this was made: a new timetable was published%s. "
                                                   "Ask the exams committee to make it again." % when])


def review(pub, cal, sched, xset, elsewhere) -> dict:
    """what the timetable committee sees before approving: the copy reviewed (the approved one when the schedule is approved,
    else the working copy), a summary, five checks, the change list and the replacements done without a new approval"""
    ap = _approval.as_schedule(sched) if sched.get("status") == "approved" else None
    s = ap or sched
    model = pub["model"]
    checks = [_papers_check(model, cal, s, xset), _seats_check(s, model), _free_check(pub, cal, s, xset, elsewhere),
              _others_check(s, elsewhere, model), _timetable_check(pub, s)]
    return dict(copy="approved" if ap else "working", what=_what(pub, cal, s), checks=checks,
                changes=_approval.changes(sched, model) if sched.get("status") == "changes" else [],
                done_without=_approval.done_without(sched))

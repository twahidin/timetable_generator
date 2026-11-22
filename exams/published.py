"""What the main site shows of exams: read only from the approved copies (schedules.on_site()). Pure: reads no files.

Every function takes `scheds`, the approved copies. What a student code may see is cut here, not in the routes: with
full=False there are no teacher names, duty rooms, roster or prints, and a class's room leaves out students with an
access arrangement of their own room, a reader or a scribe.
"""
import datetime as _datetime

from exams import approval as _approval
from exams import days as _days
from exams import papers as _papers
from exams import printouts as _printouts
from exams import seating as _seating

PRINTS = ("seating", "roster-day", "roster-teacher", "timetable")
SEP = " · "


def pos(bnds, m) -> float:
    """period position: the period's number plus the fraction of it gone, 0..len(bnds), to 3 places"""
    if not bnds or m <= bnds[0][0]:
        return 0.0
    for i, (a, b) in enumerate(bnds):
        if m < a:
            return round(float(i), 3)
        if m < b:
            return round(i + (m - a) / (b - a), 3)
    return round(float(len(bnds)), 3)


def _order(scheds):
    return sorted(scheds, key=lambda s: (s.get("start") or "", s.get("name") or ""))


def _active(scheds, today):
    return [s for s in _order(scheds) if today.isoformat() <= _approval.last_date(s)]


def _counts(s, date):
    return s["start"] <= date <= s["end"] or any(p.get("date") == date for p in s.get("papers") or [])


def _made(s):
    return s.get("made") or {}


def _papers_at(s):
    """{sitting key: [paper]} of the made sittings, in paper order"""
    by_id = {p["id"]: p for p in s.get("papers") or []}
    return {x["key"]: [by_id[i] for i in x["papers"] if i in by_id] for x in _seating.sittings(s)}


def _label(ps):
    return SEP.join(_papers.label(p) for p in ps)


def _hm(m):
    return _days.hhmm(m)


def _seat_of(s, key):
    """{student id: (room, seat)} of one sitting"""
    return {sid: (room, seat) for room, rows in (_made(s).get("seats") or {}).get(key, {}).items() for sid, seat in rows}


def _class_items(pub, s, date, bnds):
    model = pub["model"]
    cls = {x["id"]: x.get("cls") for x in model.get("students") or []}
    access = {a["student"]: a for a in s.get("access") or [] if isinstance(a, dict) and a.get("student")}
    held = _papers_at(s)
    out = {}
    for sit in _seating.sittings(s):
        if sit["date"] != date:
            continue
        ps = [p for p in held.get(sit["key"], []) if p.get("who") in ("level", "groups")]
        sat = _seat_of(s, sit["key"])
        by_class = {}
        for p in ps:
            for sid in _papers.who_sits(p, model):
                by_class.setdefault(cls.get(sid), {}).setdefault(p["id"], []).append(sid)
        for c, mine in by_class.items():
            if not c:
                continue
            chosen = [p for p in ps if p["id"] in mine]
            end = max(sit["start"] + p["minutes"] for p in chosen)
            rooms = {}
            for sid in {x for v in mine.values() for x in v}:
                a = access.get(sid) or {}
                if a.get("own_room") or a.get("reader") or a.get("scribe") or sid not in sat:
                    continue
                rooms[sat[sid][0]] = rooms.get(sat[sid][0], 0) + 1
            order = sorted(rooms, key=lambda r: (-rooms[r], r))
            others = sorted(order[1:])
            out.setdefault(c, []).append(dict(
                start=_hm(sit["start"]), end=_hm(end), label=_label(chosen), room=order[0] if order else "",
                seat_note="also " + ", ".join(others) if others else "", exam=s["name"],
                p=pos(bnds, sit["start"]), n=round(pos(bnds, end) - pos(bnds, sit["start"]), 3)))
    return out


def _all_duties(s):
    held = _papers_at(s)
    for d in _made(s).get("duties") or []:
        yield d, held.get(d["key"], [])


def _duties_on(s, date):
    return ((d, ps) for d, ps in _all_duties(s) if d["date"] == date)


def day(pub, cal, scheds, date, full) -> dict:
    model = pub["model"]
    bnds = _days.bounds(model)
    counted = [s for s in _order(scheds) if _counts(s, date)]
    merged = _days.merged_view(pub, cal, counted, date)
    empty = dict(classes={}, stopped=[], shortened=[], teachers={}, rooms={}, banner="")
    if merged["day"] is None:
        return dict(date=date, day=None, exams=empty)
    stopped, shortened = [], []
    for r in merged["lessons"]:
        if r["stopped"]:
            stopped.append(r["row"])
            shortened += [[r["row"], _hm(a), _hm(b)] for a, b in r["running"]]
    classes, teachers, rooms = {}, {}, {}
    for s in counted:
        for c, items in _class_items(pub, s, date, bnds).items():
            classes.setdefault(c, []).extend(items)
        if not full:
            continue
        for d, ps in _duties_on(s, date):
            lab = _label(ps)
            span = dict(start=_hm(d["start"]), end=_hm(d["end"]), label=lab)
            pn = dict(p=pos(bnds, d["start"]), n=round(pos(bnds, d["end"]) - pos(bnds, d["start"]), 3))
            rooms.setdefault(d["room"], []).append(dict(span, exam=s["name"], **pn))
            for n in d.get("names") or []:
                teachers.setdefault(n, []).append(dict(span, room=d["room"], role="Chief invigilator" if d.get("chief") == n else "Invigilate",
                                                       exam=s["name"], **pn))
    for lst in list(classes.values()) + list(teachers.values()) + list(rooms.values()):
        lst.sort(key=lambda x: x["start"])
    exams = dict(classes=classes, stopped=stopped, shortened=shortened, teachers=teachers, rooms=rooms,
                 banner=SEP.join(s["name"] for s in counted))
    return dict(date=date, day=merged["day"], exams=exams)


def _banner(shown, today):
    parts = []
    for s in shown:
        if (_days._date(s["start"]) - today).days <= 7:
            span = _days.nice(s["start"]) if s["start"] == s["end"] else "%s–%s" % (_days.nice(s["start"]), _days.nice(s["end"]))
            parts.append("%s: %s." % (s["name"], span))
    return " ".join(parts) or None


def listing(pub, scheds, today, full) -> dict:
    shown = _active(scheds, today)
    rows = []
    for s in shown:
        levels = {}
        for p in sorted(s.get("papers") or [], key=lambda p: (p.get("date") or "", p.get("start") or "")):
            if p.get("who") in ("level", "groups") and p.get("date") and p.get("start"):
                a = _days.minutes(p["start"])
                levels.setdefault(p["level"], []).append(dict(date=p["date"], start=_hm(a), end=_hm(a + p["minutes"]), label=_papers.label(p)))
        row = dict(id=s["id"], name=s["name"], kind=s.get("kind"), start=s["start"], end=s["end"], levels=levels)
        if full:
            held = _papers_at(s)
            row["roster"] = [dict(date=d["date"], start=_hm(d["start"]), end=_hm(d["end"]), room=d["room"], label=_label(held.get(d["key"], [])),
                                  names=list(d.get("names") or []), chief=d.get("chief"))
                             for d in sorted(_made(s).get("duties") or [], key=lambda d: (d["date"], d["start"], d["room"]))]
            row["prints"] = [[_printouts.TITLES[w], "/api/published/exams/%s/print/%s.pdf" % (s["id"], w)] for w in PRINTS]
        rows.append(row)
    return dict(schedules=rows, banner=_banner(shown, today))


def my_duties(pub, cal, scheds, name, today) -> dict:
    """a teacher's duties on the approved copies, and the lessons of theirs that don't happen on those exams' dates (with
    or without a duty)"""
    out, dates = [], set()
    for s in _active(scheds, today):
        d0, d1 = _days._date(s["start"]), _days._date(s["end"])
        while d0 <= d1:
            dates.add(d0.isoformat())
            d0 += _datetime.timedelta(days=1)
        mine = [(d, ps) for d, ps in _all_duties(s) if name in (d.get("names") or [])]
        if not mine:
            continue
        mine.sort(key=lambda x: (x[0]["date"], x[0]["start"], x[0]["room"]))
        rows = []
        for d, ps in mine:
            seated = ((_made(s).get("seats") or {}).get(d["key"]) or {}).get(d["room"]) or []
            chief = d.get("chief")
            rows.append(dict(date=d["date"], start=_hm(d["start"]), end=_hm(d["end"]), room=d["room"], label=_label(ps), students=len(seated),
                             others=[n for n in d.get("names") or [] if n != name], chief=chief if chief and chief != name else None,
                             role="Chief invigilator" if chief == name else "Invigilate"))
        out.append(dict(id=s["id"], name=s["name"], scripts=s.get("scripts") or "", minutes=sum(d["end"] - d["start"] for d, _ in mine), duties=rows))
    lessons = []
    for iso in sorted(dates):
        for r in _days.merged_view(pub, cal, scheds, iso)["lessons"]:
            if name in r["teachers"]:
                lessons += [dict(date=iso, start=_hm(a), end=_hm(b), classes=list(r["classes"]), subject=r["subject"]) for a, b in r["stopped"]]
    lessons.sort(key=lambda x: (x["date"], x["start"]))
    return dict(schedules=out, lessons=lessons)


def my_exams(pub, cal, scheds, sid, today) -> dict:
    model = pub["model"]
    bnds = _days.bounds(model)
    out = []
    for s in _active(scheds, today):
        access = {a["student"]: a for a in s.get("access") or [] if isinstance(a, dict) and a.get("student")}
        mine = [p for p in s.get("papers") or [] if p.get("date") and p.get("start") and sid in _papers.who_sits(p, model)]
        if not mine:
            continue
        mine.sort(key=lambda p: (p["date"], _days.minutes(p["start"])))
        seats = {}
        rows = []
        last = {}
        for i, p in enumerate(mine):
            last[p["date"]] = i
        first = {}
        for i, p in enumerate(mine):
            first.setdefault(p["date"], i)
        for i, p in enumerate(mine):
            key = "%s %s" % (p["date"], _days.hhmm(_days.minutes(p["start"])))
            if key not in seats:
                seats[key] = _seat_of(s, key)
            room, seat = seats[key].get(sid, ("", ""))
            w0, w1 = _days._window(s, p["date"], bnds) if bnds else (0, 0)
            rep = (s.get("times") or {}).get("report")
            rows.append(dict(date=p["date"], report=rep if first[p["date"]] == i and bnds and w0 == bnds[0][0] else None,
                             start=_hm(_days.minutes(p["start"])), end=_hm(_papers.ends(p, sid, access)), label=_papers.label(p), room=room,
                             seat=seat, note="then lessons from %s" % _hm(w1) if last[p["date"]] == i and bnds and w1 < bnds[-1][1] else ""))
        out.append(dict(id=s["id"], name=s["name"], papers=rows))
    return dict(schedules=out)

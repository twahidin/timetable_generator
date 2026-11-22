"""Invigilators: how many a room needs, who is free, and who is put on each duty. Reads the saved schedules only for minutes."""
import math

from accounts import people as _accounts
from exams import days as _days
from exams import schedules as _schedules
from exams import seating as _seating


def need(room, n, aa_rows, xrules) -> int:
    """places for a room: room is a dict with hall and access; aa_rows are the access arrangements of the students seated there"""
    if not n:
        return 0
    if room.get("hall"):
        return math.ceil(n / xrules["hall_per"]) + (1 if xrules["hall_chief"] else 0)
    if room.get("access"):
        return 1 + sum(1 for a in aa_rows if a and (a.get("reader") or a.get("scribe")))
    return xrules["per_classroom"]


def duty_minutes(duties) -> dict:
    out = {}
    for d in duties:
        for n in d.get("names") or []:
            out[n] = out.get(n, 0) + d["end"] - d["start"]
    return out


def _other_minutes(sched, year) -> dict:
    """minutes per name in the other saved schedules, for duties dated in the same calendar year"""
    out = {}
    for s in _schedules.all_saved():
        if s["id"] == sched.get("id") or not s.get("made"):
            continue
        for d in s["made"].get("duties") or []:
            if str(d.get("date", ""))[:4] != year:
                continue
            for n in d.get("names") or []:
                out[n] = out.get(n, 0) + d["end"] - d["start"]
    return out


def _hit(spans, start, end):
    return any(a < end and b > start for a, b in spans)


def _classes(rows):
    out = []
    for r in rows:
        for c in r["classes"]:
            if c not in out:
                out.append(c)
    return ", ".join(out)


def _free(name, view, start, end, duties, xset, skip=None, elsewhere=()):
    """'free then' for one person from start to end on the view's date: (why not, "" when free; the lessons they teach then
    that still run). The one check behind the candidates, the names chosen by hand and the lesson teachers of a test.
    duties: the duties already made (any date); skip: the duty being filled."""
    rules = xset["rules"]
    if name in xset["never"]:
        return "is on the never list", []
    if _hit(view["blocked"].get(name, ()), start, end):
        return "is not available then (a Must rule)", []
    on_date = [d for d in duties if d is not skip and d["date"] == view["date"]]
    clash = next((d for d in on_date if name in d["names"] and d["start"] < end and d["end"] > start), None)
    if clash:
        return "is on another duty then (%s)" % clash["room"], []
    busy = next((b for b in elsewhere if name in b["names"] and b["date"] == view["date"] and b["start"] < end and b["end"] > start), None)
    if busy:
        return "is on %s then (%s)" % (busy["name"], busy["room"]), []
    most = rules.get("max_per_day")
    if most and sum(1 for d in on_date if name in d["names"]) >= most:
        return "has %d %s that day already" % (most, "duty" if most == 1 else "duties"), []
    return "", [l for l in view["lessons"] if name in l["teachers"] and _hit(l["running"], start, end)]


def _teaches(running):
    return "; ".join("teaches %s %s %s–%s: needs a backup" % (", ".join(l["classes"]), l["subject"], _days.hhmm(l["start"]),
                                                             _days.hhmm(l["end"])) for l in running)


def _taught(model) -> dict:
    out = {}
    for l in model.get("lessons") or []:
        for n in l.get("teachers") or []:
            out.setdefault(n, set()).add(l["subject"])
    return out


def _barred(name, running, subjects, taught, xset) -> bool:
    """left out whoever the rules keep off a paper: someone who teaches its subject (when that rule is on), and a backup
    invigilator whose lesson still runs. The one filter behind the candidates and the approved names kept by Make."""
    if xset["rules"].get("not_own_subject") and set(subjects) & taught.get(name, set()):
        return True
    return bool(running) and name in xset["backups"]


def candidates(pub, cal, sched, xset, date, start, end, duties, subjects=(), exclude=(), _other=None, elsewhere=()) -> dict:
    model = pub["model"]
    rules = xset["rules"]
    pool = [p["name"] for p in _accounts.staff(pub)
            if p["teaches"] or p["name"] in xset["backups"]]
    view = _days.day_view(pub, cal, sched, date)
    mine = duty_minutes(duties)
    other = _other if _other is not None else _other_minutes(sched, date[:4])
    subjects = set(subjects)
    taught = _taught(model)
    groups = dict(freed=[], free=[], backups=[], need_backup=[])
    for name in pool:
        if name in exclude:
            continue
        why, running = _free(name, view, start, end, duties, xset, elsewhere=elsewhere)
        if why:
            continue
        if _barred(name, running, subjects, taught, xset):
            continue
        stopped = [l for l in view["lessons"] if name in l["teachers"] and _hit(l["stopped"], start, end)]
        c = dict(name=name, minutes=mine.get(name, 0), other=other.get(name, 0), reason="", rows=[])
        if running:
            c["rows"] = [l["row"] for l in running]
            c["reason"] = _teaches(running)
            groups["need_backup"].append(c)
        elif name in xset["backups"]:
            c["reason"] = "backup invigilator"
            groups["backups"].append(c)
        elif stopped:
            c["reason"] = "freed: %s on the exam then" % _classes(stopped)
            groups["freed"].append(c)
        else:
            c["reason"] = "free then"
            groups["free"].append(c)
    for k, rows in groups.items():
        rows.sort(key=lambda c: (c["minutes"], c["other"], c["name"]))
        for c in rows:
            c.pop("other")
    return groups


def _lesson_teachers(model, view, sit, duties, ids_of, students, every, xset, elsewhere=()):
    """a common test supervised by the lesson teachers: each teacher of a lesson stopped at the start supervises one ordinary
    classroom of the sitting (not a hall, not an access room), the one holding most of that lesson's students, else the
    lesson's own room; a teacher already used or not free for the duty time is left out. Rooms left without one are
    filled by the normal picks."""
    rooms = [d for d in duties if not d["locked"] and not (xset["rooms"].get(d["room"]) or {}).get("hall")
             and not (xset["rooms"].get(d["room"]) or {}).get("access")]
    if not rooms:
        return
    groups_of = {x["id"]: x.get("groups") or [] for x in model.get("students") or []}
    classes = {students[sid]["cls"] for d in duties for sid in ids_of[id(d)]}
    lessons = model.get("lessons") or []
    for l in view["lessons"]:
        if not (set(l["classes"]) & classes and _hit(l["stopped"], sit["start"], sit["start"] + 1)):
            continue
        group = (lessons[l["row"]] if l["row"] < len(lessons) else {}).get("group")
        mine = {sid for sid in students if students[sid]["cls"] in l["classes"]
                and (group == "Entire Class" or group in groups_of.get(sid, []))}
        for n in l["teachers"]:
            count = {id(d): len(mine & set(ids_of[id(d)])) for d in rooms}
            best = sorted(rooms, key=lambda d: (-count[id(d)], len(d["names"]), d["room"] != l["room"], d["room"]))
            d = best[0] if count[id(best[0])] else next((x for x in rooms if x["room"] == l["room"]), None)
            if d is None:
                continue
            why, running = _free(n, view, d["start"], d["end"], every, xset, skip=d, elsewhere=elsewhere)
            if why or running or n in d["names"]:
                continue
            d["names"].append(n)
            d["reasons"][n] = "supervises their own lesson"
    for d in rooms:
        if d["names"]:
            d["need"] = len(d["names"])


def _check_names(duties, every, views, xset, elsewhere, hand_only):
    """each name is 'free then' or not: a not_free reason, or a backup when their lesson runs (a name chosen by hand also has
    that said in its reason). hand_only: only the names chosen by hand (assign); else every name, from scratch (recheck)."""
    for d in duties:
        if not hand_only:
            d["not_free"], d["backup"] = {}, {}
        for n in d["names"]:
            hand = d["reasons"].get(n) == "chosen by hand"
            if hand_only and not hand:
                continue
            why, running = _free(n, views[d["key"]], d["start"], d["end"], every, xset, skip=d, elsewhere=elsewhere)
            if why:
                d["not_free"][n] = why
            elif running:
                d["backup"][n] = [l["row"] for l in running]
                if hand:
                    d["reasons"][n] = "chosen by hand; " + _teaches(running)


def recheck(pub, cal, sched, xset, duties, every, elsewhere=()) -> None:
    """kept duties: not_free and backup worked out again for every name (as assign does for names chosen by hand), against the
    timetable, the rules and the other schedules as they are now; reasons are kept"""
    views = {}
    for d in duties:
        if d["date"] not in views:
            views[d["date"]] = _days.day_view(pub, cal, sched, d["date"])
    _check_names(duties, every, {d["key"]: views[d["date"]] for d in duties}, xset, elsewhere, hand_only=False)


def assign(pub, cal, sched, xset, seats_by_key, refill=None, fixed=(), elsewhere=(), prefer=None) -> list:
    """the duties of the sittings in seats_by_key, filled. A hand-set duty (a pin) keeps exactly its pinned names and is filled
    only up to the number of its names that left the timetable: refill[pin key] (dropped before) plus pinned names that are
    no longer people; each name chosen by hand is checked as 'free then' (a backup when their lesson runs, else a not_free
    reason). `fixed` duties (sittings kept as they are) are returned unchanged and count as other duties. `prefer`
    {pin key: names}: names an unpinned duty keeps (the approved ones) when still free then, before anyone else is picked."""
    model = pub["model"]
    rules = xset["rules"]
    people = {p["name"] for p in _accounts.staff(pub)}
    pins = (sched.get("pins") or {}).get("duties") or {}
    common = sched.get("supervision") == "lesson"
    duties, subjects_of, places, views, ids_of, by_sit = [], {}, {}, {}, {}, []
    papers = {p["id"]: p for p in sched.get("papers") or []}
    for sit in _seating.sittings(sched):
        if sit["key"] not in (seats_by_key or {}):
            continue
        seated = seats_by_key[sit["key"]] or {}
        students = _seating.sitting_students(sit, sched, model)
        subjects_of[sit["key"]] = [papers[i]["subject"] for i in sit["papers"] if i in papers]
        view = views[sit["key"]] = _days.day_view(pub, cal, sched, sit["date"])
        mine = []
        for room, seats in seated.items():
            ids = [sid for sid, _ in seats if sid in students]
            if not ids:
                continue
            end = max(students[s]["end"] for s in ids) + rules["stay"]
            room_set = xset["rooms"].get(room) or {}
            n_need = need(room_set, len(ids), [students[s].get("aa") for s in ids], rules)
            duty = dict(key=sit["key"], room=room, date=sit["date"], start=sit["start"] - rules["arrive"], end=end, need=n_need,
                        names=[], chief=None, reasons={}, backup={}, not_free={}, short=0, locked=False)
            ids_of[id(duty)] = ids
            pk = "%s|%s" % (sit["key"], room)
            pin = pins.get(pk)
            if pin is not None:
                duty["locked"] = True
                for n in pin:
                    if n in people and n not in duty["names"]:
                        duty["names"].append(n)
                        duty["reasons"][n] = "chosen by hand"
                places[id(duty)] = (refill or {}).get(pk, 0) + sum(1 for n in pin if n not in people)
            duties.append(duty)
            mine.append(duty)
        by_sit.append((sit, students, mine))
    every = duties + list(fixed)
    if common:
        for sit, students, mine in by_sit:
            _lesson_teachers(model, views[sit["key"]], sit, mine, ids_of, students, every, xset, elsewhere)
    duties.sort(key=lambda d: (d["date"], d["start"], d["room"]))
    other, taught = {}, _taught(model)
    for d in duties:
        year = d["date"][:4]
        if year not in other:
            other[year] = _other_minutes(sched, year)
        if not d["locked"] and prefer:
            for n in (prefer.get("%s|%s" % (d["key"], d["room"])) or []):
                if len(d["names"]) >= d["need"] or n in d["names"] or n not in people:
                    continue
                why, running = _free(n, views[d["key"]], d["start"], d["end"], every, xset, skip=d, elsewhere=elsewhere)
                if why or _barred(n, running, subjects_of[d["key"]], taught, xset):
                    continue
                d["names"].append(n)
                d["reasons"][n] = "as approved" + ("; " + _teaches(running) if running else "")
                if running:
                    d["backup"][n] = [l["row"] for l in running]
        left = d["need"] - len(d["names"])
        if d["locked"]:
            left = min(left, places.get(id(d), 0))
        if left > 0 and not (common and not d["locked"] and d["names"]):
            others = [x for x in every if x is not d]
            hall = (xset["rooms"].get(d["room"]) or {}).get("hall")
            got = candidates(pub, cal, sched, xset, d["date"], d["start"], d["end"], others, subjects_of[d["key"]],
                             exclude=d["names"], _other=other[year], elsewhere=elsewhere)
            order = [(group, c) for group in ("freed", "free", "backups", "need_backup") for c in got[group]]
            if hall and not any(n in xset["chiefs"] for n in d["names"]):   # a hall: a free chief invigilator first, if any
                chief = next(((g, c) for g, c in order if c["name"] in xset["chiefs"] and g != "need_backup"), None)
                if chief:
                    order.remove(chief)
                    order.insert(0, chief)
            for group, c in order:
                if left <= 0:
                    break
                d["names"].append(c["name"])
                d["reasons"][c["name"]] = c["reason"]
                if group == "need_backup":
                    d["backup"][c["name"]] = c["rows"]
                left -= 1
        d["short"] = max(0, d["need"] - len(d["names"]))
        if (xset["rooms"].get(d["room"]) or {}).get("hall") and d["names"]:
            d["chief"] = next((n for n in xset["chiefs"] if n in d["names"]), d["names"][0])
    _check_names(duties, every, views, xset, elsewhere, hand_only=True)
    return sorted(every, key=lambda d: (d["date"], d["start"], d["room"]))

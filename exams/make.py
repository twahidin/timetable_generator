"""Make an exam schedule's seats and duties, keep hand changes, and the figures the pages show."""
import copy
import datetime
import hashlib
import json

import relief.people
import relief.settings
from exams import approval as _approval
from exams import days as _days
from exams import invigilate as _inv
from exams import papers as _papers
from exams import schedules as _schedules
from exams import seating as _seat


STALE = _approval.STALE
_USED = ("papers", "days", "levels", "classes", "start", "end", "access", "seating", "supervision")


def _now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def published_at(pub):
    """when the published timetable was published (None for a sample); the one reading behind made and the review"""
    return (pub.get("meta") or {}).get("published_at")


def fingerprint(sched, xset) -> str:
    """what Make uses (papers, days, levels and classes, access arrangements, seating, supervision, the exam rooms), as a
    short hash kept in made: a change to any of it makes the made seats and duties stale"""
    used = {k: sched.get(k) for k in _USED}
    used["rooms"] = xset.get("rooms")
    return hashlib.sha256(json.dumps(used, sort_keys=True, default=str).encode()).hexdigest()[:16]


def stale(sched, xset) -> bool:
    """the schedule was made, and what Make used has changed since"""
    made = sched.get("made")
    return bool(made) and made.get("fingerprint") != fingerprint(sched, xset)


def sitting_fp(sched, key, xset) -> str:
    """a hash of what one sitting is made from: its papers, access arrangements, seating, supervision, levels and classes, the
    day's entry, the exam rooms, and the pins and 'use anyway' pairs of the sitting"""
    sit = next((x for x in _seat.sittings(sched) if x["key"] == key), None)
    ids = set(sit["papers"]) if sit else set()
    pins = sched.get("pins") or {}
    used = dict(papers=sorted((p for p in sched.get("papers") or [] if p.get("id") in ids), key=lambda p: p["id"]),
                access=sched.get("access"), seating=sched.get("seating"), supervision=sched.get("supervision"),
                levels=sched.get("levels"), classes=sched.get("classes"), day=(sched.get("days") or {}).get(key[:10]),
                rooms=xset.get("rooms"), pin_rooms=(pins.get("rooms") or {}).get(key),
                pin_duties={k: v for k, v in sorted((pins.get("duties") or {}).items()) if _split(k)[0] == key},
                anyway=sorted(list(x) for x in sched.get("use_anyway") or [] if x and x[0] == key))
    return hashlib.sha256(json.dumps(used, sort_keys=True, default=str).encode()).hexdigest()[:16]


def _split(k):
    key, _, room = k.rpartition("|")
    return key, room


def _gone(pub, sched, model, keys=None):
    """sentences for pinned students and invigilators no longer there, and per pinned duty how many names were dropped
    {pin key: n}; those pins are dropped. With keys, only the pins of those sittings (the others are kept as they are)."""
    known_s = {s["id"] for s in model.get("students") or []}
    known_p = {p["name"] for p in relief.people.people(pub, relief.settings.load(pub)["extra_staff"])}
    pins = sched.setdefault("pins", dict(rooms={}, duties={}))
    pins.setdefault("rooms", {})
    pins.setdefault("duties", {})
    out, dropped = [], {}
    for key, by in list(pins["rooms"].items()):
        if keys is not None and key not in keys:
            continue
        for sid in list(by):
            if sid not in known_s:
                s = "%s is no longer on the timetable." % sid
                if s not in out:
                    out.append(s)
                del by[sid]
        if not by:
            del pins["rooms"][key]
    for pk, names in list(pins["duties"].items()):
        if keys is not None and _split(pk)[0] not in keys:
            continue
        keep = []
        for n in names:
            if n in known_p:
                keep.append(n)
            else:
                s = "%s is no longer on the timetable." % n
                if s not in out:
                    out.append(s)
        if len(keep) != len(names):
            dropped[pk] = len(names) - len(keep)
            if keep:
                pins["duties"][pk] = keep
            else:
                del pins["duties"][pk]
    return out, dropped


def gone_now(pub, sched) -> list:
    """sentences, once each, for everyone the schedule names who is no longer on the published timetable: pinned students
    and invigilators, and the invigilators and students of the made duties and seats (picked by hand or by the app)"""
    model = pub["model"]
    known_s = {s["id"] for s in model.get("students") or []}
    known_p = {p["name"] for p in relief.people.people(pub, relief.settings.load(pub)["extra_staff"])}
    pins = sched.get("pins") or {}
    made = sched.get("made") or {}
    out = []

    def say(x):
        s = "%s is no longer on the timetable." % x
        if s not in out:
            out.append(s)
    for by in (pins.get("rooms") or {}).values():
        for sid in by:
            if sid not in known_s:
                say(sid)
    for names in (pins.get("duties") or {}).values():
        for n in names:
            if n not in known_p:
                say(n)
    for d in made.get("duties") or []:
        for n in d.get("names") or []:
            if n not in known_p:
                say(n)
    for rooms in (made.get("seats") or {}).values():
        for rows in rooms.values():
            for sid, _ in rows:
                if sid not in known_s:
                    say(sid)
    return out


def _span(sit, students, rules, duties):
    mine = [d for d in duties if d["key"] == sit["key"]]
    if mine:
        return min(d["start"] for d in mine), max(d["end"] for d in mine)
    ends = [s["end"] for s in students.values()]
    return sit["start"] - rules["arrive"], (max(ends) if ends else sit["start"]) + rules["stay"]


def _spans(pub, sched, xset, duties, seats):
    """(sitting, start, end, rooms) of every sitting: from its duties when it has them, else its students' times"""
    out = []
    for sit in _seat.sittings(sched):
        lo, hi = _span(sit, _seat.sitting_students(sit, sched, pub["model"]), xset["rules"], duties)
        out.append((sit, lo, hi, set((seats or {}).get(sit["key"]) or {})))
    return out


def _held(spans, sit, lo, hi):
    return {r for s2, a, b, rooms in spans if s2["key"] != sit["key"] and s2["date"] == sit["date"] and a < hi and b > lo for r in rooms}


def held(pub, sched, xset) -> dict:
    """{sitting key: the rooms other sittings of the made schedule seat students in while it runs}"""
    made = sched.get("made") or {}
    spans = _spans(pub, sched, xset, made.get("duties") or [], made.get("seats") or {})
    return {sit["key"]: _held(spans, sit, lo, hi) for sit, lo, hi, _ in spans}


def make(pub, cal, sched, xset, only=None, elsewhere=None) -> dict:
    """seats and duties for every sitting; with only (a sitting key), that sitting (and any sitting not made before) is made
    again and the others are kept as they were. A full Make of a schedule with an approved copy keeps every sitting whose
    own inputs are as approved exactly as approved (seats, duties); a changed sitting is made again, its rooms keeping their
    approved invigilators where those are still free then. elsewhere: the other schedules' duties (None: read them)."""
    model = pub["model"]
    if elsewhere is None:
        elsewhere = _schedules.elsewhere(sched.get("id"))
    old = sched.get("made") or {}
    sits = _seat.sittings(sched)
    keys = {s["key"] for s in sits}
    src, prefer, same = old, {}, set()
    ap = None if only else _approval.as_schedule(sched)
    if ap and (ap.get("made") or {}).get("seats"):
        src = ap["made"]
        same = {k for k in src["seats"] if k in keys and sitting_fp(sched, k, xset) == sitting_fp(ap, k, xset)}
        prefer = {"%s|%s" % (d["key"], d["room"]): list(d["names"]) for d in src.get("duties") or [] if d["key"] not in same}
    keep = keys if only else same   # the sittings that may be kept as they were
    keep_seats = {k: copy.deepcopy(v) for k, v in (src.get("seats") or {}).items() if k in keep} if (only or same) else {}
    old_duties = [copy.deepcopy(d) for d in src.get("duties") or [] if d["key"] in keep_seats] if (only or same) else []
    redo = ({only} | (keys - set(keep_seats))) if only else keys - same
    gone, dropped = _gone(pub, sched, model, redo if only else None)
    pins = sched["pins"]
    seats, unseated, used = {}, {}, []
    kept = [x for x in _spans(pub, sched, xset, old_duties, keep_seats) if x[0]["key"] not in redo]   # earlier and later
    for sit in sits:
        key = sit["key"]
        students = _seat.sitting_students(sit, sched, model)
        if key in redo:
            lo, hi = _span(sit, students, xset["rules"], [])
        else:
            lo, hi = _span(sit, students, xset["rules"], old_duties)
        if key in redo:
            taken = {r for d, a, b, rooms in used if d == sit["date"] and a < hi and b > lo for r in rooms} | _held(kept, sit, lo, hi)
            free = [r for r in _seat.rooms_free(pub, cal, sched, sit, xset, taken, elsewhere) if r["busy"] == ""]
            res = _seat.seat(sit, students, free, sched, model, (pins.get("rooms") or {}).get(key, {}))
            seats[key] = {r: s for r, s in res["rooms"].items() if s}
            unseated[key] = res["unseated"]
        else:
            seats[key] = keep_seats[key]
            unseated[key] = list((src.get("unseated") or {}).get(key) or [])
        used.append((sit["date"], lo, hi, set(seats[key])))
    fixed = [copy.deepcopy(d) for d in old_duties if d["key"] not in redo]
    duties = _inv.assign(pub, cal, sched, xset, {k: v for k, v in seats.items() if k in redo}, refill=dropped, fixed=fixed,
                         elsewhere=elsewhere, prefer=prefer)
    _inv.recheck(pub, cal, sched, xset, [d for d in duties if d["key"] not in redo], duties, elsewhere)
    hand = pins.setdefault("duties", {})
    for d in duties:
        pk = "%s|%s" % (d["key"], d["room"])
        if d["key"] in redo and pk in hand and hand[pk] != d["names"]:
            hand[pk] = list(d["names"])   # a replacement for a name that left is kept by the next Make
        d["locked"] = pk in hand
    fp = fingerprint(sched, xset)
    if only and keys - redo and old.get("fingerprint") != fp:
        fp = old.get("fingerprint")   # the kept sittings were made from what was there before: still stale
    sched["made"] = dict(seats=seats, unseated=unseated, duties=duties, gone=gone, made_at=_now(), fingerprint=fp,
                       published_at=published_at(pub))
    return sched


def move(sched, key, sids, room) -> None:
    by = sched.setdefault("pins", dict(rooms={}, duties={})).setdefault("rooms", {}).setdefault(key, {})
    for sid in sids:
        by[sid] = room


def set_invigilators(sched, key, room, names) -> None:
    """names chosen by hand for a duty; None hands the duty back to the app"""
    hand = sched.setdefault("pins", dict(rooms={}, duties={})).setdefault("duties", {})
    if names is None:
        hand.pop("%s|%s" % (key, room), None)
    else:
        hand["%s|%s" % (key, room)] = list(names)


def summary(pub, cal, sched, xset) -> dict:
    model = pub["model"]
    made = sched.get("made") or {}
    duties = made.get("duties") or []
    papers = sched.get("papers") or []
    out = []
    for e in _days.dates(sched, cal, model):
        date = e["date"]
        view = _days.day_view(pub, cal, sched, date)
        freed, teaching = set(), set()
        for l in view["lessons"]:
            if l["stopped"]:
                freed.update(l["teachers"])
            if l["running"]:
                teaching.update(l["teachers"])
        on_today = [d for d in duties if d["date"] == date]
        entry = (sched.get("days") or {}).get(date) or {}
        by_level = {}
        for p in sorted((p for p in papers if p.get("date") == date and p.get("start")), key=lambda p: _days.minutes(p["start"])):
            try:
                st = _days.minutes(p["start"])
            except ValueError:
                continue
            by_level.setdefault(p.get("level"), []).append(
                dict(label=_papers.label(p), start=_days.hhmm(st), end=_days.hhmm(st + p["minutes"])))
        out.append(dict(date=date, day=e["day"], levels=e["levels"], whole=bool(entry.get("whole", True)),
                        window=[_days.hhmm(e["start"]), _days.hhmm(e["end"])], papers=by_level, freed=len(freed),
                        on_duty=len({n for d in on_today for n in d["names"]}), teaching=len(teaching),
                        backups=sum(len(d["backup"]) for d in on_today)))
    per_day = {}
    for p in papers:
        if p.get("date"):
            for sid in _papers.who_sits(p, model):
                per_day.setdefault((p["date"], sid), 0)
                per_day[(p["date"], sid)] += 1
    counts = dict(papers=len(papers), with_time=sum(1 for p in papers if p.get("date") and p.get("start")),
                  two_a_day=len({sid for (_, sid), n in per_day.items() if n >= 2}), duties=len(duties),
                  backups=sum(len(d["backup"]) for d in duties), short=sum(d["short"] for d in duties),
                  unseated=sum(len(v) for v in (made.get("unseated") or {}).values()))
    gone = gone_now(pub, sched)
    gone += [g for g in made.get("gone") or [] if g not in gone]   # and the ones the last Make dropped
    return dict(days=out, counts=counts, checks=_papers.check(sched, model, cal, xset["rules"]), gone=gone)


def lesson_lists(pub, cal, sched) -> dict:
    model = pub["model"]
    duties = (sched.get("made") or {}).get("duties") or []
    out = dict(none=[], backup=[], runs=[])
    for e in _days.dates(sched, cal, model):
        if e["day"] is None:
            continue
        date = e["date"]
        mine = [d for d in duties if d["date"] == date]
        for l in _days.day_view(pub, cal, sched, date)["lessons"]:
            def item(span, note):
                return dict(date=date, start=_days.hhmm(span[0]), end=_days.hhmm(span[1]), classes=list(l["classes"]),
                            subject=l["subject"], teachers=list(l["teachers"]), room=l["room"], note=note)
            for sp in l["stopped"]:
                out["none"].append(item(sp, "shortened" if l["running"] else ""))
            for sp in l["running"]:
                hit = next(((t, d) for t in l["teachers"] for d in mine if t in d["names"] and d["start"] < sp[1] and d["end"] > sp[0]), None)
                if hit:
                    out["backup"].append(item(sp, "%s is invigilating %s" % (hit[0], hit[1]["room"])))
                else:
                    out["runs"].append(item(sp, ""))
    return out

"""Make an exam schedule's seats and duties, keep hand changes, and the figures the pages show."""
import copy
import datetime

import relief.people
import relief.settings
from exams import days as _days
from exams import invigilate as _inv
from exams import papers as _papers
from exams import seating as _seat


def _now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def _split(k):
    key, _, room = k.rpartition("|")
    return key, room


def _gone(pub, sched, model):
    """sentences for pinned students and invigilators no longer there; those pins are dropped"""
    known_s = {s["id"] for s in model.get("students") or []}
    known_p = {p["name"] for p in relief.people.people(pub, relief.settings.load(pub)["extra_staff"])}
    pins = sched.setdefault("pins", dict(rooms={}, duties={}))
    out = []
    for key, by in list((pins.get("rooms") or {}).items()):
        for sid in list(by):
            if sid not in known_s:
                s = "%s is no longer on the timetable." % sid
                if s not in out:
                    out.append(s)
                del by[sid]
        if not by:
            del pins["rooms"][key]
    for key, names in list((pins.get("duties") or {}).items()):
        keep = []
        for n in names:
            if n in known_p:
                keep.append(n)
            else:
                s = "%s is no longer on the timetable." % n
                if s not in out:
                    out.append(s)
        if len(keep) != len(names):
            if keep:
                pins["duties"][key] = keep
            else:
                del pins["duties"][key]
    return out


def _span(sit, students, rules, duties):
    mine = [d for d in duties if d["key"] == sit["key"]]
    if mine:
        return min(d["start"] for d in mine), max(d["end"] for d in mine)
    ends = [s["end"] for s in students.values()]
    return sit["start"] - rules["arrive"], (max(ends) if ends else sit["start"]) + rules["stay"]


def make(pub, cal, sched, xset, only=None) -> dict:
    model = pub["model"]
    old = sched.get("made") or {}
    gone = _gone(pub, sched, model)
    pins = sched["pins"]
    sits = _seat.sittings(sched)
    keys = {s["key"] for s in sits}
    keep_seats = {k: v for k, v in (old.get("seats") or {}).items() if k in keys} if only else {}
    old_duties = [d for d in old.get("duties") or [] if d["key"] in keys] if only else []
    redo = {s["key"] for s in sits} if not only else {only} | (keys - set(keep_seats))
    seats, unseated, used = {}, {}, []
    for sit in sits:
        key = sit["key"]
        students = _seat.sitting_students(sit, sched, model)
        if key in redo:
            lo, hi = _span(sit, students, xset["rules"], [])
        else:
            lo, hi = _span(sit, students, xset["rules"], old_duties)
        if key in redo:
            taken = {r for d, a, b, rooms in used if d == sit["date"] and a < hi and b > lo for r in rooms}
            free = [r for r in _seat.rooms_free(pub, cal, sched, sit, xset, taken) if r["busy"] == ""]
            res = _seat.seat(sit, students, free, sched, model, (pins.get("rooms") or {}).get(key, {}))
            seats[key] = {r: s for r, s in res["rooms"].items() if s}
            unseated[key] = res["unseated"]
        else:
            seats[key] = keep_seats[key]
            unseated[key] = list((old.get("unseated") or {}).get(key) or [])
        used.append((sit["date"], lo, hi, set(seats[key])))
    real = sched
    work = sched
    if only:
        work = dict(sched, pins=dict(pins, duties=dict(pins.get("duties") or {})))
        for d in old_duties:
            if d["key"] not in redo:
                work["pins"]["duties"]["%s|%s" % (d["key"], d["room"])] = list(d["names"])
    duties = _inv.assign(pub, cal, work, xset, seats)
    if only:
        fresh = [d for d in duties if d["key"] in redo]
        duties = sorted(fresh + [copy.deepcopy(d) for d in old_duties if d["key"] not in redo],
                        key=lambda d: (d["date"], d["start"], d["room"]))
    real_pins = (real.get("pins") or {}).get("duties") or {}
    for d in duties:
        d["locked"] = "%s|%s" % (d["key"], d["room"]) in real_pins
    sched["made"] = dict(seats=seats, unseated=unseated, duties=duties, gone=gone, made_at=_now())
    return sched


def move(sched, key, sids, room) -> None:
    by = sched.setdefault("pins", dict(rooms={}, duties={})).setdefault("rooms", {}).setdefault(key, {})
    for sid in sids:
        by[sid] = room


def set_invigilators(sched, key, room, names) -> None:
    sched.setdefault("pins", dict(rooms={}, duties={})).setdefault("duties", {})["%s|%s" % (key, room)] = list(names)


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
    return dict(days=out, counts=counts, checks=_papers.check(sched, model, cal), gone=list(made.get("gone") or []))


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

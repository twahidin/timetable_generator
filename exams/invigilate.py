"""Invigilators: how many a room needs, who is free, and who is put on each duty. Reads the saved schedules only for minutes."""
import math

import relief.people
import relief.settings
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
    for row in _schedules.listing():
        if row["id"] == sched.get("id"):
            continue
        s = _schedules.load(row["id"])
        if not s or not s.get("made"):
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


def candidates(pub, cal, sched, xset, date, start, end, duties, subjects=(), exclude=(), _other=None) -> dict:
    model = pub["model"]
    rules = xset["rules"]
    pool = [p["name"] for p in relief.people.people(pub, relief.settings.load(pub)["extra_staff"])
            if p["teaches"] or p["name"] in xset["backups"]]
    view = _days.day_view(pub, cal, sched, date)
    mine = duty_minutes(duties)
    other = _other if _other is not None else _other_minutes(sched, date[:4])
    on_date = [d for d in duties if d["date"] == date]
    subjects = set(subjects)
    taught = {}
    for l in model.get("lessons") or []:
        for n in l.get("teachers") or []:
            taught.setdefault(n, set()).add(l["subject"])
    groups = dict(freed=[], free=[], backups=[], need_backup=[])
    for name in pool:
        if name in exclude or name in xset["never"]:
            continue
        if _hit(view["blocked"].get(name, ()), start, end):
            continue
        if any(name in d["names"] and d["start"] < end and d["end"] > start for d in on_date):
            continue
        if rules.get("max_per_day") and sum(1 for d in on_date if name in d["names"]) >= rules["max_per_day"]:
            continue
        if rules.get("not_own_subject") and subjects & taught.get(name, set()):
            continue
        stopped = [l for l in view["lessons"] if name in l["teachers"] and _hit(l["stopped"], start, end)]
        running = [l for l in view["lessons"] if name in l["teachers"] and _hit(l["running"], start, end)]
        c = dict(name=name, minutes=mine.get(name, 0), other=other.get(name, 0), reason="", rows=[])
        if running:
            if name in xset["backups"]:
                continue
            c["rows"] = [l["row"] for l in running]
            c["reason"] = "; ".join("teaches %s %s %s–%s: needs a backup" % (", ".join(l["classes"]), l["subject"],
                                    _days.hhmm(l["start"]), _days.hhmm(l["end"])) for l in running)
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


def assign(pub, cal, sched, xset, seats_by_key) -> list:
    model = pub["model"]
    rules = xset["rules"]
    people = {p["name"] for p in relief.people.people(pub, relief.settings.load(pub)["extra_staff"])}
    pins = (sched.get("pins") or {}).get("duties") or {}
    common = sched.get("supervision") == "lesson"
    duties, subjects_of = [], {}
    papers = {p["id"]: p for p in sched.get("papers") or []}
    for sit in _seating.sittings(sched):
        seated = (seats_by_key or {}).get(sit["key"]) or {}
        students = _seating.sitting_students(sit, sched, model)
        subjects_of[sit["key"]] = [papers[i]["subject"] for i in sit["papers"] if i in papers]
        view = _days.day_view(pub, cal, sched, sit["date"])
        for room, seats in seated.items():
            ids = [sid for sid, _ in seats if sid in students]
            if not ids:
                continue
            end = max(students[s]["end"] for s in ids) + rules["stay"]
            room_set = xset["rooms"].get(room) or {}
            n_need = need(room_set, len(ids), [students[s].get("aa") for s in ids], rules)
            duty = dict(key=sit["key"], room=room, date=sit["date"], start=sit["start"] - rules["arrive"], end=end, need=n_need,
                        names=[], chief=None, reasons={}, backup={}, short=0, locked=False)
            pin = pins.get("%s|%s" % (sit["key"], room))
            if pin is not None:
                duty["locked"] = True
                for n in pin:
                    if n in people and n not in duty["names"]:
                        duty["names"].append(n)
                        duty["reasons"][n] = "chosen by hand"
            elif common:
                classes = {students[s]["cls"] for s in ids}
                for l in view["lessons"]:
                    if set(l["classes"]) & classes and _hit(l["stopped"], sit["start"], sit["start"] + 1):
                        for n in l["teachers"]:
                            if n not in duty["names"]:
                                duty["names"].append(n)
                                duty["reasons"][n] = "supervises their own lesson"
                if duty["names"]:
                    duty["need"] = len(duty["names"])
            duties.append(duty)
    duties.sort(key=lambda d: (d["date"], d["start"], d["room"]))
    other = {}
    for d in duties:
        year = d["date"][:4]
        if year not in other:
            other[year] = _other_minutes(sched, year)
        left = d["need"] - len(d["names"])
        if left > 0 and not (common and not d["locked"] and d["names"]):
            others = [x for x in duties if x is not d]
            got = candidates(pub, cal, sched, xset, d["date"], d["start"], d["end"], others, subjects_of[d["key"]],
                             exclude=d["names"], _other=other[year])
            for group in ("freed", "free", "backups", "need_backup"):
                for c in got[group]:
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
    return duties

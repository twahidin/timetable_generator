"""Sittings, the rooms free at a sitting, and where each student sits. Pure: reads no files."""
import math

from exams import days as _days
from exams import papers as _papers


def sittings(sched) -> list:
    """papers with a date and a start, grouped by (date, start), in time order"""
    groups = {}
    for p in sched.get("papers") or []:
        if not p.get("date") or not p.get("start"):
            continue
        try:
            st = _days.minutes(p["start"])
        except ValueError:
            continue
        groups.setdefault((p["date"], st), []).append(p["id"])
    return [dict(key=f"{d} {_days.hhmm(st)}", date=d, start=st, papers=ids) for (d, st), ids in sorted(groups.items())]


def sitting_students(sitting, sched, model) -> dict:
    access = {a["student"]: a for a in sched.get("access") or [] if isinstance(a, dict) and a.get("student")}
    by_id = {p["id"]: p for p in sched.get("papers") or []}
    known = {s["id"]: s for s in model.get("students") or []}
    out = {}
    for pid in sitting["papers"]:
        p = by_id.get(pid)
        if p is None:
            continue
        for sid in _papers.who_sits(p, model):
            s = known[sid]
            e = _papers.ends(p, sid, access)
            row = out.setdefault(sid, dict(papers=[], level=_papers._student_level(model, s), cls=s.get("cls"), end=e,
                                           aa=access.get(sid)))
            row["papers"].append(pid)
            row["end"] = max(row["end"], e)
    return out


def _related(name, parts) -> list:
    out = [name]
    out += [c for c, ps in parts.items() if name in ps and c not in out]
    out += [p for p in parts.get(name, []) if p not in out]
    return out


def rooms_free(pub, cal, sched, sitting, xset, taken) -> list:
    model = pub["model"]
    parts = model.get("room_parts") or {}
    rules = xset["rules"]
    ends = [s["end"] for s in sitting_students(sitting, sched, model).values()]
    lo = sitting["start"] - rules["arrive"]
    hi = (max(ends) if ends else sitting["start"] + 0) + rules["stay"]
    lessons = _days.day_view(pub, cal, sched, sitting["date"])["lessons"]
    anyway = {tuple(x) for x in sched.get("use_anyway") or []}

    def direct(name):
        for l in lessons:
            span = next((sp for sp in sorted(l["running"]) if sp[0] < hi and sp[1] > lo), None)
            if span is None:
                continue
            who = ", ".join(l["classes"])
            if l["room"] == name:
                if span[1] <= sitting["start"]:   # busy only for the minutes before the paper the invigilators come early
                    return f"{l['subject']} with {who} until {_days.hhmm(span[1])} (invigilators arrive {_days.hhmm(lo)})"
                if span[0] >= hi - rules["stay"]:   # busy only for the minutes they stay after the last finish
                    return f"{l['subject']} with {who} from {_days.hhmm(span[0])} (invigilators stay until {_days.hhmm(hi)})"
                return f"{l['subject']} with {who} until {_days.hhmm(span[1])}"
            if name in [x.strip() for x in str(l.get("rain") or "").split(",")] and (sitting["key"], name) not in anyway:   # "Hall, LT2"
                return f"rain room for {l['subject']} with {who}"
        if name in taken:
            return "used by another sitting"
        return ""

    out = []
    for name, r in xset["rooms"].items():
        busy = next((b for b in (direct(n) for n in _related(name, parts)) if b), "")
        out.append(dict(name=name, seats=r["seats"], rows=r.get("rows"), cols=r.get("cols"), hall=r.get("hall", False),
                        access=r.get("access", False), busy=busy))
    return out


def _letters(i) -> str:
    return chr(65 + i) if i < 26 else chr(64 + i // 26) + chr(65 + i % 26)


def _usable_cols(room, spacing) -> int:
    return room["cols"] if spacing != "gap" else math.ceil(room["cols"] / 2)


def _space(room, spacing) -> int:
    if room.get("rows") and room.get("cols"):
        return min(room["seats"], room["rows"] * _usable_cols(room, spacing))
    return room["seats"] if spacing != "gap" else math.ceil(room["seats"] / 2)


def _layout(room, sids, students, seating, order_key):
    """-> [[sid, seat]] for the students of one room, and the ones that did not fit"""
    ordered = sorted(sids, key=order_key)
    cap = _space(room, seating.get("spacing", "every"))
    if not (room.get("rows") and room.get("cols")):
        return [[s, str(i + 1)] for i, s in enumerate(ordered[:cap])], ordered[cap:]
    shared = seating.get("shared", "levels")

    def gkey(sid):
        st = students[sid]
        return st["papers"][0] if shared == "papers" else st["level"]
    groups = {}
    for sid in ordered:
        groups.setdefault(gkey(sid), []).append(sid)
    queues = list(groups.values())
    rows = room["rows"]
    cols = [_letters(i) for i in range(room["cols"]) if seating.get("spacing", "every") != "gap" or i % 2 == 0]
    seats = [(c, r) for c in cols for r in range(1, rows + 1)][:cap]
    placed = {}
    if len(queues) < 2 or shared not in ("levels", "papers"):
        flat = [s for q in queues for s in q]
        for sid, (c, r) in zip(flat, seats):
            placed[sid] = f"{c}{r}"
    else:
        turn = 0
        for ci, c in enumerate(cols):
            live = [q for q in queues if q]
            if not live:
                break
            q = live[turn % len(live)]
            turn += 1
            for r in range(1, rows + 1):
                if (c, r) not in seats[:cap] or not q:
                    break
                placed[q.pop(0)] = f"{c}{r}"
        free = [f"{c}{r}" for c, r in seats if f"{c}{r}" not in placed.values()]
        for q in queues:
            while q and free:
                placed[q.pop(0)] = free.pop(0)
    out = [[sid, placed[sid]] for sid in ordered if sid in placed]
    return out, [sid for sid in ordered if sid not in placed]


def seat(sitting, students, rooms, sched, model, pins) -> dict:
    seating = sched.get("seating") or {}
    spacing = seating.get("spacing", "every")
    names = {s["id"]: s for s in model.get("students") or []}
    homes = {c["name"]: c.get("home") for c in model.get("classes") or []}
    by_room = {r["name"]: r for r in rooms}
    put = {r["name"]: [] for r in rooms}
    left = {sid: True for sid in students}
    parts = model.get("room_parts") or {}
    shut = set()   # a combined venue and its own rooms are one space: once one of them has a student, the others are shut

    def room_left(name):
        return 0 if name in shut else _space(by_room[name], spacing) - len(put[name])

    def place(sid, name):
        if not put[name]:
            shut.update(n for n in _related(name, parts) if n != name)
        put[name].append(sid)
        left.pop(sid, None)

    for sid, name in (pins or {}).items():
        if sid in left and name in by_room and room_left(name) > 0:
            place(sid, name)
    access_rooms = sorted(r["name"] for r in rooms if r.get("access"))
    plain = [r for r in rooms if not r.get("access")]
    for sid in sorted(left):
        aa = students[sid].get("aa")
        if aa and (aa.get("own_room") or aa.get("reader") or aa.get("scribe")):
            name = next((n for n in access_rooms if room_left(n) > 0), None)
            if name:
                place(sid, name)

    def class_key(c):
        return (next((students[s]["level"] for s in students if students[s]["cls"] == c), "") or "", c or "")

    def classes():
        out = {}
        for sid in left:
            out.setdefault(students[sid]["cls"], []).append(sid)
        return sorted(out.items(), key=lambda kv: class_key(kv[0]))

    if seating.get("home_rooms", True):
        for c, sids in classes():
            home = homes.get(c)
            if home in by_room and not by_room[home].get("access") and room_left(home) >= len(sids):
                for sid in sids:
                    place(sid, home)
    order = sorted((r["name"] for r in plain), key=lambda n: (-by_room[n]["seats"], n))
    for c, sids in classes():
        sids = sorted(sids)
        whole = next((n for n in order if room_left(n) >= len(sids)), None)
        if whole:
            for sid in sids:
                place(sid, whole)
            continue
        for n in order:
            while sids and room_left(n) > 0:
                place(sids.pop(0), n)

    rule = seating.get("order", "class")
    if rule == "name":
        key = lambda sid: (names[sid]["name"], sid)
    else:
        key = lambda sid: (students[sid]["cls"] or "", sid)
    result, unseated = {}, list(left)
    for r in rooms:
        if put[r["name"]]:
            seats, extra = _layout(r, put[r["name"]], students, seating, key)
            result[r["name"]] = seats
            unseated += extra
    unseated.sort(key=lambda s: (students[s]["level"] or "", students[s]["cls"] or "", s))
    return dict(rooms=result, unseated=unseated)

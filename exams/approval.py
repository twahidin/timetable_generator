"""Approval of an exam schedule: the copy the main site reads, the states, and the list of what changed. Pure: reads no files."""
import copy
import hashlib
import json

from exams import days as _days
from exams import papers as _papers

SNAP = ("name", "kind", "levels", "classes", "start", "end", "days", "times", "papers", "access", "seating", "supervision",
        "scripts", "made", "pins", "use_anyway")
EVENT_KEYS = ("in_charge", "where", "venues", "going", "going_by", "duties")
WHO = dict(event="the teacher in charge")
STALE = "The exam changed since Make: press Make again."
NOT_ON_SITE = "This schedule is not on the main site."
NOTHING_WAITING = "There is nothing waiting for approval."
LABELS = dict(draft="Draft", waiting="Waiting for the timetable committee", approved="Approved · on the main site",
              changes="Approved · changes waiting", withdrawn="Withdrawn")


def public(sched) -> dict:
    """what the main site may show: deep copies of SNAP, the made part cut to seats, unseated, duties and published_at"""
    event = sched.get("kind") == "event"
    out = {k: copy.deepcopy(sched.get(k)) for k in SNAP + (EVENT_KEYS if event else ())}
    if out["scripts"] is None:
        out["scripts"] = ""
    m = sched.get("made")
    out["made"] = None if not m else copy.deepcopy(dict(seats=m.get("seats"), unseated=m.get("unseated"), duties=m.get("duties"),
                                                        published_at=m.get("published_at")))
    return out


def fp(sched) -> str:
    return hashlib.sha256(json.dumps(public(sched), sort_keys=True, default=str).encode()).hexdigest()[:16]


def as_schedule(sched):
    if not sched.get("approved"):
        return None
    return dict(sched["approved"], id=sched["id"], status=sched["status"])


def last_date(s) -> str:
    return max([s.get("end") or ""] + [p["date"] for p in s.get("papers") or [] if p.get("date")])


def retimed(copy_, published_at) -> bool:
    """the copy was made for another publish of the timetable than the one on the main site now"""
    return (copy_.get("made") or {}).get("published_at") != published_at


def label(sched, today) -> str:
    st = sched.get("status") or "draft"
    ap = sched.get("approved")
    if st in ("approved", "changes") and ap and today.isoformat() > last_date(ap):
        return "Ended"
    if st == "draft" and sched.get("note"):
        return "Sent back"
    return LABELS.get(st, LABELS["draft"])


def log(sched, by, what, detail, now) -> None:
    if not sched.get("log"):
        sched["log"] = []
    sched["log"].append(dict(at=now, by=by, what=what, detail=detail))


def done_without(sched) -> list:
    return [e for e in sched.get("log") or [] if e.get("what") == "replaced"]


def _n(n, one, many) -> str:
    return "1 %s" % one if n == 1 else "%d %s" % (n, many)


def _who_to(sched) -> str:
    return WHO.get(sched.get("kind"), "the exams committee")


def blocked(sched, model, stale, errors) -> str:
    if sched.get("kind") == "event":
        if errors:
            return errors[0]
        return "Nothing on the main site changes." if sched.get("status") == "approved" and not changes(sched, model) else ""
    if not sched.get("made"):
        return "Press Make first."
    if stale:
        return STALE
    if errors:
        return "Fix the paper times first: %s" % errors[0]
    if sched.get("status") == "approved" and not changes(sched, model):
        return "Nothing on the main site changes."
    return ""


def send(sched, model, by, now, stale, errors) -> None:
    why = blocked(sched, model, stale, errors)
    if why:
        raise ValueError(why)
    st = sched.get("status") or "draft"
    if st in ("approved", "changes"):
        n = len(changes(sched, model))
        sched["status"] = "changes"
        log(sched, by, "changes sent", _n(n, "change", "changes"), now)
    else:
        sched["status"] = "waiting"
        log(sched, by, "sent again" if st == "waiting" else "sent", "", now)
    sched["sent_at"], sched["sent_by"], sched["sent_fp"], sched["note"] = now, by, fp(sched), ""


def approve(sched, by, now) -> None:
    st = sched.get("status")
    if st not in ("waiting", "changes"):
        raise ValueError(NOTHING_WAITING)
    if fp(sched) != sched.get("sent_fp"):
        raise ValueError("This schedule changed after it was sent. Ask %s to send it again." % _who_to(sched))
    sched["approved"] = public(sched)
    sched["approved_at"], sched["approved_by"], sched["note"] = now, by, ""
    sched["status"] = "approved"
    log(sched, by, "approved" if st == "waiting" else "changes approved", "", now)


def send_back(sched, note, by, now) -> None:
    note = str(note or "").strip()
    if not note:
        raise ValueError("Write a note for %s." % _who_to(sched))
    st = sched.get("status")
    if st not in ("waiting", "changes"):
        raise ValueError(NOTHING_WAITING)
    sched["status"] = "draft" if st == "waiting" else "approved"
    sched["note"] = note
    log(sched, by, "sent back" if st == "waiting" else "changes sent back", note, now)


def withdraw(sched, by, now) -> None:
    if not sched.get("approved"):
        raise ValueError(NOT_ON_SITE)
    sched["approved"] = None
    sched["status"] = "withdrawn"
    log(sched, by, "withdrawn", "", now)


def _entry(e, noun="exam") -> str:
    e = e or {}
    if not e:
        return "as the " + noun
    if e.get("whole", True) or not (e.get("from") and e.get("to")):
        out = "whole day"
    else:
        out = "part of the day %s–%s" % (e["from"], e["to"])
    return out + (" (%s)" % ", ".join(e["levels"]) if e.get("levels") else "")


def _when(p) -> str:
    a = _days.minutes(p["start"])
    return "%s %s–%s" % (_days.nice(p["date"]), _days.hhmm(a), _days.hhmm(a + p["minutes"]))


def _timed(p) -> bool:
    return bool(p.get("date") and p.get("start"))


def _who(p):
    return (p.get("who"), sorted(p.get("students") or []), p.get("together") or "")


def _names(v) -> str:
    return ", ".join(v) if v else "no one"


def _rooms_text(counts, counted=False) -> str:
    """counted: the same one room on both sides, so the counts are what changed ("3-01 (30) → 3-01 (31)")"""
    if not counts:
        return "not seated"
    if len(counts) == 1 and not counted:
        return next(iter(counts))
    return ", ".join("%s (%d)" % (r, n) for r, n in sorted(counts.items(), key=lambda x: (-x[1], x[0])))


def _by_class(seats, cls) -> dict:
    out = {}
    for room, rows in (seats or {}).items():
        for sid, _seat in rows:
            c = out.setdefault(cls.get(sid, "?"), {})
            c[room] = c.get(room, 0) + 1
    return out


def _event_changes(old, new, add) -> None:
    pl = lambda v: ", ".join(v) if v else "none"
    if (old.get("where") or "") != (new.get("where") or ""):
        add("where", "Where: %s → %s." % (old.get("where") or "not set", new.get("where") or "not set"))
    if list(old.get("venues") or []) != list(new.get("venues") or []):
        add("venues", "Venues taken: %s → %s." % (pl(old.get("venues")), pl(new.get("venues"))))
    a, b = list(old.get("going") or []), list(new.get("going") or [])
    for n in b:
        if n not in a:
            add("going", "%s now goes with the classes." % n)
    for n in a:
        if n not in b:
            add("going", "%s no longer goes with the classes." % n)
    if (old.get("duties") or []) != (new.get("duties") or []):
        add("duties", "Duties at the event changed.")


def changes(sched, model) -> list:
    """what the working copy would change on the main site: a list of dict(kind, text), in the order of the page"""
    old, new = sched.get("approved"), public(sched)
    if not old:
        return []
    out = []

    def add(kind, text):
        out.append(dict(kind=kind, text=text))

    if old["name"] != new["name"]:
        add("name", "Name: %s → %s." % (old["name"], new["name"]))
    if (old["start"], old["end"]) != (new["start"], new["end"]):
        add("dates", "Dates: %s–%s → %s–%s." % (_days.nice(old["start"]), _days.nice(old["end"]), _days.nice(new["start"]), _days.nice(new["end"])))
    lc = lambda s: ", ".join(list(s.get("levels") or []) + list(s.get("classes") or [])) or "none"
    if lc(old) != lc(new):
        add("levels", "Levels and classes: %s → %s." % (lc(old), lc(new)))
    for d in sorted(set(old["days"] or {}) | set(new["days"] or {})):
        a, b = _entry((old["days"] or {}).get(d), new["kind"]), _entry((new["days"] or {}).get(d), new["kind"])
        if a != b:
            add("day", "%s: %s → %s." % (_days.nice(d), a, b))
    if new["kind"] == "event":
        _event_changes(old, new, add)
    ro, rn = (old["times"] or {}).get("report"), (new["times"] or {}).get("report")
    if ro != rn:
        add("times", "Report time: %s → %s." % (ro, rn))
    if (old["scripts"] or "") != (new["scripts"] or ""):
        add("scripts", "Scripts go to: %s → %s." % (old["scripts"] or "not set", new["scripts"] or "not set"))
    ao = {a.get("student"): a for a in old["access"] or []}
    an = {a.get("student"): a for a in new["access"] or []}
    n = sum(1 for k in set(ao) | set(an) if ao.get(k) != an.get(k))
    if n:
        add("access", "Access arrangements changed for %s." % _n(n, "student", "students"))
    po, pn = {p["id"]: p for p in old["papers"] or []}, {p["id"]: p for p in new["papers"] or []}
    for i, p in pn.items():
        if i not in po:
            add("paper", "Added %s: %s." % (_papers.label(p), _when(p)) if _timed(p) else "Added %s with no time." % _papers.label(p))
            continue
        q = po[i]
        if (q.get("date"), q.get("start"), q.get("minutes")) != (p.get("date"), p.get("start"), p.get("minutes")):
            was = _when(q) if _timed(q) else "no time"
            now = _when(p) if _timed(p) else "no time"
            add("paper", "%s: %s → %s." % (_papers.label(p), was, now))
        if _who(q) != _who(p):
            add("paper", "%s: who sits changed." % _papers.label(p))
    for i, q in po.items():
        if i not in pn:
            add("paper", "Removed %s." % _papers.label(q))
    mo, mn = old["made"] or {}, new["made"]
    if mn is None:
        return out
    do = {(d["key"], d["room"]): d for d in mo.get("duties") or []}
    dn = {(d["key"], d["room"]): d for d in mn.get("duties") or []}
    for k in sorted(set(do) | set(dn)):
        a, b = list((do.get(k) or {}).get("names") or []), list((dn.get(k) or {}).get("names") or [])
        if a == b:
            continue
        leaving = [x for x in a if x not in b]
        joining = [x for x in b if x not in a]
        side = "invigilators" if len(leaving) >= 2 or len(joining) >= 2 else "invigilator"
        add("duty", "%s %s, %s: %s → %s (%s)." % (_days.nice(k[0][:10]), k[0][11:], k[1], _names(leaving), _names(joining), side))
    cls = {s["id"]: s.get("cls") for s in model.get("students") or []}
    so, sn = mo.get("seats") or {}, mn.get("seats") or {}
    keys = sorted(set(so) | set(sn))
    for k in keys:
        a, b = _by_class(so.get(k), cls), _by_class(sn.get(k), cls)
        for c in sorted(set(a) | set(b)):
            ra, rb = a.get(c, {}), b.get(c, {})
            if ra != rb:
                counted = len(ra) == 1 and set(ra) == set(rb)
                add("rooms", "%s %s, %s: %s → %s." % (_days.nice(k[:10]), k[11:], c, _rooms_text(ra, counted), _rooms_text(rb, counted)))
    for k in keys:
        was = {sid: (room, seat) for room, rows in (so.get(k) or {}).items() for sid, seat in rows}
        n = sum(1 for room, rows in (sn.get(k) or {}).items() for sid, seat in rows if sid in was and was[sid][0] == room and was[sid][1] != seat)
        if n:
            add("seats", "%s %s: %s a new seat." % (_days.nice(k[:10]), k[11:], "1 student has" if n == 1 else "%d students have" % n))
    if mn.get("published_at") and mn.get("published_at") != mo.get("published_at"):
        add("timetable", "Made again for the timetable published on %s." % _days.nice(mn["published_at"]))
    return out


def _swap(duty, away, name) -> None:
    duty["names"] = [name if x == away else x for x in duty["names"]]
    if duty.get("chief") == away:
        duty["chief"] = name
    if not isinstance(duty.get("reasons"), dict):
        duty["reasons"] = {}
    duty["reasons"].pop(away, None)
    duty["reasons"][name] = "replaces %s, who is away" % away
    for k in ("backup", "not_free", "marks"):
        if isinstance(duty.get(k), dict):
            duty[k].pop(away, None)


def _drop(duty, away) -> None:
    """away leaves a duty that already has the person taking over: one name fewer, no one named twice"""
    duty["names"] = [x for x in duty["names"] if x != away]
    if duty.get("chief") == away:
        duty["chief"] = duty["names"][0] if duty["names"] else None
    for k in ("reasons", "backup", "not_free", "marks"):
        if isinstance(duty.get(k), dict):
            duty[k].pop(away, None)
    if isinstance(duty.get("need"), int):
        duty["short"] = max(0, duty["need"] - len(duty["names"]))


def _pin(copy_, pk, names) -> None:
    copy_.setdefault("pins", dict(rooms={}, duties={})).setdefault("duties", {})[pk] = list(names)


def replace(sched, key, room, away, name, by, now) -> str:
    """someone on an approved duty is away: swap the name in both copies at once and note it. The route checks name is free.
    The approved copy is pinned to its own names; the working copy's duty changes (and is pinned to its own names) only
    when it holds the person away, so a change waiting for approval stays as it was."""
    ap = sched.get("approved")
    if not ap:
        raise ValueError(NOT_ON_SITE)
    duty = next((d for d in (ap.get("made") or {}).get("duties") or [] if d["key"] == key and d["room"] == room), None)
    if not duty:
        raise ValueError("That duty is not on the main site.")
    if away not in duty["names"]:
        raise ValueError("%s is not on that duty." % away)
    if name in duty["names"]:
        raise ValueError("%s is on that duty already." % name)
    was_sent = sched.get("sent_fp") is not None and sched["sent_fp"] == fp(sched)
    _swap(duty, away, name)
    pk = "%s|%s" % (key, room)
    _pin(ap, pk, duty["names"])
    mine = next((d for d in (sched.get("made") or {}).get("duties") or [] if d["key"] == key and d["room"] == room), None)
    if mine and away in mine["names"]:
        if name in mine["names"]:
            _drop(mine, away)
        else:
            _swap(mine, away, name)
        _pin(sched, pk, mine["names"])
    if was_sent:
        sched["sent_fp"] = fp(sched)
    detail = "%s %s–%s, %s: %s (away) → %s" % (_days.nice(duty["date"]), _days.hhmm(duty["start"]), _days.hhmm(duty["end"]), room, away, name)
    log(sched, by, "replaced", detail, now)
    return detail


def set_in_charge(sched, name, by, now) -> str:
    """the event's teacher in charge becomes name, in both copies at once: the timetable committee, which approves events, is the
    one changing it, so it waits for no approval, and a sent event stays as it was sent. Who is going, and the duties, stay as
    they are. The route checks name"""
    old = sched.get("in_charge") or ""
    if name == old:
        raise ValueError("%s is in charge already." % name)
    was_sent = sched.get("sent_fp") is not None and sched["sent_fp"] == fp(sched)
    sched["in_charge"] = name
    if sched.get("approved"):
        sched["approved"]["in_charge"] = name
    if was_sent:
        sched["sent_fp"] = fp(sched)
    detail = "%s → %s" % (old or "nobody", name)
    log(sched, by, "in charge", detail, now)
    return detail


def replace_going(sched, away, name, by, now) -> str:
    """someone going with an approved event is away: name takes over in both copies at once (as every duty's who) and it is
    noted. The route checks name is free. The working copy changes only when it holds the person away."""
    ap = sched.get("approved")
    if not ap:
        raise ValueError(NOT_ON_SITE)
    if away not in (ap.get("going") or []):
        raise ValueError("%s is not going." % away)
    if name in ap["going"]:
        raise ValueError("%s is going already." % name)
    was_sent = sched.get("sent_fp") is not None and sched["sent_fp"] == fp(sched)
    swap = lambda c: (c.update(going=[name if x == away else x for x in c["going"]]),
                      [d.update(who=name) for d in c.get("duties") or [] if d.get("who") == away])
    swap(ap)
    if away in (sched.get("going") or []):
        if name in sched["going"]:
            sched["going"] = [x for x in sched["going"] if x != away]
            for d in sched.get("duties") or []:
                if d.get("who") == away:
                    d["who"] = name
        else:
            swap(sched)
    if was_sent:
        sched["sent_fp"] = fp(sched)
    a, b = _days.nice(ap["start"]), _days.nice(ap["end"])
    detail = "%s, going: %s (away) → %s" % (a if a == b else "%s–%s" % (a, b), away, name)
    log(sched, by, "replaced", detail, now)
    return detail

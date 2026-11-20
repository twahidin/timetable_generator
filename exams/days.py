"""What a date of an exam schedule does to lessons and teachers. Pure: reads no files.

Times are whole minutes after midnight. A schedule is a dict with levels, classes, start, end, days
({date: dict(levels, whole, from, to)}); missing keys take the defaults described on each function.
"""
import datetime
import re

from relief.calendar import school_day


def minutes(t):
    m = re.fullmatch(r"(\d{1,2}):(\d{2})", str(t).strip())
    if not m or int(m.group(1)) > 23 or int(m.group(2)) > 59:
        raise ValueError("%s is not a time." % t)
    return int(m.group(1)) * 60 + int(m.group(2))


def hhmm(m):
    return "%02d:%02d" % divmod(int(m), 60)


def bounds(model):
    return [(minutes(a), minutes(b)) for a, b in model["times"]]


def _date(s):
    return datetime.date.fromisoformat(s)


def _entry(sched, date):
    return (sched.get("days") or {}).get(date) or {}


def _window(sched, date, bnds):
    e = _entry(sched, date)
    if e.get("whole", True) or not (e.get("from") and e.get("to")):
        return bnds[0][0], bnds[-1][1]
    return minutes(e["from"]), minutes(e["to"])


def _levels(sched, date):
    e = _entry(sched, date)
    return list(e["levels"]) if e.get("levels") is not None else list(sched.get("levels") or [])


def dates(sched, cal, model):
    bnds = bounds(model)
    out = []
    d, last = _date(sched["start"]), _date(sched["end"])
    while d <= last:
        iso = d.isoformat()
        s, e = _window(sched, iso, bnds)
        out.append(dict(date=iso, day=school_day(cal, model["days"], d), levels=_levels(sched, iso), start=s, end=e))
        d += datetime.timedelta(days=1)
    return out


def _merge(spans):
    out = []
    for s, e in spans:
        if out and out[-1][1] == s:
            out[-1] = (out[-1][0], e)
        else:
            out.append((s, e))
    return out


def _day_ok(dname, r):
    wk, dy = str(r.get("week") or "Both"), str(r.get("day") or "All")
    if wk in ("Odd", "Even") and not dname.startswith(wk):
        return False
    return dy == "All" or dname.split()[-1][:3] == dy[:3]


def day_view(pub, cal, sched, date):
    model = pub["model"]
    bnds = bounds(model)
    NP = len(bnds)
    day = school_day(cal, model["days"], _date(date))
    window = {}
    if sched["start"] <= date <= sched["end"]:
        levels = _levels(sched, date)
        chosen = sched.get("classes") or []
        win = _window(sched, date, bnds)
        for c in model["classes"]:
            if c["level"] in levels and (not chosen or c["name"] in chosen):
                window[c["name"]] = win
    lessons, blocked = [], {}
    if day is not None:
        d = model["days"].index(day)
        for i, l in enumerate(model["lessons"]):
            if l["d"] != d:
                continue
            ps = range(l["p"], min(l["p"] + l["n"], NP))
            inside = bool(l["classes"]) and all(c in window for c in l["classes"])
            stopped, running = [], []
            for p in ps:
                if inside and all(window[c][0] <= bnds[p][0] and bnds[p][1] <= window[c][1] for c in l["classes"]):
                    stopped.append(bnds[p])
                else:
                    running.append(bnds[p])
            lessons.append(dict(row=i, classes=l["classes"], teachers=l["teachers"], subject=l["subject"], level=l["level"],
                                room=l["room"], rain=l.get("rain", ""), start=bnds[ps[0]][0], end=bnds[ps[-1]][1],
                                stopped=_merge(stopped), running=_merge(running)))
        for r in model.get("setup", {}).get("rules", []):
            if r.get("rule") != "Not available" or r.get("scope") != "Teacher" or r.get("strength") != "Must":
                continue
            if not _day_ok(day, r):
                continue
            a, b = r.get("from"), r.get("to")
            a = int(a) if a not in (None, "") else 0
            b = int(b) if b not in (None, "") else NP - 1
            spans = [bnds[p] for p in range(max(a, 0), min(b, NP - 1) + 1)]
            if spans:
                blocked.setdefault(r["target"], []).extend(spans)
        blocked = {t: _merge(sorted(s)) for t, s in blocked.items()}
    return dict(date=date, day=day, window=window, lessons=lessons, blocked=blocked)


def edge_cuts(view):
    return sum(1 for r in view["lessons"] if r["stopped"] and r["running"])

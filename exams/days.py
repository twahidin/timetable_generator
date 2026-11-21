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


def _clock(t):
    """a time as the published model writes it ("7.40", "1.00" or "07:40"), read without am or pm"""
    m = re.fullmatch(r"(\d{1,2})[.:](\d{2})", str(t).strip())
    if not m or int(m.group(1)) > 23 or int(m.group(2)) > 59:
        raise ValueError("%s is not a time." % t)
    return int(m.group(1)) * 60 + int(m.group(2))


def bounds(model):
    """(start, end) minutes of each period. Read from the school's start time and period length, as ttgen/spec.py does: the
    model's `times` are a 12-hour clock without am or pm ("12.40", then "1.00"). Without those, `times` are read in order,
    12 hours added whenever a time is lower than the one before."""
    sc = model.get("school") or {}
    NP = model.get("NP") or len(model.get("times") or [])
    try:
        h, m = map(int, str(sc["start_time"]).split(":")[:2])
        pm = int(sc["period_minutes"])
        if NP and pm > 0:
            return [(h * 60 + m + pm * p, h * 60 + m + pm * (p + 1)) for p in range(NP)]
    except (KeyError, TypeError, ValueError):
        pass
    out, last, add = [], -1, 0
    for pair in model.get("times") or []:
        two = []
        for t in pair:
            v = _clock(t) + add
            while v < last:
                add += 720
                v += 720
            two.append(v)
            last = v
        out.append(tuple(two))
    return out


def _date(s):
    return datetime.date.fromisoformat(s)


def _entry(sched, date):
    return (sched.get("days") or {}).get(date) or {}


def _window(sched, date, bnds):
    e = _entry(sched, date)
    if e.get("whole", True) or not (e.get("from") and e.get("to")):
        return bnds[0][0], bnds[-1][1]
    return minutes(e["from"]), minutes(e["to"])


def levels_of(sched, model):
    """the schedule's levels; an exam of chosen classes with no level takes the levels of those classes"""
    if sched.get("levels"):
        return list(sched["levels"])
    chosen = set(sched.get("classes") or [])
    out = []
    for c in model.get("classes") or []:
        if c["name"] in chosen and c["level"] not in out:
            out.append(c["level"])
    return out


def _levels(sched, date, model):
    """the levels sitting on a date: the day's own list when it has one (an exam of chosen classes cannot name a day's
    levels on the page, so an empty list there means its classes' levels), else the schedule's levels"""
    e = _entry(sched, date)
    if e.get("levels") is not None and (e["levels"] or sched.get("levels")):
        return list(e["levels"])
    return levels_of(sched, model)


def dates(sched, cal, model):
    bnds = bounds(model)
    out = []
    d, last = _date(sched["start"]), _date(sched["end"])
    while d <= last:
        iso = d.isoformat()
        s, e = _window(sched, iso, bnds)
        out.append(dict(date=iso, day=school_day(cal, model["days"], d), levels=_levels(sched, iso, model), start=s, end=e))
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
        levels = _levels(sched, date, model)
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
            if r.get("rule") != "Not available" or r.get("scope") != "Teacher" or str(r.get("strength") or "Must") != "Must":
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

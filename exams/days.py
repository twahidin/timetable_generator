"""What a date of an exam schedule does to lessons and teachers. Pure: reads no files.

Times are whole minutes after midnight. A schedule is a dict with levels, classes, start, end, days
({date: dict(levels, whole, from, to)}); missing keys take the defaults described on each function.
"""
import datetime
import re

from relief.calendar import school_day
from ttgen.spec import plain_rules as _plain_rules, staff_items as _staff_items


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


_WEEK = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def nice(iso) -> str:
    """a date as the page writes it: "Mon 5 Oct", from the first ten characters; anything else comes back as given"""
    try:
        d = datetime.date.fromisoformat(str(iso)[:10])
    except ValueError:
        return str(iso or "")
    return "%s %d %s" % (_WEEK[d.weekday()], d.day, _MONTHS[d.month - 1])


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


def rule_on_day(dname, r):
    wk, dy = str(r.get("week") or "Both"), str(r.get("day") or "All")
    if wk in ("Odd", "Even") and not dname.startswith(wk):
        return False
    return dy == "All" or dname.split()[-1][:3] == dy[:3]


_day_ok = rule_on_day   # the old name, still called by code written before the rename


def _rows(model, bnds, day, windows):
    """the lessons of a timetable day as day_view gives them; windows {class: [(start, end)]}: a period stops when every
    class of the lesson has a window holding it"""
    NP = len(bnds)
    lessons = []
    if day is None:
        return lessons
    d = model["days"].index(day)
    for i, l in enumerate(model["lessons"]):
        if l["d"] != d:
            continue
        ps = range(l["p"], min(l["p"] + l["n"], NP))
        stopped, running = [], []
        for p in ps:
            held = bool(l["classes"]) and all(any(a <= bnds[p][0] and bnds[p][1] <= b for a, b in windows.get(c, ())) for c in l["classes"])
            (stopped if held else running).append(bnds[p])
        lessons.append(dict(row=i, classes=l["classes"], teachers=l["teachers"], subject=l["subject"], level=l["level"],
                            room=l["room"], rain=l.get("rain", ""), start=bnds[ps[0]][0], end=bnds[ps[-1]][1],
                            stopped=_merge(stopped), running=_merge(running)))
    return lessons


def _windows(sched, date, model, bnds):
    """{class: (start, end)} of the classes sitting on a date of one schedule"""
    out = {}
    if sched["start"] <= date <= sched["end"]:
        levels = _levels(sched, date, model)
        chosen = sched.get("classes") or []
        win = _window(sched, date, bnds)
        for c in model["classes"]:
            if c["level"] in levels and (not chosen or c["name"] in chosen):
                out[c["name"]] = win
    return out


def merged_view(pub, cal, scheds, date):
    """the lessons of a date with the windows of every schedule in scheds together"""
    model = pub["model"]
    bnds = bounds(model)
    day = school_day(cal, model["days"], _date(date))
    windows = {}
    for s in scheds:
        for c, w in _windows(s, date, model, bnds).items():
            windows.setdefault(c, []).append(w)
    return dict(date=date, day=day, lessons=_rows(model, bnds, day, windows))


def day_view(pub, cal, sched, date):
    model = pub["model"]
    bnds = bounds(model)
    NP = len(bnds)
    day = school_day(cal, model["days"], _date(date))
    window = _windows(sched, date, model, bnds)
    lessons = _rows(model, bnds, day, {c: [w] for c, w in window.items()})
    blocked, periods = {}, {}
    setup = model.get("setup") or {}
    if day is not None:
        for r in _plain_rules(setup):
            if r.get("rule") != "Not available" or r.get("scope") != "Teacher" or str(r.get("strength") or "Must") != "Must":
                continue
            if not rule_on_day(day, r):
                continue
            a, b = r.get("from"), r.get("to")
            a = int(a) if a not in (None, "") else 0
            b = int(b) if b not in (None, "") else NP - 1
            spans = [bnds[p] for p in range(max(a, 0), min(b, NP - 1) + 1)]
            if spans:
                blocked.setdefault(r["target"], []).extend(spans)
        blocked = {t: _merge(sorted(s)) for t, s in blocked.items()}
        for it in _staff_items(setup):   # teacher-only periods never block: carried beside blocked, as a mark
            if rule_on_day(day, it):
                periods.setdefault(it["teacher"], []).append((it["minutes"][0], it["minutes"][1], it["name"]))
        periods = {t: sorted(v) for t, v in periods.items()}
    return dict(date=date, day=day, window=window, lessons=lessons, blocked=blocked, periods=periods)


def edge_cuts(view):
    return sum(1 for r in view["lessons"] if r["stopped"] and r["running"])

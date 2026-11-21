"""Who is free for a lesson that needs relief, and how much relief each person already has. Pure: reads no files."""
import datetime

from exams.days import rule_on_day
from ttgen.spec import family
from relief import lessons as _lessons
from relief.calendar import school_day, term_of, week_of
from relief.people import people as _people


def _date(d):
    return d if isinstance(d, datetime.date) else datetime.date.fromisoformat(str(d))


def _iso(d):
    return _date(d).isoformat()


def _overlap(p, n, q, m):
    """do the periods p..p+n-1 and q..q+m-1 share one?"""
    return p <= q + m - 1 and q <= p + n - 1


def relief_periods(records, name, dates, skip=None):
    """periods of lessons where relief is name, still needed, in an absence not cancelled, on one of dates (dates or ISO strings);
    skip = (absent teacher, lesson key) leaves that one lesson out"""
    want = {_iso(d) for d in dates}
    total = 0
    for r in records:
        if r.get("cancelled"): continue
        for x in r.get("lessons") or []:
            if skip and r.get("teacher") == skip[0] and x.get("key") == skip[1]: continue
            if x.get("relief") == name and x.get("needed") and _iso(x["date"]) in want: total += int(x.get("n") or 1)
    return total


def _week_dates(cal, days, date):
    mon, _ = week_of(date)
    out = [mon + datetime.timedelta(days=i) for i in range(5)]
    return [d for d in out if school_day(cal, days, d) is not None]


def week_so_far(pub, cal, records, name, date, skip=None):
    """teaching periods plus relief periods in the school dates of the week holding date"""
    days = ((pub or {}).get("model") or {}).get("days") or []
    return _lessons.teaching_periods(pub, cal, name, date) + relief_periods(records, name, _week_dates(cal, days, date), skip)


def _absent_then(records, name, iso, p, n):
    for r in records:
        if r.get("cancelled") or r.get("teacher") != name or iso not in [_iso(d) for d in r.get("dates") or []]: continue
        per = r.get("periods")
        if per is None or _overlap(per[0], per[1] - per[0] + 1, p, n): return True
        if any(x.get("needed") and _iso(x["date"]) == iso and _overlap(x["p"], int(x.get("n") or 1), p, n) for x in r.get("lessons") or []): return True
    return False


def there_then(records, names, date, p, n):
    """the names (a lesson's other teachers) not away on date (a date or an ISO string) at any of the periods p..p+n-1"""
    iso = _iso(date)
    return [x for x in names if not _absent_then(records, x, iso, int(p), int(n or 1))]


def _chosen_then(records, name, iso, p, n, key, absent):
    """relief already chosen for name on another lesson overlapping this one (the same lesson of the same absence does not count)"""
    for r in records:
        if r.get("cancelled"): continue
        for x in r.get("lessons") or []:
            if x.get("relief") != name or not x.get("needed") or _iso(x["date"]) != iso: continue
            if x.get("key") == key and r.get("teacher") == absent: continue
            if _overlap(x["p"], int(x.get("n") or 1), p, n): return True
    return False


def _rule_hits(rule, day, p, n):
    if not rule_on_day(day, rule): return False
    a, b = rule.get("from"), rule.get("to")
    a = int(a) if a not in (None, "") else 0
    b = int(b) if b not in (None, "") else 10 ** 6
    return _overlap(a, b - a + 1, p, n)


def free_then(pub, settings, records, lesson, absent):
    """the people free for the lesson (a dict from lessons.on_date) of the absent teacher; "teaches {subject}" compares
    subject families (ttgen.spec.family: Mathematics G2 teaches a Mathematics G3 lesson), the title keeps the lesson's own subject:
    -> dict(groups=[dict(title, people=[dict(name, depts, subjects, fat, week, today, term, marks, over)])], teaching=[names])"""
    cal = settings.get("calendar") or {}
    lim = settings.get("limits") or {}
    fat_role = settings.get("fat_role") or ""
    model = ((pub or {}).get("model") or {})
    date, p, n, subject = _date(lesson["date"]), int(lesson["p"]), int(lesson.get("n") or 1), lesson.get("subject") or ""
    iso = date.isoformat()
    day = lesson.get("day") or school_day(cal, model.get("days") or [], date)
    rules = (model.get("setup") or {}).get("rules") or []
    term = term_of(cal, date)
    term_dates = []
    if term:
        d, last = _date(term["start"]), _date(term["end"])
        while d <= last: term_dates.append(d); d += datetime.timedelta(days=1)
    week_dates = _week_dates(cal, model.get("days") or [], date)
    taught = {}
    for L in model.get("lessons") or []:
        for t in L.get("teachers") or []: taught.setdefault(t, set()).add(L.get("subject") or "")
    absent_depts = next((x["depts"] for x in _people(pub, settings.get("extra_staff")) if x["name"] == absent), [])
    never = set(lim.get("never") or [])
    teaching, free = [], []
    for who in _people(pub, settings.get("extra_staff")):
        name = who["name"]
        if who["staff_only"] or name == absent: continue
        if _lessons.on_date(pub, cal, name, date, periods=(p, p + n - 1)):
            teaching.append(name); continue
        if _absent_then(records, name, iso, p, n) or _chosen_then(records, name, iso, p, n, lesson.get("key"), absent) or name in never: continue
        marks, blocked = [], False
        for r in rules:
            if r.get("rule") == "Not available" and r.get("scope") == "Teacher" and r.get("target") == name and _rule_hits(r, day, p, n):
                if str(r.get("strength") or "Must") == "Must": blocked = True
                elif "prefers not" not in marks: marks.append("prefers not")
            elif r.get("rule") == "Keep free together" and r.get("scope") == "Department" and r.get("target") in who["depts"] and _rule_hits(r, day, p, n):
                if "department meeting time" not in marks: marks.append("department meeting time")
        if blocked: continue
        skip = (absent, lesson.get("key"))
        today = relief_periods(records, name, {date}, skip=skip)   # this lesson's own periods are added below, not counted twice
        fat = bool(fat_role) and who["role"] == fat_role
        limit = lim.get("fat_per_day") if fat else lim.get("other_per_day")
        over = limit is not None and today + n > limit
        if over: marks.append(f"at {today} relief periods today (the limit is {limit})")
        free.append(dict(name=name, depts=list(who["depts"]), subjects=sorted(taught.get(name, ())), fat=fat,
                         week=week_so_far(pub, cal, records, name, date, skip=skip), today=today, term=relief_periods(records, name, term_dates, skip=skip),
                         marks=marks, over=over))
    free.sort(key=lambda x: (bool(x["marks"]), x["week"], x["term"], x["name"]))
    titles, buckets = [], {}
    for dept in absent_depts:
        titles += [f"{dept} · teaches {subject}", f"{dept} · other subjects"]
    titles.append("Other departments")
    for x in free:
        title = "Other departments"
        mine = [d for d in absent_depts if d in x["depts"]]
        if mine:
            same = family(subject) in {family(s) for s in x["subjects"]}
            title = f"{mine[0]} · teaches {subject}" if same else f"{mine[0]} · other subjects"
        buckets.setdefault(title, []).append(x)
    return dict(groups=[dict(title=t, people=buckets[t]) for t in titles if buckets.get(t)], teaching=sorted(teaching))

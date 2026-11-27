"""The school calendar: which published day a date is. Pure: no Flask, no files.

cal = dict(terms=[dict(name, start, end, starts_as)], holidays=[dict(start, end, name)]), dates "YYYY-MM-DD".
"""
import datetime

from ttgen.database import _split_day


def _d(s):
    return datetime.date.fromisoformat(s)


def week_of(date):
    """(monday, friday) of the calendar week holding date"""
    monday = date - datetime.timedelta(days=date.weekday())
    return monday, monday + datetime.timedelta(days=4)


def term_of(cal, date):
    for term in cal.get("terms", []):
        if _d(term["start"]) <= date <= _d(term["end"]):
            return term
    return None


def school_day(cal, days, date):
    """the item of days that date is, or None on a weekend, a holiday, outside every term, or a weekday not in days"""
    if date.weekday() > 4: return None
    term = term_of(cal, date)
    if term is None: return None
    if any(_d(h["start"]) <= date <= _d(h["end"]) for h in cal.get("holidays", [])): return None
    weeks = (week_of(date)[0] - week_of(_d(term["start"]))[0]).days // 7
    odd = (term.get("starts_as") == "Odd") == (weeks % 2 == 0)
    week = "Odd" if odd else "Even"
    wd = ("Mon", "Tue", "Wed", "Thu", "Fri")[date.weekday()]
    for name in days:
        w, part = _split_day(name)
        if w in ("", week) and part[:3].lower() == wd.lower():
            return name
    return None


def school_days(cal, days, start):
    """(the school days from start to the last day of the last term, {each other weekday of that span: why it is not one}):
    a holiday's name ("Holiday" when it has none), "Not in a term", or "Not a school day" (a weekday the timetable does not have)"""
    ends = [_d(t["end"]) for t in cal.get("terms", [])]
    if not ends or start > max(ends): return [], {}
    got, off = [], {}
    for i in range((max(ends) - start).days + 1):
        date = start + datetime.timedelta(days=i)
        if school_day(cal, days, date) is not None: got.append(date)
        elif date.weekday() < 5:
            hol = next((h for h in cal.get("holidays", []) if _d(h["start"]) <= date <= _d(h["end"])), None)
            if hol: off[date] = hol.get("name") or "Holiday"
            else: off[date] = "Not in a term" if term_of(cal, date) is None else "Not a school day"
    return got, off

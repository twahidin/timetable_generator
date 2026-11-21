"""A teacher's lessons on a date, read from the published timetable and the school calendar."""
import datetime
import os
from zoneinfo import ZoneInfo

from exams.days import bounds, hhmm
from relief.calendar import school_day, week_of

NO_CALENDAR = "Set the school calendar in Relief settings first: relief needs it to know which timetable day a date is."


def today():
    """the school's date (the server runs on UTC)"""
    return datetime.datetime.now(ZoneInfo(os.environ.get("SCHOOL_TZ") or "Asia/Singapore")).date()


def _key(date, day, p, n, classes, subject, group):
    return f"{date}/{day}/{p}/{n}/{'+'.join(sorted(classes))}/{subject}/{group}"


def on_date(pub, cal, teacher, date, periods=None):
    """the teacher's lessons that date in time order; periods = (from, to) 0-based inclusive, None for the whole day"""
    if not cal.get("terms"): raise ValueError(NO_CALENDAR)
    model = (pub or {}).get("model") or {}
    days = model.get("days") or []
    day = school_day(cal, days, date)
    if day is None: raise ValueError(f"{date:%a} {date.day} {date:%b} is not a school day in the calendar.")
    d, bnds, out = days.index(day), bounds(model), []
    for L in model.get("lessons") or []:
        if L.get("d") != d or teacher not in (L.get("teachers") or []): continue
        p, n = int(L["p"]), int(L.get("n") or 1)
        if periods is not None and (p + n - 1 < periods[0] or p > periods[1]): continue
        classes = list(L.get("classes") or [])
        s = bnds[p][0] if p < len(bnds) else None
        e = bnds[min(p + n, len(bnds)) - 1][1] if p < len(bnds) else None
        out.append(dict(key=_key(date, day, p, n, classes, L.get("subject") or "", L.get("group") or ""), date=date, day=day, p=p, n=n,
                        start=hhmm(s) if s is not None else "", end=hhmm(e) if e is not None else "", classes=classes,
                        subject=L.get("subject") or "", group=L.get("group") or "", room=L.get("room") or "",
                        others=[x for x in L.get("teachers") or [] if x != teacher], level=L.get("level") or ""))
    out.sort(key=lambda x: (x["p"], x["key"]))
    return out


def still_there(pub, cal, teacher, stored):
    """True when the teacher still has the stored lesson (same key) on its date"""
    date = stored["date"]
    if isinstance(date, str): date = datetime.date.fromisoformat(date)
    try: now = on_date(pub, cal, teacher, date)
    except ValueError: return False
    return any(x["key"] == stored["key"] for x in now)


def teaching_periods(pub, cal, teacher, date):
    """the teacher's periods on every school date of the week holding date; 0 when the calendar has no terms (no date is a school day)"""
    mon, _ = week_of(date)
    total = 0
    for i in range(5):
        d = mon + datetime.timedelta(days=i)
        try: total += sum(x["n"] for x in on_date(pub, cal, teacher, d))
        except ValueError: pass
    return total

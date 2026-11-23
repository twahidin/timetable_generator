"""School hours for relief: when the relief team may be pinged, when a relief may reach its teacher, when a held relief goes, and
the moment "24 hours before" a lesson moved into school hours. Pure: no Flask, no file. `settings` is settings.load's, `pub` the
published timetable; every date-time is in school time (fill._tz()).

The team's window: from the morning time to the cut-off of a duty day (stage 1: every school day). School hours for relief
teachers: from the earliest send-out time to the cut-off of a school day, the cut-off's own minute included; after the cut-off,
and on any day the calendar no longer calls a school day, a relief of a lesson that day still reaches its teacher from the
earliest send-out time on (whether the lesson is over is the caller's). A held relief never waits past its lesson's own morning.
"""
import collections, datetime, re

from exams.days import bounds
from relief import fill as _fill        # fill._tz() and fill._when() only, read at each call: fill imports cover, which imports this
from relief.calendar import school_day

DEFAULTS = dict(morning_at="06:30", send_from="06:45", cut_off="14:00", work_eve="18:00", work_day="07:00")
Hours = collections.namedtuple("Hours", "morning send_from cut_off work_eve work_day")
_TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
_DAY, _MINUTE = datetime.timedelta(days=1), datetime.timedelta(minutes=1)
AHEAD, BACK = 60, 14                    # how many days a morning or a send-out is looked for ahead, a cut-off back


def _time(v, default):
    v = v if isinstance(v, str) and _TIME.match(v) else default
    return datetime.time(int(v[:2]), int(v[3:]))


def of(settings) -> Hours:
    """the five times of settings["times"], each its default when missing or not "HH:MM\""""
    t = (settings or {}).get("times") or {}
    return Hours(*(_time(t.get(k), DEFAULTS[k]) for k in ("morning_at", "send_from", "cut_off", "work_eve", "work_day")))


def at(date, t) -> datetime.datetime:
    """the time t of date, in school time"""
    return datetime.datetime.combine(date, t, tzinfo=_fill._tz())


_at = at                                # for team_window, whose first argument is called at


def school(settings, pub, date) -> bool:
    """date is a school day of the calendar (calendar.school_day)"""
    days = ((pub or {}).get("model") or {}).get("days") or []
    return school_day((settings or {}).get("calendar") or {}, days, date) is not None


def duty_day(settings, pub, date) -> bool:
    """the relief team is on duty that day (stage 2 says who and when; stage 1: every school day)"""
    return school(settings, pub, date)


def on_duty(settings, date, team) -> list:
    """who of team is on duty on date (stage 2; stage 1: the whole team)"""
    return sorted(team)


def team_open(now, settings, pub) -> bool:
    """the relief team may be pinged now: a duty day, from the morning time to before the cut-off"""
    now, h = _fill._when(now), of(settings)
    return duty_day(settings, pub, now.date()) and h.morning <= now.time() < h.cut_off


def next_morning(now, settings, pub):
    """the first morning time of a duty day at or after now, within AHEAD days; None when there is none"""
    now, h = _fill._when(now), of(settings)
    for i in range(AHEAD + 1):
        d = now.date() + i * _DAY
        if duty_day(settings, pub, d) and at(d, h.morning) >= now: return at(d, h.morning)
    return None


def team_window(at, settings, pub):
    """(start, end) of the first team window that ends after at: (at, that day's cut-off) when the team may be pinged then,
    else (the next morning, that day's cut-off); None when there is no next morning"""
    at, cut = _fill._when(at), of(settings).cut_off
    if team_open(at, settings, pub): return at, _at(at.date(), cut)
    m = next_morning(at, settings, pub)
    return None if m is None else (m, _at(m.date(), cut))


def teacher_open(now, settings, pub, lesson_date) -> bool:
    """a relief of a lesson on lesson_date may reach its teacher now: on the lesson's own day from the earliest send-out time
    on; on any school day from the earliest send-out time to the end of the cut-off's minute"""
    now, h = _fill._when(now), of(settings)
    if now.date() == lesson_date and now.time() >= h.send_from: return True
    return school(settings, pub, now.date()) and h.send_from <= now.time() and now < at(now.date(), h.cut_off) + _MINUTE


def reaches_at(when, settings, pub, lesson_date) -> datetime.datetime:
    """when a relief held at when, of a lesson on lesson_date, reaches its teacher: when itself in school hours; else the
    earliest send-out time of the first school day after when (or of when's own day, before it), never later than the
    lesson's own morning and never earlier than when"""
    when, h = _fill._when(when), of(settings)
    if teacher_open(when, settings, pub, lesson_date): return when
    goes = at(lesson_date, h.send_from)
    for i in range(AHEAD + 1):
        d = when.date() + i * _DAY
        if at(d, h.send_from) >= goes: break
        if at(d, h.send_from) > when and school(settings, pub, d): goes = at(d, h.send_from); break
    return max(goes, when)


def before_moment(start, settings, pub):
    """the moment "24 hours before" start: start less 24 hours when that is in school hours of a school day (from the earliest
    send-out time to the cut-off), else the cut-off of the last school day at or before it whose cut-off is not after it,
    within BACK days; None when there is none"""
    b, h = _fill._when(start) - datetime.timedelta(hours=24), of(settings)
    if school(settings, pub, b.date()) and h.send_from <= b.time() <= h.cut_off: return b
    for i in range(BACK + 1):
        d = b.date() - i * _DAY
        if school(settings, pub, d) and at(d, h.cut_off) <= b: return at(d, h.cut_off)
    return None


def _span(pub, x, c):
    """(start, end) of the cover's lesson (exams.days.bounds): its first period's start to its last period's end; with no
    times for its first period, the start of its day and the start of the next"""
    b, day = bounds((pub or {}).get("model") or {}), datetime.date.fromisoformat(str(x["date"]))
    p, n, midnight = int(c["p"]), int(c.get("n") or 1), at(day, datetime.time())
    if p >= len(b): return midnight, midnight + _DAY
    return midnight + datetime.timedelta(minutes=b[p][0]), midnight + datetime.timedelta(minutes=b[min(p + n, len(b)) - 1][1])


def starts(pub, x, c) -> datetime.datetime:
    """when the cover's lesson starts"""
    return _span(pub, x, c)[0]


def ends(pub, x, c) -> datetime.datetime:
    """when the cover's lesson ends"""
    return _span(pub, x, c)[1]

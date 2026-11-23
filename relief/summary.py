"""One week's relief in numbers, for the relief team's page (relief/tgweb.py) and their weekly message (relief/report.py). Pure: no
Flask, and no file is read.

A relief counts when its cover is dated Monday to Friday of the week, approved (acknowledged or not, or asked to change since) and
has reached its teacher by now (cover.reached), its lesson needed and not stopped by an approved exam or event (cover.stopped), and
its absence not cancelled. It is counted in periods, so that each way of counting adds up to them; absences are the absences that had one; a request to change is counted in
covers, whatever has become of the cover since. What cannot be read (a record, a lesson, a cover) is passed over, alone, its kind
logged to "relief.telegram"; what does not count is not read. Nothing here holds why anyone is away, or anything anybody wrote."""
import collections, datetime, logging, types

from exams.days import bounds
from relief import cover as _cover
from relief import fill as _fill
from relief import words
from relief.calendar import term_of, week_of
from relief.people import people as _people
from relief.tell import APPROVED

DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri")
NO_DEPT = "No department"                       # an absent teacher with none, or not on the timetable any more
SETTLED = ("approved", "changed", "kept", "acknowledged")                # the history entries that end a request to change
_log = logging.getLogger("relief.telegram")


def label(cal, monday):
    """'Week 6 (12–16 Oct)': the week's number counted from the week its term starts in (the earliest term that holds any of Monday
    to Friday); '12–16 Oct' without a term; '28 Sep–2 Oct' over two months"""
    dates = _dates(monday)
    a, b = dates[0], dates[-1]
    said = f"{a.day}–{b.day} {b:%b}" if a.month == b.month else f"{a.day} {a:%b}–{b.day} {b:%b}"
    try:
        term = next((t for t in (term_of(cal, d) for d in dates) if t), None)
        return said if term is None else f"Week {(a - week_of(datetime.date.fromisoformat(term['start']))[0]).days // 7 + 1} ({said})"
    except (AttributeError, KeyError, TypeError, ValueError): return said                # a calendar changed by hand


def _dates(monday):
    return [monday + datetime.timedelta(days=i) for i in range(len(DAYS))]


def _passed_over(e):
    _log.warning("a relief could not be read (%s)", type(e).__name__)


def _when(v):
    """an ISO date-time in school time; anything else raises"""
    if not isinstance(v, str): raise TypeError("not a time")
    return _fill._when(v)


def _request(c):
    """what became of the cover's last request to change: "moved" (approved to another person after it), "kept" (settled with the
    teacher who asked: kept, approved to them again, or they took it after all), "waiting" (for the team); None when nobody asked"""
    history = c.get("history") or []
    asked = [i for i, h in enumerate(history) if h.get("what") == "asked to change"]
    if not asked: return None
    done = [h for h in history[asked[-1] + 1:] if h.get("what") in SETTLED]
    if not done: return "waiting"
    return "kept" if done[-1].get("who") == history[asked[-1]].get("who") else "moved"


def _ack(w, x, c, state):
    """(how it was acknowledged: "on_time" | "late" | "never" | "waiting", as a row says it); on time goes by the minute, as it is said"""
    if state != "acknowledged":                 # asked to change: not acknowledged
        how = "never" if _fill._ended(x, c, w.now, w.bnds) else "waiting"
        return how, how
    at, date, p = _when(c["ack"]["at"]), datetime.date.fromisoformat(x["date"]), int(c["p"])
    start = datetime.timedelta(minutes=w.bnds[p][0]) if p < len(w.bnds) else datetime.timedelta(days=1)      # no times: its day's end
    said = f"{at:%H:%M}" if at.date() == date else f"{words.day(at.date())}, {at:%H:%M}"
    on_time = at.replace(second=0, microsecond=0) <= datetime.datetime.combine(date, datetime.time(), tzinfo=at.tzinfo) + start
    return ("on_time", said) if on_time else ("late", f"late {said}")


def _relief(w, r, x, c):
    """cover c of lesson x as a relief that counts, or None; ahead: it reached its teacher before the lesson's date"""
    state = _cover.state(r, x, c)
    if state not in APPROVED: return None
    _when(c["approved"]["at"])                  # an approval whose time cannot be read is passed over
    if not _cover.reached(r, x, c, w.now, w.settings, w.pub): return None
    p, n, who, absent = int(c["p"]), int(c.get("n") or 1), c["relief"], r["teacher"]
    if p < 0 or n < 1 or not isinstance(who, str) or not isinstance(absent, str): raise ValueError("not a relief")
    how, ack = _ack(w, x, c, state)
    return dict(date=x["date"], p=p, n=n, who=who, absent=absent, lesson=f"{words.class_group(x)} {words.periods_text(c)}",
                ahead=_fill._when(_cover.goes_at(c, x, w.settings, w.pub)).date().isoformat() < x["date"], how=how, ack=ack)


def _covers(w, r):
    """[(relief or None, what became of its request to change or None)] of each cover of the week that can be read"""
    try:
        if r.get("cancelled"): return
        lessons = list(r.get("lessons") or [])
    except Exception as e: return _passed_over(e)
    for x in lessons:
        try:
            if not isinstance(x["date"], str): raise TypeError("no date")
            covers = _cover.covers(x) if x["date"] in w.days and x.get("needed") and not _cover.stopped(w.links, x) else []
            covers = list(covers)
        except Exception as e:
            _passed_over(e)
            continue
        for c in covers:
            try: got = _relief(w, r, x, c), _request(c)
            except Exception as e: _passed_over(e)
            else: yield got


def _most(counts):
    """[(name, periods)], the most first, then by name"""
    return sorted(counts.items(), key=lambda v: (-v[1], v[0]))


def week(pub, settings, records, monday, now, links=None):
    """the week of monday (any date of it, or its ISO string) as it is at now (a date-time or an ISO string) -> dict(start, end: ISO
    Monday and Friday; label; fat_role: whether a Flexi Adjunct role is set; in periods: periods, fat_periods (by whoever has that
    role now; fat_percent, whole, half up), ahead (reached its teacher before the lesson's date) and on_day, on_time (acknowledged by the start
    of the cover's first period), late, never (over and not acknowledged) and waiting (not over), top: [(name, periods)], the three
    with the most, by_dept: [(the absent teacher's first department now, periods)], by_day: {Mon .. Fri: periods}; absences; in
    covers: asked, and of those moved and kept (_request; what still waits for the team is in neither); rows, one a cover by date,
    period and absent teacher: dict(date, lesson, absent, relief, ack: "07:15" | "Mon 12 Oct, 15:20" | "late 09:30" | "never" |
    "waiting")); zeros without a relief. links: what approved exams and events stop (None: nothing)"""
    if isinstance(monday, str): monday = datetime.date.fromisoformat(monday)
    dates = _dates(week_of(monday)[0])
    cal, fat = settings.get("calendar") or {}, settings.get("fat_role") or ""
    w = types.SimpleNamespace(now=_fill._when(now), bnds=bounds((pub or {}).get("model") or {}), links=links, days=dict(zip((d.isoformat() for d in dates), DAYS)),
                              settings=settings, pub=pub)
    covers = [list(_covers(w, r)) for r in records]
    reliefs = sorted((v for got in covers for v, _ in got if v), key=lambda v: (v["date"], v["p"], v["absent"], v["lesson"], v["who"]))
    requests = collections.Counter(q for got in covers for _, q in got if q)
    people = {p["name"]: p for p in _people(pub, [])}

    def by(key):
        out = collections.Counter()
        for v in reliefs: out[key(v)] += v["n"]
        return out

    def dept(v): return next(iter((people.get(v["absent"]) or {}).get("depts") or []), NO_DEPT)
    periods, how, ahead, days = sum(v["n"] for v in reliefs), by(lambda v: v["how"]), by(lambda v: v["ahead"]), by(lambda v: w.days[v["date"]])
    fats = by(lambda v: bool(fat) and (people.get(v["who"]) or {}).get("role") == fat)[True]
    return dict(start=dates[0].isoformat(), end=dates[-1].isoformat(), label=label(cal, dates[0]), fat_role=bool(fat), periods=periods,
                absences=sum(any(v for v, _ in got) for got in covers), fat_periods=fats, fat_percent=(200 * fats + periods) // (2 * periods) if periods else 0,
                ahead=ahead[True], on_day=ahead[False], on_time=how["on_time"], late=how["late"], never=how["never"], waiting=how["waiting"],
                asked=sum(requests.values()), moved=requests["moved"], kept=requests["kept"], top=_most(by(lambda v: v["who"]))[:3], by_dept=_most(by(dept)),
                by_day={d: days[d] for d in DAYS}, rows=[dict(date=v["date"], lesson=v["lesson"], absent=v["absent"], relief=v["who"], ack=v["ack"]) for v in reliefs])

"""When the picks for covers are made, and making them: at once for a lesson today, at the fill time (settings times.fill_at,
15:00) on the school day before for a later date, on "Fill now" (every open cover of a date or of some absences, due or
not), and at once for a request to change.

run keeps nothing in memory: each run reads the published timetable, the settings and the absence records afresh, and a
cover stays open until its pick is saved, so a restart loses nothing (the next run finds every pick still due, and a model
call cut short is simply made again). Each pick is worked out by pick.choose_for outside absences._LOCK (the model is never
called while it is held) and saved by cover.set_pick, which checks again under the lock that the cover is still open and
the person still free: a pick refused there is never saved. One run at a time (_busy). soon() asks for a run from a page,
in a daemon thread (inline when SYNC); start() is the one-minute ticker, which app.py starts only when RELIEF_JOBS=on (the
Dockerfile sets it; tests and local runs never do). Errors are logged to "relief.fill" by their kind alone, never a
record's contents."""
import datetime, logging, os, threading
from zoneinfo import ZoneInfo

import store
from exams.days import bounds
from relief import absences as _absences
from relief import cover as _cover
from relief import lessons as _lessons
from relief import pick as _pick
from relief import settings as _settings
from relief.calendar import school_day

ON = os.environ.get("RELIEF_JOBS") == "on"     # automatic triggers (a new absence, needed again, cancel) run only then
SYNC = False                                    # tests: soon() runs inline
EVERY = 60                                      # seconds between the ticker's runs
FILL_AT = (15, 0)                               # when times.fill_at cannot be read
_busy = threading.Lock()                        # one run at a time
_asked, _asked_lock = set(), threading.Lock()   # the runs soon() asked for that have not started: (ids, date)
_going = [0]                                    # the runs soon() asked for that have started and not ended (under _asked_lock)
_picking = threading.Event()                    # a run is making picks
_stop = threading.Event()                       # ends the ticker (tests)
_ticker = None
_log = logging.getLogger("relief.fill")


def _tz():
    return ZoneInfo(os.environ.get("SCHOOL_TZ") or "Asia/Singapore")


def _date(d):
    return d if isinstance(d, datetime.date) else datetime.date.fromisoformat(str(d))


def _hm(fill_at):
    try:
        h, m = (int(v) for v in str(fill_at).split(":"))
        return datetime.time(h, m)
    except (TypeError, ValueError): return datetime.time(*FILL_AT)


def due_at(cal, days, date, fill_at, today=None):
    """when the picks for lessons on date (a date or an ISO string) are due, in school time: for a date today or earlier
    (today: lessons.today()), the start of that day, so at once; for a later date, fill_at ("15:00") on the school day
    before it in the calendar, over weekends, holidays and the weeks between terms (Friday for a Monday, Thursday when that
    Friday is a holiday); the day before when the calendar has no school day before it"""
    date, tz, one = _date(date), _tz(), datetime.timedelta(days=1)
    if date <= (today or _lessons.today()): return datetime.datetime.combine(date, datetime.time(), tzinfo=tz)
    first = min((_date(t["start"]) for t in cal.get("terms") or []), default=date)
    d = date - one
    while d >= first and school_day(cal, days, d) is None: d -= one
    if d < first: d = date - one
    return datetime.datetime.combine(d, _hm(fill_at), tzinfo=tz)


def _when(now):
    """now (a date-time or an ISO string; None: absences._now()) as a date-time in school time"""
    now = _absences._now() if now is None else now
    if isinstance(now, str): now = datetime.datetime.fromisoformat(now)
    return now.replace(tzinfo=_tz()) if now.tzinfo is None else now.astimezone(_tz())


def _ended(x, c, now, bnds):
    """the cover's lesson is over: dated before now's date, or on it and its last period has ended (exams.days.bounds; a
    period with no times is never over before its day is)"""
    day = now.date().isoformat()
    if x["date"] != day: return x["date"] < day
    p, n = int(c["p"]), int(c.get("n") or 1)
    if p >= len(bnds): return False
    return now.hour * 60 + now.minute >= bnds[min(p + n, len(bnds)) - 1][1]


def _covers(records, ids, date, now, bnds):
    """[(record, lesson, cover, cover key)] of every cover whose lesson is not over, of absences not cancelled (of ids, on
    date, when given), in time order"""
    rows = []
    for r in records:
        if r.get("cancelled") or (ids is not None and r.get("id") not in ids): continue
        for x in r.get("lessons") or []:
            if date is not None and x.get("date") != date: continue
            for i, c in enumerate(_cover.covers(x)):
                if not _ended(x, c, now, bnds):
                    rows.append(((x["date"], int(c["p"]), r.get("at") or "", r["id"], _cover.cover_key(x, i)), r, x, c))
    rows.sort(key=lambda t: t[0])
    return [(r, x, c, k[4]) for k, r, x, c in rows]


def _find(records, id, ckey):
    """(record, lesson, cover) from records, or None when the absence is cancelled or the cover is gone (split or joined)"""
    r = next((r for r in records if r.get("id") == id), None)
    if r is None or r.get("cancelled"): return None
    try: x, c = _cover.find(r, ckey)
    except ValueError: return None
    return r, x, c


def _asks_change(r, x, c):
    """a request to change with no new pick yet"""
    return _cover.state(r, x, c) == "change" and not _cover.new_pick(c)


def _waits(r, x, c):
    """a pick waiting for the team: a waiting cover, or the new pick of a request to change"""
    s = _cover.state(r, x, c)
    return s == "waiting" or (s == "change" and bool(_cover.new_pick(c)))


def _one(pub, settings, id, ckey, call, clock, bnds):
    """the pick for one cover, from fresh records (so it sees every pick before it), worked out outside the lock and saved
    under it; when the save is refused as no longer free (someone took the cover or the person meanwhile), worked out once
    more from fresh records, then left as it is. -> "picked", "nobody" (nobody free; it stays open) or None"""
    for again in (False, True):
        records = _absences.all_records()
        got = _find(records, id, ckey)
        if got is None: return None
        r, x, c = got
        if _ended(x, c, clock(), bnds): return None
        if _cover.state(r, x, c) == "open": into, without = "pick", ()
        elif _asks_change(r, x, c): into, without = "change", (c["relief"],)        # never the teacher who asked
        else: return None
        try: p = _pick.choose_for(pub, settings, records, r, x, c, call=call, without=without)
        except Exception as e:                  # free_then's own, such as a date no longer a school day: this cover waits
            _log.warning("a pick was not made: %s", type(e).__name__); return None
        if p is None: return "nobody"
        try:
            _cover.set_pick(id, ckey, p, pub, settings, into=into)
            return "picked"
        except Exception as e:
            if again or not (isinstance(e, ValueError) and str(e) == _cover.NOT_FREE.format(name=p["who"])):
                _log.warning("a pick was not saved: %s", type(e).__name__); return None
    return None


def _run(ids, date, call, now):
    pub = store.published()
    if not pub: return dict(picked=0, nobody=0)
    settings = _settings.load(pub)
    model = pub.get("model") or {}
    bnds, days, cal = bounds(model), model.get("days") or [], settings.get("calendar") or {}
    fill_at = (settings.get("times") or {}).get("fill_at")
    ids = None if ids is None else {ids} if isinstance(ids, str) else {str(i) for i in ids}
    date = None if date is None else _date(date).isoformat()
    def clock(): return _when(now)              # the time given, else the time now at each step
    # 1. a waiting pick whose person is no longer free goes back to open, and so does the new pick of a request to change
    #    (picked again below), due or not; an approved relief stays (the team changes it)
    records = _absences.all_records()
    for id, ckey in [(r["id"], k) for r, x, c, k in _covers(records, ids, date, clock(), bnds) if _waits(r, x, c)]:
        got = _find(records, id, ckey)
        if got is None or not _waits(*got): continue
        r, x, c = got
        into = "pick" if _cover.state(r, x, c) == "waiting" else "change"
        who = c["relief"] if into == "pick" else _cover.new_pick(c)["who"]
        try:
            if not _cover.stale(pub, settings, records, r, x, c, into=into): continue
            _cover.drop(id, ckey, _cover.NOT_FREE.format(name=who), who=who, into=into)     # not if a planner chose again meanwhile
        except Exception as e:
            _log.warning("a waiting pick was not checked: %s", type(e).__name__); continue
        records = _absences.all_records()
    # 2. the picks: an open cover that is due (any open cover of ids or date, when given), a request to change at once
    t, due = clock(), {}
    def is_due(d):
        if d not in due: due[d] = due_at(cal, days, d, fill_at, today=t.date()) <= t
        return due[d]
    records = _absences.all_records()
    todo = [(r["id"], k) for r, x, c, k in _covers(records, ids, date, t, bnds)
            if (_cover.state(r, x, c) == "open" and (ids is not None or date is not None or is_due(x["date"]))) or _asks_change(r, x, c)]
    picked = nobody = 0
    if todo: _picking.set()
    try:
        for id, ckey in todo:
            got = _one(pub, settings, id, ckey, call, clock, bnds)
            picked += got == "picked"; nobody += got == "nobody"
    finally: _picking.clear()
    return dict(picked=picked, nobody=nobody)


def run(ids=None, date=None, call=None, now=None):
    """make the picks that are due -> dict(picked, nobody): picks saved, and covers left open with nobody free (NOBODY);
    dict(picked=0, nobody=0, busy=True) at once while another run is going. First every waiting pick whose person is no
    longer free is dropped (cover.stale, then cover.drop); then, in time order, every open cover whose lesson is not over
    and whose pick is due (due_at), or with ids (an absence id or ids) or date (a date or an ISO string) every open cover of
    those, due or not; and every request to change with no new pick yet (of ids or date, when given), due or not, for
    someone other than the teacher who asked. A cover whose lesson has ended (exams.days.bounds against school time now) or whose date is before
    today is never picked for. call: the model's stand-in (pick.choose_for's); now: the time (tests)."""
    if not _busy.acquire(blocking=False): return dict(picked=0, nobody=0, busy=True)
    try: return _run(ids, date, call, now)
    finally: _busy.release()


def _queued(key):
    with _busy:                                 # waits for a run that is going (the ticker's, or another): nothing asked for is lost
        with _asked_lock:                       # going before it stops being asked for: filling() stays True throughout
            _going[0] += 1; _asked.discard(key)
        try:
            if SYNC: return _run(key[0], key[1], None, None)
            try: _run(key[0], key[1], None, None)
            except Exception as e: _log.error("the relief run failed: %s", type(e).__name__)
        finally:
            with _asked_lock: _going[0] -= 1


def soon(ids=None, date=None, force=False):
    """ask for a run (ids, date as for run) -> True, or False when it does nothing: an automatic trigger (a new absence,
    needed again, cancel) runs only when RELIEF_JOBS is on (ON); an action a person takes (Fill now, a request to change)
    passes force=True. In a daemon thread named relief-fill that waits for a run already going; inline when SYNC (tests).
    The same run asked for again before it starts is that one run. Never call it holding absences._LOCK."""
    if not (ON or force): return False
    key = (None if ids is None else frozenset({ids} if isinstance(ids, str) else {str(i) for i in ids}),
           None if date is None else _date(date).isoformat())
    with _asked_lock:
        if key in _asked and not SYNC: return True     # a run asked for and not started yet reads the records after this
        _asked.add(key)
    if SYNC: _queued(key)
    else:
        try: threading.Thread(target=_queued, args=(key,), name="relief-fill", daemon=True).start()
        except RuntimeError:                    # no thread to be had: the ticker's next run picks what is due
            with _asked_lock: _asked.discard(key)
            raise
    return True


def filling():
    """a run asked for (Fill now, a new absence, a request to change) has not ended, from the moment it is asked, or the
    ticker's run is making picks: the Today page says "Being picked" and fetches again"""
    with _asked_lock: asked = bool(_asked) or _going[0] > 0
    return asked or _picking.is_set()


def tick(now=None):
    """one run of the ticker; every error is caught and logged by its kind alone -> run's answer, or None"""
    try: return run(now=now)
    except Exception as e:
        _log.error("the relief run failed: %s", type(e).__name__)
        return None


def _loop(every):
    while not _stop.wait(every): tick()


def start(every=EVERY):
    """the ticker: a daemon thread named relief-ticker calling tick() every `every` seconds, the first a minute after it
    starts; started once (app.py, when RELIEF_JOBS=on)"""
    global _ticker
    if _ticker is not None and _ticker.is_alive(): return _ticker
    _stop.clear()
    _ticker = threading.Thread(target=_loop, args=(every,), name="relief-ticker", daemon=True)
    _ticker.start()
    return _ticker

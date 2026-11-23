"""What the relief team is told by the clock on Telegram, and Remind.

tick (every minute: tell.MINUTE) has two parts, the report and the weekly summary. They go by the bot, the timetable and the settings
as they are read once; each has its own try, so neither stops the other.

The report says which of today's approved reliefs nobody has acknowledged, at round times: every
report_every minutes of the relief settings, counted from midnight, from BEFORE minutes before the first period starts
(exams.days.bounds). The mark is the last such time at or before now, so a tick a little late, or after a restart, still says it
once; what is written in it is the time now. A mark is done with once it has been worked out (state report_last:{date}, raised
before anything is queued, in one step, so two copies of the app never do the same one), whether there was anything to say or
not: what is approved after it waits for the next. Nothing is kept in memory.

A relief counts while its cover is dated today and approved, its absence not cancelled, its lesson needed, and no approved exam or
event stops it (cover.stopped). It waits while its teacher has neither acknowledged it nor asked to change it and its first period
has not started; once that has, it is listed as started without acknowledgement, once, and waits no more: state started:{relief
key} keeps the mark of the report that listed it, and it is listed again when no copy of that report went or may still go (all
dropped or failed, or none was queued before the app stopped). report:{date}:{HHMM of the mark}:{name} goes to each of the team
who can be reached, when a relief waits or has just started; its button reminds those it lists as waiting. When none waits and a
report went since the last all clear, clear:{date}:{n}:{name} goes instead, the n-th that day: all are acknowledged, or how many
started without. It waits while a request to change of a lesson still to start is with the team, since neither would be true, and
while an absence, or a lesson or cover of today in one, cannot be read (what can be is reported): it may hold a relief that waits.
While the exams, or today in them, cannot be read (tell.known) no lesson counts as stopped, nothing is said to have started and
there is no all clear: one may be stopped.

A line says when the teacher was told (tell.Said; the day too, when it was not today) and, when they cannot be reached any more, that
they are not on Telegram now; or that they have not been told, or are not on Telegram; never why anyone is away.
Both messages are dropped when they are OLD, when one of a later mark is there for that person (an old one never follows a newer),
or when their person is not on the team any more (tell.CHECKS).

The weekly summary (relief/summary.py's numbers of one week) goes at weekly_day weekly_at of the relief settings (WEEKLY where they
cannot be read), whatever kind of day that is, and until a DAY after; later than that it is not sent at all. On a Friday it is about
that week, else about the week before. A week is done with as a mark is (state weekly_last: its Monday's ordinal), also when it had no
relief: nothing is sent then. While nobody on the team can be reached, the accounts or the exams cannot be read, or there is no relief
and an absence's file cannot be read (it may hold one), it is not done with; a date of the exams that cannot be read stops no lesson of
it (tell.known). weekly:{monday}:{name} goes to each of the team who can be reached, with a button that opens the page on that week,
and is dropped when it is a DAY old, or when its person is not on the team any more.

remind sends a relief again to its teacher, for the page (relief/tgweb.py) and for the button (relief/bot.py): its message as it
would be made now, under the relief's key with :r{n} after it, WAIT at least after the last of that relief's messages went or was
queued. An earlier reminder that still waits is dropped then, so that they do not come all at once; a relief told to nobody yet
gets the message itself. Two at once are one: a key is queued once. What was reminded is one history entry.

The records are read as the sweep reads them, under absences._LOCK (a takeover is two saves), so that a file that cannot be read
is known; remind reads absences.all_records, since it says nothing of what it cannot find but that nobody is to be reminded, and a
press waits for nobody's save.

tick never raises; what cannot be read is passed over. Failures are logged to "relief.telegram" by their kind alone."""
import datetime, logging, os, sqlite3, types

import store
from accounts import people as _accounts
from accounts import rights as _rights
from exams.days import bounds, hhmm
from relief import absences as _absences
from relief import cover as _cover
from relief import fill as _fill
from relief import links as _links
from relief import outbox, tell, tgdb
from relief import settings as _settings
from relief import summary as _summary
from relief import web as _web
from relief import words
from relief.calendar import school_day, week_of

BEFORE, EVERY = 60, 15                          # minutes: the first report before the first period; between two, when the settings cannot be read
OLD = datetime.timedelta(minutes=30)            # a report or an all clear this old does not go any more
WAIT = datetime.timedelta(minutes=5)            # a relief is not sent again sooner
WEEKLY, DAY = ("Fri", "15:00"), datetime.timedelta(days=1)               # when the summary goes, where the settings cannot be read; how long after that it may
AGAIN, OPEN_TODAY, OPEN_SUMMARY = "Remind them again", "Open relief today", "Open the full summary"
NOBODY = "Nobody to remind."
NOT_ON = "Not on Telegram."
TOO_SOON = "Sent at {at}: wait a few minutes."                   # the last of a relief's messages (itself, or a reminder of it) went
TRIED = "Last tried at {at}: wait a few minutes."                # ... or may have gone, waits in the queue or is on its way
_log = logging.getLogger("relief.telegram")


# ---- the texts (the plan's messages)
def report_text(hm, waiting, started):
    """each of waiting and started: dict(who, lesson, periods, start ("" without times), how: "sent 07:20" and the like)"""
    lines = [f"⏰ {hm} · Not yet acknowledged ({len(waiting)})"]
    lines += [" · ".join([f"• {v['who']}", f"{v['lesson']} {v['periods']}"] + ([f"starts {v['start']}"] if v["start"] else []) + [v["how"]]) for v in waiting]
    if started: lines += ["Started without acknowledgement:"] + [f"• {v['who']} · {v['lesson']} {v['periods']}{tell._from(v['start'])}" for v in started]
    return "\n".join(lines)


def clear_text(hm, n, k):
    """n: today's approved reliefs; k: how many of them started and were never acknowledged"""
    if k: return f"✅ {hm} · No reliefs are waiting now: {k} started without acknowledgement."
    return f"✅ {hm} · " + (f"All {n} reliefs for today are acknowledged." if n != 1 else "The 1 relief for today is acknowledged.")


def summary_text(v):
    """v: summary.week's"""
    few = lambda pairs: " · ".join(f"{name} {n}" for name, n in pairs)
    some = lambda n, what: f"{n} {what}" if n == 1 else f"{n} {what}s"
    asked, depts = v["asked"], v["by_dept"]
    lines = [f"📊 Relief summary · {v['label']}", f"{some(v['periods'], 'relief period')} for {some(v['absences'], 'absence')}"]
    if v["fat_role"]: lines.append(f"• Flexi Adjuncts covered {v['fat_periods']} ({v['fat_percent']}%)")
    lines += [f"• Planned ahead {v['ahead']} · arranged on the day {v['on_day']}",
              f"• Acknowledged on time {v['on_time']} · late {v['late']} · never {v['never']}" + (f" · waiting {v['waiting']}" if v["waiting"] else ""),
              f"• Asked to change {asked}" + (f" ({'all' if v['moved'] == asked else v['moved']} moved)" if asked else ""),
              "Most relief this week:", few(v["top"]), "By department of the absent teacher:",
              few(depts[:3] + ([("others", sum(n for _, n in depts[3:]))] if depts[3:] else []))]
    return "\n".join(lines)


# ---- what both parts of tick go by
def _common(now):
    """the bot, the timetable and the settings as they are now; None while nothing can be told: not connected, or nothing published
    (a publish swaps folders)"""
    bot = _links.connected()                    # None without a token too
    pub = store.published() if bot else None
    return types.SimpleNamespace(bot=bot, pub=pub, now=_fill._when(now), settings=_settings.load(pub)) if pub else None


def _team(pub):
    """({name: chat} of everyone who can be reached, the names of the team among them)"""
    reach = _links.reachable(pub)
    return reach, sorted(p["name"] for p in _accounts.staff(pub) if p["name"] in reach and "relief.team" in _rights.rights(p, _links.VIA))


# ---- the report and all clear
def _mark(now, settings, bnds):
    """the last round time at or before now, in minutes of the day, or None before the reports begin"""
    times = settings.get("times")
    every = times.get("report_every") if isinstance(times, dict) else None
    if not _settings._int_in(every, 5, 60): every = EVERY
    minute = now.hour * 60 + now.minute
    mark = minute - minute % every
    return mark if bnds and mark >= bnds[0][0] - BEFORE else None


def _starts(c, bnds):
    """the minute of the day the cover's first period starts; one past the day's last period, when that ends"""
    p = int(c["p"])
    return bnds[p][0] if p < len(bnds) else bnds[-1][1]


def _how(w, who, key):
    """when the relief's teacher was told of it (the day too, when not today), and whether they can be reached still; or that they
    have not been told"""
    at, reached = w.said.sent_at(key), who in w.reach
    if not at: return "not told yet" if reached else "not on Telegram"
    sent = f"sent {at:%H:%M}" if at.date() == w.now.date() else f"sent {at:%a %H:%M}"
    return sent if reached else f"{sent} · not on Telegram now"


def _records():
    """tell._records, none of a save that is two half done; ([], {}) before there was any absence"""
    with _absences._LOCK: return tell._records() if os.path.isdir(_absences.DIR) else ([], {})


def _relief(w, r, x, i, c):
    """cover c (the i-th) of lesson x as a relief that counts, or None"""
    s = _cover.state(r, x, c)
    if s not in tell.APPROVED: return None
    ckey, who, starts = _cover.cover_key(x, i), c["relief"], _starts(c, w.bnds)
    if not isinstance(who, str): raise ValueError("no name")
    key = tell.key_of(w.said.told, r, c, ckey)
    return dict(who=who, lesson=words.class_group(x), periods=words.periods_text(c), start=words.times(w.pub, x, c)[0], how=_how(w, who, key), state=s, key=key,
                starts=starts, over=w.now.hour * 60 + w.now.minute >= starts, cover=dict(id=r["id"], ckey=ckey, absent=r["teacher"], approved_at=c["approved"].get("at")))


def _passed_over(w, e):
    w.passed += 1
    _log.warning("a relief could not be read (%s)", type(e).__name__)


def _reliefs(w, r):
    """the reliefs of an absence that count: dict(who, lesson, periods, start, how, state, key, starts, over: it has started,
    cover: what reminds of it); each lesson and cover that cannot be read is passed over, alone, and counted (w.passed)"""
    if r.get("cancelled"): return
    lessons = r.get("lessons") or []
    if not isinstance(lessons, list): return _passed_over(w, TypeError())
    for x in lessons:
        try:
            if not isinstance(x["date"], str): raise TypeError("no date")
            covers = list(enumerate(_cover.covers(x))) if x["date"] == w.date and not _cover.stopped(w.links, x) else []
        except Exception as e:
            _passed_over(w, e)
            continue
        for i, c in covers:
            try: v = _relief(w, r, x, i, c)
            except Exception as e: _passed_over(w, e)
            else:
                if v: yield v


def _went(date):
    """the marks of the day whose report went, or may still, to anybody"""
    return [t["ref"]["mark"] for t in outbox.told_for(f"report:{date}:").values() if t["state"] in tell.LIVE]


def _listed(w, v):
    """the relief was said to have started, in a report that went or may still (true: as it was kept before its mark was)"""
    mark = tgdb.get_state(f"started:{v['key']}")
    return mark is not None and (mark is True or mark in w.went)


def _spell(w):
    """the number of the all clear there is to say once no relief waits; None when no report went since the last one"""
    clears = [t["ref"] for t in outbox.told_for(f"clear:{w.date}:").values()]
    if not w.went or any(c["mark"] >= max(w.went) for c in clears): return None
    return 1 + max((c["n"] for c in clears), default=0)


def _to_each(names, kind, key, text, buttons, ref):
    """the message queued for each of names -> the keys"""
    out = []
    for name in names:
        try:
            if outbox.queue(f"{key}:{name}", name, text, kind=kind, buttons=buttons, ref=ref): out.append(f"{key}:{name}")
        except Exception as e:
            _log.error("a message could not be queued (%s)", type(e).__name__)
            if isinstance(e, sqlite3.OperationalError): break            # the store fails: the rest would too
    if out: outbox.wake()
    return out


def _report(s):
    bot, pub, now, settings, model = s.bot, s.pub, s.now, s.settings, s.pub.get("model") or {}
    date, bnds, cal = now.date().isoformat(), bounds(model), settings.get("calendar") or {}
    mark, last = _mark(now, settings, bnds), f"report_last:{date}"
    if mark is None or school_day(cal, model.get("days") or [], now.date()) is None: return []
    was = tgdb.get_state(last)
    if isinstance(was, int) and was >= mark: return []
    reach, team = _team(pub)
    if not team: return []                      # nobody to tell: the mark is not done with
    w = types.SimpleNamespace(pub=pub, now=now, date=date, bnds=bnds, reach=reach, links=tell.known(_fill._links(pub, cal), date), said=tell.said(), went=_went(date))
    records, unread = _records()
    w.passed = len(unread)
    rows = sorted((v for r in records for v in _reliefs(w, r)), key=lambda v: (v["starts"], v["who"], v["key"]))
    waiting = [v for v in rows if v["state"] == "approved" and not v["over"]]
    started = [v for v in rows if v["state"] == "approved" and v["over"] and not _listed(w, v)] if w.links is not None else []
    text, ref = None, dict(date=date, mark=mark, made=now.isoformat(timespec="seconds"))
    if waiting or started:
        text = report_text(f"{now:%H:%M}", waiting, started)
        buttons = [[dict(text=AGAIN, what="remind", extra=dict(date=date, covers=[v["cover"] for v in waiting]))]] if waiting else []
        buttons.append([dict(text=OPEN_TODAY, url=(bot.get("base") or "") + "/relief#today")])
        kind, key = "report", f"report:{date}:{hhmm(mark).replace(':', '')}"
    elif rows and w.links is not None and not w.passed and not any(v["state"] == "change" and not v["over"] for v in rows):
        n = _spell(w)
        if n is not None:
            text = clear_text(f"{now:%H:%M}", len(rows), sum(v["state"] != "acknowledged" for v in rows))
            kind, key, buttons, ref = "clear", f"clear:{date}:{n}", [], dict(ref, n=n)
    if not tgdb.raise_state(last, mark, [f"started:{v['key']}" for v in started]) or text is None: return []
    return _to_each(team, kind, key, text, buttons, ref)


# ---- the weekly summary
def _week_due(now, settings):
    """the Monday of the week whose summary is to go now, or None"""
    times = settings.get("times")
    day, at = (times.get("weekly_day"), times.get("weekly_at")) if isinstance(times, dict) else WEEKLY
    if day not in _summary.DAYS: day = WEEKLY[0]
    if not isinstance(at, str) or not _settings._TIME.match(at): at = WEEKLY[1]
    week = datetime.timedelta(days=7)
    sent = datetime.datetime.combine(now.date(), _fill._hm(at), tzinfo=now.tzinfo) - datetime.timedelta(days=(now.weekday() - _summary.DAYS.index(day)) % 7)
    if sent > now: sent -= week                 # the last time it was to go
    if now - sent >= DAY: return None
    return week_of(sent.date() if day == "Fri" else sent.date() - week)[0]


def _weekly(s):
    monday = _week_due(s.now, s.settings)
    if monday is None: return []
    was, iso = tgdb.get_state("weekly_last"), monday.isoformat()
    if isinstance(was, int) and was >= monday.toordinal(): return []
    team = _team(s.pub)[1]
    links = _fill._links(s.pub, s.settings.get("calendar") or {}) if team else None
    if links is None: return []                 # nobody to tell, or not known what was stopped: the week is not done with
    records, unread = _records()
    for kind in sorted(set(unread.values())): _log.warning("an absence could not be read (%s)", kind)
    v = _summary.week(s.pub, s.settings, records, monday, s.now, links=types.SimpleNamespace(stopped=lambda x: tell._stopped(links, x)))
    if unread and not v["periods"]: return []   # what cannot be read may hold the week's reliefs: not done with
    text = summary_text(v)
    if not tgdb.raise_state("weekly_last", monday.toordinal()) or not v["periods"]: return []
    button = dict(text=OPEN_SUMMARY, url=f"{s.bot.get('base') or ''}/relief?week={iso}#summary")
    return _to_each(team, "weekly", f"weekly:{iso}", text, [[button]], dict(monday=iso, made=s.now.isoformat(timespec="seconds")))


def _weekly_fresh(ref, name):
    """a summary: not a DAY old, and its person on the team still"""
    return _fill._when(None) - tell._time(ref["made"]) < DAY and tell._on_team(name)


# ---- every minute
def tick(now=None):
    """the report, or the all clear, of the mark there is now, and the weekly summary, when there is one to send -> the keys queued.
    now: the time (tests), else absences._now(). Never raises"""
    out, s = [], None
    try: s = _common(now)
    except Exception as e: _log.error("the report could not be worked out (%s)", type(e).__name__)
    parts = (("the report", _report), ("the weekly summary", _weekly)) if s else ()
    for what, part in parts:
        try: out += part(s)
        except Exception as e: _log.error("%s could not be worked out (%s)", what, type(e).__name__)
    return out


def _fresh(ref, name):
    """a report or an all clear: not OLD, none of a later mark of the day there for its person, and they are on the team still"""
    if _fill._when(None) - tell._time(ref["made"]) >= OLD or not tell._on_team(name): return False
    return not any(t["name"] == name and t["state"] in tell.LIVE and t["ref"]["mark"] > ref["mark"]
                   for kind in ("report", "clear") for t in outbox.told_for(f"{kind}:{ref['date']}:").values())


tell.CHECKS.update(report=_fresh, clear=_fresh, weekly=_weekly_fresh)


# ---- Remind
def asked(covers):
    """the covers to remind of, [dict(id, ckey)] with absent and approved_at when known, else WRONG"""
    if not isinstance(covers, list): raise ValueError(_absences.WRONG)
    for v in covers:
        if not isinstance(v, dict) or not all(isinstance(v.get(k), str) and v[k] for k in ("id", "ckey")): raise ValueError(_absences.WRONG)
    return covers


def _cover_asked(w, v):
    """(record, lesson, cover) of a cover asked for, approved to anyone: in the absence given, else (an exam's takeover moved it)
    in another of the same teacher's; None when there is none"""
    absent = v.get("absent") or next((r.get("teacher") for r in w.records if r["id"] == v["id"]), None)
    return tell._holder(w.records, dict(id=v["id"], ckey=v["ckey"], absent=absent)) if isinstance(absent, str) else None


def _remindable(w, v, r, x, c):
    """the cover is one to remind of: dated the date, waiting to be acknowledged (as it was listed, when that is said), its lesson
    neither over nor stopped"""
    if _cover.state(r, x, c) != "approved" or x["date"] != w.date or v.get("approved_at") not in (None, c["approved"].get("at")): return False
    return not _cover.stopped(w.links, x) and not _fill._ended(x, c, w.now, w.bnds)


def _too_soon(when, state):
    """what is said of a relief whose last message was then, in that state"""
    return (TOO_SOON if state == "sent" else TRIED).format(at=f"{when:%H:%M}")


def _send_again(w, v):
    """one cover asked for -> (its relief teacher or None, why they are not reminded: None when they are)"""
    got = _cover_asked(w, v)
    if got is None: return None, NOBODY
    r, x, c = got
    who = c["relief"]
    if not _remindable(w, v, r, x, c): return who, NOBODY
    if who not in w.reach: return who, NOT_ON
    item = tell.relief_item(w.pub, w.reach, w.said.told, r, x, c, v["ckey"])
    if item is None: return who, NOBODY         # approved at no time (changed by hand)
    key, last = item["key"], w.said.last(item["key"])
    if last is not None and w.now - last[0] <= WAIT: return who, _too_soon(*last)
    if tell._there(w.said.told, key):           # else it was never queued, or dropped: the message itself, as the sweep would
        n = 1 + max(w.said.copies(key), default=0)
        item = dict(item, key=f"{key}:r{n}", ref=dict(item["ref"], n=n))
    if not outbox.queue(item["key"], who, item["text"], kind="relief", buttons=item["buttons"], files=item["files"], ref=item["ref"]):
        t = outbox.told(item["key"])            # somebody else was first (a key is queued once); else they have no Telegram by now
        return who, _too_soon(tell._time(t["at"]), t["state"]) if t and t["state"] != "dropped" else NOT_ON
    for n, t in w.said.copies(key).items():
        if t["state"] == "queued": outbox.drop(f"{key}:r{n}")            # if it still is
    return who, None


def _remind(date, covers, now, done, skipped):
    pub = store.published()
    if not pub: raise ValueError(_web.NO_PUB)
    cal = _settings.load(pub).get("calendar") or {}
    w = types.SimpleNamespace(pub=pub, now=_fill._when(now), date=date, bnds=bounds(pub.get("model") or {}), reach=_links.reachable(pub), links=tell.known(_fill._links(pub, cal), date),
                              records=_absences.all_records(), said=tell.said())
    for v in covers:
        try: who, why = _send_again(w, v)
        except Exception as e:
            if isinstance(e, sqlite3.OperationalError): raise            # the store fails: the rest would too
            _log.warning("a reminder could not be made (%s)", type(e).__name__)
            who, why = _who(w, v), NOBODY
        if why is None: done.append(who)
        else: skipped.append(dict(ckey=v["ckey"], name=who, why=why))


def _who(w, v):
    try: return _cover_asked(w, v)[2]["relief"]
    except Exception: return None


def remind(date, covers, by, now=None):
    """each relief of covers (as asked says) that waits to be acknowledged sent again to its teacher, when its lesson is dated date
    (a date or an ISO string), neither over nor stopped -> dict(sent: how many, skipped=[dict(ckey, name, why)]), the others, why:
    NOBODY (none there, answered, another's by now), NOT_ON, or TOO_SOON or TRIED (_too_soon). by: (name, "telegram"), or None for
    whoever is signed in; one history entry by them. WRONG for what is not a date or covers; now: the time (tests), else
    absences._now()"""
    covers = asked(covers)
    if not isinstance(date, datetime.date): date = _web._date_in(date)
    done, skipped = [], []
    try:
        _remind(date.isoformat(), covers, now, done, skipped)
    finally:
        if done:                                # whatever failed after it
            outbox.wake()
            n = len(set(done))
            _web._noted("reminded", None, f"Reminded {n} relief {'teacher' if n == 1 else 'teachers'} on {words.day(date.isoformat())}", by=by)
    return dict(sent=len(done), skipped=skipped)

"""What the relief team is told by the clock on Telegram, and Remind.

tick (every minute: tell.MINUTE) says which of today's approved reliefs nobody has acknowledged, at round times: every
report_every minutes of the relief settings, counted from midnight, from BEFORE minutes before the first period starts
(exams.days.bounds). The mark is the last such time at or before now, so a tick a little late, or after a restart, still says it
once; what is written in it is the time now. A mark is done with once it has been worked out (state report_last:{date}, raised
before anything is queued, in one step, so two copies of the app never do the same one), whether there was anything to say or
not: what is approved after it waits for the next. Nothing is kept in memory.

A relief counts while its cover is dated today and approved, its absence not cancelled, its lesson needed, and no approved exam or
event stops it (cover.stopped). It waits while its teacher has neither acknowledged it nor asked to change it and its first period
has not started; once that has, it is listed as started without acknowledgement, once (state started:{relief key}), and waits no
more. report:{date}:{HHMM of the mark}:{name} goes to each of the team who can be reached, when a relief waits or has just
started; its button reminds those it lists as waiting. When none waits and a report went since the last all clear,
clear:{date}:{n}:{name} goes instead, the n-th that day: all are acknowledged, or how many started without. It waits while a
request to change of a lesson still to start is with the team, since neither would be true. While the exams cannot be read no
lesson counts as stopped, and nothing is said to have started, nor all clear over it: it may be stopped.

A line says when the teacher was told (tell.Said), or that they have not been, or are not on Telegram; never why anyone is away.
Both messages are dropped when they are OLD, or their person is not on the team any more (tell.CHECKS).

remind sends a relief again to its teacher, for the page (relief/tgweb.py) and for the button (relief/bot.py): its message as it
would be made now, under the relief's key with :r{n} after it, WAIT at least after the last of that relief's messages went or was
queued. An earlier reminder that still waits is dropped then, so that they do not come all at once; a relief told to nobody yet
gets the message itself. Two at once are one: a key is queued once. What was reminded is one history entry.

tick never raises; a record that cannot be read is passed over. Failures are logged to "relief.telegram" by their kind alone."""
import datetime, logging, sqlite3, types

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
from relief import web as _web
from relief import words
from relief.calendar import school_day

BEFORE, EVERY = 60, 15                          # minutes: the first report before the first period; between two, when the settings cannot be read
OLD = datetime.timedelta(minutes=30)            # a report or an all clear this old does not go any more
WAIT = datetime.timedelta(minutes=5)            # a relief is not sent again sooner
AGAIN, OPEN_TODAY = "Remind them again", "Open relief today"
NOBODY = "Nobody to remind."
NOT_ON = "Not on Telegram."
TOO_SOON = "Reminded at {at}: wait a few minutes."
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
    at = w.said.sent_at(key)
    return f"sent {at:%H:%M}" if at else "not told yet" if who in w.reach else "not on Telegram"


def _reliefs(w, r):
    """the reliefs of an absence that count: dict(who, lesson, periods, start, how, state, key, starts, over: it has started,
    cover: what reminds of it)"""
    for x in r.get("lessons") or []:
        if x.get("date") != w.date or _cover.stopped(w.links, x): continue
        for i, c in enumerate(_cover.covers(x)):
            s = _cover.state(r, x, c)
            if s not in tell.APPROVED: continue
            ckey, who, starts = _cover.cover_key(x, i), c["relief"], _starts(c, w.bnds)
            if not isinstance(who, str): raise ValueError("no name")
            key = tell.key_of(w.said.told, r, c, ckey)
            yield dict(who=who, lesson=words.class_group(x), periods=words.periods_text(c), start=words.times(w.pub, x, c)[0], how=_how(w, who, key), state=s, key=key,
                       starts=starts, over=w.now.hour * 60 + w.now.minute >= starts, cover=dict(id=r["id"], ckey=ckey, absent=r["teacher"], approved_at=c["approved"].get("at")))


def _spell(date):
    """the number of the all clear there is to say once no relief waits; None when no report went since the last one"""
    went = [t["ref"]["mark"] for t in outbox.told_for(f"report:{date}:").values() if t["state"] not in ("dropped", "failed")]
    clears = [t["ref"] for t in outbox.told_for(f"clear:{date}:").values()]
    if not went or any(c["mark"] >= max(went) for c in clears): return None
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


def _tick(now):
    bot = _links.connected()                    # None without a token too
    pub = store.published() if bot else None
    if not pub: return []                       # nothing published (a publish swaps folders): the next tick
    now, model, settings = _fill._when(now), pub.get("model") or {}, _settings.load(pub)
    date, bnds, cal = now.date().isoformat(), bounds(model), settings.get("calendar") or {}
    mark, last = _mark(now, settings, bnds), f"report_last:{date}"
    if mark is None or school_day(cal, model.get("days") or [], now.date()) is None: return []
    was = tgdb.get_state(last)
    if isinstance(was, int) and was >= mark: return []
    reach = _links.reachable(pub)
    team = sorted(p["name"] for p in _accounts.staff(pub) if p["name"] in reach and "relief.team" in _rights.rights(p, _links.VIA))
    if not team: return []                      # nobody to tell: the mark is not done with
    w = types.SimpleNamespace(pub=pub, now=now, date=date, bnds=bnds, reach=reach, links=_fill._links(pub, cal), said=tell.said())
    rows = sorted(tell._each(_absences.all_records(), lambda r: _reliefs(w, r)), key=lambda v: (v["starts"], v["who"], v["key"]))
    waiting = [v for v in rows if v["state"] == "approved" and not v["over"]]
    unlisted = [v for v in rows if v["state"] == "approved" and v["over"] and not tgdb.get_state(f"started:{v['key']}")]
    started = unlisted if w.links is not None else []
    text, ref = None, dict(date=date, mark=mark, made=now.isoformat(timespec="seconds"))
    if waiting or started:
        text = report_text(f"{now:%H:%M}", waiting, started)
        buttons = [[dict(text=AGAIN, what="remind", extra=dict(date=date, covers=[v["cover"] for v in waiting]))]] if waiting else []
        buttons.append([dict(text=OPEN_TODAY, url=(bot.get("base") or "") + "/relief#today")])
        kind, key = "report", f"report:{date}:{hhmm(mark).replace(':', '')}"
    elif rows and not unlisted and not any(v["state"] == "change" and not v["over"] for v in rows):
        n = _spell(date)
        if n is not None:
            text = clear_text(f"{now:%H:%M}", len(rows), sum(v["state"] != "acknowledged" for v in rows))
            kind, key, buttons, ref = "clear", f"clear:{date}:{n}", [], dict(ref, n=n)
    if not tgdb.raise_state(last, mark, [f"started:{v['key']}" for v in started]) or text is None: return []
    return _to_each(team, kind, key, text, buttons, ref)


def tick(now=None):
    """the report, or the all clear, of the mark there is now, when there is one to send -> the keys queued. now: the time (tests),
    else absences._now(). Never raises"""
    try: return _tick(now)
    except Exception as e:
        _log.error("the report could not be worked out (%s)", type(e).__name__)
        return []


def _fresh(ref, name):
    """a report or an all clear: not OLD, and its person on the team still"""
    return _fill._when(None) - tell._time(ref["made"]) < OLD and tell._on_team(name)


tell.CHECKS.update(report=_fresh, clear=_fresh)


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
    if last is not None and w.now - last <= WAIT: return who, TOO_SOON.format(at=f"{last:%H:%M}")
    if tell._there(w.said.told, key):           # else it was never queued, or dropped: the message itself, as the sweep would
        n = 1 + max(w.said.copies(key), default=0)
        item = dict(item, key=f"{key}:r{n}", ref=dict(item["ref"], n=n))
    if not outbox.queue(item["key"], who, item["text"], kind="relief", buttons=item["buttons"], files=item["files"], ref=item["ref"]):
        t = outbox.told(item["key"])            # somebody else was first (a key is queued once); else they have no Telegram by now
        return who, TOO_SOON.format(at=f"{tell._time(t['at']):%H:%M}") if t and t["state"] != "dropped" else NOT_ON
    for n, t in w.said.copies(key).items():
        if t["state"] == "queued": outbox.drop(f"{key}:r{n}")            # if it still is
    return who, None


def _remind(date, covers, now, done, skipped):
    pub = store.published()
    if not pub: raise ValueError(_web.NO_PUB)
    cal = _settings.load(pub).get("calendar") or {}
    w = types.SimpleNamespace(pub=pub, now=_fill._when(now), date=date, bnds=bounds(pub.get("model") or {}), reach=_links.reachable(pub), links=_fill._links(pub, cal),
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
    NOBODY (none there, answered, another's by now), NOT_ON, or TOO_SOON. by: (name, "telegram"), or None for whoever is signed in;
    one history entry by them. WRONG for what is not a date or covers; now: the time (tests), else absences._now()"""
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

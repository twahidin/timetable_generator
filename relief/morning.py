"""The morning message: on a duty day (hours.duty_day), at the morning time of the relief settings, one message on Telegram to each
person on duty (hours.on_duty: stage 1, the whole relief team who can be reached) with everything that waits for today. A person
on duty who is away the whole day today (an absence of theirs, not cancelled, not an exam's or event's backup, dated today, with no
periods: _away_all_day) gets none; one away for some periods only does. When that would leave nobody, it goes to all on duty (a
message nobody gets is worse than one to a person away). Their own absence is counted and named in it as any other.

tick (every minute: tell.MINUTE, after relief/report.py's) makes it. The day is claimed (state morning_last, the day's ordinal,
raised by tgdb.raise_state before anything is queued, in one step) so that a restart or a second copy of the app never makes it
twice; it is claimed when there is nothing to cover too, and then nothing is sent. If the app was down at the morning time it goes
when the app is back, until the cut-off; after the cut-off it is not made for that day. While nobody on duty can be reached the
day is not claimed. morning:{date}:{name} goes to each, with the button Open Today's Relief Assignments, and is dropped when its day is not
today any more, once the cut-off has come, or when its person is not on the team any more (tell.CHECKS).

counts counts every cover of today that needs relief (fill._covers: its lesson needed and not over, of an absence not cancelled,
an exam's or event's backup too), not stopped as far as is known (tell._stopped), whatever its state, by the plan's Decision 12:
waiting for approval (a pick, or a request to change with a new pick), approved and not sent out, sent out and held (with the
time the first of them goes), with nobody free (open), and sent out already (reached its teacher, acknowledged or not, or asked
to change with no new pick). It is made from the records that can be read: a damaged file, or a lesson in one, is logged by kind
and passed over. It names who is away and for which periods, nothing else of them: never the reason or its kind.

tick never raises. Failures are logged to "relief.telegram" by their kind alone."""
import logging

import store
from exams.days import bounds
from relief import cover as _cover
from relief import fill as _fill
from relief import hours as _hours
from relief import report as _report
from relief import settings as _settings
from relief import tell, tgdb, words

AWAY = 8                                        # how many people away are named
_log = logging.getLogger("relief.telegram")


# ---- the text (the plan's message)
def morning_text(day, absences, lessons, waiting, unsent, held, at, nobody, already, away) -> str:
    """at: when the first held relief goes ("06:45"); away: ["Ms Evelyn Koh (whole day)", ...]; a line is left out at 0"""
    some = lambda n, what: f"{n} {what}" if n == 1 else f"{n} {what}s"
    lines = [f"☀️ Relief today · {day}", f"{some(absences, 'absence')} · {some(lessons, 'lesson')} to cover"]
    for n, line in ((waiting, "waiting for your approval"), (unsent, "approved, not sent out"), (held, f"sent out: will go at {at}"),
                    (nobody, "with nobody free: choose someone in the app"), (already, "sent out already")):
        if n: lines.append(f"• {n} {line}")
    if away: lines.append("Away: " + " · ".join(away[:AWAY]) + (f" · and {len(away) - AWAY} more" if len(away) > AWAY else ""))
    return "\n".join(lines)


# ---- what waits for today
def _what(r, x, c, now, settings, pub):
    """which line of the message the cover is counted in"""
    s = _cover.state(r, x, c)
    if s == "open": return "nobody"
    if s == "waiting" or (s == "change" and _cover.new_pick(c)): return "waiting"
    if _cover.sent_out(c) is None: return "unsent"
    return "already" if _cover.reached(r, x, c, now, settings, pub) else "held"


def counts(pub, settings, records, now, links) -> dict:
    """dict(absences, lessons, waiting, unsent, held, at, nobody, already, away) of today's covers that need relief (above); a
    record that cannot be read is passed over, its kind logged"""
    now = _fill._when(now)
    today, bnds = now.date().isoformat(), bounds((pub or {}).get("model") or {})
    out, held, away, n = dict(waiting=0, unsent=0, held=0, nobody=0, already=0), [], {}, 0
    for r in records:
        try:
            got = [(_what(r, x, c, now, settings, pub), x, c) for _, x, c, _k in _fill._covers([r], None, today, now, bnds) if x.get("needed") and not tell._stopped(links, x)]
            goes = [_cover.goes_at(c, x, settings, pub) for what, x, c in got if what == "held"]
            first = min(((x["date"], int(c["p"])) for _, x, c in got), default=None)
            name = f"{r['teacher']} ({words.away(r)})"
        except Exception as e:
            _log.warning("an absence could not be counted (%s)", type(e).__name__)
            continue
        if not got: continue
        n, held = n + 1, held + [g for g in goes if g is not None]
        for what, x, c in got: out[what] += 1
        away.setdefault(name, (first, str(r.get("at"))))
    names = sorted(away, key=lambda k: (away[k], k))                    # by the first lesson to cover, then as they came in
    return dict(absences=n, lessons=sum(out.values()), at=f"{min(held):%H:%M}" if held else "", away=names, **out)


# ---- every minute
def _away_all_day(records, iso) -> set:
    """the names away the whole day on iso: an absence of theirs, not cancelled, not an exam's or event's backup, dated iso, with
    no periods; a record that cannot be read is passed over"""
    out = set()
    for r in records:
        try:
            if not r.get("cancelled") and not r.get("exams") and iso in (r.get("dates") or []) and words.away(r) == "whole day": out.add(r["teacher"])
        except Exception as e: _log.warning("an absence could not be read (%s)", type(e).__name__)
    return out


def _morning(s):
    today, h = s.now.date(), _hours.of(s.settings)
    if not _hours.duty_day(s.settings, s.pub, today) or not _hours.at(today, h.morning) <= s.now < _hours.at(today, h.cut_off): return []
    was = tgdb.get_state("morning_last")
    if isinstance(was, int) and was >= today.toordinal(): return []
    names = _hours.on_duty(s.settings, today, _report._team(s.pub)[1])
    if not names: return []                     # nobody to tell: the day is not done with
    records, unread = _report._records()
    for kind in sorted(set(unread.values())): _log.warning("an absence could not be read (%s)", kind)
    names = [n for n in names if n not in _away_all_day(records, today.isoformat())] or names     # nobody left: all of them, as before
    v = counts(s.pub, s.settings, records, s.now, _fill._links(s.pub, s.settings.get("calendar") or {}))
    if not tgdb.raise_state("morning_last", today.toordinal()) or not v["lessons"]: return []
    iso, button = today.isoformat(), dict(text=tell.OPEN_TODAY, url=(s.bot.get("base") or "") + "/relief#today")
    return _report._to_each(names, "morning", f"morning:{iso}", morning_text(words.day(iso), **v), [[button]], dict(date=iso, made=s.now.isoformat(timespec="seconds")))


def tick(now=None) -> list:
    """the morning message, when it is to be made now -> the keys queued. now: the time (tests), else absences._now(). Never
    raises"""
    try:
        s = _report._common(now)
        return _morning(s) if s else []
    except Exception as e:
        _log.error("the morning message could not be worked out (%s)", type(e).__name__)
        return []


def _fresh(ref, name) -> bool:
    """a morning message: its day is today, the cut-off has not come, and its person is on the team still"""
    now = _fill._when(None)
    pub = store.published()
    cut = _hours.at(now.date(), _hours.of(_settings.load(pub) if pub else {}).cut_off)
    return ref["date"] == now.date().isoformat() and now < cut and tell._on_team(name)


tell.CHECKS["morning"] = _fresh

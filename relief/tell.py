"""What there is to tell people on Telegram, and telling it: the texts, the messages there should be (due), the sweep that
queues them (relief/outbox.py sends them) and whether a queued one is still true (still_true, the queue's VALID).

Nothing is kept here: due works every message out from the absence records each time, under a key of its own, and a key is
queued once (outbox.queue). So whatever restarts, however often and from wherever the sweep runs, nothing is sent twice and
nothing is missed. due is pure (it is given all it needs). The keys, {name} at the end of a message to several people:
relief:{absent}:{ckey}:{approved.at} to the relief teacher, once approved and while the lesson is not over (by the absent
teacher's name and the cover key, not the absence's id: an exam's takeover moves a cover to another absence, and it is the
same relief then; relief_key and _relief_key_for say what happens when two people were approved in one second);
gone:{relief key} or moved:{relief key}, one of them once, to a person told of a relief (its message, or a reminder of it, sent
or unsure) that is not approved to them any more, from what that message's ref holds: the cover, or its absence, may be gone;
stopped:{relief key}:{k} and again:{relief key}:{k} to a person told of a relief that is still theirs, while its lesson is
stopped and once it stands again (below; k counts the times);
{relief key}:r{n}, the relief sent once more because the team reminded them (relief/report.py queues it, the n-th time): it tells
them of the relief, under the relief's own key (_own), and is no relief of its own;
kept:{absent}:{ckey}:{when} to the teacher who asked to change; ask:{absent}:{ckey}:{change.at}:{name} to each of the team
with the new pick, or two minutes after the request without one, and then askpick:… once when a pick (another than the ask
carried) is in; planned:{id} and remind:{id} to the absent teacher; officer:{id} to the reporting officer;
cancelled:{id}:{name} to the team, the planner, and the absent teacher and the officer who were told of the absence (planned,
remind or officer sent or unsure), never to who cancelled.

Only people who can be reached are told. planned, officer, kept and cancelled are for what was done since the bot was
connected; nothing is said of a lesson that is over or an absence that is past. No message carries the typed reason, the
remarks or a pick's history; the officer's alone carries the kind of reason, and the team's alone a request's words and its
new pick's reason.

A lesson an approved exam or event stops (exams.relief_links, by cover.stopped) keeps its cover as it is, so it is worked out
each time: links is read once a sweep (fill._links, in no request; None: the exams cannot be read, no lesson counts as stopped
and nothing is said or taken back about stopping). A date something of which could not be read is so too, that date alone
(known, which all that is asked of links here and in relief/report.py goes through). While a lesson is stopped nothing is made of
its covers (no relief, ask, askpick or kept: they are made once it stands), and it is not gone or moved by that: those are said
when the cover itself ends or goes to another; planned does not count it. again is said to whoever was told it is stopped,
whatever was approved since, unless the relief itself is said again (_on_again); never of a lesson that is not there any more (a
publish moved it, or its date is a holiday now). stopped says why, again nothing of it; no other message names an exam or event.
A backup (exams) taken over by the teacher's own absence is not told as cancelled: its reliefs went with it.

still_true asks again when a message is about to go: it is dropped (its key may be queued again) when the lesson is over, when
what it says is not so any more (what it asks of a lesson that is stopped now, too), or when its person is not on the team a
message was for. stopped and again are dropped too while the exams, or that date in them, cannot be read: due makes them anew
once they can be.

sweep never raises and asks Telegram nothing; soon asks for one in a thread, and start is a ticker of one minute for the hooks
in MINUTE (the sweep, the reports), apart from relief.fill's, whose runs can wait long for the model. Two sweeps never run at
once. The records are read after what has been told (so a relief told of was in them), and before anyone is told that theirs is
gone or moved they are read again in one go, under absences._LOCK (a change of two of them is seen whole). A file there that
cannot be read is passed over, its kind logged: gone waits only while it is the record that should hold the cover. Failures
are logged to "relief.telegram" (the exams', by fill._links, to "relief.fill") by their kind alone."""
import datetime, json, logging, os, re, sqlite3, threading, types

import store
from accounts import people as _accounts
from accounts import rights as _rights
from exams.days import bounds
from relief import absences as _absences
from relief import cover as _cover
from relief import fill as _fill
from relief import free as _free
from relief import lessons as _lessons
from relief import links as _links
from relief import outbox, tgdb
from relief import settings as _settings
from relief import words

SYNC = False                                    # tests: soon() sweeps inline
MINUTE = []                                     # called with nothing every minute (start)
EVERY, FIRST = 60, 5                            # seconds between the ticker's runs, and before the first
PICK_WAIT = datetime.timedelta(minutes=2)       # how long a request to change waits for its new pick before the team is asked without
APPROVED = ("approved", "acknowledged", "change")                        # the states in which a relief has reached its teacher (as web.APPROVED)
NO_WORK = "No work set yet: look in Reliefs I'm covering."
NOBODY_ELSE = "Nobody else is free then: choose someone in the app."
NO_PICK = "No new pick yet: open the app."
ACK, CHANGE, SET_WORK, NOT_NEEDED, OPEN = "✅ Acknowledge", "↩ Request to change", "✅ Acknowledge and set work", "❌ Not needed: cancel", "Open in the app"
TOLD = ("relief:", "gone:", "moved:", "stopped:", "again:", "ask:", "planned:", "remind:", "officer:")      # the keys due must know of
SENT = ("sent", "unsure")                       # the states in which a person was told, or may have been
LIVE = (*SENT, "queued", "sending")              # ... or may still be
RELIEFS = ("relief:", "stopped:", "again:")      # the keys that say what has been said of a relief (Said)
_COPY = re.compile(r"(relief:.*):r(\d+)", re.S)  # the key of a reminder: the relief's, and which one it is
_going = threading.Lock()                       # one sweep at a time
_asked, _asked_lock = [False], threading.Lock() # a sweep soon() asked for has not started
_stop = threading.Event()                       # ends the ticker (tests)
_ticker = None
_log = logging.getLogger("relief.telegram")


# ---- the texts (the plan's messages)
def relief_text(day, lesson, periods, time, room, absent, work):
    """work: the lesson's dict(text, link, files); with a link or files and no text, it is not said that none is set"""
    text, link, files = work.get("text"), work.get("link"), work.get("files")
    lines = [f"🔔 Relief for you · {day}", " · ".join(v for v in (lesson, periods, time) if v)]
    if room: lines.append(f"Room {room}")
    lines.append(f"For {absent}")
    if text: lines.append(f"Work from {absent}: {text}")
    elif not (link or files): lines.append(NO_WORK)
    if link: lines.append(f"Link: {link}")
    if files: lines.append(f"Files: {len(files)}, sent after this message.")
    return "\n".join(lines)


def planned_text(days, away, by, n):
    """n: how many of its lessons will be covered (none: not said)"""
    lines = ["📋 Relief planned for you", f"{days} · {away}", f"Planned by {by}"]
    if n: lines.append(f"{n} {'lesson' if n == 1 else 'lessons'} will be covered.")
    return "\n".join(lines + ["Please acknowledge and set work for the relief teachers."])


def remind_text(days):
    return f"⏰ Reminder: please acknowledge your relief for {days} and set work."


def officer_text(absent, days, away, kind):
    return f"{absent} is away on {days} ({away}): {kind}.\nRelief is being arranged."


def cancelled_text(by, absent, days):
    """by "app": no person did (a duty changed, an exam withdrawn), and nobody is named"""
    return f"❌ Cancelled{'' if by == 'app' else f' by {by}'}: {absent}'s absence on {days}. Its reliefs are no longer needed."


def _from(start):
    return f" ({start})" if start else ""                                # a lesson with no times: nothing in brackets


def gone_text(lesson, periods, start, day):
    return f"❌ No longer needed: {lesson} {periods}{_from(start)} on {day}. You're free then."


def moved_text(lesson, periods, day):
    return f"✔ The relief team has moved {lesson} {periods} on {day} to someone else. You're free then."


def stopped_text(lesson, periods, start, day, why):
    """why: cover.stopped's ("3B is on Sec 3 End-of-Year Exam")"""
    return f"❌ Not happening: {lesson} {periods}{_from(start)} on {day}: {why}. You're free then."


def again_text(lesson, periods, start, day):
    return f"✔ On again: {lesson} {periods}{_from(start)} on {day}. The relief is yours as before."


def kept_text(lesson, periods, day):
    return f"The relief team has kept {lesson} {periods} on {day} with you."


def ask_text(who, lesson, periods, start, day, why, pick=None, nobody=False):
    """pick: the new pick (who, reason), or None: nobody says whether anyone else is free then"""
    lines = ["↩ Request to change", f"{who} · {lesson} · {periods}{_from(start)} on {day}", f"“{why}”"]
    if not pick: lines.append(NOBODY_ELSE if nobody else NO_PICK)
    else: lines += [f"New pick: {pick['who']}"] + ([pick["reason"]] if pick.get("reason") else [])
    return "\n".join(lines)


# ---- what both due and still_true ask
def known(links, iso):
    """links, for what is asked of them of that date (ISO); None when they are None, or something of the date could not be read
    (Links.unread)"""
    try: return None if links is None or links.unread(iso) else links
    except Exception: return None


def _stopped(links, x):
    """why an approved exam or event stops lesson x; "" when none does, and when that is not known"""
    return _cover.stopped(known(links, x["date"]), x)


def _time(v):
    """an ISO date-time in school time, or None"""
    try: return _fill._when(v) if isinstance(v, str) else None
    except ValueError: return None


def _last(r):
    """the absence's last date (ISO)"""
    return max(r.get("dates") or [x["date"] for x in r.get("lessons") or []], default="")


def _ends(x, c, bnds):
    """when the cover's lesson is over, as fill._ended has it: the end of its last period, or of its day without times"""
    day = datetime.datetime.combine(datetime.date.fromisoformat(x["date"]), datetime.time(), tzinfo=_fill._tz())
    p, n = int(c["p"]), int(c.get("n") or 1)
    if p >= len(bnds): return day + datetime.timedelta(days=1)
    return day + datetime.timedelta(minutes=bnds[min(p + n, len(bnds)) - 1][1])


def _holder(records, ref):
    """(record, lesson, cover) of the relief a message was about, approved to anyone now: in its own absence, else in another
    of the same teacher's not cancelled; None when there is none"""
    for r in sorted((r for r in records if r.get("teacher") == ref["absent"]), key=lambda r: r.get("id") != ref["id"]):
        try: x, c = _cover.find(r, ref["ckey"])
        except ValueError: continue
        if _cover.state(r, x, c) in APPROVED: return r, x, c
    return None


def _read(id):
    """the absence record, or None when there is no such file any more; one that cannot be read, or is none, raises"""
    try:
        with open(_absences._path(id), encoding="utf-8") as f: r = json.load(f)
    except FileNotFoundError: return None
    if not isinstance(r, dict) or r.get("id") != id: raise ValueError("not an absence record")
    return r


def _records():
    """(every absence record, {the other .json files there: the kind of failure each is}); raises while their folder is not
    there"""
    records, unread = [], {}
    for id in (f[:-5] for f in os.listdir(_absences.DIR) if f.endswith(".json")):
        try: r = _read(id)
        except Exception as e: unread[id] = type(e).__name__
        else: records += [r] if r else []
    return records, unread


def _stands(r, x, c):
    """the history entry of the last time the team kept the cover, while that is how it stands (theirs, not approved anew
    since, nor asked again), or None"""
    h = next((h for h in reversed(c.get("history") or []) if h.get("what") == "kept"), None)
    if h is None or h.get("who") != c.get("relief") or _cover.state(r, x, c) not in ("approved", "acknowledged"): return None
    return None if _time(h["at"]) < _time(c["approved"].get("at")) else h


# ---- what there should be
def relief_key(absent, ckey, approved_at):
    return f"relief:{absent}:{ckey}:{approved_at}"


def _relief_key_for(told, ref):
    """the key of a relief message: relief_key, with :{who} after it when another person has that one (the cover was
    approved to both in the same second, so it is the same key), and from then on"""
    k = relief_key(ref["absent"], ref["ckey"], ref["approved_at"])
    mine, t = f"{k}:{ref['who']}", told.get(k)
    return k if mine not in told and (t is None or t["name"] == ref["who"]) else mine


def _own(key, ref):
    """the relief's own key, when key is that of its message or of a reminder (the own one with :r{n} after it), else None"""
    if not isinstance(ref, dict): return None
    k, m = relief_key(ref.get("absent"), ref.get("ckey"), ref.get("approved_at")), _COPY.fullmatch(key)
    return next((x for x in (key, m and m[1]) if x in (k, f"{k}:{ref.get('who')}")), None)


def _there(told, key):
    """what became of the message under key, or None: one dropped is as if it had never been"""
    t = told.get(key)
    return t if t and t["state"] != "dropped" else None


def _item(key, name, kind, text, buttons=(), files=(), ref=None):
    return dict(key=key, name=name, kind=kind, text=text, buttons=[list(row) for row in buttons], files=list(files), ref=ref)


def _each(things, f):
    """all that f gives for each of things; one that cannot be read (a record changed by hand) is passed over"""
    for v in things:
        try: yield from f(v)
        except Exception as e: _log.warning("a message could not be worked out (%s)", type(e).__name__)


def _told_reliefs(w):
    """[(key, ref)]: the last relief each person was told of, by its message or a reminder of it, of each cover, its lesson not
    over: the relief's own key, and what its message holds when that went, else the last reminder (less its n)"""
    last = {}
    for key, t in w.told.items():
        ref = t.get("ref")
        own = _own(key, ref)
        if t["state"] not in SENT or own is None or ref.get("who") not in w.reach: continue
        ends, at = _time(ref.get("ends")), _time(ref["approved_at"])
        if ends is None or ends <= w.now or at is None: continue
        cover, rank = (ref["who"], ref["absent"], ref["ckey"]), (at, key == own, ref.get("n") or 0)
        if cover not in last or last[cover][0] < rank: last[cover] = (rank, own, {k: v for k, v in ref.items() if k != "n"})
    return [(own, ref) for rank, own, ref in last.values()]


def _of_told(w, key, ref):
    """what the person told of the relief under key has to hear of it: gone or moved when the cover is not theirs any more, else
    what _stops says"""
    if any(_there(w.told, f"{kind}:{key}") for kind in ("gone", "moved")): return      # told it is theirs no more: once is enough
    got = _holder(w.records, ref)
    if got and got[2].get("relief") == ref["who"]: yield from _stops(w, key, ref, *got)
    elif got: yield _item(f"moved:{key}", ref["who"], "moved", moved_text(ref["lesson"], ref["periods"], ref["day"]), ref=ref)
    elif ref["id"] not in w.unread: yield _item(f"gone:{key}", ref["who"], "gone", gone_text(ref["lesson"], ref["periods"], ref["start"], ref["day"]), ref=ref)


def _times_told(told, kind, key):
    """how many times the person told of the relief under key was told this of it (stopped, again): {kind}:{key}:0, :1 and so on"""
    n = 0
    while (told.get(f"{kind}:{key}:{n}") or {}).get("state") in SENT: n += 1
    return n


def _on_again(pub, cal, ref, r, x, c):
    """again may be said of a cover still theirs, its lesson not stopped: the lesson is there still, and no relief message says it
    anew (approved anew and not answered, the relief itself does)"""
    if c["approved"].get("at") != ref["approved_at"] and _cover.state(r, x, c) == "approved": return False
    return _lessons.still_there(pub, cal, r["teacher"], x)


def _stops(w, key, ref, r, x, c):
    """stopped, when the lesson of a cover still theirs is stopped; again, when it is on again (_on_again) for who was told that it
    was stopped; nothing while that is not known"""
    links = known(w.links, x["date"])
    if links is None: return
    why, what, ref_ = _cover.stopped(links, x), (ref["lesson"], ref["periods"], ref["start"], ref["day"]), dict(ref, id=r["id"])       # id: where the cover is now
    if why: yield _item(f"stopped:{key}:{_times_told(w.told, 'again', key)}", ref["who"], "stopped", stopped_text(*what, why), ref=ref_)
    else:
        n = _times_told(w.told, "stopped", key)
        if n and _on_again(w.pub, w.settings.get("calendar") or {}, ref, r, x, c):
            yield _item(f"again:{key}:{n - 1}", ref["who"], "again", again_text(*what), _answers(r, x, ref["ckey"], ref["who"]), ref=ref_)


def _absence(w, r):
    """what one absence (not past) has to say of itself"""
    if r.get("cancelled"): return _cancelled(w, r)
    out = _officer(w, r)
    if r.get("how") == "planned" and r.get("by") != r["teacher"] and not r.get("acknowledged") and r["teacher"] in w.reach: out = _planned(w, r) + out
    return out


def _since(w, v):
    t = _time(v)
    return t is not None and t >= w.since


def _cancelled(w, r):
    gone = r["cancelled"]
    if not _since(w, gone.get("at")) or _taken_over(r): return []
    told = [w.told.get(f"{kind}:{r['id']}") for kind in ("planned", "remind", "officer")]
    names = [r.get("by")] if r.get("how") == "planned" else []
    names = {n for n in names + [t["name"] for t in told if t and t["state"] in SENT] if n in w.reach}
    text = cancelled_text(gone.get("by"), r["teacher"], words.days(r))
    return [_item(f"cancelled:{r['id']}:{n}", n, "cancelled", text, ref=dict(id=r["id"], team=n not in names))        # team: as the team alone
            for n in sorted((names | set(w.team)) - {gone.get("by")})]


def _taken_over(r):
    """a backup (exams) whose lessons moved into the teacher's own absence (absences._take_over): not cancelled to anyone"""
    return bool(r.get("exams")) and r["cancelled"].get("by") == "app" and r["cancelled"].get("why") == f"Moved to {r['teacher']}'s own absence."


def _planned(w, r):
    """the absence planned for a teacher who has not acknowledged it, and the reminder: never for an absence sent at or after
    the time the reminder goes (remind_at on the school day before; today or not)"""
    out, ref, days = [], dict(id=r["id"]), words.days(r)
    if _since(w, r.get("at")):
        n = sum(1 for x in r.get("lessons") or [] if x.get("needed") and not _stopped(w.links, x))
        out.append(_item(f"planned:{r['id']}", r["teacher"], "planned", planned_text(days, words.away(r), r.get("by"), n),
                         [[dict(text=SET_WORK, url=w.base + "/relief#mine")], [dict(text=NOT_NEEDED, what="cancel", id=r["id"])]], ref=ref))
    if _fill.nudge(r, w.pub, w.settings, w.now, w.today):
        first, at = min([x["date"] for x in r.get("lessons") or []] or r["dates"]), _time(r.get("at"))
        remind = _fill.due_at(w.settings.get("calendar") or {}, ((w.pub or {}).get("model") or {}).get("days") or [], first,
                              (w.settings.get("times") or {}).get("remind_at"), today=datetime.date.min)
        if at is not None and at < remind: out.append(_item(f"remind:{r['id']}", r["teacher"], "remind", remind_text(days), ref=ref))
    return out


def _officer(w, r):
    name = r.get("reporting_officer")
    if name not in w.reach or name in (r["teacher"], r.get("by")) or not _since(w, r.get("at")): return []
    kind = r.get("reason") if r.get("reason") in _absences.REASONS else "Other"        # one of the four, never anything typed
    return [_item(f"officer:{r['id']}", name, "officer", officer_text(r["teacher"], words.days(r), words.away(r), kind), ref=dict(id=r["id"]))]


def _of_cover(w, r, x, c, ckey):
    """what one cover (its lesson neither over nor stopped) has to say"""
    s = _cover.state(r, x, c)
    if s == "approved": yield from _relief(w, r, x, c, ckey)
    if s == "change": yield from _ask(w, r, x, c, ckey)
    yield from _kept(w, r, x, c, ckey)


def _answers(r, x, ckey, who):
    """the buttons of a relief"""
    press = dict(id=r["id"], ckey=ckey, who=who, extra=dict(absent=r["teacher"], date=x["date"]))
    return [[dict(press, text=ACK, what="ack"), dict(press, text=CHANGE, what="change")]]


def _relief(w, r, x, c, ckey):
    who, at = c["relief"], c["approved"].get("at")
    if who not in w.reach or not at: return
    lesson, periods, day, (start, end) = words.class_group(x), words.periods_text(c), words.day(x["date"]), words.times(w.pub, x, c)
    ref = dict(id=r["id"], absent=r["teacher"], ckey=ckey, approved_at=at, who=who, lesson=lesson, periods=periods, start=start, day=day,
               date=x["date"], ends=_ends(x, c, w.bnds).isoformat())
    work = x.get("work") or {}
    yield _item(_relief_key_for(w.told, ref), who, "relief",
                relief_text(day, lesson, periods, f"{start}–{end}" if start and end else "", x.get("room"), r["teacher"], work),
                _answers(r, x, ckey, who), [dict(id=r["id"], file=f["id"], name=f["name"]) for f in work.get("files") or []], ref)


def relief_item(pub, reach, told, r, x, c, ckey):
    """the relief message of an approved cover, as outbox.queue takes it, or None (its teacher cannot be reached)"""
    w = types.SimpleNamespace(pub=pub, reach=reach, told=told, bnds=bounds((pub or {}).get("model") or {}))
    return next(_relief(w, r, x, c, ckey), None)


def _kept(w, r, x, c, ckey):
    h = _stands(r, x, c)
    if h is None or c["relief"] not in w.reach or not _since(w, h.get("at")): return
    yield _item(f"kept:{r['teacher']}:{ckey}:{h['at']}", c["relief"], "kept", kept_text(words.class_group(x), words.periods_text(c), words.day(x["date"])),
                ref=dict(id=r["id"], absent=r["teacher"], ckey=ckey, who=c["relief"], approved_at=c["approved"].get("at"), at=h["at"], ends=_ends(x, c, w.bnds).isoformat()))


def _ask(w, r, x, c, ckey):
    """the request to change, to each of the team: with the new pick, or after PICK_WAIT without one; then the pick once more,
    unless the ask carried that very name"""
    ch, new, at = c["change"], _cover.new_pick(c), _time(c["change"].get("at"))
    if at is None or not (new or w.now - at >= PICK_WAIT): return
    text, buttons = None, [[dict(text=OPEN, url=w.base + "/relief#today")]]
    if new: buttons.insert(0, [dict(text=f"Approve {w.shorts.get(new['who']) or new['who']}", what="approve", id=r["id"], ckey=ckey, who=new["who"],
                                    extra=dict(absent=r["teacher"], date=x["date"]))])
    for n in w.team:
        key, kind = f"{r['teacher']}:{ckey}:{ch['at']}:{n}", "ask"
        was = _there(w.told, f"ask:{key}")
        if was:
            if not new or (was.get("ref") or {}).get("pick") == new["who"]: continue
            kind = "askpick"
        if text is None:                        # who is free is worked out only for a message that says it
            text = ask_text(c["relief"], words.class_group(x), words.periods_text(c), words.times(w.pub, x, c)[0], words.day(x["date"]), ch.get("why") or "",
                            pick=new, nobody=not new and _nobody_else(w, r, x, c, ckey))
        yield _item(f"{kind}:{key}", n, kind, text, buttons, ref=dict(id=r["id"], absent=r["teacher"], ckey=ckey, at=ch["at"], pick=new["who"] if new else None,
                                                                      ends=_ends(x, c, w.bnds).isoformat()))


def _nobody_else(w, r, x, c, ckey):
    """nobody is free for the cover but the teacher who asked to change"""
    try: got = _free.free_then(w.pub, w.settings, w.records, dict(x, key=ckey, p=int(c["p"]), n=int(c.get("n") or 1)), r["teacher"], links=known(w.links, x["date"]))
    except ValueError: return False             # no longer a school day in the calendar: nothing to say
    return not any(q["name"] != c["relief"] for g in got["groups"] for q in g["people"])


def due(pub, settings, records, now, reach, told, since, team=(), base="", shorts=None, unread=(), links=None):
    """every message there should be now and is not there yet -> [dict(key, name, kind, text, buttons, files, ref)], as
    outbox.queue takes them, in the order to queue them. Pure. reach: {name: chat} of the people who can be reached; told:
    what outbox.told_for gives for the TOLD keys; since: when the bot was connected (unknown: now); team: the names on the
    relief team; base: the app's address; shorts: {name: short name}; unread: the ids of the records that could not be read (a
    relief that should be in one of them is not said to be gone); links: what approved exams and events stop (fill._links;
    None: they cannot be read)"""
    now = _fill._when(now)
    w = types.SimpleNamespace(pub=pub, settings=settings, records=records, now=now, today=now.date(), reach=reach, told=told, since=_time(since) or now,
                              team=sorted(n for n in set(team) if n in reach), base=base or "", shorts=shorts or {}, unread=unread, links=links,
                              bnds=bounds((pub or {}).get("model") or {}))
    still = list(_each(sorted(records, key=lambda r: (str(r.get("at")), str(r.get("dates")))), lambda r: [r] if _last(r) >= w.today.isoformat() else []))
    covers = sorted(_each(still, lambda r: [t for t in _fill._covers([r], None, None, now, w.bnds) if not _stopped(links, t[1])]), key=lambda t: (t[1]["date"], int(t[2]["p"]), str(t[0]["id"]), t[3]))
    out = list(_each(_told_reliefs(w), lambda v: _of_told(w, *v)))       # what is theirs no more comes before what is theirs now
    out += _each(still, lambda r: _absence(w, r))
    out += _each(covers, lambda t: _of_cover(w, *t))
    return [i for i in out if not _there(told, i["key"])]


# ---- what has been said of a relief (the report, Remind, and Today's page)
def key_of(told, r, c, ckey):
    """the key of the relief message of cover c as it is approved now"""
    return _relief_key_for(told, dict(absent=r["teacher"], ckey=ckey, approved_at=c["approved"].get("at"), who=c["relief"]))


class Said:
    """what has been said of the reliefs, read once (said): told, what outbox.states_for gives for the RELIEFS keys. key: a relief
    message's; it and its reminders are one relief's messages, those dropped as if they had never been.

    Someone told that a relief is stopped, and not surely (sent) told since that it is on again, has been told nothing: until a
    reminder has gone to them after that"""
    def __init__(self, told):
        self.told, self._copies = told, {}
        for key, t in told.items():
            m = _COPY.fullmatch(key)
            if m: self._copies.setdefault(m[1], {})[int(m[2])] = t

    def copies(self, key):
        """the reminders of the relief, in any state: {n: told}"""
        return self._copies.get(key, {})

    def _messages(self, key):
        """[(when, n, told)]: the relief's messages, n 0 for the first"""
        return [(_time(t["at"]), n, t) for n, t in [(0, self.told.get(key)), *self.copies(key).items()] if t]

    def _off(self, key):
        """when its person was told that it is stopped, while they are not sure to know that it is on again; else None"""
        n = _times_told(self.told, "stopped", key)
        if not n or (self.told.get(f"again:{key}:{n - 1}") or {}).get("state") == "sent": return None
        return _time(self.told[f"stopped:{key}:{n - 1}"]["at"])

    def sent_at(self, key):
        """when its person was last told of the relief, or may have been (a date-time), or None: they have not been told"""
        off = self._off(key)
        went = [when for when, n, t in self._messages(key) if (t["state"] in SENT if off is None else t["state"] == "sent" and when > off)]
        return max(went, default=None)

    def of(self, key):
        """dict(state, at) of its last message ("queued" while it is going out, too), or None"""
        off = self._off(key)
        got = [m for m in self._messages(key) if off is None or m[0] > off]
        got = [m for m in got if m[2]["state"] != "dropped"] or got
        if not got: return None
        t = max(got, key=lambda m: m[:2])[2]
        return dict(state="queued" if t["state"] == "sending" else t["state"], at=t["at"])

    def last(self, key):
        """when the last of its messages went, may have gone or was put in the queue (a date-time), or None"""
        return max((when for when, n, t in self._messages(key) if t["state"] in LIVE), default=None)


def said():
    """what has been said of the reliefs, as it is now"""
    return Said(outbox.states_for(*RELIEFS))


# ---- telling it
def _told():
    out = {}
    for prefix in TOLD: out.update(outbox.told_for(prefix))
    return out


def _queued(keys):
    """which of the keys are in the queue, in any state but dropped"""
    out = set()
    with tgdb.db(read=True) as c:
        for i in range(0, len(keys), 500):
            some = keys[i:i + 500]
            out |= {r["key"] for r in c.execute(f"SELECT key FROM outbox WHERE state<>'dropped' AND key IN ({','.join('?' * len(some))})", some)}
    return out


def _sweep(now):
    bot = _links.connected()                    # None without a token too
    pub = store.published() if bot else None
    if not pub: return 0                        # nothing published (a publish swaps folders): the next sweep
    reach = _links.reachable(pub)
    if not reach: return 0
    told = _told()
    now, settings, people = _fill._when(now), _settings.load(pub), _accounts.staff(pub)
    more = dict(team=[p["name"] for p in people if "relief.team" in _rights.rights(p, _links.VIA)], base=bot["base"], shorts={p["name"]: p["short"] for p in people},
                links=_fill._links(pub, settings.get("calendar") or {}))
    records, unread = _records() if os.path.isdir(_absences.DIR) else ([], {})          # none yet
    for kind in sorted(set(unread.values())): _log.warning("an absence could not be read (%s)", kind)
    items = due(pub, settings, records, now, reach, told, bot["at"], unread=unread, **more)
    if any(i["kind"] in ("gone", "moved") for i in items):
        with _absences._LOCK: records, unread = _records()
        items = due(pub, settings, records, now, reach, told, bot["at"], unread=unread, **more)
    have, n = _queued([i["key"] for i in items]), 0
    for i in items:
        if i["key"] in have: continue
        try: n += outbox.queue(i["key"], i["name"], i["text"], kind=i["kind"], buttons=i["buttons"], files=i["files"], ref=i["ref"])
        except Exception as e:
            _log.error("a message could not be queued (%s)", type(e).__name__)
            if isinstance(e, sqlite3.OperationalError): break            # the store fails: the rest would too
    if n: outbox.wake()
    return n


def _swept(now):
    try: return _sweep(now)
    except Exception as e:
        _log.error("the messages could not be worked out (%s)", type(e).__name__)
        return 0


def sweep(now=None):
    """queue every message there should be and is not there yet, and wake the sender -> how many were queued; 0 while there
    is no token or the bot is not connected. It waits for one that is going (which may have read the records before a save).
    now: the time (tests), else absences._now(). Never raises. Never call it holding absences._LOCK"""
    with _going: return _swept(now)


def _asked_for():
    with _going:
        with _asked_lock: _asked[0] = False     # from here on a sweep asked for is another one
        _swept(None)


def soon():
    """ask for a sweep -> True, or False when there is nothing to do (no token, not connected) or no thread to be had (the
    ticker's next one does it). In a daemon thread named relief-tell; one asked for while another runs runs once more after
    it; inline when SYNC (tests). Never raises. Never call it holding absences._LOCK"""
    try:
        if _links.connected() is None: return False
        if SYNC:
            sweep()
            return True
        with _asked_lock:
            if _asked[0]: return True           # one that has not started reads the records after this
            _asked[0] = True
        try: threading.Thread(target=_asked_for, name="relief-tell", daemon=True).start()
        except RuntimeError:
            with _asked_lock: _asked[0] = False
            raise
        return True
    except Exception as e:
        _log.error("the messages could not be asked for (%s)", type(e).__name__)
        return False


# ---- a minute of its own
def tick():
    for f in list(MINUTE):
        try: f()
        except Exception as e: _log.error("what is done every minute failed (%s)", type(e).__name__)


def _loop(every):
    wait = min(FIRST, every)
    while not _stop.wait(wait):
        tick()
        wait = every


def start(every=EVERY):
    """the ticker: a daemon thread named relief-tell-ticker calling what is in MINUTE every `every` seconds, the first time a few
    seconds after it starts; started once (app.py, when RELIEF_JOBS=on and there is a token)"""
    global _ticker
    if _ticker is not None and _ticker.is_alive(): return _ticker
    _stop.clear()
    _ticker = threading.Thread(target=_loop, args=(every,), name="relief-tell-ticker", daemon=True)
    _ticker.start()
    return _ticker


# ---- still true
def _over(ref):
    return _time(ref["ends"]) <= _fill._when(None)


def _on_team(name):
    if not _accounts.readable(): raise ValueError("the accounts could not be read")           # nobody's rights are known now
    return "relief.team" in _links.rights_named(name)


def _now(ref):
    """_holder of the records as they are now; raises when there is none and the record that should hold it cannot be read"""
    own = failed = None
    try: own = _read(ref["id"])
    except Exception as e: failed = e
    got = _holder([own] if own else [], ref)
    if got is None:
        with _absences._LOCK: got = _holder(_records()[0], ref)
    if got is None and failed: raise failed
    return got


def _exams():
    """(the published timetable, the calendar, what approved exams and events stop now); the last None when that cannot be read,
    or nothing is published (a publish swaps folders)"""
    pub = store.published()
    if not pub: return None, {}, None
    cal = _settings.load(pub).get("calendar") or {}
    return pub, cal, _fill._links(pub, cal)


def _stands_now(x):
    """lesson x is not stopped now, as far as it is known"""
    return not _stopped(_exams()[2], x)


def _theirs(ref):
    """(record, lesson, cover) of the relief, when it is theirs still and the lesson not over, else None"""
    got = None if _over(ref) else _now(ref)
    return got if got is not None and got[2].get("relief") == ref["who"] else None


def _relief_true(ref, name):
    """the relief is theirs still, as it was approved when the message was made, and its lesson not stopped; a reminder (n): and
    it is not answered since"""
    got = _theirs(ref)
    if got is None or got[2]["approved"].get("at") != ref["approved_at"] or ("n" in ref and _cover.state(*got) != "approved"): return False
    return _stands_now(got[1])


def _stopped_true(ref, name):
    """the relief is theirs still (gone or moved says it when not) and its lesson known to be stopped"""
    got = _theirs(ref)
    return got is not None and bool(_stopped(_exams()[2], got[1]))


def _again_true(ref, name):
    """the relief is theirs still, its lesson known not to be stopped, and on again (_on_again)"""
    got = _theirs(ref)
    if got is None: return False
    pub, cal, links = _exams()
    links = known(links, got[1]["date"])
    return links is not None and not _cover.stopped(links, got[1]) and _on_again(pub, cal, ref, *got)


def _ended_true(ref, name):
    """gone or moved: the relief is not theirs again (a message that waited would go after the one that says it is)"""
    if _over(ref): return False
    got = _now(ref)
    return got is None or got[2].get("relief") != ref["who"]


def _kept_true(ref, name):
    """the relief is theirs still, kept that very time, and neither asked about nor approved anew since; its lesson not stopped"""
    got = None if _over(ref) else _now(ref)
    h = _stands(*got) if got else None
    return h is not None and (h["who"], h["at"], got[2]["approved"].get("at")) == (ref["who"], ref["at"], ref["approved_at"]) and _stands_now(got[1])


def _ask_true(ref, name):
    """the cover is still that very request to change, with that pick (or none), its lesson not stopped, and the person on the
    team still"""
    if _over(ref) or not _on_team(name): return False
    got = _now(ref)
    if got is None or _cover.state(*got) != "change": return False
    return got[2]["change"].get("at") == ref["at"] and (_cover.new_pick(got[2]) or {}).get("who") == ref["pick"] and _stands_now(got[1])


def _absence_true(ref, name, acknowledged_too=True):
    """the absence is still to come and not cancelled (nor acknowledged)"""
    r = _read(ref["id"])
    if r is None or r.get("cancelled") or _last(r) < _fill._when(None).date().isoformat(): return False
    return not (acknowledged_too and r.get("acknowledged"))


def _cancelled_true(ref, name):
    """a copy for the team alone goes to who is on it still"""
    return not ref.get("team") or _on_team(name)


# what is asked of a queued message, by its kind, before it goes: CHECK(its ref, its person) -> bool. A kind not here is always
# true (relief/report.py puts report and clear here)
CHECKS = dict(relief=_relief_true, gone=_ended_true, moved=_ended_true, stopped=_stopped_true, again=_again_true, kept=_kept_true, ask=_ask_true,
              askpick=_ask_true, planned=_absence_true, remind=_absence_true, officer=lambda ref, name: _absence_true(ref, name, False), cancelled=_cancelled_true)


def still_true(item):
    """a queued message (outbox's item) may still go; what cannot be read raises (the queue waits and asks again)"""
    check = CHECKS.get(item.get("kind"))
    return True if check is None else check(item["ref"], item.get("name"))


outbox.VALID = still_true

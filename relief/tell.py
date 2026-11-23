"""What there is to tell people on Telegram, and telling it: the texts, the messages there should be (due), the sweep that
queues them (relief/outbox.py sends them) and whether a queued one is still true (still_true, the queue's VALID).

Nothing is kept here: due works every message out from the absence records each time, under a key of its own, and a key is
queued once (outbox.queue). So whatever restarts, however often and from wherever the sweep runs, nothing is sent twice and
nothing is missed. due is pure (it is given all it needs). The keys, {name} at the end of a message to several people:
relief:{absent}:{ckey}:{approved.at} to the relief teacher, once approved, sent out and its time has come (cover.reached:
made by the sweep from the record as it is then, never queued early; one sent out outside school hours is held until the
earliest send-out time, and an approval from before Send out counts as sent out at once), while the lesson is not over (by the absent
teacher's name and the cover key, not the absence's id: an exam's takeover moves a cover to another absence, and it is the
same relief then; relief_key and _relief_key_for say what happens when two people were approved in one second);
gone:{relief key} or moved:{relief key}, one of them once, to a person told of a relief (its message, or a reminder of it, sent
or unsure) that is not approved to them any more, from what that message's ref holds: the cover, or its absence, may be gone;
stopped:{relief key}:{k} and again:{relief key}:{k} to a person told of a relief that is still theirs, while its lesson is
stopped and once it stands again (below; k counts the times; stopped is said anew once it was said since that the relief is on);
{relief key}:r{n}, the relief sent once more because the team reminded them (relief/report.py queues it, the n-th time): it tells
them of the relief, under the relief's own key (_own), and is no relief of its own;
{relief key}:before and {relief key}:morning, the repeats (kind repeat) of a relief told ahead of its day, once each, while it is
approved or acknowledged, sent out (never one approved before there was Send out) and its first message went: before at
hours.before_moment of its lesson's start (24 hours before, moved earlier out of the night to the last cut-off), made until the
morning one's moment; morning at the earliest send-out time of the lesson's day, made until the lesson starts; neither when its
moment had passed when the first message went, nor less than REPEAT_GAP after the last message of that relief (its first, a
reminder, the other repeat, queued ones too); not acknowledged, the relief message again (as a reminder has it), acknowledged a
short line (repeat_text): one made in the other form than the state is when it goes is dropped and made again. Like the
reminders they are the relief's messages (_own, Said), apart from the reminders' :r{n};
kept:{absent}:{ckey}:{when} to the teacher who asked to change; ask:{absent}:{ckey}:{change.at}:{name} to each of the team
with the new pick, or two minutes after the request without one, and then askpick:… once when a pick (another than the ask
carried) is in; planned:{id} and remind:{id} to the absent teacher; officer:{id} to the reporting officer;
cancelled:{id}:{name} to the team, the planner, and the absent teacher and the officer who were told of the absence (planned,
remind or officer sent or unsure), never to who cancelled; of a backup (exams) that ended by itself ("app": withdrawn, a changed
duty, handled by the committee) to those told of it alone, since a whole exam's end at once; late:{id}:{name}, the late request,
to each of the team but who sent it and the absent teacher, once, of an absence sent for today on a duty day at or after its
morning time and before its cut-off (never a backup), when a lesson of it today waits for their approval: picked, or open five
minutes on (NEW_WAIT: till then its picks may be on their way); made only in the team's window (hours.team_open), never later:
one sent before the morning time (the evening, the night, a weekend) is in that day's morning message (relief/morning.py) and
pings nobody, and one whose picks come after the cut-off pings nobody; claimed once (a key there in any state, dropped too, is
never made again). The ping kind new it replaces is dropped if one is still queued (CHECKS). needed:{absent}:{ckey}:{at}:{name},
Relief needed again, to each of the team but the relief teacher who is away and the absent teacher, once, when an approved relief went back to open at at because its teacher is away
then (cover.back_to_open, cover.was_away) and the cover is open or waiting again: with its new pick at once, open five minutes
on (NEW_WAIT); in the team's window alone and claimed once as late is; never of a lesson of today found before that day's
morning time (the morning message counts it). The teacher who was away hears gone, as anyone told of a relief no longer theirs.
covered:{absent}:{ckey}:{ack at}, Who covers you, to the teacher who is away, once an acknowledgement of a lesson of theirs: it names
the relief teacher, whom they may see in the app from then on; never of a backup (exams), nor when the teacher who is away is the
relief teacher. A relief moved and acknowledged by another is told anew; one moved before it went is dropped.
unlinked:{name}:{date}:{member}, the blocked-bot alert, to each of the team but name, once: Telegram refused a message to name
because they blocked the bot, and the sender unlinked them and noted it (links.note_alert, one a person a day, with what was
refused in plain words: refused); made only in the first team window at or after it was found (hours.team_window: at once in it,
else from the next morning time) and given up when that window ends; dropped outside the window and made again in it (GATES).
work:{id}:{date}:eve and work:{id}:{date}:day, Please set work, to the teacher who is away, once each, for each date of the
absence on its own while a lesson of it that date has no work (_no_work: needed, not stopped as far as is known, not over, with
no text, link or file): eve at work_eve on the calendar day before (Sunday for a Monday), made until WORK_EVE_UNTIL (22:00) of that
evening (until midnight when work_eve is at or after it), never later at night; day at work_day
on the date, made while such a lesson is left; neither when its moment is under WORK_GAP after the absence was sent, or before the
bot was connected; never of a backup (exams) nor a cancelled absence. It points to My absences in the app (/relief cannot add
work to an absence already sent). The planned absence's remind goes as before: these may follow it.

The relief message carries no files: it says how many there are and has Open in the app, and they are downloaded in Reliefs I'm
covering (outbox still sends those of a message queued with files before this was so).

Only people who can be reached are told. planned, officer, kept, covered and cancelled are for what was done since the bot was
connected; nothing is said of a lesson that is over or an absence that is past. No message carries the typed reason, the
remarks or a pick's history; the officer's alone carries the kind of reason, and the team's alone a request's words and its
new pick's reason.

A lesson an approved exam or event stops (exams.relief_links, by cover.stopped) keeps its cover as it is, so it is worked out
each time: links is read once a sweep (fill._links, in no request; None: the exams cannot be read, no lesson counts as stopped
and nothing is said or taken back about stopping). A date something of which could not be read is so too, that date alone
(known, which all that is asked of links here and in relief/report.py goes through). While a lesson is stopped nothing is made of
its covers (no relief, ask, askpick or kept: they are made once it stands), and it is not gone or moved by that: those are said
when the cover itself ends or goes to another. planned does not count it, and of an absence with no lesson left to cover there is
no remind, and officer says nothing of relief. again is said to whoever was told it is stopped, whatever was approved since,
unless the relief itself is said again (_on_again); never of a lesson that is not there any more (a publish moved it, or its date
is a holiday now). stopped says why, again nothing of it; no other message names an exam or event. A backup (exams) taken over by
the teacher's own absence is not told as cancelled: its reliefs went with it.

Quiet times, by kind (GATES): a message the app makes by itself is made, and goes, only inside the hours its reader may be
messaged, worked out by relief/hours.py. To a relief teacher (TEACHER_KINDS: relief, its reminders and repeats, gone, moved,
stopped, again, kept): in school hours for its lesson (hours.teacher_open: from the earliest send-out time to the end of the
cut-off's minute of a school day; on the lesson's own day from the earliest send-out time), while the lesson is not over. To the
team: ask and askpick in the team's window (hours.team_open: a duty day, from the morning time to before the cut-off), or on the
lesson's own day from the cut-off until it starts; the team's copy of cancelled in their window; the blocked-bot alert in the
first of their windows after it was found. The others go at any hour,
each named in ANY_HOUR with why (the late request, Relief needed again and the morning message keep the team's window by
rules of their own, since none is made again). due does not make one outside its hours, and still_true drops one queued that is still waiting when its
hours end (an outage, a pause Telegram asked for): due makes it again, under the same key, when they come, if it is still true
then; so it goes once, in the morning, and never in the night. An answer to a person's own press or typing (relief/bot.py, relief/asking.py) does not go
through the queue and goes at once.

still_true asks again when a message is about to go: it is dropped (its key may be queued again) when the lesson is over or the
absence past (a cancelled one too), when what it says is not so any more (what it asks of a lesson that is stopped now, too), or
when its person is not on the team a message was for. stopped and again are dropped too while the exams, or that date in them, cannot be read: due makes them anew
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
from relief import hours as _hours
from relief import free as _free
from relief import lessons as _lessons
from relief import links as _links
from relief import outbox, tgdb
from relief import settings as _settings
from relief import words

SYNC = False                                    # tests: soon() sweeps inline
MINUTE = []                                     # called with nothing every minute (start)
EVERY, FIRST = 60, 5                            # seconds between the ticker's runs, and before the first
REPEAT_GAP = datetime.timedelta(hours=12)       # a repeat is not made sooner after the last message of its relief
WORK_GAP = datetime.timedelta(minutes=30)       # a reminder to set work is not made when its moment is sooner after the absence was sent
WORK_EVE_UNTIL = "22:00"                        # the evening reminder to set work is made only until this hour of its evening (until midnight when work_eve is at or after it)
PICK_WAIT = datetime.timedelta(minutes=2)       # how long a request to change waits for its new pick before the team is asked without
NEW_WAIT = datetime.timedelta(minutes=5)        # how long an absence for today with a lesson still open waits for its picks before the team is told of it
BEFORE = 60                                     # minutes before the first period starts: the day's first report (relief/report.py's)
APPROVED = ("approved", "acknowledged", "change")                        # the states in which a relief has reached its teacher (as web.APPROVED)
NO_WORK = "No work set yet: look in Reliefs I'm covering."
NOBODY_ELSE = "Nobody else is free then: choose someone in the app."
NO_PICK = "No new pick yet: open the app."
ACK, CHANGE, SET_WORK, NOT_NEEDED, OPEN = "✅ Acknowledge", "↩ Request to change", "✅ Acknowledge and set work", "❌ Not needed: cancel", "Open in the app"
NOT_TOLD = "{officer} is not on Telegram: please tell them yourself."                 # said to a teacher (the form, /relief) when their reporting officer is not on Telegram
OPEN_TODAY = "Open relief today"                # the button to Today's page (relief/report.py's too)
TOLD = ("relief:", "gone:", "moved:", "stopped:", "again:", "ask:", "planned:", "remind:", "officer:", "covered:", "needed:", "unlinked:", "work:", "late:")      # the keys due must know of
SENT = ("sent", "unsure")                       # the states in which a person was told, or may have been
WAITING = ("queued", "sending")                 # ... in which they will be by itself, or are now
LIVE = (*SENT, *WAITING)
RELIEFS = ("relief:", "stopped:", "again:")      # the keys that say what has been said of a relief (Said)
_COPY = re.compile(r"(relief:.*):r(\d+)", re.S)  # the key of a reminder: the relief's, and which one it is
_REPEAT = re.compile(r"(relief:.*):(before|morning)", re.S)  # the key of a repeat: the relief's, and which one it is
_going = threading.Lock()                       # one sweep at a time
_asked, _asked_lock = [False], threading.Lock() # a sweep soon() asked for has not started
_stop = threading.Event()                       # ends the ticker (tests)
_ticker = None
_log = logging.getLogger("relief.telegram")


# ---- the texts (the plan's messages)
def relief_text(day, lesson, periods, time, room, absent, work):
    """work: the lesson's dict(text, link, files); with a link or files and no text, it is not said that none is set. Files are not
    sent on Telegram: they are downloaded in Reliefs I'm covering"""
    text, link, files = work.get("text"), work.get("link"), work.get("files")
    lines = [f"🔔 Relief for you · {day}", " · ".join(v for v in (lesson, periods, time) if v)]
    if room: lines.append(f"Room {room}")
    lines.append(f"For {absent}")
    if text: lines.append(f"Work from {absent}: {text}")
    elif not (link or files): lines.append(NO_WORK)
    if link: lines.append(f"Link: {link}")
    if files: lines.append(f"Files: {len(files)}. Open the app to download them.")
    return "\n".join(lines)


def covered_text(day, lesson, periods, start, who):
    """Who covers you, to the teacher who is away: who has acknowledged the relief of that lesson"""
    return f"✅ Covered · {day}\n{lesson} · {periods}{_from(start)}\n{who} has acknowledged. You can reach them if you need to."


def repeat_text(day, lesson, periods, time, room, absent, today):
    """the repeat of a relief its teacher has acknowledged; today: the lesson is today"""
    head = f"⏰ Reminder · your relief today, {day}" if today else f"⏰ Reminder · your relief on {day}"
    what = " · ".join(v for v in (lesson, periods, time, room and f"Room {room}") if v)
    return "\n".join([head] + ([what] if what else []) + [f"For {absent}. The work is in the app."])


def planned_text(days, away, by, n):
    """n: how many of its lessons will be covered (none: not said)"""
    lines = ["📋 Relief planned for you", f"{days} · {away}", f"Planned by {by}"]
    if n: lines.append(f"{n} {'lesson' if n == 1 else 'lessons'} will be covered.")
    return "\n".join(lines + ["Please acknowledge and set work for the relief teachers."])


def remind_text(days):
    return f"⏰ Reminder: please acknowledge your relief for {days} and set work."


def officer_text(absent, days, away, kind, relief=True):
    """relief: it has a lesson to cover"""
    return f"{absent} is away on {days} ({away}): {kind}." + ("\nRelief is being arranged." if relief else "")


def cancelled_text(by, absent, days):
    """by "app": no person did (a duty changed, an exam withdrawn), and nobody is named"""
    return f"❌ Cancelled{'' if by == 'app' else f' by {by}'}: {absent}'s absence on {days}. Its reliefs are no longer needed."


def late_text(absent, away, n):
    """n: how many of its lessons today wait for the team (picked, or open)"""
    return f"🆕 Late request for today · {absent}\n{away}\n" + (f"{n} lessons are" if n != 1 else "1 lesson is") + " waiting for your approval. Approve, then Send out."


def needed_text(day, lesson, periods, absent, who, waiting):
    """Relief needed again: who, the approved relief teacher, is away then and the lesson is open again; waiting: a new pick waits
    for the team's approval, else nobody else is free then"""
    then = "A new pick is waiting for your approval. Approve, then Send out." if waiting else NOBODY_ELSE
    return f"🔁 Relief needed again · {day}\n{lesson} · {periods} · for {absent}\n{_cover.AWAY.format(name=who)}. {then}"


def unlinked_text(name, what):
    """the blocked-bot alert: what, the plain words of what they did not get (refused)"""
    return f"⚠️ {name} has blocked the bot and is now unlinked.\nThey did not get: {what}.\nPlease tell them yourself."


def refused(item):
    """what a message (outbox's item) was, as the blocked-bot alert names it: a relief or its repeat by its lesson, any other kind
    by its label (words.KINDS), else "Message"; never its text"""
    ref, kind = item.get("ref") if isinstance(item.get("ref"), dict) else {}, item.get("kind")
    if kind in ("relief", "repeat") and all(ref.get(k) for k in ("lesson", "periods", "day")):
        return f"Relief for you · {ref['lesson']} {ref['periods']} on {ref['day']}"
    return words.KINDS.get(kind, "Message")


def work_text(day, lessons):
    """Please set work, to the teacher who is away: lessons, those of day without work (past five, the first five and how many more)"""
    items, n = [f"{words.class_group(x)} {words.periods_text(x)}" for x in lessons], len(lessons)
    listed = ", ".join(items[:5]) + (f" and {n - 5} more" if n > 5 else "")
    return f"✏️ Please set work · {day}\n" + (f"{n} lessons have" if n != 1 else "1 lesson has") + f" no work yet: {listed}.\nSet it in the app, in My absences. Your relief teacher sees it there."


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


def _to_cover(links, r):
    """how many lessons of the absence are to be covered: needed, and not stopped as far as is known"""
    return sum(1 for x in r.get("lessons") or [] if x.get("needed") and not _stopped(links, x))


def _waiting_today(r, today, now, bnds, links):
    """(waiting, open): how many covers of the absence (not cancelled) on today (ISO), needed, their lesson not over and not stopped
    as far as is known, have a pick waiting for the team's approval, and how many have none"""
    s = [_cover.state(r, x, c) for _, x, c, _k in _fill._covers([r], None, today, now, bnds) if not _stopped(links, x)]
    return s.count("waiting"), s.count("open")


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
    """the relief's own key, when key is that of its message, of a reminder (the own one with :r{n} after it) or of a repeat
    (:before, :morning), else None"""
    if not isinstance(ref, dict): return None
    k, m, p = relief_key(ref.get("absent"), ref.get("ckey"), ref.get("approved_at")), _COPY.fullmatch(key), _REPEAT.fullmatch(key)
    return next((x for x in (key, m and m[1], p and p[1]) if x in (k, f"{k}:{ref.get('who')}")), None)


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
    """[(key, ref)]: the last relief each person was told of, by its message, a reminder or a repeat of it, of each cover, its
    lesson not over: the relief's own key, and what its message holds when that went, else the last reminder or repeat (less
    its n, repeat and acked)"""
    last = {}
    for key, t in w.told.items():
        ref = t.get("ref")
        own = _own(key, ref)
        if t["state"] not in SENT or own is None or ref.get("who") not in w.reach: continue
        ends, at = _time(ref.get("ends")), _time(ref["approved_at"])
        if ends is None or ends <= w.now or at is None: continue
        cover, rank = (ref["who"], ref["absent"], ref["ckey"]), (at, key == own, ref.get("n") or 0)
        if cover not in last or last[cover][0] < rank: last[cover] = (rank, own, {k: v for k, v in ref.items() if k not in ("n", "repeat", "acked")})
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


def _said_on(w, key, n):
    """whether the person was told, after the n-th message that the relief under key is stopped, that it is on: by its again, or by
    the relief or a reminder of it that went later"""
    if (w.told.get(f"again:{key}:{n}") or {}).get("state") in SENT: return True
    off = _time(w.told[f"stopped:{key}:{n}"]["at"])
    return any(t["state"] in SENT and when > off for when, _, t in w.said._messages(key))


def _stops(w, key, ref, r, x, c):
    """stopped, when the lesson of a cover still theirs is stopped, unless that is the last they were told (_said_on); again, when
    it is on again (_on_again) for who was told that it was stopped; nothing while that is not known"""
    links = known(w.links, x["date"])
    if links is None: return
    why, what, ref_ = _cover.stopped(links, x), (ref["lesson"], ref["periods"], ref["start"], ref["day"]), dict(ref, id=r["id"])       # id: where the cover is now
    n = _times_told(w.told, "stopped", key)
    if why:
        if not n or _said_on(w, key, n - 1): yield _item(f"stopped:{key}:{n}", ref["who"], "stopped", stopped_text(*what, why), ref=ref_)
    elif n and _on_again(w.pub, w.settings.get("calendar") or {}, ref, r, x, c):
        yield _item(f"again:{key}:{n - 1}", ref["who"], "again", again_text(*what), _answers(r, x, ref["ckey"], ref["who"], w.base), ref=ref_)


def _absence(w, r):
    """what one absence (not past) has to say of itself"""
    if r.get("cancelled"): return _cancelled(w, r)
    out = _officer(w, r) + _work(w, r)
    if r.get("how") == "planned" and r.get("by") != r["teacher"] and not r.get("acknowledged") and r["teacher"] in w.reach: out = _planned(w, r) + out
    return _late(w, r) + out


def _late(w, r):
    """the late request: the absence sent for today, on a duty day at or after the morning time and before the cut-off, to each of
    the team but who sent it and the absent teacher, once its lessons wait for them; never a backup (exams); made only while the
    team may be pinged (_team_may), never later; not while a lesson is open (no pick, or none yet) and the absence is under
    NEW_WAIT old; a key there in any state (dropped too) is not made again"""
    if r.get("exams") or r.get("cancelled") or str(r["at"])[:10] != w.today.isoformat() or not _since(w, r["at"]): return []
    h, sent = _hours.of(w.settings), _time(r["at"])
    if sent is None or not _hours.at(w.today, h.morning) <= sent < _hours.at(w.today, h.cut_off) or not _hours.duty_day(w.settings, w.pub, w.today): return []
    if not _team_may(w.now, w.settings, w.pub): return []
    waiting, open_ = _waiting_today(r, w.today.isoformat(), w.now, w.bnds, w.links)
    if (open_ and w.now - sent < NEW_WAIT) or waiting + open_ == 0: return []
    text, buttons = late_text(r["teacher"], words.away(r), waiting + open_), [[dict(text=OPEN_TODAY, url=w.base + "/relief#today")]]
    keys = [(f"late:{r['id']}:{n}", n) for n in w.team if n not in (r.get("by"), r["teacher"])]
    return [_item(key, n, "late", text, buttons, ref=dict(id=r["id"], date=w.today.isoformat())) for key, n in keys if key not in w.told]


def _since(w, v):
    t = _time(v)
    return t is not None and t >= w.since


def _cancelled(w, r):
    gone = r["cancelled"]
    if not _since(w, gone.get("at")) or _taken_over(r): return []
    by_itself = bool(r.get("exams")) and gone.get("by") == "app"
    told = [w.told.get(f"{kind}:{r['id']}") for kind in ("planned", "remind", "officer")]
    names = [r.get("by")] if r.get("how") == "planned" and not by_itself else []
    names = {n for n in names + [t["name"] for t in told if t and t["state"] in SENT] if n in w.reach}
    text = cancelled_text(gone.get("by"), r["teacher"], words.days(r))
    return [_item(f"cancelled:{r['id']}:{n}", n, "cancelled", text, ref=dict(id=r["id"], team=n not in names))        # team: as the team alone
            for n in sorted((names | set(() if by_itself else w.team)) - {gone.get("by")})]


def _taken_over(r):
    """a backup (exams) whose lessons moved into the teacher's own absence (absences._take_over): not cancelled to anyone"""
    return bool(r.get("exams")) and r["cancelled"].get("by") == "app" and r["cancelled"].get("why") == f"Moved to {r['teacher']}'s own absence."


def _planned(w, r):
    """the absence planned for a teacher who has not acknowledged it (with no button to cancel a backup: the next sync with the
    exams would make it again), and the reminder: never for an absence with no lesson to cover, or sent at or after the time the
    reminder goes (remind_at on the school day before; today or not)"""
    out, ref, days, n = [], dict(id=r["id"]), words.days(r), _to_cover(w.links, r)
    if _since(w, r.get("at")):
        buttons = [[dict(text=SET_WORK, url=w.base + "/relief#mine")]] + ([] if r.get("exams") else [[dict(text=NOT_NEEDED, what="cancel", id=r["id"])]])
        out.append(_item(f"planned:{r['id']}", r["teacher"], "planned", planned_text(days, words.away(r), r.get("by"), n), buttons, ref=ref))
    if n and _fill.nudge(r, w.pub, w.settings, w.now, w.today):
        first, at = min([x["date"] for x in r.get("lessons") or []] or r["dates"]), _time(r.get("at"))
        remind = _fill.due_at(w.settings.get("calendar") or {}, ((w.pub or {}).get("model") or {}).get("days") or [], first,
                              (w.settings.get("times") or {}).get("remind_at"), today=datetime.date.min)
        if at is not None and at < remind: out.append(_item(f"remind:{r['id']}", r["teacher"], "remind", remind_text(days), ref=ref))
    return out


def work_moments(date, settings):
    """(eve, day): when the teacher who is away is reminded to set work for lessons on date (a date or an ISO date text): the
    calendar day before at work_eve, and date at work_day, in school time"""
    d, h = _hours._day(date), _hours.of(settings)
    return _hours.at(d - datetime.timedelta(days=1), h.work_eve), _hours.at(d, h.work_day)


def _eve_until(eve):
    """when the evening reminder to set work, whose moment is eve, is made no more: WORK_EVE_UNTIL of that evening, or midnight
    when eve is at or after it"""
    until = _hours.at(eve.date(), datetime.time.fromisoformat(WORK_EVE_UNTIL))
    return until if eve < until else _hours.at(eve.date() + datetime.timedelta(days=1), datetime.time())


def _has_work(x):
    w = x.get("work") or {}
    return bool(w.get("text") or w.get("link") or w.get("files"))


def _no_work(r, date, now, bnds, links):
    """the lessons of the absence on date (ISO) that still want work, in period order: needed, not stopped as far as is known, not
    over (a cover of it still to end), with no text, link or file"""
    return sorted((x for x in r.get("lessons") or [] if x.get("date") == date and x.get("needed") and not _has_work(x) and not _stopped(links, x)
                   and not all(_fill._ended(x, c, now, bnds) for c in _cover.covers(x))), key=lambda x: int(x["p"]))


def _work(w, r):
    """Please set work (the module's doc), to the teacher who is away when they can be reached: for each date of the absence on its
    own, eve while eve <= now < day and before WORK_EVE_UNTIL of its evening (_eve_until: never at night), day from day on; each only when its moment is at least WORK_GAP after the absence was sent and
    not before the bot was connected; never of a backup or a cancelled absence. Any hour (ANY_HOUR)"""
    sent = _time(r.get("at"))
    if r.get("exams") or r.get("cancelled") or r["teacher"] not in w.reach or sent is None: return []
    out = []
    for date in sorted({x.get("date") for x in r.get("lessons") or [] if _hours._day(x.get("date"))}):
        eve, day = work_moments(date, w.settings)
        which, moment = ("eve", eve) if eve <= w.now < min(day, _eve_until(eve)) else ("day", day) if day <= w.now else (None, None)
        if which is None or moment - sent < WORK_GAP or moment < w.since: continue
        lessons = _no_work(r, date, w.now, w.bnds, w.links)
        if lessons: out.append(_item(f"work:{r['id']}:{date}:{which}", r["teacher"], "work", work_text(words.day(date), lessons),
                                     [[dict(text=OPEN, url=w.base + "/relief#mine")]], ref=dict(id=r["id"], date=date, which=which)))
    return out


def _officer(w, r):
    name = r.get("reporting_officer")
    if name not in w.reach or name in (r["teacher"], r.get("by")) or not _since(w, r.get("at")): return []
    kind = r.get("reason") if r.get("reason") in _absences.REASONS else "Other"        # one of the four, never anything typed
    text = officer_text(r["teacher"], words.days(r), words.away(r), kind, _to_cover(w.links, r) > 0)
    return [_item(f"officer:{r['id']}", name, "officer", text, ref=dict(id=r["id"]))]


def _of_cover(w, r, x, c, ckey):
    """what one cover (its lesson neither over nor stopped) has to say"""
    s = _cover.state(r, x, c)
    if s == "approved" and _cover.reached(r, x, c, w.now, w.settings, w.pub): yield from _relief(w, r, x, c, ckey)   # made once it goes, never early
    if s in ("approved", "acknowledged"): yield from _repeats(w, r, x, c, ckey)
    if s == "acknowledged": yield from _covered(w, r, x, c, ckey)
    if s == "change": yield from _ask(w, r, x, c, ckey)
    if s in ("open", "waiting"): yield from _needed(w, r, x, c, ckey)
    yield from _kept(w, r, x, c, ckey)


def _answers(r, x, ckey, who, base):
    """the buttons of a relief: its two answers, and Open in the app to Reliefs I'm covering (its work, its files) at base, the app's
    address (outbox leaves it out unless that is https)"""
    press = dict(id=r["id"], ckey=ckey, who=who, extra=dict(absent=r["teacher"], date=x["date"]))
    return [[dict(press, text=ACK, what="ack"), dict(press, text=CHANGE, what="change")], [dict(text=OPEN, url=base + "/relief#covering")]]


def _relief(w, r, x, c, ckey):
    """the relief message, with its buttons (_answers); its files stay in the app (none go with it)"""
    who, at = c["relief"], c["approved"].get("at")
    if who not in w.reach or not at: return
    lesson, periods, day, (start, end) = words.class_group(x), words.periods_text(c), words.day(x["date"]), words.times(w.pub, x, c)
    ref = dict(id=r["id"], absent=r["teacher"], ckey=ckey, approved_at=at, who=who, lesson=lesson, periods=periods, start=start, day=day,
               date=x["date"], ends=_ends(x, c, w.bnds).isoformat())
    yield _item(_relief_key_for(w.told, ref), who, "relief",
                relief_text(day, lesson, periods, f"{start}–{end}" if start and end else "", x.get("room"), r["teacher"], x.get("work") or {}),
                _answers(r, x, ckey, who, w.base), [], ref)


def _covered(w, r, x, c, ckey):
    """Who covers you, to the teacher who is away, once an acknowledgement (its own key: a relief moved and acknowledged anew is
    told anew): acknowledged since the bot was connected, never of a backup (exams: the person is on duty in school), nor when the
    teacher who is away is the relief teacher. The lesson is not over (due's covers)"""
    ack, who = c.get("ack") or {}, c.get("relief")
    if r.get("exams") or r["teacher"] not in w.reach or not who or who == r["teacher"] or not _since(w, ack.get("at")): return
    ref = dict(id=r["id"], absent=r["teacher"], ckey=ckey, who=who, at=ack["at"], date=x["date"], ends=_ends(x, c, w.bnds).isoformat())
    yield _item(f"covered:{r['teacher']}:{ckey}:{ack['at']}", r["teacher"], "covered",
                covered_text(words.day(x["date"]), words.class_group(x), words.periods_text(c), words.times(w.pub, x, c)[0], who), ref=ref)


def _repeats(w, r, x, c, ckey):
    """the repeats of a relief approved or acknowledged (the module's doc): its first message (the relief's own key) went at t0;
    before while hours.before_moment of its start is after t0, from it until the morning one's moment; morning while the earliest
    send-out time of its day is after t0, from it until the lesson starts; each not when the last message of the relief (Said.last:
    its first, a reminder, the other repeat, one queued too) is less than REPEAT_GAP before its moment, nor one approved before
    there was Send out. Whether it may go now (_teacher_may) is due's (GATES)"""
    mark = _cover.sent_out(c)
    if mark is None or mark.get("legacy"): return
    item = next(_relief(w, r, x, c, ckey), None)
    first = item and w.told.get(item["key"])
    t0 = _time(first["at"]) if first and first["state"] in SENT else None
    if t0 is None: return
    h, start = _hours.of(w.settings), _hours.starts(w.pub, x, c)
    morning, last = _hours.at(x["date"], h.send_from), w.said.last(item["key"])
    for name, moment, until in (("before", _hours.before_moment(start, w.settings, w.pub), morning), ("morning", morning, start)):
        if moment is None or not t0 < moment <= w.now < until or (last is not None and moment - last[0] < REPEAT_GAP): continue
        acked, ref = _cover.state(r, x, c) == "acknowledged", item["ref"]
        if acked:
            (s, e), today = words.times(w.pub, x, c), w.today.isoformat() == x["date"]
            text = repeat_text(ref["day"], ref["lesson"], ref["periods"], f"{s}–{e}" if s and e else "", x.get("room"), r["teacher"], today)
            buttons, files = [[dict(text=OPEN, url=w.base + "/relief#covering")]], []
        else: text, buttons, files = item["text"], item["buttons"], item["files"]
        yield _item(f"{item['key']}:{name}", item["name"], "repeat", text, buttons, files, dict(ref, repeat=name, acked=acked))


def relief_item(pub, reach, told, r, x, c, ckey, base=""):
    """the relief message of an approved cover, as outbox.queue takes it, or None (its teacher cannot be reached); base: the app's
    address, as the sweep has it"""
    w = types.SimpleNamespace(pub=pub, reach=reach, told=told, bnds=bounds((pub or {}).get("model") or {}), base=base or "")
    return next(_relief(w, r, x, c, ckey), None)


def _kept(w, r, x, c, ckey):
    h = _stands(r, x, c)
    if h is None or c["relief"] not in w.reach or not _since(w, h.get("at")): return
    yield _item(f"kept:{r['teacher']}:{ckey}:{h['at']}", c["relief"], "kept", kept_text(words.class_group(x), words.periods_text(c), words.day(x["date"])),
                ref=dict(id=r["id"], absent=r["teacher"], ckey=ckey, who=c["relief"], approved_at=c["approved"].get("at"), at=h["at"], date=x["date"],
                         ends=_ends(x, c, w.bnds).isoformat()))


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
                                                                      ends=_ends(x, c, w.bnds).isoformat(), starts=_hours.starts(w.pub, x, c).isoformat()))


def _needed(w, r, x, c, ckey):
    """Relief needed again, to each of the team but the relief teacher who is away and the teacher whose lesson it is (as the late
    request), once: the cover went back to open because its relief teacher is away then
    (cover.was_away) since the bot was connected, and is open or waiting again; made only while the team may be pinged
    (_team_may), never later; not of a lesson of today found before today's morning time (the morning message counts it); open,
    not before NEW_WAIT after it went back (its new pick may be on its way); a key there in any state (dropped too) is not made
    again"""
    away = _cover.was_away(c)
    if away is None or not _since(w, away["at"]) or not _team_may(w.now, w.settings, w.pub): return
    at, s = _time(away["at"]), _cover.state(r, x, c)
    if x["date"] == w.today.isoformat() and at < _hours.at(w.today, _hours.of(w.settings).morning): return
    if s == "open" and w.now - at < NEW_WAIT: return
    text = needed_text(words.day(x["date"]), words.class_group(x), words.periods_text(c), r["teacher"], away["who"], s == "waiting")
    ref = dict(id=r["id"], absent=r["teacher"], ckey=ckey, at=away["at"], ends=_ends(x, c, w.bnds).isoformat())
    for n in (n for n in w.team if n not in (away["who"], r["teacher"])):
        key = f"needed:{r['teacher']}:{ckey}:{away['at']}:{n}"
        if key not in w.told: yield _item(key, n, "needed", text, [[dict(text=OPEN_TODAY, url=w.base + "/relief#today")]], ref=ref)


def _unlinked(w, name, date, a):
    """the blocked-bot alert of name's block noted on date (links.alerts: a, dict(at, what)), to each of the team but name: made
    only while the team may be pinged, in the first team window at or after it was found (hours.team_window), never after it"""
    found = _time(a.get("at"))
    span = found and _team_may(w.now, w.settings, w.pub) and _hours.team_window(found, w.settings, w.pub)
    if not span or not span[0] <= w.now < span[1]: return
    text, buttons = unlinked_text(name, a.get("what") or "Message"), [[dict(text=OPEN_TODAY, url=w.base + "/relief#today")]]
    for n in w.team:
        if n != name: yield _item(f"unlinked:{name}:{date}:{n}", n, "unlinked", text, buttons, ref=dict(name=name, date=date))      # one there (not dropped) is left out by due


def _nobody_else(w, r, x, c, ckey):
    """nobody is free for the cover but the teacher who asked to change (False while that is not known)"""
    links = known(w.links, x["date"])
    if links is None: return False              # who is on a duty is not known
    try: got = _free.free_then(w.pub, w.settings, w.records, dict(x, key=ckey, p=int(c["p"]), n=int(c.get("n") or 1)), r["teacher"], links=links)
    except ValueError: return False             # no longer a school day in the calendar: nothing to say
    return not any(q["name"] != c["relief"] for g in got["groups"] for q in g["people"])


def due(pub, settings, records, now, reach, told, since, team=(), base="", shorts=None, unread=(), links=None, alerts=None):
    """every message there should be now and is not there yet -> [dict(key, name, kind, text, buttons, files, ref)], as
    outbox.queue takes them, in the order to queue them. Pure. reach: {name: chat} of the people who can be reached; told:
    what outbox.told_for gives for the TOLD keys; since: when the bot was connected (unknown: now); team: the names on the
    relief team; base: the app's address; shorts: {name: short name}; unread: the ids of the records that could not be read (a
    relief that should be in one of them is not said to be gone); links: what approved exams and events stop (fill._links;
    None: they cannot be read); alerts: the blocked-bot alerts noted (links.alerts)"""
    now = _fill._when(now)
    w = types.SimpleNamespace(pub=pub, settings=settings, records=records, now=now, today=now.date(), reach=reach, told=told, since=_time(since) or now,
                              team=sorted(n for n in set(team) if n in reach), base=base or "", shorts=shorts or {}, unread=unread, links=links,
                              bnds=bounds((pub or {}).get("model") or {}), said=Said(told), alerts=alerts or {})
    still = list(_each(sorted(records, key=lambda r: (str(r.get("at")), str(r.get("dates")))), lambda r: [r] if _last(r) >= w.today.isoformat() else []))
    covers = sorted(_each(still, lambda r: [t for t in _fill._covers([r], None, None, now, w.bnds) if not _stopped(links, t[1])]), key=lambda t: (t[1]["date"], int(t[2]["p"]), str(t[0]["id"]), t[3]))
    out = list(_each(_told_reliefs(w), lambda v: _of_told(w, *v)))       # what is theirs no more comes before what is theirs now
    out += _each(still, lambda r: _absence(w, r))
    out += _each(covers, lambda t: _of_cover(w, *t))
    out += _each(sorted(w.alerts.items()), lambda v: _unlinked(w, *v[0], v[1]))
    return [i for i in out if not _there(told, i["key"]) and _may(i, now, settings, pub)]


# ---- what has been said of a relief (the report, Remind, and Today's page)
def key_of(told, r, c, ckey):
    """the key of the relief message of cover c as it is approved now"""
    return _relief_key_for(told, dict(absent=r["teacher"], ckey=ckey, approved_at=c["approved"].get("at"), who=c["relief"]))


class Said:
    """what has been said of the reliefs, read once (said): told, what outbox.states_for gives for the RELIEFS keys. key: a relief
    message's; it, its reminders and its repeats are one relief's messages, those dropped as if they had never been.

    Someone told that a relief is stopped, and not surely (sent) told since that it is on again, has been told nothing: until a
    reminder has gone to them after that"""
    def __init__(self, told):
        self.told, self._copies, self._repeats = told, {}, {}
        for key, t in told.items():
            m, p = _COPY.fullmatch(key), _REPEAT.fullmatch(key)
            if m: self._copies.setdefault(m[1], {})[int(m[2])] = t
            elif p: self._repeats.setdefault(p[1], []).append(t)

    def copies(self, key):
        """the reminders of the relief, in any state: {n: told}"""
        return self._copies.get(key, {})

    def _messages(self, key):
        """[(when, n, told)]: the relief's messages, n 0 for the first and its repeats"""
        return [(_time(t["at"]), n, t) for n, t in [(0, self.told.get(key)), *self.copies(key).items(), *((0, t) for t in self._repeats.get(key, []))] if t]

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
        """(when, state) of the last of its messages that went, may have gone or is in the queue (a date-time), or None"""
        got = max((m for m in self._messages(key) if m[2]["state"] in LIVE), key=lambda m: m[:2], default=None)
        return got and (got[0], got[2]["state"])


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
                links=_fill._links(pub, settings.get("calendar") or {}), alerts=_links.alerts(now.date() - datetime.timedelta(days=_hours.AHEAD)))
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


# ---- quiet times: when the app's own messages may go, by kind (an answer to a person's own press or typing, relief/bot.py and
# relief/asking.py, goes at once and never through here)
TEACHER_KINDS = ("relief", "repeat", "gone", "moved", "stopped", "again", "kept")      # to a relief teacher, of a lesson: in their school hours


def _teacher_may(now, settings, pub, date, ends) -> bool:
    """a message to a relief teacher of a lesson on date (ISO), over at ends (a date-time or an ISO one), may go now: in school
    hours for it (hours.teacher_open), its lesson not over"""
    ends = ends if isinstance(ends, datetime.datetime) else _time(ends)
    return ends is not None and _hours.teacher_open(now, settings, pub, date) and _fill._when(now) < ends


def _team_may(now, settings, pub) -> bool:
    """the relief team may be pinged now (hours.team_open: a duty day, from the morning time to before the cut-off)"""
    return _hours.team_open(now, settings, pub)


def _ask_may(now, settings, pub, ref):
    """a request to change goes to the team in their window, or on its lesson's own day from the cut-off until the lesson starts"""
    if _team_may(now, settings, pub): return True
    now, starts = _fill._when(now), _time(ref.get("starts"))
    return starts is not None and starts.date() == now.date() and _hours.at(now.date(), _hours.of(settings).cut_off) <= now < starts


def _lesson_may(now, settings, pub, ref):
    return _teacher_may(now, settings, pub, ref.get("date") or str(ref.get("ends") or "")[:10], ref.get("ends"))


# GATES[kind](now, settings, pub, its ref) -> whether a message of that kind may be made, and may go, now. A kind not here goes at
# any hour, and is in ANY_HOUR with why. A later kind adds its line here, or to ANY_HOUR (a test holds every kind of CHECKS to one)
GATES = {**{kind: _lesson_may for kind in TEACHER_KINDS}, "ask": _ask_may, "askpick": _ask_may,
         "cancelled": lambda now, settings, pub, ref: not ref.get("team") or _team_may(now, settings, pub),     # the team's copy alone
         "unlinked": lambda now, settings, pub, ref: _team_may(now, settings, pub)}          # the blocked-bot alert: made again in its window (_unlinked)
ANY_HOUR = ("planned",                          # to the absent teacher: they need the evening to set work (call 9)
            "remind",                           # to the absent teacher, at remind_at the school day before (call 9)
            "officer",                          # to the reporting officer, at once (call 9)
            "report", "clear",                  # the team's report and all clear: made only at their marks of a school day, and OLD after 30 minutes
            "weekly",                           # the weekly summary: at its own setting, whatever the day (call 10)
            "morning",                          # the morning message: made only from the morning time, claimed once a day, dropped at the cut-off
            "late",                             # the late request keeps the team's window by its own rule (_late, _late_true): it is never made again once
                                                # dropped, so it must not be dropped as GATES' kinds are while nothing is published (a publish swaps folders)
            "covered",                          # Who covers you: goes when the relief teacher acknowledges, at whatever hour (in the app in the
                                                # evening too), to the teacher who is away, whom the quiet rule does not cover (call 13)
            "needed",                           # Relief needed again: as late, the team's window by its own rule (_needed, _needed_true), never made again
            "work",                             # Please set work: to the teacher who is away, at work_eve (18:00) and work_day (07:00) on purpose; the
                                                # quiet rule is for the relief team and the relief teachers (the spec's "on purpose")
            "new")                              # the ping the late request replaced: never made, and dropped by its check if still queued


def _may(item, now, settings, pub) -> bool:
    """the message (due's item, or a queued one) may be made, and may go, now, by its kind (GATES)"""
    gate = GATES.get(item.get("kind"))
    return gate is None or gate(now, settings, pub, item.get("ref") or {})


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


def _repeat_true(ref, name):
    """the relief is theirs still, as it was approved when the repeat was made, its lesson not stopped, acknowledged as the repeat
    says (ref acked: else the other form goes, made again), and its teacher may be messaged now (_teacher_may)"""
    got = _theirs(ref)
    if got is None or got[2]["approved"].get("at") != ref["approved_at"] or _cover.state(*got) != ("acknowledged" if ref.get("acked") else "approved"): return False
    pub = store.published()
    if not pub or not _lesson_may(_fill._when(None), _settings.load(pub), pub, ref): return False
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


def _absence_now(ref, acknowledged_too=True):
    """the absence, while it is still to come and not cancelled (nor acknowledged), else None"""
    r = _read(ref["id"])
    if r is None or r.get("cancelled") or _last(r) < _fill._when(None).date().isoformat(): return None
    return None if acknowledged_too and r.get("acknowledged") else r


def _remind_true(ref, name):
    """the absence is still to come, not answered, and has a lesson to cover"""
    r = _absence_now(ref)
    return r is not None and _to_cover(_exams()[2], r) > 0


def _work_true(ref, name):
    """the absence is not cancelled nor a backup, its moment's span is now still (eve: until day's moment and _eve_until), and a lesson of that
    date still wants work (_no_work); nothing published (a publish swaps folders) raises: it waits"""
    r = _read(ref["id"])
    if r is None or r.get("cancelled") or r.get("exams"): return False
    pub, cal, links = _exams()
    if not pub: raise ValueError("nothing is published")
    now, (eve, day) = _fill._when(None), work_moments(ref["date"], _settings.load(pub))
    if not (eve <= now < min(day, _eve_until(eve)) if ref.get("which") == "eve" else day <= now): return False
    return bool(_no_work(r, ref["date"], now, bounds(pub.get("model") or {}), links))


def _cancelled_true(ref, name):
    """the absence is not past, and a copy for the team alone goes to who is on it still"""
    r = _read(ref["id"])
    if r is None or _last(r) < _fill._when(None).date().isoformat(): return False
    return not ref.get("team") or _on_team(name)


def _covered_true(ref, name):
    """the relief is acknowledged still by the same teacher, at that very acknowledgement (one taken back by a change since is not
    so), its lesson not over nor stopped, not a backup, and its teacher not the one who is away"""
    got = None if _over(ref) else _now(ref)
    if got is None: return False
    r, x, c = got
    if r.get("exams") or c.get("relief") != ref["who"] or ref["who"] == r["teacher"] or _cover.state(r, x, c) != "acknowledged": return False
    return (c.get("ack") or {}).get("at") == ref["at"] and _stands_now(x)


def _late_true(ref, name):
    """the absence is not cancelled, its day is today still, the team may be pinged now (_team_may: one that comes due after the
    cut-off is dropped, and its key stays claimed), the person is on the team still, and a lesson of it today waits for the team
    (_waiting_today); nothing published (a publish swaps folders) raises: it waits"""
    r, now = _read(ref["id"]), _fill._when(None)
    if r is None or r.get("cancelled") or ref["date"] != now.date().isoformat() or not _on_team(name): return False
    pub, cal, links = _exams()
    if not pub: raise ValueError("nothing is published")
    if not _team_may(now, _settings.load(pub), pub): return False
    return sum(_waiting_today(r, ref["date"], now, bounds(pub.get("model") or {}), links)) > 0


def _needed_true(ref, name):
    """the cover is still open or waiting from that very going back to open (cover.was_away at ref's at), its lesson not over nor
    stopped, the team may be pinged now (one that comes due outside their window is dropped, and its key stays claimed) and the
    person is on it still; nothing published (a publish swaps folders) raises: it waits"""
    if _over(ref) or not _on_team(name): return False
    r = _read(ref["id"])
    if r is None or r.get("cancelled"): return False
    try: x, c = _cover.find(r, ref["ckey"])
    except ValueError: return False
    if _cover.state(r, x, c) not in ("open", "waiting") or (_cover.was_away(c) or {}).get("at") != ref["at"]: return False
    pub = store.published()
    if not pub: raise ValueError("nothing is published")
    return _team_may(_fill._when(None), _settings.load(pub), pub) and _stands_now(x)


def _unlinked_true(ref, name):
    """the person is on the team still, and the team may be pinged now; nothing published (a publish swaps folders) raises: it waits"""
    if not _on_team(name): return False
    pub = store.published()
    if not pub: raise ValueError("nothing is published")
    return _team_may(_fill._when(None), _settings.load(pub), pub)


# what is asked of a queued message, by its kind, before it goes: CHECK(its ref, its person) -> bool. A kind not here is always
# true (relief/report.py puts report, clear and weekly here, relief/morning.py morning)
CHECKS = dict(relief=_relief_true, repeat=_repeat_true, gone=_ended_true, moved=_ended_true, stopped=_stopped_true, again=_again_true, kept=_kept_true, ask=_ask_true,
              askpick=_ask_true, planned=lambda ref, name: _absence_now(ref) is not None, remind=_remind_true,
              officer=lambda ref, name: _absence_now(ref, False) is not None, cancelled=_cancelled_true, late=_late_true, needed=_needed_true, covered=_covered_true,
              unlinked=_unlinked_true, work=_work_true,
              new=lambda ref, name: False)            # new: the ping the late request replaced; one still queued from before is dropped


def still_true(item):
    """a queued message (outbox's item) may still go: inside its reader's hours (_may: dropped outside them, due makes it again when
    they come, if it is still true then), and true (CHECKS); what cannot be read raises (the queue waits and asks again)"""
    if item.get("kind") in GATES:
        pub = store.published()                 # nothing published (a publish swaps folders): dropped, made again by a later sweep
        if not pub or not _may(item, _fill._when(None), _settings.load(pub), pub): return False
    check = CHECKS.get(item.get("kind"))
    return True if check is None else check(item["ref"], item.get("name"))


outbox.VALID = still_true
outbox.WHAT = refused

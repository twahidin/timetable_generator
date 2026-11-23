"""The cover of a lesson in an absence record: who relieves it and how far that has gone (picked, approved by the relief
team, acknowledged by the relief teacher, asked to change), and a lesson split at a period boundary into parts.

A cover is the lesson itself or, once the lesson is split, one of its "parts" (dicts with p and n). Its fields are read with
.get, since stage 2's records have none: relief (a name or None), relief_by, pick (None or dict(who, by, reason, at), by
"planner" | "ai" | "app" | "team"), approved (None or dict(by, at)), sent_out (None or dict(by, at, approved_at): the relief
team released this approval to its teacher; written None with each approval, so a new approval needs a new Send out; a cover
approved before there was Send out has no such key and counts as sent out at its approval, see sent_out), ack (None or
dict(at)), change (None or dict(why, at, pick), pick None while being picked) and history (dict(what, who, by, at, why) for
every pick ever made and every step).
Every change is load, modify, save under absences._LOCK; nothing here calls the model.

links (exams.relief_links.Links, or None) says what approved exams and events do to a date. A lesson they stop is not picked
for, approved, given to anyone, split, joined, kept, acknowledged or asked to change (NOT_HAPPENING) and takes nobody's time; nothing of it is written, so a lesson that happens
again (the exam withdrawn) has the cover it had. Someone on an exam duty or at an event is not free (free.free_then)."""
import datetime

from relief import absences as _absences       # absences and free import this module too: no name of theirs is read at import
from relief import fill as _fill               # fill imports this module too: no name of theirs is read at import
from relief import free as _free
from relief import hours as _hours             # hours imports fill, which imports this module: no name of theirs is read at import
from relief import lessons as _lessons

NOT_FREE = "{name} is no longer free then. Choose someone else."
NOBODY = "Nobody is free then."
PLANNED = "Planned by {by} on {date}."
CHOSEN = "Chosen by {by} on {date}."
NOT_YOURS_COVER = "This relief is not yours."
NOT_WAITING = "This relief is not waiting for approval."
NO_SPLIT = "A lesson of one period cannot be split."
SPLIT_APPROVED = "This lesson's relief is approved already, so it cannot be split."
SPLIT_SENT = "Part of this lesson is approved already, so it cannot be joined again."
CHANGE_WHY = "Say in a line why you cannot take it."
ASKED_ALREADY = "You asked to change this relief already."
NO_CHANGE_ASKED = "Nobody has asked to change this relief."
NOT_HAPPENING = "This lesson is not happening: {why}."
PICK_CHANGED = "The pick has changed since you looked: look again before approving."
NOT_TO_SEND = "This relief is not approved yet."
SENT_ALREADY = "This relief is sent out already."
NOT_FREE_OUT = "{name} is no longer free then: change it"
BY = ("planner", "ai", "app", "team")
OPEN = dict(relief=None, relief_by=None, pick=None, approved=None, sent_out=None, ack=None, change=None)
APPROVED = ("approved", "acknowledged", "change")      # the states in which a relief is approved to its teacher


def stopped(links, x):
    """why an approved exam or event stops lesson x ("3B is on Sec 3 End-of-Year Exam"), or "" (also with no links)"""
    return links.stopped(x) if links is not None else ""


def _happens(links, x):
    why = stopped(links, x)
    if why: raise ValueError(NOT_HAPPENING.format(why=why))


def covers(x):
    """the covers of lesson x: its parts when it is split, else the lesson itself"""
    return x.get("parts") or [x]


def cover_key(x, i):
    return f'{x["key"]}#{i}' if x.get("parts") else x["key"]


def _key_of(x, c):
    for i, y in enumerate(covers(x)):
        if y is c or (y.get("p") == c.get("p") and y.get("n") == c.get("n")): return cover_key(x, i)
    raise ValueError(_absences.CHANGED)


def find(record, ckey):
    """-> (lesson, cover) for a cover key; a key no longer there (the lesson split or joined since) is CHANGED"""
    for x in record.get("lessons") or []:
        for i, c in enumerate(covers(x)):
            if cover_key(x, i) == ckey: return x, c
    raise ValueError(_absences.CHANGED)


def _day(at):
    """'Sat 17 Oct' for an ISO date-time"""
    return _absences._say(datetime.date.fromisoformat(str(at)[:10]))


def pick_of(record, c):
    """the cover's pick: its own, or for a stage 2 planner's choice (relief set, no pick) the planner's, on the day it was sent"""
    who = c.get("relief")
    if not who: return None
    p = c.get("pick")
    if isinstance(p, dict) and p.get("who") == who: return p
    at = record.get("at") or ""
    return dict(who=who, by="planner", reason=PLANNED.format(by=c.get("relief_by") or record.get("by") or "", date=_day(at) if at else ""), at=at)


def state(record, x, c):
    """"cancelled" | "open" | "waiting" | "approved" | "acknowledged" | "change" (approved, and the relief teacher asked to change)"""
    if record.get("cancelled") or not x.get("needed"): return "cancelled"
    if not c.get("relief"): return "open"
    if not c.get("approved"): return "waiting"
    if c.get("change"): return "change"
    return "acknowledged" if c.get("ack") else "approved"


def _log(c, what, who, by, at, why=None):
    c.setdefault("history", []).append(dict(what=what, who=who, by=by, at=at, why=why))


def _settle(record, c):
    """a relief set with no pick of its own (a planner's choice from stage 2's absences.new) is written down as its pick, with
    its history line, by the first change that touches the cover: so the history keeps every pick ever made"""
    if not c.get("relief") or pick_of(record, c) is c.get("pick"): return
    p = c["pick"] = pick_of(record, c)
    _log(c, "pick", p["who"], "planner", p["at"], p["reason"])


def clear(record, x, by, why, at):
    """every cover of x back to nothing (absences.cancel and not_needed): a relief there was is kept in history as dropped,
    a request to change closes"""
    for c in covers(x):
        if c.get("relief"):
            _settle(record, c)
            _log(c, "dropped", c["relief"], by, at, why)
        c.update(OPEN)


def still_free(pub, settings, records, record, x, c, who, links=None):
    """who is in free.free_then for the cover's periods; the cover itself (its key, this absent teacher) takes nobody's time"""
    lesson = dict(x, key=_key_of(x, c), p=int(c["p"]), n=int(c.get("n") or 1))
    got = _free.free_then(pub, settings, records, lesson, record["teacher"], links=links)
    return who in [p["name"] for g in got["groups"] for p in g["people"]]


def new_pick(c):
    """the new pick of a request to change waiting for the team (dict(who, by, reason, at)), or None"""
    return (c.get("change") or {}).get("pick") or None


def booked(c):
    """the people the cover takes the time of: its relief (the teacher who asked to change, until the team acts) and the
    new pick of a request to change"""
    out = [c["relief"]] if c.get("relief") else []
    new = (new_pick(c) or {}).get("who")
    return out + [new] if new and new not in out else out


def stale(pub, settings, records, record, x, c, into="pick", links=None):
    """the cover has a relief teacher who is no longer free then: teaching, away, on an exam duty or at an event, given an
    overlapping relief, or never; into="change": the new pick of its request to change is no longer free then. Never for a
    lesson that is stopped: it takes nobody's time"""
    if stopped(links, x): return False
    if into == "change":
        new = new_pick(c) if state(record, x, c) == "change" else None
        return bool(new) and not still_free(pub, settings, records, record, x, c, new["who"], links=links)
    return state(record, x, c) not in ("cancelled", "open") and not still_free(pub, settings, records, record, x, c, c["relief"], links=links)


def _open(id, ckey):
    """under the lock: the record (not cancelled), the lesson and the cover; a lesson dated before today is refused"""
    r = _absences._editable(id)
    x, c = find(r, ckey)
    _absences._past(x)
    return r, x, c


def _check_pick(pick):
    if not isinstance(pick, dict) or not isinstance(pick.get("who"), str) or not pick["who"] or pick.get("by") not in BY:
        raise ValueError(_absences.WRONG)
    return dict(who=pick["who"], by=pick["by"], reason=str(pick.get("reason") or ""), at=pick.get("at") or _absences._now())


def set_pick(id, ckey, pick, pub, settings, *, into="pick", links=None):
    """save a pick worked out outside the lock (the relief, waiting for approval; into="change": a change request's new pick),
    only while the cover is still open (or still asked to change with no new pick, and the pick is not the teacher who
    asked) and the person still free, else NOT_FREE"""
    if into not in ("pick", "change"): raise ValueError(_absences.WRONG)
    pick, pub = _check_pick(pick), _absences._pub(pub)
    with _absences._LOCK:
        r = _absences.load(id)
        if r is None: raise ValueError(_absences.WRONG)
        x, c = find(r, ckey)
        _absences._past(x)
        _happens(links, x)
        s = state(r, x, c)
        ok = s == "open" if into == "pick" else s == "change" and not c["change"].get("pick") and pick["who"] != c["relief"]
        if not ok or not still_free(pub, settings, _absences.all_records(), r, x, c, pick["who"], links=links): raise ValueError(NOT_FREE.format(name=pick["who"]))
        _settle(r, c)
        if into == "pick": c.update(relief=pick["who"], relief_by=None, pick=pick)
        else: c["change"]["pick"] = pick
        _log(c, "pick", pick["who"], pick["by"], pick["at"], pick["reason"])
        _absences._save(r)
    return r


def drop(id, ckey, why, who=None, *, into="pick"):
    """a waiting pick back to open (its person is no longer free; the caller checked stale); an approved one is never dropped.
    who: the relief the caller found no longer free; when the cover's relief is not who by now (a planner chose again since,
    or it was dropped already), nothing is dropped or saved and the record is returned as it is. into="change": the new
    pick of a request to change back to None, to be picked again (the request and its relief stay); NOT_WAITING when the
    cover has none; who as above, for the new pick"""
    if into not in ("pick", "change"): raise ValueError(_absences.WRONG)
    with _absences._LOCK:
        r, x, c = _open(id, ckey)
        if into == "change":
            new = new_pick(c) if state(r, x, c) == "change" else None
            if who is not None and (new or {}).get("who") != who: return r
            if not new: raise ValueError(NOT_WAITING)
            _settle(r, c)
            _log(c, "dropped", new["who"], "app", _absences._now(), why if isinstance(why, str) else None)
            c["change"]["pick"] = None
            _absences._save(r)
            return r
        if who is not None and c.get("relief") != who: return r
        if state(r, x, c) != "waiting": raise ValueError(NOT_WAITING)
        _settle(r, c)
        _log(c, "dropped", c["relief"], "app", _absences._now(), why if isinstance(why, str) else None)
        c.update(relief=None, relief_by=None, pick=None)
        _absences._save(r)
    return r


def _approve(r, x, c, who, by, pub, settings, records, now, waiting_only=False, links=None):
    """in memory: a waiting cover approved, or a change request's new pick made the relief, only while that pick is still
    who (the name the team member was shown), else PICK_CHANGED (also when it has been dropped since and not picked
    again); the person is checked again. waiting_only (Approve all): a waiting cover alone, a request to change NOT_WAITING"""
    s = state(r, x, c)
    if s != "cancelled": _happens(links, x)
    if s == "waiting": pick = pick_of(r, c)
    elif s == "change" and not waiting_only: pick = new_pick(c)
    elif s == "open": pick = None
    else: raise ValueError(NOT_WAITING)
    if pick is None or pick["who"] != who: raise ValueError(PICK_CHANGED)
    if not still_free(pub, settings, records, r, x, c, pick["who"], links=links): raise ValueError(NOT_FREE.format(name=pick["who"]))
    _settle(r, c)
    if s == "change": c.update(relief=pick["who"], relief_by=None)
    c.update(pick=pick, approved=dict(by=by, at=now), sent_out=None, ack=None, change=None)
    _log(c, "approved", pick["who"], by, now)


def approve(id, ckey, who, by, pub, settings, links=None):
    """a person on the relief team approves the pick they were shown, who: the waiting pick, or a request to change's new
    pick; PICK_CHANGED, before anything is read, when who is not a name, and under the lock when that pick is no longer
    who. A checked limit is no reason to refuse (a person decides), not being free is"""
    if not isinstance(who, str) or not who: raise ValueError(PICK_CHANGED)
    pub = _absences._pub(pub)
    with _absences._LOCK:
        r, x, c = _open(id, ckey)
        _approve(r, x, c, who, by, pub, settings, _absences.all_records(), _absences._now(), links=links)
        _absences._save(r)
    return r


def _shown(rows):
    """the covers Approve all or Send out all was sent, [dict(id, ckey, who, approved_at)] -> [(id, ckey, who, approved_at)]
    (approved_at None when not sent): None (a page that did not send what it showed) is PICK_CHANGED, anything else not such
    a list WRONG; a row without a name is kept, to be skipped"""
    if rows is None: raise ValueError(PICK_CHANGED)
    if not isinstance(rows, list): raise ValueError(_absences.WRONG)
    out = []
    for v in rows:
        if not isinstance(v, dict) or not all(isinstance(v.get(k), str) and v[k] for k in ("id", "ckey")): raise ValueError(_absences.WRONG)
        out.append((v["id"], v["ckey"], v.get("who"), v.get("approved_at")))
    return out


def approve_all(date, shown, by, pub, settings, links=None):
    """approve the waiting covers the team member was shown on date (a date or an ISO string), shown=[dict(id, ckey, who)]
    with who the pick shown, in time order: each only while it is still waiting for that person (else PICK_CHANGED, or
    NOT_WAITING once approved or asked to change) and they are still free (else NOT_FREE); a cover not on date, or gone, is
    skipped too. -> dict(approved=[(id, ckey, who)], skipped=[dict(id, ckey, name, why)]), name the person shown"""
    pub, iso = _absences._pub(pub), _free._iso(date)
    if datetime.date.fromisoformat(iso) < _lessons.today(): raise ValueError(_absences.PAST_LESSON)
    shown = _shown(shown)
    with _absences._LOCK:
        records, now, rows, skipped = _absences.all_records(), _absences._now(), [], []
        by_id = {r["id"]: r for r in records}
        for id, ckey, who, _ in shown:
            try:
                r = by_id.get(id)
                if r is None: raise ValueError(_absences.WRONG)
                if r.get("cancelled"): raise ValueError(_absences.CANCELLED)
                x, c = find(r, ckey)
                if x.get("date") != iso: raise ValueError(_absences.WRONG)
            except ValueError as e:
                skipped.append(dict(id=id, ckey=ckey, name=who, why=str(e))); continue
            rows.append((int(c["p"]), r["teacher"], ckey, id, who, r, x, c))
        rows.sort(key=lambda t: t[:4])
        done, saved = [], {}
        for _, _, ckey, id, who, r, x, c in rows:  # records is the list each check reads: an approval is seen by the next
            try: _approve(r, x, c, who, by, pub, settings, records, now, waiting_only=True, links=links)
            except ValueError as e:
                skipped.append(dict(id=id, ckey=ckey, name=who, why=str(e))); continue
            done.append((id, ckey, who)); saved[id] = r
        for r in saved.values(): _absences._save(r)
    return dict(approved=done, skipped=skipped)


def change(id, ckey, who, by, pub, settings, links=None):
    """the team gives the cover to who and approves it in one (an open one, a waiting one, an approved one, a change request);
    the relief it replaces and a request's new pick, when not who, are written down as dropped"""
    if not isinstance(who, str) or not who: raise ValueError(_absences.WRONG)
    pub = _absences._pub(pub)
    with _absences._LOCK:
        r, x, c = _open(id, ckey)
        if not x.get("needed"): raise ValueError(_absences.NO_NEED)
        _happens(links, x)
        if not still_free(pub, settings, _absences.all_records(), r, x, c, who, links=links): raise ValueError(NOT_FREE.format(name=who))
        _settle(r, c)
        now = _absences._now()
        for gone in booked(c):                  # the relief and a request's new pick it replaces end here
            if gone != who: _log(c, "dropped", gone, by, now)
        pick = dict(who=who, by="team", reason=CHOSEN.format(by=by, date=_day(now)), at=now)
        c.update(relief=who, relief_by=by, pick=pick, approved=dict(by=by, at=now), sent_out=None, ack=None, change=None)
        _log(c, "pick", who, "team", now, pick["reason"])
        _log(c, "changed", who, by, now)
        _absences._save(r)
    return r


def _dt(v):
    """an ISO date-time (as records hold it) or a date-time, as a date-time in school time (one kept without its offset is in
    school time); None for anything else"""
    try: return _fill._when(v) if isinstance(v, (str, datetime.datetime)) else None
    except ValueError: return None


def sent_out(c):
    """how the cover's approval was sent out to its teacher, dict(by, at, approved_at), while that is its approval now; a cover
    approved before there was Send out (no sent_out key at all) counts as sent out at its approval, legacy=True; else None"""
    a = c.get("approved")
    if not isinstance(a, dict): return None
    if "sent_out" not in c: return dict(by=a.get("by"), at=a.get("at"), approved_at=a.get("at"), legacy=True)
    s = c.get("sent_out")
    return s if isinstance(s, dict) and s.get("approved_at") == a.get("at") else None


def goes_at(c, x, settings, pub):
    """when the cover's relief reaches (or reached) its teacher, a date-time: a legacy approval at its approval; else at the
    first moment of school hours from its Send out on (hours.reaches_at); None when it is not sent out (or that is not known)"""
    s = sent_out(c)
    if s is None: return None
    if s.get("legacy"): return _dt(s.get("at"))
    return _hours.reaches_at(s["at"], settings, pub, x.get("date"))


def reached(r, x, c, now, settings, pub):
    """the cover's relief has reached its teacher by now (a date-time or an ISO text): approved to them (approved,
    acknowledged, asked to change), sent out, and its time has come"""
    if state(r, x, c) not in APPROVED: return False
    at, now = goes_at(c, x, settings, pub), _dt(now)
    return at is not None and now is not None and now >= at


def _send_out(r, x, c, who, by, pub, settings, records, now, approved_at=None, links=None):
    """in memory: the cover's approval sent out, only while it is approved to who (and approved at approved_at, when given:
    the approval the team member was shown), not stopped and who still free"""
    if sent_out(c) is not None and state(r, x, c) in APPROVED: raise ValueError(SENT_ALREADY)
    if state(r, x, c) != "approved": raise ValueError(NOT_TO_SEND)
    if c.get("relief") != who or approved_at not in (None, c["approved"].get("at")): raise ValueError(PICK_CHANGED)
    _happens(links, x)
    if not still_free(pub, settings, records, r, x, c, who, links=links): raise ValueError(NOT_FREE_OUT.format(name=who))
    c["sent_out"] = dict(by=by, at=now, approved_at=c["approved"]["at"])
    _log(c, "sent out", who, by, now)


def send_out(id, ckey, who, by, pub, settings, links=None, approved_at=None):
    """a person on the relief team sends an approved relief out to its teacher, who: the relief teacher the page showed,
    approved_at: the approval it showed (None: any). Refused with SENT_ALREADY once this approval is sent out, NOT_TO_SEND
    when it is not approved, PICK_CHANGED when it is approved to someone else or again since (also when who is not a name),
    NOT_HAPPENING, or NOT_FREE_OUT when who is no longer free then. It reaches them at once in school hours, else at the next
    earliest send-out time (goes_at)"""
    if not isinstance(who, str) or not who: raise ValueError(PICK_CHANGED)
    pub = _absences._pub(pub)
    with _absences._LOCK:
        r, x, c = _open(id, ckey)
        _send_out(r, x, c, who, by, pub, settings, _absences.all_records(), _absences._now(), approved_at, links=links)
        _absences._save(r)
    return r


def send_out_all(date, shown, by, pub, settings, links=None):
    """send out the approved covers the team member was shown on date (a date or an ISO string), shown=[dict(id, ckey, who,
    approved_at)], in time order, each as send_out checks it; a cover not on date, or gone, is skipped too. -> dict(sent=[(id,
    ckey, who)], skipped=[dict(id, ckey, name, why)]), name the person shown; each record saved once"""
    pub, iso = _absences._pub(pub), _free._iso(date)
    if datetime.date.fromisoformat(iso) < _lessons.today(): raise ValueError(_absences.PAST_LESSON)
    shown = _shown(shown)
    with _absences._LOCK:
        records, now, rows, skipped = _absences.all_records(), _absences._now(), [], []
        by_id = {r["id"]: r for r in records}
        for id, ckey, who, approved_at in shown:
            try:
                r = by_id.get(id)
                if r is None: raise ValueError(_absences.WRONG)
                if r.get("cancelled"): raise ValueError(_absences.CANCELLED)
                x, c = find(r, ckey)
                if x.get("date") != iso: raise ValueError(_absences.WRONG)
                if not isinstance(who, str) or not who: raise ValueError(PICK_CHANGED)
            except ValueError as e:
                skipped.append(dict(id=id, ckey=ckey, name=who, why=str(e))); continue
            rows.append((int(c["p"]), r["teacher"], ckey, id, who, approved_at, r, x, c))
        rows.sort(key=lambda t: t[:4])
        done, saved = [], {}
        for _, _, ckey, id, who, approved_at, r, x, c in rows:
            try: _send_out(r, x, c, who, by, pub, settings, records, now, approved_at, links=links)
            except ValueError as e:
                skipped.append(dict(id=id, ckey=ckey, name=who, why=str(e))); continue
            done.append((id, ckey, who)); saved[id] = r
        for r in saved.values(): _absences._save(r)
    return dict(sent=done, skipped=skipped)


def split(id, key, at, by, links=None):
    """split a lesson (by its key) at period at into two open parts; on a lesson split already, the part holding at is split
    the same way, so a lesson can have three parts or more. The part split keeps its place and the new part goes last, so a
    part's key never comes to mean another part (covers of a split lesson are not always in time order). Refused with
    NO_SPLIT for one period, SPLIT_APPROVED when that lesson or part is approved, WRONG when at is not strictly inside it."""
    with _absences._LOCK:
        r = _absences._editable(id)
        x = _absences._lesson(r, key)
        _absences._past(x)
        if not x.get("needed"): raise ValueError(_absences.NO_NEED)
        _happens(links, x)
        parts = x.get("parts")
        if parts:
            if not _absences._int(at): raise ValueError(_absences.WRONG)
            c = next((y for y in parts if int(y["p"]) <= at < int(y["p"]) + int(y.get("n") or 1)), None)
            if c is None: raise ValueError(_absences.WRONG)
        else: c = x
        p, n = int(c["p"]), int(c.get("n") or 1)
        if n == 1: raise ValueError(NO_SPLIT)
        if c.get("approved"): raise ValueError(SPLIT_APPROVED)
        if not _absences._int(at) or not p < at < p + n: raise ValueError(_absences.WRONG)
        _settle(r, c)
        _log(x, "split", c.get("relief"), by, _absences._now())
        if parts:
            c.update(OPEN, n=at - p)
            parts.append(dict(OPEN, p=at, n=p + n - at, history=[]))
        else:
            x.update(OPEN)
            x["parts"] = [dict(OPEN, p=p, n=at - p, history=[]), dict(OPEN, p=at, n=p + n - at, history=[])]
        _absences._save(r)
    return r


def join(id, key, by, links=None):
    """the parts of a split lesson made one open lesson again, their history kept; refused once a part is approved"""
    with _absences._LOCK:
        r = _absences._editable(id)
        x = _absences._lesson(r, key)
        _absences._past(x)
        parts = x.get("parts")
        if not parts: raise ValueError(_absences.CHANGED)
        _happens(links, x)
        if any(c.get("approved") for c in parts): raise ValueError(SPLIT_SENT)
        now = _absences._now()
        for c in parts: _settle(r, c)
        x["history"] = sorted(list(x.get("history") or []) + [h for c in parts for h in c.get("history") or []], key=lambda h: h.get("at") or "")
        for c in sorted(parts, key=lambda c: int(c["p"])):
            if c.get("relief"): _log(x, "dropped", c["relief"], by, now)     # a waiting pick on a part ends with the parts
        _log(x, "joined", None, by, now)
        x.pop("parts")
        x.update(OPEN)
        _absences._save(r)
    return r


def keep(id, ckey, by, links=None):
    """the team closes a request to change: the relief stays with the teacher who asked, and its new pick, if any, is
    written down as dropped"""
    with _absences._LOCK:
        r, x, c = _open(id, ckey)
        if state(r, x, c) != "change": raise ValueError(NO_CHANGE_ASKED)
        _happens(links, x)
        now, new = _absences._now(), new_pick(c)
        if new: _log(c, "dropped", new["who"], by, now)                     # the request's new pick is not needed now
        c["change"] = None
        _log(c, "kept", c["relief"], by, now)
        _absences._save(r)
    return r


def _mine(r, x, c, me, reached=None):
    """the cover is approved to me (approved, acknowledged, asked to change) and, when reached is given (a callable (r, x, c) ->
    bool: web._reached), has reached me; else NOT_YOURS_COVER"""
    if state(r, x, c) not in APPROVED or c.get("relief") != me or (reached is not None and not reached(r, x, c)): raise ValueError(NOT_YOURS_COVER)


def acknowledge_once(id, ckey, me, links=None, reached=None):
    """the approved relief teacher acknowledges (once; after asking to change, it takes the relief after all) -> (the record,
    whether this call did it: False when it was acknowledged already, on the page or on Telegram, and nothing was saved);
    reached: as _mine, asked under the lock"""
    with _absences._LOCK:
        r, x, c = _open(id, ckey)
        _mine(r, x, c, me, reached)
        _happens(links, x)
        if state(r, x, c) == "acknowledged": return r, False
        now = _absences._now()
        new = (c.get("change") or {}).get("pick")
        if new: _log(c, "dropped", new["who"], me, now)                     # the request's new pick is not needed now
        c.update(ack=dict(at=now), change=None)
        _log(c, "acknowledged", me, me, now)
        _absences._save(r)
    return r, True


def acknowledge(id, ckey, me, links=None, reached=None):
    """as acknowledge_once -> the record"""
    return acknowledge_once(id, ckey, me, links=links, reached=reached)[0]


def ask_change(id, ckey, why, me, links=None, reached=None):
    """the approved relief teacher asks to change, saying why in a line; the relief stays with them until the team acts;
    reached: as _mine, asked under the lock"""
    with _absences._LOCK:
        r, x, c = _open(id, ckey)
        _mine(r, x, c, me, reached)
        _happens(links, x)
        if state(r, x, c) == "change": raise ValueError(ASKED_ALREADY)
        why = why.strip() if isinstance(why, str) else ""
        if not 1 <= len(why) <= 200: raise ValueError(CHANGE_WHY)
        now = _absences._now()
        c.update(change=dict(why=why, at=now, pick=None), ack=None)
        _log(c, "asked to change", me, me, now, why)
        _absences._save(r)
    return r

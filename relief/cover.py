"""The cover of a lesson in an absence record: who relieves it and how far that has gone (picked, approved by the relief
team, acknowledged by the relief teacher, asked to change), and a lesson split at a period boundary into parts.

A cover is the lesson itself or, once the lesson is split, one of its "parts" (dicts with p and n). Its fields are read with
.get, since stage 2's records have none: relief (a name or None), relief_by, pick (None or dict(who, by, reason, at), by
"planner" | "ai" | "app" | "team"), approved (None or dict(by, at)), ack (None or dict(at)), change (None or dict(why, at,
pick), pick None while being picked) and history (dict(what, who, by, at, why) for every pick ever made and every step).
Every change is load, modify, save under absences._LOCK; nothing here calls the model."""
import datetime

from relief import absences as _absences       # absences and free import this module too: no name of theirs is read at import
from relief import free as _free
from relief import lessons as _lessons

NOT_FREE = "{name} is no longer free then. Choose someone else."
NOBODY = "Nobody is free then."
PLANNED = "Planned by {by} on {date}."
CHOSEN = "Chosen by {by} on {date}."
NOT_YOURS_COVER = "This relief is not yours."
NOT_WAITING = "This relief is not waiting for approval."
NO_SPLIT = "A lesson of one period cannot be split."
SPLIT_SENT = "Part of this lesson is approved already, so it cannot be joined again."
CHANGE_WHY = "Say in a line why you cannot take it."
ASKED_ALREADY = "You asked to change this relief already."
BY = ("planner", "ai", "app", "team")
OPEN = dict(relief=None, relief_by=None, pick=None, approved=None, ack=None, change=None)


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


def clear(x, by, why, at):
    """every cover of x back to nothing (absences.cancel and not_needed): a relief there was is kept in history as dropped,
    a request to change closes"""
    for c in covers(x):
        if c.get("relief"): _log(c, "dropped", c["relief"], by, at, why)
        c.update(OPEN)


def still_free(pub, settings, records, record, x, c, who):
    """who is in free.free_then for the cover's periods; the cover itself (its key, this absent teacher) takes nobody's time"""
    lesson = dict(x, key=_key_of(x, c), p=int(c["p"]), n=int(c.get("n") or 1))
    got = _free.free_then(pub, settings, records, lesson, record["teacher"])
    return who in [p["name"] for g in got["groups"] for p in g["people"]]


def stale(pub, settings, records, record, x, c):
    """the cover has a relief teacher who is no longer free then: teaching, away, given an overlapping relief, or never"""
    return state(record, x, c) not in ("cancelled", "open") and not still_free(pub, settings, records, record, x, c, c["relief"])


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


def set_pick(id, ckey, pick, pub, settings, *, into="pick"):
    """save a pick worked out outside the lock (the relief, waiting for approval; into="change": a change request's new pick),
    only while the cover is still open (or still asked to change with no new pick) and the person still free, else NOT_FREE"""
    if into not in ("pick", "change"): raise ValueError(_absences.WRONG)
    pick, pub = _check_pick(pick), _absences._pub(pub)
    with _absences._LOCK:
        r = _absences.load(id)
        if r is None: raise ValueError(_absences.WRONG)
        x, c = find(r, ckey)
        _absences._past(x)
        s = state(r, x, c)
        ok = s == "open" if into == "pick" else s == "change" and not c["change"].get("pick")
        if not ok or not still_free(pub, settings, _absences.all_records(), r, x, c, pick["who"]): raise ValueError(NOT_FREE.format(name=pick["who"]))
        if into == "pick": c.update(relief=pick["who"], relief_by=None, pick=pick)
        else: c["change"]["pick"] = pick
        _log(c, "pick", pick["who"], pick["by"], pick["at"], pick["reason"])
        _absences._save(r)
    return r


def drop(id, ckey, why):
    """a waiting pick back to open (its person is no longer free; the caller checked stale); an approved one is never dropped"""
    with _absences._LOCK:
        r, x, c = _open(id, ckey)
        if state(r, x, c) != "waiting": raise ValueError(NOT_WAITING)
        _log(c, "dropped", c["relief"], "app", _absences._now(), why if isinstance(why, str) else None)
        c.update(relief=None, relief_by=None, pick=None)
        _absences._save(r)
    return r


def _approve(r, x, c, by, pub, settings, records, now):
    """in memory: a waiting cover approved, or a change request's new pick made the relief; the person is checked again"""
    s = state(r, x, c)
    if s == "waiting": pick = pick_of(r, c)
    elif s == "change" and c["change"].get("pick"): pick = c["change"]["pick"]
    else: raise ValueError(NOT_WAITING)
    if not still_free(pub, settings, records, r, x, c, pick["who"]): raise ValueError(NOT_FREE.format(name=pick["who"]))
    if s == "change": c.update(relief=pick["who"], relief_by=None)
    c.update(pick=pick, approved=dict(by=by, at=now), ack=None, change=None)
    _log(c, "approved", pick["who"], by, now)


def approve(id, ckey, by, pub, settings):
    """a person on the relief team approves; a checked limit is no reason to refuse (a person decides), not being free is"""
    pub = _absences._pub(pub)
    with _absences._LOCK:
        r, x, c = _open(id, ckey)
        _approve(r, x, c, by, pub, settings, _absences.all_records(), _absences._now())
        _absences._save(r)
    return r


def approve_all(date, by, pub, settings):
    """approve every waiting cover on date (a date or an ISO string) in time order, skipping those no longer free
    -> dict(approved=int, skipped=[dict(ckey, name, why)])"""
    pub, iso = _absences._pub(pub), _free._iso(date)
    if datetime.date.fromisoformat(iso) < _lessons.today(): raise ValueError(_absences.PAST_LESSON)
    with _absences._LOCK:
        records, now, rows = _absences.all_records(), _absences._now(), []
        for r in records:
            for x in r.get("lessons") or []:
                if x.get("date") != iso: continue
                for i, c in enumerate(covers(x)):
                    if state(r, x, c) == "waiting": rows.append((int(c["p"]), r["teacher"], cover_key(x, i), r, x, c))
        rows.sort(key=lambda t: t[:3])
        done, skipped, saved = 0, [], {}
        for _, _, ckey, r, x, c in rows:          # records is the list each check reads: an approval is seen by the next
            try: _approve(r, x, c, by, pub, settings, records, now)
            except ValueError as e:
                skipped.append(dict(ckey=ckey, name=c["relief"], why=str(e))); continue
            done += 1; saved[r["id"]] = r
        for r in saved.values(): _absences._save(r)
    return dict(approved=done, skipped=skipped)


def change(id, ckey, who, by, pub, settings):
    """the team gives the cover to who and approves it in one (an open one, a waiting one, an approved one, a change request)"""
    if not isinstance(who, str) or not who: raise ValueError(_absences.WRONG)
    pub = _absences._pub(pub)
    with _absences._LOCK:
        r, x, c = _open(id, ckey)
        if not x.get("needed"): raise ValueError(_absences.NO_NEED)
        if not still_free(pub, settings, _absences.all_records(), r, x, c, who): raise ValueError(NOT_FREE.format(name=who))
        now = _absences._now()
        pick = dict(who=who, by="team", reason=CHOSEN.format(by=by, date=_day(now)), at=now)
        c.update(relief=who, relief_by=by, pick=pick, approved=dict(by=by, at=now), ack=None, change=None)
        _log(c, "pick", who, "team", now, pick["reason"])
        _log(c, "changed", who, by, now)
        _absences._save(r)
    return r


def split(id, key, at, by):
    """split a lesson (by its key) at period at, strictly inside it, into two open parts; refused for a lesson of one period
    or one approved already, and for a lesson split already (join it first: part keys go by their place)"""
    with _absences._LOCK:
        r = _absences._editable(id)
        x = _absences._lesson(r, key)
        _absences._past(x)
        if not x.get("needed"): raise ValueError(_absences.NO_NEED)
        if x.get("parts"): raise ValueError(_absences.CHANGED)
        p, n = int(x["p"]), int(x.get("n") or 1)
        if n == 1 or x.get("approved"): raise ValueError(NO_SPLIT)
        if not _absences._int(at) or not p < at < p + n: raise ValueError(_absences.WRONG)
        _log(x, "split", x.get("relief"), by, _absences._now())
        x.update(OPEN)
        x["parts"] = [dict(OPEN, p=p, n=at - p, history=[]), dict(OPEN, p=at, n=p + n - at, history=[])]
        _absences._save(r)
    return r


def join(id, key, by):
    """the parts of a split lesson made one open lesson again, their history kept; refused once a part is approved"""
    with _absences._LOCK:
        r = _absences._editable(id)
        x = _absences._lesson(r, key)
        _absences._past(x)
        parts = x.get("parts")
        if not parts: raise ValueError(_absences.CHANGED)
        if any(c.get("approved") for c in parts): raise ValueError(SPLIT_SENT)
        x["history"] = sorted(list(x.get("history") or []) + [h for c in parts for h in c.get("history") or []], key=lambda h: h.get("at") or "")
        _log(x, "joined", None, by, _absences._now())
        x.pop("parts")
        x.update(OPEN)
        _absences._save(r)
    return r


def keep(id, ckey, by):
    """the team closes a request to change: the relief stays with the teacher who asked"""
    with _absences._LOCK:
        r, x, c = _open(id, ckey)
        if state(r, x, c) != "change": raise ValueError(NOT_WAITING)
        c["change"] = None
        _log(c, "kept", c["relief"], by, _absences._now())
        _absences._save(r)
    return r


def _mine(r, x, c, me):
    if state(r, x, c) not in ("approved", "acknowledged", "change") or c.get("relief") != me: raise ValueError(NOT_YOURS_COVER)


def acknowledge(id, ckey, me):
    """the approved relief teacher acknowledges (once; after asking to change, it takes the relief after all)"""
    with _absences._LOCK:
        r, x, c = _open(id, ckey)
        _mine(r, x, c, me)
        if state(r, x, c) == "acknowledged": return r
        now = _absences._now()
        c.update(ack=dict(at=now), change=None)
        _log(c, "acknowledged", me, me, now)
        _absences._save(r)
    return r


def ask_change(id, ckey, why, me):
    """the approved relief teacher asks to change, saying why in a line; the relief stays with them until the team acts"""
    with _absences._LOCK:
        r, x, c = _open(id, ckey)
        _mine(r, x, c, me)
        if state(r, x, c) == "change": raise ValueError(ASKED_ALREADY)
        why = why.strip() if isinstance(why, str) else ""
        if not 1 <= len(why) <= 200: raise ValueError(CHANGE_WHY)
        now = _absences._now()
        c.update(change=dict(why=why, at=now, pick=None), ack=None)
        _log(c, "asked to change", me, me, now, why)
        _absences._save(r)
    return r

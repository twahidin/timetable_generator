"""What approved exams and events mean for relief on a date: which lessons do not run, who is busy and when. Only approved
copies count (as on the main site). Every answer is "", [] or 0 when the date is not a school day or there are no periods.
And the backups: the lessons of the people on an approved schedule's duties (or going with the event) that still run, sent
to relief as planned absences (backups, sync, sync_all) and marked on the exams page (mark)."""
import datetime, logging

from exams import days as _days
from exams import approval as _approval
from exams import schedules as _schedules
from relief import absences as _absences
from relief import lessons as _lessons
from relief.calendar import school_day

INVIGILATING = "Invigilating: %s"
AT_EVENT = "At event: %s"
EXAMS_BY = "Exams committee"
EXAMS_COMMITTEE = "the exams committee"
DUTY_CHANGED = "The duty changed."
HANDLED_BY_EXAMS = "Handled by the exams committee."
HANDLED_BY_IN_CHARGE = "Handled by the teacher in charge."
WITHDRAWN = "The schedule was withdrawn."
SYNC_FAILED = "exams: relief sync failed"
logger = logging.getLogger(__name__)


def _iso(date) -> str:
    return date.isoformat() if isinstance(date, (datetime.date, datetime.datetime)) else str(date)[:10]


def key_of(model, row, date, day) -> str:
    """relief's key for the model lesson `row` on `date` (a date or ISO)"""
    L = model["lessons"][row]
    return _lessons._key(_iso(date), day, int(L["p"]), int(L.get("n") or 1), list(L.get("classes") or []), L.get("subject") or "",
                         L.get("group") or "")


def _names(items):
    return ", ".join(items[:-1]) + " and " + items[-1] if len(items) > 1 else (items[0] if items else "")


class Links:
    def __init__(self, pub, cal, scheds):
        self.pub, self.cal = pub, cal or {}
        self.model = (pub or {}).get("model") or {}
        self.scheds = [dict(s, status="approved") for s in scheds or []]
        self.bnds = _days.bounds(self.model) if self.model else []
        self._days = {}
        self._duties = None

    @classmethod
    def load(cls, pub, cal):
        return cls(pub, cal, _schedules.on_site() if pub else [])

    def _date(self, date):
        try:
            return datetime.date.fromisoformat(_iso(date))
        except ValueError:
            return None

    def _day(self, date):
        """for one date: the timetable day, {key: text} of the lessons that do not run, {key: running-period set}"""
        iso = _iso(date)
        if iso in self._days:
            return self._days[iso]
        out = dict(day=None, stopped={}, runs={})
        self._days[iso] = out
        d = self._date(date)
        if d is None or not self.bnds or not self.scheds or not self.model.get("days"):
            return out
        try:
            day = school_day(self.cal, self.model["days"], d)
            if day is None:
                return out
            view = _days.merged_view(self.pub, self.cal, self.scheds, iso)
            wins = [(s, _days._windows(s, iso, self.model, self.bnds)) for s in self.scheds]
        except (ValueError, KeyError, IndexError, TypeError):
            return out
        out["day"] = day
        for r in view["lessons"]:
            L = self.model["lessons"][r["row"]]
            key = key_of(self.model, r["row"], iso, day)
            p0, n = int(L["p"]), int(L.get("n") or 1)
            periods = range(p0, min(p0 + n, len(self.bnds)))
            out["runs"][key] = {p for p in periods if not any(a <= self.bnds[p][0] and self.bnds[p][1] <= b for a, b in r["stopped"])}
            if r["running"] or not r["stopped"]:
                continue
            held = []
            for s, w in wins:
                mine = [c for c in r["classes"] if c in w and any(w[c][0] <= self.bnds[p][0] and self.bnds[p][1] <= w[c][1] for p in periods)]
                if mine:
                    held.append((min(w[c][0] for c in mine), s["name"], mine))
            held.sort(key=lambda h: h[0])
            classes = [c for c in r["classes"] if any(c in h[2] for h in held)]
            out["stopped"][key] = "%s %s on %s" % (", ".join(classes), "is" if len(classes) == 1 else "are",
                                                    _names([h[1] for h in held]))
        return out

    def stopped(self, lesson) -> str:
        """why a lesson does not run on its date: "3B is on Sec 3 End-of-Year Exam"; "" when a period of it runs"""
        return self._day(lesson["date"])["stopped"].get(lesson["key"], "")

    def _by_name(self):
        """{iso: {name: [(start, end, what, replaces)]}} from the approved duties and events, by start"""
        if self._duties is not None:
            return self._duties
        out = self._duties = {}
        if not self.bnds or not self.scheds:
            return out
        by_id = {s["id"]: s for s in self.scheds}
        try:
            rows = _schedules.busies(self.scheds, self.model)
        except (ValueError, KeyError, TypeError):
            return out
        for b in rows:
            s = by_id.get(b["id"])
            if s is None or not b.get("names"):
                continue
            if s.get("kind") == _schedules.EVENT:
                what, replaces = AT_EVENT % s.get("name"), "%s, the teacher in charge" % s.get("in_charge")
            else:
                what = INVIGILATING % s.get("name") + (" · %s" % b["room"] if b.get("room") else "")
                replaces = EXAMS_COMMITTEE
            for n in b["names"]:
                out.setdefault(b["date"], {}).setdefault(n, []).append((b["start"], b["end"], what, replaces, s))
        for names in out.values():
            for v in names.values():
                v.sort(key=lambda x: x[0])
        return out

    def _mine(self, name, date):
        d = self._date(date)
        if d is None or self._day(date)["day"] is None:
            return []
        return self._by_name().get(d.isoformat(), {}).get(name, [])

    def _span(self, p, n):
        last = min(p + max(int(n), 1), len(self.bnds)) - 1
        if p < 0 or p >= len(self.bnds):
            return None
        return self.bnds[p][0], self.bnds[last][1]

    def busy(self, name, date, p, n) -> str:
        """"Invigilating: {exam}" or "At event: {event}" for the first duty or event holding name over periods p..p+n-1"""
        span = self._span(p, n)
        if span is None:
            return ""
        for a, b, _, _, s in self._mine(name, date):
            if a < span[1] and span[0] < b:
                return (AT_EVENT if s.get("kind") == _schedules.EVENT else INVIGILATING) % s.get("name")
        return ""

    def duties(self, name, date, periods=None) -> list:
        """the person's duties and events that date, by start; periods=(from, to) keeps those overlapping those periods"""
        span = self._span(periods[0], periods[1] - periods[0] + 1) if periods else None
        if periods and span is None:
            return []
        return [dict(start=_days.hhmm(a), end=_days.hhmm(b), what=what, replaces=replaces)
                for a, b, what, replaces, _ in self._mine(name, date) if span is None or (a < span[1] and span[0] < b)]

    def week_change(self, name, dates) -> int:
        """periods more (+) or fewer (-) the person works on these dates: duty and event periods that are not a period of a
        lesson of theirs that runs, less the periods of their lessons that stop"""
        total = 0
        for date in dates:
            d = self._date(date)
            if d is None:
                continue
            mine = self._mine(name, date)
            day = self._day(date)
            try:
                own = _lessons.on_date(self.pub, self.cal, name, d)
            except ValueError:
                own = []
            running = set()
            for L in own:
                if L["key"] in day["stopped"]:
                    total -= L["n"]
                else:
                    running |= day["runs"].get(L["key"], set(range(L["p"], L["p"] + L["n"])))
            if mine:
                total += len([p for p, (x, y) in enumerate(self.bnds) if p not in running and any(a < y and x < b for a, b, *_ in mine)])
        return total


def _minutes(bnds, periods):
    """(start, end) minutes of periods [from, to] (0-based, inclusive), or of the whole day when None"""
    if not bnds:
        return None
    if not periods:
        return bnds[0][0], bnds[-1][1]
    a, b = max(int(periods[0]), 0), min(int(periods[1]), len(bnds) - 1)
    return (bnds[a][0], bnds[b][1]) if a <= b else None


def _away_spans(bnds, records) -> dict:
    """{(teacher, ISO date): [(start, end) minutes]}: each absence of relief's own (not cancelled, not a backup) over its
    periods, or over the whole day; a malformed record is skipped, never raised"""
    out = {}
    for r in records or []:
        try:
            if not isinstance(r, dict) or r.get("cancelled") or r.get("exams") or not isinstance(r.get("teacher"), str) or not r["teacher"]:
                continue
            span, dates = _minutes(bnds, r.get("periods")), r.get("dates")
            if not span or not isinstance(dates, list):
                continue
            isos = [datetime.date.fromisoformat(_iso(d)).isoformat() for d in dates]
        except (KeyError, ValueError, TypeError, IndexError):
            continue
        for d in isos:
            out.setdefault((r["teacher"], d), []).append(span)
    return out


def relief_busies(model, records) -> list:
    """busies (the shape schedules.busies gives) for relief's own records: whoever is away over their periods, and whoever
    is chosen to cover a lesson. A cancelled record gives none; a backup record (with exams) gives only the cover. A malformed
    record or lesson is skipped."""
    bnds = _days.bounds(model) if model else []
    out = []
    if not bnds:
        return out

    def busy(name, date, a, b, why):
        out.append(dict(id="relief", kind="relief", name="Relief", status="approved", date=_iso(date), start=a, end=b, room="",
                        names=[name], why=why))

    for (name, d), spans in _away_spans(bnds, records).items():
        for a, b in spans:
            busy(name, d, a, b, "is away then (relief)")
    for r in records or []:
        if not isinstance(r, dict) or r.get("cancelled") or not isinstance(r.get("lessons"), list):
            continue
        for x in r["lessons"]:
            if not isinstance(x, dict) or not x.get("needed") or not isinstance(x.get("relief"), str) or not x["relief"]:
                continue
            try:
                p = int(x["p"])
                last = min(p + max(int(x.get("n") or 1), 1), len(bnds)) - 1
                if p < 0 or p >= len(bnds):
                    continue
                busy(x["relief"], x["date"], bnds[p][0], bnds[last][1],
                     "covers relief then (%s %s)" % (", ".join(x.get("classes") or []), x.get("subject") or ""))
            except (KeyError, ValueError, TypeError):
                continue
    return out


def away_on(sched, model, records, today) -> list:
    """for an approved schedule (saved, or its approved copy as a schedule), dated today or later: dict(name, date, text) for
    each person on a duty or going with the event who has an absence (not a backup) overlapping their window then"""
    if sched.get("approved"):
        ap = _approval.as_schedule(sched)
    else:
        ap = sched if sched.get("status") in ("approved", "changes") else None
    bnds = _days.bounds(model) if model else []
    if not ap or not bnds:
        return []
    away = _away_spans(bnds, records)
    iso_today = _iso(today)
    out, seen = [], set()
    if ap.get("kind") == _schedules.EVENT:
        for b in _schedules.event_busy(dict(ap, status="approved"), model):
            if b["date"] < iso_today or not b["names"]:
                continue
            for n in b["names"]:
                if (n, b["date"]) not in seen and any(a < b["end"] and b["start"] < z for a, z in away.get((n, b["date"]), ())):
                    seen.add((n, b["date"]))
                    out.append(dict(name=n, date=b["date"], text="Away (from relief): %s on %s, going with the event. Replace them "
                                                                 "under Someone is away." % (n, _days.nice(b["date"]))))
    else:
        for d in (ap.get("made") or {}).get("duties") or []:
            if d["date"] < iso_today:
                continue
            for n in d.get("names") or []:
                if any(a < d["end"] and d["start"] < z for a, z in away.get((n, d["date"]), ())):
                    out.append(dict(name=n, date=d["date"], text="Away (from relief): %s on %s, on duty in %s %s\u2013%s. Replace "
                                                                 "them under Someone is away." % (n, _days.nice(d["date"]), d["room"],
                                                                                                  _days.hhmm(d["start"]), _days.hhmm(d["end"]))))
    out.sort(key=lambda x: (x["date"], x["name"]))
    return out


def _windows_of(ap, model):
    """[(name, ISO date, start, end)] of an approved copy: each name on an exam duty over the duty, each person going with
    an event over the event's window that date"""
    if ap.get("kind") == _schedules.EVENT:
        try:
            rows = _schedules.event_busy(dict(ap, status="approved"), model)
        except (KeyError, TypeError, ValueError):
            rows = []
    else:
        rows = (ap.get("made") or {}).get("duties") or []
    out = []
    for b in rows:
        try:
            out += [(n, _iso(b["date"]), int(b["start"]), int(b["end"])) for n in b.get("names") or [] if isinstance(n, str)]
        except (KeyError, TypeError, ValueError, AttributeError):
            continue
    return sorted(out)


def _live_backups(records):
    """relief's backups that are not cancelled (well-formed ones only)"""
    return [r for r in records or [] if isinstance(r, dict) and not r.get("cancelled") and isinstance(r.get("exams"), dict)
            and isinstance(r.get("teacher"), str)]


def _sent_elsewhere(records, sid) -> set:
    """{(teacher, lesson key)} held by a live backup of another schedule (needed or marked not needed)"""
    return {(r["teacher"], x["key"]) for r in _live_backups(records) if r["exams"].get("id") != sid
            for x in r.get("lessons") or [] if isinstance(x, dict) and isinstance(x.get("key"), str)}


def _handled_elsewhere(sid, links) -> set:
    """{(teacher, lesson key)} put in another approved schedule's "Handled ourselves" ({teacher}|{key}) while that
    schedule's approved copy still holds the teacher over the lesson (a duty, or going with the event, overlapping it):
    handled on one schedule covers that lesson for every schedule. A stale tag (the duty moved, the person replaced, the
    lesson gone) counts for nothing. links: the published timetable and calendar to read the lesson from (None: none)"""
    out = set()
    if links is None or not links.bnds:
        return out
    lessons = {}
    for o in _schedules.all_saved():
        if not isinstance(o, dict) or o.get("id") == sid or not o.get("approved"):
            continue
        tags = [tuple(t.split("|", 1)) for t in o.get("handled") or [] if isinstance(t, str) and "|" in t]
        ap = _approval.as_schedule(o) if tags else None
        if ap is None:
            continue
        wins = {}
        for name, iso, a, z in _windows_of(ap, links.model):
            wins.setdefault((name, iso), []).append((a, z))
        for name, key in tags:
            at = (name, key.split("/", 1)[0])
            if at not in wins:
                continue
            if at not in lessons:
                try:
                    lessons[at] = {x["key"]: x for x in _lessons.on_date(links.pub, links.cal, name, datetime.date.fromisoformat(at[1]))}
                except (ValueError, TypeError, KeyError):
                    lessons[at] = {}
            x = lessons[at].get(key)
            span = links._span(x["p"], x["n"]) if x else None
            if span and any(a < span[1] and span[0] < z for a, z in wins[at]):
                out.add((name, key))
    return out


def _held_elsewhere(records, sid, links) -> set:
    """{(teacher, lesson key)} another schedule holds: in its live backup, or handled by it (_handled_elsewhere)"""
    return _sent_elsewhere(records, sid) | _handled_elsewhere(sid, links)


def backups(pub, cal, sched, links, records, today) -> dict:
    """{name: [lessons]} (P7) from the schedule's approved copy: for each person on a duty (or going with the event), their
    lessons (relief.lessons.on_date, ISO dates) with a period that runs during the duty (or the event's window), dated today or
    later, not "Handled ourselves" ({name}|{key} in sched["handled"]), not while they are away in an absence of their own, and
    not already in another schedule's live backup of theirs (records: relief's; one lesson is sent once). A lesson that does
    not run (links.stopped: its classes are on this or another approved schedule) needs none. {} when the schedule has no
    approved copy."""
    ap = _approval.as_schedule(sched) if sched else None
    model = (pub or {}).get("model") or {}
    bnds = _days.bounds(model) if model else []
    if not ap or not bnds:
        return {}
    iso_today = _iso(today)
    handled = {x for x in sched.get("handled") or [] if isinstance(x, str)}
    away = _away_spans(bnds, records)
    elsewhere = _held_elsewhere(records, sched.get("id"), links)
    out, seen = {}, set()
    for name, iso, a, z in _windows_of(ap, model):
        if iso < iso_today:
            continue
        try:
            mine = _lessons.on_date(pub, cal, name, datetime.date.fromisoformat(iso))
        except ValueError:          # not a school day, or no calendar
            continue
        runs = links._day(iso)["runs"]
        for x in mine:
            if (name, x["key"]) in seen or (name, x["key"]) in elsewhere or "%s|%s" % (name, x["key"]) in handled or links.stopped(x):
                continue
            periods = runs.get(x["key"], range(x["p"], x["p"] + x["n"]))
            if not any(p < len(bnds) and bnds[p][0] < z and a < bnds[p][1] for p in periods):
                continue
            span = links._span(x["p"], x["n"])
            if span and any(s < span[1] and span[0] < e for s, e in away.get((name, iso), ())):
                continue
            seen.add((name, x["key"]))
            out.setdefault(name, []).append(dict(x, date=iso))
    return out


def _ahead(r, iso):
    """the keys of a record's lessons dated iso or later"""
    return {x["key"] for x in r.get("lessons") or [] if isinstance(x, dict) and x.get("key") and str(x.get("date") or "") >= iso}


def sync(sched, pub, cal, today, copies=None) -> dict:
    """keep relief's backups of the schedule in step with its approved copy (P6, P7, P9), changing them in place
    (relief.absences.update_exams: a lesson dated before today always stays); idempotent. Per person, the lessons wanted
    (backups) against the keys of their backup's lessons dated today or later: the same (and the same by and reason) changes
    nothing; else the backup is brought up to date (lessons no longer wanted go, new ones come in, cancelled only once it has
    no lesson at all: "Handled by the exams committee." (or "...the teacher in charge." for an event) when every lesson that
    left went because it is now "Handled ourselves", else "The duty changed."); no backup yet: a new one (from_exams). A schedule without an approved copy
    (withdrawn): every lesson dated today or later goes, and a backup left with none is cancelled "The schedule was
    withdrawn." (P12 as amended). A timetable with no periods or a calendar with no terms changes nothing. copies: the
    approved copies (schedules.on_site()), read here when None. Runs inside exams.schedules.editing(); relief.absences takes
    its own lock. -> dict(sent: backups made or given a lesson, cancelled)"""
    out = dict(sent=0, cancelled=0)
    sid = (sched or {}).get("id")
    if not sid:
        return out
    records = _absences.all_records()
    live = [r for r in _live_backups(records) if r["exams"].get("id") == sid]
    iso = _iso(today)
    links = None

    def update(r, keep, add, by, text, why):
        got = _absences.update_exams(r["id"], keep, add, by, text, today, why=why, links=links)
        if got.get("cancelled"):
            out["cancelled"] += 1
        elif add and {x.get("key") for x in got.get("lessons") or [] if isinstance(x, dict)} & {x["key"] for x in add}:
            out["sent"] += 1

    ap = _approval.as_schedule(sched)
    if ap is None:
        for r in live:
            if _ahead(r, iso):
                update(r, (), [], None, None, WITHDRAWN)
        return out
    model = (pub or {}).get("model") or {}
    if not (_days.bounds(model) if model else []) or not (cal or {}).get("terms"):
        return out
    links = Links(pub, cal, [s for s in (_schedules.on_site() if copies is None else copies) if s.get("id") != sid] + [ap])
    want = backups(pub, cal, sched, links, records, today)
    event = ap.get("kind") == _schedules.EVENT
    by = (ap.get("in_charge") or sched.get("in_charge") or "") if event else EXAMS_BY
    text = (AT_EVENT if event else INVIGILATING) % ap.get("name")
    source = dict(id=sid, kind=sched.get("kind"))
    handled = {x for x in sched.get("handled") or [] if isinstance(x, str)}
    mine = {}
    for r in live:
        mine.setdefault(r["teacher"], []).append(r)
    for name in sorted(set(want) | set(mine)):
        lessons = want.get(name, [])
        keys = {x["key"] for x in lessons}
        recs = sorted(mine.get(name, []), key=lambda r: (-len(_ahead(r, iso) & keys), r.get("at") or ""))
        if not recs:
            if lessons and _absences.from_exams(name, lessons, source, by, text, None, links=links):
                out["sent"] += 1
            continue
        main = recs[0]
        for r in recs[1:]:          # one backup per person per schedule: another one (a race) gives up its lessons to come
            if _ahead(r, iso):
                update(r, (), [], None, None, DUTY_CHANGED)
        if _ahead(main, iso) == keys and main.get("by") == by and main.get("reason_text") == text:
            continue
        held = {x.get("key") for x in main.get("lessons") or [] if isinstance(x, dict)}
        leaving = _ahead(main, iso) - keys
        why = DUTY_CHANGED
        if leaving and all("%s|%s" % (name, k) in handled for k in leaving):
            why = HANDLED_BY_IN_CHARGE if event else HANDLED_BY_EXAMS
        update(main, keys, [x for x in lessons if x["key"] not in held], by, text, why)
    return out


def to_sync(sid, scheds, records, today) -> list:
    """the schedules other than sid whose backups a sync may change: those with an approved copy that has a date today or
    later, and those with a live backup holding a lesson dated today or later (any other sync would change nothing)"""
    iso = _iso(today)
    held = {r["exams"].get("id") for r in _live_backups(records) if _ahead(r, iso)}
    out = []
    for s in scheds or []:
        if not isinstance(s, dict) or not s.get("id") or s["id"] == sid:
            continue
        ap = s.get("approved")
        if s["id"] in held or (isinstance(ap, dict) and _approval.last_date(ap) >= iso):
            out.append(s)
    return out


def sync_all(pub, cal, today, first=None) -> None:
    """relief's backups in step with every approved schedule: first (the schedule acted on) when given, then every other one
    a sync may change (to_sync), so a lesson one schedule gives up or stops goes to (or leaves) another at once. Called after
    every approval action and "Handled ourselves" change that saved, after relief's own create and cancel (once their call has
    returned and relief's lock is released) and after a publish. Each sync is idempotent; one failing never stops the others
    and this never raises: each failure is one log line (SYNC_FAILED) and the next sync puts it right. The caller holds
    exams.schedules.editing() (two syncs of one schedule never run at once); relief.absences takes its own lock inside."""
    try:
        copies = _schedules.on_site()
    except Exception:
        logger.exception(SYNC_FAILED)
        return
    if first is not None:
        try:
            sync(first, pub, cal, today, copies=copies)
        except Exception:
            logger.exception(SYNC_FAILED)
    try:
        others = to_sync((first or {}).get("id"), _schedules.all_saved(), _absences.all_records(), today)
    except Exception:
        logger.exception(SYNC_FAILED)
        return
    for o in others:
        try:
            sync(o, pub, cal, today, copies=copies)
        except Exception:
            logger.exception(SYNC_FAILED)


def mark(items, sched, records, links, today):
    """each backup item of the schedule's lessons lists (with teacher, key, date) gets state, relief and stopped, the first
    that holds: "handled" (Handled ourselves); "relief" (relief: the name) or "sent" when relief holds it (in a backup of this
    schedule, or as a needed lesson of an absence of the teacher's own: that absence covers it); "stopped" (stopped: why)
    when another approved schedule stops it (links: the other schedules' approved copies, or None); "past" when dated before
    today; "handled_elsewhere" when another schedule handled it (_handled_elsewhere); "elsewhere" when another schedule's
    backup of that person holds it; else "later" (it goes to relief when the schedule is approved). -> items"""
    sid = (sched or {}).get("id")
    iso_today = _iso(today)
    handled = {x for x in (sched or {}).get("handled") or [] if isinstance(x, str)}
    handled_else, elsewhere = _handled_elsewhere(sid, links), _sent_elsewhere(records, sid)
    held = {}
    for r in records or []:
        if not isinstance(r, dict) or r.get("cancelled") or not isinstance(r.get("teacher"), str):
            continue
        ex = r.get("exams")
        if ex and not (isinstance(ex, dict) and ex.get("id") == sid):
            continue
        for x in r.get("lessons") or []:
            if not isinstance(x, dict) or not isinstance(x.get("key"), str) or (not ex and not x.get("needed")):
                continue
            k = (r["teacher"], x["key"])
            name = x.get("relief") if x.get("needed") and isinstance(x.get("relief"), str) and x["relief"] else None
            if k not in held or (name and not held[k]):
                held[k] = name
    for it in items or []:
        k = (it.get("teacher"), it.get("key"))
        it["relief"], it["stopped"] = None, ""
        why = links.stopped(it) if links is not None and it.get("date") and it.get("key") else ""
        if "%s|%s" % k in handled:
            it["state"] = "handled"
        elif k in held:
            it["state"], it["relief"] = ("relief", held[k]) if held[k] else ("sent", None)
        elif why:
            it["state"], it["stopped"] = "stopped", why
        elif str(it.get("date") or "") < iso_today:
            it["state"] = "past"
        elif k in handled_else:
            it["state"] = "handled_elsewhere"
        elif k in elsewhere:
            it["state"] = "elsewhere"
        else:
            it["state"] = "later"
    return items

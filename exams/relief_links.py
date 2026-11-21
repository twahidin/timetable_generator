"""What approved exams and events mean for relief on a date: which lessons do not run, who is busy and when. Only approved
copies count (as on the main site). Every answer is "", [] or 0 when the date is not a school day or there are no periods."""
import datetime

from exams import days as _days
from exams import approval as _approval
from exams import schedules as _schedules
from relief import lessons as _lessons
from relief.calendar import school_day

INVIGILATING = "Invigilating: %s"
AT_EVENT = "At event: %s"
EXAMS_BY = "Exams committee"
EXAMS_COMMITTEE = "the exams committee"


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


def relief_busies(model, records) -> list:
    """busies (the shape schedules.busies gives) for relief's own records: whoever is away over their periods, and whoever
    is chosen to cover a lesson. A cancelled record gives none; a backup record (with exams) gives only the cover."""
    bnds = _days.bounds(model) if model else []
    out = []
    if not bnds:
        return out

    def busy(name, date, a, b, why):
        out.append(dict(id="relief", kind="relief", name="Relief", status="approved", date=_iso(date), start=a, end=b, room="",
                        names=[name], why=why))

    for r in records or []:
        if r.get("cancelled"):
            continue
        span = _minutes(bnds, r.get("periods"))
        if span and not r.get("exams") and r.get("teacher"):
            for d in r.get("dates") or []:
                busy(r["teacher"], d, span[0], span[1], "is away then (relief)")
        for x in r.get("lessons") or []:
            if not x.get("needed") or not x.get("relief"):
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
    away = {}
    for r in records or []:
        if r.get("cancelled") or r.get("exams") or not r.get("teacher"):
            continue
        span = _minutes(bnds, r.get("periods"))
        if span:
            for d in r.get("dates") or []:
                away.setdefault((r["teacher"], d), []).append(span)
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

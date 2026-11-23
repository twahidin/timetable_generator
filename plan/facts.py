"""What the planning chat may be shown about an exam. Pure functions: they read what they are given, change none of it and
write nothing. What they return goes (once names are replaced) to an AI outside the school, so it holds counts and
words about papers, days, levels and rooms, and never a student's name or id, extra time or an own room (access), seats
or duties (made, pins) or the log. A person's name is never a key of a result."""
import copy
from collections import Counter

from exams import days as _days
from exams import papers as _papers
from exams import settings as _settings
from exams.schedules import NO_CALENDAR

NO_PUB = "Publish the timetable first: exams read the classes, students and lessons from it."
NO_STUDENTS = ("The published timetable has no students yet. Everything can be filled in, but clashes between papers cannot "
               "be checked, no time can be suggested and seats cannot be made until the students are added and the "
               "timetable is published again.")
NO_ROOMS = "No exam rooms are set yet. Seats cannot be made until the rooms and their seats are set in the exam settings."
UNCHECKED = "Clashes not checked: no students yet."
NOT_CHECKED_CAL = "Not checked: no school calendar yet."
NOT_CHECKED_DATES = "Not checked: the exam has no dates yet."
COULD_NOT = "The checks could not run on this exam: open it on the exam page."
SETTINGS = "/exams/settings"
OWN_TIMES = dict(report="07:30", min_break=20, max_papers=2)          # what schedules.new sets
OWN_SEATING = dict(order="class", shared="levels", spacing="every", home_rooms=True)
SHARED = dict(levels="levels alternate", papers="papers alternate", blocks="one level per block")


ODD = (KeyError, TypeError, ValueError, IndexError, AttributeError)      # what a draft the app cannot read gives


def _model(pub) -> dict:
    return (pub or {}).get("model") or {}


def _dicts(sched, key) -> list:
    """the entries of a list in a draft that are dicts (anything else is skipped)"""
    v = (sched or {}).get(key)
    return [x for x in v if isinstance(x, dict)] if isinstance(v, list) else []


def _dict(sched, key) -> dict:
    v = (sched or {}).get(key)
    return v if isinstance(v, dict) else {}


def _access(sched) -> dict:
    return {a["student"]: a for a in _dicts(sched, "access") if a.get("student")}


# ---------------------------------------------------------------- the start checks
def missing(pub, cal, xset) -> list:
    """what must be there before the planning chat is any use: [dict(text, link, stops)]"""
    model = _model(pub)
    if not model:
        return [dict(text=NO_PUB, link="/", stops=True)]
    if not (cal or {}).get("terms"):
        return [dict(text=NO_CALENDAR, link="/relief/settings", stops=True)]
    out = []
    if not model.get("students"):
        out.append(dict(text=NO_STUDENTS, link="/", stops=False))
    if not (xset or {}).get("rooms"):
        out.append(dict(text=NO_ROOMS, link=SETTINGS, stops=False))
    return out


# ---------------------------------------------------------------- what the app's checks find
def _run(sched, pub, cal, xset) -> dict:
    """the checks with every access arrangement removed: dict(errors, warnings, hidden, unchecked, ran). hidden: lines of the
    full check that are not among them (they are there only because of extra time). ran is False when they could not run"""
    out = dict(errors=[], warnings=[], hidden=0, unchecked="", ran=False)
    model = _model(pub)
    if not (cal or {}).get("terms"):
        out["unchecked"] = NOT_CHECKED_CAL
    elif not (sched.get("start") and sched.get("end")):
        out["unchecked"] = NOT_CHECKED_DATES
    elif not model:
        out["unchecked"] = UNCHECKED
    else:
        rules = (xset or {}).get("rules")                       # None: the app's own defaults
        try:
            full = _papers.check(sched, model, cal, rules)
            bare = _papers.check(dict(sched, access=[]), model, cal, rules)
        except ODD:
            out["unchecked"] = COULD_NOT
            return out
        left = Counter(full["errors"]) + Counter(full["warnings"])
        left.subtract(Counter(bare["errors"]) + Counter(bare["warnings"]))
        out.update(errors=bare["errors"], warnings=bare["warnings"], hidden=sum(n for n in left.values() if n > 0), ran=True,
                   unchecked="" if model.get("students") else UNCHECKED)
    return out


def checks(sched, pub, cal, xset) -> dict:
    out = _run(sched, pub, cal, xset)
    out.pop("ran")
    return out


# ---------------------------------------------------------------- times a paper could have
def _up5(m) -> int:
    return -(-m // 5) * 5


def _timed(p) -> bool:
    try:
        _days.minutes(p["start"])
        return bool(p.get("date")) and isinstance(p.get("minutes"), int)
    except ODD:
        return False


def _why(k) -> str:
    if not k:
        return "No student of this paper has another paper that day."
    return f"Its students have at most {k} other {'paper' if k == 1 else 'papers'} that day."


def slots(sched, pub, cal, xset, paper_id, limit=3) -> list:
    """up to `limit` times a paper with no time could have: [dict(date, start, why)], best first. An offer is a time that adds
    no line to the app's own check: a school day of an exam day where the level sits, inside the day's window with the arrive
    and stay rules kept, at most max_papers a day and min_break between papers for every student (extra time counted), no two
    papers at once. A draft the app cannot read has no offers"""
    try:
        return _slots(sched, pub, cal, xset, paper_id, limit)
    except ODD:
        return []


def _slots(sched, pub, cal, xset, paper_id, limit) -> list:
    model = _model(pub)
    papers = _dicts(sched, "papers")
    paper = next((p for p in papers if p.get("id") == paper_id), None)
    if not model.get("students") or not paper or paper.get("date") or paper.get("start"):
        return []
    together = str(paper.get("together") or "").strip()
    mates = [q for q in papers if q is not paper and together and str(q.get("together") or "").strip() == together]
    if any(q.get("date") or q.get("start") for q in mates):      # a group with any date or start has no offers, as a paper with one has none
        return []
    group = [paper] + mates                                      # the untimed papers that must start together
    if not all(isinstance(m.get("minutes"), int) for m in group):
        return []
    sits = [_papers.who_sits(m, model) for m in group]
    if not sits[0] or len(set().union(*map(set, sits))) < sum(map(len, sits)):
        return []                                                # nobody sits it, or two of them share a student
    times = _dict(sched, "times")
    min_break, max_papers = times.get("min_break", 20), times.get("max_papers", 2)
    rules = (xset or {}).get("rules") or _settings.defaults()["rules"]
    arrive, stay = rules.get("arrive") or 0, rules.get("stay") or 0
    access = _access(sched)
    length = [{sid: _papers.ends(dict(start="00:00", minutes=m["minutes"]), sid, access) for sid in who} for m, who in zip(group, sits)]
    everyone = {sid for who in sits for sid in who}
    busy, starts, plain_ends = {}, {}, {}                        # by date: {student: [(start, end)]}, {starts}, {plain ends}
    for q in papers:
        if q in group or not _timed(q):
            continue
        d, st = q["date"], _days.minutes(q["start"])
        starts.setdefault(d, set()).add(st)
        plain_ends.setdefault(d, set()).add(st + q["minutes"])
        for sid in everyone.intersection(_papers.who_sits(q, model)):
            busy.setdefault(d, {}).setdefault(sid, []).append((st, _papers.ends(q, sid, access)))
    bnds = _days.bounds(model)
    day0, day1 = bnds[0][0], bnds[-1][1]
    found = []
    for day in _days.dates(sched, cal, model):
        if day["day"] is None or any(m.get("level") not in day["levels"] for m in group):
            continue
        d, first, last = day["date"], day["start"], day["end"]
        cand = {_up5(first + arrive) if first > day0 else first} | {a for a, _ in bnds if first <= a <= last}
        cand |= starts.get(d, set()) | {_up5(x + min_break) for x in plain_ends.get(d, ())}
        for st in cand:
            most = 0
            for m, who, own in zip(group, sits, length):
                if st < first or st + m["minutes"] > last or (first > day0 and st - first < arrive) or (last < day1 and last - (st + m["minutes"]) < stay):
                    most = None
                    break
                for sid in who:
                    ivs, end = busy.get(d, {}).get(sid, ()), st + own[sid]
                    if (last < day1 and m.get("who") in ("level", "groups") and end > last) or len(ivs) + 1 > max_papers or any((st < b and a < end) or 0 <= a - end < min_break or 0 <= st - b < min_break for a, b in ivs):
                        most = None
                        break
                    most = max(most, len(ivs))
                if most is None:
                    break
            if most is not None:
                found.append((most, d, st))
    found.sort()
    return [dict(date=d, start=_days.hhmm(st), why=_why(k)) for k, d, st in found[:limit]]


# ---------------------------------------------------------------- earlier exams
def last_values(sched, all_saved) -> dict | None:
    """the values of the newest exam of the same kind made before this one that the checklist can offer again, or None.
    With no sched, or none with a created_at, any other exam of the kind may be offered"""
    kind = (sched or {}).get("kind") or "exam"
    if kind not in ("exam", "test"):
        return None
    mine, made = (sched or {}).get("id"), (sched or {}).get("created_at")
    before = [x for x in all_saved or [] if isinstance(x, dict) and x.get("kind") == kind and x.get("id") and x["id"] != mine
              and (not made or (x.get("created_at") or "") < made)]
    if not before:
        return None
    s = max(before, key=lambda x: x.get("created_at") or "")
    return dict(id=s["id"], name=s.get("name") or "", **copy.deepcopy({k: s.get(k) for k in ("times", "seating", "supervision", "scripts")}))


# ---------------------------------------------------------------- the checklist
def _line(key, title, state, text, link):
    return dict(key=key, title=title, state=state, text=text, link=link)


def _plural(n, one, many) -> str:
    return f"{n} {one if n == 1 else many}"


def _times_text(t) -> str:
    t = t if isinstance(t, dict) else {}
    return f"Report {t.get('report') or 'not set'}, {_plural(t.get('min_break', 20), 'minute', 'minutes')} between papers, {t.get('max_papers', 2)} a day at most."


def _choices_text(seating, supervision, scripts) -> str:
    s = seating if isinstance(seating, dict) else {}
    return (f"Seated by {s.get('order', 'class')}, {SHARED.get(s.get('shared'), 'levels alternate')}, "
            f"{'own class in own home room' if s.get('home_rooms', True) else 'classes mixed'}, "
            f"{'a seat left between' if s.get('spacing') == 'gap' else 'every seat used'}; "
            f"{'supervised by invigilators' if supervision == 'invigilators' else 'supervised by the lesson teacher'}; "
            f"{'scripts go to ' + str(scripts) if scripts else 'no place for scripts yet'}.")


def _own_supervision(sched) -> str:
    return "lesson" if sched.get("kind") == "test" else "invigilators"


def checklist(sched, pub, cal, xset, last) -> list:
    """the lines of "Filled in so far": [dict(key, title, state, text, link)], in the order of the exam page's form"""
    xset = xset or {}
    draft = sched or {}
    link = f"/exams/{draft['id']}#" if draft.get("id") else None
    here = lambda tab: link + tab if link else ""
    papers = _dicts(draft, "papers")
    out = []
    if sched:
        dates = " to ".join(x for x in (_days.nice(draft.get("start")), _days.nice(draft.get("end"))) if x)
        out.append(_line("what", "Exam, levels, dates", "done", ", ".join(x for x in (draft.get("name"), dates) if x), here("when")))
    else:
        out.append(_line("what", "Exam, levels, dates", "todo", "There is no draft yet.", ""))
    n_days = len(_dict(draft, "days"))
    out.append(_line("days", "Each day", "done" if n_days else "todo",
                     _plural(n_days, "day set", "days set") if n_days else "Every school day, all day, until days are set.", here("when")))
    run = _run(draft, pub, cal, xset) if sched else None
    if not draft.get("papers"):
        state, text = "todo", "No papers yet."
    elif run["unchecked"] or run["errors"]:
        state = "check"
        text = _plural(len(papers), "paper", "papers") + (f", {len(run['errors'])} to check" if run["errors"] else "")
        text += f". {run['unchecked']}" if run["unchecked"] else ""
    else:
        state, text = "done", _plural(len(papers), "paper", "papers")
    out.append(_line("papers", "Papers and times", state, text, here("papers")))
    sug = draft.get("suggested") if isinstance(draft.get("suggested"), list) else []
    if sug:
        state, text = "check", f"{_plural(len(sug), 'time', 'times')} to look at"
    elif papers and all(p.get("date") and p.get("start") for p in papers):
        state, text = "done", "Every paper has a time."
    else:
        state, text = "todo", "None suggested."
    out.append(_line("suggested", "Suggested times", state, text, here("papers")))
    t = _dict(draft, "times")
    if not sched:
        state, text = "todo", "Not set."
    elif t == OWN_TIMES and last and last.get("times") != t:
        state, text = "last", "As last time: " + _times_text(last["times"])
    else:
        state, text = "done", _times_text(t)
    out.append(_line("times", "Report time and breaks", state, text, here("when")))
    saved = bool(xset.get("saved_at"))
    r = xset.get("rules") or {}
    state = "last" if saved else "todo"
    text = (f"{_plural(len(xset.get('chiefs') or []), 'chief', 'chiefs')}, {_plural(len(xset.get('backups') or []), 'backup', 'backups')}, "
            f"{len(xset.get('never') or [])} left out.") if saved else "Not set."
    out.append(_line("people", "Chiefs, backups, left out", state, text, SETTINGS))
    rooms = xset.get("rooms") or {}
    seats = sum(v.get("seats") or 0 for v in rooms.values() if isinstance(v, dict))
    out.append(_line("rooms", "Exam rooms and seats", "last" if rooms else "todo",
                     f"{_plural(len(rooms), 'room', 'rooms')}, {_plural(seats, 'seat', 'seats')}." if rooms else "No exam rooms set.", SETTINGS))
    out.append(_line("numbers", "Invigilators per room", state,
                     f"{r.get('per_classroom', 2)} per classroom, 1 for each {r.get('hall_per', 40)} students in a hall." if saved else "Not set.",
                     SETTINGS))
    mine = (draft.get("seating"), draft.get("supervision"), draft.get("scripts") or "")
    own = _dict(draft, "seating") == OWN_SEATING and mine[1] == _own_supervision(draft) and not mine[2]
    if not sched:
        state, text = "todo", "Not set."
    elif own and last and (last.get("seating"), last.get("supervision"), last.get("scripts") or "") != mine:
        state, text = "last", "As last time: " + _choices_text(last.get("seating"), last.get("supervision"), last.get("scripts"))
    else:
        state, text = "done", _choices_text(*mine)
    out.append(_line("choices", "Seating choices", state, text, here("venues")))
    out.append(_line("access", "Extra time, own room", "form", "Added in the form on the exam page.", here("access")))
    return out


# ---------------------------------------------------------------- what the AI is given
def school(pub, xset) -> dict:
    """the school: levels with their classes and counts, subjects per level, periods, timetable days, exam rooms and seats"""
    model = _model(pub)
    students = model.get("students") or []
    size = Counter(s.get("cls") for s in students)
    by_level = Counter(_papers._student_level(model, s) for s in students)
    levels = [dict(level=lv, students=by_level[lv], classes=[dict(name=c["name"], students=size[c["name"]]) for c in model.get("classes") or [] if c["level"] == lv])
              for lv in model.get("levels") or []]
    subjects = [dict(level=lv, subjects=sorted({l["subject"] for l in model.get("lessons") or [] if l.get("level") == lv}))
                for lv in model.get("levels") or []]
    periods = [dict(period=i + 1, start=_days.hhmm(a), end=_days.hhmm(b)) for i, (a, b) in enumerate(_days.bounds(model))] if model else []
    rooms = [dict(name=n, seats=v.get("seats"), hall=bool(v.get("hall"))) for n, v in ((xset or {}).get("rooms") or {}).items() if isinstance(v, dict)]
    return dict(levels=levels, subjects=subjects, periods=periods, days=list(model.get("days") or []), rooms=rooms, students=len(students))


def _count(paper, model):
    """how many students sit a paper, None when the app cannot tell"""
    try:
        return len(_papers.who_sits(paper, model))
    except ODD:
        return None


def overview(sched, pub, cal, xset) -> dict:
    """the exam as the AI sees it: its name, every date of it with the levels and window, its papers (who sits as a word and a
    count only), the subjects of its levels with no paper, and its choices. days and no_paper are None when they cannot be read"""
    model = _model(pub)
    suggested = set(x for x in (sched.get("suggested") if isinstance(sched.get("suggested"), list) else []) if isinstance(x, str))
    papers = [dict(id=p.get("id"), label=_papers.label(p), level=p.get("level"), subject=p.get("subject"), paper=p.get("paper") or "",
                   minutes=p.get("minutes"), date=p.get("date"), start=p.get("start"), who=p.get("who"), together=p.get("together") or "",
                   suggested=p.get("id") in suggested, count=_count(p, model))
              for p in _dicts(sched, "papers")]
    try:
        days = [dict(date=d["date"], nice=_days.nice(d["date"]), school_day=d["day"] is not None, levels=list(d["levels"]),
                     start=_days.hhmm(d["start"]), end=_days.hhmm(d["end"])) for d in _days.dates(sched, cal, model)]
    except ODD:
        days = None
    try:
        if not model:
            raise ValueError("no published timetable")
        no_paper = [dict(level=p["level"], subject=p["subject"]) for p in _papers.fill_from_subjects(sched, model)]
    except ODD:
        no_paper = None
    return dict(id=sched.get("id"), name=sched.get("name"), kind=sched.get("kind"), levels=list(sched.get("levels") or []),
                classes=list(sched.get("classes") or []), start=sched.get("start"), end=sched.get("end"), days=days, papers=papers,
                no_paper=no_paper, choices=dict(times=dict(_dict(sched, "times")), seating=dict(_dict(sched, "seating")),
                                                supervision=sched.get("supervision"), scripts=sched.get("scripts") or ""))

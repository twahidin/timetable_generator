"""What the planning chat may be shown about an exam. Pure functions: they read what they are given, change none of it and
write nothing. What they return goes (once names are replaced) to an AI outside the school, so it holds counts and
words about papers, days, levels and rooms, and never a student's name or id, extra time or an own room (access), seats
or duties (made, pins) or the log. A person's name is never a key of a result."""
import copy
from collections import Counter

from exams import days as _days
from exams import papers as _papers
from exams.schedules import NO_CALENDAR

NO_PUB = "Publish the timetable first: exams read the classes, students and lessons from it."
NO_STUDENTS = ("The published timetable has no students yet. Everything can be filled in, but clashes between papers cannot "
               "be checked, no time can be suggested and seats cannot be made until the students are added and the "
               "timetable is published again.")
NO_ROOMS = "No exam rooms are set yet. Seats cannot be made until the rooms and their seats are set in the exam settings."
UNCHECKED = "Clashes not checked: no students yet."
SETTINGS = "/exams/settings"
OWN_TIMES = dict(report="07:30", min_break=20, max_papers=2)          # what schedules.new sets
OWN_SEATING = dict(order="class", shared="levels", spacing="every", home_rooms=True)
SHARED = dict(levels="levels alternate", papers="papers alternate", blocks="one level per block")


def _model(pub) -> dict:
    return (pub or {}).get("model") or {}


def _rules(xset) -> dict:
    return (xset or {}).get("rules") or None


def _access(sched) -> dict:
    return {a["student"]: a for a in sched.get("access") or [] if isinstance(a, dict) and a.get("student")}


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
def _lines(sched, pub, cal, xset) -> tuple:
    """(errors, warnings, hidden) of the checks with every access arrangement removed; hidden: lines of the full check that
    are not among them (those that are there only because of extra time)"""
    model = _model(pub)
    if not model or not (cal or {}).get("terms") or not sched.get("start") or not sched.get("end"):
        return [], [], 0
    rules = _rules(xset)
    full = _papers.check(sched, model, cal, rules)
    bare = _papers.check(dict(sched, access=[]), model, cal, rules)
    left = Counter(full["errors"]) + Counter(full["warnings"])
    left.subtract(Counter(bare["errors"]) + Counter(bare["warnings"]))
    return bare["errors"], bare["warnings"], sum(n for n in left.values() if n > 0)


def checks(sched, pub, cal, xset) -> dict:
    errors, warnings, hidden = _lines(sched, pub, cal, xset)
    return dict(errors=list(errors), warnings=list(warnings), hidden=hidden,
                unchecked="" if _model(pub).get("students") else UNCHECKED)


# ---------------------------------------------------------------- times a paper could have
def _up5(m) -> int:
    return -(-m // 5) * 5


def _timed(p) -> bool:
    try:
        _days.minutes(p["start"])
        return bool(p.get("date")) and isinstance(p.get("minutes"), int)
    except (KeyError, TypeError, ValueError):
        return False


def _why(k) -> str:
    if not k:
        return "No student of this paper has another paper that day."
    return f"Its students have at most {k} other {'paper' if k == 1 else 'papers'} that day."


def slots(sched, pub, cal, xset, paper_id, limit=3) -> list:
    """up to `limit` times a paper with no time could have: [dict(date, start, why)], best first. Only school days of an exam
    day where its level sits, inside the day's window, with at most max_papers a day and at least min_break between papers
    for every student (extra time counted), and no two papers at once"""
    model = _model(pub)
    paper = next((p for p in sched.get("papers") or [] if p.get("id") == paper_id), None)
    if not model.get("students") or not paper or paper.get("date") or paper.get("start") or not isinstance(paper.get("minutes"), int):
        return []
    together = str(paper.get("together") or "").strip()
    others = [q for q in sched.get("papers") or [] if q is not paper and _timed(q)]
    if together and any(str(q.get("together") or "").strip() == together for q in others):
        return []
    times = sched.get("times") or {}
    min_break, max_papers = times.get("min_break", 20), times.get("max_papers", 2)
    access = _access(sched)
    mine = _papers.who_sits(paper, model)
    mine_set = set(mine)
    length = {sid: _papers.ends(dict(start="00:00", minutes=paper["minutes"]), sid, access) for sid in mine}
    busy, starts, ends = {}, {}, {}                                      # by date: {student: [(start, end)]}, [starts], {ends}
    for q in others:
        d, st = q["date"], _days.minutes(q["start"])
        starts.setdefault(d, set()).add(st)
        ends.setdefault(d, set()).add(st + q["minutes"])
        for sid in mine_set.intersection(_papers.who_sits(q, model)):
            e = _papers.ends(q, sid, access)
            busy.setdefault(d, {}).setdefault(sid, []).append((st, e))
            ends[d].add(e)
    try:
        exam_days = _days.dates(sched, cal, model)
    except (KeyError, TypeError, ValueError):
        return []
    found = []
    for e in exam_days:
        if e["day"] is None or (paper.get("who") in ("level", "groups") and paper.get("level") not in e["levels"]):
            continue
        d = e["date"]
        cand = {e["start"]} | starts.get(d, set()) | {_up5(x + min_break) for x in ends.get(d, ())}
        for st in cand:
            if st < e["start"] or st + paper["minutes"] > e["end"]:
                continue
            most, ok = 0, True
            for sid in mine:
                ivs = busy.get(d, {}).get(sid, ())
                end = st + length[sid]
                if len(ivs) + 1 > max_papers or any((st < b and a < end) or 0 <= a - end < min_break or 0 <= st - b < min_break for a, b in ivs):
                    ok = False
                    break
                most = max(most, len(ivs))
            if ok:
                found.append((most, d, st))
    found.sort()
    return [dict(date=d, start=_days.hhmm(st), why=_why(k)) for k, d, st in found[:limit]]


# ---------------------------------------------------------------- earlier exams
def last_values(sched, all_saved) -> dict | None:
    """the values of the newest earlier exam of the same kind that the checklist can offer again, or None"""
    kind = (sched or {}).get("kind") or "exam"
    if kind not in ("exam", "test"):
        return None
    mine = (sched or {}).get("id")
    earlier = [s for s in all_saved or [] if isinstance(s, dict) and s.get("kind") == kind and s.get("id") and s["id"] != mine]
    if not earlier:
        return None
    s = max(earlier, key=lambda x: x.get("created_at") or "")
    return dict(id=s["id"], name=s.get("name") or "", **copy.deepcopy({k: s.get(k) for k in ("times", "seating", "supervision", "scripts")}))


# ---------------------------------------------------------------- the checklist
def _line(key, title, state, text, link):
    return dict(key=key, title=title, state=state, text=text, link=link)


def _plural(n, one, many) -> str:
    return f"{n} {one if n == 1 else many}"


def checklist(sched, pub, cal, xset, last) -> list:
    """the lines of "Filled in so far": [dict(key, title, state, text, link)], in the order of the exam page's form"""
    xset = xset or {}
    url = f"/exams/{sched['id']}#" if sched else ""
    here = lambda tab: url + tab if sched else ""
    papers = (sched or {}).get("papers") or []
    out = []
    if sched:
        text = ", ".join(x for x in (sched.get("name"), _days.nice(sched.get("start")) + " to " + _days.nice(sched.get("end"))) if x)
        out.append(_line("what", "Exam, levels, dates", "done", text, here("when")))
    else:
        out.append(_line("what", "Exam, levels, dates", "todo", "There is no draft yet.", ""))
    n_days = len((sched or {}).get("days") or {})
    out.append(_line("days", "Each day", "done" if n_days else "todo",
                     _plural(n_days, "day set", "days set") if n_days else "Every school day, all day, until days are set.", here("when")))
    errors = _lines(sched, pub, cal, xset)[0] if sched else []
    if not papers:
        state, text = "todo", "No papers yet."
    else:
        state, text = ("check", f"{len(papers)}, {len(errors)} to check") if errors else ("done", str(len(papers)))
    out.append(_line("papers", "Papers and times", state, text, here("papers")))
    sug = (sched or {}).get("suggested") or []
    if sug:
        state, text = "check", f"{_plural(len(sug), 'time', 'times')} to look at"
    elif papers and all(p.get("date") and p.get("start") for p in papers):
        state, text = "done", "Every paper has a time."
    else:
        state, text = "todo", "None suggested."
    out.append(_line("suggested", "Suggested times", state, text, here("papers")))
    t = (sched or {}).get("times") or {}
    own_t = bool(sched) and t == OWN_TIMES and not (sched.get("scripts") or "") and sched.get("supervision") == (
        "lesson" if sched.get("kind") == "test" else "invigilators")
    differs = bool(last and sched) and (last.get("times") != t or last.get("supervision") != sched.get("supervision")
                                         or (last.get("scripts") or "") != (sched.get("scripts") or ""))
    state = "last" if own_t and differs else ("done" if sched else "todo")
    text = (f"Report {t.get('report') or 'not set'}, {t.get('min_break', 20)} minutes between papers, "
            f"{t.get('max_papers', 2)} a day at most.") if sched else "Not set."
    out.append(_line("times", "Report time and breaks", state, text, here("when")))
    saved = bool(xset.get("saved_at"))
    r = xset.get("rules") or {}
    state = "last" if saved else "todo"
    text = (f"{len(xset.get('chiefs') or [])} chiefs, {len(xset.get('backups') or [])} backups, "
            f"{len(xset.get('never') or [])} left out.") if saved else "Not set."
    out.append(_line("people", "Chiefs, backups, left out", state, text, SETTINGS))
    rooms = xset.get("rooms") or {}
    seats = sum(v.get("seats") or 0 for v in rooms.values() if isinstance(v, dict))
    out.append(_line("rooms", "Exam rooms and seats", "last" if rooms else "todo",
                     f"{_plural(len(rooms), 'room', 'rooms')}, {_plural(seats, 'seat', 'seats')}." if rooms else "No exam rooms set.", SETTINGS))
    out.append(_line("numbers", "Invigilators per room", state,
                     f"{r.get('per_classroom', 2)} per classroom, 1 for each {r.get('hall_per', 40)} students in a hall." if saved else "Not set.",
                     SETTINGS))
    s = (sched or {}).get("seating") or {}
    own_s = bool(sched) and s == OWN_SEATING
    state = "last" if own_s and last and last.get("seating") != s else ("done" if sched else "todo")
    text = (f"By {s.get('order', 'class')}, {SHARED.get(s.get('shared'), 'levels alternate')}, "
            f"{'own class in own home room' if s.get('home_rooms', True) else 'classes mixed'}.") if sched else "Not set."
    out.append(_line("choices", "Seating choices", state, text, here("venues")))
    out.append(_line("access", "Extra time, own room", "form", "Added in the form on the exam page.", here("access")))
    return out


# ---------------------------------------------------------------- what the AI is given
def _level_of(model, s) -> str:
    return s.get("level") or next((c["level"] for c in model.get("classes") or [] if c["name"] == s.get("cls")), "")


def school(pub, cal, xset=None) -> dict:
    """the school: levels with their classes and counts, subjects per level, periods, timetable days, exam rooms and seats"""
    model = _model(pub)
    size = Counter(s.get("cls") for s in model.get("students") or [])
    levels = [dict(level=lv, students=sum(1 for s in model.get("students") or [] if _level_of(model, s) == lv),
                   classes=[dict(name=c["name"], students=size[c["name"]]) for c in model.get("classes") or [] if c["level"] == lv])
              for lv in model.get("levels") or []]
    subjects = [dict(level=lv, subjects=sorted({l["subject"] for l in model.get("lessons") or [] if l.get("level") == lv}))
                for lv in model.get("levels") or []]
    periods = [dict(period=i + 1, start=_days.hhmm(a), end=_days.hhmm(b)) for i, (a, b) in enumerate(_days.bounds(model))] if model else []
    rooms = [dict(name=n, seats=v.get("seats"), hall=bool(v.get("hall"))) for n, v in ((xset or {}).get("rooms") or {}).items() if isinstance(v, dict)]
    return dict(levels=levels, subjects=subjects, periods=periods, days=list(model.get("days") or []), rooms=rooms,
                students=len(model.get("students") or []))


def overview(sched, pub, cal, xset) -> dict:
    """the exam as the AI sees it: its name, dates, days, papers (who sits as a word and a count only), the subjects of its
    levels with no paper, and its choices"""
    model = _model(pub)
    suggested = set(sched.get("suggested") or [])
    papers = [dict(id=p["id"], label=_papers.label(p), level=p.get("level"), subject=p.get("subject"), paper=p.get("paper") or "",
                   minutes=p.get("minutes"), date=p.get("date"), start=p.get("start"), who=p.get("who"), together=p.get("together") or "",
                   suggested=p["id"] in suggested, count=len(_papers.who_sits(p, model)))
              for p in sched.get("papers") or []]
    levels = _days.levels_of(sched, model) if model else list(sched.get("levels") or [])
    have = {(p["level"], p["subject"]) for p in papers}
    no_paper = [dict(level=lv, subject=sb) for lv, sb in sorted({(l["level"], l["subject"]) for l in model.get("lessons") or []
                                                                  if l.get("level") in levels}) if (lv, sb) not in have]
    days = [dict(date=d, nice=_days.nice(d), levels=list(e.get("levels") or []), whole=e.get("whole", True),
                 start=e.get("from") if not e.get("whole", True) else None, end=e.get("to") if not e.get("whole", True) else None)
            for d, e in sorted((sched.get("days") or {}).items())]
    return dict(id=sched["id"], name=sched.get("name"), kind=sched.get("kind"), levels=list(sched.get("levels") or []),
                classes=list(sched.get("classes") or []), start=sched.get("start"), end=sched.get("end"), days=days, papers=papers,
                no_paper=no_paper, choices=dict(times=dict(sched.get("times") or {}), seating=dict(sched.get("seating") or {}),
                                                supervision=sched.get("supervision"), scripts=sched.get("scripts") or ""))

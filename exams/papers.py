"""Papers of an exam schedule."""


def label(paper) -> str:
    """a paper's name in messages: level, subject and paper, leaving out the paper part when it is empty"""
    return " ".join(str(paper.get(k) or "").strip() for k in ("level", "subject", "paper") if str(paper.get(k) or "").strip())


import datetime
import io
import math
import secrets

from exams import days as _days
from relief.calendar import school_day

HEADER = ["Level", "Subject", "Paper", "Minutes", "Date", "Start", "Who sits", "Sits with"]
BAD_HEADER = "The first row must be: Level, Subject, Paper, Minutes, Date, Start, Who sits, Sits with."


def _student_level(model, s):
    if s.get("level"):
        return s["level"]
    return next((c["level"] for c in model.get("classes") or [] if c["name"] == s.get("cls")), None)


def who_sits(paper, model) -> list:
    """student ids (sorted) who sit the paper, from the published model"""
    students = model.get("students") or []
    who = paper.get("who")
    if who == "level":
        return sorted(s["id"] for s in students if _student_level(model, s) == paper.get("level"))
    if who == "students":
        have = {s["id"] for s in students}
        return sorted({i for i in paper.get("students") or [] if i in have})
    out = set()
    sit = {s["id"]: s for s in students if _student_level(model, s) == paper.get("level")}
    students = list(sit.values())
    for l in model.get("lessons") or []:
        if l.get("level") != paper.get("level") or l.get("subject") != paper.get("subject"):
            continue
        if l.get("group") == "Entire Class":
            out.update(s["id"] for s in students if s.get("cls") in l.get("classes", []))
        else:
            out.update(s["id"] for s in students if l.get("group") in (s.get("groups") or []))
    return sorted(out)


def fill_from_subjects(sched, model) -> list:
    """new papers: one per (level, subject) of the published lessons at the schedule's levels, none already there"""
    have = {(p.get("level"), p.get("subject")) for p in sched.get("papers") or []}
    want = sorted({(l["level"], l["subject"]) for l in model.get("lessons") or [] if l.get("level") in (sched.get("levels") or [])})
    return [dict(id=secrets.token_hex(4), level=lv, subject=sb, paper="Paper 1", minutes=60, date=None, start=None,
                 who="groups", students=[], together="") for lv, sb in want if (lv, sb) not in have]


def _cell(v):
    return "" if v is None else str(v).strip()


def read_paper_list(data: bytes) -> list:
    import openpyxl
    try:
        ws = openpyxl.load_workbook(io.BytesIO(data), data_only=True).worksheets[0]
    except Exception:
        raise ValueError(BAD_HEADER)
    rows = list(ws.iter_rows(values_only=True))
    if not rows or [_cell(v) for v in rows[0][:8]] != HEADER:
        raise ValueError(BAD_HEADER)
    out = []
    for n, row in enumerate(rows[1:], start=2):
        row = list(row) + [None] * (8 - len(row))
        if all(_cell(v) == "" for v in row[:8]):
            continue
        level, subject, paper = _cell(row[0]), _cell(row[1]), _cell(row[2])
        if not level or not subject:
            raise ValueError(f"Row {n}: give a level and a subject.")
        m = row[3]
        if isinstance(m, str):
            m = m.strip()
            m = int(m) if m.isdigit() else None
        elif isinstance(m, float) and m == int(m):
            m = int(m)
        if not isinstance(m, int) or isinstance(m, bool) or m < 1:
            raise ValueError(f"Row {n}: the minutes must be a whole number.")
        d = row[4]
        if isinstance(d, datetime.datetime):
            d = d.date().isoformat()
        elif isinstance(d, datetime.date):
            d = d.isoformat()
        elif _cell(d) == "":
            d = None
        else:
            try:
                d = datetime.date.fromisoformat(_cell(d)).isoformat()
            except ValueError:
                raise ValueError(f"Row {n}: the date is not a date.")
        st = row[5]
        if isinstance(st, datetime.datetime):
            st = st.time()
        if isinstance(st, datetime.time):
            st = "%02d:%02d" % (st.hour, st.minute)
        elif _cell(st) == "":
            st = None
        else:
            try:
                st = _days.hhmm(_days.minutes(_cell(st)))
            except ValueError:
                raise ValueError(f"Row {n}: the start is not a time.")
        who = "level" if _cell(row[6]).lower() == "all" else "groups"
        out.append(dict(id=secrets.token_hex(4), level=level, subject=subject, paper=paper, minutes=m, date=d, start=st,
                        who=who, students=[], together=_cell(row[7])))
    return out


def paper_list_xlsx(sched) -> bytes:
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Papers"
    ws.append(HEADER)
    for p in sched.get("papers") or []:
        if p.get("who") == "students":
            continue
        ws.append([p.get("level"), p.get("subject"), p.get("paper") or None, p.get("minutes"), p.get("date"), p.get("start"),
                   "All" if p.get("who") == "level" else "Groups", p.get("together") or None])
    b = io.BytesIO()
    wb.save(b)
    return b.getvalue()


def ends(paper, sid, access_by_sid) -> int:
    """minute the student finishes: start plus minutes plus the student's extra time, rounded up"""
    a = (access_by_sid or {}).get(sid) or {}
    extra = a.get("extra") or 0
    return _days.minutes(paper["start"]) + math.ceil(round(paper["minutes"] * (1 + extra / 100), 6))


def _students(n, one, many):
    """'1 student has' / '3 students have': the number once, the noun and verb by number"""
    return f"1 student {one}" if n == 1 else f"{n} students {many}"


def check(sched, model, cal, rules=None) -> dict:
    """errors and warnings on the paper times; rules: the exams settings' rules (arrive, stay), the defaults when None"""
    if rules is None:
        from exams import settings as _settings
        rules = _settings.defaults()["rules"]
    arrive, stay = rules.get("arrive") or 0, rules.get("stay") or 0
    errors, warnings = [], []
    dts = {d["date"]: d for d in _days.dates(sched, cal, model)}
    bnds = _days.bounds(model)
    day0, day1 = (bnds[0][0], bnds[-1][1]) if bnds else (0, 24 * 60)
    access = {a["student"]: a for a in sched.get("access") or [] if isinstance(a, dict) and a.get("student")}
    times = sched.get("times") or {}
    min_break, max_papers = times.get("min_break", 20), times.get("max_papers", 2)
    ok, edges = [], []
    for p in sched.get("papers") or []:
        lb = label(p)
        try:
            day = datetime.date.fromisoformat(p["date"])
            st = _days.minutes(p["start"])
        except (KeyError, TypeError, ValueError):
            errors.append(f"{lb} needs a date and a start time.")
            continue
        if school_day(cal, model["days"], day) is None:
            errors.append(f"{lb} is on {p['date']}, which is not a school day.")
            continue
        if p.get("who") in ("level", "groups"):
            e = dts.get(p["date"])
            if e is None or p.get("level") not in e["levels"]:
                errors.append(f"{lb} is on {p['date']}, which is not one of {p.get('level')}'s exam days.")
                continue
            if st < e["start"] or st + p["minutes"] > e["end"]:
                errors.append(f"{lb} runs outside {p.get('level')}'s exam time on {p['date']} "
                              f"({_days.hhmm(e['start'])}–{_days.hhmm(e['end'])}).")
            else:
                if e["start"] > day0 and st - e["start"] < arrive:
                    warnings.append(f"{lb} starts at {_days.hhmm(st)}, less than {arrive} minutes after the exam time begins: "
                                    f"rooms of lessons just before may be busy.")
                if e["end"] < day1 and e["end"] - (st + p["minutes"]) < stay:
                    warnings.append(f"{lb} ends at {_days.hhmm(st + p['minutes'])}, less than {stay} minutes before the exam time "
                                    f"ends: rooms of lessons just after may be busy.")
                if e["end"] < day1:
                    edges.append((p, e["end"]))
        ok.append(p)
    groups = {}
    for p in sched.get("papers") or []:
        if str(p.get("together") or "").strip() and p.get("date") and p.get("start"):
            groups.setdefault(p["together"].strip(), []).append(p)
    for name, ps in groups.items():
        for q in ps[1:]:
            if (q["date"], q["start"]) != (ps[0]["date"], ps[0]["start"]):
                errors.append(f"{label(ps[0])} and {label(q)} share “{name}” but start at different times.")
    sits = {id(p): set(who_sits(p, model)) for p in ok}
    for p, end in edges:
        late = sum(1 for sid in sits[id(p)] if sid in access and ends(p, sid, access) > end)
        if late:
            warnings.append(f"{_students(late, 'with extra time finishes', 'with extra time finish')} {label(p)} after the exam time "
                            f"ends on {p['date']}.")
    for date in sorted({p["date"] for p in ok}):
        ps = sorted((p for p in ok if p["date"] == date), key=lambda p: _days.minutes(p["start"]))
        count = {}
        for p in ps:
            for sid in sits[id(p)]:
                count[sid] = count.get(sid, 0) + 1
        by_k = {}
        for sid, k in count.items():
            if k > max_papers:
                by_k.setdefault(k, []).append(sid)
        for k in sorted(by_k):
            n = len(by_k[k])
            warnings.append(f"{_students(n, 'has', 'have')} {k} papers on {date}.")
        for i, a in enumerate(ps):
            for b in ps[i + 1:]:
                sa, sb = _days.minutes(a["start"]), _days.minutes(b["start"])
                clash, close = 0, 0
                for sid in sits[id(a)] & sits[id(b)]:
                    ea, eb = ends(a, sid, access), ends(b, sid, access)
                    if sa < eb and sb < ea:
                        clash += 1
                    elif 0 <= sb - ea < min_break:
                        close += 1
                if clash:
                    errors.append(f"{_students(clash, 'has', 'have')} {label(a)} and {label(b)} "
                                  f"at the same time on {date}.")
                if close:
                    warnings.append(f"{_students(close, 'has', 'have')} less than {min_break} minutes "
                                    f"between {label(a)} and {label(b)} on {date}.")
    pub = dict(model=model)
    for date, e in dts.items():
        if e["day"] is None:
            continue
        n = _days.edge_cuts(_days.day_view(pub, cal, sched, date))
        if n:
            warnings.append(f"On {date} the exam time ends in the middle of {n} {'lesson' if n == 1 else 'lessons'}.")
    return dict(errors=errors, warnings=warnings)

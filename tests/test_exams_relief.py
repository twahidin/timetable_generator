"""Plain-assert tests for what approved exams and events mean for relief: .venv/bin/python tests/test_exams_relief.py"""
import os, secrets, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = tempfile.mkdtemp()
os.environ.pop("HEADS_CODE", None)
os.environ.update(DATA_DIR=DATA, SECRET_KEY=secrets.token_hex(16), AI_PROVIDER="anthropic", AI_API_KEY="",
                  COMMITTEE_CODE=secrets.token_hex(4), TEACHER_CODE=secrets.token_hex(4), STUDENT_CODE=secrets.token_hex(4))
sys.path.insert(0, ROOT)
import app as A, store  # noqa: E402
from exams import fake as F, days as D, schedules as SC, approval as AP  # noqa: E402
from exams import relief_links as RL  # noqa: E402
from relief import lessons as LS  # noqa: E402
from datetime import date  # noqa: E402

def raises(exc, f, text=None):
    try: f()
    except exc as e:
        if text is not None: assert str(e) == text, str(e)
        return
    raise AssertionError("did not raise")

COUNT = 0
def t(f):
    global COUNT
    f(); COUNT += 1
    return f

CAL = dict(terms=[dict(name="Term 1", start="2027-01-04", end="2027-03-12", starts_as="Odd")], holidays=[])
MON = date(2027, 1, 4)          # Odd Mon
ISO = MON.isoformat()
PUB = F.sample_pub()
M = PUB["model"]
EXAM, EVENT = "Sec 3 End-of-Year Exam", "Sec 4 Learning Journey"
AISHA, BEN = "Ms Aisha Rahman", "Mr Ben Ong"

def _approve(s, status="approved"):
    s["status"] = status
    s["approved"] = AP.public(s) if status == "approved" else None
    return SC.save(s, PUB, CAL, "x", check=False)

def _exam(status="approved", duty_names=(AISHA,)):
    e = SC.new("exam", EXAM, ["Sec 3"], ISO, ISO, "Ms Grace Yeo", pub=PUB)
    e["days"] = {ISO: dict(levels=["Sec 3"], whole=True)}
    e["made"] = dict(seats=[], unseated=[], published_at=None,
                     duties=[dict(date=ISO, start=460, end=550, room="3-01", names=list(duty_names))])
    return _approve(e, status)

def _event(status="approved"):
    e = SC.new_event(EVENT, ["Sec 4"], [], ISO, ISO, "Ms Grace Yeo", "Ms Grace Yeo")
    e["days"] = {ISO: dict(levels=["Sec 4"], whole=False, **{"from": "07:40", "to": "09:00"})}
    e["going"] = [BEN]
    return _approve(e, status)

def _clear():
    for s in SC.all_saved(): SC.delete(s["id"])

def _links():
    return RL.Links(PUB, CAL, SC.on_site())

def _lesson(row, d=MON):
    L = M["lessons"][row]
    return dict(key=RL.key_of(M, row, d, "Odd Mon"), date=d, classes=L["classes"])

@t
def key_matches_relief():
    got = LS.on_date(PUB, CAL, AISHA, MON)[0]
    assert RL.key_of(M, 0, MON, "Odd Mon") == got["key"] == RL.key_of(M, 0, ISO, "Odd Mon")

@t
def links_stopped_names_the_schedule():
    _clear(); _exam(); _event()
    L = _links()
    assert L.stopped(_lesson(0)) == "3A is on " + EXAM
    assert L.stopped(_lesson(0)) == "3A is on " + EXAM
    assert L.stopped(dict(_lesson(0), date=ISO)) == "3A is on " + EXAM
    assert L.stopped(_lesson(3)) == "3A, 3B are on " + EXAM
    assert L.stopped(_lesson(8)) == "", "a mixed lesson with a Sec 4 class still runs"

@t
def links_event_window_stops_only_inside():
    _clear(); _event()
    L = _links()
    assert L.stopped(_lesson(2)) == "4A is on " + EVENT, "period 1-2 (07:40..08:20) inside 07:40-09:00"
    assert L.stopped(_lesson(6)) == "", "period 9 is outside the event window"

@t
def links_shortened_lesson_still_happens():
    _clear(); _event()
    M["lessons"][2]["n"] = 8        # 07:40+20..: periods 1..8 run past 09:00
    try:
        assert _links().stopped(_lesson(2)) == ""
    finally:
        M["lessons"][2]["n"] = 2

@t
def links_busy_and_duties():
    _clear(); _exam(); _event()
    L = _links()
    assert L.busy(AISHA, MON, 0, 1) == "Invigilating: " + EXAM
    assert L.busy(AISHA, ISO, 3, 2) == "Invigilating: " + EXAM
    assert L.busy(AISHA, MON, 8, 1) == ""
    assert L.busy(BEN, MON, 0, 1) == "At event: " + EVENT
    assert L.busy(BEN, MON, 10, 1) == ""
    assert L.busy("Mr Nobody", MON, 0, 1) == ""
    d = L.duties(AISHA, MON)
    assert d == [dict(start="07:40", end="09:10", what="Invigilating: %s · 3-01" % EXAM, replaces="the exams committee")], d
    d = L.duties(BEN, MON)
    assert d[0]["start"] == "07:40" and d[0]["end"] == "09:00" and d[0]["what"] == "At event: " + EVENT
    assert d[0]["replaces"] == "Ms Grace Yeo, the teacher in charge"
    assert L.duties(AISHA, MON, periods=(10, 12)) == []
    assert len(L.duties(AISHA, MON, periods=(0, 0))) == 1

@t
def links_only_approved():
    _clear(); _exam("waiting"); _event("waiting")
    L = _links()
    assert L.stopped(_lesson(0)) == "" and L.busy(AISHA, MON, 0, 1) == "" and L.busy(BEN, MON, 0, 1) == ""
    assert L.duties(AISHA, MON) == [] and L.week_change(AISHA, [MON]) == 0

@t
def links_week_change():
    _clear(); _exam(duty_names=(BEN,))
    L = _links()
    # Ben: duty 07:40-09:10 touches periods 0..4 (5); his only lesson is period 6..8 (Sec 3, stops: -3)
    assert L.week_change(BEN, [MON]) == 5 - 3
    # Grace teaches 3A+3B period 6..8 (stops, -3) and 4A at period 9..10 (runs)
    assert L.week_change("Ms Grace Yeo", [MON]) == -3 + 0
    assert L.week_change("Mr Nobody", [MON]) == 0
    _clear(); _exam(duty_names=("Mr Daniel Koh",))
    L = _links()
    # Daniel: duty periods 0..4; his 4A lesson at periods 1-2 runs: only periods 0, 3 and 4 are added
    assert L.week_change("Mr Daniel Koh", [MON]) == 3
    _clear(); _exam(duty_names=(AISHA,))
    assert _links().week_change(AISHA, [MON]) == 5 - 2, "her 3A lesson at 0..1 stops (-2); duty periods 0..4 (+5)"

@t
def links_week_change_duty_where_nothing_is_taught():
    _clear(); e = _exam(duty_names=("Mr Ivan Lee",))
    e["made"]["duties"][0].update(start=480, end=520)
    _approve(e)
    assert _links().week_change("Mr Ivan Lee", [MON]) == 2

@t
def links_never_raise():
    _clear(); _exam(); _event()
    L = _links()
    sat = date(2027, 1, 9)
    assert L.stopped(dict(_lesson(0), date=sat)) == "" and L.busy(AISHA, sat, 0, 1) == ""
    assert L.duties(AISHA, sat) == [] and L.week_change(AISHA, [sat]) == 0
    blank = RL.Links(PUB, dict(terms=[], holidays=[]), SC.on_site())
    assert blank.stopped(_lesson(0)) == "" and blank.busy(AISHA, MON, 0, 1) == "" and blank.duties(AISHA, MON) == []
    assert blank.week_change(AISHA, [MON]) == 0
    nop = dict(PUB, model=dict(M, NP=0, times=[], school={}))
    q = RL.Links(nop, CAL, SC.on_site())
    assert q.stopped(_lesson(0)) == "" and q.busy(AISHA, MON, 0, 1) == "" and q.duties(AISHA, MON) == [] and q.week_change(AISHA, [MON]) == 0
    n = RL.Links.load(None, CAL)
    assert n.stopped(_lesson(0)) == "" and n.busy(AISHA, MON, 0, 1) == "" and n.duties(AISHA, MON) == [] and n.week_change(AISHA, [MON]) == 0
    assert RL.Links.load(PUB, CAL).busy(AISHA, MON, 0, 1) == "Invigilating: " + EXAM

@t
def links_two_schedules_one_day():
    _clear(); _exam(); _event()
    PUB["model"]["lessons"].append(F._lesson(10, 0, 2, 1, "Sec 4", ["4A"], "Maths", "Entire Class", [AISHA], "4-01"))
    try:
        L = _links()
        lesson = dict(key=RL.key_of(M, 10, MON, "Odd Mon"), date=MON, classes=["4A"])
        assert L.busy(AISHA, MON, 2, 1) == "Invigilating: " + EXAM
        assert L.stopped(lesson) == "4A is on " + EVENT, "the lesson does not run: the event holds 4A"
        both = dict(key=RL.key_of(M, 3, MON, "Odd Mon"), date=MON, classes=["3A", "3B"])
        assert L.stopped(both) == "3A, 3B are on " + EXAM
    finally:
        PUB["model"]["lessons"].pop()

_clear()
print(f"{COUNT} exams and relief tests passed")

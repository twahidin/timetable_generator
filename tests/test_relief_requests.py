"""Plain-assert tests for relief requests: .venv/bin/python tests/test_relief_requests.py"""
import os, secrets, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = tempfile.mkdtemp()
os.environ.pop("HEADS_CODE", None)
os.environ.update(DATA_DIR=DATA, SECRET_KEY=secrets.token_hex(16), AI_PROVIDER="anthropic", AI_API_KEY="", COMMITTEE_CODE=secrets.token_hex(4), TEACHER_CODE=secrets.token_hex(4), STUDENT_CODE=secrets.token_hex(4))
os.environ.pop("SCHOOL_TZ", None)
sys.path.insert(0, ROOT)
import app as A, store  # noqa: E402
from relief import people as P  # noqa: E402
from relief import lessons as LS  # noqa: E402
from ttgen.spec import day_names  # noqa: E402
import datetime  # noqa: E402
from zoneinfo import ZoneInfo  # noqa: E402

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

CAL = dict(terms=[dict(name="Term 4", start="2026-09-07", end="2026-11-20", starts_as="Odd")],
           holidays=[dict(start="2026-10-23", end="2026-10-23", name="Deepavali")])
D = datetime.date
DAYS = day_names(2)
EVE, DAR = "Ms Evelyn Koh", "Mr Darren Lim"
TUE = [d for d in DAYS if d.startswith("Even") and d.split()[-1].startswith("Tue")][0]
FRI = [d for d in DAYS if d.startswith("Even") and d.split()[-1].startswith("Fri")][0]

def L(day, p, n, classes, subject, teachers, group="", room="R1"):
    return dict(d=DAYS.index(day), p=p, n=n, classes=classes, subject=subject, group=group, teachers=teachers, room=room, level="Sec 1")

def make(lessons):
    pub = P.fake_pub([dict(name=EVE), dict(name=DAR)], lessons)
    pub["model"]["school"].update(start_time="08:00", period_minutes=30)
    pub["model"]["NP"] = 12
    return pub

LESSONS = [L(TUE, 5, 2, ["1B", "1A"], "Maths", [EVE, DAR], "G1"), L(TUE, 0, 1, ["1A"], "Art", [EVE]),
           L(TUE, 9, 1, ["2A"], "Music", [EVE]), L(TUE, 1, 1, ["3A"], "PE", [DAR]),
           L(FRI, 0, 2, ["1A"], "Art", [EVE]), L(FRI, 3, 1, ["1A"], "Art", [EVE])]
PUB = make(LESSONS)
DATE = D(2026, 10, 13)

@t
def lessons_on_a_school_day():
    got = LS.on_date(PUB, CAL, EVE, DATE)
    assert [x["p"] for x in got] == [0, 5, 9], got
    a, b, c = got
    assert a["key"] == f"2026-10-13/{TUE}/0/1/1A/Art/", a["key"]
    assert (a["start"], a["end"]) == ("08:00", "08:30"), a
    assert b["classes"] == ["1B", "1A"] and b["n"] == 2 and (b["start"], b["end"]) == ("10:30", "11:30"), b
    assert b["key"] == f"2026-10-13/{TUE}/5/2/1A+1B/Maths/G1", b["key"]
    assert b["others"] == [DAR] and a["others"] == [], (a, b)
    assert b["date"] == DATE and b["day"] == TUE and b["subject"] == "Maths" and b["room"] == "R1" and b["level"] == "Sec 1"

@t
def some_periods_only():
    got = LS.on_date(PUB, CAL, EVE, DATE, periods=(3, 8))
    assert [x["p"] for x in got] == [5], got
    got = LS.on_date(PUB, CAL, EVE, DATE, periods=(6, 6))
    assert [x["p"] for x in got] == [5], got
    assert LS.on_date(PUB, CAL, EVE, DATE, periods=(7, 8)) == []

@t
def not_a_school_day_and_no_calendar():
    raises(ValueError, lambda: LS.on_date(PUB, CAL, EVE, D(2026, 10, 17)), "Sat 17 Oct is not a school day in the calendar.")
    raises(ValueError, lambda: LS.on_date(PUB, dict(terms=[], holidays=[]), EVE, DATE), LS.NO_CALENDAR)
    assert LS.NO_CALENDAR == "Set the school calendar in Relief settings first: relief needs it to know which timetable day a date is."

@t
def a_changed_lesson_is_noticed():
    stored = LS.on_date(PUB, CAL, EVE, DATE)[1]
    assert LS.still_there(PUB, CAL, EVE, stored)
    moved = make([L(TUE, 6, 2, ["1B", "1A"], "Maths", [EVE, DAR], "G1")])
    assert not LS.still_there(moved, CAL, EVE, stored)

@t
def teaching_periods_count_the_school_week():
    assert LS.teaching_periods(PUB, CAL, EVE, DATE) == 1 + 2 + 1 + 2 + 1
    cal = dict(CAL, holidays=[dict(start="2026-10-16", end="2026-10-16", name="x")])
    assert LS.teaching_periods(PUB, cal, EVE, DATE) == 4
    assert LS.teaching_periods(PUB, CAL, DAR, DATE) == 2 + 1

@t
def today_is_the_schools_date():
    assert LS.today() == datetime.datetime.now(ZoneInfo("Asia/Singapore")).date()

print(f"{COUNT} relief request tests passed")

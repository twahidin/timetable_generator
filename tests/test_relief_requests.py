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



@t
def still_there_takes_an_iso_date_string():
    stored = dict(LS.on_date(PUB, CAL, EVE, DATE)[1])
    stored["date"] = "2026-10-13"
    assert LS.still_there(PUB, CAL, EVE, stored)
    moved = make([L(TUE, 6, 2, ["1B", "1A"], "Maths", [EVE, DAR], "G1")])
    assert not LS.still_there(moved, CAL, EVE, stored)

@t
def teaching_periods_is_zero_without_terms():
    assert LS.teaching_periods(PUB, dict(terms=[], holidays=[]), EVE, DATE) == 0

# ---- Task 2: load and the "free then" list ----
from relief import free as FR  # noqa: E402

FAT = "Flexi Adjunct Teacher"
SAM, RUTH, MAYA, PETE, FLEX = "Mr Sam Tan", "Ms Ruth Goh", "Ms Maya Lee", "Mr Pete Ong", "Mr Flex Ng"
BUSY, NEVER, ABS, PART, TAKEN, GONE = "Mr Busy Chan", "Mr Never Yap", "Ms Abs Sen", "Mr Part Ho", "Ms Rel Ed", "Mr Gone Lee"
D12, D13, D14 = D(2026, 10, 12), D(2026, 10, 13), D(2026, 10, 14)

def people_rows():
    return [dict(name=EVE, dept="Science"), dict(name=SAM, dept="Science"), dict(name=RUTH, dept="Science"), dict(name=TAKEN, dept="Science"),
            dict(name=ABS, dept="Science"), dict(name=MAYA, dept="Mathematics"), dict(name=BUSY, dept="Mathematics"),
            dict(name=PART, dept="Mathematics"), dict(name=GONE, dept="Mathematics"), dict(name=PETE, dept="PE"),
            dict(name=NEVER, dept="PE"), dict(name=FLEX, role=FAT)]

def world(rules=(), extra=(), rows=None):
    lessons = [L(TUE, 5, 2, ["1A"], "Science", [EVE]), L(TUE, 0, 1, ["2A"], "Science", [SAM]), L(TUE, 9, 1, ["2B"], "Science", [SAM]),
               L(FRI, 0, 1, ["3A"], "Physics", [RUTH]), L(FRI, 0, 2, ["3B"], "Maths", [MAYA]), L(FRI, 2, 1, ["3C"], "PE", [PETE]),
               L(TUE, 6, 1, ["4A"], "Maths", [BUSY])]
    if rows is not None:
        have = {r["name"] for r in rows}
        lessons = [x for x in lessons if set(x["teachers"]) <= have]
    lessons += list(extra)
    pub = P.fake_pub(rows or people_rows(), lessons, roles=[dict(role=FAT, what="Flexi adjunct teachers")])
    pub["model"]["school"].update(start_time="08:00", period_minutes=30)
    pub["model"]["NP"] = 12
    pub["model"]["setup"]["rules"] = list(rules)
    return pub

def settings(never=(), fat=3, other=None):
    return dict(fat_role=FAT, limits=dict(fat_per_day=fat, other_per_day=other, never=list(never)), calendar=CAL, extra_staff=[])

def rec(teacher, lessons=(), dates=("2026-10-13",), periods=None, cancelled=None):
    return dict(teacher=teacher, dates=list(dates), periods=periods, cancelled=cancelled, lessons=list(lessons))

def rl(date, p, n, relief, needed=True, key="k"):
    return dict(key=key, date=date, p=p, n=n, needed=needed, relief=relief)

def lesson_of(pub):
    return [x for x in LS.on_date(pub, CAL, EVE, D13) if x["subject"] == "Science"][0]

def names(g): return [x["name"] for x in g["people"]]
def by_title(got): return {g["title"]: g for g in got["groups"]}

@t
def free_then_groups_by_department_and_subject():
    pub = world(); ls = lesson_of(pub)
    assert (ls["p"], ls["n"]) == (5, 2)
    got = FR.free_then(pub, settings(), [], ls, EVE)
    assert [g["title"] for g in got["groups"]] == ["Science \u00b7 teaches Science", "Science \u00b7 other subjects", "Other departments"], [g["title"] for g in got["groups"]]
    g = by_title(got)
    assert names(g["Science \u00b7 teaches Science"]) == [SAM], names(g["Science \u00b7 teaches Science"])
    assert names(g["Science \u00b7 other subjects"]) == [ABS, TAKEN, RUTH], names(g["Science \u00b7 other subjects"])
    assert names(g["Other departments"]) == [FLEX, GONE, NEVER, PART, PETE, MAYA], names(g["Other departments"])
    sam = g["Science \u00b7 teaches Science"]["people"][0]
    assert sam["depts"] == ["Science"] and sam["subjects"] == ["Science"] and sam["fat"] is False, sam
    assert (sam["week"], sam["today"], sam["term"], sam["marks"], sam["over"]) == (2, 0, 0, [], False), sam

@t
def busy_absent_and_never_are_left_out():
    pub = world(); ls = lesson_of(pub)
    recs = [rec(ABS), rec(PART, periods=[5, 5]), rec(GONE, [rl("2026-10-13", 6, 1, TAKEN, key="g1")], periods=[6, 6])]
    got = FR.free_then(pub, settings(never=[NEVER]), recs, ls, EVE)
    everyone = [n for g in got["groups"] for n in names(g)]
    for gone in (EVE, BUSY, ABS, PART, TAKEN, NEVER, GONE):
        assert gone not in everyone, (gone, everyone)
    assert got["teaching"] == [BUSY], got["teaching"]
    assert SAM in everyone and RUTH in everyone and MAYA in everyone and FLEX in everyone
    off = [rec(ABS, cancelled=dict(by=SAM)), rec(PART, periods=[8, 9]), rec(PETE, periods=[5, 6], dates=("2026-10-14",))]
    got = FR.free_then(pub, settings(), off, ls, EVE)
    everyone = [n for g in got["groups"] for n in names(g)]
    assert ABS in everyone and PART in everyone and PETE in everyone, everyone
    mine = [rec(EVE, [rl("2026-10-13", 5, 2, TAKEN, key=ls["key"])])]
    got = FR.free_then(pub, settings(), mine, ls, EVE)
    assert TAKEN in [n for g in got["groups"] for n in names(g)], "relief already chosen for this very lesson does not block"

@t
def a_must_not_available_is_left_out_a_should_is_marked():
    r = lambda who, s: dict(rule="Not available", scope="Teacher", target=who, strength=s, week="Even", day="Tue", **{"from": 4, "to": 5})
    off = dict(rule="Not available", scope="Teacher", target=PETE, strength="Must", week="Odd", day="Tue", **{"from": 4, "to": 5})
    pub = world(rules=[r(MAYA, "Must"), r(RUTH, "Should"), off]); ls = lesson_of(pub)
    got = FR.free_then(pub, settings(), [], ls, EVE)
    g = by_title(got)
    assert MAYA not in [n for x in got["groups"] for n in names(x)]
    assert PETE in names(g["Other departments"])
    other = g["Science \u00b7 other subjects"]["people"]
    assert [x["name"] for x in other] == [ABS, TAKEN, RUTH] and other[-1]["marks"] == ["prefers not"], other
    assert other[0]["marks"] == []
    miss = dict(r(TAKEN, "Should"), **{"from": 0, "to": 1})
    got = FR.free_then(world(rules=[miss]), settings(), [], ls, EVE)
    assert all(x["marks"] == [] for x in by_title(got)["Science \u00b7 other subjects"]["people"]), "a rule outside the lesson's periods marks nobody"

@t
def keep_free_together_is_marked_and_last():
    k = lambda dept, a, b: dict(rule="Keep free together", scope="Department", target=dept, week="Both", day="All", **{"from": a, "to": b})
    pub = world(rules=[k("PE", 6, 7), k("Mathematics", 0, 1)]); ls = lesson_of(pub)
    got = FR.free_then(pub, settings(), [], ls, EVE)
    other = by_title(got)["Other departments"]["people"]
    assert [x["name"] for x in other] == [FLEX, GONE, PART, MAYA, NEVER, PETE], [x["name"] for x in other]
    assert other[-1]["marks"] == ["department meeting time"] and other[-1]["week"] == 1 and other[-2]["marks"] == ["department meeting time"]
    assert all(x["marks"] == [] for x in other[:-2]), other

@t
def over_the_daily_limit_is_listed_but_over():
    pub = world(); ls = lesson_of(pub)
    recs = [rec(GONE, [rl("2026-10-13", 0, 3, FLEX, key="a"), rl("2026-10-13", 9, 3, PETE, key="b")], periods=[0, 3])]
    got = FR.free_then(pub, settings(fat=3, other=4), recs, ls, EVE)
    other = {x["name"]: x for x in by_title(got)["Other departments"]["people"]}
    f = other[FLEX]
    assert f["over"] is True and f["fat"] is True and f["today"] == 3, f
    assert f["marks"] == ["at 3 relief periods today (the limit is 3)"], f["marks"]
    p = other[PETE]
    assert p["over"] is True and p["marks"] == ["at 3 relief periods today (the limit is 4)"], p
    assert [x["name"] for x in by_title(got)["Other departments"]["people"]][-2:] == sorted([FLEX, PETE]), "over people go last"
    got = FR.free_then(pub, settings(fat=5, other=None), recs, ls, EVE)
    other = {x["name"]: x for x in by_title(got)["Other departments"]["people"]}
    assert other[FLEX]["over"] is False and other[PETE]["over"] is False and other[PETE]["marks"] == []

@t
def order_is_lightest_week_then_term():
    names_ = ["Mr A Two", "Mr A One", "Mr B", "Mr C", "Mr D"]
    rows = [dict(name=EVE, dept="Science")] + [dict(name=n, dept="Mathematics") for n in names_]
    pub = world(rows=rows, extra=[L(FRI, 0, 1, ["5A"], "Maths", ["Mr A Two"]), L(FRI, 1, 1, ["5B"], "Maths", ["Mr A One"]),
                                  L(FRI, 0, 1, ["5C"], "Maths", ["Mr B"]), L(FRI, 0, 1, ["5D"], "Maths", ["Mr C"])])
    ls = lesson_of(pub)
    recs = [rec(GONE, [rl("2026-09-14", 0, 2, "Mr B", key="x"), rl("2026-09-21", 0, 1, "Mr C", key="y")], dates=("2026-09-14", "2026-09-21"))]
    got = FR.free_then(pub, settings(), recs, ls, EVE)
    flat = [x for gr in got["groups"] for x in gr["people"]]
    assert [x["name"] for x in flat] == ["Mr D", "Mr A One", "Mr A Two", "Mr C", "Mr B"], [x["name"] for x in flat]
    assert [(x["week"], x["term"]) for x in flat] == [(0, 0), (1, 0), (1, 0), (1, 1), (1, 2)], [(x["week"], x["term"]) for x in flat]

@t
def week_so_far_counts_teaching_and_chosen_relief():
    pub = world()
    recs = [rec(GONE, [rl("2026-10-12", 3, 2, MAYA, key="a"), rl("2026-10-14", 0, 1, MAYA, key="b"), rl("2026-10-14", 1, 1, MAYA, needed=False, key="c"),
                       rl("2026-10-14", 2, 1, PETE, key="d"), rl("2026-10-20", 0, 3, MAYA, key="e")], dates=("2026-10-12", "2026-10-14", "2026-10-20"))]
    assert FR.week_so_far(pub, CAL, recs, MAYA, D13) == 2 + 2 + 1
    assert FR.week_so_far(pub, CAL, recs, PETE, D13) == 1 + 1
    assert FR.week_so_far(pub, CAL, [], MAYA, D13) == 2
    assert FR.relief_periods(recs, MAYA, {D12}) == 2 and FR.relief_periods(recs, MAYA, {D12, D14, D(2026, 10, 20)}) == 6
    assert FR.relief_periods(recs, MAYA, {"2026-10-14"}) == 1

@t
def a_cancelled_absence_counts_nothing():
    pub = world(); ls = lesson_of(pub)
    recs = [rec(GONE, [rl("2026-10-13", 0, 3, FLEX, key="a")], periods=[0, 3], cancelled=dict(by=SAM, at="x"))]
    assert FR.relief_periods(recs, FLEX, {D13}) == 0
    assert FR.week_so_far(pub, CAL, recs, FLEX, D13) == 0
    got = FR.free_then(pub, settings(), recs, ls, EVE)
    f = [x for g in got["groups"] for x in g["people"] if x["name"] == FLEX][0]
    assert (f["today"], f["week"], f["term"], f["over"], f["marks"]) == (0, 0, 0, False, []), f

print(f"{COUNT} relief request tests passed")

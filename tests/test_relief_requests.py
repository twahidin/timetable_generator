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


@t
def a_chosen_person_is_not_over_the_limit_by_their_own_lesson():
    pub = world(); ls = lesson_of(pub)
    recs = [rec(EVE, [rl("2026-10-13", 5, 2, FLEX, key=ls["key"])], periods=[5, 6])]
    got = FR.free_then(pub, settings(fat=3), recs, ls, EVE)
    f = [x for g in got["groups"] for x in g["people"] if x["name"] == FLEX][0]
    assert (f["today"], f["over"], f["marks"]) == (0, False, []), f
    other = [rec(GONE, [rl("2026-10-13", 8, 2, FLEX, key="z")], periods=[8, 9])]
    got = FR.free_then(pub, settings(fat=3), recs + other, ls, EVE)
    f = [x for g in got["groups"] for x in g["people"] if x["name"] == FLEX][0]
    assert f["today"] == 2 and f["over"] is True, f

@t
def a_second_department_lands_in_that_group():
    both = people_rows() + [dict(name="Ms Dual Ng", dept="Mathematics", dept2="Science")]
    pub = world(rows=both); ls = lesson_of(pub)
    got = FR.free_then(pub, settings(), [], ls, EVE)
    g = by_title(got)
    assert "Ms Dual Ng" in names(g["Science \u00b7 other subjects"]), [(x["title"], names(x)) for x in got["groups"]]
    assert "Ms Dual Ng" not in names(g["Other departments"])

# ---- Task 3: absence records and work files ----
import json  # noqa: E402
from relief import absences as AB  # noqa: E402
from relief import files as FL  # noqa: E402
from relief import settings as RS  # noqa: E402

LS.today = lambda: D(2026, 10, 12)
GRACE, TEAMER = "Ms Grace Wong", "Mr Team Lee"
os.makedirs(os.path.dirname(RS.PATH), exist_ok=True)
store.write_json(RS.PATH, dict(calendar=CAL, team=[TEAMER], management=[GRACE], limits=dict(fat_per_day=3, other_per_day=None, never=[]), fat_role=FAT))

def awf(rows_extra=()):
    pub = world(rows=people_rows() + [dict(name=GRACE, dept="Mathematics"), dict(name=TEAMER, dept="Mathematics")] + list(rows_extra),
                extra=[L(TUE, 8, 1, ["5A"], "Art", [EVE, BUSY])])
    return pub
APUB = awf()
ADIR = os.path.join(DATA, "relief", "absences")

def files_in(d):
    return sorted(os.listdir(d)) if os.path.isdir(d) else []

def data(**kw):
    d = dict(teacher=EVE, dates=["2026-10-13"], periods=None, reason="Medical", reason_text="", remarks="", reporting_officer=GRACE, lessons=[])
    d.update(kw); return d

def lk(pub, p):
    return [x for x in LS.on_date(pub, CAL, EVE, D13) if x["p"] == p][0]["key"]

def refuses(text, f, **kw):
    before, fbefore = files_in(ADIR), files_in(FL.DIR)
    raises(ValueError, f, text)
    assert files_in(ADIR) == before and files_in(FL.DIR) == fbefore, "a refused call wrote something"

@t
def the_sentences_are_exact():
    assert AB.CHANGED == "Your timetable has changed since you opened this page. Open it again."
    assert AB.REASONS == ("Medical", "Child sick", "Course", "Other")
    assert FL.KINDS == (".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx", ".png", ".jpg", ".jpeg") and FL.MAX == 10 * 1024 * 1024

@t
def asking_for_yourself_round_trip():
    r = AB.new(data(), APUB, EVE, "asked")
    assert len(r["id"]) == 12 and r["teacher"] == EVE and r["how"] == "asked" and r["by"] == EVE and r["dates"] == ["2026-10-13"]
    assert r["acknowledged"] is None and r["cancelled"] is None and r["reporting_officer"] == GRACE and r["reason"] == "Medical"
    assert [x["p"] for x in r["lessons"]] == [5, 8], [x["p"] for x in r["lessons"]]
    a, b = r["lessons"]
    assert a["needed"] is True and a["not_needed"] is None and a["relief"] is None and a["relief_by"] is None and a["date"] == "2026-10-13"
    assert a["work"] == dict(text="", link="", files=[]) and a["subject"] == "Science" and a["n"] == 2 and (a["start"], a["end"]) == ("10:30", "11:30")
    assert AB.load(r["id"]) == json.loads(json.dumps(r)) and os.path.exists(os.path.join(ADIR, r["id"] + ".json"))
    assert AB.all_records()[0]["id"] == r["id"] and AB.for_teacher(EVE)[0]["id"] == r["id"] and AB.planned_by(EVE) == []
    assert AB.load("nope") is None
    AB.cancel(r["id"], "Better now", EVE, APUB)

@t
def planning_for_a_colleague_with_a_chosen_relief_teacher():
    k = lk(APUB, 5)
    d = data(how="x", lessons=[dict(key=k, needed=True, relief=SAM, work=dict(text="Chapter 3", link="https://x.test/a", files=[]))])
    r = AB.new(d, APUB, GRACE, "planned", may_choose=True)
    a = r["lessons"][0]
    assert r["by"] == GRACE and r["how"] == "planned" and a["relief"] == SAM and a["relief_by"] == GRACE
    assert a["work"]["text"] == "Chapter 3" and a["work"]["link"] == "https://x.test/a"
    assert AB.planned_by(GRACE)[0]["id"] == r["id"] and AB.planned_by(EVE) == []
    refuses("Only Ms Evelyn Koh can acknowledge this.", lambda: AB.acknowledge(r["id"], GRACE))
    AB.acknowledge(r["id"], EVE)
    assert AB.load(r["id"])["acknowledged"]["at"]
    AB.cancel(r["id"], "Not needed", GRACE, APUB)

@t
def a_shared_lesson_needs_no_relief_unless_asked():
    r = AB.new(data(), APUB, EVE, "asked")
    b = [x for x in r["lessons"] if x["p"] == 8][0]
    assert b["needed"] is False and b["not_needed"] == dict(by="app", why=f"{BUSY} is there") and b["others"] == [BUSY]
    AB.cancel(r["id"], "x", EVE, APUB)
    r = AB.new(data(lessons=[dict(key=lk(APUB, 8), needed=True)]), APUB, EVE, "asked")
    b = [x for x in r["lessons"] if x["p"] == 8][0]
    assert b["needed"] is True and b["not_needed"] is None
    AB.not_needed(r["id"], b["key"], "Covered by Mr Busy Chan", EVE, APUB)
    b = AB.load(r["id"])["lessons"][1]
    assert b["needed"] is False and b["not_needed"] == dict(by=EVE, why="Covered by Mr Busy Chan")
    AB.needed_again(r["id"], b["key"], TEAMER, APUB)
    b = AB.load(r["id"])["lessons"][1]
    assert b["needed"] is True and b["not_needed"] is None
    refuses("You cannot change this absence.", lambda: AB.not_needed(r["id"], b["key"], "x", SAM, APUB))
    refuses("Say why in a line.", lambda: AB.not_needed(r["id"], b["key"], " ", EVE, APUB))
    refuses(AB.CHANGED, lambda: AB.not_needed(r["id"], "nokey", "why", EVE, APUB))
    AB.cancel(r["id"], "x", TEAMER, APUB)

@t
def every_refusal_says_its_sentence_and_writes_nothing():
    k = lk(APUB, 5)
    new = lambda by="asked", pub=APUB, who=EVE, may=False, **kw: (lambda: AB.new(data(**kw), pub, who, by, may_choose=may))
    refuses("Mr Nobody is not on the published timetable or the staff list.", new(teacher="Mr Nobody"))
    bad = "Choose up to 10 school days, today or later."
    refuses(bad, new(dates=[])); refuses(bad, new(dates=[f"2026-10-{d:02d}" for d in range(13, 24)]))
    refuses(bad, new(dates=["nope"])); refuses(bad, new(dates=["2026-10-09"])); refuses(bad, new(dates="2026-10-13"))
    refuses("Sat 17 Oct is not a school day in the calendar.", new(dates=["2026-10-17"]))
    for per in ([3], [4, 2], [-1, 2], [0, 12], ["a", 2], [1.5, 2], "x"):
        refuses("Choose the periods again.", new(periods=per))
    why = "Choose a reason; for Other, say why in a line."
    refuses(why, new(reason="Holiday")); refuses(why, new(reason="Other")); refuses(why, new(reason="Other", reason_text="  "))
    refuses(why, new(reason="Medical", reason_text="x" * 201))
    refuses("Keep the remarks under 300 characters.", new(remarks="x" * 301))
    refuses("Choose your reporting officer.", new(reporting_officer=""))
    refuses("Choose your reporting officer.", new(reporting_officer="Mr Nobody"))
    refuses("There are no lessons to cover in that time.", new(periods=[3, 4]))
    refuses("There are no lessons to cover in that time.", new(dates=["2026-10-13"], lessons=[dict(key=lk(APUB, 8), needed=False)], periods=[8, 8]))
    refuses(AB.CHANGED, new(lessons=[dict(key="2026-10-13/x/0/1/1A/Art/", needed=True)]))
    refuses(f"{BUSY} is not free for 1A Science then.", new(lessons=[dict(key=k, relief=BUSY)], may=True))
    refuses("Only management and the relief team choose relief teachers.", new(lessons=[dict(key=k, relief=SAM)]))
    refuses("A link starts with http:// or https://.", new(lessons=[dict(key=k, work=dict(text="", link="ftp://x", files=[]))]))
    refuses("A link starts with http:// or https://.", new(lessons=[dict(key=k, work=dict(text="", link="https://" + "x" * 500, files=[]))]))
    refuses("Keep the work under 2000 characters.", new(lessons=[dict(key=k, work=dict(text="x" * 2001, link="", files=[]))]))
    r = AB.new(data(periods=[5, 6]), APUB, EVE, "asked")
    assert [x["p"] for x in r["lessons"]] == [5]
    AB.cancel(r["id"], "x", EVE, APUB)

@t
def overlap_is_refused_naming_the_first_sender():
    r = AB.new(data(periods=[5, 6]), APUB, GRACE, "planned")
    refuses("Ms Grace Wong has already sent an absence for Ms Evelyn Koh on Tue 13 Oct.",
            lambda: AB.new(data(periods=[6, 6]), APUB, EVE, "asked"))
    r2 = AB.new(data(periods=[8, 8], lessons=[dict(key=lk(APUB, 8), needed=True)]), APUB, EVE, "asked")
    AB.cancel(r["id"], "x", GRACE, APUB)
    r3 = AB.new(data(periods=[5, 6]), APUB, EVE, "asked")
    for x in (r2, r3): AB.cancel(x["id"], "x", EVE, APUB)

@t
def acknowledge_once_only_by_the_absent_teacher():
    r = AB.new(data(), APUB, GRACE, "planned")
    refuses("Only Ms Evelyn Koh can acknowledge this.", lambda: AB.acknowledge(r["id"], GRACE))
    AB.acknowledge(r["id"], EVE)
    refuses("This was acknowledged already.", lambda: AB.acknowledge(r["id"], EVE))
    AB.cancel(r["id"], "x", GRACE, APUB)
    mine = AB.new(data(), APUB, EVE, "asked")
    raises(ValueError, lambda: AB.acknowledge(mine["id"], EVE))
    AB.cancel(mine["id"], "x", EVE, APUB)

@t
def work_choosing_and_cancelling():
    r = AB.new(data(), APUB, GRACE, "planned"); i = r["id"]; k = lk(APUB, 5)
    AB.set_work(i, k, dict(text="Read p.4", link="http://a.test", files=[]), EVE)
    AB.set_work(i, k, dict(text="Read p.5", link="", files=[]), GRACE)
    assert AB.load(i)["lessons"][0]["work"]["text"] == "Read p.5"
    refuses("You cannot change this absence.", lambda: AB.set_work(i, k, dict(text="x", link="", files=[]), SAM))
    refuses("You cannot change this absence.", lambda: AB.set_work(i, k, dict(text="x", link="", files=[]), TEAMER))
    refuses(AB.CHANGED, lambda: AB.set_work(i, "nokey", dict(text="x", link="", files=[]), EVE))
    AB.choose(i, k, SAM, TEAMER, APUB)
    a = AB.load(i)["lessons"][0]
    assert a["relief"] == SAM and a["relief_by"] == TEAMER
    refuses(f"{BUSY} is not free for 1A Science then.", lambda: AB.choose(i, k, BUSY, TEAMER, APUB))
    AB.choose(i, k, None, TEAMER, APUB)
    assert AB.load(i)["lessons"][0]["relief"] is None
    AB.choose(i, k, FLEX, GRACE, APUB)
    refuses("Say why in a line.", lambda: AB.cancel(i, "", EVE, APUB))
    refuses("Say why in a line.", lambda: AB.cancel(i, "x" * 201, EVE, APUB))
    refuses("You cannot change this absence.", lambda: AB.cancel(i, "no", SAM, APUB))
    AB.cancel(i, "Plans changed", TEAMER, APUB)
    c = AB.load(i)["cancelled"]
    assert c["by"] == TEAMER and c["why"] == "Plans changed" and c["at"]
    gone = "This absence was cancelled."
    refuses(gone, lambda: AB.cancel(i, "again", EVE, APUB))
    refuses(gone, lambda: AB.set_work(i, k, dict(text="x", link="", files=[]), EVE))
    refuses(gone, lambda: AB.choose(i, k, SAM, GRACE, APUB))
    refuses(gone, lambda: AB.not_needed(i, k, "x", EVE, APUB))
    refuses(gone, lambda: AB.needed_again(i, k, EVE, APUB))
    refuses(gone, lambda: AB.acknowledge(i, EVE))
    assert AB.load(i)["lessons"][0]["relief"] == FLEX

@t
def a_changed_lesson_is_marked_not_fatal():
    r = AB.new(data(), APUB, EVE, "asked")
    moved = world(rows=people_rows() + [dict(name=GRACE), dict(name=TEAMER)], extra=[L(TUE, 8, 1, ["5A"], "Art", [EVE, BUSY])])
    moved["model"]["lessons"] = [dict(x, p=6) if x["subject"] == "Science" else x for x in moved["model"]["lessons"]]
    got = AB.matches_now(r, moved, CAL)
    assert [x["changed"] for x in got["lessons"]] == [True, False], got["lessons"]
    assert [x["changed"] for x in AB.matches_now(r, APUB, CAL)["lessons"]] == [False, False]
    assert "changed" not in AB.load(r["id"])["lessons"][0]
    AB.cancel(r["id"], "x", EVE, APUB)

@t
def files_wrong_kind_too_big_and_six_refused():
    r = AB.new(data(), APUB, EVE, "asked"); i = r["id"]; k = lk(APUB, 5)
    refuses("Send a PDF, Word, PowerPoint, Excel or picture file.", lambda: FL.save(i, "run.exe", b"x"))
    refuses("Send a PDF, Word, PowerPoint, Excel or picture file.", lambda: FL.save(i, "noext", b"x"))
    refuses("A file can be at most 10 MB.", lambda: FL.save(i, "big.pdf", b"x" * (FL.MAX + 1)))
    f = FL.save(i, "../Week 3 (notes).PDF", b"%PDF")
    assert f["name"] == "Week 3 (notes).PDF" and f["size"] == 4 and len(f["id"]) == 12, f
    p = FL.path(i, f["id"])
    assert p == os.path.join(FL.DIR, i, f["id"] + ".pdf") and open(p, "rb").read() == b"%PDF"
    assert FL.path(i, "zzzz") is None and FL.path("nope", f["id"]) is None and FL.path(i, "../x") is None
    assert FL.save(i, "a<b>:c?.png", b"x")["name"] == "abc.png"
    AB.set_work(i, k, dict(text="", link="", files=[f]), EVE)
    assert AB.load(i)["lessons"][0]["work"]["files"] == [f]
    refuses(AB.CHANGED, lambda: AB.set_work(i, k, dict(text="", link="", files=[dict(id="abcdef123456", name="x.pdf", size=1)]), EVE))
    six = [FL.save(i, f"w{n}.pdf", b"x") for n in range(6)]
    refuses("A lesson can have at most 5 files.", lambda: AB.set_work(i, k, dict(text="", link="", files=six), EVE))
    assert AB.load(i)["lessons"][0]["work"]["files"] == [f]
    AB.set_work(i, k, dict(text="", link="", files=six[:5]), EVE)
    assert FL.path(i, f["id"]) is None, "a file taken off the lesson is deleted"
    FL.delete(i, six[0]["id"]); assert FL.path(i, six[0]["id"]) is None
    FL.delete(i, six[0]["id"])
    AB.cancel(i, "x", EVE, APUB)

@t
def nothing_half_saved_on_refusal():
    before, fb = files_in(ADIR), files_in(FL.DIR)
    for kw in (dict(remarks="x" * 301), dict(reason="Nope"), dict(dates=["2026-10-17"])):
        raises(ValueError, lambda: AB.new(data(**kw), APUB, EVE, "asked"))
    assert files_in(ADIR) == before and files_in(FL.DIR) == fb
    assert not [f for f in files_in(ADIR) if f.endswith(".tmp")]


# ---- Task 3 fix round 1 ----
@t
def work_checks_come_last():
    first = AB.new(data(periods=[5, 6]), APUB, GRACE, "planned")
    bad = dict(key=lk(APUB, 5), work=dict(text="", link="ftp://x", files=[]))
    refuses("Ms Grace Wong has already sent an absence for Ms Evelyn Koh on Tue 13 Oct.", lambda: AB.new(data(periods=[5, 6], lessons=[bad]), APUB, EVE, "asked"))
    AB.cancel(first["id"], "x", GRACE, APUB)
    refuses("Only management and the relief team choose relief teachers.",
            lambda: AB.new(data(lessons=[dict(key=lk(APUB, 5), relief=SAM, work=dict(text="", link="ftp://x", files=[]))]), APUB, EVE, "asked"))
    refuses("A link starts with http:// or https://.", lambda: AB.new(data(lessons=[bad]), APUB, EVE, "asked"))

@t
def an_ordinary_teacher_cannot_probe_who_is_free():
    refuses("Only management and the relief team choose relief teachers.",
            lambda: AB.new(data(lessons=[dict(key=lk(APUB, 5), relief=BUSY)]), APUB, EVE, "asked"))
    refuses("Only management and the relief team choose relief teachers.",
            lambda: AB.new(data(lessons=[dict(key=lk(APUB, 5), relief="Mr Nobody")]), APUB, EVE, "asked"))

@t
def an_attached_file_keeps_its_own_extension_and_stays_while_used():
    r = AB.new(data(lessons=[dict(key=lk(APUB, 8), needed=True)]), APUB, EVE, "asked"); i = r["id"]
    k5, k8 = lk(APUB, 5), lk(APUB, 8)
    f = FL.save(i, "notes.pdf", b"%PDF")
    AB.set_work(i, k5, dict(text="", link="", files=[dict(f, name="x.html")]), EVE)
    AB.set_work(i, k8, dict(text="", link="", files=[dict(f, name="y.exe")]), EVE)
    got = AB.load(i)["lessons"]
    assert got[0]["work"]["files"][0]["name"] == "x.pdf" and got[1]["work"]["files"][0]["name"] == "y.pdf", got
    AB.set_work(i, k5, dict(text="", link="", files=[]), EVE)
    assert FL.path(i, f["id"]), "still on the other lesson"
    AB.set_work(i, k8, dict(text="", link="", files=[]), EVE)
    assert FL.path(i, f["id"]) is None
    AB.cancel(i, "x", EVE, APUB)

@t
def needed_again_checks_the_overlap_too():
    first = AB.new(data(periods=[5, 6]), APUB, GRACE, "planned")
    k = lk(APUB, 5)
    AB.not_needed(first["id"], k, "covered", GRACE, APUB)
    second = AB.new(data(periods=[5, 6]), APUB, EVE, "asked")
    refuses("Ms Evelyn Koh has already sent an absence for Ms Evelyn Koh on Tue 13 Oct.", lambda: AB.needed_again(first["id"], k, GRACE, APUB))
    AB.cancel(second["id"], "x", EVE, APUB)
    AB.needed_again(first["id"], k, GRACE, APUB)
    AB.cancel(first["id"], "x", GRACE, APUB)

@t
def times_are_school_time_with_the_offset():
    r = AB.new(data(), APUB, EVE, "asked")
    assert r["at"].endswith("+08:00"), r["at"]
    AB.cancel(r["id"], "x", EVE, APUB)
    assert AB.load(r["id"])["cancelled"]["at"].endswith("+08:00")

@t
def week_and_term_leave_out_the_chosen_lessons_own_periods():
    pub = world(); ls = lesson_of(pub)
    recs = [rec(EVE, [rl("2026-10-13", 5, 2, MAYA, key=ls["key"])], periods=[5, 6])]
    m = [x for g in FR.free_then(pub, settings(), recs, ls, EVE)["groups"] for x in g["people"] if x["name"] == MAYA][0]
    n = [x for g in FR.free_then(pub, settings(), [], ls, EVE)["groups"] for x in g["people"] if x["name"] == MAYA][0]
    assert (m["week"], m["term"], m["today"]) == (n["week"], n["term"], n["today"]) == (2, 0, 0), (m, n)

print(f"{COUNT} relief request tests passed")

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

def wk(text="", link="", files=(), known=()):
    """a work save's body: known = the files (or their ids) on the lesson when the caller's page read it"""
    return dict(text=text, link=link, files=list(files), known=[k if isinstance(k, str) else k["id"] for k in known])

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
    AB.cancel(r["id"], "Better now", EVE)

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
    AB.cancel(r["id"], "Not needed", GRACE)

@t
def a_shared_lesson_needs_no_relief_unless_asked():
    r = AB.new(data(), APUB, EVE, "asked")
    b = [x for x in r["lessons"] if x["p"] == 8][0]
    assert b["needed"] is False and b["not_needed"] == dict(by="app", why=f"{BUSY} is there") and b["others"] == [BUSY]
    AB.cancel(r["id"], "x", EVE)
    r = AB.new(data(lessons=[dict(key=lk(APUB, 8), needed=True)]), APUB, EVE, "asked")
    b = [x for x in r["lessons"] if x["p"] == 8][0]
    assert b["needed"] is True and b["not_needed"] is None
    AB.not_needed(r["id"], b["key"], "Covered by Mr Busy Chan", EVE)
    b = AB.load(r["id"])["lessons"][1]
    assert b["needed"] is False and b["not_needed"] == dict(by=EVE, why="Covered by Mr Busy Chan")
    AB.needed_again(r["id"], b["key"], TEAMER, team=True)
    b = AB.load(r["id"])["lessons"][1]
    assert b["needed"] is True and b["not_needed"] is None
    refuses("You cannot change this absence.", lambda: AB.not_needed(r["id"], b["key"], "x", SAM))
    refuses("Say why in a line.", lambda: AB.not_needed(r["id"], b["key"], " ", EVE))
    refuses(AB.CHANGED, lambda: AB.not_needed(r["id"], "nokey", "why", EVE))
    AB.cancel(r["id"], "x", TEAMER, team=True)

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
    AB.cancel(r["id"], "x", EVE)

@t
def overlap_is_refused_naming_the_first_sender():
    r = AB.new(data(periods=[5, 6]), APUB, GRACE, "planned")
    refuses("Ms Grace Wong has already sent an absence for Ms Evelyn Koh on Tue 13 Oct.",
            lambda: AB.new(data(periods=[6, 6]), APUB, EVE, "asked"))
    r2 = AB.new(data(periods=[8, 8], lessons=[dict(key=lk(APUB, 8), needed=True)]), APUB, EVE, "asked")
    AB.cancel(r["id"], "x", GRACE)
    r3 = AB.new(data(periods=[5, 6]), APUB, EVE, "asked")
    for x in (r2, r3): AB.cancel(x["id"], "x", EVE)

@t
def acknowledge_once_only_by_the_absent_teacher():
    r = AB.new(data(), APUB, GRACE, "planned")
    refuses("Only Ms Evelyn Koh can acknowledge this.", lambda: AB.acknowledge(r["id"], GRACE))
    AB.acknowledge(r["id"], EVE)
    refuses("This was acknowledged already.", lambda: AB.acknowledge(r["id"], EVE))
    AB.cancel(r["id"], "x", GRACE)
    mine = AB.new(data(), APUB, EVE, "asked")
    raises(ValueError, lambda: AB.acknowledge(mine["id"], EVE))
    AB.cancel(mine["id"], "x", EVE)

@t
def work_choosing_and_cancelling():
    r = AB.new(data(), APUB, GRACE, "planned"); i = r["id"]; k = lk(APUB, 5)
    AB.set_work(i, k, wk("Read p.4", "http://a.test"), EVE)
    AB.set_work(i, k, wk("Read p.5"), GRACE)
    assert AB.load(i)["lessons"][0]["work"]["text"] == "Read p.5"
    refuses("You cannot change this absence.", lambda: AB.set_work(i, k, wk("x"), SAM))
    refuses("You cannot change this absence.", lambda: AB.set_work(i, k, wk("x"), TEAMER))
    refuses(AB.CHANGED, lambda: AB.set_work(i, "nokey", wk("x"), EVE))
    AB.choose(i, k, SAM, TEAMER, APUB)
    a = AB.load(i)["lessons"][0]
    assert a["relief"] == SAM and a["relief_by"] == TEAMER
    refuses(f"{BUSY} is not free for 1A Science then.", lambda: AB.choose(i, k, BUSY, TEAMER, APUB))
    AB.choose(i, k, None, TEAMER, APUB)
    assert AB.load(i)["lessons"][0]["relief"] is None
    AB.choose(i, k, FLEX, GRACE, APUB)
    refuses("Say why in a line.", lambda: AB.cancel(i, "", EVE))
    refuses("Say why in a line.", lambda: AB.cancel(i, "x" * 201, EVE))
    refuses("You cannot change this absence.", lambda: AB.cancel(i, "no", SAM))
    AB.cancel(i, "Plans changed", TEAMER, team=True)
    c = AB.load(i)["cancelled"]
    assert c["by"] == TEAMER and c["why"] == "Plans changed" and c["at"]
    gone = "This absence was cancelled."
    refuses(gone, lambda: AB.cancel(i, "again", EVE))
    refuses(gone, lambda: AB.set_work(i, k, wk("x"), EVE))
    refuses(gone, lambda: AB.choose(i, k, SAM, GRACE, APUB))
    refuses(gone, lambda: AB.not_needed(i, k, "x", EVE))
    refuses(gone, lambda: AB.needed_again(i, k, EVE))
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
    AB.cancel(r["id"], "x", EVE)

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
    AB.set_work(i, k, wk(files=[f]), EVE)
    assert AB.load(i)["lessons"][0]["work"]["files"] == [f]
    refuses(AB.CHANGED, lambda: AB.set_work(i, k, wk(files=[dict(id="abcdef123456", name="x.pdf", size=1)], known=[f]), EVE))
    six = [FL.save(i, f"w{n}.pdf", b"x") for n in range(6)]
    refuses("A lesson can have at most 5 files.", lambda: AB.set_work(i, k, wk(files=six, known=[f]), EVE))
    assert AB.load(i)["lessons"][0]["work"]["files"] == [f]
    AB.set_work(i, k, wk(files=six[:5], known=[f]), EVE)
    assert FL.path(i, f["id"]) is None, "a file taken off the lesson is deleted"
    FL.delete(i, six[0]["id"]); assert FL.path(i, six[0]["id"]) is None
    FL.delete(i, six[0]["id"])
    AB.cancel(i, "x", EVE)

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
    AB.cancel(first["id"], "x", GRACE)
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
    AB.set_work(i, k5, wk(files=[dict(f, name="x.html")]), EVE)
    AB.set_work(i, k8, wk(files=[dict(f, name="y.exe")]), EVE)
    got = AB.load(i)["lessons"]
    assert got[0]["work"]["files"][0]["name"] == "x.pdf" and got[1]["work"]["files"][0]["name"] == "y.pdf", got
    AB.set_work(i, k5, wk(known=[f]), EVE)
    assert FL.path(i, f["id"]), "still on the other lesson"
    AB.set_work(i, k8, wk(known=[f]), EVE)
    assert FL.path(i, f["id"]) is None
    AB.cancel(i, "x", EVE)

@t
def needed_again_checks_the_overlap_too():
    first = AB.new(data(periods=[5, 6]), APUB, GRACE, "planned")
    k = lk(APUB, 5)
    AB.not_needed(first["id"], k, "covered", GRACE)
    second = AB.new(data(periods=[5, 6]), APUB, EVE, "asked")
    refuses("Ms Evelyn Koh has already sent an absence for Ms Evelyn Koh on Tue 13 Oct.", lambda: AB.needed_again(first["id"], k, GRACE))
    AB.cancel(second["id"], "x", EVE)
    AB.needed_again(first["id"], k, GRACE)
    AB.cancel(first["id"], "x", GRACE)

@t
def times_are_school_time_with_the_offset():
    r = AB.new(data(), APUB, EVE, "asked")
    assert r["at"].endswith("+08:00"), r["at"]
    AB.cancel(r["id"], "x", EVE)
    assert AB.load(r["id"])["cancelled"]["at"].endswith("+08:00")

@t
def week_and_term_leave_out_the_chosen_lessons_own_periods():
    pub = world(); ls = lesson_of(pub)
    recs = [rec(EVE, [rl("2026-10-13", 5, 2, MAYA, key=ls["key"])], periods=[5, 6])]
    m = [x for g in FR.free_then(pub, settings(), recs, ls, EVE)["groups"] for x in g["people"] if x["name"] == MAYA][0]
    n = [x for g in FR.free_then(pub, settings(), [], ls, EVE)["groups"] for x in g["people"] if x["name"] == MAYA][0]
    assert (m["week"], m["term"], m["today"]) == (n["week"], n["term"], n["today"]) == (2, 0, 0), (m, n)

# ---- Task 4: rights and routes ----
import contextlib, csv, io, urllib.parse  # noqa: E402
import access  # noqa: E402
from flask import session as _session  # noqa: E402

@contextlib.contextmanager
def published(pub):
    old = store.published; store.published = lambda: pub
    try: yield
    finally: store.published = old

def signed_in(card, code):
    c = A.app.test_client()
    r = c.post("/login", data={"as": card, "code": code})
    return c, r

def committee():
    c, r = signed_in("committee", os.environ["COMMITTEE_CODE"]); assert r.status_code == 302
    return c

def staff(name):
    c, r = signed_in("relief", access.staff_code(name)); assert r.status_code == 302, (name, r.status_code)
    return c

PLAN_ONLY = "Only management and the relief team plan relief for a colleague."
CHOOSE_ONLY = "Only management and the relief team choose relief teachers."
TEAM_ONLY = "Only the relief team can open What's in."
NOT_YOURS = "This absence is not yours to open."
GONE_ABS = "That absence is not there any more."
NO_PUB = "Publish the timetable first: relief reads the teachers from it."
SIGN_IN = "Please sign in again."
K5, K8 = lk(APUB, 5), lk(APUB, 8)
SEEN = os.path.join(DATA, "relief", "seen.json")

def q(s): return urllib.parse.quote(s, safe="")

def ask(c, **kw):
    d = dict(teacher=EVE, dates=["2026-10-13"], periods=None, reason="Medical", reason_text="", remarks="", reporting_officer=GRACE, lessons=[])
    d.update(kw)
    return c.post("/api/relief/absences", json=d)

def ok(r, code=200):
    assert r.status_code == code, (r.status_code, r.get_data(as_text=True)[:400])
    return r.get_json()

def no(r, code, text):
    assert r.status_code == code, (code, r.status_code, r.get_data(as_text=True)[:400])
    assert r.get_json() == {"error": text}, r.get_json()

def lesson_url(i, key, what): return f"/api/relief/absences/{i}/lessons/{q(key)}/{what}"

def upload(c, i, name="notes.pdf", data=b"%PDF-1 notes"):
    return c.post(f"/api/relief/absences/{i}/files", data={"file": (io.BytesIO(data), name)}, content_type="multipart/form-data")

def cancel_all(c, *ids):
    for i in ids: ok(c.post(f"/api/relief/absences/{i}/cancel", json=dict(why="Tidy up")))

@t
def asking_through_the_api():
    with published(APUB):
        eve = staff(EVE)
        got = ok(eve.get("/api/relief/lessons?dates=2026-10-13"))
        assert [x["p"] for x in got["lessons"]] == [5, 8] and list(got["by_date"]) == ["2026-10-13"], got
        assert got["by_date"]["2026-10-13"] == got["lessons"]
        a, b = got["lessons"]
        assert a["key"] == K5 and a["date"] == "2026-10-13" and (a["start"], a["end"]) == ("10:30", "11:30") and b["others"] == [BUSY], got
        assert got["periods"] == [dict(p=i, start=f"{8 + i // 2:02d}:{30 * (i % 2):02d}", end=f"{8 + (i + 1) // 2:02d}:{30 * ((i + 1) % 2):02d}") for i in range(12)], got["periods"]
        assert got["periods"][0] == dict(p=0, start="08:00", end="08:30") and got["periods"][-1] == dict(p=11, start="13:30", end="14:00")
        some = ok(eve.get("/api/relief/lessons?dates=2026-10-13&from=5&to=6"))
        assert some["periods"] == got["periods"], "every period of the day, whatever the from and to"
        assert [x["p"] for x in ok(eve.get(f"/api/relief/lessons?teacher={q(EVE)}&dates=2026-10-13&from=5&to=6"))["lessons"]] == [5]
        two = ok(eve.get("/api/relief/lessons?dates=2026-10-13,%202026-10-27"))
        assert list(two["by_date"]) == ["2026-10-13", "2026-10-27"] and len(two["lessons"]) == 4, two
        no(eve.get("/api/relief/lessons?dates=2026-10-17"), 400, "Sat 17 Oct is not a school day in the calendar.")
        for bad in ("", "nope", "2026-10-09"):
            no(eve.get("/api/relief/lessons?dates=" + bad), 400, "Choose up to 10 school days, today or later.")
        for per in ("from=5", "to=6", "from=x&to=6", "from=6&to=5", "from=0&to=12", "from=-1&to=2"):
            no(eve.get("/api/relief/lessons?dates=2026-10-13&" + per), 400, "Choose the periods again.")
        people = ok(eve.get("/api/relief/people"))
        assert {"name": GRACE, "depts": ["Mathematics"]} in people and all(set(p) == {"name", "depts"} for p in people), people
        before = files_in(ADIR)
        no(ask(eve, lessons=[dict(key=K5, relief=SAM)]), 400, CHOOSE_ONLY)
        no(eve.post("/api/relief/absences", data="nope", content_type="application/json"), 400, AB.WRONG)
        assert files_in(ADIR) == before            # a key that is not a string: an_unexpected_body_is_answered_plainly_and_logged
        r = ok(ask(eve, how="planned", by=SAM, lessons=[dict(key=K5, work=dict(text="Read p.4", link="", files=[]))]))
        assert r["how"] == "asked" and r["by"] == EVE and r["teacher"] == EVE and r["reason"] == "Medical", r
        assert [x["changed"] for x in r["lessons"]] == [False, False] and r["lessons"][0]["work"]["text"] == "Read p.4"
        i = r["id"]
        assert AB.load(i)["how"] == "asked" and "changed" not in AB.load(i)["lessons"][0]
        assert i in [x["id"] for x in ok(eve.get("/api/relief/absences/mine"))["absences"]]
        assert ok(eve.get(f"/api/relief/absences/{i}"))["reason"] == "Medical"
        no(ask(eve, teacher=None), 400, "Ms Evelyn Koh has already sent an absence for Ms Evelyn Koh on Tue 13 Oct.")   # no teacher: yourself, asked
        got = ok(eve.put(lesson_url(i, K5, "work"), json=wk("Read p.5", "https://x.test/a")))
        assert got["lessons"][0]["work"] == dict(text="Read p.5", link="https://x.test/a", files=[]) and got["lessons"][0]["changed"] is False
        no(eve.put(lesson_url(i, K5, "work"), json=wk(link="ftp://x")), 400, "A link starts with http:// or https://.")
        assert ok(eve.post(lesson_url(i, K8, "needed")))["lessons"][1]["needed"] is True
        got = ok(eve.post(lesson_url(i, K8, "not-needed"), json=dict(why="Covered by Mr Busy Chan")))
        assert got["lessons"][1]["needed"] is False and got["lessons"][1]["not_needed"] == dict(by=EVE, why="Covered by Mr Busy Chan")
        no(eve.post(lesson_url(i, K8, "not-needed"), json={}), 400, "Say why in a line.")
        no(eve.post(lesson_url(i, "nokey", "needed")), 400, AB.CHANGED)
        no(eve.put(lesson_url(i, K5, "relief"), json=dict(relief=SAM)), 403, CHOOSE_ONLY)
        no(eve.post(f"/api/relief/absences/{i}/acknowledge"), 400, "Only Ms Evelyn Koh can acknowledge this.")
        no(eve.post(f"/api/relief/absences/{i}/cancel", json=dict(why=" ")), 400, "Say why in a line.")
        got = ok(eve.post(f"/api/relief/absences/{i}/cancel", json=dict(why="Better now")))
        assert got["cancelled"]["by"] == EVE and got["cancelled"]["why"] == "Better now"
        no(eve.post(f"/api/relief/absences/{i}/cancel", json=dict(why="again")), 400, "This absence was cancelled.")

@t
def planning_needs_the_right():
    with published(APUB):
        sam, grace, team = staff(SAM), staff(GRACE), staff(TEAMER)
        before = files_in(ADIR)
        no(sam.get(f"/api/relief/free?absent={q(EVE)}&key={q(K5)}"), 403, CHOOSE_ONLY)
        no(ask(sam), 403, PLAN_ONLY)
        no(ask(sam, teacher="Mr Nobody"), 403, PLAN_ONLY)
        no(sam.get(f"/api/relief/lessons?teacher={q(EVE)}&dates=2026-10-13"), 403, PLAN_ONLY)
        no(sam.get(f"/api/relief/lessons?teacher=Mr%20Nobody&dates=2026-10-13"), 403, PLAN_ONLY)
        no(sam.get("/api/relief/absences/planned"), 403, PLAN_ONLY)
        no(sam.get("/api/relief/planned.csv"), 403, PLAN_ONLY)
        no(sam.get("/api/relief/absences"), 403, TEAM_ONLY)
        assert files_in(ADIR) == before
        free = ok(grace.get(f"/api/relief/free?absent={q(EVE)}&key={q(K5)}"))
        assert SAM in [p["name"] for g in free["groups"] for p in g["people"]] and BUSY in free["teaching"], free
        assert "reason" not in json.dumps(free)
        no(grace.get(f"/api/relief/free?absent={q(EVE)}&key={q('2026-10-13/x/0/1/1A/Art/')}"), 400, AB.CHANGED)
        no(grace.get(f"/api/relief/free?absent={q(EVE)}&key=nope"), 400, AB.CHANGED)
        no(grace.get(f"/api/relief/free?absent=Mr%20Nobody&key={q(K5)}"), 400, "Mr Nobody is not on the published timetable or the staff list.")
        no(grace.get(f"/api/relief/free?key={q(K5)}"), 400, "That person is not on the published timetable or the staff list.")
        no(grace.get("/api/relief/lessons?teacher=Mr%20Nobody&dates=2026-10-13"), 400, "Mr Nobody is not on the published timetable or the staff list.")
        assert [x["p"] for x in ok(grace.get(f"/api/relief/lessons?teacher={q(EVE)}&dates=2026-10-13"))["lessons"]] == [5, 8]
        r = ok(ask(grace, reporting_officer="", lessons=[dict(key=K5, relief=SAM)]))
        assert r["how"] == "planned" and r["by"] == GRACE and r["teacher"] == EVE, r
        assert r["lessons"][0]["relief"] == SAM and r["lessons"][0]["relief_by"] == GRACE and r["lessons"][0]["changed"] is False
        i = r["id"]
        assert ok(team.put(lesson_url(i, K5, "relief"), json=dict(relief=None)))["lessons"][0]["relief"] is None
        got = ok(team.put(lesson_url(i, K5, "relief"), json=dict(relief=FLEX)))["lessons"][0]
        assert got["relief"] == FLEX and got["relief_by"] == TEAMER
        no(team.put(lesson_url(i, K5, "relief"), json=dict(relief=BUSY)), 400, f"{BUSY} is not free for 1A Science then.")
        no(team.put(lesson_url(i, K5, "relief"), json=dict(relief=["x"])), 400, AB.WRONG)
        no(team.put(lesson_url(i, K8, "relief"), json=dict(relief=SAM)), 400, "This lesson does not need relief.")
        assert AB.load(i)["lessons"][0]["relief"] == FLEX
        cancel_all(grace, i)

@t
def a_team_member_sees_whats_in_and_new_since():
    old_now = AB._now
    try:
        with published(APUB):
            eve, team, grace, sam = staff(EVE), staff(TEAMER), staff(GRACE), staff(SAM)
            AB._now = lambda: "2026-10-12T09:00:00+08:00"
            one = ok(ask(eve, dates=["2026-10-27"]))["id"]
            seen_before = open(SEEN).read() if os.path.exists(SEEN) else None
            got = ok(team.get("/api/relief/absences"))
            assert (open(SEEN).read() if os.path.exists(SEEN) else None) == seen_before, "a GET never writes"
            ids = [x["id"] for x in got["absences"]]
            assert one in ids and got["new_since"] is None and all(x["new"] for x in got["absences"]), got["new_since"]
            ats = [x["at"] for x in got["absences"]]
            assert ats == sorted(ats, reverse=True), "newest first"
            assert [x for x in got["absences"] if x["id"] == one][0]["reason"] == "Medical" and got["as_of"]
            assert all("changed" in x for r in got["absences"] for x in r["lessons"])
            saved = ok(team.post("/api/relief/absences/seen", json=dict(at="2026-10-12T09:30:00+08:00")))
            assert saved == dict(seen="2026-10-12T09:30:00+08:00"), saved
            assert store.read_json(SEEN) == {TEAMER: "2026-10-12T09:30:00+08:00"}
            got = ok(team.get("/api/relief/absences"))
            assert got["new_since"] == "2026-10-12T09:30:00+08:00"
            assert [x["new"] for x in got["absences"] if x["id"] == one] == [False]
            AB._now = lambda: "2026-10-12T10:00:00+08:00"
            two = ok(ask(grace, dates=["2026-11-10"]))["id"]
            got = {x["id"]: x["new"] for x in ok(team.get("/api/relief/absences"))["absences"]}
            assert got[two] is True and got[one] is False, got
            AB._now = old_now
            later = ok(team.post("/api/relief/absences/seen", json=dict(at="2099-01-01T00:00:00+08:00")))["seen"]
            assert later < "2099" and later.endswith("+08:00"), later
            assert ok(team.post("/api/relief/absences/seen", json=dict(at="nope")))["seen"].endswith("+08:00")
            assert ok(team.post("/api/relief/absences/seen"))["seen"].endswith("+08:00")
            got = ok(team.get("/api/relief/absences"))
            assert not any(x["new"] for x in got["absences"] if x["id"] in (one, two))
            no(grace.get("/api/relief/absences"), 403, TEAM_ONLY)
            no(grace.post("/api/relief/absences/seen"), 403, TEAM_ONLY)
            no(sam.post("/api/relief/absences/seen"), 403, TEAM_ONLY)
            assert set(store.read_json(SEEN)) == {TEAMER}
            cancel_all(eve, one); cancel_all(grace, two)
    finally: AB._now = old_now

@t
def management_sees_planned_by_me():
    with published(APUB):
        grace, team, eve = staff(GRACE), staff(TEAMER), staff(EVE)
        a = ok(ask(grace, periods=[5, 6]))
        b = ok(ask(team, periods=[8, 8], lessons=[dict(key=K8, needed=True)]))
        assert a["how"] == b["how"] == "planned" and b["by"] == TEAMER
        for c, me, theirs, other in ((grace, GRACE, a, b), (team, TEAMER, b, a)):
            got = ok(c.get("/api/relief/absences/planned"))["absences"]
            ids = [x["id"] for x in got]
            assert theirs["id"] in ids and other["id"] not in ids and all(x["by"] == me and x["how"] == "planned" for x in got), (me, ids)
        assert all("changed" in x for x in ok(grace.get("/api/relief/absences/planned"))["absences"][0]["lessons"])
        mine = {x["id"]: x for x in ok(eve.get("/api/relief/absences/mine"))["absences"]}
        assert mine[a["id"]]["how"] == "planned" and mine[b["id"]]["by"] == TEAMER
        assert ok(grace.get(f"/api/relief/absences/{b['id']}"))["reason"] == "Medical"        # management opens any absence
        no(grace.post(f"/api/relief/absences/{a['id']}/acknowledge"), 400, "Only Ms Evelyn Koh can acknowledge this.")
        got = ok(eve.post(f"/api/relief/absences/{a['id']}/acknowledge"))
        assert got["acknowledged"]["at"] and got["lessons"][0]["changed"] is False
        assert ok(grace.put(lesson_url(a["id"], K5, "work"), json=wk("p.9")))["lessons"][0]["work"]["text"] == "p.9"
        no(grace.put(lesson_url(b["id"], K8, "work"), json=wk("x")), 400, "You cannot change this absence.")
        no(grace.post(f"/api/relief/absences/{b['id']}/cancel", json=dict(why="x")), 400, "You cannot change this absence.")
        cancel_all(grace, a["id"]); cancel_all(eve, b["id"])

@t
def another_teachers_absence_is_403_and_hides_the_reason():
    with published(APUB):
        eve, sam, grace, team = staff(EVE), staff(SAM), staff(GRACE), staff(TEAMER)
        r = ok(ask(eve, reason="Other", reason_text="A private matter", remarks="Quiet please"))
        i = r["id"]
        fid = ok(upload(eve, i))["id"]
        ok(eve.put(lesson_url(i, K5, "work"), json=wk(files=[dict(id=fid, name="notes.pdf")])))
        kept = AB.load(i)
        calls = [("GET", f"/api/relief/absences/{i}", None), ("POST", f"/api/relief/absences/{i}/acknowledge", None),
                 ("PUT", lesson_url(i, K5, "work"), wk("x")), ("POST", lesson_url(i, K5, "not-needed"), dict(why="x")),
                 ("POST", lesson_url(i, K8, "needed"), None), ("PUT", lesson_url(i, K5, "relief"), dict(relief=FLEX)),
                 ("POST", f"/api/relief/absences/{i}/cancel", dict(why="x")), ("GET", f"/api/relief/files/{i}/{fid}", None)]
        for method, url, body in calls:
            no(sam.open(url, method=method, json=body), 403, NOT_YOURS)
        no(upload(sam, i), 403, NOT_YOURS)
        assert AB.load(i) == kept, "nothing changed"
        for gone in ("abcdef123456", "nope"):       # someone who may not open every absence cannot tell a missing one from another's
            no(sam.get(f"/api/relief/absences/{gone}"), 403, NOT_YOURS)
            no(sam.post(f"/api/relief/absences/{gone}/cancel", json=dict(why="x")), 403, NOT_YOURS)
            no(grace.get(f"/api/relief/absences/{gone}"), 404, GONE_ABS)
        seen = [sam.get("/api/relief/absences/mine"), sam.get("/api/relief/people"), sam.get("/api/relief/lessons?dates=2026-10-13")]
        assert i not in [x["id"] for x in seen[0].get_json()["absences"]]
        for x in seen: assert b"A private matter" not in x.data and b"Other" not in x.data, x.data[:200]
        for c in (eve, grace, team):      # the absent teacher, management (not the planner) and the relief team may open it
            got = ok(c.get(f"/api/relief/absences/{i}"))
            assert got["reason"] == "Other" and got["reason_text"] == "A private matter"
            assert c.get(f"/api/relief/files/{i}/{fid}").status_code == 200
        cancel_all(eve, i)

@t
def files_round_trip_and_rights():
    with published(APUB):
        eve, grace, team, sam = staff(EVE), staff(GRACE), staff(TEAMER), staff(SAM)
        i = ok(ask(grace))["id"]
        f = ok(upload(eve, i, "Week 3 notes.PDF", b"%PDF-1 week 3"))
        assert f["name"] == "Week 3 notes.PDF" and f["size"] == len(b"%PDF-1 week 3") and len(f["id"]) == 12, f
        g = ok(upload(grace, i, "slides.pptx", b"PK slides"))            # the planner may add files too
        ok(eve.put(lesson_url(i, K5, "work"), json=wk("See the notes", files=[f, g])))
        r = eve.get(f"/api/relief/files/{i}/{f['id']}")
        assert r.status_code == 200 and r.data == b"%PDF-1 week 3", r.status_code
        assert r.headers["Content-Disposition"].startswith("attachment") and "Week 3 notes.PDF" in r.headers["Content-Disposition"], r.headers
        assert "no-store" in r.headers["Cache-Control"]
        for c in (grace, team): assert c.get(f"/api/relief/files/{i}/{g['id']}").data == b"PK slides"
        no(sam.get(f"/api/relief/files/{i}/{f['id']}"), 403, NOT_YOURS)
        no(eve.get(f"/api/relief/files/{i}/abcdef123456"), 404, "That file is not there any more.")
        no(eve.get(f"/api/relief/files/{i}/x.y"), 404, "That file is not there any more.")
        before = files_in(os.path.join(FL.DIR, i))
        no(upload(team, i), 403, "You cannot change this absence.")        # the team may open it, not add to it
        no(upload(sam, i), 403, NOT_YOURS)
        no(upload(eve, i, "run.exe", b"MZ"), 400, FL.WRONG_KIND)
        no(upload(eve, i, "empty.pdf", b""), 400, FL.WRONG_KIND)
        no(eve.post(f"/api/relief/absences/{i}/files", data={}, content_type="multipart/form-data"), 400, FL.WRONG_KIND)
        old = FL.MAX
        try:
            FL.MAX = 100
            no(upload(eve, i, "big.pdf", b"x" * 101), 400, FL.TOO_BIG)                       # read in a bounded way
            no(upload(eve, i, "huge.pdf", b"x" * (200 * 1024)), 400, FL.TOO_BIG)              # refused from its length
        finally: FL.MAX = old
        assert files_in(os.path.join(FL.DIR, i)) == before, "nothing half-saved"
        cancel_all(eve, i)
        no(upload(eve, i), 400, "This absence was cancelled.")
        assert eve.get(f"/api/relief/files/{i}/{f['id']}").status_code == 200, "a cancelled absence's files still open"
        no(upload(eve, "abcdef123456"), 403, NOT_YOURS)
        no(upload(grace, "abcdef123456"), 404, GONE_ABS)

@t
def planned_csv_has_no_reason_and_no_formulas():
    with published(APUB):
        grace, team, eve = staff(GRACE), staff(TEAMER), staff(EVE)
        a = ok(ask(grace, reason="Other", reason_text="Secret clinic visit", remarks="=HYPERLINK(\"http://x.test\")",
                   lessons=[dict(key=K5, relief=SAM), dict(key=K8, needed=True)]))["id"]
        b = ok(ask(eve, dates=["2026-10-27"], reason="Child sick"))["id"]           # asked: in the file too, set by the teacher
        c = ok(ask(team, dates=["2026-11-10"], remarks="Course"))["id"]
        d = ok(ask(team, dates=["2026-10-27"], periods=[8, 8], lessons=[dict(key=lk(APUB, 8).replace("2026-10-13", "2026-10-27"), needed=True)]))["id"]
        cancel_all(team, d)
        r = grace.get("/api/relief/planned.csv?start=2026-10-13&end=2026-10-27")
        assert r.status_code == 200 and r.mimetype == "text/csv" and "attachment" in r.headers["Content-Disposition"], r.status_code
        text = r.data.decode("utf-8")
        assert text.startswith("﻿")
        rows = list(csv.reader(io.StringIO(text.lstrip("﻿"))))
        assert rows[0] == ["Date", "Absent", "Class / group", "Periods", "Time", "Relief teacher", "Remarks", "Set by"], rows[0]
        assert rows[1:] == [["2026-10-13", EVE, "1A Science", "P6–P7", "10:30–11:30", SAM, "'=HYPERLINK(\"http://x.test\")", GRACE],
                            ["2026-10-13", EVE, "5A Art", "P9", "12:00–12:30", "Not chosen yet", "'=HYPERLINK(\"http://x.test\")", GRACE],
                            ["2026-10-27", EVE, "1A Science", "P6–P7", "10:30–11:30", "Not chosen yet", "", EVE]], rows[1:]
        assert all(r[3] != "P9" for r in rows[1:] if r[0] == "2026-10-27"), "the cancelled one and the shared lesson nobody asked to cover are left out"
        for secret in ("Secret clinic visit", "Other", "Child sick", "Medical"): assert secret not in text, secret
        rows = list(csv.reader(io.StringIO(team.get("/api/relief/planned.csv?start=2026-11-10&end=2026-11-10").data.decode("utf-8").lstrip("﻿"))))
        assert [x[0] for x in rows[1:]] == ["2026-11-10"] and rows[1][6] == "Course" and rows[1][7] == TEAMER, rows
        assert len(list(csv.reader(io.StringIO(grace.get("/api/relief/planned.csv").data.decode("utf-8"))))) == 1, "today (12 Oct) has none"
        for bad in ("start=nope", "start=2026-10-27&end=2026-10-13", "end=13/10/2026"):
            no(grace.get("/api/relief/planned.csv?" + bad), 400, "Choose the dates again.")
        cancel_all(grace, a); cancel_all(eve, b); cancel_all(team, c)

@t
def an_unexpected_body_is_answered_plainly_and_logged():
    import logging
    from flask.logging import default_handler
    got = []
    class Keep(logging.Handler):
        def emit(self, record): got.append(record)
    keep, lg, old_ack = Keep(level=logging.ERROR), A.app.logger, AB.acknowledge
    lg.addHandler(keep); lg.removeHandler(default_handler)          # kept here, not printed over the test output
    try:
        with published(APUB):
            eve, grace = staff(EVE), staff(GRACE)
            before = files_in(ADIR)
            no(ask(eve, lessons=[dict(key=["x"])]), 400, AB.WRONG)
            assert files_in(ADIR) == before, "nothing written"
            assert len(got) == 1 and got[0].exc_info and got[0].exc_info[0] is TypeError, got
            assert "sending an absence" in got[0].getMessage(), got[0].getMessage()
            no(ask(eve, lessons=[dict(key="nope")]), 400, AB.CHANGED)
            assert len(got) == 1, "a refusal in plain words is not logged"
            i = ok(ask(grace))["id"]
            AB.acknowledge = lambda *a: {}["a bug"]
            no(eve.post(f"/api/relief/absences/{i}/acknowledge"), 400, AB.WRONG)
            assert len(got) == 2 and got[1].exc_info[0] is KeyError and "changing an absence" in got[1].getMessage(), got
            AB.acknowledge = old_ack
            cancel_all(grace, i)
    finally:
        AB.acknowledge = old_ack
        lg.removeHandler(keep); lg.addHandler(default_handler)

@t
def nothing_published_and_signed_out_answers():
    x = "abcdef123456"
    routes = [("GET", "/api/relief/lessons?dates=2026-10-13"), ("GET", f"/api/relief/free?absent={q(EVE)}&key={q(K5)}"), ("GET", "/api/relief/people"),
              ("POST", "/api/relief/absences"), ("GET", "/api/relief/absences/mine"), ("GET", "/api/relief/absences/planned"),
              ("GET", "/api/relief/absences"), ("POST", "/api/relief/absences/seen"), ("GET", f"/api/relief/absences/{x}"),
              ("POST", f"/api/relief/absences/{x}/acknowledge"), ("PUT", lesson_url(x, K5, "work")), ("POST", lesson_url(x, K5, "not-needed")),
              ("POST", lesson_url(x, K5, "needed")), ("PUT", lesson_url(x, K5, "relief")), ("POST", f"/api/relief/absences/{x}/cancel"),
              ("POST", f"/api/relief/absences/{x}/files"), ("GET", f"/api/relief/files/{x}/{x}"), ("GET", "/api/relief/planned.csv")]
    with published(APUB):
        team = staff(TEAMER)
        cm = committee()
        tc, r = signed_in("teacher", os.environ["TEACHER_CODE"]); assert r.status_code == 302
        left = A.app.test_client()
        with left.session_transaction() as s: s["role"], s["who"] = "staff", "Mr Left Lee"
        for method, url in routes:
            for c in (A.app.test_client(), cm, tc):
                no(c.open(url, method=method, json={}), 401, SIGN_IN)
        no(left.open(routes[2][1], method="GET"), 401, SIGN_IN)
        with left.session_transaction() as s: assert "role" not in s and "who" not in s, "the session of someone who left is ended"
    with published(None):
        for method, url in routes:
            no(team.open(url, method=method, json={}), 409, NO_PUB)
            no(A.app.test_client().open(url, method=method, json={}), 401, SIGN_IN)
    with published(APUB):
        assert ok(team.get("/api/relief/people")), "the session stayed while nothing was published"
    assert A.NO_RELIEF_PUB == NO_PUB

@t
def me_has_can_plan_and_can_team():
    with published(APUB):
        for name, plan, team in ((EVE, False, False), (GRACE, True, False), (TEAMER, True, True)):
            me = ok(staff(name).get("/api/relief/me"))
            assert (me["can_plan"], me["can_team"]) == (plan, team), (name, me)
        me = ok(staff(EVE).get("/api/relief/me"))
        assert set(me) == {"name", "depts", "on_team", "on_management", "can_settings", "can_plan", "can_team", "today"}, me
        assert me["today"] == "2026-10-12", "the school's date, from relief.lessons.today()"
        with A.app.test_request_context():
            _session["role"], _session["who"] = "staff", GRACE
            assert A.relief_has("relief") and A.relief_has("relief.plan") and not A.relief_has("relief.team")
            assert A.relief_has("relief.settings") and not A.relief_has("relief.save") and not A.relief_has("relief.nope")
            _session["who"] = TEAMER
            assert all(A.relief_has(r) for r in ("relief", "relief.plan", "relief.team", "relief.settings", "relief.save"))
            _session.clear(); _session["role"] = "committee"
            assert A.relief_has("relief.settings") and A.relief_has("relief.save")
            assert not any(A.relief_has(r) for r in ("relief", "relief.plan", "relief.team"))
            _session.clear()
            assert not any(A.relief_has(r) for r in ("relief", "relief.plan", "relief.team", "relief.settings", "relief.save"))
    from relief import web as W
    assert W._has is A.relief_has and W._me is A.me_staff and W._role is A.role
    assert "relief_web" in A.app.blueprints

# ---- final review fixes ----
from relief import web as RW  # noqa: E402
PAST_LESSON, PAST_ABSENCE = "This lesson is in the past.", "This absence is in the past."
K5_27 = K5.replace("2026-10-13", "2026-10-27")

def at(rec, p, date="2026-10-13"):
    return [x for x in rec["lessons"] if x["p"] == p and x["date"] == date][0]

@t
def a_shared_lesson_is_needed_when_the_others_are_away_too():
    # Eve first: Busy is there. Busy second: Eve is away, so Busy's half of the shared lesson is covered.
    eve = AB.new(data(), APUB, EVE, "asked")
    assert at(eve, 8)["needed"] is False and at(eve, 8)["not_needed"] == dict(by="app", why=f"{BUSY} is there") and at(eve, 8)["others"] == [BUSY]
    busy = AB.new(data(teacher=BUSY), APUB, BUSY, "asked")
    b8 = at(busy, 8)
    assert b8["needed"] is True and b8["not_needed"] is None and b8["others"] == [], b8
    assert at(AB.load(eve["id"]), 8)["not_needed"] == dict(by="app", why=f"{BUSY} is there"), "the earlier record is left as is"
    AB.cancel(eve["id"], "x", EVE); AB.cancel(busy["id"], "x", BUSY)
    # Busy first, Eve second; the page's lesson list says what new() will do
    busy = AB.new(data(teacher=BUSY), APUB, BUSY, "asked")
    assert at(busy, 8)["needed"] is False and at(busy, 8)["not_needed"] == dict(by="app", why=f"{EVE} is there")
    with published(APUB):
        got = ok(staff(EVE).get("/api/relief/lessons?dates=2026-10-13"))
        assert [(x["p"], x["others"]) for x in got["lessons"]] == [(5, []), (8, [])], got["lessons"]
    eve = AB.new(data(), APUB, EVE, "asked")
    assert at(eve, 8)["needed"] is True and at(eve, 8)["not_needed"] is None and at(eve, 8)["others"] == [], at(eve, 8)
    AB.cancel(busy["id"], "x", BUSY)
    with published(APUB):        # Busy's absence cancelled: he is there again
        got = ok(staff(GRACE).get(f"/api/relief/lessons?teacher={q(EVE)}&dates=2026-10-13"))
        assert [x["others"] for x in got["lessons"]] == [[], [BUSY]], got["lessons"]
    AB.cancel(eve["id"], "x", EVE)
    part = AB.new(data(teacher=BUSY, periods=[0, 6]), APUB, BUSY, "asked")      # away at other periods: still there for P9
    with published(APUB):
        assert [x["others"] for x in ok(staff(EVE).get("/api/relief/lessons?dates=2026-10-13"))["lessons"]] == [[], [BUSY]]
    AB.cancel(part["id"], "x", BUSY)

@t
def teaches_this_subject_means_the_same_subject_family():
    G2, ADD = "Ms Gee Two", "Mr Add Ma"
    rows = [dict(name=EVE, dept="Mathematics"), dict(name=G2, dept="Mathematics"), dict(name=ADD, dept="Mathematics")]
    pub = world(rows=rows, extra=[L(TUE, 3, 1, ["3A"], "Mathematics G3", [EVE]), L(FRI, 0, 1, ["3B"], "Mathematics G2", [G2]),
                                  L(FRI, 1, 1, ["3C"], "Additional Mathematics", [ADD])])
    ls = [x for x in LS.on_date(pub, CAL, EVE, D13) if x["subject"] == "Mathematics G3"][0]
    got = FR.free_then(pub, settings(), [], ls, EVE)
    assert [g["title"] for g in got["groups"]] == ["Mathematics · teaches Mathematics G3", "Mathematics · other subjects"], got["groups"]
    g = by_title(got)
    assert names(g["Mathematics · teaches Mathematics G3"]) == [G2] and names(g["Mathematics · other subjects"]) == [ADD], got
    assert g["Mathematics · teaches Mathematics G3"]["people"][0]["subjects"] == ["Mathematics G2"], "the person's own subjects are shown"

@t
def remarks_for_the_relief_team_are_not_shown_to_the_absent_teacher():
    with published(APUB):
        eve, grace, team = staff(EVE), staff(GRACE), staff(TEAMER)
        r = ok(ask(grace, remarks="Worksheets on the desk"))
        i, note = r["id"], "Worksheets on the desk"
        assert r["remarks"] == note
        mine = lambda: [x for x in ok(eve.get("/api/relief/absences/mine"))["absences"] if x["id"] == i][0]
        for got in (ok(eve.get(f"/api/relief/absences/{i}")), mine(), ok(eve.put(lesson_url(i, K5, "work"), json=wk("Read p.4"))),
                    ok(eve.post(f"/api/relief/absences/{i}/acknowledge")), ok(eve.post(lesson_url(i, K8, "needed")))):
            assert "remarks" not in got, got
        assert b"Worksheets" not in eve.get("/api/relief/absences/mine").data
        for c in (grace, team): assert ok(c.get(f"/api/relief/absences/{i}"))["remarks"] == note
        assert [x for x in ok(grace.get("/api/relief/absences/planned"))["absences"] if x["id"] == i][0]["remarks"] == note
        assert [x for x in ok(team.get("/api/relief/absences"))["absences"] if x["id"] == i][0]["remarks"] == note
        own = ok(ask(eve, dates=["2026-10-27"], remarks="My own note"))          # she sent it herself: she wrote them
        assert own["remarks"] == "My own note" and ok(eve.get(f"/api/relief/absences/{own['id']}"))["remarks"] == "My own note"
        assert "remarks" not in ok(eve.post(f"/api/relief/absences/{i}/cancel", json=dict(why="Better")))
        cancel_all(eve, own["id"])

@t
def a_past_lesson_is_not_checked_against_the_timetable():
    r = AB.new(data(dates=["2026-10-13", "2026-10-27"]), APUB, EVE, "asked")
    moved = world(rows=people_rows() + [dict(name=GRACE), dict(name=TEAMER)], extra=[L(TUE, 8, 1, ["5A"], "Art", [EVE, BUSY])])
    moved["model"]["lessons"] = [dict(x, p=6) if x["subject"] == "Science" else x for x in moved["model"]["lessons"]]
    calls, old_there, old_today = [], LS.still_there, LS.today
    LS.still_there = lambda pub, cal, who, x: calls.append(x["date"]) or old_there(pub, cal, who, x)
    try:
        LS.today = lambda: D(2026, 10, 14)
        got = AB.matches_now(r, moved, CAL)
        assert [(x["date"], x["p"], x["changed"]) for x in got["lessons"]] == [("2026-10-13", 5, False), ("2026-10-13", 8, False),
                                                                             ("2026-10-27", 5, True), ("2026-10-27", 8, False)], got["lessons"]
        assert calls == ["2026-10-27", "2026-10-27"], "lessons before today are not read again"
    finally: LS.still_there, LS.today = old_there, old_today
    assert [x["changed"] for x in AB.matches_now(r, moved, CAL)["lessons"]] == [True, False, True, False]
    AB.cancel(r["id"], "x", EVE)

@t
def the_relief_teams_right_to_change_comes_from_the_route():
    i = AB.new(data(), APUB, EVE, "asked")["id"]
    refuses("You cannot change this absence.", lambda: AB.cancel(i, "x", TEAMER))
    refuses("You cannot change this absence.", lambda: AB.not_needed(i, K5, "x", TEAMER))
    refuses("You cannot change this absence.", lambda: AB.needed_again(i, K8, TEAMER))
    AB.not_needed(i, K5, "Covered", TEAMER, team=True); AB.needed_again(i, K5, TEAMER, team=True)
    with published(APUB):
        team, old = staff(TEAMER), RW._has
        RW._has = lambda right: right != "relief.team" and old(right)     # has() says no: the settings' list alone does not let them
        try: no(team.post(f"/api/relief/absences/{i}/cancel", json=dict(why="x")), 400, "You cannot change this absence.")
        finally: RW._has = old
        assert ok(team.post(f"/api/relief/absences/{i}/cancel", json=dict(why="Tidy up")))["cancelled"]["by"] == TEAMER

@t
def a_work_save_keeps_files_someone_else_added_meanwhile():
    i = AB.new(data(), APUB, GRACE, "planned")["id"]
    f1 = FL.save(i, "one.pdf", b"1")
    AB.set_work(i, K5, wk(files=[f1]), EVE)
    f2 = FL.save(i, "two.pdf", b"2")
    AB.set_work(i, K5, wk(files=[f1, f2], known=[f1]), GRACE)         # Grace adds one while Eve's page still shows f1 alone
    AB.set_work(i, K5, wk("Read p.4", known=[f1]), EVE)                # Eve takes f1 off
    got = AB.load(i)["lessons"][0]["work"]
    assert got["text"] == "Read p.4" and [x["id"] for x in got["files"]] == [f2["id"]] and "known" not in got, got
    assert FL.path(i, f1["id"]) is None and FL.path(i, f2["id"]), "only the file Eve knew and took off is deleted"
    for bad in (dict(text="", link="", files=[]), dict(wk(), known="x"), dict(wk(), known=[1]), dict(wk(), files="x"), dict(wk(), files=None), None, [], "x"):
        refuses(AB.WRONG, lambda: AB.set_work(i, K5, bad, EVE))
    five = [FL.save(i, f"w{n}.pdf", b"x") for n in range(5)]
    refuses("A lesson can have at most 5 files.", lambda: AB.set_work(i, K5, wk(files=five), EVE))   # with f2, which Eve has not seen: six
    assert [x["id"] for x in AB.load(i)["lessons"][0]["work"]["files"]] == [f2["id"]] and FL.path(i, f2["id"])
    AB.cancel(i, "x", GRACE)

@t
def a_work_save_without_a_body_is_refused():
    with published(APUB):
        eve = staff(EVE)
        i = ok(ask(eve))["id"]
        fid = ok(upload(eve, i))["id"]
        ok(eve.put(lesson_url(i, K5, "work"), json=wk("Read p.4", files=[dict(id=fid, name="notes.pdf")])))
        kept = AB.load(i)
        for kw in (dict(), dict(data="nope", content_type="application/json"), dict(json=[]), dict(json={}),
                   dict(json=dict(text="", link="", files=[])), dict(json=dict(wk(), known=None))):
            no(eve.put(lesson_url(i, K5, "work"), **kw), 400, AB.WRONG)
        assert AB.load(i) == kept and FL.path(i, fid), "the work and its file are kept"
        cancel_all(eve, i)

@t
def a_long_file_name_keeps_its_extension():
    long = "Week 3 " + "n" * 120
    assert FL.clean_name(long + ".pdf") == long[:96] + ".pdf" and len(long[:96] + ".pdf") == 100
    assert FL.clean_name("short.pdf") == "short.pdf"
    i = AB.new(data(), APUB, EVE, "asked")["id"]
    f = FL.save(i, long + ".docx", b"PK")
    assert f["name"] == long[:95] + ".docx", f["name"]
    AB.set_work(i, K5, wk(files=[dict(f, name=long + ".html")]), EVE)
    assert AB.load(i)["lessons"][0]["work"]["files"][0]["name"] == long[:95] + ".docx"
    AB.cancel(i, "x", EVE)

@t
def the_sheet_names_the_group_only_when_it_is_not_the_whole_class():
    pub = world(rows=people_rows() + [dict(name=GRACE, dept="Mathematics"), dict(name=TEAMER, dept="Mathematics")],
                extra=[L(TUE, 8, 1, ["5A"], "Art", [EVE, BUSY]), L(TUE, 3, 1, ["1A"], "Art", [EVE], group="Entire Class"),
                       L(TUE, 10, 1, ["1B", "1A"], "Maths", [EVE], group="G1")])
    with published(pub):
        grace = staff(GRACE)
        i = ok(ask(grace))["id"]
        rows = list(csv.reader(io.StringIO(grace.get("/api/relief/planned.csv?start=2026-10-13").data.decode("utf-8").lstrip("﻿"))))
        assert [r[2] for r in rows[1:]] == ["1A Art", "1A Science", "1B, 1A Maths (G1)"], rows
        cancel_all(grace, i)

@t
def a_past_lesson_cannot_be_changed_but_can_be_acknowledged():
    i = AB.new(data(dates=["2026-10-13", "2026-10-27"]), APUB, GRACE, "planned")["id"]
    old = LS.today
    try:
        LS.today = lambda: D(2026, 10, 14)
        refuses(PAST_LESSON, lambda: AB.set_work(i, K5, wk("x"), EVE))
        refuses(PAST_LESSON, lambda: AB.not_needed(i, K5, "x", EVE))
        refuses(PAST_LESSON, lambda: AB.needed_again(i, K8, EVE))
        refuses(PAST_LESSON, lambda: AB.choose(i, K5, SAM, GRACE, APUB))
        refuses(PAST_LESSON, lambda: AB.choose(i, K5, None, GRACE, APUB))
        AB.set_work(i, K5_27, wk("Read p.4"), EVE)          # a lesson still to come can
        AB.choose(i, K5_27, SAM, GRACE, APUB)
        LS.today = lambda: D(2026, 10, 28)
        refuses(PAST_ABSENCE, lambda: AB.cancel(i, "x", GRACE))
        with published(APUB):
            eve, grace = staff(EVE), staff(GRACE)
            no(grace.post(f"/api/relief/absences/{i}/cancel", json=dict(why="x")), 400, PAST_ABSENCE)
            no(eve.put(lesson_url(i, K5_27, "work"), json=wk()), 400, PAST_LESSON)
            no(grace.put(lesson_url(i, K5_27, "relief"), json=dict(relief=None)), 400, PAST_LESSON)
            assert ok(eve.post(f"/api/relief/absences/{i}/acknowledge"))["acknowledged"]["at"], "acknowledging stays allowed"
        LS.today = lambda: D(2026, 10, 14)
        AB.cancel(i, "x", GRACE)                               # one date still to come: the absence can be cancelled
    finally: LS.today = old

@t
def the_pages_copy():
    inbox, page = (open(os.path.join(ROOT, "static", f)).read() for f in ("relief-inbox.js", "relief.js"))
    assert "The app's picks for open lessons, and approving them, come in the next stage." in inbox
    assert '"Earlier"' in inbox
    assert '"relief.ro:" + R.me.name' in page and 'getItem("relief.ro")' not in page
    assert "The app's picks for open lessons, and approving them, come in the next stage" in " ".join(open(os.path.join(ROOT, "README.md")).read().split())

print(f"{COUNT} relief request tests passed")

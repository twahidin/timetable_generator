"""Plain-assert tests for relief: .venv/bin/python tests/test_relief.py"""
import os, re, secrets, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = tempfile.mkdtemp()
KEY = secrets.token_hex(16)
os.environ.pop("HEADS_CODE", None)
os.environ.update(DATA_DIR=DATA, SECRET_KEY=KEY, AI_PROVIDER="anthropic", AI_API_KEY="", COMMITTEE_CODE=secrets.token_hex(4), TEACHER_CODE=secrets.token_hex(4), STUDENT_CODE=secrets.token_hex(4))
sys.path.insert(0, ROOT)
import app as A, access, store  # noqa: E402
from relief import people as P  # noqa: E402
from relief import calendar as C  # noqa: E402
from ttgen.spec import day_names  # noqa: E402
import datetime  # noqa: E402

COUNT = 0
def t(f):
    global COUNT
    f(); COUNT += 1
    return f

@t
def staff_code_is_stable_and_shaped():
    a = access.staff_code("Ms Evelyn Koh")
    assert a == access.staff_code("Ms Evelyn Koh")
    assert re.match(r"^[2-9A-HJ-KM-NP-Z]{4}-[2-9A-HJ-KM-NP-Z]{4}$", a), a
    assert a != access.staff_code("Mr Darren Lim")
    assert access.staff_code(" Ms Evelyn Koh ") == a
    assert access.staff_code("S0001") != access.personal_code("S0001")

@t
def staff_code_changes_with_secret_key():
    a = access.staff_code("Ms Evelyn Koh")
    os.environ["SECRET_KEY"] = secrets.token_hex(16)
    try: assert access.staff_code("Ms Evelyn Koh") != a
    finally: os.environ["SECRET_KEY"] = KEY

@t
def match_knows_staff_codes():
    code = access.staff_code("Ms Evelyn Koh")
    staff = {access.norm(code): "Ms Evelyn Koh"}
    assert access.match(code, {}, staff) == ("staff", "Ms Evelyn Koh")
    assert access.match(code.lower().replace("-", " "), {}, staff) == ("staff", "Ms Evelyn Koh")
    assert access.match("ZZZZ-ZZZZ", {}, staff) == (None, None)
    assert access.match(os.environ["TEACHER_CODE"], {}, staff) == ("teacher", None)

@t
def people_reads_the_published_setup():
    pub = P.fake_pub([dict(name="Ms Evelyn Koh", dept="Science", dept2="Mathematics", role="FAJT"), dict(name="Mr Darren Lim", dept="Science")],
                     lessons=[dict(teachers=["Mr Darren Lim"]), dict(teachers=["Mr Lesson Only"])])
    ps = {p["name"]: p for p in P.people(pub, [dict(name="Mdm Office Staff", note="admin")])}
    assert len(ps) == 4, list(ps)
    k = ps["Ms Evelyn Koh"]
    assert k["depts"] == ["Science", "Mathematics"] and k["role"] == "FAJT" and k["teaches"] is False
    assert ps["Mr Darren Lim"]["teaches"] is True
    assert "Mr Lesson Only" in ps
    assert ps["Mdm Office Staff"]["staff_only"] is True and ps["Mdm Office Staff"]["teaches"] is False
    assert [p["name"] for p in P.people(None, [dict(name="X", note="")])] == ["X"]

@t
def staff_codes_off_without_secret_key():
    ps = P.people(P.fake_pub([dict(name="Ms Evelyn Koh", dept="Science")]), [])
    assert P.staff_codes(ps) == {access.norm(access.staff_code("Ms Evelyn Koh")): "Ms Evelyn Koh"}
    del os.environ["SECRET_KEY"]
    try: assert P.staff_codes(ps) == {}
    finally: os.environ["SECRET_KEY"] = KEY

CAL = dict(terms=[dict(name="Term 4", start="2026-09-07", end="2026-11-20", starts_as="Odd")],
           holidays=[dict(start="2026-10-23", end="2026-10-23", name="Deepavali")])
TWO = day_names(2)
SCHOOL_TWO = ["Odd Mon", "Odd Tues", "Odd Wed", "Odd Thurs", "Odd Fri", "Even Mon", "Even Tues", "Even Wed", "Even Thurs", "Even Fri"]
D = datetime.date

@t
def school_day_counts_odd_and_even_weeks():
    assert C.school_day(CAL, TWO, D(2026, 9, 7)) == "Odd Mon"
    assert C.school_day(CAL, TWO, D(2026, 9, 14)) == "Even Mon"
    assert C.school_day(CAL, TWO, D(2026, 10, 13)) == "Even Tue"
    assert C.school_day(CAL, TWO, D(2026, 10, 12)) == "Even Mon"

@t
def school_day_is_none_off_school():
    assert C.school_day(CAL, TWO, D(2026, 10, 17)) is None
    assert C.school_day(CAL, TWO, D(2026, 10, 23)) is None
    assert C.school_day(CAL, TWO, D(2026, 11, 23)) is None
    assert C.school_day(CAL, TWO, D(2026, 9, 4)) is None

@t
def school_day_reads_the_schools_own_labels():
    assert C.school_day(CAL, SCHOOL_TWO, D(2026, 10, 13)) == "Even Tues"
    assert C.school_day(CAL, SCHOOL_TWO, D(2026, 10, 15)) == "Even Thurs"

@t
def school_day_one_week_timetable():
    assert C.school_day(CAL, ["Mon", "Tue", "Wed", "Thu", "Fri"], D(2026, 10, 13)) == "Tue"

@t
def term_starting_midweek_keeps_its_week():
    cal = dict(terms=[dict(name="T", start="2026-09-09", end="2026-11-20", starts_as="Odd")], holidays=[])
    assert C.school_day(cal, TWO, D(2026, 9, 11)) == "Odd Fri"
    assert C.school_day(cal, TWO, D(2026, 9, 14)) == "Even Mon"

@t
def term_of_and_week_of():
    assert C.term_of(CAL, D(2026, 10, 13))["name"] == "Term 4"
    assert C.term_of(CAL, D(2026, 12, 1)) is None
    assert C.week_of(D(2026, 10, 15)) == (D(2026, 10, 12), D(2026, 10, 16))

print(f"{COUNT} relief tests passed")

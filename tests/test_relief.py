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
from relief import settings as S  # noqa: E402
from ttgen.spec import day_names  # noqa: E402
import datetime  # noqa: E402

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
    names = [p["name"] for p in P.people(pub, [dict(name="Mdm Office Staff", note="")])]
    assert names.index("Mdm Office Staff") > names.index("Mr Darren Lim")

@t
def personal_code_is_pinned():
    os.environ["SECRET_KEY"] = "pinnedtestkey0123"
    try:
        assert access.personal_code("S0001") == "CBXX-98NB"
        assert access.staff_code("Ms Evelyn Koh") == "XUVD-7Q8J"
    finally: os.environ["SECRET_KEY"] = KEY

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

@t
def last_day_of_term_and_a_sunday_start():
    assert C.school_day(CAL, TWO, D(2026, 11, 20)) == "Odd Fri"
    cal = dict(terms=[dict(name="T", start="2026-09-06", end="2026-11-20", starts_as="Odd")], holidays=[])
    assert C.school_day(cal, TWO, D(2026, 9, 7)) == "Even Mon"
    assert C.school_day(cal, TWO, D(2026, 9, 4)) is None

# ---- settings
PUB = P.fake_pub([dict(name="Ms Evelyn Koh", dept="Science"), dict(name="Mr Darren Lim", dept="Science"), dict(name="Ms Grace Wong", dept="Mathematics")],
                 roles=[dict(role="FAJT", what="Flexible Adjunct Teacher (part-time)")])
TERM4 = dict(terms=[dict(name="Term 4", start="2026-09-07", end="2026-11-20", starts_as="Odd")], holidays=[dict(start="2026-10-23", end="2026-10-23", name="Deepavali")])

def fresh():
    if os.path.exists(S.PATH): os.remove(S.PATH)

def base(**kw):
    d = dict(management=[], team=[], extra_staff=[], calendar=TERM4)
    d.update(kw); return d

@t
def defaults_pick_the_adjunct_role_and_the_schools_rules():
    fresh()
    d = S.defaults(PUB)
    assert d["fat_role"] == "FAJT" and d["rules"] == S.DEFAULT_RULES and d["rules"] is not S.DEFAULT_RULES
    assert d["limits"] == dict(fat_per_day=3, other_per_day=None, never=[])
    assert d["times"] == dict(fill_at="15:00", remind_at="15:00", report_every=15, weekly_day="Fri", weekly_at="15:00")
    assert S.defaults(P.fake_pub([dict(name="A B")]))["fat_role"] == ""
    assert S.load(PUB)["saved_at"] is None

@t
def save_and_load_round_trip():
    fresh()
    out = S.save(base(management=["Ms Grace Wong"], team=["Mr Darren Lim", "Mdm Office Staff"], extra_staff=[dict(name="Mdm Office Staff", note="")]), PUB, "Timetable committee")
    assert out["management"] == ["Ms Grace Wong"] and out["team"] == ["Mr Darren Lim", "Mdm Office Staff"]
    assert out["calendar"] == TERM4 and out["saved_by"] == "Timetable committee" and out["saved_at"] and out["missing"] == []
    assert S.load(PUB) == out
    assert S.PATH.startswith(os.path.join(DATA, "relief"))
    assert os.path.exists(S.PATH)

@t
def save_refuses_with_one_plain_sentence():
    fresh()
    def bad(text, **kw):
        raises(ValueError, lambda: S.save(base(**kw), PUB, "x"), text)
    bad("Ms Nobody is not on the published timetable or the staff list.", team=["Ms Nobody"])
    bad("Ms Nobody is not on the published timetable or the staff list.", management=["Ms Nobody"])
    bad("Ms Nobody is not on the published timetable or the staff list.", limits=dict(never=["Ms Nobody"]))
    bad("A staff member needs a name.", extra_staff=[dict(name=" ", note="")])
    bad("Mdm Office Staff is on the staff list twice.", extra_staff=[dict(name="Mdm Office Staff"), dict(name="Mdm Office Staff")])
    bad("Ms Grace Wong is already a teacher on the timetable.", extra_staff=[dict(name="Ms Grace Wong")])
    bad("There is no role Boss on step 4.", fat_role="Boss")
    long_rule = "Keep each rule under 300 characters, at most 20 rules, none empty."
    bad(long_rule, rules=["x"] * 21)
    bad(long_rule, rules=["ok", "  "])
    bad(long_rule, rules=["x" * 301])
    lim = "A daily limit is a whole number from 1 to 20, or empty."
    bad(lim, limits=dict(fat_per_day=0)); bad(lim, limits=dict(other_per_day=21)); bad(lim, limits=dict(fat_per_day="3x")); bad(lim, limits=dict(fat_per_day=True))
    bad("25:00 is not a time like 15:00.", times=dict(fill_at="25:00"))
    bad("3pm is not a time like 15:00.", times=dict(weekly_at="3pm"))
    bad("Report every 5 to 60 minutes.", times=dict(report_every=4)); bad("Report every 5 to 60 minutes.", times=dict(report_every=61))
    bad("The weekly summary goes out on a weekday.", times=dict(weekly_day="Sat"))
    bad("Check the dates of Term 4.", calendar=dict(terms=[dict(name="Term 4", start="2026-13-01", end="2026-11-20", starts_as="Odd")], holidays=[]))
    bad("Check the dates of Term 4.", calendar=dict(terms=[dict(name="Term 4", start="2026-11-20", end="2026-09-07", starts_as="Odd")], holidays=[]))
    bad("Check the dates of Term 4.", calendar=dict(terms=[dict(name="Term 3", start="2026-07-01", end="2026-09-10", starts_as="Odd"), dict(name="Term 4", start="2026-09-07", end="2026-11-20", starts_as="Odd")], holidays=[]))
    bad("Check the dates of .", calendar=dict(terms=[dict(name="", start="2026-09-07", end="2026-11-20", starts_as="Odd")], holidays=[]))
    bad("Say whether Term 4 starts in an Odd or an Even week.", calendar=dict(terms=[dict(name="Term 4", start="2026-09-07", end="2026-11-20")], holidays=[]))
    bad("Check the dates of Deepavali.", calendar=dict(terms=[], holidays=[dict(name="Deepavali", start="2026-10-23", end="2026-10-22")]))
    bad("Check the dates of Deepavali.", calendar=dict(terms=[], holidays=[dict(name="Deepavali", start="soon", end="2026-10-22")]))
    assert not os.path.exists(S.PATH)
    S.save(base(limits=dict(fat_per_day=None, other_per_day=5), fat_role="", extra_staff=[dict(name="Mdm Office Staff")], team=["Mdm Office Staff"], bogus=1), PUB, "x")
    got = S.load(PUB)
    assert got["limits"]["fat_per_day"] is None and got["limits"]["other_per_day"] == 5 and "bogus" not in got

@t
def a_name_gone_from_the_timetable_is_missing_not_fatal():
    fresh()
    S.save(base(team=["Mr Darren Lim"]), PUB, "x")
    pub2 = P.fake_pub([dict(name="Ms Evelyn Koh", dept="Science")])
    got = S.load(pub2)
    assert got["team"] == [] and got["missing"] == ["Mr Darren Lim"]
    assert store.read_json(S.PATH)["team"] == ["Mr Darren Lim"]

print(f"{COUNT} relief tests passed")

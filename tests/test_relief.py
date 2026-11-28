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
    d = dict(calendar=TERM4)
    d.update(kw); return d

@t
def defaults_pick_the_adjunct_role_and_the_schools_rules():
    fresh()
    d = S.defaults(PUB)
    assert d["fat_role"] == "FAJT" and d["rules"] == S.DEFAULT_RULES and d["rules"] is not S.DEFAULT_RULES
    assert d["limits"] == dict(fat_per_day=3, other_per_day=None, never=[])
    assert d["times"] == dict(remind_at="15:00", report_every=15, weekly_day="Fri", weekly_at="15:00", morning_at="06:30", send_from="06:45", cut_off="14:00", work_eve="18:00", work_day="07:00")
    assert S.defaults(P.fake_pub([dict(name="A B")]))["fat_role"] == ""
    assert S.load(PUB)["saved_at"] is None

@t
def save_and_load_round_trip():
    fresh()
    out = S.save(base(limits=dict(never=["Ms Grace Wong"])), PUB, "Timetable committee")
    assert out["limits"]["never"] == ["Ms Grace Wong"] and not {"management", "team", "extra_staff"} & set(out)
    assert out["calendar"] == TERM4 and out["saved_by"] == "Timetable committee" and out["saved_at"] and out["missing"] == []
    assert S.load(PUB) == out
    assert S.PATH.startswith(os.path.join(DATA, "relief"))
    assert os.path.exists(S.PATH)

@t
def save_refuses_with_one_plain_sentence():
    fresh()
    def bad(text, **kw):
        raises(ValueError, lambda: S.save(base(**kw), PUB, "x"), text)
    bad("Ms Nobody is not on the published timetable or the staff list.", limits=dict(never=["Ms Nobody"]))
    bad("There is no role Boss on step 4.", fat_role="Boss")
    long_rule = "Keep each rule under 300 characters, at most 20 rules, none empty."
    bad(long_rule, rules=["x"] * 21)
    bad(long_rule, rules=["ok", "  "])
    bad(long_rule, rules=["x" * 301])
    lim = "A daily limit is a whole number from 1 to 20, or empty."
    bad(lim, limits=dict(fat_per_day=0)); bad(lim, limits=dict(other_per_day=21)); bad(lim, limits=dict(fat_per_day="3x")); bad(lim, limits=dict(fat_per_day=True))
    bad("25:00 is not a time like 15:00.", times=dict(cut_off="25:00"))
    bad("3pm is not a time like 15:00.", times=dict(weekly_at="3pm"))
    bad("Report every 5 to 60 minutes.", times=dict(report_every=4)); bad("Report every 5 to 60 minutes.", times=dict(report_every=61))
    bad("The weekly summary goes out on a weekday.", times=dict(weekly_day="Sat"))
    bad("Check the dates of Term 4.", calendar=dict(terms=[dict(name="Term 4", start="2026-13-01", end="2026-11-20", starts_as="Odd")], holidays=[]))
    bad("Check the dates of Term 4.", calendar=dict(terms=[dict(name="Term 4", start="2026-11-20", end="2026-09-07", starts_as="Odd")], holidays=[]))
    bad("Check the dates of Term 4.", calendar=dict(terms=[dict(name="Term 3", start="2026-07-01", end="2026-09-10", starts_as="Odd"), dict(name="Term 4", start="2026-09-07", end="2026-11-20", starts_as="Odd")], holidays=[]))
    bad("Give each term and holiday a name.", calendar=dict(terms=[dict(name="", start="2026-09-07", end="2026-11-20", starts_as="Odd")], holidays=[]))
    bad("Say whether Term 4 starts in an Odd or an Even week.", calendar=dict(terms=[dict(name="Term 4", start="2026-09-07", end="2026-11-20")], holidays=[]))
    bad("Check the dates of Deepavali.", calendar=dict(terms=[], holidays=[dict(name="Deepavali", start="2026-10-23", end="2026-10-22")]))
    bad("Check the dates of Deepavali.", calendar=dict(terms=[], holidays=[dict(name="Deepavali", start="soon", end="2026-10-22")]))
    assert not os.path.exists(S.PATH)
    S.save(base(limits=dict(fat_per_day=None, other_per_day=5), fat_role="", bogus=1), PUB, "x")
    got = S.load(PUB)
    assert got["limits"]["fat_per_day"] is None and got["limits"]["other_per_day"] == 5 and "bogus" not in got

@t
def a_name_gone_from_the_timetable_is_missing_not_fatal():
    fresh()
    S.save(base(limits=dict(never=["Mr Darren Lim"])), PUB, "x")
    pub2 = P.fake_pub([dict(name="Ms Evelyn Koh", dept="Science")])
    got = S.load(pub2)
    assert got["limits"]["never"] == [] and got["missing"] == ["Mr Darren Lim"]
    assert store.read_json(S.PATH)["limits"]["never"] == ["Mr Darren Lim"]

UNREAD = "The settings could not be read. Reload the page and try again."
NAMELESS = "Give each term and holiday a name."

@t
def save_refuses_the_wrong_json_types():
    fresh()
    for new in ([], None, "settings", 5):
        raises(ValueError, lambda: S.save(new, PUB, "x"), UNREAD)
    cases = [dict(rules="Use planned relief first."),
             dict(rules=None), dict(rules=[["x"]]), dict(limits=[["fat_per_day", 3]]), dict(limits=None), dict(limits=dict(never="Ms Grace Wong")),
             dict(limits=dict(never=None)), dict(times=[]), dict(times=None), dict(calendar=[]), dict(calendar=None), dict(calendar=dict(terms=["Term 4"], holidays=[])),
             dict(calendar=dict(terms=None, holidays=[])), dict(calendar=dict(terms=[], holidays=[["Deepavali"]])), dict(calendar=dict(terms=[], holidays=None)),
             dict(fat_role=["FAJT"]), dict(calendar=dict(terms=[dict(name=["Term 4"], start="2026-09-07", end="2026-11-20", starts_as="Odd")], holidays=[]))]
    for kw in cases:
        raises(ValueError, lambda: S.save(base(**kw), PUB, "x"), UNREAD)
    assert not os.path.exists(S.PATH)
    S.save(base(fat_role=None, limits=dict(other_per_day=None)), PUB, "x")       # an empty value is not a wrong type
    assert S.load(PUB)["fat_role"] == ""
    S.save(base(team=None, management="Ms Grace Wong", extra_staff=["junk"]), PUB, "x")       # the old lists are ignored, whatever they hold

@t
def a_term_or_holiday_needs_a_name_before_its_dates():
    fresh()
    for cal in (dict(terms=[dict(name=" ", start="soon", end="later", starts_as="Odd")], holidays=[]),
                dict(terms=[dict(start="2026-09-07", end="2026-11-20", starts_as="Odd")], holidays=[]),
                dict(terms=[], holidays=[dict(name="", start="2026-10-23", end="2026-10-23")]),
                dict(terms=[], holidays=[dict(name=None, start="bad", end="")])):
        raises(ValueError, lambda: S.save(base(calendar=cal), PUB, "x"), NAMELESS)

# ---- signing in as a person (one box for every code), and the relief routes
import contextlib, csv, io  # noqa: E402
from relief import codes as RC  # noqa: E402
from accounts import people as AP  # noqa: E402

@contextlib.contextmanager
def published(pub):
    old = store.published; store.published = lambda: pub
    try: yield
    finally: store.published = old

def signed_in(code):
    c = A.app.test_client()
    r = c.post("/login", data={"code": code})
    return c, r

def committee():
    c, r = signed_in(os.environ["COMMITTEE_CODE"]); assert r.status_code == 302
    return c

def staff(name):
    c, r = signed_in(access.staff_code(name)); assert r.status_code == 302, (name, r.status_code)
    return c

SETTINGS_DENIED = "Only the timetable committee and the relief team can change relief settings."
AGAIN = {"error": "Please sign in again."}
NOT_PUBLISHED = "Publish the timetable first: relief reads the teachers from it."

@t
def the_front_page_is_one_box_for_every_code():
    c = A.app.test_client()
    with published(PUB):
        front = c.get("/login").data
        assert b"Your code (the one the school gave you)" in front and front.count(b'name="code"') == 1 and b'class="choice' not in front
        assert c.get("/login?as=relief").data == front                 # the old cards' links still open the page
        assert not hasattr(A, "CHOICES")

@t
def a_staff_code_signs_in_as_that_person():
    fresh()
    with published(PUB):
        c, r = signed_in(access.staff_code("Mr Darren Lim"))
        assert r.status_code == 302 and r.headers["Location"].endswith("/home"), r.headers.get("Location")
        with c.session_transaction() as s: assert s["who"] == "Mr Darren Lim" and s["via"] == "code" and "role" not in s
        me = c.get("/api/relief/me").get_json()
        assert me == dict(name="Mr Darren Lim", depts=["Science"], published=True, on_team=False, on_management=False, can_settings=False,
                          can_plan=False, can_team=False, today=A.relief_lessons.today().isoformat()), me
        r = c.get("/"); assert r.status_code == 302 and r.headers["Location"].endswith("/home")   # a person's front door: their tiles
        with A.app.test_request_context():
            A.session["role"], A.session["who"] = "staff", "Mr Darren Lim"
            p = A.who(); assert p["name"] == "Mr Darren Lim" and p["depts"] == ["Science"], p
            A.session["who"] = "Ms Nobody"; A.g.pop("_signed", None)
            assert A.who() is None and "role" not in A.session and "who" not in A.session
            A.session["role"] = "teacher"; A.g.pop("_signed", None); assert A.who() is None and A.session["role"] == "teacher"
    bad, r = signed_in("ZZZZ-ZZZZ"); assert r.status_code == 401

def timetable_pub(pub):
    """a fake published timetable the teacher routes can answer from: no classes, and the teacher page already made"""
    import copy
    pub = copy.deepcopy(pub); pub["model"].update(class_ix={}, teacher_ix={}, room_ix={}, students=[])
    pub["views"][("view", "teacher", None)] = "the teacher page"
    pub["views"][("view", "teacher", "/home")] = "the person page"    # the teacher's page with the way back to the tiles
    pub["views"][("view", "teacher", "/relief")] = "the staff page"   # ...and to Relief, for a relief stage 1 session
    return pub

TPUB = timetable_pub(PUB)

@t
def a_staff_code_opens_the_teachers_timetable():
    with published(TPUB):
        c, r = signed_in(access.staff_code("Mr Darren Lim"))
        assert r.status_code == 302 and r.headers["Location"].endswith("/home"), r.headers.get("Location")
        assert c.get("/api/relief/me").get_json()["name"] == "Mr Darren Lim"
        c2 = A.app.test_client()                                      # a page still sending an old card's choice: the choice is ignored
        r = c2.post("/login", data={"as": "student", "code": access.staff_code("Mr Darren Lim")})
        assert r.status_code == 302 and r.headers["Location"].endswith("/home") and c2.get("/api/relief/me").get_json()["name"] == "Mr Darren Lim"
        # treated as a teacher: the teacher's page and files, not the committee's
        r = c.get("/timetable"); assert r.status_code == 200 and r.data == b"the person page"
        assert c.get("/pdf/custom?cls=1A").status_code == 404 and c.get("/pdf/classes/1A").status_code == 404
        assert c.get("/files/book/classes").status_code == 404 and c.get("/files/excel").status_code == 403
        with c.session_transaction() as s: assert s["who"] == "Mr Darren Lim"

@t
def a_dropped_teacher_loses_the_teacher_routes_too():
    fresh()
    with published(TPUB): a, b, d = (staff("Mr Darren Lim") for _ in range(3))
    with published(timetable_pub(P.fake_pub([dict(name="Ms Evelyn Koh", dept="Science")]))):
        r = a.get("/timetable"); assert r.status_code == 200 and b"Code no longer valid" in r.data and b"the teacher page" not in r.data
        r = b.get("/pdf/classes/1A"); assert r.status_code == 401 and r.get_json() == {"error": "Please sign in again."}
        r = d.get("/files/book/classes"); assert r.status_code == 401 and r.get_json() == {"error": "Please sign in again."}
        for x in (a, b, d):
            with x.session_transaction() as s: assert "role" not in s and "who" not in s
    with published(None):   # nothing published (a publish is swapping folders): "Not published yet", the session survives
        e = A.app.test_client()
        with e.session_transaction() as s: s["role"], s["who"] = "staff", "Mr Darren Lim"
        r = e.get("/timetable"); assert r.status_code == 200 and b"Not published yet" in r.data and b"Code no longer valid" not in r.data
        r = e.get("/pdf/classes/1A"); assert r.status_code == 404                      # nothing to print yet
        r = e.get("/api/relief/me"); assert r.status_code == 200 and r.get_json()["name"] == "Mr Darren Lim" and r.get_json()["published"] is False and r.get_json()["depts"] == []
        with e.session_transaction() as s: assert s["role"] == "staff" and s["who"] == "Mr Darren Lim"

@t
def the_relief_home_is_the_staff_page():
    with published(PUB):
        c = staff("Mr Darren Lim")
        r = c.get("/relief"); assert r.status_code == 200 and b"/static/relief.js" in r.data and b"Relief settings" in r.data, r.status_code; r.close()
    assert all(os.path.exists(os.path.join(ROOT, "static", f)) for f in ("relief.html", "relief.js", "relief-settings.html", "relief-settings.js"))

@t
def staff_on_the_timetable_get_the_way_back_to_their_tiles():
    import copy
    from ttgen import export as E
    seen = []
    def fake_render(model, view, app=None): seen.append(app); return f"page {len(seen)}"
    old, E.render_html = E.render_html, fake_render
    pub = copy.deepcopy(PUB); pub["views"] = {}
    try:
        with published(pub):
            s, (tc, _), r1 = staff("Mr Darren Lim"), signed_in(os.environ["TEACHER_CODE"]), A.app.test_client()
            with r1.session_transaction() as x: x["role"], x["who"] = "staff", "Mr Darren Lim"   # a relief stage 1 session
            assert s.get("/timetable").data == b"page 1" and tc.get("/timetable").data == b"page 2" and r1.get("/timetable").data == b"page 3"
            assert s.get("/timetable").data == b"page 1" and tc.get("/timetable").data == b"page 2" and r1.get("/timetable").data == b"page 3"
            assert len(seen) == 3                                                    # each kept, apart
    finally: E.render_html = old
    assert seen[0]["home"] == "/home" and seen[0]["homeLabel"] == "Home" and seen[0]["mode"] == "teacher", seen[0]
    assert seen[1]["home"] is None and seen[1]["mode"] == "teacher" and seen[0]["tabs"] == seen[1]["tabs"], seen[1]
    assert seen[2]["home"] == "/relief" and seen[2]["homeLabel"] == "Relief" and seen[2]["mode"] == "teacher", seen[2]
    assert set(pub["views"]) == {("view", "teacher", "/home"), ("view", "teacher", None), ("view", "teacher", "/relief")}, list(pub["views"])

@t
def a_teacher_code_sent_from_the_old_relief_card_opens_the_timetable():
    with published(PUB):
        c = A.app.test_client()
        r = c.post("/login", data={"as": "relief", "code": os.environ["TEACHER_CODE"]})   # the choice is ignored: the code decides
        assert r.status_code == 302 and r.headers["Location"].endswith("/timetable"), r.status_code
        with c.session_transaction() as s: assert s["role"] == "teacher" and "who" not in s
        assert c.get("/api/relief/me").status_code == 401                # the shared teacher code is nobody's: no relief page

@t
def a_staff_session_cannot_reach_committee_routes():
    with published(PUB):
        c = staff("Mr Darren Lim")
        assert c.get("/").headers["Location"].endswith("/home")
        for method, url in (("GET", "/api/setup"), ("PUT", "/api/setup"), ("GET", "/api/draft"), ("POST", "/api/draft"), ("GET", "/api/codes.csv"),
                            ("GET", "/api/code-slips.pdf"), ("GET", "/api/status"), ("POST", "/api/setup/changes"), ("GET", "/draft/preview")):
            r = c.open(url, method=method)
            assert r.status_code in (302, 401), (url, r.status_code)
            if r.status_code == 302: assert r.headers["Location"].endswith("/login"), url

@t
def a_dropped_teacher_is_signed_out():
    fresh()
    with published(PUB): c = staff("Mr Darren Lim")
    with published(P.fake_pub([dict(name="Ms Evelyn Koh", dept="Science")])):
        r = c.get("/relief")
        assert b"Code no longer valid" in r.data and b"Ask the timetable committee for your code." in r.data
        with c.session_transaction() as s: assert "who" not in s and "role" not in s
        assert c.get("/api/relief/me").status_code == 401

def settings_rights_by_the_accounts():
    with published(PUB):
        com = committee()
        r = com.get("/relief"); assert r.status_code == 302 and r.headers["Location"].endswith("/relief/settings")
        r = com.put("/api/relief/settings", json=base(team=["Ms Evelyn Koh"], management=["Ms Evelyn Koh"], extra_staff=[dict(name="Mr Sent Anyway")]))
        assert r.status_code == 200, r.get_json()
        j = com.get("/api/relief/settings").get_json()
        assert set(j) == {"settings", "lists", "can_admin", "people", "roles", "weeks", "can_save", "can_codes"}, list(j)
        assert j["lists"] == dict(management=["Ms Grace Wong"], team=["Mr Darren Lim"], added=[]) and j["can_admin"] is False, j["lists"]
        assert not {"management", "team", "extra_staff"} & set(j["settings"]) and "Mr Sent Anyway" not in str(j["people"])
        assert j["can_save"] is True and j["can_codes"] is True and j["roles"] == ["FAJT"] and j["weeks"] == 2
        assert j["settings"]["saved_by"] == "Timetable committee"
        assert [p["name"] for p in j["people"]] == [p["name"] for p in P.people(PUB, [])]
        team, mgmt, plain = staff("Mr Darren Lim"), staff("Ms Grace Wong"), staff("Ms Evelyn Koh")
        assert team.get("/api/relief/me").get_json()["can_settings"] is True and team.get("/api/relief/me").get_json()["on_team"] is True
        m = mgmt.get("/api/relief/me").get_json(); assert m["on_management"] is True and m["can_settings"] is False
        j = team.get("/api/relief/settings").get_json(); assert j["can_save"] is True and j["can_codes"] is False
        r = team.put("/api/relief/settings", json=base(rules=["Use planned relief first."]))
        assert r.status_code == 200 and r.get_json()["settings"]["saved_by"] == "Mr Darren Lim", r.get_json()
        assert S.load(PUB)["saved_by"] == "Mr Darren Lim" and S.load(PUB)["rules"] == ["Use planned relief first."]
        j = mgmt.get("/api/relief/settings"); assert j.status_code == 200 and j.get_json()["can_save"] is False
        r = mgmt.put("/api/relief/settings", json=base(rules=["x"])); assert r.status_code == 401 and r.get_json() == AGAIN   # a leader may read, not save
        assert S.load(PUB)["rules"] == ["Use planned relief first."]
        for url in ("/api/relief/settings",):                               # a teacher without the Relief team extra: refused by the guard
            assert plain.get(url).status_code == 401 and plain.put(url, json=base()).status_code == 401 and plain.get(url).get_json() == AGAIN
        r = plain.get("/relief/settings"); assert r.status_code == 302 and r.headers["Location"].endswith("/login")
        r = mgmt.get("/relief/settings"); assert r.status_code == 403 and SETTINGS_DENIED.encode() in r.data
        for x in (team, com):
            r = x.get("/relief/settings"); assert r.status_code == 200 and b"/static/relief-settings.js" in r.data, r.status_code; r.close()
        r = team.get("/relief"); assert r.status_code == 200 and b"/static/relief.js" in r.data, r.status_code; r.close()
        tc, _ = signed_in(os.environ["TEACHER_CODE"])
        assert tc.get("/api/relief/settings").status_code == 401 and tc.put("/api/relief/settings", json=base()).status_code == 401
        assert tc.get("/relief/settings").headers["Location"].endswith("/login") and tc.get("/api/relief/me").status_code == 401
        # a refused save is a sentence (400), never a server error
        r = com.put("/api/relief/settings", json=base(limits=dict(never=["Ms Nobody"]))); assert r.status_code == 400 and r.get_json()["error"] == "Ms Nobody is not on the published timetable or the staff list."
        for body in ([], "x", dict(limits=None), dict(calendar=dict(terms=["Term 4"]))):
            r = com.put("/api/relief/settings", json=body); assert r.status_code == 400 and r.get_json()["error"] == UNREAD, (body, r.status_code)
        r = com.put("/api/relief/settings", data="not json", content_type="application/json"); assert r.status_code == 400 and r.get_json()["error"] == UNREAD
        r = com.put("/api/relief/settings", json=base(calendar=dict(terms=[dict(name="", start="2026-09-07", end="2026-11-20", starts_as="Odd")], holidays=[])))
        assert r.status_code == 400 and r.get_json()["error"] == NAMELESS

@t
def settings_rights():
    fresh()
    # the lists come from the accounts: relief's old lists move there (Management a school leader, the team the Relief team extra)
    AP.update(lambda d: d.update(migrated=False, moved=None))
    store.write_json(S.PATH, dict(management=["Ms Grace Wong"], team=["Mr Darren Lim"], extra_staff=[]))
    assert AP.migrate(PUB, store.read_json(S.PATH)) is not None
    try: settings_rights_by_the_accounts()
    finally: AP.update(lambda d: (d["people"].pop("Mr Darren Lim"), d["people"].pop("Ms Grace Wong")))

@t
def a_relief_team_extra_alone_may_save_and_a_leader_only_read():
    fresh()
    AP.update(lambda d: (d["people"].update({"Ms Evelyn Koh": dict(extras=dict(relief=True, exams=None, admin=False))}), d["people"].update({"Mr Darren Lim": dict(group="leader")})))
    try:
        with published(PUB):
            team, lead = staff("Ms Evelyn Koh"), staff("Mr Darren Lim")           # no entry in relief's own lists
            assert team.put("/api/relief/settings", json=base(rules=["A rule."])).status_code == 200
            assert S.load(PUB)["rules"] == ["A rule."]
            assert lead.get("/api/relief/settings").status_code == 200
            assert lead.put("/api/relief/settings", json=base()).status_code == 401
            assert team.get("/api/relief/me").get_json() == dict(name="Ms Evelyn Koh", depts=["Science"], published=True, on_team=True, on_management=False, can_settings=True,
                                                                     can_plan=True, can_team=True, today=A.relief_lessons.today().isoformat())   # R16: the Relief team extra plans too
            assert lead.get("/api/relief/me").get_json() == dict(name="Mr Darren Lim", depts=["Science"], published=True, on_team=False, on_management=True, can_settings=False,
                                                                     can_plan=True, can_team=False, today=A.relief_lessons.today().isoformat())
    finally: AP.update(lambda d: (d["people"].pop("Ms Evelyn Koh"), d["people"].pop("Mr Darren Lim")))
    fresh()

@t
def relief_me_answers_a_strong_person():
    from werkzeug.security import generate_password_hash
    fresh()
    pw = generate_password_hash(secrets.token_hex(8))   # a password session ends when its record holds no password
    AP.update(lambda d: d["people"].update({"Mr Hod One": dict(group="hod", depts=["Science"], username="hod.one", pw=pw), "Ms Com One": dict(username="com.one", pw=pw, extras=dict(timetable=True, relief=False, exams=None, admin=False))}))   # on the Timetable committee
    try:
        for name, group in (("Mr Hod One", "hod"), ("Ms Com One", "committee")):
            c = A.app.test_client()
            with published(PUB):
                with c.session_transaction() as x: x.update(who=name, via="password", exp=9e9, n=0)
                r = c.get("/api/relief/me"); j = r.get_json()
                assert r.status_code == 200 and j["name"] == name and j["on_team"] is False and j["on_management"] is (group == "hod"), (name, r.status_code, j)
                assert j["can_settings"] is (group == "committee")
    finally: AP.update(lambda d: (d["people"].pop("Mr Hod One"), d["people"].pop("Ms Com One")))

# ---- relief's own lists move into the accounts, once
def _reset():
    AP.update(lambda d: d.update(people={}, migrated=False, moved=None))

@t
def migrate_from_relief():
    import history
    pub = P.fake_pub([dict(name="Mr Hod Wong", dept="Science", dept2="Mathematics", role="HOD"), dict(name="Ms Sh Tan", dept="Art", role="sh "),
                      dict(name="Ms Plain Lee", dept="Art", role="Teacher"), dict(name="Mr Team Ong", dept="Art")])
    _reset()
    raw = dict(management=["Mr Hod Wong", "Ms Sh Tan", "Ms Plain Lee", "Mdm Office Staff"], team=["Mr Team Ong", "Mr Hod Wong"],
               extra_staff=[dict(name="Mdm Office Staff", note="front desk"), dict(name="Mr Driver", note="")])
    n0 = len(history.read(kinds=['account']))
    lines = AP.migrate(pub, raw)
    assert "Mr Hod Wong: HOD (from relief's Management list)" in lines, lines
    d = AP.load()
    r = lambda n: AP.record(d, n)
    assert r("Mr Hod Wong")["group"] == "hod" and r("Mr Hod Wong")["depts"] == ["Science", "Mathematics"] and r("Mr Hod Wong")["extras"]["relief"] is True
    assert r("Ms Sh Tan")["group"] == "sh" and r("Ms Sh Tan")["depts"] == ["Art"]
    assert r("Ms Plain Lee")["group"] == "leader" and r("Ms Plain Lee")["depts"] == []
    assert r("Mdm Office Staff")["group"] == "leader" and r("Mdm Office Staff")["added"] is True and r("Mdm Office Staff")["note"] == "front desk"
    assert r("Mr Driver")["group"] == "executive" and r("Mr Driver")["added"] is True
    assert r("Mr Team Ong")["extras"]["relief"] is True and r("Mr Team Ong")["group"] is None
    assert d["migrated"] is True and d["moved"] == lines and len(lines) == 8, lines
    assert AP.migrate(pub, raw) is None and AP.load()["moved"] == lines                    # a second call does nothing
    got = history.read(kinds=["account"]); assert len(got) == n0 + 1, (n0, len(got))
    e = got[0]; assert e["what"] == "moved" and e["text"] == "Moved from relief's lists" and (e["who"], e["as"], e["via"]) == (None, "The app", "app")
    assert set(e["people"]) == {"Mr Hod Wong", "Ms Sh Tan", "Ms Plain Lee", "Mdm Office Staff", "Mr Driver", "Mr Team Ong"}
    _reset()
    assert AP.migrate(pub, dict(management=[], team=[], extra_staff=[])) is None and AP.load()["migrated"] is True and AP.load()["moved"] == []
    _reset()
    assert AP.migrate(None, dict(management=["Mr Hod Wong"])) is None and AP.load()["migrated"] is False      # no published timetable yet: later
    assert AP.migrate(None, dict(team=["Mr Team Ong"])) == ["Mr Team Ong: Relief team (from relief's Team list)"]
    _reset()

@t
def the_routes_move_the_lists_once_and_keep_the_old_file():
    fresh(); _reset()
    store.write_json(S.PATH, dict(management=["Ms Grace Wong"], team=["Mr Darren Lim"], extra_staff=[dict(name="Mdm Office Staff", note="")], rules=["Old rule."]))
    with published(PUB):
        com = committee()
        j = com.get("/api/relief/settings").get_json()
        assert j["lists"] == dict(management=["Ms Grace Wong"], team=["Mr Darren Lim"], added=["Mdm Office Staff"]), j["lists"]
        assert [p["name"] for p in j["people"]][-1] == "Mdm Office Staff"
        assert com.put("/api/relief/settings", json=base(rules=["New rule."])).status_code == 200
        kept = store.read_json(S.PATH)
        assert kept["management"] == ["Ms Grace Wong"] and kept["team"] == ["Mr Darren Lim"] and kept["extra_staff"] == [dict(name="Mdm Office Staff", note="")] and kept["rules"] == ["New rule."]
        AP.update(lambda d: d["people"].pop("Mdm Office Staff"))
        assert A.move_relief_lists() is None                                                     # done once; not done again
        assert com.get("/api/relief/settings").get_json()["lists"]["added"] == []
    _reset(); fresh()

@t
def the_relief_home_moves_the_lists_too():
    fresh(); _reset()
    store.write_json(S.PATH, dict(team=["Mr Darren Lim"]))     # relief's old team list, not moved yet: no other page has run
    with published(PUB):
        c = staff("Mr Darren Lim")
        assert AP.load()["migrated"] is False
        j = c.get("/api/relief/me").get_json()
        assert (j["can_team"], j["can_plan"], j["on_team"]) == (True, True, True), j     # the All Relief Requests tab, on the first open
        assert AP.load()["migrated"] is True and AP.record(AP.load(), "Mr Darren Lim")["extras"]["relief"] is True
        assert A.move_relief_lists() is None and c.get("/api/relief/me").get_json()["can_team"] is True   # once only
    _reset(); fresh()

@t
def nothing_published_says_so():
    com = committee()
    with published(None):
        r = com.get("/api/relief/settings"); assert r.status_code == 409 and r.get_json() == {"error": NOT_PUBLISHED}, r.get_json()
        r = com.put("/api/relief/settings", json=base()); assert r.status_code == 409 and r.get_json() == {"error": NOT_PUBLISHED}
        for url in ("/api/relief/codes.csv", "/api/relief/code-slips.pdf"):
            r = com.get(url); assert r.status_code == 409 and r.data.decode() == NOT_PUBLISHED, url

@t
def codes_off_without_secret_key():
    com = committee()
    with published(PUB):
        del os.environ["SECRET_KEY"]
        try:
            page = A.app.test_client().get("/login").data              # the box stays for the shared codes; the page says why personal ones fail
            assert b'name="code"' in page and b"SECRET_KEY is not set" in page
            assert A.NO_PERSONAL_STAFF == "Personal codes are off until SECRET_KEY is set in Railway variables."
            assert com.get("/api/relief/codes.csv").status_code == 409 and com.get("/api/relief/code-slips.pdf").status_code == 409
            assert com.get("/api/relief/codes.csv").data.decode() == A.NO_PERSONAL_STAFF
            _, r = signed_in(access.staff_code("Mr Darren Lim")); assert r.status_code == 401
            _, r = signed_in(os.environ["TEACHER_CODE"]); assert r.status_code == 302
        finally: os.environ["SECRET_KEY"] = KEY
        assert b"SECRET_KEY is not set" not in A.app.test_client().get("/login").data

@t
def codes_csv_and_slips():
    fresh()
    AP.update(lambda d: d["people"].setdefault("Mdm Office Staff", {}).update(added=True, group="executive", note="admin"))
    with published(PUB):
        com = committee()
        r = com.get("/api/relief/codes.csv"); assert r.status_code == 200 and r.mimetype == "text/csv"
        text = r.data.decode("utf-8")
        assert text.startswith("﻿")
        rows = list(csv.reader(io.StringIO(text[1:])))
        assert rows[0] == ["Name", "Department", "Personal code"]
        ps = AP.staff(PUB)
        assert [x[0] for x in rows[1:]] == [p["name"] for p in ps]
        office = next(x for x in rows if x[0] == "Mdm Office Staff")
        assert office[2] == access.staff_code("Mdm Office Staff") and office[1] == ""
        assert next(x for x in rows if x[0] == "Mr Darren Lim")[1] == "Science"
        r = com.get("/api/relief/code-slips.pdf"); assert r.status_code == 200 and r.data.startswith(b"%PDF") and r.mimetype == "application/pdf"
        sc = staff("Mdm Office Staff")
        assert sc.get("/api/relief/codes.csv").status_code == 401 and sc.get("/api/relief/code-slips.pdf").status_code == 401
        # signed in with her code, she is that person: an executive, who sees the timetable and has no relief of her own
        with sc.session_transaction() as x: assert x["who"] == "Mdm Office Staff" and x["via"] == "code"
        assert sc.get("/api/relief/me").get_json() == AGAIN and sc.get("/relief").headers["Location"].endswith("/login")
        home = sc.get("/home"); page = home.get_data(as_text=True)    # her tiles: Timetables and her own exam duties, no Relief
        assert home.status_code == 200 and 'href="/timetable"' in page and 'href="/exams"' in page and 'href="/relief"' not in page, page[-400:]
    AP.update(lambda d: d["people"].pop("Mdm Office Staff"))

@t
def codes_csv_lists_both_departments():
    pub = P.fake_pub([dict(name="Ms Evelyn Koh", dept="Science", dept2="Mathematics")])
    text = RC.codes_csv(P.people(pub, []))
    rows = list(csv.reader(io.StringIO(text[1:])))
    assert rows[1][0] == "Ms Evelyn Koh" and rows[1][1] == "Science, Mathematics" and rows[1][2] == access.staff_code("Ms Evelyn Koh")

@t
def a_name_that_could_be_a_formula_is_refused_and_never_reaches_the_csv_as_one():
    fresh()
    assert S.FORMULA == ("=", "+", "-", "@", "\t", "\r")     # the admin page refuses these at the start of a name (accounts Task 8)
    ppl = [dict(name="=Ms Formula", depts=["+Science", "Mathematics"]), dict(name="@Mr At", depts=["-Art"]), dict(name="Ms Plain", depts=["Science"])]
    rows = list(csv.reader(io.StringIO(RC.codes_csv(ppl)[1:])))
    assert rows[1][:2] == ["'=Ms Formula", "'+Science, Mathematics"] and rows[2][:2] == ["'@Mr At", "'-Art"] and rows[3][:2] == ["Ms Plain", "Science"], [r[:2] for r in rows]   # never the codes
    assert rows[1][2] == access.staff_code("=Ms Formula") and rows[2][2] == access.staff_code("@Mr At")   # the code is still the person's own

@t
def role_names_are_read_without_their_spaces():
    fresh()
    pub = P.fake_pub([dict(name="Ms Evelyn Koh", dept="Science", role="HOD "), dict(name="Mr Darren Lim", dept="Science")],
                     roles=[dict(role="FAJT ", what="Flexible Adjunct Teacher (part-time)")])
    assert S.defaults(pub)["fat_role"] == "FAJT"
    assert S.save(base(fat_role="FAJT"), pub, "x")["fat_role"] == "FAJT"
    assert S.save(base(fat_role="HOD"), pub, "x")["fat_role"] == "HOD"
    fresh()

@t
def slips_are_ten_to_a_page_and_a_new_page_per_department():
    pages = lambda data: len(re.findall(rb"/Type\s*/Page[^s]", data))
    ppl = [dict(name=f"Teacher {i:02d}", short="", depts=["Science"], role="", teaches=True, staff_only=False) for i in range(12)]
    ppl += [dict(name="Ms Grace Wong", short="", depts=["Mathematics"], role="", teaches=True, staff_only=False),
            dict(name="Mdm Office Staff", short="", depts=[], role="", teaches=False, staff_only=True)]
    buf = io.BytesIO(); RC.slips_pdf("CTSS", ppl, "https://example.test", buf)
    assert buf.getvalue().startswith(b"%PDF") and pages(buf.getvalue()) == 4, pages(buf.getvalue())
    buf = io.BytesIO(); RC.slips_pdf("CTSS", ppl[:10], "https://example.test", buf)
    assert pages(buf.getvalue()) == 1

@t
def settings_edge_cases():
    fresh()
    for k, label in (("remind_at", "Remind the absent teacher at"), ("weekly_at", "Weekly summary at"), ("morning_at", "Morning message to the relief team at"), ("send_from", "Earliest send-out to relief teachers"),
                     ("cut_off", "Cut-off for the day's relief"), ("work_eve", "Remind the absent teacher to set work at"), ("work_day", "Remind the absent teacher to set work at")):
        raises(ValueError, lambda: S.save(base(times={k: ""}), PUB, "x"), f"Give a time for {label}.")
    raises(ValueError, lambda: S.save(base(times=dict(cut_off="25:00")), PUB, "x"), "25:00 is not a time like 15:00.")
    for bad_json in ("[]", '"text"'):
        open(S.PATH, "w").write(bad_json)
        d = S.load(PUB); assert d["limits"]["never"] == [] and d["times"]["cut_off"] == "14:00", bad_json
    fresh()
    rows = list(csv.reader(io.StringIO(RC.codes_csv([dict(name="\tMs Tab", depts=["\rSci"])])[1:])))
    assert rows[1][0] == "'\tMs Tab" and rows[1][1] == "'\rSci", rows[1][:2]

# ---- Send-out, Task 1: the times and school hours ----
@t
def the_three_times_are_in_order_and_fill_at_stays_in_the_file():
    raises(ValueError, lambda: S.save(base(times=dict(morning_at="06:50", send_from="06:45")), PUB, "x"), S.ORDER)
    raises(ValueError, lambda: S.save(base(times=dict(send_from="14:00", cut_off="14:00")), PUB, "x"), S.ORDER)
    S.save(base(times=dict(morning_at="06:45", send_from="06:45", cut_off="13:00")), PUB, "x")
    store.write_json(S.PATH, dict(store.read_json(S.PATH, {}), times=dict(fill_at="15:30")))   # a file saved by the last version
    assert "fill_at" not in S.load(PUB)["times"] and S.load(PUB)["times"]["morning_at"] == "06:30", "unread; the defaults"
    S.save(base(), PUB, "x"); assert store.read_json(S.PATH, {})["times"]["fill_at"] == "15:30", "kept in the file"

@t
def a_fill_time_sent_by_a_page_is_not_saved():
    fresh(); S.save(base(times=dict(fill_at="09:00")), PUB, "x")
    assert "fill_at" not in store.read_json(S.PATH, {})["times"] and "fill_at" not in S.load(PUB)["times"]

@t
def a_time_with_a_new_line_after_it_is_not_a_time():
    raises(ValueError, lambda: S.save(base(times=dict(morning_at="06:30\n")), PUB, "x"), "06:30\n is not a time like 15:00.")
    raises(ValueError, lambda: S.save(base(times=dict(remind_at="15:00\n")), PUB, "x"), "15:00\n is not a time like 15:00.")

print(f"{COUNT} relief tests passed")

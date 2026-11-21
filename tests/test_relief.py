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
    bad("Give each term and holiday a name.", calendar=dict(terms=[dict(name="", start="2026-09-07", end="2026-11-20", starts_as="Odd")], holidays=[]))
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

UNREAD = "The settings could not be read. Reload the page and try again."
NAMELESS = "Give each term and holiday a name."

@t
def save_refuses_the_wrong_json_types():
    fresh()
    for new in ([], None, "settings", 5):
        raises(ValueError, lambda: S.save(new, PUB, "x"), UNREAD)
    cases = [dict(team=None), dict(management="Ms Grace Wong"), dict(team=[["Mr Darren Lim"]]), dict(extra_staff=dict(name="Mdm Office Staff")),
             dict(extra_staff=["Mdm Office Staff"]), dict(extra_staff=[dict(name=["Mdm Office Staff"])]), dict(rules="Use planned relief first."),
             dict(rules=None), dict(rules=[["x"]]), dict(limits=[["fat_per_day", 3]]), dict(limits=None), dict(limits=dict(never="Ms Grace Wong")),
             dict(limits=dict(never=None)), dict(times=[]), dict(times=None), dict(calendar=[]), dict(calendar=None), dict(calendar=dict(terms=["Term 4"], holidays=[])),
             dict(calendar=dict(terms=None, holidays=[])), dict(calendar=dict(terms=[], holidays=[["Deepavali"]])), dict(calendar=dict(terms=[], holidays=None)),
             dict(fat_role=["FAJT"]), dict(calendar=dict(terms=[dict(name=["Term 4"], start="2026-09-07", end="2026-11-20", starts_as="Odd")], holidays=[]))]
    for kw in cases:
        raises(ValueError, lambda: S.save(base(**kw), PUB, "x"), UNREAD)
    assert not os.path.exists(S.PATH)
    S.save(base(fat_role=None, limits=dict(other_per_day=None)), PUB, "x")       # an empty value is not a wrong type
    assert S.load(PUB)["fat_role"] == ""

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
NOT_PUBLISHED = "Publish the timetable first: relief reads the teachers from it."

@t
def the_front_page_is_one_box_for_every_code():
    c = A.app.test_client()
    with published(PUB):
        front = c.get("/login").data
        assert b"Your personal code (on the slip from the school)" in front and front.count(b'name="code"') == 1 and b'class="choice' not in front
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
        assert me == dict(name="Mr Darren Lim", depts=["Science"], on_team=False, on_management=False, can_settings=False), me
        r = c.get("/"); assert r.status_code == 302 and r.headers["Location"].endswith("/relief")
        with A.app.test_request_context():
            A.session["role"], A.session["who"] = "staff", "Mr Darren Lim"
            p = A.me_staff(); assert p["name"] == "Mr Darren Lim" and p["depts"] == ["Science"], p
            A.session["who"] = "Ms Nobody"
            assert A.me_staff() is None and "role" not in A.session and "who" not in A.session
            A.session["role"] = "teacher"; assert A.me_staff() is None and A.session["role"] == "teacher"
    bad, r = signed_in("ZZZZ-ZZZZ"); assert r.status_code == 401

def timetable_pub(pub):
    """a fake published timetable the teacher routes can answer from: no classes, and the teacher page already made"""
    import copy
    pub = copy.deepcopy(pub); pub["model"].update(class_ix={}, teacher_ix={}, room_ix={}, students=[])
    pub["views"][("view", "teacher")] = "the teacher page"
    pub["views"][("view", "staff")] = "the staff page"   # the teacher's page with the way back to Relief
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
        r = c.get("/timetable"); assert r.status_code == 200 and r.data == b"the staff page"
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
        r = e.get("/pdf/classes/1A"); assert r.status_code == 401 and r.get_json() == {"error": "Please sign in again."}
        r = e.get("/api/relief/me"); assert r.status_code == 401 and r.get_json() == {"error": "Please sign in again."}
        with e.session_transaction() as s: assert s["role"] == "staff" and s["who"] == "Mr Darren Lim"

@t
def the_relief_home_is_the_staff_page():
    with published(PUB):
        c = staff("Mr Darren Lim")
        r = c.get("/relief"); assert r.status_code == 200 and b"/static/relief.js" in r.data and b"Relief settings" in r.data, r.status_code; r.close()
    assert all(os.path.exists(os.path.join(ROOT, "static", f)) for f in ("relief.html", "relief.js", "relief-settings.html", "relief-settings.js"))

@t
def staff_on_the_timetable_get_the_way_back_to_relief():
    import copy
    from ttgen import export as E
    seen = []
    def fake_render(model, view, app=None): seen.append(app); return f"page {len(seen)}"
    old, E.render_html = E.render_html, fake_render
    pub = copy.deepcopy(PUB); pub["views"] = {}
    try:
        with published(pub):
            s, (tc, _) = staff("Mr Darren Lim"), signed_in(os.environ["TEACHER_CODE"])
            assert s.get("/timetable").data == b"page 1" and tc.get("/timetable").data == b"page 2"
            assert s.get("/timetable").data == b"page 1" and tc.get("/timetable").data == b"page 2" and len(seen) == 2   # each kept, apart
    finally: E.render_html = old
    assert seen[0]["home"] == "/relief" and seen[0]["homeLabel"] == "Relief" and seen[0]["mode"] == "teacher", seen[0]
    assert seen[1]["home"] is None and seen[1]["mode"] == "teacher" and seen[0]["tabs"] == seen[1]["tabs"], seen[1]
    assert set(pub["views"]) == {("view", "staff"), ("view", "teacher")}, list(pub["views"])

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
        assert c.get("/").headers["Location"].endswith("/relief")
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

@t
def settings_rights():
    fresh()
    with published(PUB):
        com = committee()
        r = com.get("/relief"); assert r.status_code == 302 and r.headers["Location"].endswith("/relief/settings")
        r = com.put("/api/relief/settings", json=base(team=["Mr Darren Lim"], management=["Ms Grace Wong"]))
        assert r.status_code == 200, r.get_json()
        j = com.get("/api/relief/settings").get_json()
        assert set(j) == {"settings", "people", "roles", "weeks", "can_save", "can_codes"}, list(j)
        assert j["can_save"] is True and j["can_codes"] is True and j["roles"] == ["FAJT"] and j["weeks"] == 2
        assert j["settings"]["team"] == ["Mr Darren Lim"] and j["settings"]["saved_by"] == "Timetable committee"
        assert [p["name"] for p in j["people"]] == [p["name"] for p in P.people(PUB, [])]
        team, mgmt, plain = staff("Mr Darren Lim"), staff("Ms Grace Wong"), staff("Ms Evelyn Koh")
        assert team.get("/api/relief/me").get_json()["can_settings"] is True and team.get("/api/relief/me").get_json()["on_team"] is True
        m = mgmt.get("/api/relief/me").get_json(); assert m["on_management"] is True and m["can_settings"] is False
        j = team.get("/api/relief/settings").get_json(); assert j["can_save"] is True and j["can_codes"] is False
        r = team.put("/api/relief/settings", json=base(team=["Mr Darren Lim"], management=["Ms Grace Wong"], rules=["Use planned relief first."]))
        assert r.status_code == 200 and r.get_json()["settings"]["saved_by"] == "Mr Darren Lim", r.get_json()
        assert S.load(PUB)["saved_by"] == "Mr Darren Lim" and S.load(PUB)["rules"] == ["Use planned relief first."]
        j = mgmt.get("/api/relief/settings"); assert j.status_code == 200 and j.get_json()["can_save"] is False
        r = mgmt.put("/api/relief/settings", json=base(team=["Ms Grace Wong"])); assert r.status_code == 403 and r.get_json()["error"] == SETTINGS_DENIED
        assert S.load(PUB)["team"] == ["Mr Darren Lim"]
        for url in ("/api/relief/settings",):
            assert plain.get(url).status_code == 403 and plain.put(url, json=base()).status_code == 403
        r = plain.get("/relief/settings"); assert r.status_code == 403 and SETTINGS_DENIED.encode() in r.data
        r = mgmt.get("/relief/settings"); assert r.status_code == 403 and SETTINGS_DENIED.encode() in r.data
        for x in (team, com):
            r = x.get("/relief/settings"); assert r.status_code == 200 and b"/static/relief-settings.js" in r.data, r.status_code; r.close()
        r = team.get("/relief"); assert r.status_code == 200 and b"/static/relief.js" in r.data, r.status_code; r.close()
        tc, _ = signed_in(os.environ["TEACHER_CODE"])
        assert tc.get("/api/relief/settings").status_code == 401 and tc.put("/api/relief/settings", json=base()).status_code == 401
        assert tc.get("/relief/settings").status_code == 403 and tc.get("/api/relief/me").status_code == 401
        # a refused save is a sentence (400), never a server error
        r = com.put("/api/relief/settings", json=base(team=["Ms Nobody"])); assert r.status_code == 400 and r.get_json()["error"] == "Ms Nobody is not on the published timetable or the staff list."
        for body in ([], "x", dict(team=None), dict(calendar=dict(terms=["Term 4"]))):
            r = com.put("/api/relief/settings", json=body); assert r.status_code == 400 and r.get_json()["error"] == UNREAD, (body, r.status_code)
        r = com.put("/api/relief/settings", data="not json", content_type="application/json"); assert r.status_code == 400 and r.get_json()["error"] == UNREAD
        r = com.put("/api/relief/settings", json=base(calendar=dict(terms=[dict(name="", start="2026-09-07", end="2026-11-20", starts_as="Odd")], holidays=[])))
        assert r.status_code == 400 and r.get_json()["error"] == NAMELESS
        # a team member who takes themselves off the team can no longer save
        r = team.put("/api/relief/settings", json=base(team=["Ms Evelyn Koh"])); assert r.status_code == 200 and r.get_json()["can_save"] is False
        assert team.put("/api/relief/settings", json=base(team=["Mr Darren Lim"])).status_code == 403

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
    S.save(base(extra_staff=[dict(name="Mdm Office Staff", note="admin")]), PUB, "x")
    with published(PUB):
        com = committee()
        r = com.get("/api/relief/codes.csv"); assert r.status_code == 200 and r.mimetype == "text/csv"
        text = r.data.decode("utf-8")
        assert text.startswith("﻿")
        rows = list(csv.reader(io.StringIO(text[1:])))
        assert rows[0] == ["Name", "Department", "Personal code"]
        ps = P.people(PUB, S.load(PUB)["extra_staff"])
        assert [x[0] for x in rows[1:]] == [p["name"] for p in ps]
        office = next(x for x in rows if x[0] == "Mdm Office Staff")
        assert office[2] == access.staff_code("Mdm Office Staff") and office[1] == ""
        assert next(x for x in rows if x[0] == "Mr Darren Lim")[1] == "Science"
        r = com.get("/api/relief/code-slips.pdf"); assert r.status_code == 200 and r.data.startswith(b"%PDF") and r.mimetype == "application/pdf"
        # signing in reads the accounts: until relief's extra staff move there (accounts Task 7), she is added to both
        AP.update(lambda d: d["people"].setdefault("Mdm Office Staff", {}).update(added=True, group="executive", note="admin"))
        sc = staff("Mdm Office Staff")
        assert sc.get("/api/relief/codes.csv").status_code == 403 and sc.get("/api/relief/code-slips.pdf").status_code == 403
        # signed in with her code, she is that person
        assert sc.get("/api/relief/me").get_json()["name"] == "Mdm Office Staff"
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
    for ch in "=+-@":
        raises(ValueError, lambda: S.save(base(extra_staff=[dict(name=f" {ch}HYPERLINK(1)", note="")]), PUB, "x"), f"A name cannot start with {ch}.")
    assert not os.path.exists(S.PATH)
    S.save(base(extra_staff=[dict(name="Mdm A-Lim", note="")]), PUB, "x")      # a dash inside a name is fine
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
    for k, label in (("fill_at", "Fill open lessons at"), ("remind_at", "Remind the absent teacher at"), ("weekly_at", "Weekly summary at")):
        raises(ValueError, lambda: S.save(base(times={k: ""}), PUB, "x"), f"Give a time for {label}.")
    raises(ValueError, lambda: S.save(base(times=dict(fill_at="25:00")), PUB, "x"), "25:00 is not a time like 15:00.")
    for bad_json in ("[]", '"text"'):
        open(S.PATH, "w").write(bad_json)
        d = S.load(PUB); assert d["team"] == [] and d["times"]["fill_at"] == "15:00", bad_json
    fresh()
    raises(ValueError, lambda: S.save(base(extra_staff=[dict(name="N" * 101, note="")]), PUB, "x"), "Keep a name under 100 characters.")
    raises(ValueError, lambda: S.save(base(extra_staff=[dict(name="Ms Ok", note="n" * 201)]), PUB, "x"), "Keep a note under 200 characters.")
    S.save(base(extra_staff=[dict(name="N" * 100, note="n" * 200)]), PUB, "x"); fresh()
    rows = list(csv.reader(io.StringIO(RC.codes_csv([dict(name="\tMs Tab", depts=["\rSci"])])[1:])))
    assert rows[1][0] == "'\tMs Tab" and rows[1][1] == "'\rSci", rows[1][:2]

print(f"{COUNT} relief tests passed")

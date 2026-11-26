"""Plain-assert tests for staff signing in with a username and password: .venv/bin/python tests/test_staff_passwords.py"""
import contextlib, datetime, glob, io, json, os, pickle, re, secrets, sys, tempfile, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = tempfile.mkdtemp()
KEY = secrets.token_hex(16)
CODES = {k: secrets.token_hex(8) for k in ("COMMITTEE_CODE", "TEACHER_CODE", "STUDENT_CODE", "HEADS_CODE")}
os.environ.pop("ADMIN_RECOVERY_CODE", None)
os.environ.update(DATA_DIR=DATA, SECRET_KEY=KEY, AI_PROVIDER="anthropic", AI_API_KEY="", **CODES)
sys.path.insert(0, ROOT)
import app as A, access, history as H, store  # noqa: E402
from accounts import passwords as PW, people as P  # noqa: E402
from relief import people as RP  # noqa: E402

SECRETS = [KEY, *CODES.values()]          # every password, code and recovery value used here: none may reach the history

def secret(n=8):
    """a random value the suite later looks for in the history and the accounts file: 16 hex characters or more, so it
    never turns up by chance inside a password hash, an id or a time"""
    assert n >= 8
    s = secrets.token_hex(n); SECRETS.append(s); return s

def staff_code(name):
    c = access.staff_code(name); SECRETS.append(c); return c

WRONG = "That code does not work. Check it and try again."
OFF = "This account is switched off. Ask the timetable committee."
NO_MATCH = "That username and password do not match."
LOCKED = "Too many wrong tries. Wait 15 minutes and try again."
NO_SECRET = "Accounts need SECRET_KEY in Railway variables."
FIRST = "Choose a new password first."
AGAIN = "Please sign in again."
CROSS = "That request did not come from this site."
PERSON_OFF = "Signing in as a person is off for now. Use the code the school gave your group, or ask the timetable committee."
UNREADABLE = "The accounts file could not be read: signing in as a person is off until it is fixed."

# made-up people: three published teachers, and a committee member who is not on the timetable
ALICE, BEN, ERIC, DANA, CARA = "Ms Alice Tan", "Mr Ben Ong", "Mr Eric Goh", "Ms Dana Yeo", "Ms Cara Wee"
TEACHERS = [dict(name=ALICE, dept="Science"), dict(name=BEN, dept="Mathematics"), dict(name=ERIC, dept="Science", role="HOD"),
            dict(name=CARA, dept="Mathematics")]

def publish(teachers=TEACHERS):
    """write what store.published() reads: a fake school with the teachers, one student, and the pages already made"""
    pub = RP.fake_pub(teachers)
    pub["meta"].update(published_at="1 Nov 2026, 09:00", ok=True)
    pub["model"]["students"] = [dict(id="S001", name="Sam Student", cls="1A")]
    os.makedirs(store.PUB, exist_ok=True)
    with open(os.path.join(store.PUB, "model.pkl"), "wb") as f: pickle.dump(pub["model"], f)
    store.write_json(os.path.join(store.PUB, "meta.json"), pub["meta"])
    store._cache.update(stamp=None, value=None)
    views = store.published()["views"]
    for key, text in ((("view", "committee", "/"), "the committee page"), (("view", "teacher", None), "the teacher page"),
                      (("view", "teacher", "/home"), "the person page"), (("view", "teacher", "/relief"), "the staff page"),
                      (("view", "student", None), "the student page")):
        views[key] = text   # by mode and the way back: a person to their tiles, a relief stage 1 session to Relief

def unpublish():
    p = os.path.join(store.PUB, "meta.json")
    if os.path.exists(p): os.remove(p)
    store._cache.update(stamp=None, value=None)

def person(name, **fields):
    """a record, made the way the admin page will make it"""
    def fn(d): d["people"].setdefault(name, {}).update(fields)
    P.update(fn)

def account(name, group="committee", **fields):
    pw = secret(); user = name.split(" ", 1)[1].lower().replace(" ", ".")
    person(name, group=group, username=user, pw=PW.hash_pw(pw), **fields)
    return user, pw

def rec(name): return P.record(P.load(), name)

def code_in(code, c=None, **extra):
    c = c or A.app.test_client(); return c, c.post("/login", data=dict(code=code, **extra))

def pw_in(user, pw, c=None):
    c = c or A.app.test_client(); return c, c.post("/login/password", data=dict(username=user, password=pw))

def recover(user, code, new, c=None):
    c = c or A.app.test_client(); return c, c.post("/login/recover", data=dict(username=user, code=code, new=new, again=new))

def kept(c):
    with c.session_transaction() as s: return dict(s)

def last(kind="signin"): return H.read(kinds=[kind], limit=1)[0]

def went(r, where): return r.status_code == 302 and r.headers["Location"].endswith(where)

def strikes(): return len(A.limiter.fails["127.0.0.1"])

COUNT = 0
def t(f):
    global COUNT
    A.limiter.fails.clear(); A.lockout.fails.clear(); publish(); P.update(lambda d: d["ways"].update(staff_off=None))
    f(); COUNT += 1
    return f

STAFF_USE_PASSWORD = "Staff now sign in with a username and password. Ask the timetable committee for your slip."
STAFF_CODES_OFF = "Staff codes are off: staff sign in with a username and password."

def admin(name="Ms Ada Lim"):
    """a committee admin with a password account, signed in; returns the client"""
    user, pw = account(name, group="leader", extras={"timetable": True, "admin": True})
    c, r = pw_in(user, pw); assert went(r, "/home"), r.status_code
    return c

def staff_off(c, off=True): return c.post("/api/admin/staff-codes", json={"off": off})

@t
def staff_codes_are_on_until_turned_off():
    assert P.staff_codes_off(P.load()) is False
    c, r = code_in(staff_code(ALICE)); assert went(r, "/home")

@t
def turning_staff_codes_off_refuses_a_staff_code():
    r = staff_off(admin()); assert r.status_code == 200, r.data
    assert isinstance(r.get_json()["staff_codes"]["off"], (int, float))
    n = strikes()
    c, r = code_in(staff_code(ALICE)); assert r.status_code == 401 and STAFF_USE_PASSWORD in r.data.decode()
    assert strikes() == n + 1
    e = last(); assert e["ok"] is False and e["reason"] == "staff code after staff codes were turned off"

@t
def a_student_code_and_a_password_still_work_when_staff_codes_are_off():
    c = admin(); staff_off(c)
    sc = access.personal_code("S001"); SECRETS.append(sc)
    c2, r = code_in(sc); assert went(r, "/me"), r.status_code
    user, pw = account("Mr Gil Ho"); c3, r = pw_in(user, pw); assert r.status_code == 302

@t
def an_open_staff_code_session_ends_when_staff_codes_are_turned_off():
    c, r = code_in(staff_code(ALICE)); assert went(r, "/home")
    staff_off(admin())
    r = c.get("/home"); assert went(r, "/login"), r.status_code
    r = c.get("/api/exams/my-duties"); assert r.status_code == 401 and r.get_json() == {"error": "Please sign in again."}

@t
def turning_them_on_again_lets_a_staff_code_in():
    c = admin(); staff_off(c)
    r = staff_off(c, False); assert r.get_json()["staff_codes"]["off"] is None
    c2, r = code_in(staff_code(ALICE)); assert went(r, "/home")

@t
def the_switch_is_recorded():
    c = admin(); staff_off(c); staff_off(c, False)
    es = [e for e in H.read(kinds=["account"], limit=50) if e.get("what") == "staff-codes"]
    assert {e["text"] for e in es} == {"Staff codes turned off", "Staff codes turned on"}, es
    assert all(e["who"] == "Ms Ada Lim" for e in es), es

@t
def a_teacher_cannot_press_the_switch():
    c, r = code_in(staff_code(ALICE)); assert went(r, "/home")
    assert staff_off(c).status_code == 401
    assert P.staff_codes_off(P.load()) is False

@t
def relief_code_slips_are_refused_when_staff_codes_are_off():
    c = admin(); staff_off(c)
    for url in ("/api/relief/code-slips.pdf", "/api/relief/codes.csv"):
        r = c.get(url); assert r.status_code == 409 and STAFF_CODES_OFF in r.data.decode(), (url, r.status_code)

@t
def waiting_counts_staff_without_a_chosen_password():
    P.update(lambda d: d["people"].clear())   # earlier tests left accounts behind: start from none
    account(ALICE, group="teacher"); account(BEN, group="teacher", must_change=True)
    c = admin()
    r = c.get("/api/admin/ways").get_json(); assert r["staff_codes"]["waiting"] == 3, r["staff_codes"]
    assert r["staff_codes"]["off"] is None

# ---- making accounts and printing slips ----
import base64, csv as _csv
from accounts import slips as SL

NO_SLIPS = "Everyone has chosen their own password: there is no slip to print."
NOT_STAFF = "{} is not on the published timetable or the staff list."
THREE = [dict(name=ALICE, dept="Science"), dict(name=BEN, dept="Mathematics"), dict(name=ERIC, dept="Science", role="HOD")]

def slip_school(teachers=THREE):
    """a clean accounts file, the teachers published, an admin signed in who has chosen a password -> the client"""
    P.update(lambda d: d["people"].clear()); publish(teachers); return admin()

def slips(c, names=None, preview=False): return c.post("/api/admin/staff-slips", json={"names": names, "preview": preview})

def make(c, names=None, chosen=()):
    """make the slips -> (the answer, the CSV rows as dicts); every temporary password goes to SECRETS"""
    r = c.post("/api/admin/staff-slips", json={"names": names, "preview": False, "chosen": list(chosen)}); assert r.status_code == 200, r.data
    assert r.headers["Cache-Control"] == "no-store"
    j = r.get_json(); rows = list(_csv.DictReader(io.StringIO(j["csv"].lstrip("\ufeff"))))
    for x in rows: SECRETS.append(x["Temporary password"])
    return j, rows

@t
def usernames_from_names():
    mk = SL.make_username
    assert mk("Ms Alice Tan", [], set()) == "alicetan"
    for title in ("Mr", "mrs", "MS.", "Mdm", "miss", "Dr.", "Mx"): assert mk(f"{title} Alice Tan", [], set()) == "alicetan", title
    assert mk("Dr Ng", ["Science"], set()) == "ngs"
    u = mk("Dr Ng", [], set()); assert u == "ngstaff" and 3 <= len(u) <= 40, u
    assert mk("Mdm Siti Nur'aini", [], set()) == "sitinuraini"
    assert mk("Ms Zo\u00eb Lim", [], set()) == "zoelim"
    assert mk("Ms Alice Tan", [], {"alicetan"}) == "alicetan2"
    assert mk("Ms Alice Tan", [], {"alicetan", "alicetan2"}) == "alicetan3"
    long = "Ms " + "abcdefghij" * 6
    u = mk(long, [], set()); assert len(u) == 40, len(u)
    u2 = mk(long, [], {u}); assert len(u2) <= 40 and u2 != u and u2.endswith("2"), u2
    assert all(re.fullmatch(r"[a-z0-9._-]{3,40}", x) for x in (u, u2, mk("Dr Ng", ["Science"], set())))

def ready_four():
    """ALICE has no record, BEN a username and no password, ERIC a temporary password, the admin a chosen one"""
    c = slip_school()
    person(BEN, username="ben.ong"); person(ERIC, username="eric.goh", pw=PW.hash_pw(secret()), must_change=True)
    return c

@t
def the_preview_counts_and_changes_nothing():
    c = ready_four(); before = open(P.PATH, "rb").read()
    j = slips(c, None, True).get_json(); assert j["count"] == 3, j
    assert j["lines"] == ["2 staff have no account yet: each gets a username made from their name and a temporary password.",
                          f"1 has a temporary password from an admin that they have not used yet ({ERIC}): they get a new one on this slip.",
                          "1 already chose their own password: no slip."], j["lines"]
    assert open(P.PATH, "rb").read() == before

@t
def making_slips_makes_accounts():
    c = ready_four(); ada_before = rec("Ms Ada Lim")
    j, rows = make(c); assert j["count"] == 3 and len(rows) == 3, j["count"]
    assert base64.b64decode(j["pdf"])[:4] == b"%PDF"
    assert j["csv"].startswith("\ufeff") and j["csv"].lstrip("\ufeff").splitlines()[0] == "Name,Department,Username,Temporary password"
    for x in rows:
        rc = rec(x["Name"]); assert rc["username"] == x["Username"] and rc["must_change"] is True
        assert PW.check_pw(rc["pw"], x["Temporary password"])
    assert {x["Name"] for x in rows} == {ALICE, BEN, ERIC}
    assert rec(BEN)["username"] == "ben.ong" and rec(ERIC)["username"] == "eric.goh"
    ada = rec("Ms Ada Lim"); assert ada["pw"] == ada_before["pw"] and ada["n"] == ada_before["n"]

@t
def a_slip_password_signs_in_and_asks_for_a_new_one():
    c = ready_four(); j, rows = make(c)
    x = next(r for r in rows if r["Name"] == ALICE)
    c2, r = pw_in(x["Username"], x["Temporary password"]); assert went(r, "/account/password"), (r.status_code, r.headers.get("Location"))

@t
def printing_twice():
    c = ready_four(); c2, r = code_in(staff_code(ALICE)); assert went(r, "/home")
    j, rows = make(c); first = next(r for r in rows if r["Name"] == ALICE)
    j, rows = make(c); second = next(r for r in rows if r["Name"] == ALICE)
    c3, r = pw_in(first["Username"], first["Temporary password"]); assert NO_MATCH in r.data.decode()
    c4, r = pw_in(second["Username"], second["Temporary password"]); assert went(r, "/account/password")
    assert c2.get("/home").status_code == 200

@t
def ticked_people_with_a_chosen_password_are_named_and_signed_out():
    c = slip_school(TEACHERS); user, pw = account(CARA, group="teacher")
    c2, r = pw_in(user, pw); assert went(r, "/home"); assert c2.get("/home").status_code == 200
    n0 = rec(CARA)["n"]
    j = slips(c, [CARA], True).get_json()
    assert j["count"] == 1 and f"{CARA} has chosen a password: their slip gives a new temporary one and their old password stops working." in j["lines"], j
    assert j["chosen"] == [CARA]
    make(c, [CARA], [CARA])
    assert rec(CARA)["n"] == n0 + 1
    c3, r = pw_in(user, pw); assert NO_MATCH in r.data.decode()
    assert went(c2.get("/home"), "/login")

@t
def nothing_to_print():
    c = slip_school([dict(name=ALICE, dept="Science")]); account(ALICE, group="teacher")
    j = slips(c, None, True).get_json(); assert j["count"] == 0 and j["lines"] == [NO_SLIPS], j
    r = slips(c); assert r.status_code == 400 and r.get_json()["error"] == NO_SLIPS

@t
def unknown_and_switched_off_names():
    c = slip_school()
    r = slips(c, ["Mr Who Dat"]); assert r.status_code == 400 and r.get_json()["error"] == NOT_STAFF.format("Mr Who Dat")
    person(ALICE, off=True)
    j = slips(c, [ALICE, BEN], True).get_json()
    assert j["count"] == 1 and f"{ALICE} is switched off: no slip." in j["lines"], j
    j, rows = make(c, [ALICE, BEN]); assert [x["Name"] for x in rows] == [BEN]
    assert not rec(ALICE)["pw"]
    r = slips(c, [f"Mr P{i}" for i in range(201)]); assert r.status_code == 400 and "at most 200" in r.get_json()["error"]

@t
def only_an_admin_prints():
    slip_school(); c, r = code_in(staff_code(ALICE)); assert went(r, "/home")
    r = slips(c); assert r.status_code == 401 and not rec(ALICE)["pw"]

@t
def a_damaged_accounts_file_does_not_preview():
    """a file that turns unreadable only after the admin's rights were read (a damaged file signs everyone out first),
    so readable() is made to say no to the slips route alone"""
    c = slip_school(); real = P.readable
    P.readable = lambda: False if sys._getframe(1).f_code.co_name == "admin_staff_slips" else real()
    try: r = slips(c, None, True)
    finally: P.readable = real
    assert r.status_code == 503 and r.get_json()["error"] == P.UNREADABLE, r.status_code

@t
def a_failed_pdf_changes_nothing():
    c = ready_four(); before = open(P.PATH, "rb").read()
    n = len([e for e in H.read(kinds=["account"], limit=200) if e.get("what") == "slips"])
    real = SL.slips_pdf
    def boom(*a, **k): raise RuntimeError("no pdf")
    SL.slips_pdf = boom
    err = io.StringIO()
    try:
        with contextlib.redirect_stderr(err): r = c.post("/api/admin/staff-slips", json={"names": None, "preview": False})
    finally: SL.slips_pdf = real
    assert "WARNING: sign-in slips could not be made (RuntimeError)" in err.getvalue(), err.getvalue()
    assert r.status_code == 500 and "nothing was changed" in r.get_json()["error"], r.status_code
    assert open(P.PATH, "rb").read() == before
    assert n == len([e for e in H.read(kinds=["account"], limit=200) if e.get("what") == "slips"])

@t
def someone_who_chose_between_the_preview_and_the_print_stops_it():
    c = slip_school(TEACHERS); j = slips(c, [ALICE, CARA], True).get_json(); assert j["chosen"] == []
    user, pw = account(CARA, group="teacher"); before = open(P.PATH, "rb").read()
    r = c.post("/api/admin/staff-slips", json={"names": [ALICE, CARA], "preview": False, "chosen": j["chosen"]})
    assert r.status_code == 409 and r.get_json()["error"] == "Someone ticked has just chosen their own password. Look at the list again before printing.", r.status_code
    assert open(P.PATH, "rb").read() == before
    c2, r = pw_in(user, pw); assert r.status_code == 302

@t
def everyone_ticked_switched_off_gives_only_their_lines():
    c = slip_school(); person(ALICE, off=True)
    j = slips(c, [ALICE], True).get_json(); assert j["count"] == 0 and j["lines"] == [f"{ALICE} is switched off: no slip."], j

@t
def two_people_with_one_base_username_get_two_usernames():
    c = slip_school([dict(name="Ms Alice Tan", dept="Science"), dict(name="Dr Alice Tan", dept="Science")])
    j, rows = make(c); assert sorted(x["Username"] for x in rows) == ["alicetan", "alicetan2"], rows

@t
def the_history_says_how_many_and_never_a_password():
    c = ready_four(); make(c)
    es = [e for e in H.read(kinds=["account"], limit=50) if e.get("what") == "slips"]   # the newest first; earlier tests left theirs
    assert es[0]["text"] == "Printed sign-in slips for 3 staff: 2 new accounts", es
    assert set(es[0]["people"]) == {ALICE, BEN, ERIC}
    user, pw = account(CARA, group="teacher"); publish(TEACHERS)
    make(c, [CARA], [CARA])
    e = [e for e in H.read(kinds=["account"], limit=50) if e.get("what") == "slips"][0]
    assert e["text"] == "Printed sign-in slips for 1 staff: 0 new accounts; 1 had chosen a password", e

TO_STUDENT = "Students: sign in with your code"
TO_STAFF = "Staff: sign in with your username"
STUDENT_LABEL = "Your personal code (on the slip from the school)"

@t
def while_staff_codes_are_on_the_front_page_is_as_today():
    h = A.app.test_client().get("/login").data.decode()
    assert 'name="code"' in h and 'href="/login/password"' in h and 'name="username"' not in h and "/student" not in h

@t
def when_staff_codes_are_off_the_front_page_is_the_username_page():
    staff_off(admin())
    h = A.app.test_client().get("/login").data.decode()
    assert 'name="username"' in h and 'name="password"' in h and 'name="code"' not in h
    assert 'href="/student"' in h and TO_STUDENT in h, h

@t
def the_student_page():
    c = A.app.test_client(); h = c.get("/student").data.decode()
    assert 'name="code"' in h and STUDENT_LABEL in h and 'action="/student"' in h
    assert f'href="/login/password">{TO_STAFF}' in h, h
    sc = access.personal_code("S001"); SECRETS.append(sc)
    r = c.post("/student", data=dict(code=sc)); assert went(r, "/me"), r.status_code
    r = A.app.test_client().post("/student", data=dict(code=secret())); h = r.data.decode()
    assert r.status_code == 401 and WRONG in h and 'action="/student"' in h
    r = A.app.test_client().post("/student", data=dict(code=CODES["STUDENT_CODE"])); assert went(r, "/timetable"), r.status_code
    staff_off(admin()); h = A.app.test_client().get("/student").data.decode()
    assert f'href="/login">{TO_STAFF}' in h, h
    n = strikes()
    r = A.app.test_client().post("/student", data=dict(code=staff_code(ALICE))); h = r.data.decode()
    assert r.status_code == 401 and STAFF_USE_PASSWORD in h and 'action="/student"' in h and strikes() == n + 1
    assert last()["reason"] == "staff code after staff codes were turned off"

@t
def student_slips_print_the_student_page():
    c = admin(); seen = []
    import ttgen.export as X
    real = X.code_slips_pdf
    def spy(m, codes, url, out): seen.append(url); out.write(b"%PDF-1.4")   # the route's own work; the real drawing needs a full model
    X.code_slips_pdf = spy
    try: r = c.get("/api/code-slips.pdf")
    finally: X.code_slips_pdf = real
    assert r.status_code == 200 and seen and seen[0].endswith("/student"), (r.status_code, seen)

@t
def post_login_still_takes_codes_when_off():
    staff_off(admin())
    sc = access.personal_code("S001"); SECRETS.append(sc)
    c, r = code_in(sc); assert went(r, "/me"), r.status_code

# ---- the published timetable for a teacher, once staff codes are off ----
from accounts import rights as RT

def publish_real():
    """a published timetable the real page is drawn from: the sample school with the four teachers, a lesson each in 1A,
    one student, two books on disk, and no page made yet"""
    from ttgen import export as X, reader
    from ttgen.samples import secondary
    sp = secondary()
    sp["teachers"] += [dict(name=x["name"], short=x["name"].split()[1], dept=x["dept"], allowance=20, provisional="No") for x in TEACHERS]
    reader.derive(sp)
    lv = sp["school"]["levels"][0]; days = list(sp["day_structure"][lv].keys()); p0 = sp["day_structure"][lv][days[0]].index("L")
    L = [dict(id=i + 1, d=i, p=p0, n=1, level=lv, block="", classes=["1A"], subject=sp["lessons"][0]["subject"], group=X.ENTIRE, teachers=[x["name"]],
              room=sp["venues"][0]["room"], ext=False, rain="") for i, x in enumerate(TEACHERS)]
    m = X._model(sp, days, L); m["students"] = [dict(id="S001", name="Sam Student", cls="1A", level=lv, groups=[])]
    os.makedirs(store.PUB, exist_ok=True)
    for b in ("classes", "teachers"):
        with open(os.path.join(store.PUB, f"{b}.pdf"), "wb") as f: f.write(b"%PDF-1.4 " + b.encode())
    with open(os.path.join(store.PUB, "model.pkl"), "wb") as f: pickle.dump(m, f)
    store.write_json(os.path.join(store.PUB, "meta.json"), dict(school="Sample School", published_at="1 Nov 2026, 09:00", ok=True,
                                                                files=dict(books=dict(classes="classes.pdf", teachers="teachers.pdf"))))
    store._cache.update(stamp=None, value=None)
    assert store.published()["views"] == {}

def page_data(c):
    r = c.get("/timetable"); assert r.status_code == 200, r.status_code
    m = re.search(r"<script>const DATA = (.*?);</script>", r.data.decode(), re.S); assert m, "no DATA on the page"
    return json.loads(m.group(1))

def signed_in(name, group="teacher", **fields):
    """a password account (earlier tests' slips and switches undone), signed in -> the client"""
    user, pw = account(name, group=group, **dict(dict(must_change=False, off=False, extras={}), **fields)); c, r = pw_in(user, pw); assert went(r, "/home"), r.status_code
    return c

@t
def sees_all_rules():
    today = datetime.date(2026, 11, 26)
    assert RT.sees_all(None, today) is False
    assert RT.sees_all(dict(group="teacher", extras={}), today) is False
    assert RT.sees_all(dict(group="executive", extras={"timetable": False, "relief": False, "exams": None, "admin": False}), today) is False
    for g in ("leader", "hod", "sh"): assert RT.sees_all(dict(group=g, extras={}), today) is True, g
    assert RT.sees_all(dict(group="teacher", extras={"exams": "2026-11-25"}), today) is False
    assert RT.sees_all(dict(group="teacher", extras={"exams": "2026-11-26"}), today) is True
    for x in ("timetable", "relief", "admin"): assert RT.sees_all(dict(group="teacher", extras={x: True}), today) is True, x

@t
def nothing_narrows_while_staff_codes_are_on():
    c = signed_in(ALICE)
    r = c.get("/timetable"); assert r.data == b"the person page", r.data[:80]   # the cached ("view", "teacher", "/home"), as today

@t
def a_teacher_sees_their_own_and_the_classes():
    staff_off(admin()); publish_real(); c = signed_in(ALICE)
    d = page_data(c); a = d["app"]
    assert a["mode"] == "staff" and a["tabs"] == ["classes", "teachers", "exams"] and a["me"] == ALICE, a
    assert a["files"] == [["Class PDFs", "/files/book/classes"]] and a["home"] == "/home" and a["placeholder"] == "Search a class", a
    assert d["students"] == [] and d["rooms"] == [] and d["teachers"], (len(d["students"]), len(d["rooms"]))
    assert all(t[2] == "" and t[3] == "" for t in d["teachers"]), d["teachers"][:3]
    assert {t[0] for t in d["teachers"]} >= {ALICE, BEN} and d["checks"]["problems"] == []
    assert ("view", "staff", "/home", ALICE) in store.published()["views"]
    from urllib.parse import quote
    assert c.get(f"/pdf/teachers/{quote(ALICE)}").status_code == 200
    for url in (f"/pdf/teachers/{quote(BEN)}", f"/pdf/rooms/{quote(store.published()['model']['rooms'][0]['name'])}", "/pdf/students/S001"):
        assert c.get(url).status_code == 403, url
    r = c.get("/pdf/classes/1A"); assert r.status_code == 200 and r.data[:4] == b"%PDF"
    assert c.get("/files/book/teachers").status_code == 404
    r = c.get("/files/book/classes"); assert r.status_code == 200 and r.data == b"%PDF-1.4 classes"
    assert c.get("/files/excel").status_code == 403

@t
def two_teachers_in_a_row():
    staff_off(admin()); publish_real()
    a, b = signed_in(ALICE), signed_in(BEN)
    assert page_data(a)["app"]["me"] == ALICE
    assert page_data(b)["app"]["me"] == BEN
    assert page_data(a)["app"]["me"] == ALICE

@t
def an_executive_has_no_my_timetable():
    staff_off(admin()); publish_real(); c = signed_in("Mr Ivan Ng", group="executive")
    a = page_data(c)["app"]; assert a["mode"] == "staff" and a["tabs"] == ["classes", "exams"] and a.get("me") is None, a
    from urllib.parse import quote
    for n in (ALICE, BEN, "Mr Ivan Ng"): assert c.get(f"/pdf/teachers/{quote(n)}").status_code == 403, n
    assert c.get("/pdf/classes/1A").status_code == 200

@t
def management_and_committees_see_all():
    staff_off(admin()); publish_real()
    for c in (signed_in(ERIC, group="hod"), signed_in(CARA, extras={"relief": True})):
        d = page_data(c); a = d["app"]
        assert a["mode"] == "teacher" and a["tabs"] == A.TABS["teacher"] and "me" not in a, a
        assert d["students"] and d["rooms"]
        from urllib.parse import quote
        assert c.get(f"/pdf/teachers/{quote(BEN)}").status_code == 200

@t
def the_shared_teacher_code_is_narrow_when_staff_codes_are_off():
    staff_off(admin()); publish_real()
    P.update(lambda d: d["ways"]["off"].update(teacher=None))   # turned on again (it is on in this suite's blank file)
    c, r = code_in(CODES["TEACHER_CODE"]); assert went(r, "/timetable"), r.status_code
    a = page_data(c)["app"]; assert a["mode"] == "staff" and a["tabs"] == ["classes", "exams"] and a.get("me") is None, a
    from urllib.parse import quote
    assert c.get(f"/pdf/teachers/{quote(ALICE)}").status_code == 403 and c.get("/pdf/classes/1A").status_code == 200
    assert c.get("/files/book/teachers").status_code == 404
    P.update(lambda d: d["ways"].update(staff_off=None))
    a = page_data(c)["app"]; assert a["mode"] == "teacher" and a["tabs"] == A.TABS["teacher"], a   # staff codes on: as today

@t
def nothing_typed_reaches_the_history():
    text = "".join(open(f, encoding="utf-8").read() for f in glob.glob(os.path.join(H.DIR, "*.jsonl")))
    assert text.count('"kind": "signin"') > 10, text.count('"kind": "signin"')
    for s in SECRETS:
        assert not any(x in text for x in {s, s.upper(), s.lower(), access.norm(s)}), "a password, code or recovery value is in the history"
    assert "nobody.here" not in text and "no.such.person" not in text
    with open(P.PATH, encoding="utf-8") as f: kept_file = f.read()
    for s in SECRETS:
        assert not any(x in kept_file for x in {s, s.upper(), s.lower(), access.norm(s)}), "a password, code or recovery value is in the accounts file"

print(f"{COUNT} staff password tests passed")

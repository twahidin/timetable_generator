"""Plain-assert tests for signing in as a person (accounts stage 1): .venv/bin/python tests/test_signin.py"""
import contextlib, datetime, glob, io, json, os, pickle, secrets, sys, tempfile, time
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
    A.limiter.fails.clear(); A.lockout.fails.clear(); publish()
    f(); COUNT += 1
    return f

@t
def the_page_is_one_box_and_a_link():
    c = A.app.test_client()
    page = c.get("/login").data.decode()
    assert "Sample School" in page and "Please enter your code to access your timetable." in page and 'name="code"' in page and ">Open<" in page
    assert "personal code" not in page                             # the shared codes are on: the words people already know
    assert 'href="/login/password"' in page and "Staff Sign In" in page
    assert "Google" not in page and 'class="choice' not in page and "Department heads" not in page
    assert c.get("/login?as=relief").data.decode() == page        # the old cards' ?as= is accepted and ignored
    old = os.environ.pop("STUDENT_CODE")
    try:
        unset = "STUDENT_CODE is not set in Railway variables."
        assert unset in A.setup_problems() and unset in c.get("/login").data.decode()
        person("Ms Kim Ho", group="committee", added=True, extras=dict(relief=False, exams=None, admin=True))
        assert unset in A.setup_problems(), "an admin who cannot sign in (no username or password) is not one yet"
        person("Ms Kim Ho", username="kim.ho", pw=PW.hash_pw(secret()))
        assert unset not in A.setup_problems() and unset not in c.get("/login").data.decode()   # once an admin who can sign in exists
        assert not any("not set in Railway variables" in p for p in A.setup_problems())
    finally:
        os.environ["STUDENT_CODE"] = old; P.update(lambda d: d["people"].pop("Ms Kim Ho"))

@t
def the_box_says_personal_code_once_every_shared_code_is_off():
    c = A.app.test_client()
    def turn(off):
        P.update(lambda d: d["ways"]["off"].update({r: ("2026-11-22" if off else None) for r in P.SHARED}))
    try:
        turn(True)
        page = c.get("/login").data.decode()
        assert "Please enter your personal code to access your timetable." in page and "Please enter your code to access your timetable." not in page
        P.update(lambda d: d["ways"]["off"].update(teacher=None))    # one shared code on again: the familiar words come back
        assert "Please enter your code to access your timetable." in c.get("/login").data.decode()
        turn(True)
        old = os.environ.pop("TEACHER_CODE")                          # a shared code that is not set does not count as on
        try:
            P.update(lambda d: d["ways"]["off"].update(teacher=None))
            assert "Please enter your personal code to access your timetable." in c.get("/login").data.decode()
        finally:
            os.environ["TEACHER_CODE"] = old
    finally:
        turn(False)
    assert "Please enter your code to access your timetable." in c.get("/login").data.decode()

@t
def a_published_teacher_signs_in_with_their_code_and_lands_on_home():
    code = staff_code(ALICE)
    c, r = code_in(code)
    assert went(r, "/home"), (r.status_code, r.headers.get("Location"))
    s = kept(c); assert s["who"] == ALICE and s["via"] == "code" and s["n"] == 0 and "role" not in s and "exp" not in s, s
    e = last()
    assert (e["ok"], e["via"], e["who"], e["as"], e["shared"], e["reason"], e["addr"]) == (True, "code", ALICE, ALICE, None, None, "127.0.0.1"), e
    assert e["where"] == "Sign-in", e                               # the history page's Where filter finds it
    for _ in range(2): code_in(code.lower().replace("-", " "))      # codes are read ignoring case, spaces and dashes
    assert len(rec(ALICE)["signins"]) == 2                           # the last two are kept
    assert c.get("/timetable").data == b"the person page"

@t
def shared_codes_still_work():
    before = sorted(P.load()["people"])
    for var, where, role, label in (("COMMITTEE_CODE", "/", "committee", "Shared committee code"), ("HEADS_CODE", "/", "head", "Shared heads' code"),
                                    ("TEACHER_CODE", "/timetable", "teacher", "Shared teacher code"), ("STUDENT_CODE", "/timetable", "student", "Shared student code")):
        c, r = code_in(CODES[var], **{"as": "relief"})
        assert went(r, where), (var, r.status_code)
        s = kept(c); assert s["role"] == role and "who" not in s, (var, s)
        e = last(); assert (e["ok"], e["via"], e["shared"], e["who"], e["as"]) == (True, "shared", role, None, label), e
    c, r = code_in(CODES["COMMITTEE_CODE"])
    assert c.get("/api/status").get_json()["role"] == "committee"
    sc = access.personal_code("S001"); SECRETS.append(sc)
    c, r = code_in(sc)
    assert went(r, "/me") and kept(c)["role"] == "personal" and kept(c)["sid"] == "S001"
    e = last(); assert (e["ok"], e["via"], e["who"], e["as"], e["shared"]) == (True, "personal", None, "A student", None), e
    assert "S001" not in json.dumps(e)                                # no student id in the history
    assert sorted(P.load()["people"]) == before                       # no record for a shared or a student's code

@t
def a_turned_off_shared_code_is_refused_and_its_open_sessions_end():
    tc, r = code_in(CODES["TEACHER_CODE"]); assert went(r, "/timetable") and tc.get("/timetable").data == b"the teacher page"
    cc, r = code_in(CODES["COMMITTEE_CODE"]); assert cc.get("/api/status").status_code == 200
    P.update(lambda d: d["ways"]["off"].update(teacher=time.time(), committee=time.time()))
    try:
        r = tc.get("/timetable"); assert went(r, "/login") and "role" not in kept(tc)
        r = cc.get("/api/status"); assert r.status_code == 401 and r.get_json() == {"error": AGAIN} and "role" not in kept(cc)
        n = strikes()
        c, r = code_in(CODES["TEACHER_CODE"])
        assert r.status_code == 401 and WRONG in r.data.decode() and "role" not in kept(c) and strikes() == n + 1
        e = last(); assert (e["ok"], e["reason"], e["shared"], e["via"]) == (False, "code turned off", "teacher", "shared"), e
    finally: P.update(lambda d: d["ways"]["off"].update(teacher=None, committee=None))
    c, r = code_in(CODES["TEACHER_CODE"]); assert went(r, "/timetable")

@t
def a_wrong_code_is_a_strike_and_ten_block_the_address():
    c, r = code_in(secret())
    assert r.status_code == 401 and WRONG in r.data.decode() and strikes() == 1 and "role" not in kept(c)
    e = last(); assert (e["ok"], e["reason"], e["via"], e["who"]) == (False, "wrong code", "code", None), e
    for _ in range(9): code_in(secret())
    c, r = code_in(CODES["TEACHER_CODE"]); assert r.status_code == 429 and "role" not in kept(c)
    assert last()["reason"] == "locked"

@t
def password_sign_in():
    user, pw = account(DANA)
    c, r = pw_in(user.upper(), pw)                                    # usernames ignore case
    assert went(r, "/home"), r.status_code
    s = kept(c); assert s["who"] == DANA and s["via"] == "password" and s["n"] == 0 and "role" not in s, s
    assert abs(s["exp"] - time.time() - 14 * 24 * 3600) < 60
    assert c.get("/api/status").get_json()["role"] == "committee"
    e = last(); assert (e["ok"], e["via"], e["who"], e["reason"]) == (True, "password", DANA, None), e
    assert len(rec(DANA)["signins"]) == 1
    k, r = code_in(staff_code(DANA))                                 # her code opens all but the setup and the admin page
    assert went(r, "/home") and kept(k)["via"] == "code" and k.get("/api/status").status_code == 401
    user, pw = account(ERIC, group="hod", depts=["Science"])
    c, r = pw_in(user, pw); assert went(r, "/home") and c.get("/api/status").get_json()["role"] == "head"

@t
def an_unknown_username_and_a_wrong_password_get_the_same_answer():
    user, pw = account("Mr Omar Ali", group="leader", added=True)
    _, a = pw_in("nobody.here", secret()); _, b = pw_in(user, secret())
    assert a.status_code == b.status_code == 401 and a.data == b.data and NO_MATCH in a.data.decode()
    assert strikes() == 2
    new, old = H.read(kinds=["signin"], limit=2)
    assert (new["reason"], new["who"], new["via"]) == ("wrong password", "Mr Omar Ali", "password"), new
    assert (old["reason"], old["who"], old["as"]) == ("unknown username", None, "Unknown"), old
    assert "nobody" not in json.dumps(old)                            # what was typed is never recorded

@t
def five_wrong_passwords_lock_the_account():
    user, pw = account("Ms Fay Ng", group="leader", added=True)
    for _ in range(5): _, r = pw_in(user, secret()); assert r.status_code == 401
    c, r = pw_in(user, pw)
    assert r.status_code == 429 and LOCKED in r.data.decode() and "who" not in kept(c)
    e = last(); assert (e["ok"], e["reason"], e["who"]) == (False, "locked", "Ms Fay Ng"), e
    A.limiter.fails.clear()
    for _ in range(5): pw_in("no.such.person", secret())             # an unknown username locks the same way: nothing shows who exists
    _, u = pw_in("no.such.person", secret()); assert u.status_code == 429 and u.data == r.data
    for q in A.lockout.fails.values():                                # 15 minutes later
        for i in range(len(q)): q[i] -= 901
    A.limiter.fails.clear()
    c, r = pw_in(user, pw); assert went(r, "/home") and kept(c)["who"] == "Ms Fay Ng"
    assert user not in A.lockout.fails

@t
def must_change_sends_every_page_to_the_password_page():
    user, pw = account("Mr Gus Lee", group="leader", added=True, must_change=True)
    c, r = pw_in(user, pw); assert went(r, "/account/password"), r.status_code
    for url in ("/", "/home", "/timetable", "/relief", "/relief/settings"): assert went(c.get(url), "/account/password"), url
    for url in ("/api/status", "/api/relief/me", "/pdf/classes/1A", "/files/book/classes"):
        r = c.get(url); assert r.status_code == 403 and r.get_json() == {"error": FIRST}, (url, r.status_code)
    r = c.get("/account/password"); assert r.status_code == 200 and all(f'name="{k}"' in r.data.decode() for k in ("current", "new", "again"))
    new = secret()
    r = c.post("/account/password", data=dict(current=pw, new=new, again=new)); assert went(r, "/home"), r.status_code
    assert rec("Mr Gus Lee")["must_change"] is False and rec("Mr Gus Lee")["n"] == 1 and kept(c)["n"] == 1
    assert PW.check_pw(rec("Mr Gus Lee")["pw"], new) and c.get("/timetable").status_code == 200
    k, _ = pw_in(user, new)
    x, y = secret(), secret()
    short = secrets.token_hex(4)   # under 10 characters: refused before anything keeps it; too short to look for in the files
    for data, text in ((dict(current=new, new=short, again=short), "Use at least 10 characters."),
                       (dict(current=new, new=x, again=y), "The two new passwords are not the same."),
                       (dict(current=secret(), new=x, again=x), "Your current password is not right.")):
        r = k.post("/account/password", data=data); assert r.status_code in (400, 403) and text in r.data.decode(), (text, r.status_code)
    assert PW.check_pw(rec("Mr Gus Lee")["pw"], new) and k.get("/timetable").status_code == 200
    person("Mr Gus Lee", must_change=True)                            # a new one-time password: his password session goes there first
    assert went(k.get("/timetable"), "/account/password")
    g, r = code_in(staff_code("Mr Gus Lee")); assert g.get("/timetable").status_code == 200   # his code is not the password: not stopped
    a, _ = code_in(staff_code(ALICE))                                  # no username: no password to change
    assert a.get("/account/password").status_code == 403 and a.get("/timetable").status_code == 200
    assert went(A.app.test_client().get("/account/password"), "/login")
    user, otp = account(CARA, group="teacher", must_change=True)     # a teacher given a username and a one-time password
    c, r = code_in(staff_code(CARA)); assert went(r, "/home")
    r = c.get("/relief"); assert r.status_code == 200 and b"/static/relief.js" in r.data, r.status_code; r.close()
    assert c.get("/api/relief/me").get_json()["name"] == CARA
    k, r = pw_in(user, otp); assert went(r, "/account/password") and went(k.get("/relief"), "/account/password")
    assert k.get("/api/relief/me").get_json() == {"error": FIRST}

@t
def changing_the_password_ends_the_persons_other_sessions():
    user, pw = account("Ms Hana Lim", group="leader", added=True)
    a, _ = pw_in(user, pw); b, _ = pw_in(user, pw)
    assert a.get("/timetable").status_code == 200 and b.get("/timetable").status_code == 200
    new = secret()
    r = a.post("/account/password", data=dict(current=pw, new=new, again=new)); assert went(r, "/home")
    assert a.get("/timetable").data == b"the person page"             # this session is kept, with the new number
    assert went(b.get("/timetable"), "/login") and "who" not in kept(b)
    _, r = pw_in(user, pw); assert r.status_code == 401
    _, r = pw_in(user, new); assert went(r, "/home")
    e = last("account")
    assert (e["what"], e["who"], e["people"], e["text"]) == ("password", "Ms Hana Lim", ["Ms Hana Lim"], "Changed their password"), e
    assert not any(x in json.dumps(e) for x in (pw, new)) and "pw" not in e

@t
def a_password_session_ends_after_14_days():
    user, pw = account(DANA)
    c, _ = pw_in(user, pw); assert c.get("/api/status").status_code == 200
    with c.session_transaction() as s: s["exp"] = time.time() + 86400   # 13 days old
    assert c.get("/api/status").status_code == 200
    with c.session_transaction() as s: s["exp"] = time.time() - 1
    r = c.get("/api/status"); assert r.status_code == 401 and r.get_json() == {"error": AGAIN} and "who" not in kept(c)
    c, _ = pw_in(user, pw)
    with c.session_transaction() as s: del s["exp"]
    assert c.get("/api/status").status_code == 401
    k, _ = code_in(staff_code(ALICE)); assert "exp" not in kept(k) and k.get("/timetable").status_code == 200

@t
def a_code_session_lives_through_a_publish_and_ends_when_the_teacher_is_dropped():
    c, _ = code_in(staff_code(BEN)); d, _ = code_in(staff_code(BEN))
    unpublish()                                                       # a publish swaps folders: for a moment nothing is published
    r = c.get("/timetable"); assert r.status_code == 200 and b"Not published yet" in r.data and b"Code no longer valid" not in r.data
    r = c.get("/api/relief/me"); j = r.get_json()
    assert r.status_code == 200 and j["name"] == BEN and j["depts"] == [] and j["published"] is False, (r.status_code, j)
    s = kept(c); assert s["who"] == BEN and s["via"] == "code", s
    publish([x for x in TEACHERS if x["name"] != BEN])
    r = c.get("/timetable"); assert r.status_code == 200 and b"Code no longer valid" in r.data and b"the person page" not in r.data, (r.status_code, r.data[:300])
    assert "who" not in kept(c)
    r = d.get("/api/relief/me"); assert r.status_code == 401 and r.get_json() == {"error": AGAIN} and "who" not in kept(d)
    _, r = code_in(staff_code(BEN)); assert r.status_code == 401

@t
def a_committee_password_session_does_not_need_the_timetable():
    user, pw = account(DANA)
    c, r = pw_in(user, pw); assert went(r, "/home") and c.get("/api/status").get_json()["role"] == "committee"
    unpublish()
    assert c.get("/api/status").status_code == 200
    k, r = pw_in(user, pw); assert went(r, "/home") and k.get("/api/status").status_code == 200
    publish([dict(name=ALICE, dept="Science")])
    assert c.get("/api/status").status_code == 200 and k.get("/api/status").status_code == 200

@t
def a_switched_off_person_is_refused():
    code = staff_code(ALICE)
    person(ALICE, off=True)
    try:
        c, r = code_in(code)
        assert r.status_code == 403 and OFF in r.data.decode() and "who" not in kept(c) and strikes() == 0   # no strike
        e = last(); assert (e["ok"], e["reason"], e["who"], e["via"]) == (False, "switched off", ALICE, "code"), e
    finally: person(ALICE, off=False)
    user, pw = account("Ms Ivy Chan", group="leader", added=True, off=True)
    _, r = pw_in(user, pw); assert r.status_code == 403 and OFF in r.data.decode()
    _, r = pw_in(user, secret()); assert r.status_code == 401 and NO_MATCH in r.data.decode()   # a wrong password says nothing about the account
    c, _ = code_in(code); assert c.get("/timetable").status_code == 200
    person(ALICE, off=True)
    try: assert went(c.get("/timetable"), "/login") and "who" not in kept(c)   # an open session ends at its next request
    finally: person(ALICE, off=False)

@t
def a_relief_stage_1_session_counts_as_a_code_session():
    c = A.app.test_client()
    with c.session_transaction() as s: s["role"], s["who"] = "staff", ALICE
    assert c.get("/timetable").data == b"the staff page"
    with A.app.test_request_context():
        A.session["role"], A.session["who"] = "staff", ALICE
        assert A.via() == "code" and A.who()["name"] == ALICE
    person(ALICE, n=1)                                                # a raised number ends it, as it ends any older session
    try: assert went(c.get("/timetable"), "/login") and "who" not in kept(c)
    finally: person(ALICE, n=0)

@t
def the_session_model():
    with A.app.test_request_context():
        A.session["role"] = "committee"
        assert A.via() == "shared" and A.shared() == "committee" and A.who() is None and A.has("codes") and not A.is_head()
        assert A.by() == {"who": None, "as": "Shared committee code", "via": "shared"}
    with A.app.test_request_context():
        A.session.update(role="personal", sid="S001")
        assert A.via() == "personal" and A.rights() == frozenset({"own"}) and A.by()["as"] == "A student" and A.shared() is None
    with A.app.test_request_context():
        A.session.update(who=ALICE, via="code", n=0)
        p = A.who()
        assert p["name"] == ALICE and p["depts"] == ["Science"] and "pw" not in p and A.via() == "code" and A.shared() is None
        assert A.has("relief") and not A.has("setup") and not A.is_head() and A.head_depts() is None
        assert A.by() == {"who": ALICE, "as": ALICE, "via": "code"}
    with A.app.test_request_context():
        assert A.via() is None and A.who() is None and A.rights() == frozenset() and A.by()["as"] == "Unknown" and not A.is_head()
    calls = []
    real = A.rights_table.rights
    A.rights_table.rights = lambda *a, **k: calls.append(1) or real(*a, **k)
    try:
        with A.app.test_request_context():
            A.session.update(who=ALICE, via="code", n=0)
            A.rights(); A.has("relief"); A.rights()
            assert len(calls) == 1                                    # worked out once a request, kept on flask.g
    finally: A.rights_table.rights = real
    assert A.app.view_functions["post_setup_changes"]._need == ("setup",)
    assert A.app.view_functions["timetable"]._need == ("timetable",)

@t
def recovery_works_once_per_value_and_only_with_the_variable():
    c = A.app.test_client()
    assert c.get("/login/recover").status_code == 404 and c.post("/login/recover", data={}).status_code == 404
    user, pw = account("Ms Jo Tan", added=True, extras=dict(relief=False, exams=None, admin=True))
    other, _ = account("Mr Kai Lee", added=True)                      # committee, not an admin
    rc = secret(); os.environ["ADMIN_RECOVERY_CODE"] = rc
    try:
        page = c.get("/login/recover").data.decode(); assert 'name="code"' in page and 'name="username"' in page
        for _ in range(5): pw_in(user, secret())                      # she is locked out as well
        A.limiter.fails.clear()
        new = secret()
        k, r = recover(user, rc, new); assert went(r, "/home"), r.status_code
        s = kept(k); assert s["who"] == "Ms Jo Tan" and s["via"] == "password" and s["n"] == 1, s
        assert PW.check_pw(rec("Ms Jo Tan")["pw"], new) and user not in A.lockout.fails and k.get("/api/status").status_code == 200
        e = last(); assert (e["ok"], e["via"], e["who"]) == (True, "recovery", "Ms Jo Tan"), e
        e = last("account")
        assert (e["what"], e["people"], e["text"], e["who"]) == ("recovery", ["Ms Jo Tan"], "Password set with the recovery code", "Ms Jo Tan"), e
        assert not any(x in json.dumps(e) for x in (rc, new, access.norm(rc)))
        _, r = pw_in(user, new); assert went(r, "/home")
        _, r = recover(user, rc, secret()); assert r.status_code == 403 and PW.check_pw(rec("Ms Jo Tan")["pw"], new)   # once per value
        e = last(); assert (e["ok"], e["reason"], e["via"]) == (False, "recovery code already used", "recovery"), e
        _, r = recover(user, secret(), secret()); assert r.status_code == 401
        rc2 = secret(); os.environ["ADMIN_RECOVERY_CODE"] = rc2
        _, r = recover(other, rc2, secret()); assert r.status_code == 401   # only an admin's username
        new2 = secret()
        _, r = recover(user, rc2, new2); assert went(r, "/home") and PW.check_pw(rec("Ms Jo Tan")["pw"], new2)
        used = P.load()["ways"]["recovery_used"]; assert len(used) == 2 and PW.check_pw(used[0], rc) and PW.check_pw(used[1], rc2)
    finally: os.environ.pop("ADMIN_RECOVERY_CODE", None)
    assert c.get("/login/recover").status_code == 404

SHORT_RECOVERY = "ADMIN_RECOVERY_CODE is too short (use at least 16 letters or digits); recovery is off."

@t
def a_short_recovery_code_counts_as_not_set():
    c = A.app.test_client()
    user, _ = account("Ms Ivy Goh", added=True, extras=dict(relief=False, exams=None, admin=True))
    for short in (secrets.token_hex(7), "  " + secrets.token_hex(7) + "  ", "x"):   # 14 letters or digits (after trimming), and one
        os.environ["ADMIN_RECOVERY_CODE"] = short
        try:
            assert A.recovery_code() is None and A.recovery_too_short()
            assert c.get("/login/recover").status_code == 404
            _, r = recover(user, short, secret()); assert r.status_code == 404, r.status_code   # a weak code opens nothing
            assert SHORT_RECOVERY in A.setup_problems() and SHORT_RECOVERY in c.get("/login").data.decode()
        finally: os.environ.pop("ADMIN_RECOVERY_CODE", None)
    os.environ["ADMIN_RECOVERY_CODE"] = "  " + secret() + "  "        # 16 after trimming: on
    try:
        assert A.recovery_code() and not A.recovery_too_short() and c.get("/login/recover").status_code == 200
        assert SHORT_RECOVERY not in A.setup_problems()
    finally: os.environ.pop("ADMIN_RECOVERY_CODE", None)
    assert SHORT_RECOVERY not in A.setup_problems() and not A.recovery_too_short()

@t
def a_change_from_another_site_is_refused():
    c, _ = code_in(CODES["COMMITTEE_CODE"])
    body = dict(client="x", since=0, ops=[])
    for h in ({"Origin": "https://elsewhere.example"}, {"Referer": "https://elsewhere.example/page"}, {"Origin": "null"},
              {"Origin": "https://elsewhere.example", "Referer": "http://localhost/"}):
        r = c.post("/api/setup/changes", json=body, headers=h); assert r.status_code == 403 and r.get_json() == {"error": CROSS}, h
    r = c.put("/api/setup", json={}, headers={"Origin": "https://elsewhere.example"}); assert r.status_code == 403
    for h in ({"Origin": "http://localhost"}, {"Referer": "http://localhost/"}, {}):
        r = c.post("/api/setup/changes", json=body, headers=h); assert r.status_code != 403 and r.get_json() != {"error": CROSS}, h
    assert c.get("/api/status", headers={"Origin": "https://elsewhere.example"}).status_code == 200   # reading is not a change
    k = A.app.test_client()
    r = k.post("/login", data=dict(code=CODES["TEACHER_CODE"]), headers={"Origin": "https://elsewhere.example"})
    assert r.status_code == 403 and "role" not in kept(k)

@t
def accounts_need_secret_key():
    user, pw = account(DANA); code = staff_code(ALICE)
    del os.environ["SECRET_KEY"]
    try:
        page = A.app.test_client().get("/login/password").data.decode(); assert NO_SECRET in page and 'name="password"' not in page
        c, r = pw_in(user, pw); assert r.status_code == 403 and NO_SECRET in r.data.decode() and "who" not in kept(c)
        c, r = code_in(CODES["COMMITTEE_CODE"]); assert went(r, "/")         # the shared codes work as today
        _, r = code_in(code); assert r.status_code == 401                     # personal codes are off
    finally: os.environ["SECRET_KEY"] = KEY
    _, r = pw_in(user, pw); assert went(r, "/home")

@t
def the_school_s_date_ends_the_exams_extra():
    """the server runs on UTC: an Exams and events extra ends at midnight school time, not at 8 the next morning"""
    import zoneinfo
    from accounts import rights as R
    old = os.environ.get("TZ"); os.environ["TZ"] = "UTC"; time.tzset()
    try: assert R.school_today() == datetime.datetime.now(zoneinfo.ZoneInfo("Asia/Singapore")).date()
    finally:
        if old is None: os.environ.pop("TZ", None)
        else: os.environ["TZ"] = old
        time.tzset()
    school = datetime.date.today() - datetime.timedelta(days=5)       # a date the server's own clock cannot give
    last = (school + datetime.timedelta(days=1)).isoformat()          # still on by the school's date, over by the server's
    real = R.school_today; R.school_today = lambda: school
    try:
        assert "exams" in R.rights(dict(group="teacher", extras=dict(relief=False, exams=last, admin=False)), "code")
        assert "exams" not in R.rights(dict(group="teacher", extras=dict(relief=False, exams=(school - datetime.timedelta(days=1)).isoformat(), admin=False)), "code")
        person("Ms Ida Lee", group="teacher", added=True, extras=dict(relief=False, exams=last, admin=False))
        A._tidied_on = None; A.app.test_client().get("/healthz")
        assert rec("Ms Ida Lee")["extras"]["exams"] == last, "the daily tidy ends it by the school's date"
        assert A._tidied_on == school
        assert ["Ms Ida Lee", last] in A._exams_committee(None)
        assert "Exams and events" in (A._group_label(dict(group="teacher", extras=dict(relief=False, exams=last, admin=False))) or "")
    finally:
        R.school_today = real; A._tidied_on = None

@t
def the_daily_tidy():
    today = datetime.date.today(); yesterday = today - datetime.timedelta(days=1)
    person("Ms Lia Ong", group="teacher", added=True, extras=dict(relief=False, exams=yesterday.isoformat(), admin=False))
    person("Mr Max Ho", group="teacher", added=True, extras=dict(relief=False, exams=today.isoformat(), admin=False))
    old = os.path.join(H.DIR, "2001-01.jsonl"); os.makedirs(H.DIR, exist_ok=True); open(old, "w").close()
    A._tidied_on = None
    assert A.app.test_client().get("/healthz").status_code == 200
    assert rec("Ms Lia Ong")["extras"]["exams"] is None and rec("Mr Max Ho")["extras"]["exams"] == today.isoformat()
    e = last("account")
    assert e["text"] == f"Exams and events access ended (until {yesterday.day} {yesterday.strftime('%b %Y')})" and e["people"] == ["Ms Lia Ong"], e
    assert (e["what"], e["who"], e["as"], e["via"], e["where"]) == ("ended", None, "The app", "app", "Admin"), e
    assert not os.path.exists(old)                                    # history files over two years old are removed
    n = len(H.read(kinds=["account"], limit=1000))
    person("Ms Lia Ong", extras=dict(relief=False, exams=yesterday.isoformat(), admin=False))
    A.app.test_client().get("/healthz")                               # once a day
    assert len(H.read(kinds=["account"], limit=1000)) == n and rec("Ms Lia Ong")["extras"]["exams"] == yesterday.isoformat()
    real = H.prune
    def boom(*a, **k): raise RuntimeError("never shown")
    H.prune = boom; A._tidied_on = None; err = io.StringIO()
    try:
        with contextlib.redirect_stderr(err): r = A.app.test_client().get("/healthz")
    finally: H.prune = real
    assert r.status_code == 200 and "RuntimeError" in err.getvalue() and "never shown" not in err.getvalue() and err.getvalue().count("\n") == 1, err.getvalue()

@t
def a_padded_username_shares_the_accounts_lockout():
    user, pw = account("Ms Pia Sim", group="leader", added=True)
    pads = [" ", "\t", "\u3000", "\u00a0", " \t"]
    for i, ws in enumerate(pads):                                     # padding past the 200 letters kept, each try different
        variant = (ws * 200)[:193 + i] + "Z"
        _, r = pw_in(user.upper() if i % 2 else "  " + user + variant, secret()); assert r.status_code == 401, i
    assert list(A.lockout.fails) == [user]                            # one lockout, on the account
    for u in (user, user.upper(), "  " + user + " " * 193 + "Z", user + "\u3000" * 196 + "Q"):
        _, r = pw_in(u, pw); assert r.status_code == 429 and LOCKED in r.data.decode(), repr(u[:12])
    assert strikes() == 5

@t
def an_unreadable_accounts_file_shuts_signing_in_by_name_and_keeps_the_shared_codes():
    alice, eric = staff_code(ALICE), staff_code(ERIC)
    c, r = code_in(alice); assert went(r, "/home") and c.get("/timetable").status_code == 200
    user, pw = account(DANA)
    person(ERIC, off=True, n=1)                                       # switched off, his number raised
    _, r = code_in(eric); assert r.status_code == 403 and OFF in r.data.decode()
    raw = open(P.PATH, encoding="utf-8").read()
    with open(P.PATH, "w", encoding="utf-8") as f: f.write("{not json")
    rc = secret(); os.environ["ADMIN_RECOVERY_CODE"] = rc
    try:
        assert not P.readable()
        k, r = code_in(eric)
        assert r.status_code == 403 and PERSON_OFF in r.data.decode() and "who" not in kept(k) and strikes() == 0
        e = last(); assert (e["ok"], e["who"], e["reason"]) == (False, ERIC, "accounts file unreadable"), e
        assert went(c.get("/timetable"), "/login") and "who" not in kept(c)   # an open session ends at its next request
        with c.session_transaction() as s: s.update(role="staff", who=ALICE)   # a relief stage 1 session too
        assert went(c.get("/timetable"), "/login")
        _, r = pw_in(user, pw); assert r.status_code == 403 and PERSON_OFF in r.data.decode()
        assert PERSON_OFF in A.app.test_client().get("/login/password").data.decode()
        _, r = recover(user, rc, secret()); assert r.status_code == 403 and PERSON_OFF in r.data.decode()
        t, r = code_in(CODES["TEACHER_CODE"]); assert went(r, "/timetable") and t.get("/timetable").data == b"the teacher page"   # the fallback
        m, r = code_in(CODES["COMMITTEE_CODE"]); assert m.get("/api/status").status_code == 200
        assert UNREADABLE in A.setup_problems() and UNREADABLE in A.app.test_client().get("/login").data.decode()
    finally:
        os.environ.pop("ADMIN_RECOVERY_CODE", None)
        with open(P.PATH, "w", encoding="utf-8") as f: f.write(raw)
    person(ERIC, off=False, n=0)
    assert P.readable() and UNREADABLE not in A.setup_problems()
    _, r = code_in(alice); assert went(r, "/home")

# ---- "Since you last signed in" on the home page
SINCE = "Since you last signed in"

def change(who, where="Step 4 · Teachers", kind="setup", depts=None, **more):
    """a change made by a made-up person, now"""
    H.add(dict(kind=kind, who=who, **{"as": who}, via="password", where=where, text=f"{who} changed something", depts=depts or [], **more))

def twice(user, pw, between):
    """sign in, run `between`, sign in again: the client of the second sign-in"""
    pw_in(user, pw); between(); c, r = pw_in(user, pw); assert went(r, "/home"), r.status_code
    return c

@t
def summary_after_a_second_sign_in():
    user, pw = account("Ms Una Koh", group="committee")
    def between():
        for _ in range(2): change("Ann")
        change("Bob")
        H.add(dict(kind="signin", ok=True, who="Bob", **{"as": "Bob"}, via="password", where="Sign-in", text="Bob signed in"))
    c = twice(user, pw, between)
    html = c.get("/home").data.decode()
    assert SINCE in html and "3 changes by 2 people" in html and "Ann · Step 4 · Teachers" in html and 'href="/history?since=' in html, html
    assert "See them" in html and ">Later<" in html and 'action="/home/later"' in html

@t
def head_summary_is_their_departments_and_own():
    user, pw = account(ERIC, group="hod", depts=["Science"])
    def between():
        change("Ann", "Step 4 · Teachers", depts=["Science"]); change("Bob", "Step 3 · Subjects", depts=["Mathematics"])
        change(ERIC, "Step 5 · Groups and bands", depts=["Mathematics"])
    html = twice(user, pw, between).get("/home").data.decode()
    assert SINCE in html and "Your own changes · Step 5 · Groups and bands" in html and "Ann · Step 4 · Teachers" in html, html
    assert "Bob" not in html and "2 changes by 2 people" in html, html

@t
def published_line_for_everyone():
    c, r = code_in(staff_code(BEN)); assert went(r, "/home")
    H.add(dict(kind="draft", what="publish", who="Mr Zed", **{"as": "Mr Zed"}, via="password", where="Step 9 · Publish", text="Published the timetable"))
    change("Ann")
    c, r = code_in(staff_code(BEN)); assert went(r, "/home")
    html = c.get("/home").data.decode()
    assert "The timetable was published again on" in html and SINCE in html, html
    assert "See them" not in html and "Ann" not in html
    assert "by 1 person" not in html and "Ann · " not in html and ">Later<" in html

@t
def a_teacher_is_not_shown_a_summary_of_their_own_changes():
    c, r = code_in(staff_code(BEN)); assert went(r, "/home")
    H.add(dict(kind="relief", what="request", who=BEN, **{"as": BEN}, via="code", where="Relief", text="Asked for relief"))
    c, r = code_in(staff_code(BEN)); assert went(r, "/home")
    assert SINCE not in c.get("/home").data.decode(), "only the committee and heads get the summary; a teacher only the published line"

@t
def no_box_on_first_sign_in_or_after_later():
    user, pw = account("Ms Vee Lim", group="committee")
    c, r = pw_in(user, pw); change("Ann")
    assert SINCE not in c.get("/home").data.decode()               # the first sign-in: nothing to compare with
    c, r = pw_in(user, pw)
    assert SINCE in c.get("/home").data.decode()
    r = c.post("/home/later"); assert went(r, "/home")
    assert SINCE not in c.get("/home").data.decode()
    change("Bob"); c2, r = pw_in(user, pw, c)                       # the next sign-in shows it again
    assert SINCE in c.get("/home").data.decode()

@t
def summary_times_are_school_time():
    old = os.environ.get("TZ")
    os.environ["TZ"] = "UTC"; time.tzset()
    try:
        user, pw = account("Ms Wen Foo", group="committee")
        c = twice(user, pw, lambda: change("Ann"))
        previous = rec("Ms Wen Foo")["signins"][-2]
        assert f"{H.when_text(previous)} · 1 change by 1 person" in c.get("/home").data.decode()
    finally:
        if old is None: os.environ.pop("TZ", None)
        else: os.environ["TZ"] = old
        time.tzset()

@t
def summary_reads_little():
    user, pw = account("Ms Xia Lau", group="committee")
    c = twice(user, pw, lambda: change("Ann"))
    real, calls = H._lines, []
    H._lines = lambda name: (calls.append(name), real(name))[1]
    try: assert SINCE in c.get("/home").data.decode()
    finally: H._lines = real
    assert len(calls) == 1, calls

@t
def summary_function_groups_and_limits():
    me = "Ms Yan Ko"; t0 = time.time()
    for i in range(10): change(f"P{i}", f"Step {i}", ts=time.time())
    got = H.summary(t0, None, me, top=3)
    assert got["n"] == 10 and got["people"] == 10 and len(got["rows"]) == 3 and got["more"] == 7, got
    assert H.summary(t0, lambda e: False, me)["n"] == 0
    assert H.summary(time.time() + 100, None, me) == dict(n=0, people=0, rows=[], more=0, published=None)

@t
def nothing_typed_reaches_the_history():
    text = "".join(open(f, encoding="utf-8").read() for f in glob.glob(os.path.join(H.DIR, "*.jsonl")))
    assert text.count('"kind": "signin"') > 30, text.count('"kind": "signin"')
    for s in SECRETS:
        assert not any(x in text for x in {s, s.upper(), s.lower(), access.norm(s)}), "a password, code or recovery value is in the history"
    assert "nobody.here" not in text and "no.such.person" not in text
    with open(P.PATH, encoding="utf-8") as f: kept_file = f.read()
    for s in SECRETS:
        assert not any(x in kept_file for x in {s, s.upper(), s.lower(), access.norm(s)}), "a password, code or recovery value is in the accounts file"

print(f"{COUNT} sign-in tests passed")

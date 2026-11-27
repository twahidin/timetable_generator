"""Plain-assert tests for student codes and head resets (rights, tiles, pages): .venv/bin/python tests/test_codes_resets.py"""
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
from accounts import rights as RT  # noqa: E402

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


def signed_in(name, group="teacher", depts=None, **fields):
    """a password account, signed in -> the client"""
    if depts is not None: fields["depts"] = depts
    user, pw = account(name, group=group, **dict(dict(must_change=False, off=False, extras={}), **fields)); c, r = pw_in(user, pw); assert went(r, "/home"), r.status_code
    return c

@t
def the_rights():
    R = RT.rights
    for g in ("teacher", "executive", "leader", "hod", "sh"):
        assert "codes.look" in R(dict(group=g, extras={}), "password"), g
        assert "codes.look" in R(dict(group=g, extras={}), "code"), g
    assert "codes.look" not in R(None, "shared", "teacher") and "codes.look" not in R(None, "personal")
    assert R(dict(group="teacher", extras={}, off=True), "password") == frozenset()
    assert "staff.reset" in R(dict(group="hod", extras={}), "password") and "staff.reset" in R(dict(group="sh", extras={}), "password")
    assert "staff.reset" not in R(dict(group="hod", extras={}), "code")
    for g in ("teacher", "executive", "leader"): assert "staff.reset" not in R(dict(group=g, extras={"admin": True, "timetable": True}), "password"), g

@t
def the_tiles():
    c = signed_in(ALICE)
    h = c.get("/home").data.decode()
    assert "Student codes" in h and 'href="/student-codes"' in h and "Reset a password" not in h
    c = signed_in(ERIC, group="hod", depts=["Science"])
    h = c.get("/home").data.decode()
    assert 'href="/staff-reset"' in h
    c, _ = code_in(staff_code(ERIC))
    h = c.get("/home").data.decode()
    assert "Reset a password" in h and 'href="/staff-reset"' not in h and "Sign in with your password to open this." in h

@t
def the_admin_page_lines():
    texts = [x["text"] for x in RT.gives(dict(group="hod", extras={}), ["Science"])]
    assert "Student codes: looks up a student's forgotten code." in texts
    assert "Passwords: gives staff in their departments a new temporary password." in texts

CODES_HINT = "Pick the class, then press Show code beside the student. Each look-up is recorded."
CODES_NOT_PUBLISHED = "The timetable is not published yet, so there are no student codes."
CODES_EMPTY_CLASS = "This class has no students on the published timetable."
CODES_NO_STUDENT = "That student is not on the published timetable."

def pub_students(students):
    """rewrite the published students (the rest of the published model stays) and drop the cache, as publish() does"""
    p = os.path.join(store.PUB, "model.pkl")
    with open(p, "rb") as f: model = pickle.load(f)
    model["students"] = students
    with open(p, "wb") as f: pickle.dump(model, f)
    store._cache.update(stamp=None, value=None)

@t
def student_codes_by_class():
    publish(); pub_students([dict(id="S001", name="Sam Student", cls="1A"), dict(id="S/2 'x'", name="Kim <b>", cls="1A"), dict(id="S003", name="Lee", cls="2B")])
    c = signed_in(ALICE)
    h = c.get("/student-codes").data.decode()
    assert CODES_HINT in h and ">1A<" in h and ">2B<" in h and access.personal_code("S001") not in h
    h = c.get("/student-codes?cls=1A").data.decode()
    assert "Sam Student" in h and "Kim &lt;b&gt;" in h and "Lee" not in h and access.personal_code("S001") not in h
    n = len(H.read(kinds=["look"], limit=100))
    r = c.post("/student-codes", data=dict(id="S001")); h = r.data.decode()
    code = access.personal_code("S001"); SECRETS.append(code)
    assert r.status_code == 200 and code in h and r.headers["Cache-Control"] == "no-store"
    assert access.personal_code("S/2 'x'") not in h                # only the one asked for
    e = H.read(kinds=["look"], limit=1)[0]
    assert len(H.read(kinds=["look"], limit=100)) == n + 1 and e["text"] == "Looked up the code of Sam Student (1A)" and e["who"] == ALICE
    r = c.post("/student-codes", data=dict(id="S/2 'x'")); assert r.status_code == 200 and access.personal_code("S/2 'x'") in r.data.decode()
    SECRETS.append(access.personal_code("S/2 'x'"))

@t
def student_codes_refusals():
    c = signed_in(ALICE)
    r = c.post("/student-codes", data=dict(id="NOPE")); assert r.status_code == 404 and CODES_NO_STUDENT in r.data.decode()
    assert A.app.test_client().get("/student-codes").status_code == 302          # nobody signed in
    sc = access.personal_code("S001"); SECRETS.append(sc)
    s = A.app.test_client(); s.post("/student", data=dict(code=sc))
    assert s.get("/student-codes").status_code in (302, 401) and s.post("/student-codes", data=dict(id="S001")).status_code in (302, 401)
    h = signed_in(ALICE).get("/student-codes?cls=9Z").data.decode(); assert CODES_EMPTY_CLASS in h
    unpublish(); assert CODES_NOT_PUBLISHED in signed_in(ALICE).get("/student-codes").data.decode(); publish()

@t
def student_codes_by_staff_code():
    c, _ = code_in(staff_code(BEN))                # staff codes on: a staff code session is staff
    assert c.get("/student-codes").status_code == 200

@t
def nothing_typed_reaches_the_history():
    text = "".join(open(f, encoding="utf-8").read() for f in glob.glob(os.path.join(H.DIR, "*.jsonl")))
    assert text.count('"kind": "signin"') > 1, text.count('"kind": "signin"')
    for s in SECRETS:
        assert not any(x in text for x in {s, s.upper(), s.lower(), access.norm(s)}), "a password, code or recovery value is in the history"
    assert "nobody.here" not in text and "no.such.person" not in text
    with open(P.PATH, encoding="utf-8") as f: kept_file = f.read()
    for s in SECRETS:
        assert not any(x in kept_file for x in {s, s.upper(), s.lower(), access.norm(s)}), "a password, code or recovery value is in the accounts file"
    c = admin("Ms Zara Koh"); answers = []
    for url in ("/api/admin/people", "/api/admin/ways"):
        r = c.get(url); assert r.status_code == 200, (url, r.status_code); answers.append((url, r.get_data(as_text=True)))
    files = []
    for top, _, names in os.walk(DATA):
        for n in names:
            with open(os.path.join(top, n), "rb") as f: files.append((os.path.relpath(os.path.join(top, n), DATA), f.read().decode("utf-8", "replace")))
    assert len(files) > 3, len(files)
    for where, body in answers + files:
        for s in SECRETS:
            assert not any(x in body for x in {s, s.upper(), s.lower(), access.norm(s)}), f"a password, code or recovery value is in {where}"

print(f"{COUNT} codes and resets tests passed")

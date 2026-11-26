"""Plain-assert tests for staff signing in with a username and password: .venv/bin/python tests/test_staff_passwords.py"""
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

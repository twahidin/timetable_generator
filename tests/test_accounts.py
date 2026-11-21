"""Plain-assert tests for accounts: .venv/bin/python tests/test_accounts.py"""
import os, re, secrets, sys, tempfile, threading
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = tempfile.mkdtemp()
os.environ.update(DATA_DIR=DATA, SECRET_KEY=secrets.token_hex(16), AI_PROVIDER="anthropic", AI_API_KEY="")
sys.path.insert(0, ROOT)
import datetime, time, unittest.mock  # noqa: E402
import app as A, store  # noqa: E402
from accounts import passwords as PW, people as P, rights as R  # noqa: E402
from relief.people import fake_pub  # noqa: E402

COUNT = 0
def t(f):
    global COUNT
    f(); COUNT += 1
    return f

@t
def password_rules():
    assert PW.problem("abcdefghi") == "Use at least 10 characters."
    assert PW.problem("x" * 30, "daniel.wong", "Daniel Wong") is None
    assert PW.problem("DanielWong", "daniel.wong", "Daniel Wong") == "Don't use your username or your name."
    assert PW.problem("daniel.wong", "daniel.wong", "Daniel Wong") == "Don't use your username or your name."
    assert PW.problem("Daniel Wong", "dw", "Daniel Wong") == "Don't use your username or your name."
    c = sorted(PW.COMMON)[0]
    assert len(c) >= 10 and len(PW.COMMON) >= 90 and all(len(x) >= 10 and x == x.lower() for x in PW.COMMON)
    assert PW.problem(c.upper()) == "That password is too common. Choose another."
    assert PW.problem(secrets.token_hex(8)) is None

@t
def hash_round_trip():
    pw = secrets.token_hex(8); h = PW.hash_pw(pw)
    assert h != pw and PW.check_pw(h, pw) and not PW.check_pw(h, pw + "x") and PW.check_pw(None, pw) is False

@t
def one_time_shape():
    a, b = PW.one_time(), PW.one_time()
    assert re.match(r"^[2-9A-HJ-KM-NP-Z]{4}(-[2-9A-HJ-KM-NP-Z]{4}){2}$", a) and a != b

@t
def lockout():
    L = PW.Lockout(); assert not L.blocked("k")
    for _ in range(4): L.fail("k")
    assert not L.blocked("k"); L.fail("k"); assert L.blocked("k") and not L.blocked("j")
    L.clear("k"); assert not L.blocked("k")
    for _ in range(5): L.fail("k")
    now = time.time()
    with unittest.mock.patch("time.time", return_value=now + 901): assert not L.blocked("k")

def person(group, **extras):
    return dict(group=group, extras=dict(relief=False, exams=None, admin=False, **extras), off=False)

@t
def rights_table():
    S = lambda who: R.rights(None, "shared", who)
    assert S("committee") == {"committee", "setup", "timetable", "files", "history", "codes", "relief.settings", "relief.save"}
    assert S("head") == {"setup", "timetable", "files"} and S("teacher") == {"timetable", "files"} and S("student") == {"timetable"}
    assert R.rights(None, "personal") == {"own"}
    base = {"timetable", "files"}
    assert R.rights(person("executive"), "code") == base
    assert R.rights(person("teacher"), "code") == base | {"relief"}
    assert R.rights(person("leader"), "code") == base | {"relief", "relief.plan", "relief.settings"}
    assert R.rights(person("hod"), "code") == base | {"relief", "relief.plan", "relief.settings"}
    c = R.rights(person("committee"), "code")
    assert c == base | {"relief", "relief.settings", "relief.save"} and not c & {"committee", "setup", "admin", "history", "codes"}
    assert "relief.plan" in R.rights(person("hod"), "code") and "setup" not in R.rights(person("hod"), "code")
    assert R.rights(person("executive", relief=True) if False else dict(person("executive"), extras=dict(relief=True, exams=None, admin=False)), "code") == base | {"relief", "relief.plan", "relief.settings", "relief.save", "relief.team"}
    cs = R.rights(person("committee"), "password")
    assert cs == base | {"relief", "relief.settings", "relief.save", "committee", "setup", "history", "codes"}
    assert "admin" in R.rights(dict(person("committee"), extras=dict(relief=False, exams=None, admin=True)), "password")
    assert "admin" not in R.rights(dict(person("committee"), extras=dict(relief=False, exams=None, admin=True)), "code")
    assert "admin" not in R.rights(dict(person("hod"), extras=dict(relief=False, exams=None, admin=True)), "password")
    for g in ("hod", "sh"): assert "setup" in R.rights(person(g), "google")
    assert "setup" not in R.rights(person("teacher"), "password")
    today = datetime.date(2026, 11, 21); iso = lambda d: d.isoformat()
    ex = lambda d: R.rights(dict(person("teacher"), extras=dict(relief=False, exams=iso(d), admin=False)), "code", today=today)
    assert "exams" not in ex(today - datetime.timedelta(days=1)) and "exams" in ex(today)
    assert R.rights(dict(person("committee"), off=True), "password") == frozenset()

def pub():
    return fake_pub([dict(name="Ms Test One", dept="Sci"), dict(name="Mr Test Two", dept="Maths")])

@t
def staff_merges_records():
    d = P.blank()
    d["people"]["Ms Added"] = dict(P.record(d, "Ms Added"), added=True, pw="HASHSECRET", signins=[3, 9, 5])
    d["people"]["Ms Boss"] = dict(P.record(d, "Ms Boss"), group="committee", username="ms.boss", pw="HASHSECRET")
    s = {x["name"]: x for x in P.staff(pub(), d)}
    assert s["Ms Test One"]["group"] == "teacher" and s["Ms Test One"]["depts"] == ["Sci"] and not s["Ms Test One"]["has_password"]
    assert s["Ms Added"]["group"] == "executive" and s["Ms Added"]["has_password"] and s["Ms Added"]["last"] == 9
    assert "HASHSECRET" not in repr(list(s.values())) and all("pw" not in x for x in s.values())
    f = P.find("Ms Boss", pub(), d)
    assert f["group"] == "committee" and f["pw"] == "HASHSECRET" and f["n"] == 0 and f["must_change"] is False
    assert P.find("Nobody", pub(), d) is None and P.find("Ms Test One", pub(), d)["name"] == "Ms Test One"
    assert P.by_username(d, " MS.Boss ")[0] == "Ms Boss" and P.by_username(d, "zz") == (None, None)
    assert P.admins(d) == []
    d["people"]["Ms Boss"]["extras"]["admin"] = True; assert P.admins(d) == ["Ms Boss"]
    d["people"]["Ms Boss"]["off"] = True; assert P.admins(d) == []

@t
def update_is_the_only_write():
    assert P.load() == P.blank()
    def add(n):
        def fn(d): d["people"][n] = P.record(d, n); return n
        return fn
    ths = [threading.Thread(target=P.update, args=(add(f"P{i}"),)) for i in range(20)]
    [x.start() for x in ths]; [x.join() for x in ths]
    assert len(P.load()["people"]) == 20 and P.update(lambda d: "r") == "r"
    open(P.PATH, "w").write("not json"); assert P.load() == P.blank()

@t
def sweep_ends_exams():
    d = P.blank(); today = datetime.date(2026, 11, 21)
    for n, e in (("A", "2026-11-20"), ("B", "2026-11-21"), ("C", None)):
        d["people"][n] = dict(P.record(d, n)); d["people"][n]["extras"]["exams"] = e
    assert P.sweep(d, today) == ["A"] and d["people"]["A"]["extras"]["exams"] is None and d["people"]["B"]["extras"]["exams"] == "2026-11-21"

@t
def unreadable_file_is_never_overwritten():
    shutil_rm = lambda: os.path.exists(P.PATH) and os.remove(P.PATH)
    shutil_rm(); assert P.readable()
    P.update(lambda d: d["people"].update(X=P.record(d, "X"))); assert "X" in P.load()["people"] and P.readable()
    for junk in (b"not json", b"[1, 2]"):
        open(P.PATH, "wb").write(junk)
        assert not P.readable()
        try: P.update(lambda d: d["people"].update(Y={}))
        except P.Unreadable as e: assert str(e) == "The accounts file could not be read, so nothing was changed. Ask whoever looks after the app to check it."
        else: raise AssertionError("did not raise")
        assert open(P.PATH, "rb").read() == junk
    os.remove(P.PATH); P.update(lambda d: None); assert os.path.exists(P.PATH)

@t
def corrupt_record_does_not_break_helpers():
    d = P.blank()
    d["people"]["Ms Bad"] = dict(group="hod", extras="x", depts=None, signins="y", pw="garbage", username="ms.bad", added=True)
    d["people"]["Mr Bad"] = dict(group=7, extras=dict(exams=5, admin="yes"), depts=[3, " Sci ", ""], signins=[1, "a", None], n="x")
    d["people"]["Mr Odd"] = "text"
    s = {x["name"]: x for x in P.staff(pub(), d)}
    assert s["Ms Bad"]["last"] is None and s["Ms Bad"]["extras"] == dict(relief=False, exams=None, admin=False)
    f = P.find("Ms Bad", pub(), d); assert f["pw"] == "garbage"
    assert not PW.check_pw(f["pw"], "anything") and not PW.check_pw("pbkdf2:sha256:bad", "x")
    assert P.sweep(d, datetime.date(2026, 11, 21)) == []
    assert R.rights(f, "password") >= {"setup"}
    assert P.record(d, "Mr Bad")["depts"] == ["Sci"] and P.record(d, "Mr Bad")["signins"] == [1] and P.record(d, "Mr Bad")["group"] is None
    assert P.admins(d) == []

@t
def the_moved_flag_is_a_real_boolean():
    assert P.blank()["migrated"] is False and P._fill({"migrated": "yes"})["migrated"] is False and P._fill({"migrated": True, "moved": ["x"]})["moved"] == ["x"]

print(f"{COUNT} accounts tests passed")

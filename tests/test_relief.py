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

print(f"{COUNT} relief tests passed")

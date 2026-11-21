"""Plain-assert tests for the admin API (accounts stage 1): .venv/bin/python tests/test_admin.py"""
import contextlib, datetime, glob, io, json, os, pickle, secrets, sys, tempfile, time, urllib.parse
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = tempfile.mkdtemp()
KEY = secrets.token_hex(16)
CODES = {k: secrets.token_hex(8) for k in ("COMMITTEE_CODE", "TEACHER_CODE", "STUDENT_CODE", "HEADS_CODE")}
for k in ("ADMIN_RECOVERY_CODE", "ANTHROPIC_API_KEY", "TYPED_REQUEST_MODEL", "AI_MODEL"): os.environ.pop(k, None)
os.environ.update(DATA_DIR=DATA, SECRET_KEY=KEY, AI_PROVIDER="anthropic", AI_API_KEY="", **CODES)
sys.path.insert(0, ROOT)
import app as A, history as H, store  # noqa: E402
from accounts import passwords as PW, people as P  # noqa: E402
from relief import people as RP, settings as RS  # noqa: E402
from ttgen.samples import secondary  # noqa: E402

SECRETS = [KEY, *CODES.values()]          # every password, code and one-time password used here: none may reach the history

def secret(n=8):
    assert n >= 8, "a value looked for inside files is 16 hex characters or more, so none turns up by chance"
    s = secrets.token_hex(n); SECRETS.append(s); return s

AGAIN = {"error": "Please sign in again."}
FIRST = {"error": "Choose a new password first."}
NO_ACCOUNTS = "Accounts need SECRET_KEY in Railway variables."
PICK_GROUP = "Pick a group."
ONLY_COMMITTEE = "Only the timetable committee can be admins."
EXAMS_DATE = "Give the last day of the exams and events access."
BAD_USERNAME = "A username is 3 to 40 letters, digits, dots, dashes or underscores."
TAKEN = "That username is taken."
NO_USERNAME = "Give them a username first."
NO_ONE = "Tick at least one person."
def last_admin(n): return f"{n} is the last admin: make another admin first."
def not_dept(d): return f"{d} is not one of the school's departments."
def not_staff(n): return f"{n} is not on the published timetable or the staff list."
ONLY_ADMIN = "Only an admin can open this page."
RECOVERY_ON = "A recovery code is set in Railway variables: remove it once you are back in."
RECOVERY_SHORT = "ADMIN_RECOVERY_CODE is too short (use at least 16 letters or digits); recovery is off."

TODAY = datetime.date.today()
RAVI_UNTIL = (TODAY + datetime.timedelta(days=40)).isoformat()
UNTIL = (TODAY + datetime.timedelta(days=358)).isoformat()
YESTERDAY = (TODAY - datetime.timedelta(days=1)).isoformat()

def day(iso):
    d = datetime.date.fromisoformat(iso); return f"{d.day} {d.strftime('%b %Y')}"

# made-up people (the mockup's): teachers on the published timetable, and staff added by name
ALICIA, LEE, DANIEL, SITI, RAVI, NUR, WEI = "Alicia Tan", "Lee Kok Hwa", "Daniel Wong", "Siti Rahmah", "Ravi Kumar", "Nur Aisyah", "Tan Wei Jie"
GRACE, FARID, JOSEPH, MARCUS, PRIYA = "Grace Ong", "Farid Ismail", "Joseph Lim", "Marcus Goh", "Priya Nair"
FOUR = [RAVI, NUR, WEI, GRACE]
TEACHERS = [dict(name=ALICIA, dept="MA"), dict(name=DANIEL, dept="SC", role="HOD"), dict(name=SITI, dept="MA", role=" sh "),
            dict(name=RAVI, dept="HU"), dict(name=NUR, dept="HU"), dict(name=WEI, dept="HU"), dict(name=GRACE, dept="HU"),
            dict(name=FARID, dept="HU"), dict(name=JOSEPH, dept="EL", role="Hod"), dict(name=MARCUS, dept="EL")]
PWS = {ALICIA: secret(), LEE: secret(), JOSEPH: secret()}
USERS = {ALICIA: "alicia.tan", LEE: "lee.kokhwa", JOSEPH: "joseph.lim"}
NOBODY_EXTRAS = dict(relief=False, exams=None, admin=False)
RECORDS = {ALICIA: dict(group="committee", username=USERS[ALICIA], pw=PW.hash_pw(PWS[ALICIA]), extras=dict(NOBODY_EXTRAS, admin=True)),
           LEE: dict(group="leader", added=True, username=USERS[LEE], pw=PW.hash_pw(PWS[LEE])),
           SITI: dict(group="sh", depts=[]),
           RAVI: dict(extras=dict(NOBODY_EXTRAS, exams=RAVI_UNTIL)),
           JOSEPH: dict(group="committee", username=USERS[JOSEPH], pw=PW.hash_pw(PWS[JOSEPH])),
           PRIYA: dict(group="executive", added=True, extras=dict(NOBODY_EXTRAS, relief=True))}

def publish():
    """what store.published() reads: a fake school with the teachers, one class and one student"""
    pub = RP.fake_pub(TEACHERS)
    pub["meta"].update(published_at="1 Nov 2026, 09:00", ok=True)
    pub["model"].update(classes=[dict(name="1A", level="Sec 1")], class_ix={}, teacher_ix={}, room_ix={}, students=[dict(id="S001", name="Sam Student", cls="1A")])
    os.makedirs(store.PUB, exist_ok=True)
    with open(os.path.join(store.PUB, "model.pkl"), "wb") as f: pickle.dump(pub["model"], f)
    store.write_json(os.path.join(store.PUB, "meta.json"), pub["meta"])
    store._cache.update(stamp=None, value=None)

publish()
P.update(lambda d: [d["people"].setdefault(n, {}).update(r) for n, r in RECORDS.items()])
SETUP = secondary()                                                         # the setup being edited: its school's departments and step 4
SETUP["teachers"] += [dict(name=x["name"], short=x["name"].split()[0], dept=x["dept"], role=" sh " if x["name"] == MARCUS else x.get("role"))
                      for x in TEACHERS] + [dict(name="Mr New Head", short="New", dept="SC", role="HOD")]   # not published: on no staff list
store.replace_setup(SETUP, "Saved")
DEPTS = store.setup_record()["spec"]["school"]["departments"]
assert {"SC", "HU", "MA", "EL"} <= set(DEPTS) and "XX" not in DEPTS
os.makedirs(os.path.dirname(RS.PATH), exist_ok=True)
store.write_json(RS.PATH, dict(team=[FARID]))                               # relief's own team list: moved at the admin page's first read

def pw_in(user, pw, c=None):
    c = c or A.app.test_client(); return c, c.post("/login/password", data=dict(username=user, password=pw))

def signed_in(name):
    """a fresh password sign-in of one of the accounts above"""
    c, r = pw_in(USERS[name], PWS[name]); assert r.status_code == 302 and r.headers["Location"].endswith("/home"), (name, r.status_code)
    return c

def admin(): return signed_in(ALICIA)

def as_person(name, via="code"):
    c = A.app.test_client()
    with c.session_transaction() as s:
        s.update(who=name, via=via, n=P.record(P.load(), name)["n"])
        if via == "password": s["exp"] = time.time() + 3600
    return c

def shared(role):
    c = A.app.test_client()
    with c.session_transaction() as s: s["role"] = role
    return c

def kept(c):
    with c.session_transaction() as s: return dict(s)

def rec(name): return P.record(P.load(), name)

def raw():
    with open(P.PATH, encoding="utf-8") as f: return f.read()

def accounts(): return H.read(kinds=["account"], limit=10 ** 6)

def post(c, url, **body):
    r = c.post(url, json=body); return r.status_code, r.get_json()

def went(r, where): return r.status_code == 302 and urllib.parse.urlsplit(r.headers["Location"]).path == where

def history_text():
    out = ""
    for p in glob.glob(os.path.join(H.DIR, "*.jsonl")):
        with open(p, encoding="utf-8") as f: out += f.read()
    return out

COUNT = 0
def t(f):
    global COUNT
    A.limiter.fails.clear(); A.lockout.fails.clear()
    f(); COUNT += 1
    return f

ROUTES = (("GET", "/api/admin/people"), ("POST", "/api/admin/person"), ("POST", "/api/admin/bulk"), ("POST", "/api/admin/reset"),
          ("GET", "/api/admin/ways"), ("POST", "/api/admin/shared-off"), ("GET", "/api/admin/students"))

@t
def the_people_list():
    c = admin()
    assert P.load()["migrated"] is False                                    # nothing has read the admin page yet
    r = c.get("/api/admin/people"); j = r.get_json()
    assert r.status_code == 200 and list(j) == ["people", "departments", "groups", "hints", "moved", "me"], (r.status_code, j)
    assert j["me"] == ALICIA and j["departments"] == DEPTS
    assert j["groups"] == [["committee", "Timetable committee"], ["leader", "School leader"], ["hod", "HOD"], ["sh", "SH"], ["teacher", "Teacher"],
                           ["executive", "Executive"]], j["groups"]
    assert j["hints"] == dict(heads_on_step4=[DANIEL, MARCUS], no_google=[], heads_no_dept=[SITI]), j["hints"]   # Joseph (Hod) is committee, Siti SH already
    real = store.setup_record                                                # no setup saved: the published step 4 (Marcus is no SH there)
    store.setup_record = lambda: dict(spec=None, saved_at=None, ts=0, v=0)
    try: assert c.get("/api/admin/people").get_json()["hints"]["heads_on_step4"] == [DANIEL]
    finally: store.setup_record = real
    assert f"{FARID}: Relief team (from relief's Team list)" in j["moved"], j["moved"]                  # relief's team list moved first
    by = {p["name"]: p for p in j["people"]}
    assert set(by) == {x["name"] for x in TEACHERS} | {LEE, PRIYA}, sorted(by)
    assert by[FARID]["extras"]["relief"] is True and by[LEE]["staff_only"] is True and by[LEE]["group"] == "leader"
    assert by[ALICIA]["has_password"] is True and by[ALICIA]["username"] == USERS[ALICIA] and by[NUR]["has_password"] is False
    assert by[RAVI]["extras"]["exams"] == RAVI_UNTIL and by[DANIEL]["group"] == "teacher" and by[PRIYA]["note"] == ""
    assert by[SITI]["group"] == "sh" and by[SITI]["depts"] == [], "a head with no department ticked is shown with none (step 4 has MA)"
    assert by[DANIEL]["depts"] == ["SC"], "anyone else: step 4's departments"
    assert all("pw" not in p and "n" not in p for p in j["people"])
    P.update(lambda d: d.update(moved=[]))                                   # nothing moved: [] and None alike
    assert c.get("/api/admin/people").get_json()["moved"] == []
    P.update(lambda d: d.update(moved=None))
    assert c.get("/api/admin/people").get_json()["moved"] == []
    r = c.get("/admin"); assert r.status_code in (200, 404) and not went(r, "/login"), r.status_code   # the page itself: Task 9's file
    r.close()

@t
def the_admin_routes_are_for_admins_only():
    clients = (A.app.test_client(), shared("committee"), shared("head"), shared("teacher"), signed_in(LEE), signed_in(JOSEPH), as_person(ALICIA, "code"))
    before, n = raw(), len(accounts())
    for who in clients:
        for method, url in ROUTES:
            r = who.open(url, method=method, json=dict(name=LEE, group="committee", extras=dict(admin=True), names=[LEE], action="give", extra="admin",
                                                        preview=False, code="teacher", off=True))
            assert r.status_code == 401 and r.get_json() == AGAIN, (method, url, r.status_code, r.get_json())
        r = who.get("/admin")
        if who in clients[1::4]:                                             # the shared committee code and a committee member: told, not sent away
            assert r.status_code == 403 and ONLY_ADMIN in r.get_data(as_text=True), r.status_code
        else: assert went(r, "/login"), r.status_code
    assert raw() == before and len(accounts()) == n, "a refused call changes nothing"
    assert rec(LEE)["extras"]["admin"] is False and rec(LEE)["group"] == "leader"

@t
def one_person_each_check_has_its_sentence():
    c = admin(); before, n = raw(), len(accounts())
    long = "A" * 101
    for body, want in ((dict(name=NUR, group="boss"), PICK_GROUP), (dict(name=NUR, group=None), PICK_GROUP),
                       (dict(name=NUR, extras=dict(admin=True)), ONLY_COMMITTEE), (dict(name=LEE, extras=dict(admin=True)), ONLY_COMMITTEE),
                       (dict(name=ALICIA, group="teacher"), last_admin(ALICIA)), (dict(name=ALICIA, off=True), last_admin(ALICIA)),
                       (dict(name=ALICIA, extras=dict(admin=False)), last_admin(ALICIA)),
                       (dict(name=ALICIA, username=None), last_admin(ALICIA)), (dict(name=ALICIA, username=""), last_admin(ALICIA)),
                       (dict(name=NUR, extras=dict(exams="")), EXAMS_DATE), (dict(name=NUR, extras=dict(exams=YESTERDAY)), EXAMS_DATE),
                       (dict(name=NUR, extras=dict(exams="2027-13-01")), EXAMS_DATE), (dict(name=NUR, extras=dict(exams=True)), EXAMS_DATE),
                       (dict(name=NUR, extras=dict(exams="20271114")), EXAMS_DATE),
                       (dict(name=NUR, username="ab"), BAD_USERNAME), (dict(name=NUR, username="nur aisyah"), BAD_USERNAME),
                       (dict(name=NUR, username="x" * 41), BAD_USERNAME), (dict(name=NUR, username="LEE.KOKHWA"), TAKEN),
                       (dict(name=SITI, depts=["MA", "XX"]), not_dept("XX")),
                       (dict(name="", added=True), "A staff member needs a name."), (dict(name="   ", added=True), "A staff member needs a name."),
                       (dict(name="=SUM(A1)", added=True), "A name cannot start with =."), (dict(name="@Mr X", added=True), "A name cannot start with @."),
                       (dict(name=long, added=True), "Keep a name under 100 characters."),
                       (dict(name=NUR, added=True), f"{NUR} is already a teacher on the timetable."), (dict(name=LEE, added=True), f"{LEE} is already on the staff list."),
                       (dict(name="Mr Not Here"), not_staff("Mr Not Here")), (dict(name=PRIYA, note="x" * 201), "Keep a note under 200 characters.")):
        code, j = post(c, "/api/admin/person", **body)
        assert code == 400 and j == {"error": want}, (body, code, j)
    for bad in ([], "x", dict(name=3), dict(name=NUR, extras="x"), dict(name=NUR, off="yes"), dict(name=NUR, depts="SC"), dict(name=NUR, extras=dict(relief=1))):
        r = c.post("/api/admin/person", json=bad); assert r.status_code == 400 and "error" in r.get_json(), (bad, r.status_code)
    assert raw() == before and len(accounts()) == n, "a refused change changes nothing"

@t
def one_person_changes_each_write_one_entry_and_sign_them_out_when_they_lessen():
    c = admin()
    def change(**body):
        n = len(accounts()); code, j = post(c, "/api/admin/person", **body); assert code == 200, (body, code, j)
        got = accounts(); assert len(got) == n + 1, (body, len(got) - n)
        e = got[0]; assert (e["kind"], e["who"], e["via"], e["people"], e["where"]) == ("account", ALICIA, "password", [body["name"].strip()], "Admin"), e
        return j, e
    dan = as_person(DANIEL)
    j, e = change(name=DANIEL, group="hod")                                  # a new head changes the map for their step-4 departments
    assert (j["name"], j["group"], j["depts"]) == (DANIEL, "hod", ["SC"]) and rec(DANIEL)["depts"] == ["SC"], j
    assert e["what"] == "group" and e["changes"] == [dict(name=DANIEL, field="group", was="teacher", now="hod"), dict(name=DANIEL, field="depts", was=[], now=["SC"])], e
    assert went(dan.get("/timetable"), "/login") and "who" not in kept(dan), "a group change signs them out everywhere"
    j, e = change(name=DANIEL, depts=[" SC", "MA", "SC"])
    assert j["depts"] == ["SC", "MA"] and e["what"] == "depts" and e["changes"] == [dict(name=DANIEL, field="depts", was=["SC"], now=["SC", "MA"])], e
    assert c.get("/api/admin/people").get_json()["hints"]["heads_on_step4"] == [MARCUS]
    n0 = rec(RAVI)["n"]
    j, e = change(name=RAVI, extras=dict(relief=True))
    assert j["extras"] == dict(relief=True, exams=RAVI_UNTIL, admin=False) and e["what"] == "extras" and rec(RAVI)["n"] == n0 + 1
    assert e["changes"] == [dict(name=RAVI, field="relief", was=False, now=True)], e
    j, e = change(name=RAVI, extras=dict(exams=None))
    assert j["extras"]["exams"] is None and e["changes"] == [dict(name=RAVI, field="exams", was=RAVI_UNTIL, now=None)]
    n0 = rec(NUR)["n"]
    j, e = change(name=NUR, username="Nur.Aisyah")                           # a first username: compared and kept in lower case
    assert j["username"] == "nur.aisyah" and rec(NUR)["n"] == n0, "a username given where none was signs no one out"
    assert e["what"] == "username" and e["changes"] == [dict(name=NUR, field="username", was=None, now="nur.aisyah")]
    j, e = change(name=NUR, username="nur.a"); assert rec(NUR)["n"] == n0 + 1, "a username changed signs them out"
    P.update(lambda d: d["people"][NUR].update(pw=PW.hash_pw(secret())))
    j, e = change(name=NUR, username=None)
    r = rec(NUR); assert r["username"] is None and r["pw"] is None and r["n"] == n0 + 2 and j["has_password"] is False, r
    assert e["changes"] == [dict(name=NUR, field="username", was="nur.a", now=None)], e
    n0 = rec(GRACE)["n"]
    j, e = change(name=GRACE, note="  Part-time  ")
    assert j["note"] == "Part-time" and e["what"] == "note" and rec(GRACE)["n"] == n0
    m = as_person(MARCUS)
    j, e = change(name=MARCUS, off=True)
    assert j["off"] is True and e["what"] == "off" and went(m.get("/timetable"), "/login")
    j, e = change(name=MARCUS, off=False); assert j["off"] is False and e["what"] == "on"
    j, e = change(name="  Ms Mei Ling Ho ", added=True, note="Front office")
    assert (j["name"], j["staff_only"], j["group"], j["note"]) == ("Ms Mei Ling Ho", True, "executive", "Front office"), j
    assert e["what"] == "add" and e["people"] == ["Ms Mei Ling Ho"] and rec("Ms Mei Ling Ho")["added"] is True
    n = len(accounts()); code, j = post(c, "/api/admin/person", name=GRACE, note="Part-time", group="teacher")
    assert code == 200 and len(accounts()) == n, "no change: no entry"
    # an admin's own change keeps this session and ends their others
    other = admin()
    j, e = change(name=ALICIA, extras=dict(relief=True))
    assert c.get("/api/admin/ways").status_code == 200 and went(other.get("/home"), "/login")
    # Admin for a committee member; leaving the committee ends it, while another admin is left
    j, e = change(name=JOSEPH, extras=dict(admin=True)); assert j["extras"]["admin"] is True and P.admins(P.load()) == [ALICIA, JOSEPH]
    j, e = change(name=JOSEPH, group="teacher")
    assert (j["group"], j["extras"]["admin"]) == ("teacher", False) and P.admins(P.load()) == [ALICIA], j
    assert e["changes"] == [dict(name=JOSEPH, field="group", was="committee", now="teacher"), dict(name=JOSEPH, field="admin", was=True, now=False)], e
    code, j = post(c, "/api/admin/person", name=JOSEPH, group="hod", extras=dict(admin=True)); assert (code, j) == (400, {"error": ONLY_COMMITTEE})
    change(name=JOSEPH, group="committee")
    # an Admin who cannot sign in (no username, or no password) keeps no one in: the last admin who can is still the last
    for siti in (dict(username=None, pw=None), dict(username="siti.rahmah", pw=None)):
        P.update(lambda d: d["people"][SITI].update(group="committee", extras=dict(NOBODY_EXTRAS, admin=True), **siti))
        assert P.admins(P.load()) == [ALICIA, SITI] and P.usable_admins(P.load()) == [ALICIA]
        before, n = raw(), len(accounts())
        for url, body in (("/api/admin/person", dict(name=ALICIA, extras=dict(admin=False))), ("/api/admin/person", dict(name=ALICIA, off=True)),
                          ("/api/admin/person", dict(name=ALICIA, username=None)), ("/api/admin/person", dict(name=ALICIA, group="teacher")),
                          ("/api/admin/bulk", dict(names=[ALICIA], action="take", extra="admin", preview=False)),
                          ("/api/admin/bulk", dict(names=[MARCUS, ALICIA], action="off", preview=True))):
            assert post(c, url, **body) == (400, {"error": last_admin(ALICIA)}), (url, body, post(c, url, **body))
        assert raw() == before and len(accounts()) == n, "refused: nothing changed"
    P.update(lambda d: d["people"][SITI].update(group="sh", username=None, pw=None, extras=dict(NOBODY_EXTRAS)))
    # another admin signs her out at the same moment as her own change: the sign-out holds (her number is read in the update)
    c2, real = admin(), P.update
    def racing(fn):
        P.update = real
        real(lambda d: d["people"][ALICIA].update(n=P.record(d, ALICIA)["n"] + 1))
        return real(fn)
    P.update = racing
    try: code, j = post(c2, "/api/admin/person", name=ALICIA, extras=dict(relief=False))
    finally: P.update = real
    assert code == 200 and j["extras"]["relief"] is False and went(c2.get("/home"), "/login") and "who" not in kept(c2)

@t
def ticking_four_previews_then_applies_all_in_one_entry():
    c = admin()
    P.update(lambda d: [d["people"].setdefault(n, {}).setdefault("extras", {}).update(exams=RAVI_UNTIL if n == RAVI else None) for n in FOUR])
    before, n, ns = raw(), len(accounts()), {x: rec(x)["n"] for x in FOUR}
    want = [f"{RAVI}, {NUR}, {WEI} and {GRACE} get the exams and events pages until {day(UNTIL)}.",
            f"{RAVI} has it already: their end date moves to {day(UNTIL)}."]
    code, j = post(c, "/api/admin/bulk", names=FOUR, action="give", extra="exams", until=UNTIL, preview=True)
    assert code == 200 and j["lines"] == want and j["applied"] is False, (code, j)
    assert raw() == before and len(accounts()) == n, "a preview changes nothing"
    code, j = post(c, "/api/admin/bulk", names=FOUR, action="give", extra="exams", until=UNTIL, preview=False)
    assert code == 200 and j["lines"] == want and j["applied"] is True, (code, j)
    assert all(rec(x)["extras"]["exams"] == UNTIL and rec(x)["n"] == ns[x] + 1 for x in FOUR)
    got = accounts(); assert len(got) == n + 1, "one entry for the lot"
    e = got[0]
    assert (e["what"], e["people"], e["who"], e["text"]) == ("extras", FOUR, ALICIA, f"Gave Exams and events until {day(UNTIL)} to {RAVI}, {NUR}, {WEI}, {GRACE}"), e
    assert e["changes"] == [dict(name=x, field="exams", was=RAVI_UNTIL if x == RAVI else None, now=UNTIL) for x in FOUR], e["changes"]
    code, j = post(c, "/api/admin/bulk", names=FOUR, action="give", extra="exams", until=UNTIL, preview=False)
    assert j == dict(lines=[f"{x} has it already, until {day(UNTIL)}: nothing changes for them." for x in FOUR], applied=False) and len(accounts()) == n + 1, j
    code, j = post(c, "/api/admin/bulk", names=[NUR, WEI], action="take", extra="relief", preview=True)
    assert j["lines"] == [f"{NUR} is not on the relief team.", f"{WEI} is not on the relief team."], j
    code, j = post(c, "/api/admin/bulk", names=[WEI], action="group", group="hod", preview=True)
    assert j["lines"] == [f"{WEI} moves to the HOD group.", f"{WEI} changes the map for HU (from step 4)."], j
    code, j = post(c, "/api/admin/bulk", names=[NUR, WEI], action="give", extra="relief", preview=True)
    assert j["lines"] == [f"{NUR} and {WEI} join the relief team."], j

@t
def ticking_several_with_the_last_admin_is_refused_whole():
    c = admin()
    assert P.admins(P.load()) == [ALICIA]
    before, n = raw(), len(accounts())
    for body, want in ((dict(names=[MARCUS, ALICIA], action="off"), last_admin(ALICIA)),
                       (dict(names=[NUR, ALICIA], action="group", group="teacher"), last_admin(ALICIA)),
                       (dict(names=[ALICIA], action="take", extra="admin"), last_admin(ALICIA)),
                       (dict(names=[NUR, JOSEPH], action="give", extra="admin"), ONLY_COMMITTEE),
                       (dict(names=FOUR, action="give", extra="exams"), EXAMS_DATE), (dict(names=FOUR, action="give", extra="exams", until=YESTERDAY), EXAMS_DATE),
                       (dict(names=[NUR, "Mr Not Here"], action="off"), not_staff("Mr Not Here")), (dict(names=[], action="off"), NO_ONE),
                       (dict(names=[NUR], action="explode"), "Pick what to do."), (dict(names=[NUR], action="give", extra="boss"), "Pick an extra."),
                       (dict(names=[NUR], action="group", group="boss"), PICK_GROUP)):
        for preview in (True, False):
            code, j = post(c, "/api/admin/bulk", preview=preview, **body)
            assert code == 400 and j == {"error": want}, (body, preview, code, j)
    assert raw() == before and len(accounts()) == n and rec(MARCUS)["off"] is False and rec(NUR)["group"] is None
    m = as_person(MARCUS)
    code, j = post(c, "/api/admin/bulk", names=[MARCUS, PRIYA], action="off", preview=False)
    assert code == 200 and j["lines"] == [f"{MARCUS} and {PRIYA} are switched off and signed out everywhere."] and j["applied"] is True, j
    assert went(m.get("/timetable"), "/login") and accounts()[0]["what"] == "off"
    code, j = post(c, "/api/admin/bulk", names=[MARCUS, PRIYA], action="on", preview=False)
    assert j["lines"] == [f"{MARCUS} and {PRIYA} can sign in again."] and accounts()[0]["what"] == "on" and not rec(PRIYA)["off"], j

@t
def a_reset_gives_a_one_time_password_shown_once():
    c = admin()
    out, err = io.StringIO(), io.StringIO()
    n0 = rec(NUR)["n"]
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        r = c.post("/api/admin/reset", json=dict(name=NUR, username="Nur.Aisyah"))
    j = r.get_json(); once = j["once"]; SECRETS.append(once)
    assert r.status_code == 200 and list(j) == ["once"] and "no-store" in r.headers.get("Cache-Control", ""), (r.status_code, j)
    x = rec(NUR); assert x["username"] == "nur.aisyah" and PW.check_pw(x["pw"], once) and x["must_change"] is True and x["n"] == n0 + 1, x
    e = accounts()[0]
    assert (e["what"], e["people"], e["who"]) == ("reset", [NUR], ALICIA) and e["changes"] == [dict(name=NUR, field="username", was=None, now="nur.aisyah")], e
    k, r = pw_in("nur.aisyah", once); assert went(r, "/account/password"), r.status_code
    r = k.get("/api/status"); assert r.status_code == 403 and r.get_json() == FIRST
    for text in (out.getvalue(), err.getvalue(), history_text(), raw(), json.dumps(e)): assert once not in text and once.replace("-", "") not in text
    code, j = post(c, "/api/admin/reset", name=NUR); once2 = j["once"]; SECRETS.append(once2)   # a second reset: the first one-time password stops
    assert code == 200 and once2 != once and went(k.get("/home"), "/login") and accounts()[0]["changes"] == []
    _, r = pw_in("nur.aisyah", once); assert r.status_code == 401
    for body, want in ((dict(name=WEI), NO_USERNAME), (dict(name=WEI, username="Lee.KokHwa"), TAKEN), (dict(name=WEI, username="x"), BAD_USERNAME),
                       (dict(name="Mr Not Here", username="mr.not"), not_staff("Mr Not Here"))):
        n = len(accounts()); code, j = post(c, "/api/admin/reset", **body)
        assert code == 400 and j == {"error": want} and len(accounts()) == n, (body, code, j)
    assert rec(WEI)["pw"] is None

@t
def a_password_session_ends_when_the_record_has_no_password():
    k = signed_in(LEE); assert k.get("/home").status_code == 200
    keep = rec(LEE)["pw"]
    P.update(lambda d: d["people"][LEE].update(pw=None))
    try: assert went(k.get("/timetable"), "/login") and "who" not in kept(k)
    finally: P.update(lambda d: d["people"][LEE].update(pw=keep))

@t
def the_ways_in():
    c = admin()
    j = c.get("/api/admin/ways").get_json()
    assert list(j) == ["secret_key", "personal_codes", "password_accounts", "shared", "recovery_set", "recovery_short", "recovery_warn"], j
    assert j["recovery_short"] is False and j["recovery_warn"] is None
    have = sum(1 for n in P.load()["people"] if rec(n)["username"] and rec(n)["pw"])
    assert (j["secret_key"], j["personal_codes"], j["password_accounts"], j["recovery_set"]) == (True, True, have, False), j
    assert [s["code"] for s in j["shared"]] == list(P.SHARED) and all(s["set"] is True and s["off"] is None for s in j["shared"]), j["shared"]
    week = {s["code"]: s["used_week"] for s in j["shared"]}
    tc = A.app.test_client(); r = tc.post("/login", data=dict(code=CODES["TEACHER_CODE"])); assert went(r, "/timetable")
    j = c.get("/api/admin/ways").get_json(); assert {s["code"]: s["used_week"] for s in j["shared"]} == dict(week, teacher=week["teacher"] + 1)
    code, j = post(c, "/api/admin/shared-off", code="teacher", off=True)
    sh = {s["code"]: s for s in j["shared"]}
    assert code == 200 and isinstance(sh["teacher"]["off"], (int, float)) and sh["student"]["off"] is None, j
    assert went(tc.get("/timetable"), "/login") and "role" not in kept(tc), "an open session with the code ends"
    e = accounts()[0]
    assert (e["what"], e["shared"], e["who"]) == ("shared-off", "teacher", ALICIA), e
    assert e["changes"] == [dict(name="Shared teacher code", field="off", was=None, now=sh["teacher"]["off"])], e
    code, j = post(c, "/api/admin/shared-off", code="teacher", off=True); assert accounts()[0]["id"] == e["id"], "already off: no entry"
    code, j = post(c, "/api/admin/shared-off", code="teacher", off=False)
    assert all(s["off"] is None for s in j["shared"]) and accounts()[0]["what"] == "shared-off" and accounts()[0]["changes"][0]["now"] is None
    for body in (dict(code="boss", off=True), dict(code="teacher"), dict(code="teacher", off="yes")):
        code, j = post(c, "/api/admin/shared-off", **body); assert code == 400 and "error" in j, (body, j)
    assert post(c, "/api/admin/shared-off", code="boss", off=True)[1] == {"error": "Pick a shared code."}
    os.environ["ADMIN_RECOVERY_CODE"] = secret(); SECRETS.append(os.environ["ADMIN_RECOVERY_CODE"])
    try:
        w = c.get("/api/admin/ways").get_json()
        assert (w["recovery_set"], w["recovery_short"], w["recovery_warn"]) == (True, False, RECOVERY_ON), w   # warned until it is removed
        os.environ["ADMIN_RECOVERY_CODE"] = secrets.token_hex(7)              # 14 letters or digits: too short, so off
        w = c.get("/api/admin/ways").get_json()
        assert (w["recovery_set"], w["recovery_short"], w["recovery_warn"]) == (False, True, RECOVERY_SHORT), w
        assert RECOVERY_SHORT in A.setup_problems()
    finally: os.environ.pop("ADMIN_RECOVERY_CODE")
    j = c.get("/api/admin/ways").get_json(); assert (j["recovery_set"], j["recovery_short"], j["recovery_warn"]) == (False, False, None)
    js = open(os.path.join(ROOT, "static", "admin.js"), encoding="utf-8").read()
    assert "w.recovery_warn ? `<div class=\"hint\">${esc(w.recovery_warn)}</div>`" in js and "Too short: recovery is off" in js
    old = os.environ.pop("SECRET_KEY")                                       # accounts are refused without SECRET_KEY
    try:
        for method, url in ROUTES:
            r = c.open(url, method=method, json={}); assert r.status_code == 403 and r.get_json() == {"error": NO_ACCOUNTS}, (url, r.status_code)
    finally: os.environ["SECRET_KEY"] = old
    for x in CODES.values(): assert x not in history_text()

@t
def the_students_list():
    j = admin().get("/api/admin/students").get_json()
    assert j == [{"id": "S001", "name": "Sam Student", "class": "1A"}], j

@t
def code_slips_for_the_ticked_people():
    seen, real = [], A.relief_codes.slips_pdf
    def fake(school, people, url, out): seen.append([p["name"] for p in people]); out.write(b"%PDF-"); return out
    A.relief_codes.slips_pdf = fake
    try:
        c = admin()
        r = c.get("/api/relief/code-slips.pdf", query_string=dict(names=f"{NUR}, {RAVI},Mr Not Here")); assert r.status_code == 200 and r.data == b"%PDF-"
        assert sorted(seen[-1]) == sorted([NUR, RAVI]), seen[-1]
        assert c.get("/api/relief/code-slips.pdf").status_code == 200 and len(seen[-1]) == len(A.relief_staff(store.published()))
        r = c.get("/api/relief/code-slips.pdf", query_string=dict(names="Mr Not Here")); assert r.status_code == 400 and r.get_json() == {"error": NO_ONE}
    finally: A.relief_codes.slips_pdf = real

@t
def the_first_admin_is_offered_while_no_admin_can_sign_in():
    keep = {k: rec(ALICIA)[k] for k in ("username", "pw")}
    status = lambda: shared("committee").get("/api/status").get_json()["admin_exists"]
    assert P.admins(P.load()) == P.usable_admins(P.load()) == [ALICIA] and status() is True
    assert shared("committee").get("/admin/first").status_code == 404
    P.update(lambda d: d["people"][ALICIA].update(username=None, pw=None))   # the only admin has no username (so no password)
    try:
        assert P.admins(P.load()) == [ALICIA] and P.usable_admins(P.load()) == []
        r = shared("committee").get("/admin/first"); assert r.status_code == 200 and 'name="new"' in r.data.decode(), r.status_code
        assert status() is False
        P.update(lambda d: d["people"][ALICIA].update(username=keep["username"]))   # a username but no password: still no one who can sign in
        assert shared("committee").get("/admin/first").status_code == 200 and status() is False
    finally: P.update(lambda d: d["people"][ALICIA].update(**keep))
    assert shared("committee").get("/admin/first").status_code == 404 and status() is True

@t
def the_first_admin_once_and_only_for_the_committee():
    P.update(lambda d: [r["extras"].update(admin=False) for r in d["people"].values() if isinstance(r.get("extras"), dict)])
    assert P.admins(P.load()) == []
    try:
        for who in (as_person(MARCUS), signed_in(LEE), shared("head"), shared("teacher"), A.app.test_client()):
            assert went(who.get("/admin/first"), "/login") and went(who.post("/admin/first", data={}), "/login")
        com = shared("committee")
        old = os.environ.pop("SECRET_KEY")
        try:
            r = com.get("/admin/first"); assert r.status_code == 403 and NO_ACCOUNTS in r.data.decode() and 'name="new"' not in r.data.decode()
        finally: os.environ["SECRET_KEY"] = old
        r = com.get("/admin/first"); page = r.data.decode()
        assert r.status_code == 200 and all(f'name="{k}"' in page for k in ("name", "username", "new", "again")) and f'value="{DANIEL}"' in page, page[:400]
        assert signed_in(JOSEPH).get("/admin/first").status_code == 200, "a committee member signed in with their password may too"
        good = secret()
        for form, want in ((dict(name="Ms Wendy Ang", username="wendy.ang", new=good, again=secret()), "The two new passwords are not the same."),
                           (dict(name="Ms Wendy Ang", username="wendy.ang", new="short", again="short"), "Use at least 10 characters."),
                           (dict(name="Ms Wendy Ang", username="w", new=good, again=good), BAD_USERNAME),
                           (dict(name="Ms Wendy Ang", username="LEE.KOKHWA", new=good, again=good), TAKEN),
                           (dict(name="=Wendy", username="wendy.ang", new=good, again=good), "A name cannot start with =."),
                           (dict(name="", username="wendy.ang", new=good, again=good), "A staff member needs a name.")):
            r = com.post("/admin/first", data=form); assert r.status_code == 400 and want in r.data.decode(), (form["username"], want, r.status_code)
            assert good not in r.data.decode()
        keep = rec(LEE)["pw"]                                                # someone else's password is never replaced here
        r = com.post("/admin/first", data=dict(name=LEE, username=USERS[LEE], new=good, again=good))
        assert r.status_code == 400 and f"{LEE} has a password already: they make themselves the first admin, signed in with it." in r.data.decode()
        assert rec(LEE)["pw"] == keep and P.admins(P.load()) == []
        n = len(accounts())
        r = com.post("/admin/first", data=dict(name="  Ms Wendy Ang ", username="Wendy.Ang", new=good, again=good))
        assert went(r, "/admin"), (r.status_code, r.data[:300])
        s = kept(com); assert (s["who"], s["via"]) == ("Ms Wendy Ang", "password") and "role" not in s, s
        w = rec("Ms Wendy Ang")
        assert (w["group"], w["extras"]["admin"], w["added"], w["username"], w["must_change"], w["off"]) == ("committee", True, True, "wendy.ang", False, False), w
        assert PW.check_pw(w["pw"], good) and P.admins(P.load()) == ["Ms Wendy Ang"]
        got = accounts(); assert len(got) == n + 1
        e = got[0]; assert (e["what"], e["people"], e["who"], e["as"]) == ("first-admin", ["Ms Wendy Ang"], None, "Shared committee code"), e
        assert not any(c["field"] in ("pw", "password") for c in e["changes"]) and good not in history_text()
        assert com.get("/api/admin/people").get_json()["me"] == "Ms Wendy Ang"
        for who in (shared("committee"), signed_in(JOSEPH)):
            assert who.get("/admin/first").status_code == 404 and who.post("/admin/first", data=dict(name="X Y", username="x.y", new=good, again=good)).status_code == 404
        assert P.admins(P.load()) == ["Ms Wendy Ang"]
    finally:
        P.update(lambda d: d["people"][ALICIA]["extras"].update(admin=True))

@t
def a_head_with_every_department_unticked_has_none():
    c = admin()
    P.update(lambda d: d["people"].setdefault(MARCUS, {}).update(group="sh", depts=["EL"]))
    try:
        code, j = post(c, "/api/admin/person", name=MARCUS, depts=[])
        assert code == 200 and (j["group"], j["depts"]) == ("sh", []) and rec(MARCUS)["depts"] == [], (code, j)
        e = accounts()[0]; assert e["changes"] == [dict(name=MARCUS, field="depts", was=["EL"], now=[])] and e["text"] == f"{MARCUS}: changes the map for no department", e
        j = c.get("/api/admin/people").get_json(); by = {p["name"]: p for p in j["people"]}
        assert by[MARCUS]["depts"] == [] and MARCUS in j["hints"]["heads_no_dept"], (by[MARCUS], j["hints"])
        with A.app.test_request_context():                                   # what the server gives him: none either (R8)
            A.session.update(who=MARCUS, via="password", n=rec(MARCUS)["n"], exp=time.time() + 60)
            P.update(lambda d: d["people"][MARCUS].update(pw=PW.hash_pw(secret())))
            assert A.head_depts() == [] and A.who()["depts"] == []
        s = as_person(MARCUS).get("/api/relief/me").get_json()
        assert s["depts"] == ["EL"], "relief keeps step 4's departments for a head with none ticked, explicitly"
    finally: P.update(lambda d: d["people"][MARCUS].update(group=None, depts=[], pw=None))

@t
def an_admin_s_own_change_is_recorded_under_their_name_even_when_it_ends_their_session():
    keep = {k: rec(JOSEPH)[k] for k in ("username", "pw")}
    P.update(lambda d: d["people"][JOSEPH].setdefault("extras", {}).update(admin=True))
    try:
        j = signed_in(JOSEPH)
        code, out = post(j, "/api/admin/person", name=JOSEPH, username=None)   # no username, so no password: this session ends
        assert code == 200 and out["username"] is None, (code, out)
        e = accounts()[0]
        assert (e["what"], e["who"], e["as"], e["via"], e["where"]) == ("username", JOSEPH, JOSEPH, "password", "Admin"), e
        assert j.get("/api/admin/people").status_code == 401
        P.update(lambda d: d["people"][JOSEPH].update(**keep))
        j = signed_in(JOSEPH)
        code, out = post(j, "/api/admin/bulk", names=[JOSEPH], action="off", preview=False)
        assert code == 200 and out["applied"] is True, out
        e = accounts()[0]; assert (e["what"], e["who"], e["as"], e["where"]) == ("off", JOSEPH, JOSEPH, "Admin"), e
    finally:
        P.update(lambda d: (d["people"][JOSEPH].update(off=False, **keep), d["people"][JOSEPH]["extras"].update(admin=False)))

@t
def keys_this_version_does_not_know_survive_an_admin_change():
    P.update(lambda d: (d["people"][GRACE].update(later_key={"kept": [1, 2]}), d["people"][GRACE].setdefault("extras", {}).update(later_extra="2027-01-01")))
    try:
        assert rec(GRACE)["later_key"] == {"kept": [1, 2]} and rec(GRACE)["extras"]["later_extra"] == "2027-01-01"
        c = admin()
        code, j = post(c, "/api/admin/person", name=GRACE, note="Kept through a change", extras=dict(relief=True)); assert code == 200, j
        code, j = post(c, "/api/admin/bulk", names=[GRACE], action="take", extra="relief", preview=False); assert code == 200, j
        stored = json.loads(raw())["people"][GRACE]
        assert stored["later_key"] == {"kept": [1, 2]} and stored["extras"]["later_extra"] == "2027-01-01", stored
        assert stored["note"] == "Kept through a change" and stored["extras"]["relief"] is False
    finally:
        P.update(lambda d: (d["people"][GRACE].pop("later_key", None), d["people"][GRACE]["extras"].pop("later_extra", None)))

@t
def every_account_entry_is_under_admin():
    got = accounts(); assert got and {e["what"] for e in got} >= {"moved", "group", "reset", "off", "first-admin", "shared-off"}, {e["what"] for e in got}
    assert all(e.get("where") == "Admin" for e in got), [e for e in got if e.get("where") != "Admin"][:1]
    c = admin()
    j = c.get("/api/history", query_string=dict(where="Admin")).get_json()
    assert j["entries"] and all(e["kind"] == "account" for e in j["entries"]), j["entries"][:1]

@t
def no_password_or_code_in_the_history():
    text = history_text()
    for s in SECRETS: assert s not in text, "a secret reached the history"
    for e in accounts():
        assert not ({"pw", "password", "once"} & set(e)) and all(c["field"] not in ("pw", "password", "once", "must_change") for c in e.get("changes") or []), e

import putback  # noqa: E402
def putback_admin_sentence(): return putback._ADMIN
def back(c, eid): return post(c, "/api/history/back", id=eid)

@t
def put_back_a_bulk_change():
    c = admin()
    P.update(lambda d: [d["people"].setdefault(n, {}).setdefault("extras", {}).update(exams=None) for n in (NUR, WEI)])
    n0, ns = len(accounts()), {x: rec(x)["n"] for x in (NUR, WEI)}
    assert post(c, "/api/admin/bulk", names=[NUR, WEI], action="give", extra="exams", until=UNTIL, preview=False)[0] == 200
    e = accounts()[0]; assert len(accounts()) == n0 + 1
    code, j = back(c, e["id"]); assert (code, j) == (200, dict(done=True, text="Put back.")), (code, j)
    assert all(rec(x)["extras"]["exams"] is None and rec(x)["n"] == ns[x] + 2 for x in (NUR, WEI)), "gone, and signed out again"
    got = accounts(); assert len(got) == n0 + 2
    p = got[0]
    assert (p["what"], p["people"], p["text"], p["putback_of"], p["putback_ts"]) == ("putback", [NUR, WEI], "Put back: " + e["text"], e["as"], e["ts"]), p
    assert p["putback"].startswith("a:"), p
    assert p["changes"] == [dict(name=x, field="exams", was=UNTIL, now=None) for x in (NUR, WEI)], p["changes"]
    assert back(c, e["id"])[0] == 409, "put back twice is refused"

@t
def put_back_a_group_change():
    c = admin()
    assert rec(NUR)["group"] in (None, "teacher") and not rec(NUR)["depts"]
    assert post(c, "/api/admin/person", name=NUR, group="hod")[0] == 200 and rec(NUR)["depts"] == ["HU"]
    e = accounts()[0]
    code, j = back(c, e["id"]); assert code == 200, (code, j)
    r = rec(NUR); assert (r["group"] or "teacher") == "teacher" and r["depts"] == [], r
    assert accounts()[0]["changes"] == [dict(name=NUR, field="group", was="hod", now="teacher"), dict(name=NUR, field="depts", was=["HU"], now=[])]

@t
def put_back_refused_after_a_later_change():
    c = admin()
    assert post(c, "/api/admin/person", name=WEI, group="hod")[0] == 200
    first = accounts()[0]
    assert post(c, "/api/admin/person", name=WEI, group="executive")[0] == 200
    before, n = raw(), len(accounts())
    code, j = back(c, first["id"])
    assert code == 409 and j["error"].startswith(f"Can't put back: {ALICIA} changed this again on "), (code, j)
    assert raw() == before and len(accounts()) == n

@t
def put_back_refused_when_the_value_moved_under_it():
    c = admin()
    assert post(c, "/api/admin/person", name=GRACE, extras=dict(relief=True))[0] == 200
    e = accounts()[0]
    P.update(lambda d: d["people"][GRACE]["extras"].update(relief=False))      # changed outside the history
    before, n = raw(), len(accounts())
    assert back(c, e["id"]) == (409, {"error": "Can't put back: this was changed again since."})
    P.update(lambda d: d["people"][GRACE]["extras"].update(relief=True))
    # a person no longer on the staff list
    P.update(lambda d: d["people"].setdefault("Mr Ghost", {}).update(added=True, group="executive"))
    assert post(c, "/api/admin/person", name="Mr Ghost", note="x")[0] == 200
    g = accounts()[0]
    P.update(lambda d: d["people"]["Mr Ghost"].update(added=False))
    code, j = back(c, g["id"]); assert (code, j) == (409, {"error": "Can't put back: Mr Ghost is no longer on the staff list."}), (code, j)
    P.update(lambda d: d["people"].pop("Mr Ghost", None))

@t
def put_back_keeps_an_admin():
    c = admin()
    assert post(c, "/api/admin/person", name=JOSEPH, extras=dict(admin=True))[0] == 200
    e = accounts()[0]
    assert post(c, "/api/admin/person", name=ALICIA, off=True)[0] == 200
    others = [n for n in P.admins(P.load()) if n != JOSEPH]                  # earlier tests left another admin: off for this test
    P.update(lambda d: [d["people"][n].update(off=True) for n in others])
    assert P.usable_admins(P.load()) == [JOSEPH]
    jc = signed_in(JOSEPH)
    before, n = raw(), len(accounts())
    got =back(jc, e["id"]); assert got == (409, {"error": last_admin(JOSEPH)}), got
    assert raw() == before and len(accounts()) == n and rec(JOSEPH)["extras"]["admin"] is True
    P.update(lambda d: [d["people"][n].update(off=False) for n in others + [ALICIA]])
    P.update(lambda d: d["people"][JOSEPH]["extras"].update(admin=False))

@t
def put_back_an_added_person_says_where():
    c = admin()
    assert post(c, "/api/admin/person", name="Mr Zed Added", added=True)[0] == 200
    e = accounts()[0]
    code, j = back(c, e["id"])
    assert code == 409 and j["error"] == putback_admin_sentence(), (code, j)
    mine = [x for x in c.get("/api/history", query_string=dict(where="Admin")).get_json()["entries"] if x["id"] == e["id"]][0]
    assert mine["back"]["ok"] is False and mine["back"]["why"] == j["error"], mine.get("back")

@t
def only_an_admin_puts_back_accounts():
    c = admin()
    assert post(c, "/api/admin/person", name=PRIYA, note="back me")[0] == 200
    e = accounts()[0]
    P.update(lambda d: d["people"][JOSEPH]["extras"].update(admin=False))
    jc = signed_in(JOSEPH)                                                   # committee, with a password, no Admin
    j = jc.get("/api/history", query_string=dict(where="Admin")).get_json()
    assert all("back" not in x for x in j["entries"] if x["id"] == e["id"]), j["entries"][:1]
    before = raw()
    code, k = back(jc, e["id"]); assert code == 403, (code, k)
    assert raw() == before and rec(PRIYA)["note"] == "back me"

@t
def put_back_a_broken_account_line_says_so():
    c = admin()
    g = dict(field="group", was="teacher", now="hod")
    for changes in ([g], [dict(name=NUR)], [dict(g, name=["x"])], [dict(g, name=NUR, field=5)], "group", [3]):
        e = H.add({"kind": "account", "what": "group", "where": "Admin", "people": [NUR], "changes": changes, "text": "hand-edited", **H.by_of(ALICIA, "password")})
        before = raw()
        assert back(c, e["id"]) == (409, {"error": "This change cannot be put back here."}), changes
        assert raw() == before
        mine = [x for x in c.get("/api/history", query_string=dict(where="Admin")).get_json()["entries"] if x["id"] == e["id"]]
        assert mine and "back" not in mine[0], mine

print(f"{COUNT} admin tests passed")

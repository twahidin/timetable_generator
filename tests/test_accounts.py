"""Plain-assert tests for accounts: .venv/bin/python tests/test_accounts.py"""
import itertools, os, re, secrets, sys, tempfile, threading
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
    return dict(group=group, extras={**dict(relief=False, exams=None, admin=False, timetable=False), **extras}, off=False)

def member(group=None, **extras):
    """a Timetable committee member (the tick), with a role or none"""
    return person(group, timetable=True, **extras)

@t
def rights_table():
    S = lambda who: R.rights(None, "shared", who)
    assert S("committee") == {"committee", "setup", "timetable", "files", "history", "codes", "relief.settings", "relief.save"}
    assert S("head") == {"setup", "timetable", "files"} and S("teacher") == {"timetable", "files"} and S("student") == {"timetable"}
    assert R.rights(None, "personal") == {"own"}
    base = {"timetable", "files"}
    assert R.rights(person("executive"), "code") == base | {"history.own"}
    assert R.rights(person("teacher"), "code") == base | {"relief", "history.own"}
    assert R.rights(person("leader"), "code") == base | {"relief", "relief.plan", "relief.settings", "history.own"}
    assert R.rights(person("hod"), "code") == base | {"relief", "relief.plan", "relief.settings", "history.own"}
    c = R.rights(member(), "code")
    assert c == base | {"relief", "relief.settings", "relief.save", "history.own"} and not c & {"committee", "setup", "admin", "history", "codes"}
    assert "relief.plan" in R.rights(person("hod"), "code") and "setup" not in R.rights(person("hod"), "code")
    assert R.rights(person("executive", relief=True) if False else dict(person("executive"), extras=dict(relief=True, exams=None, admin=False)), "code") == base | {"relief", "relief.plan", "relief.settings", "relief.save", "relief.team", "history.own"}
    cs = R.rights(member(), "password")
    assert cs == base | {"relief", "relief.settings", "relief.save", "committee", "setup", "history", "codes", "history.own"}
    assert "admin" in R.rights(dict(member(), extras=dict(relief=False, exams=None, admin=True, timetable=True)), "password")
    assert "admin" not in R.rights(dict(member(), extras=dict(relief=False, exams=None, admin=True, timetable=True)), "code")
    assert "admin" not in R.rights(dict(person("hod"), extras=dict(relief=False, exams=None, admin=True, timetable=False)), "password")
    for g in ("hod", "sh"): assert "setup" in R.rights(person(g), "google")
    assert "setup" not in R.rights(person("teacher"), "password")
    today = datetime.date(2026, 11, 21); iso = lambda d: d.isoformat()
    ex = lambda d: R.rights(dict(person("teacher"), extras=dict(relief=False, exams=iso(d), admin=False)), "code", today=today)
    assert "exams" not in ex(today - datetime.timedelta(days=1)) and "exams" in ex(today)
    assert R.rights(dict(member(), off=True), "password") == frozenset()

@t
def history_rights_by_group():
    hp = R.rights(person("hod"), "password"); assert "history.dept" in hp and "history.own" in hp and "history" not in hp
    hc = R.rights(person("hod"), "code"); assert "history.own" in hc and "history.dept" not in hc   # relief settings is a change
    for g in ("teacher", "executive", "leader"):   # anyone signed in by name can change something now (relief, their own events)
        own = R.rights(person(g), "code"); assert "history.own" in own and not {"history", "history.dept"} & own, g
    ex = dict(person("executive"), extras=dict(relief=False, exams="2999-12-31", admin=False))
    assert "history.own" in R.rights(ex, "code")
    assert {"history", "history.own"} <= R.rights(member(), "password")
    assert R.rights(dict(person("hod"), off=True), "password") == frozenset()
    assert not {"history.dept", "history.own"} & (R.rights(None, "shared", "committee") | R.rights(None, "shared", "head"))

def pub():
    return fake_pub([dict(name="Ms Test One", dept="Sci"), dict(name="Mr Test Two", dept="Maths")])

@t
def staff_merges_records():
    d = P.blank()
    d["people"]["Ms Added"] = dict(P.record(d, "Ms Added"), added=True, pw="HASHSECRET", signins=[3, 9, 5])
    d["people"]["Ms Boss"] = dict(P.record(d, "Ms Boss"), group="committee", username="ms.boss", pw="HASHSECRET")   # the old shape: read as the tick
    s = {x["name"]: x for x in P.staff(pub(), d)}
    assert s["Ms Test One"]["group"] == "teacher" and s["Ms Test One"]["depts"] == ["Sci"] and not s["Ms Test One"]["has_password"]
    assert s["Ms Added"]["group"] == "executive" and s["Ms Added"]["has_password"] and s["Ms Added"]["last"] == 9
    assert "HASHSECRET" not in repr(list(s.values())) and all("pw" not in x for x in s.values())
    f = P.find("Ms Boss", pub(), d)
    assert f["group"] == "executive" and f["extras"]["timetable"] is True and f["pw"] == "HASHSECRET" and f["n"] == 0 and f["must_change"] is False
    assert P.find("Nobody", pub(), d) is None and P.find("Ms Test One", pub(), d)["name"] == "Ms Test One"
    assert P.by_username(d, " MS.Boss ")[0] == "Ms Boss" and P.by_username(d, "zz") == (None, None)
    assert P.admins(d) == []
    d["people"]["Ms Boss"]["extras"] = dict(admin=True); assert P.admins(d) == ["Ms Boss"]
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
    assert s["Ms Bad"]["last"] is None and s["Ms Bad"]["extras"] == dict(timetable=False, relief=False, exams=None, admin=False)
    f = P.find("Ms Bad", pub(), d); assert f["pw"] == "garbage"
    assert not PW.check_pw(f["pw"], "anything") and not PW.check_pw("pbkdf2:sha256:bad", "x")
    assert P.sweep(d, datetime.date(2026, 11, 21)) == []
    assert R.rights(f, "password") >= {"setup"}
    assert P.record(d, "Mr Bad")["depts"] == ["Sci"] and P.record(d, "Mr Bad")["signins"] == [1] and P.record(d, "Mr Bad")["group"] is None
    assert P.admins(d) == []

@t
def unknown_keys_are_kept_and_known_ones_cleaned():
    d = P.blank()
    d["people"]["Ms Later"] = dict(group="hod", added=True, depts=[" Sci "], later={"a": [1]}, extras=dict(relief="yes", later_extra=3), n="x")
    r = P.record(d, "Ms Later")
    assert r["later"] == {"a": [1]} and r["extras"] == dict(later_extra=3, timetable=False, relief=False, exams=None, admin=False), r
    assert r["depts"] == ["Sci"] and r["n"] == 0 and r["group"] == "hod"
    r["later"]["a"].append(2); assert d["people"]["Ms Later"]["later"] == {"a": [1]}, "a copy: the data is not changed through it"
    s = {x["name"]: x for x in P.staff(pub(), d)}; assert "later" not in s["Ms Later"], "only the known fields reach a staff item"
    P.update(lambda x: x["people"].update({"Ms Later": dict(d["people"]["Ms Later"])}))
    P.update(lambda x: x["people"].update({"Ms Later": dict(P.record(x, "Ms Later"), note="changed")}))   # a read-modify-write
    got = P.load()["people"]["Ms Later"]; assert got["later"] == {"a": [1]} and got["extras"]["later_extra"] == 3 and got["note"] == "changed", got
    P.update(lambda x: x["people"].pop("Ms Later"))

@t
def a_head_s_departments_are_their_record_s_and_the_listing_carries_no_account_field():
    d = P.blank()
    d["people"]["Ms Test One"] = dict(group="hod", depts=[])
    d["people"]["Mr Test Two"] = dict(group="sh", depts=["Sci"])
    d["people"]["Ms Added"] = dict(added=True, username="ms.added", pw="HASHSECRET")
    s = {x["name"]: x for x in P.staff(pub(), d)}
    assert s["Ms Test One"]["depts"] == [] and s["Mr Test Two"]["depts"] == ["Sci"], s   # none ticked stays none; step 4 says Sci and Maths
    ls = P.listing(pub(), d)
    assert [x["name"] for x in ls] == ["Mr Test Two", "Ms Test One", "Ms Added"], [x["name"] for x in ls]   # relief's order: by department, none last
    assert all(set(x) == {"name", "short", "depts", "role", "teaches", "staff_only"} for x in ls), ls
    assert {x["name"]: x["depts"] for x in ls} == {"Ms Test One": ["Sci"], "Mr Test Two": ["Maths"], "Ms Added": []}, "step 4's departments"
    assert "HASHSECRET" not in repr(ls) and "ms.added" not in repr(ls)

@t
def the_moved_flag_is_a_real_boolean():
    assert P.blank()["migrated"] is False and P._fill({"migrated": "yes"})["migrated"] is False and P._fill({"migrated": True, "moved": ["x"]})["moved"] == ["x"]

OLD_GROUPS = (None, "committee", "leader", "hod", "sh", "teacher", "executive")

# a verbatim copy of the rights as they were before the Timetable committee became a tick (the proof that nobody's rights change)

OLD_STRONG = {"password", "google"}
OLD_SHARED = {
    "committee": {"committee", "setup", "timetable", "files", "history", "codes", "relief.settings", "relief.save"},
    "head": {"setup", "timetable", "files"},
    "teacher": {"timetable", "files"},
    "student": {"timetable"},
}

def old_rights(person, via, shared=None, today=None):
    if via == "personal": return frozenset({"own"})
    if person is None:
        return frozenset(OLD_SHARED.get(shared, ())) if via == "shared" else frozenset()
    if person.get("off"): return frozenset()
    g, ex = person.get("group"), person.get("extras") or {}
    r = {"timetable", "files"}
    if g in ("teacher", "leader", "hod", "sh", "committee"): r.add("relief")
    if g in ("leader", "hod", "sh"): r |= {"relief.plan", "relief.settings"}
    if g == "committee": r |= {"relief.settings", "relief.save"}
    if ex.get("relief"): r |= {"relief", "relief.plan", "relief.settings", "relief.save", "relief.team"}
    until = ex.get("exams")
    if until and until >= (today or datetime.date.today()).isoformat(): r.add("exams")
    if via in OLD_STRONG:
        if g == "committee":
            r |= {"committee", "setup", "history", "codes"}
            if ex.get("admin"): r.add("admin")
        if g in ("hod", "sh"): r |= {"setup", "history.dept"}
    r.add("history.own")   # anyone signed in by name can change something (ask for relief, start an event), so sees their own history
    return frozenset(r)

@t
def the_committee_group_reads_as_a_tick():
    P.update(lambda d: d["people"].update({"Old Shape": {"group": "committee", "extras": {"admin": True, "later": 7}}}))
    r = P.record(P.load(), "Old Shape")
    assert r["group"] is None and r["extras"]["timetable"] is True and r["extras"]["admin"] is True and r["extras"]["later"] == 7, r
    P.update(lambda d: d["people"].update({"Old Shape": P.record(d, "Old Shape")}))            # saved once in the new shape
    stored = P.load()["people"]["Old Shape"]
    assert stored["group"] is None and stored["extras"]["timetable"] is True, stored
    assert P.record(P.load(), "Old Shape") == r                                                # reading again changes nothing
    assert "Old Shape" in P.admins(P.load())
    P.update(lambda d: d["people"].pop("Old Shape"))

@t
def nobody_s_rights_change_on_the_day():
    today = datetime.date(2026, 11, 23)
    for g, relief, exams, admin, off, via in itertools.product(OLD_GROUPS, (False, True), (None, "2026-11-22", "2026-12-31"), (False, True), (False, True), ("code", "password", "google")):
        stored = {"group": g, "extras": {"relief": relief, "exams": exams, "admin": admin}, "off": off}
        for default in ("teacher", "executive"):                                               # what the staff list shows while no group is set
            before = dict(stored, group=g or default)
            new = P._clean(dict(stored))
            after = dict(new, group=new["group"] or default)
            assert R.rights(after, via, today=today) == old_rights(before, via, today=today), (stored, default, via)

@t
def what_a_role_and_committees_give():
    T = datetime.date(2026, 11, 23)
    hod = dict(group="hod", extras=dict(timetable=False, relief=False, exams=None, admin=False), off=False)
    assert [g["text"] for g in R.gives(hod, ["MA"], T)] == ["Sees the published timetable and the files.", "Relief: plans cover, as management.",
        "Setup: changes the teaching groups of MA only.", "History: sees their departments' changes."]
    assert R.gives(hod, [], T)[2] == {"text": "Setup: no department ticked yet, so nothing to change.", "strong": True}
    full = dict(group="hod", extras=dict(timetable=True, relief=True, exams="2026-12-31", admin=True), off=False)
    assert [g["text"] for g in R.gives(full, ["MA"], T)] == ["Sees the published timetable and the files.", "Relief: runs it, with the team's pages and settings.",
        "Setup: every step, the upload, the edit board and Publish.", "Exams and events: plans them and approves them.", "History: sees everyone's changes.", "People and access: this page."]
    ex = dict(group="executive", extras=dict(timetable=False, relief=False, exams="2026-12-31", admin=False), off=False)
    assert [g["text"] for g in R.gives(ex, [], T)] == ["Sees the published timetable and the files.", "Exams and events: plans them, until 31 Dec 2026."]
    assert R.gives(dict(full, off=True), ["MA"], T) == [{"text": "Nothing: switched off, so they cannot sign in.", "strong": False}]
    assert R.gives(dict(ex, extras=dict(ex["extras"], exams="2026-12-05")), [], T)[1]["text"] == "Exams and events: plans them, until 5 Dec 2026."
    assert [g["text"] for g in R.gives(dict(group="teacher", extras=dict(timetable=False, relief=False, exams="2026-11-22", admin=False), off=False), [], T)] == [
        "Sees the published timetable and the files.", "Relief: opens the relief page and asks for cover."]

NEEDS = (("Sees the published", "timetable"), ("Relief: opens", "relief"), ("Relief: plans", "relief.plan"), ("Relief: runs", "relief.team"),
         ("Setup: changes", "setup"), ("Setup: no department", "setup"), ("Setup: every", "committee"), ("Exams and events: plans them and", "committee"),
         ("Exams and events: plans them,", "exams"), ("History: sees everyone", "history"), ("History: sees their", "history.dept"), ("People and access", "admin"))

@t
def a_marked_line_is_never_given_by_a_code():
    today = datetime.date(2026, 11, 23)
    n = 0
    for g, relief, exams, admin, off, tt in itertools.product(OLD_GROUPS, (False, True), (None, "2026-11-22", "2026-12-31"), (False, True), (False, True), (False, True)):
        if g == "committee": continue
        for depts in ([], ["MA"]):
            person = dict(group=g or "teacher", extras=dict(timetable=tt, relief=relief, exams=exams, admin=admin), off=off)
            code, pw = R.rights(person, "code", today=today), R.rights(person, "password", today=today)
            for line in R.gives(person, depts, today):
                need = [r for start, r in NEEDS if line["text"].startswith(start)]
                if off: assert line == {"text": "Nothing: switched off, so they cannot sign in.", "strong": False}; continue
                assert len(need) == 1, line
                if line["strong"]: assert need[0] not in code and need[0] in pw, (person, line)
                else: assert need[0] in code, (person, line)
                n += 1
    assert n > 1000, n

@t
def an_hod_on_the_timetable_committee_has_both():
    p = dict(group="hod", extras=dict(timetable=True, relief=False, exams=None, admin=False), off=False)
    assert {"committee", "setup", "history", "history.dept", "codes", "relief.plan", "relief.save"} <= R.rights(p, "password")
    assert "committee" not in R.rights(p, "code") and "setup" not in R.rights(p, "code")

@t
def admin_needs_the_timetable_committee():
    p = dict(group="leader", extras=dict(timetable=False, relief=False, exams=None, admin=True), off=False)
    assert "admin" not in R.rights(p, "password")
    P.update(lambda d: d["people"].update({"No Tick": {"group": "leader", "extras": {"admin": True}}}))
    assert "No Tick" not in P.admins(P.load())
    P.update(lambda d: d["people"].pop("No Tick"))

@t
def relief_s_management_move_keeps_the_committee():
    name = "Ms Move Keep"
    P.update(lambda d: d["people"].update({name: {"group": "committee"}}))
    before = P.load()
    P.update(lambda d: d.update(migrated=False))
    out = P.migrate(fake_pub([dict(name=name, dept="Sci", role="HOD")]), {"management": [name]})
    r = P.record(P.load(), name)
    assert r["group"] == "hod" and r["extras"]["timetable"] is True, r
    assert out == [f"{name}: HOD (from relief's Management list)"], out
    def undo(d):
        d["people"].pop(name); d["migrated"] = before["migrated"]; d["moved"] = before["moved"]
    P.update(undo)

@t
def a_removed_name_reads_with_its_sign_out_number():
    assert P.record({"people": {}, "removed": {}}, "Mr Nobody")["n"] == 0
    assert P.record(P.blank(), "Mr Nobody")["n"] == 0 and P.blank()["removed"] == {}
    assert P.record({"people": {}, "removed": {"X": 4}}, "X")["n"] == 4
    assert P.record({"people": {}, "removed": {"X": 4}}, "Y")["n"] == 0
    assert P.record({"people": {"X": {"n": 2}}, "removed": {"X": 4}}, "X")["n"] == 2       # a stored record wins
    for bad in ([1], "x", None, 3): assert P._fill({"people": {}, "removed": bad})["removed"] == {}, bad
    assert P._fill({"people": {}, "removed": {"X": 4}})["removed"] == {"X": 4}
    assert P.record(None, "X")["n"] == 0

print(f"{COUNT} accounts tests passed")

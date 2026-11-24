"""Plain-assert tests for a teacher's new name carrying to their account (stage 2): .venv/bin/python tests/test_renames.py"""
import os, secrets, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = tempfile.mkdtemp()
KEY = secrets.token_hex(16)
CODES = {k: secrets.token_hex(8) for k in ("COMMITTEE_CODE", "TEACHER_CODE", "STUDENT_CODE", "HEADS_CODE")}
for k in ("ADMIN_RECOVERY_CODE", "ANTHROPIC_API_KEY", "TYPED_REQUEST_MODEL", "AI_MODEL"): os.environ.pop(k, None)
os.environ.update(DATA_DIR=DATA, SECRET_KEY=KEY, AI_PROVIDER="anthropic", AI_API_KEY="", **CODES)
sys.path.insert(0, ROOT)
import store  # noqa: E402,F401
from accounts import passwords as PW, people as P, renames as RN  # noqa: E402

COUNT = 0
def t(f):
    global COUNT
    f(); COUNT += 1
    return f

LEE, NT3, ARJUN, PRIYA = "Mdm Lee", "New Teacher 3", "Arjun Nair", "Priya Nair"
HASH = PW.hash_pw(secrets.token_hex(8))
OWN = "You cannot remove your own account."
def last_admin(n): return f"{n} is the last admin: make another admin first."
def admin_needed(new): return f"An admin has to publish this one: {new}'s account must follow or be removed."
def choose(old, new): return f"Choose first for {old}, now {new}: the same person, or a different person."

def put(records):
    """the scratch accounts file holds exactly these records (name -> fields over the defaults) -> the data as loaded"""
    def fn(d):
        d["people"].clear(); d["removed"].clear()
        for n, fields in records.items():
            r = P.record(d, n); r.update(fields); d["people"][n] = r
    P.update(fn)
    return P.load()

def setup(*rows):
    return {"teachers": [dict(r) for r in rows]}

PUB = {NT3, ARJUN}
PLAIN = setup(dict(name=LEE, earlier_names=[NT3]), dict(name=ARJUN))
ADMIN = dict(group="teacher", extras=dict(timetable=True, relief=False, exams=None, admin=True), username="nt3", pw=HASH)

@t
def kept_words():
    d = put({NT3: dict(group="hod", depts=["MA"], extras=dict(timetable=False, relief=True, exams=None, admin=False), username="nt3", pw=HASH, note="x")})
    r = P.record(d, NT3)
    assert RN.kept(r, False) == ["HOD", "Relief team", "username", "password", "a note"], RN.kept(r, False)
    assert RN.kept(r, True) == ["HOD", "Relief team", "username", "password", "a note", "Telegram"]
    blank = P.record({}, NT3); blank["signins"] = [1.0, 2.0, 3.0]
    assert RN.kept(blank, False) == []
    assert RN.kept(P.record({}, NT3), True) == ["Telegram"]
    every = P._clean(dict(group="leader", depts=["MA"], extras=dict(timetable=True, relief=True, exams="2027-01-01", admin=True), username="u", pw=HASH,
                          google="g-1", note="n", off=True, added=True))
    assert RN.kept(every, True) == ["School leader", "Timetable committee", "Relief team", "Exams and events", "Admin", "username", "password",
                                    "Google sign-in", "a note", "switched off", "added by name", "Telegram"], RN.kept(every, True)
    assert RN.kept(P._clean(dict(note="   ", depts=["MA"])), False) == []          # a blank note and departments alone are not words

@t
def a_plain_pair():
    d = put({NT3: dict(group="hod", username="nt3")})
    got = RN.pairs(PUB, PLAIN, d, set())
    assert got == [dict(old=NT3, new=LEE, has=["HOD", "username"], account=True, telegram=False, joins=True, no_remove=None)], got

@t
def no_pair():
    d = put({NT3: dict(group="hod", username="nt3")})
    assert RN.pairs(PUB, PLAIN, put({}), set()) == []                                          # nothing to keep
    stranger = put({PRIYA: dict(ADMIN, username="priya", added=True)})
    assert RN.pairs(PUB, setup(dict(name=LEE, earlier_names=[PRIYA])), stranger, {PRIYA}) == []  # not on the published timetable
    assert RN.pairs(PUB, setup(dict(name=LEE, earlier_names=[NT3]), dict(name=NT3)), d, set()) == []   # still a teacher row
    for bad in (NT3, None, {NT3: 1}, [1, None, ["x"], {NT3: 1}], 3):
        assert RN.pairs(PUB, setup(dict(name=LEE, earlier_names=bad)), d, set()) == [], bad
    for name in ("", "  ", None, 4):
        assert RN.pairs(PUB, setup(dict(name=name, earlier_names=[NT3])), d, set()) == [], name
    assert RN.pairs(PUB, {"teachers": [None, "x", 3]}, d, set()) == []
    for spec in (None, {}, {"teachers": "x"}, []): assert RN.pairs(PUB, spec, d, set()) == [], spec
    got = RN.pairs(PUB, setup(dict(name=LEE, earlier_names=[3, NT3])), d, set())                  # a non-string beside a good one
    assert [p["old"] for p in got] == [NT3], got

@t
def only_telegram():
    got = RN.pairs(PUB, PLAIN, put({}), {NT3})
    assert got == [dict(old=NT3, new=LEE, has=["Telegram"], account=False, telegram=True, joins=True, no_remove=None)], got

@t
def joins_false():
    for fields in (dict(username="lee"), dict(pw=HASH), dict(google="g-1")):
        d = put({NT3: dict(group="hod"), LEE: fields})
        assert RN.pairs(PUB, PLAIN, d, set())[0]["joins"] is False, fields
    d = put({NT3: dict(group="hod"), LEE: dict(group="sh", note="y", extras=dict(timetable=True, relief=False, exams=None, admin=False))})
    assert RN.pairs(PUB, PLAIN, d, set())[0]["joins"] is True

@t
def no_remove():
    d = put({NT3: dict(group="hod")})
    assert RN.pairs(PUB, PLAIN, d, set(), me=NT3)[0]["no_remove"] == OWN
    assert RN.pairs(PUB, PLAIN, d, set(), me=ARJUN)[0]["no_remove"] is None
    d = put({NT3: ADMIN})
    assert RN.pairs(PUB, PLAIN, d, set())[0]["no_remove"] == last_admin(NT3)
    d = put({NT3: ADMIN, ARJUN: dict(ADMIN, username="arjun")})
    assert RN.pairs(PUB, PLAIN, d, set())[0]["no_remove"] is None
    d = put({NT3: ADMIN, ARJUN: dict(ADMIN, username="arjun", off=True)})                     # switched off: not usable
    assert RN.pairs(PUB, PLAIN, d, set())[0]["no_remove"] == last_admin(NT3)

@t
def two_rows_one_name():
    d = put({NT3: dict(group="hod")})
    got = RN.pairs(PUB, setup(dict(name=LEE, earlier_names=[NT3]), dict(name=PRIYA, earlier_names=[NT3, NT3])), d, set())
    assert [(p["old"], p["new"]) for p in got] == [(NT3, LEE)], got
    two = put({NT3: dict(group="hod"), ARJUN: dict(username="arjun")})
    got = RN.pairs(PUB, setup(dict(name=LEE, earlier_names=[ARJUN, NT3]), dict(name="Mr Tan")), two, set())   # setup order, then list order
    assert [(p["old"], p["new"]) for p in got] == [(ARJUN, LEE), (NT3, LEE)], got

@t
def refusals():
    acc = dict(old=NT3, new=LEE, has=["HOD"], account=True, telegram=False, joins=True, no_remove=None)
    tg = dict(acc, has=["Telegram"], account=False, telegram=True)
    assert RN.refusal([], {}, False) is None
    assert RN.refusal([acc], {NT3: "same"}, False) == admin_needed(LEE)
    assert RN.refusal([acc], {}, False) == admin_needed(LEE)
    assert RN.refusal([tg], {NT3: "different"}, False) is None
    assert RN.refusal([tg], {NT3: "same"}, False) is None
    assert RN.refusal([acc], {}, True) == choose(NT3, LEE)
    assert RN.refusal([acc], {NT3: "maybe"}, True) == choose(NT3, LEE)
    assert RN.refusal([tg], None, False) == choose(NT3, LEE)
    assert RN.refusal([acc], {NT3: "same"}, True) is None
    assert RN.refusal([acc], {NT3: "different"}, True) is None
    stuck = dict(acc, no_remove=OWN)
    assert RN.refusal([stuck], {NT3: "different"}, True) == OWN
    assert RN.refusal([dict(stuck, joins=False)], {NT3: "same"}, True) == OWN
    assert RN.refusal([stuck], {NT3: "same"}, True) is None                 # the record moves: nothing is removed from the person
    assert RN.refusal([dict(tg, no_remove=OWN)], {NT3: "different"}, True) is None   # no account to remove
    assert RN.refusal([acc], {NT3: "same", PRIYA: "maybe"}, True) is None   # a name that makes no pair is ignored
    assert RN.refusal([acc], {PRIYA: "same"}, True) == choose(NT3, LEE)

def joined(old_fields, new_fields):
    put({NT3: old_fields, LEE: new_fields} if new_fields is not None else {NT3: old_fields})
    out = P.update(lambda d: P.join(d, NT3, LEE))
    return P.load(), out

@t
def join_moves_the_account():
    old = dict(group="hod", depts=["MA"], extras=dict(timetable=False, relief=True, exams="2026-12-31", admin=False), username="lee", pw=HASH,
               must_change=True, note="x", n=4)
    new = dict(extras=dict(timetable=True, relief=False, exams="2027-03-01", admin=False), n=1, signins=[10.0, 20.0])
    d, changes = joined(old, new)
    r = P.record(d, LEE)
    assert (r["group"], r["depts"], r["extras"]) == ("hod", ["MA"], dict(timetable=True, relief=True, exams="2027-03-01", admin=False)), r
    assert (r["username"], r["pw"], r["must_change"], r["note"], r["n"], r["signins"]) == ("lee", HASH, True, "x", 5, [10.0, 20.0]), r
    assert NT3 not in d["people"] and d["removed"][NT3] == 5 and P.record(d, NT3)["n"] == 5
    assert {c["field"] for c in changes} == {"group", "depts", "relief", "username", "pw", "must_change", "note"}, changes
    assert all(c["name"] == LEE for c in changes)
    assert next(c for c in changes if c["field"] == "pw") == dict(name=LEE, field="pw", was=None, now="set")
    assert HASH not in repr(changes)
    assert next(c for c in changes if c["field"] == "group") == dict(name=LEE, field="group", was=None, now="hod")

@t
def join_only_off():
    d, changes = joined(dict(off=True, n=2), dict(group="sh", depts=["EL"], note="keep", n=6))
    assert [(c["field"], c["was"], c["now"]) for c in changes] == [("off", False, True)], changes
    r = P.record(d, LEE)
    assert (r["group"], r["depts"], r["note"], r["off"], r["n"]) == ("sh", ["EL"], "keep", True, 7), r
    assert d["removed"][NT3] == 3

@t
def join_exams_and_codes():
    d, _ = joined(dict(extras=dict(exams="2027-05-01"), code_n=3), dict(extras=dict(exams="2027-01-01"), code_n=1))
    assert P.record(d, LEE)["extras"]["exams"] == "2027-05-01" and P.record(d, LEE)["code_n"] == 3
    d, _ = joined(dict(group="hod"), None)                       # the new name had no record yet
    assert P.record(d, LEE)["group"] == "hod" and P.record(d, LEE)["extras"]["exams"] is None and P.record(d, LEE)["n"] == 1

@t
def join_refused():
    for fields in (dict(username="mdm.lee"), dict(pw=HASH), dict(google="g-1")):
        put({NT3: dict(group="hod"), LEE: fields})
        try: P.update(lambda d: P.join(d, NT3, LEE)); raise AssertionError(fields)
        except ValueError: pass
        assert NT3 in P.load()["people"], fields                 # nothing changed

@t
def join_odd_data():
    d = {"people": {NT3: "not a dict"}}                          # no `removed`, a record that is not a dict
    P.join(d, NT3, LEE)
    assert d["removed"][NT3] == 1 and NT3 not in d["people"] and P.record(d, LEE)["n"] == 1
    d = {"people": {NT3: {"group": "hod", "n": 2}}, "removed": "x"}
    P.join(d, NT3, LEE)
    assert d["removed"] == {NT3: 3}
    d = {"people": {NT3: {"group": "hod", "extras": "x"}, LEE: {"extras": None}}, "removed": {}}
    P.join(d, NT3, LEE)
    assert P.record(d, LEE)["group"] == "hod"

@t
def drop_removes():
    put({NT3: dict(group="hod", depts=["MA"], extras=dict(timetable=True, relief=False, exams="2027-01-01", admin=False), username="nt3", pw=HASH, note="n", n=3)})
    was = P.update(lambda d: P.drop(d, NT3))
    d = P.load()
    assert NT3 not in d["people"] and d["removed"][NT3] == 4 and P.record(d, NT3)["n"] == 4
    assert was == dict(role="HOD", timetable=True, relief=False, exams="2027-01-01", admin=False, depts=["MA"], username="nt3", note="n", off=False), was
    d = {"people": {}}
    assert P.drop(d, NT3)["role"] is None and d["removed"] == {NT3: 1}

from relief import links, tgdb  # noqa: E402

def tg_state():
    with tgdb.db(read=True) as c:
        return ({r["name"]: (r["chat"], r["handle"], r["at"]) for r in c.execute("SELECT name, chat, handle, at FROM links")},
                {r["name"] for r in c.execute("SELECT name FROM codes")},
                {r["k"] for r in c.execute("SELECT k FROM state")},
                {r["chat"] for r in c.execute("SELECT chat FROM talks")})

def tg_clear():
    with tgdb.db() as c:
        for tb in ("links", "codes", "state", "talks"): c.execute(f"DELETE FROM {tb}")

def tg_talk(chat):
    with tgdb.db() as c: c.execute("INSERT OR REPLACE INTO talks(chat, kind, data, until) VALUES (?, 'x', '{}', 9e12)", (chat,))

@t
def move_moves_the_link():
    tg_clear()
    links.link(NT3, 101, "@nt3"); links.link(ARJUN, 102, "@arjun")
    before = tg_state()[0][NT3]
    links.new_code(NT3); links.new_code(ARJUN); tg_talk(101); tg_talk(102)
    with tgdb.db() as c:
        c.execute("INSERT INTO state(k, v) VALUES (?, '1')", (links.BLOCKED + NT3,))
        c.execute("INSERT INTO state(k, v) VALUES (?, '1')", (f"{links.ALERT}{NT3}:2026-11-24",))
        c.execute("INSERT INTO state(k, v) VALUES (?, '1')", (f"{links.ALERT}{ARJUN}:2026-11-24",))
    assert links.move(NT3, LEE) == "moved"
    ln, codes, st, talks = tg_state()
    assert NT3 not in ln and ln[LEE] == before and ln[ARJUN][0] == 102, ln
    assert codes == {ARJUN}, codes
    assert st == {links.BLOCKED + LEE, f"{links.ALERT}{ARJUN}:2026-11-24"}, st
    assert talks == {101, 102}, talks
    assert links.move(NT3, LEE) == "none"                         # twice is harmless
    assert tg_state()[0][LEE] == before

@t
def move_keeps_the_new_blocked_note():
    tg_clear()
    links.link(NT3, 101, "@nt3")
    with tgdb.db() as c:
        c.execute("INSERT INTO state(k, v) VALUES (?, '\"old\"')", (links.BLOCKED + NT3,))
        c.execute("INSERT INTO state(k, v) VALUES (?, '\"new\"')", (links.BLOCKED + LEE,))
    assert links.move(NT3, LEE) == "moved"
    assert links.blocked(LEE) == "new" and links.blocked(NT3) is None

@t
def move_kept():
    tg_clear()
    links.link(NT3, 101, "@nt3"); links.link(LEE, 103, "@lee")
    links.new_code(NT3); tg_talk(101); tg_talk(103)
    links.note_alert(NT3, "x")
    with tgdb.db() as c: c.execute("INSERT INTO state(k, v) VALUES (?, '1')", (links.BLOCKED + NT3,))
    assert links.move(NT3, LEE) == "kept"
    ln, codes, st, talks = tg_state()
    assert set(ln) == {LEE} and ln[LEE][0] == 103 and codes == set() and st == set() and talks == {103}, tg_state()

@t
def move_none():
    tg_clear()
    links.link(ARJUN, 102, "@arjun")
    links.new_code(NT3); links.new_code(ARJUN); links.note_alert(NT3, "x"); links.note_alert(ARJUN, "x")
    with tgdb.db() as c: c.execute("INSERT INTO state(k, v) VALUES (?, '1')", (links.BLOCKED + NT3,))
    assert links.move(NT3, LEE) == "none"
    ln, codes, st, _ = tg_state()
    assert set(ln) == {ARJUN} and codes == {ARJUN} and len(st) == 1 and next(iter(st)).startswith(links.ALERT + ARJUN), tg_state()

@t
def move_same_or_blank_changes_nothing():
    tg_clear()
    links.link(NT3, 101, "@nt3"); links.new_code(NT3); links.note_alert(NT3, "x")
    before = tg_state()
    for a, b in ((NT3, NT3), ("", LEE), (NT3, ""), ("", ""), (None, LEE), (NT3, None)):
        assert links.move(a, b) == "none", (a, b)
        assert tg_state() == before, (a, b)

@t
def move_colon_name_spares_other_alerts():
    tg_clear()
    links.link("A:B", 101, "@x")
    links.note_alert("A:B", "x"); links.note_alert("A", "y")          # "A:B" must not touch alert:A:..., nor "A" alert:A:B:...
    with tgdb.db() as c: c.execute("INSERT INTO state(k, v) VALUES (?, '1')", (f"{links.ALERT}A:B:C:2026-11-24",))
    assert links.move("A", LEE) == "none"                              # alert:A:B:... is "A:B"'s, not "A"'s
    keys = tg_state()[2]
    assert any(k.startswith(f"{links.ALERT}A:B:") for k in keys) and not any(k.startswith(f"{links.ALERT}A:2") for k in keys), keys
    assert links.move("A:B", LEE) == "moved"
    assert set(links.alerts("2000-01-01")) == {("A:B:C", "2026-11-24")}, links.alerts("2000-01-01")   # only the other name's alert is left

print(f"{COUNT} renames tests passed")

"""Plain-assert tests for a teacher's new name carrying to their account (stage 2): .venv/bin/python tests/test_renames.py"""
import copy, os, secrets, sys, tempfile
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
def no_join(new): return f"{new} is switched off, so no admin could sign in afterwards: switch {new} on first."
def B(*picks): return {"renames": [dict(old=o, new=n, choice=c) for o, n, c in picks]}
K = (NT3, "Mdm Lee")   # the pair (old, new) the plain setup makes

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
    assert got == [dict(old=NT3, new=LEE, has=["HOD", "username"], account=True, telegram=False, joins=True, no_remove=None,
                      no_join=None)], got

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
    assert got == [dict(old=NT3, new=LEE, has=["Telegram"], account=False, telegram=True, joins=True, no_remove=None,
                      no_join=None)], got

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
    acc = dict(old=NT3, new=LEE, has=["HOD"], account=True, telegram=False, joins=True, no_remove=None, no_join=None)
    tg = dict(acc, has=["Telegram"], account=False, telegram=True)
    assert RN.refusal([], {}, False) is None
    assert RN.refusal([acc], {K: "same"}, False) == admin_needed(LEE)
    assert RN.refusal([acc], {}, False) == admin_needed(LEE)
    assert RN.refusal([tg], {K: "different"}, False) is None
    assert RN.refusal([tg], {K: "same"}, False) is None
    assert RN.refusal([acc], {}, True) == choose(NT3, LEE)
    assert RN.refusal([acc], {K: "maybe"}, True) == choose(NT3, LEE)
    assert RN.refusal([tg], None, False) == choose(NT3, LEE)
    assert RN.refusal([acc], {K: "same"}, True) is None
    assert RN.refusal([acc], {K: "different"}, True) is None
    stuck = dict(acc, no_remove=OWN)
    assert RN.refusal([stuck], {K: "different"}, True) == OWN
    assert RN.refusal([dict(stuck, joins=False)], {K: "same"}, True) == OWN
    assert RN.refusal([stuck], {K: "same"}, True) is None                   # the record moves: nothing is removed from the person
    assert RN.refusal([dict(tg, no_remove=OWN)], {K: "different"}, True) is None   # no account to remove
    assert RN.refusal([acc], {K: "same", (PRIYA, LEE): "maybe"}, True) is None   # a pair that does not exist is ignored
    assert RN.refusal([acc], {(PRIYA, LEE): "same"}, True) == choose(NT3, LEE)

@t
def a_choice_is_bound_to_the_pair():
    acc = dict(old=NT3, new=LEE, has=["HOD"], account=True, telegram=False, joins=True, no_remove=None, no_join=None)
    assert RN.refusal([acc], {NT3: "same"}, True) == choose(NT3, LEE)                # keyed by the old name only: no choice
    assert RN.refusal([acc], {(NT3, ARJUN): "same"}, True) == choose(NT3, LEE)       # a choice made for another new name
    assert RN.refusal([acc], {(LEE, NT3): "same"}, True) == choose(NT3, LEE)         # the other way round
    assert RN.refusal([acc, dict(acc, old=ARJUN)], {K: "same"}, True) == choose(ARJUN, LEE)
    assert RN.refusal([acc, dict(acc, old=ARJUN)], {K: "same", (ARJUN, LEE): "different"}, True) is None

@t
def reading_the_choices():
    item = lambda o=NT3, n=LEE, c="same": dict(old=o, new=n, choice=c)
    assert RN.read_choices([item()]) == {(NT3, LEE): "same"}
    assert RN.read_choices([item(), item(ARJUN, "Mr Tan", "different")]) == {(NT3, LEE): "same", (ARJUN, "Mr Tan"): "different"}
    for bad in (None, {NT3: "same"}, "x", 3, [None, 1, "x", [NT3, LEE, "same"]], [dict(old=NT3, new=LEE)], [item(c="maybe")], [item(c=["same"])],
                [item(o=3)], [item(n=None)], [dict(old=NT3, new=LEE, choice=True)]):
        assert RN.read_choices(bad) == {}, bad
    assert RN.read_choices([item(), item(c="different")]) == {}                      # two answers for one pair: no choice
    assert RN.read_choices([item(), item()]) == {(NT3, LEE): "same"}
    assert RN.read_choices([item(), 5, item(ARJUN, LEE, "maybe")]) == {(NT3, LEE): "same"}

@t
def no_join_when_no_admin_could_sign_in():
    d = put({NT3: ADMIN, LEE: dict(off=True)})
    before = copy.deepcopy(d)
    p = RN.pairs(PUB, PLAIN, d, set(), me=NT3)[0]
    assert p["no_join"] == no_join(LEE) and p["joins"] is True, p
    assert d == before                                                                   # worked out on a copy
    assert RN.refusal([p], {K: "same"}, True) == no_join(LEE)
    assert RN.refusal([p], {K: "different"}, True) == OWN
    assert RN.refusal([dict(p, joins=False, no_remove=None)], {K: "same"}, True) is None   # no join: nothing to stop
    assert RN.refusal([dict(p, account=False, no_remove=None)], {K: "same"}, True) is None
    d = put({NT3: ADMIN, LEE: dict(off=True), ARJUN: dict(ADMIN, username="arjun")})     # another admin can sign in
    assert RN.pairs(PUB, PLAIN, d, set(), me=NT3)[0]["no_join"] is None
    d = put({NT3: ADMIN})                                                                # the new name is not switched off
    assert RN.pairs(PUB, PLAIN, d, set())[0]["no_join"] is None
    d = put({NT3: dict(group="hod"), LEE: dict(off=True)})                               # no admin could sign in before either
    assert RN.pairs(PUB, PLAIN, d, set())[0]["no_join"] is None
    d = put({NT3: ADMIN, LEE: dict(off=True, username="lee")})                           # cannot join at all
    p = RN.pairs(PUB, PLAIN, d, set())[0]
    assert p["joins"] is False and p["no_join"] is None, p

@t
def a_new_name_with_spaces_around_it():
    d = put({NT3: dict(group="hod", username="nt3")})
    got = RN.pairs(PUB, setup(dict(name=LEE + " ", earlier_names=[NT3]), dict(name=ARJUN)), d, set())
    assert [(p["old"], p["new"]) for p in got] == [(NT3, LEE)], got
    assert RN.pairs(PUB, setup(dict(name=LEE, earlier_names=[NT3]), dict(name=NT3 + " ")), d, set()) == []   # still a teacher row

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
    assert st == {f"{links.ALERT}{ARJUN}:2026-11-24"}, st             # a linked person has no blocked note
    assert talks == {101, 102}, talks
    assert links.move(NT3, LEE) == "none"                         # twice is harmless
    assert tg_state()[0][LEE] == before

@t
def move_moved_leaves_no_blocked_note():
    tg_clear()
    links.link(NT3, 101, "@nt3")
    with tgdb.db() as c:
        c.execute("INSERT INTO state(k, v) VALUES (?, '\"old\"')", (links.BLOCKED + NT3,))
        c.execute("INSERT INTO state(k, v) VALUES (?, '\"new\"')", (links.BLOCKED + LEE,))
    assert links.move(NT3, LEE) == "moved"
    assert links.blocked(LEE) is None and links.blocked(NT3) is None     # linked now: no note, as _put keeps it

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
    assert set(ln) == {ARJUN} and codes == {ARJUN}, tg_state()
    assert st == {links.BLOCKED + LEE} | {k for k in st if k.startswith(links.ALERT + ARJUN)} and len(st) == 2, st   # the note follows the person

@t
def move_none_blocked_note():
    tg_clear()
    with tgdb.db() as c:
        c.execute("INSERT INTO state(k, v) VALUES (?, '\"old\"')", (links.BLOCKED + NT3,))
    assert links.move(NT3, LEE) == "none"
    assert links.blocked(LEE) == "old" and links.blocked(NT3) is None
    tg_clear()
    with tgdb.db() as c:
        c.execute("INSERT INTO state(k, v) VALUES (?, '\"old\"')", (links.BLOCKED + NT3,))
        c.execute("INSERT INTO state(k, v) VALUES (?, '\"new\"')", (links.BLOCKED + LEE,))
    assert links.move(NT3, LEE) == "none"
    assert links.blocked(LEE) == "new" and links.blocked(NT3) is None    # the new name's own note stays
    tg_clear()
    links.link(LEE, 103, "@lee")
    with tgdb.db() as c:
        c.execute("INSERT INTO state(k, v) VALUES (?, '\"old\"')", (links.BLOCKED + NT3,))
    assert links.move(NT3, LEE) == "none"
    assert links.blocked(LEE) is None and links.blocked(NT3) is None     # the new name is linked: the note goes

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

# ---- the publish asks, refuses and applies (the routes)
import contextlib, io, json, pickle, threading, time  # noqa: E402,F401
import app as A, draft as D, history as H, putback as PB  # noqa: E402
from relief import people as RP  # noqa: E402
from ttgen.samples import secondary  # noqa: E402

PWS = {NT3: secrets.token_hex(8), PRIYA: secrets.token_hex(8)}
HASHES = {n: PW.hash_pw(v) for n, v in PWS.items()}
USERS = {NT3: "nt3", PRIYA: "priya"}
def admin_rec(n): return dict(group="teacher", extras=dict(timetable=True, relief=False, exams=None, admin=True), username=USERS[n], pw=HASHES[n])
SLIP = " They need a new code slip."
def joined_line(old, new, tg=False): return f"{new} (was {old}): their account followed." + (" Their Telegram link followed too." if tg else "") + SLIP
def removed_line(old, new): return f"{old}'s account is removed: {new} starts fresh." + SLIP
def tg_moved_line(old, new): return f"{new} (was {old}): their Telegram link followed." + SLIP
def tg_gone_line(old, new): return f"{old}'s Telegram link is removed: {new} starts fresh." + SLIP
def removed_tg_line(old, new): return f"{old}'s account is removed: {new} starts fresh. Their Telegram link followed." + SLIP
def tg_kept_line(old, new): return f"{new} (was {old}): {new} keeps their own Telegram link; {old}'s is removed." + SLIP
def tg_none_line(old, new): return f"{new} (was {old}): there was no Telegram link to move." + SLIP
def not_on_line(old, new): return f"{new} (was {old}): not on the timetable just published, so nothing was changed."
UNFINISHED = "The new names could not be finished. Tell whoever looks after the app."

def publish_pub(names):
    """what store.published() reads: a fake school with these teachers"""
    pub = RP.fake_pub([dict(name=n, dept="MA") for n in names])
    pub["meta"].update(published_at="1 Nov 2026, 09:00", ok=True)
    pub["model"].update(classes=[dict(name="1A", level="Sec 1")], class_ix={}, teacher_ix={}, room_ix={}, students=[dict(id="S001", name="Sam Student", cls="1A")])
    os.makedirs(store.PUB, exist_ok=True)
    with open(os.path.join(store.PUB, "model.pkl"), "wb") as f: pickle.dump(pub["model"], f)
    store.write_json(os.path.join(store.PUB, "meta.json"), pub["meta"])
    store._cache.update(stamp=None, value=None)

def pub_names():
    return [t["name"] for t in store.published()["model"]["setup"]["teachers"]]

CALLS = []
def stand_in(without=()):
    """the slow publish: a new fake published timetable from the setup's teacher rows"""
    def publish(*a, **k):
        CALLS.append(1)
        spec, _ = store.load_setup()
        publish_pub([t["name"] for t in spec["teachers"] if t["name"] not in without])
        return {"published": True}
    return publish

def pw_client(name):
    c = A.app.test_client()
    r = c.post("/login/password", data=dict(username=USERS[name], password=PWS[name]))
    assert r.status_code == 302, (name, r.status_code)
    return c

def committee_client():
    c = A.app.test_client()
    r = c.post("/login", data=dict(code=CODES["COMMITTEE_CODE"]))
    assert r.status_code == 302, r.status_code
    return c

def sess(c):
    with c.session_transaction() as x: return dict(x)

def account_entries(): return H.read(kinds=["account"], limit=10 ** 6)

def since(n0):
    """the account entries written after there were n0, oldest first (the History reads newest first)"""
    es = account_entries(); return list(reversed(es[:len(es) - n0]))

def raw_accounts():
    with open(P.PATH, encoding="utf-8") as f: return f.read()

def scene(records, linked=(), published=(NT3, ARJUN, PRIYA)):
    """the accounts, the links, the timetable published now and a setup in which NT3's row is now LEE's"""
    tg_clear()
    put(records)
    for i, n in enumerate(linked): links.link(n, 500 + i, f"@{i}")
    publish_pub(list(published))
    spec = secondary()
    spec["teachers"] = [dict(name=LEE, short="Lee", dept="MA", earlier_names=[NT3]), dict(name=ARJUN, short="Arjun", dept="MA"),
                        dict(name=PRIYA, short="Priya", dept="MA")]
    store.replace_setup(spec, "Saved")
    assert store.load_setup()[0]["teachers"][0]["earlier_names"] == [NT3]
    CALLS.clear()
    A.draft.publish = stand_in()

def publish(c, body=None):
    r = c.post("/api/draft/publish", json=body) if body is not None else c.post("/api/draft/publish")
    return r.status_code, r.get_json()

REAL_PUBLISH, REAL_INFO = A.draft.publish, A.draft.info
A.draft.info = lambda *a, **k: {"draft": {"name": "x"}}
try:
    @t
    def get_lists_the_pairs():
        scene({NT3: dict(group="hod", username="nt3x"), PRIYA: admin_rec(PRIYA)}, linked=[NT3])
        got = pw_client(PRIYA).get("/api/draft/renames").get_json()
        assert got["renames"] == [dict(old=NT3, new=LEE, has=["HOD", "username", "Telegram"], account=True, telegram=True, joins=True,
                                       no_remove=None, no_join=None, needs_admin=False)], got
        got = committee_client().get("/api/draft/renames").get_json()
        assert got["renames"] == [dict(old=NT3, new=LEE, has=["an account", "Telegram"], account=True, telegram=True, joins=None,
                                       no_remove=None, no_join=None, needs_admin=True)], got
        scene({NT3: dict(group="hod", username="nt3x"), PRIYA: admin_rec(PRIYA)})
        got = committee_client().get("/api/draft/renames").get_json()
        assert [(p["has"], p["needs_admin"]) for p in got["renames"]] == [(["an account"], True)], got
        scene({NT3: admin_rec(NT3)})                                                 # the last admin: a sentence for admins only
        assert committee_client().get("/api/draft/renames").get_json()["renames"][0]["no_remove"] is None
        assert pw_client(NT3).get("/api/draft/renames").get_json()["renames"][0]["no_remove"] == OWN
        os.remove(os.path.join(store.PUB, "meta.json")); store._cache.update(stamp=None, value=None)
        assert committee_client().get("/api/draft/renames").get_json()["renames"] == []         # nothing published
        scene({NT3: dict(group="hod", username="nt3x"), PRIYA: admin_rec(PRIYA)})
        c = committee_client()
        assert c.get("/api/draft").get_json() == {"draft": {"name": "x"}}           # the draft's answer is unchanged: no renames in it
        assert A.app.test_client().get("/api/draft/renames").status_code == 401

    @t
    def publish_without_a_choice_is_refused():
        scene({NT3: dict(group="hod", username="nt3x"), PRIYA: admin_rec(PRIYA)})
        c = pw_client(PRIYA)                                                         # a sign-in writes its time: before it, not after
        before = raw_accounts()
        code, got = publish(c)
        assert code == 409 and got["error"] == choose(NT3, LEE) and [p["old"] for p in got["renames"]] == [NT3], (code, got)
        assert CALLS == [] and pub_names() == [NT3, ARJUN, PRIYA] and raw_accounts() == before
        code, got = publish(c, B((NT3, LEE, "maybe")))
        assert code == 409 and got["error"] == choose(NT3, LEE) and CALLS == []
        code, got = publish(c, {"renames": {NT3: "same"}})                          # the old shape, keyed by the old name: no choice
        assert code == 409 and got["error"] == choose(NT3, LEE) and CALLS == [] and raw_accounts() == before

    @t
    def the_committee_code_cannot_publish_an_account():
        scene({NT3: dict(group="hod", username="nt3x"), PRIYA: admin_rec(PRIYA)})
        code, got = publish(committee_client(), B((NT3, LEE, "same")))
        assert code == 409 and got["error"] == admin_needed(LEE) and got["renames"][0]["has"] == ["an account"], (code, got)
        assert CALLS == [] and pub_names() == [NT3, ARJUN, PRIYA]
        scene({PRIYA: admin_rec(PRIYA)}, linked=[NT3])                               # only a Telegram link
        n0 = len(account_entries())
        code, got = publish(committee_client(), B((NT3, LEE, "same")))
        assert code == 200 and got["renamed"] == [tg_moved_line(NT3, LEE)] and got["published"] is True, (code, got)
        assert set(links.linked()) == {LEE} and len(account_entries()) == n0
        assert NT3 not in P.load()["people"] and NT3 not in P.load()["removed"] and LEE not in P.load()["people"]   # nothing of the accounts changes
        scene({PRIYA: admin_rec(PRIYA)}, linked=[NT3])
        code, got = publish(committee_client(), B((NT3, LEE, "different")))
        assert code == 200 and got["renamed"] == [tg_gone_line(NT3, LEE)] and links.linked() == {}, (code, got)
        assert NT3 not in P.load()["removed"]

    def history_view(c, eid):
        got = c.get("/api/history?limit=500").get_json()
        return next(e for e in got["entries"] if e.get("id") == eid)

    @t
    def same_person():
        scene({NT3: dict(group="hod", depts=["MA"], username="nt3x", pw=HASH, note="x", n=2), PRIYA: admin_rec(PRIYA)}, linked=[NT3])
        n0 = len(account_entries())
        c = pw_client(PRIYA)
        code, got = publish(c, B((NT3, LEE, "same")))
        assert code == 200 and got["renamed"] == [joined_line(NT3, LEE, tg=True)], (code, got)
        d = P.load(); r = P.record(d, LEE)
        assert (r["group"], r["username"], r["pw"], r["note"]) == ("hod", "nt3x", HASH, "x") and NT3 not in d["people"] and d["removed"][NT3] == 3, r
        assert set(links.linked()) == {LEE}
        es = since(n0)
        assert len(es) == 1 and es[0]["what"] == "rename" and es[0]["people"] == [NT3, LEE], es
        assert es[0]["text"] == f"{NT3} is now {LEE}: their account followed" and es[0]["changes"][0] == dict(name=LEE, field="renamed", was=NT3, now=LEE), es
        assert HASH not in json.dumps(es) and HASH not in json.dumps(got)
        st = c.get("/api/status").get_json()
        assert st["published"]["renamed"] == [joined_line(NT3, LEE, tg=True)], st["published"]
        assert history_view(c, es[0]["id"])["text"] == es[0]["text"]
        r = c.post("/api/history/back", json=dict(id=es[0]["id"]))
        assert r.status_code == 409 and r.get_json()["error"] == PB._ADMIN, (r.status_code, r.get_json())
        assert P.record(P.load(), LEE)["username"] == "nt3x"
        # a second publish with the same body: the pairs are settled
        before, n1 = raw_accounts(), len(account_entries())
        code, got = publish(c, B((NT3, LEE, "same")))
        assert code == 200 and "renamed" not in got and raw_accounts() == before and len(account_entries()) == n1, (code, got)
        assert c.get("/api/status").get_json()["published"]["renamed"] == []

    @t
    def a_different_person():
        scene({NT3: dict(group="hod", username="nt3x", pw=HASH), PRIYA: admin_rec(PRIYA)}, linked=[NT3])
        n0 = len(account_entries())
        c = pw_client(PRIYA)
        code, got = publish(c, B((NT3, LEE, "different")))
        assert code == 200 and got["renamed"] == [removed_line(NT3, LEE)], (code, got)
        d = P.load()
        assert NT3 not in d["people"] and NT3 in d["removed"] and links.linked() == {}
        assert P.record(d, LEE) == P.record({}, LEE), P.record(d, LEE)
        es = since(n0)
        assert len(es) == 1 and es[0]["what"] == "remove" and es[0]["text"] == f"Removed {NT3}: {LEE} took over their timetable", es
        ch = es[0]["changes"]
        assert len(ch) == 1 and ch[0]["name"] == NT3 and ch[0]["field"] == "removed" and ch[0]["now"] is None and ch[0]["was"]["username"] == "nt3x", ch
        assert HASH not in json.dumps(es)
        assert history_view(c, es[0]["id"])["text"] == es[0]["text"]
        r = c.post("/api/history/back", json=dict(id=es[0]["id"]))
        assert r.status_code == 409 and r.get_json()["error"] == PB.REMOVED.format(NT3), (r.status_code, r.get_json())

    @t
    def same_person_whose_new_name_has_a_sign_in():
        scene({NT3: dict(group="hod", username="nt3x"), LEE: dict(group="sh", username="lee"), PRIYA: admin_rec(PRIYA)}, linked=[NT3])
        lee = P.record(P.load(), LEE)
        n0 = len(account_entries())
        code, got = publish(pw_client(PRIYA), B((NT3, LEE, "same")))
        assert code == 200 and got["renamed"] == [removed_tg_line(NT3, LEE)], (code, got)
        d = P.load()
        assert NT3 not in d["people"] and P.record(d, LEE) == lee and set(links.linked()) == {LEE}
        assert [e["what"] for e in since(n0)] == ["remove"]
        scene({NT3: dict(group="hod", username="nt3x"), LEE: dict(group="sh", username="lee"), PRIYA: admin_rec(PRIYA)}, linked=[NT3, LEE])
        lee_chat = tg_state()[0][LEE][0]
        code, got = publish(pw_client(PRIYA), B((NT3, LEE, "same")))
        assert code == 200 and set(links.linked()) == {LEE} and tg_state()[0][LEE][0] == lee_chat
        assert got["renamed"] == [removed_line(NT3, LEE)], got                      # LEE kept their own link: nothing followed

    @t
    def the_publisher_is_the_renamed_person():
        scene({NT3: admin_rec(NT3), PRIYA: admin_rec(PRIYA)})
        other = pw_client(NT3)                                                       # another session of theirs
        c = pw_client(NT3)
        code, got = publish(c, B((NT3, LEE, "different")))
        assert code == 409 and got["error"] == OWN and CALLS == [], (code, got)       # the route gives renames.pairs `me`
        code, got = publish(c, B((NT3, LEE, "same")))
        assert code == 200 and got["renamed"] == [joined_line(NT3, LEE)], (code, got)
        st = c.get("/api/status")
        assert st.status_code == 200 and st.get_json()["who"] == LEE, st.get_json()
        assert c.get("/api/admin/people").status_code == 200
        s = sess(c)
        assert s["who"] == LEE and s["n"] == P.record(P.load(), LEE)["n"], s
        assert other.get("/api/status").status_code == 401                          # nobody else stays signed in as them
        assert pw_client(PRIYA).get("/api/status").status_code == 200

    @t
    def a_new_name_not_published_is_skipped():
        scene({NT3: dict(group="hod", username="nt3x"), PRIYA: admin_rec(PRIYA)}, linked=[NT3])
        A.draft.publish = stand_in(without={LEE})
        c = pw_client(PRIYA)
        before = raw_accounts()
        code, got = publish(c, B((NT3, LEE, "different")))
        assert code == 200 and got["renamed"] == [not_on_line(NT3, LEE)] and CALLS == [1], (code, got)
        assert raw_accounts() == before and set(links.linked()) == {NT3}
        scene({PRIYA: admin_rec(PRIYA)})                                             # no pairs: the answer is the publish's own
        c = pw_client(PRIYA)
        code, got = publish(c)
        assert code == 200 and got == {"published": True}, (code, got)
        assert c.get("/api/status").get_json()["published"]["renamed"] == []        # the note is still written, so none lingers

    @t
    def a_critical_draft_changes_nothing():
        scene({NT3: dict(group="hod", username="nt3x"), PRIYA: admin_rec(PRIYA)}, linked=[NT3])
        def critical(*a, **k): raise D.Critical(2)
        A.draft.publish = critical
        c = pw_client(PRIYA)
        before = raw_accounts()
        code, got = publish(c, B((NT3, LEE, "different")))
        assert code == 409 and got == {"error": D.critical_text(2), "critical": 2}, (code, got)
        assert raw_accounts() == before and set(links.linked()) == {NT3} and pub_names() == [NT3, ARJUN, PRIYA]

    @t
    def one_pair_failing_does_not_stop_the_others():
        scene({NT3: dict(group="hod", username="nt3x"), ARJUN: dict(group="sh", username="arjun"), PRIYA: admin_rec(PRIYA)})
        spec, _ = store.load_setup()
        spec["teachers"] = [dict(name=LEE, short="Lee", dept="MA", earlier_names=[NT3]), dict(name="Mr Tan", short="Tan", dept="MA", earlier_names=[ARJUN]),
                            dict(name=PRIYA, short="Priya", dept="MA")]
        store.replace_setup(spec, "Saved")
        real_join = P.join
        def broken(d, old, new):
            if old == NT3: raise RuntimeError("no")
            return real_join(d, old, new)
        A.people.join = broken
        err = io.StringIO()
        try:
            with contextlib.redirect_stderr(err): code, got = publish(pw_client(PRIYA), B((NT3, LEE, "same"), (ARJUN, "Mr Tan", "same")))
        finally: A.people.join = real_join
        assert "Traceback" in err.getvalue() and "RuntimeError: no" in err.getvalue(), err.getvalue()   # logged with where it failed
        assert code == 200 and got["renamed"] == [f"{LEE} (was {NT3}): could not be finished. Tell whoever looks after the app.",
                                                  joined_line(ARJUN, "Mr Tan")], (code, got)
        d = P.load()
        assert NT3 in d["people"] and P.record(d, "Mr Tan")["username"] == "arjun" and pub_names() == [LEE, "Mr Tan", PRIYA]

    @t
    def a_choice_made_for_another_new_name_is_no_choice():
        scene({NT3: dict(group="hod", username="nt3x", pw=HASH), PRIYA: admin_rec(PRIYA)})
        c = pw_client(PRIYA)
        shown = c.get("/api/draft/renames").get_json()["renames"]
        assert [(p["old"], p["new"]) for p in shown] == [(NT3, LEE)], shown
        spec, _ = store.load_setup()                                                 # meanwhile the old name is claimed by another row
        spec["teachers"] = [dict(name=LEE, short="Lee", dept="MA"), dict(name=ARJUN, short="Arjun", dept="MA", earlier_names=[NT3]),
                            dict(name=PRIYA, short="Priya", dept="MA")]
        store.replace_setup(spec, "Saved")
        before = raw_accounts()
        for body in (B((NT3, LEE, "same")), {"renames": {NT3: "same"}}):             # what the page sent, in either shape
            code, got = publish(c, body)
            assert code == 409 and got["error"] == choose(NT3, ARJUN), (code, got)
            assert [(p["old"], p["new"]) for p in got["renames"]] == [(NT3, ARJUN)], got
            assert CALLS == [] and pub_names() == [NT3, ARJUN, PRIYA] and raw_accounts() == before
        code, got = publish(c, B((NT3, ARJUN, "different")))                         # chosen for the pair as it is now
        assert code == 200 and got["renamed"] == [removed_line(NT3, ARJUN)], (code, got)

    def two_at_once(body):
        """two publishes of one body, the second made while the first is inside the slow publish -> (first, second)"""
        inside, go, out = threading.Event(), threading.Event(), {}
        real = A.draft.publish
        def slow(*a, **k):
            if not inside.is_set(): inside.set(); assert go.wait(10)
            return real(*a, **k)
        A.draft.publish = slow
        a, b = pw_client(PRIYA), pw_client(PRIYA)
        def run(k, c): out[k] = publish(c, body)
        ta = threading.Thread(target=run, args=("a", a)); ta.start()
        assert inside.wait(10)
        tb = threading.Thread(target=run, args=("b", b)); tb.start()
        time.sleep(0.4)                                                              # the second is at the door
        go.set(); ta.join(20); tb.join(20)
        A.draft.publish = real
        return out["a"], out["b"], a

    @t
    def two_publishes_at_once_apply_a_pair_once():
        for old in (dict(group="hod", depts=["MA"]), dict(group="hod", username="nt3x", pw=HASH)):
            scene({NT3: old, PRIYA: admin_rec(PRIYA)})
            n0 = len(account_entries())
            (ca, ga), (cb, gb), c = two_at_once(B((NT3, LEE, "same")))
            assert ca == 200 and ga["renamed"] == [joined_line(NT3, LEE)], (ca, ga)
            assert cb == 200 and "renamed" not in gb, (cb, gb)
            es = since(n0)
            assert [e["what"] for e in es] == ["rename"], es
            d = P.load()
            assert P.record(d, LEE)["n"] == 1 and d["removed"][NT3] == 1, (P.record(d, LEE)["n"], d["removed"])
            shown = c.get("/api/status").get_json()["published"]["renamed"]
            assert shown in ([joined_line(NT3, LEE)], []) and "could not be finished" not in json.dumps(shown), shown

    @t
    def two_publishes_at_once_a_different_person():
        scene({NT3: dict(group="hod", depts=["MA"]), PRIYA: admin_rec(PRIYA)}, linked=[NT3])
        n0 = len(account_entries())
        (ca, ga), (cb, gb), _ = two_at_once(B((NT3, LEE, "different")))
        assert (ca, ga.get("renamed"), cb, "renamed" in gb) == (200, [removed_line(NT3, LEE)], 200, False), (ga, gb)
        assert [e["what"] for e in since(n0)] == ["remove"]

    @t
    def a_stale_pair_is_skipped_by_the_apply():
        for old, choice in ((dict(group="hod", depts=["MA"]), "same"), (dict(group="hod", username="nt3x", pw=HASH), "same"),
                            (dict(group="hod"), "different")):
            scene({NT3: old, PRIYA: admin_rec(PRIYA)}, linked=[NT3])
            real, kept = A._rename_pairs, {}
            A._rename_pairs = lambda: kept.setdefault("p", real())                 # the pairs as the first publish worked them out
            try:
                c = pw_client(PRIYA)
                code, got = publish(c, B((NT3, LEE, choice)))
                assert code == 200 and len(got["renamed"]) == 1, got
                n0, before = len(account_entries()), raw_accounts()
                code, got = publish(c, B((NT3, LEE, choice)))
                assert code == 200 and "renamed" not in got, (choice, got)
                assert len(account_entries()) == n0 and raw_accounts() == before
            finally: A._rename_pairs = real

    @t
    def the_last_admin_cannot_join_a_switched_off_name():
        scene({NT3: admin_rec(NT3), LEE: dict(off=True)})
        c = pw_client(NT3)
        shown = c.get("/api/draft/renames").get_json()["renames"]
        assert [(p["joins"], p["no_remove"], p["no_join"]) for p in shown] == [(True, OWN, no_join(LEE))], shown
        assert committee_client().get("/api/draft/renames").get_json()["renames"][0]["no_join"] is None   # for admins only
        before = raw_accounts()
        code, got = publish(c, B((NT3, LEE, "same")))
        assert code == 409 and got["error"] == no_join(LEE) and CALLS == [], (code, got)
        assert raw_accounts() == before and pub_names() == [NT3, ARJUN, PRIYA]
        assert c.get("/api/status").status_code == 200 and P.usable_admins(P.load()) == [NT3]

    @t
    def the_apply_refuses_a_join_that_leaves_no_admin():
        scene({NT3: admin_rec(NT3), LEE: dict(off=True)})
        c = pw_client(NT3)
        real = A._rename_pairs
        A._rename_pairs = lambda: [dict(p, no_join=None) for p in real()]          # as if worked out before LEE was switched off
        err = io.StringIO()
        try:
            with contextlib.redirect_stderr(err): code, got = publish(c, B((NT3, LEE, "same")))
        finally: A._rename_pairs = real
        assert code == 200 and got["renamed"] == [f"{LEE} (was {NT3}): could not be finished. Tell whoever looks after the app."], (code, got)
        d = P.load()
        assert NT3 in d["people"] and P.usable_admins(d) == [NT3] and P.record(d, LEE)["username"] is None
        assert "Traceback" not in err.getvalue()                                     # refused, not a fault
        assert c.get("/api/status").status_code == 200

    @t
    def telegram_only_same_person_sentences():
        scene({PRIYA: admin_rec(PRIYA)}, linked=[NT3, LEE])
        lee_chat = tg_state()[0][LEE][0]
        code, got = publish(committee_client(), B((NT3, LEE, "same")))
        assert code == 200 and got["renamed"] == [tg_kept_line(NT3, LEE)], (code, got)
        assert set(links.linked()) == {LEE} and tg_state()[0][LEE][0] == lee_chat
        scene({PRIYA: admin_rec(PRIYA)}, linked=[NT3])
        real = A.relief_links.move
        A.relief_links.move = lambda o, n: (real(o, n), "none")[1]                  # the link went meanwhile
        try: code, got = publish(committee_client(), B((NT3, LEE, "same")))
        finally: A.relief_links.move = real
        assert code == 200 and got["renamed"] == [tg_none_line(NT3, LEE)], (code, got)

    @t
    def a_new_name_with_a_space_is_carried():
        scene({NT3: dict(group="hod", username="nt3x", pw=HASH), PRIYA: admin_rec(PRIYA)})
        spec, _ = store.load_setup()
        spec["teachers"][0]["name"] = LEE + " "
        store.replace_setup(spec, "Saved")
        c = pw_client(PRIYA)
        assert [(p["old"], p["new"]) for p in c.get("/api/draft/renames").get_json()["renames"]] == [(NT3, LEE)]
        code, got = publish(c, B((NT3, LEE, "same")))
        assert code == 200 and got["renamed"] == [joined_line(NT3, LEE)], (code, got)
        d = P.load()
        assert NT3 not in d["people"] and P.record(d, LEE)["username"] == "nt3x" and (LEE + " ") not in d["people"]

    @t
    def a_failure_before_the_pairs_is_one_line():
        scene({NT3: dict(group="hod", username="nt3x"), PRIYA: admin_rec(PRIYA)})
        real_people, real_publish = A.relief_people.people, A.draft.publish
        def once(*a, **k):
            A.relief_people.people = real_people; raise RuntimeError("no")
        def then_break(*a, **k):
            got = real_publish(*a, **k); A.relief_people.people = once; return got
        A.draft.publish = then_break
        err = io.StringIO()
        try:
            with contextlib.redirect_stderr(err): code, got = publish(pw_client(PRIYA), B((NT3, LEE, "same")))
        finally: A.relief_people.people, A.draft.publish = real_people, real_publish
        assert code == 200 and got["renamed"] == [UNFINISHED] and got["published"] is True, (code, got)
        assert "Traceback" in err.getvalue() and pub_names() == [LEE, ARJUN, PRIYA]
        assert NT3 in P.load()["people"]

    @t
    def put_back_refuses_a_join_of_a_role_only():
        scene({NT3: dict(group="hod"), PRIYA: admin_rec(PRIYA)})
        n0 = len(account_entries())
        c = pw_client(PRIYA)
        code, got = publish(c, B((NT3, LEE, "same")))
        assert code == 200 and got["renamed"] == [joined_line(NT3, LEE)], (code, got)
        es = since(n0)
        assert len(es) == 1 and {ch["field"] for ch in es[0]["changes"]} == {"renamed", "group"}, es
        r = c.post("/api/history/back", json=dict(id=es[0]["id"]))
        assert r.status_code == 409 and r.get_json()["error"] == PB._ADMIN, (r.status_code, r.get_json())
        assert P.record(P.load(), LEE)["group"] == "hod" and NT3 not in P.load()["people"]

    @t
    def a_committee_member_by_password_who_is_not_an_admin():
        member = dict(admin_rec(PRIYA), extras=dict(timetable=True, relief=False, exams=None, admin=False))
        scene({NT3: dict(group="hod", username="nt3x", pw=HASH), PRIYA: member})
        c = pw_client(PRIYA)
        shown = c.get("/api/draft/renames").get_json()["renames"]
        assert [(p["has"], p["joins"], p["no_join"], p["needs_admin"]) for p in shown] == [(["an account"], None, None, True)], shown
        before = raw_accounts()
        code, got = publish(c, B((NT3, LEE, "same")))
        assert code == 409 and got["error"] == admin_needed(LEE) and CALLS == [] and raw_accounts() == before, (code, got)
        assert pub_names() == [NT3, ARJUN, PRIYA]
        assert c.get("/api/status").get_json()["published"]["renamed"] == []      # a committee member sees the lines

    @t
    def an_earlier_session_of_the_new_name_ends_at_the_join():
        scene({NT3: dict(group="hod", username="nt3x", pw=HASH), PRIYA: admin_rec(PRIYA)}, published=(NT3, ARJUN, PRIYA, LEE))
        spec, _ = store.load_setup()
        spec["teachers"].append(dict(name="Mr Tan", short="Tan", dept="MA"))
        store.replace_setup(spec, "Saved")
        lee = A.app.test_client()
        with lee.session_transaction() as x: x.update(who=LEE, via="code", n=0)     # LEE signed in by their code, before the join
        assert lee.get("/api/published/exams").status_code == 200
        code, got = publish(pw_client(PRIYA), B((NT3, LEE, "same")))
        assert code == 200 and got["renamed"] == [joined_line(NT3, LEE)], (code, got)
        assert P.record(P.load(), LEE)["n"] == 1
        assert lee.get("/api/published/exams").status_code == 401
        with lee.session_transaction() as x: assert "who" not in x, dict(x)

    @t
    def with_accounts_off_there_are_no_pairs():
        scene({NT3: dict(group="hod", username="nt3x"), PRIYA: admin_rec(PRIYA)}, linked=[NT3])
        c = committee_client()
        key = os.environ.pop("SECRET_KEY")
        try:
            r = c.get("/api/draft/renames")
            assert r.status_code == 200 and r.get_json()["renames"] == [], r.get_json()
        finally: os.environ["SECRET_KEY"] = key

    @t
    def a_head_gets_no_renamed_lines():
        scene({NT3: dict(group="hod", username="nt3x", pw=HASH), PRIYA: admin_rec(PRIYA)})
        code, got = publish(pw_client(PRIYA), B((NT3, LEE, "same")))
        assert code == 200 and got["renamed"] == [joined_line(NT3, LEE)]
        h = A.app.test_client()
        assert h.post("/login", data=dict(code=CODES["HEADS_CODE"])).status_code == 302
        st = h.get("/api/status").get_json()
        assert st["role"] == "head" and st["published"] is not None and st["published"].get("renamed", []) == [], st["published"]
        assert h.get("/api/draft/renames").status_code in (401, 403)
finally:
    A.draft.publish, A.draft.info = REAL_PUBLISH, REAL_INFO

print(f"{COUNT} renames tests passed")

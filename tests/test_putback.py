"""Plain-assert tests for the rules of Put back: .venv/bin/python tests/test_putback.py"""
import copy, datetime, os, sys, tempfile, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = tempfile.mkdtemp()
os.environ.update(DATA_DIR=DATA, AI_API_KEY="")
sys.path.insert(0, ROOT)
import history as H, store, sync, putback as P  # noqa: E402
from ttgen import samples  # noqa: E402

COUNT = 0
def t(f):
    global COUNT
    f(); COUNT += 1
    return f

T0 = datetime.datetime(2026, 11, 19, 10, 2, tzinfo=H.SCHOOL_TZ).timestamp()
ANN, BOB, CARA = (H.by_of(n, "password") for n in ("Ann Lee", "Bob Tan", "Cara Ng"))

def fresh():
    if os.path.isdir(H.DIR):
        for n in os.listdir(H.DIR): os.remove(os.path.join(H.DIR, n))

def spec():
    s = samples.secondary(); sync.ensure_ids(s); return s

def save(sp, ops, by, batch, ts):
    """record one save as the store does (entries judged on `sp`, which is then changed); returns the entries as written"""
    es = H.setup_entries(sp, ops, by, batch, 1)
    sync.apply(sp, copy.deepcopy(ops))
    for i, e in enumerate(es): e["ts"] = ts + i * 0.01
    return H.add_many(es)

def reversed_ok(sp, ops):
    before = copy.deepcopy(sp)
    es = H.setup_entries(sp, ops, ANN, "bx", 1)
    work = copy.deepcopy(sp); sync.apply(work, copy.deepcopy(ops))
    sync.apply(work, P.reverse(es))
    assert sync._canon(work) == sync._canon(before), ops

@t
def each_op_reverses():
    sp = spec(); T = sp["teachers"][0]; L2 = sp["lessons"][1]
    reversed_ok(sp, [["set", "teachers", T["_id"], "short", "ZZ"]])
    reversed_ok(sp, [["set", "teachers", T["_id"], "nosuchfield", "ZZ"]])
    reversed_ok(sp, [["merge", "teachers", T["_id"], "can_teach", ["X"], []]])
    reversed_ok(sp, [["add", "teachers", {"_id": "newrow0001", "name": "Zed Ng"}, ""]])
    reversed_ok(sp, [["add", "teachers", {"_id": "newrow0001", "name": "Zed Ng"}, T["_id"]]])
    reversed_ok(sp, [["del", "lessons", L2["_id"]]])
    reversed_ok(sp, [["del", "lessons", sp["lessons"][0]["_id"]]])
    reversed_ok(sp, [["del", "lessons", sp["lessons"][-1]["_id"]]])
    reversed_ok(sp, [["school", "name", "Other"]])
    reversed_ok(sp, [["school", "brand_new_key", 3]])
    lv = next(iter(sp["day_structure"])); day = next(iter(sp["day_structure"][lv]))
    reversed_ok(sp, [["day", lv, day, "LLL"]])
    reversed_ok(sp, [["top", "k", 1]])
    reversed_ok(sp, [["set", "teachers", T["_id"], "short", "A"], ["set", "teachers", T["_id"], "short", "B"], ["del", "teachers", T["_id"]]])
    es = H.setup_entries(sp, [["del", "lessons", L2["_id"]]], ANN, "bx", 1)
    assert es[0]["after"] == sp["lessons"][0]["_id"]
    assert H.setup_entries(sp, [["del", "lessons", sp["lessons"][0]["_id"]]], ANN, "bx", 1)[0]["after"] == ""
    assert H.setup_entries(sp, [["day", lv, day, "L"]], ANN, "bx", 1)[0]["level"] == lv
    assert P.reverse(H.setup_entries(sp, [["day", lv, day, "L"]], ANN, "bx", 1))[0][:2] == ["day", lv]

@t
def a_later_change_blocks_with_its_name():
    fresh(); sp = spec(); T = sp["teachers"][0]
    [a] = save(sp, [["set", "teachers", T["_id"], "short", "AA"]], ANN, "bann", T0)
    [b] = save(sp, [["set", "teachers", T["_id"], "short", "BB"]], BOB, "bbob", T0 + 3600)
    u, ents, newer = P.gather(a["id"])
    assert u == "b:bann" and [e["id"] for e in ents] == [a["id"]] and [e["id"] for e in newer] == [b["id"]]
    assert P.why_not(ents, newer) == "Can't put back: Bob Tan changed this again on " + H.short_when(b["ts"])
    assert P.why_not(*P.gather(b["id"])[1:]) is None
    assert H.short_when(b["ts"]) == "19 Nov, 11:02 am"

@t
def another_field_does_not_block():
    fresh(); sp = spec(); T = sp["teachers"][0]
    [a] = save(sp, [["set", "teachers", T["_id"], "short", "AA"]], ANN, "bann", T0)
    save(sp, [["set", "teachers", T["_id"], "dept", "Zed"]], BOB, "bbob", T0 + 60)
    assert P.why_not(*P.gather(a["id"])[1:]) is None

@t
def a_deleted_row_blocks_a_field_change():
    fresh(); sp = spec(); T = sp["teachers"][0]; N = {"_id": "newrow0001", "name": "Zed Ng"}
    [a] = save(sp, [["set", "teachers", T["_id"], "short", "AA"]], ANN, "bann", T0)
    [d] = save(sp, [["del", "teachers", T["_id"]]], BOB, "bbob", T0 + 60)
    assert P.why_not(*P.gather(a["id"])[1:]) == "Can't put back: Bob Tan changed this again on " + H.short_when(d["ts"])
    [ad] = save(sp, [["add", "teachers", N, ""]], ANN, "bnew", T0 + 120)
    [s] = save(sp, [["set", "teachers", "newrow0001", "short", "Q"]], BOB, "bset", T0 + 180)
    assert P.why_not(*P.gather(ad["id"])[1:]) == "Can't put back: Bob Tan changed this again on " + H.short_when(s["ts"])
    assert P.why_not(*P.gather(s["id"])[1:]) is None

@t
def same_save_and_its_follow_ups_do_not_block():
    fresh(); sp = spec(); T = sp["teachers"][0]
    es = save(sp, [["set", "teachers", T["_id"], "short", "AA"], ["set", "teachers", T["_id"], "dept", "Zed"]], ANN, "bann", T0)
    app = H.add({"kind": "app", "op": "set", "section": "teachers", "row": T["_id"], "field": "short", "was": "AA", "now": "AB",
                 "as": "The app", "via": "app", "follows": "bann", "ts": T0 + 0.5})
    u, ents, newer = P.gather(es[1]["id"])      # the middle of the save is enough
    assert [e["id"] for e in ents] == [e["id"] for e in es] and [e["id"] for e in newer] == [app["id"]]
    assert P.why_not(ents, newer) is None
    other = H.add({"kind": "app", "op": "set", "section": "teachers", "row": T["_id"], "field": "short", "was": "AA", "now": "AB",
                   "as": "The app", "via": "app", "follows": "bother", "ts": T0 + 1})
    assert P.why_not(ents, [other] + newer) == "Can't put back: the app changed this again on " + H.short_when(T0 + 1)

@t
def already_put_back():
    fresh(); sp = spec(); T = sp["teachers"][0]
    [a] = save(sp, [["set", "teachers", T["_id"], "short", "AA"]], ANN, "bann", T0)
    H.add(dict(kind="setup", batch="bback", v=2, op="set", section="teachers", row=T["_id"], field="short", was="AA", now=T["short"],
               putback="b:bann", ts=T0 + 600, **CARA))
    assert P.why_not(*P.gather(a["id"])[1:]) == "Already put back by Cara Ng on " + H.short_when(T0 + 600)

@t
def replaced_blocks_everything_older():
    fresh(); sp = spec(); T = sp["teachers"][0]
    [a] = save(sp, [["set", "teachers", T["_id"], "short", "AA"]], ANN, "bann", T0)
    acc = H.add({"kind": "account", "people": ["Dan"], "changes": [{"name": "Dan", "field": "group", "was": "teacher", "now": "hod"}], "ts": T0 + 10, **ANN})
    rep = H.add({"kind": "setup-replaced", "text": "whole", "ts": T0 + 100, **BOB})
    want = "Can't put back: the whole setup was replaced on " + H.short_when(T0 + 100) + ". Use a saved copy on the committee page."
    assert P.why_not(*P.gather(a["id"])[1:]) == want
    assert P.why_not(*P.gather(acc["id"])[1:]) is None
    assert P.unit_of(rep) is None

def acc(by, changes, ts):
    return H.add({"kind": "account", "people": [c["name"] for c in changes], "changes": changes, "ts": ts, **by})

@t
def account_rules():
    fresh()
    g = lambda n, was, now: {"name": n, "field": "group", "was": was, "now": now}
    a = acc(ANN, [g("Dan", "teacher", "hod")], T0)
    assert P.unit_of(a) == "a:" + a["id"]
    acc(BOB, [g("Eve", "teacher", "hod")], T0 + 60)
    assert P.why_not(*P.gather(a["id"])[1:]) is None
    b = acc(BOB, [g("Dan", "hod", "sh")], T0 + 120)
    assert P.why_not(*P.gather(a["id"])[1:]) == "Can't put back: Bob Tan changed this again on " + H.short_when(T0 + 120)
    new = acc(ANN, [{"name": "Fay", "field": "added", "was": False, "now": True}, g("Fay", None, "teacher")], T0 + 200)
    adm = "Can't put back a new person, a username or a password here: change it on the admin page."
    assert P.why_not(*P.gather(new["id"])[1:]) == adm
    un = acc(ANN, [{"name": "Gus", "field": "username", "was": "a", "now": "b"}], T0 + 210)
    assert P.why_not(*P.gather(un["id"])[1:]) == adm
    today = datetime.date(2026, 11, 20)
    ex = acc(ANN, [{"name": "Hal", "field": "exams", "was": "2026-11-19", "now": "2027-01-05"}], T0 + 300)
    assert P.why_not(*P.gather(ex["id"])[1:], today=today) == "Can't put back: the Exams and events date (19 Nov 2026) has passed."
    assert P.why_not(*P.gather(ex["id"])[1:], today=datetime.date(2026, 11, 19)) is None
    ex2 = acc(ANN, [{"name": "Ian", "field": "exams", "was": None, "now": "2027-01-05"}], T0 + 310)
    assert P.why_not(*P.gather(ex2["id"])[1:], today=today) is None
    assert P.why_not(*P.gather(ex["id"])[1:]) == "Can't put back: the Exams and events date (19 Nov 2026) has passed."   # today is the real date
    assert P.unit_of({"kind": "account", "changes": []}) is None and P.unit_of({"kind": "setup"}) is None
    assert P.unit_of({"kind": "signin", "id": "x"}) is None and P.unit_of({"kind": "setup", "batch": "b9"}) == "b:b9"

@t
def old_entries_say_why():
    fresh(); sp = spec()
    lv = next(iter(sp["day_structure"])); day = next(iter(sp["day_structure"][lv]))
    es = H.setup_entries(sp, [["day", lv, day, "LLL"]], ANN, "bday", 1)
    del es[0]["level"]; es[0]["ts"] = T0
    [e] = H.add_many(es)
    assert P.why_not(*P.gather(e["id"])[1:]) == "Can't put back: this change was recorded before Put back existed. Change it on its step."
    d = H.setup_entries(sp, [["del", "lessons", sp["lessons"][1]["_id"]]], ANN, "bdel", 1)
    del d[0]["after"]
    assert P.reverse(d) == [["add", "lessons", d[0]["was"], None]]

@t
def changed_since_sees_the_current_setup():
    fresh(); sp = spec(); T = sp["teachers"][0]; L2 = sp["lessons"][1]
    N = {"_id": "newrow0001", "name": "Zed Ng"}
    lv = next(iter(sp["day_structure"])); day = next(iter(sp["day_structure"][lv]))
    ops = [["set", "teachers", T["_id"], "short", "AA"], ["merge", "teachers", T["_id"], "can_teach", ["X"], []],
           ["add", "teachers", N, ""], ["del", "lessons", L2["_id"]], ["school", "name", "Q"], ["day", lv, day, "LLL"], ["top", "k", 1]]
    es = H.setup_entries(sp, ops, ANN, "bx", 1)
    sync.apply(sp, copy.deepcopy(ops))
    assert P.changed_since(sp, es) is None
    sentence = "Can't put back: this was changed again since."
    def moved(mutate):
        s2 = copy.deepcopy(sp); mutate(s2); return P.changed_since(s2, es)
    assert moved(lambda s: sync._find(s, "teachers", T["_id"]).__setitem__("short", "ZZ")) == sentence
    assert moved(lambda s: sync._find(s, "teachers", T["_id"]).__setitem__("can_teach", [])) == sentence
    assert moved(lambda s: s.__setitem__("teachers", [r for r in s["teachers"] if r["_id"] != "newrow0001"])) == sentence
    assert moved(lambda s: s["lessons"].insert(0, copy.deepcopy(L2))) == sentence
    assert moved(lambda s: s["school"].__setitem__("name", "R")) == sentence
    assert moved(lambda s: s["day_structure"][lv].__setitem__(day, "XX")) == sentence
    assert moved(lambda s: s.__setitem__("k", 2)) == sentence

@t
def find_and_gather():
    fresh(); sp = spec(); T = sp["teachers"][0]
    H.add({"kind": "signin", "as": "Ann Lee", "ts": T0 - 5})
    es = save(sp, [["set", "teachers", T["_id"], "short", "AA"], ["set", "teachers", T["_id"], "dept", "Zed"], ["set", "teachers", T["_id"], "name", "Nn"]],
              ANN, "bann", T0)
    later = save(sp, [["set", "lessons", sp["lessons"][0]["_id"], "periods", 5]], BOB, "bbob", T0 + 30)
    older = save(sp, [["set", "lessons", sp["lessons"][1]["_id"], "periods", 5]], BOB, "bold", T0 - 3000)
    assert H.find(es[1]["id"])["id"] == es[1]["id"] and H.find("h0000000000000000") is None and H.find("nope") is None
    sign = H.read(signins=True, kinds={"signin"})[0]
    assert H.find(sign["id"])["kind"] == "signin"
    for e in es:
        u, ents, newer = P.gather(e["id"])
        assert u == "b:bann" and [x["id"] for x in ents] == [x["id"] for x in es]
        assert [x["id"] for x in newer] == [later[0]["id"]], newer
    assert P.gather("nope") is None
    assert P.gather(sign["id"]) is None
    assert P.gather(H.add({"kind": "setup-refused", "text": "r"})["id"]) is None

@t
def sentences_use_school_time():
    os.environ["TZ"] = "UTC"; time.tzset()
    fresh(); sp = spec(); T = sp["teachers"][0]
    ts = datetime.datetime(2026, 11, 19, 23, 30, tzinfo=H.SCHOOL_TZ).timestamp()   # 15:30 UTC
    [a] = save(sp, [["set", "teachers", T["_id"], "short", "AA"]], ANN, "bann", ts - 100)
    save(sp, [["set", "teachers", T["_id"], "short", "BB"]], BOB, "bbob", ts)
    assert P.why_not(*P.gather(a["id"])[1:]).endswith(" on 19 Nov, 11:30 pm")

@t
def annotate_marks_each_unit():
    fresh(); sp = spec(); T = sp["teachers"][0]
    a = save(sp, [["set", "teachers", T["_id"], "short", "AA"], ["set", "teachers", T["_id"], "dept", "Zed"]], ANN, "bann", T0)
    b = save(sp, [["set", "lessons", sp["lessons"][0]["_id"], "periods", 5]], BOB, "bbob", T0 + 60)
    c = save(sp, [["set", "teachers", T["_id"], "short", "CC"]], BOB, "bcc", T0 + 120)
    newer_all = H.read(kinds=P.TOUCH_KINDS, limit=10**7)
    shown = newer_all[:]
    P.annotate(shown, newer_all, lambda ents: ents[0]["batch"] != "bbob")
    by_id = {e["id"]: e for e in shown}
    for e in a:
        assert by_id[e["id"]]["back"] == {"unit": "b:bann", "n": 2, "ok": False, "why": "Can't put back: Bob Tan changed this again on " + H.short_when(c[0]["ts"])}
    assert "back" not in by_id[b[0]["id"]]
    assert by_id[c[0]["id"]]["back"] == {"unit": "b:bcc", "n": 1, "ok": True, "why": None}
    assert P.PUTTABLE == {"group", "depts", "relief", "exams", "admin", "note", "off"}

print(f"test_putback: {COUNT} tests passed")

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
    u, ents, newer = P.gather(es[1]["id"])      # the middle of the save is enough; the app's follow-up is part of the save
    assert [e["id"] for e in ents] == [e["id"] for e in es] + [app["id"]] and newer == [] and P.own(ents) == es
    assert P.why_not(ents, newer) is None and P.why_not(es, [app]) is None
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

@t
def skipped_and_unchanged_ops_give_no_entry():
    sp = spec(); T = sp["teachers"][0]; lv = next(iter(sp["day_structure"])); day = next(iter(sp["day_structure"][lv]))
    same = [["set", "teachers", T["_id"], "short", T["short"]], ["set", "teachers", T["_id"], "nosuchfield", None],
            ["set", "teachers", "no-such-row", "short", "Q"], ["set", "teachers", T["_id"], "_id", "x"],
            ["add", "teachers", copy.deepcopy(T), ""], ["del", "teachers", "no-such-row"],
            ["merge", "lessons", sp["lessons"][0]["_id"], "classes", sp["lessons"][0]["classes"][:1], []],
            ["school", "name", sp["school"].get("name")], ["school", "nosuchkey", None],
            ["day", lv, day, sp["day_structure"][lv][day]], ["top", "nosuchkey", None], ["top", "lessons", []]]
    for op in same:
        assert H.setup_entries(sp, [op], ANN, "bx", 1) == [], op
    es = H.setup_entries(sp, same + [["set", "teachers", T["_id"], "short", "ZZ"]], ANN, "bx", 1)
    assert [(e["op"], e["was"], e["now"]) for e in es] == [("set", T["short"], "ZZ")], es

@t
def band_clash_judges_the_names_the_put_back_leaves():
    sp = spec(); band = copy.deepcopy(sp["blocks"][0]); L = sp["lessons"][0]
    assert P.band_clash(sp, [["set", "lessons", L["_id"], "periods", 1]]) is None            # no band in it: nothing to judge
    sp["blocks"] = [b for b in sp["blocks"] if b["_id"] != band["_id"]] + [dict(band, _id="newband001")]
    assert P.band_clash(sp, [["add", "blocks", band, ""]]) == f"Can't put back: another band is called {band['block']} now."   # a deleted band brought back
    sp = spec(); sp["blocks"].append({"_id": "newband002", "block": "New Band", "level": "Sec 1"}); L = sp["lessons"][0]
    assert P.band_clash(sp, [["del", "blocks", "newband002"]]) is None
    L["block"] = "New Band"
    assert P.band_clash(sp, [["del", "blocks", "newband002"]]) == "Can't put back: lessons or rules joined New Band after this change."   # an added band taken away
    assert P.band_clash(sp, [["set", "lessons", L["_id"], "block", "Sec 1 English"], ["del", "blocks", "newband002"]]) is None   # the lesson goes back with it
    assert P.band_clash(sp, [["set", "blocks", "newband002", "level", "Sec 2"]]) is None and P.band_clash(sp, [["set", "blocks", 5, "block", "x"], 7]) is None

@t
def a_line_with_no_readable_time_is_not_a_crash():
    import json
    fresh(); sp = spec(); T = sp["teachers"][0]
    [a] = save(sp, [["set", "teachers", T["_id"], "short", "AA"]], ANN, "bann", T0)
    b = dict(a, id=a["id"] + "1", batch="bodd", ts="soon", **BOB)
    with open(os.path.join(H.DIR, a["at"][:7] + ".jsonl"), "a") as f: f.write(json.dumps(b) + "\n")
    assert P.why_not([a], [b]).startswith("Can't put back: Bob Tan changed this again on "), P.why_not([a], [b])
    u, ents, newer = P.gather(b["id"])
    assert u == "b:bodd" and [x["id"] for x in ents] == [b["id"]] and H.ts_of(b) is None and H.ts_of(a) == a["ts"]
    assert H.ts_of({"ts": True}) is None and H.ts_of({"ts": float("nan")}) is None and H.ts_of(None) is None
    odd = dict(a, section=["x"], row={"a": 1}, field=["f"])                    # lists where names belong: refused, never a crash
    assert P.changed_since(sp, [odd]) == "Can't put back: this was changed again since." and P.why_not([a], [odd]) is None

def _fake(i, **k):
    return dict({"kind": "setup", "id": "h%016d" % i, "ts": T0 + i, "batch": "bf%d" % i, "op": "set", "section": "lessons",
                 "row": "other%d" % (i % 50), "field": "periods", "as": "Bob Tan", "was": 1, "now": 2}, **k)

@t
def annotate_is_quick_on_a_long_history():
    shown = [_fake(i, row="r%d" % i, field="short", batch="bs%d" % i) for i in range(1, 201)]
    newer = [_fake(i) for i in range(30000, 10000, -1)]
    t0 = time.time()
    P.annotate(shown, newer, lambda ents: True)
    took = time.time() - t0
    print(f"annotate: 200 units against 20000 newer entries in {took:.3f}s")
    assert took < 0.5, took
    assert all(e["back"]["ok"] for e in shown)

@t
def annotate_gives_the_same_answers_as_why_not():
    fresh(); sp = spec(); T = sp["teachers"][0]; L = sp["lessons"]
    units = [
        save(sp, [["set", "teachers", T["_id"], "short", "AA"]], ANN, "b1", T0),
        save(sp, [["set", "teachers", sp["teachers"][1]["_id"], "short", "AA"]], ANN, "b2", T0 + 1),
        save(sp, [["set", "lessons", L[0]["_id"], "periods", 5]], ANN, "b3", T0 + 2),
        save(sp, [["set", "lessons", L[1]["_id"], "periods", 5]], ANN, "b4", T0 + 3),
        save(sp, [["set", "lessons", L[2]["_id"], "periods", 5]], ANN, "b5", T0 + 4),
    ]
    save(sp, [["set", "teachers", T["_id"], "short", "BB"]], BOB, "b6", T0 + 10)           # same field again: blocks b1
    save(sp, [["set", "teachers", sp["teachers"][1]["_id"], "dept", "Zed"]], BOB, "b7", T0 + 11)   # another field: b2 free
    save(sp, [["del", "lessons", L[0]["_id"]]], CARA, "b8", T0 + 12)                          # row deleted: blocks b3
    A_ = [{"kind": "account", "id": "hacc", "ts": T0 + 20, "as": CARA, "who": CARA, "changes": [{"name": "Zed", "field": "group"}]}]
    H.add_many(A_)
    H.add({"kind": "setup-replaced", "ts": T0 + 30, "text": "x", "as": CARA})      # blocks b4 and b5
    save(sp, [["set", "teachers", sp["teachers"][2]["_id"], "short", "CC"]], ANN, "b9", T0 + 40)   # after everything: free
    newer_all = H.read(kinds=P.TOUCH_KINDS, limit=10**7)
    shown = [dict(e) for e in newer_all if e.get("batch") in {"b1", "b2", "b3", "b4", "b5", "b9"}]
    P.annotate(shown, newer_all, lambda ents: True)
    assert len(shown) == 6
    for e in shown:
        es = sorted((x for x in newer_all if x.get("batch") == e["batch"]), key=lambda x: x["id"])
        want = P.why_not(es, [x for x in newer_all if x["id"] > es[-1]["id"]])
        assert e["back"]["why"] == want and e["back"]["ok"] == (want is None), (e["batch"], e["back"], want)
    whys = {e["batch"]: e["back"]["why"] for e in shown}
    assert whys["b9"] is None and whys["b1"].endswith("changed this again on " + H.short_when(T0 + 10)) and whys["b3"].startswith("Can't put back: Cara Ng")
    assert all(whys[b].startswith("Can't put back: the whole setup") for b in ("b2", "b4", "b5"))


# ------------------------------------------------------------------------------------------------ the app
import secrets  # noqa: E402
os.environ.update(SECRET_KEY=secrets.token_hex(16), COMMITTEE_CODE=secrets.token_hex(8))
import app as A  # noqa: E402
from accounts import passwords as PW, people as PP  # noqa: E402

CORA, DEV, HAL, HIA, TEA = "Cora Chen", "Dev Rao", "Hal Soh", "Hia Lim", "Tess Ong"
NOT_HERE = "This change cannot be put back here."
ONLY_COMMITTEE = "Only the timetable committee can put back someone else's change."
PP.update(lambda d: d["people"].update({
    CORA: dict(group="committee", added=True, username="cora.c", pw=PW.hash_pw(secrets.token_hex(8))),
    DEV: dict(group="committee", added=True, username="dev.r", pw=PW.hash_pw(secrets.token_hex(8))),
    HAL: dict(group="hod", added=True, depts=["EL"], username="hal.s", pw=PW.hash_pw(secrets.token_hex(8))),
    TEA: dict(group="teacher", added=True)}))

def as_person(name, via="password"):
    c = A.app.test_client()
    with c.session_transaction() as s:
        s.update(who=name, via=via, n=PP.record(PP.load(), name)["n"])
        if via == "password": s["exp"] = time.time() + 3600
    return c

def start(sp=None):
    fresh(); sp = sp or spec(); store.replace_setup(sp, "test"); return store.setup_record()["spec"]

def change(c, *ops):
    r = c.post("/api/setup/changes", json={"client": "x", "since": store.setup_record()["v"], "ops": [list(o) for o in ops]}); assert r.status_code == 200, r.get_json()
    return r.get_json()

def entries(kind="setup"): return sorted(H.read(kinds=[kind], limit=10 ** 6), key=lambda e: e["id"])

def back(c, eid):
    r = c.post("/api/history/back", json={"id": eid}); return r.status_code, r.get_json()

def field(sec, i, f): return store.setup_record()["spec"][sec][i][f]

@t
def committee_puts_back_a_save():
    sp = start(); T = sp["teachers"][0]; was = T["short"]
    v0 = store.setup_record()["v"]
    change(as_person(CORA), ["set", "teachers", T["_id"], "short", "ZZ"])
    first = entries()[-1]; assert field("teachers", 0, "short") == "ZZ"
    s, j = back(as_person(DEV), first["id"])
    assert (s, j) == (200, {"done": True, "text": "Put back."}), (s, j)
    assert field("teachers", 0, "short") == was
    e = entries()[-1]
    assert e["putback"] == "b:" + first["batch"], e
    assert e["putback_of"] == CORA and e["putback_ts"] == first["ts"] and e["as"] == DEV, e
    r = as_person(DEV).get(f"/api/setup/changes?since={v0}&client=y").get_json()
    assert any(o == ["set", "teachers", T["_id"], "short", was] for p in r["patches"] for o in p["ops"]), r

@t
def a_save_of_three_goes_back_whole():
    sp = start(); T = sp["teachers"][:3]; was = [x["short"] for x in T]
    c = as_person(CORA)
    change(c, *[["set", "teachers", x["_id"], "short", "Q%d" % i] for i, x in enumerate(T)])
    es = entries(); assert len(es) == 3
    j = as_person(DEV).get("/api/history").get_json()
    assert [e["back"]["n"] for e in j["entries"] if e["id"] in {x["id"] for x in es}] == [3, 3, 3], j
    assert back(c, es[1]["id"])[0] == 200
    assert [field("teachers", i, "short") for i in range(3)] == was

@t
def a_resent_save_is_recorded_once():
    sp = start(); T = sp["teachers"][0]; was = T["short"]; v0 = store.setup_record()["v"]
    ops = [["set", "teachers", T["_id"], "short", "ZZ"], ["add", "teachers", {"_id": "newrow0001", "name": "Zed Ng"}, ""]]
    c = as_person(CORA)
    for _ in range(2):   # a lost reply: the page sends the same save again, from the same version
        r = c.post("/api/setup/changes", json={"client": "x", "since": v0, "ops": ops}); assert r.status_code == 200, r.get_json()
    es = entries()
    assert [(e["op"], e["text"]) for e in es] == [("set", T["name"] + ": short " + was + " → ZZ"), ("add", "Added Zed Ng")], es
    j = as_person(DEV).get("/api/history").get_json()
    marks = [e["back"] for e in j["entries"] if e["id"] in {x["id"] for x in es}]
    assert len(marks) == 2 and all(m["ok"] for m in marks), marks
    assert back(as_person(DEV), es[0]["id"]) == (200, {"done": True, "text": "Put back."})
    now = store.setup_record()["spec"]
    assert sync._find(now, "teachers", T["_id"])["short"] == was and sync._find(now, "teachers", "newrow0001") is None
    assert [e["text"] for e in entries()[-2:]] == ["Deleted Zed Ng", T["name"] + ": short ZZ → " + was], entries()[-2:]

def parents_school():
    """a made-up setup using Class Parents: each class has a form teacher"""
    sp = spec()
    for k in sp["classes"]: k["parents"] = ["Form " + k["class"]]
    return sp

def form_time_school():
    """Class Parents, and a subject for them that has no lessons yet"""
    sp = parents_school()
    sp["subjects"].append({"_id": "subjform01", "subject": "Form Time", "code": "FT", "dept": "EL", "periods": {"Sec 1": 1}})
    return sp

@t
def class_parents_follow_ups_go_back_with_the_save():
    sp = parents_school(); sub = sp["subjects"][0]["subject"]; sp["school"]["parents_subjects"] = [sub]
    L = next(x for x in sp["lessons"] if x["subject"] == sub)
    for k in ("block", "code_override"): L.pop(k, None)
    L.update(teachers=["Typed Teacher"], by_hand=True)    # a whole-class lesson whose teacher was typed, not the form teachers
    sp = start(sp); before = copy.deepcopy(sp)
    assert sync._find(sp, "lessons", L["_id"])["teachers"] == ["Typed Teacher"]
    change(as_person(CORA), ["set", "lessons", L["_id"], "block", sp["blocks"][0]["block"]])
    assert [(e["field"], e["was"], e["now"]) for e in entries("app")] == [("by_hand", True, None)], entries("app")
    mine = entries()[-1]
    j = as_person(DEV).get("/api/history").get_json()
    assert [e["back"] for e in j["entries"] if e["id"] == mine["id"]] == [{"unit": "b:" + mine["batch"], "n": 1, "ok": True, "why": None}], j
    assert back(as_person(DEV), mine["id"]) == (200, {"done": True, "text": "Put back."})
    now = store.setup_record()["spec"]
    assert sync._find(now, "lessons", L["_id"])["teachers"] == ["Typed Teacher"], sync._find(now, "lessons", L["_id"])
    assert sync._canon(now) == sync._canon(before)

@t
def a_new_class_parents_subject_goes_back_with_its_lessons():
    sp = start(form_time_school()); before = copy.deepcopy(sp)
    change(as_person(CORA), ["school", "parents_subjects", ["Form Time"]])
    made = [e for e in entries("app") if e["op"] == "add"]
    assert made and all(e["now"]["subject"] == "Form Time" for e in made), entries("app")
    mine = entries()[-1]
    assert back(as_person(DEV), mine["id"]) == (200, {"done": True, "text": "Put back."})
    now = store.setup_record()["spec"]
    assert not any(x["subject"] == "Form Time" for x in now["lessons"]), [x["_id"] for x in now["lessons"] if x["subject"] == "Form Time"]
    assert sync._canon(now) == sync._canon(before)

@t
def a_later_change_to_a_follow_up_blocks_the_save():
    start(form_time_school())
    change(as_person(CORA), ["school", "parents_subjects", ["Form Time"]])
    mine = entries()[-1]; made = [e for e in entries("app") if e["op"] == "add"][0]
    change(as_person(CORA), ["set", "lessons", made["row"], "periods", 2])     # a lesson the app added, changed again
    later = entries()[-1]
    s, j = back(as_person(DEV), mine["id"])
    assert (s, j) == (409, {"error": "Can't put back: " + CORA + " changed this again on " + H.short_when(later["ts"])}), (s, j)
    start(form_time_school()); change(as_person(CORA), ["school", "parents_subjects", ["Form Time"]])
    mine = entries()[-1]; made = [e for e in entries("app") if e["op"] == "add"][0]
    real = store._record
    store._record = lambda es: None              # a lesson the app added swapped for another row, with no entry (so the app adds none)
    try: store.apply_changes([["del", "lessons", made["row"]], ["add", "lessons", dict(made["now"], _id="otherform1"), ""]], "z")
    finally: store._record = real
    assert back(as_person(DEV), mine["id"]) == (409, {"error": "Can't put back: this was changed again since."})

def rename_band(sp, to="Renamed", rules=()):
    """the page's band rename as one save: the band, its lessons and the Block rules that name it; -> (band, old name, the save's first entry)"""
    band = sp["blocks"][0]; old = band["block"]
    change(as_person(CORA), ["set", "blocks", band["_id"], "block", to], *[["set", "lessons", x["_id"], "block", to] for x in sp["lessons"] if x.get("block") == old],
           *[["set", "rules", r["_id"], "target", to] for r in rules])
    return band, old, entries()[-1]

BLOCK_RULE = {"_id": "rule000001", "scope": "Block", "rule": "Not available", "strength": "Must", "note": "made up"}

@t
def a_band_rename_goes_back_with_its_lessons_and_rules():
    sp = start(); rule = dict(BLOCK_RULE, target=sp["blocks"][0]["block"])
    change(as_person(CORA), ["add", "rules", rule, ""]); before = store.setup_record()["spec"]
    band, old, e = rename_band(store.setup_record()["spec"], rules=[rule])
    assert back(as_person(DEV), e["id"]) == (200, {"done": True, "text": "Put back."})
    assert sync._canon(store.setup_record()["spec"]) == sync._canon(before)

@t
def a_band_rename_is_not_put_back_onto_a_name_taken_since():
    for taken in (None, "  sec 1   ENGLISH "):     # the page compares band names trimmed, spaces squeezed, in any case
        sp = start(); band, old, e = rename_band(sp)
        change(as_person(CORA), ["add", "blocks", dict(band, _id="newband001", block=taken or old), ""])
        before = store.setup_record()["spec"]
        assert back(as_person(DEV), e["id"]) == (409, {"error": f"Can't put back: another band is called {old} now."}), taken
        assert sync._canon(store.setup_record()["spec"]) == sync._canon(before)

@t
def a_band_rename_is_not_put_back_when_lessons_or_rules_joined_it():
    sp = start(); band, old, e = rename_band(sp)
    outside = next(x for x in sp["lessons"] if x.get("block") and x["block"] not in (old, "Renamed"))
    change(as_person(CORA), ["set", "lessons", outside["_id"], "block", "Renamed"])
    before = store.setup_record()["spec"]
    assert back(as_person(DEV), e["id"]) == (409, {"error": "Can't put back: lessons or rules joined Renamed after this change."})
    assert sync._canon(store.setup_record()["spec"]) == sync._canon(before)
    sp = start(); band, old, e = rename_band(sp)
    change(as_person(CORA), ["add", "rules", dict(BLOCK_RULE, target="Renamed"), ""])
    assert back(as_person(DEV), e["id"]) == (409, {"error": "Can't put back: lessons or rules joined Renamed after this change."})
    assert sync._find(store.setup_record()["spec"], "blocks", band["_id"])["block"] == "Renamed"

@t
def put_back_twice_is_refused():
    sp = start(); T = sp["teachers"][0]; c = as_person(CORA)
    change(c, ["set", "teachers", T["_id"], "short", "ZZ"]); e = entries()[-1]
    assert back(c, e["id"])[0] == 200
    s, j = back(c, e["id"]); assert s == 409 and j["error"].startswith("Already put back by " + CORA + " on "), j

@t
def put_back_refuses_when_the_value_moved_under_it():
    sp = start(); T = sp["teachers"][0]; c = as_person(CORA)
    change(c, ["set", "teachers", T["_id"], "short", "ZZ"]); e = entries()[-1]
    real = store._record
    store._record = lambda es: None
    try: store.apply_changes([["set", "teachers", T["_id"], "short", "NEW"]], "z")
    finally: store._record = real
    s, j = back(c, e["id"])
    assert (s, j) == (409, {"error": "Can't put back: this was changed again since."}), (s, j)
    assert field("teachers", 0, "short") == "NEW"

@t
def head_puts_back_only_their_own():
    sp = start(); L = sp["lessons"][0]; assert L["dept"] == "EL"
    h = as_person(HAL)
    change(h, ["set", "lessons", L["_id"], "periods", 9]); mine = entries()[-1]
    change(as_person(CORA), ["set", "lessons", sp["lessons"][1]["_id"], "periods", 7]); theirs = entries()[-1]
    j = h.get("/api/history").get_json()
    by_id = {e["id"]: e for e in j["entries"]}
    assert by_id[mine["id"]]["back"]["ok"] is True and "back" not in by_id[theirs["id"]], j
    assert back(h, theirs["id"]) == (403, {"error": ONLY_COMMITTEE})
    assert field("lessons", 1, "periods") == 7
    assert back(h, mine["id"])[0] == 200 and field("lessons", 0, "periods") == L["periods"]

@t
def head_put_back_judged_on_the_setup_now():
    sp = start(); L = sp["lessons"][0]; h = as_person(HAL)
    change(h, ["set", "lessons", L["_id"], "periods", 9]); mine = entries()[-1]
    sub = next(x for x in sp["subjects"] if x["subject"] == L["subject"])
    change(as_person(CORA), ["set", "subjects", sub["_id"], "dept", "MA"])   # the lesson's department follows its subject
    s, j = back(h, mine["id"]); assert s == 409 and j["error"] and "changed again" not in j["error"], (s, j)
    assert field("lessons", 0, "periods") == 9

@t
def cannot_put_back_kinds():
    sp = start(); L = sp["lessons"][0]
    h = as_person(HAL); change(h, ["set", "lessons", sp["lessons"][5]["_id"], "periods", 3])   # another department: refused
    refused = entries("setup-refused")[-1]
    ids = [refused["id"]]
    for k in ("signin", "board", "relief"): ids.append(H.add({"kind": k, "who": CORA, "as": CORA, "text": k})["id"])
    store.replace_setup(spec(), "again"); ids.append(entries("setup-replaced")[-1]["id"])
    j = as_person(CORA).get("/api/history?signins=1").get_json()
    assert j["entries"] and all("back" not in e for e in j["entries"] if e["id"] in ids), j
    c = as_person(CORA)
    for i in ids: assert back(c, i) == (409, {"error": NOT_HERE}), i
    assert back(c, "h-none")[0] == 404 and back(c, "h-none")[1] == {"error": "That entry is not in the history."}

@t
def a_broken_line_is_skipped():
    sp = start(); T = sp["teachers"][0]; c = as_person(CORA)
    change(c, ["set", "teachers", T["_id"], "short", "ZZ"]); e = entries()[-1]
    with open(os.path.join(H.DIR, e["at"][:7] + ".jsonl"), "a") as f: f.write('{"kind": "set')
    r = c.get("/api/history"); assert r.status_code == 200
    assert any("back" in x for x in r.get_json()["entries"]), r.get_json()

@t
def teacher_cannot_post():
    start()
    r = as_person(TEA, "code").post("/api/history/back", json={"id": "x"}); assert r.status_code == 401, r.status_code
    assert A.app.test_client().post("/api/history/back", json={"id": "x"}).status_code == 401

print(f"test_putback: {COUNT} tests passed")

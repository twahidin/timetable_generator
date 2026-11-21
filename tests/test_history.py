"""Plain-assert tests for the history file: .venv/bin/python tests/test_history.py"""
import copy, datetime, os, sys, tempfile, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = tempfile.mkdtemp()
os.environ.update(DATA_DIR=DATA, AI_API_KEY="")
sys.path.insert(0, ROOT)
import history as H, store, sync  # noqa: E402
from ttgen import samples  # noqa: E402

COUNT = 0
def t(f):
    global COUNT
    f(); COUNT += 1
    return f

def fresh():
    if os.path.isdir(H.DIR):
        for n in os.listdir(H.DIR): os.remove(os.path.join(H.DIR, n))

def month_file(entry):
    return os.path.join(H.DIR, entry["at"][:7] + ".jsonl")

@t
def add_and_read_newest_first():
    fresh()
    a = H.add({"kind": "app", "text": "one"}); b = H.add({"kind": "app", "text": "two"})
    assert a["id"].startswith("h") and len(a["id"]) == 17 and a["id"] < b["id"], (a["id"], b["id"])
    assert isinstance(a["ts"], float) and a["at"][:4].isdigit()
    assert [e["text"] for e in H.read()] == ["two", "one"]
    both = H.add_many([{"kind": "app", "text": "x"}, {"kind": "app", "text": "y"}])
    assert len(both) == 2 and both[0]["id"] < both[1]["id"]
    assert H.read(limit=2)[0]["text"] == "y"
    assert H.by_of("Ann Lee", "password") == {"who": "Ann Lee", "as": "Ann Lee", "via": "password"}
    assert H.by_of(None, "shared", "Shared teacher code") == {"who": None, "as": "Shared teacher code", "via": "shared"}
    assert H.by_of(None, "?")["as"] == "Unknown"

@t
def forbidden_keys_dropped():
    fresh()
    e = H.add({"kind": "account", "text": "t", "password": "p", "now": {"code": "c", "keep": 1, "l": [{"token": "z", "ok": 2}]}})
    assert "password" not in e and e["now"] == {"keep": 1, "l": [{"ok": 2}]}, e
    raw = open(month_file(e)).read()
    assert '"password"' not in raw and '"code"' not in raw and '"token"' not in raw

@t
def half_line_skipped():
    fresh()
    e = H.add({"kind": "app", "text": "good1"})
    with open(month_file(e), "a") as f: f.write('{"kind": "set')
    H.add({"kind": "app", "text": "good2"})
    assert [x["text"] for x in H.read()] == ["good2", "good1"]
    last = open(month_file(e)).read().splitlines()[-1]
    import json; assert json.loads(last)["text"] == "good2"

@t
def filters():
    fresh()
    H.add({"kind": "setup", "who": "Ann", "where": "Step 4 · Teachers", "depts": ["Maths"], "text": "a"})
    H.add({"kind": "setup", "who": "Bob", "where": "Step 5 · Department map", "depts": ["Science", "Maths"], "text": "b"})
    H.add({"kind": "signin", "who": "Ann", "text": "in"})
    H.add({"kind": "relief", "who": "Bob", "text": "c"})
    assert [e["text"] for e in H.read()] == ["c", "b", "a"]
    assert len(H.read(signins=True)) == 4
    assert [e["text"] for e in H.read(who="Ann")] == ["a"]
    assert [e["text"] for e in H.read(where="Step 5 · Department map")] == ["b"]
    assert [e["text"] for e in H.read(dept="Maths")] == ["b", "a"]
    assert [e["text"] for e in H.read(kinds=["relief"])] == ["c"]
    allr = H.read()
    assert [e["text"] for e in H.read(before=allr[0]["id"])] == ["b", "a"]
    assert [e["text"] for e in H.read(before=allr[0]["id"], limit=1)] == ["b"]
    now = time.time()
    assert len(H.read(since=now - 60, until=now + 60)) == 3
    assert H.read(until=now - 3600) == [] and H.read(since=now + 3600) == []

@t
def prune_two_years():
    fresh()
    today = datetime.date(2026, 11, 21)
    for n in ("2024-10.jsonl", "2024-11.jsonl", "2026-11.jsonl", "notes.txt"):
        open(os.path.join(H.DIR, n), "w").write("")
    assert H.prune(today) == 1
    assert sorted(os.listdir(H.DIR)) == ["2024-11.jsonl", "2026-11.jsonl", "notes.txt"]
    assert H.prune(today) == 0

@t
def uses_counts_last_week():
    fresh()
    H.add({"kind": "app", "text": "n"})
    H.add({"kind": "app", "text": "n"})
    H.add({"kind": "relief", "text": "n"})
    old = time.time() - 10 * 86400
    H.add({"kind": "app", "text": "n", "ts": old})
    assert H.uses() == 3 and H.uses(kind="app") == 2 and H.uses(30, kind="app") == 3 and H.uses(kind="zzz") == 0

@t
def setup_entries_values():
    spec = samples.secondary(); sync.ensure_ids(spec)
    before = copy.deepcopy(spec)
    L = next(r for r in spec["lessons"] if r["level"] == "Sec 3" and r["teachers"] and sync.lesson_dept(spec, r))
    old = L["teachers"]; new = ["Joseph Lim"]
    dept = sync.lesson_dept(spec, L)
    assert dept
    by = H.by_of("Ann Lee", "password")
    row = {"_id": "newrow0001", "name": "Zed Ng", "dept": "Maths"}
    ops = [["set", "lessons", L["_id"], "teachers", new],
           ["add", "teachers", row, ""],
           ["set", "teachers", "newrow0001", "dept", "Science"],
           ["del", "classes", spec["classes"][0]["_id"]]]
    ops_copy = copy.deepcopy(ops)
    es = H.setup_entries(spec, ops, by, "b1", 7)
    assert spec == before and ops == ops_copy
    assert len(es) == 4 and all(e["kind"] == "setup" and e["batch"] == "b1" and e["v"] == 7 and e["as"] == "Ann Lee" for e in es)
    e = es[0]
    assert (e["was"], e["now"], e["section"], e["field"]) == (old, new, "lessons", "teachers") and e["row"] == L["_id"]
    assert dept in e["depts"] and e["where"] == "Step 5 · Department map" and e["op"] == "set"
    assert e["text"] == f"{H.row_label('lessons', L)}: teachers {', '.join(old)} → Joseph Lim", e["text"]
    assert e["label"].startswith("Sec 3 ")
    assert es[1]["was"] is None and es[1]["now"]["name"] == "Zed Ng" and es[1]["text"] == "Added Zed Ng"
    assert es[2]["was"] == "Maths" and es[2]["now"] == "Science" and set(es[2]["depts"]) == {"Maths", "Science"}
    assert es[3]["now"] is None and es[3]["was"]["class"] == spec["classes"][0]["class"] and es[3]["text"].startswith("Deleted ")
    assert H.row_label("x", None) == "(gone)"
    s2 = H.setup_entries(spec, [["school", "name", "X"], ["day", "Sec 1", "Mon", None], ["top", "k", 1]], by, "b2", 8)
    assert [e["where"] for e in s2] == ["School & day"] * 3 and s2[0]["text"].startswith("name: ")

@t
def code_kept_in_setup_rows_only():
    fresh()
    spec = samples.secondary(); sync.ensure_ids(spec)
    L = spec["lessons"][0]
    assert L.get("code")
    [e] = H.setup_entries(spec, [["del", "lessons", L["_id"]]], H.by_of("Ann", "password"), "b", 1)
    w = H.add(e)["was"]
    assert w["code"] == L["code"] and H.read()[0]["was"]["code"] == L["code"]
    a = H.add({"kind": "account", "password": "p", "changes": [{"field": "pw", "code": "x"}], "now": {"code": "y"}})
    assert a["changes"] == [{"field": "pw"}] and "password" not in a and a["now"] == {}

@t
def setup_entries_never_raises():
    spec = samples.secondary(); sync.ensure_ids(spec)
    T = spec["teachers"][0]
    ops = [["merge", "teachers", T["_id"], "can_teach", ["X"]], ["set", "nosuch", "a", "f", 1],
           ["set", "teachers", T["_id"], "note", "hi"], 5, [], ["merge"], ["add", "teachers", "notadict", ""]]
    es = H.setup_entries(spec, ops, H.by_of("Ann", "password"), "b", 1)
    assert [e["op"] for e in es] == ["set"] and es[0]["now"] == "hi", es

@t
def row_label_every_section():
    spec = samples.secondary(); sync.ensure_ids(spec)
    spec["roles"] = [{"role": "Head of Department", "_id": "r1"}]
    for sec, f in (("venues", "room"), ("classes", "class"), ("subjects", "subject"), ("teachers", "name"),
                   ("blocks", "block"), ("students", "name"), ("roles", "role")):
        row = spec[sec][0]
        assert H.row_label(sec, row) == row[f], (sec, H.row_label(sec, row))
    c = spec["combinations"][0]
    assert H.row_label("combinations", c) == (c.get("name") or c["code"])
    assert H.row_label("combinations", {"code": "S1"}) == "S1"
    r = spec["rules"][0]
    assert H.row_label("rules", r) == f"{r['target']} · {r['rule']}"
    assert H.row_label("choices", {"kind": "recess", "level": "Sec 1"}) == "recess Sec 1"
    assert H.row_label("choices", {"kind": "setting", "key": "k"}) == "setting k"
    assert H.row_label("lessons", {"level": "Sec 3", "subject": "Physics", "classes": ["3B"]}) == "Sec 3 Physics 3B"

@t
def stray_files_and_non_dict():
    fresh()
    H.add({"kind": "app", "text": "a"})
    for n in ("2024-xx.jsonl", "notes.txt"):
        open(os.path.join(H.DIR, n), "w").write("junk\n")
    assert H.prune(datetime.date(2026, 11, 21)) == 0 and len(H.read()) == 1
    assert {"2024-xx.jsonl", "notes.txt"} <= set(os.listdir(H.DIR))
    for bad in ("x", None, [1]):
        try: H.add(bad)
        except TypeError: pass
        else: raise AssertionError("no TypeError")
    try: H.add_many([{"kind": "app"}, 3])
    except TypeError: pass
    else: raise AssertionError("no TypeError")
    assert len(H.read()) == 1

print(f"{COUNT} history tests passed")

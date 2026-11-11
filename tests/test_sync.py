"""Plain-assert tests for sync.py: run with .venv/bin/python tests/test_sync.py"""
import copy
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import sync  # noqa: E402


def canon(x):
    return json.dumps(x, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def norm(x, top=True):
    """Compare form: no nulls, no `_` keys (except `_id`), rows ordered by _id."""
    if isinstance(x, dict):
        out = {}
        for k, v in x.items():
            if v is None or (k.startswith("_") and k != "_id"):
                continue
            if top and k in sync.LISTS and isinstance(v, list):
                v = sorted(v, key=lambda r: r.get("_id", ""))
            out[k] = norm(v, False)
        return out
    if isinstance(x, list):
        return [norm(v, False) for v in x]
    return x


def same(a, b):
    return canon(norm(a)) == canon(norm(b))


with open(os.path.join(HERE, "sync_cases.json"), encoding="utf-8") as f:
    CASES = json.load(f)

passed = 0
for case in CASES:
    name, base = case["name"], case["base"]
    if "ops" in case:
        got = sync.diff(base, case["cur"])
        assert canon(got) == canon(case["ops"]), (name, "diff", canon(got))
        spec = copy.deepcopy(base)
        assert sync.apply(spec, case["ops"]) == 0, (name, "skipped")
        assert same(spec, case["cur"]), (name, "apply", canon(norm(spec)))
    else:
        spec = copy.deepcopy(base)
        sync.apply(spec, case["theirs"])
        sync.apply(spec, case["mine"])
        assert same(spec, case["merged"]), (name, "merge", canon(norm(spec)))
    passed += 1

# constants and ids
assert sync.MERGE == {"teachers": ("can_teach",), "students": ("groups",)}
assert sync.LISTS == ("venues", "classes", "subjects", "teachers", "blocks", "lessons",
                      "rules", "students", "combinations", "roles", "choices")
i = sync.new_id()
assert len(i) == 10 and all(c in "abcdefghijklmnopqrstuvwxyz0123456789" for c in i)
assert sync.new_id() != sync.new_id()

# ensure_ids
spec = {"school": {"name": "A"}, "classes": [{"class": "1A"}, {"_id": "keep", "class": "1B"}],
        "teachers": [{"name": "Tan"}]}
assert sync.ensure_ids(spec) is True
assert spec["classes"][1]["_id"] == "keep"
ids = [spec["classes"][0]["_id"], spec["teachers"][0]["_id"]]
assert all(len(x) == 10 for x in ids) and ids[0] != ids[1]
before = copy.deepcopy(spec)
assert sync.ensure_ids(spec) is False and spec == before
assert sync.ensure_ids({"school": {}}) is False
passed += 1

# skips and edge behaviour
spec = {"classes": [{"_id": "c1", "size": 1}]}
assert sync.apply(spec, [["set", "classes", "zz", "size", 2], ["del", "classes", "zz"],
                         ["add", "classes", {"_id": "c1"}, ""],
                         ["merge", "classes", "zz", "x", [], []],
                         ["bogus"], ["top", "classes", []]]) == 6
assert spec == {"classes": [{"_id": "c1", "size": 1}]}
assert sync.apply(spec, [["add", "classes", {"_id": "c0"}, ""],
                         ["add", "classes", {"_id": "c9"}, "nope"],
                         ["set", "classes", "c1", "size", None],
                         ["top", "extra_sheets", {"a": 1}]]) == 0
assert [r["_id"] for r in spec["classes"]] == ["c0", "c1", "c9"]
assert spec["classes"][1] == {"_id": "c1"} and spec["extra_sheets"] == {"a": 1}
passed += 1

# malformed merge lists are skipped, never half-applied or raised
for bad in ("x", {"a": 1}, None, 5):
    for pos in (4, 5):
        op = ["merge", "teachers", "t1", "can_teach", [], []]
        op[pos] = bad
        spec = {"teachers": [{"_id": "t1", "can_teach": [1]}]}
        assert sync.apply(spec, [op]) == 1, ("merge", bad, pos)
        assert spec == {"teachers": [{"_id": "t1", "can_teach": [1]}]}
passed += 1

# non-dict school / day_structure / level are replaced, not raised on
spec = {"school": None, "day_structure": None}
assert sync.apply(spec, [["school", "name", "B"], ["day", "Sec 1", "Mon", "FL"]]) == 0
assert spec == {"school": {"name": "B"}, "day_structure": {"Sec 1": {"Mon": "FL"}}}
spec = {"day_structure": {"Sec 1": None, "Sec 2": "x"}}
assert sync.apply(spec, [["day", "Sec 1", "Mon", "FL"], ["day", "Sec 2", "Mon", None]]) == 0
assert spec["day_structure"]["Sec 1"] == {"Mon": "FL"}
spec = {"school": "oops"}
assert sync.apply(spec, [["school", "name", None]]) == 0 and spec["school"] == {}
passed += 1

# what a head of department may change
spec = {"teachers": [{"_id": "t1", "provisional": "No"}, {"_id": "t2", "provisional": "Yes"}, {"_id": "t3"}], "classes": [{"_id": "c1"}]}
for ok in ([["set", "lessons", "l1", "students", 12]], [["add", "blocks", {"_id": "b9"}, ""]], [["del", "lessons", "l1"]],
           [["merge", "teachers", "t1", "can_teach", [], []]], [["add", "teachers", {"_id": "t9", "provisional": "No"}, ""]],
           [["set", "teachers", "t2", "name", "X"]], [["del", "teachers", "t2"]], []):
    assert sync.head_may(spec, ok) is None, ok
for bad in ([["set", "classes", "c1", "size", 9]], [["school", "name", "X"]], [["day", "Sec 1", "Mon", "FL"]], [["top", "k", 1]],
            [["set", "teachers", "t1", "name", "X"]], [["set", "teachers", "t3", "name", "X"]], [["del", "teachers", "t1"]],
            [["set", "teachers", "t2", "provisional", "No"]], [["add", "classes", {"_id": "c2"}, ""]],
            [["set", "lessons", "l1", "students", 1], ["set", "classes", "c1", "size", 9]], ["x"], [[]], [["set"]]):
    why = sync.head_may(spec, bad)
    assert isinstance(why, str) and why.endswith("."), bad
assert "classes" in sync.head_may(spec, [["set", "classes", "c1", "size", 9]])
passed += 1

# a head's batch is split: what they may make is applied, the rest is refused with a reason (index in the batch)
spec = {"teachers": [{"_id": "t1", "provisional": "No"}], "classes": [{"_id": "c1"}]}
batch = [["set", "lessons", "l1", "students", 12], ["set", "classes", "c1", "size", 9],
         ["add", "teachers", {"_id": "t9", "name": "N"}, ""], ["set", "teachers", "t9", "short", "NN"],
         ["set", "teachers", "t1", "name", "X"]]
ok, refused = sync.head_split(spec, batch)
assert ok == [batch[0], batch[2], batch[3]], ok
assert [i for i, _ in refused] == [1, 4], refused
assert refused[0][1] == sync.head_may(spec, [batch[1]]) and "classes" in refused[0][1]
assert "provisional" in refused[1][1] and all(w.endswith(".") for _, w in refused)
assert sync.head_split(spec, []) == ([], [])
assert sync.head_may(spec, batch) == refused[0][1]
assert sync.head_split(spec, ["x", [["set"]]])[1][0] == (0, "Department heads cannot send that change.")
passed += 1

# choices are a list; ensure_ids links each to its rule by the rule's _id, and a head cannot touch them
spec = {"rules": [{"rule": "In words"}], "choices": [{"kind": "rule", "rule": 0}, {"kind": "rule", "rule": 7}]}
assert "choices" in sync.LISTS
assert sync.ensure_ids(spec) is True
a, b = spec["choices"]
assert a["_id"] and b["_id"] and a["rule_id"] == spec["rules"][0]["_id"] and b["rule_id"] is None, spec
assert "rule" not in a and "rule" not in b, spec
assert sync.ensure_ids(spec) is False
why = sync.head_split(spec, [["add", "choices", {"kind": "rule"}, ""]])[1][0][1]
assert "choices" in why, why
passed += 1

# a list section that is null or not a list: add starts it as a list, del / set / merge skip (same as sync.js)
for bad in (None, "x", {"a": 1}):
    spec = {"roles": bad}
    assert sync.apply(spec, [["add", "roles", {"_id": "r1", "role": "EO"}, ""]]) == 0, bad
    assert spec == {"roles": [{"_id": "r1", "role": "EO"}]}, spec
    spec = {"roles": bad}
    assert sync.apply(spec, [["del", "roles", "r1"], ["set", "roles", "r1", "role", "X"],
                             ["merge", "roles", "r1", "x", [1], []]]) == 3, bad
    assert spec == {"roles": bad}
passed += 1

# a head may not touch the lessons the Class Parents take: the staffed rows' teachers, mark, subject, block, code, classes,
# level, nor delete one, nor make a row staffed that was not (an add, or a set that leaves it staffed)
SUBJ = "Form Period"
def staffed_setup():
    return {"school": {"parents_subjects": [SUBJ]}, "subjects": [{"_id": "s1", "subject": SUBJ}, {"_id": "s2", "subject": "Maths"}],
            "classes": [{"_id": "c1", "class": "1A", "level": "Sec 1", "parents": ["Lim", "Tan"]}, {"_id": "c2", "class": "1B", "level": "Sec 1"}],
            "lessons": [dict(_id="L1", level="Sec 1", subject=SUBJ, block=None, classes=["1A"], teachers=["Lim", "Tan"]),
                        dict(_id="L2", level="Sec 1", subject="Maths", block=None, classes=["1A"], teachers=["Ong"]),
                        dict(_id="L3", level="Sec 1", subject=SUBJ, block="Band A", classes=["1A"], teachers=["Ong"])]}
sp = staffed_setup()
WHY = "Only the committee can change these lessons: their teachers are the class's form teachers."
for op in (["set", "lessons", "L1", "teachers", ["Koh"]], ["set", "lessons", "L1", "by_hand", True], ["del", "lessons", "L1"],
           ["set", "lessons", "L1", "subject", "Maths"], ["set", "lessons", "L1", "block", "Band A"], ["set", "lessons", "L1", "classes", ["1B"]],
           ["set", "lessons", "L1", "level", "Sec 2"], ["set", "lessons", "L1", "code_override", "X"],
           ["set", "lessons", "L2", "subject", SUBJ],                    # the ordinary row would become staffed
           ["set", "lessons", "L3", "block", None],                      # so would a block row with its block cleared
           ["add", "lessons", dict(_id="n1", level="Sec 1", subject=SUBJ, block=None, classes=["1B"], teachers=[]), ""]):
    assert sync.head_may(sp, [op]) == WHY, op
for op in (["set", "lessons", "L2", "teachers", ["Koh"]], ["set", "lessons", "L1", "note", "x"], ["set", "lessons", "L1", "students", 9],
           ["set", "lessons", "L3", "teachers", ["Koh"]],                # a block row of the named subject is not staffed
           ["add", "lessons", dict(_id="n2", level="Sec 1", subject=SUBJ, block="Band A", classes=["1B"], teachers=[]), ""],
           ["add", "lessons", dict(_id="n3", level="Sec 1", subject="Maths", block=None, classes=["1B"], teachers=[]), ""], ["del", "lessons", "L2"]):
    assert sync.head_may(sp, [op]) is None, op
assert sync.head_split(sp, [["set", "lessons", "L2", "students", 1], ["del", "lessons", "L1"]]) == ([["set", "lessons", "L2", "students", 1]], [(1, WHY)])
# one batch cannot get round it: each op is judged on the setup as the allowed ones before it leave it
for first, then in ((dict(_id="n8", level="Sec 1", subject="Maths", block=None, classes=["1A"], teachers=["Typed T"]), ["set", "lessons", "n8", "subject", SUBJ]),
                    (dict(_id="n8", level="Sec 1", subject=SUBJ, block="Band A", classes=["1B"], teachers=[]), ["set", "lessons", "n8", "block", None])):
    ok, refused = sync.head_split(sp, [["add", "lessons", first, ""], then])
    assert ok == [["add", "lessons", first, ""]] and refused == [(1, WHY)], (ok, refused)
    assert [r["_id"] for r in sp["lessons"]] == ["L1", "L2", "L3"]       # the setup judged on is not changed
passed += 1

print(f"{passed} cases passed")

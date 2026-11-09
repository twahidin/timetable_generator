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
                      "rules", "students", "combinations", "roles")
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

print(f"{passed} cases passed")

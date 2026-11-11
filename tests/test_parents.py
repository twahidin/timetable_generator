"""Plain-assert tests for ttgen/parents.py: run with .venv/bin/python tests/test_parents.py"""
import copy
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from ttgen import parents as P  # noqa: E402

with open(os.path.join(HERE, "parents_cases.json"), encoding="utf-8") as f:
    CASES = json.load(f)

passed = 0
for c in CASES:
    spec = copy.deepcopy(c["spec"])
    if "adopt" in c:
        P.adopt(spec, c["adopt"])
    P.derive(spec)
    assert spec == c["after"], (c["name"], spec)
    assert P.derive(spec) is False, (c["name"], "second derive")
    assert spec == c["after"], (c["name"], "second derive leaves it")
    passed += 1

spec = {
    "school": {"parents_subjects": ["CE 1", "Art", "CP Time"], "parents_max": 2, "parents_name": "  "},
    "subjects": [{"_id": "s1", "subject": "CP Time"}, {"_id": "s2", "subject": "CE 1"}],
    "classes": [{"_id": "c1", "class": "1A", "level": "Sec 1", "parents": ["Tan", None, "Lim"]}],
}
whole = {"subject": "CE 1", "classes": ["1A"], "teachers": ["Lim", ""]}
assert P.names(whole) == ["Lim"]
assert P.names(spec["classes"][0]) == ["Tan", "Lim"]
assert P.names({}) == []
assert P.subjects(spec) == ["CE 1", "CP Time"]
assert P.subjects({"school": {}}) == []
assert P.staffed(spec, whole) is True
assert P.staffed(spec, {"subject": "CE 1", "block": "Band"}) is False
assert P.staffed(spec, {"subject": "CE 1", "code_override": "X"}) is False
assert P.staffed(spec, {"subject": "Art"}) is False
assert P.follows(spec, whole) is True
assert P.follows(spec, dict(whole, by_hand=True)) is False
assert P.want(spec, whole) == ["Tan", "Lim"]
assert P.want(spec, {"subject": "CE 1", "classes": ["1B"]}) == []
assert P.same(["Tan", "Lim"], ["Lim", "Tan"]) is True
assert P.same(["Tan"], ["Tan", "Lim"]) is False
assert P.same([], [None]) is True
for given, expect in [(2, 3), (4, 4), ("4", 4), (6, 6), (7, 3), (0, 3), (2.5, 3), ("x", 3), ("0x10", 3), ([4], 3), (None, 3),
                      (float("inf"), 3), (True, 3)]:
    assert P.cap({"school": {"parents_max": given}}) == expect, ("cap", given)
assert P.cap({"school": {}}) == 3
assert P.cap({}) == 3
assert P.label(spec) == "Form teachers"
assert P.label({"school": {"parents_name": " Class Parents "}}) == "Class Parents"
assert P.label({}) == "Form teachers"
passed += 1

# adopt on a spec with nothing to do adds no keys
s = {"school": {}, "lessons": [], "classes": []}
assert P.adopt(s, None) == 0
assert P.derive(s) is False
assert s == {"school": {}, "lessons": [], "classes": []}
assert P.derive({}) is False
passed += 1

print(f"{passed} cases passed")

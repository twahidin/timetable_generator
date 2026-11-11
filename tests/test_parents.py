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


# ---- the workbook (Task 3): Teacher columns that grow, Class Parents columns and Settings rows, Changed by hand
import tempfile  # noqa: E402
import openpyxl  # noqa: E402
from ttgen import reader, template, spec as SPEC  # noqa: E402
from ttgen.samples import primary  # noqa: E402

SUBJ = "Mathematics"
KEYS = ("parents_name", "parents_max", "parents_subjects")
FOUR = ["Adeline Tan", "Benjamin Teo", "Charmaine Yeo", "Darren Lim"]


def with_parents(sp):
    sp = copy.deepcopy(sp)
    sp["school"].update(parents_name="Class Parents", parents_max=4, parents_subjects=[SUBJ])
    cls = {c["class"]: c for c in sp["classes"]}
    cls["1A"]["parents"] = list(FOUR)
    cls["1B"]["parents"] = ["Evelyn Ong"]
    for x in sp["lessons"]:
        if x["subject"] == SUBJ and x["classes"] == ["1A"]:
            x["teachers"] = list(FOUR)                                  # follows: the same people as the boxes
            x["note"], x["room_weeks"] = "a note", "Odd"
        if x["subject"] == SUBJ and x["classes"] == ["1B"]:
            x["by_hand"] = True                                         # typed teachers, kept
    return sp


def write(sp, drop=None):
    d = tempfile.mkdtemp(); p = os.path.join(d, "s.xlsx"); template.write_template(sp, p)
    if drop:
        wb = openpyxl.load_workbook(p); ws = wb["6 Lessons"]
        ws.delete_cols(next(j for j in range(1, ws.max_column + 1) if ws.cell(5, j).value == drop)); wb.save(p)
    return p


def read(p):
    return reader.read_template(p)


def teachers_of(sp):
    return [[t for t in x.get("teachers") or [] if t] for x in sp["lessons"]]


def notes_and_room_weeks(sp):
    return [(x.get("note"), x.get("room_weeks")) for x in sp["lessons"]]


def headings(p, sheet):
    ws = openpyxl.load_workbook(p)[sheet]
    return [ws.cell(5, j).value for j in range(1, ws.max_column + 1) if ws.cell(5, j).value]


def lessons_headings(p): return headings(p, "6 Lessons")
def classes_headings(p): return headings(p, "2 Classes")
def settings_labels(p):
    ws = openpyxl.load_workbook(p)["Settings"]; return [ws.cell(r, 1).value for r in range(5, ws.max_row + 1) if ws.cell(r, 1).value]


def t(f):
    global passed
    f(); passed += 1


@t
def four_teachers_and_class_parents_survive_the_workbook():
    sp = with_parents(primary())
    a = read(write(sp)); b = read(write(a))
    assert teachers_of(a) == teachers_of(sp) and any(len(x["teachers"]) == 4 for x in a["lessons"])
    assert [c.get("parents") or [] for c in a["classes"]] == [c.get("parents") or [] for c in sp["classes"]]
    assert {k: a["school"].get(k) for k in KEYS} == dict(parents_name="Class Parents", parents_max=4, parents_subjects=[SUBJ])
    assert [bool(x.get("by_hand")) for x in a["lessons"]] == [bool(x.get("by_hand")) for x in sp["lessons"]] and any(x.get("by_hand") for x in a["lessons"])
    assert not any(x.get("by_hand") is False for x in a["lessons"]) and not any("parents" in c and not c["parents"] for c in a["classes"])
    assert notes_and_room_weeks(a) == notes_and_room_weeks(sp) and ("a note", "Odd") in notes_and_room_weeks(a)
    assert a["school"]["extra_settings"] == sp["school"].get("extra_settings", []) and b == a
    h = lessons_headings(write(sp)); assert h[-1] == "Changed by hand" and "Teacher 4" in h and "Teacher 5" not in h
    assert classes_headings(write(sp))[5:] == ["Note"] + [f"Class Parents {i}" for i in range(1, 5)]
    assert [x for x in settings_labels(write(sp)) if str(x).startswith(("Form teachers", "Most form teachers"))] == ["Form teachers are called", "Most form teachers for a class", "Form teachers take these lessons"]


@t
def a_workbook_from_before_reads_as_before():
    sp = read(write(primary())); assert not any("parents" in c for c in sp["classes"]) and not any(k in sp["school"] for k in KEYS) and not any(x.get("by_hand") for x in sp["lessons"])
    h = lessons_headings(write(primary())); assert [x for x in h if x.startswith("Teacher ") and x != "Teacher periods"] == ["Teacher 1", "Teacher 2", "Teacher 3"] and h[-1] == "Changed by hand"
    assert not any(str(k).startswith(("Form teachers", "Most form teachers")) for k in settings_labels(write(primary()))) and classes_headings(write(primary()))[-1] == "Note"
    # a workbook with only three Teacher columns and no Changed by hand column: no adopt, nothing new
    old = read(write(primary(), drop="Changed by hand")); assert old == sp


@t
def a_workbook_without_the_column_keeps_typed_teachers():
    sp = with_parents(primary())
    for x in sp["lessons"]: x.pop("by_hand", None)
    sp["lessons"][[i for i, x in enumerate(sp["lessons"]) if x["subject"] == SUBJ and x["classes"] == ["1B"]][0]]["teachers"] = ["Nadia Kumar"]
    back = read(write(sp, drop="Changed by hand"))
    got = {x["classes"][0]: x for x in back["lessons"] if x["subject"] == SUBJ}
    assert got["1B"].get("by_hand") is True and "by_hand" not in got["1A"] and "by_hand" not in got["1C"], {k: v.get("by_hand") for k, v in got.items()}
    again = read(write(back)); assert again == back                           # the column is there now: no second adopt, nothing lost
    plain = sp; plain["school"]["parents_subjects"] = []
    assert not any(x.get("by_hand") for x in read(write(plain, drop="Changed by hand"))["lessons"])   # nothing named: nothing adopted


@t
def the_workbook_does_not_check_can_teach_on_the_named_subjects():
    def check(sp):
        ws = openpyxl.load_workbook(write(sp))["6 Lessons"]
        ck = next(j for j in range(1, ws.max_column + 1) if ws.cell(5, j).value == "Check")
        return ws.cell(6, ck).value
    f = check(with_parents(primary())); g = check(primary())
    assert f'B6="{SUBJ}"' in f and "not set to teach" in f and "No teacher." in f and "twice in this block" in f   # the guard is on the Can teach branch only
    assert 'OR(B6=' not in g and "not set to teach" in g and "No teacher." in g                                       # nothing named: the formula is as before
    two = with_parents(primary()); two["school"]["parents_subjects"] = [SUBJ, "Art"]
    assert f'OR(B6="{SUBJ}",B6="Art")' in check(two)


@t
def the_skill_version_is_2026_11_3():
    root = os.path.dirname(HERE)
    assert SPEC.SKILL_VERSION == "2026-11.3"
    assert "2026-11.3" in open(os.path.join(root, "skill", "school-timetable-generator", "SKILL.md"), encoding="utf-8").read()
    assert "2026-11.3" in open(os.path.join(root, "README.md"), encoding="utf-8").read()


print(f"{passed} cases passed")

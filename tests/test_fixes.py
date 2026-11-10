"""Plain-assert tests for fixes applied to the lessons of a draft: .venv/bin/python tests/test_fixes.py"""
import copy, os, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, ROOT)
import fixes  # noqa: E402
from ttgen import export, reader, template  # noqa: E402
from ttgen.export import ENTIRE  # noqa: E402
from ttgen.samples import primary  # noqa: E402
import openpyxl  # noqa: E402
n = 0
def t(f): global n; f(); n += 1

def lesson(i, d, p, n_, cls, subject, group, teachers, room="", level="", block=""):
    return dict(id=i, d=d, p=p, n=n_, level=level, block=block, classes=cls, subject=subject, group=group, teachers=teachers, room=room, ext=False, rain="")

def derived():
    sp = primary(); reader.derive(sp); return sp, list(sp["day_structure"][sp["school"]["levels"][0]].keys())
SP, DAYS = derived()
ROW = next(x for x in SP["lessons"] if not x.get("block") and x["code"] == ENTIRE)
CLS, SUBJ, TEACHERS = ROW["classes"][0], ROW["subject"], ROW["teachers"]
KEY = f"C:{CLS}:{SUBJ}"; ROOM = SP["venues"][0]["room"]; TEACHER = next(x["name"] for x in SP["teachers"] if x["name"] not in TEACHERS)
def by_id(L, i): return next(x for x in L if x["id"] == i)

def two_lessons():
    return SP, [lesson(1, 0, 2, 2, [CLS], SUBJ, ENTIRE, TEACHERS, level=ROW["level"]), lesson(2, 1, 4, 2, [CLS], "Other", ENTIRE, TEACHERS, level=ROW["level"])]

def one_block():
    b = next(x for x in SP["lessons"] if x.get("block")); rows = [x for x in SP["lessons"] if x.get("block") == b["block"] and x["code"] != ENTIRE][:3]
    assert len(rows) == 3
    return SP, [lesson(7, 0, 0, 2, x["classes"], x["subject"], x["code"], x["teachers"], level=x["level"], block=b["block"]) for x in rows]

@t
def move_and_swap():
    sp, L = two_lessons()
    out = fixes.apply(L, [dict(kind="move", id=1, d=2, p=0)], sp, DAYS)
    x = by_id(out["lessons"], 1); assert (x["d"], x["p"]) == (2, 0) and L[0]["d"] == 0
    assert out["texts"] == [f"Moved {fixes.what(L[0])} from {DAYS[0]} period 2 to {DAYS[2]} period 0."] and out["touched"] == {1}
    out = fixes.apply(L, [dict(kind="swap", a=1, b=2)], sp, DAYS)
    assert [(x["d"], x["p"]) for x in sorted(out["lessons"], key=lambda x: x["id"])] == [(1, 4), (0, 2)] and out["touched"] == {1, 2}
    assert out["texts"] == [f"Swapped {fixes.what(L[0])} ({DAYS[0]} period 2) with {fixes.what(L[1])} ({DAYS[1]} period 4)."]
    L2 = copy.deepcopy(L); L2[1]["n"] = 1
    out = fixes.apply(L2, [dict(kind="swap", a=1, b=2)], sp, DAYS); assert len(out["problems"]) == 1 and out["touched"] == set()

@t
def a_block_lesson_moves_every_row():
    sp, L = one_block()
    out = fixes.apply(L, [dict(kind="move", id=7, d=3, p=5)], sp, DAYS)
    assert {(x["d"], x["p"]) for x in out["lessons"] if x["id"] == 7} == {(3, 5)} and len([x for x in out["lessons"] if x["id"] == 7]) == 3

@t
def teacher_room_add_delete():
    sp, L = two_lessons(); L[1]["subject"] = SUBJ   # both lessons are of the key
    out = fixes.apply(L, [dict(kind="teacher", key=KEY, teachers=[TEACHER])], sp, DAYS)
    assert all(x["teachers"] == [TEACHER] for x in out["lessons"]) and out["touched"] == {1, 2} and L[0]["teachers"] == TEACHERS
    assert out["texts"] == [f"{SUBJ} for {CLS} is now taught by {TEACHER}, not {', '.join(TEACHERS)}."]
    out = fixes.apply(L, [dict(kind="room", id=1, group=ENTIRE, room=ROOM)], sp, DAYS)
    assert by_id(out["lessons"], 1)["room"] == ROOM and by_id(out["lessons"], 2)["room"] == "" and out["touched"] == {1}
    assert out["texts"] == [f"{fixes.what(L[0])} on {DAYS[0]} period 2 is now in {ROOM}, not no room."]
    out = fixes.apply(L, [dict(kind="add", key=KEY, d=4, p=0, n=1, room=ROOM)], sp, DAYS)
    new = by_id(out["lessons"], 3); assert len(out["lessons"]) == 3 and out["touched"] == {3}
    assert (new["subject"], new["classes"], new["group"], new["teachers"], new["level"], new["block"], new["d"], new["p"], new["n"], new["room"]) == (SUBJ, [CLS], ENTIRE, TEACHERS, ROW["level"], "", 4, 0, 1, ROOM)
    assert out["texts"] == [f"Added {SUBJ} for {CLS} on {DAYS[4]} period 0 (1 periods) in {ROOM}."]
    assert fixes.apply(L, [dict(kind="add", key=KEY, d=4, p=0, n=1, room="")], sp, DAYS)["texts"] == [f"Added {SUBJ} for {CLS} on {DAYS[4]} period 0 (1 periods) with no room."]
    out = fixes.apply(L, [dict(kind="delete", id=2)], sp, DAYS)
    assert [x["id"] for x in out["lessons"]] == [1] and out["texts"] == [f"Deleted {fixes.what(L[1])} on {DAYS[1]} period 4."]
    sp, B = one_block(); g = B[0]["group"]
    out = fixes.apply(B, [dict(kind="delete", id=7, group=g)], sp, DAYS); assert [x["group"] for x in out["lessons"]] == [x["group"] for x in B[1:]]
    out = fixes.apply(B, [dict(kind="add", key=f"G:{g}", d=1, p=1, n=2, room="")], sp, DAYS)
    new = by_id(out["lessons"], 8); assert (new["group"], new["classes"], new["block"]) == (g, B[0]["classes"], B[0]["block"])
    for bad in (dict(kind="teacher", key=KEY, teachers=["Nobody Real"]), dict(kind="room", id=1, group=ENTIRE, room="Nowhere"), dict(kind="add", key="C:9Z:Nothing", d=0, p=0, n=1, room="")):
        assert len(fixes.apply(L, [bad], sp, DAYS)["problems"]) == 1

@t
def a_fix_that_no_longer_applies_is_skipped():
    sp, L = two_lessons()
    out = fixes.apply(L, [dict(kind="move", id=99, d=0, p=0), dict(kind="move", id=1, d=2, p=0)], sp, DAYS)
    assert len(out["problems"]) == 1 and out["problems"][0].startswith("A fix could not be applied: ") and by_id(out["lessons"], 1)["d"] == 2
    out = fixes.apply(L, [dict(kind="move", id=1, d=2, p=0, at="x", text="y")], sp, DAYS); assert not out["problems"]   # stored fixes carry at and text

@t
def add_then_room_then_move_then_undo():
    sp, L = two_lessons(); fx = [dict(kind="add", key=KEY, d=4, p=0, n=1, room=""), dict(kind="room", id=3, group=ENTIRE, room=ROOM), dict(kind="move", id=3, d=4, p=1)]
    for k in (3, 2, 1, 0):
        out = fixes.apply(L, fx[:k], sp, DAYS); assert not out["problems"] and len(out["lessons"]) == len(L) + (1 if k else 0)

@t
def the_hook_edits_the_lessons_before_the_checks():
    with tempfile.TemporaryDirectory() as d:
        sp = primary(); setup = os.path.join(d, "s.xlsx"); template.write_template(sp, setup)
        ds = sp["day_structure"]; lv = sp["school"]["levels"][0]; day = next(iter(ds[lv])); cls = next(c["class"] for c in sp["classes"] if c["level"] == lv)
        x = next(x for x in sp["lessons"] if cls in x["classes"] and not x.get("block"))
        wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Lessons"
        ws.append(["Lesson ID", "Day", "Start period", "End period", "Periods", "Starts", "Ends", "Level", "Block", "Classes", "Subject", "Group", "Teachers", "Room", "After school", "Rain room"])
        p0 = ds[lv][day].index("L"); ws.append([1, day, p0, p0, 1, "", "", lv, "", cls, x["subject"], ENTIRE, ", ".join(x["teachers"]), "", "", ""])
        tt = os.path.join(d, "timetable.xlsx"); wb.save(tt)
        m0 = export.model_from_files(None, tt, spec=sp); assert (m0["lessons"][0]["d"], m0["lessons"][0]["p"]) == (0, p0)
        out = {}; m = export.model_from_files(None, tt, spec=sp, edit=fixes.editor([dict(kind="move", id=1, d=2, p=p0)], out))
        assert (m["lessons"][0]["d"], m["lessons"][0]["p"]) == (2, p0) and out["touched"] == {1} and len(out["texts"]) == 1 and out["problems"] == []
        assert m["checks"]["lessons"] == 1 and (m["checks"]["after_school"] == m0["checks"]["after_school"])

print(f"{n} checks passed")

"""Plain-assert tests for fixes applied to the lessons of a draft: .venv/bin/python tests/test_fixes.py"""
import collections, copy, os, random, subprocess, sys, tempfile, time
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, ROOT)
import fixes  # noqa: E402
from ttgen import export, reader, template, verify  # noqa: E402
from ttgen import spec as spec_mod  # noqa: E402
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
def apply_keeps_the_rows_as_they_were():
    sp, L = two_lessons(); other = next(x["name"] for x in SP["teachers"] if x["name"] not in TEACHERS)
    out = fixes.apply(L, [dict(kind="delete", id=2), dict(kind="teacher", key=KEY, teachers=[other]), dict(kind="move", id=1, d=2, p=0)], sp, DAYS)
    assert [(x["id"], x["d"], x["p"], x["teachers"]) for x in out["was"]] == [(2, 1, 4, TEACHERS), (1, 0, 2, TEACHERS), (1, 0, 2, [other])], out["was"]
    assert out["was"][0] is not L[1] and L[0]["teachers"] == TEACHERS and fixes.apply(L, [], sp, DAYS)["was"] == []
    got = {}; fixes.editor([dict(kind="move", id=1, d=2, p=0)], got)(copy.deepcopy(L), sp, DAYS); assert [x["id"] for x in got["was"]] == [1] and got["touched"] == {1}

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
    bare = copy.deepcopy(L)
    for x in bare: x["teachers"] = []
    out = fixes.apply(bare, [dict(kind="teacher", key=KEY, teachers=[TEACHER])], sp, DAYS)   # a lesson that had nobody
    assert out["texts"] == [f"{SUBJ} for {CLS} is now taught by {TEACHER}; it had no teacher."], out["texts"]
    out = fixes.apply(L, [dict(kind="room", id=1, group=ENTIRE, room=ROOM)], sp, DAYS)
    assert by_id(out["lessons"], 1)["room"] == ROOM and by_id(out["lessons"], 2)["room"] == "" and out["touched"] == {1}
    assert out["texts"] == [f"{fixes.what(L[0])} on {DAYS[0]} period 2 is now in {ROOM}, not no room."]
    out = fixes.apply(L, [dict(kind="add", key=KEY, d=4, p=0, n=1, room=ROOM)], sp, DAYS)
    new = by_id(out["lessons"], 3); assert len(out["lessons"]) == 3 and out["touched"] == {3}
    assert (new["subject"], new["classes"], new["group"], new["teachers"], new["level"], new["block"], new["d"], new["p"], new["n"], new["room"]) == (SUBJ, [CLS], ENTIRE, TEACHERS, ROW["level"], "", 4, 0, 1, ROOM)
    assert out["texts"] == [f"Added {SUBJ} for {CLS} on {DAYS[4]} period 0 (1 period) in {ROOM}."]
    assert fixes.apply(L, [dict(kind="add", key=KEY, d=4, p=0, n=1, room="")], sp, DAYS)["texts"] == [f"Added {SUBJ} for {CLS} on {DAYS[4]} period 0 (1 period) with no room."]
    out = fixes.apply(L, [dict(kind="delete", id=2)], sp, DAYS)
    assert [x["id"] for x in out["lessons"]] == [1] and out["texts"] == [f"Deleted {fixes.what(L[1])} on {DAYS[1]} period 4."]
    sp, B = one_block(); g = B[0]["group"]
    out = fixes.apply(B, [dict(kind="delete", id=7, group=g)], sp, DAYS); assert [x["group"] for x in out["lessons"]] == [x["group"] for x in B[1:]]
    out = fixes.apply(B, [dict(kind="add", key=f"G:{g}", d=1, p=1, n=2, room="")], sp, DAYS)
    new = by_id(out["lessons"], 8); assert (new["group"], new["classes"], new["block"]) == (g, B[0]["classes"], B[0]["block"])
    assert out["texts"] == [f"Added group {g} on {DAYS[1]} period 1 (2 periods) with no room."]
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

@t
def an_added_id_is_not_reused_after_a_delete():
    sp, L = two_lessons(); add = dict(kind="add", key=KEY, d=4, p=0, n=1, room="")
    out = fixes.apply(L, [add, dict(kind="delete", id=3), add], sp, DAYS)
    assert [x["id"] for x in out["lessons"]] == [1, 2, 4] and out["touched"] == {4}   # a deleted lesson is not touched
    assert fixes.apply_one(copy.deepcopy(L), add, sp, DAYS).startswith("Added")      # four arguments still work

@t
def a_malformed_fix_is_skipped_and_listed():
    sp, L = two_lessons(); good = dict(kind="move", id=1, d=2, p=0)
    for bad in (dict(kind="teacher", key="C:9A", teachers=[]), dict(kind="add", key="C:9A", d=0, p=0, n=1, room=""), "move", dict(kind="move", id=1), dict(kind="teacher", key=5, teachers=[]), dict(kind="add", key="G", d=0, p=0, n=1, room="")):
        out = fixes.apply(L, [bad, good], sp, DAYS)
        assert len(out["problems"]) == 1 and len(out["texts"]) == 1 and by_id(out["lessons"], 1)["d"] == 2, bad

@t
def a_slot_outside_the_day_is_refused():
    sp, L = two_lessons(); NP = int(sp["school"]["periods_per_day"])
    for bad in (dict(kind="move", id=1, d=0, p=NP - 1), dict(kind="move", id=1, d=len(DAYS), p=0), dict(kind="move", id=1, d=-1, p=0),
                dict(kind="add", key=KEY, d=0, p=NP, n=1, room=""), dict(kind="add", key=KEY, d=0, p=NP - 1, n=2, room="")):
        out = fixes.apply(L, [bad], sp, DAYS); assert out["problems"] == ["A fix could not be applied: That is outside the day."] and out["lessons"] == L, bad
    assert not fixes.apply(L, [dict(kind="move", id=1, d=0, p=NP - 2)], sp, DAYS)["problems"]

# ----------------------------------------------------------------------------------------------- judging a fix
A, B, C3, D = "1A", "1B", "1C", "1D"; LV = "P1"; NP = int(SP["school"]["periods_per_day"]); RECESS = SP["day_structure"][LV][DAYS[0]].index("R")
T = [x["name"] for x in SP["teachers"]]
def model_with(L, **over):
    """a model of the primary setup holding only the lessons L; over replaces setup fields (rules default to none)"""
    sp = dict(SP, **dict(dict(rules=[]), **over)); m = export._model(sp, DAYS, L); m["checked_setup"] = sp; return m, sp
def rows_of(m, i): return [x for x in m["lessons"] if x["id"] == i]
def slot_of(m, i): x = rows_of(m, i)[0]; return x["d"], x["p"], x["n"]
def at(S, d, p): return next(s for s in S if (s["d"], s["p"]) == (d, p))
def bare(s): return {k: v for k, v in s.items() if k not in ("push", "beside", "clashes")}   # a slot's keys from before a push, a place beside and the list of collisions were offered

@t
def a_busy_teacher_class_room_or_student_is_a_clash():
    L = [lesson(1, 0, 2, 2, [A], "Maths", ENTIRE, [T[0]], room=ROOM, level=LV), lesson(2, 1, 2, 2, [B], "Science", ENTIRE, [T[0]], level=LV),
         lesson(3, 2, 5, 2, [A], "Art", "G1", [T[1]], level=LV), lesson(4, 3, 5, 2, [A], "Music", "G2", [T[2]], level=LV),
         lesson(5, 4, 2, 2, [B], "English", ENTIRE, [T[3]], room=ROOM, level=LV)]
    m, sp = model_with(L, students=[dict(id="S1", name="Ann Lee", level=LV, groups=["G1", "G2"], **{"class": A})])
    b = fixes.Busy(m)
    assert b.clash(rows_of(m, 1), 1, 2, 2, ignore={1}) == f"{T[0]} is teaching Science for {B} then." and b.clash(rows_of(m, 1), 3, 2, 2, ignore={1}) is None
    assert b.clash(rows_of(m, 1), 2, 5, 2, ignore={1}) == f"{A} has group G1 then." and b.clash(rows_of(m, 3), 0, 2, 2, ignore={3}) == f"{A} has Maths for {A} then."
    assert b.clash(rows_of(m, 3), *slot_of(m, 4), ignore={3}) == "1 student of G1 has group G2 then."
    assert b.clash(rows_of(m, 5), 0, 2, 2, ignore={5}) == f"{ROOM} is in use then." and b.clash(rows_of(m, 5), 0, 2, 2, ignore={1, 5}) is None
    assert b.clash([dict(rows_of(m, 5)[0], room="TBC")], 0, 2, 2, ignore={5}) is None and b.clash([dict(rows_of(m, 5)[0], room="")], 0, 2, 2, ignore={5}) is None
    assert b.lesson_time(rows_of(m, 1), 0, RECESS, 1) == f"That is not lesson time for {A}." and b.lesson_time(rows_of(m, 1), 0, NP - 1, 2) == f"That is not lesson time for {A}."
    assert b.lesson_time(rows_of(m, 1), 0, 2, 2) is None and b.lesson_time(rows_of(m, 1), 0, 0, 1) is not None   # period 0 is the assembly
    assert {x["id"] for x in fixes.neighbours(m, {3})} == {1, 3, 4}   # class 1A's lessons; 2 and 5 share nothing with it

@t
def judge_states():
    rules = [dict(scope="Class", target=A, rule="Not in periods", week="Both", day="All", **{"from": 7, "to": 8}, strength="Prefer"),
             dict(scope="Class", target=A, rule="Not in periods", week="Both", day="All", **{"from": 9, "to": 10}, strength="Must")]
    teachers = [dict(x, allowance=2) if x["name"] == T[5] else x for x in SP["teachers"]]
    L = [lesson(1, 0, 2, 2, [A], SUBJ, ENTIRE, [T[0]], level=LV), lesson(2, 1, 2, 2, [B], "Science", ENTIRE, [T[0]], level=LV),
         lesson(6, 1, 9, 1, [A], "Art", ENTIRE, [T[5]], level=LV)]
    m, sp = model_with(L, rules=rules, teachers=teachers)
    j = lambda **f: fixes.judge(m, sp, DAYS, f)
    assert j(kind="move", id=1, d=2, p=2) == dict(state="ok", why="", must=[], prefer=[])
    r = j(kind="move", id=1, d=1, p=2); assert r["state"] == "no" and r["why"] == f"{T[0]} is teaching Science for {B} then.", r
    r = j(kind="move", id=1, d=2, p=7); assert r["state"] == "prefer" and r["why"] == r["prefer"][0] and "Class · 1A · Not in periods" in r["why"] and r["must"] == [], r
    r = j(kind="move", id=1, d=2, p=9); assert r["state"] == "no" and r["why"] == r["must"][0] and r["why"].startswith("Rule Class · 1A · Not in periods"), r
    assert j(kind="move", id=6, d=2, p=10)["state"] == "ok"   # it broke the Must row where it was and still does: the count does not rise
    r = j(kind="move", id=1, d=0, p=RECESS); assert r["state"] == "na" and r["why"] == f"That is not lesson time for {A}.", r
    assert j(kind="move", id=1, d=0, p=NP - 1) == dict(state="na", why="That is outside the day.", must=[], prefer=[])
    r = j(kind="teacher", key=KEY.replace(CLS, A), teachers=[T[5]]); assert r["state"] == "prefer" and r["why"] == f"{T[5]} would have 3 periods, 1 over the allowance.", r
    assert j(kind="teacher", key=KEY.replace(CLS, A), teachers=[T[0]])["state"] == "ok"   # the same teacher: no new clash with Science, which is on another day
    r = j(kind="swap", a=1, b=6); assert r["state"] == "na" and "not the same length" in r["why"], r

@t
def a_rule_broken_by_another_lesson_is_new():
    must = dict(scope="Class", target=A, rule="Not in periods", week="Both", day="All", **{"from": 9, "to": 10}, strength="Must")
    L = [lesson(1, 0, 9, 1, [A], SUBJ, ENTIRE, [T[0]], level=LV), lesson(2, 1, 5, 1, [A], "Art", ENTIRE, [T[1]], level=LV)]
    m, sp = model_with(L, rules=[must])
    r = fixes.judge(m, sp, DAYS, dict(kind="swap", a=1, b=2))   # the break moves from lesson 1 to lesson 2: the same count, a new lesson breaking it
    assert r["state"] == "no" and r["must"] == [r["why"]] and r["why"] == f"Rule Class · {A} · Not in periods: Art for {A} is in periods 9-10 on {DAYS[0]}.", r
    assert fixes.judge(m, sp, DAYS, dict(kind="move", id=1, d=2, p=10))["state"] == "ok"   # lesson 1 still breaks it, elsewhere: not new
    cap = dict(scope="Teacher", target=T[0], rule="Max periods a day", number=2, strength="Must")
    L = [lesson(40 + k, 0, 1 + k, 1, [A], SUBJ, ENTIRE, [T[0]], level=LV) for k in range(3)] + [lesson(43 + k, 1, 5 + k, 1, [B], SUBJ, ENTIRE, [T[0]], level=LV) for k in range(2)]
    m, sp = model_with(L, rules=[cap])
    r = fixes.judge(m, sp, DAYS, dict(kind="move", id=40, d=1, p=7))   # Monday is no longer over, Tuesday now is
    assert r["state"] == "no" and r["why"].endswith(f"{T[0]} has 3 periods on {DAYS[1]}, more than 2."), r
    assert fixes.judge(m, sp, DAYS, dict(kind="move", id=40, d=2, p=7))["state"] == "ok"

@t
def keep_free_together_is_about_the_day_not_its_first_lesson():
    dept = next(x["dept"] for x in SP["teachers"] if x["name"] == T[0]); win = dict(scope="Department", target=dept, rule="Keep free together", week="Both", day="All", strength="Must", **{"from": 2, "to": 3})
    L = [lesson(1, 0, 2, 1, [A], "Art", ENTIRE, [T[0]], level=LV), lesson(2, 0, 3, 1, [B], "Art", ENTIRE, [T[0]], level=LV), lesson(3, 1, 5, 1, [A], "Art", ENTIRE, [T[0]], level=LV)]
    m, sp = model_with(L, rules=[win]); ws = verify.rules(m, sp)[0]
    assert [w["key"] for w in ws] == [f"rule:0:{T[0]}|0"] and ws[0]["where"]["day"] == DAYS[0] and ws[0]["where"]["period"] == 2 and "id" not in ws[0]["where"] and "row" not in ws[0]["where"], ws
    r = fixes.judge(m, sp, DAYS, dict(kind="move", id=1, d=2, p=5)); assert r["state"] != "no" and r["must"] == [], r   # the day stays broken through lesson 2: not a new violation
    r = fixes.judge(m, sp, DAYS, dict(kind="move", id=3, d=1, p=2)); assert r["state"] == "no" and r["why"].startswith("Rule Department"), r   # a clean day broken anew

@t
def keep_free_together_bears_on_a_second_department_teacher():
    other = next(d for d in SP["school"]["departments"] if d != next(x["dept"] for x in SP["teachers"] if x["name"] == T[0]))
    win = dict(scope="Department", target=other, rule="Keep free together", week="Both", day="All", strength="Must", **{"from": 2, "to": 3})
    L = [lesson(1, 0, 5, 1, [A], "Art", ENTIRE, [T[0]], level=LV)]
    teachers = [dict(x, dept2=other) if x["name"] == T[0] else x for x in SP["teachers"]]
    m, sp = model_with(L, rules=[win], teachers=teachers); depts = verify.teacher_depts(m, sp)
    assert fixes._bears(m, sp, win, m["lessons"][0], depts)
    m0, sp0 = model_with(L, rules=[win]); assert not fixes._bears(m0, sp0, win, m0["lessons"][0], verify.teacher_depts(m0, sp0))
    r = fixes.judge(m, sp, DAYS, dict(kind="move", id=1, d=1, p=2)); assert r["state"] == "no" and r["why"].startswith("Rule Department"), r   # into the window
    assert fixes.judge(m0, sp0, DAYS, dict(kind="move", id=1, d=1, p=2))["state"] != "no"

@t
def the_departments_are_worked_out_once_per_context():
    L = [lesson(1, 0, 5, 1, [A], "Art", ENTIRE, [T[0]], level=LV)]; m, sp = model_with(L); ctx = fixes._ctx(m); real, calls = verify.teacher_depts, []
    verify.teacher_depts = lambda *a: calls.append(1) or real(*a)
    try:
        for p in (2, 3): fixes.judge(m, sp, DAYS, dict(kind="move", id=1, d=1, p=p), ctx)
    finally: verify.teacher_depts = real
    assert len(calls) == 1, calls

@t
def a_lesson_length_in_any_spelling():
    rows = [dict(x, length="2.0") if x is ROW else dict(x, length="two") if x["classes"] == [CLS] and x["code"] == ENTIRE else x for x in SP["lessons"]]
    m, sp = model_with([lesson(1, 0, 2, 1, [CLS], SUBJ, ENTIRE, TEACHERS, level=LV)], lessons=rows)
    sh = {x["key"]: x for x in fixes.short(m, sp)}; assert sh[KEY]["n"] == 2, sh[KEY]
    assert all(x["n"] == 1 for k, x in sh.items() if k.startswith(f"C:{CLS}:") and k != KEY)

@t
def slots_for_a_lesson_and_a_block():
    L = [lesson(1, 0, 2, 2, [A], SUBJ, ENTIRE, [T[0]], level=LV), lesson(7, 2, 2, 2, [A], "Science", ENTIRE, [T[1]], level=LV),
         lesson(8, 3, 5, 3, [A], "Art", ENTIRE, [T[2]], level=LV), lesson(9, 4, 2, 2, [A, B], "Assembly talk", ENTIRE, [T[3]], level=LV)]
    m, sp = model_with(L); S = fixes.slots(m, sp, DAYS, 1)
    assert len(S) == len(DAYS) * NP - 1 and not [s for s in S if (s["d"], s["p"]) == (0, 2)]
    assert bare(at(S, 2, 2)) == dict(d=2, p=2, state="ok", why="", swap=7, also=[]) and bare(at(S, 1, 2)) == dict(d=1, p=2, state="ok", why="", swap=None, also=[])
    assert at(S, 2, 2)["push"]["out"] == [dict(id=7, what=f"Science for {A}", classes=[A], groups=1)] and at(S, 1, 2)["push"] is None
    assert at(S, 3, 5)["state"] == "na" and at(S, 3, 5)["why"] == "Another lesson is there." and at(S, 3, 6)["why"] == "Another lesson is there."
    assert at(S, 4, 2)["swap"] == 9 and at(S, 4, 2)["also"] == [f"This also moves Assembly talk for {A}, {B} to {DAYS[0]} period 2."] and at(S, 4, 2)["state"] == "ok"
    assert at(S, 0, RECESS)["state"] == "na" and at(S, 0, NP - 1)["why"] == "That is outside the day."
    sp0, Bk = one_block(); cls = Bk[0]["classes"]; assert len(cls) == 3 and all(x["classes"] == cls for x in Bk)
    busy_teacher = Bk[1]["teachers"][0]
    L = Bk + [lesson(30, 1, 5, 3, [cls[1]], SUBJ, ENTIRE, [T[-1]], level=LV), lesson(31, 2, 5, 2, [D], SUBJ, ENTIRE, [busy_teacher], level=LV),
              lesson(32, 3, 5, 2, [cls[2]], SUBJ, ENTIRE, [T[-1]], level=LV)]
    m, sp = model_with(L); S = fixes.slots(m, sp, DAYS, 7)
    assert at(S, 4, 5)["state"] == "ok" and at(S, 4, 5)["swap"] is None
    assert at(S, 1, 5)["state"] == "na" and bare(at(S, 2, 5)) == dict(d=2, p=5, state="no", why=f"{busy_teacher} is teaching {SUBJ} for {D} then.", swap=None, also=[])
    assert at(S, 3, 5)["swap"] == 32 and at(S, 3, 5)["state"] == "na"   # a single class's lesson never swaps into a block's slot
    r = fixes.judge(m, sp, DAYS, dict(kind="move", id=7, d=1, p=6)); assert r["state"] == "no" and r["why"].startswith(f"{cls[1]} has "), r
    ok = [s for s in S if s["state"] == "ok"]; assert ok and all(not [x for x in L if x["id"] != 7 and x["d"] == s["d"] and set(x["classes"]) & set(cls) and x["p"] < s["p"] + 2 and s["p"] < x["p"] + x["n"]] for s in ok)

@t
def teachers_offered_are_those_who_teach_the_subject_then_its_department():
    # Mathematics G3 and G2 are one card; Aye teaches the G2 one; Bee and Cee (by a second department) are in MA; Dee is not
    row = lambda sub, cls, who, tg: dict(ROW, subject=sub, tag=tg, classes=cls, teachers=who, code=ENTIRE, block=None, periods=2, level=LV)
    subs = [dict(subject="Mathematics G3", code="MA", tag="G3", dept="MA", periods={}), dict(subject="Mathematics G2", code="MA", tag="G2", dept="MA", periods={})]
    tch = [dict(name=n, short=n, dept=d, **x) for n, d, x in [("Dee", "SC", {}), ("Cee", "SC", dict(dept2="MA")), ("Bee", "MA", {}), ("Aye", "SC", {}), ("Now", "MA", {})]]
    rows = [row("Mathematics G3", [CLS], ["Now"], "G3"), row("Mathematics G2", [B], ["Aye"], "G2")]
    school = dict(SP["school"], tags=[["G3", "P"], ["G2", "A"], ["-", ""]])
    L = [lesson(1, 0, 2, 2, [CLS], "Mathematics G3", ENTIRE, ["Now"], level=LV)]
    m, sp = model_with(L, school=school, subjects=subs, teachers=tch, lessons=rows)
    key = f"C:{CLS}:Mathematics G3"
    assert [o["teachers"] for o in fixes.teacher_options(m, sp, DAYS, key)] == [["Aye"], ["Cee"], ["Bee"]], fixes.teacher_options(m, sp, DAYS, key)

@t
def a_card_is_step_3s_card():
    # (a) "Drama" with tag a is not "Dram"; (b) spaces round a name and its G-level still join the card; (c) odd setups do not raise
    mk = lambda subs, tch, rows, tags, L: model_with(L, school=dict(SP["school"], tags=tags), subjects=subs, teachers=tch, lessons=rows)
    sub = lambda n, tg: dict(subject=n, code="DR", tag=tg, dept="AR", periods={})
    rw = lambda n, cls, who: dict(ROW, subject=n, classes=cls, teachers=who, code=ENTIRE, block=None, periods=2, level=LV)
    tch = [dict(name="Now", short="N", dept="XX"), dict(name="Ann", short="A", dept="XX"), dict(name="Bo", short="B", dept="YY")]
    offers = lambda m, sp, name: [o["teachers"] for o in fixes.teacher_options(m, sp, DAYS, f"C:{CLS}:{name}")]
    L = lambda n: [lesson(1, 0, 2, 2, [CLS], n, ENTIRE, ["Now"], level=LV)]
    m, sp = mk([sub("Drama", "a"), sub("Dram", "-")], tch, [rw("Drama", [CLS], ["Now"]), rw("Dram", [B], ["Ann"])], [["a", "A"], ["-", ""]], L("Drama"))
    assert offers(m, sp, "Drama") == [], offers(m, sp, "Drama")   # Ann teaches "Dram", which is not Drama's card
    m, sp = mk([sub("  Art G3 ", "G3"), sub("Art G2", "G2")], tch, [rw("Art G3", [CLS], ["Now"]), rw("Art G2", [B], ["Ann"])], [["G3", "P"], ["G2", "A"]], L("Art G3"))
    assert offers(m, sp, "Art G3") == [["Ann"]], offers(m, sp, "Art G3")
    m, sp = mk([sub("Art G3", "G3")], tch, [rw("Art G3", [CLS], ["Now"])], [["G3", "P"]], L("Art G3"))
    for odd in (dict(subjects=[None, sub("Art G3", "G3")], teachers=[None] + tch), dict(school=dict(sp["school"], tags="G3")), dict(school=dict(sp["school"], tags=None)),
                dict(school=dict(sp["school"], tags=[None, "G3", [], ["G3", "P"]]))):
        assert isinstance(fixes.teacher_options(m, dict(sp, **odd), DAYS, f"C:{CLS}:Art G3"), list)

@t
def nobody_to_offer_is_an_empty_list():
    # a subject with no department, taught only by its own teacher; and a lesson whose subject is not on step 3's list
    subs = [dict(subject="Assembly talk", code="AT", tag="-", dept="", periods={})]
    rows = [dict(ROW, subject="Assembly talk", tag="-", classes=[CLS], teachers=["Solo"], code=ENTIRE, block=None, periods=2, level=LV)]
    tch = [dict(name="Solo", short="Solo", dept="MA"), dict(name="Other", short="Other", dept="MA")]
    L = [lesson(1, 0, 2, 2, [CLS], "Assembly talk", ENTIRE, ["Solo"], level=LV), lesson(2, 1, 2, 2, [B], "Unlisted", ENTIRE, ["Solo"], level=LV)]
    m, sp = model_with(L, subjects=subs, teachers=tch, lessons=rows)
    assert fixes.teacher_options(m, sp, DAYS, f"C:{CLS}:Assembly talk") == []
    assert fixes.teacher_options(m, sp, DAYS, f"C:{B}:Unlisted") == []

@t
def teacher_room_add_delete_options():
    P = verify.planned_rows(SP)[("C", CLS, SUBJ)]["periods"]; dept = next(s["dept"] for s in SP["subjects"] if s["subject"] == SUBJ)
    can = [x["name"] for x in SP["teachers"] if dept in spec_mod.teacher_depts(x) and x["name"] not in TEACHERS]
    free, busy = can[0], can[1]; home = next(c["home_room"] for c in SP["classes"] if c["class"] == CLS); other = next(v["room"] for v in SP["venues"] if v.get("kind") == "classroom" and v["room"] != home)
    L = [lesson(1, 0, 2, 2, [CLS], SUBJ, ENTIRE, TEACHERS, room=other, level=LV)] + [lesson(10 + k, 1 + k // 6, 5 + k % 6, 1, [CLS], SUBJ, ENTIRE, TEACHERS, level=LV) for k in range(P - 3)] \
        + [lesson(2, 0, 2, 2, [B], "Science", ENTIRE, [busy], room=home, level=LV)]
    m, sp = model_with(L); have = P - 1
    opts = {tuple(o["teachers"]): o for o in fixes.teacher_options(m, sp, DAYS, KEY)}
    assert opts[(free,)]["state"] == "ok" and opts[(busy,)]["state"] == "no" and opts[(busy,)]["why"] == f"{busy} is teaching Science for {B} then."
    assert not [k for k in opts if set(k) <= set(TEACHERS)] and all(len(k) == 1 for k in opts)   # step 5's teachers are the current ones: left out
    R = {o["room"]: o for o in fixes.room_options(m, sp, DAYS, 1, ENTIRE)}
    assert set(R) == {v["room"] for v in SP["venues"] if v.get("kind") == "classroom"} - {other} and R[home]["state"] == "no" and R[home]["why"] == f"{home} is in use then."
    assert dict(key=KEY, name=f"{SUBJ} for {CLS}", have=have, want=P, n=1) in fixes.short(m, sp)
    A1 = fixes.add_slots(m, sp, DAYS, KEY, 1); assert len(A1) == len(DAYS) * NP and at(A1, 4, 2)["state"] == "ok" and at(A1, 0, 2)["state"] == "no"
    assert at(A1, 0, RECESS)["state"] == "na"
    A2 = fixes.add_slots(m, sp, DAYS, KEY, 2); assert at(A2, 4, 2) == dict(d=4, p=2, state="no", why=f"That would leave {SUBJ} for {CLS} with {P + 1} periods; step 3 plans {P}.")
    assert fixes.can_delete(m, sp, DAYS, 1) == dict(state="no", why=f"That would leave {SUBJ} for {CLS} with {have - 2} periods; step 3 plans {P}.", plan=True)
    m, sp = model_with(L + [lesson(3, 4, 7, 1, [CLS], SUBJ, ENTIRE, TEACHERS, level=LV), lesson(4, 4, 8, 1, [CLS], "Other", ENTIRE, TEACHERS, level=LV)])
    assert not [x for x in fixes.short(m, sp) if x["key"] == KEY] and fixes.can_delete(m, sp, DAYS, 4) == dict(state="ok", why="", plan=False)
    assert fixes.can_delete(m, sp, DAYS, 3)["state"] == "no" and at(fixes.add_slots(m, sp, DAYS, KEY, 1), 4, 2)["state"] == "no"

@t
def an_add_takes_its_id_from_its_place_among_the_adds():   # a skipped add still counts, so later fixes act on the lesson they were made for
    sp, L = two_lessons(); k1, k2 = dict(kind="add", key=KEY, d=4, p=0, n=1, room=""), dict(kind="add", key=KEY, d=3, p=0, n=1, room="")
    for k0 in (dict(kind="add", key=KEY, d=2, p=6, n=1, room=""), dict(kind="add", key="C:9Z:Nothing", d=2, p=6, n=1, room="")):
        out = fixes.apply(L, [k0, k1, k2, dict(kind="move", id=4, d=2, p=0)], sp, DAYS)
        assert sorted((x["id"], x["d"], x["p"]) for x in out["lessons"] if x["id"] in (4, 5)) == [(4, 2, 0), (5, 3, 0)], out["lessons"]
    assert len(out["problems"]) == 1 and out["touched"] == {4, 5}, out

@t
def an_add_takes_the_first_free_home_room_then_another_room_of_its_kind():
    home = lambda c: next(x["home_room"] for x in SP["classes"] if x["class"] == c)
    other = next(c["class"] for c in SP["classes"] if c["class"] != CLS and c["level"] == LV); t = next(x for x in T if x not in TEACHERS)
    m, sp = model_with([lesson(1, 4, 2, 1, [other], "Science", ENTIRE, [t], room=home(CLS), level=LV)])
    assert at(fixes.add_slots(m, sp, DAYS, KEY, 1), 4, 2)["state"] == "ok"
    r = fixes.add_room(m, sp, KEY, 4, 2, 1); classrooms = [v["room"] for v in SP["venues"] if (v.get("kind") or "classroom") == "classroom"]
    assert r != home(CLS) and r in classrooms, r
    assert fixes.add_room(m, sp, KEY, 3, 2, 1) == home(CLS) and fixes.add_room(m, sp, KEY, 4, 1, 2) != home(CLS)   # the two periods must both be free
    g = "1ML1"; e = verify.planned_rows(SP)[("G", g)]; c1, c2 = e["classes"][:2]
    m, sp = model_with([lesson(1, 4, 2, 1, [other], "Science", ENTIRE, [t], room=home(c1), level=LV)])
    assert fixes.add_room(m, sp, f"G:{g}", 4, 2, 1) == home(c2) and fixes.add_room(m, sp, f"G:{g}", 3, 2, 1) == home(c1)

@t
def a_fix_that_changes_nothing_is_na():
    L = [lesson(1, 0, 2, 2, [A], SUBJ, ENTIRE, [T[0]], level=LV)]; m, sp = model_with(L)
    none = dict(state="na", why="That changes nothing.", must=[], prefer=[])
    assert fixes.judge(m, sp, DAYS, dict(kind="move", id=1, d=0, p=2)) == none and fixes.judge(m, sp, DAYS, dict(kind="swap", a=1, b=1)) == none

@t
def the_after_school_flag_follows_the_slot():
    P5 = "P5"; ds = SP["day_structure"][P5][DAYS[0]]; aft = ds.index("A"); c5 = next(c["class"] for c in SP["classes"] if c["level"] == P5); key5 = next(f"C:{c5}:{x['subject']}" for x in SP["lessons"] if x["classes"] == [c5] and x["code"] == ENTIRE)
    avoid = dict(scope="School", target="Whole school", rule="Avoid after-school slots", week="Both", day="All", strength="Prefer")
    L = [dict(lesson(1, 0, aft, 1, [c5], "Art", ENTIRE, [T[0]], level=P5), ext=True), lesson(2, 1, 2, 1, [c5], "Music", ENTIRE, [T[1]], level=P5),
         lesson(3, 2, 2, 1, [c5], "Science", ENTIRE, [T[2]])]   # lesson 3 has no level: its class's level is used
    m, sp = model_with(L, rules=[avoid])
    out = fixes.apply(L, [dict(kind="move", id=1, d=0, p=2)], sp, DAYS); assert by_id(out["lessons"], 1)["ext"] is False and by_id(out["lessons"], 2)["ext"] is False
    assert [w for w in verify.rules(m, sp)[0] if w["where"]["id"] == 1] and not [w for w in verify.rules(dict(m, lessons=out["lessons"]), sp)[0] if w["where"]["id"] == 1]
    out = fixes.apply(L, [dict(kind="move", id=2, d=1, p=aft)], sp, DAYS); assert by_id(out["lessons"], 2)["ext"] is True
    r = fixes.judge(m, sp, DAYS, dict(kind="move", id=2, d=1, p=aft)); assert r["state"] == "prefer" and "Avoid after-school slots" in r["why"], r
    r = fixes.judge(m, sp, DAYS, dict(kind="move", id=1, d=3, p=2)); assert r["state"] == "ok", r
    out = fixes.apply(L, [dict(kind="move", id=3, d=2, p=aft)], sp, DAYS); assert by_id(out["lessons"], 3)["ext"] is True
    out = fixes.apply(L, [dict(kind="swap", a=1, b=2)], sp, DAYS); assert (by_id(out["lessons"], 1)["ext"], by_id(out["lessons"], 2)["ext"]) == (False, True)
    out = fixes.apply(L, [dict(kind="add", key=key5, d=4, p=aft, n=1, room=""), dict(kind="add", key=key5, d=4, p=2, n=1, room="")], sp, DAYS)
    assert [x["ext"] for x in out["lessons"][3:]] == [True, False]
    out = fixes.apply(L, [dict(kind="room", id=1, group=ENTIRE, room=ROOM)], sp, DAYS); assert by_id(out["lessons"], 1)["ext"] is True   # not moved: the file's flag stays
    assert L[0]["ext"] is True and L[1]["ext"] is False

# ----------------------------------------------------------------------------------------------- not placed, and a push
B0 = one_block()[1][0]

@t
def test_lift_takes_the_whole_lesson_to_the_pool_and_place_brings_it_back():
    sp, L = one_block(); pool = []
    assert fixes.apply_one(L, dict(kind="lift", id=7), sp, DAYS, pool=pool) == f"Lifted out {fixes.what(B0)} from {DAYS[0]} period 0."
    assert L == [] and [x["id"] for x in pool] == [7, 7, 7] and all((x["d"], x["p"]) == (0, 0) for x in pool)
    assert fixes.apply_one(L, dict(kind="place", id=7, d=1, p=2), sp, DAYS, pool=pool) == f"Placed {fixes.what(B0)} on {DAYS[1]} period 2."
    assert pool == [] and len(L) == 3 and all((x["d"], x["p"]) == (1, 2) for x in L)

@t
def test_a_push_lifts_what_it_names_and_says_so():
    sp, L = two_lessons(); pool = []; two = fixes.what(L[1])
    text = fixes.apply_one(L, dict(kind="move", id=1, d=1, p=4, out=[2]), sp, DAYS, pool=pool)
    assert text == f"Moved {fixes.what(L[0])} from {DAYS[0]} period 2 to {DAYS[1]} period 4. Pushed out: {two}.", text
    assert [x["id"] for x in L] == [1] and (L[0]["d"], L[0]["p"]) == (1, 4) and [(x["id"], x["d"], x["p"]) for x in pool] == [(2, 1, 4)]
    out = fixes.apply(two_lessons()[1], [dict(kind="move", id=1, d=1, p=4, out=[2])], sp, DAYS)
    assert out["touched"] == {1, 2} and [x["id"] for x in out["was"]] == [2, 1] and [x["id"] for x in out["pool"]] == [2]

@t
def test_an_out_that_is_gone_is_passed_over():
    sp, L = two_lessons(); pool = []
    text = fixes.apply_one(L, dict(kind="move", id=1, d=1, p=4, out=[2, 99]), sp, DAYS, pool=pool)
    assert text.endswith(f" Pushed out: {fixes.what(two_lessons()[1][1])}.") and [x["id"] for x in pool] == [2], text
    sp, L = two_lessons(); pool = []
    assert fixes.apply_one(L, dict(kind="move", id=1, d=1, p=0, out=[99]), sp, DAYS, pool=pool) == f"Moved {fixes.what(L[0])} from {DAYS[0]} period 2 to {DAYS[1]} period 0."

@t
def test_an_out_naming_the_lesson_itself_is_refused():
    sp, L = two_lessons(); pool = []; start = copy.deepcopy(L)
    for f in (dict(kind="move", id=1, d=1, p=4, out=[2, 1]), dict(kind="move", id=1, d=1, p=4, out=2)):
        try: fixes.apply_one(L, f, sp, DAYS, pool=pool); assert False, f
        except ValueError as e: assert str(e) == "That fix is not complete.", e
    assert L == start and pool == []
    fixes.apply_one(L, dict(kind="lift", id=1), sp, DAYS, pool=pool)
    try: fixes.apply_one(L, dict(kind="place", id=1, d=1, p=4, out=[1]), sp, DAYS, pool=pool); assert False
    except ValueError as e: assert str(e) == "That fix is not complete.", e
    assert [x["id"] for x in L] == [2] and [x["id"] for x in pool] == [1]

@t
def test_undoing_a_push_brings_everything_back():
    sp, L = two_lessons(); start = copy.deepcopy(L)
    out = fixes.apply(L, [dict(kind="move", id=1, d=1, p=4, out=[2])], sp, DAYS); assert [x["id"] for x in out["pool"]] == [2] and L == start
    out = fixes.apply(L, [], sp, DAYS); assert out["lessons"] == start and out["pool"] == [] and out["problems"] == []
    got = {}; fixes.editor([dict(kind="lift", id=2)], got)(copy.deepcopy(L), sp, DAYS); assert [x["id"] for x in got["pool"]] == [2]

@t
def test_delete_and_teacher_reach_a_lesson_in_the_pool():
    sp, L = two_lessons(); pool = []; one = fixes.what(L[0])
    fixes.apply_one(L, dict(kind="lift", id=1), sp, DAYS, pool=pool)
    fixes.apply_one(L, dict(kind="teacher", key=KEY, teachers=[TEACHER]), sp, DAYS, pool=pool)
    assert pool[0]["teachers"] == [TEACHER] and L[0]["teachers"] == TEACHERS
    assert fixes.apply_one(L, dict(kind="room", id=1, group=ENTIRE, room=ROOM), sp, DAYS, pool=pool) == f"{one} (not placed) is now in {ROOM}, not no room." and pool[0]["room"] == ROOM
    assert fixes.apply_one(L, dict(kind="room", id=2, group=ENTIRE, room=ROOM), sp, DAYS, pool=pool) == f"{fixes.what(L[0])} on {DAYS[1]} period 4 is now in {ROOM}, not no room."
    assert fixes.apply_one(L, dict(kind="delete", id=1), sp, DAYS, pool=pool) == f"Deleted {one} (it was not placed)." and pool == [] and [x["id"] for x in L] == [2]

@t
def test_move_and_swap_of_a_pooled_lesson_are_refused():
    sp, L = two_lessons(); pool = []
    fixes.apply_one(L, dict(kind="lift", id=1), sp, DAYS, pool=pool); L0, P0 = copy.deepcopy(L), copy.deepcopy(pool)
    for f in (dict(kind="move", id=1, d=2, p=0), dict(kind="swap", a=1, b=2), dict(kind="swap", a=2, b=1)):
        try: fixes.apply_one(L, f, sp, DAYS, pool=pool); assert False, f
        except ValueError as e: assert str(e) == "That lesson is not placed. Place it first.", e
    for f, why in ((dict(kind="lift", id=1), "There is no lesson with that id on the timetable."), (dict(kind="place", id=2, d=0, p=2), "That lesson is not waiting to be placed.")):
        try: fixes.apply_one(L, f, sp, DAYS, pool=pool); assert False, f
        except ValueError as e: assert str(e) == why, e
    assert L == L0 and pool == P0

def _sample_lessons():
    """the primary sample's step 5 rows as timetable lessons: one id per entire-class row, one id per block (its groups' rows)"""
    out, blocks, i = [], {}, 0
    for x in SP["lessons"]:
        if not x.get("classes") or not x.get("periods"): continue
        if x.get("block") and x["code"] != ENTIRE:
            if x["block"] not in blocks: i += 1; blocks[x["block"]] = i
            k = blocks[x["block"]]
        else: i += 1; k = i
        out.append(lesson(k, k % len(DAYS), 2 + k % 4, 1, list(x["classes"]), x["subject"], x["code"], list(x["teachers"]), level=x["level"], block=x.get("block") or ""))
    return out

@t
def test_apply_never_leaves_a_lesson_on_both_sides():
    L = _sample_lessons(); ids = sorted({x["id"] for x in L}); keys = [verify._kstr(k) for k in verify.planned_rows(SP)]; R = random.Random(7); fx = []
    for _ in range(200):
        i, d, p = R.choice(ids), R.randrange(len(DAYS)), R.randrange(2, 6); kind = R.choice(("lift", "place", "move", "push", "delete", "add"))
        fx.append(dict(kind="lift", id=i) if kind == "lift" else dict(kind="place", id=i, d=d, p=p, **(dict(out=R.sample(ids, 2)) if R.random() < 0.3 else {})) if kind == "place"
                  else dict(kind="move", id=i, d=d, p=p) if kind == "move" else dict(kind="move", id=i, d=d, p=p, out=R.sample(ids, 2)) if kind == "push"
                  else dict(kind="delete", id=i) if kind == "delete" else dict(kind="add", key=R.choice(keys), d=d, p=p, n=1, room="", **(dict(out=[R.choice(ids)]) if R.random() < 0.5 else {})))
    kinds = collections.Counter()
    for k in range(len(fx) + 1):
        out = fixes.apply(L, fx[:k], SP, DAYS); on, off = {x["id"] for x in out["lessons"]}, {x["id"] for x in out["pool"]}
        assert not on & off, (k, on & off)
        gone = {f["id"] for f in fx[:k] if f["kind"] == "delete"}
        for i in ids: assert (i in on) + (i in off) == 1 or (i in gone and i not in on | off), (k, i)
        assert len(out["texts"]) + len(out["problems"]) == k
    for f, t_ in zip(fx, fixes.apply(L, fx, SP, DAYS)["texts"]): kinds[t_.split()[0]] += 1
    assert len(kinds) >= 4 and fixes.apply(L, fx, SP, DAYS)["problems"], kinds

@t
def test_a_fix_list_replayed_on_changed_lessons_skips_and_names():
    sp, L = two_lessons(); L = [x for x in L if x["id"] != 1]; start = copy.deepcopy(L)
    out = fixes.apply(L, [dict(kind="lift", id=1), dict(kind="place", id=1, d=1, p=4, out=[2])], sp, DAYS)
    assert out["problems"] == ["A fix could not be applied: There is no lesson with that id on the timetable.", "A fix could not be applied: That lesson is not waiting to be placed."], out["problems"]
    assert out["lessons"] == start and out["pool"] == [] and out["touched"] == set()
    out = fixes.apply(L, [dict(kind="move", id=1, d=1, p=4, out=[2])], sp, DAYS)
    assert out["problems"] == ["A fix could not be applied: There is no lesson with that id on the timetable."] and out["lessons"] == start and out["pool"] == [], out

@t
def test_judge_lift_place_and_push():
    L = [lesson(1, 0, 2, 2, [A], SUBJ, ENTIRE, [T[0]], level=LV), lesson(2, 1, 2, 2, [A], "Science", ENTIRE, [T[1]], level=LV), lesson(3, 3, 2, 2, [B], "Art", ENTIRE, [T[0]], level=LV)]
    m, sp = model_with(L); pool = [lesson(5, 0, 2, 2, [A], "Music", ENTIRE, [T[0]], level=LV)]
    j = lambda pool=pool, **f: fixes.judge(m, sp, DAYS, f, pool=pool)
    assert j(kind="lift", id=1) == dict(state="ok", why="", must=[], prefer=[])
    assert j(kind="lift", id=5) == dict(state="na", why="There is no lesson with that id on the timetable.", must=[], prefer=[])
    assert j(kind="place", id=5, d=2, p=2) == dict(state="ok", why="", must=[], prefer=[])
    assert j(kind="place", id=5, d=0, p=RECESS) == dict(state="na", why=f"That is not lesson time for {A}.", must=[], prefer=[])
    assert j(kind="place", id=5, d=3, p=2) == dict(state="no", why=f"{T[0]} is teaching Art for {B} then.", must=[], prefer=[])
    assert j(kind="place", id=1, d=2, p=2)["why"] == "That lesson is not waiting to be placed." and j(pool=(), kind="place", id=5, d=2, p=2)["state"] == "na"
    r = j(kind="move", id=1, d=1, p=2); assert r["state"] == "no" and r["why"] == f"{A} has Science for {A} then.", r
    assert j(kind="move", id=1, d=1, p=2, out=[2]) == dict(state="ok", why="", must=[], prefer=[])
    assert j(kind="place", id=5, d=1, p=2)["state"] == "no" and j(kind="place", id=5, d=1, p=2, out=[2])["state"] == "ok"
    assert j(kind="move", id=1, d=1, p=2, out=[1])["why"] == "That fix is not complete."
    assert j(kind="move", id=5, d=1, p=2)["why"] == "That lesson is not placed. Place it first."
    assert j(kind="teacher", key=f"C:{A}:Music", teachers=[T[2]])["state"] == "ok" and j(kind="room", id=5, group=ENTIRE, room=ROOM)["state"] == "ok"

@t
def test_slots_say_what_a_push_would_take_out():
    L = [lesson(1, 0, 2, 2, [A], SUBJ, ENTIRE, [T[0]], level=LV), lesson(2, 1, 2, 2, [A], "Science", ENTIRE, [T[1]], level=LV), lesson(3, 3, 2, 2, [B], "Art", ENTIRE, [T[0]], level=LV)]
    m, sp = model_with(L); S = fixes.slots(m, sp, DAYS, 1); old = lambda s: {k: s[k] for k in ("d", "p", "state", "why", "swap", "also")}
    assert all(set(s) == {"d", "p", "state", "why", "swap", "also", "push", "beside", "clashes"} for s in S)
    plain = fixes.slots(m, sp, DAYS, 1, extras=False)   # the old editor's callers (draft.options), the helper's and the typed request's: no push, no beside, the rest the same
    assert all(set(s) == {"d", "p", "state", "why", "swap", "also"} for s in plain) and plain == [old(s) for s in S]
    assert at(S, 1, 2)["push"] == dict(state="ok", why="", out=[dict(id=2, what=f"Science for {A}", classes=[A], groups=1)]) and old(at(S, 1, 2)) == dict(d=1, p=2, state="ok", why="", swap=2, also=[])
    assert at(S, 2, 2)["push"] is None and old(at(S, 2, 2)) == dict(d=2, p=2, state="ok", why="", swap=None, also=[])
    assert at(S, 1, 1)["push"] == dict(state="ok", why="", out=[dict(id=2, what=f"Science for {A}", classes=[A], groups=1)]) and at(S, 1, 1)["state"] == "na"
    assert at(S, 3, 2)["push"] is None and at(S, 3, 2)["state"] == "no"   # a teacher busy with another class: nothing of its class to push

@t
def test_slots_say_whether_a_lesson_can_go_beside_another():
    # G1 and G2 of one class meet at once with no shared student; a whole-class lesson cannot share a group's time
    L = [lesson(1, 0, 2, 1, [A], "Art", "G1", [T[0]], level=LV), lesson(2, 1, 2, 1, [A], "Music", "G2", [T[1]], level=LV),
         lesson(3, 3, 2, 1, [A], SUBJ, ENTIRE, [T[2]], level=LV)]
    m, sp = model_with(L); S = fixes.slots(m, sp, DAYS, 1)
    assert at(S, 1, 2)["beside"] == dict(state="ok", why="") and bare(at(S, 1, 2)) == dict(d=1, p=2, state="ok", why="", swap=2, also=[])
    assert at(S, 2, 2)["beside"] is None and at(S, 2, 2)["push"] is None
    assert at(S, 3, 2)["beside"] == {k: v for k, v in fixes.judge(m, sp, DAYS, dict(kind="move", id=1, d=3, p=2)).items() if k in ("state", "why")}
    S3 = fixes.slots(m, sp, DAYS, 3); b = at(S3, 1, 2)["beside"]
    assert b["state"] == "no" and b["why"].startswith(f"{A} has "), b
    assert at(S3, 1, 2)["state"] in ("na", "ok", "prefer", "no") and at(S3, 1, 2)["push"]["out"] == [dict(id=2, what=fixes.what(L[1]), classes=[A], groups=1)]
    pool = [lesson(5, 0, 3, 1, [A], "Drama", "G2", [T[3]], level=LV)]; L2 = L[:1] + L[2:]
    m, sp = model_with(L2); P = fixes.slots(m, sp, DAYS, 5, pool=pool)
    assert at(P, 0, 2)["beside"] == dict(state="ok", why="") and at(P, 0, 2)["push"]["out"] == [dict(id=1, what=fixes.what(L[0]), classes=[A], groups=1)]
    b = at(P, 3, 2)["beside"]; assert b["state"] == "no" and b["why"].startswith(f"{A} has "), b
    assert at(P, 2, 2)["beside"] is None

@t
def test_slots_of_a_pooled_lesson_are_places():
    L = [lesson(1, 2, 2, 2, [A], SUBJ, ENTIRE, [T[0]], level=LV)]; m, sp = model_with(L); pool = [lesson(5, 0, 2, 2, [A], "Music", ENTIRE, [T[1]], level=LV)]
    S = fixes.slots(m, sp, DAYS, 5, pool=pool)
    assert len(S) == len(DAYS) * NP and all(s["swap"] is None and s["also"] == [] for s in S)
    assert {k: at(S, 0, 2)[k] for k in ("state", "why", "push")} == dict(state="ok", why="", push=None)
    assert at(S, 2, 2)["state"] == "no" and at(S, 2, 2)["why"] == f"{A} has {SUBJ} for {A} then." and at(S, 2, 2)["push"] == dict(state="ok", why="", out=[dict(id=1, what=f"{SUBJ} for {A}", classes=[A], groups=1)])
    assert at(S, 0, RECESS)["state"] == "na"

def _thirty():
    """thirty lessons of 1A, 1B and both, on the days and periods, many on top of each other (the draft need not be clean)"""
    r = random.Random(11); L = []
    for i in range(1, 31):
        L.append(lesson(i, r.randrange(len(DAYS)), r.randrange(0, 6), r.choice((1, 1, 2)), ([A], [B], [A, B])[i % 3], (SUBJ, "Science", "Art")[i % 3], ENTIRE, [T[i % 5]], level=LV))
    return L

WHO = {"d", "p", "state", "why", "swap", "also", "there"}

@t
def test_who_is_at_each_place_and_place_judges_the_one_dropped_on():
    L = _thirty(); pool = [lesson(40, 0, 2, 2, [A], "Music", ENTIRE, [T[7]], level=LV)]; m, sp = model_with(L); seen = listed = 0
    for lid in list(range(1, 31)) + [40]:
        mine = [x for x in pool if x["id"] == lid]; pl = pool
        full = fixes.slots(m, sp, DAYS, lid, pl); who = fixes.slots(m, sp, DAYS, lid, pl, extras="who"); plain = fixes.slots(m, sp, DAYS, lid, pl, extras=False)
        assert len(full) == len(who) == len(plain) and all(set(w) == WHO for w in who) and all(set(x) == {"d", "p", "state", "why", "swap", "also"} for x in plain)
        for s, w, q in zip(full, who, plain):
            assert w["there"] == (s["push"] and s["push"]["out"]) and (w["d"], w["p"]) == (s["d"], s["p"])
            if w["there"] is not None:
                seen += 1; assert [sorted(o) for o in w["there"]] == [sorted(dict(id=x["id"], what=x["what"], classes=x["classes"], groups=x["groups"])) for x in s["push"]["out"]] and [o["id"] for o in w["there"]] == sorted(o["id"] for o in w["there"])
            if mine and w["there"] is not None: assert (w["state"], w["why"], w["swap"], w["also"]) == ("na", "Another lesson is there.", None, []), w
            elif mine: assert {k: w[k] for k in q} == q == bare(s)
            else: assert {k: w[k] for k in q} == q   # a lesson on the timetable: exactly as without the extras
            got = fixes.place(m, sp, DAYS, lid, s["d"], s["p"], pl); assert {k: v for k, v in got.items() if k != "clashes"} == {k: v for k, v in s.items() if k != "clashes"}, (lid, s["d"], s["p"])
            if s["clashes"] is not None: assert got["clashes"] == s["clashes"], (lid, s["d"], s["p"])
            else:
                assert got["clashes"] is None or got["clashes"], (lid, s["d"], s["p"])
                listed += got["clashes"] is not None
    assert seen > 100, seen
    assert listed > 0, listed   # the places with a lesson of the same classes were really there, and red places without one are listed

@t
def test_place_of_a_free_place_has_no_push_and_no_beside_and_outside_the_day_is_refused():
    L = _thirty(); m, sp = model_with(L); S = fixes.slots(m, sp, DAYS, 1); free = next(s for s in S if s["push"] is None)
    p = fixes.place(m, sp, DAYS, 1, free["d"], free["p"]); assert p == free and p["push"] is None and p["beside"] is None
    for d, q in ((len(DAYS), 0), (-1, 0), (0, NP), (0, -1), ("0", 0), (0, 1.5), (True, 0)):
        try: fixes.place(m, sp, DAYS, 1, d, q)
        except ValueError as e: assert str(e) == "That is outside the day.", (d, q, e)
        else: raise AssertionError((d, q))
    try: fixes.place(m, sp, DAYS, 999, 0, 0)
    except ValueError as e: assert str(e) == "There is no lesson with that id on the timetable."
    else: raise AssertionError("did not raise")

@t
def test_marks():
    L = [lesson(1, 0, 2, 1, [A], SUBJ, ENTIRE, [T[0]], room=ROOM, level=LV), lesson(2, 0, 2, 1, [B], "Art", ENTIRE, [T[0]], room=ROOM, level=LV),
         lesson(3, 1, 2, 1, [A], "Art", ENTIRE, [T[1]], level=LV), lesson(4, 1, 2, 1, [A], "Music", "G1", [T[2]], level=LV),
         lesson(5, 2, 2, 1, [A], "Art", "G1", [T[1]], room="TBC", level=LV), lesson(6, 2, 2, 1, [A], "Music", "G2", [T[2]], room=ROOM, level=LV),
         lesson(7, 0, RECESS, 1, [C3], "Art", ENTIRE, [], room=ROOM, level=LV)]
    m, sp = model_with(L); b = fixes.Busy(m); mk = lambda i, **k: fixes.marks(b, b.ids[i], **k)
    assert mk(1) == ["teacher", "room"] and mk(2) == ["teacher", "room"]
    assert mk(3) == ["class", "noroom"] and mk(4) == ["class", "noroom"]
    assert mk(5) == ["noroom"] and mk(6) == []   # two groups of one class at once
    assert mk(7) == ["noteacher", "break"] and mk(1, pool=True) == ["notplaced"]
    assert fixes.marks(b, [lesson(9, len(DAYS), 2, 1, [A], "Art", ENTIRE, [T[0]], level=LV)]) == ["break", "noroom"]
    m["room_cap"] = dict(m["room_cap"], **{ROOM: 2}); b = fixes.Busy(m); assert fixes.marks(b, b.ids[1]) == ["teacher"]
    sp0, Bk = one_block(); Bk = [dict(x, d=0, p=2, teachers=[T[0]], room=ROOM) for x in Bk]; m, sp = model_with(Bk); b = fixes.Busy(m)
    assert fixes.marks(b, b.ids[7]) == []   # a band's own groups share a teacher and a room

@t
def test_no_teacher_and_no_room_are_never_a_clash():
    L = [lesson(1, 0, 2, 1, [A], SUBJ, ENTIRE, [T[0]], room=ROOM, level=LV), lesson(2, 1, 2, 1, [B], "Art", ENTIRE, [T[1]], level=LV)]
    m, sp = model_with(L); key = f"C:{A}:{SUBJ}"
    j = fixes.judge(m, sp, DAYS, dict(kind="teacher", key=key, teachers=[])); assert j["state"] == "ok", j
    j = fixes.judge(m, sp, DAYS, dict(kind="room", id=1, group=ENTIRE, room="")); assert j["state"] == "ok", j
    rows = copy.deepcopy(m["lessons"]); name = verify._name(("C", A, SUBJ))
    assert fixes.apply_one(rows, dict(kind="teacher", key=key, teachers=[]), sp, DAYS) == f"{name} now has no teacher; it had {T[0]}."
    assert fixes.apply_one(rows, dict(kind="teacher", key=key, teachers=[T[2]]), sp, DAYS) == f"{name} is now taught by {T[2]}; it had no teacher."
    assert fixes.apply_one(rows, dict(kind="teacher", key=key, teachers=[T[1]]), sp, DAYS) == f"{name} is now taught by {T[1]}, not {T[2]}."

@t
def test_marks_after_a_teacher_is_taken_away():
    L = [lesson(1, 0, 2, 1, [A], SUBJ, ENTIRE, [T[0]], room=ROOM, level=LV)]
    m, sp = model_with(L); rows = copy.deepcopy(m["lessons"])
    fixes.apply_one(rows, dict(kind="teacher", key=f"C:{A}:{SUBJ}", teachers=[]), sp, DAYS)
    b = fixes.Busy(dict(m, lessons=rows)); assert fixes.marks(b, b.ids[1]) == ["noteacher"], fixes.marks(b, b.ids[1])

def _of_key(k, i, d, p, n_=1, who=None): return lesson(i, d, p, n_, [CLS], SUBJ, ENTIRE, list(who or TEACHERS), level=ROW["level"])
PLAN = verify.planned_rows(SP)[("C", CLS, SUBJ)]["periods"]
def _placed(k): return [_of_key(KEY, 10 + j, 1 + j // 6, 5 + j % 6) for j in range(k)]   # k one-period lessons of KEY
def _leave(k): return f"That would leave {SUBJ} for {CLS} with {k} periods; step 3 plans {PLAN}."

@t
def test_a_pushed_out_or_pooled_lesson_still_counts_for_the_plan():
    m, sp = model_with(_placed(PLAN))
    r = fixes.judge(m, sp, DAYS, dict(kind="add", key=KEY, d=1, p=5, n=1, room="", out=[10]))
    assert r["state"] == "no" and r["why"] == _leave(PLAN + 1), r   # 10 waits in the pool: still counted
    m, sp = model_with(_placed(PLAN - 1)); pool = [_of_key(KEY, 50, 0, 2)]
    r = fixes.judge(m, sp, DAYS, dict(kind="add", key=KEY, d=4, p=2, n=1, room=""), pool=pool); assert r["state"] == "no" and r["why"] == _leave(PLAN + 1), r
    assert fixes.judge(m, sp, DAYS, dict(kind="add", key=KEY, d=4, p=2, n=1, room=""))["state"] == "ok"   # without the pool it is missing
    r = fixes.judge(m, sp, DAYS, dict(kind="delete", id=50), pool=pool); assert r == dict(state="no", why=_leave(PLAN - 1), must=[], prefer=[]), r
    assert fixes.judge(m, sp, DAYS, dict(kind="delete", id=10), pool=pool)["why"] == _leave(PLAN - 1)
    m, sp = model_with(_placed(PLAN)); assert fixes.judge(m, sp, DAYS, dict(kind="delete", id=50), pool=pool) == dict(state="ok", why="", must=[], prefer=[])   # a surplus one


@t
def test_the_option_lists_take_the_pool():
    m, sp = model_with(_placed(PLAN)); pool = [_of_key(KEY, 50, 0, 2)]
    assert fixes.can_delete(m, sp, DAYS, 10) == fixes.can_delete(m, sp, DAYS, 10, pool=[]) == dict(state="no", why=_leave(PLAN - 1), plan=True)   # a placed lesson step 5 asks for
    assert fixes.can_delete(m, sp, DAYS, 10, pool=pool) == dict(state="ok", why="", plan=False)   # the pooled one counts: this one is surplus
    m, sp = model_with(_placed(PLAN - 1)); A = fixes.add_slots(m, sp, DAYS, KEY, 1)
    assert any(x["state"] == "ok" for x in A) and A == fixes.add_slots(m, sp, DAYS, KEY, 1, pool=[])
    A = fixes.add_slots(m, sp, DAYS, KEY, 1, pool=pool); assert not [x for x in A if x["state"] in ("ok", "prefer")]
    assert next(x for x in A if (x["d"], x["p"]) == (4, 2)) == dict(d=4, p=2, state="no", why=_leave(PLAN + 1))
    assert fixes.room_options(m, sp, DAYS, 10, ENTIRE, pool=pool) is not None and fixes.teacher_options(m, sp, DAYS, KEY, pool) is not None

@t
def test_a_pooled_lesson_counts_in_the_teachers_load():
    teachers = [dict(x, allowance=2) if x["name"] == TEACHER else x for x in SP["teachers"]]
    m, sp = model_with([_of_key(KEY, 1, 0, 2)], teachers=teachers); pool = [_of_key(KEY, 5, 1, 2, n_=2)]
    r = fixes.judge(m, sp, DAYS, dict(kind="teacher", key=KEY, teachers=[TEACHER]), pool=pool)
    assert r["state"] == "prefer" and r["why"] == f"{TEACHER} would have 3 periods, 1 over the allowance.", r
    assert fixes.judge(m, sp, DAYS, dict(kind="teacher", key=KEY, teachers=[TEACHER]))["state"] == "ok"

@t
def test_an_add_takes_an_id_past_the_pool_in_judge_too():
    m, sp = model_with([lesson(1, 2, 2, 1, [A], "Art", ENTIRE, [T[0]], level=LV)]); pool = [lesson(2, 0, 2, 1, [B], "Music", ENTIRE, [T[1]], level=LV)]
    f = dict(kind="add", key=KEY, d=4, p=2, n=1, room="", out=[2])
    assert fixes.judge(m, sp, DAYS, f, pool=pool)["state"] == "ok", fixes.judge(m, sp, DAYS, f, pool=pool)
    L = [lesson(1, 2, 2, 1, [A], "Art", ENTIRE, [T[0]], level=LV), pool[0]]; out = fixes.apply(L, [dict(kind="lift", id=2), f], sp, DAYS)
    assert out["problems"] == [] and [x["id"] for x in out["pool"]] == [2] and out["texts"][1].startswith("Added ")

@t
def test_more_marks_and_a_place_on_a_break():
    sp0, Bk = one_block(); ROOM2 = SP["venues"][1]["room"]
    Bk = [dict(x, d=0, p=2, teachers=[T[0]], room=ROOM if j == 0 else ROOM2) for j, x in enumerate(Bk)]
    m, sp = model_with(Bk); b = fixes.Busy(m); assert fixes.marks(b, b.ids[7]) == []   # in two rooms, none over
    m, sp = model_with(Bk + [lesson(40, 0, 3, 1, [D], "Art", ENTIRE, [T[5]], room=ROOM2, level=LV)]); b = fixes.Busy(m)
    assert fixes.marks(b, b.ids[7]) == ["room"] and fixes.marks(b, b.ids[40]) == ["room"]
    m, sp = model_with([lesson(1, 0, RECESS, 1, [A], SUBJ, ENTIRE, [T[0]], level=LV)])
    r = fixes.judge(m, sp, DAYS, dict(kind="place", id=5, d=0, p=RECESS, out=[1]), pool=[lesson(5, 2, 2, 1, [A], "Music", ENTIRE, [T[1]], level=LV)])
    assert r == dict(state="na", why=f"That is not lesson time for {A}.", must=[], prefer=[]), r

@t
def test_short_counts_a_pooled_lesson_as_timetabled():
    m, sp = model_with([]); P = verify.planned_rows(SP)[("C", CLS, SUBJ)]["periods"]
    assert {x["key"]: x for x in fixes.short(m, sp)}[KEY]["have"] == 0
    pool = [lesson(1, 0, 2, 1, [CLS], SUBJ, ENTIRE, TEACHERS, level=LV)]
    got = {x["key"]: x for x in fixes.short(m, sp, pool)}; assert got[KEY]["have"] == 1 if P > 1 else KEY not in got, got.get(KEY)
    assert fixes.short(m, sp, [lesson(1, 0, 2, P, [CLS], SUBJ, ENTIRE, TEACHERS, level=LV)]) == [x for x in fixes.short(m, sp) if x["key"] != KEY]

# ----------------------------------------------------------------------------------------------- every collision at a place
V = [x["room"] for x in SP["venues"]]
def _crowded():
    """_thirty with rooms, a rain room, two groups of 1A, two bands every student takes and students in them: every kind of clash somewhere"""
    L = _thirty()
    for x in L[::4]: x["room"] = V[0]
    for x in L[1::6]: x["room"] = V[1]
    L[2]["rain"] = V[1]
    L += [lesson(31, 0, 2, 1, [A], "Music", "G1", [T[6]], room=V[1], level=LV), lesson(32, 1, 3, 1, [A], "Art", "G2", [T[7]], level=LV)]
    L += [lesson(33, 2, 2, 1, [A, B], "Art", g, [T[k]], level=LV, block="BX") for g, k in (("X1", 1), ("X2", 2), ("X3", 3))]
    L += [lesson(34, 3, 3, 2, [A], "Music", g, [T[k]], level=LV, block="BY") for g, k in (("Y1", 4), ("Y2", 6))]
    st = lambda i, c, gs: dict(id=i, name=f"Pupil {i}", level=LV, groups=gs, **{"class": c})
    return model_with(L, blocks=[dict(block="BX", level=LV, classes=[A, B]), dict(block="BY", level=LV, classes=[A])],
                      students=[st("S1", A, ["G1", "X1", "Y1"]), st("S2", A, ["G2", "X2", "Y2"]), st("S3", B, ["X3"]), st("S4", A, ["G1", "X3", "Y1"])])

def _named_first(s):
    """what clash's sentence names first: the teacher, the group code or class of shared students, the room, else the class"""
    import re
    if " is teaching " in s: return s.split(" is teaching ")[0]
    if (g := re.match(r"\d+ students? of (.+?) ha(?:s|ve) ", s)): return g.group(1)
    if s.endswith(" is in use then."): return s[: -len(" is in use then.")]
    return s.split(" has ")[0]

@t
def test_whys_agree_with_the_first_reason():
    m, sp = _crowded(); b = fixes.Busy(m); kinds = collections.Counter()
    for i, rows in b.ids.items():
        nn = rows[0]["n"]
        for d in range(len(DAYS)):
            for p in range(NP):
                got, why = b.whys(rows, d, p, nn, (i,)), b.clash(rows, d, p, nn, (i,))
                assert bool(got) == bool(why), (i, d, p, got, why)
                assert all(set(x) == {"kind", "text", "ids"} and x["kind"] in ("teacher", "class", "students", "room") for x in got), got
                for x in got:
                    assert all(type(j) is int and j != i and any(y["d"] == d and y["p"] < p + nn and p < y["p"] + y["n"] for y in b.ids[j]) for j in x["ids"]), (i, d, p, x)
                    if x["kind"] != "room": assert len(x["ids"]) == 1, x
                if why: assert _named_first(why) in got[0]["text"], (i, d, p, why, got)
                kinds.update(x["kind"] for x in got)
    assert set(kinds) == {"teacher", "class", "students", "room"}, kinds   # the model reaches every kind

@t
def test_whys_lists_every_kind_in_order():
    L = [lesson(1, 0, 2, 1, [A], SUBJ, ENTIRE, [T[0]], room=ROOM, level=LV), lesson(2, 1, 2, 1, [B], "Science", ENTIRE, [T[0]], level=LV),
         lesson(3, 1, 2, 1, [A], "Art", ENTIRE, [T[1]], level=LV), lesson(4, 1, 2, 1, [C3], "Music", ENTIRE, [T[2]], room=ROOM, level=LV)]
    m, sp = model_with(L); b = fixes.Busy(m); got = b.whys(b.ids[1], 1, 2, 1, (1,))
    assert [x["kind"] for x in got] == ["teacher", "class", "room"], got
    assert [x["text"] for x in got] == [f"{T[0]} is teaching Science for {B} then.", f"{A} has Art for {A} then.", f"{ROOM} is in use then."], got

@t
def test_whys_names_a_band_once():
    L = [lesson(1, 0, 2, 1, [A, B], SUBJ, ENTIRE, [T[5]], level=LV)] + [lesson(7, 1, 2, 1, [A, B], "Art", g, [T[k]], level=LV, block="BX") for g, k in (("X1", 1), ("X2", 2), ("X3", 3))]
    m, sp = model_with(L, students=[dict(id="S1", name="Ann Lee", level=LV, groups=["X1"], **{"class": A}), dict(id="S2", name="Ben Tan", level=LV, groups=["X2"], **{"class": B})])
    b = fixes.Busy(m); nm = lambda i: fixes.named(b.ids[i]); got = b.whys(b.ids[1], 1, 2, 1, (1,), name=nm)
    assert got == [dict(kind="class", text=f"{A} and {B} have {nm(7)} then.", ids=[7])], got
    assert nm(7).startswith("the ") and nm(7).endswith(" band")

@t
def test_whys_one_line_a_teacher_and_lesson():
    L = [lesson(1, 0, 2, 2, [A], SUBJ, ENTIRE, [T[0]], level=LV), lesson(2, 1, 2, 2, [B], "Science", ENTIRE, [T[0]], level=LV)]
    m, sp = model_with(L); b = fixes.Busy(m)
    assert b.whys(b.ids[1], 1, 2, 2, (1,)) == [dict(kind="teacher", text=f"{T[0]} is teaching Science for {B} then.", ids=[2])]

@t
def test_whys_lines_carry_the_ids_of_the_lessons_in_the_way():
    L = [lesson(1, 0, 2, 1, [A], SUBJ, ENTIRE, [T[0]], room=ROOM, level=LV), lesson(2, 1, 2, 1, [B], "Science", ENTIRE, [T[0]], level=LV),
         lesson(3, 1, 2, 1, [A], "Art", ENTIRE, [T[1]], level=LV), lesson(4, 1, 2, 1, [C3], "Music", ENTIRE, [T[2]], room=ROOM, level=LV)]
    m, sp = model_with(L); b = fixes.Busy(m); got = b.whys(b.ids[1], 1, 2, 1, (1,))
    assert [(x["kind"], x["ids"]) for x in got] == [("teacher", [2]), ("class", [3]), ("room", [4])], got
    assert all(set(x) == {"kind", "text", "ids"} for x in got)

@t
def test_whys_room_line_names_the_lessons_in_the_room_and_those_whose_wet_weather_room_it_is():
    L = [lesson(1, 0, 2, 1, [A], SUBJ, ENTIRE, [T[0]], room=ROOM, level=LV), lesson(2, 1, 2, 1, [B], "Art", ENTIRE, [T[1]], room=ROOM, level=LV),
         dict(lesson(3, 1, 2, 1, [C3], "Music", ENTIRE, [T[2]], level=LV), rain=ROOM)]
    m, sp = model_with(L); b = fixes.Busy(m)
    assert b.whys(b.ids[1], 1, 2, 1, (1,)) == [dict(kind="room", text=f"{ROOM} is in use then.", ids=[2, 3])]
    L = [dict(lesson(1, 0, 2, 1, [A], SUBJ, ENTIRE, [T[0]], level=LV), rain=ROOM), lesson(2, 1, 2, 1, [B], "Art", ENTIRE, [T[1]], room=ROOM, level=LV)]
    m, sp = model_with(L); b = fixes.Busy(m)   # the rows' own wet-weather room: the lessons in it
    assert b.whys(b.ids[1], 1, 2, 1, (1,)) == [dict(kind="room", text=f"{ROOM} is in use then.", ids=[2])]
    L = [dict(lesson(1, 0, 2, 1, [A], SUBJ, ENTIRE, [T[0]], level=LV), rain=ROOM), lesson(2, 1, 2, 1, [B], "Art", ENTIRE, [T[1]], room=ROOM, level=LV),
         dict(lesson(3, 1, 2, 1, [C3], "Music", ENTIRE, [T[2]], level=LV), rain=ROOM)]
    m, sp = model_with(L); b = fixes.Busy(m)   # a lesson that only shares the wet-weather room is not in the way
    assert b.whys(b.ids[1], 1, 2, 1, (1,)) == [dict(kind="room", text=f"{ROOM} is in use then.", ids=[2])]

@t
def test_place_lists_the_collisions_of_a_red_place_with_no_lesson_of_the_class_there():
    L = [lesson(1, 0, 2, 1, [A], SUBJ, ENTIRE, [T[0]], level=LV), lesson(2, 1, 2, 1, [B], "Art", ENTIRE, [T[0]], level=LV)]
    m, sp = model_with(L); s = fixes.place(m, sp, DAYS, 1, 1, 2)
    assert s["push"] is None and s["beside"] is None and s["state"] == "no"
    assert s["clashes"] == [dict(kind="teacher", text=f"{T[0]} is teaching Art for {B} then.", ids=[2])], s["clashes"]
    assert fixes.place(m, sp, DAYS, 1, 2, 2)["clashes"] is None   # nothing collides there
    red = next(x for x in fixes.slots(m, sp, DAYS, 1) if (x["d"], x["p"]) == (1, 2)); assert red["clashes"] is None   # the slots are as before

@t
def test_whys_on_a_double_day():
    L = [lesson(1, 1, 2, 1, [A], SUBJ, ENTIRE, [T[0]], room="TBC", level=LV), lesson(2, 0, 2, 1, [B], "Art", ENTIRE, [T[0]], room="TBC", level=LV), lesson(3, 1, 4, 1, [B], "Art", ENTIRE, [T[0]], room="TBC", level=LV)]
    school = dict(SP["school"], extra_settings=list(SP["school"].get("extra_settings") or []) + [[spec_mod.DOUBLE, DAYS[0], ""]])
    m, sp = model_with(L, school=school); b = fixes.Busy(m); assert m["double"] == {0}
    assert b.whys(b.ids[1], 0, 2, 1, (1,)) == [] and b.clash(b.ids[1], 0, 2, 1, (1,)) is None   # the day named: no teacher line
    assert [x["kind"] for x in b.whys(b.ids[1], 1, 4, 1, (1,))] == ["teacher"]   # another day: the teacher line

@t
def test_place_lists_every_collision_where_another_lesson_is():
    L = [lesson(1, 0, 2, 1, [A], SUBJ, ENTIRE, [T[0]], room=ROOM, level=LV), lesson(2, 1, 2, 1, [A], "Art", ENTIRE, [T[0]], room=ROOM, level=LV)]
    m, sp = model_with(L); s = fixes.place(m, sp, DAYS, 1, 1, 2)
    assert s["push"] is not None and s["clashes"] == [dict(kind="teacher", text=f"{T[0]} is teaching Art for {A} then.", ids=[2]), dict(kind="class", text=f"{A} has Art for {A} then.", ids=[2]), dict(kind="room", text=f"{ROOM} is in use then.", ids=[2])], s["clashes"]
    free = fixes.place(m, sp, DAYS, 1, 2, 2); assert free["push"] is None and free["clashes"] is None
    assert all("clashes" not in x for x in fixes.slots(m, sp, DAYS, 1, extras=False) + fixes.slots(m, sp, DAYS, 1, extras="who"))

if "--full" in sys.argv:
    SOLVED = []
    def solved_primary():
        """the primary sample solved as tests/smoke.py --full does (once), checked against its setup plus the WIDE rule rows -> (m, setup, days, timetable path)"""
        if SOLVED: return SOLVED[0]
        work = tempfile.mkdtemp(); setup, tt = os.path.join(work, "setup.xlsx"), os.path.join(work, "timetable.xlsx"); env = dict(os.environ, PYTHONPATH=ROOT)
        subprocess.run([sys.executable, "-m", "ttgen", "sample", "primary", "--out", setup], check=True, env=env, cwd=ROOT, capture_output=True)
        done = subprocess.run([sys.executable, "-m", "ttgen", "solve", setup, "--out", tt, "--time", "30"], env=env, cwd=ROOT, capture_output=True)   # 30 s: feasible and clean in 15
        assert done.returncode == 0 and os.path.exists(tt), "The solve did not finish in the time given, so there is no timetable to check."
        own = export.model_from_files(setup, tt)["setup"]; sp = copy.deepcopy(own); sp["rules"] = list(sp.get("rules") or []) + WIDE
        m = export.model_from_files(None, tt, spec=sp); SOLVED.append((m, sp, m["days"], tt)); return SOLVED[0]

    def r_(scope, target, rule, strength="Must", **k): return dict(scope=scope, target=target, rule=rule, strength=strength, week="Both", day=k.pop("day", "All"), **k)
    WIDE = [r_("Level", "P1", "Keep free together", "Prefer", day="Tue", **{"from": 7, "to": 8}), r_("Department", "MA", "At most N at once", number=3),
            r_("School", "Whole school", "Max periods a day", "Prefer", number=8), r_("School", "Whole school", "Max periods in a row", number=6),
            r_("School", "Whole school", "At least one recess a day", "Prefer"), r_("Subject", "English Language", "Not on the same day as", "Prefer", subject="Art"),
            r_("Subject", "Mathematics", "Once a day per group"), r_("Level", "P2", "Same time across classes", subject="Physical Education")]

    def sample_ids(m, k):
        """k lesson ids: a block lesson, a whole-class one, a group one, then others spread over the list"""
        by = {}
        for x in m["lessons"]: by.setdefault(x["id"], []).append(x)
        block = next(i for i, r in by.items() if len(r) > 1); whole = next(i for i, r in by.items() if len(r) == 1 and r[0]["group"] == ENTIRE)
        group = next((i for i, r in by.items() if len(r) == 1 and r[0]["group"] != ENTIRE), None)
        out = list(dict.fromkeys(i for i in (block, whole, group) if i is not None)); rest = [i for i in by if i not in out]
        return out + rest[:: max(1, len(rest) // max(1, k - len(out)))][: k - len(out)]

    LESSON_TIME = ("sits in a break", "sits in a class's recess", "(Settings: Lessons end by)")
    def full_state(m, sp, days, tt, lid, s):
        """the reference: the fix applied to every lesson through the app's own path, every check rebuilt, the same counting rule"""
        fix = dict(kind="swap", a=lid, b=s["swap"]) if s["swap"] else dict(kind="move", id=lid, d=s["d"], p=s["p"])
        out = {}; m2 = export.model_from_files(None, tt, spec=m["setup"], edit=fixes.editor([fix], out))
        if out["problems"]: return "na"
        if s["swap"]:
            ra, rb = rows_of(m, lid), rows_of(m, s["swap"]); blk = lambda r: len(r) > 1 or any(x["block"] for x in r)
            if {c for x in ra for c in x["classes"]} != {c for x in rb for c in x["classes"]} and (blk(ra) or blk(rb)): return "na"
        new = set(m2["checks"]["problems"]) - set(m["checks"]["problems"])
        if any(x.endswith(LESSON_TIME) or x.endswith(LESSON_TIME[2] + ".") for x in new): return "na"
        if [x for x in new if not x.endswith("planned.")]: return "no"
        if {k: v["periods"] for k, v in verify.placed(m2).items()} != {k: v["periods"] for k, v in verify.placed(m).items()}: return "no"
        subj = lambda mm: {fixes._subject(w): w["strength"] for w in verify.rules(mm, sp)[0]}
        sb, sa = subj(m), subj(m2); new = [v for k, v in sa.items() if k not in sb]
        return "no" if "Must" in new else "prefer" if new else "ok"

    @t
    def the_reduced_check_agrees_with_the_full_one_and_is_fast():
        m, sp, days, tt = solved_primary(); assert m["checks"]["ok"], m["checks"]["problems"][:5]
        assert not verify.rules(m, sp)[1], verify.rules(m, sp)[1]   # every WIDE row is checked
        for lid in sample_ids(m, 6):
            t0 = time.time(); S = fixes.slots(m, sp, days, lid); dt = time.time() - t0; assert dt < 2, (lid, dt)
            live = [s for s in S if s["state"] != "na"]
            for s in random.Random(1).sample(live, min(5, len(live))):
                assert s["state"] == full_state(m, sp, days, tt, lid, s), (lid, s)

    def ref_state(m0, sp, days, tt, base, fix):
        """the reference for any kind of fix: the fixes before it (base, of which m0 is the model) and the fix applied to every
        lesson through the app's own path, every check rebuilt, by the spec's rule of clean"""
        out = {}; m2 = export.model_from_files(None, tt, spec=m0["setup"], edit=fixes.editor(base + [fix], out))
        if out["problems"]: return "na"
        if fix["kind"] == "swap":
            ra, rb = rows_of(m0, fix["a"]), rows_of(m0, fix["b"]); blk = lambda r: len(r) > 1 or any(x["block"] for x in r)
            if {c for x in ra for c in x["classes"]} != {c for x in rb for c in x["classes"]} and (blk(ra) or blk(rb)): return "na"
        new = set(m2["checks"]["problems"]) - set(m0["checks"]["problems"])
        if any(x.endswith(LESSON_TIME) or x.endswith(LESSON_TIME[2] + ".") for x in new): return "na"
        if [x for x in new if not x.endswith("planned.")]: return "no"
        p0, p2 = ({k: v["periods"] for k, v in verify.placed(mm).items()} for mm in (m0, m2))
        for k in set(p0) | set(p2):
            was, now, want = p0.get(k, 0), p2.get(k, 0), m0["planned"].get(k, 0)
            if now != was and not (was < now <= want or want <= now < was): return "no"
        subj = lambda mm: {fixes._subject(w): w["strength"] for w in verify.rules(mm, sp)[0]}
        sb, sa = subj(m0), subj(m2); new = [v for k, v in sa.items() if k not in sb]
        if "Must" in new: return "no"
        if fix["kind"] in ("teacher", "add", "delete"):
            def load(mm):
                out = collections.Counter(); seen = set()
                for x in mm["lessons"]:
                    for t_ in x["teachers"]:
                        if (x["id"], t_) not in seen: seen.add((x["id"], t_)); out[t_] += x["n"]
                return out
            l0, l2 = load(m0), load(m2)
            for t_ in l2:
                cap = fixes._allowance(m0["teacher_ix"].get(t_, {}).get("allowance"))
                if cap is not None and l2[t_] > cap and l2[t_] > l0[t_]: new.append("Prefer")
        return "prefer" if new else "ok"

    def slot_fix(lid, s): return dict(kind="swap", a=lid, b=s["swap"]) if s["swap"] else dict(kind="move", id=lid, d=s["d"], p=s["p"])

    def with_fixes(sp, tt, base):
        out = {}; m = export.model_from_files(None, tt, spec=sp, edit=fixes.editor(base, out)); assert not out["problems"], out["problems"]; return m

    @t
    def the_reduced_check_agrees_with_the_full_one_for_every_kind_and_a_chain():
        m, raw, days, tt = solved_primary(); sp = m["checked_setup"]; R = random.Random(2); seen = collections.Counter()   # the derived setup, as the app passes it
        def agree(m0, base, fix, state):
            ref = ref_state(m0, sp, days, tt, base, fix); seen[fix["kind"], state] += 1; assert state == ref, (fix, state, ref, fixes.judge(m0, sp, days, fix))
        by = {}
        for x in m["lessons"]: by.setdefault(x["id"], []).append(x)
        whole = [i for i, r in by.items() if len(r) == 1 and r[0]["group"] == ENTIRE and not r[0]["block"]]
        # teacher fixes on a few keys
        for lid in R.sample(whole, 3):
            key = verify._kstr(fixes._row_key(by[lid][0]))
            for o in fixes.teacher_options(m, sp, days, key)[:2]: agree(m, [], dict(kind="teacher", key=key, teachers=o["teachers"]), o["state"])
        # an add towards the plan: one lesson dropped from the solved timetable first
        for gone in [i for i in whole if by[i][0]["n"] == 1][:5] + whole[:1]:   # a one-period lesson has the most open slots
            key = verify._kstr(fixes._row_key(by[gone][0])); base = [dict(kind="delete", id=gone)]; m1 = with_fixes(raw, tt, base)
            assert any(x["key"] == key for x in fixes.short(m1, sp)); k = by[gone][0]["n"]; S = fixes.add_slots(m1, sp, days, key, k)
            open_ = [s for s in S if s["state"] in ("ok", "prefer")]
            if open_: break
        assert open_, "no add towards the plan has an open slot"
        for s in R.sample(open_, min(2, len(open_))) + R.sample([s for s in S if s["state"] == "no"], 3):
            agree(m1, base, dict(kind="add", key=key, d=s["d"], p=s["p"], n=k, room=fixes.add_room(m1, sp, key, s["d"], s["p"], k)), s["state"])
        # a delete of an extra lesson: a duplicate added first
        def free_dup(i):   # a slot where a copy of lesson i clashes with nothing (only its count is past the plan)
            x = by[i][0]; return next((s for s in fixes.add_slots(m, sp, days, verify._kstr(fixes._row_key(x)), x["n"]) if s["why"].startswith("That would leave")), None)
        dup, s = next((i, s) for i in [i for i in whole if i != gone and by[i][0]["n"] == 1] + whole for s in [free_dup(i)] if s)
        x = by[dup][0]; key = verify._kstr(fixes._row_key(x))
        base = [dict(kind="add", key=key, d=s["d"], p=s["p"], n=x["n"], room="")]; m1 = with_fixes(raw, tt, base); new_id = max(by) + 1
        assert rows_of(m1, new_id)
        for lid in (new_id, dup, next(i for i in whole if i not in (dup, gone))): agree(m1, base, dict(kind="delete", id=lid), fixes.can_delete(m1, sp, days, lid)["state"])
        assert fixes.can_delete(m1, sp, days, new_id)["state"] in ("ok", "prefer")
        # a chain: the second fix judged after the first is applied
        lid, first = next((i, s) for i in whole[3:] for s in fixes.slots(m, sp, days, i) if s["state"] in ("ok", "prefer"))
        base = [slot_fix(lid, first)]; m1 = with_fixes(raw, tt, base)
        nxt = next(i for i in whole if i != lid and set(by[i][0]["classes"]) & set(by[lid][0]["classes"]))
        S = [s for s in fixes.slots(m1, sp, days, nxt) if s["state"] != "na"]
        for s in R.sample(S, 4): agree(m1, base, slot_fix(nxt, s), s["state"])
        back = fixes.judge(m1, sp, days, dict(kind="move", id=lid, d=by[lid][0]["d"], p=by[lid][0]["p"]))["state"]; agree(m1, base, dict(kind="move", id=lid, d=by[lid][0]["d"], p=by[lid][0]["p"]), back)
        assert {k_ for k_, _ in seen} >= {"teacher", "add", "delete", "move"} and len({st for _, st in seen}) >= 2, seen
        print("  agreed:", dict(seen))

# ----------------------------------------------------------------------------------------------- the fix wave after the whole-branch review
@t
def test_a_band_in_the_way_is_named_as_a_band_with_its_classes():
    sp0, Bk = one_block(); cls = Bk[0]["classes"]; label = export.block_label(Bk[0]["block"], Bk[0]["level"]); assert label
    L = Bk + [lesson(30, 1, 5, 2, [cls[1]], SUBJ, ENTIRE, [T[-1]], level=LV)]
    m, sp = model_with(L); S = fixes.slots(m, sp, DAYS, 30)
    assert at(S, 0, 0)["push"]["out"] == [dict(id=7, what=f"the {label} band", classes=cls, groups=3)], at(S, 0, 0)["push"]
    assert fixes.named(Bk) == f"the {label} band" and fixes.band(Bk) == label and fixes.named(L[-1:]) == fixes.what(L[-1]) and fixes.band(L[-1:]) == ""
    two = [dict(x, block="") for x in Bk]; shorts = " / ".join(dict.fromkeys(export.abbrev(x["subject"]) for x in two))
    assert fixes.named(two) == f"the {shorts} band"   # a band with no block is named by its subjects, as the board names its card
    pool = []; text = fixes.apply_one(copy.deepcopy(L), dict(kind="move", id=30, d=0, p=0, out=[7]), sp, DAYS, pool=pool)
    assert text.endswith(f" Pushed out: the {label} band.") and {x["id"] for x in pool} == {7}, text

@t
def test_at_replay_out_lifts_only_a_lesson_still_in_the_way():
    other = next(c["class"] for c in SP["classes"] if c["class"] != CLS)
    sp, L = two_lessons(); L.append(lesson(3, 3, 0, 1, [other], "Art", ENTIRE, [TEACHER], level=ROW["level"]))   # another class, at the target
    out = fixes.apply(L, [dict(kind="move", id=2, d=3, p=99), dict(kind="move", id=1, d=3, p=0, out=[2, 3])], sp, DAYS)   # the first is skipped: 2 never came
    assert len(out["problems"]) == 1 and out["pool"] == [] and out["texts"] == [f"Moved {fixes.what(L[0])} from {DAYS[0]} period 2 to {DAYS[3]} period 0."], out
    assert {x["id"]: (x["d"], x["p"]) for x in out["lessons"]} == {1: (3, 0), 2: (1, 4), 3: (3, 0)}
    sp, L = two_lessons()   # the same day, a period apart: not in the way either
    out = fixes.apply(L, [dict(kind="move", id=1, d=1, p=2, out=[2])], sp, DAYS); assert out["pool"] == [] and "Pushed out" not in out["texts"][0], out
    out = fixes.apply(L, [dict(kind="move", id=1, d=1, p=3, out=[2])], sp, DAYS); assert [x["id"] for x in out["pool"]] == [2] and "Pushed out" in out["texts"][0], out   # periods 3-4 meet 4-5
    pool = [lesson(5, 0, 0, 2, [CLS], "Music", ENTIRE, TEACHERS, level=ROW["level"])]; L2 = copy.deepcopy(two_lessons()[1])
    assert "Pushed out" not in fixes.apply_one(L2, dict(kind="place", id=5, d=2, p=0, out=[1, 2]), sp, DAYS, pool=pool) and [x["id"] for x in pool] == []   # a place, nothing in the way
    x = fixes.apply(two_lessons()[1], [dict(kind="add", key=KEY, d=0, p=2, n=1, room="", out=[1, 2])], sp, DAYS)
    assert [y["id"] for y in x["pool"]] == [1] and x["texts"][0].endswith(f"Pushed out: {fixes.what(two_lessons()[1][0])}."), x   # an add: only the one it meets

@t
def test_the_delete_says_whether_its_no_is_the_plan():
    m, sp = model_with(_placed(PLAN)); j = fixes.can_delete(m, sp, DAYS, 10)
    assert j == dict(state="no", why=_leave(PLAN - 1), plan=True), j
    m, sp = model_with(_placed(PLAN + 1)); assert fixes.can_delete(m, sp, DAYS, 10) == dict(state="ok", why="", plan=False)   # a surplus lesson
    real = fixes.judge; fixes.judge = lambda *a, **k: dict(state="no", why="Rule Not available: Mr X has Art on Mon period 2.", must=["x"], prefer=[])
    try: assert fixes.can_delete(m, sp, DAYS, 10) == dict(state="no", why="Rule Not available: Mr X has Art on Mon period 2.", plan=False)   # a no from a rule
    finally: fixes.judge = real

@t
def test_two_bands_on_one_class_at_once():
    """a band every student takes a group of keeps the class busy while all its groups meet: another band's lesson then is a class clash"""
    g = lambda i, d, code, blk, tch: lesson(i, d, 2, 1, [A], "Art", code, [tch], room="TBC", level=LV, block=blk)
    L = [g(1, 0, "X1", "BX", T[0]), g(1, 0, "X2", "BX", T[1]), g(2, 0, "Y1", "BY", T[2]), g(3, 1, "Y2", "BY", T[3])]
    bands = lambda **k: [dict(dict(block="BX", level=LV, classes=[A]), **k.get("x", {})), dict(dict(block="BY", level=LV, classes=[A]), **k.get("y", {}))]
    def marks(L, blocks): m, sp = model_with(L, blocks=blocks); b = fixes.Busy(m); return b, {i: [k for k in fixes.marks(b, b.ids[i]) if k != "noroom"] for i in b.ids}
    b, mk = marks(L, bands()); assert mk == {1: ["class"], 2: ["class"], 3: []}, mk   # all of BX meets on day 0: BY's group then clashes, both ways
    assert b.band_clash(b.ids[2], 0, 2, 1, ignore=(2,))[0] == A and b.band_clash(b.ids[2], 0, 2, 1, ignore=(1, 2)) is None
    why = b.clash(b.ids[2], 0, 2, 1, ignore=(2,)); assert why.startswith(f"{A} has the ") and why.endswith(f"and every student of {A} is in one of the two."), why
    assert b.clash(b.ids[3], 0, 2, 1, ignore=(3,)) == why and b.clash(b.ids[3], 2, 2, 1, ignore=(3,)) is None   # where it fits: not onto BX, free elsewhere
    assert marks(L, bands(x=dict(everyone=False)))[1] == {1: [], 2: [], 3: []}   # BX unticked, and BY's other group is elsewhere: nobody is known to be in both
    assert marks(L, bands(x=dict(everyone=False), y=dict(everyone=True)))[1][2] == []
    assert marks(L, [dict(block="Options BX", level=LV, classes=[A]), bands()[1]])[1] == {1: [], 2: [], 3: []}   # a band the setup does not name is not counted
    half = [g(1, 0, "X1", "BX", T[0]), g(4, 3, "X2", "BX", T[1]), g(2, 0, "Y1", "BY", T[2]), g(3, 1, "Y2", "BY", T[3])]
    assert marks(half, bands())[1] == {1: [], 2: [], 3: [], 4: []}   # one group of each: they may be different students
    both = [g(1, 0, "X1", "BX", T[0]), g(1, 0, "X2", "BX", T[1]), g(2, 0, "Y1", "BY", T[2]), g(2, 0, "Y2", "BY", T[3])]
    assert marks(both, bands(x=dict(everyone=False)))[1] == {1: ["class"], 2: ["class"]}   # BY takes everyone: BX's lesson then clashes though BX is an option band
    out = [g(1, 0, "X1", "BX", T[0]), g(1, 0, "X2", "BX", T[1]), lesson(5, 0, 2, 1, [A], "Music", "P1", [T[2]], room="TBC", level=LV)]
    assert marks(out, bands())[1] == {1: [], 5: []}   # a group outside a band (a pull-out) beside a band is left alone
    assert fixes.everyone_bands(dict(checked_setup=dict(blocks=[dict(block="Sec 1 Options"), dict(block="E", everyone=True), dict(block="N", everyone=False), dict(block="M"), dict(block=" ")]))) == {"E", "M"}

@t
def test_outside_the_day():
    m, sp = model_with([lesson(1, 0, RECESS, 1, [A], "Art", ENTIRE, [T[0]], level=LV)]); b = fixes.Busy(m); r = b.ids[1]
    assert b.lesson_time(r, 0, RECESS, 1) and not b.outside(r, 0, RECESS, 1)   # a recess is a break, not the end of the day
    assert b.outside(r, len(DAYS), 2, 1) and b.outside(r, 0, m["NP"], 1) and b.outside(r, 0, m["NP"] - 1, 2) and not b.outside(r, 0, 2, 1)
    grid = {lv: [("." + row[1:]) if d == 1 else row for d, row in enumerate(rows)] for lv, rows in m["grid"].items()}   # no school in period 0 of day 1
    b2 = fixes.Busy(dict(m, grid=grid)); assert b2.outside(r, 1, 0, 1) and not b2.outside(r, 0, 0, 1) or m["grid"][LV][0][0] == "."
    b3 = fixes.Busy(dict(m, keep={DAYS[0]: 3})); assert b3.outside(r, 0, 2, 2) and not b3.outside(r, 0, 2, 1)   # past 'Lessons end by'

@t
def test_a_day_a_teacher_may_take_two_lessons_at_once():
    days = ["Odd Mon", "Odd Fri", "Even Mon", "Even Fri"]; dd = lambda v: spec_mod.double_days(dict(extra_settings=[[spec_mod.DOUBLE, v, ""]]), days)
    assert dd("Even Fri") == {3} and dd("even friday") == {3} and dd("Fri") == {1, 3} and dd("Odd Mon; Even Fri") == {0, 3} and dd("") == set() and dd(None) == set() and dd("Sat, Even") == set()
    assert spec_mod.double_days({}, days) == set() and spec_mod.double_days(dict(extra_settings=[["Lessons end by (Friday)", "Fri", ""]]), days) == set()
    L = [lesson(1, 0, 2, 1, [A], SUBJ, ENTIRE, [T[0]], room="TBC", level=LV), lesson(2, 0, 2, 1, [B], "Art", ENTIRE, [T[0]], room="TBC", level=LV),
         lesson(3, 1, 2, 1, [A], SUBJ, ENTIRE, [T[0]], room="TBC", level=LV), lesson(4, 1, 2, 1, [B], "Art", ENTIRE, [T[0]], room="TBC", level=LV)]
    school = dict(SP["school"], extra_settings=list(SP["school"].get("extra_settings") or []) + [[spec_mod.DOUBLE, DAYS[0], ""]])
    m, sp = model_with(L, school=school); b = fixes.Busy(m); mk = lambda i: [k for k in fixes.marks(b, b.ids[i]) if k != "noroom"]
    assert m["double"] == {0} and mk(1) == [] and mk(2) == [] and mk(3) == ["teacher"] and mk(4) == ["teacher"]   # allowed on the day named, a mistake on the next
    assert b.clash(b.ids[3], 0, 3, 1, ignore=(3,)) is None and b.clash(b.ids[1], 1, 2, 1, ignore=(1,)).startswith(f"{T[0]} is teaching ")
    ch = export.check_model(m)["problems"]
    assert sum(x.startswith("Teacher in two lessons (allowed that day): ") for x in ch) == 1 and sum(x.startswith("Teacher double-booked: ") for x in ch) == 1, ch
    allowed = next(x for x in ch if x.startswith("Teacher in two lessons")); assert verify.crit_of(allowed) == "" and verify.crit_of(next(x for x in ch if x.startswith("Teacher double"))) == "teacher"
    m0, _ = model_with(L); assert m0["double"] == set() and sum(x.startswith("Teacher double-booked: ") for x in export.check_model(m0)["problems"]) == 2

# ----------------------------------------------------------------------------------------------- the trade
SUBJ_T = "Maths"; KA, KB = f"C:{A}:{SUBJ_T}", f"C:{B}:{SUBJ_T}"; NA, NB = f"{SUBJ_T} for {A}", f"{SUBJ_T} for {B}"
def trade_lessons(**by):
    """three lessons of A (ids 1 to 3, teacher T[0]) and three of B (ids 4 to 6, teacher T[1]), each pair at the same day and period"""
    return [lesson(i + (0 if c == A else 3), d, 2, 1, [c], SUBJ_T, ENTIRE, list(by.get(c, [T[0] if c == A else T[1]])), level=LV) for c in (A, B) for d, i in ((0, 1), (1, 2), (2, 3))]
def trade(**kw): return dict(dict(kind="trade", a=KA, b=KB, x=T[0], y=T[1]), **kw)

@t
def trade_applies():
    L = trade_lessons(); before = copy.deepcopy(L); touched, was = set(), []
    text = fixes.apply_one(L, trade(), SP, DAYS, touched=touched, was=was)
    assert text == f"{T[0]} and {T[1]} traded: {T[0]} now teaches {NB}, {T[1]} {NA}." and verify._name(fixes._key(KA)) == NA
    assert all(x["teachers"] == ([T[1]] if x["classes"] == [A] else [T[0]]) for x in L) and touched == {1, 2, 3, 4, 5, 6} and was == before

@t
def trade_end_state():
    m, sp = model_with(trade_lessons()); assert fixes.judge(m, sp, DAYS, trade()) == dict(state="ok", why="", must=[], prefer=[])
    import helper
    for one, two in (((KA, T[1]), (KB, T[0])), ((KB, T[0]), (KA, T[1]))):   # either teacher fix alone puts a teacher in two classes at once
        c = helper.chain(m, sp, DAYS, [dict(kind="teacher", key=k, teachers=[v]) for k, v in (one, two)]); assert c["state"] == "no", c["state"]

@t
def trade_clash():
    L = trade_lessons() + [lesson(7, 1, 2, 1, [C3], "Art", ENTIRE, [T[1]], level=LV)]; L[4]["d"] = 3   # B's second lesson is elsewhere, T[1] is with C3 when A meets
    m, sp = model_with(L); j = fixes.judge(m, sp, DAYS, trade())
    assert j["state"] == "no" and j["why"] == f"{T[1]} is teaching Art for {C3} then.", j

@t
def trade_partial():
    L = trade_lessons(); L[2]["teachers"] = [T[3]]; touched = set()
    fixes.apply_one(L, trade(), SP, DAYS, touched=touched)
    assert L[2]["teachers"] == [T[3]] and touched == {1, 2, 4, 5, 6} and L[0]["teachers"] == [T[1]]

@t
def trade_two_teachers():
    L = trade_lessons(); L[0]["teachers"] = [T[0], T[4]]; fixes.apply_one(L, trade(), SP, DAYS)
    assert L[0]["teachers"] == [T[1], T[4]] and L[3]["teachers"] == [T[0]]

@t
def trade_refused():
    L = trade_lessons(); L[3]["teachers"] = [T[1], T[0]]   # B's first lesson has both: T[0] already teaches B
    L2 = trade_lessons(); L2[0]["teachers"] = [T[0], T[1]]   # A's first lesson has both: T[1] already teaches A
    L3 = trade_lessons()
    cases = [(L3, trade(b=KA), "That changes nothing."), (L3, trade(y=T[0]), "That changes nothing."), (L3, trade(x=T[2]), f"{T[2]} does not teach {NA}."),
             (L2, trade(), f"{T[1]} already teaches {NA}."), (L, trade(), f"{T[0]} already teaches {NB}."),
             (L3, trade(y="Not A Teacher"), "Not A Teacher is not on the setup's list of teachers."), (L3, trade(x="No One", y="Not A Teacher"), "No One, Not A Teacher are not on the setup's list of teachers."),
             (L3, trade(b=f"C:{B}:Nothing"), f"There is no lesson of Nothing for {B} on the timetable."), (L3, trade(a=f"C:{A}:Nothing"), f"There is no lesson of Nothing for {A} on the timetable.")]
    for lessons, f, say in cases:
        before = copy.deepcopy(lessons)
        try: fixes.apply_one(lessons, f, SP, DAYS); assert False, f
        except ValueError as e: assert str(e) == say, (str(e), say)
        assert lessons == before   # nothing changed
        m, sp = model_with(lessons); assert fixes.judge(m, sp, DAYS, f) == dict(state="na", why=say, must=[], prefer=[]), f
    assert fixes.judge(*model_with(L3), DAYS, dict(kind="trade", a=KA, b=KB, x=T[0]))["state"] == "na"   # incomplete

@t
def trade_load():
    teachers = [dict(x, allowance=2) if x["name"] == T[5] else x for x in SP["teachers"]]
    L = trade_lessons()[:3] + [lesson(4, 3, 2, 1, [B], SUBJ_T, ENTIRE, [T[5]], level=LV), lesson(5, 4, 2, 1, [B], SUBJ_T, ENTIRE, [T[5]], level=LV)]   # T[5] has 2 periods, about to take A's 3
    m, sp = model_with(L, teachers=teachers); j = fixes.judge(m, sp, DAYS, trade(y=T[5]))
    assert j["state"] == "prefer" and j["why"] == f"{T[5]} would have 3 periods, 1 over the allowance.", j

@t
def trade_pool():
    L = trade_lessons(); pool = [L.pop(0)]; touched = set(); m, sp = model_with(L)   # lesson 1 of A waits in the pool
    assert fixes.judge(m, sp, DAYS, trade(), pool=copy.deepcopy(pool)) == dict(state="ok", why="", must=[], prefer=[])
    fixes.apply_one(L, trade(), SP, DAYS, touched=touched, pool=pool)
    assert pool[0]["teachers"] == [T[1]] and touched == {1, 2, 3, 4, 5, 6} and all(x["teachers"] == ([T[1]] if x["classes"] == [A] else [T[0]]) for x in L)

@t
def a_teacher_on_another_group_of_the_same_lesson_is_not_free():
    sp, L = one_block(); names = [x["name"] for x in SP["teachers"]]; ta, tb, tc = names[0], names[1], names[2]
    L[0]["teachers"], L[1]["teachers"], L[2]["teachers"] = [ta], [tb], []   # one lesson (id 7), three groups at the same time
    L.append(lesson(8, 1, 0, 2, L[0]["classes"], L[0]["subject"], L[0]["group"], [ta], level=L[0]["level"], block=L[0]["block"]))   # the first group's other lesson
    m, sp = model_with(L); out = fixes.choices(m, sp, DAYS, 7, L[0]["group"]); T = {x["name"]: x for x in out["teachers"]}
    assert out["n_lessons"] == 2
    assert T[tb]["free"] is False and L[1]["group"] in T[tb]["doing"], T[tb]   # on another group of this very lesson: not free then
    assert T[ta]["free"] is True and T[ta]["doing"] == ""                      # the row's own teacher is not busy with the row's own lessons
    assert T[tc]["free"] is True                                                # on no lesson at all
    L2 = [dict(x) for x in L]; L2[1]["teachers"] = [ta, tb]                     # the row's own teacher also on the other group: busy there too
    m2, sp2 = model_with(L2); T2 = {x["name"]: x for x in fixes.choices(m2, sp2, DAYS, 7, L2[0]["group"])["teachers"]}
    assert T2[ta]["free"] is False and L2[1]["group"] in T2[ta]["doing"]
@t
def a_move_onto_a_teacher_only_period_is_no_and_can_be_forced():
    tp = TEACHERS[0]; lv = ROW["level"]; school = dict(SP["school"], start_time="07:40", period_minutes=20)   # periods 1 to 3 of Monday are 8.00 to 9.00
    staff = [dict(_id="z1", name="Staff meeting", all=False, depts=[], teachers=[tp], week="Both", days=["Mon"], times=["08:00", "09:00"], place="Hall")]
    over = dict(school=school, staff_periods=staff, rules=spec_mod.rules_with_staff(dict(SP, school=school, staff_periods=staff, rules=[])))
    why = f"{tp} has Staff meeting then (Mon 8.00 to 9.00)."
    L = [lesson(1, 1, 2, 2, [CLS], SUBJ, ENTIRE, [tp], level=lv), lesson(2, 0, 1, 1, [CLS], "Art", ENTIRE, [tp], level=lv), lesson(3, 2, 6, 1, [CLS], SUBJ, ENTIRE, [TEACHER], level=lv)]
    m, sp = model_with(L, **over); pool = [lesson(5, 3, 2, 2, [CLS], "Music", ENTIRE, [tp], level=lv)]
    j = lambda **f: fixes.judge(m, sp, DAYS, f, pool=pool)
    for r in (j(kind="move", id=1, d=0, p=2), j(kind="place", id=5, d=0, p=2), j(kind="add", key=KEY, d=0, p=3, n=1, room="")):
        assert r["state"] == "no" and r["why"] == why and r["must"] == [r["why"]], r
    m3, sp3 = model_with([lesson(3, 0, 2, 1, [CLS], SUBJ, ENTIRE, [TEACHER], level=lv)], **over)
    r = fixes.judge(m3, sp3, DAYS, dict(kind="teacher", key=KEY, teachers=[tp])); assert r["state"] == "no" and r["why"] == why and r["must"] == [why], r   # the lesson given to the teacher
    r = j(kind="move", id=2, d=0, p=3); assert r["state"] == "ok", r   # already inside the period, elsewhere inside it: not broken anew
    S = fixes.slots(m, sp, DAYS, 1)
    assert at(S, 0, 2)["state"] == "no" and at(S, 0, 2)["why"] == why and not [s for s in S if s["d"] == 0 and s["p"] <= 3 and s["state"] == "ok"]


print(f"{n} checks passed")

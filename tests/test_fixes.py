"""Plain-assert tests for fixes applied to the lessons of a draft: .venv/bin/python tests/test_fixes.py"""
import collections, copy, os, random, subprocess, sys, tempfile, time
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, ROOT)
import fixes  # noqa: E402
from ttgen import export, reader, template, verify  # noqa: E402
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
    assert at(S, 2, 2) == dict(d=2, p=2, state="ok", why="", swap=7, also=[]) and at(S, 1, 2) == dict(d=1, p=2, state="ok", why="", swap=None, also=[])
    assert at(S, 3, 5)["state"] == "na" and at(S, 3, 5)["why"] == "Another lesson is there." and at(S, 3, 6)["why"] == "Another lesson is there."
    assert at(S, 4, 2)["swap"] == 9 and at(S, 4, 2)["also"] == [f"This also moves Assembly talk for {A}, {B} to {DAYS[0]} period 2."] and at(S, 4, 2)["state"] == "ok"
    assert at(S, 0, RECESS)["state"] == "na" and at(S, 0, NP - 1)["why"] == "That is outside the day."
    sp0, Bk = one_block(); cls = Bk[0]["classes"]; assert len(cls) == 3 and all(x["classes"] == cls for x in Bk)
    busy_teacher = Bk[1]["teachers"][0]
    L = Bk + [lesson(30, 1, 5, 3, [cls[1]], SUBJ, ENTIRE, [T[-1]], level=LV), lesson(31, 2, 5, 2, [D], SUBJ, ENTIRE, [busy_teacher], level=LV),
              lesson(32, 3, 5, 2, [cls[2]], SUBJ, ENTIRE, [T[-1]], level=LV)]
    m, sp = model_with(L); S = fixes.slots(m, sp, DAYS, 7)
    assert at(S, 4, 5)["state"] == "ok" and at(S, 4, 5)["swap"] is None
    assert at(S, 1, 5)["state"] == "na" and at(S, 2, 5) == dict(d=2, p=5, state="no", why=f"{busy_teacher} is teaching {SUBJ} for {D} then.", swap=None, also=[])
    assert at(S, 3, 5)["swap"] == 32 and at(S, 3, 5)["state"] == "na"   # a single class's lesson never swaps into a block's slot
    r = fixes.judge(m, sp, DAYS, dict(kind="move", id=7, d=1, p=6)); assert r["state"] == "no" and r["why"].startswith(f"{cls[1]} has "), r
    ok = [s for s in S if s["state"] == "ok"]; assert ok and all(not [x for x in L if x["id"] != 7 and x["d"] == s["d"] and set(x["classes"]) & set(cls) and x["p"] < s["p"] + 2 and s["p"] < x["p"] + x["n"]] for s in ok)

@t
def teacher_room_add_delete_options():
    P = verify.planned_rows(SP)[("C", CLS, SUBJ)]["periods"]; can = [x["name"] for x in SP["teachers"] if any(c.get("subject") == SUBJ for c in x.get("can_teach") or []) and x["name"] not in TEACHERS]
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
    assert fixes.can_delete(m, sp, DAYS, 1) == dict(state="no", why=f"That would leave {SUBJ} for {CLS} with {have - 2} periods; step 3 plans {P}.")
    m, sp = model_with(L + [lesson(3, 4, 7, 1, [CLS], SUBJ, ENTIRE, TEACHERS, level=LV), lesson(4, 4, 8, 1, [CLS], "Other", ENTIRE, TEACHERS, level=LV)])
    assert not [x for x in fixes.short(m, sp) if x["key"] == KEY] and fixes.can_delete(m, sp, DAYS, 4) == dict(state="ok", why="")
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

print(f"{n} checks passed")

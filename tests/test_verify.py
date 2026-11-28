"""Plain-assert tests for checking a timetable against the setup: .venv/bin/python tests/test_verify.py"""
import copy, os, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, ROOT)
from ttgen import verify, export, reader, template  # noqa: E402
from ttgen.samples import primary  # noqa: E402
import openpyxl  # noqa: E402
n = 0
def t(f): global n; f(); n += 1

def model_for(sp, placed):   # a model from hand-placed lessons: placed = [(day index, p, n, classes, subject, group, teachers, room)]
    sp = copy.deepcopy(sp); reader.derive(sp); days = list(sp["day_structure"][sp["school"]["levels"][0]].keys())
    L = [dict(id=i + 1, d=d, p=p, n=n_, level=sp["classes"][0]["level"] if cls else "", block="", classes=cls, subject=s, group=g, teachers=tt, room=r, ext=False, rain="")
         for i, (d, p, n_, cls, s, g, tt, r) in enumerate(placed)]
    m = export._model(sp, days, L); m.setdefault("checked_setup", sp); return m   # the derived setup, as the app passes it

@t
def deployment_finds_teacher_periods_missing_and_extra():
    sp = primary(); row = next(x for x in sp["lessons"] if not x.get("block")); cls, subj = row["classes"][0], row["subject"]
    reader.derive(sp); want = row["periods"]
    m = model_for(sp, [(0, 0, want, [cls], subj, "Entire Class", ["Nobody"], "")])
    ws = {w["key"]: w for w in verify.deployment(m, sp)}
    k = f"dep:C:{cls}:{subj}:teachers"; assert k in ws and ws[k]["sides"]["step5"] == row["teachers"][0]
    assert (ws[k]["ops"] == [["set", "lessons", row["_id"], "teachers", ["Nobody"]]]) if row.get("_id") else ws[k]["ops"] is None
    assert ws[k]["text"] == f"{subj} for {cls} is taught by Nobody on the timetable; step 5 says {row['teachers'][0]}." and ws[k]["group"] == cls
    assert ws[k]["where"] == dict(cls=cls, day=m["days"][0], period=0, id=1, row="Entire Class")
    assert all(w["kind"] == "deployment" for w in ws.values()) and sum(1 for w in ws.values() if w["key"].endswith(":missing")) == len(verify.planned_rows(sp)) - 1
    m2 = model_for(sp, [(0, 0, want - 1, [cls], subj, "Entire Class", row["teachers"], ""), (1, 0, 1, [cls], "Nothing", "Entire Class", row["teachers"], "")])
    ws = {w["key"]: w for w in verify.deployment(m2, sp)}
    assert f"dep:C:{cls}:{subj}:periods" in ws and f"dep:C:{cls}:Nothing:extra" in ws and ws[f"dep:C:{cls}:Nothing:extra"]["ops"] is None
    assert ws[f"dep:C:{cls}:{subj}:periods"]["text"] == f"{subj} for {cls}: {want - 1} periods timetabled, {want} on step 3."

@t
def a_block_lesson_counts_once_per_group():
    sp = primary(); b = next(x for x in sp["lessons"] if x.get("block")); reader.derive(sp)
    rows = [(0, 0, b["periods"], b["classes"], b["subject"], b["code"], b["teachers"], "")] * 2   # two ids; then made one id, two rows
    m = model_for(sp, rows); m["lessons"][1]["id"] = 1
    assert not any(w["key"] == f"dep:G:{b['code']}:periods" for w in verify.deployment(m, sp))
    assert verify.placed(m)[("G", b["code"])]["periods"] == b["periods"]

@t
def a_venue_of_the_wrong_kind_is_found():
    sp = primary(); reader.derive(sp)
    row = next(x for x in sp["lessons"] if not x.get("block") and x.get("room_kind") and any(v.get("kind") != x["room_kind"] for v in sp["venues"])); cls = row["classes"][0]
    other = next(v for v in sp["venues"] if v.get("kind") != row["room_kind"])
    m = model_for(sp, [(0, 0, row["periods"], [cls], row["subject"], "Entire Class", row["teachers"], other["room"])])
    ws = {w["key"]: w for w in verify.deployment(m, sp)}
    k = f"dep:C:{cls}:{row['subject']}:venue"; assert k in ws and ws[k]["ops"] is None
    assert ws[k]["text"] == f"{row['subject']} for {cls} is in {other['room']} ({other['kind']}); step 3 asks for {row['room_kind']}."

@t
def model_from_files_takes_a_given_setup():
    with tempfile.TemporaryDirectory() as d:
        sp = primary(); setup = os.path.join(d, "s.xlsx"); template.write_template(sp, setup)
        ds = sp["day_structure"]; lv = sp["school"]["levels"][0]; day = next(iter(ds[lv])); cls = next(c["class"] for c in sp["classes"] if c["level"] == lv)
        x = next(x for x in sp["lessons"] if cls in x["classes"] and not x.get("block"))
        wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Lessons"
        ws.append(["Lesson ID", "Day", "Start period", "End period", "Periods", "Starts", "Ends", "Level", "Block", "Classes", "Subject", "Group", "Teachers", "Room", "After school", "Rain room"])
        p0 = ds[lv][day].index("L"); ws.append([1, day, p0, p0, 1, "", "", lv, "", cls, x["subject"], "Entire Class", ", ".join(x["teachers"]), "", "", ""])
        tt = os.path.join(d, "timetable.xlsx"); wb.save(tt)
        other = copy.deepcopy(sp); other["school"]["name"] = "Other School"
        m = export.model_from_files(setup, tt, spec=other)
        assert m["school"]["name"] == "Other School" and m["checked_setup"]["school"]["name"] == "Other School" and other["school"]["name"] == "Other School"
        assert m["checked_setup"]["lessons"][0].get("periods") is not None   # derived
        m0 = export.model_from_files(setup, tt); assert m0["school"]["name"] != "Other School" and m0["checked_setup"]["school"]["name"] == m0["school"]["name"]
        assert export.model_from_files(None, tt, spec=other)["school"]["name"] == "Other School"   # no setup file needed

@t
def clashes_drop_the_planned_lines_and_name_the_group():
    sp = primary(); c1, c2 = sp["classes"][0]["class"], sp["classes"][1]["class"]
    m = model_for(sp, [(0, 0, 2, [c1], "English Language", "Entire Class", ["Ms X"], ""), (0, 1, 1, [c2], "Mathematics", "Entire Class", ["Ms X"], "")])
    assert any(p.endswith("planned.") for p in m["checks"]["problems"])
    ws = verify.clashes(m); assert any(w["group"] == "Ms X" and w["key"].startswith("clash:Teacher double-booked") and w["kind"] == "clash" and w["strength"] == "Must" for w in ws)
    assert not any(w["text"].endswith("planned.") for w in ws)

@t
def a_teacher_or_class_clash_says_whose_week_to_open():
    sp = primary(); c1, c2 = sp["classes"][0]["class"], sp["classes"][1]["class"]
    m = model_for(sp, [(0, 0, 1, [c1], "English Language", "Entire Class", ["Ms X"], ""), (0, 0, 1, [c2], "Mathematics", "Entire Class", ["Ms X"], ""),
                       (1, 0, 1, [c1], "Art", "Entire Class", ["Mr Y"], ""), (1, 0, 1, [c1], "Music", "Entire Class", ["Mr Z"], "")])
    ws = verify.clashes(m)
    t = [w for w in ws if w["text"].startswith("Teacher double-booked: Ms X on ")]; k = [w for w in ws if w["text"].startswith(f"Class clash: {c1} on ")]
    assert t and all(w["where"] == dict(teacher="Ms X") for w in t), t
    assert k and all(w["where"] == dict(cls=c1) for w in k), k
    assert all(w["where"] is None for w in ws if not w["text"].startswith(("Teacher double-booked: ", "Class clash: ")) and w["crit"] != "break"), ws   # a lesson in a break has its own place

@t
def ops_use_the_row_ids():
    import sync
    sp = primary(); sync.ensure_ids(sp); reader.derive(sp)
    rows = [x for x in sp["lessons"] if not x.get("block")]; row, gone = rows[0], rows[1]; cls = row["classes"][0]
    assert row.get("_id") and gone.get("_id") and (gone["classes"][0], gone["subject"]) != (cls, row["subject"])
    m = model_for(sp, [(0, 0, row["periods"], [cls], row["subject"], "Entire Class", ["Nobody"], "")])
    ws = {w["key"]: w for w in verify.deployment(m, sp)}
    assert ws[f"dep:C:{cls}:{row['subject']}:teachers"]["ops"] == [["set", "lessons", row["_id"], "teachers", ["Nobody"]]]
    miss = ws[f"dep:C:{gone['classes'][0]}:{gone['subject']}:missing"]["ops"]
    assert miss == [["del", "lessons", gone["_id"]]]

@t
def ops_are_left_out_when_a_row_covers_several_classes():
    import sync
    sp = primary(); row = next(x for x in sp["lessons"] if not x.get("block")); c1 = row["classes"][0]
    c2 = next(c["class"] for c in sp["classes"] if c["class"] != c1 and c["level"] == row["level"]); row["classes"] = [c1, c2]
    sync.ensure_ids(sp); reader.derive(sp)
    m = model_for(sp, [(0, 0, row["periods"], [c1], row["subject"], "Entire Class", ["Nobody"], "")])
    ws = {w["key"]: w for w in verify.deployment(m, sp)}
    a, b = ws[f"dep:C:{c1}:{row['subject']}:teachers"], ws[f"dep:C:{c2}:{row['subject']}:missing"]
    assert a["ops"] is None and b["ops"] is None

@t
def a_teacher_difference_on_a_staffed_lesson_marks_it_by_hand():
    import sync
    sp = primary(); rows = [x for x in sp["lessons"] if not x.get("block") and len(x["classes"]) == 1 and x.get("periods")]
    row, other = rows[0], next(x for x in rows if x["subject"] != rows[0]["subject"])
    sp["school"]["parents_subjects"] = [row["subject"]]; sync.ensure_ids(sp); reader.derive(sp)
    m = model_for(sp, [(0, 0, row["periods"], row["classes"], row["subject"], "Entire Class", ["Nobody"], ""), (1, 0, other["periods"], other["classes"], other["subject"], "Entire Class", ["Nobody"], "")])
    ws = {w["key"]: w for w in verify.deployment(m, sp)}
    ops = ws[f"dep:C:{row['classes'][0]}:{row['subject']}:teachers"]["ops"]
    assert ops == [["set", "lessons", row["_id"], "teachers", ["Nobody"]], ["set", "lessons", row["_id"], "by_hand", True]], ops   # the teachers first, then the mark
    assert ws[f"dep:C:{other['classes'][0]}:{other['subject']}:teachers"]["ops"] == [["set", "lessons", other["_id"], "teachers", ["Nobody"]]]   # an ordinary row: one op
    sp["school"]["parents_subjects"] = []; m = model_for(sp, [(0, 0, row["periods"], row["classes"], row["subject"], "Entire Class", ["Nobody"], "")])
    assert {w["key"]: w for w in verify.deployment(m, sp)}[f"dep:C:{row['classes'][0]}:{row['subject']}:teachers"]["ops"] == [["set", "lessons", row["_id"], "teachers", ["Nobody"]]]   # the rule off: as today
    sp["school"]["parents_subjects"] = [row["subject"]]; c2 = next(c["class"] for c in sp["classes"] if c["class"] != row["classes"][0] and c["level"] == row["level"])
    shared = copy.deepcopy(sp); r2 = next(x for x in shared["lessons"] if x["_id"] == row["_id"]); r2["classes"] = [row["classes"][0], c2]
    m = model_for(shared, [(0, 0, row["periods"], [row["classes"][0]], row["subject"], "Entire Class", ["Nobody"], "")])
    assert {w["key"]: w for w in verify.deployment(m, shared)}[f"dep:C:{row['classes'][0]}:{row['subject']}:teachers"]["ops"] is None   # a row of two classes: no op, staffed or not

@t
def clashes_leave_out_the_choice_problems():
    m = model_for(primary(), [(0, 0, 1, [primary()["classes"][0]["class"]], "English Language", "Entire Class", ["Ms X"], "")])
    m["checks"]["problems"] = list(m["checks"]["problems"]) + ["A second choice was used out of order."]; m["choice_problems"] = ["A second choice was used out of order."]
    assert not any("second choice" in w["text"] for w in verify.clashes(m)) and verify.clashes(m)

@t
def an_extra_group_row_carries_its_code():
    import sync
    sp = primary(); sync.ensure_ids(sp); cls = sp["classes"][0]["class"]; subj = sp["subjects"][0]["subject"]; reader.derive(sp)
    m = model_for(sp, [(0, 0, 1, [cls], subj, "ZZ9", ["Ms X"], "")])
    ws = {w["key"]: w for w in verify.deployment(m, sp)}
    op = ws["dep:G:ZZ9:extra"]["ops"][0]; assert op[2]["code_override"] == "ZZ9" and op[2]["subject"] == subj and op[2]["classes"] == [cls]

def rule(scope, target, kind, a=None, b=None, day="All", **kw):
    r = dict(dict(scope=scope, target=target, rule=kind, week="Both", day=day, strength="Must"), **kw)
    if a is not None: r["from"] = a
    if b is not None: r["to"] = b
    return r

def run(sp, rows, placed):
    sp = copy.deepcopy(sp); sp["rules"] = rows; m = model_for(sp, placed); return verify.rules(m, m["checked_setup"]), m

@t
def not_available_and_keep_free_together():
    sp = primary(); c = sp["classes"][0]["class"]; t = sp["teachers"][0]["name"]
    (ws, nc), m = run(sp, [rule("Teacher", t, "Not available", 0, 1)], [(0, 1, 1, [c], "English", "Entire Class", [t], "")])
    assert len(ws) == 1 and ws[0]["key"] == f"rule:0:{c}|English|0|1" and ws[0]["group"] == t and ws[0]["where"]["period"] == 1 and nc == []
    assert ws[0]["text"] == f"Rule Teacher · {t} · Not available: {t} has English for {c} on {m['days'][0]} period 1 but is not available (periods 0-1)."
    assert run(sp, [rule("Teacher", t, "Not available", 0, 1)], [(0, 3, 1, [c], "English", "Entire Class", [t], "")])[0][0] == []
    d = next(x["dept"] for x in sp["teachers"] if x["name"] == t); lv = sp["classes"][0]["level"]
    for row, who in ((rule("Department", d, "Keep free together", 2, 3), t), (rule("Level", lv, "Keep free together", 2, 3), c)):
        (ws, nc), m = run(sp, [row], [(1, 3, 1, [c], "English", "Entire Class", [t], "")])
        assert len(ws) == 1 and ws[0]["key"] == f"rule:0:{who}|1" and ws[0]["group"] == who
        assert ws[0]["text"].endswith(f"{who} has English on {m['days'][1]} period 3; {row['target']} keeps periods 2-3 free together.")
        assert run(sp, [row], [(1, 5, 1, [c], "English", "Entire Class", [t], "")])[0][0] == []

@t
def keep_free_together_counts_a_second_department():
    sp = primary(); c = sp["classes"][0]["class"]; T = sp["teachers"][0]; t = T["name"]
    d2 = next(d for d in sp["school"]["departments"] if d != T["dept"]); row = rule("Department", d2, "Keep free together", 2, 3)
    L = [(1, 3, 1, [c], "English", "Entire Class", [t], "")]
    assert run(sp, [row], L)[0][0] == []                                    # not in that department: the rule does not see them
    T["dept2"] = d2; (ws, nc), m = run(sp, [row], L)
    assert len(ws) == 1 and ws[0]["group"] == t and ws[0]["text"].endswith(f"{d2} keeps periods 2-3 free together.")
    assert verify.teacher_depts(m, m["checked_setup"])[t] == [T["dept"], d2]

@t
def fixed_at_only_in_not_in_finish_by():
    sp = primary(); c = sp["classes"][0]["class"]; t = sp["teachers"][0]["name"]; L = lambda d, p, n_=1: [(d, p, n_, [c], "English", "Entire Class", [t], "")]
    (ws, _), m = run(sp, [rule("Class", c, "Fixed at", 2, 9, day=None)], L(0, 3))
    assert len(ws) == 1 and ws[0]["key"] == f"rule:0:{c}|English|0|3" and ws[0]["text"].endswith(f"English for {c} starts at period 3 on {m['days'][0]}, not period 2.")
    assert run(sp, [rule("Class", c, "Fixed at", 2)], L(0, 2))[0][0] == []
    (ws, _), m = run(sp, [rule("Class", c, "Not in periods", 2, 3)], L(0, 3))
    assert len(ws) == 1 and ws[0]["text"].endswith(f"English for {c} is in periods 2-3 on {m['days'][0]}.")
    assert run(sp, [rule("Class", c, "Not in periods", 2, 3)], L(0, 4))[0][0] == []
    (ws, _), m = run(sp, [rule("Class", c, "Only in periods", 2, 4)], L(0, 4, 2))
    assert len(ws) == 1 and ws[0]["text"].endswith(f"English for {c} is outside periods 2-4 on {m['days'][0]}.")
    assert run(sp, [rule("Class", c, "Only in periods", 2, 4)], L(0, 3, 2))[0][0] == []
    (ws, _), m = run(sp, [rule("Class", c, "Finish by", None, 3)], L(0, 3, 2))
    assert len(ws) == 1 and ws[0]["text"].endswith(f"English for {c} ends at period 4 on {m['days'][0]}, after period 3.")
    assert run(sp, [rule("Class", c, "Finish by", None, 3)], L(0, 2, 2))[0][0] == []
    (ws, _), _ = run(sp, [rule("Class", c, "Not in periods", 2, 3, strength="Prefer")], L(0, 2))
    assert ws[0]["strength"] == "Prefer" and ws[0]["text"].endswith(" (Prefer)") and ws[0]["kind"] == "rule"
    assert run(sp, [rule("Class", c, "Not in periods", 2, 3, day=m["days"][1])], L(0, 2))[0][0] == []   # another day's rule

@t
def only_these_subjects_and_only_in_venues():
    sp = primary(); c = sp["classes"][0]["class"]; t = sp["teachers"][0]["name"]
    (ws, _), m = run(sp, [rule("School", "Whole school", "Only these subjects", 2, 3, subject="Mathematics")], [(0, 2, 1, [c], "English", "Entire Class", [t], ""), (0, 3, 1, [c], "Mathematics", "Entire Class", [t], "")])
    assert len(ws) == 1 and ws[0]["key"] == f"rule:0:{c}|English|0|2" and ws[0]["text"].endswith(f"English for {c} is in periods 2-3 on {m['days'][0]}, kept for Mathematics.")
    row = rule("School", "Whole school", "Only in venues", 2, 3, venues=["Hall", "ISH"])
    (ws, _), m = run(sp, [row], [(0, 2, 1, [c], "English", "Entire Class", [t], "Lab"), (0, 3, 1, [c], "Art", "Entire Class", [t], "Hall"), (1, 3, 1, [c], "Art", "Entire Class", [t], "TBC"), (1, 5, 1, [c], "Art", "Entire Class", [t], "Lab")])
    assert len(ws) == 1 and ws[0]["group"] == "Lab" and ws[0]["text"].endswith(f"English for {c} is in Lab on {m['days'][0]} period 2; only Hall, ISH are allowed in periods 2-3.")

@t
def rules_that_cannot_be_checked_are_listed():
    sp = primary(); sp["rules"] = [dict(scope="Planet", target="Mars", rule="Not in periods", week="Both", day="All", **{"from": 0, "to": 1}, strength="Must"),
                                   dict(scope="School", target="Whole school", rule="Not in periods", week="Both", day="All", strength="Must"),
                                   dict(scope="School", target="Whole school", rule="In words", text="x", strength="Must")]
    m = model_for(sp, []); ws, nc = verify.rules(m, m["checked_setup"]); assert ws == [] and len(nc) == 2 and "scope" in nc[0] and "From" in nc[1]
    assert verify.rule_periods(dict(), 5) == range(0, 5) and verify.rule_days(["Odd Mon", "Even Mon", "Odd Tue"], dict(week="Odd", day="Mon")) == [0]

@t
def keep_free_together_needs_a_department_or_level_and_subject_cells_are_split():
    sp = primary(); c = sp["classes"][0]["class"]; t = sp["teachers"][0]["name"]; L = [(0, 3, 1, [c], "English", "Entire Class", [t], "")]
    (ws, nc), _ = run(sp, [rule("Teacher", t, "Keep free together", 2, 3)], L)
    assert ws == [] and len(nc) == 1 and nc[0].startswith("Teacher") and "scope" in nc[0]
    (ws, _), _ = run(sp, [rule("Class", c, "Not in periods", 2, 3, subject="Maths, English")], L); assert len(ws) == 1
    (ws, _), _ = run(sp, [rule("Subject", "Maths, English", "Not in periods", 2, 3)], L); assert len(ws) == 1

def with_grid(sp, rows, placed, edit=None):   # like run, but the model can be edited before the rules are checked
    sp = copy.deepcopy(sp); sp["rules"] = rows; m = model_for(sp, placed)
    if edit: edit(m)
    return verify.rules(m, m["checked_setup"]), m

@t
def max_periods_a_day_per_teacher_class_level_and_school():
    sp = primary(); c = sp["classes"][0]["class"]; lv = sp["classes"][0]["level"]; t = sp["teachers"][0]["name"]
    L = [(0, 1, 3, [c], "English", "Entire Class", [t], ""), (0, 6, 1, [c], "Art", "Entire Class", [t], ""), (1, 1, 2, [c], "Art", "Entire Class", [t], "")]
    for row, who in ((rule("Teacher", t, "Max periods a day", number=3), t), (rule("School", "Whole school", "Max periods a day", number=3), t),
                     (rule("Class", c, "Max periods a day", number=3), c), (rule("Level", lv, "Max periods a day", number=3), c)):
        (ws, nc), m = run(sp, [row], L)
        assert len(ws) == 1 and nc == [] and ws[0]["key"] == f"rule:0:{who}|0" and ws[0]["group"] == who and ws[0]["where"] is None
        assert ws[0]["text"].endswith(f"{who} has 4 periods on {m['days'][0]}, more than 3.") and ws[0]["strength"] == "Must"
        assert run(sp, [dict(row, number=4)], L)[0][0] == []
    (ws, nc), _ = run(sp, [rule("Subject", "Art", "Max periods a day", number=1)], L); assert ws == [] and len(nc) == 1 and "scope" in nc[0]
    (ws, nc), _ = run(sp, [rule("School", "Whole school", "Max periods a day")], L); assert ws == [] and len(nc) == 1 and "Number" in nc[0]

@t
def max_periods_in_a_row_counts_unbroken_runs():
    sp = primary(); c = sp["classes"][0]["class"]; t = sp["teachers"][0]["name"]; row = rule("School", "Whole school", "Max periods in a row", number=2)
    (ws, nc), m = run(sp, [row], [(0, 1, 2, [c], "English", "Entire Class", [t], ""), (0, 3, 1, [c], "Art", "Entire Class", [t], "")])
    assert len(ws) == 1 and nc == [] and ws[0]["key"] == f"rule:0:{t}|0" and ws[0]["group"] == t and ws[0]["where"] is None
    assert ws[0]["text"].endswith(f"{t} teaches 3 periods in a row on {m['days'][0]}, more than 2.")
    assert run(sp, [row], [(0, 1, 2, [c], "English", "Entire Class", [t], ""), (0, 4, 1, [c], "Art", "Entire Class", [t], "")])[0][0] == []   # a gap breaks the run
    assert len(run(sp, [rule("Teacher", t, "Max periods in a row", number=2)], [(0, 1, 3, [c], "English", "Entire Class", [t], "")])[0][0]) == 1
    (ws, nc), _ = run(sp, [rule("Class", c, "Max periods in a row", number=2)], [(0, 1, 3, [c], "English", "Entire Class", [t], "")]); assert ws == [] and len(nc) == 1

@t
def at_least_one_recess_needs_a_free_recess_or_a_free_stretch_of_a_window():
    sp = primary(); c = sp["classes"][0]["class"]; t = sp["teachers"][0]["name"]; row = rule("School", "Whole school", "At least one recess a day")
    L = lambda *ps: [(0, p, 1, [c], "English", "Entire Class", [t], "") for p in ps]
    (ws, nc), m = run(sp, [row], L(4, 5, 6))   # the P1-2, P3-4 and P5-6 recesses are all taken
    assert len(ws) == 1 and nc == [] and ws[0]["key"] == f"rule:0:{t}|0" and ws[0]["group"] == t and ws[0]["where"] is None and ws[0]["text"].endswith(f"{t} has no recess on {m['days'][0]}.")
    assert run(sp, [row], L(4, 5))[0][0] == []   # the P5-6 recess is free
    assert len(run(sp, [rule("Teacher", t, "At least one recess a day")], L(4, 5, 6))[0][0]) == 1
    def window(m):
        for lv in m["raw_grid"]: m["raw_grid"][lv][0] = "FLLLWWWWLLLL.."   # the raw day (m["grid"] has W as L)
    assert len(with_grid(sp, [row], L(4, 6), window)[0][0]) == 1   # 5 and 7 are free, but not two in a row (recess length 2)
    assert with_grid(sp, [row], L(4, 5), window)[0][0] == []
    assert with_grid(sp, [row], L(4, 5, 6, 7), window)[0][0] != []
    def none(m):
        for lv in m["raw_grid"]: m["raw_grid"][lv][0] = "FLLLLLLLLLLL.."   # the raw day (m["grid"] has W as L)
    assert [w for w in with_grid(sp, [row], L(4, 5, 6), none)[0][0] if w["key"].endswith("|0")] == []   # no level has a recess that day

@t
def at_most_n_at_once_for_a_subject_or_department_and_rooms_are_left_alone():
    sp = primary(); cs = [x["class"] for x in sp["classes"][:3]]; t = sp["teachers"][0]["name"]
    L = [(0, 3, 1, [c], "English Language", "Entire Class", [t], "") for c in cs]
    (ws, nc), m = run(sp, [rule("Subject", "English Language", "At most N at once", number=2)], L)
    assert len(ws) == 1 and nc == [] and ws[0]["key"] == "rule:0:0|3" and ws[0]["group"] == "English Language" and ws[0]["where"] is None
    assert ws[0]["text"].endswith(f"2+ English Language lessons at once on {m['days'][0]} period 3 (3).")
    assert run(sp, [rule("Subject", "English Language", "At most N at once", number=3)], L)[0][0] == []
    dept = next(s["dept"] for s in sp["subjects"] if s["subject"] == "English Language")
    (ws, _), m = run(sp, [rule("Department", dept, "At most N at once", number=2)], L)
    assert len(ws) == 1 and ws[0]["text"].endswith(f"2+ {dept} lessons at once on {m['days'][0]} period 3 (3).")
    assert run(sp, [rule("Room", "Hall", "At most N at once", number=1)], [(0, 3, 1, [c], "Art", "Entire Class", [t], "Hall") for c in cs])[0] == ([], [])

@t
def same_time_across_classes_names_the_odd_class_out():
    sp = primary(); lv = sp["classes"][0]["level"]; c1, c2, c3 = [x["class"] for x in sp["classes"] if x["level"] == lv][:3]; t = sp["teachers"][0]["name"]
    row = rule("Level", lv, "Same time across classes", subject="Mathematics")
    L = lambda p3: [(0, 2, 1, [c1], "Mathematics", "Entire Class", [t], ""), (0, 2, 1, [c2], "Mathematics", "Entire Class", [t], ""), (0, p3, 1, [c3], "Mathematics", "Entire Class", [t], "")]
    (ws, nc), _ = run(sp, [row], L(3))
    assert len(ws) == 1 and nc == [] and ws[0]["key"] == f"rule:0:{c3}" and ws[0]["group"] == c3 and ws[0]["where"] is None
    assert ws[0]["text"].endswith(f"{c3} has Mathematics at a different time from the other {lv} classes.")
    assert run(sp, [row], L(2))[0][0] == []
    (ws, nc), _ = run(sp, [rule("Level", lv, "Same time across classes")], L(3)); assert ws == [] and len(nc) == 1 and "subject" in nc[0]

@t
def not_on_the_same_day_as_names_the_class():
    sp = primary(); c = sp["classes"][0]["class"]; t = sp["teachers"][0]["name"]; row = rule("Subject", "English", "Not on the same day as", subject="Mathematics")
    L = lambda d2: [(0, 1, 1, [c], "English", "Entire Class", [t], ""), (d2, 3, 1, [c], "Mathematics", "Entire Class", [t], "")]
    (ws, nc), m = run(sp, [row], L(0))
    assert len(ws) == 1 and nc == [] and ws[0]["key"] == f"rule:0:{c}|0" and ws[0]["group"] == c and ws[0]["where"] is None
    assert ws[0]["text"].endswith(f"{c} has English and Mathematics on {m['days'][0]}.")
    assert run(sp, [row], L(1))[0][0] == []
    (ws, nc), _ = run(sp, [rule("Class", c, "Not on the same day as", subject="Mathematics")], L(0)); assert ws == [] and len(nc) == 1 and "scope" in nc[0]

@t
def once_a_day_per_group_finds_a_group_met_twice():
    sp = primary(); c = sp["classes"][0]["class"]; t = sp["teachers"][0]["name"]; row = rule("School", "Whole school", "Once a day per group")
    (ws, nc), m = run(sp, [row], [(0, 1, 1, [c], "English", "Entire Class", [t], ""), (0, 4, 1, [c], "English", "Entire Class", [t], ""), (1, 1, 1, [c], "English", "Entire Class", [t], ""),
                                  (0, 2, 1, [c], "Art", "ZZ1", [t], ""), (0, 5, 1, [c], "Art", "ZZ1", [t], ""), (1, 2, 1, [c], "Art", "ZZ1", [t], "")])
    assert nc == [] and sorted(w["text"].split(": ", 1)[1] for w in ws) == sorted([f"English for {c} meets twice on {m['days'][0]}.", f"group ZZ1 meets twice on {m['days'][0]}."])
    assert all(w["where"] is None and w["strength"] == "Must" for w in ws) and {w["group"] for w in ws} == {c}
    assert len({w["key"] for w in ws}) == 2
    (ws, _), _ = run(sp, [rule("Subject", "Art", "Once a day per group")], [(0, 1, 1, [c], "English", "Entire Class", [t], ""), (0, 4, 1, [c], "English", "Entire Class", [t], "")]); assert ws == []

@t
def after_school_slots_are_named_with_the_rows_strength():
    sp = primary(); c = sp["classes"][0]["class"]; t = sp["teachers"][0]["name"]; lv = sp["classes"][0]["level"]
    L = [(0, 12, 1, [c], "English", "Entire Class", [t], ""), (0, 2, 1, [c], "English", "Entire Class", [t], "")]
    def ext(m): m["lessons"][0]["ext"] = True
    for row in (rule("School", "Whole school", "Avoid after-school slots", strength="Prefer"), rule("Level", lv, "Avoid after-school slots", strength="Prefer"), rule("Class", c, "Avoid after-school slots", strength="Prefer")):
        (ws, nc), m = with_grid(sp, [row], L, ext)
        assert len(ws) == 1 and nc == [] and ws[0]["key"] == f"rule:0:{c}|English|0|12" and ws[0]["group"] == c and ws[0]["strength"] == "Prefer"
        assert ws[0]["where"] == dict(cls=c, day=m["days"][0], period=12, id=1, row="Entire Class") and ws[0]["text"].endswith(f"English for {c} is in an after-school slot on {m['days'][0]}. (Prefer)")
    assert run(sp, [rule("School", "Whole school", "Avoid after-school slots")], L)[0][0] == []
    (ws, nc), _ = with_grid(sp, [rule("Teacher", t, "Avoid after-school slots")], L, ext); assert ws == [] and len(nc) == 1 and "scope" in nc[0]

@t
def max_periods_a_day_counts_parallel_groups_once():
    sp = primary(); c = sp["classes"][0]["class"]; t1, t2 = sp["teachers"][0]["name"], sp["teachers"][1]["name"]; row = rule("Class", c, "Max periods a day", number=3)
    two = [(0, 2, 2, [c], "Art", "ZZ1", [t1], ""), (0, 2, 2, [c], "Music", "ZZ2", [t2], "")]
    assert run(sp, [row], two)[0][0] == []
    (ws, _), m = run(sp, [row], two + [(0, 6, 1, [c], "English", "Entire Class", [t1], "")] + [(0, 8, 1, [c], "English", "Entire Class", [t1], "")])
    assert len(ws) == 1 and ws[0]["text"].endswith(f"{c} has 4 periods on {m['days'][0]}, more than 3.")
    both = [(0, 2, 2, [c], "Art", "ZZ1", [t1], ""), (0, 2, 2, [c], "Art", "ZZ2", [t1], "")]   # a teacher in two lessons at once is one set of periods
    assert run(sp, [rule("Teacher", t1, "Max periods a day", number=2)], both)[0][0] == []

@t
def a_number_that_is_not_whole_is_not_checked_not_a_crash():
    sp = primary(); c = sp["classes"][0]["class"]; t = sp["teachers"][0]["name"]; L = [(0, 1, 3, [c], "English", "Entire Class", [t], "")]
    for kind in ("Max periods a day", "Max periods in a row", "At most N at once"):
        for bad in ("abc", 2.5):
            (ws, nc), _ = run(sp, [rule("School" if kind != "At most N at once" else "Subject", "Whole school" if kind != "At most N at once" else "English", kind, number=bad)], L)
            assert ws == [] and len(nc) == 1 and nc[0].endswith("Number is not a whole number")
        assert len(run(sp, [rule("School", "Whole school", "Max periods a day", number="2.0")], L)[0][0]) == 1   # 2.0 is read as 2

@t
def same_time_skips_a_class_without_the_subject():
    sp = primary(); lv = sp["classes"][0]["level"]; c1, c2, c3 = [x["class"] for x in sp["classes"] if x["level"] == lv][:3]; t = sp["teachers"][0]["name"]
    row = rule("Level", lv, "Same time across classes", subject="Mathematics"); two = [(0, 2, 1, [c], "Mathematics", "Entire Class", [t], "") for c in (c1, c2)]
    assert run(sp, [row], two)[0][0] == []
    (ws, _), _ = run(sp, [row], two + [(0, 3, 1, [c3], "Mathematics", "Entire Class", [t], "")]); assert [w["group"] for w in ws] == [c3]

@t
def typed_rules_against_the_report():
    sp = primary(); sp["rules"] = [dict(scope="School", target="Whole school", rule="In words", text="No PE first", strength="Must", week="Both", day="All"),
                                   dict(scope="School", target="Whole school", rule="In words", text="Art late", strength="Prefer", week="Both", day="All")]
    rep = [dict(no=2, strength="Prefer", applies="Whole school", rule="Art late", result="Partly", how="Two classes."), dict(no=7, strength="Must", applies="", rule="Ghost", result="Met", how="")]
    ws = {w["key"]: w for w in verify.typed(sp, rep)}
    assert set(ws) == {"typed:1:none", "typed:2:Partly", "typed:7:unknown"} and ws["typed:2:Partly"]["strength"] == "Prefer" and "Two classes." in ws["typed:2:Partly"]["text"]
    assert ws["typed:1:none"]["text"] == "T1 has no line in the rule report: No PE first." and ws["typed:1:none"]["strength"] == "Must"
    assert ws["typed:2:Partly"]["text"] == "T2 partly: Art late. The agent says: Two classes."
    assert ws["typed:7:unknown"]["text"] == "The rule report's line 7 (Ghost) is not a typed rule on step 6." and ws["typed:7:unknown"]["strength"] == "Must"
    assert all(w["kind"] == "typed" and w["group"] == "School" for w in ws.values())
    rep2 = [dict(no=1, strength="Must", applies="", rule="x", result="Not met", how=""), dict(no=2, strength="Prefer", applies="", rule="y", result="Met", how="")]
    ws2 = {w["key"]: w for w in verify.typed(sp, rep2)}; assert set(ws2) == {"typed:1:Not met"} and ws2["typed:1:Not met"]["text"] == "T1 not met: No PE first."

@t
def typed_again_after_a_fix_touches_a_lesson_the_rule_is_about():
    sp = primary(); lv = sp["classes"][0]["level"]; c = sp["classes"][0]["class"]; tch = sp["teachers"][0]["name"]
    other = next(x["class"] for x in sp["classes"] if x["level"] != lv)
    words = lambda scope, target, strength="Must": dict(scope=scope, target=target, rule="In words", text="No PE first.", strength=strength, week="Both", day="All")
    line = lambda result, no=1: dict(no=no, strength="Must", applies="", rule="x", result=result, how="")
    def again(rows, rep, touched):
        s2 = copy.deepcopy(sp); s2["rules"] = rows
        m = model_for(s2, [(0, 1, 1, [c], "English", "Entire Class", [tch], ""), (1, 1, 1, [other], "English", "Entire Class", [tch], "")])
        m["lessons"][1]["level"] = next(x["level"] for x in sp["classes"] if x["class"] == other)   # model_for gives every lesson the first class's level
        m["rule_report"] = rep; return verify.typed_again(m, m["checked_setup"], touched)
    ws = again([words("Level", lv)], [line("Met")], {1}); assert len(ws) == 1 and ws[0]["key"] == "typed:1:again" and ws[0]["kind"] == "typed", ws
    assert ws[0]["text"] == "T1 was reported met, but lessons it is about were changed in the app. Check it again: No PE first." and ws[0]["strength"] == "Must", ws
    assert again([words("Level", lv)], [line("Met")], {2}) == [], "a touched lesson of another level"
    assert again([words("Level", lv)], [line("Met")], set()) == [] and again([words("School", "Whole school")], [line("Met")], set()) == []
    ws = again([words("School", "Whole school", "Prefer")], [line("Partly")], {2}); assert [w["key"] for w in ws] == ["typed:1:again"] and ws[0]["strength"] == "Prefer" and "reported partly" in ws[0]["text"], ws
    assert again([words("School", "Whole school")], [line("Not met")], {1}) == [] and again([words("School", "Whole school")], [], {1}) == [] and again([words("School", "Whole school")], [line("")], {1}) == []
    assert again([words("Class", c)], [line("Met")], {1}) != [] and again([words("Class", c)], [line("Met")], {2}) == []
    assert again([words("Level", lv), words("School", "Whole school")], [line("Met", 2)], {1}) != [] and [w["key"] for w in again([words("Level", lv), words("School", "Whole school")], [line("Met", 2)], {1})] == ["typed:2:again"]
    # warnings() puts them after the typed ones and before the choices
    s2 = copy.deepcopy(sp); s2["rules"] = [words("School", "Whole school")]
    m = model_for(s2, [(0, 1, 1, [c], "English", "Entire Class", [tch], "")]); m["rule_report"] = [line("Met")]; m["choice_problems"] = ["Second choice 1: no such rule."]
    kinds = [(w["kind"], w["key"]) for w in verify.warnings(m, touched={1})["warnings"]]
    assert kinds[-2:] == [("typed", "typed:1:again"), ("choice", "choice:Second choice 1: no such rule.")], kinds
    assert ("typed", "typed:1:again") not in [(w["kind"], w["key"]) for w in verify.warnings(m)["warnings"]]

@t
def a_typed_rule_whose_scope_cannot_be_read_is_about_every_lesson():
    sp = primary(); c = sp["classes"][0]["class"]; tch = sp["teachers"][0]["name"]
    gone = dict(id=9, d=0, p=3, n=1, level="", block="", classes=[c], subject="Art", group="Entire Class", teachers=[tch], room="", ext=False, rain="")
    def again(scope, result, touched, was=()):
        s2 = copy.deepcopy(sp); s2["rules"] = [dict(scope=scope, target="Someone", rule="In words", text="No PE first.", strength="Must", week="Both", day="All")]
        m = model_for(s2, [(0, 1, 1, [c], "English", "Entire Class", [tch], "")]); m["rule_report"] = [dict(no=1, strength="Must", applies="", rule="x", result=result, how="")]
        return [w["key"] for w in verify.typed_again(m, m["checked_setup"], touched, was)]
    for scope in ("", None, "Nonsense"):
        assert again(scope, "Met", {1}) == ["typed:1:again"] and again(scope, "Partly", {7}) == ["typed:1:again"] and again(scope, "Met", set(), [gone]) == ["typed:1:again"], scope
        assert again(scope, "Met", set()) == [] and again(scope, "Not met", {1}) == [], scope

@t
def typed_again_judges_the_rows_as_they_were_too():
    sp = primary(); c = sp["classes"][0]["class"]; t1, t2 = sp["teachers"][0]["name"], sp["teachers"][1]["name"]
    words = lambda scope, target: dict(scope=scope, target=target, rule="In words", text="No PE first.", strength="Must", week="Both", day="All")
    line = [dict(no=1, strength="Must", applies="", rule="x", result="Met", how="")]
    def again(row, touched, was):
        s2 = copy.deepcopy(sp); s2["rules"] = [row]; m = model_for(s2, [(0, 1, 1, [c], "English", "Entire Class", [t2], "")]); m["rule_report"] = line
        return [w["key"] for w in verify.typed_again(m, m["checked_setup"], touched, was)]
    gone = dict(id=9, d=0, p=3, n=1, level="", block="", classes=[c], subject="Art", group="Entire Class", teachers=[t1], room="", ext=False, rain="")
    assert again(words("Class", c), set(), [gone]) == ["typed:1:again"]
    assert again(words("Teacher", t1), {1}, [gone]) == ["typed:1:again"] and again(words("Teacher", t1), {1}, []) == []
    assert again(words("Teacher", t1), set(), []) == [] and again(words("Class", c), set(), ()) == [] and again(words("Class", "Nobody"), set(), [gone]) == []
    m = model_for(dict(copy.deepcopy(sp), rules=[words("Class", c)]), [(0, 1, 1, [c], "English", "Entire Class", [t2], "")]); m["rule_report"] = line
    assert [w["key"] for w in verify.warnings(m, touched=(), was=[gone])["warnings"] if w["kind"] == "typed"] == ["typed:1:again"]

@t
def choices_become_warnings():
    ws = verify.choices_(dict(choice_problems=["Second choice 1: no such rule."]))
    assert len(ws) == 1 and ws[0]["kind"] == "choice" and ws[0]["key"] == "choice:Second choice 1: no such rule." and ws[0]["text"] == "Second choice 1: no such rule."

def clash_model():
    sp = primary(); sp["rules"] = [dict(scope="School", target="Whole school", rule="In words", text="No PE first", strength="Must", week="Both", day="All")]
    c1, c2 = [x["class"] for x in sp["classes"]][:2]; tch = sp["teachers"][0]["name"]
    m = model_for(sp, [(0, 0, 1, [c1], "English", "Entire Class", [tch], ""), (0, 0, 1, [c2], "English", "Entire Class", [tch], "")])
    m["rule_report"] = []; m["choice_problems"] = []; return m

@t
def warnings_come_in_kind_order():
    m = clash_model(); r = verify.warnings(m); kinds = [w["kind"] for w in r["warnings"]]
    assert list(r) == ["warnings", "not_checked"] and r["not_checked"] == []
    assert sorted(set(kinds), key=verify.KINDS.index) == ["clash", "deployment", "typed"] and kinds == sorted(kinds, key=verify.KINDS.index)

@t
def check_timetable_prints_and_exits_one_on_a_must():
    import io, contextlib
    from ttgen import __main__ as cli
    with tempfile.TemporaryDirectory() as d:
        sp = primary(); setup = os.path.join(d, "setup.xlsx"); template.write_template(sp, setup)
        ds = sp["day_structure"]; lv = sp["school"]["levels"][0]; day = next(iter(ds[lv])); cls = next(c["class"] for c in sp["classes"] if c["level"] == lv)
        x = next(x for x in sp["lessons"] if cls in x["classes"] and not x.get("block"))
        wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Lessons"
        ws.append(["Lesson ID", "Day", "Start period", "End period", "Periods", "Starts", "Ends", "Level", "Block", "Classes", "Subject", "Group", "Teachers", "Room", "After school", "Rain room"])
        p0 = ds[lv][day].index("L"); ws.append([1, day, p0, p0, 1, "", "", lv, "", cls, x["subject"], "Entire Class", ", ".join(x["teachers"]), "", "", ""])
        tt = os.path.join(d, "timetable.xlsx"); wb.save(tt); out = io.StringIO()
        with contextlib.redirect_stdout(out): code = cli.main(["check-timetable", tt, "--setup", setup])
        text = out.getvalue(); assert code == 1 and "[deployment]" in text and "warnings, 0 critical (" in text, text
        assert text.splitlines()[1].startswith(" - [") and "[critical" not in text
        assert verify.CRIT_WORDS == {"teacher": "Teacher in two places", "class": "Class clash", "room": "Room used twice", "break": "In a break or outside the day", "noteacher": "No teacher"}
        wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Lessons"   # the same lesson with nobody to teach it: a critical mistake
        ws.append(["Lesson ID", "Day", "Start period", "End period", "Periods", "Starts", "Ends", "Level", "Block", "Classes", "Subject", "Group", "Teachers", "Room", "After school", "Rain room"])
        ws.append([1, day, p0, p0, 1, "", "", lv, "", cls, x["subject"], "Entire Class", "", "", "", ""])
        tt2 = os.path.join(d, "timetable2.xlsx"); wb.save(tt2); out = io.StringIO()
        with contextlib.redirect_stdout(out): code = cli.main(["check-timetable", tt2, "--setup", setup])
        text = out.getvalue(); first = text.splitlines()[0]
        assert code == 1 and first.split(" warnings, ")[1].startswith("1 critical"), text
        assert any(l.startswith(" - [critical: No teacher] No teacher: ") for l in text.splitlines()), text

@t
def keys_shared_by_several_hits_are_made_unique_and_stay_stable():
    sp = primary(); m = model_for(sp, []); real = verify.clashes
    try:
        verify.clashes = lambda m_: [verify.warning("rule:1:5A|4|11", "clash", "first"), verify.warning("rule:1:5A|4|11", "clash", "second"), verify.warning("rule:1:5A|4|11", "clash", "third")]
        a = [w["key"] for w in verify.warnings(m, sp)["warnings"] if w["text"] in ("first", "second", "third")]
        b = [w["key"] for w in verify.warnings(m, sp)["warnings"] if w["text"] in ("first", "second", "third")]
    finally: verify.clashes = real
    assert a == ["rule:1:5A|4|11", "rule:1:5A|4|11#2", "rule:1:5A|4|11#3"] and a == b, a

@t
def parallel_group_lessons_in_one_slot_have_their_own_keys():
    sp = primary(); c = sp["classes"][0]["class"]; t = sp["teachers"][0]["name"]
    both = [(0, 12, 1, [c], "English", "ZZ1", [t], ""), (0, 12, 1, [c], "English", "ZZ2", [t], "")]
    def ext(m):
        for x in m["lessons"]: x["ext"] = True
    row = rule("School", "Whole school", "Avoid after-school slots")
    (ws, _), _ = with_grid(sp, [row], both, ext); keys = [w["key"] for w in ws]
    assert keys == [f"rule:0:{c}|ZZ1|0|12", f"rule:0:{c}|ZZ2|0|12"] and not any("#" in k for k in keys), keys
    (ws2, _), _ = with_grid(sp, [row], both[1:], ext); assert [w["key"] for w in ws2] == [keys[1]]

@t
def an_extra_lesson_gives_an_add_op_appended_with_the_class_level():   # finding 1: the add row the step 5 update sends
    sp = primary(); cls = sp["classes"][0]["class"]; lv = sp["classes"][0]["level"]; subj = sp["subjects"][0]["subject"]; t_ = sp["teachers"][0]["name"]; reader.derive(sp)
    m = model_for(sp, [(0, 0, 1, [cls], subj, "Entire Class", [t_], ""), (1, 0, 1, [cls], subj, "Entire Class", [t_], "")])
    m["lessons"] = [x for x in m["lessons"]]; sp2 = copy.deepcopy(sp); sp2["lessons"] = [x for x in sp2["lessons"] if not (cls in x["classes"] and x["subject"] == subj)]
    for x in m["lessons"]: x["level"] = ""   # a workbook without a Level column
    ws = {w["key"]: w for w in verify.deployment(m, sp2)}
    op = ws[f"dep:C:{cls}:{subj}:extra"]["ops"]; assert len(op) == 1 and op[0][:2] == ["add", "lessons"], op
    assert op[0][2] == dict(level=lv, subject=subj, classes=[cls], teachers=[t_]), op[0][2]
    assert op[0][3] == verify.APPEND and op[0][3] != "" and "_id" not in op[0][2]   # appended, not put first; the id is given when it is applied
    import sync
    s3 = copy.deepcopy(sp2); sync.ensure_ids(s3); row = dict(op[0][2], _id=sync.new_id()); sync.apply(s3, [["add", "lessons", row, op[0][3]]])
    assert s3["lessons"][-1]["_id"] == row["_id"]

@t
def once_a_day_allows_the_spread_the_solver_makes():   # finding 2: 7 lessons over 5 days may meet twice on a day
    sp = primary(); c = sp["classes"][0]["class"]; t_ = sp["teachers"][0]["name"]; row = rule("School", "Whole school", "Once a day per group")
    seven = [(d, p, 1, [c], "English", "Entire Class", [t_], "") for d, p in ((0, 1), (0, 4), (1, 1), (1, 4), (2, 1), (3, 1), (4, 1))]
    (ws, nc), m = run(sp, [row], seven); assert ws == [] and nc == [], ws
    (ws, _), m = run(sp, [row], seven[:6] + [(0, 6, 1, [c], "English", "Entire Class", [t_], "")])
    assert len(ws) == 1 and ws[0]["text"].endswith(f"English for {c} meets 3 times on {m['days'][0]}."), [w["text"] for w in ws]

@t
def at_least_one_recess_sees_the_recess_windows_of_the_setup():   # finding 3: W is turned into L on m["grid"]
    sp = primary(); c = sp["classes"][0]["class"]; t_ = sp["teachers"][0]["name"]; row = rule("School", "Whole school", "At least one recess a day")
    for lv in sp["day_structure"]: d0 = next(iter(sp["day_structure"][lv])); sp["day_structure"][lv][d0] = "FLLLWWWWLLLL.."
    L = lambda *ps: [(0, p, 1, [c], "English", "Entire Class", [t_], "") for p in ps]
    (ws, nc), m = run(sp, [row], L(*range(1, 12)))
    assert [w["key"] for w in ws] == [f"rule:0:{t_}|0"] and nc == [], ws
    assert run(sp, [row], L(1, 2, 3, 4, 7, 8, 9, 10, 11))[0][0] == []   # 5 and 6 free: the recess length inside the window

@t
def a_rule_row_with_an_id_keys_its_warnings_by_the_id():   # finding 4
    sp = primary(); c = sp["classes"][0]["class"]; t_ = sp["teachers"][0]["name"]; L = [(0, 3, 1, [c], "English", "Entire Class", [t_], "")]
    other = rule("Class", "Nobody", "Not in periods", 0, 0, _id="r0000000aa")
    (ws, _), _ = run(sp, [other, rule("Class", c, "Not in periods", 2, 3, _id="r0000000bb")], L)
    assert [w["key"] for w in ws] == [f"rule:r0000000bb:{c}|English|0|3"], ws

@t
def a_rule_row_with_bad_periods_is_not_checked_not_a_crash():   # finding 5
    sp = primary(); c = sp["classes"][0]["class"]; t_ = sp["teachers"][0]["name"]; L = [(0, 3, 1, [c], "English", "Entire Class", [t_], "")]
    for kind in ("Not available", "Fixed at", "Finish by", "Not in periods", "Only in periods"):
        for a, b in (("two", 3), (1, "x"), (2.5, 3), (4, 2)):
            r = rule("Teacher" if kind == "Not available" else "Class", t_ if kind == "Not available" else c, kind, a, b)
            (ws, nc), _ = run(sp, [r, rule("Class", c, "Not in periods", 3, 3)], L)
            assert len(ws) == 1 and len(nc) == 1 and ("whole number" in nc[0] or "after its To" in nc[0]), (kind, a, b, nc)
    (ws, nc), _ = run(sp, [rule("Class", c, "Not in periods", "2", "3.0")], L); assert len(ws) == 1 and nc == []   # '2' and 3.0 are whole numbers

@t
def a_special_room_week_row_may_be_in_a_classroom_on_its_other_week():   # finding 6
    from ttgen.samples import secondary
    sp = secondary(); reader.derive(sp)
    row = next(x for x in sp["lessons"] if not x.get("block") and x.get("room_kind") not in (None, "classroom") and len(x["classes"]) == 1); row["room_weeks"] = "Odd"
    cls = row["classes"][0]; room = next(v["room"] for v in sp["venues"] if (v.get("kind") or "classroom") == "classroom")
    days = list(sp["day_structure"][sp["school"]["levels"][0]].keys()); odd, even = days.index(next(d for d in days if d.startswith("Odd"))), days.index(next(d for d in days if d.startswith("Even")))
    for d, bad in ((even, False), (odd, True)):
        m = model_for(sp, [(d, 1, row["periods"], [cls], row["subject"], "Entire Class", row["teachers"], room)])
        assert any(w["key"] == f"dep:C:{cls}:{row['subject']}:venue" for w in verify.deployment(m, sp)) == bad, (d, bad)

@t
def a_missing_auto_coded_block_row_has_no_op_and_an_entire_class_row_has_the_del():   # finding 7
    import sync
    sp = primary(); sync.ensure_ids(sp); reader.derive(sp)
    b = next(x for x in sp["lessons"] if x.get("block") and not x.get("code_override") and len(x["classes"]) == 1) if any(x.get("block") and len(x["classes"]) == 1 for x in sp["lessons"]) else None
    if b is None:   # the sample's block rows cover several classes: make one that covers one
        b = next(x for x in sp["lessons"] if x.get("block")); b["classes"] = b["classes"][:1]; reader.derive(sp)
    e = next(x for x in sp["lessons"] if not x.get("block") and len(x["classes"]) == 1)
    ws = {w["key"]: w for w in verify.deployment(model_for(sp, []), sp)}
    assert ws[f"dep:G:{b['code']}:missing"]["ops"] is None
    assert ws[f"dep:C:{e['classes'][0]}:{e['subject']}:missing"]["ops"] == [["del", "lessons", e["_id"]]]
    b["code_override"] = b["code"]; ws = {w["key"]: w for w in verify.deployment(model_for(sp, []), sp)}
    assert ws[f"dep:G:{b['code']}:missing"]["ops"] == [["del", "lessons", b["_id"]]]

@t
def a_typed_rule_with_an_unclear_result_is_a_warning():   # finding 9
    sp = primary(); sp["rules"] = [dict(scope="School", target="Whole school", rule="In words", text="No PE first", strength="Prefer", week="Both", day="All")]
    for res in ("", "Maybe", None):
        ws = verify.typed(sp, [dict(no=1, strength="Prefer", applies="", rule="x", result=res, how="Not sure.")])
        assert [w["key"] for w in ws] == ["typed:1:unclear"] and ws[0]["strength"] == "Prefer", ws
        assert ws[0]["text"] == "T1: the rule report does not say whether it was met: No PE first. The agent says: Not sure.", ws[0]["text"]
    assert verify.typed(sp, [dict(no=1, result="Met")]) == []

@t
def the_timetable_workbook_is_read_read_only():   # finding 8
    real, seen = export.openpyxl.load_workbook, []
    def spy(*a, **kw): wb = real(*a, **kw); seen.append((kw, wb)); return wb
    with tempfile.TemporaryDirectory() as d:
        sp = primary(); ds = sp["day_structure"]; lv = sp["school"]["levels"][0]; day = next(iter(ds[lv])); cls = next(c["class"] for c in sp["classes"] if c["level"] == lv)
        x = next(x for x in sp["lessons"] if cls in x["classes"] and not x.get("block"))
        wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Lessons"
        ws.append(["Lesson ID", "Day", "Start period", "End period", "Periods", "Starts", "Ends", "Level", "Block", "Classes", "Subject", "Group", "Teachers", "Room", "After school", "Rain room"])
        p0 = ds[lv][day].index("L"); ws.append([1, day, p0, p0, 1, "", "", lv, "", cls, x["subject"], "Entire Class", ", ".join(x["teachers"]), "", "", ""])
        rm = wb.create_sheet("Read me"); rm.append(["Notes"]); rm.append(["A note."]); rm.append([None]); rm.append(["Solver status: OPTIMAL."])
        rr = wb.create_sheet("Rule report"); rr.append(["No.", "Must / Prefer", "Applies to", "Rule", "Result", "How"]); rr.append([1, "Must", "Whole school", "x", "Met", "ok"])
        rc = wb.create_sheet("Recess"); rc.append(["Class", "Day", "Start period", "Periods"]); rc.append([cls, day, 4, 1])
        tt = os.path.join(d, "timetable.xlsx"); wb.save(tt)
        export.openpyxl.load_workbook = spy
        try: m = export.model_from_files(None, tt, spec=sp)
        finally: export.openpyxl.load_workbook = real
        assert seen and all(kw.get("read_only") for kw, _ in seen), seen
        assert len(m["lessons"]) == 1 and "A note." in m["notes"] and m["status"] == "OPTIMAL" and m["rule_report"][0]["result"] == "Met" and m["recess"][cls] == [[0, 4, 1]], (m["notes"], m["status"], m["recess"])

@t
def the_days_come_out_in_calendar_order_whatever_order_the_setup_holds_them_in():   # a setup saved from the browser holds its days alphabetically
    with tempfile.TemporaryDirectory() as d:
        sp = primary(); setup = os.path.join(d, "s.xlsx"); template.write_template(sp, setup)
        ds = sp["day_structure"]; lv = sp["school"]["levels"][0]; want = list(ds[lv]); day = want[0]; cls = next(c["class"] for c in sp["classes"] if c["level"] == lv)
        x = next(x for x in sp["lessons"] if cls in x["classes"] and not x.get("block"))
        wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Lessons"
        ws.append(["Lesson ID", "Day", "Start period", "End period", "Periods", "Starts", "Ends", "Level", "Block", "Classes", "Subject", "Group", "Teachers", "Room", "After school", "Rain room"])
        p0 = ds[lv][day].index("L"); ws.append([1, day, p0, p0, 1, "", "", lv, "", cls, x["subject"], "Entire Class", ", ".join(x["teachers"]), "", "", ""])
        tt = os.path.join(d, "timetable.xlsx"); wb.save(tt)
        mixed = copy.deepcopy(sp); mixed["day_structure"] = {l: {k: v[k] for k in sorted(v)} for l, v in mixed["day_structure"].items()}
        assert list(mixed["day_structure"][lv]) != want                      # alphabetical: Fri, Mon, Thu, Tue, Wed
        m = export.model_from_files(None, tt, spec=mixed)
        assert m["days"] == want, m["days"]                                  # Mon to Fri again
        assert m["days"][m["lessons"][0]["d"]] == day                        # and the lesson is still on its own day

@t
def what_is_critical_and_what_is_not():
    C = verify.crit_of
    assert C("Teacher double-booked: Tan Wei Ming on Odd Mon 8.00-8.40 (periods 1-2).") == "teacher"
    assert C("Class clash: 1A on Odd Mon period 3 (8.40).") == "class" and C("Room over capacity: Lab 1 on Odd Tue period 4 (9.00) (holds 1 at once).") == "room"
    assert C("Art Entire Class sits in a break or outside the day on Odd Mon period 5 (9.20).") == "break"
    assert C("PE Entire Class sits in a class's recess on Odd Mon period 5 (9.20).") == "break"
    assert C("Mathematics G3 1EMP ends after 1.00 on Odd Fri period 16 (1.00) (Settings: Lessons end by).") == "break"
    for text in ("Rain room in use: B4-1 on Odd Mon period 3 (8.40) is the home room of a class at PE, but a lesson is in it.",
                 "3 students have two lessons at the same time, e.g. S1 A.", "group 1EMP: 4 periods timetabled, 6 planned.", ""):
        assert C(text) == "", text

def clash_model(sp, rows, rules=()):
    sp = copy.deepcopy(sp); sp["rules"] = list(rules); m = model_for(sp, rows); m["checks"] = export.check_model(m); return m

@t
def a_teacher_in_two_places_is_critical_and_a_rule_is_not():
    sp = primary(); a, b = sp["classes"][0]["class"], sp["classes"][1]["class"]; t = sp["teachers"][0]["name"]
    (rule_ws, nc), m = run(sp, [rule("Teacher", t, "Not available", 0, 1)], [(0, 1, 1, [a], "English", "Entire Class", [t], ""), (0, 1, 1, [b], "English", "Entire Class", [t], "")])
    m["checks"] = export.check_model(m)
    crit = [w for w in verify.clashes(m) if w["crit"]]
    assert [w["crit"] for w in crit] == ["teacher"] and crit[0]["kind"] == "clash" and crit[0]["text"].startswith("Teacher double-booked: " + t)
    assert rule_ws and all(w["crit"] == "" for w in rule_ws)                # a broken Must rule is a warning

@t
def a_lesson_with_no_teacher_is_critical():
    # a band lesson of two groups, the second with no teacher: one critical mistake, naming that group
    sp = primary(); a, b = sp["classes"][0]["class"], sp["classes"][1]["class"]; t = sp["teachers"][0]["name"]
    m = clash_model(sp, [(1, 4, 2, [a, b], "Music", "XB1", [t], ""), (1, 4, 2, [a, b], "Music", "XB2", [], "")])
    assert m["lessons"][0]["id"] == 1 and m["lessons"][1]["id"] == 2     # model_for gives each row its own id; make them one band
    for x in m["lessons"]: x["id"] = 7
    ws = [w for w in verify.clashes(m) if w["crit"] == "noteacher"]
    assert len(ws) == 1 and ws[0]["key"] == "clash:noteacher:7:XB2" and ws[0]["kind"] == "clash" and ws[0]["strength"] == "Must"
    assert ws[0]["text"] == f"No teacher: group XB2 on {m['days'][1]} period 4." and ws[0]["where"] == dict(cls=a, day=m["days"][1], period=4, id=7, row="XB2") and ws[0]["group"] == a
    whole = clash_model(sp, [(0, 0, 1, [b], "English", "Entire Class", [], "")])
    w = [w for w in verify.clashes(whole) if w["crit"] == "noteacher"]
    assert [x["text"] for x in w] == [f"No teacher: English for {b} on {whole['days'][0]} period 0."] and w[0]["where"] == dict(cls=b, day=whole["days"][0], period=0, id=1, row="Entire Class")

@t
def a_lesson_in_a_break_or_a_recess_has_a_place_for_the_fix_button():
    sp = primary(); a = sp["classes"][0]["class"]; t = sp["teachers"][0]["name"]
    m0 = model_for(copy.deepcopy(sp), [(0, 0, 1, [a], "English", "Entire Class", [t], "")])
    lv = m0["lessons"][0]["level"] if m0["lessons"][0]["level"] in m0["grid"] else m0["class_ix"][a]["level"]
    brk = next(q for q in range(m0["NP"]) if m0["grid"][lv][0][q] not in "LA")        # a break of the level's first day
    free = next(q for q in range(m0["NP"]) if m0["grid"][lv][1][q] in "LA")
    whole = clash_model(sp, [(0, brk, 1, [a], "English", "Entire Class", [t], "")])
    w = [x for x in verify.clashes(whole) if x["crit"] == "break"]
    assert len(w) == 1 and w[0]["where"] and w[0]["where"]["cls"] == a and w[0]["where"]["day"] == whole["days"][0] and w[0]["group"] == a, w
    m = model_for(copy.deepcopy(sp), [(1, free, 1, [a], "Music", "XB1", [t], "")]); m["cgrid"][a] = [list(r) for r in m["grid"][lv]]; m["cgrid"][a][1][free] = "R"       # a group lesson in its class's recess
    m["checks"] = export.check_model(m)
    w = [x for x in verify.clashes(m) if x["crit"] == "break"]
    assert len(w) == 1 and "recess" in w[0]["text"] and w[0]["where"]["cls"] == a and w[0]["where"]["day"] == m["days"][1] and w[0]["group"] == a, w
    assert w[0]["text"] in m["checks"]["problems"] and m["checks"]["where"][w[0]["text"]] == [w[0]["where"]]            # the line itself is as it was; its places are kept in order
    # a teacher clash and a no-teacher warning keep their where
    t2 = clash_model(sp, [(0, 1, 1, [a], "English", "Entire Class", [t], ""), (0, 1, 1, [sp["classes"][1]["class"]], "English", "Entire Class", [t], "")])
    c = [x for x in verify.clashes(t2) if x["crit"] == "teacher"]
    assert len(c) == 1 and c[0]["where"] == dict(teacher=t)
    nt = [x for x in verify.clashes(clash_model(sp, [(0, 1, 1, [a], "English", "Entire Class", [], "")])) if x["crit"] == "noteacher"]
    assert nt[0]["where"]["cls"] == a

@t
def a_room_over_capacity_names_a_lesson_in_it_for_the_fix_button():
    sp = primary(); a, b = sp["classes"][0]["class"], sp["classes"][1]["class"]; t1, t2 = sp["teachers"][0]["name"], sp["teachers"][1]["name"]
    room = next(v["room"] for v in sp["venues"])
    m = clash_model(sp, [(0, 1, 1, [a], "English", "Entire Class", [t1], room), (0, 1, 1, [b], "Music", "Entire Class", [t2], room)])
    w = [x for x in verify.clashes(m) if x["crit"] == "room"]
    assert len(w) == 1 and w[0]["text"].startswith(f"Room over capacity: {room} on "), w
    assert w[0]["where"] == dict(cls=a, day=m["days"][0], period=1, id=1, row="Entire Class") and w[0]["group"] == a, w
    longer = clash_model(sp, [(0, 1, 2, [a], "English", "Entire Class", [t1], room), (0, 2, 1, [b], "Music", "Entire Class", [t2], room)])   # the clash is in period 2 only; the first lesson in the room then is the first row
    w = [x for x in verify.clashes(longer) if x["crit"] == "room"]
    assert len(w) == 1 and w[0]["where"]["cls"] == a and w[0]["where"]["period"] == 1 and w[0]["where"]["id"] == 1, w

@t
def a_lesson_with_no_teacher_has_its_day_period_id_and_row_in_its_place():
    sp = primary(); a = sp["classes"][0]["class"]
    m = clash_model(sp, [(1, 3, 1, [a], "English", "Entire Class", [], "")])
    w = [x for x in verify.clashes(m) if x["crit"] == "noteacher"]
    assert len(w) == 1 and w[0]["where"] == dict(cls=a, day=m["days"][1], period=3, id=1, row="Entire Class") and w[0]["group"] == a, w

@t
def two_lines_that_read_the_same_hand_out_their_places_in_order():
    sp = primary(); a, b = sp["classes"][0]["class"], sp["classes"][1]["class"]; t = sp["teachers"][0]["name"]
    m0 = model_for(copy.deepcopy(sp), [(0, 0, 1, [a], "English", "Entire Class", [t], "")])
    lv = m0["lessons"][0]["level"] if m0["lessons"][0]["level"] in m0["grid"] else m0["class_ix"][a]["level"]
    brk = next(q for q in range(m0["NP"]) if m0["grid"][lv][0][q] not in "LA")
    m = clash_model(sp, [(0, brk, 1, [a], "Music", "XB1", [t], ""), (0, brk, 1, [b], "Music", "XB1", [sp["teachers"][1]["name"]], "")])
    lines = [x for x in m["checks"]["problems"] if "sits in a break" in x]
    assert len(lines) == 2 and lines[0] == lines[1], lines                           # the same words twice, as before
    w = [x for x in verify.clashes(m) if x["crit"] == "break"]
    assert [x["where"]["cls"] for x in w] == [a, b] and [x["group"] for x in w] == [a, b], w

@t
def two_bands_of_one_class_at_once_are_not_a_mistake():
    # two group lessons (two different bands) of one class in the same period, different teachers and rooms: no warning with crit, and no "Class clash" line
    sp = primary(); a = sp["classes"][0]["class"]; t1, t2 = sp["teachers"][0]["name"], sp["teachers"][1]["name"]
    rooms = [v["room"] for v in sp["venues"][:2]]
    m = clash_model(sp, [(2, 2, 1, [a], "Music", "XB1", [t1], rooms[0]), (2, 2, 1, [a], "Art", "XC1", [t2], rooms[1])])
    assert not any(w["crit"] for w in verify.clashes(m)) and not any(x.startswith("Class clash") for x in m["checks"]["problems"])
    whole = clash_model(sp, [(2, 2, 1, [a], "Music", "XB1", [t1], rooms[0]), (2, 2, 1, [a], "English", "Entire Class", [t2], rooms[1])])
    assert [w["crit"] for w in verify.clashes(whole) if w["crit"]] == ["class"]            # a whole-class lesson with another is one

@t
def every_teacher_clash_is_listed_past_thirty():
    # one teacher on two classes' lessons in each of 35 different periods (every second period of 5 days), so none join up
    sp = primary(); a, b = sp["classes"][0]["class"], sp["classes"][1]["class"]; t = sp["teachers"][0]["name"]
    slots = [(d, p) for d in range(5) for p in range(0, 14, 2)]; assert len(slots) == 35
    rows = [(d, p, 1, [c], "English", "Entire Class", [t], "") for d, p in slots for c in (a, b)]
    crit = lambda r: [w for w in verify.clashes(clash_model(sp, r)) if w["crit"] == "teacher"]
    assert len(crit(rows)) == 35 and len({w["key"] for w in crit(rows)}) == 35
    assert len(crit(rows[:-1])) == 34

@t
def a_lesson_during_a_teacher_only_period_is_one_must_warning():
    sp = primary(); row = next(x for x in sp["lessons"] if not x.get("block")); cls, subj, who = row["classes"][0], row["subject"], row["teachers"][0]
    sp["school"].update(start_time="07:40", period_minutes=20)
    sp["staff_periods"] = [dict(_id="z1", name="Staff meeting", all=False, depts=[], teachers=[who], week="Both", days=["Mon"], times=["08:00", "09:00"], place="Hall")]
    m = model_for(sp, [(0, 1, 2, [cls], subj, "Entire Class", [who], "")]); day = m["days"][0]
    ws = [w for w in verify.rules(m, m["checked_setup"])[0] if "staff" in w]
    assert len(ws) == 1 and ws[0]["kind"] == "rule" and ws[0]["strength"] == "Must" and ws[0]["crit"] == "" and ws[0]["group"] == who
    assert ws[0]["text"] == f"{who} has {subj} for {cls} on {day} period 1 during Staff meeting (8.00 to 9.00)."
    assert ws[0]["staff"] == f"{who} has Staff meeting then (Mon 8.00 to 9.00)."
    assert ws[0]["key"] == f"rule:tp.z1.{who}.Mon:{cls}|{subj}|0|1" and ws[0]["where"]["id"] == 1
    sp2 = copy.deepcopy(sp); sp2["staff_periods"].insert(0, dict(_id="a0", name="Briefing", all=True, depts=[], teachers=[], week="Both", days=["Fri"], times=["08:00", "09:00"], place=""))
    m2 = model_for(sp2, [(0, 1, 2, [cls], subj, "Entire Class", [who], "")])
    assert [w["key"] for w in verify.rules(m2, m2["checked_setup"])[0] if "staff" in w] == [ws[0]["key"]]      # an answer stays with its warning when a row is added in front
    m3 = model_for(sp, [(0, 4, 2, [cls], subj, "Entire Class", [who], "")])
    assert not [w for w in verify.rules(m3, m3["checked_setup"])[0] if "staff" in w]


print(f"{n} checks passed")

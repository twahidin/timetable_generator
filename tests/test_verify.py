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
    assert ws[k]["where"] == dict(cls=cls, day=m["days"][0], period=0)
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
    assert len(ws) == 1 and ws[0]["key"] == f"rule:0:{c}|0|1" and ws[0]["group"] == t and ws[0]["where"]["period"] == 1 and nc == []
    assert ws[0]["text"] == f"Rule Teacher · {t} · Not available: {t} has English for {c} on {m['days'][0]} period 1 but is not available (periods 0-1)."
    assert run(sp, [rule("Teacher", t, "Not available", 0, 1)], [(0, 3, 1, [c], "English", "Entire Class", [t], "")])[0][0] == []
    d = next(x["dept"] for x in sp["teachers"] if x["name"] == t); lv = sp["classes"][0]["level"]
    for row, who in ((rule("Department", d, "Keep free together", 2, 3), t), (rule("Level", lv, "Keep free together", 2, 3), c)):
        (ws, nc), m = run(sp, [row], [(1, 3, 1, [c], "English", "Entire Class", [t], "")])
        assert len(ws) == 1 and ws[0]["key"] == f"rule:0:{who}|1" and ws[0]["group"] == who
        assert ws[0]["text"].endswith(f"{who} has English on {m['days'][1]} period 3; {row['target']} keeps periods 2-3 free together.")
        assert run(sp, [row], [(1, 5, 1, [c], "English", "Entire Class", [t], "")])[0][0] == []

@t
def fixed_at_only_in_not_in_finish_by():
    sp = primary(); c = sp["classes"][0]["class"]; t = sp["teachers"][0]["name"]; L = lambda d, p, n_=1: [(d, p, n_, [c], "English", "Entire Class", [t], "")]
    (ws, _), m = run(sp, [rule("Class", c, "Fixed at", 2, 9, day=None)], L(0, 3))
    assert len(ws) == 1 and ws[0]["key"] == f"rule:0:{c}|0|3" and ws[0]["text"].endswith(f"English for {c} starts at period 3 on {m['days'][0]}, not period 2.")
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
    assert len(ws) == 1 and ws[0]["key"] == f"rule:0:{c}|0|2" and ws[0]["text"].endswith(f"English for {c} is in periods 2-3 on {m['days'][0]}, kept for Mathematics.")
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

print(f"{n} checks passed")

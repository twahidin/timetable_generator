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
    return export._model(sp, days, L)

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

print(f"{n} checks passed")

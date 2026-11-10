"""Plain-assert tests for typed rules and the rule report: .venv/bin/python tests/test_rules.py"""
import io, os, sys, tempfile, contextlib, filecmp, sqlite3
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, ROOT)
from ttgen import spec as S, reader, template, solver, __main__ as main  # noqa: E402
from ttgen.samples import secondary  # noqa: E402
import openpyxl  # noqa: E402
n = 0
def t(f): global n; f(); n += 1
TYPED = {"scope": "Level", "target": "Sec 1", "rule": "In words", "text": "No PE in the first period", "strength": "Must", "week": "Both", "day": "All"}
BLANK = {"scope": "Class", "target": "1A", "rule": "In words", "text": "", "strength": "Prefer", "week": "Both", "day": "All"}

def with_typed():
    sp = secondary(); sp["rules"] = list(sp.get("rules", [])) + [TYPED, BLANK]; return sp

@t
def the_rule_type_exists():
    assert S.TYPED == "In words" and S.SKILL_VERSION == "2026-11.1"
    row = next(r for r in S.RULE_TYPES if r[0] == "In words"); assert row[1] == "School, Level, Class, Subject, Room, Teacher" and row[2] == "N" and row[3] == "N"
    assert S.typed_rules(with_typed())[0][0] == 1 and S.typed_rules(with_typed())[1][0] == 2
    assert S.typed_label(1, TYPED) == "T1 · Must · Sec 1 · No PE in the first period"
    assert S.typed_label(2, dict(TYPED, target="")) == "T2 · Must · No PE in the first period"

@t
def a_typed_rule_round_trips_through_the_workbook():
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "s.xlsx"); template.write_template(with_typed(), p)
        wb = openpyxl.load_workbook(p); ws = wb["More rules"]
        assert "In words" in [ws.cell(r, 13).value for r in range(1, 8)]   # the header row is within the sheet's first rows
        assert any(ws.cell(r, 13).value == "No PE in the first period" for r in range(1, 40))
        assert "2026-11" in str(wb["README"]["A4"].value)
        back = reader.read_template(p); got = [r for r in back["rules"] if r.get("rule") == "In words"]
        assert [(r["scope"], r["target"], r["text"], r["strength"]) for r in got] == [("Level", "Sec 1", "No PE in the first period", "Must"), ("Class", "1A", "", "Prefer")], got

@t
def an_older_workbook_without_the_column_still_reads():
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "s.xlsx"); template.write_template(with_typed(), p)
        wb = openpyxl.load_workbook(p); ws = wb["More rules"]; ws.delete_cols(13); wb.save(p)   # the column is gone, as in an older workbook
        back = reader.read_template(p); got = [r for r in back["rules"] if r.get("rule") == "In words"]
        assert len(got) == 2 and all(r["text"] == "" for r in got) and got[0]["target"] == "Sec 1"
        assert len([r for r in back["rules"] if r.get("rule") == "Not in periods"]) == len([r for r in secondary()["rules"] if r.get("rule") == "Not in periods"])

@t
def check_lists_typed_rules_and_flags_an_empty_one():
    sp = with_typed(); reader.derive(sp); P = solver.Problem(sp)
    probs = dict(solver.rule_problems(sp, P)); i_blank = len(sp["rules"]) - 1; i_typed = i_blank - 1
    assert i_typed not in probs and probs[i_blank].startswith("Write the rule in words"), probs
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "s.xlsx"); template.write_template(sp, p); out = io.StringIO()
        with contextlib.redirect_stdout(out): main.main(["check", p])
        text = out.getvalue(); assert " * For the agent to honour: T1 · Must · Sec 1 · No PE in the first period" in text, text
        assert "Write the rule in words" in text

@t
def the_skill_copy_is_identical():
    a, b = os.path.join(ROOT, "ttgen"), os.path.join(ROOT, "skill", "school-timetable-generator", "scripts", "ttgen")
    def files(root): return sorted(os.path.relpath(os.path.join(dp, f), root) for dp, dn, fn in os.walk(root) if "__pycache__" not in dp for f in fn if not f.endswith(".pyc"))
    assert files(a) == files(b), (files(a), files(b))
    diff = [f for f in files(a) if not filecmp.cmp(os.path.join(a, f), os.path.join(b, f), shallow=False)]
    assert not diff, diff

@t
def rule_report_rows_are_read_loosely():
    from ttgen import export
    rows = [("No.", "Must / Prefer", "Applies to", "Rule", "Result", "How"), (1, "Must", "Sec 1", "No PE in the first period", "MET", "PE never starts at period 0."),
            (2, "Prefer", "1A", "Art after recess", "partly met", "Three of four lessons."), (None, None, None, None, None, None), ("3", "Must", "", "Hall free on Fri", "nope", "")]
    got = export.rule_report_rows(iter(rows))
    assert [(r["no"], r["strength"], r["result"]) for r in got] == [(1, "Must", "Met"), (2, "Prefer", "Partly"), (3, "Must", "")], got
    assert got[0]["how"] == "PE never starts at period 0." and got[2]["applies"] == ""

@t
def the_database_carries_the_rule_report():
    from ttgen import database
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "t.sqlite"); con = sqlite3.connect(p)
        con.execute("CREATE TABLE lessons (id INTEGER PRIMARY KEY, day TEXT, start_period INTEGER, periods INTEGER, subject TEXT, classes TEXT)")
        con.execute("INSERT INTO lessons VALUES (1, 'Odd Mon', 3, 2, 'Art', '1A')")
        con.execute("CREATE TABLE rule_report (no INTEGER, strength TEXT, applies TEXT, rule TEXT, result TEXT, how TEXT)")
        con.execute("INSERT INTO rule_report VALUES (1, 'Must', 'Sec 1', 'No PE in the first period', 'Met', 'Never at 0.')"); con.commit(); con.close()
        out = database.read_db(p); assert len(out) == 8 and out[6] == [dict(no=1, strength="Must", applies="Sec 1", rule="No PE in the first period", result="Met", how="Never at 0.")], out[6]
        con = sqlite3.connect(p); con.execute("DROP TABLE rule_report"); con.commit(); con.close()
        assert database.read_db(p)[6] == []

@t
def the_skill_says_its_version_and_asks_for_the_report():
    md = open(os.path.join(ROOT, "skill", "school-timetable-generator", "SKILL.md"), encoding="utf-8").read()
    assert "Skill version: 2026-11" in md and "Rule report" in md and "In words" in md and "Not met" in md

@t
def rule_report_rows_forgive_a_title_row_t_numbers_and_header_variants():
    from ttgen import export
    rows = [("Rule report", None, None, None, None, None), (None, None, None, None, None, None),
            ("#", "Strength", "Applies to", "Typed rule", "Met?", "How"), ("T1", "Must", "Sec 1", "No PE in the first period", "met", "Never at 0."), ("T2", "Prefer", "1A", "Art after recess", "Not met", "No room.")]
    got = export.rule_report_rows(iter(rows))
    assert [(r["no"], r["strength"], r["rule"], r["result"]) for r in got] == [(1, "Must", "No PE in the first period", "Met"), (2, "Prefer", "Art after recess", "Not met")], got
    assert export.rule_report_rows(iter([("Notes", "Rule", "Result", "How"), ("x", "A", "Met", "y")]))[0]["no"] is None   # Notes is not No.

@t
def a_report_on_the_timetable_workbook_reaches_the_database():
    from ttgen import export, database
    from ttgen.samples import primary
    with tempfile.TemporaryDirectory() as d:
        sp = primary(); setup = os.path.join(d, "setup.xlsx"); template.write_template(sp, setup)
        ds = sp["day_structure"]; lv = sp["school"]["levels"][0]; day = next(iter(ds[lv])); cls = next(c["class"] for c in sp["classes"] if c["level"] == lv)
        x = next(x for x in sp["lessons"] if cls in x["classes"] and not x.get("block"))
        wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Lessons"
        ws.append(["Lesson ID", "Day", "Start period", "End period", "Periods", "Starts", "Ends", "Level", "Block", "Classes", "Subject", "Group", "Teachers", "Room", "After school", "Rain room"])
        p0 = ds[lv][day].index("L"); ws.append([1, day, p0, p0, 1, "", "", lv, "", cls, x["subject"], "Entire Class", ", ".join(x["teachers"]), "", "", ""])
        rr = wb.create_sheet("Rule report"); rr.append(["No.", "Must / Prefer", "Applies to", "Rule", "Result", "How"]); rr.append(["T1", "Must", "Whole school", "Nothing in words", "Met", "Checked."])
        tt = os.path.join(d, "timetable.xlsx"); wb.save(tt)
        m = export.model_from_files(setup, tt); assert m["rule_report"][0]["no"] == 1 and m["rule_report"][0]["how"] == "Checked."
        db = os.path.join(d, "t.sqlite"); database.write_db(m, db, spec=sp)
        assert database.read_db(db)[6][0]["result"] == "Met"
        m2 = export.model_from_files(None, db); assert m2["rule_report"][0]["rule"] == "Nothing in words"   # the database alone carries it on

print(f"{n} checks passed")

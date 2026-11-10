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
    assert S.TYPED == "In words" and S.SKILL_VERSION == "2026-11"
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

print(f"{n} checks passed")

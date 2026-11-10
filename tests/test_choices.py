"""Plain-assert tests for second choices and the Choices sheet: .venv/bin/python tests/test_choices.py"""
import io, os, sys, tempfile, contextlib
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, ROOT)
from ttgen import choices, reader, template, __main__ as main  # noqa: E402
from ttgen.samples import secondary  # noqa: E402
import openpyxl  # noqa: E402
n = 0
def t(f): global n; f(); n += 1
N0 = len(secondary()["rules"]); i_R1, i_R2 = N0, N0 + 1
R1 = dict(scope="Level", target="Sec 1", rule="Not in periods", week="Both", day="All", **{"from": 20, "to": 22}, strength="Must")
R2 = dict(scope="School", target="Whole school", rule="In words", text="No PE in the first period", strength="Must", week="Both", day="All")

def with_choices():
    sp = secondary(); sp["school"]["after_school"] = False; sp["rules"] = list(sp["rules"]) + [dict(R1), dict(R2)]
    sp["choices"] = [dict(kind="recess", level="Sec 2", window=["09:00", "11:20"], order=2),
                     dict(kind="setting", key="after_school", second="Yes", order=1),
                     dict(kind="rule", rule=i_R1, fallback="Instead", instead=dict(R1, **{"from": 23, "to": 25}), order=3),
                     dict(kind="rule", rule=i_R2, fallback="Prefer", order=4)]
    return sp

@t
def ordered_and_labels():
    sp = with_choices(); o = choices.ordered(sp)
    assert [c["kind"] for _, c in o] == ["setting", "recess", "rule", "rule"]
    assert choices.item_label(sp, o[0][1]) == "After-school slot allowed when a class cannot fit" and choices.first_text(sp, o[0][1]) == "No" and choices.second_text(sp, o[0][1]) == "Yes"
    assert choices.item_label(sp, o[1][1]) == "Recess for Sec 2" and choices.first_text(sp, o[1][1]).startswith("Fixed at ") and choices.second_text(sp, o[1][1]) == "Floating between 9.00 and 11.20"
    assert choices.item_label(sp, o[2][1]) == "Rule: Level · Sec 1 · Not in periods" and choices.second_text(sp, o[2][1]).startswith("Instead: ")
    assert choices.item_label(sp, o[3][1]) == "Rule: T1 · Must · Whole school · No PE in the first period" and choices.second_text(sp, o[3][1]) == "Make it Prefer"

@t
def applying_the_first_k():
    sp = with_choices(); n = len(sp["rules"])
    a1 = choices.apply_all(sp, 1); assert a1["school"]["after_school"] is True and sp["school"]["after_school"] is False
    a2 = choices.apply_all(sp, 2); row = a2["day_structure"]["Sec 2"]["Odd Mon"]; assert "W" in row and "R" not in row and a2["day_structure"]["Sec 2"]["Odd Mon"] != sp["day_structure"]["Sec 2"]["Odd Mon"]
    assert any(str(x[0]).startswith("Floating recess length") and x[1] == 2 for x in a2["school"]["extra_settings"])
    a3 = choices.apply_all(sp, 3); r = a3["rules"][i_R1]; assert (r["from"], r["to"]) == (23, 25) and len(a3["rules"]) == n
    a4 = choices.apply_all(sp, 4); assert a4["rules"][i_R2]["strength"] == "Prefer" and sp["rules"][i_R2]["strength"] == "Must"
    sp["choices"][3]["fallback"] = "Drop"; a4 = choices.apply_all(sp, 4); assert len(a4["rules"]) == n - 1 and (a4["rules"][i_R1]["from"], a4["rules"][i_R1]["to"]) == (23, 25)

@t
def problems_are_found_and_skipped():
    sp = with_choices()
    sp["choices"] += [dict(kind="rule", rule=99, fallback="Drop", order=5), dict(kind="setting", key="after_school", second="No", order=6), dict(kind="recess", level="Sec 1", window=["09:00", "09:20"], order=7)]
    ps = dict(choices.problems(sp)); assert 4 in ps and "no longer on the setup" in ps[4] and "same as the first" in ps[5] and "shorter than the recess" in ps[6], ps
    assert choices.apply_all(sp, 7)["rules"] == choices.apply_all(sp, 4)["rules"]   # the bad ones change nothing
    sp["choices"][6]["window"] = ["11:00", "12:00"]; assert "does not include the recess" in dict(choices.problems(sp))[6]
    sp["day_structure"]["Sec 1"]["Odd Mon"] = sp["day_structure"]["Sec 1"]["Odd Mon"].replace("RR", "WW"); sp["choices"][6]["window"] = ["09:00", "11:20"]
    assert "already has a floating recess" in dict(choices.problems(sp))[6]
    assert [u["used"] for u in choices.used_rows(sp, 2)] == ["Second choice", "Second choice", "First choice", "First choice"] and choices.used_rows(sp, 2)[0]["no"] == 1

@t
def bad_setting_values_are_skipped_and_prefer_rows_are_left_alone():
    sp = with_choices(); sp["choices"] = [dict(kind="setting", key="max_day", second="3 periods", order=1), dict(kind="setting", key="after_school", second="Maybe", order=2)]
    ps = dict(choices.problems(sp)); assert "whole number" in ps[0] and "Yes or No" in ps[1], ps
    assert choices.apply_all(sp, 2)["rules"] == sp["rules"] and choices.apply_all(sp, 2)["school"]["after_school"] is False
    sp = secondary(); sp["rules"] = [dict(scope="School", target="Whole school", rule="Max periods a day", week="Both", day="All", strength="Prefer", number=6)]
    sp["choices"] = [dict(kind="setting", key="max_day", second="no limit", order=1)]
    assert choices.first_text(sp, sp["choices"][0]) == "no limit" and choices.apply_all(sp, 1)["rules"] == sp["rules"]

@t
def the_choices_sheet_round_trips():
    sp = with_choices(); sp["school"]["choices_mode"] = "compare"
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "s.xlsx"); template.write_template(sp, p)
        wb = openpyxl.load_workbook(p); ws = wb["Choices"]; assert ws["B3"].value == "Make one timetable for each" and ws.cell(6, 3).value == "After-school slot allowed when a class cannot fit"
        assert wb.sheetnames.index("Choices") == wb.sheetnames.index("More rules") + 1
        back = reader.read_template(p); got = choices.ordered(back)
        assert [c["kind"] for _, c in got] == ["setting", "recess", "rule", "rule"] and back["school"]["choices_mode"] == "compare"
        assert got[0][1]["second"] == "Yes" and got[1][1]["window"] == ["09:00", "11:20"] and got[2][1]["fallback"] == "Instead" and got[2][1]["instead"]["from"] == 23
        assert back["rules"][got[2][1]["rule"]]["rule"] == "Not in periods" and back["rules"][got[3][1]["rule"]]["rule"] == "In words"
        wb.remove(wb["Choices"]); wb.save(p); assert reader.read_template(p)["choices"] == []   # an older workbook

@t
def check_lists_the_choices():
    sp = with_choices()
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "s.xlsx"); template.write_template(sp, p); out = io.StringIO()
        with contextlib.redirect_stdout(out): main.main(["check", p])
        assert " * Second choice 1: After-school slot allowed when a class cannot fit — No → Yes" in out.getvalue(), out.getvalue()

print(f"{n} checks passed")

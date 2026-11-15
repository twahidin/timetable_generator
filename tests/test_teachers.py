"""Plain-assert tests for the Teachers sheet without Can teach and with Department 2: run with .venv/bin/python tests/test_teachers.py"""
import os
import re
import sys
import tempfile

import openpyxl
from openpyxl.utils import get_column_letter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from ttgen import reader, spec, template  # noqa: E402
from ttgen.samples import primary, secondary  # noqa: E402

passed = 0


def write(sp, drop=None):
    d = tempfile.mkdtemp(); p = os.path.join(d, "s.xlsx"); template.write_template(sp, p)
    if drop:
        sheet, heads = drop; wb = openpyxl.load_workbook(p); ws = wb[sheet]
        for h in heads: ws.delete_cols(next(j for j in range(1, ws.max_column + 1) if ws.cell(5, j).value == h))
        wb.save(p)
    return p


def headings(p, sheet):
    ws = openpyxl.load_workbook(p)[sheet]
    return [ws.cell(5, j).value for j in range(1, ws.max_column + 1) if ws.cell(5, j).value]


def t(f):
    global passed
    f(); passed += 1


@t
def teacher_depts_are_the_home_then_the_second():
    D = spec.teacher_depts
    assert D(dict(dept="MA", dept2="SC")) == ["MA", "SC"] and D(dict(dept="MA", dept2="MA")) == ["MA"]
    assert D(dict(dept=" MA ", dept2="")) == ["MA"] and D(dict(dept=None, dept2="SC")) == ["SC"] and D({}) == [] and D(dict(dept="MA", can_teach=[1])) == ["MA"]


@t
def a_second_department_goes_to_the_workbook_and_back():
    sp = secondary(); T = sp["teachers"]; other = next(d for d in sp["school"]["departments"] if d != T[0]["dept"])
    T[0]["dept2"] = other; T[1]["dept2"] = T[1]["dept"]                     # the same as the home: none
    p = write(sp); got = reader.read_template(p)["teachers"]
    assert got[0]["dept2"] == other and got[1]["dept2"] is None and all(x["dept2"] is None for x in got[2:])
    assert [x["dept"] for x in got] == [x["dept"] for x in T] and all("can_teach" not in x for x in got)
    assert headings(p, "4 Teachers")[:6] == ["Teacher", "Short", "Department", "Department 2", "Allowance (periods)", "Provisional"]
    again = reader.read_template(write(reader.read_template(p)))             # written and read once more: the same setup
    assert all(again[k] == reader.read_template(p)[k] for k in ("teachers", "subjects", "classes", "venues", "blocks", "lessons", "rules"))


@t
def the_teachers_formulas_point_at_the_columns_they_name():
    wb = openpyxl.load_workbook(write(secondary())); ws = wb["4 Teachers"]
    col = {ws.cell(5, j).value: get_column_letter(j) for j in range(1, ws.max_column + 1) if ws.cell(5, j).value}
    assert not [h for h in col if str(h).startswith(("Can teach", "at ")) or "key" in str(h)]
    al, pg, sp_, od, tl, ro, rg, pc, lc = (col[h] for h in ("Allowance (periods)", "Periods given", "Spare", "Other duties (periods)", "Total load", "Role", "Role guide (periods)", "% of allowance", "Load check"))
    assert ws[f"{sp_}6"].value == f'=IF(OR(A6="",{al}6=""),"",{al}6-{pg}6)'
    assert ws[f"{tl}6"].value == f'=IF(A6="","",N({pg}6)+N({od}6))'
    assert ws[f"{pc}6"].value == f'=IF(OR(A6="",N({al}6)=0),"",{tl}6/{al}6)'
    f = ws[f"{lc}6"].value
    assert f'N({al}6)>0,{tl}6>{al}6),"Over allowance. "' in f and f"{al}6<>{rg}6" in f and f'IF({ro}6="","No role. "' in f
    refs = {m for w in wb.worksheets if w.title != "4 Teachers" for row in w.iter_rows() for c in row if isinstance(c.value, str) for m in re.findall(r"'4 Teachers'!\$([A-Z]+)\$", c.value)}
    assert refs <= {"A", ro, tl, pc} and refs & {ro, tl, pc}                 # other sheets read only the names, the roles, the loads and the % of allowance


@t
def a_workbook_from_before_still_opens_and_its_can_teach_is_ignored():
    sp = secondary(); p = write(sp, drop=("4 Teachers", ["Department 2"])); wb = openpyxl.load_workbook(p); ws = wb["4 Teachers"]
    ws.insert_cols(6, 2); ws.cell(5, 6, "Can teach 1"); ws.cell(5, 7, "at 1"); ws.cell(6, 6, sp["subjects"][0]["subject"]); ws.cell(6, 7, "All"); wb.save(p)
    old, new = reader.read_template(p), reader.read_template(write(sp))
    assert all("can_teach" not in x and x["dept2"] is None for x in old["teachers"])
    assert old["teachers"] == new["teachers"] and old["lessons"] == new["lessons"] and old["subjects"] == new["subjects"]


@t
def a_stored_can_teach_is_left_out_of_the_workbook():
    sp = secondary(); sp["teachers"][0]["can_teach"] = [dict(subject=sp["subjects"][0]["subject"], levels="All")]
    p = write(sp); assert not [h for h in headings(p, "4 Teachers") if str(h).startswith("Can teach")]
    assert "can_teach" not in reader.read_template(p)["teachers"][0] and sp["teachers"][0]["can_teach"]   # the setup's own list is not touched


@t
def allocate_is_gone():
    assert not any(os.path.exists(os.path.join(ROOT, d, "allocate.py")) for d in ("ttgen", "skill/school-timetable-generator/scripts/ttgen"))


print(f"{passed} checks passed")

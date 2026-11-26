"""Plain-assert tests for equipment and configuration on a room: run with .venv/bin/python tests/test_venues.py"""
import os
import sys
import tempfile

import openpyxl

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from ttgen import reader, template  # noqa: E402
from ttgen.samples import secondary  # noqa: E402

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


def setup():
    sp = secondary(); v = sp["venues"]
    v[0]["equipment"] = ["30 keyboards", "2 amps"]; v[0]["configuration"] = "cluster seating"
    v[1]["equipment"] = ["  PCs / laptops & chargers ", "", 'a "smart" board']; v[1]["configuration"] = "  rows of 8  "
    return sp


@t
def equipment_and_configuration_survive_the_workbook():
    sp = setup(); p = write(sp); back = reader.read_template(p)["venues"]
    assert headings(p, "1 Venues")[-4:] == ["For (subjects, departments or levels)", "Equipment", "Configuration", "Made of (rooms used together)"], headings(p, "1 Venues")
    assert back[0]["equipment"] == ["30 keyboards", "2 amps"] and back[0]["configuration"] == "cluster seating"
    assert back[1]["equipment"] == ["PCs / laptops & chargers", 'a "smart" board'] and back[1]["configuration"] == "rows of 8"
    assert back[2]["equipment"] == [] and not back[2]["configuration"]
    again = reader.read_template(write(reader.read_template(p)))["venues"]                    # a second trip changes nothing
    assert [(x["room"], x["equipment"], x["configuration"]) for x in again] == [(x["room"], x["equipment"], x["configuration"]) for x in back]


@t
def a_workbook_from_before_reads_with_no_equipment():
    sp = setup(); p = write(sp, drop=("1 Venues", ["Equipment", "Configuration"])); back = reader.read_template(p)
    assert all(x["equipment"] == [] and not x["configuration"] for x in back["venues"]) and len(back["venues"]) == len(sp["venues"])
    keep = lambda v: [(x["room"], x.get("kind"), x.get("capacity"), x.get("building"), x.get("floor"), x.get("only_for") or [], x.get("note")) for x in v]
    assert keep(back["venues"]) == keep(reader.read_template(write(secondary()))["venues"])     # everything else as a plain setup gives it


@t
def the_other_columns_of_the_venues_sheet_have_not_moved():
    a = headings(write(secondary()), "1 Venues")
    assert a[:8] == ["Room", "Kind", "Capacity", "Block", "Floor / level", "Used by lessons", "Note", "For (subjects, departments or levels)"], a


@t
def equipment_decides_nothing():
    import checks                                              # the app's own list of findings for a setup (ttgen/checks.py; checks.py at the repository's root is a name for it)
    assert checks.findings(setup()) == checks.findings(secondary())


print(f"{passed} checks passed")

"""Plain-assert tests for the skill's own check printing step 7's sums: .venv/bin/python tests/test_check_sums.py"""
import contextlib, io, os, re, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, ROOT)
from ttgen import reader, template, __main__ as main  # noqa: E402
from ttgen import checks as C  # noqa: E402
from ttgen.samples import secondary  # noqa: E402
n = 0
def t(f): global n; f(); n += 1

CRIT, WARN = "Critical (", "Warnings ("

def run(sp):
    """the check on this setup as a workbook: (exit code, what it printed, the findings of the workbook as read)"""
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "s.xlsx"); template.write_template(sp, p); out = io.StringIO()
        with contextlib.redirect_stdout(out): code = main.main(["check", p])
        return code, out.getvalue(), C.findings(reader.read_template(p))

def fuller(extra, after_school=None, choice=False):
    """the secondary sample with class 1B's Art given `extra` more periods (1B is 161 of 162 lesson periods, +24 after school)"""
    sp = secondary(); art = next(s for s in sp["subjects"] if s["subject"] == "Art")["periods"]["Sec 1"]
    row = next(x for x in sp["lessons"] if not x.get("block") and x["classes"] == ["1B"] and x["subject"] == "Art")
    row["periods_override"] = art + extra
    if after_school is not None: sp["school"]["after_school"] = after_school
    if choice: sp["choices"] = [dict(kind="setting", key="after_school", second="Yes", order=1)]
    return sp

def section(text, head):
    """the ' - ' lines under one heading, up to the next line that is not one"""
    lines = text.splitlines(); i = next(k for k, l in enumerate(lines) if l.startswith(head)); out = []
    for l in lines[i + 1:]:
        if not l.startswith(" - "): break
        out.append(l)
    return out

def count(text, head): return int(re.search(re.escape(head) + r"(\d+)\)", text).group(1))

@t
def plain_sample_has_both_headings():
    code, text, found = run(secondary())
    assert code == 0, text
    crit = [f for f in found if f["level"] == C.CRITICAL]; warn = [f for f in found if f["level"] == C.WARNING]
    assert not crit and warn, found
    assert "Critical (0): no timetable can be made until these are fixed" in text.splitlines(), text
    assert f"Warnings ({len(warn)}): a timetable can still be made; a person should check these" in text.splitlines(), text
    assert section(text, CRIT) == [] and len(section(text, WARN)) == len(warn)

@t
def nothing_wrong_still_prints_both_headings():
    sp = secondary()
    for x in sp["lessons"]:   # every class well under its day, so nothing is almost full
        if not x.get("block") and x["subject"] == "Art": x["periods_override"] = 3
    code, text, found = run(sp)
    assert code == 0 and "Critical (0)" in text and count(text, WARN) == len(found), text
    assert text.index(CRIT) < text.index(WARN)

@t
def an_overfull_class_is_critical_and_ends_with_1():
    code, text, found = run(fuller(40))
    crit = [f for f in found if f["level"] == C.CRITICAL]
    assert code == 1 and crit and count(text, CRIT) == len(crit), text
    top = section(text, CRIT)
    assert any(l.startswith(" - [classes] Class 1B needs 201 periods but Sec 1 has 162 lesson periods a cycle (+24 after-school)") for l in top), top
    assert top == [f" - [{f['area']}] {f['text']}" for f in crit]
    assert text.index(CRIT) < text.index(WARN) and not any("Class 1B needs" in l for l in section(text, WARN))

@t
def the_same_words_as_the_app():
    for sp in (secondary(), fuller(40), fuller(6)):
        code, text, found = run(sp)
        assert section(text, CRIT) + section(text, WARN) == [f" - [{f['area']}] {f['text']}" for f in found], text

@t
def over_but_within_the_after_school_slots_is_a_warning():
    code, text, found = run(fuller(6))   # 167 of 162, with 24 after-school slots
    assert code == 0 and count(text, CRIT) == 0 and any("Class 1B needs 167 periods" in l for l in section(text, WARN)), text

@t
def second_choices_that_clear_it():
    code, text, found = run(fuller(6, after_school=False, choice=True))   # no after-school slots: 167 of 162 is critical until choice 1
    assert any(f["level"] == C.CRITICAL for f in found) and code == 0, text
    assert any("Class 1B needs 167 periods" in l for l in section(text, CRIT)), text
    line = "Giving way in the committee's order, nothing is critical after choice 1: After-school slot allowed when a class cannot fit."
    assert line in text.splitlines(), text
    assert " * Second choice 1: After-school slot allowed when a class cannot fit — No → Yes" in text, text

@t
def second_choices_that_do_not_clear_it():
    code, text, found = run(fuller(40, after_school=False, choice=True))   # 201 of 162 + 24: still over with the slots
    assert code == 1 and "Even after every second choice (1), 1 thing will not fit." in text.splitlines(), text
    assert "Giving way in the committee's order" not in text

@t
def no_choices_no_give_way_line():
    code, text, _ = run(fuller(40))
    assert "second choice" not in text.lower() and "Giving way" not in text, text

@t
def old_lines_are_gone_and_the_rest_stays():
    code, text, _ = run(fuller(40))
    assert not any(l.startswith((" ! Fixed lessons clash", " ! Rule ", " ! Day structure and rules disagree")) for l in text.splitlines()), text
    assert "No input problems found." not in text
    lines = text.splitlines(); assert re.match(r"\d+ classes, \d+ teachers, \d+ lesson rows, ", lines[0]) and " units to place over " in lines[1], lines[:2]
    sp = secondary(); sp["rules"] = list(sp["rules"]) + [dict(scope="School", target="Whole school", rule="In words", text="No PE in the first period", strength="Must", week="Both", day="All")]
    code, text, _ = run(sp); assert " * For the agent to honour: T1 · Must · Whole school · No PE in the first period" in text, text

@t
def root_name_is_the_same_module():
    import checks
    assert checks is C and checks._class_fit is C._class_fit and checks.findings is C.findings and checks.CRITICAL == "critical"

@t
def the_skill_has_the_same_file():
    a = os.path.join(ROOT, "ttgen", "checks.py"); b = os.path.join(ROOT, "skill", "school-timetable-generator", "scripts", "ttgen", "checks.py")
    assert open(a, "rb").read() == open(b, "rb").read()
    src = open(a, encoding="utf-8").read(); assert not re.search(r"^\s*(from|import) ttgen\b", src, re.M)   # relative imports only: the skill runs it from its own folder

@t
def the_skill_copy_runs_by_itself():
    """from the skill's scripts folder alone, as an agent runs it: the check prints the headings"""
    import subprocess
    scripts = os.path.join(ROOT, "skill", "school-timetable-generator", "scripts")
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "s.xlsx"); template.write_template(fuller(40), p)
        r = subprocess.run([sys.executable, "-B", "-m", "ttgen", "check", p], cwd=scripts, capture_output=True, text=True, env=dict(os.environ, PYTHONPATH=""))
        assert r.returncode == 1 and "Critical (" in r.stdout and " - [classes] Class 1B needs 201 periods" in r.stdout, (r.returncode, r.stdout[-400:], r.stderr[-400:])

@t
def skill_md_says_what_the_check_prints():
    from ttgen import spec as SPEC
    s = open(os.path.join(ROOT, "skill", "school-timetable-generator", "SKILL.md"), encoding="utf-8").read()
    assert SPEC.SKILL_VERSION == "2026-11.10" and "Skill version: 2026-11.10" in s
    for words in ("**Critical** items", "**Any critical item: stop.**", "nothing is critical after choice", "`ttgen/checks.py`", "the check has done these sums"): assert words in s, words
    readme = open(os.path.join(ROOT, "README.md"), encoding="utf-8").read()
    assert "`ttgen/checks.py`" in readme and "Skill version: 2026-11.10" in readme

print(f"{n} checks passed")

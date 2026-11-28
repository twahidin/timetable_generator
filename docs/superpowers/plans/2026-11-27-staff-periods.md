# Teacher-only periods Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The committee enters a weekly period for teachers with no students once on step 6; it shows on those teachers' timetables and keeps lessons and relief away from them, and is a mark (never a refusal) for exams and events.

**Architecture:** A new list `spec["staff_periods"]` in the setup. `ttgen/spec.py` turns it into items (clock times, periods, people) and, for lesson readers, into block-outs shaped like a teacher's Must "Not available" rule and marked `staff`. `ttgen.reader.derive` appends those block-outs to the derived setup's `rules`, so the solver, step 7's sums, the rule check, the board's judge, the helper and Re-fit follow with no change of their own. Relief, exams, the exporter, the published page and the board read the items directly.

**Tech Stack:** Python 3 (Flask, openpyxl, reportlab), plain browser JavaScript, plain-assert tests (`.venv/bin/python tests/<name>.py`, `node tests/<name>.test.js`).

**Spec:** `docs/superpowers/specs/2026-11-27-staff-periods-design.md` (mockup `2026-11-27-staff-periods-mockup.html` and `.png` beside it). Read it before any task.

## Global Constraints

- The repository is public. The school is only ever "CTSS". Only made-up names in code, tests, comments and commit messages.
- NEVER run `git stash`, `git stash pop`, `git checkout -- <file>`, `git reset`, or switch branches. Never use `pkill`/`killall`; stop only processes you started, by PID. Commit on branch `staff-periods` only; never push.
- Commit messages end with the line `Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>`.
- Words on the page: "Teacher-only periods" (heading), "+ Add a teacher-only period", "All teachers", "Name on the timetable", "Who", "Week", "Days", "From", "To", "Place (optional)".
- Name and Place are at most 60 characters.
- Sentences, exactly:
  - step 8's list: `{teacher} has {lesson} on {day} period {p} during {name} ({from} to {to}).`
  - the board's box: `{teacher} has {name} then ({day} {from} to {to}).`
  - exams and events mark, and the candidate's reason: `has {name} then`
  - relief's busy reason: `Teacher-only period: {name}`
  - the legend line: `{name} · {week and days} · {from} to {to} · {place}` (no last part when there is no place)
- Clock times are stored `"HH:MM"` (24-hour) and shown 12-hour with a dot and no am/pm, as the model's `times` are: `"15:00"` shows as `3.00`, `"17:30"` as `5.30`, `"07:40"` as `7.40`.
- A teacher-only period is never a row of `m["lessons"]` or `D.lessons`, is never counted in any period count, load or allowance, and never reaches the `student` or `personal` page data.
- Rows of "Teacher availability" (plain Must "Not available" rules) behave exactly as before everywhere.
- `skill/school-timetable-generator/scripts/ttgen/` stays a byte-for-byte copy of `ttgen/`: after any change under `ttgen/`, copy the changed files and check `diff -rq ttgen skill/school-timetable-generator/scripts/ttgen` prints nothing.
- `ttgen/timetable_page.html` keeps many statements on one long line: use `/* */` comments only inside a line; after each edit cut the last `<script>` out and run `node --check` on it.
- Skill version becomes `2026-11.12`.
- In a browser check, clicks and drags are made with the browser tool's real pointer, on the sample school only; say for each check which kind of action it was.

## Review Focus

1. A setup saved before this work has no `staff_periods` key at all: every reader must treat a missing key, `None`, or a non-list as an empty list, and a row that is not a dict as absent. (Test in Task 1.)
2. A weekday written long or oddly on the setup ("Tues", "Thurs", "Thursday"): a row's days must match by the first three letters, as rules do. (Test in Task 1.)
3. A teacher named in a row who is renamed, or removed from step 4, while the draft and the published timetable still name them: the row goes on working for the others and nothing raises. (Tests in Tasks 1 and 4.)
4. A period that overlaps a lesson of the same teacher on the published page (one forced there by hand): the lesson must stay visible on the page, the PDF and the Excel sheet. (Tests in Task 5.)
5. A one-week school (days "Mon".."Fri", week always "Both") and a row whose week is "Odd" left over from a two-week setup: the row applies to no day and nothing raises. (Test in Task 1.)

---

## File Structure

| File | Responsibility |
|---|---|
| `ttgen/spec.py` (modify) | The list's shape, people, faults, items, block-outs; `plain_rules`, `rules_with_staff`; `SKILL_VERSION`. |
| `ttgen/reader.py`, `ttgen/template.py` (modify) | The workbook sheet "Teacher-only periods"; `derive` appends the block-outs. |
| `ttgen/solver.py`, `ttgen/verify.py`, `fixes.py` (modify) | Skip marked rows where a rule row is listed to the committee; the two sentences. |
| `ttgen/export.py`, `ttgen/timetable_page.html`, `app.py` (modify) | The box and legend on a teacher's timetable (page, PDF, Excel), "Who's free", a teacher's own periods by request. |
| `draft.py`, `static/board.js`, `static/app.js` (modify) | Fixed boxes on step 8's teacher rows. |
| `static/staffperiods.js` (create) | Plain functions for step 6's list (people, faults, the "blocks" line), run under Node. |
| `static/app.js`, `static/sync.js`, `sync.py`, `history.py`, `static/teacherview.js`, `static/index.html`, `static/style.css` (modify) | Step 6's list, saving by row, history labels, rename. |
| `relief/free.py`, `static/relief-plan.js` (modify) | Busy for relief, with the reason. |
| `exams/days.py`, `exams/invigilate.py`, `exams/events.py`, `exams/approval.py`, `app.py`, `static/exams.js` (modify) | A mark, never a refusal. |
| `tests/test_staff_periods.py`, `tests/staffperiods.test.js` (create) | The new suites; other suites get the tests named in each task. |
| `skill/school-timetable-generator/SKILL.md`, `README.md` (modify) | The sheet, the model sentence, the version. |

Test files are plain-assert scripts. A new Python suite starts like `tests/test_combined.py` (the `t` decorator, `n` counter, `if __name__ == "__main__": print(f"{n} checks passed")`). A new Node suite starts like `tests/groups.test.js`.

---

### Task 1: The list in `ttgen/spec.py`

**Files:**
- Modify: `ttgen/spec.py`
- Create: `tests/test_staff_periods.py`
- Copy: `ttgen/spec.py` to `skill/school-timetable-generator/scripts/ttgen/spec.py`

**Interfaces:**
- Consumes: `spec["school"]` (`start_time` "HH:MM", `period_minutes`, `periods_per_day`), `spec["teachers"]` rows (`name`, `dept`, `dept2`), `teacher_depts_of(t)`, `WEEKDAYS`.
- Produces (all in `ttgen/spec.py`):
  - A row: `dict(_id?, name: str, all: bool, depts: list[str], teachers: list[str], week: "Both"|"Odd"|"Even", days: list[str], times: ["HH:MM", "HH:MM"], place: str)`.
  - `staff_rows(spec) -> list[dict]`: the rows that are dicts; `[]` for a missing key, `None` or a non-list.
  - `staff_people(spec, row) -> list[str]`: names on step 4 the row means now, in step 4's order, each once.
  - `staff_faults(spec, row) -> list[tuple[bool, str]]`: `(hard, sentence)`; a row with a hard fault blocks nothing and shows nowhere.
  - `clock12(hhmm: str) -> str`.
  - `staff_items(spec) -> list[dict]`: one per row without a hard fault, per person, per day of the row: `dict(id: str, row: int, name, place, teacher, week, day, times: [str, str], minutes: (int, int), periods: (int, int) | None, before: bool, after: bool)`. `periods` is the first and last period the times overlap, cut to the grid, `None` when the times lie wholly outside it. `before`/`after`: the times start before period 0 / end after the last period. `id` is `f"tp.{row _id or index}.{teacher}.{day}"` with any `:` in it replaced by a space.
  - `staff_blocks(spec) -> list[dict]`: for each item with periods, `dict(scope="Teacher", target=teacher, rule="Not available", week=week, day=day, strength="Must", note=name, times=times, staff=name, place=place, _id=id, **{"from": a, "to": b})`.
  - `plain_rules(spec) -> list[dict]`: `spec["rules"]` without rows that have a `staff` key.
  - `rules_with_staff(spec) -> list[dict]`: `plain_rules(spec) + staff_blocks(spec)`. Calling it on a spec whose rules already hold marked rows gives the same list (no doubling).
  - `staff_days_text(week: str, days: list[str]) -> str`: `"Tue and Thu"`, `"Odd Mon"`, `"Even Mon, Wed and Fri"`.
  - `staff_legend_line(item_or_row) -> str`: the legend line of Global Constraints from a row's `name`, `week`, `days`, `times`, `place`.

- [ ] **Step 1: Write the failing tests** in `tests/test_staff_periods.py`

```python
def school():
    sp = secondary(); sp["school"].update(start_time="07:40", period_minutes=20, periods_per_day=26)
    sp["teachers"] = [dict(name="Mr Arjun Rao", dept="English", dept2=None), dict(name="Ms Mei Ling Koh", dept="Mathematics", dept2="English"),
                      dict(name="Mr Farhan Aziz", dept="Mathematics", dept2=None)]
    return sp
ZONE = dict(_id="z1", name="Zone computing class", all=False, depts=[], teachers=["Mr Arjun Rao", "Mr Farhan Aziz"], week="Both", days=["Tue", "Thu"], times=["15:00", "17:30"], place="West Zone centre")

@t
def people_by_name_department_and_all():
    sp = school()
    assert S.staff_people(sp, ZONE) == ["Mr Arjun Rao", "Mr Farhan Aziz"]
    assert S.staff_people(sp, dict(ZONE, teachers=[], depts=["English"])) == ["Mr Arjun Rao", "Ms Mei Ling Koh"]      # first and second department
    assert S.staff_people(sp, dict(ZONE, all=True, teachers=["Mr Arjun Rao"])) == [t_["name"] for t_ in sp["teachers"]]   # once each
    assert S.staff_people(sp, dict(ZONE, teachers=["Mr Gone", "Mr Arjun Rao"])) == ["Mr Arjun Rao"]

@t
def missing_or_broken_lists_are_empty():
    for v in ("absent", None, "x", [None, 3, "row"]):
        sp = school()
        if v != "absent": sp["staff_periods"] = v
        assert S.staff_rows(sp) == [] and S.staff_items(sp) == [] and S.staff_blocks(sp) == [] and S.rules_with_staff(sp) == S.plain_rules(sp)
    assert S.staff_items({}) == [] and S.staff_blocks(dict(rules=[])) == [] and S.rules_with_staff({}) == []     # a test fixture's setup may have no school at all

@t
def faults():
    sp = school(); f = lambda **k: S.staff_faults(sp, dict(ZONE, **k))
    assert f() == []
    assert f(name=" ") == [(True, "It has no name.")]
    assert f(teachers=[]) == [(True, "Nobody is in it.")]
    assert f(days=[]) == [(True, "It has no day.")]
    assert f(times=["15:00", "15:00"]) == [(True, "Its To time is not after its From time.")]
    assert f(times=["x", None]) == [(True, "Its From and To times are not times.")]
    assert f(teachers=["Mr Gone", "Mr Arjun Rao"]) == [(False, "Mr Gone is not on step 4.")]
    assert f(teachers=["Mr Gone"]) == [(False, "Mr Gone is not on step 4."), (True, "Nobody is in it.")]
    assert f(teachers=[], depts=["Science"]) == [(False, "Department Science has no teacher."), (True, "Nobody is in it.")]
    assert f(name="x" * 61) == [(True, "Its name is longer than 60 letters.")]

@t
def items_periods_and_edges():
    sp = school(); sp["staff_periods"] = [ZONE]; it = S.staff_items(sp)
    assert len(it) == 4 and [(x["teacher"], x["day"]) for x in it] == [("Mr Arjun Rao", "Tue"), ("Mr Arjun Rao", "Thu"), ("Mr Farhan Aziz", "Tue"), ("Mr Farhan Aziz", "Thu")]
    assert it[0]["periods"] == (22, 25) and it[0]["minutes"] == (900, 1050) and it[0]["after"] and not it[0]["before"]
    assert it[0]["id"] == "tp.z1.Mr Arjun Rao.Tue"
    one = lambda a, b: S.staff_items(dict(sp, staff_periods=[dict(ZONE, times=[a, b])]))[0]
    assert one("07:00", "07:30")["periods"] is None and one("07:00", "07:30")["before"]                 # wholly before the day
    assert one("16:20", "17:00")["periods"] is None and one("16:20", "17:00")["after"]                  # wholly after
    assert one("07:15", "08:00")["periods"] == (0, 0) and one("07:15", "08:00")["before"]
    assert one("14:50", "15:10")["periods"] == (21, 22)                                                  # half periods count whole
    assert one("14:20", "15:20")["periods"] == (20, 22) and not one("14:20", "15:20")["after"]

@t
def blocks_are_must_not_available_rows():
    sp = school(); sp["staff_periods"] = [ZONE, dict(ZONE, _id="m1", name="Briefing", times=["07:00", "07:30"])]
    sp["rules"] = [dict(scope="Teacher", target="Mr Farhan Aziz", rule="Not available", week="Both", day="Mon", strength="Must", **{"from": 0, "to": 3})]
    b = S.staff_blocks(sp)
    assert len(b) == 4 and b[0] == dict(scope="Teacher", target="Mr Arjun Rao", rule="Not available", week="Both", day="Tue", strength="Must", note="Zone computing class",
                                        times=["15:00", "17:30"], staff="Zone computing class", place="West Zone centre", _id="tp.z1.Mr Arjun Rao.Tue", **{"from": 22, "to": 25})
    once = S.rules_with_staff(sp); assert len(once) == 5 and once[0] is sp["rules"][0]
    assert S.rules_with_staff(dict(sp, rules=once)) == once and S.plain_rules(dict(sp, rules=once)) == sp["rules"]
    assert S.split_rules(dict(sp, rules=once))["availability"] == sp["rules"]                            # marked rows never reach the Teacher availability sheet

@t
def odd_days_long_day_names_and_one_week():
    sp = school(); sp["staff_periods"] = [dict(ZONE, days=["Tues", "Thursday"])]
    assert [x["day"] for x in S.staff_items(sp)][:2] == ["Tues", "Thursday"]
    from ttgen.verify import rule_days
    days = S.day_names(2); blocks = S.staff_blocks(sp)
    assert rule_days(days, blocks[0]) == [1, 6] and rule_days(days, blocks[1]) == [3, 8]
    assert rule_days(S.day_names(1), dict(blocks[0], week="Odd")) == []

@t
def words():
    assert [S.clock12(x) for x in ("15:00", "17:30", "07:40", "12:40", "00:05")] == ["3.00", "5.30", "7.40", "12.40", "12.05"]
    assert S.staff_days_text("Both", ["Tue", "Thu"]) == "Tue and Thu" and S.staff_days_text("Odd", ["Mon"]) == "Odd Mon"
    assert S.staff_days_text("Even", ["Mon", "Wed", "Fri"]) == "Even Mon, Wed and Fri"
    assert S.staff_legend_line(ZONE) == "Zone computing class · Tue and Thu · 3.00 to 5.30 · West Zone centre"
    assert S.staff_legend_line(dict(ZONE, place="")) == "Zone computing class · Tue and Thu · 3.00 to 5.30"
```

Head of the file: `from ttgen import spec as S`, `from ttgen.samples import secondary`, the `t` decorator and counter as in `tests/test_combined.py`.

- [ ] **Step 2: Run** `.venv/bin/python tests/test_staff_periods.py`. Expected: FAIL with `AttributeError: module 'ttgen.spec' has no attribute 'staff_people'`.

- [ ] **Step 3: Implement** the functions of the Interfaces block in `ttgen/spec.py`, and make `split_rules` walk `plain_rules(spec)` instead of `spec.get("rules", [])`. Fault order is as the tests give it: soft faults first (teachers in the row's order, then departments), then hard ones in the order name, name too long, nobody, no day, times not times, To not after From. `periods` uses the arithmetic of `ttgen/reader.py` `periods_between` (first period `(a - start) // minutes`, last `ceil((b - start) / minutes) - 1`) before cutting to `0..NP-1`.

- [ ] **Step 4: Run** `.venv/bin/python tests/test_staff_periods.py` (PASS), then `.venv/bin/python tests/test_rules.py` and `.venv/bin/python tests/test_verify.py` (PASS, unchanged counts).

- [ ] **Step 5: Copy and commit**

```bash
cp ttgen/spec.py skill/school-timetable-generator/scripts/ttgen/spec.py
diff -rq ttgen skill/school-timetable-generator/scripts/ttgen
git add ttgen/spec.py skill/school-timetable-generator/scripts/ttgen/spec.py tests/test_staff_periods.py
git commit -m "Teacher-only periods: the list, its people, faults, items and block-outs"
```

---

### Task 2: The workbook, `derive`, and the skill

**Files:**
- Modify: `ttgen/template.py` (the sheet, written after "Teacher availability", about line 443; the README sheet's list of sheets), `ttgen/reader.py` (`read_template` returns `staff_periods`; `KNOWN_SHEETS`, about line 309; `derive`, line 333), `ttgen/solver.py` (`rule_problems`, line 750), `ttgen/spec.py` (`SKILL_VERSION`, line 35), `app.py` (`normalise`, line 701: add `"staff_periods"` to the keys it defaults), `skill/school-timetable-generator/SKILL.md`, `README.md`
- Modify tests that pin the version: `tests/test_check_sums.py:207,212`, `tests/test_combined.py:370`, `tests/test_parents.py:182`
- Test: `tests/test_staff_periods.py`
- Copy: every changed file under `ttgen/` to the skill's `scripts/ttgen/`

**Interfaces:**
- Consumes: Task 1's `staff_rows`, `rules_with_staff`, `plain_rules`.
- Produces:
  - Sheet "Teacher-only periods", header row as the "Teacher availability" sheet has it, columns in this order: `Name`, `All teachers` (`Yes` or empty), `Departments` (names joined with `, `), `Teachers` (names joined with `, `), `Week`, `Days` (joined with `, `), `From`, `To` (time cells, format `h:mm AM/PM`, as "Teacher availability"), `Place`.
  - `read_template(path)["staff_periods"]`: the rows, in sheet order, shaped as Task 1's row without `_id`; `[]` when the workbook has no such sheet. A sheet row is kept when any of its cells is filled.
  - `reader.derive(spec)`: before it returns, `spec["rules"] = rules_with_staff(spec)`.
  - `solver.rule_problems(spec, P=None)`: never lists a row that has a `staff` key.
  - `SKILL_VERSION = "2026-11.12"`.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_staff_periods.py`)

```python
def round_trip(sp):
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f: path = f.name
    try: template.write_template(sp, path); return reader.read_template(path)
    finally: os.unlink(path)

@t
def the_workbook_keeps_every_shape_of_row():
    sp = secondary(); names = [x["name"] for x in sp["teachers"]][:2]; dept = sp["teachers"][0]["dept"]
    rows = [dict(name="Zone computing class", all=False, depts=[], teachers=names, week="Both", days=["Tue", "Thu"], times=["15:00", "17:30"], place="West Zone centre"),
            dict(name="Staff meeting", all=True, depts=[], teachers=[], week="Odd", days=["Mon"], times=["15:00", "16:20"], place="Hall"),
            dict(name="Department meeting", all=False, depts=[dept], teachers=names[:1], week="Even", days=["Wed"], times=["14:20", "15:20"], place=""),
            dict(name="", all=False, depts=[], teachers=[], week="Both", days=[], times=["15:00", "16:00"], place="")]            # a row just added on step 6
    sp["staff_periods"] = copy.deepcopy(rows)
    assert round_trip(sp)["staff_periods"] == rows
    assert round_trip(secondary())["staff_periods"] == []
    back = round_trip(sp); avail = [r for r in back["rules"] if r.get("rule") == "Not available" and r.get("scope") == "Teacher"]
    assert len(avail) == len([r for r in secondary()["rules"] if r.get("rule") == "Not available" and r.get("scope") == "Teacher"])   # not written to Teacher availability too

@t
def derive_appends_the_block_outs_once():
    sp = secondary(); t0 = sp["teachers"][0]["name"]; before = len(sp["rules"])
    sp["staff_periods"] = [dict(name="Zone computing class", all=False, depts=[], teachers=[t0], week="Both", days=["Tue"], times=["15:00", "17:30"], place="")]
    reader.derive(sp); n1 = len(sp["rules"]); reader.derive(sp)
    assert n1 == len(sp["rules"]) == before + 1 and sp["rules"][-1]["staff"] == "Zone computing class" and sp["rules"][:before] == S.plain_rules(sp)
    assert not any(i >= before for i, _ in solver.rule_problems(sp))

@t
def the_solver_keeps_a_teachers_lessons_out():            # only with --full
    if "--full" not in sys.argv: return
    sp = secondary(); who = next(x for x in sp["lessons"] if x.get("teachers"))["teachers"][0]
    sp["staff_periods"] = [dict(name="Zone computing class", all=False, depts=[], teachers=[who], week="Both", days=["Mon"], times=["07:40", "09:40"], place="")]
    res = solver.solve(copy.deepcopy(sp), time_limit=60)
    m = export.model_from_result(res); mon = [i for i, d in enumerate(m["days"]) if d.endswith("Mon")]
    assert [x for x in m["lessons"] if who in x["teachers"]] and not [x for x in m["lessons"] if who in x["teachers"] and x["d"] in mon and x["p"] < 6]

@t
def will_it_fit_and_the_database_know_the_list():
    # a teacher whose every lesson period of the cycle is taken by a teacher-only period (all weekdays, 07:40 to the end of the day):
    # step 7's sums (ttgen.checks, through the same call tests/test_check_sums.py makes) list that teacher as one no timetable can fit,
    # and do not list them without the row.
    # a timetable database written by ttgen.database from a model whose setup holds the list gives the same list back when it is read.
    ...

@t
def the_skill_names_the_sheet_and_the_version():
    s = open(os.path.join(ROOT, "skill/school-timetable-generator/SKILL.md"), encoding="utf-8").read()
    assert S.SKILL_VERSION == "2026-11.12" and "Skill version: 2026-11.12" in s and "`Teacher-only periods`" in s
    assert "Teacher-only periods" in open(os.path.join(ROOT, "README.md"), encoding="utf-8").read()
```

Check `solver.solve`'s real signature and result before relying on the `--full` test; keep the assertion (none of that teacher's lessons on a Monday in periods 0 to 5) whatever the call looks like. Write `will_it_fit_and_the_database_know_the_list` in full from its two comment lines, with the calls `tests/test_check_sums.py` and `ttgen/database.py` really offer; it must have both assertions.

- [ ] **Step 2: Run** `.venv/bin/python tests/test_staff_periods.py`. Expected: FAIL on `KeyError: 'staff_periods'`.

- [ ] **Step 3: Implement** the sheet in `ttgen/template.py` (next to the "Teacher availability" block; data validation for Week as that sheet has it) and its line in the README sheet's list; the reading in `ttgen/reader.py` (names lists with `names_list`; times with `_clock`); `"Teacher-only periods"` in `KNOWN_SHEETS`; the last line of `derive`; the skip in `rule_problems`; `"staff_periods"` in `normalise`'s defaults.

- [ ] **Step 4: Update the skill and the version.** In `SKILL.md`: the version line to `2026-11.12`; `Teacher-only periods` in the list of sheets (near line 23) and a row in the sheet table (near line 155): "Teacher-only periods | a weekly period for teachers with no students | Name, All teachers, Departments, Teachers, Week, Days, From, To, Place. Every teacher it names is not available in the periods the times overlap, as a Must `Not available`; `ttgen` does this when it reads the setup."; one sentence in the teachers' part of the model (near line 298) saying the same. In `README.md`: the version and one line naming the sheet. `SKILL_VERSION = "2026-11.12"` and the three pinned tests.

- [ ] **Step 5: Run** `.venv/bin/python tests/test_staff_periods.py`, `tests/test_check_sums.py`, `tests/test_combined.py`, `tests/test_parents.py`, `tests/test_rules.py`, `tests/test_typed.py`, `tests/smoke.py` (all PASS), then `.venv/bin/python tests/test_staff_periods.py --full` (PASS; run it alone, nothing else running).

- [ ] **Step 6: Copy and commit**

```bash
cp ttgen/spec.py ttgen/reader.py ttgen/template.py ttgen/solver.py skill/school-timetable-generator/scripts/ttgen/
diff -rq ttgen skill/school-timetable-generator/scripts/ttgen
git add -A ttgen skill README.md app.py tests
git commit -m "Teacher-only periods: the workbook sheet, derive, skill 2026-11.12"
```

---

### Task 3: Step 8's warning and the board's judge

**Files:**
- Modify: `ttgen/verify.py` (`_hit`, line 195; `_not_available`, line 211), `fixes.py` (`judge`, where `must`/`prefer` are filled from `rule_subjects`, about line 548)
- Test: `tests/test_verify.py`, `tests/test_fixes.py`, `tests/test_board.py`, `tests/test_refit.py`, `tests/test_helper.py`
- Copy: `ttgen/verify.py` to the skill

**Interfaces:**
- Consumes: the derived setup (`m["checked_setup"]`) now holds the marked block-outs in `rules` (Task 2), each with `_id`, `staff`, `times`, `target`, `day`.
- Produces:
  - A warning for a marked row: `key = f"rule:{r['_id']}:{verify._key(x, q)}"`, `kind="rule"`, `strength="Must"`, `group=teacher`, `text` the step 8 sentence with no `Rule …:` in front, `where` as other rule warnings, plus one more key on the warning dict: `staff` = the board's sentence.
  - `{lesson}` in the step 8 sentence is `verify._what(x)` ("English Language for 2B", "group 2EL3"); `{day}` is the model's day name; `{p}` the first period of the lesson inside the period; `{from}`/`{to}` are `clock12` of the row's times. In the board's sentence `{day}` is the weekday as the row wrote it (`r["day"]`).
  - `fixes.judge`: when a warning that is new after the fix has a `staff` key, its `staff` sentence goes into `must` in place of its `text`.

- [ ] **Step 1: Write the failing tests**

In `tests/test_verify.py` (uses its `model_for`):

```python
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
```

(Use a first day name the primary sample really has for `days=[...]`; the assertion on the key then uses that name.)

In `tests/test_fixes.py`, following the file's own helpers for a model and a judge call: `a_move_onto_a_teacher_only_period_is_no_and_can_be_forced` asserts for a move of a lesson of teacher T onto the period: `j["state"] == "no"`, `j["why"] == f"{T} has Staff meeting then (Mon 8.00 to 9.00)."`, `j["must"] == [j["why"]]`; the same for kinds `place`, `add` and `teacher` (giving the lesson to T); a move of a lesson already inside the period to another place inside it is not "no" for that reason (not broken anew); `fixes.slots(...)` counts the place among its refused ones and never as "ok".

In `tests/test_board.py`: `a_forced_lesson_on_a_teacher_only_period_publishes`: through the app (the file's own client and draft helpers) set `staff_periods` in the setup, force a move onto it (`FORCED` with the judge's sentence), assert the draft lists one open warning whose text is the step 8 sentence, `critical == 0`, and `POST` publish answers 200.

In `tests/test_refit.py` and `tests/test_helper.py`: with a period over a slot, no step of a Re-fit plan and no helper suggestion puts a lesson of that teacher into it; and `helper.suggest` on the staff warning does not raise and names no rule row other than the marked one (`helper._rule_row(m["checked_setup"], w["key"])[1]["staff"] == "Staff meeting"`).

- [ ] **Step 2: Run** the five suites. Expected: the new tests FAIL (`KeyError: 'staff'` or a text mismatch); every older test still passes.

- [ ] **Step 3: Implement** in `ttgen/verify.py`: `_not_available` builds the two sentences for a row with `staff` and sets `w["staff"]`; `_hit` leaves `Rule {label}: ` off for such a row. In `fixes.judge`: use `w.get("staff") or w["text"]` where a new rule warning's sentence is collected.

- [ ] **Step 4: Run** `tests/test_verify.py`, `tests/test_fixes.py`, `tests/test_board.py`, `tests/test_refit.py`, `tests/test_helper.py`, `tests/test_rules.py`, `tests/test_ask.py`, `tests/test_versions.py`, `tests/smoke.py`. All PASS.

- [ ] **Step 5: Copy and commit**

```bash
cp ttgen/verify.py skill/school-timetable-generator/scripts/ttgen/verify.py
diff -rq ttgen skill/school-timetable-generator/scripts/ttgen
git add ttgen/verify.py skill fixes.py tests
git commit -m "Teacher-only periods: step 8's warning and the board's sentence"
```

---

### Task 4: Step 6's list

**Files:**
- Create: `static/staffperiods.js`, `tests/staffperiods.test.js`
- Modify: `static/index.html` (a `<script src="/static/staffperiods.js">` line before `app.js`), `static/app.js` (`LIST_KEYS` line 99; `issues()` line 663; `stepAt` line 973 and the Things to fix click at 1891; the rules page at 1680 to 1713; the click and change handlers near 1861 and 2023; `addRow` line 2098), `static/sync.js:13` and `sync.py:19` (`LISTS`), `sync.py` `_head_why` (line 280), `history.py` (`WHERE` line 23, `_NAME_FIELD` line 27, `row_label` line 307), `static/teacherview.js` (`uses` line 83, `rename` line 131, `renameText` line 172), `static/style.css`
- Modify tests: `tests/sync.test.js:51`, `tests/test_sync.py:58` (the exact list), `tests/teacherview.test.js`, `tests/test_history.py`

**Interfaces:**
- Consumes: the row shape of Task 1.
- Produces (`static/staffperiods.js`, a module `StaffPeriods` in the pattern of `static/groups.js`, exported for Node):
  - `blank() -> row`: `{name: "", all: false, depts: [], teachers: [], week: "Both", days: [], times: ["15:00", "16:00"], place: ""}`.
  - `people(spec, row) -> string[]`, `faults(spec, row) -> [{hard: boolean, text: string}]`: the same answers and sentences as `ttgen.spec.staff_people` and `staff_faults`.
  - `whoLine(spec, row) -> string`: `""` for names only; `"58 teachers now. A new teacher is included."` for all teachers; `"9 teachers now."` for a row with a department (singular `"1 teacher now."`).
  - `blocksLine(school, row) -> string`: `"blocks periods 22 to 25"`, `"blocks period 22"`, with `" · after the last period (4.20 pm)"` and/or `" · before the first period (7.40 am)"` added when the times reach past the grid; `"after the last period (4.20 pm): it blocks no lesson"` / `"before the first period (7.40 am): it blocks no lesson"` when wholly outside; `""` when the times are not times.
  - `options(spec, row) -> {all: boolean, depts: string[], teachers: string[]}`: what "+ Add teachers" may still add (departments from step 4's teachers, first and second; teachers not yet named), in step 4's order.
- Sync: `"staff_periods"` is in `LISTS` in both files, so rows get `_id` and change by row. A head is refused: `"Department heads cannot change teacher-only periods."`.
- History: `WHERE["staff_periods"] = "Step 6 · Configuration & constraints"`; a row's label is its name, or `"a teacher-only period"` when it has none.
- Rename: `TeacherView.uses(spec, name).staff` is the list of row indexes whose `teachers` hold the name; `rename` changes them and counts `r.staff`; `renameText` adds `"1 teacher-only period"` / `"2 teacher-only periods"` to its list.

- [ ] **Step 1: Write the failing tests**

`tests/staffperiods.test.js` (fixture: three teachers as in Task 1's `school()`, `school = {start_time: "07:40", period_minutes: 20, periods_per_day: 26}`):

```js
t("people and faults agree with the server's", () => {
  assert.deepStrictEqual(SP.people(spec, ZONE), ["Mr Arjun Rao", "Mr Farhan Aziz"]);
  assert.deepStrictEqual(SP.people(spec, { ...ZONE, teachers: [], depts: ["English"] }), ["Mr Arjun Rao", "Ms Mei Ling Koh"]);
  assert.deepStrictEqual(SP.faults(spec, SP.blank()), [{ hard: true, text: "It has no name." }, { hard: true, text: "Nobody is in it." }, { hard: true, text: "It has no day." }]);
  assert.deepStrictEqual(SP.faults(spec, { ...ZONE, teachers: ["Mr Gone", "Mr Arjun Rao"] }), [{ hard: false, text: "Mr Gone is not on step 4." }]);
  assert.deepStrictEqual(SP.faults(spec, { ...ZONE, times: ["15:00", "14:00"] }), [{ hard: true, text: "Its To time is not after its From time." }]);
  assert.deepStrictEqual(SP.faults({ teachers: spec.teachers }, null), []);
});
t("the lines under a row", () => {
  assert.strictEqual(SP.whoLine(spec, ZONE), "");
  assert.strictEqual(SP.whoLine(spec, { ...ZONE, all: true }), "3 teachers now. A new teacher is included.");
  assert.strictEqual(SP.whoLine(spec, { ...ZONE, teachers: [], depts: ["English"] }), "2 teachers now.");
  assert.strictEqual(SP.blocksLine(school, ZONE), "blocks periods 22 to 25 · after the last period (4.20 pm)");
  assert.strictEqual(SP.blocksLine(school, { ...ZONE, times: ["14:20", "15:20"] }), "blocks periods 20 to 22");
  assert.strictEqual(SP.blocksLine(school, { ...ZONE, times: ["15:00", "15:20"] }), "blocks period 22");
  assert.strictEqual(SP.blocksLine(school, { ...ZONE, times: ["17:00", "18:00"] }), "after the last period (4.20 pm): it blocks no lesson");
  assert.strictEqual(SP.blocksLine(school, { ...ZONE, times: ["07:00", "08:00"] }), "blocks period 0 · before the first period (7.40 am)");
  assert.strictEqual(SP.blocksLine(school, { ...ZONE, times: ["", "x"] }), "");
});
t("what can still be added", () => {
  assert.deepStrictEqual(SP.options(spec, ZONE), { all: true, depts: ["English", "Mathematics"], teachers: ["Ms Mei Ling Koh"] });
  assert.deepStrictEqual(SP.options(spec, { ...ZONE, all: true }), { all: false, depts: [], teachers: [] });
});
```

`tests/teacherview.test.js`: a rename of "Mr Arjun Rao" to "Mr A Rao" with `spec.staff_periods = [ZONE]` leaves `spec.staff_periods[0].teachers` as `["Mr A Rao", "Mr Farhan Aziz"]`, `r.staff === 1`, and `renameText(r)` contains `"1 teacher-only period"`.

`tests/sync.test.js` and `tests/test_sync.py`: the pinned `LISTS` gain `"staff_periods"` after `"rules"`; a new test in each: adding a row gives an `add` op for section `staff_periods` with an `_id`, changing its `place` gives one `set` op, and (Python) a head's op on it is refused with the sentence above.

`tests/test_history.py`: a change of a row's `place` is listed under "Step 6 · Configuration & constraints" with the row's name as its label.

- [ ] **Step 2: Run** `node tests/staffperiods.test.js` (FAIL: cannot find module), `node tests/sync.test.js`, `node tests/teacherview.test.js`, `.venv/bin/python tests/test_sync.py`, `.venv/bin/python tests/test_history.py` (the new tests FAIL).

- [ ] **Step 3: Implement** `static/staffperiods.js`, the `LISTS` entries, the head refusal, the history labels and the rename.

- [ ] **Step 4: Run** the five suites. All PASS.

- [ ] **Step 5: Build the list on the page** (`static/app.js`, `static/style.css`), as part 1 of the mockup:
  - On step 6's Teachers tab, before the "Teacher availability" block (line 1710): heading "Teacher-only periods"; under it the paragraph from the spec ("A period for teachers with no students, the same every week: a meeting, a zone class. It shows on their timetables. Lessons are kept away from it; a lesson you put there by hand gets a warning. A change here shows on the published timetable after you publish again on step 9."); a table with the column heads of Global Constraints; "+ Add a teacher-only period" (`data-add="staffp"`).
  - A row is `<tr id="staff_periods-${i}">` with the row colour and message of the other rule tables (`rowCls(out, crit, "staff_periods", i)`, `msg`): name (`inp("spec.staff_periods.${i}.name", …)`, `maxlength="60"`); "Who" as chips, each with ✕ (`data-spx="${i}|all"`, `"${i}|d|${dept}"`, `"${i}|t|${name}"`), then `<select data-spadd="${i}">` whose first option is "+ Add teachers" and whose option groups come from `StaffPeriods.options` ("All teachers", "Departments", "Teachers"), then `StaffPeriods.whoLine`; week (`sel`, the page's `weeks`); one button a weekday (`data-spday="${i}|${day}"`, class `on` when chosen; the weekdays are the page's `days` without "All"); From and To (`<input type="time" data-sptime="${i}|0">`, `…|1`), under them `StaffPeriods.blocksLine`; place (`inp`, `maxlength="60"`); `delBtn("staff_periods", i)`.
  - Handlers beside the existing ones: `data-spx` removes that chip; `data-spadd` adds the chosen department or teacher or sets `all` (choosing "All teachers" keeps the names and departments the row had, so taking "All teachers" off again shows them); `data-spday` toggles the day, keeping the days in weekday order; `data-sptime` sets `times[k]`; each then `save(); render();`. `addRow("staffp")` pushes `StaffPeriods.blank()` into `S.spec.staff_periods` and scrolls to the new row.
  - `LIST_KEYS` gains `"staff_periods"`. The Teachers tab's counter adds `S.spec.staff_periods.length`.
  - `issues()` adds `add("staff_periods", i, "Teacher-only period " + (row.name || "(no name)") + ": " + f.text, false)` for every fault of every row. They are never critical. `stepAt("staff_periods")` is step 6. A click on such an entry in "Things to fix" sets `R6.tab = "teachers"` before it scrolls to the row.
  - For a reader who cannot edit step 6 (`locked`), the list shows read-only like the tables around it.
  - After the edit run `node --check static/app.js`. Then list the names the changed stretch of `app.js` defined before (`git diff` for removed `const`/`function` lines) and check each is still defined or no longer used.

- [ ] **Step 6: Check it in a browser** on the sample school (a scratch data folder, served as `http://staffp.localhost:<port>`): add the three rows of the mockup with real clicks and typing; take a chip off; change days and times and see the lines under them; make each fault and see it in "Things to fix", and click through from there while another tab of step 6 is open; reload and see the rows kept; rename a teacher on step 4 and see the chip follow; delete a row; then use every older control of the Teachers tab once ("+ Add block-out", its time boxes, its ✕). Open History and see the changes named.

- [ ] **Step 7: Commit**

```bash
git add static sync.py history.py tests
git commit -m "Teacher-only periods: the list on step 6"
```

---

### Task 5: The teacher's timetable: page, printout, Excel, "Who's free"

**Files:**
- Modify: `ttgen/export.py` (`teacher_view` line 504; `draw_page` line 683 and the legend drawing near 774; `write_excel`'s `grid_sheet` line 876; `html_data` line 996), `ttgen/timetable_page.html` (`teacherView` line 221, `gridHTML` line 300, `viewHTML`'s legend near 318, `renderFree` line 494, the CSS near line 60, the staff-mode fetch near line 580), `app.py` (a new route beside `exams_my_duties`, line 3388)
- Test: `tests/test_staff_periods.py`, `tests/timetable_page.test.js`, `tests/test_routes.py`
- Copy: `ttgen/export.py`, `ttgen/timetable_page.html` to the skill

**Interfaces:**
- Consumes: `spec.staff_items(m["setup"])`, `clock12`, `staff_legend_line`, `staff_rows`.
- Produces:
  - `export.staff_cells(m, teacher=None) -> list[dict]`: from `m["setup"]`, one per item and per model day the item falls on (`verify.rule_days(m["days"], item)`): `dict(teacher, d, p, n, name, place, t0, t1, before, after, key)`; `p`, `n` from the item's periods (`p=None, n=0` when it has none); `t0`, `t1` 12-hour; `key` the item's `id`. `teacher=None` gives everyone's.
  - `export.staff_lines(m, teacher) -> list[str]`: the legend line of each row the teacher is in, in the list's order, each row once.
  - `teacher_view(m, t)`: `cells` gain, for each staff cell with periods, `dict(d, p, n, title=name, lines=[time, place], color=None, ext=False, id=None, staff=True, before=…, after=…)` where `time` is `"3.00–4.20"`, or `"3.00 (to 5.30)"` when `after`, `"(from 7.00) 8.00"` when `before`; `legend` gains `dict(color=None, label="", text=line, staff=True)` for each of `staff_lines`. `stats`, `subtitle` and every count are unchanged.
  - `html_data(m, view, …)["staff"]`: for `view == "full"`, a list of `[teacher, d, p, n, name, place, t0, t1, before, after]` (`p` is `null` for a period with no box) plus `html_data(...)["staff_lines"] = {teacher: [line, …]}`; for `student`, `staff` and `personal` both are `[]` / `{}`.
  - Route `GET /api/timetable/my-periods` (`@need("timetable")`, the name found as `exams_my_duties` finds it, 403 for a shared code or a student): `{"staff": [rows as above, the viewer's only], "lines": [line, …]}`.
  - In the page: a global `STAFF` (rows) and `STAFF_LINES` filled from `D.staff`/`D.staff_lines`, or in staff mode from the route; `teacherView(t)` adds the cells and legend entries; `.cell.staff` is white with a dark outline and has no `data-id`; a class `cut-r` / `cut-l` gives the broken edge; `renderFree` adds a teacher to the busy set when a staff row of that teacher is on the day and its periods overlap the range.

- [ ] **Step 1: Write the failing tests**

`tests/test_staff_periods.py` (a model as `tests/test_combined.py` `model_for` builds one, from `secondary()` with its school set to 07:40, 20 minutes, 26 periods; teacher `T` teaches one lesson on the first Tuesday, periods 22 to 24):

```python
@t
def the_teachers_view_gets_the_box_and_the_line_and_no_new_counts():
    m0 = model_for(sp0, PLACED); m = model_for(sp_with_zone, PLACED)        # ZONE: Tue and Thu 15:00-17:30 for T, place "West Zone centre"
    v0, v = export.teacher_view(m0, T), export.teacher_view(m, T)
    boxes = [c for c in v["cells"] if c.get("staff")]
    assert v["stats"] == v0["stats"] and v["subtitle"] == v0["subtitle"] and len(v["cells"]) == len(v0["cells"]) + len(boxes)
    assert len(boxes) == sum(1 for d in m["days"] if d.split()[-1] in ("Tue", "Thu")) and all((c["p"], c["n"], c["after"], c["before"]) == (22, 4, True, False) for c in boxes)
    assert boxes[0]["title"] == "Zone computing class" and boxes[0]["lines"] == ["3.00 (to 5.30)", "West Zone centre"] and boxes[0]["id"] is None
    assert [e["text"] for e in v["legend"] if e.get("staff")] == ["Zone computing class · Tue and Thu · 3.00 to 5.30 · West Zone centre"]
    assert not any(c.get("staff") for c in export.class_view(m, CLS)["cells"]) and not any(c.get("staff") for c in export.room_view(m, ROOM)["cells"])
    assert [v_["key"] for v_ in export.all_views(m, "teachers")] == [v_["key"] for v_ in export.all_views(m0, "teachers")]      # a teacher with no lessons still has no page

@t
def a_period_wholly_outside_the_day_is_a_line_only():
    m = model_for(sp_with_briefing, PLACED)                                   # 07:00-07:30 Mon for T
    v = export.teacher_view(m, T)
    assert not [c for c in v["cells"] if c.get("staff")] and [e["text"] for e in v["legend"] if e.get("staff")] == ["Briefing · Mon · 7.00 to 7.30"]

@t
def the_page_data_by_view():
    m = model_for(sp_with_zone, PLACED)
    full = export.html_data(m, "full")
    assert [T, m["days"].index(next(d for d in m["days"] if d.endswith("Tue"))), 22, 4, "Zone computing class", "West Zone centre", "3.00", "5.30", False, True] in full["staff"]
    assert full["staff_lines"] == {T: ["Zone computing class · Tue and Thu · 3.00 to 5.30 · West Zone centre"]}
    for view in ("student", "staff"): assert export.html_data(m, view)["staff"] == [] and export.html_data(m, view)["staff_lines"] == {}
    sid = m["students"][0]["id"]; assert export.html_data(m, "personal", student_id=sid)["staff"] == []
    assert "Zone computing class" not in json.dumps(export.html_data(m, "student")) and "Zone computing class" not in json.dumps(export.html_data(m, "personal", student_id=sid))

@t
def the_printout_and_the_excel_file_keep_the_lesson():
    m = model_for(sp_with_zone, PLACED)                                       # T's lesson sits inside the period on the first Tuesday
    assert export.pdf_bytes(m, export.teacher_view(m, T))[:4] == b"%PDF"
    lanes = export._lanes(export.teacher_view(m, T)["cells"]); tue = [c for c in export.teacher_view(m, T)["cells"] if c["d"] == TUE and c["p"] >= 22]
    assert len(tue) == 2 and {lanes[id(c)][1] for c in tue} == {2}             # they share the row, neither hides the other
    path = os.path.join(tempfile.mkdtemp(), "x.xlsx"); export.write_excel(m, path, log=lambda *a: None)
    ws = openpyxl.load_workbook(path)[TEACHER_SHEET]; text = " ".join(str(c.value) for row in ws.iter_rows() for c in row if c.value)
    assert "Zone computing class" in text and SUBJECT_SHORT in text and "Zone computing class · Tue and Thu · 3.00 to 5.30 · West Zone centre" in text
```

(`TEACHER_SHEET` is the sheet `grid_sheet` makes for teachers; read its name from `write_excel`.)

`tests/timetable_page.test.js` (its `boot` and `data` helpers): with `D.staff` holding one row for a teacher, `teacherView(name).rows` holds a cell with `staff: true` and the legend holds the line; the HTML of the grid has a `cell staff cut-r` element with no `data-id` that contains "Zone computing class" and "to 5.30"; `stats` equal those without `D.staff`; `classView` of the teacher's class holds no staff cell; in `renderFree` for that day and periods 22 to 23 the teacher is not listed, and is listed for periods 1 to 3; in staff mode with `D.staff = []` and the fetch map answering `/api/timetable/my-periods`, the viewer's own view shows the box.

`tests/test_routes.py` (its client and sign-in helpers, a published sample with a period for teacher A): a teacher signed in as A gets their rows from `/api/timetable/my-periods` and none of B's; B gets `{"staff": [], "lines": []}`; a student gets 403; the cached staff page's HTML for A and for B does not contain the period's name; and with a draft uploaded, the committee's `/draft/preview` HTML contains the period's name (it is made from the setup as it is now).

- [ ] **Step 2: Run** the three suites. Expected: the new tests FAIL (`AttributeError: … 'staff_cells'`, missing `D.staff`, 404).

- [ ] **Step 3: Implement the exporter**: `staff_cells`, `staff_lines`, `teacher_view`, `html_data`; in `draw_page` a branch for a cell with `staff` (white fill, outline `#5B6677` 1 pt, the accent bar in the same colour, a dashed right edge when `after` and left when `before`, the text in the page's ink colour) and for a legend entry with `staff` (a white outlined swatch); in `grid_sheet` a white fill with a thin dark border for a staff cell, and where a slot holds a lesson and a period the cell keeps the lesson's fill and its text gains ` / {name}`.

- [ ] **Step 4: Implement the page and the route**: the CSS (`.cell.staff{background:#fff;border:1.5px solid #5B6677;border-left-width:4px;color:inherit}`, `.cell.staff.cut-r{border-right-style:dashed}`, `.cell.staff.cut-l{border-left-style:dashed}`), `teacherView`, the legend entries, `renderFree`, the staff-mode fetch, and `GET /api/timetable/my-periods`. Cut the last `<script>` out of the template and run `node --check` on it.

- [ ] **Step 5: Run** `tests/test_staff_periods.py`, `node tests/timetable_page.test.js`, `tests/test_routes.py`, `tests/smoke.py`, `tests/test_combined.py`, `tests/test_staff_passwords.py`. All PASS.

- [ ] **Step 6: Look at it.** On a scratch server with the sample school published with the three mockup rows: open a teacher's page as the committee and as that teacher; open a class page and a student's page; open "Who's free" for the period's time; make one teacher's PDF and turn it to a picture (`sips -s format png x.pdf --out x.png`) and look at the box, the broken edge and the legend line. Compare with part 2 of the mockup.

- [ ] **Step 7: Copy and commit**

```bash
cp ttgen/export.py ttgen/timetable_page.html skill/school-timetable-generator/scripts/ttgen/
diff -rq ttgen skill/school-timetable-generator/scripts/ttgen
git add ttgen skill app.py tests
git commit -m "Teacher-only periods: the teacher's page, printout, Excel sheet and Who's free"
```

---

### Task 6: Step 8's board

**Files:**
- Modify: `draft.py` (`board()`, line 451, the dict returned near line 487), `static/board.js` (beside `personRow`, line 82), `static/app.js` (`bdRowHTML` line 4359, `bdPieces` line 4336), `static/style.css`
- Test: `tests/test_board.py`, `tests/board.test.js`

**Interfaces:**
- Consumes: `export.staff_cells(m)` (Task 5), read from the draft's model, whose `m["setup"]` is the setup as it is now.
- Produces:
  - `draft.board()["staff"]`: `[dict(teacher, d, p, n, name, place, t0, t1, before, after)]`, only cells with periods.
  - `Board.staffOf(board, name, d) -> [{p, n, name, place, t0, t1, before, after}]`: that teacher's boxes on day `d`, by `p`; `[]` when `board.staff` is missing.
  - On a teacher's row (rows by teacher, and a teacher's whole cycle), each box is a `<div class="bdstaff">` laid over its periods: not a button, not draggable, no `data-id`, with the name and `"3.00–4.20"` / `"3.00 (to 5.30)"`, and `title` holding name, times and place. Class rows and room rows get none.

- [ ] **Step 1: Write the failing tests**

`tests/board.test.js`: `Board.staffOf({ staff: [{ teacher: "A", d: 1, p: 22, n: 4, name: "Zone", place: "", t0: "3.00", t1: "5.30", before: false, after: true }, { teacher: "B", d: 1, p: 0, n: 2, name: "Briefing", place: "", t0: "7.40", t1: "8.20", before: false, after: false }] }, "A", 1)` equals the first row without `teacher` and `d`; `staffOf(board, "A", 0)` and `staffOf({}, "A", 1)` are `[]`.

`tests/test_board.py`: with `staff_periods` in the setup, `GET /api/draft/board` holds `staff` rows for the row's teachers on its days and none for other teachers; the cards (`cards`) and every count of the board are the same as without the list; after the row is deleted from the setup the next board has `staff == []`.

- [ ] **Step 2: Run** `node tests/board.test.js` and `.venv/bin/python tests/test_board.py`. Expected: the new tests FAIL.

- [ ] **Step 3: Implement** `draft.board()`'s `staff`, `Board.staffOf`, and the boxes in `bdRowHTML` for `row.by === "teacher"` (a grid item on the row's first lane, behind the cards: `z-index` below a card's, `pointer-events:none` so a drop on the place still reaches the board's drop handling). Run `node --check static/app.js`.

- [ ] **Step 4: Run** `node tests/board.test.js`, `tests/test_board.py`, `tests/test_fixes.py`, `node tests/draft.test.js`. All PASS.

- [ ] **Step 5: Check it in a browser** with a real mouse, on the sample school with the three mockup rows and an uploaded draft: "Rows: Teachers" shows the boxes on the right teachers and days; a teacher's whole cycle shows them; a lesson of that teacher dragged onto a box opens the drop box with the board's sentence and "Put it here anyway" (part 3 of the mockup), and the forced lesson and the box are both visible; Cancel leaves the lesson where it was; a lesson of another teacher dropped there goes in with no such sentence; the box itself cannot be dragged or clicked open. Then once each: an ordinary drag, click-then-click move, Lift out, the tray, Undo. Say for each check whether it was a real click or drag.

- [ ] **Step 6: Commit**

```bash
git add draft.py static tests
git commit -m "Teacher-only periods: fixed boxes on step 8's teacher rows"
```

---

### Task 7: Relief

**Files:**
- Modify: `relief/free.py` (`free_then`, lines 120 and 144 to 150), `static/relief-plan.js` (`freeList`, lines 100 to 121)
- Test: `tests/test_relief_requests.py`, `tests/test_relief.py`, the Node test that covers `freeList` (find it with `grep -l freeList tests/*.test.js`)

**Interfaces:**
- Consumes: `ttgen.spec.rules_with_staff(setup)`; a marked row has `staff` (the name).
- Produces:
  - `free_then(...)`: reads `rules_with_staff(model.get("setup") or {})`. A person a marked Must row hits is not in `groups` and is in `busy` as `dict(name=name, why=f"Teacher-only period: {r['staff']}")`. A plain Must "Not available" still drops the person silently.
  - `freeList` fold label: `"the ${n} busy then (an exam duty, an event or a teacher-only period)"`; each entry stays `"{name} ({why})"`.

- [ ] **Step 1: Write the failing tests**

`tests/test_relief_requests.py` (its `world`, `settings`, `lesson_of` helpers; `world` sets `pub["model"]["setup"]["rules"]`, so set `pub["model"]["setup"]["staff_periods"]` and the setup's `school` times the same way):

```python
@t
def a_teacher_in_a_teacher_only_period_is_busy_with_its_name():
    pub = world(); setup = pub["model"]["setup"]
    setup["staff_periods"] = [dict(_id="s1", name="Staff meeting", all=False, depts=[], teachers=[MAYA], week="Both", days=[DAY_OF_THE_LESSON], times=TIMES_OVER_THE_LESSON, place="")]
    got = free_then(pub, settings(), [], lesson_of(pub), ABSENT)
    names = [p["name"] for g in got["groups"] for p in g["people"]]
    assert MAYA not in names and dict(name=MAYA, why="Teacher-only period: Staff meeting") in got["busy"]
    setup["staff_periods"][0]["days"] = [ANOTHER_DAY]
    got = free_then(pub, settings(), [], lesson_of(pub), ABSENT)
    assert MAYA in [p["name"] for g in got["groups"] for p in g["people"]] and not got["busy"]
```

`tests/test_relief.py`: for a teacher in a period who is absent that day, `relief.lessons.on_date(pub, cal, teacher, date)` returns exactly what it returns without the list (no entry for the period), and `teaching_periods` is unchanged.

The Node test: `freeList` with two busy entries renders the new fold label and both `"name (why)"`.

- [ ] **Step 2: Run** the suites. Expected: the new tests FAIL.

- [ ] **Step 3: Implement** the two changes.

- [ ] **Step 4: Run** `tests/test_relief.py`, `tests/test_relief_requests.py`, `tests/test_relief_team.py`, `tests/test_relief_telegram.py`, `tests/test_exams_relief.py`, and the `relief_*.test.js` suites. All PASS.

- [ ] **Step 5: Commit**

```bash
git add relief static/relief-plan.js tests
git commit -m "Teacher-only periods: busy for relief, with the period's name"
```

---

### Task 8: Exams and events: a mark, never a refusal

**Files:**
- Modify: `exams/days.py` (`day_view`, lines 186 to 207), `exams/invigilate.py` (`candidates` line 101, `_check_names` line 176, `assign`'s order at line 277), `exams/events.py` (`going` line 76, `who_free` line 251), `exams/approval.py` (where `not_free` is copied or popped, lines 294 and 304), `app.py` (`_exam_away` line 3556, `_event_away` line 3757), `static/exams.js` (lines 897, 915, 919, 952, 1053, 1074)
- Test: `tests/test_exams.py`, `tests/test_exams_relief.py`, `tests/exams.test.js`

**Interfaces:**
- Consumes: `ttgen.spec.staff_items(setup)`, `plain_rules(setup)`, `exams.days.rule_on_day`.
- Produces:
  - `day_view(...)["blocked"]`: built from `plain_rules(setup)` only (a marked row never blocks).
  - `day_view(...)["periods"]`: `{teacher: [(start, end, name), …]}` in minutes, from the items on that timetable day, by start; the item's own clock times, not cut to the grid.
  - `invigilate.marked(name, view, start, end) -> str`: `"has {name} then"` for the first of the teacher's periods that overlaps `start`..`end`, else `""`.
  - `candidates(...)`: a fifth group `"period"`. A person with no `why` from `_free`, no running lesson, not a backup invigilator, and a mark, goes to `period` with `reason` = the mark (in place of `free` or `freed`). A person with a running lesson stays in `need_backup`, the mark added to the reason after `"; "`.
  - `assign(...)`: walks `("freed", "free", "backups", "period", "need_backup")`.
  - `_check_names(...)`: beside `d["not_free"]`, sets `d["marks"] = {name: mark}` for chosen names that are free and have a mark; `approval.py` carries `marks` wherever it carries `not_free`.
  - `events.going(...)`: a person who is free and has a mark gets `status="period"`, `text=mark`. `events.people_lines` and `send_errors` are unchanged: a mark is not a clash. `events.who_free(...)` returns a third list `period=[{name, reason}]`.
  - `_exam_away` accepts a name from `("freed", "free", "backups", "period")`; `_event_away` from `("freed", "free", "period")`.
  - `static/exams.js`: the group tables gain `["period", "In a teacher-only period"]` after the free groups (and after backups where those are listed); a mark renders as `<span class="flag soft">{name}: {mark}</span>` where `Not free:` flags render; an event's going row with `status === "period"` is muted amber with its text.

- [ ] **Step 1: Write the failing tests**

`tests/test_exams.py` (its `_PUB`, `_xset`, `_sched` helpers; `exams/fake.py` `sample_pub()` has 26 periods of 20 minutes from 07:40 and blocks "Mr Ivan Lee" on Mondays, periods 0 to 5; put `staff_periods` into `pub["model"]["setup"]` for another teacher `P`, Monday 15:00 to 17:30, name "Zone computing class", and give the setup the `school` times and `teachers` rows the items need):

```python
@t
def a_teacher_only_period_marks_and_never_blocks():
    view = days.day_view(pub, cal, sched, MONDAY)
    assert P not in view["blocked"] and view["periods"][P] == [(900, 1050, "Zone computing class")] and view["blocked"]["Mr Ivan Lee"] == [(460, 580)]
    assert INV._free(P, view, 930, 990, [], xset)[0] == "" and INV.marked(P, view, 930, 990) == "has Zone computing class then"
    assert INV.marked(P, view, 1050, 1100) == "" and INV.marked(P, view, 990, 1080) == "has Zone computing class then"      # an exam that runs after the last period
    got = INV.candidates(pub, cal, sched, xset, MONDAY, 930, 990, [])
    assert [c["name"] for c in got["period"]] == [P] and got["period"][0]["reason"] == "has Zone computing class then"
    assert P not in [c["name"] for g in ("freed", "free", "backups", "need_backup") for c in got[g]]

```

`make_calls_them_only_when_the_free_run_out`, written with the file's own way of making a schedule and calling `assign`: one room and one invigilator needed, at a time when F is free and P is in a period, gives the names `[F]`; the same with F on the never list (nobody else free) gives `[P]`, with `duty["marks"] == {P: "has Zone computing class then"}` and `duty.get("not_free") in (None, {})`.

Further tests in `tests/test_exams.py`, each with the file's own helpers:
- `a_name_chosen_by_hand_is_kept_with_a_mark`: `_check_names` gives `marks == {P: "has Zone computing class then"}` and no `not_free` for P; for "Mr Ivan Lee" on a Monday morning `not_free` still says `"is not available then (a Must rule)"`.
- `an_event_with_such_a_person_can_be_sent`: `events.going(...)` gives P `status == "period"` and the mark; `events.clashes(...) == []`; `events.send_errors(...) == []`; `events.who_free(...)["period"]` names P.
- `a_replacement_in_a_period_is_accepted`: through the app's routes for an approved exam and an approved event, replacing with P answers 200 and with "Mr Ivan Lee" on a Monday morning still answers the refusal `"… is not free then."`.

`tests/test_exams_relief.py`: one test that relief's "elsewhere" busies and a period together still give the mark only (`INV._free` empty, `marked` set).

`tests/exams.test.js`: the candidates panel renders the group title "In a teacher-only period" with its people after "Free then"; a duty row with `marks` renders `flag soft` with the mark and no "Not free:".

- [ ] **Step 2: Run** `tests/test_exams.py`, `tests/test_exams_relief.py`, `node tests/exams.test.js`. Expected: the new tests FAIL (`KeyError: 'periods'`).

- [ ] **Step 3: Implement** `day_view`, `marked`, `candidates`, `assign`'s order, `_check_names`, `approval.py`'s carrying of `marks`, `events.going` and `who_free`, the two routes, and `static/exams.js` (with a `.flag.soft` style beside `.flag`).

- [ ] **Step 4: Run** `tests/test_exams.py`, `tests/test_exams_relief.py`, `node tests/exams.test.js`, `tests/test_plan.py`, `tests/smoke.py`. All PASS.

- [ ] **Step 5: Commit**

```bash
git add exams app.py static tests
git commit -m "Teacher-only periods: a mark, never a refusal, for exams and events"
```

---

### Task 9: Everything together

**Files:**
- Create: `docs/superpowers/plans/2026-11-27-staff-periods-notes.md`
- Modify: whatever the checks below find

- [ ] **Step 1: Every suite, quick.** Run each `tests/test_*.py` and `tests/smoke.py` with `.venv/bin/python`, each `tests/*.test.js` with `node`, and `node --check static/app.js`. Judge each by its exit status (`if out=$(cmd 2>&1); then …`) and its last line. Expected: all PASS.

- [ ] **Step 2: The slow suites**, one at a time with nothing else running: `--full` for `tests/test_typed.py`, `tests/test_helper.py`, `tests/test_fixes.py`, `tests/smoke.py`, `tests/test_staff_periods.py`, `tests/test_combined.py`. A failure of `test_helper.py --full` or `test_typed.py --full` is compared with the same suite on `origin/main` in a detached scratch worktree before it is called a fault of this branch.

- [ ] **Step 3: The copy.** `diff -rq ttgen skill/school-timetable-generator/scripts/ttgen` prints nothing.

- [ ] **Step 4: The whole path in a browser**, real mouse, sample school, a scratch data folder served as `http://staffp.localhost:<port>`: step 6 add the three mockup rows; step 7 "Will it fit?" runs; step 8 upload the sample timetable, see any warning, force one lesson onto a period, see the warning on the list with "Show me"; step 9 publish; the teacher's page (box, broken edge, legend line), a class page and a student page (nothing), "Who's free"; a teacher signed in with a password account sees their own box and nobody else's; Plan relief for an absent teacher at the period's time (the teacher in the period listed busy with the reason; no cover asked for the period); Exams: candidates for a paper at that time show the group "In a teacher-only period", a name chosen by hand carries the soft mark, an event with that person can be sent. Then change a row on step 6 and publish again from step 9 without a new upload: the published page follows.

- [ ] **Step 5: The school's real setup, counts only.** On a scratch copy of the data folder (never the real one; deleted afterwards; nothing printed but counts): add one row for all teachers on one weekday at a time when lessons run, through the app's API on a scratch server; the number of new warnings on step 8 equals the number of lessons with a teacher that overlap it on that weekday; the board, the published page data and the PDF book are made without an error; take the row out and the count of warnings is the count before. Delete the copy.

- [ ] **Step 6: Write the notes file**: what was decided while building, known limits (those of the spec, and any found), what was and was not tried in a browser and with which kind of action, the counts from Step 5.

- [ ] **Step 7: Commit**

```bash
git add docs/superpowers/plans/2026-11-27-staff-periods-notes.md
git commit -m "Teacher-only periods: notes"
```

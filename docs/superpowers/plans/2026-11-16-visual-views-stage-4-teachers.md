# Visual views, stage 4: teachers, two departments, no "Can teach" (steps 4, 5 and 8) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The app stops asking what each teacher can teach; a teacher can have a second department; step 4 gets teacher cards with the Roles table below; step 5's department page gives its space to the classes and teaching groups; step 8 still has teachers to offer.

**Architecture:** A teacher row keeps `dept` (the home department) and gains `dept2`; one small function per language (`spec.teacher_depts` in Python, `People.depts` in the page) answers "which departments is this teacher in" and everything else asks it. The workbook's Teachers sheet loses its Can teach columns and gains Department 2, and the skill's version rises. On the page a new pure module `static/teacherview.js` (`TeacherView`) makes step 4's cards and `static/map.js` (`DeptMap`) gains `page()`, the level-first layout of step 5; `static/app.js` draws both. A stored `can_teach` is left on the teacher and never read.

**Tech Stack:** Python 3 (Flask app, `ttgen` package, openpyxl, plain-assert test scripts), vanilla JS in the browser (no build step), Node for the page modules' tests.

**Spec:** `docs/superpowers/specs/2026-11-15-visual-setup-views-design.md` (stage 4, "Across all four stages", "What would make this a failure"). Stage 3's plan and notes, for the patterns to repeat: `docs/superpowers/plans/2026-11-15-visual-views-stage-3-subjects.md`, `…-stage-3-notes.md`. Branch `visual-views-stage-4`, from `main` at de3714f.

## Global Constraints

- **"Can teach" is gone from everything a person or the outside agent meets.** At the end of the branch "Can teach" (the list's name), "who can teach", "basket", "Staff room" and "not set to teach" appear nowhere in `static/`, `ttgen/`, `README.md` or `docs/DEPLOY.md`, and "Can teach" appears in `skill/` only in the one sentence of `SKILL.md` that tells the agent to ignore those columns in an older workbook. (The checks' sentence about the periods a teacher "can teach in" is about time and stays.) `can_teach` appears only in `sync.py`, `static/sync.js` and their tests (decision 3).
- **Nothing is converted and nothing is lost.** A setup saved before this stage (teachers with `can_teach`, no `dept2`) opens as it is: the `can_teach` list stays on the row untouched and is never read, shown or written to a workbook. A workbook from before (Can teach columns, no Department 2) opens with every other cell read as before.
- **Two departments at most.** `dept` is the home department, `dept2` the second. A `dept2` that is empty or equal to `dept` means none. "Is this teacher in department D" is asked only through `spec.teacher_depts` (Python) and `People.depts` / `People.inDept` (page): either department counts. Where one department is needed (the published pages, the exports, a list grouped by department) it is `dept`, and `ttgen/export.py` and `ttgen/database.py` do not change. A teacher's load counts once.
- **Only the committee gives a second department.** A department head cannot set `dept2`, even on a provisional teacher or a teacher they add; the server refuses or strips it and the page shows it disabled. Placing a teacher from "Others" on step 5 never changes the teacher's departments.
- **Heads otherwise as today.** On step 4 a head adds teachers (provisional) and edits a provisional teacher only. On step 5 a head may place any teacher on any class or group, except the lessons the Class Parents rule holds (`cpBlock`), as today. Every new handler checks the lock itself as well as being disabled.
- **The Table views stay.** Step 4's Table is today's table less the Can teach column, plus a Department 2 column after Department. Step 5's "Groups and bands" and "Table" views change only where this plan says (the teacher drop-downs and the tick bar).
- **One set of data.** A field in an open teacher card is the table's own `data-k` path (`spec.teachers.{i}.name` and so on). Each action (a second department given or taken off, a teacher placed or taken off a card) is one save and one Undo step, followed by the same `save(); render();` the existing actions use.
- **Every drag has a click.** Nothing can be done only by dragging: a second department is also a box in the open card and in the Table; placing a teacher is also tick and click.
- **The views are remembered** per person in the browser: step 4 under `ttsetup.view.teachers`, opening on Cards the first time.
- `ttgen/` and `skill/school-timetable-generator/scripts/ttgen/` stay byte-identical (`diff -rq` prints nothing). The skill's version becomes `2026-11.5` everywhere it is named: `ttgen/spec.py` `SKILL_VERSION`, `SKILL.md`, `README.md`, and the two tests that pin it (`tests/test_parents.py`, `tests/test_rules.py`).
- Everything a person typed is drawn through `esc()`, in text and in attributes. A department's name carried in an attribute for a handler is encoded with `encodeURIComponent`, as stage 2's `data-vadd` is.
- No new style rule may match an element that existed before. New class names start with `tk` (step 4) and `dp` (step 5); grep each in `static/style.css` and `static/app.js` before using it.
- `render()`'s code that restores the keyboard focus is being changed on another branch (`tab-keeps-place`). Do not edit it here.
- **The school's size (counts from the real setup):** 92 teachers in 9 of the school's 11 departments (the largest has 17), 460 lesson rows, 59 bands, 4 levels; the largest department's page on step 5 has 69 cards, the largest level of one department 20. 67 of the 92 teachers teach at least one subject of a department that is not theirs, 14 of them in two or more. Step 4's Cards and every department's page must draw and answer a change without a pause a person would notice.
- Sentences are plain and short, and name things as the page already does (Teacher, Short, Department, Allowance, Role, Other duties, Provisional, the school's own word for Class Parents through `Parents.label`).
- Tests, samples and documents use made-up names only. The school is "CTSS" or "the school". A run on the real setup reports counts only.
- Browser checks run on a scratch server with a scratch `DATA_DIR` and the README's example codes, never the repository's `data/`. No test or check calls a model API.
- `tests/test_helper.py --full` fails about one run in three on `main` with a suggestion that swaps a group with itself (being fixed on branch `helper-full-flake`). That one failure is not this branch's; any other is.
- Commits end with `Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>`. Nothing is pushed.

## Decisions this plan makes (to be checked on reading)

The spec leaves these open. Each is the plan writer's call.

1. **A department's "Keep free together" rule keeps a second-department teacher free too.** The spec says either department counts "wherever the app asks is this teacher in this department". The one place outside steps 4 and 5 that asks is this rule (the outside agent's solver and report, the checks before download, the check of a returned timetable, the Fix card). So a teacher in Mathematics and Science is kept free at both departments' meeting times. The school's real setup has no such rule today, so nothing changes for it now.
2. **How the two are held.** `dept` stays as it is; `dept2` is a new plain field. The page takes a `dept2` off when it becomes empty or equal to `dept`.
3. **The stored list stays, and so does its name in the change format.** `sync.py` and `static/sync.js` keep `can_teach` in their list of merged fields, so a page left open across the change can still save. Nothing else names it. New teachers are made without it.
4. **`ttgen/allocate.py` is removed** (both copies). Nothing calls it and it exists only to read Can teach.
5. **Step 5 is one page, not three tabs.** Classes, Teaching groups and Bands were tabs. Now each level is a section; inside it each subject (in step 3's order) has its class cards, then its groups that are in no band; a band is a lane under its name, placed where its first subject would be. A lane shows only the groups of this department's subjects, as today.
6. **"Its students" is the planned number.** A class card shows the class's size from step 2; a group card shows the group's Students from step 5; nothing when blank. The real count from the student list is not shown here.
7. **"Not placed yet" becomes "No lessons yet":** it ticks the teachers of the page who are on no lesson row.
8. **Step 5's table view** lists a subject's department's teachers (home or second) first, under the department's name, then "Others". This takes the place of "Can teach this".
9. **Step 4's "Can teach …" filter goes.** The department filter counts either department. The tick bar keeps department (the home one), role and allowance.
10. **A second department by clicking** is a "Second department" box, in the open card and in the Table. The ✕ on its chip takes it off. Dropping a chip on a teacher who already has a second department replaces it and says so.
11. **A teacher with two departments has a card in both columns.** Opening one opens the card that was clicked. Tick boxes on cards feed the same tick bar as the Table's.
12. **Columns on step 4:** every department on the school's list in its order (an empty one says so), then any other department found on a teacher, then "No department yet".
13. **Provisional** reads "added by a head, not yet confirmed" wherever the mark shows, for everyone.
14. **A head and the second department:** refused even on a provisional teacher; taken off a teacher a head adds.
15. **"Already teach that subject" on step 8** means any subject of the same step 3 card: the same department, code and name less its G-level. Inside each of the two groups the order is the teacher list's.
16. **The uploaded teacher list** (step 4) is read as today: it has no second-department column.
17. **The samples** give no teacher a second department, so the sample rules and the tests built on them are unchanged.
18. **The Roles card** is headed "Roles" and says "The teacher list above is checked against these roles."

## Review Focus

1. **A setup and a workbook from before.** Teachers with a stored `can_teach` and no `dept2`; a workbook with Can teach columns and no Department 2. Both open, nothing else differs, nothing asks about it. Pinned in Task 1 (`a_workbook_from_before_still_opens_and_its_can_teach_is_ignored`, `a_stored_can_teach_is_left_out_of_the_workbook`) and checked in a browser in Tasks 5 and 7.
2. **The Teachers sheet's formulas after the columns move.** Periods given, Spare, Total load, % of allowance, Load check and the Roles sheet's averages must each point at the column they name; nothing computes them in a test. Pinned in Task 1 (`the_teachers_formulas_point_at_the_columns_they_name`).
3. **Nobody to offer on step 8.** A subject no one teaches, in a department with no teacher; a subject that is not on step 3's list; a subject with no department. The offer is an empty list and never an error, and the school's real setup offers no fewer teachers than before. Pinned in Task 3 (`nobody_to_offer_is_an_empty_list`) and counted on the real setup at the whole-branch review.
4. **A second department that is not a clean value.** Equal to the home, a department no longer on the school's list, a teacher with no home department, a name with spaces round it, a `null` teacher row: the teacher shows once per department they are in, and nothing throws. Pinned in Task 4 (`every_teacher_shows_once_in_each_of_their_departments_whatever_the_row_holds`).
5. **Two people, a head, and a page left open.** Two committee tabs give one teacher different second departments: the later stands, nothing errors. A head's attempt is refused by the server. A head's page from before the change, still sending a Can teach change with a placement, has the placement kept and the rest refused in words. Pinned in Task 3 (`a_head_cannot_give_a_second_department`, `a_heads_old_can_teach_change_is_refused_and_the_rest_of_the_batch_lands`) and checked in a browser in Task 5.

---

### Task 1: The workbook and the skill: "Can teach" out, "Department 2" in

**Files:**
- Modify: `ttgen/spec.py`, `ttgen/template.py`, `ttgen/reader.py`, `ttgen/samples.py`; delete `ttgen/allocate.py`; the same five under `skill/school-timetable-generator/scripts/ttgen/`
- Modify: `skill/school-timetable-generator/SKILL.md`, `README.md` (the version line; the list of test commands gains `tests/test_teachers.py`)
- Create: `tests/test_teachers.py` (in the style of `tests/test_venues.py`: its `write`, `headings` and `t` helpers)
- Modify: `tests/test_parents.py` (the Can teach test and the version test), `tests/test_rules.py` (the version)

**Interfaces:**
- Produces: `ttgen.spec.teacher_depts(t) -> list[str]`: a teacher row's departments, home first: the trimmed, non-empty, different ones of `dept` and `dept2`.
- Produces: teacher rows from `reader.read_template` carry `dept2` (text, or `None` when blank or equal to Department) and no `can_teach` key.
- Produces: `ttgen.spec.SKILL_VERSION == "2026-11.5"`.
- The Teachers sheet's columns, in order: `Teacher`, `Short`, `Department`, `Department 2`, `Allowance (periods)`, `Provisional`, `Periods given`, `Spare`, `Note`, `Role`, `Other duties (periods)`, `Total load`, `Role guide (periods)`, `% of allowance`, `Load check`. The `(key, used by checks)` column and `NPAIR` go.

- [ ] **Step 1: Write the failing tests** in `tests/test_teachers.py`

```python
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
def the_samples_have_no_can_teach_and_allocate_is_gone():
    assert all("can_teach" not in x and "dept2" not in x for f in (secondary, primary) for x in f()["teachers"])
    assert not any(os.path.exists(os.path.join(ROOT, d, "allocate.py")) for d in ("ttgen", "skill/school-timetable-generator/scripts/ttgen"))
```

Also pin the samples' part-time teacher: before changing `samples.py`, run both samples on `main`, note the `target` of each sample's part-time rule, and assert the same two names afterwards (`the_samples_keep_their_part_time_teacher`).

In `tests/test_parents.py`: replace `the_workbook_does_not_check_can_teach_on_the_named_subjects` with `the_lessons_check_no_longer_tests_can_teach` (for `with_parents(primary())` and for `primary()`: the Check formula of row 6 holds "No teacher." and "twice in this block", and holds neither "not set to teach", nor "4 Teachers", nor `OR(B6=`, nor `B6="{SUBJ}"`); rename the version test to `the_skill_version_is_2026_11_5` with its three strings. In `tests/test_rules.py` the version assertion becomes `"2026-11.5"`.

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/bin/python tests/test_teachers.py; .venv/bin/python tests/test_parents.py; .venv/bin/python tests/test_rules.py`
Expected: `test_teachers.py` fails at `teacher_depts` (no such function); the other two fail on the version and on "not set to teach".

- [ ] **Step 3: Change `ttgen`**

- `spec.py`: `teacher_depts(t)` as above; `SKILL_VERSION = "2026-11.5"`.
- `template.py`: the Teachers sheet with the columns above. Department and Department 2 take the department list as their pick list; every formula and every reference from another sheet follows the moved columns. The sheet's title becomes "Step 4 · Teachers: who they are"; its first note line becomes "Department 2 is for a teacher who teaches in two departments: they count in both. Who teaches what is on Step 6."; the README sheet's line for step 4 becomes "List the teachers with their department and role. Periods given and Spare update as you fill Step 6." followed by whatever that line says after its second sentence today. The Lessons sheet's Check keeps "No periods…", "No class.", "No teacher.", "… twice in this block.", "Code used twice." and "Block not on Step 5.", and loses the Can teach test and the guard that skipped it for the named subjects.
- `reader.py`: `dept2` read from "Department 2"; Can teach columns not read.
- `samples.py`: teacher rows without `can_teach`; the part-time teacher chosen as before, from the builder's own record of each teacher's subjects.
- Delete `allocate.py`.
- Copy the five changes to `skill/school-timetable-generator/scripts/ttgen/`.

- [ ] **Step 4: Change `SKILL.md`**

The version line (`2026-11.5`). The Teachers row of the sheets table: "Teacher, Short, Department, Department 2 (optional: a teacher who teaches in two departments), Allowance, Provisional, Note, Role (from `Roles`), Other duties (periods); formulas show …" as today after that. Take "teacher not set to teach the subject" out of the list of what Check flags. Add one sentence beside the Teachers row: "A workbook made before 2026-11.5 has Can teach columns: ignore them. Any teacher may take any lesson the Lessons sheet gives them."

- [ ] **Step 5: Run the suites**

Run: `.venv/bin/python tests/test_teachers.py && .venv/bin/python tests/test_parents.py && .venv/bin/python tests/test_rules.py && .venv/bin/python tests/test_venues.py && .venv/bin/python tests/test_verify.py && .venv/bin/python tests/test_choices.py && .venv/bin/python tests/smoke.py && diff -rq ttgen skill/school-timetable-generator/scripts/ttgen`
Expected: every script prints its pass line; `diff` prints nothing. `tests/smoke.py` may fail only in a check that reads a sample teacher's `can_teach`; such a check is rewritten to what it was protecting (never deleted) and named in the report.

- [ ] **Step 6: Commit** `feat(workbook): the Teachers sheet without Can teach, with Department 2; skill 2026-11.5`

---

### Task 2: Either department counts for a department's rule

**Files:**
- Modify: `ttgen/solver.py`, `ttgen/report.py`, `ttgen/verify.py` (and their copies under `skill/`), `checks.py`, `fixes.py`
- Modify: `skill/school-timetable-generator/SKILL.md` (one sentence)
- Test: `tests/test_verify.py`, `tests/test_teachers.py`, `tests/test_fixes.py`

**Interfaces:**
- Consumes: `spec.teacher_depts(t)` (Task 1).
- Produces: `solver.Problem.tdepts: dict[str, list[str]]` in place of `tdept` (no `tdept` is left in any file).
- Produces: `verify.teacher_depts(m, spec) -> dict[str, list[str]]`: each teacher of the setup with their departments; a teacher the timetable names and the setup does not keeps the one department the timetable gives them.

- [ ] **Step 1: Write the failing tests**

In `tests/test_verify.py`, beside `not_available_and_keep_free_together`:

```python
@t
def keep_free_together_counts_a_second_department():
    sp = primary(); c = sp["classes"][0]["class"]; T = sp["teachers"][0]; t = T["name"]
    d2 = next(d for d in sp["school"]["departments"] if d != T["dept"]); row = rule("Department", d2, "Keep free together", 2, 3)
    L = [(1, 3, 1, [c], "English", "Entire Class", [t], "")]
    assert run(sp, [row], L)[0][0] == []                                    # not in that department: the rule does not see them
    T["dept2"] = d2; (ws, nc), m = run(sp, [row], L)
    assert len(ws) == 1 and ws[0]["group"] == t and ws[0]["text"].endswith(f"{d2} keeps periods 2-3 free together.")
```

In `tests/test_teachers.py`:

```python
@t
def the_solver_and_the_checks_block_a_second_department_too():
    sp = secondary(); reader.derive(sp); T = next(x for x in sp["teachers"] if any(x["name"] in (l.get("teachers") or []) for l in sp["lessons"]))
    d2 = next(d for d in sp["school"]["departments"] if d != T["dept"])
    T["dept2"] = d2; P = solver.Problem(sp)
    assert P.tdepts[T["name"]] == [T["dept"], d2] and not hasattr(P, "tdept")
    # a Must rule that keeps d2 free for every period of every day: this teacher, who has lessons, can no longer fit them
    sp["rules"].append(dict(scope="Department", target=d2, rule="Keep free together", week="Both", day="All", strength="Must", **{"from": 0, "to": 99}))
    assert any(line.startswith(T["name"] + " teaches") for line in checks._teacher_fit(solver.Problem(sp)))
    del T["dept2"]; assert not any(line.startswith(T["name"] + " teaches") for line in checks._teacher_fit(solver.Problem(sp)))
```

(Use the rule row's real field names and the last period of the sample's day in place of 99 if `rule_positions` needs them; the two assertions stay.)

In `tests/test_fixes.py`, beside the test that builds a Department window (it reads a teacher's `dept`): one more case where the teacher has that department only as `dept2`, and the rule still bears on their lesson (the judgement of a move into the window is the same as for a home-department teacher).

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/bin/python tests/test_verify.py; .venv/bin/python tests/test_teachers.py; .venv/bin/python tests/test_fixes.py`
Expected: the three new tests fail (the second department is not seen; `Problem` has no `tdepts`).

- [ ] **Step 3: Change the five files**

`solver.py`: `tdepts` built with `spec.teacher_depts`; "the teachers of department D" is every teacher with D among theirs. The same in `report.py` and `checks.py`. `verify.py`: `teacher_depts(m, spec)` and its use in `_keep_free_together`. `fixes.py` `_bears`: the same test through `verify.teacher_depts`. The Fix card must not get slower: the departments are worked out once per judged change (in the context `_ctx` builds, or once per call that loops over lessons), never once per lesson. Copy the three `ttgen` files to `skill/`. `SKILL.md`, where "Keep free together" for a department is described: "A teacher with a Department 2 counts in both departments."

- [ ] **Step 4: Run the suites**

Run: `.venv/bin/python tests/test_verify.py && .venv/bin/python tests/test_teachers.py && .venv/bin/python tests/test_fixes.py && .venv/bin/python tests/test_rules.py && .venv/bin/python tests/test_choices.py && .venv/bin/python tests/test_helper.py && .venv/bin/python tests/test_typed.py && .venv/bin/python tests/smoke.py && grep -rn "tdept\b" --include=*.py . | grep -v "^./.venv"; diff -rq ttgen skill/school-timetable-generator/scripts/ttgen`
Expected: every script passes; the `grep` and the `diff` print nothing.

- [ ] **Step 5: Commit** `feat(rules): a department's rule counts a teacher's second department`

---

### Task 3: The server: who is offered on step 8, and what a head may change

**Files:**
- Modify: `fixes.py` (`teacher_options`), `sync.py` (`_head_why`, the two docstrings), `app.py` (the head's new teacher; the sign-in choice's blurb), `docs/DEPLOY.md`, `README.md` (the `HEADS_CODE` row)
- Test: `tests/test_fixes.py`, `tests/test_sync.py`, `tests/smoke.py`

**Interfaces:**
- Consumes: `spec.teacher_depts(t)`.
- Produces: `fixes.teacher_options(m, spec, days, key)` with the same result shape and the same judging, offering, in this order: step 5's teachers of the key (as today), then every teacher of the setup's list who is on a lesson row of the subject or of another subject of its card, then every other teacher whose departments include the subject's department. Within the second and the third group the order is the teacher list's. Whoever is on the lesson now is left out, as today.
- "Its card" is step 3's: the subject rows with the same trimmed department, code and name less the row's own tag from its end, when that tag is one of the school's. A subject not on the list is a card of its own.

- [ ] **Step 1: Write the failing tests**

In `tests/test_fixes.py` (with its own helpers `model_with`, `lesson`, `SP`, `DAYS`; made-up names):

```python
@t
def teachers_offered_are_those_who_teach_the_subject_then_its_department():
    # a copy of SP with: "Mathematics G3" and "Mathematics G2" (department MA, code MA, tags G3 and G2), a class lesson of Mathematics G3 taught by Now;
    # Aye teaches Mathematics G2 somewhere and is in SC; Bee is in MA and teaches nothing; Cee is in SC with MA as dept2; Dee is in SC only.
    # In the teacher list the order is Dee, Cee, Bee, Aye, Now.
    assert [o["teachers"] for o in fixes.teacher_options(m, sp, DAYS, key)] == [["Aye"], ["Cee"], ["Bee"]]
```

Aye comes first (already teaches a subject of the card), then the department's teachers in the list's order (Cee, by a second department, before Bee), never Dee and never Now.

```python
@t
def nobody_to_offer_is_an_empty_list():
    # a lesson of a subject with no department, taught only by its own teacher; and a lesson whose subject is not on step 3's list
    assert fixes.teacher_options(m, sp, DAYS, key_no_department) == [] and fixes.teacher_options(m, sp, DAYS, key_not_on_the_list) == []
```

Change `teacher_room_add_delete_options`: its `can` list (today built from `can_teach`) becomes the teachers of `SUBJ`'s department who are not on the lesson.

In `tests/test_sync.py`, in "what a head of department may change": move `[["merge", "teachers", "t1", "can_teach", [], []]]` from the allowed list to the refused list; add `[["set", "teachers", "t2", "dept", "SC"]]` to the allowed list and `[["set", "teachers", "t2", "dept2", "SC"]]` to the refused list; assert `sync.head_may(spec, [["set", "teachers", "t2", "dept2", "SC"]]) == "Only the committee gives a teacher a second department."` and that the merge's sentence is `"Department heads can only add a teacher, or edit a provisional teacher."`.

In `tests/smoke.py` (new tests named in the file's own style, `test_…`):

- `test_a_head_can_edit_only_provisional_teachers`: the head's `merge … can_teach` on a confirmed teacher is now refused (`len(j["refused"]) == 1`).
- `a_head_cannot_give_a_second_department` (new): a head adds `{"_id": "newhire004", "name": "Two dept hire", "dept": "MA", "dept2": "SC"}`: the stored row is provisional and has no `dept2`; the head's `["set", "teachers", "newhire004", "dept2", "SC"]` is refused; the committee's same change is kept.
- `a_heads_old_can_teach_change_is_refused_and_the_rest_of_the_batch_lands` (new, from `test_a_heads_map_batch_is_applied_whole`): the same batch as today, with the `merge … can_teach` op still in it: one op refused, the new teacher, the split class and the placement all stored, and the new teacher has no `can_teach`. `test_a_heads_map_batch_is_applied_whole` itself loses the merge op and its `can_teach` assertion.

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/bin/python tests/test_fixes.py; .venv/bin/python tests/test_sync.py; .venv/bin/python tests/smoke.py`
Expected: the new and changed tests fail (offers come from Can teach; a head's merge is allowed; `dept2` is stored).

- [ ] **Step 3: Change the server**

- `fixes.py`: `teacher_options` as in Interfaces. Its docstring says the new order.
- `sync.py` `_head_why`: a head's `merge` on a teacher is refused with "Department heads can only add a teacher, or edit a provisional teacher."; a head's `set` of `dept2` is refused with "Only the committee gives a teacher a second department." whatever the teacher; the rest as today. The docstrings say what a head may change now. `MERGE` is not changed.
- `app.py`: where a head's added teacher is made provisional, `dept2` is also taken off the row. The Department heads sign-in choice's blurb becomes "Heads of department: who teaches which class and group, teaching groups and bands."
- `docs/DEPLOY.md` and the `HEADS_CODE` row of `README.md`: every "who can teach what" becomes "who teaches which class and group"; the list of what the server lets a head change loses it.

- [ ] **Step 4: Run the suites**

Run: `.venv/bin/python tests/test_fixes.py && .venv/bin/python tests/test_sync.py && node tests/sync.test.js && .venv/bin/python tests/test_helper.py && .venv/bin/python tests/test_typed.py && .venv/bin/python tests/smoke.py`
Expected: every script passes. A test in `test_helper.py` or `test_typed.py` that pinned who is offered by Can teach is rewritten to the new order, never deleted, and named in the report.

Until Task 7 the page of step 5 still draws its baskets, and a head's basket change is now refused by the server in words. That is expected in the middle of the branch.

- [ ] **Step 5: Commit** `feat(server): step 8 offers who teaches the subject, then its department; a head's Can teach permission ends`

---

### Task 4: The teacher cards model

**Files:**
- Modify: `static/people.js` (two new functions; `planTeachers` stops writing `can_teach`)
- Create: `static/teacherview.js`
- Modify: `static/index.html` (the script, after `subjectview.js`), `README.md` (the test list)
- Test: `tests/teacherview.test.js` (new), `tests/people.test.js`

**Interfaces:**
- Produces, in `People`: `depts(t) -> ["MA", "SC"]` (home first; trimmed, non-empty, different) and `inDept(t, dept) -> true|false`. The same answers as `spec.teacher_depts`.
- Produces, in `TeacherView` (a pure module like `SubjectView`: `var TeacherView = (function () {…})()`, `module.exports`, `People` through `require` under Node):

```js
TeacherView.columns(spec, f) -> [{ dept, cards: [{ ti, name, short, role, dept, dept2, home, provisional }] }]
   // f (optional) = { dept: "", q: "" }: only that department's column; only teachers whose name or short name holds q (People.key)
   // dept and dept2 on a card are the tidy values ("" when none); home is true in the column of the home department
TeacherView.setSecond(spec, ti, dept) -> { how: "set"|"changed"|"same"|"home"|"off"|"none", was: "" } | null
   // dept "" takes the second department off ("off"), or does nothing when there was none ("none"); null when there is no such teacher
TeacherView.tidy(t) -> true|false     // takes off a dept2 that is empty or equal to dept; true when the row changed
```

- Columns: every department of `spec.school.departments` in its order, then any other department found on a teacher (home or second) in the order first met, then `""` when some teacher has no department at all. Cards in a column follow the teacher list. A teacher has one card in each of their departments.

- [ ] **Step 1: Write the failing tests** in `tests/teacherview.test.js` (the header and `t()` helper of `tests/subjectview.test.js`)

```js
const spec = () => ({ school: { departments: ["MA", "SC", "PE"] }, teachers: [
  { _id: "a", name: "Arjun Nair", short: "Arjun", dept: "MA", role: "EO" },
  { _id: "b", name: "Lim Hui Min", short: "Hui Min", dept: "SC", dept2: "MA", provisional: "Yes" },
  { _id: "c", name: "Tan Wei Ming", short: "Wei Ming", dept: "SC", dept2: "SC" },
  null,
  { _id: "d", name: "Siti Rahman", short: "Siti", dept: " HU ", dept2: "" },
  { _id: "e", name: "", dept: null, can_teach: [{ subject: "Mathematics", levels: "All" }] }] });

t("a column per department of the school, then others found, then no department", () => {
  const C = TeacherView.columns(spec());
  assert.deepStrictEqual(C.map(c => c.dept), ["MA", "SC", "PE", "HU", ""]);
  assert.deepStrictEqual(C.map(c => c.cards.map(x => x.ti)), [[0, 1], [1, 2], [], [4], [5]]);
});
t("a teacher with two departments has a card in both, marked home in one", () => {
  const C = TeacherView.columns(spec()), inMA = C[0].cards[1], inSC = C[1].cards[0];
  assert.deepStrictEqual([inMA.ti, inMA.home, inMA.dept, inMA.dept2, inMA.provisional], [1, false, "SC", "MA", true]);
  assert.deepStrictEqual([inSC.ti, inSC.home, inSC.dept2], [1, true, "MA"]);
});
t("every teacher shows once in each of their departments whatever the row holds", () => {
  const C = TeacherView.columns(spec()), seen = {};
  C.forEach(c => c.cards.forEach(x => { seen[x.ti] = (seen[x.ti] || 0) + 1; }));
  assert.deepStrictEqual(seen, { 0: 1, 1: 2, 2: 1, 4: 1, 5: 1 });           // a second equal to the home is one department; a null row is no card
  assert.strictEqual(C[1].cards[1].dept2, "");
  assert.doesNotThrow(() => TeacherView.columns({}) && TeacherView.columns({ school: { departments: "x" }, teachers: "y" }));
});
t("the filter: one department's column, and a search by name or short name", () => {
  assert.deepStrictEqual(TeacherView.columns(spec(), { dept: "MA" }).map(c => [c.dept, c.cards.map(x => x.ti)]), [["MA", [0, 1]]]);
  assert.deepStrictEqual(TeacherView.columns(spec(), { q: "hui" }).map(c => c.cards.map(x => x.ti)), [[1], [1], [], [], []]);
});
t("giving, changing and taking off a second department", () => {
  const s = spec();
  assert.deepStrictEqual(TeacherView.setSecond(s, 0, "SC"), { how: "set", was: "" }); assert.strictEqual(s.teachers[0].dept2, "SC");
  assert.deepStrictEqual(TeacherView.setSecond(s, 0, "PE"), { how: "changed", was: "SC" });
  assert.deepStrictEqual(TeacherView.setSecond(s, 0, " PE "), { how: "same", was: "PE" });
  assert.deepStrictEqual(TeacherView.setSecond(s, 0, "MA"), { how: "home", was: "PE" }); assert.strictEqual(s.teachers[0].dept2, "PE");
  assert.deepStrictEqual(TeacherView.setSecond(s, 0, ""), { how: "off", was: "PE" }); assert.ok(!("dept2" in s.teachers[0]));
  assert.deepStrictEqual(TeacherView.setSecond(s, 0, ""), { how: "none", was: "" });
  assert.strictEqual(TeacherView.setSecond(s, 3, "MA"), null); assert.strictEqual(TeacherView.setSecond(s, 99, "MA"), null);
});
t("tidy takes off a second department that is empty or the home", () => {
  const s = spec();
  assert.strictEqual(TeacherView.tidy(s.teachers[2]), true); assert.ok(!("dept2" in s.teachers[2]));
  assert.strictEqual(TeacherView.tidy(s.teachers[1]), false); assert.strictEqual(s.teachers[1].dept2, "MA");
  assert.strictEqual(TeacherView.tidy(s.teachers[4]), true); assert.strictEqual(TeacherView.tidy(null), false);
});
t("nothing here reads or writes a stored can_teach", () => {
  const s = spec(), was = JSON.stringify(s.teachers[5].can_teach);
  TeacherView.columns(s); TeacherView.setSecond(s, 5, "MA"); TeacherView.tidy(s.teachers[5]);
  assert.strictEqual(JSON.stringify(s.teachers[5].can_teach), was);
});
```

In `tests/people.test.js`: `People.depts` and `People.inDept` on the same kinds of row (two departments, the same twice, none, spaces, `null`); the expected new teacher of `planTeachers` loses `can_teach: []`; a teacher updated by a list keeps a stored `can_teach` and `dept2` untouched.

- [ ] **Step 2: Run them to see them fail**

Run: `node tests/teacherview.test.js; node tests/people.test.js`
Expected: the first fails (no module); the second fails on `People.depts` and on `can_teach: []`.

- [ ] **Step 3: Write `static/teacherview.js` and change `static/people.js`**

As in Interfaces. No page access, nothing random. `static/index.html` loads `teacherview.js` after `subjectview.js`.

- [ ] **Step 4: Run the tests**

Run: `node tests/teacherview.test.js && node tests/people.test.js && node tests/map.test.js && node tests/sync.test.js`
Expected: all pass.

- [ ] **Step 5: Commit** `feat(teachers): the cards model: a column per department, a second department given and taken off`

---

### Task 5: Step 4 in two views, the Roles below, the second department

**Files:**
- Modify: `static/app.js` (`VIEWS.teachers`, `VIEWS.roles`, `teacherBar`, `bulkTeachers`, `headLocks`, the click, change and drag handlers, the pop-up, the two "add teacher" defaults), `static/style.css` (`.tk…` rules only), `README.md` (step 4's sentences)

**Interfaces:**
- Consumes: `TeacherView.columns`, `setSecond`, `tidy`; `People.depts`; the page's own `issues()`, `loadChecks(load)`, `rowCls`, `avatarOf`, `heldOpen` / `heldResolve`, `inp`, `sel`, `delBtn`.
- Produces: `TEACHERVIEW = "ttsetup.view.teachers"`; `TV = { view: "cards", open: null, openId: null, col: "" }`; the switch `data-tview="cards|table"` (it works for a head: add it to the exemptions `headLocks` already has for `data-sview`); a card `<div class="tkcard" data-tcard="{ti}" data-tcol="{encoded column department}">`; open and close `data-topen`, `data-tclose`; a department chip `data-tchip="{encoded department}"`; the ✕ of a second department `data-tsecond="{ti}"`.

- [ ] **Step 1: Take "Can teach" off step 4**

Remove: the Can teach column of the table; the "Can teach …" filter (`tfSubj`, `S.tf.subj` and its two resets); the tick bar's "can teach … at …" row with `tc-add`, `tc-rm`, `pickS`, `pickV` and `P.s`, `P.v`; the Can teach pop-up (the last branch of the pop-up's drawing, `ctRow`, and the `data-ctadd` / `data-ctdel` handling); `can_teach: []` from the two places a teacher is added on step 4. `scopes()` goes if nothing else uses it.

- [ ] **Step 2: The order of the step, and the Table**

The step draws, top to bottom: the heading card with the Cards / Table switch at its top right; the upload card (committee); the teachers card (`#teacherList`: the "Add teachers" helper, the Show bar, the tick bar, then the Cards or the Table); the Roles card last, in both views. The lead paragraph:

> Each teacher with their department, role and allowance. A teacher who teaches in two departments can have a second department: they are then on both departments' pages on step 5. Who teaches which class or group is set on step 5. Tick teachers (shift-click for a run) to give them a department, role or allowance together.

The Roles card is headed "Roles" and its first sentence is "The teacher list above is checked against these roles."; the rest of it is unchanged.

The Table gains a "Department 2" column after Department: `sel(`spec.teachers.${i}.dept2`, …)` over the school's departments less the teacher's home, with an empty first choice. The Show bar's department filter counts either department (`People.inDept`). The Provisional mark reads "added by a head, not yet confirmed" and shows to everyone; the committee's hover text stays.

Where a `data-k` change is written to the setup, a change to `spec.teachers.{i}.dept` or `.dept2` is followed by `TeacherView.tidy` on that teacher before the save; `bulkTeachers`' `tc-dept` does the same.

- [ ] **Step 3: The Cards**

- A row of department chips above the columns, one per department of the school: "Departments: drag one onto a teacher to give them a second department, or open the teacher and pick it." The chips are draggable for the committee only.
- `TeacherView.columns(S.spec, { dept: f.dept, q })`: a column per entry, headed with the department ("No department yet" for `""`) and its number of teachers; an empty column says "No teachers yet." The columns wrap; the page never scrolls sideways at a desk width (as `.sjcols`).
- A closed card: the tick box (`data-pick="teachers.{ti}"`, the Table's own), the avatar, the name, the short name, the role, the departments as chips (the home one first; the second with a ✕ for the committee), the load as a bar with "{given + other duties} / {allowance}" (or "{n} periods" with no allowance), `loadChecks(load)[ti]` in words under it, and "added by a head, not yet confirmed" when provisional. It carries the Table row's marks (`rowCls(out, crit, "teachers", ti)`). The card in a teacher's home column has `id="teachers-{ti}"`.
- A click on a card (not on its tick box, chip ✕ or a field) opens it in place, in the column it was clicked in (`heldOpen(TV, S.spec.teachers, ti)`, `TV.col`): Name, Short, Department, Second department, Allowance, Role, Other duties, Provisional, each the Table's own `data-k` path; Given, Spare and Total load as figures; Delete (the Table's `delBtn`); Close. One card is open at a time; the open card is found again by the row's `_id` on each draw and closes when its teacher is deleted.
- A chip dropped on a card, the Second department box, and the ✕ all go through `TeacherView.setSecond`, then one `save(); render();` and one toast:
  - set: "{name} is now in {dept} too. Undo takes it back."
  - changed: "{name}'s second department is now {dept}, not {was}. Undo takes it back."
  - off: "{was} taken off {name}. Undo takes it back."
  - home: "{dept} is already {name}'s department." (nothing saved)
  - same: "{name} is already in {dept} too." (nothing saved)
- The existing document-level drag listeners gain the chip (a payload `{ dept }`) and the card as a drop zone; a chip dropped anywhere else does nothing.
- A click on a Things to fix message for a teacher, with step 4 on Cards, opens that teacher's card in their home column.

- [ ] **Step 4: A head on step 4**

`headLocks` for a head (not in a practice copy): the view switch, the tick boxes, opening and closing a card always work. In an open card, as in a table row, the fields work only while the teacher is provisional, and never Provisional or Second department (title: "Only the committee gives a teacher a second department."). The chips are not draggable and their ✕ is not drawn. The handlers for `data-tchip` drops, `data-tsecond` and the Second department box return at once for a head. The comment above `isHead` says what a head may change now.

- [ ] **Step 5: Check it**

Run: `node --check static/app.js && node tests/teacherview.test.js && node tests/people.test.js && node tests/sync.test.js && grep -n "canteach\|ctRow\|tfSubj\|tc-add\|tc-rm\|pickS\|pickV" static/app.js; .venv/bin/python tests/smoke.py`
Expected: the checks pass and the `grep` prints nothing. (`can_teach` is still in step 5's map code until Task 7.)

In a browser, on a scratch server with the secondary sample in the school's own setup (not a practice copy), signed in with the committee's example code:

1. Step 4 opens on Cards, with the Roles card below the teachers in both views; the view is remembered after a reload.
2. Drag a department chip onto a teacher: the teacher has a card in both columns with both chips; Undo takes it back in one step. Do the same with the Second department box in the open card and in the Table; take it off with the ✕.
3. Set a teacher's home department to their second: the second is taken off in the same save.
4. Open a card, change the name, the role and the allowance: the Table shows the same; Undo is one step per change.
5. Tick two cards and set a role with the tick bar.
6. Give one teacher a stored `can_teach` list (Save to file, add the list to one teacher in the saved file, Load from file): the page opens, shows nothing of it, and after a change to that teacher a new Save to file still holds the list.
7. In a second browser profile signed in with the heads' example code: the cards and both views show; a confirmed teacher's open card is read-only; a teacher the head adds is provisional, can be edited, and its Second department box is disabled; no chip drags.
8. Two committee tabs give the same teacher two different second departments within a few seconds: both tabs end on the later one, and neither shows an error.
9. The console has no error.

- [ ] **Step 6: Commit** `feat(teachers): step 4 in two views; teacher cards, a second department, the Roles below`

---

### Task 6: The department page's model

**Files:**
- Modify: `static/map.js`
- Test: `tests/map.test.js`

**Interfaces:**
- Consumes: `People.depts`, `People.inDept` (Task 4).
- Changes: `DeptMap.roster(spec, dept, extraIds)`: the teachers whose home or second department is `dept`, in the list's order, then the visitors. `DeptMap.search(spec, q, dept)`: teachers in neither.
- Produces:

```js
DeptMap.page(spec, info, dept, level) -> [{ level, sections: [
    { kind: "subject", subject, cards: [card] }               // the subject's class cards (level's classes in the list's order), then its groups in no band
  | { kind: "band", bi, title, groups: [card], twice: [name] } ] }]
card = { kind: "class"|"group", li, cls, title, subject, level, periods, students, teachers, block }
   // cls only on a class card; title = the class, or the group's code (info[li].code)
   // students: a class card: that class's `size` on step 2; a group card: the lesson row's `students`; null when blank or not a number
```

- Levels follow `spec.school.levels`, then any other level found on a row, each only when it has a card; `level` (when not `""`) keeps that one. Inside a level the sections follow step 3's order of subjects: a subject's section sits at its subject's place, a band's lane at the place of the first of its subjects (of this department) in that order; when a subject section and a lane share a place the subject comes first, and lanes follow the bands list. A subject with no card has no section. A lane holds only the groups of this department's subjects; `twice` as `cards()` gives it today.
- Not changed in this task: `cards`, `deploy`, `baskets` and the rest (Task 7).

- [ ] **Step 1: Write the failing tests** in `tests/map.test.js` (its `fixture()` gains a second level, a band of two Mathematics groups, a second department on one teacher and sizes on its classes; made-up names)

```js
t("roster and search count a second department", () => {
  const s = fixture(); s.teachers[2].dept2 = "MA";                         // a Science teacher, Mathematics as second
  assert.ok(DeptMap.roster(s, "MA", []).includes(2) && DeptMap.roster(s, "SC", []).includes(2));
  assert.ok(!DeptMap.search(s, s.teachers[2].name, "MA").includes(2));
});
t("the page: levels first, then subjects in step 3's order, a band as a lane at its first subject's place", () => {
  const P = DeptMap.page(fixture(), info(), "MA", "");
  assert.deepStrictEqual(P.map(l => l.level), ["Sec 1", "Sec 2"]);
  assert.deepStrictEqual(P[0].sections.map(x => x.kind === "band" ? "band:" + x.title : x.subject), [/* the fixture's own order, written out */]);
});
t("a class card shows the class's size, a group card the group's students, and neither when blank", () => { /* students: 38, 24, null */ });
t("a lane holds only this department's groups, and names a teacher on two of them", () => { /* groups of another department's subject are left out; twice: [name] */ });
t("one level only; a department with no lessons; a row with no subject, no level or a level the school does not list", () => {
  assert.deepStrictEqual(DeptMap.page(fixture(), info(), "MA", "Sec 2").map(l => l.level), ["Sec 2"]);
  assert.deepStrictEqual(DeptMap.page(fixture(), info(), "PE", ""), []);
  assert.doesNotThrow(() => DeptMap.page({ lessons: [null, {}, { subject: "Mathematics", level: "Sec 9", classes: "x" }] }, [], "MA", ""));
});
t("every card of the old three tabs is on the page exactly once", () => {
  const s = fixture(), key = c => c.kind + "|" + c.li + "|" + (c.cls || "");
  const old = DeptMap.cards(s, info(), "MA", "classes", "").concat(DeptMap.cards(s, info(), "MA", "groups", "")).map(key).sort();
  const now = []; DeptMap.page(s, info(), "MA", "").forEach(l => l.sections.forEach(x => (x.cards || x.groups).forEach(c => now.push(key(c)))));
  assert.deepStrictEqual(now.sort(), old);
});
```

Write each bracketed expectation out from the fixture; the last test is the one that proves nothing was dropped.

- [ ] **Step 2: Run them to see them fail**

Run: `node tests/map.test.js`
Expected: the new tests fail (`DeptMap.page` is not a function; the roster does not count `dept2`).

- [ ] **Step 3: Write `page`, and change `roster` and `search`**

- [ ] **Step 4: Run the tests**

Run: `node tests/map.test.js && node tests/people.test.js && node tests/groups.test.js && node tests/classview.test.js`
Expected: all pass.

- [ ] **Step 5: Commit** `feat(map): the department page by level, then subject; a second department on the roster`

---

### Task 7: Step 5's department page, and the last of "Can teach"

**Files:**
- Modify: `static/app.js` (`VIEWS.lessons`' lead, `VIEWS.map`, `rosterList`, `cardsView`, `profileView`, `placeOn`, `mapAction`, the click and drop handlers, `issues()`, `VIEWS.table`'s teacher boxes, `tgBar` and its toast), `static/map.js`, `static/style.css`, `README.md` (step 5 and the tick bar's sentences)
- Test: `tests/map.test.js`

**Interfaces:**
- Consumes: `DeptMap.page`, `roster`, `search` (Task 6); `People.inDept`.
- Changes in `DeptMap`: `deploy(spec, card, idxs, opts)` reads only `opts.max`: a teacher is refused only when the card would hold too many (the sentence is today's), and nobody's `can_teach` is written. `unplaced(spec, idxs)`: those of `idxs` named on no lesson row. `newTeacher` makes a row without `can_teach`. Removed: `baskets`, `staffRoom`, `canTeach`, `needBasket`, `addToBasket`, `removeFromBasket`. Kept: `cards` (the profile's "Teaches" list uses it), `loads`, `rowFor`, `undeploy`, `prune`, `MAX`. `Parents.exempt` in `static/parents.js` is no longer called by the page; it and its tests stay.

- [ ] **Step 1: Change the tests in `tests/map.test.js`**

Remove the tests of baskets, `canTeach`, `needBasket`, `addToBasket`, `removeFromBasket` and `opts.exempt`. Change the deploy tests: a teacher of any department with no `can_teach` is placed at once; "more than three" and `opts.max` refuse with today's sentences and place no one; after any deploy no teacher row has gained a `can_teach`, and a stored one is unchanged. Add `unplaced: the teachers on no lesson row` and `a new teacher has no can_teach`.

Run: `node tests/map.test.js`. Expected: the changed deploy tests fail (a teacher outside the basket is refused).

- [ ] **Step 2: Change `static/map.js`** as in Interfaces. Run `node tests/map.test.js`: all pass.

- [ ] **Step 3: The page**

The Map view, top to bottom:

- **The strip** (a card): the department box; "{n} teachers · {k} ticked"; "Select all", "Deselect all", "No lessons yet" (title "Tick the teachers with no lessons yet"); the search box ("Find a teacher here, or one from another department"); "+ New teacher" and its form, as today. Under it the department's teachers (`DeptMap.roster`) as chips that wrap: tick box, avatar (click for the profile, drag to place), name, the load bar and "{total} / {allowance}" as today's roster row, a tag with the home department when it is another one (title "Home department: {dept}"), and "provisional" (title "Added by a head, not yet confirmed"). When the search finds teachers outside the page: a line "Others" and, for each, "+ Add" (title "Add them to this page to place them. Their departments do not change.").
- **The cards** (a card): the level box ("All levels"); then `DeptMap.page(S.spec, lessonInfo(), dept, M.level)`: a heading per level; inside it a heading per subject with its cards in a grid, and each band as today's lane (its name, "{n} groups", the "is on two groups of this band" lines) with its group cards in the same grid. With nothing to show: "No lessons for {dept}{ at {level}} yet. Add them in Groups and bands or the table view."
- **A card** is larger than today's and shows: the title (the class, or the group's code) with the Class Parents badge where it applies; "{students} students · {periods} periods" (the students part only when there is a figure); each teacher on a line of their own, avatar and full name (cut with "…", the whole name on hover), with the ✕; the "+" when there is room; the "Changed by hand" line as today. In a lane a card also names its subject.
- Placing works as today: tick teachers and click a card, or drag one (a ticked one drags all ticked) onto it. `placeOn` no longer asks about a basket; its toast keeps "Placed … on …", "… already on it" and the refusal's own sentence.
- The profile opens in place of the cards as today, without its Can teach part; the Teaches list is unchanged.
- The step's lead: "Tick teachers at the top, then click a class or group card to place them there. Dragging works too. Click an avatar for the teacher's profile. The table view shows the same rows for bulk edits, bands and new groups."

Remove from `static/app.js`: `basketsView`, `basketAdd`, `basketRemove`, `staffDrop`, `stillTeaches`, the tabs (`M.tab`, `data-mtab`), the handlers and drop zones of `data-mbasket`, `data-mstaff`, `data-mbx`, `data-mpx`, and `canTeach` / `canTeachRow`. From `static/style.css`: the `.basket…` and `.blist` rules and the three-column `.map` grid; new rules start with `dp`.

- [ ] **Step 4: Things to fix, the table view and the tick bar**

- `issues()` no longer says "… is not set to teach this at …". Every other message stays.
- `VIEWS.table`'s teacher boxes and `tgBar`'s "pick…" box: when the row's subject has a department (for the tick bar: when every ticked row's subject has the same one), the teachers of that department (home or second) come first under the department's name, then "Others"; otherwise one plain list in the teacher list's order.
- The tick bar's toast loses its "they are not set to teach" part.

- [ ] **Step 5: The words**

`README.md`: step 5's description (the strip, the level-first page, no baskets, no "must be in the subject's basket first"), the profile, the table view's tick bar, step 4's tick bar, the sentence that a form teacher needs no Can teach entry (removed), and the upload's "keeps their lessons and what they can teach" (now "keeps their lessons").

- [ ] **Step 6: Check it**

Run: `node --check static/app.js && for f in tests/*.test.js; do node "$f" || break; done && .venv/bin/python tests/smoke.py && .venv/bin/python tests/test_sync.py && grep -rnI "Can teach\|who can teach\|basket\|Staff room\|not set to teach" static ttgen README.md docs/DEPLOY.md; grep -rnI "Can teach" skill | wc -l; grep -rnl "can_teach" --include=*.py --include=*.js --include=*.html . | grep -v "^./.venv\|^./docs/"`
Expected: every suite passes; the first `grep` prints nothing; the count is 1 (the sentence in `SKILL.md`); the last lists only `sync.py`, `static/sync.js` and files under `tests/`.

In a browser, on a scratch server with the secondary sample in the school's own setup, as the committee:

1. Step 5 shows the strip, then the cards by level and subject, with each band's groups together under its name; the level box narrows it; every department's page opens.
2. Tick two teachers and click a card; drag a teacher onto a card; take one off with the ✕: each is one Undo step, and the load on the strip follows.
3. A fourth teacher on a card is refused with the sentence, and nobody is placed.
4. "Others": find a teacher of another department, add them, place them; step 4 shows their departments unchanged.
5. A teacher given a second department on step 4 is on both departments' strips, with the home-department tag on the other one.
6. A class of a row that lists several classes: placing a teacher on one class's card makes that class a row of its own, as before.
7. The profile opens and closes; it has no Can teach part.
8. The table view: a teacher box lists the department's teachers first; the tick bar places a teacher on several rows.
9. Things to fix has no "not set to teach" line, and a setup whose teachers still hold `can_teach` (from Task 5's check 6) shows none either.
10. As a head (second profile): placing and taking off work; a Class Parents lesson's card is locked as before; the strip's "+ New teacher" makes a provisional teacher.
11. The console has no error.

- [ ] **Step 7: Commit** `feat(map): step 5 without baskets: the teachers as a strip, classes and groups by level; the end of Can teach on the page`

---

## The whole-branch review

On the most capable model, with this plan's Review Focus and Decisions, and these checks on top of the diff.

**The suites.** Every `node tests/*.test.js`; `test_teachers`, `test_venues`, `test_typed`, `test_helper`, `test_fixes`, `test_verify`, `test_rules`, `test_choices`, `test_parents`, `test_sync`, `smoke` (and `smoke.py --full`); `node --check static/app.js`; `diff -rq ttgen skill/school-timetable-generator/scripts/ttgen` prints nothing.

**The school's real setup (counts only; delete every derived file afterwards).**

- The newest setup workbook reads with the new reader: 92 teachers, none with a second department, every other sheet's rows equal to what the reader on `main` gives.
- Written by the new writer and read back: the same setup. The count of Teachers-sheet columns, and that no heading starts "Can teach".
- Step 8, for each of the 65 subjects that have lessons: the number of teachers the new order offers against the number Can teach offered on `main`. The plan's count before building: no subject is left with none (the fewest is 2), and no teacher that was offered is lost. The same must hold after building, through `fixes.teacher_options` on the returned timetable of 10 November for a sample of lessons.
- The Fix card's time for one lesson on that timetable, before and after: no slower beyond noise.
- `TeacherView.columns` and `DeptMap.page` for every department: every teacher on exactly one card per department they are in; every class and group card of the old three tabs on the new page exactly once; the time each takes.
- The real page on a scratch server holding the real setup: step 4 Cards and Table, and the largest department's page on step 5, drawn warm, and a placement: each in milliseconds. No screenshot is taken.

**In a browser, on made-up data:** Tasks 5 and 7's lists once more on the finished branch, plus: download the workbook from step 7 and open it again from the Start step (the setup is the same, second departments included); step 8's Fix card on a returned sample timetable offers teachers for a lesson, and says so in its usual words for a lesson with no one to offer; steps 1, 2, 3 and 6 still open and change.

**Names.** No real name and no full school name in the diff or the commit messages.

Then the notes file `docs/superpowers/plans/2026-11-16-visual-views-stage-4-notes.md`: what was built, every ruling with its cost if wrong, what the review checked, known limits, deferred minor points, what was not exercised.

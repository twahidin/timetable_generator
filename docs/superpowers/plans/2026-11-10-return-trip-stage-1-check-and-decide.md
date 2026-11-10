# Return trip stage 1: check and decide — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** An uploaded timetable becomes a draft on the server, is checked against the school's current setup (clashes, the deployment on step 5, the standard rules, the typed rules through the rule report, the choices used), every finding is a warning the committee lead can settle (update step 5, or leave it), and publishing carries the warnings left and the setup version it was checked against.

**Architecture:** A new module `ttgen/verify.py` (both copies) turns a finished timetable model plus a setup into a list of warning dicts with stable keys; `python -m ttgen check-timetable` prints them so the agent can check its own work. A new app module `draft.py` keeps the uploaded file, the decisions and the warnings under `DATA/draft/`, always checking against the current setup read fresh from `store`. `app.py` gets draft routes in place of `/api/import-timetable`; `store.publish` takes the current setup and the extra record. A new `static/draft.js` holds the pure front-end logic (grouping, counts, sentences) and `static/app.js` draws step 8 from it.

**Tech Stack:** Python 3.11 (openpyxl, sqlite3), Flask, vanilla JavaScript with no build step. Python tests are plain asserts like `tests/test_choices.py`; Node tests like `tests/choices.test.js`; server tests in `tests/smoke.py`.

**Spec:** `docs/superpowers/specs/2026-11-10-return-trip-design.md`: "The return trip, start to end" parts 1 Upload, 2 Check, 3 Decide and 5 Publish; "Working together"; "Constraints on the build"; "Suggested order of building" item 1. Parts 4 Fix (the grid, the helper, the typed request) are stages 2 to 4 and are **not** in this plan, except that the draft and the warning model must leave room for them (a `fixes` list on the draft, a `fixed` answer on a warning).

## Global Constraints

- Every check, every decision and the publish run against the school's **current** setup (`store.load_setup()`), read fresh each time; the setup inside the uploaded file is used only for its configuration id. The draft's model is built with `model_from_files(setup_path, timetable_path, spec=<current setup>)`.
- A warning is `dict(key, kind, text, strength, group, where, sides, ops)`: `key` a stable string (the same warning gets the same key on every check); `kind` ∈ `"clash" | "deployment" | "rule" | "typed" | "choice"`; `text` one sentence; `strength` `"Must"` or `"Prefer"` (clash, deployment and choice: `"Must"`); `group` the class name, teacher name or `"School"` the list groups it under; `where` `dict(cls, day, period)` or `None`; `sides` `dict(timetable, step5)` (two short phrases) or `None`; `ops` a list of `sync` operations that make step 5 match the timetable, or `None` when there is no such answer.
- A decision is `dict(answer, at)` with `answer` ∈ `"step5" | "left" | "fixed"` (`"fixed"` is for stage 2; stage 1 never writes it), stored by warning key in `DATA/draft/decisions.json`. A warning with no decision, or with `"left"`, counts as **open**. A decision whose key no longer appears after a check is dropped.
- The draft lives in `DATA/draft/`: `timetable.<xlsx|sqlite>`, `setup.xlsx` when one was sent, `meta.json` (`source, uploaded_at, config_id, fixes: []`), `decisions.json`. A new upload replaces all of it; `"left"` decisions whose keys reappear are carried over.
- Periods are 0-based everywhere (rules' From/To, the lessons' `p`, the Day structure); day names are the setup's (`"Odd Mon"`, `"Mon"`); week `"Both" | "Odd" | "Even"`, day `"All"` or a weekday.
- `SKILL_VERSION` becomes `"2026-11.2"`; `SKILL.md`'s version line and the README cell follow from it. `ttgen/` and `skill/school-timetable-generator/scripts/ttgen/` stay identical (`tests/test_rules.py` checks). After every task that touches `ttgen/`: `rm -rf skill/school-timetable-generator/scripts/ttgen && cp -R ttgen skill/school-timetable-generator/scripts/ttgen && find skill -name __pycache__ -exec rm -rf {} +`.
- Step 8 stays committee-only on the server (`@need("committee")` on every draft route); `/api/status` carries a draft summary to both roles because the page polls it, but a head's page hides step 8 (`HEAD_HIDDEN`) as today.
- Warnings are never walls: Publish works with open warnings. Nothing the agent sent is changed: the uploaded file is kept as it came.
- No framework, no bundler, no new package. Wording: plain sentences, sentence case, no "please", no exclamation marks. Names in tests, samples and docs are made up; never commit `.claude/launch.json` or `data/`.
- Tests: `.venv/bin/python tests/test_verify.py` (new), `tests/test_choices.py`, `tests/test_rules.py`, `tests/smoke.py` (and `--full` once), `tests/test_sync.py`, `node tests/draft.test.js` (new), `choices.test.js`, `groups.test.js`, `map.test.js`, `people.test.js`, `sync.test.js`, `node --check static/app.js`. Page checks against a scratch `DATA_DIR` (a temporary `timetable-scratch` launch.json configuration on port 8003, removed afterwards), never the repo's `data/`.
- Commit on branch `return-trip-stage-1` after each task (the branch starts from `main` at `c95ad7e`; the first commit adds the spec and this plan). Do not push or open a pull request until the committee asks.

## Review Focus

1. A timetable uploaded before any setup is saved, or for another school → a plain sentence back, no crash, no draft written. Pinned in Task 5.
2. A head changes step 5 while a draft is open → the next check runs against the new setup, decisions on warnings that still appear are kept, the rest are dropped; "update step 5" on a row that no longer exists refuses with a sentence and records nothing. Pinned in Task 5.
3. A rule row the checker cannot judge (a target that matches nothing, a blank From and To on a rule that needs them, a rule type with no checker) → listed under `not_checked`, never silently passed and never a crash. Pinned in Tasks 2 and 3.
4. A Lessons workbook whose block lessons are several rows with one Lesson ID → the deployment comparison counts a group's periods once, not once per row; a workbook with no Lesson ID column still reads. Pinned in Task 1.
5. A rule report that numbers rules as "T1", lists a number the setup does not have, or has no line for a typed Must → each is its own warning with the right strength. Pinned in Task 4.

---

### Task 1: `ttgen/verify.py`: the deployment comparison, and a model built against a given setup

**Files:**
- Create: `ttgen/verify.py`, `tests/test_verify.py`
- Modify: `ttgen/export.py` (`model_from_files(setup_path, timetable_path, spec=None)`)
- Copy: `ttgen/` → the skill copy (Global Constraints)

**Interfaces:**
- Consumes: `ttgen.export.model_from_files`, `ttgen.export._model`, `ttgen.reader.derive`, `ttgen.export.ENTIRE`, `ttgen.spec.untag`.
- Produces in `ttgen.export`: `model_from_files(setup_path, timetable_path, spec=None)`: when `spec` is given it is deep-copied and used as the setup (the file's own setup and `setup_path` are ignored for everything but `m["setup"]["school"]["config_id"]`, which is taken from the file when the file has one); the rest unchanged. In both cases the model now also keeps `m["checked_setup"]`: the setup **with the second choices applied** (`choices.apply_all(spec, k)`, derived), which is the setup every check is made against; `m["setup"]` stays the setup as downloaded.
- Every `verify` function that takes `spec` takes the checked setup: callers pass `m["checked_setup"]`, and `warnings(m, spec=None)` (Task 4) defaults to it.
- Produces in `ttgen.verify`:
  - `KINDS = ("clash", "deployment", "rule", "typed", "choice")`.
  - `warning(key, kind, text, strength="Must", group="School", where=None, sides=None, ops=None) -> dict` (the shape in Global Constraints).
  - `planned_rows(spec) -> dict[key, dict]`: `key = ("C", class, subject)` for an entire-class row (one per class on the row) and `("G", code)` for a group row, value `dict(rows=[the spec lesson rows], teachers=set, periods=int, room_kind=str|None, classes=list, level, subject)`. Rows without `periods` or `classes` are skipped (as `_model` does).
  - `placed(m) -> dict[key, dict]`: the same keys from the timetable, value `dict(lessons=[model lessons], teachers=set, periods=int, rooms=set)`; a lesson id counts once per key (as `check_model` does).
  - `deployment(m, spec) -> list[dict]`: one warning per difference:
    - teachers differ → key `f"dep:{k}:teachers"`, text `"{what} is taught by {A} on the timetable; step 5 says {B}."`, `sides=dict(timetable=A, step5=B)`, `ops=[["set", "lessons", row["_id"], "teachers", sorted(timetable teachers)] for each row with an _id]` (`None` when no row has an `_id`), `group` = the class (first class), `where` = the first lesson's `dict(cls, day=m["days"][d], period=p)`;
    - periods differ → key `f"dep:{k}:periods"`, text `"{what}: {n} periods timetabled, {want} on step 3."`, sides, `ops=None`;
    - venue kind differs → key `f"dep:{k}:venue"`, text `"{what} is in {room} ({kind}); step 3 asks for {room_kind}."`, only when the row's `room_kind` is set, the lesson's room is set and not `"TBC"`, and the room's kind in `m["room_ix"]` differs; `ops=None`;
    - missing → key `f"dep:{k}:missing"`, text `"{what} is on step 5 but not on the timetable."`, `ops=[["del", "lessons", row["_id"]] ...]`;
    - extra → key `f"dep:{k}:extra"`, text `"{what} is on the timetable but not on step 5."`, `ops=[["add", "lessons", dict(level, subject, classes, teachers=sorted, block=block or None), ""]]` when the subject is on `spec["subjects"]`, else `None`.
    - `what` = `f"{subject} for {class}"` or `f"group {code}"`. A key's `k` in the key string is `"C:{class}:{subject}"` / `"G:{code}"`.
  - `clashes(m) -> list[dict]`: `m["checks"]["problems"]` as warnings, key `"clash:" + text`, `group` the teacher/class/room named at the start of the sentence when one is (`"Teacher double-booked: X on"` → X; `"Class clash: X on"` → X; else `"School"`), **leaving out** the lines ending `"planned."` (the deployment comparison owns periods).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_verify.py (plain asserts, the t() pattern of tests/test_choices.py)
from ttgen import verify, export, reader
from ttgen.samples import primary

def model_for(sp, placed):   # a model from hand-placed lessons: placed = [(day index, p, n, classes, subject, group, teachers, room)]
    sp = copy.deepcopy(sp); reader.derive(sp); days = list(sp["day_structure"][sp["school"]["levels"][0]].keys())
    L = [dict(id=i + 1, d=d, p=p, n=n, level=sp["classes"][0]["level"] if cls else "", block="", classes=cls, subject=s, group=g, teachers=t, room=r, ext=False, rain="")
         for i, (d, p, n, cls, s, g, t, r) in enumerate(placed)]
    return export._model(sp, days, L)

@t
def deployment_finds_teacher_periods_missing_and_extra():
    sp = primary(); row = next(x for x in sp["lessons"] if not x.get("block")); cls, subj = row["classes"][0], row["subject"]
    reader.derive(sp); want = row["periods"]
    m = model_for(sp, [(0, 0, want, [cls], subj, "Entire Class", ["Nobody"], "")])
    ws = {w["key"]: w for w in verify.deployment(m, sp)}
    k = f"dep:C:{cls}:{subj}:teachers"; assert k in ws and ws[k]["sides"]["step5"] == row["teachers"][0] and ws[k]["ops"] == [["set", "lessons", row["_id"], "teachers", ["Nobody"]]] if row.get("_id") else ws[k]["ops"] is None
    assert all(w["kind"] == "deployment" for w in ws.values()) and sum(1 for w in ws.values() if w["key"].endswith(":missing")) == len(verify.planned_rows(sp)) - 1
    m2 = model_for(sp, [(0, 0, want - 1, [cls], subj, "Entire Class", row["teachers"], ""), (1, 0, 1, [cls], "Nothing", "Entire Class", row["teachers"], "")])
    ws = {w["key"]: w for w in verify.deployment(m2, sp)}
    assert f"dep:C:{cls}:{subj}:periods" in ws and f"dep:C:{cls}:Nothing:extra" in ws and ws[f"dep:C:{cls}:Nothing:extra"]["ops"] is None

@t
def a_block_lesson_counts_once_per_group():
    sp = primary(); b = next(x for x in sp["lessons"] if x.get("block")); reader.derive(sp)
    rows = [(0, 0, b["periods"], b["classes"], b["subject"], b["code"], b["teachers"], "")] * 2   # the same lesson id twice would be two rows; here two ids
    m = model_for(sp, rows); m["lessons"][1]["id"] = 1                                           # one lesson id, two rows
    assert not any(w["key"] == f"dep:G:{b['code']}:periods" for w in verify.deployment(m, sp))

@t
def model_from_files_takes_a_given_setup():
    with tempfile.TemporaryDirectory() as d:
        sp = primary(); setup = os.path.join(d, "s.xlsx"); template.write_template(sp, setup)
        # a one-lesson workbook as tests/test_rules.py builds, then:
        other = copy.deepcopy(sp); other["school"]["name"] = "Other School"
        m = export.model_from_files(setup, tt, spec=other); assert m["school"]["name"] == "Other School"

@t
def clashes_drop_the_planned_lines_and_name_the_group():
    m = model_for(primary(), [(0, 0, 2, ["1A"], "English", "Entire Class", ["Ms X"], ""), (0, 1, 1, ["1B"], "Maths", "Entire Class", ["Ms X"], "")])
    ws = verify.clashes(m); assert any(w["group"] == "Ms X" and w["key"].startswith("clash:Teacher double-booked") for w in ws) and not any("planned" in w["text"] for w in ws)
```

(Use the primary sample's real class names, not `1A`, by reading them from `sp["classes"]`.)

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/bin/python tests/test_verify.py`
Expected: FAIL with `ImportError: cannot import name 'verify'`

- [ ] **Step 3: Implement `verify.py` (the functions above) and the `spec=` parameter of `model_from_files`**

`model_from_files`: `if spec is not None: spec = copy.deepcopy(spec)` in place of reading the file's setup; `setup` (what `m["setup"]` keeps) is that copy with `school.config_id` set from the file's setup when the file has one. The `placed`/`planned_rows` logic mirrors `check_model`'s `placed`/`planned` loops; do not change `check_model`.

- [ ] **Step 4: Run the tests and the existing suites**

Run: `.venv/bin/python tests/test_verify.py && .venv/bin/python tests/test_choices.py && .venv/bin/python tests/test_rules.py`
Expected: `4 checks passed`, then the existing counts (16, 10)

- [ ] **Step 5: Copy `ttgen` to the skill, commit**

```bash
git add ttgen tests/test_verify.py skill/school-timetable-generator/scripts/ttgen
git commit -m "feat(verify): deployment comparison and a model against a given setup"
```

---

### Task 2: Standard rules on a finished timetable, part 1: the rules about periods

**Files:**
- Modify: `ttgen/verify.py`, `tests/test_verify.py`
- Copy: `ttgen/` → the skill copy

**Interfaces:**
- Consumes: Task 1's `warning`; `ttgen.spec.names_list`, `subject_test`, `untag`, `RULE_TYPES`; `ttgen.solver.rule_label`.
- Produces in `ttgen.verify`:
  - `rule_days(days, r) -> list[int]` and `rule_periods(r, NP) -> range`: the solver's `_day_ok` / `rule_positions` logic (week `Odd`/`Even` by prefix, day by first three letters, blank From → 0, blank To → NP-1).
  - `in_scope(m, spec, r) -> callable(lesson) -> bool`: Teacher → target in `teachers`; Class → target in `classes`; Room → `room == target`; Level → `level == target` or every class's level is the target; Block → `block == target`; Subject → `subject_test([target])(subject, dept)`; Department → the subject's `dept` in `m["subjects"]` equals target; Group → `group == target`; School → always. Then `r["subject"]` narrows with `subject_test([r["subject"]])` when set. An unknown scope → `None`.
  - `rules(m, spec) -> tuple[list[dict], list[str]]`: `(warnings, not_checked)`. Each rule row `i` in `spec["rules"]` with `rule` not `"In words"` goes to its checker; a row whose checker is missing, whose scope is unknown, or that needs From/To and has neither, goes to `not_checked` as `f"{rule_label(r)}: {why}"`. Warning: key `f"rule:{i}:{detail}"` (`detail` names the lesson or day: `"{cls}|{d}|{p}"` or `"{teacher}|{d}"`), text `f"Rule {rule_label(r)}: {sentence}"` with `" (Prefer)"` appended when `strength == "Prefer"`, `strength` from the row, `group` the class/teacher/room the sentence is about, `where` when a lesson is named.
  - This task's checkers (sentences in sentence case, the rule's periods written `periods a-b`):
    - Not available: a lesson in scope overlapping the periods on a rule day → `"{target} has {subject} {who} on {day} period {p} but is not available (periods a-b)."`
    - Keep free together: Department → any lesson of a teacher of that department (the teacher's `dept` in `m["teachers"]`) in the periods; Level → any lesson of a class of the level → `"{teacher or class} has {subject} on {day} period {p}; {target} keeps periods a-b free together."`
    - Fixed at: each lesson in scope on a rule day must start at From (Day All: every such lesson) → `"{what} starts at period {p} on {day}, not period {from}."`; `to` is ignored.
    - Not in periods / Only in periods: a lesson in scope with a period inside / outside the periods on a rule day → `"{what} is in periods a-b on {day}."` / `"{what} is outside periods a-b on {day}."`
    - Finish by: a lesson in scope on a rule day ending after To → `"{what} ends at period {q} on {day}, after period {to}."`
    - Only these subjects: in the periods on rule days, a lesson in scope whose subject fails `subject_test(names_list(r["subject"]))` → `"{what} is in periods a-b on {day}, kept for {names}."` (the scope's `subject` field is the list, so `in_scope` must not narrow by it for this rule type).
    - Only in venues: a lesson in scope running into the periods whose room is not in `r["venues"]` (and not blank/TBC) → `"{what} is in {room} on {day} period {p}; only {venues} are allowed in periods a-b."`

- [ ] **Step 1: Write the failing tests** (one per checker; each builds a tiny model with `model_for` from Task 1 and one rule row, asserts one warning with the expected key suffix, and one case with no warning)

```python
@t
def not_available_and_keep_free_together():
    sp = primary(); c = sp["classes"][0]["class"]; t = sp["teachers"][0]["name"]
    sp["rules"] = [dict(scope="Teacher", target=t, rule="Not available", week="Both", day="All", **{"from": 0, "to": 1}, strength="Must")]
    m = model_for(sp, [(0, 1, 1, [c], "English", "Entire Class", [t], "")])
    ws, nc = verify.rules(m, sp); assert len(ws) == 1 and ws[0]["key"] == f"rule:0:{c}|0|1" and ws[0]["group"] == t and ws[0]["where"]["period"] == 1 and nc == []
    m = model_for(sp, [(0, 3, 1, [c], "English", "Entire Class", [t], "")]); assert verify.rules(m, sp)[0] == []

@t
def fixed_at_only_in_not_in_finish_by():
    ...  # each: a lesson that breaks it → one warning whose text ends as specified; a lesson that keeps it → none; a Prefer row → text ends " (Prefer)" and strength "Prefer"

@t
def only_these_subjects_and_only_in_venues():
    ...

@t
def rules_that_cannot_be_checked_are_listed():
    sp = primary(); sp["rules"] = [dict(scope="Planet", target="Mars", rule="Not in periods", week="Both", day="All", **{"from": 0, "to": 1}, strength="Must"),
                                   dict(scope="School", target="Whole school", rule="Not in periods", week="Both", day="All", strength="Must")]
    ws, nc = verify.rules(model_for(sp, []), sp); assert ws == [] and len(nc) == 2 and "scope" in nc[0] and "From" in nc[1]
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/bin/python tests/test_verify.py`
Expected: FAIL with `AttributeError: module 'ttgen.verify' has no attribute 'rules'`

- [ ] **Step 3: Implement `rule_days`, `rule_periods`, `in_scope`, `rules` with the seven checkers in a dispatch dict `CHECKERS = {"Not available": _not_available, ...}`**

- [ ] **Step 4: Run the tests**

Run: `.venv/bin/python tests/test_verify.py`
Expected: `8 checks passed`

- [ ] **Step 5: Copy `ttgen` to the skill, commit**

```bash
git add ttgen tests/test_verify.py skill/school-timetable-generator/scripts/ttgen
git commit -m "feat(verify): the period rules checked on a finished timetable"
```

---

### Task 3: Standard rules, part 2: the rules about counts and patterns

**Files:**
- Modify: `ttgen/verify.py`, `tests/test_verify.py`
- Copy: `ttgen/` → the skill copy

**Interfaces:**
- Consumes: Task 2's `CHECKERS`, `in_scope`, `rule_days`; `m["grid"]` (a level's day as a code string, `R` recess, `W` window), `m["cgrid"]`, `m["subjects"][s]["dept"]`.
- Produces: the remaining entries of `CHECKERS`:
  - Max periods a day (Teacher, Class, Level, School): per day, the sum of `n` over the lessons of each teacher (School, Teacher) or each class (Class, Level); over Number → `"{who} has {n} periods on {day}, more than {number}."` (key detail `"{who}|{d}"`, `where=None`, `group=who`).
  - Max periods in a row (Teacher, School): the longest run of consecutive occupied periods of a teacher on a day (a lesson's periods are `p..p+n-1`) over Number → `"{teacher} teaches {n} periods in a row on {day}, more than {number}."`
  - At least one recess a day (Teacher, School): on each day a teacher is free (no lesson) for the whole `R` run of some level in `m["grid"]`, or for `length` consecutive periods inside a `W` run of some level, `length` = that level's recess length (`spec.floating_recess(spec["school"])` for the level, else the number of W periods); otherwise → `"{teacher} has no recess on {day}."` Days where no level has an `R` or `W` are skipped.
  - At most N at once (Subject, Department): per `(d, q)` the number of lessons of the subject / department over Number → `"{number}+ {target} lessons at once on {day} period {q} ({count})."`; Room scope → nothing here (`check_model` already reports room capacity), not listed as not checked.
  - Same time across classes (Level with `subject`): the set of `(d, q)` of that subject per class of the level; a class whose set differs from the most common set → `"{cls} has {subject} at a different time from the other {level} classes."`
  - Not on the same day as (Subject target, `subject` = the other): for each class, a day with both → `"{cls} has {A} and {B} on {day}."`
  - Once a day per group (School, Subject): a group code (or class + subject for entire-class lessons) with two lesson ids on one day → `"{what} meets twice on {day}."`
  - Avoid after-school slots (School, Level, Class): a lesson in scope with `ext` true → `"{what} is in an after-school slot on {day}."` with the row's strength.

- [ ] **Step 1: Write the failing tests** (one per checker, as in Task 2; `At least one recess a day` needs a day whose level grid has `R`: use the primary sample's structure and place lessons on every `R` period of the teacher's day)

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/bin/python tests/test_verify.py`
Expected: FAIL: the new rule types appear in `not_checked` and the asserted warnings are missing

- [ ] **Step 3: Implement the eight checkers**

- [ ] **Step 4: Run the tests**

Run: `.venv/bin/python tests/test_verify.py`
Expected: `16 checks passed`

- [ ] **Step 5: Copy `ttgen` to the skill, commit**

```bash
git add ttgen tests/test_verify.py skill/school-timetable-generator/scripts/ttgen
git commit -m "feat(verify): the count and pattern rules checked on a finished timetable"
```

---

### Task 4: Typed rules through the rule report, all warnings together, `check-timetable`, the skill

**Files:**
- Modify: `ttgen/verify.py`, `ttgen/__main__.py`, `ttgen/spec.py` (`SKILL_VERSION`), `skill/school-timetable-generator/SKILL.md`, `tests/test_verify.py`, `tests/test_rules.py` (the version)
- Copy: `ttgen/` → the skill copy

**Interfaces:**
- Consumes: `ttgen.spec.typed_rules`, `typed_label`; `m["rule_report"]` (`[{no, strength, applies, rule, result, how}]`, `no` an int or None); `m["choice_problems"]`; Tasks 1 to 3.
- Produces in `ttgen.verify`:
  - `typed(spec, report) -> list[dict]`: for each `(n, i, r)` of `typed_rules(spec)`: no report row with `no == n` → key `f"typed:{n}:none"`, text `"T{n} has no line in the rule report: {sentence}."`, strength from the row; a row with `result` `"Not met"` or `"Partly"` → key `f"typed:{n}:{result}"`, text `"T{n} {result lower-case}: {sentence}. The agent says: {how}"` (or without the second sentence when `how` is blank); `"Met"` → nothing. A report row whose `no` is not a typed number → key `f"typed:{no}:unknown"`, text `"The rule report's line {no} ({rule}) is not a typed rule on step 6."`, strength Must. `group="School"`.
  - `choices_(m) -> list[dict]`: `m["choice_problems"]` as warnings, key `"choice:" + text`, kind `"choice"`.
  - `warnings(m, spec=None) -> dict(warnings=list, not_checked=list)`: `spec = spec or m["checked_setup"]`; `clashes(m) + deployment(m, spec) + rules(m, spec)[0] + typed(spec, m["rule_report"]) + choices_(m)`, in that order, `not_checked` from `rules`.
- Produces in `ttgen/__main__.py`: `check-timetable <timetable> [--setup <xlsx>]` (`--setup` required for a workbook, optional for a database that holds its setup): builds the model with `model_from_files`, prints one line `"{N} warnings ({open per kind}: 3 clashes, 2 deployment, ...)"`, then every warning as `" - [{kind}] {text}"` grouped by kind in `KINDS` order, then `" ? Not checked: {line}"` per `not_checked`, exit 0 when there are no `Must` warnings, else 1.
- Produces in `SKILL.md`: the version line `2026-11.2`; in the hand-back section one new paragraph: run `python -m ttgen check-timetable <the database>` before handing back and fix what it lists, or say in the notes why it stays (the committee sees the same list).
- `SKILL_VERSION = "2026-11.2"`; `tests/test_rules.py`'s version assertion follows.

- [ ] **Step 1: Write the failing tests**

```python
@t
def typed_rules_against_the_report():
    sp = primary(); sp["rules"] = [dict(scope="School", target="Whole school", rule="In words", text="No PE first", strength="Must", week="Both", day="All"),
                                   dict(scope="School", target="Whole school", rule="In words", text="Art late", strength="Prefer", week="Both", day="All")]
    rep = [dict(no=2, strength="Prefer", applies="Whole school", rule="Art late", result="Partly", how="Two classes."), dict(no=7, strength="Must", applies="", rule="Ghost", result="Met", how="")]
    ws = {w["key"]: w for w in verify.typed(sp, rep)}
    assert set(ws) == {"typed:1:none", "typed:2:Partly", "typed:7:unknown"} and ws["typed:2:Partly"]["strength"] == "Prefer" and "Two classes." in ws["typed:2:Partly"]["text"]

@t
def warnings_come_in_kind_order():
    ...  # a model with a teacher clash, a teacher difference and a typed rule with no report line: kinds == ["clash", "deployment", "typed"], not_checked == []

@t
def check_timetable_prints_and_exits_one_on_a_must():
    ...  # write the primary sample and a one-lesson Lessons workbook (as tests/test_rules.py does); main(["check-timetable", tt, "--setup", setup]) == 1; stdout has "[deployment]" lines and a "warnings (" summary line
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/bin/python tests/test_verify.py`
Expected: FAIL with `AttributeError: ... 'typed'`

- [ ] **Step 3: Implement `typed`, `choices_`, `warnings`, the `check-timetable` command, the `SKILL.md` paragraph and version, `SKILL_VERSION`**

- [ ] **Step 4: Run the tests and the suites that read the version**

Run: `.venv/bin/python tests/test_verify.py && .venv/bin/python tests/test_rules.py && .venv/bin/python tests/test_choices.py`
Expected: `19 checks passed`, 10, 16 (after updating the version assertion in `tests/test_rules.py`)

- [ ] **Step 5: Copy `ttgen` to the skill, commit**

```bash
git add ttgen tests skill/school-timetable-generator
git commit -m "feat(verify): typed rules via the report, check-timetable, skill 2026-11.2"
```

---

### Task 5: The draft on the server: upload, check, decide, publish

**Files:**
- Create: `draft.py`
- Modify: `app.py` (routes), `store.py` (`publish`, `pub_info` data), `tests/smoke.py`
- Test: `tests/smoke.py`

**Interfaces:**
- Consumes: Task 4's `verify.warnings`; Task 1's `model_from_files(..., spec=)`; `store.load_setup() -> (spec, saved_at)`, `store.setup_record()["v"]`, `store.apply_changes(ops, client)`, `store.publish`, `store.DATA`, `store.write_json/read_json`, `app._uploaded_timetable` (reshaped below), `access`/`need`.
- Produces in `draft.py`:
  - `DIR = os.path.join(store.DATA, "draft")`.
  - `save(setup_path, timetable_path, source) -> None`: replaces `DIR` (write into `DIR + ".new"`, swap in), keeps the files as `setup.xlsx` / `timetable.<ext>`, writes `meta.json` (`source, uploaded_at=store.now(), config_id` from the file's setup when it has one, `fixes=[]`); carries over `"left"` decisions from the old `decisions.json` (all of them; `info()` drops the ones whose keys do not reappear).
  - `exists() -> bool`; `paths() -> (setup_path|None, timetable_path)`.
  - `model(spec) -> dict`: `model_from_files(*paths(), spec=spec)`.
  - `info() -> dict | None`: `None` with no draft, else the model against the current setup and `dict(source, uploaded_at, config_id, setup_version=f"v{v}", config_state (the same five states as today's import), school, timetable, lessons, classes, teachers, students, after, notes, rule_report, choices_used, choices (count, as today), typed (count), warnings=[w + dict(decision=decisions.get(key))], not_checked, open, left, fixes=[], other_school)`; `open` = warnings with no decision or `"left"`, `left` = with `"left"`. Writes `decisions.json` back without the keys that no longer appear. Raises `LookupError` when there is no saved setup.
  - `decide(key, answer) -> dict`: `answer` ∈ `"step5" | "left" | "open"` (`"open"` removes the decision). `"step5"`: finds the warning by key in a fresh `info()`; no warning → `ValueError("That warning is no longer on the list.")`; `ops is None` → `ValueError("This difference is set on step 3 for the whole level; the app does not change it from here.")`; else `store.restore_point("Before updating step 5 from the timetable")` (so the change can be undone from the earlier copies), then `store.apply_changes(ops, client="draft")` and the decision `dict(answer="step5", at=store.now())`; a `store.Refused`/`LookupError` → `ValueError(str)`. Returns `info()` afterwards.
  - `publish() -> dict`: `store.publish(setup_path, timetable_path, source=meta["source"], spec=current, extra=dict(compared_v=v, open=n, left=[w["text"] for left], decisions={key: answer}, fixes=[]))`; returns `info()` with `published=True`.
- Produces in `store.publish(setup_xlsx, timetable_path, run_id=None, source=None, log=print, spec=None, extra=None)`: `spec` passed to `model_from_files`; `extra` merged into `meta.json`; `config_id` in the meta stays the file's. `pub_info()` (in `app.py`) adds `compared_v`, `open`, `left`, `fixes` from the meta (defaults `""`, 0, `[]`, `[]`).
- Produces in `app.py`:
  - `POST /api/draft` (committee; form fields `setup`, `timetable` as today): reads the files with `_uploaded_timetable` logic but **without** building the model against the file's setup; `draft.save(...)`; returns `draft.info()`. Errors: no saved setup → `409 {"error": "Save the school's setup first: the timetable is checked against it."}`; unreadable file → `400` with the sentence; a draft with unpublished fixes (`meta["fixes"]` non-empty) and no form field `replace=1` → `409 {"error": "The draft has fixes that were never published.", "fixes": n}`.
  - `GET /api/draft` (committee): `draft.info()` or `{"draft": None}`.
  - `POST /api/draft/decide` (committee; JSON `{key, answer}`): `draft.decide` → info; `ValueError` → `400 {"error": sentence}`.
  - `POST /api/draft/publish` (committee): `draft.publish()`; no draft → `404`.
  - `/api/import-timetable` is removed; `/api/export` keeps `_uploaded_timetable` (it still builds the model from the files' own setup, as printouts do today).
  - `/api/status` gains `draft`: `None` or `dict(uploaded_at, source, open)` (no model build: read `meta.json` and count `decisions.json` is not enough for `open`, so cache the last `info()`'s `open` in `meta.json` as `open` when `info()` runs).
- `tests/smoke.py`: `test_a_head_cannot_download_or_publish_or_replace` lists `POST /api/draft` instead of `/api/import-timetable`; `test_publish_uploaded_timetable` (`--full`) uploads to `/api/draft`, asserts `open >= 0` and the `warnings` list has every key once, then `POST /api/draft/publish`, then `/api/status` `published.compared_v == "v..."`.

- [ ] **Step 1: Write the failing server tests** (in `tests/smoke.py`, fast ones; the primary sample's setup saved via `PUT /api/setup`, a one-lesson Lessons workbook built as `tests/test_rules.py` does)

```python
def test_draft_needs_a_saved_setup():        # Review Focus 1: run before the setup is saved (order the tests so)
    r = c.post("/api/draft", data={"setup": (...), "timetable": (...)}); assert r.status_code == 409 and "setup first" in r.get_json()["error"]

def test_draft_upload_check_decide_publish():
    ... PUT the primary sample; POST /api/draft with the one-lesson workbook
    j = r.get_json(); assert r.status_code == 200 and j["open"] == len(j["warnings"]) and j["config_state"] in ("same", "older", "unknown", "unsaved")
    k = next(w["key"] for w in j["warnings"] if w["key"].endswith(":teachers")) ... (the workbook's lesson names a teacher step 5 does not)
    j2 = c.post("/api/draft/decide", json={"key": k, "answer": "left"}).get_json(); assert j2["left"] == 1 and j2["open"] == j["open"]
    j3 = c.post("/api/draft/decide", json={"key": k, "answer": "step5"}).get_json(); assert k not in {w["key"] for w in j3["warnings"]}   # step 5 now matches
    spec = c.get("/api/setup").get_json()["spec"]; assert "Nobody" in next(x["teachers"] for x in spec["lessons"] if x["_id"] == <the row>)
    kp = next(w["key"] for w in j3["warnings"] if w["key"].endswith(":periods")); r = c.post("/api/draft/decide", json={"key": kp, "answer": "step5"}); assert r.status_code == 400 and "step 3" in r.get_json()["error"]
    assert c.get("/api/status").get_json()["draft"]["open"] == j3["open"]

def test_draft_decisions_survive_a_setup_change_and_stale_ones_go():   # Review Focus 2
    ... "left" on a missing-row warning; delete that row through /api/setup/changes; GET /api/draft: the key is gone and the decision with it; POST decide step5 on a now-missing key → 400 "no longer on the list"

def test_a_new_upload_keeps_left_decisions():
    ... upload the same workbook again; the "left" decision on a key that reappears is still there

def test_draft_for_another_school_is_said():
    ... other_school set when the workbook's setup names another school (as the import did)
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/bin/python tests/smoke.py`
Expected: FAIL: `404` from `/api/draft`

- [ ] **Step 3: Implement `draft.py`, the routes, `store.publish(spec=, extra=)`, `pub_info`, `/api/status`'s `draft`**

`info()` must not rebuild the model twice per request: build once, pass to `verify.warnings`. `_uploaded_timetable` becomes `_save_uploads(work) -> (setup_path|None, timetable_path)` plus the model build where `/api/export` needs it.

- [ ] **Step 4: Run the server tests, fast and full**

Run: `.venv/bin/python tests/smoke.py && .venv/bin/python tests/smoke.py --full`
Expected: all checks passed (the counts grow by 5; `--full` publishes through the draft)

- [ ] **Step 5: Commit**

```bash
git add draft.py app.py store.py tests/smoke.py
git commit -m "feat(draft): the uploaded timetable as a draft with warnings, decisions and publish"
```

---

### Task 6: Step 8 in the browser: the draft card, the warning list, the decisions, Published now

**Files:**
- Create: `static/draft.js`, `tests/draft.test.js`
- Modify: `static/app.js` (`exportCard`, `importTimetable`, `importHTML`, `paintPublished`, the click handler, `starterPrompt` unchanged), `static/index.html` (script tag before `app.js`), `static/style.css`, `README.md`

**Interfaces:**
- Consumes: Task 5's `/api/draft` family and `/api/status.draft`, `published.compared_v/open/left/fixes`; the warning and decision shapes.
- Produces in `static/draft.js` (global `Draft`, pure functions, loadable in Node like `static/choices.js`):
  - `Draft.KINDS = ["clash", "deployment", "rule", "typed", "choice"]`, `Draft.KIND_TEXT = {clash: "Clashes", deployment: "Differences from the deployment", rule: "Rules", typed: "Rules in words", choice: "Choices used"}`.
  - `Draft.isOpen(w) -> bool` (no decision or `left`).
  - `Draft.group(warnings, filter) -> [{kind, title, groups: [{name, items: [w]}]}]`: by kind in `KINDS` order, then by `group` in first-seen order, `filter` ∈ `"open" | "left" | "all"`; kinds with no items are left out.
  - `Draft.counts(warnings) -> {open, left, step5, must, prefer}`.
  - `Draft.answerText(w) -> str`: `"Left for now"`, `"Step 5 updated"`, `"Fixed"` or `""`.
  - `Draft.sideText(w) -> str`: `"Timetable: A · Step 5: B"` or `""`.
- Produces in `static/app.js`:
  - `exportCard()` becomes the **draft card**: the file pickers and `Make printouts` as today; the button `Check` (`id="imCheck"`) uploads to `/api/draft` (with `replace=1` after a `confirm` when the server answers 409 about fixes); below it `draftHTML(j)` replaces `importHTML(j)`.
  - `draftHTML(j)`: the head line as today; `configLine(j)`; a line `"{open} warning{s} open · {left} left for now · {step5} settled on step 5"`; the filter radios open / left / all; the grouped list from `Draft.group`: each kind a `<details open>` with `KIND_TEXT` and its count, each group a `<h4>`, each warning a row with its text, `sideText`, `where` as `"{cls} · {day} · period {p}"`, and the buttons `Update step 5` (`data-decide="step5|{key}"`, only when `ops` is not null) and `Leave it` / `Reopen` (`data-decide="left|{key}"` / `"open|{key}"`), plus the decision's text; above the list one muted sentence `"Fixing a lesson in the app comes in the next stage. Until then, fix the file and upload it again: what you left for now stays left."`; `not_checked` as a muted list under the Rules kind; then `ruleReportHTML`, `choicesUsedHTML`, notes and after-school lists as today; then the publish line `"{open} warnings open; you can still publish."` and `Publish this timetable` (`id="imPublish"` → `POST /api/draft/publish` after the confirm), with the replace sentence as today.
  - On step 8 render, when `G.st.draft` exists and `S.draft` (the last `/api/draft` answer) is empty, fetch `/api/draft` once and draw it, so the draft survives a reload. The published card (`paintPublished`) adds `"Checked against the setup at {compared_v}"`, `"{open} warnings were left open"` with the `left` sentences in a `<details>`, and `"No fixes were made in the app."` / `"{n} fixes"` (the list comes in stage 2).
  - Clicks: `data-decide` → `POST /api/draft/decide`, redraw from the answer, toast the error sentence on 400.
- `style.css`: `.warn` rows, the kind `<details>` summaries, the decision chip.
- `README.md`: the Publish item (step 5 of "From setup to published timetable") rewritten: upload makes a draft; four checks; grouped warnings; update step 5 / leave it; publish with warnings and the compared-against version; `python -m ttgen check-timetable` for the agent; the removed sentence "A later project checks the report against the timetable; today the app keeps and shows it." goes.

- [ ] **Step 1: Write the failing Node tests**

```js
// tests/draft.test.js (the pattern of tests/choices.test.js: load static/draft.js in a vm, plain asserts)
const W = (key, kind, group, decision) => ({ key, kind, text: key, strength: "Must", group, where: null, sides: null, ops: null, decision });
t("grouping by kind then group, open only", () => {
  const ws = [W("c1", "clash", "Ms X"), W("d1", "deployment", "1A"), W("d2", "deployment", "1A", { answer: "step5" }), W("d3", "deployment", "1B", { answer: "left" }), W("r1", "rule", "School")];
  const g = Draft.group(ws, "open"); assert.deepEqual(g.map(x => x.kind), ["clash", "deployment", "rule"]);
  assert.deepEqual(g[1].groups.map(x => [x.name, x.items.length]), [["1A", 1], ["1B", 1]]);
  assert.deepEqual(Draft.group(ws, "left")[0].groups[0].items.map(w => w.key), ["d3"]);
});
t("counts", () => { ... open 4, left 1, step5 1 ... });
t("texts", () => { assert.equal(Draft.sideText({ sides: { timetable: "Mr Tan", step5: "Mdm Lee" } }), "Timetable: Mr Tan · Step 5: Mdm Lee"); assert.equal(Draft.answerText({ decision: { answer: "left" } }), "Left for now"); });
```

- [ ] **Step 2: Run them to verify they fail**

Run: `node tests/draft.test.js`
Expected: FAIL: cannot find `static/draft.js`

- [ ] **Step 3: Implement `static/draft.js`; run the Node tests**

Run: `node tests/draft.test.js`
Expected: `3 checks passed`

- [ ] **Step 4: Rebuild step 8 in `app.js`, the styles, the script tag, the README**

Run: `node --check static/app.js && node tests/sync.test.js && node tests/choices.test.js`
Expected: no syntax error; the existing counts

- [ ] **Step 5: Check the page in the browser preview against a scratch `DATA_DIR`**

Start the scratch server (port 8003, the README's example codes, a temporary `DATA_DIR`), sign in as the committee, open the primary sample into the school's setup, download the workbook, build a Lessons workbook with one lesson whose teacher is not on step 5 (as the tests do) and upload it on step 8. Expected: the draft card shows the open count, the Differences group names the class, `Update step 5` closes the teacher warning and step 5 shows the new teacher, `Leave it` moves one warning to the left filter, reloading the page brings the draft back, Publish works with warnings open, and Published now shows "Checked against the setup at v…" and the left sentences. Take a screenshot of the draft card for the report. Remove the scratch configuration afterwards.

- [ ] **Step 6: Run every suite, commit**

Run: `.venv/bin/python tests/test_verify.py && .venv/bin/python tests/test_choices.py && .venv/bin/python tests/test_rules.py && .venv/bin/python tests/test_sync.py && .venv/bin/python tests/smoke.py && node tests/draft.test.js && node tests/choices.test.js && node tests/groups.test.js && node tests/map.test.js && node tests/people.test.js && node tests/sync.test.js && node --check static/app.js`
Expected: every suite passes

```bash
git add static tests/draft.test.js README.md
git commit -m "feat(publish): step 8 draws the draft, its warnings and the decisions"
```

---

## Not in this plan

- The fix-up grid, the helper, the typed request (stages 2 to 4): the `fixes` list stays empty and the `"fixed"` answer is never written.
- Showing a draft to heads (project 3).
- The Railway volume: the app's existing no-volume warning covers the draft too (`store.on_volume()` is already shown on step 8).

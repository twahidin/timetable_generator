# Class Parents Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A class has form teachers (the school's own word, "Class Parents" at CTSS, up to a school maximum); a default rule puts them on the class's lessons of the subjects the school names, all together, and the committee can change any one such lesson by hand.

**Architecture:** One pure rule, written twice and kept in step by a shared file of cases: `static/parents.js` for the page and `ttgen/parents.py` for the server, the workbook reader and the skill. The page runs it inside `save()` (so an edit and what it does to the lessons are one Undo step and one batch of changes); the server runs it again after every change it stores and logs what it had to put right under its own client id, so every browser hears of it. The workbook grows its Teacher columns to the widest lesson and gains a "Changed by hand" column, Class Parents columns on Classes and three Settings rows.

**Tech Stack:** Flask, vanilla JS (no build step), openpyxl through `ttgen`, plain-script tests (`node tests/x.test.js`, `.venv/bin/python tests/x.py`).

**Spec:** `docs/superpowers/specs/2026-11-11-class-parents-design.md` (approved 2026-11-11). A map of the code as it stood when this was planned is quoted where needed below.

**Base:** branch `class-parents` (from `main`, holding the spec and this plan). Stage 3 of the return trip (pull request 46) must be on `main` and merged into this branch before Task 1, because both change `static/app.js`, `draft.py` and `README.md`. Function names are given, not line numbers.

## Global Constraints

- Data, exact names: `spec.school.parents_name` (text, default `"Form teachers"`), `spec.school.parents_max` (whole number 1 to 6, default 2), `spec.school.parents_subjects` (list of subject names, default `[]` = the rule is off), `spec.classes[i].parents` (list of teacher names, no blanks, may be absent), `spec.lessons[i].by_hand` (`true` or absent).
- A **staffed row** is a lesson row whose subject is in `parents_subjects` and which is whole-class (`!block && !code_override`). It **follows** unless `by_hand` is true.
- A following row with at least one Class Parent among its classes has exactly `want(row)` as its teachers: the Class Parents of each of its classes, in class order then box order, each name once. A following row whose classes have no Class Parents at all is left as it is.
- A row is made for a class when the subject is named, the subject has periods above 0 at the class's level, and the class has no row of that subject at all (whole-class, group or block). Its `_id` is `"cp-" + class row _id + "-" + subject row _id`, so two browsers make the same row once.
- Teachers already typed are never replaced unasked: when a subject is first named, when a class first gets Class Parents, on the first fill and when a workbook without the "Changed by hand" column is read, a staffed row with teachers that are not the same people as `want(row)` (order ignored) is marked `by_hand`.
- `by_hand` is set in the same change as the teachers it protects; with the rule off, or for a subject taken out of it, no row keeps the mark.
- Only the committee changes `parents`, the three school settings, a staffed row's `teachers` or `by_hand`, and only the committee adds or deletes a staffed row. The server refuses a department head's attempt with a sentence; the page disables the controls.
- A staffed row may hold `max(3, parents_max)` teachers by hand and any number when it follows a shared row; every other row keeps three.
- A Class Parent on a staffed row of their own class is never reported as "not set to teach".
- `ttgen/` and `skill/school-timetable-generator/scripts/ttgen/` stay byte-identical (`tests/test_rules.py::the_skill_copy_is_identical`). `SKILL_VERSION` becomes `"2026-11.3"`.
- Sentences are plain, with no em-dashes or arrows. `{name}` below is `parents_name` as typed. Exact sentences are given where a test reads them.
- Made-up names only in tests, samples and docs. Nothing under `data/` or `.claude/` is touched or committed.
- Plan-level calls that differ from the spec's wording, each to be listed in the notes file at the end: workbook headings are `"{name} 1"` to `"{name} N"` (the name as typed, not a singular); the Things to fix sentence for a class with none is `"{class} has no {name} yet."`; the workbook's own Check column does not test Can teach on lessons of the named subjects at all; the step 4 paste-list "Remove", which already strips a teacher from lessons, strips them from Class Parents too.

## Review Focus

1. A stale or second committee tab, or a department head's tab, saving after the Class Parents changed: every following row is right on the server afterwards and every open browser hears of it. Pinned in Task 4.
2. Undo after changing a class's Class Parents puts the box and every lesson it changed back in one step, and does not leave the lessons marked "Changed by hand". Pinned in Tasks 2 and 5.
3. A workbook written with four teachers on a lesson, read back, written again: no teacher lost, Note and Special room weeks still in their own columns, no Settings row doubled. Pinned in Task 3.
4. A setup shaped like CTSS's (two named subjects whose rows name the same one to three teachers per class, a third named subject with no lessons, classes with no Class Parents yet): naming the subjects and pressing the first fill replaces nobody's typed teachers and leaves every class's rows following. Pinned in Tasks 1 and 2.
5. A setup or published timetable saved before this change (no `parents`, no settings, an older pickled model): every page opens and reads as today. Pinned in Tasks 1, 3 and 6.

---

### Task 1: the rule, twice (`static/parents.js`, `ttgen/parents.py`) with shared cases

**Files:**
- Create: `static/parents.js`, `ttgen/parents.py`, `skill/school-timetable-generator/scripts/ttgen/parents.py` (identical copy), `tests/parents_cases.json`, `tests/parents.test.js`, `tests/test_parents.py`
- Modify: `static/index.html` (a `<script src="/static/parents.js">` before `app.js`, beside the other modules)

**Interfaces:**
- Produces (JS, on `Parents`, exported with the `if (typeof module !== "undefined") module.exports = Parents;` tail the other modules use; Python functions of the same names in snake_case with the same results):
  - `Parents.names(row) -> string[]`: a row's teachers (or a class's `parents`) with blanks dropped.
  - `Parents.subjects(spec) -> string[]`: `school.parents_subjects` limited to subjects on step 3.
  - `Parents.cap(spec) -> number`: `max(3, Number(school.parents_max) || 2)`.
  - `Parents.label(spec) -> string`: `school.parents_name` trimmed, or `"Form teachers"`.
  - `Parents.staffed(spec, row) -> boolean`; `Parents.follows(spec, row) -> boolean` (staffed and not `by_hand`).
  - `Parents.want(spec, row) -> string[]`.
  - `Parents.same(a, b) -> boolean`: the same names, order ignored.
  - `Parents.adopt(spec, only) -> number`: marks `by_hand` on every following row that has teachers, has a non-empty `want`, and whose teachers are not `same` as it; `only` is `null` or `{subjects?: string[], classes?: string[]}` limiting which rows are looked at; returns how many were marked.
  - `Parents.derive(spec) -> boolean`: puts the setup right (Global Constraints: marks dropped where the row is no longer staffed, following rows set to `want`, missing rows made at the end of `lessons` with `{_id, level, subject, block: null, classes: [cls], teachers, students: null}`); returns whether anything changed. Running it twice changes nothing the second time. A setup with no `parents_subjects` and no marks is returned untouched (Review Focus 5).
- Python: `ttgen.parents.names, subjects, cap, label, staffed, follows, want, same, adopt(spec, only=None), derive(spec)`.

- [ ] **Step 1: Write the shared cases** in `tests/parents_cases.json`: a list of `{"name", "spec", "adopt" (optional: the `only` argument, or `null` to run adopt on everything; absent = adopt is not run), "after"}`; each test loads the spec, runs `adopt` when asked, runs `derive`, and compares the whole spec with `after`. Cases, one each, small specs with `_id`s, classes `1A`, `1B`, teachers `Tan`, `Lim`, `Goh`, `Ong`, `Koh`, subjects `CP Time` and `CE 1` with periods `{"Sec 1": 1}`:
  - `off-is-untouched`: no `parents_subjects`; `after` equals `spec`.
  - `off-drops-marks`: no `parents_subjects`, one row with `by_hand: true`; the mark is gone.
  - `follows-the-box`: `1A.parents = [Tan, Lim]`, a `CE 1` row for `1A` with `[Lim]`; after: `[Tan, Lim]`.
  - `order-is-the-box-order`: row `[Lim, Tan]`, box `[Tan, Lim]`; after `[Tan, Lim]`.
  - `no-parents-leaves-the-row`: `1A.parents` absent, row `[Goh]`; unchanged, no mark.
  - `by-hand-stays`: row `by_hand: true` with `[Goh]`, box `[Tan, Lim]`; unchanged.
  - `makes-the-missing-lesson`: `CP Time` named, no row for `1A`; after has a row `_id` `cp-<1A id>-<CP Time id>`, `level` the class's, `teachers` the box, at the end.
  - `makes-none-without-periods`: the subject has no periods at the class's level; nothing made.
  - `makes-none-when-taught-in-groups`: a block row of the subject holds `1A`; nothing made, the block row untouched.
  - `shared-row-takes-both`: one whole-class row for `[1A, 1B]`, boxes `[Tan, Lim]` and `[Lim, Goh]`; after `[Tan, Lim, Goh]`.
  - `blank-names-are-dropped`: box `[Tan, null, "", Lim]`; the row gets `[Tan, Lim]`.
  - `subject-not-on-step-3-is-ignored`: `parents_subjects` names a subject that is not in `subjects`; nothing made, no error.
  - `adopt-marks-other-people`: `"adopt": null`, box `[Tan, Lim]`, one row `[Goh]`, one row `[Lim, Tan]`, one row `[]`; after: the first `by_hand: true` and still `[Goh]`, the second `[Tan, Lim]` with no mark, the third `[Tan, Lim]`.
  - `adopt-only-one-class`: `"adopt": {"classes": ["1A"]}` with differing rows for `1A` and `1B`; only `1A`'s row is marked, `1B`'s is set to its box.
  - `ctss-shape` (Review Focus 4): `CE 1` and `CE 2` rows for `1A` both `[Tan, Lim]` and for `1B` `[Goh]` and `[Goh, Ong]`, `CP Time` named with no rows, boxes `1A [Tan, Lim]`, `1B [Goh, Ong]`, `"adopt": null`; after: `1B`'s `[Goh]` row is `by_hand`, the others follow, two `CP Time` rows made.

- [ ] **Step 2: Write `tests/parents.test.js` and `tests/test_parents.py`**, each running every case (`assert.deepStrictEqual` / `==` on the whole spec) and a second `derive` returning false, in the style of `tests/sync.test.js` and `tests/test_sync.py` (`t(name, f)` counter, final line `N cases passed`). Add to both a direct check of `staffed`, `follows`, `want`, `same`, `cap` (2 gives 3, 4 gives 4, `"x"` gives 3) and `label` (blank gives `"Form teachers"`).

- [ ] **Step 3: Run both, see them fail**

Run: `node tests/parents.test.js` and `.venv/bin/python tests/test_parents.py`
Expected: FAIL, the module is not found.

- [ ] **Step 4: Implement both modules and the script tag**, then copy `ttgen/parents.py` to the skill.

- [ ] **Step 5: Run them and the copy test**

Run: `node tests/parents.test.js && .venv/bin/python tests/test_parents.py && .venv/bin/python tests/test_rules.py`
Expected: both pass with the same count (the 15 cases and the direct checks), and `10 checks passed`.

- [ ] **Step 6: Commit** `feat(parents): the Class Parents rule, on the page and in ttgen, with shared cases`

---

### Task 2: what the page does on an edit (`static/parents.js`, page-only half)

**Files:**
- Modify: `static/parents.js`, `tests/parents.test.js`

**Interfaces:**
- Consumes: Task 1.
- Produces (JS only):
  - `Parents.settle(spec, prev, hand) -> boolean`: called from `save()`. When `hand` is true and `prev` (the setup as last saved) is given, first marks hand edits: a following row whose teachers differ (not `same`) from the same row in `prev`, while `want` of that row is equal in `prev` and now, gets `by_hand = true`; a following row that is not in `prev`, has teachers and is not `same` as a non-empty `want`, gets `by_hand = true`. Then `derive(spec)`. Returns whether anything changed.
  - `Parents.setParents(spec, classIndex, list) -> void`: sets the class's `parents` to `list` with blanks dropped and repeats removed. From none to some: `adopt(spec, {classes: [cls]})` first. From some to none: clears the teachers of every following row all of whose classes now have none. It does not call `derive` (the caller's `save()` does).
  - `Parents.setSubjects(spec, list) -> void`: sets `school.parents_subjects`; for each subject newly named, `adopt(spec, {subjects: [s]})`.
  - `Parents.setMax(spec, n) -> string | null`: refuses below 1, above 6, or below what a class has, returning `"{classes joined with ', '} already have more than {n}."` (`"1A already has more than 1."` for one class); otherwise sets it and returns null.
  - `Parents.fillCount(spec) -> number` and `Parents.fill(spec) -> number`: the classes with no Class Parents that would get some from their staffed rows (teachers in row order, each once, up to `parents_max`); `fill` sets them through `setParents` and returns how many classes were filled.
  - `Parents.handRows(spec) -> number[]`: indexes of staffed rows with `by_hand`. `Parents.back(spec, i) -> void`: removes the mark from row `i`. `Parents.backAll(spec) -> number`.
  - `Parents.exempt(spec, row, name) -> boolean`: `row` is staffed and `name` is a Class Parent of one of its classes.
  - `Parents.of(spec, name) -> string[]`: the classes `name` is a Class Parent of.
  - `Parents.issues(spec) -> {kind, i, text}[]` with `kind` `"classes"`, `"teachers"` or `"config"` and `i` the row index (0 for `config`), in this order and wording:
    - a class with no Class Parents while the rule names a subject and the class has a following row: `"{class} has no {name} yet."`
    - a Class Parent not on the step 4 list: `"{class}: {teacher} is not on the teacher list."` (kind `classes`)
    - a teacher who is a Class Parent of two or more classes: `"{teacher} is one of the {name} of {A} and {B}: their lessons together cannot be at the same time."` (kind `teachers`, `i` the teacher's row; three or more classes are joined `A, B and C`)
    - a named subject no longer on step 3: `"{name} take {subject}, which is not on step 3."` (kind `config`)
    - a named subject taught to a class in groups: `"{subject} for {class} cannot be staffed by its {name}: it is taught in groups."` (kind `classes`)

- [ ] **Step 1: Write the failing tests** in `tests/parents.test.js` (names are the behaviour):

```js
t("a hand change of a following lesson is marked, and stays", () => {
  const prev = base(); const now = clone(prev); row(now, "ce1-1A").teachers = ["Goh"];
  assert.strictEqual(Parents.settle(now, prev, true), true);
  assert.deepStrictEqual([row(now, "ce1-1A").by_hand, row(now, "ce1-1A").teachers], [true, ["Goh"]]);
});
t("the same change arriving from elsewhere (hand false) is put back, not marked", () => { /* settle(now, prev, false): teachers back to the box, no mark */ });
t("changing the box moves the lessons and marks nothing (Review Focus 2)", () => { /* setParents(now, 0, ["Tan","Goh"]); settle(now, prev, true): both rows [Tan, Goh], no by_hand anywhere */ });
t("undoing a box change marks nothing", () => { /* prev has box [Tan,Goh] and rows [Tan,Goh]; now is the earlier state (box and rows [Tan,Lim]); settle(now, prev, false) leaves it exactly so */ });
t("a row split off by hand with other teachers is marked", () => { /* now has a new staffed row for 1B with [Koh], not in prev; settle(now, prev, true) marks it */ });
t("first Class Parents for a class keep what was typed (Review Focus 4)", () => { /* 1B has none, its CE 1 row is [Goh]; setParents(spec, 1, ["Goh","Ong"]) then derive: CE 1 row by_hand with [Goh]; its CE 2 row [Goh, Ong] follows */ });
t("taking every Class Parent off clears the following lessons, not the hand-changed ones", () => {});
t("naming a subject keeps typed teachers and makes the missing lessons", () => {});
t("setMax refuses below what a class has, with the classes named", () => { assert.strictEqual(Parents.setMax(spec, 1), "1A already has more than 1."); });
t("fill takes them from the lessons, in order, up to the maximum, and never touches a class that has some", () => {});
t("back and backAll put the Class Parents on again", () => {});
t("exempt is true only for a Class Parent of the row's own class on a staffed row", () => {});
t("issues: the five sentences, in order", () => { /* build one spec with all five and compare the whole list */ });
t("issues on a setup from before this change is empty", () => { assert.deepStrictEqual(Parents.issues(old()), []); });
```

- [ ] **Step 2: Run, see them fail** (`node tests/parents.test.js`: `Parents.settle is not a function`).
- [ ] **Step 3: Implement the functions.**
- [ ] **Step 4: Run** `node tests/parents.test.js` → all pass, 14 more than after Task 1. `.venv/bin/python tests/test_parents.py` passes with its Task 1 count.
- [ ] **Step 5: Commit** `feat(parents): hand changes, first fill, the maximum and the things to fix`

---

### Task 3: the workbook (`ttgen/template.py`, `ttgen/reader.py`) and the skill version

**Files:**
- Modify: `ttgen/template.py`, `ttgen/reader.py`, `ttgen/spec.py` (`SKILL_VERSION = "2026-11.3"`), the same three under `skill/school-timetable-generator/scripts/ttgen/`, `skill/school-timetable-generator/SKILL.md` (the version line; one sentence: the Lessons sheet may have more than three Teacher columns; the "Changed by hand" column and the Classes sheet's form-teacher columns are the app's own and need nothing from the agent), `README.md` (the version), `tests/test_rules.py` (the version pin), `tests/test_parents.py`

**Interfaces:**
- Consumes: `ttgen.parents.adopt`, `derive`, `label`, `subjects`.
- Produces:
  - `write_template(spec, path)`: Teacher columns on Lessons number `max(3, widest lesson's teachers with blanks dropped)` (replace the module constant `NTCH` by a value worked out per workbook, as `NCLS` is; it feeds `TC`, the Teachers sheet's load formula, the Check formula, `LIN`, `c0`); a last Lessons column `"Changed by hand"` (`Yes` or blank) added after `"Special room weeks"`, with Note and Special room weeks still found by name (`COL[...]`), not by position; Classes columns `"{name} 1"` to `"{name} N"` after Note (N = `parents_max`, or the widest class if larger), validated against the teacher list like a lesson's teacher cell; three Settings rows with these exact labels: `"Form teachers are called"` (the name), `"Most form teachers for a class"` (the number), `"Form teachers take these lessons"` (the subjects joined with `", "`); they are written only when `parents_name`, `parents_max` or `parents_subjects` is set or a class has `parents`. The Check formula's Can teach test is left out for rows of the named subjects.
  - `read_template(path) -> spec`: reads any number of `"Teacher N"` columns (and of `"Class N"` columns: remove the caps of 3 and 12); `by_hand: True` where "Changed by hand" is Yes; the three Settings rows into `school.parents_name`, `parents_max`, `parents_subjects` (the labels added to `known`, never into `extra_settings`); `classes[i].parents` from the columns headed `"{name} N"`; when the Lessons sheet has no "Changed by hand" column and subjects are named, `parents.adopt(spec)`. A workbook without any of it reads exactly as before.

- [ ] **Step 1: Write the failing tests** in `tests/test_parents.py` (a section after the cases, built on `ttgen.samples.primary()` with made-up changes):

```python
@t
def four_teachers_and_class_parents_survive_the_workbook():          # Review Focus 3
    sp = with_parents(primary())          # parents_name "Class Parents", parents_max 4, one subject named, 1A's parents four names, one staffed row by_hand, one lesson with a note and room weeks
    a = read(write(sp)); b = read(write(a))
    assert teachers_of(a) == teachers_of(sp) and any(len(x["teachers"]) == 4 for x in a["lessons"])
    assert [c.get("parents") or [] for c in a["classes"]] == [c.get("parents") or [] for c in sp["classes"]]
    assert {k: a["school"].get(k) for k in KEYS} == dict(parents_name="Class Parents", parents_max=4, parents_subjects=[SUBJ])
    assert [bool(x.get("by_hand")) for x in a["lessons"]] == [bool(x.get("by_hand")) for x in sp["lessons"]]
    assert notes_and_room_weeks(a) == notes_and_room_weeks(sp)        # still in their own columns
    assert a["school"]["extra_settings"] == sp["school"]["extra_settings"] and b == a      # nothing doubled on the second trip

@t
def a_workbook_from_before_reads_as_before():                         # Review Focus 5
    sp = read(write(primary())); assert not any("parents" in c for c in sp["classes"]) and not any(k in sp["school"] for k in KEYS) and not any(x.get("by_hand") for x in sp["lessons"])
    h = lessons_headings(write(primary())); assert [x for x in h if x.startswith("Teacher ") and x != "Teacher periods"] == ["Teacher 1", "Teacher 2", "Teacher 3"] and h[-1] == "Changed by hand"
    assert not any(str(k).startswith("Form teachers") for k in settings_labels(write(primary()))) and classes_headings(write(primary()))[-1] == "Note"   # the Settings rows and the Classes columns appear only when used

@t
def a_workbook_without_the_column_keeps_typed_teachers():
    ...  # write with_parents, delete the "Changed by hand" column (as tests/test_rules.py::an_older_workbook_without_the_column_still_reads does), read: the staffed row with other people is by_hand, the row with the same people is not

@t
def the_workbook_does_not_check_can_teach_on_the_named_subjects():
    ...  # the Check formula of a staffed row holds no "not set to teach" branch; an ordinary row's still does

@t
def the_skill_version_is_2026_11_3():
    assert spec.SKILL_VERSION == "2026-11.3" and "2026-11.3" in open(SKILL_MD).read() and "2026-11.3" in open(README).read()
```

- [ ] **Step 2: Run, see them fail** (`.venv/bin/python tests/test_parents.py`: the fourth teacher is missing after the round trip).
- [ ] **Step 3: Implement** in `template.py`, `reader.py`, `spec.py`; update `SKILL.md`, `README.md`, the pin in `tests/test_rules.py`; copy the three `ttgen` files to the skill.
- [ ] **Step 4: Run** `.venv/bin/python tests/test_parents.py` → all pass, 5 more than after Task 1; `.venv/bin/python tests/test_rules.py`, `tests/test_choices.py`, `tests/test_verify.py`, `tests/test_fixes.py`, `tests/smoke.py` → all pass with their present counts (workbooks are written all over those suites).
- [ ] **Step 5: Commit** `feat(workbook): Teacher columns that grow, Class Parents columns, Changed by hand; skill 2026-11.3`

---

### Task 4: the server keeps it right, and a head cannot change it (`store.py`, `sync.py`)

**Files:**
- Modify: `store.py`, `sync.py`, `tests/test_sync.py`, `tests/smoke.py`

**Interfaces:**
- Consumes: `ttgen.parents.derive`, `staffed`.
- Produces:
  - `store._load()` and `store.replace_setup(spec, why)`: `parents.derive(spec)` after `sync.ensure_ids`, before the setup is written.
  - `store.apply_changes(...)`: after `sync.apply` and its log entry, a copy of the setup is derived; when that changed anything, the changes (`sync.diff(before, after)`) are applied as a further version and logged with `client="parents"`; the version returned is the last one, so the caller's reply (`changes_since(since, client, upto=v)`) carries them to the sender too.
  - `sync._head_why(spec, op)`: for a head, refuses with `"Only the committee can change these lessons: their teachers are the class's form teachers."` a `set` of `teachers` or `by_hand` on a staffed row, a `del` of a staffed row, and an `add` of a whole-class row whose subject is named; refuses nothing else that it allows today.

- [ ] **Step 1: Write the failing tests.** In `tests/test_sync.py`:

```python
sp = staffed_setup()      # a named subject, class 1A with parents, one staffed row "L1", one ordinary row "L2"
WHY = "Only the committee can change these lessons: their teachers are the class's form teachers."
for op in (["set", "lessons", "L1", "teachers", ["Koh"]], ["set", "lessons", "L1", "by_hand", True], ["del", "lessons", "L1"],
           ["add", "lessons", dict(_id="n1", level="Sec 1", subject=SUBJ, block=None, classes=["1B"], teachers=[]), ""]):
    assert sync.head_may(sp, [op]) == WHY, op
for op in (["set", "lessons", "L2", "teachers", ["Koh"]], ["set", "lessons", "L1", "note", "x"],
           ["add", "lessons", dict(_id="n2", level="Sec 1", subject=SUBJ, block="Band A", classes=["1B"], teachers=[]), ""]):
    assert sync.head_may(sp, [op]) is None, op
```

  In `tests/smoke.py` (committee client `c`, a second committee client id, head client `h`):

```python
def test_class_parents_are_kept_right_on_the_server():               # Review Focus 1
    # the committee names a subject and gives 1A Class Parents through /api/setup/changes with only those two ops (no lesson ops, as a stale page would)
    # → the reply's version is two above; GET /api/setup shows 1A's row of that subject with the Class Parents and a made row for every other class with periods
    # → the reply to the SENDER holds a patch with those lesson ops (they were logged under another client)
    # → a second browser asking /api/setup/changes?since=<before> gets both entries
def test_a_stale_tab_cannot_undo_a_following_lesson():
    # a committee post that sets a following row's teachers without by_hand → after it the row is the Class Parents again, and the sender is told
def test_a_hand_change_with_its_mark_is_kept():
    # set teachers and by_hand in one batch → kept; a later change of the box leaves that row alone
def test_a_head_cannot_change_a_staffed_lesson():                    # in NEED_HEADS
    # the head's set teachers is refused with WHY in j["refused"], the rest of the batch is applied
def test_a_setup_put_whole_is_put_right():
    # PUT /api/setup with a following row holding other teachers and no mark → GET shows the Class Parents on it
```

- [ ] **Step 2: Run, see them fail.**
- [ ] **Step 3: Implement** in `store.py` and `sync.py`.
- [ ] **Step 4: Run** `.venv/bin/python tests/test_sync.py` → `18 cases passed` (17 today, plus the head block); `.venv/bin/python tests/smoke.py` → the present count plus 5; `node tests/sync.test.js` unchanged.
- [ ] **Step 5: Commit** `feat(server): following lessons put right after every change, and closed to department heads`

---

### Task 5: the page: settings, the box on step 2, the first fill (`static/app.js`)

**Files:**
- Modify: `static/app.js`, `static/style.css`, `tests/smoke.py` (page-string checks only where it has them)

**Interfaces:**
- Consumes: Tasks 1 and 2. Existing: `save(o)`, `S.snap`, `inp`, `sel`, `chips`/`openPop`/`commitPop`, the delegated `change` handler with `setPath`, `issues()` with `add(kind, i, msg, hard)`, `VIEWS.school`, `VIEWS.rules`, `VIEWS.classes`, `committee()`, `headLocks`.
- Produces: no new interface for later tasks except `save()` now keeping the rule.

- [ ] **Step 1: `save(o)`**: before `Sync.ensureIds` and the compare with `S.last`, `Parents.settle(S.spec, S.snap, !(o && (o.quiet || o.remote)))`. Nothing else in `save` changes. (Every edit calls `save()` plainly; undo, a copy from the server and others' changes call it quiet or remote, so only a person's own edit can mark a lesson "Changed by hand".)
- [ ] **Step 2: School & day** (`VIEWS.school`): two fields under the school's other settings: `What your school calls a class's form teachers` (`data-k="spec.school.parents_name"`, placeholder `Form teachers`) and `Most a class can have` (a number box 1 to 6 with `data-pmax`). The number goes through `Parents.setMax`; a refusal is toasted and the box redrawn with the old value.
- [ ] **Step 3: Step 6, the Configuration card** (`VIEWS.rules`, after the `SET()` rows, drawn by hand, not through `SETTING_RULES`): a row `{name} take these lessons` with the chosen subjects as chips opening the existing subjects pop-up; Done goes through `Parents.setSubjects` then `save(); render()`. Under it one muted line: `They are put on these lessons for every class, all together. You can still change one lesson by hand on step 5.`
- [ ] **Step 4: Step 2** (`VIEWS.classes`): after Home room, exactly `parents_max` (default 2) `sel` cells per class (more for a class that already holds more) under one heading `{name}`, each listing the step 4 teachers with a blank first, a name not on the list shown as the others are (`(not on list)`); a change goes through `Parents.setParents(S.spec, i, list)` (a branch in the `change` handler for `data-parent="i|k"`, not `setPath`, which would throw on a row with no `parents`). Above the table, when the rule names a subject: `{n} lesson(s) changed by hand` with a button `Put the {name} on all of them` (asks `Put the {name} back on {n} lesson(s)? The teachers typed on them are replaced.`) when `Parents.handRows` is not empty; and, when `Parents.fillCount` is above 0, a button `Take them from the lessons` (asks `Give {n} class(es) their {name} from the teachers now on their lessons?`).
- [ ] **Step 5: Things to fix** (`issues()`): add every entry of `Parents.issues(S.spec)` with `add(kind, i, text)` (none of them hard).
- [ ] **Step 6: Step 4's paste-list Remove**: where it strips the removed teachers from lessons, strip them from every class's `parents` too.
- [ ] **Step 7: Heads**: step 2 and step 6 are already read-only for a head (`locked`); check by reading that the two new buttons and the selects are disabled there.
- [ ] **Step 8: Check in the browser** on a scratch server (a temporary entry in `.claude/launch.json` built from an existing one, `DATA_DIR` in the scratchpad, removed afterwards; the secondary sample): set the name to `Class Parents` and the most to 4; name two subjects on step 6 (one with lessons, one without) and see the missing lessons appear on step 5; pick Class Parents for a class and see its lessons take them; press Undo once and see the box and the lessons go back together with no "changed by hand" count; first fill; a class with none in Things to fix; reload and see it all kept; no console errors. Report what was and was not tried.
- [ ] **Step 9: Run** every Node suite, `node --check static/app.js`, `.venv/bin/python tests/smoke.py`.
- [ ] **Step 10: Commit** `feat(page): Class Parents on step 2, their name and maximum, and the lessons they take on step 6`

---

### Task 6: step 5, the returned timetable and the published pages

**Files:**
- Modify: `static/map.js`, `tests/map.test.js`, `static/app.js`, `static/style.css`, `ttgen/verify.py`, `ttgen/export.py`, `ttgen/timetable_page.html` (and the three `ttgen` files in the skill copy), `tests/test_verify.py`, `tests/smoke.py`

**Interfaces:**
- Consumes: Tasks 1, 2, 4.
- Produces:
  - `DeptMap.deploy(spec, card, idxs, opts)`: `opts.max` (default `DeptMap.MAX`) is the most teachers the card may hold; `opts.exempt(name) -> boolean` lets a teacher on without the subject in Can teach. The refusal for a full card says the number (`"three is the most."` stays for 3; `"four is the most."`, `"five ..."`, `"six ..."` otherwise).
  - `verify.deployment(m, spec)`: a teacher difference on a staffed row offers `ops` that also set the mark: `[["set", "lessons", id, "teachers", [...]], ["set", "lessons", id, "by_hand", True]]`.
  - `export._model`: each class gains `parents` (names, from the setup the timetable was checked against); the model gains `parents_name`. `class_view` adds `" · {name}: A, B"` to its subtitle when the class has some; `teacher_view` adds `" · {name} of 3I4"` (classes joined `", "`). `html_data` carries the parents as a fifth element of each class array and the name; `timetable_page.html` shows the same two lines. A model without the keys (published earlier) shows no line and raises nothing (Review Focus 5).

- [ ] **Step 1: Failing tests.**
  - `tests/map.test.js`: `deploy` with `opts.max = 4` puts a fourth teacher on and refuses a fifth with "four is the most."; without `opts.max` a fourth is refused as today; `opts.exempt` lets a teacher on with no basket entry and `needBasket` is not asked about them.
  - `tests/test_verify.py`: `a_teacher_difference_on_a_staffed_lesson_marks_it_by_hand` (the ops are the pair above; for an ordinary row they are as today, one op).
  - `tests/smoke.py`: `test_update_step_5_on_a_staffed_lesson_keeps_the_timetables_teachers` (upload a draft whose staffed lesson has another teacher, decide `step5`, the setup's row has that teacher and `by_hand`, and stays so after another change); `test_published_pages_name_the_class_parents` (publish; the class page data and the class PDF subtitle hold the line; a model pickled without the keys still renders).
- [ ] **Step 2: Run, see them fail.**
- [ ] **Step 3: Implement the Python side** (`verify.py`, `export.py`, `timetable_page.html`, skill copies).
- [ ] **Step 4: Implement the page side** in `static/app.js`:
  - `cardsView`: a staffed class card shows a small badge with `{name}`; its room for more is `Parents.cap(S.spec) - teachers`; a card with `by_hand` shows `Changed by hand` and a button `Back to the {name}` (`Parents.back` then `save(); render()`).
  - `placeOn` / `unplace`: pass `max: Parents.cap(S.spec)` and `exempt: nm => Parents.exempt(S.spec, row, nm)` for a staffed row.
  - the step 5 table: Teacher columns number `Parents.cap(S.spec)` when the rule names a subject (the extra cells are empty and disabled on rows that are not staffed), three otherwise; a staffed row shows `Changed by hand` and the same button in its Note cell's line; the bulk tools' three-teacher test uses the row's own most, and the toast says `already had as many teachers as they can hold`.
  - `canTeach` uses in `issues()` and in the table's teacher lists: skipped when `Parents.exempt(S.spec, row, name)`.
  - a head (`isHead()` and not a practice copy): staffed cards take no drop, click or ✕, staffed rows' teacher cells and the Back button are disabled, each with the title `Only the committee can change these lessons: their teachers are the class's {name}.`
- [ ] **Step 5: Check in the browser** (scratch server as in Task 5): a staffed card with its badge; a fourth teacher dropped on it by hand, marked Changed by hand; Back to the Class Parents; changing the box afterwards leaves a hand-changed card alone; no "not set to teach" for a Class Parent, one for a stranger put on by hand; signed in as a head with the README's example heads code on the scratch server, the staffed card refuses; publish a small draft and see the line on the class page and on a teacher's page; a cell with four names in the published grid (say what it looks like). Report what was and was not tried.
- [ ] **Step 6: Run** every suite: `node tests/*.test.js` one by one, `node --check static/app.js`, `.venv/bin/python tests/test_parents.py`, `test_sync.py`, `test_verify.py`, `test_rules.py`, `test_choices.py`, `test_fixes.py`, `test_helper.py`, `smoke.py` (and `smoke.py --full`).
- [ ] **Step 7: Commit** `feat(step 5): Class Parents on the cards and the table, by hand and back; the returned timetable and the published pages`

---

### Task 7: the README and the notes

**Files:**
- Modify: `README.md`
- Create: `docs/superpowers/plans/2026-11-11-class-parents-notes.md` (written by the controller at the end, from the ledger: rulings, the plan-level calls listed under Global Constraints, deferred points, what was not tried in a browser)

- [ ] **Step 1:** In `README.md`, where steps 2, 5 and 6 are described: what Class Parents are, the two settings, the rule and that it is a default, "Changed by hand" and "Back to", the first fill, that only the committee changes them, and that the workbook's Lessons sheet may have more than three Teacher columns. Plain sentences, the app's words.
- [ ] **Step 2:** Run `.venv/bin/python tests/test_rules.py` (it reads the README for the version) → passes.
- [ ] **Step 3: Commit** `docs: Class Parents in the README`

---

## Self-review (done when this plan was written)

- **Spec coverage.** Step 2 box, the two settings, the rule on step 6: Task 5. What the rule does, typed teachers kept, the first fill: Tasks 1 and 2. Four teachers: Tasks 3 and 6. Where they show: Task 6. The workbook: Task 3. Things to fix: Tasks 2 and 5. Committee only, the server refusing: Task 4. Following lessons right after every kind of change (the page, another tab, a workbook or file loaded, an earlier copy restored): Tasks 4 and 5. "Update step 5": Task 6. Can teach: Tasks 2, 3, 6. The maximum as a cap and lowering it: Task 2. Published pages from the checked setup: Task 6. Skill copy and version: Tasks 1, 3, 6.
- **Not covered, on purpose:** a class renamed on step 2 (as today, its lessons keep the old name; the Class Parents stay with the class row and a new lesson is made for the new name, the old ones showing under Things to fix as they do today); the print width of four names in one period of the published grid (looked at in Task 6, changed only if unreadable); `ttgen/allocate.py` handing a following lesson of a class with no Class Parents to a teacher, as it does for any lesson with none.
- **Names agree** across tasks: `parents`, `by_hand`, `parents_name`, `parents_max`, `parents_subjects`; `Parents.settle/setParents/setSubjects/setMax/fill/fillCount/handRows/back/backAll/exempt/of/issues`; `ttgen.parents.derive/adopt/staffed/want`.

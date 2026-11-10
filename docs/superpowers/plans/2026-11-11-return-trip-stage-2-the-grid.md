# Return trip stage 2: the fix-up grid — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The committee lead fixes the draft timetable inside the app: a class's or a teacher's week as a grid, a selected lesson colouring every slot it could go to, swaps and moves by hand, teacher and room changes, adding a missing lesson and deleting an extra one, every fix checked before it lands, recorded, undoable, and carried into the published record.

**Architecture:** The draft stays "the uploaded file plus a list of fixes": `meta.json`'s `fixes` holds the moves in order and a new app module `fixes.py` applies them to the file's lessons before the model is built (a new `edit=` hook on `model_from_files`), so every check, the publish and the download see the fixed timetable while the agent's file is untouched. Legality is judged in two tiers so a whole grid colours in under two seconds: an exact busy index for clashes, then the standard rules re-run on only the lessons that can interact with the moved ones, compared by count against the same subset before the move. `static/grid.js` holds the pure layout logic and `static/app.js` draws a Fix card on step 8.

**Tech Stack:** Python 3.11 (openpyxl, sqlite3), Flask, vanilla JavaScript with no build step. Python tests are plain asserts (`tests/test_verify.py` pattern); Node tests like `tests/draft.test.js`; server tests in `tests/smoke.py`.

**Spec:** `docs/superpowers/specs/2026-11-10-return-trip-design.md`, part 4 Fix: "The grid", "Moves the app knows how to make", "Block lessons", "What clean means", "Typed rules and moves", "Every move is recorded"; part 5 Publish (the list of moves, the draft download); "Suggested order of building" item 2. **Not** in this plan: the helper's suggestions for a warning and its ranking (stage 3), the typed request (stage 4).

## Global Constraints

- A **fix** is one dict in `meta.json`'s `fixes`, in the order made, each with `at` (`store.now()`) and `text` (the sentence written when it was applied) plus, by `kind`:
  - `move`: `id`, `d`, `p` (the lesson with that id starts on day index `d` at period `p`; every row of the id moves);
  - `swap`: `a`, `b` (two lesson ids of the same length exchange day and period);
  - `teacher`: `key` (`"C:{class}:{subject}"` or `"G:{code}"`, the keys of `verify.planned_rows`), `teachers` (list): every lesson of the key;
  - `room`: `id`, `group`, `room`: that row of the lesson;
  - `add`: `key`, `d`, `p`, `n`, `room`: a new lesson whose subject, classes, group, teachers, level and block come from the step 5 rows of the key; its id is 1 + the highest id in the file plus one per earlier `add`;
  - `delete`: `id`, and `group` when only one row of a block lesson goes.
- A lesson is identified by its `id` from the uploaded file (block lessons are several rows sharing an id); a row by `(id, group)`. Periods and day indexes are 0-based, as everywhere.
- A slot's **state** is one of `"ok"` (clean), `"prefer"` (the only thing that gives is a Prefer rule or a teacher's allowance), `"no"` (a clash or a Must), `"na"` (the lesson cannot go there at all: a break, outside the day, the wrong length for a swap). Every state but `"ok"` carries `why`, one sentence.
- **Clean** (spec): after the fix the clash check finds nothing new, no standard rule row has more Must warnings than before, the lesson is inside its class's lesson time, and the period counts are unchanged, except that an add or a delete brings a count towards what step 3 plans and never past it. "More than before" is by count per rule row and strength, so a lesson that already broke a rule where it stood is not held against a move that still breaks it.
- A fix is judged when it is offered and again when it is applied, by the same function (`fixes.judge`). `"no"` and `"na"` are refused on apply with the sentence; `"prefer"` applies.
- Block lessons move as one: every row of the id. A swap needs the same length and either the same set of classes on both lessons or no block lesson on either side.
- The uploaded file is never changed. A fix that no longer applies (its lesson id is gone after a new setup, its key has no step 5 row) is skipped and listed in `info()["fix_problems"]`; it never breaks the draft.
- Speed: the draft's model is cached in the process, keyed by the upload, the setup version and the fixes (the README already asks for one gunicorn worker); the draft no longer re-reads the setup workbook on every build. `fixes.slots` for one lesson answers in under 2 seconds on the solved secondary sample (904 lesson rows, 10 days of 26 periods).
- Step 8 stays committee-only (`@need("committee")` on every new route). Every server string drawn into HTML goes through `esc()`.
- `ttgen/` and `skill/school-timetable-generator/scripts/ttgen/` stay identical (after any change under `ttgen/`: `rm -rf skill/school-timetable-generator/scripts/ttgen && cp -R ttgen skill/school-timetable-generator/scripts/ttgen && find skill -name __pycache__ -exec rm -rf {} +`). `fixes.py`, `draft.py` and the page are the app's only. `SKILL_VERSION` does not change: the hand-over format is unchanged.
- No framework, no bundler, no new package. Wording: plain sentences, sentence case, no "please", no exclamation marks. Names in tests, samples and docs are made up; never commit `.claude/launch.json` or `data/`.
- Tests: `.venv/bin/python tests/test_fixes.py` (new; `--full` for the slow checks on a solved sample), `tests/test_verify.py`, `tests/test_choices.py`, `tests/test_rules.py`, `tests/test_sync.py`, `tests/smoke.py` (and `--full` once), `node tests/grid.test.js` (new), `node tests/draft.test.js`, the other Node suites, `node --check static/app.js`. Page checks against a scratch `DATA_DIR` on port 8003, never the repo's `data/`.
- Commit on branch `return-trip-stage-2` (from `main` at 648d96c) after each task; the first commit adds this plan. Do not push or open a pull request until the committee asks.

## Review Focus

1. The setup changes under a draft that has fixes (a head changes a teacher on step 5, a class is renamed) → the fixes that still apply are applied, the rest are listed as fix problems, nothing is a 500. Pinned in Tasks 1 and 3.
2. A block lesson (one id, several classes, groups and teachers) is moved or swapped → every row moves, and the slot is `"ok"` only when every class, teacher and room of every row is free. Pinned in Tasks 1 and 2.
3. Two committee browsers: a move posted from a stale grid (the lesson already moved, or the slot since taken) → judged against the draft as it is on the server, refused with a sentence, and the page reloads the grid. Pinned in Tasks 3 and 6.
4. Undo across kinds: add a lesson, change its room, move it, then undo three times → the draft is the uploaded file again, and each step in between is consistent. Pinned in Tasks 1 and 3.
5. The reduced rule check disagrees with the full one → it must not: for a sample of candidate moves on a solved timetable the two give the same state. Pinned in Task 2 (`--full`).

---

### Task 1: Fixes applied to the draft: the move kinds, the hook, the cache

**Files:**
- Create: `fixes.py`, `tests/test_fixes.py`
- Modify: `ttgen/export.py` (`model_from_files(..., edit=None)`), `draft.py` (`_build`, a cached model, `fix_problems`)
- Copy: `ttgen/` → the skill copy

**Interfaces:**
- Consumes: `ttgen.export.model_from_files`, `ENTIRE`; `ttgen.verify.planned_rows(spec)` (keys `("C", class, subject)` / `("G", code)`, values with `rows, teachers, periods, room_kind, classes, level, subject`), `verify._kstr`; `draft._build`, `store.setup_record()`.
- Produces in `ttgen.export`: `model_from_files(setup_path, timetable_path, spec=None, edit=None)`: `edit(lessons, spec, days) -> lessons` is called on the lessons read from the file, with the derived checked setup and the day names, just before `_model`; `None` changes nothing.
- Produces in `fixes.py`:
  - `KINDS = ("move", "swap", "teacher", "room", "add", "delete")`.
  - `what(x) -> str` (`"{subject} for {class}"` for an entire-class lesson, `"group {code}"` otherwise) and `when(days, d, p) -> str` (`"{day} period {p}"`).
  - `apply_one(lessons, fix, spec, days) -> str`: changes `lessons` (a list the caller owns) in place and returns the sentence; raises `ValueError(sentence)` when the fix cannot apply (no lesson with that id, the two lessons differ in length, no step 5 row for the key, a room or teacher name that is not on the setup). Sentences: `"Moved {what} from {when} to {when}."`; `"Swapped {what a} ({when}) with {what b} ({when})."`; `"{name of key} is now taught by {names}, not {names}."`; `"{what} on {when} is now in {room}, not {room}."`; `"Added {what} on {when} ({n} periods) in {room}."` (`"with no room"` when blank); `"Deleted {what} on {when}."`.
  - `apply(lessons, fixes, spec, days) -> dict(lessons, texts, problems, touched)`: a deep copy of `lessons` with every fix applied in order; a fix that raises is skipped and its sentence goes to `problems` as `"A fix could not be applied: {sentence}"`; `touched` is the set of lesson ids any applied fix changed or added.
  - `editor(fixes, out) -> callable`: the `edit` function for `model_from_files`; it stores `apply`'s `texts`, `problems` and `touched` into the dict `out`.
- Produces in `draft.py`:
  - `model_now(rec=None) -> (m, rec, fx)`: the model of the draft with its fixes applied against `rec` (default the current setup record), from a one-entry cache keyed by `(meta["uploaded_at"], rec["v"], json of fixes)`; `fx` is `dict(texts, problems, touched)`. The build passes `setup_path=None` when a spec is given and sets `m["setup"]["school"]["config_id"]` from `meta["config_id"]` (no re-read of the setup workbook).
  - `_build` uses `model_now`; `info()` gains `fixes=[dict(text, at, kind)]` (from meta) and `fix_problems=[sentence]`; `save()` clears the cache.

- [ ] **Step 1: Write the failing tests** (`tests/test_fixes.py`, the `t()` pattern; a `lessons_for(sp, placed)` helper like `model_for` in `tests/test_verify.py`)

```python
@t
def move_and_swap():
    sp, L = two_lessons()                      # ids 1 (day 0 period 2, n 2) and 2 (day 1 period 4, n 2) of one class
    out = fixes.apply(L, [dict(kind="move", id=1, d=2, p=0)], sp, DAYS)
    x = by_id(out["lessons"], 1); assert (x["d"], x["p"]) == (2, 0) and L[0]["d"] == 0          # the caller's list is untouched
    assert out["texts"] == [f"Moved {fixes.what(L[0])} from {DAYS[0]} period 2 to {DAYS[2]} period 0."] and out["touched"] == {1}
    out = fixes.apply(L, [dict(kind="swap", a=1, b=2)], sp, DAYS)
    assert [(x["d"], x["p"]) for x in sorted(out["lessons"], key=lambda x: x["id"])] == [(1, 4), (0, 2)] and out["touched"] == {1, 2}

@t
def a_block_lesson_moves_every_row():          # Review Focus 2
    sp, L = one_block()                        # id 7: three rows (three groups) of a band
    out = fixes.apply(L, [dict(kind="move", id=7, d=3, p=5)], sp, DAYS)
    assert {(x["d"], x["p"]) for x in out["lessons"] if x["id"] == 7} == {(3, 5)} and len([x for x in out["lessons"] if x["id"] == 7]) == 3

@t
def teacher_room_add_delete():
    ...  # teacher: every lesson of the key gets the new list; room: only the row (id, group); add: a new id = max + 1 with subject, classes, group, teachers, level, block from the step 5 row; delete: the lesson is gone; each with its sentence

@t
def a_fix_that_no_longer_applies_is_skipped():  # Review Focus 1
    sp, L = two_lessons()
    out = fixes.apply(L, [dict(kind="move", id=99, d=0, p=0), dict(kind="move", id=1, d=2, p=0)], sp, DAYS)
    assert len(out["problems"]) == 1 and out["problems"][0].startswith("A fix could not be applied: ") and by_id(out["lessons"], 1)["d"] == 2

@t
def add_then_room_then_move_then_undo():       # Review Focus 4: undo is dropping the last fix
    sp, L = two_lessons(); fx = [dict(kind="add", key=KEY, d=4, p=0, n=1, room=""), dict(kind="room", id=3, group="Entire Class", room=ROOM), dict(kind="move", id=3, d=4, p=1)]
    for k in (3, 2, 1, 0):
        out = fixes.apply(L, fx[:k], sp, DAYS); assert not out["problems"] and len(out["lessons"]) == len(L) + (1 if k else 0)

@t
def the_hook_edits_the_lessons_before_the_checks():
    ...  # a one-lesson workbook as tests/test_rules.py builds; model_from_files(setup, tt, edit=fixes.editor([move], out)) → m["lessons"][0] is at the new slot and m["checks"] were made on it
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/bin/python tests/test_fixes.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'fixes'`

- [ ] **Step 3: Implement `fixes.py` (the functions above), the `edit=` hook in both copies of `ttgen/export.py`, and `draft.model_now` with `_build` using it**

- [ ] **Step 4: Run the tests and the suites the change touches**

Run: `.venv/bin/python tests/test_fixes.py && .venv/bin/python tests/test_verify.py && .venv/bin/python tests/test_rules.py && .venv/bin/python tests/smoke.py`
Expected: `6 checks passed`, 40, 10, 44

- [ ] **Step 5: Copy `ttgen` to the skill, commit**

```bash
git add fixes.py draft.py ttgen tests/test_fixes.py skill/school-timetable-generator/scripts/ttgen
git commit -m "feat(fixes): the move kinds applied to the draft, with a cached model"
```

---

### Task 2: Judging a fix: the busy index, the reduced rule check, the options for a lesson

**Files:**
- Modify: `fixes.py`, `tests/test_fixes.py`

**Interfaces:**
- Consumes: Task 1's `apply_one`, `what`, `when`; `ttgen.verify.rules(m, spec) -> (warnings, not_checked)` (each warning has `key = "rule:{rule id or index}:{detail}"`, `strength`, `text`), `verify.planned_rows`, `verify.placed`; the model: `m["lessons"]`, `m["grid"][level][d]` and `m["cgrid"][class][d]` (code strings: `L` lesson time, `A` after-school slot, anything else not lesson time), `m["class_ix"]`, `m["room_ix"]`, `m["room_cap"]`, `m["students"]` (`cls`, `groups`), `m["teacher_ix"]` (`allowance`), `m["planned"]`.
- Produces in `fixes.py`:
  - `Busy(m)`: built once per request. `Busy.clash(rows, d, p, n, ignore=()) -> str | None`: the first reason these lesson rows cannot occupy `d, p .. p+n-1`, ignoring the lessons whose ids are in `ignore`: a teacher teaching then (`"{teacher} is teaching {what} then."`), a class in a whole-class lesson then or a whole-class lesson meeting any lesson of the class (`"{class} has {what} then."`), a group that shares a student with a group there (`"{n} students of {code} have {what} then."`), a room at its capacity (`"{room} is in use then."`; a blank room or `"TBC"` never clashes), or `None`. `Busy.lesson_time(rows, d, p, n) -> str | None`: `"That is not lesson time for {class}."` when any period is not `L` or `A` for any class of the rows or runs past the day.
  - `neighbours(m, ids) -> list`: the lessons that can interact with those ids under any rule: every lesson sharing a teacher, a class, the subject or the subject's department with one of them (the lessons themselves included).
  - `rule_counts(m, spec, lessons) -> collections.Counter`: `{(rule id, strength): count}` from `verify.rules` run on a shallow copy of `m` whose `lessons` is the given list.
  - `judge(m, spec, days, fix) -> dict(state, why, must, prefer)`: the fix applied to a copy of the affected lessons; `"na"` from `lesson_time` or a `ValueError` of `apply_one`; `"no"` from `Busy.clash` for any moved row (ignoring the moved ids), from a period count moving away from or past the plan (`"That would leave {name} with {n} periods; step 3 plans {want}."`), or from any rule row whose Must count rises between `rule_counts` before and after, both run on the same set of lesson ids: the `neighbours` of the changed lessons as they were and as they would be, joined (a new teacher's other lessons count as neighbours) (`must` = the new Must sentences); `"prefer"` when only Prefer counts rise or a teacher goes over the allowance (`"{teacher} would have {n} periods, {k} over the allowance."`); else `"ok"`. `why` is the first sentence of the deciding list.
  - `slots(m, spec, days, lesson_id) -> list[dict(d, p, state, why, swap, also)]`: every `(d, p)` of the week(s): an empty stretch of the lesson's classes → a `move`; a slot where exactly one other lesson starts with the same length → a `swap` (`swap` = its id, `also` = `["This also moves {what} to {when}."]` when its classes differ from the selected lesson's); anything else occupied → `"na"` (`"Another lesson is there."`). The lesson's own slot is left out.
  - `teacher_options(m, spec, days, key) -> list[dict(teachers, state, why)]`: every teacher of the setup whose `can_teach` names the key's subject, and the step 5 teachers of the key, each judged as a `teacher` fix; the current teachers are left out.
  - `room_options(m, spec, days, lesson_id, group) -> list[dict(room, state, why)]`: the rooms of the row's kind (the step 5 row's `room_kind`, else the current room's kind) and the class's home room, each judged as a `room` fix.
  - `add_slots(m, spec, days, key, n) -> list[dict(d, p, state, why)]` and `can_delete(m, spec, days, lesson_id, group=None) -> dict(state, why)`: an `add` / `delete` judged; `add` uses the class's home room when the row's kind is `classroom`, else the first free room of the kind, else `""`.
  - `short(m, spec) -> list[dict(key, name, have, want, n)]`: the keys timetabled below plan (`n` = the step 5 row's usual lesson length capped at what is missing), for the Add list.

- [ ] **Step 1: Write the failing tests**

```python
@t
def a_busy_teacher_class_room_or_student_is_a_clash():
    m = model_with(...)   # class A: Maths (T1, room R1) day 0 p 2-3; class B: Science (T1) day 1 p 2-3; group G1 and G2 of class A sharing a student
    b = fixes.Busy(m)
    assert "is teaching" in b.clash(rows_of(m, 1), 1, 2, 2, ignore={1}) and b.clash(rows_of(m, 1), 3, 2, 2, ignore={1}) is None
    assert "have" in b.clash(rows_of(m, G1), *slot_of(m, G2), ignore={G1}) and "is in use" in ...
    assert b.lesson_time(rows_of(m, 1), 0, RECESS, 1).startswith("That is not lesson time")

@t
def judge_states():
    ...  # a move into a free slot → "ok"; into the teacher's other lesson → "no" with the teacher sentence; into periods a Prefer "Not in periods" row covers → "prefer" naming the rule; into periods a Must row covers → "no"; a lesson already inside a Must row's periods moved to another period inside them → not "no" (the count does not rise); a teacher change that takes a teacher over the allowance → "prefer"

@t
def slots_for_a_lesson_and_a_block():          # Review Focus 2
    ...  # a single lesson: its own slot absent, a same-length lesson of the class offered as a swap with swap=id, a longer one "na"; a block of three classes: "ok" only where all three are free, "no" where one class or one of its teachers is busy

@t
def teacher_room_add_delete_options():
    ...  # teacher_options lists a can_teach teacher who is free in every period of the key as "ok" and a busy one as "no"; room_options offers rooms of the kind; add_slots for a key one period short offers free slots and refuses a second add past the plan; can_delete is "ok" for an extra lesson and "no" for a planned one at its count

if "--full" in sys.argv:
    @t
    def the_reduced_check_agrees_with_the_full_one_and_is_fast():   # Review Focus 5
        m, sp, days = solved_primary()          # solves the primary sample as tests/smoke.py --full does
        for lid in sample_ids(m, 6):
            t0 = time.time(); S = fixes.slots(m, sp, days, lid); assert time.time() - t0 < 2
            for s in random.Random(1).sample([s for s in S if s["state"] != "na"], 5):
                assert s["state"] == full_state(m, sp, days, lid, s), (lid, s)   # full_state: apply to all lessons, check_model + verify.rules on everything, the same counting rule
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/bin/python tests/test_fixes.py`
Expected: FAIL with `AttributeError: module 'fixes' has no attribute 'Busy'`

- [ ] **Step 3: Implement `Busy`, `neighbours`, `rule_counts`, `judge`, `slots`, the option functions and `short`**

The student test in `Busy`: two groups clash when some student of `m["students"]` lists both, and a group clashes with a whole-class lesson of a class one of its students is in; build `{group: set(groups sharing a student)}` once.

- [ ] **Step 4: Run the tests, fast and full**

Run: `.venv/bin/python tests/test_fixes.py && .venv/bin/python tests/test_fixes.py --full`
Expected: `10 checks passed`, then `11 checks passed`

- [ ] **Step 5: Commit**

```bash
git add fixes.py tests/test_fixes.py
git commit -m "feat(fixes): a fix judged by a busy index and the rules on its neighbours"
```

---

### Task 3: The routes: the grid, the options, making a fix, undo, the download, the published record

**Files:**
- Modify: `draft.py`, `app.py`, `store.py` (`publish(..., edit=None)`), `ttgen/export.py` (`write_excel`: the Read me section), `tests/smoke.py`
- Copy: `ttgen/` → the skill copy

**Interfaces:**
- Consumes: Tasks 1 and 2 (`fixes.apply`, `judge`, `slots`, `teacher_options`, `room_options`, `add_slots`, `can_delete`, `short`), `draft.model_now`, `draft._finish`, `draft._lock`, `ttgen.database.write_db(m, path)`.
- Produces in `draft.py`:
  - `grid(view, name) -> dict(view, name, days, NP, times, codes, lessons, classes, teachers, short)`: `view` ∈ `"class" | "teacher"`; `codes` = one code string per day for the class (its `cgrid`, else its level's `grid`) or, for a teacher, `"L"` where any level has lesson time; `lessons` = the rows of the view as `dict(id, group, subject, classes, teachers, room, d, p, n, block, what)`; `classes` and `teachers` = every name, for the pickers; `short` = `fixes.short` filtered to the class (empty for a teacher). `ValueError("There is no class or teacher of that name on the timetable.")` for an unknown name.
  - `options(lesson_id=None, group=None, add=None, n=None) -> dict`: for a lesson `dict(slots, teachers, rooms, delete, key)`; for `add` `dict(slots)`.
  - `fix(move) -> info()`: under `_lock`: `judge` against `model_now()`; `"no"`/`"na"` → `ValueError(why)`; else the fix (with `at` and its `text`) is appended to `meta.json`'s `fixes`, and `info()` is returned.
  - `undo() -> info()`: drops the last fix; `ValueError("There is nothing to undo.")` when there is none.
  - `database(path) -> None`: `write_db(model_now()[0], path)`.
  - `publish()` passes `edit=fixes.editor(...)` and `extra["fixes"] = [texts]`, and afterwards writes `published_fixes = len(fixes)` into `meta.json`. The upload route's "fixes that were never published" check (stage 1) becomes `len(fixes) > meta.get("published_fixes", 0)`, so a draft whose fixes are all published is replaced without the question.
- Produces in `store.publish(setup_xlsx, timetable_path, run_id=None, source=None, log=print, spec=None, extra=None, edit=None)`: `edit` goes to `model_from_files`; `m["fixes"] = (extra or {}).get("fixes") or []` is set before `export_all`.
- Produces in `ttgen.export.write_excel`: when `m.get("fixes")`, the Read me sheet gets a section headed `"Fixes made in the app"` with one line per sentence, after Checks.
- Produces in `app.py` (all `@need("committee")`):
  - `GET /api/draft/grid?view=&name=` → `draft.grid`; `GET /api/draft/options?id=&group=` or `?add=&n=` → `draft.options`; `POST /api/draft/fix` (JSON: one fix without `at`/`text`) → `draft.fix`; `POST /api/draft/undo`; `GET /api/draft/download` → the database as `"{school} {timetable} - draft.sqlite"`. A `ValueError` is a 400 with `{"error": sentence}`; no draft is a 404; every other fault goes through `_checked`'s handling (a sentence, not a 500).
- `tests/smoke.py` additions (fast, on the one-lesson workbook the draft tests already build, extended to three lessons of two classes).

- [ ] **Step 1: Write the failing server tests**

```python
def test_the_grid_of_a_class_and_a_teacher():
    j = c.get("/api/draft/grid?view=class&name=" + CLS).get_json(); assert j["lessons"] and len(j["codes"]) == len(j["days"]) and CLS in j["classes"]
    assert c.get("/api/draft/grid?view=class&name=Nobody").status_code == 400

def test_a_fix_moves_the_lesson_and_undo_brings_it_back():
    lid = ...; s = next(s for s in c.get(f"/api/draft/options?id={lid}").get_json()["slots"] if s["state"] == "ok" and not s["swap"])
    j = c.post("/api/draft/fix", json=dict(kind="move", id=lid, d=s["d"], p=s["p"])).get_json(); assert len(j["fixes"]) == 1 and j["fixes"][0]["text"].startswith("Moved ")
    g = c.get("/api/draft/grid?view=class&name=" + CLS).get_json(); assert (s["d"], s["p"]) in {(x["d"], x["p"]) for x in g["lessons"] if x["id"] == lid}
    assert c.get("/api/status").get_json()["draft"]["open"] == j["open"]
    j = c.post("/api/draft/undo").get_json(); assert j["fixes"] == [] and c.post("/api/draft/undo").status_code == 400

def test_a_fix_into_a_clash_is_refused_with_the_sentence():   # Review Focus 3: judged on the server's draft, whatever the page showed
    r = c.post("/api/draft/fix", json=dict(kind="move", id=lid, d=D2, p=P2)); assert r.status_code == 400 and "is teaching" in r.get_json()["error"]

def test_fixes_survive_a_setup_change_or_say_so():            # Review Focus 1
    ... make a fix; rename the lesson's class through /api/setup/changes; GET /api/draft is 200 and fix_problems names the fix or the fix still shows

def test_the_draft_downloads_with_its_fixes():
    ... make a fix; GET /api/draft/download; read_db on the bytes: the lesson is at the new slot

# --full: publish after a fix → /api/status published.fixes == [the sentence]; the Excel's Read me sheet holds "Fixes made in the app" and the sentence
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/bin/python tests/smoke.py`
Expected: FAIL: `404` from `/api/draft/grid`

- [ ] **Step 3: Implement `draft.grid`, `options`, `fix`, `undo`, `database`, the routes, the publish pass-through and the Read me section**

- [ ] **Step 4: Run the server tests, fast and full, and the suites `ttgen` touches**

Run: `.venv/bin/python tests/smoke.py && .venv/bin/python tests/smoke.py --full && .venv/bin/python tests/test_rules.py && .venv/bin/python tests/test_choices.py`
Expected: all pass (smoke grows by 5; `--full` checks the published fixes)

- [ ] **Step 5: Copy `ttgen` to the skill, commit**

```bash
git add draft.py app.py store.py ttgen tests/smoke.py skill/school-timetable-generator/scripts/ttgen
git commit -m "feat(draft): the grid, the options, fixes with undo, the download and the published list"
```

---

### Task 4: Typed rules after a fix: "check again"

**Files:**
- Modify: `ttgen/verify.py` (`typed_again`), `draft.py` (the warning, the `"met"` answer), `static/draft.js`, `tests/test_verify.py`, `tests/smoke.py`, `tests/draft.test.js`
- Copy: `ttgen/` → the skill copy

**Interfaces:**
- Consumes: `verify.in_scope(m, spec, r)` (a predicate over a lesson for a rule row's scope and subject), `typed_rules(spec)`, Task 1's `touched` ids from `draft.model_now()[2]`.
- Produces in `ttgen.verify`: `typed_again(m, spec, touched) -> list[dict]`: for each typed rule `(n, i, r)` whose scope matches any lesson of `m["lessons"]` with an id in `touched` (School scope always matches when `touched` is not empty) and whose report line is `"Met"` or `"Partly"`: a warning with key `f"typed:{n}:again"`, kind `"typed"`, text `"T{n} was reported {result lower-case}, but lessons it is about were changed in the app. Check it again: {sentence}."`, strength from the rule row.
- Produces in `draft.py`: `_build` appends `typed_again` to the warnings (after the typed ones, before the choices); `ANSWERS` gains `"met"`; `decide(key, "met")` is accepted only for a key ending `":again"` and records `dict(answer="met", at)`; a warning with answer `"met"` is not open. The published `decisions` map carries it.
- Produces in `static/draft.js`: `isOpen` treats `"met"` as settled; `answerText` → `"Checked: still met"`; `counts` gains `met`.

- [ ] **Step 1: Write the failing tests** (`tests/test_verify.py`: a typed Level rule and a touched lesson of that level → one `typed:1:again`; a touched lesson of another level → none; a typed School rule → one; no touched ids → none. `tests/smoke.py`: after a fix on a setup with a typed School rule reported Met, the draft lists the warning as open; `decide` `"met"` settles it; `"met"` on a deployment key is a 400. `tests/draft.test.js`: `isOpen`, `answerText`, `counts` with `"met"`.)

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/bin/python tests/test_verify.py && node tests/draft.test.js`
Expected: FAIL with `AttributeError: ... 'typed_again'`

- [ ] **Step 3: Implement `typed_again`, the draft changes and the `draft.js` changes**

- [ ] **Step 4: Run the tests**

Run: `.venv/bin/python tests/test_verify.py && .venv/bin/python tests/smoke.py && node tests/draft.test.js && .venv/bin/python tests/test_rules.py`
Expected: all pass

- [ ] **Step 5: Copy `ttgen` to the skill, commit**

```bash
git add ttgen draft.py static/draft.js tests skill/school-timetable-generator/scripts/ttgen
git commit -m "feat(draft): a typed rule is checked again after a fix touches its lessons"
```

---

### Task 5: `static/grid.js`: the week as a table

**Files:**
- Create: `static/grid.js`, `tests/grid.test.js`
- Modify: `static/index.html` (script tag before `app.js`)

**Interfaces:**
- Consumes: the `draft.grid` payload (`days, NP, times, codes, lessons`) and the `options` payload (`slots` with `d, p, state, why, swap, also`).
- Produces (global `Grid`, pure functions, loadable in Node):
  - `Grid.weeks(days) -> [{name, days: [{i, label}]}]`: `"Odd Mon"` … → two weeks named `"Odd"` and `"Even"` with labels `"Mon"` …; one-week schools → one week named `""`.
  - `Grid.table(payload, week) -> [[cell]]`: one row per period, one cell per day of the week: `{d, p, code, lessons: [rows starting here], rowspan, covered}`; `rowspan` = the longest lesson starting there, `covered` true for a cell under an earlier cell's span; periods that are not lesson time for the view carry `code` and no lessons.
  - `Grid.lesson(payload, id, group) -> row | null`; `Grid.same(a, b)` (same id and group).
  - `Grid.slotAt(slots, d, p) -> slot | null`; `Grid.stateClass(state) -> "ok" | "prefer" | "no" | "na" | ""`; `Grid.slotText(slot, days) -> str` (`"Move to {day} period {p}"` / `"Swap with the lesson on {day} period {p}"`, then `" — "` + `why` when there is one); `Grid.sorted(slots) -> slots` (ok first, then prefer, then no; `na` left out; within a state by day then period).

- [ ] **Step 1: Write the failing Node tests** (weeks for one-week and two-week day names; a table where a two-period lesson spans two rows and the cell below is covered; parallel group rows of one id in one cell; a break period carrying its code; `slotAt`, `stateClass`, `slotText` with and without `why`; `sorted` dropping `na` and ordering the rest)

- [ ] **Step 2: Run them to verify they fail**

Run: `node tests/grid.test.js`
Expected: FAIL: cannot find `static/grid.js`

- [ ] **Step 3: Implement `static/grid.js` and add the script tag**

- [ ] **Step 4: Run the tests**

Run: `node tests/grid.test.js && node --check static/app.js`
Expected: `7 cases passed`; no syntax error

- [ ] **Step 5: Commit**

```bash
git add static/grid.js static/index.html tests/grid.test.js
git commit -m "feat(grid): the week laid out as a table, and the slot wording"
```

---

### Task 6: The Fix card on step 8

**Files:**
- Modify: `static/app.js` (`draftHTML`, a `fixHTML` card, the click handler), `static/style.css`, `README.md`

**Interfaces:**
- Consumes: Tasks 3 to 5 (the routes, `Draft`, `Grid`), `S.draft`, `post()`, `esc()`, `toast()`.
- Produces in `static/app.js`:
  - State `S.fix = { view: "class" | "teacher", name, week, sel: {id, group} | null, grid, options, adding: key | null }`, kept across redraws of the draft, cleared by a new upload.
  - In `draftHTML`: the sentence `"Fixing a lesson in the app comes in the next stage…"` goes; each warning with a `where` gets a **Fix the timetable** button (`data-fix="{cls}|{day index}|{period}"`) that opens the Fix card on that class and week with the lesson there selected; below the warnings a **Fixes** list (`j.fixes`, newest last, with their times), an **Undo the last fix** button (`id="fxUndo"`, shown when there is one), any `fix_problems` as issues, and a link **Download the draft (.sqlite)** to `/api/draft/download`.
  - `fixHTML()`: the Fix card under the warnings: a class picker and a teacher picker (`data-fxview`), week tabs when there are two weeks, the table from `Grid.table` (day headings, a period column with the clock time, lessons as buttons `data-fxsel="{id}|{group}"` showing subject, group and teacher shorts, breaks greyed with their code's meaning), and a side panel. With a lesson selected: the lesson in words, **Possible moves** (`Grid.sorted(options.slots)` as buttons `data-fxgo="{d}|{p}"` with `Grid.slotText`), **Change the teacher** (`options.teachers`, `data-fxteacher`), **Change the room** (`options.rooms`, `data-fxroom`), and **Delete this lesson** when `options.delete.state` is not `"no"`; every option shows its state as a coloured dot and its `why`. With nothing selected: the class's **Missing periods** (`grid.short`) each with **Add a lesson** (`data-fxadd="{key}"`), which colours the grid with `options(add=…)` and makes a click on a slot post the `add`.
  - Colouring: with a selection the table's cells get `Grid.stateClass(Grid.slotAt(options.slots, d, p).state)` and a `title` of the `why`; a click on an `ok` or `prefer` cell posts the fix (a `swap` whose `also` is not empty asks first: the sentences, then `confirm`); `no` and `na` cells toast the `why` and do nothing.
  - After every fix or undo: `S.draft` = the answer, the draft list redrawn, the grid and the options fetched again (the selection kept when the lesson still exists). A 400 from `/api/draft/fix` toasts the sentence and fetches the grid again (Review Focus 3).
  - `paintPublished`: the fixes of the published timetable as a `<details>` list (`"{n} fixes made in the app"`), in place of the count alone.
- `style.css`: the grid table (`table.fxgrid`, cells `ok` green, `prefer` amber, `no` red, `na` grey, the selected lesson outlined), the side panel, the state dots. Light theme only; the grid scrolls sideways inside its card on a narrow screen.
- `README.md`: the Publish item gains the Fix card (pick a class or a teacher, select a lesson, the colours, the kinds of fix, undo, what "clean" means in one sentence, the download) and the published list of fixes.

- [ ] **Step 1: Draw the Fix card and wire the clicks**

Run: `node --check static/app.js && node tests/grid.test.js && node tests/draft.test.js`
Expected: no syntax error; both suites pass

- [ ] **Step 2: Check the page in the browser preview against a scratch `DATA_DIR`**

Start the scratch server (port 8003, the README's example codes, a fresh temporary `DATA_DIR`; a temporary `timetable-scratch` entry in the launch configuration, removed afterwards). Sign in as the committee, open the primary sample into the school's setup, download the workbook, solve it with `python -m ttgen solve` into the scratchpad (a short `--time`), upload the timetable on step 8. Expected: a warning's **Fix the timetable** opens the grid on its class with the lesson selected; the slots colour within two seconds; a green slot moves the lesson and the Fixes list gains the sentence; a red slot does nothing but say why; a swap of two lessons works; **Change the teacher** offers a free teacher and the deployment warning for it appears or goes accordingly; **Change the room** works; **Delete this lesson** is offered only for an extra lesson; a class with missing periods offers **Add a lesson**; **Undo the last fix** steps back; a reload keeps the fixes; publishing shows the fixes under Published now; the downloaded draft opens with **Make printouts**. Screenshots of the grid with a selection, and of the Fixes list, for the report. Say plainly what was not exercised.

- [ ] **Step 3: Run every suite, commit**

Run: `.venv/bin/python tests/test_fixes.py && .venv/bin/python tests/test_verify.py && .venv/bin/python tests/test_choices.py && .venv/bin/python tests/test_rules.py && .venv/bin/python tests/test_sync.py && .venv/bin/python tests/smoke.py && node tests/grid.test.js && node tests/draft.test.js && node tests/choices.test.js && node tests/groups.test.js && node tests/map.test.js && node tests/people.test.js && node tests/sync.test.js && node --check static/app.js`
Expected: every suite passes

```bash
git add static README.md
git commit -m "feat(publish): the Fix card: a week grid with coloured slots, fixes and undo"
```

---

## Not in this plan

- The helper's suggestions for a warning, chains of two moves and their ranking (stage 3); the typed request (stage 4).
- Showing the second class's own grid before a cross-class swap is confirmed: this plan names the other lesson's move in a sentence and asks first. The spec asks for the grid; it comes with the helper's preview in stage 3.
- Splitting or joining lessons, and swaps of different lengths (the spec's non-goals).
- Heads seeing the draft (project 3).

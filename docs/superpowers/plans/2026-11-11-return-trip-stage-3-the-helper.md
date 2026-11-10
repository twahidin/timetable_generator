# Return trip stage 3: the helper — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When the committee lead opens the Fix card from a warning, a helper offers up to three ways to settle that warning, each already checked, each saying what moves and what it disturbs, with a preview that shows every class it touches before it is applied; a way to settle may be one fix or two made together.

**Architecture:** A new app module `helper.py` turns one warning into candidate fixes (from the option functions `fixes.py` already has), keeps the ones that make the warning go away without creating another, adds two-fix chains when single fixes are not enough, and ranks them. `draft.py` gains `suggest`, a batch `fix_many` that judges a list in order and keeps all or none (undone together), and `preview`, which returns the week of every class a list of fixes touches, as it would be. The page draws "Ways to settle this" in the Fix card's side panel and a "Before you apply" panel with the other classes' weeks, which also replaces the plain confirm stage 2 used for a swap that moves another class's lesson.

**Tech Stack:** Python 3.11, Flask, vanilla JavaScript with no build step. Python tests are plain asserts (`tests/test_fixes.py` pattern); Node tests like `tests/grid.test.js`; server tests in `tests/smoke.py`.

**Spec:** `docs/superpowers/specs/2026-11-10-return-trip-design.md`, part 4 Fix: "The helper" (two or three ways to settle the warning, each a short sentence saying what moves and what it disturbs, with Apply; when nothing settles it cleanly, say so and show the least bad moves with what each breaks; ranked fewest lessons moved first, then nothing amber, then teacher loads kept level; up to two moves) and "Moves the app knows how to make" (a swap between lessons of different classes: the second class's grid is shown before the lead confirms); "Suggested order of building" item 3. **Not** in this plan: typing a request in words (stage 4).

## Global Constraints

- A **suggestion** is `dict(fixes, text, disturbs, state, moved)`: `fixes` a list of one or two fixes in the shapes stage 2 posts (`move`, `swap`, `teacher`, `room`, `add`, `delete`, without `at`/`text`); `text` one sentence saying what to do; `disturbs` a list of sentences saying what else changes or gives (`["Nothing else moves."]` when nothing does); `state` `"ok"` or `"prefer"`; `moved` the number of lessons whose slot, teacher or room changes.
- A suggestion is offered only if every one of its fixes is `"ok"` or `"prefer"` under `fixes.judge`, judged in order, each on the timetable as the earlier ones leave it; and only if it **settles** the warning: with the fixes applied, the warning is gone (for a warning about a lesson: no warning remains for that rule row and that lesson; otherwise: its key is gone) and no new difference from step 5 has appeared (the number of deployment warnings does not rise).
- At most three suggestions, ranked: fewer fixes first, then fewer lessons moved, then `"ok"` before `"prefer"`, then (for a teacher change) the lower resulting load against the allowance, then the same day before another day, then the earlier day and period.
- When nothing settles the warning, `suggest` returns no suggestions, a sentence saying so, and up to three **blocked** entries `dict(text, why)`: the nearest fixes that would settle it and what each breaks. Blocked entries cannot be applied.
- Warnings the helper has nothing for (a rule in words, a choice warning, a clash that names no teacher or class) get a sentence, not an error: `"The app has no suggestion for this one. Select a lesson on the grid to see where it can go."`
- A batch of fixes is all or nothing: `fix_many` judges each in order on the state the earlier ones leave and writes them only if all pass; each fix of a batch carries the same `batch` id, and Undo takes a whole batch back at once.
- A **preview** changes nothing. It returns, for every class any fix of the list touches (before or after), that class's week as it would be, with each changed lesson marked `"moved"`, `"changed"` (teacher or room) or `"new"`, and the deleted lessons listed.
- Speed: `suggest` for one warning answers in under 2 seconds on the solved secondary sample.
- Everything stage 2 fixed stays as it is: `fixes.judge` is the only judge, the uploaded file is never changed, the draft's model is cached and never mutated, every route is committee-only, every server string on the page goes through `esc()`.
- `helper.py`, `draft.py` and the page are the app's only; nothing under `ttgen/` changes in this stage (if a task finds it must, the skill copy is refreshed the usual way and `tests/test_rules.py` stays green). `SKILL_VERSION` does not change.
- No framework, no bundler, no new package. Wording: plain sentences, sentence case, no "please", no exclamation marks. Names in tests, samples and docs are made up; never commit `.claude/launch.json` or `data/`.
- Tests: `.venv/bin/python tests/test_helper.py` (new; `--full` for the slow checks on a solved sample), `tests/test_fixes.py`, `tests/test_verify.py`, `tests/test_choices.py`, `tests/test_rules.py`, `tests/test_sync.py`, `tests/smoke.py` (and `--full` once), `node tests/grid.test.js`, `node tests/draft.test.js`, the other Node suites, `node --check static/app.js`. Page checks against a scratch `DATA_DIR` on port 8003, never the repo's `data/`.
- Commit on branch `return-trip-stage-3` (from `main` at 35e80ac) after each task; the first commit adds this plan. Do not push or open a pull request until the committee asks.

## Review Focus

1. A suggestion that settles its warning by creating another: a teacher who is not on step 5 for that lesson, a room of the wrong kind, a lesson moved into a new Prefer break that is not said → never offered, or said in `disturbs`. Pinned in Task 1.
2. The timetable changes between the suggestion and Apply (another fix, a setup change) → the batch is judged on the draft as it is, refused with a sentence when it no longer passes, and nothing is half-applied. Pinned in Task 3.
3. A two-fix suggestion is undone as one, and after the undo the draft is exactly as before it. Pinned in Task 3.
4. A warning with nothing to suggest (a rule in words, a choice, a clash with no name, a warning whose lesson has since been deleted) → the sentence, an empty list, no error. Pinned in Tasks 1 and 3.
5. A block lesson (several classes) in a suggestion → the preview shows every one of its classes, and the suggestion counts its move once. Pinned in Tasks 2 and 3.

---

### Task 1: `helper.py`: single-fix suggestions for a warning

**Files:**
- Create: `helper.py`, `tests/test_helper.py`
- Modify: `fixes.py` (one new method, `Busy.blocker`)

**Interfaces:**
- Consumes from `fixes.py`: `judge(m, spec, days, fix, ctx=None) -> dict(state, why, must, prefer)`, `slots(m, spec, days, lesson_id)`, `teacher_options(m, spec, days, key)`, `room_options(m, spec, days, lesson_id, group)`, `add_slots(m, spec, days, key, n)`, `add_room`, `can_delete`, `short(m, spec)`, `apply(lessons, fixes, spec, days) -> dict(lessons, texts, problems, touched, was)`, `what(x)`, `when(days, d, p)`, `_rows`, `_key`, `_row_key`, `_subject(w)`, `Busy`. From `ttgen.verify`: `deployment(m, spec)`, `rules(m, spec)`, `planned_rows`, `_kstr`, `_name`. A warning is `dict(key, kind, text, strength, group, where, sides, ops)`; `where` may hold `cls`, `day`, `period`, `id`, `row`, or `teacher`.
- Produces in `fixes.py`: `Busy.blocker(rows, d, p, n, ignore=()) -> int | None`: the id of the lesson behind the reason `Busy.clash` gives for the same arguments (None when there is no clash or the reason is a room).
- Produces in `helper.py`:
  - `NOTHING = "The app has no suggestion for this one. Select a lesson on the grid to see where it can go."`
  - `say(m, spec, days, fix) -> str`: the fix as an instruction: `"Move {what} to {when}."`; `"Swap {what a} with {what b} ({when of b})."`; `"Give {name of key} to {names}."`; `"Put {what} in {room}."`; `"Add {what} on {when} ({n} period[s])."`; `"Delete {what} on {when}."`
  - `chain(m, spec, days, fixes) -> dict(state, why, steps, lessons, texts, touched, was)`: each fix judged in order on the timetable the earlier ones leave (`dict(m, lessons=...)` built with `fixes.apply`); `state` is the worst of the steps (`"na"`/`"no"` stop the chain, with that step's `why`); `steps` the judge results; `lessons` the lessons after all of them; `texts`, `touched` and `was` as `fixes.apply` gives them for the whole list (the sentence of each fix, the ids changed or added, the rows as they were).
  - `involved(m, warning) -> list[int]`: the lesson ids a warning is about: `where.id` when it has one; for a deployment key the lessons of that key; for a day-level rule key (`rule:{rid}:{who}|{d}`) the lessons of that teacher or class on that day; for a clash naming a teacher or class the lessons of theirs that overlap another of theirs; else `[]`.
  - `settles(m, spec, days, warning, lessons) -> bool`: with `lessons` in place of the timetable's, is the warning gone and has the count of deployment warnings not risen (Global Constraints)? Only the checks the warning needs are run (the one rule row for a rule warning, `verify.deployment` for a deployment one, the teacher's or class's overlaps for a clash).
  - `candidates(m, spec, days, warning) -> list[list[fix]]`: single fixes worth trying, by kind: a deployment teachers difference → the teacher fix to step 5's teachers; periods short or a missing row → an add at each `add_slots` slot that is not `"no"`/`"na"` (length from `fixes.short`); periods over or an extra lesson → a delete of each lesson of the key; a venue difference → each `room_options` room for the row in `where`; a rule or clash → for each involved lesson (at most 8) every `slots` entry that is not `"no"`/`"na"` as a move or swap, and for a rule or clash about a teacher each `teacher_options` entry for the lesson's key.
  - `disturbs(m, spec, days, fixes, steps) -> list[str]`: `"{what} moves to {when}."` for every lesson a swap moves besides the one named in the text; every `prefer` sentence of the steps; for a teacher fix `"{old} drops to {n} periods, {new} rises to {k}."`; `["Nothing else moves."]` when the list would be empty.
  - `rank(m, spec, days, s) -> tuple`: the sort key of Global Constraints.
  - `suggest(m, spec, days, warning, limit=3) -> dict(suggestions, none, blocked)`: `candidates` → `chain` → keep `"ok"`/`"prefer"` that `settles` → sort by `rank` → the first `limit`, never two with the same `fixes`. `none` is `NOTHING` when there were no candidates at all, `"Nothing settles this without breaking a rule or a clash."` when candidates existed but none passed, else `None`. `blocked` (only when `suggestions` is empty) = up to three candidates that would settle the warning if they were allowed, as `dict(text=say(...), why=<the refusing step's why>)`.

- [ ] **Step 1: Write the failing tests** (`tests/test_helper.py`, the `t()` pattern; build models with the helpers of `tests/test_fixes.py`, imported or copied)

```python
@t
def a_wrong_teacher_is_settled_by_giving_the_lesson_back():
    m, sp, days = model_with_wrong_teacher()        # step 5 says T_RIGHT for Maths of class A; the timetable has T_WRONG; T_RIGHT is free in every period of it
    w = next(w for w in verify.deployment(m, sp) if w["key"].endswith(":teachers"))
    out = helper.suggest(m, sp, days, w); s = out["suggestions"][0]
    assert s["fixes"] == [dict(kind="teacher", key=KEY, teachers=[T_RIGHT])] and s["state"] == "ok" and s["moved"] >= 1
    assert s["text"] == f"Give Maths for {CLS} to {T_RIGHT}." and out["none"] is None and out["blocked"] == []

@t
def a_lesson_breaking_a_rule_gets_moves_that_stop_breaking_it():
    ...  # a Must "Not in periods 0-1" row and a lesson at period 0: every suggestion is a move or swap of that lesson to a slot outside the periods, at most 3, ranked same day first; none of them leaves a warning for that rule row and lesson

@t
def a_suggestion_never_trades_one_warning_for_another():       # Review Focus 1
    ...  # the only free teacher who can teach the subject is not step 5's: a teacher clash on T_RIGHT is not "settled" by handing the lesson to that teacher (a new deployment difference), so that fix is not offered; a move that lands in a Prefer window is offered with state "prefer" and the rule's sentence in disturbs

@t
def missing_extra_and_venue():
    ...  # a key one period short → adds at open slots, each "Add ... (1 period)."; an extra lesson → "Delete ..."; a lesson in a room of the wrong kind → "Put ... in {room}." for a free room of step 3's kind

@t
def nothing_to_suggest_is_a_sentence():                         # Review Focus 4
    for w in (dict(key="typed:1:none", kind="typed", text="x", where=None), dict(key="choice:x", kind="choice", text="x", where=None),
              dict(key="clash:Room over capacity: R1 on Mon period 2.", kind="clash", text="x", where=None), dict(key="rule:0:1A|Maths|0|0", kind="rule", text="x", where=dict(cls="1A", day="Mon", period=0, id=999, row="Entire Class"))):
        out = helper.suggest(m, sp, days, w); assert out == dict(suggestions=[], none=helper.NOTHING, blocked=[])

@t
def blocked_when_nothing_passes():
    ...  # a lesson whose every other slot clashes: suggestions == [], none == "Nothing settles this without breaking a rule or a clash.", blocked has up to 3 entries each with a text and the clash sentence as why

@t
def blocker_names_the_lesson_in_the_way():
    ...  # Busy.blocker returns the id of the teacher's other lesson for a slot where Busy.clash says "{teacher} is teaching ... then.", and None for a free slot
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/bin/python tests/test_helper.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'helper'`

- [ ] **Step 3: Implement `Busy.blocker` and `helper.py` (the functions above)**

`helper.py` must not import `draft` or `store`. Share one `fixes._ctx` per request where the option functions allow it.

- [ ] **Step 4: Run the tests and the suites the change touches**

Run: `.venv/bin/python tests/test_helper.py && .venv/bin/python tests/test_fixes.py && .venv/bin/python tests/test_verify.py`
Expected: `7 checks passed`, 20, 45

- [ ] **Step 5: Commit**

```bash
git add helper.py fixes.py tests/test_helper.py
git commit -m "feat(helper): ways to settle a warning with one fix, checked and ranked"
```

---

### Task 2: Two fixes together, and the speed

**Files:**
- Modify: `helper.py`, `tests/test_helper.py`

**Interfaces:**
- Consumes: Task 1's `chain`, `settles`, `candidates`, `rank`, `say`, `disturbs`; `fixes.Busy.blocker`; `fixes.slots`.
- Produces in `helper.py`:
  - `pairs(m, spec, days, warning, have) -> list[list[fix]]`: tried only when `have` (the single-fix suggestions found) is fewer than three. For each involved lesson L and each of its slots S that is `"no"` because exactly one other lesson B is in the way (`Busy.blocker`): for up to three of B's own `"ok"` moves (not swaps, not to S, nearest day first), the pair `[move B, move L to S]`. For a deployment teachers difference whose teacher fix is `"no"` because step 5's teacher is teaching another lesson B then: for up to three of B's `"ok"` moves, the pair `[move B, the teacher fix]`. At most 40 pairs are judged per warning.
  - `suggest` adds the pairs that pass `chain` and `settles` after the singles, ranks all together, and keeps three; a pair's `text` is the two instructions joined by `" Then "` (the second starting lower-case is not required), its `moved` counts each lesson id once (a block lesson once, however many rows).

- [ ] **Step 1: Write the failing tests**

```python
@t
def a_pair_frees_the_slot_first():
    ...  # class A's lesson L must leave period 0 (a Must rule); every open slot is taken by lesson B of the same teacher, which has a free slot elsewhere: one suggestion with fixes [move B, move L], text "Move ... Then move ...", moved == 2, state "ok"; chain() on it passes; after apply the rule warning for L is gone

@t
def singles_come_before_pairs_and_three_at_most():
    ...  # three clean single moves exist: no pair is offered; with one single and several pairs: the single is first, the list has three entries

@t
def a_teacher_handback_after_moving_the_lesson_in_the_way():
    ...  # step 5's teacher is teaching lesson B in one period of the key: the suggestion is [move B to its free slot, teacher fix], and disturbs names B's move

@t
def a_block_lesson_counts_once():                               # Review Focus 5
    ...  # a pair that moves a three-row block lesson and one other lesson has moved == 2

if "--full" in sys.argv:
    @t
    def every_warning_of_a_spoiled_timetable_is_answered_quickly_and_truly():
        m, sp, days = spoiled_primary()      # the solved primary sample with five lessons moved into each other, one teacher swapped, one lesson deleted, one duplicated
        for w in verify.warnings(m)["warnings"]:
            t0 = time.time(); out = helper.suggest(m, sp, days, w); assert time.time() - t0 < 2, (w["key"], time.time() - t0)
            for s in out["suggestions"]:
                L = fixes.apply(m["lessons"], s["fixes"], sp, days); assert not L["problems"]
                assert w["key"] not in {x["key"] for x in verify.warnings(export._model(sp, days, L["lessons"], recess=...))["warnings"]}, (w["key"], s["text"])   # the full check agrees the warning is gone
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/bin/python tests/test_helper.py`
Expected: FAIL with `AttributeError: module 'helper' has no attribute 'pairs'`

- [ ] **Step 3: Implement `pairs` and its place in `suggest`**

- [ ] **Step 4: Run the tests, fast and full, and time `suggest` by hand on the secondary sample**

Run: `.venv/bin/python tests/test_helper.py && .venv/bin/python tests/test_helper.py --full`
Expected: `11 checks passed`, then `12 checks passed`. For the hand timing, spoil the solved secondary timetable the same way (the solved files are in the session scratchpad; the dispatch names them) and record the slowest `suggest` in the report: under 2 seconds.

- [ ] **Step 5: Commit**

```bash
git add helper.py tests/test_helper.py
git commit -m "feat(helper): two fixes together when one is not enough"
```

---

### Task 3: The routes: suggest, a batch of fixes undone together, the preview

**Files:**
- Modify: `draft.py`, `app.py`, `tests/smoke.py`

**Interfaces:**
- Consumes: Tasks 1 and 2 (`helper.suggest`, `helper.chain`, `helper.say`); `draft._now()`, `_lock`, `_whole`, `_length`, `fix`, `undo`, `grid`, `_build`, `info`; `fixes.apply`, `fixes.add_room`.
- Produces in `draft.py`:
  - `suggest(key) -> dict(suggestions, none, blocked)`: the warning with that key in the draft as it is now (from `_build()`); a key that is no longer on the list → `ValueError("That warning is no longer on the list.")`.
  - `fix_many(moves) -> info()`: `moves` a list of one or two fixes as the page posts them; each goes through `_whole` (and an add without a room gets `add_room`'s on the state it is judged on); under `_lock`: `helper.chain` on the draft as it is now; `"no"`/`"na"` → `ValueError(why)` and nothing is written; else every fix is appended with its `at`, its `text` (the sentence `fixes.apply` gives for it in the chain) and a shared `batch` (a short random id). A list that is empty or longer than two → `ValueError("Send one or two fixes.")`.
  - `undo()` takes back the last fix and every fix before it with the same `batch` (a fix without a `batch` goes alone, as today).
  - `preview(moves) -> dict(state, why, texts, classes, gone)`: nothing is written; `state`/`why` from `helper.chain`; `texts` the sentences; `classes` = for every class any changed lesson has (before or after), the payload `grid("class", name)` would give with the fixes applied, each lesson row carrying `mark` (`"moved"`, `"changed"`, `"new"` or `""`) and, when moved, `was = dict(d, p)`; `gone` = `[dict(cls, what, d, p)]` for deleted lessons. `grid`'s payload-building moves into a helper both use.
- Produces in `app.py` (all `@need("committee")`, errors as the other draft routes: a `ValueError` is a 400 sentence, no draft a 404):
  - `GET /api/draft/suggest?key=` → `draft.suggest`; `POST /api/draft/fixes` (JSON `{"fixes": [...]}`) → `draft.fix_many`; `POST /api/draft/preview` (JSON `{"fixes": [...]}`) → `draft.preview`.
- `info()`'s `fixes` entries gain `batch` (or `None`).

- [ ] **Step 1: Write the failing server tests**

```python
def test_suggest_for_a_warning_and_for_one_that_is_gone():
    ... a draft whose lesson has a teacher step 5 does not name; k = the teachers warning's key
    j = c.get("/api/draft/suggest", query_string={"key": k}).get_json(); assert j["suggestions"] and j["suggestions"][0]["fixes"][0]["kind"] == "teacher"
    assert c.get("/api/draft/suggest", query_string={"key": "dep:C:Nobody:Nothing:teachers"}).status_code == 400

def test_a_batch_is_all_or_nothing_and_undone_together():      # Review Focus 2 and 3
    before = c.get("/api/draft").get_json()
    r = c.post("/api/draft/fixes", json={"fixes": [GOOD_MOVE, MOVE_INTO_A_CLASH]}); assert r.status_code == 400 and c.get("/api/draft").get_json()["fixes"] == before["fixes"]
    j = c.post("/api/draft/fixes", json={"fixes": [GOOD_MOVE, SECOND_GOOD_MOVE]}).get_json(); assert len(j["fixes"]) == len(before["fixes"]) + 2 and j["fixes"][-1]["batch"] == j["fixes"][-2]["batch"] is not None
    j = c.post("/api/draft/undo").get_json(); assert j["fixes"] == before["fixes"]
    assert c.post("/api/draft/fixes", json={"fixes": []}).status_code == 400 and c.post("/api/draft/fixes", json={"fixes": [GOOD_MOVE] * 3}).status_code == 400

def test_a_stale_suggestion_is_refused_whole():                # Review Focus 2
    ... get a two-fix suggestion; make another fix that takes its target slot; POST the suggestion's fixes → 400 with the sentence, the fixes list unchanged

def test_the_preview_shows_every_class_touched_and_changes_nothing():   # Review Focus 5
    ... a swap of lessons of two classes (teacher view): preview → state ok, classes names == {both}, each with one lesson marked "moved" and its was; GET /api/draft afterwards: fixes unchanged; a block lesson's move lists every class of the block; a delete appears in gone

def test_a_head_cannot_reach_the_helper_routes():
    ... the head client: 403/401 on suggest, fixes, preview
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/bin/python tests/smoke.py`
Expected: FAIL: `404` from `/api/draft/suggest`

- [ ] **Step 3: Implement `draft.suggest`, `fix_many`, the batch in `undo`, `preview`, and the three routes**

- [ ] **Step 4: Run the server tests, fast and full**

Run: `.venv/bin/python tests/smoke.py && .venv/bin/python tests/smoke.py --full`
Expected: all pass (smoke grows by 5)

- [ ] **Step 5: Commit**

```bash
git add draft.py app.py tests/smoke.py
git commit -m "feat(draft): suggestions for a warning, fixes made together, and a preview"
```

---

### Task 4: The page's pure parts: marks, the batch in the list, the words

**Files:**
- Modify: `static/grid.js`, `static/draft.js`, `tests/grid.test.js`, `tests/draft.test.js`

**Interfaces:**
- Consumes: the `preview` payload (`classes` with marked lesson rows, `gone`), a suggestion (`fixes, text, disturbs, state, moved`), `info()`'s `fixes` with `batch`.
- Produces in `static/grid.js`:
  - `Grid.markClass(row) -> "moved" | "changed" | "new" | ""` and `Grid.wasText(row, days) -> str` (`"was {day} period {p}"` for a moved row, else `""`).
  - `Grid.others(preview, shown) -> [class payload]`: the preview's classes but the one on the main grid (`shown` = `{view, name}`; for a teacher view every class is "other").
  - `Grid.previewFor(sel, slot) -> [fix]`: the list to preview for a click on a slot (the one fix `Grid.fixFor` gives).
- Produces in `static/draft.js`:
  - `Draft.batches(fixes) -> [{batch, items: [fix]}]`: the fixes list grouped so that neighbours with the same `batch` are one entry (a fix without a batch is its own), newest last.
  - `Draft.undoText(fixes) -> str`: `"Undo the last fix"` or, when the last entry is a batch of two, `"Undo the last two fixes"`.
  - `Draft.stateWord(state) -> str`: `"Clean"` for `"ok"`, `"Bends a Prefer"` for `"prefer"`.

- [ ] **Step 1: Write the failing Node tests** (marks and `wasText`; `others` for a class view and a teacher view; `previewFor` for a move and a swap; `batches` for [single, pair, single]; `undoText` for a single and a pair; `stateWord`)

- [ ] **Step 2: Run them to verify they fail**

Run: `node tests/grid.test.js && node tests/draft.test.js`
Expected: FAIL: `Grid.markClass is not a function`

- [ ] **Step 3: Implement the functions**

- [ ] **Step 4: Run the tests**

Run: `node tests/grid.test.js && node tests/draft.test.js && node --check static/app.js`
Expected: both suites pass with the new cases; no syntax error

- [ ] **Step 5: Commit**

```bash
git add static/grid.js static/draft.js tests/grid.test.js tests/draft.test.js
git commit -m "feat(grid): preview marks, batches in the fixes list, and the helper's words"
```

---

### Task 5: The helper in the Fix card

**Files:**
- Modify: `static/app.js`, `static/style.css`, `README.md`

**Interfaces:**
- Consumes: Tasks 3 and 4; the Fix card of stage 2 (`S.fix`, `fixHTML`, `fxOpen`, `fxOptions`, `fxFix`, `fxAfter`, `fxClick`, `fxAlso`, `Grid.wanted`).
- Produces in `static/app.js`:
  - `S.fix` gains `warn` (the key of the warning the card was opened from, or null), `ways` (the `suggest` answer for it, with what it was asked for, as the options are kept), and `pre` (a preview being shown: `{fixes, answer}` or null).
  - **Fix the timetable** on a warning sets `warn` and fetches `/api/draft/suggest` for it (dropping a late answer with `Grid.wanted`, as for options); the side panel then starts with **Ways to settle this**: the warning's sentence, then each suggestion as a block: its `text`, its `disturbs` lines, a state dot with `Draft.stateWord`, and two buttons, **Show** (`data-fxshow="{index}"`) and **Apply** (`data-fxapply="{index}"`). With no suggestions: the `none` sentence and, when there are `blocked` entries, "The nearest ways, and what each breaks:" with each `text` and `why` and no buttons. Selecting a lesson on the grid keeps this block above the lesson's own lists; **Close** (`data-fxwaysclose`) removes it.
  - **Show** posts the suggestion's fixes to `/api/draft/preview` and opens the **Before you apply** panel under the grid: the sentences, the state, then, for each class in `Grid.others(...)`, that class's week as a small table (`Grid.table` on its payload, the same cell drawing as the main grid but read-only, changed lessons outlined by `Grid.markClass` with `Grid.wasText` in the title), the `gone` lessons as a list, and **Apply** and **Cancel**. The main grid outlines the lessons of the shown class that the preview marks.
  - **Apply** (from a suggestion or from the preview panel) posts the fixes to `/api/draft/fixes`; then as after any fix (`fxAfter`): the draft list, the grid and the options again; the ways are fetched again when the warning is still on the list, else the block says "This warning is settled." A 400 toasts the sentence and fetches the ways again.
  - A swap whose slot has `also` sentences no longer uses `confirm`: the click opens the **Before you apply** panel for `Grid.previewFor(sel, slot)`, so the other class's week is seen before the swap is made. Swaps and moves without `also` apply at once, as in stage 2.
  - The Fixes list is drawn from `Draft.batches`: a batch of two is one entry with both sentences; the undo button's label is `Draft.undoText`.
- `style.css`: the ways block, the preview panel, the small tables (`table.fxgrid.small`), the mark outlines.
- `README.md`: the Publish item gains the helper (ways to settle a warning, Show before Apply, two fixes together undone as one, what "blocked" means) and the preview before a swap that moves another class's lesson.

- [ ] **Step 1: Draw the ways block and the preview panel, wire the clicks**

Run: `node --check static/app.js && node tests/grid.test.js && node tests/draft.test.js`
Expected: no syntax error; both suites pass

- [ ] **Step 2: Check the page in the browser preview against a scratch `DATA_DIR`**

Start the scratch server (port 8003, the README's example codes, a fresh temporary `DATA_DIR`; a temporary `timetable-scratch` launch configuration, removed afterwards). Use a spoiled copy of a solved sample timetable (two lessons moved into a clash, one teacher changed to one step 5 does not name, one lesson deleted, one duplicated), so the draft has warnings of each kind. Expected: **Fix the timetable** on the teacher warning opens the card with "Give … to …" first; **Show** opens Before you apply with nothing else moving; **Apply** settles it and the block says so; the clash warning offers moves, and at least one suggestion on the page is two fixes with "Then"; applying it adds one entry with two sentences to the Fixes list and **Undo the last two fixes** takes both back; the missing lesson offers adds and the duplicate a delete; a warning for a rule in words shows the no-suggestion sentence; a swap from a teacher's week that moves another class's lesson opens the preview with that class's week; a warning that cannot be settled shows the blocked list. Screenshots of the ways block and of the preview panel for the report. Say plainly what was not exercised.

- [ ] **Step 3: Run every suite, commit**

Run: `.venv/bin/python tests/test_helper.py && .venv/bin/python tests/test_fixes.py && .venv/bin/python tests/test_verify.py && .venv/bin/python tests/test_choices.py && .venv/bin/python tests/test_rules.py && .venv/bin/python tests/test_sync.py && .venv/bin/python tests/smoke.py && node tests/grid.test.js && node tests/draft.test.js && node tests/choices.test.js && node tests/groups.test.js && node tests/map.test.js && node tests/people.test.js && node tests/sync.test.js && node --check static/app.js`
Expected: every suite passes

```bash
git add static README.md
git commit -m "feat(publish): the helper: ways to settle a warning, with a preview before applying"
```

---

## Not in this plan

- Typing a request in words (stage 4).
- Chains of more than two fixes, and suggestions that add or delete as the second fix of a pair.
- Suggestions for a selected lesson with no warning (the stage 2 lists already say where it can go).
- Heads seeing the draft (project 3).

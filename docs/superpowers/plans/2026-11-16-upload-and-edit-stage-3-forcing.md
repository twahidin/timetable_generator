# Upload and edit, stage 3: forcing, and Not placed. Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** On the board a lesson can be dropped where it clashes (it lands and is marked), dropped on another lesson to push that lesson out, lifted out to a "Not placed" tray and put back, on any day; counters above the board say what is wrong; nothing can be published, printed or downloaded while a lesson is not placed.

**Architecture:** The draft stays the uploaded file plus the list of fixes. Two things are added to that list: a lesson may be lifted out (kinds `lift` and `place`, and an `out` list on a move, a place or an add for what it pushes out), and a change judged a clash may be kept when the page asks for it by name (`force`). A lesson with no time is not in the model's lessons at all: `fixes.apply` keeps it in a pool beside them, so the check, the editor's index, the helper, the printouts and the published timetable never meet a lesson without a time. The draft's answer lists the pool, adds a critical "Not placed" warning for each lesson in it, and the board draws it as a tray. `ttgen/` is not changed.

**Tech Stack:** Flask (`app.py`, `draft.py`, `fixes.py`), vanilla JS (`static/app.js`, `static/board.js`, `static/draft.js`), plain-script tests. No new dependency.

**Spec:** `docs/superpowers/specs/2026-11-16-upload-and-edit-design.md` (stage 3 of "Suggested order of building": "A forced move, push out, the tray, cut and paste, another day; the counters; the critical marks on cards"), with the notes of stages 1 and 2 in `docs/superpowers/plans/`.

**Branch:** `upload-and-edit-stage-3`, cut from `upload-and-edit-stage-2`.

## Global Constraints

- "A lesson that vanishes" is the first failure the design names: "A pushed-out or lifted-out lesson is always in 'Not placed' until it is put back, through Undo, a reload, a second committee member's change and a new check; and nothing can be published while one is there."
- "A band torn apart: one class of a band moved without the others, or its groups at different times." A lesson is lifted, pushed out, placed and moved as its whole lesson id, all rows and classes.
- "A forced change that hides what it broke. Every critical mistake a change makes is on the card and in the counters at once."
- "A lesson can never be dropped where it cannot go": a place judged `na` (a break, recess, outside the day, not enough periods left) is refused, forced or not.
- A push only pushes out lessons of the dragged lesson's own class or classes. "A teacher or a room that is busy elsewhere is marked on the card and nothing else moves."
- Forcing happens only from the board, and only when the request says `force`. The Fix card, the helper and the typed request make only clean changes, as before, and never see a lesson that is not placed.
- Printouts and the draft's download "are refused, in words, while a lesson is not placed".
- A draft from before this stage opens as it did, with its fixes. A fix list replayed against a changed file or setup skips what no longer applies and names it, as today.
- Critical: not placed, no teacher, a teacher in two lessons, a class clash, a room holding more than it takes, a lesson in a break or outside the day. A lesson with no room is counted and shown, and is a warning. A student in two lessons at once is a warning.
- Rows by teacher and by room, the teacher and room lists on the card, the open band and the warnings panel beside the board are stage 4. Build none of them.
- `ttgen/` is not changed. Made-up names only; the school is only ever "CTSS" or "the school". New sentences are plain, with no em-dash and no arrow. No test or check calls a model API. Never run `git stash` in any form, nor `git checkout -- <file>`.
- Every browser check of clicking or dragging is made with real pointer actions (`left_click`, `left_click_drag`), and the report says for each check which kind of action it was.

## Decisions this plan makes (for the committee lead to check)

1. A drop on an empty place that clashes simply lands and is marked red; no question is asked. Undo takes it back.
2. A drop on a place where the class already has a lesson asks one question: Swap (when a swap is allowed), Push out (the lessons named go to Not placed), or Cancel.
3. The tray is at the right of the board. It lists every lesson that is not placed, on any day, grouped by class, and under them "Step 5 asks for these".
4. Cut and paste from the keyboard: Ctrl or Cmd+X lifts the selected lesson out; Ctrl or Cmd+V puts the selected tray lesson at the place the pointer is over.
5. Dragging a card over another day's tab for half a second switches to that day; the drop is made there.
6. A red mark on a card says in two or three words what is wrong ("In two places", "In a break", "No teacher", "Not placed"); the full sentence is in the line when the card is selected. "No room" is an amber mark.
7. A difference from step 5 about a class's lessons cannot be answered "Update step 5" while one of those lessons is waiting in Not placed (it would shrink step 5 to fit a lesson that was only lifted out).
8. A lesson with no room is now listed as a warning of its own kind, "No room" (stage 1 left it unlisted until this stage).
9. Replacing the draft by a new upload already asks first when the draft has changes that were never published; a lesson waiting in Not placed is such a change, and the question says so.

## Review Focus

1. Undo after a push that lifted two lessons, one of them a band: all come back where they were, in one undo. Test in Task 1.
2. The fix list replayed after the file or the setup changed (a lesson an `out` names is gone; a lifted lesson's class was renamed): the fix that cannot apply is skipped and named, nothing else is lost, and no lesson is left both on the timetable and in the pool. Test in Task 1.
3. Two committee members: one lifts a lesson while the other is dragging it, or both push the same lesson out: the second change is judged on the draft as it then is and refused in words or applied; never a lesson in two places or in neither. Test in Task 2 (the second request), browser check in Task 4.
4. Publishing, printing and downloading with one lesson not placed: each refused in words; with none, each works as before. Test in Task 2.
5. The old editor, the helper and the typed request while lessons are in the pool: they work on the placed lessons, never offer a pooled lesson, and never force. Test in Task 2.

---

### Task 1: The pool, the new kinds and their judging (`fixes.py`)

**Files:**
- Modify: `fixes.py`
- Test: `tests/test_fixes.py`

**Interfaces:**
- Consumes: `apply_one`, `apply`, `editor`, `Busy`, `judge`, `slots`, `_rows`, `what`, `when`, `_slot`, `_after`, `short` as they are.
- Produces:
  - `KINDS = ("move", "swap", "teacher", "room", "add", "delete", "lift", "place")`.
  - `apply_one(lessons, fix, spec, days, new_id=None, touched=None, was=None, pool=None)`: `pool` is a list the caller owns holding the rows of lessons that are not placed (default: a new empty list). 
    - `lift` `{kind, id}`: the lesson's rows leave `lessons` and join `pool`, each keeping its `d` and `p` as they were. Sentence: `"Lifted out {what} from {when}."` A lesson already in the pool, or an unknown id: `ValueError("There is no lesson with that id on the timetable.")`.
    - `place` `{kind, id, d, p}` with optional `out`: the lesson's rows leave `pool` and join `lessons` at `d`, `p` (the day checked by `_slot`, `ext` set as a move sets it). Sentence: `"Placed {what} on {when}."` An id not in the pool: `ValueError("That lesson is not waiting to be placed.")`.
    - `out` (a list of lesson ids) on a `move`, a `place` or an `add`: before the change is made each of those lessons that is on the timetable is lifted into the pool; an id that is not on the timetable any more is passed over. The sentence gains `" Pushed out: {what}, {what}."` naming those that were lifted, in the list's order; nothing is added when none was. An `out` that names the lesson itself is `ValueError("That fix is not complete.")`.
    - `delete` finds its lesson on the timetable or in the pool. The sentence for one in the pool: `"Deleted {what} (it was not placed)."`
    - `teacher` changes the matching rows on the timetable and in the pool. `room` finds its row in either.
    - `move` and `swap` of a lesson that is in the pool: `ValueError("That lesson is not placed. Place it first.")`.
  - `apply(lessons, fixes, spec, days) -> dict(lessons, texts, problems, touched, was, pool)`: `pool` is the rows not placed after every fix. No id is ever in both `lessons` and `pool`.
  - `editor(fixes, out)`: also leaves `pool` in `out`.
  - `judge(m, spec, days, fix, ctx=None, pool=())`: `pool` is the rows not placed now.
    - `lift`: `ok` for a lesson on the timetable; `na` with the sentence otherwise.
    - `place`: judged as a move of that lesson to `d`, `p` is judged (lesson time, clashes, rules), with no "changes nothing" case and no check of periods against the plan.
    - a fix with `out`: judged with those lessons taken off the timetable first (they neither clash with it nor count for a rule).
    - A `teacher` or `room` fix on a pooled lesson alone: `ok`.
  - `slots(m, spec, days, lesson_id, pool=())`: for a lesson on the timetable, as now, and each slot where other lessons of its classes are gains `push = dict(state, why, out=[dict(id, what)])`: the lessons there (all of them, the swap's one included) and how the move is judged once they are out; `push` is `None` for a place with no other lesson there. For a lesson in the pool: every `(d, p)` judged as a `place`, `swap` always `None`, `push` as above.
  - `marks(busy, rows, pool=False) -> list of str`, the critical kinds of one lesson in the order `"notplaced", "noteacher", "break", "teacher", "class", "room"`, then `"noroom"` (not critical): `"notplaced"` alone when `pool`; `"noteacher"` when a row has no teacher; `"break"` when `busy.lesson_time` gives a reason for its own place; `"teacher"` when one of its teachers is on another lesson id in one of its periods; `"class"` when a row that the whole class takes shares a period with another lesson id of that class, or a group's row with a whole-class lesson of one of its classes; `"room"` when one of its rooms holds more lesson ids in a period than `m["room_cap"]` allows (1 when the room is not listed); `"noroom"` when a row's room is empty or `"TBC"`. Two groups of one class at the same time are not `"class"`. Students in two lessons are not marked.
  - `short(m, spec, pool=())`: a lesson in the pool counts as timetabled, so it is not also offered as one step 5 asks for.

- [ ] **Step 1: Write the failing tests** in `tests/test_fixes.py`, with the file's helpers (`lesson`, `two_lessons`, `one_block`, `SP`, `DAYS`, `by_id`). The tests, each with exact sentences and places:

```python
def test_lift_takes_the_whole_lesson_to_the_pool_and_place_brings_it_back():
    sp, L = one_block(); pool = []
    assert fixes.apply_one(L, dict(kind="lift", id=7), sp, DAYS, pool=pool) == f"Lifted out {fixes.what(B0)} from {DAYS[0]} period 0."
    assert L == [] and [x["id"] for x in pool] == [7, 7, 7] and all((x["d"], x["p"]) == (0, 0) for x in pool)
    assert fixes.apply_one(L, dict(kind="place", id=7, d=1, p=2), sp, DAYS, pool=pool) == f"Placed {fixes.what(B0)} on {DAYS[1]} period 2."
    assert pool == [] and len(L) == 3 and all((x["d"], x["p"]) == (1, 2) for x in L)

def test_a_push_lifts_what_it_names_and_says_so():        # move id 1 onto id 2's time with out=[2]: 2 is in the pool, the sentence ends " Pushed out: {what 2}."
def test_an_out_that_is_gone_is_passed_over():            # out=[2, 99]: 2 lifted, no error, the sentence names only 2
def test_an_out_naming_the_lesson_itself_is_refused():
def test_undoing_a_push_brings_everything_back():         # apply([push]) then apply([]) on the same lessons: equal to the start; pool empty
def test_delete_and_teacher_reach_a_lesson_in_the_pool(): # lift, then teacher by key changes the pooled rows; delete empties the pool with "(it was not placed)"
def test_move_and_swap_of_a_pooled_lesson_are_refused():
def test_apply_never_leaves_a_lesson_on_both_sides():     # a random list of 200 lift/place/move/push/delete/add fixes on the primary sample's lessons: after every prefix the ids of lessons and of pool are disjoint, and every id of the start is in exactly one of lessons, pool or deleted
def test_a_fix_list_replayed_on_changed_lessons_skips_and_names(): # [lift 1, place 1, push with out=[2]] applied to lessons from which 1 was removed: two problems named, 2 untouched, nothing in the pool
def test_judge_lift_place_and_push():                     # lift ok; place on a free slot ok; place on a break "na"; place where its teacher is busy "no" with that reason; a move onto another lesson of the class is "no" without out and "ok" with out=[it]
def test_slots_say_what_a_push_would_take_out():          # for id 1, the slot at id 2's time: push == dict(state="ok", why="", out=[dict(id=2, what=...)]); a free slot: push is None; an old key set (d, p, state, why, swap, also) is unchanged
def test_slots_of_a_pooled_lesson_are_places():           # no (d, p) is skipped as "its own"; every slot's swap is None
def test_marks():                                         # each kind on a made-up pair; two groups of one class at once: []; a pooled lesson: ["notplaced"]; a room listed with room_cap 2 holding two lessons: no "room"
def test_short_counts_a_pooled_lesson_as_timetabled():
```

- [ ] **Step 2: Run** `.venv/bin/python tests/test_fixes.py`. Expected: fails on the first new test (`apply_one() got an unexpected keyword argument 'pool'`).
- [ ] **Step 3: Write the code** in `fixes.py`. `apply_one` still checks everything before it changes anything, for every kind, so a refused fix leaves `lessons` and `pool` as they were.
- [ ] **Step 4: Run** `.venv/bin/python tests/test_fixes.py`, `tests/test_helper.py`, `tests/test_typed.py`, `tests/smoke.py`, `tests/test_board.py`. Expected: all pass (the old callers pass no `pool`).
- [ ] **Step 5: Commit** `feat(fixes): a lesson can be lifted out, placed and pushed out; marks`.

### Task 2: The draft with a pool (`draft.py`, `app.py`)

**Files:**
- Modify: `draft.py`, `app.py`
- Test: `tests/test_board.py`, `tests/smoke.py`

**Interfaces:**
- Consumes: Task 1's `apply(...)["pool"]`, `editor`, `judge(..., pool=)`, `slots(..., pool=)`, `marks`, `short(..., pool=)`; `verify.warning(key, kind, text, strength, group, where, sides, ops, crit)`.
- Produces:
  - `model_now` keeps `fx["pool"]` (the rows not placed) with the model; every caller that judges passes it.
  - `draft.FIELDS` gains `lift=("id",)` and `place=("id", "d", "p")`. `_whole` keeps two optional request fields on a `move`, a `place` and an `add`: `force` (true only when it is exactly `True`) and `push` (the same).
  - `draft.fix(move)`:
    - with `push`, the lessons to push out are worked out by the server, under the lock, from the draft as it then is: every lesson of the moved lesson's classes that shares a period with the target (the moved lesson itself excepted); they are stored on the fix as `out=[ids]`. `push` is never stored.
    - a judgement of `na` is refused with its sentence. A judgement of `no` is refused with its sentence unless the request has `force`; with `force` the fix is kept. `force` is never stored.
    - a `lift` needs no `force`.
    - `fix_many`, `preview`, `suggest` and `ask` (the Fix card's batch, the helper, the typed request) never force and never push.
  - `draft.info()` gains `unplaced`: the number of lessons in the pool. Its `warnings` gain, built in `draft.py`:
    - for each lesson in the pool: `warning(f"clash:notplaced:{id}", "clash", f"Not placed: {what}.", where=dict(cls=first class or "", id=id), crit="notplaced")`;
    - for each lesson row on the timetable with no room (empty or `"TBC"`): `warning(f"room:none:{id}:{group}", "room", f"No room: {what} on {day} period {p}.", strength="Prefer", group=first class or "School", where=dict(cls, day, period, id, row))`;
    - a warning whose key is `dep:{k}:missing` or `dep:{k}:periods` for a key `k` that a pooled lesson's rows have: its `ops` becomes `None` and its text gains `" A lesson of it is waiting in Not placed."`
    - `critical` counts the not-placed warnings with the rest, so `publish()` refuses through the rule stage 1 made.
  - `draft.board()` gains: on every card `marks` (`fixes.marks`) and `why` (the sentence `Busy.clash` gives for the card at its own place with itself set aside, or `""`); `unplaced`: the pool's lessons as cards (`d` and `p` are `None`; `was = dict(d, p)` the place they left; `marks == ["notplaced"]`), ordered by first class, then id; `short`: `fixes.short(m, spec, pool)` for the whole school, each entry with `classes` added (the classes of that step 5 row, from `verify.planned_rows`).
  - `draft.slots(lesson_id)` answers for a lesson in the pool too.
  - `class NotPlaced(Exception)` with `.count`; its sentence is `"1 lesson is not placed. Place it or delete it on step 8 first."` or `"{n} lessons are not placed. Place them or delete them on step 8 first."` `draft.printouts` and `draft.database` raise it; `POST /api/draft/printouts` and `GET /api/draft/download` answer 409 `{error, unplaced}`.
  - `UnpublishedFixes`'s sentence: `"The draft has changes that were never published."`, and when lessons are waiting it adds `" {n} lesson(s) are waiting in Not placed."` (`"1 lesson is waiting in Not placed."` for one).
  - The published record and the printouts' "Read me" list of changes hold the new kinds' sentences like any other fix's.

- [ ] **Step 1: Write the failing tests.** In `tests/test_board.py` (its draft helper): `test_a_lift_is_in_info_the_board_and_the_counts` (after `draft.fix(dict(kind="lift", id=PLAIN_ID))`: `info()["unplaced"] == 1`, one warning with `crit == "notplaced"` and the exact text, `critical` one higher, the card gone from `board()["cards"]` and in `board()["unplaced"]` with `d is None`, `was`, and `marks == ["notplaced"]`); `test_a_forced_move_needs_force` (a move judged `no`: refused without `force` with its sentence, kept with it, and the card's `marks` then hold the kind and `why` the sentence); `test_a_place_judged_na_is_refused_even_forced`; `test_a_push_is_worked_out_by_the_server` (the stored fix has `out` with the ids and no `push` or `force` key; the pushed lessons are in `unplaced`; `undo()` brings all back); `test_a_second_push_of_the_same_lesson_finds_it_gone` (two `fix` calls with `push` for the same target one after the other: the second's `out` does not name the lesson already lifted, and no id is in both `cards` and `unplaced`); `test_publish_printouts_and_download_are_refused_while_a_lesson_waits` (the three exceptions with their sentences; after `place`, all three work); `test_slots_of_a_waiting_lesson`; `test_no_room_is_a_warning_of_its_own_kind`; `test_update_step_5_is_withheld_for_a_waiting_lesson`; `test_the_helper_and_the_batch_never_force` (`fix_many` with a move judged `no` and a `force` key is refused; `suggest` on a warning offers nothing that needs a pooled lesson); `test_a_draft_from_before_this_stage_opens` (a `meta.json` with only move and swap fixes: `info()` and `board()` answer, `unplaced == 0`); `test_marks_on_the_board_of_a_clean_draft_are_empty`. In `tests/smoke.py`: the routes' 409 answers for printouts and download with a lesson waiting, and the upload's 409 sentence.
- [ ] **Step 2: Run** `.venv/bin/python tests/test_board.py`. Expected: the first new test fails (`This kind of fix is not known.`).
- [ ] **Step 3: Write the code.**
- [ ] **Step 4: Run** every Python test script and `tests/smoke.py`. Expected: all pass.
- [ ] **Step 5: Commit** `feat(draft): Not placed in the draft, a forced move, a push worked out by the server; no room is listed`.

### Task 3: The tray, the counters and the questions as plain functions (`static/board.js`, `static/draft.js`)

**Files:**
- Modify: `static/board.js`, `static/draft.js`
- Test: `tests/board.test.js`, `tests/draft.test.js`

**Interfaces:**
- Consumes: the board payload of Task 2 (`cards[].marks`, `cards[].why`, `unplaced`, `short`) and the slots with `push`.
- Produces:
  - `Board.MARK = {notplaced: "Not placed", noteacher: "No teacher", break: "In a break", teacher: "In two places", class: "In two places", room: "In two places", noroom: "No room"}` and `Board.critical(card) -> bool` (any mark other than `"noroom"`).
  - `Board.badge(card) -> {text, crit} | null`: the words of the card's first mark and whether it is critical; `null` for a card with no mark.
  - `Board.tray(board) -> [{cls, cards}]`: `board.unplaced` grouped by each card's first class (`""` last), classes in the order of `board.levels`.
  - `Board.counts(board) -> {notplaced, noteacher, twoplaces, inbreak, noroom}`: lessons, not rows; `twoplaces` counts a card once whichever of teacher, class and room it has.
  - `Board.COUNTERS = [["notplaced", "Not placed"], ["noteacher", "No teacher"], ["twoplaces", "In two places"], ["inbreak", "In a break"], ["noroom", "No room"]]`.
  - `Board.hits(board, counter) -> [card]`: the cards a counter counts, in the order day, period, first class, id; the tray's cards for `"notplaced"`.
  - `Board.step(hits, id) -> card | null`: the card after the one with `id` in `hits`, the first when `id` is not among them or is the last; `null` when `hits` is empty.
  - `Board.can(slot)` stays (clean or bends a rule). New: `Board.lands(slot) -> bool`: the slot is not null, has no lesson to push (`slot.push` is null or undefined) and its state is `"ok"`, `"prefer"` or `"no"`. `Board.forced(slot) -> bool`: `slot.state === "no"`.
  - `Board.asks(slot) -> {swap: bool, push: bool} | null`: `null` when the place has no other lesson (`slot.push` null or undefined); else `swap` when `slot.swap` is a lesson id and the slot's own state is `"ok"` or `"prefer"`, `push` when `slot.push.state` is not `"na"`.
  - `Board.fix(card, slot, how)`: `how` is `"move"` (default), `"swap"` or `"push"`. For a card on the timetable: a move `{kind: "move", id, d, p}` with `force: true` when `Board.forced(slot)`; a swap as now; a push `{kind: "move", id, d, p, push: true}` with `force: true` when `slot.push.state === "no"`. For a card from the tray (`card.d === null`): the same with `kind: "place"`, and never a swap.
  - `Board.addFix(short, slot, how) -> {kind: "add", key, d, p, n}` with `force` and `push` by the same rules.
  - `Board.liftFix(card) -> {kind: "lift", id}`.
  - `Board.question(card, slot, board) -> {text, also, swap, push}`: `text` `"{card.what} on {day} period {p}: another lesson is there."`; `swap` the button's words `"Swap with {other what}"` or `null`; `push` `"Push out {what}"`, `"Push out {what} and {what}"`, or for three and more `"Push out {n} lessons"`, or `null`; `also`: the swap's `also` sentences, and when the push is judged `"no"` the sentence `"It will still clash: {slot.push.why}"`.
  - `Board.tell(slot, days)` gains: for a place where another lesson is, `"Another lesson is there. Drop to swap or push out."`; for a `"no"` place with no other lesson, `"Move to {day} period {p}. It will clash: {why}"`.
  - `Board.target` and `Board.aim` are unchanged (a swap target is still a slot whose swap is allowed).
  - In `static/draft.js`: `Draft.critWord("notplaced") === "Not placed"`; the warning kind `"room"` has the title `"No room"` and sorts after the clashes.

- [ ] **Step 1: Write the failing tests** in `tests/board.test.js` (one per function above, with exact values: a board of three cards with marks, two tray cards of two classes and one with no class; slots with and without `push`; a tray card's fixes; the question for one, two and three lessons to push and for a swap with an `also`) and in `tests/draft.test.js` (the word and the title).
- [ ] **Step 2: Run** `node tests/board.test.js`. Expected: fails (`Board.tray is not a function`).
- [ ] **Step 3: Write the code.**
- [ ] **Step 4: Run** `for f in tests/*.test.js; do node "$f" || break; done`. Expected: every file passes.
- [ ] **Step 5: Commit** `feat(board): the tray, the counters, forcing and the push question as plain functions`.

### Task 4: Forcing, push out and the tray on the page

**Files:**
- Modify: `static/app.js`, `static/style.css`

**Interfaces:**
- Consumes: Tasks 2 and 3; the board's page code as stage 2 left it (`S.board`, `bdLoad`, `bdDraw`, `bdPaint`, `bdWant`, `bdSlotsP`, `bdTry`, `bdSend`, `bdDropWait`, `bdLineDraw`, `bdClick`, the document's drag listeners).
- Produces, for Task 5: the tray's markup (`<div id="bdTray">`, a tray card `<button class="bdcard tray" data-card="{id}" draggable="true">`, a "Step 5 asks for these" entry `<button class="bdshort" data-short="{key}" draggable="true">`); `bdCard(id)` finds a tray card too; the selected card's line (`#bdLine`) has room for buttons.

- [ ] **Step 1: Marks.** A card with a mark shows `Board.badge` at its top right: red for a critical one, amber for "No room"; a critical card has a red outline. The selected card's line adds the card's `why` sentence when it has one.
- [ ] **Step 2: The strip and a forced drop.** The strip's red means "lands, but clashes". A click or a drop on a place where `Board.lands(slot)` makes the change of `Board.fix(card, slot)` (with `force` when it is red); the line then says the fix's sentence. A grey place refuses with its reason as now. The hint reads: "Drag a lesson to another time on its row, or click it and then click a place. Green is clean, amber bends a rule, red lands but clashes, grey cannot take it. Drop on another lesson to swap or push it out."
- [ ] **Step 3: The question.** A click or a drop on a place where another lesson is (`Board.asks(slot)` not null) shows `Board.question` in the line: its text, its `also` sentences, then the buttons it has, in the order Swap, Push out, Cancel. Swap posts `Board.fix(card, slot, "swap")`, Push out posts `Board.fix(card, slot, "push")`. When neither is possible the place refuses with "Another lesson is there, and it cannot be pushed out: {slot.push.why}". A dashed outline still marks a lesson a swap is allowed with, and a drop anywhere on such a lesson aims at that lesson's start, as in stage 2 (the question then offers Swap, and Push out for that place). A drop on any other lesson is judged at the place the pointer gives (the pointer's period less the grab), and what it would overlap there is what Push out names.
- [ ] **Step 4: The tray.** At the right of the board, as wide as three periods, scrolling on its own: the heading "Not placed" with the count; `Board.tray` as groups of cards (the class's name, then its cards drawn as on the board, each saying where it was: "was Odd Mon period 3"); "Nothing is waiting." when empty. Dragging a card from the board onto the tray lifts it (`Board.liftFix`); the selected card's line has a button "Lift out" that does the same. A tray card is selected and dragged like any card: its slots are fetched, the strip shows on its class's rows in the day view (every row of its classes) and on every row in its class's cycle view, and a click or a drop on a place places it (`Board.fix` gives `kind: "place"`), with the same question when another lesson is there. Dropping a tray card back on the tray does nothing.
- [ ] **Step 5: The counters.** Above the hint, `Board.COUNTERS` with `Board.counts`: each a button "{label} {n}", red when its count is above zero for the four critical ones, amber for "No room", plain at zero; then "Warnings {n}" (the draft's open warnings that are not critical), which scrolls to the warnings card. A click on a counter with a count selects `Board.step(Board.hits(board, counter), the selected id)`: the day view switches to that card's day (the cycle view to that card's first class when the card is not in the shown class), the card is scrolled into view and selected; for "Not placed" the tray card is selected. While a counter is being stepped through, every card it does not count is faded; the fade ends when the selection is closed.
- [ ] **Step 6: Check.** `node --check static/app.js`; every `tests/*.test.js`. In the browser on the scratch server the controller names, with real pointer actions: a drag to a red place lands, the card is outlined red with "In two places", the counter goes up, the line says why; "Undo the last timetable change" takes it back and the counter goes down; a drop on another lesson that cannot swap asks with Push out, Cancel changes nothing, Push out moves the card and the other lesson is in the tray with "was ..."; a drop on a swappable lesson offers Swap and Push out; a tray card dragged to a green place of its row is placed; a tray card dragged to an occupied place asks; a card dragged onto the tray is lifted, and "Lift out" does the same; a band pushed out leaves every one of its classes' rows and is one card in the tray under its first class; undo after a push brings both lessons back; a counter click steps through its cards across days; step 9 says how many critical mistakes there are and refuses to publish while one waits; a second tab shows a lift within about five seconds; the console has no new error.
- [ ] **Step 7: Commit** `feat(board): a clash lands and is marked, push out, the Not placed tray, the counters`.

### Task 5: Another day, cut and paste, delete, step 5's list, and step 9

**Files:**
- Modify: `static/app.js`, `static/style.css`, `README.md`

**Interfaces:**
- Consumes: Task 4's tray markup and line; `Board.addFix`; the existing `delete` fix and `GET /api/draft/options?id=` (its `delete` judgement) and `fixes.can_delete`; step 9's `printoutsCard` and the draft's download link.

- [ ] **Step 1: Another day.** While a card is in the air, a pointer held over a day's tab for half a second switches the board to that day without ending the drag; the drop is made there. (The board is drawn again under the drag: the drag's state lives in `S.board`, not in the dragged element, as stage 2 arranged for a new draft landing mid-drag.) A selected card stays selected when the day is changed by a click, so "select, change the day, click a place" still works.
- [ ] **Step 2: Cut and paste.** With a card on the board selected, Ctrl+X or Cmd+X lifts it out and selects it in the tray. With a tray card selected, Ctrl+V or Cmd+V puts it at the place the pointer is over, as a click there would (the question included); with the pointer over no place of its rows it says "Point at a place on its row, then paste." Neither key does anything when the keyboard is in a field, and the browser's own cut and paste is left alone unless a card is selected.
- [ ] **Step 3: Delete.** The selected card's line, on the board or in the tray, has "Delete this lesson". It asks first: "Delete {what}?" and, from the delete's judgement, "Step 5 asks for this lesson." when deleting leaves step 5's periods short, then Delete and Cancel. Delete posts the existing `delete` fix; a refusal says the server's sentence.
- [ ] **Step 4: Step 5 asks for these.** Under the tray's cards, the heading "Step 5 asks for these" and `board.short` as entries "{name} · {n} period(s)" with "has {have} of {want}"; nothing is shown when the list is empty. An entry is selected and dragged like a tray card: where it fits comes from `GET /api/draft/options?add={key}&n={n}` (its `slots`), the strip shows on the rows of the entry's `classes`, and a click or a drop on a place posts `Board.addFix`. A place where another lesson is refuses with "Another lesson is there. Lift it out first."
- [ ] **Step 5: Step 9.** While lessons are waiting, the printouts card and the draft's download on step 9 are replaced by the sentence the server gives ("{n} lessons are not placed. Place them or delete them on step 8 first."), and a 409 from either route shows the same sentence. A critical "Not placed" line's "Show on step 8" opens step 8 with that lesson selected in the tray.
- [ ] **Step 6: README.** The paragraph on step 8 says a lesson can be dropped where it clashes and is then marked, that a drop on another lesson swaps or pushes it out, what the Not placed tray is, and that nothing is published, printed or downloaded while a lesson waits there.
- [ ] **Step 7: Check.** `node --check static/app.js`; every `tests/*.test.js`; `.venv/bin/python tests/test_board.py`; `.venv/bin/python tests/smoke.py`. In the browser with real pointer actions and real keys: a card dragged over another day's tab and held switches the day and is dropped there; Ctrl+X lifts the selected card; Ctrl+V with the pointer over a green place places it; "Delete this lesson" asks, Cancel keeps it, Delete removes it and Undo brings it back; the deleted lesson then appears under "Step 5 asks for these" and dragging it to a place adds it; with a lesson waiting, step 9 shows the sentence in place of the printouts and "Show on step 8" selects the tray card; with none waiting the printouts are made as before; the console has no new error.
- [ ] **Step 8: Commit** `feat(board): another day, cut and paste, delete, step 5's list; step 9 refuses printouts while a lesson waits`.

## After the tasks

- The controller counts on the real returned timetables (counts and timings only): cards with each mark against stage 1's critical counts (the newest file must have no critical mark), the no-room warnings, and the time of `draft.board()` and `draft.slots()` with the marks and the push judgements; and, on a scratch copy, a lift, a forced move and a push each undone, with the lesson rows counted before and after.
- Notes go in `docs/superpowers/plans/2026-11-16-upload-and-edit-stage-3-notes.md`.

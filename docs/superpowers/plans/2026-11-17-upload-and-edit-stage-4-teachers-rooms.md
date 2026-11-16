# Upload and edit, stage 4: teachers and rooms, and nothing outside the timetable section. Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The board can show its rows by teacher and by room as well as by class; a lesson's teacher and room are changed on the lesson itself (a list each, with "none"), or by dragging its card to another teacher's or room's row; a band opens to show its groups; the helper's ways and the typed request live in the panel beside the board; the old one-class editor is gone, so everything on step 8 is inside the timetable section.

**Architecture:** Nothing new is stored. A change of teacher is today's `teacher` fix (for all that class's or group's lessons of the subject) and a change of room today's `room` fix (for one lesson, or for all the group's with a tick box, as one batch). Both may now be forced from the board as a move may, with the reason the page showed. The board's payload gains the teachers and rooms to make rows of; a new read-only answer lists who and which room could take one lesson. `static/board.js` lays out rows of any of the three kinds. The page code of the old editor's grid and lists is removed; its helper and typed-request parts are re-hosted in the panel. The judging of "push out" and "put beside" moves from every place to the one place a card is dropped on.

**Tech Stack:** Flask (`app.py`, `draft.py`, `fixes.py`, `helper.py`), vanilla JS (`static/app.js`, `static/board.js`, `static/draft.js`), plain-script tests. No new dependency.

**Spec:** `docs/superpowers/specs/2026-11-16-upload-and-edit-design.md` (stage 4 of "Suggested order of building": "Rows by teacher and by room; the card's teacher and room lists, with 'none'; the open band; the warnings panel, helper and typed request beside the board"), with the notes of stages 1 to 3 in `docs/superpowers/plans/`, and the committee lead's word of 2026-11-17: "The warnings and fixes should be highlighed in the editor instead of a separate section. ie it should part of the timetable section".

**Branch:** `upload-and-edit-stage-4`, cut from `upload-and-edit-stage-3`.

## Global Constraints

- "Teachers are grouped by department and rooms by kind. On these rows a card dragged along its row changes its time, exactly as on its class's row (the question of swap or push out is about its own class's lessons). A card dragged to another teacher's row gives the lesson to that teacher, and to another room's row moves it to that room: the same change the card's lists make. If that teacher or room is busy then, the card lands and both are marked; the other lesson is not pushed out and no swap between two classes is offered."
- "As today, a change of teacher is a change for that class's or group's lessons of that subject, all of them, because step 5 names one set of teachers for them; the page says how many lessons will change before it is made."
- "A change of room is for that one lesson, with a tick box 'all this group's lessons'."
- "None is a choice in both lists. A lesson can be left with no teacher or no room while the lead works. No teacher is a critical mistake until one is given; no room is counted and shown, and is a warning."
- "Teachers: those who are free in all the lesson's periods come first, in the order step 8 offers them today (who already teaches the subject, then the rest of its department), then everyone else with what they are teaching then." "Rooms: the free rooms of the right kind first, then the rest with what is in them then."
- "The helper and the typed request stay as they are, in that same panel: ways to settle the selected warning, and the box for asking in words. What they suggest is applied to the board like any other change." They make only clean changes and never see a lesson that is not placed.
- A lesson never vanishes; a band is never torn; a place judged `na` is refused forced or not; a forced change shows what it broke on the card and in the counters at once. (Stage 3's rules, unchanged.)
- A draft from before this stage opens as it did, with its fixes. `ttgen/` is not changed.
- The rows of the board never move under the pointer when the line's or the panel's content changes.
- Made-up names only; the school is only ever "CTSS" or "the school". New sentences are plain, with no em-dash and no arrow. No test or check calls a model API. Never run `git stash` in any form, nor `git checkout -- <file>`.
- Every browser check of a click, a drag or a key is made with real pointer and key actions at the pane's own size, and the report says for each which kind it was. The browser tool's drag is unreliable under an emulated window size.

## Decisions this plan makes (for the committee lead to check)

1. The rows are switched by three buttons above the board: Classes, Teachers, Rooms. Day tabs, Find, the counters, the strip and the panel work the same on all three.
2. On Teachers rows a lesson taught by two teachers is on both their rows. A lesson with no teacher is on a row "No teacher" at the top; on Rooms rows a lesson with no room is on a row "No room".
3. A click on a teacher's or a room's name opens that one row's whole cycle, as a class's name does.
4. Dropping a card on another teacher's row replaces, on that lesson's teachers, the teacher whose row it was dragged from with the one it is dropped on (and changes the time too when it is dropped on another period: two changes, one undo). The page first says how many lessons the change of teacher touches.
5. When the teacher or the room picked is busy then, the page says so and asks "Give it anyway?"; yes lands it and both lessons are marked.
6. The selected lesson opens in a fourth tab of the panel, "Lesson": its teacher list or lists, its room list, the tick box, and for a band its groups, each with its own lists. "Teacher, room and more" on the line goes.
7. The helper's "Ways to settle this" opens under a warning in the Warnings tab; the typed request box is at the foot of that tab. The old one-class grid with its lists of places is removed: the board is the only editor.
8. Where a card fits is worked out without judging "push out" and "put beside" for every place with a lesson; those are judged for the one place a card is dropped on. Every place with another lesson is blue; the question says what is possible there.

## Review Focus

1. A change of teacher made from one lesson changes all that class's or group's lessons of the subject: the count the page says is the count changed, across days, and one undo takes all back. Test in Task 1.
2. A drop on another teacher's row for a lesson with two teachers, and for one group of a band: only that teacher of that group changes; the band's other groups and the lesson's other teacher are untouched. Tests in Tasks 1 and 3.
3. "None": a lesson left with no teacher is critical at once and counted; given a teacher again it is clean. A room set to none is a warning. Test in Task 1.
4. A forced teacher or room change whose reason changed since the page asked (a colleague's change) is refused with the reason as it now is. Test in Task 1.
5. With the old editor gone: every warning that used to open it ("Fix the timetable", step 9's "Show on step 8") still leads somewhere useful, and the helper's ways and the typed request still apply their changes and their previews. Browser checks in Task 6.

---

### Task 1: Teachers, rooms and one lesson's choices from the server

**Files:**
- Modify: `fixes.py`, `draft.py`, `app.py`
- Test: `tests/test_fixes.py`, `tests/test_board.py`, `tests/smoke.py`

**Interfaces:**
- Consumes: `fixes.apply_one`'s `teacher` and `room` kinds, `fixes.judge`, `fixes.Busy`, `fixes._row_key`, `fixes._cards`, `fixes.teacher_options` (its order of teachers), `verify.planned_rows`, `draft._whole`, `draft.fix`, `draft.undo` (batches), `helper.chain`.
- Produces:
  - `draft.board()` gains:
    - on every row of every card (and of every tray card): `key`, the row key string (`verify._kstr(fixes._row_key(row))`);
    - `teachers`: `[dict(dept, teachers=[dict(name, short)])]`: the setup's teachers by home department in the setup's order of departments and of teachers, a last group `dept=""` for teachers with none, and a group `"Not in the setup"` for a teacher named on a lesson and not in the setup (left out when there is none);
    - `rooms`: `[dict(kind, rooms=[name])]`: the setup's venues by kind in the setup's order, and a group `"Not in the setup"` for a room on a lesson and not among the venues (a room that is empty or "TBC" is no room);
    - `day`: one string of `NP` letters per day, `L` where a period is `L` or `A` for any level and `.` elsewhere (the codes of a teacher's or a room's row).
  - `draft.lesson(lesson_id, group=None) -> dict(id, group, key, what, n_lessons, teachers, rooms)` and `GET /api/draft/lesson?id=&group=` (committee only, through `_checked(..., sentences=True)`), for a lesson on the timetable or in the pool; `group` defaults to its first row's.
    - `n_lessons`: how many lesson ids the row's key has on the timetable and in the pool together (what a change of teacher touches).
    - `teachers`: every teacher of the setup, once, `dict(name, short, free, doing, rank)`: `rank` 0 for step 5's teachers of the key, 1 for a teacher already on a lesson of the subject or of its step 3 card, 2 for another teacher of the subject's department (home or second), 3 for everyone else (the order `fixes.teacher_options` uses, kept); `free` true when the teacher is on no other lesson in any period of any lesson of the key that is on the timetable; `doing`: "" when free, else what they teach then, the first such lesson: `"{what} on {day} period {p}"`. Ordered: free ones by rank then the setup's order, then the others by rank then the setup's order. The row's present teachers are in the list like any other.
    - `rooms`: every venue of the setup, once, `dict(room, kind, right, free, holding)`: `right` true when its kind is the kind step 5 asks for (the kind `fixes.room_options` uses) or it is the home room of one of the row's classes; `free` true when it holds fewer lessons than it takes in every period of this lesson (always true for a lesson in the pool); `holding`: "" when free, else `"{what}"` of the first lesson in it then. Ordered: free and right, free and not right, then the rest, each in the setup's order.
    - An id that is neither on the timetable nor in the pool, or a group it has no row of: the existing sentences.
  - `draft._whole`: `force` and `why` are also taken on `teacher` and `room`; `room` also takes `all` (true only when exactly `True`).
  - `draft.fix` for a `room` with `all`: under the lock, one `room` fix for every lesson id of the row's key that has a row of that group (on the timetable and in the pool), stored with one `batch` id so that one undo takes all back; each is judged in turn on the timetable the earlier ones leave; with `force` and `why`, a "no" is kept only when its reason equals `why`; any other "no" or "na" refuses the whole batch with its sentence and nothing is stored. Without `all` a `room` fix is as today.
  - `fixes.judge` for a `teacher` fix with `teachers == []` and a `room` fix with `room == ""`: `ok` (they are never a clash).
  - `fixes.apply_one`: `teacher` with an empty list says `"{name} now has no teacher; it had {old}."`; the other sentences are unchanged.

- [ ] **Step 1: Write the failing tests.**
  - `tests/test_fixes.py`: `test_no_teacher_and_no_room_are_never_a_clash` (judge `ok`; the sentence for no teacher); `test_marks_after_a_teacher_is_taken_away` (`marks` gives `"noteacher"`).
  - `tests/test_board.py`: `test_the_board_lists_teachers_by_department_and_rooms_by_kind` (exact groups for the made-up setup; a teacher and a room named only on a lesson under "Not in the setup"; `day` strings; every card row has `key`); `test_lesson_lists_free_teachers_first_in_the_editors_order` (exact `rank`, `free`, `doing` for a made-up case with one busy step 5 teacher and one free teacher of another department); `test_lesson_lists_free_rooms_of_the_right_kind_first`; `test_lesson_of_a_waiting_lesson` (rooms all free; teachers judged against the key's other lessons); `test_a_change_of_teacher_touches_every_lesson_of_the_key` (`n_lessons` equals the lessons the fix changes; one undo); `test_a_busy_teacher_needs_force_with_the_reason` (refused without; refused with a wrong `why`; kept with the right one, and both cards then have the `"teacher"` mark); `test_room_for_all_the_groups_lessons_is_one_undo` (the batch; a refusal mid-batch stores nothing); `test_none_for_a_teacher_is_critical_and_none_for_a_room_is_a_warning`; `test_the_lesson_route` (200, 400 sentences, 404 with no draft, 401).
- [ ] **Step 2: Run** `.venv/bin/python tests/test_board.py`. Expected: fails (`module 'draft' has no attribute 'lesson'`).
- [ ] **Step 3: Write the code.**
- [ ] **Step 4: Run** every Python test script. Expected: all pass.
- [ ] **Step 5: Commit** `feat(draft): the board's teachers and rooms, one lesson's choices, a forced teacher or room, a room for all the group's lessons`.

### Task 2: Judge "push out" and "put beside" for the one place dropped on

**Files:**
- Modify: `fixes.py`, `draft.py`, `app.py`
- Test: `tests/test_fixes.py`, `tests/test_board.py`, `tests/smoke.py`

**Interfaces:**
- Consumes: `fixes.slots(m, spec, days, lesson_id, pool, extras)`, `fixes.judge`.
- Produces:
  - `fixes.slots(..., extras="who")`: each slot has its stage 2 keys (`d, p, state, why, swap, also`) and `there`: `None` where no other lesson of the lesson's classes is, else the list `[dict(id, what, classes, groups)]` of the lessons there (as `push.out` listed them). No `push`, no `beside`. For a lesson in the pool the slot's `state` and `why` are those of the plain place where `there` is `None`, and `"na"`, `"Another lesson is there."` where it is not. `extras=True` and `extras=False` answer as before.
  - `fixes.place(m, spec, days, lesson_id, d, p, pool=()) -> dict(d, p, state, why, swap, also, push, beside)`: the one slot at that place with everything stage 3's `slots(extras=True)` gave it; `ValueError` with the existing sentence for an unknown lesson.
  - `draft.slots(lesson_id)` answers with `extras="who"`; `draft.place(lesson_id, d, p)` and `GET /api/draft/place?id=&d=&p=` (committee only) answer `fixes.place` (400 with "Say which place." when `d` or `p` is not a whole number).
- [ ] **Step 1: Write the failing tests**: for thirty lessons of the test's made-up draft, at every place with a lesson there, `fixes.place(...)` equals the slot `fixes.slots(..., extras=True)` gives, key for key, and the `"who"` slots' `there` equals that slot's `push.out`; the `"who"` slots' other keys equal `extras=False`'s for a lesson on the timetable; the route's answers and its 400; a timing: on the 2,000-row made-up draft `draft.slots` takes under a third of `extras=True`'s time.
- [ ] **Step 2: Run** `.venv/bin/python tests/test_fixes.py`. Expected: fails (`module 'fixes' has no attribute 'place'`).
- [ ] **Step 3: Write the code.**
- [ ] **Step 4: Run** every Python test script. Expected: all pass.
- [ ] **Step 5: Commit** `perf(fixes): where a lesson fits says who is at each place; a push and a place beside are judged for the place dropped on`.

### Task 3: Rows of any kind, and a lesson's choices, as plain functions

**Files:**
- Modify: `static/board.js`
- Test: `tests/board.test.js`

**Interfaces:**
- Consumes: the board payload with Task 1's `teachers`, `rooms`, `day` and each row's `key`; the lesson answer of Task 1; the `"who"` slots and the place answer of Task 2.
- Produces:
  - A mode gains `by`: `"class"` (default, as today), `"teacher"` or `"room"`: `{kind: "day", d, by}` and `{kind: "cycle", by, name}` (a class mode keeps `cls` as well, so today's callers work).
  - `Board.groups(board, mode, weeks)`:
    - `by: "teacher"`, day: a first group `""` with one row `"No teacher"` (key `""`) when a card of the day has a row with no teacher; then a group per entry of `board.teachers` (`name` the department, `"No department"` for `""`), a row per teacher: `key` and `label` the name, `codes` `board.day[d]`, `cards` the day's cards with a row whose `teachers` hold the name. A row has `by: "teacher"`, `name`, and `cls: ""`.
    - `by: "room"`: the same with `board.rooms` (group `name` the kind), the row `"No room"`, and a card in a room's row when a row of it has that room.
    - cycle: a row per day for that teacher or room, grouped by week, as for a class.
    - A card is in a row once however many of its rows match.
  - `Board.of(card, row) -> [row of the card]`: the card's rows that put it in this board row (for a class row: all of them).
  - `Board.lines(card, board, row)`: for a class row as today; for a teacher row: title the subject's short name (the band's name for a band), lines `[its classes joined by ", " (at most three, then "+N"), the room of the matching row or "No room"]`; for a room row: `[classes, the matching row's teachers' short names or "No teacher"]`.
  - `Board.onRow(card, row, board)`: on a teacher or room row always true (a drop on its own row changes the time, on another row hands it over); class rows as today.
  - `Board.hand(card, from, to, board) -> fix | null`: `from` and `to` are rows of the same kind (not class). `null` when they are the same row. Teacher: for the first row of `Board.of(card, from)`: `{kind: "teacher", key: thatRow.key, teachers: its teachers with from.name replaced by to.name}` (from the "No teacher" row: its teachers plus `to.name`; onto the "No teacher" row: its teachers without `from.name`); a `to.name` already among them gives `null`. Room: `{kind: "room", id: card.id, group: thatRow.group, room: to.name}` (`""` onto "No room").
  - `Board.handText(card, from, to, n) -> string`: `"Give {what} to {to} in place of {from}? It changes {n} lesson(s) of {key's name}."` (`"Give {what} to {to}?"` from the "No teacher" row; `"Take {from} off {what}?"` onto it); for a room `"Move {what} to {to}?"` / `"Leave {what} with no room?"`.
  - `Board.states(card, slots, d, NP)`: `"ask"` where `slot.there` is a list (a `"who"` slot); the rest as today (a slot with `push` still works).
  - `Board.asks(slot)`, `Board.question(card, slot, board)`, `Board.fix(card, slot, how)`: unchanged, and work on the slot `GET /api/draft/place` answers.
  - `Board.people(lesson) -> {free: [...], busy: [...]}` and `Board.venues(lesson) -> {right: [...], other: [...], busy: [...]}`: the lesson answer's lists split for drawing, in the server's order.
  - `Board.teacherFix(lesson, row, i, name) -> fix`: the `teacher` fix that puts `name` in place of the row's `i`th teacher (`""` takes that teacher away; `i` equal to the number of teachers adds one); `Board.roomFix(lesson, row, room, all) -> fix`.
- [ ] **Step 1: Write the failing tests** in `tests/board.test.js`, one per function, with exact values: a board of two departments and two kinds of room; a lesson with two teachers on both rows; the "No teacher" and "No room" rows present and absent; `hand` for a plain lesson, for a lesson with two teachers, for one group of a band, from and onto the "No teacher" row, onto a teacher already on it (`null`), for a room and "No room"; `handText` for each; `states` with `there`; `teacherFix` replacing, taking away and adding; `roomFix` with and without `all`.
- [ ] **Step 2: Run** `node tests/board.test.js`. Expected: fails (`Board.hand is not a function`).
- [ ] **Step 3: Write the code.**
- [ ] **Step 4: Run** `for f in tests/*.test.js; do node "$f" || break; done`. Expected: every file passes.
- [ ] **Step 5: Commit** `feat(board): rows by teacher and by room, handing a lesson over, and a lesson's choices as plain functions`.

### Task 4: Rows by teacher and by room on the page, and the drop that asks

**Files:**
- Modify: `static/app.js`, `static/style.css`

**Interfaces:**
- Consumes: Tasks 1 to 3; the board's page code as stage 3 left it.
- Produces, for Tasks 5 and 6: `S.board.mode.by`; `bdPlace(card, d, p)` (fetches `GET /api/draft/place` and returns the slot, or null with the server's sentence said); the line's question mechanism able to ask a yes or no ("Give it anyway?").

- [ ] **Step 1: The switch.** Above the day tabs: "Rows:" and three buttons, Classes, Teachers, Rooms, the chosen one marked. It keeps the day; it closes the selection; it survives a redraw and a fetch and is forgotten when the step is left. In the Teachers and Rooms views a group's header folds as a level's does; a row's label opens that teacher's or room's whole cycle, and "All teachers" / "All rooms" goes back.
- [ ] **Step 2: The rows.** Drawn with `Board.groups` and `Board.lines(card, board, row)`; marks, badges, Find, the counters' stepping (which switches to Classes rows first), the strip and the dashed swap outlines as on class rows. The strip of a teacher's or a room's row shows the selected card's places on that row's day, as its class's row would.
- [ ] **Step 3: A drop on a blue place.** With Task 2's slots a place with another lesson is blue and not yet judged: a click or a drop there fetches `bdPlace`, then goes on as stage 3 did with that slot (the question with Swap, Put it beside, Push out as offered; the refusal when none is). While it is fetched the line says "Working out what can be done there…" and the board takes no other change.
- [ ] **Step 4: Along the row, and onto another.** On a teacher's or a room's row a drop on its own row changes the time exactly as on a class row. A drop on another row of the same kind asks `Board.handText` (the count from `GET /api/draft/lesson`'s `n_lessons`) with "Yes" and "Cancel"; "Yes" posts `Board.hand`'s fix; when the server refuses because that teacher or room is busy then, the line shows its sentence and asks "Give it anyway?" with "Yes, give it" and "Cancel", and "Yes, give it" posts the same fix with `force` and that sentence as `why`. When the drop is also on another period, the time is changed first (as a drop on its own row would, its question included) and the hand-over is asked after it; both are one entry for Undo when both are made (the two fixes posted together as a batch through `POST /api/draft/fixes` when neither needs forcing, else one after the other and the page says "Two changes were made; undo each").
- [ ] **Step 5: Check.** `node --check static/app.js`; every `tests/*.test.js`. In the browser with real pointer actions at the pane's own size: Teachers rows show departments and each teacher's day; a lesson with two teachers is on both rows; Rooms rows by kind; a teacher's name opens the cycle and "All teachers" goes back to the same day; a card dragged along a teacher's row changes its time; a card dragged to a free teacher's row asks with the count and, on Yes, every lesson of that class and subject is that teacher's (look at another day), and one Undo takes it back; a card dragged to a busy teacher's row says who is busy and "Give it anyway?", and Yes marks both lessons red and the counter counts them; a card dragged to another room's row moves it; a drop on a blue place on a class row still asks its question (now fetched); the console has no new error.
- [ ] **Step 6: Commit** `feat(board): rows by teacher and by room; a lesson handed to another teacher or room by a drop`.

### Task 5: The lesson in the panel: its teachers, its room, its groups

**Files:**
- Modify: `static/app.js`, `static/style.css`

**Interfaces:**
- Consumes: `GET /api/draft/lesson`; `Board.people`, `Board.venues`, `Board.teacherFix`, `Board.roomFix`; Task 4's yes-or-no question; the panel's tabs.

- [ ] **Step 1: The tab.** The panel gains a fourth tab, "Lesson", shown only while a card on the board or in the tray is selected. A click that selects a card opens it; a selection made by pressing a card to drag it does not change the tab; closing the selection goes back to the tab that was open before.
- [ ] **Step 2: What it shows.** The lesson's name and where it is (or "Not placed"); its warnings (stage 3's lines); then for a plain lesson its lists, for a band a block per group (the group's code, its subject) with that group's lists, the block of the row the card was clicked on first when the rows are by teacher or by room.
  - "Teacher": one list for each teacher the row has, and one more headed "Add a teacher" (the only one when it has none). A list offers, in order: "None" (in a list that holds a teacher), "Free then" with `Board.people(...).free`, then "Busy then" with the others, each busy one followed by what they teach then. Under the lists: "A change of teacher changes all {n} lessons of {key's name}."
  - "Room": one list: "None", "Free, the right kind", "Free, another kind", "In use then" (each followed by what is in it), and the tick box "all this group's lessons".
- [ ] **Step 3: Choosing.** A choice posts `Board.teacherFix` or `Board.roomFix` at once when the teacher or room is free; for a busy one the line asks "{name} is teaching {doing}. Give it anyway?" (for a room "{room} holds {holding} then. Use it anyway?"), and on yes posts it and, when the server refuses with a reason, asks once more with the server's sentence and posts with `force` and that `why`. "None" for a teacher asks "Leave {what} with no teacher? It cannot be published until it has one." A refusal says the server's sentence. After a change the lesson stays selected and its lists are fetched again.
- [ ] **Step 4:** The line's "Teacher, room and more" button goes. The line keeps the lesson's sentence, "Lift out", "Delete this lesson" and "Close".
- [ ] **Step 5: Check.** `node --check static/app.js`; every `tests/*.test.js`. In the browser with real pointer actions: selecting a lesson opens "Lesson" with free teachers first; picking a free teacher changes every lesson of that class and subject and says the fix's sentence; picking a busy one asks, and yes marks both; "None" for the teacher makes the card red "No teacher" and the counter 1, and step 9 refuses to publish; picking a teacher again clears it; a room picked for one lesson, then with the tick box for all the group's lessons, and one Undo for the latter; "None" for the room gives the amber "No room"; a band shows its groups, and changing one group's teacher leaves the others; a lesson in the tray can be given a teacher and a room; the rows do not move at any point; the console has no new error.
- [ ] **Step 6: Commit** `feat(board): a lesson's teachers and room are changed in the panel, with none; a band opens to its groups`.

### Task 6: The helper and the typed request in the panel; the old editor removed

**Files:**
- Modify: `static/app.js`, `static/style.css`, `static/grid.js` (only if a function there is left unused), `README.md`
- Test: `tests/grid.test.js` (only for what is removed)

**Interfaces:**
- Consumes: `GET /api/draft/suggest?key=`, `POST /api/draft/preview`, `POST /api/draft/fixes`, `POST /api/draft/ask` as they are; the page's `fxWaysHTML`, `fxSugHTML`, `fxPreHTML`, `fxSmallHTML`, `fxAskHTML`, `fxWays`, `fxPreview`, `fxApply`, `fxAsk`, `fxSuggestion`, `fxAfter`.

- [ ] **Step 1: Ways to settle a warning.** In the Warnings tab a warning the helper can work on has "Ways to settle this" (in place of "Fix the timetable"). It opens, under that warning, what the old editor showed: the ways, each with its dot, its sentence, what it disturbs and "Preview" / "Apply"; "The app has no suggestion for this one" and its blocked list as today. One warning's ways are open at a time. "Preview" shows "Before you apply" under the way: its sentences and the small before-and-after grids of the classes it changes, as today. "Apply" makes the change through the existing route; the board and the panel then show it, and the warning follows as it did (settled, changed, or still there).
- [ ] **Step 2: Asking in words.** At the foot of the Warnings tab, when typed requests are set up on the server: the box and its button, and under it the answer as today (the reading of the request, the choices to settle, the ways with Preview and Apply). The box keeps its focus and caret across a redraw.
- [ ] **Step 3: Remove the old editor.** The one-class grid (`#fxBox`, `table.fxgrid` as an editor, the lists of moves, teachers, rooms, the add list and the delete of the old card, `fxOpen`, `fxRefresh`, `fxOptions`, `fxSelect`, `fxGo`, `fxFix`, `fxOpenFirst`, the block `#bdOld`) is removed with its handlers and styles; what the helper's preview needs to draw its small grids stays. `GET /api/draft/grid` and `GET /api/draft/options` stay on the server (the preview and the "Step 5 asks for these" list use them). Nothing on the page is left that looks for a removed element.
- [ ] **Step 4: Where things lead now.** A warning's "Show me" (stage 3) is the way to its lesson; a teacher-clash line's "Show me" switches to Teachers rows, that teacher's day, with the lessons marked; step 9's "Show on step 8" and "Find it on step 8" do the same as "Show me". A warning about a class or a teacher with no lesson to show opens that class's or teacher's whole cycle.
- [ ] **Step 5: README.** The paragraph on step 8: rows by class, teacher or room; a lesson's teacher and room changed in the panel or by a drop on another row, with none; the ways to settle a warning and the typed request in the Warnings tab; no other editor.
- [ ] **Step 6: Check.** `node --check static/app.js`; every `tests/*.test.js`; `.venv/bin/python tests/smoke.py`. In the browser with real pointer actions on a made-up draft with a teacher in two places (the controller names it): the clash's "Show me" opens Teachers rows on that teacher with both lessons red; "Ways to settle this" lists ways; "Preview" shows the small grids; "Apply" settles it, the board shows the move and the counters go down; a warning with no way says so; step 8 has no card or block other than the upload card and the timetable card; step 9's "Show on step 8" lands on the lesson; a grep of `static/app.js` and `static/style.css` finds none of the removed names; the console has no new error.
- [ ] **Step 7: Commit** `feat(board): the helper's ways and the typed request are in the Warnings tab; the old one-class editor is removed`.

## After the tasks

- The controller counts and times on the real returned timetables (counts and timings only): the teachers' and rooms' rows against the setup (every teacher and room once; every card on at least one teacher row or "No teacher", one room row or "No room"); `draft.slots` against stage 2's 0.06 s; `draft.lesson`; a forced teacher change and a room change for all a group's lessons, each undone, with the lesson rows counted before and after.
- Notes go in `docs/superpowers/plans/2026-11-17-upload-and-edit-stage-4-notes.md`.

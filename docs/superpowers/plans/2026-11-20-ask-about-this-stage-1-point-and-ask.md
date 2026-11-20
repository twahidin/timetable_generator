# Ask about this, stage 1: point at a lesson or an empty period and get checked options, without AI. Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** On step 8's board the committee lead right-clicks a lesson, a band or an empty period (or selects it and presses Ask); an "Ask" tab opens in the panel beside the board with starter questions; the app answers each at once with a list of checked options (swap, move, give to another teacher, trade classes with another teacher, another room, fill the empty period), each with Preview, Apply or "Apply anyway", and options go stale when the timetable changes.

**Architecture:** Nothing new is stored except one new kind of change, the `trade` (two teachers exchange two classes), which is a fix like the others: applied by `fixes.apply_one`, judged by `fixes.judge` on the timetable it leaves, worded once, undone by Undo. A new read-only module `ask.py` holds the look-ups; every option it returns has been judged by `fixes.judge` (one change) or `helper.chain` (two) and worded by `helper.py`. One route, `GET /api/draft/about`, serves them. The page gains `static/ask.js` (plain functions, tested under Node) and an Ask tab in the board's side panel. Apply goes through today's `/api/draft/fix` and `/api/draft/fixes`, which gain a `stamp` so a change made for a timetable that has moved on is refused. No model is called anywhere in this stage.

**Tech Stack:** Flask (`app.py`, `draft.py`, `fixes.py`, `helper.py`, new `ask.py`), vanilla JS (`static/app.js`, `static/board.js`, new `static/ask.js`), `static/style.css`, plain-script tests. No new dependency.

**Spec:** `docs/superpowers/specs/2026-11-20-ask-about-this-design.md` (stage 1 of "Suggested order of building"). Background: `docs/superpowers/specs/2026-11-16-upload-and-edit-design.md` and the notes of its four stages in `docs/superpowers/plans/`.

**Branch:** `timetable-view-helper` in the worktree `~/Developer/tt-generator/tt-timetable-view` (cut from `origin/main` b50d16e; the design is commit ac7bb46). Python: `~/Developer/tt-generator/timetable_generator/.venv/bin/python` (written `PY` below).

## Global Constraints

- "The chat never changes the timetable. Only Apply does, pressed by a person." In this stage: no look-up writes anything; only `/api/draft/fix`, `/api/draft/fixes` and `/api/draft/undo` change the draft.
- "Every option shown anywhere in the Ask tab has been through this [the check], at the moment it is shown and again at Apply." An option's verdict and wording come from `fixes.judge`, `helper.chain`, `helper.say` and `helper.disturbs`, never from the page.
- Three verdicts, the board's own: clean (`ok`), bends a rule (`prefer`), lands with a problem (`no`). A change judged `na` is never an option.
- "An option that lands with a problem has Apply anyway in place of Apply. It asks first, with the problem's sentence … It is offered for the kinds of change the board itself can force: a move, a place, an add, a change of teacher, a change of room. A swap, a trade and two changes together are never forced": such an option is listed with its reason and no Apply.
- "A change of teacher is for all that class's (or group's) lessons of the subject … and so is each half of a trade; the option says how many lessons."
- "A trade is judged on the timetable it leaves, not one half at a time." "A trade is one change: one line in the Changes list, one Undo."
- "When the timetable changes … the options already on screen are struck through ('The timetable changed. Ask again.') and cannot be applied. The server checks this too."
- "Selecting cards while working does not change what the Ask tab is about; only pointing with Ask does."
- A lesson never vanishes; a band is never torn; a draft from before this stage opens as it did, with its fixes. `ttgen/` is not changed.
- The board is no slower to open, drag on or redraw. A look-up answers in under half a second on a timetable of the school's size (about 1,950 lesson rows, 90 teachers, 73 rooms, 260 places).
- Made-up names only; the school is only ever "CTSS" or "the school". New sentences are plain, with no em-dash and no arrow. No test or check calls a model API (`TYPED_REQUEST_MODEL=mock` or no key). Never run `git stash` in any form, nor `git checkout -- <file>`. Commit trailer: `Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>`.
- Every browser check of a click, a right-click, a drag or a key is made with real pointer and key actions at the pane's own size, and the report says for each which kind it was. After a block replace in `static/app.js`, list the names the old block defined and grep that each is still defined or unused, and re-try every control of the board, old ones included.

## Decisions this plan makes (for the committee lead to check)

1. The Ask tab appears in the panel only once something has been pointed at, as the Lesson tab appears only while a lesson is selected.
2. An answer shows at most 8 options, the best first (fewer lessons moved, clean before bending, the same day first, a teacher's load against the allowance), then "and N more".
3. "Who else could teach it?" replaces the teacher whose row was clicked on Teachers rows, else the lesson's first teacher; the option says "in place of". Free teachers come first; up to 4 busy ones follow, each with "Apply anyway".
4. "Who could I trade this class with?" looks at teachers who already teach the subject (or another subject on the same step 3 card) or are in its department, and at their classes of that subject or card. It stops after 40 trades judged and says so.
5. "What can go here?" lists only lessons that would start at that period. The period must be empty for every class of the lesson.
6. An empty period is pointed at only where the row has no lesson then. A period with a lesson is asked about through its card.
7. A click on an empty period with no lesson selected now selects that place (it is outlined, and the line names it with Ask and Close). Escape clears it.
8. A trade's sentence: "Adam Lee and Chen Wei traded: Adam Lee now teaches 2C Mathematics, Chen Wei 2A Mathematics."

## Review Focus

1. A trade of two classes that meet at the same time: judged clean when the end state is clean (two changes of teacher in a row would be refused). A teacher who teaches only some of a class's lessons of the subject: only those lessons change hands. Tests in Task 1.
2. An Apply pressed after a colleague's change: refused by the server with "The timetable changed. Ask again.", nothing written. An "Apply anyway" whose reason has changed: refused with the reason as it now is. Tests in Task 2.
3. A band: a time option moves every group; a teacher or room option changes one group and leaves the others; on a class's row the lead picks the group. Tests in Tasks 3 and 5.
4. An empty period that a two-period lesson would overrun into a break, the end of the day, or another lesson of one of its classes: not offered. A lesson waiting in Not placed is offered as a place, never as a move. Tests in Task 4.
5. A teacher, a room or a class that only a lesson names (not in the setup), a lesson with no teacher, a lesson with no rows, the "No teacher" and "No room" rows: every look-up answers in words and never with an error page. Tests in Tasks 3 and 4.

---

### Task 1: The trade, a kind of change

**Files:**
- Modify: `fixes.py` (`KINDS`, `apply_one`, `judge`), `draft.py` (`FIELDS`), `helper.py` (`_own`, `say`, `disturbs`)
- Test: `tests/test_fixes.py`, `tests/test_helper.py`, `tests/test_board.py`

**Interfaces:**
- Consumes: `fixes._key`, `fixes.rows_of_key`, `fixes._names`, `verify._name`, the generic before-and-after machinery of `fixes.judge`.
- Produces: the fix `dict(kind="trade", a=<key string>, b=<key string>, x=<teacher name>, y=<teacher name>)`: on the rows of key `a` that have `x`, `y` takes `x`'s place in the row's teacher list; on the rows of key `b` that have `y`, `x` takes `y`'s place. Other teachers of a row stay where they are. Accepted by `fixes.apply_one`, `fixes.judge`, `draft.fix` (never forced: `trade` is not in `draft.FORCED`), `draft.fix_many`, `helper.chain`, `helper.say`, `helper.disturbs`.

- [ ] **Step 1: Write the failing tests** in `tests/test_fixes.py`, on a model built as that file builds its others (two classes `A`, `B` of one level, one subject, teachers `T1` on `A`, `T2` on `B`):
  - `trade_applies`: after `apply_one`, every `A` row has `T2` and every `B` row has `T1`; the sentence is exactly `"T1 and T2 traded: T1 now teaches <name of b>, T2 <name of a>."` with the names `verify._name` gives; `touched` holds every lesson id of both keys; `was` holds every row as it was.
  - `trade_end_state`: `A` and `B` have a lesson at the same day and period. `judge` of the trade is `ok`. `helper.chain` of the two `teacher` fixes in either order is `no` (this pins why the kind exists).
  - `trade_clash`: `T2` also teaches a third class `C` at a time `A` meets: the trade is `no` and `why` is the sentence `Busy` gives for `T2`.
  - `trade_partial`: `T1` is on only two of `A`'s three lessons (a second teacher `T3` has the third): after the trade `T3`'s lesson is unchanged and `touched` does not hold it.
  - `trade_two_teachers`: a row of `A` taught by `[T1, T4]` becomes `[T2, T4]`.
  - `trade_refused` (each is `ValueError` from `apply_one` and `na` from `judge`, with these sentences): `a == b` or `x == y`: "That changes nothing."; `x` on no row of `a`: "T1 does not teach <name of a>."; `y` already on a row of `a`, or `x` on a row of `b`: "T2 already teaches <name of a>."; a name not on the setup's list: the `teacher` kind's own sentence; no lesson of a key: the `teacher` kind's own sentence.
  - `trade_load`: a trade that takes `T2` over the allowance is `prefer` with the `teacher` kind's allowance sentence.
  - `trade_pool`: a lesson of `A` waiting in the pool changes hands with the rest (as the `teacher` kind reaches the pool).
- [ ] **Step 2: Run** `PY tests/test_fixes.py`. Expected: fails at `trade_applies` ("This kind of fix is not known.").
- [ ] **Step 3: Implement** in `fixes.py`: add `"trade"` to `KINDS`; a `trade` branch in `apply_one` (check everything before changing anything, as every kind does); in `judge` take `ids` as the lesson ids of both keys on the timetable and in the pool, and add `"trade"` to the kinds whose teacher loads are compared. Nothing else in `judge` changes: its in-place comparison already ignores the lessons the fix changes and then checks them against each other as they are after it.
- [ ] **Step 4: Run** `PY tests/test_fixes.py`. Expected: passes, with the count of cases it prints up by 8.
- [ ] **Step 5: Tests for the draft and the helper.** `tests/test_board.py`: `draft.FIELDS["trade"] == ("a", "b", "x", "y")`; `POST /api/draft/fix` with a trade writes one fix whose `text` is the sentence above, `GET /api/draft` lists it under `fixes` with `kind == "trade"`, one `POST /api/draft/undo` takes it back; the same body with `force: true` and a `why` on a trade judged `no` is still refused with the judgement's sentence. After the trade the last of `draft.model_now()[2]["texts"]` is that sentence (it is what the published timetable's record of changes is written from). `tests/test_helper.py`: `helper.say` of a trade is `"Trade classes: T1 takes <name of b>, T2 takes <name of a>."`; `helper.disturbs` gives one sentence per teacher whose periods change ("T1 drops to 20 periods." / "T2 rises to 26 periods."), and "Nothing else moves." when the two classes have the same periods.
- [ ] **Step 6: Implement** `FIELDS`, `helper._own` (the ids of both keys), `helper.say`, `helper.disturbs`. Run `PY tests/test_board.py`, `PY tests/test_helper.py`, `PY tests/smoke.py`. Expected: all pass.
- [ ] **Step 7: Commit** `feat(step 8): a trade of two classes between two teachers, as one change`.

### Task 2: A stamp on the draft, and a preview of any one change

**Files:**
- Modify: `draft.py` (`_build`, `fix`, `fix_many`, `preview`, new `stamp`), `app.py` (`/api/draft/fix`, `/api/draft/fixes`)
- Test: `tests/test_board.py`

**Interfaces:**
- Produces:
  - `draft.stamp(meta=None, rec=None) -> str`: 12 hex characters of a SHA-1 over the JSON of `[upload_id, uploaded_at, [[f.get("at"), f.get("text")] for f in fixes], setup version]`. `GET /api/draft` (`draft.info()`) gains `stamp`.
  - `draft.fix(move, stamp=None)` and `draft.fix_many(moves, stamp=None)`: with a stamp that is not the draft's, under the lock and before anything is judged, `ValueError(draft.MOVED)` where `MOVED = "The timetable changed. Ask again."`. The routes pass `body.get("stamp")` when it is a string. Without a stamp both behave exactly as today.
  - `draft.preview(moves)`: one fix of any kind the board makes, including `place` and `trade`, judged with the pool; when it is judged `no` the answer still shows the timetable with the change made (`state == "no"`, `why` its sentence); `na` shows nothing changed, as today. Two fixes: as today.

- [ ] **Step 1: Write the failing tests** in `tests/test_board.py`:
  - `stamp_moves`: the stamp is the same on two reads; it differs after a fix; after the undo it differs from the stamp just before the undo; it differs after a new upload of the same files.
  - `stamp_refuses`: `POST /api/draft/fix` with the stamp read before another fix was made answers 400 with `MOVED` and the fixes list is unchanged; the same for `/api/draft/fixes`; with the current stamp both succeed; with no stamp both succeed.
  - `preview_place`: a lesson lifted into Not placed, previewed as a `place`: `state` `ok`, the lesson is in its class's week with `mark == "moved"`.
  - `preview_no`: a move onto a teacher clash: `state == "no"`, `why` the clash sentence, and the lesson is shown at the new place.
  - `preview_trade`: both classes' weeks come back, the lessons marked `changed`.
- [ ] **Step 2: Run** `PY tests/test_board.py`. Expected: fails at `stamp_moves`.
- [ ] **Step 3: Implement.** For one fix, `preview` judges with `fixes.judge(..., pool=pool)` and applies with `fixes.apply_one` on deep copies of the lessons and the pool; it does not go through `_fixes_of` (which refuses `place`) for that case, but cuts the fix with `_whole` as `fix` does.
- [ ] **Step 4: Run** `PY tests/test_board.py`, `PY tests/test_helper.py`, `PY tests/smoke.py`. Expected: all pass; the helper's existing previews are unchanged.
- [ ] **Step 5: Commit** `feat(step 8): a stamp on the draft; preview covers a place, a trade and a change that lands with a problem`.

### Task 3: Look-ups about a lesson

**Files:**
- Create: `ask.py`
- Test: `tests/test_ask.py` (new, in the manner of `tests/test_board.py`: the sample primary school, a made-up Lessons workbook, the app's test client)

**Interfaces:**
- Consumes: `fixes.slots(extras=False)`, `fixes.choices`, `fixes.judge`, `fixes._ctx`, `fixes._row_key`, `fixes.what`, `fixes.when`, `fixes.named`, `helper.say`, `helper.disturbs`, `helper.chain`, `helper.rank`, `typed._Step5` and `typed.STEP5` (the sentence for a new difference from step 5), `draft.FORCED`, `spec.teacher_depts`.
- Produces, all read-only, all taking `(m, spec, days, pool, ...)`:
  - A **subject** is `dict(kind="lesson", id=int, group=str|None, teacher=str|None)` or `dict(kind="place", by="class"|"teacher"|"room", name=str, d=int, p=int)`. `ask.subject(m, pool, raw) -> dict` returns it cleaned or raises `ValueError(sentence)`: "There is no lesson with that id on the timetable.", "There is no row of {group} in that lesson.", "That is outside the day.", "There is no class called {name}." (and teacher, room; the names "" of the "No teacher" and "No room" rows are refused with "Pick a teacher's row." / "Pick a room's row.").
  - An **option** is `dict(fixes=[fix, ...], text=str, disturbs=[str], state="ok"|"prefer"|"no", why=str, apply="yes"|"anyway"|"none")`. `ask.check(m, spec, days, pool, fixes, ctx=None, extra=()) -> option | None`: one fix is judged by `fixes.judge` with the pool, two by `helper.chain`; `None` when the judgement is `na`, when `fixes` is empty or longer than two, or when two fixes hold a `place` or a `lift`. `text` is `ask.say` (below) of each fix joined as `helper.says` joins them; `disturbs` is `helper.disturbs` plus `extra`, plus `typed.STEP5` when the change gives a difference from step 5 the timetable did not have. `apply` is `"yes"` for `ok` and `prefer`; `"anyway"` for `no` when there is one fix and its kind is `move`, `place`, `add`, `teacher` or `room`; else `"none"`.
  - `ask.say(m, spec, days, pool, fix) -> str`: `helper.say`, and for a `place`: "Place {what} on {day} period {p}."
  - An **answer** is `dict(title=str, text=str, lines=[str], options=[option], more=int, stopped=bool)`; `more` counts options left out past `ask.MOST = 8`.
  - `ask.here(m, spec, days, pool, sub) -> dict(title, lines)` (the open warnings on the lesson are not in it: the page already has them and shows them itself; stage 2 adds them here for the AI). A lesson's title: "{what} · {day} period {p}" ("periods {p} to {q}" for a longer one, "Not placed" for one in the pool); a band's: "the {band} band · …" and one line a group ("group {g}: {subject}, {teachers or 'no teacher'}, {room or 'no room'}"). A place's: "{name} · {day} period {p} · empty".
  - `ask.swaps(…, sub) -> answer`: every slot of `fixes.slots` with a swap, as a `swap` option. Text: "This lesson can swap with N lessons." / "Nothing can swap with this lesson." (a lesson in the pool: "A lesson that is not placed cannot be swapped. Ask where it can go."). Order: `apply` yes before none, then `helper.rank`.
  - `ask.moves(…, sub) -> answer`: every slot without a swap judged `ok` or `prefer`, as a `move` (or a `place` for a lesson in the pool); when fewer than three, up to three judged `no` after them, nearest day first. Slots judged `na` (another lesson is there, a break) are never options.
  - `ask.teachers(…, sub) -> answer`: from `fixes.choices` for the subject's group (default the lesson's first row). The teacher replaced is `sub["teacher"]` when that teacher is on the row, else the row's first; with none on the row the option adds one. Free teachers in `choices`' order, each as a `teacher` fix through `check`, with `extra` saying "{department or departments} · {periods now} to {after} of {allowance} periods" and, from the second lesson on, "It changes all N lessons of {name}."; then up to `ask.BUSY = 4` busy teachers with their `doing`. Each option also carries `who=dict(name, depts, subjects, free, doing, rank, load, after, allowance)` (stage 2 reads it); `subjects` is the subjects of step 5's lesson rows that name the teacher.
  - `ask.rooms(…, sub) -> answer`: from `fixes.choices`' rooms: free and right, then free and another kind, as `room` options for this one lesson; then up to 4 in use, with "It holds {holding} then." in `disturbs`.
- Rules for all four: a subject that is a place raises `ValueError("Point at a lesson for this.")`; a lesson with no teacher, a teacher or room not in the setup, and a lesson with no rows answer with text and no options, never with an exception other than `ValueError`.

- [ ] **Step 1: Write the failing tests** in `tests/test_ask.py`. The fixture: classes `A`, `B`; lessons so that (1) lesson 1 of `A` has one same-length lesson of `A` it can swap with cleanly and one whose swap is a teacher clash; (2) a two-class band of three groups; (3) a lesson lifted into the pool; (4) a lesson with no teacher; (5) a lesson naming a teacher not in the setup. Cases:
  - `subject_clean` and `subject_refused`: each sentence above.
  - `check_one`: an `ok` move gives `apply == "yes"` and `text == helper.say(...)`; a move onto a teacher clash gives `state == "no"`, `apply == "anyway"`, `why` the judgement's sentence; a swap judged `no` gives `apply == "none"`; a trade judged `no` gives `apply == "none"`; a move to a break gives `None`.
  - `check_two`: two clean moves give one option with both fixes and `apply == "yes"`; when the second is `no` the option is `state == "no"`, `apply == "none"`; a list with a `place` in it gives `None`; three fixes give `None`.
  - `check_is_the_board`: for every option of `swaps` and `moves` of lesson 1, `draft.fix` (or forced with `why`, for `anyway`) of its fix succeeds and the stored text is what `fixes.apply_one` gives; undone after each. This pins "an Apply does what its option says".
  - `swaps_lists`: the clean swap first with `apply == "yes"`, the clashing one after with `apply == "none"`; the text counts both.
  - `moves_pool`: the lifted lesson's options are all `place` fixes.
  - `moves_band`: an option for the band moves all three groups (the fix is one `move` of the band's id) and `disturbs` names the other classes.
  - `teachers_one_group`: asked with `group` of the band's second group, the option's fix key is that group's and no other group's teachers change when it is applied.
  - `teachers_replace`: on a row of two teachers with `teacher` naming the second, the fix keeps the first and replaces the second.
  - `teachers_none` and `teachers_unknown`: fixtures (4) and (5) answer with options that add or replace, and no exception.
  - `rooms_lists`: free right-kind rooms first; a room in use is `anyway` with its `holding` in `disturbs`.
  - `cap`: with more than 8 candidates `len(options) == 8` and `more` is the rest.
- [ ] **Step 2: Run** `PY tests/test_ask.py`. Expected: fails on import (`No module named 'ask'`).
- [ ] **Step 3: Implement `ask.py`**, sharing one `fixes._ctx(m)` across the options of an answer.
- [ ] **Step 4: Run** `PY tests/test_ask.py`. Expected: passes.
- [ ] **Step 5: Commit** `feat(step 8): look-ups about one lesson: swaps, moves, teachers, rooms, each option judged`.

### Task 4: Trades, filling a period, who is free; the route

**Files:**
- Modify: `ask.py`, `draft.py` (new `about`), `app.py` (new route)
- Test: `tests/test_ask.py`, `tests/smoke.py`

**Interfaces:**
- Consumes: Task 1's `trade` fix; Task 3's `subject`, `check`, `here`, answer shape; `fixes.short`, `fixes.add_room`, `fixes.Busy`, `fixes._cards`, `fixes._on_card`, `fixes._room_kind`, `verify.planned_rows`.
- Produces:
  - `ask.trades(…, sub, other=None) -> answer`: for teacher X of the subject's row (as `teachers` picks) and key A. Candidates Y, in this order: step 5's teachers of the subject, teachers on a lesson of the subject or of another subject of its step 3 card, teachers whose departments include the subject's; with `other`, that teacher alone. For each Y, Y's keys B on the timetable whose subject is A's or on A's card (with `other`: every key of Y). Each `(A, B, X, Y)` not refused outright is judged as a `trade`; `ok` and `prefer` are options (`extra`: "It changes N lessons of {name a} and M of {name b}."), `no` ones follow with `apply == "none"`. Judging stops after `ask.TRADES = 40` and sets `stopped`; the text then ends "Only the first 40 possible trades were checked."
  - `ask.fill(…, sub) -> answer` for a place (a lesson subject raises `ValueError("Point at an empty period for this.")`):
    - by `class`: lessons in the pool with that class, as a `place` at `(d, p)`; entries of `fixes.short` whose step 5 classes include it, as an `add` (room from `fixes.add_room`); lessons of that class elsewhere, as a `move`, with "Leaves {day} period {p} empty." in `disturbs`. A candidate is tried only when periods `p` to `p + n - 1` are inside the day and hold no lesson of any of the lesson's classes.
    - by `teacher`: the same three sources, for lessons that teacher is on (an add: step 5 names the teacher).
    - by `room`: lessons that cover `(d, p)` with no room (or "TBC"), or in a room of another kind than `fixes._room_kind` asks, as a `room` fix to this room.
    - Options judged `ok` or `prefer` only; order: place, add, move, each by `helper.rank`. Text: "N lessons could go here." / "Nothing fits here without a clash or a broken rule."
  - `ask.free(…, sub) -> answer` with no options: for a place, or a lesson (its day, period and length): `lines` one a department ("Mathematics: Bala Nair, Chen Wei") for the teachers on no lesson in those periods, then one a kind for the rooms free then; text "N teachers and M rooms are free on {day} period {p}."
  - `draft.about(q, raw_subject) -> dict(subject, title, stamp, **answer)`; `q` one of `ask.QUESTIONS = ("here", "swaps", "moves", "teachers", "trades", "rooms", "fill", "free")`, else `ValueError("That question is not known.")`.
  - `GET /api/draft/about?q=…&kind=lesson&id=…[&group=…][&teacher=…]` or `…&kind=place&by=…&name=…&d=…&p=…`, committee only, answered through `_checked(..., sentences=True)` as the other draft reads are (400 with the sentence for a `ValueError`, 404 with no draft).

- [ ] **Step 1: Write the failing tests** in `tests/test_ask.py`:
  - `trades_found`: `T1` on `A`, `T2` on `B`, same subject: one option, a `trade`, `apply == "yes"`; applied through `/api/draft/fix` it writes one fix and one undo takes it back.
  - `trades_meet_at_once`: `A` and `B` meet at the same time: the trade is still an option (Review Focus 1).
  - `trades_other`: with `other` a teacher of another department, their keys of any subject are tried.
  - `trades_stopped`: with `ask.TRADES` set to 1 in the test, `stopped` is true and the text says so.
  - `fill_class`: an empty period of `A`: the pooled lesson of `A` first, as a `place`; a step 5 shortfall of `A` as an `add` with a room; a lesson of `A` from another day as a `move` with the "Leaves …" sentence.
  - `fill_overrun` (Review Focus 4): a two-period lesson is not offered at the last period of the day, at the period before a break, or where its second period holds a lesson of one of its classes; a band is not offered where its other class is busy.
  - `fill_teacher` and `fill_room`: as specified; a lesson already in a room of the right kind is not offered.
  - `fill_unknown` (Review Focus 5): an empty period of a class, a teacher and a room that only a lesson names answers with its text and no options.
  - `fill_refuses_lesson`, `free_counts`, `about_unknown_question`.
  - `about_route`: 401 for a client not signed in; 200 with `title`, `stamp`, `options` for a lesson and for a place; 400 with the sentence for a lesson id that is not there and for `by=teacher&name=`; the stamp equals `GET /api/draft`'s.
  - `about_writes_nothing`: the draft's files' bytes are the same before and after one call of every question.
- [ ] **Step 2: Run** `PY tests/test_ask.py`. Expected: fails at `trades_found`.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `PY tests/test_ask.py`, `PY tests/test_board.py`, `PY tests/smoke.py`; add to `tests/smoke.py` one pass of every question on the sample secondary school's solved timetable (the `--full` run), asserting each answers and that every option's fix is accepted by `draft.preview`. Expected: all pass.
- [ ] **Step 5: Commit** `feat(step 8): look-ups for trades, filling a period and who is free; GET /api/draft/about`.

### Task 5: The Ask tab's plain functions

**Files:**
- Create: `static/ask.js` (`var Ask = (function () { … })(); if (typeof module !== "undefined") module.exports = Ask;`, as `static/board.js`)
- Modify: `static/index.html` (line 43 loads `/static/board.js`): load `/static/ask.js` on the next line
- Test: `tests/ask.test.js` (new, as `tests/board.test.js`)

**Interfaces:**
- Consumes: the board payload (`Board` functions `box`, `of`, `onRow`), Task 4's answer shape.
- Produces:
  - `Ask.ofCard(card, from)` -> `{kind: "lesson", id, group, teacher}`: `from` is the row the card was clicked on (`{by, name}`) or null. On a teacher's row: `teacher` that name and `group` the first of the card's rows that has that teacher; on a room's row: `group` the first row in that room; else `group` null.
  - `Ask.ofPlace(at)` -> `{kind: "place", by, name, d, p}` from a place of the board `{cls, by, name, d, p}` (a class row's name is `cls`).
  - `Ask.empty(board, at)` -> true when no card of that row covers period `p` on day `d` (class rows: `Board.onRow`; teacher and room rows: `Board.of(card, row).length`).
  - `Ask.groups(card)` -> `[{group, label}]` for a card with more than one row ("{group} · {subject}"), else `[]`.
  - `Ask.starters(sub, card)` -> `[{q, label}]`: a lesson on the timetable: `swaps` "What can this swap with?", `moves` "Where else can it go?", `teachers` "Who else could teach it?", `trades` "Who could I trade this class with?", `rooms` "Which rooms could it use?"; a lesson not placed: `moves` "Where can it go?", `teachers`, `rooms`; a place: `fill` "What can go here?", `free` "Who is free then?".
  - `Ask.query(sub, q)` -> the query string of `GET /api/draft/about` (every value through `encodeURIComponent`; `group` and `teacher` left out when null).
  - `Ask.verdict(option)` -> `{text, cls}`: `ok` "Clean" `ok`; `prefer` "Bends a rule" `prefer`; `no` "Lands with a problem" `no`.
  - `Ask.send(option, stamp)` -> `{url, body}`: one fix: `/api/draft/fix` with the fix's fields and `stamp`, and with `force: true, why: option.why` when `option.apply === "anyway"`; two: `/api/draft/fixes` with `{fixes, stamp}`. Null when `option.apply === "none"`.
  - `Ask.stale(entry, stamp)` -> true when `entry.stamp !== stamp`.
  - `Ask.target(option)` -> the lesson id "Show on the board" goes to (`id` of a move, place, room; `a` of a swap), or null.

- [ ] **Step 1: Write the failing tests** in `tests/ask.test.js`: one case for each function above with the exact labels and strings; `ofCard` on a band from a teacher's row picks that teacher's group and not the first; `empty` is false under a two-period card's second period and true beside it; `starters` of a lesson in the tray has no `swaps` and no `trades`; `send` of an `anyway` option carries `force` and `why`, of a `none` option is null; `query` escapes a class called `1 A&B`.
- [ ] **Step 2: Run** `node tests/ask.test.js`. Expected: fails (`Cannot find module '../static/ask.js'`).
- [ ] **Step 3: Implement `static/ask.js`.**
- [ ] **Step 4: Run** `node tests/ask.test.js` and `node tests/board.test.js`. Expected: pass.
- [ ] **Step 5: Commit** `feat(step 8): the Ask tab's plain functions`.

### Task 6: Pointing, and the Ask tab with its answers

**Files:**
- Modify: `static/app.js` (the board code, lines 3321 to 4250: `bdEnsure`'s state, `bdSideTab`, `bdSideHTML`, `bdLineHTML`, `BDHINT`, `bdPaint`, `bdClick`, `bdCellClick`, the Escape handler; new functions prefixed `ak`), `static/style.css`
- Test: `node --check static/app.js`; browser checks on a scratch server (see the last step)

**Interfaces:**
- Consumes: `Ask.*` (Task 5), `GET /api/draft/about` (Task 4), `bdQuiet`, `bdCard`, `bdRowData`, `bdPlaceAt`, `bdGoTo`, `bdSideDraw`, `bdLineDraw`, `bdPaint`, `S.draft.stamp` (Task 2).
- Produces (Task 7 builds on these):
  - `S.board.about = { sub, card (its id or null), log: [entry], n }` or null; an entry is `{ sub, title, q, label, got ("loading" | "fail" | the answer), stamp }`. `S.board.place = {cls, by, name, d, p}` or null (the empty period selected).
  - `akOpen(sub)`: sets `about.sub` (keeping the log), shows the tab (`b.side = "ask"`), draws the panel. `akAsk(q)`: pushes a loading entry, fetches, drops an answer whose entry is gone, draws. `akHTML(b)`: the tab. `akOptionHTML(e, i, k)`: one option with `data-ak="{i}.{k}"` on its buttons.
  - Buttons: `data-bdask` (the line's Ask), `data-akq="{q}"` (a starter), `data-akgroup="{group}"` (a band's group chip), `data-akshow="{i}.{k}"` (Show on the board), `data-akclear` (Clear).

- [ ] **Step 1: The state and the tab.** `about` and `place` join the board's state in `bdEnsure`. `bdSideHTML` lists a fifth tab "Ask" while `b.about` is set; `bdSideTab` leaves `b.side === "ask"` alone while it is. The tab: the subject's title (from the first answer's `title`, before that from the card's `what` or the place's row, day and period); under it the lesson's open warnings as the Lesson tab words them (`bdLineWarnings`); for a band pointed at on a class's row, its groups as chips, the chosen one marked (the first until another is chosen; choosing sets `sub.group`); the starters as buttons; then the log, newest last, each entry: its label as a heading (with its subject's title when it differs from the tab's), "Working it out…" while loading, "That could not be worked out. Ask again." on a failure, else `text`, `lines` as a list, the options, "and N more" when `more`; a Clear button when the log is not empty. An option: its text in bold, `disturbs` as a small list, the verdict with the helper's dot (`fxDot`), `why` when the verdict is `no`, and "Show on the board" when `Ask.target` gives a lesson. No Preview or Apply yet. Every string from the server goes through `esc()`.
- [ ] **Step 2: Pointing.**
  - A `contextmenu` listener on `document`: inside `#bdBox` on a `.bdcard` (board or tray, not a "Step 5 asks for these" entry) it calls `preventDefault` and `akOpen(Ask.ofCard(card, row))`; on a `.bdcell` or `.bdmark` where `Ask.empty` is true, `preventDefault` and `akOpen(Ask.ofPlace(at))`; anywhere else, and while a card is in the air or a drop waits, the browser's menu is left alone.
  - `bdCellClick` with no card selected and `Ask.empty` true: `b.place` is that place (a second click on it clears it). `bdPaint` gives its cell the class `psel`. Selecting a card, changing rows, day or cycle, and Escape clear it.
  - `bdLineHTML`: with a place selected and no card, "{row} · {day} period {p} ({time}) · empty", then **Ask** and **Close**; for a selected lesson, **Ask** before "Lift out". `data-bdask` calls `akOpen` for whichever is selected.
  - `BDHINT` gains: " Click a name at the left to see its whole cycle. Right-click a lesson or an empty period, or press Ask, to see what can be done there."
- [ ] **Step 3: Rules to keep.** A click that selects a card still opens the Lesson tab and does not touch `about`. A new board (`bdTake`) keeps `about` and its log; a new upload (`other` in `bdLoad`) clears both, since lesson ids restart. `akAsk` while `FX.busy` toasts `BDWHY.busy`. The typed box's focus (`fxKeep`) and the panel's scroll (`bdSideAt`) behave as before on every redraw.
- [ ] **Step 4: Style** in `static/style.css` next to the `.bdl…` rules: `.ak…` classes for the title, the chips, the starters (wrapping buttons), an entry, an option; `.bdcell.psel` an outline in the accent colour. The five tabs may wrap onto two lines, as four do today.
- [ ] **Step 5: Check.** `node --check static/app.js`; `node tests/ask.test.js`; `node tests/board.test.js`. Then on a scratch server (a temporary launch entry on a scratch data folder with the sample secondary school's solved timetable; the controller names it in the dispatch), with real pointer actions, and say for each which kind it was: right-click a lesson on Classes rows opens the Ask tab with five starters; right-click a band lists its groups; right-click an empty period on a class's, a teacher's and a room's row, on the day board and in a whole cycle; right-click on a period under a card asks about the card; right-click outside the board shows the browser's menu; left click on an empty period selects it and the line's Ask opens the tab; Escape clears; each starter answers; "Show on the board" goes to the lesson; a left click on a card still opens the Lesson tab and leaves the Ask tab's subject; drag a card and drop it (the old controls: day tabs, Rows, Find, counters, Undo, Lift out, Delete, the Lesson tab's lists) all still work.
- [ ] **Step 6: Commit** `feat(step 8): right-click or Ask on a lesson or an empty period; the Ask tab answers`.

### Task 7: Preview, Apply, Apply anyway, and stale answers

**Files:**
- Modify: `static/app.js` (`akOptionHTML`, new `akPreview`, `akApply`, `akPreHTML`; `bdClick`), `static/style.css`
- Test: `node --check static/app.js`; browser checks

**Interfaces:**
- Consumes: `Ask.send`, `Ask.stale`, `bdSend(url, body, card, keep, {stay, note, refused})`, `bdYesNo`, `POST /api/draft/preview` (Task 2), `fxSmallHTML`, `fxDot`, `S.draft.stamp`.
- Produces: buttons `data-akpre="{i}.{k}"`, `data-akapply="{i}.{k}"`, `data-akprecancel`; `S.board.about.pre = { at: "{i}.{k}", got: "loading" | answer }` or null.

- [ ] **Step 1: The buttons.** An option whose entry is not stale shows **Preview**, and **Apply** (`apply === "yes"`), **Apply anyway** (`"anyway"`) or neither (`"none"`, with the line "This one cannot be applied from here." under its reason). A stale entry (`Ask.stale(entry, S.draft.stamp)`) is drawn struck through with "The timetable changed. Ask again." and no buttons but its starter's own (pressing the entry's heading asks it again).
- [ ] **Step 2: Preview.** Posts the option's fixes to `/api/draft/preview`; under the option: the texts, the verdict (for `no`: the dot and `why`), "Outlined: lessons that move, change or are new.", each class's small week (`fxSmallHTML`), the deleted lessons if any, and the same Apply or Apply anyway, and Cancel. A second click shuts it; another option's Preview replaces it; a new draft clears it. While `FX.busy` it toasts `BDWHY.busy`.
- [ ] **Step 3: Apply.** `bdSend` with `Ask.send(option, entry.stamp)`; the selection is left as it is (`stay`). On success the line says the change's sentence, as for any change, and the tab stays open on its subject with every entry now stale. A refusal toasts the server's sentence (`draft.MOVED`, or the judgement's) and the board is fetched again.
- [ ] **Step 4: Apply anyway.** First `bdYesNo({ id: <the option's lesson or null>, text: option.why, ask: "Apply anyway?", yes: "Yes, apply", run })`; Cancel and Escape withdraw it; Yes sends the forced fix. `bdYesNo` and `bdLineHTML` take a question with no lesson id (an add into an empty period has none).
- [ ] **Step 5: Check.** `node --check static/app.js`, both Node suites. On the scratch server with real pointer and key actions, each named by kind: Preview opens and shuts and shows the outlined lessons; Apply a clean swap: the board changes, the Changes tab lists it, the entries strike through, Ctrl or Cmd+Z takes it back; Apply a trade: one line in Changes, one Undo restores both classes; Apply anyway on a busy teacher: the question shows the sentence, Yes lands it and both lessons are marked "In two places", Cancel changes nothing; fill an empty period from "What can go here?" with a lesson from Not placed and with a move; an option whose `apply` is `none` has no Apply; with a second browser tab make a change, then press Apply in the first before its page has caught up: refused with "The timetable changed. Ask again." (if the page catches up first, the entry is struck through: say which was seen); the typed request box and "Ways to settle this" in the Warnings tab still preview and apply.
- [ ] **Step 6: Commit** `feat(step 8): Preview, Apply and Apply anyway on an answer's options; answers go stale with the timetable`.

### Task 8: The whole branch on the school's own files, and the notes

**Files:**
- Create: `docs/superpowers/plans/2026-11-20-ask-about-this-stage-1-notes.md`
- Test: every suite

- [ ] **Step 1: Every suite on the final code**: `PY tests/<name>.py` for `test_ask`, `test_fixes`, `test_helper`, `test_board`, `test_typed`, `test_verify`, `test_rules`, `test_choices`, `test_parents`, `test_sync`, `test_teachers`, `test_venues`, `test_combined` and `smoke`; `--full` on `test_typed`, `test_helper`, `test_fixes` and `smoke`; every `node tests/*.test.js` one by one; `node --check static/app.js`. Expected: all pass.
- [ ] **Step 2: The school's real setup and both real returned timetables** (under `~/Desktop/CTSS/CTSS_TIMETABLE/`; private: counts and timings only, a scratch `DATA_DIR`, every scratch file deleted afterwards). For 40 lessons spread over levels and days, 10 bands, and 30 empty periods (10 each on class, teacher and room rows): each of the eight questions answers without an exception; the longest and the median time of each question (the limit is half a second); how many answers had options, how many had none; how many trades were found and how often `stopped` was set; for every option with `apply` `yes` of 20 answers, `draft.preview` accepts it with the same `state`. A drag's "where it fits" (`GET /api/draft/slots`) and the board's payload take what they took before this branch (0.05 to 0.09 s and 0.05 to 0.15 s in stage 4's notes).
- [ ] **Step 3: Names.** No commit of the branch holds the school's full name or a real teacher's full name (the count is printed, never the names).
- [ ] **Step 4: Write the notes file**: what was built, every ruling made where this plan was silent or wrong, what was checked on the real files (counts and timings), what was left as it is, deferred minors, and what was not tried in a browser.
- [ ] **Step 5: Commit** `docs: notes of Ask about this, stage 1`.

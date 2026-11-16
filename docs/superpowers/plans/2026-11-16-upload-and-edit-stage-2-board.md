# Upload and edit, stage 2: the board. Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Step 8 shows the whole school's timetable for one day as rows of cards, opens one class's whole cycle, fades everything but a chosen subject, and moves a lesson by dragging it (or by a click) wherever the app already allows a move or a swap.

**Architecture:** The draft stays the uploaded file plus the list of fixes, and every change is still made by `POST /api/draft/fix` and judged by `fixes.judge`. Two read-only routes are added: the whole timetable as cards (`/api/draft/board`) and where one lesson fits (`/api/draft/slots`). A pure module `static/board.js` lays the cards out in rows and lanes and answers every question the page asks about a drag; `static/app.js` draws it and handles the mouse. Today's warnings list and Fix card stay below the board, unchanged, and are where a teacher or a room is changed until stage 4.

**Tech Stack:** Flask (`app.py`, `draft.py`, `fixes.py`), vanilla JS with no build step (`static/app.js`, new `static/board.js`), plain-script tests (`.venv/bin/python tests/x.py`, `node tests/x.test.js`). HTML5 drag and drop. No new dependency.

**Spec:** `docs/superpowers/specs/2026-11-16-upload-and-edit-design.md` (stage 2 of "Suggested order of building"), with `docs/superpowers/plans/2026-11-16-upload-and-edit-stage-1-notes.md`.

**Branch:** `upload-and-edit-stage-2`, cut from `upload-and-edit` (stage 1, pull request 57, not merged yet).

## Global Constraints

- Stage 2 makes only the changes the app already allows: a move judged "ok" or "prefer", and a swap judged "ok" or "prefer". A place judged "no" or "na" refuses the drop and says why. Forcing, push out, the Not placed tray, cut and paste, dropping on a day's tab, the counters and the red marks are stage 3. Rows by teacher and by room and the card's teacher and room lists are stage 4. Build none of them.
- A lesson never vanishes: every lesson row of the draft is on a card, and every card is in at least one row of the board, whatever its class, time or length.
- A band moves as one: a card is one lesson id with all its rows and all its classes. Nothing in this stage moves one group or one class of it.
- The agent's file is not changed. The board makes no change except through `POST /api/draft/fix` and `POST /api/draft/undo`.
- "Two bands, or two groups, of one class at the same time are not a mistake": two cards at the same time in one row are both drawn, one above the other.
- The school's size: 32 classes on 4 levels, 26 periods a day, a two-week cycle (10 days), about 1,950 lesson rows, some 200 a day. "The board must open, change day, ... show where a dragged card fits and answer a drop without a pause a person would notice."
- Made-up names only in code, tests and documents. The school is only ever "CTSS" or "the school".
- New sentences on the page are plain, with no em-dash and no arrow.
- No test and no check calls a model API.
- `static/board.js` touches no page object and runs under Node. `node --check static/app.js` passes.
- `ttgen/` is not changed by this stage. If it must be, the copy under `skill/school-timetable-generator/scripts/ttgen/` is kept byte-identical.
- Never run `git stash` in any form, nor `git checkout -- <file>`, in this checkout.
- A draft from before this stage opens as it did, with its fixes.

## Decisions this plan makes (for the committee lead to check)

1. The board sits on step 8 between the upload card and the warnings list. The warnings list, the Fix card, the helper and the typed box stay below it as they are. A selected card has a button "Teacher, room and more" that opens the Fix card on that lesson.
2. A band is drawn as a piece in each of its classes' rows, each piece saying the band's name and how many groups it has. All pieces light up together and move together. (The design's picture shows one tall card; classes of a band are often not next to each other.)
3. One class's whole cycle is the same board turned: a row for each day, the periods across. A card dragged to another day's row there changes its day.
4. A drop on another lesson where a swap is allowed asks "Swap ...?" with Swap and Cancel. Stage 3 adds Push out to the same question.
5. In the day view a card can only be dropped on its own class's row (for a band, any of its classes' rows). Dropping on another class's row is refused in words.
6. Where a card fits is fetched when the card is pressed or selected, and kept until the draft changes.
7. A class on the timetable that is not in the setup gets a row under "Not in the setup", and a lesson with no class a row "No class", so nothing is left off the board.

## Review Focus

1. Two lessons of one class at the same time (two bands, or a clash in the uploaded file): both are drawn, stacked in the row, and each can be picked up. Test in Task 2 (`lanes`).
2. A band of many classes on two levels, its classes not next to each other: a piece in every class's row and one move for all. Tests in Task 1 (one card) and Task 2 (`groups`).
3. A lesson in a break, in recess or outside the day in the uploaded file (68 on one real file): drawn where it is, on the shaded cells, and it can be dragged out. Test in Task 2.
4. A lesson whose class is not in the setup, or with no class: it has a row. Tests in Task 1 and Task 2.
5. The draft changed by someone else while a card is selected or in the air: the drop is judged by the server on the draft as it then is, a refusal is said in words, the board is fetched again and the old "where it fits" is thrown away. Test in Task 1 (the fix after a change), browser check in Task 4.

---

### Task 1: The board and the slots from the server

**Files:**
- Modify: `draft.py` (new `board`, `slots`)
- Modify: `app.py` (two routes, a gzip answer)
- Create: `tests/test_board.py`

**Interfaces:**
- Consumes: `draft._now()`, `fixes.slots(m, spec, days, lesson_id)`, `fixes.what(x)`, `fixes._rows`, `ttgen.export.block_label(block, level)`, `ttgen.export.PALETTE`, the model keys `days`, `NP`, `times`, `levels`, `classes` (each `name`, `level`), `cgrid`, `grid`, `subjects` (each `short`, `dept`, `color`), `teacher_ix` (each `short`), `lessons` (each `id, group, subject, classes, teachers, room, d, p, n, block, level`).
- Produces:
  - `draft.board() -> dict(days, NP, times, levels, codes, subjects, palette, cards)`; raises `NoDraft`.
    - `levels`: `[dict(level=str, classes=[str])]`, the setup's levels in order, each with its classes in the setup's order. A class named on a lesson but not in the setup goes in a last entry `dict(level="Not in the setup", classes=[...])` (left out when there is none).
    - `codes`: `{class: [one string of NP letters per day]}` for every class in `levels`: `m["cgrid"][class]` when it has one, else `m["grid"][its level]`, else `"." * NP` for each day. A period takes a lesson when its letter is `L` or `A`.
    - `subjects`: `{subject: [short, color, dept]}`.
    - `palette`: `[[tint, accent]]`, the hex pairs of `export.PALETTE`.
    - `cards`: one per lesson id, ordered by id: `dict(id, d, p, n, classes, band, what, rows)`. `classes`: every class of its rows, once each, in first-seen order. `rows`: `[dict(group, subject, teachers, tshorts, room)]` in the model's order (`tshorts` as `draft._payload` makes them). `what`: `fixes.what` of its first row. `band`: `""` for a lesson of one row with no block; otherwise `block_label(block, level)` of its first row that has a block, or, when no row has one, the short names of its distinct subjects joined by `" / "`.
  - `draft.slots(lesson_id) -> dict(id=int, slots=[dict(d, p, state, why, swap, also)])`: `fixes.slots` on the draft as it is now. An id that is not a whole number or not on the timetable raises `ValueError("There is no lesson with that id on the timetable.")`.
  - `GET /api/draft/board` (committee only): `draft.board()` through `_checked(..., sentences=True)`; the body is gzip'd, with `Content-Encoding: gzip` and `Vary: Accept-Encoding`, when the request's `Accept-Encoding` names gzip.
  - `GET /api/draft/slots?id=N` (committee only): `draft.slots`, through `_checked(..., sentences=True)`; no `id` answers 400 `{"error": "Say which lesson."}`.

- [ ] **Step 1: Write the failing tests** in `tests/test_board.py`, in the plain style of `tests/test_fixes.py` (its `lesson(...)` helper and the `primary()` sample), with a scratch `DATA_DIR` set before `store` and `draft` are imported, as `tests/smoke.py` does. A helper saves a made-up Lessons workbook as the draft. The tests:

```python
def test_every_lesson_is_on_exactly_one_card():
    b = draft.board(); m = draft._now()[0]
    assert sorted(c["id"] for c in b["cards"]) == sorted({x["id"] for x in m["lessons"]})
    assert sum(len(c["rows"]) for c in b["cards"]) == len(m["lessons"])

def test_a_band_is_one_card_with_all_its_classes_and_rows():
    c = card(BAND_ID)   # a made-up block of three groups over two classes
    assert c["band"] and len(c["rows"]) == 3 and set(c["classes"]) == BAND_CLASSES and c["classes"] == list(dict.fromkeys(c["classes"]))

def test_a_plain_lesson_has_no_band_and_its_teachers_short_names():
    c = card(PLAIN_ID); assert c["band"] == "" and len(c["rows"]) == 1 and len(c["rows"][0]["tshorts"]) == len(c["rows"][0]["teachers"]) and c["what"] == f"{SUBJ} for {CLS}"

def test_codes_cover_every_class_and_day():
    b = draft.board(); names = [c for l in b["levels"] for c in l["classes"]]
    assert set(names) == set(b["codes"]) and all(len(v) == len(b["days"]) and all(len(s) == b["NP"] for s in v) for v in b["codes"].values())

def test_a_class_not_in_the_setup_has_a_row():   # a lesson for class "9Z"
    b = draft.board(); assert b["levels"][-1] == dict(level="Not in the setup", classes=["9Z"]) and "9Z" in b["codes"]

def test_slots_are_the_editors_slots():
    assert draft.slots(PLAIN_ID) == dict(id=PLAIN_ID, slots=draft.options(PLAIN_ID)["slots"])

def test_slots_of_an_unknown_lesson_is_a_sentence():
    for bad in (None, "x", 999999): raises(ValueError, lambda: draft.slots(bad), "There is no lesson with that id on the timetable.")

def test_a_move_refused_after_the_draft_changed_leaves_the_board_as_it_was():
    s = next(x for x in draft.slots(PLAIN_ID)["slots"] if x["state"] == "ok" and x["swap"] is None)
    draft.fix(dict(kind="move", id=OTHER_ID, d=s["d"], p=s["p"]))            # someone else takes the place first
    before = draft.board()
    raises(ValueError, lambda: draft.fix(dict(kind="move", id=PLAIN_ID, d=s["d"], p=s["p"])))
    assert draft.board() == before

def test_the_routes():   # with app.test_client(), signed in as the committee the way tests/smoke.py does
    # GET /api/draft/board with Accept-Encoding: gzip -> 200, Content-Encoding gzip, the unzipped JSON equals draft.board()
    # GET /api/draft/board without it -> 200, no Content-Encoding, the same JSON
    # GET /api/draft/slots -> 400 "Say which lesson."; ?id=999999 -> 400 with the sentence; ?id=PLAIN_ID -> 200
    # with no draft: both routes -> 404
    # not signed in: both routes -> 401

def test_the_board_of_two_thousand_rows_is_quick_and_small():
    # a made-up draft of 2,000 one-period lessons over 32 made-up classes and 10 days: board() in under 1 second,
    # and its JSON gzip'd is under 200,000 bytes
```

- [ ] **Step 2: Run** `.venv/bin/python tests/test_board.py`. Expected: fails with `AttributeError: module 'draft' has no attribute 'board'`.
- [ ] **Step 3: Write `draft.board()` and `draft.slots(lesson_id)`** in `draft.py`, beside `grid` and `options`.
- [ ] **Step 4: Write the two routes** in `app.py`, beside `draft_grid`, and a small `_gz(response)` used by the board route only.
- [ ] **Step 5: Run** `.venv/bin/python tests/test_board.py` and `.venv/bin/python tests/smoke.py`. Expected: both end "N checks passed".
- [ ] **Step 6: Commit** `feat(board): the whole timetable as cards and where a lesson fits`.

### Task 2: The board's layout, as plain functions

**Files:**
- Create: `static/board.js` (`var Board = (function () { ... })(); if (typeof module !== "undefined") module.exports = Board;`, the shape of `static/grid.js`)
- Create: `tests/board.test.js` (the shape of `tests/grid.test.js`)
- Modify: `static/index.html` (load `/static/board.js` before `/static/app.js`)

**Interfaces:**
- Consumes: the payload of `draft.board()` (Task 1) and the slots of `draft.slots()`.
- Produces (every function is pure):
  - `Board.lanes(cards) -> [{card, lane}]`: the cards of one row ordered by `p`, then longer first, then `id`; each takes the lowest lane free in all its periods.
  - `Board.groups(board, mode, weeks) -> [{name, rows: [{key, label, d, cls, codes, lanes, cards: [{card, lane}]}]}]`.
    - `mode = {kind: "day", d}`: a group per entry of `board.levels` (`name` its level), a row per class: `key` and `label` and `cls` the class, `d` the day, `codes` that class's letters for the day, `cards` the lanes of the cards on day `d` whose `classes` hold the class. After them, when any card has no class at all, a group `"No class"` with one row (`key ""`, `label "No class"`, `cls ""`, `codes` of `NP` letters `L`) holding those cards of day `d`.
    - `mode = {kind: "cycle", cls}`: a group per week of `weeks` (the value of `Grid.weeks(board.days)`: `[{name, days: [{i, label}]}]`), a row per day: `key` the day's index as a string, `label` the day's label, `d` its index, `cls` the class, `codes` the class's letters for that day, `cards` the lanes of that class's cards on that day.
    - `lanes` of a row: the number of lanes used, at least 1.
  - `Board.open(code) -> bool`: `code === "L" || code === "A"`.
  - `Board.box(card, NP) -> {from, to}`: the card's first and last column, kept inside `0 .. NP - 1` (a lesson that starts past the last period is drawn on the last one; a length under 1 counts as 1).
  - `Board.lines(card, board) -> {title, lines, color}`: a plain lesson: `title` its subject's short name (the subject itself when it has none), `lines` `[its teachers' short names joined by ", " or "No teacher", its room or "No room"]`; a band: `title` the band's name, `lines` `["1 group"]` or `["N groups"]`. `color`: the colour number of its first row's subject, `0` when unknown.
  - `Board.finds(board) -> [{value, label}]`: `{value: "", label: "All subjects"}`, then a `{value: "d:" + dept, label: dept + " (department)"}` for each department that has a card, by name, then a `{value: "s:" + subject, label: subject}` for each subject that has a card, by name.
  - `Board.matches(card, find, board) -> bool`: true for `""`; for `"s:X"` when a row of the card has subject `X`; for `"d:X"` when a row's subject has department `X`.
  - `Board.grab(card, p) -> int`: which period of the card the pointer holds: `p - card.p` kept inside `0 .. n - 1`.
  - `Board.start(p, grab) -> int`: where the card would start: `p - grab`, not below 0.
  - `Board.slot(card, slots, d, p) -> slot | null`: the slot with that `d` and `p`; `{d, p, state: "own", why: "", swap: null, also: []}` for the card's own start; `null` when there is none.
  - `Board.states(card, slots, d, NP) -> [string]`: for each period of day `d` the state of starting there: `"own"`, `"ok"`, `"prefer"`, `"no"`, `"na"`, or `""` when unknown.
  - `Board.can(slot) -> bool`: `slot` is not null and its state is `"ok"` or `"prefer"`.
  - `Board.fix(card, slot) -> {kind: "swap", a, b} | {kind: "move", id, d, p}`: a swap when `slot.swap` is a lesson id, else a move.
  - `Board.onRow(card, row) -> bool`: the card may be dropped on this row: `row.cls === ""` and the card has no class, or the card's `classes` hold `row.cls`.
  - `Board.tell(slot, days) -> string`: `"Swap with the lesson on {day} period {p}."` or `"Move to {day} period {p}."`, then a space and `slot.why` when it has one; `"This is where the lesson is now."` for `"own"`.

- [ ] **Step 1: Write the failing tests** in `tests/board.test.js`. A helper `card(id, d, p, n, classes, extra)` and a `board(cards)` of two levels (`"Sec 1"`: `1A`, `1B`; `"Sec 2"`: `2A`), two days, `NP` 6, codes `"LLLRLL"`. The tests:

```js
t("lanes: two lessons at the same time are stacked, neither is lost", () => {
  const a = card(1, 0, 1, 2, ["1A"]), b = card(2, 0, 2, 1, ["1A"]), c = card(3, 0, 3, 1, ["1A"]);
  assert.deepStrictEqual(Board.lanes([c, b, a]), [{ card: a, lane: 0 }, { card: b, lane: 1 }, { card: c, lane: 0 }]);
});
t("groups, day: a row per class under its level, a band piece in each of its classes' rows", () => {
  const band = card(5, 0, 0, 2, ["1A", "2A"], { band: "MT" }), g = Board.groups(board([band, card(6, 1, 0, 1, ["1B"])]), { kind: "day", d: 0 });
  assert.deepStrictEqual(g.map(x => [x.name, x.rows.map(r => r.key)]), [["Sec 1", ["1A", "1B"]], ["Sec 2", ["2A"]]]);
  assert.strictEqual(g[0].rows[0].cards[0].card, band); assert.strictEqual(g[1].rows[0].cards[0].card, band);
  assert.deepStrictEqual(g[0].rows[1].cards, []); assert.strictEqual(g[0].rows[1].lanes, 1); assert.strictEqual(g[0].rows[0].codes, "LLLRLL");
});
t("groups, day: a lesson with no class has a row of its own", () => { /* last group "No class", one row, the card in it; no such group when every card has a class */ });
t("groups, day: a lesson in recess is in its row", () => { /* card at p 3 (code R) is in 1A's cards */ });
t("groups, cycle: a row per day for one class, grouped by week", () => { /* weeks [{name:"Odd",days:[{i:0,label:"Mon"}]},{name:"Even",days:[{i:1,label:"Mon"}]}] -> two groups, keys "0" and "1", only 1A's cards */ });
t("box: a lesson that runs past the day is kept on the board", () => { assert.deepStrictEqual(Board.box(card(1, 0, 5, 3, ["1A"]), 6), { from: 5, to: 5 }); assert.deepStrictEqual(Board.box(card(1, 0, 9, 1, ["1A"]), 6), { from: 5, to: 5 }); assert.deepStrictEqual(Board.box(card(1, 0, 1, 0, ["1A"]), 6), { from: 1, to: 1 }); });
t("lines: a plain lesson, one with no teacher and no room, a band of one and of three groups", () => { /* exact titles and lines as in Interfaces */ });
t("finds and matches: departments first, then subjects, only those on a card", () => { /* exact list; matches for "", "s:", "d:" and an unknown subject */ });
t("grab and start: a two-period card held by its second period starts one earlier", () => { assert.strictEqual(Board.grab(card(1, 0, 2, 2, ["1A"]), 3), 1); assert.strictEqual(Board.start(4, 1), 3); assert.strictEqual(Board.start(0, 1), 0); assert.strictEqual(Board.grab(card(1, 0, 2, 2, ["1A"]), 9), 1); });
t("slot, states, can: the card's own place, a clean place, a clash, a place with no answer", () => { /* states -> ["", "ok", "own", "no", "na", "prefer"]; can true only for ok and prefer; slot null where none */ });
t("fix: a move, and a swap when the slot names the other lesson", () => { assert.deepStrictEqual(Board.fix(card(1, 0, 2, 1, ["1A"]), { d: 1, p: 4, swap: null }), { kind: "move", id: 1, d: 1, p: 4 }); assert.deepStrictEqual(Board.fix(card(1, 0, 2, 1, ["1A"]), { d: 1, p: 4, swap: 7 }), { kind: "swap", a: 1, b: 7 }); });
t("onRow: its own class's row, any row of a band's classes, never another class's", () => { /* as in Interfaces, with the "No class" row */ });
t("tell: the sentence for a move, a swap, a clash with its reason, and the card's own place", () => { /* exact sentences */ });
```

- [ ] **Step 2: Run** `node tests/board.test.js`. Expected: fails with `Cannot find module '../static/board.js'`.
- [ ] **Step 3: Write `static/board.js`** with the functions above, and add its `<script>` line to `static/index.html` after `grid.js`.
- [ ] **Step 4: Run** `node tests/board.test.js`. Expected: "N cases passed", N at least 13. Run `for f in tests/*.test.js; do node "$f" || break; done`. Expected: every file passes.
- [ ] **Step 5: Commit** `feat(board): rows, lanes and the answers to a drag as plain functions`.

### Task 3: The board on step 8

**Files:**
- Modify: `static/app.js` (a `bd...` family of functions beside the `fx...` family; `VIEWS.edit`; the draft loader)
- Modify: `static/style.css`

**Interfaces:**
- Consumes: `GET /api/draft/board` (Task 1); `Board.groups`, `Board.open`, `Board.box`, `Board.lines`, `Board.finds`, `Board.matches` (Task 2); `Grid.weeks`; the page's `S.draft`, `loadDraft`, `draftSig`, `fxGet`, `fxOpen`, `esc`, `toast`.
- Produces, for Task 4:
  - `S.board = {data, mode, find, fold, sel, slots, slotsFor, fail}`: `data` the payload or `null`; `mode` `{kind: "day", d}` or `{kind: "cycle", cls}`; `find` a value of `Board.finds`; `fold` `{level: true}` for a level folded shut; `sel` the selected card's id or `null`; `slots` and `slotsFor` filled by Task 4.
  - `bdLoad()`: fetches the board; an answer to an older fetch is dropped; on success keeps `mode`, `find`, `fold` and `sel` (a `sel` no longer on the timetable becomes `null`, a `mode.d` past the last day becomes 0, a `mode.cls` that is gone goes back to the day view) and calls `bdDraw()`.
  - `bdDraw()`: draws `#bdBox` again, keeping the board's scroll.
  - `bdCard(id) -> card | null`.
  - In the page: `#bdBox` holds the board. A row is `<div class="bdrow" data-row="{key}" data-d="{d}" data-cls="{cls}">`; its period cells are `<i class="bdcell" data-p="{p}">` (class `brk` when `Board.open` is false); a piece of a card is `<button class="bdcard" data-card="{id}" draggable="true">`; the selected card's pieces have class `sel`; a faded piece has class `fade`.

- [ ] **Step 1: Draw the board.** In `VIEWS.edit`, after `exportCard()`, a card `#bdBox`. It is drawn whenever the warnings list below it is drawn (a draft is loaded and the page is not showing the Published message); otherwise it is not there. Its parts, top to bottom:
  - a heading "The timetable";
  - a row of controls: the day tabs, grouped by week when `Grid.weeks` gives more than one week (a button per day, the shown one marked); "Find a subject:" with a `<select>` of `Board.finds`; in the cycle view a button "All classes" and the heading "{class}: the whole cycle" in place of the day tabs;
  - the hint: "Drag a lesson to another time on its row, or click it and then click a place. Green is clean, amber bends a rule, red clashes, grey cannot take it.";
  - a header row of the periods: the period's number and, small, its start time from `data.times`;
  - for each group of `Board.groups`: a group header with the level's name that folds the level shut or open on a click (day view; it shows how many classes are folded), then its rows. A row has its label at the left (in the day view a button that opens that class's whole cycle), then its cells and its cards. Cards are placed on a CSS grid of `NP` columns: a piece spans `Board.box`'s columns and sits in its lane's line; the cells lie under the cards, one per period, the full height of the row;
  - a piece shows `Board.lines`: the title in bold, then its lines, each cut with an ellipsis when it does not fit; its `title` attribute gives the card's `what`, its day and period and its lines in full. It is tinted with `palette[color][0]` and has a left edge of `palette[color][1]`;
  - "Loading the timetable…" before the first answer; "The timetable could not be loaded. Open the step again." after a failed fetch.
- [ ] **Step 2: Load it with the draft.** `bdLoad()` is called wherever the page takes a new draft answer: when `loadDraft` applies one, in `fxAfter`, after an upload, after `publishDraft`, and after `decide`. It is not called by a poll that found the summary unchanged.
- [ ] **Step 3: The controls.** A click on a day's tab shows that day. The Find select fades (class `fade`) every piece `Board.matches` is false for, in both views. A click on a class's name opens its cycle; "All classes" goes back to the day that was shown. Day, find, fold and view survive a redraw and a new fetch, and are forgotten when the step is left.
- [ ] **Step 4: Selecting.** A click on a piece selects its card (all its pieces get `sel`); a click on it again, the Escape key, or "Close" clears it. Under the hint a line shows the selected card: "{what} · {day} period {p} ({start time})", for a band also "· {N} groups", and two buttons: "Teacher, room and more", which opens the Fix card below on that lesson (`fxOpen("class", the card's first class, the day's name, {id, group of its first row})`) and scrolls to it, and "Close".
- [ ] **Step 5: Styles** in `static/style.css`: `.bdrow`, `.bdcell`, `.bdcell.brk` (the grey of `table.fxgrid td.brk`), `.bdcard`, `.bdcard.sel`, `.bdcard.fade` (opacity 0.25), the sticky period header and the sticky row labels, so that 32 rows of 26 periods scroll inside the card both ways with the header and the labels in view. A one-period card is at least 44 px wide; the board scrolls sideways when the window is narrower than that allows.
- [ ] **Step 6: Check.** `node --check static/app.js`; `for f in tests/*.test.js; do node "$f" || break; done`. Then in a browser on the scratch server the controller names (a sample timetable with bands is already its draft): the board shows every class under its level; a band has a piece in each of its classes' rows; changing the day changes the cards; a class's name opens ten or five day rows and "All classes" goes back to the same day; Find fades the rest in both views; a fold hides a level; selecting a piece of a band lights all its pieces; "Teacher, room and more" opens the Fix card with that lesson selected; a move made in the Fix card shows on the board without a reload; the console has no error.
- [ ] **Step 7: Commit** `feat(board): a day of the whole school on step 8, one class's cycle, find a subject`.

### Task 4: Moving a card

**Files:**
- Modify: `static/app.js`, `static/style.css`
- Modify: `README.md` (the paragraph on step 8)

**Interfaces:**
- Consumes: `GET /api/draft/slots?id=` (Task 1); `Board.grab`, `Board.start`, `Board.slot`, `Board.states`, `Board.can`, `Board.fix`, `Board.onRow`, `Board.tell` (Task 2); `S.board`, `bdLoad`, `bdDraw`, `bdCard`, the row, cell and card markup (Task 3); `post("/api/draft/fix", fix)`, `post("/api/draft/undo")`, `fxAfter(j)`, `draftSig`.
- Produces: nothing later tasks use.

- [ ] **Step 1: Where it fits.** When a card is selected, and when a piece is pressed (pointer down) before a drag, the page fetches `/api/draft/slots?id=` unless `S.board.slotsFor` is already that id on the same draft (`draftSig`). The answer is kept in `S.board.slots`; an answer for a card no longer selected or held is dropped; a new draft answer clears it. While a card is selected or in the air, each cell of each row `Board.onRow` allows gets the class of `Board.states` for that row's day (`own`, `ok`, `prefer`, `no`, `na`), coloured as `table.fxgrid td.ok`, `.prefer`, `.no`, `.na` are; rows the card cannot be dropped on are dimmed.
- [ ] **Step 2: A click moves it.** With a card selected, a click on a cell of an allowed row asks for the place `Board.slot(card, slots, row's d, the cell's p)`: when `Board.can`, the change of Step 4 is made; otherwise the page says the slot's `why`, or "That lesson cannot go there." when it has none, or "Still working out where this lesson fits." when the slots have not come.
- [ ] **Step 3: Dragging.** `dragstart` on a piece selects its card and remembers `Board.grab(card, the period under the pointer)`; the period under the pointer is worked out from the pointer's x inside the row, so it is right over a cell and over another card alike. `dragover` on a row works out `p = Board.start(period under the pointer, grab)` and the slot; the row's cells from `p` for the card's length get class `over`; the line under the hint shows `Board.tell(slot, days)`; the drop is allowed (`preventDefault`) only when `Board.onRow` and `Board.can`. `drop` makes the change of Step 4. A drop on a row of another class says "A lesson stays with its class. Drop it on its own row." `dragend` clears the `over` marks. The card stays selected after a drop that was refused.
- [ ] **Step 4: The change.** `Board.fix(card, slot)`. A move is posted at once. A swap first shows, in the line under the hint, "Swap {card.what} with the lesson on {day} period {p}?", each sentence of `slot.also`, and the buttons "Swap" and "Cancel"; "Swap" posts it. While a post is running no other is sent. On success the answer goes to `fxAfter(j)` (which already takes the new draft and calls `bdLoad`), the selection is cleared, and the line says the fix's sentence (the last of `j.fixes`, its `text`). On a refusal the server's sentence is shown as a toast, and the board and the slots are fetched again.
- [ ] **Step 5: Undo.** Beside the board's heading a button "Undo the last change", shown when the draft has a fix, with that fix's sentence small beside it. It posts `/api/draft/undo` and takes the answer the same way.
- [ ] **Step 6: README.** The paragraph on step 8 says the timetable is shown as a board of one day, that a lesson is dragged to another time on its row, and that the list of warnings and the editor are below it.
- [ ] **Step 7: Check.** `node --check static/app.js`; every `tests/*.test.js`; `.venv/bin/python tests/test_board.py`; `.venv/bin/python tests/smoke.py`. Then in a browser on the scratch server (the drag is made with the browser tool's drag, or by dispatching `dragstart`, `dragover`, `drop` with a `DataTransfer` from the page's console when the tool cannot drag): a plain lesson selected shows green, amber, red and grey cells on its row only; a click on a green cell moves it and the line says the fix's sentence; "Undo the last change" puts it back; a drag to a green cell moves it; a drag of a two-period card held by its second period lands one period earlier than the pointer; a drag to a red cell is refused with its reason and nothing changes; a drag onto another class's row is refused with its sentence; a drop on a lesson of the same length asks "Swap ...?", "Cancel" changes nothing and "Swap" exchanges them; a band's piece dragged in one class's row moves every piece; in a class's whole cycle a card dragged to another day's row changes its day; with the Fix card open below on the same class, a board move shows in it; a second browser tab on step 8 shows the move within about five seconds; the console has no error.
- [ ] **Step 8: Commit** `feat(board): a lesson is moved by dragging it or by a click, where the app allows`.

## After the tasks

- The controller times `draft.board()`, its gzip'd size and `draft.slots()` on the real returned timetables (counts and timings only), and tries the board in a browser on a made-up timetable of the school's shape.
- Notes go in `docs/superpowers/plans/2026-11-16-upload-and-edit-stage-2-notes.md`.

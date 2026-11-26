# Step 8: four panels, full screen, and what a lesson is tied to: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Step 8 can show three classes' whole cycles and the side panel as four panels, fill the browser window, outline the lessons a chosen lesson is tied to, and say on a card which thing is in two places.

**Architecture:** The class cycle mode gains `panels` (three class names or ""); each panel is drawn with the functions that draw one class's cycle today, so every row still carries its class and day and the drag, drop, click and colouring code is not copied. The layout sums and the "tied" judgements are plain functions in `static/board.js`, tested under Node. The lesson that blocks a red place comes from the server: `Busy.whys` lines gain `ids` and `fixes.place` gives `clashes` on a red place.

**Tech Stack:** Flask, vanilla JS (no build step), plain-assert tests (`$PY tests/x.py`, `node tests/x.test.js`).

**Spec:** `docs/superpowers/specs/2026-11-26-step8-side-by-side-design.md`, with the mock-up `2026-11-26-step8-side-by-side-mockup.html` beside it (a made-up school; open it to see the look). Read the spec first; this plan argues from it.

## Global Constraints

- Work only in the worktree `tt-step8-side-by-side` (branch `step8-side-by-side`). Python is the dev checkout's: `PY=/Users/joetay/Developer/tt-generator/timetable_generator/.venv/bin/python` (the worktree has no `.venv`).
- NEVER run `git stash`, `git stash pop`, `git checkout -- <file>`, `git reset --hard`, or switch branches. `git stash list | wc -l` must stay at 2. To see old code: `git show HEAD:path > <scratch file>`.
- Never use `pkill`/`killall` by name or pattern; stop only processes you started, by PID.
- Never print or edit `.claude/launch.json`. Never start a dev server from a builder task: browser checks are the controller's (Task 7 lists them; the controller also looks after Tasks 3 to 6).
- The repo is public: made-up names only in code, tests and docs; the school is only ever "CTSS".
- No test may call a model API or the Telegram API.
- `static/app.js` has very long lines: search with `grep -nF` or Python and print lines cut to about 600 characters. After a block replace, list the `const`/`function` names the old block defined (`git diff`) and check each is still defined or no longer used.
- Everything from the server or the setup that reaches HTML goes through `esc()`.
- A redraw of the board under a drag cancels the drag in Chromium: outlines, fades and row heights are class and style changes only (as `bdPaint` works today). Nothing new may call `bdDraw` while `S.board.drag !== null`.
- When the four panels are not shown, the one-day board, the one-class cycle and a teacher's or room's cycle must draw the same HTML as before this work, apart from: the **Four panels** button, the **Full screen** button, the new mark words and the two parts added to the Lesson page.
- Words on the page are fixed; copy them exactly: "Four panels", "All classes", "Full screen", "Exit full screen", "No class here", "Choose a class…", "Choose a class at the top to show it here.", "Same teacher", "Same room", "Blocks the place under the pointer", "Teacher in two places", "Class in two places", "Room in two places", "Where it can go", "Tied to", "All three panels are in use: change one at its top".
- Commit after each task, on this branch only. Commit messages end with the line `Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>`. Never push.
- After every task: `node --check static/app.js`, the suites the task names, and `git stash list | wc -l` equal to 2.

## Review Focus

1. Stored panels that are stale or broken (a class the board no longer has, another school's upload, text in `localStorage` that is not a list of three names, a browser that refuses `localStorage`): an empty panel or none stored, never an error. Pinned in Task 2 (`Board.panels`) and Task 3 (the read and the write are in `try`).
2. A school with fewer than three classes, a level of one class, or one week only: the panels open with empty panels and no week heading; with no class at all there is no **Four panels** button. Pinned in Task 2 (`Board.panelsFor`, `Board.panes`).
3. A lesson of two or three shown classes (a band): one lesson drawn in several panels; chosen in one it is chosen in all; the cells it would fill follow the pointer from one panel to the next (row keys differ). Pinned in Task 2 (`Board.panes`).
4. The answer about a blocked place that is late, failed, for another place, or from a server without `ids`: nothing is drawn, nothing is said, nothing throws. Pinned in Task 5 (`Board.blockers`) and checked by the controller in the browser.
5. A lesson with no teacher, no room, room "TBC", or a combined venue: it is tied to nothing by an empty name, and a combined venue meets its rooms. Pinned in Task 5 (`Board.tied`) and Task 6 (`Board.ties`).

---

### Task 1: The lessons in the way, from the server (spec part 3, "The lesson that blocks a place")

**Files:**
- Modify: `fixes.py` (`Busy.whys`, `_placer`, `place`, the docstrings of `slots` and `place`), `draft.py` (the docstring of `place`)
- Test: `tests/test_fixes.py`, `tests/test_board.py`, `tests/smoke.py`
- Commit also (first commit of the branch): the spec, the mock-up, its picture and this plan

**Interfaces:**
- Produces: every line of `Busy.whys(...)` is `dict(kind, text, ids)`; `ids` is a sorted list of lesson ids with no repeats. `fixes.place(...)["clashes"]` (and so `GET /api/draft/place`) is that list wherever the plain move or place collides, `None` where nothing collides. `fixes.slots(...)` is unchanged.

- [ ] **Step 1: Commit the design and the plan**

```bash
git add docs/superpowers/specs/2026-11-26-step8-side-by-side-design.md docs/superpowers/specs/2026-11-26-step8-side-by-side-mockup.html docs/superpowers/specs/2026-11-26-step8-side-by-side-mockup.png docs/superpowers/plans/2026-11-26-step8-side-by-side.md
git commit -m "docs: design and plan for step 8 in four panels"
```

- [ ] **Step 2: Write the failing tests** in `tests/test_fixes.py`, after `test_whys_on_a_double_day`

```python
@t
def test_whys_lines_carry_the_ids_of_the_lessons_in_the_way():
    L = [lesson(1, 0, 2, 1, [A], SUBJ, ENTIRE, [T[0]], room=ROOM, level=LV), lesson(2, 1, 2, 1, [B], "Science", ENTIRE, [T[0]], level=LV),
         lesson(3, 1, 2, 1, [A], "Art", ENTIRE, [T[1]], level=LV), lesson(4, 1, 2, 1, [C3], "Music", ENTIRE, [T[2]], room=ROOM, level=LV)]
    m, sp = model_with(L); b = fixes.Busy(m); got = b.whys(b.ids[1], 1, 2, 1, (1,))
    assert [(x["kind"], x["ids"]) for x in got] == [("teacher", [2]), ("class", [3]), ("room", [4])], got
    assert all(set(x) == {"kind", "text", "ids"} for x in got)

@t
def test_whys_room_line_names_the_lessons_in_the_room_and_those_whose_wet_weather_room_it_is():
    L = [lesson(1, 0, 2, 1, [A], SUBJ, ENTIRE, [T[0]], room=ROOM, level=LV), lesson(2, 1, 2, 1, [B], "Art", ENTIRE, [T[1]], room=ROOM, level=LV),
         dict(lesson(3, 1, 2, 1, [C3], "Music", ENTIRE, [T[2]], level=LV), rain=ROOM)]
    m, sp = model_with(L); b = fixes.Busy(m)
    assert b.whys(b.ids[1], 1, 2, 1, (1,)) == [dict(kind="room", text=f"{ROOM} is in use then.", ids=[2, 3])]
    L = [dict(lesson(1, 0, 2, 1, [A], SUBJ, ENTIRE, [T[0]], level=LV), rain=ROOM), lesson(2, 1, 2, 1, [B], "Art", ENTIRE, [T[1]], room=ROOM, level=LV)]
    m, sp = model_with(L); b = fixes.Busy(m)   # the rows' own wet-weather room: the lessons in it
    assert b.whys(b.ids[1], 1, 2, 1, (1,)) == [dict(kind="room", text=f"{ROOM} is in use then.", ids=[2])]

@t
def test_place_lists_the_collisions_of_a_red_place_with_no_lesson_of_the_class_there():
    L = [lesson(1, 0, 2, 1, [A], SUBJ, ENTIRE, [T[0]], level=LV), lesson(2, 1, 2, 1, [B], "Art", ENTIRE, [T[0]], level=LV)]
    m, sp = model_with(L); s = fixes.place(m, sp, DAYS, 1, 1, 2)
    assert s["push"] is None and s["beside"] is None and s["state"] == "no"
    assert s["clashes"] == [dict(kind="teacher", text=f"{T[0]} is teaching Art for {B} then.", ids=[2])], s["clashes"]
    assert fixes.place(m, sp, DAYS, 1, 2, 2)["clashes"] is None   # nothing collides there
    red = next(x for x in fixes.slots(m, sp, DAYS, 1) if (x["d"], x["p"]) == (1, 2)); assert red["clashes"] is None   # the slots are as before
```

In `tests/test_combined.py`, beside its test of a combined venue's "is in use then." line and with that file's own helpers, add `a_room_line_of_a_combined_venue_names_the_lessons_in_its_rooms`: lesson 1 in a combined venue, lessons 2 and 3 each in one of its rooms at the place asked about; the one room line's `ids` is `[2, 3]`.

- [ ] **Step 3: Rewrite the tests that pin the old shape** (each must fail before Step 5 and pass after)

  - `tests/test_fixes.py`, `test_whys_agree_with_the_first_reason`: a line's keys are `{"kind", "text", "ids"}`; every id is an `int`, is not `i`, and is a lesson with a row on day `d` whose periods overlap `p .. p+nn-1`; a `teacher`, `class` or `students` line has exactly one id.
  - `test_whys_names_a_band_once`: the expected line gains `ids=[7]`. `test_whys_one_line_a_teacher_and_lesson`: `ids=[2]`. `test_place_lists_every_collision_where_another_lesson_is`: the three lines gain `ids=[2]` each.
  - The loop that asserts `fixes.place(m, sp, DAYS, lid, s["d"], s["p"], pl) == s`: equal apart from `clashes`; where `s["clashes"]` is a list the two are equal; where it is `None`, place's is `None` or a list that is not empty. Count the second kind and assert the count is above 0.
  - `tests/test_board.py`, `test_the_place_route_and_the_slots_route_agree_with_the_draft`: a line's keys are `{"kind", "text", "ids"}` and `ids` is a list of ints; `free` is the first slot with `there is None` and `state` "ok" or "prefer".
  - `tests/smoke.py`, `test_the_slots_say_who_and_the_place_route_judges_the_one_dropped_on`: `(k["push"] is None) == (s["there"] is None)`; `k["clashes"]` is a list when `s["there"]` is not `None`, else `None` or a list that is not empty.

- [ ] **Step 4: Run them to see them fail**

Run: `$PY tests/test_fixes.py; $PY tests/test_combined.py; $PY tests/test_board.py; $PY tests/smoke.py`
Expected: the new and rewritten tests FAIL (`KeyError: 'ids'`, or the assertion on the keys).

- [ ] **Step 5: Implement**

  - `Busy.whys`: `line(kind, text, ids)` appends `dict(kind=kind, text=text, ids=sorted(set(ids)))`. A teacher line: that lesson. A class line: lesson `i`. A students line (the band clash and `students()`): that lesson. A room line for a room the rows are in: every lesson not in `ignore` at `("r", s, d, q)` and at `("h", s, d, q)` for `s` in `self.rooms(room)` and `q` in `Q`. A room line for a wet-weather room of the rows: every lesson not in `ignore` at `("r", s, d, q)` for `s` in `self.rooms(h)`. The sentences, their order, and when a line is made do not change; `_why`, `clash` and `blocker` are not touched.
  - `_placer(m, spec, days, lesson_id, pool, extras, ctx, red=False)`: in `at`, when `red` and `extras is True` and `clashes is None`, `clashes = b.whys([dict(x) for x in rows], d, p, n, ignore={lesson_id}, name=name) or None`, before `more` is built. `place` passes `red=True`; `slots` does not.
  - Docstrings of `Busy.whys`, `fixes.slots`, `fixes.place`, `draft.place`: say `ids`, and that `place` lists the collisions of a red place too.

- [ ] **Step 6: Run the suites**

Run: `$PY tests/test_fixes.py && $PY tests/test_combined.py && $PY tests/test_board.py && $PY tests/smoke.py && $PY tests/test_ask.py && node tests/board.test.js`
Expected: each prints its pass line; no failure.

- [ ] **Step 7: Commit** (`feat(step 8): the lessons in the way come with each collision line; a red place lists them`)

---

### Task 2: The panels' sums, in `board.js` (spec part 1)

**Files:**
- Modify: `static/board.js` (new functions before `return`, all added to the exported object)
- Test: `tests/board.test.js`

**Interfaces (produced, all on `Board`):**
- `panels(list, classes) -> [a, b, c] | null`: `list` made into exactly three entries, each a name in `classes` or `""`; a name met a second time becomes `""`; anything that is not an array, or leaves no class, gives `null`.
- `panelsFor(stored, levels, cls, level) -> [a, b, c] | null`: what **Four panels** opens. `levels` is the board's (`[{level, classes}]`). With `cls` (pressed on that class's cycle): `panels(stored)` when it holds `cls`, else `[cls, "", ""]`. Without: `panels(stored)` when there is one; else the first three classes of the level named `level`; else of the first level that has a class; `null` when the board has no class.
- `panelSet(panels, i, cls) -> [a, b, c]`: panel `i` gets `cls` (`""` empties it). Unchanged when `i` is not 0, 1 or 2, when `cls` is in another panel, or when it would leave no class.
- `panelPut(panels, cls) -> [a, b, c] | null`: `cls` into the first empty panel; the same panels when it is shown already; `null` when no panel is empty.
- `panelShow(panels, classes) -> {panels, cls} | null`: for showing a lesson of `classes`: the first of them that is in a panel (the panels unchanged); else `classes[0]` put into the first empty panel; `null` when neither can be.
- `panes(board, panels, weeks) -> [{cls, groups}]`: three entries; `groups` is `groups(board, {kind: "cycle", cls}, weeks)` with every row's `key` set to `cls + "|" + d`; an empty panel has `groups: []`.
- `lane(H, F, L) -> number`: `floor((H - F) / L)` kept between 16 and 60; `L` below 1 or not a number counts as 1; a result that is not a number is 16.
- `ownRows(card) -> string`: "This lesson is 1A's. It can only go on 1A's rows."; for several classes "This lesson is 1A, 1B and 1C's. It can only go on their rows."; `""` for a card with no class.

- [ ] **Step 1: Write the failing tests** at the end of `tests/board.test.js` (before its last line that prints the count)

```js
t("panels: three entries, a class once, unknown classes emptied, none left is null", () => {
  const all = ["1A", "1B", "2A"];
  assert.deepStrictEqual(Board.panels(["1A", "1B", "2A"], all), ["1A", "1B", "2A"]);
  assert.deepStrictEqual(Board.panels(["1A", "9Z", "1A", "2A"], all), ["1A", "", ""]);
  assert.deepStrictEqual(Board.panels(["", "2A"], all), ["", "2A", ""]);
  [null, undefined, "1A", {}, [], ["", "", ""], ["9Z"], [1, null, {}]].forEach(x => assert.strictEqual(Board.panels(x, all), null));
});
t("panelsFor: what Four panels opens", () => {
  const lv = board([]).levels;   // Sec 1: 1A, 1B; Sec 2: 2A
  assert.deepStrictEqual(Board.panelsFor(["2A", "", "1B"], lv, "", ""), ["2A", "", "1B"]);
  assert.deepStrictEqual(Board.panelsFor(null, lv, "", "Sec 2"), ["2A", "", ""]);
  assert.deepStrictEqual(Board.panelsFor(["9Z"], lv, "", "No such level"), ["1A", "1B", ""]);
  assert.deepStrictEqual(Board.panelsFor(["2A", "", "1B"], lv, "1B", ""), ["2A", "", "1B"]);
  assert.deepStrictEqual(Board.panelsFor(["2A", "", ""], lv, "1B", ""), ["1B", "", ""]);
  assert.deepStrictEqual(Board.panelsFor(null, [{ level: "S", classes: [] }, { level: "T", classes: ["a", "b", "c", "d"] }], "", ""), ["a", "b", "c"]);
  assert.strictEqual(Board.panelsFor(null, [], "", ""), null); assert.strictEqual(Board.panelsFor(["1A"], [{ level: "S", classes: [] }], "", ""), null);
});
t("panelSet: a panel's class changed or emptied", () => {
  assert.deepStrictEqual(Board.panelSet(["1A", "", ""], 1, "1B"), ["1A", "1B", ""]);
  assert.deepStrictEqual(Board.panelSet(["1A", "1B", ""], 0, ""), ["", "1B", ""]);
  assert.deepStrictEqual(Board.panelSet(["1A", "", ""], 0, ""), ["1A", "", ""]);         // the last class stays
  assert.deepStrictEqual(Board.panelSet(["1A", "1B", ""], 2, "1A"), ["1A", "1B", ""]);   // a class is never shown twice
  assert.deepStrictEqual(Board.panelSet(["1A", "1B", ""], 7, "2A"), ["1A", "1B", ""]);
});
t("panelPut and panelShow: a class into the first empty panel", () => {
  assert.deepStrictEqual(Board.panelPut(["1A", "", "2A"], "1B"), ["1A", "1B", "2A"]);
  assert.deepStrictEqual(Board.panelPut(["1A", "", "2A"], "2A"), ["1A", "", "2A"]);
  assert.strictEqual(Board.panelPut(["1A", "1B", "2A"], "3C"), null);
  assert.deepStrictEqual(Board.panelShow(["1A", "", ""], ["2A", "1A"]), { panels: ["1A", "", ""], cls: "1A" });
  assert.deepStrictEqual(Board.panelShow(["1A", "", ""], ["2A", "1B"]), { panels: ["1A", "2A", ""], cls: "2A" });
  assert.strictEqual(Board.panelShow(["1A", "1B", "2A"], ["3C"]), null); assert.strictEqual(Board.panelShow(["1A", "", ""], []), null);
});
t("panes: a panel a class, row keys that never collide, a lesson of two shown classes in both", () => {
  const weeks = [{ name: "", days: [{ i: 0, label: "Mon" }, { i: 1, label: "Tue" }] }];
  const band = card(5, 0, 0, 2, ["1A", "2A"], { band: "MT" }), b = board([band, card(6, 1, 0, 1, ["1B"])]);
  const ps = Board.panes(b, ["1A", "", "2A"], weeks), keys = [].concat(...ps.map(p => [].concat(...p.groups.map(g => g.rows.map(r => r.key)))));
  assert.deepStrictEqual(ps.map(p => p.cls), ["1A", "", "2A"]); assert.deepStrictEqual(ps[1].groups, []);
  assert.deepStrictEqual(keys, ["1A|0", "1A|1", "2A|0", "2A|1"]);
  assert.strictEqual(ps[0].groups[0].rows[0].cards[0].card, band); assert.strictEqual(ps[2].groups[0].rows[0].cards[0].card, band);
  const one = Board.groups(b, { kind: "cycle", cls: "1A" }, weeks)[0].rows[0];
  assert.deepStrictEqual(Object.assign({}, ps[0].groups[0].rows[0], { key: one.key }), one);   // but for its key, the row of the one-class cycle
});
t("lane: the rows share the panel's height, between 16 and 60", () => {
  assert.strictEqual(Board.lane(331, 71, 10), 26); assert.strictEqual(Board.lane(331, 71, 12), 21);
  assert.strictEqual(Board.lane(200, 71, 10), 16); assert.strictEqual(Board.lane(2000, 71, 10), 60);
  assert.strictEqual(Board.lane(0, 0, 0), 16); assert.strictEqual(Board.lane(NaN, 71, 10), 16); assert.strictEqual(Board.lane(331, 71, -3), 60);
});
t("ownRows: whose rows a lesson can go on", () => {
  assert.strictEqual(Board.ownRows(card(1, 0, 0, 1, ["1A"])), "This lesson is 1A's. It can only go on 1A's rows.");
  assert.strictEqual(Board.ownRows(card(1, 0, 0, 1, ["1A", "1B"])), "This lesson is 1A and 1B's. It can only go on their rows.");
  assert.strictEqual(Board.ownRows(card(1, 0, 0, 1, ["1A", "1B", "1C"])), "This lesson is 1A, 1B and 1C's. It can only go on their rows.");
  assert.strictEqual(Board.ownRows(card(1, 0, 0, 1, [])), "");
});
```

- [ ] **Step 2: Run to see them fail.** Run: `node tests/board.test.js`. Expected: `FAILED: panels: ...` with "Board.panels is not a function".
- [ ] **Step 3: Implement the eight functions** in `static/board.js` and export them. No function reads the page.
- [ ] **Step 4: Run.** `node tests/board.test.js`. Expected: its pass line, the count 8 higher than before.
- [ ] **Step 5: Commit** (`feat(board): the four panels' sums: which classes, their rows, a row's height`)

---

### Task 3: The four panels on the page (spec part 1)

**Files:**
- Modify: `static/app.js`: the `S.board` literal in `bdEnsure`; `bdHTML`, `bdRowHTML`, `bdSideHTML`, `bdDraw`, `bdTake`, `bdPaint`, `bdClick`, `bdGoTo`, `bdShowWarning`, `bdWhyText` and its two callers, `bdPopDraw` and the `pointerdown` that sets `BD.popXY`; the `change` listener that serves `#bdFind`; the view that writes `<div class="card" id="bdBox">` (two places: `grep -nF 'id="bdBox"'`); `render`'s keeping of `.bdwrap`'s scroll (about line 959)
- Modify: `static/style.css`

**Interfaces:**
- Consumes (Task 2): `Board.panels`, `panelsFor`, `panelSet`, `panelShow`, `panes`, `lane`, `ownRows`.
- Produces, for Tasks 4 to 6:
  - `S.board.mode = {kind: "cycle", cls, panels, d}` for the four panels (`cls` is always the first class in `panels`); `S.board.panels` (the panels last shown, or `null`); `S.board.full` (`false`; Task 4 uses it).
  - `bdFour() -> [a, b, c] | null`: the panels when the four panels are shown.
  - `bdPanelsShow(p, d)`: shows panels `p` (mode as above, `d` the day to go back to), keeps them (`S.board.panels` and `localStorage` key `tt.bdpanels`, JSON, in `try`), clears `S.board.place`, and lets go of a chosen lesson that is on the board when none of its classes is in `p` (`sel`, `ask`, `del`, `note`, `step` cleared, `akBack`). It does not draw.
  - `bdBoxClass() -> string`: `"card"`, plus `" bdfour"` when `bdFour()`, plus `" bdfull"` when `S.board.full`. Both places that write `#bdBox` use it, and `bdDraw` sets `box.className` from it.
  - `bdFit()`: sets each live panel's row height (below). Safe to call when no panel is shown.
  - HTML: the panels are `<div class="bdmain bdquad">` holding three `<div class="bdpane" data-pane="{i}" data-panecls="{class}">` and then `#bdSide`. A pane holds `<div class="bdpanehd"><select data-bdpane="{i}">…</select></div>` and one `.bdwrap > .bdin` with the period header and the rows. Rows are today's `.bdrow` elements.

- [ ] **Step 1: State and storage.** Add `full: false, panels: <read from tt.bdpanels, else null>` to the `S.board` literal; write `bdFour`, `bdPanelsShow`, `bdBoxClass`. Reading: `JSON.parse` in `try`; anything that is not an array is `null` (the board's classes are applied later by `Board.panels`).

- [ ] **Step 2: Draw the panels** in `bdHTML` when `bdFour()`:
  - Control row: `<button data-bdall="1">All classes</button><b>Four panels</b>` and the Find list. No day tabs. The "Rows:" buttons stay.
  - On the one-day board with Classes rows, and on a one-class cycle: a button `<button data-bdfour="1">Four panels</button>` in the control row before the Find list; not when the board has no class.
  - A pane's list (`select[data-bdpane]`): first option `value=""` reading "Choose a class…" in an empty pane, "No class here" in a pane with a class when another pane has one (no such option when it is the only class); then an `<optgroup>` a level with its classes, less those in the other two panes.
  - A pane's rows: `Board.panes(d, panels, weeks)`; a week's heading (`.bdgrp`) when `weeks.length > 1`; rows through `bdRowHTML(row, b, true, hit, warned, true)`. The new last argument `fixed` makes the row's lanes exactly `var(--bdh)` high (`repeat(lanes, var(--bdh))` in place of `minmax(var(--bdh), auto)`) and adds `data-lanes`. Without it `bdRowHTML` writes what it writes today.
  - A pane's period header: each period's number; its start time in the `<small>` only when `p % 3 === 0` (an `&nbsp;` otherwise, so the header keeps its height); `title="Period {p}, {time}"` on every period.
  - An empty pane: its list and `<p class="muted bdnone">Choose a class at the top to show it here.</p>`.
  - `#bdSide` is the fourth child of `.bdquad`: no `#bdGrip`, and `bdSideHTML` writes no inline width there (the stored width is neither used nor changed).
  - The quad is one child of `#bdBox` and has the class `bdmain`, so `bdKeep` (which keeps the child that holds a dragged card) and every `.bdmain:not(.bdold)` selector hold as they are. Do not change `bdKeep`.

- [ ] **Step 3: Styles** in `static/style.css` (values from the spec):
  - `.bdquad`: a grid of two columns and two rows of equal size, gap 8px, height `max(600px, 82vh)`. Under 900px wide: one column, each pane and `#bdSide` 420px high.
  - `.bdpane`: a column; its `.bdwrap` takes the rest of its height, scrolls both ways, and has no `max-height`. `--bdlab: 42px; --bdw: 20px`; card text 10.5px.
  - `.bdpane.thin .bdcard`: one line: the subject (`b`) whole, then the other lines on the same line, cut with "…"; `.bdpane.thin .bdbadge{max-width:50%}`.
  - `.bdquad #bdSide`: fills its quarter (`width:auto`, no `min-height`).

- [ ] **Step 4: `bdFit()`.** For each `.bdmain:not(.bdold) .bdpane` with rows: `H` = its `.bdwrap`'s `clientHeight`, `L` = the sum of its rows' `data-lanes`, `F` = the height of everything in the pane's `.bdin` that is not a lane (the period header, the week headings, each row's strip and border). `n = Board.lane(H, F, L)`; set `--bdh` to `n` pixels on the pane and toggle its class `thin` when `n < 28`. It must hold that when `n > 16` the pane's `.bdin` is no taller than its `.bdwrap` (no up-and-down scroll). Call it at the end of `bdDraw` (before `bdPaint`), where `render` calls `bdPaint` after `main.innerHTML` (about line 961), and on the window's `resize` (once a frame). It only sets styles and classes.

- [ ] **Step 5: Clicks and lists.**
  - `data-bdfour`: `p = Board.panelsFor(bd.panels, d.levels, <the cycle's class, or "">, <the level of the chosen lesson's first class, else the first level not folded>)`; when `p`, `bdPanelsShow(p, bd.mode.d)`, `bdDraw()`, `bdWant()`.
  - A `change` on `select[data-bdpane]` (beside the `#bdFind` line): `bdPanelsShow(Board.panelSet(panels, i, value), bd.mode.d)`, `bdDraw()`, `bdWant()`. Not while `bd.wait` or `bd.drag !== null`.
  - `data-bdall`, `data-bdrows`, `data-bdcls`: as today (they leave the four panels; `S.board.panels` stays).
- [ ] **Step 6: Going to a lesson.**
  - `bdGoTo(c)` on Classes rows with `bdFour()`: `r = Board.panelShow(panels, <c's classes that the board has>)`; with `r`, `bdPanelsShow(r.panels, c.d)`; else `bd.mode = {kind: "day", d: c.d}`. The level is opened as today. The one-class branch (today's line that tests `bd.mode.cls`) must not run for the four panels.
  - `bdShowWarning`, a class and no lesson: with `bdFour()`, `r = Board.panelShow(panels, [a.cls])`; with `r`, `bdPanelsShow(r.panels, …)` and that pane (`.bdpane[data-panecls]`) is scrolled into view (`block: "nearest"`), and the row looked for is that class's (`[data-cls]` as well as `[data-d]`); else today's one-class cycle. A teacher's warning: untouched.
  - `bdTake`: with `mode.panels`, `p = Board.panels(mode.panels, bdClasses(j))`: `null` goes to the day board as today, else `mode.panels = p` and `mode.cls` its first class. Also `b.panels = Board.panels(b.panels, bdClasses(j))` (and the stored copy with it).
- [ ] **Step 7: Painting and words.**
  - `bdPaint`: with `bdFour()` no row gets `dim`. Nothing else changes here (Task 5 adds the outlines).
  - `bdWhyText(a, drag, c)`: for `a.why === "class"` with `bdFour()` and `Board.ownRows(c)` not empty, that sentence; else today's. Pass `c` from `bdAct` and from the `dragover` listener.
  - `bdDraw` keeps each pane's scroll (left and top) when the pane at that place holds the same class after the draw; `render` (about lines 959 and 965) keeps every live `.bdwrap`'s scroll by its order when their number is the same.
  - `BD.popXY` gains `pane` (the index of the `.bdpane` pressed, else `null`); in `bdPopDraw`, with a pane, only the chosen lesson's pieces in that pane are the rows to keep clear.

- [ ] **Step 8: Check.** Run: `node --check static/app.js && node tests/board.test.js && $PY tests/test_board.py && $PY tests/smoke.py`. Expected: all pass. Then, by reading the diff: every name the diff removed is still defined or unused; with `bdFour()` null, `bdHTML` differs from before only by the **Four panels** button.
- [ ] **Step 9: Commit** (`feat(step 8): four panels: three classes' whole cycles and the side panel`)

Controller's look in the browser after this task (a made-up school, a real mouse): open from the day board and from a class's cycle; change and empty a pane; a click-then-click move and a drag inside a pane and between its weeks; a swap; "Put it here anyway"; a paste from Not placed; a drop on the fourth panel lifts out; Undo; the panels come back after leaving and re-opening step 8; a window under 900 pixels wide.

---

### Task 4: Full screen (spec part 2)

**Files:**
- Modify: `static/app.js` (`bdHTML`, `bdClick`, the Escape `keydown` listener, `bdHowHTML`), `static/style.css`

**Interfaces:**
- Consumes: `S.board.full`, `bdBoxClass`, `bdFour`, `bdFit` (Task 3).
- Produces: the button `data-bdfull="1"`; the class `bdfull` on `#bdBox`.

- [ ] **Step 1: The button.** In `bdHTML`'s title line (`.bdtitle`), at the right, in every view and also while the board is loading: `<button data-bdfull="1" class="bdfullb" aria-pressed="{full}">Full screen</button>`, reading "Exit full screen" when `S.board.full`. `bdClick`: toggles `bd.full`, then `bdDraw()` (which sets the box's class and calls `bdFit`). Not while `bd.wait` or `bd.drag !== null`.
- [ ] **Step 2: The three lines.** With `bdFour()` and `full`, `bdHTML` writes above the panels exactly: the title line, now holding `<h2>`, the **All classes** button, the Find list and the full-screen button; the counters with Undo; the status line (`#bdLine`). It does not write the "Rows:" row, the control row or the key of the outlines (Task 5). In every other view with `full`, everything above the board is written as out of full screen.
- [ ] **Step 3: Styles.**
  - `#bdBox.bdfull`: `position: fixed; inset: 0; z-index: 22` (above the page's header, 5, and its pop-ups, 20; below the page's overlays, 25 and 26, and the toast, 30), no margin or rounded corners, a column that scrolls inside itself with `overscroll-behavior: contain`.
  - `.bdfull .bdhow` and `.bdfull #bdFoot`: not shown.
  - `.bdfull .bdmain`: takes the rest of the height; its `.bdwrap` has no `max-height` and scrolls inside; `.bdfull .bdquad` takes the rest of the height in place of `82vh`.
  - Row heights are not touched outside the panes.
- [ ] **Step 4: Esc.** In the Escape listener: when nothing is asked and nothing is chosen (today's early return), not in a field, no drag and no waiting drop, and `b.full`: `preventDefault`, `b.full = false`, `bdDraw()`. One press never does both. In `bdHowHTML`'s Keys line: "Esc lets go of the lesson, then leaves full screen."
- [ ] **Step 5: Check.** `node --check static/app.js && node tests/board.test.js`. `S.board` is made anew when step 8 is opened again, so full screen is not remembered: confirm by reading `bdEnsure` that nothing stores `full`.
- [ ] **Step 6: Commit** (`feat(step 8): full screen: the timetable card fills the browser window`)

Controller's look: the card's box equals the window in full screen (`getBoundingClientRect`), in every view; the drop box, a question and a toast show above it; at 1440 by 900 the three panes show both weeks with no up-and-down scroll; Esc's order (a question, then the lesson, then full screen); the one-day board and a teacher's cycle keep their row height; leaving step 8 and coming back is not full screen.

---

### Task 5: What a lesson is tied to (spec part 3)

**Files:**
- Modify: `static/board.js`, `static/app.js` (`bdPaint`, `bdHTML`, `bdDraw`, `bdDragEnd`, the `mousemove` and `dragover` listeners, the `BD` literal), `static/style.css`
- Test: `tests/board.test.js`

**Interfaces:**
- Consumes: `clashes[].ids` from `GET /api/draft/place` (Task 1); `bdFour` (Task 3); `bdQuiet(url)` (exists: a GET that says nothing on failure).
- Produces on `Board`: `tied(card, other, parts) -> "teacher" | "room" | ""` and `blockers(slot) -> number[]`.
- Produces on the page: card classes `tiet` (same teacher), `tier` (same room), `tief` (faded), `blk` (blocks the place).

- [ ] **Step 1: Write the failing tests** in `tests/board.test.js`

```js
t("tied: the same teacher, else a room that meets, else nothing", () => {
  const mk = (id, teachers, room, more) => card(id, 0, 0, 1, ["1A"], { rows: [{ group: "G", subject: "Maths", teachers: teachers, room: room }].concat(more || []) });
  const a = mk(1, ["Mr Tan", "Ms Lee"], "Lab 1&2"), parts = { "Lab 1&2": ["Lab 1", "Lab 2"] };
  assert.strictEqual(Board.tied(a, mk(2, ["Ms Lee"], "R9"), parts), "teacher");
  assert.strictEqual(Board.tied(a, mk(3, ["Mr Ong"], "R9", [{ group: "H", subject: "Art", teachers: ["Mr Tan"], room: "" }]), parts), "teacher");   // any row
  assert.strictEqual(Board.tied(a, mk(4, ["Mr Ong"], "Lab 2"), parts), "room");      // a combined venue meets its rooms
  assert.strictEqual(Board.tied(a, mk(5, ["Ms Lee"], "Lab 1"), parts), "teacher");   // the teacher comes first
  assert.strictEqual(Board.tied(a, mk(6, ["Mr Ong"], "R9"), parts), "");
  assert.strictEqual(Board.tied(a, a, parts), ""); assert.strictEqual(Board.tied(a, mk(1, ["Mr Tan"], "Lab 1"), parts), "");   // itself, by id
  assert.strictEqual(Board.tied(mk(7, [], ""), mk(9, [], ""), parts), ""); assert.strictEqual(Board.tied(mk(8, [], "TBC"), mk(10, [], "TBC"), undefined), "");
  assert.strictEqual(Board.tied({ id: 11 }, { id: 12 }, parts), "");   // cards with no rows
});
t("blockers: the ids a judged place names, each once, in order", () => {
  assert.deepStrictEqual(Board.blockers({ clashes: [{ kind: "teacher", text: "x", ids: [7] }, { kind: "room", text: "y", ids: [3, 7, 9] }, { kind: "room", text: "z", ids: [] }] }), [3, 7, 9]);
  [null, undefined, {}, { clashes: null }, { clashes: "x" }, { clashes: [{ kind: "class", text: "from an older server" }] }].forEach(s => assert.deepStrictEqual(Board.blockers(s), []));
});
```

- [ ] **Step 2: Run to see them fail** (`node tests/board.test.js`: "Board.tied is not a function"), **implement** both in `static/board.js` (`tied` uses `roomsMeet`; a room of `""` or "TBC" meets nothing), **run again** to pass.

- [ ] **Step 3: The standing outlines** in `bdPaint`, only with `bdFour()` and a lesson wanted (`c`); with either missing the three classes are taken off every card. For each `.bdcard` inside a `.bdpane` row, with `o` its card and `own = Board.onRow(c, <that row>, d)`:
  - `k = o.id === c.id ? "" : Board.tied(c, o, d.room_parts)`; a card that has today's `swap` outline gets none of the three.
  - `tiet`: `k === "teacher"` (in the lesson's own class's panes too).
  - `tier`: `k === "room"` and not `own`.
  - `tief`: not `own`, not the lesson itself, and neither of the two above.
  Styles: `.bdcard.tiet{outline:2px solid #7c3aed;outline-offset:-2px}`, `.bdcard.tier{outline:2px dotted #0f8f8f;outline-offset:-2px}`, `.bdcard.tief{opacity:.62}`, `.bdcard.blk{outline:3px dashed #c62828;outline-offset:-3px;opacity:1;z-index:2}`. A card faded by Find or by a counter (`fade`, `cfade`) stays at their 25%.

- [ ] **Step 4: The key.** With `bdFour()` and not `full`, `bdHTML` writes under the counters `<div class="row bdties"><span><i class="bdkey kt"></i>Same teacher</span><span><i class="bdkey kr"></i>Same room</span><span><i class="bdkey kb"></i>Blocks the place under the pointer</span></div>`, each swatch drawn with its outline.

- [ ] **Step 5: The lesson that blocks a red place.** `BD.blk = {key: "", t: 0, gen: -1, got: {}}` and `bdBlock(at)`, `at` being `{id, d, p}` or `null`:
  - `null`, or another key than the one held: take `blk` off every card, clear the timer, hold the new key (`"{id}|{d}|{p}"`, or `""`).
  - A new key: after 200 ms, if it is still the key held: from `BD.blk.got[key]` when `BD.blk.gen === BD.gen` (else the cache is emptied for the new `BD.gen`), or `bdQuiet("/api/draft/place?id=…&d=…&p=…")`; the answer is kept as `Board.blockers(answer)` and, when the key is still held and `BD.gen` is the one it was asked on, every `.bdmain:not(.bdold) .bdcard` whose id is in it gets `blk`. A `null` answer is not kept and draws nothing.
  - It is called with a place only when all of these hold: `bdFour()`; a lesson is wanted and its slots are here (`b.slotsFor === c.id`); the row is one of the lesson's own (`Board.onRow`); `Board.states(c, b.slots, d, NP)[p] === "no"`. Else with `null`.
  - Callers: the `mousemove` listener when no drag is on (the place is the `.bdcell` or `.bdmark` under the pointer: its row's day and its own period, as a click there would start the lesson); the `dragover` listener (the row and the period `bdAimed` gives); `bdDragEnd` and `bdDraw` call `bdBlock(null)`.
  - It never changes `b.pt`, the strip's titles, or what a click or drop does.

- [ ] **Step 6: Check.** `node --check static/app.js && node tests/board.test.js`. Expected: pass.
- [ ] **Step 7: Commit** (`feat(step 8): outlines for the same teacher, the same room, and the lesson that blocks a red place`)

Controller's look: with a lesson chosen, purple on that teacher's lessons in all panes, dotted teal on its room's lessons in the other classes' panes only, the rest of those panes faded and still readable; a swap candidate keeps its green dashed outline; resting on a red place outlines the lesson its sentence names, in every pane it is in, and leaving the place removes it; the same during a drag, and the drag is not cut off; a stopped server draws nothing and says nothing; none of it on the one-day board or the one-class cycle.

---

### Task 6: The Lesson page's two parts and the mark's words (spec parts 4 and 5)

**Files:**
- Modify: `static/board.js` (`MARK`; new `tally`, `ties`), `static/app.js` (`akHTML`, `bdPaint`, `bdClick`, `bdPieces`, `bdHowHTML`), `static/style.css`
- Test: `tests/board.test.js`

**Interfaces:**
- Consumes: `bdFour`, `bdPanelsShow` (Task 3); `Board.panelPut` (Task 2); `bdSlotsHad(id)` (exists: a lesson's fetched places for the board now, or `null`).
- Produces on `Board`:
  - `tally(card, slots) -> {ok, prefer, ask}`: over `slots`, counted as `Board.states` colours a place: `ask` where another lesson of the class is (`there` not empty, or what `asks` answers), else `ok` or `prefer` by its state. Zeroes for no slots.
  - `ties(card, board) -> {band, teachers}`: `band` is `card.classes` when `card.band` and it has two or more classes, else `null`. `teachers`: each teacher of the card's rows once, in order, as `{name, classes: [{cls, n}]}`: the classes, other than the card's own, of the placed cards (`board.cards`) that have a row with that teacher, `n` the number of such cards; the levels' classes in their order, then other names sorted.

- [ ] **Step 1: Write the failing tests** in `tests/board.test.js`; change the tests that pin "In two places" on a card (the `MARK` literal, and the three `badge`/`flag` expectations: a `teacher` mark reads "Teacher in two places", `class` "Class in two places", `room` "Room in two places"; `COUNTERS` keeps "In two places").

```js
t("tally: where a lesson can go, counted as the board colours its places", () => {
  const c = card(1, 0, 0, 1, ["1A"]), s = (d, p, state, more) => Object.assign({ d: d, p: p, state: state, why: "", swap: null, also: [], there: null }, more || {});
  const slots = [s(0, 1, "ok"), s(0, 2, "ok"), s(0, 3, "prefer"), s(0, 4, "no"), s(0, 5, "na"),
    s(1, 0, "ok", { swap: 5, there: [{ id: 5 }] }), s(1, 1, "na", { there: [{ id: 6 }, { id: 7 }] })];
  assert.deepStrictEqual(Board.tally(c, slots), { ok: 2, prefer: 1, ask: 2 });
  assert.deepStrictEqual(Board.tally(c, null), { ok: 0, prefer: 0, ask: 0 });
});
t("ties: each teacher's other classes with their lessons; a band of several classes says so", () => {
  const mk = (id, cls, teachers) => card(id, 0, 0, 1, cls, { rows: [{ group: "G", subject: "Maths", teachers: teachers, room: "" }] });
  const me = mk(1, ["1A"], ["Mr Tan", "Ms Lee"]);
  const b = board([me, mk(2, ["1A"], ["Mr Tan"]), mk(3, ["2A"], ["Mr Tan"]), mk(4, ["1B"], ["Mr Tan"]), mk(5, ["2A"], ["Mr Tan"]), mk(6, ["1B", "2A"], ["Mr Ong"])]);
  assert.deepStrictEqual(Board.ties(me, b), { band: null, teachers: [{ name: "Mr Tan", classes: [{ cls: "1B", n: 1 }, { cls: "2A", n: 2 }] }, { name: "Ms Lee", classes: [] }] });
  assert.deepStrictEqual(Board.ties(card(7, 0, 0, 1, ["1A", "1B"], { band: "MT" }), b).band, ["1A", "1B"]);
  assert.strictEqual(Board.ties(card(8, 0, 0, 1, ["1A"], { band: "MT" }), b).band, null);
  assert.deepStrictEqual(Board.ties({ id: 9, classes: ["1A"] }, b), { band: null, teachers: [] });
});
```

- [ ] **Step 2: Run to see them fail, implement `MARK`, `tally` and `ties`, run to pass** (`node tests/board.test.js`).

- [ ] **Step 3: The two parts** in `akHTML`, for a lesson on the board only (not in Not placed, not an entry of step 5's list, not gone), after its warnings (`.bdlws`) and before the band's chips, in every view:
  - `<div class="aktie"><h4>Where it can go</h4><div id="akWhere">…</div>`: from `bdSlotsHad(c.id)`; with none, empty. Else three lines, each left out when its number is 0: "{n} clean place(s)", "{n} that bend(s) a Prefer" ("1 that bends a Prefer"), "{n} where another lesson of the class is: a swap is asked"; when all three are 0: "Nowhere else in the cycle.". `bdPaint` ends by writing `#akWhere` again when it is on the page (so it fills when the places arrive, with no redraw of the panel).
  - `<h4>Tied to</h4>` and: for a band (`ties.band`): "This lesson is one band. It moves in 1A, 1B and 1C at the same time." Else a block a teacher: "{teacher} also teaches:" and a list, an item a class: "{cls}: {n} lesson(s)"; with `bdFour()`, after it " · shown" when the class is in a pane, else `<button data-bdshowcls="{cls}">Show {cls}</button>`, `disabled` with `title="All three panels are in use: change one at its top"` when no pane is empty. A teacher with no other class: "{teacher} teaches no other class." No teacher at all: "This lesson has no teacher."
  - `bdClick`, `data-bdshowcls`: `p = Board.panelPut(panels, cls)`; with `p`, `bdPanelsShow(p, bd.mode.d)`, `bdDraw()`, `bdWant()`.
- [ ] **Step 4: The mark's words on the card.** In `bdPieces`, a card with a mark has the mark's words (`Board.badge(c).text`) as the first line of its `title`. In `bdHowHTML` one more item: `<li><b>In two places:</b> Teacher: one of the lesson's teachers has another lesson then. Class: the class has another lesson then (two groups of one band, or of one class, do not count). Room: the room holds more lessons then than it takes.</li>`, and the "Whole cycle" item ends "… **Four panels** shows three classes at once; **Full screen** fills the window."
- [ ] **Step 5: Check.** `node --check static/app.js && node tests/board.test.js && node tests/ask.test.js && node tests/draft.test.js`. `grep -rnF "In two places" static tests ttgen README.md`: what is left is the counter (`COUNTERS`), the Warnings list's own words and the README (Task 7).
- [ ] **Step 6: Commit** (`feat(step 8): the Lesson page says where a lesson can go and what it is tied to; a card says which thing is in two places`)

---

### Task 7: README, notes, every suite, the checks on the page and on real data

**Files:**
- Modify: `README.md` (step 8's section, about lines 196 to 210: the four panels and how they are opened and left, full screen and Esc, the three outlines, the two parts of the Lesson page, the three marks and what each means; "In two places" stays the counter's name)
- Create: `docs/superpowers/plans/2026-11-26-step8-side-by-side-notes.md`

- [ ] **Step 1: README.** Plain sentences, in the section's own style; no real name.
- [ ] **Step 2: Every suite, quick and slow.** Each `tests/test_*.py` and `tests/smoke.py` with `$PY`; each `tests/*.test.js` with `node`, one by one; `node --check static/app.js`; then `--full` on `tests/smoke.py`, `tests/test_combined.py`, `tests/test_fixes.py`, `tests/test_helper.py` and `tests/test_typed.py` (run the slow ones in the background; never stop a run by name). Expected: every one passes. A failure is fixed in the task that owns the code, not here.
- [ ] **Step 3 (controller): the browser, with a real mouse, on a made-up school.** A temporary launch entry on a scratch data folder, opened as `http://<name>.localhost:<port>`; the launch file is restored and compared afterwards. Every line of the spec's "How it is checked" for the browser, each with which kind of action it was (a real pointer action, or looked at). No drag is tried under an emulated window size.
- [ ] **Step 4 (controller): the school's real setup and timetable, counts only.** (a) For three classes of each level: for every row of `Board.panes`, the cards, lanes and codes equal those of that class's own cycle (`Board.groups`), and for every lesson of those classes `Board.states` on a pane's row equals it on the cycle's row. (b) For every lesson of those classes and every red place with no lesson of the class there: `fixes.place` gives a list exactly when `Busy.clash` gives a sentence; every id of a teacher, class or students line is a lesson that line's sentence names. Numbers only in the report; no name, no picture.
- [ ] **Step 5: The notes file:** each ruling made while building, known limits, what was and was not tried in the browser and by which kind of action, and the calls for the lead: the eleven at the end of the spec, and these made in this plan: "Tied to" lists the classes a teacher *also* teaches (the lesson's own class is left out); a band of one class lists its teachers; the lines of "Where it can go" with a count of 0 are left out; on thin rows the mark takes at most half the card.
- [ ] **Step 6: Commit** (`docs: README for step 8's four panels; the notes`)
- [ ] **Step 7: Whole-branch review** on the most capable model, against the spec and "What would make it a failure"; one fix wave; one re-review; Steps 2 and 4 again on the final code. Then merge `origin/main` in (other sessions change `static/app.js`) and run Step 2 once more. The pull request, the merge and the deploy each wait for the lead's own word.

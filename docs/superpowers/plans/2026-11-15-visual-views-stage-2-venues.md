# Visual views, stage 2: rooms by block, with equipment and configuration (step 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Step 1 (Venues) gets a second view, Blocks, that shows every room by block and floor and lets the committee add and change rooms there; a room can also carry a list of equipment and a line for its configuration, which are shown and never decide anything.

**Architecture:** A new pure module `static/venueview.js` (`VenueView`) turns the setup's rooms into a model of blocks, floors and rooms and suggests the next room's name; Node tests pin it. Two new fields on a room, `equipment` (a list of short texts) and `configuration` (one line), travel through the workbook's Venues sheet (two new columns at the end), the reader and the published room page. `static/app.js` draws the model and reuses the table's own change paths, as stage 1 did for classes.

**Tech Stack:** Vanilla JS in the browser (no build step), Node for the module's tests, Python (`ttgen`: openpyxl for the workbook, reportlab for the PDF) with plain-assert tests run by `.venv/bin/python`.

**Spec:** `docs/superpowers/specs/2026-11-15-visual-setup-views-design.md` (stage 2 and "Across all four stages"). Stage 1's plan and notes, for the patterns to repeat: `docs/superpowers/plans/2026-11-15-visual-views-stage-1-classes.md`, `…-stage-1-notes.md`. Branch `visual-views-stage-2`, from `main` at 85599d9.

## Global Constraints

- The Table view of step 1 is today's table plus two columns at its end (Equipment, Configuration). Nothing else in it changes.
- One set of data: a change made in the Blocks view goes through the same paths as the table's (`setPath` by `data-k`, the `data-names` handler for lists, the existing delete), one save, one Undo step. A room added from the Blocks view is added the way the "Add rooms" bar adds rooms.
- Equipment and configuration are only shown. No check, rule, "Will it fit?" test or Things to fix line reads them, and `ttgen`'s solver and checks do not either.
- The only new things stored are `equipment` (a list of strings) and `configuration` (a string) on a room, and a kind added to the school's own list of room kinds. No list of blocks or floors is stored: a block or a floor exists because a room names it.
- A workbook written before this stage opens with nothing lost (rooms have no equipment and no configuration). A workbook written by this stage and read back gives the same rooms. The two new columns are the last two of the Venues sheet, so no existing column moves.
- The skill's version becomes `2026-11.4` everywhere it is named (`ttgen/spec.py` `SKILL_VERSION`, `SKILL.md`, `README.md`, the test that pins it), and `skill/school-timetable-generator/scripts/ttgen/` stays byte for byte the same as `ttgen/` (`diff -rq` shows nothing).
- A timetable published before this stage still shows (a published model whose rooms have no `equipment` key must not break any page or PDF).
- The view is remembered per person in the browser, and the step opens on Blocks the first time.
- Department heads see both views and can change nothing on step 1; the view switch and Close still work for them.
- Nothing can be done only by dragging (this stage has no dragging).
- Everything a person typed is drawn through `esc()`, in text and in attributes.
- The open room is held by the row's own `_id` (found again on each draw), never by its place alone: the lesson of stage 1.
- No new style rule may match an element that existed before: every new class name is new to `static/style.css` and `static/app.js`.
- The school's size: about 90 rooms in 6 blocks. Sentences are plain and short, and name things as the page already does (Kind, Capacity, Block, Floor / level, For, Note).
- Tests, samples and documents use made-up names only. The school is "CTSS" or "the school". A run on the real setup reports counts only.
- Browser checks run on a scratch server with a scratch `DATA_DIR` and the README's example codes, never the repository's `data/`. No test or check calls a model API.
- Commits end with `Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>`. Nothing is pushed.

## Review Focus

1. **Rooms that are not tidy.** A room with no block, no floor, no name, no capacity, or a floor that is not a number ("G", "Mezz"); a `null` row; two rooms with the same name: every room shows exactly once, nothing throws. Pinned in Task 1 (`every_room_shows_once_whatever_it_lacks`).
2. **The next room's name.** After B2-3 comes B2-4; after L1-09 comes L1-10; a name already used anywhere is skipped; a room whose name does not end in a number, or an empty floor, suggests no name. Pinned in Task 1 (`the_next_room_follows_the_floors_pattern`).
3. **Old and new workbooks.** A workbook from before reads with no equipment; one written now reads back the same; an equipment item with odd characters (a slash, an ampersand, a quote, leading or trailing spaces) comes back as typed, less the spaces. Pinned in Task 2 (`equipment_and_configuration_survive_the_workbook`, `a_workbook_from_before_reads_with_no_equipment`).
4. **A published timetable from before.** A model whose rooms carry no `equipment` draws its room page and PDF as before, character for character. Pinned in Task 2 (the smoke test's "old model" part).
5. **Two people at once, and a head.** With a room open in one committee tab, another tab deletes a room above it (the open room stays the same room) and then that room (it closes). A head opens a room and can change nothing. Checked in a browser in Task 4.

---

### Task 1: The blocks model

**Files:**
- Create: `static/venueview.js`
- Test: `tests/venueview.test.js`

**Interfaces:**
- Consumes: nothing but the setup (`spec.venues`, `spec.classes`, `spec.school.room_kinds`).
- Produces: `VenueView.blocks(spec)`, `VenueView.nextRoom(spec, block, floor)`, `VenueView.nextFloor(spec, block)`, `VenueView.kinds(spec)`.

  ```js
  VenueView.blocks(spec) ->
  [{ block: "Block B", rooms: 5, seats: 198,
     floors: [{ floor: "2", rooms: [{ vi: 2, room: "B2-1", kind: "classroom", capacity: 40, home: ["2R1", "2R9"], only_for: ["Sec 3"],
                                      equipment: [], configuration: "", note: "" }] }] }]
  ```

  Rules the tests pin:
  - A room's block is its `building`, trimmed; its floor is `String(floor)`, trimmed (`1` and `"1"` are one floor). Every non-null row of `spec.venues` appears exactly once, with `vi` its index, `room` its name or `""`.
  - Blocks are in natural order of their names (numbers inside a name count as numbers, letter case ignored); rooms with no block are one last block with `block: ""`.
  - A block's floors: those that are numbers first, highest at the top; then the others in natural order; a floor of `""` last.
  - Rooms on a floor are in natural order of their names (B2-9 before B2-10).
  - `capacity` is a number or `null`; `seats` is the sum of the numbers; `rooms` on a block is its count.
  - `home` is the classes whose `home_room` is this room, in step 2's order. `only_for` and `equipment` are lists of strings (`[]` when absent); `configuration` and `note` are strings (`""` when absent); `kind` is the room's kind or `""`.
  - `nextRoom(spec, block, floor)` returns `{ room, kind, capacity }` for a room about to be added there: `kind` and `capacity` are those of the floor's last room (in the order above); `room` is that room's name with its last run of digits one higher, keeping the same width (09 gives 10), stepping on while the name is already used by any room; `room` is `""` when that name has no digits at its end. For a floor with no rooms: `{ room: "", kind: <the first of the school's kinds, or "classroom">, capacity: null }`.
  - `nextFloor(spec, block)` is the block's highest number floor plus one, as a string; `"1"` when it has none.
  - `kinds(spec)` is the school's own list followed by any kind found on a room that is not in it, in first-seen order, each once, no empty one.

- [ ] **Step 1: Write the failing tests**

`tests/venueview.test.js`, in the style of `tests/classview.test.js`:

```js
// Plain-assert tests for static/venueview.js (step 1's Blocks view): run with `node tests/venueview.test.js`
const assert = require("assert");
const VenueView = require("../static/venueview.js");
let n = 0; const t = (name, f) => { f(); n++; };
const fixture = () => ({
  school: { room_kinds: ["classroom", "lab", "computer lab", "music room"] },
  venues: [{ _id: "v1", room: "B1-1", kind: "classroom", capacity: 44, building: "Block B", floor: 1 },
           { _id: "v2", room: "B1-2", kind: "classroom", capacity: 44, building: " Block B ", floor: "1" },
           { _id: "v3", room: "B2-1", kind: "classroom", capacity: 40, building: "Block B", floor: 2, only_for: ["Sec 3"] },
           { _id: "v4", room: "B2-10", kind: "lab", capacity: 30, building: "Block B", floor: 2 },
           { _id: "v5", room: "B2-9", kind: "classroom", capacity: "40", building: "Block B", floor: 2 },
           { _id: "v6", room: "Music Room", kind: "music room", capacity: 30, building: "Block A", floor: 3, equipment: ["30 keyboards", "2 amps"], configuration: "cluster seating", note: "by the hall" },
           { _id: "v7", room: "Field", kind: "pe venue", capacity: "" },
           { _id: "v8", room: "A-G1", kind: "classroom", capacity: 20, building: "Block A", floor: "G" }],
  classes: [{ class: "4P1", home_room: "B1-1" }, { class: "2R1", home_room: "B2-1" }, { class: "2R9", home_room: "B2-1" }]
});
const names = b => b.floors.map(f => [f.floor, f.rooms.map(r => r.room)]);

t("blocks_in_natural_order_with_their_counts_and_no_block_last", () => {
  const B = VenueView.blocks(fixture());
  assert.deepStrictEqual(B.map(b => [b.block, b.rooms, b.seats]), [["Block A", 2, 50], ["Block B", 5, 198], ["", 1, 0]]);
});
t("floors_highest_first_then_the_named_ones_and_rooms_in_natural_order", () => {
  const B = VenueView.blocks(fixture());
  assert.deepStrictEqual(names(B[0]), [["3", ["Music Room"]], ["G", ["A-G1"]]]);
  assert.deepStrictEqual(names(B[1]), [["2", ["B2-1", "B2-9", "B2-10"]], ["1", ["B1-1", "B1-2"]]]);
  assert.deepStrictEqual(names(B[2]), [["", ["Field"]]]);
});
t("a_room_carries_what_the_tile_and_the_editor_show", () => {
  const B = VenueView.blocks(fixture());
  assert.deepStrictEqual(B[1].floors[0].rooms[0], { vi: 2, room: "B2-1", kind: "classroom", capacity: 40, home: ["2R1", "2R9"], only_for: ["Sec 3"], equipment: [], configuration: "", note: "" });
  assert.deepStrictEqual(B[0].floors[0].rooms[0], { vi: 5, room: "Music Room", kind: "music room", capacity: 30, home: [], only_for: [], equipment: ["30 keyboards", "2 amps"], configuration: "cluster seating", note: "by the hall" });
  assert.deepStrictEqual([B[1].floors[0].rooms[1].capacity, B[2].floors[0].rooms[0].capacity], [40, null]);   // "40" is 40; "" is none
});
t("every_room_shows_once_whatever_it_lacks", () => {
  const s = fixture();
  s.venues.push(null, {}, { room: "", building: "Block B", floor: 2 }, { room: "B1-1", kind: "classroom", building: "Block B", floor: 1 }, { room: "Loft", building: "Block B", floor: "Mezz" }, { room: "Hall", building: "block a" }, { room: "X", floor: 0, building: "Block B" });
  const B = VenueView.blocks(s), all = B.reduce((a, b) => a.concat(b.floors.reduce((x, f) => x.concat(f.rooms), [])), []);
  assert.strictEqual(all.length, 14); assert.deepStrictEqual(all.map(r => r.vi).sort((a, b) => a - b), [0, 1, 2, 3, 4, 5, 6, 7, 9, 10, 11, 12, 13, 14]);   // every row but the null one, once
  assert.deepStrictEqual(B.map(b => b.block), ["Block A", "block a", "Block B", ""]);                       // case is ignored for the order, not for which block a room is in
  assert.deepStrictEqual(B[2].floors.map(f => f.floor), ["2", "1", "0", "Mezz"]);
  assert.deepStrictEqual(B[2].floors[0].rooms.map(r => r.room), ["", "B2-1", "B2-9", "B2-10"]);            // a room with no name yet is first on its floor
  assert.deepStrictEqual(VenueView.blocks({}), []); assert.deepStrictEqual(VenueView.blocks({ venues: [null] }), []);
});
t("the_next_room_follows_the_floors_pattern", () => {
  const s = fixture();
  assert.deepStrictEqual(VenueView.nextRoom(s, "Block B", "1"), { room: "B1-3", kind: "classroom", capacity: 44 });
  assert.deepStrictEqual(VenueView.nextRoom(s, "Block B", 2), { room: "B2-11", kind: "lab", capacity: 30 });              // after the floor's last room, B2-10
  assert.deepStrictEqual(VenueView.nextRoom(s, "Block A", "3"), { room: "", kind: "music room", capacity: 30 });          // "Music Room" ends in no number
  assert.deepStrictEqual(VenueView.nextRoom(s, "Block C", "1"), { room: "", kind: "classroom", capacity: null });         // a new block: the school's first kind
  assert.deepStrictEqual(VenueView.nextRoom({ venues: [] }, "", ""), { room: "", kind: "classroom", capacity: null });
  s.venues.push({ room: "B1-3", building: "Block Z", floor: 9 }, { room: "b1-4", building: "Block Z", floor: 9 });
  assert.strictEqual(VenueView.nextRoom(s, "Block B", "1").room, "B1-5");                                               // names used anywhere are stepped over, whatever their case
  const p = { venues: [{ room: "L1-08", building: "L", floor: 1 }, { room: "L1-09", building: "L", floor: 1 }] };
  assert.strictEqual(VenueView.nextRoom(p, "L", "1").room, "L1-10");
});
t("the_next_floor_is_one_above_the_highest", () => {
  const s = fixture();
  assert.deepStrictEqual([VenueView.nextFloor(s, "Block B"), VenueView.nextFloor(s, "Block A"), VenueView.nextFloor(s, "Block C"), VenueView.nextFloor(s, "")], ["3", "4", "1", "1"]);
});
t("kinds_are_the_schools_list_then_any_other_found_on_a_room", () => {
  assert.deepStrictEqual(VenueView.kinds(fixture()), ["classroom", "lab", "computer lab", "music room", "pe venue"]);
  assert.deepStrictEqual(VenueView.kinds({ venues: [{ room: "A", kind: "" }, { room: "B", kind: "studio" }, { room: "C", kind: "studio" }] }), ["studio"]);
  assert.deepStrictEqual(VenueView.kinds({}), []);
});
console.log(n + " cases passed");
```

- [ ] **Step 2: Run it and see it fail**

Run: `node tests/venueview.test.js`
Expected: FAIL with `Cannot find module '../static/venueview.js'`

- [ ] **Step 3: Write `static/venueview.js`**

Same shape as `static/classview.js`: a header comment saying what it is and that it is pure; `var VenueView = (function () { "use strict"; … return { blocks: blocks, nextRoom: nextRoom, nextFloor: nextFloor, kinds: kinds }; })();` and `if (typeof module !== "undefined") module.exports = VenueView;`. Lookup tables keyed by typed names are `Object.create(null)` or a `Map`. One natural-order comparison (`localeCompare` with `{ numeric: true, sensitivity: "base" }`, a plain comparison as the tie-break so the order is the same on every machine) serves blocks, floors and rooms.

- [ ] **Step 4: Run the tests and see them pass**

Run: `node tests/venueview.test.js`
Expected: `7 cases passed`

- [ ] **Step 5: Commit**

```bash
git add static/venueview.js tests/venueview.test.js
git commit -m "feat(venues): the blocks model: rooms by block and floor, and the next room's name"
```

---

### Task 2: Equipment and configuration in the workbook and on the published room page

**Files:**
- Modify: `ttgen/template.py` (the `1 Venues` sheet, near line 227), `ttgen/reader.py` (venues, near line 164), `ttgen/export.py` (the model's `rooms` near line 90, `room_view` near line 495, the PDF's second line near lines 411 and 657), `ttgen/spec.py` (`SKILL_VERSION`)
- Modify: `skill/school-timetable-generator/SKILL.md` (the version line; the `1 Venues` row of the sheet table), and copy every changed `ttgen/*.py` to `skill/school-timetable-generator/scripts/ttgen/`
- Modify: `README.md` (the skill version it names), `tests/test_parents.py` (the test that pins the skill version)
- Create: `tests/test_venues.py`
- Modify: `tests/smoke.py` (one test)

**Interfaces:**
- Consumes: `template.write_template(spec, path)`, `reader.read_template(path)` (as `tests/test_parents.py` uses them; a sheet's headings are on row 5), `ttgen.samples.secondary()`, `export.room_view(m, room)`, `export.pdf_bytes(m, view)`, `export.html_data(m)`, and the smoke test `test_published_pages_name_the_class_parents` as the pattern for publishing in a test.
- Produces:
  - On a room in the setup: `equipment` (list of strings) and `configuration` (string).
  - Venues sheet: after "For (subjects, departments or levels)", the columns "Equipment" and "Configuration", both typed (input) columns. Equipment is the items joined with ", "; an empty list or missing value writes an empty cell.
  - `read_template`: every room has `equipment` (a list; `[]` when the column is missing or the cell empty; items trimmed, empty ones dropped) and `configuration` (the cell's text trimmed, or `None`).
  - The published model's `rooms` entries gain `equipment` (list) and `configuration` (string, `""` when none).
  - `room_view(m, r)`: `subtitle` is today's text plus, when the room has them, ` · Equipment: 30 keyboards, 2 amps` and ` · Configuration: cluster seating` in that order; `pdf_subtitle` is today's text alone; the PDF draws the added part on its own line or lines under the subtitle, wrapped between items and never cut, the way the Class Parents line is drawn (the grid moves down only on pages that have the line). A room with neither has exactly today's `subtitle` and no extra line.
  - `SKILL_VERSION == "2026-11.4"`.

- [ ] **Step 1: Write the failing tests**

`tests/test_venues.py`, plain asserts in the style of `tests/test_parents.py` (a `t` decorator that counts, last line `print(f"{n} checks passed")`), with these cases:

```python
def setup():
    sp = secondary(); v = sp["venues"]
    v[0]["equipment"] = ["30 keyboards", "2 amps"]; v[0]["configuration"] = "cluster seating"
    v[1]["equipment"] = ["  PCs / laptops & chargers ", "", 'a "smart" board']; v[1]["configuration"] = "  rows of 8  "
    return sp

@t
def equipment_and_configuration_survive_the_workbook():
    sp = setup(); p = write(sp); back = reader.read_template(p)["venues"]
    assert headings(p, "1 Venues")[-3:] == ["For (subjects, departments or levels)", "Equipment", "Configuration"], headings(p, "1 Venues")
    assert back[0]["equipment"] == ["30 keyboards", "2 amps"] and back[0]["configuration"] == "cluster seating"
    assert back[1]["equipment"] == ["PCs / laptops & chargers", 'a "smart" board'] and back[1]["configuration"] == "rows of 8"
    assert back[2]["equipment"] == [] and not back[2]["configuration"]
    again = reader.read_template(write(reader.read_template(p)))["venues"]                    # a second trip changes nothing
    assert [(x["room"], x["equipment"], x["configuration"]) for x in again] == [(x["room"], x["equipment"], x["configuration"]) for x in back]

@t
def a_workbook_from_before_reads_with_no_equipment():
    sp = setup(); p = write(sp, drop=("1 Venues", ["Equipment", "Configuration"])); back = reader.read_template(p)
    assert all(x["equipment"] == [] and not x["configuration"] for x in back["venues"]) and len(back["venues"]) == len(sp["venues"])
    keep = lambda v: [(x["room"], x.get("kind"), x.get("capacity"), x.get("building"), x.get("floor"), x.get("only_for") or [], x.get("note")) for x in v]
    assert keep(back["venues"]) == keep(reader.read_template(write(secondary()))["venues"])     # everything else as a plain setup gives it

@t
def the_other_columns_of_the_venues_sheet_have_not_moved():
    a = headings(write(secondary()), "1 Venues")
    assert a[:8] == ["Room", "Kind", "Capacity", "Block", "Floor / level", "Used by lessons", "Note", "For (subjects, departments or levels)"], a

@t
def equipment_decides_nothing():
    import checks                                              # the app's own list of findings for a setup (checks.py at the repository's root)
    assert checks.findings(setup()) == checks.findings(secondary())
```

`from ttgen.samples import secondary`, `from ttgen import reader, template`, and the repository's root on `sys.path` (as `tests/test_parents.py` sets it) so that `import checks` works.

The skill version: rename `the_skill_version_is_2026_11_3` in `tests/test_parents.py` to `the_skill_version_is_2026_11_4` and change its three strings to `2026-11.4`.

`write(sp, drop=None)` and `headings(p, sheet)` are small helpers of this file (copy the shape of the ones in `tests/test_parents.py`; `drop=(sheet, [headings])` deletes those columns from the written workbook).

In `tests/smoke.py`, a test `test_a_published_room_page_shows_its_equipment`, modelled on `test_published_pages_name_the_class_parents` (same helpers to start a setup, upload a draft and publish): give one room that the published timetable uses `equipment` `["30 keyboards", "2 amps"]` and `configuration` `"cluster seating"` through the same change route the page uses, publish, then assert:
- `m = store.published()["model"]`; that room's entry in `m["rooms"]` has the two values; another room has `[]` and `""`;
- `export.room_view(m, room)["subtitle"]` ends with `" · Equipment: 30 keyboards, 2 amps · Configuration: cluster seating"`, and its `pdf_subtitle` is the subtitle without that ending;
- for a room with neither, `subtitle` is exactly what it is on `main` (kind, capitalised, and " · holds N" when it has a capacity) and the view draws no extra line;
- `c.get("/pdf/rooms/<room>")` is 200 and a PDF;
- an old model (a pickled copy of `m` with `equipment` and `configuration` popped from every room) gives `room_view` subtitles equal to the plain ones and `export.pdf_bytes` a PDF;
- twelve long equipment items (each 30 characters) still give a PDF, and the lines drawn for them are each no wider than the subtitle's width (the same measure the Class Parents test uses).

- [ ] **Step 2: Run them and see them fail**

Run: `.venv/bin/python tests/test_venues.py; .venv/bin/python tests/test_parents.py | tail -1; .venv/bin/python tests/smoke.py 2>&1 | tail -3`
Expected: `test_venues.py` fails at the headings assertion; `test_parents.py` fails on the version; smoke fails in the new test.

- [ ] **Step 3: Implement**

`ttgen/template.py`: two columns after "For…" (widths about 34 and 24), both in the sheet's set of input columns, painted with the rest; the sheet's intro line gains one sentence: "Equipment and Configuration are notes about the room: the timetable does not read them." `ttgen/reader.py`: read the two by heading. `ttgen/export.py`: the model's rooms, `room_view`, and the PDF's second line (make the Class Parents line's drawing serve any view's second line; a class, teacher or student page must come out exactly as before). `ttgen/spec.py`: the version. `SKILL.md`: the version line, and in the `1 Venues` row add "Equipment, Configuration (notes only: never read them as constraints)". `README.md`: the version. Then copy the changed `ttgen` files into the skill's copy.

- [ ] **Step 4: Run the tests and see them pass**

Run: `.venv/bin/python tests/test_venues.py && for t in test_parents test_rules test_verify test_choices test_fixes test_helper test_typed test_sync; do .venv/bin/python tests/$t.py | tail -1; done; .venv/bin/python tests/smoke.py 2>/dev/null | tail -1; diff -rq ttgen skill/school-timetable-generator/scripts/ttgen | grep -v __pycache__`
Expected: `4 checks passed`; every other suite as before; smoke `90 checks passed`; `diff` prints nothing.

Run: `.venv/bin/python tests/smoke.py --full 2>/dev/null | tail -1`
Expected: `91 checks passed`

- [ ] **Step 5: Commit**

```bash
git add ttgen skill tests/test_venues.py tests/test_parents.py tests/smoke.py README.md
git commit -m "feat(venues): equipment and configuration on a room: in the workbook, read back, and on the published room page"
```

---

### Task 3: Step 1's view switch, the table's two columns, and the Blocks view to look at

**Files:**
- Modify: `static/index.html` (load `venueview.js` after `classview.js`)
- Modify: `static/app.js` (`VIEWS.venues`, the click handler, `headLocks`)
- Modify: `static/style.css`
- Modify: `README.md` (the test list; step 1's paragraph)

**Interfaces:**
- Consumes: `VenueView.blocks(S.spec)`, `VenueView.kinds(S.spec)` (Task 1); in `app.js`: `VIEWS.venues()` (near line 1113), `issues()` and `rowCls(out, crit, "venues", vi)`, `inp`/`sel`, the `data-names` change handler (a comma-separated box that saves a list), `esc`, `locked("venues")`, and stage 1's step 2 code as the pattern (`CLASSVIEW`, `CV`, `data-cview`, `classesTable()`, the `headLocks` exemptions).
- Produces (Task 4 relies on these names):
  - `const VENUEVIEW = "ttsetup.view.venues"` and `const VV = { view: "blocks", open: null, openId: null, draft: null }`; `VV.view` is `"blocks"` or `"table"`, read from `localStorage` at load (anything else means `"blocks"`), written on a switch, both inside try/catch.
  - The switch: `<div class="switch">` with two buttons `data-vview="blocks|table"`, labelled Blocks and Table. A click sets `VV.view`, stores it, closes any open room and re-renders. On a locked step these buttons stay usable.
  - `venuesTable()`: today's table with two more columns before the delete button: Equipment (`<input data-names="spec.venues.${i}.equipment">` showing the items joined with ", ", placeholder "none") and Configuration (`inp("spec.venues.${i}.configuration", v.configuration)`).
  - `venuesBlocks()`: the Blocks view, in this task without any way to change a room.
  - Each room's tile is a `<button class="vtile …" data-vroom="{vi}" id="venues-{vi}">`; in this task a click does nothing yet.

What the Blocks view shows (the spec's "Blocks" list is the authority):
- One panel per block from `VenueView.blocks`: its name ("No block yet" for `""`), "{n} rooms · {seats} seats".
- Inside, one row per floor: a label ("Floor 2"; the floor's own word when it is not a number, such as "G"; "No floor yet" for `""`), then the floor's tiles.
- A tile: the room's name ("(no name yet)" when empty); its kind as a small coloured mark and the word; its seats when it has a number; then one line: "Home of 2R1, 2R9" when it is a home room, else "Kept for Sec 3" when it has a For list, else nothing. A small mark shows when the room has equipment or a configuration. A room under Things to fix carries the table row's mark class.
- Kinds and colours: the kinds the app ships with (classroom, lab, science room, computer lab, art room, d&t studio, food lab, music room, pe venue, hall, special room) each have a fixed colour and a short mark of their own (a two-letter mark or an inline shape; no icon font, nothing fetched); any other kind gets one neutral colour. A legend under the switch lists the kinds in use.
- With no room yet: one line, "No rooms yet. Add them with the bar above, or switch to Table."
- The "Add rooms" bar of today stays above both views.

- [ ] **Step 1: Move the table into `venuesTable()`, add its two columns and the switch**; `VIEWS.venues()` chooses by `VV.view`. Load `venueview.js` in `index.html`.

- [ ] **Step 2: Check nothing else moved**

Run: `node --check static/app.js && .venv/bin/python tests/smoke.py 2>/dev/null | tail -1`
Expected: no syntax error; `90 checks passed`

- [ ] **Step 3: Write `venuesBlocks()` and its styles** (new class names only; none may exist already in `static/style.css` or `static/app.js`: grep each before using it).

- [ ] **Step 4: Run every page-side suite**

Run: `node --check static/app.js && for f in tests/*.test.js; do node $f | tail -1; done && .venv/bin/python tests/smoke.py 2>/dev/null | tail -1`
Expected: every line ends "passed"; `venueview.test.js` 7; smoke 90.

- [ ] **Step 5: README**: add `node tests/venueview.test.js   # step 1's blocks view` and `.venv/bin/python tests/test_venues.py   # equipment and configuration through the workbook` to the test list, and two sentences on step 1's two views and the two new notes on a room.

- [ ] **Step 6: Browser check on a scratch server** (the secondary sample school, committee; then a head), written into the task report:
  1. Step 1 opens on Blocks; every room of the Table is on exactly one tile (compare the counts); the choice survives a reload.
  2. In the Table, type "30 keyboards, 2 amps" under Equipment and "cluster seating" under Configuration for one room: the tile shows the mark; the two boxes keep their text after a reload; Undo takes each back in one step.
  3. Download the workbook (step 7): the Venues sheet has the two columns with those values. Open it again from the Start step: the room still has them.
  4. A room with no block and one with no floor show under "No block yet" and "No floor yet".
  5. Rename a room to `B<i>1"x` and a block to `Blk <b>&`: both show as typed in both views.
  6. As a department head: both views show and switch, the Table's boxes are disabled, and "Only the committee can change this step." shows.
  7. School & day's Brush legend and step 2's three views look as before (no style of this task reaches them), and the console has no error.

- [ ] **Step 7: Commit**

```bash
git add static/index.html static/app.js static/style.css README.md
git commit -m "feat(venues): step 1 in two views; rooms by block and floor, and two notes on a room in the table"
```

---

### Task 4: Changing rooms from the Blocks view

**Files:**
- Modify: `static/app.js`, `static/style.css`, `README.md` (one sentence)

**Interfaces:**
- Consumes: Task 3's `VV`, `venuesBlocks()`, `data-vroom`; `VenueView.nextRoom`, `VenueView.nextFloor`, `VenueView.kinds` (Task 1); in `app.js`: stage 1's `cvOpen`/`cvResolve` (the pattern for holding an open row by `_id`), `delBtn("venues", vi)`, `setPath`, `save()`, the way the "Add rooms" bar adds rooms (the `k === "venues"` branch near line 1601), the `.issue` click handler (stage 1 made it open a class's card), `sc().room_kinds`.
- Produces: `vvOpen(vi)` and `vvResolve()` (the open room held by `_id`, as `cvOpen`/`cvResolve` do; factor the two pairs into one helper if that is cleaner, without changing step 2's behaviour); `data-vclose`, `data-vadd="{block}|{floor}"`, `data-vfloor="{block}"`, `data-vblock`, `data-vkind`.

What it does (the spec's "Blocks" list is the authority):
- **A click on a tile opens the room** in place, under its floor's row (one room open at a time): name, kind, seats, block, floor, For and note with the same `data-k` and `data-names` paths as the table row; Equipment (the `data-names` box) and Configuration; the table's own Delete (it asks as the table's does) and a Close button. A room under Things to fix shows its messages there.
- **New kind…** is the last choice of the open room's Kind box. Choosing it shows a small box for the kind's name and an Add button: Add puts the name at the end of the school's list of kinds (if it is not there already, compared without regard to case) and gives it to the room, in one save. An empty name, or Close, leaves everything as it was.
- **"+ Room"** at the end of each floor's row adds a room there in one save: block and floor as that row's, and name, kind and seats from `VenueView.nextRoom`; the new room is opened so its name and the rest can be changed at once. When the suggestion has no name, the room is added with an empty name and its Name box has the focus.
- **"+ Floor"** on a block adds a room on a new floor of that block (`VenueView.nextFloor`) the same way, and **"+ Block"** under the panels asks for the block's name in a small box and adds a room on its floor "1". A floor or a block is never added without a room.
- Changing the open room's block or floor moves its tile to its new place and keeps it open.
- A click on a Things to fix message for a room, on the Blocks view, opens that room there and scrolls to it. On the Table nothing changes.
- On a locked step (a head): a tile opens, every field in it is disabled, Close and the view buttons work; "+ Room", "+ Floor", "+ Block" and Delete are disabled.
- Keyboard: tiles and every button are reachable and usable without a mouse; Escape closes the open room.

- [ ] **Step 1: Write the open room, its handlers and styles.**

- [ ] **Step 2: Write "+ Room", "+ Floor", "+ Block" and "New kind…".**

- [ ] **Step 3: Run every suite**

Run: `node --check static/app.js && for f in tests/*.test.js; do node $f | tail -1; done && .venv/bin/python tests/smoke.py 2>/dev/null | tail -1`
Expected: every line ends "passed"; smoke 90.

- [ ] **Step 4: README**: one sentence on adding and changing rooms from the Blocks view.

- [ ] **Step 5: Browser check on a scratch server** (the secondary sample, committee, two tabs; then a head), written into the task report:
  1. Open a room, change its seats and its kind: the Table shows the same; Undo takes each back in one step.
  2. "+ Room" on a floor whose last room ends in a number: the new room has the next number, the same kind and seats, and is open. One Undo removes it.
  3. "+ Floor" on a block, then "+ Block" with the name "Block Z": each adds one room where it should, open, with one Undo step each.
  4. "New kind…" with "dance studio": the room has it, School & day's list of kinds ends with it, and step 3's Room kind box offers it. Adding "Dance Studio" again adds nothing new.
  5. Change the open room's floor to another floor: its tile moves and it stays open on the same room.
  6. Two tabs: with a room open in one, delete a room above it (in the table's order) in the other: after the poll the open room is still the same room. Then delete that room in the other tab: the open room closes.
  7. A Things to fix message about a room (give two rooms the same name to get one): a click opens that room on Blocks with the message showing.
  8. As a head: a tile opens with every field disabled; "+ Room", "+ Floor", "+ Block" and Delete are disabled; Close works.
  9. Delete the open room and Undo: the room is back in its place. No console error at any point.

- [ ] **Step 6: Commit**

```bash
git add static/app.js static/style.css README.md
git commit -m "feat(venues): add and change rooms from the blocks view; a school's own room kinds"
```

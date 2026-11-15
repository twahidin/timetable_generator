# Visual views, stage 2: decisions made while building, and what was left

From the build ledger of `2026-11-15-visual-views-stage-2-venues.md`. Built subagent-driven on 2026-11-15 (a fresh implementer per task, a reviewer per task, one whole-branch review, one fix) on branch `visual-views-stage-2` from `main` at 75e8593.

## What was built

Step 1 (Venues) has two views, switched at the top right: Blocks and the Table. Blocks shows a panel per block, a row per floor and a tile per room; a click opens a room in place to change it; "+ Room", "+ Floor" and "+ Block" add rooms; "New kind…" adds a kind of room to the school's own list. A room can carry equipment (a list of short texts) and a configuration (one line). They are only shown: in both views, in the workbook's Venues sheet (two new last columns), and on the published room page (web, Excel and PDF). The skill's version is 2026-11.4. A new pure module, `static/venueview.js`, works out the blocks and the next room's name.

## Rulings (decisions made where the plan was silent or wrong)

The plan's own gap

- The published web page builds a room's header itself, in `ttgen/timetable_page.html`, from a short row of data. The plan changed only the server-side view, so the equipment would have reached the PDF and the Excel file and not the page teachers open. Found by the controller while checking a reviewer's question. The page's data rows for rooms now carry the equipment and the configuration as a fourth and fifth element, and the page shows them; a page made from older data (three elements) still draws.

The model

- The next room's name is worked out on the digits as text, not as a number: a name ending in twenty digits made the first version run for ever, which on the page would have frozen the tab. It gives up after 1,000 names in a row are found used, and then suggests no name. Found at the task review.
- A school's list of kinds that is not a list counts as no list; a room name with a space at its end still gives the next name.
- A floor is the text as typed: "1" and 1 are one floor, but "02" and "2" are two rows.

The workbook and the published pages

- An equipment item cannot hold a comma: the comma separates items, in the page's box and in the workbook's cell, as it does for "For".
- The Excel sheet for a room decides which figures to repeat in its heading by looking at the short subtitle, not the long one. With the long one, "30 keyboards" hid "30 periods used". Found at the task review.
- On the printed room timetable the notes wrap between items and at the join between the equipment and the configuration, and take at most six lines, the last ending with "…". Each line moves the grid down, and a pasted inventory of 120 items left the grid almost no height. The web page and the Excel file hold the whole list. Form teachers are still never cut, however many. Found at the whole-branch review; fixed by the controller, test first, and not seen by a second reviewer.
- The test that pins the skill's version in `tests/test_rules.py` was changed too; the plan named only the one in `tests/test_parents.py`.

The page

- A floor or a block is never stored on its own: "+ Floor" and "+ Block" each add one room there. A half-typed block name or kind name is held on the page only, and nothing is saved until Add.
- "New kind…" compares names without regard to case, and puts the new kind on the school's list and on the room in one save, so one Undo takes both back.
- The pair of block and floor that "+ Room" carries is encoded, so a block or floor name holding a bar or a quote cannot be split wrongly.
- The open room is remembered by the room row's own id, as the open class card is. The two share one helper now (`heldOpen`, `heldResolve`); step 2's code was compared with the old line by line and driven again in a browser at the whole-branch review.
- A department head can open a room and read it. Every field, "+ Room", "+ Floor", "+ Block", "New kind…" and Delete are disabled; the new branches also check the lock themselves; and the server refuses a head's change to rooms or to the school's kinds.
- A click on a Things to fix message for a room opens that room on Blocks.
- Step 1's opening paragraph gained one sentence: "Equipment and Configuration are notes for people: nothing checks them."

## Checked at the whole-branch review

On the school's real setup (counts only): 73 rooms. Three named blocks hold 42 of them; 31 rooms have no block and no floor yet, and show under "No block yet". Nine floor rows. Ten kinds on the school's list, and no room has a kind outside it. Every room shows exactly once; the seat totals, home classes and floors match a plain count. A next name is suggested on 8 of the 9 floor rows, and none is a name already used. The model takes under 15 ms.

The workbook: with three rooms given notes, the notes come back, and not one row of any sheet (rooms, classes, subjects, teachers, bands, lessons, rules) differs from a plain read, write and read. Today's workbook, written before this stage, reads with no equipment and no error. The reader and the check of the skill as it was before this stage take a workbook written now, ignoring the two new columns.

The published pages, built from the outside agent's timetable of 10 November: rooms with equipment show it; all 73 rooms' data rows have five elements; the PDF builds with 12, 40 and 120 items. A published timetable from before, with none of this in it, still gives its PDF, its Excel file and its page.

The real page: Blocks drew in 22 to 43 ms, the Table in 34 to 41 ms, and opening a room took 21 to 25 ms. 73 tiles for 73 rooms. No script error.

In a browser, by the reviewer, all seen and right: step 2 after its helper was shared (open a card, change it, Undo, a Class Parent, add, delete, two tabs, Bands, a Things to fix click); a real department-head sign-in on step 1 (reads everything, changes nothing, the setup's version unchanged); two committee tabs on step 1 (the open room stays the same room when one above it is deleted, and closes when it is deleted); a room and a block with markup in their names; School & day, step 3, step 5 and step 8.

No real name and no full school name is in the diff or the commit messages.

## Known limits, ruled to stand

- The page's drawing code has no automated test: the repository tests page code in a browser. The model has 10 tests, the workbook and published pages 4 and one long smoke test.
- The outside agent's skill as it was before this stage was run on a new workbook only as far as its reader and its check, not its solver.
- Nothing under Things to fix says that a room has no name. "+ Room" makes such a room when it has no name to suggest (the floor's last room does not end in a number), with the Name box ready to type in.
- The look of the Blocks view on the school's real rooms was not looked at by eye: no screenshots of real data were taken.

## Deferred minor points

The model

- A negative capacity is subtracted from a block's seats; "0x10" and "1e3" read as numbers.
- A room added after a room with no kind gets an empty kind where the table stores none.

The workbook and the published pages

- Text beginning with "=" in a typed cell is written to the workbook as a formula (so is Note, before this stage).
- The workbook's reader also splits a list at ";" and at line breaks, the page's box only at commas, so "keyboards; amps" typed on the page is two items after a trip through the workbook (so is "For", before this stage).
- On a class, teacher or student Excel sheet, a figure whose number appears only in the Class Parents line now shows where it was hidden before.
- The smoke test checks that the PDF builds and that its lines fit, not the text inside the PDF.

The page

- A school's list of kinds that is not a list (only a hand-made setup file can hold one) blanks step 1 through the "Add rooms" bar, as before this stage; the open room and "New kind…" share the weakness.
- The open room's Kind box offers the school's list only, as the Table does, not kinds found on other rooms. A plain change of kind writes the room directly and does not ask the server for others' changes at once.
- Switching views leaves a half-typed "+ Block" or "New kind…" box behind; a stale one uses up the next Escape.
- After "+ Room" with a suggested name the keyboard focus is lost. "+ Block" with the name of an existing block adds a room to that block without a word.
- A tile with no kind says "no kind".

## Not exercised in a real browser

Not tried in a browser: saving the downloaded workbook to disk and opening it again by hand (the round trip was done through the server's own routes and, on real data, through the reader and writer); the printed PDF looked at by eye with a six-line block; a window narrow enough to wrap a floor's tiles onto many lines; the committee's own site (it has this only after a merge and "Deploy Latest Commit").

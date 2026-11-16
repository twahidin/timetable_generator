# Upload and edit, stage 2: decisions made while building, and what was left

From the build ledger of `2026-11-16-upload-and-edit-stage-2-board.md`. Built subagent-driven on 2026-11-16 (a fresh implementer per task, a reviewer per task, one whole-branch review, one fix wave and its re-review, then one narrow correction and its re-review) on branch `upload-and-edit-stage-2`, cut from `upload-and-edit` (stage 1) at 7857d82. Design: `docs/superpowers/specs/2026-11-16-upload-and-edit-design.md` (stage 2 of 4). The committee lead said "continue the rest of the stages" after stage 1; the plan was not read by them before the build.

## What was built

Step 8 has a board between the upload card and the warnings. It shows one day of the whole school: a row for each class under its level, the periods across with their times, a card for each lesson coloured by its subject's department. A band is a piece in each of its classes' rows, saying the band's name and how many groups it has. Two lessons of one class at the same time are stacked in the row. A level folds shut. The day is chosen from tabs, grouped by week.

A click on a class's name opens that class's whole cycle: a row for each day. "All classes" goes back to the day that was shown. "Find a subject" (a department or a subject) fades every other card in both views.

A lesson is moved by dragging its card along its row, or by a click on it and then a click on a place. Only what the app already allowed can be done: a move or a swap judged clean, or one that only bends a rule. While a card is selected or in the air a thin strip over each of its rows shows every period it could start at: green clean, amber bends a rule, red clashes, grey cannot take it. A lesson it can be swapped with has a dashed outline; a click or a drop anywhere on it asks "Swap A with B (day period)?" with Swap and Cancel. A place that is refused says why. "Undo the last timetable change" takes the last change back. Every change is still one entry in the draft's list of fixes, made by the same route and judged by the same code as the Fix card's.

The warnings list, the Fix card, the helper and the typed box are in a card of their own below the board, unchanged. A selected card has "Teacher, room and more", which opens the Fix card on that lesson.

The server has two new read-only answers: the whole timetable as cards (`GET /api/draft/board`, gzip'd) and where one lesson fits (`GET /api/draft/slots?id=`). `static/board.js` holds the layout and the answers to a drag as plain functions, with `tests/board.test.js`; the server half is tested by `tests/test_board.py`.

Every upload now has its own identity (`upload_id` in the draft's meta), so a page tells two uploads made in the same minute apart.

## Rulings (decisions made where the plan was silent or wrong)

The plan's own calls, not yet confirmed by the committee lead

- The board sits between the upload card and the warnings list; the old editor stays below it and is where a teacher or a room is changed until stage 4.
- A band is drawn as a piece in each of its classes' rows, not as one tall card. A band's classes are often not next to each other.
- One class's whole cycle is the same board turned: a row for each day. A card dragged to another day's row there changes its day.
- In the day view a card can only be dropped on its own class's row (for a band, any of its classes' rows).
- A class on the timetable that is not in the setup has a row under "Not in the setup", and a lesson with no class a row "No class".
- Moving a lesson to another day from the day view is done by selecting it, changing the day's tab and clicking a place. Dropping on a day's tab is stage 3.
- Periods are numbered as the rest of the app numbers them (from 0).

Where a card fits

- The plan coloured the row's cells. On a full day every open period lies under a card, so nothing could be seen. A strip of marks above each row's cards shows it instead, and the cells keep their colours where they can be seen.
- A swap can be started by a click: a lesson with a dashed outline, clicked while another is selected, asks the Swap question. A click on any other card selects that card. The plan had every click on another card select it.
- A drop anywhere on a dashed lesson aims at the swap, not only a drop that lines the two starts up.
- The Swap question names both lessons. The plan's wording was "with the lesson on (day period)".

Dragging

- A drop made before the app has worked out where the card fits waits for the answer and is then judged. Before this, a quick drag was refused with "Still working out where this lesson fits."
- A new draft arriving while a card is in the air does not end the drag: the old showing is cleared, the new one fetched, and the drop is judged against the new draft.
- A pointer over the row's label is not on a period.
- Escape is left alone when the keyboard is in a field, and while a drop is waiting.

The page

- The board fetches again whenever the draft it was fetched for is not the current one (the upload's identity, the list of fixes, the setup's version), from every place the page takes a new draft.
- A new upload clears the selection, since lesson ids start again.
- The board's undo button reads "Undo the last timetable change", so it is not taken for the top bar's "Undo the last change", which undoes the setup. Ctrl+Z on step 8 is still the setup's undo.
- A click or a drop while a change is being saved says "Wait for the last change to finish." A Swap question withdrawn because the timetable changed says "The timetable changed. Ask again."

The build itself

- For the browser checks the sample secondary school was solved with the repo's own solver (no model call), which gives a timetable with bands, ten days and 26 periods.
- Two builders reported checks as passing that they had made with clicks and drags sent from the console; a real mouse then behaved differently twice. From then on the checks that matter were made with real pointer actions, by the builder and again by the controller.
- The process allows one fix wave after the whole-branch review. This build made one more, narrow correction with its own review: the upload's identity. A page could not tell two uploads in the same minute apart, and the board would have kept showing the first file's lessons. The weakness is older than this branch; the board is what made it matter.

## Checked on the real files (counts and timings only)

- The newest returned timetable: 994 cards holding all 1,954 lesson rows, 300 of them bands, 32 classes; no card without a row. The board's data is built in about 0.1 s the first time and is 33 KB to send. Where a lesson fits: 0.05 s in the middle, 0.10 s at worst.
- In a browser on that timetable: 32 rows and 187 pieces on a day; the step opened to the first row in 104 ms; a full redraw of the board 15.5 ms; a change of day 16 ms; from pressing a card to its showing 102 ms.
- The returned timetable of 10 November: 1,018 cards holding all 1,948 rows; 38 cards lie on a break or outside the day and are drawn where they are.
- Stage 1's counts are unchanged: 145 warnings and 99 critical on the 10 November file, 198 and none on the newest.
- No commit holds the school's full name or a real teacher's full name.

## Left as it is

- A refusal from before a colleague's change can be said once if a drag ends in the instant after that change lands.
- When the dragged lesson was deleted by someone else mid-drag the page says "Where this lesson fits could not be loaded. Click the lesson again." where "The timetable changed" would be truer.
- There is no keyboard way to move a lesson yet. Cut and paste from the keyboard is stage 3.
- A place that is clean while another lesson is there without a swap (two groups of one class at once) is reached through the strip or a drag only.
- Grey means both a break and "cannot take it". There is no dark mode, as on the rest of the page.
- "Teacher, room and more" for a class that is not in the setup opens whatever the Fix card does for it.

## Deferred minors

- Keyboard focus is lost when the board redraws (a day's tab, a fold, Find).
- No automated test of the board's page code: the pointer maths, the drag's states, the swap question. It was checked in a browser with real pointer actions.
- A change of the setup's classes, levels or day structure by someone else redraws the board only when the setup's version in the draft answer changes or the step is opened again.
- While the board's fetch keeps failing, every opening of step 8 tries again and shows another message.
- `draftHTML` is built three times for one drawing of step 8.
- A slots fetch that never answers leaves that card waiting until the next board fetch; a failed aside fetch is not retried on a second press; every press on a card that is not selected asks the server once.
- A Swap question with several "this also moves" sentences can be taller than the line kept for it and nudge the board.
- An error inside the page after a successful move is reported as "Could not reach the server".
- `draft.slots` and `draft.options` take `True` or `1.5` as a lesson id; the routes only pass strings.
- Tests not written: three or more lessons at once in one row; a lesson starting before the first period.
- The README has one older line of 968 characters.

## Next

Stage 3 is forcing and Not placed (a forced move, push out, the tray, cut and paste, a drop on a day's tab, the counters, the red marks). Stage 4 is rows by teacher and by room and the card's teacher and room lists. Each needs its own plan.

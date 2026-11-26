# Step 8: four panels, full screen, what a lesson is tied to: notes

Notes beside the plan `2026-11-26-step8-side-by-side.md` and the design `../specs/2026-11-26-step8-side-by-side-design.md`.
Built 2026-11-26 on branch `step8-side-by-side`, Subagent-driven (the lead's choice): a fresh builder and a fresh reviewer a task, the
controller's own look in a browser after each page task, one whole-branch review on the most capable model, one fix round, one
re-review.

## What was built

1. The server names the lessons in the way: each collision line of `Busy.whys` carries `ids`; `fixes.place` (so
   `GET /api/draft/place`) lists a red place's collisions too. `fixes.slots` is unchanged.
2. `static/board.js`: the panels' sums (`panels`, `panelsFor`, `panelsWith`, `panelSet`, `panelPut`, `panelShow`, `panes`, `lane`,
   `ownRows`, `andList`), the judgements (`tied`, `blockers`), and the Lesson page's counts (`tally`, `ties`). All plain functions,
   tested in `tests/board.test.js`.
3. The four panels on step 8: the mode `{kind: "cycle", cls, panels, d}`, drawn by the functions that draw one class's cycle.
4. Full screen: the timetable card fixed over the browser window.
5. The outlines (same teacher, same room, the fade, the lessons that block a red place) and their key.
6. The Lesson page's "Where it can go" and "Tied to"; the mark reading Teacher / Class / Room in two places.
7. README.

## Rulings made while building (each can be undone)

- **Four panels with a lesson chosen keeps the lesson.** The design opens the stored panels and lets go of a lesson whose class is
  not shown. Together these meant: choose a lesson, press Four panels, and the lesson is let go. Now its class goes into the first
  empty panel, and with none empty it takes the third panel's place (`Board.panelsWith`). If wrong: one list choice brings the third
  class back.
- **The Four panels button is on every one-day board and whole cycle**, Teachers and Rooms rows included. The design's Part 1 says
  "when the rows are Classes"; its call 10 says "Four panels brings them back" after "Show me" on a teacher in two places, which
  lands on the Teachers rows. The call is what the lead was told.
- **The class panels are tighter than the mock-up**: the week heading, the fit strip and the panel's head line were trimmed (the
  design does not fix them) so that both weeks fit a smaller window. The start times under every third period stay.
- **"Tied to" lists the classes a teacher also teaches**: the lesson's own class is left out. A band of one class lists its
  teachers; a band of two or more says "This lesson is one band. It moves in … at the same time."
- **"Where it can go" leaves out a line whose count is 0**, and has no heading until the lesson's places are here.
- **No Show button for a class the setup lacks** (a class on the timetable that step 2 does not have).
- **A wet-weather room's collision line names only the lessons in the room**, not the lessons that share it as their wet-weather
  room (two lessons that share a wet-weather room are not in each other's way).
- **A panel's list changed during a drag or a waiting drop goes back to its old value**; the board is not drawn again under a drag.
- **Leaving the four panels opens the one-day board at its top** (the first panel's scroll is not carried over).
- **On thin rows the mark takes at most half the card**; its full words are the first line of the card's title on hover.

## What the lead will meet, in numbers

Measured in a browser on the made-up school (10 days in two weeks, 26 periods), the page at 1440 pixels wide, in full screen
with the four panels:

- At 900 pixels high inside the browser (a 1440 by 900 screen with the browser's own full screen on): each class panel shows
  both weeks with nothing to scroll, at 20 pixels a row. A lesson is one line.
- Both weeks fit a class panel from about 806 pixels high inside the browser when one day of the class has two lessons at once
  (11 lines of lessons), and from about 772 when none has (10 lines; worked out, not measured). Under that the rows stay at 16
  pixels and the panel scrolls: at 780 pixels the last 11 pixels of the second week are below the panel's edge.
- An ordinary browser window on a 1440 by 900 laptop is about 760 to 790 pixels high inside (the reviewer's estimate, not
  measured on the lead's laptop). So there: either the bottom row or so of the second week needs a small scroll in each panel,
  or the browser's own full-screen key (on a Mac, Ctrl+Cmd+F) gives the whole 900.
- Before the fix round the same sums were 896 and 865 pixels: the trim of the week headings (22 to 14 pixels), the fit strip (6 to
  4) and the panel's head line (about 42 to 29) gained about 45 pixels a panel.
- The design said "about 19 pixels a row" at 1440 by 900; it is 20 after the trim (16 before it).
- Out of full screen the four panels are 82% of the window's height, so on a laptop the rows are at 16 pixels and each panel
  scrolls a little; a period is at least 20 pixels wide, so a panel also scrolls sideways a little until the window is about
  1500 pixels wide or the card is in full screen.
- From 28 pixels a row (a window about 1100 pixels high in full screen) a lesson has its two lines.

## Known limits

- The red dashed outline is for a red place with no lesson of the class there. A place that is red because of a rule (for example
  "meets twice on Odd Tue") outlines nothing: no lesson is in the way.
- The outline comes when the pointer has rested 200 ms on the place; after the board is drawn again under a still pointer it comes
  back at the next move of the pointer. A board that changes during the rest drops the request.
- Each rest on a new red place is one request to the server, which builds its index of the timetable again (as a click on a blue
  place does today). On the real timetable 93,499 places were judged in 8 seconds on a laptop; the live site's speed was not
  measured.
- After a change is made the chosen lesson is let go (as before this work), so the next Esc leaves full screen.
- In full screen with the four panels on a narrow window, the title line (36 pixels, one line) may cut the Find list short.
- The page behind the full-screen card is not locked: it may be scrolled somewhere else when full screen is left.
- "n where another lesson of the class is: a swap is asked" are the design's words; at most of those places the box only asks
  (swap, put it beside, or put it here anyway).
- Re-opening step 8 lands on the one-day board; the panels' classes are remembered (in this browser), the view is not.
- `Board.panelsFor`, `panelSet`, `panelPut` and `panelShow` expect what `Board.panels` gives; they are not hardened against other
  input.

## How it was checked

**Suites.** On the final code (50f1af2): `node --check static/app.js`, the 27 node suites and the 34 Python suites (quick): 62 of 62
pass, each judged by its exit status. Slow runs (`--full`): `tests/smoke.py` 104, `tests/test_combined.py` 40 and
`tests/test_fixes.py` 76 pass. `tests/test_helper.py --full` and `tests/test_typed.py --full` **do not pass reliably, on main
(82c0646) as on this branch**: they solve the primary sample afresh with a 30-second limit, so each run checks a different
timetable, and on some of them a "Swap …" suggestion fails the suite's own check (or the solve does not finish on a busy
computer). Runs: main passed both once on a quiet computer and failed both twice on a busy one; the branch passed
`test_helper` once and failed four times, `test_typed` failed four times; one busy run gave the same failing line on main and
on the branch. This work cannot change them: the helper and the typed request call `fixes.slots(extras=False)`, `judge` and the
fix functions, and the branch's only change to `fixes.py` is inside `Busy.whys`, and in `_placer` under `red` and
`extras is True` (the board's `place` alone). It is a fault of those two suites or of the helper that was there before, and it
should have its own piece of work.

**In a browser, on a made-up school** (the app's secondary sample: 16 classes, 10 days of an Odd and an Even week, 26 periods, 402
lessons made by the solver), on a scratch server and scratch data. The session had no window open, so the browser pane was hidden
and its page was given a 1440 by 900 size; the tool's real drag was traced and landed where it was aimed.

With real pointer actions and real keys:

- opening the four panels from the one-day board; choosing a lesson then clicking a place (moved); a drag inside a panel (moved); a
  drag onto another class's panel (refused: "This lesson is 1A's. It can only go on 1A's rows."); a drag from the Odd week onto a
  lesson in the Even week (the drop box, Cancel); a click on a lesson that can be swapped (the question with Swap and Put it here
  anyway); Put it here anyway (both lessons there, two lanes, both marked); a drag onto the fourth panel (lifted out, chosen in Not
  placed); the pointer over a place and Cmd+V (placed); Cmd+Z five times (all undone);
- "Show me" on a lesson whose class is shown (the view stays), with a panel empty (the class is put in), with neither (the one-day
  board on the lesson's day, the panels kept);
- Full screen (the card's box equals the window in every view; with the four panels exactly three lines above them; the drop box
  and a toast above the card); Esc once closes the question and lets go of the lesson, Esc again leaves full screen;
- the outlines: a lesson chosen by a click (its teacher's lessons outlined in the other panels, the rest faded; a count over every
  card of the three panels agreed with the outlines, no mismatch); the pointer resting on a red place (the lesson its sentence
  names outlined in the other class's panel; a place red by a rule outlines nothing; one request a place); a real drag onto that
  red place still landed; a lesson in a room another teacher uses in another class (dotted outline there, not in its own panel);
- the Lesson page's two parts; Show 1C (the class goes into the empty panel, the lesson stays chosen, the other Show buttons are
  disabled with their title); a band chosen (chosen and coloured in all its panels, the one-band sentence).

By the list's change event or a click sent from the page (not a pointer): changing and emptying a panel; the one-day board, the
Teachers rows, a teacher's cycle and a class's cycle in full screen (row heights unchanged, the board scrolls inside); a window
under 900 pixels wide (one column, each panel 420 pixels); leaving step 8 and coming back.

After the fix round, with real clicks: a Sec 3 band chosen on the one-day board, then Four panels: the third panel became 3A (kept
too), the lesson stayed chosen and its page stayed open; Esc with the board shown as "could not be loaded" in full screen left
full screen. By clicks sent from the page: the Four panels button on the Teachers rows and on a teacher's whole cycle opens the
panels on Classes rows.

**Not tried in a browser:** a real window of the lead's laptop (see the numbers above); the 200 ms rest during a drag (the tool's
drag lasts tens of milliseconds and cannot be held still; read in the code); "Show me" on a teacher in two places and on a
class-only warning (the sample has neither; read in the code by the whole-branch review); a combined venue's outline (pinned in the
suites); a server stopped during a hover (read in the code: nothing is drawn or said); a window too short for full screen; Print.

**On the school's real setup and timetable, counts only** (a second scratch folder, never opened in a browser): 10 days, 26 periods, 32 classes, 1014 lessons, 3 combined venues. (a) 12 sets of three panels over all 32 classes: 320 panel rows
compared with the class's own cycle (lessons, lines, break codes, day): 0 different. (b) Three classes of each level, 361 lessons,
93,499 places judged: 688 red places with no lesson of the class there; `fixes.place` lists collisions exactly when `Busy.clash`
gives a sentence (688 agree, 0 disagree) and otherwise equals its slot; 375 places with a list, 625 lines; the 404 lessons named
on teacher, class and students lines are each named by their line's sentence; 221 room lines with 221 lessons. Run on the code
before the fix round and again on the final code: the same numbers.

## Reviews

Each task had its own review. They sent back: a wet-weather room's line naming lessons that only share the wet-weather room (task
1, fixed); the drop box landing too high in a scrolled full-screen card (task 4, fixed). The whole-branch review found nothing
that loses a change or breaks an existing way of editing; its two main points are the first three rulings above, and its small
points went into the one fix round. The fix round's re-review found every point addressed and nothing new.

## Calls for the lead

The eleven at the end of the design, and from the build:

12. Pressing Four panels with a lesson chosen always shows that lesson's class, taking the third panel's place when no panel is
    empty.
13. The Four panels button is also on the Teachers and Rooms rows.
14. The class panels are tighter than the mock-up (thinner week headings, fit strip and head line).
15. "Tied to" leaves out the lesson's own class; "Where it can go" leaves out a count of 0.
16. Further room for the rows, not taken: dropping the line of start times under the period numbers (about 12 pixels a panel).

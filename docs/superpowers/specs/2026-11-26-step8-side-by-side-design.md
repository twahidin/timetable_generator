# Step 8: four panels (three classes and the side panel), full screen, and what a lesson is tied to

Date: 2026-11-26. Asked for by the committee lead. Mock-up: `2026-11-26-step8-side-by-side-mockup.html` (a made-up school;
it works by click and drag), picture `2026-11-26-step8-side-by-side-mockup.png` (full screen, a lesson chosen).

## Why

On step 8 ("Upload and edit") the board shows either one day with a row per class, or one class's whole cycle. To swap
lessons by hand the lead needs a class's whole cycle, and then cannot see the classes its teachers also teach. A move that
looks free in one class is red because of a lesson in another class that is not on the screen.

The lead's words:

- "right now all the edit is done one class at a time but sometimes I want to see multiple classes at once so that I can do
  the manual swapping"
- "a full screen for up to 3 classes timetable at a time and so that I can do swapping and see how it is all related"
- "explain what does two places error means"
- after a first mock-up (three classes stacked under each other): "I want it to be whole class view like two weeks in one
  view 4 panels like a quadrant, last panel is the chat panel the first three are class"
- asked what the fourth panel holds, a typed AI chat or today's side panel: "Today's side panel"

"What does two places mean" is a sign that the mark "In two places" on a card does not say enough: it covers a teacher
clash, a class clash and a room used by more lessons than it takes.

## Goals

1. A view of step 8 in four panels, two across and two down: three panels each hold one class's whole cycle (every week of
   it), and the fourth holds today's side panel. Each class panel is edited exactly as one class's cycle is edited today
   (click then click, drag, the drop box, Undo, the Lesson page).
2. A full-screen board: the timetable card fills the browser window.
3. With a lesson chosen, the lessons it is tied to in the other panels can be seen: the same teacher's lessons, the same
   room's lessons, and the lesson that blocks the place under the pointer.
4. The mark on a card says which thing is in two places: the teacher, the class or the room.

## Not in this work

- A typed AI chat on step 8.
- Teachers or rooms in the panels. A teacher's or room's whole cycle stays as it is.
- More than three classes, or a choice of how the panels are arranged.
- Dropping a lesson on another class's rows. A lesson belongs to its class or classes; it moves in time only.
- Any change to what a place's colour means, to the drop box's buttons, to the Not placed tray, the counters' counts, the
  content of the side panel's four tabs (apart from the two parts added to the Lesson page, part 4), the keys (Ctrl or
  Cmd+X, V, Z), or the published timetable.
- The one-day board and the one-class cycle as they are today, apart from the new mark words, the Full screen button and
  the Four panels button.
- Remembering the panels' classes on the server. They are kept in this browser only.

## What would make it a failure

- Anything that works on one class's whole cycle today and does not in a class panel: a drag (inside a week, between the
  weeks), a click-then-click move, a swap, "Put it here anyway", a paste from Not placed, Undo, a counter's step, "Show me"
  on a warning, the Lesson page.
- A place coloured, or a sentence said, differently from what the one-class cycle says for the same lesson and place.
- An outline on a lesson that is not in the way, or not that teacher's or room's.
- Full screen that cannot be left, or that hides the drop box, the side panel or the Undo button.
- The one-day board, the one-class cycle, or a teacher's or room's cycle looking or behaving differently when the four
  panels are not in use.

## Approaches

**How the view is made.** Four ways were weighed.

(a) Widen today's class cycle: the same mode holds up to three classes and draws a panel a class. Every part of the page
that asks "is a class's cycle shown?" keeps working, and each row still says its class and its day, which is all the drag,
the drop and the colouring read. One selection, one drag, one set of fetched places, as now.
(b) A new kind of view beside the cycle view: every check for the cycle view must be doubled.
(c) A separate full-screen page (as the compare page is): its own copy of the drag, the questions and Undo, which would
drift from step 8.
(d) Three whole boards on the page, each with its own state: the page keeps one selection, one drag and one set of fetched
places; three boards would need all of that three times and then have to be kept in step.

(a) is chosen (builder's call; the lead handed over the how).

**Who says what is in the way.** (a) Work it out on the page from the cards; (b) have the server say which lessons collide.
The earlier step 8 design ruled that the server owns what a clash is (teachers, classes, bands, shared students, rooms,
combined venues, the days a teacher may take two lessons), because a second copy on the page drifts. That ruling is kept:
the lesson "that blocks this place" comes from the server (builder's call). The two standing outlines, "same teacher" and
"same room", are not judgements: they are read from the cards on the page.

**Full screen.** (a) The browser's own full-screen mode from a button; (b) the timetable card filling the browser window.
(b) is chosen (builder's call): in the browser's own mode Esc leaves full screen before the page hears it, and on step 8
Esc already lets go of a lesson. The lead can still press the browser's own full-screen key to hide its bars too.

## Part 1: the four panels

### The mode

`S.board.mode` for a class's cycle is today `{kind: "cycle", cls, d}`. The four panels are the same kind with one more
field: `{kind: "cycle", cls, panels, d}`.

- `panels`: a list of exactly three entries, each a class name or `""` (an empty panel), no class twice, at least one class.
- `cls` stays and is always the first class in `panels`, so code that reads `mode.cls` keeps working.
- No `panels`: today's one-class cycle, unchanged.

A teacher's or room's cycle (`mode.by` "teacher" or "room") never has `panels`.

### How it is opened and left

- A button **Four panels** in the board's control rows, shown when the rows are Classes: on the one-day board and on a
  class's cycle. From the day board it opens the stored panels (below), or, with none stored, the first three classes of the
  level of the chosen lesson, else of the first level that is not folded. From a class's cycle it opens the stored panels
  when they hold that class; else that class in the first panel and the other two empty.
- In the four panels the control row has **All classes** (back to the one-day board, on the day the board was last on), as
  the class cycle has today. There are no day tabs, as in the cycle today. "Rows: Teachers / Rooms" leaves the four panels
  as it leaves the cycle today.
- A click on a class's name on the day board still opens that one class's cycle, as today.

The panels' classes are kept in `S.board` while step 8 is open and in this browser's `localStorage` (one key, as the side
panel's width is kept). A stored class the board no longer has becomes an empty panel; stored panels with no class left are
forgotten.

### A class panel

- A head line: a list holding the class (the classes of every level, grouped by level, less those in the other two panels;
  and "No class here" when another panel has a class), then, in small grey words, nothing else that needs data the board
  does not have (the mock-up's "form teacher · room" is decoration and is not built).
- Under it the class's whole cycle as the one-class cycle draws it today: the period header, a heading a week (when the
  cycle has more than one), a row a day. The rows come from `Board.groups` for `{kind: "cycle", cls: <that class>}`, so
  each row's element carries its class and its day, and the lanes, the breaks, the fit strip, the drag, the drop and the
  click read them as they do now. Row keys must be unique across the three panels (class and day).
- The panel scrolls on its own, both ways, when its rows or periods do not fit.
- An empty panel shows its list reading "Choose a class…" and the words "Choose a class at the top to show it here."
- Changing a panel's class draws the board again. A chosen lesson none of whose classes is shown any more is let go.

Sizes in a class panel (the one-class cycle keeps today's): the row label 42 pixels, a period at least 20 pixels wide and
sharing the panel's width, the card text 10.5 pixels. The period header shows each period's number, and its start time
under every third period (the times do not fit under every period at this width); every period's title says its time.

The rows share the panel's height. With the panel's scroll area `H` pixels tall, the fixed parts (the period header, the
week headings, each row's strip and border) taking `F`, and `L` lanes in all its rows, a lane is `floor((H − F) / L)`
pixels high, kept between 16 and 60. Below 28 the cards go to one line (the subject in full, then the teacher and room on
the same line, cut short with "…"). When the rows do not fit at 16 the panel scrolls. The sum is a plain function in
`board.js` (`Board.lane(H, F, L)`), tested under Node. It is worked out again when the window changes size, when full screen
is entered or left, and each time the board is drawn.

A lesson of two or three of the classes shown (a band, a combined lesson) is drawn in each of those panels. It is one
lesson: chosen in one it is shown chosen in all, and its places are coloured in all its classes' panels.

### The fourth panel

Today's side panel (`#bdSide`): its tabs (Not placed, Warnings, Changes, and Lesson or Empty period), its own scroll, a
drop on it lifting a lesson out. In the four panels it sits in the bottom right quarter and takes that quarter's size; the
grip that drags its width is hidden there, and the stored width is neither used nor changed.

### The whole

- Out of full screen the four panels together are 82% of the window's height, and at least 600 pixels.
- On a window under 900 pixels wide (where the side panel goes under the board today) the four panels are one column, each
  420 pixels high.
- The title line, the control rows, the counters with Undo, the green "how to" box and the one-line status stay above the
  panels, and the notes of the upload under them, as today.
- The drop box and the questions are placed as today, over the timetable card.

### Choosing and moving

Nothing changes in what a click, a drag or a drop does. `bdPaint` colours the rows the chosen lesson is on
(`Board.onRow`), which are now the rows of its classes' panels.

A panel of a class the lesson is not in:

- is not dimmed as a whole (today's `.dim`, 40%): the lead must be able to read it. Instead its cards that are not tied to
  the chosen lesson fade a little (62%, as in the mock-up), and the tied ones keep their full colour with an outline
  (part 3);
- takes no drop and no click-to-move. The line says "This lesson is 1A's. It can only go on 1A's rows." (for a lesson of
  several classes: "This lesson is 1A, 1B and 1C's. It can only go on their rows."). A click on a card there chooses that
  card instead, as a click on any other card does today.

### Going to a lesson (a counter's step, "Show me", "Show on the board")

`bdGoTo(c)` on the Classes rows, when the four panels are shown:

- a class of the lesson is in a panel: the view stays, and the lesson is scrolled into view in that panel;
- else a panel is empty: the lesson's first class goes into the first empty panel;
- else: the board goes to the one-day board on the lesson's day, where every class has a row. The panels stay stored, so
  **Four panels** brings them back.

"Show me" on a warning that names a lesson goes through `bdGoTo`, as above. The two other kinds keep what they do today,
and the panels stay stored:

- a warning about a teacher with no lesson named (a teacher in two places): the Teachers rows on its day with that teacher's
  lessons marked, as today. This leaves the four panels;
- a warning about a class with no lesson named: when the class is in a panel the view stays and that panel is scrolled into
  view; else when a panel is empty the class goes into it; else that class's one-class cycle, as today.

`bdTake` (a fetched board) empties a panel whose class the board no longer has; with no class left it goes to the day board,
as today.

## Part 2: full screen

- A button **Full screen** at the right of the timetable card's title line, in every view of the board. Pressed, it reads
  **Exit full screen**.
- In full screen the timetable card is fixed over the whole browser window, above the page's header and the step list.
  The green "how to" box and the notes under the board are hidden while it is on. The drop box, the questions and the
  toasts stay above it.
- In full screen with the four panels there are exactly three lines above the panels, so that the rows get the height:
  the title line, which also carries **All classes**, "Find a subject" and **Exit full screen**; the counters with Undo;
  the one-line status. The "Rows:" buttons and the key of the outlines are hidden (All classes leads back to them).
- In full screen with any other view everything above the board stays as it is out of full screen, less the green box,
  and the board with the side panel beside it fills the rest of the height.
- Row heights change only in the four panels (they share each panel's height, as in part 1). The one-day board and the
  one-class, teacher's and room's cycles keep today's row height in full screen and scroll inside the taller area.
- **Esc** does what it does today, in one press: it closes an open question or drop box and lets go of the chosen lesson
  or empty period. A press of Esc with nothing asked and nothing chosen leaves full screen.
- Full screen is left when step 8 is left. It is not remembered between visits.

What it gives on the school's real cycle (10 days, 26 periods): on a 1440 by 900 window in full screen each class panel
shows both weeks with no scrolling, at about 19 pixels a row, so each lesson is one line (the mock-up, which has one more
line above the panels, measures 18). A day where two lessons of the class overlap takes two lanes and makes every row of
that panel thinner; at the floor of 16 the panel scrolls. A taller window gives taller rows; from 28 pixels a row a lesson
has its two lines.

## Part 3: what a lesson is tied to

All of this is drawn by adding and removing classes on the cards (as `bdPaint` does), never by drawing the board again, so
a drag in the air is not cut off. All of it is only in the four panels.

### Same teacher, same room

With a lesson chosen:

- **Same teacher:** every other card with a row whose teachers include any teacher of the chosen lesson gets a purple
  outline. In the lesson's own class's panel too.
- **Same room:** every other card in a panel of a class the lesson is *not* in, with a row whose room meets a room of the
  chosen lesson (`Board.roomsMeet` with the board's `room_parts`, so a combined venue meets its rooms), gets a dotted teal
  outline, unless it already has the purple one. Not in the lesson's own class's panel: a class's own room is on most of
  its lessons. "No room" and "TBC" meet nothing.

Both come from one plain function in `board.js` over two cards (`Board.tied(card, other, parts)` → `"teacher"`, `"room"`
or `""`), tested under Node. A card that can be swapped with the chosen lesson keeps today's swap outline; the tied outline
is not added to it.

A key under the counters, shown only in the four panels, names the three outlines: Same teacher, Same room, Blocks the
place under the pointer.

### The lesson that blocks a place

This is for **red places only**: a place of the chosen lesson's own rows where no other lesson of its classes is, and
where it would land with a problem. (A blue place has another lesson of the class right there in the same panel; a click
or a drop on it lists every collision in the drop box, as today, and the lessons that can be swapped cleanly keep today's
green dashed outline. Why a swap is *not* offered is not shown in this work; see the calls at the end.)

- `fixes.Busy.whys` gives each collision line a list `ids`: the ids of the lessons in the way for that line (a teacher
  line: that lesson; a class line: that lesson; a students line: that lesson; a room line: every lesson in that room, or in
  a room it shares, in those periods, a wet-weather room's lessons included). The sentences and their order do not change.
- `fixes.place` today gives `clashes` only where another lesson of the class is there (`None` elsewhere). It now gives the
  list wherever the plain move or place collides with something; where nothing collides it stays as today. So
  `GET /api/draft/place` returns the lines, with their `ids`, for a red place.
- The tests that pin the old shape are rewritten with it: a line being exactly `{kind, text}` and `clashes` being `None` on
  a place with no lesson of the class (`tests/test_fixes.py`, `tests/test_board.py`, `tests/smoke.py`), and the test that a
  place equals its slot.
- On the page: when the pointer rests for 200 ms on a red place of the chosen lesson's own rows (hovering, or during a
  drag), the page asks `GET /api/draft/place` for it, once a lesson, place and board (kept until the board is fetched
  again), and the cards whose ids are in its `clashes` get a red dashed outline in every panel they are in. The outline
  goes when the pointer leaves the place. A failed or late answer draws nothing; an answer for another place, lesson or
  board is dropped. The answer is used for the outline only: what a click or a drop there does is unchanged, and so is
  what the status line and the strip's title say.
- A lesson in the way whose class is in no panel is simply not outlined; the place's sentence already names it.

## Part 4: on the Lesson page

Two short parts are added to the Lesson page of a placed lesson, after its warnings and before the questions, in every
view of the board:

- **Where it can go:** from the lesson's fetched places (`b.slots`, when they are this lesson's), over the whole cycle:
  "n clean places", "n that bend a Prefer", "n where another lesson of the class is: a swap is asked". Absent until the
  places are here.
- **Tied to:** for each teacher of the lesson, the classes whose cards that teacher is on, each with its number of lessons,
  from the board's cards. In the four panels, a class shown reads "shown"; one not shown has a button **Show 2A**, which
  puts it in the first empty panel (disabled when no panel is empty, its title "All three panels are in use: change one at
  its top"). In the other views there are no buttons. A lesson that is a band says instead: "This lesson is one band. It
  moves in 1A, 1B and 1C at the same time."

## Part 5: the mark's words

`Board.MARK` today gives "In two places" for the marks `teacher`, `class` and `room`. It becomes:

| mark | on the card |
|---|---|
| `teacher` | Teacher in two places |
| `class` | Class in two places |
| `room` | Room in two places |

A card shows its first mark, in the server's order (teacher before class before room), as today. The counter above the
board stays **In two places** and counts as today. The Warnings list keeps its own words ("Teacher in two places", "Class
clash", "Room used twice"). The green "how to" box and the README say what the three mean:

- Teacher in two places: one of the lesson's teachers has another lesson at the same time.
- Class in two places: the class has another lesson at the same time. Two groups of one band, or two groups of one class,
  at the same time are not counted.
- Room in two places: the room holds more lessons then than it takes.

On a narrow card the mark is cut short ("Teacher in t…"), so the mark's words are also the first line of the card's title
on hover. The Lesson page keeps listing the lesson's critical mistakes as it does today.

## Constraints

- `static/app.js`, `static/board.js`, `static/style.css`, `fixes.py` (and `draft.py` only if `place` needs it), the README's
  step 8 section, `tests/board.test.js`, `tests/test_board.py`, `tests/test_fixes.py`, `tests/smoke.py`. No change to the setup, the draft's
  stored form, the skill, or the published page.
- A redraw of the board under a drag cancels the drag in Chromium: outlines, fades and row heights during a drag are class
  and style changes only. The page's way of keeping a dragged card's element in place while the board is drawn again
  (`bdKeep`) must hold with three scrolling panels.
- `bdDraw` keeps the board where it was scrolled; with the four panels it keeps each panel's scroll.
- The days' own names decide the weeks (`Grid.weeks`); a school with one week has no week headings.
- Only "CTSS" may name the school in the repository; the mock-up is a made-up school.
- Other sessions are working in `static/app.js` on other branches: merge main in before the pull request.

## How it is checked

- Node: `Board.tied`; `Board.lane`; the new `MARK` words; the rows of three panels have keys that do not collide; a lesson
  of two shown classes is in both panels' rows.
- Python: `whys` lines carry the right `ids` for a teacher, a class, shared students, a room, a wet-weather room and a
  combined venue, and the
  sentences are unchanged; `/api/draft/place` returns `clashes` for a red place with no lesson of the class there, and
  nothing new for a clean one.
- Every existing suite, quick and `--full`.
- In a browser with a real mouse, on a made-up school: opening the four panels from the day board and from a class's cycle;
  changing and emptying a panel; a move by click and by drag inside a panel, between its weeks; a swap; "Put it here
  anyway"; a paste from Not placed; a lift-out by dropping on the fourth panel; Undo; a counter's step and "Show me" on a
  lesson with its class shown, with a panel empty, and with neither; "Show me" on a teacher in two places and on a class
  warning; the three outlines; full screen at two window sizes;
  Esc's order; a window under 900 pixels wide; the one-day board, the one-class cycle and a teacher's cycle unchanged, in
  and out of full screen.
- On the school's real setup and timetable, counts only: for every lesson of three classes, the places' colours in the
  four panels equal those of each class's own cycle; the outlined blockers equal the lessons the sentences name.

## Left to the builder

- The exact keys, class names and storage key; where the control rows wrap on a narrow window.
- Whether the three panels are drawn by one function called three times or by one pass, and how `bdKeep` holds a dragged
  card across them.
- How the 200 ms rest is timed during a drag (dragover fires continuously).
- The colours of the outlines, as long as the three can be told apart and from the selection and the swap outlines.
- Esc's exact wiring, as long as one press never both lets go of a lesson and leaves full screen.

## Calls made here that the lead may want changed

1. A lesson cannot be dropped on another class's panel.
2. The other classes' unrelated lessons fade a little while a lesson is chosen.
3. The one-class cycle stays as it is; the four panels are opened by their own button.
4. Full screen fills the browser window; it does not use the browser's own full-screen mode.
5. When a lesson to show is in none of the three panels and none is empty, the board goes to the one-day board.
6. The mark reads "Teacher / Class / Room in two places"; the Warnings list keeps "Class clash" and "Room used twice".
7. The outlines are only in the four panels; the one-day board keeps its look.
8. On a laptop-sized window the rows are thin (one line a lesson); that is the price of both weeks of three classes at once.
9. The red dashed outline is for red places only. For a lesson that cannot be swapped with the chosen one, the board does
   not say which lesson stops the swap; that would be a further piece of work.
10. "Show me" on a teacher in two places still opens the Teachers rows, which leaves the four panels; **Four panels** brings
    them back.
11. In full screen the four panels hide the "Rows:" buttons and the key of the outlines to give the rows more height.

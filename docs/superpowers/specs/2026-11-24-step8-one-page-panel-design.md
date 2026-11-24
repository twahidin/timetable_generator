# Step 8: one page beside the board, collisions on a drop, teachers by department

Date: 2026-11-24. Asked for by the committee lead, with screenshots of step 8 ("Upload and edit").

## Why

Today a click on the board opens a small pop-out beside the lesson (Ask, Lift out, Delete this lesson, Cancel). The lead
finds the pop-out in the way: it appears on every click, and the useful things (the questions) are two presses away. A drop
on another lesson offers "Push out …" without saying what is in the way. And the two questions about teachers list people
the lead would not pick: teachers who are busy, or who collide at another lesson of the group.

The lead's words:

- "instead of having a popout automatically, could put the lift out, and delete lesson on the right instead, the ask will
  appear automatically below, so you can see two buttons, delete or lift out. and then a series of questions. If I click on
  empty slot, it will just show the ask questions"
- "prefer one tab"
- "instead of pushing out, state other collisions, similar to roz" (their timetabling program)
- "when it asked, who to swap with suggest people in the department and see if it is direct swap and who else can teach it
  as long as no collision", "but all within the same department first"

## Goals

1. A click on a lesson or an empty period opens no pop-out. Everything about it is on one tab of the side panel.
2. A drop on another lesson says every collision at that place, and no longer offers to push the other lesson out.
3. The teacher questions suggest the same department first and only what does not collide.

## Not in this work

- The typed AI chat (stage 2 of "Ask about this").
- Any change to dragging, the Not placed tray, Undo, the counters, the day tabs, the Rows buttons, or the keys
  (Ctrl or Cmd+X, V, Z; Esc).
- The server's push (a fix with `push`): it stays for anything that still sends it; the board stops sending it.
- "What can this swap with?", "Where else can it go?", "Which rooms could it use?", "What can go here?", "Who is free then?":
  their answers do not change.

## What would make it a failure

- A pop-out that still appears on a plain click.
- A control of the board that worked before and does not now (drag, click-then-click move, tray, Undo, Show me, counters).
- A collision the box does not list but the timetable then shows as a critical mistake.
- A teacher suggested as free who then clashes.

## Approaches

**The panel.** (a) Keep the Lesson and Ask tabs, open Ask on a click and put the two buttons on it; (b) one tab holding
both. The lead chose (b). Within (b): the tab could follow the selection strictly (nothing selected, no tab), or stay about
the last thing pointed at, as the Ask tab does today. The second is chosen (builder's call): answers stay reachable after
Esc, and "Show on the board" inside an answer can select another lesson without the page changing under the reader.

**Collisions.** (a) Compute them on the page from the board's cards; (b) have the server list them with the place's
judgement. (b) is chosen (builder's call): the server already owns the rules for a clash (teachers, classes, bands, shared
students, rooms and combined venues), and a second copy on the page would drift.

**Teachers.** (a) Filter on the page; (b) filter on the server in `ask.py`. (b) is chosen (builder's call): the "more" count
and the sentence must match what is listed.

## Part 1: the side panel

### The tab

The side panel's tabs become: Not placed, Warnings, Changes, and one more while the board is about something. That tab is
labelled **Lesson** when it is about a lesson and **Empty period** when it is about an empty period. The separate "Ask" tab
and the old "Lesson" tab are gone; this one holds both.

It is about the last thing pointed at, and stays so until something else is pointed at:

- a click on a lesson that selects it (on the board or in Not placed);
- a right-click on a lesson (which now also selects it, and never lets go of it) or on an empty period (with no lesson
  selected it is marked as a click marks it; with a lesson selected the selection stays and nothing is marked, as today);
- a click on an empty period with no lesson selected;
- a counter's step, and a warning's "Show me" (from step 9's "Show on step 8" the panel keeps Warnings, and the tab is there
  to open, as today).

"Show on the board" inside an answer selects that lesson on the board and leaves the tab on what it is about, as today.

Letting go (a second click on the selected lesson or the marked period, Esc): the panel goes back to the tab that was open
before, as the Lesson tab does today. The tab stays in the row, so its answers are one press away.

An entry of "Step 5 asks for these" has no page (it is not a lesson yet). Selecting one leaves the panel as it is; the line
under the green box says what the pop-out said ("{name} · {n} periods · has {have} of {want}", and "Switch to Classes rows
to place it." off the Classes rows).

### The page, about a lesson, top to bottom

1. The lesson's name in bold, and under it where it is ("Mon period 20 (2.20) · 5 groups", or "Not placed (was …)").
2. Two buttons: **Lift out** (not shown for a lesson in Not placed) and **Delete this lesson**. They act on the lesson the
   page is about. Off while a change is being saved, as today.
   - Delete still asks first, in the same spot: the two buttons give way to "Delete {lesson}?", the reason when the delete
     is a "no" ("Step 5 asks for this lesson." and the judgement's sentence), then **Delete** and **Cancel**. Esc cancels.
   - A lesson that is gone (deleted): the sentence "This lesson is no longer on the timetable." and nothing to press, as today.
3. The lesson's open warnings, all of them, as today.
4. A band's groups as chips, one chosen (as today: the group of the row clicked on in the Teachers or Rooms rows, else the
   first).
5. The starter questions, as today.
6. **Teacher** and **Room** lists for the chosen group, with "Add a teacher", the count a change of teacher touches, and
   "all this group's lessons", exactly as the Lesson tab has them today. One group at a time: the chip chooses it (today's
   blocks per group, three open, are gone). A plain lesson has no chips and one set of lists.
7. The answers, newest last, each as today (Show on the board, Preview, Apply), then **Clear**. Asking a question scrolls
   its answer into view, as today.

### The page, about an empty period

Its row, day and period ("2A · Mon period 4 · empty"), then the two starter questions and the answers. No buttons, no lists.

### What goes

- The pop-out for a selected lesson and for a marked empty period, with its Ask and Cancel buttons.
- The pop-out's delete question (it is in the panel now).

### What stays a small box beside the pointer

Questions that follow something the lead did, and need an answer before the board goes on: the drop question (part 2), the
hand-over on a teacher's or room's row, "Give it anyway?", "Use it anyway?", "Apply anyway?", "Leave it with no teacher?".

### Moving by click

Unchanged: with a lesson selected, a click on a place moves the lesson there. An empty period is marked, and asked about,
only when no lesson is selected.

### The green box

- "Ask:" line: "click a lesson or an empty period; its questions are on the right."
- "Keys:" line: "Esc lets go of the lesson" in place of "Esc closes the pop-out".

## Part 2: a drop on another lesson

### What the box says

Heading: "{lesson} on {day} period {p} collides with:" then one line per collision, each led by its kind, in the order the
server finds them today:

- **Teacher**: "{teacher} is teaching {lesson} then." One line a teacher and lesson.
- **Class**: one line for each lesson in the way, naming all the classes it shares with the dropped lesson: "2A, 2B and 2C
  have the Mathematics 2A-2D band then." The lesson is named as the board names it (a band by its band's name), so a band
  is one line, not a line a class or a group.
- **Students**: the sentences today's first-clash check gives for shared students and for a band whose students are all in
  one of the two; one line for each lesson in the way.
- **Room**: "{room} is in use then." (a combined venue and its rooms as today)

Every collision, not the first only. At most 8 lines, then "and {n} more".

When nothing collides (another group of the same class is there, with no shared student, teacher or room): the heading is
"{lesson} on {day} period {p}: another lesson is there." and the line "Nothing collides."

### Its buttons

- **Swap with {lesson}**: as today, only when the swap is clean or bends a rule.
- **Put it here anyway**: when it collides. Both lessons stay; the collisions then show as critical mistakes on the cards and
  in Warnings, until fixed. Not offered where the place is not lesson time for the class (the box then says that sentence
  and has Cancel only).
- **Put it beside {lesson}** (or "Put it beside them"): when nothing collides, as today.
- **Cancel**.
- No "Push out". To clear a place first, lift the other lesson out with its own button.

The line under the green box, while a lesson is dragged over such a place, stays as it is ("Another lesson is there. Drop
or click to see what can be done.", `BDWHY.thereTell` in `static/app.js`). `Board.tell`'s sentence that names push is not
reached on the page; it and `Board.question`'s push words are removed with their tests.

A lesson of "Step 5 asks for these" is still added only where its classes are free, as today.

### The server

`GET /api/draft/place` gains `clashes`: a list of `{kind, text}` (`kind` one of `class`, `teacher`, `students`, `room`)
for the plain move or place with the other lessons left there. It comes from a new all-reasons walk beside the first-reason
one in `fixes.py` (`Busy._why`), in the same order of kinds and finding the same lessons, teachers and rooms. `_why` and its
sentence are not changed (the judgement, the forcing and their tests stay as they are); the list has its own wording for a
class line (above), so its first line need not equal `beside.why`. What must hold: the list is empty exactly when `_why`
finds nothing, and what `_why` names first is in the list's first line. "Put it here anyway" posts the plain move or place
forced with `beside.why`, which the server already accepts for a move and a place (it keeps a forced change only for the
same reason it judged).

The box is for a place where a lesson of the dropped lesson's own classes is (the blue places), as today. A red place
(the classes are free there, and a teacher, a room or a student collides) is not changed: the lesson lands at once with its
problem, the line having said the first one. Listing every collision there too is a possible follow-up, not this work.

A rule of step 6 broken there is not a collision: when the place is free of clashes and only a Must rule stands in the way,
the box says that rule's sentence (as `beside.why` does today) and offers "Put it here anyway".

## Part 3: the teacher questions

### "Who else could teach it?"

- Only teachers with no collision at any lesson of the group (a change of teacher changes all its lessons). That is what
  "free" already means in `fixes.choices`. A free teacher whose change bends or breaks a rule of step 6 or goes over an
  allowance is still listed, after the clean ones, with the rule's sentence and "Apply anyway" as today: a rule is not a
  collision.
- Order, as today's lists: step 5's teachers of the subject, teachers already on the subject, the rest of the subject's
  department, then everyone else.
- When no one of the first three kinds can take it: the answer's sentence says "No one in {department} is free to take
  {lesson}." before the others (with no department on the subject's card: "No one who teaches {subject} is free …").
- At most 8 are listed, then "and {n} more", as today.
- The busy teachers at the foot of today's answer (up to 4) go. The Teacher list on the page still shows them under "Busy
  then", for the lead who wants one anyway.

### "Who could I trade this class with?"

- Who is tried is unchanged: teachers of the same subject, then the rest of the subject's department. A trade is always
  inside the subject or its department.
- Each trade's verdict reads **Direct swap** when clean, **Direct swap, bends a rule** when it only bends one, and **Not a
  direct swap** with the reason when it would land with a problem. Direct swaps first, as today.
- The answer's sentence: "{n} direct swaps are possible for {teacher}." in place of "{n} trades are possible …".

## Tests

- Node: `tests/board.test.js` (the question's words and buttons from a slot with `clashes`; the fix "Put it here anyway"
  posts; the line's sentence), `tests/ask.test.js` (the verdict of a trade; the page's parts for a lesson, a tray lesson, a
  place).
- Python: `tests/test_fixes.py` (every reason, in order, first equal to `clash`; a band once; a combined venue),
  `tests/test_ask.py` or where the Ask answers are tested today (teachers: none listed that clash, department order, the
  "No one in …" sentence, the bound; trades: wording), `tests/test_board.py` (`/api/draft/place` carries `clashes`).
- No test calls a model or Telegram.
- Browser, real pointer actions, scratch data folder, sample school: click a lesson, click an empty period, Lift out,
  Delete and its Cancel, each starter question, the Teacher and Room lists, a band's chips, a drop on another lesson (a
  collision, "Put it here anyway", Undo), a clean swap, drag to an empty place, the Not placed tray, Undo, a counter, Show me,
  right-click, Esc, the Teachers and Rooms rows.

## Left to the builder

- Names of functions and state; how the old `b.lesson` state folds into `b.about`.
- CSS of the page (reuse the Lesson and Ask classes).
- Whether the three parts are three commits or more; one branch, `step8-no-popout`.

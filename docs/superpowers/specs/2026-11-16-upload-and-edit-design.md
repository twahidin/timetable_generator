# Upload and edit: a board for changing the timetable by hand, and a Publish step that only publishes

Date: 16 November 2026. Status: design, awaiting the committee's approval of this document. A project of its own,
after the visual setup views. It reworks the Fix part of the return trip
(`docs/superpowers/specs/2026-11-10-return-trip-design.md`) and leaves the rest of it standing.

## Why

Step 8 today takes the timetable an outside agent made, checks it, and lets the committee lead fix it. The fixing is
done one class's week at a time: click a lesson, the page colours where it may go, click a slot. It only ever makes a
change that checks clean, it never leaves a lesson without a time, and it publishes with any warning still open.

The committee lead, looking at CTSS's own timetable on that step, asked for it to be redone. In their words:

- "First I need an editing step between 7 and 8. Called Upload and Edit."
- "I want the editing to be more intuitive, it could be this view like class or subject where I can see all the four
  levels at once or venue page or time page where I can see all the subjects within the allocation of time."
- "I can simply cut and paste or shift the cards around by dragging and dropping (either as a band or subject on its
  own)."
- "If I shift it around, it will replace or pop out cards on the side that is not placed after say I forcefully
  push."
- "I can also replace the venue or teacher and it will show me which class does not have a venue or teacher."
- "For the publish step, it should be just publish the timetable while showing all the warnings", and it must not
  publish while there is a critical mistake.

So three things about today's step are reversed. The lead sees the whole school, not one class. The lead may force a
change, and what it knocks out waits at the side. And publishing is held back only by mistakes that make the timetable
impossible to run, with everything else shown and left to the lead's judgement.

## Who uses it

The committee lead and the committee, at a desk. Heads, teachers and students do not see either step, as today.

## What it is

Step 8 becomes two steps. The list on the left reads: 7 Download, **8 Upload and edit**, **9 Publish**, Students.

### Step 8. Upload and edit

**Upload** is as today: the timetable database on its own, or the Lessons workbook with the setup workbook beside
it. The upload becomes the draft, kept on the server, checked against the setup as it is now. A new upload replaces
the draft; if the draft has changes that were never published, or lessons waiting in "Not placed", the page says so
and asks first.

**The board** opens as soon as there is a draft. It is the school's timetable for one day:

```
 Rows: [Classes] Teachers  Rooms      Day: [Odd Mon] Odd Tue ... Even Fri      Find a subject: [ all ]
 Not placed 1 · No teacher 1 · No room 1 · In two places 2 · Warnings 12
       1      2      3      4     R     6      7      8      9     10 ...      | Not placed
 Sec 1                                                                         |  2B Science
  1A  [Maths G3    ][English     ]      [Mother Tongue band ][Science     ]    |
  1B  [English     ][Maths G3    ]      [  3 groups         ][Art         ]    | 1A Maths
  1C  [Science     ][Art         ]      [  1A to 1D         ][English     ]    |  Teacher [ ... ]
  1D  [PE          ][Science     ]      [                   ][Maths G3    ]    |  Room    [ ... ]
 Sec 2
  2A  [Maths G3 !  ][Science  !  ]      [English     ][PE          ]           |
  ...
```

- **Rows and columns.** The periods of the day run across, with their times. The rows are the classes, grouped by
  level, all levels on the one page; a level can be folded shut. Breaks, recess and the time outside a level's day
  are shaded and take no lesson.
- **A card is a lesson**: its subject, its teacher or teachers, its room. A lesson of two periods is two periods
  wide. A card is coloured by its subject's department, as the published timetable is.
- **A band is one card** across all its classes (a band's groups meet at the same time). It shows the band's name
  and how many groups it has. Clicking it opens the band: its groups, each with its subject, teacher and room.
- **The day.** One tab per day of the cycle: five at a school with one week, ten at CTSS (Odd Mon to Even Fri).
- **Three kinds of row.** The same day can be shown with classes, teachers or rooms as the rows. Teachers shows each
  teacher's day (who is free, who is in two places). Rooms shows each room's day (which lab is empty). Teachers are
  grouped by department and rooms by kind. On these rows a card dragged along its row changes its time, exactly as on
  its class's row (the question of swap or push out is about its own class's lessons). A card dragged to another
  teacher's row gives the lesson to that teacher, and to another room's row moves it to that room: the same change the
  card's lists make. If that teacher or room is busy then, the card lands and both are marked; the other lesson is
  not pushed out and no swap between two classes is offered.
- **One class's whole cycle.** A click on a class's name (or a teacher's, or a room's) opens that one row's whole
  cycle: the days down the side, the periods across, as the published timetable shows it. Everything that can be done
  on the board can be done there. A click on "All classes" goes back.
- **Find a subject.** Picking a subject (or a department) keeps its cards bright and fades the rest, on every level
  and every kind of row. Nothing is hidden.

**Moving a card**

- **Drag** a card to another time on its own row. While it is dragged the row shows, for each place it could start:
  clean; fits but bends a rule or a teacher's allowance (and which); clashes (and with what); cannot go (a break,
  outside the day, not enough periods left). The sentence for the place under the pointer is shown beside the board.
- **Drop on empty time:** the lesson moves. If the move is clean it is simply made. If it clashes, the lesson still
  lands, and it is marked (see "Critical mistakes" below). A lesson can never be dropped where it cannot go.
- **Drop on another lesson of the same class:** the page asks one question with two buttons. **Swap** (offered when
  the two are the same length and each can go where the other was) exchanges them. **Push out** puts the dragged
  lesson there and moves every lesson of that class it now overlaps to "Not placed".
- **A band moves as one**, for all its classes. Pushing with a band pushes out what it overlaps in every one of its
  classes. A single group cannot be dragged out of its band to another time: its students would be in two places.
- **Another day.** Dragging a card onto a day's tab switches to that day, and the drop is made there. Or the lesson is
  cut, the day changed, and the lesson put back.
- **Not placed** is a tray at the side of the board. A lesson there has no time. It keeps its class, subject, teacher
  and room. Dragging a card onto the tray lifts it out (this is "cut"); dragging a card from the tray onto its row
  places it (this is "paste"), with the same showing of where it fits and the same swap or push question. The tray
  lists what is waiting on every day, not only the day shown, grouped by class.
- **What step 5 asks for and the timetable lacks.** Under the waiting lessons the tray has a second list, "Step 5
  asks for these": a lesson for each row of step 5 that the timetable has no lesson for, or too few periods of (the
  list today's "add a lesson" offers). Dragging one onto its class's row adds it, with its subject, teacher and kind of
  room from the setup. These are warnings, not critical: they are the agent's shortfall, not a lesson the lead moved.
- **Delete.** A selected card, on the board or in the tray, has "Delete this lesson". It asks first and says whether
  step 5 asks for that lesson; Undo brings it back. Add and delete are today's, kept.
- **Every drag has a click.** Selecting a card and then clicking a place on its row moves it there; selecting a card
  and pressing a "Lift out" button cuts it; selecting a card in the tray and clicking a place puts it back. Cut and
  paste also work from the keyboard.
- **Undo** takes back the last change, and the one before, as today. Each change is written down in words ("Moved 1A
  Mathematics from Odd Mon period 1 to Odd Tue period 6. Pushed out: 1A Art.").

**Changing a teacher or a room**

- A click on a card (or on a group of an open band) opens it beside the board: its teacher or teachers and its room,
  each a list to pick from.
- **Teachers**: those who are free in all the lesson's periods come first, in the order step 8 offers them today (who
  already teaches the subject, then the rest of its department), then everyone else with what they are teaching then.
  As today, a change of teacher is a change for that class's or group's lessons of that subject, all of them, because
  step 5 names one set of teachers for them; the page says how many lessons will change before it is made.
- **Rooms**: the free rooms of the right kind first, then the rest with what is in them then. A change of room is for
  that one lesson, with a tick box "all this group's lessons".
- **None** is a choice in both lists. A lesson can be left with no teacher or no room while the lead works. No
  teacher is a critical mistake until one is given; no room is counted and shown, and is a warning.

**What needs attention**

- A line of counters above the board: **Not placed**, **No teacher**, **In two places**, **In a break** (the four
  critical kinds), then **No room** and **Warnings**. A click on a counter fades everything else and steps through
  those cards, switching day as needed.
- A card with a critical mistake is outlined in red and says what is wrong in a few words; the full sentence is in
  the panel beside the board when the card is selected.
- The list of warnings (clashes, differences from step 5, rules, rules in words, choices used) stays, as a panel that
  can be opened beside the board. Each warning has **Show me**, which goes to its card. A difference from step 5 keeps
  its answer **The timetable is right, update step 5**. The answer "Leave it" goes: Publish shows every warning, so
  there is nothing to tick off. A rule in words that a change touched still asks to be looked at again and can be
  marked "Still met".
- **The helper and the typed request** stay as they are, in that same panel: ways to settle the selected warning,
  and the box for asking in words. What they suggest is applied to the board like any other change.

### Step 9. Publish

- The step shows what will be published: the school, the term, the counts, which setup version it was checked
  against, and the list of changes made in the app.
- **Critical mistakes** are listed first, each with a link back to its card on step 8. While there is one, the
  Publish button does not publish and says why ("3 critical mistakes to settle on step 8 first").
- **Warnings** are listed under them, all of them, grouped as today. They do not stop publishing.
- **Publish** replaces the published timetable for everyone, after the same confirmation as today. The published
  record keeps what it keeps today, with the open warnings in place of the "left" ones.
- **Make printouts** (the zip of PDFs, the Excel file and the page) and **Download the draft** move here. Both are
  refused, in words, while a lesson is not placed: the timetable file has no way to hold a lesson without a time,
  and a file that silently left one out would be the vanishing lesson this design forbids.

### Critical mistakes

A critical mistake is one that makes the timetable impossible to run as written:

- a lesson that is not placed (lifted out or pushed out, and not yet put back or deleted);
- a lesson with no teacher;
- a teacher in two lessons at once;
- a class clash as the check finds it today: a lesson the whole class takes, at the same time as any other lesson of
  that class. Two bands, or two groups, of one class at the same time are not a mistake: different students take them,
  and the check of each student stays a warning;
- a room holding two lessons at once, unless the setup says that room takes more than one class;
- a lesson in a break, in its class's recess, or outside its level's day (the board never makes one; an uploaded file
  can hold one).

Everything else is a warning: a lesson with no room (a room still "TBC" counts as none), a room over its seats, a
student in two lessons at once, a lesson step 5 asks for and the timetable lacks, periods timetabled against periods
planned, a difference from step 5, a rule broken (Must or Prefer), a teacher over allowance, a rule in words to look
at again, a second choice used.

**What the school's own files show** (counts only). The newest timetable the agent returned has none of the critical
kinds: it could be published at once, with its 39 warnings shown. The one of 10 November has 30 cases of a teacher in
two places and 68 lessons in a break or outside the day: 98 critical mistakes, so it could not be published until they
were settled. That file also has 166 lesson rows with no room; if no room were critical it would add 166 more, which
is why it is a warning here. In both files classes have two bands at the same time (60 and 128 class-periods), which
is normal and is not counted.

## Across both steps

- **The agent's file is kept as it came.** As today, the draft is the uploaded file plus the list of changes made in
  the app, so the two can always be told apart, and the list is in the published timetable's Read me.
- **One draft for the committee.** Two committee members see the same draft; a change one makes shows on the other's
  board within a few seconds without a reload, and two changes made at the same moment are both kept or the second is
  refused in words, never silently lost.
- **Checked against the setup as it is now**, as today. A change on step 5 is seen by the next check.
- **The school's size.** CTSS has 32 classes on 4 levels, about 90 teachers, 73 rooms, 26 periods a day, a two-week
  cycle and about 1,950 lesson rows on a timetable, some 200 a day. The board must open, change day, change the kind
  of row, show where a dragged card fits and answer a drop without a pause a person would notice.
- **A practice copy** has no step 8 or 9 work, as today ("Publishing is off in a practice copy").

## Goals

- The lead can see a whole day of the whole school, by class, by teacher or by room, and one class's whole cycle.
- A lesson is moved by dragging it. A change the app would have refused can be forced, and nothing it displaces is
  lost: it waits in "Not placed".
- A teacher or a room is changed on the card, and lessons with none are counted and found in one click.
- Publish shows every warning and refuses only for a critical mistake.

## Not in this project

- Making or re-solving a timetable in the app, or filling the "Not placed" tray automatically.
- Moving a lesson to another class, or one group out of its band's time.
- Splitting a lesson into shorter ones or joining lessons. A lesson moves as the block it is.
- Changing step 5 from the board, other than the existing "update step 5" answer to a difference.
- Heads, teachers or students seeing or editing the draft (project 3).
- Phone layouts: this is used at a desk.

## What would make this a failure even if it works

- A lesson that vanishes. A pushed-out or lifted-out lesson is always in "Not placed" until it is put back, through
  Undo, a reload, a second committee member's change and a new check; and nothing can be published while one is there.
- A band torn apart: one class of a band moved without the others, or its groups at different times.
- A forced change that hides what it broke. Every critical mistake a change makes is on the card and in the counters
  at once.
- The board slow or dead at the school's size. It is tried on a timetable shaped like CTSS's before it is merged, and
  timed on the real one (counts and timings only: the real workbook and timetable are private).
- A draft from before this project that no longer opens, or opens with its changes lost.
- The agent's file changed, or a published timetable that differs from what the board showed.
- Anyone's real name, or the school's full name, in the code, the tests or these documents.

## Approaches

Three ways of building it were considered.

1. **The board on top of today's draft (chosen).** The draft stays the uploaded file plus a list of changes, each
   judged by the code that checks the whole timetable. Two things are added to that list: a change may be kept even
   when it clashes, and a lesson may have no time. The board is a new way of drawing the draft and of making those
   changes. It keeps Undo, the record of changes, the check against step 5, the helper and the typed request, and
   every existing draft still opens. It costs the most thought where a forced change meets the old rule that every
   change is clean.
2. **A free editor on a copy of the timetable.** The page would edit lessons directly and the app would check
   afterwards. Dragging is simpler to build, but the list of changes, Undo across sessions, the record in the
   published timetable and "the agent's file is kept as it came" would all have to be rebuilt, and the helper and the
   typed request would no longer fit.
3. **Dragging added to today's one-class grid.** The least work, but it gives no picture of the whole school, which
   is the first thing asked for.

The committee lead left the choice to the writer.

## Suggested order of building

Four stages, one plan and one pull request each, each usable on its own.

1. **Two steps and the Publish rule.** Step 8 becomes "Upload and edit" holding today's upload, check and editor;
   step 9 "Publish" shows the critical mistakes and the warnings and refuses for a critical one; printouts and the
   draft's download move to it; "Leave it" goes.
2. **The board.** A day of the whole school by class; cards and bands; one class's whole cycle; dragging that makes
   the changes the app already allows (a clean move, a swap), with the showing of where a card fits; find a subject.
3. **Forcing, and Not placed.** A forced move, push out, the tray, cut and paste, another day; the counters; the
   critical marks on cards.
4. **Teachers and rooms.** Rows by teacher and by room; the card's teacher and room lists, with "none"; the open
   band; the warnings panel, helper and typed request beside the board.

## Decided by the committee lead

1. A new step, "Upload and edit", between Download and Publish.
2. Editing by dragging cards and by cut and paste, for a band or a single subject.
3. A forced move is allowed; what it pushes out waits at the side as not placed.
4. The teacher and the room can be replaced on a lesson, and lessons with none are shown.
5. Views of the whole school: by class with all levels at once, by venue, by time.
6. Publish only publishes, shows all the warnings, and does not publish with a critical mistake.

## Decided by the writer of this document (to be checked on reading)

- The board is one day of the whole school; the rows are classes, teachers or rooms; a click on a row's name opens
  its whole cycle. "By subject" is a way of finding (the rest fades), not a fourth kind of row.
- What is critical and what is a warning, as listed above. A broken Must rule, a difference from step 5, a lesson
  with no room and a lesson the timetable lacks are warnings. A lesson in a break or outside the day is critical.
- Add and delete stay: add from the tray's second list, delete from the selected card.
- On the Teachers and Rooms rows, a card dragged to another row changes its teacher or its room.
- Printouts and the draft's download are refused while a lesson is not placed.
- Dropping on another lesson asks: swap or push out. A push only pushes out lessons of the same class or classes; a
  teacher or a room that is busy elsewhere is marked on the card and nothing else moves.
- A single group cannot leave its band's time. A lesson cannot move to another class.
- A change of teacher is for all that class's or group's lessons of the subject, as today; a change of room is for
  the one lesson unless the box is ticked.
- "Leave it" goes. "Update step 5" and "Still met" stay.
- The helper and the typed request stay as they are, beside the board.
- Printouts and the draft's download move to step 9.
- The tray lists every day's waiting lessons, and a new upload asks first when it is not empty.

## Left to the builder

- How the list of changes records a forced change, a lesson with no time and a lesson with no teacher or room, as
  long as a draft from before still opens and Undo takes each back.
- Whether the old one-class click editor is kept beside the board through stages 1 to 3 or replaced at stage 2.
- The look of cards, rows, the tray and the marks, within the page's present style; how small a one-period card may
  be and what it shows when there is no room for all three lines; how a band whose classes are not next to each other
  is drawn.
- How the page learns of another committee member's change (as the setup does today, or simpler).
- How far the showing of where a dragged card fits is worked out ahead of the drag, as long as it is not felt.
- The order of teachers and rooms within "free" and "not free", and the words of every new sentence, in the plain
  style of the rest of the page.
- How each stage is tested, as long as it includes a timetable shaped like the school's and a run on the real one
  (counts and timings only).

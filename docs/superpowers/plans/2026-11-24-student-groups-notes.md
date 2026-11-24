# One student's groups on the published timetable: notes

Plan: `docs/superpowers/plans/2026-11-24-student-groups.md`. Design:
`docs/superpowers/specs/2026-11-24-student-groups-design.md` (mockup beside it). Built 24 Nov 2026 on branch
`student-groups` from main d600cee, subagent-driven: eight tasks, each built by a fresh builder and read by a
reviewer, then a whole-branch review on the most capable model and one fix wave. All names in tests, docs and
screenshots are made up; the school is "CTSS".

## What it gives

- **A saved student follows onto the published timetable at once.** Any change to a student on the Students step
  (the new screen, a box in the table, the group chips, the bar for ticked students, a paste, ✕, a Put back) updates
  that student's own record on the published timetable. No lesson, teacher, room or period moves, and the time of
  publishing does not change. No publish on step 9 is needed.
- **Open on every row** (the second column) opens a panel over the page for that student: the bands over their class
  with the group picked in each, every group's teacher, room and head count against its size, **None** and **Exempt**
  for each band, other groups as ticks, the Note, and on the right the student's week on the published timetable.
  Lessons gained are blue, lessons left are grey and crossed out, a clash is red and named with its day and period.
  A band every student takes with nothing picked says "choose one".
- **+ Add student** opens the same panel empty (in the class the list is filtered to). The new student's personal
  sign-in code works at once.
- **Save writes only what was changed in the panel**, so a change made to the same student by someone else meanwhile
  is kept, and the panel says when that happened.
- **A status card** above the list says whether the list and the published timetable agree, names the students who
  differ and why, and offers **Update the published timetable** when a restore, a load from file or a new list left
  them apart. It asks first, with the counts, and the server refuses if the counts have changed since.
- **A line after each save** says what happened on the published timetable, with a link to the student's timetable
  as a PDF.
- **The files to download** (the workbook, the finder page, the PDF books, the zip, the database) are remade in the
  background about a minute after the last student change. Until then the page says they are being refreshed.
- **History** has the setup change under the person's name, with Put back, and a line of the app's saying what it
  did on the published timetable.

## Rulings made while building (mine, not the lead's)

Each was made where the design or the plan was silent or wrong. What it costs if wrong is in brackets.

1. The test for a saved clash checks the model's checks and the first 20 problems in `meta.json`, because the
   made-up setup already has many problems and `meta.json` keeps 20. (Nothing.)
2. A row with no ID or name is ignored by the update and by the status: not listed, no History line. (A blank row is
   not reported there; Things to fix still names it.)
3. "Updated" only when the published record really changes: a Note-only save writes nothing to the published
   timetable. (Nothing: the Note is not on it.)
4. A row with no class gives the reason "no class". (Wording.)
5. With no setup saved at all, the status says so quietly and Update does nothing. A setup that exists with an empty
   list still makes every published student "on the published timetable but not on this list", and Update removes
   them after asking. (If wrong, an empty list could not clear the roster.)
6. The update route has no catch-all for errors; an unexpected error is a 500 like any other route. (A raw error
   page instead of a sentence, in a case nobody has seen.)
7. `store.now()` is accurate to the minute, so the files job also compares in-memory counters of publishes and
   model writes. (Nothing: `meta.json` gains no field.)
8. `store.published()` checks the folder under its lock, so a reader never sees the folder mid-swap. Before this a
   request in that instant could sign a student out; publish always had that gap. (Nothing found; the lock is held
   only for the two renames.)
9. The skeleton's stamp is `published_at` plus a short hash of the lessons, because two publishes in one minute
   would share `published_at`. (A few milliseconds per status.)
10. Task 6 was built while Task 5's read-only review ran (new files only). (None came of it.)
11. A class change in the panel goes through one function: picks that are not groups of the new class are shown
    unticked and crossed out with the reason, and are not saved unless ticked back. (One more thing on the screen.)
12. **The screen is a panel over the page, not a card above the list.** On a two-week timetable of 26 periods the
    card's week was clipped and scrolled out of sight. The mockup the lead approved shows a card; the two columns
    are the same. (If the lead prefers the card: a styling change.)
13. **Open is the second column of the list**, not the last, where it was out of sight in a normal window.
14. A full publish is followed by a catch-up of students who differ, instead of changing what `store.publish` does
    with the setup it is given. (A second write of the model in the rare case of a race.)
15. Plan with AI's name guard now also notices a student change (it was keyed on the time of publishing only), so
    a new student's name is coded before it goes to the AI provider. (A talk's names are rebuilt a little more
    often.)
16. **Update the published timetable** sends the counts the person agreed to; the server refuses and shows the new
    counts when they have changed since. A student ✕ is sent on its own at once, so two quick ✕ each remove their
    student. (One more request per ✕.)
17. The ✕ question ("Remove … from the list and from the published timetable?") is asked whenever students are
    published, also for a student who is not on it. (Slightly loose wording in that case.)
18. Builders signed commits with the model that wrote the code. The first two commits (2881d9e, f2a93e8) were
    written by an Opus builder and carry a Fable line on my instruction, before I corrected the rule.

## Known limits

- There is no way to hold student changes back from the live timetable. Groups for a coming semester are not to be
  prepared on the Students step while the current timetable is live. (The lead: "No, never".)
- **Remove all** and **Replace the list** take nobody off the published timetable by themselves; **Update the
  published timetable** does, after asking. Two ✕ pressed while the first is still being sent can also be held this
  way; the page then says so.
- An exam already approved and on the main site keeps its seating after a student change, until it is made and
  approved again. The exam's working copy says "press Make again".
- The published card lists the first 20 problems of the timetable (as before this work). On a timetable with more
  than 20, the line "N students have two lessons at the same time" may not show there. The panel shows each
  student's clashes.
- When a student was changed elsewhere while their panel was open with changes, the panel's clash lines and Save
  question are worked out from the student as they were when it opened, and "keeps both" can leave two groups of
  one band. Things to fix names that.
- If remaking the files fails, they stay marked as being refreshed until the next student change or a restart.
  Students' own pages and PDFs are right all the same.
- A group added on step 5 after the publish has no lessons on the published timetable; a student put in it is not
  updated there until the next publish, and the screen says so.
- The "Saved. …" line under the status card stays until the next student save or until the step is opened again.
- At a window 1100px wide the week's day columns are narrow and some lesson labels are cut (the tooltip has them).
- A student save made while a full publish on step 9 is running waits for the publish to finish before it answers
  (about half a minute on the sample school). A student re-numbered during a publish keeps the old ID on the
  published timetable until Update the published timetable is pressed.
- The status card is worked out without waiting for a publish or a save in progress, so for a moment it can show a
  list and a published timetable from two different instants. It is fetched again, and Update checks its counts on
  the server before it writes.
- The server remakes the files with one processor core for about a minute; what that does to the live host under
  load was measured only on a Mac.

## On the school's real timetable (numbers only)

The lead's newest timetable database ("v16", generated 10 Nov), published in a scratch folder with 1256 made-up
students placed in its groups:

- 32 classes, 1948 lesson rows, two weeks of five days, 26 periods a day, 246 teaching groups (170 with the room's
  seats known). A class is offered 14 to 46 groups in 2 to 8 bands.
- The skeleton the panel fetches: about 100 KB (10 KB compressed), 0.04 to 0.08 s.
- One saved student reaches the published timetable in 0.2 to 0.4 s. The status takes about 0.1 s.
- The whole-list update of 1256 students: 0.14 s.
- Remaking the files: about 60 to 70 s, starting 60 s after the last change.
- In the panel at 1400 x 850 the bands column scrolls by itself, both weeks sit side by side, and picking far down
  the list keeps its place. Nothing was thrown.

## Tests on the final code (8f307b0)

- Every Python suite (32, with `tests/smoke.py`), every page suite (26) and `node --check static/app.js` pass.
  New: `tests/test_students.py` (64 checks, publishing for real and forcing the races) and
  `tests/studentview.test.js` (30 cases). `tests/test_plan.py` gained 2 and `tests/test_routes.py` lists the three
  new routes.
- The four slow runs pass: `test_typed --full` 34, `test_helper --full` 21, `test_fixes --full` 67,
  `smoke --full` 104. Earlier in the day `test_helper --full` failed three runs on the branch and one of two on a
  clean copy of main, each time its known solver-dependent fault (see the last section); `test_typed --full` failed
  once while the computer was very busy and passed every run after.
- In a browser, on a scratch data folder with the sample secondary school published (about 600 made-up students),
  with real clicks: about 90 checks by the builders and reviewers, and the main path again by me at the end (open a
  student, swap a group, Save, the status line, the student's PDF).

## Not tried in a browser

- The "No timetable is published yet" line, the practice-copy line, and a save's error answer (read in the code).
- The files line on step 9 going away (seen going on the Students step).
- A second real browser signed in as another committee member (stood in for by a console change and by a second
  test client).
- Printing. A phone-sized window beyond a look at 820px.

## Things noticed that are from before this work (not changed)

- **Add to the list** replaces a student already on the list whole, so their Note (and an Exempt line in it) and
  Combination are lost. Undo brings them back.
- `/api/status` gives heads the published timetable's problems, and the students-clash line among them names up to
  five students.
- `tests/test_helper.py --full` fails some runs on main too (a swap offered with a twin lesson of the same subject;
  its fix sits on the unmerged branch `helper-full-flake`).

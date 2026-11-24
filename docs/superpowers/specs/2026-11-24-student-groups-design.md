# One student's groups, on the published timetable

Date: 24 November 2026. Status: **written for the committee lead to approve**. The lead saw the mockup on
24 November 2026 and said "Yes, write it up". Read once by a builder; what it asked is settled below, each marked
"design's call", and one question went to the lead and is answered (see "Preparing ahead"). Mockup with made-up names: `2026-11-24-student-groups-mockup.html`
beside this file (a picture of it: `2026-11-24-student-groups-mockup.png`). Where this file and the mockup differ,
this file is right.

## Why

The lead's words: "I also need a way to change student TG easily so that their timetable can change, is there a way
to do it as well as add in new students and allocate based on the published timetable." And, when asked what should
happen to the timetable: "The published timetable should not change just because I swap the TG, it is just that the
student will receive a new timetable right".

What the app does today (main `d600cee`):

- The committee's **Students** step holds the list (`spec.students[]`: `id`, `name`, `class`, `level`, `groups`,
  `note`, `combination`). It can be pasted or uploaded, a student can be added, and ticked students can be added to a
  group, removed from one, or moved to a class.
- A change there reaches a student's timetable **only when the whole timetable is published again** on step 9. That
  publish takes the step 8 draft and the setup as they are at that moment. A student change cannot go out on its own.
- Nothing helps choose groups for one student: no view of their week, no warning that a group clashes with another of
  their lessons (the check exists only as one school-wide count on the published timetable), and group counts show
  only in the picker for ticked students.
- The live site's published timetable has no students in it yet.

## What the lead decided

| Question | Answer |
|---|---|
| Does a group swap change the published timetable? | No. Lessons, teachers, rooms and periods stay. Only that student's own timetable changes. |
| How many students at a time? | "A few now and then" (a new arrival, a subject change). |
| Who may do it? | "Committee only". |
| The screen in the mockup? | "Yes, write it up". |
| Are next semester's groups prepared on the Students step while this timetable is live? | "No, never". So no Pause switch. |

The lead was also shown these five points and the choice of approach, and said yes to the whole message. They are
**my proposals, accepted without comment**, not the lead's own words:

1. A new student uses the same screen. The app does not pick subjects for them.
2. A clash or a full group warns but does not stop the save.
3. Every change goes in History with the person's name, with Put back.
4. The files to download refresh by themselves about a minute after a change.
5. Ticking several students and moving them together stays as it is.

## Goals

- The committee opens **one student** and sees their bands, the group picked in each, every group's head count
  against its size, and the student's **week on the published timetable**.
- Picking another group shows at once which lessons the student gains and leaves, and names any clash.
- **Save** changes that student's own timetable on the published timetable straight away: their page, their PDF,
  their line in the Students tab. No publish on step 9 is needed.
- A **new student** is added and placed with the same screen, and their personal sign-in code works at once.
- Every such change is in History under the person's name and can be put back.

## Non-goals

- Anyone but the timetable committee changing students (heads, form teachers). Not asked for; the lead chose
  committee only.
- Placing a whole level at once. The paste, the upload and the bar for ticked students stay as they are and cover it.
- Picking subjects for a student automatically. Which subject is the student's choice.
- Changing any lesson, teacher, room or period. Changing the solver or the skill.
- A student changing their own groups.
- The published timetable page itself: no new buttons there.

## Anti-goals (these would make it a failure even if it works)

- A student change that alters **anything else** on the published timetable: a lesson, a teacher's or a room's
  timetable, another student's record, the time it was published.
- A student change that looks like a **new publish** to the rest of the app. Exams and Plan with AI key on
  `published_at`; it must not move.
- Students **losing their timetable** because the setup has moved on (new group codes on step 5, a restored copy, a
  new setup for next semester). When in doubt the published record is left as it is.
- A newer student change **lost** because an older background job finished after it.
- A real student's or teacher's name anywhere in the repository. Made-up names only; the school is "CTSS".

## Approaches

Three ways were looked at. The lead handed the choice over; the first is my pick.

1. **One list, and the published timetable follows it (picked).** The Students step stays the only list. When a
   student is saved there, the server also updates that one student on the published timetable. History and Put
   back already exist for setup changes, so they come with it. The cost: a guard is needed for the day the setup no
   longer matches the published timetable (see "When a student cannot follow").
2. **A second list kept with the published timetable**, edited on its own page. It would work even after the setup
   has moved on. Dropped: two lists to keep the same, the next publish would overwrite one with the other, and the
   committee would have to learn which list is the real one.
3. **A "publish the students only" button.** Simplest to build. Dropped: an extra click after every change that is
   easy to forget, and the lead expects the student to "receive a new timetable" when the group is changed.

## The design

### 1. The student screen (the mockup)

Where: the committee's Students step. Each row of the list gets an **Open** button. **+ Add student** opens the same
screen empty instead of adding a blank row to the list (today it adds a blank row). The table's own boxes, the group
chips and the bar for ticked students stay and keep working as they do.

The screen is a card with two columns.

**Top:** the student's name, ID, class and level. For a student already on the list the class is a drop-down; ID and
name can be edited. Under it, one line: "The personal code stays the same" (or, when the ID is being changed, "A new
ID gives a new personal code").

**Left, the groups, by band.** The list of bands and groups comes from **step 5** (the band, Everyone takes one, the
subject, the size); the published timetable is laid over it (the teacher, the room, the lesson periods). Design's
call. A group on step 5 with no lessons on the published timetable is still listed, marked "not on the published
timetable". For each band over the student's class:

- A heading: the band's name, and "every student takes one" or "optional" (step 5's Everyone takes one).
- One line per group, as radio buttons (one group per band, as today's Add to group rule), then **None** and
  **Exempt**, the same three kinds today's group picker offers for a band. Exempt writes "Exempt: <band>" into the
  student's Note exactly as the picker does today, and taking a group or None removes it. Design's call. Each group
  line: the group code and subject, then the teacher and the room, then the **head count against the
  size**.
- **Head count:** the students on the list in that group, counted as it will be after Save.
- **Size:** the Students number on the group's row on step 5. When that is blank: the seats of the room, when all the
  group's published lessons are in one room whose seats are known. When neither is known: "?" and the group is never
  called full.
- **Full:** a group the student is not in whose count has reached its size is marked "full"; the student's own group
  is marked when the count is over the size. Shown in red. It never stops the pick.
- **Clash:** a group whose lessons overlap another lesson the student would still have is marked with the day, the
  period and the other subject ("Clashes: Tue period 4, with 3EL2 English"). It can still be picked.
- **Order:** subjects in the order the published timetable lists them; within a subject, the group with the most
  room first, then by code.
- The group the student was in when the screen opened stays marked "was in this group" until Save.

Under the bands, **Other groups**: groups over the student's class that are in no band, as tick boxes. A group the
student is already in that is not a group of their class, or is no longer on step 5, is listed here too, ticked,
with "not a group of class 3B" or "not on step 5", and stays unless unticked.

Under those, the student's **Note** as a box (it holds the exempt lines and anything typed).

**Right, the week.** The student's timetable on the published timetable as it would be with the picks on the left:
whole-class lessons of their class, plus the lessons of the picked groups. Cells show the subject's short name and
the room. Lessons gained are blue, lessons left are grey and crossed out, a period with two lessons is red and shows
both. A key under the grid names the three colours.

**Bottom:** one sentence of what will change ("Moves from 3HIS1 History to 3GEO2 Geography. 4 lessons change. No
clash."), **Cancel**, and **Save · the timetable changes at once**. Nothing is saved until Save; Cancel and Esc
close the screen with nothing changed.

**Save asks first, once, when** any of these is true, naming each: a clash; a band every student takes with no group
picked and not Exempt; a group that is not on the published timetable (see below). The question ends "Save anyway?". A full group asks nothing.

**A new student** needs an ID, a name and a class before Save. An ID already on the list is refused: "S0412 is
already on the list." Choosing the class brings up its bands, each marked "choose one" until picked.

**Changing the class** of a student drops the picks that are not groups of the new class (shown crossed out under
Other groups until Save) and brings up the new class's bands.

**After Save** the screen closes, the row is highlighted in the list, and a line says what happened: "Saved. Aisha
Rahman's timetable is updated on the published timetable." with a link **Timetable (PDF)** (the existing
`/pdf/students/<id>`), or the reason it was not (see below).

**With no published timetable** the screen still opens: bands and groups come from step 5 with their counts, and the
right column says "No timetable is published yet, so there is no week to show." Only the band rule is checked.

**In a practice copy** nothing reaches the server, so Save changes the practice copy only and the line says so. The
screen shows **no week** there (the published timetable is the real school's, the practice copy may not be): bands
and counts only, as with no published timetable. Design's call.

Wording: the product never says "he" or "she" about a student. (The mockup's first draft did; it is corrected.)

### 2. What Save does

Save sends one change to the setup: the ordinary operations the Students step already uses (`set` for ID, name,
class and Note, `merge` for groups, `add` for a new row), in one save. So it is one unit in History and one Put back.

After the setup has taken the change, the server brings **the students that save touched** up to date on the
published timetable. This runs for **every** applied change to `students`, whichever control made it: this screen,
a box in the table, the group chips, the bar for ticked students, a paste, a row's delete button, or a Put back from
History. Students are matched between the list and the published timetable **by student ID** (the published records
have no row id). A save that changes an ID removes the old ID and adds the new one; when the new ID cannot follow
(it is already on the list, say), the old one stays, so a mistyped ID never takes a student off.

**Removals.** A save that deletes **one** student removes them from the published timetable at once, and the row's
delete question says so ("Remove S0412 Aisha Rahman from the list and from the published timetable?"). A save that
deletes **more than one** student (Remove all, Replace the list) removes **nobody** from the published timetable:
those students show on the status line as "on the published timetable but not on this list", and only the button
of section 4 removes them, after asking. The rest of such a save is treated as usual: with Replace the list, a
student whose ID is on both lists is updated at once, and a new ID is added. The questions Remove all and Replace
the list ask today name only the list; they gain a sentence saying what happens on the published timetable.
Design's call: loading a new list must never wipe the live timetables in one click.

What "up to date" means for one student who can follow (next section):

- Their record in the published model's `students` list (`id`, `name`, `cls`, `level`, `groups`) becomes what a full
  publish of today's setup would give for them. A test pins this: the records after a students update equal the
  records of a full publish from the same setup, for the students who can follow (a full publish also takes rows
  that cannot, a blank row as a student called "None" among them; that is left as it is).
- Their row in the setup kept inside the model (`m["setup"]["students"]`) is replaced too, so the timetable database
  made from the model still rebuilds every output.
- The model's checks are worked out again the way a publish leaves them, and `meta.json` takes the new student count,
  `ok` and `problems`. (`check_model` alone drops the second-choice problems that `model_from_files` appends after
  it; they are added again.) A saved clash therefore shows on the published card as "1 students have two lessons at
  the same time", which is true.
- `meta.json` gains `students_at` (when) and keeps `published_at` and everything else as it was.
- Everything else in the model is the same object content as before: lessons, teachers, rooms, classes, grids.

Rules for the builder:

- The cached published model is read by other requests while this runs. Never change it in place: build the new
  model beside it, write it, then drop the cache.
- One update at a time, and never during a publish (`store._publishing`). A reader must never see a half-written
  file. A reader that meets the new model with the old `meta.json` for an instant is harmless.
- The update reads the students **as the setup holds them when it runs**, not as the request sent them, so two
  quick saves end with the later state whichever finishes first.
- A failure here must not undo or fail the setup save. The save's answer says the published timetable was not
  updated and why; the status line (section 4) keeps saying so until it is.

### 3. When a student cannot follow

A student on the setup's list **can follow** when all of these hold:

- they have an ID or a name, and no other row on the list has the same one;
- their class is a class of the published timetable;
- every group code of theirs has lessons on the published timetable.

A student who cannot follow is **left exactly as the published timetable has them** (or stays absent, if new), and
the reason is given in words: "group 3XYZ is not on the published timetable", "class 3K is not on the published
timetable", "this ID is on the list twice". The next full publish on step 9 takes them as it does today.

This is the guard for a setup that has moved on. Two more parts of it:

- A change to the **whole setup** (Load from file, Restore an earlier copy, a new setup) updates **nothing** on the
  published timetable by itself. Only saves that name student rows do.
- Only the students a save touched are updated or removed. A student is never removed from the published timetable
  because some other save happened.

### 4. The status line and "Update the published timetable"

At the top of the list on the Students step, one line from the server compares the whole list with the published
timetable:

- "On the published timetable: 601 students, all as listed here."
- or "3 students here differ from the published timetable:" with each ID, name and reason (the three reasons above,
  "not updated yet", or "on the published timetable but not on this list"), first 10 shown and the rest counted.
- or "No timetable is published yet."
- and, while the files are behind (section 5): "The files to download are being refreshed."

When any student is "not updated yet" or "on the published timetable but not on this list" (a restored copy, a load
from file, an update that failed), a button **Update the published timetable** brings the whole list into step. It
asks first, with the counts: "2 students change, 1 is added, 14 are removed from the published timetable. Go on?"
The removals are said in their own sentence when there are any. Students who cannot follow are left, as always.

### 5. The files to download

The published folder holds files made at publish: the Excel workbook, the timetable finder page, the PDF books, the
zip of single PDFs and the timetable database. The students' own pages and PDFs are made on request from the model,
so they are right at once. The stored files are behind after a student change. Of these, only the committee's
downloads carry students (the Students book, the zip, the workbook, the finder file, the database); the books
teachers download (classes, teachers, rooms) do not change.

Measured on the sample secondary school (601 students, 16 classes): remaking every file takes about 20 seconds. The
real school is larger. So it runs in the background:

- A student update marks the files behind (`files_behind` in `meta.json`).
- A single background job waits until no student change has arrived for about a minute, then remakes all the files
  from the model as it then is and swaps them in the way a publish does (a fresh folder, swapped whole). It loads
  its own copy of the model: `export_all` may change the model it is given, so the shared cached one is never used.
- If a student change arrives while it works, that change must survive the swap, and the job runs once more.
- Meanwhile every download serves the last complete files. Step 9's published card and the Students status line
  say the files are being refreshed.
- After a restart with the files still marked behind, the job starts again by itself.
- The wait is a setting a test can shorten, and the remake can be called directly. No test waits a minute.

The server runs one process with threads (`--workers 1 --threads 8`), so one background thread is enough.

### 6. History and Put back

- The setup change is recorded as today: one entry per operation, one unit per save, under the person's name.
  `store.apply_changes` today hands back only the versions; it has to hand back as well the save's batch id and the
  student rows as they were before and are after, because the update needs the old ID of a deleted or re-numbered
  row and the history line needs the batch.
  Builder: check the entry for a group change names the group left and the group joined in words a committee member
  reads at a glance; reword only if it does not.
- A new history line, written by the app right after, says what happened on the published timetable: "Published
  timetable updated for Aisha Rahman (S0412)." or "… for 32 students." or "Published timetable not changed for Aisha
  Rahman (S0412): group 3XYZ is not on it." It names the save it came from but has **its own kind** and is not part
  of that save's unit: an entry of kind "app" that follows a unit is reversed with it, and this line has nothing to
  reverse. It cannot itself be put back.
- **Put back** of the setup change works as it does now (refused when the row was changed again since). Because it
  is an applied change to `students`, the published timetable follows it, and a line is written for that too.
- **Update the published timetable** writes one line with its counts. It has no Put back; the way back is to put
  the list right and press it again.

### 7. Who

Every new route needs the `committee` right. Heads, teachers and students get the usual refusal. The Students step
is already hidden from heads, and a head's change to a student row is already refused by the server.

### 8. What else on the site notices

- **Sign-in codes:** made from the ID. A new student's code works at once; a removed student's session ends with
  the existing "Code no longer valid"; a changed ID gives a new code (as a publish does today). The code slips and
  the codes file are made on request, so they are right at once.
- **Exams:** the working copy of a made exam already goes stale when who sits a paper changes ("The exam changed
  since Make: press Make again."). A group change or a new student triggers that for the exams it touches. An exam
  **already approved and on the main site** is judged by `published_at` only, so it stays as approved: a new student
  is not seated in it and a moved student stays on the old paper until the exam is made and approved again. No exams
  code is changed. Design's call; it is in Known limits and is said to the lead.
- **Plan with AI:** keys on `published_at`, which does not move. **Relief and the staff list** read teachers and
  lessons, which do not change.

## Where the code goes (for the builder; change it with a reason)

- `store.py`: the students update and the whole-list update beside `publish`, sharing its locks and its swap; the
  files job. Prefer not to change the `ttgen` package (a change there must be copied to the skill and follows the
  repo's rule for the skill version); if the student-record mapping in `ttgen/export.py` has to be shared, share it
  rather than copy it.
- `app.py`: call the update after each applied change that names `students` (the setup changes route and the History
  put back route; the third caller of `apply_changes`, step 8's "update step 5" in `draft.py`, sends lesson rows
  only), and new committee routes: the published timetable's skeleton for the screen, the status line, and
  Update the published timetable.
- **The skeleton:** one answer the page fetches when the screen first opens and again when the published timetable
  changes: the days, periods, times and breaks; each class's whole-class lessons; each group's subject, band,
  classes, teachers, rooms, seats and lesson slots. The page then works out weeks, clashes, counts and order by
  itself.
- `static/studentview.js` (new): the pure working-out (week, clash, count, full, order, the summary sentence),
  tested by `tests/studentview.test.js` as the other views are. `static/app.js`: the screen and its events.
- `history.py` and `static/history.js`: the new line's kind and label.

## Left to the builder

- Whether the screen is a card over the list or a panel that covers it; it must stay usable in a window 1100px
  wide, and the week must stay readable for a timetable of two weeks (ten day columns).
- The names of routes, functions and fields in `meta.json`.
- The exact wording of each sentence, in the plain style of the page (no "he" or "she").
- How the page learns the published timetable changed (the status line's answer may carry a stamp).

## Tests and checks

- **Python** (a new plain-script suite, as the others): a students update changes one student's record and nothing
  else in the model (every other key compared before and after); `published_at` is unchanged; the result equals a
  full publish of the same setup; each "cannot follow" reason leaves the record alone; a deleted student is removed;
  a whole-setup replacement updates nothing; the whole-list update's counts; a new student's personal code signs in
  and a removed student's stops; a Put back updates the published timetable; a made exam goes stale after a group
  change; the files job remakes the files, keeps a change that arrives while it works, and starts again after a
  restart; each new route refuses a head, a teacher and a student. No model API, no Telegram.
- **JavaScript:** `tests/studentview.test.js` for the working-out, including a two-week timetable, a group with no
  size, a student in a group outside their class, and an optional band.
- **Every existing suite** passes, with the `--full` runs of `tests/test_typed.py`, `tests/test_helper.py`,
  `tests/test_fixes.py` and `tests/smoke.py`.
- **In a browser**, on a scratch data folder with the sample secondary school published (its students are made up),
  with real mouse clicks: open a student, swap a group, see the week change, save, open that student's published
  timetable and PDF and see the new group; add a new student and sign in with their code; pick a clashing group and
  a full one; put the change back from History; restore an earlier copy and use Update the published timetable; and
  every old control of the Students step still works.
- **On the school's real setup and timetable** (counts only, never names): how many bands and groups the screen
  shows for the largest class, how long the skeleton takes to fetch and the files take to remake.

## Preparing ahead (asked of the lead, answered)

With this design every change on the Students step shows on the live timetable at once. If the committee prepared
**next semester's** groups on the Students step while this semester's timetable was still live, and the group codes
were the same, students would see next semester's groups early. The guard of section 3 cannot tell: the codes exist.
The lead was asked on 24 November 2026 whether that happens and answered **"No, never"**. So there is **no Pause
switch**. It is a known limit, below.

## Known limits

- There is no way to hold student changes back from the live timetable. Groups for a coming semester are not to be
  prepared on the Students step while the current timetable is live (the lead: this never happens).
- An exam already approved and on the main site does not pick up a student change until it is made and approved
  again (section 8).

- Two committee members saving the same student at the same moment: the later save wins field by field (groups are
  merged item by item, as today). The published timetable ends as the setup ends.
- A student sees a change the next time their page loads.
- The files to download are up to a minute or so behind a change, and say so.
- A group added on step 5 after the publish has no lessons on the published timetable. A student put in it is not
  updated there until the next publish; the screen and the status line say so.
- A full publish on step 9 still takes the whole list as the setup has it, including students who could not follow.

# Seeing the setup: visual views for steps 1 to 5, and the end of "Can teach"

Date: 15 November 2026. Status: design, awaiting the committee's approval of this document. A project of its own,
after project 2 (the return trip) and before project 3 (who sees what).

## Why

Steps 1 to 4 of the setup are tables. A table is good for typing a list and poor for seeing a school. The committee
lead, looking at CTSS's real setup, asked for four things.

- **To see what a table hides.** Where the rooms are, block by block and floor by floor. Which classes there are, who
  their Class Parents are, what each class takes. How the subjects are banded across the classes of a level.
- **To type less.** A subject offered at G3, G2 and G1 is three rows today, each with the full name and the code typed
  again. "I want to be able to create subjects and populate it easier than what it is now."
- **To drop "Can teach".** "The can teach part is redundant because teachers are allocated in TGs or a whole class
  directly, so I rather make the teaching groups bigger and remove this part." The head of department decides which
  teaching groups a teacher takes; a second list of what each teacher may teach is work nobody needs.
- **A teacher in two departments.** "A teacher can have two department because a teacher can teach both Math and
  Science." Today a teacher has one.

The table views stay. Every visual view is a second way of looking at, and changing, the same data.

## What it is

Four stages, in this order, one plan and one pull request each. The first three only add; the fourth changes how
heads work and what the workbook holds, so it lands last, with the most testing.

### Stage 1. Step 2, Classes: cards and the band picture

Step 2 gets three views, switched at the top right: **Cards**, **Bands**, **Table**. Table is today's table,
unchanged.

**Cards.** One row of cards per level, under a line with the level's name, its number of classes and its students.
Each card shows:

- the class, its planned number of students and its home room;
- its Class Parents (the school's own word for them), as avatars with short names, up to the school's maximum (four
  at CTSS). A plus adds one from the teacher list; a click on one removes or replaces it. These are the same
  changes the table's boxes make, and the Class Parents rule that already exists follows them in the same way;
- the class's subject combination: every subject the class has a lesson row of. A subject the whole class takes
  together is one colour; a subject only part of the class takes, in a teaching group, is another;
- once the student list is in (the Students step): the real number of students of the class beside the planned
  one, and on each subject that part of the class takes, how many of this class's students take it. Before the
  student list is in, the subjects show without counts and the card shows the planned number only.

A click on a card opens the class: the same fields as its table row, to change.

A card is marked (as a table row is today) when the class has something under Things to fix.

**Bands.** One picture per level: "how the subjects are banded". Each class of the level is a column. The rows
are what the classes take:

- A subject the whole class takes together is a cell in that class's column, on the subject's row (a subject and
  its G-levels together: one row for English, not three).
- A band is one bar across the classes it draws students from, with its name and its teaching groups inside, each
  with its subject and its size.
- A band whose groups are all one subject (Mathematics G3, G2, G1) sits on that subject's row. A band that mixes
  subjects (an option band with Geography and History, or Physics/Chemistry and Chemistry/Biology) has a row of
  its own, named as step 5 names the band.
- Bands that would share a row and draw from different classes (classes 1 to 2 in one, 3 to 4 in the other) are
  bars side by side on the same row. Bands that share classes are on rows of their own.
- A class that has no part in a row has an empty, dashed cell there.
- A subject some classes take whole and others take in a band shows both on its row: cells and a bar.

The picture is for looking. Bands are still made and changed on step 5's "Groups and bands"; a click on a bar goes
there, to that band. A department head sees the picture too, and step 5 links to it.

Everything on the cards and in the picture is worked out from what the setup already holds: the lesson rows (their
classes, band, code, students), the bands, and the student list (each student's class and teaching-group codes).
Nothing new is typed and nothing new is stored.

### Stage 2. Step 1, Venues: blocks and rooms

Step 1 gets two views: **Blocks** and **Table**.

**Blocks.** One panel per block, headed with the block's name, its number of rooms and its seats. Inside, one row
per floor, the highest floor at the top. Each room is a tile showing its name, its kind (a colour and an icon per
kind), its seats, and either the class whose home room it is or who it is kept for. Rooms with no block are in a
panel of their own, "No block yet".

- **Add a room** at the end of a floor's row: the name follows the floor's pattern (after B2-3 comes B2-4), the kind
  and seats are copied from the room before it, and all three can be changed at once.
- **Add a floor** to a block, and **add a block**.
- **A click on a room** opens it: name, kind, seats, block, floor, "For" (as today) and note, plus the two new
  things below. Deleting a room asks first, as the table does.

**Equipment and configuration (new).** A room can carry a short list of equipment ("30 keyboards", "40 PCs") and one
line for its configuration, meaning how it is laid out ("cluster seating", "exam layout"). Both are free text: an
equipment item is whatever the committee types, with no separate number, and the list is one cell in the
workbook. The committee lead
decided these are **only shown**: they do not decide which lessons may use a room. The kind and "For" go on doing
that. They show:

- on the room's tile (a small mark when a room has any) and in the room when opened;
- as two more columns in the table view;
- in the workbook's Venues sheet, as two more columns, so a workbook written and read back gives the same setup.
  The skill's notes for the outside agent call them information only;
- on the published room timetable, under the room's name (the builder's call below).

**Kinds.** The school's list of room kinds is already its own (School & day). The room editor also offers "New
kind…", which adds to that list. The kinds the app ships with each get a colour and an icon; a kind the school
adds gets a neutral one.

### Stage 3. Step 3, Subjects: one card per subject

Step 3 gets two views: **Cards** and **Table**.

**Cards.** One column per department, in the school's order of departments. Each card is one subject with all its
G-levels:

- the name and the code, typed once;
- a tick box for each of the school's tags (G3, G2, G1 at a secondary school; the school's own level tags
  elsewhere). Ticking G3, G2 and G1 on "Mathematics" makes the three subjects "Mathematics G3", "Mathematics G2"
  and "Mathematics G1", named exactly as they are typed today;
- one small grid of periods: a row per ticked tag, a column per level. The periods of G3, G2 and G1 differ, so each
  has its own row. A blank cell means the subject is not offered at that level;
- a subject with no tag ticked is one subject with one row of periods (PE, CP Time);
- the room kind and the lesson length, set once for the card.

**Behind a card, the data is what it is today**: one subject row per G-level. The card reads and writes those rows.
So the table view, the workbook, the lessons and everything after step 3 are unchanged, and a setup made before
this change shows as cards with nothing to convert.

- Rows belong to one card when they have the same department, the same code and the same name once the tag is
  taken off the end. The tag is the row's own tag (one of the school's tags), and it must also be the end of the
  row's name; a row where the two disagree, or that fits no card, is a card of its own, shown as it is.
- Each tick box is one row: ticked means the row "name tag" exists, unticked means it does not. Ticking never
  renames a row.
- A card with nothing ticked is the one row with no tag. Ticking its first tag: when no lesson uses the untagged
  row, that row is replaced by the tagged one (its periods move across); when lessons use it, it is kept, shown on
  the card as "no G-level", and the tagged rows are added beside it.
- Unticking the last tag of a card leaves a card with nothing ticked (one row with no tag, no periods), not a
  deleted subject. A whole card is deleted with its own button, which asks first.
- When the rows of one card differ in room kind or lesson length, the card says so and shows each row's own value
  to change, instead of one value for all.
- Unticking a tag removes that subject. When lessons use it, the card asks first, in the same words as the table.
- Changing the name or code on a card changes it on every row of the card, with whatever a change of name in the
  table does today, no more and no less.
- **Add a subject** at the foot of a department's column: an empty card, already in that department.

### Stage 4. Steps 4 and 5: teachers, two departments, no "Can teach"

**"Can teach" goes.** The app stops asking what each teacher can teach.

- Step 4 loses its Can teach column. Step 5 loses its Can teach baskets and the "not set to teach" mark. A head may
  place any teacher in any teaching group or class.
- The workbook's Teachers sheet loses its "Can teach" and "at" columns, and the Lessons sheet's Check column no
  longer tests them. A workbook from before this change still opens: its Can teach columns are ignored.
- The skill's notes and version change with it, so the outside agent is not told of columns that are gone.
- Department heads lose the permission that existed only for this ("who a teacher can teach").
- A "Can teach" list already stored on a teacher is left where it is and never read again: nothing is converted,
  and a setup saved before this stage opens as it is.

**Two departments.** A teacher has one or two departments. The first is their home department.

- Wherever the app asks "is this teacher in this department", either one counts: the teacher is on step 5 in both
  departments' pages, so either head can place them. Wherever the app needs one department for a teacher (a list
  grouped by department, a published page), it uses the home department. A teacher's load counts once.
- The workbook's Teachers sheet gets a "Department 2" column next to Department. A workbook from before reads as
  one department.
- Only the committee gives a teacher a second department, on step 4. A head who needs a teacher from elsewhere
  finds them under "Others" on step 5 and places them; that does not change the teacher's departments.
- The second department is an ordinary detail of the teacher, like the role: when two committee members change it
  at once, the later change stands.

**Step 4, Teachers.** Two views: **Cards** and **Table**, and in both the Roles table moves **below** the teachers.

- Cards: one column per department. A teacher with two departments is in both columns, with both shown as chips on
  the card. Each card has the avatar, name, short name, role, and the teacher's load as a bar (periods given plus
  other duties, against the allowance), with today's load messages ("Over allowance…") in words under it.
- A row of department chips sits above the columns. Dragging a chip onto a teacher gives them that department as
  their second; the teacher's card also has a way to do the same by clicking, and to take a second department off.
- A click on a card opens the teacher: the same fields as the table row.
- "Provisional" stays, and says what it means where it shows: "added by a head, not yet confirmed".

**Step 5, the department page.** With the baskets gone:

- the department's teachers (home or second) are a strip at the top, each with their load; a teacher whose home
  department is another one is marked; "Others" finds any other teacher to place;
- the teaching groups and classes fill the page as larger cards, each with its students, its periods and its
  teachers by name;
- cards are laid out **by level first**, then by subject within the level (the committee lead's choice). The
  groups of one band sit together under the band's name.
- Placing a teacher works as today: drag onto a card, or tick and click.

**Step 8, who could take a lesson.** The Fix card, the helper and the typed request offer teachers to take over a
lesson. Today they are the teachers whose Can teach names the subject. From this stage they are, in this order:
the teachers who already teach that subject (any G-level, any level) somewhere in the setup, then the other
teachers of the subject's department (home or second). This is an order, not a new filter: the lesson's own
teachers, the judging of each offer against clashes and rules, and how many are shown before "more" all stay as
they are today. A teacher the lead names in a typed request is taken whoever they are, as now.

## Across all four stages

- **One set of data, two ways in.** A change made in a visual view is the same change the table makes: one save,
  one Undo step, picked up by the other committee members' pages in the same way, refused for a department head in
  the same cases.
- **Heads.** Steps 1 to 3 are read-only for department heads today and stay so: a head sees the cards and pictures
  and cannot change them. On step 4 a head still adds and edits provisional teachers only.
- **The view is remembered** for each person on each step, in their browser. The first time, a step opens on its
  visual view.
- **Every drag has a click.** Nothing can be done only by dragging.
- **Workbooks.** A stage that changes the workbook (stage 2: two Venues columns; stage 4: Teachers and the Check
  column) raises the skill's version as earlier stages did, and a workbook written before it still opens with
  nothing lost. Stages 1 and 3 do not change the workbook.
- **The school's size.** CTSS has about 90 rooms, 32 classes, 100 subject rows, 110 teachers and 1,000 lesson rows,
  on a two-week cycle with lessons of up to 3 periods. Every view must open and respond at that size without a
  pause a person would notice.

## Goals

- The committee can see rooms by block and floor, classes with their Class Parents and subjects, and the banding of
  a level, without reading a table.
- A subject with three G-levels is made by typing its name once.
- Nobody maintains "Can teach". A teacher who teaches in two departments is in both.
- Each stage is usable on its own and leaves everything else working.

## Not in this project

- Equipment or configuration deciding which lessons may use a room.
- Changing bands from the band picture.
- Floor plans drawn to scale, or moving a room by dragging it.
- A list of usual subjects to pick from.
- More than two departments for a teacher.
- Phone layouts: this is used at a desk.
- Per-teacher sign-in and what each person may see after publishing (project 3).

## What would make this a failure even if it works

- A visual view that shows something different from the table, or loses something the table can do.
- The committee's page slowing down or coming up dead on the school's real setup. This has happened once (a
  1-period subject under a lesson length of 3); every stage is tried on a setup shaped like CTSS's before it is
  merged, and reviewed on the real workbook.
- A workbook or a saved setup from before a stage that no longer opens, or opens with something missing.
- Stage 4 leaving the Fix card on step 8 with no teachers to offer.
- Anyone's real name, or the school's full name, in the code, the tests or these documents.

## Decided by the committee lead

1. The table stays on every step; the visual view is beside it.
2. Class cards show Class Parents (up to four), the subject combination, and the number of students once the
   student list is in.
3. A picture of how the subjects are banded across the classes.
4. Subjects: the slow part is typing every G1, G2 and G3.
5. Rooms carry a type, equipment and configuration; equipment and configuration are only shown.
6. Roles go below the teachers table.
7. "Can teach" is removed; departments replace it, and a teacher can have two.
8. Step 5 lays its cards out by level first.
9. The order: step 2, step 1, step 3, then steps 4 and 5 together.

## Decided by the writer of this document (to be checked on reading)

- The band picture is a third view on step 2 and read-only; step 5 links to it.
- A subject only part of the class takes shows this class's own count, not the group's.
- "Configuration" means how the room is laid out, one line of text; equipment is a short list.
- Equipment and configuration also go in the workbook and on the published room timetable.
- "New kind…" in the room editor; a neutral colour for a school's own kinds.
- A subject card is the rows with the same department, code and name less its tag; the data stays one row per
  G-level; ticking adds or removes a row and never renames one.
- A band that mixes subjects has a row of its own in the band picture.
- A stored "Can teach" is left in place and ignored.
- Step 8's new order changes only the order of the teachers offered.
- No list of usual subjects (it was in the first sketch; the lead's answer pointed elsewhere).
- Two departments at most; the first is the home department; only the committee sets the second.
- Step 8's teachers come from the setup's own lessons, then the department.
- The "not set to teach" mark is dropped, not replaced.
- A step opens on its visual view the first time.

## Left to the builder

- How the two departments are held on a teacher, and what happens to a stored "Can teach" (it must simply stop
  mattering; no step for the committee).
- The colours and icons of room kinds, the look of cards, bars and chips, within the page's present style.
- How a band whose classes are not next to each other is drawn (one bar in pieces, or the columns re-ordered).
- Whether `ttgen/allocate.py`, which nothing in the app calls, is removed or left.
- How the equipment list is written in its one workbook cell, as long as reading it back gives the same list.
- Where the published room timetable puts the equipment line.
- The words of every new sentence, in the plain style of the rest of the page.
- How each stage is tested, as long as it includes a setup shaped like the school's and a run on the real workbook
  (counts only: the real workbook and timetable are private).

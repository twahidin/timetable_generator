# Class Parents: a class's form teachers, and the lessons they take

Date: 11 November 2026. Status: design, awaiting the committee's approval of this document. A small project of its
own, beside project 2 (the return trip).

## Why

At CTSS every form class has up to four form teachers, called Class Parents. They take the class's
CP Time and its Character Education lessons together. The app has no idea of a form teacher: a teacher dropped on a
class card on step 5 is that class's teacher for that one subject, and nothing more. So today the committee types the
same two or three names on each class's Character Education 1 lesson and again on Character Education 2 (32 classes,
64 rows), nothing says who a class's Class Parents are, and a lesson cannot hold a fourth teacher at all, because the
workbook has only Teacher 1 to Teacher 3.

The committee lead asked for three things: a way to say who a class's Class Parents are; the name and the maximum as
school settings (other schools say "form teachers" and have two); and the Class Parents put on the class's CP Time and
CCE lessons, as a constraint, all of them together on every such lesson.

## What it is

1. **Step 2, Classes.** Each class has a Class Parents box: pick teachers from the step 4 list, in order, up to the
   school's maximum. The column's heading is the school's own name for them.
2. **Two school settings** (School & day, with the other school settings): what the school calls them (default "Form
   teachers"; CTSS sets "Class Parents") and the most a class can have (default 2, from 1 to 6; CTSS sets 4).
3. **A constraint on step 6** (the Settings tab, beside the other school-wide settings): "{Class Parents} take these
   lessons", with a pick-list of subjects. CTSS picks CP Time, Character Education 1 and Character Education 2. Empty
   means the constraint is off and the Class Parents are only recorded and shown.
4. **What the constraint does.** For every class and every subject it names:
   - the class's whole-class lesson of that subject has exactly the class's Class Parents as its teachers, all of
     them, in the order of the box on step 2;
   - when the subject has periods at the class's level and the class has no lesson of it yet, the lesson is made
     (this is how CP Time gets its 32 lessons);
   - the teachers of those lessons are changed in one place only, the box on step 2. On step 5 (the map and the
     table) those lessons show their teachers but do not take drops, ticks or typing, and say why: "Changed on step 2:
     these are the class's {Class Parents}."
   It is a Must. There is no Prefer form.
5. **A first fill.** While some class has no Class Parents and the constraint names at least one subject, step 2
   offers "Take them from the lessons": each such class gets the teachers now on its lessons of the named subjects
   (in the order they appear, each once, up to the maximum). Classes that already have Class Parents are left alone.
   The committee sees how many classes would be filled before agreeing.
6. **Four teachers on a lesson.** A lesson that the constraint staffs may hold as many teachers as the school's
   maximum. The workbook's Lessons sheet gets as many Teacher columns as the widest lesson needs (never fewer than
   three), the way it already grows its Class columns. Every other lesson keeps today's limit of three on the map and
   in the table.
7. **Where they show.** A small badge with the school's name for them on the class's cards on step 5; on a teacher's
   profile, "{Class Parent} of 3I4"; on the published class timetable, a line under the class's name; on a teacher's
   own published timetable, the same line as on the profile.
8. **In the workbook.** The Classes sheet gets one column per place ("Class Parent 1" to "Class Parent 4" at CTSS,
   named with the school's word in the singular as typed). The Settings sheet holds the name, the maximum and the
   subjects the constraint names. Reading a workbook back gives the same setup. A workbook from before this change
   reads as today: no Class Parents, the constraint off.

## What it is not

- Not a new kind of rule for the outside agent. The agent sees ordinary lesson rows with their teachers, as today,
  and timetables them as today. The constraint is kept by the app when the setup is built, and checked by the app
  when the timetable comes back, where a wrong teacher on such a lesson already shows as a difference from step 5.
- Not a permission. Being a Class Parent does not change what anyone can see or do in the app. Project 3 (who sees
  what) may use it later.
- Not a fourth teacher for every lesson. Only the lessons the constraint staffs go past three.
- No change to relief, allowances or roles. A Class Parent's periods on these lessons count toward their load the
  way any co-taught lesson's do today.

## What would make it a failure

- A class whose CP Time or Character Education lesson quietly has other teachers than its Class Parents, in the
  setup, in the workbook, or after a change on step 2.
- A fourth teacher dropped silently when the workbook is written or read.
- A committee that has typed its 64 rows being asked to type the Class Parents again.
- A department head, or a stale browser tab, changing those lessons' teachers behind the committee's back.

## Things to fix (the list on the right of every step)

- A class with no Class Parents while the constraint names a subject: "3I4 has no Class Parents: its CP Time and
  Character Education lessons have no teacher."
- A teacher who is a Class Parent of two classes: "{Name} is a Class Parent of 3I4 and 3I5: their CP Time and
  Character Education lessons cannot be at the same time." A warning only; some schools do this on purpose.
- A Class Parent who is no longer on the step 4 list.
- A subject the constraint names that is no longer on step 3.

## Rules that follow from the rest of the app

- Only the committee changes Class Parents, the two settings and the constraint. Department heads see them and
  cannot change them, and cannot change the teachers of a lesson the constraint staffs. The server refuses it, not
  only the page.
- Renaming or removing a teacher on step 4 does not follow through to lessons today: the old name stays on the
  lesson, flagged "(not on list)". Class Parents behave the same way, and stay in step with their lessons: the old
  name shows flagged in the box on step 2 and on the lessons it staffs, and putting the right name in the box puts
  it on the lessons. Renaming a class is the same as today too: the Class Parents stay with the class row.
- The lessons are always worked out from the boxes, never the other way round. After every change, wherever it
  comes from (the page, another tab, a department head, a workbook or progress file loaded, an earlier copy
  restored), the lessons the constraint staffs are put right again, on the page and on the server, and the server's
  result wins. A stale tab cannot leave them wrong.
- On Publish, a returned timetable with other teachers on such a lesson shows as a difference from step 5, as for
  any lesson. For these lessons "Update step 5" is not offered: the sentence says to change the class's Class
  Parents on step 2, or to fix the timetable.
- A Class Parent does not need the subject under Can teach on step 4. A lesson the constraint staffs never shows
  "cannot teach this subject".
- The maximum is a cap, not a quota: a class with one Class Parent is complete. Only a class with none is flagged.
- The lessons carry the periods step 3 gives the subject at the class's level, as every lesson does (in a two-week
  timetable, the periods of the two weeks). A level where the subject has no periods gets no lesson.
- The published pages take the Class Parents from the setup the timetable was checked against at publishing, not
  from the returned file, which does not hold them.
- A new class added on step 2 gets its lessons of the named subjects once it has a level, with no teachers until its
  Class Parents are picked.
- Turning the constraint off, or taking a subject out of it, leaves the lessons and their teachers as they are and
  makes them ordinary lessons again (changeable on step 5; a lesson holding more than three teachers keeps them, and
  the map says it is full).
- Lowering the maximum below what a class already has is refused with a sentence naming the classes.
- Changes save and merge by themselves like every other change, and Undo takes back the Class Parents change and
  what it did to the lessons as one step.
- The skill's copy of `ttgen` stays identical to the app's, and the skill's version line goes up, because the
  workbook's layout changes (more Teacher columns, new Classes columns, new Settings rows).

## Calls made in this document (the committee did not decide these; say if any is wrong)

- The constraint is a Must with no Prefer form.
- The default name is "Form teachers" and the default maximum is 2; the maximum can be 1 to 6.
- The constraint applies to a class's whole-class lesson of a named subject. A named subject taught in groups or
  bands is not touched and is listed under Things to fix as "cannot be staffed by {Class Parents}: it is taught in
  groups".
- A whole-class lesson shared by several classes takes the Class Parents of all of them, each once. It may then hold
  more teachers than the maximum; that is allowed, and the workbook grows its Teacher columns to fit.
- The constraint is worked out class by class. A class with a whole-class lesson of a named subject: that lesson is
  staffed. A class taught that subject in groups: left alone and listed under Things to fix. A class with neither,
  where the subject has periods at its level: the lesson is made.
- A Class Parent needs no Can teach entry for these lessons (see the rules above).
- "Update step 5" is not offered for a teacher difference on these lessons.
- The name, the maximum and the list of subjects are kept with the school's settings (`spec.school`), so only the
  committee can change them; in the workbook the new Classes columns come after Note and are read by their heading.
- A teacher may be a Class Parent of more than one class; it is a warning, not refused.
- The badge and the lines on the published timetables are part of this work, not a later one.
- The first fill takes teachers from the lessons of the named subjects only, and never overwrites a class that
  already has Class Parents.

## Left to the builder

- How the lessons are kept in step with the Class Parents (when it runs, on the page and on the server), as long as
  the rules above hold for every way a setup can change: the page, a department head's tab, a workbook or progress
  file loaded, an earlier copy restored, "Update step 5" from a returned timetable.
- The exact wording of the settings, the column headings and the sentences, in the app's plain style.
- Where the solver, the checks, the will-it-fit view, the PDF and the timetable pages assume three teachers, and what
  each needs.
- The tests. At least: the workbook round trip with four teachers and with the new Classes columns; the constraint
  after each kind of change listed above; a head's attempt refused by the server; the first fill on a setup shaped
  like CTSS's (two subjects naming the same one to three teachers per class, a third subject with no lessons).

## What exists today (for the builder)

- Classes rows hold `class, level, size, home_room, note`. Lesson rows hold `teachers` as a list of names. School
  settings live in `spec.school`; the step 6 settings are `SETTING_RULES` in `ttgen/spec.py`.
- Three teachers is assumed in `ttgen/template.py` (`NTCH = 3`, and `[:NTCH]` when writing), `ttgen/reader.py`
  (`_first_col(x, "Teacher", 3)`), `static/map.js` (`MAX = 3`) and the bulk tools of the step 5 table in
  `static/app.js`.
- In CTSS's v17 workbook, Character Education 1 and 2 each have one whole-class lesson per class (32 each); in every
  class both name the same teachers (two in 22 classes, three in 5, one in 5). CP Time is a subject with one period
  at every level and no lessons.
- What a department head may change is decided in `sync.py` (`head_may`, `_head_why`); today a head may send any
  change to a lesson row, and a lesson's teacher list is saved whole, last writer wins.
- More places that assume three teachers or the present columns: in `ttgen/template.py` the columns after the
  Teacher block on the Lessons sheet (`LIN`, `c0`, `TC` for Teacher periods) and the Classes sheet's fixed column
  list; in `static/app.js` the card's "room for more" count, the step 5 table's Teacher cells and the blank class
  row. The solver and `ttgen/verify.py` take a teacher list of any length; the published grid prints every teacher
  of a lesson, so four names in a cell need a look.
- The step 6 settings (`SETTING_RULES`) are Yes/No or a number today, and the workbook's Settings sheet validates
  them so; a list of subjects is a new kind of row there.
- `renameRefs()` in `static/app.js` is an empty stub: nothing follows a rename today.

# School timetable app

One deployment per school. The timetable committee builds the setup step by step and downloads it with the timetable
skill; an AI agent outside the app (Claude with the skill, say) makes the timetable from them; the committee uploads
the result, checks it and **publishes**. Teachers and students then open the published timetable with their access
code and download PDFs. The app does not generate timetables itself.

| Code (Railway variable) | Who | What they see |
|---|---|---|
| `COMMITTEE_CODE` | timetable committee | the setup editor, the downloads, Publish, the personal student codes |
| `TEACHER_CODE` | teachers | every class, teacher, room and student timetable, the lesson search, Who's free, PDFs |
| `HEADS_CODE` (optional) | heads of department | every step to read except Download, Publish and Students; everything on step 5 (who can teach what, who teaches which class, group or band, new groups and bands, moving rows between bands), and new teachers (marked provisional until the committee confirms them) to change; a refused change is skipped and reported, and the rest of their work is kept |
| `ANTHROPIC_API_KEY` (optional) | the committee, in Railway | with it set, the Fix card on step 8 has a box to type a request in words; only those words go to Anthropic. A server that still has `AI_PROVIDER=anthropic` and `AI_API_KEY` from an earlier version has the box too |
| `TYPED_REQUEST_MODEL` (optional) | the committee, in Railway | the model that reads the words, `claude-opus-5-5` unless set (with the earlier `AI_API_KEY`, the model `AI_MODEL` names); `mock` is a practice reader that needs no key |
| `STUDENT_CODE` | students | class timetables and **Build my timetable** (pick class and groups), PDFs of those |
| personal codes (made by the app) | one student each | only that student's own timetable and its PDF |

**The steps.** Start · School & day · 1 Venues · 2 Classes · 3 Subjects · 4 Teachers · 5 Department map ·
6 Configuration & constraints (the school-wide settings, teacher block-outs, fixed lessons and every other rule) ·
7 Download · 8 Publish · Students. Steps 1 to 4 have the same numbers as the workbook's sheets (1 Venues to 4 Teachers);
step 5 fills its 5 Blocks and 6 Lessons sheets, and step 6 its Settings, Teacher availability, Fixed lessons and More
rules sheets. Step 4 starts with the **Roles** (fill them first: the teacher list is checked against them), then the
teacher list, then the teachers table.

**Form teachers.** A class can have form teachers, who take its lessons together. **School & day** has two settings for
them: what the school calls them (**What your school calls a class's form teachers**, default "Form teachers"; a school
may type "Class Parents" and that word then takes the place of "Form teachers" everywhere below) and **Most a class can
have** (1 to 6, default 2; lowering it below what a class already has is refused). On step 2 each class's form teachers
are picked in order from the step 4 list. When some class has none, **Take them from the lessons** (it asks first) fills
the classes that have none from the teachers already on their lessons of the subjects step 6 names. A line above the
table counts the lessons changed by hand and offers **Put the Form teachers on all of them** (it asks first). Only the
committee changes any of this.

The student list goes in on the **Students** step, after the timetable is made (it is not needed to make one): paste it from Excel or a CSV, or upload an .xlsx or
.csv, with each student's ID, name, class and group codes; the committee can then edit each student's groups there.
To fill groups in the app, tick students (shift-click for a run, or the top box for everyone shown) and **Add to group**,
**Remove from group** or **Move to class** for all of them at once; a group in a band replaces the student's other group
in that band.
Things to fix lists students who are in none of the groups of a band over their class (so they would miss that
subject), one note per band. Having the subject in another band counts; a Note with "Exempt" and the subject ("Exempt
from MTL") excuses them; untick **Everyone takes one** on a band that is an option (it starts unticked for a band named
Option or Elective).

**Restoring.** The server keeps restore points of the setup in `setup_history/` (see Saving the setup below). When
students have no groups or bands no classes, the Students step shows **Restore from an earlier copy**: pick a copy and it
fills only those students (by Student ID) and bands; nothing else changes and Undo takes it back. To go back to an
earlier copy of the whole setup, use **Restore an earlier copy** on step 7, Download.
The student list is optional, but with it the checks make sure no student has two lessons at once, and every student
gets a personal code. Personal codes are made from each student's ID and `SECRET_KEY`, so they stay the same when the
timetable is republished; without `SECRET_KEY` they are off. The committee downloads them as a list (CSV) or as slips
to print, one page per class. Students not on the list use the general student code and Build my timetable.

## From setup to published timetable

1. **Build the setup** on the steps. The **Things to fix** panel lists what does not add up. *Critical* (red): no
   timetable can be made until it is fixed (a teacher on two groups of one band, a fixed lesson outside lesson time,
   fixed lessons that put one teacher in two places). *Warnings* (amber): a timetable can still be made, but a person
   should look (a teacher over their allowance, a room that seats too few, a rule that matches no lesson). Form teachers add
five lines: a class with none yet ("3I4 has no Form teachers yet."), a form teacher who is not on the teacher list, a
teacher who is a form teacher of two classes (a warning: their lessons cannot be at the same time), a named subject that
is not on step 3, and a named subject the class has only in groups.
2. **Will it fit?** Step 7 opens with the sums on the setup as it stands, before anything goes to an agent: each
   class's periods against the lesson periods of its days, lessons against the stretches between breaks (a 3-period
   lesson cannot run across recess), a lesson longer than any stretch, special rooms against the lessons that need
   them, each teacher's lessons against the times they can teach, and floating recess that cannot work. Critical
   first, each with a button to the step that fixes it; it runs again whenever the setup changes (`checks.py`).
3. **Download** (step 7): the configuration workbook and the timetable skill. Use the skill zip when the agent can run
   code: its scripts make a timetable file this app publishes as it is. `SKILL.md` alone is for an agent that cannot.
   `SKILL.md` carries a version line (`Skill version: 2026-11.3`) and the workbook's README sheet names the version it
   was made for. When the setup has second choices (step 6), step 7 counts them and asks **If the first choices do not
   fit:** **Fall back only when needed** (the default) or **Make one timetable for each**; the workbook carries the pick
   on its Choices sheet. Every downloaded workbook also carries a **Configuration id** row on Settings (`v14`, or `v14+`
   when it was downloaded with changes not yet saved). A **Starter prompt** card has the text to paste into the chatbot
   with the two files, with a **Copy** button: use the attached skill, check first, hand back the database or a Lessons
   workbook, fill in the rule report and the Choices used sheet.
4. **Make the timetable outside**: give the agent both, and ask it to generate the timetable and report anything that
   does not fit. It hands back a timetable database (`.sqlite`) or a timetable workbook (a Lessons sheet).
5. **Publish** (step 8): upload that file (a workbook comes with its setup workbook; a database made by the skill holds
   its setup) and press **Check**. The upload becomes the **draft**, kept on the server, and the app checks it four ways
   against the setup as it is now: clashes (teacher, class, room and student double-booked, lessons outside lesson time),
   differences from the deployment (who teaches what, periods placed against periods planned, rooms; other teachers than the
   form teachers on a lesson they take show here like any other, and **Update step 5** keeps the timetable's teachers and
   marks the lesson "Changed by hand"), the setup's rules,
   and the typed rules and choices used that the agent reported. A warning for another school than the saved setup, and
   which configuration the timetable was made from, are shown too. The warnings are listed by kind and then by class,
   teacher or group, with the timetable's side and step 5's side. For each one, **Update step 5** changes the setup to
   match the timetable, and **Leave it** keeps the warning on the list as left for now (**Reopen** takes it back);
   what you left stays left when you upload the file again. A rule in words that reads **Check again** has a **Still met**
   button for when you have looked. **Fix the timetable** (on a warning, or the Fix card below the list) shows one
   class's or one teacher's week as a table; pick a class or a teacher, and a week when the school has two, then select a
   lesson. Every slot is coloured by what a fix there would do (green is open, amber is open but less wanted, red is
   not allowed, grey is a slot the lesson cannot go to: not lesson time, outside the day, or another lesson is there
   that it cannot swap with); click a green or amber slot to move the lesson, or a lesson there to swap with it (in a
   teacher's week an open slot can be a swap with the class's lesson there; a swap that also moves another class's
   lesson opens **Before you apply** first, with that class's week). The side panel also changes the teacher or
   the room, deletes an extra lesson, and, with nothing selected, lists a class's missing periods with **Add a lesson**.
   Every fix is kept with its sentence under **Fixes**, and **Undo the last fix** takes the last one back. A fix that
   would cause a clash, change a subject's periods from the plan or newly break a Must rule is refused (red), so a clean
   draft stays clean. **Fix the timetable** on a warning also opens **Ways to settle this**: up to three ways, each
   already checked, with what each one disturbs and whether it is clean or bends a Prefer. **Show** opens **Before you
   apply** under the grid: the sentences, and the week of each other class the fixes touch with the moved, changed or
   new lessons outlined; **Apply** makes the fixes, **Cancel** leaves everything as it was. Where one fix is not enough
   a way can be two fixes made together; they are one entry under **Fixes** and **Undo the last two fixes** takes both
   back. With `ANTHROPIC_API_KEY` set, the Fix card also has a box above the ways: type what you want in your own words ("move PE for 2A off Friday", "give 2A maths to Mdm Lee"). It takes three kinds of request: move lessons, change who teaches a lesson, change a lesson's room. A language model only reads the words into a small request; the app finds the lessons and people itself, asks which one when a name could be several, and runs the same checks as **Ways to settle this**, showing up to three ways per lesson with **Show** and **Apply**. Nothing changes until you press Apply, and anything else you ask to keep is repeated back as not checked. The whole site can send 30 requests in 10 minutes. If the words cannot be read, the box says so and the helper's own suggestions carry on; without the key the box is not there and the helper works as before. When no way settles a warning the panel says so and lists the nearest ways with what each breaks; those are
   blocked (they would cause a clash or newly break a Must rule) and have no button. **Download the
   draft (.sqlite)** carries the draft with its fixes elsewhere (Make printouts accepts it). **Publish this
   timetable** then makes the draft what teachers and students see, with every download and the personal student codes
   (about a minute), even with warnings open: **Published now** says which setup version it was checked against, how many
   warnings were left open and what they said, and lists the fixes made in the app. The rule report and the choices used stay with the published timetable.
   The published class timetable names the class's form teachers under its title (on the PDF as a line of its own), and a
   teacher's timetable says which classes they are a form teacher of; both come from the setup it was checked against.
   **Make printouts** gives the same files without publishing. For an agent, `python -m ttgen check-timetable
   TIMETABLE [--setup SETUP.xlsx]` prints the same check.

**Timetable database.** Publishing (and every export, in the app or with `python -m ttgen export`) also writes the
timetable as a SQLite database: every lesson with its day, times, classes, teachers and room, plus the classes,
teachers, rooms and the setup itself, for importing into other systems. **Make printouts** on step 8 reads one back:
upload it alone (it holds its setup) or with a setup workbook, and get every output again.

**What a timetable compromises.** An overloaded teacher still gets every lesson: allowance is not a limit the solver
keeps, and Prefer rules bend when they must. The Excel workbook lists what was given up on a **Compromises** sheet
(teachers over their allowance, each Prefer rule not kept, Max periods in a row), and its Teacher load sheet shows other
duties and a red "Over allowance by" column.

**The department map (step 5).** The step opens on a map with three columns; **Table** at the top switches to the
15-column table of the same rows, for bulk edits, bands and new groups (the choice is remembered in the browser).
On the left, the **roster**: a department switcher (every head sees every department), then its teachers with a tick
box, avatar, role and a load bar (periods deployed plus other duties against the allowance; red when over). **Select
all** (it shows a dash when only some are ticked), **Deselect all** and **Not placed yet** (ticks the teachers with no
subject) sit above the list; shift-click ticks a run. The search box finds a teacher on the roster, and lists matching
teachers of other departments with **+ Add to roster**, for a teacher who teaches a subject outside their own
department. **+ New teacher** adds a hire or a post still to be filled: name (or a placeholder such as "New Mathematics
teacher 1"), short name, department, role and allowance (the role's guide when left empty); a head's new teacher is
provisional until the committee confirms them on step 4.
In the middle, **Can teach**: a basket per subject of the department with the avatars of everyone who can teach it (each with the teacher's short
name under it, the full name on hover; the cards on the right show the names the same way), from
any department, and a **Staff room** for roster teachers with no subject yet. Tick teachers and click a basket, or drag
them in (dragging a ticked teacher drags every ticked teacher). The ✕ on an avatar in a basket takes the subject off
them; dropping teachers on the staff room takes them out of every basket of the department. Either asks first, and says
how many lesson rows still name them for it: those rows are not changed, and Things to fix flags them.
On the right, **where they teach**: tabs **Classes** (one card per class for a whole-class lesson), **Teaching groups**
and **Bands** (a lane per band, its groups inside; a teacher on two groups of one band is flagged on the lane), filtered
to the department's subjects, with a level filter. Each card shows the code, subject, level, periods and up to three
teachers. Click a card, or drop teachers on it, to deploy the ticked teachers: deploying **adds** (co-teaching), never
replaces; a card that would go past three says so and takes none; the ✕ on an avatar takes that teacher off. A teacher
must be in the subject's basket first: dropping one who is not asks whether to add them to the basket and place them. On
Classes, a whole-class row that lists several classes shows one card per class, and changing one class's teachers moves
that class to a row of its own in the table (the solver already treats each class's lesson separately). Every click or
drop is one change: one Undo takes it back.
Clicking any avatar (not its tick box) opens the teacher's **profile** in place of the cards: avatar with **New look**,
name, role, department, load against allowance, **Can teach** with the levels (editable there, ✕ to remove a subject)
and **Teaches** (every class and group they are on, ✕ to take them off). Details are changed on step 4.

**Groups and bands (step 5).** The second view, **Groups and bands**, is where teaching groups and bands are made.
On the left, **New teaching group**: level, G-level (filters the subjects), subject, band (none = a whole-class
lesson), classes (empty = the band's classes) and students; the group code forms as you pick (level digit, subject
code, G-level letter, running number, as the workbook has it) and **Add** makes the row. **Add one per class** makes a
whole-class row for each class picked, or for every class of the level, skipping classes that have the subject already.
Below it, **New band**: level, the subjects it covers, its classes (every class of the level unless you change them) and
a name that forms from the level and subjects ("Sec 2 Mathematics"; "Sec 3 Option A" for a band of several subjects,
the next free letter) and can be typed over; a name already used is refused. **Everyone takes one** is on unless the
name says Option. **Add band** makes it and sets the group form's band to it.
In the middle, **Not in a band**: the level's whole-class rows and pull-out groups, with a subject filter, **Select all
shown** and **Deselect all**. Tick rows and **Move** them into a band, or drag a row (or every ticked row) onto a lane on
the right. A whole class moved into a band becomes a group of it, and the band's classes widen to cover it. On the
right, the level's bands as lanes, each with its groups (code, subject, students, teachers) and a ✕ that puts a group
back in the pool; a teacher on two groups of one band is flagged on the lane. Moving a row changes later codes of that
subject (1MAP3 becomes 1MAP2): the page says which, and when a student list names the old codes it asks first and
says how many students are affected. The table view keeps the 15-column rows for bulk edits.

**How a group's periods split into lessons.** The Lessons column on step 5's table view shows the usual split in grey (20 periods with a
3-period lesson: 6×3 + 1×2). Type your own, such as `5x3 + 2x2` or `4x3 + 4x2`, on one row or on all ticked rows, or clear it to
go back. It must add up to the row's periods, and a band's groups should share a pattern; Things to fix flags both. The
workbook carries it in the Lesson pattern column on the Lessons sheet.

**Deploying in the table view.** On the same view, filter the teaching groups by level, subject or teacher, tick rows (shift-click
for a run), pick a teacher and **Make Teacher 1**, **Add as co-teacher** or **Take off** for all of them at once. The bar shows
the teacher's load now and with those groups; groups they are not set to teach, or two groups of one band, are flagged.
On step 4 (Teachers), filter by department or subject, tick teachers and give them a subject they can teach (at all
levels, one level or a band of levels), take a subject off them, or set their department, role or allowance together.
A row may name up to three teachers (co-teaching), each blocked for the lesson and counted the full periods.
A lesson the form teachers take may hold as many as the school's most (never fewer than three). On the map its card shows
the school's word as a badge, and the table row shows "Changed by hand" when it applies. The committee can still
change one such lesson by hand; it is then marked "Changed by hand" and no longer follows step 2 until **Back to the
Form teachers** puts them on again. A form teacher needs no Can teach entry for their own class's lesson. Heads of
department see these lessons and cannot change them.

**The teacher list.** On step 4 the committee can upload the school's teacher list. In a practice copy (the sample
school, to try things on) a head of department can too; on the school's own setup a head cannot. Paste
it, or choose a .csv file or, with the committee's code, an .xlsx file: for an Excel file the sheet is the first one
whose name contains "teacher", else the first sheet. The columns are Name, Short name, Department, Role, Allowance,
Other duties and Note, with the usual spellings of each heading (Teacher, Dept, Initials, Remarks and so on) read too.
Only Name is needed, and with no heading row the columns are read in that order. A column you leave out is not
changed: a list of names and roles leaves everyone's allowance as it is. A new teacher with no short name gets the
first word of the name. One with no allowance gets the guide allowance of their role when the row names a role on the
Roles table that has a guide; otherwise the allowance is left blank.
**Read the list** changes nothing: it shows "N new · M to update · K unchanged", names the new teachers, says what the
updates change (for example "Changes: allowance 80 · short name 12"), notes a row with no name or a name that is in the
list twice (that row is left out), and says if it cannot find a name column. A new name that looks like a teacher who
is not in the list ("Tan Wei-Ming" and "Tan Wei Ming") gets a warning: if they are one person, make the two names
match and read the list again, or Apply adds a second teacher. A role or department that is not yet on the setup is
listed, with **Add these roles** or **Add these departments**. **Apply** adds and updates in one step (one Undo takes
it back); an updated teacher keeps their lessons and what they can teach. Before a list that makes 10 or more
changes to the teachers, the server keeps a restore point (**Restore an earlier copy**, on step 7, brings it back).
Teachers who are not in the list are never removed by Apply: they are listed as "not in this list", and **Remove**
asks first, saying how many lessons on step 5 name them.
Removing a teacher takes them off the lessons they were on: those lessons lose that teacher, and a shared lesson keeps
its other teacher. Availability rules on step 6 that name them stay, and step 6 flags them.

**Teacher avatars.** Each teacher has a small face, on the table here and on the map on step 5. It is worked out from
the teacher's name, so the same name has the same face wherever it is shown, and it is drawn in the browser from fixed
parts: no picture is uploaded or stored, and nothing is sent to an outside service. **New look**, on the teacher's
profile on step 5 (click any avatar on the map), gives the teacher another one by adding one to a number kept on the
teacher's row. The committee can do this for any teacher; a head of department only for a provisional teacher. The number is part of the saved setup only, so the workbook does not carry it and a setup opened
from a workbook starts with the faces the names give.

## Deploy on Railway

Each school runs its own copy: one Railway service with its own volume and access codes.
**[docs/DEPLOY.md](docs/DEPLOY.md)** walks through it: every variable with a safe default, memory, the first sign-in
and loading the setup. In short:

1. Fork this repository. Railway: **New Project → GitHub repo** → pick it (it has a `Dockerfile` and `railway.json`).
2. **Attach a volume** to the service, mounted at `/data`. The saved setup and the published timetable live there;
   without a volume they are lost on every deploy.
3. **Variables:** `SECRET_KEY` (a long random string; keep it), `COMMITTEE_CODE`, `TEACHER_CODE` and `STUDENT_CODE` (at
   least 6 letters or digits each, all different).
4. **Settings → Networking → Generate Domain**, open it and sign in with the committee code. The sign-in page and the
   deploy logs list anything still missing (a code, `SECRET_KEY` or the volume).

Coming from a version that generated in the app: the `AI_*` and `SOLVE_SECONDS` variables are no longer read
([details](docs/DEPLOY.md#coming-from-an-earlier-version)).

## What the setup can say

These are read by the skill's solver (`ttgen`), which the outside agent runs, and checked again by the app on Publish.

A room holds one class at a time unless step 6 has a "Room · At most N at once" rule; a note on a Settings row such as
"Field and Hall take 2 classes each" is read as those rules.

**Constraints (step 6):** below the Configuration card, the constraints sit under five tabs by what they apply to:
**School** (whole-school fixed lessons such as CCE, the HBL day, school-wide rules), **Levels and classes** (fixed
lessons for a class or a group, rules for a level, class, band or group), **Subjects** (rules for a subject or a
department, such as lessons late in the day only in some rooms), **Venues** (room limits and bookings) and **Teachers**
(block-outs and teachers' rules). Each tab has its **Standard rules** table (the rule types below, with the Applies to
list narrowed to the tab), a **Typed rules** table and, folded away, the rule types that apply to the tab. **+ Add
rule** and **+ Typed rule** on a tab add a row for that tab.

**Typed rules** are anything the list cannot say: **Must** or **Prefer**, what it applies to (the whole school, a level,
a class, a subject, a venue or a teacher, from the same lists as other rules) and a sentence, such as "Must · Sec 1 ·
No PE in the first period". They are numbered T1, T2… in setup order and go to the workbook as More rules rows with
Rule = **In words** and the sentence in the **In words** column (an older workbook without the column still opens). The
timetable scripts never enforce them: `python -m ttgen check` lists each one "for the agent to honour", `SKILL.md` tells
the agent to honour every Must, try every Prefer and hand back a rule report, and step 7 counts them. A typed rule with
no sentence is flagged on step 6 and by `check`.

**Form teachers' lessons (step 6):** in the Configuration card, **Form teachers take these lessons** names subjects (tick
them from step 3). For every class, its whole-class lesson of each named subject then has the class's form teachers, all
of them together and in the order of the box on step 2, and follows that box. A missing lesson is made when the subject
has periods at the class's level. This is a default, and typed teachers are never replaced: when the class has form teachers and the lesson holds other
people, the lesson keeps its teachers and is marked "Changed by hand"; a lesson with nobody on it takes the form teachers;
a lesson with the same people simply follows. Turn it off by naming no subject; the lessons then stay as they are. The agent sees ordinary
lessons. A subject taught in groups is left alone. In the workbook, the Lessons sheet has as many Teacher columns as the
widest lesson needs (never fewer than three) and a **Changed by hand** column; the Classes sheet has one column per form
teacher, headed with the school's word and a number; Settings has three rows for the word, the most and the subjects. An
older workbook reads as before: no form teachers, the rule off, and teachers typed on a named subject's lessons kept.

**First and second choices (step 6):** below the constraints, **If it does not fit, give way in this order** lists items
that have a second choice. **+ Add a second choice** picks the item (a setting that is Yes/No or a number, a rule, or a
level's recess) and what to do instead: a setting takes the other value; a rule is made **Prefer**, replaced by another
rule (**Use this instead**) or **Drop**ped; a recess becomes floating between two times (recess for a level that has a
fixed recess). Drag the rows, or use the arrows, to set the order; an item has one second choice. Deleting a rule on step 6
removes its second choice; a workbook row whose rule or level has gone says what is missing. The workbook carries them on a **Choices** sheet (First choice and Second choice
columns, in order) with the pick from step 7. The agent tries the first choices; if no timetable fits, `python -m
ttgen solve` gives way one item at a time from the top of the list and stops at the first timetable that fits, never
changing anything that is not on the list (the setup's own rows are not changed: each fallback is applied to a copy).
With **Make one timetable for each** it makes the first-choices timetable and one more after each step of the list
(`... - after choice 2.xlsx`, or one folder each with `--export`) for the committee to compare. It hands back a
**Choices used** sheet (item, First or Second choice, how), also written to the database, which Publish reads. Step 7's
"Will it fit?" also says whether the sums pass after giving way ("With the first choices, 1 thing will not fit. Giving
way in your order, the sums pass after choice 3: ...") or that they fail even after every second choice. Heads of
department see the list but cannot change it.

**Rules (step 6):** besides teacher block-outs, three common school rules have their own one-click rows. **Every
class at one time** puts a subject at one slot for every class of a level, or of the whole school (Fixed lessons, Class
"Every class", Level All), such as whole-school CCE: one row per slot. **HBL day** (the rule *Only these subjects*) lets
only the subjects ticked be taught in those periods; tick a department for all its subjects, or a subject for all its
G1/G2/G3 groups. **Lessons late in the day only in some rooms** (*Only in venues*) keeps a subject's lessons that run into
the periods picked to the rooms picked, such as PE after 11.00 only in the hall. Under every rule the solver cannot use
as written (a rule name it does not know, a level or subject not on the setup, a rule that matches no lesson) step 6
says what is wrong and what happens to it; opening a workbook says how many there are, and `ttgen check` lists them.
Fixed lessons that put one teacher or one class in two places (a whole-school CCE slot when a teacher takes CCE for two
classes) are critical, with the teacher named.

**Rooms:** a group only goes in a room of its subject's kind that seats it (Venues **Capacity** = seats; the group size
is the Students sheet count for its code, the row's Students, or the class size). A room's **For** column keeps it for
some subjects, departments or levels (blank = anyone). A lesson row's **Special room weeks** (Odd or Even) gives the
group its lab or studio on that week only and a classroom on the other. The solver keeps enough suitable rooms free at
every period; afterwards each group gets the smallest free room that seats it (whole-class lessons their home room,
and a group keeps its room where it can). The checks flag a room too small, a room used against its purpose, a lesson
with no free room, and groups bigger than every room they may use (fix the seats or split the group). About 1 GB of
memory is enough for a 1,500-student school.

**Floating recess:** paint **W** (recess window) periods on Day structure where the recess may go, for example
periods 5-10 instead of a fixed recess at 7-8. The solver places the recess inside each window and uses the rest of
the window for lessons. Settings: **Floating recess goes by** Level (the whole level goes together, its time may
differ by day) or Class (each class on its own); **Floating recess length (periods)**; **Most classes at recess at
once** (canteen space; fixed R recess counts too; blank = no limit). Make each window the recess plus whole lessons
(2 + 3 + 3 periods with 3-period lessons), so the lessons still fit wherever the recess goes: on a full school, a
recess that leaves an odd period beside it costs a lesson, and a tight canteen limit can then leave no timetable. With "Every teacher gets at least one recess a day"
on, every teacher is free for a whole R recess, or the recess length inside a W window, each day. The class timetables,
PDFs and pages show each class's own recess; the timetable workbook lists them on a Recess sheet.

A big, tight school (30 or more classes) is best solved level by level, hardest level first: the skill's
`python -m ttgen solve --staged` (`ttgen/staged.py`). One whole-school search can find nothing for hours.

## Run locally

```bash
pip install -r requirements.txt
export SECRET_KEY=dev COMMITTEE_CODE=COMMIT1 TEACHER_CODE=TEACH1 STUDENT_CODE=STUDY1 HEADS_CODE=HEADS1   # HEADS_CODE is optional
python app.py            # http://localhost:8000  (or: gunicorn app:app --workers 1 --threads 8 --timeout 600)
.venv/bin/python tests/smoke.py          # server checks; add --full for the slow publish check (SMOKE_NO_HEADS=1: without a heads' code)
.venv/bin/python tests/test_sync.py      # the setup changes, in Python
node tests/sync.test.js                  # the same changes, in the browser's JavaScript
node tests/people.test.js                # reading a teacher list and the avatars
node tests/split.test.js                 # periods cut into lessons, as ttgen cuts them
.venv/bin/python tests/test_typed.py     # the typed request: reading the words, matching names, the ways
```
To try the Fix card's box without a key, start with `TYPED_REQUEST_MODEL=mock`: it understands "move <subject> for <class> off <day>" and "give <class> <subject> to <teacher>".

Keep one gunicorn worker (with threads): publishing swaps files in under a lock held in the web process.

**Saving the setup.** There is no Save button: every change is saved for the school by itself, on the volume, and the
setup opens by itself after signing in, on any browser. Several people can work in it at once. Changes to different
things all stay; if two people change the same field, the later one wins and the other sees it within a few seconds.
The header shows **Saved**, **Saving** or **Offline**, and how many others are in the setup. **Undo** / **Redo**
(⌘Z / ⇧⌘Z) take back only your own changes. Changes made while the server cannot be reached are kept in the browser
and sent when it can. While people work the server keeps a restore point about every 10 minutes (the last 48), and one
before every whole-setup action; **Restore an earlier copy** on step 7, Download, brings one back. The sample schools
open as a practice copy: nothing in it is saved for the school. Starting blank, opening a setup workbook, loading from
a file and restoring an earlier copy replace the setup for everyone: they are for the committee only, they ask first,
and an earlier copy is kept. **Save to file** and **Load from file**, on step 7, keep copies as files.

## What's inside

| Path | What |
|---|---|
| `app.py` | routes: sign-in, the committee's editor, the downloads, check and publish, the timetable pages, PDFs |
| `access.py` | access codes (committee, heads, teachers, students), personal codes, wrong-code limit (10 per 10 minutes per address) |
| `checks.py` | will it fit: the sums on a setup before it is downloaded (class periods, breaks, rooms, teachers' time) |
| `store.py` | the shared setup (version, change log, restore points) and the published timetable on the volume |
| `sync.py` | setup changes as small operations: apply, merge, and what a head may change |
| `static/sync.js` | the same operations in the browser; Node can run it for the tests |
| `tests/smoke.py` | server checks, run with plain Python (no test runner) |
| `tests/test_sync.py`, `tests/sync.test.js` | the setup changes, checked in Python and in JavaScript against the same cases |
| `static/people.js` | reading a teacher list, matching it to the teachers already there, and drawing the avatars; Node can run it for the tests |
| `typed.py` | the typed request on the Fix card: the one place a language model is called (the words in, a small request out), then the names matched to the draft and the ways checked, with no model |
| `tests/test_typed.py` | those, with no network and no key |
| `tests/people.test.js` | those checks, run with Node |
| `static/parents.js`, `ttgen/parents.py` | the form teachers' rule, written twice for the page and the server and kept in step by `tests/parents_cases.json` |
| `tests/parents.test.js`, `tests/test_parents.py` | those cases, run with Node and with Python |
| `tests/split.test.js`, `tests/split_cases.json` | how a subject's periods are cut into lessons, the same on the page and in `ttgen` |
| `static/` | the committee's step-by-step editor and the sign-in page style |
| `ttgen/` | the Python package: template, reader, solver, checks and the Excel/PDF/HTML outputs |
| `skill/school-timetable-generator/` | the skill (`SKILL.md` + `scripts/ttgen`) for any AI agent outside the app |

`ttgen/` and `skill/school-timetable-generator/scripts/ttgen/` are the same package; change both together.

## Command line (without the app)

```bash
cd skill/school-timetable-generator/scripts
pip install -r requirements.txt
python -m ttgen check  My_School_Timetable_Setup.xlsx
python -m ttgen solve  My_School_Timetable_Setup.xlsx --out My_School_Timetable.xlsx --time 300 --export My_School_Outputs
python -m ttgen export My_School_Timetable_Setup.xlsx My_School_Timetable.xlsx --out My_School_Outputs
```

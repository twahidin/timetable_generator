# School timetable app

One deployment per school. The timetable committee builds the setup step by step and downloads it with the timetable
skill; an AI agent outside the app (Claude with the skill, say) makes the timetable from them; the committee uploads
the result, checks it and **publishes**. Teachers and students then open the published timetable with their access
code and download PDFs. The app does not generate timetables itself.

| Code (Railway variable) | Who | What they see |
|---|---|---|
| `COMMITTEE_CODE` | timetable committee | the setup editor, the downloads, Publish, the personal student codes |
| `TEACHER_CODE` | teachers | every class, teacher, room and student timetable, the lesson search, Who's free, PDFs |
| `HEADS_CODE` (optional) | heads of department | every step to read except Download, Publish and Students; groups, bands, who can teach what, and new teachers (marked provisional until the committee confirms them) to change; a refused change is skipped and reported, and the rest of their work is kept |
| `STUDENT_CODE` | students | class timetables and **Build my timetable** (pick class and groups), PDFs of those |
| personal codes (made by the app) | one student each | only that student's own timetable and its PDF |

**The steps.** Start · School & day · 1 Venues · 2 Classes · 3 Subjects · 4 Teachers · 5 TG & deployment ·
6 Configuration & constraints (the school-wide settings, teacher block-outs, fixed lessons and every other rule) ·
7 Download · 8 Publish · Students. Steps 1 to 4 have the same numbers as the workbook's sheets (1 Venues to 4 Teachers);
step 5 fills its 5 Blocks and 6 Lessons sheets, and step 6 its Settings, Teacher availability, Fixed lessons and More
rules sheets. Step 4 starts with the **Roles** (fill them first: the teacher list is checked against them), then the
teacher list, then the teachers table.

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
   should look (a teacher over their allowance, a room that seats too few, a rule that matches no lesson).
2. **Will it fit?** Step 7 opens with the sums on the setup as it stands, before anything goes to an agent: each
   class's periods against the lesson periods of its days, lessons against the stretches between breaks (a 3-period
   lesson cannot run across recess), a lesson longer than any stretch, special rooms against the lessons that need
   them, each teacher's lessons against the times they can teach, and floating recess that cannot work. Critical
   first, each with a button to the step that fixes it; it runs again whenever the setup changes (`checks.py`).
3. **Download** (step 7): the configuration workbook and the timetable skill. Use the skill zip when the agent can run
   code: its scripts make a timetable file this app publishes as it is. `SKILL.md` alone is for an agent that cannot.
4. **Make the timetable outside**: give the agent both, and ask it to generate the timetable and report anything that
   does not fit. It hands back a timetable database (`.sqlite`) or a timetable workbook (a Lessons sheet).
5. **Publish** (step 8): upload that file (a workbook comes with its setup workbook; a database made by the skill holds
   its setup) and press **Check, then publish**. The app checks it against its setup (teacher, class, room and student
   clashes, lessons outside lesson time, periods placed against periods planned) and lists what it found, with a
   warning when it is for another school than the saved setup. **Publish this timetable** then makes it what teachers
   and students see, with every download and the personal student codes (about a minute). **Make printouts** gives the
   same files without publishing.

**Timetable database.** Publishing (and every export, in the app or with `python -m ttgen export`) also writes the
timetable as a SQLite database: every lesson with its day, times, classes, teachers and room, plus the classes,
teachers, rooms and the setup itself, for importing into other systems. **Make printouts** on step 8 reads one back:
upload it alone (it holds its setup) or with a setup workbook, and get every output again.

**What a timetable compromises.** An overloaded teacher still gets every lesson: allowance is not a limit the solver
keeps, and Prefer rules bend when they must. The Excel workbook lists what was given up on a **Compromises** sheet
(teachers over their allowance, each Prefer rule not kept, Max periods in a row), and its Teacher load sheet shows other
duties and a red "Over allowance by" column.

**How a group's periods split into lessons.** The Lessons column on step 5 shows the usual split in grey (20 periods with a
3-period lesson: 6×3 + 1×2). Type your own, such as `5x3 + 2x2` or `4x3 + 4x2`, on one row or on all ticked rows, or clear it to
go back. It must add up to the row's periods, and a band's groups should share a pattern; Things to fix flags both. The
workbook carries it in the Lesson pattern column on the Lessons sheet.

**Deploying by hand.** On the same step, filter the teaching groups by level, subject or teacher, tick rows (shift-click
for a run), pick a teacher and **Make Teacher 1**, **Add as co-teacher** or **Take off** for all of them at once. The bar shows
the teacher's load now and with those groups; groups they are not set to teach, or two groups of one band, are flagged.
On step 4 (Teachers), filter by department or subject, tick teachers and give them a subject they can teach (at all
levels, one level or a band of levels), take a subject off them, or set their department, role or allowance together.
A row may name up to three teachers (co-teaching), each blocked for the lesson and counted the full periods.

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
```
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
| `tests/people.test.js` | those checks, run with Node |
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

---
name: school-timetable-generator
description: Generate a clash-free Singapore school timetable from a filled setup workbook (.xlsx) and deliver class, teacher, room and student timetables as Excel, PDF and searchable HTML.
---

# School timetable generator

Turns a filled **timetable setup workbook** into a timetable with no teacher, room or student in two places at once,
then delivers it in three forms that always agree with each other:

- **one Excel workbook** with every class, teacher, room and student timetable (each prints on its own page);
- **PDFs**: one page per class, teacher, room and student, as printable books with bookmarks and as single files;
- **one HTML page** to search and filter everything, offline, in any browser.

Works for Singapore primary (weekly, 30-minute periods) and secondary (two-week Odd/Even cycle, 20-minute periods,
subject-based banding) schools, and for any school that fills the same template.

## What you need

- The filled setup workbook (`.xlsx`). Its sheets, in order: `README`, `Settings`, `Period times`, `Day structure`,
  `1 Venues`, `2 Classes`, `3 Subjects`, `4 Teachers`, `Roles`, `5 Blocks`, `6 Lessons`, `Teacher availability`,
  `Fixed lessons`, `More rules`, `Rule types`, `Students`, `Combinations`, `Lists` (the current setup layout, from template v9 on; a school's
  own notes sheet may follow `README`). Workbooks in the older layout (a `7 Rules` sheet) read too.
  Blank or sample templates come with this skill (`templates/`) or from the setup web app.
- Python 3.10+ with `pip install ortools openpyxl reportlab` (reportlab is only for the PDFs).
- The scripts: if `scripts/ttgen/` is next to this file, use them (run from the `scripts` folder, or put it on
  `PYTHONPATH`). If they are missing, build them from **Building it without the scripts** below.

## Workflow

1. **Check the input first.** `python -m ttgen check SETUP.xlsx`. Fix or report every problem before solving:
   subjects with no periods for a level, rows with no class or teacher, unknown subjects. Also open `6 Lessons`,
   `More rules` and `4 Teachers`: text in a **Check** or **Load check** column is a problem the person must fix
   (teacher not set to teach the subject, teacher twice in a block, repeated code, over allowance).
2. **Do the capacity sums** (cheap, catches most impossible inputs):
   - each class: periods it needs (whole-class subjects + the longest group in each block it belongs to) against the
     `L` periods in its level's Day structure, remembering that lessons have fixed lengths and cannot cross a break;
   - each teacher: periods taught against allowance, and against the lesson periods of the levels they teach
     (above about 85% is usually impossible to pack);
   - each block: groups needing a special room kind at once against the number of rooms of that kind.
3. **Solve and export in one go.**
   `python -m ttgen solve SETUP.xlsx --out TIMETABLE.xlsx --time 300 --workers 8 --export OUTPUT_FOLDER`.
   A 16-18 class school usually has a first complete timetable within a minute or two and keeps improving it
   (fewer after-school lessons, fewer bent Prefer rules) for 5-15 minutes; 30+ classes with heavy banding may need
   20-30 minutes. Run long solves in the background, tell the person roughly how long it will take, and report the
   best timetable found when the time is up. Exporting a 600-student school takes about a minute more.
4. **Read the result**: the solver prints the status, the checks and notes; the workbook's `Read me` sheet and the
   HTML page's **Checks** tab list problems, after-school lessons, rules checked after solving, and notes.
5. **If no timetable is found** (INFEASIBLE, or UNKNOWN after the time limit):
   - INFEASIBLE in seconds means a hard contradiction. Find it by solving with the rules removed, then adding
     them back one at a time; and by checking teacher loads, room counts and Must rules against part-time teachers.
   - UNKNOWN means not found in time: give it more time before changing anything.
   - Tell the person exactly what blocks the timetable and the smallest change that fixes it (for example "the four
     Sec 3 CCE classes share one teacher, so 'same time across classes' cannot hold"). Never drop a Must rule or
     change their data silently; propose the change and let them decide.
6. **Deliver** (see **Outputs**) with a short summary: whether every check passed, which lessons (if any) fell into
   after-school slots and why, which Prefer rules were bent, and any notes. Give the person the Excel workbook, the
   HTML page, the four PDF books, and the zip of single PDFs; do not paste timetables into the chat.

## Outputs

`--export OUTPUT_FOLDER` (or `python -m ttgen export SETUP.xlsx TIMETABLE.xlsx --out OUTPUT_FOLDER`) writes:

| File | What it is | Who uses it |
|---|---|---|
| `<School> <Timetable> - all timetables.xlsx` | `Read me` (checks, after-school lessons, notes, linked contents), `Classes`, `Teachers`, `Rooms`, `Students` (one grid each, page break after each, landscape A4), `Lessons` (one row per group per lesson, filterable), `Teacher load` | the timetabler; anyone who wants to edit or filter |
| `<School> <Timetable> - timetable finder.html` | one offline page: search box, browse by class/teacher/room/student, **Lessons** tab with filters and CSV download, **Who's free** (teachers, rooms and classes free at a chosen time, handy for relief), **Build a timetable** (a student picks their class and groups), **Checks**, print, light/dark | everyone: share by email or the school drive |
| `PDF/Classes - all.pdf`, `Teachers - all.pdf`, `Rooms - all.pdf`, `Students - all.pdf` | one landscape A4 page each, bookmarked by level, department, room kind or class | printing |
| `<School> <Timetable> - individual PDFs.zip` | the same pages as single files: `Classes/1A.pdf`, `Teachers/<name>.pdf`, `Rooms/<room>.pdf`, `Students/<class>/<id> <name>.pdf` | sending each person their own |

Student timetables need the `Students` sheet (each student's class and group codes). Without it the Students
outputs are skipped and the HTML page's **Build a timetable** lets a student pick their groups instead; say so.
Options: `--no-individual` (books only, faster), `--no-pdf`, `--no-html`, `--no-excel`.

**A timetable made some other way** (by hand, or by your own solver) exports the same way: write a workbook with a
`Lessons` sheet in the hand-over format below and run `python -m ttgen export SETUP.xlsx THAT.xlsx --out FOLDER`.
The export re-checks everything independently (teacher, room, class and student clashes, periods placed against
periods planned, nothing in a break), so it doubles as a checker.

Hand-over format, one row per group per lesson (rows that meet at the same time in a block share a Lesson ID):
`Lesson ID, Day, Start period, End period, Periods, Starts, Ends, Level, Block, Classes, Subject, Group, Teachers, Room, After school`.
Day is exactly as on `Day structure` (e.g. `Odd Mon`); Group is the group code from `6 Lessons` or `Entire Class`;
Classes and Teachers are comma-separated; After school is `yes` or blank.

## The template, sheet by sheet

| Sheet | One row per | Key columns |
|---|---|---|
| Settings | setting | School, Timetable, (School type: primary only), Cycle (1 week, or 2 weeks Odd/Even), Period length (minutes), Period 0 starts at, Periods in a day, Lesson length (periods); then the school-wide rule rows: Same subject at most once a day (per group) Yes/No, After-school slot allowed when a class cannot fit Yes/No (No: the `A` periods are never used), Most PE classes at the same time (number), Most teaching periods a teacher has in a day (number), Every teacher gets at least one recess a day Yes/No; any other rows are notes |
| Day structure | level and day | one cell per period: `F` flag/assembly, `L` lesson, `R` recess, `U` lunch, `A` after-school slot (used only if needed), blank = no school. Day names as the school writes them (e.g. `Odd Tues`) |
| 1 Venues | room | Room, Kind (classroom, lab, pe venue, ...), Capacity, Block (building), Floor / level |
| 2 Classes | form class | Class, Level, Students, Home room |
| 3 Subjects | subject | Subject, Code, G-level (G1/G2/G3 or -; `Level tag` with Std/Fdn/Higher for primary), Department, Room kind (blank = home room), optional Lesson length, then periods per cycle for each level |
| 4 Teachers | teacher | Teacher, Short, Department, Allowance, Provisional, up to 8 pairs of Can teach / at (All, a level or a band such as Sec 1-2), Note, Role (from `Roles`), Other duties (periods); formulas show Periods given, Spare, Total load, Role guide, % of allowance, Load check |
| Roles | role | Role, What it is, Guide allowance, Group (Management, Teacher, ...); above the table, the teacher (EO) and management average loads and the even-spread margin |
| 5 Blocks | block | Block name, Level, Class 1-9 (more if needed): classes whose students are split into groups that all have lessons at the same time |
| 6 Lessons | group, or class for a whole-class subject | Level, Subject, Block (empty = whole class), Class 1-9, Teacher 1-3, Students, optional Periods / Code overrides; formulas show Group code, Periods, Doubles and Triples (or the lesson lengths in use), Room kind, Teacher periods, Check |
| Teacher availability | block-out | Teacher, Week, Day (All or Mon-Fri), From, To (clock times; every period they overlap is blocked), Reason |
| Fixed lessons | lesson at a set time (optional) | Level, Class(es) or group (a class, or a group code from 6 Lessons), Subject, Week, Day, Start period, Note |
| More rules | any other constraint | Applies to (kind), Applies to, Subject (optional), Rule, Week, Day, From/To period, Number, Must/Prefer |
| Students | student (recommended) | Student ID, Name, Level, Class, Combination, Choice 1-3, Merit, Groups (codes from 6 Lessons, comma separated), Source |
| Combinations | subject combination | Level, Code, Name, Subject 1-3, Places |

**How periods become lessons.** With lesson length L (3 for 20-minute secondary periods = 1 hour; 2 for 30-minute
primary periods), a subject with P periods gets as many L-period lessons as possible plus one or two
(L-1)-period lessons for the remainder: 20 periods at L=3 is 6 triples + 1 double; 22 is 6 triples + 2 doubles;
13 at L=2 is 6 doubles + 1 single.

**Group codes** = level digit + subject code + level-tag letter + running number (1ELP1, 5MAS2). A code typed in
"Code (only to keep an old one)" wins. Rows without a block are whole-class lessons ("Entire Class").

**Rules** come from four places, all Must unless `More rules` says Prefer: the rule rows on `Settings` (once a day
per group, at most N PE classes at once, a teacher's daily cap, a recess a day; and `Lessons end by (Monday to Thursday)` style rows,
which trim the Day structure so no lesson runs past that time on those days; `Students have no free periods` is
counted after solving, not enforced), `Teacher availability` (Not
available for a teacher, clock times turned into the periods they overlap), `Fixed lessons` (Fixed at, for a class
with a subject or for a group code) and `More rules`. Rule types (`Rule types` repeats this list):
Not available · Keep free together · Fixed at · Not in periods · Only in periods · Finish by · Max periods a day ·
Max periods in a row* · At least one recess a day* · At most N at once (a room, a subject, or a department such as PE) ·
Same time across classes · Not on the same day as · Once a day per group · Avoid after-school slots.
(* checked after solving, not enforced.) A rule row whose note starts with "example" is an example to replace.

## Building it without the scripts

Use OR-Tools CP-SAT. Read the workbook's input cells yourself; do not rely on cached formula values.

1. **Grid.** Positions are `day * periods_per_day + period`. A lesson of length n may start at p on a day if the
   level's codes at p..p+n-1 are all `L` or `A` (contiguous, no break inside). Starting positions that touch `A`
   carry a cost.
2. **Units.** Each block (rows sharing a Block name) is one unit; each row with a code but no block is a unit;
   each whole-class row gives one unit per listed class. A unit needs, for every lesson length, as many lessons as
   its longest row; a row takes part in the first k lessons of a length where k is its own count (so a group with
   more periods has extra lessons the others do not attend).
3. **Variables.** Per unit lesson: start (domain = allowed positions), fixed-size interval, day = start // periods.
4. **Students.** For every class build "kinds of student": from the Students sheet (distinct sets of group codes),
   or, without it, one per level tag found in the class's blocks (a tag's students sit the rows with that tag; in a
   block with no row of that tag they sit the longest row, unless that subject family is taken elsewhere at their
   tag). For each kind: NoOverlap over the class's whole-class lessons plus the block lessons that kind attends.
   Also NoOverlap(whole-class lessons of the class + all lessons of each block listing the class).
5. **Teachers.** NoOverlap over every lesson they take part in, plus fixed intervals for Must "Not available" and
   "Keep free together" (department).
6. **Rooms.** Per room kind, AddCumulative with capacity = number of rooms of that kind (a room's "At most N at
   once" rule counts it N times); demand = groups of that kind in the lesson; rows with no kind use classrooms.
   Room "Not available" adds fixed demand.
7. **Rules.** Remove start positions for Must "Not in / Only in periods", "Finish by", "Not available" (class,
   level, block), "Fixed at" with Day All; add a cost for Prefer versions. "Fixed at" on a day: BoolOr(start == pos).
   "Max periods a day": per day, sum of lesson length x [day == d] <= N (Prefer: plus a costed slack).
   "Same time across classes": equal starts for the matching whole-class lessons. "Not on the same day as":
   different days. "Once a day per group": AllDifferent(days) when lessons <= days (Must) or costed (Prefer);
   otherwise at most ceil(lessons / days) per day. "At most N at once" (subject): AddCumulative.
8. **Objective.** Minimise after-school periods (weighted by students affected) plus Prefer costs. Break symmetry by
   ordering identical lessons of a unit. Time limit 300 s, 8 workers.
9. **Rooms and checks.** Assign rooms greedily by start time (home room for whole-class lessons; a group keeps the
   same room where possible). Write the `Lessons` sheet in the hand-over format, then check independently: periods
   placed = planned for every row, no teacher or room double-booked, no whole-class lesson overlapping anything else
   of its class, no student (Students sheet) with two lessons at once, nothing in a break.
10. **Outputs.** Build each timetable as a list of lesson boxes (day, start, length, title, two short lines, colour by
    department) plus the level's break pattern, then draw it three ways from the same data:
    - class: whole-class lessons show subject, teacher short name, room; a block lesson shows the block name, its
      subjects and the number of groups, or "<subject> only" when just some groups meet; the legend under the grid
      lists every group with teacher and room. Teacher: subject, group or class, room. Room: subject, who, teacher.
      Student: their class's whole-class lessons plus their groups' lessons, with teacher and room.
    - PDF (reportlab): A4 landscape, one page each; days down the side (Odd/Even week bands), periods across with
      start times; shaded breaks labelled Assembly/Recess/Lunch, pale yellow after-school slots; overlapping lessons
      share the row height; legend under the grid; bookmarks per level/department/class.
    - Excel: the same grid with merged cells, one block of rows per timetable and a page break after each.
    - HTML: one file with the data embedded as JSON and plain JavaScript (no external files) for search, lists,
      grids, the lesson filter table, the free finder and the student builder.

## Lessons learned

- Total periods fitting is not enough: fixed lesson lengths waste periods at segment ends (a 5-period morning holds
  two doubles and a single at best). Check shapes when a class or teacher is near full.
- "Once a day per group" as Must plus a part-time teacher who teaches a daily subject is infeasible.
- A block with more groups needing a special room than rooms of that kind cannot run; use classrooms or add rooms.
- "Same time across classes" fails if one teacher has two of the classes.
- Teachers loaded above about 85% of their levels' lesson periods rarely fit.
- When groups in a block have different periods (Maths G1 28 vs 20), the extra lessons run for those students
  only; the rest of the class is free or in another band's short lesson. With a Students sheet, a G1 student who
  takes Mother Tongue at G3 must not clash with those extra lessons, and the solver handles it.
- Report clock times, not only period numbers: Period times gives start and end of every period.

---
name: school-timetable-generator
description: Generate a clash-free Singapore school timetable from a filled setup workbook (.xlsx) and deliver class, teacher, room and student timetables as Excel, PDF and searchable HTML.
---

# School timetable generator

Skill version: 2026-11.1 (the setup workbook's README names the version it was made for; if it names a newer one, ask for that skill).

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
  The setup web app and the timetable pages call a block a **band** (a card on step 5, Teaching groups & deployment); the workbook keeps `5 Blocks` and
  the `Block` columns. When talking to the committee, say band.
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
3. **Solve and export in one go** (when the setup has no rules "In words"; with them, solve first, add the Rule report
   sheet, then export: see **Typed rules** below).
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
   - UNKNOWN means not found in time: give it more time before changing anything. If it is still UNKNOWN after
     20-30 minutes, solve each level on its own (a copy with only that level's classes): when every level solves in
     seconds, the levels only clash through shared teachers and rooms and the single search is stalling. Use
     `--staged` (below) instead of waiting longer.
   - **Staged solve** for 30+ classes with tight days: `python -m ttgen solve SETUP.xlsx --out TIMETABLE.xlsx
     --staged --time 180 --workers 8` (`--time` is per step). It builds level by level, hardest first, keeping
     earlier levels fixed; a level that does not fit is placed with clashes against other levels allowed but
     penalised; then only the classes in the remaining clashes are re-solved until there are none; then the whole
     school is checked with every lesson kept. The committee app does this by itself for a first timetable of a
     school with 30+ classes.
   - Tell the person exactly what blocks the timetable and the smallest change that fixes it (for example "the four
     Sec 3 CCE classes share one teacher, so 'same time across classes' cannot hold"). Never drop a Must rule or
     change their data silently; propose the change and let them decide.
6. **Deliver** (see **Outputs**) with a short summary: whether every check passed, which lessons (if any) fell into
   after-school slots and why, what was compromised (teachers over their allowance, Prefer rules bent, Max periods in a
   row: the solve result lists them), any notes, and the Rule report for every typed rule. Give the person the Excel workbook, the
   HTML page, the four PDF books, the zip of single PDFs and the timetable database (.sqlite) for other systems; do not paste timetables into the chat.
   If the school runs the timetable app, tell them they can publish it there: on step 8, **Publish**, upload the .sqlite (or the timetable workbook with the setup workbook) and press **Check, then publish**.

## Outputs

`--export OUTPUT_FOLDER` (or `python -m ttgen export SETUP.xlsx TIMETABLE.xlsx --out OUTPUT_FOLDER`) writes:

| File | What it is | Who uses it |
|---|---|---|
| `<School> <Timetable> - all timetables.xlsx` | `Read me` (checks, after-school lessons, notes, linked contents), `Classes`, `Teachers`, `Rooms`, `Students` (one grid each, page break after each, landscape A4), `Lessons` (one row per group per lesson, filterable), `Teacher load` | the timetabler; anyone who wants to edit or filter |
| `<School> <Timetable> - timetable finder.html` | one offline page: search box, browse by class/teacher/room/student, **Lessons** tab with filters and CSV download, **Who's free** (teachers, rooms and classes free at a chosen time, handy for relief), **Build a timetable** (a student picks their class and groups), **Checks**, print, light/dark | everyone: share by email or the school drive |
| `PDF/Classes - all.pdf`, `Teachers - all.pdf`, `Rooms - all.pdf`, `Students - all.pdf` | one landscape A4 page each, bookmarked by level, department, room kind or class | printing |
| `<School> <Timetable> - individual PDFs.zip` | the same pages as single files: `Classes/1A.pdf`, `Teachers/<name>.pdf`, `Rooms/<room>.pdf`, `Students/<class>/<id> <name>.pdf` | sending each person their own |
| `<School> <Timetable> - timetable data.sqlite` | the timetable as a SQLite database: tables `lessons` (one row per group per lesson: day, week, start/end period and clock time, level, band, subject, group code, room, classes, teachers), `lesson_classes`, `lesson_teachers`, `classes`, `teachers`, `rooms`, `subjects`, `days`, `periods`, `day_structure`, `students` and `student_groups` (when the setup has a student list), `recess`, `rule_report` (the agent's answer per typed rule), `meta` (school, solver status, notes and the whole setup as JSON); views `class_timetable`, `teacher_timetable`, `room_timetable` | importing into another system (a school MIS, a booking or relief tool, Power BI, Excel's Power Query); rebuilding every output later from one file |

Student timetables need the `Students` sheet (each student's class and group codes). Without it the Students
outputs are skipped and the HTML page's **Build a timetable** lets a student pick their groups instead; say so.
Options: `--no-individual` (books only, faster), `--no-pdf`, `--no-html`, `--no-excel`, `--no-db`.

**A timetable made some other way** (by hand, or by your own solver) exports the same way: write a workbook with a
`Lessons` sheet in the hand-over format below and run `python -m ttgen export SETUP.xlsx THAT.xlsx --out FOLDER`.
A timetable database works in place of the workbook: `python -m ttgen export SETUP.xlsx THAT.sqlite --out FOLDER`, or
`python -m ttgen export - THAT.sqlite --out FOLDER` for one written by this exporter (it keeps the setup). A database from
another tool needs a `lessons` table with `day` (as on Day structure), `start_period`, `periods` (or `end_period`),
`subject` and `classes` (comma-separated), and ideally `group_code`, `block`, `level`, `teachers` and `room`.
The export re-checks everything independently (teacher, room, class and student clashes, periods placed against
periods planned, nothing in a break), so it doubles as a checker.

Hand-over format, one row per group per lesson (rows that meet at the same time in a block share a Lesson ID):
`Lesson ID, Day, Start period, End period, Periods, Starts, Ends, Level, Block, Classes, Subject, Group, Teachers, Room, After school, Rain room`.
Day is exactly as on `Day structure` (e.g. `Odd Mon`); Group is the group code from `6 Lessons` or `Entire Class`;
Classes and Teachers are comma-separated; After school is `yes` or blank.
When the setup has rules in words (below), the same workbook carries a `Rule report` sheet: `No., Must / Prefer, Applies to, Rule, Result, How`,
one row per typed rule in the order `python -m ttgen check` lists them; Result is `Met`, `Partly` or `Not met`, How is one sentence.
`ttgen export` copies it into the database as the `rule_report` table, and the committee app shows it on Publish.

## The template, sheet by sheet

| Sheet | One row per | Key columns |
|---|---|---|
| Settings | setting | School, Timetable, (School type: primary only), Cycle (1 week, or 2 weeks Odd/Even), Period length (minutes), Period 0 starts at, Periods in a day, Lesson length (periods); then the school-wide rule rows: Same subject at most once a day (per group) Yes/No, After-school slot allowed when a class cannot fit Yes/No (No: the `A` periods are never used), Most PE classes at the same time (number), Most teaching periods a teacher has in a day (number), Every teacher gets at least one recess a day Yes/No, In rain, PE goes to the class's home room Yes/No (Yes: while a class has a lesson in a `pe venue`, its home room stays free and is its rain room); any other rows are notes |
| Day structure | level and day | one cell per period: `F` flag/assembly, `L` lesson, `R` recess, `W` recess window (the solver puts the recess somewhere in it; the rest is lesson time), `U` lunch, `A` after-school slot (used only if needed), blank = no school. Day names as the school writes them (e.g. `Odd Tues`) |
| 1 Venues | room | Room, Kind (classroom, lab, pe venue, ...), Capacity, Block (building), Floor / level |
| 2 Classes | form class | Class, Level, Students, Home room |
| 3 Subjects | subject | Subject, Code, G-level (G1/G2/G3 or -; `Level tag` with Std/Fdn/Higher for primary), Department, Room kind (blank = home room), optional Lesson length, then periods per cycle for each level |
| 4 Teachers | teacher | Teacher, Short, Department, Allowance, Provisional, up to 8 pairs of Can teach / at (All, a level or a band such as Sec 1-2), Note, Role (from `Roles`), Other duties (periods); formulas show Periods given, Spare, Total load, Role guide, % of allowance, Load check |
| Roles | role | Role, What it is, Guide allowance, Group (Management, Teacher, ...); above the table, the teacher (EO) and management average loads and the even-spread margin |
| 5 Blocks | block | Block name, Level, Class 1-9 (more if needed): classes whose students are split into groups that all have lessons at the same time |
| 6 Lessons | group, or class for a whole-class subject | Level, Subject, Block (empty = whole class), Class 1-9, Teacher 1-3, Students, optional Periods / Code overrides; formulas show Group code, Periods, Doubles and Triples (or the lesson lengths in use), Room kind, Teacher periods, Check |
| Teacher availability | block-out | Teacher, Week, Day (All or Mon-Fri), From, To (clock times; every period they overlap is blocked), Reason |
| Fixed lessons | lesson at a set time (optional) | Level (a level, or All), Class(es) or group (a class, a group code from 6 Lessons, or `Every class`: that subject for every class of the level, or of the whole school with Level All, such as whole-school CCE; one row per slot), Subject, Week, Day, Start period, Note |
| More rules | any other constraint | Applies to (kind), Applies to, Subject (optional; for Only these subjects several, comma separated), Rule, Week, Day, From/To period, Number, Venues (for Only in venues: rooms, comma separated), Must/Prefer, In words (the sentence of a rule in words: Rule = In words) |
| Students | student (recommended) | Student ID, Name, Level, Class, Combination, Choice 1-3, Merit, Groups (codes from 6 Lessons, comma separated), Source |
| Combinations | subject combination | Level, Code, Name, Subject 1-3, Places |

A room holds one class at a time. A room that takes several classes at once (a field, a hall) needs an "At most N
at once" rule for the Room; a note on a Settings row such as "Field and Hall take 2 classes each" is read as those
rules too. Capacity is seats: a group only goes in a room that seats it (group size: the Students sheet count for its
code, else the row's Students, else the class size). Venues "For" (optional) keeps a room for some subjects,
departments or levels. 6 Lessons "Special room weeks" (Odd / Even) gives the group its special room on that week only
and a classroom on the other. The solver adds, for every set of rooms some group is limited to, a cumulative limit
over the groups limited to it; rooms are then handed out smallest-that-fits.

**How periods become lessons.** With lesson length L (3 for 20-minute secondary periods = 1 hour; 2 for 30-minute
primary periods), a subject with P periods gets as many L-period lessons as possible plus one or two
(L-1)-period lessons for the remainder: 20 periods at L=3 is 6 triples + 1 double; 22 is 6 triples + 2 doubles;
13 at L=2 is 6 doubles + 1 single.

**Group codes** = level digit + subject code + level-tag letter + running number (1ELP1, 5MAS2). A code typed in
"Code (only to keep an old one)" wins. Rows without a block are whole-class lessons ("Entire Class").
"Lesson pattern (only if different)" replaces the usual split of a row's periods, such as `5x3 + 2x2`; it must add up to the
row's periods (otherwise the usual split is used and a problem is reported).

**Rules** come from four places, all Must unless `More rules` says Prefer: the rule rows on `Settings` (once a day
per group, at most N PE classes at once, a teacher's daily cap, a recess a day; and `Lessons end by (Monday to Thursday)` style rows,
which trim the Day structure so no lesson runs past that time on those days; `Students have no free periods` is
counted after solving, not enforced; with `W` recess windows on Day structure, `Floating recess goes by` (Level: a level
has its recess together; Class: each class has its own), `Floating recess length (periods)` and `Most classes at recess at
once` (canteen space, fixed and floating recess counted)), `Teacher availability` (Not
available for a teacher, clock times turned into the periods they overlap), `Fixed lessons` (Fixed at, for a class
with a subject, a group code, or Every class of a level or the school) and `More rules`. Rule types (`Rule types` repeats this list):
Not available · Keep free together · Fixed at (a class, band, group or subject; or, with a Subject, every class of a level
or the school) · Not in periods · Only in periods · Finish by (uses the To period) · Only these subjects (an HBL day: in those
periods only lessons of the subjects named, separated by commas; a name without its G1/G2/G3 tag covers every tag, a
department code covers its subjects; blank periods = the whole day) · Only in venues (a lesson that runs into those
periods uses only the rooms under Venues: PE after 11.00 only in the hall) · Max periods a day ·
Max periods in a row* · At least one recess a day (a whole `R` recess, or the recess length inside a `W` window, of any level) · At most N at once (a room, a subject, or a department such as PE) ·
Same time across classes · Not on the same day as · Once a day per group · Avoid after-school slots.
(* checked after solving, not enforced.) A rule row whose note starts with "example" is an example to replace.
**Write rules only in this vocabulary**: a rule name from this list, an Applies to the setup has (School · Whole school
for every level, not Level · All), a real subject in Subject. A rule written any other way (a made-up rule name, a
description such as "all except English" in Subject) is skipped by the app, which then builds a different timetable from
yours. If the school has a rule these cannot say, write it in a Note, tell the committee, and say which rule you used
instead. `python -m ttgen check` lists every rule row that cannot be used as written, and fixed lessons that put one
teacher or class in two places.

### Typed rules (In words)

`More rules` rows whose Rule is **In words** are rules the committee could not say with the list: the sentence is in the
**In words** column, with Must or Prefer and what it applies to. The scripts do not enforce them; `python -m ttgen check`
lists each one as "For the agent to honour: T1 · Must · Sec 1 · No PE in the first period". You must:

- honour every **Must** (add the constraint your solver needs for it; if it cannot be met, say so before solving, never drop it silently);
- try every **Prefer** and keep it where the timetable allows;
- hand back the **Rule report** (one row per typed rule, numbered as `check` numbers them, with `Met`, `Partly` or `Not met`
  and one sentence saying how it was met or why it could not be). The report rides on the timetable workbook, and the
  database is made from that workbook, so the order matters:
  1. solve: `python -m ttgen solve SETUP.xlsx --out TIMETABLE.xlsx` (without `--export`, or export again after step 2);
  2. add a sheet named `Rule report` to `TIMETABLE.xlsx` with the columns `No., Must / Prefer, Applies to, Rule, Result, How`;
  3. `python -m ttgen export SETUP.xlsx TIMETABLE.xlsx --out OUTPUT_FOLDER`: the `.sqlite` it writes carries the report as
     its `rule_report` table, and that is the file to hand back (with `TIMETABLE.xlsx` beside it).
  A database written before the sheet was added has no report, and the committee app then says "No rule report came back".

## Building it without the scripts

Use OR-Tools CP-SAT. Read the workbook's input cells yourself; do not rely on cached formula values.

1. **Grid.** Positions are `day * periods_per_day + period`. A lesson of length n may start at p on a day if the
   level's codes at p..p+n-1 are all `L`, `W` or `A` (contiguous, no break inside). Starting positions that touch `A`
   carry a cost. Each run of `W` (a recess window) holds a floating recess: an interval of the recess length that may
   start anywhere in the window, one per level per window (Level) or one per class (Class). It joins every NoOverlap of
   its classes (step 4), so their lessons go round it; `Most classes at recess at once` is an AddCumulative over the
   floating recess intervals (demand = classes) and the fixed `R` periods (demand = classes of the level).
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
   Room "Not available" adds fixed demand. "Only in venues" (Must): where a lesson may start decides which rooms it may
   use (only the rule's rooms when it runs into the rule's periods), so give it one optional interval per set of rooms,
   exactly one present, and count it under that set. With "In rain, PE goes to the class's home room", each lesson in a `pe venue`
   also needs its class's home room (a one-room demand), so the home room is free whenever the class is at PE.
7. **Rules.** Remove start positions for Must "Not in / Only in periods", "Finish by", "Not available" (class,
   level, block), "Only these subjects" (lessons with a subject not named), "Fixed at" with Day All; add a cost for Prefer versions. "Fixed at" on a day: BoolOr(start == pos).
   "Max periods a day": per day, sum of lesson length x [day == d] <= N (Prefer: plus a costed slack).
   "Same time across classes": equal starts for the matching whole-class lessons. "Not on the same day as":
   different days. "Once a day per group": AllDifferent(days) when lessons <= days (Must) or costed (Prefer);
   otherwise at most ceil(lessons / days) per day. "At most N at once" (subject): AddCumulative.
   Rules "In words" are not in the list: honour each Must with constraints you write for it, try each Prefer, and fill the Rule report (above).
8. **Objective.** Minimise after-school periods (weighted by students affected) plus Prefer costs. Break symmetry by
   ordering identical lessons of a unit. Time limit 300 s, 8 workers.
9. **Rooms and checks.** Assign rooms greedily by start time (home room for whole-class lessons; a group keeps the
   same room where possible; a PE class's home room is reserved first as its rain room, the `Rain room` column). Write the `Lessons` sheet in the hand-over format, then check independently: periods
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

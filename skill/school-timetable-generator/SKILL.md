---
name: school-timetable-generator
description: Generate a clash-free Singapore school timetable from a filled setup workbook (.xlsx) and deliver class, teacher, room and student timetables as Excel, PDF and searchable HTML.
---

# School timetable generator

Skill version: 2026-11.12 (the setup workbook's README names the version it was made for; if it names a newer one, ask for that skill; the last number counts up, so 2026-11.12 is newer than 2026-11.9). The Lessons sheet may have more than three Teacher columns; the "Changed by hand" column there and the form-teacher columns on the Classes sheet are the app's own and need nothing from you.

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
  `Teacher-only periods`, `Fixed lessons`, `More rules`, `Rule types`, `Students`, `Combinations`, `Lists` (the current setup layout, from template v9 on; a school's
  own notes sheet may follow `README`). Workbooks in the older layout (a `7 Rules` sheet) read too.
  The setup web app and the timetable pages call a block a **band** (a card on step 5, Teaching groups & deployment); the workbook keeps `5 Blocks` and
  the `Block` columns. When talking to the committee, say band.
  Blank or sample templates come with this skill (`templates/`) or from the setup web app.
- Python 3.10+ with `pip install ortools openpyxl reportlab` (reportlab is only for the PDFs).
- The scripts: if `scripts/ttgen/` is next to this file, use them (run from the `scripts` folder, or put it on
  `PYTHONPATH`). If they are missing, build them from **Building it without the scripts** below.
  Run them with `python -B` so no `__pycache__` folder is left inside the skill, and never edit them in place: when you
  need to change the solver (rules in words), work on a copy of `scripts/`.

## Workflow

1. **Check the input first.** `python -m ttgen check SETUP.xlsx`. After the counts it lists **Critical** items, then
   **Warnings**, in the same words as step 7 of the setup app (the app and the skill run the same sums from one file,
   `ttgen/checks.py`), then the rules in words for you to honour. When anything is critical, the check ends with an error.
   - **Any critical item: stop.** Tell the person what it is and the smallest change that fixes it, and do not solve.
     Do not change the setup yourself. The one exception is a setup with a `Choices` sheet: when the check says
     `Giving way in the committee's order, nothing is critical after choice k`, it ends without an error and you solve
     as that sheet says (see **First and second choices**). `solve` still tries the first choices for one `--time`
     before it gives way: that wait is not a stall. `Even after every second choice` and `None of the second choices
     can be used` mean stop.
   - **A `[lessons]` warning that names a lesson row: tell the person and wait for their answer before solving.** It
     means that lesson will be left out (no class, an unknown subject, no periods for the level), will have no teacher
     (critical in `check-timetable`, so the app will not publish the timetable), or will not be split as typed (a
     lesson pattern that does not add up, which often means a wrong number of periods on that row).
   - **The other warnings** do not stop you (`[classes]` almost full, `[teachers]` over allowance, `[rules]` a rule row
     that cannot be used as written, `[venues]`): put every one in the summary you give at the end.
   - `The setup could not be checked: ...` and nothing after it means nothing was checked (exit code 2). Tell the
     person the message; do not take it for older scripts and do not solve.
   The **Check** and **Load check** columns on `6 Lessons`, `More rules` and `4 Teachers` flag problems inside the
   workbook (teacher twice in a block, repeated code, over allowance), but a workbook downloaded from the setup app often
   has those cells empty, because the formulas were never calculated: empty does not mean clean. Go by what the check
   prints, not by those cells. The check does not look for one of these, a group code used on two rows of `6 Lessons`:
   count the codes yourself and tell the person about any repeat.
2. **The capacity sums: the check has done these sums.** They are cheap and catch most impossible inputs, and step 1
   lists what they find as Critical items or Warnings, so do not repeat them by hand:
   - each class: periods it needs (whole-class subjects + the longest group in each block it belongs to) against the
     `L` periods in its level's Day structure, remembering that lessons have fixed lengths and cannot cross a break;
   - each teacher: periods taught against allowance, and against the lesson periods of the levels they teach
     (above about 85% is usually impossible to pack);
   - each block: groups needing a special room kind at once against the number of rooms of that kind.
   Only when the check prints no Critical or Warnings section (scripts older than 2026-11.10) do these sums yourself,
   and report every teacher over allowance by name and by how many periods.
3. **Solve and export in one go** (when the setup has no rules "In words"; with them, solve first, add the Rule report
   sheet, then export: see **Typed rules** below).
   `python -m ttgen solve SETUP.xlsx --out TIMETABLE.xlsx --time 300 --workers 8 --export OUTPUT_FOLDER`.
   A 16-18 class school usually has a first complete timetable within a minute or two and keeps improving it
   (fewer after-school lessons, fewer bent Prefer rules) for 5-15 minutes; 30+ classes with heavy banding may need
   20-30 minutes. Run long solves in the background, tell the person roughly how long it will take, and report the
   best timetable found when the time is up. Exporting a 600-student school takes about a minute more.
   These times assume about 8 cores. On 2-4 cores expect several times longer, and for 30+ classes solve each level on
   its own first (step 5) before spending time on one whole-school search.
4. **Read the result**: the solver prints the status, the checks and notes; the workbook's `Read me` sheet and the
   HTML page's **Checks** tab list problems, after-school lessons, rules checked after solving, and notes.
5. **If no timetable is found** (INFEASIBLE, or UNKNOWN after the time limit):
   - INFEASIBLE in seconds means a hard contradiction. Find it by solving with the rules removed, then adding
     them back one at a time; and by checking teacher loads, room counts and Must rules against part-time teachers.
   - UNKNOWN means not found in time. With fewer than 30 classes, give it more time before changing anything. With 30+
     classes, or when it is still UNKNOWN after 10 minutes, solve each level on its own (a copy with only that level's
     classes; about a minute each): when every level solves in seconds, the levels only clash through shared teachers
     and rooms and the single search is stalling. Use `--staged` (below) instead of waiting longer.
   - **Staged solve** for 30+ classes with tight days: `python -m ttgen solve SETUP.xlsx --out TIMETABLE.xlsx
     --staged --time 180 --workers 8` (`--time` is per step). It builds level by level, hardest first, keeping
     earlier levels fixed; a level that does not fit is placed with clashes against other levels allowed but
     penalised; then only the classes in the remaining clashes are re-solved until there are none; then the whole
     school is checked with every lesson kept. The committee app does this by itself for a first timetable of a
     school with 30+ classes.
     The order of the levels matters. A level with a group that has a lesson on nearly every day (G1 Maths split over
     three bands: ten lessons in ten days) can be shut out within seconds by the levels placed before it. When a level
     is INFEASIBLE at once with the earlier levels kept, start again with that level first, or solve it together with
     the level it shares most teachers with, before letting everything move.
     `--staged` does not carry rules in words: with them, stage your own solver in the same way (see **Typed rules**).
   - Tell the person exactly what blocks the timetable and the smallest change that fixes it (for example "the four
     Sec 3 CCE classes share one teacher, so 'same time across classes' cannot hold"). Never drop a Must rule or
     change their data silently; propose the change and let them decide.
6. **Deliver** (see **Outputs**) with a short summary: whether every check passed, which lessons (if any) fell into
   after-school slots and why, what was compromised (teachers over their allowance, Prefer rules bent, Max periods in a
   row: the solve result lists them), any notes, and the Rule report for every typed rule. Give the person the Excel workbook, the
   HTML page, the PDF books (four; three when the setup has no Students sheet), the zip of single PDFs and the timetable database (.sqlite) for other systems; do not paste timetables into the chat.
   If the school runs the timetable app, tell them they can publish it there: on step 8, **Upload and edit**, upload the .sqlite (or the timetable workbook with the setup workbook), look at what the check found, then publish on step 9, **Publish**. The app will not publish while a critical mistake remains: a lesson with no teacher, a teacher or a whole class in two lessons at once, a room holding more lessons than it takes, or a lesson in a break or outside the day. Run `python -m ttgen check-timetable` before handing back and settle these first: the lines it marks `[critical: ...]` are the ones the app will not publish with. `export` and `check-timetable` can end with exit code 1 when nothing is critical: `Teacher in two lessons (allowed that day)` lines count for both, and for `check-timetable` a Must typed rule reported `Partly` counts too. Exit code 1 is not a failure by itself; read the first line of `check-timetable` (`N warnings, M critical`), and with 0 critical the timetable can be published (`export` prints `all checks passed` or `N problems` on its first line).

## Outputs

`--export OUTPUT_FOLDER` (or `python -m ttgen export SETUP.xlsx TIMETABLE.xlsx --out OUTPUT_FOLDER`) writes:

| File | What it is | Who uses it |
|---|---|---|
| `<School> <Timetable> - all timetables.xlsx` | `Read me` (checks, after-school lessons, notes, linked contents), `Classes`, `Teachers`, `Rooms`, `Students` (one grid each, page break after each, landscape A4), `Lessons` (one row per group per lesson, filterable), `Teacher load` | the timetabler; anyone who wants to edit or filter |
| `<School> <Timetable> - timetable finder.html` | one offline page: search box, browse by class/teacher/room/student, **Lessons** tab with filters (week, day, time, level, class, department, subject, teacher, room, band) shown three ways (each class's grid with the matching lessons in colour and the rest faded, every class on one page, or a table) and CSV download, **Who's free** (teachers, rooms and classes free at a chosen time, handy for relief), **Build a timetable** (a student picks their class and groups), **Checks**, print, light/dark | everyone: share by email or the school drive |
| `PDF/Classes - all.pdf`, `Teachers - all.pdf`, `Rooms - all.pdf`, `Students - all.pdf` | one landscape A4 page each, bookmarked by level, department, room kind or class | printing |
| `<School> <Timetable> - individual PDFs.zip` | the same pages as single files: `Classes/1A.pdf`, `Teachers/<name>.pdf`, `Rooms/<room>.pdf`, `Students/<class>/<id> <name>.pdf` | sending each person their own |
| `<School> <Timetable> - timetable data.sqlite` | the timetable as a SQLite database: tables `lessons` (one row per group per lesson: day, week, start/end period and clock time, level, band, subject, group code, room, classes, teachers), `lesson_classes`, `lesson_teachers`, `classes`, `teachers`, `rooms`, `room_parts` (`venue, room`: one row per room of each combined venue), `subjects`, `days`, `periods`, `day_structure`, `students` and `student_groups` (when the setup has a student list), `recess`, `rule_report` (the agent's answer per typed rule), `choices_used` (which second choices the agent gave way on: `no, item, used, how`), `meta` (school, solver status, notes and the whole setup as JSON); views `class_timetable`, `teacher_timetable`, `room_timetable` | importing into another system (a school MIS, a booking or relief tool, Power BI, Excel's Power Query); rebuilding every output later from one file |

Student timetables need the `Students` sheet (each student's class and group codes). Without it the Students
outputs are skipped and the HTML page's **Build a timetable** lets a student pick their groups instead; say so.
Options: `--no-individual` (books only, faster), `--no-pdf`, `--no-html`, `--no-excel`, `--no-db`.
Export into a folder on a local disk. SQLite cannot write the database into some synced, mounted or network folders: it
stops with `disk I/O error` and leaves a broken `.sqlite` and a `-journal` file behind. Export locally, check the
database there, then copy the whole folder across.

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
`ttgen export` copies it into the database as the `rule_report` table, and the committee app shows it on step 8.

## The template, sheet by sheet

| Sheet | One row per | Key columns |
|---|---|---|
| Settings | setting | School, Timetable, (School type: primary only), Cycle (1 week, or 2 weeks Odd/Even), Period length (minutes), Period 0 starts at, Periods in a day, Lesson length (periods); then the school-wide rule rows: Same subject at most once a day (per group) Yes/No, After-school slot allowed when a class cannot fit Yes/No (No: the `A` periods are never used), Most PE classes at the same time (number), Most teaching periods a teacher has in a day (number), Every teacher gets at least one recess a day Yes/No, In rain, PE goes to the class's home room Yes/No (Yes: while a class has a lesson in a `pe venue`, its home room stays free and is its rain room); any other rows are notes |
| Day structure | level and day | one cell per period: `F` flag/assembly, `L` lesson, `R` recess, `W` recess window (the solver puts the recess somewhere in it; the rest is lesson time), `U` lunch, `A` after-school slot (used only if needed), blank = no school. Day names as the school writes them (e.g. `Odd Tues`) |
| 1 Venues | room | Room, Kind (classroom, lab, pe venue, ...), Capacity, Block (building), Floor / level, Equipment, Configuration (notes only: never read them as constraints), Made of (rooms used together) |
| 2 Classes | form class | Class, Level, Students, Home room |
| 3 Subjects | subject | Subject, Code, G-level (G1/G2/G3 or -; `Level tag` with Std/Fdn/Higher for primary), Department, Room kind (blank = home room), optional Lesson length, then periods per cycle for each level |
| 4 Teachers | teacher | Teacher, Short, Department, Department 2 (optional: a teacher who teaches in two departments), Allowance, Provisional, Note, Role (from `Roles`), Other duties (periods); formulas show Periods given, Spare, Total load, Role guide, % of allowance, Load check. A workbook made before 2026-11.5 has Can teach columns: ignore them. Any teacher may take any lesson the Lessons sheet gives them. |
| Roles | role | Role, What it is, Guide allowance, Group (Management, Teacher, ...); above the table, the teacher (EO) and management average loads and the even-spread margin |
| 5 Blocks | block | Block name, Level, Class 1-9 (more if needed): classes whose students are split into groups that all have lessons at the same time |
| 6 Lessons | group, or class for a whole-class subject | Level, Subject, Block (empty = whole class), Class 1-9, Teacher 1-3, Students, optional Periods / Code overrides; formulas show Group code, Periods, Doubles and Triples (or the lesson lengths in use), Room kind, Teacher periods, Check |
| Teacher availability | block-out | Teacher, Week, Day (All or Mon-Fri), From, To (clock times; every period they overlap is blocked), Reason |
| Teacher-only periods | a weekly period for teachers with no students | Name, All teachers, Departments, Teachers, Week, Days, From, To, Place. Every teacher it names is not available in the periods the times overlap, as a Must `Not available`; `ttgen` does this when it reads the setup. |
| Fixed lessons | lesson at a set time (optional) | Level (a level, or All), Class(es) or group (a class, a group code from 6 Lessons, or `Every class`: that subject for every class of the level, or of the whole school with Level All, such as whole-school CCE; one row per slot), Subject, Week, Day, Start period, Note |
| More rules | any other constraint | Applies to (kind), Applies to, Subject (optional; for Only these subjects several, comma separated), Rule, Week, Day, From/To period, Number, Venues (for Only in venues: rooms, comma separated), Must/Prefer, In words (the sentence of a rule in words: Rule = In words) |
| Students | student (recommended) | Student ID, Name, Level, Class, Combination, Choice 1-3, Merit, Groups (codes from 6 Lessons, comma separated), Source |
| Combinations | subject combination | Level, Code, Name, Subject 1-3, Places |

A room holds one class at a time. A venue whose **Made of** lists rooms (their names, comma separated) is a combined
venue: the rooms are used together, as when a folding wall joins two studios. A lesson there takes every one of its rooms,
so nothing else may be in any of them at that time, and the combined venue is free only when all its rooms are. It takes one
group at a time (no "At most N at once" above 1 on it or its rooms) and adds no room to any count. A room is in at most one
combined venue, a combined venue is not made of combined venues, and the rooms and the combined venue are all of one kind.
Seats decide who gets it: a class too big for one room fits only the combined venue, and, for a kind that has a combined venue, where no venue of the kind seats a
group it goes to the venue of that kind with the most seats (for a kind without one nothing changes: every room of the kind is allowed and the checks flag it). Room "Not available" on a room also closes the combined venue
that room is in; on the combined venue it leaves its rooms open. The timetable names one room per lesson: a lesson held in
the pair names the combined venue. A room that takes several classes at once (a field, a hall) needs an "At most N
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
which trim the Day structure so no lesson runs past that time on those days; `Teachers may take two lessons at once on` names days (as on Day structure, or a weekday for every week) of self-directed or home-based learning: on those days the check lists a teacher in two lessons as `Teacher in two lessons (allowed that day)` and not as `Teacher double-booked`, so it is not a mistake to settle, though the solver itself still never puts a teacher in two lessons; `Students have no free periods` is
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

**How to honour them.** `ttgen.solver.solve` has no place to add a constraint of your own, so either build your own solver
(see **Building it without the scripts**) or work on a copy:

- Copy `scripts/` to a working folder and change only the copy. `check`, `export` and `check-timetable` are always run
  from the unchanged scripts, and the setup workbook is never changed. In the copy's `solve()` there are three places to
  add to: right after `lesson_domains`, trim where each lesson may start (a day, a period, a fixed start); just before
  `m.Minimize`, add constraints on the lessons' start variables and intervals; add a term to `extra_cost` for each Prefer.
- Sort the rules before writing anything. A rule about where one lesson may start is a trimmed list of starts (cheap and
  exact). A rule about two lessons is a constraint. A rule about rooms is mostly a choice in the room hand-out, with at
  most one cumulative limit in the solver.
- A typed rule that the list can already say is better as a list row, because the app then enforces it too: a lesson at
  a set time is a `Fixed lessons` row, two subjects kept apart is "Not on the same day as". Honour it as typed, and tell
  the committee which rows they could move.
- **Two Musts that contradict each other** (no lessons after school, and a lesson fixed in an after-school slot): never
  choose silently. Follow the more specific rule, report the other as `Partly` with the reason in How, and put the
  contradiction at the top of your summary. When neither is more specific, ask before solving.
- **A day when teachers and rooms are not booked** (home-based learning; Settings `Teachers may take two lessons at once on`):
  that setting only changes the check, and the solver still keeps a teacher in one lesson at a time. When a rule needs
  the overlap, leave that day's lessons out of the teacher and room constraints, keep each teacher's Not available
  times, and leave Room blank for those lessons: a blank room passes every check, and an invented name such as "Online"
  would be counted as one real room. Put a small cost on each overlap so they stay few. "Max periods in a row" is still
  counted on that day, so a teacher with a lesson in every hour of it is listed.
- **Notes on a band** (`5 Blocks`) are not rules and the scripts do not read them. A note that reads as an instruction
  ("3 periods on Odd Tuesday 2.20pm") may be honoured where it breaks no rule. Say in your summary which notes you
  treated as fixed, and suggest the committee move them to `Fixed lessons`.
- Check every typed rule on the finished `Lessons` sheet with code that shares nothing with the solver, and write the
  Rule report from that check, not from what the solver was asked to do.

Before you hand back, run `python -m ttgen check-timetable <the database>`. It lists the clashes, the places the timetable differs
from the setup, the rules it breaks and the typed rules your report says are not met. Fix what it lists, or say in the notes why
it stays: the committee sees the same list in the app.

### First and second choices (Choices sheet)

The setup workbook's `Choices` sheet is a list, top to bottom, of things the committee would rather keep as they are but
will give way on if no timetable fits: a setting (a second value), a rule (make it Prefer, give a different rule
Instead, or Drop it) or a level's recess (let it float inside a window). `python -m ttgen check` lists them as "Second choice 1: ...".
The mode on the sheet decides what you make: `Fall back only when needed` is one timetable; `Make one
timetable for each` is one per step.

- `python -m ttgen solve` does this by itself: first choices, then one item at a time from the top of the list, stopping as soon
  as one fits (`--time` is per attempt). It prints " * Gave way on choice 2: ..." for each item it used and adds a `Choices used`
  sheet to the workbook. With `Make one timetable for each` it writes one workbook per step (`TIMETABLE.xlsx` for the first choices,
  `TIMETABLE - after choice 1.xlsx`, ... ) and, with `--export`, one folder each (`first choices`, `after choice 1`, ...).
- An agent with its own solver does the same: solve with the first choices; if nothing fits, give way on item 1, then items 1 and 2,
  and so on, in the order of the list, and stop at the first timetable that fits. **Never give way on anything that is not on the list.**
- Hand back the **Choices used** sheet beside the Rule report, before `ttgen export`: columns `No., Item, Used, How`, one row per
  choice on the list, numbered as `check` numbers them, Used = `First choice` or `Second choice`, How = one sentence (what was used).
  `ttgen export` copies it into the database as `choices_used`, and checks the timetable against the setup with those second
  choices applied (a floating recess is then not read as a lesson in a break). The database keeps the setup as downloaded.

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
   "Keep free together" (department). A teacher with a Department 2 counts in both departments. A `Teacher-only periods`
   row (a weekly period for named teachers with no students) is one more Must "Not available" for each teacher it names,
   in the periods its times overlap; `ttgen` adds these when it reads the setup, so they need no rule row of their own.
6. **Rooms.** Per room kind, AddCumulative with capacity = number of rooms of that kind (a room's "At most N at
   once" rule counts it N times); demand = groups of that kind in the lesson; rows with no kind use classrooms.
   For a kind that has a combined venue, count single rooms instead. Each group keeps its set E of allowed venues: the
   venues of the group's room kind that are kept for it (or for anyone) and that seat it, narrowed by any Must "Only in
   venues" rule for the lesson's periods (so a class too big for one room has only the combined venue in E). Its weight is 1 if
   E holds an ordinary room, else the fewest rooms of any combined venue in E. The single rooms under a set of venues are its
   ordinary rooms plus the rooms of its combined venues. Add a cumulative limit for the single rooms under each group's E,
   for the rooms of each combined venue, and for all single rooms of the kind. Each limit covers every group whose single
   rooms under E lie inside it, with capacity the number of single rooms in it, and demand = each group's weight (1 when no
   combined venue is in play). A combined venue never adds capacity. The count is exact only when the kind's single rooms
   are exactly one combined venue's rooms. With a third room of the kind, or two combined venues, counting each period
   does not guarantee a hand-out (a lesson keeps one room for its whole length): a timetable can meet every limit and still
   leave a group with a room marked TBC, which the check in item 9 reports.
   Room "Not available" adds fixed demand on an ordinary room. On a combined venue, take the venue out of the allowed set E
   of every lesson running into those periods instead; do not add fixed demand, which would close its rooms. "Only in venues" (Must): where a lesson may start decides which rooms it may
   use (only the rule's rooms when it runs into the rule's periods), so give it one optional interval per set of rooms,
   exactly one present, and count it under that set. With "In rain, PE goes to the class's home room", each lesson in a `pe venue`
   also needs its class's home room (a one-room demand), so the home room is free whenever the class is at PE.
7. **Rules.** Remove start positions for Must "Not in / Only in periods", "Finish by", "Not available" (class,
   level, block), "Only these subjects" (lessons with a subject not named), "Fixed at" with Day All; add a cost for Prefer versions. "Fixed at" on a day: BoolOr(start == pos).
   "Max periods a day": per day, sum of lesson length x [day == d] <= N (Prefer: plus a costed slack).
   "Same time across classes": equal starts for the matching whole-class lessons. "Not on the same day as":
   different days. "Once a day per group": AllDifferent(days) when lessons <= days (Must) or costed (Prefer);
   otherwise at most ceil(lessons / days) per day. "At most N at once" (subject): AddCumulative.
   Rules "In words" are not in the list: honour each Must with constraints you write for it, try each Prefer, and fill the Rule report (above). If the setup has a Choices sheet, solve with the first choices and give way in order (see **First and second choices**); fill `Choices used`.
8. **Objective.** Minimise after-school periods (weighted by students affected) plus Prefer costs. Break symmetry by
   ordering identical lessons of a unit. Time limit 300 s, 8 workers.
9. **Rooms and checks.** Assign rooms greedily by start time (a combined venue is free only when all its rooms are, and taking it takes every one of its rooms; smallest venue that seats the group first; home room for whole-class lessons; a group keeps the
   same room where possible; a PE class's home room is reserved first as its rain room, the `Rain room` column). Write the `Lessons` sheet in the hand-over format, then check independently: periods
   placed = planned for every row, no teacher or room double-booked (a lesson in a combined venue counts in each of its
   rooms), no whole-class lesson overlapping anything else of its class, no student (Students sheet) with two lessons at
   once, nothing in a break. Report every group with a room marked TBC; never leave TBC unreported. Where the kind has a
   combined venue and another room (item 6), a group may be left without a room: keep the combined venue's rooms for its
   subject with the Venues "For" column, so other groups do not take them, or move one of the lessons and hand rooms out again.
10. **Outputs.** Build each timetable as a list of lesson boxes (day, start, length, title, two short lines, colour by
    department) plus the level's break pattern, then draw it three ways from the same data:
    - class: whole-class lessons show subject, teacher short name, room; a block lesson shows the block name, its
      subjects and the number of groups, or "<subject> only" when just some groups meet; the legend under the grid
      lists every group with teacher and room. Teacher: subject, group or class, room. Room: subject, who, teacher.
      Student: their class's whole-class lessons plus their groups' lessons, with teacher and room.
    - PDF (reportlab): A4 landscape, one page each; days down the side (Odd/Even week bands), a clock scale across
      counted in hours above each week; each lesson with its own start and end time; striped breaks labelled
      Assembly/Recess/Lunch, drawn only when a lesson follows them that day; overlapping lessons share the row height;
      legend under the grid; bookmarks per level/department/class.
    - Excel: the same grid with merged cells, one block of rows per timetable and a page break after each.
    - HTML: one file with the data embedded as JSON and plain JavaScript (no external files) for search, lists,
      grids, the lesson filter table, the free finder and the student builder.
      In 2026-11.11 the page the app publishes also has a `staff` mode: a teacher's own timetable and the classes.
      In 2026-11.12 the setup workbook has a `Teacher-only periods` sheet: weekly periods for teachers with no students, kept out of every lesson and count.

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
- Without a Students sheet the solver protects one kind of student per G level in each class. A student who mixes
  levels (Higher MT with G2 Maths) is not protected. `side_by_side` above 0 in the solve result means two band lessons
  of one class run at the same time: find which, and keep them apart when a student could be in both.
- Keeping one-hour lessons to back-to-back starts in each stretch between breaks (its first period, then every third)
  makes the search far smaller and leaves no one-period holes. Allow other starts only on a day that has a shorter lesson.
- "No free periods" needs a meaning before solving. Count a period as free for a kind of student when it lies before a
  later lesson of theirs on that day; time after their last lesson is an early dismissal, not a free period.
- In a big school a whole-school search can find nothing in 15 minutes while every level solves alone in under a
  minute. Probe the levels early.

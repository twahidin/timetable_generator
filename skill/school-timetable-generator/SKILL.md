---
name: school-timetable-generator
description: Generate a clash-free school timetable (Singapore primary or secondary) from a filled timetable setup workbook (.xlsx) and explain anything that does not fit.
---

# School timetable generator

Turns a filled **timetable setup workbook** into a timetable: one grid per class, teacher and room, with no
teacher, room or student in two places at once. Works for Singapore primary (weekly, 30-minute periods)
and secondary (two-week Odd/Even cycle, 20-minute periods, subject-based banding) schools, and for any
school that fills the same template.

## What you need

- The filled setup workbook (`.xlsx`). Its sheets, in order: `Settings`, `Period times`, `Day structure`,
  `1 Venues`, `2 Classes`, `3 Subjects`, `4 Teachers`, `5 Blocks`, `6 Lessons`, `7 Rules`, `Rule types`, `Students`, `Lists`.
  Blank or sample templates come with this skill (`templates/`) or from the setup web app.
- Python 3.10+ with `pip install ortools openpyxl`.
- The solver: if `scripts/ttgen/` is next to this file, use it. If it is missing, build it from
  **Building the solver** below (it is about 400 lines).

## Workflow

1. **Check the input first.** Run `python -m ttgen check SETUP.xlsx` (from the `scripts` folder, or with it on
   `PYTHONPATH`). Fix or report every problem before solving: subjects with no periods for a level, rows with no
   class or teacher, unknown subjects. Also open `6 Lessons` and `7 Rules`: any text in a **Check** column is a
   problem the person must fix (teacher not set to teach the subject, teacher twice in a block, repeated code).
2. **Do the capacity sums** (cheap, catches most impossible inputs):
   - each class: periods it needs (whole-class subjects + the longest group in each block it belongs to) against the
     `L` periods in its level's Day structure, remembering that lessons have fixed lengths and cannot cross a break;
   - each teacher: periods taught against allowance, and against the lesson periods of the levels they teach
     (above about 85% is usually impossible to pack);
   - each block: groups needing a special room kind at once against the number of rooms of that kind.
3. **Solve.** `python -m ttgen solve SETUP.xlsx --out TIMETABLE.xlsx --time 300 --workers 8`.
   A 16-18 class school usually has a first complete timetable within about a minute and keeps improving it
   (fewer after-school lessons, fewer bent Prefer rules) for 5-15 minutes; 30+ classes with heavy banding may need
   20-30 minutes. Run long solves in the background, tell the person roughly how long it will take, and report the
   best timetable found when the time is up.
4. **Read the result**: the solver prints the status, the checks and notes; the workbook's `Read me` sheet lists
   problems, after-school lessons, rules checked after solving, and notes.
5. **If no timetable is found** (INFEASIBLE, or UNKNOWN after the time limit):
   - INFEASIBLE in seconds means a hard contradiction. Find it by solving with the rules removed, then adding
     them back one at a time; and by checking teacher loads, room counts and Must rules against part-time teachers.
   - UNKNOWN means not found in time: give it more time before changing anything.
   - Tell the person exactly what blocks the timetable and the smallest change that fixes it (for example "the four
     Sec 3 CCE classes share one teacher, so 'same time across classes' cannot hold"). Never drop a Must rule or
     change their data silently; propose the change and let them decide.
6. **Deliver** the timetable workbook and a short summary: whether every check passed, which lessons (if any) fell
   into after-school slots and why, which Prefer rules were bent, and any notes.

## The template, sheet by sheet

| Sheet | One row per | Key columns |
|---|---|---|
| Settings | setting | School type (primary/secondary), Weeks in cycle (1 or 2), Period length (minutes), Period 0 starts at, Periods in a day, Standard lesson length (periods) |
| Day structure | level and day | one cell per period: `F` flag/assembly, `L` lesson, `R` recess, `U` lunch, `A` after-school slot (used only if needed), blank = no school |
| 1 Venues | room | Room, Kind (classroom, lab, pe venue, ...), Capacity |
| 2 Classes | form class | Class, Level, Students, Home room |
| 3 Subjects | subject | Subject, Code, Level tag (G1/G2/G3, Std/Fdn/Higher, or -), Department, Room kind (blank = home room), Lesson length (blank = standard), then periods per cycle for each level |
| 4 Teachers | teacher | Teacher, Short, Department, Allowance, up to 8 pairs of Can teach / at (All, a level or a band such as Sec 1-2) |
| 5 Blocks | block | Block name, Level, Class 1-12: classes whose students are split into groups that all have lessons at the same time |
| 6 Lessons | group, or class for a whole-class subject | Level, Subject, Block (empty = whole class), Class 1-12, Teacher 1-3, Students, optional Periods / Code overrides; formulas show Group code, Periods, Full and Short lessons, Room kind, Check |
| 7 Rules | constraint | Applies to (kind), Applies to, Subject (optional), Rule, Week, Day, From/To period, Number, Must/Prefer |
| Students | student (optional) | Student ID, Class, Groups (codes from 6 Lessons, comma separated) |

**How periods become lessons.** With lesson length L (3 for 20-minute secondary periods = 1 hour; 2 for 30-minute
primary periods), a subject with P periods gets as many L-period lessons as possible plus one or two
(L-1)-period lessons for the remainder: 20 periods at L=3 is 6 triples + 1 double; 22 is 6 triples + 2 doubles;
13 at L=2 is 6 doubles + 1 single.

**Group codes** = level digit + subject code + level-tag letter + running number (1ELP1, 5MAS2). A code typed in
"Code (only to keep an old one)" wins. Rows without a block are whole-class lessons ("Entire Class").

**Rules** (all on `7 Rules`; `Rule types` repeats this list):
Not available · Keep free together · Fixed at · Not in periods · Only in periods · Finish by · Max periods a day ·
Max periods in a row* · At least one recess a day* · At most N at once · Same time across classes ·
Not on the same day as · Once a day per group · Avoid after-school slots. (* checked after solving, not enforced.)

## Building the solver (only if scripts/ttgen is missing)

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
9. **Output.** Assign rooms greedily by start time (home room for whole-class lessons; a group keeps the same room
   where possible). Write sheets `Read me`, `Classes`, `Teachers`, `Rooms` (days down, periods across, merged cells
   per lesson, banded cells listing the subjects with a comment naming each group, teacher and room), `Lessons`
   (one row per group lesson) and `Teacher load`. Then check independently: periods placed = planned for every row,
   no teacher or room double-booked, no whole-class lesson overlapping anything else of its class, nothing in a break.

## Lessons learned

- Total periods fitting is not enough: fixed lesson lengths waste periods at segment ends (a 5-period morning holds
  two doubles and a single at best). Check shapes when a class or teacher is near full.
- "Once a day per group" as Must plus a part-time teacher who teaches a daily subject is infeasible.
- A block with more groups needing a special room than rooms of that kind cannot run; use classrooms or add rooms.
- "Same time across classes" fails if one teacher has two of the classes.
- Teachers loaded above about 85% of their levels' lesson periods rarely fit.
- When groups in a block have different periods (Maths G1 28 vs 20), the extra lessons run for those students
  only; the rest of the class is free or in another band's short lesson.
- Report clock times, not only period numbers: Period times gives start and end of every period.

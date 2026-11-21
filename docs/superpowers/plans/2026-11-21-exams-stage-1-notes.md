# Exams and events stage 1: notes

Built 21 November 2026 on branch `exams-stage-1` (from origin/main 0008e69), subagent-driven: a builder and a reviewer
per task (eleven tasks), then a finishing task, then one fix wave from the final whole-branch review. Plan:
`2026-11-21-exams-stage-1-inside-the-committee.md`. Design: `../specs/2026-11-20-exams-and-events-design.md`.

## What stage 1 gives

- An **Exams and events** card on the front page. Only the exams committee (a list in **Exam settings**) and the
  timetable committee can open `/exams` and `/api/exams`; everyone else is refused, since the pages show student
  names, seats and access arrangements. Only the timetable committee changes the exams committee list.
- **Exam settings**: the committee list, the rooms that can be used for exams (seats, rows and columns, hall,
  access room), the backup teachers, chief invigilators, people never asked, and the rules (invigilators per
  classroom, students per hall invigilator, arrive before, stay after, duties a day).
- **A new exam or test**: name, levels (or chosen classes), dates, whole day or part of a day for each date (a part
  day stops only the periods inside the window), papers (filled from the subjects, typed, or uploaded from a paper
  list), who sits each paper (the level, that subject's groups, or a list), times, shared "together" papers, make-up
  papers and access arrangements (extra time, separate room, reader, scribe). A check says what is wrong with the
  paper times (a student with two papers at once, too many papers a day, too short a break, extra time running into
  the next paper or past the end of a part day, a paper at the very edge of a part day).
- **Make** works out, from the published timetable only: which lessons stop and which teachers are freed; which rooms
  are free then; where each student sits (by the four "How to seat" choices on the Venues and seats tab); and who
  invigilates each room (or the lesson's own teacher, for a test). **Move class to...** and **Who could take it**
  (with "Use", the cross, and "Let the app choose" for a duty chosen by hand) change one sitting by hand and make only
  that sitting again. When the exam changes after Make, the page says "The exam changed since Make: press Make
  again." and the printouts wait.
- **Printouts**: seating plans, door lists, attendance sheets, class lists, rosters by day and by teacher and the exam
  timetable as PDFs (titled with the button words, dates as "Mon 5 Oct"), and an Excel download.
- No student or teacher is told anything yet; no model, Telegram or network call anywhere in this stage.

## Rulings made during the build (each also in the ledger)

1. Task 8 writes small shells of the two exam pages so its routes answer; Task 10 replaces them in full.
2. The finishing task runs every `tests/*.py` (the plan's list omitted test_ask, test_teachers, test_venues).
3. Settings ranges: per classroom 1-10, students per hall invigilator 1-500, arrive and stay 0-120, duties a day 1-20 or none.
4. A Must rule with no strength written still blocks the teacher.
5. "Who sits" by groups keeps only students of the paper's level, so a mixed-level lesson does not pull the other
   level into the paper.
6. Seating falls through rather than leaving students out: a pin to a full room seats normally; an access student
   with no access room free is seated in the ordinary steps; a group's partial column is left empty and leftovers fill free seats.
7. A backup who has a running lesson is not offered as the backup; a hand-set name's reason is "chosen by hand";
   several lessons are joined with "; "; lesson-supervised rooms are not topped up.
8. Plan conflict: a locked duty kept its pinned names and then filled any remaining places. The browser check showed
   this was wrong for a hand-set duty; the fix wave changed it (C2 below).
9. Seats rows follow the sample (30 + 20); the plan's 60 + 20 assumed everyone of the level sits.
10. The Lessons sheet's list names are the design's own words.
11. The view body carries `counts`, `periods`, every student of the exam's levels, `levels` and `rooms_by_key`, for
    the pages and their busy reasons.
12. Count words go by number ("1 backup", "n backups"). Seats are coloured by class (the view has no student level);
    the "Move class to..." select acts at once (another move undoes it).
13. Move, invigilators and use-anyway call `make(only=key)` (a review gap, fixed); an unknown sitting answers 400
    "That sitting is not in this exam."; malformed JSON answers 400 "Check the exam and try again.", never 500.
14. A failed save of a new exam's classes is said ("classes were not saved"); the who-row class was renamed so it does
    not break the Papers table; print PDFs open inline (Excel stays a download).

## Rulings from the final review

- **Only the timetable committee changes the Exams committee list** (I10). A staff member's save keeps the stored list
  as it is; the settings page shows it read-only to staff with "Only the timetable committee can change this list."
- **The arrive and stay margins stay for common tests** (I1). A warning tells the committee when a paper starts (or
  ends) at the edge of its exam time, and a room busy only in a margin says so ("until 09:00 (invigilators arrive
  08:45)").
- **"Keep free together" Department rules are not treated as busy for invigilation**: the spec names only "Not
  available".
- **"Use" on a full duty may add a name above the number needed**: a design choice, left as it is.

## The final-review fix wave

Each item has a test on the made-up school (`tests/test_exams.py`).

- **C1 Real period times.** The published model writes period times as a 12-hour clock with no am or pm ("7.40",
  "12.40", then "1.00" for 13:00). `days.bounds` now builds the periods from the school's start time and period
  length (as `ttgen/spec.py` does) and only as a fallback reads `times` in order, adding 12 hours whenever a time is
  lower than the one before. `minutes()` stays strict for stored values. The view sends the periods as 24-hour
  HH:MM; a saved day's from/to and a paper's start are stored as 24-hour HH:MM (this also closes "per-day from/to
  are stored as typed"). The made-up school now uses the real dotted clock, so every test runs on it.
- **C2 The cross on a hand-set invigilator.** A hand-set duty keeps exactly its pinned names and shows the gap as
  "Short by 1"; it is filled only for names that left the timetable (Make counts them per duty), and the replacement
  is written back to the pin so the next Make keeps it. Sittings kept by a one-sitting Make are passed through as
  they are (not filled and thrown away). "Let the app choose" (in Who could take it, for a duty chosen by hand) posts
  `names: null`, which removes the pin and makes that sitting again.
- **C3 Common test supervision.** Only ordinary classrooms get lesson teachers; each teacher supervises one room per
  sitting (the room holding most of their stopped lesson's students, else the lesson's own room; ties go to the room
  with fewer lesson teachers so far); a teacher already used or not free for the duty time (running lesson, Must
  rule, overlapping duty, daily limit, never list) is left out; rooms left without one get the normal picks.
- **I4 Hand-picked names are checked** with the same "free then" helper as the candidates and the lesson teachers: a
  running lesson asks for a backup ("chosen by hand; teaches ...: needs a backup"); a Must rule, the never list, an
  overlapping duty or the daily limit keeps the name and shows "Not free: ...".
- **I5** Once a room gets its first student, its combined venue and the venue's other rooms are shut for that sitting
  (home-room step included).
- **I6** A one-sitting Make counts the rooms of every kept overlapping sitting (earlier and later) as taken; the
  view's `rooms_by_key` passes them as taken too, so the move selects do not offer them.
- **I1** The part-day edge warnings and the margin busy reasons (above). **M1** Students whose extra time runs past
  the end of a part day are counted in a warning. **I2** Count sentences say the number once ("60 students have").
- **I3** An exam of chosen classes with no level takes the levels of those classes, limited to those classes; Fill
  from the subjects reads those classes' lessons.
- **I7** The four "How to seat" choices (order, shared room, spacing, home rooms) are segmented buttons on the Venues
  and seats tab, saved by the normal save; the save accepts only their values.
- **I8** Make keeps a fingerprint of what it used (papers, days, levels and classes, start and end, access, seating,
  supervision, exam rooms); when it differs the view carries `stale: true`, the Schedule, Venues and Invigilators tabs
  say "The exam changed since Make: press Make again.", the print and download buttons wait, and the printouts and the
  Excel answer 409 with that sentence. A one-sitting Make on a stale exam stays stale.
- **I9** "... is no longer on the timetable." is worked out live in the summary from the pins and the made duties and
  seats (auto-picked invigilators who left are named too), plus the names the last Make dropped.
- **I11** With no students published, the checks panel and the Access arrangements tab say "The published timetable
  has no students yet: add them on the Students step and publish again to check clashes and seat students."
- **I12** Printout titles use the page's button words, dates read "Mon 5 Oct · 07:50 · Hall", and the PDF file name
  comes from the title ("Sec 3 Exam Seating plan.pdf").
- **I13** A save checks every paper field, the exam-day times, the seating values, the supervision, the kind and each
  day's levels and date; the view answers 400 with a sentence for a schedule it cannot read, never 500.
- **M2** A rain value with two rooms ("Hall, LT2") keeps both busy. **M3** A hall takes a free person from the chief
  invigilators list first. **M6** A mid-day part day reads "lessons outside 09:40–10:40" on the Schedule tab.
- The edge-cut warning has a test.

## Checked

- At the end of the build, every suite run alone one after another: `test_exams` 51, `test_relief` 37, `test_typed` 33
  (`--full` 34), `test_helper` 20 (`--full` 21), `test_fixes` 65 (`--full` 67), `test_verify` 56, `test_rules` 11,
  `test_choices` 16, `test_parents` 35, `test_sync` 18, `test_board` 58, `test_combined` 38, `test_ask` 49,
  `test_teachers` 9, `test_venues` 4, `smoke` 102 (`--full` 103), and the 15 node test files.
- After the fix wave, run one after another: `test_exams` 72, `test_relief` 37, `smoke` 102 (`--full` 103), and every
  other suite unchanged: `test_ask` 49, `test_board` 58, `test_choices` 16, `test_combined` 38, `test_fixes` 65,
  `test_helper` 20, `test_parents` 35, `test_rules` 11, `test_sync` 18, `test_teachers` 9, `test_typed` 33,
  `test_venues` 4, `test_verify` 56, the 15 node test files, and `node --check` on `app.js`, `exams.js` and
  `exams-settings.js`.
- Browser, made-up school (during the build; the fix wave's page changes were not tried in a browser): the front
  card, committee sign-in, Exam settings, a new exam with a part day, Fill from the subjects, Make, a room's seat grid,
  Move class to..., Who could take it, the Lessons tab, and the printouts drawn to PNG; phone width 375 with no
  sideways scroll.
- **The school's real timetable file (CTSS), counts only, scratch folder deleted.** 1985 lessons, 26 periods (all
  written with a dot), no student list, so 973 made-up students were made for the 25 classes of Sec 1-3 by class
  size. `bounds` reads 07:40 to 16:20, rising, 13 periods from noon on. Exam: Sec 1-3, one made-up week (Mon-Fri),
  one paper per level a day (all three at 08:00, 90 minutes), exam rooms = the 41 classroom rooms with their
  capacities, no backups.
  - Whole days: 15 papers, 744 lessons stopped over the week (156 on the first day), 33 of 41 rooms free at 08:00
    (1327 seats), 125 duties, 0 short, 0 backups, 26 rooms used, **4865 student-papers seated and 0 unseated**, 0
    overlapping duties sharing a name, checks 0 errors and 0 warnings, Make 0.45 s, the view's work 0.04 s.
  - Part days 07:40-11:00: 384 lessons stopped (83 on the first day), the same 33 free rooms, 125 duties, 0 short,
    4865 seated, 0 unseated, 5 warnings (one edge-cut warning a day), Make 0.44 s.
  - Common tests (one level, about 09:00-10:00, 30 minutes, lesson teachers): no teacher on two rooms at once. With
    the window opening with the paper, 25 rooms are busy only in the arrive margin (lessons until 09:00) and 21, 126
    and 179 students (Sec 1, 2, 3) have no seat, with the edge warning shown; with the window opened one period
    before the paper, every student is seated.
- The branch's commits hold no real staff name and not the school's full name (checked at the end of the build).

## Found in the browser check (both fixed in the fix wave)

- A hand-set invigilator removed with the cross was refilled with the same person (C2).
- Print headings showed raw dates and internal names (I12).

## Not tried in a browser

- Upload a paper list (no file tool in the pane; covered by tests).
- The Access arrangements tab and the make-up paper form.
- The staff refusal (reading staff codes was refused by the safety check; covered by tests).
- The Excel download (tests only).
- A PDF opened in a real viewer (drawn to PNG instead).
- Every page change of the fix wave: the "How to seat" buttons, "Let the app choose", the "Not free" flag, the stale
  line, the no-students sentence, the read-only committee list, the mid-day part-day words.

## Deferred minors

- Settings and files: `load()` does not range-check saved rules or rooms; no test pins the rule bounds; a saved duty is
  read with `["end"]` (KeyError on a malformed file); the read-modify-write of schedules is not locked across requests.
- Days and schedules: a lesson with p >= NP raises IndexError in `day_view` (the view now answers 400, not 500);
  `whole=false` with no from/to means the whole day; `_day_ok` is copied from the solver without a pointer comment; a
  refused save is not tested to write nothing; a "level" paper of an exam of chosen classes still seats every student
  of the level.
- Papers: three paper-list error sentences untested; a paper list's start must be "08:00" (a dotted "8.00" is refused).
- Seating: group order for alternating columns depends on the sort (sort the groups first); step 4 orders rooms by
  nominal seats, not usable space under gap spacing; a pin can put an ordinary student into an access room; untested:
  gap spacing, shared papers/blocks, order by name, numbered seats, reader/scribe, ignored pins.
- Invigilators: `day_view` computed per sitting even when not a common test; untested: max_per_day, not_own_subject.
- Make: a dead try/except in `summary`; a non-school date untested; `_exam_remake` skips the NO_STUDENTS and paper-time
  guards that Make has (a failure answers 400, nothing lost); found by the fix wave's re-review: a hand pin left for a
  sitting that no longer exists (a paper's time changed after the pin) is never cleared by Make, so if that person or
  student leaves the timetable a "no longer on the timetable" line stays on the page (`make.py:155`; one-line fix: a
  full Make passes `keys=None` to `_gone`, or drops pins whose sitting is gone).
- Routes: `exams_list` reads `c["level"]` directly; use-anyway, move and invigilators do not check the room against the
  settings' rooms; deleting an unknown id answers ok.
- Pages: a cleared number field can get its old value back on repaint; the cross deletes a paper with no confirm;
  exams-settings.html repeats about 60 lines of CSS; `homeLink()` is in two files; the "no calendar" text is hard-coded
  in exams.js; a stale note can stay in sessionStorage; unseated students cannot be moved into a room from the page;
  the use-anyway message shows even when nobody lands in the room; seat colours are by class, not level; PDF contents and
  layouts are not asserted by tests; a seat label outside the letter+number pattern is left out of the grid.

## For stage 2

- **"Real rooms are scarce" was a time-reading error, fixed in stage 1.** The build's real-data run rewrote the dots
  as colons in a scratch copy, so "1.00" (13:00) read as 01:00 and the exam time and the busy rooms came out wrong:
  3 to 6 of 41 rooms looked free and 3698 student-papers had no seat. Read from the start time and the period length,
  33 of 41 rooms are free at 08:00 and every student is seated (above). What is left is the common-test margin: a
  paper that starts with its window keeps the rooms of lessons just before busy (the warning says so).
- The real timetable has no student list, so seating real students needs them uploaded or added to the setup first.
- Telling teachers and students (the Telegram and student-page parts of the design) is stage 2 and beyond.

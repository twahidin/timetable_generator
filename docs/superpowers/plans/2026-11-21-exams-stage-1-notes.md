# Exams and events stage 1: notes

Built 21 November 2026 on branch `exams-stage-1` (from origin/main 0008e69), subagent-driven: a builder and a reviewer
per task (eleven tasks), then this finishing task. Plan: `2026-11-21-exams-stage-1-inside-the-committee.md`. Design:
`../specs/2026-11-20-exams-and-events-design.md`.

## What stage 1 gives

- An **Exams and events** card on the front page. Only the exams committee (a list in **Exam settings**) and the
  timetable committee can open `/exams` and `/api/exams`; everyone else is refused, since the pages show student
  names, seats and access arrangements.
- **Exam settings**: the committee list, the rooms that can be used for exams (seats, rows and columns, hall,
  access room), the backup teachers, chief invigilators, people never asked, and the rules (invigilators per
  classroom, students per hall invigilator, arrive before, stay after, duties a day).
- **A new exam or test**: name, levels, dates, whole day or part of a day for each date (a part day stops only the
  periods inside the window), papers (filled from the subjects, typed, or uploaded from a paper list), who sits each
  paper (the level, that subject's groups, or a list), times, shared "together" papers, make-up papers and access
  arrangements (extra time, separate room, reader, scribe). A check says what is wrong with the paper times (a
  student with two papers at once, too many papers a day, too short a break, extra time running into the next paper).
- **Make** works out, from the published timetable only: which lessons stop and which teachers are freed; which rooms
  are free then; where each student sits; and who invigilates each room (or the lesson's own teacher, for a test).
  **Move class to...** and **Who could take it** (with a "Use anyway" for a clash) change one sitting by hand and
  make only that sitting again.
- **Printouts**: seating plans, a roster by day, classes, a lessons sheet (No relief needed / Backup needed / Runs as
  usual) as PDFs, and an Excel download.
- No student or teacher is told anything yet; no model, Telegram or network call anywhere in this stage.

## Rulings made during the build (each also in the ledger)

1. Task 8 writes small shells of the two exam pages so its routes answer; Task 10 replaces them in full.
2. This task runs every `tests/*.py` (the plan's list omitted test_ask, test_teachers, test_venues).
3. Settings ranges: per classroom 1-10, students per hall invigilator 1-500, arrive and stay 0-120, duties a day 1-20 or none.
4. A Must rule with no strength written still blocks the teacher.
5. "Who sits" by groups keeps only students of the paper's level, so a mixed-level lesson does not pull the other
   level into the paper.
6. Seating falls through rather than leaving students out: a pin to a full room seats normally; an access student
   with no access room free is seated in the ordinary steps; a group's partial column is left empty and leftovers fill free seats.
7. A backup who has a running lesson is not offered as the backup; a hand-set name's reason is "chosen by hand";
   several lessons are joined with "; "; lesson-supervised rooms are not topped up.
8. Plan conflict: a locked duty keeps its pinned names that are still people and then fills any remaining places.
   The browser check showed this is wrong for a hand-set duty (see "Found in the browser check").
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

## Checked

- Every suite on the final code, run alone one after another (the quick run, then `--full`):
  `test_exams` 51 tests, `test_relief` 37, `test_typed` 33 (`--full` 34), `test_helper` 20 (`--full` 21), `test_fixes` 65
  (`--full` 67), `test_verify` 56, `test_rules` 11, `test_choices` 16, `test_parents` 35, `test_sync` 18, `test_board` 58,
  `test_combined` 38, `test_ask` 49, `test_teachers` 9, `test_venues` 4, `smoke` 102 (`--full` 103).
  Node: ask 12, board 67, choices 13, classview 18, draft 25, grid 14, groups 33, map 26, parents 46, people 31,
  split 189, subjectview 15, sync 17, teacherview 8, venueview 24. `node --check` on app.js, exams.js and
  exams-settings.js passes.
- Browser, made-up school, scratch data folder and a temporary launch entry (removed afterwards, compared equal):
  - Real click: the front page shows the card; committee sign-in; the "Exams" link opens `/exams`; Exam settings link;
    rooms added, hall seats/rows/columns typed, a room ticked as hall, a layout typed, a backup picked, Save ("Saved
    by Timetable committee").
  - Real click: New exam; name, level, dates; Make it opens the editor; a part day on Tuesday gave 07:40-09:00 and saved.
  - Real click: Papers tab, Fill from the subjects (5 papers, counts 30/40/30/20/20); times by key presses; three
    papers removed; "No problems with the paper times."
  - Real click: Schedule tab, Make gave the counters, the Sec 4 day striped "normal lessons", a teacher line per day.
  - Real click: Venues and seats, a room's seat grid; Move class to... gave "Moved 3A, 30 students, to Hall."; the hall
    has 2 invigilators (1 chief).
  - Real click: Invigilators tab, Who could take it showed four groups, one blocked by a Must rule, two under "Would
    need a backup".
  - Real click: Lessons tab, three lists with counts.
  - Printouts: the pane downloads PDFs rather than showing them, so the seating plan, roster by day and classes were
    drawn to PNG from the scratch data instead: contents correct.
  - Phone width 375: no sideways scroll on the page.
- The school's real published timetable (CTSS), counts only, scratch folder deleted. It has 1985 lessons, 25 classes
  in the three levels and **no student list**, so 1246 made-up students were seated per class size. Exam: Sec 1-3, one
  made-up week (Mon-Fri), one paper per level a day (all three at 08:00, 90 minutes), exam rooms = the 41 classroom
  rooms with their capacities, backups list empty. Results: 15 papers, 87 lessons stopped over the week (16 on the
  first day), 36 duties, 0 places short, 0 backups needed, 17 distinct rooms used, 1167 student-papers seated and 3698
  unseated (973 students sit at once each day and only 3 to 6 of the 41 rooms are free then, 88 to 185 seats), the
  summary check showed 15 errors and 4 warnings, and `make` took 0.1 seconds. **Period times in the real model are
  written "7.40", not "07:40"; the exam code refuses them** (see the first item under "For stage 2"). The run
  rewrote the dots as colons in the scratch copy only.
- The branch's commits hold no real staff name and not the school's full name: 205 teacher names and short codes
  checked, no full name matches, the school's full name 0 matches. One 6-letter short code that is
  also an ordinary English word matches 22 times as a word in code; it is the word, not a person.

## Found in the browser check

- A hand-set invigilator removed with the cross is refilled with the same person (a locked duty keeps its pins and then
  fills the rest). Wanted: a hand-set duty keeps exactly the pinned names and shows the gap as short; only names gone
  from the timetable are replaced (Review Focus 4).
- Print headings show raw dates ("2026-10-05") and internal names ("roster-day", "seating"): wanted "Mon 5 Oct - 07:50",
  "Seating plan", "Roster by day".

## Not tried in a browser

- Upload a paper list (no file tool in the pane; covered by tests).
- The Access arrangements tab and the make-up paper form.
- The staff refusal (reading staff codes was refused by the safety check; covered by tests).
- The Excel download (tests only).
- A PDF opened in a real viewer (drawn to PNG instead).

## Deferred minors

- Settings and files: `load()` does not range-check saved rules or rooms; no test pins the rule bounds; a saved duty is
  read with `["end"]` (KeyError on a malformed file); the read-modify-write of schedules is not locked across requests.
- Days and schedules: a lesson with p >= NP raises IndexError in `day_view`; `whole=false` with no from/to means the
  whole day; `_day_ok` is copied from the solver without a pointer comment; per-day from/to are stored as typed; a
  refused save is not tested to write nothing.
- Papers: edge-cut warning untested; three paper-list error sentences untested; unknown "Who sits" values read as groups.
- Seating: group order for alternating columns depends on the sort (sort the groups first); step 4 orders rooms by
  nominal seats, not usable space under gap spacing; a pin can put an ordinary student into an access room; untested:
  gap spacing, shared papers/blocks, order by name, numbered seats, reader/scribe, ignored pins.
- Invigilators: `day_view` computed per sitting even when not a common test; common-test supervision not limited to
  classrooms; untested: max_per_day, not_own_subject, duty overlap, chiefs, common-test fallback.
- Make: a dead try/except in `summary`; no tests for `taken`, the only-path duty survival or a non-school date;
  `_exam_remake` skips the NO_STUDENTS and paper-time guards that Make has (a failure answers 400, nothing lost).
- Routes: `exams_list` reads `c["level"]` directly; use-anyway, move and invigilators do not check the room against the
  settings' rooms; deleting an unknown id answers ok.
- Pages: a cleared number field can get its old value back on repaint; the cross deletes a paper with no confirm;
  exams-settings.html repeats about 60 lines of CSS; `homeLink()` is in two files; the "no calendar" text is hard-coded
  in exams.js; a stale note can stay in sessionStorage; unseated students cannot be moved into a room from the page;
  the use-anyway message shows even when nobody lands in the room; seat colours are by class, not level; PDF contents and
  layouts are not asserted by tests; a seat label outside the letter+number pattern is left out of the grid.

## For stage 2

- **Real period times.** The real published model writes period times as "7.40"; `exams.days.minutes` accepts only
  "HH:MM" and raises "7.40 is not a time." on the real school's data. Read both forms (and "07:40") wherever the model's
  `times` are read, or the exams card breaks on the school's real timetable.
- **Real rooms are scarce at the exam time.** With 20-minute periods and the arrive/stay margins, lessons in the
  neighbouring minutes keep most classrooms busy: 3 to 6 rooms of 41 were free at 08:00, so 973 students could not be
  seated. Check whether this is right (lessons of the other levels, margins) or whether rooms should count as free when
  a stopped lesson only overlaps the margin.
- The real timetable has no student list, so seating real students needs them uploaded or added to the setup first.
- Telling teachers and students (the Telegram and student-page parts of the design) is stage 2 and beyond.
- Hand-set invigilators and the print headings (above) are the two fixes the browser check asked for.

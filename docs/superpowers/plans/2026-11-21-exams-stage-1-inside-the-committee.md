# Exams stage 1: exams inside the exams committee — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The exams committee (and the timetable committee) can set up an exam or a common test, enter its papers with
their times, and get, from the published timetable, checked paper times, venues, a seat for every student, invigilators
who are free then, and the lists of lessons that stop, need backup or run, with printouts and an Excel download. Nothing
reaches the main site or relief in this stage.

**Architecture:** A new package `exams/` beside `relief/`, one file per job: `settings.py` (the exams settings JSON),
`fake.py` (the made-up published school every test uses), `days.py` (what a date of a schedule does to each lesson and
teacher), `schedules.py` (one JSON file per schedule), `papers.py` (who sits, the paper list in and out, the checks),
`seating.py` (rooms free and seats), `invigilate.py` (who is needed, who is free, the picks), `make.py` (puts them together,
hand changes, the views), `printouts.py` (PDFs and Excel). `app.py` gains the **Exams and events** card and
`/api/exams/...`; two plain-JavaScript pages, `static/exams.html` and `static/exams-settings.html`. It signs in with relief's
personal staff codes and reads relief's school calendar, both merged in PR #77.

**Tech Stack:** Python 3 / Flask (one gunicorn worker), plain JavaScript, reportlab (PDFs), openpyxl (Excel),
plain-assert test scripts.

**Spec:** `docs/superpowers/specs/2026-11-20-exams-and-events-design.md` (approved 21 Nov 2026): "Who uses it", "What it
is" up to and including "Common tests", "Printouts and downloads", "What is kept", "Stages" (stage 1). Mockups:
`docs/superpowers/specs/2026-11-20-exams-and-events-mockups.html`, tabs 1 to 7.

**Branch:** `exams-stage-1`, cut from `origin/main` at build time (main has relief stage 1 since 0008e69), with the design,
the mockups and this plan committed first.

## Global Constraints

- The repo is public: the school is only ever "CTSS"; tests, samples and docs use made-up names only.
- Never print, log or commit a real code, key, token, staff name or student name. Real data is used as counts only.
- No model, Telegram or network call anywhere in this stage.
- Tests are plain-assert scripts run as `.venv/bin/python tests/test_exams.py`, with `DATA_DIR` set to a fresh temp folder
  before `import app` (header as `tests/test_relief.py`).
- Files are written atomically with `store.write_json`; exams data lives under `os.path.join(store.DATA, "exams")`.
- Everything about teachers, classes, students, rooms and lessons is read from the **published** timetable
  (`store.published()["model"]`), never from the setup being edited. Dates become timetable days only through
  `relief.calendar.school_day(relief.settings.load(pub)["calendar"], model["days"], date)`.
- Students come only from `model["students"]` (`id, name, cls, level, groups`). There is no other student list.
- Only the exams committee (a list in the exams settings) and the timetable committee (`COMMITTEE_CODE`) may open
  anything under `/exams` or `/api/exams`; student names, seats and access arrangements go to no one else.
- Copy is plain words in the app's style. Exact texts fixed by this plan are in quotes; use them verbatim.
- Times inside `exams/` are whole minutes after midnight (`int`); stored and shown as "HH:MM".
- Builders and reviewers: NEVER run `git stash`, `git stash pop` or `git checkout -- <file>`. After each task,
  `git stash list` must show the same entries as before it.
- In `static/*.js`, never put a `//` comment in the middle of a long line; use `/* */`.
- Every commit ends with the line `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Extra time makes a clash.** A student with 25% extra time whose first paper now runs into the next paper's start must
   be reported as two papers at once. (Test in Task 4.)
2. **A part-day window whose edge cuts a lesson.** The periods inside the window stop, the periods outside run; the teacher
   is busy for the outside part and freed for the inside part; the warning counts the lesson. (Test in Task 2.)
3. **A lesson with classes of two levels, only one on the exam.** It runs in full and its teacher is not freed. (Test in
   Task 2.)
4. **A later publish drops a teacher who was pinned as an invigilator or a student who was moved by hand.** The view still
   opens; the name shows once as "no longer on the timetable"; "Make again" drops it and fills the place. (Test in Task 7.)
5. **Not enough free exam seats.** The students left over are listed as without a seat, the check is red, and nothing
   crashes. (Test in Task 5.)

---

## File structure

| File | What it is |
|---|---|
| `exams/__init__.py` | empty; marks the package |
| `exams/settings.py` | defaults, load, check, save of `DATA/exams/settings.json` |
| `exams/fake.py` | `sample_pub()` and `CAL`: the made-up published school and calendar every test uses |
| `exams/days.py` | time helpers; a schedule's dates; what one date does to every lesson and teacher |
| `exams/schedules.py` | new, check, save, load, list, delete of `DATA/exams/schedules/<id>.json` |
| `exams/papers.py` | who sits a paper, fill from subjects, paper list in and out, checks on the times |
| `exams/seating.py` | sittings, rooms free then, seats |
| `exams/invigilate.py` | how many invigilators, who is free then, the picks, duty minutes, who could take it |
| `exams/make.py` | make (seats then duties), hand changes, the day summary, the three lists of lessons |
| `exams/printouts.py` | seating plans, door lists, attendance sheets, class lists, rosters, timetables (PDF); the Excel download |
| `app.py` | the Exams and events card, the committee page link, the exams routes |
| `static/exams.html`, `static/exams.js` | the list of schedules and the schedule editor (tabs) |
| `static/exams-settings.html`, `static/exams-settings.js` | the exams settings page |
| `static/choice-exams.svg` | the card's picture (a simple line drawing like `choice-relief.svg`) |
| `tests/test_exams.py` | every test of this stage |

---

### Task 1: Exams settings and the made-up school

**Files:**
- Create: `exams/__init__.py`, `exams/settings.py`, `exams/fake.py`
- Test: `tests/test_exams.py` (create; header as `tests/test_relief.py`, plus `from exams import settings as ES, fake as F`)

**Interfaces:**
- Produces: `exams.fake.CAL` = `dict(terms=[dict(name="Term 4", start="2026-09-07", end="2026-11-20", starts_as="Odd")], holidays=[dict(start="2026-10-12", end="2026-10-12", name="School holiday")])`
  (so 2026-10-05 is "Odd Mon", 2026-10-06 "Odd Tue", 2026-10-12 not a school day).
- Produces: `exams.fake.sample_pub() -> dict`, shaped as `ttgen/export.py` `_model` builds the published model (only the
  keys exams reads), with `meta`, `codes={}`, `views={}`, and `model` holding:
  - `school=dict(name="Sample School", timetable="2027", weeks=2, period_minutes=20, start_time="07:40")`, `days=day_names(2)`,
    `NP=26`, `times=[[clock, clock], ...]` for 26 periods of 20 minutes from 07:40, `levels=["Sec 3", "Sec 4"]`.
  - `classes`: `3A` (Sec 3, home "3-01", size 30), `3B` (Sec 3, home "3-02", size 30), `4A` (Sec 4, home "4-01", size 30),
    each `dict(name, level, size, home, parents=[])`.
  - `students`: `3A-01`…`3A-30`, `3B-01`…`3B-30`, `4A-01`…`4A-30`, `dict(id, name="Student " + id, cls, level, groups)`;
    in 3A and 3B, numbers 01–10 have `groups=["3PC1"]`, 11–30 `["3CS1"]`; 4A has `groups=[]`.
  - `teachers` (and `setup.teachers` rows `dict(name, dept)`): Ms Aisha Rahman (English), Mr Ben Ong (Science),
    Ms Chloe Tan (Mathematics), Mr Daniel Koh (Mathematics), Ms Grace Yeo (English), Mr Hafiz Rahman (PE), Mr Ivan Lee (English).
  - `rooms` (`dict(name, kind, capacity, parts)`): 3-01, 3-02, 4-01 (classroom, 40); Hall (pe venue, 400); 3-11 (special
    room, 24); Lab 3-08 (lab, 40); LT1, LT2 (classroom, 40); "LT1&2" (classroom, 80, parts ["LT1", "LT2"]);
    `room_parts={"LT1&2": ["LT1", "LT2"]}`.
  - `lessons` (`dict(id, d, p, n, level, block, classes, subject, group, teachers, room, ext=False, rain="")`), periods
    0 = 07:40, 6 = 09:40, 9 = 10:40:
    0 `3A English` d0 p0 n2 [Ms Aisha Rahman] 3-01 group "Entire Class";
    1 `3B Mathematics` d0 p0 n2 [Ms Chloe Tan] 3-02 "Entire Class";
    2 `4A Mathematics` d0 p1 n2 [Mr Daniel Koh] 4-01 "Entire Class";
    3 `3A,3B Pure Chemistry` d0 p6 n3 [Mr Ben Ong] Lab 3-08 group "3PC1";
    4 `3A,3B Combined Science` d0 p6 n3 [Ms Grace Yeo] 3-01 group "3CS1";
    5 `4A PE` d0 p4 n2 [Mr Hafiz Rahman] room "Field", rain "Hall";
    6 `4A English` d0 p9 n2 [Ms Grace Yeo] 4-01;
    7 `4A Literature` d0 p3 n1 [Ms Grace Yeo] LT1;
    8 `3A,4A Assembly` d0 p12 n1 [Mr Hafiz Rahman] Hall (level "Sec 3", classes ["3A", "4A"]);
    9 `3A English` d1 p0 n2 [Mr Ivan Lee] 3-01.
  - `setup=dict(teachers=..., roles=[], rules=[dict(rule="Not available", scope="Teacher", target="Mr Ivan Lee", strength="Must", day="Mon", week="Both", **{"from": 0, "to": 5})])`.
- Produces: `exams.settings.defaults() -> dict` =
  `dict(committee=[], rooms={}, backups=[], chiefs=[], never=[], rules=dict(per_classroom=2, hall_per=40, hall_chief=True, arrive=15, stay=10, max_per_day=None, not_own_subject=False), saved_at=None, saved_by=None)`.
  `rooms` maps a venue name to `dict(seats: int, rows: int|None, cols: int|None, hall: bool, access: bool, note: str)`.
- Produces: `exams.settings.load(pub) -> dict` (defaults merged with the saved file; names not among
  `relief.people.people(pub, relief_settings.load(pub)["extra_staff"])` are dropped from the four name lists and listed in
  `missing`; rooms not in `model["rooms"]` are dropped and listed in `missing_rooms`).
- Produces: `exams.settings.save(data, pub, by: str) -> dict` (checks, writes, returns `load(pub)`), raising `ValueError`
  with one sentence: "{name} is not on the published timetable or the staff list.", "{room} is not a room of the published
  timetable.", "Give {room} a number of exam seats.", "{room}: rows times columns is less than its exam seats.",
  "Give a whole number for {label}." (labels: "invigilators per classroom", "students per hall invigilator", "arrive before",
  "stay after", "duties a day"); wrong JSON types give "Check the settings and try again."

- [ ] **Step 1: Write the failing tests** in `tests/test_exams.py`:
  - `sample_school_is_consistent`: `sample_pub()["model"]` has 90 students, 10 lessons, 9 rooms;
    `relief.calendar.school_day(F.CAL, model["days"], date(2026,10,5)) == "Odd Mon"`, `date(2026,10,12)` → None.
  - `settings_defaults_and_round_trip`: `load(pub)` equals defaults plus empty `missing` and `missing_rooms`; saving
    `committee=["Ms Grace Yeo"]`, `rooms={"Hall": dict(seats=240, rows=24, cols=10, hall=True, access=False, note="")}`,
    `backups=["Mr Ivan Lee"]` then `load` returns them, with `saved_by` the given name.
  - `settings_refuse_bad_values`: an unknown name, an unknown room, a room with 0 seats, rows × cols below seats, and
    `per_classroom="two"` each raise `ValueError` with the exact sentence above.
  - `settings_drop_people_no_longer_there`: write a file naming "Mr Gone Away" in `backups`; `load` drops him and
    `missing == ["Mr Gone Away"]`.
- [ ] **Step 2: Run** `.venv/bin/python tests/test_exams.py` — expect an import error.
- [ ] **Step 3: Implement** `exams/__init__.py`, `exams/fake.py`, `exams/settings.py` as in Interfaces (settings under
  `os.path.join(store.DATA, "exams", "settings.json")`, a lock around save, as `relief/settings.py`).
- [ ] **Step 4: Run** the tests — all pass.
- [ ] **Step 5: Commit** `git add exams tests/test_exams.py && git commit -m "Exams: settings and the made-up school"`

---

### Task 2: What a date of a schedule does to lessons and teachers

**Files:**
- Create: `exams/days.py`
- Test: `tests/test_exams.py`

**Interfaces:**
- Produces: `minutes(t: str) -> int` ("07:40" → 460, refuses anything not HH:MM with `ValueError("{t} is not a time.")`),
  `hhmm(m: int) -> str`.
- Produces: `bounds(model) -> list[tuple[int, int]]`: each period's (start, end) minutes from `model["times"]`.
- Produces: `dates(sched, cal, model) -> list[dict]`: one per calendar date from `sched["start"]` to `sched["end"]`:
  `dict(date="YYYY-MM-DD", day: str | None, levels: list[str], start: int, end: int)`; `day` None when `school_day` is None;
  `levels` = `sched["days"][date]["levels"]` (default: the schedule's levels); window = the whole school day
  (`bounds[0][0]`, `bounds[-1][1]`) when `sched["days"][date]["whole"]` is true, else
  `minutes(from)`, `minutes(to)`.
- Produces: `day_view(pub, cal, sched, date: str) -> dict`:
  `dict(date, day, window={class: (start, end)}, lessons=[row, ...], blocked={teacher: [(start, end)]})` where `window`
  holds every class on the schedule that date (classes of `levels`; when `sched["classes"]` is non-empty, only those of
  them), and each `row` is
  `dict(row: int (index in model["lessons"]), classes, teachers, subject, level, room, rain, start, end, stopped: [(s, e)], running: [(s, e)])`
  for every lesson of that day name. On a date outside `sched["start"]`..`sched["end"]`, `window` is empty (a make-up
  paper's date). A period of a lesson is **stopped** when every class of the lesson is in `window`
  and the period lies inside that class's window; otherwise it is **running**. Adjacent periods merge into one span.
  `blocked` holds Must "Not available" teacher rules of `model["setup"]["rules"]` that match the day (week "Both" or the
  day's week part; day "All" or the same first three letters of the weekday, as `ttgen/solver.py` `_day_ok`), periods
  `from`..`to` inclusive (defaults 0 and NP-1), as minute spans. On a date whose `day` is None, `lessons == []`.
- Produces: `edge_cuts(view) -> int`: lessons with both stopped and running spans.

- [ ] **Step 1: Write the failing tests** (a helper `sched(**kw)` builds `dict(levels=["Sec 3"], classes=[], start="2026-10-05", end="2026-10-06", days={})` updated by `kw`):
  - `times_round_trip`: `minutes("07:40") == 460`, `hhmm(460) == "07:40"`, `minutes("7.40")` raises "7.40 is not a time.".
  - `whole_day_stops_every_sec3_lesson`: with `days={"2026-10-05": dict(levels=["Sec 3"], whole=True)}`, rows 0, 1, 3, 4
    are all stopped, rows 2, 5, 6, 7 all running.
  - `part_day_edge_shortens_a_lesson` (Review Focus 2): `whole=False, from="07:40", to="09:00"`, and lesson 0 changed to
    n=8 (07:40–10:20) in a copy of the sample: row 0 has `stopped == [(460, 540)]` and `running == [(540, 620)]`;
    `edge_cuts(view) == 1`.
  - `mixed_level_lesson_runs` (Review Focus 3): with Sec 3 whole day, row 8 (3A with 4A) is all running.
  - `chosen_classes_only`: `classes=["3A"]`, Sec 3 whole day: row 0 stopped, row 1 (3B) running.
  - `not_a_school_day_has_no_lessons`: `dates` for start/end 2026-10-12 gives one entry with `day is None`; its
    `day_view` has `lessons == []`.
  - `must_rule_blocks_on_mondays`: `day_view(...)["blocked"]["Mr Ivan Lee"] == [(460, 580)]` on 2026-10-05 and no entry on
    2026-10-06.
- [ ] **Step 2: Run** the tests — expect an import error.
- [ ] **Step 3: Implement** `exams/days.py` as in Interfaces.
- [ ] **Step 4: Run** the tests — all pass.
- [ ] **Step 5: Commit** `git add exams/days.py tests/test_exams.py && git commit -m "Exams: what a date does to lessons and teachers"`

---

### Task 3: Schedules: make, check, save, list

**Files:**
- Create: `exams/schedules.py`
- Test: `tests/test_exams.py`

**Interfaces:**
- Produces: the schedule dict, stored as `DATA/exams/schedules/<id>.json`:
  `dict(id, kind: "exam" | "test", name, levels: [str], classes: [str], start, end, days: {date: dict(levels, whole, from, to)},
  times=dict(report="07:30", min_break=20, max_papers=2), papers: [paper], access: [aa],
  seating=dict(order="class", shared="levels", spacing="every", home_rooms=True), supervision="invigilators",
  pins=dict(rooms={}, duties={}), use_anyway=[], made=None, status="draft", created_at, created_by, saved_at, saved_by)`.
  A `paper` is `dict(id, level, subject, paper, minutes: int, date: str | None, start: str | None, who: "level" | "groups" | "students", students: [id], together: str)`.
  An `aa` (access arrangement) is `dict(student, extra: int (percent), own_room: bool, reader: bool, scribe: bool, note)`.
  A new common test (`kind="test"`) has `seating.home_rooms=True` and `supervision="lesson"`.
- Produces: `new(kind, name, levels, start, end, by) -> dict` (id `secrets.token_hex(4)`; `access` copied from the most
  recently created schedule that has any, keeping only students still in `model["students"]`).
- Produces: `save(sched, pub, cal, by) -> dict` (checks then writes, returns the saved dict); `load(id) -> dict | None`;
  `listing() -> list[dict(id, kind, name, levels, start, end, papers: int, status, saved_at)]` newest first;
  `delete(id)`.
- Check sentences (`ValueError`): "Give the exam a name.", "Pick at least one level or class.", "Check the dates: the last
  day is before the first.", "An exam can cover at most 31 days.", "{time} is not the start of a period.", "{time} is not
  the end of a period.", "On {date} the end is before the start.", "{level} is not a level of the published timetable.",
  "{class} is not a class of the published timetable.", "Give {paper} a length in minutes.", "Extra time for {student}
  must be 0 to 100 percent.", "{student} is not on the published timetable."; wrong JSON types: "Check the exam and try
  again." (`{paper}` is the paper's name as `papers.label(paper)` gives it, Task 4; here the plain `level subject paper`.)
- Produces: `NO_CALENDAR = "Set the school calendar in Relief settings first: exams need it to know which timetable day a date is."`
  (used by the routes when `cal["terms"]` is empty).

- [ ] **Step 1: Write the failing tests**:
  - `new_exam_has_the_defaults`: `new("exam", "Sec 3 End-of-Year Exam", ["Sec 3"], "2026-10-05", "2026-10-06", "Ms Grace Yeo")`
    has `supervision == "invigilators"`, `seating["home_rooms"] is True`, `status == "draft"`; `new("test", ...)` has
    `supervision == "lesson"`.
  - `save_load_list_delete`: save, `load(id)` equals it, `listing()[0]["name"]` is the name, `delete` removes it.
  - `save_refuses_bad_input`: an empty name, no levels, end before start, a span of 32 days, a window "07:50" (not a period
    start), "10:30" as an end, end before start on a day, level "Sec 9", class "9Z", a paper with `minutes=0`, `extra=150`,
    and student "ZZ-99" each raise the exact sentence.
  - `access_arrangements_carry_forward`: a saved schedule with `access=[dict(student="3A-05", extra=25, ...), dict(student="ZZ-99", ...)]`
    written directly to disk (bypassing the check), then `new(...)` copies only the 3A-05 entry.
- [ ] **Step 2: Run** the tests — expect an import error.
- [ ] **Step 3: Implement** `exams/schedules.py` as in Interfaces (lock around writes; `listing` reads every file, skipping
  any that fails to load).
- [ ] **Step 4: Run** the tests — all pass.
- [ ] **Step 5: Commit** `git add exams/schedules.py tests/test_exams.py && git commit -m "Exams: schedules"`

---

### Task 4: Papers: who sits, the paper list, the checks

**Files:**
- Create: `exams/papers.py`
- Test: `tests/test_exams.py`

**Interfaces:**
- Produces: `label(paper) -> str` = `f"{level} {subject} {paper}"` with the paper part left out when empty.
- Produces: `who_sits(paper, model) -> list[str]` (student ids, sorted): `who="level"` → students whose `level` (or whose
  class's level) is the paper's level; `"groups"` → students of the published lessons of that level and subject: all
  students of the lesson's classes when its `group` is "Entire Class", else students whose `groups` include the lesson's
  `group`; `"students"` → `paper["students"]` that are still in the model.
- Produces: `fill_from_subjects(sched, model) -> list[paper]`: one paper per (level, subject) of the published lessons of
  the schedule's levels, sorted by level then subject, `paper="Paper 1"`, `minutes=60`, `date=None`, `start=None`,
  `who="groups"`, `together=""`; papers already in the schedule with the same level and subject are not added again.
- Produces: `read_paper_list(data: bytes) -> list[paper]` from the first sheet, header row exactly
  `Level | Subject | Paper | Minutes | Date | Start | Who sits | Sits with` ("Who sits": "All" → `"level"`, blank or
  "Groups" → `"groups"`; "Date" a date cell or "YYYY-MM-DD"; "Start" a time cell or "HH:MM"); errors raise `ValueError`
  "Row {n}: {what}." with what one of "give a level and a subject", "the minutes must be a whole number",
  "the date is not a date", "the start is not a time", or "The first row must be: Level, Subject, Paper, Minutes, Date,
  Start, Who sits, Sits with." Students-only papers are not in the sheet.
- Produces: `paper_list_xlsx(sched) -> bytes` (same columns; doubles as the template).
- Produces: `ends(paper, sid, access_by_sid) -> int`: start plus minutes plus the student's extra time, rounded up to a
  whole minute.
- Produces: `check(sched, model, cal) -> dict(errors: [str], warnings: [str])`, using `days.dates`:
  - errors: "{label} needs a date and a start time."; "{label} is on {date}, which is not a school day." (from
    `school_day` itself, so a make-up paper may fall after the exam's last day); for `who` "level" or "groups" only:
    "{label} is on {date}, which is not one of {level}'s exam days." and
    "{label} runs outside {level}'s exam time on {date} ({from}–{to}).";
    "{label} and {label} share “{together}” but start at different times.";
    "{n} student(s) have {label} and {label} at the same time on {date}." (intervals overlap, extra time included);
  - warnings: "{n} student(s) have {k} papers on {date}." (k above `sched["times"]["max_papers"]`);
    "{n} student(s) have less than {min_break} minutes between {label} and {label} on {date}.";
    "On {date} the exam time ends in the middle of {n} lesson(s)." (`days.edge_cuts`, when n > 0).
  "{n} student(s) have" is written "1 student has" or "{n} students have", and "lesson(s)" "lesson"/"lessons", by the count.

- [ ] **Step 1: Write the failing tests**:
  - `who_sits_by_level_groups_and_list`: Sec 3 English `who="level"` → 60 ids; Sec 3 Pure Chemistry `who="groups"` → 20
    ids (3A-01..10, 3B-01..10); Sec 3 English `who="groups"` → the 30 of 3A (lesson 9 and lesson 0 are 3A only);
    `who="students", students=["3B-04", "ZZ-99"]` → ["3B-04"].
  - `fill_from_subjects_once`: for Sec 3 gives Assembly, Combined Science, English, Mathematics, Pure Chemistry (5); run
    again on the result adds none.
  - `paper_list_round_trip`: `read_paper_list(paper_list_xlsx(s))` gives the same papers (ids aside); a sheet with a bad
    header raises the header sentence; a row with minutes "abc" raises "Row 2: the minutes must be a whole number.".
  - `check_finds_missing_times_and_non_school_days`: a paper with no start, and one dated 2026-10-12, give the two errors;
    a Sec 3 paper on 2026-10-07 (a school day after the exam) gives "… is not one of Sec 3's exam days.", while a
    make-up paper (`who="students"`) that day gives no error.
  - `extra_time_makes_a_clash` (Review Focus 1): Sec 3 whole day on 2026-10-05; Sec 3 Pure Chemistry (`who="groups"`)
    07:50 for 60 minutes and Sec 3 English (`who="level"`) 08:55: no clash error (a less-than-20-minutes warning); with `access=[dict(student="3A-02", extra=25, ...)]` the error is "1 student has Sec 3 Pure
    Chemistry Paper 1 and Sec 3 English Paper 1 at the same time on 2026-10-05." (labels as `label` makes them).
  - `check_window_and_together`: on a part day 07:40–09:00, a Sec 3 paper at 08:30 for 60 minutes gives the "runs outside"
    error; two papers with `together="MT2"` at different starts give the share error.
- [ ] **Step 2: Run** the tests — expect failures.
- [ ] **Step 3: Implement** `exams/papers.py` as in Interfaces.
- [ ] **Step 4: Run** the tests — all pass.
- [ ] **Step 5: Commit** `git add exams/papers.py tests/test_exams.py && git commit -m "Exams: papers, who sits, the checks"`

---

### Task 5: Sittings, rooms free then, seats

**Files:**
- Create: `exams/seating.py`
- Test: `tests/test_exams.py`

**Interfaces:**
- Consumes: `days.day_view`, `papers.who_sits`, `papers.ends`, `exams.settings.load`.
- Produces: `sittings(sched) -> list[dict(key, date, start: int, papers: [paper id])]`: papers with a date and start
  grouped by (date, start), `key = f"{date} {start HH:MM}"`, in time order.
- Produces: `sitting_students(sitting, sched, model) -> dict(sid -> dict(papers: [id], level, cls, end: int, aa: aa | None))`.
- Produces: `rooms_free(pub, cal, sched, sitting, xset, taken: set[str]) -> list[dict(name, seats, rows, cols, hall, access, busy: str)]`:
  every room of `xset["rooms"]`, `busy` "" when free, else the reason: "{subject} with {classes} until {HH:MM}" (a running
  lesson span overlapping [start − arrive, last end + stay]), "rain room for {subject} with {classes}" (a running lesson's
  `rain` names it; free when `[sitting key, room]` is in `sched["use_anyway"]`), "used by another sitting" (in `taken`).
  A combined venue is busy when any of its parts is, and a part when its combined venue is.
- Produces: `seat(sitting, students, rooms, sched, model, pins: dict[sid, room]) -> dict(rooms: {room: [[sid, seat]]}, unseated: [sid])`:
  1. pinned students go to their pinned room first (dropped silently when the student or room is gone);
  2. students with an `aa` whose `own_room` is true, or who have a reader or scribe, go to the free rooms marked `access`,
     in name order; rooms marked `access` take no one else;
  3. when `home_rooms`: each class whose sitting students all fit go to the class's home room when it is free and its exam
     seats hold them;
  4. the rest, as classes in (level, class) order, fill the remaining free rooms largest exam seats first, each class whole
     where it fits in the room's space left, else into the next room, a class split only when no room can hold it whole;
  5. inside a room, students in `order` ("class": class then id; "name": name), seats from the room's layout: with rows
     and cols, seat names are column letter + row number ("A1", "A2", … down each column, then "B1"…), and when two or more
     levels (`shared="levels"`) or papers (`"papers"`) share the room, columns go to the groups in turn (A to the first, B to
     the second, …), a group that runs out leaving its columns to the others; `"blocks"` fills group after group;
     `spacing="gap"` uses only columns A, C, E…; without a layout seats are "1", "2", ….
  6. anyone left is `unseated`.

- [ ] **Step 1: Write the failing tests** (settings with rooms 3-01, 3-02, 4-01 at 40 seats, 6 rows × 7 cols; Hall 240,
  24 × 10, hall; 3-11 24, 4 × 6, access; LT1&2 80; LT1 and LT2 40):
  - `sittings_group_by_start`: two papers at 2026-10-05 07:50 and one at 10:00 give two sittings, keys
    "2026-10-05 07:50" and "2026-10-05 10:00".
  - `rooms_busy_with_running_lessons`: Sec 3 whole day on 2026-10-05, sitting 07:50 (60 min): 4-01 busy "Mathematics with
    4A until 08:40", LT1 busy, LT1&2 busy, 3-01 free; a sitting at 09:00 gives Hall "rain room for PE with 4A", and with
    `use_anyway=[["2026-10-05 09:00", "Hall"]]` the Hall is free.
  - `own_class_in_own_room`: Sec 3 English for all of Sec 3 at 07:50: 3A in 3-01 seats A1…, 3B in 3-02, nobody unseated.
  - `access_students_apart`: 3A-05 with `own_room=True, extra=25` sits in 3-11 seat "A1"; 3-01 holds the other 29.
  - `shared_hall_alternates_levels`: with `home_rooms=False` and Sec 3 and Sec 4 papers in one sitting, the Hall's column A
    holds Sec 3 students and column B Sec 4.
  - `not_enough_seats` (Review Focus 5): only room 3-01 (40 seats) set up, 60 Sec 3 students: 3A and 10 of 3B seated,
    20 of 3B in `unseated`, no exception.
  - `pins_win`: `pins={"3A-07": "3-02"}` puts 3A-07 in 3-02.
- [ ] **Step 2: Run** the tests — expect failures.
- [ ] **Step 3: Implement** `exams/seating.py` as in Interfaces.
- [ ] **Step 4: Run** the tests — all pass.
- [ ] **Step 5: Commit** `git add exams/seating.py tests/test_exams.py && git commit -m "Exams: rooms free then and seats"`

---

### Task 6: Invigilators

**Files:**
- Create: `exams/invigilate.py`
- Test: `tests/test_exams.py`

**Interfaces:**
- Consumes: `days.day_view`, the seats from Task 5, `exams.settings.load`.
- Produces: a **duty** `dict(key (sitting key), room, date, start: int, end: int, need: int, names: [str], chief: str | None, reasons: {name: str}, backup: {name: [row]}, short: int, locked: bool)`;
  `start` = sitting start − `arrive`, `end` = the room's last student end + `stay`.
- Produces: `need(room, n, aa_rows, xrules) -> int`: hall → ceil(n / `hall_per`) + (1 if `hall_chief`); access room → 1 plus
  one per student with a reader or scribe; any other room → `per_classroom`; 0 when n is 0.
- Produces: `candidates(pub, cal, sched, xset, date, start, end, duties, subjects=(), exclude=()) -> dict(freed: [c], free: [c], backups: [c], need_backup: [c])`,
  each `c = dict(name, minutes: int, reason: str, rows: [row])`, built from relief's people with `teaches` true plus the
  backups list: **free then** = no running span and no `blocked` span overlapping [start, end), no other duty in `duties`
  overlapping, not on `never`, not in `exclude`, not at `max_per_day` duties that date, not (when `not_own_subject`)
  teaching one of `subjects` (the sitting's papers) in the published lessons; a backup invigilator is never in **freed** or
  **free**, only in **backups**; absences arrive with relief stage 2, so this stage reads none; **freed** = free then with a stopped span overlapping, reason "freed: {classes} on the exam then";
  **free** = the other free then (not backups), reason "free then"; **backups** = backup invigilators free then, reason
  "backup invigilator"; **need_backup** = teachers whose only obstacle is running lessons, reason
  "teaches {classes} {subject} {HH:MM}–{HH:MM}: needs a backup", `rows` the lesson rows. Each group sorted by `minutes`
  (duty minutes this schedule, then minutes in other saved schedules of the same calendar year), then name.
- Produces: `assign(pub, cal, sched, xset, seats_by_key) -> list[duty]`: duties in (date, start, room) order; locked duties
  (`sched["pins"]["duties"]["{key}|{room}"]`) keep their names (names no longer among the people are dropped); otherwise
  fill `need` from freed, then free, then backups, then need_backup (with `backup` filled), counting each pick's minutes
  as it goes; `short` = places left empty; the chief of a hall is the first name on the `chiefs` list among the picks, else
  the first pick. Under `supervision="lesson"` (a common test), a classroom's duty is the teachers of the class's stopped
  lesson rows overlapping the sitting start (reason "supervises their own lesson"), and only rooms with no such teacher are
  filled as above.
- Produces: `duty_minutes(duties) -> {name: minutes}`.

- [ ] **Step 1: Write the failing tests** (Sec 3 whole day 2026-10-05; Sec 3 English 07:50 for 60 min; rooms as Task 5;
  `backups=["Mr Ivan Lee"]`):
  - `need_per_room`: classroom 30 → 2; hall 100 with chief → 4; access room with one reader → 2.
  - `freed_teachers_first`: the duty of 3-01 (07:35–09:00) gets Ms Aisha Rahman and Ms Chloe Tan (both freed), reasons
    "freed: 3A on the exam then" and "freed: 3B on the exam then".
  - `busy_teacher_needs_a_backup`: with only Mr Daniel Koh and Mr Ivan Lee left as people (others on `never`), Mr Ivan
    Lee is blocked (Must rule, Monday 07:40–09:40), so the duty takes Mr Daniel Koh with `backup == {"Mr Daniel Koh": [2]}`
    and `short == 1`.
  - `backups_kept_for_later`: Sec 3 whole day on 2026-10-06 (Odd Tue, where only lesson 9 runs), Sec 3 English 07:50 for
    60 min for all of Sec 3: the four places of 3-01 and 3-02 go to four of the six teachers with no lessons that day;
    Mr Ivan Lee is not picked, though his 3A lesson stops; `candidates(...)` for the 3-01 duty (its own duty left out of
    `duties`) has `backups[0]["name"] == "Mr Ivan Lee"` and no Mr Ivan Lee in `freed`.
  - `common_test_supervised_by_lesson_teacher`: `kind="test"`, `supervision="lesson"`, a Sec 3 Mathematics test at 07:50
    for 30 min in home rooms: 3-02's duty is ["Ms Chloe Tan"], reason "supervises their own lesson".
  - `locked_names_kept`: `pins.duties={"2026-10-05 07:50|3-01": ["Ms Grace Yeo", "Mr Gone Away"]}` gives names
    ["Ms Grace Yeo"] and `locked is True`.
- [ ] **Step 2: Run** the tests — expect failures.
- [ ] **Step 3: Implement** `exams/invigilate.py` as in Interfaces.
- [ ] **Step 4: Run** the tests — all pass.
- [ ] **Step 5: Commit** `git add exams/invigilate.py tests/test_exams.py && git commit -m "Exams: invigilators"`

---

### Task 7: Make, hand changes and the views

**Files:**
- Create: `exams/make.py`
- Test: `tests/test_exams.py`

**Interfaces:**
- Consumes: Tasks 2 to 6.
- Produces: `make(pub, cal, sched, xset, only: str | None = None) -> dict`: fills `sched["made"] = dict(seats={key: {room: [[sid, seat]]}}, unseated={key: [sid]}, duties=[duty], gone=[str], made_at)`
  sitting by sitting in time order (rooms taken by an overlapping earlier sitting are passed as `taken`), seats then duties;
  `only` remakes one sitting and keeps the rest; pinned students or invigilators no longer in the model go in `gone` as
  "{name} is no longer on the timetable." (each once) and are dropped. Returns the schedule (the caller saves it).
- Produces: `move(sched, key, sids: [str], room) -> None` (adds `pins.rooms[key][sid] = room`), and
  `set_invigilators(sched, key, room, names: [str]) -> None` (sets `pins.duties["{key}|{room}"]`); the route calls
  `make(..., only=key)` after either.
- Produces: `summary(pub, cal, sched, xset) -> dict(days=[dict(date, day, levels, whole, window: [HH:MM, HH:MM], papers: {level: [dict(label, start, end)]}, freed: int, on_duty: int, teaching: int, backups: int)], counts=dict(papers, with_time, two_a_day, duties, backups, short, unseated), checks=papers.check(...), gone=[...])`.
  `freed` counts teachers with any stopped span that day, `teaching` teachers with any running span, `on_duty` teachers
  with a duty, `backups` duty places with a `backup` entry.
- Produces: `lesson_lists(pub, cal, sched) -> dict(none=[item], backup=[item], runs=[item])`, `item = dict(date, start: HH:MM, end: HH:MM, classes, subject, teachers, room, note)`:
  **none** = stopped spans (note "shortened" when the lesson also has running spans); **backup** = running spans of a
  teacher with an overlapping duty (note "{teacher} is invigilating {room}"); **runs** = every other running span.
  Spans on dates that are not school days are left out.

- [ ] **Step 1: Write the failing tests** (the sample with Sec 3 whole day on 2026-10-05, papers Sec 3 English 07:50
  60 min and Sec 3 Pure Chemistry 10:00 60 min; settings as Task 5):
  - `make_seats_and_duties`: after `make`, `made.unseated` is empty for both sittings, every duty has `short == 0`, and no
    teacher has two duties whose times overlap.
  - `move_keeps_hand_changes`: `move(s, "2026-10-05 07:50", ["3A-07"], "3-02")` then `make(..., only=...)` puts 3A-07 in
    3-02; a full `make` again still does.
  - `gone_people_are_named_once` (Review Focus 4): pin "Mr Gone Away" on a duty and move "ZZ-99"; `make` gives
    `sorted(gone) == ["Mr Gone Away is no longer on the timetable.", "ZZ-99 is no longer on the timetable."]` and the duty
    is filled from the candidates.
  - `summary_counts`: day 2026-10-05 has `freed >= 4`, `papers["Sec 3"]` with two entries, `counts["papers"] == 2`.
  - `lesson_lists_three_ways`: rows 0, 1, 3, 4 appear in `none`; row 2 (4A Mathematics with Mr Daniel Koh) appears in
    `backup` when Mr Daniel Koh is pinned on the 07:50 duty, else in `runs`.
- [ ] **Step 2: Run** the tests — expect failures.
- [ ] **Step 3: Implement** `exams/make.py` as in Interfaces.
- [ ] **Step 4: Run** the tests — all pass.
- [ ] **Step 5: Commit** `git add exams/make.py tests/test_exams.py && git commit -m "Exams: make, hand changes, the views"`

---

### Task 8: The card, the rights and the routes

**Files:**
- Modify: `app.py` (the `CHOICES` card, `login()` redirect, `index()`, new routes after the relief routes),
  `static/index.html` or `static/app.js` (an "Exams" link in the committee page header beside "Relief settings")
- Create: `static/choice-exams.svg`
- Test: `tests/test_exams.py` (Flask test client, signing in as in `tests/test_relief.py`)

**Interfaces:**
- `CHOICES["exams"] = dict(title="Exams and events", blurb="Exam and test schedules, seating and invigilation.", label="Your personal code", hint="Use the personal code on the slip from the timetable committee.", roles=("staff",), img="/static/choice-exams.svg")`,
  placed after "relief"; `CHOICE_OF["staff"]` stays `"relief"` (set it explicitly after the comprehension).
- `login()`: a staff code on the Exams card goes to "/exams".
- Constants: `NO_EXAMS_PUB = "Publish the timetable first: exams read the classes, students and lessons from it."`,
  `ONLY_EXAMS = "Only the exams committee and the timetable committee can open exams."`,
  `NO_STUDENTS = "The published timetable has no students. Add them on the Students step and publish again to seat them."`,
  and `schedules.NO_CALENDAR`.
- `_exams_rights(pub) -> tuple[bool, str] | None`: committee → `(True, "Timetable committee")`; staff → `(name in exams settings committee, name)`;
  an ended staff session → None.
- Routes (all `@need("committee", "staff")`; 409 `NO_EXAMS_PUB` when nothing is published; 401 "Please sign in again."
  when the rights are None; 403 `ONLY_EXAMS` when not allowed; 400 with the `ValueError` sentence on a bad save):
  - `GET /exams`, `GET /exams/<id>` → `static/exams.html`; `GET /exams/settings` → `static/exams-settings.html` (both
    pages show `ONLY_EXAMS` themselves from the API's 403).
  - `GET /api/exams/me` → `{name, can_use}`.
  - `GET /api/exams/settings` → `{settings, people, rooms: model rooms [name, kind, capacity]}`; `PUT` saves.
  - `GET /api/exams` → `{schedules: listing(), levels, classes: [name, level], calendar_ok: bool}`;
    `POST /api/exams` `{kind, name, levels, start, end}` → the new schedule (409 `NO_CALENDAR` when the calendar has no terms).
  - `GET /api/exams/<id>` → the schedule; `PUT /api/exams/<id>` → save (the client sends the whole schedule; `made` and
    `pins` are kept from disk, never taken from the client); `DELETE /api/exams/<id>`.
  - `POST /api/exams/<id>/fill` → adds `fill_from_subjects`; `GET /api/exams/<id>/papers.xlsx`;
    `POST /api/exams/<id>/papers.xlsx` (file field `file`) → replaces the level/groups papers with the sheet's.
  - `GET /api/exams/<id>/view` → `{summary, lessons: lesson_lists, made, students: {sid: [name, class]} for this exam's
    students only, rooms: settings rooms, students_missing: bool}`.
  - `POST /api/exams/<id>/make` `{only?}` (409 `NO_STUDENTS` when `model["students"]` is empty; 400 with the first check
    error when `check` has errors: "Fix the paper times first: {first error}");
    `POST /api/exams/<id>/move` `{key, students, room}`; `POST /api/exams/<id>/invigilators` `{key, room, names}`;
    `POST /api/exams/<id>/use-anyway` `{key, room}`; `GET /api/exams/<id>/who?key=&room=` → `candidates(...)`.
- The routes call `relief_settings.load(pub)["calendar"]` for `cal`.

- [ ] **Step 1: Write the failing tests** (put `F.sample_pub()` in place with the same helper `tests/test_relief.py` uses
  to stand in a published timetable; set the relief calendar to `F.CAL` through `relief_settings.save`):
  - `exams_card_on_the_front_page`: `/login` lists "Exams and events"; a staff code on that card redirects to "/exams";
    TEACHER_CODE on it is refused with the link to Teacher's timetable.
  - `only_the_committees_get_in`: a staff member not on the list gets 403 `ONLY_EXAMS` from `/api/exams`; after the
    committee saves them onto the list, 200; the committee always 200.
  - `no_calendar_no_new_exam`: with an empty calendar `POST /api/exams` → 409 `NO_CALENDAR`.
  - `create_fill_make_view`: create a Sec 3 exam for 2026-10-05 (whole day), fill, `PUT` back only English and Pure
    Chemistry timed as in Task 7, `make`, then `view` has `summary.counts.papers == 2`, no unseated students, and
    `students` holds only Sec 3 ids; with a third paper left without a time, `make` → 400 "Fix the paper times first: …".
  - `make_refuses_without_students`: a published model with `students=[]` → 409 `NO_STUDENTS`.
  - `client_cannot_write_made`: a `PUT` carrying a forged `made` and `pins` leaves the stored ones unchanged.
- [ ] **Step 2: Run** the tests — expect failures.
- [ ] **Step 3: Implement** the card, the redirect, the link, the svg and the routes as in Interfaces.
- [ ] **Step 4: Run** `tests/test_exams.py`, `tests/test_relief.py` and `tests/smoke.py` — all pass.
- [ ] **Step 5: Commit** `git add app.py static tests/test_exams.py && git commit -m "Exams: the card and the routes"`

---

### Task 9: Printouts and the Excel download

**Files:**
- Create: `exams/printouts.py`
- Modify: `app.py` (`GET /api/exams/<id>/print/<what>.pdf`, `GET /api/exams/<id>/download.xlsx`, same rights as Task 8)
- Test: `tests/test_exams.py`

**Interfaces:**
- Produces: `pdf(what: str, pub, cal, sched, xset, out) -> None` for `what` in `seating` (per sitting and room: the seat
  grid, each seat "class id" with the name beside in small type), `doors` (per sitting and room: who sits here, by class),
  `attendance` (per sitting and room: a signature line per student), `classes` (per class: each paper's date, time, room
  and seat for each student), `roster-day` (per date: duties with times, rooms, names, chief), `roster-teacher` (per
  teacher: their duties), `timetable` (per level: papers by date with times); fonts and colours from `ttgen.export`
  (`_fonts`, `_hex`, `INK`, `MUTED`) as `relief/codes.py` does; A4; a heading on every page "{school} · {exam name} · {what}".
- Produces: `xlsx(pub, cal, sched, xset) -> bytes` with sheets `Papers` (as the paper list), `Seats` (Date, Start, Room,
  Seat, Student ID, Name, Class, Paper), `Duties` (Date, From, To, Room, Paper(s), Invigilators, Chief, Needs backup),
  `Lessons` (List, Date, From, To, Classes, Subject, Teachers, Room, Note); no cell starts with `=`, `+`, `-`, `@`, tab
  or carriage return (neutralise with a leading apostrophe, as `relief/codes.py` does for its CSV).
- An unknown `what` → 404. Nothing made yet → 409 "Press Make first."

- [ ] **Step 1: Write the failing tests**: each of the seven `what` values gives bytes starting with `%PDF` for the made
  sample exam of Task 7; the xlsx has the four sheet names and a `Seats` row count of 60 + 20 (two sittings) plus the
  header; a student named "=SUM(1)" (a copy of the sample) appears as "'=SUM(1)"; `print/nothing.pdf` → 404; a schedule
  never made → 409 "Press Make first.".
- [ ] **Step 2: Run** the tests — expect failures.
- [ ] **Step 3: Implement** `exams/printouts.py` and the two routes.
- [ ] **Step 4: Run** the tests — all pass.
- [ ] **Step 5: Commit** `git add exams/printouts.py app.py tests/test_exams.py && git commit -m "Exams: printouts and the Excel download"`

---

### Task 10: The pages: list, what and when, papers, settings

**Files:**
- Create: `static/exams.html`, `static/exams.js`, `static/exams-settings.html`, `static/exams-settings.js`
- Test: `node --check static/exams.js static/exams-settings.js`; the browser check is in Task 12

**Interfaces:**
- Consumes: the routes of Tasks 8 and 9. Look and feel as `static/relief.html` / `static/relief-settings.html` (header
  `top`, `card`, `style.css`), and as mockup tabs 1 to 3.
- `/exams` (no id): the list of schedules (mockup tab 1, without statuses other than "Draft") with "+ New exam or test"
  (a small form: Exam or Common test, name, levels as ticks or classes, from and to dates) and a link to Exams settings;
  when `calendar_ok` is false, the list shows `NO_CALENDAR` with a link to `/relief/settings`, and "+ New" is disabled.
- `/exams/<id>`: tabs **1 What and when** (mockup tab 2: name, levels or classes, dates; a row per date with its timetable
  day or "Not a school day", levels sitting, Whole day / Part with from and to as selects of period starts and ends; the
  exam-day times; for a common test, "Supervised by the teacher whose lesson it would have been" / "by invigilators"),
  **2 Papers** (mockup tab 3: the table with level, subject, paper, minutes, who sits with its count, sits with, date and
  start; "Fill from the subjects of …", "Upload a paper list (Excel)", "Download the paper list", "+ Add a paper",
  "+ Add a make-up paper" (picks students by class); the checks panel from `summary.checks`), **3 Access arrangements**
  (student picker by class, extra time %, own room, reader, scribe, note). Every edit is saved with `PUT` after a short
  pause (as relief settings does), showing "Saved" or the server's sentence; "Changes not saved." while a save is pending.
- `/exams/settings` (mockup tab 6's rules panel and the exam rooms): the Exams committee list (picked from people), exam
  rooms (pick from the published rooms: exam seats, rows, columns, hall, access, note), backup invigilators, chief
  invigilators, the "never" list, and the rules; Save; the server's sentence on a refusal.
- Copy fixed here: the tab names above; "Not a school day"; "Whole day"; "Part"; "Saved"; "Changes not saved.".

- [ ] **Step 1:** Build `static/exams.html` and `static/exams.js` for the list and tabs 1 to 3.
- [ ] **Step 2:** Build `static/exams-settings.html` and `static/exams-settings.js`.
- [ ] **Step 3: Run** `node --check static/exams.js` and `node --check static/exams-settings.js` — no output.
- [ ] **Step 4: Commit** `git add static && git commit -m "Exams: the list, what and when, papers, access arrangements, settings"`

---

### Task 11: The pages: schedule, venues and seats, invigilators, lessons

**Files:**
- Modify: `static/exams.html`, `static/exams.js`
- Test: `node --check static/exams.js`; the browser check is in Task 12

**Interfaces:**
- Consumes: `GET /api/exams/<id>/view`, `make`, `move`, `invigilators`, `use-anyway`, `who`, the print and download
  routes.
- Tabs **4 Schedule** (mockup tab 4: the counters; days down, levels across, papers as purple blocks and "normal lessons"
  striped for levels not on that day; the line per day "Teachers: {freed} freed by the exam · {on_duty} on duty ·
  {teaching} still teaching · {backups} backups"; the checks; buttons "Make" (or "Make again" once made) and "Download
  (Excel)"; `gone` sentences shown above the counters; `NO_STUDENTS` shown in place of Make when `students_missing`),
  **5 Venues and seats** (mockup tab 5: a sitting picker; rooms table with seats used / exam seats, who, invigilators;
  busy rooms greyed with their reason and "Use it anyway" for a rain room; the seat grid of a picked room, names on hover;
  "Move class to…" and "Move student to…" (a room select); the print buttons Seating plan, Door list, Attendance sheet,
  Class lists), **6 Invigilators** (mockup tab 6: duties table with reasons, "Backup needed" and "Short by {n}" flags;
  a duty opens "Who could take it" in four groups, Freed by the exam / Free then / Backup invigilators / Would need a
  backup, each with "Use"; the duty load list; Roster by day / by teacher prints), **7 Lessons** (mockup tab 7 without
  the relief buttons: the three lists with counts, by date; a line "Sending backups to the relief team arrives in a later
  stage.").
- Copy fixed here: the tab names; "Make"; "Make again"; "Use it anyway"; "Who could take it"; "Backup needed";
  "Short by {n}"; the per-day line above; the later-stage line.

- [ ] **Step 1:** Build tabs 4 to 7 in `static/exams.js` (and any markup in `static/exams.html`).
- [ ] **Step 2: Run** `node --check static/exams.js` — no output.
- [ ] **Step 3: Commit** `git add static && git commit -m "Exams: schedule, venues and seats, invigilators, lessons"`

---

### Task 12: Finish

**Files:**
- Create: `docs/superpowers/plans/2026-11-21-exams-stage-1-notes.md` (rulings, checks, what was not tried, stage 2 points)
- Modify: `README.md` (one short section: the Exams and events card, who can open it, what stage 1 does)

- [ ] **Step 1: Run every suite** on the final code: `.venv/bin/python tests/<name>.py` for test_exams, test_relief,
  test_typed, test_helper, test_fixes, test_verify, test_rules, test_choices, test_parents, test_sync, test_board,
  test_combined and smoke; `node tests/*.test.js` one by one; `node --check static/app.js static/exams.js static/exams-settings.js`;
  then `--full` for test_typed, test_helper, test_fixes and smoke (run test_typed `--full` alone: it fails when another
  heavy run shares the machine). All pass, or a failure is shown to fail on main too.
- [ ] **Step 2: Browser check with real clicks** (the browser tool's `left_click`, never console clicks), on a scratch
  data folder with the made-up sample published and a made-up calendar, through a temporary launch entry removed
  afterwards (compare the launch file with `cmp`): the card and sign-in for a committee member and a refusal for a
  teacher not on the list; settings (a room, a backup); a new exam; a part day; fill papers; give times; an upload of the
  downloaded paper list; Make; a seat grid; "Move class to…"; "Who could take it" → Use; each print opens a PDF; phone
  width. One line per check saying it was a real click.
- [ ] **Step 3: The school's real published timetable, numbers only** (scratch folder deleted afterwards; nothing printed
  but counts): make a Sec 1–3 exam over one made-up week with one paper per level a day; report the number of lessons
  stopped, duties, backups needed, rooms used and, when the published timetable has students, students seated and
  unseated (when it has none, say so and seat made-up students per class size instead).
- [ ] **Step 4: Check the branch's commits** hold no real staff or student name and not the school's full name
  (`git log -p origin/main..HEAD` searched for every teacher name of the real published timetable, as counts).
- [ ] **Step 5: Write the notes file** and the README section; commit `git add docs README.md && git commit -m "Exams stage 1: notes"`.

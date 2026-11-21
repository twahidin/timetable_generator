# Exams stage 4: events — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Any teacher signed in with their personal code starts an event and is its teacher in charge: the classes, the
days (whole or part), where, the school venues it takes and who goes with the classes (form teachers, the teachers who
would teach those classes then, a department, or picked people), with optional duties. The app shows who going is free
then and whose other lessons need backup, the three lists of lessons, the venues freed and the lessons that use a taken
venue. The event goes through the same approval as an exam; once approved it shows on the main site (class blocks,
people going, venues busy, the Exams and events tab, the banner, a teacher's and a student's own pages) and counts as
busy for exams and other events.

**Architecture:** An event is a schedule with `kind: "event"` in the same store (`exams/schedules.py`), with no papers,
seats or Make. A new module `exams/events.py` holds what is worked out for an event from the published timetable on
every view: the days it covers, the four ways to fill who goes, each person's "free then" (through `invigilate._free`),
the lesson lists, the venues freed and flagged, the clashes, the send errors, who may replace someone away, and the
review. `schedules.copies` and `schedules.busies` make the other schedules' busy people, rooms and classes one list for
exams and events alike. `approval.py` learns an event's fields, changes and away replacement. `published.py` adds the
event layer to a date, the list, a teacher's duties and a student's timetable. `app.py` gains the `/api/events` routes
behind `_event_rights`; the exams pages gain the event list and editor; the published page draws event blocks.

**Tech Stack:** Python 3 / Flask (one gunicorn worker), plain JavaScript, plain-assert test scripts, node tests.

**Spec:** `docs/superpowers/specs/2026-11-20-exams-and-events-design.md`: "Events (mockup tab 8)", "Who uses it" (teacher
in charge), "A teacher is away on a schedule's day", "Approval and the main site", "What people see", "Stages" (stage
4). Mockups `2026-11-20-exams-and-events-mockups.html`, tabs 1, 8 and 10. Controller's brief:
`docs/superpowers/plans/stage-4-brief.md` (its decisions are copied into the notes in Task 8). Stages 1 and 2:
`2026-11-21-exams-stage-1-*.md`, `2026-11-21-exams-stage-2-*.md`.

**Branch:** `exams-stage-4`, stacked on `exams-stage-2` (cut at bd19fa7, not yet merged), with this plan committed first.

## Decisions

From the brief (B) and this plan (P); the notes file repeats them.

- B1 An event is a schedule with `kind: "event"`: `in_charge`, `where`, `venues`, `going`, `going_by` ("form teachers",
  "teachers then", "department", "people") and `duties` ([{duty, who, time}]); no papers, seats or invigilators.
- B2 Any staff member with a personal code may start an event and becomes its teacher in charge; they and the timetable
  committee may open and change it, nobody else; the exams committee does not manage events. Rights only in app.py
  helpers (`_event_rights(sched)`, built as `_exams_gate`).
- B3 Four ways to fill who goes; the teacher in charge adds or removes names; each person shows free then or the lessons
  with other classes that need backup (`invigilate._free` with `elsewhere`).
- B4 A school venue the event takes is busy for exams and other events; running lessons that use it are flagged
  ("{subject} with {classes} uses {room} then"), not moved.
- B5 The three lists in `make.lesson_lists`' shape. B6 Approval as exams; Send needs a name, classes or levels, a day,
  someone going and no clash; the review shows what changes and its checks.
- B7 Someone going who is away is replaced by the teacher in charge on both copies at once, logged, "Done without
  approval". B8 `/api/day` gains event blocks (classes: name, where, time; people going and venues: full readers only);
  Who's free counts them; the banner and the tab "Exams and events" list events. B9 "My exam and event duties"; the
  student's "My exam timetable" lists their class's events. B10 The list's event chip, "+ New event", the editor's four
  tabs. B11 Made-up names; the fixture gains class `parents`. Relief stage 3 is not built: "Sending backups to the relief
  team arrives in a later stage."
- P1 The timetable committee may also start an event: it names the teacher in charge (one of relief's people). A staff
  member's event is always their own.
- P2 Events have their own routes, `/api/events/...`; every exam route answers 404 `NO_EXAM` for an event (so the exams
  committee cannot reach one), and `/api/exams` lists exams and tests only.
- P3 People going are checked with `events.FREE` as the settings (no never list, no duties-a-day limit: those are
  invigilation rules). A Must "Not available" rule, another schedule's duty and another event are reasons.
- P4 A **clash** blocks Send: a person going not free then (P3), a class of the event on another waiting or approved
  schedule at an overlapping time, a venue it takes used by another schedule then. Lessons with other classes are
  backups, not clashes; a running lesson in a taken venue is a flag (a failed review check), not a clash.
- P5 An event has no Make: its lists and checks are worked out on every view, so it has no stale state, no "timetable
  changed" check and never `retimed`.
- P6 A fill adds the names it finds that are not going yet; `going_by` records the last way used.
- P7 A person away is replaced for the whole event, only by someone free then with no lesson running then.
- P8 A duty's person must be going ("Pick a person going for every duty.").
- P9 `approval.public` adds the event fields only for an event: no exam's fingerprint changes.
- P10 Event items on the main site carry `kind: "event"`; exam items keep their exact stage 2 shape.
- P11 Busies of an event cover every date from start to end with classes on (`elsewhere` has no calendar); a non-school
  date holds no lesson or paper, so it changes nothing.
- P12 "Venues freed" (spec) shows in the event's Lessons tab only, not on the main site.

## Global Constraints

- The repo is public: the school is only ever "CTSS"; tests, samples and docs use made-up names only.
- Never print, log or commit a real code, key, token, staff name or student name. Real data is used as counts only.
- No model, Telegram or network call anywhere in this stage.
- Tests are plain-assert scripts run as `.venv/bin/python tests/test_exams.py`, with `DATA_DIR` set to a fresh temp folder
  before `import app` (the existing header). New tests go at the end, before the final `print`.
- Files are written atomically with `store.write_json`; exams data lives under `os.path.join(store.DATA, "exams")`; an
  event is a schedule file in `schedules.DIR`.
- Everything about teachers, classes, students, rooms and lessons is read from the **published** timetable
  (`store.published()["model"]`). Dates become timetable days only through `relief.calendar.school_day`.
- Students come only from `model["students"]`. Access arrangements never leave the exams pages except as a student's own
  room, seat and times on `/api/me/exams`. The shared student code never gets a teacher's name, a seat, a duty room, a
  roster or a print — nor an event's people going, teacher in charge or duties.
- **The main site reads only `sched["approved"]`**, through `schedules.on_site()`; never the working copy.
- Rights: every exams and events rights decision sits in `app.py`'s `_exams_gate`, `_exams_rights`, `_exams_can_approve`,
  `_exams_can_keep_list`, `_published_reader`, `_exams_student` and (new) `_event_rights`. `@need(...)` uses only today's
  role names (committee, head, teacher, student, staff, personal); no new `role()` call outside those helpers.
- Pure modules take `today: datetime.date` and `now: str` as parameters; only `app._exams_today()` and
  `schedules._now()` read the clock.
- Dates shown to people read "Mon 5 Oct" (`days.nice`); times are 24-hour "HH:MM"; inside `exams/` times are minutes.
- Copy is plain words in the app's style. Exact texts fixed by this plan are in quotes; use them verbatim.
- Every stage 2 sentence, shape and fingerprint stays; a stage 2 test changes only where a task here names it.
- `ttgen/timetable_page.html` keeps statements on long lines: never add a `//` comment in the middle of a line (use
  `/* */`). After every edit, extract the last `<script>` and check it:
  `.venv/bin/python -c "s=open('ttgen/timetable_page.html',encoding='utf-8').read();open('/tmp/ttpage.js','w',encoding='utf-8').write(s.rsplit('<script>',1)[1].split('</script>')[0])" && node --check /tmp/ttpage.js`
  — no output. Then copy it to `skill/school-timetable-generator/scripts/ttgen/timetable_page.html` (the two stay
  identical; `cmp` them).
- In `static/*.js`, never put a `//` comment in the middle of a long line; use `/* */`.
- Builders and reviewers: NEVER run `git stash`, `git stash pop` or `git checkout -- <file>`. After each task,
  `git stash list` must show the same entries as before it.
- Every commit ends with the line `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **An event and an exam for the same class at once.** The event's Send is refused with the clash ("Sec 3 End-of-Year
   Exam (approved) has 3A, 3B on Mon 5 Oct too."), the exam's review names the event, and if both reach the main site
   both blocks show and nothing breaks. (Tests in Tasks 2, 4 and 5.)
2. **A person going who teaches other classes then.** They show "teaches 4A Literature 08:40–09:00 → backup", the lesson
   is in "Backup needed" and still runs on the main site (not crossed out), the review counts it. (Tasks 1, 3 and 5.)
3. **A venue the event takes used by a running lesson** (directly, through a combined venue, or as a rain room). It is
   flagged, not moved; the exam's Make and rooms list treat the venue as taken. (Tasks 1, 2 and 3.)
4. **The shared student code asks for a date or the list.** An event block has its name, where and times only: no
   person going, no teacher in charge, no duty, no venue item. (Task 5.)
5. **A teacher who is not in charge opens, changes, sends or replaces in an event**, directly or through the exam routes,
   or forges `in_charge` or `status` in a PUT. Every way is refused or ignored. (Task 4.)

---

## File structure

| File | What changes |
|---|---|
| `exams/events.py` | new: an event's days, fill, who goes and their status, lesson lists, venues freed and flagged, clashes, send errors, who may replace, the review |
| `exams/schedules.py` | `new_event`, the event check, `place`, `copies`, `event_busy`, `busies`, `elsewhere(id, model)`, `listing` kinds |
| `exams/invigilate.py` | `_free`: a busy with no room reads "is on {name} then" |
| `exams/review.py` | `_others_check`: an event that has this exam's classes then |
| `exams/make.py` | `make` reads `elsewhere(id, model)` |
| `exams/approval.py` | event keys in the copy, `blocked`, the event's changes, the sentences naming who sends, `replace_going` |
| `exams/published.py` | event items on a date, event rows in the list, event duties, a student's events |
| `exams/fake.py` | class `parents` |
| `app.py` | `_event_rights`, `_event_gate`, the `/api/events` routes, `/events/<id>`, exam routes refuse events, prints refuse events |
| `ttgen/timetable_page.html` (+ the skill copy) | "Exams and events" tab, event blocks, Who's free wording, events on My exam timetable |
| `static/exams.js`, `static/exams.html`, `static/app.js` | the list with events, New event, the event editor, my exam and event duties, the waiting count |
| `tests/test_exams.py`, `tests/exams.test.js`, `tests/timetable_page.test.js` | every test of this stage |

Test helpers added once (Task 1) after the stage 2 tests, all on `exams/fake.py`'s school (2026-10-05 is "Odd Mon"):
`import exams.events as EV`; `_ev(**kw)` = `SC.new_event("Sec 3 Learning Journey", ["Sec 3"], [], "2026-10-05",
"2026-10-05", "Ms Aisha Rahman", "Ms Aisha Rahman")` updated with `days={"2026-10-05": dict(levels=["Sec 3"],
whole=False, **{"from": "07:40", "to": "10:40"})}`, `where="Off site (museum)"`, `going=["Ms Aisha Rahman", "Ms Grace
Yeo", "Mr Hafiz Rahman"]`, `duties=[dict(duty="Bus marshal", who="Mr Hafiz Rahman", time="07:45")]`, then `kw`.
Task 3 adds (an event can be sent only from then on) `_ev_ok(**kw)` = `_ev(**kw)` sent with `AP.send(e, _M, "Ms Aisha
Rahman", NOW, False, [])` and approved with `AP.approve(e, "Timetable committee", NOW)`, and at module level
`E1 = AP.as_schedule(_ev_ok(venues=["Hall"]))` (beside stage 2's `A1`). On that event: lessons 0
(3A English), 1 (3B Mathematics), 3 (Pure Chemistry) and 4 (Combined Science) stop; Ms Grace Yeo's 4A Literature
08:40–09:00 (LT1) and Mr Hafiz Rahman's 4A PE 09:00–09:40 (Field, rain room Hall) run inside the window; Mr Ivan Lee's
Must rule blocks 07:40–09:40.

---

### Task 1: The event record, who goes, the lessons

**Files:**
- Create: `exams/events.py`
- Modify: `exams/schedules.py`, `exams/fake.py` (parents: 3A ["Ms Aisha Rahman"], 3B ["Ms Chloe Tan"], 4A ["Mr Daniel
  Koh"]; only `tests/test_exams.py` reads this school)
- Test: `tests/test_exams.py`

**Interfaces:**
- Produces: `schedules.EVENT = "event"`, `schedules.GOING_BY = ("form teachers", "teachers then", "department", "people")`.
- Produces: `schedules.new_event(name, levels, classes, start, end, by, in_charge) -> dict`: `dict(id, kind="event", name,
  levels, classes, start, end, days={}, in_charge, where="", venues=[], going=[], going_by="people", duties=[],
  made=None, status="draft", log=[], approved=None, note="", created_at, created_by=by, saved_at=None, saved_by=None)`.
  It reads no file.
- Produces: `schedules._check(s, pub)` for an event: the exam's checks of name, levels and classes, dates and days (one
  shared helper, every exam sentence unchanged) with "Give the event a name." and "An event can cover at most 31 days.";
  then `in_charge` and `where` strings, `venues` and `going` lists of strings, `going_by` in `GOING_BY`, `duties` a list
  of dicts whose `duty`, `who` and `time` are strings (None becomes "") — anything else `WRONG`; each venue a room of the
  model, else "{room} is not a room of the published timetable."; each name going among
  `relief.people.people(pub, relief.settings.load(pub)["extra_staff"])`, else "{name} is not on the published timetable
  or the staff list."; `going` loses repeated names (first kept). `in_charge` is not checked against the people (only at
  creation, Task 4). `KINDS` stays ("exam", "test") for the exam path.
- Produces: `schedules.place(s) -> str`: `where` stripped, else the venues joined ", ", else "".
- Produces in `exams/events.py` (imports `days`, `invigilate`, `schedules`, `seating`, `relief.people`, `relief.settings`;
  reads only relief's settings, as `invigilate.candidates` does):
  - `FREE = dict(never=[], backups=[], rules=dict(max_per_day=None))` (P3).
  - `on_dates(pub, cal, s) -> [dict(date, day, classes: [str], start: int, end: int)]`: dates from start to end that are
    school days with classes on (`days._windows`), in date order, with that day's window.
  - `fill(pub, cal, s, way, dept="", names=()) -> [str]`: the names `way` gives that are not going yet and are among
    relief's people: "form teachers" the `parents` of the classes on the event (model class order); "teachers then" the
    teachers of lessons that stop on its dates, in order of their first stopped lesson (date, start, row); "department"
    everyone whose `depts` hold `dept`, in relief's people order ("" → ValueError "Pick a department."); "people"
    `names` in their order. Another `way` → ValueError `schedules.WRONG`.
  - `going(pub, cal, s, elsewhere) -> [dict(name, tag, status, text)]` per name going, in order: `tag` "teacher in charge"
    and "{class} form teacher" joined " · " ("" for none); on each of `on_dates`, `invigilate._free(name, day_view, start,
    end, [], FREE, elsewhere=elsewhere)`: a reason on any date → status "not_free", text the reason; else lessons running
    in the window → "backup", "teaches {classes} {subject} {HH:MM}–{HH:MM}" (several joined "; ") then " → backup"; else
    "free", "free then: lessons with {classes} stop" when lessons of theirs stop then, else "free then". With more than one
    school date, a reason or a lesson gets " ({Mon 5 Oct})".
  - `lesson_lists(pub, cal, s) -> dict(none, backup, runs)`, items as `make.lesson_lists` (date, start, end, classes,
    subject, teachers, room, note), row order per date: stopped spans → none (note "shortened" when part runs); running
    spans overlapping the window and taught by someone going → backup, note "{teacher} is at {event name}"; the rest →
    runs.
  - `freed(pub, cal, s) -> [dict(date, start, end, rooms)]`: per date, the rooms of stopped lessons less those a running
    lesson uses or names as a rain room in the window (rooms and their related venues, `seating._related`) and the venues
    the event takes; sorted; dates with none left out.
  - `flags(pub, cal, s) -> [str]`, by date, start, room: a running lesson overlapping the window whose room is related to
    a venue taken: "{Mon 5 Oct} {HH:MM}–{HH:MM}: {subject} with {classes} uses {room} then."; whose rain room is: "… uses
    {room} in wet weather then." (times: the running span).
  - `cuts(pub, cal, s) -> [str]`: per date with `days.edge_cuts` n > 0, "On {Mon 5 Oct} the event time ends in the
    middle of 1 lesson." / "… of {n} lessons.".

- [ ] **Step 1: Write the failing tests**:
  - `event_record_and_its_check`: `e = SC.new_event(...)` as in `_ev` has kind "event", in_charge "Ms Aisha Rahman",
    going [], going_by "people", status "draft", approved None; `SC._check(_ev(), _PUB)` passes; `_ev(name=" ")` →
    "Give the event a name."; `_ev(levels=[])` → "Pick at least one level or class."; `_ev(end="2026-11-30")` → "An
    event can cover at most 31 days."; `_ev(venues=["Gym"])` → "Gym is not a room of the published timetable.";
    `_ev(going=["Mr Nobody"])` → "Mr Nobody is not on the published timetable or the staff list.";
    `_ev(going_by="friends")` and `_ev(duties=[dict(duty="x", who=5, time="")])` → `SC.WRONG`; a day "from" "07:50" →
    "07:50 is not the start of a period."; `_ev(going=["Ms Grace Yeo", "Ms Grace Yeo"])` checks to going ["Ms Grace Yeo"];
    `SC.place(_ev(where="", venues=["LT1&2", "Hall"])) == "LT1&2, Hall"`.
  - `fill_the_going_list`: on `_ev(going=[])`: "form teachers" → ["Ms Aisha Rahman", "Ms Chloe Tan"]; "teachers then" →
    ["Ms Aisha Rahman", "Ms Chloe Tan", "Mr Ben Ong", "Ms Grace Yeo"]; "department" with "English" → ["Mr Ivan Lee", "Ms
    Aisha Rahman", "Ms Grace Yeo"], with "" → "Pick a department."; "people" with ["Mr Daniel Koh", "Mr Nobody"] → ["Mr
    Daniel Koh"]; "friends" → `SC.WRONG`; on `_ev(going=["Ms Aisha Rahman"])` "form teachers" → ["Ms Chloe Tan"].
  - `who_goes_free_or_backup` (Review Focus 2): `EV.going(_PUB, F.CAL, _ev(going=["Ms Aisha Rahman", "Ms Grace Yeo", "Mr
    Hafiz Rahman", "Mr Ivan Lee"]), [])` == [dict(name="Ms Aisha Rahman", tag="teacher in charge · 3A form teacher",
    status="free", text="free then: lessons with 3A stop"), dict(name="Ms Grace Yeo", tag="", status="backup",
    text="teaches 4A Literature 08:40–09:00 → backup"), dict(name="Mr Hafiz Rahman", tag="", status="backup", text="teaches
    4A PE 09:00–09:40 → backup"), dict(name="Mr Ivan Lee", tag="", status="not_free", text="is not available then (a Must
    rule)")].
  - `event_lesson_lists`: for `_ev()`: `[(i["subject"], i["classes"]) for i in L["none"]] == [("English", ["3A"]),
    ("Mathematics", ["3B"]), ("Pure Chemistry", ["3A", "3B"]), ("Combined Science", ["3A", "3B"])]`; `[(i["subject"],
    i["start"], i["note"]) for i in L["backup"]] == [("PE", "09:00", "Mr Hafiz Rahman is at Sec 3 Learning Journey"),
    ("Literature", "08:40", "Ms Grace Yeo is at Sec 3 Learning Journey")]`; runs subjects ["Mathematics", "English",
    "Assembly"]; `EV.freed(...) == [dict(date="2026-10-05", start="07:40", end="10:40", rooms=["3-01", "3-02", "Lab
    3-08"])]`, and with `venues=["3-01"]` rooms ["3-02", "Lab 3-08"].
  - `venues_taken_flag_running_lessons` (Review Focus 3): `EV.flags(_PUB, F.CAL, _ev(venues=["LT1&2", "Hall"])) == ["Mon 5
    Oct 08:40–09:00: Literature with 4A uses LT1 then.", "Mon 5 Oct 09:00–09:40: PE with 4A uses Hall in wet weather
    then."]`; `EV.flags` of `_ev()` == []; a day window 07:40–08:00 gives `EV.cuts(...) == ["On Mon 5 Oct the event time
    ends in the middle of 2 lessons."]`; `_ev(start="2026-10-12", end="2026-10-12", days={})` has `on_dates == []`.
- [ ] **Step 2: Run** `.venv/bin/python tests/test_exams.py` — expect an import error.
- [ ] **Step 3: Implement** as in Interfaces.
- [ ] **Step 4: Run** the tests — all pass, stages 1 and 2 included.
- [ ] **Step 5: Commit** `git add exams tests/test_exams.py && git commit -m "Events: the record, its check, who goes and the lessons"`

---

### Task 2: Events among the other schedules; clashes

**Files:**
- Modify: `exams/schedules.py`, `exams/invigilate.py`, `exams/review.py`, `exams/make.py`, `exams/events.py`, `app.py`
  (each `exams_schedules.elsewhere(id)` becomes `elsewhere(id, pub["model"])`)
- Test: `tests/test_exams.py`

**Interfaces:**
- Produces: `schedules.copies(id) -> [dict]`: for every other stored schedule, the copy the main site shows or may
  soon show, with `status` "waiting" or "approved": waiting → `dict(s, status="waiting")`; approved →
  `dict(approval.as_schedule(s), status="approved")`; changes → both (approved first); draft and withdrawn none.
- Produces: `schedules.event_busy(copy, model) -> [busy]`, pure: per date from start to end with classes on
  (`days._windows`; P11), in date order: when `going` is not empty `dict(id, name, status, date, start, end, room="",
  names=list(going), classes=[classes on], kind="event")`, then per venue `dict(..., room=venue, names=[], classes=[],
  kind="event")`; none when the model has no periods (nothing published).
- Produces: `schedules.busies(copies, model) -> [busy]`, pure: an exam copy gives one busy per made duty (stage 2's shape,
  no new key); an event copy gives `event_busy`; a "waiting" copy whose id also has an "approved" copy leaves out the
  busies equal in (date, start, end, room, names) to one of the approved copy's.
- Produces: `schedules.elsewhere(id, model=None) -> busies(copies(id), model)` (None: the published model); stage 2's
  `elsewhere` tests pass unchanged. `make.make`'s `elsewhere=None` reads `elsewhere(sched.get("id"), pub["model"])`.
- Produces: `invigilate._free`: a busy with `room == ""` reads "is on {busy name} then".
- Produces: `review._others_check`: after the takes and uses lines, for each event busy with `classes` on a date, the
  classes also on this schedule then (its window on that date overlaps the busy) give "{other} ({status}) has {classes}
  on {Mon 5 Oct} too." (classes joined ", ", once per other and date).
- Produces in `events.py`:
  - `people_lines(pub, cal, s, elsewhere) -> [str]`: per name going (in order) and date, a `_free` reason gives "{name},
    {Mon 5 Oct} {HH:MM}–{HH:MM}: {why}." (the event's window).
  - `other_lines(pub, cal, s, elsewhere, others) -> [str]`: per other copy (by name, then status) and event date: the
    event's classes also in that copy's windows (`days._windows`) at an overlapping time → "{other} ({status}) has
    {classes} on {Mon 5 Oct} too."; then busies with a room related to a venue taken, on that date, overlapping →
    "{other} ({status}) uses {room} on {Mon 5 Oct} too." (once per other, room, date).
  - `clashes(pub, cal, s, elsewhere, others) = people_lines + other_lines`.
  - `send_errors(pub, cal, s, elsewhere, others) -> [str]`, each when it applies, in this order: "Pick at least one
    school day for the event." (no `on_dates`), "Add at least one person going with the classes.", "Pick a person going
    for every duty." (a duty whose `who` is not going), "Fix the clashes first: {first clash}". The name and the levels
    or classes are checked on every save.
  - `who_free(pub, cal, s, elsewhere) -> dict(freed, free)`: every person relief knows who is not going and, on every
    event date, has no `_free` reason and no lesson running in the window; `freed` (a lesson of theirs stops then) with
    reason "freed: lessons with {classes} stop", else `free` with "free then"; each `dict(name, reason)` by name.

- [ ] **Step 1: Write the failing tests**:
  - `event_busies_for_other_schedules`: `busy = SC.busies([dict(_ev(venues=["Hall"]), id="ev1", status="approved")],
    _M)` == [dict(id="ev1", name="Sec 3 Learning Journey", status="approved", date="2026-10-05", start=460, end=640,
    room="", names=["Ms Aisha Rahman", "Ms Grace Yeo", "Mr Hafiz Rahman"], classes=["3A", "3B"], kind="event"),
    dict(id="ev1", name="Sec 3 Learning Journey", status="approved", date="2026-10-05", start=460, end=640, room="Hall",
    names=[], classes=[], kind="event")]; for `s = _sit([_paper(date="2026-10-05", start="07:50")], days=dict(SEC3))`
    the Hall in `SE.rooms_free(_PUB, F.CAL, s, _first(s), _xset(), set(), elsewhere=busy)` is "taken by Sec 3 Learning
    Journey until 10:40", and `IV._free("Ms Aisha Rahman", D.day_view(_PUB, F.CAL, s, "2026-10-05"), 455, 540, [],
    _xset(), elsewhere=busy)[0] == "is on Sec 3 Learning Journey then"`; after `_reset()`, stored in `SC.DIR` (by
    `store.write_json`) a waiting `_ev(venues=["Hall"])` and a draft `_ev()`: `SC.elsewhere("zzzz", _M)` holds the
    waiting one's two busies only (status "waiting"); `_reset()` after.
  - `event_clashes_with_an_exam_for_the_same_class` (Review Focus 1): `A = _approved()`, `others =
    [dict(AP.as_schedule(A), status="approved")]`, `busy = SC.busies(others, _M)`: `EV.clashes(_PUB, F.CAL, _ev(), busy,
    others) == ["Ms Aisha Rahman, Mon 5 Oct 07:40–10:40: is on Sec 3 End-of-Year Exam then (3-01).", "Mr Hafiz Rahman,
    Mon 5 Oct 07:40–10:40: is on Sec 3 End-of-Year Exam then (3-02).", "Sec 3 End-of-Year Exam (approved) has 3A, 3B on
    Mon 5 Oct too."]` and `EV.send_errors(...)` == ["Fix the clashes first: Ms Aisha Rahman, Mon 5 Oct 07:40–10:40: is
    on Sec 3 End-of-Year Exam then (3-01)."]; the exam's side: `RV.review(_PUB, F.CAL, A, _xset(("3-01", "3-02",
    "4-01", "Hall")), SC.busies([dict(_ev(), id="ev1", status="waiting")], _M))` has others lines ["Sec 3 Learning
    Journey (waiting) takes 2 of these invigilators on Mon 5 Oct.", "Sec 3 Learning Journey (waiting) has 3A, 3B on Mon
    5 Oct too."] and free lines ["Ms Aisha Rahman, 3-01 on Mon 5 Oct 07:35–09:00: is on Sec 3 Learning Journey then.",
    "Mr Hafiz Rahman, 3-02 on Mon 5 Oct 09:45–11:10: is on Sec 3 Learning Journey then."].
  - `event_venue_taken_by_another_schedule`: `others = [dict(_ev(name="Sec 3 Talk", going=[], venues=["LT1"]),
    id="ev2", status="waiting")]`: `EV.other_lines(_PUB, F.CAL, _ev(name="Sec 4 Talk", levels=["Sec 4"],
    days={"2026-10-05": dict(levels=["Sec 4"], whole=False, **{"from": "07:40", "to": "10:40"})}, venues=["LT1&2"],
    going=["Mr Daniel Koh"], duties=[]), SC.busies(others, _M), others) == ["Sec 3 Talk (waiting) uses LT1 on Mon 5 Oct
    too."]` (4A only, so no class line).
  - `event_send_errors`: `EV.send_errors(_PUB, F.CAL, _ev(), [], []) == []`; `_ev(going=[], duties=[])` → ["Add at
    least one person going with the classes."]; `_ev(start="2026-10-12", end="2026-10-12", days={})` → ["Pick at least
    one school day for the event."]; `_ev(duties=[dict(duty="First aid", who="Mr Ben Ong", time="all day")])` → ["Pick
    a person going for every duty."]; with "Mr Ivan Lee" added to going → ["Fix the clashes first: Mr Ivan Lee, Mon 5
    Oct 07:40–10:40: is not available then (a Must rule)."].
  - `who_may_replace_someone_going`: `EV.who_free(_PUB, F.CAL, _ev(), []) == dict(freed=[dict(name="Mr Ben Ong",
    reason="freed: lessons with 3A, 3B stop"), dict(name="Ms Chloe Tan", reason="freed: lessons with 3B stop")],
    free=[])`.
- [ ] **Step 2: Run** the tests — expect failures.
- [ ] **Step 3: Implement** as in Interfaces (`schedules` never imports `events`; `events` imports `schedules`).
- [ ] **Step 4: Run** `tests/test_exams.py` and `tests/smoke.py` — all pass.
- [ ] **Step 5: Commit** `git add app.py exams tests/test_exams.py && git commit -m "Events: busy for exams and other events, clashes, who may replace"`

---

### Task 3: Approval of an event, and its review

**Files:**
- Modify: `exams/approval.py`, `exams/events.py`
- Test: `tests/test_exams.py`

**Interfaces:**
- Produces: `approval.EVENT_KEYS = ("in_charge", "where", "venues", "going", "going_by", "duties")`; `public(sched)`
  copies `SNAP + EVENT_KEYS` for an event, `SNAP` alone for an exam (P9).
- Produces: `approval.WHO = dict(event="the teacher in charge")`, default "the exams committee": approve's refusal reads
  "This schedule changed after it was sent. Ask {who} to send it again." and send back's "Write a note for {who}." (the
  exam sentences are unchanged).
- Produces: `blocked(sched, model, stale, errors)` for an event: no Make needed; `errors[0]` when there are errors (the
  route passes `events.send_errors`), else "Nothing on the main site changes." when approved with no changes, else "".
- Produces: `changes(sched, model)` for an event: a missing day entry reads "as the event"; after the `day` lines, kinds
  `where` "Where: {old or "not set"} → {new or "not set"}."; `venues` "Venues taken: {old} → {new}." (joined ", ",
  "none" when empty); `going` "{name} now goes with the classes." per name added (new order) then "{name} no longer goes
  with the classes." per name removed (old order); `duties` "Duties at the event changed.".
- Produces: `replace_going(sched, away, name, by, now) -> str` (the detail): no snapshot → `NOT_ON_SITE`; `away` not in
  the approved `going` → "{away} is not going."; `name` in it → "{name} is going already.". In the approved copy `away`
  → `name` in place in `going` and as every duty's `who`; in the working copy the same when it holds `away` (when it
  holds `name` already, `away` just leaves); `sent_fp` re-stamped as stage 2 ruling C; log "replaced", detail "{Mon 5
  Oct}[–{Tue 6 Oct}], going: {away} (away) → {name}". The route checks that `name` is free (Task 4).
- Produces: `events.review(pub, cal, sched, elsewhere, others) -> dict(copy, what, checks, changes, done_without)`, the
  copy as `review.review` picks it: `what = dict(kind="event", classes (model order, on any date), levels
  (`days.levels_of`), start, end, days: [dict(date, whole, window: [HH:MM, HH:MM])], where (`place`), in_charge, stopped:
  int (none items), going: int, backups: int (backup items), venues: [dict(room, dates: int, start, end)] by room,
  flagged: int)`; `checks` three `dict(key, ok, lines)`: `going` (`people_lines`, ok "Everyone going is free then."),
  `venues` (`flags`, ok "No running lesson uses the venues taken."), `others` (`other_lines`, ok "No clash with other
  schedules."); `changes` and `done_without` as exams.

- [ ] **Step 1: Write the failing tests**:
  - `event_states_and_copy`: `e = _ev()`: `AP.blocked(e, _M, False, []) == ""`, `AP.blocked(e, _M, False, ["Add at least
    one person going with the classes."])` is that sentence; after send and approve `e["approved"]["going"] ==
    e["going"]`, `set(AP.public(e)) == set(AP.SNAP + AP.EVENT_KEYS)`, label on 2026-10-05 "Approved · on the main site",
    on 2026-10-06 "Ended"; `set(AP.public(_made_sched())) == set(AP.SNAP)`; `AP.send_back` on a waiting event with "  "
    → "Write a note for the teacher in charge."; a waiting event changed after send → approve raises "This schedule
    changed after it was sent. Ask the teacher in charge to send it again.".
  - `event_changes_list`: `e = _ev_ok()`; where "Science Centre", venues ["Hall"], going ["Ms Aisha Rahman", "Mr Hafiz
    Rahman", "Mr Daniel Koh"], duties []: texts == ["Where: Off site (museum) → Science Centre.", "Venues taken: none →
    Hall.", "Mr Daniel Koh now goes with the classes.", "Ms Grace Yeo no longer goes with the classes.", "Duties at the
    event changed."]; send → status "changes", log detail "5 changes"; a "to" of "11:00" on the day adds "Mon 5 Oct:
    part of the day 07:40–10:40 (Sec 3) → part of the day 07:40–11:00 (Sec 3).".
  - `someone_away_from_an_event`: `e = _ev_ok()`: `AP.replace_going(e, "Mr Hafiz Rahman", "Mr Ben Ong", "Ms Aisha Rahman",
    NOW) == "Mon 5 Oct, going: Mr Hafiz Rahman (away) → Mr Ben Ong"`; both copies' going == ["Ms Aisha Rahman", "Ms
    Grace Yeo", "Mr Ben Ong"] and both duties' who "Mr Ben Ong"; status "approved"; `AP.changes(e, _M) == []`;
    `AP.done_without(e)[0]["by"] == "Ms Aisha Rahman"`; away "Mr Daniel Koh" → "Mr Daniel Koh is not going."; name "Ms
    Grace Yeo" → "Ms Grace Yeo is going already."; on `_ev()` → "This schedule is not on the main site.".
  - `event_review` (Review Focus 2 and 3): `e = _ev(venues=["LT1&2", "Hall"])` sent: `EV.review(_PUB, F.CAL, e, [],
    [])` has copy "working", `what == dict(kind="event", classes=["3A", "3B"], levels=["Sec 3"], start="2026-10-05",
    end="2026-10-05", days=[dict(date="2026-10-05", whole=False, window=["07:40", "10:40"])], where="Off site (museum)",
    in_charge="Ms Aisha Rahman", stopped=4, going=3, backups=2, venues=[dict(room="Hall", dates=1, start="07:40",
    end="10:40"), dict(room="LT1&2", dates=1, start="07:40", end="10:40")], flagged=2)`; check keys ["going", "venues",
    "others"], going ok with ["Everyone going is free then."], venues not ok with Task 1's two flags, others ok; with "Mr
    Ivan Lee" going, the going lines are ["Mr Ivan Lee, Mon 5 Oct 07:40–10:40: is not available then (a Must rule)."].
- [ ] **Step 2: Run** the tests — expect failures.
- [ ] **Step 3: Implement** as in Interfaces (`approval` still imports only `days` and `papers`).
- [ ] **Step 4: Run** `tests/test_exams.py` — all pass, every stage 2 approval test unchanged.
- [ ] **Step 5: Commit** `git add exams tests/test_exams.py && git commit -m "Events: approval, changes, someone away, the review"`

---

### Task 4: The event routes and rights

**Files:**
- Modify: `app.py` (exams section), `exams/schedules.py` (`listing`)
- Test: `tests/test_exams.py` (helpers `_event(a)`: as Ms Aisha Rahman, POST `/api/events` `{name: "Sec 3 Learning
  Journey", levels: ["Sec 3"], classes: [], start: "2026-10-05", end: "2026-10-05"}`, then PUT the `_ev` day and where;
  `_approved_event(a, c)`: `_event(a)`, fill "form teachers", fill "department" "PE", send, the committee approves)

**Interfaces:**
- Constants: `NO_EVENT = "That event is not there any more."`, `ONLY_IN_CHARGE = "Only the teacher in charge and the
  timetable committee can open this event."`, `PICK_IN_CHARGE = "Pick the teacher in charge."`, `EVENT_KEEPS = ("id",
  "kind", "in_charge", "created_at", "created_by", "status", "approved", "approved_at", "approved_by", "sent_at",
  "sent_by", "sent_fp", "note", "log")`.
- `_event_rights(sched) -> (may: bool, who: str, every: bool) | None`: the committee `(True, "Timetable committee",
  True)`; staff: None when `me_staff()` is None, else `(sched is None or sched.get("in_charge") == name, name, False)`.
  Added to the helpers of `rights_reads_go_through_named_helpers`.
- `_event_gate(id=None) -> (pub, who, sched, every, err)`: 409 `NO_EXAMS_PUB`; with `id`, a missing schedule or one not
  of kind "event" → 404 `NO_EVENT`; rights None → 401 "Please sign in again."; not `may` → 403 `ONLY_IN_CHARGE`.
- `_exam_or_404(id)` answers 404 `NO_EXAM` for an event; `DELETE /api/exams/<id>` goes through it (P2); `PUT
  /api/exams/<id>` with `kind` "event" → 400 `WRONG` (an exam never becomes an event).
- `schedules.listing(today, published_at=None, kinds=None, in_charge=None)`: only rows of `kinds`, and with `in_charge`
  only events whose `in_charge` is that name; event rows add `in_charge`, `where` (`place`), `classes`, `n_going: int`
  and have `retimed` False (P5). `/api/exams` passes `kinds=("exam", "test")`.
- Routes, all `@need("committee", "staff")`, under `schedules.editing()` from loading to saving, 400 with the ValueError
  sentence (`BAD_INPUT` → `WRONG`):
  - `GET /api/events` → `{schedules: listing(today, published_at, ("event",), None if every else who), levels, classes,
    calendar_ok, people: [names] (every only, else [])}`.
  - `POST /api/events` `{name, levels, classes, start, end, in_charge}`: 409 `NO_CALENDAR` without terms; staff: the event
    is theirs (`in_charge` in the body ignored); the committee: blank → 400 `PICK_IN_CHARGE`, not among relief's people
    → "{name} is not on the published timetable or the staff list."; `new_event`, saved with the check → the event.
  - `GET /api/events/<id>`; `PUT` keeps `EVENT_KEEPS` from the stored copy; `DELETE` → 409 `ON_SITE` while approved.
  - `GET /api/events/<id>/view` → `{summary: {days: [dict(date, day, levels, whole, window)]} (every date of
    `days.dates`), classes (on any date), going, lessons, freed, flags, cuts, clashes, periods, rooms: [model room names],
    depts: [relief departments, sorted], people: [relief names]}` with `elsewhere(id, model)` and `copies(id)`.
  - `POST /api/events/<id>/fill` `{way, dept, names}` → the saved event, `going` + `events.fill(...)`, `going_by = way`.
  - `GET /api/events/<id>/review` and `POST .../send` (saved with the check), `.../approve`, `.../send-back` `{note}`,
    `.../withdraw` (each 403 `ONLY_APPROVE` unless `_exams_can_approve()`; saved with `check=False`), answered by
    `_event_review_reply(pub, s)`: the keys of `_exam_review_reply`, `can_send = blocked(s, model, False,
    send_errors(...))`, `changed` as exams, `review = events.review(...)`.
  - `POST /api/events/<id>/away` `{away, name}`: `name` must be in `who_free` (freed or free) of the approved copy, else
    400 "{name} is not free then."; then `approval.replace_going`; `check=False`.
  - `GET /api/events/<id>/who` → `who_free` of the approved copy; 400 `NOT_ON_SITE` without one.
  - `GET /events/<id>` serves `exams.html`.

- [ ] **Step 1: Write the failing tests** (`_setup()` gives the exams committee ["Ms Grace Yeo"]):
  - `any_teacher_may_start_an_event`: `a = staff("Ms Aisha Rahman")` POSTs → 200, `in_charge == "Ms Aisha Rahman"`,
    kind "event"; `a.get("/api/events")` rows: one, label "Draft", `in_charge` hers, `n_going == 0`; `a.get("/api/exams")`
    → 403 `ONLY_EXAMS`; the committee's POST without `in_charge` → 400 `PICK_IN_CHARGE`, with "Mr Nobody" → "Mr Nobody
    is not on the published timetable or the staff list.", with "Mr Ben Ong" → 200 and his; with no calendar → 409
    `NO_CALENDAR`; `/events/<id>` → 200 for her.
  - `only_the_teacher_in_charge_and_the_committee` (Review Focus 5): her event; `b = staff("Mr Ben Ong")`: GET, PUT,
    DELETE `/api/events/<id>`, POST `send`, `fill`, `away`, GET `view` and `who` → 403 `ONLY_IN_CHARGE`;
    `b.get("/api/events")` rows []; `g = staff("Ms Grace Yeo")` (exams committee): GET and PUT and DELETE
    `/api/exams/<id>` → 404 `NO_EXAM`, `g.get("/api/exams")` rows hold no event, her PUT of a new exam (`_exam(g)`) with `kind`
    "event" → 400 `WRONG`; the committee GETs it (200) and lists
    it; her PUT with `in_charge="Mr Ben Ong"`, `status="approved"` and a forged `approved` keeps all three as stored; her
    `approve` → 403 `ONLY_APPROVE`; `/api/events/<an exam id>` → 404 `NO_EVENT`.
  - `fill_view_send_approve`: before any fill, send → 400 "Add at least one person going with the classes."; her `fill`
    "form teachers" → going ["Ms Aisha Rahman", "Ms Chloe Tan"], going_by "form teachers"; "department" "PE" → + "Mr
    Hafiz Rahman", going_by "department"; `view` going statuses ["free", "free", "backup"], `len(lessons["none"]) == 4`,
    `freed[0]["rooms"] == ["3-01", "3-02", "Lab 3-08"]`; send → 200, label "Waiting for the timetable committee"; the
    committee approves → 200 and `SC.on_site()` holds the event with that going.
  - `event_send_refused_on_a_clash` (Review Focus 1): `_approved_exam(c)` ("Sec 3 Exam"); her event with going filled by
    "form teachers": send → 400 and the error starts "Fix the clashes first: "; its review's others lines hold "Sec 3 Exam
    (approved) has 3A, 3B on Mon 5 Oct too.".
  - `away_on_an_approved_event`: `_approved_event`: `who` → freed names ["Mr Ben Ong"]; away `{away: "Mr Hafiz Rahman",
    name: "Mr Daniel Koh"}` → 400 "Mr Daniel Koh is not free then."; with "Mr Ben Ong" → 200, `SC.on_site()` going ["Ms
    Aisha Rahman", "Ms Chloe Tan", "Mr Ben Ong"], `review.done_without[0]["detail"] == "Mon 5 Oct, going: Mr Hafiz
    Rahman (away) → Mr Ben Ong"`; DELETE → 409 `ON_SITE`; withdraw → `SC.on_site() == []`; DELETE → 200.
- [ ] **Step 2: Run** the tests — expect failures.
- [ ] **Step 3: Implement** the constants, helpers, listing fields and routes as in Interfaces.
- [ ] **Step 4: Run** `tests/test_exams.py`, `tests/test_relief.py` and `tests/smoke.py` — all pass.
- [ ] **Step 5: Commit** `git add app.py exams tests/test_exams.py && git commit -m "Events: routes and rights for the teacher in charge"`

---

### Task 5: Events on the main site, pure, and the reader's cut

**Files:**
- Modify: `exams/published.py`, `app.py` (`/api/published/exams` passes `cal`; the published print answers 404 for an
  event)
- Test: `tests/test_exams.py`

**Interfaces:**
- Produces: `published.EVENT_ROLE = "At event"`.
- Produces: `day(...)`: for each counted event and each class it has on the date (`days._windows`), a class item
  `dict(start, end, label=name, room=place, seat_note="", exam=name, kind="event", p, n)` over the window; with `full`,
  per person going a teacher item `dict(start, end, label=name, room=place, role="At event", duty, exam=name,
  kind="event", p, n)` (`duty`: their duties as "{duty} {time}" stripped, joined ", ", "" for none) and per venue a room
  item `dict(start, end, label=name, exam=name, kind="event", p, n)`. Exam items keep their stage 2 shape (P10). The
  banner and `stopped` already count events (they are `on_site()` copies).
- Produces: `listing(pub, scheds, today, full, cal=None)`: an event row `dict(id, name, kind="event", start, end,
  classes, where=place, days: [dict(date, start, end)])` (school dates when `cal` is given, else every date with classes
  on), with `full` also `in_charge`, `going`, `duties`; no roster or prints. Exam rows unchanged.
- Produces: `my_duties(...)`: an event where `name` is going gives `dict(id, name, kind="event", where, in_charge,
  minutes (the windows' length), duties: [dict(date, start, end, duty)])` per school date; exam entries gain `kind`; the
  `lessons` that don't happen count events' dates too.
- Produces: `my_exams(...)`: an event that has the student's class on a school date gives `dict(id, name, kind="event",
  where, papers=[], days: [dict(date, start, end, note)])`, `note` "then lessons from {HH:MM}" when the window ends before
  the school day ends, else ""; exam entries gain `kind`.

- [ ] **Step 1: Write the failing tests**:
  - `event_on_a_date`: `e = PB.day(_PUB, F.CAL, [E1], "2026-10-05", True)["exams"]`: `stopped == [0, 1, 3, 4]`;
    `classes["3A"] == [dict(start="07:40", end="10:40", label="Sec 3 Learning Journey", room="Off site (museum)",
    seat_note="", exam="Sec 3 Learning Journey", kind="event", p=0.0, n=9.0)]`, no "4A"; `teachers["Mr Hafiz Rahman"]
    == [dict(start="07:40", end="10:40", label="Sec 3 Learning Journey", room="Off site (museum)", role="At event",
    duty="Bus marshal 07:45", exam="Sec 3 Learning Journey", kind="event", p=0.0, n=9.0)]`, Ms Grace Yeo's `duty == ""`;
    `set(rooms) == {"Hall"}`; banner "Sec 3 Learning Journey".
  - `student_code_sees_name_where_time_only` (Review Focus 4): `full=False` gives `teachers == {}`, `rooms == {}`, the
    same class items, and none of "Ms Aisha Rahman", "Ms Grace Yeo", "Mr Hafiz Rahman", "Bus marshal" in `json.dumps` of
    the answer; `PB.listing(_PUB, [E1], date(2026, 10, 1), False, cal=F.CAL)["schedules"][0]` has exactly the keys {"id",
    "name", "kind", "start", "end", "classes", "where", "days"}; with `True` it also has `in_charge == "Ms Aisha
    Rahman"`, `going` as `_ev`, `duties == [dict(duty="Bus marshal", who="Mr Hafiz Rahman", time="07:45")]`, `days ==
    [dict(date="2026-10-05", start="07:40", end="10:40")]`; banner "Sec 3 Learning Journey: Mon 5 Oct.".
  - `event_and_exam_on_one_date` (Review Focus 1): `[A1, E1]` (A1 as stage 2): 3A's items as (start, label) ==
    [("07:40", "Sec 3 Learning Journey"), ("07:50", "Sec 3 English Paper 1"), ("10:00", "Sec 3 Pure Chemistry Paper 1")];
    Ms Aisha Rahman has two teacher items (07:35 invigilating, 07:40 at the event); banner "Sec 3 End-of-Year Exam · Sec
    3 Learning Journey"; Ms Grace Yeo's 4A Literature (row 7) is not in `stopped` (Review Focus 2).
  - `my_event_duties_and_timetable`: `PB.my_duties(_PUB, F.CAL, [E1], "Mr Hafiz Rahman", date(2026, 10, 1))` ==
    dict(schedules=[dict(id=E1["id"], name="Sec 3 Learning Journey", kind="event", where="Off site (museum)",
    in_charge="Ms Aisha Rahman", minutes=180, duties=[dict(date="2026-10-05", start="07:40", end="10:40", duty="Bus
    marshal 07:45")])], lessons=[]); Ms Grace Yeo's lessons == [dict(date="2026-10-05", start="09:40", end="10:40",
    classes=["3A", "3B"], subject="Combined Science")]; Mr Ben Ong: schedules [], lessons the Pure Chemistry 09:40–10:40;
    `PB.my_exams(_PUB, F.CAL, [E1], "3A-07", ...)["schedules"] == [dict(id=E1["id"], name="Sec 3 Learning Journey",
    kind="event", where="Off site (museum)", papers=[], days=[dict(date="2026-10-05", start="07:40", end="10:40",
    note="then lessons from 10:40")])]`; 4A-01 → []; `[A1, E1]` for 3A-07 → the exam, then the event.
  - `event_routes_on_the_main_site`: `_approved_event(a, c)`, then inside `_today(date(2026, 10, 1))`: `as_role("student")` `/api/day?date=2026-10-05` → 3A's item
    keys {"start", "end", "label", "room", "seat_note", "exam", "kind", "p", "n"}, `teachers == {}`, and the reply text
    holds none of the going names; `/api/published/exams` as student: the event row has no "going"; as
    `as_role("teacher")`: going ["Ms Aisha Rahman", "Ms Chloe Tan", "Mr Hafiz Rahman"]; `print/seating.pdf` of the
    event → 404; `as_role("staff", who="Mr Hafiz Rahman")` `/api/exams/my-duties` has the event; `as_role("personal",
    sid="3A-07")` `/api/me/exams` has its day.
- [ ] **Step 2: Run** the tests — expect failures.
- [ ] **Step 3: Implement** as in Interfaces.
- [ ] **Step 4: Run** the tests — all pass, every stage 2 main-site test unchanged.
- [ ] **Step 5: Commit** `git add app.py exams tests/test_exams.py && git commit -m "Events on the main site: blocks, the list, own pages"`

---

### Task 6: The published page: events

**Files:**
- Modify: `ttgen/timetable_page.html`, then copy to `skill/school-timetable-generator/scripts/ttgen/timetable_page.html`
- Test: `tests/test_exams.py` (`the_published_page_has_the_date_choice`: the three old sentences below are replaced in
  its list by the new ones), `tests/timetable_page.test.js`; the browser check is the controller's

**Interfaces:**
- Consumes: the Task 5 shapes.
- `TABS_ALL`'s exams tab reads "Exams and events"; the banner link "See Exams and events"; `renderExams` heading "Exams
  and events" and, with none, "No exams, tests or events on the main site now." (was "No exams or tests on the main site
  now."); `KINDS.event = "Event"`.
- `eventHTML(s)` for `kind === "event"`: the name with "Event · {dates}", a line "Classes {classes} · {where}", a table
  Date | Time from `days`; with `in_charge`, "Teacher in charge: {name}", "Going: {names}", and when there are duties a
  table Duty | Who | Time.
- `dated(v)`: a room item with `kind === "event"` is titled "Event" (else "Exam"); a teacher item's lines add `duty` when
  set; the line with nothing on reads "On {Mon 5 Oct} ({Odd Mon}): no exams, tests or events. This is the usual {Odd
  Mon} timetable." (was "no exams or tests").
- Who's free on a date: the count line ends "Duties, events and the rooms they take count as busy; lessons that don't
  happen do not." (was "Duties and exam rooms count as busy; lessons that don't happen do not."); the date line's empty
  word reads "no exams, tests or events".
- My exam timetable: a schedule shows with papers or `days`; an event's day is a row "{Mon 5 Oct}" | "{name} · {where} ·
  {start}–{end}" | note.

- [ ] **Step 1: Write the failing tests**:
  - Python: the page holds "Exams and events", "See Exams and events", "No exams, tests or events on the main site now.",
    ": no exams, tests or events. This is the usual ", "Teacher in charge: ", "Going: ", "Duties, events and the rooms
    they take count as busy; lessons that don't happen do not.", and equals the skill copy.
  - Node (`tests/timetable_page.test.js`): the Who's free sentence there becomes the new one; a new case "an event on a
    date": a `/api/day` answer with 3A's item `{start: "07:40", end: "10:40", label: "Sec 3 Learning Journey", room: "Off
    site (museum)", seat_note: "", kind: "event", p: 0, n: 9}`, Ms Grace Yeo's teacher item (role "At event", duty
    "Bus marshal 07:45") and an LT2 room item (kind "event") — the node test's own school has no Hall and no Mr Hafiz
    Rahman: 3A's view holds `<b>Sec 3 Learning Journey</b><span class="">Off site (museum)</span><span
    class="m">07:40–10:40</span>`; her view holds `<span class="m">Bus marshal 07:45</span>`; LT2's view holds
    `<b>Event</b>`; Who's free for periods 0 to 3 lists neither her nor LT2.
- [ ] **Step 2: Run** both — expect failures.
- [ ] **Step 3: Implement** the page changes above.
- [ ] **Step 4: Run** the script check of Global Constraints (no output), copy to the skill path, `cmp` (no output),
  `node tests/timetable_page.test.js`, `tests/test_exams.py` and `tests/smoke.py` — all pass.
- [ ] **Step 5: Commit** `git add ttgen/timetable_page.html skill/school-timetable-generator/scripts/ttgen/timetable_page.html tests && git commit -m "Published page: events on a date, the Exams and events tab"`

---

### Task 7: The exams pages: events in the list, New event, the event editor

**Files:**
- Modify: `static/exams.js`, `static/exams.html` (an `ev-kind` chip), `static/app.js`
- Test: `tests/test_exams.py` (`the_exams_pages_carry_the_approval_words`: "My exam duties" and "You have no exam duties
  on the main site." become the new words below), `tests/exams.test.js`; `node --check`; the browser check is the
  controller's

**Interfaces:**
- Consumes: `/api/events` and the Task 4 routes, `/api/exams/me`, `/api/exams/my-duties` (Task 5 shape).
- `S.base` is "/api/exams" on `/exams/<id>` and "/api/events" on `/events/<id>`; every call that names one schedule
  (save, view, review, the approval actions, who, away) uses it; `S.tabs` is the exam tabs or the event tabs.
- **The list** (`/exams`, mockup tab 1): `startList` reads `/api/exams/me`, `/api/exams/my-duties`, `/api/events` and,
  with `can_use`, `/api/exams`. Heading "Exams, tests and events" with "+ New exam or test" (with `can_use`) and "+ New
  event" (everyone); without `can_use` the heading reads "Exams and events" and a link "Back to Relief" stays. Event cards:
  chip "Event", the name linking to `/events/{id}`, " · teacher in charge {in_charge}", the line "{dates} · {levels or
  classes} · {where} · {n_going} going" and the status lines as exams. None: "No exams, tests or events yet." (with
  `can_use`) or "You are not in charge of an event yet.".
- **New event**: a form "New event" (Name, placeholder "e.g. Sec 2 Learning Journey"; Who: levels or "Or pick classes";
  Dates, the last day defaulting to the first; for the committee (`people` not empty) "Teacher in charge", a select) →
  POST `/api/events` → `/events/{id}`; a refusal shows the server's sentence.
- **My exam and event duties** (was "My exam duties"): an event block: its name, rows "{Mon 5 Oct} · {start}–{end}" | "At
  the event · {where}" | "duty: {duty}" (when set), and "teacher in charge: {in_charge}"; none at all: "You have no exam
  or event duties on the main site.".
- **The event editor** (`/events/<id>`, mockup tab 8), tabs "What and when", "Who goes", "Lessons", "Approval":
  - What and when: Name; Who (levels, "Or pick classes"); Dates; the "Each day" table as exams (from the view's
    `summary.days`); "Where" (text, placeholder "Off site (museum)"); "Venues in school" (a tick per room) with "Venues
    ticked here are taken: exams and other events cannot use them then."; a card "Clashes" (● per `clashes` line), "Lessons
    that use a venue taken" (`flags`) and the `cuts`.
  - Who goes: buttons "Form teachers of {classes}", "Teachers who'd teach them then", "A department" (a select of `depts`
    and "Add"), "Pick people" (a select of `people` not going and "Add") → `fill`; one row per person "{name} · {tag}" |
    `text` (free muted, backup flagged, not free bad) | a ✕ (`aria-label` "Take {name} off the list", which also blanks
    their duties' person); "{n} going · {m} with lessons that need backup"; "Duties at the event": rows Duty | Who (a
    select of the going names) | Time with ✕ and "+ Add a duty". With an approved copy, "Someone is away": "Who is away"
    (the approved going), "Who takes it" (`/who`: freed then free, with reasons), "Replace now" → `away`; then "{name}
    goes in their place on the main site now. The timetable committee sees it under Done without approval.".
  - Lessons: stage 2's three lists from the view, "Sending backups to the relief team arrives in a later stage.", and
    "Venues freed: {rooms} on {Mon 5 Oct} {start}–{end} (could be used for a make-up paper)" per `freed` row.
  - Approval: stage 2's tab as it is; `whatBlock` for `what.kind === "event"`: "Classes {classes} ({levels}) · {where} ·
    {when}", "Lessons that won't happen: {stopped} (no relief needed)", "People going: {going} · lessons that need
    backup: {backups} (sending them comes in a later stage)", "Venues taken: …" (as exams, "none"), "Lessons that use a
    venue taken: {flagged}"; `CHECK_NAMES` adds going "People going" and venues "Venues".
- `checkLines`: a free line names the other schedule when it holds " is on {other} then" (with or without a room in
  brackets).
- `static/app.js`: "Exams · {n} waiting" counts the waiting and changes rows of `/api/exams` and `/api/events`.

- [ ] **Step 1: Write the failing tests**: `the_exams_pages_carry_the_event_words`: `exams.js` holds "Exams, tests and
  events", "+ New event", "New event", "Teacher in charge", "Venues in school", "Venues ticked here are taken: exams and
  other events cannot use them then.", "Who goes", "Form teachers of ", "Teachers who'd teach them then", "A department",
  "Pick people", "Take ", "+ Add a duty", "Clashes", "Lessons that use a venue taken", "Venues freed: ", "My exam and
  event duties", "You have no exam or event duties on the main site.", "You are not in charge of an event yet.", "People
  going: ", " goes in their place on the main site now. The timetable committee sees it under Done without approval.",
  "/api/events"; `app.js` holds "/api/events"; `tests/exams.test.js` gains "an event's free line has no room in brackets":
  free ["Ms A, 3-01 on Mon 5 Oct 07:35–09:00: is on Sec 3 Learning Journey then.", the same for "Mr B"] and others
  ["Sec 3 Learning Journey (waiting) takes 2 of these invigilators on Mon 5 Oct."] give `checkLines` [].
- [ ] **Step 2: Run** the tests — expect failures.
- [ ] **Step 3: Implement** the page changes above (look and feel as stages 1 and 2, mockup tab 8).
- [ ] **Step 4: Run** `node --check static/exams.js`, `node --check static/app.js` (no output), `node tests/exams.test.js`
  and `tests/test_exams.py` — all pass.
- [ ] **Step 5: Commit** `git add static tests && git commit -m "Exams pages: events, New event, the event editor"`

---

### Task 8: Finish

**Files:**
- Create: `docs/superpowers/plans/2026-11-21-exams-stage-4-notes.md` (the brief's decisions 1 to 11 and its relief
  note as written in the brief, this plan's P1 to P12 as rulings, rulings made during the build, what was checked, what
  was not tried, points for accounts and relief stage 3)
- Modify: `README.md` (one line in the Exams and events section: any teacher makes an event with their personal code and
  is its teacher in charge; who goes, backups and venues; the same approval; what the main site shows)
- Delete: `docs/superpowers/plans/stage-4-brief.md` once its decisions are in the notes (it is not committed: a plain
  delete)

- [ ] **Step 1: Run every suite** on the final code, one after another: `.venv/bin/python tests/<name>.py` for every
  `tests/*.py` (test_exams, test_relief, test_ask, test_board, test_choices, test_combined, test_fixes, test_helper,
  test_parents, test_rules, test_sync, test_teachers, test_typed, test_venues, test_verify, smoke); `node tests/*.test.js`
  one by one; `node --check static/app.js static/exams.js static/exams-settings.js` and the page script check; then
  `--full` for test_typed (alone), test_helper, test_fixes, test_combined and smoke. All pass, or a failure is shown to
  fail on `exams-stage-2` too.
- [ ] **Step 2: `cmp`** the two `timetable_page.html` copies, and `for f in ttgen/*.py; do cmp -s "$f"
  "skill/school-timetable-generator/scripts/$f" || echo "differs: $f"; done` — no output.
- [ ] **Step 3: The school's real published timetable, counts only** (the newest solver timetable file stage 2 counted;
  a scratch data folder, deleted afterwards; nothing printed but counts, bytes and times): a made-up term, one event for
  the level with most classes on one made-up school day, part of the day over about four periods, going filled by "form
  teachers" then "teachers then" (when the timetable has no form teachers, by "teachers then" only, and say so), one
  venue taken; sent and approved through the functions, beside the stage 2 made-up exam on another level that day.
  Report: classes on the event, lessons that stop, backup items, people going by status, venues freed and flags, the
  clash lines (as a count), the review's three checks as ok or not; `/api/day` for that date (class, teacher and room
  items, bytes, time) for staff and the student code; `/api/published/exams` bytes for both; `my_duties` of one person
  going (as counts) and a student's `my_exams` event rows.
- [ ] **Step 4: Check the branch's commits** hold no real staff or student name and not the school's full name
  (`git log -p exams-stage-2..HEAD` searched for every teacher name of the real timetable, reported as a count).
- [ ] **Step 5: Write the notes and the README line**, remove the brief; commit `git add docs/superpowers/plans/2026-11-21-exams-stage-4-notes.md README.md && git commit -m "Exams stage 4: notes"` (files by name, never `git add -A`). The browser check is the controller's.

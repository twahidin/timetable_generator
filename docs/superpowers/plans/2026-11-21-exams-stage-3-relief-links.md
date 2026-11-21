# Exams stage 3: exams, events and relief — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Relief knows about approved exams and events, and exams know about relief. In relief: a lesson whose classes
are on an approved exam or event is "Not happening", needing no relief; a teacher on an exam duty or at an event is not
offered as free then, and a teacher whose lessons stop then is; "week so far" counts duty and event periods and drops
lessons that do not happen; a teacher on duty who is away can still ask for relief, and is told who replaces their duty.
In exams: someone away or covering relief (from relief's records) is not free then; an approved schedule shows who on it
is now away. When a schedule is approved, the lessons that need a backup go to relief as planned relief ("Invigilating:
…", "At event: …"), unless the exams committee (or the teacher in charge) marks one "Handled ourselves"; a later
approved change, a replacement or a withdrawal updates or cancels them.

**Architecture:** One new module, `exams/relief_links.py`, answers every exams question relief asks (a `Links` object
built from the approved copies for any date) and keeps relief's backup records in step with a schedule (`sync`). Relief
takes a `links=None` keyword in the few functions that need it (`free.free_then`, `free.there_then`,
`free.week_so_far`, `absences.new`), so relief without exams behaves exactly as today; `relief/web.py` builds one
`Links` per request. Relief's records reach exams through `relief_links.relief_busies`, appended to
`schedules.elsewhere`, so every "free then" in exams (Make, the candidates, people going) sees them. Backups are
ordinary planned absences with an `exams` marker, made and cancelled by two new functions in `relief/absences.py`.

**Tech Stack:** Python 3 / Flask (one gunicorn worker), plain JavaScript, plain-assert test scripts, node tests.

**Spec:** `docs/superpowers/specs/2026-11-20-exams-and-events-design.md`: "Lessons on those days", "A teacher is away on
a schedule's day", "What relief gets (and the small changes it needs)", "Approval and the main site" (Withdraw cancels
backups), "Stages" (stage 3), "Calls made in this design". Relief: `2026-11-20-relief-module-design.md` and
`docs/superpowers/plans/2026-11-21-relief-stage-2-notes.md`. Exams stages 2 and 4 notes:
`2026-11-21-exams-stage-2-notes.md`, `2026-11-21-exams-stage-4-notes.md`.

**Branch:** `exams-stage-3` = `exams-stage-4` (PR #82, stacked on #81) with `relief-stage-2` (69f6987, not pushed)
merged in (2a8acef). If `relief-stage-2` gains commits, merge it again; never rebase.

## Decisions

- P1 **Not built here** (they need relief stages 3 and 4): the relief layer on the published timetable on a date, the
  relief team's approval of picks, Telegram messages. Nobody is messaged.
- P2 Only **approved** copies count (`schedules.on_site()`), as for the main site. A waiting change counts only once
  approved.
- P3 A lesson is "not happening" only when **every** period of it stops (`merged_view` running empty). A lesson only
  shortened still needs relief: relief covers lessons whole.
- P4 Busy for relief: an exam's made duties (names, room, minutes) and an event's people going over the event's window
  (`schedules.event_busy`). An event's free-text duties (`who`, `time`) are not busy: their time is words, not minutes.
- P5 Duty and event minutes count as **periods** for "week so far": every period whose bounds overlap a duty or event
  window, once a date, leaving out periods of the person's own lessons that still run (counted already).
- P6 **Backups are planned absences**: `how="planned"`, `reason="Other"`, `reason_text` "Invigilating: {name}" or "At
  event: {name}", `by` "Exams committee" (exam) or the teacher in charge's name (event), plus `exams=dict(id, kind)`.
  So relief's pages, What's in, acknowledging, setting work and choosing relief work on them unchanged. The person on
  duty acknowledges and sets work, as any planned absence.
- P7 A backup is one lesson of one person on duty (or going) that runs during their window, dated today or later, that
  is not "Handled ourselves", for a person not away then. One record per person per schedule.
- P8 **"Handled ourselves"** is the exams committee's own business (the lead: "Exam committee only needs approval to
  change publish website other than that they can do what they need to do within the committee"): stored on the
  schedule as `handled` (["{teacher}|{key}"]), outside the approved copy and the fingerprint, applied to relief at once.
- P9 `sync` runs after every approval action that saves (send, approve, send back, withdraw, someone away) and after a
  "Handled ourselves" change. It is idempotent. It never fails the action: an error is logged and the next action syncs
  again. A new publish does not sync (relief's own `matches_now` marks lessons that changed).
- P10 A person's **own absence wins**: when a teacher with a backup record is absent over its lessons, `absences.new`
  moves those lessons into the new absence (with the relief already chosen and the work), and the backup record drops
  them (cancelled when none is left). `sync` sends no backup for someone away then.
- P11 An absence whose lessons all stop, or that has only duties, may still be sent when the teacher has a duty or event
  then: the duty must be replaced. Without exams (links None) the old refusal stands.
- P12 Withdraw cancels a schedule's backup records, except those whose every date is before today (history stays).
- P13 Locks: `schedules.editing()` may be held while `relief.absences` takes its own lock (sync), never the other way
  round; relief never takes the exams lock.

## Global Constraints

- The repo is public: the school is only ever "CTSS"; tests, samples and docs use made-up names only.
- Never print, log or commit a real code, key, token, staff name or student name. Real data is used as counts only.
- No model, Telegram or network call anywhere in this stage.
- Tests are plain-assert scripts. New tests go in a **new file** `tests/test_exams_relief.py` (header copied from
  `tests/test_exams.py`: `DATA_DIR` set to a fresh temp folder before `import app`), ending
  `print(f"{COUNT} exams and relief tests passed")`. `tests/test_exams.py`, `tests/test_relief.py` and
  `tests/test_relief_requests.py` keep passing; one of their tests changes only where a task here names it.
- Everything about teachers, classes, rooms and lessons is read from the **published** timetable. Dates become timetable
  days only through `relief.calendar.school_day`. Period times come from `exams.days.bounds(model)` (the published
  `times` are a 12-hour clock with no am/pm: never read them).
- Relief functions keep working with `links=None` exactly as before; relief never imports `exams.relief_links` except in
  `relief/web.py` and inside a function (no import cycle: `exams.relief_links` imports `relief.lessons`,
  `relief.absences` and `exams.schedules`).
- Rights: unchanged. Exams and events rights sit in app.py's helpers (`_exams_gate`, `_event_gate`, …); relief's in
  `relief/web.py`'s `_gate`/`_has`. New routes use those helpers only.
- Pure modules take `today` as a parameter; only `app._exams_today()`, `relief.lessons.today()` and the existing `_now()`
  functions read the clock.
- Dates shown read "Mon 5 Oct" (`exams.days.nice`); times "HH:MM"; inside `exams/` times are minutes.
- Copy is plain words. Exact texts in quotes are fixed: use them verbatim.
- In `static/*.js` and `ttgen/timetable_page.html` never put a `//` comment in the middle of a long line; use `/* */`.
  `node --check` every changed static file.
- Builders and reviewers: NEVER run `git stash`, `git stash pop` or `git checkout -- <file>`; `git add` files by name.
- Every commit ends with the line `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **A teacher on an approved duty falls ill after approval.** Their absence is accepted, the backup lessons (with the
   relief already chosen) move into it, the exams page shows them away, and the replacement's backups are sent at the
   replacement. No lesson is covered twice or dropped. (Task 5.)
2. **A withdrawal or change after the dates have passed.** Past backup records stay as they are. (Task 5.)
3. **A date that is not a school day, a calendar with no terms, a timetable with no periods, or no published
   timetable.** `Links` answers "", [] and 0 and never raises; relief's pages work as before. (Task 1, Task 2.)
4. **A new publish after approval.** A backup lesson that vanished is dropped at the next sync without an error; a
   `handled` entry for a vanished lesson is ignored. (Task 5.)
5. **Two schedules on one day.** A teacher on duty for one while their class sits the other has no backup for that
   lesson (it does not run), and a teacher whose class is away is offered as free then. (Tasks 1, 2 and 5.)

---

## File structure

| File | What changes |
|---|---|
| `exams/relief_links.py` (new) | `Links`, `key_of`, `relief_busies`, `away_on`, `backups`, `sync`, `mark` |
| `relief/free.py` | `links=None` in `there_then`, `week_so_far`, `free_then`; `busy` list |
| `relief/absences.py` | `links=None` in `new`; `from_exams`, `exams_records`, `cancel_exams`; own absence takes over |
| `relief/web.py` | one `Links` per request in `/lessons`, `/free`, `POST /absences`; `stopped` and `duties` in `/lessons` |
| `static/relief.js`, `static/relief-plan.js` | "Not happening" rows, duty lines, the busy fold |
| `exams/schedules.py` | `elsewhere` appends `relief_busies` |
| `exams/invigilate.py` | `_free` says a busy's `why` |
| `exams/events.py`, `exams/review.py` | other-schedule lines leave out relief busies; backup items carry `teacher`, `key` |
| `exams/make.py` | backup items carry `teacher`, `key` |
| `app.py` | sync after approval actions; `handled` routes; `away` notices; backup states in the lessons answer; `handled` kept |
| `static/exams.js` | away notices; "Handled ourselves" and the backup states; the "later stage" sentences replaced |
| `README.md`, notes | Task 7 |

---

### Task 1: `exams/relief_links.py`: what approved exams and events mean on a date

**Files:**
- Create: `exams/relief_links.py`
- Test: `tests/test_exams_relief.py` (new; header and helpers: copy `raises`, `t`, the calendar and
  `exams.fake.sample_pub()` set-up from `tests/test_exams.py`)

**Interfaces:**
- Consumes: `exams.schedules.on_site()`, `schedules.busies(copies, model)`, `schedules.event_busy`, `exams.days.bounds`,
  `days.merged_view(pub, cal, scheds, date)`, `days._windows`, `days.hhmm`, `relief.calendar.school_day`,
  `relief.lessons._key(date, day, p, n, classes, subject, group)`.
- Produces:
  - `INVIGILATING = "Invigilating: %s"`, `AT_EVENT = "At event: %s"`, `EXAMS_BY = "Exams committee"`.
  - `key_of(model, row: int, date, day: str) -> str` — relief's key for model lesson `row` on `date` (a date or ISO).
  - `class Links: __init__(self, pub, cal, scheds)`; `Links.load(pub, cal) -> Links` (scheds = `schedules.on_site()`;
    an empty Links when `pub` is None).
  - `Links.stopped(lesson: dict) -> str` — `lesson` as `relief.lessons.on_date` gives it (`key`, `date` a date or ISO).
    "3B is on Sec 3 End-of-Year Exam"; two or more classes "3A, 3B are on …"; two schedules "… on X and Y" (the
    schedules whose windows hold one of the lesson's classes then, by start). "" when a period of it runs.
  - `Links.busy(name, date, p: int, n: int) -> str` — "Invigilating: {exam}" / "At event: {event}" for the first (by
    start) approved duty or event window holding `name` that overlaps periods p..p+n-1; "".
  - `Links.duties(name, date, periods=None) -> list` of `dict(start="HH:MM", end="HH:MM", what, replaces)` by start;
    `what` "Invigilating: {exam} · {room}" or "At event: {event}"; `replaces` "the exams committee" or "{in_charge}, the
    teacher in charge"; `periods=(from, to)` keeps those overlapping those periods.
  - `Links.week_change(name, dates) -> int` — P5: + duty/event periods not also a period of their running lessons,
    − periods of their lessons that stop, summed over `dates`.

- [ ] **Step 1: Write the failing tests** (an approved exam: Sec 3 whole day on a school date, one duty "Ms Aisha
  Rahman" in a room 08:00–09:30; an approved event: Sec 2 part day, going "Mr Ben Ong"; set `status="approved"` and
  `approved = approval.public(s)` directly and save with `schedules.save(..., check=False)`):
  - `links_stopped_names_the_schedule`: a Sec 3 lesson on the date → `"3A is on Sec 3 End-of-Year Exam"`; a mixed lesson
    with a Sec 4 class → `""`; a Sec 2 lesson outside the event window → `""`.
  - `links_shortened_lesson_still_happens`: a lesson half inside a part-day window → `""`.
  - `links_busy_and_duties`: `busy("Ms Aisha Rahman", date, p, 1)` for a period inside 08:00–09:30 →
    `"Invigilating: Sec 3 End-of-Year Exam"`; outside → `""`; `busy("Mr Ben Ong", …)` in the window →
    `"At event: Sec 2 Learning Journey"`; `duties("Mr Ben Ong", date)[0]["replaces"]` ends `", the teacher in charge"`.
  - `links_only_approved`: the same exam with status "waiting" (no approved copy) → every answer "" / [] / 0.
  - `links_week_change`: a duty over two periods where the person teaches nothing → +2; a person whose two Sec 3
    lesson-periods stop and who has no duty → −2; a duty over a period of their own running lesson → that period not
    added.
  - `links_never_raise`: a Saturday, a calendar with no terms, a model with no periods, `Links.load(None, cal)` → "",
    [], 0, no exception (Review Focus 3).
  - `links_two_schedules_one_day` (Review Focus 5): a Sec 3 exam and a Sec 2 event the same date; a lesson of 2A taught
    by the exam's invigilator during the duty → `stopped` names the event (it does not run).

- [ ] **Step 2: Run them to see them fail** — `.venv/bin/python tests/test_exams_relief.py` → ImportError on
  `exams.relief_links`.

- [ ] **Step 3: Implement** `exams/relief_links.py`. Cache per ISO date: the school day, `merged_view` rows of the
  approved copies, a `{key: text}` of stopped lessons and `{name: [(start, end, what, replaces)]}` from
  `schedules.busies([dict(c, status="approved") for c in scheds], model)` (entries with names only; `id` maps back to its
  schedule for the kind, name, room and teacher in charge). Every answer is "", [] or 0 when the date is not a school
  day or there are no periods.

- [ ] **Step 4: Run the tests** — all pass; `tests/test_exams.py` still passes.

- [ ] **Step 5: Commit** — `git add exams/relief_links.py tests/test_exams_relief.py`; message
  "Exams stage 3: what approved exams and events mean for relief on a date".

### Task 2: Relief's "free then" and "week so far" know exams and events

**Files:**
- Modify: `relief/free.py` (`there_then`, `week_so_far`, `free_then`), `relief/web.py` (`free()`), `static/relief-plan.js`
- Test: `tests/test_exams_relief.py`

**Interfaces:**
- Consumes: `Links` (Task 1).
- Produces: `there_then(records, names, date, p, n, links=None)` also leaves out names `links.busy(...)` names;
  `week_so_far(pub, cal, records, name, date, skip=None, links=None)` adds `links.week_change(name, <the week's school
  dates>)`; `free_then(pub, settings, records, lesson, absent, links=None)`: a lesson for which `links.stopped(x)` is
  not "" does not make its teacher "teaching then"; a person with `links.busy(...)` is left out of the groups and listed
  in a new key `busy=[dict(name, why)]` (by name); `week` uses `links`. `relief/web.py` gets
  `_links(pub, cal)` → `exams.relief_links.Links.load(pub, cal)` (imported inside the function).

- [ ] **Step 1: Write the failing tests:**
  - `free_then_leaves_out_the_invigilator`: with the Task 1 exam approved, `free_then(…, links=L)` for a Sec 1 lesson
    08:00–08:40 on the date: "Ms Aisha Rahman" in `busy` with why `"Invigilating: Sec 3 End-of-Year Exam"`, in no group;
    with `links=None` she is offered (when free) as before.
  - `free_then_offers_a_freed_teacher`: a teacher whose only lesson then is a Sec 3 lesson that stops → in a group, not
    in `teaching`.
  - `week_so_far_counts_duties`: `week_so_far(…, links=L)` − `week_so_far(…)` equals `L.week_change(name, week)`.
  - `there_then_leaves_out_someone_on_duty`.
  - `free_route_uses_links`: `GET /api/relief/free` as a planner (relief stage 2's test helpers) answers a `busy` list
    naming the invigilator.
  - `relief_plan_page_shows_the_busy_fold`: `static/relief-plan.js` holds `"on an exam duty or at an event then"`.

- [ ] **Step 2: Run them to see them fail.**

- [ ] **Step 3: Implement.** In the free list of `static/relief-plan.js`, beside the "teaching then" fold, a second fold
  "Show the {n} on an exam duty or at an event then" / "Hide the …", listing "{name} ({why})".

- [ ] **Step 4: Run** `tests/test_exams_relief.py`, `tests/test_relief.py`, `tests/test_relief_requests.py` — all pass;
  `node --check static/relief-plan.js`.

- [ ] **Step 5: Commit** — "Relief: free then and week so far count exams and events".

### Task 3: Asking for and planning relief on an exam or event day

**Files:**
- Modify: `relief/absences.py` (`new`), `relief/web.py` (`lessons()`, `create()`), `static/relief.js` (the ask form),
  `static/relief-plan.js` (the plan form)
- Test: `tests/test_exams_relief.py`

**Interfaces:**
- Consumes: `Links.stopped`, `Links.duties` (Task 1), `there_then(..., links=)` (Task 2).
- Produces: `GET /api/relief/lessons` adds to each lesson `stopped` (Links text or "") and to the answer
  `duties={iso: Links.duties(teacher, date, periods)}`; `absences.new(data, pub, by, how, may_choose=False, links=None)`:
  a lesson with `links.stopped(x)` is `needed=False`, `not_needed=dict(by="app", why="Not happening: " + text)`, whatever
  the client asked; "There are no lessons to cover in that time." is raised only when no lesson is needed **and**
  `links` gives no duty over the dates and periods (P11). `create()` passes `links`.

- [ ] **Step 1: Write the failing tests:**
  - `lessons_route_marks_not_happening`: a Sec 3 teacher's lessons on the exam date: a stopped one has `stopped`
    `"3A is on Sec 3 End-of-Year Exam"`; `duties[iso]` for the invigilator holds `what`
    `"Invigilating: Sec 3 End-of-Year Exam · {room}"`.
  - `new_absence_marks_stopped_lessons`: the record's stopped lesson is not needed with why
    `"Not happening: 3A is on Sec 3 End-of-Year Exam"`, even when the body asks `needed: true`.
  - `duty_only_absence_is_accepted` (P11): the invigilator's lessons that day all stop; `POST /api/relief/absences` for
    them answers 200; with no exam approved the same body is refused "There are no lessons to cover in that time.".
  - `forms_say_not_happening`: `static/relief.js` and `static/relief-plan.js` hold `"Not happening: "`,
    `"no relief needed"` and `"replaces you"` / `"replaces them"`.

- [ ] **Step 2: Run them to see them fail.**

- [ ] **Step 3: Implement.** In both forms a lesson with `stopped` shows "Not happening: {stopped} · no relief needed" and
  no needed choice; under each date with duties, a line per duty: "{what}, {start}–{end}: {replaces} replaces you." (ask
  form) / "… replaces them." (plan form).

- [ ] **Step 4: Run** the three relief and exams-relief suites; `node --check static/relief.js static/relief-plan.js`.

- [ ] **Step 5: Commit** — "Relief: lessons that do not happen on exam and event days, and duties on the forms".

### Task 4: Exams see relief: someone away or covering relief is not free; away notices

**Files:**
- Modify: `exams/relief_links.py` (`relief_busies`, `away_on`), `exams/schedules.py` (`elsewhere`),
  `exams/invigilate.py` (`_free`), `exams/events.py` (`other_lines`), `exams/review.py` (the other-schedules check),
  `app.py` (the exams and events list and review answers), `static/exams.js`
- Test: `tests/test_exams_relief.py`

**Interfaces:**
- Consumes: `relief.absences.all_records()`; busies (`schedules.busies` shape).
- Produces:
  - `relief_busies(model, records) -> list` of busies `dict(id="relief", kind="relief", name="Relief",
    status="approved", date, start, end, room="", names=[name], why)`: for every record not cancelled and without
    `exams`, each date over its `periods` (or the whole day): why `"is away then (relief)"`; for every record not
    cancelled, each needed lesson with a `relief`: why `"covers relief then ({classes} {subject})"` (classes joined
    ", ").
  - `schedules.elsewhere(id, model=None)` returns the other schedules' busies **plus** `relief_busies` (import inside
    the function).
  - `invigilate._free`: a busy with `why` answers its `why`.
  - Every place that turns `elsewhere` into other-schedule lines or tags (`events.other_lines`, the review's
    other-schedules check) leaves out `kind == "relief"`.
  - `away_on(sched, model, records, today) -> list` of `dict(name, date, text)` for an approved schedule, dated today or
    later: an exam duty's name, or an event's person going, with an absence (not `exams`) overlapping their window then.
    text: exam `"Away (from relief): {name} on {Mon 23 Nov}, on duty in {room} {HH:MM}–{HH:MM}. Replace them under
    Someone is away."`; event `"Away (from relief): {name} on {Tue 24 Nov}, going with the event. Replace them under
    Someone is away."`
  - The exams list answer gives each schedule `away` (the texts); the schedule's review answer too. `static/exams.js`
    shows them as notices on the list row and above "Someone is away".

- [ ] **Step 1: Write the failing tests:**
  - `away_person_is_not_a_candidate`: an absence for a teacher on the date → `invigilate.candidates` (through
    `schedules.elsewhere`) leaves them out with reason `"is away then (relief)"`; Make does not pick them.
  - `relief_cover_is_busy`: a teacher chosen as relief for a lesson then → reason `"covers relief then (1A Art)"`.
  - `relief_busies_are_not_other_schedules`: the review of an exam and `events.other_lines` name no "Relief" line.
  - `away_notice_on_an_approved_exam_and_event`: the texts above, exactly; a cancelled absence or a past date → none.
  - `exams_page_shows_away`: `static/exams.js` holds `"Away (from relief)"` handling (`away`).

- [ ] **Step 2: Run them to see them fail.**

- [ ] **Step 3: Implement.**

- [ ] **Step 4: Run** `tests/test_exams_relief.py`, `tests/test_exams.py`, `tests/exams.test.js`; `node --check
  static/exams.js`.

- [ ] **Step 5: Commit** — "Exams: someone away or covering relief is not free; away notices".

### Task 5: Backups go to relief when a schedule is approved

**Files:**
- Modify: `relief/absences.py` (`from_exams`, `exams_records`, `cancel_exams`; `new` takes over; `_no_overlap`),
  `exams/relief_links.py` (`backups`, `sync`, `mark`), `exams/make.py` and `exams/events.py` (`lesson_lists` backup
  items), `app.py` (`_relief_sync`, `handled` routes, `EXAM_KEEPS`/`EVENT_KEEPS`, the lessons answer)
- Test: `tests/test_exams_relief.py`

**Interfaces:**
- Consumes: `Links` (Task 1), `relief_busies` (Task 4), `approval.as_schedule`, `relief.lessons.on_date`,
  `relief.free.there_then`.
- Produces:
  - `absences.from_exams(teacher, lessons, source: dict(id, kind), by, reason_text, records) -> dict | None` — a new
    record (P6) holding exactly `lessons` (dicts from `on_date`, ISO dates), each `needed` unless one of its other
    teachers is there (`there_then`, as `new` decides), `relief=None`, empty work; `None` (nothing saved) when none is
    needed. Under `_LOCK`.
  - `absences.exams_records(source_id) -> list` (not cancelled); `absences.cancel_exams(id, why) -> dict` (cancelled
    `dict(at, by="app", why)`; left as it is when every date is before today).
  - `absences.new`: inside its lock, a lesson of the new absence that is a needed lesson of one of the teacher's
    backup records moves in with its `relief`, `relief_by` and `work`; the backup record drops it and is cancelled with
    why `"Moved to {teacher}'s own absence."` when none is left. `_no_overlap` skips records with `exams`.
  - `relief_links.backups(pub, cal, sched, links, records, today) -> dict` `{name: [lessons]}` (P7), from the approved
    copy: exam duties' names over each duty window, an event's going over its window (`event_busy`); lessons from
    `relief.lessons.on_date` overlapping the window, with `links.stopped(x) == ""`, dated today or later, not in
    `sched.get("handled")` as `"{name}|{key}"`, the person not away then (a `relief_busies` away entry overlapping).
  - `relief_links.sync(sched, pub, cal, today) -> dict(sent=int, cancelled=int)`: desired = `backups(...)` (nothing when
    the schedule has no approved copy). Per person: an existing record with the same lesson keys stays; otherwise the
    old is cancelled (`"The duty changed."`) and a new one made, carrying `relief`, `relief_by` and `work` by key; a
    person no longer desired → cancelled `"The duty changed."`; a withdrawn schedule → every record cancelled
    `"The schedule was withdrawn."` (P12). `by` and `reason_text` per P6.
  - `relief_links.mark(items, sched, records)` — sets on each backup item `state` ("later", "sent", "relief",
    "handled") and `relief` (the name or None): "handled" when in `handled`; "relief" when its record lesson has a
    relief; "sent" when in a record; else "later".
  - `lesson_lists` (make and events) backup items gain `teacher` (the person on duty or going) and `key` (`key_of`).
  - app.py: `_relief_sync(pub, s)` called after a successful save in `_exam_approval` (every action) and in the handled
    routes; catches every exception, `app.logger.exception("exams: relief sync failed")`. `POST /api/exams/<id>/handled`
    (`_exams_gate`, `_exam_or_404`) and `POST /api/events/<id>/handled` (`_event_gate`), body
    `{teacher, key, handled: bool}`: refused 400 `"That lesson no longer needs a backup."` unless it is a backup item of
    the working copy now; saves with `check=False`; answers the schedule's lessons. `handled` joins `EXAM_KEEPS` and
    `EVENT_KEEPS` (a PUT cannot change it) and stays out of `approval.SNAP`. The lessons answer runs `mark`.

- [ ] **Step 1: Write the failing tests:**
  - `approve_sends_backups`: an exam whose invigilator teaches a Sec 1 lesson during the duty; send + approve → one
    relief record, teacher the invigilator, `reason_text` `"Invigilating: Sec 3 End-of-Year Exam"`, `by`
    `"Exams committee"`, `how` "planned", the one lesson needed; it shows in `GET /api/relief/absences` (What's in).
  - `event_backup_by_the_teacher_in_charge`: an approved event → `"At event: Sec 2 Learning Journey"`, by its
    `in_charge`.
  - `handled_ourselves_sends_nothing`: marking the lesson handled on the approved schedule cancels its record; unmarking
    sends it again; a PUT carrying `handled` changes nothing; the fingerprint does not change.
  - `sync_is_idempotent_and_keeps_the_chosen_relief`: approve twice → one record; choose a relief for it, then an
    approved change that adds a second backup lesson for the same person → the new record still has the chosen relief
    on the first lesson.
  - `withdraw_cancels_but_keeps_the_past` (Review Focus 2): withdraw → `"The schedule was withdrawn."`; with
    `relief.lessons.today` set after the date → the record stays uncancelled.
  - `own_absence_takes_over` (Review Focus 1): after approval and a chosen relief, the invigilator asks for relief for
    the whole day → the lesson is in the new absence, needed, with the chosen relief; the backup record is cancelled
    `"Moved to {name}'s own absence."`; then replacing them under "Someone is away" with a person who has no lesson
    then sends no backup for the replacement, and the sync after it sends none for the away person.
  - `republish_drops_a_vanished_backup` (Review Focus 4): publish a timetable without that lesson, run an approval
    action → the record is cancelled, no error; a `handled` key that vanished is ignored.
  - `class_on_another_schedule_needs_no_backup` (Review Focus 5).
  - `sync_failure_does_not_fail_approve`: with `relief_links.sync` replaced by a function that raises, approve answers
    200.

- [ ] **Step 2: Run them to see them fail.**

- [ ] **Step 3: Implement.**

- [ ] **Step 4: Run** `tests/test_exams_relief.py`, `tests/test_exams.py`, `tests/test_relief.py`,
  `tests/test_relief_requests.py` — all pass.

- [ ] **Step 5: Commit** — "Exams stage 3: backups go to relief when a schedule is approved".

### Task 6: The exams pages: "Handled ourselves" and where each backup stands

**Files:**
- Modify: `static/exams.js`, `tests/exams.test.js` (only the cases the old sentences name), `tests/test_exams.py`
  (only the tests that hold the "later stage" sentences)
- Test: `tests/exams.test.js`, `tests/test_exams_relief.py`

**Interfaces:**
- Consumes: backup items with `teacher`, `key`, `state`, `relief` (Task 5); the handled routes; `away` (Task 4).

- [ ] **Step 1: Write the failing tests:** a node case rendering the Lessons tab with one backup item of each state
  shows "Goes to the relief team when approved", "Sent to the relief team", "Relief: Mr Ben Ong", "Handled ourselves",
  and a checkbox labelled "Handled ourselves" for each; source-word test: `static/exams.js` no longer holds
  `"arrives in a later stage"` or `"comes in a later stage"`.

- [ ] **Step 2: Run them to see them fail.**

- [ ] **Step 3: Implement.** In "Backup needed", each row gets a checkbox "Handled ourselves" (posting to
  `/api/exams/<id>/handled` or `/api/events/<id>/handled`, then repainting from the answer) and its state line. The
  sentence under the list becomes "Backups go to the relief team as planned relief when the schedule is approved." The
  Approval tab reads "Backups for the relief team: {n} (sent when approved)" (exam) and "People going: {n} · lessons
  that need backup: {n} (sent to the relief team when approved)" (event), counting only those not handled.

- [ ] **Step 4: Run** every node test file and `node --check static/exams.js`; the exams suites.

- [ ] **Step 5: Commit** — "Exams pages: Handled ourselves and where each backup stands".

### Task 7: Finish: README, notes, every suite, real data

**Files:**
- Modify: `README.md` (the Relief and Exams and events cards: lessons that do not happen, duties count, backups as
  planned relief, "Handled ourselves"), `docs/superpowers/plans/2026-11-21-exams-stage-3-notes.md` (new)

- [ ] **Step 1:** README lines; the notes file: what stage 3 gives, the decisions P1–P13, every ruling from the ledger,
  checks, "Not tried in a browser", deferred minors, and "For relief stage 3" (the relief layer on a date can read
  `Links`; relief's Today should pass `links`; the takeover rule in `absences.new`).
- [ ] **Step 2:** Every suite alone, quick then `--full` for test_typed, test_helper, test_fixes, test_combined and
  smoke; `tests/test_exams_relief.py`; every node file; `node --check` on every changed static file. All pass.
- [ ] **Step 3:** The school's real published timetable (the newest setup in the CTSS folder), counts only, scratch
  folder deleted after: one Sec 3 exam day made, sent and approved through the functions → how many backups sent, how
  many lessons "not happening" on relief's lessons for its invigilators, `free_then` for one Sec 1 lesson then (how many
  left out as busy), the time each takes. Names never printed.
- [ ] **Step 4:** Commit README and notes — "Exams stage 3: notes".

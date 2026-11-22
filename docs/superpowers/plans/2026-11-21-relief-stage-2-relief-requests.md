# Relief stage 2: relief requests on the app — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** In the Relief module, a teacher asks for relief for themselves and sets work for each lesson; management (and
the relief team) plan relief for a colleague, choosing a relief teacher from a ranked "free then" list or leaving it
open; the absent teacher acknowledges relief someone else planned and sets work, or cancels it; the relief team sees
everything that came in, read-only, until stage 3 adds the AI's picks and approval.

**Architecture:** Four new modules in the package `relief/`: `lessons.py` (a teacher's lessons on a date, read from the
published timetable through the school calendar; matching a stored lesson against a later publish), `free.py` (load
numbers and the ranked "free then" list), `absences.py` (the records: one JSON file per absence under
`DATA/relief/absences/`, with checks and plain-sentence refusals) and `files.py` (work files under
`DATA/relief/files/`). The routes live in a Flask blueprint, `relief/web.py`, registered from `app.py` with the app's
`need`, `me_staff` and a new `relief_has(right)`; every permission question goes through `relief_has` so the accounts
work can take it over in one place. The Relief home (`static/relief.html`) grows tabs; the page code is split by job
into `static/relief.js` (home, My absences), `static/relief-form.js` (the lesson list with work boxes, shared),
`static/relief-plan.js` (planning, Planned by me) and `static/relief-inbox.js` (the team's What's in).

**Tech Stack:** Python 3 / Flask (one gunicorn worker), plain JavaScript, plain-assert test scripts.

**Spec:** `docs/superpowers/specs/2026-11-20-relief-module-design.md` (approved 20 Nov 2026): "Module 1. Relief
requests", "The 'free then' list", "Load", "What is kept", "Stages" item 2. Mockups: tabs 1 to 5 of
`docs/superpowers/specs/2026-11-20-relief-module-mockups.html`. Stage 1's notes: `2026-11-20-relief-stage-1-notes.md`.

**Branch:** `relief-stage-2`, cut from `origin/main` at build time (cc310f4 or later), with this plan committed first.

## Decisions taken in this plan (the lead may change any; the first is the lead's own answer)

1. **Who plans relief.** The lead called them "IP heads" and answered on 21 Nov 2026: they are the HODs and SHs. The
   design's planners are the people on the **Management** list in Relief settings, plus the relief team, so today the
   HODs and SHs go on that list (no new list). When the accounts work (project 3, built in another session) lands,
   planning follows its groups: every school leader, HOD and SH has `relief.plan`, plus the relief team; no extra
   "plans relief" tick is needed.
2. **"Reliefs I'm covering" moves to stage 3.** Nothing reaches a relief teacher before the relief team approves it, and
   approving is stage 3, so in stage 2 that list would always be empty.
3. **A read-only "What's in" comes forward from stage 3**, so that a request a teacher sends in stage 2 is never
   invisible: the relief team sees every request, who sent it, the acknowledgement, the work and cancellations. Picks,
   Approve and Today stay in stage 3.
4. **No Telegram yet (stage 4).** The absent teacher sees a planned absence in My absences the next time they open
   Relief; the reporting officer is recorded and told from stage 4; the 15:00 reminder starts in stage 4.
5. **One sign-in.** Stage 2 adds no way of signing in. It uses stage 1's `staff` session (`session["who"]`) and asks
   every permission question through `relief_has(right)` with the accounts work's right names, so when accounts lands
   `relief_has` becomes its `has`.

## Global Constraints

- The repo is public: the school is only ever "CTSS"; tests, samples and docs use made-up names only.
- Never print, log or commit a real code, key or token. Tests make random codes with `secrets.token_hex`.
- No model or Telegram call anywhere in this stage.
- Tests are plain-assert scripts run as `.venv/bin/python tests/<name>.py`, with `DATA_DIR` set to a fresh temp folder
  before `import app` (as `tests/test_relief.py` does). Reuse `relief.people.fake_pub` for published timetables.
- Files are written with `store.write_json`, under one module lock per kind of record.
- "Today" is the school's date: `relief.lessons.today()` = `datetime.datetime.now(ZoneInfo(os.environ.get("SCHOOL_TZ") or "Asia/Singapore")).date()` (the server runs on UTC).
- Everything about teachers and lessons is read from the **published** timetable and the relief settings' calendar.
- The absence reason (and its line of text) is shown only to the absent teacher, whoever planned it, management and the
  relief team — never in a list another teacher can open.
- Copy is plain words in the app's style; exact sentences fixed below are used verbatim.
- Periods are 0-based in the data (`p`, as the published model) and shown as `P{p+1}`; a lesson of `n` periods shows
  `P{p+1}–P{p+n}` with its start and end times.
- Right names (shared with the accounts work): `relief` (any person signed in with their code), `relief.plan`
  (Management list or Relief team), `relief.team` (Relief team), `relief.settings`, `relief.save` (as stage 1).
- Builders and reviewers: NEVER run `git stash`, `git stash pop` or `git checkout -- <file>`; `git stash list` unchanged
  after each task. In `static/*.js`, never a `//` comment in the middle of a long line; use `/* */`.
- Every commit ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`, written with a quoted heredoc.

## Review Focus

1. **A date that is not a school day** (weekend, holiday, outside every term) or **no calendar yet**: the form says so
   in one sentence and sends nothing. (Task 1, Task 3.)
2. **The same teacher asked for twice** for overlapping periods on one date (a planner and the teacher, or two
   planners): the second is refused, naming who sent the first. (Task 3.)
3. **A later publish changes a lesson** that an absence covers: the absence still opens, that lesson is marked "The
   lesson has changed since this was planned", nothing crashes. (Task 1, Task 3.)
4. **Someone reads an absence that is not theirs**: an ordinary teacher gets 403 on another teacher's absence and never
   sees a reason. (Task 4.)
5. **A work file of the wrong kind or too big**, or a link that is not http(s): refused with its sentence; nothing
   half-saved. (Task 3.)

---

## File structure

| File | What it is |
|---|---|
| `relief/lessons.py` | today(); a teacher's lessons on a date; lesson keys; matching against a later publish |
| `relief/free.py` | week and term load; the ranked "free then" list |
| `relief/absences.py` | absence records: make, check, save, list, acknowledge, cancel, not needed, work, relief choice |
| `relief/files.py` | work files: save, read, delete, limits |
| `relief/web.py` | the blueprint with every stage 2 route |
| `app.py` | `relief_has(right)`, registering the blueprint, `/api/relief/me` gains `can_plan` and `on_team` stays |
| `exams/days.py` | `_day_ok` renamed `rule_on_day` (public), its one caller updated |
| `static/relief.html`, `static/relief.js` | the home with tabs; My absences (acknowledge, set work, cancel) |
| `static/relief-form.js` | the lesson list with work boxes, used by Ask and Plan |
| `static/relief-plan.js` | Plan relief for a colleague, Planned by me, Download |
| `static/relief-inbox.js` | the relief team's What's in (read-only) |
| `tests/test_relief_requests.py` | every server test of this stage |
| `README.md` | the Relief section: what stage 2 adds |

---

### Task 1: A teacher's lessons on a date

**Files:** Create `relief/lessons.py`; Modify `exams/days.py` (rename only); Test `tests/test_relief_requests.py`
(create, header as `tests/test_relief.py`).

**Interfaces:**
- Consumes: `relief.calendar.school_day(cal, days, date)`, `relief.calendar.week_of(date)`, `exams.days.bounds(model)`.
- Produces: `relief.lessons.today() -> datetime.date` (see Global Constraints).
- Produces: `relief.lessons.on_date(pub, cal, teacher, date, periods=None) -> list[dict]` — the teacher's lessons that
  date, in time order, each `dict(key, date, day, p, n, start, end, classes, subject, group, room, others, level)`:
  `key` = `f"{date}/{day}/{p}/{n}/{'+'.join(sorted(classes))}/{subject}/{group}"`; `start`/`end` "HH:MM" from `bounds`;
  `others` = the lesson's other teachers (the absent one left out). `periods` = `(from, to)` 0-based inclusive, or
  None for the whole day; a lesson overlapping the span counts. Raises `ValueError(NO_CALENDAR)` when the calendar has
  no terms and `ValueError(f"{date:%a %d %b} is not a school day in the calendar.")` when `school_day` is None.
- Produces: `NO_CALENDAR = "Set the school calendar in Relief settings first: relief needs it to know which timetable day a date is."`
- Produces: `relief.lessons.still_there(pub, cal, teacher, stored: dict) -> bool` — True when `on_date` for that
  teacher and date still holds a lesson with the stored `key`.
- Produces: `relief.lessons.teaching_periods(pub, cal, teacher, date) -> int` — the teacher's periods on every school
  date of `week_of(date)` (holidays and non-school days count 0).
- Change: `exams.days._day_ok` becomes `rule_on_day(day_name, rule)` (same body), used by `day_view` and by Task 2.

- [ ] **Step 1: Write the failing tests** (a `fake_pub` with days `day_names(2)`, a teacher `Ms Evelyn Koh` with
  lessons: "Odd Tue"… use the Term 4 calendar of `tests/test_relief.py`, where 2026-10-13 is "Even Tue"):
  - `lessons_on_a_school_day`: three lessons of hers on "Even Tue" come back in time order with their keys, times and
    classes; a lesson she shares with `Mr Darren Lim` has `others == ["Mr Darren Lim"]`.
  - `some_periods_only`: `periods=(3, 8)` keeps only lessons overlapping periods 3 to 8.
  - `not_a_school_day_and_no_calendar`: Sat 2026-10-17 raises "Sat 17 Oct is not a school day in the calendar.";
    an empty calendar raises `NO_CALENDAR`.
  - `a_changed_lesson_is_noticed`: `still_there` is True for a stored key, False after the lesson moves to another
    period in a new `fake_pub`.
  - `teaching_periods_count_the_school_week`: her periods for the week of 2026-10-13 equal the sum over Even Mon–Fri;
    with Fri 2026-10-16 a holiday, Friday's periods are left out.
  - `today_is_the_schools_date`: with `SCHOOL_TZ` unset, `today()` equals the Singapore date (compare with
    `datetime.now(ZoneInfo("Asia/Singapore")).date()`).
- [ ] **Step 2: Run** `.venv/bin/python tests/test_relief_requests.py` — fails on import.
- [ ] **Step 3: Implement** `relief/lessons.py` and the rename in `exams/days.py`.
- [ ] **Step 4: Run** it, `tests/test_relief.py` and the exams tests (`ls tests | grep -i exam`) — all pass.
- [ ] **Step 5: Commit** "Relief: a teacher's lessons on a date".

---

### Task 2: Load and the "free then" list

**Files:** Create `relief/free.py`; Test `tests/test_relief_requests.py`.

**Interfaces:**
- Consumes: Task 1; `relief.people.people`; `relief.settings.load`; Task 3's `absences.all_records()` shape (a list of
  absence dicts; Task 2's tests build them by hand: `dict(teacher, cancelled=None, lessons=[dict(key, date, p, n, needed, relief)])`).
- Produces: `relief.free.relief_periods(records, name, dates: set) -> int` — periods of lessons where `relief == name`,
  `needed` True, the absence not cancelled, `date` in `dates`.
- Produces: `relief.free.week_so_far(pub, cal, records, name, date) -> int` — `teaching_periods` + relief periods in
  the school dates of `week_of(date)`.
- Produces: `relief.free.free_then(pub, settings, records, lesson: dict, absent: str) -> dict` with
  `groups: [dict(title, people: [dict(name, depts, subjects, fat, week, today, term, marks: [str], over: bool)])]`
  and `teaching: [names]`. Rules, from the design's "free then" list:
  - Free = not teaching any period of the lesson that date; not absent then (a non-cancelled absence of theirs covering
    an overlapping needed lesson, or any absence of theirs that date with `periods` None); no overlapping relief already
    chosen for them; not "Not available" by a Must rule then (`exams.days.rule_on_day`); not on `limits.never`; not the
    absent teacher.
  - Groups, by the absent teacher's departments and the lesson's subject, titled exactly
    `f"{dept} · teaches {subject}"`, `f"{dept} · other subjects"`, `"Other departments"` (empty groups left out).
  - Marks: `"department meeting time"` (inside a "Keep free together" time of their department), `"prefers not"` (a
    Should "Not available"); marked people go after the others in their group.
  - `over` = Flexi Adjunct (role `settings.fat_role`) whose relief periods that date plus this lesson's `n` exceed
    `limits.fat_per_day`, or anyone else over `limits.other_per_day` when set; `over` people are listed (dimmed by the
    page) with the mark `f"at {today} relief periods today (the limit is {limit})"`.
  - Order inside a group: unmarked before marked, then `week`, then `term`, then name.
  - `term` = relief periods in the calendar term holding the date; `today` = relief periods that date.

- [ ] **Step 1: Write the failing tests** (made-up Science, Mathematics and PE teachers; one Flexi Adjunct):
  `free_then_groups_by_department_and_subject`, `busy_absent_and_never_are_left_out`, `a_must_not_available_is_left_out_a_should_is_marked`,
  `keep_free_together_is_marked_and_last`, `over_the_daily_limit_is_listed_but_over`, `order_is_lightest_week_then_term`,
  `week_so_far_counts_teaching_and_chosen_relief`, `a_cancelled_absence_counts_nothing` — each with exact names and
  numbers in its asserts.
- [ ] **Step 2: Run** — fails. **Step 3: Implement.** **Step 4: Run** — passes.
- [ ] **Step 5: Commit** "Relief: load and the free-then list".

---

### Task 3: Absence records and work files

**Files:** Create `relief/absences.py`, `relief/files.py`; Test `tests/test_relief_requests.py`.

**Interfaces:**
- Consumes: Tasks 1 and 2; `relief.settings.load`; `relief.people.people`.
- A record (one JSON file `DATA/relief/absences/<id>.json`, `id` = `secrets.token_hex(6)`):
  `dict(id, teacher, dates: [ISO], periods: [from, to] | None, reason, reason_text, remarks, reporting_officer, by, how ("asked" | "planned"),
  at, acknowledged: {at} | None, cancelled: {at, by, why} | None, lessons: [dict(key, date, day, p, n, start, end, classes, subject,
  group, room, others, needed: bool, not_needed: {by, why} | None, relief: name | None, relief_by: name | None,
  work: dict(text, link, files: [dict(id, name, size)]))])`.
- Produces in `relief/absences.py` (each raises `ValueError(sentence)`; writes under `_LOCK`):
  - `REASONS = ("Medical", "Child sick", "Course", "Other")`.
  - `new(data, pub, by, how) -> dict` — `data` = `dict(teacher, dates, periods, reason, reason_text, remarks, reporting_officer, lessons: [dict(key, needed, relief, work)])`.
    Lessons are rebuilt from `relief.lessons.on_date` for each date (the client's lesson details are not trusted;
    a client key not found raises `CHANGED`). A lesson whose `others` is not empty defaults to `needed=False` with
    `not_needed = {by: "app", why: "{others} is there"}` unless the client sends `needed: true`.
    Checks, in order, with these sentences:
    - teacher not a person: `f"{name} is not on the published timetable or the staff list."`
    - no date, more than 10 dates, a bad date, or a date before `today()`: `"Choose up to 10 school days, today or later."`
    - a date not a school day / no calendar: Task 1's sentences.
    - `periods` not None and not two whole numbers in the day, from ≤ to: `"Choose the periods again."`
    - reason not in `REASONS`, or "Other" with an empty `reason_text`, or `reason_text` over 200 characters:
      `"Choose a reason; for Other, say why in a line."`
    - remarks over 300 characters: `"Keep the remarks under 300 characters."`
    - `how == "asked"` and no `reporting_officer`, or not a person: `"Choose your reporting officer."`
    - no needed lesson in the whole absence: `"There are no lessons to cover in that time."`
    - another non-cancelled absence of the same teacher with an overlapping needed lesson:
      `f"{by_name} has already sent an absence for {teacher} on {date:%a %d %b}."`
    - a `relief` choice that is not in that lesson's `free_then` (any group, `over` allowed):
      `f"{name} is not free for {classes} {subject} then."`
    - `relief` set by someone without `relief.plan`: `"Only management and the relief team choose relief teachers."`
    - work: Task 3's work checks below.
  - `CHANGED = "Your timetable has changed since you opened this page. Open it again."`
  - `load(id) -> dict | None`; `all_records() -> list[dict]` (newest `at` first); `for_teacher(name)`; `planned_by(name)`.
  - `acknowledge(id, by)` — only the absent teacher, only `how == "planned"`, once; else `"Only {teacher} can acknowledge this."` / `"This was acknowledged already."`
  - `set_work(id, key, work, by)` — the absent teacher or whoever planned it; `work` = `dict(text ≤ 2000, link, files)`;
    link empty or starting `http://`/`https://` and ≤ 500: else `"A link starts with http:// or https://."`; text over
    2000: `"Keep the work under 2000 characters."`; files must be ids saved by `relief/files.py` for this absence.
  - `not_needed(id, key, why, by)` and `needed_again(id, key, by)` — the absent teacher, the planner or the relief team.
  - `choose(id, key, relief_name, by, pub)` — `relief.plan` only (the caller checks the right; this checks `free_then`).
  - `cancel(id, why, by)` — the absent teacher, the planner or the relief team; `why` 1 to 200 characters
    (`"Say why in a line."`); a cancelled absence cannot change again (`"This absence was cancelled."`).
  - `matches_now(record, pub, cal) -> dict` — the record with each lesson's `changed = not still_there(...)`.
- Produces in `relief/files.py`: `KINDS = (".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx", ".png", ".jpg", ".jpeg")`,
  `MAX = 10 * 1024 * 1024`, at most 5 files a lesson; `save(absence_id, filename, data: bytes) -> dict(id, name, size)`
  (`"Send a PDF, Word, PowerPoint, Excel or picture file."`, `"A file can be at most 10 MB."`); `path(absence_id, file_id) -> str | None`;
  `delete(absence_id, file_id)`. Stored as `DATA/relief/files/<absence id>/<file id><ext>`; the original name is kept
  in the record only (sanitised to letters, digits, spaces, `.-_()`).

- [ ] **Step 1: Write the failing tests** — one per sentence above (exact text), plus: `asking_for_yourself_round_trip`,
  `planning_for_a_colleague_with_a_chosen_relief_teacher`, `a_shared_lesson_needs_no_relief_unless_asked`,
  `overlap_is_refused_naming_the_first_sender`, `acknowledge_once_only_by_the_absent_teacher`, `cancel_then_nothing_changes`,
  `a_changed_lesson_is_marked_not_fatal` (Review Focus 3), `files_wrong_kind_too_big_and_six_refused`, `nothing_half_saved_on_refusal`
  (the absences folder has no new file after each refusal).
- [ ] **Step 2: Run** — fails. **Step 3: Implement.** **Step 4: Run** — passes.
- [ ] **Step 5: Commit** "Relief: absence records and work files".

---

### Task 4: Rights and routes

**Files:** Create `relief/web.py`; Modify `app.py`; Test `tests/test_relief_requests.py`.

**Interfaces:**
- Produces in `app.py`: `relief_has(right: str) -> bool` per Global Constraints (`relief` = `me_staff()` not None;
  `relief.plan` = staff on `management` or `team`; `relief.team` = staff on `team`; `relief.settings` / `relief.save` as
  `_relief_rights`); `app.register_blueprint(relief_web.bp)` after `relief_web.init(has=relief_has, me=me_staff, role=role)`.
  `/api/relief/me` adds `can_plan = relief_has("relief.plan")` and `can_team = relief_has("relief.team")`.
- Produces in `relief/web.py` (`bp = Blueprint("relief_web", __name__)`; every route returns 401
  `{"error": "Please sign in again."}` without a person, 409 with `NO_RELIEF_PUB` when nothing is published, 400
  `{"error": sentence}` on `ValueError`, 403 `{"error": sentence}` without the right):
  - `GET /api/relief/lessons?teacher=&dates=a,b&from=&to=` → `{lessons: [...], by_date}`; `relief` for yourself,
    `relief.plan` for anyone else (`"Only management and the relief team plan relief for a colleague."`).
  - `GET /api/relief/free?absent=&key=` → `free_then(...)` for that lesson; `relief.plan`.
  - `GET /api/relief/people` → `[{name, depts}]` for the reporting officer and absent-teacher pickers; `relief`.
  - `POST /api/relief/absences` → `new(...)` with `how = "asked"` when `teacher` is yourself, else `"planned"`
    (`relief.plan`); answers the saved record (through `matches_now`).
  - `GET /api/relief/absences/mine` → your records; `GET /api/relief/absences/planned` → records you planned
    (`relief.plan`); `GET /api/relief/absences` → every record, newest first, with `new_since` for the caller
    (`relief.team`; "new" = `at` after the time this person last marked What's in as seen, kept in
    `DATA/relief/seen.json` as `{name: iso}`); `POST /api/relief/absences/seen` records that time (the page calls it
    after showing the list; a GET never writes).
  - `GET /api/relief/absences/<id>` → the record for the absent teacher, its planner, `relief.plan` or `relief.team`;
    else 403 `"This absence is not yours to open."`.
  - `POST …/<id>/acknowledge`, `PUT …/<id>/lessons/<key>/work`, `POST …/<id>/lessons/<key>/not-needed`,
    `POST …/<id>/lessons/<key>/needed`, `PUT …/<id>/lessons/<key>/relief` (`relief.plan`), `POST …/<id>/cancel`.
  - `POST /api/relief/absences/<id>/files` (multipart, one file) → `files.save`, for the absent teacher or the planner;
    `GET /api/relief/files/<id>/<file>` → the file as an attachment with its kept name, for whoever may open the absence.
  - `GET /api/relief/planned.csv?start=&end=` (`relief.plan`): columns `Date, Absent, Class / group, Periods, Time,
    Relief teacher, Remarks, Set by`, cells guarded with `relief.codes._cell`; not the reason.
- Hand-over note in `relief/web.py`'s docstring: when the accounts work merges, `init(has=...)` receives its `has`;
  the right names are already the same.

- [ ] **Step 1: Write the failing tests**: `asking_through_the_api`, `planning_needs_the_right` (an ordinary teacher gets
  403 on `/free` and on POST for someone else), `a_team_member_sees_whats_in_and_new_since`, `management_sees_planned_by_me`,
  `another_teachers_absence_is_403_and_hides_the_reason` (Review Focus 4), `files_round_trip_and_rights`,
  `planned_csv_has_no_reason_and_no_formulas`, `nothing_published_and_signed_out_answers`, `me_has_can_plan_and_can_team`.
- [ ] **Step 2: Run** — fails. **Step 3: Implement.** **Step 4: Run** it, `tests/test_relief.py`, `tests/smoke.py` — pass.
- [ ] **Step 5: Commit** "Relief: rights and routes for relief requests".

---

### Task 5: The teacher's pages: Ask for relief and My absences

**Files:** Modify `static/relief.html`, `static/relief.js`; Create `static/relief-form.js`; Test: browser check in Task 7,
`node --check`.

**Interfaces:** Consumes Task 4's routes. Looks follow mockup tabs 1, 3 and 4 (app halves only).
- Home tabs (only those the person may open): **My absences**, **Ask for relief**, **Plan relief** (`can_plan`),
  **What's in** (`can_team`), and the existing links ("Your timetable" now goes to `/timetable#teachers/<name>`,
  Relief settings, Sign out). The stage 1 line "…arrive here in the next stage." is removed.
- **Ask for relief:** Which day (Today, Tomorrow, Pick dates — up to 10), Away for (Whole day / Some periods with from
  and to), Reason (four buttons; Other shows a line), the lessons in that time (from `/api/relief/lessons`, re-read when
  the dates or periods change) each with its work box, link box and "Add a file" (files upload after the absence is
  saved, then attach with `PUT …/work`), a shared lesson shown as "{others} is there: no relief needed" with "Ask for
  cover anyway", Reporting officer (picker, remembered in `localStorage` key `relief.ro`), **Send to the relief team**.
  A refusal shows the server's sentence and keeps everything typed. Success: "Sent. The relief team can see it."
- **My absences:** each absence (newest first): dates, whole day or periods, reason, "Planned by {by}" or "Asked by
  you", a status chip ("Please acknowledge and set work", "Acknowledged", "Cancelled by {by}: {why}", "With the relief
  team"), and for each lesson its relief teacher or "the relief team will assign", its work (editable), "Not needed" /
  "Needed after all", "The lesson has changed since this was planned" when marked. Buttons: **Acknowledge and save the
  work** (planned absences), **Not needed at all: cancel** (asks for a line).
- `static/relief-form.js` exposes `ReliefForm.lessons(container, lessons, opts)` and `ReliefForm.read(container)`
  (returns `[{key, needed, work}]`), used by Tasks 5 and 6.

- [ ] **Step 1:** Build the pages. **Step 2:** `node --check static/relief.js static/relief-form.js`; run
  `tests/test_relief_requests.py` and `tests/test_relief.py`. **Step 3: Commit** "Relief: Ask for relief and My absences".

---

### Task 6: Planning pages and the team's What's in

**Files:** Create `static/relief-plan.js`, `static/relief-inbox.js`; Modify `static/relief.html`; `README.md`.

**Interfaces:** Consumes Task 4's routes and `ReliefForm`. Looks follow mockup tabs 2 and 5.
- **Plan relief:** date(s), absent teacher (picker of people), whole day / some periods, reason, remarks for the relief
  team; the lessons, each with its work box (optional for the planner) and **Choose a relief teacher**, which opens that
  lesson's "free then" list: the groups with their titles, each person with departments/subjects, "Flexi Adjunct" mark,
  "week {n}", "{n} relief today", marks, dimmed when `over`; "Show the {n} teaching then" folds out names. Choosing
  fills the lesson ("{name}" with ✕ to clear). **Send: {k} chosen, {m} for the relief team**. Under it the note "{absent}
  will see this in their Relief page and is asked to acknowledge and set work."
- **Planned by me:** date, for whom, lessons (chosen / open), acknowledgement chip, cancellation, a link to open the
  absence (the same detail view as My absences, with Choose on open lessons). **Download** (date range → `planned.csv`).
- **What's in** (read-only): mockup tab 5's table — submitted, by and how, for whom, when, reason, absent teacher
  (acknowledged or not, for planned ones), work (`k of n`), relief (`k chosen · m open`), cancelled rows dimmed; views
  Coming up / Today / Cancelled; "new" marked. A line under it: "Picking and approving relief teachers come in the next
  stage."
- README: the Relief section says what stage 2 adds and who can do what.

- [ ] **Step 1:** Build. **Step 2:** `node --check` on both; run the Python suites of Task 4. **Step 3: Commit**
  "Relief: planning pages and the team's What's in".

---

### Task 7: Finish

- [ ] **Step 1:** Every suite on the final code (as stage 1's notes list), the new `tests/test_relief_requests.py`
  included; `test_typed.py --full` alone, not beside another heavy run.
- [ ] **Step 2:** Browser check on a scratch server with the made-up secondary sample and a calendar saved, real pointer
  actions, one line per check: a teacher asks for relief (whole day and some periods), sets work with a link and a file;
  a refusal for a Saturday keeps the form; management plans for a colleague, opens a "free then" list, chooses a teacher,
  leaves one lesson open, sends; the absent teacher sees it, acknowledges, sets work, marks one lesson not needed; a
  second absence for the same lesson is refused with the first sender's name; cancel; the team's What's in shows all of
  it with "new"; an ordinary teacher sees no Plan or What's in tab and gets 403 on another absence's address; phone width.
- [ ] **Step 3:** On the school's real published timetable (scratch folder, numbers only, deleted afterwards): for one
  made-up date in the saved calendar, how many teachers have lessons, the largest "free then" list for a lesson, how
  long `free_then` takes for the busiest teacher's whole day, and that no lesson raises.
- [ ] **Step 4:** Notes file `docs/superpowers/plans/2026-11-21-relief-stage-2-notes.md` (rulings, checks, not tried,
  stage 3 points); grep the branch for the school's full name and real staff names (counts only); then ask the lead
  before the pull request, the merge and the deploy.

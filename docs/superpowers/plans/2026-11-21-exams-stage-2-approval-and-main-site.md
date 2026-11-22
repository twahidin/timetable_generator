# Exams stage 2: approval and the main site — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The exams committee sends a made exam to the timetable committee, which approves it, sends it back with a note,
approves or sends back later changes, or withdraws it. Only the approved copy reaches the main site: the published
timetable on a date shows papers and duties in place of the lessons that stop, an Exams tab and a banner list the
approved exams, each teacher sees their duties and each student their papers and seats.

**Architecture:** Three new pure modules in `exams/`: `approval.py` (the states, the approved copy kept inside the
schedule's JSON, the list of main-site changes, the away replacement, the log), `review.py` (what an approval changes on
the main site, and its checks) and `published.py` (the exam layer of one date, the published list and banner, a
teacher's duties, a student's papers). Seating and invigilation count the rooms and people of other waiting and approved
schedules; Make keeps an approved schedule's unchanged sittings as approved. `app.py` gains the approval routes and the
main-site routes. The published page stays cached per role and embeds nothing about exams: it fetches `/api/day`,
`/api/published/exams` and `/api/me/exams`.

**Tech Stack:** Python 3 / Flask (one gunicorn worker), plain JavaScript, reportlab, plain-assert test scripts.

**Spec:** `docs/superpowers/specs/2026-11-20-exams-and-events-design.md`: "Approval and the main site", "What people see",
"Printouts and downloads", "What is kept", "Stages" (stage 2). Mockups `2026-11-20-exams-and-events-mockups.html`, tabs
1, 9 and 10. Controller's brief: `docs/superpowers/plans/stage-2-brief.md` (its decisions are copied into the notes in
Task 9). Stage 1: `2026-11-21-exams-stage-1-inside-the-committee.md` and `2026-11-21-exams-stage-1-notes.md`.

**Branch:** `exams-stage-2`, at origin/main cc310f4, with this plan committed first.

## Decisions

From the brief (B) and this plan (P); the notes file repeats them.

- B1 States `draft → waiting → approved`; `waiting → draft` with a note (shown "Sent back"); `approved → changes`
  (changes waiting) `→ approved` (approved, or sent back with a note); `approved | changes → withdrawn`; "Ended" is worked
  out (today after the last date). Kept in the schedule JSON: `status`, `approved` (the snapshot), `approved_at`,
  `approved_by`, `sent_at`, `sent_by`, `sent_fp`, `note`, `log` ([{at, by, what, detail}]). The main site reads only
  `approved`.
- B2 Send (anyone who may use exams) needs Make done, not stale, no check errors. Approve, send back and withdraw are for
  the timetable committee only (`_exams_can_approve`). Approving copies the working copy; withdrawing removes the copy.
- B3 After approval, edits and Make change only the working copy; "Send the changes" lists the main-site differences.
- B4 "Someone is away" on an approved duty changes the working copy and the approved copy at once, is logged and listed
  under "Done without approval".
- B5 Rooms and duties of other waiting (working copy) and approved (approved copy) schedules are taken or busy.
- B6 The Approval tab: what changes on the main site, the checks, the buttons; "the timetable changed since this was
  made" compares `made.published_at` with the published meta.
- B7–B11 The date choice and `/api/day`, the banner, the Exams tab with staff prints, My exam duties, My exam timetable.
- B12 A full Make passes `keys=None` to `make._gone`. B13 No history page; the `log` is kept.
- P1 Approve is refused when the schedule changed after it was sent (`sent_fp`), so the committee approves what it saw.
- P2 A full Make on an approved schedule keeps every sitting whose inputs equal the approved copy's exactly as approved
  (seats and invigilators); kept duties are re-checked (Not free, backup) but not refilled; other sittings are made again.
- P3 A schedule with an approved copy cannot be deleted: the timetable committee withdraws it first.
- P4 On the main site a lesson stops when every class in it is on some approved schedule then (two schedules combine).
- P5 A class's line never names an access-arrangements room; make-up papers are not in class lines or the per-level
  timetable (they show on the student's own page and the invigilators' duties).
- P6 The date choice is on `/timetable` only (`/me` filters its lessons, so row numbers differ); the date is not kept in
  the page's link.
- P7 A new "Scripts go to" field (spec: "where scripts go"). P8 Staff prints on the main site: seating plan, both rosters,
  exam timetable; none for the shared student code. P9 Who's free on a date counts duties and exam rooms (spec).
- P10 "Preview on the main site" (mockup tab 10) is not built. P11 The committee page link reads "Exams · {n} waiting".

## Global Constraints

- The repo is public: the school is only ever "CTSS"; tests, samples and docs use made-up names only.
- Never print, log or commit a real code, key, token, staff name or student name. Real data is used as counts only.
- No model, Telegram or network call anywhere in this stage.
- Tests are plain-assert scripts run as `.venv/bin/python tests/test_exams.py`, with `DATA_DIR` set to a fresh temp folder
  before `import app` (the existing header). New tests go at the end, before the final `print`.
- Files are written atomically with `store.write_json`; exams data lives under `os.path.join(store.DATA, "exams")`.
- Everything about teachers, classes, students, rooms and lessons is read from the **published** timetable
  (`store.published()["model"]`). Dates become timetable days only through `relief.calendar.school_day`.
- Students come only from `model["students"]`. Access arrangements never leave the exams pages except as a student's own
  room, seat and times on `/api/me/exams`. The shared student code never gets a teacher's name, a seat, a duty room, a
  roster or a print.
- **The main site reads only `sched["approved"]`**, through `schedules.on_site()`; never the working copy.
- Rights: every exams rights decision sits in `app.py`'s `_exams_gate`, `_exams_rights`, `_exams_can_approve` and
  `_published_reader`. `@need(...)` uses only today's role names (committee, head, teacher, student, staff, personal); no
  new `role()` call outside those four helpers (personal accounts will rewrite them).
- Pure modules take `today: datetime.date` and `now: str` as parameters; only `app._exams_today()` and
  `schedules._now()` read the clock.
- Dates shown to people read "Mon 5 Oct" (`days.nice`); times are 24-hour "HH:MM"; inside `exams/` times are minutes.
- Copy is plain words in the app's style. Exact texts fixed by this plan are in quotes; use them verbatim.
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

1. **A schedule approved, then the timetable published again.** The main site keeps the approved copy (lessons that stop
   are worked out from the new lessons with the approved windows); the Approval tab says the timetable changed and names
   the invigilator who now teaches then; Make again keeps the approved sittings and flags the clash. (Tests in Tasks 2
   and 3.)
2. **The shared student code asks `/api/day` or `/api/published/exams`.** No teacher names, no duty rooms, no roster, no
   prints, and no class line names the access-arrangements room. (Tests in Tasks 5 and 6.)
3. **A date outside every term, or a holiday.** `/api/day` answers `day: null` with an empty exam layer; the page says
   "Not a school day."; a malformed date gets a sentence, not a 500. (Tests in Tasks 5 and 6.)
4. **Two schedules approved for overlapping dates.** Both show; a lesson whose classes sit different schedules at once
   stops; the banner names both; the second's Make treats the first's rooms and invigilators as taken; the review names a
   clash. (Tests in Tasks 2, 3 and 5.)
5. **An approved schedule edited and Made, changes not sent (or sent, not yet approved).** The main site, My exam duties,
   My exam timetable and the staff prints still show the approved copy. (Tests in Tasks 4 and 5.)

---

## File structure

| File | What changes |
|---|---|
| `exams/approval.py` | new: states and labels, the snapshot and its fingerprint, send/approve/send back/withdraw, the change list, the away replacement, the log |
| `exams/review.py` | new: what an approval changes on the main site, and the five checks |
| `exams/published.py` | new: the exam layer of a date, the published list and banner, a teacher's duties, a student's papers |
| `exams/days.py` | `nice`, `merged_view` (with `day_view` built on a shared `_rows`) |
| `exams/schedules.py` | `scripts` field, listing labels, `elsewhere`, `on_site` |
| `exams/seating.py`, `exams/invigilate.py` | other schedules as taken and busy; `recheck` |
| `exams/make.py` | other schedules, `published_at`, keeping approved sittings, `sitting_fp`, the `_gone` fix |
| `exams/printouts.py` | `_day` is `days.nice` |
| `app.py` | the rights helpers, the approval routes, the main-site routes, `/timetable` and `/me` config, `TABS` |
| `ttgen/timetable_page.html` (+ the skill copy) | date choice, crossed lessons, exam cells, Who's free on a date, banner, Exams tab, My exam timetable |
| `static/exams.js`, `static/exams.html` | statuses, the Approval tab, Someone is away, My exam duties, Scripts go to |
| `static/app.js` | the committee page's Exams link count |
| `tests/test_exams.py` | every test of this stage |

Test helpers added once (Task 1) at the top of the new tests: `NOW = "2026-10-01T08:00:00"`;
`_approved(pub=_PUB, access=(), rooms=("3-01", "3-02", "4-01", "Hall"), **kw)` returns `_made_sched(**kw)` with
`access`, made with `MK.make(pub, F.CAL, s, _xset(rooms))`, then `AP.send(s, _M, "Ms Grace Yeo", NOW, False, [])` and
`AP.approve(s, "Timetable committee", NOW)` (Task 2 adds `elsewhere=[]` to this Make and to `_mk`).
Made on the sample (verified on stage 1 code): duties `2026-10-05 07:50|3-01` 455–540 ["Ms Aisha Rahman", "Ms Chloe
Tan"]; `2026-10-05 10:00|3-01` 585–670 ["Mr Ben Ong", "Mr Daniel Koh"]; `2026-10-05 10:00|3-02` 585–670 ["Mr Hafiz Rahman",
"Mr Ivan Lee"]; 07:50: 3A (30) in 3-01, 3A-07 at "B1"; 10:00: 3A-01..10 in 3-01, 3B-01..10 in 3-02; with 3A-05 on
`own_room=True, extra=25` and room 3-11 (access) she sits 3-11 "A1" in both sittings. Every new pure test starts with
`_reset()`.

---

### Task 1: Approval states, the approved copy, the change list

**Files:**
- Create: `exams/approval.py`
- Modify: `exams/days.py` (add `nice`), `exams/printouts.py` (`_day = _days.nice`)
- Test: `tests/test_exams.py` (import `exams.approval as AP`)

**Interfaces:**
- Produces: `days.nice(iso: str) -> str`: "Mon 5 Oct" from the first ten characters; anything else comes back as given.
- Produces: `approval.SNAP = ("name", "kind", "levels", "classes", "start", "end", "days", "times", "papers", "access",
  "seating", "supervision", "scripts", "made", "pins", "use_anyway")`.
- Produces: `public(sched) -> dict`: deep copies of `SNAP` (missing keys as None; `scripts` ""), with `made` cut to
  `dict(seats, unseated, duties, published_at)` (None when not made). `fp(sched) -> str`: first 16 hex of sha256 of
  `json.dumps(public(sched), sort_keys=True)`.
- Produces: `as_schedule(sched) -> dict | None`: `dict(sched["approved"], id=sched["id"], status=sched["status"])`, None
  without a snapshot. `last_date(s) -> str`: the latest of `s["end"]` and every paper date.
- Produces: `label(sched, today) -> str`: "Ended" when status is approved or changes and `today.isoformat()` is after
  `last_date(sched["approved"])`; else by status: draft "Draft" ("Sent back" when `note`), waiting "Waiting for the
  timetable committee", approved "Approved · on the main site", changes "Approved · changes waiting", withdrawn
  "Withdrawn". A missing status is draft.
- Produces: `approval.STALE = "The exam changed since Make: press Make again."`; `make.STALE` is set from it (`make`
  imports `approval`, never the other way).
- Produces: `blocked(sched, model, stale: bool, errors: list[str]) -> str` ("" when it may be sent): "Press Make first."
  (no `made`), `STALE`, "Fix the paper times first:
  {errors[0]}", and for status approved "Nothing on the main site changes." when `changes` is empty.
- Produces: `send(sched, model, by, now, stale, errors) -> None` (ValueError with `blocked`'s sentence): draft or
  withdrawn → waiting (log "sent"); waiting → waiting (log "sent again"); approved → changes, changes → changes (log
  "changes sent", detail "{n} change(s)"); sets `sent_at`, `sent_by`, `sent_fp = fp(sched)`, `note = ""`.
- Produces: `approve(sched, by, now) -> None`: needs status waiting or changes, else "There is nothing waiting for
  approval."; `fp(sched) != sched["sent_fp"]` → "This schedule changed after it was sent. Ask the exams committee to send
  it again."; sets `approved = public(sched)`, `approved_at`, `approved_by`, status approved, `note = ""`; log "approved"
  or "changes approved".
- Produces: `send_back(sched, note, by, now) -> None`: blank note → "Write a note for the exams committee."; waiting →
  draft (log "sent back"), changes → approved (log "changes sent back"), else "There is nothing waiting for approval.";
  keeps `note` (stripped); the log detail is the note.
- Produces: `withdraw(sched, by, now) -> None`: no snapshot → "This schedule is not on the main site."; `approved = None`,
  status withdrawn, log "withdrawn".
- Produces: `changes(sched, model) -> list[dict(kind, text)]`, working copy (`public`) against `sched["approved"]`, kinds
  in this order, each sentence ending with ".":
  `name` "Name: {old} → {new}."; `dates` "Dates: {nice}–{nice} → {nice}–{nice}."; `levels` "Levels and classes: {old} →
  {new}." (levels then classes, joined ", "); `day` per date whose `days` entry differs "{nice}: {old} → {new}." (an entry
  reads "whole day", "part of the day {from}–{to}", either with " ({levels})" when it names levels, or "as the exam");
  `times` "Report time: {old} → {new}."; `scripts` "Scripts go to: {old or "not set"} → {new or "not set"}.";
  `access` "Access arrangements changed for {n} student(s)."; `paper` by id: "Added {label}: {nice} {start}–{end}." (or
  "Added {label} with no time."), "Removed {label}.", "{label}: {nice} {start}–{end} → {nice} {start}–{end}." (date,
  start or minutes changed), "{label}: who sits changed."; `duty` per (key, room) whose names differ: "{nice} {HH:MM},
  {room}: {leaving} → {joining} (invigilator)." (names joined ", ", "no one" when empty, "invigilators" when either side
  has two or more); `rooms` per sitting and class whose room counts differ: "{nice} {HH:MM}, {class}: {old} → {new}." (a
  side is "3-01", or "3-01 (29), 3-02 (1)" by count then name, or "not seated"); `seats` per sitting: "{nice} {HH:MM}:
  {n} student(s) have a new seat." (same room, other seat); `timetable` "Made again for the timetable published on
  {nice}." when `made.published_at` differs and the new one is set. "{n} student(s) have" reads "1 student has" / "{n}
  students have"; "change(s)" likewise.
- Produces: `replace(sched, key, room, away, name, by, now) -> str` (the detail): no snapshot → "This schedule is not on
  the main site."; no approved duty (key, room) → "That duty is not on the main site."; `away` not on it → "{away} is not
  on that duty."; `name` on it → "{name} is on that duty already.". In the approved duty and in the working copy's duty
  (when present with `away` on it): `away` → `name` in place, `chief` follows, `reasons[name] = "replaces {away}, who is
  away"`, `away` leaves `backup` and `not_free`; `pins.duties["{key}|{room}"]` = the new names in both copies; log
  "replaced" with detail "{nice} {HH:MM}–{HH:MM}, {room}: {away} (away) → {name}". The route checks that `name` is free.
- Produces: `done_without(sched) -> list` (log entries with what "replaced"); `log(sched, by, what, detail, now)` appends
  `dict(at=now, by=by, what=what, detail=detail)`.

- [ ] **Step 1: Write the failing tests**:
  - `dates_read_as_on_the_page`: `D.nice("2026-10-05") == "Mon 5 Oct"`, `D.nice("2026-10-02T09:30:00") == "Fri 2 Oct"`,
    `PR._day("2026-11-01") == "Sun 1 Nov"`.
  - `states_and_labels`: `s = _mk(_made_sched())`: `AP.label(s, date(2026, 10, 1)) == "Draft"`; after `AP.send(s, _M,
    "Ms Grace Yeo", NOW, False, [])` status "waiting", `sent_by == "Ms Grace Yeo"`, label "Waiting for the timetable
    committee", `s["log"][-1]["what"] == "sent"`; after `AP.approve(s, "Timetable committee", NOW)` status "approved",
    `s["approved"]["papers"] == s["papers"]`, `s["approved"]["made"]["duties"] == s["made"]["duties"]`,
    `set(s["approved"]["made"]) == {"seats", "unseated", "duties", "published_at"}`, `AP.as_schedule(s)["id"] ==
    s["id"]`, label on 2026-10-06 "Approved · on the main site", on 2026-10-07 "Ended".
  - `send_needs_make_fresh_and_no_errors`: `AP.blocked(_made_sched(), _M, False, []) == "Press Make first."`; for a made
    one `AP.blocked(s, _M, True, []) == "The exam changed since Make: press Make again."` and `AP.blocked(s, _M, False,
    ["X."]) == "Fix the paper times first: X."`; `AP.send` raises those; an approved one with nothing changed gives
    "Nothing on the main site changes.".
  - `send_back_and_withdraw`: `AP.approve` on a draft raises "There is nothing waiting for approval."; after send,
    `send_back(s, "  ", ...)` raises "Write a note for the exams committee."; `send_back(s, "2C has a WA then", ...)`:
    status "draft", label "Sent back", note kept; send clears the note; approve; `withdraw` → `approved is None`, status
    "withdrawn", label "Withdrawn"; again → "This schedule is not on the main site.".
  - `approve_refuses_a_change_after_sending`: send, then `s["papers"][0]["minutes"] = 50`: approve raises "This schedule
    changed after it was sent. Ask the exams committee to send it again.".
  - `changes_list_what_shows`: `s = _approved()`; `MK.set_invigilators(s, "2026-10-05 07:50", "3-01", ["Ms Aisha
    Rahman", "Mr Hafiz Rahman"])` and `_mk(s, only="2026-10-05 07:50")`; then (no Make, so the 10:00 seats stay) name "Sec
    3 EOY Exam", `times.report = "07:20"`, the Pure Chemistry start "10:20": the texts are exactly ["Name: Sec 3 End-of-Year Exam → Sec 3 EOY Exam.", "Report
    time: 07:30 → 07:20.", "Sec 3 Pure Chemistry Paper 1: Mon 5 Oct 10:00–11:00 → Mon 5 Oct 10:20–11:20.", "Mon 5 Oct
    07:50, 3-01: Ms Chloe Tan → Mr Hafiz Rahman (invigilator)."].
  - `changes_list_a_moved_student`: `s = _approved()`; `MK.move(s, "2026-10-05 07:50", ["3A-07"], "3-02")`,
    `_mk(s, only="2026-10-05 07:50")`: texts == ["Mon 5 Oct 07:50, 3-02: no one → Mr Ben Ong, Mr Hafiz Rahman
    (invigilators).", "Mon 5 Oct 07:50, 3A: 3-01 → 3-01 (29), 3-02 (1).", "Mon 5 Oct 07:50: 23 students have a new
    seat."]; then send → status "changes", detail "3 changes".
  - `someone_away_goes_on_at_once`: `s = _approved()`; `AP.replace(s, "2026-10-05 07:50", "3-01", "Ms Chloe Tan", "Mr
    Hafiz Rahman", "Ms Grace Yeo", NOW)` returns "Mon 5 Oct 07:35–09:00, 3-01: Ms Chloe Tan (away) → Mr Hafiz Rahman";
    both copies' duty names == ["Ms Aisha Rahman", "Mr Hafiz Rahman"]; both pins hold them; status "approved";
    `AP.changes(s, _M) == []`; `AP.done_without(s)[0]["by"] == "Ms Grace Yeo"`; replacing "Mr Ben Ong" there raises "Mr Ben
    Ong is not on that duty."; on a draft "This schedule is not on the main site.".
- [ ] **Step 2: Run** `.venv/bin/python tests/test_exams.py` — expect an import error.
- [ ] **Step 3: Implement** `days.nice`, `exams/approval.py` (imports only `days` and `papers`), and point
  `printouts._day` at `days.nice`.
- [ ] **Step 4: Run** the tests — all pass, stage 1's included.
- [ ] **Step 5: Commit** `git add exams tests/test_exams.py && git commit -m "Exams: approval states, the approved copy, the change list"`

---

### Task 2: Other schedules count; Make on an approved schedule

**Files:**
- Modify: `exams/schedules.py`, `exams/seating.py`, `exams/invigilate.py`, `exams/make.py`
- Test: `tests/test_exams.py` (`_mk` now passes `elsewhere=[]`)

**Interfaces:**
- Consumes: `approval.as_schedule`.
- Produces: `schedules.elsewhere(id) -> list[busy]`, `busy = dict(id, name, status: "waiting" | "approved", date, start:
  int, end: int, room, names: [str])`: one per duty of every other schedule: waiting → its `made` duties; approved or
  changes → its `approved["made"]` duties (name from the copy); draft and withdrawn give none.
- Produces: `schedules.on_site() -> list[dict]`: `as_schedule` of every schedule with a snapshot.
- Produces: `schedules.new(...)` adds `scripts=""`; `_check` refuses a non-string `scripts` with the WRONG sentence
  (a missing one is "").
- Produces: `seating.rooms_free(pub, cal, sched, sitting, xset, taken, elsewhere=())`: after the lesson, rain and taken
  reasons, a room (or a related combined venue or part) in a busy overlapping [arrive, last end + stay) is busy "taken by
  {busy name} until {HH:MM}".
- Produces: `invigilate._free(..., elsewhere=())` → "is on {busy name} then ({room})" for a name in an overlapping busy;
  `candidates(..., elsewhere=())`, `assign(..., elsewhere=())` pass it to every `_free` call.
- Produces: `invigilate.recheck(pub, cal, sched, xset, duties, every, elsewhere=()) -> None`: for each duty, `not_free`
  and `backup` are worked out again for every name (as `assign` does for names chosen by hand); reasons are kept.
- Produces: `make.sitting_fp(sched, key, xset) -> str`: a hash of the sitting's papers (sorted by id), `access`,
  `seating`, `supervision`, `levels`, `classes`, the `days` entry of its date, `xset["rooms"]`, `pins.rooms[key]`, the
  `pins.duties` entries of the key, the `use_anyway` pairs of the key.
- Produces: `make.make(pub, cal, sched, xset, only=None, elsewhere=None)`: `elsewhere` None reads
  `schedules.elsewhere(sched.get("id"))`; passed to `rooms_free` and `assign`; `made["published_at"] =
  pub["meta"].get("published_at")`; `_gone` gets `keys=None` on a full Make (B12). On a full Make of a schedule with
  `approved["made"]`, every sitting key in the approved seats with `sitting_fp(sched) == sitting_fp(as_schedule(sched))`
  keeps the approved seats, unseated and duties (deep copies, passed as `fixed`, then `recheck`ed); the rest are made.

- [ ] **Step 1: Write the failing tests**:
  - `other_schedules_take_rooms_and_people`: `s = _sit([_paper(date="2026-10-05", start="07:50")], days=dict(SEC3))`,
    `busy = [dict(id="b", name="Sec 4 Exam", status="approved", date="2026-10-05", start=455, end=540, room="Hall",
    names=["Mr Hafiz Rahman"])]`: in `SE.rooms_free(..., set(), elsewhere=busy)` the Hall is "taken by Sec 4 Exam until
    09:00"; "Mr Hafiz Rahman" is in `IV.candidates(_PUB, F.CAL, s, _xset(), "2026-10-05", 455, 540, [])["free"]` and in no
    group with `elsewhere=busy`; `MK.make(_PUB, F.CAL, s, _xset(("Hall",)), elsewhere=busy)` leaves all 30 unseated.
  - `elsewhere_reads_waiting_and_approved_copies`: write to `SC.DIR` an approved schedule (working duty names ["X"],
    approved duty names ["Ms Grace Yeo"]), a waiting one, a draft and a withdrawn one; `SC.elsewhere("zzzz")` holds one
    busy each from the approved (names ["Ms Grace Yeo"], status "approved") and the waiting (status "waiting") only.
  - `make_keeps_the_published_at`: a copy of `_PUB` with `meta["published_at"] = "2026-10-01T08:00:00"` gives
    `made["published_at"] == "2026-10-01T08:00:00"`.
  - `a_full_make_clears_a_pin_of_a_vanished_sitting` (B12): `s = _mk(_made_sched())`, `s["pins"]["duties"]["2026-10-05
    09:00|3-01"] = ["Mr Gone Away"]`, `_mk(s)`: the pin is gone and `MK.gone_now(_PUB, s) == []`.
  - `approved_make_keeps_unchanged_sittings` (P2): `s = _approved()`, `x = _xset(("3-01", "3-02", "4-01", "Hall"))`,
    `x["never"] = ["Ms Aisha Rahman"]`, Pure Chemistry minutes 50, `MK.make(_PUB, F.CAL, s, x, elsewhere=[])`: the 07:50
    3-01 duty names == ["Ms Aisha Rahman", "Ms Chloe Tan"] with `not_free == {"Ms Aisha Rahman": "is on the never list"}`,
    the 07:50 seats equal the approved ones, the 10:00 3-01 duty `end == 660`; the same Make of a never-approved
    `_mk(_made_sched())` leaves "Ms Aisha Rahman" off the 07:50 duty.
  - `approved_make_after_a_new_timetable_flags_the_clash` (Review Focus 1): `pub2 = copy.deepcopy(_PUB)` with
    `F._lesson(10, 0, 2, 2, "Sec 4", ["4A"], "Science", "Entire Class", ["Ms Aisha Rahman"], "LT2")` appended; a full Make
    of `_approved()` on `pub2` keeps the 07:50 3-01 names and sets `backup == {"Ms Aisha Rahman": [10]}`.
- [ ] **Step 2: Run** the tests — expect failures.
- [ ] **Step 3: Implement** as in Interfaces (`make` may import `approval`; `approval` imports no exams module but
  `days` and `papers`).
- [ ] **Step 4: Run** `tests/test_exams.py` — all pass.
- [ ] **Step 5: Commit** `git add exams tests/test_exams.py && git commit -m "Exams: other schedules count; Make keeps what is approved"`

---

### Task 3: The approval review

**Files:**
- Create: `exams/review.py`
- Test: `tests/test_exams.py` (import `exams.review as RV`)

**Interfaces:**
- Consumes: `approval`, `make.lesson_lists`, `make.gone_now`, `papers.check`, `invigilate._free`, `days`.
- Produces: `review(pub, cal, sched, xset, elsewhere) -> dict(copy, what, checks, changes, done_without)`:
  - `copy` "approved" when status is approved (it reviews `as_schedule(sched)`), else "working" (the working copy).
  - `what = dict(classes: [str] (every class in a window on a school date, in model order), levels: [str], start, end,
    days: [dict(date, whole: bool, window: [HH:MM, HH:MM])] (school dates), papers: int, stopped: int (items of
    `lesson_lists()["none"]`), teachers: int (names on duties), duties: int, most: [name, n] | None (most duties, ties by
    name), backups: int (duty places with a backup), venues: [dict(room, dates: int, start: HH:MM, end: HH:MM)] by room,
    anyway: [dict(key, room)])`.
  - `checks`: five `dict(key, ok: bool, lines: [str])` in this order:
    `papers` ok "No student has two papers at once, and every paper is on an exam day." else the `papers.check` errors;
    `seats` ok "Every student has a seat." else "1 student has no seat." / "{n} students have no seat.";
    `free` ok "Every invigilator is free then." else, per duty name, "{name}, {room} on {nice} {HH:MM}–{HH:MM}: {why}."
    (`why` is `_free`'s reason, or "teaches {classes} {subject} {HH:MM}–{HH:MM}" for a running lesson not in the duty's
    `backup`), then "{room} on {nice} {HH:MM}–{HH:MM} is short by {n}.", then the `gone_now` sentences;
    `others` ok "No clash with other schedules." else per other schedule (by name) and date "{other} ({waiting | approved})
    takes {n} of these invigilators on {nice}." then "{other} ({…}) uses {room} on {nice} too." (overlapping busies);
    `timetable` ok "Made from the timetable on the main site now." else "The timetable changed since this was made: a new
    timetable was published on {nice(published_at)}. Ask the exams committee to make it again." when `made.published_at`
    differs from `pub["meta"].get("published_at")` (a schedule made before this stage has none, so it is flagged until
    made again; the sample has none on either side, so it passes).
  - `changes`: `approval.changes(sched, model)` when status is changes, else []. `done_without`: `approval.done_without`.

- [ ] **Step 1: Write the failing tests** (a waiting one is `_mk(_made_sched())` after `AP.send`; an approved one is
  `_approved()`):
  - `review_of_a_waiting_schedule`: `copy == "working"`; `what` has classes ["3A", "3B"], levels ["Sec 3"], papers 2,
    stopped 5, teachers 6, duties 3, most ["Mr Ben Ong", 1], backups 0, venues [dict(room="3-01", dates=1, start="07:35",
    end="11:10"), dict(room="3-02", dates=1, start="09:45", end="11:10")], anyway []; the check keys are ["papers",
    "seats", "free", "others", "timetable"], all ok, `checks[2]["lines"] == ["Every invigilator is free then."]`.
  - `review_after_a_new_timetable` (Review Focus 1): made and approved on a `_PUB` copy with published_at
    "2026-10-01T08:00:00"; reviewed on `pub2` (published_at "2026-10-02T09:30:00", lesson 10 of Task 2): `copy ==
    "approved"`, the timetable line "The timetable changed since this was made: a new timetable was published on Fri 2
    Oct. Ask the exams committee to make it again.", the free lines ["Ms Aisha Rahman, 3-01 on Mon 5 Oct 07:35–09:00:
    teaches 4A Science 08:20–09:00."].
  - `review_names_other_schedules` (Review Focus 4): `elsewhere=[dict(id="b", name="Sec 4 Exam", status="waiting",
    date="2026-10-05", start=500, end=560, room="3-01", names=["Ms Aisha Rahman", "Mr Ben Ong"])]` gives others lines
    ["Sec 4 Exam (waiting) takes 1 of these invigilators on Mon 5 Oct.", "Sec 4 Exam (waiting) uses 3-01 on Mon 5 Oct
    too."].
  - `review_counts_seats_and_short_places`: with `made["unseated"]["2026-10-05 07:50"] = ["3A-30"]` and the 07:50 duty
    `short = 1`: seats lines ["1 student has no seat."]; the free lines end with "3-01 on Mon 5 Oct 07:35–09:00 is short
    by 1.".
  - `review_of_changes_lists_them`: after Task 1's moved-student change and send, `changes` holds those three texts.
- [ ] **Step 2: Run** the tests — expect an import error.
- [ ] **Step 3: Implement** `exams/review.py` as in Interfaces.
- [ ] **Step 4: Run** the tests — all pass.
- [ ] **Step 5: Commit** `git add exams/review.py tests/test_exams.py && git commit -m "Exams: what an approval changes, and its checks"`

---

### Task 4: The approval routes and the rights helpers

**Files:**
- Modify: `app.py` (exams section), `exams/schedules.py` (`listing`)
- Test: `tests/test_exams.py`

**Interfaces:**
- Consumes: Tasks 1 to 3.
- `_exams_can_approve() -> bool` (the timetable committee: `role() == "committee"` today); `_exams_today() ->
  datetime.date` (tests replace it); `ONLY_APPROVE = "Only the timetable committee can approve, send back or withdraw."`;
  `ON_SITE = "This schedule is on the main site: the timetable committee must withdraw it before it can be deleted."`
- `EXAM_KEEPS` adds "approved", "approved_at", "approved_by", "sent_at", "sent_by", "sent_fp", "note", "log".
- `schedules.listing(today=None, published_at=None)` rows add `label`, `note`, `sent_by`, `sent_at`, `approved_at`,
  `on_site: [start, end] | None` (the approved copy's) and `retimed: bool` (waiting, approved or changes, and the copy
  the main site would read has a `made.published_at` other than `published_at`: the spec's flag after a new publish);
  `/api/exams` passes `_exams_today()` and the published meta's `published_at`. `/api/exams/me` → `{name, can_use,
  can_approve}`.
- `send` computes `stale = make.stale(s, xset)` and `errors = papers.check(s, model, cal, xset["rules"])["errors"]`.
- `_exam_review_reply(pub, s)` → JSON `{status, label, note, sent_at, sent_by, approved_at, approved_by, changed: bool
  (sent_fp set and differs from fp), can_send: str (blocked's sentence, "" when it may be sent), can_approve, unsent:
  [changes] (status approved only), review}`; `elsewhere` from `schedules.elsewhere(id)`.
- Routes (all `@need("committee", "staff")`, behind `_exams_gate`; 404 `NO_EXAM`; 400 with the ValueError sentence;
  each saves with `_save_exam` and answers `_exam_review_reply`):
  `GET /api/exams/<id>/review`; `POST /api/exams/<id>/send`; `POST /api/exams/<id>/approve`, `POST
  /api/exams/<id>/send-back` `{note}`, `POST /api/exams/<id>/withdraw` (each 403 `ONLY_APPROVE` unless
  `_exams_can_approve()`); `POST /api/exams/<id>/away` `{key, room, away, name}`: `name` must be in the freed, free or
  backups groups of `invigilate.candidates` for the approved duty (approved copy, its other duties, `exclude` the duty's
  names, `elsewhere`), else 400 "{name} is not free then."; then `approval.replace`.
- `DELETE /api/exams/<id>` → 409 `ON_SITE` while the schedule has an approved copy.
- `_exam_rooms_by_key` and `GET /api/exams/<id>/who` pass `schedules.elsewhere(id)`.

- [ ] **Step 1: Write the failing tests** (route helper `_approved_exam(c)`: `_made_exam(c)`, then `send` and `approve`
  with the committee; `_today(d)` a context manager replacing `A._exams_today`):
  - Update `only_the_committees_get_in`: `/api/exams/me` gives `dict(name="Ms Grace Yeo", can_use=False,
    can_approve=False)` and `dict(name="Timetable committee", can_use=True, can_approve=True)`.
  - `send_and_approve_by_the_right_people`: Ms Grace Yeo on the exams list sends (200, label "Waiting for the timetable
    committee"); her approve → 403 `ONLY_APPROVE`; the committee's → 200, `SC.load(id)["approved"]["made"]["duties"] ==
    SC.load(id)["made"]["duties"]`; `/api/exams` row label "Approved · on the main site" with today 2026-10-01 and `on_site
    == ["2026-10-05", "2026-10-06"]`, "Ended" with today 2026-10-07; `retimed` false, and true once the published meta
    (a copy of `_PUB` with `published_at` "2026-10-09T10:00:00") differs.
  - `send_refused_until_made_and_fresh`: send before Make → 400 "Press Make first."; after a paper change with no Make →
    400 "The exam changed since Make: press Make again.".
  - `approve_refuses_a_schedule_changed_after_sending`: send, PUT a minutes change, Make, approve → 400 "This schedule
    changed after it was sent. Ask the exams committee to send it again.".
  - `changes_wait_for_approval` (Review Focus 5): approved; PUT English start "08:00", Make: the review's `unsent` holds
    "Sec 3 English Paper 1: Mon 5 Oct 07:50–08:50 → Mon 5 Oct 08:00–09:00." and `SC.on_site()[0]` still has 07:50; send
    → status "changes" and `review.changes` holds it; send-back with "Not that day" → status "approved", note kept, still
    07:50; send again, approve → `SC.on_site()[0]` English start "08:00".
  - `withdraw_and_delete`: DELETE an approved one → 409 `ON_SITE`; withdraw → `SC.on_site() == []`, label "Withdrawn";
    DELETE → 200.
  - `put_cannot_forge_an_approval`: PUT on a draft with `status="approved"` and a forged `approved` leaves both as stored.
  - `away_on_the_main_site`: approved; away `{key: "2026-10-05 07:50", room: "3-01", away: "Ms Chloe Tan", name: "Mr
    Daniel Koh"}` → 400 "Mr Daniel Koh is not free then."; with "Mr Hafiz Rahman" → 200, `SC.on_site()[0]` duty names
    ["Ms Aisha Rahman", "Mr Hafiz Rahman"], `review.done_without[0]["detail"]` as in Task 1; on a draft → 400 "This
    schedule is not on the main site.".
- [ ] **Step 2: Run** the tests — expect failures.
- [ ] **Step 3: Implement** the helpers, constants, listing fields and routes as in Interfaces.
- [ ] **Step 4: Run** `tests/test_exams.py`, `tests/test_relief.py` and `tests/smoke.py` — all pass.
- [ ] **Step 5: Commit** `git add app.py exams tests/test_exams.py && git commit -m "Exams: send, approve, send back, withdraw, someone is away"`

---

### Task 5: The main site's exam layer, pure

**Files:**
- Create: `exams/published.py`
- Modify: `exams/days.py` (`merged_view`; `day_view` built on `_rows`)
- Test: `tests/test_exams.py` (import `exams.published as PB`)

**Interfaces:**
- Produces: `days.merged_view(pub, cal, scheds, date) -> dict(date, day, lessons)`: rows as `day_view` gives them, where a
  period stops when every class of the lesson has a window containing it in any of `scheds` (P4); `day_view` keeps its
  shape and results, built on the same `_rows(model, bnds, day, windows: {class: [(start, end)]})`.
- Produces: `published.PRINTS = ("seating", "roster-day", "roster-teacher", "timetable")`; `pos(bnds, m) -> float`
  (period position, i + fraction of period i, clamped to 0..len(bnds), rounded to 3 places).
- Produces: `day(pub, cal, scheds, date, full: bool) -> dict(date, day, exams)` with `exams = dict(classes: {class:
  [item]}, stopped: [row], shortened: [[row, HH:MM, HH:MM]], teachers: {name: [item]}, rooms: {room: [item]}, banner:
  str)`; `scheds` are `on_site()` copies; those whose dates or paper dates include `date` count. `stopped` and
  `shortened` (the running spans of rows that also stop) from `merged_view`. Class item `dict(start, end, label, room,
  seat_note, exam, p, n)` per sitting of a level or groups paper: `label` the class's papers in it joined " · ", end
  without extra time, `room` the room of most of the class's students and `seat_note` "also {rooms}" for the others —
  students with own room, reader or scribe left out (P5). Teacher item `dict(start, end, label, room, role, exam, p, n)`
  per duty name (role "Chief invigilator" for the chief, else "Invigilate"; label the sitting's papers). Room item
  `dict(start, end, label, exam, p, n)` per duty. `full=False`: `teachers == {}` and `rooms == {}`. `banner` the counted
  schedules' names joined " · ". Not a school day: `day` None and every part empty ("" banner).
- Produces: `listing(pub, scheds, today, full) -> dict(schedules, banner)`: schedules not ended, by start:
  `dict(id, name, kind, start, end, levels: {level: [dict(date, start, end, label)]})` (level and groups papers by date
  and time), and when `full` also `roster: [dict(date, start, end, room, label, names, chief)]` and `prints: [[title,
  "/api/published/exams/{id}/print/{what}.pdf"]]` (titles from `printouts.TITLES`, in `PRINTS` order). `banner`: for each
  shown schedule with `start` at most 7 days after today, "{name}: {nice start}–{nice end}." ("{name}: {nice start}." for
  one day), joined " "; None when none.
- Produces: `my_duties(pub, cal, scheds, name, today) -> dict(schedules, lessons)`: per schedule not ended where `name`
  has duties, `dict(id, name, scripts, minutes, duties: [dict(date, start, end, room, label, students: int, others: [str],
  chief: str | None (when someone else), role)])`; `lessons`: every stopped span of `name`'s lessons on those schedules'
  school dates (`merged_view`), `dict(date, start, end, classes, subject)` by date and time.
- Produces: `my_exams(pub, cal, scheds, sid, today) -> dict(schedules)`: per schedule not ended where `sid` sits a paper,
  `dict(id, name, papers: [dict(date, report, start, end, label, room, seat, note)])` by date and start; `end` with the
  student's own extra time; room and seat from the approved seats ("" when not seated); `report` = `times.report` on the
  first paper of a date whose window starts at the first period, else None; `note` "then lessons from {HH:MM}" on the last
  paper of a date whose window for the student's level ends before the school day ends, else "".

- [ ] **Step 1: Write the failing tests** (`A1 = AP.as_schedule(_approved())`):
  - `merged_view_matches_day_view`: for `_made_sched()` on 2026-10-05, `D.merged_view(_PUB, F.CAL, [s], d)["lessons"] ==
    D.day_view(_PUB, F.CAL, s, d)["lessons"]`.
  - `day_layer_from_the_approved_copy`: `e = PB.day(_PUB, F.CAL, [A1], "2026-10-05", True)["exams"]`; `day == "Odd
    Mon"`; `e["stopped"] == [0, 1, 3, 4]`, `e["shortened"] == []`; 3A's items as (start, end, label, room, seat_note) are
    [("07:50", "08:50", "Sec 3 English Paper 1", "3-01", ""), ("10:00", "11:00", "Sec 3 Pure Chemistry Paper 1", "3-01",
    "")] with the first `p == 0.5, n == 3.0`; 3B has one item in "3-02"; no "4A"; `e["teachers"]["Ms Aisha Rahman"] ==
    [dict(start="07:35", end="09:00", label="Sec 3 English Paper 1", room="3-01", role="Invigilate", exam="Sec 3
    End-of-Year Exam", p=0.0, n=4.0)]`; `set(e["rooms"]) == {"3-01", "3-02"}`; `e["banner"] == "Sec 3 End-of-Year Exam"`.
  - `student_code_sees_no_names_or_duty_rooms` (Review Focus 2): with `_approved(access=[dict(student="3A-05", extra=25,
    own_room=True, reader=False, scribe=False, note="")], rooms=(... , "3-11"))`, `full=False` gives `teachers == {}`,
    `rooms == {}`, 3A's first item room "3-01" and seat_note "", and "3-11" nowhere in `json.dumps` of the answer.
  - `not_a_school_day_is_empty` (Review Focus 3): 2026-10-12 and 2026-12-01 give `day is None` and `exams ==
    dict(classes={}, stopped=[], shortened=[], teachers={}, rooms={}, banner="")`.
  - `two_approved_schedules_on_one_date` (Review Focus 4): B = `SC.new("exam", "Sec 4 Exam", ["Sec 4"], "2026-10-05",
    "2026-10-05", ...)`, 4A English `who="level"` at 07:50, made (`elsewhere=[]`; Task 2 tests the taking), sent,
    approved: the day for [A1, B1] has `stopped == [0, 1, 2, 3, 4, 5, 6, 7, 8]` (row 8, 3A with 4A, stops only with
    both), classes 3A, 3B and 4A, banner "Sec 3 End-of-Year Exam · Sec 4 Exam" (schedules by start, then name).
  - `unsent_changes_stay_off_the_main_site` (Review Focus 5): `s = _approved()`, English start "08:00", full Make: the
    day, `listing` and `my_exams` for 3A-07 all still say 07:50.
  - `published_listing_and_banner`: on 2026-10-01 `levels["Sec 3"] == [dict(date="2026-10-05", start="07:50",
    end="08:50", label="Sec 3 English Paper 1"), dict(date="2026-10-05", start="10:00", end="11:00", label="Sec 3 Pure
    Chemistry Paper 1")]`; `roster[0] == dict(date="2026-10-05", start="07:35", end="09:00", room="3-01", label="Sec 3
    English Paper 1", names=["Ms Aisha Rahman", "Ms Chloe Tan"], chief=None)`, 3 roster rows; `prints[0] == ["Seating
    plan", f"/api/published/exams/{A1['id']}/print/seating.pdf"]`; banner "Sec 3 End-of-Year Exam: Mon 5 Oct–Tue 6 Oct.";
    `full=False` rows have no "roster" or "prints"; 2026-09-27 → banner None; 2026-10-07 → `schedules == []`.
  - `a_teachers_duties`: Ms Aisha Rahman → one schedule, `minutes == 85`, duties [dict(date="2026-10-05",
    start="07:35", end="09:00", room="3-01", label="Sec 3 English Paper 1", students=30, others=["Ms Chloe Tan"],
    chief=None, role="Invigilate")], lessons [dict(date="2026-10-05", start="07:40", end="08:20", classes=["3A"],
    subject="English")]; Mr Ivan Lee's lessons are [dict(date="2026-10-06", start="07:40", end="08:20", classes=["3A"],
    subject="English")].
  - `a_students_papers`: 3A-07 → papers [dict(date="2026-10-05", report="07:30", start="07:50", end="08:50", label="Sec 3
    English Paper 1", room="3-01", seat="B1", note=""), dict(date="2026-10-05", report=None, start="10:00", end="11:00",
    label="Sec 3 Pure Chemistry Paper 1", room="3-01", seat="B1", note="")]; 3B-15 → `schedules == []`; 3A-05 with the
    access arrangement → English room "3-11", seat "A1", end "09:05"; `_approved(papers=[the English paper],
    days={"2026-10-05": dict(levels=["Sec 3"], whole=False, **{"from": "07:40", "to": "09:00"})})` gives 3A-07's paper
    report "07:30" and note "then lessons from 09:00".
- [ ] **Step 2: Run** the tests — expect failures.
- [ ] **Step 3: Implement** `days.merged_view`/`_rows` and `exams/published.py` as in Interfaces.
- [ ] **Step 4: Run** the tests — all pass, stage 1's `day_view` tests unchanged.
- [ ] **Step 5: Commit** `git add exams tests/test_exams.py && git commit -m "Exams: the main site's exam layer"`

---

### Task 6: The main-site routes

**Files:**
- Modify: `app.py` (`TABS`, `/timetable`, `/me`, new routes after the exams routes)
- Test: `tests/test_exams.py` (helper `as_role(role, **session)` sets the session through `session_transaction`)

**Interfaces:**
- `_published_reader() -> "full" | "student" | None`: committee, head, teacher, staff → "full"; student → "student".
- Constants: `BAD_DATE = "Give a date such as 2026-10-05."`, `NO_DAY_CAL = "The school calendar is not set yet, so the
  timetable cannot be shown on a date."`, `ONLY_STAFF_PRINTS = "Only staff can open the seating plans and rosters."`
- `TABS["teacher"]` and `TABS["student"]` gain "exams"; `/timetable` adds `dates=True, exams=True` to its app config;
  `/me` adds `exams=True`. The cache key does not change (the config is the same for each role).
- Routes:
  - `GET /api/day?date=` `@need("committee", "head", "teacher", "student", "staff")` → `published.day(pub, cal,
    schedules.on_site(), date, full=reader == "full")`; 409 `NO_EXAMS_PUB` with nothing published, 400 `BAD_DATE`, 409
    `NO_DAY_CAL` when the calendar has no terms.
  - `GET /api/published/exams` (same roles) → `published.listing(pub, on_site(), _exams_today(), full)`.
  - `GET /api/published/exams/<id>/print/<what>.pdf` (same roles): 403 `ONLY_STAFF_PRINTS` unless "full", 404 for a
    `what` outside `PRINTS` or no approved copy; `printouts.pdf(what, pub, cal, as_schedule(s), xset, buf)`, inline, named
    as stage 1's prints.
  - `GET /api/exams/my-duties` `@need("committee", "staff")` → `published.my_duties(pub, cal, on_site(), name,
    _exams_today())` with `name` from `_exams_rights(pub)` (401 when None); open to any staff member (only their own).
  - `GET /api/me/exams` `@need("personal")` → `published.my_exams(pub, cal, on_site(), session sid, _exams_today())`;
    401 "Please sign in again." when the sid is not among the published students.

- [ ] **Step 1: Write the failing tests** (`_approved_exam` from Task 4; `_today(date(2026, 10, 1))`):
  - `day_for_staff_and_for_the_student_code` (Review Focus 2): the committee's `/api/day?date=2026-10-05` has `day ==
    "Odd Mon"`, `stopped == [0, 1, 3, 4]` and Ms Aisha Rahman in teachers; `as_role("student")` gets the same classes,
    `teachers == {}`, `rooms == {}`; `as_role("personal", sid="3A-07")` → 401.
  - `day_refuses_bad_dates` (Review Focus 3): 2026-10-12 → 200 with `day is None`; `date=05-10-2026` and no date → 400
    `BAD_DATE`; an empty calendar → 409 `NO_DAY_CAL`.
  - `published_exams_and_prints`: `as_role("teacher")` gets roster and prints, banner "Sec 3 Exam: Mon 5 Oct–Tue 6 Oct.";
    `as_role("student")` gets neither; the teacher's `print/seating.pdf` → 200 `%PDF`, the student's → 403
    `ONLY_STAFF_PRINTS`, `print/doors.pdf` → 404; after a working-copy change and Make, the staff roster is unchanged.
  - `my_duties_and_my_exams`: `as_role("staff", who="Ms Aisha Rahman")` (not on the exams list) gets her 3-01 duty from
    `/api/exams/my-duties`; the committee gets `schedules == []`; `as_role("personal", sid="3A-07")` gets seat "B1" from
    `/api/me/exams`.
  - `timetable_and_me_ask_for_exams`: with `ttgen.export.render_html` replaced as in `tests/test_relief.py` (the stand-in
    also takes `student_id`), `/timetable`
    for a teacher passes `dates is True`, `exams is True` and "exams" in `tabs`; `/me` passes `exams is True`.
- [ ] **Step 2: Run** the tests — expect failures.
- [ ] **Step 3: Implement** as in Interfaces.
- [ ] **Step 4: Run** `tests/test_exams.py`, `tests/test_relief.py`, `tests/test_parents.py` and `tests/smoke.py` — all pass.
- [ ] **Step 5: Commit** `git add app.py tests/test_exams.py && git commit -m "Exams: the main site's routes"`

---

### Task 7: The published page: a date, the banner, the Exams tab, My exam timetable

**Files:**
- Modify: `ttgen/timetable_page.html`, then copy to `skill/school-timetable-generator/scripts/ttgen/timetable_page.html`
- Test: `tests/test_exams.py` (source words), `node --check` on the extracted script; the browser check is the
  controller's

**Interfaces:**
- Consumes: `APP.dates`, `APP.exams`, `/api/day`, `/api/published/exams`, `/api/me/exams` (Task 6 shapes).
- `L` rows gain `i` (their index in `D.lessons`, the published model's row); `cellOf` keeps `ix: xs.map(x => x.i)`.
- **The date choice** (only when `APP.dates`): in the header before `#theme`, `<input type="date" id="onDate"
  aria-label="Show the timetable on a date">` and a button "Usual timetable" (shown while a date is chosen).
  `pickDate(iso)` fetches `/api/day?date=`; `S.on` holds the answer (null for the usual timetable); an error answer shows
  its sentence in a line above the view; then the current tab is drawn again.
- `dated(v)` (Classes, Teachers, Rooms, Students and the builder; called in `show` and the builder's update when `S.on`):
  with `S.on.day` null the view's grid is replaced by "Not a school day." and "{Mon 12 Oct} is outside the terms or a
  holiday in the school calendar."; else `v.only` = the index of `S.on.day` in `DAYS`, cells of other days dropped, a cell
  whose every `ix` is in `stopped` gets `x` (crossed), a shortened one gets the line "runs {from}–{to} only", and exam
  cells are added from `classes[v.key]` (a student: their class), `teachers[v.key]` or `rooms[v.key]`, each `{d, p, n,
  title, lines, exam: true}`: class title the label, lines room, times, seat_note; teacher title "{role} · {room}", lines
  label, times; room title "Exam", lines label, times. Above the grid: "On {Mon 5 Oct} ({Odd Mon}): {banner}. Lessons
  that don't happen are crossed out." or, with no exams, "On {Mon 5 Oct} ({Odd Mon}): no exams or tests. This is the
  usual {Odd Mon} timetable." The PDF, CSV, Lessons and Checks stay the usual timetable.
- `gridHTML` draws only row `v.only` when it is set, and adds the classes `x` and `exam` to cells. CSS: `.cell.x`
  (faded, title and lines struck through), `.cell.exam` (purple `#6b3fa0` family, both themes), `.datepick`.
- **Who's free on a date**: with `S.on.day`, the day select gives way to the date line, lessons in `stopped` do not make
  anyone or anything busy, teacher and room exam items overlapping the chosen periods do, and classes with a class item
  then are not "with no lesson"; the count line adds "Duties and exam rooms count as busy; lessons that don't happen do
  not."
- **Banner and Exams tab** (only when `APP.exams`): `TABS_ALL` gains `["exams", "Exams", ""]`; the page fetches
  `/api/published/exams` once at load; a banner (after the header, as `APP.banner`) shows its `banner` plus a link "See
  Exams" to `#exams`. `renderExams()` (wide, hash `#exams`): per schedule the name, "Exam"/"Common test" and dates, per
  level a table Date | Time | Paper; with `roster`, "Roster by day" (Date | Time | Room | Paper | Invigilators, the chief
  marked "(chief)") and the `prints` as buttons opening in a new tab; none: "No exams or tests on the main site now."
- **My exam timetable** (personal mode, when `APP.exams`): `showPersonal` fetches `/api/me/exams` and, when it has
  papers, puts a card "My exam timetable" above the timetable: per schedule its name, a row per paper "{Mon 5 Oct}"
  (+ " · report {07:30}"), label, "{start}–{end}", room, "Seat {seat}", note. Nothing shows when there are none.

- [ ] **Step 1: Write the failing test** `the_published_page_has_the_date_choice`: the page source holds "Usual
  timetable", "Not a school day.", "Lessons that don't happen are crossed out.", "See Exams", "No exams or tests on the
  main site now.", "My exam timetable", "Roster by day", "/api/day?date=", "/api/published/exams", "/api/me/exams",
  ".cell.x", ".cell.exam", " only", "Duties and exam rooms count as busy; lessons that don't happen do not."; it equals
  the skill copy byte for byte.
- [ ] **Step 2: Run** the test — expect a failure.
- [ ] **Step 3: Implement** the page changes above, one statement per line where new code allows it.
- [ ] **Step 4: Run** the script check of Global Constraints (no output), copy to the skill path, `cmp` (no output), and
  `tests/test_exams.py` and `tests/smoke.py` — all pass.
- [ ] **Step 5: Commit** `git add ttgen/timetable_page.html skill/school-timetable-generator/scripts/ttgen/timetable_page.html tests/test_exams.py && git commit -m "Published page: the timetable on a date, the exams banner and tab, my exam timetable"`

---

### Task 8: The exams pages: statuses, Approval, Someone is away, My exam duties

**Files:**
- Modify: `static/exams.js`, `static/exams.html`, `static/app.js`
- Test: `tests/test_exams.py` (source words), `node --check`; the browser check is the controller's

**Interfaces:**
- Consumes: `/api/exams` rows (Task 4), `/api/exams/me`, `/api/exams/<id>/review`, `send`, `approve`, `send-back`,
  `withdraw`, `away`, `/api/exams/my-duties`.
- **List** (mockup tab 1): the chip shows `label` (classes draft, waiting, approved, ended, withdrawn); under the name:
  "Sent back: “{note}”" (draft) or "Changes sent back: “{note}”" (approved), "sent by {sent_by}, {date}" (waiting,
  changes), "on the main site {start} to {end}" (approved), and "The timetable changed since this was made." when
  `retimed`.
- **My exam duties**: `startList` asks `/api/exams/me` first; without `can_use` the page shows only "My exam duties"
  (no 403 sentence, a link back to Relief); with it, the same section above the list when there are duties. Per
  schedule: rows "{Mon 5 Oct} · {start}–{end}" | "{role} {room} · {label} · {n} students" | "with {others}" · "chief:
  {chief}" · "scripts to {scripts}" (each only when set); "Lessons that don't happen: {Mon 5 Oct} {start} {classes}
  {subject} · …"; "{n} duties · {fmtLen} this exam" ("1 duty"). None: "You have no exam duties on the main site."
- **Editor**: the status chip beside the name; with an approved copy the notice "On the main site. Changes you make here
  wait for the timetable committee: send them from the Approval tab."; What and when gains "Scripts go to" (text,
  `scripts`, placeholder "the staff room").
- **Approval tab** (key "approval", after Lessons), from `/review` on opening and after every action: the status and
  the note ("Sent back by the timetable committee: “{note}”"); for everyone: "Send to the timetable committee" (draft,
  withdrawn), "Send again" with "Changed since you sent it: send it again." (waiting or changes and `changed`), "Changes
  not sent yet" with `unsent` and "Send the changes" (approved), each disabled with `can_send`'s sentence when set, and
  "Nothing on the main site has changed since it was approved." for approved with no `unsent`; "What changes on the main
  site": "Classes {classes} ({levels}) · {papers} papers · {whole days | part of the day | whole days, part day on
  {dates}}", "Lessons that won't happen: {stopped} (no relief needed)", "Teachers with duties: {teachers} · {duties}
  duties · most: {name}, {n}", "Backups for the relief team: {backups} (sending them comes in a later stage)", "Venues
  taken: {room} {start}–{end} on {n} day(s); …", "Rain rooms used anyway: …" (when any); "Checks" with ✓ for ok and ● for
  each line of a failed check. For `can_approve`: "Approve: show on the main site" (waiting), "Changes waiting for you"
  and "Approve the changes" (changes), "Send back with a note" (a text box and "Send back"), "Withdraw from the main
  site" (approved, changes; `confirm("Take {name} off the main site now?")`). "Done without approval": "{detail} · by
  {by}, {Mon 5 Oct} {HH:MM}". A refusal shows the server's sentence.
- **Someone is away** (Who could take it panel, when the schedule has an approved copy): "Who is away" (the duty's
  names), "Who takes it" (the Freed, Free then and Backup names), "Replace now" → `away`; then "{name} takes the duty on
  the main site now. The timetable committee sees it under Done without approval."
- **Committee page** (`static/app.js`, beside `#examsLink`): "Exams · {n} waiting" when rows have status waiting or changes.

- [ ] **Step 1: Write the failing test** `the_exams_pages_carry_the_approval_words`: `exams.js` holds "Approval", "Send to
  the timetable committee", "Send again", "Send the changes", "Approve: show on the main site", "Approve the changes",
  "Send back with a note", "Withdraw from the main site", "Done without approval", "Someone is away", "Replace now", "My
  exam duties", "You have no exam duties on the main site.", "Scripts go to", "On the main site. Changes you make here wait
  for the timetable committee: send them from the Approval tab."; `app.js` holds " waiting".
- [ ] **Step 2: Run** the test — expect a failure.
- [ ] **Step 3: Implement** the page changes above (look and feel as stage 1, mockup tabs 1 and 10).
- [ ] **Step 4: Run** `node --check static/exams.js` and `node --check static/app.js` (no output) and `tests/test_exams.py`.
- [ ] **Step 5: Commit** `git add static tests/test_exams.py && git commit -m "Exams pages: statuses, approval, someone is away, my exam duties"`

---

### Task 9: Finish

**Files:**
- Create: `docs/superpowers/plans/2026-11-21-exams-stage-2-notes.md` (the brief's decisions B1–B13 and this plan's
  P1–P11 as rulings, rulings made during the build, what was checked, what was not tried, points for stage 3)
- Modify: `README.md` (one line in the Exams and events section: approval by the timetable committee and what the main
  site shows)
- Delete: `docs/superpowers/plans/stage-2-brief.md` once its decisions are in the notes (`git rm` when it was committed,
  else a plain delete)

- [ ] **Step 1: Run every suite** on the final code, one after another: `.venv/bin/python tests/<name>.py` for every
  `tests/*.py` (test_exams, test_relief, test_ask, test_board, test_choices, test_combined, test_fixes, test_helper,
  test_parents, test_rules, test_sync, test_teachers, test_typed, test_venues, test_verify, smoke); `node tests/*.test.js`
  one by one; `node --check static/app.js static/exams.js static/exams-settings.js` and the page script check; then
  `--full` for test_typed (alone), test_helper, test_fixes and smoke. All pass, or a failure is shown to fail on main.
- [ ] **Step 2: `cmp`** the two `timetable_page.html` copies, and `for f in ttgen/*.py; do cmp -s "$f"
  "skill/school-timetable-generator/scripts/$f" || echo "differs: $f"; done` — no output.
- [ ] **Step 3: The school's real published timetable, counts only** (the file stage 1 used; scratch data folder deleted
  afterwards; nothing printed but counts and times): a Sec 1–3 exam over one made-up week, one paper per level a day, made,
  sent and approved; report per date of `/api/day` the stopped rows, class items and teacher items (full and student
  code), the published list's roster rows, `my_duties` for the teacher with most duties (as a count), the time of one
  `/api/day` and one `/api/published/exams` answer, and the review's five checks as ok or not. When the timetable has no
  students, seat made-up students per class size as stage 1 did and say so.
- [ ] **Step 4: Check the branch's commits** hold no real staff or student name and not the school's full name
  (`git log -p origin/main..HEAD` searched for every teacher name of the real timetable, reported as a count).
- [ ] **Step 5: Write the notes and the README line**, remove the brief; commit `git add -A docs README.md && git commit
  -m "Exams stage 2: notes"`. The browser check is the controller's.

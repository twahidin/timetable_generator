# Relief stage 3: the relief team's module — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every lesson that needs cover gets a relief teacher picked for it — the planner's choice, or the AI's pick by
the school's written rules from a labelled shortlist, checked by the app, with the app's own order when the AI is not
available — and nothing reaches the relief teacher until someone on the relief team approves it on the **Today** page;
the relief teacher sees it in **Reliefs I'm covering**, acknowledges it or asks to change; the team has a **load
tracker**, and What's in gains "Needs a nudge" and each absence's relief status.

**Architecture:** Three new modules in `relief/`: `cover.py` (the state of each lesson's cover inside the absence
records: picked, approved, acknowledged, asked to change, split at a period boundary; every change under the absences
lock), `pick.py` (the app's own order, the labelled shortlist, the model call with its own usage guard, the checks and
the fallback) and `fill.py` (when picks are due, filling them outside the lock and saving only if still valid, a
background thread for "at once", and a one-minute ticker switched on only on Railway). New routes join the stage 2
blueprint `relief/web.py`; the pages gain `static/relief-today.js`, `static/relief-covering.js` and
`static/relief-load.js`.

**Tech Stack:** Python 3 / Flask (one gunicorn worker, 8 threads), the `anthropic` SDK as `typed.py` uses it, plain
JavaScript, plain-assert test scripts.

**Spec:** `docs/superpowers/specs/2026-11-20-relief-module-design.md` (approved 20 Nov 2026): "Module 2. Relief team",
"The AI's pick (approach B)", "Load", "Module 1 … Reliefs I'm covering", "What is kept", "Stages" item 3. Mockups: tabs
5, 6, 7 and 9 of `docs/superpowers/specs/2026-11-20-relief-module-mockups.html`. Stage 2's notes:
`2026-11-21-relief-stage-2-notes.md` ("For stage 3 and later").

**Branch:** `relief-stage-3`, cut from `relief-stage-2` (stage 2 is PR-open, not merged; rebase onto main once it
merges), with this plan committed first.

## Decisions taken in this plan (the lead may change any)

1. **The published timetable on a date is a stage of its own (3b), after exams stage 2 (PR #81) merges.** Exams stage 2
   already gives the published page its date choice (`/api/day`, the "Usual timetable" button, crossing out lessons that
   do not happen). Relief's part — the relief teacher's RELIEF lessons, the class showing the relief teacher, the absent
   teacher's lessons crossed out with who covers each, Who's free counting reliefs and absences — adds to that same
   mechanism, so it is planned once PR #81 is on main.
2. **No Telegram yet (stage 4).** Approve puts the relief in the relief teacher's **Reliefs I'm covering** at once; the
   Telegram message, Remind, the 15-minute report and the weekly summary come with the bot in stage 4. The Today page
   says "Approved: they see it in Reliefs I'm covering."
3. **Change is choose-and-approve in one press.** The team member who picks someone in Change is the approval; the
   person picked sees it at once.
4. **The absent teacher and the planner see a relief teacher's name only once it is approved.** Before that the lesson
   reads "The relief team will assign" (or, for the planner's own choice, "Planned: {name}, waiting for the relief
   team").
5. **Timed picks run inside the app**, in one background thread, switched on by `RELIEF_JOBS=on`, which the Dockerfile
   sets; local runs and tests never start it. A restart loses nothing: the next minute's tick finds every pick still due.
6. **The AI's budget:** at most 60 picks by the model in any 10 minutes for the whole server; past that, and whenever
   the model fails, the app's own order, saying so.
7. **The model** is the one the app already uses for typed requests (`ANTHROPIC_API_KEY`, `TYPED_REQUEST_MODEL`);
   `TYPED_REQUEST_MODEL=mock` gives a built-in practice picker with no network (for the sample and the browser check).
   With no key, every pick is the app's own order.
8. **A split is undone with "Join again"** while no part of the lesson is approved.

**Meeting exams stage 3** (built in another session on top of `relief-stage-2`, PR not open yet): it adds `links=None`
to `free.free_then`, `free.there_then` and `free.week_so_far`, a `links=None` keyword and a "takeover" (lessons moved
from an exams backup record to the teacher's own absence, with the chosen relief and work) inside `absences.new`, and
`from_exams`, `exams_records`, `cancel_exams`. Whichever branch merges second must make the takeover carry the cover
fields (`pick`, `approved`, `ack`, `change`, `history`, `parts`) and pass `links` from `pick.shortlist` to `free_then`.

## Global Constraints

- The repo is public: the school is only ever "CTSS"; tests, samples and docs use made-up names only.
- Never print, log or commit a real code, key or token. Tests make random codes with `secrets.token_hex`.
- **No real model call anywhere in tests or checks.** Tests inject `call=`; the browser check uses
  `TYPED_REQUEST_MODEL=mock`. No Telegram in this stage.
- **Nothing sent to the model carries a name, an absence reason, work, remarks or a file.** Teachers are "Teacher {n}";
  names in the rules text become the same labels, or "another teacher".
- **Nothing reaches a relief teacher before a relief team member approves it** (Reliefs I'm covering lists approved
  covers only).
- **The page never waits on the model.** Picks run in the background; the Today page shows "Being picked" and refreshes.
- Tests are plain-assert scripts run as `.venv/bin/python tests/<name>.py`, with `DATA_DIR` set to a fresh temp folder
  before `import app` (as `tests/test_relief_requests.py` does). Reuse `relief.people.fake_pub`. `RELIEF_JOBS` is never
  set in tests.
- Every write of an absence record goes through `absences._LOCK` (not re-entrant) and `store.write_json`; no model call
  is ever made while holding it.
- "Today" and "now" are school time: `relief.lessons.today()`, `relief.absences._now()` (`SCHOOL_TZ`, default
  Asia/Singapore). Lesson times come from `exams.days.bounds` (the published `times` are a 12-hour clock without am/pm).
- Periods are 0-based in the data and shown `P{p+1}`; a cover of `n` periods shows `P{p+1}–P{p+n}` with its times.
- Right names (shared with the accounts work): `relief`, `relief.plan`, `relief.team`, `relief.settings`, `relief.save`.
  Stage 3 adds no new right name: the relief teacher's routes check `relief` plus "this cover is yours".
- The absence reason is shown only to the absent teacher, the planner, management and the relief team; never to a relief
  teacher, never in Reliefs I'm covering, never to the model.
- Copy is plain words in the app's style; the exact sentences below are used verbatim. Dates in sentences read
  "Sat 17 Oct".
- Builders and reviewers: NEVER run `git stash`, `git stash pop` or `git checkout -- <file>`; `git stash list` unchanged
  after each task. In `static/*.js`, never a `//` comment in the middle of a long line; use `/* */`.
- Every commit ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`, written with a quoted heredoc.

Exact sentences:

| Name | Text |
|---|---|
| `NOT_FREE` | `{name} is no longer free then. Choose someone else.` |
| `NOBODY` | `Nobody is free then.` |
| `APP_ORDER` | `Picked by the app's own order: the AI was not available.` |
| `PLANNED` | `Planned by {by} on {Sat 17 Oct}.` |
| `NOT_YOURS_COVER` | `This relief is not yours.` |
| `NOT_WAITING` | `This relief is not waiting for approval.` |
| `NO_SPLIT` | `A lesson of one period cannot be split.` |
| `SPLIT_SENT` | `Part of this lesson is approved already, so it cannot be joined again.` |
| `CHANGE_WHY` | `Say in a line why you cannot take it.` |
| `TEAM_ONLY` | as stage 2 |

## Review Focus

1. **Two absences arrive together and both picks name the same free teacher** for overlapping periods: the second save
   re-checks and picks again, so nobody is given two places at once. (Task 3.)
2. **A pick goes stale** (the picked teacher asks for relief themselves, or is given an overlapping relief by Change):
   a waiting pick is dropped and picked again by the next run; Approve refuses with `NOT_FREE` naming them; "Approve
   all waiting" skips it and says so; an approved one shows "{name} is no longer free then: change it". (Tasks 1, 3, 4.)
3. **The model answers with a label not on the shortlist, an empty reason, a real name, or nothing** (or times out, or
   the guard is full): the app's own order is used with `APP_ORDER`, and no exception reaches a route. (Task 2.)
4. **An absence is cancelled, or a lesson marked not needed, after its relief was approved**: the relief leaves Reliefs
   I'm covering and stops counting as load; a request to change on it is closed. (Task 1.)
5. **A record written by stage 2** (planner's `relief` set, no cover state): it reads as "waiting" with the reason
   `PLANNED`, and Approve works on it. (Task 1.)

---

## File structure

| File | What it is |
|---|---|
| `relief/cover.py` | covers of a lesson (whole or split), their state, every change by the team or the relief teacher |
| `relief/pick.py` | the app's own order, the labelled shortlist, the model call and its guard, checks, fallback |
| `relief/fill.py` | when a pick is due; filling one absence, a date, or everything due; the background thread; the ticker |
| `relief/free.py` | counts relief periods by cover (split parts too) and skips covers no longer counting |
| `relief/absences.py` | `not_needed`, `cancel`, `choose` clear or set cover state through `cover.py` |
| `relief/web.py` | Today, approve, approve all, change, split, join, keep, fill now; covering, acknowledge, ask to change; load tracker; What's in additions; files for the relief teacher |
| `app.py` | starts the ticker when `RELIEF_JOBS=on`; `/api/relief/me` unchanged |
| `Dockerfile` | `ENV RELIEF_JOBS=on` |
| `static/relief.html`, `static/relief.js` | two new tabs (Today for the team, Reliefs I'm covering for everyone), Load for the team |
| `static/relief-today.js` | the Today page |
| `static/relief-covering.js` | Reliefs I'm covering |
| `static/relief-load.js` | the load tracker |
| `static/relief-inbox.js` | "Needs a nudge" view, relief status per absence, the next-stage line removed |
| `tests/test_relief_team.py` | every server test of this stage |
| `README.md`, `DEPLOY.md` | what stage 3 adds; what is sent to the model (labels only) and `RELIEF_JOBS` |

---

### Task 1: The cover of a lesson and its state

**Files:**
- Create: `relief/cover.py`
- Modify: `relief/free.py` (`relief_periods`, `_chosen_then`), `relief/absences.py` (`not_needed`, `needed_again`,
  `choose`, `cancel`)
- Test: `tests/test_relief_team.py`

**Interfaces:**
- Consumes: `absences._LOCK`, `absences.load`, `absences._save`, `absences.all_records`, `absences._lesson`,
  `absences._past`, `free.free_then`, `free.there_then`, `lessons.today`, `absences._now`.
- Produces:
  - `covers(x) -> list[dict]`: `x["parts"]` when the lesson is split, else `[x]`; each cover has `p`, `n` and the cover
    fields below, read with `.get` (stage 2 records have none).
  - Cover fields: `relief` (name or None, as stage 2), `relief_by`, `pick` (None or `dict(who, by, reason, at)`, `by` in
    `"planner"|"ai"|"app"|"team"`), `approved` (None or `dict(by, at)`), `ack` (None or `dict(at)`), `change` (None or
    `dict(why, at, pick)`; `pick` as above or None while being picked), `history` (list of `dict(what, who, by, at,
    why)`, `what` in `"pick"|"dropped"|"approved"|"changed"|"acknowledged"|"asked to change"|"kept"|"split"|"joined"`;
    every pick ever made, with its reason, stays here).
  - `state(record, x, c) -> str`: `"cancelled"` (absence cancelled or lesson not needed), `"open"` (no relief),
    `"waiting"` (relief set, not approved), `"approved"`, `"acknowledged"`, `"change"` (approved, asked to change).
    A stage 2 record with `relief` set and no `pick` reads as `"waiting"` with
    `pick = dict(who=relief, by="planner", reason=PLANNED, at=record["at"])`.
  - `cover_key(x, i) -> str`: `x["key"]` for a whole lesson, `f'{x["key"]}#{i}'` for part `i`.
  - `find(record, ckey) -> (lesson, cover)` raising `ValueError(CHANGED)` when gone.
  - `set_pick(id, ckey, pick, pub, settings, *, into="pick") -> record`: saves a pick (and `relief=pick["who"]`) only if
    the cover is still open (for `into="change"`: still asked to change with no new pick yet) and the person still free
    (`still_free`); else raises `ValueError(NOT_FREE)`.
  - `drop(id, ckey, why) -> record`: a **waiting** pick whose person is no longer free goes back to open (history
    `"dropped"`); an approved one is never dropped.
  - `stale(pub, settings, records, record, x, c) -> bool`: the cover's relief is set and that person is no longer free
    then (teaching, away, given an overlapping relief, or on the "never" list since).
  - `still_free(pub, settings, records, record, x, c, who) -> bool`: `who` is in `free.free_then(...)` for that cover's
    periods, ignoring this cover itself.
  - `approve(id, ckey, by, pub, settings) -> record`; `approve_all(date, by, pub, settings) -> dict(approved=int,
    skipped=[dict(ckey, name, why)])`; `change(id, ckey, who, by, pub, settings) -> record` (choose and approve);
    `split(id, key, at, by) -> record` (`at` = period index strictly inside the lesson; parts open; refused with
    `NO_SPLIT` for `n == 1` or when anything in the lesson is approved); `join(id, key, by) -> record` (refused with
    `SPLIT_SENT`); `keep(id, ckey, by) -> record` (closes a change request, relief stays);
    `acknowledge(id, ckey, me) -> record`, `ask_change(id, ckey, why, me) -> record` (both refused with
    `NOT_YOURS_COVER` unless `me` is the approved relief; `ask_change` needs a line, `CHANGE_WHY`).
  - Approving a cover with an open change request gives the relief to `change.pick.who` (re-checked with `still_free`).
  - Every action on a cover whose lesson has ended is refused with stage 2's `PAST_LESSON`.

- [ ] **Step 1: Write the failing tests** in `tests/test_relief_team.py` (copy the header of
  `tests/test_relief_requests.py`; fix "today" at Mon 12 Oct 2026 as it does). Name them:
  `a_stage_2_record_reads_as_waiting_with_the_planned_reason`, `approve_makes_it_approved_and_records_who`,
  `approve_refuses_someone_no_longer_free` (the picked teacher asks for relief for that date first → `NOT_FREE` with
  their name), `approve_all_skips_the_stale_and_counts_the_rest`, `change_chooses_and_approves_in_one`,
  `split_at_a_boundary_gives_two_open_parts_and_join_undoes_it`, `split_refused_for_one_period_and_after_approval`,
  `the_relief_teacher_acknowledges_and_asks_to_change_only_their_own`,
  `approving_a_change_request_moves_it_and_keep_leaves_it`, `cancel_and_not_needed_end_the_cover_and_its_load`
  (`free.relief_periods` drops it; the change request closes), `relief_periods_counts_split_parts_by_their_own_n`,
  `actions_on_an_ended_lesson_are_refused`.
- [ ] **Step 2: Run** `.venv/bin/python tests/test_relief_team.py` — expected: fails, `relief.cover` missing.
- [ ] **Step 3: Implement** `relief/cover.py` with the interface above; change `free.relief_periods` and
  `free._chosen_then` to walk `cover.covers(x)` (each part counts its own `n`, cancelled and not-needed never count);
  make `absences.not_needed` and `cancel` clear `pick`, `approved`, `ack`, `change` with `relief`; make
  `absences.choose` store `pick=dict(who, by="planner", reason=PLANNED, at=now)`.
- [ ] **Step 4: Run** the new file and `tests/test_relief_requests.py`, `tests/test_relief.py` — all pass.
- [ ] **Step 5: Commit** "Relief: the cover of a lesson: picked, approved, acknowledged, asked to change, split".

### Task 2: The pick: the app's own order and the AI's, checked

**Files:**
- Create: `relief/pick.py`
- Test: `tests/test_relief_team.py`

**Interfaces:**
- Consumes: `free.free_then`, `people.people`, settings (`rules`, `limits`, `fat_role`), `typed.enabled()`,
  `typed.model()`, `typed._client()`, `cover.covers`, `cover.state`.
- Produces:
  - `shortlist(pub, settings, records, record, x, c) -> list[dict]`: the `free_then` people for the cover's periods
    with `over` people removed, each with its group index `g` (0 same department and teaches the subject, 1 same
    department, 2 other departments).
  - `app_order(short) -> list[dict]`: Flexi Adjunct Teachers first, then everyone else; inside each, sorted by
    `(g, bool(marks), week, term, name)`.
  - `labelled(short, record, x, c, settings, people) -> dict(lesson, teachers, rules, limits)` and the map
    `{label: name}`; labels `"Teacher {i}"` from 1 in `app_order`. Per teacher: `label`, `departments`, `subjects`,
    `teaches_this_subject`, `flexi_adjunct`, `teaching_this_week`, `relief_this_week`, `relief_today`,
    `relief_this_term`, `relief_today_at` (list of `"P{p+1}–P{p+n}"`), `relief_by_day` (`{"Mon": periods, …}` for the
    school week), `marks`. Lesson: `subject`, `level`, `periods`,
    `weekday`, `date`. Rules: `settings["rules"]` with every person's name and short name replaced by their label, or
    by `"another teacher"` when not on the shortlist.
  - `GUARD_N, GUARD_S = 60, 600`; `ask(data, call=None) -> dict(ok, label, reason) | dict(ok=False, error)`, never
    raising: its own `SYSTEM` (follow the rules in order, quote the rule followed, answer one label from the list and a
    reason of one or two sentences) and `SCHEMA` (`label`, `reason`), the call shaped as `typed._call` (same client and
    model, `max_tokens=600`), `TYPED_REQUEST_MODEL=mock` answering the first label with "Practice pick: the first
    teacher in the app's order.".
  - `choose_for(pub, settings, records, record, x, c, call=None, without=()) -> dict(who, by, reason, at) | None`
    (only for an open cover; a planner's choice is already its pick): `None` when the shortlist (less `without`) is
    empty; else the model's label if it
    is on the map and the reason, with labels turned back into names, is 1–300 characters and names nobody off the
    shortlist; else `app_order[0]` with `APP_ORDER`. `by` is `"ai"` or `"app"`.
- [ ] **Step 1: Write the failing tests**: `app_order_puts_flexi_adjunct_first_then_lightest_week`,
  `over_the_limit_is_not_on_the_shortlist`, `nothing_sent_carries_a_name_or_a_reason` (build `labelled` for a record
  whose reason, remarks and work hold distinctive words and whose rules text names a teacher: assert no teacher name,
  no reason word, no remark, no work text in `json.dumps(data)`), `a_good_answer_is_used_with_names_put_back`,
  `a_bad_label_an_empty_reason_or_a_failure_falls_back_to_the_app_order` (each: label not on the map, reason "", reason
  401 chars, `call` raising, `call` returning a non-dict, guard full by `_seen`), `the_guard_counts_only_calls_made`,
  `an_empty_shortlist_gives_none_and_no_call` (call records it was not made), `mock_model_picks_the_first_label`.
- [ ] **Step 2: Run** — fails, `relief.pick` missing.
- [ ] **Step 3: Implement** `relief/pick.py`. Labels are turned back into names with
  `re.sub(r"\bTeacher (\d+)\b", ...)`, unknown numbers make the answer fail the check.
- [ ] **Step 4: Run** the file — passes.
- [ ] **Step 5: Commit** "Relief: the pick, by the AI from a labelled shortlist, checked, with the app's own order".

### Task 3: Filling picks when they are due

**Files:**
- Create: `relief/fill.py`
- Modify: `app.py` (start the ticker), `Dockerfile` (`ENV RELIEF_JOBS=on`)
- Test: `tests/test_relief_team.py`

**Interfaces:**
- Consumes: `pick.choose_for`, `cover.set_pick`, `cover.state`, `calendar.school_day`, settings `times.fill_at`.
- Produces:
  - `due_at(cal, days, date, fill_at) -> datetime`: for a lesson today or earlier, the start of that day (due at once);
    for a later date, `fill_at` on the school day before it in the calendar (Friday for a Monday; skipping holidays).
  - `run(ids=None, date=None, call=None, now=None) -> dict(picked=int, nobody=int)`: reads `store.published()` and
    `settings.load(pub)` itself; first `cover.drop`s every waiting pick that is `stale`; then for every open, needed,
    not-ended cover that is due (or every open cover of `ids`/`date` when given), compute `choose_for` on a snapshot **outside**
    the lock, then `cover.set_pick` under it; on `NOT_FREE` compute once more from fresh records, then leave it open.
    Covers of one absence are picked in lesson order, each seeing the picks before it. A module lock taken with
    `acquire(blocking=False)` keeps two runs from overlapping (the second returns `dict(picked=0, nobody=0, busy=True)`).
  - `soon(ids=None, date=None)`: runs `run` in a daemon thread; `SYNC = False` module flag, tests set it `True` to run
    inline.
  - Change requests: `run` also picks for every `"change"` cover whose `change.pick` is None, excluding the teacher who
    asked, saving into `change.pick`.
  - `start()`: a daemon thread calling `run(now=...)` every 60 seconds, catching and logging every exception (type only,
    never record contents); `app.py` calls it once at import when `os.environ.get("RELIEF_JOBS") == "on"`.
  - `filling() -> bool` for the Today page.
- [ ] **Step 1: Write the failing tests**: `due_at_today_is_now_and_monday_is_friday_at_fill_time` (with a holiday on the
  Friday → Thursday), `run_fills_only_what_is_due`, `two_absences_at_once_never_give_one_teacher_two_places` (two
  absences with one free teacher, both run; one gets them, the other another teacher or open with `NOBODY`),
  `a_run_while_another_runs_returns_busy`, `no_model_call_is_made_while_the_lock_is_held` (the injected `call` asserts
  `not absences._LOCK.locked()`), `a_change_request_gets_a_new_pick_without_the_teacher_who_asked`,
  `a_stale_waiting_pick_is_dropped_and_picked_again` (the picked teacher's own absence arrives; the run drops and
  re-picks; history keeps both), `the_ticker_is_not_started_in_tests` (`RELIEF_JOBS` unset → no thread named
  `relief-ticker`).
- [ ] **Step 2: Run** — fails.
- [ ] **Step 3: Implement** `relief/fill.py`; `app.py` starts it under the env check; the Dockerfile sets the variable.
- [ ] **Step 4: Run** the file, `tests/smoke.py` — pass.
- [ ] **Step 5: Commit** "Relief: picks made when due, at once for today, and a ticker on Railway".

### Task 4: Routes for the team and the relief teacher

**Files:**
- Modify: `relief/web.py`
- Test: `tests/test_relief_team.py`

**Interfaces:**
- Consumes: Tasks 1–3; stage 2's `_gate`, `_record`, `_change`, `_out`, `_body`, `_cal`.
- Produces (all under `/api/relief`; team routes need `relief.team`, refused with `TEAM_ONLY`):
  - `GET /today?date=` → `dict(date, filling, counts=dict(need, waiting, approved, acknowledged, change, nobody, open),
    rows=[...])`, rows in time order, one per cover: `id, ckey, absent, classes, subject, group, room, p, n, start, end,
    work_set (bool), state, pick (who, by, reason), approved, ack, change (why, pick), stale (bool), over_now (bool: the
    relief now takes them over a checked limit)`. A stale approved cover reads "{name} is no longer free then: change
    it". No reason of the
    absence on a row (the team opens the absence for it).
  - `POST /absences/<id>/covers/<path:ckey>/approve`; `POST /today/approve-all` `{date}`;
    `PUT /absences/<id>/covers/<path:ckey>/relief` `{relief}` (Change); `GET /absences/<id>/covers/<path:ckey>/free`
    (the free-then list for that cover); `POST /absences/<id>/lessons/<path:key>/split` `{at}`; `POST .../join`;
    `POST /absences/<id>/covers/<path:ckey>/keep`; `POST /today/fill` `{date}` → starts `fill.soon(date=)`.
    Stage 2's `POST /absences`, `.../needed` and `.../cancel` call `fill.soon()` after saving (a new absence for today is
    picked at once; a teacher who becomes absent stops being anyone's waiting pick).
  - For the relief teacher (`relief`): `GET /covering` → covers approved to me from today on (and earlier this week),
    each with `id, ckey, date, start, end, p, n, classes, subject, group, room, absent, work (text, link, files), state,
    ack, change` — never `reason`, `reason_text`, `remarks`, `reporting_officer`; `POST
    /absences/<id>/covers/<path:ckey>/acknowledge`; `POST .../ask-change` `{why}`.
  - `GET /files/<id>/<file>` also opens for the approved relief teacher of a lesson that lists the file.
  - `GET /load?week=YYYY-MM-DD|term=<name>` (team) → `rows=[dict(name, depts, fat, teaching, relief, week, term,
    changes)]` for every teacher with teaching that week; `GET /load/<name>` → every relief they took this term
    (date, lesson, absent, pick reason, approved by); `GET /load.csv` with stage 2's `_cell` guard.
  - What's in (`GET /absences`): each record gains `cover=dict(total, approved, waiting, open)` and `nudge` (planned by
    someone else, not acknowledged, and past `times.remind_at` on the school day before its first lesson).
  - `_out` for the absent teacher and the planner: a cover's `relief` is shown only when approved; otherwise `relief`
    is None and the planner's own unapproved choice is shown as `planned`.
- [ ] **Step 1: Write the failing tests**: `today_lists_covers_in_time_order_with_counts_and_no_reason`,
  `approve_routes_need_the_team` (an ordinary teacher and a planner not on the team get 403),
  `covering_lists_only_approved_and_never_the_reason`, `acknowledge_and_ask_change_are_the_relief_teachers_alone`,
  `the_relief_teacher_can_open_the_work_file`, `the_absent_teacher_sees_the_name_only_once_approved`,
  `load_counts_teaching_and_relief_for_the_week_and_term`, `load_csv_neutralises_formulas`,
  `whats_in_counts_covers_and_marks_the_nudge`, `an_absence_for_today_gets_its_picks_at_once` (`fill.SYNC = True`,
  injected `call` via `pick`'s module hook).
- [ ] **Step 2: Run** — fails.
- [ ] **Step 3: Implement** the routes in `relief/web.py`.
- [ ] **Step 4: Run** the file, `tests/test_relief_requests.py`, `tests/smoke.py` — pass.
- [ ] **Step 5: Commit** "Relief: routes for Today, approving, changing, covering and the load tracker".

### Task 5: The Today page and Reliefs I'm covering

**Files:**
- Create: `static/relief-today.js`, `static/relief-covering.js`
- Modify: `static/relief.html`, `static/relief.js` (`TABS` gains `["today", me => !!me.can_team]` and
  `["covering", () => true]`)

**Interfaces:**
- Consumes: Task 4's routes; `Relief.tab`, `Relief.api`, `Relief.json`, `ReliefForm` helpers (`esc`, `day`, `periods`,
  `time`).
- Produces:
  - **Today** (mockup tab 6): a date choice (today by default, "Tomorrow" button), counters, rows in time order with the
    absent teacher, class and subject, room, "work set" or "no work yet", the pick with its reason (and "AI", "app's
    order", "planned" or "team"), the state, and buttons Approve, Change (opens the free-then list, as Plan relief's),
    Split (lessons of 2+ periods; choose the boundary), Join again, Keep (on a change request; Approve there reads
    "Approve the new pick"). "Approve all waiting" and "Fill now" at the top. While `filling` is true the page fetches
    again every 3 seconds and shows "Being picked".
  - **Reliefs I'm covering** (mockup tab 7): the covers approved to me, grouped by date, each with the lesson, room,
    whose class, the work and its files (download links), and Acknowledge / Request to change (a line of why).
    Empty: "No relief for you right now."
- [ ] **Step 1:** Build both tabs; every text through `esc`.
- [ ] **Step 2:** `node --check` each changed script.
- [ ] **Step 3:** Open the sample in the browser (controller's temporary launch entry, `TYPED_REQUEST_MODEL=mock`) and
  try each button with real clicks; screenshots of made-up data only.
- [ ] **Step 4: Commit** "Relief: the Today page and Reliefs I'm covering".

### Task 6: The load tracker and What's in

**Files:**
- Create: `static/relief-load.js`
- Modify: `static/relief.html`, `static/relief-inbox.js`, `static/relief.js` (`TABS` gains
  `["load", me => !!me.can_team]`; `R.absences`' relief line: the approved name, or "The relief team will assign", or
  "Planned: {name}, waiting for the relief team")

**Interfaces:**
- Consumes: Task 4's `/load`, `/load/<name>`, `/load.csv`, What's in `cover` and `nudge`.
- Produces:
  - **Load** (mockup tab 9): This week / This term, filters Department and "Flexi Adjunct only", the table (teaching this
    week, relief this week, week so far, relief this term, requests to change this term), Download; a name opens their
    reliefs this term with the reason of each pick and who approved it.
  - **What's in**: a "Needs a nudge" view; a relief status column ("3 of 5 approved", "2 waiting", "1 open"); the line
    "The app's picks … come in the next stage." removed.
- [ ] **Step 1:** Build both; `node --check`.
- [ ] **Step 2:** Browser check as Task 5.
- [ ] **Step 3: Commit** "Relief: the load tracker and What's in's relief status".

### Task 7: Finish

- [ ] README's Relief section: what stage 3 adds. DEPLOY.md: what relief sends to the model (labels, departments,
  subjects, period counts; never names, reasons, work), `RELIEF_JOBS`, the AI budget.
- [ ] Every suite: `.venv/bin/python tests/<name>.py` for each `tests/*.py`, `node tests/*.test.js` one by one,
  `node --check` on every changed script; `--full` runs alone.
- [ ] Browser check on the made-up sample with a made-up term (`TYPED_REQUEST_MODEL=mock`): ask for relief for today →
  picks appear → approve one, approve all, change one, split one, join again; as the relief teacher acknowledge one and
  ask to change another; as the team approve the new pick; the load tracker and its download; What's in's nudge;
  an ordinary teacher sees no Today or Load tab; phone width.
- [ ] The school's real published timetable, numbers only, scratch deleted afterwards: a made-up whole-day absence for
  the five teachers with the most lessons on a made-up date, `run` with the app's own order only (no model): picks
  made, nobody-free count, the slowest pick and the whole run's time, no errors.
- [ ] No real staff name and not the school's full name in the branch's commits.
- [ ] Notes: `docs/superpowers/plans/2026-11-21-relief-stage-3-notes.md` (rulings, checks, what was not tried in a
  browser, what stage 3b and stage 4 need).

# Relief: the absent teacher's timetable and a calendar for Pick dates — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** On the relief page, Pick dates becomes a two-month calendar (click, or drag across a run of school days, up to 20)
on Plan relief and Ask for relief; Plan relief gets a "Their timetable ↗" link beside the absent teacher; a long absence's
dates read as runs ("Mon 30 Nov – Fri 11 Dec") wherever they are listed in one line.

**Architecture:** The server lists the school days (one new read-only route built on `relief.calendar.school_day`, the same
rule `lessons.on_date` uses), so the page greys exactly what the server would refuse. One new page file,
`static/relief-dates.js`, is the calendar for both forms; its date logic is pure functions tested in node. One runs rule,
written once in Python (`relief/words.py`) and once in the page (`relief-form.js`), used by every one-line list of dates.

**Tech Stack:** Python 3 / Flask, plain JavaScript (no libraries), plain-assert test scripts.

**Spec:** `docs/superpowers/specs/2026-11-26-relief-dates-calendar-design.md` (approved 26 Nov 2026, "Approved, plan it"),
with its mockups `2026-11-26-relief-dates-calendar-mockups.html` (the lead chose A; the mockup's summary line predates the
one runs rule). Read both.

**Branch:** `relief-calendar`, worktree `tt-relief-calendar`, from main 82c0646 plus the design commits. Nothing is pushed.

## Global Constraints

- The repo is public: the school is only ever "CTSS"; tests, samples and docs use made-up names only (never a real staff
  name, never the school's real calendar).
- Builders and reviewers: NEVER run `git stash`, `git stash pop` or `git checkout -- <file>`; `git stash list` shows the
  same entries after each task as before it. Never `pkill`/`killall` by name or pattern; stop only processes you started,
  by PID.
- In `static/*.js`, never a `//` comment in the middle of a long line; use `/* */`.
- Dates read "Tue 13 Oct" (`RF.day` / `words.day`); a run reads "Mon 30 Nov – Fri 11 Dec" (spaces around U+2013 "–").
  Exact copy (verbatim):
  - "Choose up to 20 school days, today or later."
  - "There are no school days coming up in the calendar."
  - "No dates yet. Up to 20 school days."
  - "That is 20 school days, the most at one time."
  - "N school days: …" ("1 school day: …" for one), and a button "Clear all"
  - "Reading the school calendar…"
  - grey-day reasons: "In the past", "Weekend", a holiday's own name, "Not in a term", "Not a school day"
  - the link "Their timetable ↗"
- The limit is **20** school days (`MAX_DATES = 20`); the page cap is the same number.
- No new right name, no new dependency, no new library. The new route goes through `need("relief")` and is pinned in
  `tests/test_routes.py` `GUARDS` as `"relief_web.school_days": ('relief',)`.
- Every commit ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`, written with a quoted heredoc.
- A changed old test keeps its meaning or states the new rule; it is never weakened. Name every changed old test in the
  commit message.
- Tasks run one after another, in order. New tests go in a new section at the end of the file named, headed
  `# ---- Calendar, Task N: <name> ----` (node: `/* ---- Calendar, Task N ---- */`).
- "Run the suites" means, one at a time, from the worktree: `.venv/bin/python tests/<f>.py` for `test_relief_requests`,
  `test_relief`, `test_relief_team`, `test_exams_relief`, `test_routes`, `test_relief_telegram`, `smoke`; and
  `node tests/<f>` for every `tests/relief_*.test.js` plus `tests/timetable_page.test.js`; `node --check` on every
  `static/*.js` the task touched. Each prints its count and no failure. (Baseline on main: see the notes file.)

## Review Focus

1. **A drag that crosses a weekend, a holiday or the month boundary ticks a day the server then refuses**, or misses a
   school day. Expected: exactly the server's school days between the two days, in either drag direction.
   (Task 3 `dragResult` tests; Task 4 browser check with real drags across the two months.)
2. **The form repainting during a drag** (the lessons read finishing, a teacher chosen) and the calendar losing the drag
   or jumping month. Expected: the month shown and the drag survive any repaint; the lessons are read once, on release.
   (Task 3 `view state is kept by key`; Task 4 browser check: drag while a lessons read is in flight.)
3. **A click counted twice** (pointer path plus the button's own click) or a keyboard Enter not counted at all.
   Expected: one click or one Enter/Space toggles once. (Task 3 click rule; Task 4 browser check: mouse click and Enter.)
4. **No calendar set, nothing published, or a school break:** blank grey months or an endless "Reading…". Expected: the
   server's sentence in place of the calendar, Today and Tomorrow still working; in a break the calendar opens on the
   next term. (Task 1 route tests; Task 3 `months` tests.)
5. **The 21st day:** a drag that would pass 20 or a click on a 21st day. Expected: nothing past 20 is ticked, from the
   day the drag started, and the line says "That is 20 school days, the most at one time."; the server refuses 21.
   (Task 1 `twenty_school_days_are_allowed_and_twenty_one_are_not`; Task 3 cap tests.)

---

### Task 1: The server: school days, the limit of 20, `staff_only`

**Files:**
- Modify: `relief/calendar.py` (add `school_days`), `relief/lessons.py` (add `NO_DAYS`), `relief/absences.py:32,104`,
  `relief/web.py` (new route after `people()`, ~line 460; `people()` adds `staff_only`)
- Test: `tests/test_relief_requests.py` (new section at the end; update the old assertions at ~383, ~640, ~644),
  `tests/test_relief_telegram.py` (~6568, ~6569: the sentence), `tests/test_routes.py` (`GUARDS`)

**Interfaces:**
- Produces: `relief.calendar.school_days(cal: dict, days: list[str], start: datetime.date) -> tuple[list[datetime.date], dict[datetime.date, str]]`
  — every date from `start` to the last day of the last term (inclusive) for which `school_day` is not None, and for every
  **weekday** in that span that is not one of them, its reason: the holiday's `name` (or "Holiday" when unnamed), else
  "Not in a term" (no `term_of`), else "Not a school day". No terms, or `start` after the last term: `([], {})`.
- Produces: `relief.lessons.NO_DAYS = "There are no school days coming up in the calendar."` (equal to `relief.asking.NO_DAYS`).
- Produces: `GET /api/relief/school-days` → 200 `{"today": iso, "days": [iso, ...], "off": {iso: reason}}`; refusals
  with the gate's answers (401 / 409 as `/api/relief/lessons`), 400 `{"error": lessons.NO_CALENDAR}` with no terms,
  400 `{"error": lessons.NO_DAYS}` with terms but no school day from today on. Endpoint name `relief_web.school_days`.
- Produces: `/api/relief/people` items are `{name, depts, staff_only}` (`staff_only` a bool from `accounts.listing`).

- [ ] **Step 1: Write the failing tests** (section `# ---- Calendar, Task 1: the server ----`). With the file's `CAL`
  (Term 4 2026-09-07 to 2026-11-20, Deepavali 2026-10-23), `DAYS = day_names(2)` and `LS.today()` = Mon 12 Oct:
  - `school_days_from_a_monday_in_term`: `got, off = school_days(CAL, DAYS, D(2026,10,12))`; `len(got) == 29`,
    `got[0] == D(2026,10,12)`, `got[-1] == D(2026,11,20)`, `D(2026,10,23) not in got`, `off == {D(2026,10,23): "Deepavali"}`.
  - `school_days_across_a_break_and_a_missing_weekday`: cal with Term 4 as above and
    `dict(name="Term 1", start="2027-01-04", end="2027-01-15", starts_as="Odd")`, days `["Mon","Tue","Wed","Thu"]`
    (`day_names(1)` without Fri), start `D(2026,11,16)`: `got` = Nov 16–19 and Jan 4–7, 11–14 (12 dates);
    `off[D(2026,11,20)] == "Not a school day"`, `off[D(2026,11,23)] == "Not in a term"`, `off[D(2027,1,8)] == "Not a school day"`,
    no Saturday or Sunday key in `off`, `max(off) == D(2027,1,15)`.
  - `school_days_with_no_term_or_after_the_last`: `school_days(dict(terms=[], holidays=[]), DAYS, D(2026,10,12)) == ([], {})`
    and `school_days(CAL, DAYS, D(2026,11,21)) == ([], {})`; `LS.NO_DAYS == ASK.NO_DAYS` (import `relief.asking as ASK`).
  - `the_school_days_route`: under `published(APUB)`, `staff(EVE)`: `GET /api/relief/school-days` is 200 with
    `today == "2026-10-12"`, `len(days) == 29`, `days[0] == "2026-10-12"`, `off == {"2026-10-23": "Deepavali"}`; with the
    settings' calendar emptied (write `RS.PATH` with `terms=[]`, restore after in `finally`) it is
    `no(..., 400, LS.NO_CALENDAR)`; with `LS.today` set to `D(2026,11,23)` it is `no(..., 400, LS.NO_DAYS)` (restore in `finally`).
  - Add `("GET", "/api/relief/school-days")` to `routes` in `nothing_published_and_signed_out_answers` (401 signed out, 409 unpublished).
  - `twenty_school_days_are_allowed_and_twenty_one_are_not`: the first 20 school days from 2026-10-13 (skip weekends and
    2026-10-23) through `GET /api/relief/lessons?dates=...` answer 200 with 20 keys in `by_date`; 21 dates answer
    `no(..., 400, "Choose up to 20 school days, today or later.")`.
  - `people_say_who_is_staff_only`: each item of `GET /api/relief/people` has exactly `{"name", "depts", "staff_only"}`;
    a published teacher has `staff_only is False`; a person added by name in the accounts (as `tests/test_routes.py`
    adds its made-up `added=True` people) has `staff_only is True`.
  - Old tests changed: in `every_refusal_says_its_sentence_and_writes_nothing` the sentence becomes the 20 one and the
    too-many case is 21 dates (`[(D(2026,10,13) + datetime.timedelta(days=i)).isoformat() for i in range(21)]`); in
    `asking_through_the_api` the sentence becomes the 20 one and the people assertion becomes
    `set(p) == {"name", "depts", "staff_only"}` with `{"name": GRACE, "depts": ["Mathematics"], "staff_only": False}` in it;
    in `tests/test_relief_telegram.py` lines ~6568–6569 the sentence becomes the 20 one; `GUARDS` gains the new endpoint.

- [ ] **Step 2: Run** `.venv/bin/python tests/test_relief_requests.py` — expect FAIL (no `school_days`).

- [ ] **Step 3: Implement** `school_days` in `relief/calendar.py` (pure; walk the dates once, reuse `school_day`, `term_of`
  and the holidays), `NO_DAYS` in `relief/lessons.py`, `MAX_DATES = 20` and the sentence in `absences._iso_dates`, the route
  `school_days()` in `relief/web.py` (`_gate()`, then `_cal(pub)`; model day names from `pub["model"]["days"]`; ISO strings
  in the reply), and `staff_only=bool(p.get("staff_only"))` in `people()`.

- [ ] **Step 4: Run the suites** — all pass.

- [ ] **Step 5: Commit** — `feat(relief): the school days for the page, up to 20 school days, staff_only on people`
  (name the changed old tests).

---

### Task 2: One runs rule for a line of dates

**Files:**
- Modify: `relief/words.py` (`days`), `static/relief-form.js` (add `dayRuns`, export it),
  `static/relief-inbox.js:43` (row), `static/relief.js:169` (My absences head), `static/relief-plan.js:369` (`plannedRow`)
- Create: `tests/relief_dates.test.js` (loads `relief-form.js` in a `vm` context as `tests/relief_inbox.test.js` does)
- Test: `tests/test_relief_requests.py` (new section), `tests/relief_inbox.test.js` (one new case)

**Interfaces:**
- Produces: Python `relief.words.days(record) -> str` and JS `ReliefForm.dayRuns(dates: string[], label?: (iso) => string) -> string`,
  the same rule: sort and de-duplicate the ISO dates; a date continues a run when it is the next weekday after the one
  before (Fri → the following Mon; otherwise the next day); a run of **3 or more** reads `"<first> – <last>"`; shorter runs
  list each date; everything joined with `", "`. `label` (JS only) names each date, default `RF.day`.

- [ ] **Step 1: Write the failing tests.**
  - Python `words_days_joins_runs_of_three_or_more`: `days(dict(dates=[...]))` gives
    `"Tue 13 Oct, Wed 14 Oct"` for two; `"Mon 12 Oct – Wed 14 Oct"` for 12, 13, 14; `"Thu 15 Oct – Tue 20 Oct"` for
    15, 16, 19, 20 (a weekend joins); `"Wed 21 Oct, Thu 22 Oct, Mon 26 Oct, Tue 27 Oct"` for 21, 22, 26, 27 (Fri 23 missing
    breaks it); `"Mon 12 Oct – Fri 16 Oct, Tue 20 Oct"` for 12–16 and 20, unsorted, with a duplicate; `""` for none.
  - Node `tests/relief_dates.test.js`: the same five cases through `RF.dayRuns`, and
    `RF.dayRuns(["2026-10-12","2026-10-13","2026-10-14"], d => d === "2026-10-12" ? "Today" : RF.day(d)) === "Today – Wed 14 Oct"`.
  - Node `tests/relief_inbox.test.js`: an absence with dates 2026-10-13 to 2026-10-16 shows `Tue 13 Oct – Fri 16 Oct` in the row.

- [ ] **Step 2: Run** both test files — expect FAIL.

- [ ] **Step 3: Implement** `days()` and `dayRuns`; use `RF.dayRuns` in the three page lines (the inbox keeps its
  "Today" label through the `label` argument).

- [ ] **Step 4: Run the suites** (plus `node tests/relief_dates.test.js`) — all pass.

- [ ] **Step 5: Commit** — `feat(relief): a long absence's dates read as runs`.

---

### Task 3: The calendar (`static/relief-dates.js`)

**Files:**
- Create: `static/relief-dates.js`
- Modify: `static/relief.html` (the `<script>` after `relief-form.js`, before `relief.js`; the calendar's CSS in the page's
  `<style>`, using its variables `--line`, `--panel`, `--navy`, as `.seg` does, with a `@media (max-width:640px)` rule
  that stacks the months)
- Test: `tests/relief_dates.test.js`

**Interfaces:**
- Consumes: `ReliefForm.day`, `ReliefForm.dayRuns`, `ReliefForm.esc`; the route of Task 1.
- Produces `window.ReliefDates`:
  - `load(api: (url) => Promise<{ok, status, data, error}>) -> Promise<{ok, status, error, info}>`: reads
    `/api/relief/school-days` once per page (a failed read is retried on the next call); `info = {today, days: Set<iso>, list: iso[], off: {iso: reason}}`.
  - `why(iso, info) -> string`: `""` for a school day; else "In the past" (before `info.today`), "Weekend", `info.off[iso]`,
    or "Not in a term" (after the last school day).
  - `between(a, b, info) -> iso[]`: the school days from `a` to `b` inclusive, either order, in date order.
  - `dragResult(picked: iso[], anchor, end, info, max) -> {picked: iso[], capped: bool}`: `anchor` not in `picked` adds
    the school days of `between(anchor, end)` taken **from the anchor towards the end** until `picked` holds `max`
    (`capped` true when some were left out); `anchor` in `picked` removes every day of `between`. `picked` returned sorted.
  - `months(info) -> {first: "YYYY-MM", last: "YYYY-MM"}`: the month of the first and of the last school day.
  - `html(view) -> string`, pure: `view = {info, first: "YYYY-MM", picked: iso[], preview: {add: iso[], rem: iso[]}, max, capped}`;
    two months from `first`, each `.rd-month` with `‹` (`data-rd="prev"`, disabled when `first <= months(info).first`) on the
    left month and `›` (`data-rd="next"`, disabled when the right month `>= months(info).last`) on the right one; Monday
    first; each day a `<button type="button" class="rd-d …" data-d="iso">` with classes `off` (and `aria-disabled="true"`,
    `title` = its reason), `pick` (`aria-pressed="true"`), `add`, `rem`, `today`; then the line `.rd-sum`:
    "N school days: <dayRuns> [Clear all]" (`data-rd="clear"`), or "No dates yet. Up to 20 school days."; plus
    "That is 20 school days, the most at one time." when `picked.length >= max`.
  - `mount(box: Element, opts: {key: string, picked: iso[], max: number, onChange: (iso[]) => void})`: draws into `box`
    ("Reading the school calendar…" until `load` answers; on a refusal the server's sentence via `Relief.say`, with a
    "Try again" button when `status === 0`). The month shown is kept per `opts.key` across mounts (a form repaint makes a
    new box). While a drag is in progress in that key, a mount only records the new `picked` and draws on release.
  - `focusFirst(box)`: focus the first day button that is not `off`.
- Pointer and keys (the builder's code; the rules): a drag starts on `pointerdown` (main button) on a day that is not
  `off`, follows `pointermove` on `document` with `document.elementFromPoint` to the day under the pointer (a grey day
  keeps the last school day as the end), draws the preview by changing classes only (never rebuilding the grid mid-drag),
  and ends on `pointerup` with one `onChange(dragResult(...).picked)` when it changed anything; `pointercancel` ends it with
  no change. A `click` with `event.detail === 0` (Enter or Space) toggles that day through the same `dragResult`; a mouse
  click is never counted twice. Arrow keys move focus by a day (left/right) or a week (up/down), moving the months on when
  focus leaves them. `.rd-grid` has `touch-action: none` so a finger drags rather than scrolls on the grid.

- [ ] **Step 1: Write the failing tests** in `tests/relief_dates.test.js` (section Task 3), with a made-up `info`: today
  `2026-11-26`, `list` the weekdays from 26 Nov to 31 Dec 2026 minus 4 Dec and 25 Dec, `off = {"2026-12-04": "Founders' Day",
  "2026-12-25": "Christmas Day"}` (made-up school):
  - `why`: "2026-11-25" → "In the past"; "2026-11-28" → "Weekend"; "2026-12-04" → "Founders' Day"; "2027-01-04" →
    "Not in a term"; "2026-11-27" → "".
  - `between("2026-12-08", "2026-11-27", info)` → 27 Nov, 30 Nov, 1, 2, 3, 7, 8 Dec (7 dates, date order).
  - `dragResult([], "2026-11-27", "2026-12-08", info, 20)` → those 7, `capped` false; dragging from a ticked day removes
    the ticked days between; `dragResult(["2026-12-14"], "2026-12-08", "2026-11-27", info, 3)` (a drag backwards with room
    for 2) → `["2026-12-07", "2026-12-08", "2026-12-14"]`, `capped` true (taken from the anchor); a click (anchor = end) on
    a ticked day removes it, on an unticked school day adds it.
  - `months(info)` → `{first: "2026-11", last: "2026-12"}`; with `list` starting in January → `first` "2027-01".
  - `html(...)`: for `first` "2026-11", the left `‹` is disabled and the right `›` is disabled; the button for 4 Dec has
    `off`, `aria-disabled="true"` and `title="Founders' Day"`; a picked day has `pick` and `aria-pressed="true"`; the line
    reads `7 school days: Fri 27 Nov – Thu 3 Dec, Mon 7 Dec, Tue 8 Dec`; with 20 picked it holds the "That is 20 …" sentence;
    with none, "No dates yet. Up to 20 school days.".
  - `view state is kept by key`: in a small stand-in DOM, `mount` twice with key "plan" after a `next` press keeps the
    month (as far as the stand-in allows; else test the per-key state function the builder exposes for it).

- [ ] **Step 2: Run** `node tests/relief_dates.test.js` — expect FAIL.

- [ ] **Step 3: Implement** `static/relief-dates.js` and the page's CSS and script tag.

- [ ] **Step 4: Run the suites** and `node --check static/relief-dates.js` — all pass.

- [ ] **Step 5: Commit** — `feat(relief): a two-month calendar for picking school days`.

---

### Task 4: The calendar on Plan relief and Ask for relief

**Files:**
- Modify: `static/relief-plan.js` (`paintDay` ~212, `addDate` ~325, the click cases `adddate`/`undate` ~448–449, the
  `day` case ~447, `onKey` ~491), `static/relief.js` (Ask for relief: `paintDay` ~485, `addDate` ~575, click ~626–628,
  key ~650)
- Test: `tests/relief_dates.test.js` (string checks of the two forms), browser check

**Interfaces:**
- Consumes: `ReliefDates.mount`, `ReliefDates.focusFirst` (Task 3).

- [ ] **Step 1: Write the failing tests** (node, reading the two files as text): neither `relief-plan.js` nor `relief.js`
  holds `type="date" id="plDate"`, `id="askDate"`, `adddate`, `undate` or "Up to 10 dates"; each calls
  `ReliefDates.mount(` with `key: "plan"` / `key: "ask"` and `max: 20`.

- [ ] **Step 2: Run** — expect FAIL.

- [ ] **Step 3: Implement.** Under Pick dates, `paintDay` draws the seg and an empty `<div class="rd-box">`, then mounts
  the calendar into it with the form's `picked`; `onChange(list)` sets `P.picked` / `A.picked`, then `changed(); reread();`
  (no `paintDay`: the calendar redraws itself). Choosing Pick dates calls `ReliefDates.focusFirst`. Remove `addDate`,
  the `adddate`/`undate` cases and the date-box Enter key. Today, Tomorrow, `dates()`, `reread()`, Send and the reset after
  Send are unchanged (the reset's `picked: []` shows an empty calendar next time).

- [ ] **Step 4: Run the suites** — all pass.

- [ ] **Step 5: Browser check** on the scratch server the controller names (open it as `http://<name>.localhost:<port>`),
  with the browser tool's real pointer only (`left_click`, `left_click_drag`; never events sent from the console), one
  line per check saying which kind it was, at the pane's own size (no emulated viewport for drags):
  1. Plan relief → Pick dates: a drag from a day in this month to one in the next ticks only school days; the lessons
     list shows those dates' lessons after release; the line reads as runs.
  2. A drag back over ticked days takes them off; a click ticks and unticks one day; Enter on a focused day ticks it.
  3. Grey days cannot be ticked; pointing at the holiday shows its name.
  4. 21st day refused with the sentence; Send with 20 dates succeeds and Planned by me shows the runs line.
  5. The same on Ask for relief.
  6. `‹ ›` move both months and stop at the ends.
  Report screenshots' paths (made-up data only).

- [ ] **Step 6: Commit** — `feat(relief): Pick dates is a calendar on both forms`.

---

### Task 5: "Their timetable ↗" on Plan relief

**Files:**
- Modify: `static/relief-form.js` (`person`/`drawPicker`: an optional `opts.after(name) -> html` drawn after "Change" in
  the chosen row), `static/relief-plan.js` (`paintWho`)
- Test: `tests/relief_dates.test.js` (section Task 5)

**Interfaces:**
- Consumes: `staff_only` on `/api/relief/people` items (Task 1).

- [ ] **Step 1: Write the failing tests**: drawing the picker (as `RF.person` into a stand-in container) with
  `value: "Ms Ada Ong"` and an `after` returning `<a …>` puts that HTML after the Change button; without `after` the row
  is as before. `relief-plan.js` builds the link as
  `<a class="… " href="/timetable#teachers/${enc(name)}" target="_blank" rel="noopener">Their timetable ↗</a>` and only
  when the chosen person is not `staff_only` (a text check on the file is enough for that branch).

- [ ] **Step 2: Run** — expect FAIL.

- [ ] **Step 3: Implement**; the link looks like the page's other small buttons (`.small` / `.ghost` styles), and a name
  with "/" (as in "s/o") still opens that teacher (the published page splits at the first "/" only).

- [ ] **Step 4: Run the suites**; browser check with a real click: the link opens a new tab on the teacher's timetable,
  both weeks; a person added only in the accounts gets no link.

- [ ] **Step 5: Commit** — `feat(relief): Their timetable link beside the absent teacher`.

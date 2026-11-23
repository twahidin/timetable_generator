# Relief duty and the send-out, stage 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Relief teachers hear of a relief only once the relief team has approved it and pressed Send out (or a head chose them when
planning), and only in school hours; the team is not pinged between the cut-off and the morning message; the AI picks at once for any
date; the person away is told who covers them; files stay in the app.

**Architecture:** One new pure module, `relief/hours.py`, answers every question of time (the three times, school hours for relief
teachers, the team's window, when a held relief goes, the stage 2 seams). The cover record gains one field, `sent_out`. Every message is
still worked out by the sweep (`relief/tell.py` `due`) from the records, under a key of its own, queued once and checked again by
`still_true`; the morning message is made by the minute ticker in a new module `relief/morning.py`, claimed once a day with
`tgdb.raise_state`. No new scheduler, no new table, no new right, no new dependency.

**Tech Stack:** Python 3 / Flask, sqlite3, plain JavaScript, plain-assert test scripts (as stage 4).

**Spec:** `docs/superpowers/specs/2026-11-23-relief-duty-and-send-out-design.md` (approved 23 Nov 2026; questions 2 to 4 as written) and
its mockups `2026-11-23-relief-duty-and-send-out-mockups.html`. Stage 4's notes `2026-11-22-relief-stage-4-notes.md` and today's
`2026-11-23-relief-telegram-answers-notes.md` hold the rulings this plan keeps. Stage 2 (the duty roster, days with no relief duty) is
not planned here; Task 1 builds its two seams and nothing more.

**Branch:** `relief-send-out`, worktree `tt-relief-stage-4`, from c797c9b (main d2dfbaf plus the design). Nothing is pushed.

## Global Constraints

From today's plan, verbatim where they apply:
- The repo is public: the school is only ever "CTSS"; tests, samples and docs use made-up names only.
- **Never print, log, show or commit a real token, code or key.** The bot's address holds the token: no URL, no exception
  text and no Telegram answer body is ever logged; failures are logged to `relief.telegram` by kind alone.
- **No real Telegram call anywhere in tests or checks.** `relief/tg.py` has one network function, `_send`; every test
  replaces it at import with a function that fails if called. Browser checks use `TELEGRAM_BOT_TOKEN=practice`.
- **A Telegram message carries a person's name, class, subject, room, period, time, work; never the typed absence reason,
  remarks, a pick's history, or anything from the model except the pick's own reason line to the team.**
- A button press or typed answer does exactly what the page's button does: same functions, same rights
  (`rights.rights(person, "telegram")`), same sentences, one history entry by that person with via `telegram`.
- Nothing network-bound runs under `absences._LOCK`. The webhook handler makes no model call.
- "Today" and "now" are school time (`lessons.today()`, `absences._now()`); lesson times come from `exams.days.bounds`.
- Tests are plain-assert scripts run as `.venv/bin/python tests/<name>.py`, `DATA_DIR` set to a fresh temp folder before
  `import app`; `RELIEF_JOBS` never set; `TELEGRAM_BOT_TOKEN` set to `practice` or a random made-up string, never real.
- Rights names used: `relief`, `relief.plan`, `relief.team`, `relief.save`. No new right name.
- Builders and reviewers: NEVER run `git stash`, `git stash pop` or `git checkout -- <file>`; `git stash list` unchanged
  after each task. In `static/*.js`, never a `//` comment in the middle of a long line; use `/* */`.
- Dates read "Tue 13 Oct"; periods "P9–P11"; times "10:40". The sentences below are used verbatim.
- Every commit ends with `Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>`, written with a quoted heredoc.
- Nothing is pushed. No real Telegram or model call. Made-up names only; the school only "CTSS". Logs by kind alone.
- A message never holds the typed reason (nor the reason's kind, except the officer's message as before).
- No em-dashes and no arrows in copy, docs or notes. `·` is U+00B7.

From the spec ("Constraints carried", the anti-goals) and for this plan:
- Nothing reaches a relief teacher before a relief team member approved it and sent it out, or a head (`relief.plan`) chose that
  teacher when planning, nor before the earliest send-out time of a school day; outside school hours (from the earliest send-out time
  to the cut-off of a school day; after the cut-off, only about a lesson of that day still to come) nothing reaches them.
- Nobody on the relief team is pinged for a new request between the cut-off and the morning time.
- A held relief is made from the record as it is when it goes: never queued early with `next_at`.
- A message is sent once, or marked "may not have been sent"; never twice. Every new message has its own key, is worked out by the
  sweep or the minute ticker, never sent from a page, and has its check in `tell.CHECKS`.
- No new right name, no new dependency, no new scheduler, no new table. Send out uses `relief.team`; the times use `relief.save`; a
  head's own choice uses `relief.plan`.
- Without Telegram connected everything works on the pages: Send out then makes the relief show in Reliefs I'm covering at its time.
- Every new route goes through `need()` and is listed in `tests/test_routes.py`. Every save by a person writes one history entry.
- No staff name, reason or work goes to the AI provider; picking at once changes when the AI is asked, not what it is told.
- Tasks run one after another, in the order below, never in parallel. Each task appends its tests in a new section at the end of the
  test file it names, headed `# ---- Send-out, Task N: ... ----` (in node files, `/* ---- Send-out, Task N ---- */`).
- "Run the suites" means, one at a time: `.venv/bin/python tests/test_relief_telegram.py`, `tests/test_relief_team.py`,
  `tests/test_relief_requests.py`, `tests/test_relief.py`, `tests/test_exams_relief.py`, `tests/test_routes.py`, `tests/smoke.py`, and
  `node tests/<file>` for each node file the task touched. Each prints its count and no failure.
- A changed old test keeps its meaning or says the new rule; it is never weakened. Every old test a task changes is named in its commit
  message.

## Review Focus

1. **A relief teacher messaged in the night, or twice**: a relief sent out at 21:00, a queue held up past the cut-off by an outage, a
   repeat made twice after a restart. Expected: nothing to a relief teacher outside school hours, whatever was queued; each key once.
   (Task 6, `a_message_held_up_past_the_cut_off_waits_for_the_morning`; Task 9, `a_repeat_goes_once_and_not_within_twelve_hours`.)
2. **A relief nobody sent out reaching its teacher, or one sent out never reaching them because a gate never opens** (the calendar no
   longer knows the day, no term at all). Expected: approved alone never goes; sent out always goes by its lesson's own morning.
   (Task 1, `a_held_relief_never_waits_past_its_own_morning`; Task 3, `approve_alone_tells_nobody`.)
3. **The morning message saying nothing waits when something does, or coming twice after a restart.** Expected: a message whenever
   any lesson of today is to cover, whatever its state, once a day across restarts and two copies. (Task 7,
   `the_morning_message_counts_every_lesson_to_cover` and `the_morning_message_is_claimed_once_a_day`.)
4. **Records already in the data when this is deployed**: approved reliefs with no `sent_out` field. Expected: treated as sent out at
   their approval, so nobody is messaged again, nothing vanishes from Reliefs I'm covering, no repeat is made of them. (Task 3,
   `an_approval_from_before_the_deploy_counts_as_sent_out`; Task 4, `reliefs_from_before_the_deploy_stay_in_reliefs_im_covering`;
   Task 9, `no_repeat_of_a_relief_from_before_the_deploy`.)
5. **A planned relief told at once when its teacher is away then, or has since been changed.** Expected: a head cannot choose
   someone away; a choice changed or re-chosen before it goes tells only the teacher it is now, once sent out; the first hears nothing.
   (Task 8, `a_head_s_choice_changed_before_it_goes_tells_only_the_new_teacher`.)

---

## The order, and why

Times first (every gate reads them), then the AI picking at once (on its own). Task 3 then lands the `sent_out` mark, the Send out
routes and Today's two Send out buttons together, so that the app never has a state in which an approval reaches nobody and nobody can
press Send out; the many Telegram tests change there, by one rule (`give()` sends out). Tasks 4 to 6 finish what "has reached its
teacher" and the quiet times mean everywhere; the new messages come after, each on its own.

1. Times in Relief settings, and school hours (`relief/hours.py`)
2. The AI picks at once for any date, nearest first within the guard
3. The "sent out" mark and Send out (held until the earliest send-out time)
4. "Has reached its teacher" everywhere, and Send out on Telegram
5. Today: states, counters, lines and the next school day after the cut-off
6. Quiet times by kind
7. The morning message and the late request (in place of the `new` ping)
8. Planned relief: a head's own choice approved and sent out at planning, and chosen again
9. The repeats: 24 hours before and on the morning
10. Relief needed again: an approved relief whose teacher is away goes back to open
11. The relief message by link, Who covers you, and `/relief`'s last sentence
12. The blocked-bot alert to the team, with its History line by "The app"
13. The work reminders at 18:00 and 07:00
14. Finish: the guides, the notes, the names check, every suite

## Decisions taken in this plan (the lead may change any)

1. **The mark is `sent_out = dict(by, at, approved_at)` on the cover.** A cover approved with no `sent_out` key at all was approved
   before this deploy: it counts as sent out at its approval and has reached its teacher at once (no gate), so nobody is messaged
   again and nothing leaves Reliefs I'm covering. Every approval from now on writes `sent_out=None`. Cost if wrong: a record edited by
   hand without the key reads as sent out.
2. **School hours for relief teachers include the cut-off minute** (06:45 to 14:00:59); the team's window ends before it (06:30 to
   13:59:59). Reason: the spec moves a repeat "to 14:00". Cost: a relief for tomorrow sent out at 14:00 exactly goes at once.
3. **On the lesson's own date its teacher's hours open at the earliest send-out time whatever the calendar says**, and a held relief
   never waits past its lesson's own 06:45. Reason: a day the calendar stops knowing (made a holiday) must not hold a relief for ever.
   Cost: none seen.
4. **The AI guard stops the run, it does not fall back**: when 60 picks have gone to the model in ten minutes, the rest of a run stay
   open for the next minute's run (call 29), nearest dates first. Without a model the app's order is used as today. `fill.run`'s answer
   gains `held` only when the guard stopped it. Cost: after the deploy, far dates are picked over some minutes.
5. **Send out is checked like Approve**: it takes the name the page showed (and the approval it showed), refuses `PICK_CHANGED` when
   either changed, checks the teacher is still free, and "Send out {n} approved" sends exactly the rows the page showed, as Approve all
   does. A second press: `This relief is sent out already.`
6. **Copy after a press, not in the spec**: Approve "{name} approved: press Send out to tell them."; Change "{name} chosen and approved:
   press Send out to tell them."; a row's Send out "Sent out."; the top "Sent out {n} reliefs for {day}." ("Sent out 1 relief for
   {day}."), with " They will be sent at {hh:mm}." when they are held; the top button reads "Send out approved" at 0, as "Approve all
   waiting" does. Cost: copy.
7. **A head's own choice is approved and sent out only for a planned absence** (Plan relief for a colleague). A head's own request
   that names a relief teacher (possible through the API alone) waits for the team, as today. A planner's choice saved before this
   deploy (waiting) stays waiting for the team. Cost: one condition each.
8. **The planner may choose again while the relief is still their own choice** (picked by them and approved by them), until the
   lesson starts; once the team has changed it, it is the team's. Refusal once started: `This lesson has started: ask the relief team to
   change it.` Cost: one condition; a head asks the team instead.
9. **The repeats count every message of the relief** (its first, a Remind, the other repeat) for the 12-hour rule, and a repeat missed
   while the app was down is made until the next repeat's moment (the morning one: until the lesson starts), then given up. No repeat
   is made of a relief sent out before this deploy. Cost: a missed repeat is not sent late.
10. **A repeat's form is fixed when it is made** (short line when acknowledged, the relief again when not); if that changes before it
    goes it is dropped and made again in the right form. Kind `repeat`.
11. **Today's line for a head's choice is "Planned by {head} · " and the row's told line** ("Sent 06:45" after the morning repeat). The
    mockup's "· reminded today 06:45" is not built. Cost: one line of copy.
12. **The morning message's lines**, in this order, each left out at 0: waiting for your approval (a waiting pick, or a request to
    change with a new pick); approved, not sent out; sent out: will go at {06:45}; with nobody free (open); sent out already (has
    reached its teacher, acknowledged or not, or asked to change with no new pick). It is made from the records that can be read; a
    damaged file is logged by kind and does not stop it. It is claimed even when there is nothing to cover. Cost: a damaged file's
    lessons are missing from the counts.
13. **"Away:" past eight people**: the first eight, then " · and {n} more". Cost: copy.
14. **The late request is made only between the morning time and the cut-off**: one whose picks come after the cut-off pings nobody.
    Its one-lesson text keeps "Approve, then Send out.". A `new` ping still queued when this is deployed is dropped. Cost: a request sent
    in the last five minutes before the cut-off may ping nobody; it is on Today.
15. **A request to change goes to the team at once inside the team's window, or after the cut-off for a lesson of today until it
    starts; otherwise at the next morning time.** Reason: spec "Quiet times" and call 27. Cost: one asked at 05:00 for today waits until
    06:30.
16. **Today opens on the next school day past the cut-off of a school day, and on a day that is not a school day**; its second day
    button reads "Tomorrow" when that is tomorrow, else the day ("Mon 19 Oct"). The past-the-cut-off line is shown on the next school
    day's view alone, where it is true. Cost: layout.
17. **On Telegram the Send out button names the person as Approve does** (`📤 Send out to {short name}`), and the line after it is
    `📤 Sent out: {name}, {hh:mm}.`, or `📤 Sent out: {name}, {hh:mm}. Will be sent at {hh:mm}.` when held. Cost: copy.
18. **The blocked-bot alert** is kept as a row `alert:{name}:{date}` in the existing `state` table, made within the first team window
    after it and then given up (one a person a day). "They did not get:" names a relief or a repeat by its lesson, any other kind by
    its label in Relief settings, else "Message". It has **Open relief today**, as the mockup shows. Cost: a block found on Friday
    evening is said on Monday at 06:30, not later.
19. **The work reminders' list**: "A, B, C, D, E and {n} more"; never for a backup; only for moments since the bot was connected. Cost:
    copy.
20. **Relief needed again** waits up to five minutes for the new pick, as the late request does, and is not made for a lesson of today
    found before that day's morning time (the morning message counts it). A request to change (state change) whose teacher is away goes
    back to open too.
21. **The spec and the code disagree on the weekly summary's "on time"** (call 28). The code measures "on time" as acknowledged by the
    lesson's start, which never depended on the approval, so it is unchanged. What changes: a relief counts only once it has reached
    its teacher, and "Planned ahead / arranged on the day" goes by when it reached them, not when it was approved.
22. **Question 3.** `/relief`'s "{officer} will be told." is removed; both "{officer} is not on Telegram: please tell them
    yourself." (the form's and `/relief`'s) stay. This is what the lead was shown and approved on 23 Nov; the spec's question 3 now
    says so. Cost: one sentence.
23. **The settings' help line for the morning message says "Not on weekends or holidays."**: the mockup's "or days with no relief
    duty" is stage 2's. `fill_at` is dropped by `settings.load` and kept in the file by `settings.save`.
24. **The absent teacher's own view says "Being arranged"** for a relief approved and not yet acknowledged (call 12), in My absences.
25. **The kinds' labels move to `relief/words.py` (`KINDS`)**, `tgweb.UNSENT` is that same dict, so the alert and the settings list
    read one list. New labels: late "Late request for today", morning "Morning message", needed "Relief needed again", covered "Who
    covers you", unlinked "Bot blocked alert", work "Please set work"; "new" goes.

## File structure

| File | Change |
|---|---|
| `relief/hours.py` (new) | the times, the two windows, `reaches_at`, `before_moment`, the stage 2 seams `duty_day`, `on_duty` |
| `relief/settings.py`, `static/relief-settings.js` | Task 1: the five times; `fill_at` gone |
| `relief/fill.py`, `relief/pick.py` | Task 2: every open cover due; the guard waits. Task 10: back to open when away |
| `relief/cover.py`, `relief/absences.py` | Task 3: `sent_out`, `send_out`, `send_out_all`, `reached`, `goes_at`. Tasks 8, 10 |
| `relief/web.py`, `static/relief-today.js`, `static/relief.html` | Tasks 3 to 5, 8, 10: routes, rows, counts, the page |
| `relief/tell.py` | Tasks 3, 6, 7, 9 to 13: gates and the new kinds |
| `relief/morning.py` (new), `app.py` | Task 7; Task 12 (`_relief_entry` by "The app") |
| `relief/report.py`, `relief/summary.py`, `relief/bot.py`, `relief/outbox.py` | Task 4; Task 12 (outbox) |
| `relief/asking.py`, `relief/words.py`, `relief/tgweb.py`, `relief/links.py` | Tasks 11, 12 |
| `static/relief.js`, `static/relief-plan.js` | Tasks 4, 8 |
| tests: `test_relief_telegram.py`, `test_relief_team.py`, `test_relief_requests.py`, `test_relief.py`, `test_exams_relief.py`, `test_routes.py`, `relief_today.test.js`, `relief_settings.test.js` | each task's own |
| `docs/DEPLOY.md`, `README.md`, the notes files | Task 14 |

---

### Task 1: Times in Relief settings, and school hours

Spec: "The settings (stage 1)"; My calls 1, 21, 33, 34; "Constraints carried"; "Left to the builder" (the moments).

**Files:**
- Create: `relief/hours.py`
- Modify: `relief/settings.py` (`defaults`, `_check`, `load`, `save`), `static/relief-settings.js` (`times`, about line 86)
- Test: `tests/test_relief_telegram.py`, `tests/test_relief.py` (lines 151, 178, 631 to 636), `tests/relief_settings.test.js`

**Interfaces:**
- Produces, `relief/settings.py`: `defaults(pub)["times"] == dict(remind_at="15:00", report_every=15, weekly_day="Fri", weekly_at="15:00",
  morning_at="06:30", send_from="06:45", cut_off="14:00", work_eve="18:00", work_day="07:00")`; `KEPT_TIMES = ("fill_at",)` (kept in the
  file by `save`, popped by `load`); `ORDER = "The morning message comes at or before the earliest send-out, and both before the
  cut-off."`; labels for "Give a time for {label}.": `morning_at` "Morning message to the relief team at", `send_from` "Earliest send-out
  to relief teachers", `cut_off` "Cut-off for the day's relief", `work_eve` and `work_day` "Remind the absent teacher to set work at".
- Produces, `relief/hours.py` (pure: no Flask, no file; `settings` is `settings.load`'s, `pub` the published timetable):
  - `DEFAULTS` (the five times above as "HH:MM"); `Hours = namedtuple("Hours", "morning send_from cut_off work_eve work_day")` of
    `datetime.time`; `of(settings) -> Hours` (each time from `settings["times"]`, its default when missing or not "HH:MM").
  - `at(date, t) -> datetime` in school time (`fill._tz()`); `school(settings, pub, date) -> bool` (`calendar.school_day` is not None).
  - `duty_day(settings, pub, date) -> bool`: stage 2's seam; `school(...)` in stage 1.
  - `on_duty(settings, date, team) -> list[str]`: stage 2's seam; `sorted(team)` in stage 1.
  - `team_open(now, settings, pub) -> bool`: `duty_day(now.date())` and `morning <= now.time() < cut_off`.
  - `next_morning(now, settings, pub) -> datetime | None`: the first morning time of a duty day at or after `now`, within 60 days.
  - `team_window(at, settings, pub) -> tuple[datetime, datetime] | None`: (start, end) of the first team window that ends after `at`:
    `(at, cut_off of that day)` when `team_open(at)`, else `(next_morning(at), cut_off of that day)`.
  - `teacher_open(now, settings, pub, lesson_date) -> bool`: `now.date() == lesson_date` and `now.time() >= send_from`; or
    `school(now.date())` and `send_from <= now.time()` and `now < at(now.date(), cut_off) + 1 minute`. (Whether the lesson is over is
    the caller's.)
  - `reaches_at(when, settings, pub, lesson_date) -> datetime`: `when` if `teacher_open(when, ...)`; else the earliest send-out time of
    the first school day after `when` (or of `when`'s own day when it is before it), never later than `at(lesson_date, send_from)`,
    never earlier than `when`.
  - `before_moment(start, settings, pub) -> datetime | None`: `start - 24 hours` when that is in teacher hours of a school day (`school`
    and `send_from <= t` and `t <= cut_off`), else the cut-off of the last school day at or before it whose cut-off is not after it,
    within 14 days.
  - `starts(pub, x, c) -> datetime` and `ends(pub, x, c) -> datetime`: the cover's start and end (`exams.days.bounds`; no times: the
    start of its day and the start of the next).

- [ ] **Step 1: Write the failing tests** (`tests/test_relief_telegram.py`, at the end)

```python
# ---- Send-out, Task 1: the times and school hours ----
from relief import hours as HR  # noqa: E402
D = datetime.date
def t_(day, hm): return datetime.datetime.fromisoformat(f"2026-10-{day:02d}T{hm}:00+08:00")

@t
def the_times_are_the_settings_with_their_defaults():
    with school():
        h = HR.of(rs()); assert [f"{v:%H:%M}" for v in h] == ["06:30", "06:45", "14:00", "18:00", "07:00"]
        assert "fill_at" not in rs()["times"] and HR.of(dict(times=dict(cut_off="25:00", morning_at=None))).cut_off == datetime.time(14)
        assert HR.on_duty(rs(), D(2026, 10, 13), [TEAM, LEE]) == sorted([TEAM, LEE]), "stage 1: the whole team"
        assert HR.duty_day(rs(), SCHOOL, D(2026, 10, 13)) and not HR.duty_day(rs(), SCHOOL, D(2026, 10, 17)), "a Saturday"

@t
def the_team_window_and_school_hours_by_the_clock():
    with school(calendar=dict(TERM, holidays=[dict(start="2026-10-15", end="2026-10-15", name="Made-up holiday")])):
        s = rs(); team = lambda d, hm: HR.team_open(t_(d, hm), s, SCHOOL); open_ = lambda d, hm, lesson: HR.teacher_open(t_(d, hm), s, SCHOOL, D(2026, 10, lesson))
        assert [team(12, hm) for hm in ("06:29", "06:30", "09:10", "13:59", "14:00", "21:00")] == [False, True, True, True, False, False]
        assert not team(17, "09:10") and not team(15, "09:10"), "a weekend, a holiday"
        assert [open_(12, hm, 13) for hm in ("06:44", "06:45", "14:00", "14:01", "21:00")] == [False, True, True, False, False]
        assert open_(13, "14:05", 13) and not open_(13, "06:30", 13), "after the cut-off, only its own day; never before 06:45"
        assert not open_(17, "09:10", 19) and not open_(15, "09:10", 16), "a weekend, a holiday"
        assert HR.next_morning(t_(12, "21:00"), s, SCHOOL) == t_(13, "06:30") and HR.next_morning(t_(14, "21:00"), s, SCHOOL) == t_(16, "06:30")

@t
def a_held_relief_goes_at_the_next_start_of_school_hours():
    with school():
        s = rs(); r = lambda d, hm, lesson: HR.reaches_at(t_(d, hm), s, SCHOOL, D(2026, 10, lesson))
        assert r(12, "09:10", 14) == t_(12, "09:10") and r(12, "21:00", 13) == t_(13, "06:45") and r(16, "21:00", 21) == t_(19, "06:45")
        assert r(13, "06:30", 13) == t_(13, "06:45") and r(13, "14:05", 13) == t_(13, "14:05"), "after the cut-off, a lesson of that day goes at once"

@t
def a_held_relief_never_waits_past_its_own_morning():
    with school(calendar=dict(TERM, holidays=[dict(start="2026-10-13", end="2026-10-16", name="Made-up holiday")])):
        assert HR.reaches_at(t_(12, "21:00"), rs(), SCHOOL, D(2026, 10, 14)) == t_(14, "06:45"), "its day is a holiday now: still its own morning"
    with school(calendar=dict(terms=[], holidays=[])):
        assert HR.reaches_at(t_(12, "21:00"), rs(), SCHOOL, D(2026, 10, 13)) == t_(13, "06:45") and HR.teacher_open(t_(13, "06:45"), rs(), SCHOOL, D(2026, 10, 13))

@t
def twenty_four_hours_before_moves_to_the_last_cut_off():
    with school():
        b = lambda d, hm: HR.before_moment(t_(d, hm), rs(), SCHOOL)
        assert b(19, "09:20") == t_(16, "14:00"), "a Monday lesson: Friday at 14:00"
        assert b(14, "15:00") == t_(13, "14:00") and b(15, "07:40") == t_(14, "07:40")
```

In `tests/test_relief.py`: line 151 expects the new `times` dict (no `fill_at`); line 178's bad time uses `times=dict(cut_off="25:00")`; the
loop at line 631 walks `remind_at`, `weekly_at`, `morning_at`, `send_from`, `cut_off`, `work_eve`, `work_day` with their labels; line 636
checks `d["times"]["cut_off"] == "14:00"`. Add, in `tests/test_relief.py`:

```python
@t
def the_three_times_are_in_order_and_fill_at_stays_in_the_file():
    raises(ValueError, lambda: S.save(base(times=dict(morning_at="06:50", send_from="06:45")), PUB, "x"), S.ORDER)
    raises(ValueError, lambda: S.save(base(times=dict(send_from="14:00", cut_off="14:00")), PUB, "x"), S.ORDER)
    S.save(base(times=dict(morning_at="06:45", send_from="06:45", cut_off="13:00")), PUB, "x")
    store.write_json(S.PATH, dict(store.read_json(S.PATH, {}), times=dict(fill_at="15:30")))   # a file saved by the last version
    assert "fill_at" not in S.load(PUB)["times"] and S.load(PUB)["times"]["morning_at"] == "06:30", "unread; the defaults"
    S.save(base(), PUB, "x"); assert store.read_json(S.PATH, {})["times"]["fill_at"] == "15:30", "kept in the file"
```

In `tests/relief_settings.test.js`, `SETTINGS.times` gains the five keys; one test:

```js
t("the times card: the three times in place of Fill open lessons at, and the work reminders", async () => {
  const p = await opened({ "GET admin": ok(TOKEN) }), text = p.text("#main");
  for (const x of ["Morning message to the relief team at", "One message on Telegram with everything waiting for today. Not on weekends or holidays.",
                   "Earliest send-out to relief teachers", "Nothing reaches a relief teacher before this time of a school day, whenever Send out was pressed. School hours for relief teachers run from here to the cut-off.",
                   "Cut-off for the day's relief", "After it, nobody on the team is pinged about today, and the team works on the next school day. Until the next morning message, the team is not disturbed.",
                   "Remind the absent teacher to set work at", "the evening before, and", "on the day", "Only while a lesson of that day has no work. Any absence, asked or planned."]) assert.ok(text.includes(x), x);
  assert.ok(!text.includes("Fill open lessons at"));
  for (const k of ["morning_at", "send_from", "cut_off", "work_eve", "work_day"]) assert.ok(p.$(`input[data-t="${k}"]`), k);
});
```

- [ ] **Step 2: Run them to see them fail**: `.venv/bin/python tests/test_relief_telegram.py` (no module `relief.hours`), `tests/test_relief.py`, `node tests/relief_settings.test.js`.
- [ ] **Step 3: Implement** the interfaces. `_check` validates each of the seven times as today's three ("Give a time for {label}.", "{v} is not
  a time like 15:00."), then `morning_at <= send_from < cut_off` else `ORDER`; it returns `times` without `fill_at`. `save` copies the old
  file's `times.fill_at` into what it writes when there was one. The page: `times()` draws, in this order, the three new lines (each an
  `<input type="time" data-t>` with its label as `aria-label`, and its help as `<div class="small muted">`), the existing remind_at line,
  the work reminder line with two inputs (`aria-label` "Remind the absent teacher to set work at, the evening before" and "..., on the
  day"), then the report and weekly lines as today. `fill.py` keeps reading `times.get("fill_at")` until Task 2: it now gets `None` and its
  fallback (15:00), as before.
- [ ] **Step 4: Run the suites** (node: `relief_settings.test.js`).
- [ ] **Step 5: Commit** `Relief: the morning, send-out and cut-off times, and school hours`.

### Task 2: The AI picks at once for any date, nearest first within the guard

Spec: "The AI picks at once (stage 1)"; My calls 2, 29.

**Files:**
- Modify: `relief/fill.py` (`_run` step 2, `_one`, `due_at`'s parameter, the module docstring), `relief/pick.py` (`choose_for`, `WAIT`)
- Test: `tests/test_relief_team.py` (`run_fills_only_what_is_due`, `due_at_today_is_now_and_monday_is_friday_at_fill_time`)

**Interfaces:**
- Produces: `pick.WAIT` (a module constant object); `pick.choose_for(..., wait=False)`: with `wait=True`, an `ask` answered `BUSY` returns
  `WAIT` in place of the app's order (any other fallback as today). `fill._one(...)` returns `"held"` for `WAIT`; `_run` stops its loop at
  the first `"held"`; `fill.run(...) -> dict(picked, nobody)`, with `held=<covers left>` only when the guard stopped it.
  `fill.due_at(cal, days, date, at, today=None)` (its time parameter renamed; `nudge` and the planned reminder still use it with
  `remind_at`). `fill._run` no longer reads `times.fill_at`.
- Rule: step 2 picks every open cover whose lesson is not over and not stopped, of any date, and every request to change with no new pick,
  in `_covers`' order (date, period): the nearest first.

- [ ] **Step 1: Write the failing tests** (`tests/test_relief_team.py`, at the end; its helpers `ft`, `mon`, `absent`, `st`, `first`)

```python
# ---- Send-out, Task 2: picked at once, nearest first ----
@ft
def every_open_lesson_is_picked_at_once_whatever_its_date():
    fresh()
    a = absent(dates=("2026-10-16",))["id"]; b = absent(teacher=RUTH, dates=("2026-10-13",))["id"]
    got = FL.run(now=mon("09:00"), call=first)
    assert got == dict(picked=3, nobody=0) and st(a, KF) == "waiting" and st(b, KR6) == "waiting", "Friday too, on Monday at 09:00"

@ft
def a_full_guard_leaves_the_rest_open_for_the_next_run():
    fresh()
    far = absent(dates=("2026-10-16",))["id"]; near = absent(teacher=RUTH, dates=("2026-10-13",))["id"]
    with stand_in(PK, "GUARD_N", 1):
        PK._seen.clear(); got = FL.run(now=mon("09:00"), call=first)
        assert got == dict(picked=1, nobody=0, held=2) and st(near, KR2) == "waiting" and st(far, KF) == "open", "the nearest first; not the app's order"
        assert [h["by"] for h in cov(near, KR2)[2]["history"]] == ["ai"]
        PK._seen.clear(); FL.run(now=mon("09:01"), call=first); assert st(far, KF) == "waiting"
    PK._seen.clear()
    with stand_in(PK, "CALL", None), stand_in(PK.typed, "enabled", lambda: False): fresh(); i = absent()["id"]; assert FL.run(now=mon("09:00"))["picked"] == 2 and cov(i, K2)[2]["pick"]["by"] == "app", "no model: the app's order, as today"
```

(`stand_in` is copied into `tests/test_relief_team.py` from `tests/test_relief_telegram.py`, as there.)

- [ ] **Step 2: Run them to see them fail.**
- [ ] **Step 3: Implement** the interfaces. Change `run_fills_only_what_is_due` by this rule only: where it asserted that a cover of a later date stays
  open until its fill time, it now asserts it is picked at the first run; its name becomes `run_fills_every_open_cover`. In
  `due_at_today_is_now_and_monday_is_friday_at_fill_time` only the parameter name changes (it stays the planned reminder's time). Update the
  module docstring (no fill time; the guard waits).
- [ ] **Step 4: Run the suites.** Tests elsewhere that counted picks of one date after `FL.run()` with no ids now see later dates picked too:
  each is put right by counting what the new rule picks, named in the commit message.
- [ ] **Step 5: Commit** `Relief: the AI picks as soon as a request is in, for any date`.

### Task 3: The "sent out" mark and Send out

Spec: "Approve and Send out (stage 1)" ("When it goes", "Pressed for tomorrow at 21:00"); "A day, in order"; My calls 4, 5, 6, 33;
"Alternatives considered" (not in the queue); "Left to the builder" (the mark's shape; a held relief changed and cancelled before 06:45).

**Files:**
- Modify: `relief/cover.py` (`OPEN`, `_approve`, `change`, new functions and sentences), `relief/absences.py` (`COVER`), `relief/web.py`
  (two routes, `STEPS`, `_row`, `today`'s counts, `_told`, `STALE`), `relief/tell.py` (`_of_cover`), `static/relief-today.js` (`buttons`,
  `paintActs`, `onClick`, the approve and choose messages, the note), `tests/test_routes.py`
- Test: `tests/test_relief_telegram.py` (helpers and the old tests by the rule below), `tests/test_relief_team.py` (Today's counts),
  `tests/relief_today.test.js`

**Interfaces:**
- Produces, `relief/cover.py`:
  - `OPEN` gains `sent_out=None`; `absences.COVER` gains `"sent_out"`. `_approve` and `change` write `sent_out=None` with each approval.
  - `sent_out(c) -> dict | None`: `c["sent_out"]` while its `approved_at` is `c["approved"]["at"]`; for a cover approved with no
    `sent_out` key (before this deploy) `dict(by=approved.by, at=approved.at, approved_at=approved.at, legacy=True)`; else None.
  - `goes_at(c, x, settings, pub) -> datetime | None`: when it reaches (reached) its teacher: the legacy mark's `at`; else
    `hours.reaches_at(sent_out.at, settings, pub, x["date"])`; None when not sent out.
  - `reached(r, x, c, now, settings, pub) -> bool`: state in `("approved", "acknowledged", "change")` and `now >= goes_at(...)`.
  - `send_out(id, ckey, who, by, pub, settings, links=None, approved_at=None) -> record`: under the lock: state `approved` (else
    `NOT_TO_SEND`), not sent out for this approval (else `SENT_ALREADY`), `c["relief"] == who` and `approved_at` in (None,
    `c["approved"]["at"]`) (else `PICK_CHANGED`), not stopped (`NOT_HAPPENING`), still free (`still_free`, else `NOT_FREE_OUT`); writes
    `sent_out=dict(by=by, at=now, approved_at=c["approved"]["at"])` and history `dict(what="sent out", who=who, by=by, at=now, why=None)`.
  - `send_out_all(date, shown, by, pub, settings, links=None) -> dict(sent=[(id, ckey, who)], skipped=[dict(id, ckey, name, why)])`:
    `shown=[dict(id, ckey, who, approved_at)]`, as `approve_all` (`_shown` parses it; past dates `PAST_LESSON`; one save a record).
  - Sentences: `NOT_TO_SEND = "This relief is not approved yet."`, `SENT_ALREADY = "This relief is sent out already."`,
    `NOT_FREE_OUT = "{name} is no longer free then: change it"`; `web.STALE` is `cover.NOT_FREE_OUT`.
- Produces, `relief/web.py`:
  - `POST /api/relief/absences/<id>/covers/<path:ckey>/send-out` `{who, approved_at}` (gate `TEAM`): `_change`; history `"sent out"`,
    words `f"sent out {who}'s relief for {_cover_words(r, ckey)}"`; `STEPS["sendout"] = ("sent out", <those words>, None)`.
  - `POST /api/relief/today/send-out` `{date, covers: [{id, ckey, who, approved_at}]}` (gate `TEAM`) -> `dict(sent: n, at: ISO | None,
    skipped)`: `at` the earliest `goes_at` of those sent that are held (None when none is); one history entry for the press, no absence:
    `"Sent out {n} reliefs for {day}"` ("Sent out 1 relief for {day}"); none when nothing was sent.
  - Today's row gains `out`: `"unsent"` (approved, not sent out), `"held"` (sent out, not reached), `"sent"` (reached), None for the other
    states; `goes_at` (ISO or None); `sent_out` (`dict(by, at)` or None). `counts` gains `unsent` and `held`; `approved` counts state
    `approved` with `out == "sent"` alone. `_told` is None unless `out == "sent"`.
- Produces, `relief/tell.py`: `_of_cover` makes the relief message only when `cover.reached(r, x, c, w.now, w.settings, w.pub)`.
- Produces, `static/relief-today.js`: `out(r)` is `r.out` or, for a row without it, `"sent"` in an approved state (old answers draw as
  before); top button `data-td="send-all"` "Send out {n} approved" / "Send out approved" (off at 0), after Approve all; row button
  `data-td="send-out"` "Send out" (class primary) for state `approved`, `out(r) === "unsent"`, not stale; Approve answers "{name} approved:
  press Send out to tell them."; Change "{name} chosen and approved: press Send out to tell them."; Send out "Sent out."; the top after
  Send out all "Sent out {n} reliefs for {day}." plus " They will be sent at {hh:mm}." when `at`, then one line a skipped row as Approve all
  says them; `T.follow` gains a row on Send out, not on Approve. The note: "Nothing reaches a relief teacher until someone on the relief
  team approves it and sends it out."

- [ ] **Step 1: The rule of change for the old tests, and the helpers** (`tests/test_relief_telegram.py`, before any new test)
  - `give(i, ckey, who_, by=TEAM)` becomes chosen, approved and sent out: `CV.change(...)`, then `CV.send_out(i, ckey, who_, by, SCHOOL, rs())`.
    Its comment says so. New helper `out(i, ckey, by=TEAM)`: `CV.send_out` with the cover's relief as `who`.
  - A test that approves with `CV.approve`, `CV.approve_all`, `on_cover(..., "approve")`, `/approve-all` or Telegram's Approve and then
    expects a relief message, a report line or a Remind gets `out(i, ckey)` (or a press of the new routes) right after, and nothing else
    changes. Known to need it (from the approving tests): `approve_queues_the_relief_once` (its first sweep after Approve now queues
    nothing; then `out`, then the rest as it was), `a_moved_relief_tells_the_first_teacher_once`, `an_ask_waits_for_the_pick_then_goes`,
    `a_request_to_change_is_moved_kept_or_still_waiting`, `approve_needs_the_team_right_and_the_pick_shown`, `a_moved_relief_pressed_late_says_so`,
    `a_takeover_moves_the_cover_and_the_button_finds_it`, `two_presses_at_once_save_once`, `every_save_asks_for_a_sweep_once_after_its_history_entry`
    (one more save: Send out), `the_report_never_carries_a_reason`, `nothing_is_sent_when_nothing_waits`, and any other the run names.
  - A test whose relief is given or sent out outside school hours and expects it told then (the clock before 06:45, or after 14:00 for a
    later day's lesson) presses at 09:00 instead, unless the hour is what it tests. `nothing_goes_before_approval` keeps its hours (it
    asserts nothing) and gains: approved, not sent out, nothing either.
  - `tests/test_relief_team.py`: `today_lists_covers_in_time_order_with_counts_and_no_reason` and any test asserting `counts` gain
    `unsent` and `held`; an approved row not sent out moves from `approved` to `unsent`. `tests/relief_today.test.js`: every `p.acts()`
    list gains `"Send out approved (off)"` after the Approve all entry; `day()`'s counts gain `unsent: 0, held: 0`.
- [ ] **Step 2: Write the failing tests**

```python
# ---- Send-out, Task 3: the mark and Send out ----
SEND_ALL = "/api/relief/today/send-out"
def sending(i, ckey, who_=SAM): return dict(id=i, ckey=ckey, who=who_, approved_at=approved_at(i, ckey))

@t
def approve_alone_tells_nobody():
    with school(SAM, MAYA, TEAM):
        i = absent(by=HUGO); CV.set_pick(i, K5, dict(who=SAM, by="ai", reason="Free then.", at=clock.now), SCHOOL, rs())
        on_cover(TEAM, i, K5, "approve", dict(who=SAM))
        assert swept() == 0 and told_of("relief") == [] and covered(i, K5)[2]["sent_out"] is None
        on_cover(TEAM, i, K5, "send-out", dict(who=SAM, approved_at=approved_at(i, K5)))
        assert told_of("relief") == [("relief", SAM)] and covered(i, K5)[2]["sent_out"] == dict(by=TEAM, at=clock.now, approved_at=approved_at(i, K5))
        assert f"Relief for {EVE} on Tue 13 Oct: sent out {SAM}'s relief for 1A, 1B Science (G2) P6–P7 on Tue 13 Oct" in [e["text"] for e in entries()]
        assert on_cover(TEAM, i, K5, "send-out", dict(who=SAM), code=400)["error"] == "This relief is sent out already."
        CV.change(i, K5, MAYA, TEAM, SCHOOL, rs()); swept(); assert ("relief", MAYA) not in told_of(), "a new approval needs a new Send out"
        give(i, K5, MAYA); swept(); assert ("relief", MAYA) in told_of(), "give sends out"

@t
def send_out_is_checked_like_approve():
    with school(SAM, TEAM):
        i = absent(by=HUGO); CV.change(i, K5, SAM, TEAM, SCHOOL, rs())
        for body, why in ((dict(who=MAYA), CV.PICK_CHANGED), (dict(who=SAM, approved_at="2026-10-01T09:00:00+08:00"), CV.PICK_CHANGED)):
            assert on_cover(TEAM, i, K5, "send-out", body, code=400)["error"] == why
        absent(teacher=SAM, dates=("2026-10-13",)); assert on_cover(TEAM, i, K5, "send-out", dict(who=SAM), code=400)["error"] == "Mr Sam Tan is no longer free then: change it"
        assert on_cover(SAM, i, K5, "send-out", dict(who=SAM), code=403)["error"] == "Only the relief team can open What's in."

@t
def send_out_all_sends_what_the_page_showed():
    with school(SAM, MAYA, TEAM):
        i = absent(by=HUGO); CV.change(i, K2, MAYA, TEAM, SCHOOL, rs()); CV.change(i, K5, SAM, TEAM, SCHOOL, rs())
        got = call(TEAM, "post", SEND_ALL, dict(date="2026-10-13", covers=[sending(i, K2, MAYA), dict(sending(i, K5), who=RUTH)]))
        assert (got["sent"], got["at"], [(v["ckey"], v["why"]) for v in got["skipped"]]) == (1, None, [(K5, CV.PICK_CHANGED)])
        assert "Sent out 1 relief for Tue 13 Oct" in [e["text"] for e in entries()] and told_of("relief") == [("relief", MAYA)]

@t
def pressed_at_21_00_it_waits_for_06_45():
    with school(SAM, TEAM):
        at("21:00"); i = absent(by=HUGO); CV.change(i, K5, SAM, TEAM, SCHOOL, rs())
        got = call(TEAM, "post", SEND_ALL, dict(date="2026-10-13", covers=[sending(i, K5)])); assert got["at"] == "2026-10-13T06:45:00+08:00"
        row_ = next(v for v in call(TEAM, "get", "/api/relief/today?date=2026-10-13")["rows"] if v["ckey"] == K5)
        assert (row_["out"], row_["goes_at"], row_["told"]) == ("held", "2026-10-13T06:45:00+08:00", None)
        at("06:44", day=13); assert swept() == 0 and told_of("relief") == []
        at("06:45", day=13); swept(); assert said(SAM)[-1].startswith("🔔 Relief for you · Tue 13 Oct")

@t
def a_held_relief_goes_as_the_record_is_at_06_45():
    with school(SAM, MAYA, TEAM):
        at("21:00"); i = absent(by=HUGO); give(i, K5, SAM); give(i, K2, MAYA)
        at("22:00"); absences.set_work(i, K5, dict(text="Read p. 5", link="", files=[], known=[]), HUGO)
        CV.change(i, K2, RUTH, TEAM, SCHOOL, rs())                     # changed, not sent out again
        at("23:00"); j = absent(teacher=RUTH, by=HUGO); give(j, day_key_of(RUTH, 6), MAYA); absences.cancel(j, "Better", HUGO)   # Maya is free at P7 since K2 went to Ruth
        at("06:45", day=13); swept()
        assert told_of("relief") == [("relief", SAM)] and "Work from Ms Evelyn Koh: Read p. 5" in said(SAM)[-1], "new work goes; the changed and the cancelled do not"

@t
def an_approval_from_before_the_deploy_counts_as_sent_out():
    with school(SAM, TEAM):
        i = absent(by=HUGO); CV.change(i, K5, SAM, TEAM, SCHOOL, rs())
        change_record(i, lambda r: [x.pop("sent_out") for x in r["lessons"] if x["key"] == K5])   # as the last version wrote it
        r, x, c = covered(i, K5); assert CV.sent_out(c)["legacy"] and CV.reached(r, x, c, TE._time(clock.now), rs(), SCHOOL)
        q(TE.relief_key(EVE, K5, approved_at(i, K5)), SAM, kind="relief"); put(TE.relief_key(EVE, K5, approved_at(i, K5)), state="sent")
        at("21:00"); assert swept() == 0, "told already: never again"
        row_ = next(v for v in call(TEAM, "get", "/api/relief/today?date=2026-10-13")["rows"] if v["ckey"] == K5); assert row_["out"] == "sent"
```

(`day_key_of(name, p)` is a new two-line helper beside `day_key`: the key of that teacher's lesson at period p on 13 Oct.)

`tests/relief_today.test.js`:

```js
t("Send out: the top button and the row's, what each sends and says", async () => {
  const u = row({ out: "unsent", told: null }), w = inState("waiting", { ckey: "k2", key: "k2", p: 1, n: 1 });
  const p = await today(day([u, w], { counts: { need: 2, waiting: 1, approved: 0, unsent: 1, held: 0, acknowledged: 0, change: 0, nobody: 0, open: 0 } }));
  assert.ok(p.acts().includes("Send out 1 approved") && p.btn("Send out") && !p.btn("Send out", "k2"));
  p.steps = ok({}); await p.press("Send out"); assert.strictEqual(p.under(), "Sent out.");
  assert.deepStrictEqual(p.calls.filter(c => c.url.endsWith("/send-out")).map(c => c.body), [{ who: SAM, approved_at: APPROVED.at }]);
  p.steps = ok({ sent: 1, at: "2026-10-13T06:45:00+08:00", skipped: [] }); await p.click("#tdActs button", "Send out 1 approved");
  assert.deepStrictEqual(p.top(), ["Sent out 1 relief for Tue 13 Oct. They will be sent at 06:45."]);
  const q = await today(day([row({ out: "unsent", told: null, stale: true, warn: "Mr Sam Tan is no longer free then: change it" })])); assert.ok(!q.btn("Send out"));
});
t("Approve and Change say that Send out is next", async () => {
  const p = await today(day([inState("waiting")])); p.steps = ok({}); await p.press("Approve"); assert.strictEqual(p.under(), `${SAM} approved: press Send out to tell them.`);
});
```

- [ ] **Step 3: Run them to see them fail** (`CV.send_out` does not exist; 404 on the routes).
- [ ] **Step 4: Implement** the interfaces; add both routes to `tests/test_routes.py` (`"relief_web.send_out": ('relief',)`,
  `"relief_web.send_out_all": ('relief',)`, and both in `RELIEF_INSIDE` with `("relief.team", TEAM_ONLY)`). Update the docstrings of
  `cover.py` (the field), `web.py` (the routes; "Nothing reaches a relief teacher before the team approves it and sends it out") and
  `tell.py` (the relief message is made once it has reached its teacher, never queued early).
- [ ] **Step 5: Apply the rule of Step 1, run the suites** (node: `relief_today.test.js`); then `.venv/bin/python tests/test_relief_telegram.py` alone once more.
- [ ] **Step 6: Commit** `Relief: Send out, a press of its own after Approve, held until the earliest send-out time`, listing every old test touched.

### Task 4: "Has reached its teacher" everywhere, and Send out on Telegram

Spec: "Approve and Send out" (the paragraph "Where the app today means 'has reached its teacher'", the Telegram paragraph); "The asker
told who covers (stage 1)" (the app); My calls 7, 12, 17, 28.

**Files:**
- Modify: `relief/web.py` (`covering`, `_relieves`, `_yours`, `_hidden`, `_lesson_out`), `relief/cover.py` (`_mine`,
  `acknowledge_once`, `ask_change`), `relief/bot.py` (`_theirs`, `_approve`, new `_send_out`, `ACTIONS`, `_Out`, `_settle`),
  `relief/outbox.py` (new `keep_buttons`), `relief/report.py` (`_relief`, `_remindable`, `_remind`), `relief/summary.py` (`_relief`,
  `week`), `relief/tell.py` (`relief_item` gains `base`), `static/relief.js` (`reliefLines`)
- Test: `tests/test_relief_telegram.py`, `tests/test_relief_team.py`

**Interfaces:**
- Consumes: `cover.reached`, `cover.goes_at`, `cover.send_out`, `web.STEPS["sendout"]` (Task 3).
- Produces:
  - `cover.acknowledge_once(id, ckey, me, links=None, reached=None)`, `cover.ask_change(id, ckey, why, me, links=None, reached=None)`,
    `cover._mine(r, x, c, me, reached=None)`: `reached` a callable `(r, x, c) -> bool` asked under the lock; False is `NOT_YOURS_COVER`.
    `web._reached(pub) -> callable` (one `settings.load` a request, `now` at the call). The page's routes and the bot pass it.
  - `web.covering`, `web._relieves` and `web._yours` count a cover only once it has reached its teacher.
  - The absent teacher who may not see everything sees the relief's name only in state `acknowledged` (`_hidden`, `_lesson_out`).
    `reliefLines` in `static/relief.js`: a cover in an approved state with no name shown reads `Being arranged`.
  - `report._relief` counts only reached reliefs; `report._remindable` too; `report._remind`'s `w` gains `settings`;
    `tell.relief_item(pub, reach, told, r, x, c, ckey, base="")` (Remind passes the bot's base).
  - `summary.week`: a relief counts once reached at `now`; `ahead` is `goes_at(...).date() < x["date"]`. "On time" is unchanged (Decision 21).
  - Telegram: `outbox.keep_buttons(name, rows) -> list` (an inline keyboard: tokens made and the rows written into `buttons` for
    `BUTTON_DAYS`, as `_claim` does); `bot._Out` gains `rows` (default None) and `_settle(chat, message, line, rows=None)` puts them on the
    message it edits. After Approve on a request to change: line `✅ Approved: {name}, {hh:mm}.` (as now) and one button
    `dict(text=f"📤 Send out to {short}", what="sendout", id, ckey, who, extra=dict(absent, date, approved_at))`, `short` as Approve's.
    `ACTIONS["sendout"] = ("relief.team", _send_out, (_cover.PICK_CHANGED, _cover.NOT_FREE_OUT, _cover.NOT_HAPPENING))`; its line
    `📤 Sent out: {name}, {hh:mm}.` or `📤 Sent out: {name}, {hh:mm}. Will be sent at {hh:mm}.`; history through `step_saved("sendout")`.

- [ ] **Step 1: Write the failing tests**

```python
# ---- Send-out, Task 4: has reached its teacher ----
def covering_of(name): return [v["ckey"] for v in call(name, "get", "/api/relief/covering")["covers"]]

@t
def nothing_not_sent_out_is_seen_or_answered_by_its_teacher():
    with school(SAM, TEAM):
        i = absent(by=HUGO); f = FI.save(i, "a.pdf", b"made-up"); absences.set_work(i, K5, dict(text="", link="", files=[dict(id=f["id"], name="a.pdf")], known=[]), HUGO)
        CV.change(i, K5, SAM, TEAM, SCHOOL, rs())
        assert covering_of(SAM) == [] and who(SAM).get(f"/api/relief/files/{i}/{f['id']}").status_code == 403
        on_cover(SAM, i, K5, "acknowledge", code=403); on_cover(SAM, i, K5, "ask-change", dict(why="x"), code=403)
        at("21:00"); out(i, K5); assert covering_of(SAM) == [], "held: not yet"
        at("06:45", day=13); assert covering_of(SAM) == [K5] and who(SAM).get(f"/api/relief/files/{i}/{f['id']}").status_code == 200
        assert on_cover(SAM, i, K5, "acknowledge")["state"] == "acknowledged"

@t
def reliefs_from_before_the_deploy_stay_in_reliefs_im_covering():
    with school(SAM):
        i = absent(by=HUGO); CV.change(i, K5, SAM, TEAM, SCHOOL, rs()); change_record(i, lambda r: [x.pop("sent_out") for x in r["lessons"] if x["key"] == K5])
        at("23:00"); assert covering_of(SAM) == [K5], "approved before the deploy: there at any hour"

@t
def the_report_and_remind_count_only_what_reached_its_teacher():
    with school(SAM, MAYA, TEAM):
        at("09:00", day=13); i = absent(by=HUGO); give(i, K5, SAM); swept(); CV.change(i, K2, MAYA, TEAM, SCHOOL, rs())
        at("09:15", day=13); RE.tick(); assert texts_to()[-1] == head("09:15", 1) + "\n• Mr Sam Tan · 1A, 1B Science (G2) P6–P7 · starts 10:30 · sent 09:00", "Maya's, approved and not sent out: neither waiting nor started"
        assert skips(remind(listed(i, K2))) == [(K2, MAYA, "Nobody to remind.")]

@t
def the_absent_teacher_sees_the_name_once_acknowledged():
    with school(SAM):
        i = absent(); give(i, K5, SAM); mine_ = lambda: next(c for x in call(EVE, "get", f"/api/relief/absences/{i}")["lessons"] for c in x["covers"] if c["ckey"] == K5)
        assert mine_()["relief"] is None and mine_()["state"] == "approved"
        on_cover(SAM, i, K5, "acknowledge"); assert mine_()["relief"] == SAM

@t
def on_telegram_approve_then_send_out():
    with school(SAM, MAYA, TEAM):
        i = asked(); swept(); press(TEAM, "approve")
        e = calls("editMessageText")[-1]; assert e["text"].endswith(f"✅ Approved: {MAYA}, 09:10.")
        assert [b["text"] for row in e["reply_markup"]["inline_keyboard"] for b in row] == ["📤 Send out to Ms Lee"] and told_of("relief", MAYA) == []
        press(TEAM, "sendout"); swept(); assert told_of("relief", MAYA) == [("relief", MAYA)] and calls("editMessageText")[-1]["text"].endswith("📤 Sent out: Ms Maya Lee, 09:10.")
        assert {"sent out", "approved"} <= {x["what"] for x in entries()}
```

`tests/test_relief_team.py`: `the_absent_teacher_sees_the_name_only_once_approved` becomes `..._only_once_acknowledged` by that rule;
`covering_lists_only_approved_and_never_the_reason`, `acknowledge_and_ask_change_are_the_relief_teachers_alone` and
`the_relief_teacher_can_open_the_work_file` send out (a helper `sent(i, ckey)` there: `CV.send_out` with the relief's name, by `TEAMER`)
after each approval whose teacher then sees or does something. A JS test in `tests/relief_telegram.test.js` is not needed: `reliefLines` is
checked by a line in the existing `relief.js` page tests where My absences is drawn (`Being arranged` for `{state: "approved", relief: null}`).

- [ ] **Step 2: Run them to see them fail.**
- [ ] **Step 3: Implement** the interfaces. `bot.py` keeps `_cover_of`'s order by `_web.APPROVED`. The Approve line on Telegram is unchanged.
- [ ] **Step 4: Run the suites.** Old tests of Remind, the report and the week whose reliefs come from `give()` are unchanged; those that
  approve another way follow Task 3's rule.
- [ ] **Step 5: Commit** `Relief: a relief has reached its teacher once it is sent out and its time has come; Send out on Telegram`.

### Task 5: Today: states, counters, lines and the next school day after the cut-off

Spec: "What Today shows, by state" (the table), the new counter; "A day, in order" (14:00); mockup tabs 2 to 5; "Left to the builder"
(the 12 px); My call 8.

**Files:**
- Modify: `relief/web.py` (`today`: default date, `hours`, `asked_after`), `static/relief-today.js` (`chip`, `buttons`, `paintHead`,
  `paintTop`, `paintDay`, `init`, `load`), `static/relief.html` (`.td-acts`)
- Test: `tests/test_relief_team.py`, `tests/relief_today.test.js`

**Interfaces:**
- Consumes: Task 3's row fields and counts.
- Produces: `GET /api/relief/today` without `date`: today, or past today's cut-off on a school day, or on a day that is not a school day,
  the next school day (within 30 days; else today). The answer gains `hours = dict(morning="06:30", send_from="06:45", cut_off="14:00",
  today=ISO, next_day=ISO | None, past_cut_off=bool)`; a row gains `asked_after` ("14:10") when its absence was sent today, for today,
  at or after today's cut-off. The page:
  - opens with no date (the server's), and its two day buttons are "Today" and the next school day ("Tomorrow" when that is tomorrow,
    else its day, Decision 16);
  - chip and line under it by state, as the spec's table and the mockup: approved and `unsent`: chip "Approved", line
    `Approved · not sent out`; `held`: chip "Approved", line `Will be sent at {hh:mm}` (its day too, "Tue 13 Oct, 06:45", when that is not
    the date shown); `sent`: as today (told line); acknowledged and the rest as today; a waiting row with `asked_after`: line
    `Asked at {asked_after}, after the cut-off: nobody was pinged`;
  - counters: Lessons to cover, Waiting for you, Approved, not sent out (`unsent`), Approved, not acknowledged (`approved`), Acknowledged,
    Asked to change, No relief teacher yet, Nobody free then (as today);
  - above the rows, while any row is held: `{n} reliefs sent out: they will be sent at {hh:mm} on {day}. You can still change them until
    then.` (`1 relief sent out: it will be sent at {hh:mm} on {day}. You can still change it until then.`); on the next school day's view
    while `past_cut_off`: `Past the cut-off ({cut_off}). Nobody on the team is pinged until the morning message at {morning}. What you send
    out now is sent at {send_from} on {day}.`; under the title while `past_cut_off`: `After {cut_off} the page opens on the next school day`;
  - `.td-acts{justify-content:flex-end}` with `margin-bottom:12px` only on `.td-acts.tg`, set while a bot is connected (stage 4's Minor 9).

- [ ] **Step 1: Write the failing tests**

`tests/test_relief_team.py` (its `rt` style, a made-up clock through `absences._now` and `lessons.today` as its Today tests do):

```python
# ---- Send-out, Task 5: Today after the cut-off ----
@rt
def today_opens_on_the_next_school_day_after_the_cut_off():
    with clock_at("2026-10-12T14:20:00+08:00"):
        j = ok(staff(TEAMER).get("/api/relief/today")); assert (j["date"], j["hours"]["past_cut_off"], j["hours"]["next_day"]) == ("2026-10-13", True, "2026-10-13")
    with clock_at("2026-10-16T21:00:00+08:00"): assert ok(staff(TEAMER).get("/api/relief/today"))["date"] == "2026-10-19", "Friday evening: Monday"
    with clock_at("2026-10-12T13:59:00+08:00"): assert ok(staff(TEAMER).get("/api/relief/today"))["date"] == "2026-10-12"
    with clock_at("2026-10-13T14:10:00+08:00"):
        i = absent(dates=("2026-10-13",))["id"]; rows_ = ok(staff(TEAMER).get("/api/relief/today?date=2026-10-13"))["rows"]
        assert {v["asked_after"] for v in rows_ if v["id"] == i} == {"14:10"}
```

(`clock_at(iso)` is a context manager beside the other helpers there, standing in for `absences._now` and `lessons.today`.)

`tests/relief_today.test.js`:

```js
const HOURS = { morning: "06:30", send_from: "06:45", cut_off: "14:00", today: TODAY, next_day: "2026-10-14", past_cut_off: false };
t("by state: not sent out, will be sent at, asked after the cut-off", async () => {
  const p = await today(day([row({ out: "unsent", told: null }), maya({ out: "held", goes_at: "2026-10-13T06:45:00+08:00", told: null }), inState("waiting", { ckey: "k9", key: "k9", asked_after: "14:10" })], { hours: HOURS }));
  assert.ok(p.state().startsWith("Approved Approved · not sent out") && p.state("k2").startsWith("Approved Will be sent at 06:45"));
  assert.ok(p.state("k9").includes("Asked at 14:10, after the cut-off: nobody was pinged"));
  assert.deepStrictEqual(p.top(), ["1 relief sent out: it will be sent at 06:45 on Tue 13 Oct. You can still change it until then."]);
});
t("past the cut-off: the next school day, its line, and the counters", async () => {
  const p = await today(day([], { date: "2026-10-14", hours: Object.assign({}, HOURS, { past_cut_off: true }), counts: { need: 2, waiting: 2, approved: 0, unsent: 0, held: 0, acknowledged: 0, change: 0, nobody: 0, open: 0 } }));
  assert.ok(p.top().includes("Past the cut-off (14:00). Nobody on the team is pinged until the morning message at 06:30. What you send out now is sent at 06:45 on Wed 14 Oct."));
  assert.ok(p.text("#tdSub").includes("After 14:00 the page opens on the next school day") && p.text("#tdCounts").includes("Approved, not sent out"));
  assert.strictEqual(p.calls.find(c => c.url.startsWith(`${URL}?`)).url, `${URL}?`, "the first reading asks for no date");
  assert.deepStrictEqual(p.all("#tdSeg button").map(b => p.text(b)), ["Today", "Tomorrow"]);
});
t("no bot: no room kept under the buttons at the top", () => {
  assert.ok(!/margin-bottom/.test(css("relief.html", ".td-acts")) && /margin-bottom:12px/.test(css("relief.html", ".td-acts.tg")));
});
```

The old test `at any width there is room between the buttons at the top and the day` (line 200) reads `.td-acts.tg`. The page's first
`GET` now carries no date: the old tests' server stand-in answers any `GET ${URL}?...`, so only tests that assert the first URL change.

- [ ] **Step 2: Run them to see them fail.**
- [ ] **Step 3: Implement** the interfaces. `T.date` is empty until the first answer, then `data.date`; Refresh and the reads after a step keep
  the date shown.
- [ ] **Step 4: Run the suites** (node: `relief_today.test.js`).
- [ ] **Step 5: Commit** `Relief: Today shows what is not sent out, what is held, and opens on the next school day after the cut-off`.

### Task 6: Quiet times by kind

Spec: "Quiet times for the other messages"; "Who gets what" (the Obeys column); My calls 9, 10, 11, 27, 33.

**Files:**
- Modify: `relief/tell.py` (`due`'s `w`, `_relief`, `_of_told`, `_kept`, `_ask`, `_cancelled`, `still_true`, new `TEACHER_KINDS`, `_may`)
- Test: `tests/test_relief_telegram.py`

**Interfaces:**
- Consumes: `hours.teacher_open`, `hours.team_open` (Task 1).
- Produces: `tell.TEACHER_KINDS = ("relief", "repeat", "gone", "moved", "stopped", "again", "kept")`; `tell._teacher_may(now, settings, pub,
  date, ends) -> bool` (`hours.teacher_open(now, ...)` and `now < ends`); `tell._team_may(now, settings, pub) -> bool` (`hours.team_open`).
  In `due`: items of `TEACHER_KINDS` are made only when `_teacher_may` for their lesson; `ask` and `askpick` when `_team_may`, or when the
  lesson is today and `cut_off <= now <` its start; a `cancelled` copy to the team alone (`ref["team"]`) when `_team_may`. In
  `still_true`: before its `CHECKS`, a queued item of `TEACHER_KINDS` is False unless `_teacher_may` now (its date from `ref["date"]`, or
  `ref["ends"][:10]`); a team copy of `cancelled`, `ask` and `askpick` False on the same rule as `due`. Dropped, it is made again when its
  time comes, if still true. Absent teacher, officer, `planned`, `remind`, report, all clear and weekly summary: unchanged.

- [ ] **Step 1: Write the failing tests**

```python
# ---- Send-out, Task 6: quiet times ----
@t
def nothing_reaches_a_relief_teacher_outside_school_hours():
    with school(SAM, TEAM, LEE):
        i = absent(by=HUGO); give(i, K5, SAM); swept()
        at("15:00"); absences.not_needed(i, K5, "x", HUGO); swept(); assert told_of("gone") == [], "after the cut-off, for tomorrow: waits"
        at("06:44", day=13); swept(); assert told_of("gone") == []
        at("06:45", day=13); swept(); assert told_of("gone") == [("gone", SAM)]

@t
def a_message_held_up_past_the_cut_off_waits_for_the_morning():
    with school(SAM):
        at("13:59"); i = absent(by=HUGO); give(i, K5, SAM); TE.sweep(); assert state(f"relief:{EVE}:{K5}:{approved_at(i, K5)}") == "queued"
        at("14:30"); send(); assert state(f"relief:{EVE}:{K5}:{approved_at(i, K5)}") == "dropped" and said(SAM) == [], "the queue was held up: not in the evening"
        at("06:45", day=13); swept(); assert len(said(SAM)) == 1

@t
def the_team_is_not_disturbed_in_the_evening():
    with school(SAM, TEAM, LEE, HUGO):
        i = absent(by=HUGO); give(i, K5, SAM); swept(); at("20:00")
        absences.cancel(i, "Better", HUGO); swept(); assert told_of("cancelled") == [], "the team's copy waits for the morning"
        at("06:30", day=13); swept(); assert sorted(told_of("cancelled")) == [("cancelled", LEE), ("cancelled", TEAM)]

@t
def a_request_to_change_after_the_cut_off_goes_until_its_lesson_starts():
    with school(SAM, MAYA, TEAM, LEE, calendar=TERM, times=dict(cut_off="10:00")):
        at("09:00", day=13); i = absent(); give(i, K5, SAM); swept()
        at("10:10", day=13); on_cover(SAM, i, K5, "ask-change", dict(why="A meeting")); swept()
        assert sorted(n for k, n in told_of("ask")) == [LEE, TEAM], "a relief of today, after the cut-off, before 10:30"
    with school(SAM, MAYA, TEAM, LEE):
        i = absent(dates=("2026-10-14",)); give(i, KW, SAM); swept(); at("20:00"); on_cover(SAM, i, KW, "ask-change", dict(why="x")); swept()
        assert told_of("ask") == [], "tomorrow's, in the evening: at the morning time"
        at("06:30", day=13); swept(); assert len(told_of("ask")) == 2
```

- [ ] **Step 2: Run them to see them fail.**
- [ ] **Step 3: Implement** the interfaces. `still_true` reads the settings and the timetable once a call (`_exams()` plus `settings.load`).
  Update `tell.py`'s docstring (the gates by kind).
- [ ] **Step 4: Run the suites.** Old tests that make `gone`, `moved`, `kept`, `stopped`, `again`, a team `cancelled` or an `ask` at an hour
  outside its window (15:00, 20:00, 23:00 on Mon 12 Oct for Tue's lessons) now find it made at its next window: each moves its clock into
  the window (09:00, or 06:45 on Tue 13 Oct) where the hour is not what it tests, or asserts the wait where it is; named in the commit.
- [ ] **Step 5: Commit** `Relief: quiet times: relief teachers in school hours, the team between the morning time and the cut-off`.

### Task 7: The morning message and the late request

Spec: "The messages" (the morning message, the late request); "What becomes of today's ping"; "A day, in order"; My calls 14, 15, 16,
22, 25 (no late request for a backup); "Left to the builder" (the moments 21:00, 06:30, 06:45, 09:10, 14:05; a weekend, a holiday).

**Files:**
- Create: `relief/morning.py`
- Modify: `relief/tell.py` (`_new` becomes `_late`, `new_text` becomes `late_text`, `TOLD`, `CHECKS`, `BEFORE`'s comment), `relief/tgweb.py`
  (`UNSENT`), `app.py` (`relief_tell.MINUTE.append(relief_morning.tick)` after `relief_report.tick`; `import relief.morning`)
- Test: `tests/test_relief_telegram.py` (new tests; the section `# ---- Answers, Task 3` and `no_ping_before_the_report_starts` by the rule)

**Interfaces:**
- Consumes: `hours.duty_day`, `hours.on_duty`, `hours.team_open`, `cover.sent_out`, `cover.reached`, `cover.goes_at`.
- Produces, `relief/morning.py`:
  - `morning_text(day, absences, lessons, waiting, unsent, held, at, nobody, already, away) -> str`: lines `☀️ Relief today · {day}`,
    `{a} absences · {n} lessons to cover` ("1 absence", "1 lesson"), then each at 1 or more, in this order: `• {w} waiting for your
    approval`, `• {u} approved, not sent out`, `• {h} sent out: will go at {at}`, `• {k} with nobody free: choose someone in the app`,
    `• {s} sent out already`; then `Away: {name} ({whole day or periods}) · ...`, at most eight, then ` · and {n} more`.
  - `counts(pub, settings, records, now, links) -> dict(absences, lessons, waiting, unsent, held, at, nobody, already, away)`: every cover of
    today needing relief (`fill._covers` for today), not stopped as far as known (`tell._stopped`), not over, of an absence not cancelled,
    backups too; by Decision 12.
  - `tick(now=None) -> list[str]` (the keys queued): on a `duty_day`, `morning <= now < cut_off`, `tgdb.get_state("morning_last")` below
    today's ordinal and somebody to tell (`on_duty(settings, today, the reachable team)`); then `tgdb.raise_state("morning_last", ordinal)`
    before anything is queued; nothing more when no lesson is to cover; else `morning:{date}:{name}` (kind `morning`, button
    `[[dict(text=OPEN_TODAY, url=base + "/relief#today")]]`, ref `dict(date, made)`) to each. Never raises; logs by kind.
  - `_fresh(ref, name) -> bool` in `tell.CHECKS["morning"]`: its date is today, now before the cut-off, `tell._on_team(name)`.
- Produces, `relief/tell.py`: kind `late`, key `late:{id}:{name}`, ref `dict(id, date)`; `late_text(absent, away, n) -> str`:
  `🆕 Late request for today · {absent}` / `{away}` / `{n} lessons are waiting for your approval. Approve, then Send out.` (`1 lesson is
  waiting for your approval. Approve, then Send out.`). `_late(w, r)`: as stage 4's `_new` (claimed once, five minutes for its picks,
  never a backup, never to who sent it or the absent teacher), except: sent today at or after today's morning time and before today's
  cut-off, on a `duty_day`, and made only while `_team_may`; the `BEFORE` rule goes from it. `_late_true` (`CHECKS["late"]`): `_new_true`'s
  questions and `_team_may` now. `CHECKS["new"] = lambda ref, name: False` (a ping queued before the deploy is dropped). `TOLD`: `"new:"`
  becomes `"late:"`. `tgweb.UNSENT`: `new` goes; `late="Late request for today"`, `morning="Morning message"`.

- [ ] **Step 1: The rule for the old ping's tests.** In `# ---- Answers, Task 3` and the final fix wave's `no_ping_before_the_report_starts`:
  kind `new` becomes `late`, `new:` keys `late:`, `NEW_EVE` becomes `"🆕 Late request for today · Ms Evelyn Koh\nwhole day\n2 lessons are
  waiting for your approval. Approve, then Send out."`, `TE.new_text` `TE.late_text`; "before the report's start" becomes "before the
  morning time" (06:30: the cases at 06:59 and 07:00 become 06:29 and 06:30, and one sent at 06:00 is in the morning message and pings
  nobody); `only_today_only_since_connected_never_to_who_sent_it` keeps every case. `the_module_stands_alone` and the Answers Task 4 set of
  `tgweb.UNSENT` follow the new kinds.
- [ ] **Step 2: Write the failing tests**

```python
# ---- Send-out, Task 7: the morning message and the late request ----
from relief import morning as MO  # noqa: E402
MORNING_13 = "☀️ Relief today · Tue 13 Oct\n2 absences · 3 lessons to cover\n• 1 waiting for your approval\n• 1 sent out: will go at 06:45\n• 1 sent out already\nAway: Ms Evelyn Koh (whole day) · Ms Ruth Goh (whole day)"
def mornings(): return sorted((r["key"], r["text"]) for r in outs("morning"))
def ticked_m(hm, day=13): at(hm, day); return MO.tick()

@t
def the_morning_message_counts_every_lesson_to_cover():
    assert MO.morning_text("Tue 13 Oct", 1, 1, 0, 0, 0, "06:45", 1, 0, ["Mr A (whole day)"]) == "☀️ Relief today · Tue 13 Oct\n1 absence · 1 lesson to cover\n• 1 with nobody free: choose someone in the app\nAway: Mr A (whole day)"
    assert MO.morning_text("d", 9, 9, 9, 0, 0, "06:45", 0, 0, [f"P{n}" for n in range(10)]).endswith("· P7 · and 2 more")
    with school(SAM, MAYA, TEAM, LEE):
        i = absent(by=HUGO); give(i, K5, SAM); swept()                                     # 09:00 Mon: sent out already
        at("21:00"); give(i, K2, MAYA)                                                      # held until 06:45
        j = absent(teacher=RUTH); FL.run(ids=[j])                                           # one waiting (Ruth's P7)
        assert ticked_m("06:29") == [] and outs("morning") == []
        ticked_m("06:30"); assert [x[1] for x in mornings()] == [MORNING_13] * 2
        assert {r["name"] for r in outs("morning")} == {TEAM, LEE} and all(buttons_of(r) == OPEN_TODAY for r in outs("morning"))
    with school(SAM, TEAM):
        i = absent(by=HUGO); CV.change(i, K5, SAM, TEAM, SCHOOL, rs()); ticked_m("06:30")
        assert "• 1 approved, not sent out" in outs("morning")[0]["text"], "only approved, not sent out: still said, never silence"

@t
def the_morning_message_is_claimed_once_a_day():
    with school(TEAM, LEE):
        absent(dates=("2026-10-13", "2026-10-14")); FL.run(); ticked_m("06:30"); ticked_m("06:31"); assert len(outs("morning")) == 2
        tgdb.set_state("morning_last", None); assert MO.tick() == [] and len(outs("morning")) == 2, "a key is queued once, whatever the mark says"
        assert ticked_m("09:00", day=14) != [] and len(outs("morning")) == 4 and ticked_m("06:30", day=17) == [], "Wednesday: its own; a Saturday: none"
    with school(TEAM, calendar=dict(TERM, holidays=[dict(start="2026-10-13", end="2026-10-13", name="Made-up holiday")])):
        absent(dates=("2026-10-14",)); assert ticked_m("06:30") == [], "a holiday"
    with school(TEAM, LEE):
        absent(); FL.run(); assert ticked_m("09:10") != [] and ticked_m("14:05", day=14) == [], "late after an outage, until the cut-off; not after it"
    with school(TEAM):
        assert ticked_m("06:30") == [] and tgdb.get_state("morning_last") == datetime.date(2026, 10, 13).toordinal(), "nothing to cover: claimed, no message"

@t
def a_whole_day_by_the_clock():
    with school(SAM, MAYA, TEAM, LEE, times=dict(cut_off="11:00")):
        at("21:00"); i = absent(); FL.run(ids=[i]); swept(); assert outs() == [], "the evening: nobody pinged"
        CV.change(i, K2, MAYA, TEAM, SCHOOL, rs()); CV.change(i, K5, SAM, TEAM, SCHOOL, rs())
        call(TEAM, "post", SEND_ALL, dict(date="2026-10-13", covers=[sending(i, K2, MAYA), sending(i, K5, SAM)]))
        ticked_m("06:30"); assert "• 2 sent out: will go at 06:45" in outs("morning")[0]["text"]
        at("06:44", day=13); swept(); assert told_of("relief") == []
        at("06:45", day=13); swept(); assert len(told_of("relief")) == 2
        at("09:06", day=13); j = absent(teacher=RUTH); FL.run(ids=[j]); at("09:10", day=13); swept()
        assert sorted(n for k, n in told_of("late")) == [LEE, TEAM] and outs("late")[0]["text"].endswith("1 lesson is waiting for your approval. Approve, then Send out.")
        at("11:05", day=13); m = absent(teacher=BUSY); FL.run(ids=[m]); at("11:20", day=13); swept(); assert len(told_of("late")) == 2, "after the cut-off: no ping"
        kb = day_key_of(BUSY, 8); who_ = next(n for n in (LEE, TEAM, MAYA, SAM) if CV.still_free(SCHOOL, rs(), absences.all_records(), *covered(m, kb), n))
        give(m, kb, who_); swept(); assert ("relief", who_) in told_of("relief"), "sending allowed: P9 at 12:00 is still to come, it goes at once"
```


- [ ] **Step 3: Run them to see them fail** (`relief.morning` does not exist).
- [ ] **Step 4: Implement** the interfaces. `app.py` imports `relief.morning` with the other relief modules so `CHECKS["morning"]` is set
  wherever the sender runs; the hook is added only where `relief_report.tick` is.
- [ ] **Step 5: Apply the rule of Step 1, run the suites.**
- [ ] **Step 6: Commit** `Relief: the morning message, and the late request in place of the ping for today`, naming every old test touched.

### Task 8: Planned relief: a head's own choice approved and sent out at planning

Spec: "Planned relief (a head's own choice)" ("The lead's rule", "What is written", "When the teacher is told: First"); lead's items 13, 14;
My calls 30, 31, 32, 33; Review Focus 5; "Left to the builder" (`absences.new`, `absences.choose`, `_may_replace`).

**Files:**
- Modify: `relief/cover.py` (new `chose`, `planned_by`), `relief/absences.py` (`new`, `choose`, new `STARTED`, `may_choose`),
  `relief/web.py` (`_row`: `planned_by`; `_lesson_out`: `may_choose`), `static/relief-today.js` (`chip`, the note), `static/relief-plan.js`
  (`mayChoose`, line 41)
- Test: `tests/test_relief_telegram.py`, `tests/test_relief_team.py`, `tests/test_relief_requests.py`, `tests/test_exams_relief.py`

**Interfaces:**
- Consumes: `cover.sent_out`, `hours.reaches_at`.
- Produces:
  - `cover.chose(r, x, c, who, by, now) -> None` (in memory): `_settle`; every name `booked(c)` holds that is not `who` written down as
    dropped; `relief=who`, `relief_by=by`, `pick=dict(who, by="planner", reason=PLANNED.format(by=by, date=_day(now)), at=now)`,
    `approved=dict(by=by, at=now)`, `ack=None`, `change=None`, `sent_out=dict(by=by, at=now, approved_at=now)`; history `pick`, `approved`,
    `sent out` (all by the planner).
  - `cover.planned_by(c) -> str | None`: the planner while the relief is still their own choice (`pick.by == "planner"`, approved by
    `c["relief_by"]`), else None.
  - `absences.new(...)`: for `how == "planned"`, after `_take_over` and before `_save`, each lesson whose relief the planner chose and that is
    not approved gets `cover.chose(...)` (so a backup's approved cover the teacher's own absence took over is left as it was). A head's own
    request (`how == "asked"`) with a choice waits for the team, as today (Decision 7).
  - `absences.choose(id, key, relief_name, by, pub, links=None)`: allowed while the state is `open` or `waiting`, or `cover.planned_by(x) ==
    by` (Decision 8), else `APPROVED_ALREADY`; refused `STARTED = "This lesson has started: ask the relief team to change it."` once the
    lesson's first period has begun; a name: `cover.chose(...)`; none: an approved choice is written down as dropped and the cover goes
    back to open (`OPEN`), to be picked by the AI and approved by the team.
  - `absences.may_choose(r, x, me, pub) -> bool` (one lesson, not split, needed, not started, and the rule above); `_lesson_out` gives it as
    `may_choose` to a viewer who is not hidden.
  - Today's row gains `planned_by`; the page's line for it: `Planned by {head} · {the row's line}` (Decision 11), no Send out button.
    The note: "Nothing reaches a relief teacher until the relief team approves it and sends it out, or a head chooses them when planning."
- Rule of change for old tests: a test that used a planner's choice only to have a pick waiting for the team (then approves it, or counts it
  waiting) makes that pick as a waiting one: new helper `waiting_choice(i, key, who, by)` in each test file that writes the stage 2 shape
  (`relief`, `relief_by`, no `pick`, no `approved`) with `change_record` / `AB._save`, which is what a record from before this deploy holds
  and still reads as waiting. A test about the planner's choice itself expects approved and sent out by the planner. Known to use a
  planner's choice (each is one or the other): in `test_relief_team.py` the 31 tests found by
  `awk '/^def /{n=$2} /AB\.choose|relief=[A-Z]+\)/{print n}' tests/test_relief_team.py | sort -u`, among them
  `a_stage_2_record_reads_as_waiting_with_the_planned_reason` (keeps its meaning: the stage 2 shape stays waiting),
  `approve_makes_it_approved_and_records_who`, `the_planners_pick_stays_in_history`; in `test_relief_requests.py`
  `planning_for_a_colleague_with_a_chosen_relief_teacher`, `work_choosing_and_cancelling`, `management_sees_planned_by_me`; in
  `test_exams_relief.py` `own_absence_takes_over_a_split_lesson_and_a_planners_pick`, `sync_is_idempotent_and_keeps_the_chosen_relief`; in
  `test_relief_telegram.py` the ten found the same way.

- [ ] **Step 1: Write the failing tests** (`tests/test_relief_telegram.py`)

```python
# ---- Send-out, Task 8: a head's own choice ----
def absences_new_error(**kw):
    try: absent(**kw)
    except ValueError as e: return str(e)
    return ""

@t
def a_head_s_choice_is_approved_and_sent_out_at_planning():
    with school(SAM, TEAM):
        i = absent(by=HUGO, lessons=[dict(key=K5, relief=SAM)]); r, x, c = covered(i, K5)
        assert CV.state(r, x, c) == "approved" and c["approved"] == dict(by=HUGO, at=clock.now) and c["sent_out"] == dict(by=HUGO, at=clock.now, approved_at=clock.now)
        assert [h["what"] for h in c["history"]] == ["pick", "approved", "sent out"] and CV.planned_by(c) == HUGO
        swept(); assert told_of("relief") == [("relief", SAM)], "in school hours: at once"
        row_ = next(v for v in call(TEAM, "get", "/api/relief/today?date=2026-10-13")["rows"] if v["ckey"] == K5); assert (row_["out"], row_["planned_by"]) == ("sent", HUGO)
        assert CV.state(*covered(i, K2)) == "open", "a lesson left open waits for the AI and the team"

@t
def a_head_s_choice_in_the_evening_goes_at_06_45():
    with school(SAM):
        at("21:00"); absent(by=HUGO, lessons=[dict(key=K5, relief=SAM)]); swept(); assert told_of("relief") == []
        at("06:45", day=13); swept(); assert told_of("relief") == [("relief", SAM)]

@t
def the_planner_may_choose_again_until_the_lesson_starts():
    with school(SAM, MAYA):
        i = absent(by=HUGO, lessons=[dict(key=K5, relief=SAM)]); swept()
        on_lesson(HUGO, i, K5, "relief", dict(relief=MAYA)); swept()
        assert told_of("moved") == [("moved", SAM)] and ("relief", MAYA) in told_of("relief") and CV.planned_by(covered(i, K5)[2]) == HUGO
        give(i, K5, LEE); assert on_lesson(HUGO, i, K5, "relief", dict(relief=SAM), code=400)["error"] == absences.APPROVED_ALREADY, "the team's now"
    with school(SAM):
        i = absent(by=HUGO, lessons=[dict(key=K5, relief=SAM)]); at("10:30", day=13)
        assert on_lesson(HUGO, i, K5, "relief", dict(relief=MAYA), code=400)["error"] == "This lesson has started: ask the relief team to change it."

@t
def a_head_s_choice_changed_before_it_goes_tells_only_the_new_teacher():
    with school(SAM, MAYA, RUTH, TEAM):
        absent(teacher=RUTH, dates=("2026-10-13",))
        assert "is not free" in absences_new_error(by=HUGO, lessons=[dict(key=K5, relief=RUTH)]), "someone away (and teaching) then cannot be chosen"
        at("21:00"); i = absent(by=HUGO, lessons=[dict(key=K5, relief=SAM)])
        at("22:00"); CV.change(i, K5, MAYA, TEAM, SCHOOL, rs())                    # the team changed it: their Send out is needed
        at("06:45", day=13); swept()
        assert told_of("relief") == [] and told_of("moved") == [] and told_of("gone") == [], "the first never heard; the new one is not sent out"
        out(i, K5); swept(); assert told_of("relief") == [("relief", MAYA)]
    with school(SAM, MAYA):
        at("21:00"); i = absent(by=HUGO, lessons=[dict(key=K5, relief=SAM)])
        at("22:00"); on_lesson(HUGO, i, K5, "relief", dict(relief=MAYA))           # the head chose again
        at("06:45", day=13); swept(); assert told_of("relief") == [("relief", MAYA)] and told_of("moved") == [], "the second at 06:45, the first nothing"
```

`tests/relief_today.test.js`: a row with `planned_by: TEAM` reads `Approved Planned by Mr Hugo Ong · Sent 07:20 ...` and has no Send out.
`tests/test_relief_requests.py`: `every_relief_save_is_one_history_entry_without_the_reason` keeps one entry for a plan with a chosen
teacher (no extra entry for its approval or its Send out).

- [ ] **Step 2: Run them to see them fail.**
- [ ] **Step 3: Implement** the interfaces; the page line in `chip` for `planned_by`; in `static/relief-plan.js` (line 41)
  `mayChoose = x => !x.changed && !x.stopped && x.date >= RF.today() && (x.may_choose === true || !R.approvedOf(x).length) && (x.covers || []).length < 2`.
- [ ] **Step 4: Apply the rule of change, run the suites** (node: `relief_today.test.js`).
- [ ] **Step 5: Commit** `Relief: a head's own choice is approved and sent out when it is planned, and may be chosen again`, naming every old test touched.

### Task 9: The repeats: 24 hours before and on the morning

Spec: "Planned relief" ("When the teacher is told": 24 hours before, on the morning itself, the 12 hours, each once, acknowledged or not,
the short line); My calls 3, 34, 35, 36; "Left to the builder" (keys apart from Remind's `:r{n}`, Remind's wait counting them).

**Files:**
- Modify: `relief/tell.py` (`repeat_text`, `_repeats`, `_of_cover`, `_own`, `Said`, `_REPEAT`, `CHECKS["repeat"]`)
- Test: `tests/test_relief_telegram.py`

**Interfaces:**
- Consumes: `hours.before_moment`, `hours.starts`, `cover.sent_out` (legacy flag), `Said`.
- Produces: kind `repeat`, keys `{relief key}:before` and `{relief key}:morning`; ref = the relief's ref plus `repeat` ("before" |
  "morning") and `acked` (bool). `repeat_text(day, lesson, periods, time, room, absent, today) -> str`:
  `⏰ Reminder · your relief on {day}` (today: `⏰ Reminder · your relief today, {day}`) / `{lesson} · {periods} · {time} · Room {room}` (parts
  left out when empty) / `For {absent}. The work is in the app.`, button `[[dict(text=OPEN, url=base + "/relief#covering")]]`. Not
  acknowledged: the relief message's text and buttons (as Remind sends it). Rule (`_repeats(w, r, x, c, ckey)`, states `approved` and
  `acknowledged`, not a legacy mark): its first message (the relief's own key) sent at `t0`; moments `mb = hours.before_moment(start)` and
  `mm = hours.at(lesson date, send_from)`; `before` while `mb > t0`, `mb <= now < mm`; `morning` while `mm > t0`, `mm <= now < start`; each
  skipped when the last message of the relief (`Said.sent_at`, Remind and the other repeat counted) is less than 12 hours before its
  moment; made only while `_teacher_may`. `Said` reads `:before` and `:morning` as messages of the relief (its `of`, `sent_at`, `last`, so
  Remind's five minutes count them), not as Remind's copies; `_own` takes them as the relief's (gone and moved follow them).
  `_repeat_true` (`CHECKS["repeat"]`): `_relief_true` without its `n` question, `ref["acked"]` still what the state says, `_teacher_may` now.

- [ ] **Step 1: Write the failing tests**

```python
# ---- Send-out, Task 9: the repeats ----
SHORT_14 = "⏰ Reminder · your relief on Wed 14 Oct\n2A Science · P2 · 08:30–09:00 · Room 2-05\nFor Ms Evelyn Koh. The work is in the app."
def repeats(): return sorted((r["key"].rsplit(":", 1)[-1], r["text"].splitlines()[0]) for r in outs("repeat"))

@t
def planned_on_monday_for_wednesday_three_messages():
    with school(SAM):
        i = absent(by=HUGO, dates=("2026-10-14",), lessons=[dict(key=KW, relief=SAM)]); swept(); on_cover(SAM, i, KW, "acknowledge")
        at("08:29", day=13); swept(); assert repeats() == []
        at("08:30", day=13); swept(); assert outs("repeat")[0]["text"] == SHORT_14 and buttons_of(outs("repeat")[0]) == [[dict(text="Open in the app", url=BASE + "/relief#covering")]]
        at("06:45", day=14); swept(); assert repeats() == [("before", "⏰ Reminder · your relief on Wed 14 Oct"), ("morning", "⏰ Reminder · your relief today, Wed 14 Oct")]

@t
def a_repeat_goes_once_and_not_within_twelve_hours():
    with school(SAM):
        at("10:00"); absent(by=HUGO, lessons=[dict(key=K5, relief=SAM)]); swept()
        at("10:30"); swept(); assert repeats() == [], "24 hours before is within 12 hours of the first message"
        at("06:45", day=13); swept(); swept(); assert [k for k, _ in repeats()] == ["morning"] and outs("repeat")[0]["text"].startswith("🔔 Relief for you"), "not acknowledged: the relief again"
    with school(SAM):
        at("07:00", day=13); absent(by=HUGO, dates=("2026-10-13",), lessons=[dict(key=K5, relief=SAM)]); swept(); at("09:00", day=13); swept(); assert repeats() == [], "planned on the day: one message"
    with school(SAM, calendar=dict(TERM, holidays=[dict(start="2026-10-15", end="2026-10-15", name="Made-up holiday")])):
        absent(by=HUGO, dates=("2026-10-16",), lessons=[dict(key=KF, relief=SAM)]); swept()
        at("13:59", day=14); swept(); assert repeats() == []
        at("14:00", day=14); swept(); assert [k for k, _ in repeats()] == ["before"], "Thursday a holiday: the last cut-off before it"

@t
def no_repeat_of_a_relief_from_before_the_deploy():
    with school(SAM):
        i = absent(by=HUGO, dates=("2026-10-14",)); CV.change(i, KW, SAM, TEAM, SCHOOL, rs()); change_record(i, lambda r: [x.pop("sent_out") for x in r["lessons"] if x["key"] == KW])
        swept(); at("06:45", day=14); swept(); assert repeats() == []

@t
def remind_counts_the_repeats_and_they_count_as_told():
    with school(SAM, TEAM):
        i = absent(by=HUGO, dates=("2026-10-14",), lessons=[dict(key=KW, relief=SAM)]); swept(); at("06:45", day=14); swept()
        assert skips(RE.remind("2026-10-14", [dict(id=i, ckey=KW, absent=EVE)], BY)) == [(KW, SAM, "Sent at 06:45: wait a few minutes.")]
        at("07:00", day=14); absences.not_needed(i, KW, "x", HUGO); swept(); assert told_of("gone") == [("gone", SAM)]
```

- [ ] **Step 2: Run them to see them fail.**
- [ ] **Step 3: Implement** the interfaces; add the key rule to `tell.py`'s docstring.
- [ ] **Step 4: Run the suites.** Old tests that give a relief on Mon 12 Oct for Tue 13 Oct and then sweep on Tue 13 Oct after 06:45 counting
  every message now meet the morning repeat: each acknowledges first where that does not change its meaning, or adds the repeat to what it
  expects; never by weakening the rule. Named in the commit.
- [ ] **Step 5: Commit** `Relief: a relief told before its day is told again 24 hours before and on the morning`.

### Task 10: Relief needed again: an approved relief whose teacher is away goes back to open

Spec: "Planned relief" ("If the relief teacher is away on the day"); "Who gets what" (Relief needed again); My calls 37, 38, 39;
"Left to the builder" (`cover.drop`'s sibling, `free._absent_then`); the test "a relief teacher who falls sick after acknowledging".

**Files:**
- Modify: `relief/cover.py` (`AWAY`, `back_to_open`, `was_away`), `relief/fill.py` (`_run` step 1), `relief/web.py` (`_row`: `away`),
  `relief/tell.py` (`needed_text`, `_needed`, `_of_cover`, `CHECKS`, `TOLD`), `relief/tgweb.py` (`UNSENT`), `static/relief-today.js` (`relief`)
- Test: `tests/test_relief_telegram.py`, `tests/test_relief_team.py`, `tests/relief_today.test.js`

**Interfaces:**
- Produces: `cover.AWAY = "{name} was to cover it and is away then"`; `cover.back_to_open(id, ckey, who, links=None) -> record`: under the
  lock, only while the state is `approved`, `acknowledged` or `change`, the relief is `who` and `free._absent_then(all_records(), who,
  date, p, n, links)` (else the record as it is); history `dropped` by `"app"` with why `AWAY.format(name=who)`; `c.update(OPEN)`.
  `cover.was_away(c) -> dict(who, at) | None`: that entry, while no `approved` or `changed` entry came after it. `fill._run` step 1 also
  sends back to open every approved cover whose relief is away then, for that reason alone (`stale`'s other reasons stay marked on Today);
  step 2 picks it in the same run. Today's row gains `away` (the name) and the page a line `{name} was to cover it and is away then`.
  Kind `needed`, key `needed:{absent}:{ckey}:{at}:{name}`, ref `dict(id, absent, ckey, at, ends)`, to each of the team (stage 2 too):
  `needed_text(day, lesson, periods, absent, who, waiting) -> str`: `🔁 Relief needed again · {day}` / `{lesson} · {periods} · for
  {absent}` / `{who} was to cover it and is away then. A new pick is waiting for your approval. Approve, then Send out.` (no pick: `{who}
  was to cover it and is away then. Nobody else is free then: choose someone in the app.`), button Open relief today. Made while the
  cover is `open` or `waiting` with that `was_away`, its lesson not over, `_team_may`, `at` since the bot was connected, not for a lesson
  of today when `at` is before today's morning time, and (open) five minutes after `at` at least. `_needed_true` asks the same now and
  `_on_team`. `UNSENT["needed"] = "Relief needed again"`.

- [ ] **Step 1: Write the failing tests**

```python
# ---- Send-out, Task 10: relief needed again ----
NEEDED_K5 = "🔁 Relief needed again · Tue 13 Oct\n1A, 1B Science (G2) · P6–P7 · for Ms Evelyn Koh\nMr Sam Tan was to cover it and is away then. A new pick is waiting for your approval. Approve, then Send out."

@t
def a_relief_teacher_who_falls_sick_after_acknowledging():
    with school(SAM, TEAM, LEE):
        i = absent(by=HUGO); give(i, K5, SAM); swept(); on_cover(SAM, i, K5, "acknowledge")
        at("07:00", day=13); absent(teacher=SAM, dates=("2026-10-13",)); FL.run(); swept()
        r, x, c = covered(i, K5); assert CV.state(r, x, c) == "waiting" and c["relief"] != SAM and CV.was_away(c)["who"] == SAM
        assert sorted(n for k, n in told_of("needed")) == [LEE, TEAM] and outs("needed")[0]["text"] == NEEDED_K5, "in the day's hours: at once"
        assert told_of("gone") == [("gone", SAM)], "told, so told it is no longer theirs"
        FL.run(); swept(); assert len(told_of("needed")) == 2, "once"
        row_ = next(v for v in call(TEAM, "get", "/api/relief/today?date=2026-10-13")["rows"] if v["ckey"] == K5); assert row_["away"] == SAM

@t
def only_away_sends_an_approved_relief_back():
    with school(SAM):
        i = absent(by=HUGO); give(i, K5, SAM); j = absent(teacher=RUTH); kr = day_key_of(RUTH, 6)
        change_record(j, lambda r: next(x for x in r["lessons"] if x["key"] == kr).update(relief=SAM, relief_by=TEAM, approved=dict(by=TEAM, at=clock.now), sent_out=None))
        FL.run(); assert covered(i, K5)[2]["relief"] == SAM, "given an overlapping relief: marked on Today, not sent back"
        at("06:10", day=13); absent(teacher=SAM, dates=("2026-10-13",)); FL.run(); at("06:30", day=13); swept()
        assert CV.was_away(covered(i, K5)[2])["who"] == SAM and told_of("needed") == [], "found before the morning message, a lesson of today: the morning message counts it"
```

(The made-up school has no lesson of a relief teacher's own on a later day, so the case "found in the evening, told at the next
morning time" for a later lesson is the same `_team_may` gate as Task 6's `the_team_is_not_disturbed_in_the_evening`.)

- [ ] **Step 2: Run them to see them fail.**
- [ ] **Step 3: Implement** the interfaces. `test_relief_team.py` gains one test that `back_to_open` leaves a cover alone when the relief is
  not `who` any more, and is refused nothing for a cover of a past date (`_past` raises, the run logs it by kind).
- [ ] **Step 4: Run the suites** (node: `relief_today.test.js`, one test for the `away` line).
- [ ] **Step 5: Commit** `Relief: a relief whose teacher is away goes back to open, and the team hears Relief needed again`.

### Task 11: The relief message by link, Who covers you, and `/relief`'s last sentence

Spec: "The messages" (the relief message, Who covers you); "Files by link (stage 1)"; "The asker told who covers (stage 1)"; "Asking for
relief: two ways"; My calls 13, 24, 25, 46, 47; question 3 (Decision 22).

**Files:**
- Modify: `relief/tell.py` (`relief_text`, `_relief`, `_answers` row, `covered_text`, `_covered`, `CHECKS`, `TOLD`), `relief/asking.py`
  (`SENT`, `TOLD`, `_sent`), `relief/tgweb.py` (`UNSENT`)
- Test: `tests/test_relief_telegram.py` (`every_text_is_the_plans` reads stage 4's plan and this plan; `sent_text`'s default tail; the
  files tests by the rule)

**Interfaces:**
- Produces: `relief_text(...)`'s files line `Files: {n}. Open the app to download them.`; the relief message's buttons are its two answers
  and a row `[dict(text=OPEN, url=base + "/relief#covering")]`; no files are queued with it (`files=[]`; `outbox._send_files` stays for
  messages queued before the deploy). Kind `covered`, key `covered:{absent}:{ckey}:{ack at}`, to the absent teacher when reachable:
  `covered_text(day, lesson, periods, start, who) -> str`: `✅ Covered · {day}` / `{lesson} · {periods} ({start})` / `{who} has acknowledged.
  You can reach them if you need to.`; made while acknowledged with that `ack.at`, `ack.at` since the bot was connected, the lesson not
  over, never for a backup (`r.get("exams")`), never when the absent teacher is the relief teacher; `_covered_true` asks the same now.
  `UNSENT["covered"] = "Who covers you"`. `/relief`: `SENT = "✅ Sent to the relief team: {n}, {work}.{officer}"`, `{officer}` is
  `" " + NOT_TOLD.format(...)` when the officer is not on Telegram, else empty; `asking.TOLD` goes.
- Rule of change: tests asserting `Files: {n}, sent after this message.` or that `sendDocument` follows a relief
  (`the_work_and_its_files_go_with_the_relief`, `files_follow_the_message_and_a_failed_file_is_noted` keeps its outbox part with an item
  queued by hand) now assert the new line and no `sendDocument`; every test's expected relief buttons (`relief_buttons`, `approve_queues_the_relief_once`)
  gain the Open in the app row; `sent_text`'s default tail becomes `""`.

- [ ] **Step 1: Write the failing tests**

```python
# ---- Send-out, Task 11: by link, and who covers you ----
COVERED_K5 = "✅ Covered · Tue 13 Oct\n1A, 1B Science (G2) · P6–P7 (10:30)\nMr Sam Tan has acknowledged. You can reach them if you need to."

@t
def files_stay_in_the_app():
    with school(SAM):
        i = absent(by=HUGO); f = FI.save(i, "Sheet 4.pdf", b"made-up"); absences.set_work(i, K2, dict(text="Notes.", link="", files=[dict(id=f["id"], name="Sheet 4.pdf")], known=[]), EVE)
        give(i, K2, SAM); swept(); r, = outs("relief")
        assert r["text"].endswith("\nFiles: 1. Open the app to download them.") and json.loads(r["files"]) == [] and calls("sendDocument") == []
        assert buttons_of(r)[-1] == [dict(text="Open in the app", url=BASE + "/relief#covering")]

@t
def the_absent_teacher_hears_who_covers_each_lesson():
    with school(EVE, SAM, MAYA):
        i = absent(); give(i, K5, SAM); give(i, K2, MAYA); swept(); assert told_of("covered") == []
        on_cover(SAM, i, K5, "acknowledge"); swept(); assert said(EVE)[-1] == COVERED_K5 and told_of("covered") == [("covered", EVE)]
        on_cover(MAYA, i, K2, "acknowledge"); swept(); assert len(told_of("covered")) == 2, "one a lesson"
    with school(EVE, SAM):
        j = absent(); change_record(j, lambda r: r.update(exams=dict(id="made-up", kind="exam"))); give(j, K5, SAM); on_cover(SAM, j, K5, "acknowledge"); swept()
        assert told_of("covered") == [], "a backup: the person is on duty in school"

@t
def relief_says_nothing_of_who_will_be_told():
    assert "will be told" not in AK.SENT and not hasattr(AK, "TOLD") and AK.NOT_TOLD == TE.NOT_TOLD
```

In `every_text_is_the_plans`, the
plan read is stage 4's and this plan's, so the new files line must appear here verbatim: `Files: {n}. Open the app to download them.`

- [ ] **Step 2: Run them to see them fail.**
- [ ] **Step 3: Implement** the interfaces.
- [ ] **Step 4: Apply the rule of change, run the suites.**
- [ ] **Step 5: Commit** `Relief: files by link, Who covers you, and /relief no longer says who will be told`, naming every old test touched.

### Task 12: The blocked-bot alert to the team

Spec: "The messages" (A teacher blocked the bot); "The blocked-bot alert (stage 1)"; lead's item 5; My calls 11, 23; "Left to the builder"
(a blocked bot in the evening).

**Files:**
- Modify: `relief/words.py` (`KINDS`), `relief/tgweb.py` (`UNSENT = words.KINDS`), `relief/links.py` (`note_alert`, `alerts`),
  `relief/outbox.py` (`_blocked`, `WHAT`, `UNLINKED`), `relief/tell.py` (`refused`, `unlinked_text`, `_unlinked`, `due`'s `alerts`,
  `_sweep`, `CHECKS`, `TOLD`), `app.py` (`_relief_entry`; `relief_outbox.UNLINKED.append(...)`)
- Test: `tests/test_relief_telegram.py`

**Interfaces:**
- Produces: `words.KINDS` (today's `tgweb.UNSENT` plus the labels of Decision 25; `tgweb.UNSENT is words.KINDS`).
  `links.note_alert(name, what) -> bool`: state `alert:{name}:{date}` = `dict(at, what)`, written only when that row is not there (one a
  person a day); `links.alerts(since_date) -> dict[(name, date), dict(at, what)]`, one read. `outbox.WHAT = lambda item: "Message"`
  (`tell` sets it to `tell.refused`) and `outbox.UNLINKED = []` (each called with the name); `_blocked`, when it unlinked the person:
  `links.note_blocked`, `links.note_alert(name, WHAT(item))`, then each of `UNLINKED`, each in its own `try`. `tell.refused(item) -> str`:
  a `relief` or `repeat` item `f"Relief for you · {lesson} {periods} on {day}"` from its ref, any other `words.KINDS.get(kind, "Message")`.
  Kind `unlinked`, key `unlinked:{name}:{date}:{member}`, ref `dict(name, date)`, to each of the team (never the person), with Open relief
  today: `unlinked_text(name, what) -> str`: `⚠️ {name} has blocked the bot and is now unlinked.` / `They did not get: {what}.` / `Please tell
  them yourself.`; made while `_team_may` and within `hours.team_window(at)`; `_unlinked_true`: `_on_team` and `_team_may`.
  `app._relief_entry(what, text, absence=None, who=None, via=None)`: `history.by_of(who, via)` when `who` or `via == "app"` (By "The
  app"); `app.py` appends `lambda name: _relief_entry("telegram unlinked", f"Telegram unlinked for {name}: the bot was blocked", via="app")`.

- [ ] **Step 1: Write the failing tests**

```python
# ---- Send-out, Task 12: the blocked-bot alert ----
ALERT_EVE = "⚠️ Ms Evelyn Koh has blocked the bot and is now unlinked.\nThey did not get: Relief planned.\nPlease tell them yourself."

@t
def a_blocked_bot_in_the_evening_is_told_to_the_team_in_the_morning():
    with school(EVE, TEAM, LEE):
        at("21:00"); absent(by=HUGO); TE.sweep()                                         # "Relief planned for you" to Eve: no quiet time
        f, seen = tele(BLOCKED); with_send(f, send)
        assert links.chat_of(EVE) is None and told_of("unlinked") == []
        assert ("The app", f"Telegram unlinked for {EVE}: the bot was blocked") in [(e["as"], e["text"]) for e in entries()]
        at("06:30", day=13); swept(); assert sorted(n for k, n in told_of("unlinked")) == [LEE, TEAM] and said(TEAM)[-1] == ALERT_EVE
        swept(); assert len(told_of("unlinked")) == 2, "once"

@t
def an_alert_names_any_other_kind_by_its_label():
    assert TE.refused(dict(kind="relief", ref=dict(lesson="1A, 1B Science (G2)", periods="P6–P7", day="Tue 13 Oct"))) == "Relief for you · 1A, 1B Science (G2) P6–P7 on Tue 13 Oct"
    assert TE.refused(dict(kind="planned", ref=dict(id="x"))) == "Relief planned" and TE.refused(dict(kind="exam-made-up", ref=None)) == "Message"
    assert tgweb.UNSENT is WO.KINDS and "new" not in WO.KINDS and WO.KINDS["unlinked"] == "Bot blocked alert"
```

(`tele` and `BLOCKED` are the Telegram stand-ins `a_blocked_chat_is_unlinked` uses. A relief teacher's message cannot meet a block in the
evening any more: Task 6 holds it; a planned absence's message to the absent teacher still goes then, so it is the case tested.)

- [ ] **Step 2: Run them to see them fail.**
- [ ] **Step 3: Implement** the interfaces. `a_blocked_chat_is_unlinked` and the Answers Task 2 tests pass unchanged; the Answers Task 4 test
  of `UNSENT`'s keys follows `words.KINDS`.
- [ ] **Step 4: Run the suites.**
- [ ] **Step 5: Commit** `Relief: the relief team is told when a teacher blocks the bot, and the History says so`.

### Task 13: The work reminders at 18:00 and 07:00

Spec: "Reminding the absent teacher to set work (stage 1)"; lead's item 15; My calls 40 to 45; "Left to the builder" (requests sent at
10:00, 16:00, 23:00, 06:50 and 07:10, for a Monday, and work set between the two).

**Files:**
- Modify: `relief/tell.py` (`work_text`, `work_moments`, `_work`, `_absence`, `CHECKS`, `TOLD`), `relief/tgweb.py` (`UNSENT`)
- Test: `tests/test_relief_telegram.py`

**Interfaces:**
- Consumes: `hours.of(settings).work_eve`, `.work_day`, `hours.at`.
- Produces: `tell.work_moments(date, settings) -> tuple[datetime, datetime]`: (the calendar day before `date` at `work_eve`, `date` at
  `work_day`). Kind `work`, keys `work:{id}:{date}:eve` and `work:{id}:{date}:day`, ref `dict(id, date, which)`, to the absent teacher when
  reachable, with `[[dict(text=OPEN, url=base + "/relief#mine")]]`. `work_text(day, lessons) -> str`: `✏️ Please set work · {day}` / `{n} lessons
  have no work yet: {list}.` (`1 lesson has no work yet: {list}.`; past five: the first five, then ` and {n} more`) / `Set it in the app,
  in My absences. Your relief teacher sees it there.`; `{list}` items `f"{words.class_group(x)} {words.periods_text(x)}"`, joined with
  ", ". Rule (`_work(w, r)`, each date of the absence on its own): its lessons that are needed, not stopped as far as known, not over, with
  no text, link or file; none: nothing. `eve` while `eve <= now < day`; `day` while `day <= now` and a lesson is left; each only when its
  moment is at least 30 minutes after the absence was sent, since the bot was connected, not for a backup, not cancelled. No quiet time
  (Decision: the spec's "on purpose"). `_work_true` asks the same now. `UNSENT["work"] = "Please set work"`. The planned absence's 15:00
  reminder is unchanged.

- [ ] **Step 1: Write the failing tests**

```python
# ---- Send-out, Task 13: please set work ----
WORK_13 = "✏️ Please set work · Tue 13 Oct\n2 lessons have no work yet: 1C Science P3–P5, 1A, 1B Science (G2) P6–P7.\nSet it in the app, in My absences. Your relief teacher sees it there."
def works(): return sorted(r["key"].rsplit(":", 1)[-1] for r in outs("work"))

@t
def work_reminders_by_when_the_request_was_sent():
    with school(): assert TE.work_moments(datetime.date(2026, 10, 19), rs()) == (t_(18, "18:00"), t_(19, "07:00")), "a Monday: Sunday at 18:00"
    for sent, want in (("10:00", ["day", "eve"]), ("16:00", ["day", "eve"]), ("23:00", ["day"])):
        with school(EVE):
            at(sent); absent(); at("18:00"); swept(); at("07:00", day=13); swept(); assert works() == want, sent
    for sent in ("06:50", "07:10"):
        with school(EVE):
            at(sent, day=13); absent(dates=("2026-10-13",)); at("07:00", day=13); swept(); at("07:30", day=13); swept(); assert works() == [], sent
    with school(EVE):
        at("16:00"); i = absent(); at("18:00"); swept(); assert said(EVE)[-1] == WORK_13
        at("20:00"); absences.set_work(i, K2, dict(text="p. 5", link="", files=[], known=[]), EVE); absences.set_work(i, K5, dict(text="p. 6", link="", files=[], known=[]), EVE)
        at("07:00", day=13); swept(); assert works() == ["eve"], "work set between the two: no 07:00"

@t
def work_reminders_never_to_a_backup_or_for_a_lesson_that_does_not_need_cover():
    with school(EVE):
        absent(lessons=[dict(key=K2, needed=False)]); at("18:00"); swept()
        assert "1C Science" not in said(EVE)[-1] and said(EVE)[-1].startswith("✏️ Please set work · Tue 13 Oct\n1 lesson has no work yet: 1A, 1B Science (G2) P6–P7.")
    with school(EVE):
        i = absent(); change_record(i, lambda r: r.update(exams=dict(id="x", kind="exam"))); at("18:00"); swept(); assert works() == []
```

- [ ] **Step 2: Run them to see them fail.**
- [ ] **Step 3: Implement** the interfaces.
- [ ] **Step 4: Run the suites.** Old tests that count every message to the absent teacher on Mon 12 Oct at 18:00 or later, or Tue 13 Oct
  at 07:00 or later, with lessons left without work, gain the reminder in what they expect; named in the commit.
- [ ] **Step 5: Commit** `Relief: the absent teacher is reminded to set work at 18:00 and 07:00`.

### Task 14: Finish: the guides, the notes, the names check, every suite

**Files:**
- Modify: `docs/DEPLOY.md` ("What leaves the server": every message by who gets it and what it holds, with the new ones: the morning message
  to the relief team (counts, the names of who is away and whole day or periods), the late request (whose absence, whole day or periods, how
  many lessons), Relief needed again (the lesson, whose absence, who was to cover it), the blocked-bot alert (who blocked it and which
  message they did not get), the repeats and the relief message (now without files: "Open the app to download them"), Who covers you (the
  lesson and the relief teacher's name, to the teacher who is away), Please set work (the lessons without work, to the absent teacher); the
  `RELIEF_JOBS` row: picks at once for any date, no fill time; section 6 or "When Telegram is down": a message to a relief teacher held up
  past the cut-off waits for the next school hours), `README.md` (the relief team's lines: Approve, then Send out; the morning message; the late
  request; the times in Relief settings; relief teachers told in school hours only, files in the app; a head's own choice approved at
  planning; the absent teacher told who covers each lesson; the work reminders), `docs/superpowers/plans/2026-11-22-relief-stage-4-notes.md`
  ("Open questions" answer 3, "Keep", gains "reversed by the lead on 23 Nov 2026 (item 10): files by link, built:
  2026-11-24-relief-send-out-stage-1"; "What the final review left to the lead", "Work set after the relief teacher was told", still true;
  "the relief team was not pinged ... the ping is built" points to the late request), `docs/superpowers/plans/2026-11-23-relief-telegram-answers-notes.md`
  (A, the ping: "replaced by the morning message and the late request: see 2026-11-24-relief-send-out-stage-1-notes.md"; known limits of A
  marked as of the ping before; open questions 1, 3 and 4 marked: 1 built (History by "The app"), 3 and 4 settled by the morning message).
- Create: `docs/superpowers/plans/2026-11-24-relief-send-out-stage-1-notes.md`: what each task gives (by its commit), the lead's words
  and the approval of questions 2 to 4, the 25 decisions above with their cost if wrong, the rulings made during the build, the copy the
  lead should see (every new sentence of this plan, verbatim, grouped "On Telegram", "In the app"), known limits (below), what stage 2 will
  find (the seams `hours.duty_day`, `hours.on_duty`), and the checks.
- Known limits to carry: a missed repeat is not sent late; the morning message's counts miss a damaged file's lessons; a late request whose
  picks come after the cut-off pings nobody; work set after 06:45 is not sent to the relief teacher (the lead's call 47); a block on Friday
  evening is told on Monday at 06:30; two people may Send out the same rows in one second: one is refused "This relief is sent out already.".

- [ ] **Step 1: Check what is untrue.** `grep -n "sent after this message\|fill time\|Fill open lessons\|approves it, in the app\|not pinged\|Relief asked for today\|files through Telegram" README.md docs/DEPLOY.md docs/superpowers/plans/2026-11-2[23]-*.md`; each hit is put right or pointed to the new notes.
- [ ] **Step 2: Write the docs and the notes** as listed.
- [ ] **Step 3: The names check** (the parts that need no school file), counts only, on the lines added since c797c9b and the commit messages:
  the school's full name 0; bot token and model key shapes 0 (`git diff c797c9b | grep -cE "[0-9]{8,10}:[A-Za-z0-9_-]{35}|sk-ant-"`); em-dashes
  0 in added lines (`git diff c797c9b | grep "^+" | grep -c "—"`). The staff-list part is left to the controller (it needs the school's file).
- [ ] **Step 4: Run every suite once more**, one at a time: all `tests/*.py` and all `tests/*.test.js`; write the counts in the new notes.
- [ ] **Step 5: Commit** `Relief: the send-out, stage 1: guides, notes and the names check`.

# Relief: the absent teacher's timetable and a calendar for Pick dates: notes

Built 26 November 2026 on branch `relief-calendar` (from main 82c0646), in the worktree `tt-relief-calendar`, subagent-driven:
a builder and a reviewer per task, a fix round where a review asked, a whole-branch review on the most capable model, one fix
wave and its re-review. Not pushed, not merged, not deployed.
Design: `../specs/2026-11-26-relief-dates-calendar-design.md` (approved 26 Nov 2026), mockups
`../specs/2026-11-26-relief-dates-calendar-mockups.html` (option A chosen). Plan: `2026-11-26-relief-dates-calendar.md`.

## What this is

The committee lead, looking at the relief page's Plan relief tab, asked two things:

1. A button to see the absent colleague's whole timetable from the form. Built as **"Their timetable ↗"** after the chosen
   name and its Change button: it opens `/timetable#teachers/<name>` (the published page's teacher view, both weeks) in a new
   tab. Plan relief only; not shown for staff added only in the accounts (they have no timetable).
2. A better **Pick dates**: a calendar to click several days or drag across a run, two months side by side. Built on both
   Plan relief and Ask for relief, replacing the date box, "Add this date" and the chips. Today and Tomorrow are unchanged.

## The lead's words (26 November 2026)

- "Is there a button to see her full timetable in here?" and the calendar request (passed on by the session that started this one).
- What the full timetable is for: "Just to see the timetable for the person, in a new tab".
- The button as described (beside the name, new tab, both weeks, Plan relief only): "correct".
- The most dates in one request: "20 school days is fine" (it was 10).
- The calendar's look, from two working mockups: "A, two months" (always side by side; not B, one month that opens the next).
- The behaviour as played back (both forms, grey days skipped by a drag, 20 days, the summary line, shorter date lines on the
  team's pages, Telegram asking unchanged): "Looks right".
- "Approved, plan it", then "Build it".

## What it does now

- **The server** answers `GET /api/relief/school-days` (right: relief) with every school day from today to the end of the last
  term, and for every other weekday in that span why it is off: the holiday's name, "Not in a term" or "Not a school day". It is
  built on the same `school_day()` the lessons read uses, so the calendar greys exactly the days the server would refuse.
  No calendar set, nothing published, or no school day left: the server's own sentence shows in place of the calendar.
- **One absence holds up to 20 school days** (`MAX_DATES = 20`; "Choose up to 20 school days, today or later.").
- **The calendar**: two months side by side (stacked under 640 px), opening on the month of the first school day (in a break,
  the next term). Click a day to tick or untick it; drag across days to tick every school day between (from a ticked day, to
  take them off); grey days (past, weekend, holiday, outside a term, not a timetable day) cannot be ticked and a drag passes
  over them; a click on a grey day says why in the line under the calendar ("Fri 4 Dec: Founders' Day"). At most 20: a drag
  that would pass 20 keeps the first ones from where it started and says "That is 20 school days, the most at one time." The
  line reads "7 school days: Fri 27 Nov – Thu 3 Dec, Mon 7 Dec, Tue 8 Dec" with Clear all. Keyboard: Tab reaches one day,
  arrows move, Enter or Space ticks. On a phone a swipe scrolls the page; a finger drags only after a short hold; a tap ticks.
  The lessons below are read once a click or drag ends.
- **Date lines everywhere use one runs rule**: three or more dates in a row (a weekend keeps the run, a holiday or a missing
  weekday breaks it) read "Mon 30 Nov – Fri 11 Dec"; shorter runs are listed. On What's in (keeping "Today"), My absences,
  Planned by me, the calendar's line, and in `relief/words.py days()` (Telegram messages, the in-app notice, Telegram's asking line).
- `/api/relief/people` items now carry `staff_only`.

## Calls I made on the lead's behalf (the design's "my calls" and the build's rulings)

Each says what it costs if wrong; the lead may change any of them.

1. During a school break the calendar opens on the next term, not on two grey months. If wrong: one press of ‹ to see this month.
2. One runs rule everywhere, so the form and Planned by me read the same; a holiday breaks a run. If wrong: a wording change.
3. Telegram's dates line follows the runs rule; Telegram's own "several days" buttons still offer the next 10 school days
   (asking on Telegram was to stay as it is). If wrong: someone away 15 days asks on the page, not on Telegram.
4. No timetable link for staff added only in the accounts. If wrong: a link that would open the first tab.
5. The calendar is usable by keyboard (arrows, Enter, Space).
6. The server names the reason for every non-school weekday (not only holidays), so the page guesses nothing. Costs nothing visible.
7. A touch long-press menu does not end a touch drag (Android raises one with no menu); a menu that really opens ends it. If wrong:
   a touch drag could stay armed until the next touch, which ends it.
8. A finger drag needs a short hold (about 300 ms); a quick swipe scrolls. If wrong: the hold feels slow; a tap still ticks.
9. "Try again" shows after any failed read except the three fixed sentences (no calendar, nothing published, no school days).
10. After Send, the next Pick dates opens on the first school day's month again.
11. Parked, not fixed: a page left open past midnight keeps yesterday as today (the Today button did so before this work too);
    the server then refuses a past date with "Choose up to 20 school days, today or later." Reload the page.
12. Parked nits: the number 20 is written in four places; the "no school days" sentence is defined twice (a test keeps them equal).

## Checked, and how

- Every suite, on the final code (see the last section for counts).
- Browser, made-up Sample Secondary School on a scratch data folder, real mouse clicks and drags (never events sent from the
  console), at the pane's own size: on both forms a drag across the two months (forward and backward) ticks only school days and
  skips the weekend and the made-up holiday; dragging back takes days off; one click ticks once and a second unticks; Enter
  ticks; ‹ › stop at the ends; the 21st day is refused with the sentence; Send with 20 dates works and Planned by me and My
  absences show the runs line ("Thu 26 Nov – Thu 3 Dec, Mon 7 Dec – Fri 18 Dec, Mon 4 Jan – Thu 7 Jan"); the months sit side by
  side at 645 and 660 px and stack at 600 px; a click on the holiday shows its reason; after Send the calendar opens on the first
  term month. "Their timetable ↗" has `href=/timetable#teachers/Darren%20Lim` and, clicked, showed that teacher's timetable.
- The school's real setup (newest setup file, counts only, nothing copied): its 10 day names all match the school-day rule (39
  school days in 8 made-up weeks with one holiday); its 98 teacher names hold no "/", quote or `<>&`.

## Not tried

- **A real phone or tablet.** The browser tool cannot make a real touch; the hold, the scroll and the tap are covered by node
  tests only. Worth one try on a phone before or after the merge: open Ask for relief, Pick dates, swipe to scroll over the
  calendar (nothing should tick), tap a day, hold a finger on a day then drag.
- **A screen reader** (VoiceOver, NVDA, JAWS): covered by tests of the click rule and the live region only.
- **The link opening a new tab in Chrome**: the in-app browser opened it in the same tab; `target="_blank"` opens a new tab in a
  normal browser.
- The live site's own school calendar: the calendar shows whatever terms and holidays are set in Relief settings there.
- Dark mode: the relief page has none.

## Known limits

- A pen drags at once, like a mouse. On Windows, Ctrl+click ticks a day like a plain click.
- A teacher's link opens the first tab if that name is not on the published timetable (only possible for staff added only in
  the accounts, who get no link).

## The branch and the suites on the final code

Commits on `relief-calendar` after main 82c0646: the design (63f15d5, a576f2d), the plan (7c4fa3e), Task 1 server (2f95815),
Task 2 runs rule (ffae4ce), Task 3 calendar (21565de, fix 792d39e), Task 4 the forms (0657ca5), Task 5 the link (49b0750), the
whole-branch fix wave (89de80f), main d8de366 (PR #113, step 8 side by side) merged in (ed0c864; no file in common), and these notes.

Every suite on ed0c864, quick runs: test_relief_requests 68, test_relief 45, test_relief_team 82, test_relief_telegram 448 (its
one expected "ERROR in web" log line), test_exams_relief 102, test_routes 20, smoke 103, and every other `tests/*.py` and
`tests/*.test.js` file passed (relief_dates 63, relief_inbox 4, relief_settings 25, relief_summary 11, relief_telegram.js 39,
relief_today 59, timetable_page 7 among them); `node --check` clean on every `static/*.js`. The `--full` runs were not made
(no file they cover changed).

To try it after a deploy: Relief → Plan relief → Pick dates; choose an absent teacher and press "Their timetable ↗".

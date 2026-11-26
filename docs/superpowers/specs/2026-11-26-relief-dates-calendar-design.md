# Relief: the absent teacher's timetable, and a calendar for Pick dates

Date: 2026-11-26. Asked by the timetable committee lead while looking at the relief page's **Plan relief** tab.
Mockups (made-up dates): `2026-11-26-relief-dates-calendar-mockups.html` (the lead chose A).

## Why

1. A head planning relief for a colleague wants to glance at that colleague's whole timetable without leaving the
   form ("Is there a button to see her full timetable in here?"). The form lists only the lessons on the chosen dates.
2. Picking dates one at a time (date box, "Add this date", up to 10) is slow for a long absence. The lead wants a
   calendar: click several days, or drag across a run of days, with two months side by side so a run can cross into
   the next month. Absences of up to about four weeks are planned; the lead set the most at **20 school days**.

## Goals

- **The timetable button (Plan relief only).** Once an absent teacher is chosen, a small link-button
  **"Their timetable ↗"** sits after the name and its "Change" button. It opens `/timetable#teachers/<name>` in a new
  tab (`target="_blank" rel="noopener"`): the published page's teacher view, both weeks, as everyone sees it there
  today. The form is left as it is. Ask for relief gets nothing new: the page header already has "Your timetable".
- **The calendar (Pick dates, on Plan relief and on Ask for relief).** It replaces the date box, "Add this date" and
  the date chips under Pick dates on both forms. Today and Tomorrow stay as they are.
  - Two months side by side, always (the lead's choice A): at first the month of the first school day in the server's
    list (this month whenever a school day is left in it) and the month after. `‹` on the left month and `›` on the
    right month move both by one month. `‹` is disabled on that first month; `›` is disabled when the right month holds
    the last school day the server gave. On a narrow screen the second month sits under the first. *(My call, after the
    builder check: during a break the calendar opens on the next term instead of two grey months.)*
  - Weeks start on Monday; seven columns, the weekend narrow or plain.
  - **Click** a school day to tick it; click a ticked day to take it off.
  - **Drag:** press on a school day and move across others; on release every school day between the start day and
    the end day (either direction, across the two months) is ticked. Pressing on a ticked day and dragging takes the
    days in between off instead. While dragging, the days that will be added or taken off are shown in a lighter tint
    (as in the mockup).
  - **Grey days** cannot be ticked and a drag passes over them: days before today, weekends, holidays, days outside
    every term, and weekdays that are not a day of the published timetable. Pointing at one says why: the holiday's
    name, "Weekend", "In the past", "Not in a term", "Not a school day".
  - **At most 20** ticked. A drag that would pass 20 ticks only the first ones from the day it started, up to 20; the
    line under the calendar then says "That is 20 school days, the most at one time."
  - **The line under the calendar**: "7 school days: Fri 27 Nov – Thu 3 Dec, Mon 7 Dec, Tue 8 Dec" (the dates with the
    one runs rule below) and a **Clear all** button; with nothing ticked, "No dates yet. Up to 20 school days."
  - The lessons below are read again once a click or a drag ends (not during a drag), exactly as "Add this date" does
    today, and stay grouped under each date as now.
  - With no school calendar set (no terms), nothing published, or no school day left in the calendar, the calendar is
    replaced by that sentence (the server's own: "Set the school calendar in Relief settings first: …", the gate's, or
    "There are no school days coming up in the calendar." as Telegram says it), and Today and Tomorrow still work as
    today.
- **The limit rises from 10 to 20 school days** for one absence, on the server too: `MAX_DATES = 20` in
  `relief/absences.py`; the refusal becomes "Choose up to 20 school days, today or later." (the same sentence is used
  for a past date, on the page and on Telegram).
- **A long absence's dates read short elsewhere, with one runs rule everywhere.** Where an absence's dates are listed
  in one line, a run of **three or more** dates in which each is the next weekday after the one before (a weekend
  between them keeps the run; a holiday or any other missing weekday breaks it) is joined: "Mon 30 Nov – Fri 11 Dec"
  instead of ten dates. Shorter runs stay listed as today ("Tue 13 Oct, Wed 14 Oct"). The same rule, on purpose
  without the calendar, everywhere: the line under the calendar, What's in (`relief-inbox.js` row, which keeps its
  "Today" word for today's date), My absences (`relief.js` head line), Planned by me (`relief-plan.js` `plannedRow`),
  and on the server `relief/words.py` `days()` (Telegram messages, the in-app notice, and the Telegram asking line,
  which no test lists three dates in). *(My call, after the builder check: one rule, so an absence reads the same in
  the form and, after Send, in Planned by me.)*

## Non-goals

- No change to asking on Telegram (its own "several days" buttons), the Today page, Load, the Weekly summary, the
  relief sheet download, or the relief settings' calendar editor.
- No date range typed as text, no "every Monday" repeats, no new reasons, no change to "Some periods".
- No timetable button on the relief team's pages (What's in, Today); not asked.

## Anti-goals (what would make it a failure even if it works)

- A day the calendar lets you tick being turned down by the server when you press Send ("… is not a school day in the
  calendar"). The page and the server must use one rule.
- The page jumping or redrawing under the pointer during a drag so the drag lands on the wrong day.
- A real name, the school's full name or real calendar data in the repo, tests or mockups.

## Constraints

- Plain JavaScript pages, no libraries; the relief page's scripts in `static/relief.html` (load order matters:
  `relief-form.js`, `relief.js`, then the tab files). Flask blueprint `relief/web.py` for relief routes.
- A browser drag must be checked with the browser tool's real pointer (`left_click_drag`), never with events sent from
  the console; on a phone a drag must work by touch (pointer events).
- The school's real data only as counts; made-up names in tests and samples.

## Approaches considered

1. **The server lists the school days; one shared calendar on the page (chosen).** A new read-only route gives the page
   every school day from today to the end of the last term, with holiday names. Both forms use one calendar file. The
   page greys exactly what the server would refuse, because the list comes from the same `school_day()` that
   `lessons.on_date` uses.
2. **The page works out the school days itself** from the terms and holidays. Same look, but the rule (terms, holidays,
   weekdays in the timetable, odd/even names) would be written twice and could drift.
3. **A calendar that knows only weekends and past days**, the server quietly dropping holidays from a range. Simpler,
   but holidays look tickable and a dropped day surprises.

The lead talked about outcomes and left the how to me; I chose 1.

## The how, as decided

### Server

- **`GET /api/relief/school-days`** in `relief/web.py`, right `relief` (anyone who can open the relief page; both forms
  need it). Reply:
  `{"today": "2026-11-26", "days": ["2026-11-26", ...], "off": {"2026-12-04": "Founders' Day", ...}}` where `days` is every
  date from the school's today (`relief.lessons.today()`) to the last day of the last term (inclusive) for which
  `relief.calendar.school_day(cal, model days, date)` is not None, and `off` names each holiday date in that span (from
  `calendar.holidays[].name`, a holiday covering several days naming each of them). Nothing published or no terms: the
  same refusal, sentence and status, the lessons read gives today (`_gate()`'s, `lessons.NO_CALENDAR`). Terms set but no
  school day from today on: a refusal with "There are no school days coming up in the calendar." (the sentence
  `relief/asking.py` already uses).
  The page works out the other grey reasons itself (before today, weekend, outside the days' span = "Not in a term",
  a weekday missing from `days` but not in `off` = "Not a school day").
- **`MAX_DATES = 20`** and the refusal text in `_iso_dates` with it.
- **`words.days(record)`** follows the one runs rule above.
- **`/api/relief/people`** adds `staff_only` (from `relief_staff`) so the page can leave the timetable button off for
  staff added in the accounts, who have no timetable. `tests/test_relief_requests.py` checks this reply's exact fields
  (`{name, depts}`) and has an 11-date refusal case: both change with this work (21 dates for the refusal).

### Page

- A new file **`static/relief-dates.js`** (loaded after `relief-form.js`, before `relief.js`), one calendar used by both
  forms: `ReliefDates.mount(box, {picked, max: 20, onChange})` or similar; it fetches the school days once per page
  load (shared by both forms) and draws the two months, the line and Clear all.
- `relief-plan.js` `paintDay` and `relief.js` `paintDay` (Ask for relief) mount it under Pick dates in place of the
  date box; `addDate`/`undate` go; `P.picked` / `A.picked` stay the forms' list (sorted ISO dates), so `dates()`,
  `reread()` and Send are unchanged. The calendar is not redrawn by the forms' other repaints while a drag is in
  progress.
- The timetable button in `relief-plan.js` `paintWho` (or next to what `RF.person` draws), shown only when a teacher is
  chosen and that person is not `staff_only`.
- The dates line helper (runs) shared by What's in, My absences and Planned by me, with the same rule as `words.days`.
- Each day is a button: Tab reaches the calendar, arrow keys move between days, Enter or Space ticks.

## Left to the builder

- The route's exact name and reply field names; where the shared runs helper lives on the page.
- How the drag is tracked (pointer events with `elementFromPoint`, as in the mockup, is known to work with a real
  mouse) and the CSS, matching the relief page's look (the mockup's colours come from the page's `.seg .on`).
- Tests: the route (school days, holidays named, no calendar, nothing published, a weekday not in the timetable), the
  20 limit and its sentence (update the two existing assertions in `tests/test_relief_requests.py` and the two in
  `tests/test_relief_telegram.py`), `words.days` runs, and a node test of the calendar's pure parts (ranges, runs,
  the 20 cap) if they are split out.

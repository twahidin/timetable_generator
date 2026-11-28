# Teacher-only periods: notes from the build

Design: `docs/superpowers/specs/2026-11-27-staff-periods-design.md`. Plan: `2026-11-27-staff-periods.md` beside this
file. Built 2026-11-27 and 28 on branch `staff-periods`: eight tasks, each by a fresh builder and checked by a fresh
reviewer, then one review of the whole branch and one round of fixes, with main (PRs #117 and #118) merged in. Then the
published timetable's new look (PR #119) reached main: it was merged in and the box carried into it (a tenth task,
reviewed). Last, PR #120 (relief: changing a request) merged in cleanly.

## What was built

- Step 6, Teachers tab: the list "Teacher-only periods" above "Teacher availability". A row has a name and a place (in
  one cell, the place under the name), who is in it (teachers, departments, or all teachers), the week, the days, and
  the From and To times (in one cell). The table fits its card without sideways scrolling.
- The setup file has a sheet "Teacher-only periods". The agent's skill is version 2026-11.12 and keeps lessons away.
- Step 8: a lesson of a teacher inside a period is a warning on the list (never critical). The board shows each period
  as a fixed box on that teacher's rows.
- The published timetable: the box on the teacher's page, printout and Excel sheet, one line for each period under the
  timetable, and "Who's free" treats the teacher as busy. Classes and students never get it.
- Relief: a teacher in a period is listed as busy with the reason "Teacher-only period: {name}". Nothing asks for cover
  of a period.
- Exams and events: a mark "has {name} then", never a refusal.

## In the published timetable's new look (PR #119)

The new look places everything by the clock. A teacher-only period's box follows it:

- The box runs from its own start to its own end, cut to the day structure: never before the first period starts,
  never after the last period ends. A cut side has a broken edge, and the time reads "3.00 (to 5.30)" or
  "(from 7.00) 8.00". In a narrow box only the period's own start shows ("3.00", "7.00"); the hover text and the line
  under the timetable have the rest.
- The page reaches the box: a teacher whose last lesson ends at 1.30 and who has a box to 4.10 gets a page to 4.10. A
  period wholly outside the day has no box and does not stretch the page.
- A period counts as a lesson for the break rule: the Lunch band is drawn on a day that has a period after lunch.
- The first line of the box is the time, then the name, then the place, as a lesson's box in that look.
- Under the new look a box could now run to its real end (5.30) at little cost, because each page already runs to its
  own last thing. It was kept cut at the end of the day because the lead's answer was "edge is enough". One change in
  `staff_cells` (the cut) would let it run.

## Different from the mockup or the design

1. **The board asks no question.** Part 3 of the mockup drew a box with "Put it here anyway". On the real board a
   lesson dropped or clicked onto a period's time lands at once, and the warning shows on the lesson and on the list.
   That is the board's rule for every place that breaks a Must rule (red places). "Put it here anyway" appears only
   when another lesson already stands there.
2. **The step 6 table's layout.** The mockup had eight columns. The built table has six: the place sits under the name,
   and From and To sit one above the other, so that everything fits the card.
3. **A day typed long.** A day typed in the setup file as "Tuesday" or "Tues" is read and stored as "Tue". An entry that
   is no weekday ("Sat") is a soft fault, "Sat is not a weekday.", and is ignored.
4. **A setup with one week.** A row whose week is Odd or Even is read as Both.
5. **A fault the design did not name:** "Its place is longer than 60 letters." (the page's box stops at 60, so only an
   imported setup can meet it).
6. **A period cut on both sides** (it starts before the first period and ends after the last) reads
   "(from 7.00 to 6.00)" in its box.

## Rulings made while building

Each was made without asking, with what it costs if it is wrong.

1. `ttgen/export.py` finds a period's days with a helper of its own in `ttgen/spec.py` (`staff_day_indexes`), not with
   `verify.rule_days`, because `verify` imports `export`. A test pins that the two agree. If wrong: one small helper is
   doubled.
2. The fault for a place longer than 60 letters is a hard fault. If wrong: one sentence changes in two files.
3. The browser checks inside tasks 4, 5 and 6 were done by the controller, not the builders. If wrong: a page fault is
   found a task or two later than it could have been.
4. The board's box follows the board's own rows. (Checked afterwards: the teacher rows of a day show every teacher, and
   a teacher's whole cycle shows every day, so no box is missing.)
5. The board asking no question for a red place stays (point 1 above). If wrong: a confirm step for red places is its
   own small piece of work.
6. Every teacher's periods show on the full teacher page: to the committee, and to teachers while the shared staff
   codes are still on. That page already shows every teacher's timetable. A teacher signed in with their own password
   gets only their own. If wrong: the full page's rows need a filter by viewer.
7. Two people changing the same field of one row at the same moment (Who, or Days): the last save wins, as for rule
   rows today. If wrong: one person's chip or day is lost and is put back by hand.
8. A department head who renames a provisional teacher named in a period leaves the period with the old name (a head
   may not change step 6). Step 6 then shows "… is not on step 4." until the committee puts it right.
9. The last small commit of the fix round (the wider time boxes) was checked by measurement in a browser, not by a
   reviewer.
10. In the new look the box is cut to the day structure (see the section above). If wrong: one change lets it run to
    its real end.
11. In the new look a period counts as a lesson for the break bands. If wrong: a Lunch band shows on a row where none
    was wanted.
12. The stored printouts' look number (`LOOK`) was not raised: printouts stored before this work hold no period, and a
    publish that brings periods makes its printouts anew.

## Known limits

- A change on step 6 acts on the published timetable, relief and exams only after the next Publish (the design).
- The part of a period after the last period is words in its box, not a length (the design).
- A teacher with no lessons has no timetable page, so a period shows nowhere for them; they are still busy then.
- A teacher renamed after publishing sees no box on their own page until the next Publish (their timetable has the
  same limit).
- A department with both a "Keep free together" rule and a period at the same time gets two warnings for one lesson.
- The place is words: two periods can name the same hall at once and nothing says so.
- Typing a time with the keyboard redraws the row after the first part, as the "Teacher availability" time boxes do
  today. Picking the time works.
- On the board the box's hover text never shows (the box lets clicks and drops through), so the place is not readable
  there. It is on the published page and the printout.
- Exams: on an event of several dates a mark does not say which date; two periods over one exam show only the first;
  a replacement chosen through "away" carries its mark only after the next Make or check.
- A Re-fit step's reason shows the long sentence of step 8's list; the board's own reason shows the short one.

## Checks made

**Suites, on the final code** (commit eca3231, which holds main 712b86f: PRs #117 to #120), each judged by its exit
status: every quick suite, 73 of 73 passed (every `tests/test_*.py`, `tests/smoke.py`, every `tests/*.test.js`,
`node --check static/app.js`, and the skill's copy of `ttgen` equal to `ttgen`). The slow suites, one at a time:
`test_staff_periods` 29, `test_combined` 40, `test_fixes` 77, `smoke` 104, `test_typed` 34, `test_helper` 22, all
passed. Earlier in the build `test_typed --full` and `test_helper --full` failed once on a busy computer; they failed
the same way on main itself in two runs made for comparison, and passed in the last two runs on this branch.

**In a browser, on a scratch server with the made-up secondary sample saved as the school's setup** (window 1440 px):

- Real clicks: "+ Add a teacher-only period"; the day buttons; ✕ on a chip and on a row; an entry of "Things to fix"
  clicked from another tab of step 6; "+ Add block-out"; Undo twice; "Rows: Teachers" on the board; a lesson card; a
  place on the board; a teacher's name (whole cycle).
- Real typing: a period's name and place; a teacher's new name on step 4 (the chip follows; the toast counts
  "1 teacher-only period").
- Real drags on the board (dragstart and drop traced): a lesson to a clean place; a lesson dropped on a box (the drop
  reaches the board, the lesson lands with the warning, the card lies over the box).
- By the select's change: adding a teacher and a department to "Who".
- By a change event sent from the console: a time (the tool cannot type into a time box).
- By a call from the console: Publish (the button's own yes/no question cannot be answered by the tool).
- Looked at: the published teacher page in the light and the dark look; a class page (nothing); "Who's free" at three
  times; the teacher's PDF turned into a picture (all of these before the new look was merged; after it, a sample
  teacher's PDF and page were made by a script and looked at as pictures, light and dark, not clicked through); step 6's table after the fix round (829 px in an 829 px card; the
  time boxes 125 px wide, "03:00 PM" in full; a day saved as "Tuesday" shows as Tue and survives a click on another
  day).
- By a script against the server: a student's page holds no period and the own-periods request answers 403; step 7's
  sums answer; History names the step, the row and the change; publishing again with no new upload carries a rename.

**Not tried in a browser** (the suites cover them): a teacher signed in with their own password seeing only their own
box; Plan relief's busy list; the exams page's group "In a teacher-only period" and its mark; a head's read-only view
of step 6; the Excel sheet opened in Excel; Print from the browser; in the new look, a period's box beside an exam box
on the view of one date, and the board and step 6 again after the last merge (their code did not change in it).

**On the school's real setup** (a scratch copy of the setup only, counts only, deleted afterwards): 99 teachers, 457
lesson rows. One row for all teachers on one weekday, periods 2 to 5: no fault, 99 people, 99 block-outs. Through the
setup file and back: the row identical, 14 rules and 457 lessons before and after. Step 7's sums: 9 findings with and
without the row. No real timetable file was in the test folder, so every planned lesson row was placed once by a
script (not a real timetable): 917 warnings without the row and 1025 with it; the 108 new ones are all
teacher-only-period warnings and equal the 108 lesson-and-teacher pairs on that weekday; none critical; the other
warnings unchanged. 92 teacher pages (teachers with a lesson), 184 boxes, 92 lines, 92 PDFs made in under a second; no
box on any class page; no period in the student page's data; every teacher's figures unchanged.

## Left for later (small, none blocks)

- A workbook day that is no weekday is dropped the first time a day button of that row is clicked.
- `rules_with_staff` is worked out anew on each relief look-up, and `staff_cells` twice per page: cheap today.
- Tests that could be added: a box on a dated view of the published page; two overlapping periods of one teacher on
  the board; a period name with HTML-special letters on the exams page.

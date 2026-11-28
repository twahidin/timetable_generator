# The published timetable's new look, step 1: notes

Notes beside the plan `2026-11-27-timetable-look-step-1.md` and the design `../specs/2026-11-27-timetable-look-design.md`.
Built 2026-11-27 and 28 on branch `timetable-look`, subagent-driven (the lead's choice): a fresh builder and a fresh
reviewer a task, the controller's own look at pictures of each page task, one whole-branch review on the most capable
model, one fix wave, one re-review, then the controller's browser check.

## What was built

1. **The data rule** (`ttgen/export.py` `html_data`). A page that is not the committee's is not sent the teachers'
   allowance, the classes' sizes, a lesson's after-school flag or the checks' after-school list and notes.
2. **The clock sums** on the page (`clk`, `edge`, `cellTime`, `cellStart`, `bandsOf`, `spanOf`, `hourMarks`, `lanes` by
   minutes) and in the PDF (`_mins`, `_clk`, `_bands`, `_span`, `_hours`, `_lanes`, `_box_lines`). The two sets are twins.
3. **The new grid on the page** (`gridHTML`): an hour row above each week, strong hour lines, striped breaks drawn only
   when a lesson follows, each lesson with its time first. Every page that draws a grid follows: class, teacher, room,
   student, the view on one date, the Lessons tab's class grids, the committee's preview.
4. **Who sees what** (`COMMITTEE`): figures, counts of periods and "after school" show to the committee only. A class
   page shows no figures to anyone.
5. **The printout** (`draw_page`): the same look, no figures, no "after school".
6. **Stored files** (`export.LOOK`, `files_look`, `store.files_stale`): files made by an older look are made again once
   after the app starts.

## Rulings made while building (each can be undone)

- **The full time or the start alone goes by the box's real width, not the lesson's length.** The plan said "under 40
  minutes shows the start alone". The page now holds both forms in each box and a CSS container query picks one. The
  design's own words were "when the start and end do not fit the box's width". If wrong: a browser with no container
  queries shows the full time and may clip it in a narrow box.
- **The grid's least width is 1.8 px a minute**, not 2. A usual day then needs about 938 px, close to the old grid's
  948 px, so it fits a 1366 px laptop with no sideways move. At that width a 40-minute lesson shows its start alone and
  a wider window shows its full time.
- **The day names stay in place** when the grid is moved sideways.
- **A cramped printed box keeps its time.** When only one line fits, it is the start time then the title, and the title
  is the part that is cut. The design first said the title stands alone.
- **A two-line printed box keeps its detail.** The time and title share the first line when they fit, with the class and
  room under them. This came from the count below (32 boxes on teachers' pages).
- **The CSV's "Periods" column and the Lessons Table's "Periods" column are the committee's only.** The lead said counts
  of periods are for the committee only; these two were not on the design's list. If wrong: a teacher loses one column.
- **A teacher-mode page keeps its count of problems.** The status label at the top reads it. Only the after-school list
  and the notes are held back.
- **"runs 8.20–8.40 only"** on the date view is written like every other time in the grid (it was 24-hour).
- **The PDF's time line is bold**, as on the page.
- **The PDF's week name stays turned on its side at the left of each week**, as before; it is not repeated in the hour row.
- **SKILL.md's one sentence about the PDF was corrected.** Its version number did not move: the skill reads and writes
  the same files.
- **Who's free keeps its line "Teachers show how many periods they teach that day"** for the viewers who have that tab.
  It is not a timetable page and the count is what the tab is for. An open point for the lead (below).
- **A saved copy of the page (no sign-in) counts as the committee's**: it shows the figures. Only the committee's own
  tools make that file.

## Counts on the school's own timetable (a scratch copy, numbers only, the copy deleted)

26 periods of 20 minutes, 10 days.

- Class pages: 1719 boxes on 32 pages. 32 show the start time alone (a one-period lesson, one a class). No row has
  lessons side by side. On the PDF no box loses its time or its detail line.
- Teacher pages: 2365 boxes on 94 pages. 69 show the start alone. 16 day rows have two lessons side by side, never
  more. On the PDF those 32 boxes lost the detail line before the fix wave; the two-line rule above was made for them.
- Room pages: 1924 boxes on 60 pages. 32 show the start alone. None side by side.
- No PDF page failed to draw.

These counts were taken at the grid's first least width (2 px a minute). At 1.8 px a minute and a 1366 px screen a
40-minute lesson also shows its start alone; on a wider screen it shows the full time.

## What was checked, and how

- Every quick suite and the slow ones on the final code (see the hand-over).
- Pictures of a full made-up timetable from a clean copy of each task's commit: the page in light and dark, the PDF of a
  class, a teacher and a room.
- A scratch server with the made-up timetable published, real pointer clicks: the committee, the shared teacher code and
  the shared student code. No sideways move at 1366 px; no time clipped; the day names stay put at 1000 px; the lesson
  box; the Lessons tab and its Table; the single PDF, the stored class book and the Excel file all download.
- A real browser print of a class page: the heading, two hour rows and ten day rows on one sheet, the legend on the next
  as before.
- The Excel file: 250,086 cells of a workbook written by the old code and by the new are the same (the reviewer's run).

## Not tried

- The view on one date with an exam or an event, in a browser (the scratch server had no school calendar). The page's
  own tests cover it.
- "Preview as it will be published" from step 8, in a browser. It is the same page in the committee's mode.
- A staff member's own page with staff codes off, in a browser. The page's tests cover it.
- A real printer and a real phone.

## For the lead after the deploy

- A single PDF (Download PDF on a page) has the new look at once.
- The stored books (Class PDFs, Teacher PDFs, the zip) are made again by themselves about a minute after the app starts.
  Download the class book two minutes after the deploy and look. If it still has the old look, publishing again makes
  new ones. A failed remake is only in the server's log.
- While the files are being made again the committee page does not say so. The old files stay downloadable until the
  new ones are in place.

## Open points for the lead

1. Who's free shows how many periods a teacher teaches that day, to everyone who has that tab. Keep, or the committee only?
2. "My exam timetable", the Exams tab and duty lines still write times as 13:00. The grid writes 1.00.
3. A page whose only lesson sits between two whole hours shows no hour label (it cannot happen on a real class page).
4. A page for a teacher or a student is still sent the day structure's after-school slots, though nothing shows them.

## What step 2 (the phone day list) builds on

`gridHTML`'s shape (`.ruler`, `.row`, `.track`, `.cell` with `.t` > `.tf` and `.ts`), `cellTime`, `cellStart`,
`bandsOf(v, d)`, `spanOf(v)`, `COMMITTEE`, and the rule that the day names are sticky. Step 2 adds one small answer
from the app (today's school day) for a student's own page.

## Other work on the same drawing

"Lift one group out of a band lesson, and after school on the board" (branch `band-one-group`) and "staff-only periods"
(branch `staff-periods`) both touch the published page. Whichever merges second merges main first and looks at a
teacher's page again.

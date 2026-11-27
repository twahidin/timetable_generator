# The published timetable: a look where the time reads at one glance

Date: 2026-11-27. Branch `timetable-look`. Status: approved by the lead on 2026-11-27. No plan yet, nothing built.

Pictures (made-up names): `2026-11-27-timetable-look-mockup.html` (open with `?a` for the grid, `?p` for the phone list),
`2026-11-27-timetable-look-mockup-a.png`, `2026-11-27-timetable-look-mockup-phone.png`.

## Why

The committee's lead looked at a published class timetable and said the time of a lesson cannot be read at one glance.
Today a lesson's box holds the subject, teacher and room. To know when it is, the reader follows the box up to a top
row of 26 small period numbers and start times. The Even week is far below that row.

The lead also said the page shows things that are "internal planning": the words "after school", the dashed edge on
such a lesson, the number of students and "periods a cycle". A student or a parent has no use for them.

## What the lead decided

1. **Look A.** The same shape as today: days down the side, time across, both weeks on one page. Each lesson shows its
   own start and end time (8.00–9.00). The top row counts in hours, with a strong line down the page at each hour, and
   is repeated above the Even week. Recess, lunch and assembly are striped bands with their names.
2. **No "after school" words and no dashed edge** on a lesson.
3. **No number of students and no "periods a cycle"** on a class page.
4. **No Lunch band** on a day's row when no lesson comes after lunch that day.
5. **The PDF printouts get the same look**, in the same piece of work.
6. **On a phone, a day list**: one day at a time, lessons down the screen with their times. Built as a second step.
7. **Figures on teacher, room and student pages are for the committee only.** Teachers and students do not see them,
   and no printout carries them.
8. **Counts of periods are for the committee only** too: the "· N periods" in the list under a timetable, and the
   "· N periods" in the box that opens on a click.

## Goals

- A reader finds a lesson and reads its time without looking anywhere else.
- The screen, the paper and the phone say the same thing.
- A student, parent or teacher sees no planning words or planning figures.

## Not in this work

- Step 8's board. It has no after-school mark today, and it is not touched.
- The Excel file. Only the committee can download it. It stays as it is, with its figures and its after-school column.
- The Lessons tab's "One page" view (the small blocks) and its Table view, apart from the after-school words (below).
- Lessons later than the day structure allows, and staff-only periods: another session is designing those. This design
  only makes sure the page does not assume a fixed end of the day (see "How long a page is").

## What would make it a failure

- A lesson whose box shows no time on a computer screen.
- A page that still says "after school" to a student or a teacher.
- A printout that looks different from the screen.
- Any of the pages that share the drawing (below) breaking, because only the class page was tried.

## How it works today (checked in the code on main ea073c8)

- `ttgen/timetable_page.html` is one self-contained page. Its last script draws everything. `gridHTML(v)` draws the
  grid for every kind of page: class, teacher, room and student (`classView`, `teacherView`, `roomView`,
  `personalView`), the view on one date (`dated`), the Lessons tab's "Class grids" (`drawLessonGrids`), a student's own
  page (`showPersonal`) and the "Build a timetable from groups" page. `viewHTML(v)` draws the heading, the figures
  (`v.stats`), the tools, the grid, the legend and a note.
- "Preview as it will be published" on steps 8 and 9 is the same template (`draft.preview_page`, `mode="committee"`).
  So it follows with no extra work.
- A lesson is placed by period: `left = p / NP`, `width = n / NP`. `D.times[p]` holds each period's start and end as
  12-hour text ("12.40", "1.00"). `PB` already holds each period's start and end in minutes.
- The day's shape is a row of codes for each day (`v.codes[d]`): `L` lesson time, `F` assembly, `R` recess, `U` lunch,
  `A` an after-school slot (drawn pale yellow), `.` no school (drawn grey).
- A lesson in an after-school slot has `ext` set. It is drawn with a dashed edge, a yellow colour (`D.ext`) and the
  words "after school" (`.cell.ext:after`). The words are also in the lesson dialog, the Lessons table, the Lessons
  tab's "After school only" tick box, the CSV download's "After school" column and the note under the grid.
- The PDF is drawn by `draw_page(c, m, v)` in `ttgen/export.py`, from the same kind of view (`class_view`,
  `teacher_view`, `room_view`, `student_view`). It draws `v["stats"]` at the top right and `v["pdf_subtitle"]` under
  the title. The Excel sheets read `v["subtitle"]`, `v["stats"]` and also `v["pdf_subtitle"]` from the same views
  (`export.py` near line 885: a figure already named in `pdf_subtitle` is not written a second time; `tests/smoke.py`
  pins this).
- Who is looking: `APP.mode` is `committee`, `teacher`, `staff`, `student` or `personal`. A saved copy of the page has
  no `APP` (`MODE` is `"full"`).
- `tests/timetable_page.test.js` runs the page's last script in a small fake DOM. No test looks at a PDF page.

## The approaches

**A. Change the one drawing in place (chosen).** `gridHTML` and `draw_page` are rewritten to the new look. Every page
that uses them follows. One look everywhere, and the preview is right for free. The risk is that a page nobody tried
breaks, so every kind of page is opened in the browser check.

**B. A new drawing for class pages only.** Smaller to try, but teacher, room and student pages would keep the old look,
the two would drift, and the lead would see two kinds of timetable. Not chosen.

**C. One drawing shared by the page and step 8's board.** The published page must work as a single saved file with no
other files, and the board has its own needs (dragging, marks). Not chosen.

For the phone: a second small drawing (`dayListHTML`) chosen by the width of the screen. Making the grid's boxes
re-flow with CSS alone was looked at and dropped: the boxes are placed by position, and side-by-side lessons would not
come out in order.

The lead does not choose between ways of building. A is my call.

## The design

### 1. The clock scale (screen and PDF)

Everything across the page is placed by the clock, in minutes, not by period number.

- **How long a page is.** A page runs from the earliest thing drawn on it to the end of its last lesson, over all its
  days and both weeks. There is no fixed end hour. A class with a lesson that ends at 4.20 gets a page to 4.20; a class
  that ends at 3.20 gets a page to 3.20, with wider boxes. (My call. It also means a lesson later than today's day
  structure needs nothing more from this drawing, as long as its start and end are known in minutes.)
- **The top row** has a label at each whole hour inside the page: "8 am", "9", "10", "11", "12 noon", "1 pm", "2" …
  The first label carries "am" (or "pm" if the page starts after noon), 12 carries "noon", 1 carries "pm". The row is
  drawn at the top and again above each further week, with the week's name at its left ("ODD WEEK", "EVEN WEEK"). A
  school with one week has one row and no week name.
- **Lines down the page:** a strong line at each whole hour, a faint line at each period edge.
- **Period numbers are no longer shown** on the published page or the PDF.

### 2. A lesson's box

- First line: the time, start and end, as the school's times are written today: "8.00–9.00", "12.40–1.40". No am or pm.
- Then the title in bold, then **one** line of detail: what the box holds today (groups, teacher, room), joined with
  " · " as in the mockup ("Jonas · Music Room", "G1 · G2 · G3 · 5 groups"). Three lines in all, so the time does not
  push the room or the teacher out of the box. A line too long for the box is cut with "…", as today.
- A lesson in an after-school slot looks like any other: its subject's colour, a solid edge, no extra words. `D.ext`
  is no longer used for drawing.
- **A narrow box.** When the start and end do not fit the box's width, the box shows the start time only. The full time
  is in the hover text and in the lesson dialog. (My call.)
- **Height.** On screen a row with lessons side by side grows with the number of lessons side by side (today it grows
  to a fixed 1.7 times, whatever the number), so that every lesson shows its three lines. On the PDF a row of the
  smallest height the page allows must still hold the three lines of a lesson that has the row to itself; make the
  type a little smaller if that is what it takes. Where lessons are side by side on a PDF row and there is no room, the
  detail line is dropped first, then the time; when only one line fits, time and title share it if the width allows,
  else the title stands alone.
- The hover text and the lesson dialog keep the day and the time. The dialog loses "· after school".

### 3. Breaks

- Assembly, recess and lunch are striped bands with their names. A narrow band writes its whole name turned on its
  side, as today, and is not shortened (the mockup's "Ass." is not to be copied).
- **A band is drawn in a day's row only when a lesson on that page starts at or after the band's end that day.** This
  is the lead's Lunch rule, used for every break (my call for recess and assembly). A day with no lessons has no bands.
- After-school slots (`A`) and no-school time (`.`) are drawn as plain empty time. No yellow, no grey.

### 4. The view on one date

- One row, as today. It uses the same scale as the whole page, made longer if an exam or event of that day ends later.
- An exam or event box shows its time on its first line, written as a lesson's time is ("1.00–2.30", not "13:00"), and
  is placed and sized by its own start and end in minutes (`it.start`, `it.end`), not by `it.p` and `it.n`, which are
  cut to the day structure.
- A lesson that does not happen stays crossed out. A shortened one keeps its line "runs … only".
- A break band is drawn when a lesson, exam or event of that day comes after it.

### 5. Who sees what

"The committee" here means `APP.mode === "committee"` (the published page opened by a committee member, and the
preview on steps 8 and 9), and a saved copy of the page with no `APP`, which only the committee's own tools make. (The
saved copy is my call.)

| Thing | Committee | Everyone else | PDF | Excel |
|---|---|---|---|---|
| Class page: number of students, periods a cycle | gone | gone | gone | as today |
| Class page: level, home room, form teachers (words under the name) | stay | stay | stay | as today |
| Teacher page: periods a cycle, allowance, most in a day, days teaching | shown | gone | gone | as today |
| Room page: kind, periods used, share of lesson time | shown | gone | gone | as today |
| Student page: class, level, groups, periods a cycle | shown | gone | gone | as today |
| The list under a timetable: "N periods" in each line | shown | gone | gone | as today |
| Lesson dialog: "· N periods" | shown | gone | - | - |
| Dashed edge, yellow colour, "after school" on a lesson | gone | gone | gone | as today |
| Lesson dialog "· after school" | gone | gone | - | - |
| Lessons tab: "After school only" tick box, and the small words in its Table | stay | gone | - | - |
| Lessons tab: the yellow colour in "One page" and in the Table | gone | gone | - | - |
| The link `#lessons?ext` | works | does nothing | - | - |
| Checks tab: "After-school lessons" (the committee's tab already) | stays | - | - | - |
| CSV download: "After school" column | stays | gone | - | - |
| Teacher PDF: "N after-school periods" under the name | - | - | gone | - |

- The class page's line under the name becomes "Sec 1 · home room A1-1 · Form teachers: …". A student page keeps
  "id · Class · level" there. A room page keeps its kind, equipment and what it is made of in words.
- **The data follows the rule, not only the drawing** (`html_data`). A page made for anyone but the committee does not
  carry: the teachers' allowance, the classes' sizes, the after-school flag of a lesson (sent as 0), or the checks'
  problems, after-school list and notes (today the `teacher` mode's page carries all four). With the flag gone from
  those pages, everything "after school" on the page can simply hang on the flag. Find every use of a class's size on
  the page and see that a blank one reads well.
- **The PDF.** `draw_page` stops drawing `v["stats"]` for every kind of page. The line under the title loses
  "N students" (class) and "N after-school periods" (teacher). Because the Excel sheets read `pdf_subtitle` too, give
  the PDF's line its own key, or the Excel sheets theirs, so that every Excel line stays exactly as it is today.
- **The list under a timetable** (the legend). Every line ends, or for a band begins, with a count of periods
  ("· 6 periods", "5 periods · …"). The page leaves the count out unless the committee is looking. The PDF leaves it
  out always. The PDF and the Excel sheets read the same `legend` text from the views today, so the PDF needs its own
  text, or the count its own field, so that every Excel line stays exactly as it is.
- The note under the grid becomes: "Striped bands are breaks. Click a lesson for every group, teacher and room in it."
  The PDF's foot note becomes: "Striped bands are breaks."

### 6. The PDF page

A4 landscape as today, one page a timetable, the legend under the grid. The grid is drawn to the same rules as the
screen: the clock scale, the hour row above each week, strong hour lines, striped bands by the break rule, each box
with its time first. The two hour rows take a little height from the day rows; the legend's room is worked out as
today. The space the figures used at the top right is left empty.

### 7. Print from the browser, and the dark theme

- The Print button prints the grid, never the phone list, fitted to A4 landscape as today.
- The stripes, the hour lines and the hour labels have dark-theme colours.

### 8. The phone day list (the second step)

- **When.** On a screen narrower than about 700 px, a class, teacher, room or student page (a student's own page too)
  shows the day list in place of the grid. The Lessons tab's class grids stay grids.
- **What it shows.** Buttons for the week (when there is more than one) and for the day. Under them, that day from top
  to bottom: the time at the left, and a box with the title and all its lines, in the subject's colour. A break is a
  striped strip with its time and name, by the same break rule. Lessons at the same time are listed one under the
  other with the same time. Tapping a lesson opens the same dialog as on a computer.
- **Which day it opens on.** Today's school day. A student's own page cannot ask `/api/day` today (it needs the
  "timetable" right, and that page has only "own"), so step 2 adds a small answer that gives nothing but the name of
  today's school day ("Odd Mon"), open to anyone who may see a timetable or their own. When the calendar cannot say
  (no terms set, a saved copy), the list opens on today's weekday in the first week, read from the device's clock.
  When today is not a school day, it opens on the first day. It shows the usual timetable for that day. Where the page
  has a date box, choosing a date shows that date, with crossings and exams, as the grid does. (My call.)
- **A way to the whole week.** A small "Whole week" switch shows the grid on the phone, moved sideways with a finger,
  for anyone who wants it. (My call.)
- The heading, the tools, the legend and the note stay around it. The PDF a phone downloads is the same PDF.

## The steps

1. **The grid and the printouts.** Sections 1 to 7: the new grid on every page, who sees what, and the PDF.
2. **The phone day list.** Section 8.

Each step is planned, built, checked and merged on the lead's word, one after the other.

## What the builder must check or decide

- `ttgen/timetable_page.html` keeps many statements on one long line. Use `/* */` inside a line, never `//`. After
  every edit cut the last script out and run `node --check` on it.
- `skill/school-timetable-generator/scripts/ttgen` is a copy of `ttgen`. Find how the repo keeps the two the same, keep
  them the same, and see whether `SKILL.md`'s version number has to move because the skill's printouts change.
- The stored printout books and the zip (`/files/book/…`, `/files/zip`) are made when the timetable is published or
  when a student change runs `store.remake_files`. Single PDFs (`/pdf/…`) are made on request. So after a deploy a
  single PDF has the new look at once, and a stored book keeps the old look, with its "after school" words, until its
  files are made again. Teachers can download the class and teacher books, so the old books must not stay: find the
  smallest safe way to have the stored files made again once after the deploy (the existing `remake_files` and its
  `files_behind` mark are the place to look), and write in the notes file what was done and what the lead must do,
  if anything.
- Tests. `tests/timetable_page.test.js` gets cases for: the time in a lesson's box; start time only in a narrow box; no
  band when no lesson follows; the page's start and end; the hour labels; no figures and no after-school words for
  `teacher`, `staff`, `student` and `personal`; figures for `committee`. Its lines that expect "periods a cycle" on a
  staff page (near 263) and "allowance" on a teacher-mode page (near 275) change, and so may the lines of
  `tests/smoke.py` that pin `pdf_subtitle` (near 1225, 1253 and 1274). For the PDF: move the sums (the page's start and end, the bands of a row, a box's lines) into
  small functions and test those with plain asserts, and look at pages rendered to pictures.
- The browser check opens every kind of page in both themes, the one-date view with an exam, the Lessons tab's class
  grids, the preview on step 8, the browser's print preview and, in step 2, a phone-width screen, and tries the old
  controls on each as well as the new look.
- Count on a scratch copy of the school's real published timetable (counts only, the copy deleted after): how many
  boxes fall back to the start time only, and how many PDF boxes lose their time or their detail line for lack of
  height. If either is more
  than a few, come back before going on.
- A period length that does not divide the hour: the hour lines are placed by minutes, so they need not fall on a
  period edge. Try it once with a made-up school.

## Other work that touches the same drawing

The design "lift one group out of a band lesson, and after school on the board" (branch `band-one-group`, file
`docs/superpowers/specs/2026-11-27-band-one-group-and-after-school-design.md`, approved 2026-11-27, not built) fits
this one as follows: a lesson put after school by hand has `ext` set, so the rules here cover it; the small
"after school" mark on step 8's board is that design's work, not this one's; and for a late time the lead raises
"Periods in a day" on step 2, which gives every page empty late columns. A page that ends at its own last lesson
(section 1) does not show them.

Another session is designing staff-only periods on timetables. That and the design above
would change `gridHTML`, `draw_page` or the data they read. Build them one after the other, not side by side, and
merge main into whichever comes second before its browser check.

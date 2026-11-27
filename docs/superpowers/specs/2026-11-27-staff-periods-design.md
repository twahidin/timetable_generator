# Teacher-only periods: a period for named teachers with no students

Date: 2026-11-27. Asked for by the committee lead. Mockup: `2026-11-27-staff-periods-mockup.html` and `.png` beside this
file (made-up names). One stage.

Approved by the lead on 2026-11-27 ("Approved"). No plan and no code yet: those wait for the lead's word.

## Why

Some teachers are busy at fixed times every week with no class of the school in front of them: a zone computing class
after school, a staff meeting, a department meeting. Today the committee can only block such a time on step 6
("Teacher availability"). That keeps lessons away, but the time shows on no timetable, each row is one teacher on one
day, and the part after the last period is dropped.

The lead's words:

- "I want to be able to add on after school lessons too, ie beyond the school structure, example I have a west zone
  computing class from 3 pm to 5:30pm every Thursday and Tuesday for some teachers"
- It is for teachers only (if the school's own students took part, it would be in the generated timetable), and "there
  are times where we need to allocate such periods for [teachers] without students (example school meetings etc)".
- Asked whether a meeting is weekly or on dates: "Same slot each week".
- Asked about a new one in the middle of a term: "Publish again is fine".
- Asked whether it counts against the allowance: "No, show it only".
- Asked about a period that ends after the last period (4.20 pm on the test setup): "Yes, edge is enough".
- Asked which way to build it: "A, its own list".
- Asked whether exam duties and events are refused during such a period: "for event and exams, those teachers with
  non-timetabled event can be called for invigilations and event duties , ie can be overide".

## Goals

1. On step 6 the committee enters a teacher-only period once: a name, who is in it, the week, the days, clock times
   and a place.
2. It shows on the timetable of every teacher in it: the published page, the teacher's printout, and step 8's board for
   that teacher.
3. The app treats those teachers as busy then for lessons and relief, wherever it already respects a teacher's
   block-out: the agent that makes the timetable, the checks on steps 7 and 8, relief; and also the published page's
   "Who's free".
4. For exam invigilation and events the teacher can still be called: the app prefers others and marks the name, and
   never refuses.
5. A lesson may still be put on top of it by hand. The app warns and never refuses.

## Not in this work

- Single dated events (a meeting on one date). Those stay in Exams and events.
- A change that shows on the published timetable without a publish. After a change on step 6 the lead publishes again
  on step 9 (the same draft, no new upload).
- Counting a teacher-only period in a teacher's periods, load or allowance. The lead raises "Other duties" on step 4 by
  hand if some of it should count.
- Booking a room. "Place" is words only. (A room can still be closed for lessons with a "Not available" rule for the
  room, as today.)
- Extra columns on the timetable for times after the last period, or before the first.
- Adding, moving or deleting a teacher-only period on step 8's board. It is entered on step 6 only.
- Any change to "Teacher availability": its rows stay as they are and still show on no timetable.
- Telegram messages (the morning message, relief messages) naming a teacher-only period.
- Putting a lesson after school on the board, and lifting a group out of a band: another design
  (`2026-11-27-band-one-group-and-after-school-design.md`, branch `band-one-group`).
- The published timetable's new look (hour lines, each lesson's own time): another design (branch `timetable-look`).
  See "The two sibling designs" below.

## What would make it a failure

- A teacher-only period, or the names of the teachers in it, reaching a class's page, a student's page, or the data
  sent to a student's browser.
- Relief asking anyone to cover a teacher-only period when a teacher in it is absent.
- A teacher-only period counted in "periods a cycle", the load bars, the allowance checks or relief's period counts.
- A publish refused because a lesson stands on a teacher-only period.
- An event that cannot be sent, or an invigilator or a replacement that cannot be chosen, because of a teacher-only
  period.
- A teacher-only period lost or changed when a new timetable is uploaded on step 8.
- A row of "Teacher availability" that behaves differently than before, or starts to show on a timetable.
- A lesson hidden on a timetable or a printout because a teacher-only period is drawn over it.
- The agent making a timetable from a workbook that holds teacher-only periods without keeping lessons away from them
  and without anyone being told (see "The hand-over to the agent").

## Approaches

**A. A list of its own on step 6 (chosen by the lead).** One row holds a name, many teachers, more than one day, clock
times and a place. The app reads each row as a block-out for every teacher in it, so everything that already respects a
teacher's block-out keeps working. New: the list, the box on the timetables, and keeping the real clock times.

**B. A tick on each "Teacher availability" row** ("Show on the timetable", with a name). Least to build. But a row is
one teacher on one day: the zone class for three teachers is six rows, a staff meeting is a row for every teacher, and
a new teacher is left out until someone adds a row.

**C. A lesson with no class on step 8's board.** Dropped: the agent would not hear of it, it would be lost at every new
upload, relief would ask for cover (`relief/lessons.py` `on_date` takes every lesson row that names the teacher), and
step 5's comparison would report it as a lesson nobody planned.

## How it works today (checked on main ea073c8)

- A row of step 6's "Teacher availability" is a rule in `spec["rules"]`:
  `dict(scope="Teacher", target=<one name>, rule="Not available", week="Odd"|"Even"|"Both", day="All"|"Mon".., from, to, strength="Must", note=<Reason>, times=["15:00","17:30"])`.
  `from` and `to` are the first and last period the clock times overlap (`ttgen/reader.py` `periods_between`), cut to
  the day's periods: 3 pm to 5.30 pm on a day of 26 periods of 20 minutes from 7.40 gives periods 22 to 25, and the time
  after 4.20 pm is not used for anything. The typed times are kept in `times`.
- Who reads a teacher's Must "Not available": the solver (`ttgen/solver.py`, about line 538), the rule check
  (`ttgen/verify.py` `_not_available`, a warning on step 8's list; through it the board's judge in `fixes.py`, which
  answers "no" with a sentence the board can force with "Put it here anyway"), relief's list of free teachers
  (`relief/free.py` `free_then`: the teacher is left out), exams and events (`exams/days.py` `day_view` puts the
  periods' clock spans in `blocked`; `exams/invigilate.py` `_free` answers "is not available then (a Must rule)"), step
  7's "Will it fit?" (`ttgen/checks.py`, about line 197), the report (`ttgen/report.py`, about line 171), the helper
  (`helper.py`, about line 169, which finds the rule's row from the warning's key), and the page's own checks in
  `static/app.js`.
- What `_free`'s answer does differs by place. Making invigilation duties and the list of candidates leave the person
  out. A name chosen by hand is kept and flagged "Not free". A replacement on an approved exam or event is refused
  (`app.py`, about lines 3556 and 3757). An event with a person going who is "not free" has a clash, and a clash stops
  the event from being sent ("Fix the clashes first", `exams/events.py` `send_errors`), with no way to force it.
- "Keep free together" for a department already keeps the solver away from a time for that department's teachers.
  Relief only marks such a teacher "department meeting time" and still offers them; exams do not read it.
- Saving the setup writes the workbook and reads it back before the checks (`normalise` in `app.py`, about line 701),
  so whatever the workbook holds must read back to exactly the same setup.
- The published model's teacher rows hold only the first department (`ttgen/export.py`, about line 84); the copy of the
  setup in the model holds both.
- Only a teacher with at least one lesson has a timetable: a page, a printout, a place in "Who's free"
  (`all_views` in `ttgen/export.py`; the page's teacher list).
- The `staff` view's page is made once and kept for all staff; only the viewer's name is put in when it is served
  (`app.py`, about lines 1553 to 1588). A teacher's own exam duties reach that page by a request of their own
  (`/api/me/exams`).
- A rule warning on step 8 is not critical. It does not stop publishing.
- The setup workbook has a sheet "Teacher availability" (Teacher, Week, Day, From, To, Reason), written by
  `ttgen/template.py` from `spec.split_rules(...)["availability"]` and read back by `ttgen/reader.py`. The agent's skill
  (`skill/school-timetable-generator/`, version 2026-11.11) reads the same workbook; `scripts/ttgen/` there is a copy of
  `ttgen/` and the two are kept the same.
- The published timetable keeps a copy of the setup made at publishing (`pub["model"]["setup"]`). Relief and exams read
  the rules from that copy, so a change on step 6 acts on them only after the next publish. The draft stays on step 8
  after a publish, and `draft.publish` checks it against the setup as it is at that moment, so "change step 6, then
  Publish again" works today for a rule.
- A teacher's timetable: `ttgen/export.py` `teacher_view` (cells, legend, the figures "periods a cycle", "allowance",
  "most in a day", "days teaching"), drawn on paper by `draw_page` and in the Excel file by `write_excel`; the published
  page (`ttgen/timetable_page.html`) builds the same view in the browser from `html_data`, which is cut down on the
  server for the `student`, `staff` (a teacher's own timetable and the classes) and `personal` views.
- The published page's "Who's free" (`renderFree`) reads lessons, and on a chosen date also exam and event items. It
  reads no rule, so a teacher with a block-out shows as free there today.
- Step 8's board gets a teacher's week from `draft._payload(m, "teacher", name)`: lessons only.
- A teacher renamed on step 4 is followed in every rule whose `scope` is "Teacher"
  (`2026-11-24-teacher-rename-design.md`), with a toast that counts what followed.
- A teacher has a department and may have a second one (`dept`, `dept2`).

## What a teacher-only period is

A row of a new list in the setup (suggested `spec["staff_periods"]`), each with:

| Field | What it holds |
|---|---|
| Name on the timetable | Words, needed. "Zone computing class", "Staff meeting". Up to 60 characters. |
| Who | "All teachers", or any mix of departments and named teachers. |
| Week | Odd, Even or Both (only Both when the setup has one week). |
| Days | One or more of the setup's weekdays. |
| From, To | Clock times, as on "Teacher availability". |
| Place | Words, optional, up to 60 characters. Books nothing. |

"All teachers" and a department are read anew each time: a teacher added on step 4 later, or moved into the department
(first or second), is in the period with no further step. A teacher is in a period once, however many ways the row
names them. On the published side "Who" is worked out from the copy of the setup in the model, never from the model's
teacher rows (they hold one department only).

A teacher with no lessons can be in a period ("All teachers" takes in everyone on step 4). Such a teacher is busy then
for relief and exams like anyone else, but gets no timetable page or printout because of it: only teachers with a
lesson have one, as today. The count under "Who" counts everyone it means.

It repeats every week (or every Odd or Even week) on its days. It has no dates.

## Step 6: where it is entered

On the Teachers tab of step 6, a new part "Teacher-only periods" above "Teacher availability", as in part 1 of the
mockup:

- Under the heading: "A period for teachers with no students, the same every week: a meeting, a zone class. It shows on
  their timetables. Lessons are kept away from it; a lesson you put there by hand gets a warning. A change here shows
  on the published timetable after you publish again on step 9."
- One row a period: the name, "Who" as chips (a teacher, a department, or "All teachers") with "+ Add teachers", the
  week, a button for each weekday, From and To as time boxes, the place, and ✕ to delete the row.
- Under "Who" for a department or "All teachers", a small line with the number of teachers it means now
  ("58 teachers now. A new teacher is included.").
- Under the times, a small line saying which periods the row blocks, as "Teacher availability" does in its "Blocks"
  column. When the times reach past the last period, or start before the first, the line says so in plain words
  ("after the last period (4.20 pm)").
- "+ Add a teacher-only period" adds an empty row.
- The tab's counter on "Teachers" counts these rows with the others.

Who may enter it: whoever may change step 6 today. No new right.

"Things to fix" lists a row with no name, nobody in "Who", no day, a "To" that is not after its "From", a teacher who
is no longer on step 4, or a department with no teacher. A row with such a fault blocks nothing and shows nowhere
until it is put right, except that a row with some teachers still on step 4 goes on working for those.

Two rows may overlap for the same teacher, and a row may run across a recess, a lunch or an assembly. Neither is a
fault.

History and "Put back" treat a change to this list as they treat any other change to the setup.

A teacher renamed on step 4: the name in "Who" follows, and the toast counts it with the rest. A typed department is
not involved: "Who" holds the department's name as step 4 has it.

## What it does: the teacher is busy

One function in `ttgen/spec.py` (suggested `staff_blocks(spec)`) turns the list into block-outs: for each row without
a fault, each teacher in it, and each of its days, one item shaped like a teacher's Must "Not available" rule (same
`scope`, `target`, `rule`, `week`, `day`, `from`, `to`, `strength`, `times`), plus the row's name and place and a mark
that it comes from a teacher-only period. `from` and `to` are the periods the clock times overlap, as today. A row
whose times lie wholly after the last period or wholly before the first gives no periods: it blocks no lesson, and is
still kept for the clock-time readers and for the timetables.

Every reader of a teacher's Must "Not available" also takes these items, except the exams and events check, which
treats them more softly (below). The builder finds each reader (the list under
"How it works today" is the start, not the whole) and a test names each one:

- **The agent and the solver.** Lessons of a teacher in the period are kept out of its periods, exactly as for a Must
  block-out. See "The hand-over to the agent".
- **Step 8's list.** A lesson of a teacher that overlaps is one warning: "{teacher} has {lesson} on {day} period {p}
  during {name} ({from} to {to})." A warning of the same kind and weight as a Must rule's today: it can be answered, it
  has "Show me", and it does not stop publishing. An answer the lead gave stays with its warning when another row of
  the list is added, removed or moved. The helper (`helper.py`) finds a rule's row from a warning's key today: for
  these warnings it must find the teacher-only period instead, or leave the warning alone, and never a wrong rule row.
- **Step 7's "Will it fit?" and the report** count the periods as they count a teacher's Must block-out.
- **Step 8's board.** Putting a lesson there, or giving the lesson to a teacher in the period, is judged "no" with the
  sentence "{teacher} has {name} then ({day} {from} to {to})." and can be forced with "Put it here anyway" (or "Give it
  anyway?" for a teacher change), as a Must rule can today. Part 3 of the mockup. Re-fit, the helper and "Ask about
  this" never choose such a place on their own, as for a Must rule today.
- **Relief.** A teacher in the period is not offered as free for a lesson that overlaps it. They appear in the list of
  busy people with the period's name as the reason (today a Must block-out drops the teacher silently; the busy list
  exists for exam duties). Nothing asks for cover of the period itself: it is not a lesson, and must never become one
  in `relief/lessons.py`.
- **Exams and events: a mark, never a refusal** (the lead's answer). A teacher-only period is **not** put in
  `day_view`'s `blocked` and never makes `_free` answer "not free". It is carried beside it (suggested: a second set of
  clock spans with the period's name), for the period's own clock times, including the part after the last period and
  before the first. Then:
  - Making invigilation duties, and the list of candidates: a teacher in a period then is a candidate in a group of
    their own with the reason "has {name} then", taken after the teachers who are free and before a teacher whose
    lesson still runs. So the app calls them only when the free teachers run out.
  - A name chosen by hand, a person going on an event, a duty of an event, and a replacement on an approved exam or
    event: all allowed. The name carries the mark "has {name} then" wherever "Not free" is shown today, in its own
    softer style, and the mark is never counted as a clash. An event with such a person can be sent.
  - A teacher's own Must block-out on "Teacher availability" still refuses, as today.
- **"Who's free" on the published page.** A teacher in the period is not listed as free for a range of periods that
  overlaps it, and where the view names why someone is busy it gives the period's name. (Rows of "Teacher
  availability" stay outside "Who's free", as today.)

Nothing here counts periods. The figures on a teacher's page, the load bars on steps 4 and 5, the allowance checks and
relief's counts are unchanged.

## Where it shows

Part 2 of the mockup.

- **The teacher's published timetable** (the full page, and a teacher's own page in the `staff` view): on each of its
  days a box over the periods it overlaps, white with a dark outline, unlike any subject's colour. In the box: the real
  times as typed ("3.00–5.30"), the name, the place. Clicking it opens nothing, or the small details box with the same
  three things.
- **Past the edge.** The timetable is not made wider. A period that ends after the last period stops at the right
  edge, with a broken edge there and its real end time marked ("to 5.30"). The same on the left for one that starts
  before the first period.
- **A line under the timetable.** In the teacher's legend, after the teaching entries, one entry for each teacher-only
  period: "{name} · {week and days} · {from} to {to} · {place}". A period that lies wholly outside the day's periods
  has no box and shows here only.
- **The teacher's printout** (PDF) and the teachers' sheets of the Excel file: the same box and the same legend line.
- **A lesson in the same periods** (one forced there by hand): both show. The lesson is never hidden; the builder
  shares the space as two lessons at one time are shared today (`_lanes`), or writes the period's name into the
  lesson's cell where a cell holds one thing (Excel).
- **Step 8's board**, a teacher's grid: the same box, fixed. It cannot be dragged, lifted or deleted, and it has no
  Lesson page. Class panels show nothing.
- **"Preview as it will be published"** on steps 8 and 9 shows what a publish would show, from the setup as it is now.
- **"Their timetable ↗"** on Plan relief opens the teacher's published page and so shows it.

Never: a class's timetable, a student's timetable, the Lessons tab, the rooms' and venues' pages, the student lists.
In the `student` and `personal` views the data sent to the browser holds no teacher-only period at all. In the `staff`
view a signed-in teacher's browser receives only that teacher's own periods. The `staff` page is one page kept for all
staff, so they cannot be inside it: they come by a request of the teacher's own, as the exam duties do
(`/api/me/exams`), or by another way the builder chooses that keeps the rule.

## The hand-over to the agent

- The setup workbook gets a sheet "Teacher-only periods", one row a period. Suggested columns: Name, All teachers
  (Yes or empty), Departments (a list), Teachers (a list), Week, Days (a list), From, To, Place. `ttgen/reader.py` reads
  it back into the list. A workbook without the sheet reads as an empty list.
- The sheet must read back to exactly the list it was written from, because saving the setup goes through the workbook
  and back. A test writes and reads every shape of row, a row with a fault included (an empty name, nobody in "Who", no
  day): a half-filled row on step 6 must not vanish or change when the page saves.
- The periods are **not** also written as rows of "Teacher availability": one place holds them, so nothing is read
  twice.
- `SKILL.md` gets the sheet in its table of sheets and one sentence in the teachers' part of the model: each teacher in
  a teacher-only period is not available in the periods it overlaps, as a Must "Not available". The skill's version
  goes up by one (2026-11.12), and the workbook's README names it, so an agent with an older skill is told to ask for
  the newer one (the guard that exists).
- `skill/school-timetable-generator/scripts/ttgen/` stays a copy of `ttgen/`. The skill's own check then reports a
  lesson on a teacher-only period with the sentence of step 8's list.

## Changing one after publishing

The lead changes the list on step 6, looks at step 8 (its usual line says the setup has changed since the timetable was
made; any lesson now standing on a period is a warning), and presses Publish on step 9. The published timetable, relief,
exams and "Who's free" follow from that moment, because they read the copy of the setup made at publishing.

Until then the published timetable shows the list as it was at the last publish.

## The two sibling designs

- **After school on the board** (`band-one-group`): a lesson the lead puts after school at a time when its teacher has
  a teacher-only period gets both sentences in the drop box, each from its own check. If the lead raises "Periods in a
  day" on step 2 to reach later times (that design's answer for times past the day), a teacher-only period then blocks
  and is drawn in the new periods with no further work, because it is kept in clock times.
- **The timetable's look** (`timetable-look`): whichever look is live when this is built, the box follows it. On
  today's grid it covers whole period cells and writes its real times. On a look that places lessons by the clock, it
  is placed by its own clock times. If that design is built after this one, its builder carries the box, the
  past-the-edge mark and the legend line over.

## Tests

- `ttgen`: the function that turns the list into block-outs: names, a department by first and by second department,
  all teachers, a teacher named twice, a teacher gone from step 4, Odd and Even weeks, several days, times that end
  after the last period, start before the first, lie wholly outside, or cover half a period.
- `tests/test_verify.py`, `tests/test_rules.py`: the warning and its sentence; it is not critical; an answer to it stays
  when another row is added, removed or moved.
- `tests/test_fixes.py`, `tests/test_board.py`: the judge's "no" and its sentence for a move, a place, an add and a
  teacher change; forcing it; Re-fit and the helper never offering it; the teacher grid's fixed boxes; publishing with
  such a warning open.
- `tests/test_relief*.py`: a teacher in a period is not free and is listed busy with its name; an absent teacher's
  day has no entry for the period; relief's period counts are unchanged.
- `tests/test_exams.py`, `tests/test_exams_relief.py`: during a period (an exam that runs after the last period
  included) the teacher is a candidate after the free ones with the reason "has {name} then"; Make takes them only when
  the free ones run out; a name chosen by hand and a replacement on an approved exam are accepted with the mark; an
  event with such a person going has no clash and can be sent; a "Teacher availability" block-out still refuses.
- The workbook: written and read back unchanged; a workbook without the sheet; the skill's copy of `ttgen` equal to
  `ttgen`; the solver keeping a lesson out of a period.
- The published page (`tests/timetable_page.test.js` and the export tests): the box and the legend line on the
  teacher's view; nothing on a class's or student's view; `html_data` for `student`, `personal` and `staff` holds no
  teacher-only period; the request that gives a signed-in teacher their own periods gives nobody else's and refuses a
  student; "Who's free"; the figures unchanged; a teacher with no lessons still has no page.
- Step 6 (`tests/*.test.js` for the page's plain functions): the row's faults in "Things to fix", the count line, the
  "after the last period" line; a rename on step 4 followed.
- Every suite that exists, quick and `--full`, on the final code.
- In a browser with a real mouse, on the sample school: add the three rows of the mockup, see step 8's teacher grid and
  the warning, force a lesson onto one, publish, open the teacher's page, a class's page and "Who's free"; print one
  teacher's PDF to a picture; and every older control of step 6's Teachers tab once.
- On a scratch copy of the school's real setup and timetable, counts only: one row for all teachers at a time when
  lessons run gives as many warnings as lessons then; taking the row out gives none; the copy is deleted afterwards.

## Known limits

- A change on step 6 does not act on the published timetable, relief or exams until the lead publishes again.
- The published timetable does not grow: the part of a period after the last period is words in the box, not a
  length.
- The place is words. Two periods can name the same hall at once and nothing says so.
- The app does not check that a teacher in "All teachers" is in school on that day; a part-time teacher's own block-out
  and the meeting simply both apply.
- A single dated meeting is not covered here.
- A teacher with no lessons has no timetable page, so a period shows nowhere for them. They are still busy then.
- A department that has both a "Keep free together" rule and a teacher-only period at the same time gets two warnings
  for one lesson there. The committee keeps one of the two. (The teacher-only period is the stricter: relief does not
  offer its teachers at all.)

## Left to the builder

- The names of the list, its fields and the function, and how the block-outs are passed to each reader, within the
  rules above.
- How an answer to a warning is keyed so that it stays with its warning.
- The exact look of the box, the broken edge and the "to 5.30" mark on each surface (page, PDF, Excel, board), kept
  near the mockup and unlike a lesson.
- How "+ Add teachers" picks (the picker step 6 or step 5 already uses for teachers, with the departments and "All
  teachers" on top).
- Whether a click on the box opens the details box.
- How the Excel teacher sheet shares a cell between a lesson and a period.

## Decided by the writer (for the lead to check)

1. The words on the page: "Teacher-only periods".
2. "Who" can be names, departments, or all teachers; a department and "All teachers" take in a teacher who joins later.
3. "Place" is words and books no room.
4. Relief lists a teacher in such a period as busy, with the period's name, and never asks for cover of the period.
5. For exams and events the app calls a teacher in such a period only when the free teachers run out, and marks the
   name "has {name} then". (That they can be called at all is the lead's answer; the order is the writer's.)
6. "Who's free" on the published page treats the teacher as busy then.
7. Besides the box, each period is one line under the teacher's timetable; a period wholly outside the day's periods
   shows there only.
8. On step 8's board the box is fixed: it is changed on step 6 only.
9. Rows of "Teacher availability" are untouched and stay hidden.
10. The agent learns of the list through a new sheet and a new skill version (2026-11.12).
11. Telegram messages do not name these periods.
12. A period that starts before the first period (a morning briefing) is treated like one that ends after the last.
13. A teacher with no lessons gets no timetable page because of a teacher-only period.

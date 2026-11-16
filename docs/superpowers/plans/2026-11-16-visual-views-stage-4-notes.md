# Visual views, stage 4: decisions made while building, and what was left

From the build ledger of `2026-11-16-visual-views-stage-4-teachers.md`. Built subagent-driven on 2026-11-16 (a fresh implementer per task, a reviewer per task, one whole-branch review, one fix wave and its re-review) on branch `visual-views-stage-4` from `main` at de3714f. Fifteen commits with this file; head of the code 8fa6ea8.

## What was built

"Can teach" is gone. The app no longer asks what each teacher may teach: not on step 4, not on step 5, not under Things to fix, not in the workbook, not in the outside agent's skill, and a department head no longer has a permission for it. A list already stored on a teacher is left where it is and never read, shown or written to a workbook.

A teacher can have a second department. The first is the home department (`dept`), the second is `dept2`. The workbook's Teachers sheet has a "Department 2" column after Department and has lost its sixteen Can teach columns and its hidden key column; the Lessons sheet's Check no longer tests Can teach. The skill's version is 2026-11.5. Only the committee gives a second department.

Step 4 (Teachers) has two views, Cards and Table, and the Roles card is below the teachers in both. On Cards there is a column per department; a teacher with two departments has a card in both. A department chip dragged onto a card, a "Second department" box in the open card and in the Table, and a ✕ on the chip give, change and take off the second department.

Step 5's Map view is one page: the department's teachers (home or second) as a strip with their loads, then the classes and teaching groups by level, then by subject in step 3's order, with each band's groups together under the band's name. Placing a teacher is tick and click, or drag, as before, and no longer asks about anything.

Step 8's Fix card offers, to take over a lesson: step 5's teachers of it, then every teacher already on a lesson of a subject of the same step 3 card, then the other teachers of the subject's department (home or second).

New modules: `static/teacherview.js` (step 4's cards) with `tests/teacherview.test.js`; `tests/test_teachers.py` for the workbook, the samples and the two-department rule. `DeptMap.page` in `static/map.js` is step 5's layout. `ttgen/allocate.py` is removed.

## Rulings (decisions made where the plan was silent or wrong)

The plan's own faults

- The samples' change (teacher rows without `can_teach`) was moved from Task 1 to Task 3, so that the samples stop carrying the list in the same commit in which the Fix card stops reading it. With the plan's order every suite that uses the Fix card would have been red for two tasks.
- The workbook's README-sheet line for step 4 begins "List the teachers with their department." The plan's "and role" repeated the line's own next sentence.
- The plan's sentence for the row of department chips would have told a department head to drag one. For a head the row reads "Departments: only the committee gives a teacher a second department."
- The plan said the map tests' fixture "gains" rows. About twenty tests pin exact results on it, so the new tests have a second fixture of their own.
- The plan's card sentence gave "1 students" and "1 periods". A card says "1 student" and "1 period".
- The plan's end-of-branch search did not look for the Start step's own sentence. "How it works" still said Things to fix lists "a teacher not set up for a subject". It now gives three checks that exist.

The model

- A card's `home` flag is true in the column of the teacher's first department, and in the "No department yet" column for a teacher with none. So a teacher whose only department was typed as the second still has exactly one home card, which is the one a Things to fix click opens.
- Step 8's "same card" rule was first written loosely (the name ending with the tag, with no space). It now follows step 3's rule: the trimmed department, code and name less its own tag only when that tag is one of the school's and follows a space. A tags list or a row that is not what it should be is skipped and never raises.
- The departments of each teacher are worked out once per judging of a change on step 8, and a test pins it. The first version rebuilt them on every one of the thousands of judgings the helper makes.
- On step 5, a band's groups at two levels make one lane in each level, and the lane's "is on two groups of this band" line counts the band's groups at every level, as the old Bands tab did.

The page

- "+ Add teacher" on Cards opens the new teacher's card with the keyboard in its Name box, after clearing the Show bar's filter. It used to add a closed blank card at the foot of the first column, where a person would not see it.
- Opening or closing a two-department teacher's card in their second department's column keeps the scroll and the keyboard in that column. The first version jumped to the home column's card.
- When a department head makes a provisional teacher's department equal to the second department the committee gave, the page no longer sends the change that takes the second one off, which the server refuses in words the head would not understand. Every reader already treats a second department equal to the home as none.
- The upload card on step 4 is headed "Upload the teacher list": its "2 ·" counted nothing once Roles moved below.
- The strip's teacher chips show the name and the load, not the role. The role is on step 4 and in the profile, a click away.
- The table view's teacher box shows a teacher who is not on the teacher list as "Name (not on list)", as the card does. It used to show a blank.
- A students figure of 0 shows as "0 students"; no figure shows nothing.

Left as they are, on purpose

- A step 5 card cannot be reached with the keyboard alone; the Table view is the keyboard's way to place a teacher. The old card was the same.
- A workbook opened gives every teacher a `dept2` of nothing (null) where a teacher made on the page has no such field. Every reader treats the two alike.
- Step 4's Cards at the school's size is a long page: two columns side by side at a laptop's width, beside Things to fix. The Show bar narrows it to one department.
- The Table heads its column "Department 2", the workbook's own heading; the open card says "Second department".

## Checked at the whole-branch review

On the school's real setup (counts only; every derived file deleted afterwards):

- The workbook. The new reader gives 92 teachers, none with a second department and none with a Can teach list; every other sheet's rows equal what the reader on `main` gives. Written by the new writer and read back, the setup is the same but for one school setting (`choices_mode`) that differs in the same way on `main`. The Teachers sheet has 15 columns, none headed Can teach. The Lessons Check has no "not set to teach".
- Step 4. 92 cards for 92 teachers in 11 columns (2 empty); every teacher on exactly one card per department, with exactly one home card.
- Step 5. 460 class and group cards over 11 departments; the largest page has 69. No department's page differs from the old Classes and Teaching groups tabs, and no card is repeated. 82 lanes. 193 of the 246 group cards show no students figure, because those groups have no Students typed on step 5; all 214 class cards show their class's size.
- Step 8, on the outside agent's timetable of 10 November (1,948 lessons), for a sample of 92 of the 460 planned rows, `main` against this branch: no error on either; 3 rows had nobody to offer on `main` and none has on the branch; no row is offered fewer teachers; no teacher offered on `main` is lost. The middle row is offered 15 teachers where it was offered 5.
- Speed on that timetable. One row's offers: 30 ms in the middle where it was 26, the slowest 218 ms where it was 123, because more teachers are judged, each at the same cost. One whole Fix card: 80 ms where it was 66. The helper, on 12 of the 144 warnings: the same 7 suggestions for the same 5 warnings, in 2.5 seconds where it was 2.0.
- The real page, on a scratch server (no screenshot taken): step 4's Cards draw in 26 ms and the Table in 57; opening a card takes 28 ms; the largest department's page on step 5 draws in 16 ms; placing a teacher takes 32 ms. Things to fix has no "not set to teach" line. No script error.

The suites, at 8fa6ea8: every `tests/*.test.js` (13 files, among them map 25, people 31, teacherview 8), `test_teachers` 9, `test_venues` 4, `test_typed` 33, `test_helper` 17, `test_fixes` 26, `test_verify` 47, `test_rules` 11, `test_choices` 16, `test_parents` 35, `test_sync` 18, `smoke` 92. `ttgen` equals the skill's copy. The words "Can teach", "who can teach", "basket", "Staff room", "not set to teach" and "not set up for a subject" appear nowhere in `static/`, `ttgen/`, `README.md` or `docs/DEPLOY.md`; "Can teach" appears once in `skill/` (the sentence that tells the agent to ignore those columns in an older workbook); `can_teach` is named only by `sync.py`, `static/sync.js` and tests.

In a browser, on made-up data, by the reviewer, all seen and right: step 4 in both views with the view remembered; a real drag of a department chip onto a card, the box in the open card and in the Table, the ✕; a home department set to the second one; a card's fields against the Table; the tick bar; a stored Can teach list that shows nowhere and survives a change; a real department-head sign-in (reads everything, edits only a provisional teacher, cannot give a second department, and the server refuses a forced one while keeping the rest of the batch); two committee tabs giving one teacher two different second departments (the later stands, no error); step 5's strip and page for all 11 departments, a real drag of a teacher onto a card, tick and click, a fourth teacher refused, "Others", a class split off a shared row, the profile, the table view's boxes and tick bar; the workbook built and opened again through the server's own routes with second departments kept; a Things to fix click that opens a teacher's card; steps 1, 2, 3 and 6; the page at 1280 and at 1000 pixels wide.

No real name and no full school name is in the diff or the commit messages.

## Known limits, ruled to stand

- **Step 5's Table view is slow on the school's real setup, and was before this branch.** With all 460 rows shown it takes about 1.6 seconds to draw, and about 0.6 with one level picked. Building the page's text takes 80 ms (the teacher boxes 41 of them); the rest is the browser making 159,000 choices in 3,300 boxes, because every teacher box lists every teacher. The Map view is not affected. Worth a task of its own.
- A department's "Keep free together" rule now keeps a second-department teacher free too. The school's real setup has no such rule today, so this was tried on made-up data only.
- The Fix card was not opened in a browser on a returned timetable (the browser tool cannot upload the file). Its teacher list was run through the server's own functions on the real timetable and on both samples.
- On a head's page a Class Parents lesson's lock on step 5 was checked by a builder with the rule switched on from the console, and by reading at the review; the sample has no Class Parents.
- The uploaded teacher list's tidy of a second department equal to the new home was checked by reading only: the browser tool cannot upload a file.
- A page left open across the change: a head's old page that still sends a Can teach change has that one change refused in words and the rest kept (a server test pins it). A committee's old page can still save one, and nothing reads it.
- The page's drawing code has no automated test, as before: the repository tests page code in a browser.
- The look of the two new pages on the school's real data was not looked at by eye: no screenshot of real data was taken.

## Deferred minor points

The workbook and the server

- The workbook's Lists sheet still carries the two columns of level bands that only the Can teach pick list used.
- The test of an older workbook does not include the old hidden key column (the reader ignores headings it does not know).
- The solver's and the report's own lines for a second-department teacher have no end-to-end test; the checks' line, the same expression, has.
- A department head can still set the unused `can_teach` field on a provisional teacher through the general "edit a provisional teacher" rule.
- The second department is taken off a head's new teacher in `app.py` only; `sync.head_may` alone would allow it (one caller today).
- Step 8's card rule keeps a subject whose name is its tag alone under that name, where step 3 makes it a card of its own; they differ only if another subject's name less its tag is that same word.
- The older "wide" memo in `fixes.py` builds its value on every call (older than this branch).

The page

- `static/teacherview.js` states the "no department" rule twice, in two passes; a second department stored with spaces round it is left untrimmed when it is given again (every reader trims); a department stored as something other than text shows as that thing's text.
- `dplane`, `dpstrip` and `dpcards` are class names with no style rule.
- `DeptMap.cards(…, "bands")` is now reached only from tests; `DeptMap.roster` runs three times per draw of the Map (92 rows each).
- The model's tests for odd input cover two cases; the filter test has no case for a department with no column or a search that finds nobody.

## Not exercised in a real browser

Saving the downloaded workbook to disk and opening it again by hand (the round trip was done through the server's own routes, and on real data through the reader and writer); the Fix card and the helper on a returned timetable; the typed request box (no test may call a model); an uploaded teacher list; a department head adding a teacher from step 4's Cards (the same code as the committee's); the committee's own site (it has this only after a merge and "Deploy Latest Commit").

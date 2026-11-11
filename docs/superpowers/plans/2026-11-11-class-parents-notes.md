# Class Parents: decisions made while building, and what was left

From the build ledger of `2026-11-11-class-parents.md`. Built subagent-driven on 2026-11-11 (a fresh implementer per task, a reviewer per task, one whole-branch review, one fix wave, one re-review) on branch `class-parents` from `main` at a3311fa (stage 3 of the return trip merged and live).

## Where the plan's wording differs from the design's

- Workbook headings on the Classes sheet are the school's word as typed plus a number ("Class Parents 1" to "Class Parents 4"), not a singular.
- A class with none shows "{class} has no {name} yet." under Things to fix. Its lessons of the named subjects keep whatever teachers they have until the class gets its first form teachers.
- The workbook's own Check column does not test Can teach on lessons of the named subjects at all (whole-class or in groups).
- The step 4 paste-list "Remove" already strips a removed teacher from lessons, so it strips them from the form teachers too, and its question says how many classes lose one.
- The badge with the school's word is on the map's class cards. A row of the lessons table shows "Changed by hand" and its Back button, no badge.

## Rulings (decisions made where the plan was silent or wrong)

The rule

- The maximum counts only as a whole number from 1 to 6 (a number or a string of digits, spaces around it allowed); anything else is 2. One reading for the page, the server and the workbook reader.
- "Changed by hand" is true or absent; any other value is removed.
- A lesson the rule makes takes the id `cp-<class id>-<subject id>`, or the first free of `-2`, `-3` and so on when a row already has that id. Two browsers making the same lesson make it once.
- "In a block" (and "has a kept code") means a non-empty text or a number other than 0, the same on the page and in Python. The fix wave first narrowed it to text only, to make odd values such as an empty list read the same in both; the re-review caught that a code typed as 12 in a workbook arrives as a number and such a row would have become a staffed lesson. Put right by the controller, test first, after the re-review: that last commit was not seen by a reviewer.

What an edit does (the page)

- In `save()` the ids are given first and the rule runs second, before the Undo step is recorded. So a change of a class's box and the lessons it moves are one save, one Undo step and one batch of changes.
- A person's own save can mark a lesson by hand; an undo, a redo, a copy opened from the server and other people's changes cannot. The five quiet or remote saves were listed and none can follow a fresh edit.
- A hand change is marked only when the lesson's class has form teachers. On a class with none, what is typed is kept and is judged when the class gets its first form teachers.
- A row that becomes staffed by a person's edit (its band cleared, its subject changed to a named one) is treated like a new row: other people on it means it is marked by hand, never replaced.
- A class's first form teachers do not mark a shared lesson whose teachers came from another class's box.
- The first fill leaves out a name that is already a form teacher of another class on the same shared lesson.
- On a department head's page outside a practice copy `save()` does not run the rule at all. The server's result reaches the head as other people's changes. (Before this, the rule making a missing lesson on a head's page was sent, refused, and reported to the head as a failed change.)

The server

- After every change it stores, the server runs the rule and logs what it had to put right as a further version under its own client id, `parents`. A school that does not use the feature pays nothing: no copy, no extra version.
- The reply to a sender carries `mine`, the version at which its own changes were applied. The page applies other people's changes below it, then its own, then those above it (`Sync.rebase` gained an optional `after`). Without this a browser whose change the server corrected kept showing its own version.
- The server only derives; it never decides that a lesson was changed by hand. It cannot tell a typed teacher sent without its mark from a page's own derived list that is one box change behind.
- A department head may not, on a staffed lesson, change its teachers, mark, subject, band, code, classes or level, nor delete it, nor make a lesson staffed that was not, nor merge into a lesson's fields. A head's changes are judged in order against the setup as the earlier ones of the same batch leave it. A malformed change is refused, not an error.

The workbook

- Up to six Teacher columns the Check formula's text is exactly as before, so every existing workbook is written cell for cell as before (apart from the version text and the one new last column). Above six, the "twice in this block" test is one term per teacher over the whole Teacher block, the named-subject test is written once, and Teacher columns seven and beyond get no Can-teach test (a lesson passes six teachers only by following several classes' form teachers). Longest formula measured: 6,967 characters at 24 Teacher columns with 30 named subjects; Excel's limit is 8,192.
- The Settings sheet is read as before to row 59, and beyond only while the labels carry on without a gap.
- The three Settings rows and the Classes columns are written only when the feature is used; the "Changed by hand" column is always there.

The published pages

- On the PDF the form teachers are a line of their own under the subtitle, wrapped between names and never cut; the grid moves down only on pages that have the line. On the web page and in the Excel export they are part of the subtitle.
- A student's timetable carries the line for the student's own class.

Process

- Task 6 was done in two dispatches with a review each (the Python side, then the page).
- One test first written against the git history (`git archive` of an earlier commit) was replaced by a pinned formula text; a test must not need the history.

## Fixed at the whole-branch review

- The design's line on a teacher's step 5 profile ("{name} of 3I4") had never been built: the plan's Task 6 left it out.
- The lessons table drew three Teacher columns once the rule was switched off, hiding a fourth teacher a lesson still held. It now shows every teacher a row holds, and still gives an ordinary row no fourth box.
- A department head's malformed change to a lesson gave a server error; a head's merge into a lesson's band could make a group row count as a whole-class one. Both are refused.
- The README said three Things to fix lines (there are five) and overstated when typed teachers are kept. The workbook note now says "on the Lessons sheet (Step 6 · Lessons)".

## Checked at the whole-branch review

On the school's real workbook (counts only): naming CP Time and the two Character Education subjects made 32 CP Time lessons and 96 following lessons; the first fill gave all 32 classes their form teachers with nothing marked by hand; a fourth form teacher reached that class's three lessons; a hand change was marked and its Undo unmarked it. The page's copy equalled the server's after every step, the server never had to correct the page (11 versions for 11 edits, 20 to 45 ms a change), and the workbook round trip returned the same setup (4 Teacher columns, longest formula 3,395 characters). On 4,000 random small setups the page's version of the rule and the server's agree. Nothing in the repository still assumes three teachers. Every route a department head has to these lessons is closed. The school's word and names are escaped everywhere they are shown.

## Known limits, ruled to stand

- Two committee members on the same class within one sync (about four seconds): a tab that is behind and changes the class's box can put back a lesson the other member changed by hand in those seconds. The row still shows "Changed by hand"; the hand change has to be made again.
- One committee member typing a teacher on a lesson at the moment another names its subject, or gives the class its first form teachers: the typed teacher is replaced.
- A browser tab left open across the deploy runs the old page: a teacher it types on a following lesson is put back on the server but stays on that tab's screen until a reload.
- A workbook edited in Excel: a teacher typed on a following lesson without Yes under "Changed by hand" is put back on import, as the note in the workbook says; nothing on the page says so.
- Renaming a class or a teacher does not follow through, as for every lesson today.
- If the branch were rolled back after setups were saved with the new data, the old code would drop a fourth teacher when writing a workbook and read the three Settings rows as extra settings.

## Deferred minor points

The rule

- The named subjects are worked out for every row, and all classes searched per class (fine at school size).
- A subject or level given as a number, a period value that is a one-item list or text such as "0x2", and an id that is a float are read differently by the page and by Python. The page writes none of these.
- With the rule off, a stray `by_hand: false` on a row is no longer stripped by the server.
- `pmax` repeats the body of `cap`, `classOf` the lookup in `want`.

The workbook

- A first round trip of the school's real workbooks adds one recess-window row to the extra settings and `choices_mode`, as the old writer does too.
- The Classes columns are found by the name on Settings: a name changed on Settings but not in the headings drops the form teachers silently.
- A subject name holding a comma cannot be named in the Settings cell.
- In the wider Check form a name is compared literally (COUNTIFS reads `*`, `?` and a leading `<` or `=` as patterns), and one error cell in the Teacher block makes that Check an error. With subjects named, an ordinary row lists all Can-teach messages before the "twice" ones.
- A name beginning with "=" becomes a formula, as for every text cell before.

The server and heads

- A head who deletes the only group row of a named subject for a class makes the server add that class's lesson.
- A committee tab can send very long lists of form teachers, which the rule copies onto every staffed lesson.
- If the status call fails on load the role is unknown and the rule runs once on a head's page (the server refuses the result).
- The head's checks assume every lesson row in the setup is an object.

The page

- The Things to fix line for a named subject that is not on step 3 opens step 6 at the first extra setting, not at the form teachers row. The named subjects are kept in the pop-up's order.
- Picking a name already on the row in another box leaves it twice, and on a staffed row also marks it by hand.
- Dropping a teacher on one class's card of a shared staffed lesson that is already full is refused with a count the card does not show.

The published pages

- A student's general code receives every class's form teachers in the page's data (each class's page is already open to that code).
- "Update step 5" marks a staffed lesson by hand even when its class has no form teachers.
- One name wider than the PDF line on its own overruns the line. The Excel export can drop a stat whose text is part of the longer subtitle.
- The fit of the tallest solved timetable with a two-line block of form teachers was reasoned from the layout code and from built legends (row height 62 against 66, minimum 40), not rendered from a solved timetable.

## Not exercised in a real browser

The browser checks (a scratch server, the secondary sample, most clicks driven through the page's own handlers) covered: the name and the maximum with a refused value; naming subjects on step 6 and the lessons made; the boxes on step 2; Undo putting a box and its lessons back together; the count of hand-changed lessons and its button; the first fill; Things to fix; two committee tabs picking up each other's changes; a reload keeping everything; every writer of a staffed lesson's teachers ending marked by hand on the page and the server (a drop, a click, the ✕, the table's boxes, the three bulk tools); Back; a later box change leaving a hand-changed card alone; "not set to teach" for a stranger and not for a form teacher; a fifth teacher refused; a head's drop, click, ✕, table boxes, Back and bulk tools refused; the Level box on step 2 readable again.

After the fix wave, by the controller, with the word set to "Class Parents" and the maximum 4: step 2's heading, count line and both buttons in the school's word; "Put the Class Parents on all of them" asking and then putting a class's four on its lesson on the server; the two-classes and none-yet lines under Things to fix; the profile line for a form teacher of two classes and none for another teacher; four Teacher columns in the table, four boxes on a staffed row and three on an ordinary one; the rule switched off and on again with a row holding four; the page's lessons equal to the server's; no console errors.

Not tried in a browser: publishing a draft and the line on the published pages (tested on the server side; a PDF with four long names was looked at); a four-name cell in a published grid; a staffed lesson wider than the maximum; a head's Undo and a head's row controls in the table (read only); the step 4 paste-list Remove; "(not on list)" in a box.

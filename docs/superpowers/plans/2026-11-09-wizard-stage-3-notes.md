# Wizard stage 3: decisions made while building, and what was left

From the build ledger of `2026-11-09-wizard-stage-3-teachers.md`. Each task had its own review; the whole branch had a final review, one fix wave and a re-check of that wave.

## Rulings (decisions made where the plan was silent or wrong)

- "New look" sits on the teachers table for now. The spec puts it on the teacher's profile, which does not exist until stage 4. Cost if wrong: one button to move.
- Browser checks ran on a scratch data folder. A real head sign-in could not be opened (reading the test codes is refused), so head checks set the role from the console, as in stage 2. Cost if wrong: a head-only page bug reaches the committee's try-out.
- Tasks 1 and 2 (the avatar and the list reader, one new file) went to one implementer and one review. Cost if wrong: none seen.
- Task 2: a list with a heading for another column but no name heading is refused ("Could not find the column of names. Head it Name or Teacher.") instead of being read by position; more name headings are recognised; a list read by position says so. Cost if wrong: a list the page refuses that it could have guessed.
- Task 2: two reviewer minors were raised and fixed: a row with data but no name was dropped without a word, and names such as "Constructor" could be misread.
- Task 3: a head in a practice copy cannot read an Excel file (the route that reads it stays committee-only). Final fix: for anyone who is not the committee the file button takes .csv only and the page says why. Cost if wrong: one route decorator.
- Task 3: removing teachers leaves availability rules on step 6 that name them. Step 6 flags such a rule ("… is not a teacher on the setup, so this row matches nothing"). Cost if wrong: a few rules to remove by hand.
- Task 5: the README review and the whole-branch review ran together; findings from both went into the one fix wave.
- Final: the preview names the new teachers, says which columns change, warns when a new name looks like a teacher who is not in the list, and Remove's question counts the lessons. This was a gap in the plan: the preview showed counts only, so a teacher spelt differently in the list could be added twice and the real one removed. Cost if wrong: a longer preview card.
- Final: "looks like" (`People.alike`) means: the same letters once punctuation and spaces are ignored, the same words in another order, one name's words all inside the other, or one or two letters different. It does not catch "Mohd" for "Muhammad"; the list of new names is there for that. Cost if wrong: a warning for two different people with near-identical names (it only warns).
- Final: a batch of 10 or more changes to the teachers takes a restore point first (the spec asks for one before a teacher upload; a change carries no label saying "upload", so size stands in). Cost if wrong: an upload of fewer than 10 changes relies on the 10-minute points and Undo.
- Final: reading an uploaded sheet stops at 60 columns and trims to the widest used column (also the Students upload). A sheet with stray formatting far to the right had used 448 MB.
- Final, left as they are: an empty cell in the list does not clear a field; uploaded teachers are never provisional; a .csv that is not UTF-8 comes in garbled (same as the Students upload); two browsers adding the same new name at once make two teachers (same as by hand).

## Deferred minor points

The reader (`static/people.js`):
- A quoted CSV cell with a line break inside splits into two rows; a line with any tab is read as tab-separated.
- Negative allowance and other-duties numbers are accepted.
- Role and department are compared with capitals ("st" against "ST" is an unknown role); names are not normalised for accented letters before matching.
- A one-column paste of "Nair, Arjun" is split into name and short name; a list with no headings whose first line is exactly "Staff" or "Name" is taken as a heading row.
- The heading row is looked for in the first 10 rows only; a longer title block is read by position, with a note.
- Two new teachers who share a first word get the same short name.
- The look-alike warning also fires for a shorter name whose words are all inside a longer one ("Tan Li" and "Tan Li Ying").
- The tests do not cover a byte-order mark, Windows line endings or an apostrophe in a name (checked by hand; they work).

The page (`static/app.js`):
- The preview can clear itself after the person's own Apply if the server's echo changes the teachers (it fails safe: read the list again).
- "The teachers changed since the list was read" stays until the next Read or typing in the paste box.
- Remove also drops empty teacher slots in the lessons it touches.
- "Add these roles" on an emptied roles table hides the default roles.
- A change from another browser that is still waiting to be drawn can leave a just-removed teacher named on one lesson (step 5 shows "not on list").
- Remove's question reads stiffly for one teacher on one lesson.
- Two quick New look presses within a second are one Undo.

The server:
- A workbook sheet named like "Teacher load" placed before "4 Teachers" would be read instead of it.
- A bulk table edit of 10 or more teachers, or a backlog sent in one go, also takes a restore point (48 are kept).

The README:
- It does not say that heads do not see the list card, or that in a practice copy a head may press New look on any teacher.

## Not exercised in a real browser

- A real head-of-department sign-in (the role was set from the console): the list card hidden, New look only on a provisional teacher, the .csv-only file button in a practice copy.
- Choosing an .xlsx or .csv with the file button (paste was used; the route and the reader have tests).
- Real mouse clicks on the avatar (clicks were made from the console).
- Remove carried through on the page (its question was read and cancelled; Remove then Undo was simulated with the sync code and restored teachers and lessons exactly).

## Note

The final reviewer, unasked, ran a real setup workbook's teachers sheet and a real staff export through the reader, read-only and printing counts only. Nothing from them was written or committed. Every teacher on the workbook's own sheet read with no notes; the staff export has no heading row the reader knows, so it was read by position and said so.

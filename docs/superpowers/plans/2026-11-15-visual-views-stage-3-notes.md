# Visual views, stage 3: decisions made while building, and what was left

From the build ledger of `2026-11-15-visual-views-stage-3-subjects.md`. Built subagent-driven on 2026-11-15 (a fresh implementer per task, a reviewer per task, one whole-branch review, one fix wave and one follow-up to it) on branch `visual-views-stage-3` from `main` at e91f46a.

## What was built

Step 3 (Subjects) has two views, switched at the top right: Cards and the Table. On Cards there is a column per department, and a subject with its G-levels is one card: the name and the code typed once, a tick box per G-level, one grid of periods with a row per G-level and a column per level, and Department, Room kind and Lesson length for the card. Ticking a G-level makes the subject "name G-level", as it is typed in the table; unticking removes it. The data is what it was, one subject row per G-level, so only the page changed: no workbook, reader, server or skill change, and the skill's version stays 2026-11.4. A new pure module, `static/subjectview.js`, groups the rows into cards and makes a card's changes.

## Rulings (decisions made where the plan was silent or wrong)

The plan's own faults

- The plan's sentence for the Delete question was wrong for one lesson row ("1 lesson row of step 5 use it."). The verb now follows the lesson rows ("uses" for one, "use" for more) and "it" or "them" follows the subjects being removed. Found at the task review.
- The plan counted the school's subjects from another copy of the workbook: the newest has 66 rows that make 39 cards, not 65 and 38.
- The plan did not look at how the app's own primary sample names its subjects: "English Language (Standard)" with the tag Std, which does not end in its tag. See "A primary school" below. Found at the whole-branch review.

The model

- A tick never makes a second subject of a name already on the list. A row typed in the table as "Science G2" with no G-level set is shown as it is; ticking G2 on the Science card would have made a second "Science G2", and lessons name a subject by its name. Found at the task review (the reviewer graded it minor; raised by the controller).
- `uses()` and a card row's `lessons` figure read lesson rows through one count, as text, so they cannot disagree.
- One test case pins names like `__proto__` and lists that are not lists (the guards existed and nothing held them in place).
- A new row made by a tick takes its code, department, room kind and lesson length from the card's first row in the list.

A primary school

- The spec's rule stands: a row whose G-level (or level tag) is not the end of its name is a card of its own, shown as it is. Rows named another way, such as "English Language (Standard)", are not guessed into a subject's card: that would be a rule about one sample's spelling.
- So that the obvious click cannot make a duplicate, a tick is refused when a row shown as it is already has that tag with the card's department and the card's code (when the code is not empty) and a name that begins with the card's name. The page names that row: "English Language (Standard) is already on the list as this subject's Std, on a card of its own."
- The first version of that rule refused a tick for any row with the card's department, code and tag. A count on the school's real setup caught it before the branch was finished: two groups of subjects there share a department and a code under different names, and 3 of the 62 G-levels a card could be given were refused. The rule was narrowed to rows shown as they are and named after the subject; all 62 then succeed. Found by the controller after the fix wave's re-review had passed it as "by design".
- The line on a row shown as it is now says what is so and no longer tells anyone to rename: "Shown as it is: this row's name does not end with its level tag, Std."
- A primary school's Cards view is therefore less tidy than a secondary school's: its "(Standard)" and "(Foundation)" subjects are cards of their own beside the plain subject.

The page

- The Delete of a row shown as it is asks first, like every other card's Delete.
- When a tick is refused because of a row already on the list, the page says which row; a box that sprang back with no word would look broken.
- The name toast and every sentence on a card read the school's own word through one helper ("G-level" or "level tag").
- Each card handler checks the lock itself, as well as its caller.
- The Delete question counts G-levels, not rows (a card with a plain row and three G-levels has 3 G-levels), names a one-row card by its row's own name, and warns about lessons only for names that leave the list (deleting one of two rows of one name warns of nothing).
- "The G-levels differ in room kind or lesson length: each has its own in the grid."
- The department columns fit two side by side at 1280 px (a column is at least 300 px wide); no card whose rows agree scrolls sideways inside itself at that width.
- Two people ticking the same G-level of one subject at the same moment leave two rows of one name: the second shows as a card of its own, "Another row has this name and G-level.", and deleting it leaves the subject whole. The page's merging was not changed.

Left as the spec says

- A change of name on a card does what a change of name in the table does, no more and no less: lessons keep the old name and show it as not on the list, and a name already used elsewhere is not refused.

## Checked at the whole-branch review

On the school's real setup (counts only): 66 subject rows make 39 cards in 11 departments with 4 levels: 21 cards of one row, 9 of two, 9 of three. One card has a plain row beside its G-level rows. No row is shown as it is, and every row is on exactly one card. A card's lesson and teaching-group figures equal a plain count. Ticking and then unticking each of the 62 G-levels a card lacks brings the rows back exactly, but for three plain subjects with no lessons whose periods are cleared (the change in place, then the emptying untick). A name changed and changed back leaves every card as it was. The model takes 0.16 ms.

The workbook: the same changes made through the cards and typed as table rows read back as the same subject rows, and a plain write and read of the real setup gives the subject rows it had.

The real page (times only, no picture and no text taken): 39 cards, 66 grid rows and 66 table rows. Once warm, Cards draws in 67 to 72 ms and the Table in 65 to 66 ms (the first two runs were 227 and 405 ms). A tick, an untick and a change of periods take 82 to 132 ms from the event to the page drawn again. No script error and no sideways scroll at 1280 px.

In a browser, by the reviewer, all seen and right on made-up data: making a subject with three G-levels from a card; Undo after each of eleven kinds of change, one step each, the list back exactly; a subject whose rows differ in room kind, a row whose G-level is not the end of its name, two rows of one name and G-level, a plain row beside G-level rows, a card with no name; a real department-head sign-in (both views, 539 controls disabled, the handlers refuse when forced, the setup's version unchanged); two committee tabs (the same tick in both; a card deleted in one while the other types lower down: the value lands on the right row); Things to fix clicks on Cards and on Table; a tag, a department, a subject and a code holding markup; steps 1 and 2, School & day, step 5 and step 6 unchanged (no new style rule matches anything on them).

After the fix wave, by its implementer on made-up data: the primary sample has 19 cards, 7 shown as they are with the new line; ticking Std on the plain "English Language" gives the toast, leaves the box unticked and adds no row. The Delete question read: "Remove Literature in English and its 3 G-levels? 10 lesson rows of step 5 use them. Undo takes it back." (a plain row and three G-levels); "Remove Higher Chinese G3? 4 lesson rows of step 5 use it. Undo takes it back."; "Remove Tamil G3? Undo takes it back." for one of two rows of that name. At 1280 px two columns sit side by side and none of the 25 cards whose rows agree scrolls inside itself; at 1024 px the page does not scroll sideways.

Every suite passes on the last commit: the model's 15 cases, the other eleven JavaScript files, the Python suites, the server checks (90, and 91 in full). `ttgen` and the skill's copy are identical and untouched.

No real name and no full school name is in the diff or the commit messages.

## Known limits, ruled to stand

- Tab out of a box that was just changed drops the keyboard to the page instead of the next box. This is so in the Table too, on every step, and is older than this stage: the redraw replaces the box the browser was moving to. It matters more on Cards, where name, Tab, code is the main way in. Tick boxes keep their place. Put to the committee lead as a follow-up.
- Changes made within one second of each other are one Undo step (as before this stage).
- A primary school's subjects named in a way that does not begin with the plain subject's name ("Higher Chinese Language" beside "Chinese Language") are not seen as that subject's level: ticking Higher on "Chinese Language" makes "Chinese Language Higher".
- `tests/test_helper.py --full` fails about one run in three, with a suggestion that swaps a group with itself. It does the same on `main` at e91f46a, and this branch changes no Python. Not looked into here.
- The page's drawing code has no automated test: the repository tests page code in a browser. The model has 15 tests.
- Unticking a G-level and ticking it again makes a new row after the card's last row, with blank periods; Undo brings the old row back.
- A rule, a room's "For" or the Class Parents' list that names a subject is not counted as using it: only lesson rows are, as the spec says.

## Deferred minor points

The model

- A lesson length stored as the text "2" shows as 2.
- `add()` on a setup whose subjects are not a list replaces that value; the page always holds a list.
- No test pins a row index that is text, negative or not a number, or a `null` row between real rows for tick, untick and remove; all behave correctly when tried.

The page

- A change of name on a card can give two subjects one name with no word, as in the table.
- A change of name in one tab while another ticks a G-level on the same card leaves a stray card of the old name; nothing is lost.
- The Things to fix messages on a card sit under the Department, Room kind and Lesson length line, not straight under the grid.
- The name box redraws the page even when the name did not change.
- In a grid whose rows differ in lesson length, the lesson length box is 40 px wide (two digits fit).
- A department head who forces a disabled periods box by script changes only their own page's copy; the server refuses it (as in the table).

## Not exercised in a real browser

Not tried in a browser: the Cards view on the school's real data looked at by eye (no picture of real data was taken); a real primary school's own setup (only the app's primary sample and blank); the committee's own site (it has this only after a merge and "Deploy Latest Commit").

# Visual views, stage 1: decisions made while building, and what was left

From the build ledger of `2026-11-15-visual-views-stage-1-classes.md`. Built subagent-driven on 2026-11-15 (a fresh implementer per task, a reviewer per task, one whole-branch review, one fix wave, one re-review) on branch `visual-setup-views` from `main` at fa01b16.

## What was built

Step 2 (Classes) has three views of the same data, switched at the top right: Cards, Bands and the Table as it was. A new pure module, `static/classview.js`, works out two models from the setup (`ClassView.cards`, `ClassView.bands`, and `ClassView.levels`); `static/app.js` draws them. Nothing new is stored in the setup, sent to the server or written to the workbook.

## Rulings (decisions made where the plan was silent or wrong)

The models

- A class with no name has no card in the model. The page draws such a class (one just added with "+ Add class") under a group of its own, "New classes", already open, until it is named.
- A band with no name yet is not drawn in the band picture. Before the fix wave it was drawn as a band whose groups were every lesson row with an empty band box, so those rows showed twice.
- A group with no subject yet stays in its band's bar, shown as "No subject yet", and takes no part in naming the band's row. Before the fix wave it stopped the picture from drawing at that level. Found at the whole-branch review.
- A named band with no groups yet is drawn, as an empty bar on a row of its own. (One test in the fix brief assumed otherwise; the implementer corrected the test, not the rule.)

The page

- The open card is remembered by the class row's own id, not by its place in the list. When another committee member deletes or adds a class above it, the card stays on the same class; when the open class itself is deleted, the card closes. The plan held it by place; the task review passed that, and the controller sent it back because of what two people working at once would meet.
- A click on a Things to fix message for a class opens that class's card, so the reason shows. From Bands the page switches to Cards first. On the Table nothing changes.
- A department head can open and close a card and switch views, and every field in the card is disabled. The Close button, the level picker and the bars are left usable on the locked step, beside the view buttons the plan named.
- The band picture's legend has a class name of its own. Its first form reused `.legend` and restyled the Brush legend on School & day; found at the task review and put right.
- The timing on the school's real workbook was done at the whole-branch review, not in Task 4: the real workbook stays out of an implementer's task.

## Checked at the whole-branch review

On the school's real setup (counts only): 32 classes, 4 levels, 460 lesson rows, 59 bands, no students on the list yet. Every class has exactly one card. All 246 banded rows are in exactly one bar and all 214 whole-class rows give a cell; no row is missing from the picture; no bar covers a class that none of its groups names. Seven bars are in more than one piece. The models take 2 to 3 milliseconds under Node.

With 1,256 made-up students on the real setup, 710 subject counts were each checked against a count done the slow way: none differed.

On the real page with those students: Cards drew in 36 to 44 ms, Bands in 16 to 17 ms a level, the unchanged Table in 79 to 137 ms. No script error.

A real department-head sign-in saw all three views, switched them, picked a level, opened and closed a card, clicked a bar through to step 5 and came back, and could change nothing: the setup was the same afterwards, with no Undo entry.

Two real committee tabs: with a card open in one, the other deleted a class above it (the card stayed on its class) and then the open class itself (the card closed).

A class named `1<b>A"x` and a band named `Sec 1 <i>Opt"&` showed as typed everywhere. A stale or wrong remembered view falls back to Cards. None of the new style rules can match an element that existed before. The Table's code is main's, with one attribute added to its rows. No real name and no full school name is in the diff or the commit messages.

## Known limits, ruled to stand

- The page's drawing code has no automated test: the repository tests page code in a browser. The two models have 18 tests.
- A class row that has no id yet (added and not yet saved) is held by its place until its first save, a moment later.
- Counts appear only for a class that has at least one student on the list; a class the list has not reached shows its subjects without counts.
- The band picture is for looking. Bands are changed on step 5.

## Deferred minor points

The models

- The cards model's lookup tables are plain objects, so a class, subject or group code named like `constructor` would confuse them (the band model's are safe).
- A school whose list of levels holds an empty level would show the classes with no level twice.
- A lesson whose band is not in the list of bands shows nowhere on the picture (the real setup has none).
- Two bands with the same name each show the other's groups; this comes from step 5's own code and is older than this stage.

The page

- A level whose classes all have a blank size reads "0 students" in its heading while each card says "? planned".
- A bar clicked at a level that is not in the school's list of levels opens step 5 with no band in view and no word about it.
- "See how the levels are banded" (no level chosen on step 5) opens on "No level" when some class has no level, not on the first level.
- The "New classes" heading has no counts, and the planned number of a nameless class is read in a second place.
- The Table view says nothing on a blank setup (as before this stage). Renaming a band in step 5's table does not rename its lesson rows (older than this stage).

## Not exercised in a real browser

Checked in a browser (a scratch server, the secondary sample and, at the review, the school's real setup with made-up students): the three views and the remembered choice; a card opened, changed and undone; Class Parents added from a card and followed by the class's lesson; counts after the sample's students were loaded; names with markup in them; the head's read-only page, with a real head sign-in at the review; the band picture's cells, bars, bars in pieces and second lines; the jump to step 5 and back; a blank setup; two committee tabs; a group with no subject and a band with no name.

Not tried in a browser: a card's Delete followed by Undo; a window narrow enough to scroll the picture sideways; a class holding more Class Parents than the school's maximum; a level that disappears (its last class deleted by someone else) while Bands shows it; the committee's own site (it has this only after a merge and "Deploy Latest Commit").

# Wizard stage 6a: decisions made while building, and what was left

From the build ledger of `2026-11-10-wizard-stage-6a-constraints-and-typed-rules.md`. Built inline (one executor), with one fresh whole-branch review at the end and one fix pass.

## Rulings (decisions made where the plan was silent or wrong)

- Task 1: the workbook reader sets `text` only on In words rows (and on any row with words in the column), not on every More rules row, so other rules, saved setups and sync diffs stay exactly as they were. Cost if wrong: nothing reads `text` on other rules.
- Task 3: the workbook column check ran through the app's `/api/build` route with the Flask test client rather than the page's download button (same route). Cost if wrong: none.
- Task 4: the clipboard could not be read back under automation (the page was not focused); Copy was checked by its toast and its fallback path. Cost if wrong: a browser without clipboard rights still gets the text selected.
- Final: the skill's workflow wrote the database before the report existed. SKILL.md and the starter prompt now say: solve, add the `Rule report` sheet to the timetable workbook, then `ttgen export` that workbook, so the database handed back carries the report. A round-trip test pins it.
- Final: the report parser skips a title row above the header, reads a number written "T1" as 1, and takes common header spellings (Strength, Typed rule, Met?). An unreadable header gives an empty report, which the page reports as none coming back.
- Final: typed rules are numbered over every In words row, including one `check` skips for a scope In words does not allow: the page, the sheet and `check` must agree, and a bad scope can now only come from a hand-edited workbook (the page offers only School, Level, Class, Subject, Room and Teacher). Cost if wrong: `check` lists such a row twice.
- Final: "+ Add rule" on a tab presets a rule type that applies to the tab's scope, never Fixed at (fixed lessons have their own button).
- Final, left as they are (the reviewer set them aside; each stands): a 20-second solve of the primary sample finding nothing (typed rules are matched by name and ignored; the 60-second smoke passes); `write_db` without the setup in `export_all` (unchanged behaviour).

## Deferred minor points

- The typed-rule count behind "The setup has N typed rules; the report has M" comes from the app's saved setup, not the setup the timetable was checked against; a timetable published before this change shows "No rule report came back" once the setup has typed rules.
- A typed rule with no target and no sentence shows one problem at a time on the page ("Pick the level" first); the workbook's Check column shows both.
- The exported "all timetables" workbook has no Rule report sheet, so re-publishing from it (or from Make printouts output) drops the report.
- SKILL.md says "add the constraint your solver needs" for a typed Must, but the scripted solver has no hook for it: an agent using the scripts can only edit `ttgen` or report Not met. A gap in the spec rather than the code.

## Not exercised in a real browser

- A real head-of-department sign-in (the role was set from the console): step 6 read-only with the tabs still switching.
- A real file upload on Publish: the check and the publish were driven with curl against the live server, and the page's own upload form was not clicked.
- Reading the clipboard after Copy.
- The user's own school: the sample schools were used; a typed rule, a title row and header variants in a Rule report were made by hand.

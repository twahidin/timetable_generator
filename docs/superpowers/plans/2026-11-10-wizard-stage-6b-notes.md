# Wizard stage 6b: decisions made while building, and what was left

From the build ledger of `2026-11-10-wizard-stage-6b-choices-and-configuration-id.md`. Built subagent-driven (a fresh implementer per task, a reviewer per task, one whole-branch review at the end) rather than inline.

## Rulings (decisions made where the plan was silent or wrong)

- Pre-flight: Task 1 also changes `SKILL.md`'s version line to 2026-11.1 (one line), so the README cell and the skill agree at every commit; Task 2 keeps the rest of the `SKILL.md` work. Cost if wrong: none (Task 2 would have written the same line).
- Task 1: rule choices on the Choices sheet are matched back by label, first untaken (plan-mandated). Overturned at the final review: a label of scope, target, subject and rule let two Not in periods rows for one level share an Item, so a Drop came back on the wrong one. The Item now also carries the week (not Both), day (not All), periods, number and venues, never the strength, in `ttgen/choices.py` and `static/choices.js` alike; exact match with first untaken stays for true duplicates, and the Must rows that Settings stands for are never matched.
- Task 1 review: periods are 0-based everywhere in the app (Settings says "Numbered 0-N-1"), so "periods 7-8" in the first-choice text is right; the recess rows default to Level. The README's stale `Skill version: 2026-11` was carried into this task and is now 2026-11.1.
- Task 2 review: `solve --export` stored the fallback-applied setup in the database, so a re-export would re-apply Drop and Instead by index. The `record_choices` helper now sets `m["setup"]` to the setup as read. `read_db` callers are `export.model_from_files` (updated) and tests; `test_rules` checks the two copies of `ttgen` are identical.
- Task 6: the brief's way of making the sums fail (a Sec 1 Not in periods over the day) is not critical in `checks.py`. The implementer used the no-school fixed lesson with a Drop choice, as Task 4's smoke test does. Cost if wrong: none, the check is equivalent.
- Task 6: the step 7 stat and the mode radios show only when the setup has choices (the brief drew the radios always). A mode for a list that does not exist would only puzzle the committee; the workbook still carries the default. Cost if wrong: one condition to drop.
- Task 6 review: `Choices.move` and `moveTo` renumber `order` 1..n (pinned by the Task 5 tests); the browser narrative stands on the implementer's report and screenshots.

## Deferred minor points

Reading and writing the Choices sheet

- Rule choices are matched back by label, so only rows identical in every labelled part are interchangeable (see Rulings).
- A setting's label is matched by its first 30 characters, as the Settings reader does.
- `used_from_rows` returns an empty list silently for an unreadable Choices used header (then k is 0 and a floated recess reads as a break).
- An unrecognised Used value ("Seconds") reads as empty, which counts as First choice, and raises no problem.
- `config_id` is compared after `setdefault` fills missing sections, so a false `+` is possible only if the saved setup lacks a key.
- `store._strip` drops a key named `choices` holding an empty list at any depth, not only at the top level, and has no direct test of the empty versus absent case.

Applying a fallback

- Nothing enforces one choice per item: two choices on one item both apply.
- Instead replaces the row with a clear and update, and drops `_id` on the copy.
- `isdigit()` rejects "3.0" as a second value (flagged, not crashed).
- `problems()` checks the recess on the level's first R day only; other days with no R in the window stay R (intended, untested).
- `Choices.moveTo` with an unknown `before` moves the row last; `move` with direction 0 returns true.
- After-school null reads Yes in JavaScript and No in Python; `timeOk` is stricter than `_minutes`; `newSetting` does not check the second value's format (`problems()` does).
- Three error sentences have no Python counterpart ("Pick the rule", and "already has a second choice" twice).

The check and the solver

- `with_fallbacks` calls `choices.problems` twice (once per item in a comprehension), and `/api/check` runs the findings twice for step 0.
- A raising first step in `with_fallbacks` re-raises into the `/api/check` catch-all (nearly unreachable).
- `solve` is long, and `cmode` is compared both ways.
- The `record_choices` test does not drive `main()`, so removing the call from the loop would go unnoticed.
- The Choices used list is checked on Publish only against the unknown-item path in the publish test; no valid-choices or multi-choice coverage there.
- The older, unsaved and newer configuration states are covered by inspection only (Task 3).

The page

- An Instead choice with no instead row (an older or hand-edited workbook) has no editor; the way out is to switch the fallback and back. A "Start from the rule" button would fix it.
- The add form stores a number second as a string; the in-place editor stores a Number.
- The in-place fallback select keeps a blank option.
- Focus after a mode radio change lands on the first radio.
- Rules without an `_id` are left out of the add form (every saved rule has one).
- Firefox caret trouble in inputs inside draggable rows (a drag handle would avoid it).
- Long single lines in `giveWay` and `download`; two literal colours in the CSS.

Tests and tidiness

- `_clock` and `_clock_min` duplicate formatting; the reader has a different `_clock`.
- The template imports choices, then the solver, then ortools at module load (the app already does via derive).
- `export.py` has a `wbu` name and a dense one-line conditional; `import_timetable` has a dense three-way conditional.
- Missing tests: a bad number or Yes/No second, a level with no R, a missing window, `rule_id` resolution, ties in `ordered`, a typed rule with a target, a Department rule, a Yes `settingValue`; the floating-recess test should assert the problems list is empty rather than "no 'break'"; the test name undersells the v7+ case and does not assert the `extra_settings` exclusion; a duplicate `import openpyxl` in `test_publish_uploaded_timetable`.
- The JavaScript test strings are hand-copied from Python, and `tests/choices.test.js` has a dead `rowOf` helper with `Math.random`.

## Not exercised in a real browser

- A real mouse drag of the give-way rows (the drags were synthetic drag events, as in stage 5).
- The browser's own Download workbook click (the workbook came from the same endpoint with curl).
- The unsaved, unknown and newer configuration states from a real upload (only their drawing was checked; same and older were reached with a real upload).
- The "Even after every second choice" state of Will it fit? was only checked by painting a stubbed result, never produced for real.
- The empty and not-on-list Choices used states were only checked by calling `choicesUsedHTML` directly in the page.
- A real head-of-department sign-in (the role was set, not signed in as one): step 6 read-only, no controls enabled.
- The user's own school: the secondary sample only.
- Compare mode and the `--export` folders of `ttgen solve` were not run by hand (covered by tests only).

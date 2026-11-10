# Return trip stage 1: decisions made while building, and what was left

From the build ledger of `2026-11-10-return-trip-stage-1-check-and-decide.md`. Built subagent-driven on 2026-11-10 (a fresh implementer per task, a reviewer per task, one whole-branch review, one fix wave, one re-review) on branch `return-trip-stage-1` from `main` at c95ad7e.

## Rulings (decisions made where the plan was silent or wrong)

- Pre-flight: `verify.planned_rows`/`deployment` assume a derived setup and never call `derive` themselves; `model_from_files` and the test helper derive. Cost if wrong: one call added.
- Task 1 review: the `set teachers` and `del` ops act on a whole step 5 row while a warning key is one class of it, so when a matched row lists more than one class `ops` is None (the lead changes step 5 by hand). An `extra` op for a group lesson adds the row with `code_override` = the group code. Cost: a few multi-class rows need a manual edit.
- Task 5: a warning's key must identify its hit, so the lesson detail carries the group code (or the subject for an entire-class lesson) as well as class, day and period; the `#N` suffix stays only for true duplicates. A suffix alone would let a "left" decision on `#2` move to another lesson when an earlier hit disappears. Cost: keys changed once, before any draft existed.
- Task 5: a "step5" decision is kept in `decisions.json` after its key disappears (it records that step 5 was updated from the timetable) and is counted as `step5`; only decisions with other answers whose keys vanish are dropped. Cost: a stale step5 entry in the published record.
- Task 6: periods are 0-based everywhere in the app (Settings says "Numbered 0-N-1"; the warning sentences from `ttgen` say `period {p}` 0-based), so the where line shows the 0-based period, not p+1.
- Final review: rule warning keys use the rule row's `_id` (falling back to the index for rows without one); `check_model`'s own period numbering agrees with the where line.
- Final review, the reviewer's "declined to judge" list, each ruled to stand: typed keys follow the T numbers (the spec fixes them); deployment keys follow derive's auto group codes (they are what the timetable carries); an upload for another school still writes the draft, with the `other_school` sentence; a joint entire-class lesson split per class is not reported; Same time across classes warns where the solver's note says it skipped the rule; At most N at once honours the rule's days and periods (the solver ignores them: fewer warnings, never false ones); verify checks scopes the solver does not enforce; a Group column spelled other than "Entire Class" reads as missing plus extra.
- Final re-review, parked as real and deferred: deleting a block row that has `code_override` can still renumber later auto-coded rows of the same level and subject; read-only workbook loading trusts the sheet's dimension tag (files from openpyxl, Excel and xlsxwriter write it correctly); the decide and publish routes catch only `ValueError`/`LookupError` (the GET and upload routes answer sentences for any fault); "Once a day per group" merges several entire-class rows of one subject for a class into one count.

## Fixed at the whole-branch review

- "Update step 5" on an extra lesson added a row without an id, which the change format skips, yet recorded the decision (a silent no-op shown as settled). The id is now given when the op is applied, the row goes at the end, a blank lesson level is taken from the class, and the step 5 path runs under the draft's lock.
- "Once a day per group" flagged a solver-made timetable 50 times: the solver allows ceil(lessons/days) a day, and so does the check now.
- "At least one recess a day" never saw recess windows (`W` is lesson time in the model's grid); the check now reads the raw day structure.
- A rule row with a non-numeric From/To, or From > To, crashed the whole draft; it goes to "not checked", and a draft that cannot be checked answers a sentence, not a 500.
- A "Special room weeks" row was reported in the other week as the wrong venue kind.
- Deleting an auto-coded block row would renumber the band's codes; del/add ops are offered only for entire-class rows and rows with `code_override`.
- The timetable workbook was loaded with merged-cell binding on every click (27 s for the solver's own secondary workbook); it is read read-only now (0.15 s).
- A typed rule whose report Result is blank or unrecognised was treated as Met; it is a warning ("the rule report does not say whether it was met").
- Publish re-read the setup instead of using the one the draft was checked against.

## Deferred minor points

Reading and checking

- `spec["subjects"]` and `m["room_ix"]` are read without `.get`; with `spec=` and a setup workbook both given, the workbook is read only for its configuration id.
- Fixed at with Level or School scope and no Subject flags most lessons of that day (the solver ignores such a row); a day-specific Fixed at also flags a second lesson of the same unit that day.
- `subject_test` matches untagged names and department codes where the solver matches exactly; Keep free together at Level ignores Subject.
- Avoid after-school slots warns once per group row of a block lesson.
- `_what` and `_key` use the first class of a joint lesson; `rule_days`'s `spec`/`per` parameters are unused.
- A Room "At most N at once" row with a blank or non-numeric Number is listed as not checked / raises in `_model` (now a 400 sentence).
- Report rows with `no` None share the key `typed:None:unknown` and read "line None"; blank typed text gives "…: ."; `check-timetable` on a workbook without `--setup` prints a traceback.
- Test gaps: scopes Room, Block, Subject, Group for the period rules; two-week day names; a teacher with no lessons; a level missing from the grid; the CLI without `--setup`, exit 0 and a Not checked line.

The draft on the server

- `publish` holds the draft lock for the whole export (about a minute for a large school), so `GET /api/draft` waits meanwhile.
- `paths()` raises on a draft folder without a timetable file (now a 400 sentence); a corrupt `meta.json` makes the status say there is no draft while `exists()` is True; the two-step folder swap is not crash-safe.
- `_build` reads the files outside the lock, so an upload that swaps the folder mid-build can fail that one request.
- A refused step5 leaves a stray restore point; an upload landing between a decision's build and its save writes the old build's open count; `draft.model()` is unused.
- The race test for decisions written during a build does not discriminate against the old code.
- The "step 3" refusal sentence is used for every warning with `ops` None when called through the API (the button is hidden on the page); the "periods … on step 3" text is also used when the figure is a step 5 `periods_override`.
- The spec's "links to step 3" for a periods or venue difference was left out of the plan; there is no link yet.
- Undecided open warnings are counted in the published record, but only the "left" sentences are kept.

The page

- The draft is fetched once per page load; another committee member's later upload needs a reload.
- `not_checked` is drawn in two places with a dead fallback.
- Smoke test tidiness: a conditional `kp` fallback, inline `__import__`, an unused `io` import.

## Not exercised in a real browser

The implementer's browser check (scratch server, primary sample, a one-lesson timetable) covered: upload to a draft with the open count, Update step 5 closing a teacher warning and changing the step 5 row, Leave it moving a warning to the Left filter, a reload restoring the draft, publishing with open warnings, and Published now showing the compared-against version, the left count and "No fixes were made in the app.", with no console errors. Not tried in a browser: the 409 confirm for unpublished fixes (always empty in this stage), the "other school" sentence, Reopen, the not-checked list, the 400 toast, a phone width, and the page after the final fix wave (the period number and the decision redraw were verified by reading and by the Node and server tests).

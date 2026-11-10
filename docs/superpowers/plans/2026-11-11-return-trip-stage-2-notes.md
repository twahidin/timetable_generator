# Return trip stage 2: decisions made while building, and what was left

From the build ledger of `2026-11-11-return-trip-stage-2-the-grid.md`. Built subagent-driven on 2026-11-11 (a fresh implementer per task, a reviewer per task, one whole-branch review, one fix wave, one re-review) on branch `return-trip-stage-2` from `main` at 648d96c.

## A defect in what was already live, found on the way

A setup saved from the browser holds its days alphabetically: the server sorted JSON keys on the way out and the page sent them back as it got them. Since stage 1 the draft is checked and published against the saved setup, so a timetable published through the draft showed its days as Fri, Mon, Thu, Tue, Wed. Fixed at the source in `ttgen/export.py`: the model builder orders the days by the calendar whatever order the setup holds them in (`order_days`), with a test that failed first. It is its own commit, on a local branch `hotfix-day-order` from `main` (ad0b4bc) so it can go live ahead of stage 2, and the same commit is on this branch (2163938). `app.json.sort_keys = False` also keeps the order through the API from now on. `ttgen/solver.py`'s `Problem.days` still takes key order; the app no longer solves, and workbooks are written in calendar order.

## Rulings (decisions made where the plan was silent or wrong)

- Pre-flight: the two-second bound on colouring a grid is asserted in the suite on the primary sample (the one the suite already solves) and was measured by hand on the secondary sample (57 ms at worst at first, 0.14 s for the whole options call at the final review).
- Task 1 review: an added lesson's number depends only on its place among the adds (the file's highest lesson id plus one per earlier add, applied or skipped), so deleting the highest lesson never lets a number be reused and a skipped add never shifts later fixes onto another lesson (the second half came at the final review). A malformed fix is skipped and listed, never an error for the whole draft. A move or add outside the day is refused.
- Task 2 review, overturning the plan: "more than before" is not counted per rule row. A fix is worse when it creates a rule warning that was not there before for the same subject: for a warning about a lesson, the pair (rule row, lesson id), whatever its slot; for a day-level warning, its key. So a lesson that already broke a rule and still breaks it after its own move is not held against the move, but a different lesson newly breaking it is red (Must) or amber (Prefer). The plan's count rule let a swap show green while a Must break moved from one lesson to another, which is the design's anti-goal. A warning's `where` gained `id` and `row` for this.
- Task 2 (carried into Task 4): "Keep free together" is about a teacher's or a class's day, so its warning carries no lesson id and its subject is its key; otherwise a day that stays broken through a different lesson read as a new break.
- Task 4 review: a rule in words is marked "check again" when a fix touches a lesson it is about, including a lesson that was deleted and one whose teacher or room was changed away from the rule's scope: `fixes.apply` also returns the rows as they were (`was`), and `verify.typed_again` judges scope on those too. A rule whose scope cannot be read is about every lesson (final review).
- Task 6: a click on a lesson that is a red or grey swap target, while another lesson is selected, selects that lesson; its reason is in its title and in the side list.
- Final review, the reviewer's "declined to judge" list, each ruled to stand: a single-class lesson may swap with a block lesson of that same single class (the plan's "same set of classes"; the design's point is that a band across classes is never broken up); the second class's own grid before a cross-class swap is confirmed stays with stage 3 (a sentence and a confirm today); a deployment difference a fix creates (a teacher who is not the one on step 5) is not part of "clean" and shows in the list afterwards; a "left" decision is dropped when a fix removes its warning and undo does not bring it back; the open count can be a moment stale when a read races a fix.
- Standing from the plan and flagged to the committee: a teacher change applies to every lesson of the class and subject or group; the server chooses an added lesson's room (a free home room of its classes, else a free room of the kind) and the lead changes it afterwards.

## Fixed at the whole-branch review

- After an add was skipped as a fix problem, later adds took a lower number and later fixes aimed at them landed on another lesson.
- An add always took the class's home room even when it was in use, so a missing band group could not be added back (every slot red or grey).
- In a teacher's week, a green cell that was a swap posted a move. A click now posts what its slot offers (`Grid.fixFor`), a delete names its row (`Grid.deleteFor`).
- An add's length is bounded to the periods in a day; "(1 period)"; the downloaded draft is labelled with the setup version it holds; a move to the lesson's own slot or a swap with itself is refused ("That changes nothing."); a teacher or class clash warning opens that week from its Fix the timetable button; the README says what grey means; the slow agreement test covers teacher fixes, an add, a delete and a chain of two fixes.

## Deferred minor points

Fixes and their judgement

- `Busy.lesson_time` tests every class's level where `check_model` uses the row's level (stricter for a cross-level row; none on the samples).
- "That fix is not complete." and "it is not complete." also cover a fault inside one fix, which hides the fault's own message.
- On a clash, `judge` returns at once with empty `must` and `prefer` lists, so the page cannot show rule breaks beside a clash.
- A delete can leave a student's group code with no lessons (only for a group that step 5 does not plan).
- An add whose key has several step 5 rows takes the union of their teachers. A re-added band group is its own lesson, so a later move of the band leaves it behind. A teacher fix on a combined-class lesson names only one class in its sentence.
- A swap posted from a stale page whose partner has since moved is accepted against the partner's new slot (the sentence is accurate and it can be undone).
- A move to the same slot or a teacher change to the same teachers still marks rules to check again when made through code paths that bypass the judgement.
- `fixes.py` is about 400 dense lines; `judge` is long; the key-to-lessons test and the neighbour index keys are written twice; private helpers of `verify` and `export` are used; `_ctx` judges an add with a different provisional number from the one it gets when applied (used only inside the judgement).

The draft on the server

- `published_fixes` counts fixes that were skipped. The download builds the model twice (the second is a cache hit) and reaches into `draft._now`. The teacher view counts after-school slots as lesson time. Odd-typed fix fields get the generic "Could not check" sentence. `draft.model` is unused.
- No test exercises `model_now`'s cache directly (a hit, a miss after a setup change, `save` clearing it).
- Old decisions whose key holds a day index point at another day after the day-order fix: a "Left for now" label may sit on another day's warning, which still counts as open.
- Blank typed text gives "Check it again: ."; a "met" decision stays through later fixes to the same rule's lessons (the record carries the times).

The page

- `Grid.deleteFor` posts no group for a blank-block lesson whose rows are spread over several classes when a class's week shows one row; posting the group always would close it.
- Other callers of `post()` still let a network failure go unreported; a failed options fetch offers no retry button; the ok/prefer test and the split-and-number pattern are written more than once.
- Mixed day naming becomes one unnamed week with full labels; a lesson with a negative period or one past the day is mishandled by the table (malformed input only).
- Smoke test tidiness: a helper called twice in one test, an unused helper.

## Not exercised in a real browser

The browser checks (scratch server, both solved samples, most clicks scripted through the page's own handler) covered: selecting a lesson and the slots colouring in about a second, a move, a swap, a teacher change, a room change, undo, a reload keeping the fixes, publishing with the fixes listed, the draft download, week tabs on the two-week school, a narrow screen, adding and deleting on a variant timetable with a missing and an extra lesson, a late answer dropped after two quick clicks, a swap from a teacher's week (on an amber cell), a clash warning's Fix the timetable button opening the teacher's week, and deleting one row of a two-row lesson. Not tried in a browser: posting "Still met" (drawn from a made-up warning only), the confirm for a swap that also moves another class's lesson (none arose on the samples), a class-clash warning's button, an add by clicking a cell after the final fixes, and the three failure messages (a failed options fetch, a failed grid refetch, a network failure), which were checked by reading.

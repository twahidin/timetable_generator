# Return trip stage 3: decisions made while building, and what was left

From the build ledger of `2026-11-11-return-trip-stage-3-the-helper.md`. Built subagent-driven on 2026-11-11 (a fresh implementer per task, a reviewer per task, one whole-branch review, one fix wave, one re-review) on branch `return-trip-stage-3` from `main` at 35e80ac.

## A defect in what was already live, found on the way

A lesson's after-school mark did not follow it. Stage 2's `fixes.py` left the mark as the file had it on a move or a swap and set it off on an add, while the checks, the "Avoid after-school slots" rule and the grid all read the mark. So an after-school warning could never be settled by moving the lesson, and a lesson moved into an after-school slot was not flagged. Fixed at the source: on a move, a swap and an add the mark is set from the setup's day structure (on when any period of the lesson is coded A for a level of the lesson). It is its own commit (223be91 here), went to `main` ahead of stage 3 as pull request 45 (b140c54) and is live.

## Rulings (decisions made where the plan was silent or wrong)

- Task 1 review, overturning the plan: a suggestion "settles" its warning only when the warning is gone and the set of deployment difference keys gained nothing. The plan compared the count, so trading one difference for another counted as settled.
- Task 1: when nothing is offered the sentence depends on why. Something was refused by a rule or a clash: "Nothing settles this without breaking a rule or a clash." with the refused fixes listed. Nothing was refused but nothing settled it: the "no single fix" sentence. A warning the helper has nothing to say about (a rule in words, a choice, a clash with no name, a lesson that is gone): the plain "nothing to suggest" sentence. "Give ... to nobody." is never offered.
- Task 3 review: in a preview a row is marked from its own (lesson, group) row as it was, never from another group of the same lesson. A batch is refused unless every fix has its sentence. `suggest` takes the model and the warnings from one state of the draft.
- Task 5: the stage 2 confirm box for a swap that also moves another class's lesson is replaced by the preview, which shows that class's week.
- Final review: when the warning a card was opened from leaves the list, the page follows it (the same key without its `#n`; else a clash for the same teacher or class; else the same rule on the same lesson) and carries on with that warning, saying it has changed. With nothing to follow it says "This warning is no longer on the list." It never says "settled": a key leaving the list is not proof the trouble is gone (a clash key holds its period span, a rule key its slot, and repeated keys are renumbered).
- Final review: every move sentence of the helper says where the lesson is now ("Move X from Odd Mon period 3 to Odd Mon period 1."). Two lessons of one class and subject are told apart only by their slot, and without it two suggestions could read the same.
- Final review, the reviewer's "declined to judge" list: a decision dropped when its warning's key disappears is not brought back by Undo (stage 2's ruling stands; a batch adds nothing new). No limit on a request body's size predates the branch and is left.
- The commit of Task 2 carries its implementer's own model line; left as it is.

## Checked at the whole-branch review

On the solved secondary sample, spoiled: 367 suggestions over 139 warnings, and 1354 more with six Prefer rules added, each checked against the full list of warnings. Every one settled its warning, none added a deployment difference or a Must break, and every new Prefer break was named. A batch is judged and written in one step under the draft's lock; no path to a half-applied or half-undone batch was found. The three new routes are for the committee lead only; 33 malformed bodies each got a sentence and wrote nothing. Every server string on the page is escaped. The slowest suggestion took 0.32 s (the bound is 2 s).

## Deferred minor points

The helper

- `helper._apply` copies the loop of `fixes.apply` (the rule for an added lesson's number and the broad except) and can drift from it.
- A slot refused by a Must rule on the lesson itself still makes pairs that always fail at the second step; they use up the cap of 40 (never filled in the runs). The second lesson's moves are judged again per blocked slot, and a full busy index is rebuilt per first fix. Judge calls inside `_moves` are not capped.
- A suggestion that moves a lesson from one after-school slot to another keeps its Prefer warning under a new key: it reads "Clean" and "Nothing else moves.", and a "Left for now" on the old key is lost.
- Rule warnings with no lesson and no who-and-day key get the "nothing to suggest" sentence. `say` assumes its lesson exists. "Then Move" has a capital M.
- The `--full` test checks that the warning is gone and no deployment key is new, not new clash or Must warnings (the final review's own run covered that once).
- `helper.py` is about 390 dense lines.

The draft on the server

- A stale Apply after another tab uploads a replacement timetable moves whatever lesson now has that number: fixes carry bare lesson numbers. Stage 2's grid clicks share this. A stamp of the draft in suggest and preview, refused on a mismatch, would close it.
- Preview payloads carry no short names for classes. An added lesson that is fixed again later in the same batch is marked "moved", not "new"; a teacher change and a move in one batch is marked "moved" only. A refused preview runs the chain twice.
- The stale-pair test asserts an exact list of moves to fixed slots, so it breaks if the ranking changes. The add-room part of one test is conditional.

The page

- Two answers for the same warning's ways can land out of order. Picking another class drops the ways. There is no retry or Close while the ways load.
- A cell that is both selected and marked hides the outline. The small table's cell drawing is written twice. `fxShorts` is rebuilt per class.
- `Grid.wasText` prints "undefined" for a day number outside the list; a batch named "" is treated as none.

## Not exercised in a real browser

The browser checks (scratch server, a spoiled draft of each sample) covered: the ways block, the blocked list, a two-fix suggestion applied and undone as one, the preview with another class's weeks, and a refused stale Apply. After the final fix wave: the move sentences with their "from", a real Apply that took its warning off the list ("This warning is no longer on the list.") and its Undo, and, with the draft's answer altered by hand, a clash coming back narrowed under a new key ("This warning has changed: ...", carried on with the new key). Not tried in a browser: a clean single teacher suggestion, a real swap that also moves another class's lesson (it was simulated), a real narrowed clash or renumbered key (simulated), phone widths, and late answers being dropped.

## Left in the fix wave

- Two lessons that are the same in every way (class, subject, group and slot) gave two suggestions that read the same. The fix wave's report said the samples do not produce this; the slow full run of the helper's tests did produce it afterwards (its solved timetable differs from run to run), so it was fixed after the re-review, test first: lines that read the same are offered once, the better ranked, and the place freed is filled by the next. That last change was not seen by a reviewer.
- Once a card has said "This warning has changed", the line stays on later redraws of the same card.
- The page's following of a warning has no automated test of its own (`Draft.follow` has; the wiring in `app.js` was read and tried by hand).

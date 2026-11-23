# Re-fit (stage 2 of saved versions and re-fit): decisions made while building, and what was left

From the build ledger of `2026-11-22-refit-stage-2.md` (design: `docs/superpowers/specs/2026-11-22-saved-versions-and-refit-design.md`, feature 3). Built on branch refit-1, with `origin/main` (be22d11) merged in before the final review, and again (19ac240, accounts stage 2 with Put back) after it: one conflict, the two import lines of `app.py`, both sides kept. That merge changes none of the re-fit's files, and a re-fit's history line (kind `draft`) is not something Put back acts on; the four re-fit routes are pinned to the committee in `tests/test_routes.py` with the other draft routes, and Apply writes its history line through the same `_draft_entry` as every draft save. Main was merged a third time (fbcad30, blank teaching-group rows), cleanly.

## What it does

On step 8, **Re-fit to the setup** works out one list of changes that settles what a changed setup broke in the uploaded timetable: a teacher who changed on step 5 (two who changed places are traded in one step), a lesson missing or extra, a wrong venue, a clash, a broken Must rule. Nothing changes until **Apply**. Apply keeps the draft as a version first and makes the list as one batch, so one Undo takes it all back. What the app cannot settle is listed under **Needs you** with a true sentence.

## One rule changed while building (the lead's decision, 23 November 2026)

The plan's rule was: a lesson leaves its day only when it is barred from that whole day. The first measurement on the real file showed that this rule, with bands fixed, answers about a third of teacher changes however deep the search goes (11 of 30). The lead was asked "May Re-fit move a lesson to another day, flagged, when nothing works on its own day?" and answered "Yes, allow it". So Task 7b was added:

- A lesson keeps its day. Only when no list of up to 3 moves answers a warning with the lessons on their own days may a lesson move to another day, or change places with a lesson of another day. Each such step is flagged **another day**.
- Same-day answers come first, always, for every warning of the list: a same-day answer of any warning is taken before any lesson changes day for another.
- Two teachers who change places on step 5 are **traded** in one step (no lesson moves).

The plan's Global Constraints still state the old rule (the plan was not rewritten); the design and the README state the new one.

## Checked on the real file (counts and timings only)

The newest real setup with the timetable that goes with it: 1,026 lessons (1,985 lesson rows). As they are: 0 warnings for Re-fit to work on. Made-up changes were then made to a copy of the setup and the plan was worked out through the app's own functions on a scratch data folder, deleted afterwards. No name was printed. The machine was shared with two other builds, so every time reads slow (load 4 to 10 for the first figures, 60 to 90 where said).

| Made-up change | Plans | Answered | Seconds, mean and longest |
|---|---|---|---|
| One teacher changed to the colleague of the subject who is free most | 30 | 16 of 30 whole (before Task 7b: 14 of 40; with every lesson on its own day at most 11 of 30) | 2.0 to 2.9; 10.5 to 20 |
| One teacher changed to a random colleague of the subject | 30 | 11 of 30 whole; 1 not looked at in time | 4.6 to 5.5; 32 |
| Two teachers trade a class | 30 | 30 or 31 of 60 warnings; 11 or 12 of 30 plans whole; 4 by a trade step | 9 to 15; 32 (2 to 8 plans not finished in time, more with the load) |
| A teacher away one weekday (a Must rule added) | 20 | 25 of 98 broken-rule lines; 36 of the 98 are lessons of bands, which never move | 2.7 to 6.5; 15 |
| Six teachers changed at once | 6 | 11 of 36 warnings; 3 or 4 of the 6 plans not finished in time. With 90 seconds: 12 of 36, none late, 85 s | 21 to 28; 32 |
| One class: one period more of a subject, one fewer of another | 20 | 14 of 20 adds; 0 of 20 deletes, rightly (see below) | 7.4; 20 |
| One class: one lesson (3 periods) more of a subject, one lesson fewer of another | 20 | 33 of 40 warnings: 20 of 20 deletes, 13 of 20 adds; 13 of 20 plans whole; 8 plans take a lesson to another day | 10 to 16; 31 to 38 |

- **Steps of the answers** (teacher to the freest colleague): 16 teacher changes, 10 exchanges, 5 moves; 6 of the 16 plans take a lesson to another day (1 to 4 lessons). A teacher away one weekday: every answer goes to another day, as it must.
- **The same again on the final code** (after the final review's fixes): 16 of 30 and 33 of 40, as before.
- **Nothing wrong was offered.** In every run: no list was refused by the judge that Apply uses, no plan raised the number of critical mistakes or of warnings, and every warning a plan said it settles was settled when the list was judged again (0 of all).
- **A period fewer is not a lesson fewer.** At this school a lesson is 3 periods long, so a setup that plans one period fewer cannot be met by deleting a lesson: the app refuses with "That would leave … with N periods; step 3 plans N.", which is true. The realistic change is a whole lesson more or fewer (the last row): every surplus lesson was deleted, and two in three missing ones were added, 10 of them after a move.
- **The limits.** `MAX_NODES = 250` is never reached on the real file: one search judges 4 to 11 lists on average and 143 at most, and a run with 80 gave the same answers. What ends a search is that it has tried everything inside the lead's rules, or the time. `BUDGET_S = 30` leaves a single change well inside it (2 to 8 s on average). A large change (six teachers at once) does not finish: the list says "Not looked at in time; run Re-fit again." for the rest, and applying the list and running again carries on. **No constant was changed.**
- **The time is wall-clock.** With the machine very busy (load 60 to 90) the same trades run gave 24 of 60 instead of 31, with 14 plans not finished in time. On a slow or busy server more will say "run Re-fit again".
- **Apply's own check** of a finished list (`helper.chain`): 0.4 to 1.3 s (4.9 s at load 80).
- **Why not more is answered.** Experiments on the real file (30 samples each) before Task 7b: larger limits change nothing, because the search is narrow, not cut short. With lessons kept on their days and bands fixed, an exhaustive search of up to 6 moves answers 11 of 30; with other days allowed 20 of 30. Judging the moves "with the new teacher already in place" instead of step by step would add 1 answer in 13, so the judge stayed step by step.

## Rulings made while building

- Every limit and every fixed sentence is a constant at the top of `refit.py`.
- Every step keeps the row objects it does not change, because `helper.settles` tells rows apart by identity.
- When a teacher change is blocked, the lesson itself may be moved too (not only the lessons in its way).
- Among answers of the same depth: fewest lessons moved first (a swap moves two), then fewest to another day, then fewest typed rules touched, then the shortest distance, then allowances.
- A clash the setup allows (an allowed double, no "critical" mark) is not something to re-fit.
- Whether a lesson's own day is barred is judged with the teacher it will have.
- At most 8 changes of step 5 itself in one answer; more says so.
- A list never names a lesson that the list itself adds; such an answer goes to Needs you.
- The list has "Settled by these changes too" for warnings that other warnings' changes settle, and the tag "no room" on an added lesson without a room. A last look puts there whatever the final list settles.
- A missing lesson of a subject whose teacher also changes waits for the teacher change. When that has no answer: "Its teachers differ from step 5 too: settle that first, then run Re-fit again."
- A lesson is never added for a subject that has no teacher on step 5: "Step 5 has no teacher for it: choose one there first, then run Re-fit again."
- A teacher only added or only taken off (or given to a lesson that had nobody) is one teacher fix, searched as a change of one for another, with no trade; its reason says "Step 5 adds {name} to it.", "Step 5 takes {name} off it." or "Step 5 gives it to {name}.". More than one teacher changing still needs you. The lead decided this on 23 November 2026, after the merge (before, these needed you).
- The check of the whole list compares sets (mistakes, Prefer wishes, Must rules), judges answer by answer, and when the list as a whole is not one to offer, gives up only the answer at fault, inside 10 seconds.
- A line in the server's log names the kind, the error type and the file and line only, never a word of the timetable.
- The plan lives in its own file, `refit_plan.py`.
- Apply: the answers of typed rules ("met" taken back) are written before the draft, so a failed write leaves a rule open rather than wrongly met. The history line is written at once. When the check after the write fails, the page is still told that the re-fit was made.
- Apply and Preview answer "The draft changed since this list was made. Run Re-fit again." also when the draft or the setup is gone.
- Whether there is anything to re-fit is said by the server (`refit` in the draft's information), not by a copy of the rule on the page.
- Opening the window shows a running job or a fresh finished list, else starts a run at once. Cancel keeps the list on the server.
- Another day (Task 7b): a far look comes only after every same-day look; a same-day look that was cut short is made again before any far look; the far round stops at its first answer and starts again from the same-day looks; there is no far look for a room warning, for one that still waits, or for one whose same-day look judged nothing. An exchange counts two lessons to another day. At most 12 places on other days are tried for a lesson, and at most 3 trades for a teacher change.
- A blocked trade says the first trade's refusal, but not one that is about the other class's period (that is said under the other warning).

## Checked in a browser

On a scratch server with the sample school's made-up names, twice (before and after Task 7b):

- The button: enabled, and greyed with each of its two reasons. Starting, the progress, Escape while it runs (the polling stops) and opening again.
- The list: a trade as one step with the mirrored warning under "Settled by these changes too", a teacher change, an add, a move to another day with its chip, "check T1 again", Needs you, the totals and the footer.
- Preview on the board: one request, the changed lessons outlined, hidden and shown again, the narrow period column.
- Apply: with the answer held back, Apply, Preview, Close, Cancel and the board's Undo are off and Escape does not close. Then the toast, the version "Before re-fit …" in Versions, and one Undo that takes every change back.
- A draft changed in another tab: the sentence, the list greyed, the focus on Run Re-fit again, which makes a new list. A failed run and an app restart.
- The keyboard: Tab stays inside, undo keys do not reach the board, the focus goes back to the button. 375 px wide: no sideways scroll.

- After the final review's fixes: the chip of the rule of days reads "Lessons stay on their day unless nothing works there"; a list that settles everything is applied and the button greys with "Nothing to re-fit: the timetable fits the setup.".

Not checked: the school's real file in a browser (it was measured through the app's functions only); a Needs you line whose reason equals its text (read in the code); Safari and Firefox; a slow network; printing; how much slower other pages are while a re-fit runs (the job is a thread of the one web worker, for up to 40 seconds).

## The final review (whole branch, then one fix wave)

Verdict: ready with fixes, nothing critical. Made in the one fix wave: the chip of the rule of days (it stated the old rule); a Needs you sentence that was about a timetable the list had changed since now says "Not looked at in time; run Re-fit again."; an unforeseen error inside a change is logged and said as "The app could not work this one out: change it on the board." instead of being hidden; `_trades` stops at its limit; an explicit return in the check of the whole list; a pointer in the plan's rule of days.

Left as they are, by ruling:

- **Focus after an Apply that settles everything.** Put right in the follow-up of 23 November 2026: after the redraw that follows a made Apply, `rfRefocus` gives a focus left on nothing to the first of Re-fit and Versions that is on.
- When the check of the whole list takes an answer out, a later answer that went to another day because of it stays, and the answer taken out says "No list of up to 3 moves fits it." though a list was found. Rare: no list was at fault in any run on the real file.
- With only Not placed lessons, lessons without a teacher or two bands at one time on the draft, the button is on and the window says "The app has no change to offer for these." with each under Needs you. Greying the button would say "the timetable fits the setup", which would be untrue.
- A deletion, and a teacher change that is blocked for good, still get a look on other days that cannot help them, and can say "Not looked at in time" when the time is up first.
- A teacher change or a trade may be made on a lesson an earlier warning moved (the rule is about moving a lesson twice).
- Answers to warnings are not part of what makes a list stale.
- Each answer is judged with the Not placed lessons as they were before the list; Apply judges the whole list again and writes nothing when it refuses.
- A search stopped by its limit of lists could let an answer on another day in before a same-day one deeper in the search; the limit was never reached on the real file.
- The cures of the check of the whole list can change what the list leaves after a Needs you sentence was written for another warning.

## Suites

Each on its own, all passing, on the code of the final fix wave and again after each merge of main (the last on fbcad30): the 29 Python scripts (`tests/smoke.py` 103 checks, `tests/test_refit.py` 166, `test_board` 59, `test_versions` 44, `test_routes` 18, `test_fixes` 65, `test_helper` 20, main's new `test_putback` 37 and the others), the 18 `node tests/*.test.js` files, and `node --check` on the 28 scripts of `static/`. In one earlier run `tests/test_sync.py` failed on its own one-second timing check while the machine was busy and passed when run again; this branch does not touch it.

## Deferred small points

- A shortage that is not a whole number of lessons needs you.
- No list moves a third lesson away so that a second can take its place (moves and exchanges only).
- A teacher change whose subject has two of its own lessons at one time is refused until the clash is settled (a second Re-fit answers it).
- A surplus lesson waiting in Not placed cannot be deleted by the list.
- A teacher change at Apply also changes waiting lessons of the subject; a typed rule of a waiting lesson's former teacher is not flagged.
- An unexpected stop inside Apply leaves the job taken out (run Re-fit again).
- The Needs you sentence of a blocked trade is chosen by the wording of the judge's clash sentence; a rewording there would change it silently.
- Some lines of `refit.py` and `refit_plan.py` are very long (the files' style).
- The plan's first-task minors: how the kind of a warning is read from its rank, and the coupling to `helper._dep_parts`.

## What stage 3 could add

- A "Try harder" button that hands what is under Needs you to the solver (the design's approach B).
- Judging several teacher changes together, for a change of many teachers at once.
- "Keep looking" for a list that ran out of time, instead of applying and running again.
- Placing lessons that wait in Not placed.
- Changes to a band itself (a banded subject gaining or losing periods, a group joining or leaving).

## Follow-up after the merge (23 November 2026, branch refit-2)

The lead answered "Yes" to both open points, so:

- **A teacher only added or only taken off is made.** One teacher added to a subject, one taken off it, or one given to a lesson that had nobody, is one teacher change in the list, with its own reason ("Step 5 adds … to it.", "Step 5 takes … off it.", "Step 5 gives it to ….").  More than one teacher changing still needs you. Ruling: "a teacher" is read as exactly one (the question was in the singular).
- **The focus after Apply.** After the draft is redrawn the focus goes to "Re-fit to the setup" when it is still on, else to Versions. Seen in a browser in both cases.

On the real file (counts only, 30 made-up changes each, the scratch folder deleted): a second teacher added, the colleague of the subject who is free most: 16 of 30 answered (2 s on average, 10 s at most; 6 take a lesson to another day); a random colleague: 11 of 30 (one not looked at in time). These are the same numbers as for one teacher changed for another, because what stands in the way is the same: the new teacher's own lessons. One of two teachers taken off: 8 of 8 answered with no move, under a second (for 22 of the 30 rows picked, step 8 listed no difference at all, so there was nothing to re-fit). Nothing wrong was offered in any run.

Checked: a review of the change (approved, nothing to fix before merging); every suite on the result. Left as small points: the test of a period that waits for a teacher taken off shows the result but not the order of the looks; if the window is opened again in the instant before the draft is fetched after a failed check, the focus can go to the button behind it.

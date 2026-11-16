# Upload and edit, stage 1: decisions made while building, and what was left

From the build ledger of `2026-11-16-upload-and-edit-stage-1-two-steps.md`. Built subagent-driven on 2026-11-16 (a fresh implementer per task, a reviewer per task, one whole-branch review, one fix wave and its re-review, then one more narrow correction and its re-review) on branch `upload-and-edit` from `main` at 49033b1. Design: `docs/superpowers/specs/2026-11-16-upload-and-edit-design.md` (stage 1 of 4).

## What was built

Step 8 is "Upload and edit": the upload, the check and today's editor (the warnings list, the Fix card, the helper, the typed box). Step 9 is "Publish": it shows the critical mistakes, then every warning, and publishes. It publishes nothing while a critical mistake remains: the button is off, the page says how many to settle on step 8, and the server refuses (409) whatever the page does.

Every warning carries `crit`. Five kinds are critical: a teacher in two lessons at once (`teacher`), a whole-class lesson clashing with another lesson of the class (`class`), a room holding more lessons than it takes (`room`), a lesson in a break, in recess, outside the day or past "Lessons end by" (`break`), and a lesson with no teacher (`noteacher`, a new line). Everything else is a warning: a broken Must rule, a difference from step 5, a typed request not met. Two bands of one class at the same time are not a clash.

The answer "Leave it" is gone. A warning is open, met, or sent back to step 5. A "left" answer stored by the old code reads as open.

The printouts (one file or one per page) are made from the draft on step 9, before publishing, by `POST /api/draft/printouts`.

The outside agent's own check (`python -m ttgen check-timetable`) starts with "N warnings, K critical (…)" and marks each critical line. The skill is 2026-11.6.

A page left open on step 8 or 9 picks up a draft changed elsewhere (another tab, another committee member, a new upload) within about one poll, without a reload.

## Rulings (decisions made where the plan was silent or wrong)

The plan's own calls, not yet confirmed by the committee lead

- The limit of 30 on each kind of clash line is gone: every critical mistake is listed, since each one stops publishing.
- A lesson with no teacher is a new line and is critical.
- A lesson with no room is not listed until stage 3 (the Not placed tray and "none" for a room arrive there).
- Step 9 is read-only apart from Publish and the printouts. Nothing is settled there.
- The Publish button is drawn but off while a critical mistake remains, with the count beside it.
- The skill's version went to 2026-11.6 because the agent's check changed.

Reaching a critical mistake from step 9

- Every critical mistake has a place, so "Show on step 8" opens the class's week with the lesson selected. This took three rulings. A lesson in a break first had no place (68 of the 99 critical mistakes on a real file would have been a dead end); `check_model` now returns a place for it. A room line was first ruled to have none and to get "Find it on step 8" instead; the whole-branch review showed that landed on a line with nothing to press, so the ruling was reversed and a room line has a place too. A lesson with no teacher has its day, period and id in its place.
- Two check lines that read the same (the same subject for two classes in the same break period) each get their own place, handed out in order.
- "Find it on step 8" stays for a critical mistake that still has no place (none is known today).

The helper and the Fix card

- For a lesson with no teacher the helper offers no moves and says "This lesson has no teacher. Pick one under Change the teacher." A move never gives a lesson a teacher.
- The fix sentence for a lesson that had no teacher ends "…; it had no teacher."

The page

- A browser that remembered the old step name "publish" opens step 9.
- Steps 8 and 9 fetch the draft when opened and again when the status's draft summary changes (`uploaded_at`, `open`, `critical`, `fixes`). The setup's save time is not part of that, so someone editing the setup does not reset an open Fix card. A publish in progress holds the loader. A fetch that failed is not tried again until the summary changes or the step is opened.
- "Loading the draft…" is shown while the first fetch runs, where the page used to say "Nothing to publish yet".

The build itself

- The browser tool cannot choose a file, so a script uploaded made-up timetables to a scratch server for the browser checks. The upload control itself was not clicked.
- The process allows one fix wave after the whole-branch review. This build made one more, narrow correction, with its own review, because both faults it removed were brought in by the fix wave (the helper offering moves for a lesson with no teacher; the page refetching on every poll while the setup was being edited).
- A builder ran a stray `git stash pop` and dropped one of the committee lead's old stashes. It was found and restored. Builders and reviewers are now forbidden every form of `git stash` and `git checkout -- <file>` in this checkout.

## Checked on the real files (counts only)

- The returned timetable of 10 November: 145 warnings, 99 critical (31 teacher, 68 break), every one of the 99 with a place; publishing is refused with 99. Main's code gives 144 lines for the same file, none of them missing on the branch.
- The newest returned timetable: 198 warnings, none critical; the same 198 as main.
- A draft made by main's code, with one fix and one "left" answer, opens on the branch: the fix is kept and the warning is open again.
- No commit holds the school's full name or a real teacher's full name.

## Left as it is

- After "Show on step 8" the keyboard's focus stays where it was. The editor is rebuilt in stage 2.
- The Fix card's move sentences still have an em-dash, and clash places carry no day. Both are older than this stage.
- Below 1000 px the step list is a strip that scrolls sideways.
- The Published card of a record made before this stage can say "197 warnings were open" above a list of 3. Old records counted differently; new ones agree.
- The limit of 30 on rain-room lines stays (they are warnings).
- After publishing, the draft stays and Publish is on again, as the return trip's design says.
- A stale answer to an older fetch can replace a newer draft on the page for one poll (about five seconds), then corrects itself.

## Deferred minors

- `verify.crit_of` reads the words of a check line. A subject or class named "Class clash:" or holding "sits in a break" would be misread. Tagging at the source would change `check_model`'s output.
- The helper's check that a move settles a room line or a break line looks only at the class's overlaps. The moves it offers are already judged clean by the editor's own check.
- `Draft.follow` can follow a settled room line onto another clash of the same class and say "changed" where "settled" is meant.
- `Draft.critWord` looks its word up in a plain object. `counts` and `critical` throw on a null entry. The server sends neither.
- `draft.printouts` builds its model outside the lock; an upload landing mid-build makes the route answer a plain 400.
- During the minute a publish takes, a redraw of step 9 draws the button on again. The server's lock holds.
- After a publish that fails with an error other than 401 or 409, a summary that changed meanwhile is not fetched until the step is opened again. A dropped fetch answer can cause one extra fetch.
- The upload card keeps `id="printouts"`.
- No automated test of step 9's lists, of the gate on the page or of the Published card. The page was checked in a browser; the server's refusal is tested.
- Tests not written: a band with two groups that both lack a teacher; a warning with no `crit` key; an unknown `crit`; a critical warning marked met. Two tests write a "met" answer straight into the file on keys the app would refuse.

## Next

Stage 2 is the board (one day of the whole school, cards dragged). Stage 3 is forcing and Not placed. Stage 4 is teachers and rooms on the card. Each needs its own plan.

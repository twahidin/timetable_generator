# Exams stage 3 meets relief stage 3: notes

Built 22 November 2026 on the lead's "continue on to next stage", on branch `exams-relief-join`: exams-stage-3 (07b002a, PR
#85) + main (a5ca928: exams stages 2 and 4 merged) + relief-stage-3 (d693183, PR #88, with relief stage 2, PR #84, under it).
Plan and decisions J1 to J8: `2026-11-22-exams-relief-join.md`. Built here (not by subagents, as the two sides had to be held
in mind together), then reviewed by a fresh reviewer, one fix wave, one scoped re-review.

## What it gives

- **Picks, approval, Change, Approve all, Split and Join** refuse a lesson an approved exam or event stops; the background
  picks leave it alone (the model is not asked). Nothing about a stop is written down: withdraw the exam and every cover is as
  it was.
- **Nobody on an exam duty or at an event** is picked, approved or changed to. A waiting pick of theirs is made again; an
  approved relief stays and is flagged until the team changes it.
- **Today**: a stopped lesson is greyed, "Not happening" with why, no buttons, out of the counts; the teacher of a backup has
  their duty beside the name; Change's list has the "on an exam duty or at an event" fold.
- **Reliefs I'm covering**: "Not happening", with why and no buttons. **What's in**, **Planned by me** and the planned relief
  sheet leave it out or say so. **My absences** shows only "Not happening" for it.
- **Load**: "Exams and events this week" (shown in a week that has any; always in the Download), counted in "Week so far"; a
  relief of a stopped lesson is listed as "not happening" and not counted. The AI's "teaching periods this week" counts them
  the same way (its instructions say so).
- **A teacher on a duty who sends their own absence** takes the backup's lesson over with everything relief has done on it:
  the pick, the approval, the acknowledgement, a request to change, the parts, the history.
- **The exams side** counts and names a relief teacher only once the relief team has approved them.

## Rulings (each with what it costs if wrong)

1. J1 is worked out on reading, never written. If wrong: a stopped lesson would need marking and unmarking.
2. An approved relief is never dropped by an exam, only flagged (as relief does for any other reason). If wrong: one condition.
3. A planner's choice on a new absence is refused when the backup's relief is approved for someone else, or the lesson is split,
   naming the lesson, before anyone is looked up. If wrong: the choice could be ignored instead.
4. A lesson that leaves a backup is kept in the record's `gone` list, its cover ended; the list is sent to nobody (it holds picks,
   reasons and what a relief teacher typed). If wrong: the list is not kept.
5. Waiting picks hold nobody for the exams side. If wrong: one condition in `_approved_covers`.
6. A relief on a lesson this schedule itself, or another approved one, stops holds nobody; "this schedule" is the copy being
   worked on (the approved copy when someone is replaced on it). If wrong: a needless "covers relief then".
7. On the exams page a split lesson's relief shows once every part is approved. If wrong: one condition.
8. `Links` reads nothing on a date no approved schedule (and no duty) holds. If wrong: slower, never different.
9. If the exams cannot be read, relief works as if there were none (one log line). If wrong: relief stops with the exams.

## Checked

- The review found no Critical, three Important (`gone` was sent to the absent teacher; replacing someone on an approved exam
  read the working copy; event pages did not free their own stopped reliefs) and six Minor. All fixed. The re-review found one
  Important left (a review of an approved schedule with an unsent edit read the working copy for relief) and three Minor; fixed
  too. 54 deliberate single-line breaks, both reviews' survivors among them, each now fail a test.
- Every suite on the final code (fbbb06b), all passing: `test_accounts` 13, `test_admin` 18, `test_ask` 49, `test_board` 58,
  `test_choices` 16, `test_combined` 38, `test_exams` 187, `test_exams_relief` 88, `test_fixes` 65, `test_helper` 20,
  `test_history` 27, `test_history_draft` 9, `test_parents` 35, `test_relief` 42, `test_relief_requests` 59, `test_relief_team`
  68, `test_routes` 18, `test_rules` 11, `test_signin` 24, `test_sync` 32, `test_teachers` 9, `test_typed` 33, `test_venues` 4,
  `test_verify` 56, `smoke` 102; every `tests/*.test.js`; `node --check`; and `--full`: `test_fixes` 67, `test_combined` 39,
  `smoke` 103.
- `test_typed --full` and `test_helper --full`, whose 30-second solves need a quiet machine, failed at first on this branch and, the
  same way, on plain main (a5ca928), while other work kept the load at 8 to 35 on 8 cores; no file they exercise (typed.py,
  helper.py, checks.py, fixes.py, ttgen) differs from main. Run again on 22 November: `test_typed --full` passed (34).
  `test_helper --full` passed 1 run of 3 (21): its failures are not load but a fault in main, a swap with another lesson of the
  same group counted as settling a rule warning, fixed on 16 November on the unmerged branch `helper-full-flake` (b21c9cb). With
  that fix it passed 3 of 4; the fourth failed another check (a Music Room clash), not looked into.
- **The school's real timetable, numbers only** (scratch data, deleted): 111 teachers, 8 made-up absences, 25 lessons to cover,
  all picked and approved; a made-up whole-day Sec 3 exam stopped 5 of them: Today counted 20 and showed 5 as "Not happening",
  and all 25 were back after a withdraw. No waiting pick sat on anyone with a duty. Today took 1.2 to 1.4 s with the exam
  (0.9 s without), Load 0.1 s, the rest under 0.02 s; an idle timer tick 0.0 s with nothing waiting and 1.1 s with 19 waiting
  (a "free then" each, as before). With week changes kept for a request (the fix wave), Today with and without the exam took
  the same time, within the noise of a busy machine.
- **Browser**, made-up school, real clicks: Today for a date with a stopped lesson, a backup's duty, the free list's fold,
  choosing (approved at once), Fill now; Reliefs I'm covering as the relief teacher; asking for one's own absence while on a duty
  (the approved relief came along, the backup was cancelled, Today kept one row); Load with its column, a name opened; What's in.

## Known limits

- Nobody is told anything until relief stage 4. For stage 4: a takeover moves a cover to another absence id (the absent teacher
  and the cover key stay), and a stopped lesson keeps its state, so use `cover.stopped(links, x)` before reminding anyone.
- A lesson counts as running while any of its periods runs, also for a part of a split lesson that is wholly inside the exam.
- Today's "N teachers away" counts a teacher on a duty.
- An exam approved with a duty for today sends backups the timer picks up within a minute (relief's "at once").
- `Links.load` reads every schedule file, on each Today poll and each timer run; small today, worth a look after some years.
- A relief teacher's acknowledgement is not asked again when a takeover moves the lesson.

## Merging

PR #85 (exams stage 3) merges cleanly with main and contains PR #84 (relief stage 2), so #84 closes with it. Then this branch,
which contains PR #88 (relief stage 3), so #88 closes with it; on their own #84 and #88 conflict with main. Relief stage 4 is being built on d693183 and meets this in `relief/web.py`, `fill.py`, `absences.py`,
`relief-today.js`, `relief.js`.

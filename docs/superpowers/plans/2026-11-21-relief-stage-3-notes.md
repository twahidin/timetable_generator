# Relief stage 3: notes

Built 21 November 2026 on branch `relief-stage-3` (from relief-stage-2 4dde1f7, PR #84 open; relief-stage-2 41c5035
merged in before Task 4), subagent-driven: a builder and a reviewer per task, a fix round where the review asked.
Plan: `2026-11-21-relief-stage-3-relief-team.md`. Design: `../specs/2026-11-20-relief-module-design.md`.

## What stage 3 gives

- **Today** (relief team): a page for a date. Every lesson needing cover with its pick: the planner's choice, the AI's
  pick by the school's rules, or the app's own order. Approve, Approve all waiting, Change, Split / Join again, Keep (a
  request to change), Fill now. While picks are being made the page refreshes itself.
- **Reliefs I'm covering** (every teacher): the approved reliefs, with Acknowledge or Request to change. A request to
  change also gets a new pick at once.
- **Load** (relief team): relief and teaching periods per teacher, this week and this term, Department and Flexi
  Adjunct filters, a Download, and a name opens that teacher's reliefs.
- **What's in** now shows "Needs a nudge" and each absence's relief status.
- **Picks**: the app's own order (same department and subject first, Flexi Adjunct Teachers by subject under their
  limit, lightest week first), or the AI's pick with the names turned into labels (see DEPLOY.md). A background timer
  (`RELIEF_JOBS=on`) makes picks when due: at once for today, at the fill time on the school day before.
- Nothing reaches a relief teacher before the relief team approves it. No Telegram (stage 4); the published timetable
  on a date comes with stage 3b.

## Rulings made during the build (each also in the ledger; "if wrong" is the cost)

1. `cover.pick_of(record, c)` gives the effective pick, so a stage 2 planner choice counts as a pick. If wrong: one helper.
2. `pick.CALL` is a hook the route tests use to stand in for the model. If wrong: a test-only seam.
3. The background work does nothing unless `RELIEF_JOBS=on` (or an action forces it), so tests are not raced by
   threads. If wrong: a local run without the variable picks only on Fill now.
4. The planner's own unapproved choice shows to the planner and the relief team; the absent teacher sees a name only
   once approved. If wrong: one condition.
5. Stage 2 tests were updated to that rule and to the new stored pick field. If wrong: test edits only.
6. A lesson already approved cannot be split, with its own sentence ("This lesson's relief is approved already, so it
   cannot be split."). If wrong: one sentence.
7. Actions refuse lessons dated before today; the background run also skips a lesson whose end has passed today. If
   wrong: a team member can approve a relief for a lesson that ended this morning (harmless record).
8. A lesson can be split again inside an unapproved part (so three parts are possible). If wrong: one case.
9. Sentences "Chosen by {by} on {date}.", "You asked to change this relief already." and "Nobody has asked to change this
   relief." accepted. If wrong: copy.
10. A planner's derived pick is written into the record, with its history line, by the first change that touches it;
    join and acknowledge log a discarded pick as "dropped". If wrong: an untouched planner pick has no history line yet.
11. `drop` is refused when the relief teacher has changed since; a change request's new pick refuses the teacher who
    asked. If wrong: a quiet no-op instead of an error.
12. A split lesson's parts keep their index and a new part goes last, so every list of covers is sorted by period.
    If wrong: parts shown out of order.
13. Names in the rules are replaced with or without an honorific and any run of spaces; the same check guards the
    answer. The rules box gains a line asking for full names. If wrong: an over-scrubbed word in a rule.
14. `max_tokens` is 4000 as for typed requests; each fallback logs its kind only (never data). If wrong: nothing.
15. Flexi Adjunct Teachers outside the department rank by subject match, then lightest week. If wrong: an order change.
16. The run reloads records before each pick, catches errors per cover, and only picks open covers (or a change with no
    new pick). If wrong: a cover left open until the next minute.
17. A waiting new pick on a change request counts as a booking for load and "free then", and a stale one is dropped and
    picked again. If wrong: a teacher counted twice while a request is open.
18b. `soon()` logs and returns if a thread cannot start, so a route never answers 500 after a save. If wrong: a missed
    background run.
21. Relief-stage-2 41c5035 (with the accounts) was merged into this branch before Task 4, so routes use the accounts'
    rights and history (every route through `need("relief")`, narrower rights inside), and `pick.py` reads people from
    the accounts' listing so an accounts-only person in a rule is scrubbed (one test pins it). If wrong: nothing; the
    merge was needed anyway.
22. The server sends `parts` sorted by period with each part's `ckey`, in all three views. If wrong: pages show parts
    out of order.
23. An absent teacher who also holds relief.plan or relief.team sees picks and history on her own absence. If wrong: one condition.
24. Browser checks ran on a temporary launch entry (port 8016, RELIEF_JOBS=on, practice model, made-up codes, scratch
    data), removed afterwards. If wrong: nothing kept.
25. The browser checks of Tasks 5 and 6 (21 real-click checks) stand for Task 7's list. If wrong: a page change after
    them is untried.
26. (Final review) Approve, Approve the new pick and Approve all send the person the page showed; the server refuses, or
    skips in Approve all, with "The pick has changed since you looked: look again before approving." when the pick is no
    longer that person, so nobody is approved whom the team did not see. If wrong: one more press after a re-read.
27. (Final review) Approve all records exactly the covers it approved, one History line each; skipped rows carry the
    absence. If wrong: nothing.
28. (Final review) The planned-relief sheet names a relief teacher only once approved; otherwise "Waiting for the relief
    team" or "Not chosen yet". If wrong: a column's wording.
29. (Final review) Keep and Change log the pick they drop; a planner choosing on an approved or split lesson is told
    "This lesson's relief is approved already: ask the relief team to change it." or "This lesson is split: the relief
    team chooses for each part."; a request to change re-picks only that absence (its other open lessons may be picked
    early, still waiting for approval). If wrong: copy.

## Checked

- The final whole-branch review (most capable model): one Critical (Approve could approve a pick the team never saw)
  and two Important (Approve all's History lines; unapproved picks on the planned-relief sheet), all fixed in one wave
  with seven new tests, each failing on the old code; a browser check with real clicks: Approve on a stale row is refused
  with its sentence and the page shows the new pick; Approve all skips it and approves the rest with one History line.

- Every suite on the final code (53183fd plus these docs), all passing: `test_accounts` 13, `test_admin` 18,
  `test_ask` 49, `test_board` 58, `test_choices` 16, `test_combined` 38, `test_exams` 76, `test_fixes` 65,
  `test_helper` 20, `test_history` 27, `test_history_draft` 9, `test_parents` 35, `test_relief` 42,
  `test_relief_requests` 59, `test_relief_team` 61, `test_routes` 18, `test_rules` 11, `test_signin` 24,
  `test_sync` 32, `test_teachers` 9, `test_typed` 33, `test_venues` 4, `test_verify` 56, `smoke` 102.
- The slow runs, one at a time with nothing else running: `test_typed --full` 34, `test_helper --full` 21,
  `test_fixes --full` 67, `smoke --full` 103, all passing.
- Every `tests/*.test.js` passes (ask 12, board 67, choices 13, classview 18, draft 25, grid 14, groups 33, map 26,
  parents 46, people 31, split 189, subjectview 15, sync 17, teacherview 8, venueview 24). `node --check` is clean on
  `static/app.js` and every `static/*.js` changed on this branch.
- Browser, with real clicks, on the made-up secondary sample with the practice AI and the background timer on: Task 5
  (Today) 9 of 9; Task 6 (Reliefs I'm covering, Load, What's in) 12 of 12. A constant used before it was set in
  `relief.js` blanked the page during Task 6's check; fixed and re-checked.
- The school's real published timetable, numbers only (scratch deleted, no model): 111 teachers, 93 with lessons on a
  made-up Tuesday; 5 made-up whole-day absences for those with the most lessons gave 4 saved (the fifth had no lessons
  to cover: all shared with a co-teacher who was there) and 13 lessons to cover. The run picked all 13 (the app's own
  order) in 1.25 s (slowest pick 0.085 s, mean 0.060 s); Today's 13 rows took 0.45 s; Approve all 13 took 0.45 s
  (holding the lock); an idle timer tick 0.00 s; the week so far for every teacher 0.06 s.
- No real staff name (111 checked) and not the school's full name in the branch.

## Not tried in a browser

- A refusal shown beside a row: nothing was refused during the check; the page shows the server's sentence by the same
  path as the success lines.
- The Flexi Adjunct filter's positive case on Load: the sample has no Flexi role, so it was checked with a page-only
  fetch stub marking one teacher; the real case is tested on the server only.
- The Department select on Load was set with a form input, not a pointer click; the Download was clicked with the
  link stubbed.
- A real model: every browser check used the practice AI. The "Being picked..." state lasts only a moment with it and
  longer with a real model.
- Today was a Sunday during the checks, so Mon 23 Nov stood in; the check used 127.0.0.1 because a localhost cookie
  was dropped once by another local app.

## For the accounts work

Relief stage 3 adds no new right names: it uses `relief`, `relief.plan` and `relief.team` as stage 2 does (Today, Load
and every pick action are the relief team's `relief.team`).

## Meeting exams stage 3 (PR #85)

Exams stage 3 touches the same places (the create and cancel routes, `absences.choose`, `_out`, What's in, and the
takeover in `absences.new`):
- The takeover in `absences.new` must carry the cover fields (relief, relief_by, work, and now the pick and cover
  state), or a taken-over absence loses its picks.
- `pick.shortlist` must pass `links` to `free_then`, so a lesson stopped by an exam is not offered as a free period.
- Merge around `_out` (it now sends `parts` sorted with `ckey`, and the exams side adds `stopped`).

## For stage 3b and stage 4, and minor items left

Stage 3b (the timetable on a date) and stage 4 (Telegram):
- Approving a change request's new pick writes no "dropped" line for the teacher who asked (one line in `cover._approve`).
- A request to change re-picks that absence's other open lessons too, before they are due (each a model call when the AI
  is set up; they only wait for approval); passing the cover's date to `fill.soon` would keep it to that day.
- Today shows no "the lesson has changed since this was planned" flag, and a run still picks for a lesson gone after a
  republish (final review M4).
- The past lessons of a cancelled absence keep their relief but stop counting in load, the AI's numbers and the covering
  list (final review M3).
- Picks for a term's first school day fall due on the previous term's last school day (the design as written).
- Nothing is told to anyone on Telegram; approval is the only gate to a relief teacher.
- A pending Fill now for a date not yet due is lost on a restart.

Cost and speed (watch these on the real timetable):
- Each minute the timer does one "free then" per waiting cover; Today does one per cover and polls every 3 seconds
  while picks are being made; Approve all holds the lock for one "free then" per waiting cover. On the real timetable
  13 lessons took 0.45 s; a larger day will take longer.
- The AI guard (60 picks per 10 minutes) may be reached by a heavy 15:00 run; past it, the app's own order.

Small things in the code:
- A stored pick whose `who` differs from the relief could be overwritten (not reachable through the mutators).
- Splitting a waiting part logs "split" without a "dropped" line.
- A pick is saved even if the lesson's end passed during a long model call; a lesson gone from the timetable still gets
  a pick; one malformed record or term can stop a whole run.
- `_check_pick` does not check `at`; join sorts history by `at` as a string; some private names are shared between
  modules (`_cover._log`, `_free._iso`).
- The rules scrub does not catch a bare surname alone ("Tan"), and "May" at a sentence start is replaced; short names
  match with exact case only. Tests do not clear `AI_API_KEY` or `AI_PROVIDER` (a shell with them set turns the
  suite red), and one test uses a literal fake key.
- Fill now accepts a past date (does nothing) while Approve all refuses it.
- Today: `nobody` means nobody at all is free, while a cover left open because everyone free is over a limit shows
  plain "open" (the page words it "Only teachers over a limit are free then"); cancelled absences are listed outside
  the counts; the change count includes since-cancelled ones.
- Pages: the date is read once at load (stale past midnight); a visibility change may start a duplicate fetch
  (harmless); Split is not offered on a change request; Refresh with a name open flashes "Loading..."; "This term"
  shows the same columns as This week, with the week clamped into the term; the Planned by me chooser is hidden on any
  split lesson (the planner cannot choose per part there); a changed relief shows as approved on a teacher's Load
  list with no marker; the planner's and team's picks show a reason but no tag.
- TEAM_ONLY's wording ("Only the relief team can open What's in.") also refuses approve, change, fill and load; the
  pages hide those buttons.

## Open questions for the lead

1. History lines name the absent teacher and the dates (never the reason). Is that all right for everyone who can open
   the History?
2. An absent HOD or SH (who holds `relief.plan`) sees picks on her own absence. Should she, or only the relief team?
3. Picks for a term's first day fall due weeks early (on the last school day of the term before). Wanted, or should
   they wait until a few days before?
4. The Load list also lists waiting picks and new picks (marked), not only reliefs taken. Keep, or show only reliefs
   taken?
5. Cancelled absences stay on Today, outside the counts. Keep them visible, or hide them?

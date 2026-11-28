# Relief piece 2 (changing a request): notes

Plan: `2026-11-27-relief-change-piece-2.md`. Design: `../specs/2026-11-27-relief-tabs-and-relook-design.md`, "Piece 2"
(approved by the committee lead on 27 November 2026; pieces 3 and 4 are not built), mockup part 6 beside it. Branch
`relief-change`, from main 3935ccb. Built subagent-driven on 28 November 2026: seven tasks, each reviewed; then a whole-branch review on the most capable model, a
browser check, one fix wave (fifteen points) and its re-review.

## What it gives

- **Change dates or times** of a request: the absent teacher on My absences, the head who planned it on Planned by me (the
  card's **Change dates or times**), and the relief team on All Relief Requests (a new **Edit** on each request with a date
  today or later that is not cancelled and not a backup). The controls are Ask for relief's: Today / Tomorrow / Pick dates
  (the two-month calendar), Whole day / Some periods. "What this change does" lists each lesson, read again on every change:
  **Kept** (it keeps its relief teacher, pick, approval, acknowledgement and work), **Added** (a relief teacher is picked, as
  for a new request) and **No longer needed** (its relief ends; a relief teacher already told is told so; its work files go
  when no lesson left lists them). Lessons of earlier days ("{n} earlier lessons stay as they were.") and lessons of today
  that have started always stay. A reason for the change is optional (up to 200 characters). **Save the change** is off
  while the list is being read, nothing changes, or the choice is refused.
- The checks are a new request's: up to 20 school days, today or later; school days only; the periods; no overlap with the
  teacher's other absences; a shared lesson with a co-teacher who is there is not needed unless **Ask for relief anyway** is
ticked on its Added line; something left to cover (a request whose new lessons are all shared says to tick it). Two
  people on one request: a save from an older list is refused ("The request has changed since you looked: look again before
  saving."), nothing written.
- The record keeps each change (`changes`: when, by whom, the reason, the dates and periods before and after, the lessons
  added and gone and which of them needed relief, whether it asked to acknowledge again, and the dates and periods the person
  chose, so the editor opens on that choice) and `changed_at`. All Relief Requests says "Changed by {by}, {when}"
  under the stamp, and the row shows as new.
- A lesson the change adds that one of the teacher's exam or event backups holds moves in with its whole cover (the preview
  says so); the backup shrinks or is cancelled, as with a new request.
- **Relief not needed** on one lesson takes an optional reason everywhere (My absences, Planned by me, the Edit view's "Or
  change one lesson" with **Needed again** or **Ask for relief anyway**, and a new button on each row of Today's Relief Assignments). On a row that is
  part of a split lesson it reads "Relief not needed for the whole lesson" and ends every part. A lesson that is over cannot be marked ("This lesson is over.") and shows no button.
- **Cancel the whole request** is on the Edit view too ("Or cancel the whole request"), with a reason needed, as before.
- **Telegram:** the absent teacher is told when somebody else changes the request, marks a lesson not needed or cancels it
  (what changed and by whom, never the typed reason); when a change adds a needed lesson to a planned request the teacher
  had acknowledged, they are asked to acknowledge again and set work. The relief team is told when anyone changes a request's lessons of today
  that need relief (each of the team but the person who changed it and the absent teacher; "Changed by …" when it was not the
  absent teacher). The page says "{teacher} is told on Telegram, if they have linked it."; the counts in every message are of
  lessons that need relief. A reporting officer told of the absence is told the new dates and
  times, with the kind of reason alone. Relief teachers already told get "No longer needed" or "Cancelled", as before.
- A backup for an exam duty or an event cannot be changed: the pages show no change controls on it, and the server refuses
  ("This relief follows the exam or event schedule: change the duty instead."). Its lessons can still be marked not needed.

## Rulings made while building (the lead may change any)

1. A change's record entry carries `again` (it cleared the acknowledgement) so the message knows without guessing; it is
   true only when the planned request had been acknowledged and somebody other than the teacher added a needed lesson.
2. An earlier date of the request (before today) always stays in its dates, with or without a lesson left on it: dates are
   history, as lessons are. Choosing the same dates again is then "Nothing changes".
3. "Something to cover" counts the lessons kept (started ones too), not only the new choice, so a change of today after a
   lesson started is not refused.
4. The save is refused without the preview's list (`shown`); the page always sends it.
5. An added lesson that a backup holds gets its own preview line: it moves in with its relief teacher.
6. The relief team's Telegram message about a change of today counts only today's added and gone lessons that need relief,
   and is not sent when there are none.
9. (Whole-branch review, I3) The team hears of a change of today's lessons by anyone, a head too, not only by the teacher,
   as a late request by a head is told: the design named the teacher's own case.
10. (Fix wave) Out of the wave, written here instead: a dropped lesson an exam or event cover takes back is announced only
    as "No longer needed" (the same teacher may be asked again minutes later); the planner is not told when the team or the
    teacher changes their planned relief (the lead's call); a teacher whose own request was cancelled by someone else before
    this piece may get the cancel message once after the deploy; the record's dates and periods after a change describe
    earlier days by the new periods; a lesson whose timetable changed shows as No longer needed plus Added on opening.
11. All Relief Requests' view buttons ask first (a confirm box) when an open Edit holds unsaved choices; the Edit view stays
    open after a one-lesson step.
7. Commit lines name Claude Opus 5.5 (the session's attribution), not the plan's Fable 5.2.
8. Calls from the plan itself (Task 7 Step 5): **Close** beside Save in place of the picture's **Cancel**, so it is not read
   as cancelling the request; the change list lives in the Edit view (and under the card on My absences and Planned by me),
   not in a pop-up.

## Differences from the picture (mockup part 6)

- **Close** in place of **Cancel** beside **Save the change** (above).
- The change list is part of the Edit view, read again on each change, not a pop-up shown on Save.
- On All Relief Requests, Edit opens under the table (outside its sideways scroller, so it fits a phone), one at a time,
  headed "Edit: {teacher}'s request"; "Edit" again closes it.

## Known limits

- A change made after the cut-off for today pings nobody on the team, as a late request does.
- A record's periods are the new ones even when a started lesson kept from before lies outside them.
- Only the last change of a record is told on Telegram: two changes before the sender runs give one message, of the last.
- A lesson that has started (not yet over) can still be marked not needed (as before this piece).
- A lesson dropped by a change and later added back keeps its old entry in the record's `gone` list (history).

## Deferred minor points (from the reviews)

- A reason that is not a string is read as "" (as before); a cover's history may hold an empty reason for a relief dropped
  without one (nothing shows it).
- No test drops a split lesson or a lesson with an open request to change (the code reads right).
- The plan `change` returns holds the cleared covers of gone lessons; a gone lesson's stamp is a second clock reading.
- The route's after-save step repeats the cancel route's (sync, then the sender soon).
- An officer who is also on the relief team gets both the officer's message and the team's for one same-day change.
- Several Relief not needed marks are one message each to the absent teacher, at any hour.
- The needed counts in a message include lessons an exam stops or that are already over.
- A one-lesson step that finishes after its Edit was closed is said nowhere; Shift+Tab from the Edit goes to the table's last row.
- A queued "changed request for today" message is not dropped by a later change (after an outage its "Now:" line may be
  out of date).
- The calendar's ticks made while a save is under way are dropped; focus goes to the page after a refused save; opening
  another card's editor drops the first one's typed reason; the card tests run on My absences only.
- The caret may move once on a late redraw; Today's "relief not needed" lines pile up above the rows until a bulk action (as
  gone rows' lines do).

## Checks

- After the fix wave, on bfe7274: every quick suite, one at a time, 66 of 66 pass (test_relief_telegram once failed on a
  chance match of "98765" in a random id in the history files, as seen in piece 1, and passed twice when run again);
  test_relief_change 27, relief_change 38, relief_inbox 19, relief_today 72, test_relief_telegram 458, test_relief_team 91.
- The real timetable again on the final code (numbers only, same method): 94 teachers; the made-up 20-day request of the
  busiest teacher, 74 lessons; to 10 days: 37 kept, 37 gone, 0.004 s; to Some periods P1 to P13: 52 kept, 22 gone, 0.005 s;
  saved in 0.005 s; adding one day back: 5 shared lessons added, all 5 needing relief once Ask for relief anyway is ticked.

Before the fix wave, on 3c2fd3d:

- Every quick suite, one at a time, on 3c2fd3d (the code of b553a09 plus the guide): 66 of 66 pass (36 Python, 30 page
  suites), each judged by its exit status and its last line. Relief's own: test_relief_change 21 (new), test_relief 45,
  test_relief_requests 70, test_relief_team 91, test_relief_telegram 455, test_exams_relief 103, test_routes 20;
  relief_change 30 (new), relief_inbox 16, relief_today 71, relief_ahead 24, relief_dates 63, relief_settings 25,
  relief_summary 11, relief_telegram 39.
- The slow runs (`--full`), alone, one at a time: test_typed 34, test_helper 21, test_fixes 76, smoke 104: all four pass
  (so no comparison with main was needed this time).
- The school's real timetable, numbers only (the newest real timetable data published into a scratch folder with
  `store.publish(None, …)`, deleted afterwards; a made-up calendar; no model, no network; no name printed): 94 teachers with
  lessons, 10 day names, 26 periods a day. The teacher with the most lessons (37 lessons in the two weeks) was given a
  made-up whole-day request over 20 school days, every lesson asked as needed: 74 lessons. `plan_change` to 10 of the days:
  37 kept, 0 added, 37 gone, 0 earlier, in 0.002 s. To Some periods (P1 to P13) over the 20 days: 42 kept, 0 added, 32 gone,
  in 0.003 s. `change` saving the 10 days: 0.003 s (37 lessons left, one change written). Back to 20 days after that: 37
  kept, 37 added, 0 gone, in 0.003 s; all 37 added came in as not needed, since every lesson of this teacher is shared with
  a co-teacher who is there (see Known limits).

## Browser check

A scratch server under its own hostname with made-up data (the test files' names), signed in by made-up usernames and
passwords, real clicks and typing (the From and To lists were set by form_input: the pane cannot open a native list):
- Before the fix wave, 6 of 7 checks passed: a head's change on Planned by me (Pick dates, Some periods, the list, Save,
  Close); the absent teacher's on My absences, with no relief teacher's name before acknowledgement; the team's Edit
  (change, Relief not needed with and without a reason, Needed again, cancel only once a reason is typed, "Changed by");
  Today's Relief not needed on a whole row and on a split part, the line above the rows, the focus kept on a button; two
  people saving one request ("changed since you looked", then the request as it is now); no script errors. The fault: on a
  phone (375 px) the Edit view sat inside the table's sideways scroller and was cut off. It also showed that the team could
  not ask for cover on a shared lesson.
- After the fix wave, again with real clicks: at 375 px the Edit view is outside the table and nothing goes past the edge;
  Ask for relief anyway on a shared lesson in the Edit view made it a lesson to cover and a relief teacher was picked; the
  Edit stayed open after the step; a request changed earlier opens on "Nothing changes yet."; no console errors.
- Not tried: a real phone; a screen reader; a real Telegram bot (never called); Print.

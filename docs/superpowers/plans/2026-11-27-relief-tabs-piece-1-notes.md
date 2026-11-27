# Relief piece 1 (the words and the new tab): notes

Plan: `2026-11-27-relief-tabs-piece-1.md`. Design: `../specs/2026-11-27-relief-tabs-and-relook-design.md` (approved by the
committee lead on 27 November 2026; pieces 2 to 4 are not built). Branch `relief-tabs`, from main ea073c8. Built
subagent-driven on 27 November 2026: five tasks, each reviewed, then a whole-branch review.

## What it gives

- The tabs read **Relief Planning**, **All Relief Requests**, **Today's Relief Assignments**, **Term Relief Report**; their
  addresses (`#plan`, `#inbox`, `#today`, `#load`) are unchanged, so links already sent still open the right tab. The Telegram
  button to the day reads "Open Today's Relief Assignments".
- **Not acknowledged** (was "Needs a nudge") on All Relief Requests: a request a head planned that its teacher has not
  acknowledged (as before), or one with a relief of today that has reached its relief teacher and is neither acknowledged nor
  asked to change. The row says "Relief not acknowledged: {name}, {periods}", with "· started" once the lesson has begun.
- **Planned Relief Assignments** (`#ahead`, relief team only, read-only): every relief on the school days after today, by date,
  for the next two weeks or the rest of the term; "Open this day" shows that date on Today's Relief Assignments.

## Rulings made while building (the lead may change any)

1. The refusal for the relief team's routes reads "Only the relief team can open this." (it named "What's in" for every team
   route, Today's too). Costs one more wording change if the lead wants tab names in refusals.
2. The line on a row reads "Relief not acknowledged: {name}, {periods}" (the plan had "Not acknowledged: …", which could be
   read as the absent teacher). The absent teacher's own case keeps the amber chip "not acknowledged yet".
3. The link above Today's rows reads "show today" (was "open Today", which read as a tab name).
4. The form heading "Plan relief for a colleague" stays: it names the form, not the tab.
5. On the new tab a day's "{n} lessons" counts lessons to cover (not ones that are not happening), and "Open this day" sits
   in each day's heading, once a day, not on every row.
6. Switching between "Next 2 weeks" and "This term" clears the list while the other is read (it would sit under the wrong
   name); Refresh keeps the list on screen.
7. A record, lesson or cover changed by hand that cannot be read is passed over on the new tab and in Not acknowledged, with
   one log line a request that holds only the kind of error.

## Known limits

- The new tab does not work out again who is free. "… is no longer free then", "over a limit" and "nobody is free" show only on
  Today's Relief Assignments, after Open this day. (Seen in the browser check: a relief teacher chosen by a head, then away
  themselves that day, shows as an ordinary approved row on the new tab and with its warning on Today's.) Piece 3 or 4 may
  want the warning here; it costs one who-is-free per row.
- After Open this day, Today's Relief Assignments stays on that date until another is chosen, as with its own day buttons.
- "Not acknowledged" lists a relief teacher from the moment the relief reaches them (the lead: "As soon as told"); before the
  lesson's own morning nothing of a later day counts.
- The Telegram label changed for new messages only; messages already sent keep "Open relief today" and still open the tab.
- `tests/test_relief_telegram.py` has an assertion that can fail by chance on main too (near "whether, and no more": a short
  made-up chat number looked for in a day's JSON, where a random id or a time can hold it). It failed once in five runs here
  and passed on the rerun. Not this branch's; worth its own small fix.

- Mockup part 2, which the lead approved "as drawn", shows a "Flexi Adjunct" mark beside a relief teacher's name and a "5 h in
  a row" flag. Neither is on the tab yet: both belong with piece 3, where the long-run mark goes into the same cell.

## For the lead to confirm (differences from the picture or the words)

- "Open this day" is one button in each day's heading, not one on every row.
- The row says "Relief not acknowledged: {name}, {periods}" rather than a column "Not acknowledged by".
- "show today" in place of "open Today"; "Only the relief team can open this." as the refusal.
- The new tab says how far it reaches ("up to {day}"), counts "asked to change" in a day's heading, and names the exam duty
  of a teacher who is in school on a duty (as Today does).

## Checks

- Every quick suite, one at a time, on the final code (1d73c3c): 64 of 64 pass. Relief's own: test_relief 45, test_relief_requests 69,
  test_relief_team 91, test_relief_telegram 448, test_exams_relief 103, test_routes 20; relief_ahead 24, relief_inbox 7,
  relief_today 62, relief_dates 63, relief_settings 25, relief_summary 11, relief_telegram 39.
- The slow runs (`--full`): `test_fixes` and `smoke` pass. `test_helper --full` and `test_typed --full` solve a sample afresh
  under a time limit and fail on main too: run one at a time on this computer, `test_helper --full` failed 4 of 4 on main
  (ea073c8) and 4 of 5 on the branch, each time on a different "Swap …" suggestion its own full check disagrees with;
  `test_typed --full` failed on main and passed on the branch. The branch changes no file either suite runs (only `relief/`,
  `static/relief*`, relief's tests, `README.md`, `docs/DEPLOY.md`). They are main's own trouble, offered before as a piece of work.
- The school's real timetable, numbers only (the newest real timetable published into a scratch folder, deleted afterwards; no
  model, no network; made-up dates and absences): 98 teachers, 10 day names, 26 periods a day; 169 made-up whole-day absences
  over 40 school days (25 more refused: no lessons to cover), 357 lessons to cover. The new tab's list: two weeks 71 rows in
  0.01 s, the term 357 rows in 0.01 s, and its rows equal the lessons to cover after today. The first day's 12 rows have the
  same state, pick and send-out as Today's 12 rows (Today itself 0.79 s, as before). All Relief Requests, 169 absences with
  the new "not acknowledged" reading: 0.07 s.
- The whole-branch review (the most capable model): no Critical; one Important (a lesson an exam stops showed the bare word
  "stopped" instead of the reason) and eleven minors; one fix wave took all but the Flexi Adjunct mark above, and was
  re-reviewed.
- Browser, real mouse, a scratch server under its own hostname with the made-up Sample Secondary School: the nine tab names;
  each old address opens its tab; the new tab's days, counts and chips; a split lesson as two rows; a head's choice "Approved ·
  will be sent …" with "Planned by …"; Open this day before Today's tab was ever opened; This term; Refresh keeping the list and
  the focus; one column layout for every day; at phone width the table scrolls inside its box and the page does not; Not
  acknowledged with two relief teachers of today. No console errors.
- After the fix wave, again with a real mouse: the list says how far it reaches ("up to Fri 11 Dec"); Open this day reads
  the day once and puts the keyboard focus on the Today's Relief Assignments tab.
- Not tried: a real phone; a screen reader; Print on the new tab; the Telegram button on a real bot (never called here); a
  lesson an exam stops and a teacher on an exam duty were checked by tests only, not in the browser.
- Left open, small: the "Open this day" button's spoken label names the date but not the words on the button (a voice-control
  user saying "Open this day" may miss it); one line when the file is next open.

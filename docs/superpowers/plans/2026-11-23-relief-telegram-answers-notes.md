# Relief on Telegram, the lead's answers: notes

Built 23 November 2026 on branch `relief-telegram-answers` (from main ebdccb9, where relief stage 4 is merged as PR #96), in the
worktree `tt-relief-stage-4`, subagent-driven: a builder and a reviewer per task, fix rounds where the review asked. Not pushed, not
merged, not deployed.
Plan: `2026-11-23-relief-telegram-answers.md`. Stage 4's notes, where the questions were asked: `2026-11-22-relief-stage-4-notes.md`.
How to set it up and what leaves the server: `../../DEPLOY.md`, section 6 and "What leaves the server".

**Built without the lead reading the plan first.** The lead answered the thirteen questions and wrote "continue all", so the plan
was written and built straight away (ruling PF4, below). Every decision listed in these notes was taken on the lead's behalf, and the
lead may change any of them. Each one says what it costs if it is wrong.

## The lead's thirteen answers

As the lead wrote them, on 23 November 2026, to stage 4's eleven open questions and its two follow-ups. Then: "continue all".

| # | The question (short) | The answer | What came of it |
|---|---|---|---|
| 1 | Ping the relief team when relief is asked for today? | yes | Built: A (since replaced by the morning message and the late request) |
| 2 | The one-time code in place of the personal code? | keep | Kept |
| 3 | Work files through Telegram with the relief? | Keep | Kept; reversed by the lead on 23 Nov (item 10): files by link, built in the send-out, stage 1 |
| 4 | The kind of reason in the reporting officer's message? | Keep | Kept |
| 5 | Should the app's form say when the reporting officer is not on Telegram? | yes | Built: B |
| 6 | `/relief`: a text and then a file went to two lessons; a Next button? | fixed for both | Built: C |
| 7 | Cancelling on Telegram: a typed line and a second press? | keep | Kept |
| 8 | The report begins an hour before the first period? | keep | Kept |
| 9 | Tell the team why the all clear is held back while an old file cannot be read? | ok | Not built (the suggestion was "not now") |
| 10 | Tell a person in the app that their Telegram was unlinked because the bot was blocked? | yes | Built: D |
| 11 | The copy: anything to change? | Ok | No wording changed |
| 12 | Follow-up: show the messages other than reliefs that could not be sent? | yes | Built: E |
| 13 | Follow-up: Today's 12 px more under its buttons without a token? | fix next time | Built in the send-out, stage 1, Task 5 (d07ceec): the room is kept only while a bot is connected |

Some of these are readings, in case they are not what was meant:
- **Answer 6, "fixed for both"**, was read as: build the Next button, so that a text and a file both land on the same lesson. If
  something else was meant, say so: C can be changed or taken out.
- **Answer 9, "ok"**, was read as agreeing with the suggestion "not now", so nothing was built. **Answer 11, "Ok"**, was read as: no
  wording change asked.
- **Answers 12 and 13** were matched to stage 4's two follow-ups by their order alone: 12 to the list of messages that could not be
  sent, 13 to Today's 12 px. If they were meant the other way round, say so.

## What each change gives

- **A. The relief team is pinged for relief asked for today** (f5612d6). When an absence for today is sent today (from the app's
  form, Plan relief or `/relief`), each member of the relief team who is on Telegram gets one message once its picks wait for their
  approval: whose absence, whole day or which periods, and how many lessons wait, with a button that opens Today. It waits until no
  lesson of it is still without a pick, or five minutes after the absence was sent, so it never comes before the picks. It never
  comes before the day's first report, an hour before the first period (07:00 when lessons start at 08:00): one asked in the night
  is sent then (f4df792, after the final review). Never for an exam's or event's backup, never twice for one absence, never to who
  sent it or to the absent teacher. **Replaced by the morning message and the late request: see `2026-11-24-relief-send-out-stage-1-notes.md`.**
- **B. The form says when the reporting officer is not on Telegram** (b55c496). After "Sent. The relief team can see it." the form
  adds "{officer} is not on Telegram: please tell them yourself.", the same sentence `/relief` already said, under the same rule:
  an officer is named, is neither the absent teacher nor who sent it, and the bot is connected.
- **C. `/relief` keeps a lesson's work until Next** (1431c1c, 8970db3, 09839c9). A lesson takes as many messages as the person likes:
  each line is added to its text on a new line, each file or photo is added, and a link is its one link. After each message the
  lesson's question is asked again at the bottom of the chat, saying what is set, with **Next** (and **Later for all the rest** when two
  lessons or more are left). Before anything is set, the buttons are as before (Same as before, Later, Later for all the rest). The
  two fix rounds made it hold when messages come quickly:
  - Two messages sent together for one lesson (a text and a file at the same moment) are both taken, on that lesson.
  - Lines that arrive together are kept once each, in the order the app handles them, which may differ from the order they were sent.
  - A message that crosses a press of Next lands on the lesson that is current when the app handles it.
  - A message that crosses Next on the last lesson, or Later for all the rest, into the list is answered "Please press one of the
    buttons." with the list again, and is on no lesson.
  - A press on an older copy of the question counts once and leaves one set of buttons in the chat.
  - Sending the same link again says nothing of replacing it.
- **D. Told in the app that the bot was blocked** (fb17a84). When the app unlinks somebody because they blocked the bot, their own
  Telegram card in My absences says so, with the day, until they link again in any way (a code, Start, a moved link).
- **E. Relief settings says which messages could not be sent** (4326563). The Telegram card in Relief settings lists the messages
  that could not be sent, or may not have been, since Monday: newest first, 20 at most, each by kind, name, time and state, never its
  text. Reliefs (Today has their line), reports and all clears are left out. Only the relief team sees the list (0ce58e2, after the
  final review): it names who was away, and the timetable committee, who may also open Relief settings, may not see absences.

No new route, no new right, no new table, no new dependency. Nothing new is sent from a page: A is worked out by the same sweep as
every other message (the sweep is the app's check, once a minute and after each save, of what there is to tell on Telegram).

## Decisions taken in the plan (the lead may change any)

1. A: relief planned by somebody else for today pings too, as a request does: the team must approve it just as soon. If wrong: one
   condition.
2. A: only an absence sent today pings. One sent yesterday evening for today does not: a message at 21:00 would wake people, and the
   team opens Today in the morning, where it waits. If wrong: a late request is seen only when someone opens Today. (One sent in the
   night of the same day waits for the report's start: ruling FA2, below.)
3. A: the ping waits until no lesson of today of that absence is still open, or five minutes after it was sent, then counts the
   lessons waiting for a pick's approval and those still open (nobody free, or the pick did not come). If wrong: such an absence is
   pinged up to five minutes late.
4. A: never to who sent the absence, nor to the absent teacher, when either is on the team. If wrong: one name in a set.
5. A: the number in the text is the one when it was made; the message is dropped if nothing of today waits when it goes, but not
   rewritten. If wrong: it may say "2 lessons" when one is left.
6. A: claimed once, even when dropped: if the team approves everything before the ping goes, no ping comes later for that absence,
   even if a pick goes back to open. If wrong: a pick that goes back to open after everything was approved is never pinged again.
7. B: the form says only the "not on Telegram" sentence, after "Sent. The relief team can see it." on the same line; it does not say
   "{officer} will be told." If wrong: copy.
8. B: the same rule as the officer's message: an officer is named, is neither the absent teacher nor who sent it, and the bot is
   connected. If wrong: one condition.
9. C: a second text for a lesson is added to the first, on a new line, not put in its place. People type in pieces on a phone; a slip
   is mended in the app, or with Start again. If wrong: a corrected line shows both.
10. C: a second link replaces the first (a lesson has one link, as in the app), and the bot says so. If wrong: copy.
11. C: before anything is set, the buttons are as before (Later does what Next would). Once something is set: Next, and Later for all
    the rest when two lessons or more are left; Same as before and Later are gone, so nothing set is thrown away by a press. If
    wrong: a button.
12. C: after each message the lesson's question is asked again at the bottom of the chat (a new message; the one before loses its
    buttons), saying what is set; the later files of an album change it in place. If wrong: one message more a piece.
13. D: the note is a row in the existing store (the app's own Telegram file on the server, `relief/telegram.db`), written only while
    that person has no link, and taken away only when they link again. If wrong: the line stays for someone who never links again.
14. D: no history entry for the unlinking. The app's history needs a signed-in person, and the sender has none, so an entry "by The
    app" cannot be written as things are. One condition would allow it (an open question, below). If wrong: one condition and one
    entry.
15. E: reports and all clears are left out (each is true for 30 minutes only; a late one is never sent), and so is the relief itself
    (Today shows it). The weekly summary is shown. A kind this plan does not name (exams' own, later) shows as "Message". If wrong:
    one list.
16. E: newest first, 20 at most, then "and {n} more"; "since Monday" by when it was tried (may not have been sent) or queued (could
    not be sent). If wrong: one number, one column.

## Rulings made during the build ("if wrong" is the cost)

Before the build:
- PF1. The button "Open relief today" is written once, for the ping and the report alike, so the two cannot drift apart. If wrong:
  one line in `relief/report.py`, outside the plan's file list.
- PF2. `/relief`'s "{officer} will be told." stays where it was; only the "not on Telegram" sentence moved, so the form and `/relief`
  share it. If wrong: nothing.
- PF3. "Claimed once, even when dropped" needed the sweep (the app's check, every minute, of what there is to tell) to see dropped pings. It already does, so no extra read was added. If
  wrong: one read a sweep.
- PF4. The plan was built without waiting for the lead to read it, on "continue all"; its 16 decisions are above, for the lead to
  change. If wrong: rework of a decision the lead would have changed.

During the build:
- 5a. The first review of C found that a second message sent quickly, while the new question was on its way, was dropped without a
  word: the very case the lead named. Ruled: fixed in C, not left as a limit. At the work question such a message is taken into the
  lesson asked about, as it would be a moment later; the other questions of `/relief` keep stage 4's guard. If wrong: a change in how
  the conversation is locked, which a two-at-once test proves.
- 5b. A message that arrives while the list is on its way (Next or Later for all the rest was pressed first, so the lesson is closed)
  is answered "Please press one of the buttons." and the list, as a moment later: said, not taken. Silence was the fault. A press on
  an older copy of the question, counted because its buttons are kept, also takes the buttons off the newer copy. If wrong: the
  person adds that piece with Start again or in the app.

The builders' own choices, accepted by the reviews:
- A: the number in the ping counts the lessons with a pick waiting and those with none, since both wait for the team. If wrong: an
  open lesson is counted as "waiting for your approval"; it does wait for the team, to choose.
- A: while nothing is published, the check just before sending reads no lesson times. If wrong: a ping could go while nothing is
  published; it is still true then.
- D: the note is written only when the sender itself unlinked that person, so somebody unlinked by hand meanwhile, or moved to
  another phone, gets no line. If wrong: a blocked person who was already unlinked sees no line.
- E: "since Monday" is from Monday's date at 00:00 school time; equal times are listed by name. If wrong: nothing a person sees.
- C: a second link that is refused says only the refusal; "One link a lesson" is said only when it is taken. A reply to another
  message, sent while the work question is on its way, is asked again, not taken (it cannot be compared yet). If Next is handled
  before a crossing line, the line lands on the next lesson; if the line is handled first, the same Next still counts: either way
  the conversation moves once. A stale copy of a question can stay in the chat without buttons; the current question is then asked
  once more below it. At the list on its way, a reply gets "Please press one of the buttons." too. If wrong: one message more, rare.
- C: `a_whole_conversation_sends_an_absence` now counts six answered presses where it counted four: the two Next taps. If wrong: the
  test's number.

Carried from the build's record, for whoever maintains the code:
- Task 2's Python tests were not run failing on their own before the code was written; its deliberate faults were caught after.
- Task 4's order by name for equal times is not checked by any test.
- Task 3 changed three of stage 4's tests, because the ping falls due in them: `the_module_stands_alone` (the new kind in its list),
  `a_reminder_is_the_relief_again_and_no_relief_of_its_own` and `stopped_is_said_again_once_something_said_that_it_is_on` (each
  now expects the team's ping too). The final fix wave changed the last one again: its absence is sent at 06:50, so the ping now
  comes at 07:00, not 06:55.

After the final review (no Critical, two Important, five Minor; the two Important fixed in this wave):
- FA1. The list of messages that could not be sent (E) is shown to the relief team alone. Relief settings also opens for the
  timetable committee's shared code and for an admin without relief, and the list names who was away ("Relief planned · {name}"),
  which they may not see. For them the card shows no list; connecting, disconnecting and unlinking answer the same way. If wrong:
  a committee member who is not on the relief team does not see that messages failed (they could not act on them either).
- FA2. The ping to the relief team (A) never goes before the day's first report, an hour before the first period. An absence sent
  in the night (00:03, say) is pinged at that time, if a lesson of it still waits for the team then; one sent after it is pinged as
  before. With no lesson times (nothing published) nothing changed. If wrong: a request sent at 06:00 is pinged at the report's
  start, up to an hour or so later; one sent in school hours is pinged as before.
- FA3. Three of the review's Minor points are kept as known limits, not changed in the code (M3, M4, M5 under Known limits, A and
  D). If wrong: as each limit says.

## Copy the lead should see

Every new sentence a person sees, exactly as the code has it. {..} stands for a name, a day, a lesson or a number.

**On Telegram**

To the relief team (A), with the button **Open relief today**:

> 🆕 Relief asked for today · {absent}
> {whole day, or the periods, as "P1–P3"}
> {n} lessons are waiting for your approval.

("1 lesson is waiting for your approval." for one.) Replaced since by the late request, "🆕 Late request for today · {absent}": see
`2026-11-24-relief-send-out-stage-1-notes.md`.

In `/relief` (C):
- Once something is set for a lesson: "Work for {lesson} {periods} on {day}{start}: {what is set}. Send more, or press Next."
  {start} is the lesson's start time in brackets with a space before it, " (10:40)", or nothing when the lesson has no times.
  "{what is set}" reads as in the list before Send, for example "work set (text, 1 file)" or "work set (text, link, 2 files)", never
  what the work says.
- The button **Next**. **Later for all the rest** is offered with it when two lessons or more are left.
- A second, different link for one lesson: "One link a lesson: this one is in place of the one before."
- Unchanged, but now also said to a message that crosses Next on the last lesson, or Later for all the rest: "Please press one of
  the buttons." with the list.
- Unchanged before anything is set: "Work for {lesson} {periods} on {day}{start}? Type it, send a file or a photo, or tap Later."
  with **Same as before** (when a lesson before has work), **Later, in the app** and **Later for all the rest** (when two lessons or
  more are left).

**In the app**

- The Ask for relief form, once sent (B): "Sent. The relief team can see it. {officer} is not on Telegram: please tell them
  yourself." (only the first sentence when the officer will be told, or none is named).
- My absences, the Telegram card, after the bot was blocked (D): "Your Telegram was unlinked on {day}: the bot was blocked there.
  Unblock it in Telegram, then link again." It is shown in place of "Get your reliefs and reminders on your own Telegram.", above
  **Link Telegram**, and goes once they press it, and for good once they are linked again.
- Relief settings, the Telegram card (E), one of:
  - "{n} messages could not be sent, {m} may not have been sent, since {Monday}." (for example "since Mon 12 Oct.")
  - "{n} messages could not be sent since {Monday}." ("1 message could not be sent since {Monday}.")
  - "{m} messages may not have been sent since {Monday}." ("1 message may not have been sent since {Monday}.")
  - then one line a message: "{kind} · {name} · {day} {hh:mm} · could not be sent" or "... · may not have been sent", and "and {n}
    more" past 20.
  - The kinds: "Relief planned", "Reminder to acknowledge", "To the reporting officer", "Request to change", "New pick for a request
    to change", "Relief kept", "Absence cancelled", "No longer needed", "Relief moved", "Not happening", "On again", "Weekly summary",
    "New request for today", and "Message" for any other. (Since the send-out, stage 1, "New request for today" is gone and seven
    kinds are added: see `2026-11-24-relief-send-out-stage-1-notes.md`.)
  - Nothing is shown when there is nothing to say.

## Known limits

A, the ping (as it was before the send-out, stage 1, which replaced it; none of these holds of the late request as such: see
`2026-11-24-relief-send-out-stage-1-notes.md`):
- An absence sent the evening before for today is not pinged (decision 2): the team sees it when they open Today.
- The earliest a ping goes is exactly one hour before the first period. The report itself starts at a round time (07:00, 07:15
  ...), so at a school whose first period does not begin on such a time the ping can come a few minutes before the first report.
  It never comes in the night.
- The number is the one when the ping was made, and is not rewritten. It counts lessons as the app holds them, so a lesson split in
  two parts reads "2 lessons".
- A ping that was dropped (everything approved before it went, or the person off the team by then) is never made again for that
  absence, even if a pick goes back to open.
- While nothing is published, a lesson already over today could still count when the ping goes (narrow).
- An absence sent in the night is pinged at the report's start, an hour before the first period, not when it was sent (ruling FA2).
- (M3) If every lesson of an absence was approved before any ping was made, and a relief is later taken off again the same day, the
  team gets "Relief asked for today" at that later moment.
- (M5) Each request for today is one message to each relief team member: ten absences in a few minutes are about fifty messages for
  a team of five. A burst to one chat may make Telegram ask for a pause of some seconds, which holds every message, reliefs too,
  until it ends.

B, the form: no test drives the whole form to its "Sent" line; the sentence itself is tested, and the browser check looks at the
form (Checks, below).

C, `/relief`:
- A message meant for the next lesson but sent before Next lands on the one asked about. The question that follows says which lesson
  and what is set, and Start again or the app is the way back.
- A file sent once the list is out is on no lesson: the answer is "Please press one of the buttons." and it is to be added in the app.
- One more tap for a lesson with work (Next).
- If a link is sent and then another one quickly, Telegram's late preview of the first can come once the second has replaced it; the
  bot then answers "Send text, a file or a photo." and asks the question again. A stray message, nothing lost.
- A reply sent while the work question is on its way is asked again without a sentence saying why.
- If three things cross at once, a copy of the question without buttons can end up below the current one, or two copies asked again
  can leave two sets of buttons. Rare.
- **Send** pressed on an older copy of the list sends the request and ends the conversation, but the newer copy keeps its buttons,
  which then answer "This button is no longer active."
- At the list on its way a reply is answered "Please press one of the buttons."; a moment later it is answered "Answer the question
  I asked last."
- With two copies of the app on one store, a line that loses the race to a step in the other copy is not taken (the bot works on one
  copy only).
- A tick on an older copy of the days question redraws the message that was pressed (older than this change).

D, the blocked line:
- The unlinking still writes no history entry (decision 14; an open question). Since the send-out, stage 1, it does: "Telegram
  unlinked for {name}: the bot was blocked", by "The app".
- The note is written just after the unlinking, not in the same step: a crash between the two leaves the person unlinked with no
  line.
- A note for somebody who never links again stays in the store (the app's Telegram file); it is shown only to them.
- (M4) If the app is rolled back to the version before this one and forward again, a "bot was blocked" line can come back for
  someone who linked again in between; linking once more clears it.

E, the settings list:
- A message to somebody who blocked the bot is removed from the queue, the list of messages waiting to go (stage 4's ruling P3, so
  that it can be sent once they link again), so it is not in the list. D's line says it to the
  person instead.
- The list is for the relief team alone (ruling FA1): the timetable committee sees no list on the card.
- Equal times are ordered by name, which no test checks, and the edges of the week (Monday 00:00, Sunday 23:59) are not tested to
  the minute.

Small things in the code (this paragraph is for whoever maintains the code; nothing in it changes what a person sees): in `relief/web.py` the form's check reads the teacher and the sender before its `try` (both are always
set); a line of `relief/outbox.py`'s description is long; `relief/asking.py` keeps one arrow in a description, the file's own style.

## Open questions for the lead

1. D: should the unlinking be written in the History, by "The app"? One condition in the app's history hook (the code that writes
   each change to the History, which now needs a signed-in person) would allow it. **Built in the send-out, stage 1** (the History
   line by "The app", with the alert to the team).
2. B: should the form also say "{officer} will be told." when they are on Telegram, as `/relief` does?
3. A: should a request sent the evening before ping at the report's start (an hour before the first period)? **Settled by the
   morning message** (the send-out, stage 1): a request sent before the morning time is in that morning's message and pings nobody.
4. A: a request sent in the night is pinged at the report's start, an hour before the first period. Earlier, later, or as it is?
   **Settled by the morning message** (the send-out, stage 1), as 3.
5. Answer 6: was "fixed for both" meant as the Next button that was built? (C can be changed or taken out.)

## Checks

- Every suite on the final code, one at a time, after these documents were written (a test reads stage 4's plan table), all
  passing, each at its first run: all 29 `tests/*.py`: `smoke` 103, `test_accounts` 14, `test_admin` 30, `test_ask` 49,
  `test_board` 59, `test_choices` 16, `test_combined` 38, `test_compare` 21, `test_exams` 193, `test_exams_relief` 102,
  `test_fixes` 65, `test_helper` 20, `test_history` 47, `test_history_draft` 9, `test_parents` 35, `test_putback` 37,
  `test_relief` 42, `test_relief_requests` 59, `test_relief_team` 74, `test_relief_telegram` 327, `test_routes` 19, `test_rules`
  11, `test_signin` 33, `test_sync` 32, `test_teachers` 9, `test_typed` 33, `test_venues` 4, `test_verify` 56, `test_versions` 44;
  and all 23 `tests/*.test.js`: ask 12, board 67, choices 13, classview 18, draft 25, exams (9 page tests, then its onHandled and
  icChange groups, which print no number), grid 14, groups 33, history 5, map 26, parents 46, people 31, relief_inbox 3,
  relief_settings 23, relief_summary 11, relief_telegram 38, relief_today 40, split 189, subjectview 15, sync 17, teacherview 8,
  timetable_page 7, venueview 24. The slow `--full` runs were not done: no file they exercise changed.
- During the build, after each task, `test_relief_telegram`, `test_relief_team`, `test_relief_requests`, `test_routes`, `smoke` and
  the node files touched: 303, 305, 311, 313, 320, 325 and then 327 Telegram tests; 74, 59, 19 and 103 throughout;
  `relief_telegram.test.js` 37 then 38; `relief_settings.test.js` 23.
- Faults put in on purpose, one at a time, each caught (or a test added until it was): Task 1, 7 of 8 (the form using the sentence
  is the one not caught: no page test drives the form); Task 2, 5 (two tests added); Task 3,
  14 (three tests added; two of them cannot fail apart from another rule, and are kept as the plan wrote them); Task 4, 8; Task 5, 11,
  then 7 and 4 in its fix rounds.
- Names check, counts only, on the lines added since ebdccb9 and the commit messages: the school's full name 0; bot token and model key shapes 0;
  em-dashes 0 in the commit messages and 1 in the added lines, the plan's own check command, which names the character it counts
  (none is used as a dash). The school's real files were not opened for this.
- Names check against the school's staff list (counts only, on the lines added and the commit messages since ebdccb9): 104 real
  staff names, 0 found; the school's full name 0; token and key shapes 0. (Run again by the controller after the final fix wave.)
- Browser check, in practice mode on a made-up school with a scratch data folder, at desktop width and at phone width (375 px), by
  real clicks: the ask form's confirmation after Send read "Sent. The relief team can see it. Ms Rosa Ng is not on Telegram: please
  tell them yourself."; the Link Telegram card of a person unlinked by a blocked bot showed the line with its day, and the line went
  while a link code was shown; the Telegram card in Relief settings showed "2 messages could not be sent, 1 may not have been sent,
  since Mon 23 Nov." with its three rows, and neither the failed relief nor last week's row. No sideways scroll at phone width, no
  error in the page or the server. This was done before the final fix wave, and the settings card was seen as a relief team member;
  since that wave only the relief team sees the list, and a test covers the others.
- The final review, of the whole branch: no Critical; two Important (the settings list showed the committee who was away; the ping
  could come in the night), both fixed in the final fix wave (rulings FA1 and FA2); five Minor (one on these notes and one on the
  README, both fixed; three kept as known limits, ruling FA3).
- The second review, of the final fix wave alone: every point addressed, nothing Critical or Important. Three small points: the
  ping's start is not rounded to the report's interval (now under Known limits), a count in these notes (corrected), and a short
  comment in a test (left).
- After the final fix wave, every suite once more, one at a time: all 29 `tests/*.py` and all 23 `tests/*.test.js` pass
  (`test_relief_telegram` 329, `test_relief_team` 74, `test_relief_requests` 59, `test_relief` 42, `test_exams_relief` 102,
  `test_exams` 193, `test_routes` 19, `test_history` 47, `test_putback` 37, `smoke` 103, `test_board` 59,
  `relief_settings.test.js` 23, `relief_telegram.test.js` 38, `relief_today.test.js` 40). The names check was run again on the
  whole branch: 104 real staff names, 0 found; the school's full name 0; token and key shapes 0.
- Main moved while this was built (pull request #97, the Re-fit window on step 8, nothing of relief). It was merged in without a
  conflict, and every suite run on the result, one at a time: all 30 `tests/*.py` (the new `test_refit` 166) and all 23
  `tests/*.test.js` pass, with the numbers above.
- Before the merge of the pull request (#99), main had moved twice more: pull request #100 (a Re-fit follow-up) and #98 (Plan with
  AI, stage 1). Both were merged in without a conflict, and every suite run on the result, one at a time: all 31 `tests/*.py`
  (`test_relief_telegram` 329, `test_routes` 20, `test_plan` 200, `test_refit` 170, `test_exams` 206, `smoke` 103) and all 24
  `tests/*.test.js` pass.
- Final fix wave, one suite at a time at its end: `test_relief_telegram` 329 (two tests added, one of stage 4's changed: see the
  build's record above), `test_relief_team` 74, `test_relief_requests` 59, `test_routes` 19, `smoke` 103,
  `relief_settings.test.js` 23, `relief_telegram.test.js` 38; five deliberate faults, each caught.
- Not checked: no real Telegram bot was called anywhere, and no model; no suite reaches the network. `/relief` with Next and the
  ping to the team were not walked on a practice phone: tests alone cover them.

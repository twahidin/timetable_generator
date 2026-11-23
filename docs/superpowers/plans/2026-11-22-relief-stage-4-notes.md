# Relief stage 4 (Telegram): notes

Built 22 and 23 November 2026 on branch `relief-stage-4` (from relief-stage-3 d693183; main merged in at 6b664d3, e18d0e3,
f39b518, be22d11, 19ac240 and fbcad30), subagent-driven: a builder and a reviewer per task, a fix round where the review asked. Pushed and
opened as a pull request on 23 November, on the lead's word; not merged.
Plan: `2026-11-22-relief-stage-4-telegram.md`. Design: `../specs/2026-11-20-relief-module-design.md`.
How to set it up and what leaves the server: `../../DEPLOY.md`, section 6 and "What leaves the server".

## What stage 4 gives

The school's own bot tells the right person at the right moment, and people answer there; every answer is checked by the app as
on its own pages. Without a token, or until Connect is pressed, nothing is sent and nobody is told.

- Task 1, the client and the store (63025ae, 75a8929, 865dbb7): `relief/tg.py`, the one place that calls Telegram, and
  `relief/tgdb.py`, the file `relief/telegram.db`.
- Task 2, linking a person, the hook, connecting the bot (51917b0, 463738b, f62d72e): `links.py`, `bot.py`, `tgweb.py`.
- Task 3, the message queue and its sender (1f20414, e3b89b1, c9d26ba): `outbox.py`. A message goes once or is marked unsure.
- Task 4, what to tell and telling it (1837c18, 0b1850a, 2adc326): `tell.py`, `words.py`. Worked out from the records each time.
- Task 4b, main 6b664d3 merged in, and the lessons an exam stops (33d7a36, 94cd7cf, 7dad030).
- Task 5, answering on Telegram: Acknowledge, Request to change, cancel, Approve (c25788d, c0eb838, 651ff8a, 12115e0, 78e874c).
- Task 6, Remind, the not-acknowledged report, the all clear (8e325b5, e997b1b, 1b0ee66): `report.py`.
- Task 6b, main e18d0e3 merged in, and its stopped lessons followed (2935bbc, 28a2837, 6fcf1da, f7880d6, 2543470).
- Task 7, the weekly summary, message and page (2d12600, a86dd98): `summary.py`, `static/relief-summary.js`.
- Task 8, asking for relief with `/relief` (5b85a96, bf9a851): `asking.py`.
- Task 9, the pages: Link Telegram, Today's lines and Remind, the settings card (dc971d4, 09f9835, and after the browser check 14e4af6,
  91067dc).
- Task 10, the finish: main f39b518 (PR #93, the AI pick hides a name written as a title) merged in without a conflict (ba1b8c6),
  "Sent at ...: wait a few minutes." (3a7c29e), the guides (4699d48), the plan's text and these notes (f73c920); after its review main
  be22d11 (PR #94, an event's teacher in charge can be changed; README.md alone conflicted) merged in (786ddea), "Last tried at ..."
  (c3c72c8), and the guides and notes once more.
- The final fix wave, after the whole-branch review (F1 to F7, below): exam and event backups on Telegram (a8a4aea), an outage
  costs no more than the outage (610a814), what is not read is said (5736aee), and these guides and notes.
- After the fix wave's second review: main 19ac240 (PR #86, accounts stage 2: Put back, each person's own history, Change
  username) merged in without a conflict (b08b4ed), and the History download says "Telegram" for a change made there, as the
  History page does (Task 11, 6f490c6).
- Before the pull request: main fbcad30 (PR #95, a teaching-group row not filled in no longer stops the check, the download or an
  upload) merged in without a conflict (1a42984). It touches nothing of relief.

## Decisions the lead may change (the plan's 1 to 10)

Linking by a one-time code instead of the personal code (differs from the design); a link is not tied to the account's sign-in
number; a message once or "may not have been sent"; the kind of reason to the reporting officer alone; work text, links and files
go through Telegram; the report starts an hour before the first period; `/relief` offers the next ten school days; one copy only;
practice mode; exams make their own messages with `outbox.queue`.

## Rulings made during the build ("if wrong" is the cost)

Before the build:
- P1. What is shaped like a code is judged by its shape and never compared with personal codes, so the bot cannot be used to guess
  one. If wrong: copy.
- P2. Who can be reached is read once a sweep or page (`links.reachable`), never person by person. If wrong: nothing.
- P3. A message to a chat that blocked the bot is removed from the queue, so it can be sent after linking again. If wrong: a
  "failed" line is lost.
- P4. `words.py` and `fill.nudge` moved out of `web.py` to avoid an import cycle. If wrong: a move others' edits may meet.
- P5. One Remind (`report.remind`). If wrong: nothing.
- P6. `summary.week` takes the Monday and the time, not what was told. If wrong: nothing.
- P7. The officer offered is the latest absence's, not kept apart. If wrong: nothing.
- P8. The report's mark is the last round time at or before now. If wrong: nothing.

Task 1:
- 1a. What counts as "unsure", and taking the store's write lock at once, were put right before anything rested on them. If wrong:
  a few lines.

Task 2:
- 2a. A chat taken over by another person is told TAKEN, not MOVED_LINK. If wrong: copy.
- 2b. Connect's address is Railway's own name for the app when it is set, else the address it was pressed on (a header could be
  forged). If wrong: one condition.
- 2c. The same link pressed again by the same chat within its 15 minutes is answered HELLO. If wrong: a column.
- 2d. Accepted: STOPPED, history entries for connect and disconnect, `practice_bot` under a real token is not connected,
  conversations dropped when a link moves or ends, 503 when the store fails. If wrong: copy, or one condition each.
- 2e. Connected is tied to the token and SECRET_KEY; the address is checked whole; BAD_CODE says "deleted" only when it was; a code
  needs the relief right when it is used; odd JSON is never a 500. If wrong: a small round.

Task 3:
- 3a. 500 and 504 from Telegram are unsure; 502, 503 and the other 5xx are tried again. If wrong: a rare duplicate after a 502.
- 3b. Six tries, all five waits (about 43 minutes), before a message is failed, but only for a message that fails by itself: one
  that met an outage, or a token Telegram does not take, counts no try (F3 replaces the old ruling, where every "network" counted).
  If wrong: one number.
- 3c. After an unsure message, or one that met an outage, nothing goes until Telegram answers `getMe`, asked at most every 20
  seconds. If wrong: one call every 20 seconds while it is down.
- 3d. While the accounts cannot be read nothing is sent or dropped. If wrong: messages wait a little.
- 3e. A pause Telegram asks for holds everything, a bad item never stops the rest, and a message sending for over two minutes is
  unsure. If wrong: one larger round.
- 3f. Not being able to look up a chat counts as "try later", not as failed. If wrong: one condition.

Task 4:
- T4a. A relief message is keyed by the absent teacher, the lesson and the approval, not by the absence, so a backup taken over by
  the teacher's own absence is neither gone nor sent again. If wrong: a small search.
- T4b, M1, M2. Main was merged in before Task 5 and after Task 6, with the lessons an exam stops handled in tasks of their own (4b,
  6b). If wrong: one task each.
- The order: what follows a run of picks (`fill.AFTER`) comes at the end of `tick` and `_queued`, never in `run`, with the run's hold
  let go, each in its own try. If wrong: a few lines.
- 4a. "No longer needed" and "moved" are dropped when the relief is theirs again by then. If wrong: two entries.
- 4b. "No work set yet" only when there is no text, link or file. If wrong: copy.
- 4c. The absent teacher and the officer who were told of an absence are told that it is cancelled too. If wrong: two recipients more.
- 4d. Two people approved for one lesson in the same second have keys of their own. If wrong: nothing.
- 4e. At the first connect, a reminder still to come and a request still waiting are sent. If wrong: nothing.
- 4f. Somebody who lost the relief right is reached by nothing and is nobody's chat. If wrong: one check a call.
- 4g. Asks and "kept" are keyed by the absent teacher and the lesson; a lesson that is over is not told; Connect again keeps the day
  it was first connected; and six smaller ones. If wrong: small.
- 4h. The sweep and the reports have a one-minute ticker of their own, so they do not wait for an AI pick. If wrong: a thread.

Task 4b:
- 4i. "Not happening" needs the relief to be theirs still, "on again" the same approval; "kept" waits while stopped; a backup taken
  over is not told as cancelled. If wrong: copy.
- 4j. "On again" reaches everyone told it was off; exams that cannot be read say nothing about stopping; a relief team member's
  refused Approve may show the exam's name (they see it on Today). If wrong: one condition.

Task 5:
- 5a. A refusal in the app's own words takes the buttons off, with the sentence on the message; Approve keeps them when the pick has
  changed or is not free. If wrong: a message edit.
- 5b. Somebody without the relief right is told "This button is not for you."; a request to change or to cancel is refused at the
  press for whatever it would be refused for, whatever its reason; `/relief` ends a question that waits, and Acknowledge ends a
  waiting why for the same lesson. If wrong: copy.
- 5c. Nothing published (a publish swaps folders) keeps the buttons. If wrong: one word.
- 5d. A typed answer that replies to another message acts on nothing; one-word non-answers are asked again; Keep it. If wrong: copy.
- 5e. Cancelling takes a second press: a typed line never cancels an absence. If wrong: one more tap.

Task 6:
- 6a. A reminder that went counts as the relief having been told (moved, gone, stopped, again and cancelled once a relief). If wrong:
  one function.
- 6b. "sent Mon 15:00" when it was another day. If wrong: copy.
- 6c. The 13 choices accepted, among them: no all clear while a request to change of a lesson still to start waits; "The 1 relief for
  today is acknowledged."; no Remind button with nobody waiting; "not told yet". If wrong: copy and small behaviours.
- 6d. No all clear while anything of today cannot be read; a started relief is listed again when its report never went; an older
  report never follows a newer one. If wrong: one larger round.

Task 6b:
- 6e. A press refused because an exam stops the lesson keeps its buttons (Acknowledge, Request to change, Approve). If wrong: one word.
- 6f. "❌ Cancelled: ..." when the app did it. If wrong: copy.
- 6g. No all clear while today or the exams cannot be read; presses go by the page's own reading of the exams. If wrong: on such a
  date a relief may go out whose Acknowledge is refused.
- 6h. "Not happening" is said again whenever something since said that the relief is on; the officer's second line is left out, and
  the reminder not sent, when no lesson is left to cover; "Nobody else is free then" is not said of a date that is not known. If
  wrong: copy and a small key rule.

Tasks 7 to 10:
- 7a. The 13 choices accepted: Friday is about that week, any other day about the week before; within 24 hours or not at all;
  acknowledged after asking counts as kept; the page and the message may differ on a date the exams cannot read. If wrong: copy.
- 7b. A week with nothing readable is not marked done; on time is to the minute. If wrong: small.
- 8a. The 19 choices accepted, with the files outside the list (`files.check`, `web.created`, `secure_delete`, `bot.forget`, edited
  messages). A lost question keeps the conversation. If wrong: copy and small behaviours.
- 8b. The list before Send says what is set ("work set (text, 1 file)"); an edit that says the same is not answered. If wrong: copy.
- 8c. A start without a token deletes every conversation. If wrong: half an hour of somebody's typing.
- 9a. The 15 choices accepted (after a step here the day is read again until the teacher is told, five times at most); on a past date
  the line says only what is so. If wrong: copy.
- 9b. The link code goes from the page when the person is signed out or the page is left. If wrong: small.
- 9c. The fix round's seven choices accepted. If wrong: copy.
- 9d. From the browser check: "Open the bot" is the main button of the card; "Remind all not acknowledged" comes first in its row and
  its place is kept, so that nothing moves under the pointer; "Nobody to remind." in place of "Reminded 0."; room on Today and the
  weekly page. If wrong: copy and layout.
- 9e. The report says "sent 06:45 · not on Telegram now" of somebody told before and not reached any more. If wrong: copy.
- 9f. On a phone "Remind all not acknowledged" is the last of those buttons and no place is kept for it, so nothing above it moves. If
  wrong: layout.
- 10a. "Sent at {at}: wait a few minutes." in place of "Reminded at ...", since it is said after the relief itself too. If wrong: copy.
- 10b. Practice mode shows no address of a bot (the code alone); Relief settings' line on the reporting officer says when they are told.
  If wrong: copy.
- 10c. "Last tried at {at}: wait a few minutes." when that message may have gone, waits in the queue or is on its way. If wrong: copy.

The final fix wave (after the whole-branch review):
- F1. An exam or event duty's backup has no "❌ Not needed: cancel" button on Telegram, and cancelling one there is refused at
  each step: "This is for an exam or event duty, so it cannot be cancelled here. Ask the exams committee, or the event's teacher in
  charge." Cancelled there, it came back at the next sync at once. If wrong: a teacher cannot cancel a duty's backup from the phone
  (the page still can, and it comes back as before).
- F2. A backup the app ends (a withdrawn schedule, a changed duty, Handled ourselves) is told only to the person on duty and the
  reporting officer, if they were told of it; its relief teachers hear "No longer needed" as before. The relief team and the
  planner are not messaged (40 withdrawn backups were 80 messages for a team of two). A person who cancels still tells them. If
  wrong: the team and the teacher in charge hear of a withdrawn duty's backups only in the app.
- F3. An outage costs no more than the outage. While Telegram cannot be reached, or refuses the token (401 or 404), nothing is
  tried and no try is counted; the app asks Telegram every 20 seconds, and at once when it starts, and what waits goes within half a
  minute of its return, oldest first. What is not true any more by then is dropped. A message that fails by itself keeps its six
  tries and holds the others one run at most. The log has one line when a doubt begins and one when it ends. If wrong: up to one
  question to Telegram every 20 seconds while it is down; a message that fails by itself six times is given up after its six
  tries as before.
- F4. "Cancelled" is not sent once the absence's last date is past. Remind, while the last message of that relief still waits or is
  on its way, answers "Last tried at {at}: wait a few minutes." however long ago that was, and queues nothing more (before, two
  copies went together when Telegram was back). If wrong: nothing.
- F5. A line from a linked person that is no command, no code and no answer to a question is answered "I can't read messages here.
  To answer a relief, press a button under it. Send /relief to ask for relief." (it used to get "Linked: ..."). The same for a
  sticker or a command the bot does not know. /start, /help and linking still get "Linked: ...", a stray file or photo "That was
  not attached to any lesson", an unlinked chat "This Telegram is not linked", and a group nothing. If wrong: copy.
- F6. The Telegram tests take away any model key before they start, as the relief team's tests do. If wrong: nothing.
- F7. The guides, the plan and these notes say what F1 to F5 do; DEPLOY.md says what to do when `telegram.db` is damaged. If
  wrong: words.
- F8. A command the bot does not know (/cancel outside a conversation, /settings) and a blank message get the F5 sentence too,
  not "Linked: ...". It says what to do. If wrong: copy.
- F9. The second review of the fix wave found three small points and nothing more. One was a sentence in DEPLOY.md, corrected
  ("When Telegram is down": an outage that begins as a timeout marks that one message "May not have been sent"). The other two
  are in Known limits and were not fixed, since the build allows one fix wave. If wrong: one message lost to a restart in a
  window of seconds, during an outage, at its last try only.
- R1. The first builder's F3 and F4 work, found uncommitted after it was cut off, was read whole, kept and finished, not built
  again. If wrong: a fault of the first builder's that neither the nine faults put in on purpose nor the second review saw.
- M3. After the second review, main 19ac240 was merged in and every suite run on the result; the stage's routes and saves were
  checked against accounts stage 2 (below, Meeting accounts stage 2). If wrong: one more task.

## Copy the lead should see

In three groups: what differs from the approved mockups, what is new, and what is said when something cannot be done. What is not here is
as in the mockups, or one of the app's own sentences said by the bot unchanged. {..} stands for a name, a day, a lesson or a number.

**Changed from the mockups**

On Telegram:
- Linking: the mockup asked for the personal code ("Welcome. Send me your personal code"). Now a code from the app, and "Linked: {name}.
  You'll get your reliefs here. Send /relief to ask for relief, /stop to unlink." (no department).
- Relief for you: three lines more, when they apply: "No work set yet: look in Reliefs I'm covering." (nothing set), "Link: {link}",
  "Files: {n}, sent after this message."
- Relief planned for you: the reason is left out (the mockup: "whole day · Course"). "{n} lessons will be covered." is left out when none.
- Acknowledge: "✅ Acknowledged 07:46." on the message itself (the mockup: "Thanks. Acknowledged at 07:46. It is on your timetable for
  today."; the timetable is stage 3b's).
- Request to change: "Say why in one line. Until the relief team replies, this relief is still yours." (the mockup: "Tell us why, in a
  line."). To the team: "New pick: {name}" (the mockup: "AI's new pick"; it may be the app's own order), with the day. "The relief team has
  moved {lesson} {periods} on {day} to someone else. You're free then." has the day too.
- Cancelling: "Cancel this absence? Say why in one line, or press Keep it.", then "Cancel {days}? Your reason: {why}" with "Yes, cancel it"
  and "Keep it", then "Cancelled. The relief team will see it." (the mockup asked once and listed who was told).
- Not yet acknowledged: no "(25 min ago)"; "sent Mon 15:00" when it was another day, "not told yet", "not on Telegram", "sent 06:45 · not on
  Telegram now". It starts an hour before the first period (the mockup: from the first relief sent).
- All clear: "The 1 relief for today is acknowledged."; "No reliefs are waiting now: {k} started without acknowledgement."
- The week: "· waiting {n}" when some still wait; the Flexi Adjunct line only with that role.
- `/relief`: "Tomorrow, {day}"; "From which period?" and "To which period?" (the mockup had one answer, "P1–P9"); "Work for {lesson}
  {periods} on {day} ({start})? Type it, send a file or a photo, or tap Later." (the mockup: "Type it, send a file, or tap Later."); "Later
  for all the rest"; a list to look at before **Send** (below); "✅ Sent to the relief team: {n} lessons, work set for 2." or "no work set
  yet" (the mockup: "work set for both"), and "{officer} will be told." (the mockup: "has been told").

In the app:
- Today: an approved row says "Approved" and, under it, "Sent 07:20" (the mockup: "Sent 07:20 · not acknowledged (25 min)").
- What's in: "asked on Telegram" (the mockup: "himself · Telegram").
- Weekly summary: three lines more ("Arranged: {a} planned ahead · {b} on the day", "Acknowledged: {x} on time · {y} late · {z} never · {w}
  waiting", "Asked to change: {n} ({m} moved, {k} kept)"), "By department of the absent teacher" and "Most relief this week" (the mockup has
  them in the message alone), "Counted in periods; absences and requests to change are counted one by one. A lesson stopped by an exam or
  event is left out.", "No relief this week.", "Week of {day}" while a week is read, and ‹, › and "This week" (the mockup: a list of weeks).
- Relief settings: "Connected as @{bot} since {day}: {address}", "{n} of {people} linked", and the lists "Not linked ({n})" and "Linked
  ({n})" with Unlink (the mockup: "Bot connected · 84 of 96 teachers linked · who isn't linked · Print code slips"). No code slips: codes are
  not used for linking. The reporting officer "Is told on Telegram, when they have linked it, when someone who names them asks for relief."

**New**

On Telegram:
- To the reporting officer: "{absent} is away on {days} ({whole day or periods}): {kind}." and, when a lesson is to be covered, "Relief is
  being arranged."
- To the relief teacher: "❌ No longer needed: {lesson} {periods} ({start}) on {day}. You're free then."; "The relief team has kept {lesson}
  {periods} on {day} with you."; for a lesson an exam or event stops "❌ Not happening: {lesson} {periods} ({start}) on {day}: {why}. You're
  free then." and "✔ On again: {lesson} {periods} ({start}) on {day}. The relief is yours as before."
- To the team, the planner and whoever was told: "❌ Cancelled by {by}: {absent}'s absence on {days}. Its reliefs are no longer needed."; when
  the app ended a backup, "❌ Cancelled: ..." to whoever was told of it alone.
- To a line the bot does not read: "I can't read messages here. To answer a relief, press a button under it. Send /relief to ask for
  relief." ("Linked: {name}. ..." is now for /start, /help and linking alone.)
- To the team, on a request to change: "Nobody else is free then: choose someone in the app."; "No new pick yet: open the app."
- On the message a button was on: "✅ Approved: {name}, 07:46.", "↩ Asked to change 07:31.", "❌ Cancelled 08:10."; after Remind them again
  "Reminded {n}."
- Linking: "Unlinked. Your relief messages stop here. To link again, open Relief in the school's app and press Link Telegram."; "Your relief
  messages now go to another Telegram. If this was not you, tell the relief team."; "This Telegram was linked to someone else before. Their
  relief messages no longer come here."
- The bot's menu: "Ask for relief", "Unlink this Telegram", "What this bot does".
- `/relief`: "Which days? Tick them, then press Done."; "Which day?"; "Say why in one line." (for Other); "Who is your reporting officer?
  Type part of their name."; "Who is your reporting officer?" over the names found, with "Not here? Type more of the name."; the list:
  "Relief for {days} · {whole day or periods}", "Reason: {kind}", "Reporting officer: {name}", a line for each lesson with "work set (text,
  1 file)" or "no work yet", "and {n} more", and **Send** / **Start again**.
- A very long message ends with "…and more in the app."

In the app:
- My absences: "Get your reliefs and reminders on your own Telegram.", **Link Telegram**, "1. Open the bot", "2. Press Start there.", "Or send
  this code to @{bot}: {code}", "The code works once and runs out in 15 minutes.", "That code has run out.", **Get a new code**, "Linked as
  @{name} since {day}." or "Linked since {day}.", **Unlink**, "Stop relief messages to this Telegram?" with **Keep it**.
- Today: "Sent 07:20 · not on Telegram now", "Being sent…", "Not sent yet", "Not on Telegram: they see it in Reliefs I'm covering"; **Remind**
  ("Reminded.") and **Remind all not acknowledged** ("Reminded {n}."; nothing of the number when nobody was, only why).
- Relief settings: "Not set up yet. The bot's token goes in Railway's variables (TELEGRAM_BOT_TOKEN) of the copy the school uses; then come
  back here and press Connect. How to make the bot is in docs/DEPLOY.md."; "The token is set. Connect points Telegram at this copy of the
  app."; "The bot works on one copy of the app only. Connect it on the copy the school uses."; "Practice mode: nothing is sent to Telegram.";
  **Connect the bot**, **Connect again**, "Connected."; **Disconnect**, "Disconnect? Nobody gets messages until it is connected again.";
  "Stop relief messages to {name}?"; "Nobody." in an empty list.
- History: "Telegram" as the way; "Telegram linked", "Telegram linked (moved from another Telegram)", "Telegram unlinked", "Telegram unlinked
  for {name}", "Telegram unlinked for {name}: the same Telegram is now {name}'s", "Telegram connected (@{bot})", "Telegram disconnected",
  "Reminded {n} relief teachers on {day}".

**Said when something cannot be done**

On Telegram:
- Linking: "This Telegram is not linked. Open Relief in the school's app, press Link Telegram and follow the link there."; "That code is not
  right or has run out. Get a new one in the app. If it was your personal code, do not send it here: it opens the app. I have deleted your
  message." (or "Please delete your message now." when Telegram did not delete it).
- A button: "This button is not for you."; "This button is no longer active."; "Something went wrong. Try again in the app."
- Cancelling a backup: "This is for an exam or event duty, so it cannot be cancelled here. Ask the exams committee, or the event's teacher in
  charge."
- A typed answer: "Answer the question I asked last."; "Nothing was changed." (after Keep it or /cancel).
- `/relief`: "Please press one of the buttons."; "Send text, a file or a photo."; "Tick at least one day."; "There are no school days coming
  up in the calendar."; "Nobody on the staff list matches that. Type part of their name."; "{file}: {why}" for a file the app refuses; "{name}
  could not be attached: add it in the app."; "That was not attached to any lesson: add it in the app."; "{officer} is not on Telegram: please
  tell them yourself."; "Cancelled: nothing was sent."; "Your request for relief was not sent. Send /relief to start again."
- Remind them again: "Nobody to remind."; "Not on Telegram."; "Sent at {hh:mm}: wait a few minutes." (the last message of that relief went);
  "Last tried at {hh:mm}: wait a few minutes." (it may have, or waits, or is on its way, however long ago).

In the app:
- Today: "May not have been sent: remind them"; "Could not be sent: remind them"; on a past date "Not sent", "May not have been sent", "Could
  not be sent"; Remind's answers as on Telegram; "Telegram is not connected yet."; "Telegram could not be reached just now. Try again."
- My absences: "Telegram is not connected yet."; "Something went wrong. Try again."; "Please sign in again."
- Relief settings: "Set SECRET_KEY in Railway variables first: the bot needs it."; "Telegram needs a secure address: open the app at its https
  address and press Connect there."; "Telegram did not answer, or did not accept the bot. Check TELEGRAM_BOT_TOKEN in Railway variables and
  try again."; "Add the bot's token in Railway variables first (TELEGRAM_BOT_TOKEN)."; "Disconnected here, but Telegram did not answer. The
  app reads and sends nothing now."; "That person has no Telegram linked."; "Could not reach the server. Check the connection and try
  again."; "Sign in again (opens a new tab), then try once more."

## Meeting accounts stage 2 (main 19ac240, PR #86)

- No text conflict. Every Telegram route is in the route test's lists, and that test passes. A save made on Telegram writes one
  history entry by that person, marked "Telegram", as before; main did not change how relief writes its entries.
- Everyone signed in by name now sees their own history. What a teacher did on Telegram (acknowledged, asked to change, asked for
  relief) is in it, marked "Telegram".
- A person's rights on Telegram now hold "their own history" too. It opens nothing there: Telegram shows no page.
- One thing was changed (Task 11): the History download wrote "telegram" in small letters in "Signed in with"; it says
  "Telegram" now, and a test keeps the page's words and the download's words the same.
- Put back (main's) does not touch relief: relief entries have no Put back button, as before.

## Meeting exams

- What exams does: an approved exam or event stops lessons, and duties become backups (planned absences). Nothing under `exams/` is
  changed on this branch, and exams sends no message of its own.
- PR #89 (the join, main 6b664d3) came in with Task 4b; #91 (the date fix) and #92 (after a withdrawn exam, main e18d0e3) with Task 6b.
- What this stage does: every question "does an exam stop this lesson" is `cover.stopped(links, x)`, and for what is sent it is asked
  through `tell.known(links, iso)` and `tell._stopped(links, x)`: a date the exams cannot read (`Links.unread`) counts as not known, so
  no lesson of it counts as stopped, nothing is said or taken back about stopping, and there is no all clear.
- A press goes by the page's own links (`bot._exams`), so Telegram refuses what the page refuses, in the page's words.
- A backup is told as any planned absence is: PLANNED and one reminder to the person on duty, the relief to its teacher once approved,
  CANCELLED when it is withdrawn ("Cancelled:", nobody named), to the person on duty and an officer who were told of it alone
  (F2). It cannot be cancelled on Telegram (F1). A backup the teacher's own absence took over is not told as cancelled:
  its reliefs went with it, and their messages too (they are keyed by teacher and lesson).
- A lesson stopped when its absence was sent stays needed (PR #92), so it is picked, approved and told once the exam is withdrawn.
- PR #94 (main be22d11): the committee may give an event to another teacher in charge, and the backup's `by` changes with it. Checked on the
  made-up sample: PLANNED is not sent again (its key is the absence's), and names whoever was in charge when it was made; a cancel by a person
  later tells the one in charge at that moment, not the one before (unless they are on the team, or were told of the absence); the reminder, the
  relief and what is told of it go on as they were; the one before can no longer cancel it. Nobody is told of the change itself. When the
  teacher in charge was going themself, they were not told PLANNED; they are once somebody else is in charge.

## What exams may use

- `outbox.queue(key, name, text, kind=..., buttons=(), files=(), ref=None)`, then `outbox.wake()`. True: the message is new. False: its
  key is there already (in any state but dropped), or the person has no Telegram. ValueError: it could not be kept.
- The key is the message: queued once, whoever asks again. Start it with a word of your own ("exam:"); these are taken: relief, gone,
  moved, stopped, again, kept, ask, askpick, planned, remind, officer, cancelled, report, clear, weekly. A message to several people
  ends its key with the name.
- The kind is yours too. Put its check in `tell.CHECKS`: `f(ref, name)` is asked just before the message goes, and False drops it (the
  key is free again). A kind with no check always goes. What cannot be read should raise: the queue asks again later, six times in all.
- `links.connected()` first (None: nothing to do), and `links.reachable(pub)` once for everyone ({name: chat}); never `chat_of` in a
  loop.
- A hook of your own in `tell.MINUTE` (app.py, where the jobs are on and there is a token) runs every minute. Work out from the records
  what should be told, as `tell.due` does; do not queue from the routes.
- Buttons: `dict(text, url)` with an https address, or a kind of your own in `bot.ACTIONS` (the right it needs, what it does, the
  refusals that keep it).
- What not to do: call `tg.call` (only `outbox`, `bot`, `asking` and `tgweb` do); queue, or do anything that may call Telegram, while
  holding `absences._LOCK` or the exams lock; put a chat number, a token, a key or a name in a log (keys hold names); put a reason, a
  remark or anything a model wrote in a text; texts over 4000 characters (cut at a line end); HTML or Markdown (texts are plain).

## Checks

- Every suite on the final code, one at a time, all passing: `test_relief_telegram` 290, `test_relief_team` 74,
  `test_relief_requests` 59, `test_relief` 42, `test_exams_relief` 101, `test_routes` 19, `smoke` 102, `test_accounts` 13,
  `test_admin` 18, `test_ask` 49, `test_board` 58, `test_choices` 16, `test_combined` 38, `test_compare` 21, `test_exams` 189,
  `test_fixes` 65, `test_helper` 20, `test_history` 27, `test_history_draft` 9, `test_parents` 35, `test_rules` 11,
  `test_signin` 24, `test_sync` 32, `test_teachers` 9, `test_typed` 33, `test_venues` 4, `test_verify` 56, `test_versions` 44.
  Right after the merge of main the first seven passed too (`test_relief_telegram` 289 then). After Task 9's second fix round
  `test_relief_telegram`, `test_relief_team`, `test_routes` and `smoke` passed again, with the same numbers.
- After Task 10's fix round (main be22d11 in, the reminder's two sentences, the guides), again one at a time, all passing:
  `test_relief_telegram` 291, `test_relief_team` 74, `test_relief_requests` 59, `test_relief` 42, `test_exams_relief` 102,
  `test_exams` 193, `test_routes` 19, `test_accounts` 13, `test_history` 27, `smoke` 102, and every `tests/*.test.js`. The two
  slow runs below that failed were not run again: the Mac's load stayed above 8.
- The final fix wave was built in two sittings: the first builder was cut off on 23 Nov after F1 and F2 were committed; the second
  finished F3 and F4 from its work, not yet committed, then did F5 to F7. Nine faults put in on purpose in F3 and F4, one at a time,
  were each caught. Then, one at a time, all passing: `test_relief_telegram` 302, `test_relief_team` 74, `test_relief_requests` 59,
  `test_relief` 42, `test_exams_relief` 102, `test_exams` 193, `test_routes` 19, `test_accounts` 13, `test_history` 27,
  `test_history_draft` 9, `smoke` 102, and every `tests/*.test.js` with the numbers below.
- Every `tests/*.test.js` passes (ask 12, board 67, choices 13, classview 18, draft 25, exams, grid 14, groups 33, map 26, parents 46,
  people 31, relief_inbox 3, relief_settings 22, relief_summary 11, relief_telegram 36, relief_today 40, split 189, subjectview 15,
  sync 17, teacherview 8, timetable_page 7, venueview 24).
- The slow runs, each alone: `smoke --full` 103, `test_combined --full` 39, `test_fixes --full` 67, all passing. `test_typed
  --full` and `test_helper --full` failed as they are, while other work kept the Mac's load at 10 to 33: their 30-second solve
  did not finish (`test_typed` three times, `test_helper` once; its second run failed on a swap of two lessons of one group, the
  fault in main that the join's notes tell of). Run once each with 120 seconds for the solve and nothing else changed, both
  passed (34 and 21). No file they exercise differs from main.
- The second review of the fix wave (c8183d7 to 0f0ba08): F1 to F7 each addressed, nothing Critical or Important, three small
  points (ruling F9).
- After the merge of main 19ac240 (b08b4ed), every suite, one at a time, all passing: all 29 `tests/*.py` (`smoke` 102,
  `test_accounts` 14, `test_admin` 30, `test_ask` 49, `test_board` 58, `test_choices` 16, `test_combined` 38, `test_compare` 21,
  `test_exams` 193, `test_exams_relief` 102, `test_fixes` 65, `test_helper` 20, `test_history` 46, `test_history_draft` 9,
  `test_parents` 35, `test_putback` 37, `test_relief` 42, `test_relief_requests` 59, `test_relief_team` 74,
  `test_relief_telegram` 302, `test_routes` 19, `test_rules` 11, `test_signin` 33, `test_sync` 32, `test_teachers` 9,
  `test_typed` 33, `test_venues` 4, `test_verify` 56, `test_versions` 44) and all 23 `tests/*.test.js` (the numbers above, and
  `history` 5, new on main). After Task 11: `test_history` 47, `test_routes` 19, `history.test.js` 5. The slow `--full` runs and
  the browser check were not done again after the fix wave: no page changed in it.
- On the last code (after Task 11), every suite once more, one at a time: all 29 `tests/*.py` and all 23 `tests/*.test.js` pass,
  with the numbers above and `test_history` 47.
- After the merge of main fbcad30 (1a42984), the code the pull request holds, every suite once more, one at a time: all 29
  `tests/*.py` and all 23 `tests/*.test.js` pass, with the numbers above but `smoke` 103 and `test_board` 59 (main's new tests).
- Names check on the whole branch against main 19ac240 (added lines and commit messages, counts only): 104 real staff names
  from the school's newest setup file, 0 found; the school's full name 0; bot token shapes 0; model key shapes 0; em-dashes in
  the guides' and these notes' new lines 0.
- No suite reaches the network: without a token nothing is called, and the tests that set one replace `tg._send`, the only way out to
  Telegram. No real Telegram or model call was made anywhere.
- Faults put in on purpose, in copies of the tree (caught at once, of how many; the rest were gaps closed with tests, code taken out,
  or shown to make no difference): Task 2: 50 of 51, 17 of 19, 22 of 24. Task 3: 97 of 106, 20 of 21, 61 of 65. Task 4: 117 of 140, 30
  of 32, 16 of 16, 56 of 60. Task 4b: 35 of 38, 13 of 14. Task 5: 78 of 81, 15 of 15, 47 of 48, 9 of 9, 35 of 38. Task 6: 106 of 117,
  21 of 21, 46 of 51. Task 6b: 36 of 36, 14 of 14, 31 of 31. Task 7: 91 of 92; then the page 35 of 41 and the server 9 of 10. Task 8:
  136 of 144, 60 of 61. Task 9: 492 of 529 and 14 of 14, then 184 of 206, then 66 of 68. Task 10: 12 of 12.
- Random and killed runs: the sender killed at each of its steps for six kinds of answers (258 kills) and by a real kill signal (75
  kills, about 400 messages each round): never a message or a file twice. `/relief`: 10,100 random steps one at a time and 1,540 rounds
  of 3 to 8 things at once, with the lock and, as for two copies of the app, without: never two absences, two entries or two "Sent";
  again after the fix round (1,500 and 250). Today with no bot connected, the old script and the new side by side: 1,560 states, the
  same page and the same calls, twice.
- A real gunicorn (one worker, 8 threads, practice, scratch data) for the hook: 404 before Connect, 403 without the secret, 413 past the
  limit, each update once.
- The school's real published timetable, numbers only, scratch deleted, no model, practice mode, no network (at 09f9835): 111 teachers,
  10 school days, 183 made-up whole-day absences (17 refused: no lessons), 563 lessons to cover; picks for one day 20.9 s (stage 3's
  work, mock model); 60 approved; 111 linked; the first sweep queued 60 messages in 0.24 s, an idle sweep 0.03 to 0.04 s; 60 sent in 2
  runs, 3.8 s (practice); longest message 206 characters; report tick 0.00 s; weekly summary 0.02 s; the first question of `/relief`
  0.01 s.
- A walk in practice mode on the made-up sample, inside the process (no browser, no web server): link by Start and by typed code (52
  people), `/relief` with a typed reason, an officer found by name, text, a photo, Same as before, Send; the officer told; approve all;
  three reliefs told, the photo sent after its message; Acknowledge; Request to change with a why; the team asked with the new pick;
  Approve from Telegram; the first teacher told "moved", the new one told; the report at 07:15 ("Not yet acknowledged (2)"), Remind them
  again ("Reminded 2."), both acknowledged, the all clear at 07:20 ("All 3 reliefs for today are acknowledged."), the weekly page right
  (9 periods, 1 absence, 1 asked, 1 moved); the typed reason in no message and not in `telegram.db`; no error. It found that "Reminded
  at" was said after the relief itself (Ruling 10a).
- The browser check (practice mode, the made-up sample, real clicks, 1280 px and phone width 375): the settings card (the practice line,
  Connect, "Connected as ...", the counts, what is typed in the form kept, the Not linked and Linked lists, Unlink with its question and the
  list staying open, Disconnect's question with the focus on Keep it, Escape); the link card (not linked, the code, linked by itself within 5
  seconds, Unlink's question, Escape; the code gone after Sign out and Back); `/relief` on a practice phone (a typed reason, an officer by
  name, text, a photo, Same as before, the list with "work set (text, 1 file)", Send); Today (Approve all, "Not sent yet" then "Sent 06:45"
  by itself, Remind too soon, after five minutes "Reminded.", "Being sent…" and "Sent 06:52" by itself, Remind all with its reasons, "Sent
  06:45 · not on Telegram now" after Unlink, with no Remind there); Acknowledge, Request to change and Approve on Telegram; What's in "asked
  on Telegram"; the weekly page. No sideways scroll at phone width on any. What it found (9d to 9f: the main button of the link card, the
  place of Remind all, "Reminded 0.", room on Today and the weekly page, the practice link, the officer's line) is in 14e4af6 and 91067dc,
  and Today and the weekly page were looked at again after it at both widths.

## Known limits

Messages and the queue:
- A report or an all clear that is 30 minutes late (Telegram down, a long pause) is dropped, never sent late. A new pick after the one
  the team was asked about goes to the team once more; a third is seen in the app alone.
- Two copies of the app and a wait for a retry: never a duplicate, but one copy may wait longer. Buttons that ran out stay in the store
  until the next start.
- A file that is unsure sets no doubt; five files that time out hold the other messages up to five minutes.
- If unlinking a blocked chat fails, the link stays until the next message. That unlinking writes no history entry (still so: the
  person is now told on their own card instead, and an entry "by The app" is an open question in `2026-11-23-relief-telegram-answers-notes.md`).
- A fault of the app's own before anything was sent counts as "network"; so does an answer that is neither 200 nor an error. Telegram
  answering at once tells it from an outage: it is tried six times in all, and holds the other messages one run each time. A blip
  shorter than one run may count one try. Practice mode keeps every call in memory for as long as the app runs.
- A message at its sixth and last try that meets an outage shows as "Could not be sent" for the few seconds until the app has
  asked Telegram and found it down; then it waits again. If the app restarts in just those seconds, it stays "Could not be sent".
- A work file whose place on Telegram's file server has run out is logged as "network", not "refused". Only the log's word differs.
- A fresh relief message and "on again" may both go when they cross in the queue (both true). "On again" is not said when a publish
  renamed the lesson's group while the exam stopped it (its key is not there any more).
- A link or its code is good for whoever uses it first within its 15 minutes: one passed on links the wrong Telegram. HELLO names the
  person linked, and the History has it.
- A relief that an exam's takeover moved into a record that cannot be read at that moment can be told "No longer needed". It needs a
  corrupt file. A stray file in the absences folder is passed over.
- An officer's message queued before the last lesson stops keeps its second line. A "kept" message does not count as saying that the
  relief is on.
- A relief the person knows of only by the app (acknowledged there before they linked) or by "kept" counts as never told on
  Telegram: when it is then moved, no longer needed or not happening, nothing is said there (the review's Minor 1).
- A backup that gains a lesson after "Relief planned for you" was sent is not told again on Telegram; only its one reminder, and not
  once that went (Minor 6). A reminder in the same second as "not happening" does not count as after it.

The report, the all clear and the week:
- An absence file that can never be read holds back every all clear until it is put right (the safe side; its kind is logged each
  minute).
- An all clear may come to somebody without the dropped report before it; a started relief may be listed one report late.
- "On again" is withheld while a date cannot be read, so an acknowledged relief told "not happening" is in no report then.
- Main logs an error per sweep for one damaged duty; the weekly part logs an unreadable file each minute while it holds the summary
  back (a day at most).
- `weekly_last` is one number: a server clock that ran years ahead for a minute would keep the summaries quiet until then.
- Each sweep (after a save, and every minute) reads every absence file. Today reads every relief message that is kept (400 days; 12,000
  rows took about 0.1 s). The small rows that mark a report or a started relief are never deleted.

Presses and typing:
- What a request to change or a cancel is refused for is asked in two places (at the press and when it is done). A fault in a malformed
  record is shown as the page shows it. An acknowledgement on the page in the same second as a press is not "since".
- A press whose app stops before the save is lost: press again. A cancel waits for the exams lock, as the page's does.
- `/relief`: two messages meant for one lesson went to two lessons; since the lead's answers a lesson takes any number of messages
  until **Next** (its limits now are in `2026-11-23-relief-telegram-answers-notes.md`); whatever is
  typed at a work question is the work, a personal code too, and the relief teacher gets it (typed as a why to change, the relief
  team); Send fetches files inside the request; an album is noted before its "not attached" is queued; a list redrawn as Send is pressed
  may show its buttons again (they are no longer active).
- A second copy without a token would delete the first one's conversations if they shared a volume (they do not).

The pages:
- A status read that never answers holds back later reads until a step or leaving the page. A guard was dropped from the page's
  visibility handler (no way found for it to matter).
- Another person signed in in a second tab: the first tab then shows the second person's link (page-wide, older than this stage).
- A code asked for in a second tab ends the first tab's; Cancel only closes the card, and the code stays good until it runs out.
- "Planned by {name}" in PLANNED is whoever was in charge when it was made (PR #94).
- Remind on a lesson that is over answers "Nobody to remind."; the app has no dark mode to follow.
- "Open the full summary" and "Open in the app" go through the sign-in page when nobody is signed in, and do not come back to the tab.

Small things in the code: the bot's practice name is written twice, `tgweb.need` repeats `web.need`, `_noted` is in two modules,
`tell.APPROVED` is also `web.APPROVED`, `_taken_over` matches a sentence of `absences.py`, `cover.acknowledge` is called by tests alone,
`_send` and `call` both meet an HTTP error, a yes or no in a form with files is written "True", a waiting "No longer needed" reads every
record when it goes, some test lines are long. `tests/test_relief_requests.py` may depend on the date it is run on (it fails when only
`lessons.today` is moved to February 2027; not this stage's, not looked into).

## Follow-ups

- Done (the lead's answer 12, yes; built: 2026-11-23-relief-telegram-answers): messages other than reliefs that could not be sent, or may not have been, were shown to
  nobody (a report, PLANNED, a request to change ...). The Telegram card in Relief settings now lists them since Monday, by kind,
  name and time, never the text (the review's Minor 4), to the relief team alone. Reports and all clears are left out: see `2026-11-23-relief-telegram-answers-notes.md`.
- Stays (the lead's answer 13, "fix next time"): a school without a token is not quite as before: Today has 12 px more under its
  buttons (Minor 9). Harmless; it goes when Today is next touched.

## What the final review left to the lead

The review did not judge these. Each is kept as it is.

When a teacher asks for relief for today with `/relief`, the relief team was not pinged on Telegram; the design lists no such
message. It was the first open question below. The lead answered yes on 23 Nov 2026, and the ping is built (from the app's form
and `/relief` alike, once its picks wait for approval, never before the report's start, an hour before the first period, so one
asked in the night is sent then): see `2026-11-23-relief-telegram-answers-notes.md`.

Work set after the relief teacher was told is not told to them. Their message says to look in the app.

A teacher renamed by a publish loses their Telegram link. A relief whose lesson a publish moved stays, and is flagged in What's
in alone. The design says so.

Cancelling a backup on the page brings it back at the next sync. That is main's, not changed here.

The kind of reason sent to reporting officers, work files through Telegram, the one-time codes and the second press to cancel
were the lead's open questions below. The lead kept all four (answers 2, 3, 4 and 7).

A link or a code passed on links whoever uses it first. "Open in the app" does not come back to the tab after signing in. A
personal code typed as work goes as work. These are known limits, accepted.

Somebody unlinked by the relief team is not told on Telegram. That is right for a lost phone.

Slow Telegram file servers can hold the app's hook for minutes, four at a time. It is rare, and nothing is lost.

What Telegram kept while the app was down acts when it comes, and is judged at that moment. Conversations and codes have run
out by then.

Real Telegram was never called: its limit per chat, its answers for a bot nobody started, deleting messages, link previews,
its speed and Railway's network. Only the first real run shows them (the list at the end).

Speed was measured on a Mac alone, not on Railway.

The wording of the guides, the README and the copy was left to another reviewer and to the lead.

The suites were not run again by the review; the browser and the layout were the controller's check.

## Open questions for the lead

All answered by the lead on 23 Nov 2026 (thirteen answers: 1 to 11 here, 12 and 13 to the two follow-ups above). What was
built and decided on them is in `2026-11-23-relief-telegram-answers-notes.md`.

1. When a teacher asks for relief for today, the relief team is not pinged on Telegram (the design lists no such message): should it
   be, when picks are waiting for approval? **Answered 23 Nov 2026: "yes"**; built: 2026-11-23-relief-telegram-answers.
2. The one-time code in place of the personal code (decision 1 of the plan; differs from the design). Keep? **Answered 23 Nov 2026: "keep"**.
3. Work files go through Telegram with the relief. Keep, or "open in the app" for files? **Answered 23 Nov 2026: "Keep"**.
4. The reporting officer's message holds the kind of reason, Medical and Child sick among them. Keep, or leave the kind out? **Answered 23 Nov 2026: "Keep"**.
5. Reporting officers who are not on Telegram are told nothing by the app (`/relief` tells the asker so; the app's own form does not).
   Should the form say so? **Answered 23 Nov 2026: "yes"**; built: 2026-11-23-relief-telegram-answers.
6. `/relief`: one message a lesson, so a text and then a file go to two lessons. A Next button would mend it, at one more tap a lesson.
   Wanted? **Answered 23 Nov 2026: "fixed for both"** (read as: build the Next button, so that a text and a file land on the same lesson); built: 2026-11-23-relief-telegram-answers.
7. Cancelling on Telegram takes a typed line and a second press, where the mockup took one. Keep? **Answered 23 Nov 2026: "keep"**.
8. The report begins an hour before the first period. Keep, or from the first relief sent? **Answered 23 Nov 2026: "keep"**.
9. While an old file cannot be read, the all clear is held back and only the log says why. Should the team be told? **Answered 23 Nov 2026: "ok"** (to the suggestion "not now": not built).
10. Should a person be told in the app that their Telegram was unlinked because the bot was blocked? **Answered 23 Nov 2026: "yes"**; built: 2026-11-23-relief-telegram-answers.
11. The copy above: anything to change? **Answered 23 Nov 2026: "Ok"** (no wording change asked).

## Before the first real run (a real bot is connected for the first time)

In order, on the service the school uses, with the lead and one or two people who know it is a trial:

1. Merge and deploy without the token first. What is new then: the Weekly summary tab (relief team), and the Telegram card in Relief
   settings ("Not set up yet. ..."). There is no card in My absences, and Today is as it was.
2. The bot and the token (DEPLOY.md, section 6). Press **Connect the bot**: the card shows the address people use, not another one.
3. Link by **Open the bot** and Start; link a second person by the typed code; press the same link twice; send a wrong code (deleted,
   with its answer); `/stop`; link again. On a phone: coming back from Telegram to the app's page, does the card say linked by itself?
4. Plan relief for one of them and approve it: the message, its files, **Acknowledge**, the line on the message. Press it twice.
   **Request to change**: the line opened for the answer, a plain answer, an answer that replies to another message. Cancelling: both
   presses. The absences are real records: use lessons still to come, name each other as reporting officer, and cancel the absences
   afterwards (the linked relief team and officer get those messages).
5. `/relief`: a link as work (does its preview arrive as an edit, and is it left unanswered?), an album of photos (its later files), a
   forwarded file, a PDF near 10 MB, a photo. Then What's in: "asked on Telegram", and the files on their lessons.
6. Block the bot, then approve a relief for that person: they are unlinked, and Today says "Not on Telegram: they see it in Reliefs I'm
   covering".
7. The first busy morning: does Telegram ask for a pause (429)? Then everything waits until it ends and goes in order; a restart
   meanwhile forgets the pause. A message that is sending for over two minutes is marked "May not have been sent". If Telegram is
   down for a while, nothing is given up: what waits goes within half a minute of its return, and the log has one line when it
   begins and one when it ends.
8. The report and the all clear at their times; **Remind them again**; the summary on Friday.
9. Railway's logs hold the kinds of failures alone ("network", "slow", "unsure" ...): no name, text, chat or token. The History says
   "Telegram" beside the person.
10. If anything is wrong, **Disconnect** turns it all off, and nobody is unlinked.

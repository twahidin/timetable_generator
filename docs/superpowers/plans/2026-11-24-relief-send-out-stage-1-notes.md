# Relief duty and the send-out, stage 1: notes

Built 23 and 24 November 2026 on branch `relief-send-out` (from main d2dfbaf, with the design c0785f6, 8038f03 and c797c9b and the
plan fdbfef2), in the worktree `tt-relief-stage-4`, subagent-driven: a builder and a reviewer per task, a fix round where the review
asked. Not pushed, not merged, not deployed.
Plan: `2026-11-24-relief-send-out-stage-1.md`. Design: `../specs/2026-11-23-relief-duty-and-send-out-design.md`, with its mockups
`../specs/2026-11-23-relief-duty-and-send-out-mockups.html`. The notes before this one: `2026-11-22-relief-stage-4-notes.md` (Telegram)
and `2026-11-23-relief-telegram-answers-notes.md` (the lead's thirteen answers).
How to set it up and what leaves the server: `../../DEPLOY.md`, section 6 ("When messages go") and "What leaves the server".

## What this is

On 23 November 2026 the lead described how relief duty really runs at CTSS: the team rests in the evening, one person is in charge
each day, relief teachers are told in the morning all at once when someone presses Send out, and some days have no relief duty. The
design turned that into two stages. The lead approved it on 23 November ("Approved, plan it"), with questions 2 to 4 as written, and
then said **"Build it"** on 23 November 2026, so the plan was built straight away.

This is **stage 1, the send-out**: Approve and Send out as two presses, the times, quiet times, the AI picking at once, the morning
message and the late request, a head's own choice approved at once, the reminders of a relief told ahead, "Relief needed again", files
by link, "Who covers you", the blocked-bot alert and the reminders to set work. Stage 2 (the duty roster, days with no relief duty) is
not built.

Everything below that is not the lead's own words was decided on the lead's behalf, in the design ("my calls"), in the plan
("decisions") or during the build ("rulings", "choices"). The lead may change any of them; each says what it costs if it is wrong.

## The lead's words

As the lead wrote them on 23 November 2026, in the order given (the design's "What the lead said"):

1. "Any evening request, please do not disturb the team let them rest. In the morning it will ping the team with everything ,
   we need to set the timing and also , there will be two people on duty per week and we can switch the relief on and off ,
   that means certain days we do not need to be on relief duty example Fridays HBL day.."
2. "Usually the team will look at the relief the night before and in the morning for last min requests before and sometimes
   at 7 am. The idea is that the AI will allocate any time a request is in and at 7 am , the person in charge will approve the
   deployment and all notifications will be send out. any late request after 7am, the entire team will receive the late
   notification and any one of the member can approve. So on any day, one person is in charge and the other will be on
   standby , at any time, the relief team can adjust the allocation by the ai too before the notifications are out. The person
   in charge or relief team can send out ."
3. "The form should not say who will be told, the person requesting the relief will be informed which officer is covering
   the person when the person has acknowledged so that they can reach to them and all information will be given to them via
   telegram ."
4. Asked "May relief teachers be told the evening before, or never before the morning time?": "Never before morning".
5. "Any teacher who block, please alert relief team" (a teacher who blocks the school's Telegram bot).
6. Asked whether Approve and Send out are two presses before the morning time and one after: "Send out can be sent anytime but
   yes it is a seperate press". Asked what happens when a teacher asks for relief on a day relief duty is off (Friday HBL): "if
   any teacher sent, then it will be sent to the relief team as a FYI".
7. Asked what happens when Send out is pressed at 9 pm (hold until morning, or send at 9 pm): "yes first [hold] but we set a
   time for when it can send out earliest".
8. "However cut off time for sending out is 2 pm for the day's relief after that it is for the next day. There is a roster
   for every week".
9. Asked whether the same person is in charge all week: "They swap from day to day, suggest there is calendar function, ie we
   allocate the person every Friday, Monday... from when to when".
10. Asked who gets the morning message, the "not acknowledged" reports and the blocked-bot alert: "the alert that a teacher
    has blocked the bot.. for the team and the rest is for the duty personnel, lastly any teacher can access the relief page
    ( via the app) to see if they have been assigned relief for the day or see which relief they have been assigned to and the
    instructions in there. Telegram can send them the link and basic instructions but if there are more.. example files to
    download etc. they can download via the web app".
11. Asked "two stages, or one build?": "two stages".
12. Asked whether 2 pm is a hard stop for sending out today's relief or only the pings stop: "Pings stop, sending allowed".
13. On reading the draft: "For those with planned relief it is automatically approved".
14. Asked (a) whether that means: when a head plans an absence for a colleague and chooses the relief teacher, the choice
    counts as approved at once and the relief team does not have to approve it, while a lesson the head left without a teacher
    still goes to the AI and waits for the team; and (b) when that relief teacher is told (1 as soon as it is planned, in school
    hours; 2 on the morning of the day by itself; 3 approved by itself but the team still presses Send out): "Yes that reading is
    right, option 1 , the notification should be out 24 hours before and also on the morning itself. A teacher can also check
    anyways on the app before that. However if the assigned relief is sick on that day, then it falls back to normal relief
    assignment".
15. "For Absent Teacher who submit after 1500, they are reminded to set work by 1800 and 0700 if they have not done so. The
    absent teacher can submit through this portal or relief bot right, tell me what it looks like for both".

The design's four questions, as the lead answered them on 23 November:
1. The 2 pm cut-off: "Pings stop, sending allowed" (built: a request after the cut-off pings nobody and can still be sent out).
2. Who covers you: approved as written, on the relief teacher's acknowledgement (built).
3. The sentences about the reporting officer: approved as put to the lead: "{officer} will be told." is removed; the two "{officer} is
   not on Telegram: please tell them yourself." sentences stay (built).
4. The standby: approved as written, no extra message (stage 2; nothing to build here).

Two readings, in case another was meant: in item 3, "which officer is covering the person" is read as the relief teacher who covers
the lesson, and "the person requesting the relief" as the teacher who is away (when a head plans for a colleague, the colleague is
told, not the head).

## What stage 1 gives

### A day, in order

With the default times (each is a setting in Relief settings):

- **The evening before, from the cut-off (14:00) to the morning message.** A request comes in (the app's form, Plan relief or
  `/relief`) and is recorded. The AI picks for it at once, whatever its date. Nobody on the relief team is pinged. A team member who
  looks at **Today** (it opens on the next school day after the cut-off) may approve, change and press **Send out**: what is sent out
  is held, and the row says "Will be sent at 06:45". Nothing reaches a relief teacher. At 18:00 a teacher who is away tomorrow and
  has left a lesson without work gets "Please set work" on Telegram (made until 22:00 only: never in the night).
- **06:30, the morning message.** On a school day, each member of the relief team on Telegram gets one message with everything that
  waits for today: how many absences and lessons, how many wait for approval, are approved and not sent out, are sent out and wait
  for 06:45, have nobody free, or are sent out already, and who is away. When nothing is to cover, no message. A member of the team
  away the whole day today gets none (when the whole team is, all of them get it; answered by the lead on 24 November).
- **06:45, the earliest send-out.** Every relief of today sent out before now goes to its relief teacher, made from the record as it
  is now. A relief told before its day gets its morning reminder. From now until the cut-off, Send out sends at once.
- **07:00.** The second "Please set work" goes to a teacher who is away today and still has a lesson without work.
- **06:30 to 14:00, late requests.** A request for today that comes in after the morning message time reaches the whole team (but
  who sent it and the teacher who is away), once its picks are in, five minutes at most. Any of them approves and sends it out, on
  Today or on Telegram.
- **The "not yet acknowledged" report** (every 15 minutes from an hour before the first period) also lists each relief of today
  approved and not sent out whose lesson has not started, and no all clear goes while one is left.
- **During the day.** When a relief teacher acknowledges, the teacher who is away is told who covers that lesson. If an approved relief
  teacher is away themselves, the lesson goes back to open, the AI picks again, and the team hears "Relief needed again". If a teacher
  has blocked the bot, the team hears it.
- **14:00, the cut-off.** No more pings about today. A request after it for a lesson still to come today is picked and shown on Today
  with no ping; Today, open on the next school day, says "Today still has {n} to arrange: open Today."; a team member who looks can
  still approve and send it out, and it goes at once. A request to change and the "not
  yet acknowledged" report still reach the team for a lesson of today until it starts.
- **Weekends and holidays.** No morning message; a request then is in the next school day's morning message.
- **A relief for a later day** (a head's own choice when planning, or one the team sent out ahead) is told at once in school hours
  (else at the next 06:45 of a school day), again 24 hours before (moved earlier to the last 14:00 when that falls outside school
  hours), and again at 06:45 on the day itself, never two within 12 hours.

### Piece by piece

- **Task 1, the times and school hours** (84d1a08, d882d8a): five times in Relief settings (the morning message, the earliest
  send-out, the cut-off, and the two work reminders) in place of "Fill open lessons at"; one place in the code that answers every
  question of time (`relief/hours.py`), and the two hooks stage 2 will fill (`hours.duty_day`, `hours.on_duty`). A settings file of
  any wrong shape gives the defaults; it never stops a message.
- **Task 2, the AI picks at once** (55a8cdc, 03578ac): every open lesson is picked as soon as it is there, for any date, the nearest
  first. When the AI's guard (60 picks in 10 minutes) is full, a lesson of today is picked by the app's own order at once and a lesson
  of a later date waits for the next minute's run.
- **Task 3, Send out** (c4c8bbc): Approve no longer tells anyone. **Send out** on a row, and **Send out {n} approved** at the top of
  Today, mark the relief "sent out"; it goes at once in school hours, else at the next 06:45. A new approval (Change, a new pick
  approved) needs a new Send out. One History entry a press.
- **Task 4, "has reached its teacher" everywhere, and Send out on Telegram** (e898887): Reliefs I'm covering, the file download,
  Acknowledge and Request to change, Remind, the report and the all clear, and the weekly summary count a relief only once it is sent
  out and its time has come. The teacher who is away sees the relief teacher's name only once it is acknowledged ("Being arranged"
  before). On Telegram, after **Approve** of a new pick, the button **📤 Send out to {name}**.
- **Task 5, Today** (d07ceec): the "Approved, not sent out" counter, the row lines ("Approved · not sent out", "Will be sent at
  06:45"), a line for what is held, the opening on the next school day after the cut-off, and the second day button. It also did the
  lead's answer 13 of 23 November ("fix next time"): the 12 px of room under Today's buttons is kept only while a bot is connected.
- **Task 6, quiet times** (f7915d8): a relief teacher is messaged only in school hours, the team only between the morning time and
  the cut-off (with the exceptions in "Who gets what", below). A message held up past those hours is dropped and made again when
  they open, if still true. Remind outside a relief teacher's hours sends nothing and says from when it can.
- **Task 7, the morning message and the late request** (98acfc8): in place of the ping of 23 November ("Relief asked for today").
- **Task 8, a head's own choice** (79f9172, 9d849bb): in Plan relief for a colleague, a teacher chosen by a head (anyone who may plan
  relief) is approved and sent out at once by that head; the head may choose again until the lesson starts.
- **Task 9, the repeats** (9157c24, 0be822f): a relief told before its day is told again 24 hours before and on the morning.
- **Task 10, Relief needed again** (c1ac72f): an approved relief whose teacher is then away at its periods goes back to open, the AI
  picks again, and the team is told.
- **Task 11, files by link and Who covers you** (912e516, 93ac7ee): no file is sent on Telegram; the relief message says how many and
  has **Open in the app**, which stays after Acknowledge. The teacher who is away is told who covers each lesson once it is
  acknowledged. `/relief` no longer says "{officer} will be told."
- **Task 12, the blocked-bot alert** (ef0457b): the team is told when a teacher blocks the bot and which message they did not get;
  the History says "Telegram unlinked for {name}: the bot was blocked", by "The app".
- **Task 13, the work reminders** (a7beb15): "Please set work" to the teacher who is away, at 18:00 the evening before and 07:00 on the
  day, while a lesson of that day has no work.
- **The one fix round** (after the final review): the four commits listed under "Fixed in the one fix round", below.
- **Task 14, the finish**: the guides (`docs/DEPLOY.md`, `README.md`), corrections in the two notes before this one, these notes, the
  names check and every suite.

No new right, no new table, no new dependency, no new scheduler. Every message is still worked out by the app's check of what there
is to tell (once a minute and after each save), under a key of its own, and sent once.

## What changes for people on the first day it is live

- **Approve no longer tells the relief teacher. Send out does.** A team used to Approve must press Send out too (on the row, at the
  top of Today, or on Telegram after Approve). A relief approved and not sent out reaches nobody, and the morning message counts it
  as "approved, not sent out".
- **Reliefs approved before the deploy count as sent out** at their approval: a relief teacher already told of one is not told again,
  they stay in Reliefs I'm covering, and no reminder 24 hours before or on the morning is made of them. One approved and never told,
  because no bot was connected then, goes at the first school hours after connecting. A head's choice saved before the deploy
  (waiting for the team) still waits for the team.
- **The AI picks at once** for every open lesson, whatever its date. On the first minutes after the deploy the far dates are picked
  over some minutes (the guard). "Fill open lessons at" is gone from Relief settings; **Fill now** stays.
- **Files are in the app.** The relief message says "Files: {n}. Open the app to download them." and has **Open in the app**.
- **Nothing reaches a relief teacher before 06:45 or after 14:00** of a school day (after 14:00, only about a lesson of that day
  still to come). Remind outside those hours sends nothing and says from when it can.
- **A Send out pressed outside school hours** reads "Will be sent at 06:45" on Today, and the relief can still be changed until then.
- **After 14:00 Today opens on the next school day**, with the **Today** button to go back to today. When today still has lessons to
  come that are open, waiting for approval, or approved and not sent out, the line "Today still has {n} to arrange: open Today."
  is above the rows; nobody is pinged for them.
- **The "not yet acknowledged" report** lists, under "Approved, not sent out", each relief of today approved and not sent out, and
  no all clear goes while one is left. Once its lesson has started, still never sent out, the next report lists it once under
  "Started, never sent out", and the all clear counts it (24 November).
- **The team gets no ping in the evening.** The morning message at 06:30 replaces it. The ping "Relief asked for today" is replaced
  by the late request.
- **A head's own choice in Plan relief needs no Approve.** It is told to the relief teacher at once in school hours.
- **The teacher who is away** sees "Being arranged" until the relief teacher acknowledges, then the name, and is told it on
  Telegram (from 06:45 to before 18:00; an acknowledgement in the evening or the night at 06:45 the next morning, from 24 November).
  They also get "Please set work" at 18:00 and 07:00 when a lesson has no work (the evening one never after 22:00).
- **The team is told when a teacher blocks the bot.**
- **`/relief`** no longer ends with "{officer} will be told."
- If the bot is already connected, the first minute after the deploy sends "Covered" to the teacher who is away for each lesson
  acknowledged since the bot was connected and not yet over, and "Please set work" for each reminder to set work whose time it is
  then (a deploy between 18:00 and 22:00 sends tomorrow's evening ones): true, but all at once. On the live site no bot is connected.

## The settings and their defaults

In **Relief settings**, under **Times** (saved by whoever may save Relief settings: the timetable committee, its shared code and the
relief team):

| Setting (as the page says it) | Default | The help line under it |
|---|---|---|
| Morning message to the relief team at | 06:30 | "One message on Telegram with everything waiting for today. Not on weekends or holidays." |
| Earliest send-out to relief teachers | 06:45 | "Nothing reaches a relief teacher before this time of a school day, whenever Send out was pressed. School hours for relief teachers run from here to the cut-off." |
| Cut-off for the day's relief | 14:00 | "After it, nobody on the team is pinged about today, and the team works on the next school day. Until the next morning message, the team is not disturbed." |
| Remind the absent teacher to set work at {18:00} the evening before, and {07:00} on the day | 18:00 and 07:00 | "Only while a lesson of that day has no work. Any absence, asked or planned." |

Unchanged: "Remind the absent teacher to acknowledge and set work at {15:00} the school day before", "Report "not yet acknowledged"
every {15} minutes", "Weekly summary on {Fri} at {15:00}". Saving refuses a wrong order with "The morning message comes at or before
the earliest send-out, and both before the cut-off." "Fill open lessons at" is gone; its value stays in the file, unread.

## Who gets what

Every message, new or changed, by who gets it and when. "School hours" for a relief teacher: from the earliest send-out time to the
end of the cut-off's minute of a school day; after the cut-off, only about a lesson of that day still to come. "The team's window":
from the morning time to before the cut-off of a school day.

| Message | To | When | Outside its hours |
|---|---|---|---|
| The morning message (new) | each of the relief team on Telegram, but a member away the whole day today (unless the whole team is) | the morning time of a school day, when a lesson of today is to cover; once a day | made when the app is back, until the cut-off; never after it |
| The late request (new, in place of the ping) | each of the team but who sent it and the teacher who is away; never for an exam's or event's backup | an absence for today sent between the morning time and the cut-off, once its picks are in, or five minutes on | not made outside the team's window, and never later |
| Relief for you (changed: no files, Open in the app) | the relief teacher | once approved and sent out (or chosen by a head when planning), in school hours | held to the next start of school hours |
| Reminder of a relief (new) | the relief teacher | 24 hours before (else the last cut-off before) and the morning itself, for a relief told before its day; not within 12 hours of the last message of that relief | in school hours alone |
| Kept, moved, no longer needed, not happening, on again (unchanged words) | the relief teacher | at once | in school hours alone |
| Relief needed again (new) | each of the team but the relief teacher who is away and the teacher whose lesson it is | when an approved relief goes back to open because its teacher is away; with the new pick, or five minutes on | only in the team's window, never later; for a lesson of today found before the morning time, the morning message counts it |
| Who covers you (new) | the teacher who is away | when the relief teacher acknowledges, from the earliest send-out time to before the evening work time (06:45 to 18:00), any day; never for a backup | held to the next earliest send-out time, if still so then |
| Request to change, new pick (unchanged words) | each of the team | at once | in the team's window, or after the cut-off for a lesson of today until it starts; else the next morning time |
| The blocked-bot alert (new) | each of the team but the person | when a message to them is refused because they blocked the bot; one a person a day | the first team window after it was found; given up when it ends |
| Cancelled, the team's copy (unchanged words) | the team | at once | waits for the next morning time, if still true |
| Cancelled to the planner, the teacher who is away, the officer | as before | at once | any hour |
| Not yet acknowledged, all clear | the team | as before, from an hour before the first period; the report also lists what is approved and not sent out, and no all clear goes while one is left; one whose lesson has started is named once under "Started, never sent out" | as before |
| Relief planned for you, the reminder to acknowledge | the teacher who is away | as before | any hour |
| Please set work (new) | the teacher who is away; never for a backup | 18:00 the calendar day before (made until 22:00 of that evening only) and 07:00 on the day, while a lesson of that day needs cover, is still to come and has no work; not within 30 minutes of the request; each once | any hour, on purpose |
| The reporting officer's | the officer | at once | any hour |
| Weekly summary | the team | Friday 15:00 (setting) | its own setting |

Answers to a person's own press or typing go at once, at any hour.

## Copy the lead should see

Every new or changed sentence, exactly as the code has it. {..} stands for a name, a day, a lesson, a time or a number. Days read
"Tue 13 Oct", periods "P3–P4", times "09:20".

**On Telegram**

The morning message, to each of the relief team, with the button **Open relief today** (a line is left out when its number is 0):

> ☀️ Relief today · {day}
> {n} absences · {n} lessons to cover
> • {n} waiting for your approval
> • {n} approved, not sent out
> • {n} sent out: will go at {hh:mm}
> • {n} with nobody free: choose someone in the app
> • {n} sent out already
> Away: {name} ({whole day, or the periods}) · {name} ({...})

("1 absence", "1 lesson". Past eight people away: the first eight, then " · and {n} more".)

The late request, with **Open relief today**:

> 🆕 Late request for today · {absent}
> {whole day, or the periods}
> {n} lessons are waiting for your approval. Approve, then Send out.

("1 lesson is waiting for your approval. Approve, then Send out.")

The relief message, with **✅ Acknowledge**, **↩ Request to change** and a row **Open in the app** (to Reliefs I'm covering):

> 🔔 Relief for you · {day}
> {lesson} · {periods} · {start}–{end}
> Room {room}
> For {absent}
> Work from {absent}: {text}
> Link: {link}
> Files: {n}. Open the app to download them.

(Room, Link and Files only when there are; "No work set yet: look in Reliefs I'm covering." when there is no text, link or file.
After **Acknowledge** the line "✅ Acknowledged {hh:mm}." and the row **Open in the app** stay.)

The reminder of a relief told before its day, once it is acknowledged, with **Open in the app**:

> ⏰ Reminder · your relief on {day}
> {lesson} · {periods} · {start}–{end} · Room {room}
> For {absent}. The work is in the app.

(On the day itself the first line is "⏰ Reminder · your relief today, {day}". Not yet acknowledged: the relief message again, with
its buttons.)

Relief needed again, with **Open relief today**:

> 🔁 Relief needed again · {day}
> {lesson} · {periods} · for {absent}
> {name} was to cover it and is away then. A new pick is waiting for your approval. Approve, then Send out.

(With no new pick, the last sentence is "Nobody else is free then: choose someone in the app.")

Who covers you, to the teacher who is away:

> ✅ Covered · {day}
> {lesson} · {periods} ({start})
> {name} has acknowledged. You can reach them if you need to.

The blocked-bot alert, with **Open relief today**:

> ⚠️ {name} has blocked the bot and is now unlinked.
> They did not get: {what}.
> Please tell them yourself.

({what} is "Relief for you · {lesson} {periods} on {day}" for a relief or its reminder, else the message's kind as Relief settings lists
it, else "Message".)

Please set work, with **Open in the app** (to My absences):

> ✏️ Please set work · {day}
> {n} lessons have no work yet: {lesson} {periods}, {lesson} {periods}.
> Set it in the app, in My absences. Your relief teacher sees it there.

("1 lesson has no work yet: ...". Past five lessons: the first five, then " and {n} more".)

The "not yet acknowledged" report gains a block of its own, after "Not yet acknowledged" and before "Started without
acknowledgement", one line a relief of today approved and not sent out whose lesson has not started:

> Approved, not sent out ({n}):
> • {name} · {lesson} {periods} ({start})

Since 24 November it gains one more block, after "Started without acknowledgement", one line a relief of today approved and never
sent out whose lesson has started, said once:

> Started, never sent out:
> • {name} · {lesson} {periods} ({start})

and the all clear then says "✅ {hh:mm} · No reliefs are waiting now: {k} started without acknowledgement, {m} never sent out."
(each part only when it is not 0).

On a request to change, after **Approve {name}**: "✅ Approved: {name}, {hh:mm}." and the button **📤 Send out to {short name}**;
after it: "📤 Sent out: {name}, {hh:mm}." or "📤 Sent out: {name}, {hh:mm}. Will be sent at {hh:mm}." when it is held. When the
relief was approved again or changed since, the press answers "The pick has changed since you looked: look again before approving."
and the button goes.

`/relief`, its last message: "✅ Sent to the relief team: {n}, {work}." and, when the reporting officer is not on Telegram, " {officer}
is not on Telegram: please tell them yourself." ("{officer} will be told." is gone.)

**Remind them again** (on the report) and **Remind** (on Today), outside the relief teacher's school hours: "Not sent outside school
hours: remind them from {hh:mm}." ("from Tue 06:45" when that is another day).

**In the app**

Today:
- Buttons: **Send out** on an approved row; **Send out {n} approved** at the top ("Send out approved" at 0, off).
- The counter "Approved, not sent out".
- A row: "Approved" with "Approved · not sent out", or "Will be sent at {hh:mm}" while held; a head's own choice adds "Planned by
  {head} · " before the row's line; a waiting row asked after the cut-off: "Asked at {hh:mm}, after the cut-off: nobody was pinged";
  a lesson back to open: "{name} was to cover it and is away then".
- Above the rows: "1 relief sent out: it will be sent at {hh:mm} on {day}. You can still change it until then." ("{n} reliefs sent
  out: they will be sent at {hh:mm} on {day}. You can still change them until then.") and, on the next school day's view past the
  cut-off: "Past the cut-off ({14:00}). Nobody on the team is pinged until the morning message at {06:30}. What you send out now is
  sent at {06:45} on {day}."; and, on that view, while today still has lessons to come that are open, waiting for approval, or
  approved and not sent out: "Today still has {n} to arrange: open Today." ("open Today" shows today).
- After a press: "{name} approved: press Send out to tell them."; "{name} chosen and approved: press Send out to tell them.";
  "Sent out."; "Sent out {n} reliefs for {day}." ("Sent out 1 relief for {day}.") with " They will be sent at {hh:mm}." when held;
  a row Send out skipped: "{lesson}, {name}: {name} is no longer free then: change it".
- Refusals: "This relief is sent out already."; "This relief is not approved yet."
- The second day button: "Tomorrow" when the next school day is tomorrow, else the day ("Mon 19 Oct").
- At the foot: "Nothing reaches a relief teacher until the relief team approves it and sends it out, or a head chooses them when
  planning."

My absences (the teacher who is away): "Being arranged" in place of the relief teacher's name until it is acknowledged.

Plan relief: "This lesson has started: ask the relief team to change it." (choosing again once the lesson has started); "This
lesson's relief is approved already: ask the relief team to change it." (as before, now also for a head's choice on a lesson the
teacher's own absence took over).

Relief settings: the three times and their help lines, and the work reminders (above); the sentence that is always true now reads
"Always true, whatever the rules say: only teachers free at that time · never someone away that day · nothing reaches a relief
teacher until the relief team approves it and sends it out, or a head chooses them when planning."; the Telegram card's list of messages that
could not be sent names seven new kinds: "Late request for today", "Morning message", "Reminder of a relief", "Relief needed again",
"Who covers you", "Bot blocked alert", "Please set work" ("New request for today" is gone).

History: "Sent out {n} reliefs for {day}" ("Sent out 1 relief for {day}"); "sent out {name}'s relief for {lesson} {periods} on
{day}"; "Telegram unlinked for {name}: the bot was blocked", by "The app".

## Decisions taken in the plan (the lead may change any), as built

1. **The "sent out" mark.** A relief approved before the deploy (with no mark at all) counts as sent out at its approval, so nobody is
   messaged again and nothing leaves Reliefs I'm covering. Every approval from now on needs a Send out. If wrong: a record edited by
   hand without the mark reads as sent out.
2. **School hours for relief teachers include the cut-off minute** (06:45 to 14:00:59); the team's window ends before it (06:30 to
   13:59:59). If wrong: a relief for tomorrow sent out at 14:00 exactly goes at once.
3. **On the lesson's own date its teacher's hours open at 06:45 whatever the calendar says**, and a held relief never waits past its
   lesson's own 06:45. Reason: a day the calendar stops knowing (made a holiday) must not hold a relief for ever. If wrong: none seen.
4. **The AI's guard** (60 picks in 10 minutes for the whole app), **as built after ruling 2a**: when it is full, a lesson of today is
   picked by the app's own order at once, as before; only a lesson of a later date waits for the next minute's run, nearest dates
   first. Without a model the app's order is used, as before. If wrong: after the deploy, far dates are picked over some minutes;
   on a morning with more than 60 picks in ten minutes some of today's picks are the app's order, not the AI's.
5. **Send out is checked like Approve**: it takes the name and the approval the page showed, refuses when either changed ("The pick
   has changed since you looked: look again before approving."), checks the teacher is still free, and "Send out {n} approved"
   sends exactly the rows the page showed. A second press: "This relief is sent out already." (also once acknowledged or asked to
   change). If wrong: copy.
6. **The copy after a press** (not in the design): "{name} approved: press Send out to tell them.", "{name} chosen and approved:
   press Send out to tell them.", "Sent out.", "Sent out {n} reliefs for {day}." with " They will be sent at {hh:mm}." when held;
   the top button reads "Send out approved" at 0. If wrong: copy.
7. **A head's own choice is approved and sent out only on a planned absence** (Plan relief for a colleague, and, by ruling 8b, an
   exam's or event's backup chosen by a head). A head's own request that names a relief teacher (possible through the app's
   interface alone) waits for the team. A head's choice saved before the deploy stays waiting. If wrong: one condition each.
8. **The head may choose again while the relief is still their own choice**, until the lesson starts ("This lesson has started: ask
   the relief team to change it."); once the team has changed it, it is the team's. By ruling 8a, only on a planned absence. If
   wrong: one condition; a head asks the team instead.
9. **The repeats count every message of the relief** (its first, a Remind, the other repeat, one still queued too) for the 12-hour
   rule; a repeat missed while the app was down is made until the next one's moment (the morning one: until the lesson starts), then
   given up; none is made of a relief from before the deploy. If wrong: a missed repeat is not sent late.
10. **A repeat's form is fixed when it is made** (the short line when acknowledged, the relief again when not); if that changes before
    it goes, it is dropped and made again in the right form. If wrong: none seen.
11. **Today's line for a head's choice** is "Planned by {head} · " and the row's own line ("Sent 06:45" after the morning repeat). The
    mockup's "· reminded today 06:45" is not built. If wrong: one line of copy.
12. **The morning message's lines**, in this order, each left out at 0: waiting for your approval (a pick, or a request to change with
    a new pick); approved, not sent out; sent out: will go at {06:45}; with nobody free; sent out already. Only lessons that need
    relief count. It is made from the records that can be read: a damaged file is logged and does not stop it. It is claimed even when
    there is nothing to cover (then nothing is sent). If wrong: a damaged file's lessons are missing from the counts.
13. **"Away:" past eight people**: the first eight, then " · and {n} more", ordered by each absence's first lesson to cover. If wrong:
    copy.
14. **The late request is made only between the morning time and the cut-off**; one whose picks come after the cut-off pings nobody.
    A ping of the kind before still queued at the deploy is dropped. If wrong: a request sent in the last five minutes before the
    cut-off may ping nobody (it is on Today).
15. **A request to change goes to the team at once in the team's window, or after the cut-off for a lesson of today until it starts;
    otherwise at the next morning time.** If wrong: one asked at 05:00 for today waits until 06:30.
16. **Today opens on the next school day past the cut-off of a school day (14:00 itself counts as past), and on a day that is not a
    school day**; the second day button reads "Tomorrow" or the day. The past-the-cut-off line shows on the next school day's view
    alone. If wrong: layout.
17. **On Telegram the Send out button names the person as Approve does** ("📤 Send out to {short name}"), and the line after it is
    "📤 Sent out: {name}, {hh:mm}." (with " Will be sent at {hh:mm}." when held). If wrong: copy.
18. **The blocked-bot alert** is kept as a row in the app's Telegram file (`alert:{name}:{date}`), made within the first team window
    after the block was found and then given up, one a person a day. "They did not get:" names a relief or its reminder by its lesson,
    any other by its label in Relief settings, else "Message". It has **Open relief today**. If wrong: a block found on Friday
    evening is said on Monday at 06:30, not later.
19. **The work reminders' list**: "A, B, C, D, E and {n} more"; never for a backup; only for moments since the bot was connected. If
    wrong: copy.
20. **Relief needed again** waits up to five minutes for the new pick, as the late request does, and is not made for a lesson of today
    found before that day's morning time (the morning message counts it). A request to change whose teacher is away goes back to
    open too. If wrong: up to five minutes late.
21. **The weekly summary's "on time"** stays as the code measured it (acknowledged by the lesson's start); the design (call 28) said
    "from when the relief message went". What changed: a relief counts once it has reached its teacher, and "planned ahead / arranged
    on the day" goes by when it reached them. If wrong: one field to read.
22. **Question 3.** `/relief`'s "{officer} will be told." is removed; both "is not on Telegram: please tell them yourself." sentences
    stay, as the lead approved. If wrong: one sentence.
23. **The morning message's help line says "Not on weekends or holidays."** ("or days with no relief duty" is stage 2's). "Fill open
    lessons at" is dropped when the settings are read and kept in the file when they are saved. If wrong: copy.
24. **The absent teacher's own view says "Being arranged"** for a relief approved and not yet acknowledged (also while the relief
    teacher has asked to change). If wrong: one condition.
25. **The kinds' labels are one list** (`relief/words.py`), read by Relief settings and the alert alike. New labels: "Late request for
    today", "Morning message", "Reminder of a relief", "Relief needed again", "Who covers you", "Bot blocked alert", "Please set work";
    "New request for today" goes. If wrong: copy.

## Rulings made during the build ("if wrong" is the cost)

Before the build (a read-only scan of the plan against the code found fifteen places where the plan's text would have tripped a
builder; each was ruled, none changes what the lead approved):
- PF1, PF2, PF6, PF8, PF10, PF11, PF14: tests the plan wrote that could not work as written, or old tests that had to follow
  (an exact list of message kinds, Today's whole answer), were corrected for the builders. If wrong: a small rework.
- PF3 was a fault in the code the plan described, not a test that could not work: the plan's `cover.chose` would have written a
  head's pick into the History a second time (the app already writes it when the absence is saved). If wrong: none.
- PF4. Remind outside a relief teacher's school hours must not be lost silently: it sends nothing and says "Not sent outside school
  hours: remind them from {at}." (new copy for the lead). If wrong: copy.
- PF5. Today offers Remind only on a relief that has been sent out. If wrong: none seen.
- PF7. A relief acknowledged or asked to change keeps its "told" line (it never reads as not sent out). If wrong: none seen.
- PF9, PF12: two traps in the code (a name used twice in Today's script; an import loop) were named for the builders. If wrong: none.
- PF13. The Plan page shows a head's current choice while it is still theirs, not only while it waits. If wrong: a head would not see
  whom they chose.
- PF15. Every commit ends with the same attribution line. If wrong: none.

During the build:
- 1a (Task 1). The times never raise for any shape of settings or calendar (they fall back to the defaults, or "not a school day"),
  and take a date in either form. A bad settings file would otherwise have stopped every relief message. If wrong: a few lines.
- 2a (Task 2). When the AI's guard is full, a lesson of today is picked by the app's own order at once, as before; only later dates
  wait. This narrows the design's call 29 and the plan's decision 4, to keep the 20 November design's rule that "at 7 am the page
  waits on the AI and the team cannot act" must never happen. If wrong: on a morning with more than 60 picks in ten minutes, some of
  today's picks are the app's order.
- 6a (Task 6). Every kind of message is listed either with its hours or as "any hour", and a test fails for a kind in neither. A
  forgotten one would have been sent at night. If wrong: one line a kind.
- 8a (Task 8). A head may choose again only on a planned absence. The review proved a path where a head's choice on an exam backup,
  taken over by the teacher's own absence, could be changed by the head to a new name that kept the old approval and send-out: a
  relief teacher told with nobody having approved them. Now no change by a head can leave an old approval, send-out,
  acknowledgement or request to change on a relief it replaces. If wrong: a head cannot re-choose on a backup that a teacher's own
  absence took over (the team changes it on Today).
- 8b (Task 8). A head's own choice on an exam's or event's backup is approved and sent out at once, like any planned absence: it is a
  head's deliberate choice, the lead's rule. If wrong: one condition (an open question below).
- 9a (Task 9). A failed repeat is named "Reminder of a relief" in Relief settings; three tests added. Two points stand as built, for
  the lead: the 12-hour rule counts a message still queued as well as one that went; across a break, "24 hours before" is the last
  school day before the lesson, at the cut-off. If wrong: copy, and one early return.
- 11a (Task 11). Acknowledge on Telegram keeps the row **Open in the app** (the text still says the files are in the app), and a
  failure to keep a message's buttons never loses the saved approval's History entry. If wrong: small.

In the one fix round (after the final review):
- F1. The team's report gains the block "Approved, not sent out", and no all clear goes while one is left. A relief whose lesson
  has started leaves the block. If wrong: one more block in the morning.
- F2. After the cut-off, the next school day's view says how many of today are still to arrange, with a way back to today. It is a
  line on the page, not a ping. If wrong: a late request after 2 pm is seen only by someone who opens the app.
- F5. The evening reminder to set work is made only until 22:00, a fixed hour and not a setting. If wrong: one constant.
- F6. A **📤 Send out to {name}** button on Telegram whose relief was approved again or changed since goes when pressed: it carries
  the approval it was made for, so it can never succeed. If wrong: a team member presses Send out on Today instead.
- F7. "Relief needed again" leaves out the relief teacher who is away and the teacher whose lesson it is, when either is on the
  relief team, as the late request does. If wrong: one condition; they see it on Today.

The builders' own choices that a person would meet, accepted by the reviews:
- Task 1: a held relief looks 60 days ahead for a school day, then falls back to its lesson's own 06:45.
- Task 3: a second Send out answers "This relief is sent out already." also once acknowledged or asked to change.
- Task 4: while the relief teacher has asked to change, the teacher who is away sees no name.
- Task 5: Today opens on the next school day from 14:00 itself; the line for what is held gives the earliest time.
- Task 6: a message held past its reader's hours is dropped and made again in the next hours under the same key, if still true; a
  Remind copy held past the cut-off is dropped and not made again (the team may press Remind again).
- Task 7: the morning message counts only lessons marked as needing relief, and names who is away by their first lesson to cover.
- Task 8: choosing the teacher who is already the head's choice changes nothing and writes no History entry; another head cannot
  change a head's approved choice in Plan relief (the team changes it on Today).
- Task 9: no repeat while the teacher has asked to change; a teacher who never got the first message on Telegram gets no repeats.
- Task 10: a relief teacher on an exam or event duty then (their own lessons have a backup) counts as away; "Nobody else is free then" goes once, five minutes on.
- Task 11: a teacher who is away and links later still gets "Who covers you" if the acknowledgement came after the bot was connected
  and the lesson is not over. "Who covers you" has no buttons.
- Task 12: two blocks in a day: two History lines, one alert.
- Task 13: a link alone or a file alone counts as work; a lesson with no relief teacher yet counts; a lesson not needed or stopped by
  an exam does not; an 18:00 reminder still queued at 07:00 is dropped (the 07:00 one goes).

## Known limits

The times (Task 1): a settings file that cannot be read gives the defaults with no line in the log; with no school day found, nothing
is pinged (it fails closed).

Picks (Task 2): after the deploy, picks for far dates appear over some minutes. A pick made days ahead does not see later absences that
would have spread the load better; the team sees the load and may change it.

Send out (Tasks 3, 4):
- Two people may press Send out on the same rows in the same second: one is refused "This relief is sent out already.".
- There is no button to take back a Send out that is held; Change or cancel does it (design call 6).

Today (Task 5):
- A page left open and idle past the cut-off keeps its old top lines and day buttons until Refresh or an action (no action can go to
  the wrong date); a quiet re-read with the same rows does not draw the top lines again.
- Held reliefs are in no counter tile; the line above the rows says them.
- With no calendar, or a break over 30 days, the second day button is gone.
- A request for today after the cut-off pings nobody; the next school day's view says "Today still has {n} to arrange: open Today."
  (fixed in the fix round).
- No server test covers Today's opening day on a holiday, with no calendar, or at 00:01.

Quiet times (Task 6):
- A Remind copy held up past the cut-off (an outage) is dropped and not made again.
- While a relief's message waits for school hours (overnight), its last state reads "dropped" and Today reads "Not sent yet" with no
  time (left as it is, below).

The morning message and the late request (Task 7):
- Its counts miss a damaged file's lessons; when one lesson of an absence cannot be read, the whole absence is left out (logged).
- A team member who is away the whole day today does not get it (answered on 24 November); one away for some periods does.
- A late request whose picks come after the cut-off pings nobody; one sent in the last five minutes before the cut-off may not ping.
- On the day of the deploy, an absence already pinged by the ping before can be pinged once more as a late request (only if that ping
  ran on the live site with a bot connected; left as it is, below).

A head's own choice (Task 8):
- A head cannot re-choose on a backup that a teacher's own absence took over; the team changes it on Today.
- A Today row on such a taken-over lesson can still read "Planned by {head}".
- Choosing the same teacher again right after someone else's save writes a History entry (harmless).
- The Plan page's script has no page test of its own; the server's rule is tested.

The repeats (Task 9):
- A missed repeat is not sent late.
- Remind and the app's check can each queue a message of the same relief in the same second: one extra message, never at night.
- If the first message failed and only a Remind copy reached the teacher, no repeats are made.
- For a Monday lesson after a week's break, "24 hours before" is the Friday before the break, at the cut-off.

Relief needed again (Task 10):
- A relief teacher who goes away after the cut-off, for a lesson later the same day, makes no "Relief needed again" (no ping after the
  cut-off, the lead's rule); the lesson is open again and is counted in "Today still has {n} to arrange".
- If the relief teacher who acknowledged is then found away, the teacher who is away sees "Being arranged" again but is not told on
  Telegram until the new relief teacher acknowledges.
- "Nobody else is free then" also shows when the lesson is open for another reason (the AI's guard holding a later date).
- If the absence is cancelled and the same teacher is picked again, the message still names them as away.
- Only "away" sends a relief back to open; a changed timetable or a duty is marked on Today for a person to change, as before.

Files and Who covers you (Task 11):
- Work set after the relief teacher was told (06:45) is not sent to them on Telegram; it shows in Reliefs I'm covering (the lead's
  call 47).
- "Who covers you" goes from 06:45 to before 18:00, any day; an acknowledgement in the evening or the night is told at 06:45 the
  next morning (answered on 24 November). An acknowledgement at 18:30 is told the next morning too.
- If the bot is connected before the deploy, the first minute after it sends "Covered" for every lesson acknowledged since and not
  over, at once.

The report (fix round):
- A relief approved and not sent out now brings the "not yet acknowledged" report at its first time, an hour before the first
  period. Where the first period starts before 07:30, that report reaches the team before the 06:30 morning message.
- A relief approved and never sent out whose lesson has started is listed once under "Started, never sent out" (open question 11,
  answered on 24 November).

The blocked-bot alert (Task 12):
- A block on Friday evening is told on Monday at 06:30.
- An alert is lost when the app, or Telegram, is down for the whole first window after the block (Today's "not on Telegram" and the
  History line remain). One held up by an outage from 13:59 to the next morning goes a day late, still in the team's hours.
- A Connect under a different bot without Disconnect unlinks everybody, as before; each then gets a History line.

The work reminders (Task 13):
- After an outage, the 07:00 reminder still goes while any lesson of that date is left; the 18:00 one is not made after 22:00.
- A text of spaces counts as work.

Small things in the code (for whoever maintains it; nothing a person sees): the guard's `held` is an upper bound; one info log line a
held run; the repeats and the Relief needed again check are worked out every minute (one more read of every record); the alert rows
are never pruned (a few hundred a year at most); `_covering_row` does not strip a trailing slash from the address; three tests are a
little looser than before (one changed assert in Task 11, two loops in Task 13).

## Fixed in the one fix round

After the final review of the whole branch, in four commits (three of code, then these documents):

- F1. The team's "not yet acknowledged" report lists each relief of today that is approved and not sent out, under "Approved, not
  sent out", and no all clear goes while one is left. It answers the review's finding that the all clear could say the day was done
  while a relief was approved and never sent out, so its teacher was never told.
- F2. After the cut-off, the next school day's view on Today says "Today still has {n} to arrange: open Today." It answers the
  finding that a request for today after 2 pm, or a relief teacher found away after it, was hidden behind the Today button.
- F3. Relief settings' sentence that is always true now names Send out and a head's own choice. It answers the finding that it still
  said "the relief team approves before anything is sent", which was untrue. No other sentence in the code or the pages said that
  approval alone sends or tells.
- F5. The evening "Please set work" is made only until 22:00. It answers the finding that after an outage it could go in the middle
  of the night to a teacher who is off sick.
- F6. On Telegram, a **📤 Send out to {name}** button whose relief was approved again or changed since goes when it is pressed. It
  answers the finding (Task 4) that such a button could never succeed and stayed.
- F7. "Relief needed again" leaves out the relief teacher who is away and the teacher whose lesson it is. It answers the finding
  (Task 10) that it went to them when they were on the relief team, where the late request leaves them out.

## Left as it is

- A relief whose message waits for school hours reads "Not sent yet" with no time on Today. Reason: it is a word on the page
  only and bounded: the message is made again and goes at the start of the next school hours, and the line is right once it has gone.
- On the day of the deploy, an absence already pinged under the old kind of ping could be pinged again as a late request. Reason:
  only if a bot were connected before this goes live, and none is.
- The exam schedule's page names a backup's relief teacher to the person in charge of the schedule once it is approved (never to the
  teacher who is away). Reason: it shows only to that person, so the
  teacher who is away still sees the name only once it is acknowledged.

## Open questions for the lead

1. A team member who is away today still gets the morning message (stage 2's roster will narrow it to the two on duty). Leave out a
   team member who is away?
   Answered on 24 November: yes. Built: a member away the whole day today (not for some periods) gets no morning message; when
   the whole team is away, all of them get it.
2. "Who covers you" goes when the relief teacher acknowledges, at whatever hour (an acknowledgement at 21:00 sends it at 21:00, to the
   teacher who is away). Hold it to the morning?
   Answered on 24 November: hold. Built: it goes from 06:45 to before 18:00 on any day; one acknowledged outside that is told at
   06:45 the next morning, if it is still so then.
3. A head's own choice on an exam's or event's backup is approved and sent out at once, like any planned absence (ruling 8b). Or
   should a backup always wait for the team?
4. Across a break, "24 hours before" is the last school day before the lesson, at the cut-off (a Monday lesson after a week's break:
   the Friday before the break). Or no reminder that early?
5. The twelve-hour rule counts a message still queued as well as one that went. Keep?
6. A blocked-bot alert is lost when the app, or Telegram, is down for the whole first window after the block. Enough, with Today's
   "not on Telegram" and the History line?
7. If the bot is connected on the live site before this is deployed, the first minute after the deploy sends "Covered" for every
   lesson acknowledged since and not over, and "Please set work" for every reminder to set work whose time it is then, at once.
   Acceptable, or should that first burst be left out?
8. Held reliefs are in no counter on Today (the line above the rows says them). Wanted as a tile?
9. "Relief needed again" now goes as the late request does: not to the teacher who is away, nor to the relief teacher who is away
   (ruled in the fix round, F7). Keep?
10. A relief teacher who goes away after the cut-off for a lesson later that day makes no "Relief needed again"; Today's next-day
    view says "Today still has {n} to arrange: open Today." (ruled in the fix round, F2: no ping after the cut-off, by "Pings stop,
    sending allowed"). Should a message go then after all?
11. A relief approved and never sent out leaves the report once its lesson has started, with no line anywhere. Should the report
    gain a line "Started, never sent out", as it has "Started without acknowledgement"?
    Answered on 24 November: yes. Built: the next report lists it once under "Started, never sent out", and the all clear says
    how many were never sent out.
12. After the cut-off, the line "Today still has {n} to arrange" counts lessons that are open, waiting for approval, or approved
    and not sent out. It does not count a request to change for a lesson of today (that request still reaches the team on
    Telegram). Should it be counted too?

Answered on 24 November: 1 yes, 2 hold, 11 yes; the others kept as they are. The earlier list's answer 6 (the Next button on Telegram) is confirmed.

The design's own points the lead may change (each is built as the design says):
- Item 3's two readings: the relief teacher (not the reporting officer) is "the officer covering"; the teacher who is away (not a head
  who planned for them) is told.
- Call 3: a relief the team sends out before its day is told as a head's choice is (at once, 24 hours before, on the morning): up to
  three messages for one relief.
- Call 9: messages to the teacher who is away and the reporting officer go at once at any hour, so a planner at 22:00 can cause one.
- Call 10: the weekly summary stays Friday 15:00, after the cut-off (set it to 13:00 to keep it inside).
- Call 17: the first "not yet acknowledged" report, an hour before the first period, may list nearly everything sent at 06:45.
- Call 27: the cut-off does not stop the report or a request to change for a relief of today until its lesson starts.
- Call 30: "a head" is anyone who may plan relief for a colleague: school leaders, heads of department, subject heads and the relief
  team.
- Call 42: every absence with a lesson missing work gets the reminders still to come, not only one sent after 15:00.
- Call 46: work cannot be added on Telegram after Send; the reminder points to the app.
- Decision 21: the weekly summary's "on time" is still measured as acknowledged by the lesson's start.

## Before the first real morning

On the service the school uses, with the bot connected, and one or two people who know it is a trial. Use lessons still to come and
cancel the trial absences afterwards (the team and any reporting officer named get those messages). The list spans several days,
in the order of a day:

1. Deploy. Nothing is to be done. Two warnings for the day of the deploy, both only if a bot is already connected (on the live site
   none is): the first minute between 06:45 and 18:00 sends "Covered" for each lesson acknowledged since the bot was connected and not yet over, and "Please
   set work" for each reminder whose time it is then; and an absence already pinged under the old kind of ping can be pinged once
   more as a late request. Open **Relief settings**: the times show 06:30, 06:45, 14:00, and 18:00 and 07:00; save once.
   Look at **Today**: reliefs approved before the deploy read as told, and nobody gets a message about them.
2. After 06:45 and before 14:00, plan relief for a trial colleague for tomorrow in **Plan relief for a colleague**, choosing a trial relief teacher:
   the relief teacher's phone gets "Relief for you" at once, with **Open in the app**; Today shows "Planned by {head}". The colleague's
   My absences says "Being arranged".
3. Plan another for a lesson three school days ahead: told at once; then 24 hours before; then at 06:45 on the day.
4. After 14:00, send a trial request for tomorrow: nobody on the team is pinged; Today opens on tomorrow with the past-the-cut-off
   line; the AI has picked. Approve: "{name} approved: press Send out to tell them." Press **Send out**: "Will be sent at 06:45", the
   held line above the rows, and nothing on the relief teacher's phone. Change one held relief, and cancel another.
5. Send a trial request for tomorrow at 15:00 with one lesson left without work: at 18:00 the trial teacher gets "Please set work".
6. 06:30: the morning message on the team's phones. Its counts match Today (waiting, approved not sent out, held, nobody free, sent
   already) and the Away line is right.
7. Before 06:45 press **Remind** on a relief its teacher was told of yesterday: "Not sent outside school hours: remind them from 06:45."
8. 06:45: the held reliefs reach their teachers as they are now (the changed one to its new teacher, the cancelled one to nobody), each
   once. The planned relief of step 2 gets its morning reminder.
9. 07:00: "Please set work" again if work is still missing; set the work and see no third message.
10. A relief teacher acknowledges before 18:00: the teacher who is away gets "Covered" with the name, and My absences shows the name.
    One acknowledged after 18:00 shows the name in My absences at once, and "Covered" comes at 06:45 the next morning.
11. After 06:30, send a late trial request for today: the team (but the sender and the teacher who is away) get "Late request for
    today" within five minutes. On Telegram, press **Approve**, then **📤 Send out to {name}**: it goes at once.
12. Mark a trial relief teacher as away for a lesson they were to cover: the lesson goes back to open, the AI picks again, the team gets
    "Relief needed again", and the relief teacher gets "No longer needed".
13. Have a trial person block the bot, then send them a relief: they are unlinked, the team gets the alert (in the team's window), and
    the History has the line by "The app".
14. After 14:00, a request to change for an afternoon lesson of today still reaches the team. A new request for today after 14:00
    pings nobody; Today, open on the next school day, says "Today still has 1 to arrange: open Today.", and Send out on today's view
    still sends it at once. Approve one relief of today and do not send it out: the next "not yet acknowledged" report lists it under
    "Approved, not sent out", and no all clear comes while it is left.
15. A relief with files: the message says "Files: {n}. Open the app to download them.", and the files download in Reliefs I'm covering.
16. Railway's logs hold the kinds of failures alone; no name, text, chat or token.
17. If anything is wrong, **Disconnect** turns all messages off and relief goes on in the app. To roll back, see `../../DEPLOY.md`
    ("Rolling back"). Worked out from the older code, not tried. Roll back between the earliest send-out time and the cut-off of a
    school day, because every approved relief, sent out or not, is then told at once. Messages of the new kinds still queued go when
    they are sent; a Relief settings save made while rolled back drops the new times. Going forward again, a relief the older
    version told reads "Approved · not sent out" until someone presses Send out (that press sends no second message), and a
    takeover done by the older version drops the mark, so a cover it moved counts as sent out. A relief on an absence asked for
    while rolled back has no mark at all, so it too counts as sent out at its approval, as any relief from before this version.

## What stage 2 will add, and what stage 1 leaves ready

Stage 2, the duty roster (its own plan, on the lead's word): a **Duty roster** card in Relief settings with weekly lines ("Every
{weekday}: in charge {name}, standby {name}, from {date} to {date}"), one-day changes, "No relief duty" lines (Friday HBL) and a This
week strip; on a day with no relief duty no picks, no morning message, no report, and an FYI to the team; on a day with a line, the
morning message, the reports and the all clear go to the person in charge and the standby alone, with a first line "You are in
charge today. Standby: {name}." or "You are on standby today. In charge: {name}.".

What stage 1 leaves ready for it: every question "is the team on duty today" goes through `hours.duty_day` (stage 1: every school day),
and every question "who is on duty" through `hours.on_duty` (stage 1: the whole team). The morning message, the late request, the
team's window and the alert already ask these two, so stage 2 fills them in and adds the card; the help line "Not on weekends or
holidays." then gains "or days with no relief duty".

## Checks

- During the build, after each task, the relief suites one at a time (`test_relief_telegram`, `test_relief_team`,
  `test_relief_requests`, `test_relief`, `test_exams_relief`, `test_routes`, `smoke`, and the page tests the task touched), all
  passing:
  - Task 1: telegram 337, team 74, requests 59, relief 44, exams_relief 102, routes 20, smoke 103, relief_settings 24; fix round:
    telegram 339, relief 45.
  - Task 2: team 76; fix round: team 79 (the rest as before).
  - Task 3: telegram 346, relief_today 44.
  - Task 4: telegram 357, relief_telegram 39, relief_today 44, relief_inbox 3, relief_summary 11, relief_settings 24.
  - Task 5: team 80, relief_today 56, and all 24 page tests.
  - Task 6: telegram 367. Task 7: telegram 375.
  - Task 8: telegram 382, relief_today 57, relief_telegram 39; fix round: telegram 386.
  - Task 9: telegram 397; fix round: telegram 401.
  - Task 10: telegram 407, team 81, relief_today 58.
  - Task 11: telegram 414; fix round: telegram 416.
  - Task 12: telegram 422. Task 13: telegram 429.
  - requests 59, exams_relief 102, routes 20 and smoke 103 throughout (relief 45 from Task 1's fix round on).
- Faults put in on purpose, one at a time, each caught (or a test added until it was): Task 1, 25 (24 caught, one a change that
  changed nothing), then 13 in its fix round; Task 2, 3, then 3; Task 3, 26 (4 after tests were added); Task 4, 26 (25 caught: one
  rule is read by nothing yet); Task 5, 17 (3 after tests were added); Task 6, 17; Task 7, 29 (3 after tests were added); Task 8, 12,
  then 4 more in its fix round with the first ones again; Task 9, 9, then 4; Task 10, 12; Task 11, 14, then 5; Task 12, 11; Task 13,
  13.
- Every review: Tasks 1, 2, 8, 9 and 11 had a fix round (rulings 1a, 2a, 8a, 9a, 11a), each re-reviewed clean; the others passed at
  their first review with no Critical or Important finding.
- Names check, counts only, on the lines added since d2dfbaf and the commit messages, without opening any of the school's files: the
  school's full name 0; bot token and model key shapes 0 (one line matches, the plan's own check command, which names the shapes it
  counts); em-dashes 0 in the commit messages and 0 in the lines this task added to the documents (one line of the plan matches,
  the same check command, which names the character it counts; none is used as a dash).
- The one fix round: each rule broken on purpose, one at a time, and each caught: 3 for the report, 5 and 4 for the line after the
  cut-off (server and page), 3 for the evening reminder, 1 for the Send out button, 2 for "Relief needed again". Then each suite once,
  one at a time: `test_relief_telegram` 435, `test_relief_team` 82, `test_relief_requests` 59, `test_relief` 45, `test_exams_relief`
  102, `test_routes` 20, `smoke` 103, `relief_today` 59, `relief_settings` 25, `relief_telegram` 39.
- Names check against the school's staff list (counts only; the added lines and commit messages since main d2dfbaf): 104 real staff
  names, 0 found; the school's full name 0; token and key shapes 0. (The controller runs it again after the last commit.)
- Every suite once more, one at a time, after these documents were written: all 31 `tests/*.py` and all 24 `tests/*.test.js` pass,
  each at its first run: `smoke` 103, `test_accounts` 14, `test_admin` 30, `test_ask` 49, `test_board` 59, `test_choices` 16,
  `test_combined` 38, `test_compare` 21, `test_exams` 206, `test_exams_relief` 102, `test_fixes` 65, `test_helper` 20,
  `test_history` 47, `test_history_draft` 9, `test_parents` 35, `test_plan` 201, `test_putback` 37, `test_refit` 170, `test_relief`
  45, `test_relief_requests` 59, `test_relief_team` 81, `test_relief_telegram` 429, `test_routes` 20, `test_rules` 11, `test_signin`
  33, `test_sync` 32, `test_teachers` 9, `test_typed` 33, `test_venues` 4, `test_verify` 56, `test_versions` 44; ask 12, board 67,
  choices 13, classview 18, draft 31, exams (its page tests, then rounds 2 to 4, the last 20), grid 14, groups 33, history 5, map
  26, parents 46, people 31, plan 20, relief_inbox 3, relief_settings 24, relief_summary 11, relief_telegram 39, relief_today 58,
  split 189, subjectview 15, sync 17, teacherview 8, timetable_page 7, venueview 24.
- Browser check: in practice mode on a made-up school with a scratch data folder, by real clicks, at desktop width and at phone width
  (375 px), at 01:30 at night school time on a school day: the ask form's confirmation; on Today "Approve all 2 waiting" gave
  "Approved 2 reliefs." and rows "Approved · not sent out" with Send out and Change, the counter "Approved, not sent out" 2, the top
  button "Send out 2 approved"; pressing it gave "Sent out 2 reliefs for Tue 24 Nov. They will be sent at 06:45.", the line "2
  reliefs sent out: they will be sent at 06:45 on Tue 24 Nov. You can still change them until then.", and rows "Will be sent at
  06:45" with Change only; Relief settings' Times with the five new times and their help lines; a head planned a relief for a
  colleague for the next day with their own choice, and Today showed it "Planned by Mr Hugo Ong", approved and sent out without the
  team; the teacher who is away saw "Being arranged" and never the relief teacher's name. No sideways scroll at phone width, no error
  in the page or the server. NOT seen, because it was night: the "sent" state after 06:45, the late request, the view after the
  cut-off (and F2's line, built after the check); the Telegram side.
- Final review of the whole branch: no Critical; four Important (the all clear while a relief was approved and not sent out; today's
  late work hidden after 2 pm; the untrue sentence in Relief settings; rollback advice that could not work), all fixed in the one fix
  round; six Minor (one fixed: the evening work reminder at night; the rest lines in these notes). The reviewer ran a whole week on a
  fixed clock with nine people: no relief teacher messaged before 06:45, after the cut-off or at night, none twice; data written the
  old way safe.
- Not checked: no real Telegram bot was called anywhere, and no model; no suite reaches the network. The Telegram side (the morning
  message, Send out on Telegram, the repeats, the alert) was not walked on a practice phone: tests alone cover it. In the
  browser, the "sent" state, the late request, the view after the cut-off and its line were not seen (above). Speed on the live service was not measured.
- Main 5de8cb5 (the admin roles and committees work, with Plan with AI's logged refusal reason and a code used twice) was merged
  into this branch as one merge commit. One file conflicted, `relief/links.py`, where this stage's blocked-bot alert (`note_alert`,
  `alerts`) and main's `forget` (what goes when a person is removed on the admin page) were written in the same place: both were kept
  whole. Then this stage was made to follow main. A removed person's note that the bot was blocked and every blocked-bot alert about
  them now go with their link, in the same transaction as their link and link codes, so a person given the same name later sees no
  old block, and an alert about them that was already queued is dropped instead of sent. A removed person is on no list: not reachable, not on the relief team, not on duty for the morning message, and a message
  queued for them is dropped as for anyone who has no Telegram any more. A person taken off the Timetable committee loses only what the
  tick gave (saving Relief settings, unless they are on the relief team); one who is also a teacher, a school leader, a head of
  department or a subject head keeps relief through that role, and one with no such role who is not on the relief team is on no
  list either. The rights that came from the old "Timetable committee"
  group now come from the Timetable committee tick; the test fixtures that made a committee member now tick it (a record in the old
  shape is still read as on the committee, and a test says so). The app's hooks (the morning message after the report, the History
  line by The app for a blocked bot) are each registered once, and the History page shows this stage's entries to the same people as
  before. No sentence of these notes, `docs/DEPLOY.md` or `README.md` was made untrue by the change (they name the timetable
  committee, never its old group, for relief settings). Then every suite once, one at a time, each at its first run: `smoke` 103,
  `test_accounts` 23, `test_admin` 53, `test_ask` 49, `test_board` 59, `test_choices` 16, `test_combined` 38, `test_compare` 21,
  `test_exams` 206, `test_exams_relief` 102, `test_fixes` 65, `test_helper` 20, `test_history` 47, `test_history_draft` 9,
  `test_parents` 35, `test_plan` 212, `test_putback` 37, `test_refit` 170, `test_relief` 45, `test_relief_requests` 59,
  `test_relief_team` 82, `test_relief_telegram` 439, `test_routes` 20, `test_rules` 11, `test_signin` 33, `test_sync` 32,
  `test_teachers` 9, `test_typed` 33, `test_venues` 4, `test_verify` 56, `test_versions` 44; adminview 16, ask 12, board 67, choices
  13, classview 18, draft 31, exams (the last round 20), grid 14, groups 37, history 5, map 26, parents 46, people 31, plan 20,
  relief_inbox 3, relief_settings 25, relief_summary 11, relief_telegram 39, relief_today 59, split 189, subjectview 15, sync 17,
  teacherview 8, timetable_page 7, venueview 24.
- The merge was reviewed by a fresh reviewer: nothing of main and nothing of this stage was lost or written twice; removing a person
  takes only that person's rows (tried with eleven names made to look alike, such as one name that begins with another); each of the
  app's hooks is there once. No Critical or Important finding; three small points, of which the one about wording is corrected above.
- Last of all, every suite once more on the merged code (commit 91b2622), one at a time, run by the controller: all 31 `tests/*.py`
  and all 25 `tests/*.test.js` pass at their first run, with the same counts as in the paragraph above (`test_relief_telegram` 439,
  `test_relief_team` 82, `smoke` 103, `test_admin` 53, `test_accounts` 23, `test_plan` 212). Main was fetched again and had not
  moved past 5de8cb5. The commit after it changes these notes and `docs/DEPLOY.md` alone.
- Names check once more on the whole branch against main (counts only): 104 real staff names, 0 found; the school's full name 0;
  token and key shapes 0.
- After the last review, corrected in words here and in `docs/DEPLOY.md` (ruling F9, no code changed): step 7 of the first morning;
  a relief on an absence asked for while rolled back; the report's two new known limits; open questions 11 and 12.
- The lead's answers of 24 November (1 yes, 2 hold, 11 yes), built on branch `relief-send-out-answers` from main d9aebf3: reviewed
  by a fresh reviewer, with no Critical or Important finding (it followed a held "Who covers you" from the evening to 06:45: made
  again once, never lost; a relief that started and was never sent out is named once). Every suite on that code, one at a time, run
  by the controller: all 31 `tests/*.py` and all 25 `tests/*.test.js` pass (`test_relief_telegram` 448, `test_relief_team` 82,
  `smoke` 103). Two readings of the answers were the controller's own and may be changed: "away" means away the whole day; the
  evening limit for "Who covers you" is the evening work time (18:00), so an acknowledgement at 18:30 is told the next morning.
  Not checked: no real Telegram bot, as before.

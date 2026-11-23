# Relief duty and the send-out

Date: 23 November 2026. Status: **approved by the committee lead on 23 November 2026** ("Approved, plan it"), with questions 2 to 4 as written (the first reading of each). Mockups, all with made-up names:
`2026-11-23-relief-duty-and-send-out-mockups.html` beside this file (open it in a browser; one tab per screen).

The relief module was built to the design the lead approved on 20 November (`2026-11-20-relief-module-design.md`) and to
stage 4 on Telegram. In it, a relief teacher is told the moment someone on the relief team presses Approve, at any hour, and the
relief team can be messaged at any hour too. On 23 November the lead described how relief duty really runs at CTSS: the team
rests in the evening, one person is in charge each day with another on standby, the relief teachers are told in the morning
all at once when the person in charge sends it out, and some days (Friday HBL) have no relief duty at all. This document turns
that into a change to the app, in two stages, for the lead to approve before anything is planned or built.

Everything below that is not in the lead's own words is marked as a proposal or as **my call**, with its reason and its cost
if it is wrong. The lead may change any of them.

## What the lead said

The lead's words on 23 November 2026, as written, in the order given:

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

How two of these are read here, in case another reading was meant:
- In item 3, "which officer is covering the person" is read as the relief teacher who covers the absent teacher's lesson, not
  the reporting officer.
- In item 3, "the person requesting the relief" is read as the teacher who is away, because the reason given is "so that they
  can reach to them". When a head plans an absence for a colleague, the colleague who is away is told, not the head.

## Intent

**Why (the lead's).** The relief team should rest in the evening. One person is responsible each day. Relief teachers are not
disturbed before the morning. The person away can reach whoever covers them. A relief a head chose when planning needs no second
approval, and its teacher hears of it early enough to prepare (items 13 and 14).

**Goals.**
- No new request pings the relief team between the day's cut-off and the next morning. What belongs to a relief already sent out
  for today (a report that it is not acknowledged, a request to change) still reaches them until its lesson starts (my call 27).
- One morning message tells the people on duty everything that waits for today.
- The relief team approves, and then sends out as a separate press. Nothing reaches a relief teacher before a team member
  pressed Send out for it, or a head chose them when planning (the lead's items 13 and 14), nor outside school hours (from the
  earliest send-out time to the cut-off of a school day; after the cut-off, only about a lesson of that day still to come).
- A relief told before its day is told again 24 hours before and on the morning itself (item 14).
- If a relief teacher is away on the day, their lesson goes back to the normal flow: open, the AI picks, the team approves and
  sends out (item 14).
- The AI picks as soon as a request is in, for any date, so the evening and the morning are spent checking, not waiting.
- A late request in school hours reaches the whole team, and any one of them can approve and send it out.
- The teacher who is away is told who covers each lesson once that teacher has acknowledged.
- Files stay in the app; Telegram carries the basics and a link.
- The team hears at once (within the day's hours) when a teacher blocks the bot.
- A weekly duty roster (stage 2) says who is in charge and who is on standby each day, with one-day changes and days with no
  relief duty.

**Non-goals.**
- The roster does not decide who is allowed to act: anyone on the relief team can still approve and send out on any day.
- No new way to sign in, no new right, no new kind of person.
- The published timetable on a date (stage 3b of the relief design) is not built, here or before this.
- No change to how the AI picks, the "free then" list, the checked limits or the relief rules.

**Anti-goals (would make it a failure even if it works).**
- A relief teacher is messaged in the evening or at night, or before the earliest send-out time.
- A relief is sent out that nobody on the relief team approved, or that nobody pressed Send out for, unless a head (anyone who
  may plan relief for a colleague) chose that teacher when planning.
- A relief stays with a teacher who is away that day, so the lesson has nobody.
- A request is lost because it came on a day with no relief duty, after the cut-off, in the evening or at a weekend.
- The relief team is pinged in the evening by the app (not by a person's own answer on Telegram).
- The morning message is wrong in a way that hides work: it says nothing waits when something does.
- A relief held until the morning goes out with words that are no longer true (a cancelled lesson, a changed teacher, old work).

## How it works today

True to the code on branch `relief-duty-design` (main d2dfbaf).

- **Picks.** `relief/fill.py` makes the picks. A lesson today is picked at once. A lesson on a later date is picked at the
  setting `fill_at` (15:00) on the school day before (`due_at`), or when the team presses Fill now. A request to change gets a
  new pick at once. Every run (the ticker runs each minute) first checks each waiting pick: one whose teacher is no longer free
  goes back to open and is picked again (`fill._run`, step 1, with `cover.stale` and `cover.drop`). An approved relief is not
  dropped, whatever the reason, the teacher being away that day too (`cover.drop` refuses anything but a waiting pick): Today
  marks it "{name} is no longer free then: change it". Approve checks again that the teacher is free
  (`cover._approve` calls `still_free`).
- **Cover states** (`relief/cover.py`, `state`): open, waiting (a pick waits for the team), approved, acknowledged, change
  (approved, and the relief teacher asked to change), cancelled. Approve, Approve all and Change write `approved` (by, at).
  Change chooses and approves in one.
- **A planner's own choice.** Plan relief for a colleague needs the right `relief.plan`: school leaders, heads of department and
  subject heads (`accounts/rights.py`), and everyone on the relief team. When the planner chooses a relief teacher for a lesson,
  `absences.new` checks that teacher is in the "free then" list and writes the lesson's `relief` and `relief_by` (the planner),
  with no pick of its own; `cover.pick_of` reads it as a pick "by planner" with the reason "Planned by {planner} on {day}."
  (`cover.PLANNED`). Its state is **waiting**, like the AI's pick: it waits for the relief team's Approve. Until then the
  absent teacher does not see the name (`web._hidden`), the planned relief download says "Waiting for the relief team"
  (`web.WAITING_TEAM`), and the planner may choose again or take it off (`absences.choose`), which is refused once it is approved
  ("changed on the team's Today page"). A lesson the planner left open is picked by the AI like any other.
- **Telling.** `relief/tell.py` works every message out from the records each time (`due`) and queues each under a key of its
  own, once (`outbox.queue`). The sweep runs every minute and after each save. Before a message goes, `still_true` asks again
  whether it is still so; one that is not is dropped. `relief/outbox.py` sends: oldest first, once or marked "may not have been
  sent". Its only holding today is a retry wait (`next_at`) and a pause Telegram asks for; `queue` writes `next_at` 0.
- **The relief message** is made as soon as a cover is approved and its teacher is on Telegram (`tell._relief`), whatever the
  hour. Its work files are sent after it, one by one (`outbox._send_files`). The text says "Files: {n}, sent after this
  message."
- **The ping built on 23 November** (pull request #99, kind `new`): one message to each relief team member on Telegram for an
  absence sent today for today, once its picks wait (or five minutes after it was sent, `NEW_WAIT`), never before an hour
  before the first period (`BEFORE`), never for an exam's backup, never to who sent it or to the absent teacher. One sent the
  evening before is not pinged.
- **Other messages, all at once when they fall due:** "Relief planned for you" to the absent teacher; the reminder to
  acknowledge at `remind_at` (15:00) the school day before; the reporting officer's message; request to change and its new pick
  to the team; kept, moved, no longer needed, not happening, on again to the relief teacher; cancelled to the team, the planner
  and whoever was told. The relief team is everyone with the relief team extra (the right `relief.team`, `accounts/rights.py`).
- **The report** (`relief/report.py`): every `report_every` minutes (15) from an hour before the first period, to the whole
  team, while an approved relief of today is not acknowledged; then one all clear. The weekly summary goes to the whole team at
  `weekly_day` `weekly_at` (Friday 15:00).
- **A blocked bot.** When Telegram refuses a message because the person blocked the bot, the app unlinks them, removes the
  message from the queue and notes it on their own Telegram card (`outbox._blocked`, `links.note_blocked`). Nobody else is told.
  No History line is written: the History needs a signed-in person.
- **The pages.** Today (`static/relief-today.js`) shows Today and Tomorrow, the counters, and Approve, Approve all waiting,
  Change, Fill now, Remind. "Reliefs I'm covering" (`/api/relief/covering`) and the relief teacher's file download show a relief
  once it is approved. The absent teacher's own view of an absence shows the relief teacher's name once it is approved
  (`web._hidden`). The ask form says "{officer} is not on Telegram: please tell them yourself." when that is so (PR #99).
- **Settings** (`relief/settings.py`): `times` holds `fill_at`, `remind_at`, `report_every`, `weekly_day`, `weekly_at`; the
  calendar holds terms and holidays (`relief/calendar.py`, `school_day`). Relief settings are saved by whoever has
  `relief.save`: a member of the timetable committee group, anyone with the relief team extra, and the shared committee code.

## What changes

### A day, in order

Times are the proposed defaults; each is a setting.

- **The evening before (from the cut-off, 14:00, to the morning time).** Requests come in and are recorded. The AI picks for
  them at once. Nobody on the team is pinged. The team may look at Today for the next school day, approve, change, and press
  Send out; what is sent out is held, and the page says "Will be sent at 06:45".
- **06:30, the morning message.** On a school day with relief duty, one message on Telegram to the people on duty (stage 1: the
  whole team) with everything that waits for today.
- **06:45, the earliest send-out.** Every relief of today that was sent out before now goes to its relief teacher. From now on,
  Send out sends at once.
- **06:30 to 14:00, late requests.** A request for today that comes in after the morning message time pings the whole team, once
  its picks are in (five minutes at most, as today). Any member approves and presses Send out. ("Late" starts at the morning
  message time, a setting; the lead said "after 7am": set the morning message to 07:00 for exactly that.)
- **14:00, the cut-off.** Today is closed for pings. A request that comes in after it for a lesson still to come today is
  recorded, picked and shown on Today, with no ping; a team member who looks can still approve and send it out, and it goes at
  once. Today opens on the next school day from here. Requests for later days wait for that day's morning message.
- **Weekends, holidays and (stage 2) days with no relief duty** have no morning message; a request sent then waits for the
  next school day's morning message, unless it is for a day with no relief duty (below).
- **A relief for a later day** (a head's own choice when planning, or one the team sent out ahead) is told to its teacher at the
  first moment of school hours, then again 24 hours before and on the morning itself (below, "Planned relief").

### The settings (stage 1)

Three new times in Relief settings, under "Times", in place of "Fill open lessons at":

| Setting | Proposed default | What it does |
|---|---|---|
| Morning message to the relief team at | 06:30 | The one message with everything waiting for today. |
| Earliest send-out to relief teachers | 06:45 | Nothing reaches a relief teacher before this time of a school day, whenever Send out was pressed. |
| Cut-off for the day's relief | 14:00 | After it, no pings for today; the team works on the next school day. |
| Remind the absent teacher to set work at | 18:00 the evening before, and 07:00 on the day | Only while a lesson of that day has no work (below, "Reminding the absent teacher to set work"). |

Saving checks morning message at or before earliest send-out, and earliest send-out before the cut-off ("The morning message
comes at or before the earliest send-out, and both before the cut-off."). `fill_at` is no longer shown or read (its value stays
in the file, as the old lists do). The other times stay as they are.

### Approve and Send out (stage 1)

Approve stays as it is: it approves a pick, and checks the teacher is still free. It no longer sends. **Send out** is a new,
separate press, for the relief team (the right `relief.team`, as Approve).

- **Send out {n} approved**, at the top of Today, beside "Approve all {n} waiting": every relief of the date on screen that is
  approved and not sent out, in one press. A relief whose teacher is no longer free is not sent out and is listed: "{name} is
  no longer free then: change it".
- **Send out**, on a row, for one relief alone.
- The cover gets a "sent out" mark: who pressed it, when, and for which approval. A new approval (Change, a request to
  change's new pick approved) needs a new Send out. One History entry a press: "Sent out {n} reliefs for {day}" or "Sent out
  {name}'s relief for {lesson} {periods} on {day}".
- **When it goes:** at once in school hours, else at the next start of school hours. **School hours** for relief teachers are
  from the earliest send-out time to the cut-off of a school day; after the cut-off, a message about a lesson of that same day
  still to come also goes at once (the lead's item 12: "Pings stop, sending allowed"). The sweep makes the relief message only
  once its time has come, from the record as it is then, so a change or a cancel before then is simply what goes (or nothing
  goes).
- **Pressed for tomorrow at 21:00:** held; the row says "Will be sent at 06:45".
- **Pressed for a relief next week, in school hours:** it goes at once, then again 24 hours before and on the morning itself,
  as a head's own choice does (my call 3, below).

What Today shows, by state:

| State | The row says | Buttons |
|---|---|---|
| No pick | No relief teacher yet | Choose |
| Picked, waiting | Waiting for you | Approve, Change |
| Approved, not sent out | Approved · not sent out | **Send out**, Change |
| Sent out, held | Approved · will be sent at 06:45 | Change |
| Sent | Approved · Sent 06:45 (and the lines stage 4 has: "Being sent…", "Not on Telegram: they see it in Reliefs I'm covering" …) | Remind, Change |
| Acknowledged | Acknowledged 06:52 | Change |
| Asked to change | Asked to change, with the new pick | Approve the new pick, Keep, Change |
| A head's own choice | Approved · Planned by {head} · Sent Mon 12 Oct, 10:05 (or "will be sent at 06:45" while held), then as Sent or Acknowledged above | Remind (once sent), Change |
| Back to open: its teacher is away | Waiting for you, with the new pick, and "{name} was to cover it and is away then" | Approve, Change |

A new counter "Approved, not sent out". "Approved, not acknowledged" then counts sent ones alone. A head's own choice is never
"Approved, not sent out": it is sent out when it is planned.

Where the app today means "has reached its teacher" (uses of the list `APPROVED` in `relief/web.py` and `relief/tell.py`), it
now means **sent out, and its time has come**: Reliefs I'm covering, the relief teacher's file download, the not-acknowledged
report and its all clear, Remind, and Acknowledge and Request to change on the page and on Telegram. Two uses differ: the
absent teacher's own view of an absence (`web._hidden`) shows the relief teacher's name once it is **acknowledged** (my call
12), and the weekly summary (`relief/summary.py`) counts reliefs that were sent out and measures "on time" from when the relief
message went, not from the approval (my call 28). The load tracker's counts stay as they are (they count approved and waiting
reliefs, as the design says).

On Telegram, the request-to-change message keeps its **Approve {name}** button. After the press, the line on the message
reads "✅ Approved: {name}, 10:12." and the button becomes **📤 Send out to {name}** (my call 7).

### Planned relief (a head's own choice) (stage 1)

This changes a rule of the 20 November design ("Planned relief also waits for the relief team's approval before the relief
teacher is told"), on the lead's word (items 13 and 14).

**The lead's rule.** A head's own choice of relief teacher, made when planning an absence for a colleague, is approved at once;
the relief team does not approve it. A lesson the head left open goes to the AI and the team as any other. That relief teacher
is told as soon as it is planned, in school hours; told again 24 hours before; and again on the morning itself. The relief shows
in the teacher's app page before that ("A teacher can also check anyways on the app"). If the assigned relief teacher is sick on
the day, the lesson falls back to the normal relief assignment.

**What is written** (my call 30, 31). "A head" is anyone who may plan relief for a colleague (the right `relief.plan`: school
leaders, heads of department, subject heads, and the relief team). When they send the plan with a teacher chosen for a lesson,
that lesson is saved as approved by them (`approved` by the planner's name, at the moment of planning) and sent out by them
(the "sent out" mark, by the planner, for that approval), with its pick "Planned by {planner} on {day}." as today. No extra
History entry: the planning entry says it. The same holds when the planner chooses again later in Plan relief (my call 32).
Today shows the row as "Approved · Planned by {head} · Sent {time}"; the team can still Change it (a new approval by them, which
needs their Send out). A lesson left open is picked by the AI and waits for the team.

**When the teacher is told** (my calls 33 to 36):
- **First:** the relief message (as above) at once when it is planned in school hours; planned outside them (the evening, a
  weekend), at the next start of school hours (06:45 of the next school day). The lead's "never before morning" still holds.
- **24 hours before** the lesson's start. When that moment is outside school hours, it moves earlier, to the last cut-off
  (14:00 of a school day) before that moment: for a lesson on Monday at 09:20, Friday at 14:00; for one on Wednesday at 15:00, Tuesday at 14:00.
- **On the morning itself**, at the earliest send-out time (06:45) of the lesson's day.
- A repeat is not sent when its moment had already passed when the first message went, or when the teacher was told of that
  relief (by its first message or the other repeat) less than 12 hours before. So a relief planned at 10:00 on Monday for Tuesday
  09:20 gets the first message at 10:00 and the morning one at 06:45 on Tuesday; one planned at 07:00 on Tuesday for that day
  gets one message; one planned on Monday for Thursday gets three.
- Each repeat goes once, and only while the relief is still that teacher's and its lesson still to come; a new approval (Change)
  starts again with a first message of its own.
- **Already acknowledged:** the repeats still go, as a short line without buttons (the point is to remember a relief told days
  ago). **Not acknowledged:** the relief message again, with its buttons, as Remind sends it.

The short line, 24 hours before (with **Open in the app**):

> ⏰ Reminder · your relief on Wed 14 Oct
> 3B Maths · P3–P4 · 09:20–10:00 · Room 2-14
> For Mr Arjun Nair. The work is in the app.

and on the morning itself the first line reads "⏰ Reminder · your relief today, Wed 14 Oct".

**In the app before that.** The relief shows in the teacher's Reliefs I'm covering from its first message on, with its work and
files, as any relief sent out. (Reliefs I'm covering lists reliefs from Monday of this week on, so a later week shows too.)

**If the relief teacher is away on the day** (my calls 37 to 39). Every approved relief, a head's choice or not, whose teacher
then has an absence over its periods goes back to open, and the normal flow takes over: the AI picks, the team approves and
sends out. One rule for every relief: a teacher who is away cannot cover any lesson, however it was arranged. It is checked by
every run of the picks (each minute, and at once after an absence is saved), for that one reason alone: a teacher away. Other
reasons for "no longer free" (a changed timetable, a duty) stay as today: marked on Today for the team to change. The teacher
who was to cover it, if told, gets the existing "❌ No longer needed: … You're free then." The relief team is told:

> 🔁 Relief needed again · Wed 14 Oct
> 3B Maths · P3–P4 · for Mr Arjun Nair
> Mr Daniel Tan was to cover it and is away then. A new pick is waiting for your approval. Approve, then Send out.

("Nobody else is free then: choose someone in the app." when the AI finds nobody.) To the whole team in both stages, with
**Open relief today**, between the morning time and the cut-off of a school day, else at the next morning time; for a lesson of
today found before the morning message, the morning message counts it and there is no separate message.

### The AI picks at once (stage 1)

Every open lesson is picked as soon as its absence is in, for any date: `fill._run` treats every open cover as due. `due_at`
stays, because the absent teacher's reminder uses it with `remind_at`. Fill now stays (it picks again for a date). A pick made
days ahead is checked again by every run (each minute: one whose teacher is no longer free goes back to open and is picked
again) and once more when it is approved and when it is sent out. What it cannot see is later absences that would have made
another choice spread the load better; the team sees the load and may change it. The AI is asked for no more than its guard
allows (60 picks in 10 minutes for the whole app, `relief/pick.py`): when a long planned absence or the first run after the
deploy holds more open lessons than that, the nearest dates are picked first and the rest stay open and are picked by the next
runs, minute by minute; they are not handed to the app's own order just because the guard was reached (my call 29).

### The messages (stage 1)

Each in the style of the existing ones. `{..}` stands for a name, a day, a lesson or a number.

**The morning message** (new), to each person on duty (stage 1: each relief team member on Telegram), at the morning time on a
school day with relief duty, with the button **Open relief today**:

> ☀️ Relief today · Tue 13 Oct
> 3 absences · 6 lessons to cover
> • 3 waiting for your approval
> • 2 approved, not sent out
> • 1 with nobody free: choose someone in the app
> Away: Mr Arjun Nair (whole day) · Ms Chloe Ong (P3–P5) · Mdm Siti Rahman (P6–P8)

A line is left out when its number is 0. When everything approved was sent out already (held), the line reads "• 2 sent out:
will go at 06:45". A relief told already (a head's own choice, or one sent out ahead) is counted in the total with the line
"• 1 sent out already". More than eight people away: the first eight, then "and {n} more". When there is no lesson to cover today,
there is no message. Stage 2 puts one line first: "You are in charge today. Standby: Ms Rachel Koh." or "You are on standby
today. In charge: Mr Marcus Goh."

**The late request** (changes the ping of PR #99), to each of the whole team, once:

> 🆕 Late request for today · Mr Arjun Nair
> P3–P5
> 2 lessons are waiting for your approval. Approve, then Send out.

with **Open relief today**. ("1 lesson is waiting for your approval.")

**The relief message** (changed), to the relief teacher, when it is sent out and its time has come:

> 🔔 Relief for you · Tue 13 Oct
> 3B Maths · P3–P4 · 09:20–10:00
> Room 2-14
> For Mr Arjun Nair
> Work from Mr Arjun Nair: Worksheet 4, questions 1 to 10.
> Link: https://example.org/sls/abc
> Files: 2. Open the app to download them.

with **✅ Acknowledge**, **↩ Request to change** and a new row **Open in the app** (to Reliefs I'm covering). "Files: …" is said
only when there are files; nothing is sent after the message.

**Who covers you** (new), to the teacher who is away, when a relief teacher acknowledges one of their lessons:

> ✅ Covered · Tue 13 Oct
> 3B Maths · P3–P4 (09:20)
> Mr Daniel Tan has acknowledged. You can reach them if you need to.

One message a lesson (each is acknowledged at its own moment). Not sent when the lesson is over, when the absent teacher is the
relief teacher, or for an exam's or event's backup (the person is on duty in school).

**A teacher blocked the bot** (new), to each of the whole team:

> ⚠️ Ms Priya Menon has blocked the bot and is now unlinked.
> They did not get: Relief for you · 3B Maths P3–P4 on Tue 13 Oct.
> Please tell them yourself.

"They did not get:" names the message that was refused: a relief by its lesson, any other by its kind as Relief settings lists
kinds ("Relief planned", "Reminder to acknowledge" …). One a person a day. Also a History line "Telegram unlinked for {name}:
the bot was blocked", by "The app".

**The reminder of a relief told before its day** (new, 24 hours before and on the morning) and **Relief needed again** (new, to
the team) are under "Planned relief" above.

**Unchanged in wording:** relief planned for you, the reminder, the reporting officer's, request to change and new pick,
kept, moved, no longer needed, not happening, on again, cancelled, the report, the all clear, the weekly summary.

### What becomes of today's ping

The ping built in PR #99 (kind `new`) is replaced by two things:
- a request that arrives before the morning time (the evening, the night, a weekend) is in the morning message, and pings
  nobody;
- a request for today that arrives after the morning message and before the cut-off is the late request above: the same
  waiting for its picks (five minutes at most), the same "once, even when dropped", the same people left out (who sent it, the
  absent teacher), its text as above. Its "never before an hour before the first period" (`BEFORE`) becomes "never before the
  morning time". One that arrives after the cut-off pings nobody.

### Quiet times for the other messages

- **To the relief team:** nothing is made between the cut-off and the next school day's morning time, except the answer to a
  press of their own. "Cancelled" to the team and the blocked-bot alert, falling due then, wait until the morning time and go
  then if still true. A request to change, and the not-acknowledged report, belong to a relief already sent out for today: they
  go at once, also after the cut-off, until the lesson starts (a teacher told at 06:45 of a 14:40 lesson may ask to change at
  14:10). After the last lesson of the day nothing of this kind can come (my call 27).
- **To relief teachers:** only in school hours (from the earliest send-out time to the cut-off of a school day; after the
  cut-off, only about a lesson of that day still to come), whatever the kind; anything falling due outside them waits for the
  next start of school hours, and is dropped if no longer true by then. A relief for a later day may so be told on an earlier
  school day (a head's own choice, or sent out ahead), never in the evening.
- **"Relief needed again"** to the team: between the morning time and the cut-off, else at the next morning time.
- **To the absent teacher and the reporting officer:** as today, at once (my call 9). The weekly summary keeps its own
  setting, Friday 15:00 (my call 10).

### Reminding the absent teacher to set work (stage 1)

**The lead's rule (item 15).** A teacher who sends their request after 15:00 and has not set work is reminded at 18:00 and at
07:00.

**What exists today.** The only reminder is for an absence someone else planned and the absent teacher has not acknowledged:
"⏰ Reminder: please acknowledge your relief for {days} and set work.", at `remind_at` (15:00) on the school day before
(`fill.nudge`, `tell._planned`, key `remind:{id}`), once, and only for one planned before that time. A teacher's own request with
no work set gets no reminder at all. Work counts as set for a lesson when it has text, a link or a file (`web._row`'s
`work_set`, the relief message's "No work set yet"). Work cannot be set on Telegram after Send: `/relief` only asks a new request,
so the absent teacher sets missing work in the app (My absences).

**What changes** (my calls 40 to 47):
- **Which lessons:** those of the absence on one day that need cover (not "no relief needed", not stopped by an exam or event),
  are still to come, and have no text, link or file. Each school day of the absence is looked at on its own.
- **When:** 18:00 on the day before that day (the calendar day: Sunday 18:00 for a Monday), and 07:00 on the day itself. Both
  are settings ("Remind the absent teacher to set work at"), defaults 18:00 and 07:00.
- **Who gets which:** every absence with such lessons, asked or planned, whenever it was sent, gets the reminders whose moment is
  still to come when it is sent. Sent at 16:00 for tomorrow: 18:00 and 07:00. Sent at 10:00 for tomorrow: 18:00 and 07:00 too
  (in the lead's spirit: no one should reach the morning without work; the lead named the case after 15:00 because the 15:00
  reminder has passed by then). Sent at 23:00 for tomorrow: 07:00 only. Sent at 06:50 for today: none (07:00 would come ten
  minutes after the confirmation that already said "no work set yet"; a reminder is skipped within 30 minutes of the request).
  Sent at 07:10 for today: none.
- The planned absence's 15:00 reminder ("please acknowledge … and set work") stays as it is. When it went less than three hours
  before 18:00, the 18:00 one still goes if work is missing (they are about different things: acknowledging, and the work).
- **Not sent** once every lesson of that day has work, once the absence or that day is cancelled, once the lesson is over, for
  an exam's or event's backup, or to a teacher not on Telegram. Each goes once (keys `work:{id}:{date}:eve` and `:day`).
- **Quiet times:** these go to the absent teacher in the evening on purpose. The quiet rule is for the relief team and relief
  teachers.

The message, with **Open in the app** (to My absences):

> ✏️ Please set work · Tue 13 Oct
> 2 lessons have no work yet: 3B Maths P3–P4, 2A Maths P5–P6.
> Set it in the app, in My absences. Your relief teacher sees it there.

("1 lesson has no work yet: …"; more than five lessons: the first five, then "and {n} more".)

At 07:00 the relief teacher may have been told at 06:45 already. Work set after that is not sent to them on Telegram (as today,
stage 4: their message says to look in the app); it shows in their Reliefs I'm covering. My call 46.

### Asking for relief: two ways, as today

A teacher who is away asks for relief in the app (Relief, the tab **Ask for relief**) or on Telegram (`/relief` to the school's
bot). Both ask the same things in the same order of meaning (the day, whole day or some periods, the reason, the work for each
lesson, the reporting officer), both save through `absences.new`, and both land in the relief team's What's in. The mockup's tab
"Asking for relief: the app and the bot" shows both as they are at head. This design changes nothing in either, except:
- the work reminders above, after Send, for lessons left without work;
- whatever the lead answers to question 3 (the sentences about the reporting officer: the form's "{officer} is not on Telegram:
  please tell them yourself." and `/relief`'s "{officer} will be told."); as written, they stay;
- what follows Send (when the AI picks, who is pinged), as the rest of this document says.

### Files by link (stage 1)

The relief message no longer sends files on Telegram (this reverses the lead's answer 3 to stage 4, on item 10). It says
"Files: {n}. Open the app to download them." and has **Open in the app**. Files are downloaded in Reliefs I'm covering, as
today. `/relief` still takes files from the teacher who asks; only sending them on to the relief teacher stops.

### The asker told who covers (stage 1)

As in "Who covers you" above. In the app too, the teacher who is away sees the relief teacher's name on their absence only once
it is acknowledged; before that, "Being arranged" (my call 12). Management and the relief team see everything, as today.

### The blocked-bot alert (stage 1)

As above. It is made when the app finds out (a message to that teacher is refused), from what was refused, and goes to the
whole team in both stages (the lead's item 10). The person's own card keeps saying so, as today.

### The roster and days with no relief duty (stage 2)

A new card in Relief settings, **Duty roster**, saved with the rest of the settings, by whoever may save Relief settings today
(the timetable committee, its shared code, and the relief team). No new right.

- **Weekly lines:** "Every {weekday}: in charge {name}, standby {name}, from {date} to {date}". Names are picked from the relief
  team. Two lines for the same weekday may not overlap in dates.
- **No relief duty lines:** "Every {weekday}: no relief duty ({a name, e.g. HBL}), from {date} to {date}".
- **One day only:** a date with its own in charge and standby, or "no relief duty" with a name. It wins over a weekly line.
- **This week:** a strip, Monday to Friday, showing for each day the two names, "No relief duty (HBL)", or the holiday.
- **A day with no line** works as stage 1: the whole team is told and anyone approves.
- **A person on a line who is no longer on the relief team** is passed over; the line shows "not on the relief team now". If
  both are passed over, the whole team is told.

On a day with a line, the morning message, the not-acknowledged reports and the all clear go to the person in charge and the
standby alone. Everything else goes as in stage 1 (late requests, request to change, the blocked-bot alert, cancelled, the
weekly summary: the whole team).

**A day with no relief duty:** a teacher can still send a request for it, on the app or `/relief`, and it is recorded as any
other. The AI does not pick for it, nothing waits for approval, there is no morning message and no report. The team gets an FYI
on Telegram, at once if it comes between the morning time and the cut-off of a school day, else at the next morning time:

> ℹ️ FYI · Mr Arjun Nair is away on Fri 16 Oct (whole day).
> It is a no relief duty day (HBL), so nothing is arranged.

Today shows that day's lessons with "No relief duty (HBL)" at the top; the team may still choose someone by hand (Change), then
Send out.

### Who gets what

| Message | Who (stage 1) | Who (stage 2, on a day with a roster line) | When | Obeys |
|---|---|---|---|---|
| Morning message | whole team | in charge and standby | the morning time, school days with duty | morning time |
| Late request | whole team | whole team | at once, picks in or five minutes | morning time to cut-off; else none |
| Relief for you | relief teacher | same | when sent out, or when a head planned it with that teacher | school hours |
| Reminder of a relief told before its day | relief teacher | same | 24 hours before (else the last cut-off before), and the morning itself; not within 12 hours of the last | school hours |
| Kept, moved, no longer needed, not happening, on again | relief teacher | same | at once | school hours |
| Relief needed again (its teacher is away) | whole team | whole team | at once | morning time to cut-off; else the next morning time |
| Who covers you | absent teacher | same | at the acknowledgement | none (falls in the day) |
| Request to change, new pick | whole team | whole team | at once | none (falls in the day) |
| Blocked-bot alert | whole team | whole team | at once | morning time to cut-off; else the next morning time |
| Off-day FYI | (none in stage 1) | whole team | at once | morning time to cut-off; else the next morning time |
| Cancelled (team's copy) | whole team | whole team | at once | morning time to cut-off; else the next morning time |
| Cancelled (planner, absent teacher, officer) | as today | same | at once | none |
| Not yet acknowledged, all clear | whole team | in charge and standby | as today, from an hour before the first period | as today |
| Relief planned for you, reminder | absent teacher | same | as today | none |
| Please set work | absent teacher | same | 18:00 the day before and 07:00 on the day, while a lesson of that day has no work; not within 30 minutes of the request | none (on purpose) |
| Reporting officer's | officer | same | at once | none |
| Weekly summary | whole team | whole team | Friday 15:00 (setting) | its own setting |

## Constraints carried

From the approved relief design and stage 4, kept whole but for the first, which the lead changed (items 13 and 14):
- Nothing reaches a relief teacher before a relief team member approved it and sent it out, or a head (`relief.plan`) chose that
  teacher when planning; and nothing reaches them outside school hours. The 20 November design said only "before someone on
  the relief team approved it", and planned relief waited for the team too.
- A message is sent once, or marked "may not have been sent"; never twice. Every new message has its own key and is worked out
  by the sweep, never sent from a page.
- A message never holds the typed reason, the remarks or a pick's history. The officer's alone carries the kind of reason.
  The new messages carry none of these.
- Logs say the kind of failure alone, never a name, text, chat or token.
- No new right name. Send out uses `relief.team`; the times and the roster use `relief.save`; a head's own choice uses
  `relief.plan`, as planning does today.
- The bot works on one copy of the app.
- No staff name, reason or work goes to the AI provider; picking at once changes when the AI is asked, not what it is told.
- Without Telegram connected, everything works on the pages: Send out then makes the relief show in Reliefs I'm covering at its
  time.

## Approaches

**What the lead was shown:** one build, or two stages. **The lead picked "two stages"** (item 11).

**How to build it (my call).** Extend what is there; add no new scheduler and no new dependency.
- The cover record gets a "sent out" mark (by, at, for which approval); a head's choice is saved approved and sent out.
- The run of the picks (`fill._run`, step 1) also sends back to open an approved relief whose teacher is away then.
- The sweep (`tell.due`) learns the times: it makes a relief-teacher message only in school hours, the two repeats at their
  moments, and a team message only between the morning time and the cut-off (or holds it to the next morning time). It already
  works by the clock this way for PR #99's ping (`BEFORE`), so this is one rule, applied by kind.
- The morning message is made by the minute ticker, claimed once a day the way the report claims its mark (`tgdb.raise_state`),
  so a restart or a second copy never sends it twice.
- The settings gain three times and (stage 2) a roster section in the same file.

Alternatives considered:
- **Hold in the queue** (queue the relief message at Send out with `next_at` set to 06:45; the column is there). Not chosen: the
  text would be made at 21:00, so work set at 22:00 would be missing, and two places would decide when something goes. The
  sweep makes it at 06:45 from the record as it is.
- **A separate scheduler** (a job library, or a cron job on Railway) for the morning message. Not chosen: a new dependency and a
  second place where time is kept, when the app's own minute ticker already sends the report on time.

## The two stages

Each its own plan and pull request, merged and deployed only on the lead's word, each usable alone.

**Stage 1, the send-out flow.** Approve and Send out as two presses; the three times; the AI picks at once for any date; the
morning message and the late request in place of PR #99's ping; quiet times for the team and for relief teachers; the asker
told who covers once acknowledged; files by link only; the blocked-bot alert to the team; the work reminders to the absent
teacher at 18:00 and 07:00; a head's own choice approved and
sent out at planning, with the reminders 24 hours before and on the morning (also for any relief sent out before its day); an
approved relief whose teacher is away going back to open, with "Relief needed again" to the team. "The two on duty" is the
whole team.
After it, the lead can: let the team rest in the evening; have the team check in the evening and send out at one press in the
morning; know that no relief teacher hears anything outside school hours; let heads arrange planned relief without the team;
let teachers see who covers them.
Left out: the roster, days with no relief duty, narrowing messages to two people.

**Stage 2, the duty roster.** The Duty roster card with weekly lines, one-day changes, "No relief duty" lines and the This week
strip; on days with no relief duty, no picks, no morning message, no report, and the FYI to the team; the morning message, the
reports and the all clear narrowed to the person in charge and the standby on days with a line. After it, the lead can set
who is on duty each day and switch relief off for HBL Fridays.
Left out: a nudge to the standby when nothing is sent out (question 4); anything that limits who may act.

## My calls (the lead may change any)

1. The three times are 06:30, 06:45 and 14:00 by default, as proposed to the lead. Reason: the lead's "7 am" is when the person
   in charge acts; 06:45 lets them send a little before. Cost if wrong: three settings to change.
2. Fill open lessons at (`fill_at`) goes; every open lesson is picked at once. Reason: the lead's "the AI will allocate any time
   a request is in". Cost: a pick made days ahead does not see later absences when spreading load; the team may change it.
3. A relief the team sends out before its day (a teacher asks today for next Wednesday, the AI picks, the team approves and
   sends out) is told as a head's own choice is: at once in school hours (else at the next start of them), then 24 hours before
   and on the morning itself, by my calls 33 to 36. Reason: it follows the lead's answer on planned relief (item 14) by analogy;
   a teacher should hear of a relief early enough to prepare, and "never before morning" still holds. This replaces the
   draft's "told only on its own morning" and its question. Cost if wrong: if the lead wanted these told only on their own
   morning, one condition; a teacher may get up to three messages for one relief.
4. Send out sends everything approved and not sent out for the date on screen in one press, and a row has its own Send out.
   Reason: the morning batch, and a single late request. Cost: one button.
5. A relief whose teacher is no longer free is skipped by Send out and listed. Reason: the same check Approve makes. Cost: none.
6. No button to take back a Send out that is held; Change or cancel does it. Reason: Change already makes a new approval that
   needs a new Send out. Cost: one button if the team wants it.
7. On Telegram, approving a request to change's new pick does not send; the button then becomes "📤 Send out to {name}". No
   Send out on the morning message. Reason: Send out is a separate press, and one relief named on a button is clear, a batch is
   not. Cost: one more tap, or a button.
8. A request for today after the cut-off pings nobody but can still be sent out, at once. Now the lead's own rule (item 12,
   "Pings stop, sending allowed").
9. Messages to the absent teacher and the reporting officer keep their times (at once; the reminder at 15:00 the day before).
   Reason: the lead's quiet rule named the team and relief teachers, and the absent teacher needs the evening to set work.
   Cost: a planner working at 22:00 can cause a message to the absent teacher then.
10. The weekly summary keeps Friday 15:00 though that is after the cut-off. Reason: it is a summary, not a request, and has its
    own setting. Cost: one message after the cut-off on Fridays; set it to 13:00.
11. The team's copy of "Cancelled" and the blocked-bot alert made in the evening wait for the morning time. Reason: "let them
    rest". Cost: the team learns of an evening cancel in the morning (Today shows it at once).
12. The absent teacher sees the relief teacher's name, in the app and on Telegram, only once it is acknowledged. Reason: the
    lead's item 3. Cost: one condition.
13. "Who covers you" goes one a lesson, to the teacher who is away, not to a head who planned it, never for a backup, never once
    the lesson is over. Reason: the why is to reach whoever covers them. Cost: more messages for a whole-day absence.
14. The morning message counts and names; with nothing to cover, no message. Reason: a message that says nothing teaches people
    to ignore it. Cost: on a quiet morning someone may wonder whether the bot works.
15. The morning message, if the app was down at its time, goes when the app is back, until the cut-off. Reason: late is better
    than never for the day's work. Cost: none seen.
16. The late request waits for its picks, five minutes at most, as PR #99's ping does. Cost: up to five minutes late.
17. The not-acknowledged report keeps its start, an hour before the first period (the lead's "keep"); at 07:00 it may list
    nearly everything sent at 06:45. Cost: one fuller first report.
18. In stage 2, the reports and the all clear go to the same two people as the morning message; request to change, cancelled
    and the weekly summary stay with the whole team. Reason: the lead's item 10 named the morning message, the reports and the
    alert; item 2 gives late matters to the whole team. Cost: one list.
19. On a day with no relief duty, the FYI goes to the whole team, and in the day's hours. Reason: no one is on duty that day.
    Cost: a few messages.
20. The roster lives in Relief settings, saved with it; names are picked from the relief team; someone who left the team is
    passed over. Cost: a roster edit and a rules edit at once by two people overwrite as any settings save does today.
21. Rights: the roster and the times are edited by whoever has `relief.save` today: the timetable committee (personal sign-in
    and the shared code) and the relief team. No new right. Cost: none seen.
22. Weekends and holidays have no morning message; a request then is in the next school day's. Cost: none seen.
23. The blocked-bot alert names the refused message and is written in the History by "The app" (one condition in the History
    hook, which today needs a signed-in person). Cost: one condition.
24. The relief message gets "Open in the app"; files are not sent on Telegram any more. Reason: the lead's item 10, which
    reverses the stage 4 answer "Keep". Cost: the relief teacher needs the app for files.
25. Exam and event backups take part like any absence (morning message, approve, send out), but have no late request ping and no
    "Who covers you", as PR #99's ping had none. Cost: one condition each.
26. The published-timetable side: nothing. Stage 3b (the timetable on a date) is not built.
27. The cut-off stops pings for new requests. It does not stop the not-acknowledged reports or a request to change for a relief
    already sent out for today: those reach the people on duty (reports) or the team (request to change) until the lesson
    starts. Reason: they are the day's own duty, in school hours. Cost: if the lead wants silence after 14:00 for these too, one
    condition each (and an unacknowledged afternoon relief then shows on Today alone).
28. The weekly summary counts reliefs that were sent out, and "on time" runs from when the relief message went. Reason: a relief
    approved in the evening and sent at 06:45 was not late at 06:50. Cost: one field to read.
29. When more lessons are open than the AI's guard allows in ten minutes, the nearest dates are picked first and the rest by the
    next runs. Reason: the AI's choice is the point; waiting a few minutes days ahead costs nothing. Cost: after the deploy, picks
    for far dates appear over some minutes.
30. "A head" in the lead's rule is anyone with `relief.plan`: school leaders, heads of department, subject heads and the relief
    team. Reason: they are the people who may plan for a colleague, on the same form. Cost: if only heads were meant, one
    condition (a relief team member's choice would then wait for Approve).
31. A head's choice is saved approved by the planner and sent out by the planner, at the moment of planning, with no History entry
    of its own; Today shows "Planned by {head} · Sent {time}" and the team may Change it. Reason: the lead's "automatically
    approved", and option 1 (told as soon as planned). Cost: one line of copy.
32. The planner may still choose again or take the teacher off in Plan relief until the lesson starts; each change is a new
    approval and send-out by them, and the first teacher hears "moved" or "No longer needed". Today `absences.choose` refuses
    once approved. Reason: a head who slipped should mend it without the team. Cost if wrong: one condition; the head asks the
    team to Change it instead.
33. "School hours" for relief teachers are from the earliest send-out time to the cut-off of a school day (after the cut-off,
    only about a lesson of that day still to come). A choice made outside them is told at the next start of them. Reason: the
    lead's "in school hours" and "never before morning". Cost: a head planning at 21:00 sees their relief told at 06:45.
34. "24 hours before" is 24 hours before the lesson's start, moved earlier to the last cut-off when it falls outside school
    hours (Friday 14:00 for a Monday lesson). Reason: a day's notice, never at night. Cost: on a Monday lesson the notice is
    three days ahead.
35. A repeat is skipped when its moment had passed when the first message went, or the teacher was told of that relief less than
    12 hours before. Reason: no two messages for one relief in one morning. Cost: one number.
36. The repeats go even when acknowledged, as a short line without buttons; when not acknowledged, the relief message again with
    its buttons, as Remind sends it. Each goes once. Reason: the lead set no condition, and a relief told days ago is easy to
    forget. Cost: a message some teachers do not need.
37. The fallback holds for every approved relief whose teacher is then away at its periods, not for planned ones alone. Reason:
    one rule; a teacher who is away covers nothing, however it was arranged. Cost if wrong: one condition.
38. It is checked by every run of the picks and at once after an absence is saved, for "away" alone; other reasons for "no longer
    free" stay as today (marked on Today). Reason: away is certain; a changed timetable or a duty may be one the team knows
    better. Cost: those still need a person.
39. The teacher who was to cover it gets the existing "No longer needed" if they were told, and the whole team gets "Relief needed
    again" in the day's hours (else at the next morning time, or in the morning message for a lesson of today). Reason: the
    team must approve and send out the new pick in time; the existing message is true. Cost: one message to a sick teacher.

40. The work reminders look at each day of the absence on its own, and at the lessons that need cover, are still to come and
    have no text, link or file. Reason: what the relief teacher needs is work for their lesson. Cost: none seen.
41. 18:00 and 07:00 are settings, defaults as the lead said. 18:00 is on the calendar day before (Sunday for a Monday). Reason:
    the evening closest to the lesson. Cost: a Sunday message to an absent teacher.
42. Every absence with lessons missing work gets the reminders still to come, whenever it was sent, not only one sent after
    15:00. Reason: the lead's aim is work set before the day; after 15:00 is the case where no other reminder comes. Cost if
    wrong: one condition; teachers who asked in the morning get one or two reminders the lead did not name.
43. A reminder within 30 minutes of the request is skipped (a request at 06:50 for today gets none). Reason: its confirmation
    just said "no work set yet". Cost: one number.
44. The planned absence's 15:00 reminder stays, and both work reminders may follow it. Reason: acknowledging and setting work
    are two things. Cost: up to three messages for a planned absence left untouched.
45. The work reminders go in the evening and at 07:00 on purpose: the quiet rule is for the team and relief teachers. Not to a
    backup, not to someone not on Telegram, each once. Cost: none seen.
46. The message points to the app (My absences), not to `/relief`, because `/relief` cannot add work to an absence already sent.
    Reason: true to the code. Cost: if the lead wants work set on Telegram after Send, that is a new `/relief` step, not in
    this design.
47. Work set after the relief teacher was told is not sent to them on Telegram (as today); it shows in Reliefs I'm covering.
    Cost: a relief teacher told at 06:45 who does not open the app misses work set at 07:05.

## Questions for the lead

Asked on 23 November after a reviewer read this document as a builder would. Question 1 is answered. The draft's question on a
relief planned days ahead is taken out: the lead's answer on planned relief (items 13 and 14) settles it by analogy (my call 3).
For 2 to 4 the document is written with the first reading in each; approving it as it stands approves those.

1. **The 2 pm cut-off.** You said: "cut off time for sending out is 2 pm for the day's relief after that it is for the next day".
   A request comes in at 14:10 for a lesson at 14:40 today. As written here (my call 8) it pings nobody, but a team member who
   sees it on Today can still approve and send it out. Or is 14:00 a hard stop: nothing is sent out for today after it?
   **The lead's answer (23 Nov): "Pings stop, sending allowed".** So it is as written in my call 8, which is now the lead's.
2. **Who covers you.** "...will be informed which officer is covering the person when the person has acknowledged": read here as
   the relief teacher acknowledging their relief. Then the teacher who is away is told that teacher's name. Is that the reading?
   (The other one: when the absent teacher acknowledges an absence that was planned for them.)
3. **Sentences about the reporting officer.** "The form should not say who will be told." Today the app's form says
   "{officer} is not on Telegram: please tell them yourself." when that is so, and `/relief` on Telegram says either that or
   "{officer} will be told." Take all three out, or keep the "not on Telegram" one (it says who will NOT be told)?
4. **The standby.** On a day with a roster line, if nothing has been sent out by some time (say 07:15), should the standby be told
   on Telegram? As written, nothing more is sent: the standby has the same morning message.

## Left to the builder

- The exact shape of the "sent out" mark and of the roster in the settings file; the state name for "approved, not sent out".
- Keys for the new messages (morning, late, covered, blocked, FYI, the two repeats, needed again), and how each is claimed once;
  the repeats keyed by the relief's own key, apart from Remind's `:r{n}`, and Remind's five-minute wait counting them.
- Where a head's choice is saved approved and sent out (`absences.new`, `absences.choose`, the takeover of a backup's lessons in
  `absences._may_replace`); letting `cover.drop` (or a sibling) send an approved relief back to open for "away" alone, with
  `free._absent_then` as the test.
- How `due` gates each kind by the times (one helper), and what `still_true` asks of each new kind.
- Moving `fill.due_at`'s use: picks at once, the reminder still by `remind_at`.
- Page layout beyond the mockups; the 12 px under Today's buttons left from stage 4 (the lead's "fix next time") goes when Today
  is touched here.
- Where the work reminders are worked out (beside `tell._planned`), their two times in `settings.times`, and their keys.
- The tests: a fixed clock through a whole day (21:00, 06:30, 06:45, 09:10, 14:05), a weekend, a holiday, an off day; a held
  relief changed and cancelled before 06:45; a blocked bot in the evening; a head's choice planned at 10:00 and at 21:00 for
  the next day, for a Monday and for three days ahead (first message and repeats); a relief teacher who falls sick after
  acknowledging; work reminders for requests sent at 10:00, 16:00, 23:00, 06:50 and 07:10, for a Monday, and for work set
  between the two.

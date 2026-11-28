# Relief: clearer tabs, changing a request, seeing a pick, and the morning re-look

Date: 27 November 2026. Status: **approved by the committee lead on 27 November 2026** ("Approved, plan it"). Mockups, all with made-up names:
`2026-11-27-relief-tabs-mockups.html` beside this file (parts 1 to 7).

The relief module is live on ct-timetable: teachers ask for relief, heads plan it, the AI picks a relief teacher for each lesson
by the school's written rules, and the relief team approves and sends out on the Today tab. On 27 November the lead asked for
the tabs to be renamed, a new tab, an answer about "Needs a nudge", a way to see a relief teacher's day, and in the conversation
that followed: a button to ask the AI to choose again with a note, changing and cancelling a request, a "Notify all" button and
a morning re-look of the whole day. This document turns that into four pieces of work, each its own branch and pull request, for
the lead to approve before anything is planned or built.

Everything below that is not in the lead's own words is marked **my call**, with its reason. The lead may change any of them.

## What the lead said

The lead's words, as written, in the order given (the first four reached this session through the session that started it):

1. Rename the tabs: "What's in" → **All Relief Requests**; "Today" → **Today's Relief Assignments**; "Plan relief" →
   **Relief Planning**; "Load" → **Term Relief Report**.
2. "One more button: **Planned Relief Assignments**".
3. "What is **Needs a nudge**? Is it a reminder to set work?"
4. "When I assign the relief, is there a way to see the relief teacher's timetable and where the system has slotted the relief,
   e.g. so I can see that he would teach a five-hour stretch, which is not ideal?"
5. "Show me how it looks like" (the mockups were drawn).
6. "I may need another button to ask the AI to re choose, but I can optionally add on a small prompt to say select these people
   and see if they are available" and "The prompt is in plain text".
7. On the new tab as drawn (mockup part 2): "Yes, as drawn".
8. On a long run (warn only, or warn and avoid): "B, warn and avoid".
9. "Also the relief team can cancel their relief requests completely or edit their requests, ie I can set no relief needed".
10. "Best to edit the date and times as well as cancel the entire thing , if we need to cancel best to put a reason too and
    marking Relief not needed ( reasons stated could be optional )".
11. Asked who else may change dates and times: "Team and the teacher"; then "Leave heads in, limit is 3 hours and 40 mins".
12. "Rename it to Not acknowledged, usually our acknowledgement is by 740 on the day itself, also sometimes the relief requests
    might come in the morning itself, the AI should relook and and redeploy the assignment again based on needs, example the day
    before. FAJT EL was assigned for a SS lesson, suddenly a planned relief comes in requesting EL teacher or a EL teacher declare
    absent sick on the morning, could it relook. So cutoff is 7 am so after that the relief team will need to intervene and might
    rejig if something late comes and need to change the assignment."
13. On "Not acknowledged" being the absent teachers who have not acknowledged a head's planning: "Ok this is correct … but you
    can comebine for those who are informed on the day itself and they need to acknowledge too." On whether the re-look may move a
    relief already acknowledged: "this is HOD who planned, AI should not make the change unless it is the relief team even if it
    is not acknowledged."
14. Asked whether the re-look's moves before 07:00 may reach teachers without the relief team: "Yes the relief team can only send
    out all the notifications for them to acknowledge, there should be a notify all button too. So teachers may see their planned
    relief and can acknowledge once the notification is out." (Read as: no exception; nothing reaches a teacher until the relief
    team sends it out. The lead did not object to that reading.)
15. Asked whether a head's own choice when planning should now wait for Notify all: "Keep it going at once".
16. On how the re-look works: "A, one fresh look at the whole day".
17. Asked whether a relief teacher who has not acknowledged shows in "Not acknowledged" as soon as told or only after 07:40:
    "As soon as told".
18. "I think for planned relief, the telegram notification goes out on the morning itself. they might get confused if they
    received another time, can I change the timing, say how many hours before the class or none which defaults when relief team
    sends all notification at once".
19. Asked whether that timing is for a head's planned relief only or for every relief: "Only a head's planned relief, I think no
    more than twice, the idea is that you do not want the RT to receive to many messages, maybe 24 hours before the actual
    lessons and morning notifcation".

What "Needs a nudge" means was answered in the conversation: an absence a head planned for a teacher, which that teacher has not
acknowledged, once it is past "Remind the absent teacher at" (15:00) on the school day before its first lesson; the same moment
the Telegram reminder "please acknowledge your relief … and set work" goes. A teacher's own request is never in it.

## Goals, non-goals, anti-goals

Goals: tab names the relief team uses; one place to see every relief still to come; the relief team (and the teacher and the
head) can correct a request instead of cancelling and asking again; the person approving sees what a pick does to the relief
teacher's day, and long runs are avoided; the relief team can ask the AI again in plain words; a late request in the morning
gets the whole day rearranged before 07:00 instead of being squeezed in.

Non-goals: the AI does not send anything to anyone; the relief team still releases every relief (except a head's own choice,
which goes at its own time, piece 3.6); no change to how teachers ask for relief, or to Telegram's buttons beyond the words
below; no new rights.

Anti-goals (a failure even if it works): a relief teacher told of a move the relief team never released; a head's or the relief
team's own choice moved by the app; a real staff name in the repository, the mockups or the tests; old links (Telegram buttons
to `/relief#today` and the like) that stop opening the right tab.

## Constraints

- Plain JavaScript pages and Flask, as the rest of the relief module; tests `.venv/bin/python tests/<name>.py` and
  `node tests/<name>.test.js`; no real model call in a test (`relief.pick.CALL` or `mock`).
- What goes to the AI stays without names: every person is a label ("Teacher 3"), names in the rules and in the relief team's
  note are replaced by labels or "another teacher" (`relief/pick.py`'s matcher). No reason, remark, reporting officer or work.
  `docs/DEPLOY.md` says what goes to the model and must say the new parts.
- The period times are the published timetable's own (`exams.days.bounds`; 20 minutes at CTSS).
- One clock: school time (`relief.fill._when`), as now.

## Approaches

**The order of the work (my call).** Four pieces, each its own branch, plan, review and pull request, smallest first, so the
lead has something early and each can be checked on its own: 1 words and the new tab; 2 changing a request; 3 seeing and
steering a pick; 4 the morning re-look. Piece 4 needs piece 3's long-run mark and the AI note; piece 2 and piece 3 do not need
each other. The other way, one large branch, was set aside: a month of the lead's waiting, and one review too large to be good.

**A long run (the lead chose B).** A: only warn. B (chosen): warn and avoid: the long run is a mark, as "prefers not" is, so the
app's own order puts the teacher after the unmarked ones and the AI is told to prefer a teacher with no mark where the rules
leave a choice. B uses what the app already has; its cost is that, to avoid a long run, a teacher with a slightly heavier week
may be picked now and then.

**The morning re-look (the lead chose A).** A (chosen): one fresh look at the whole day: the AI is sent every lesson of that day
it may rearrange, who is free for each, and the rules, and answers with a whole arrangement, so it can see a swap (the English
Flexi Adjunct Teacher to the English lesson, someone else to Social Studies). The app checks every pick before anything is kept.
B: free the lessons and pick them again one at a time, hardest to fill first: simpler, but it finds a swap only when the order
happens to suit it. B is kept as the fallback when the AI cannot be reached.

**The new tab (the lead chose "as drawn").** Read-only, with "Open this day" to Today's Relief Assignments on that date, where
Approve, Change and Split already are. Acting on every row in the new tab was set aside: it would copy Today's tab.

## Piece 1: the words and the new tab

1. **Tab names.** My absences · Ask for relief · Reliefs I'm covering · **Relief Planning** · **All Relief Requests** ·
   **Today's Relief Assignments** · **Planned Relief Assignments** (new) · **Term Relief Report** · Weekly summary. The tabs keep
   their addresses (`#plan`, `#inbox`, `#today`, `#load`), so every link already sent still opens the right tab; the new tab is
   `#ahead` (**my call**). Each tab's own heading, help lines, empty-list sentences, refusals that name a tab ("Only the relief
   team can open What's in.", "it is changed on the team's Today page" and the like), `README.md`, `docs/DEPLOY.md`, the Telegram
   texts that name a tab, and the tests that pin those texts are changed to match. The Telegram button "Open relief today" reads
   **"Open Today's Relief Assignments"** (**my call**: it names the tab it opens). Today's own heading "Relief on Thu 3 Dec" stays:
   it names the date, not the tab. Words in code comments are changed where they name a tab a person would look for.
2. **Not acknowledged** (was "Needs a nudge") on All Relief Requests lists a request when either
   - the absent teacher has not acknowledged a head's planning, past the reminder time (as now), or
   - a relief of **today** has reached its relief teacher (sent out, and its time has come) and that teacher has neither
     acknowledged it nor asked to change it: **as soon as it reaches them** (the lead: "As soon as told"), so from the earliest
     send-out time, 06:45; one whose lesson has started stays in the list until the day ends, marked "started" (**my call**: the
     same reliefs as the 15-minute report, which already lists them for the team on Telegram).
   Each row says who has not acknowledged: "absent teacher", or "relief: {name}, {periods}" for each such relief. The view's
   button reads "Not acknowledged (n)"; the empty sentence "Everyone has acknowledged."
3. **Planned Relief Assignments** (new tab, relief team only, as Today is): every relief on the school days **after today**,
   grouped by date with that date's line ("1 teacher away · 2 lessons · 2 waiting for you"), one row a cover as on Today (time,
   lesson, for whom, relief teacher, status in Today's words), and "Open this day" on each date's rows, which opens Today's Relief
   Assignments on that date. A choice "Next 2 weeks" (the default) or "This term" (to the end of the term today is in), and
   Refresh. A lesson an exam or event stops shows "Not happening", as on Today. Read-only. Once piece 3 is in, a row whose relief
   teacher has a long run shows the mark.

## Piece 2: changing a request

Who may: the absent teacher (on My absences), the head who planned it (on Relief Planning's "Planned by me") and the relief team
(on All Relief Requests, through a new **Edit** button on each request with a date today or later). These are the same people
who may cancel it or mark a lesson not needed today. A backup made for an exam duty or an event cannot be changed this way: it
follows the exam schedule (**my call**: the next sync with the exams would undo the change).

1. **Change the dates or times.** The same controls as Ask for relief: Today / Tomorrow / Pick dates (the two-month calendar),
   and Whole day / Some periods with from and to. Before saving, a short list says what the change does, lesson by lesson:
   - **Kept**: a lesson in both; it keeps its relief teacher, pick, approval, acknowledgement and work.
   - **Added**: a lesson only in the new dates or times; a relief teacher is picked for it at once (or, from piece 4, by the
     re-look), as for a new request.
   - **No longer needed**: a lesson only in the old; its relief ends. A relief teacher already told is told "No longer needed",
     as when a backup's lesson goes. Its work files go.
   A lesson dated before today, or one of today that has started, is never dropped (it is history, or under way). The same
   checks as a new request: school days only, the teacher's other absences may not overlap, a lesson shared with a co-teacher who
   is there is not needed. A reason for the change is optional. The record keeps when and by whom it was changed, and All Relief
   Requests shows it as new to the relief team (as a backup's change is shown today).
2. **Relief not needed** on one lesson: on My absences and Planning (as now), on the Edit view of All Relief Requests, and as a
   button on each row of Today's Relief Assignments. **The reason is optional everywhere** (today it is required; **my call**:
   the lead said reasons for this "could be optional", and one rule for everyone is simpler). "Needed again" undoes it, as now.
   On a row that is one part of a split lesson the button reads "Relief not needed for the whole lesson" and ends every part
   (**my call**: a part alone would need a new kind of record).
3. **Cancel the whole request**: on the Edit view too; **a reason is required**, as now.
4. **Who is told.** When someone other than the absent teacher changes, cancels or marks a lesson of the request not needed, the
   absent teacher is told on Telegram what changed and by whom (**my call**; today a teacher whose own request the team cancels is
   not told). The relief teachers already told get "No longer needed" or "Cancelled", as now. The relief team is told on Telegram
   when a teacher changes their own request for today (as for a late request today). The reporting officer of a teacher's own
   request is told the new dates and times, as they were told the first ones. When a change adds a lesson to a request a head
   planned, the absent teacher must acknowledge again (they have work to set for it), as when a backup gains a lesson today; a
   change that only takes lessons away keeps the acknowledgement.

## Piece 3: seeing and steering a pick, and when reliefs are sent

1. **Their day.** Under the relief teacher on each row of Today's Relief Assignments, a "Their day ▾" button opens a strip of
   that teacher's day on that date, period by period: their own lessons (class and subject), other reliefs, exam duties and
   events, and this relief marked; free periods empty; a line "12 periods teaching · 3 relief (this one) · 1 exam duty"; a key.
   Lessons an approved exam or event stops are shown as free.
2. **The free list** (Change on Today, and Relief Planning's choice, which draw the same list) shows each free teacher's day as a
   thin strip beside their name, with this relief marked where it would go; pointing at a block names it ("4A Maths, P10–P12").
3. **The long-run mark.** A run is lessons, reliefs and exam or event duties back to back with no free period between (a free
   period in the teacher's own timetable, recess included, ends a run). When this relief would make the run it sits in longer
   than the limit, the teacher carries the mark "{h} h {m} min in a row with this" in the free list, on Today's row, in the new
   tab, and in what the AI is sent. As a mark, it puts the teacher after unmarked ones in the app's own order within the same
   group (Flexi Adjunct Teachers still come first, as the rules say) and the AI is told to prefer a teacher with no mark.
   **The limit: 3 h 40 min** (a run of exactly 3 h 40 min is fine); a box in Relief settings, in hours and minutes; empty turns
   the check off. The AI is also sent each teacher's busy periods that day (no classes, no names), so its reasons can say why.
4. **Ask AI again.** A button on each row of Today's Relief Assignments whose lesson has not started and which is not a lesson
   that does not happen. It opens a box "Anything the AI should know this time? (optional)" for a note in plain words (up to 300
   characters, **my call**), and "Ask the AI". The AI picks again from those free then with the note; names in the note are
   replaced by labels before it goes. The app itself checks each name in the note that is not on the free list and says why, in
   one line each: teaching then (class and subject), away, on an exam duty or at an event, over a limit, or never given relief.
   The answer shows "You asked: …", the new pick with the AI's reason, and:
   - on a row not approved yet: the new pick takes its place, waiting for approval as any pick;
   - on an approved row: the new pick is offered beside the approved one, "Approve {new}" or "Keep {old}"; nothing changes for the
     teacher already chosen until "Approve {new}". Then, as with Change today, the teacher moved off is told "moved, you're free
     then" (in school hours for relief teachers, as now) and the new one is told when it is sent out (Send out or Notify all).
   When the AI cannot be reached, the app's own order picks and says so, as for every pick.
5. **Notify all.** A button at the top of Today's Relief Assignments that, in one press, on the date shown: approves every pick
   that "Approve all" approves (requests to change and Ask AI again offers on approved rows are left for their own buttons, and a
   line says how many were left); approves the re-look's rearrangement waiting for that date (piece 4); and sends out every
   approved relief not sent out yet (one sent out outside school hours is held to the earliest send-out time, as now). The two
   buttons there now stay for working row by row.
6. **When a head's planned relief reaches the relief teacher.** A head's own choice is still approved at once and never moved
   by the re-look, but it no longer goes out at the moment it is planned. A new setting in Relief settings, "A head's planned
   relief reaches the relief teacher [24] hours before the lesson", **24 by default** (the lead's "maybe 24 hours before"): it
   goes by itself at that moment, moved out of the night as the 24-hours-before reminder is today (to the last cut-off before
   it, when it falls outside school hours). **Empty**: it waits for the relief team, and goes with Notify all or its row's Send
   out (until then Today's Relief Assignments counts it as "Approved, not sent out"). Either way, Notify all or Send out on that
   date sends it at once if pressed sooner. A head who plans for a lesson less than that many hours away has it go at once (in
   school hours). Planned before this change, a relief already sent out stays as it is.
7. **No more than two messages about one relief (the lead: "no more than twice").** A relief teacher gets the relief itself
   and, when it reached them before the morning of its day, one short reminder on that morning; the "24 hours before" reminder
   is no longer sent (**my reading** of the lead's words, for every relief, not only a head's: it is the one a teacher told
   days ahead would otherwise get as a third message). Not counted: a reminder the relief team sends with Remind, and the
   messages that say something changed (moved, no longer needed, not happening, on again, cancelled).

## Piece 4: the morning re-look

1. **When.** Whenever something new comes for a date: a new request (a teacher's own or planned), a lesson added by a change
   (piece 2), a lesson needed again, or an approved relief teacher who is now away. Only before the **re-look time on that date,
   07:00** (a new time in Relief settings, "Rearrange the day by itself until"). After it, nothing is moved by itself: a new lesson
   is picked on its own, as now, and the relief team rearranges by hand with Change and Ask AI again.
2. **What may move.** Picks made by the AI or by the app's own order, waiting or approved, sent out or not, acknowledged or not.
   **Never moved:** a head's own choice when planning, and the relief team's own choice (**my call** on the team's: the lead said
   the AI should not make a change "unless it is the relief team"): Choose, Change, any pick got with Ask AI again, "Keep {old}",
   and "Keep as it was" on a rearrangement. Approving an AI or app pick, or a rearrangement, does not make it the team's choice:
   until the re-look time a later re-look may still move it. Also never moved: a lesson that has started; a relief with a request
   to change still with the team; a lesson that does not happen. Those are sent to the AI as fixed: their teachers are busy then.
3. **How.** One call to the AI with the whole day: each lesson it may arrange (subject, level, periods), who is free for each
   (labels, as now, with each teacher's week, relief so far, marks including the long run, and busy periods that day), the
   rules and the limits. It answers with one label and a short reason per lesson. The app checks every answer (free then, not on
   two lessons at once, under the day's limits) and keeps a lesson's current pick where an answer fails the check. If the AI
   cannot be reached, the app re-picks the movable lessons one at a time by its own order, hardest to fill first (fewest free);
   what that changes is handled as below.
4. **What changes: one rearrangement, taken or kept whole (my call).** The changes one re-look makes on a day hang together (the
   English teacher can take the English lesson only once someone else has Social Studies), so they are one rearrangement:
   - when it moves no approved relief, it is made at once: each changed or new pick waits for approval as any pick;
   - when it moves an approved relief, nothing changes yet: above the rows a box says "The re-look suggests 2 changes", lists
     them with the AI's reasons, and offers "Approve the rearrangement" or "Keep as it was"; each row it touches says so. The
     approved teachers keep their reliefs and are told nothing until it is approved. Notify all approves it too. On approval, as
     with Change today, a teacher moved off is told "moved, you're free then" and a new one is told when it is sent out. On "Keep
     as it was", the lessons in it that had nobody are picked on their own, as now. A later re-look of the same day replaces a
     rearrangement still waiting.
   Nothing new reaches any teacher until the relief team sends it out (a head's own choice is never moved, and goes at its own
   time, piece 3.6).
5. **Who sees it.** The rows say what the re-look did and why. The 06:30 morning message to the relief team says how many changes
   the re-look suggests, when there are any. Each change is written in the cover's history ("re-look").

## Calls made in this design (the lead may change any)

1. Four pieces in this order, each its own pull request.
2. Tab addresses stay; the new tab is `#ahead`.
3. The Telegram button reads "Open Today's Relief Assignments".
4. Not acknowledged includes today's relief teachers on the same rule as the 15-minute report, started ones until the day ends.
5. "This term" on the new tab means to the end of the current term.
6. A backup for an exam or event cannot be changed (only by the exam schedule).
7. The reason for Relief not needed is optional everywhere, the teacher's My absences included.
8. The absent teacher is told when someone else changes, cancels or marks part of their request not needed; the team is told
   when a teacher changes their own request for today.
9. The AI note is up to 300 characters.
10. Ask AI again on an approved row offers the new pick beside the old; nothing changes until "Approve {new}".
11. The re-look never moves the relief team's own choices, as well as a head's; approving an AI pick does not make it the team's.
12. The re-look time is a setting, 07:00 by default; the long-run limit is a setting, 3 h 40 min by default.
13. A re-look's changes are one rearrangement, approved or kept whole; Notify all approves it.
14. Notify all leaves requests to change and Ask AI again offers on approved rows for their own buttons, and says how many.
15. A teacher moved off is told when the new teacher is approved, as Change does today; the new teacher when it is sent out.
16. A change that adds a lesson to a planned request asks the absent teacher to acknowledge again; the reporting officer is told
    the new dates.
17. On a split lesson, Relief not needed ends the whole lesson.
18. A head's planned relief goes 24 hours before its lesson by default (moved out of the night as today's 24-hour reminder
    is); empty waits for the relief team; a relief already sent out before the change stays as it is.
19. The "24 hours before" reminder is dropped for every relief, so a relief teacher gets at most the relief and one morning
    reminder; the team's Remind and the change messages are not counted.

## Left to the builder

Route names and shapes; how the free list's answer carries each teacher's day (one answer, not one request per teacher); the
exact field the re-look's suggestion is kept in on an approved cover; how the whole-day call counts in the AI's usage guard and
its size limits; the wording of lines not quoted above, in the page's plain style; the tests, which must use made-up names only.
Each piece ends with every suite passing, a browser check on a scratch server with made-up data, a whole-branch review that also
runs on the school's real setup (numbers only, never names), and a notes file beside its plan.

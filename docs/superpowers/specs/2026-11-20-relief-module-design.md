# Relief: planning, asking for and assigning relief, with Telegram and an AI that picks by the school's rules

Date: 20 November 2026. Status: **approved by the committee lead on 20 November 2026** ("Approved, plan it"). Reviewed once by a
builder's reading; the lead answered its two open questions (period unit, one published timetable). The fourth of the four
projects agreed on 9 November 2026 ("relief via Telegram with AI assignment"). Mockups, all with made-up names:
`2026-11-20-relief-module-mockups.html` beside this file (open it in a browser; one tab per screen).

## Why

Relief is arranged today in the CTSS portal, a separate school app. Its Planned Relief page is a form where
management types the absent teacher, the class, the periods and the relief teacher's name. It suggests nothing: whoever
fills it in has to work out who is free. The day's unplanned relief is made in yet another tool and uploaded to the
portal as a PDF or photo.

The committee lead wants relief to live in this timetable app, because the app holds the published timetable (who
teaches what, when, and so who is free) and because relief is part of what the app should give any school that uses
it. The portal will read from the app through an API the lead will make. In the lead's words:

- Management "can do planned relief similar to this but it will be easier for them to assign as it will tell them
  which teachers are available via the published timetable for that time period based on who is available in their
  department and the subject closest, followed by others and their subjects (AI chatbot can help them here to help
  them allocate)".
- If the relief is not planned, "teachers can submit their relief request through Telegram or app link", naming their
  reporting officer; it "will cross check with planned relief"; with no planned relief "the AI will look at the set of
  relief rules to see who gets assigned and also keep track of the overall load of the teacher".
- "Once it is assigned, it will inform the relief team its allocation and reason for allocation, relief team will
  approve before sending the notification via Telegram, teacher will need to acknowledge and the team will receive a
  report at 15 mins interval of who did not acknowledge."
- "A teacher who wants to dispute the relief can click on Request to change to state why they reject, AI will notify
  the team and make a new recommendation."
- A weekly summary "sent to all relief team members", which "could be accessed anytime through the relief team module".
- "I also want relief teacher to be assigned and updated on the published timetable for that day only."
- After the first mockups: "plan relief and relief submission should be another module for both management and
  teacher. Relief team can see what is in and who has submitted. Teacher who is absent must also sign in to
  acknowledge the planned relief and set work so that instructions will be given to the assigned relief, or come and
  cancel if not needed."

The relief rules today, in the lead's words: "check the planned first, then we allocate the Flexi Adjunct Teacher as
the first rule, no more than 3 periods, try to match subject and try to spread it out over the week, then after that
normal teachers with the lowest load first and spread it out." The lead added: "the rule can be set later, we use AI
to allocate."

## Goals

- Management plans relief ahead and sees, for each lesson, who is free then, ranked: same department and subject
  first, then same department, then everyone else, each with their load.
- Teachers ask for relief themselves, on the app or on Telegram, and set work for each lesson.
- The absent teacher acknowledges a relief someone else planned for them and sets work, or cancels it.
- The relief team sees everything that comes in, gets the AI's pick for every open lesson with a reason, and approves
  or changes it before anyone is told.
- The relief teacher is told on Telegram, acknowledges or asks to change; the team is told every 15 minutes who has
  not acknowledged.
- Load is counted and shown; a weekly summary goes to the relief team.
- The published timetable shows the relief on that date only.
- Any school using the app can set its own people, calendar and rules.

## Non-goals

- Replacing the portal or changing it. The portal's own relief pages are left alone; it may later read this app
  through the lead's API.
- Generating or changing the timetable. Relief never changes the published timetable itself, only what is shown on
  one date.
- Leave records, medical certificates or HR approval of absences. The app records the reason a teacher gives and
  nothing more.
- Per-teacher sign-in for everything else ("who sees what", project 3). This project adds personal teacher codes
  because relief needs them; what else those codes open beyond relief and the teacher's timetable is project 3's
  question.

## Anti-goals (would make it a failure even if it works)

- A relief teacher is told before someone on the relief team approved it.
- The AI picks someone who is teaching then, is away that day, or is over a limit the school set, and it reaches the
  team as if it were fine.
- Staff names, absence reasons or work instructions are sent to the AI provider.
- At 7 am the page waits on the AI and the team cannot act. Without the AI, everything still works with the app's
  own order.
- A relief shows on the published timetable on any date other than its own.

## Who uses it

| Who | How they sign in | What they do |
|---|---|---|
| Every teacher | their personal code (new) | ask for relief, set work, see their absences, acknowledge or ask to change a relief they cover, acknowledge or cancel relief planned for them |
| Management | personal code; on the Management list | everything a teacher does, plus plan relief for a colleague |
| Relief team | personal code; on the Relief team list | everything a teacher does, plus the relief team module, and entering an absence for anyone (for a teacher who phones in) |
| Reporting officer | personal code (any teacher) | is told when someone who names them asks for relief |
| Committee | COMMITTEE_CODE, as today | prints the personal code slips; sets up the relief settings the first time (who is on the two lists) |

Management and the Relief team are lists of people kept in the relief settings, not new shared codes, so every action
is recorded against a person ("Set by", "Approved by"). They are picked from the teachers of the published timetable;
a member of staff who teaches no lessons (a non-teaching Vice-Principal, an admin officer on the relief team) can be
added by name and gets a personal code too.

**Which data relief reads.** Everything about teachers comes from the setup kept with the published timetable, not
from the setup the committee is editing: names, departments (including second departments), roles, subjects taught and
the step 6 rules. While the committee builds next term's setup, relief keeps using the published one.

## Approaches considered

How the AI allocates was the one open choice about the build. Three ways were considered:

- **A. The app allocates; the AI only helps.** The rules become a fixed list of settings (planned first, Flexi
  Adjunct Teachers first up to a daily limit, subject and department match, lightest week, a "never" list). The app
  ranks and writes the reason itself; the AI only runs the helper chat, with no school data sent. Instant, free, the
  same answer every time, works without the AI; a school rule that does not fit the list needs the app changed.
- **B. The AI allocates; the app checks it.** The rules are written in plain words. The app makes a shortlist of
  teachers who can take the lesson, with their numbers, replaces names with labels, and the AI picks by the written
  rules and writes the reason. The app checks the pick is on the shortlist and puts the names back; if the AI is
  unavailable or its answer fails the check, the app falls back to A's order and says so. Any rule written in words
  works; each pick takes a few seconds and costs a little, and picks can vary slightly.
- **C. The AI decides from the whole timetable.** Dropped: it could pick someone who is teaching, and it sends
  everything to the provider.

**The lead chose B.**

## What it is

Two modules behind a fourth card on the landing page, **Relief** ("Enter your personal code"). After signing in, each
person sees the parts that are theirs (mockup tab 1).

### Module 1. Relief requests (everyone)

**My absences.** Every absence of mine: planned by management, or asked by me. Each shows its lessons, their relief
teacher (or "the relief team will assign"), the work set, and a status.

**Ask for relief** (mockup tab 3), on the app or on Telegram:
- which day (today, tomorrow, several days, another day), whole day or some periods, a reason (Medical, Child sick,
  Course, Other with a line of text);
- the teacher's lessons in that time are listed from the published timetable for that date; they never type classes
  or periods;
- **work for each lesson**: text, plus a file or a link (SLS, Google Drive); "same as before" and "later, in the app"
  are allowed;
- the reporting officer, remembered from the last time; they are told on Telegram.

It goes straight to the relief team's "What's in". A teacher may ask for any date, today or later.

**Plan relief for a colleague** (management and the relief team, mockup tab 2): pick the date and the absent teacher, whole day or
some periods, a reason and remarks for the relief team. The teacher's lessons in that time are listed. For each
lesson, management may choose a relief teacher from the ranked "free then" list (below) or leave it for the relief
team. The helper chat sits beside the form. Sending puts it in "What's in" and tells the absent teacher. **Download**
gives the planned relief for a range of dates as a spreadsheet file; there is no Upload in this project.

**Lessons with more than one teacher.** When the absent teacher shares a lesson with others who are not away (a
co-taught lesson, Class Parents taking CP Time together), the lesson is listed as "Ms … is there: no relief needed",
and the planner or the absent teacher can still ask for cover for it.

**Acknowledge, set work or cancel** (mockup tab 4): when someone else planned the absence, the absent teacher is told
on Telegram at once ("Relief planned for you", Acknowledge and set work / Not needed: cancel) and sees it in My
absences. They acknowledge, set work for each lesson, and may mark one lesson "Not needed" or cancel the whole
absence with a line saying why. A cancellation tells the relief team, the planner, and any relief teacher already
told. If they have not acknowledged by 15:00 the day before (a setting), they get one reminder and the absence shows
under "Needs a nudge" in What's in. The relief goes ahead whether or not they acknowledge.

**Reliefs I'm covering.** Every relief given to me, with the lesson, the room, whose class, the work set and its
files, and Acknowledge / Request to change: the same two buttons as the Telegram message, for anyone not on Telegram.

### The "free then" list

Used by management's planning, the relief team's Change, and as the AI's shortlist. For one lesson on one date:

- Free means: not teaching at any period of the lesson on that date's cycle day (the published timetable), not away
  that date at those periods, not already given relief that overlaps, not "Not available" then by a Must rule on step 6
  (part-time days, fixed meetings), and not on the school's "never" list.
- A teacher who is free but inside a "Keep free together" time of their department, or "Not available" by a Should
  rule, stays on the list, marked ("department meeting time", "prefers not"), after the others in their group; the AI
  is told the same.
- Grouped by the **absent teacher's** department(s) and the **lesson's** subject: same department and teaches this
  subject; same department, other subjects; other departments (with their subjects). A teacher's second department
  counts as their department.
- Teachers with no lessons at all are on the list (free all day, a light week).
- Inside each group, lightest week first. Flexi Adjunct Teachers are marked; one over a checked limit is shown dimmed
  with the reason and may still be chosen by a person.
- "Show the ones teaching then" folds out the rest, for reference.

### Load

- **Periods** everywhere in relief (limits, load, summaries, what the AI is told) are the published timetable's own
  periods, whatever their length at a school. At CTSS a period is 20 minutes, so the Flexi Adjunct limit of 3 periods
  is about one hour of relief a day (the lead: "periods depends on how the published timetable works, about 1 hour
  per day").
- **Week so far** = the teacher's teaching periods in that school week (Monday to Friday, from the published timetable
  on the cycle days of that week) plus every relief period given to them in that week (approved or waiting). Lightest
  first. Ties: fewer relief periods this term first.
- **Relief this term** and **relief today** are counted from the relief records, by the school calendar's terms.
- A cancelled relief no longer counts.

### Module 2. Relief team

**What's in** (mockup tab 5): every absence, newest first: when submitted, by whom and how (management, the teacher
on the app, the teacher on Telegram), for whom, the dates and lessons, the reason, whether the absent teacher has
acknowledged (when someone else planned it), how many lessons have work set, the relief status, and cancellations.
Views: Coming up, Today, Needs a nudge, Cancelled. New since the person last looked are marked.

**Today** (mockup tab 6), with a date choice: every lesson that needs cover that day, in time order, with the absent
teacher, whether work is set, the relief teacher and the reason, and the status (waiting for you, sent, acknowledged,
asked to change, cancelled). Buttons: Approve, Change (opens the "free then" list), Remind, and "Approve and send all
waiting". Counters at the top. The helper chat sits below.

**One relief teacher per lesson**, as a rule. When nobody is free for the whole lesson, the team may split it at a
period boundary in Change and give each part its own relief teacher.

**How a lesson gets its relief teacher:**
1. If management chose one when planning, that is the pick, with the reason "Planned by … on …".
2. Otherwise the AI picks (approach B, below), with a reason that quotes the rule it followed.
3. Either way it waits for the relief team's approval. Nothing reaches the relief teacher before that.

**When the AI picks:** at once for an absence that arrives for today; for a later date, at 15:00 on the school day
before (a setting; Friday for a Monday); and whenever the team presses "Fill now". A request to change also gets a new pick at once.

**Approve** sends the Telegram message to the relief teacher at once (or, when they have not linked Telegram, it waits
in their Reliefs I'm covering and the team sees "not on Telegram").

**Request to change:** the relief teacher gives a line saying why. The team is told on Telegram with the AI's new pick
and its reason; the team approves the new pick, changes it, or keeps the first teacher. Until the team acts, the relief
stays with the first teacher, and their message says so.

**15-minute report** (mockup tab 8): to every relief team member on Telegram, every 15 minutes (a setting) while any
approved relief that day is not acknowledged: who, which lesson, when it starts, when it was sent. A relief whose
lesson has started without acknowledgement is listed once as "started without acknowledgement", then dropped. When all
are acknowledged, one "all clear". Quiet when nothing is waiting. "Remind them again" re-sends to those teachers only.

**Load tracker** (mockup tab 9): every teacher with teaching this week, relief this week, week so far, relief this
term, requests to change this term; filters for department and Flexi Adjunct only; This week / This term; download.
A name opens every relief they took this term, with the reason and who approved it.

**Weekly summary** (mockup tab 10): sent on Telegram to every relief team member at Friday 15:00 (a setting), and a
page for any week: relief periods, absences, the share covered by Flexi Adjunct Teachers, planned ahead against
arranged on the day, acknowledged on time / late / never, requests to change, most relief this week, by department of
the absent teacher, by day, and the full list.

**Relief settings** (mockup tab 12), changed by the committee and the relief team:
- Management list; Relief team list (picked from the teachers on step 4).
- Flexi Adjunct Teachers: the role on step 4 that marks them (none is allowed).
- **Relief rules**, numbered, in plain words, which the AI follows in order and quotes in its reasons. Filled at first
  with the school's current rules (below). Shown under them, fixed: only teachers free then; never someone away that
  day; the relief team approves before anything is sent.
- **Checked limits**, which the app enforces whatever the AI says: the most relief periods a day for a Flexi Adjunct
  Teacher (3), the most for anyone else (blank = none), and a "never give relief to" list of teachers.
- Reporting officer: is told. ("Must approve before relief is arranged" is not part of this project; it can be added
  later if the school wants it.)
- When to fill open lessons (15:00 the day before), the absent-teacher reminder (15:00 the day before), the report
  interval (15 minutes), the weekly summary (Friday 15:00).
- Telegram: connected or not, how many teachers have linked, who has not, print code slips.
- **School calendar**: each term's first day and whether it starts an Odd or an Even week, and the holidays and
  no-school days. The app needs it to know which cycle day a date is (13 Oct 2026 is an Even Tue when Term 4 starts on
  Mon 7 Sep as Odd) and which term a date is in.

The school's current rules, as the first text of the rules box:
1. Use planned relief first.
2. Then Flexi Adjunct Teachers: no more than 3 relief periods a day each; match the subject where possible; spread
   their relief over the week.
3. Then other teachers, lightest week first (teaching periods plus relief periods this week); if tied, whoever has had
   less relief this term; spread over the week.

### The AI's pick (approach B)

For one open lesson:
1. The app builds the shortlist: the "free then" list, minus anyone over a checked limit. If it is empty, the lesson is
   shown as "nobody free" and no call is made.
2. Each teacher on it becomes a label ("Teacher 14"), with only: department(s), subjects taught, whether they teach this
   lesson's subject, Flexi Adjunct or not, teaching periods this week, relief periods this week, today and this term,
   and the relief they already have that day and that week (as periods, not names). The lesson is described by its
   subject, level, periods and date. Names in the school's rule text are replaced by the same labels. No absence
   reason, work, remark or name is sent.
3. The model gets the school's rules and this data and returns one label and a one- or two-sentence reason.
4. The app checks the label is on the shortlist, puts the real names back into the reason, and shows it. If the call
   fails, times out, is refused by a usage guard, or returns a label not on the shortlist, the app picks the first
   teacher in its own order (planned, then Flexi Adjunct Teachers under their limit by subject match then lightest
   week, then everyone else lightest week first) and the reason says "Picked by the app's own order: the AI was not
   available."
5. Several open lessons of one absence are picked one after another, each seeing the picks before it, so "spread it
   out" can work.

The helper chat (management's planning page and the relief team's page) works the same way: the question, the labelled
data for the lessons on screen, and the rules go to the model; the answer comes back in labels and the app puts the
names in. A "Use …" button in an answer is checked by the app like a pick, and nothing is saved until a person presses
it.

The model is called the way `typed.py` calls it today (the same key and model variables, a usage guard for the whole
server, every failure turned into one plain sentence, never raising), with its own system text and a mock for tests. No
test or probe calls a real model.

### Telegram

The app gets its own bot (the portal's bot cannot be shared: a bot's button presses reach only one app). The token is a
Railway variable the lead adds; the app never shows it.

- **Linking:** a teacher opens the bot and sends their personal code; the bot answers with their name and department.
  One Telegram account per teacher; linking again moves it. `/stop` unlinks.
- **Asking for relief:** `/relief` walks through the same questions as the app, with buttons (mockup tab 3).
- **Messages the bot sends:** relief planned for you (to the absent teacher), the reminder to acknowledge, "is away,
  relief being arranged" (to the reporting officer), relief for you (to the relief teacher, with the work set and
  files), cancelled / moved / no longer needed (to the relief teacher), request to change and the new pick (to the
  team), the 15-minute report and the all clear (to the team), the weekly summary (to the team).
- **Buttons:** Acknowledge, Request to change, Acknowledge and set work (opens the app), Not needed: cancel, Approve
  the new pick, Remind them again, Open in the app.
- The reason for an absence goes only to the relief team, management and the reporting officer, never to the relief
  teacher.

### The published timetable on a date

The published timetable gets a date choice: "Usual timetable" (as today) or a date. On a date:
- a relief teacher's timetable shows their relief lessons, marked RELIEF, with whose class it is;
- the class's timetable shows the relief teacher in place of the absent one;
- the absent teacher's timetable shows their lessons crossed out, with who covers each;
- Who's free on that date counts reliefs and absences.

Only approved reliefs show. Students see the change on their class timetable too. On any other date nothing changes.

### Personal teacher codes

Each teacher on the published timetable gets a personal code, made the way personal student codes are (from the
teacher and `SECRET_KEY`), with code slips and a CSV for the committee, as for students. A personal teacher code opens
the Relief module and also what TEACHER_CODE opens today, so a teacher needs only one code. TEACHER_CODE keeps working
as now.

## What is kept

The relief records live in the app's data folder, beside the setup and the published timetable, and survive deploys
and restarts. For every absence and every lesson in it: who submitted it, when and how; the reason; the work and its
files; the planner's choice; every pick (AI or app, with its reason); who approved, changed or cancelled and when; when
the relief teacher was told, acknowledged or asked to change, with their words; and Telegram links. Load and the
summaries are worked out from these records, never kept separately.

A relief for a later date points at a lesson of the published timetable. When the committee publishes again and that
lesson has changed or gone, the relief is flagged in What's in ("the lesson has changed since this was planned")
instead of silently following it.

## Stages

Each stage is its own design check, plan, build and pull request, and each is merged and deployed only on the lead's
word.

1. **Who's who and the calendar.** Personal teacher codes (slips, CSV), sign-in as a person, the Relief card, relief
   settings (the lists, the Flexi Adjunct role, the rules text and checked limits, the school calendar).
2. **Module 1 on the app.** Ask for relief, plan relief with the "free then" list in the app's own order, My absences
   with acknowledge / set work / cancel, work files and links, Reliefs I'm covering.
3. **Module 2 on the app.** What's in, Today with picks (the AI with the app's checks and fallback), Approve and
   Change, request to change and acknowledge in the app, the load tracker, and the published timetable on a date.
4. **Telegram.** The bot, linking, asking on Telegram, every message and button above, the reminder, the 15-minute
   report, the weekly summary.
5. **The helper chat** on management's and the relief team's pages.

Stage 1 is planned first, once this document is approved; each later stage gets its own plan when its turn comes.

## Left to the builder

- Where the records are kept (a SQLite file in the data folder is the obvious choice) and their exact shape.
- How the bot receives updates (a webhook on the app's address with Telegram's secret header is the likely choice,
  since a second copy polling during a deploy would clash) and how timed jobs run (the app runs one gunicorn worker;
  jobs must be safe across a restart and never send the same message twice).
- File size limit and kinds for work files, and who may download them (the absent teacher, the relief teacher,
  management, the relief team).
- Page layout details beyond the mockups; the wording of messages, in the app's plain style.
- The system text for the model and the exact labelled data format.

## Calls made in this design (Claude's, not the lead's; the lead may change any)

- Personal teacher codes, made like personal student codes, as the way people sign in; Telegram linked by sending that
  code to the bot.
- The reporting officer is told, not asked to approve (the lead: "the rule can be set later"); "must approve" is left
  out of this project.
- The relief team, like management, can enter an absence for anyone.
- Relief reads teachers, departments, roles and step 6 rules from the published setup; non-teaching staff can be added
  to the two lists by name.
- Must "Not available" times count as not free; "Keep free together" and Should times are marked and placed last.
- "Same department" means the absent teacher's department; "same subject" means the lesson's subject.
- A lesson the absent teacher shares with someone who is there needs no relief unless asked.
- One relief teacher per lesson; the team may split a lesson at a period boundary.
- Download of planned relief stays; Upload is left out.
- Inside each group of the "free then" list and of the AI's fallback, same subject first, then same department, then
  everyone else.
- Planned relief also waits for the relief team's approval before the relief teacher is told.
- Lessons a planner leaves open are picked at 15:00 the day before.
- A relief stays with the teacher who asked to change it until the team acts.
- Only approved reliefs show on the published timetable; students see them on class timetables.
- The weekly summary at Friday 15:00; the absent-teacher reminder at 15:00 the day before.
- Work can be text, a file or a link.
- Checked limits as separate settings the app enforces, beside the rules text the AI reads.
- Names replaced by labels before anything goes to the AI.

## Known limits

- The app keeps one published timetable, and relief always uses it (the lead: "only one published timetable, relief
  just uses the current published one"). Publishing a new timetable switches relief to it at once; reliefs already
  planned for later dates whose lessons changed are flagged in What's in.

- A teacher renamed on a later setup gets a new personal code and loses the link to their earlier relief records and
  Telegram until the committee links them again.
- The calendar knows terms, Odd and Even weeks and holidays; it does not know a day that follows another day's
  timetable (for example a Monday timetable on a Wednesday). Such a day needs a later change.
- Non-teaching duties (invigilation, events) are not in the published timetable, so the app may call someone free who
  is busy with them; the relief team's approval and "Request to change" catch these.

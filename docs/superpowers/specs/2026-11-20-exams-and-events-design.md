# Exams, tests and events: schedules, seating, invigilators and backups

Date: 20 November 2026. Status: **approved by the committee lead on 21 November 2026** ("Approved, plan it"). Reviewed once by a builder's
reading; the lead answered its one open question (where the students come from: "Add to the setup"). Mockups, all with made-up names:
`2026-11-20-exams-and-events-mockups.html` beside this file (open it in a browser; one tab per screen, numbered 0 to 10).

## Why

The lead asked for "a exam, assessment or adhoc schedule generator (Scheduling and Seating Arrangement generator when
the committee can generate a timetable for exams, example they can generate for the whole school or just certain levels
only, sometimes there is an event for school for certain levels or whole school … So then the relief can either go
through the relief team or not needed)".

What takes the time today, in the lead's words: "When they need to schedule certain teachers only for certain levels but
sometimes the teacher teaches other level, so arranging backup, invigilator and venues allocation takes a lot of time."
When only some levels sit an exam, the other levels keep their normal lessons, and many teachers teach both. Every
invigilation slot has to be checked against that teacher's own lessons; a clash needs a backup for the lesson or another
invigilator; rooms have to be found that no running lesson needs.

The app already holds most of what that checking needs: the published timetable (every lesson, teacher, class, room and
period) and the rooms with their seats. Its setup has a Students step (each student's class and subject groups); the 2027
setup has no students in it yet, and the lead chose to add them there and publish again before the first exam ("Add to
the setup") rather than keep a second student list for exams. The relief module, approved on 20
November 2026 and being built now, adds the school calendar (which date is which timetable day), personal codes for
teachers, and the published timetable on a date. Its design names this gap itself: "Non-teaching duties (invigilation,
events) are not in the published timetable, so the app may call someone free who is busy with them." This design closes
that gap.

## How schools run exams (research, 20 November 2026)

From MOE and school pages: since 2023 Singapore secondary schools have no mid-year exams. Sec 1 to 3 sit a weighted
assessment (WA) in each of Terms 1 to 3, often in lesson time or a level's common slot, and an End-of-Year exam of about
two weeks in Term 4. Sec 4 and 5 sit WAs in Terms 1 and 2, prelims in Term 3, then the national O- or N-Level papers with
the school as the centre. Schools publish per level an exam schedule, a seating plan with a seat number per paper, and a
briefing; students with access arrangements (extra time, a reader, a separate room) are seated apart with their own
invigilator; students usually may not leave before the day's last paper; a missed paper is made up within a few days.
Exams software elsewhere (UK) keeps access arrangements per candidate, seats candidates, and builds invigilator rotas per
sitting from who is available. No public source gives Singapore's invigilator ratios, so the numbers here are settings.

## Goals

- The exams committee sets up an exam or a common test for chosen levels (or the whole school) over chosen dates, each day
  either the whole day off or part of the day, with every paper's date and time.
- The app checks the paper times and then does the slow part: venues, seats for every student, invigilators who are free
  then (shared fairly, backup invigilators kept for replacements), and the list of lessons that need backup.
- The teacher in charge of an event sets it up the same way: the classes, the time, who goes with them.
- Nothing reaches the main site until the timetable committee approves it; then it shows on its own dates only.
- Relief knows about it: lessons of classes on an exam or event need no relief; teachers on duty are not offered for relief;
  backups go to the relief team; duty counts in relief's load.
- Teachers see their duties; students and parents see each paper with its venue and seat.
- Printouts and downloads for the exams committee: seating plans, door lists, class lists, attendance sheets, the roster.

## Non-goals

- **Placing paper times.** The exams committee sets every paper's date and time (the lead: "We set the times"). The app
  checks them. Placing papers could be a later project.
- National exams administration (SEAB entries, index numbers, SEAB forms). The app can still be used for their invigilation
  and seating if index numbers are uploaded later; not in this project.
- Marking, results, attendance taking, or tracking make-up papers beyond adding a paper for a few students.
- Moving a running lesson to another room when an event takes its room. The app flags it; people decide.
- An AI choosing invigilators (approach B below). An AI helper may come later.
- Changing the weekly timetable. A schedule only changes what is shown on its dates.

## Anti-goals (would make it a failure even if it works)

- Anything shows on the main site that the timetable committee has not approved, other than a replacement for someone away
  (the one exception the lead set).
- A student has two papers at once or no seat; a room holds more students than its exam seats.
- An invigilator or an event teacher is picked while they teach a lesson that still runs, are away, or are on another duty.
- Relief offers someone who is invigilating, or asks for relief for a lesson whose class is sitting the exam.
- A lesson is shown as not happening when it actually runs (its class is not on the exam), so a class is left alone.
- Student names, seats or access arrangements are shown to someone who should not see them (the shared student code, the
  AI provider, a teacher outside the school's roles).

## Who uses it

| Who | How they sign in | What they do |
|---|---|---|
| Exams committee | personal code (relief's); on the Exams committee list | make and change exams and common tests freely: papers, venues, seats, invigilators, printouts; send to the timetable committee; replace an invigilator who is away (goes on the main site at once) |
| Teacher in charge of an event | personal code (any teacher) | make and change their event; send it to the timetable committee; replace a teacher going who is away (at once) |
| Timetable committee | COMMITTEE_CODE, as today | approve, send back with a note, or withdraw; sees every change done without approval; keeps the Exams committee list and the exam rooms the first time |
| Relief team | personal code; on relief's Relief team list | receives backups as planned relief; covers the lessons of an away teacher that still run |
| Teachers | personal code or TEACHER_CODE | see their duties and which of their lessons don't happen; see the exam timetables and the roster on the main site |
| Students and parents | the student's personal code; STUDENT_CODE | with a personal code: their papers, venues and seats; with the shared code: the exam timetable per level only |

The Exams committee is a list of people kept in the exams settings, picked from relief's people (the published
timetable's teachers plus staff who do not teach, added by name), so every action is recorded against a person.

## Approaches considered

How the venues, seats and invigilators are chosen was the one open choice about the build.

- **A. The app does it itself, by fixed rules.** Rules are settings with boxes (the backup invigilators, invigilators per
  room, a "never" list). Instant, the same answer every time, every pick with a plain reason, nothing sent outside. A rule
  that does not fit the settings needs the app changed.
- **B. An AI picks invigilators from rules in words; the app checks.** As relief does. Any rule in words works; an exam is
  about 200 duties, so a roster takes minutes and costs money, and picks vary each time. Venues and seats are counting,
  which an AI does not do better. Could come later as a helper on top of A.
- **C. The outside agent makes it, like the weekly timetable** (download a workbook, the agent works, upload). Dropped: a
  replacement at 6:45 am cannot wait for that round trip, and the job is small enough for the app.

**The lead chose A**, with the exams committee's own pool of backup invigilators used first ("Exam committee has their own
backup invigilators, they can write it as a rule to use these pool first"; then "Yes, A with the pool").

## What it is

A fifth card on the landing page, **Exams and events** ("Enter your personal code"), and, for the timetable committee, a
section on the committee page. Mockup tab 1 is the list of every schedule of the year with its status: Draft, Waiting for
the timetable committee, Sent back (with the note), Approved · on the main site (dates), Ended.

All teacher, class, student, room and lesson facts come from the **published** timetable and its setup (as relief does),
never from the setup the committee is editing. **Students** are only those in the published timetable: there is no
separate student list for exams. While the published timetable has no students, the module still lets the exams committee
set up papers and times, but says plainly that seats, clash checks, access arrangements and students' pages need the
students added on the Students step and the timetable published again. Dates become timetable days through relief's school calendar.

### Exam rooms (settings, kept between exams)

Which venues of the published setup may be used for exams, and for each: **exam seats** (fewer than its normal capacity,
e.g. a hall that holds 400 seats 240 in exam layout), its **layout** (rows × columns, so seats can be named D14), whether
it counts as a **hall** for the invigilator numbers, and a note. A combined venue (made of rooms, PR #72) is busy whenever any of its rooms is busy. One or more rooms can be marked
for **access arrangements**.

### A schedule: what, when, for whom (mockup tab 2)

- **Kind**: Exam, Common test, or Event. **Name.**
- **Who**: whole school, chosen levels, or chosen classes.
- **Dates**: from–to; days that are not school days in the calendar are skipped and shown as such.
- **Each day**: which of the levels are on it that day, and **whole day off** (the level has no lessons that day) or **part
  of the day** with a from–to time (the level's lessons stop in that window, then run as usual). The lead: "sometimes
  whole day off and sometimes part of the day". Times snap to the published timetable's period boundaries.
- **Exam-day times** (settings with defaults): students report at, the least break between papers, at most N papers a day
  for one student (a warning, not a stop).

A class is **on the schedule** at a time when its level (or the class) is on it that day and the time is inside the day's
window. A lesson's **periods inside the window don't happen** when every class in the lesson is on the schedule; its periods
outside the window run (a lesson that crosses the window's edge is shortened). The setup screen warns when a window's edge
cuts lessons ("ends in the middle of 4 lessons") so the committee can move it. A lesson with some classes on and some not
still runs (and its teacher is still needed).

### Papers (mockup tab 3)

For each paper: level, subject, paper name, length, **who sits**, "sits with" (papers that start together, e.g. Chinese,
Malay and Tamil Paper 2), and the **date and time, set by the exams committee**. Who sits is the whole level, or the
students of that subject's groups at that level from the published timetable (lessons of the subject and the students in
their classes and group codes), or a list of students (a make-up paper). "Fill from the subjects" adds one paper per subject
of the chosen levels as a start; "Upload a paper list" takes an Excel sheet.

**Access arrangements**: a list per exam (carried from the last exam, editable) of students with extra time (a percentage),
own room, reader or scribe, and a note. Their papers end later by their extra time; they sit in an access-arrangements room.

**Checks** on the times (always): no student has two papers at once; "sits with" papers start together; no paper on a
non-school day; a paper for a whole level or for subject groups lies inside that level's window that day. Warnings: a
student over the papers-a-day limit.

**A make-up paper** (who sits = picked students) may be at any school time, inside or outside the windows. It stops no
lesson: its students miss whatever lesson they have then, which their page and that lesson's teacher's page say ("Alicia Ng
is at a make-up paper, 10:20–11:20"), and nothing goes to relief. It still needs a room free then and invigilators free
then, found the same way.

### Venues and seats (mockup tab 5)

Per **sitting** (papers that start together), the app:
1. Lists the exam rooms free then: not used by a lesson that still runs at any period from invigilators' arrival to the
   last finish (lessons of classes on the schedule are not running), not taken by another approved or waiting schedule,
   not taken by an event. A room a running lesson uses in wet weather (a PE lesson's rain room) counts as busy, with "Use
   it anyway".
2. Seats each class in its own home room when the home room is free and has the exam seats (setting: own class in own home
   room / mix classes), then fills the shared rooms largest first. Students with access arrangements go to the
   access-arrangements room.
3. Seats students inside a room by the order chosen: class then Student ID (the data has no separate register or index
   number), or name. In a shared room, two levels or papers alternate by column (setting: alternate levels by column /
   alternate papers / one level per block). Spacing: every seat, or a seat left between.
4. Flags a room over its exam seats, and offers a fix (move some students to a named room with space).

The committee can move a class or a student to another room and swap seats by hand; "Make again" keeps paper times and
any hand changes and redoes the rest. On an approved schedule, "Make again" only fills what is empty or now clashes; it
never reshuffles seats and duties already on the main site.

### Invigilators (mockup tab 6)

Per room per sitting, the duty runs from the arrival time (default 15 minutes before) to the last student's finish plus the
stay-after time (default 10 minutes). How many: settings (defaults: 2 per classroom; a hall 1 per 40 students plus a chief;
the access room 1, plus a reader where needed). A chief is chosen from a "chief invigilators" list when one is set, else
the first picked is marked chief.

**Free then** for a duty on its date: not teaching a lesson that still runs at any overlapping period (the published
timetable on that date's timetable day, minus lessons that don't happen), not away (relief's absences), not on another duty
or event of this or another approved or waiting schedule, not "Not available" by a Must rule on step 6, not on the "never"
list. The same test as relief's "free then", plus duties.

**Order**: teachers **freed** by the schedule (their lesson then doesn't happen because the class is on it) first, then
others free then; inside each, the lightest duty load (minutes this schedule, then this year). **Backup invigilators** (a
list kept by the exams committee, which may include staff who do not teach) are kept off regular duties where possible and
come first for a replacement. Optional settings, off by default: not in a paper of their own subject; the subject teacher
on standby for the first minutes of their paper; at most N duties a day.

When nobody is free for a duty, the app picks the best teacher who **would need a backup** (their lesson still runs) and
shows "backup needed"; the exams committee can accept that, pick another, or leave it short.

Each duty shows its reason ("freed: 3B is sitting English", "free, lightest duty load"). "Who could take it" lists the
choices in the groups above. The **duty load** list shows each teacher's duties and minutes this schedule and this year.

### Lessons on those days (mockup tab 7)

Every lesson on the schedule's dates falls into one list:
- **No relief needed**: its classes are on the schedule. Its teacher is free then (and counts as freed).
- **Backup needed**: its teacher has a duty or goes to the event then, and the lesson still runs. For each: "Send to the
  relief team", "Handled ourselves", or "Pick another invigilator".
- **Runs as usual**: everything else.

Backups are sent **when the schedule is approved** (not before), as planned relief with the reason "Invigilating: <name of
schedule>" or "At event: <name>", and from then on follow relief's own route (its pick, the relief team's approval,
Telegram, acknowledgement). A backup for a schedule that is withdrawn, or whose duty moves, is cancelled in relief.

### A teacher is away on a schedule's day (mockup tab 7)

Relief records the absence (the teacher asks, management plans it, or the relief team enters it). The app then splits it:
- **Their duties** go to the exams committee (for an event, to the teacher in charge), who is told at once (in the app;
  on Telegram once relief's bot exists). "Who could take it" lists backup invigilators free then first, then others free
  then, lightest duty load first. **The replacement goes on the main site at once**, without waiting for the timetable
  committee, which sees it under "Done without approval". The replacement is told on Telegram (once the bot exists) and
  sees it in their duties. The lead: "exam committee will find replacement for their own exam portion".
- **Their lessons that still run** (other levels) go to the relief team as usual. The lead: "relief team will take over if
  the teacher covers other levels too."
- **Their lessons with classes on the schedule** don't happen; nobody covers them.

### Events (mockup tab 8)

The **teacher in charge** (any teacher, with their personal code) makes the event: name; who (levels or classes); dates,
each whole day or part with times; where (off site, typed, or school venues, which are then taken); **who goes with the
classes**, chosen by: the form teachers of those classes, the teachers who would teach those classes then, a department,
or picked people; and an optional list of duties (duty, who, time). The app shows the same three lists of lessons (the
classes' lessons stop; going teachers' other lessons need backup; the rest run), venues freed and venues taken (lessons
that use a taken venue are flagged, not moved). It goes to the timetable committee like an exam. The lead: "Teacher in
charge will do the scheduling."

### Common tests

A common test is an exam with usually one paper and one level in a short window, often in lesson time. Two extra choices:
seat in home rooms (the default for a common test), and **supervised by the teacher whose lesson it would have been** (that
teacher's lesson doesn't happen but they supervise it; no invigilators are picked) or by invigilators picked as for an exam.

### Approval and the main site (mockup tabs 1 and 10)

- Inside the exams committee (or for the teacher in charge, inside their event) everything is free: drafts, trying,
  "Make again", hand changes, printouts, downloads. The lead: "Exam committee only needs approval to change publish website
  other than that they can do what they need to do within the committee."
- **Send to the timetable committee** puts the schedule in "Waiting". The timetable committee sees what it changes on the
  main site: classes and dates, lessons that won't happen (count, no relief needed), teachers with duties (count, most
  duties), backups for the relief team, venues taken, lessons that use a taken venue, and the checks (no clashes for
  students, everyone seated, every invigilator free then, clashes with other schedules, the weekly timetable changed since
  the schedule was made). **Approve** puts it on the main site; **Send back with a note** returns it to Draft.
- **Every later change that would show on the main site** (a paper, a date, a venue, a seat, an invigilator) waits for
  approval as a list of just those changes ("Approve the changes" / "Send back"). The approved version stays on the main
  site until then. The one exception: a replacement for someone away goes on at once and is listed under "Done without
  approval".
- **Withdraw** (timetable committee) takes it off the main site at once and cancels its backups in relief.
- After its last date a schedule shows as Ended and stays readable.

### What people see (mockup tab 9)

- **The main site on a date**: the date choice relief adds ("Usual timetable" or a date). On a date inside an approved
  schedule: a class's timetable shows the papers (with venue) or the event in place of the lessons that don't happen, which
  are crossed out; a teacher's timetable shows their duties, their lessons that don't happen, and who covers a lesson sent
  to relief; Who's free on that date counts duties and events. A banner on the main site during an approved schedule names
  it and links to its exam timetable.
- **Exams and events on the main site**: each approved schedule's timetable per level. Teachers (and heads) also see the
  invigilation roster and the seating plans; the shared student code sees the timetable per level only.
- **A teacher's own page** (personal code): "My exam duties" with each duty's time, venue, paper, number of students, who
  else is there, and where scripts go; their lessons that don't happen; reliefs they cover.
- **A student's own page** (`/me`, personal code; parents use the same code): "My exam timetable" with each paper's date,
  report time, start and end, venue and seat; part days say "lessons from 10:20"; events show their time and place.
- Access arrangements show only to the exams committee and, as their room and time, to the student themself.

### Printouts and downloads (exams committee and timetable committee)

Per venue: seating plan (the grid with class and Student ID, names on hover in the app and printed beside), door list,
attendance sheet. Per class: where each student sits for each paper. The invigilation roster by day and by teacher. The
exam timetable per level. Each as PDF, and everything as one Excel file.

## What relief gets (and the small changes it needs)

The exams module answers, for any date, from **approved** schedules only:
1. Which classes are on a schedule at which periods (their lessons don't happen).
2. Which teachers are busy at which periods (duties, events), and why.
3. The backups sent (as planned relief).
4. Each teacher's duty periods that week (rounded up to the published timetable's periods).

Relief then needs these changes to its approved design, to be made in its own stages:
- **"Free then"** also leaves out teachers busy with a duty or event then.
- **Ask for relief / plan relief** lists the absent teacher's lessons that don't happen as "not happening: 3B is on the
  End-of-Year Exam", needing no relief, and their duties as "duty: the exams committee replaces it".
- **"Week so far"** counts duty and event periods as busy, and does not count lessons that don't happen. The lead chose
  this ("Count it"), so relief shares out fairly in an exam week.
- **The published timetable on a date** carries the exam and event layer above.

## What is kept

The records live in the app's data folder (beside relief's), survive deploys and restarts, and are worked out from the
published timetable on use. For each schedule: its working copy and its approved copy (the one on the main site), the
changes waiting for approval, and a log: who made, sent, approved, sent back, withdrew, changed or replaced what and when,
with the notes. Plus the exams settings: the Exams committee list, exam rooms, backup and chief invigilators, the "never"
list, the invigilation rules, and the access arrangements per exam.

When the committee publishes a new weekly timetable, every waiting or approved schedule is checked again. One whose duties
or venues now clash is flagged to the exams committee (or teacher in charge) and the timetable committee ("the timetable
changed since this was approved: 2 duties now clash with lessons"); the approved copy stays on the main site until a fix is
approved.

## Stages

Each stage is its own design check, plan, build and pull request, merged and deployed only on the lead's word.

0. **Before anything:** relief stage 1 (personal codes, the people relief knows, the school calendar; PR #77, open on 21
   November 2026) is merged, because this module signs in with those codes and reads that calendar. If it is not merged
   by then, this project waits rather than building a second calendar. Before the first real exam, the committee adds the
   students to the setup and publishes again (the module can be built and tested on made-up students before that).
1. **Exams inside the exams committee.** Exams settings (the list, exam rooms, invigilator rules, backup and chief
   invigilators), set up an exam or common test, papers with times and who sits, access arrangements, the checks, venues and
   seats, invigilators, the three lists of lessons (shown, not sent), printouts and downloads. Useful on its own: the
   committee gets seating plans and a roster.
2. **Approval and the main site.** Send, approve, send back, changes waiting, withdraw; the main site on a date (built here
   or reused from relief stage 3, whichever comes first), the exams tab, teachers' duties, students' exam timetables.
3. **Exams and relief.** Backups sent as planned relief; relief's changes above; a teacher away (duties to the exams
   committee, replacements at once, lessons to the relief team); Telegram messages once relief's bot exists. Needs relief
   stages 2 and 3.
4. **Events.** The teacher in charge, who goes, duties, venues taken, the same approval and relief links.

Stage 1 is planned first, once this document is approved.

## Left to the builder

- Where the records are kept (a SQLite file in the data folder, as for relief, is the obvious choice) and their shape,
  including how the working copy, the approved copy and the waiting changes are stored.
- The exact seating and filling order inside the rules above, and tie-breaks.
- Page layout beyond the mockups; the wording, in the app's plain style; PDF layouts.
- The Excel layout of "Upload a paper list" and of the downloads.
- How the main site's date view is shared with relief's.

## Calls made in this design (Claude's, not the lead's; the lead may change any)

- A new card "Exams and events", signing in with relief's personal codes; the Exams committee as a list of people in the
  exams settings.
- Any teacher may start an event and becomes its teacher in charge.
- Events go to the timetable committee for approval, like exams.
- The timetable committee approves with COMMITTEE_CODE (a shared code), so approvals are recorded as "the timetable
  committee", not a person.
- Backups are sent to the relief team only when the schedule is approved; Withdraw cancels them.
- The exams committee hears of an absence through relief, not separately.
- Exam rooms have their own exam seats and layout, kept between exams; access arrangements are a list per exam, carried
  forward.
- Part-day windows snap to period boundaries; a lesson doesn't happen only when all its classes are on the schedule.
- Seating defaults: own class in own home room, then shared rooms largest first; class then Student ID; alternate levels by
  column in a shared room; every seat.
- Invigilation defaults: 2 per classroom, a hall 1 per 40 plus a chief, arrive 15 minutes before, stay 10 after; freed
  teachers first, then lightest duty load; backup invigilators kept off regular duties where possible; "not own subject" and
  "subject teacher on standby" off by default.
- When nobody is free, the best teacher who would need a backup is picked and flagged, rather than leaving the duty empty.
- Three papers a day for a student is a warning, not a stop.
- A common test is supervised by the teacher whose lesson it would have been, unless invigilators are asked for.
- Only approved schedules affect relief and the main site.
- The shared student code sees exam timetables per level only; seats and names need the student's personal code or a
  teacher's code.
- Duty minutes are rounded up to periods when relief counts them.
- A window's edge inside a lesson shortens the lesson (only the periods inside stop), with a warning on the setup screen.
- A make-up paper for picked students may be outside the windows; it stops no lesson and sends nothing to relief.
- A rain room of a running PE lesson counts as busy, with "Use it anyway".
- "Make again" on an approved schedule never reshuffles what is on the main site.

## Known limits

- Students come only from the published timetable: a student who changes class, joins or leaves shows in exams only
  after the committee publishes again. Until the 2027 setup has students, nothing can be seated.
- The data has no register numbers or exam index numbers; seating uses class then Student ID. Index numbers for national
  exams would need an upload (not in this project).
- The app does not place paper times; the exams committee sets them.
- Relief's calendar does not know a day that follows another day's timetable; such an exam day needs the same later change
  relief needs.
- A lesson that uses a venue an event takes is flagged, not moved.
- The timetable committee signs in with a shared code, so "approved by" names the committee, not a person, until project 3
  (who sees what) gives it personal sign-in. Accounts and roles are being planned in another session; if that gives every
  person their own sign-in and roles, the Exams committee list and the timetable committee's approval move onto it.

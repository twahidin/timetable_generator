# School timetable app

One deployment per school. The timetable committee builds the setup step by step and downloads it with the timetable
skill; an AI agent outside the app (Claude with the skill, say) makes the timetable from them; the committee uploads
the result, checks it and **publishes**. Teachers and students then open the published timetable and download PDFs.
Everyone signs in on one page: staff with their own name (a username and password, or their personal code), students
with their personal or the shared student code. The **Admin page** (below) decides who is who. The shared codes in the
table keep working until an admin turns them off on the admin page's **Ways in**. The app does not generate timetables itself.

| Code (Railway variable) | Who | What they see |
|---|---|---|
| `COMMITTEE_CODE` | timetable committee | the setup editor, the downloads, Upload and edit, Publish, the personal student codes |
| `TEACHER_CODE` | teachers | every class, teacher, room and student timetable, the lesson search, Who's free, PDFs |
| `HEADS_CODE` (optional) | heads of department | every step to read except Download, Upload and edit, Publish and Students; everything on step 5 (who teaches which class and group, new groups and bands, moving rows between bands), and new teachers (marked provisional until the committee confirms them) to change; a refused change is skipped and reported, and the rest of their work is kept |
| `ANTHROPIC_API_KEY` (optional) | the committee, in Railway | with it set, step 8's Warnings tab has a box to type a request in words (**Ask in words**); only those words go to Anthropic. A server that still has `AI_PROVIDER=anthropic` and `AI_API_KEY` from an earlier version has the box too |
| `TYPED_REQUEST_MODEL` (optional) | the committee, in Railway | the model that reads the words, `claude-opus-5-5` unless set (with the earlier `AI_API_KEY`, the model `AI_MODEL` names); `mock` is a practice reader that needs no key |
| `STUDENT_CODE` | students | class timetables and **Build my timetable** (pick class and groups), PDFs of those |
| personal codes (made by the app) | one student each | only that student's own timetable and its PDF |
| personal teacher codes (made by the app) | one teacher each | the Relief module and everything the teacher code opens |

**Relief.** The home page has a **Relief** tile for a teacher signed in with their own personal code or password. Stage 1 gives each teacher a
code and a Relief home (their name, their timetable, and for the relief team the way to the settings). Stage 2 adds
relief requests on the Relief home, in tabs that show only to those who may use them:
- **Every teacher:** **Ask for relief** (today, tomorrow or up to 10 dates; the whole day or some periods; a reason;
  their lessons then, read from the published timetable, each with work: text, a link or files; the reporting
  officer), and **My absences**: everything asked or planned for them, where they acknowledge relief someone else
  planned, set or change the work, mark a lesson not needed, or cancel with a line saying why.
- **Management and the relief team** (school leaders, HODs and SHs, and anyone ticked for the **Relief team** on the admin page): **Plan relief** for a colleague, choosing a
  relief teacher for each lesson from its "free then" list (same department and subject first, lightest week first,
  Flexi Adjunct Teachers marked, anyone over a checked limit dimmed but still choosable) or leaving it for the relief
  team; **Planned by me**, where each absence opens with Choose on its open lessons; and **Download** of the relief
  sheet for a range of dates (every absence with lessons then; never the reason).
- **The relief team:** **What's in**, read-only: every absence, who sent it and how, the acknowledgement, the work,
  the relief chosen or open, cancellations, and what is new since they last looked.

Stage 3 is the relief team's module and everyone's cover list:
- **Today** (the relief team): the page for a date. Every lesson needing cover, with its pick: the planner's choice, the
  AI's pick by the school's rules, or the app's own order when there is no AI. The team can **Approve**, **Approve all
  waiting**, **Change** the pick, **Split** a lesson into parts (each with its own relief teacher) and **Join again**,
  **Keep** the relief when a teacher asks to change it, or **Fill now** to pick at once.
- **Reliefs I'm covering** (every teacher): the reliefs sent out to them (below), with **Acknowledge** or **Request to
  change**, the work and its files.
- **Load** (the relief team): how many relief periods each teacher has this week and this term, by department, with a
  Download; a name opens that teacher's reliefs.
- **What's in** also shows "Needs a nudge" and each absence's relief status.

Stage 4 is Telegram: the school's own bot tells people about relief on their phones, and they answer there. It is off
until somebody makes the bot, sets `TELEGRAM_BOT_TOKEN` and presses **Connect the bot** in Relief settings
([docs/DEPLOY.md](docs/DEPLOY.md#6-telegram-for-relief) has the steps). Each person links their own Telegram with
**Link Telegram** at the top of My absences (and unlinks it there, or with `/stop`). Whoever is not linked finds their
reliefs and absences in the app, as before; somebody unlinked because they blocked the bot sees why on their Link
Telegram card.
- **Relief teachers** get their relief once the relief team has approved it and sent it out (or a head chose them when
  planning), in school hours alone, with the work and a link, and **Open in the app** for the files (no file is sent on
  Telegram), and press **Acknowledge** or **Request to change** (they say why in one line). A relief told before its day
  is told again 24 hours before and on the morning itself. They are told when it is moved, kept or no longer needed, and
  when an exam or event stops the lesson or it is on again.
- **Absent teachers** are told of relief somebody else planned, with a button that opens the app to set work and one to
  cancel (one line saying why, then a second press; not for an exam or event duty's backup, which the exams committee
  or the event's teacher in charge stops), and get one reminder. They are told who covers each lesson once that relief
  teacher acknowledges (when that is in the evening or at night, they are told at 06:45 the next morning), and are reminded to set work at 18:00 the evening before and 07:00 on the day while a lesson has
  none. `/relief` asks for relief on Telegram with the
  app's own questions, work and files included; a lesson takes as many messages as wanted (a text, then a file) until
  **Next**; What's in then says "asked on Telegram".
- **Reporting officers** are told who is away and when, with the kind of reason alone; the Ask for relief form and
  `/relief` say when the reporting officer is not on Telegram, so the teacher tells them.
- **The relief team** gets the morning message (06:30, a setting; not a member away the whole day) with everything
  waiting for today and who is away; a
  late request for an absence for today sent after the morning message and before the cut-off (14:00, a setting), once
  its picks wait for approval; "Relief needed again" when an approved relief's teacher is away then; an alert when a
  teacher blocks the bot; each request to change with its new pick and an **Approve** button, a report of who has not
  acknowledged (every 15 minutes, a setting, from an hour before the first period) with **Remind them again**, one all
  clear, what was cancelled by a person, and a weekly summary (Friday 15:00, a setting). Between the cut-off and the
  next morning message nobody on the team is pinged about a new request.
- On **Today** a relief is approved with **Approve**, then told with **Send out** (a row's own, or **Send out {n}
  approved** at the top; on Telegram, **📤 Send out to {name}** after **Approve**). Sent out outside school hours (from
  the earliest send-out time, 06:45, to the cut-off of a school day), it is held and goes at the next school day's
  earliest send-out time (06:45; sent out on a Friday evening, on Monday). A head's own choice in
  Plan relief for a colleague is approved and sent out when it is planned. A relief sent out says when its teacher was
  told, or that they are not on Telegram, with **Remind** beside it and **Remind all not acknowledged** at the top. After
  the cut-off Today opens on the next school day. **Weekly summary** is a new tab with any week's numbers.

What people do there is checked as on the app's own pages and written in the **History** (by that person, "Telegram"). A
message goes once: when it cannot be known whether it went, Today says "May not have been sent: remind them" and it is
not sent again by itself. While Telegram is down nothing is given up: what waits goes when it is back, if still true.
A line the bot does not read (not a button, code, command or answer) is answered "I can't read messages here."

Nothing reaches a relief teacher before the relief team approves it and sends it out, or a head chooses them when
planning, in the app or on Telegram, and nothing reaches them on Telegram outside school hours. The AI picks as soon as a
request is in, for any date. The teacher who is away sees the relief teacher's name once it is acknowledged ("Being
arranged" before that). The times are in **Relief settings**; `docs/DEPLOY.md` (section 6, "When messages go") has what
goes when. The published timetable on a date, with the relief in it, comes later.

Relief also knows what approved exams and events do to a date (stage 3 of exams and events): a lesson whose every period stops for an exam or event shows as "Not happening" and needs no relief while it is stopped (if the exam is withdrawn, an absence sent meanwhile asks for its relief again); someone on an exam duty or going to an event is not offered as free then (a fold under the list says who and why) and cannot be chosen; their duty minutes count in "week so far"; and an absence may be sent even when every lesson stops, because the duty must be replaced and the exams committee sees who is away. The forms list the teacher's duties on each date. An absence sent before the exam or event was approved shows such a lesson as "Not happening", and it cannot be given a relief teacher. The relief team's pages know the same: such a lesson is not picked for, approved or counted (Today and Reliefs I'm covering say "Not happening", and a relief given before stands again if the exam is withdrawn); nobody on an exam duty or at an event is picked, and an approved relief who is given a duty then is flagged; Today says which duty the teacher of a backup is on; and Load's "Week so far" and the numbers the AI is given count exam and event duties and leave out lessons that stop.

The reason for an absence is seen only by the absent teacher, whoever planned it, management and the relief team; on
Telegram the reporting officer is told its kind alone (Medical, Child sick, Course or Other). Each
relief save is one line in the **History**, never with the reason. Relief reads the teachers from the published timetable, so publish first. **Relief settings**
(the committee page's header link, or the Relief home for the relief team) hold the Flexi Adjunct Teachers' role, the
relief rules in words, the limits the app checks, the times and the school calendar (terms, which week each term
starts as, holidays); they connect the Telegram bot, list who is linked and who is not, and show the relief team the messages
that could not be sent, or may not have been, since Monday (not reliefs, reports or all clears); they show management, the
relief team and the other staff who teach no lessons, which are set
on the admin page (roles, the **Relief team** tick, and the staff added there). The committee downloads the
personal teacher codes there as a list (CSV) or as slips to print. Like the personal student codes, they are made from
each name and `SECRET_KEY`, and are off without it.

**Exams and events.** The home page has an **Exams and events** tile (`/exams`) for the exams committee and the timetable committee; everyone else signed in by name has a **My exam and event duties** tile instead, which opens the same page for their own exam and event duties and the events they are in charge of (stage 4, below). The exams committee is given on the admin page: on Staff, tick **Exams and events** for a person, with an end date, and it stops by itself after that day (the tile then says "Until" and the date). No one else can use the exams themselves, because they show student names, seats and access arrangements. The exam settings page shows that list but does not change it. Stage 1 is the committee's own working: set up an exam or a test, say which levels and days it covers (a whole day or part of a day), fill in the papers (by hand or from an uploaded paper list) and their times, and check the paper times. **Make** then stops the lessons that fall inside the exam, frees their teachers, seats the students in the exam rooms, and picks invigilators (or leaves the teacher of the lesson in the room, for a test). The committee can move a class to another room, set the invigilators by hand, and print the seating plans, the roster by day and the lessons sheet, or download the Excel. It needs the Relief **school calendar** (to know which timetable day a date is) and the personal teacher codes (to know who is on the staff), and reads everything from the published timetable. Stage 2 adds approval: the exams committee presses **Send to the timetable committee** once Make is done, nothing has changed since Make, and the paper times have no errors (the other checks are for the timetable committee to weigh), and the timetable committee approves it, sends it back with a note, or withdraws it; later changes wait for a second approval, except an invigilator who is away, who can be replaced at once and is listed as done without approval. Only the approved copy reaches the main site: the published page gets a **date box** (lessons that do not happen are crossed out and the papers and duties are drawn in), a banner, an **Exams** tab, a teacher's **My exam duties** and a student's **My exam timetable**. Sending, approving, sending back, withdrawing and replacing someone away are also written to the **History**. The shared student code sees classes, rooms and times only, never teacher names, duty rooms, rosters or prints. No message is sent to students or teachers about papers, seats or duties yet.

Stage 4 adds **events** (a learning journey, a camp): anyone signed in by name (with their code or their password) starts one with **+ New event** and is its teacher in charge (the timetable committee may too, naming one); only the teacher in charge and the timetable committee open or change it, and the exams committee does not manage events. The timetable committee can give an event to another teacher in charge (**Change** beside the name in its heading): at once, with no approval, and the one before no longer opens it. The event says which classes and days (a whole day or part of one), where it is, and which school rooms it takes; the teacher in charge fills the **going** list (form teachers, teachers who would teach those classes then, a department, or picked people) and sees who is free then and whose lessons need a backup. The lessons of the event's classes stop, and a lesson that uses a taken room is flagged. It goes through the same approval (each save and each step is written to the **History**), and only the approved copy reaches the main site: event blocks on the date box, the banner and the **Exams and events** tab, a teacher's **My exam and event duties** and a student's own timetable. The shared student code sees only the event's name, where and time. When a schedule is approved, the lessons of each person on duty or going that still run during their duty become **backups sent to the relief team as planned absences** ("Invigilating: {name}" or "At event: {name}", by the exams committee or the teacher in charge), one record per person. Backups show in the relief team's What's in and to the person on duty, who acknowledges them and sets work; the relief team's picks cover them like any other planned absence. The Lessons tab shows where each backup stands and gives the committee a **Handled ourselves** tick for cover it arranges itself (nothing is sent for it; each tick is written to the **History**): that is how the committee stops a backup, since a backup cancelled inside relief comes back at the next sync (which runs straight after the cancel). Someone's own absence wins over a backup, and when it is cancelled the lesson goes back to the backup at once; a withdrawn or changed schedule removes only lessons still to come, and a new publish brings the backups in step at once. On Telegram (relief stage 4) a backup is told as any planned absence is: the person on duty hears that relief is planned for them and is reminded once, its relief teacher hears once the relief team has approved them. When the app ends a backup (a withdrawn schedule, a changed duty, **Handled ourselves**), the person on duty and the reporting officer hear it if they were told of it, and its relief teacher hears that the relief is no longer needed; the relief team and the event's teacher in charge are not messaged. A backup cannot be cancelled on Telegram. Giving the event to another teacher in charge is told to nobody. The relief teacher of a lesson an exam or event stops is told that it is not happening, and that it is on again after a withdrawal. Nobody is messaged about a duty itself (given, moved or taken away), and the exams committee gets no messages.

**Preview before publishing.** On steps 8 and 9, **Preview as it will be published** opens the draft as the published timetable page would show it, in a new tab, for the committee only. A banner says it is a preview, how many lessons are waiting in Not placed (they are not on it) and whether a critical mistake still stops publishing. Nothing is published, and the preview has no PDF or file links.

**The published timetable's Lessons tab.** One filter (week, day, time, level, class, department, subject, teacher, room, band, or any word) and three ways to see what it finds: **Class grids** (each class's timetable as on its own page, one under another, with the lessons that match in colour and the rest faded; a class with no match is left out), **One page** (every class at once as a small timetable of blocks; a click opens the class) and **Table** (sortable, with the CSV download). The address keeps the filter and the view, so a link can be shared.

**The steps.** Start · School & day · 1 Venues · 2 Classes · 3 Subjects · 4 Teachers · 5 Teacher & TG deployment ·
6 Configuration & constraints (the school-wide settings, teacher block-outs, fixed lessons and every other rule) ·
7 Download · 8 Upload and edit · 9 Publish · Students. Steps 1 to 4 have the same numbers as the workbook's sheets (1 Venues to 4 Teachers);
step 5 fills its 5 Blocks and 6 Lessons sheets, and step 6 its Settings, Teacher availability, Fixed lessons and More
rules sheets. Step 4 shows the teachers two ways, **Cards** (a column per department, a card per teacher; with one department shown its cards go across in three columns) and **Table**; the choice is
remembered in your browser. The **Roles** card is below the teachers: the teacher list is checked against it. A teacher can
have a **second department** beside their own (the committee gives it, and a head cannot): drag a department chip from
the row above the columns onto a teacher's card, or pick it in the **Second department** box (in the open card or in the
Table), or take it off with the ✕ on its chip. They then have a card in both departments' columns and are on both
departments' pages on step 5. A click on a card opens it in place to change it. A stored list of subjects a teacher could teach, from an older setup,
stays in the file untouched; the page no longer shows or changes it. Step 1 shows the rooms two ways, **Blocks** (a panel per block, a row per floor, a tile per room) and **Table**; the choice is remembered in your browser. On Blocks, tick rooms (a box on each tile, or **Tick all** on a floor) and a bar moves them together to a block and a floor, picked from the lists or typed as new ones; an open room's own **Block** and **Floor** are lists too, each with a **New …** choice. A room can carry **Equipment** and a **Configuration**, two plain notes that are only shown (in the table, on the Blocks tile, in the workbook and on the room's page) and that no check reads. On Blocks, a click on a room opens it to change; **+ Room** on a floor, **+ Floor** on a block and **+ Block** add a room (each in one step you can undo), and **New kind…** in a room's Kind box adds a kind to the school's list.

**Renaming a teacher.** Type a new name over a teacher's name on step 4 (on the card or in the Table view) and the new name goes onto their groups (step 5), their form-teacher places (step 2) and any rule that names them (step 6), in the same save. The toast says what moved, for example "New Teacher 3 is now Mdm Lee: on 6 groups, form teacher of 2A, 1 rule. Undo, at the top, brings it back." **Undo** takes all of it back, and **Put back** on the History page puts the whole rename back too. A name another teacher already has is refused ("Mdm Lee is already a teacher.") and nothing is saved. The short name beside the name follows only when it was the same as the name. Any other short name stays as it is, and the message says so, so change it too if it should be different (the short name is what the timetable prints). Sentences people typed are not changed: a typed rule or a note that holds the old name is named in the message, so it can be checked. If two teacher rows had the same old name, the name changes and their groups are left for a person to sort out. The draft on step 8 and every saved version follow by themselves: a timetable that still names the old teacher is read with the new name, with no **Re-fit**, and a timetable made by an agent from a workbook downloaded before the rename can still be uploaded.

A head of department can rename only a teacher they added themselves (one still marked provisional), and only when everything that names the teacher is theirs to change; otherwise the message says what stands in the way. Not yet: after **Publish** the new name is still a new person. Their role, committees, username, password, Telegram link, reliefs and exam duties stay under the old name, and they need a new code slip, because the personal code is made from the name. Carrying those over is planned and not built.

**Form teachers.** A class can have form teachers, who take its lessons together. **School & day** has two settings for
them: what the school calls them (**What your school calls a class's form teachers**, default "Form teachers"; a school
may type "Class Parents" and that word then takes the place of "Form teachers" everywhere below) and **Most a class can
have** (1 to 6, default 2; lowering it below what a class already has is refused). On step 2 each class's form teachers
are picked in order from the step 4 list. When some class has none, **Take them from the lessons** (it asks first) fills
the classes that have none from the teachers already on their lessons of the subjects step 6 names. A line above the
table counts the lessons changed by hand and offers **Put the Form teachers on all of them** (it asks first). Only the
committee changes any of this.

**Step 2's three views.** Step 2 shows the classes as **Cards** (one card per class under its level, with its home room, its form teachers and its subjects; a click opens the card to change it), as **Bands** (a picture of how each level's subjects are banded) or as the **Table** (every field in a row). On Bands, pick a level: whole-class subjects are filled cells, and each band is a bar across its classes with its groups and sizes; a click on a bar opens it on step 5's **Banding & TG Group Editor**, which has a button back to the picture. The choice is remembered in your browser; department heads see all three and can change nothing.

**Step 3's two views.** Step 3 shows the subjects as **Cards** (a subject and its G-levels are one card: the name is typed once, the G-levels are ticked, and one periods grid has a row per G-level) or as the **Table** (a row per subject and G-level). To make a subject with its G-levels, press **+ Add a subject** in a department, type the name and code, and tick the G-levels; unticking one, or Delete, asks first when step 5 uses it, and Undo takes any of these back. The choice is remembered in your browser; department heads see both and can change nothing.

The student list goes in on the **Students** step, after the timetable is made (it is not needed to make one): paste it from Excel or a CSV, or upload an .xlsx or
.csv, with each student's ID, name, class and group codes; the committee can then edit each student's groups there.
To fill groups in the app, tick students (shift-click for a run, or the top box for everyone shown) and **Add to group**,
**Remove from group** or **Move to class** for all of them at once; a group in a band replaces the student's other group
in that band.
Things to fix lists students who are in none of the groups of a band over their class (so they would miss that
subject), one note per band. Having the subject in another band counts; a Note with "Exempt" and the subject ("Exempt
from MTL") excuses them; untick **Everyone takes one** on a band that is an option (it starts unticked for a band named
Option or Elective).

**Restoring.** The server keeps restore points of the setup in `setup_history/` (see Saving the setup below). When
students have no groups or bands no classes, the Students step shows **Restore from an earlier copy**: pick a copy and it
fills only those students (by Student ID) and bands; nothing else changes and Undo takes it back. To go back to an
earlier copy of the whole setup, use **Restore an earlier copy** on step 7, Download.
The student list is optional, but with it the checks make sure no student has two lessons at once, and every student
gets a personal code. Personal codes are made from each student's ID and `SECRET_KEY`, so they stay the same when the
timetable is republished; without `SECRET_KEY` they are off. The committee downloads them as a list (CSV) or as slips
to print, one page per class. Students not on the list use the general student code and Build my timetable.

## From setup to published timetable

1. **Build the setup** on the steps. The **Things to fix** panel lists what does not add up. *Critical* (red): no
   timetable can be made until it is fixed (a teacher on two groups of one band, a fixed lesson outside lesson time,
   fixed lessons that put one teacher in two places). *Warnings* (amber): a timetable can still be made, but a person
   should look (a teacher over their allowance, a room that seats too few, a rule that matches no lesson). Form teachers add
five lines: a class with none yet ("3I4 has no Form teachers yet."), a form teacher who is not on the teacher list, a
teacher who is a form teacher of two classes (a warning: their lessons cannot be at the same time), a named subject that
is not on step 3, and a named subject the class has only in groups.
2. **Will it fit?** Step 7 opens with the sums on the setup as it stands, before anything goes to an agent: each
   class's periods against the lesson periods of its days, lessons against the stretches between breaks (a 3-period
   lesson cannot run across recess), a lesson longer than any stretch, special rooms against the lessons that need
   them, each teacher's lessons against the times they can teach, and floating recess that cannot work. Critical
   first, each with a button to the step that fixes it; it runs again whenever the setup changes (`checks.py`).
3. **Download** (step 7): the configuration workbook and the timetable skill. Use the skill zip when the agent can run
   code: its scripts make a timetable file this app publishes as it is. `SKILL.md` alone is for an agent that cannot.
   `SKILL.md` carries a version line (`Skill version: 2026-11.9`) and the workbook's README sheet names the version it
   was made for. When the setup has second choices (step 6), step 7 counts them and asks **If the first choices do not
   fit:** **Fall back only when needed** (the default) or **Make one timetable for each**; the workbook carries the pick
   on its Choices sheet. Every downloaded workbook also carries a **Configuration id** row on Settings (`v14`, or `v14+`
   when it was downloaded with changes not yet saved). A **Starter prompt** card has the text to paste into the chatbot
   with the two files, with a **Copy** button: use the attached skill, check first, hand back the database or a Lessons
   workbook, fill in the rule report and the Choices used sheet.
4. **Make the timetable outside**: give the agent both, and ask it to generate the timetable and report anything that
   does not fit. It hands back a timetable database (`.sqlite`) or a timetable workbook (a Lessons sheet).
5. **Upload and edit** (step 8): upload that file (a workbook comes with its setup workbook; a database made by the skill holds
   its setup) and press **Upload and check** (each of the two boxes takes a click or a dropped file). The upload becomes the **draft**, kept on the server, and the app checks it four ways
   against the setup as it is now: clashes (teacher, class, room and student double-booked, lessons outside lesson time),
   differences from the deployment (who teaches what, periods placed against periods planned, rooms; other teachers than the
   form teachers on a lesson they take show here like any other, and **Update step 5** keeps the timetable's teachers and
   marks the lesson "Changed by hand"), the setup's rules,
   and the typed rules and choices used that the agent reported. A warning for another school than the saved setup, and
   which configuration the timetable was made from, are shown too. Below the upload, the timetable is shown as a board
   of one day, the periods across, with a row per class, per teacher or per room (**Rows: Classes, Teachers, Rooms**; a
   "No teacher" and a "No room" row hold the lessons with none), or of one class's, teacher's or room's whole cycle; a lesson is dragged to another time
   on its row, or clicked and then a place clicked, and **Undo the last timetable change** (at the end of the counters, or
   Ctrl or Cmd+Z) puts it back. Each place is coloured: green is clean, amber bends a Prefer, red lands with a problem (a
   clash or a broken rule), blue has another lesson there and asks, grey cannot take it (a break, outside the day).
   A lesson dropped where it clashes lands there and is marked on its card, and the counters above the board (Not placed,
   No teacher, In two places, In a break, No room) count what is wrong; a click on one steps through its lessons. A drop
   on another lesson asks first: swap with it, put it beside it (when both can be there), or push it out; pushing out a band
   names the band and says which other classes lose it too. Held over another
   day's tab for half a second, a dragged lesson goes to that day. **Lift out** (or Ctrl or Cmd+X) takes a lesson off the
   board, and a pushed-out lesson goes the same way: both wait in **Not placed**, a tab of the panel beside the board, until they
   are dragged or pasted (Ctrl or Cmd+V, where the pointer is) back onto their row, deleted, or undone. **Delete this
   lesson** asks first and says why when it should not go (step 5 asks for the lesson, or the rule it breaks); the tray's **Step 5 asks for these** lists the lessons
   step 5 plans that the timetable lacks, to drag onto a free place. Nothing is published, printed or downloaded while a
   lesson waits in Not placed: step 9 says how many and sends you back here. The panel beside the board (under it on a
   narrow window) has three tabs: **Not placed**, **Warnings** and **Changes**; it is as tall as the board and scrolls on
   its own, and a lesson dragged from the board onto any of its tabs is lifted out. A lesson with a warning is marked on
   the board (its mark, or "1 warning"), the selected lesson's **Lesson** tab lists its warnings, and **Show me** on a warning
   goes to its lesson (or its class's whole cycle) and flashes it. **Changes** lists the changes made in the app, newest
   first, with **Undo the last timetable change**. The warnings are listed by
   kind and then by class, teacher or group, with the timetable's side and step 5's side. For each one, **Update step
   5** changes the setup to match the timetable, and a rule in words that reads **Check again** has a **Still met**
   button for when you have looked (**Reopen** takes it back). The summary line reads critical, other warnings open (the two add up to the Warnings tab's number) and
   settled on step 5. A **critical mistake** is a lesson with no teacher, a teacher in two places, a class clash, a room
   used by more lessons than it takes, or a lesson in a break or outside the day; each shows its kind in words before
   its sentence, and every one is listed. Everything else is a warning and never stops publishing. Two bands, or two
   groups, of one class at the same time are not a clash. A lesson clicked on the board opens a fourth tab, **Lesson**:
   its teachers and its room, each chosen from a list with **None** (no teacher is a critical mistake, no room a
   warning), free ones first; a change of teacher is for all that class's or group's lessons of the subject (the tab
   says how many), a change of room for that lesson or, ticked, all the group's lessons; a band has a block per group.
   On the Teachers or Rooms rows a lesson dropped on another teacher's or room's row is handed to them, after a
   question. A teacher or room busy then is given only when you say so, and both lessons are marked. **Show me** on a
   teacher in two places opens the Teachers rows on that day with that teacher's lessons marked. On a warning about a
   class or a teacher, **Ways to settle this** opens under the warning, in the panel: up to three ways, each already
   checked, with what each one disturbs and whether it is clean or bends a Prefer; **Close** (or the button again)
   shuts them, and opening another warning's ways shuts the first. **Preview** opens **Before you apply** under that
   way: the sentences, and the week of each class the fixes touch with the moved, changed or new lessons outlined;
   **Apply** makes the fixes, **Cancel** leaves everything as it was. After a change the ways follow their warning:
   **Settled.**, or its new sentence and new ways. Where one fix is not enough a way can be two fixes made together;
   they are one entry under **Changes** and are undone together. A fix that would cause a clash, change a subject's
   periods from the plan or newly break a Must rule is never offered, so a clean draft stays clean. When no way settles a
   warning the panel says so and lists the nearest ways with what each breaks; those are blocked and have no button.
   With `ANTHROPIC_API_KEY` set, the foot of the Warnings tab has **Ask in words**: type what you want in your own words
   ("move PE for 2A off Friday", "give 2A maths to Mdm Lee"). It takes three kinds of request: move lessons, change who
   teaches a lesson, change a lesson's room. A language model only reads the words into a small request; the app finds
   the lessons and people itself, asks which one when a name could be several, and runs the same checks as **Ways to
   settle this**, showing up to three ways per lesson with **Preview** and **Apply**. Nothing changes until you press
   Apply, and anything else you ask to keep is repeated back as not checked. The whole site can send 30 requests in 10
   minutes. If the words cannot be read, the box says so; without the key the box is not there. Every change made on
   step 8 is kept with its sentence under **Changes**, and **Undo the last timetable change** takes the last one back.
   There is no other editor: everything is done on the board and in its panel. At the foot of the timetable card,
   under the upload's notes, **Go to step 9** goes on. Steps 8 and 9 do not show the setup's "Things to fix" column, so the
   timetable has the page's width.

   **Saved versions and Compare.** Step 8 keeps one draft and, beside it, named versions of it that can be opened again. **Compare** (the
   page `/compare`, for the committee) sets two of them side by side: the draft, a saved version or the published timetable. Lessons are matched
   by what they are (the planned lesson of step 5), never by lesson number, so two uploads that number their lessons differently still compare.
   Six tiles count the lessons at another time, the lessons with a different teacher or room, the critical mistakes, the warnings and the longest
   day of a teacher. Critical and warnings are "checked now": each timetable is checked against the setup as it is today, so a version saved
   before step 5 changed can show warnings it did not have then. **Show** picks a class, a teacher or a room: its week on each side is drawn in
   two grids (stacked on a phone), with **mark what differs** outlining in orange the places that are not the same, bands in light blue, and a
   sentence for each difference below. **Download the differences (Excel)** lists every difference, class by class. Comparing only reads: nothing
   is changed. The **Versions** button on the upload card (**Versions (3)** when there are three) opens the list over the page: **Save the draft
   as** names a copy of the draft (**Save version**; at most 30 are saved by hand); each version has **Open**, **Compare…**, **Download**
   (the timetable as a database) and **Delete** (it asks first). **Open** never loses the draft you had: the draft is kept first as a version of
   its own, and step 8 is drawn from the one opened. The app also keeps the draft as a version before an upload replaces it and before a version
   is opened (the newest 10 of these are kept, the older ones go). The list also shows the published timetable, to compare with. The list only
   reads and saves: nothing in it publishes. **Re-fit to the setup** (beside **Versions**; greyed with the reason when the timetable already fits the
   setup) works out the fewest lesson changes that settle what step 5 or the rules now ask for: a teacher who changed (two who change places on step 5
   **trade classes** in one step), a teacher added to a subject or taken off it, a lesson missing or extra, a venue, a clash, a Must rule.
   It never moves a band, and a lesson keeps its day unless
   nothing works on it: only then may it move to another day, or change places with a lesson of another day, and each such step is flagged **another
   day** (a lesson barred from every period of its own day may move to another at once). The window shows the work as it runs, then the list: what does
   not fit now, each group's steps with the sentence and its reason, what the changes settle too, and **Needs you** for what the app cannot settle (a
   change to a band itself, a judge's refusal, more than it looked at in time), with the totals before and after. Typed rules (step 6) may be touched:
   each such step says **check T{n} again**, and Apply sets those rules back to be checked. **Preview on the board** draws the changed classes with the
   moved lessons outlined. Nothing changes until **Apply all N changes**: the draft is kept first as a version "Before re-fit …", and the changes are
   made as one batch, so one **Undo** takes the whole re-fit back. A list for a draft that has changed since is refused, with **Run Re-fit again**. A teacher renamed on step 4 needs no Re-fit: the draft is read with the new name.
6. **Publish** (step 9): it shows the timetable as it will be published, read-only: the critical mistakes (each with
   **Show on step 8**, which opens step 8 with the warning marked in the panel's Warnings tab and its lesson selected on
   the board, or a lesson that is not placed selected in the Not placed tab), every other
   open warning, and the changes made in the app. While a lesson waits in Not placed, the printouts and the draft's
   download are replaced by how many are waiting. **Publish
   this timetable** is off while a critical mistake remains, with the reason above it, and the server refuses as well
   (it says how many critical mistakes are left), so a second tab cannot get round it. With none, it makes the draft what teachers and students see,
   with every download and the personal student codes (about a minute), even with warnings open: **Published now**
   says which setup version it was checked against, how many warnings were open when it was published and what they
   said, and lists the fixes made in the app. **Make printouts (.zip)** on step 9 makes every timetable of the draft,
   with the fixes made in the app, without publishing; **Download the draft (.sqlite)** carries the draft elsewhere. The rule report and the choices used stay with the published timetable.
   The published class timetable names the class's form teachers under its title (on the PDF as a line of its own), and a
   teacher's timetable says which classes they are a form teacher of; both come from the setup it was checked against.
   For an agent, `python -m ttgen check-timetable
   TIMETABLE [--setup SETUP.xlsx]` prints the same check.

**Timetable database.** Publishing (and every export, in the app or with `python -m ttgen export`) also writes the
timetable as a SQLite database: every lesson with its day, times, classes, teachers and room, plus the classes,
teachers, rooms and the setup itself, for importing into other systems. **Make printouts** on step 9 makes every output again from the draft, which may be a database
made by this app or the skill (it holds its setup).

**What a timetable compromises.** An overloaded teacher still gets every lesson: allowance is not a limit the solver
keeps, and Prefer rules bend when they must. The Excel workbook lists what was given up on a **Compromises** sheet
(teachers over their allowance, each Prefer rule not kept, Max periods in a row), and its Teacher load sheet shows other
duties and a red "Over allowance by" column.

**The department map (step 5).** The step opens on the department's page; **Table** at the top switches to the
15-column table of the same rows, for bulk edits, bands and new groups (the choice is remembered in the browser).
At the top, a strip: a department switcher (every head sees every department), the number of teachers and how many are
ticked, **Select all** (it shows a dash when only some are ticked), **Deselect all** and **No lessons yet** (ticks the
teachers who are on no lesson row), and below them the department's teachers, home or second department, as chips that
wrap: a tick box, avatar, name, a load bar (periods deployed plus other duties against the allowance; red when over)
and the figures. A teacher whose home department is another one carries that department as a tag, and a teacher a head
added carries "provisional" until the committee confirms them on step 4. Shift-click ticks a run. The search box finds
a teacher in the strip, and lists matching teachers of other departments under **Others** with **+ Add**, to place a
teacher who teaches a subject outside their own department; adding them to the page does not change their departments.
**+ New teacher** adds a hire or a post still to be filled: name (or a placeholder such as "New Mathematics
teacher 1"), short name, department, role and allowance (the role's guide when left empty); a head's new teacher is
provisional until the committee confirms them on step 4.
Below the strip, **where they teach**: a level box ("All levels"), then each level as a section, and inside it each of
the department's subjects in step 3's order, with a card for each class of a whole-class lesson and for each teaching
group that is in no band. A band is a lane under its name, its groups inside (a teacher on two groups of one band is
flagged on the lane). Each card shows the class or the group's code, its students and periods, and each teacher on a
line of their own, with a ✕. Click a card, or drop teachers on it, to place the ticked teachers (dragging a ticked
teacher drags every ticked teacher): placing **adds** (co-teaching), never replaces; a card that would go past three
says so and takes none; the ✕ takes that teacher off. A whole-class row that lists several classes shows one card
per class, and changing one class's teachers moves that class to a row of its own in the table (the solver already
treats each class's lesson separately). Every click or drop is one change: one Undo takes it back.
Clicking any avatar (not its tick box) opens the teacher's **profile** in place of the cards: avatar with **New look**,
name, role, department, load against allowance and **Teaches** (every class and group they are on, ✕ to take them
off). Details are changed on step 4.

**Banding & TG Group Editor (step 5).** The second view, **Banding & TG Group Editor** (it was called Groups and bands), is where teaching
groups and bands are made. It shows each group's teachers but does not change them: teachers are deployed in the first view, the
**Teacher Deployment Editor** (it was called Map), where a band's groups are light blue cards in a light blue lane, a whole class on
its own is a green card. Beside Level are three filters, **Teacher**, **TG** and **Class** (each lists only what this department's
cards at that level have), and a search box that finds a TG code, a teacher or a class; they work together, and **Clear** shows every card again.
Across the top are two cards. **New teaching group**: level, G-level (filters the subjects), subject, band (none = a whole-class
lesson), classes (empty = the band's classes) and students; the group code forms as you pick (level digit, subject
code, G-level letter, running number, as the workbook has it) and **Add** makes the row. **Add one per class** makes a
whole-class row for each class picked, or for every class of the level, skipping classes that have the subject already.
Beside it, **New band**: level, the subjects it covers, its classes (every class of the level unless you change them) and
a name that forms from the level and subjects ("Sec 2 Mathematics"; "Sec 3 Option A" for a band of several subjects,
the next free letter) and can be typed over; a name already used is refused. **Everyone takes one** is on unless the
name says Option. **Add band** makes it and sets the group form's band to it.
Under the two cards, one filter governs both lists below it: **Level** (one level, or **All levels**, which puts each
list under a heading for each level), **Department** (the department of the subject; the subjects and teachers on
offer are then that department's), **Subject**, **Teacher** (a teacher, or **No teacher** for the rows nobody
teaches yet) and **Band** (one band alone). **Show all** clears the department, the subject, the teacher and the band.
Below the filter are two tabs, each with how many it shows. On both, a small ✕ beside a teacher's name takes that teacher off that
teaching group.
**Single teaching groups** are the whole-class rows and pull-out groups that are in no band, each with who teaches it,
with **Select all shown** and **Deselect all**. Tick rows and **Move** them into a band of their own level: a whole
class moved into a band becomes a group of it, and the band's classes widen to cover it. **Delete** removes a row.
**Banded teaching groups** are the bands as lanes, side by side, each with its groups (code, subject, students,
teachers). A click on a band's name opens a box to change it there (Enter saves, Escape leaves it); its groups and the rules
on step 6 that name it follow the new name. On a group, **Take out** makes it a single teaching group again and **Delete** removes it. **Delete band**
asks in the band itself: delete the band and its groups, or delete the band and keep its groups as single teaching
groups; it says when rules on step 6 name the band. With a subject or a teacher chosen, only the bands with a group
that matches are shown, each whole, with the groups that do not match faded. A delete is taken back by **Undo** at the
top. A teacher on two groups of one band is flagged on the lane. Moving a row changes later codes of that
subject (1MAP3 becomes 1MAP2): the page says which, and when a student list names the old codes it asks first and
says how many students are affected. The table view keeps the 15-column rows for bulk edits; its list of bands has a filter of its own (a level, a word of
the name, and only the bands with something to fix).

**How a group's periods split into lessons.** The Lessons column on step 5's table view shows the usual split in grey (20 periods with a
3-period lesson: 6×3 + 1×2). Type your own, such as `5x3 + 2x2` or `4x3 + 4x2`, on one row or on all ticked rows, or clear it to
go back. It must add up to the row's periods, and a band's groups should share a pattern; Things to fix flags both. The
workbook carries it in the Lesson pattern column on the Lessons sheet.

**Deploying in the table view.** On the same view, filter the teaching groups by level, subject or teacher, tick rows (shift-click
for a run), pick a teacher and **Make Teacher 1**, **Add as co-teacher** or **Take off** for all of them at once. The bar shows
the teacher's load now and with those groups; two groups of one band are flagged. In the teacher boxes and the bar's box,
the teachers of the subject's department (home or second) come first, then the others.
On step 4 (Teachers), filter by department (either department of a teacher counts), tick teachers and set their department,
role or allowance together.
A row may name up to three teachers (co-teaching), each blocked for the lesson and counted the full periods.
A lesson the form teachers take may hold as many as the school's most (never fewer than three). On the map its card shows
the school's word as a badge, and the table row shows "Changed by hand" when it applies. The committee can still
change one such lesson by hand; it is then marked "Changed by hand" and no longer follows step 2 until **Back to the
Form teachers** puts them on again. Heads of
department see these lessons and cannot change them.

**The teacher list.** On step 4 the committee can upload the school's teacher list. In a practice copy (the sample
school, to try things on) a head of department can too; on the school's own setup a head cannot. Paste
it, or choose a .csv file or, with the committee's code, an .xlsx file: for an Excel file the sheet is the first one
whose name contains "teacher", else the first sheet. The columns are Name, Short name, Department, Role, Allowance,
Other duties and Note, with the usual spellings of each heading (Teacher, Dept, Initials, Remarks and so on) read too.
Only Name is needed, and with no heading row the columns are read in that order. A column you leave out is not
changed: a list of names and roles leaves everyone's allowance as it is. A new teacher with no short name gets the
first word of the name. One with no allowance gets the guide allowance of their role when the row names a role on the
Roles table that has a guide; otherwise the allowance is left blank.
**Read the list** changes nothing: it shows "N new · M to update · K unchanged", names the new teachers, says what the
updates change (for example "Changes: allowance 80 · short name 12"), notes a row with no name or a name that is in the
list twice (that row is left out), and says if it cannot find a name column. A new name that looks like a teacher who
is not in the list ("Tan Wei-Ming" and "Tan Wei Ming") gets a warning: if they are one person, make the two names
match and read the list again, or Apply adds a second teacher. A role or department that is not yet on the setup is
listed, with **Add these roles** or **Add these departments**. **Apply** adds and updates in one step (one Undo takes
it back); an updated teacher keeps their lessons. Before a list that makes 10 or more
changes to the teachers, the server keeps a restore point (**Restore an earlier copy**, on step 7, brings it back).
Teachers who are not in the list are never removed by Apply: they are listed as "not in this list", and **Remove**
asks first, saying how many lessons on step 5 name them.
Removing a teacher takes them off the lessons they were on: those lessons lose that teacher, and a shared lesson keeps
its other teacher. Availability rules on step 6 that name them stay, and step 6 flags them.

**Teacher avatars.** Each teacher has a small face, on step 4 and on the map on step 5. It is worked out from
the teacher's name, so the same name has the same face wherever it is shown, and it is drawn in the browser from fixed
parts: no picture is uploaded or stored, and nothing is sent to an outside service. **New look**, on the teacher's
profile on step 5 (click any avatar on the map), gives the teacher another one by adding one to a number kept on the
teacher's row. The committee can do this for any teacher; a head of department only for a provisional teacher. The number is part of the saved setup only, so the workbook does not carry it and a setup opened
from a workbook starts with the faces the names give.

## Deploy on Railway

Each school runs its own copy: one Railway service with its own volume and access codes.
**[docs/DEPLOY.md](docs/DEPLOY.md)** walks through it: every variable with a safe default, memory, the first sign-in
and loading the setup. In short:

1. Fork this repository. Railway: **New Project → GitHub repo** → pick it (it has a `Dockerfile` and `railway.json`).
2. **Attach a volume** to the service, mounted at `/data`. The saved setup and the published timetable live there;
   without a volume they are lost on every deploy.
3. **Variables:** `SECRET_KEY` (a long random string; keep it), `COMMITTEE_CODE`, `TEACHER_CODE` and `STUDENT_CODE` (at
   least 6 letters or digits each, all different).
4. **Settings → Networking → Generate Domain**, open it and sign in with the committee code, then press "Make the first admin" on the committee page (or open `/admin/first`; see Admin page below). The sign-in page and the
   deploy logs list anything still missing (a code, `SECRET_KEY` or the volume).

### Admin page

`/admin` is for the named admins (people on the Timetable committee with Admin ticked, signed in with a username and
password). It has **Staff**, **Students**, **Ways in** and a link to the **History**. A person has **one role** (School
leader, HOD, SH, Teacher or Executive) and **any number of committees** (Timetable committee, Relief team, Exams and
events until a date); each committee adds its own access and none takes any away, so an HOD can also be on the
Timetable committee and the Relief team. On Staff you search and filter by role, committee and department, and press a
name or its **Edit** button to open that person's panel: their role, the departments a head changes the teaching groups
of, their committees, Admin (it needs the Timetable committee), **What this gives them** in plain sentences (the lines
marked ✱ need a password account), their username (changed later with **Change username**: they keep their password
and are signed out), a one-time password, a note, and Switch off. Or tick several people and use **Add to a committee**,
**Take off a committee** or **Set role**, print their code slips or switch them off, reading a preview of what it will
do before pressing the button. A change to a person's role, departments, committees or Admin signs them out everywhere.
**Remove this person** is at the foot of the panel for anyone who is not on the published timetable (added by name, or
left on the list after leaving the timetable): their username and password go, their code stops working, their
Telegram chat is unlinked and every session of theirs ends; what they changed stays in the History, and a removal cannot
be put back (add the person again with **Add a person**; the same name gets the same personal code as before). People on
the published timetable come from it, so they are switched off instead. **Ways in** shows each way to sign in and lets
you turn a shared code off or on, with its week's use. It needs `SECRET_KEY`. To make the first admin, sign in with the committee code: until an admin exists the
committee page says "No admin account yet. Make the first admin" (and `/admin` goes there too); you give your name, a
username and a password, and you are signed in as the first admin, on the Timetable committee with Admin ticked and
your role left as it was. If every admin forgets their password, set
`ADMIN_RECOVERY_CODE` in Railway variables (at least 16 letters or digits; a shorter one is ignored) and use
`/login/recover` once with an admin's username; then remove the variable.

### History

The history page keeps who changed what, and when, for two years. A change to the setup can be put back from there,
and an admin can put back a change made on the admin page (a role, departments, a committee, Admin, a note, switched off or on;
not a removal, not a change to a person who was removed since, and not an old entry that moved someone into or out of
the Timetable committee group). The
committee sees everything; a head of department sees changes to their departments and their own; everyone else who can
change something sees their own. After signing in, the home page shows "Since you last signed in", a short summary of
what changed since the person's previous sign-in. The committee can download the history as an Excel file.

Coming from a version that generated in the app: the `AI_*` and `SOLVE_SECONDS` variables are no longer read
([details](docs/DEPLOY.md#coming-from-an-earlier-version)).

## What the setup can say

These are read by the skill's solver (`ttgen`), which the outside agent runs, and checked again by the app on Publish.

A venue can be **made of** two or more rooms used together (a combined venue). On step 1, in the Blocks view, tick two or
more rooms of one kind and press **Combine**. The new venue's card shows "made of ..."; its seats start as the sum of its rooms'
and can be changed, and its kind follows its rooms. Deleting it leaves its rooms. Rules ("Only in venues") can pick it.
A room is in at most one combined venue, a combined venue is not made of combined venues, and it and its rooms take one group at a time.
A lesson in it is in each of its rooms, so it clashes with any lesson in either; the timetable names the combined venue.

A room holds one class at a time unless step 6 has a "Room · At most N at once" rule; a note on a Settings row such as
"Field and Hall take 2 classes each" is read as those rules.

**Constraints (step 6):** below the Configuration card, the constraints sit under five tabs by what they apply to:
**School** (whole-school fixed lessons such as CCE, the HBL day, school-wide rules), **Levels and classes** (fixed
lessons for a class or a group, rules for a level, class, band or group), **Subjects** (rules for a subject or a
department, such as lessons late in the day only in some rooms), **Venues** (room limits and bookings) and **Teachers**
(block-outs and teachers' rules). Each tab has its **Standard rules** table (the rule types below, with the Applies to
list narrowed to the tab), a **Typed rules** table and, folded away, the rule types that apply to the tab. **+ Add
rule** and **+ Typed rule** on a tab add a row for that tab.

**Typed rules** are anything the list cannot say: **Must** or **Prefer**, what it applies to (the whole school, a level,
a class, a subject, a venue or a teacher, from the same lists as other rules) and a sentence, such as "Must · Sec 1 ·
No PE in the first period". They are numbered T1, T2… in setup order and go to the workbook as More rules rows with
Rule = **In words** and the sentence in the **In words** column (an older workbook without the column still opens). The
timetable scripts never enforce them: `python -m ttgen check` lists each one "for the agent to honour", `SKILL.md` tells
the agent to honour every Must, try every Prefer and hand back a rule report, and step 7 counts them. A typed rule with
no sentence is flagged on step 6 and by `check`.

**Form teachers' lessons (step 6):** in the Configuration card, **Form teachers take these lessons** names subjects (tick
them from step 3). For every class, its whole-class lesson of each named subject then has the class's form teachers, all
of them together and in the order of the box on step 2, and follows that box. A missing lesson is made when the subject
has periods at the class's level. This is a default, and typed teachers are never replaced: when the class has form teachers and the lesson holds other
people, the lesson keeps its teachers and is marked "Changed by hand"; a lesson with nobody on it takes the form teachers;
a lesson with the same people simply follows. Turn it off by naming no subject; the lessons then stay as they are. The agent sees ordinary
lessons. A subject taught in groups is left alone. In the workbook, the Lessons sheet has as many Teacher columns as the
widest lesson needs (never fewer than three) and a **Changed by hand** column; the Classes sheet has one column per form
teacher, headed with the school's word and a number; Settings has three rows for the word, the most and the subjects. An
older workbook reads as before: no form teachers, the rule off, and teachers typed on a named subject's lessons kept.

**First and second choices (step 6):** below the constraints, **If it does not fit, give way in this order** lists items
that have a second choice. **+ Add a second choice** picks the item (a setting that is Yes/No or a number, a rule, or a
level's recess) and what to do instead: a setting takes the other value; a rule is made **Prefer**, replaced by another
rule (**Use this instead**) or **Drop**ped; a recess becomes floating between two times (recess for a level that has a
fixed recess). Drag the rows, or use the arrows, to set the order; an item has one second choice. Deleting a rule on step 6
removes its second choice; a workbook row whose rule or level has gone says what is missing. The workbook carries them on a **Choices** sheet (First choice and Second choice
columns, in order) with the pick from step 7. The agent tries the first choices; if no timetable fits, `python -m
ttgen solve` gives way one item at a time from the top of the list and stops at the first timetable that fits, never
changing anything that is not on the list (the setup's own rows are not changed: each fallback is applied to a copy).
With **Make one timetable for each** it makes the first-choices timetable and one more after each step of the list
(`... - after choice 2.xlsx`, or one folder each with `--export`) for the committee to compare. It hands back a
**Choices used** sheet (item, First or Second choice, how), also written to the database, which Publish reads. Step 7's
"Will it fit?" also says whether the sums pass after giving way ("With the first choices, 1 thing will not fit. Giving
way in your order, the sums pass after choice 3: ...") or that they fail even after every second choice. Heads of
department see the list but cannot change it.

**Rules (step 6):** besides teacher block-outs, three common school rules have their own one-click rows. **Every
class at one time** puts a subject at one slot for every class of a level, or of the whole school (Fixed lessons, Class
"Every class", Level All), such as whole-school CCE: one row per slot. **HBL day** (the rule *Only these subjects*) lets
only the subjects ticked be taught in those periods; tick a department for all its subjects, or a subject for all its
G1/G2/G3 groups. **Lessons late in the day only in some rooms** (*Only in venues*) keeps a subject's lessons that run into
the periods picked to the rooms picked, such as PE after 11.00 only in the hall. Under every rule the solver cannot use
as written (a rule name it does not know, a level or subject not on the setup, a rule that matches no lesson) step 6
says what is wrong and what happens to it; opening a workbook says how many there are, and `ttgen check` lists them.
Fixed lessons that put one teacher or one class in two places (a whole-school CCE slot when a teacher takes CCE for two
classes) are critical, with the teacher named.

**Rooms:** a group only goes in a room of its subject's kind that seats it (Venues **Capacity** = seats; the group size
is the Students sheet count for its code, the row's Students, or the class size). A room's **For** column keeps it for
some subjects, departments or levels (blank = anyone). A lesson row's **Special room weeks** (Odd or Even) gives the
group its lab or studio on that week only and a classroom on the other. The solver keeps enough suitable rooms free at
every period; afterwards each group gets the smallest free room that seats it (whole-class lessons their home room,
and a group keeps its room where it can). The checks flag a room too small, a room used against its purpose, a lesson
with no free room, and groups bigger than every room they may use (fix the seats or split the group). About 1 GB of
memory is enough for a 1,500-student school.

**Floating recess:** paint **W** (recess window) periods on Day structure where the recess may go, for example
periods 5-10 instead of a fixed recess at 7-8. The solver places the recess inside each window and uses the rest of
the window for lessons. Settings: **Floating recess goes by** Level (the whole level goes together, its time may
differ by day) or Class (each class on its own); **Floating recess length (periods)**; **Most classes at recess at
once** (canteen space; fixed R recess counts too; blank = no limit). Make each window the recess plus whole lessons
(2 + 3 + 3 periods with 3-period lessons), so the lessons still fit wherever the recess goes: on a full school, a
recess that leaves an odd period beside it costs a lesson, and a tight canteen limit can then leave no timetable. With "Every teacher gets at least one recess a day"
on, every teacher is free for a whole R recess, or the recess length inside a W window, each day. The class timetables,
PDFs and pages show each class's own recess; the timetable workbook lists them on a Recess sheet.

A big, tight school (30 or more classes) is best solved level by level, hardest level first: the skill's
`python -m ttgen solve --staged` (`ttgen/staged.py`). One whole-school search can find nothing for hours.

## Run locally

```bash
pip install -r requirements.txt
export SECRET_KEY=dev COMMITTEE_CODE=COMMIT1 TEACHER_CODE=TEACH1 STUDENT_CODE=STUDY1 HEADS_CODE=HEADS1   # HEADS_CODE is optional
python app.py            # http://localhost:8000  (or: gunicorn app:app --workers 1 --threads 8 --timeout 600)
.venv/bin/python tests/smoke.py          # server checks; add --full for the slow publish check (SMOKE_NO_HEADS=1: without a heads' code)
.venv/bin/python tests/test_sync.py      # the setup changes, in Python
node tests/sync.test.js                  # the same changes, in the browser's JavaScript
node tests/people.test.js                # reading a teacher list and the avatars
node tests/split.test.js                 # periods cut into lessons, as ttgen cuts them
node tests/classview.test.js            # step 2's cards and band picture
node tests/venueview.test.js            # step 1's blocks view
node tests/subjectview.test.js          # step 3's subject cards
node tests/teacherview.test.js          # step 4's teacher cards and the second department
node tests/relief_telegram.test.js      # relief: the Link Telegram card
node tests/relief_today.test.js         # relief: Today, what was sent and Remind
node tests/relief_settings.test.js      # relief: the Telegram card in Relief settings
node tests/relief_summary.test.js       # relief: the weekly summary
node tests/relief_inbox.test.js         # relief: What's in, how an absence was asked for
.venv/bin/python tests/test_venues.py   # equipment and configuration through the workbook
.venv/bin/python tests/test_combined.py # venues made of two or more rooms (add --full for the solve)
.venv/bin/python tests/test_teachers.py # the Teachers sheet: Department 2, an older workbook read as before
.venv/bin/python tests/test_typed.py     # the typed request: reading the words, matching names, the ways
.venv/bin/python tests/test_relief.py    # relief: personal teacher codes, people, settings, calendar, routes
.venv/bin/python tests/test_relief_requests.py  # relief requests: lessons, the free-then list, absences, work files, routes
.venv/bin/python tests/test_relief_telegram.py  # relief on Telegram: the client, linking, the queue, messages, answers, reports (no network, no token)
.venv/bin/python tests/test_exams.py     # exams and events: days, papers, seating, invigilators, routes
```
To try the **Ask in words** box without a key, start with `TYPED_REQUEST_MODEL=mock`: it understands "move <subject> for <class> off <day>" and "give <class> <subject> to <teacher>".
To try relief's Telegram pages without a bot, start with `TELEGRAM_BOT_TOKEN=practice`: nothing is sent to Telegram, and nobody can link there, so no message is made.

Keep one gunicorn worker (with threads): publishing swaps files in under a lock held in the web process.

**Saving the setup.** There is no Save button: every change is saved for the school by itself, on the volume, and the
setup opens by itself after signing in, on any browser. Several people can work in it at once. Changes to different
things all stay; if two people change the same field, the later one wins and the other sees it within a few seconds.
The header shows **Saved**, **Saving** or **Offline**, and how many others are in the setup. **Undo** / **Redo**
(⌘Z / ⇧⌘Z) take back only your own changes. Changes made while the server cannot be reached are kept in the browser
and sent when it can. While people work the server keeps a restore point about every 10 minutes (the last 48), and one
before every whole-setup action; **Restore an earlier copy** on step 7, Download, brings one back. The sample schools
open as a practice copy: nothing in it is saved for the school. Starting blank, opening a setup workbook, loading from
a file and restoring an earlier copy replace the setup for everyone: they are for the committee only, they ask first,
and an earlier copy is kept. **Save to file** and **Load from file**, on step 7, keep copies as files.

## What's inside

| Path | What |
|---|---|
| `app.py` | routes: sign-in, the committee's editor, the downloads, check and publish, the timetable pages, PDFs |
| `access.py` | access codes (committee, heads, teachers, students), personal codes, wrong-code limit (10 per 10 minutes per address) |
| `relief/` | relief: the people it knows (the published teachers and other staff), personal teacher codes, the settings, the school calendar; a teacher's lessons on a date, the free-then list, absence records, work files and the request routes (`web.py`); on Telegram: `tg.py` (the one place that calls Telegram), `tgdb.py` (its file on the volume), `links.py` (who is linked), `outbox.py` (the queue and the sender), `tell.py` (what there is to tell), `bot.py` and `asking.py` (what people press and type, `/relief`), `report.py` and `summary.py` (the reports and the week), `tgweb.py` (its routes) |
| `static/relief.html`, `static/relief-settings.html` | the Relief home (`relief.js`: My absences, Ask for relief; `relief-plan.js`: Plan relief, Planned by me; `relief-inbox.js`: What's in; `relief-telegram.js`: Link Telegram; `relief-summary.js`: Weekly summary; `relief-form.js`: shared) and the Relief settings page, with their scripts |
| `tests/test_relief.py` | relief: codes, people, calendar, settings and the routes |
| `tests/test_relief_requests.py` | relief requests: lessons, the free-then list, absences, files and their routes |
| `tests/test_relief_telegram.py` | relief on Telegram, on the server: no network, and never a real token |
| `tests/relief_*.test.js`, `tests/dom.js` | relief's page scripts, run with Node in a small stand-in for the browser |
| `checks.py` | will it fit: the sums on a setup before it is downloaded (class periods, breaks, rooms, teachers' time) |
| `store.py` | the shared setup (version, change log, restore points) and the published timetable on the volume |
| `sync.py` | setup changes as small operations: apply, merge, and what a head may change |
| `static/sync.js` | the same operations in the browser; Node can run it for the tests |
| `tests/smoke.py` | server checks, run with plain Python (no test runner) |
| `tests/test_sync.py`, `tests/sync.test.js` | the setup changes, checked in Python and in JavaScript against the same cases |
| `static/people.js` | reading a teacher list, matching it to the teachers already there, and drawing the avatars; Node can run it for the tests |
| `typed.py` | the typed request (**Ask in words** on step 8): the one place a language model is called (the words in, a small request out), then the names matched to the draft and the ways checked, with no model |
| `tests/test_typed.py` | those, with no network and no key |
| `tests/people.test.js` | those checks, run with Node |
| `static/parents.js`, `ttgen/parents.py` | the form teachers' rule, written twice for the page and the server and kept in step by `tests/parents_cases.json` |
| `tests/parents.test.js`, `tests/test_parents.py` | those cases, run with Node and with Python |
| `tests/split.test.js`, `tests/split_cases.json` | how a subject's periods are cut into lessons, the same on the page and in `ttgen` |
| `static/` | the committee's step-by-step editor and the sign-in page style |
| `ttgen/` | the Python package: template, reader, solver, checks and the Excel/PDF/HTML outputs |
| `skill/school-timetable-generator/` | the skill (`SKILL.md` + `scripts/ttgen`) for any AI agent outside the app |

`ttgen/` and `skill/school-timetable-generator/scripts/ttgen/` are the same package; change both together.

## Command line (without the app)

```bash
cd skill/school-timetable-generator/scripts
pip install -r requirements.txt
python -m ttgen check  My_School_Timetable_Setup.xlsx
python -m ttgen solve  My_School_Timetable_Setup.xlsx --out My_School_Timetable.xlsx --time 300 --export My_School_Outputs
python -m ttgen export My_School_Timetable_Setup.xlsx My_School_Timetable.xlsx --out My_School_Outputs
```

# Plan with AI: a chat that asks, fills in and makes an exam

Date: 22 November 2026. Status: **approved by the committee lead on 22 November 2026** ("Approved, plan it"); nothing is
built. Reviewed once by a builder's reading and corrected. Mockups, all with made-up names: `2026-11-22-ai-planning-chat-mockups.html` beside this
file (open it in a browser; one tab per screen).

## What the lead asked for

In the lead's words, in order:

- "I would like an AI capable dialogic to help plan for the timetable (Use Opus 5.5 and High effort)".
- Asked when they would open it and what they would type: "Example, I would like to plan an exam timetable.. then it will
  ask me what i need, who and what are their roles and help me populate and then generate".
- Asked who should set the papers' dates and times: "Chat suggests them". Asked what they go by when they set them by hand:
  "Just the agreed date and time for the subject by the school management".
- Asked which roles besides invigilator, chief invigilator, backup invigilator and left out: "Just those four".
- Asked whether the chat fills in the draft at once or waits for an OK at each step: "fill at once".
- Asked what the chat should plan after exams: "Events".
- Asked how it should be built: "A: AI leads".

**How the two answers about times are read together** (the writer's reading, put to the lead and not corrected): the times
are agreed by the school management outside the app, so they are something the chat takes in. The chat suggests a time only
for a paper that has no agreed time, and marks it as a suggestion. It never changes an agreed time by itself.

## Why

The exams module (stages 1 to 4, on main) can already hold a whole exam and make its venues, seats and invigilators. But the
person planning one has to know which of eight tabs and one settings page to fill in, in what order, and finds out what is
missing only when Make refuses. The lead wants to be asked instead: what do you need, who is involved, in what role; then to
see it filled in, and to press one button to have it made.

## Goals

- A person types what they want to plan. The chat asks for what is missing, a question or two at a time, and takes the
  answer in their own words.
- Each answer is filled in on the exam's draft at once, shown as a line saying what was done, with **Take it back**.
- The agreed list of papers goes in by pasting it or giving a file; every line is shown as the app read it, and the app's
  own checks say straight away what does not work.
- The people are asked for by their four roles.
- When nothing is missing, the person presses **Make**. The app's fixed rules choose venues, seats and invigilators, as
  today. The chat then says in plain words what came out and what needs a person.
- Stopping and coming back days later works: the draft holds everything, and the chat asks only for what is still missing.
- The second exam of the year is much shorter: what is already set from the last one is offered as "Keep as last time?".

## Non-goals

- Choosing invigilators, rooms or seats with the AI. Make stays the app's fixed rules (the lead's choice of 20 November).
- Working out a whole exam timetable from nothing. The times are agreed by management; the chat takes them in.
- Reading photos, scans or PDFs. The app cannot hide names in a picture before it goes to the AI, and it has no reader for
  PDFs. The person pastes the text instead.
- Students who need extra time, their own room, a reader or a scribe; and which students sit a make-up paper. Those stay on
  the exam page's own forms. The chat reminds and links; it never sees them.
- Making the weekly timetable. The app stopped doing that on 9 November 2026.
- New roles (standby, script collection, hall in-charge): "Just those four".
- Events, the weekly setup (steps 1 to 7) and the typed chat of step 8 ("Ask about this", stage 2, approved and not built).
  Each is its own project later and uses the same chat; see Stages.
- Talking to anyone but the person at the page: no messages, no Telegram.

## Anti-goals (would make it a failure even if it works)

- An agreed time is changed, or a suggested time is taken for an agreed one, without a person knowing.
- Anything reaches the main site, the timetable committee or another person because of something the AI wrote.
- The chat says something is free, clear or seated that the app has not checked (above all while there are no students, or
  where extra time is the only problem).
- A student's name or ID as the app knows it, or their extra time or own room, is sent to the AI; or a teacher's name in one
  of the forms below.
- The chat's words and the draft disagree: it says "done" and the draft was not changed, or the other way round.
- What the chat filled in is lost because the exam page was open in another tab, or the other way round.
- The AI being slow, off or over its limit stops anyone using the exam pages.
- Anything of a talk is written to the server's disk or its logs.
- A test, a probe or a review calls a real AI.

## Who uses it

Whoever may change exams today, with the same right checked on the server at every step: a person with the **Exams and
events** extra (until its end date) and the **timetable committee** (a member signed in, or the shared committee code). The
chat has exactly the rights of the person typing, and none of its own. If a right ends in the middle of a talk, the next
step is refused with the sentence the exam page would give.

## Approaches considered

- **A. The AI leads, using only the app's own tools (chosen: "A: AI leads").** The AI holds the talk and decides what to ask
  next. It can act only through a fixed list of the app's actions (below). The app makes every check and every change, and
  words every button. It handles any order, changes of mind and "why?". It costs a wait, from several seconds to about a
  minute an answer at high effort, and about 5 to 15 US cents an answer, so a few dollars for planning a whole exam (worked
  out from the AI's published prices; not measured, since no test may call the AI).
- **B. The app asks fixed questions; the AI only reads each answer.** Quick, a cent or two an answer, always the same order.
  Nobody can go off the list, change an earlier answer easily or ask why. Closer to a form than the dialogue the lead asked
  for.
- **C. The AI is given everything and returns a finished draft.** Asks nothing, sends the most data, and leaves the person to
  check it all at the end. Dropped.
- **The AI company hosts the assistant.** It would keep each talk on its side until deleted, which "not kept" excludes.
  Dropped.

## What it is

### Where it is

- A tile **Plan with AI** on the home page for people who may change exams, and the same button on the **Exams, tests and
  events** page (people on the shared committee code have no home page).
- It opens a page of its own, `/plan`: the talk on the left; on the right **Filled in so far**, which is read from the draft
  itself, with a link from each line to the tab of the exam page where it lives. On a phone the panel folds up above the
  talk.
- With no AI set up on the server (`typed.enabled()` is false) the tile and the button are not shown.

### Starting

The page opens with "What would you like to plan?", a box to type in, and buttons: **Plan an exam**, **Plan a common test**,
and **Carry on: <name>** for each exam that is not on the main site. Typed words that ask for something the chat cannot plan
yet (an event, the weekly timetable) get a sentence saying so and a link to the page that does it.

Before the first question the app itself checks what is missing for the whole job, and the page says it at the top, so it is
not found at the end:
- No published timetable, or no school calendar: the chat cannot start; it says where to set it.
- **No students in the published timetable**: the papers, days, people and rooms can be filled in, but **clashes between
  papers cannot be checked, no time can be suggested, and Make refuses**. The page says so and links to the Students step.
  What does not need students is still checked (a school day, inside the level's exam time, "sits with" papers together),
  and the app adds "Clashes not checked: no students yet" to every result, so the chat cannot call the list clear.
- No exam rooms set: it says so; the rooms are asked for on the way.

### What it asks for

The order is the AI's to judge; the list is the app's. "Filled in so far" shows each line as done, to check, or still to do.

| | What | Where it is kept |
|---|---|---|
| 1 | Exam or common test, name, levels or classes, dates | the draft (made at this point) |
| 2 | Each day: which levels are on it, whole day or part of it | the draft |
| 3 | The agreed list of papers: level, subject, paper, length, date, start, who sits, sits with | the draft |
| 4 | Papers with no agreed time | the draft, marked as suggested |
| 5 | Report time, least break between papers, most papers a day | the draft |
| 6 | Chiefs, backup invigilators, left out | exam settings (every exam) |
| 7 | Exam rooms: which, exam seats, rows and columns, which are halls, which are for access arrangements | exam settings (every exam) |
| 8 | Invigilators per classroom, students per hall invigilator, a chief in each hall, arrive and stay minutes, most duties a day, not in a paper of their own subject | exam settings (every exam) |
| 9 | Seating order, shared rooms, spacing, own classrooms; for a common test, who supervises; where scripts go | the draft |
| 10 | Extra time, own room, reader, scribe | a form on the exam page; the chat links to it |

Lines 6 to 8 are kept between exams already. For lines 5 and 9 the app offers the values of the newest earlier exam of the
same kind (exam or common test), whatever its status, else its own defaults. The chat says all of them in one go and asks
"Keep as last time?", so a person who agrees answers once. A new exam made on the exam page starts as it does today.

**Someone who should not invigilate.** The "left out" list holds for every exam until changed. If the person says why and it
is only for some dates ("on leave"), the chat says that leave put into relief already keeps that teacher off duties on those
dates, and links to it, before it offers to add them to the left-out list.

### The agreed list

The person pastes the text (an email, a table copied from a document) or gives an Excel or Word file.

1. A file that is already in the app's own paper-list layout is read by the app, with no AI.
2. Otherwise the app takes the text out, replaces names (below), and the AI reads it into lines: the words as written for the
   level, subject and paper, and the length, date and start. This is a job of its own, done in pieces, outside the answer's
   limits (at most 5 minutes; the page shows how far it is). The raw text does not stay in the talk; the app's result does.
3. The app checks every line against the published timetable. Three things can happen:
   - **The words are the timetable's own** (the subject's name, code or short name at that level, whatever the capitals,
     spaces and brackets): the line goes in at once.
   - **The words are different but the AI can tell what is meant** ("E Maths" for Mathematics; "Mathematics" where the level
     has Mathematics G1, G2 and G3; "Mother Tongue" for Chinese, Malay and Tamil): these lines are shown **together, once**,
     in a table "As written / Read as", and go in when the person says yes to the table or corrects a line. A line that
     stands for several subjects becomes one paper for each, at the same time, tied with "Sits with". What was agreed for one
     set of words is used for every line with the same words.
   - **It cannot be matched**, or its date, time or length is not one: it is not put in; it is listed with the reason and
     asked about.
4. What goes in is shown as a table, with **Take it back**. A paper already there with the same level, subject and paper name
   is changed, never doubled, and the line says what it was before.
5. The app's own checks on times run straight away, and each problem is said in plain words with both papers named ("12 Sec 3
   students have Geography and Physics at the same time on 6 Oct"). The chat asks what to do.

Subjects of the chosen levels with no paper in the list are named once ("No paper for Sec 2 Art: is there one?").

### Agreed and suggested times

The server, not the AI, decides which a time is:

- **Agreed:** it came from a line of the list; or the person gave it in their own words. To set or move a time at once, the
  chat must hand the server the person's own words it is acting on, and the server checks that those words are in what that
  person typed or pressed since the last answer. Without them the step is refused. So an agreed time moves only when the
  person has just said so; the line shows the time before and after, with Take it back.
- **Suggested:** it is one of the times the app offered for that paper. Only a paper with no agreed time gets a suggestion,
  and only after the person says yes to one. The **app** works out the times that pass its checks for that paper (no student
  with two papers at once, inside the level's exam time, within the papers-a-day limit, the least break kept) and the AI says
  up to three of them with a reason.

A suggested time is marked **suggested** in the talk, in "Filled in so far", and on the exam page's Papers tab, until a
person changes the time or presses **Agreed** beside it. The Approval tab shows how many are still suggested, as a note; it
does not block sending.

### What the chat may do

| | What |
|---|---|
| **At once**, each with Take it back | Start an exam or common test. Fill in lines 1 to 5 and 9 above: add, change or remove papers, days, times, seating choices. |
| **Only when the person presses** | Exam settings that every exam shares (lines 6, 7 and 8). Make. Any change to an exam that is waiting for approval or on the main site. |
| **Never** | Send, approve, send back or withdraw. Delete an exam. Extra time, own room, readers and scribes, or which students sit. Who is on the exams committee, accounts and rights. The school calendar, relief, the setup or the published timetable. |

This table was shown to the lead with "Change any line you disagree with"; they changed nothing.

- **A press** is a card written by the app from the change itself: what it is now, what it would be, and a button
  (**Change the settings**, **Make seats and duties**, **Make the change**) beside **Not now**. Words the AI writes can never
  be such a button, and a card that no longer fits (something changed meanwhile) says so and is not applied.
- The AI may offer up to four **quick answers** under a question. Pressing one only types it.
- A draft, a sent-back or a withdrawn exam is filled in at once. One that is **waiting** or **on the main site** gets a card
  for every change, which is then saved as the exam page's own change would be ("Changes not sent yet", for a person to
  send). An **ended** exam can be read and not changed.

### Take it back

Each step the chat does is one line in the talk: "✓ Put 31 papers in the draft. See them · Take it back". Take it back puts
exactly the parts that step changed as they were. If any of them was changed since, by hand or by someone else, the app says
which, who saved the exam last, and leaves those as they are. Steps can be taken back in any order under that rule. Taking
back "started the exam" is offered only while nobody else has changed it; it removes that draft.

A pressed settings card can be taken back in the same way. Make cannot (press Make again). Once the exam has been sent, or is
on the main site, its earlier steps can no longer be taken back from the talk, because that would undo what the timetable
committee is looking at; the line says "Sent since: change it on the exam page." "By whom" is the last person who saved the
exam; the app keeps no record part by part.

Take it back lasts as long as the talk does. After that, changes are made on the exam page.

### Make, and what came out

When nothing is left to do, the chat offers Make as a card; the button is also under "Filled in so far" and says what is
missing if pressed too early. It is the same Make, with the same refusals. Afterwards the **app** gives the figures (seated,
not seated, duties, short, backup needed, rooms over) and, for each duty that is short, **counts** of why nobody else could
take it: on another duty or event then, teaching a lesson that runs, away, marked not available, left out, at the most duties
a day, teaches the subject (when that rule is on). Counts only: no names, and never why a person is away. The chat explains
these and answers questions about them ("Why is Hall B short on the 7th?") from what the app says; when the app does not say,
the chat says it does not know. Then it links to the exam page: the seating plans, the roster, and the Approval tab, where a
person sends it.

### The exam page and the chat together

The exam page saves the **whole** exam a moment after each change, and today it does not notice that the exam changed since
it was opened: a page left open in another tab would undo what the chat filled in. Two committee members on the same exam
already undo each other that way. So, as part of this project: every save says which copy it started from, and a save
started from an older copy is refused with "This exam was changed by <name> since you opened it. Reload to carry on." Events
use the same saving and get the same check. The exam settings page saves its whole file too, and gets the check with the
settings cards in stage 2. The chat's own steps change only their own parts of the stored exam, so they never undo someone
else's.

### What is sent to the AI, and what never is

- **Sent:** the typed words; the text of the agreed list; and, as the chat asks for them, the draft's own parts (name, dates,
  days, papers, choices), levels, class names, subjects, counts of students, room names and seats, period times, the exam
  rules and numbers, the app's check sentences, and the figures after Make.
- **Teachers go as codes** ("T07"), in everything that is sent: typed words, the list, the app's sentences, the roles, the
  duties. The codes become names again before anything is shown. Caught as a name: the full name; the short name; a title
  with any part of the name ("Ms Tan" for Tan Wei Ling); any two or more words of one person's name side by side, in any
  order. In **typed words** also a capitalised single word that is part of a teacher's name. In a **list** single words and
  short names are left alone. Nowhere is a word made a code when it is a day, a month, or a level, class, subject, subject
  code or room of the timetable ("May", "Art"), so that a list's dates and subjects are never changed. A name that fits
  several people goes as those people's codes, and the chat asks which.
- **Students:** the ID, the full name, or two or more words of one student's name side by side, typed or in the list, becomes
  "a student" before it is sent, and the chat says those go on the form. A student's first name alone is sent as typed.
- **The school's name** becomes "the school".
- **Extra time:** the checks the AI reads are worked out **as if nobody had extra time**. When the full check finds more, the
  app itself tells the person ("2 more points with extra time: see the Papers tab") and tells the AI only that there are
  points it cannot see. Whether nothing is left, and whether Make may be offered, is decided by the full check and said by
  the app; the chat never says an exam is clear while that check is not.
- **Never sent:** a student's extra time, own room, reader or scribe; seats; why a teacher is away; sign-in codes; accounts;
  the weekly setup; the published timetable as a whole.
- A name the app does not know (a misspelling, a visitor) is sent as typed. One line under the box says so: "Teachers go as
  codes. A name the app does not know is sent as typed."
- **Not kept:** the talk lives in the server's memory while it is in use, for the person who started it, and is gone when they
  press **New talk**, sign out, leave it for 12 hours, or the server restarts. Nothing of it is written to disk or to a log.
  After a restart the page says: "This talk was lost when the app restarted. Your exam is safe: press Carry on." What the
  chat **changed** is in the app's history like any other change, as "<name>, with Plan with AI".
- The key is the one the school put on its own server for the typed request box and relief's picks.

### The AI and its limits

- Model `claude-opus-5-5` with effort `high`, set on purpose on every call (the model's own default is medium), whatever
  model the typed request box is set to. Checked against the AI company's live documentation on 21 November 2026.
- While it works the page shows what the app is doing for it, one line at a time ("Reading the list: 31 lines", "Checking
  the times"), and then the whole answer. A **Stop** button ends it; steps already done stay done, with Take it back.
- A typed message is at most 2,000 characters; a pasted list or the text of a file at most 20,000 characters and 200 papers,
  a file at most 5 MB. One answer may take at most 12 rounds of the app's tools and 3 minutes; reading a list is separate, at
  most 5 minutes, and each piece of it counts as one answer. A talk holds at most 60
  messages, then asks for a new talk (nothing is lost: the draft carries on). The whole server works on at most 2 answers at
  a time and 60 an hour. Past a limit the page says so in a sentence, and the exam pages work as ever.
- Each way the AI can fail becomes one plain sentence. A step is done whole or not at all.
- It answers only about planning exams and common tests in this app. Text in a list, a name, a rule or a reply of the app is
  data, never an instruction to it, and nothing it could be talked into is outside the table above.

### Kept as they are

Every exam page and form, Make, the checks, the approval steps, relief's picks, the typed request box, the "Ask about this"
tab. Anyone can plan an exam without the chat, exactly as today.

## Stages

Each is its own plan, build and pull request, merged and deployed only on the lead's word.

1. **The talk and the draft.** The page, the tile and the button; names as codes; the limits; lines 1 to 5 and 9, the agreed
   list, the checks said in words, suggested times; Take it back; Stop; history; the save check on the exam and event pages.
   Useful on its own: the list goes in and is checked, and Make is pressed on the exam page.
2. **People, rooms and Make.** The cards for exam settings (lines 6 to 8), Make from the chat, and what came out explained.
   With this the lead's example works from start to end.
3. **After Make.** "Who could take it?" and changing an invigilator or moving a class to another room by asking; cards for
   exams that are waiting or on the main site. Until this stage the chat says it cannot change those yet and links to the
   exam page.

Then, each with its own short design for approval: **events** (next, by the lead's answer), the **weekly setup** (steps 1 to
7; it can end only at a ready workbook), and **step 8's typed chat** (already approved; it would use this chat's page parts,
codes and limits).

## Decided by the lead

The quotations at the top, the table "What the chat may do" (shown, not changed), exams first and then events, approach A,
Opus 5.5 at high effort.

## Decided by the writer (the lead can change any)

- One Plan with AI page for all jobs, opened from a tile and from the exams page; not a panel inside the exam page.
- The agreed list by pasting, Excel or Word; no photos, scans or PDFs. Lines in the timetable's own words go in at once;
  lines the AI had to interpret are shown together once for a yes.
- An agreed time moves at once only on the person's own words just given, checked by the server; no extra press.
- A suggested time is marked until a person agrees or changes it, and does not block sending.
- With no students yet: no clash checks, no suggestions, no Make, and it says so everywhere.
- "As last time" means the newest earlier exam of the same kind.
- The AI's checks leave extra time out; the app itself tells the person about those points.
- How names are caught, and what is sent as typed: one-word first names of students, and single words in a list.
- Students' needs and make-up students stay on forms. Student names become "a student".
- The left-out list is for every exam, so leave is pointed to relief first.
- The talk is not kept; the draft is. Take it back lasts as long as the talk.
- A card, not an instant change, for exams that are waiting or on the main site.
- The save check on the exam and event pages.
- The limits: 2,000 characters, 20,000 for a list, 200 papers, 12 rounds, 3 minutes, 60 messages, 2 at a time, 60 an hour.
- Shown to exactly the people who may change exams; nothing for teachers until events.
- The three stages.

## Left to the builder

- The AI's fixed instructions and the exact list, names and shapes of the tools, as long as the table "What the chat may do"
  holds **in the server** (each tool is refused there), not only in the instructions.
- How the naming rules above are built: relief's `pick.py` finds some of these forms and misses others (a title with the
  first word of a name, two words in another order). Use one shared place for the chat and, later, step 8, and keep the same
  code for the same person through a talk.
- How a step's "before" is kept for Take it back, and how the suggested mark is kept so that setting or clearing it does not
  make the made seats and duties stale and is not shown on the main site.
- How the page follows an answer while it is worked out (a stream or short polls).
- What the practice stand-in (`TYPED_REQUEST_MODEL=mock`) says: enough to walk a whole exam in a test and in a browser.
- The exact words, except those quoted here.

Facts the builder needs:

- The server runs one process with 8 threads and a 600-second limit (`Dockerfile`). An answer holds a thread for its whole
  length, hence 2 at a time. **Never hold `exams.schedules.editing()` while waiting for the AI**: take it inside a step only.
- For this model: thinking is always on and cannot be turned off, effort is `output_config.effort`; a forced `tool_choice`
  is refused (use `auto`, with `strict` tools, and check what came back); a reply may end in `refusal` or `max_tokens`, read
  before its content; thinking counts toward `max_tokens`. Thinking blocks are tied to the conversation: within a talk the
  instructions, the tools and every earlier message must be sent back **unchanged**, only ever added to. So the tool list
  stays the same all through a talk (a tool that is not allowed now answers with a sentence), and changed facts are added,
  not edited in. `typed.py` shows the key, the server-side fallback and the failure sentences to follow; its one cached
  client has a 12-second timeout, so the chat needs its own.
- `schedules.save` checks the whole exam and `_save_exam` records it in the history; `papers.check` gives the errors and
  warnings; `papers.read_paper_list` reads the app's own layout; `make.make` with its refusals is `_exam_make` in `app.py`.
- New routes join the table of guards that `tests/test_routes.py` checks. `_exams_gate` works rights out once per request and
  keeps them; an answer of several rounds in one request must read the person's record again at each step.
- "Seated" and "rooms over" are not in the server's figures today (`make.summary` has neither; the page works them out): the
  chat needs them on the server. So are the counts of why a duty is short (`invigilate.candidates` drops people without
  keeping why).
- `approval.approve` refuses when the exam changed after it was sent.
- On the live site the published times are a 12-hour clock without am or pm; use `exams.days.bounds`.
- The build follows the project's habits: no real names in code, tests or documents; every suite before a pull request; the
  school's real files only through the server's functions, as counts.

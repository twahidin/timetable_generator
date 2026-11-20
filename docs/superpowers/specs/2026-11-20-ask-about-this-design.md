# Ask about this: point at a lesson or an empty period on step 8 and ask for what you want

Date: 20 November 2026. Status: design, awaiting the committee's approval of this document. A project of its own,
on top of "Upload and edit" (`docs/superpowers/specs/2026-11-16-upload-and-edit-design.md`), which it leaves
standing: the board, the panel beside it, the checks and the way a change is kept are not redesigned here.

## Why

The committee lead has used step 8's board on the school's real timetable since it went live on 17 November. This is
their first report on it. Dragging works, but finding out *what is possible* is slow: to fill a gap, or to find a
colleague who could take a class, the lead has to try places and lists one at a time. In their words:

- "click on any lesson or a group of lessons on a period and empty periods and right click or pop up a dialogic
  agent such that I can ask if I can fill the space, swap with another lesson or swap with another teacher."
- "what I meant is that I can use a dialogic chat to type what I want for the period, example find me another
  teacher that I can trade this class with that is free or in the same department or teaching similar subjects."
- "Or fill in the empty slot."

They also asked for a timetable view of one class, one teacher or one venue. That view exists already (a click on a
row's name opens that row's whole cycle, and every edit works there); they had not found it, and on finding it said
"that is fine". So no new view is built. What is built is the asking.

## Who uses it

The committee lead and the committee, at a desk, on step 8. Nobody else sees it.

## What it is

### Pointing at something

- **A lesson.** Right-click a lesson's card, on the board or in "Not placed". Or select it and press **Ask** on the
  line above the board.
- **A band.** A band is one card with several groups, each with its own subject, teacher and room: this is what "a
  group of lessons on a period" means here. Pointing at it is pointing at the band. A question about time (swap,
  move) is about the whole band, which moves as one. A question about a teacher or a room is about one group: the
  group of the teacher's or room's row that was clicked, or, on a class's row, the group the lead picks from the
  band's groups listed at the top of the tab.
- **An empty period of a row.** Right-click an empty period on a row: a class's, a teacher's or a room's, on the day
  board or in a whole cycle. Or click it with no lesson selected (today that click does nothing) and press **Ask**.
  The thing pointed at is the place: that row, that day, that period.
- A click with a lesson selected still moves that lesson there, as today. The browser's own right-click menu is
  replaced only on cards and periods of the board.

Pointing opens a fifth tab in the panel beside the board, **Ask**, with what was pointed at written at its top
("2A Mathematics · Odd Mon periods 1 to 2 · Adam Lee · B2-4", or "2A · Odd Mon period 4 · empty"). The board stays
in view. Selecting cards while working does not change what the Ask tab is about; only pointing with Ask does.
Asking about a new thing starts a new conversation; the earlier one stays readable above it until **Clear**.

### Asking

Two ways, in the same tab:

- **Starter questions**, as buttons, chosen by what was pointed at. For a lesson: "What can this swap with?",
  "Where else can it go?", "Who else could teach it?", "Who could I trade this class with?", "Which rooms could it
  use?". For an empty period: "What can
  go here?", "Who is free then?". The app answers these itself, at once, with no AI.
- **Typing what you want**, in a box under the conversation: "find me another teacher I can trade this class with,
  free then or in the same department or teaching similar subjects", "fill in this empty slot", "not her, she is on
  leave", "only on a Friday". This goes to an AI, which answers in a few sentences and in options. The conversation
  goes back and forth: a second question builds on the first.

### Answers are options

Every answer that proposes a change is a list of **options**. An option is one change, or two made together. It is
written as an instruction ("Give 2A Mathematics to Bala Nair", "Swap with 2A PE, Odd Tue periods 2 to 3", "Place 2A
Art, waiting in Not placed"), with what else it disturbs under it (the other lesson of a swap, a teacher's periods
rising from 24 to 30 of 32, the gap a move leaves) and one of three verdicts, the board's own: **clean**, **bends a
rule** (and which), or **lands with a problem** (and what it clashes with).

- **Preview** shows what the option would do without making it, where the helper's Preview shows it today: under
  the option, in the panel, as the small week of each class it touches with the changed lessons outlined. It is
  extended to cover a lesson placed from "Not placed" and an option that lands with a problem (shown with the
  problem, not without the change). **Show on the board** goes to the lesson, as "Show me" does.
- **Apply** makes it. It is then a change like any other: on the board at once, in the Changes list, taken back by
  Undo, seen by a colleague's page within seconds.
- An option that lands with a problem has **Apply anyway** in place of Apply. It asks first, with the problem's
  sentence, as a hand-over to a busy teacher does today ("… Apply anyway?"), and is then kept as the board keeps a
  forced change. It is offered for the kinds of change the board itself can force: a move, a place, an add, a change
  of teacher, a change of room. A swap, a trade and two changes together are never forced (the first and the last
  as today): when one of those lands with a problem the option is listed with its reason and no Apply.
- An option the app would refuse outright (a lesson in a break, a group out of its band's time) is never shown as an
  option. The answer may say why it cannot be done.
- When the timetable changes, by an Apply here, a drag on the board or a colleague, the options already on screen are
  struck through ("The timetable changed. Ask again.") and cannot be applied. The server checks this too: an Apply
  carries the mark of the timetable its option was made for, and is refused in words when the draft has moved on.

**The chat never changes the timetable.** Only Apply does, pressed by a person.

### What can be asked about

The app gains a small set of look-ups. The starter questions use them directly; the AI uses the same ones and no
others. All of them read the draft as it is at that moment and change nothing.

1. **What is here.** The lessons of the place or the lesson pointed at: class or classes, subject, group, teachers,
   room, length, and the warnings open on it.
2. **Where a lesson can go and what it can swap with.** Every place of the cycle, judged as the board judges a drag:
   clean, bends a rule, clashes, cannot. (This exists: it is what colours the strip when a card is picked up.)
3. **Who could teach a lesson.** Every teacher of the setup with: free or busy at the times of all the lessons the
   change would cover, and with what; their department or departments; the subjects they teach on step 5; their
   periods now and after against their allowance; and how close they are to the lesson (already step 5's teacher for
   it, teaches the same subject or another on the same step 3 card, same department, other).
4. **Trades between two teachers.** For the lesson's teacher and another: the classes of the other teacher that the
   two could exchange, each taking the other's. A trade is judged on the timetable it leaves, not one half at a
   time: judged half by half, the first teacher would be "busy" with the class they are about to give away whenever
   the two classes meet at the same time, and most real trades would be refused.
5. **Which rooms a lesson could use**: free and the right kind, free and another kind, in use and by what. (Exists.)
6. **What can fill a period.**
   - On a class's row: that class's lessons waiting in "Not placed"; lessons step 5 asks for and the timetable lacks
     for that class; and that class's lessons elsewhere in the cycle that could move there, each with the gap it
     would leave.
   - On a teacher's row: that teacher's lessons elsewhere that could move there, and lessons waiting or lacking that
     are theirs.
   - On a room's row: lessons at that time with no room, or in a room of the wrong kind, that could use this room.
7. **Who and what is free at a time**: the teachers free then, by department, and the rooms free then, by kind.
8. **Check a change.** One change or two together, judged by the same code that judges every change on the board,
   with what else it disturbs. Every option shown anywhere in the Ask tab has been through this, at the moment it is
   shown and again at Apply.

"A change" is what the board already makes (move, swap, place from Not placed, add a lesson step 5 asks for, change
of teacher, change of room) and one new kind, the **trade**: two teachers exchange two classes. A change of teacher
is for all that class's (or group's) lessons of the subject, as it is everywhere in the app, and so is each half of
a trade; the option says how many lessons. A trade is one change: one line in the Changes list, one Undo, written
down in words like the others ("Adam Lee and Chen Wei traded: Adam Lee now teaches 2C Mathematics, Chen Wei 2A
Mathematics."), and carried into the published timetable's record of changes as the others are.

"Who else could teach it?" lists teachers, each with **Give** (the change of teacher). "Who could I trade this class
with?" lists teachers with the trades look-up 4 finds for each. Both work in stage 1, without typing.

### The AI's part

- The AI reads the typed words and what was pointed at, calls look-ups 1 to 8 as it needs, and answers. It works out
  nothing about clashes itself. To put an option in front of the lead it must hand the change to look-up 8; the
  server words the option, gives it its verdict and its buttons. Text the AI writes can never be an Apply button.
- It may ask a short question back when the request can be read two ways ("All six lessons of 2A Mathematics, or do
  you mean another class?").
- It answers only about this timetable. Asked for anything else, it says what the Ask tab is for.
- Each typed question is answered in one go: the lead sees "Working it out…" and then the whole answer. An answer
  that takes longer than about 45 seconds, or more than 8 rounds of look-ups, is stopped with a sentence saying so.
- A conversation holds at most 20 typed questions; then the tab asks to start a new one. A typed question is at most
  500 characters. The whole server answers at most 60 typed questions an hour; past that the tab says so and the
  starter questions still work.
- **With no AI set up** (a server with no key), the Ask tab still opens and the starter questions work. The typing
  box is replaced by one line: "Typing a question is not set up on this server." The switch is the typed request
  box's own (`typed.enabled()`): where that box shows, this one does. On a local or test server set to the practice
  reader (`TYPED_REQUEST_MODEL=mock`) a scripted stand-in answers, and no AI is called.

### What is sent to the AI, and what never is

Until now the app has sent an AI only the words typed into the request box, never the timetable. This project
changes that, by the lead's decision, within these limits:

- **Sent:** the typed words; what was pointed at; and what the look-ups return for that question: classes, subjects,
  groups, days and periods, room names, department names, teachers' period counts, and the app's own sentences about
  clashes and rules.
- **Teachers are sent as codes** ("T07"), never by name or by their short name. This holds for every part of what
  is sent, including the app's sentences ("T07 is teaching 2C Mathematics then."). On the way back the codes are
  turned into names before anything is shown.
- **Names the lead types** are turned into codes before the words are sent, erring on the side of sending a code:
  a full name, a short name, a title with part of a name ("Mdm Lim"), and a capitalised word that is part of some
  teacher's name and is not also a class, a subject, a room or a day. One that fits several teachers is sent as
  those teachers' codes, and the chat asks which. Now and then an ordinary word that is also somebody's name will
  be sent as a code and the AI will ask what was meant; that is the accepted cost. A name the app cannot match (a
  misspelling, a person not on the setup's list) is sent as typed: the page says so in one line under the box
  ("Teacher names are sent as codes. A name the app does not know is sent as typed.").
- **Never sent:** anything about a student (the look-ups return no student's name or number; a sentence may say "3
  students of group G1"); the school's name; sign-in codes; the committee's rules in words (they are free text and
  may name people); the timetable as a whole (only what the look-ups return for the question asked).
- **Not kept:** as with the typed request box today, the server stores and logs nothing of a conversation: not the
  words, the look-ups or the answer. The conversation lives in the page and is gone on a reload.
- The AI service is the one the typed request box already uses, with the key the school put on its own server.

### Kept as they are

The board, dragging, the Lesson tab's lists, the helper's "Ways to settle this" under a warning, and the typed
request box at the foot of the Warnings tab all stay. The Ask tab does not replace them. One sentence is added to
the board's hint line: a click on a row's name shows that class's, teacher's or room's whole cycle.

## Goals

- From any lesson or any period of any row, the lead gets a list of what can be done there, already checked, in one
  click or one typed sentence.
- "Find me another teacher" can be asked with the lead's own conditions (free then, same department, teaches a
  similar subject, not a named person) and answered with options that can be applied.
- An empty period can be filled from the answer.
- No teacher's name that the app knows leaves the server.

## Not in this project

- The AI making a change by itself, or any change without Apply.
- An option of more than two changes together. (A longer chain is asked for and applied step by step.)
- A change of teacher for one lesson only, or a teacher trade for one period. It stays a change for all that
  class's lessons of the subject.
- Selecting several separate lessons by hand and asking about them together. A band is covered; a hand-picked set
  is not.
- Asking with nothing pointed at. (The typed request box in the Warnings tab still takes "move PE for 2A off
  Friday".)
- A conversation remembered after a reload, or shared between two committee members.
- Making or re-solving the timetable, splitting or joining lessons, changing step 5.
- A new timetable view. Phone layouts.

## What would make this a failure even if it works

- An option on screen that the app's own check did not produce, or an Apply that does something other than what its
  option says.
- A teacher's name, full or short, in anything the app sends the AI: a look-up's result, one of its own sentences,
  or a typed name it knows.
- The timetable changed by the chat without a person pressing Apply.
- An option applied to a timetable that has changed since it was shown.
- The board slower to open, to drag on or to redraw than it is today, at the school's size (32 classes, about 90
  teachers, 73 rooms, 26 periods a day, a two-week cycle, about 1,950 lesson rows).
- The AI being down, slow or over its limit stopping the board, the starter questions or any change made by hand.
- Anything of a conversation written to the server's disk or its logs.
- A test, a probe or a review that calls a real AI. Tests use a scripted stand-in.
- Anyone's real name, or the school's full name, in the code, the tests or these documents.

## Approaches

Three ways of answering a typed question were considered.

1. **The AI asks the app (chosen).** The AI is given the look-ups above and nothing else. It decides what to look
   up and how to put the answer; every clash and every rule is judged by the code that already judges the board; an
   option exists only when that code has produced it. It handles the lead's own conditions and follow-up questions,
   sends only what a question needs, and cannot show a change the app has not checked. It costs a wait of some
   seconds and a few cents a question (an estimate, at the model the typed box uses today; to be measured when the
   lead first tries it, since no test may call the AI).
2. **The AI is given the timetable and answers by itself.** Simple to build. But it would be working out clashes
   across some 1,950 rows by reading, and would be wrong some of the time with nothing to catch it; it sends the
   whole timetable with every question; and it costs many times more.
3. **No conversation: the typed box of today, made larger.** The words are read once into a fixed form (move,
   teacher, room) and the app answers. It sends no timetable at all. But it cannot take a condition it has no field
   for ("or teaching similar subjects"), cannot be answered back to, and the lead asked for a chat. Its strength is
   kept as the starter questions, which need no AI.

On where the conversation runs: on the school's own server, one question at a time, as the typed request box does.
The AI company also offers to host such an assistant itself; that keeps each conversation's history on its side
until deleted, which this design's "not kept" rule excludes.

The committee lead chose: the app's own ready answers first, then the chat on top, with teachers sent as codes. The
rest of the how was left to the writer.

## Suggested order of building

Two stages, one plan and one pull request each, each usable on its own.

1. **Point and ask, without AI.** Pointing at a lesson, a band or an empty period (right-click, the Ask button, the
   click on an empty period); the Ask tab; look-ups 1 to 8; the trade as a kind of change; the starter questions
   answered by the app; options with Preview, Apply and "Apply anyway?"; options struck through when the timetable
   changes; the hint about a row's name.
2. **The chat.** The typing box; the AI over the look-ups; teachers as codes in both directions; questions back;
   the limits; the line shown where no AI is set up.

## Decided by the committee lead

1. No new timetable view: the whole cycle behind a row's name is the view.
2. A lesson, an empty period or a period can be pointed at, by right-click or a pop-up, and asked about.
3. The asking is a typed chat, with conditions in the lead's own words: a teacher to trade a class with who is free,
   in the same department or teaching similar subjects; filling an empty slot; swapping with another lesson.
4. The AI may be sent the timetable around what was pointed at, with teachers' names as codes.
5. The app's own ready answers come first, the chat on top.

## Decided by the writer of this document (to be checked on reading)

- The Ask tab sits in the panel beside the board, not in a box floating over it.
- The chat never applies anything.
- "A group of lessons on a period" is a band with its groups. Several separate lessons picked by hand, and a period
  where a row has two cards at once, are asked about one card at a time.
- "Trade this class" covers all that class's lessons of the subject, both ways. It is a new kind of change, one
  line and one Undo, judged on the timetable it leaves.
- An option that lands with a problem can be applied after "Apply anyway?", for the kinds the board can force; a
  swap, a trade and two changes together cannot.
- Preview is in the panel, as the helper's is, not drawn on the board.
- Typed names are turned into codes generously, at the cost of an ordinary word sometimes going as a code.
- What fills an empty period on a class's, a teacher's and a room's row, as listed in look-up 6.
- Something must be pointed at before a question can be typed.
- A new thing pointed at starts a new conversation. Nothing of a conversation survives a reload.
- What is sent and what is never sent, as listed; in particular that rules in words are not sent, and that a typed
  word the app cannot match to a teacher goes as typed.
- The limits: 500 characters, 20 questions a conversation, 60 typed questions an hour for the server, 45 seconds
  and 8 rounds of look-ups an answer.
- The starter questions are answered by the app, not the AI, also once the chat is built.
- The helper under a warning and the typed request box in the Warnings tab stay.
- The hint line names the click on a row's name.

## Left to the builder

- The names, shapes and routes of the look-ups, and which existing functions they are built on (`fixes.slots`,
  `fixes.choices`, `fixes.teacher_options`, `fixes.room_options`, `fixes.add_slots`, `fixes.short`,
  `helper.chain` and the wording in `helper.py` are the starting points), as long as an option's verdict and
  wording come from the same code as the board's and the helper's.
- How many options an answer shows, and their order, in the spirit of the helper's ranking (fewer changes, fewer
  lessons moved, clean before bending, a teacher's load against the allowance, the same day first); how many
  teachers a "who could teach" answer lists before "and 12 more".
- Which of the other teacher's classes look-up 4 tries, as long as it is bounded and says when it stopped short.
- Whether a lesson that would cover a period without starting at it counts as filling it.
- How a conversation is carried from one question to the next, as long as the server keeps nothing on disk or in
  its logs, a reload starts clean, and it works however many server processes run. (A simple way: each typed
  question starts a fresh exchange with the AI, given the earlier questions and answers of that conversation as
  text.)
- How teachers are given codes and how every outgoing string is passed through them, as long as the same teacher
  keeps one code through a conversation, a short name is replaced only as a whole word, and tests prove two things:
  over every look-up, no teacher's full or short name is in what would be sent; and for every teacher of the setup,
  typing their full name, their short name, a title with each word of their name, and each word of their name
  capitalised leaves no word of the name in what would be sent.
- How the trade is stored, judged, worded and undone, as long as a draft from before still opens, the agent's file
  is kept as it came, and the judging is `fixes.judge`'s own before-and-after comparison on the end state.
- The model and its settings: by default the typed request box's own (`typed.model()`), set by the same variables;
  what the AI is told in its fixed instructions, in the manner of `typed.SYSTEM` (text in a look-up's result or in
  the typed words is data, never an instruction).
- The scripted stand-in for the AI in tests and on local servers.
- The look of the tab, the starter buttons, an option and a struck-through option, within the page's present
  style; the words of every new sentence, in the plain style of the rest of the page.
- How each stage is tested, as long as it includes a timetable shaped like the school's, a run on the real files
  (counts and timings only: how long each look-up takes, and that the count of teachers' names in what would be
  sent is zero), and browser checks of right-click, Apply and Undo made with real pointer actions.

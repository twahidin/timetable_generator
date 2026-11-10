# The return trip: upload, check, fix and publish the timetable an outside agent made

Date: 10 November 2026. Status: design, awaiting the committee's approval of this document. Project 2 of 4.

Project 1 (`2026-11-09-setup-wizard-design.md`, complete and live) made the app the place where the configuration is
built and downloaded. The timetable is made outside, by an AI agent working from the configuration workbook and the
skill, and comes back as the timetable database (`.sqlite`) the skill's `ttgen export` writes or as a workbook with a
Lessons sheet. This document covers what happens next: the file comes back, the app checks it against what the school
asked for, the committee lead settles every difference, fixes what needs fixing inside the app, and publishes.

## Why

The last outside timetable came back with 47 differences from the deployment, and someone found them by hand, in a
spreadsheet, over hours. The app already has everything needed to find them in seconds: the configuration the agent
worked from, the clash check that runs on every upload, the standard rules, the typed rules with the agent's rule
report, and the second choices it gave way on. What it lacks is a place to look at each difference, decide which side
is right, and fix the timetable by hand without leaving the app.

Fixing by hand matters because the alternative, sending the whole timetable back for another run, is slow and makes
a new timetable with new surprises. Today the committee lead swaps lessons or teachers in a manual system that at
least says whether the result clashes. The app should do that better: show at a glance which swaps are possible,
check every move before it lands, and help find the moves when the lead does not know where to start.

## Who uses it

- **The committee lead** (one person, with the committee code): uploads, decides, fixes, publishes. Everything on step
  8 is theirs alone, as today.
- **Department heads** do nothing new in this project. They keep steps 4 and 5. Whether they see a draft before it is
  published is project 3's question (who sees what).
- **The outside agent** is not a user of the app, but the rule checker this project adds goes into the skill's copy of
  `ttgen` too, so an agent that can run code can check its own work before handing it back.

## Goals

- Every difference between the returned timetable and the deployment on step 5 is found by the app and shown as a
  warning: wrong teacher, wrong class or group, wrong number of periods, a lesson missing, a lesson that nobody
  asked for.
- Every broken rule is found the same way: clashes, the standard rules from step 6, the typed rules through the
  agent's rule report, and the second choices it used.
- Each warning can be settled one of three ways: fix the timetable, update step 5 to match the timetable, or leave it.
- The lead can fix a lesson inside the app, on the class's week grid, and see before the move lands whether it is
  clean, bends only a Prefer, or clashes.
- A helper beside the grid lists the moves that are possible for the lesson in hand, and for a warning offers two or
  three ways to settle it, every one already checked. The lead can also type what they want in their own words.
- Publishing works as today, with the warnings the lead chose to leave and the fixes they made shown alongside.

## Non-goals

- Making or re-solving a timetable in the app. The helper searches for swaps among the lessons that exist; it never
  places a timetable from scratch. (Project 1's decision stands: generation is outside.)
- Splitting a lesson into shorter ones or joining lessons. A lesson moves as the block it is.
- Heads fixing their own department's differences. The lead decided: committee lead only.
- Showing a draft to heads, teachers or students before it is published (project 3).
- Relief (project 4).

## Anti-goals (it has failed if)

- A fix lands that quietly breaks something elsewhere: a clash in another class, a Must rule, a block lesson moved
  for one class but not the others. Every move is checked by the same checks that run on the whole timetable, before
  it is applied, and the result is shown before the lead confirms.
- A list of 47 warnings that nobody reads. Warnings are grouped (by class, by teacher, by kind), each one says in a
  sentence what the timetable says and what step 5 says, and the count of what is still open is always visible.
- The check is slow. Upload to warning list in seconds for a school of 1,500 lessons; the grid's colouring for a
  selected lesson in under two seconds. (Designer's targets.)
- The published timetable no longer matches step 5 and nobody can tell. Publishing records which setup version the
  timetable was compared against, what was left open and what was changed.
- The agent's file is lost. The uploaded file is kept as it came; the fixes are kept as a list of moves on top of
  it, so the agent's version and the published version can always be told apart.
- Real teacher or student data lands in the public repository. Samples and tests use made-up names.

## The return trip, start to end

Step 8 (Publish) grows from one card into the sequence below. Each part is a card on the step; the lead can go back
and forth between them.

### 1. Upload

As today: the timetable database on its own, or the Lessons workbook with the configuration workbook beside it. The
app reads the configuration id the file carries and says whether it is the configuration the school has now (`v14`),
an older one, an unsaved one (`v14+`), or unknown. The upload becomes the **draft**: it is kept on the server (on the
volume, beside the published timetable), and everything that follows works on the draft. Nothing is visible to
anyone else until Publish.

A new upload replaces the draft. If the draft holds fixes that were never published, the app says so and asks first.

### 2. Check

The app runs four checks on the draft and lists what it finds as **warnings**. A warning is never a wall: the lead can
publish with warnings open.

**Clashes** (as today, `check_model`): a teacher in two places, a room over capacity, a class in two lessons, a student
in two lessons, a lesson in a break or outside the day, a lesson in a class's recess, periods timetabled against
periods planned.

**Which setup.** Every check, every move and the publish run against the school's **current** setup, steps 1 to 6 as
they are at that moment, read fresh each time. The setup inside the uploaded file is used only for its configuration
id. So a change made on step 5 (by the lead settling a warning, or by a head) is seen by the next check, and the
published timetable carries the setup it was checked against. *(Designer's call: it is the only way "update step 5"
can close a warning, and it keeps one truth.)*

**The deployment** (new): every lesson on the timetable is matched to a row of the department map on step 5 by class
or group and subject. For each match the teacher (or teachers) and the class or group come from step 5, and the
periods a week and the venue kind from step 3 for that subject and level. All four must agree. A row on step 5 with
no lessons on the timetable is **missing**; a lesson on the timetable with no row on step 5 is **extra**. If the
configuration moved on after the download (the file's configuration id is older than the school's), the list says so
at the top, because then the timetable may be right and step 5 may have changed under it.

**The rules** (new): the standard rules from step 6 are checked against the finished timetable, one checker per rule
type on the list in `ttgen/spec.py` (`RULE_TYPES`): Not available, Keep free together, Fixed at, Not in periods, Only
in periods, Finish by, Only these subjects, Only in venues, Max periods a day, Max periods in a row, At least one
recess a day, At most N at once, Same time across classes, Not on the same day as, Once a day per group, Avoid
after-school slots. A broken Must is a warning; a Prefer not kept is a warning marked as such. The checks use the
setup after the second choices the agent gave way on, as the clash check already does. The typed rules (In words) are
checked through the agent's rule report: a Must reported Not met or Partly is a warning; a typed rule with no line in
the report is a warning; a report line that names a rule the setup does not have is a warning. **The choices used**
stay as built in stage 6b (`check_used`).

Each warning carries: its kind (clash, deployment, rule, choice), a sentence, where it is on the grid (class, day,
period) when it has a place, and what the two sides say when it is a difference. The list is grouped by kind, then by
class or teacher, with the open count at the top and a filter for what is open, fixed, left.

*(Designer's calls in this section: the rule checkers live in `ttgen`, both copies, as `ttgen check-timetable
<file>`, so the agent can run them before handing back and `SKILL.md` tells it to. Which checks are feasible for
which rule types is for the builder to find out; a rule type the checker cannot judge is listed as "not checked",
never silently passed.)*

### 3. Decide

Every warning that is a difference has three answers, as buttons on the warning:

- **Step 5 is right, fix the timetable.** Opens the fix-up screen (below) on that lesson, with the helper already
  showing ways to settle it. The warning stays open until the timetable agrees with step 5.
- **The timetable is right, update step 5.** The app changes the department map to match: the teacher, or the class
  or group. This is a change to the setup like any other on step 5 (it saves, merges, takes its place in the change
  history and can be undone), so the configuration id moves on and the published timetable is marked as checked
  against the newer version. The warning closes. A periods-a-week or venue-kind difference is set on step 3 for the
  whole level, not for one class, so that warning offers only the other two answers and links to step 3 instead.
  *(Designer's call: the app never changes a level-wide figure behind one class's warning.)*
- **Leave it.** The warning is marked left and counted as open, so it is in the published list.

A clash or a broken rule has only the first and the third answers. The decisions are kept with the draft; re-running
the check after a fix does not forget them, and a warning that no longer appears is dropped.

*(Designer's call: the app does not guess which side is right. It states both sides; the lead chooses. The default
button order puts "fix the timetable" first because the heads approved step 5.)*

### 4. Fix

The lead chose the view with both the grid and the helper on one screen.

**The grid.** The class's week on the left: days across, periods down, one grid per week where the school has two. A
lesson shows its subject, group and teacher. Clicking a lesson selects it, and every slot on the grid colours itself:
green where swapping with that slot (or moving into it, if the slot is empty for the class) is clean; amber where it
breaks only a Prefer rule; red where it clashes or breaks a Must; grey where the lesson cannot go at all (a break, the
wrong length). Hovering or tapping a coloured slot says why in a sentence. Clicking a green or amber slot makes the
move; the two lessons swap, or the one lesson moves. The grid can be switched to a teacher's week, where the same
colouring works for that teacher's lessons.

**Moves the app knows how to make.** Swap two lessons of the same class with the same length; move a lesson into an
empty slot of its class; change a lesson's teacher to another teacher on step 5 who is free in all of its periods;
change a lesson's room; **add** a lesson into empty slots of its class, for a row of step 5 that is missing or short of
periods (the lesson's subject, group, teacher and venue kind come from step 5 and step 3, the lead picks the slots and
the room, and the colouring shows where it can go); **delete** a lesson that step 5 does not ask for or that puts a
class over its planned periods. A swap between two lessons of different classes is the same as two moves, and the
second class's grid is shown before the lead confirms. *(The lead decided: add and delete are in. Designer's calls:
same length only for swaps; a lesson moves whole; chains of more than two moves are the helper's business, not the
grid's.)*

**Block lessons.** A block lesson (an option band: one lesson id across several classes, groups and teachers) is one
lesson on every grid it touches. It moves as one, for all its classes at once, so a block slot is green only when
the move is clean for every class in the block, and a block can only swap with another block of the same classes and
length or move into a slot that is empty for all of them. A single class's lesson never swaps into a block's slot.
*(Designer's call.)*

**What clean means.** After the move, the clash check finds nothing new, every standard Must rule still holds, the
lesson is still inside its class's lesson time, and the period counts are unchanged, except that an add or a delete
brings a count towards what step 3 plans and never past it. Amber means the only thing that
gives is a Prefer rule or a teacher's allowance on step 4, and the sentence names it and says by how much. A move is
checked before it is offered and again when it is applied, by the same code that checks the whole timetable.

**Typed rules and moves.** The app cannot judge a rule in words, so the colouring does not try. Instead, when a move
touches a lesson that a typed rule is about (its subject, class, level, teacher or room is in the rule's scope), that
rule's report line is marked **check again** and becomes an open warning until the lead marks it still met or leaves
it. The published record then says which typed rules were re-checked by the lead and which were left. *(Designer's
call.)*

**Every move is recorded.** The draft is the uploaded file plus a list of moves. Each move can be undone, newest first.
The list appears on the Publish card and in the published timetable's Read me sheet, so what changed since the
agent's version is always written down.

**The helper.** On the right. When the lead arrives from a warning, it opens with two or three ways to settle that
warning, each a short sentence saying what moves and what it disturbs ("Change the teacher only; Mdm Lee is free in
all five periods, nothing else moves"; "Change the teacher and swap Tue P3–P4 with Art, Thu P3–P4; two lessons
move"), with an Apply button. When the lead selects a lesson on the grid, it lists the same moves the colouring shows,
in words. When nothing settles the warning cleanly, it says so and shows the least bad moves with what each breaks.
Suggestions are ranked: fewest lessons moved first, then nothing amber, then teacher loads kept level. A suggestion
may be up to two moves. *(Designer's calls.)*

**Typing a request.** Above the helper's list is a box where the lead can type what they want in their own words:
"move PE off Friday", "give 2A maths to Mdm Lee and keep the doubles together". The app turns the words into a
structured ask (which lessons, what kind of change, what to keep) with a language model, then runs the same search
and the same checks, and shows the suggestions the same way. The language model never places a lesson; it only reads
the request. The box appears only when `ANTHROPIC_API_KEY` is set in Railway, which the committee does itself; without
the key the helper works fully from the app's own search. *(Designer's call, agreed in the brainstorm: both ways of
asking; the typed one optional.)*

### 5. Publish

As today: Publish replaces the published timetable for everyone, after the same confirmation. The published record
adds: the setup version the draft was last compared against, the warnings left open (with the lead's decisions), and
the list of moves made in the app. The Publish card shows the open count before the button ("3 warnings left; you
can still publish"). The draft stays after publishing, so a later fix starts from what is published.

The draft can also be downloaded at any time as the timetable database, with the moves applied, for keeping or for
giving back to the agent for another round. *(Designer's call.)*

## Working together

Nothing changes for heads. Step 8 stays committee-only on the server, as the access table in project 1 says. The
draft, its decisions and its moves are one shared thing on the server, like the setup; two committee browsers see the
same draft.

## Constraints on the build

- Flask and the one vanilla JS file as today, with the grid and helper in their own file like `static/choices.js`.
  No framework, no bundler. The grid is HTML.
- The draft, its decisions and its moves are files on the volume beside the published timetable. No database server.
  The live service has no volume yet: until it has one, the app shows the same warning for the draft as it does today
  for the published timetable (lost on the next deploy). Adding the volume is the committee's Railway task, not a pull
  request, and the design asks for it before stage 1 goes live. *(Open point for the committee.)*
- The rule checkers go into `ttgen` in both copies (the app's and the skill's), with `SKILL.md`'s version line moving
  on, as stage 6 did. The editor and the helper are the app's only.
- The language model is called server-side with the key from Railway, never from the browser, and only for the typed
  request. If the call fails, the box says so and the helper carries on without it.
- The repository is public: no secrets, no real names, never commit `.claude/launch.json` or `data/`.
- Light only, laptop and tablet in landscape, as before.
- Tests: the project has suites now (`tests/`). The checkers and the move engine get tests against the sample schools;
  the screens are checked by hand in the browser preview as before.

## Suggested order of building

Each is a pull request the committee can try on its own.

1. **Check and decide**: the draft on the server, the deployment comparison, the standard-rule checkers in `ttgen`
   (both copies, `check-timetable`), the typed-rule check through the rule report, the grouped warning list, the three
   decisions including "update step 5", publishing with warnings and the compared-against version.
2. **The grid**: the class and teacher week, the colouring for a selected lesson, swaps and moves by hand, teacher and
   room changes, adding and deleting a lesson, the move list with undo, the draft download, moves shown on Publish.
3. **The helper**: suggestions for a warning and for a selected lesson, ranked and checked, Apply.
4. **The typed request**: the box, the language model turning words into an ask, the key check.

## Left to the builder

- How the draft is stored (the file plus a move log is the shape; the format is theirs).
- How the checks are made fast enough for the colouring (an incremental check per candidate slot rather than a full
  re-check is the obvious route).
- Which rule types the checker can judge from a finished timetable and how "not checked" is shown.
- How the helper searches (trying every legal single move and every pair that touches the lesson is enough; nothing
  cleverer is asked for).
- The exact prompt and the Claude model for reading a typed request, and the shape of the structured ask.
- Exact wording and layout within the screens described; the mockup chosen in the brainstorm is
  `.superpowers/brainstorm/*/content/fixup-editor.html`, option C, as a sketch, not a design.

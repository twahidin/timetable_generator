# Combined venues: rooms that are used together as one, or apart

Date: 2026-11-19. Branch `combined-venues` (from main 272dbc7).

## Why

Some rooms come in sets. D&T Lab 1 and D&T Lab 2 each seat 20. A lower secondary class is a whole class of about 40
with two or three teachers, so it needs both labs at the same time. Upper secondary D&T groups are small, so each
takes one lab and two groups can run side by side. The Food Labs and the two D&T Design Rooms work the same way.

Today a room is one thing. The school has tried both ways the setup allows, and both are wrong:

- **Two separate rooms.** The timetable gave two lower secondary classes one lab each at the same time.
- **One big room** ("D&T Lab 1&2", the 18 November workaround, with an "At most 2 at once" rule and a rule in words).
  The labs can no longer be told apart, so an upper secondary group has no lab of its own on the timetable, and the
  rule in words is not checked by anything.

The committee lead wants to say once, on step 1, that the two labs can be used together as one venue. The timetable
then gives a big class both, and never puts anyone else in either lab at that time; small groups still get one lab
each.

## Who uses it

- **The timetable committee** on step 1 (Venues), in the rules, and on steps 8 and 9.
- **The outside agent** (Claude Cowork with the skill) that makes the timetable from the downloaded workbook.
- **Everyone who reads the published timetable**, on class, teacher and room pages.

## What it is

A **combined venue** is a venue on step 1 that is made of two or more rooms that are also on step 1. It has its own
name, kind and seats. A lesson held in it uses every one of its rooms for the whole lesson.

The words on the page are "combined venue" and "made of". Its rooms are called "its rooms".

### The one rule everything follows

**A lesson in a combined venue is in each of its rooms.** Everywhere the app or the solver asks "is this room in use
then?" or "how many lessons are in this room then?", a lesson in the combined venue counts once for each of its
rooms. And the combined venue is free only when every one of its rooms is free.

So, with D&T Lab 1&2 made of D&T Lab 1 and D&T Lab 2:

| At the same time | Allowed? |
|---|---|
| a class in D&T Lab 1&2, nothing in either lab | yes |
| a group in D&T Lab 1, another group in D&T Lab 2 | yes |
| a class in D&T Lab 1&2 and a group in D&T Lab 1 (or Lab 2) | no: "Room used twice" |
| two classes in D&T Lab 1&2 | no: "Room used twice" |

Nobody else may be in either lab while a class has the combined venue. The committee lead chose this over the
18 November rule ("one Sec 1 class and one Sec 3/4 group alongside").

### Step 1 (Venues)

**Making one, on the Blocks view.** Rooms already have tick boxes, and a bar appears when any are ticked (it moves
rooms to a block and floor). The bar gains a **Combine** button. It is live when two or more rooms are ticked and
all of them are ordinary rooms of one kind, none is already in a combined venue, and none takes several groups at
once; otherwise it is greyed with the reason beside it. Pressing it adds a combined venue and opens its card:

```
Floor 2   [D&T Design Rm 1]  [D&T Design Rm 2]  [D&T Lab 1]  [D&T Lab 2]
          [D&T Lab 1&2 · d&t studio · 40 seats · made of D&T Lab 1 + D&T Lab 2]
```

- **Name:** suggested from its rooms. When the names differ only in a final number or letter, the shared part and
  the endings joined with "&" ("D&T Lab 1" + "D&T Lab 2" gives "D&T Lab 1&2"). Otherwise the names joined with " + ".
  The committee can change it. It must not equal another venue's name.
- **Kind:** the kind of its rooms. All its rooms are of one kind and the combined venue is of that kind: it is
  shown, not picked. (Every room count in the solver and the checks is per kind; one kind keeps them exact.)
- **Seats:** the sum of its rooms' seats. Can be changed (a pair of 20-seat labs may be said to seat 44). If any
  room has no seats, the box starts empty and Things to fix asks for the seats: seats decide who gets the venue.
- **Block and floor:** those of its first room. The card sits on that floor, after the single rooms, and looks
  different enough to tell apart (the "made of" line is always shown on the card).
- **Made of:** shown on the card and changeable in the open card (add or take off rooms; at least two).
- "For", Note, Equipment and Configuration work as on any room and are the combined venue's own. A room's "For"
  does not carry over to the combined venue.

**The Table view** gains a "Made of" column: empty for an ordinary room, the rooms' names for a combined venue.

**Taking one apart.** Deleting the combined venue leaves its rooms as they are. One save, one Undo, as everything
else on the page.

**Keeping it whole.**
- Renaming a room renames it inside the combined venue it belongs to, in the same save. (Nothing else follows a
  room's rename today: a rule or a home room naming the old name is flagged, as now. That stays as it is.)
- Deleting a room takes it off the combined venue. A combined venue left with fewer than two rooms stays on the
  page and is flagged in Things to fix.

**Things to fix (step 1), all critical unless said:**
- a combined venue with fewer than two rooms, or naming a room that is not on step 1;
- a room that is in more than one combined venue (see Limits);
- a combined venue made of another combined venue;
- a combined venue whose rooms are not all of one kind (after a room's kind is changed);
- a room of a combined venue, or the combined venue itself, with an "At most N at once" rule above 1: a combined
  venue and its rooms take one group at a time;
- warning only: a combined venue with no seats;
- warning only: seats of the combined venue above the sum of its rooms' seats by more than 10%, in case of a slip;
- warning only: a lesson row whose room kind has a combined venue and whose group size is not known (no Students
  count, no Students on the row, no class size): without a size it may be given any room of the kind.

### Names with a stray space

The picture that started this showed "D&T Lab 1: not on step 1 (Venues)" under a rule, though the room was there.
Room names are stored exactly as typed, the rule's list is trimmed, and the two are compared exactly, so a room typed
with a space at the end never matches.

- A room name typed on step 1 is trimmed (and runs of spaces made one) when it is stored.
- Every place that matches a rule's venue names to rooms compares names trimmed, so a setup already saved with such
  a name stops showing the message and the rule keeps its room: on the page the check, the kind check under it and
  the picker (`static/app.js`, near `namesList`, the "Only in venues" branch of the rule check and the "rooms"
  picker); in Python where `Problem` builds the venue rules (it drops an unmatched room from the rule today),
  `solver.rule_problems`, and `verify`'s venue check. The workbook reader already trims, so the agent's path is
  not affected.

### Who gets the combined venue

**Seats decide, as for every room today.** A group may use the rooms of its subject's room kind that are kept for it
(or for anyone) and that seat it. A class of 40 does not fit a 20-seat lab, so the only d&t studio that seats it is
the combined venue. A group of 13 fits a single lab, and rooms are handed out smallest first, so it gets one lab.
No rule is needed for the usual case. On the school's figures: the Sec 1 D&T and Sec 2 FCE rows are whole classes of
35 to 41; the upper secondary rows are small groups.

**A group that fits nothing.** Today, when no room of the kind seats a group, every room of the kind is allowed
and a note says so ("Bigger than every … they may use"). In a kind that has a combined venue that would hand a
class of 41 a single 20-seat lab when the pair is said to seat 40. So, only for a kind that has a combined venue:
a group that no venue seats is limited to the venue or venues of that kind with the most seats, with the same note.
Kinds with no combined venue are untouched. A group whose size is not known may use any room of the kind, as today
(Things to fix warns, above).

**A rule can force it.** "Only in venues" (step 6, More rules) lists venues; a combined venue can be picked like any
room. "Sec 1 · Design & Technology · Only in venues · D&T Lab 1&2" keeps Sec 1 to the pair whatever the sizes. The
picker shows combined venues under their kind with their rooms in brackets.

**"Not available" on a room** makes every combined venue it belongs to not available then. "Not available" on the
combined venue leaves its rooms free.

### The workbook

Sheet `1 Venues` gains one column at the end: **Made of (rooms used together)**. Empty for an ordinary room. For a
combined venue: its rooms' names, separated by commas. The sheet's help line says: "Made of: for a venue that is
several rooms used together as one (a class too big for one lab), the rooms, separated by commas. A lesson there
takes every one of them."

- The reader finds the column by its header (starts with "Made of"). A workbook without it reads as today.
- In the setup the venue row carries `made_of`: a list of room names, absent or empty for an ordinary room.
- The school's 19 November workbook has "D&T Lab 1&2" and "FCE Lab 1&2" as ordinary rooms. It keeps reading that
  way. Nothing is converted without the committee: they add the single labs and fill in Made of (or tick and
  Combine on step 1).

### The solver and the skill (the outside agent)

The agent solves with the skill's copy of `ttgen` (`skill/school-timetable-generator/scripts/ttgen/`, kept equal to
`ttgen/`). The solver must follow the one rule:

- **`Problem`** knows each combined venue's rooms (`parts`), its own seats, kind and "For".
- **The room limits in the model.** Today: for every set of rooms some group is limited to (and for all rooms of
  the kind), a cumulative limit over the groups limited to it, with capacity the number of rooms. With combined
  venues, in a kind that has one:
  - each group keeps its own set of allowed venues E, and a weight: 1 if E holds any ordinary room, else the
    fewest rooms of any combined venue in E;
  - the "single rooms under" a set of venues are its ordinary rooms and the rooms of its combined venues;
  - a limit is built for the single rooms under each group's E, for the rooms of each combined venue, and for all
    single rooms of the kind. Each limit covers every group whose single rooms under E lie inside it, with
    capacity the number of single rooms in it. A combined venue never adds capacity.
  With D&T Lab 1&2 the only studio that seats 40: a Sec 1 class weighs 2 of the 2 labs and a small group 1, so one
  class, or two small groups, never a class with a group. The table under "The one rule" must hold in the solver
  for three setups: the kind has only the two labs and the pair; the kind has a third lab as well; a group is
  kept to one lab of the pair by an "Only in venues" rule. Where the limits are still looser than the truth,
  `assign_rooms` gives a room marked TBC and the check reports it, as today for any room shortage.
- **`assign_rooms`** (handing rooms out after solving): a combined venue is free when all its rooms are; taking it
  takes them all; taking one of its rooms makes it not free. Smallest that seats the group first, as today.
- **The staged solve** (`staged.py`) holds a room for the other levels' lessons by adding "Not available" on
  that venue. A lesson held in a combined venue must hold each of its rooms (since "Not available" on the combined
  venue alone leaves its rooms free); a lesson held in a room makes its combined venue not available, by the rule
  above.
- **Rain rooms** (a home room kept free while its class is at PE, when the setting is on): a home room that is in a
  combined venue, or is one, follows the one rule in the model, in `assign_rooms` and in the checks.
- **Room rules checked after solving** (`report.compromises`, "Not available" for a Room): a lesson in a combined
  venue counts as being in each of its rooms.
- **`report.check`**: "Room over capacity" counts a lesson in a combined venue against each of its rooms.
- **`checks.py`**: both sums that count rooms per kind (the "enough rooms" sum over the cycle, and the band sum
  of groups needing a kind at once) count single rooms and weigh groups as the model does, so a combined venue is
  never an extra room. They must not raise a false alarm; being a little loose is acceptable.

`SKILL.md`: the sheet table and the paragraph "A room holds one class at a time" say what Made of means, and
**Building it without the scripts** gains the modelling above. The skill version goes up one (2026-11.9), with the
workbook README naming it, as for every skill change.

### Step 8 (Upload and edit) and the checks on an uploaded timetable

The timetable the agent returns names one room per lesson, as today. "D&T Lab 1&2" is a room on the setup, so it
matches.

- **The timetable's model** (`ttgen/export.py`) carries each combined venue's rooms, from the setup; so do the
  board's payload (`draft.py`) and the published page's data (`html_data`), which have no such thing today.
- **"Room used twice"** (`Room over capacity` in `export.py`'s check): counted per single room. The message names
  the single room and, where a combined venue is involved, says so: "Room over capacity: D&T Lab 1 on Mon … (in use
  as part of D&T Lab 1&2)."
- **Moving a lesson or changing its room.** A move into D&T Lab 1 while a lesson is in D&T Lab 1&2, and the other
  way round, is treated exactly as a move into a room in use is today: the page says so and offers "Use it anyway?";
  forced, it stands as a critical "Room used twice" that stops publishing. The sentence names the venue the change
  asks for ("D&T Lab 1&2 is in use then."), because the page offers forcing only when the sentence names that
  venue (`static/board.js`), and adds which lesson holds which room. The places that decide "in use": `Busy`
  (`_why`, and the rain-room tests beside it), `fixes.marks`, the "holding" list in `fixes.choices`, and the
  page's own test `bdBusyFor` in `static/app.js`.
- **The helper** (`helper.py`) and the room lists in the lesson panel: a room is offered as free only when it is
  free by the one rule.
- **A class in half of its venue.** Step 8 has no seat check today, and this project does not add a general one.
  It adds one warning (not critical): a lesson in a room of a combined venue whose group does not fit that room but
  fits the combined venue. "1A1 Design & Technology (40 students) is in D&T Lab 1 (20 seats); D&T Lab 1&2 seats
  it." This is the mistake the feature exists to stop, so a returned or hand-edited timetable must show it.
- **The board, rows by room:** a lesson's card sits in the row of the venue it names. A lesson in D&T Lab 1&2 is in
  that row, not in the rows of D&T Lab 1 and D&T Lab 2. Dropping a card on a busy room is refused as above.
- **`verify.py`:** "Only in venues" and the room-kind check read the combined venue as a venue with its own name
  and kind. A rule for a Room ("Not available") is tested by the one rule: a lesson in D&T Lab 1&2 while D&T Lab 1
  is not available breaks it.

### Step 9 and the published timetable

- Class, teacher and student timetables show the room the lesson names: "D&T Lab 1&2".
- **Room pages:** the combined venue has its own page with its lessons. The page of each of its rooms shows those
  lessons too, marked as "with D&T Lab 2, as D&T Lab 1&2", so a person looking up D&T Lab 1 sees every time it is
  taken. The "periods used" figures of a room count them. A room used only as part of a combined venue gets a page
  (today a room has a page only when a lesson names it).
- Room pages are drawn in two places, and both change: `room_view` in `ttgen/export.py` (the Excel workbook and
  the PDFs) and `roomView` in `ttgen/timetable_page.html` (the HTML page and the published site).
- **"Who's free"** on the published page lists a room as free only when it is free by the one rule.
- **The database** (`ttgen/database.py`): one new table, `room_parts (venue, room)`, a row per room of each
  combined venue. The existing tables and the three views keep their columns and their rows, so nothing that reads
  the file today changes. `SKILL.md`'s line on the database names the new table.

## Goals

- The committee says once which rooms pair up, on step 1.
- A timetable made with the skill never puts a second group in a room that a combined venue is using.
- A returned timetable that does so is caught on step 8 as "Room used twice". Moving a lesson by hand into such a
  place is met as any busy room is today: refused with the reason, forced only on the committee's say, and then a
  critical mistake that stops publishing.
- Single rooms keep working exactly as today, including on a setup with no combined venue.

## Not in this project

- Sharing: a second group "alongside" a class in a combined venue. A combined venue takes one group.
- A combined venue of rooms of different kinds.
- A general "room too small" check on step 8 (only the one warning above).
- Making rules and home rooms follow a room's rename.
- A lesson taking any two rooms picked at solve time. The sets are fixed on step 1.
- Converting the old "D&T Lab 1&2" rooms automatically.
- Checking rules in words.

## Limits (to say plainly on the page and in the skill)

- A room belongs to at most one combined venue. (A hall in thirds that combines as A+B and B+C is not covered.)
- A combined venue is not made of combined venues.
- A room that takes several groups at once (an "At most N at once" rule above 1) cannot be part of one.

## What would make this a failure even if it works

- A setup with no combined venue behaves differently in any way, or solves more slowly.
- The step 8 checks and the solver disagree about what "in use" means, so the agent's timetable arrives with
  mistakes the solver thought were fine, or the other way round.
- A combined venue counted as an extra room anywhere (the room sums, the model's limits), so that too many lessons
  are allowed at once.
- Renaming or deleting a lab quietly breaks the combined venue with nothing in Things to fix.

## Approaches

1. **A named venue made of rooms (chosen by the committee lead).** The pair is its own venue with a "made of" list;
   a lesson still names one room; every place that counts room use counts the lesson against each of its rooms.
   Costs: every place that counts room use must learn the rule (the reviewer of this document found about
   fifteen, listed in the sections above; the builder should search for more). Gains: the timetable file keeps its shape, step 1 shows the pairs,
   the school's existing name and rules carry over.
2. **A lesson that takes two rooms.** No new venue; the lesson's room reads "D&T Lab 1, D&T Lab 2". Flexible, but it
   changes the timetable file and every screen that shows a room, step 1 shows nothing about pairs, and the agent
   could pair the wrong rooms.
3. **One big room that takes two groups**, plus a rule that a big group takes it whole. Least work, but the halves
   have no names: the timetable cannot say which lab a group is in.

## Suggested order of building

1. The setup: `made_of` in the reader, the template and the skill copy; the name trimming.
2. The solver side: `Problem`, the model's limits, `assign_rooms`, staged, `report.check`, `checks.py`. Tests on the
   sample school with a pair added.
3. Step 1: Combine on the bar, the card, the Table column, rename and delete, Things to fix; the rule picker.
4. The returned timetable: the model, the check, `Busy`, the helper, the board.
5. The published room pages; `SKILL.md` and the skill version.

## Decided by the committee lead

- While a class has the combined venue, nobody else is in any of its rooms.
- How it behaves on each step, as described above (read back and agreed on 2026-11-19).
- Approach 1.

## Decided by the writer of this document (to be checked on reading)

- A room belongs to at most one combined venue; no combined venue inside another; rooms that take several groups
  cannot be combined; all its rooms are of one kind.
- The suggested name, the starting seats, block and floor.
- A group that no venue seats goes to the biggest venue of its kind, where the kind has a combined venue.
- On step 8 a clash through a combined venue can be forced like any busy room, and then stops publishing.
- The one new step 8 warning for a class in half of its venue; no general seat check.
- The database gains a table and changes nothing that is there.
- A room's rename follows into its combined venue only.
- "For" is the combined venue's own; "Not available" on a room carries to the combined venue, not the reverse.
- On the board by room, a card sits only in the row of the venue it names.
- On the published room pages, a room's page also shows the lessons of the combined venue it belongs to.
- Room names are trimmed when stored and when compared (the stray-space message).
- Nothing in an old workbook is converted without the committee.
- The 10% warning on seats.

## Left to the builder

- The look of the combined venue's card, within the Blocks view's existing style.
- The exact wording of messages not quoted here.
- How the model's room limits are written, as long as the table under "The one rule" holds in the solver, in
  `assign_rooms` and in every check, and a setup with no combined venue builds the same model as today.
- Whether one helper ("the single rooms this venue stands for") serves Python and the page, or one each.

## How it will be checked

- The existing suites, quick and `--full`, unchanged on setups with no combined venue.
- New tests: reading and writing Made of; the four rows of the table in the solver (for the three setups named
  there), in `assign_rooms`, in the uploaded timetable's check, in `Busy`, `fixes.marks` and the page's
  `bdBusyFor`; both room sums; the staged solve holding a pair; "Not available" on a lab against a lesson in the
  pair; the class-in-half warning; a class of 41 with a pair said to seat 40; rename and delete on step 1 (page
  tests); the published page's room pages and "Who's free".
- A solve of the sample school with a pair added: a 40-student class gets the pair, two small groups share the labs
  at one time, no "Room over capacity".
- On the school's real setup (counts only): with D&T Lab 1 and 2, and Food Lab 1 and 2, entered as single rooms and
  combined, the room sums raise nothing new and every Sec 1 D&T and Sec 2 FCE lab row is limited to its pair.
- In a browser, with a real mouse: tick two rooms and Combine, rename a lab, delete a lab, pick the pair in a rule,
  drop a card on a lab while its pair is in use.

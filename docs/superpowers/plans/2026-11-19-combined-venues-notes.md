# Combined venues: notes from the build

Built 2026-11-19 on branch `combined-venues` from main 272dbc7, subagent-driven: a builder and a reviewer per task, then
one review of the whole branch. Design: `docs/superpowers/specs/2026-11-19-combined-venues-design.md`. Plan:
`2026-11-19-combined-venues.md`. Skill version 2026-11.9.

## Rulings made while building

1. **The old-model test compares results.** The plan's test for a timetable saved before this change only checked that
   nothing threw. It now checks that the problems and warnings are the same with and without the new fields.
2. **The refusal sentence is unchanged.** "{room} is in use then." stays exactly as it was, because the page offers
   "Use it anyway?" only on that sentence. Which lesson holds which room is told by the room list ("D&T Studio 2 holds
   Design & Technology for 1A then."), not by the sentence.
3. **Room names are cleaned once, when the solver's `Problem` is built** (`spec.clean_rooms`), and again when a
   timetable model is built. This trims the caller's setup in place. It replaced chasing every place that compares a
   room name.
4. **The browser checks were done by the controller,** not by the builders.
5. **A combined venue's kind is never picked.** It follows its rooms whenever they share one kind
   (`VenueView.syncKinds`), on the card and in the Table. When the rooms differ, the card says so and Things to fix
   reports it.
6. **The slow solve test checks the two studios only** for "one lesson per room at a time". The sample school's Field
   and Hall take two classes at once by rule, so the plan's assertion over every room was wrong. The same test still
   asserts that the solver's own check reports no room over capacity.
7. **The exact room model was not built.** The whole-branch review showed the solver's count is exact only where a
   kind's rooms are one combined venue's own rooms (see Known limits). Making it exact everywhere means the solver
   choosing a room for each lesson of such a kind. That is new solver design and was left as a follow-up.
8. **A lesson's own rows count against a room.** A band with one row in the pair and one row in a room of the pair is
   refused on a move, as the timetable's check already calls it a room used twice. (This reverses a note given to the
   Task 6 builder.)
9. **Odd numbers count as unknown.** A seat count or a class size typed as text ("abc") no longer raises on step 8
   (`spec.whole`). `spec.venue_problems` keeps its own reading, where "20.0" is unknown; `whole` reads it as 20.

## Departures from the design

- The design said the refusal sentence "adds which lesson holds which room". It does not (ruling 2).
- `Combine` has one more refusal than the design lists: "Give each ticked room a name first."
- The page compares a Room rule's target with clean names too (the design named only "Only in venues").
- The Lessons tab's Room filter on the published page also follows the one rule: choosing Studio 1 shows the pair's
  lessons. The search box on that tab does not.

## Known limits

- The design's limits: a room is in at most one combined venue; no combined venue inside another; all its rooms of
  one kind; it and its rooms take one group at a time.
- **The solver's room count is exact only when a kind's rooms are exactly one combined venue's rooms** (two labs and
  their pair, as the school's D&T and food labs are). Once the kind has any other room (a third studio, a second
  pair, or a pair of classrooms among the classrooms), the solver counts rooms period by period, and that does not
  guarantee every lesson can be given a room: with a third studio, lessons at staggered times can leave a class that
  needs the pair with a room marked TBC. The check always reports it ("lesson-groups have no free room"); it is never
  silent. Two ways round it today: keep the pair's rooms for their subject with the "For" box on step 1, so other
  groups do not take them; or move one of the lessons. A test pins this case (`a_third_studio_is_a_known_limit`).
- **Two warnings show on step 7 only** ("Will it fit?"), not in the Things to fix panel beside step 1: "No lesson is
  limited to {venue}…" (the rooms' seats are so large that nobody needs the pair) and "no group size is known…".
  They come from the server's sums.
- A group whose size is not known may be given any room of its kind. Things to fix warns.
- A setup saved with a stray space in a room name keeps the space in the saved name. Everything compares clean names,
  so it works; the space goes when the name is next typed.
- Rules and home rooms do not follow a room's rename (as before). Only the combined venue's list does.
- A class's home room can be a combined venue and nothing says so.
- Typing two room names into Made of on an ordinary room's Table row turns it into a combined venue without a
  question.
- `venue_parts` still lists a combined venue that Things to fix marks critical for a shared room, mixed kinds or an
  "At most N" rule. The counting does not throw on these; it is not exact for them.

## What was tried in a browser (sample school, scratch server, real clicks unless said)

- Step 1: one tick greys Combine with its reason; two ticks and Combine open the card with the suggested name, the
  summed seats and the dashed tile; Undo and Redo take one step each.
- A studio renamed by typing a name with stray spaces: stored clean, and the pair's "made of" line followed.
- One studio's kind changed (set through the list, not a pointer click): the critical message appears, a click on it
  opens the pair's card, which says its rooms are of different kinds. The second studio changed: the pair follows and
  the message goes.
- A studio removed: "a combined venue needs at least two rooms."; the card still shows Made of, so it can be mended.
- Step 6: a new "Only in venues" rule; the picker lists the pair with its rooms in brackets; ticked, it shows as a chip
  with no message.
- A saved setup (put by script) with a room named with a space at the end and a rule naming it without: no "not on
  step 1" message, and the picker shows it ticked. Combine on that setup saved cleanly.
- Table view: the Made of column; the pair's Kind is text.
- Step 8, a four-lesson draft uploaded by script with a class in the pair and another in one studio at the same time:
  "Room used twice … in use as part of D&T Studio 1&2", both cards marked, the warning for a class in half of its
  venue, the room list showing all three venues held by the other lesson, and "Use it anyway?" on picking a held
  studio (cancelled).
- The preview of the published page: three rooms listed; each studio's page shows the pair's lessons "with D&T Studio
  2, as D&T Studio 1&2"; the pair's page says what it is made of; "Who's free" lists neither studio nor the pair while
  the pair is in use, and lists the other studio while one is in use.

## Not tried in a browser

- The read-only (department heads') view of step 1.
- "New kind…" on a studio of a pair; typing into Made of.
- Dragging a card onto a busy studio on the board (the room list was used); forcing with "Yes, use it".
- The PDF and Excel room pages (they come from the same function as the tested Python room view).
- A page published before this change; the Lessons tab's Room filter.
- Print.

## The school's real setup (counts only)

The newest setup workbook (19 November) with its two lab venues entered in memory as two 20-seat rooms each plus a pair
seating 44, and the old "At most 2 at once" room rule dropped:

- No problem reported for either combined venue.
- D&T: 9 Sec 1 rows are limited to the pair. 4 upper secondary rows may use a single lab or the pair; 3 of those have
  no size known.
- Food labs: 8 Sec 2 rows are limited to the pair. 1 Sec 4 row has no size known.
- The "enough rooms" sums raise nothing before or after.
- Things to fix: 16 warnings before, 20 after. The 4 new ones are the "no group size is known" warnings for those
  four groups. None went away.

## After the whole-branch review (one fix pass, then one re-check)

- A room name in the returned timetable's Room column, in a rain room and in a stored room change is cleaned like the
  setup's, so a stray space cannot hide a clash through a pair.
- The rain-room check on step 8 follows the one rule when a home room is a combined venue.
- A broken combined venue shows on step 7 as critical under Venues (it showed as a warning under Lessons with a wrong
  row number).
- Combine says so when the suggested name is already a room, and how to convert that room.
- The warning when no lesson is limited to a combined venue.
- A room of a pair takes one group at a time even with an "At most N at once" rule on it; the pair's kind is read
  from its rooms on the timetable side and on opening a setup; odd Made of values cannot raise; the "Add classes"
  helper does not hand a combined venue out as a home room.
- Checked in a browser after the fixes (sample school): the Combine message when the name is taken, the card's Kind
  line, a reload, step 7 showing the new warning with "Open Venues" and the critical line for a pair with one room,
  step 2 drawing, and an old single room turned into a combined venue by typing two room names into its Made of box
  on the Table view (it kept its name and seats; its Kind became text). Not clicked: "Add (home rooms filled from
  free classrooms)".
- Left from the last re-check, both small: a department head could see "1 change could not be made" on opening the
  page if the saved setup holds a combined venue whose kind is out of step and no committee page has opened it since
  (any committee open corrects it); and the "No lesson is limited to…" warning also shows, oddly worded, for a
  combined venue whose kind no lesson uses. **Both done 2026-11-20** on branch `combined-venues-exact`: a department
  head's page no longer puts a combined venue's kind right on opening (as `save()` leaves Class Parents alone there),
  so there is nothing for the server to refuse; the committee's page and a practice copy still put it right. The warning
  now says what is wrong: "No lesson uses {venue}'s kind…" when no lesson has its kind, "No lesson may use {venue}…"
  when its For box or seats leave every group of the kind out, and the old sentence only when every group that may
  use it fits one of its rooms. Tests: `opening_the_setup_syncs_kinds_except_on_a_department_heads_page`
  (`tests/venueview.test.js`, runs the page's own `openServer`) and `a_pair_no_lesson_can_use_is_worded_for_what_is_wrong`.
- **The exact room count was not built (2026-11-20, the committee lead's choice).** The school's two pairs are each
  the only rooms of their kind, so the count is exact for them; the limit under Known limits stands until a kind gains
  a third room or a second pair.
- On the school's real setup loaded into a scratch server (numbers only, before the fix pass): every step drew with
  no error, step 1 showed 74 rooms of which 2 combined, and the workbook written from it read back with both.

## For the committee, after this is live

The setup today has ONE room for each pair ("D&T Lab 1&2", "FCE Lab 1&2"). Convert each; do not make a second one.

1. On step 1 add the two labs as rooms of their own (D&T Lab 1, D&T Lab 2; the same for the food labs), 20 seats
   each, the same kind as the old room.
2. Turn the old room into the combined venue: on step 1's Table view, in the old room's Made of box, type the two
   labs' names. It keeps its name, so the rules that name it still point at it. Set its seats (44 today).
   (Ticking the two labs and pressing Combine works too, but then remove the old room: Combine says so.)
3. Take off the "At most 2 at once" rule on the old room and the rule in words about the labs. The pair now does
   what they tried to say.
4. Give the Students number for the four upper secondary groups that have none (step 7 lists them).
5. On step 7 press Check again and read "Will it fit?": nothing critical, and no "No lesson is limited to…" line
   (nor "No lesson uses…" or "No lesson may use…" for a pair).
6. Download the workbook and give the outside agent the skill 2026-11.9 with it.

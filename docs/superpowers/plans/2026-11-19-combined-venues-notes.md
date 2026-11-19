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
7. **Odd numbers count as unknown.** A seat count or a class size typed as text ("abc") no longer raises on step 8
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
- **The solver's count is exact for the usual shapes and loose for one.** When a group may use an ordinary room or
  the pair (a class of 30, a third studio seating 30, the pair seating 40), it weighs 1. Two such classes and a small
  group at one time pass the model; the room hand-out then leaves one of them with a room marked TBC and the check
  reports it. It is the same "exact only when the sets nest" limit the solver had before.
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

## For the committee, after this is live

1. On step 1, add the two labs as rooms of 20 seats (D&T, and the food labs), tick each pair and press Combine. Set the
   pair's seats (44 today).
2. Take off the old single "D&T Lab 1&2" and "FCE Lab 1&2" rooms' "At most 2 at once" rule and the rule in words about
   them, and point the "Only in venues" rule at the pair or the labs as wanted.
3. Give the Students number for the four upper secondary groups that have none.
4. Download the workbook and give the outside agent the skill 2026-11.9 with it.

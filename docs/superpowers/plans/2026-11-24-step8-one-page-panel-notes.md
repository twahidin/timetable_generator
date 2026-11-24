# Step 8: one page, the collisions box and the teacher answers: notes

Built 2026-11-24 on branch `step8-no-popout`. Spec: `docs/superpowers/specs/2026-11-24-step8-one-page-panel-design.md`.
Plan: `docs/superpowers/plans/2026-11-24-step8-one-page-panel.md`.

## Rulings

- The "Close" button of the old Lesson tab (`data-bdclose`) and its click branch are gone, because nothing shows it now. Esc and a second click let go of the lesson. Cost if wrong: none.
- For the list of collisions, the name to look for in the first line is the teacher, class, group code or room named in the old first-reason sentence. Reason: the plan's wording was loose for a students sentence.
- When a place has collisions and is also not lesson time, the box shows the lines, then "That is not lesson time for {class}.", and Cancel only. Reason: the spec says the box then says that sentence; the plan's "empty when there are lines" was wrong, so the spec won. Cost if wrong: one extra line.
- One band line only among the collisions. Reason: the plan said the band sentence once; a second "everyone" band in the way is rare. Cost if wrong: one collision line missing while the first is shown.
- Sentences on the page must be true. So "No one in {dept} is free to take {what}. n teachers outside {dept} are free." (with no department: "No one who teaches {subject} is free to take {what}. n other teachers are free."), not "from another department".
- Esc on the delete question also lets go of the lesson (as the old pop-out did). A person would not be hurt.
- Right-click under a card's edge also selects. Right-click now selects the lesson and never lets go of it.

## Known limits

- A red place (the classes are free, but a teacher, room or student collides) still lands at once, with only its first problem said. Listing every collision there is a follow-up.
- Only one band line can appear among the collisions.
- The server still accepts a fix with `push`, though the board no longer sends it. `Board.tell`'s and `Board.question`'s push words are removed.
- `Busy.whys` in `fixes.py` repeats `Busy._why`'s walk on purpose. A new kind of clash must be added to both.
- Switching Rows closes the selection but leaves the page showing (`data-bdrows` has no way back to the earlier tab).

## Small points left as they are

- `back` (the tab to return to) is only recorded when the page shows.
- Esc with a "Step 5 asks for these" entry selected leaves the page as it is.
- The page refetches its lists while its tab is hidden.
- Pointing at a band again resets its chip (old behaviour).
- Select-assignments are written in three places.
- The first-line test of the collisions is a substring check; there is no test of a doubled room.
- `question` takes its swap words from `asks(s)`, not `offers(card, s)`. Pool slots have no swap, so this cannot be reached.
- No test of the teacher sentence with more than 8 free outsiders.
- `who.free` and `who.doing` are now constants in the teacher payload.
- Switching two-row tabs: with four tabs the tab row is always two rows.
- Letting go of a "Step 5 asks for these" entry has no way back to the earlier tab.

## Checked in a browser

By the controller, with real clicks and drags on a scratch server and a sample school:

- A click on a lesson: no pop-out, the Lesson tab with its buttons and lists. Delete asks inline, and Cancel works. Esc goes back to the earlier tab and the Lesson tab stays. A click and a second click on an empty period. A right-click on an empty period and on a lesson. An answer scrolls into view.
- Lift out (the lesson goes to Not placed, still selected). A click-place from the tray. Undo with Cmd+Z. A drag from the tray to the board.
- A drop on another lesson at lesson time: "collides with:" with a Teacher line and a Class line, "Put it here anyway" and Cancel. Putting it there leaves both lessons marked "In two places" with 2 critical, and Undo takes it back. A place that is not lesson time shows the lines, the sentence and Cancel only.
- A band's chips and the lists for each; a Room list change (the page stays); a busy teacher in the Teacher list gives "Give it anyway?" and Cancel puts the list back; the No room counter; Show me goes to the right day; the Teachers rows (a click gives the page for that teacher's group, no chips); Delete and then "no longer on the timetable", and Undo brings the page back.
- "Who could I trade this class with?": "3 direct swaps are possible for … 4 more would land with a problem.", with Direct swap three times, then Not a direct swap four times; Preview and Apply on the direct ones.

## Not tried in a browser

- A hover while dragging over a day's tab.
- The collisions box with more than 8 collisions ("and n more").
- A hand-over after "Put it here anyway" on the Teachers rows.
- The box where nothing collides ("Nothing collides." with "Put it beside them"), a clean swap, and a "Step 5 asks for these" entry's line.
- The new "No one in … is free" sentences and "Who else could teach it?" on the page.
- The published site (nothing here is deployed).

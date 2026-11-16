# Upload and edit, stage 4: decisions made while building, and what was left

From the build ledger of `2026-11-17-upload-and-edit-stage-4-teachers-rooms.md`. Built subagent-driven on 2026-11-17 (a fresh implementer per task, a reviewer per task, one whole-branch review, one fix wave and its re-review) on branch `upload-and-edit-stage-4`, cut from `upload-and-edit-stage-3` at b20fb0b. Design: `docs/superpowers/specs/2026-11-16-upload-and-edit-design.md` (stage 4 of 4). The committee lead had said "continue the rest of the stages" and, during stage 3, "The warnings and fixes should be highlighed in the editor instead of a separate section. ie it should part of the timetable section". The plan was not read by them before the build.

## What was built

The board's rows can be switched: Classes, Teachers, Rooms. On Teachers rows every teacher of the setup has a row under their department, with their lessons of the day; a lesson taught by two teachers is on both rows; a lesson with no teacher is on a row "No teacher" at the top. Rooms rows are the venues by kind, with a row "No room". A teacher or a room that only a lesson names has a row under "Not in the setup". A click on a teacher's or a room's name opens that row's whole cycle. Day tabs, Find, the counters, the strip and the panel work the same on all three.

A lesson is given to another teacher by dropping its card on that teacher's row, and to another room by dropping it on that room's row. The page first says what it changes ("Give Physical Education for 1A to Harish Rahman in place of Farhan Low? It changes 4 lessons of Physical Education for 1A."). When the teacher or the room is busy then, it says so and asks "Give it anyway?"; yes lands it and both lessons are marked. A drop on another row at another period changes the time too.

A selected lesson opens in a fourth tab of the panel, "Lesson": its teacher list (None first, then who is free then, then who is busy and with what), "Add a teacher", its room list (free and the right kind, free and another kind, in use then), a tick box to change the room for all the group's lessons, and for a band each group with its own lists. "None" for the only teacher asks first, since a lesson with no teacher cannot be published.

The helper's "Ways to settle this" opens under a warning in the Warnings tab, each way with Preview and Apply. The typed request box is at the foot of that tab. "Show me" on a teacher clash goes to Teachers rows, the day and the period its sentence names. The old one-class editor is removed: step 8 is the step's heading, the upload card and the timetable card, and nothing else.

Where a card fits is worked out without judging a push out and a place beside for every place with another lesson. Each such place is blue; the two are judged for the one place the card is dropped on.

Under the page: the board's data gains the teachers by department, the rooms by kind and each row's key. `GET /api/draft/lesson` lists who and which room could take one lesson. `GET /api/draft/place` judges one place. A teacher or a room fix may be forced, with the reason the page showed (`why`), as a move may since stage 3. A room fix with `all` changes every lesson of the group, each judged in turn, kept as one batch that one undo takes back. A room fix that changes nothing is refused. `static/board.js` holds the rows, the hand-over and the lists as plain functions. `ttgen/` is not changed.

## Rulings (decisions made where the plan was silent or wrong)

The plan's own calls, not yet confirmed by the committee lead

- The rows are switched by three buttons above the board: Classes, Teachers, Rooms.
- A lesson taught by two teachers is on both their rows. A lesson with no teacher is on a row "No teacher"; a lesson with no room on a row "No room".
- A click on a teacher's or a room's name opens that one row's whole cycle, as a class's name does.
- Dropping a card on another teacher's row replaces the teacher whose row it was dragged from with the one it is dropped on. The page first says how many lessons the change touches: a change of teacher is for all the class's or group's lessons of that subject, as it always was in this app.
- When the teacher or the room picked is busy then, the page says so and asks "Give it anyway?".
- The selected lesson opens in a fourth tab of the panel, "Lesson". "Teacher, room and more" on the line is gone.
- The helper's ways open under a warning in the Warnings tab; the typed request box is at the foot of that tab; the old one-class grid with its lists of places is removed.
- Every place with another lesson is blue, and the question says what is possible there once a card is dropped on it.

The server

- A room fix that changes nothing is refused with "That changes nothing.", and a change of room for all a group's lessons skips the lessons already in that room. The first version stored fixes reading "is now in 1-03, not 1-03."
- A room is listed "free" only when a change to it would not be refused for the room, so the list and the judgement agree.
- A lesson with no teacher reads "has no teacher on the timetable; step 5 says …" in its difference from step 5. It read "is taught by  on the timetable", with an empty name.
- The helper's two sentences for a warning it has no way for end "Select its lesson on the board to see where it can go." They named the grid that is gone.

A drop on another row

- When the drop also changes the period and that move is clean, the move waits for the hand-over's answer, so both go as one change with one undo, and Cancel changes nothing. After a move that had to be forced, a swap or a push, the time change is already made and Cancel leaves it. The question says "Yes also moves it to …".
- "Give it anyway?" is offered only when the server's own sentence says that teacher or that room is busy then. Any other refusal is said as it is.
- A card with no lesson rows still has a row in the Teachers and Rooms views, and the "No class" row is a row like the others.

The Lesson tab

- "None" for a teacher asks first only when it leaves the lesson with no teacher. Taking one of two teachers off is made at once; Undo takes it back.
- The tab closes when another lesson is picked up by dragging. It stayed open on the old lesson, with lists that did nothing.
- For a subject the class has one lesson of, the sentence reads "A change of teacher changes this one lesson of …".

The whole-branch review

- A change of room for all a group's lessons is never forced. The first version asked about the one lesson selected and, on yes, put every lesson of the group into the busy room, because the server's sentence for a busy room names no time and so was the same reason for each. Now the server refuses the whole when any of them would clash, and with the box ticked the page says "Untick “all this group's lessons” to use it anyway." A whole group in a busy room has to be done lesson by lesson.
- A busy teacher's question adds "It may clash at other times too." when the change covers more than one lesson: the yes is about the lesson shown, and the change is for all of them.
- For a lesson with no teacher the helper says "This lesson has no teacher. Pick one on its Lesson tab." It named a heading of the removed editor.
- After a choice in a list of the Lesson tab the keyboard is given back to the page, so Escape and Ctrl or Cmd+Z work at once.

The Warnings tab

- "Show me" on a teacher clash reads the day and the period from the warning's sentence. The first version went to the first day that teacher had a marked lesson on, so a second clash was never reached.
- A change made on the board frees the board at once; the open ways are fetched again afterwards. Answering a warning ("Update step 5", "Still met") shuts its ways.
- Apply or Preview pressed while a change is being saved says "Wait for the last change to finish."

The build itself

- Task 6's five commits carry the co-author line of the model that wrote them, Claude Opus 5.5, where the rest of the branch names Claude Fable 5.2. They were left: rewriting commits in the owner's checkout to change a name was not worth it.
- Review findings that were small and in the next task's files were carried into that task's builder, not given a round of their own.
- The browser tool's screenshot frame is wider than the page when the pane is narrow (800 against 544 CSS pixels), so a click's coordinate is the page's times the ratio. One click of the controller's landed on a class's name before this was seen.

## Checked on the real files (counts and timings only)

- Both real timetables, against the setup workbook: the Teachers view has 92 rows in 9 departments and the Rooms view 73 rows in 10 kinds, the same as the setup. On the newest timetable 15 more teachers that only lessons name have rows under "Not in the setup".
- The newest returned timetable: 994 cards, every one on a teacher row and a room row; 200 have a lesson of two or more teachers. The returned timetable of 10 November: 1,018 cards, every one on a teacher row; 61 have a lesson with no room and are on the "No room" row; 240 have two or more teachers. No card names a teacher or a room that has no row.
- Timings: the board's data in 0.05 to 0.09 s. Where a lesson fits: 0.05 to 0.06 s in the middle, 0.15 s at worst (0.16 to 0.20 s in stage 3, 0.06 s in stage 2). One lesson's lists of teachers and rooms: 0.04 s. One place judged with its push and beside: 0.03 s.
- On both: a change of teacher to a busy teacher is refused without `force`, kept with it (one or two more critical mistakes), and undone; a change of room for all a group's lessons (4 lessons on one file, 2 on the other) is kept as one change per lesson and taken back by one undo. Every lesson row is accounted for before, during and after (1,954 and 1,948 rows).
- Stage 1's counts are unchanged: 198 warnings and no critical mistake on the newest file, 311 warnings and 99 critical on the 10 November file.
- No commit of this stage holds the school's full name or a real teacher's full name (85 real full names looked for).

## Left as it is

- The half-second hold over a day's tab was still never tried with a pointer held still: the browser tool cannot pause a drag.
- The typed request box at the foot of the Warnings tab was read, not run: typed requests are off on the test server, and no test may call a model.
- "Wait for the last change to finish." on Apply during a save was read, not seen: the save is too short to click into.
- A teacher on another group of the same band is listed "Free then" and judged free. One teacher on two groups of a band at once is not called a clash anywhere in the app. That is older than this work and is a question for the committee.
- A click on a dashed swap card on another teacher's row swaps the two lessons' times and asks nothing about the teacher.
- A lesson waiting in Not placed can be dropped only on Classes rows; in the other two views the page says to switch.

## Deferred minors

- Undo closes the selection, so the Lesson tab closes after undoing a change made in it.
- "all this group's lessons" cannot be applied with the room the lesson already has: another room must be chosen and then that one again.
- The lists of the Lesson tab blink to "Loading…" after each change. Its four tabs wrap onto two lines in the narrow panel.
- For a lesson with two teachers where the teacher kept is himself busy then (only after an earlier forced change), the server's sentence names the kept teacher, so "Give it anyway?" is not offered for the new one.
- On a band where one teacher teaches two groups, a drop on another teacher's row changes the first group only. The question names it.
- A change of teacher is built from the card as the page drew it. A colleague's change of the same lesson's teachers in the same second could be undone by it; a new draft withdraws the question.
- A change of room for all a group's lessons that is refused for another lesson by a rule, not by the room being in use, shows the server's sentence without saying it is about another lesson.
- A card from Not placed dropped on Teachers or Rooms rows waits for where it fits before it is told to switch to Classes rows. The count for the hand-over question gets a fresh 8 seconds.
- With a place named by a clash and no card marked for it there, "Show me" selects the first lesson of that teacher's row at that period. A late answer for the ways can cancel the one-time scroll to them.
- `draft.options` still works out teacher and room lists for an add, which nothing shows any more. `fixes.place` at a lesson's own place answers "That changes nothing."; the page never asks it. The sentence "There is no lesson with that id" is written in four places. The name `held` is used twice in `fixes.choices`.
- Tests not written: a band among the lessons of the test that compares the two kinds of slots; the page's own code (the hand-over, the Lesson tab, the ways in the panel), which was checked in a browser with real pointer and key actions. The pure functions (`static/board.js`, 62 cases) and the server (`tests/test_board.py` 49, `tests/test_fixes.py` 53, `tests/test_helper.py` 18) are tested.

## Next

Upload and edit is built: stage 1 is pull request #57; stages 2, 3 and 4 are local branches stacked on it, each waiting for the committee lead's word to push and open its pull request, in order. After a merge the committee's site needs "Deploy Latest Commit", and the outside agent needs skill 2026-11.6.

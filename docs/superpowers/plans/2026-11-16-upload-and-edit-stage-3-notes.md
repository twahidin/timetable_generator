# Upload and edit, stage 3: decisions made while building, and what was left

From the build ledger of `2026-11-16-upload-and-edit-stage-3-forcing.md`. Built subagent-driven on 2026-11-16 and 17 (a fresh implementer per task, a reviewer per task, one whole-branch review, one fix wave and its re-review) on branch `upload-and-edit-stage-3`, cut from `upload-and-edit-stage-2` at 315e7b5. Design: `docs/superpowers/specs/2026-11-16-upload-and-edit-design.md` (stage 3 of 4). The committee lead had said "continue the rest of the stages"; the plan was not read by them before the build. Half way through they added, in their words: "The warnings and fixes should be highlighed in the editor instead of a separate section. ie it should part of the timetable section". That became Task 6.

## What was built

A lesson can land where it clashes. A drop or a click on a red place moves the lesson there; its card gets a red outline and a few words ("In two places", "In a break", "No teacher"), the counters above the board count it, and the line says why when it is selected. A grey place still refuses.

A drop on another lesson asks one question, with only the answers that are possible: Swap, Put it beside (two groups of one class at the same time, when that is clean), Push out, Cancel. A pushed-out band is named as a band, and the question says which other classes it leaves.

"Not placed" is a tab of the panel beside the board. A lesson gets there by being pushed out, dragged onto the panel, "Lift out", or Ctrl or Cmd+X. It goes back by being dragged or clicked onto a place of its row, or Ctrl or Cmd+V where the pointer is. It keeps its class, subject, teacher and room, and says where it was. A lesson waiting there is a critical mistake: nothing is published, printed or downloaded until it is placed or deleted.

A dragged card held over another day's tab for half a second switches the day. "Delete this lesson" asks first and says when step 5 asks for the lesson. Under the waiting lessons the panel lists "Step 5 asks for these": lessons the setup plans and the timetable lacks, dragged or clicked onto a place to add them. Ctrl or Cmd+Z on step 8 undoes the last timetable change.

The warnings and the changes are inside the timetable section (the committee lead's request). The panel beside the board has three tabs: Not placed, Warnings, Changes. A lesson with a warning is marked on the board (red for a critical mistake, amber "N warnings" otherwise) and lists its warnings when selected. "Show me" on a warning goes to its lesson. The separate warnings card under the board is gone. The old one-class editor opens inside the timetable card, under the board, only while it is in use. On steps 8 and 9 the page's right-hand "Things to fix" column gives its width to the timetable.

A lesson with no room is listed as a warning of its own kind, "No room", with an amber mark and a counter.

Under the page: the draft is still the uploaded file plus the list of fixes. A lesson with no time is not among the model's lessons at all: `fixes.apply` keeps it in a pool beside them, so the check, the old editor, the helper, the printouts and the published timetable never meet a lesson without a time. New fix kinds `lift` and `place`; an `out` list on a move, a place or an add for what it pushes out, worked out by the server under its lock. `force` (with the reason the page showed, `why`) and `push` are words of the request only and are never stored. `ttgen/` is not changed.

## Rulings (decisions made where the plan was silent or wrong)

The plan's own calls, not yet confirmed by the committee lead

- A drop on an empty place that clashes simply lands and is marked. No question is asked; Undo takes it back.
- Cut and paste from the keyboard: Ctrl or Cmd+X lifts the selected lesson out; Ctrl or Cmd+V puts the selected waiting lesson where the pointer is.
- A dragged card held over another day's tab for half a second switches to that day.
- A difference from step 5 about a class's lessons cannot be answered "Update step 5" while one of those lessons is waiting in Not placed. It would shrink step 5 to fit a lesson that was only lifted out. The review found this had to cover every class of a lesson shared by several.
- A lesson with no room is listed as a warning of its own kind.
- Replacing the draft by a new upload asks first when lessons are waiting, and says how many.

What a drop on another lesson offers

- "Put it beside" was added. The plan's question was Swap or Push out only, so a lesson lifted from beside another group of its class could never go back beside it. Two groups of one class at the same time are normal on the school's own timetables.
- A place where another lesson is and the page would ask is blue on the strip. It was grey, which the hint says means "cannot take it".
- A band pushed out is named as a band ("the Mother Tongue band"), and the question says which other classes lose it. It was named by one of its groups.
- A drop anywhere on a lesson a swap is allowed with aims at that lesson's start. A drop on any other lesson is judged where the pointer puts the card, and what it overlaps there is what Push out names.

Forcing and deleting

- The server keeps a change judged a clash only when the request says `force` and gives the reason the page showed. If the reason has changed since (a colleague's change), it refuses with the reason as it now is.
- The board's "Delete this lesson" may delete a lesson step 5 asks for, after saying so. The old editor still may not.
- A lesson waiting in Not placed counts as timetabled against step 5's planned periods and the teacher's load. The first version did not count it, so a lesson could be added past the plan.
- Publishing has a second guard on the pool itself, beside the count of critical mistakes.
- When a fix list is replayed after the setup changed, a push lifts only a lesson that is still in the way.

The page

- The selected lesson's line has one fixed height and scrolls inside itself, and the hint sits in it when nothing is selected. Before this, selecting a lesson made the line taller and moved the rows under the pointer; a real drag missed its row because of it.
- While a card is in the air every place inside the timetable card accepts the drop and the page judges it where it is let go. A release off the rows says where to drop. Chromium decides whether to deliver a drop from the last place it had judged, so a fast drag across rows that refuse used to lose a good drop.
- To keep a drag alive when the board is drawn again under it (the switch of day), the part of the board holding the dragged card stays in place, hidden, until the drag ends. Moving or removing the dragged element ends or strands the drag in Chromium.
- Ctrl or Cmd+Z on step 8 undoes the last timetable change. This reverses stage 2, where it stayed the setup's undo. Ctrl or Cmd+Y does nothing there.
- The counter reads "Other warnings N" (open and not critical) and the tab "Warnings N" (every open one), and the tab's first line adds up: "3 critical · 3 other warnings open".
- A lift or a push made from the board shows the Not placed tab. A lesson in Not placed carries no badge: the tab says what it is.
- Red is worded "lands with a problem", not "clashes": a place can be red for a broken rule.
- A "Not placed" line does not offer the old editor ("Fix the timetable"), which never shows a waiting lesson.

The build itself

- Every browser check of a click, a drag or a key was made with real pointer and key actions and repeated by the controller. The browser tool's drag is unreliable at an emulated window size (it lets go at a wrongly scaled point), so drags were tried at the pane's own size.
- Builders saw a first drag end with no drop now and then, and every retry work. Traced event by event the page's handling was clean each time. It fits the tool letting go within tens of milliseconds, before the browser has answered; it was not reproduced with a hand's timing because the tool cannot pause mid-drag.

## Checked on the real files (counts and timings only)

- The returned timetable of 10 November: 99 critical mistakes as in stage 1 (31 teacher, 68 lessons in a break or outside the day), on 71 marked lessons; 166 "No room" warnings on 61 lessons.
- The newest returned timetable: no critical mistake, no lesson marked red, 27 entries under "Step 5 asks for these".
- On both: a lift, a forced move and a push (one of a band of 15 rows), each undone, with every lesson row accounted for before and after; with a lesson waiting, printouts and the download are refused and so is publishing; a move to a red place without `force` is refused.
- Twenty-five forced moves onto free red places on the newest file: none made a critical mistake without a mark. Eight were red for a rule only and gave a rule warning.
- Timings: the board's data in 0.07 s, 34 KB to send. Where a lesson fits: 0.16 to 0.20 s in the middle, 0.32 s at worst (0.06 s in stage 2).
- No commit holds the school's full name or a real teacher's full name.

## Left as it is

- Where a lesson fits takes about 0.2 s on the real files, three times stage 2's: every place with another lesson gets a push judgement and a beside judgement, each with its own pass over the rules. The fix is to send only who is at each place and judge the push and the beside for the one place the card is dropped on. It is carried into stage 4's plan.
- The half-second hold over a day's tab was never tried with a pointer held still: the browser tool cannot pause a drag. The drop after the switch was tried with a real drag.
- "Ask in words" at the foot of the Warnings tab opens the typed box. It was not seen working: typed requests are off on the test server.
- A teacher-clash line has no "Show me" (it names a teacher, not a lesson). Rows by teacher come in stage 4.
- There is still no way to move a lesson with the keyboard alone except cut and paste with the pointer over a place.
- A waiting lesson also shows as a difference from step 5 ("9 periods timetabled"), with "A lesson of it is waiting in Not placed." added.
- Dragging on a narrow window, where the panel sits under the board, is awkward. The design is for a desk.

## Deferred minors

- The counters row is one line taller at a narrow window (it always holds the Undo button, hidden when there is nothing to undo).
- Ctrl or Cmd+Z while the board is still loading undoes without its "Undone:" line.
- The Changes list shows each change's sentence as stored when it was made; after a setup change a push's "Pushed out: X" can name a lesson the replay no longer lifts.
- While a drop waits for its answer (at most 8 seconds) clicks anywhere in the timetable card are ignored.
- A panel redraw while a card is held over it drops the "Drop here to lift it out." highlight until the pointer leaves and returns.
- A step 5 entry with no class fits only the "No class" row; with Find set every entry fades.
- A waiting lesson with no class gets "Find it on step 8" on step 9 and is not selected in the tray.
- `Draft.follow` aside, `decide` tells a withheld difference by the end of its sentence, not by a flag. Step 9's not-placed sentence is a copy of the server's.
- The helper and the typed request no longer pay for the push and beside judgements, but the old editor's options still take 0.14 s on the real files.
- No automated test of the page code: the drag's states, the panel, the keys. The pure functions (`static/board.js`, 44 cases) and the server (`tests/test_fixes.py` 49, `tests/test_board.py` 32) are tested. The equality of the slots' answers before and after the speed work was checked by a script, not by a committed test.
- Dead code of the old intro editor card; one long README line.

## Next

Stage 4: rows by teacher and by room; the lesson's teacher and room lists with "none" on its own panel; the open band; the helper and the typed request beside the board; the old one-class editor removed, so nothing of step 8 is outside the timetable section. And the speed task above.

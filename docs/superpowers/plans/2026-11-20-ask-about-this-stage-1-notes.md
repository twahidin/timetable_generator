# Ask about this, stage 1: decisions made while building, and what was left

From the build ledger of `2026-11-20-ask-about-this-stage-1-point-and-ask.md`. Built subagent-driven on 2026-11-20 (a fresh builder and a reviewer per task, one whole-branch review, one fix round and its re-review) on branch `timetable-view-helper`, cut from `main` b50d16e, with `main` ded3bfa (PR #74, PR #73) merged in after Task 4. Design: `docs/superpowers/specs/2026-11-20-ask-about-this-design.md` (stage 1 of 2), approved by the committee lead ("Approved, plan it"); they chose "Subagent-driven".

## What was built

On step 8's board a lesson, a band or an empty period of a class's, a teacher's or a room's row can be pointed at: right-click it, or select it (a click on an empty period now selects that period) and press **Ask** on the line. A fifth tab of the panel, **Ask**, opens with what was pointed at at its top ("Physical Education for 1A · Odd Mon periods 4 to 6 · Farhan Low · Basketball Court"), a band's groups as chips, and starter questions: for a lesson "What can this swap with?", "Where else can it go?", "Who else could teach it?", "Who could I trade this class with?", "Which rooms could it use?"; for a lesson in Not placed "Where can it go?", teachers, rooms; for an empty period "What can go here?" and "Who is free then?".

The app answers each at once (no AI anywhere in this stage). An answer is a sentence and up to 8 options, each a change already judged by the code that judges the board: its wording, what else it disturbs, and one of three verdicts (clean, bends a rule, lands with a problem). An option has **Preview** (the small week of each class it touches, in the panel), **Apply**, or **Apply anyway** (asks first, naming the option and the problem) for the kinds the board can force; a swap, a trade and two changes together are never forced and are listed with their reason and no Apply. "Show on the board" goes to the option's lesson.

Applied, an option is a change like any other: on the board at once, in Changes, taken back by Undo. When the timetable changes (an Apply, a drag, a colleague's change, a colleague's save of the setup) the answers on screen are struck through with "The timetable changed. Ask again." and cannot be applied; the server refuses an Apply made for an older timetable with the same sentence.

A new kind of change, the **trade**: two teachers exchange two classes of a subject ("Adam Lee and Chen Wei traded: Adam Lee now teaches 2C Mathematics, Chen Wei 2A Mathematics."), judged on the timetable it leaves (judged half by half, the first teacher would be "busy" with the class they are giving away), one line in Changes, one Undo, in the published record of changes.

The hint line says a click on a row's name shows its whole cycle, and that a right-click asks.

Under the page: `ask.py` (the look-ups, read-only), `GET /api/draft/about`, `draft.stamp` on the draft (in `GET /api/draft`) and a `stamp` on `POST /api/draft/fix` and `/fixes`, a preview of any one change (a place, a trade, a change that lands with a problem shown with the change made), `static/ask.js`, the `ak…` functions of `static/app.js`. `ttgen/` is not changed.

## Rulings (decisions made where the plan was silent or wrong)

The plan's own calls, not yet confirmed by the committee lead: at most 8 options an answer, then "and N more"; "Who could I trade this class with?" looks at teachers of the same subject, step 3 card or department and stops after 40 trades checked (or 0.35 s), saying so; "What can go here?" lists lessons that would start at that period; a click on an empty period with nothing selected selects it; the trade's sentence above.

Made while building:

- "Who else could teach it?" and "Which rooms could it use?" judge candidates in order only until 8 options are made; "and N more" counts the rest unjudged, so it may count one that would be refused. (Judging all 90 teachers a click broke the half-second limit.)
- The swaps answer counts the swaps that can be applied and names the rest apart: "This lesson can swap with 3 lessons. 19 more would land with a problem." / "No swap of this lesson is clean. 19 would land with a problem." A swap with a lesson alike in every way (same class, subject, teacher and room) is left out: nothing a person can see would change.
- "What can go here?" takes its options in turn from lessons waiting in Not placed, lessons step 5 asks for, and lessons of the class elsewhere, so many of one kind cannot hide the others. On a room's row it offers lessons that ask for this kind of room, or whose room is not on the setup's list.
- A trade's refusals for the second teacher read "{x} already teaches {class}." and "{y} does not teach {class}.". "Only the first N possible trades were checked." counts those judged and those seen to clash without judging.
- A break cannot be pointed at (nothing can go there). Nor can an empty period of the "No teacher" or "No room" row; a lesson on those rows can.
- A teacher option's lines: who drops and who rises, and every teacher whose periods change (a teacher kept on some lessons who gains others is now named, in the helper's suggestions and the typed request too); "{name} is in {departments}. Allowance {n} periods." An add says its room ("It goes in A1-02." or "No room of its kind is free then, so it has no room.").
- When an answer comes back for a newer timetable than the page has (a colleague saved the setup), the page fetches the draft first, so the answer is live. A refusal for an older timetable does the same.
- The stamp check and the judging use one setup record, read once.
- Commits up to the fix round name Claude Fable 5.2 as co-author; the fix round's name Claude Opus 5.5 (the session's model changed).

## Checked on the real files (counts and timings only)

The newest setup with the newest returned timetable (1,026 lessons, 32 classes, 111 teacher rows, 76 room rows, 0 critical), and the 9 November setup with the 10 November timetable (1,018 lessons, 92 teacher rows, 73 room rows, 110 critical), at the final code. 40 lessons, 10 bands (two groups each) and 30 empty periods (10 each on class, teacher and room rows) asked every question:

- Every answer came back (no error). Median and slowest, newest file: swaps 0.12 / 0.27 s, moves 0.09 / 0.28, teachers 0.19 / 0.50, trades 0.10 / 0.49 (13 of 60 stopped short), rooms 0.12 / 0.18, who is free 0.04 / 0.27, what can go here 0.06 / 0.12. The 10 November file: the same within a few hundredths, teachers 0.52 at worst, trades 0.46.
- Before the fix round the slowest trade answer was 1.35 s; the fix round brought it under half a second.
- About 2,300 options a file: clean about 1,100, bends a rule 68, lands with a problem about 1,150; Apply about 1,150, Apply anyway about 600, no Apply about 550.
- Preview of 55 and 63 options with Apply: the same verdict every time.
- One option of each question and kind applied with its stamp (6 and 7): every one made and undone; a second Apply with the old stamp refused every time.
- The board and "where a lesson fits" take what they took before (0.17 s and 0.05 s).
- No commit holds the school's full name or any of the 103 real full staff names of the newest setup.

## Checked in a browser (made-up sample school, real pointer and key actions)

Right-click a lesson opens the Ask tab; each starter answers; Preview of a swap that lands with a problem shows the outlined lessons and only Cancel; Apply of a clean swap writes one change and strikes the answers; Cmd+Z undoes and the answers are live again; a second tab's change, then Apply in the first: refused by the server with "The timetable changed. Ask again."; after a colleague's setup save, Apply is refused, the page takes the new timetable, and the next answer is live and applies; after a move the tab's heading names the new time; "Apply anyway?" names the option, and pointing at another lesson or a colleague's change withdraws it. The helper's "Ways to settle this" and the typed request box still preview and apply. The last round of checks was made with the browser pane hidden, in an emulated window: clicks only, no drags.

## Left as it is

- The slowest "Who else could teach it?" is about half a second on the real files (0.50 and 0.52 s, one case in 60 each).
- Not tried in a browser: right-click on an empty period of the "No teacher" row (read in the code and a test); Clear withdrawing "Apply anyway?" (the same code as pointing elsewhere); a drag after this work in a real (not emulated) window.
- When a poll is already fetching, a new answer can show struck through for a moment until the board is drawn again. After a colleague's setup save the upload card's line above the board can change once, moving the board down once.

## Deferred minors

- The load lines say "drops to 1 periods" for a count of 1 (older wording).
- A stale entry asked again is added at the end of the tab, not in its place; asking again about a place does not first check it is still empty (the server answers).
- `fixes.judge` can raise for a trade or teacher change whose key is not text when called directly (the routes guard it). `helper.rank` has no branch for a trade. `draft._one` repeats the add's length and room lines. `planned_rows` is worked out per lesson in "What can go here?" on a room's row.
- `akShow` repeats the scroll-and-flash lines of "Show me"; "the same place" is compared in two ways.
- Tests not written: the page's own code (checked in a browser), the replacement path of "What can go here?", a few room-order and cap cases, `Ask.send` with no fixes.

## For the committee lead to decide

- On 2026-11-20 the lead asked, about the Lesson tab, that a blocked change always says why and offers to do it anyway (PR #74). This design keeps a swap, a trade and two changes together from ever being forced: they show their reason and no Apply. Should they get "Apply anyway" too?
- Stage 2, the typed chat, has no plan yet.

## Next

The lead's word to push the branch and open the pull request; then "Yes, merge it"; then "Deploy Latest Commit" on ct-timetable and a check by hash. No skill version changes (the outside agent's files are untouched).

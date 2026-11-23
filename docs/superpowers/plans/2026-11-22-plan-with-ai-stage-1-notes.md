# Plan with AI stage 1 (the talk and the draft): notes

Plan: `docs/superpowers/plans/2026-11-22-plan-with-ai-stage-1-talk-and-draft.md`. Design: `docs/superpowers/specs/2026-11-22-ai-planning-chat-design.md`
(approved 22 Nov 2026; stage 1 of three). Built 22 and 23 Nov 2026 on branch `plan-ai-stage-1`, cut from main e18d0e3. Main was merged in twice as it
moved (fbcad30, then 4f1a0b6: accounts stage 2, the change of an event's teacher in charge, blank teaching-group rows, relief on Telegram, Re-fit).
Not pushed: it waits for the lead's word.

## What stage 1 gives

- **A page, Plan with AI** (`/plan`), for whoever may change exams (the Exams and events extra, or the timetable committee). A tile on the home page
  and a button on the Exams page open it; an exam's own page has "Open in Plan with AI". With no AI key on the server none of them is shown, and
  nothing else changes.
- **A talk.** The person types what they want to plan; the AI asks for what is missing, a question at a time, with up to four quick answers to press.
  On the right, "Filled in so far" is read from the exam's draft itself, each line with a link to the tab of the exam page where it lives (in a new
  tab). On a phone the panel folds above the talk.
- **Filled in at once, with Take it back.** Starting an exam or common test, its name, levels, classes and dates, each day, the papers, their times,
  the report time and breaks, the seating choices, "as last time": each is one line in the talk ("✓ Put 31 papers in the draft") with See it and Take
  it back. Steps can be taken back in any order; a part someone changed since stays as it is, and the line says which and who saved last. Only a
  draft (sent back included) or a withdrawn exam is changed; one that is waiting, on the main site or ended is refused with the sentence, and so is
  taking a step back on it.
- **The agreed list.** Pasted, or an Excel or Word file (at most 5 MB, 20,000 characters, 200 papers). A file in the app's own layout is read with no
  AI. Lines whose words are the timetable's own go in at once as one step. Lines the reader had to interpret ("Maths" where the level has
  Mathematics G2 and G3) are shown once in a table "As written / Read as" with Yes, all and Not now; a line for several subjects becomes one paper
  each, tied by Sits with. Lines that cannot be matched are listed with the reason. A paper already in the draft is changed, never doubled, and only
  in what the row says (a row with no time leaves the agreed time alone); a line "Changed by the list:" says what it was before.
- **Agreed and suggested times.** A time moves only when the person has just said so in their own words (the server checks the words), or when they
  press one of up to three times the app itself worked out for a paper with no time. A pressed time is marked "suggested" in the talk and on the exam
  page's Papers tab, with an Agreed button, until a person agrees or changes it.
- **Names never go to the AI.** Teachers go as codes ("T07"), students as "a student", the school as "the school", in everything sent: typed words,
  the list, the app's own sentences. Codes become names again before anything is shown. Extra time and own rooms are never sent: the checks the AI
  reads leave them out, and the app itself tells the person when the full check finds more.
- **Nothing of a talk is kept.** It lives in the server's memory, for the person who started it, and goes on New talk, sign-out, 12 hours idle or a
  restart (the page then says so; the exam is whole: Carry on). Nothing is written to disk or a log; an uploaded file is read in memory; the browser
  keeps only the talk's id, so a reload shows the talk again. What the chat changed is in the history like any change, as "{name}, with Plan with AI".
- **The exam and event pages no longer overwrite a newer save.** Every save says which copy it started from; a save from an older copy is refused
  with "This exam was changed by {name} since you opened it. Reload to carry on." (also for events, and after a change of teacher in charge). The page
  keeps what was typed where nobody else changed the same thing.
- **A practice stand-in.** With `TYPED_REQUEST_MODEL=mock` the whole chat can be walked with no AI and no key (a short list of phrases; it says them
  when asked anything else).

Not in stage 1 (stages 2 and 3 of the design): the exam settings (chiefs, backups, left out, rooms, numbers) and Make from the chat, cards to press,
what came out of Make explained, changes to an exam that is waiting or on the main site. The chat says these are done on the exam page.

## What the lead must do before it works on the real site

1. **The key.** The chat uses the key the school put on its own server for the typed request box (`ANTHROPIC_API_KEY` in Railway). With no key the
   tile and the buttons stay hidden. Only the lead enters or changes a key. Each answer is a call to `claude-opus-5-5` at high effort: the design's
   estimate is 5 to 15 US cents an answer (worked out from published prices, never measured).
2. **Merge and deploy** on their word. Then **send one real message in Plan with AI with the server's log open.** No test, probe, review or browser
   run of this build made a real AI call, so the first real answer is the first proof that the AI accepts the request as built. A failure shows in the
   talk as "The AI could not be reached just now." and in the log as the fault's type only (`BadRequestError` would mean the request's shape).
3. **Students.** The school's published timetable has no students today. Until students are added and it is published again, the chat says "Clashes
   not checked: no students yet.", suggests no time, and the panel shows the papers as "to check". Everything else can be filled in.
4. **Exam rooms** are set on the exam settings page (the start screen says so when none are set).

## How it was built and checked

- Subagent-driven: one builder and one review for each of the plan's 13 tasks, fix rounds until each review was clean, the two merges of main each
  as a reviewed task (main's new "change the teacher in charge" was brought under the save check; relief on Telegram and Re-fit save no exam), a final
  whole-branch review on the most capable model, one fix wave after it and its re-review.
- **No real AI call was made by any test, probe, review or browser run.** Every test passes a stand-in; the test files remove any key from their own
  environment and replace the one function that builds the real client by one that fails.
- **Every suite on the final commit** (f9a1ff8): 60 runs, all passed: a syntax check of all 31 page scripts; 24 page-script suites (the chat's page 20 tests, the exam page's suite); 31
  Python suites (the chat 200 tests, routes 20, exams 206, exams with relief 102, history 47, put back 37, sign-in 33, relief on Telegram 302, Re-fit
  166, the smoke test 103, and the rest); and the five slow full forms (combined 39, fixes 67, typed 34, smoke 104, helper 21).
- **Browser practice run** (real clicks, a scratch copy with the app's sample school, made-up names, the stand-in): the Exams page button, the start
  screen, an exam started by typing, whole days by a quick answer, a pasted list with the "Read as" table and Yes, all, Take it back out of order, a
  paper added, the app's offered times and a suggested one pressed, a time moved by typed words (before and after shown), check, keep as last time;
  the "suggested" chip and Agreed on the exam page; the two-writers refusal with Reload on an exam and on an event, with nothing lost; Take it back
  after the exam page had been in between; phone width (375: no sideways scroll, the panel folded); a restart (the lost sentence and Carry on);
  sign-out. After the fix wave, on the final commit: "Open in Plan with AI" from
  the exam page (the talk says what it carries on with, the address is cleaned, a reload keeps the talk), check, a paper added, and the panel's
  "5 papers, 1 to check".
- **The school's real files**, counts and timings only, on a scratch copy deleted after (the newest setup workbook and timetable that belong
  together): 4 levels, 32 classes, 111 teachers, 0 students, 68 subjects, 76 rooms, 1,985 lesson rows. 205 protected words; 111 of 111 stored teacher
  names become codes (103 of 103 with their two longest words reversed; no stored name has a title); no subject, class, room, level, weekday or month
  is changed (0 of 199); what the AI may be shown holds no student id and no teacher name (6,205 characters for the school, 28,349 for an exam of 100
  papers); every call under 50 ms. With 1,246 made-up students in memory: all become "a student"; three times offered for each of five papers in
  about 11 ms each. The final review timed the panel's checklist on a made-up school of 1,280 students with timed papers: 0.5 s at 100 papers and 2.3 s
  at 200, which is why the fix wave keeps the checklist between polls.
- **The public repository**: the branch's added lines were searched for the school's full name and for every stored staff name of the newest
  workbook: 0 and 0.

## Rulings made during the build (what each costs if wrong)

Plan decisions P1 to P9 are in the plan. During the build:

The save check (exam and event pages)
1. The page takes a revision only together with the whole exam (or from its own action when it is exactly the next one). The plan's "take it from
   every reply" would let an old copy overwrite a newer one. Costs an extra Reload now and then.
2. When the server sends the whole exam while something is typed, the page merges key by key against the last copy the server is known to hold: what
   only the person changed stays, what only others changed comes in, the same thing changed by both blocks the page. Costs a false Reload if wrong.
3. A save's own answer never blocks the page; what was typed during the save wins and is saved next.
4. The note about suggested times also shows on an exam already on the main site; it never blocks sending.

Names to codes
5. A leak is worse than a question: where a word could be a person's name or a date word, room or subject ("3 May Lim" in a list when May Lim is a
   person), the whole stored name is coded even if a row then loses its date and is asked about. A month or weekday bound to a day number stays a date.
6. School names under 4 letters are not hidden. A title is a teacher's. A unit after a number (min, hr) stays a unit. Full rules: the plan's Task 3
   and the tests.

What the AI may be shown, and the steps
7. The checks the AI reads count extra time silently (a time that clashes only for an extra-time student is not offered, and never says why).
8. `who` "students" is never set by the chat; a paper and its suggested mark are put back together or not at all.
9. A step made before a send may be taken back once the exam is sent back or withdrawn (the committee no longer looks at it, and each part is
   compared before it is put back). The design's "once sent" is read as "while sent or on the site". Costs an undo the lead did not expect.
10. A pick of a quick answer is taken only while nothing was said after the answer that offered it.

The list
11. A row with neither date nor start goes in without a time (it can get a suggested one); "has no date" is only for a start without a date.
12. A file is refused by what its zip records before it is unpacked; an Excel file is read at most 30 columns wide and 5,000 rows long. Costs: a
    very wide or long real list must be pasted.
13. The Sits with label is per line: "{level} {words} {paper}", so Paper 1 and Paper 2 of one subject on different days are not tied together (the
    plan's label tied them, and the app's check then refused).
14. Rows that repeat an earlier row are listed as not put in, so one repeat never refuses the whole list.
15. The "Read as" table has one row per paper as written, each with its own date and start.
16. On a paper already in the draft a row changes only what it carries: its length always, date and start only when it gives a date, Sits with only
    when given, "whole level" only when it says so; a paper for chosen students keeps them. Costs: a list cannot clear a time; a person does.

The AI calls
17. Only the ten tools with no "may be left out" field are checked strictly by the provider; the six that set things (basics, days, papers, times,
    day times, choices) are not, and the app refuses wrong input itself. The provider's limits (20 strict tools, 24 optional and 16 either-or
    parameters across them) were read on its live page on 23 Nov 2026; an earlier ruling of this build broke them (28 either-or parameters) and every
    real answer would have been refused. A test now pins the three numbers.
18. The history sent to the AI stays sendable after every ending (unrun tools are answered "Stopped.", a refused or cut reply is not kept).
19. A tool's result is compact and at most 150,000 characters; over that it is replaced by a sentence, never cut in the middle.
19a. On the lead's word of 23 Nov 2026, when the AI company refuses a request (a 4xx answer) the log also holds its own short reason (at most 300
    characters, anything in quotes taken out), because the first real call on the live site was refused and the log could not say why. Nothing of a
    talk is logged, as before. Costs: a reason that is cut or hard to read.

Talks and the server
20. The app's notes for the AI (which exam, a step taken back, a new publish) go in a message of their own just before the person's next words.
21. A right that ends between two messages is answered by "Please sign in again." (401), as on every exam page; one that ends while the AI is
    answering refuses the next step with the exam page's sentence.
22. A person's talks are keyed by a keyed hash of their name (records have no id); the shared committee code's by a random token in the session.
23. The list route reads an upload in memory only, and refuses a body with no stated length.

The page
24. Links that leave `/plan` open in a new tab, and the page remembers the talk's id (only the id) so a reload or Back shows the talk again.
25. A done step has "See it" to the exam's page, built from the app's own link, never from a line's words.

The build itself
26. Commits from 23 Nov end with the Fable 5.2 co-author line (the session's rule); earlier ones with Opus 5.5's.
27. `plan/names.py` (760 lines) and `plan/steps.py` (about 870) each stay one file: the final review said not to split what was just settled.

## Known limits

- N1, fixed on 23 Nov 2026 in its own small pull request: a day the chat sets must say "whole day or part" (a missing one is refused), and a whole day takes no times.
- N2: a step's answer to the AI over 150,000 characters would be replaced by "That is too much to show at once." after the change was saved (about
  60,000 at 200 papers, so out of reach today).
- N3: the panel's kept checklist is rebuilt when this exam, the publish, the exam settings or the day changes, not when the school calendar or the
  earlier exam it says "as last time" about changes; the AI's own read is always fresh.
- Names sent as typed: a name the app does not know; a student's first name alone; single words in a list; a student's name glued to a class
  ("3AAlicia Ng"); "Miss Hakim Art Room" in a list where spaces alone separate columns takes the subject's word (11 of 48,000 made-up rows).
- The person's "own words" check proves that the words the AI hands over were typed or pressed as whole words since the last answer, nothing more.
- A list line that covers two levels takes one set of subjects when corrected; if one level does not publish one of them the correction is refused.
- "See it" opens the exam page's first tab. Typed words about an event or the weekly timetable get a sentence, not a link.
- A talk can be opened even when a start check stops it (only the page hides the box). The lost sentence says "restarted" also for a talk closed
  elsewhere or idle 12 hours. A very long talk that reaches the AI's own limit says "could not be reached" rather than "start a new talk".
- `AppEnv.may()` in `app.py` repeats the sign-in check clause by clause: a new clause in one must be added to the other.

## Not tried

- A real AI answer: none, by rule. So also: how well the real AI asks, what an answer costs and how long it takes.
- In a browser: Stop while an answer runs (the stand-in answers at once; tests cover it), an Excel or Word upload (the browser tool cannot choose a
  file; tested over HTTP with a 1 MB file), the Approval tab's "papers have a suggested time" line (the practice exam was not made; node tests cover
  it), the home tile and a person with the Exams extra (the practice run used the shared committee code; route tests cover both), a right ending in
  the middle of a talk, a link opening in a new tab, a screen reader.
- `steps.run` on the school's real data (it saves).

## Follow-ups outside this branch

- The exam page's own "Upload a paper list (Excel)" (on main since exams stage 1) reads a workbook without the size guards this branch gives the
  chat's reader: a crafted file could keep the server busy.
- `tests/test_helper.py --full` fails in some runs on any branch (the slow check solves a timetable afresh for 30 seconds; cause found on 16 Nov, the
  fix is on the unmerged branch `helper-full-flake`). It passed in this branch's last full run and failed in four of
  five runs during the second merge; not this branch's.
- One test of this branch (`after_is_read_alike...`) failed once in many runs on a busy machine: its scripted answer finished before the route built
  its reply. A test's timing, not the app's.

## Stage 2 starting points

- The cards (Change the settings, Make seats and duties, Make the change) need a `form` line kind: `talk.py` and the page already carry `buttons`
  and `table` on a line, and `steps.Refused` sentences with the exam's link.
- "Seated", "rooms over" and the counts of why a duty is short are not in the server's figures yet (the design's "Facts the builder needs").
- The exam settings page saves its whole file and has no save check yet; the design gives it one with the settings cards.
- When stage 2 lets the chat name teachers (chiefs, left out), re-read the parked name cases in the plan's ledger: "Mdm Lim may be away" in an app
  sentence, a stored name with a bracket and a paper, two stored names that overlap.

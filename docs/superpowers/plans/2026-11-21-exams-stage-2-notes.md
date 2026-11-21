# Exams and events stage 2: notes

Built 21 November 2026 on branch `exams-stage-2` (from origin/main cc310f4), subagent-driven: a builder and a reviewer per
task (eight tasks, three of them with a fix round), then a finishing task. Plan: `2026-11-21-exams-stage-2-approval-and-main-site.md`.
Design: `../specs/2026-11-20-exams-and-events-design.md`. Stage 1: `2026-11-21-exams-stage-1-notes.md`.

## What stage 2 gives

- **Approval.** An exam moves draft, waiting for the timetable committee, approved (on the main site), or back to draft
  with the committee's note (sent back), or withdrawn. "Ended" is worked out from the last date. **Send to the timetable
  committee** needs Make done, not stale and no paper-time error (the other checks are for the timetable committee to
  weigh). **Approve, Send back and Withdraw** (and the same for a list of changes) are for the timetable committee only,
  and they still work after a new publish (they save without the timetable check; Send and every edit keep it). Approving freezes a copy of everything the main site reads
  (papers, days, levels, classes, access, seats and duties); the schedule keeps a log of who did what and when.
- **Changes after approval.** An edit and Make leave the approved copy on the main site. **Send the changes** lists what
  would differ (papers added, removed or moved, invigilator changes, room changes, seat counts) and puts the schedule in
  "changes waiting"; the committee sees only that list. Make again keeps every sitting whose papers are as approved
  exactly as approved, and re-seats a changed sitting while keeping its approved invigilators where they are still free.
- **Someone is away.** On an approved schedule the exams committee names the person who is away and who takes the duty;
  it is applied to the approved copy, and to the working copy only where its duty holds the person away (a change
  waiting for approval is kept as it is), logged, and listed for the timetable committee as "Done without approval". The
  panel lists every duty of the approved copy, so a duty is reachable even when a waiting change moved its sitting.
- **Other schedules count.** The rooms and duties of other schedules that are waiting (their working copy), approved
  (their approved copy) or approved with changes waiting (both copies) are taken or busy for Make, "Who could take it"
  and the "free then" check. A combined venue and its own rooms are one room in the review's clash line.
- **The Approval tab** (mockup tab 10): what changes on the main site (classes and dates, lessons that stop, teachers
  with duties and the most duties, venues taken, rain rooms used anyway), five checks (papers, everyone seated,
  invigilators free then, clashes with other schedules, "the timetable changed since this was made"), the buttons and
  the note.
- **The main site.** `GET /api/day?date=` gives one date from the approved copies only: which lessons stop, each class's
  papers, and (for staff) each teacher's and room's duties. The published page has a **date box** ("Usual timetable" or a
  date): lessons that do not happen are crossed out, papers and duties are drawn as extra cells, a non-school date reads
  "Not a school day.". A **banner** shows while an approved exam is on today or in the next 7 days, and an **Exams** tab
  shows the timetable per level (staff also get the roster by day and the PDFs: seating plan, both rosters, exam
  timetable). The page fetches all of this, so the cached published page never holds exam data.
- **The shared student code** gets classes, rooms and times only: no teacher names, no duty rooms, no roster, no prints,
  and no class line names the access-arrangements room.
- **My exam duties** (a staff member's own duties and the lessons that do not happen for them, on the Exams and events
  card; `GET /api/exams/my-duties`) and **My exam timetable** (a student's own papers with report time, venue and seat,
  and their access arrangement's room and times only for them; `GET /api/me/exams`, personal code, used by parents too).
- A full Make now clears a pin of a vanished sitting (stage 1's follow-up). "Scripts go to" is a new field on an exam.
- Rights live in six helpers in `app.py` (`_exams_gate`, `_exams_rights`, `_exams_can_approve`, `_exams_can_keep_list`,
  `_published_reader`, `_exams_student`) and `@need(...)` uses only today's role names: no other exams line reads the
  role or the session, so the personal-accounts work rewrites them in one place.
- No model, Telegram or network call anywhere; nobody is messaged yet.

## The controller's brief: decisions (B1 to B13)

1. States: draft, waiting, approved, sent back, approved with changes waiting, withdrawn, "ended" computed. Kept in the
   schedule JSON: `status`, `approved` (a frozen copy), `approved_at`, `approved_by`, `sent_at`, `sent_by`, `note`, `log`.
2. Send needs Make done, not stale, no check error; Approve, Send back, Withdraw and the same for changes are the timetable
   committee's (`_exams_can_approve`, role committee today). Approving copies the working copy; Withdraw removes the copy
   and the main site stops showing it.
3. After approval, any edit and Make leave the copy live; "Send the changes" computes the difference list and puts the
   schedule in "changes waiting".
4. The one exception to approval: "Someone is away" on an approved schedule (applied to both copies, logged, listed).
5. Other waiting or approved schedules make rooms taken and duties busy.
6. The Approval view as above (mockup tab 10).
7. The date choice reads `/api/day` from approved copies only, filtered by who is asking, and the page crosses out
   stopped lessons and draws exam blocks and duties; "Usual timetable" goes back; a non-school day says so.
8. The banner while an approved exam includes today or the next 7 days ("{name}: {first}-{last}. See Exams.").
9. The Exams tab from `/api/published/exams`, with staff-only roster and prints (`.../print/<what>.pdf`); the student
   code sees only the timetable per level.
10. A teacher's duties on the card, from approved copies; committee members see them above the list.
11. A student's `/me` shows "My exam timetable" from `/api/me/exams`; parents use the same code; no PDF change.
12. A full Make passes `keys=None` to `make._gone`.
13. No history page in this stage (accounts will add it); the `log` is kept.

## The plan's own calls (P1 to P11)

P1 Approve is refused when the schedule changed after it was sent. P2 Make on an approved schedule keeps unchanged
sittings exactly as approved (see ruling G below). P3 A schedule with an approved copy cannot be deleted; withdraw it
first. P4 On the main site a lesson stops when every class in it is on some approved schedule then (two schedules
combine; a lesson whose classes sit different schedules at once stops). P5 A class line never names an access room;
make-up papers are not in class lines or the per-level timetable. P6 The date choice is on `/timetable` only and the
date is not kept in the page's link. P7 "Scripts go to" field. P8 Staff prints on the main site: seating plan, both
rosters and the exam timetable; none for the shared student code. P9 "Who's free on a date" counts duties and exam
rooms. P10 "Preview on the main site" (mockup tab 10) is not built. P11 The committee page link reads "Exams · {n} waiting".

## Rulings made during the build (each also in the ledger)

- **A** Task 1 also touched `exams/make.py` (`make.STALE` comes from `approval.STALE`); the plan's file list missed it.
- **B** `log` is read as `old.get("log") or []`, and a new schedule starts with `log=[]`, `approved=None`, `note=""`, so a
  save of a draft never leaves `log: None`.
- **C** "Someone is away" re-stamps `sent_fp` when the fingerprint equalled it before the replacement, so an away
  replacement alone does not block Approve. Cost: only the replace path re-stamps.
- **D** The away panel asks `/who?copy=approved`, so its list and the route use the same approved copy.
- **E** The student's own page (`/me`, personal code) never fetches `/api/published/exams` (that would be a 401); it
  fetches only `/api/me/exams`.
- **F** Task 9 adds files by name (never `git add -A`).
- **G** Make on an approved schedule keeps unchanged sittings exactly as approved; a changed sitting is re-seated and its
  rooms keep their approved invigilators where those people are still free (done through `assign(prefer=...)`, nothing
  extra is stored in `pins`). Cost: a moved paper keeps invigilators the committee may want changed; they can change
  them by hand.
- **H** Two weak page-word tests were replaced by `"runs "` and `"Exams · "`.
- **I** Small defects found by the pre-flight scan were carried into the tasks that owned them (one `retimed` rule, one
  free-check helper, tests for `scripts`, `on_site`, `last_date`).
- A shortened lesson (part of it stopped) keeps its teacher busy in every period it still runs, by overlap, not
  containment ("Who's free on a date"; fix round of Task 7).
- Where another schedule's clash is named by the free check, the separate "takes N of these invigilators" line is dropped
  (fix round of Task 8).
- The trailer on commits stays the plan's "Claude Opus 5.5".

## The final review's fix wave (21 November 2026)

A whole-branch review (cc310f4..543da73) confirmed four important findings on the made-up school; one fixer then made
every change below, each with a test (the made-up school only).

1. **Overlapping saves.** An approve during a Make was undone when the Make saved the copy it had loaded (gunicorn runs
   one process with 8 threads). Every route that loads and saves a schedule (edit, Fill, paper upload, Make, move,
   invigilators, use anyway, send, approve, send back, withdraw, someone is away) and delete now hold one lock
   (`schedules.editing()`, an `RLock`) from loading to saving. Test: a slowed Make and an approve in two threads; the
   approve is kept.
2. **Approval after a new publish.** Approve, send back, withdraw and someone is away save with `check=False`, so a
   schedule approved before a publish that dropped one of its students can still be withdrawn; Send and every edit keep
   the check.
3. **Someone is away and a waiting change.** The approved copy is pinned to its own names; the working copy's duty is
   changed (and pinned to its own names) only when it holds the person away, and when the person taking over is on it
   already the one away just leaves (no name twice, `short` worked out again).
4. **A student who joins after approval.** Make keeps an approved sitting only when the students who sit it now are its
   seated and unseated students; who sits each paper is in `make.fingerprint` (so the schedule is stale after such a
   publish); the seats check also counts students who sit a made sitting but are in neither list. A class whose count
   changes in one room reads "3A: 3-01 (30) → 3-01 (31)." in the change list.
5. `/api/day` takes only YYYY-MM-DD (`fromisoformat(raw).isoformat() == raw`): no week dates or short forms.
6. A schedule with changes waiting holds both copies for the other schedules (the working duties that differ are
   "waiting").
7. Who keeps the exams committee list (`_exams_can_keep_list`) and the student of `/api/me/exams` (`_exams_student`) are
   named helpers; no other exams line reads the role or the session (a test reads `app.py` for it).
8. The "Someone is away" panel lists every duty of the approved copy ("Duty on the main site").
9. My exam duties lists the lessons that don't happen for a teacher with no duty too (the card shows for them).
10. The timetable check without a publish date reads "a new timetable was published." (never "published on .").
11. `schedules.listing(today)` needs `today`; nothing in `exams/` reads the clock but `schedules._now` (invigilate reads
    the saved schedules through `schedules.all_saved()`).
12. `/who?copy=approved` for a duty that is not there: "That duty is not on the main site."
13. The Approval tab keeps a "takes N of these invigilators" line unless the free lines name that schedule on that date
    for at least N people (a node test runs the function cut from `static/exams.js`).
14. README: Send needs Make done, nothing changed since, and no paper-time error.
15. A published page left open across a publish: the page carries the timetable's `published_at` (in its app settings),
    sends it with `/api/day`, and the answer carries it; a different one gives 409 "The timetable was published again:
    reload the page." and the page shows that sentence instead of drawing cells.
16. A combined venue and its rooms are one room in the review's clash line and on a room's view of a date (a paper held
    in LT1 shows on LT1&2 as "in LT1"; Who's free already counted them together). Done on the page for the room view: the
    server's room items stay per room, so Who's free does not mark a sibling room busy.

Tests the review asked for, added: reader and scribe students left out of the class room line for the student code;
Make reading a stored neighbour from disk (its room and invigilators taken: Review Focus 4 end to end); the change kinds
levels, dates, day, scripts, access, Added (timed and not), Removed and timetable; and a committed node test of the
published page's dates (`tests/timetable_page.test.js`: the page's last script in a small fake DOM, crossed cells,
"runs ... only", exam cells for a class, a teacher and a room, Who's free on a date, a holiday, the stamp check).

Cost to know: who sits each paper is now part of what Make used, so a schedule made before this change reads "The exam
changed since Make: press Make again." once after the deploy (stage 1 schedules on the live site included).

### Rulings recorded with the fix wave

- P2 keeps an unchanged approved sitting and flags a name that now clashes (instead of re-filling it), as Review Focus 1
  chose; the committee changes it by hand.
- After a new publish the build shows the `retimed` flag and review lines (plan B6), not a count sentence.
- "My exam duties" lives on the Exams and events card (plan decision); a teacher's own page comes with accounts.
- Approve is not blocked by failed checks: the committee decides with the checks in front of it.

## Checked

### After the fix wave

- Every suite run alone one after another on the final code, all pass: `test_exams` 141, `test_relief` 37,
  `test_typed` 33 (`--full` 34), `test_helper` 20 (`--full` 21), `test_fixes` 65 (`--full` 67), `test_combined` 38
  (`--full` 39), `test_verify` 56, `test_rules` 11, `test_choices` 16, `test_parents` 35, `test_sync` 18, `test_board` 58,
  `test_ask` 49, `test_teachers` 9, `test_venues` 4, `smoke` 102 (`--full` 103), the 17 node test files (two new:
  `tests/exams.test.js` 4, `tests/timetable_page.test.js` 5), and `node --check` on `static/app.js`, `static/exams.js`,
  `static/exams-settings.js` and the last script of `ttgen/timetable_page.html`. The two copies of the page, and every
  `ttgen/*.py` against its skill copy, are identical. In the back-to-back run, with the machine busy (load average about
  20), `test_typed --full` and `test_helper --full` (solver runs) failed once each; run alone afterwards both pass.
- **The school's real timetable (CTSS), counts only, scratch folder deleted.** The newest solver timetable file in the
  folder (v23; the same file stage 1 counted, not Task 9's v17 from deployment): 1985 lessons, 26 periods, no student
  list, so 973 made-up students for the 25 classes of Sec 1-3 by class size. The same made-up term and exam as Task 9
  (Mon 23 to Fri 27 Nov, whole days, one paper per level a day at 08:00 for 90 minutes), the 41 classroom rooms as exam
  rooms, made, sent and approved through the functions.
  - Make: 15 papers, 5 sittings, 4865 student-papers seated, 0 unseated, 125 duties, 0 short. The review's five checks
    all ok.
  - First day, `published.day` for staff: 156 lessons crossed out, 25 class items, 50 teacher items (50 teachers), 25
    rooms; for the student code 156 crossed out, 25 class items, 0 teachers, 0 rooms.
  - 93 teachers have duties (250 duty rows, the most is 5; that teacher has 12 lessons that do not happen). The one
    teacher with no duty has lessons that do not happen and now sees them (item 9). All 973 students have papers (4865
    rows).
  - `/api/day` for the first day: 19228 bytes for staff, 4180 for the student code; `/api/published/exams`: 29585 and
    1503 bytes. A Saturday answers `day: null`; an old page's stamp answers 409; a week date ("2026-W48-1") answers 400.
  - The fix wave on real data: one more made-up student in a Sec 1 class on a new publish makes the schedule stale and the
    review says "1 student has no seat."; Make again re-seats the 5 sittings that student sits (0 kept as approved, since
    every day's sitting holds a Sec 1 paper), places the student in all 5, is fresh, and lists 6 changes; Withdraw after
    that publish answers 200 and the main site is empty.
  - Times: the machine was busy (load average about 20), so Make took 0.6 to 1.4 s both on the code before the fix wave
    (543da73) and after it, run back to back; the fix wave adds no measurable time (review 0.05 to 0.09 s, a day 4 to 12
    ms, `my_duties` 10 to 19 ms a teacher, either way).
- The fix wave's commits hold no real staff name (207 names and short forms of the newest file searched in
  `git log -p 543da73..HEAD`: no full name; two short forms that are ordinary words, one of them also a first name the
  made-up school uses) and not the school's full name (0); the same holds for the whole branch.

### At the end of the build (before the fix wave)

- Every suite run alone one after another on the final code, all pass: `test_exams` 121, `test_relief` 37, `test_typed`
  33 (`--full` 34), `test_helper` 20 (`--full` 21), `test_fixes` 65 (`--full` 67), `test_verify` 56, `test_rules` 11,
  `test_choices` 16, `test_parents` 35, `test_sync` 18, `test_board` 58, `test_combined` 38, `test_ask` 49,
  `test_teachers` 9, `test_venues` 4, `smoke` 102 (`--full` 103), the 15 node test files, and `node --check` on
  `static/app.js`, `static/exams.js`, `static/exams-settings.js` and the last script of `ttgen/timetable_page.html`.
  The two copies of the published page, and every `ttgen/*.py` against its skill copy, are identical.
- **The school's real published timetable (CTSS), counts only, scratch folder deleted.** Newest setup (v17 from
  deployment) with its solver timetable: 1916 lessons, 26 periods, no student list, so 983 made-up students were made
  for the 25 classes of Sec 1-3 by class size. A made-up term (23 Nov to 18 Dec 2026), a Sec 1-3 exam over Mon 23 to Fri
  27 Nov, whole days, one paper per level a day (all at 08:00, 90 minutes), 39 classroom rooms as exam rooms, made, sent
  and approved through the functions.
  - Make: 15 papers, 5 sittings, 4915 student-papers seated, 0 unseated, 123 duties, 0 short, 0.63 s. The review's five
    checks all ok (0.03 s).
  - First day, `published.day` for staff: 168 lessons crossed out, 25 class items, 50 teacher items (50 teachers), 25
    rooms; for the student code the same 168 crossed out and 25 class items, 0 teachers, 0 rooms.
  - 92 teachers have duties (246 duty rows; the most is 5 duties, and that teacher also has 19 lessons that do not
    happen); `my_duties` about 5 ms each. `my_exams`: all 983 students have papers (4915 rows), about 2 ms each.
  - `/api/day` for the first day: 20306 bytes for staff, 4343 for the student code, 6 ms and 4 ms. `/api/published/exams`:
    29685 bytes for staff (3 ms), 1524 for the student code (2 ms). A Saturday answers `day: null`.
- The branch's commits hold no real staff name (192 names and short forms of the newest setup searched in `git log -p
  origin/main..HEAD`: 0 names; one short form is an ordinary English word that appears in code text) and not the
  school's full name (0).
- **Browser, made-up school** (the controller's check, scratch data with a made-up term 23 Nov to 18 Dec 2026):
  - Committee: the Approval tab shows "What changes on the main site" and the checks; "Send to the timetable
    committee" gives "Waiting for the timetable committee"; "Approve: show on the main site" gives approved, and
    "Withdraw from the main site" is offered.
  - Teacher code: `/timetable` shows the banner "Sec 3 End-of-Year Exam: Mon 23 Nov-Tue 24 Nov. See Exams", the date box
    and the Exams tab; picking 23 Nov reads "On Mon 23 Nov (Odd Mon): Sec 3 End-of-Year Exam. Lessons that don't happen
    are crossed out.", with crossed lessons, the two papers drawn with room and times, and the mixed-level Assembly still
    running; the Exams tab (a real click) shows the Sec 3 timetable, the roster by day with invigilators and four print
    buttons.
  - Student code: `/api/day` and `/api/published/exams` carry no teacher names, empty teachers and rooms, no roster and
    no prints (checked from the page by fetch).

## Not tried in a browser

- The fix wave's page changes (the away panel's duty list, the duties card for a teacher with no duty, the "takes" rule,
  the "published again" sentence, a combined venue's room view on a date): covered by node tests and source tests only.
- Send back, Withdraw, changes waiting, "Someone is away".
- A staff member's "My exam duties" and the student's `/me` "My exam timetable" (personal and staff codes cannot be typed
  in the pane; covered by tests).
- Phone width, and the printouts of the main site.
- The two stage 1 gaps still stand: an uploaded paper list and a PDF in a real viewer.

## Deferred minors

What the fix wave below closed is gone from this list.

- Approval: `printouts.py` has an unused `import datetime`; `approval._when` reads `p["minutes"]` (TypeError if missing);
  `fp` uses `default=str`.
- Make: the approved duties are deep-copied twice; `_gone(keys=None)` reports gone names for kept sittings whose duties
  still carry them; the prefer pick has no chief-first choice; the backup skip in the prefer loop has no test.
- Review: the timetable check would flag an unmade schedule (the review only runs once made); no test with a class
  outside every window.
- Schedules and routes: no route-level test of `elsewhere` with a second approved schedule (the fix wave's test reads a
  stored neighbour through Make itself); a near-empty assertion at the end of `day_refuses_bad_dates`; print names other
  than seating are not tested against `TITLES`; one lock for every schedule, so a Make of one schedule holds an edit of
  another for its 0.6 s.
- Published layer: "also {rooms}" can name a non-access duty room; the banner count counts a make-up date outside
  start..end; `published` calls the private `days._date` and `days._window`; module-level test statements sit outside
  `@t`.
- Pages: a mixed cell is drawn uncrossed; `chipClass` depends on the label strings; `say` is built twice; the chip and
  notice refresh only on opening the Approval tab or on an action; one weak assertion (`"S.abMsg"` in the js).
- Spec items not built: "lessons that use a taken venue" in the review (stage 1's busy-room flag covers it);
  "Preview on the main site" (P10).

## For stage 3 and 4

- **Stage 3 (telling people).** The approved copy and its `log` are the source for messages: who sent, who approved, who
  is away. Relief's absences should feed "Someone is away" (today the exams committee says who is away). Relief stage 3
  adds its own layer to the same `/api/day` answer: the `exams` key is a small object so another key can sit beside it.
  Nothing tells a teacher or student yet (no Telegram, no page notice beyond the banner).
- **Stage 4 and accounts.** `_exams_gate`, `_exams_rights`, `_exams_can_approve`, `_exams_can_keep_list`,
  `_published_reader` and `_exams_student` are the only places that read the role or the session; personal accounts
  rewrite them. A history page with "Put back" can read `log` and the
  approved copy; no history page exists yet. The staff code in the pane could not be tried, so My exam duties needs a
  browser check once accounts exist.
- The real timetable has no student list: real seating needs the students uploaded or added to the setup and published.
- Real rooms were not scarce at 08:00 (the stage 1 time-reading error stays fixed); the common-test margin warning is
  unchanged.

## Found by the fix wave's re-review (parked, small follow-ups)

- A working duty whose names are only reordered counts as "waiting" too, so the Other schedules check can show both an
  "(approved) takes N" and a "(waiting) takes N" line for the same people (cosmetic).
- The stale-page guard compares the timetable's `published_at`, written to the minute: two publishes within one minute
  cannot be told apart.
- With one lock for every schedule, creating or saving one schedule waits for another schedule's Make (about a second
  on the school's real data).
- `/api/day`'s `rooms` stays per room; the page spreads combined venues (`relatedRooms` mirrors `seating._related`), so
  the two copies of that rule must be kept in step, and relief stage 3's layer must spread them too.

# Exams and events stage 3: notes (exams, events and relief)

Built 21 November 2026 on branch `exams-stage-3` (exams stage 4 `559f2df` plus relief stage 2 `69f6987`, merged again at
`4dde1f7`), subagent-driven: a builder and a reviewer per task (six tasks; tasks 5 and 6 each had one fix round, every
re-review clean), then a finishing task. Plan: `2026-11-21-exams-stage-3-relief-links.md`. Design:
`../specs/2026-11-20-exams-and-events-design.md`. Stage 4: `2026-11-21-exams-stage-4-notes.md`. Relief stage 2:
`2026-11-21-relief-stage-2-notes.md`.

## What stage 3 gives

- **Relief knows what approved exams and events do to a date.** Only approved copies count (as for the main site). A lesson
  whose every period stops for an exam or an event is shown as "Not happening: ..." on relief's forms and needs no relief; it
  is marked "Not needed" in a new absence. A lesson that is only shortened still needs relief.
- **Someone on an exam duty or going to an event is busy for relief.** They are left out of a lesson's "free then" list and
  shown instead in a fold under it ("Show the N on an exam duty or at an event then"); a stopped lesson frees its teacher; a
  planner cannot choose them as relief (the pick checks see exams too). Their duty and event minutes count as periods in
  "week so far". The forms list a teacher's duties on each date, and an absence on a day the teacher has a duty may be sent
  even when every lesson stops, because the duty must be replaced.
- **Someone away, or covering relief, is not free for an exam or event.** The exam and event pages show away notices, and a
  person covering a relief lesson is busy for invigilation and for who goes.
- **Backups go to relief when a schedule is approved.** The lessons of each person on duty or going that still run during
  their duty become one planned absence per person ("Invigilating: {name}" or "At event: {name}", by the exams committee or
  the teacher in charge) in relief. They show in What's in and to the person on duty, who acknowledges them and sets work;
  choosing relief for them comes with relief stage 3's picks. Records are kept in step in place after every approval action,
  every "Handled ourselves" change, every absence sent or cancelled in relief and every publish. The committee stops a
  backup with "Handled ourselves"; a backup cancelled inside relief comes back at the next sync (which runs straight after
  the cancel).
- **Where each backup stands.** The Lessons tab shows, per person on duty, one item with a state line (handled, relief,
  sent, stopped, past, elsewhere, later) and a **Handled ourselves** tick for cover the committee arranges itself.
- **A person's own absence wins** over their backup: the lessons move into the own absence with the relief chosen and the
  work.
- No model, Telegram or network call anywhere; nobody is messaged. Relief's own approval of picks and Telegram are relief
  stages 3 and 4.
- **Not built** (P1; they need relief stages 3 and 4): the relief layer on the published timetable on a date, the relief
  team's approval of picks (and of a backup), choosing relief for a backup, Telegram and any message to people on duty, a
  Preview of relief for a date.

## Decisions (the plan's P1 to P13)

- P1 **Not built here** (they need relief stages 3 and 4): the relief layer on the published timetable on a date, the
  relief team's approval of picks, Telegram messages. Nobody is messaged.
- P2 Only **approved** copies count (`schedules.on_site()`), as for the main site. A waiting change counts only once
  approved.
- P3 A lesson is "not happening" only when **every** period of it stops (`merged_view` running empty). A lesson only
  shortened still needs relief: relief covers lessons whole.
- P4 Busy for relief: an exam's made duties (names, room, minutes) and an event's people going over the event's window
  (`schedules.event_busy`). An event's free-text duties (`who`, `time`) are not busy: their time is words, not minutes.
- P5 Duty and event minutes count as **periods** for "week so far": every period whose bounds overlap a duty or event
  window, once a date, leaving out periods of the person's own lessons that still run (counted already).
- P6 **Backups are planned absences**: `how="planned"`, `reason="Other"`, `reason_text` "Invigilating: {name}" or "At
  event: {name}", `by` "Exams committee" (exam) or the teacher in charge's name (event), plus `exams=dict(id, kind)`.
  So relief's pages, What's in, acknowledging, setting work and choosing relief work on them unchanged. The person on
  duty acknowledges and sets work, as any planned absence. (Read with the final review fix wave: no page lists a backup
  for choosing relief yet; that comes with relief stage 3's picks.)
- P7 A backup is one lesson of one person on duty (or going) that runs during their window, dated today or later, that
  is not "Handled ourselves", for a person not away then. One record per person per schedule.
- P8 **"Handled ourselves"** is the exams committee's own business (the lead: "Exam committee only needs approval to
  change publish website other than that they can do what they need to do within the committee"): stored on the
  schedule as `handled` (["{teacher}|{key}"]), outside the approved copy and the fingerprint, applied to relief at once.
- P9 `sync` runs after every approval action that saves (send, approve, send back, withdraw, someone away) and after a
  "Handled ourselves" change. It is idempotent. It never fails the action: an error is logged and the next action syncs
  again. A new publish does not sync (relief's own `matches_now` marks lessons that changed). (Amended by the final review
  fix wave: relief's create and cancel routes and a publish now sync too, through `relief_links.sync_all`.)
- P10 A person's **own absence wins**: when a teacher with a backup record is absent over its lessons, `absences.new`
  moves those lessons into the new absence (with the relief already chosen and the work), and the backup record drops
  them (cancelled when none is left). `sync` sends no backup for someone away then.
- P11 An absence whose lessons all stop, or that has only duties, may still be sent when the teacher has a duty or event
  then: the duty must be replaced. Without exams (links None) the old refusal stands.
- P12 Withdraw, and a changed duty, remove only the lessons of a backup still to come (dated today or later); lessons before
  today always stay (history). A backup record is cancelled only when it is empty. (Amended by the Task 5 ruling I2+I4:
  the first plan cancelled the record on withdraw, except past ones.)
- P13 Locks: `schedules.editing()` may be held while `relief.absences` takes its own lock (sync), never the other way
  round: relief code never takes the exams lock while it holds its own. (Reworded by the final review fix wave: relief's
  create and cancel routes now take the exams lock for a sync, once relief's own call has returned.)

A constraint, not a decision (from the plan's Global Constraints): pure modules take `today` as a parameter; only
`app._exams_today()`, `relief.lessons.today()` and the existing `_now()` functions read the clock.

## Rulings

From the controller before and during the build (verbatim from the build ledger):

- K1 Ruling: tests use the made-up school as it is: the event is a Sec 4 event on 4A named "Sec 4 Learning Journey"; "a Sec 1/Sec 2 lesson" means a 4A lesson; the mixed lesson is the 3A+4A Assembly; sentence formats stay verbatim with these names — the fake has no Sec 1/2 — cost if wrong: none (names only).
- K2 Ruling: the new test file uses its own calendar with a future term (e.g. Term 1 2027-01-04..2027-03-12, starts_as Odd), saved as relief's calendar; tests about the past patch relief.lessons.today (and app._exams_today) as test_relief_requests does — cost if wrong: test-only.
- K3 Ruling: the handled routes answer the same JSON as the route the Lessons tab reads today (whatever static/exams.js fetches for the lists), with mark() applied — cost if wrong: one page fetch.
- K4 Ruling: copy the staff sign-in and published() helpers from tests/test_relief_requests.py into the new file — cost: none.
K5 Ruling (for Task 3): the pick checks must see exams too — absences.new's free_then check for a chosen relief and absences.choose(id, key, relief_name, by, pub, links=None) pass links to free_then; the relief route that calls choose passes _links(...) — else a planner can choose an invigilator as relief (Task 2 review ⚠️) — cost if wrong: one keyword on a function relief stage 3 also edits (told the relief session the touch points).
Ruling: an absence on a day the teacher has a duty is accepted even when every lesson was marked "Not needed" by the person — P11 says the duty must be replaced, and the exams committee learns of it through the away notice — cost if wrong: an absence with nothing to cover shows in What's in.
Ruling: carry Task 4 Minors 1 and 2 into Task 5 (it needs away spans for backups anyway): one shared _away_spans(bnds, records) used by relief_busies, away_on and backups, skipping a malformed record instead of raising — cheap, same file — cost if wrong: none.
Ruling: I1 — _absent_then reads an exams record by needed lessons only — the plan never meant periods as away time (P4) — cost: one line in relief/free.py (relief-owned, not on the do-not-touch list).
Ruling: I2+I4+race+stale text — update backup records in place (absences.update_exams), never cancel-and-remake; past lessons always stay; P12 amended: withdraw removes future lessons, cancels only an empty record — the spec's "cancelled in relief" is about the backup still to come — cost if wrong: an acknowledged record changes under the person (acknowledged cleared when a lesson is added).
Ruling: I3 — backups skip a lesson in another live backup of that person; _relief_sync syncs the acted schedule then every other one — no double cover — cost: a few file reads per approval action.
Ruling: I5 — one backup item per teacher on duty; mark states handled/relief/sent/stopped/past/elsewhere/later; Task 6 shows the new ones — cost: stage 1/4 list counts change.
Ruling (carried into Task 6): "Handled ourselves" on one schedule covers that lesson for every schedule — _held_elsewhere also treats a lesson in another schedule's `handled` (same person) as held, so B does not send what A's committee handled — handled means the committee arranged the cover itself — cost if wrong: one condition.

Not a ruling but a build fact: the first plan text of P12 and Task 5's I4 ("remake/withdraw drops past lessons") was
replaced by the amended P12 above.

## Checked

### Suites (final code)

Every suite run alone one after another (the machine shared with other sessions): all 17 python suites pass (`test_exams_relief` 45, `test_exams` 179, `test_relief` 37, `test_relief_requests` 58,
`test_typed` 33, `test_helper` 20, `test_fixes` 65, `test_combined` 38, `test_verify` 56, `test_rules` 11, `test_choices` 16,
`test_parents` 35, `test_sync` 18, `test_board` 58, `test_ask` 49, `test_teachers` 9, `test_venues` 4) and `smoke` (102); then
`--full` for `test_typed` (34), `test_helper` (21), `test_fixes` (67), `test_combined` (39) and `smoke` (103), each alone, all
pass. All 18 node test files pass (`exams.test.js` 7 cases plus the `onHandled` click-path cases), and `node --check` passes on
every `static/*.js` changed on the branch.

### The school's real published timetable (CTSS), counts only, scratch folder deleted

The newest setup (v23) and its solver timetable (the file stages 2 and 4 counted): 1985 lessons, 26 periods, 32 classes, no
student list (so made-up students by class size, as before), a made-up term (Jan to Mar 2027) and one made-up day, Tue 5 Jan
(today made-up as 1 Jan). Everything went through the functions (`make`, `approval.send` and `approve`, `relief_links.sync`).

- **Sec 3 exam** (one 90-minute paper at 08:00, whole day, 41 classroom rooms): 8 duties, 16 invigilators, Make 0.03 s. Sent
  and approved. **Backups sent: 0.** The 16 invigilators are teachers freed by the exam: of their 38 lessons that day 18 are
  "not happening" (Sec 3 classes) and none of the other 20 runs during their duty windows (07:45 to 09:40), so nothing is
  sent; a second sync also sent nothing. Sync took 3 ms. The 38 lessons were read through `Links.stopped` in 2 ms.
- **free_then for one Sec 1 lesson at period 1** with the exam approved: 63 free (68 without links), 16 left out as busy on a
  duty, 29 teaching; 0.055 s with links, 0.032 s without.
- **To exercise the backups, a Sec 2 event** (08:00 to 13:00, the Sec 2 teachers going, 30 people): sent and approved; sync
  sent **24 backups** (24 people, 31 lessons, 29 of them needed, 2 not needed because a co-teacher is there), 17 ms; a second
  sync sent 0. With the event approved as well, the same Sec 1 lesson's `free_then` gives 55 free and 34 left out as busy
  (exam duties and event), 19 teaching, 0.054 s.
- No name, code or key was printed or written; the scratch folder was deleted.
- The names check (`git log -p 559f2df..HEAD` plus this notes file and the README): 115 names and short forms of the setup's
  teacher sheet searched, 1 matched (547 times, 5 of them in the same capital form): an ordinary English word that is also a
  teacher's first name, in code and prose, as in stage 4; no real name. The school's full name (its first word, lower case):
  0.

### Browser

Done by the controller on the made-up school, in a local test copy (a made-up committee code; the launch file restored
afterwards and compared equal): the Lessons tab showed "Goes to the relief team when approved" with the tick; the Approval
tab "Backups for the relief team: 1 (sent when approved)"; Approve made the relief record (planned, reason Other,
"Invigilating: Sec 3 Common Test", by "Exams committee", the `exams` marker, one 4A lesson needed); the Lessons tab then read
"Sent to the relief team"; ticking "Handled ourselves" kept focus on the box, emptied and cancelled the record; unticking with
the keyboard sent it again; an absence planned for the other invigilator marked their stopped lesson "Not happening: 3A is on
Sec 3 Common Test" and the exams list showed "Away (from relief): ... on duty in 3-01 07:40–09:20. Replace them under Someone
is away."; no server or console errors.

## Not tried in a browser

The relief pages (staff sign-in needs a personal code), events, and phone width. From the final review fix wave (covered by
tests only): the "Handled by another schedule" line, the "Not happening" line on an absence's lesson, and a backup coming
back after an own absence is cancelled.

## Deferred minors

From the task reviews (verbatim from the ledger):

Task 1: complete (commits fb8354b..45978e6, review clean). Minors parked for the final review: cached silent catch in _day/_by_name (log it), datetime input to _iso, in_charge None guard, duplicated period-holding test, no multi-date week_change test. (The reviewer's mid-merge note was the controller's own merge, resolved as e6aea70.)
Task 2: complete (commits e6aea70..154d538, review clean). Minors parked: precedence-looking return in week_so_far, busy checked before away/chosen/never (an away invigilator shows in the busy fold), a no-op try/finally around LS.today in two tests.
Task 3: complete (commits 154d538..3eb46a1, review clean). Minors parked: loose status assertions (400/409/422, != 200), unused old = LS.today, forms test is source words (plan-mandated).
Task 4: complete (commits 3eb46a1..b7838d1, review clean). Minors: malformed relief record can raise in relief_busies/away_on (Make/review); away-span logic written twice; maybe-unreachable else in away_on; test noise (no-op request context, one-item loop, no test that _event_others' relief busies reach the event review); weak ".away" page test; _with_away re-reads schedules via private _all.
Task 5: minor (deferred): two clocks (folded into fix), _copy_files without tmp-then-replace, orphan file copies, "The duty changed." wording when not a duty change, own absence cancelled → backup waits for the next approval action (relief never takes the exams lock).
Task 5: fix round 1/5 (5 addressed + minors, 0 open; commits 169ee43..91cd889). Re-review (opus) clean.
Task 5: minor (deferred): _take_over moves only needed lessons (a Not-needed leftover inside the own absence gets "The duty changed." later instead of "Moved…"); cancel_exams unused and still cancels past lessons (remove or guard); failure isolation across schedules untested; from_exams None when every lesson has a co-teacher there → item "later" forever (update path stores needed False → "sent": disagree); a backup cancelled in relief is re-sent next sync; event review backup count is per person going.
Task 6: minor (deferred): _held_elsewhere reads all_saved() each call and a stale handled tag keeps suppressing; _backups_left recomputes lists (double pass); "Handled ourselves" twice for the handled state.

## For relief stage 3

- **Relief's Today and the load tracker should pass `links`** (`exams.relief_links.Links.load(pub, cal)`) to
  `free.there_then`, `free.week_so_far` and `free.free_then`, as the `/api/relief/free` and lessons routes now do, so a
  lesson that stops is not covered and a person on duty is not picked. Relief must never import `exams.relief_links` at module
  level except in `relief/web.py` (import cycle).
- **The takeover in `absences.new` must carry any new cover fields.** When a new own absence moves a backup's lessons in
  (`_take_over`), it brings the relief chosen, `relief_by` and the work; a field added to a lesson in relief stage 3 (a
  confirmed state, a Telegram message id) has to be carried there and in `from_exams`'s `carry` by key, or it is lost.
- **`_absent_then` reads an exams backup by its needed lessons only** (not its periods): a backup's span is not away time.
  Keep that when changing `relief/free.py`.
- **Backups are planned absences with `exams=dict(id, kind)`** (`how="planned"`, `reason="Other"`); relief's pages treat them
  as any planned absence; `_no_overlap` skips them; `absences.exams_records(id)` lists a schedule's live ones.
- **The relief layer on a date can read `Links`** (`stopped(lesson)`, `busy(name, date, p, n)`, `duties(name, date)`,
  `week_change`), built from `schedules.on_site()`: that is the one place that says what the main site shows for a date.
- Locks: `schedules.editing()` may be held while `relief.absences` takes its own lock (sync), never the other way round:
  relief code never takes the exams lock while it holds its own. Relief's create and cancel routes sync
  (`relief_links.sync_all`) once relief's call has returned; a new relief route that changes who is away should do the same.
- **An absence sent before a schedule was approved** keeps its stopped lessons needed: relief's `_out` marks them `stopped`
  ("Not happening: ..." on the page) and `choose` refuses them, but re-marking them not needed (and taking a chosen relief
  off) is left to relief stage 3.
- **Choosing relief for a backup** comes with relief stage 3's picks: no page lists backups for choosing now (What's in is
  read-only, and "Planned by me" lists the planner's own).
- Not built: messages to people on duty, the relief team's approval of a backup, a Preview of relief for a date.

## Final review fix wave

From the final whole-branch review (opus) of `f49ddad..14083f3`, the Task 7 review and the controller's browser check: one
fix wave (opus), FIX_BASE `14083f3`, commits `0d84374..HEAD`. Each item has a test that fails without it where one can
show it (in `tests/test_exams_relief.py` unless named).

1. **A cancelled own absence left a backup lesson covered by nobody.** `exams.relief_links.sync_all(pub, cal, today,
   first=None)` now holds the loop `app._relief_sync` had (the acted schedule first, then every schedule `to_sync` names,
   each failure one log line, `SYNC_FAILED`, through the module's logger). It runs from `app._relief_sync` (unchanged
   behaviour), from relief's create and cancel routes once relief's own call has returned (`relief.web._sync_exams`:
   inside `exams.schedules.editing()`, imported inside the function, logged and never failing the answer), and from the
   publish route after a publish succeeds (a lesson that moves into or out of a duty window goes to or leaves relief at
   once: P9 amended). Tests: `cancelled_own_absence_gives_the_lesson_back`, `a_republish_sends_a_lesson_that_moved_into_a_duty`,
   `one_failing_sync_does_not_stop_the_others`.
2. **Notes**: P1 to P13 in full from the plan (P9 and P6 noted against this wave, P12 as amended, P13 reworded), the clock
   line moved to a constraint line, the controller's browser check recorded, the grammar slip fixed, a "Not built" line.
3. **A lesson added to a backup shows new in What's in**: `update_exams` stamps `changed_at` (relief's `_now()`) when a
   lesson came in; What's in counts new as sent or changed at or after the time last seen. Test:
   `a_lesson_added_to_a_backup_is_new_in_whats_in`.
4. **An absence sent before a schedule is approved**: relief's `_out` adds `stopped` (the `Links` text or "") to each lesson
   dated today or later of a record still to come (one `Links` per request, kept on `flask.g`; a failure to read the exams
   side logs a line and leaves `stopped` ""), `absences.choose` refuses a stopped lesson "This lesson is not happening:
   {text}." (choosing a teacher only: taking one off still works), and `static/relief.js`'s absence lesson line shows "Not
   happening: {stopped}" (escaped). Tests: `an_absence_sent_before_approval_marks_its_stopped_lesson`,
   `relief_pages_work_when_the_exams_cannot_be_read`, `the_absence_page_shows_not_happening`.
5. **A stale "Handled ourselves" tag** on another schedule counts only while that schedule's approved copy still has the
   person over the lesson (`_handled_elsewhere(sid, links)`, reading the lesson through `links.pub` and `links.cal`); such a
   lesson gets the `mark` state `handled_elsewhere`, "Handled by another schedule", with no tick. Tests:
   `a_stale_handled_tag_counts_for_nothing`, `handled_on_one_schedule_covers_every_schedule` (now `handled_elsewhere`),
   and the state case in `tests/exams.test.js`.
6. **`absences.cancel_exams` removed** (unused; it would cancel past lessons); `exams_records` stays; its test now checks it
   is gone.
7. **The reason when "Handled ourselves" empties a backup**: "Handled by the exams committee." (exam) or "Handled by the
   teacher in charge." (event) when every lesson that left went because it is now handled on this schedule; else "The duty
   changed.". Tests in `handled_ourselves_sends_nothing`, `event_backup_by_the_teacher_in_charge` and
   `a_backup_emptied_partly_by_a_duty_change_says_the_duty_changed`.
8. **Silent catches logged**: `Links._day` logs one line a date, `Links._by_name` one line a schedule (it now reads each
   schedule's busies on its own, so one that cannot be read gives no duties and the others still count). Test:
   `links_log_what_they_cannot_read_once`.
9. **The stopped text** names each class whose window overlaps the stopped time, so it is never " are on ". Today's
   `merged_view` needs one window to hold a whole period, so the case arises only if it ever joins windows that meet
   mid-period; the test (`links_name_the_classes_when_two_windows_meet_mid_period`) wraps `merged_view` to give such a view.
10. **`_with_away`** reads relief's records once per list answer and the schedules through `schedules.all_saved()`. Test:
    `the_lists_read_relief_once`.
11. **README and notes** no longer say choosing relief works on backups "as on any planned absence": backups show in What's
    in and to the person on duty; choosing relief for them comes with relief stage 3's picks. Both say the committee stops a
    backup with "Handled ourselves" and a backup cancelled inside relief comes back at the next sync.

Rulings recorded here (accepted, not changed now):

- `week_change` counts a duty in the stopped part of a shortened lesson twice (+1 period): rare, noted.
- A duty-only absence (P11) can be sent twice for the same teacher and day: `_no_overlap` checks needed lessons only.
- `from_exams` makes nothing when every lesson has a co-teacher there, so that item stays "later".
- Privacy: a teacher in charge who adds a colleague to the going list learns they are away then ("is away then (relief)"),
  never the reason. It fits the spec's "told at once"; the lead may want to know.
- P13 reworded: relief code never takes the exams lock while it holds its own.
- Re-marking "not needed" the stopped lessons of an absence sent before approval is left to relief stage 3 (named there).

The fixer's own calls (for the lead to know):

- Relief's cancel route syncs after every cancel, so a backup cancelled inside relief comes back at once (the next sync
  runs straight after the cancel), not at some later approval action.
- `choose` refuses only choosing a teacher for a stopped lesson; taking a chosen one off still works.
- The "Handled by …" reason reads only the schedule's own tags; a lesson that left because another schedule handled it
  gives "The duty changed.".

Checked after the wave, every suite alone one after another: all 17 python suites pass (`test_exams_relief` 57,
`test_exams` 179, `test_relief` 37, `test_relief_requests` 58, `test_typed` 33, `test_helper` 20, `test_fixes` 65,
`test_combined` 38, `test_verify` 56, `test_rules` 11, `test_choices` 16, `test_parents` 35, `test_sync` 18, `test_board` 58,
`test_ask` 49, `test_teachers` 9, `test_venues` 4) and `smoke` (102); then `--full`: `test_typed` 34, `test_fixes` 67,
`test_combined` 39, `smoke` 103, and `test_helper` 21 on its second run (the first failed one check on the solved sample,
whose 30-second solve is not the same each time; nothing in the wave touches the helper, the check or the solver, and the
second run alone passed). All 17 node test files pass (`exams.test.js` 7 cases plus the `onHandled` cases), and `node
--check` passes on `static/exams.js` and `static/relief.js`. The names check on the wave's commits (`git log -p
14083f3..HEAD`, the newest setup's teacher sheet, counts only): 111 teachers, 332 names and short forms searched, no full
name matched; 6 words matched, each a made-up test name shared with a common name (2) or an ordinary English word (4); the
school's full name (its first word, lower case): 0.

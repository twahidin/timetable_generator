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
  person covering a relief lesson is a busy for invigilation and for who goes.
- **Backups go to relief when a schedule is approved.** The lessons of each person on duty or going that still run during
  their duty become one planned absence per person ("Invigilating: {name}" or "At event: {name}", by the exams committee or
  the teacher in charge) in relief, so What's in, acknowledging, setting work and choosing relief all work on them. Records
  are kept in step in place after every approval action and every "Handled ourselves" change.
- **Where each backup stands.** The Lessons tab shows, per person on duty, one item with a state line (handled, relief,
  sent, stopped, past, elsewhere, later) and a **Handled ourselves** tick for cover the committee arranges itself.
- **A person's own absence wins** over their backup: the lessons move into the own absence with the relief chosen and the
  work.
- No model, Telegram or network call anywhere; nobody is messaged. Relief's own approval of picks and Telegram are relief
  stages 3 and 4.

## Decisions (the plan's P1 to P13)

- P1 **Not built here** (they need relief stages 3 and 4): the relief layer on the published timetable on a date, the
- P2 Only **approved** copies count (`schedules.on_site()`), as for the main site. A waiting change counts only once
- P3 A lesson is "not happening" only when **every** period of it stops (`merged_view` running empty). A lesson only
- P4 Busy for relief: an exam's made duties (names, room, minutes) and an event's people going over the event's window
- P5 Duty and event minutes count as **periods** for "week so far": every period whose bounds overlap a duty or event
- P6 **Backups are planned absences**: `how="planned"`, `reason="Other"`, `reason_text` "Invigilating: {name}" or "At
- P7 A backup is one lesson of one person on duty (or going) that runs during their window, dated today or later, that
- P8 **"Handled ourselves"** is the exams committee's own business (the lead: "Exam committee only needs approval to
- P9 `sync` runs after every approval action that saves (send, approve, send back, withdraw, someone away) and after a
- P10 A person's **own absence wins**: when a teacher with a backup record is absent over its lessons, `absences.new`
- P11 An absence whose lessons all stop, or that has only duties, may still be sent when the teacher has a duty or event
- P12 Withdraw, and a changed duty, remove only the lessons of a backup still to come (dated today or later); lessons before today always stay (history). A backup record is cancelled only when it is empty. (Amended by the Task 5 ruling I2+I4: the first plan cancelled the record on withdraw, except past ones.)
- P13 Locks: `schedules.editing()` may be held while `relief.absences` takes its own lock (sync), never the other way
- Pure modules take `today` as a parameter; only `app._exams_today()`, `relief.lessons.today()` and the existing `_now()`

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

The controller will add the browser check (see below).

## Not tried in a browser

The controller will add the browser check. Until then, nothing in this stage has been looked at in a browser: the Lessons tab
state lines and the "Handled ourselves" tick (covered by node tests that run the click path and by source-word tests), the
fold of busy people and the "Not happening" lines on the relief forms, the duties lines, the away notices on the exam and
event pages, a backup record in What's in, and phone width.

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
- Locks: `schedules.editing()` may be held while `relief.absences` takes its own lock (sync), never the other way round.
- Not built: messages to people on duty, the relief team's approval of a backup, a Preview of relief for a date.

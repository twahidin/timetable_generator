# Exams and events stage 4: notes

Built 21 November 2026 on branch `exams-stage-4`, stacked on `exams-stage-2` (not yet merged), subagent-driven: a builder
and a reviewer per task (seven tasks, every review clean), then a finishing task. Plan:
`2026-11-21-exams-stage-4-events.md`. Design: `../specs/2026-11-20-exams-and-events-design.md`. Stage 2:
`2026-11-21-exams-stage-2-notes.md`.

## What stage 4 gives

- **An event is a schedule of kind "event"** in the same store as exams, with the same approval states, the same main-site
  rule (only the approved copy is read) and the same "other schedules count" busy logic. It has no papers, seats or
  invigilators; its own fields are the teacher in charge, "where" (free words), the school rooms it takes (venues), the
  people going and how that list was filled, and optional duties.
- **Who starts one.** Any staff member signed in with a personal code starts an event with **+ New event** and becomes its
  teacher in charge; they and the timetable committee may change it, nobody else may open it. The timetable committee may
  also start one but must name the teacher in charge (P1). The exams committee does not manage events. Events have their
  own `/api/events` routes; the exam routes answer 404 for an event (P2). Every rights decision is in `app.py`'s helpers
  (`_event_rights` is new), so the accounts work still rewrites one place.
- **Who goes.** Four ways to fill the list: the form teachers of the chosen classes (`classes[].parents`), the teachers who
  would teach those classes during the event's windows, everyone in a department, or picked people; the teacher in charge
  adds or removes names. For each person the page says "free then" (their lessons with the event's classes stop) or that
  they have lessons with other classes (so a backup is needed), using stage 2's "free then" helper.
- **Venues.** A school room the event takes is busy for exams and other events during its windows; a lesson that uses it
  then is flagged ("{subject} with {classes} uses {room} then"), not moved.
- **The three lessons lists**, as for exams: the event classes' lessons stop (no relief needed), going teachers' lessons with
  other classes need a backup, the rest run. Sending the backups to the relief team is not built: the page says "Sending
  backups to the relief team arrives in a later stage."
- **Approval** is the same: send (needs a name, classes or levels, a day, at least one person going and no clash errors),
  approve, send back, withdraw, and changes waiting after approval. The Approval tab shows what changes on the main site
  (classes, lessons that stop, people going, rooms taken, lessons that use a taken room) and the checks.
- **Someone is away.** On an approved event the teacher in charge replaces a person going who is away; applied to both
  copies at once, logged and listed under "Done without approval".
- **The main site.** `/api/day` adds event blocks: each class on the event gets a block over the window with the event's
  name and where; each person going gets a block, and each room taken shows as busy (full readers only). Who's free counts
  people going and rooms taken as busy. The banner and the **Exams and events** tab (renamed) list events with dates,
  classes, where, and for full readers the people going and duties. **My exam and event duties** includes the events a
  teacher goes to; a student's **My exam timetable** includes the events of their class ("{event} · {where} · {from}-{to}").
- **The shared student code** sees an event's name, where and time only: no teacher in charge, no people going, no duties,
  no rooms; the staff print route answers 404 for an event.
- No model, Telegram or network call anywhere; nobody is messaged yet.

## The controller's brief: decisions (E1 to E11, and the relief note)

1. An event is a schedule with `kind: "event"` in the same store, sharing days and windows, approval, the main site and the
   other-schedules busy logic. No papers, seats or invigilators. New fields: `in_charge`, `where`, `venues`, `going`,
   `going_by` ("form teachers", "teachers then", "department", "people"; a record for the page) and `duties` (optional
   list of {duty, who, time}).
2. Who: any staff member with a personal code may start an event and becomes its teacher in charge; they and the timetable
   committee may change it, others may not open it; the exams committee does not manage events. Rights only through
   app.py helpers (a new `_event_rights(sched)`, in the pattern of `_exams_gate`).
3. Going: four ways to fill the list, the teacher in charge can add or remove names; the app shows for each person
   whether they are free then or have lessons with other classes (backup needed), through `invigilate._free` with
   `elsewhere`.
4. Venues: a school venue the event takes is busy for exams and other events during the windows; lessons that use it are
   flagged, not moved.
5. Lists: the same three lists as exams (`make.lesson_lists` shape).
6. Approval identical to exams. Send needs a name, classes or levels, a day, at least one person going and no clash errors;
   the review shows what changes on the main site and the checks (people going free then or flagged, clashes with other
   schedules).
7. Someone is away: on an approved event the teacher in charge replaces a person going who is away, applied to both
   copies, logged, listed under "Done without approval".
8. Main site: event blocks in `/api/day` as above; the student code sees name, where and time only; who's free counts
   people going and venues taken as busy; the banner and the tab cover events (tab renamed "Exams and events").
9. Own pages: "My exam duties" becomes "My exam and event duties" and includes events a teacher goes to; the student's
   "My exam timetable" includes events of their class.
10. Pages: the list shows events with the event chip; "+ New event" (any staff) opens the event editor with tabs What and
    when, Who goes, Lessons, Approval.
11. Made-up names only; tests on `exams/fake.py`'s school (a class's `parents` added to it).
- **Relief note.** Relief stage 3 (backups sent to the relief team) is not built: events show the lessons that need backup,
  as exams do, with "Sending backups to the relief team arrives in a later stage."

## Rulings

From the plan (P1 to P12 of the first review of the plan) and the pre-flight scan:

- P1: the timetable committee may also start an event but must name its teacher in charge (lets the committee, and the
  browser check, create events). If wrong, drop the committee path.
- P2: events have their own `/api/events` routes; the exam routes answer 404 for an event, so the exams committee cannot
  open or change an event through exam routes.
- K1: `E1` is defined right after `_ev_ok` at the end of the test file, not beside `A1` (tests run as they are defined).
- K2: the event `_check` resets made, papers, access, times, seating, supervision, scripts, pins and use_anyway to empty for
  an event, so a forged PUT cannot put exam items, duties or seats on the main site (tested; a forged `kind="exam"` on an
  event PUT stays "event").
- K3: an event busy in the free check reads "is on {name} then" without an empty "()"; asserted for no "()" in any free or
  clash line.
- K4: one shared helper for the "{other} ({status}) has {classes} on {date} too." sentence; the event gate, review reply
  and approval reuse the exam versions through parameters (`_exam_approval(..., event=True)`) instead of copies.
- K5: "See Exams and events" is checked, not the vacuous "See Exams"; a node case renders an event row of
  `/api/published/exams` and an event in My exam timetable.
- K6: the "off the list" aria-label text is asserted, not the vacuous "Take ".
- K7: the tests name the actor (the timetable committee approves; "that duty in both copies").
- K8: the test helper GETs the event, edits and PUTs the whole object.
- K9: an approved event's copy counts in `copies` and `busies` (asserted).
- K10: the committee cannot reassign a teacher in charge in this stage: `in_charge` is kept for everyone and a committee
  PUT of it is ignored. Open point (below).
- K11: the trailer on commits stays the plan's "Claude Opus 5.5", as stages 1 and 2.
- K12: `event_busy` covers every date from start to end including non-school dates, while `on_dates` and `day` use school
  days only. Harmless (a non-school date holds no lesson), but two date rules; noted, no code change.
- K13: `approval.changes` inserts the event kinds (where, venues, going, duties) before its early return on no made part.
- K14: `published.my_exams` handles events before the no-papers `continue`; the same for `my_duties`.

Made during the build:

- Task 3: when the working copy holds both the away person and the replacement, the away person's duties pass to the
  replacement (no orphaned duty); the brief said only that the person "just leaves".
- Task 4: a DELETE of a missing exam id now answers 404 (it was ok): a visible stage 2 change, accepted. The exam routes
  refuse an event explicitly, with a test.
- Task 5: an event with no "where" shows its school venue names as its place to students (`schedules.place`'s fallback):
  the venue is where the class goes; rooms as busy rooms stay staff-only.
- Task 6: "Going:" is left out when nobody goes (the brief gave no wording).

## Checked

### Suites (final code)

Every suite run alone one after another on the final code (the machine shared with other sessions' suites), all pass:
the 16 python suites (`test_exams`, `test_relief`, `test_typed`, `test_helper`, `test_fixes`, `test_combined`,
`test_verify`, `test_rules`, `test_choices`, `test_parents`, `test_sync`, `test_board`, `test_ask`, `test_teachers`,
`test_venues`, `smoke`), the 17 node test files, and `node --check` on `static/app.js`, `static/exams.js`,
`static/exams-settings.js` and the last script of `ttgen/timetable_page.html`; then `--full` for `test_typed`,
`test_helper`, `test_fixes` and `smoke`, each alone, all pass. The two copies of the published page, and every
`ttgen/*.py` against its skill copy, are identical. (`test_combined --full` is not in this task's list and was not run.)

### The school's real published timetable (CTSS), counts only, scratch folder deleted

The newest setup (v23) and its solver timetable file (the file stage 2 counted): 1985 lessons, 26 periods, 32 classes, no
student list, so 973 made-up students for the classes of Sec 1 to 3 by class size. A made-up term (Nov to Dec 2026) and one
made-up day, Tue 24 Nov (Even Tues).

- **Sec 2 event** (8 classes): part of the day, 08:00 to 13:00, where "Off site (museum)", one school room taken. The
  timetable has form teachers (16 on the 8 Sec 2 classes), so the going list was filled by "form teachers" (16 people) then
  "teachers then" (14 more): 30 going, in 0.002 s. Review: 38 lessons stop, 37 lessons need a backup (the 30 going: 24
  have lessons with other classes, 6 are free then), 1 room taken, rooms freed on 1 date, a "time ends in the middle of a lesson" line on 1 date, 0 venue flags, 0 clashes, the
  review's three checks all ok (0.003 s); no send errors; sent and approved through the functions.
- **Sec 3 exam** the same day (one 90-minute paper at 08:00, 41 classroom rooms, made, sent, approved): 311 student-papers
  seated, 0 unseated, 8 duties, 0 short, Make 0.05 s; after it, the event's review still had 0 clashes and no failed
  check.
- **`published.day` for the date**, staff: 97 lessons crossed out (the event's 38 and the exam's), 16 class items (8
  event, 8 exam), 46 teachers with items (30 event blocks), 9 rooms (1 event room), 14842 bytes, 1.4 ms. Student code: the
  same 97 crossed out and 16 class items (8 event), 0 teachers, 0 rooms, 3906 bytes, 1.1 ms; none of the 30 going names or
  the teacher in charge appears anywhere in the student answer.
- **`published.listing`** (`/api/published/exams`): 2926 bytes for staff, 611 for the student code (no going or in-charge
  name in it).
- **`my_duties`** of one person going: 1 schedule and 3 lessons that do not happen. **`my_exams`** of a Sec 2 student: 1
  schedule row (the event); of a Sec 3 student: 1 (the exam).
- The branch's commits hold no real staff name (205 names and short forms of the setup searched in
  `git log -p origin/main..HEAD`: 1 hit, an ordinary English word that is also a first name in the made-up school and
  appears 30 times as code text; no real name) and not the school's full name (0).

### Browser (the controller's check, made-up school, a future made-up term; launch file restored and compared equal)

- Committee: the Exams page shows "+ New event"; the form (name typed, Sec 3 ticked, dates and teacher in charge by
  form_input) then "Make it" opens `/events/<id>` with tabs What and when, Who goes, Lessons, Approval, "teacher in charge
  Ms Aisha Rahman", Odd Wed, the venues list; where typed and saved.
- Who goes: "Teachers who'd teach them then" gives "There is no one new to add." (correct: no Sec 3 lessons that Wednesday
  in the made-up school); Pick people (select by form_input, Add by a real click) gives "Added 1 person.", "Ms Aisha
  Rahman · teacher in charge · free then".
- Approval: Send, Approve gives "Approved · on the main site", what changes (classes, off site, people going 1), checks all
  clear, Withdraw offered.
- Student code: banner "Sec 3 Learning Journey: Wed 25 Nov. See Exams and events"; tab "Exams and events"; date 25 Nov reads
  "On Wed 25 Nov (Odd Wed): Sec 3 Learning Journey. Lessons that don't happen are crossed out." and the block "Sec 3
  Learning Journey · Off site (museum) · 07:40-16:20"; `/api/day` and `/api/published/exams` carry no names, no
  in_charge or going, empty teachers and rooms.

## Not tried in a browser

- A teacher (personal code) starting their own event, "Someone is away" on an event, the teacher view of the event tab,
  duties, phone width, and the printouts (personal and staff codes cannot be typed in the pane; covered by tests).
- Event editor behaviour beyond the source-word tests (the editor is exercised only by the controller's check above).

## Deferred minors

- Task 1: `lesson_lists`'s `item` closure is redefined per lesson; the `going` ternary reads badly; `_check_event` repeats
  the name check instead of `_named(s, "event")`; no multi-date event test (the "(Mon 5 Oct)" suffix, the `many`
  branch); no recorded RED run.
- Task 2: `other_lines` orders all class lines then all venue lines (the brief said per copy and date); the busies dedupe
  key drops a waiting event copy's people busy when only its classes changed (the plan's key); repeated tag filters.
- Task 3: no test of the duty hand-over branch; a working duty naming the away person is untouched when the away person is
  not in the working going; flags are computed twice in the review; `event_review` never exercises the approved copy or
  non-empty changes; the `sent_fp` re-stamp is not asserted for events; `ev9` is saved and not removed in tests.
- Task 4: `event_rights_stay_inside_helpers` asserts only that two defs exist; a committee PUT of `in_charge` being
  ignored is untested; a DELETE of a missing exam id now 404s.
- Task 5: `published._place` duplicates `schedules.place`; a dead `a, b = None, None` in `_class_items`; `day()` takes the
  first class's window while the others use min and max (the same today); untested: a personal code on `/api/day`, an empty
  where with venues, duplicate names in going, `cal=None` in `_ev_dates`.
- Task 6: an event's name shows in the My exam timetable heading and again in its row (cosmetic).
- Task 7: `links()` shows "Exam settings" to a teacher in charge before `/api/exams/me` returns (call it after); the list
  sort floats rows without `saved_at`; a dead `S.me0`; `S.msg` lingers after goPick, goDept and evReplace; the editor's
  behaviour has only source-word tests.

## For stage 3 (relief) and later

- **Relief stage 3.** The lessons that need a backup are an event's `lesson_lists["backup"]` (and the `backups` count in its
  review); relief's backup sending reads them from the approved copy, as exam duties are read. Relief's absences should
  also feed "Someone is away" on events as on exams. Events add `event` blocks to the same `/api/day` `exams` key; relief's
  layer must spread combined venues, as stage 2 noted.
- **Accounts.** `_event_rights`, `_event_gate` and the five stage 2 helpers are the places that read the role or the
  session; personal accounts rewrite them. The "teacher in charge" is a name (`in_charge`), matched to the signed-in
  person's name; an account id would be firmer. Open point (K10): the committee cannot reassign the teacher in charge once an
  event exists; add it when accounts land.
- **History.** The event's `log` and approved copy are ready for a history page with "Put back".
- Not built: a Preview on the main site for events (as for exams, P10), a typed multi-day event test, an event in the print
  pages, and a message to people going (nothing tells anyone yet).
- Date rule to keep in mind (K12): `event_busy` covers non-school dates; `on_dates` and `day` do not.

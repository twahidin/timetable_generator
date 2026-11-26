# Staff passwords: notes

Built 2026-11-26 on branch staff-passwords from main 82c0646 (plan: 2026-11-26-staff-passwords.md, spec: ../specs/2026-11-26-staff-passwords-design.md).

## Calls made while building

- Titles ("Ms", "Mr", "Dr" and so on) are dropped from usernames, so "Ms Alice Tan" gets a name like `alice.tan`.
- The slips come as a PDF with a CSV beside it, in the one answer (`Cache-Control: no-store`); the temporary password is never stored, only its hash.
- Slips are all-or-nothing, and a tick that has gone stale (the person has chosen a password meanwhile) is refused with a 409.
- A person with a username but no password counts as "no account yet".
- Shared codes are accepted on `/student`; a staff code typed there is refused like on `/login` (same message, same strike, same history reason). The POST handler is shared by `/login` and `/student`.
- There is no admin check on the Staff codes switch itself, because only a password admin can reach the Ways in tab to press it.
- Ways in rows: Student codes prints student slips; Staff codes keeps a "Print code slips" button while staff codes are on. `_ways()` also reports students, staff and staff_chosen so the row can say "7 of 99 staff".
- A teacher's Exams tab lists "Your duties" (own invigilation with room and classes) from `/api/exams/my-duties`.
- Relief pages are left as they are: changing what relief does is a spec non-goal, so relief may still show colleagues' free periods.
- Narrowing of a plain teacher's pages fails open on an unreadable accounts file, as sign-in does. Room names stay in lesson data (the spec allows).
- A plain teacher's lesson box shows other teachers' names as plain text, not links; no empty "Other" heading or "- allowance" on My timetable.

## Deferred minors

- `_check` reads the accounts file about 3 times for a code session; a lambda inside a generator in `_ways` (waiting count); no test of `_fill` with a bool or string `staff_off`; the final history test's floor is `>10`.
- CSV guard quotes a kept username starting with "-", same as relief codes.
- The generic except in staff-slips could say "nothing was changed" for a failure in the write step of `_update_as` (narrow).
- POST `/login` with a wrong code while staff codes are off redraws the code page, not the username page.
- An in-charge teacher's `/api/events/<id>/review` and `/who` show staff busy/free for their own event (pre-existing).
- Ways in tick-bar: a print error is lost if the menu was replaced meanwhile (add `note(e.message,true)`); a save-step failure reads like a server refusal; a weak `staff>=1` assert; some wording ("staffOffAsk(0)", SLIP_SAYS, "for 1 staff").

## Browser check (scratch server, made-up data, real clicks)

Tried: Ways in rows; the preview; Print saved both files (download stubbed); no password in the page text; 56 accounts made in 3.3 s server time (hashing is the cost); Turn off asked first and showed "Off since 26 Nov 2026"; `/login` became the username page with the student link; `/student` shows the code box and the staff link; a teacher by password sees My timetable (own first), Classes, Exams and events; another teacher's name in a lesson box is plain text; `/pdf/teachers/<other>` 403, own 200, rooms 403, teacher book 404.

Not tried in a browser: "Your duties" (no exams in the scratch data; covered by JS and route tests); the printed slip on paper; a real sign-in with a slip followed by choosing a password was covered by route tests (the controller's report says what else the final run showed).

## Commits (82c0646..HEAD)

- 7e8e6df feat: the Ways in tab makes accounts, prints slips and turns staff codes off
- 11d4edc fix: a teacher's Exams tab lists their own duties; the approved-exam fixture is shared, no subprocess
- c9a29cd feat: a teacher's Exams tab shows their own duties and the classes
- 2d364ea fix: a teacher's page links only what it can open; no empty heading or allowance
- d289d3b feat: teachers see their own timetable and the classes once staff codes are off
- d91a5b7 test: pin the staff code and slip routes; capture the expected slip warning
- 6d95bfa feat: a code page for students; the front page follows the staff codes switch
- b6b3ba5 fix: slips are all-or-nothing, stale ticks refused, roomier slip
- f03a412 feat: make staff accounts and print their sign-in slips
- 4d2b7e5 feat: a switch that turns staff codes off

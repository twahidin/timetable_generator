# Accounts stage 1: notes

Built 21 November 2026 on branch `accounts-stage-1`, subagent-driven (a builder and a reviewer per task, 14 tasks).
Ledger and task reports: `.superpowers/sdd/2026-11-21-accounts-stage-1-accounts-rights-history/` (not in the repository).
Design: `../specs/` (accounts and history).

## What stage 1 gives

- **One sign-in page.** A person signs in as themselves: username and password, or their personal code. The shared codes
  (committee, heads, teachers, students) still work until an admin turns them off.
- **Rights by group.** The server decides from the people's records, on every request: committee, leaders, heads (with the
  departments they change), teachers, executives, students; plus extras (Relief team, Exams and events until a date, Admin).
  Every route names the right it needs; the whole map is pinned in `tests/test_routes.py`.
- **People file** (`accounts/`): who is who, one-time passwords, a recovery code, a lock after wrong tries.
- **Admin page** (`/admin`): Staff, Students, Ways in (turn a shared code off or on), code slips, bulk changes with a preview.
- **History** (`/history`): who changed what and when, setup changes, refused changes, publishing, relief, exams, sign-ins,
  account changes; each setup entry keeps the old and new values for a later Put back.
- **Heads** change only their own departments' lines on step 5 (a refused change is skipped and reported).
- **Home page** with tiles by right (Committee page, Timetables, Relief, Exams and events, Admin, History). The Exams and
  events tile shows for the committee too, with no "Until" line.
- Relief settings and the exams committee now read from the people file (migrated once).

## Rulings made during the build (what each costs if wrong)

1. R1 `store` imports `history` inside functions: a later refactor only.
2. R2 the strong-sign-in rule binds named persons; shared codes keep today's rights: a shared committee code could not open the history.
3. R3 step 8/9 links go to the committee page with the step named in the text: a worse link only.
4. R4 a people file that exists but cannot be read is never overwritten (admin changes refuse): an admin change fails until the file is fixed by hand.
5. R5 setup history entries carry the setup row's id as `row`: Put back must read `row`.
6. R6 secrets are dropped from history except inside setup `was`/`now`/`op`: a secret pasted into a setup field would be kept (it is kept in the setup anyway).
7. R7 a stray file in the history folder must not break requests: nothing.
8. R8 a head with no departments reads but changes nothing: such a head cannot work until an admin ticks a department.
9. R9 a band name another band already has is refused (judged by trimmed name at any level): nothing.
10. R10 a head changes only provisional teachers of their own departments; a department-less one is the committee's: a head cannot tidy another department's teacher.
11. R11 refusals by `check` not recorded (no caller uses it): a future `check` caller must record its own.
12. R12 the old role names bridge in `need()` between tasks 5 and 6: removed again, nothing left.
13. R13 with an unreadable people file, person sign-ins fail closed and shared codes carry on: everyone uses shared codes until it is fixed.
14. R14 the one-time-password rule applies to password sessions only: nothing.
15. R15 recovery use and password changes are written to history: nothing.
16. R16 the Relief team extra also gives `relief.plan` and `relief.team`: relief stage 2 must call `has()`.
17. R17 main was merged into the branch before the exams move: the merge and the exams move are one piece of work.
18. R18 a non-admin on an admin route gets the app-wide 401 "Please sign in again.": the admin page treats 401 as "not for you".
19. R19 `_keep_me` reads the acting admin's counter inside the update: nothing.
20. R20 the step-4 head hint reads the setup being edited: nothing.
21. R21 test secrets grepped for in files are at least 16 hex characters: a flaky suite hides real failures.
22. R22 the one-time password is cleared on a tab switch: nothing.
23. R23 history step names follow PR #80's page words; old entries keep their stored text: older entries read differently.

## Known limits (deferred minors, grouped)

- **Accounts file:** unknown keys are dropped on read; a non-ISO exams date reads as none; an empty file counts as unreadable;
  re-adding a name with an old off-list record brings back its old group and extras; an admin can reset the only other admin and
  then drop their own Admin; recovery code strength is not checked; the same-origin check depends on `X-Forwarded-Host` on Railway.
- **Sign-in:** while the file is unreadable, a person's code gets 401 and a strike; a recovery race returns 403 with no entry.
- **History:** whole month files are read (24 months scanned for a week); one gunicorn worker assumed; some follow-ups are dropped
  under a who filter; step names are hard-coded in `history.js`.
- **Heads and bands:** a band rename plus a new band reusing the name in one save is refused; duplicate band names by the
  committee are still possible; "Move into band" offers bands holding none of the head's groups (then refused).
- **Relief settings:** a Management name with an explicit group keeps it; an extra-staff name with a record overwrites its note.
- **Admin page:** failed loads say "Loading…" or the wrong sentence; no "Saved." after some saves; "Off since" uses the UTC date;
  a partial bulk apply does not say what changed; heads with another role are dropped silently.
- **Fixes and undo:** undoing a batch records only the newest text; failure isolation is tested for fix and undo only.
- **Leftovers:** unused `static/choice-*` images; duplicated RIGHTS list in `app.py` (a test keeps it equal); test helper clean-ups.

## Not tried in a browser

- The relief settings page and the exams settings read-only committee list (checked by `node --check` and tests only).
- Some admin page paths: Ways in off/on, the bulk preview with an invalid date, radio focus in the bar menu.
- The code slips PDF (only by fetch).
- The 401 banner on the admin page, and the leave-page behaviour after a session ends.
- The Put-back-free history views on a phone width; the head's step 5 pages with a real head signed in.

## For stage 2

- **Put back** reads `changes`, `was` and `now` of a setup entry, and `row` (not `id`, which is the entry's own).
- The head's history view and each person's own history view.
- "Since you last signed in" on the home page.
- Download of the history.
- Relief stage 2 calls `has()` for `relief.plan` and `relief.team`.

## Deploy notes

- Set `SECRET_KEY` first (without it personal codes and slips are off).
- After "Deploy Latest Commit", sign in with the committee code and open `/admin/first` to make the first admin.
- The shared codes keep working until they are turned off on the admin page's **Ways in**.
- Check the same-origin refusal on admin POSTs behind Railway's proxy after the first deploy.
- (Do not deploy a commit between the old Task 6 and Task 7: both are in now.)

## Open questions for the lead

- Relief design says "IP heads" plan relief: if they are not all HOD/SH, a "plans relief" extra may be needed.
- A committee member's personal code opens exams only with the Exams extra (the committee needs the password otherwise): confirm.
- The exams settings text "The timetable committee always can." may need "... signed in with their password".

## Checked

- Every suite and every node test on the final code: see the task 14 report. `tests/test_routes.py` pins the whole route map.

# Relief stage 2: notes

Built 21 November 2026 on branch `relief-stage-2` (from origin/main cc310f4), subagent-driven: a builder and a reviewer
per task, one whole-branch review, one fix wave and its re-review. Plan: `2026-11-21-relief-stage-2-relief-requests.md`.
Design: `../specs/2026-11-20-relief-module-design.md`.

## What stage 2 gives

- **Ask for relief** (any teacher): day(s), whole day or some periods (every period offered with its time), reason,
  the teacher's lessons in that time with work for each (text, a link, files), reporting officer (remembered per person
  on that browser). Sent straight to the relief team.
- **Plan relief** (Management list and Relief team; the lead: the HODs and SHs): the colleague's lessons, each with a
  ranked "free then" list (same department and subject family first, then the department, then everyone; lightest week
  first; Flexi Adjunct and over-the-limit marks), or left open. **Planned by me** opens the same absence card; a
  **Download** of every absence in a date range (no reason, formulas neutralised).
- **My absences**: acknowledge relief someone planned, set work, mark a lesson not needed or needed after all, cancel.
  Past lessons are read-only; acknowledging stays allowed.
- **What's in** (Relief team, read-only): Coming up, Today, Earlier, Cancelled, with "new since you last looked".
- The absence reason is seen only by the absent teacher, the planner, management and the relief team. Remarks written
  for the relief team are not sent to the absent teacher.
- A shared lesson needs no relief only when another of its teachers is there (not away).

## Rulings made during the build (each also in the ledger)

1. Dates in sentences read "Sat 17 Oct", "Wed 7 Oct".
2. `absences.new(..., may_choose=False)`; only planners choose relief teachers.
3. "Absent then" reads each record's dates, periods and lessons.
4. Tests fix "today" at 12 Oct 2026.
5. Every commit carries the session's attribution line.
6. Two small tests carried from Task 1.
7. The free-then counts leave out the lesson being re-chosen.
8. The planning right is checked before anyone is looked up, so a teacher cannot probe who is free or absent.
9. Work files dropped only when no lesson lists them; timestamps in school time; overlap checked on "needed after all".
10. The download lists every absence in the range, asked ones too, "Set by" = whoever sent it.
11. The forms take today's date and the periods from the server; "Some periods" never sends a whole day.
12. The browser check ran on a temporary launch entry, removed afterwards (file compared equal).
13. The reporting officer is remembered per person; the sheet hides "Entire Class"; "teaches this subject" means the
    same subject family.
14. Remarks are left out for the absent teacher alone.
15. The final fix wave: the shared-lesson cover, the Earlier view, past lessons read-only, files kept when someone else
    attached them meanwhile, What's in faster, the team right passed from the routes.
16. **One point left open for the lead** (see below).

## Left open: one small fix recommended before the pull request

If a teacher's form shows a shared lesson as "no relief needed" (because the co-teacher was there when the page loaded)
and the co-teacher's own absence arrives before Send, the lesson is recorded "Not needed" on both, and the class has
no teacher. The fix is small: the page sends "needed" only when the person chose it, so the server decides from the
records at that moment. It needs the lead's word, because the build process allows only one fix wave.

## Checked

- Every suite on the final code (391c9c0): `test_relief_requests` 56, `test_relief` 37, `smoke` 102, `test_exams` 72,
  and every other suite and `node tests/*.test.js`.
- Browser, with real clicks, on the made-up secondary sample with a made-up term: 35 checks passed (asking with work,
  link and file; a Saturday refused; planning with a choice and an open lesson; acknowledging, work, not needed;
  overlap refused naming the first sender; cancel; What's in with "new"; an ordinary teacher without the Plan and
  What's in tabs and refused another absence; phone width). Files were attached by a script on the page's own input.
- Not tried in a browser: the final fix wave's page changes (Earlier view, officer per person, past lessons
  read-only, `known` on work saves, the shared-lesson default) — covered by tests only. The sample has no shared lesson.
- The school's real published timetable, numbers only (scratch deleted): 510 lessons over two made-up dates, the
  largest free-then list 79 people, the slowest whole day 0.20 s, no errors.
- No real staff name (96 checked) and not the school's full name in the branch.

## For the accounts work (project 3)

- Every relief permission goes through `app.relief_has(right)`, passed into `relief/web.py` with
  `init(has=..., me=..., role=...)`. Right names: `relief`, `relief.plan`, `relief.team`, `relief.settings`,
  `relief.save`. The team right reaches `absences._may_change` from the routes (`team=has("relief.team")`).
- `_gate` in `relief/web.py` accepts only the `staff` session role today; with accounts it should accept any signed-in
  person.
- The Relief team extra needs `relief.plan` and `relief.team`; the HODs, SHs and school leaders need `relief.plan`.

## For stage 3 and later

- "Reliefs I'm covering" (moved here from stage 2), the AI's picks, Approve, Today, the timetable on a date.
- Uploads are not capped per absence and files never attached are not cleaned up.
- The stored `others` keeps only co-teachers who were there; stage 3's picks may want the full list.
- An earlier absence's app-made "{them} is there" stays when the co-teacher later goes away.
- The Ask and Plan forms are near copies; the school date is read once per page load.
- Minor items from the reviews: `rule_on_day(None)` guard; ids accept any letters and digits; odd sentences for odd
  input; the "Your timetable has changed…" sentence for a file that has gone; the "chosen here" person keeps the
  primary Choose button; the Planned-by-me Lessons column narrow on a phone; `family()` merges bracketed subjects
  (ranking heading only).

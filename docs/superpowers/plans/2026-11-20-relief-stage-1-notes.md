# Relief stage 1: notes

Built 20 November 2026 on branch `relief-stage-1` (from origin/main 0308796), subagent-driven: a builder and a reviewer
per task, one whole-branch review, one fix wave and its re-review. Plan:
`2026-11-20-relief-stage-1-people-and-calendar.md`. Design: `../specs/2026-11-20-relief-module-design.md`.

## What stage 1 gives

- A **Relief** card on the front page. Each teacher signs in with a personal code (made like the personal student codes,
  from the name and `SECRET_KEY`); the same code also opens the Teacher's timetable card. Signed in, a teacher sees
  "Relief · {name}" and a line saying asking for and planning relief arrive in the next stage.
- **Relief settings** (`/relief/settings`, linked from the committee page's header): management and the relief team,
  other staff with no lessons (who get a code too), the Flexi Adjunct role (found by itself from a role that says
  "adjunct"), the rules as plain text (the school's three rules to start), the checked limits, the reporting officer
  line, the times, and the school calendar (terms with Odd/Even, holidays). The committee and the relief team can save;
  management can read through the API but has no page link.
- **Codes** for the committee: a CSV and printable slips, a page per department.

## Rulings made during the build (each also in the ledger)

1. A repeated extra-staff name says "{name} is on the staff list twice." (the plan's "already a teacher" was wrong for a
   non-teacher).
2. A save checks names against the people built with the extra staff of the same save.
3. Every commit carries the session's attribution line.
4. People with no department sort last; `personal_code` and `staff_code` share one helper (codes unchanged, pinned by a
   test).
5. Two more calendar tests (last day of a term; a term starting on a Sunday).
6. Wrong JSON types in a save give one plain sentence (400, never 500); a nameless term or holiday says "Give each term
   and holiday a name."
7. Promoted from review minors: no spreadsheet formulas in the codes CSV (refused on save, neutralised on output); role
   names stripped everywhere.
8. The browser check ran on a temporary launch entry, removed afterwards (file compared equal).
9. Final fix wave: "Give a time for {label}." for a cleared time; a staff session is not signed out in the instant a
   publish swaps folders; tab and carriage return also count as formula starters; a settings file of the wrong shape
   falls back to the defaults; names capped at 100 characters, notes at 200; "Changes not saved." shows whenever the
   form has unsaved changes.
10. Left as they are: in the instant of a publish swap, `/relief/settings` shows "Code no longer valid" and `/relief`
    goes to the sign-in page, while the session survives.

## Checked

- Every suite on the final code: see the pull request. `tests/test_relief.py` is new (37 checks).
- `test_typed.py --full` fails on this branch **and on main 0308796 alike** when two runs compete for the machine: its
  30-second solve of the sample does not finish. Run alone on the final code it passes (34 checks). Not caused by
  relief; worth a look of its own.
- Browser, with real clicks, on the made-up secondary sample: the Relief card sign-in, the home, the committee's link,
  adding a team member, a rule, a term and a holiday, Save and reload, a bad term ("Check the dates of Term 1.") keeping
  the form, a team member saving, an ordinary teacher refused, the Relief link on the timetable for staff only, four
  cards on the front page, phone width.
- The school's real published timetable, numbers only (scratch folder deleted): 111 people (94 teaching), none without a
  department, the Flexi Adjunct role found (15 people), 111 codes, all 54 school dates of a made-up term mapped to the
  10 published days, a save with a real name and a term accepted.
- The branch's commits hold no real staff name (96 checked) and not the school's full name.

## Not tried in a browser

- Five cards on the front page (with HEADS_CODE) — only from the console.
- The code downloads — only by fetch, to avoid saving a codes file.
- The "No longer on the timetable" notice, the read-only state after a team member takes themselves off the team, and
  the leave-page warning.
- The final fix wave's page change ("Changes not saved.") — checked with `node --check` only.

## For stage 2

- "Your timetable" on the Relief home opens the general teacher view, not the teacher's own timetable.
- Two relief team members saving at once: the last save wins without a warning.
- `relief/calendar.py` and `relief/codes.py` import private helpers from `ttgen` (`_split_day`, `_fit`, `_fonts`,
  `_hex`); a rename there would break relief.
- `school_day()` treats a term saved without Odd/Even (saved while the timetable had one week) as Even.
- Known limits from the design stand: a renamed teacher gets a new code; no "Monday timetable on a Wednesday" days.

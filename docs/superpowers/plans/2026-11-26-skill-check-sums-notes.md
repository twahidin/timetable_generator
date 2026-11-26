# The skill's check runs step 7's sums: notes

Design: `docs/superpowers/specs/2026-11-26-skill-check-sums-design.md`. Plan: `2026-11-26-skill-check-sums.md`.
Branch `skill-check-sums`, from main 14e50ac. Skill version 2026-11.10. Built in one session, then one independent
review of the whole branch.

## What changed

- `checks.py` is now `ttgen/checks.py`, and the skill carries the same file. `checks.py` at the root is a name for
  that module (`import checks` gives `ttgen.checks` itself, private names included), so the app, the tests and any
  branch not yet merged need no change.
- `python -m ttgen check` prints `Critical (n)` and `Warnings (n)`, both always, each line as ` - [area] text` in the
  app's own words and order. With a Choices sheet and something critical it prints whether giving way clears it.
  It ends with 1 while something critical stays, otherwise 0. Before, it always ended with 0.
- The old ` ! Day structure and rules disagree`, ` ! Fixed lessons clash` and ` ! Rule ...` lines are gone from the
  check: the same findings are in the two lists. `No input problems found.` is gone too.
- `SKILL.md` is the lead's draft of 2026-11-26, written after a good timetable was made for the school with an
  outside agent, with four small changes of the builder's:
  1. `checks.py` is named `ttgen/checks.py`;
  2. step 1 says what to do when a Choices sheet clears the critical items (solve as the sheet says);
  3. step 6: the line `N warnings, M critical` is `check-timetable`'s; `export` prints `all checks passed` or
     `N problems`;
  4. the version line says the last number counts up, so 2026-11.10 is newer than 2026-11.9 (read as a decimal it
     would look older).

## Checked against the scripts before the draft went in

The draft's statements about the scripts were each looked up on main: `lesson_domains`, `m.Minimize` and `extra_cost`
are the three places in `solve()`; `side_by_side` is in the solve result; `Teacher in two lessons (allowed that day)`
is the check's wording; `check-timetable` ends with 1 on a Must warning as well as a critical one; the Students PDF
book is written only with a Students sheet. Statements that come from the run itself (times on 2 to 4 cores, the
SQLite `disk I/O error` on a synced folder, the order of levels in a staged solve) are the lead's agent's experience
and were not tried again here.

## On the school's real workbook (the newest, 26 November; counts only)

- The moved file gives the same list as main's `checks.py`, item for item: 0 critical, 34 warnings.
- The list from the workbook as read from disk equals the list after the app's `normalise` (the skill never runs
  `normalise`).
- The skill's copy, run alone from its `scripts` folder: `Critical (0)`, `Warnings (34)` (24 classes, 10 teachers),
  the 20 typed rules listed, ends with 0.
- A scratch copy with the one Higher Mother Tongue row's Periods box emptied again (the fault of 24 November):
  `Critical (9)`, the nine class lines, ends with 1.

## Rulings

- The page's own extra warning on step 7 (rows not filled in, `unfilled_rows` in `app.py`) is not in the skill: it
  reads the page's rows, which a workbook never carries.
- The right-hand **Things to fix** panel is the page's own list and is not printed by the skill. The sums already
  cover teachers over their allowance and a lesson pattern that does not add up.
- Exit code 1 from `check` is new. An agent or a script that ran `check` and went on whatever it said now gets an
  error when the setup cannot work. That is the point, and `SKILL.md` says so.
- `check` reads the setup once and runs `findings` before anything else works the setup out, because reading a
  lesson pattern that does not add up reports it only the first time.

## Known limits

- The skill version is text. Nothing in the code compares versions; a person or an agent does. Hence change 4 above.
- A setup whose only critical items are cleared by second choices ends with 0 and the Critical list still shows
  them, with the give-way line under it. An agent that reads only the heading could stop when it need not;
  `SKILL.md` step 1 names the line.

## Not tried

- No real agent has run the new check: the lead's good timetable was made with skill 2026-11.9 and the draft's text.
- Nothing here is seen in a browser: step 7 calls the same function from its new place, and the suites cover it.

## What the lead does next

1. Say "Open the PR", then "Yes, merge it" for that pull request.
2. In Railway, CMD + K, **Deploy Latest Commit** (not Redeploy). One deploy also carries PRs #104 to #111 if they
   are not live yet.
3. After the deploy, download the skill again from step 7: it then says 2026-11.10, and its check prints the two lists.
   A workbook downloaded after the deploy names 2026-11.10 on its README sheet.

# The skill's check runs step 7's sums

Date: 2026-11-26. Size: a small change. Approved by the lead on 2026-11-26 ("add on to the skill ... plus this design
change"), with the lead's own draft of `SKILL.md` 2026-11.10.

## Why

On 2026-11-24 one row of the school's setup (a Higher Mother Tongue group whose Periods box was empty) took its
subject's 21 periods where 2 were meant. Step 7 of the app said so at once: nine classes of the level needed more
periods than the cycle holds. The skill's own first step, `python -m ttgen check`, would have printed "No input problems
found." on the same workbook, because the sums behind **Will it fit?** live in `checks.py` at the repository's root and
are not part of the skill. `SKILL.md` asked the agent to do those sums by hand.

The lead then made a good timetable for the school with an outside agent and came back with a draft of `SKILL.md`
that carries what that run taught. Both go in together.

## Goals

- `python -m ttgen check SETUP.xlsx` prints the same critical items and warnings as step 7, in the same words.
- One file holds the sums. The app and the skill cannot drift apart.
- `SKILL.md` becomes the lead's draft, version 2026-11.10.

Not goals: changing any sum, any wording of a finding, the page, or the solver.

Must not happen: step 7 showing a different list after the move; a second copy of the sums that only the skill has.

## Approaches

1. **Move `checks.py` into the `ttgen` package** (chosen). `ttgen/` and `skill/.../scripts/ttgen/` are already one
   package kept in step, so the skill gets the sums with no new mechanism. The root `checks.py` stays as a name for
   the same module, so `import checks` in the app, the tests and any branch not yet merged keeps working.
2. Copy `checks.py` into the skill only. Rejected: two copies that drift, which is the fault being fixed.
3. Only tell the agent, in `SKILL.md`, to do the sums more carefully. Rejected: it is what failed.

## The design

**The file.** `checks.py` moves to `ttgen/checks.py` (its imports become relative) and is copied to
`skill/school-timetable-generator/scripts/ttgen/checks.py`, byte for byte, as the rest of the package is. The root
`checks.py` becomes three lines that put `ttgen.checks` under the name `checks`.

**What `check` prints.** After the two lines of counts:

```
Critical (9): no timetable can be made until these are fixed
 - [classes] Class 1A1 needs 178 periods but Sec 1 has 162 lesson periods a cycle (+0 after-school): at least 16 periods must go after school.
 ...
Warnings (36): a timetable can still be made; a person should check these
 - [teachers] ... teaches 117 periods, over their allowance of 104.
 ...
```

Both headings are always printed, `Critical (0)` and `Warnings (0)` included, so an agent can tell new scripts from
old ones. The lines are `checks.findings` in its own order. The separate ` ! Day structure and rules disagree`,
` ! Fixed lessons clash` and ` ! Rule ...` lines go: the same findings are in the list. The typed rules
(` * For the agent to honour: ...`) and the second choices (` * Second choice n: ...`) follow as now.

**Second choices.** When the setup has a Choices sheet and something is critical, the check does what step 7 does
(`checks.with_fallbacks`) and prints one more line under the Critical list: either `Giving way in the committee's
order, nothing is critical after choice k: <items>.` or `Even after every second choice (n), m things will not fit.`

**How it ends.** Exit code 1 when anything is critical and no step of the second choices clears it; otherwise 0.

**`SKILL.md`.** The lead's draft as given, with two changes of mine, both small:

- one sentence in step 1 for the second-choices line above (the draft's "Any critical item: stop" would otherwise
  stop an agent whose Choices sheet already answers the problem);
- in step 6 the draft says to read the first line `N warnings, M critical` for both `export` and `check-timetable`;
  only `check-timetable` prints that line, so the sentence names it.

The version goes to 2026-11.10 in `ttgen/spec.py` (both copies), `SKILL.md`, `README.md` and the three tests that pin it.
`README.md` also says where `checks.py` now lives.

## Left out, on purpose

- The page adds one warning of its own on step 7, "rows not filled in" (`unfilled_rows` in `app.py`). It reads the
  page's unsaved rows, which a workbook never carries. Not in the skill.
- The right-hand **Things to fix** panel is the page's own list. The skill prints the sums, which already cover
  teachers over allowance and a lesson pattern that does not add up.

## Testing

- A new test: the secondary sample made critical (a class given more periods than its day holds) prints
  `Critical (n)` with that line and ends with 1; the plain sample prints `Critical (0)` and ends with 0; with a
  Choices sheet that clears it, the give-way line and 0.
- `ttgen/checks.py` and the skill's copy are the same bytes (the existing rule for the package).
- On the school's real workbook: the fixed one prints `Critical (0)`; with the one Periods box emptied again it
  prints the nine class lines. Counts only in any report.
- Step 7's list for the real workbook is the same before and after the move.
- Every suite, quick and `--full`.

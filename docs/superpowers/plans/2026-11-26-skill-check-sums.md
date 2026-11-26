# The skill's check runs step 7's sums: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `python -m ttgen check SETUP.xlsx` prints the critical items and warnings of step 7's **Will it fit?**, from one file the app and the skill share, and `SKILL.md` becomes the lead's draft 2026-11.10.

**Architecture:** `checks.py` moves into the `ttgen` package, which already exists twice as the same bytes (`ttgen/` and `skill/school-timetable-generator/scripts/ttgen/`). The root `checks.py` stays as a name for `ttgen.checks`. The `check` command prints `checks.findings` under two headings and ends with 1 when something critical stays.

**Tech Stack:** Python 3 (the repository's `.venv`), plain-assert test scripts run one by one, no new dependency.

**Spec:** `docs/superpowers/specs/2026-11-26-skill-check-sums-design.md`

## Global Constraints

- No sum and no wording of a finding changes: `checks.findings(spec)` returns the same list before and after.
- `ttgen/` and `skill/school-timetable-generator/scripts/ttgen/` stay the same bytes, file for file (`tests/test_rules.py` compares them).
- `import checks` keeps working everywhere, private names included (`checks._class_fit`, `checks._loads_and_rooms`, `checks._teacher_fit`, `checks.room_sums`).
- Both headings are always printed: `Critical (n): no timetable can be made until these are fixed` and `Warnings (n): a timetable can still be made; a person should check these`.
- Skill version `2026-11.10` in `ttgen/spec.py` (both copies), `SKILL.md`, `README.md`, and the tests that pin it (`tests/test_rules.py`, `tests/test_combined.py`, `tests/test_parents.py`).
- The public repository names the school only as "CTSS"; no real person's name in a test, a commit or a document.
- Never `git stash`, `git stash pop` or `git checkout -- <file>`; never stop a process by name.
- Commits end with `Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>`. Nothing is pushed.

## Review Focus

- A workbook read straight from disk (the skill never runs the app's `normalise`): `findings(read_template(p))` must not throw, and for the school's real workbook must equal the list step 7 makes. Test: Task 1, real-workbook step.
- A setup with a Choices sheet whose second choices clear the critical items: the check must not end with 1 and must say which choice clears it. Test: Task 1.
- A setup with a Choices sheet that does not clear them: ends with 1, says so. Test: Task 1.
- A setup with nothing wrong: `Critical (0)`, `Warnings (0)` printed, ends with 0. Test: Task 1.
- An older test that reads the check's output (`tests/test_choices.py::check_lists_the_choices`) still finds its ` * Second choice 1:` line. Covered by running that suite.

---

### Task 1: the sums in the package, and the check prints them

**Files:**
- Move: `checks.py` → `ttgen/checks.py` (`git mv`), imports made relative (`from .reader import derive`, `from .spec import ...`, `from .solver import ...`, and the three inner `from ttgen...` imports)
- Create: `checks.py` (root): a docstring, then `import sys`, `from ttgen import checks as _checks`, `sys.modules[__name__] = _checks`
- Copy: `ttgen/checks.py` → `skill/school-timetable-generator/scripts/ttgen/checks.py`
- Modify: `ttgen/__main__.py` (the `check` branch), then copy to the skill's `__main__.py`
- Test: `tests/test_check_sums.py` (new; the style of `tests/test_venues.py`: a `t` decorator, `passed`, a last line `print(f"{passed} checks passed")`)

**Interfaces:**
- Produces: `ttgen.checks.findings(spec) -> [dict(level, area, text)]`, `ttgen.checks.with_fallbacks(spec) -> dict(critical, pass_at, items)`, `CRITICAL`, `WARNING`, unchanged.
- `ttgen.__main__.main(["check", path]) -> int`: 1 when a critical finding stays (no Choices sheet, or `with_fallbacks(...)["pass_at"] is None`), else 0.

- [ ] **Step 1: Write the failing tests** in `tests/test_check_sums.py`. A helper `run(sp) -> (code, text)` writes `sp` with `template.write_template` to a temp folder and calls `main.main(["check", p])` with stdout captured.
  - `plain_sample_has_both_headings`: `secondary()` → `code == 0`; the text has a line starting `Critical (` and a line starting `Warnings (`; the counts in the headings equal the counts of `checks.findings(reader.read_template(p))` by level.
  - `an_overfull_class_is_critical_and_ends_with_1`: `secondary()` with one whole-class lesson row's `periods_override` raised by the level's whole cycle (so the class needs more than lesson plus after-school periods) → `code == 1`; a line ` - [classes] Class <that class> needs ` is under the Critical heading and above the Warnings heading; every critical finding's text is printed.
  - `the_same_words_as_the_app`: for that setup, the set of printed ` - [area] text` lines equals `{f" - [{f['area']}] {f['text']}" for f in checks.findings(...)}`.
  - `second_choices_that_clear_it`: the overfull setup made to depend on a choice (take `with_choices()`'s pattern from `tests/test_choices.py`: after-school slot No → Yes as a second choice, and a class that fits only with the after-school slots) → `code == 0`, and a line starting `Giving way in the committee's order, nothing is critical after choice 1:`.
  - `second_choices_that_do_not_clear_it`: the Task's overfull class plus that same choice → `code == 1` and a line starting `Even after every second choice (`.
  - `root_name_is_the_same_module`: `import checks; from ttgen import checks as c; assert checks is c and checks._class_fit is c._class_fit`.
  - `old_lines_are_gone`: no line starts with ` ! Fixed lessons clash`, ` ! Rule ` or ` ! Day structure and rules disagree`, and `No input problems found.` is not printed.
- [ ] **Step 2: Run** `../timetable_generator/.venv/bin/python tests/test_check_sums.py`. Expected: fails (no `ttgen.checks`).
- [ ] **Step 3: Move the file and write the root name.** Then `check` in `ttgen/__main__.py`: after the two count lines, `found = checks.findings(spec)`; print the Critical heading and its ` - [area] text` lines, the give-way line when `spec.get("choices")` and something is critical, the Warnings heading and its lines; keep the typed-rule and second-choice lines; return the code above. Give-way wording: `Giving way in the committee's order, nothing is critical after choice {k}: {"; ".join(items[:k])}.` and `Even after every second choice ({len(items)}), {m} thing{s} will not fit.`
- [ ] **Step 4: Copy** both files to the skill's package; run the new test, `tests/test_rules.py`, `tests/test_choices.py`, `tests/test_combined.py`, `tests/test_teachers.py`, `tests/test_venues.py`, `tests/smoke.py`. Expected: all pass.
- [ ] **Step 5: The real workbook** (outside the repository; counts only in any note): `findings(read_template(p))` equals `findings(normalise(read_template(p)))` on the newest setup workbook; the check prints `Critical (0)`; with the one Higher Mother Tongue row's Periods emptied in a scratch copy it prints the nine class lines and ends with 1; the list from the moved file equals the list from `origin/main`'s `checks.py`.
- [ ] **Step 6: Commit** `feat(skill): the check prints step 7's critical items and warnings`.

### Task 2: SKILL.md 2026-11.10 and the version

**Files:**
- Modify: `skill/school-timetable-generator/SKILL.md` (the lead's draft, whole file, plus the two changes the spec names)
- Modify: `ttgen/spec.py:35` and the skill's copy (`SKILL_VERSION = "2026-11.10"`)
- Modify: `README.md` (the version line near line 180; the **Will it fit?** paragraph says `ttgen/checks.py`; the paragraph on the skill says its check prints the same list)
- Modify: `tests/test_rules.py:17`, `tests/test_combined.py:361`, `tests/test_parents.py:182-184`

- [ ] **Step 1: Change the three tests** to `2026-11.10`; add to `tests/test_check_sums.py`: `skill_md_says_what_the_check_prints`: `SKILL.md` holds `Skill version: 2026-11.10`, `**Critical**`, `**Any critical item: stop.**` and `nothing is critical after choice`. Run: they fail.
- [ ] **Step 2: Put the draft in.** The added sentence in step 1 of the Workflow, after "Do not change the setup yourself.": "The one exception is a setup with a `Choices` sheet: when the check says `Giving way in the committee's order, nothing is critical after choice k`, it ends without an error and you solve as that sheet says (see **First and second choices**)." In step 6, the exit-code sentence names `check-timetable` for the `N warnings, M critical` line and says `export` prints `all checks passed` or `N problems`.
- [ ] **Step 3: Version and README.** Run the three tests and the new one. Expected: pass.
- [ ] **Step 4: Every suite**, quick then `--full` (the list in the repository's README and the notes of earlier work: `tests/test_*.py`, `tests/smoke.py`, each `tests/*.test.js` with `node`, `node --check static/app.js`).
- [ ] **Step 5: Commit** `docs(skill): SKILL.md 2026-11.10, what a real run taught; the check's list`.

### Task 3: notes

- [ ] Write `docs/superpowers/plans/2026-11-26-skill-check-sums-notes.md`: what was decided on the way, what was checked on the real workbook (counts only), what is left out on purpose, and what the lead does next (pull request, merge, Deploy Latest Commit, then download the skill again from step 7). Commit.

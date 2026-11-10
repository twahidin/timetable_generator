# Wizard stage 6b: first and second choices, and the configuration id — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The committee can give a setting, a rule or a level's recess a second choice and put the second choices in a give-way order; the order travels on a Choices sheet, `ttgen solve` and the skill give way down it, Will it fit? says how far down the list the sums pass, what comes back says which choices were used and is checked with those fallbacks applied, and every workbook carries a configuration id that Publish matches against the setup.

**Architecture:** A new top-level list `spec["choices"]` holds one row per second choice (`kind` setting | rule | recess, an `order`, and the fallback). `ttgen/choices.py` owns the vocabulary: labels, problems, applying the first k fallbacks to a copy of the setup, the Choices sheet, the `Choices used` sheet and database table, and the give-way loop `ttgen solve` runs. The app's `checks.py` runs Will it fit? on the fallbacks in order; `app.py` stamps the configuration id at download and compares it at Publish. `static/choices.js` (global `Choices`, Node-tested like `groups.js`) holds the page's pure logic; `static/app.js` draws the list on step 6, the mode and the fit result on step 7, and the choices used on step 8. The two copies of `ttgen` change together.

**Tech Stack:** Python 3.11 (openpyxl, sqlite3), Flask, vanilla JavaScript with no build step. Python tests are plain asserts like `tests/test_rules.py`; Node tests like `tests/groups.test.js`.

**Spec:** `docs/superpowers/specs/2026-11-09-setup-wizard-design.md`: "Step 6: Configuration and constraints" → "First and second choices" (all of it); "Step 7: Download" → the configuration id and "What must come back" (the agent does not change the configuration, the same configuration id, a choice used is not a change); "Step 8: Publish" (what is shown). Stage 6a's plan and notes (`2026-11-10-wizard-stage-6a-*.md`) give the shapes this builds on.

## Global Constraints

- A choice row: `{_id, kind: "setting"|"rule"|"recess", order: int, ...}` with, by kind: setting `key` (a `SETTING_RULES` key) and `second` (`"Yes"`/`"No"`, or a number for a number setting); rule `rule_id` (the rule row's `_id`; in a setup read from a workbook, `rule`: the row's index in `spec["rules"]` instead), `fallback` one of `"Prefer"`, `"Instead"`, `"Drop"`, and for Instead `instead`: a rule row (same keys as a rule, no `_id`); recess `level` and `window: ["HH:MM", "HH:MM"]`. The give-way order is `order` ascending, ties by list position. **Exactly two choices per item, one choice per item.**
- The mode is a school setting `spec["school"]["choices_mode"]`: `"fallback"` (default, "Fall back only when needed") or `"compare"` ("Make one timetable for each").
- The workbook gets a **Choices** sheet and the timetable workbook a **Choices used** sheet (`No., Item, Used, How`); the database a `choices_used` table. Workbooks without them still read. Both go in `reader.KNOWN_SHEETS`.
- Giving way never changes the setup's rows: every fallback is applied to a deep copy. A fallback not on the list, or used out of order, is a problem on Publish.
- The configuration id is `v<N>` (the setup's version at download), `v<N>+` when the downloaded setup differs from the saved one. It sits on the Settings sheet as the row **Configuration id**, in the setup as `spec["school"]["config_id"]`. The app never asks the agent for anything else about it.
- `SKILL_VERSION` becomes `"2026-11.1"`; `SKILL.md`'s version line and the README cell follow from it.
- `ttgen/` and `skill/school-timetable-generator/scripts/ttgen/` stay identical (`tests/test_rules.py` checks).
- Heads: step 6 stays read-only for a head (`locked("rules")`), and `sync.head_split` already refuses every change to a list that is not lessons, blocks or teachers, so `choices` needs no new rule: a test pins it.
- No framework, no bundler, no new package. Every change goes through `save()`; nothing is written while drawing. Names in tests, samples and docs are made up; never commit `.claude/launch.json` or `data/`.
- Wording: plain sentences, sentence case, no "please", no exclamation marks.
- Tests: `.venv/bin/python tests/test_choices.py` (new), `tests/test_rules.py`, `tests/smoke.py` (and `--full` once), `tests/test_sync.py`, `node tests/choices.test.js` (new), `groups.test.js`, `map.test.js`, `people.test.js`, `sync.test.js`, `node --check static/app.js`. Page checks against a scratch `DATA_DIR`, never the repository's `data/`; the secondary sample is the test school.
- Commit on branch `wizard-stage-6b` after each task. Do not push or open a pull request until the committee asks.

## Review Focus

1. A choice whose rule was deleted on step 6, or whose level lost its recess → the row shows what is missing, Will it fit? and `ttgen solve` skip it with a note, nothing crashes. Pinned in Tasks 1 and 5.
2. A workbook made before this change (no Choices sheet, no Configuration id row) → opens as before; Publish says the id is unknown rather than wrong. Pinned in Tasks 1 and 3.
3. A returned timetable whose Choices used list gives way on item 3 but not item 2, or names an item not on the list → both reported as problems; the check still runs with the leading second choices applied. Pinned in Task 2.
4. A floating-recess fallback whose window is shorter than the recess, or on a level that already has a recess window → flagged, not applied blindly. Pinned in Task 1.
5. The committee downloads with changes still unsent → the id ends in `+` and Publish says the workbook was downloaded with unsaved changes. Pinned in Task 3.

---

### Task 1: Choices in `ttgen`: the data, applying a fallback, the Choices sheet

**Files:**
- Create: `ttgen/choices.py`, `tests/test_choices.py`
- Modify: `ttgen/spec.py` (`SKILL_VERSION`), `ttgen/template.py` (Choices sheet, sheet order), `ttgen/reader.py` (Choices sheet, `KNOWN_SHEETS`), `ttgen/__main__.py` (`check` lists the choices), `tests/test_rules.py` (the version)
- Copy: `ttgen/` → `skill/school-timetable-generator/scripts/ttgen/` (after every task that touches `ttgen/`: `rm -rf skill/school-timetable-generator/scripts/ttgen && cp -R ttgen skill/school-timetable-generator/scripts/ttgen && find skill -name __pycache__ -exec rm -rf {} +`)

**Interfaces:**
- Produces `ttgen.choices`:
  - `KINDS = ("setting", "rule", "recess")`, `FALLBACKS = ("Prefer", "Instead", "Drop")`, `MODES = {"fallback": "Fall back only when needed", "compare": "Make one timetable for each"}`, `SHEET = "Choices"`, `USED_SHEET = "Choices used"`.
  - `ordered(spec) -> list[tuple[int, dict]]`: `(index, choice)` sorted by `order` then index, every row (valid or not).
  - `rule_index(spec, c) -> int | None`: `c["rule"]` when it is an int within range, else the index of the rule whose `_id == c["rule_id"]`, else None.
  - `item_label(spec, c) -> str`: setting → the `SETTING_RULES` label; rule → `"Rule: " + solver.rule_label(r)` for a standard rule, `"Rule: " + typed_label(n, r)` for an In words rule (n its T number); recess → `f"Recess for {level}"`; an unresolvable item → `"(missing) ..."` with what is known.
  - `first_text(spec, c) -> str`: setting → the current value as the Settings sheet shows it (`"Yes"`, `"No"`, the number, or `"no limit"`); rule → `"As written (Must)"` / `"As written (Prefer)"`; recess → `"Fixed at 9.20 to 10.00 (periods 7-8)"` from `recess_first`, `"(no fixed recess)"` when none.
  - `second_text(spec, c) -> str`: setting → `str(c["second"])`; rule → `"Make it Prefer"`, `"Drop it"`, or `"Instead: " + rule_label(c["instead"])` (for an In words rule `"Instead: " + the sentence`); recess → `"Floating between 9.00 and 11.20"` (clock text as `spec.ampm` without am/pm… use `_clock(t)`: `"9.00"`, `"11.20"`).
  - `recess_first(spec, level) -> dict | None`: `{"from": p, "to": q, "length": n, "text": ...}` of the level's R run on the first day that has one (`None` when no day has an R).
  - `problems(spec) -> list[tuple[int, str]]`: `(index, sentence)`: the rule is gone (`"The rule this choice falls back on is no longer on the setup."`); a setting key not in `SETTING_RULES`; `second` blank or equal to the first choice (`"The second choice is the same as the first."`); a recess level with no fixed recess; a window missing, unreadable, or shorter than the recess (`"The window 9.00 to 9.20 is shorter than the recess (2 periods)."`), or one that does not overlap the recess (`"The window 11.00 to 12.00 does not include the recess (9.50 to 10.30)."`); a level that already has a recess window (W) (`"Sec 1 already has a floating recess (W on Day structure)."`); Instead with no `instead` row or one with no rule; `order` missing (not a problem: treated as last).
  - `apply_all(spec, k) -> dict`: a deep copy with the first k valid choices of `ordered(spec)` applied (choices with problems are skipped). Setting: as the page's `setSetting` (after_school / pe_rain_home on `school`; a Yes/No rule row added or removed; a number rule's `number` set, or the row removed for blank/`"no limit"`). Rule Prefer: `strength = "Prefer"`. Rule Drop: the row removed, **all drops done last, highest index first**. Rule Instead: the row replaced by `dict(instead)` with `strength` from `instead` or the original. Recess: on every day of the level whose row has an R inside the window periods (`reader.periods_between(school, from, to)`), every `L` and `R` in the window becomes `W`; the Settings row `Floating recess length (periods)` is added (from `RECESS_ROWS`) with the run's length when missing or blank, left alone otherwise; `Floating recess goes by` added as `Level` when missing. The copy's `choices` list is kept.
  - `used_rows(spec, k) -> list[dict]`: `[{no, item, used, how}]` for every valid choice in order, `used` = `"Second choice"` for the first k, else `"First choice"`, `how` = `second_text` / `first_text`.
  - `mode(spec) -> str`: `"compare"` only when `school.choices_mode == "compare"`.
- Produces in the workbook: sheet **Choices** after More rules and before Rule types: A1 title `"If it does not fit, give way in this order"`, A2 note (one sentence: the agent gives way one item at a time from the top and stops as soon as a timetable fits; never on anything not listed), **A3 `"If the first choices do not fit"`, B3 the mode's text (data validation: the two texts)**, header row 5: `No., Kind, Item, First choice, Second choice, Window from, Window to, Applies to (kind), Applies to, Subject, Rule, Week, Day, From period, To period, Number, Venues, In words`; one row per choice in order (Kind `Setting` / `Rule` / `Recess`; Window columns for a recess as `h:mm AM/PM` times; the Instead columns filled only for an Instead rule, from `c["instead"]`, Venues comma-joined). Choices with problems are written too (the agent sees the committee's words; `check` flags them).
- Produces in the reader: `spec["choices"]` from the sheet: Setting rows → `key` by label (`SETTING_RULES` label prefix match as the Settings reader does), `second` from the Second choice cell (number for a number setting); Rule rows → `rule`: the index of the first rule row not yet taken whose `item_label` equals the Item cell (both trimmed), else `rule: None`; `fallback` from the Second choice cell (`Make it Prefer` → Prefer, `Drop it` → Drop, anything starting `Instead` → Instead with `instead` read from the Instead columns like a More rules row); Recess rows → `level` = Item without `Recess for `, `window` from the two time cells as `"HH:MM"`; `order` = row position; `school.choices_mode` from B3. No sheet → `choices: []`.
- Produces: `python -m ttgen check` prints, after the typed rules, `" * Second choice {n}: {item_label} — {first_text} → {second_text}"` per choice and `" ! Second choice {n}: {problem}"` for each problem.

- [ ] **Step 1: Write `tests/test_choices.py`** (header like `tests/test_rules.py`; a fixture `with_choices()` = `secondary()` plus three rules: `R1 = dict(scope="Level", target="Sec 1", rule="Not in periods", week="Both", day="All", **{"from": 20, "to": 22}, strength="Must")`, `R2 = dict(scope="School", target="Whole school", rule="In words", text="No PE in the first period", strength="Must", week="Both", day="All")`, and choices `[dict(kind="recess", level="Sec 2", window=["09:00", "11:20"], order=2), dict(kind="setting", key="after_school", second="Yes", order=1), dict(kind="rule", rule=i_R1, fallback="Instead", instead=dict(R1, **{"from": 23, "to": 25}), order=3), dict(kind="rule", rule=i_R2, fallback="Prefer", order=4)]` with the sample's `after_school` set to `False` first; `N0 = len(secondary()["rules"])`, `i_R1, i_R2 = N0, N0 + 1` as module constants) with these checks:

```python
@t
def ordered_and_labels():
    sp = with_choices(); o = choices.ordered(sp)
    assert [c["kind"] for _, c in o] == ["setting", "recess", "rule", "rule"]
    assert choices.item_label(sp, o[0][1]) == "After-school slot allowed when a class cannot fit" and choices.first_text(sp, o[0][1]) == "No" and choices.second_text(sp, o[0][1]) == "Yes"
    assert choices.item_label(sp, o[1][1]) == "Recess for Sec 2" and choices.first_text(sp, o[1][1]).startswith("Fixed at ") and choices.second_text(sp, o[1][1]) == "Floating between 9.00 and 11.20"
    assert choices.item_label(sp, o[2][1]) == "Rule: Level · Sec 1 · Not in periods" and choices.second_text(sp, o[2][1]).startswith("Instead: ")
    assert choices.item_label(sp, o[3][1]) == "Rule: T1 · Must · Whole school · No PE in the first period" and choices.second_text(sp, o[3][1]) == "Make it Prefer"

@t
def applying_the_first_k():
    sp = with_choices(); n = len(sp["rules"])
    a1 = choices.apply_all(sp, 1); assert a1["school"]["after_school"] is True and sp["school"]["after_school"] is False
    a2 = choices.apply_all(sp, 2); row = a2["day_structure"]["Sec 2"]["Odd Mon"]; assert "W" in row and "R" not in row and a2["day_structure"]["Sec 2"]["Odd Mon"] != sp["day_structure"]["Sec 2"]["Odd Mon"]
    assert any(str(x[0]).startswith("Floating recess length") and x[1] == 2 for x in a2["school"]["extra_settings"])
    a3 = choices.apply_all(sp, 3); r = a3["rules"][i_R1]; assert (r["from"], r["to"]) == (23, 25) and len(a3["rules"]) == n
    a4 = choices.apply_all(sp, 4); assert a4["rules"][i_R2]["strength"] == "Prefer" and sp["rules"][i_R2]["strength"] == "Must"
    sp["choices"][3]["fallback"] = "Drop"; a4 = choices.apply_all(sp, 4); assert len(a4["rules"]) == n - 1 and (a4["rules"][i_R1]["from"], a4["rules"][i_R1]["to"]) == (23, 25)

@t
def problems_are_found_and_skipped():
    sp = with_choices()
    sp["choices"] += [dict(kind="rule", rule=99, fallback="Drop", order=5), dict(kind="setting", key="after_school", second="No", order=6), dict(kind="recess", level="Sec 1", window=["09:00", "09:20"], order=7)]
    ps = dict(choices.problems(sp)); assert 4 in ps and "no longer on the setup" in ps[4] and "same as the first" in ps[5] and "shorter than the recess" in ps[6], ps
    assert choices.apply_all(sp, 7)["rules"] == choices.apply_all(sp, 4)["rules"]   # the bad ones change nothing
    sp["choices"][6]["window"] = ["11:00", "12:00"]; assert "does not include the recess" in dict(choices.problems(sp))[6]
    sp["day_structure"]["Sec 1"]["Odd Mon"] = sp["day_structure"]["Sec 1"]["Odd Mon"].replace("RR", "WW"); sp["choices"][6]["window"] = ["09:00", "11:20"]
    assert "already has a floating recess" in dict(choices.problems(sp))[6]
    assert [u["used"] for u in choices.used_rows(sp, 2)] == ["Second choice", "Second choice", "First choice", "First choice"] and choices.used_rows(sp, 2)[0]["no"] == 1

@t
def the_choices_sheet_round_trips():
    sp = with_choices(); sp["school"]["choices_mode"] = "compare"
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "s.xlsx"); template.write_template(sp, p)
        wb = openpyxl.load_workbook(p); ws = wb["Choices"]; assert ws["B3"].value == "Make one timetable for each" and ws.cell(6, 3).value == "After-school slot allowed when a class cannot fit"
        assert wb.sheetnames.index("Choices") == wb.sheetnames.index("More rules") + 1
        back = reader.read_template(p); got = choices.ordered(back)
        assert [c["kind"] for _, c in got] == ["setting", "recess", "rule", "rule"] and back["school"]["choices_mode"] == "compare"
        assert got[0][1]["second"] == "Yes" and got[1][1]["window"] == ["09:00", "11:20"] and got[2][1]["fallback"] == "Instead" and got[2][1]["instead"]["from"] == 23
        assert back["rules"][got[2][1]["rule"]]["rule"] == "Not in periods" and back["rules"][got[3][1]["rule"]]["rule"] == "In words"
        wb.remove(wb["Choices"]); wb.save(p); assert reader.read_template(p)["choices"] == []   # an older workbook

@t
def check_lists_the_choices():
    sp = with_choices()
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "s.xlsx"); template.write_template(sp, p); out = io.StringIO()
        with contextlib.redirect_stdout(out): main.main(["check", p])
        assert " * Second choice 1: After-school slot allowed when a class cannot fit — No → Yes" in out.getvalue(), out.getvalue()
```

- [ ] **Step 2: Run it** — `.venv/bin/python tests/test_choices.py`. Expected: FAIL, `ModuleNotFoundError: ttgen.choices`.
- [ ] **Step 3: Write `ttgen/choices.py`** with the Produces above; `set_setting(spec, key, value)` as a module function the apply step uses (the page's `setSetting` in Python). Change `SKILL_VERSION` to `"2026-11.1"`, and `tests/test_rules.py`'s assert to match.
- [ ] **Step 4: The Choices sheet in `template.py` and `reader.py`**, `KNOWN_SHEETS` += `{"Choices", "Choices used"}`, `check` in `__main__.py`.
- [ ] **Step 5: Run** `tests/test_choices.py`, `tests/test_rules.py` (after copying `ttgen/` to the skill). Expected: `5 checks passed`, `10 checks passed`.
- [ ] **Step 6: Commit** — `git add ttgen skill tests/test_choices.py tests/test_rules.py && git commit -m "ttgen: first and second choices, the Choices sheet, check lists them"`.

### Task 2: Giving way: `ttgen solve`, the Choices used sheet and table, Publish checks with the fallbacks applied

**Files:**
- Modify: `ttgen/choices.py`, `ttgen/__main__.py` (solve), `ttgen/database.py`, `ttgen/export.py` (`model_from_files`, `export_all` untouched), `skill/school-timetable-generator/SKILL.md`, `tests/test_choices.py`, `tests/test_rules.py` (`read_db` tuple length)

**Interfaces:**
- Consumes: Task 1's `ordered`, `apply_all`, `used_rows`, `mode`, `item_label`.
- Produces `ttgen.choices`:
  - `give_way(spec, run, mode="fallback") -> list[dict]`: attempts `[{k, spec, res}]`. `run(spec_k) -> res` (a solve result with `res["lessons"]`). Fallback mode: k = 0, 1, … up to the number of valid choices, stopping at the first `res` with lessons. Compare mode: every k. `k = 0` is the first choices.
  - `used_sheet(path, rows)`: adds the sheet `Choices used` (header `No., Item, Used, How`, one row each) to the workbook at `path`, replacing an existing one.
  - `used_from_rows(rows) -> list[dict]`: a `Choices used` sheet read loosely as `export.rule_report_rows` reads its sheet (title row skipped, header found by a `Used` cell, `No.`/`#` accepted, `used` normalised to `"First choice"`/`"Second choice"` from `first`/`second`/`1`/`2`/`fallback`/`given way`, anything else `""`).
  - `check_used(spec, used) -> tuple[int, list[str]]`: `k` = the number of leading choices (by `no`) marked Second choice; problems: a row whose `no` is not a choice on the list (`"Choices used names item 5, which is not on the list."`), a second choice after a first (`"Item 3 (…) was given way on while item 2 (…) was not: the agent must give way in order."`). Rows with `no` None are ignored.
- Produces: `database.write_db` writes `choices_used (no INTEGER, item TEXT, used TEXT, how TEXT)` from `m.get("choices_used")`; `read_db` returns an 8-tuple, `[7]` the rows (`[]` without the table).
- Produces: `export.model_from_files` reads `Choices used` from the workbook sheet or `db[7]`, then before `derive`: `k, probs = choices.check_used(spec, used)`; `spec = choices.apply_all(spec, k)`; after `_model` (called with the applied copy): `m["setup"]` is set back to the setup as read (first choices: the database keeps the configuration as downloaded, never the fallback copy), `m["choices_used"] = used`, `m["choice_problems"] = probs`, and `probs` are appended to `m["checks"]["problems"]` with `m["checks"]["ok"]` recomputed. A timetable that used a permitted second choice is therefore checked against the setup with it applied (a floating recess no longer reads as "sits in a break").
- Produces: `python -m ttgen solve` runs `give_way(spec, run, mode(spec))` where `run` is the existing solve (or staged solve) with `--time` per attempt; fallback mode writes `--out` from the last attempt, prints `" * Gave way on choice {n}: {item_label} ({second_text})"` for each used, adds the `Choices used` sheet, and `--export` exports it with `m["choices_used"]`; compare mode writes the first attempt to `--out` and attempt k to `<stem> - after choice {k}<ext>`, each with its sheet, and `--export` exports every attempt with lessons into `DIR/first choices` and `DIR/after choice {k}`. With no choices nothing changes (one attempt, k = 0, no sheet).
- Produces in `SKILL.md`: version line `2026-11.1`; a section **First and second choices (Choices sheet)** after Typed rules: what the sheet says; `ttgen solve` does it by itself (first choices, then one item at a time from the top, stop as soon as one fits; `Make one timetable for each` gives one workbook per step); an agent with its own solver does the same and **never gives way on anything not on the list**; hand back the `Choices used` sheet (`No., Item, Used, How`, Used = `First choice` or `Second choice`) beside the Rule report, before `ttgen export`, so the database carries it as `choices_used`; the Outputs table's database row names `choices_used`; "Building it without the scripts" step 7 gets one sentence on the Choices sheet.

- [ ] **Step 1: Add to `tests/test_choices.py`:**

```python
@t
def give_way_stops_at_the_first_fit():
    sp = with_choices(); calls = []
    def run(s): calls.append(s["school"]["after_school"]); return dict(lessons=[1] if len(calls) >= 3 else [], status="x")
    out = choices.give_way(sp, run); assert [a["k"] for a in out] == [0, 1, 2] and out[-1]["res"]["lessons"] and calls[1] is True
    calls.clear(); out = choices.give_way(sp, lambda s: dict(lessons=[1]), "compare"); assert [a["k"] for a in out] == [0, 1, 2, 3, 4]

@t
def choices_used_round_trips_and_is_checked():
    sp = with_choices(); rows = choices.used_rows(sp, 2)
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "t.xlsx"); openpyxl.Workbook().save(p); choices.used_sheet(p, rows)
        back = choices.used_from_rows(openpyxl.load_workbook(p)["Choices used"].iter_rows(values_only=True))
        assert [u["used"] for u in back] == ["Second choice", "Second choice", "First choice", "First choice"]
    assert choices.check_used(sp, back) == (2, [])
    bad = [dict(no=1, used="First choice"), dict(no=3, used="Second choice"), dict(no=9, used="Second choice")]
    k, probs = choices.check_used(sp, bad); assert k == 0 and len(probs) == 2 and "in order" in probs[0] and "not on the list" in probs[1], probs
    assert choices.used_from_rows(iter([("Choices used",), ("#", "Item", "Used", "How"), ("2", "x", "given way", "")]))[0]["used"] == "Second choice"

@t
def a_timetable_with_a_floating_recess_passes_when_the_choice_was_used():
    from ttgen import export, database
    sp = with_choices(); sp["choices"] = [sp["choices"][0]]   # only the Sec 2 recess
    with tempfile.TemporaryDirectory() as d:
        setup = os.path.join(d, "setup.xlsx"); template.write_template(sp, setup)
        ds = sp["day_structure"]["Sec 2"]; day = next(iter(ds)); row = ds[day]; p0 = row.index("R")   # a lesson placed in the fixed recess
        cls = next(c["class"] for c in sp["classes"] if c["level"] == "Sec 2"); x = next(x for x in sp["lessons"] if cls in x["classes"] and not x.get("block"))
        wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Lessons"
        ws.append(["Lesson ID", "Day", "Start period", "End period", "Periods", "Starts", "Ends", "Level", "Block", "Classes", "Subject", "Group", "Teachers", "Room", "After school", "Rain room"])
        ws.append([1, day, p0, p0, 1, "", "", "Sec 2", "", cls, x["subject"], "Entire Class", ", ".join(x["teachers"]), "", "", ""])
        tt = os.path.join(d, "t.xlsx"); wb.save(tt)
        m = export.model_from_files(setup, tt); assert any("recess" in p or "break" in p for p in m["checks"]["problems"]), m["checks"]["problems"]
        choices.used_sheet(tt, choices.used_rows(sp, 1))
        m = export.model_from_files(setup, tt); assert not any("break" in p for p in m["checks"]["problems"]) and m["choices_used"][0]["used"] == "Second choice" and m["choice_problems"] == []
        db = os.path.join(d, "t.sqlite"); database.write_db(m, db); assert database.read_db(db)[7][0]["used"] == "Second choice"
        assert "R" in database.read_db(db)[5]["day_structure"]["Sec 2"][day]   # the database keeps the downloaded setup, not the fallback copy
        m2 = export.model_from_files(None, db); assert m2["choices_used"][0]["item"] == "Recess for Sec 2"
```

- [ ] **Step 2: Run it.** Expected: FAIL, `AttributeError: give_way`.
- [ ] **Step 3: Implement** `give_way`, `used_sheet`, `used_from_rows`, `check_used`; the `solve` command; `write_db`/`read_db`; `model_from_files`. Update `tests/test_rules.py` (`len(out) == 8`). Then `SKILL.md`.
- [ ] **Step 4: Run** `tests/test_choices.py`, `tests/test_rules.py` (after the skill copy), and `.venv/bin/python -m ttgen solve` on a secondary sample workbook with one impossible first choice to watch the give-way lines once (`--time 20`; not a committed test). Expected: `8 checks passed`, `10 checks passed`.
- [ ] **Step 5: Commit** — `git commit -am "ttgen: solve gives way down the Choices list; Choices used comes back and is checked"` (add new files first).

### Task 3: The configuration id

**Files:**
- Modify: `store.py` (`config_id`), `ttgen/template.py` (Settings row), `ttgen/reader.py` (known row → `school.config_id`), `app.py` (`/api/build` stamps; `/api/import-timetable` compares), `tests/smoke.py`, `tests/test_choices.py`

**Interfaces:**
- Produces `store.config_id(spec) -> str`: `f"v{v}"` where `v` is the saved setup's version (`setup_record()["v"]`, `0` with no setup), with `"+"` appended when `_strip(spec) != _strip(saved)`; `_strip(x)` removes every key starting with `_` and the key `config_id` at every depth (a module helper).
- Produces in the workbook: Settings row `("Configuration id", sc.get("config_id") or "", "The setup's version when this workbook was downloaded. A timetable made from it carries the same id; Publish checks they match.")` right after `Timetable`; `reader` adds `"Configuration id"` to `known` and sets `sc["config_id"] = str(v).strip()` when the cell has a value (absent key otherwise).
- Produces: `POST /api/build` sets `spec["school"]["config_id"] = store.config_id(spec)` before building. `POST /api/import-timetable` replies with `config_id` (from `m["setup"]["school"].get("config_id")` or `""`), `setup_version` (`f"v{v}"`), and `config_state` one of `"same"`, `"older"` (the id parses as `v<N>` with N below the saved version), `"unsaved"` (ends in `+`), `"unknown"` (blank or unparsable), `"newer"` (N above: a different installation).

- [ ] **Step 1: Add to `tests/smoke.py`:**

```python
def test_the_workbook_carries_the_configuration_id():
    import io, openpyxl
    spec = c.get("/api/setup").get_json()["spec"]; v = c.get("/api/setup").get_json()["v"]
    wb = openpyxl.load_workbook(io.BytesIO(c.post("/api/build", json=spec).data), read_only=True)
    rows = {str(r[0]): r[1] for r in wb["Settings"].iter_rows(min_row=5, max_row=12, values_only=True) if r[0]}
    assert rows["Configuration id"] == f"v{v}", rows
    spec["school"]["name"] = "Changed School"
    wb = openpyxl.load_workbook(io.BytesIO(c.post("/api/build", json=spec).data), read_only=True)
    assert {str(r[0]): r[1] for r in wb["Settings"].iter_rows(min_row=5, max_row=12, values_only=True) if r[0]}["Configuration id"] == f"v{v}+"
```

and in `test_publish_uploaded_timetable`: after `ttgen sample primary`, open `setup.xlsx` with openpyxl and write `f"v{v}"` (the saved setup's version from `/api/setup`) into column B of the Settings row whose column A is `Configuration id`, save, then assert `j["config_id"] == f"v{v}" and j["config_state"] == "same"`. Add to `tests/test_choices.py` (Task 3 touches it too): `a_workbook_without_the_id_row_reads_without_one`: write the secondary sample, delete the Settings row `Configuration id`, read it back → `"config_id" not in back["school"]`; and with the row holding `"v7+"` → `back["school"]["config_id"] == "v7+"`.
- [ ] **Step 2: Run** `tests/smoke.py`. Expected: FAIL, `KeyError: 'Configuration id'`.
- [ ] **Step 3: Implement** `store.config_id`, the Settings row, the reader, the two routes.
- [ ] **Step 4: Run** `tests/smoke.py`, `tests/test_rules.py`, `tests/test_choices.py` (the skill copy again). Expected: all pass (smoke `31 checks passed`).
- [ ] **Step 5: Commit** — `git commit -am "The configuration id: stamped at download, matched on Publish"`.

### Task 4: The server side: sync, Will it fit? on the fallbacks, what Publish returns

**Files:**
- Modify: `sync.py` (`LISTS`, `ensure_ids`), `static/sync.js` (`LISTS`, `ensureIds`), `checks.py` (`with_fallbacks`), `app.py` (`/api/check`, `/api/import-timetable`, `pub_info`, `normalise`, `/api/build` defaults), `store.py` (`publish` meta), `tests/test_sync.py`, `tests/sync.test.js`, `tests/smoke.py`

**Interfaces:**
- Consumes: `ttgen.choices.ordered`, `apply_all`, `item_label`, `problems`.
- Produces: `"choices"` in `sync.LISTS` and `static/sync.js` `LISTS`. `ensure_ids` / `ensureIds` also **link** choices: a row with an int `rule` and no `rule_id` whose index is within `rules` gets `rule_id = rules[rule]["_id"]` (after ids are given) and loses `rule`; one out of range loses `rule` and gets `rule_id = null`. Returns true when anything changed.
- Produces `checks.with_fallbacks(spec) -> dict`: `{"critical": [n0, n1, …], "pass_at": k | None, "items": [item_label…]}`; `n_k` = critical findings of `findings(choices.apply_all(spec, k))` (a step that raises counts as its predecessor); runs only while the previous step has criticals; `pass_at` the first k with none (0 when the first choices pass).
- Produces: `POST /api/check` adds `fallbacks` (the dict above) when the setup has choices, else `fallbacks: None`.
- Produces: `POST /api/import-timetable` adds `choices_used` (`m["choices_used"]`), `choice_problems` (`m["choice_problems"]`) and `choices` (the number of valid choices on the saved setup). `store.publish` keeps `choices_used`, `choice_problems` and `config_id` in meta.json; `pub_info` returns all three.
- Produces: `normalise` and `/api/build` `setdefault("choices", [])`.

- [ ] **Step 1: Tests.** `tests/test_sync.py`: `ensure_ids` on `{"rules": [{"rule": "In words"}], "choices": [{"kind": "rule", "rule": 0}, {"kind": "rule", "rule": 7}]}` → both choices have `_id`, the first `rule_id == rules[0]["_id"]`, the second `rule_id is None`, neither has `rule`; `head_split` refuses `["add", "choices", {...}]` with a sentence containing `choices`. `tests/sync.test.js`: the same linking case through `Sync.ensureIds`. `tests/smoke.py`: `test_check_tries_the_fallbacks_in_order`: take the saved sample spec; pick a Sec 1 class and a whole-class subject it has (a lesson row with that class and no block); add the rule `dict(scope="Class", target=cls, subject=subj, rule="Fixed at", level="Sec 1", week="Odd", day="Fri", **{"from": NP - 1}, strength="Must")` (the last period of Friday is no school in the sample, so `structure_vs_rules` makes it critical: "can never be met") and a choice `dict(kind="rule", rule=<its index>, fallback="Drop", order=1)`; POST `/api/check` → `j["critical"] > 0`, `j["fallbacks"]["critical"][0] >= 1`, `j["fallbacks"]["pass_at"] == 1` and `j["fallbacks"]["items"][0].startswith("Rule: Class · ")`; and `test_publish_uploaded_timetable` adds a `Choices used` sheet (`["No.", "Item", "Used", "How"], [1, "x", "First choice", ""]`) and asserts `j["choices_used"][0]["used"] == "First choice"` and the status reply's `published["choices_used"]` matches.
- [ ] **Step 2: Run** `tests/test_sync.py`, `node tests/sync.test.js`, `tests/smoke.py`. Expected: FAIL on the new checks only.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the three again plus `tests/test_choices.py`. Expected: all pass.
- [ ] **Step 5: Commit** — `git commit -am "Server: choices sync and link, Will it fit? down the give-way order, choices used on Publish"`.

### Task 5: `static/choices.js`: the page's pure logic

**Files:**
- Create: `static/choices.js`, `tests/choices.test.js`
- Modify: `static/index.html` (load `choices.js` after `groups.js`)

**Interfaces:**
- Produces global `Choices` (and `module.exports`), every function taking `spec` and, where settings are involved, `SET` (the array `S.meta.setting_rules`: `{key, label, number, rule}`):
  - `ordered(spec) -> [{i, c}]` (as Python, by `order` then index).
  - `ruleLabel(r)` = `solver.rule_label`; `typedNo(spec, i)` the T number of rule i.
  - `itemLabel(spec, c, SET)`, `firstText(spec, c, SET)`, `secondText(spec, c)`: the same strings as Python's (`"Rule: Level · Sec 1 · Not in periods"`, `"Recess for Sec 2"`, `"Floating between 9.00 and 11.20"`).
  - `ruleIndex(spec, c)`: by `rule_id`.
  - `settingValue(spec, SET, key)`: the current value as `first_text` shows it (`"Yes"`, `"No"`, a number, `""` for no limit).
  - `recessFirst(spec, level) -> {from, to, length, text} | null`.
  - `problems(spec, SET) -> {i: [sentence]}` with Python's sentences (Review Focus 1 and 4).
  - `candidates(spec, SET) -> {settings: [key], rules: [i], levels: [level]}`: items without a choice yet; `rules` leaves out the rows that stand for a Settings row (a Must rule matching a `SET` entry's `rule` on scope and rule, and on target for Department) since those are settings; `levels`: those with a fixed recess and no W.
  - `newSetting(spec, SET, key, second) -> {i} | {error}` (`"Pick the setting."`, `"Give the second value."`, `"The second choice is the same as the first."`, `"… already has a second choice."`), `newRule(spec, ruleId, fallback, instead) -> {i} | {error}` (Instead: `instead` defaults to a copy of the rule without `_id`), `newRecess(spec, level, from, to) -> {i} | {error}` (`"Give the window as two times."`, the shorter-than-recess sentence). Each appends `{kind, order: max order + 1, …}` to `spec.choices` (created when missing).
  - `move(spec, i, dir) -> boolean`: dir -1/+1 swaps the row with its neighbour in `ordered` and renumbers every `order` 1..n.
  - `moveTo(spec, i, before) -> boolean`: puts row i just before row `before` in the order (`before` null: last) and renumbers 1..n; false when nothing changes.
  - `prune(spec) -> number`: removes choices whose rule is gone (`rule_id` not among `rules`), returns how many.

- [ ] **Step 1: Write `tests/choices.test.js`** with a fixture (a two-level school with day rows holding `RR`, `after_school: false`, two rules with `_id`s, `SET` as the meta gives it) and cases: labels and texts for the three kinds; `candidates` leaves out items that have a choice; `newSetting` refuses the same value and a second choice on an item that has one; `newRecess` refuses a short window and a level with no recess; `newRule("Instead")` copies the rule; `move` renumbers 1..n and refuses to move the first up; `moveTo` puts a row before another and last; `prune` after deleting a rule; `problems` sentences match Python's. Run: `node tests/choices.test.js`. Expected: FAIL, `Cannot find module`.
- [ ] **Step 2: Write `static/choices.js`** (the `Groups` module's style); add the script tag.
- [ ] **Step 3: Run** `node tests/choices.test.js`. Expected: `N cases passed`.
- [ ] **Step 4: Commit** — `git add static/choices.js tests/choices.test.js static/index.html && git commit -m "Choices module: labels, candidates, new choices, order, problems"`.

### Task 6: The page: step 6 list, step 7 mode and fit, step 8 choices used and the id

**Files:**
- Modify: `static/app.js`, `static/style.css`

**Interfaces:**
- Consumes: `Choices.*` (Task 5), `/api/check` `fallbacks` (Task 4), `/api/import-timetable` and `pub_info` fields (Tasks 3 and 4).
- Produces on **step 6**, a third card after Constraints: `<h2>If it does not fit, give way in this order</h2>` with a lead sentence (one item at a time, from the top; the agent stops as soon as a timetable fits), a table `table.giveway` whose rows are draggable (`draggable="true"`, `data-cdrag="i"`; a drop on another row calls `Choices.moveTo(spec, i, thatRow)`, below the table `moveTo(spec, i, null)`; `dataTransfer` text/plain as the map's drags) with ▲ ▼ buttons too (`data-cmove="i|-1"` / `"i|1"`, for keyboards and the tests) and columns `#`, Item, First choice, Second choice, ✕ `data-del="choices.i"`: the Second choice cell is editable in place — setting: `select`/`number` bound to `spec.choices.{i}.second`; rule: `select` of `Make it Prefer / Use this instead / Drop it` bound to `spec.choices.{i}.fallback`, and for Instead a second row (`tr.instead`) with the rule's changeable fields bound to `spec.choices.{i}.instead.<field>` (standard rule: Subject, Week, Day, From, To, Number, Venues as `moreRow` draws them; In words: the sentence); recess: two `type="time"` inputs bound to `spec.choices.{i}.window.0` / `.1`. Problems from `Choices.problems` show under the row (`tr.rowmsg`) and join `issues()` under key `choices` (critical: none; the right-hand panel lists them with `stepAt("choices")` → step 6). Below the table, `+ Add a second choice` opens an inline form (`CF` state like `R6`: `{open, kind, key, rule, level, second, fallback, from, to}`): kind (A setting / A rule / A level's recess) → the item (`Choices.candidates`) → the second choice fields → **Add** (`Choices.newX`, error as a toast) / Cancel. `addRow`'s `del` handler calls `Choices.prune` after a rule is deleted.
- Produces on **step 7**: the stat `<b>N</b> second choice(s)`; in card 1 a line `If the first choices do not fit:` with two radios bound to `spec.school.choices_mode` (`fallback` default, `compare`) and their one-line meanings; `paintFit` adds, when `j.fallbacks` exists and `j.critical > 0`: `pass_at === null` → `<p class="issue crit">Even after every second choice (N), M things will not fit.</p>`; `pass_at = k ≥ 1` → `<p class="issue soft">With the first choices, M things will not fit. Giving way in your order, the sums pass after choice k: item1; item2.</p>`; `starterPrompt()` adds, when there are choices, the sentence on the Choices sheet (try the first choices; give way one item at a time from the top; stop at the first fit; never on anything not on the list; hand back the Choices used sheet beside the Rule report) and, in compare mode, "Make one timetable for each step of the list."
- Produces on **step 8**: `choicesUsedHTML(used, problems, n)`: nothing when `!used.length && !n`; `No Choices used list came back. The setup has N second choices; the timetable was checked against the first choices.` as an issue when the list is empty; else `<h3>Choices used</h3>` and one line per row: `Recess for Sec 2: second choice, floating between 9.00 and 11.20` (`item` + `: ` + `used` lower-cased + (`how` ? `, ` + how lower-cased first letter : "")), each problem as `<p class="issue">`. A configuration line above the rule report in `importHTML`: `config_state` same → `<p class="okmsg">Made from this configuration (v12).</p>`; older → `<p class="issue">Made from configuration v12; the setup is now v19. Changes since then are not in this timetable.</p>`; unsaved → `… was downloaded with unsaved changes (v12+) …`; unknown → `<p class="muted small">The timetable does not say which configuration it was made from (an older workbook).</p>`; newer → `… v30 is newer than this setup's v19: it was made from another copy.` `paintPublished` shows the same choices-used block and `Made from configuration v12` from `p.config_id`.
- CSS: `table.giveway td.item{min-width:260px}`, `tr.instead td{background:var(--soft-bg)…}` (reuse existing tokens), `.giveway button.small` for the arrows, `.cf` for the add form row.

- [ ] **Step 1: Draw step 6** (`render()` → `rules()` returns the third card), the events (`data-cmove`, the `CF` form, `del` → prune), `issues()` key `choices`, `stepAt("choices")`. `node --check static/app.js`.
- [ ] **Step 2: Step 7 and step 8** as above.
- [ ] **Step 3: Browser check** against a scratch `DATA_DIR` on the secondary sample (a temporary launch.json entry, removed afterwards): add a recess choice for Sec 2 (9.00 to 11.20), a setting choice (after-school slot No → Yes after setting it to No), an Instead choice on a rule; move one up and down with the arrows and one by drag (synthetic drag events as in stage 5); set the mode to compare; open step 7 and read the fit card (make the first choices fail: a Sec 1 Not in periods over the day, with a Drop choice, then see "the sums pass after choice k"); copy the prompt; download the workbook and open it with openpyxl to see the Choices sheet and the Configuration id row; on step 8, upload a timetable workbook with a Choices used sheet (made with `ttgen solve` on the downloaded workbook, `--time 60`) and read the choices-used lines and the configuration line. Screenshots of step 6 and step 7 for the committee.
- [ ] **Step 4: Run** every suite (Global Constraints). Expected: all pass.
- [ ] **Step 5: Commit** — `git commit -am "Step 6 give-way list, step 7 mode and fit on the fallbacks, step 8 choices used and the configuration id"`.

### Task 7: README and the notes

**Files:**
- Modify: `README.md` ("What the setup can say": a **First and second choices (step 6)** paragraph after Typed rules; the Download and Publish sections mention the mode, the Choices sheet, the configuration id and the choices used; the heads' row unchanged), `docs/superpowers/plans/2026-11-10-wizard-stage-6b-notes.md` (new: rulings, deferred minors, not exercised in a real browser, as the 6a notes).

- [ ] **Step 1: Write both.**
- [ ] **Step 2: Commit** — `git commit -am "README: first and second choices, the configuration id; stage 6b notes"`.

## Not in this plan

- More than two choices per item; choices for who teaches what or room allocation; the app choosing between the compared timetables (the committee does).
- Enforcing typed rules, or the agent's "add the constraint your solver needs" gap (noted in the 6a notes).
- Project 2's verification beyond what Publish already checks here.

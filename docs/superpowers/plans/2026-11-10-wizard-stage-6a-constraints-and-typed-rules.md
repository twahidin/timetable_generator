# Wizard stage 6a: constraints under tabs, and typed rules — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Step 6 shows the constraints under five tabs (School · Levels and classes · Subjects · Venues · Teachers), each with its standard rules and a table of typed rules in plain words, and the typed rules travel to the outside agent (workbook, `ttgen check`, `SKILL.md`, a starter prompt) and come back as a rule report the app keeps and shows on Publish.

**Architecture:** A typed rule is an ordinary rule row with `rule: "In words"` and the sentence in `text`; nothing else in the data changes. `ttgen` learns the rule type (never enforced, listed by `check`, written to and read from a new "In words" column on the More rules sheet) and a `Rule report` that comes back (a sheet in the Lessons workbook, a table in the database). `static/app.js` regroups step 6 into tabs by each rule's scope and adds the typed-rules table, a starter prompt on step 7 and the rule report on step 8. The two copies of `ttgen` (`ttgen/` and `skill/school-timetable-generator/scripts/ttgen/`) change together and a test keeps them identical.

**Tech Stack:** Python 3.11 (openpyxl, sqlite3), Flask, vanilla JavaScript with no build step. Python tests are plain asserts like `tests/test_sync.py`.

**Spec:** `docs/superpowers/specs/2026-11-09-setup-wizard-design.md`: "Step 6: Configuration and constraints" (Constraints, typed rules, "How typed rules are stored and handed over"; *not* "First and second choices", which is stage 6b) and "Step 7: Download" ("A starter prompt", "What must come back": the rule report and the skill version line; *not* the configuration id, left for 6b).

## Global Constraints

- The typed rule's storage is fixed by the spec: a rule row with `rule: "In words"`, the sentence in `text`, `strength` Must or Prefer, `scope` one of School, Level, Class, Subject, Room, Teacher and `target` from the same lists as other rules. The workbook's More rules sheet gets the sentence in a new "In words" column; **older workbooks without the column still read**.
- `ttgen` does not enforce typed rules. `python -m ttgen check` lists them as "for the agent to honour". The solver skips them without a word.
- `ttgen/` and `skill/school-timetable-generator/scripts/ttgen/` stay identical: change one, copy to the other, and `tests/test_rules.py` fails when they differ (ignoring `__pycache__`).
- `SKILL.md` gets a version line `Skill version: 2026-11` (the value in `ttgen.spec.SKILL_VERSION`), and the workbook's README sheet names the version it needs.
- The Configuration card on step 6 (settings) is not changed. The rule rows the settings stand for stay on the Configuration card, never on a tab.
- Heads: step 6 stays read-only for a head (`locked("rules")`), as today. Nothing here is a heads' change.
- No framework, no bundler, no new package. Every change to the setup goes through `save()`; nothing is written while drawing.
- Names, codes and classes in tests, samples and docs are made up. The repository is public: never commit `.claude/launch.json` or `data/`.
- Wording: plain sentences, sentence case, no "please", no exclamation marks. Step numbers stay today's.
- Tests: `.venv/bin/python tests/test_rules.py` (new), `.venv/bin/python tests/smoke.py` (and `--full` once, for the publish round trip), `.venv/bin/python tests/test_sync.py`, `node tests/groups.test.js`, `node tests/map.test.js`, `node tests/people.test.js`, `node tests/sync.test.js`, `node --check static/app.js`. Page checks in the browser preview against a scratch `DATA_DIR`, never the repository's `data/`; the secondary sample is the test school.
- Commit on branch `wizard-stage-6a` after each task. Do not push or open a pull request until the committee asks.

## Review Focus

1. A workbook made before this change (no "In words" column on More rules) → opens as before; every More rules row reads with the same fields; a row whose Rule cell says "In words" reads with an empty sentence. Pinned in Task 1.
2. A typed rule with no sentence → flagged on step 6 and by `ttgen check` ("Write the rule in words"), never handed over as an empty line the agent has to guess at. Pinned in Tasks 1 and 3.
3. A returned timetable with no Rule report (an agent that ignored the instruction) → the check and the publish work as today, and when the setup has typed rules the page says "No rule report came back". Pinned in Tasks 2 and 4.
4. A Rule report whose rows do not match the setup's typed rules (fewer, more, or renumbered) → shown as returned, with a line "The setup has N typed rules; the report has M." Pinned in Tasks 2 and 4.
5. `ttgen/` and the skill's copy drifting apart → `tests/test_rules.py` fails. Pinned in Task 1.

---

### Task 1: The "In words" rule type in `ttgen`

**Files:**
- Modify: `ttgen/spec.py`, `ttgen/template.py`, `ttgen/reader.py`, `ttgen/solver.py` (`rule_problems` only), `ttgen/__main__.py`
- Create: `tests/test_rules.py`
- Copy: `ttgen/` → `skill/school-timetable-generator/scripts/ttgen/` (after the change; `cp -R` then remove `__pycache__`)

**Interfaces:**
- Produces: `ttgen.spec.TYPED = "In words"`, `ttgen.spec.SKILL_VERSION = "2026-11"`, and a new entry at the end of `RULE_TYPES`: `("In words", "School, Level, Class, Subject, Room, Teacher", "N", "N", "A rule in plain words that the list cannot say. The timetable scripts do not enforce it: the agent honours a Must, tries a Prefer, and reports how each was met.", "Level · Sec 1 · No PE in the first period")`.
- Produces: `ttgen.spec.typed_rules(spec) -> list[tuple[int, int, dict]]` — `(number, index, rule)` for every rule row with `rule == TYPED`, numbered 1, 2, 3… in `spec["rules"]` order; and `ttgen.spec.typed_label(number, rule) -> str` — `"T1 · Must · Sec 1 · No PE in the first period"` (`number`, `strength`, `target`, `text`, joined with " · "; a blank `target` is left out).
- Produces: the More rules sheet has the column **"In words"** as data column 13 (M), after Note; the Times and Check formulas move to N and O (`RIN = set(range(1, 14))`, `B.paint(rw, rL, RIN, 15)`); the Check formula adds `IF(AND(D{r}="In words",M{r}=""),"Write the rule in words. ","")`; the README sheet gets, in row 4, `Made for timetable skill version 2026-11: use SKILL.md with that version line.`
- Produces: `ttgen.reader.read_template` reads `text` from the "In words" cell when the column exists (`x.get("In words")`), else `""`, for every More rules row; rows keep every other field as today.
- Produces: `rule_problems` says `"Write the rule in words: without them this row says nothing."` for an In words row with a blank `text`, after the scope and target checks; the solver's constraint builder ignores In words rows.
- Produces: `python -m ttgen check` prints, after the rule problems, one line per typed rule: ` * For the agent to honour: <typed_label>`.

- [ ] **Step 1: Write `tests/test_rules.py`** (plain asserts, prints `N checks passed`; it imports `ttgen` from the repository root like `tests/test_sync.py` imports `sync`):

```python
"""Plain-assert tests for typed rules and the rule report: .venv/bin/python tests/test_rules.py"""
import io, os, sys, tempfile, contextlib, filecmp, sqlite3
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, ROOT)
from ttgen import spec as S, reader, template, solver, __main__ as main
from ttgen.samples import secondary
import openpyxl
n = 0
def t(f): global n; f(); n += 1
TYPED = {"scope": "Level", "target": "Sec 1", "rule": "In words", "text": "No PE in the first period", "strength": "Must", "week": "Both", "day": "All"}
BLANK = {"scope": "Class", "target": "1A", "rule": "In words", "text": "", "strength": "Prefer", "week": "Both", "day": "All"}

def with_typed():
    sp = secondary(); sp["rules"] = list(sp.get("rules", [])) + [TYPED, BLANK]; return sp

@t
def the_rule_type_exists():
    assert S.TYPED == "In words" and S.SKILL_VERSION == "2026-11"
    row = next(r for r in S.RULE_TYPES if r[0] == "In words"); assert row[1] == "School, Level, Class, Subject, Room, Teacher" and row[2] == "N" and row[3] == "N"
    assert S.typed_rules(with_typed())[0][0] == 1 and S.typed_rules(with_typed())[1][0] == 2
    assert S.typed_label(1, TYPED) == "T1 · Must · Sec 1 · No PE in the first period"
    assert S.typed_label(2, dict(TYPED, target="")) == "T2 · Must · No PE in the first period"

@t
def a_typed_rule_round_trips_through_the_workbook():
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "s.xlsx"); template.write_template(with_typed(), p)
        wb = openpyxl.load_workbook(p); ws = wb["More rules"]
        assert "In words" in [ws.cell(r, 13).value for r in range(1, 8)]   # the header row is within the sheet's first rows
        assert any(ws.cell(r, 13).value == "No PE in the first period" for r in range(1, 40))
        assert "2026-11" in str(wb["README"]["A4"].value)
        back = reader.read_template(p); got = [r for r in back["rules"] if r.get("rule") == "In words"]
        assert [(r["scope"], r["target"], r["text"], r["strength"]) for r in got] == [("Level", "Sec 1", "No PE in the first period", "Must"), ("Class", "1A", "", "Prefer")], got

@t
def an_older_workbook_without_the_column_still_reads():
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "s.xlsx"); template.write_template(with_typed(), p)
        wb = openpyxl.load_workbook(p); ws = wb["More rules"]; ws.delete_cols(13); wb.save(p)   # the column is gone, as in an older workbook
        back = reader.read_template(p); got = [r for r in back["rules"] if r.get("rule") == "In words"]
        assert len(got) == 2 and all(r["text"] == "" for r in got) and got[0]["target"] == "Sec 1"
        assert len([r for r in back["rules"] if r.get("rule") == "Not in periods"]) == len([r for r in secondary()["rules"] if r.get("rule") == "Not in periods"])

@t
def check_lists_typed_rules_and_flags_an_empty_one():
    sp = with_typed(); reader.derive(sp); P = solver.Problem(sp)
    probs = dict(solver.rule_problems(sp, P)); i_blank = len(sp["rules"]) - 1; i_typed = i_blank - 1
    assert i_typed not in probs and probs[i_blank].startswith("Write the rule in words"), probs
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "s.xlsx"); template.write_template(sp, p); out = io.StringIO()
        with contextlib.redirect_stdout(out): main.main(["check", p])
        text = out.getvalue(); assert " * For the agent to honour: T1 · Must · Sec 1 · No PE in the first period" in text, text
        assert "Write the rule in words" in text

@t
def the_skill_copy_is_identical():
    a, b = os.path.join(ROOT, "ttgen"), os.path.join(ROOT, "skill", "school-timetable-generator", "scripts", "ttgen")
    def files(root): return sorted(os.path.relpath(os.path.join(dp, f), root) for dp, dn, fn in os.walk(root) if "__pycache__" not in dp for f in fn if not f.endswith(".pyc"))
    assert files(a) == files(b), (files(a), files(b))
    diff = [f for f in files(a) if not filecmp.cmp(os.path.join(a, f), os.path.join(b, f), shallow=False)]
    assert not diff, diff

print(f"{n} checks passed")
```

- [ ] **Step 2: Run** `.venv/bin/python tests/test_rules.py` → fails at the first check with `AttributeError: module 'ttgen.spec' has no attribute 'TYPED'`.
- [ ] **Step 3: Implement** the Interfaces in `spec.py`, `template.py`, `reader.py`, `solver.py` (`rule_problems`: after the target check, `if rule == TYPED: if not str(r.get("text") or "").strip(): say(...); continue`) and `__main__.py` (the check loop). Then `rm -rf skill/school-timetable-generator/scripts/ttgen && cp -R ttgen skill/school-timetable-generator/scripts/ttgen && find skill -name __pycache__ -exec rm -rf {} +`.
- [ ] **Step 4: Run** `.venv/bin/python tests/test_rules.py` → `5 checks passed`; `.venv/bin/python tests/smoke.py` → still `30 checks passed` (the smoke's `test_ids_do_not_reach_the_workbook` reads the template: no change expected).
- [ ] **Step 5: Commit** — `git add ttgen skill/school-timetable-generator/scripts/ttgen tests/test_rules.py && git commit -m "Typed rules: the In words rule type, its workbook column, and check listing them for the agent"`

---

### Task 2: The rule report comes back

**Files:**
- Modify: `ttgen/export.py`, `ttgen/database.py`, `app.py` (`import_timetable`, `pub_info`), `store.py` (`publish`), `skill/school-timetable-generator/SKILL.md`, `tests/test_rules.py`, `tests/smoke.py` (the `--full` publish check)
- Copy: `ttgen/` → the skill's copy again.

**Interfaces:**
- Consumes: `spec.TYPED`, `spec.typed_rules`, `spec.SKILL_VERSION`.
- Produces: `ttgen.export.RESULTS = ("Met", "Partly", "Not met")` and `ttgen.export.rule_report_rows(rows) -> list[dict]` — `rows` is an iterable of row tuples whose first row is the header; headers matched by lower-cased start: `no`, `must`, `applies`, `rule`, `result`, `how`; each returned dict is `{"no": int|None, "strength": str, "applies": str, "rule": str, "result": "Met"|"Partly"|"Not met"|"", "how": str}` with `result` normalised (any case; "partly met", "partial" → "Partly"; "not met", "no", "unmet" → "Not met"; "met", "yes" → "Met"; anything else → ""); blank rows skipped.
- Produces: `model_from_files` sets `m["rule_report"]` from a `Rule report` sheet of the Lessons workbook (`rule_report_rows(ws.iter_rows(values_only=True))`), or from the database's `rule_report` table, else `[]`.
- Produces: `database.write_db` writes `CREATE TABLE rule_report (no INTEGER, strength TEXT, applies TEXT, rule TEXT, result TEXT, how TEXT)` from `m.get("rule_report")`; `database.read_db` returns a 7-tuple, the last element the list of dicts (`[]` when the table is missing). `model_from_files` and any other caller of `read_db` take the seventh element.
- Produces: `/api/import-timetable` returns `rule_report` (the list) and `typed` (the count of typed rules in the saved setup, `len(spec.typed_rules(saved))`, 0 when there is no saved setup); `store.publish` writes `rule_report` into `meta.json`; `pub_info` returns `rule_report` (list, `[]` when none).
- Produces: `SKILL.md` gains, in the front matter block's line after the title, `Skill version: 2026-11`; a section **"Typed rules (In words)"** after "Rules come from four places": they are on More rules with Rule = In words and the sentence in the In words column; `check` lists them; honour every Must, try every Prefer, and never drop or reword one silently; and a **Rule report** that must come back: a sheet named `Rule report` in the Lessons workbook with columns `No., Must / Prefer, Applies to, Rule, Result, How` (Result one of Met, Partly, Not met; How one sentence), one row per typed rule in `check`'s order; `ttgen export` carries it into the database as the `rule_report` table. The hand-over format paragraph and "Building it without the scripts" step 7 both point at it; the table of sheets gets the In words column.

- [ ] **Step 1: Add the failing checks to `tests/test_rules.py`** (before the final `print`):

```python
@t
def rule_report_rows_are_read_loosely():
    from ttgen import export
    rows = [("No.", "Must / Prefer", "Applies to", "Rule", "Result", "How"), (1, "Must", "Sec 1", "No PE in the first period", "MET", "PE never starts at period 0."),
            (2, "Prefer", "1A", "Art after recess", "partly met", "Three of four lessons."), (None, None, None, None, None, None), ("3", "Must", "", "Hall free on Fri", "nope", "")]
    got = export.rule_report_rows(iter(rows))
    assert [(r["no"], r["strength"], r["result"]) for r in got] == [(1, "Must", "Met"), (2, "Prefer", "Partly"), (3, "Must", "")], got
    assert got[0]["how"] == "PE never starts at period 0." and got[2]["applies"] == ""

@t
def the_database_carries_the_rule_report():
    from ttgen import database
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "t.sqlite"); con = sqlite3.connect(p)
        con.execute("CREATE TABLE lessons (id INTEGER PRIMARY KEY, day TEXT, start_period INTEGER, periods INTEGER, subject TEXT, classes TEXT)")
        con.execute("INSERT INTO lessons VALUES (1, 'Odd Mon', 3, 2, 'Art', '1A')")
        con.execute("CREATE TABLE rule_report (no INTEGER, strength TEXT, applies TEXT, rule TEXT, result TEXT, how TEXT)")
        con.execute("INSERT INTO rule_report VALUES (1, 'Must', 'Sec 1', 'No PE in the first period', 'Met', 'Never at 0.')"); con.commit(); con.close()
        out = database.read_db(p); assert len(out) == 7 and out[6] == [dict(no=1, strength="Must", applies="Sec 1", rule="No PE in the first period", result="Met", how="Never at 0.")], out[6]
        con = sqlite3.connect(p); con.execute("DROP TABLE rule_report"); con.commit(); con.close()
        assert database.read_db(p)[6] == []

@t
def the_skill_says_its_version_and_asks_for_the_report():
    md = open(os.path.join(ROOT, "skill", "school-timetable-generator", "SKILL.md"), encoding="utf-8").read()
    assert "Skill version: 2026-11" in md and "Rule report" in md and "In words" in md and "Not met" in md
```

- [ ] **Step 2: Run** `.venv/bin/python tests/test_rules.py` → fails with `AttributeError: module 'ttgen.export' has no attribute 'rule_report_rows'`.
- [ ] **Step 3: Implement** the Interfaces in `export.py`, `database.py`, `app.py`, `store.py` and `SKILL.md`; copy `ttgen/` to the skill again.
- [ ] **Step 4: Extend the slow publish check** in `tests/smoke.py` (`test_publish_uploaded_timetable`): before uploading, open the solved timetable workbook with openpyxl and add a `Rule report` sheet with the header row and one row `(1, "Must", "Whole school", "Nothing in words", "Met", "Checked.")`; after publishing assert `j["rule_report"][0]["result"] == "Met"` and `c.get("/api/status").get_json()["published"]["rule_report"][0]["how"] == "Checked."`. Run `.venv/bin/python tests/smoke.py --full` once → passes (`31 checks passed`); plain `smoke.py` → `30 checks passed`.
- [ ] **Step 5: Run** `.venv/bin/python tests/test_rules.py` → `8 checks passed`.
- [ ] **Step 6: Commit** — `git add ttgen skill tests/test_rules.py tests/smoke.py app.py store.py && git commit -m "The rule report: read from the Lessons workbook or the database, kept with the published timetable; SKILL.md asks for it"`

---

### Task 3: Step 6 under tabs, with typed rules

**Files:**
- Modify: `static/app.js` (`VIEWS.rules`, `addRow`, `ruleProblems`, events), `static/style.css`

**Interfaces:**
- Consumes: `placeRules()` (settings / availability / fixed / more), `targetOptions(scope)`, `S.meta.rule_types` (now with "In words"), `addRow(k)` blanks, the `data-k` change handler, `issues()`'s `out.rules[i]`.
- Produces: `const TABS = [["school", "School", ["School"]], ["levels", "Levels and classes", ["Level", "Class", "Block", "Group"]], ["subjects", "Subjects", ["Subject", "Department"]], ["venues", "Venues", ["Room"]], ["teachers", "Teachers", ["Teacher"]]]` and `tabOf(rule) -> tab id` — the tab whose scope list holds `rule.scope`; a blank or unknown scope → `"school"`. Module state `R6 = { tab: "school" }`, hook `data-rtab="<id>"`.
- Produces: `VIEWS.rules()` draws the Configuration card unchanged, then one card with the tab strip (each tab's label with the count of its rules, including typed ones) and, for the open tab only: **Teacher availability** table (Teachers tab; `where.availability`), **Fixed lessons** table (School tab: fixed rows with scope School; Levels and classes tab: the rest of `where.fixed`), **Standard rules** table (today's More rules table, the rows of `where.more` with `tabOf(r) === tab` and `r.rule !== "In words"`; its scope select lists only the tab's scopes), **Typed rules** table (the In words rows of the tab: `T<number>` label from the typed order, Must / Prefer select, scope select limited to the tab's scopes, target select from `targetOptions`, a wide text box `data-k="spec.rules.<i>.text"` with placeholder "What must, or should, happen", ✕), and a collapsed **Rule types for this tab** details (today's Rule types table filtered to types whose scopes meet the tab's).
- Produces: buttons per tab: `+ Add rule` (every tab; `addRow("rules")` then sets the new row's `scope` to the tab's first scope), `+ Typed rule` (every tab; `addRow("typed")` with blank `{ scope: <tab's first scope>, target: null, rule: "In words", text: "", strength: "Must", week: "Both", day: "All" }`), `+ Add block-out` (Teachers), `+ Add fixed lesson` (Levels and classes), `+ Every class at one time (CCE)` and `+ HBL day` (School), `+ Lessons late in the day only in some rooms` (Subjects). Adding a rule from a tab keeps that tab open.
- Produces: `ruleProblems` says `"Write the rule in words: without them this row says nothing."` for an In words row with blank `text` (after the target check), and nothing else for a typed rule.
- Produces: the Download step's stats line gains `<b>N</b> typed rules for the agent to honour` when N > 0.

- [ ] **Step 1: Tabs.** Add `TABS`, `tabOf`, `R6`; rewrite `VIEWS.rules()` as under Interfaces, reusing today's row-drawing code for the three existing tables (move each into a small function: `availRows(ix)`, `fixedRows(ix)`, `moreRows(ix, scopes)`), and add `typedRows(ix, scopes)`. The tab strip is `<div class="row tabs">` of buttons `data-rtab` with class `on` for the open one.
- [ ] **Step 2: Events.** `data-rtab` click → `R6.tab = id; render()`. `addRow`: new blank `typed`; after `addRow("rules")` from a tab the scope is set (pass the tab's first scope through a module variable or a second argument `addRow(k, preset)`); `data-add` buttons on the tabs carry `data-scope="<first scope>"` and the click handler passes it on. Typed rules never get the `groupCode` or `setPattern` paths (they are rules rows, not lessons).
- [ ] **Step 3: `ruleProblems`** for In words as under Interfaces; the Download stats line.
- [ ] **Step 4: CSS**: `.tabs button{border-radius:999px}.tabs button.on{background:var(--accent);color:#fff;border-color:var(--accent)}`, `.typed td.words input{width:100%;min-width:320px}`.
- [ ] **Step 5: Check in the browser preview** (committee, secondary sample as a practice copy, scratch `DATA_DIR`): step 6 shows Configuration, then five tabs with counts that add up to the number of rules not on the Configuration card; Teachers shows the block-outs; School shows the whole-school fixed lessons (CCE) and the HBL rule; Subjects shows the "late in the day" venue rule; Venues the room limits; `+ Typed rule` on Levels and classes adds a row `T1 · Must · Level` with an empty text box and Things to fix says "Write the rule in words…"; typing a sentence clears it and the rule stays on that tab; a second typed rule on School is `T2`; Undo removes the row; the Download step says `2 typed rules for the agent to honour` and the downloaded workbook's More rules sheet has the sentence in the In words column (open the file with openpyxl from the shell); as a head (role set from the console) the step is read-only with the tabs still switchable.
- [ ] **Step 6: Run** `node --check static/app.js` and every test command → pass. **Commit** — `git add static/app.js static/style.css && git commit -m "Step 6: constraints under tabs, with typed rules in plain words"`

---

### Task 4: The starter prompt, and the rule report on Publish

**Files:**
- Modify: `static/app.js` (`VIEWS.download`, `importHTML`, `paintPublished`), `static/style.css`

**Interfaces:**
- Consumes: Task 2's `rule_report` and `typed` in the import reply and `rule_report` in `/api/status`'s `published`; `spec.SKILL_VERSION` is not on the page: the prompt names the version from `S.meta.skill_version`, which `app.py`'s `/api/meta/<kind>` (the route that returns `rule_types`) gains as `skill_version=SKILL_VERSION`.
- Produces: `starterPrompt() -> string`, the text the committee pastes into the chatbot: `Use the attached school-timetable-generator skill (version <v>), not an older installed copy. Make the timetable for <school> <timetable> from the attached setup workbook: run python -m ttgen check first and tell me every problem; then solve and export with python -m ttgen; hand back the timetable database (.sqlite) written by ttgen export, or, if you cannot run code, a workbook with a Lessons sheet in the hand-over format in SKILL.md. The setup has <N> typed rules (Rule "In words" on the More rules sheet): honour every Must, try every Prefer, and hand back the Rule report sheet with one line per typed rule: Met, Partly or Not met, and how. Do not change the setup.` (the typed-rules sentence only when N > 0).
- Produces: a card **"3 · Starter prompt"** on step 7 between the skill card and "Keep a copy": the prompt in a read-only `<textarea id="prompt">` and a **Copy** button (`navigator.clipboard.writeText`, falling back to selecting the text; toast "Copied.").
- Produces: `ruleReportHTML(report, typed) -> string` — a table (No., Must / Prefer, Applies to, Rule, Result, How) with the Result cell coloured (Met green, Partly amber, Not met red, blank grey), under a heading **Rule report**, and above it: when `report` is empty and `typed > 0`, `<p class="issue">No rule report came back. The setup has N typed rules; ask the agent for the Rule report sheet.</p>`; when both are non-zero and `report.length !== typed`, `<p class="issue">The setup has N typed rules; the report has M.</p>`. Used by `importHTML` (after the checks) and by `paintPublished` (after the published line, with `typed` = the current setup's typed-rule count).

- [ ] **Step 1:** `app.py`: `skill_version` in the meta reply; `app.js`: `starterPrompt`, the card, the Copy button; `ruleReportHTML`, `importHTML`, `paintPublished`; CSS `.rr td.met{color:var(--ok)}.rr td.partly{color:#b45309}.rr td.notmet{color:var(--warn)}`.
- [ ] **Step 2: Check in the browser preview**: step 7 shows the prompt with the sample school's name, the version `2026-11` and, after adding a typed rule on step 6, "1 typed rules"? no: "1 typed rule" (singular and plural both right); Copy puts it on the clipboard (read it back with `navigator.clipboard.readText()` from the console); on step 8, checking a timetable workbook with no Rule report while the setup has a typed rule shows "No rule report came back…"; with a Rule report sheet added (openpyxl from the shell, two rows) the table shows both rows with coloured results and, when the setup has one typed rule, the "has 1 typed rule; the report has 2" line. After publishing (committee, scratch data), the Published now card shows the same table.
- [ ] **Step 3: Run** `node --check static/app.js` and every test command → pass. **Commit** — `git add app.py static/app.js static/style.css && git commit -m "Download: a starter prompt to paste into the chatbot; Publish: the rule report that came back"`

---

### Task 5: README and the notes

**Files:**
- Modify: `README.md`, `docs/DEPLOY.md` (only if it describes step 6 or 7)

- [ ] **Step 1:** README step 6 paragraph: the five tabs and what goes under each; typed rules (Must or Prefer, what they apply to, a sentence; numbered T1, T2 in setup order; not enforced by the scripts; listed by `check`; the agent reports each); the workbook's In words column (older workbooks still open). Step 7: the starter prompt and the skill version line. Step 8: the rule report (Met / Partly / Not met and how), the "no rule report came back" line, and that project 2 will check it.
- [ ] **Step 2:** Read it back against the page once: every button and tab name in the README exists on the page with that wording.
- [ ] **Step 3: Commit** — `git add README.md docs/DEPLOY.md && git commit -m "Docs: constraints under tabs, typed rules, the starter prompt and the rule report"`

---

## Not in this plan

Stage 6b: first and second choices (the Choices sheet, the give-way order, Will it fit? on fallbacks, `ttgen solve` giving way, the Choices used part of the report), and the configuration id on the Settings sheet. Project 2 checks the rule report; this plan only keeps and shows it.

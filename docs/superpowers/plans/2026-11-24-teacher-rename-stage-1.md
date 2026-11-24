# Teacher rename, stage 1: the setup and the draft follow. Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Typing a new name over a teacher's name on step 4 changes it on their groups, form-teacher places and rules in one save, and the draft on step 8 reads the old name as the new one.

**Architecture:** A pure function in `static/teacherview.js` does the whole rename on the setup object and keeps the old name in a new teacher-row field, `earlier_names`; the page's one change handler calls it before saving, so the server receives ordinary operations in one batch. On the server, `ttgen/spec.py` turns `earlier_names` into a map (earlier name to current name) that `model_from_files` applies to the lessons it reads against the school's setup, and `fixes.apply` applies to the stored step 8 changes before replaying them.

**Tech Stack:** Vanilla JS (no build step; tests are `node tests/x.test.js`), Python 3 / Flask (tests are plain scripts: `../timetable_generator/.venv/bin/python tests/x.py`).

**Spec:** `docs/superpowers/specs/2026-11-24-teacher-rename-design.md`, Parts 1 and 2 only. Parts 3 to 5 (step 9's question, the account, reliefs, exam duties) are later stages: build nothing of them.

## Global Constraints

- The repository is public: made-up names only in code, tests and docs ("Mdm Lee", "New Teacher 3"); the school is "CTSS" only.
- `ttgen/` has a copy under `skill/school-timetable-generator/scripts/ttgen/`; `tests/test_rules.py` fails unless the two are byte-identical. After any change to a `ttgen` file, copy it over. The workbook format does not change: do not touch the skill version.
- The new field is `earlier_names` on a teacher row: a list of strings, oldest first, no duplicates, never a name any teacher row has now; a row with none has no such key.
- A name is matched exactly (`===`) everywhere in the carry. Only the duplicate check uses `People.key` (case and spacing ignored).
- Free text is never rewritten (a typed rule's `text`, any row's `note`).
- Never run `git stash`, `git stash pop` or `git checkout -- <file>`. Never use `pkill`/`killall`; stop only processes you started, by PID. Never read or print `.claude/launch.json`. Never import `app` without `DATA_DIR` set to a scratch folder.
- Commits end with the line `Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>`. Do not push.
- `static/app.js` keeps many statements on very long lines: edit with exact string replacement, never by slicing between markers, and run `node --check static/app.js` after every edit.

## Review Focus

1. A step 8 change made before the rename ("give 2A maths to New Teacher 3") is replayed after it: it must still apply and the lesson must name Mdm Lee, not be skipped as "not on the setup's list of teachers". Pinned in Task 3.
2. A rename that changes only case or spacing ("mdm lee" to "Mdm Lee") must carry, not be refused as a duplicate of itself. Pinned in Task 1.
3. A group whose list holds an emptied teacher box (`["New Teacher 3", null]`) keeps the empty place where it is. Pinned in Task 1.
4. A placeholder name used again: a row added later with a name that is another row's earlier name takes that name back, whatever way the page added it. Pinned in Task 1 (`settle`) and Task 2 (called on every save).
5. Undo after a rename brings back the name, the groups, the form teachers, the rule and `earlier_names` together; Redo does it again. Checked in the browser in Task 2.

---

### Task 1: The rename as a pure function

**Files:**
- Modify: `static/teacherview.js` (add four functions and export them)
- Test: `tests/teacherview.test.js`

**Interfaces:**
- Consumes: `People.key(name)` from `static/people.js` (already required in the file as `P`).
- Produces (all on `TeacherView`):
  - `uses(spec, name) -> { lessons: number[], classes: number[], rules: number[], typed: number[], notes: number, twice: boolean }`. `lessons`: indices of `spec.lessons` rows whose `teachers` list holds `name`. `classes`: indices of `spec.classes` rows whose `parents` list holds `name`. `rules`: indices of `spec.rules` rows with `scope === "Teacher"` and `target === name`. `typed`: the numbers (1, 2, 3… counted over rules with `rule === "In words"`, in order) of typed rules whose `text` contains `name`. `notes`: how many rows of `venues, classes, subjects, teachers, blocks, lessons, rules` have a string `note` containing `name`. `twice`: more than one teacher row has exactly this name. A blank `name` uses nothing.
  - `rename(spec, ti, to) -> null | { error: string } | { was, now, groups: number, classes: string[], rules: number, typed: number[], notes: number, twice: boolean }`. Changes `spec` in place.
  - `renameText(r) -> string`: the toast for a result of `rename` that is not null and has no `error`.
  - `settle(spec) -> boolean`: puts every row's `earlier_names` right; true when anything changed.

- [ ] **Step 1: Write the failing tests** (append to `tests/teacherview.test.js`, before its last line that prints the count)

```js
const rspec = () => ({ school: {}, teachers: [
  { _id: "a", name: "New Teacher 3", short: "NT3", dept: "MA" },
  { _id: "b", name: "Arjun Nair", short: "Arjun", dept: "MA" },
  { _id: "c", name: "Lim Hui Min", short: "Hui Min", dept: "SC", earlier_names: ["Miss Lim"] }],
  classes: [{ class: "2A", parents: ["New Teacher 3", "Arjun Nair"] }, { class: "2B", parents: ["Arjun Nair"] }, { class: "2C" }],
  lessons: [{ subject: "Maths", teachers: ["New Teacher 3", null] }, { subject: "Maths", teachers: [null, "Arjun Nair", "New Teacher 3"] },
    { subject: "Science", teachers: ["Lim Hui Min"], note: "ask New Teacher 3 first" }, { subject: "Art" }, null],
  rules: [{ scope: "Teacher", target: "New Teacher 3", rule: "Not available" }, { scope: "Class", target: "New Teacher 3", rule: "Fixed at" },
    { scope: "School", rule: "In words", text: "no PE after lunch" }, { scope: "School", rule: "In words", text: "New Teacher 3 is free on Fridays" }] });

t("uses finds every place that names a teacher exactly", () => {
  assert.deepStrictEqual(TeacherView.uses(rspec(), "New Teacher 3"), { lessons: [0, 1], classes: [0], rules: [0], typed: [2], notes: 1, twice: false });
  assert.deepStrictEqual(TeacherView.uses(rspec(), ""), { lessons: [], classes: [], rules: [], typed: [], notes: 0, twice: false });
  assert.deepStrictEqual(TeacherView.uses({}, "X"), { lessons: [], classes: [], rules: [], typed: [], notes: 0, twice: false });
});
t("a rename carries to groups, form teachers and Teacher rules, and keeps the old name", () => {
  const s = rspec(), r = TeacherView.rename(s, 0, "  Mdm   Lee ");
  assert.deepStrictEqual(r, { was: "New Teacher 3", now: "Mdm Lee", groups: 2, classes: ["2A"], rules: 1, typed: [2], notes: 1, twice: false });
  assert.strictEqual(s.teachers[0].name, "Mdm Lee");
  assert.deepStrictEqual(s.teachers[0].earlier_names, ["New Teacher 3"]);
  assert.deepStrictEqual(s.lessons[0].teachers, ["Mdm Lee", null]);            // the empty place stays where it is
  assert.deepStrictEqual(s.lessons[1].teachers, [null, "Arjun Nair", "Mdm Lee"]);
  assert.deepStrictEqual(s.classes[0].parents, ["Mdm Lee", "Arjun Nair"]);
  assert.strictEqual(s.rules[0].target, "Mdm Lee");
  assert.strictEqual(s.rules[1].target, "New Teacher 3");                      // not a Teacher rule: left
  assert.strictEqual(s.rules[3].text, "New Teacher 3 is free on Fridays");     // free text is never rewritten
  assert.strictEqual(s.lessons[2].note, "ask New Teacher 3 first");
});
t("not a rename: a blank new name, a row with no name yet, the same name, no such row", () => {
  const s = rspec(), before = JSON.stringify(s);
  for (const to of ["", "   ", null, "New Teacher 3", " New Teacher 3 "]) assert.strictEqual(TeacherView.rename(s, 0, to), null);
  assert.strictEqual(TeacherView.rename(s, 9, "X"), null);
  s.teachers.push({ _id: "z", name: "" }); const b2 = JSON.stringify(s);
  assert.strictEqual(TeacherView.rename(s, 3, "Somebody"), null); assert.strictEqual(JSON.stringify(s), b2);
  s.teachers.pop(); assert.strictEqual(JSON.stringify(s), before);
});
t("a name another teacher has is refused; a change of only case or spacing is a rename", () => {
  const s = rspec(), before = JSON.stringify(s);
  assert.deepStrictEqual(TeacherView.rename(s, 0, "arjun  nair"), { error: "Arjun Nair is already a teacher." });
  assert.strictEqual(JSON.stringify(s), before);
  const r = TeacherView.rename(s, 0, "new teacher 3");
  assert.strictEqual(r.now, "new teacher 3"); assert.strictEqual(r.groups, 2); assert.deepStrictEqual(s.lessons[0].teachers, ["new teacher 3", null]);
});
t("earlier names: renaming back clears it, the latest rename wins, a name in use is nobody's", () => {
  const s = rspec();
  TeacherView.rename(s, 0, "Mdm Lee"); TeacherView.rename(s, 0, "Mdm Lee Mei");
  assert.deepStrictEqual(s.teachers[0].earlier_names, ["New Teacher 3", "Mdm Lee"]);
  TeacherView.rename(s, 0, "New Teacher 3");
  assert.deepStrictEqual(s.teachers[0].earlier_names, ["Mdm Lee", "Mdm Lee Mei"]);
  TeacherView.rename(s, 1, "Miss Lim");                                         // Hui Min's earlier name is taken as a name
  assert.ok(!("earlier_names" in s.teachers[2]));
  TeacherView.rename(s, 1, "Mdm Lee");                                         // row 0's earlier name is taken as a name
  assert.deepStrictEqual(s.teachers[0].earlier_names, ["Mdm Lee Mei"]);
  assert.deepStrictEqual(s.teachers[1].earlier_names, ["Arjun Nair", "Miss Lim"]);
});
t("two rows of the old name: the name changes and nothing follows", () => {
  const s = rspec(); s.teachers.push({ _id: "d", name: "New Teacher 3", dept: "SC" });
  const r = TeacherView.rename(s, 0, "Mdm Lee");
  assert.deepStrictEqual([r.twice, r.groups, r.classes, r.rules], [true, 0, [], 0]);
  assert.deepStrictEqual(s.lessons[0].teachers, ["New Teacher 3", null]); assert.strictEqual(s.rules[0].target, "New Teacher 3");
  assert.ok(!("earlier_names" in s.teachers[0]));                               // the other row still has the name
});
t("settle puts earlier names right whatever wrote them", () => {
  const s = rspec();
  s.teachers[0].earlier_names = ["Old A", "Old A", "", null, 7, "Arjun Nair", "Shared"];
  s.teachers[1].earlier_names = "nope";
  s.teachers[2].earlier_names = ["Shared", "Miss Lim"];
  assert.strictEqual(TeacherView.settle(s), true);
  assert.deepStrictEqual(s.teachers[0].earlier_names, ["Old A"]);              // a name two rows claim stays on the last of them
  assert.ok(!("earlier_names" in s.teachers[1]));
  assert.deepStrictEqual(s.teachers[2].earlier_names, ["Shared", "Miss Lim"]);
  assert.strictEqual(TeacherView.settle(s), false);
  s.teachers.push({ _id: "n", name: "Old A" }); assert.strictEqual(TeacherView.settle(s), true);   // a placeholder name used again
  assert.ok(!("earlier_names" in s.teachers[0]));
  assert.strictEqual(TeacherView.settle({}), false); assert.strictEqual(TeacherView.settle(null), false);
});
t("the toast says what followed", () => {
  const T = TeacherView.renameText, base = { was: "New Teacher 3", now: "Mdm Lee", groups: 0, classes: [], rules: 0, typed: [], notes: 0, twice: false };
  assert.strictEqual(T(base), "New Teacher 3 is now Mdm Lee.");
  assert.strictEqual(T({ ...base, groups: 6, classes: ["2A"], rules: 1 }), "New Teacher 3 is now Mdm Lee: on 6 groups, form teacher of 2A, 1 rule. Undo, at the top, brings it back.");
  assert.strictEqual(T({ ...base, groups: 1, classes: ["2A", "2B", "2C"], rules: 2 }), "New Teacher 3 is now Mdm Lee: on 1 group, form teacher of 2A, 2B and 2C, 2 rules. Undo, at the top, brings it back.");
  assert.strictEqual(T({ ...base, classes: ["2A", "2B"] }), "New Teacher 3 is now Mdm Lee: form teacher of 2A and 2B. Undo, at the top, brings it back.");
  assert.strictEqual(T({ ...base, twice: true }), "New Teacher 3 is now Mdm Lee. Two teachers were called New Teacher 3, so their groups were not changed: pick the right teacher on each.");
  assert.strictEqual(T({ ...base, groups: 2, typed: [3], notes: 1 }), "New Teacher 3 is now Mdm Lee: on 2 groups. Undo, at the top, brings it back. Typed rule T3 still says New Teacher 3: check it. 1 note still says New Teacher 3: check it.");
  assert.strictEqual(T({ ...base, typed: [3, 5], notes: 2 }), "New Teacher 3 is now Mdm Lee. Typed rules T3 and T5 still say New Teacher 3: check them. 2 notes still say New Teacher 3: check them.");
});
```

- [ ] **Step 2: Run it and see it fail**

Run: `node tests/teacherview.test.js`
Expected: FAIL with `TeacherView.uses is not a function`.

- [ ] **Step 3: Implement `uses`, `rename`, `renameText`, `settle` in `static/teacherview.js`** and add them to the returned object.

Rules the tests do not spell out: the new name is cleaned by trimming and making runs of whitespace one space; `rename` returns `null` when the cleaned name equals the stored old name exactly; the duplicate check compares `P.key` of the cleaned name with `P.key` of every other row's name and uses that row's own name in the sentence; `rename` ends by calling `settle`, which is what takes the new name off every list and keeps a name in use off this row's list; `settle` reads names exactly (no `P.key`) and deletes the key when the list is empty or was not a list; `uses` and `renameText` change nothing.

- [ ] **Step 4: Run the tests**

Run: `node tests/teacherview.test.js`
Expected: every test passes (the file prints its count).

- [ ] **Step 5: Commit**

```bash
git add static/teacherview.js tests/teacherview.test.js
git commit -m "feat(step 4): a pure rename of a teacher that carries to groups, form teachers and rules"
```
(with the Co-Authored-By line from Global Constraints)

---

### Task 2: Step 4's name box uses it

**Files:**
- Modify: `static/app.js` (the `document.addEventListener("change", …)` handler, at the lines around `setPath(path, v);` and the stub `function renameRefs()`; and `save()`)
- No new test file: the pure parts are Task 1's; this task is checked with `node --check` and in a browser.

**Interfaces:**
- Consumes: `TeacherView.uses`, `TeacherView.rename`, `TeacherView.renameText`, `TeacherView.settle` (Task 1); the page's own `tkHead()`, `otherRow(x)`, `cpBlock(x)`, `toast(text)`, `render()`, `save()`, `poll()`, `classNames()`.
- Produces: nothing later tasks call.

- [ ] **Step 1: In the change handler, handle a teacher's name before `setPath(path, v)`.** Both name boxes (the open card on step 4 and the Table view's Name column) are `data-k="spec.teachers.N.name"`, so one branch covers them. When the path matches `/^spec\.teachers\.(\d+)\.name$/`, the row has a non-blank name and `v` is not null:
  1. If `tkHead()`: take `u = TeacherView.uses(S.spec, oldName)` and build the parts that stand in a head's way, in this order: `a form teacher of 2A` (class names joined with ", " and a final " and "); `named in 1 rule` / `named in N rules`; `on 1 group of other departments` / `on N groups of other departments` (the `u.lessons` rows with `otherRow(row)`); `on 1 lesson the form teachers take` / `on N lessons the form teachers take` (the rest of `u.lessons` with `cpBlock(row)`). If there is any part: `toast("Only the committee can rename " + oldName + ": they are " + parts joined with ", " and a final " and " + ".")`, `render()` (the box goes back) and return. Nothing is saved.
  2. `const r = TeacherView.rename(S.spec, ti, v)`. If `r && r.error`: `toast(r.error); render(); return;`. If `r`: skip `setPath` (the name is set), `toast(TeacherView.renameText(r))`, and let the handler go on to its `save(); render(); poll();` as for any change. If `r` is null: fall through to the existing code unchanged.
- [ ] **Step 2: In `save()`, call `TeacherView.settle(S.spec)` before the setup is compared or sent**, so a teacher added by any path (the Add bar, the heads' "Add teachers" box, a pasted list, a new card) takes their name off every `earlier_names` in the same save and the same Undo entry.
- [ ] **Step 3: Replace the comment in `function renameRefs()`** so it no longer says a teacher's old name is left for the user to fix (rooms, classes, subjects and bands are as before).
- [ ] **Step 4: Check the syntax**

Run: `node --check static/app.js && for f in tests/*.test.js; do node "$f" > /dev/null || echo "FAIL $f"; done`
Expected: no output.

- [ ] **Step 5: Check in a browser** on the scratch server the controller names in the dispatch (the secondary sample school, signed in as the committee), with the browser tool's real pointer actions (`left_click`, `type`, `key`), never `.click()` from the console. Say for each line which action was used and what was seen:
  1. Step 4, open a teacher who has groups, type a new name, press Tab: the toast names the groups; step 5's Table view shows the new name on those rows with no "(not on list)"; step 2 and step 6 show it where the teacher was a form teacher or in a rule (add one first if the sample has none).
  2. Undo (top of the page): the name, the groups, the form teacher and the rule are back, and `S.spec.teachers[i].earlier_names` is gone. Redo: all changed again.
  3. Type a name another teacher has: the toast says "… is already a teacher." and the box shows the old name again.
  4. Step 4's Table view: rename there too.
  5. Add a new teacher whose name is the first teacher's earlier name: after the save that teacher's `earlier_names` no longer holds it.
  6. Reload the page: the renamed teacher and `earlier_names` came back from the server (the save was accepted, the header says Saved).
  A head's refusal cannot be reached with the committee code: say so in the report rather than faking it.
- [ ] **Step 6: Commit**

```bash
git add static/app.js
git commit -m "feat(step 4): a new name on a teacher carries to their groups, form teachers and rules"
```

---

### Task 3: The draft reads an earlier name as the teacher's name now

**Files:**
- Modify: `ttgen/spec.py` (new `renamed_teachers`), `ttgen/export.py` (`model_from_files`, where `spec_given`), and the two copies under `skill/school-timetable-generator/scripts/ttgen/`
- Modify: `fixes.py` (`apply`)
- Modify: `history.py` (the wording of a setup entry for the field `earlier_names`)
- Test: `tests/test_board.py` (new tests beside `test_a_group_with_an_emptied_teacher_box_still_takes_a_timetable`), `tests/test_history.py`

**Interfaces:**
- Consumes: the `earlier_names` field as Global Constraints define it (written by Task 2's page; a setup from anywhere else may hold anything there).
- Produces:
  - `ttgen.spec.renamed_teachers(spec) -> dict[str, str]`: earlier name to current name. Left out: a row that is not a dict or has no non-blank string name; an `earlier_names` that is not a list; an entry that is not a non-blank string; an earlier name equal to any teacher row's current name; an earlier name that two or more rows claim.
  - `model_from_files(setup_path, timetable_path, spec=…, edit=…)`: when `spec` is given, each lesson read from the file has its `teachers` passed through that map before `edit` runs; a name that appears twice after mapping is kept once, in its first place. With no `spec` given nothing changes.
  - `fixes.apply(lessons, fixes, spec, days)`: every stored fix is replayed with its teacher names passed through the same map (a `teachers` list on any kind of fix; `x` and `y` of a trade). The fixes given are not changed.

- [ ] **Step 1: Write the failing tests** in `tests/test_board.py`, before `test_the_preview_is_the_draft_as_the_published_page_would_show_it`:

```python
def test_a_draft_reads_an_earlier_name_as_the_teachers_name_now():
    """a teacher renamed on step 4 keeps the old name in the row's earlier_names; a timetable that still names the old teacher is
    read as naming the new one: no warning that step 5 and the timetable differ, and a change made on step 8 before the rename still applies"""
    import copy
    from ttgen import reader, spec as spec_mod
    f = spec_mod.renamed_teachers
    rows = [{"name": "Mdm Lee", "earlier_names": ["New Teacher 3", "", None, 7, "Arjun Nair", "Shared"]}, {"name": "Arjun Nair", "earlier_names": "nope"},
            {"name": "Lim Hui Min", "earlier_names": ["Shared", "Miss Lim"]}, {"name": ""}, None, {"earlier_names": ["Nobody"]}]
    assert f({"teachers": rows}) == {"New Teacher 3": "Mdm Lee", "Miss Lim": "Lim Hui Min"} and f({}) == {} and f({"teachers": None}) == {}
    d = copy.deepcopy(SPEC); reader.derive(d)
    i = next(i for i, x in enumerate(d["lessons"]) if x.get("block") and x.get("teachers") and x.get("periods")); g = d["lessons"][i]; old = g["teachers"][0]
    ti = next(k for k, t in enumerate(SPEC["teachers"]) if t["name"] == old); other = next(t["name"] for t in SPEC["teachers"] if t["name"] not in g["teachers"])
    key = f"dep:G:{g['code']}:teachers"
    file_rows = [dict(id=1, day=DAYS[0], p=0, n=1, level=g["level"], block=g["block"], classes=g["classes"], subject=g["subject"], group=g["code"], teachers=list(g["teachers"]))]
    upload = lambda rows: c.post("/api/draft", data=dict(setup=(io.BytesIO(setup_bytes(SPEC)), "setup.xlsx"), timetable=(io.BytesIO(workbook(rows)), "timetable.xlsx"), replace="1"), content_type="multipart/form-data")
    def renamed(to, earlier):
        s = copy.deepcopy(SPEC); s["teachers"][ti]["name"] = to
        if earlier: s["teachers"][ti]["earlier_names"] = earlier
        for x in s["lessons"]: x["teachers"] = [to if t == old else t for t in x.get("teachers") or []]
        return s
    cards = lambda: [t for card in board()["cards"] for row in card["rows"] for t in row["teachers"]]
    try:
        assert upload(file_rows).status_code == 200 and not any(w["key"] == key for w in draft.info()["warnings"])
        assert c.put("/api/setup", json=dict(spec=renamed("Mdm Lee", [old]), why="a rename")).status_code == 200
        j = draft.info(); assert not any(w["key"] == key for w in j["warnings"]), [w["text"] for w in j["warnings"] if w["key"] == key]
        assert "Mdm Lee" in cards() and old not in cards()
        assert c.put("/api/setup", json=dict(spec=renamed("Mdm Lee", None), why="no earlier name")).status_code == 200   # without the field the old reading stands
        assert any(w["key"] == key for w in draft.info()["warnings"]) and old in cards()
        # a change made on step 8 before the rename names the old teacher, and is replayed after it
        assert c.put("/api/setup", json=dict(spec=SPEC, why="back")).status_code == 200
        file_rows[0]["teachers"] = [other]; assert upload(file_rows).status_code == 200
        draft.fix(dict(kind="teacher", key=f"G:{g['code']}", teachers=[old]))
        assert c.put("/api/setup", json=dict(spec=renamed("Mdm Lee", [old]), why="a rename")).status_code == 200
        j = draft.info(); assert not j["fix_problems"], j["fix_problems"]
        assert "Mdm Lee" in cards() and old not in cards() and other not in cards()
        s = renamed("Mdm Lee", [old]); s["teachers"].append(dict(name=old, short=old, dept=SPEC["teachers"][ti].get("dept"), _id="zz11zz11zz"))   # the old name is a teacher again: never mapped
        assert c.put("/api/setup", json=dict(spec=s, why="the name is in use")).status_code == 200
        assert old in cards()
    finally:
        assert c.put("/api/setup", json=dict(spec=SPEC, why="back")).status_code == 200; save_draft(ROWS)
```

`draft.info()["fix_problems"]` is the list of stored changes that could not be replayed; a board card names its teachers in `card["rows"][k]["teachers"]`; a `teacher` change of a banded group takes the key `G:<code>` (`fixes._key`).

  And in `tests/test_history.py`, in that file's own style: a save whose operations set a teacher's `name` and `earlier_names` and one lesson's `teachers` gives history entries none of whose `text` or `label` holds the raw key `earlier_names` (it reads "Earlier names"); and putting that save back (as `tests/test_putback.py` puts a save back) restores the name, removes `earlier_names` and restores the lesson's teachers together.

- [ ] **Step 2: Run them and see them fail**

Run: `../timetable_generator/.venv/bin/python tests/test_board.py`
Expected: FAIL with `AttributeError: module 'ttgen.spec' has no attribute 'renamed_teachers'`.

- [ ] **Step 3: Implement** `renamed_teachers` in `ttgen/spec.py`; the mapping in `ttgen/export.py` `model_from_files` (inside the `spec_given` case, on the lessons list just before `if edit: out = edit(out, spec, days)`); copy both files to the skill's `ttgen`; the mapping of stored fixes in `fixes.apply` (on copies); the wording in `history.py`. If Put back already restores the batch whole, the put-back test needs no code.

- [ ] **Step 4: Run the suites this touches**

Run (with `LOGS` set to a folder of your own in the scratch directory the dispatch names): `for t in test_board test_fixes test_helper test_verify test_rules test_versions test_compare test_refit test_history test_putback smoke; do ../timetable_generator/.venv/bin/python tests/$t.py > "$LOGS/$t.log" 2>&1 || echo "FAIL $t"; done`
Expected: no FAIL line.

- [ ] **Step 5: Commit**

```bash
git add ttgen/spec.py ttgen/export.py skill/school-timetable-generator/scripts/ttgen/spec.py skill/school-timetable-generator/scripts/ttgen/export.py fixes.py history.py tests/test_board.py tests/test_history.py
git commit -m "feat(step 8): a timetable that names a teacher's earlier name is read as their name now"
```

---

### Task 4: The guide, the notes and every suite

**Files:**
- Modify: `README.md` (the part on step 4 and on "From setup to published timetable")
- Create: `docs/superpowers/plans/2026-11-24-teacher-rename-stage-1-notes.md`

- [ ] **Step 1: README.** In the text about step 4, say in the README's own plain style: typing a new name over a teacher's name changes it on their groups (step 5), form-teacher places (step 2) and rules (step 6) in the same save, with the toast's sentence as the example; Undo takes it all back; a name another teacher has is refused; a head renames only a teacher they added, and only when everything that names the teacher is theirs; the draft on step 8 follows without Re-fit; the account, reliefs and exam duties do not follow yet (the new name is a new person after Publish, with a new personal code).
- [ ] **Step 2: Notes file.** Rulings made while building, known limits (from the spec: free text kept; replacing the setup from a workbook drops `earlier_names`; two people changing one teacher at once is best effort), and what was not tried in a browser (a head's refusal).
- [ ] **Step 3: Every suite, quick and slow.**

Run: every `tests/*.test.js` with `node`, `node --check static/app.js`, every `tests/test_*.py` and `tests/smoke.py`, then `--full` on `tests/test_typed.py`, `tests/test_helper.py`, `tests/test_fixes.py` and `tests/smoke.py`.
Expected: all pass; report the counts.

- [ ] **Step 4: Commit**

```bash
git add README.md docs/superpowers/plans/2026-11-24-teacher-rename-stage-1-notes.md
git commit -m "docs: a teacher's new name carries (stage 1): README and notes"
```

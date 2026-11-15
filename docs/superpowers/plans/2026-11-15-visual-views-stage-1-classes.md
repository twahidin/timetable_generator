# Visual views, stage 1: class cards and the band picture (step 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Step 2 (Classes) gets three views of the same data: Cards (each class with its Class Parents, subjects and student counts), Bands (how a level's subjects are banded across its classes) and today's Table.

**Architecture:** A new pure module `static/classview.js` (`ClassView`) turns the setup into two plain models, one for the cards and one for a level's band picture; Node tests pin it. `static/app.js` draws the models and reuses the table's own change paths (`data-k` fields, `Parents.setParents`, `delBtn`), so a change from a card is the same change the table makes. Nothing is added to the setup, the server or the workbook.

**Tech Stack:** Vanilla JS in the browser (no build step), Node for the module's tests (`node tests/*.test.js`, plain `assert`), Flask untouched.

**Spec:** `docs/superpowers/specs/2026-11-15-visual-setup-views-design.md` (stage 1 and "Across all four stages"). Branch `visual-setup-views`, from `main` at fa01b16.

## Global Constraints

- The Table view of step 2 is today's table, cell for cell. Its code moves into a function of its own and is otherwise not changed.
- One set of data: a change made on a card goes through the same path as the table's (`setPath` by `data-k`, `Parents.setParents`, the existing delete), one save, one Undo step.
- Nothing new is stored in the setup, sent to the server or written to the workbook. No skill version change in this stage.
- The view is remembered per person in the browser (`localStorage`), and the step opens on Cards the first time.
- Department heads see every view and can change nothing on step 2 (as today); the view switch and the level picker must still work for them.
- Nothing can be done only by dragging (this stage has no dragging).
- Everything a person typed (class, subject, band, teacher, room names) is drawn through `esc()`.
- The school's size: 32 classes, about 1,000 lesson rows, about 1,300 students. Both models for every level are worked out in well under a second; `Groups.codes(spec)` is called once per model, never once per class or per row.
- Sentences on the page are plain, short, and name things as the page already does ("Class Parents" is the school's own word from `Parents.label(S.spec)`).
- Tests, samples and documents use made-up names only. The school is "CTSS" or "the school", never its full name. No real workbook or timetable is committed; a run on the real setup reports counts only.
- Browser checks run on a scratch server with a scratch `DATA_DIR` and the README's example codes, never the repository's `data/`. No test or check calls a model API.
- Commits end with `Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>`. Nothing is pushed.

## Review Focus

1. **A student list for some classes only, or none.** A class with no student on the list shows its planned number and subjects without counts; it never shows 0. Pinned in Task 1 (`counts_only_where_the_list_has_the_class`).
2. **Rows that are not tidy.** A lesson naming a class that is not on step 2, a lesson with no classes, a `null` row, a band with no groups, a band listing a class of another level, a class with no level: no error, and nothing invented. Pinned in Task 1 (`untidy_rows_do_not_throw`) and Task 2 (`untidy_bands_do_not_throw`).
3. **The school's size.** A setup of 32 classes, 1,000 lesson rows and 1,300 students gives every level's cards and band picture in under 300 ms under Node. Pinned in Task 2 (`a_school_sized_setup_is_quick`).
4. **A band whose classes are not side by side, or that shares classes with another of the same subject.** The bar is drawn in pieces; the second band goes on a row of its own. Pinned in Task 2 (`a_bar_is_cut_where_its_classes_are_apart`, `bands_sharing_a_class_take_rows_of_their_own`).
5. **A name with `<` or `&` in it.** A class named `1<b>A` and a band named `Sec 1 <i>Opt` show as typed, in both views. Checked in a browser in Tasks 3 and 4 (the last step of each).

---

### Task 1: The cards model

**Files:**
- Create: `static/classview.js`
- Test: `tests/classview.test.js`

**Interfaces:**
- Consumes: `Groups.codes(spec)` (one code per `spec.lessons` row; `"Entire Class"` for a whole-class row), `Parents.names(classRow)` (the class's Class Parents, a list of names). In Node: `require("./groups.js")`, `require("./parents.js")`; in the page they are globals loaded before this file.
- Produces: `ClassView.cards(spec)` returning a list of levels:

  ```js
  [{ level: "Sec 3", planned: 154, real: 3,          // sums over its classes; real is null when the list has no student of any of them
     cards: [{ ci: 0, class: "3A", planned: 40, real: 3, home_room: "B3-1", parents: ["Arjun Nair", "Mei Tan"],
               subjects: [{ subject: "English Language G3", whole: true, count: null },
                          { subject: "Mathematics G3", whole: false, count: 2 }] }] }]
  ```

  and `ClassView.levels(spec)`: the levels that have at least one class, in the order below.

  Rules the tests pin:
  - Levels come in the order of `spec.school.levels`; a level found only on classes follows, in first-seen order; classes with no level are last under `level: ""`. A level with no class is left out.
  - `ci` is the class's index in `spec.classes`. `planned` is `Number(size)` or `null`. `real` is the number of `spec.students` whose `class` is this class, or `null` when there is none.
  - `subjects`: each distinct `subject` of the lesson rows whose `classes` include the class. `whole` is true when one of those rows has the code `"Entire Class"`. Whole subjects first, then the others; within each, the order of `spec.subjects` (a subject not on step 3 after them, in first-seen order).
  - `count` is `null` for a whole subject and whenever the class's `real` is `null`; otherwise the number of the class's students holding (in `groups`) at least one code of the class's rows of that subject.

- [ ] **Step 1: Write the failing tests**

`tests/classview.test.js`, in the style of `tests/groups.test.js` (plain `assert`, `let n = 0; const t = (name, f) => { f(); n++; };`, last line `console.log(n + " cases passed")`), with this fixture and these cases:

```js
const assert = require("assert");
const ClassView = require("../static/classview.js");
let n = 0; const t = (name, f) => { f(); n++; };
const W = (subject, cls) => ({ level: "Sec 3", subject, classes: [cls], students: 40 });
const fixture = () => ({
  school: { levels: ["Sec 1", "Sec 3"], departments: ["EL", "MA", "HU", "PE"], tags: [["G3", "P"], ["G2", "A"], ["G1", "K"], ["-", ""]], parents_max: 4 },
  classes: [{ class: "3A", level: "Sec 3", size: 40, home_room: "B3-1", parents: ["Arjun Nair", "Mei Tan"] }, { class: "3B", level: "Sec 3", size: 38, home_room: "B3-2" },
            { class: "3C", level: "Sec 3", size: 39 }, { class: "3D", level: "Sec 3", size: 37 }, { class: "1A", level: "Sec 1", size: 40 }],
  subjects: [{ subject: "English Language G3", code: "EL", tag: "G3", dept: "EL" }, { subject: "Mathematics G3", code: "MA", tag: "G3", dept: "MA" }, { subject: "Mathematics G2", code: "MA", tag: "G2", dept: "MA" },
             { subject: "Geography G3", code: "GE", tag: "G3", dept: "HU" }, { subject: "History G3", code: "HI", tag: "G3", dept: "HU" }, { subject: "Physical Education", code: "PE", tag: "-", dept: "PE" }],
  teachers: [{ name: "Arjun Nair", short: "Arjun" }, { name: "Mei Tan", short: "Mei" }],
  blocks: [{ block: "Sec 3 Mathematics", level: "Sec 3", classes: ["3A", "3B", "3C", "3D"] }, { block: "Sec 3 Option A", level: "Sec 3", classes: ["3A", "3B"] }, { block: "Sec 3 Option B", level: "Sec 3", classes: ["3C", "3D"] }],
  lessons: [W("Physical Education", "3A"), W("Physical Education", "3B"), W("Physical Education", "3C"), W("Physical Education", "3D"),
            W("English Language G3", "3A"), W("English Language G3", "3B"), W("English Language G3", "3C"), W("English Language G3", "3D"),
            { level: "Sec 3", subject: "Mathematics G3", block: "Sec 3 Mathematics", classes: ["3A", "3B", "3C", "3D"], students: 30 },   // 3MAP1
            { level: "Sec 3", subject: "Mathematics G3", block: "Sec 3 Mathematics", classes: ["3A", "3B", "3C", "3D"], students: 30 },   // 3MAP2
            { level: "Sec 3", subject: "Mathematics G2", block: "Sec 3 Mathematics", classes: ["3A", "3B", "3C", "3D"], students: 24 },   // 3MAA1
            { level: "Sec 3", subject: "Geography G3", block: "Sec 3 Option A", classes: ["3A", "3B"], students: 38 },                    // 3GEP1
            { level: "Sec 3", subject: "History G3", block: "Sec 3 Option A", classes: ["3A", "3B"], students: 37 },                      // 3HIP1
            { level: "Sec 3", subject: "Geography G3", block: "Sec 3 Option B", classes: ["3C", "3D"], students: 41 },                    // 3GEP2
            { level: "Sec 3", subject: "History G3", block: "Sec 3 Option B", classes: ["3C", "3D"], students: 33 },                      // 3HIP2
            { level: "Sec 1", subject: "English Language G3", classes: ["1A"], students: 40 }],
  students: [{ id: "S1", name: "Student One", class: "3A", groups: ["3MAP1", "3GEP1"] }, { id: "S2", name: "Student Two", class: "3A", groups: ["3MAP1", "3HIP1"] },
             { id: "S3", name: "Student Three", class: "3A", groups: ["3MAA1", "3GEP1"] }]
});

t("levels_in_the_schools_order_with_their_sums", () => {
  const L = ClassView.cards(fixture());
  assert.deepStrictEqual(L.map(x => [x.level, x.planned, x.real, x.cards.length]), [["Sec 1", 40, null, 1], ["Sec 3", 154, 3, 4]]);
  assert.deepStrictEqual(ClassView.levels(fixture()), ["Sec 1", "Sec 3"]);
});
t("a_card_has_the_class_its_room_its_parents_and_its_index", () => {
  const c = ClassView.cards(fixture())[1].cards[0];
  assert.deepStrictEqual([c.ci, c.class, c.planned, c.real, c.home_room, c.parents], [0, "3A", 40, 3, "B3-1", ["Arjun Nair", "Mei Tan"]]);
});
t("whole_subjects_first_then_the_rest_each_in_step_3_order", () => {
  const c = ClassView.cards(fixture())[1].cards[0];
  assert.deepStrictEqual(c.subjects.map(s => [s.subject, s.whole]), [["English Language G3", true], ["Physical Education", true],
    ["Mathematics G3", false], ["Mathematics G2", false], ["Geography G3", false], ["History G3", false]]);
});
t("a_part_subject_counts_this_classs_students_once_each", () => {
  const c = ClassView.cards(fixture())[1].cards[0], by = Object.fromEntries(c.subjects.map(s => [s.subject, s.count]));
  assert.deepStrictEqual(by, { "English Language G3": null, "Physical Education": null, "Mathematics G3": 2, "Mathematics G2": 1, "Geography G3": 2, "History G3": 1 });
  const s = fixture(); s.students[0].groups.push("3MAP2");            // one student in two groups of the same subject is still one
  assert.strictEqual(ClassView.cards(s)[1].cards[0].subjects.find(x => x.subject === "Mathematics G3").count, 2);
});
t("counts_only_where_the_list_has_the_class", () => {
  const b = ClassView.cards(fixture())[1].cards[1];
  assert.strictEqual(b.real, null); assert.ok(b.subjects.length === 6 && b.subjects.every(s => s.count === null));
  const s = fixture(); s.students = [];
  assert.ok(ClassView.cards(s).every(l => l.real === null && l.cards.every(c => c.real === null)));
  delete s.students; assert.strictEqual(ClassView.cards(s)[1].cards[0].real, null);
});
t("a_kept_code_counts_as_part_of_the_class", () => {
  const s = fixture(); s.lessons.push({ level: "Sec 3", subject: "History G3", classes: ["3A"], students: 6, code_override: "3HI-X" }); s.students[2].groups.push("3HI-X");
  const h = ClassView.cards(s)[1].cards[0].subjects.find(x => x.subject === "History G3");
  assert.deepStrictEqual([h.whole, h.count], [false, 2]);
});
t("untidy_rows_do_not_throw", () => {
  const s = fixture();
  s.lessons.push(null, { level: "Sec 3", subject: "Art", classes: ["9Z"] }, { level: "Sec 3", subject: "Art" }, { level: "Sec 3", classes: ["3A"] }, { level: "Sec 3", subject: "Art", classes: ["3A"] });
  s.classes.push(null, { class: "X1" }, { class: "5A", level: "Sec 5", size: "" }); s.students.push(null, { id: "S9", class: "9Z" }, { id: "S8", class: "3A" });
  const L = ClassView.cards(s);
  assert.deepStrictEqual(L.map(x => x.level), ["Sec 1", "Sec 3", "Sec 5", ""]);
  const a = L[1].cards[0]; assert.strictEqual(a.real, 4); assert.deepStrictEqual(a.subjects[2], { subject: "Art", whole: true, count: null });   // not on step 3: after the other whole subjects, before the part ones
  assert.deepStrictEqual([L[2].cards[0].planned, L[3].cards[0].class, L[3].cards[0].subjects], [null, "X1", []]);
  assert.deepStrictEqual(ClassView.cards({}), []); assert.deepStrictEqual(ClassView.levels({}), []);
});
console.log(n + " cases passed");
```

- [ ] **Step 2: Run it and see it fail**

Run: `node tests/classview.test.js`
Expected: FAIL with `Cannot find module '../static/classview.js'`

- [ ] **Step 3: Write `static/classview.js` with `cards(spec)` and `levels(spec)`**

Same shape as `static/groups.js`: a header comment saying what it is and that it is pure, `var ClassView = (function () { "use strict"; … return { cards: cards, levels: levels }; })();` and `if (typeof module !== "undefined") module.exports = ClassView;`. Take `Groups` and `Parents` from the globals when they exist, else `require` them. Call `Groups.codes(spec)` once; build per class the map subject to codes in one pass over the lessons, and per class the list of its students in one pass over the students.

- [ ] **Step 4: Run the tests and see them pass**

Run: `node tests/classview.test.js`
Expected: `7 cases passed`

- [ ] **Step 5: Commit**

```bash
git add static/classview.js tests/classview.test.js
git commit -m "feat(classes): the cards model: each class with its Class Parents, subjects and student counts"
```

---

### Task 2: The band picture's model

**Files:**
- Modify: `static/classview.js`
- Test: `tests/classview.test.js`

**Interfaces:**
- Consumes: Task 1's module; `Groups.lanes(spec, level)` (one entry per band of the level: `{ bi, block, level, classes, groups: [{ li, code, subject, classes, students, teachers }] }`), `Groups.untag(subject)` (the subject without its G-level), `Groups.codes(spec)`.
- Produces: `ClassView.bands(spec, level)`:

  ```js
  { level: "Sec 3", classes: ["3A", "3B", "3C", "3D"],
    rows: [{ label: "English Language", cells: [{ kind: "whole" }, { kind: "whole" }, { kind: "whole" }, { kind: "whole" }], bars: [] },
           { label: "Mathematics", cells: [null, null, null, null],
             bars: [{ block: "Sec 3 Mathematics", bi: 0, classes: ["3A", "3B", "3C", "3D"], spans: [[0, 4]],
                      groups: [{ code: "3MAP1", subject: "Mathematics G3", students: 30 }] }] }] }
  ```

  Rules the tests pin:
  - `classes`: the level's classes in step 2 order. A level with none gives `{ level, classes: [], rows: [] }`.
  - A row is one label. For a lesson row with no band, the label is `Groups.untag(subject)`, and each of its classes (of this level) gets a cell on that label's first row: `{ kind: "whole" }` when its code is `"Entire Class"`, else `{ kind: "part", code }`. Whole wins over part in the same cell.
  - A band's label is the one subject its groups share once untagged, or the band's own name when its groups are of several subjects or it has none.
  - A bar's `classes` are the band's listed classes that are classes of this level, in column order; when the band lists none, the classes its groups name. A band left with no class of this level is not drawn.
  - `spans` are the runs of neighbouring columns, each `[first column, how many]`.
  - A bar goes on the first row of its label where none of its classes has a cell or another bar; otherwise on a new row of the same label, placed straight after the last row of that label.
  - Row order: labels in the order their subjects appear on step 3 (untagged), then any other label in the order it first turns up (bands in `spec.blocks` order). Rows with no cell and no bar are not returned.
  - `groups` are the band's groups in lesson order: `code`, `subject`, `students` (a number or `null`).

- [ ] **Step 1: Write the failing tests** (added to `tests/classview.test.js`, above its last line, using Task 1's fixture)

```js
const cellKinds = r => r.cells.map(c => c ? c.kind : null);
t("whole_class_subjects_are_cells_and_a_one_subject_band_is_a_bar_on_its_row", () => {
  const B = ClassView.bands(fixture(), "Sec 3");
  assert.deepStrictEqual(B.classes, ["3A", "3B", "3C", "3D"]);
  assert.deepStrictEqual(B.rows.map(r => r.label), ["English Language", "Mathematics", "Physical Education", "Sec 3 Option A", "Sec 3 Option B"]);
  assert.deepStrictEqual(cellKinds(B.rows[0]), ["whole", "whole", "whole", "whole"]); assert.deepStrictEqual(B.rows[0].bars, []);
  const m = B.rows[1]; assert.deepStrictEqual(cellKinds(m), [null, null, null, null]);
  assert.deepStrictEqual(m.bars.map(b => [b.block, b.bi, b.classes, b.spans]), [["Sec 3 Mathematics", 0, ["3A", "3B", "3C", "3D"], [[0, 4]]]]);
  assert.deepStrictEqual(m.bars[0].groups, [{ code: "3MAP1", subject: "Mathematics G3", students: 30 }, { code: "3MAP2", subject: "Mathematics G3", students: 30 }, { code: "3MAA1", subject: "Mathematics G2", students: 24 }]);
});
t("a_band_of_several_subjects_has_a_row_named_as_the_band", () => {
  const B = ClassView.bands(fixture(), "Sec 3"), a = B.rows[3], b = B.rows[4];
  assert.deepStrictEqual([a.label, a.bars[0].spans, a.bars[0].groups.map(g => g.code)], ["Sec 3 Option A", [[0, 2]], ["3GEP1", "3HIP1"]]);
  assert.deepStrictEqual([b.label, b.bars[0].spans, cellKinds(b)], ["Sec 3 Option B", [[2, 2]], [null, null, null, null]]);
});
t("one_subject_bands_on_different_classes_share_a_row", () => {
  const s = fixture(); s.blocks[0].classes = ["3A", "3B"]; s.blocks.push({ block: "Sec 3 Mathematics 2", level: "Sec 3", classes: ["3C", "3D"] });
  s.lessons.push({ level: "Sec 3", subject: "Mathematics G3", block: "Sec 3 Mathematics 2", classes: ["3C", "3D"], students: 28 });
  const m = ClassView.bands(s, "Sec 3").rows.filter(r => r.label === "Mathematics");
  assert.strictEqual(m.length, 1); assert.deepStrictEqual(m[0].bars.map(b => [b.block, b.spans]), [["Sec 3 Mathematics", [[0, 2]]], ["Sec 3 Mathematics 2", [[2, 2]]]]);
});
t("bands_sharing_a_class_take_rows_of_their_own", () => {
  const s = fixture(); s.blocks.push({ block: "Sec 3 Mathematics 2", level: "Sec 3", classes: ["3A", "3D"] });
  s.lessons.push({ level: "Sec 3", subject: "Mathematics G1", block: "Sec 3 Mathematics 2", classes: ["3A", "3D"], students: 12 });
  const rows = ClassView.bands(s, "Sec 3").rows, at = rows.map(r => r.label);
  assert.deepStrictEqual(at.slice(0, 4), ["English Language", "Mathematics", "Mathematics", "Physical Education"]);   // the new row sits straight after the first
  assert.deepStrictEqual(rows[2].bars.map(b => [b.block, b.spans]), [["Sec 3 Mathematics 2", [[0, 1], [3, 1]]]]);
});
t("a_bar_is_cut_where_its_classes_are_apart", () => {
  const s = fixture(); s.blocks[1].classes = ["3A", "3C", "3D"];
  assert.deepStrictEqual(ClassView.bands(s, "Sec 3").rows.find(r => r.label === "Sec 3 Option A").bars[0].spans, [[0, 1], [2, 2]]);
});
t("a_class_taking_a_subject_whole_beside_a_band_of_it", () => {
  const s = fixture(); s.blocks[0].classes = ["3A", "3B", "3C"]; s.lessons.forEach(x => { if (x.block === "Sec 3 Mathematics") x.classes = ["3A", "3B", "3C"]; });
  s.lessons.push({ level: "Sec 3", subject: "Mathematics G3", classes: ["3D"], students: 37 });
  const m = ClassView.bands(s, "Sec 3").rows.filter(r => r.label === "Mathematics");
  assert.strictEqual(m.length, 1); assert.deepStrictEqual(cellKinds(m[0]), [null, null, null, "whole"]); assert.deepStrictEqual(m[0].bars[0].spans, [[0, 3]]);
});
t("a_kept_code_with_no_band_is_a_part_cell_and_whole_wins", () => {
  const s = fixture(); s.lessons.push({ level: "Sec 3", subject: "History G3", classes: ["3A", "3B"], students: 6, code_override: "3HI-X" }, { level: "Sec 3", subject: "English Language G2", classes: ["3A"], students: 5, code_override: "3EL-X" });
  const rows = ClassView.bands(s, "Sec 3").rows, h = rows.find(r => r.label === "History");
  assert.deepStrictEqual(h.cells, [{ kind: "part", code: "3HI-X" }, { kind: "part", code: "3HI-X" }, null, null]);
  assert.deepStrictEqual(cellKinds(rows.find(r => r.label === "English Language")), ["whole", "whole", "whole", "whole"]);
});
t("untidy_bands_do_not_throw", () => {
  const s = fixture();
  s.blocks.push(null, { block: "Sec 3 Empty", level: "Sec 3", classes: ["3A"] }, { block: "Sec 3 Stray", level: "Sec 3", classes: ["1A", "9Z"] }, { block: "Sec 3 Unlisted", level: "Sec 3" });
  s.lessons.push({ level: "Sec 3", subject: "Art", block: "Sec 3 Stray", classes: ["1A"], students: 9 }, { level: "Sec 3", subject: "Art", block: "Sec 3 Unlisted", classes: ["3B", "3C"] });
  const B = ClassView.bands(s, "Sec 3"), by = Object.fromEntries(B.rows.map(r => [r.label, r]));
  assert.deepStrictEqual(by["Sec 3 Empty"].bars[0].groups, []); assert.ok(!("Sec 3 Stray" in by));               // no class of this level: not drawn
  assert.deepStrictEqual([by["Art"].bars[0].classes, by["Art"].bars[0].groups[0].students], [["3B", "3C"], null]);   // listed no classes: its groups' classes
  assert.deepStrictEqual(ClassView.bands(s, "Sec 9"), { level: "Sec 9", classes: [], rows: [] });
  assert.deepStrictEqual(ClassView.bands({}, "Sec 1"), { level: "Sec 1", classes: [], rows: [] });
});
t("a_school_sized_setup_is_quick", () => {
  const s = { school: { levels: ["Sec 1", "Sec 2", "Sec 3", "Sec 4"], tags: [["G3", "P"], ["G2", "A"], ["G1", "K"], ["-", ""]] }, classes: [], subjects: [], blocks: [], lessons: [], students: [] };
  for (let k = 0; k < 34; k++) ["G3", "G2", "G1"].forEach(g => s.subjects.push({ subject: `Subject ${k} ${g}`, code: `S${k}`, tag: g }));
  s.school.levels.forEach((lv, li) => {
    const cls = Array.from({ length: 8 }, (_, i) => `${li + 1}C${i + 1}`); cls.forEach(c => s.classes.push({ class: c, level: lv, size: 40 }));
    for (let k = 0; k < 12; k++) cls.forEach(c => s.lessons.push({ level: lv, subject: `Subject ${k} G3`, classes: [c], students: 40 }));          // 96 whole-class rows a level
    for (let k = 12; k < 34; k++) { s.blocks.push({ block: `${lv} Band ${k}`, level: lv, classes: cls });
      for (let g = 0; g < 7; g++) s.lessons.push({ level: lv, subject: `Subject ${k} ${["G3", "G2", "G1"][g % 3]}`, block: `${lv} Band ${k}`, classes: cls, students: 30 }); }   // 154 banded rows a level
    cls.forEach((c, ci) => { for (let i = 0; i < 40; i++) s.students.push({ id: `${c}-${i}`, class: c, groups: Array.from({ length: 10 }, (_, k) => `${li + 1}S${12 + k}P${1 + (i + ci) % 3}`) }); });
  });
  assert.strictEqual(s.lessons.length, 1000); assert.strictEqual(s.students.length, 1280);
  const t0 = Date.now(); const L = ClassView.cards(s); const B = s.school.levels.map(lv => ClassView.bands(s, lv)); const ms = Date.now() - t0;
  assert.strictEqual(L.reduce((a, l) => a + l.cards.length, 0), 32); assert.ok(B.every(b => b.rows.length >= 34)); assert.ok(ms < 300, `took ${ms} ms`);
});
```

- [ ] **Step 2: Run them and see them fail**

Run: `node tests/classview.test.js`
Expected: FAIL with `ClassView.bands is not a function`

- [ ] **Step 3: Add `bands(spec, level)` to `static/classview.js`** and export it. Use `Groups.lanes(spec, level)` for the bands and `Groups.codes(spec)` (once) for the rows with no band.

- [ ] **Step 4: Run the tests and see them pass**

Run: `node tests/classview.test.js`
Expected: `16 cases passed`

Run: `node tests/groups.test.js && node tests/parents.test.js`
Expected: both pass as before (16 and 46 cases).

- [ ] **Step 5: Commit**

```bash
git add static/classview.js tests/classview.test.js
git commit -m "feat(classes): the band picture's model: whole-class cells and bands as bars across a level's classes"
```

---

### Task 3: Step 2's view switch and the Cards view

**Files:**
- Modify: `static/index.html` (load `classview.js` after `groups.js`)
- Modify: `static/app.js` (`VIEWS.classes`, the click and change handlers, `headLocks`)
- Modify: `static/style.css`
- Modify: `README.md` (the test list; step 2's paragraph)

**Interfaces:**
- Consumes: `ClassView.cards(S.spec)` (Task 1); in `app.js`: `issues()` and `rowCls(out, crit, "classes", ci)` for a card's mark, `inp`/`sel` with `data-k` paths `spec.classes.${ci}.class|level|size|home_room|note`, `delBtn("classes", ci)`, `Parents.label/maximum/names/setParents`, `teacherNames()`, `avatarOf(teacher, size)`, `levels()`, `rooms()`, `esc`, `locked("classes")`.
- Produces (Task 4 relies on these names):
  - `const CLASSVIEW = "ttsetup.view.classes"` and `const CV = { view: "cards", open: null, level: "" }`; `CV.view` is one of `"cards" | "bands" | "table"`, read from `localStorage` at load (anything else means `"cards"`) and written on a switch.
  - The switch: `<div class="switch">` with three buttons `data-cview="cards|bands|table"`, labelled Cards, Bands, Table, the current one with class `on`. A click sets `CV.view`, stores it, closes any open card and re-renders.
  - `classesTable()` returning today's table markup unchanged; `classesCards()`; and a place for Task 4's `classesBands()`, which until then returns a line saying the picture is coming (removed in Task 4).

What the Cards view shows (the spec's "Cards" list is the authority):
- Per level from `ClassView.cards`: a heading line "{level} · {n} classes · {planned} students", with " · {real} on the list" when `real` is not `null`; then a grid of cards.
- A card (`data-ccard="{ci}"`, with the table row's mark class): the class; "{real} on the list · {planned} planned" or "{planned} planned"; "Home room {room}" or "No home room"; the Class Parents as small avatars with their short names (a name not on the teacher list shows as text), then a "+" while the class has fewer than the school's maximum; the subjects as chips, whole ones in one style and part ones in another with " · {count}" when the count is not `null`.
- A click on a card (or its "+") opens it in place (`CV.open = ci`): the same fields as the table row, with the same `data-k` paths and the same Class Parents selects, a Delete button (the table's own) and a Close button. One card is open at a time. A class under Things to fix shows its messages in the open card, as the row's tooltip does in the table.
- The Class Parents selects of the table row and of the open card sit inside an element with `data-parents="{ci}"`, and the existing `data-parent` change handler reads the selects from `el.closest("[data-parents]")` instead of `el.closest("tr")`.
- "+ Add class" under the cards adds a class as the table's button does and opens its card. The two helper bars above the table today (Add classes; the Class Parents bar) stay above the Cards and Table views.
- With no class yet: one line, "No classes yet. Add them with the bar above."
- `headLocks`: on a locked step the buttons carrying `data-cview` stay enabled, as `data-rtab` ones do. A head can open a card and sees its fields disabled.

- [ ] **Step 1: Move the table into `classesTable()` and add the switch**, with `VIEWS.classes()` choosing by `CV.view`. Load `classview.js` in `index.html`.

- [ ] **Step 2: Check nothing moved**

Run: `node --check static/app.js && .venv/bin/python tests/smoke.py 2>/dev/null | tail -1`
Expected: no syntax error; `89 checks passed`

- [ ] **Step 3: Write `classesCards()`, the open card, the handlers and the styles** as described above. Styles go beside `table.classtable` in `static/style.css`, in the page's present look (the card style of step 5's cards, the `.switch` of step 5).

- [ ] **Step 4: Run every page-side suite**

Run: `node --check static/app.js && for f in tests/*.test.js; do node $f | tail -1; done && .venv/bin/python tests/smoke.py 2>/dev/null | tail -1`
Expected: every line ends "passed"; `classview.test.js` 16; smoke 89.

- [ ] **Step 5: README**: add `node tests/classview.test.js   # step 2's cards and band picture` to the test list, and two sentences on step 2's three views where the README describes the steps.

- [ ] **Step 6: Browser check on a scratch server** (the secondary sample school, signed in as the committee; then as a head), and write what was seen in the task report:
  1. Step 2 opens on Cards; the levels and cards match the Table's rows; Table is as before; the choice survives a reload.
  2. Open a card, change the home room and the number of students: the Table shows the same; Undo puts both back in one step each.
  3. Add a Class Parent on a card, then a second: the class's lesson of a named subject follows on step 5 (set a named subject on step 6 first), exactly as from the Table.
  4. Load the sample's students (Students step): a card shows "{n} on the list" and counts on its part subjects; a class with no student on the list shows no counts.
  5. Rename a class to `1<b>A`: the card shows the name as typed, nothing is bold.
  6. As a department head: the three views switch, a card opens, every field in it is disabled, and "Only the committee can change this step." shows.
  7. No error in the browser's console at any point.

- [ ] **Step 7: Commit**

```bash
git add static/index.html static/app.js static/style.css README.md
git commit -m "feat(classes): step 2 in three views; class cards with Class Parents, subjects and student counts"
```

---

### Task 4: The Bands view

**Files:**
- Modify: `static/app.js` (`classesBands()`, the handlers, a link on step 5)
- Modify: `static/style.css`
- Modify: `README.md` (one sentence)

**Interfaces:**
- Consumes: `ClassView.bands(S.spec, level)` and `ClassView.levels(S.spec)` (Tasks 1 and 2); `CV`, the switch and `classesBands()`'s place (Task 3); on step 5, the "Groups and bands" view (`M.view = "groups"`, stored under `MAPVIEW`) whose bands are drawn as `<div class="lane" data-glane="{band name}">`.
- Produces: `classesBands()`; `data-cband="{band name}"` on each bar; a button on step 5's "Groups and bands" view with `data-cbands="{level}"`.

What the Bands view shows (the spec's "Bands" list is the authority):
- A level picker (`<select id="cvLevel">` over `ClassView.levels`), set from `CV.level`, falling back to the first level; a legend of the three marks (whole class; band, same time; part of the class).
- One grid: a first column of row labels, then one column per class with the class's name on top. Each model row is one line of the grid: a filled cell for `whole`, a cell with the code for `part`, a dashed empty cell where the class has neither a cell nor a bar on that line, and each bar drawn over its `spans` (one piece per span; every piece carries the band's name, the first piece also its groups as chips "{subject without the row's label when it is the same subject, else the subject} · {students}").
- A row whose label repeats the row above (a second band of the same subject) shows the label once, muted on the repeats.
- A click on any piece of a bar opens step 5 on "Groups and bands", at the band's level if that view filters by level, and scrolls the band's lane into view. For a head this works too (step 5 is theirs).
- On step 5's "Groups and bands" view, beside its level choice: a button "See how {level} is banded" (or "See how the levels are banded" when no level is chosen) that opens step 2 on Bands at that level.
- With no class at the level, or no lesson rows yet: one line saying so, in the page's words.
- On a narrow window the grid scrolls sideways inside its card; the label column stays in place.

- [ ] **Step 1: Write `classesBands()`, its handlers and styles**, replacing Task 3's placeholder line.

- [ ] **Step 2: Run every page-side suite**

Run: `node --check static/app.js && for f in tests/*.test.js; do node $f | tail -1; done && .venv/bin/python tests/smoke.py 2>/dev/null | tail -1`
Expected: every line ends "passed"; smoke 89.

- [ ] **Step 3: README**: one sentence on the band picture under step 2, and that step 5 links to it.

- [ ] **Step 4: Browser check on a scratch server** (the secondary sample, committee; then a head), written into the task report:
  1. Bands shows one column per class of the chosen level; whole-class subjects are cells in every class that takes them; each band of the sample is a bar across the classes step 5 lists for it, with its groups and sizes.
  2. On step 5, give a band's first and third class only: its bar is in two pieces, each named. Make a second band of the same subject on a class the first has: it sits on a second line under the same label.
  3. A click on a bar opens step 5's "Groups and bands" with that band in view. The button there comes back to step 2's Bands at that level.
  4. Rename a band to `Sec 1 <i>Opt` on step 5: the bar shows it as typed.
  5. As a head: the picture shows, the level picker works, a click on a bar opens step 5.
  6. A fresh blank setup (no classes): each view says there is nothing yet; no console error.
  7. Time it on a school-sized setup: open the newest CTSS workbook copy the controller provides on the scratch server (never committed), and note in the report how long step 2 takes to draw in each view (counts and milliseconds only).

- [ ] **Step 5: Commit**

```bash
git add static/app.js static/style.css README.md
git commit -m "feat(classes): the band picture on step 2, linked both ways with step 5's groups and bands"
```

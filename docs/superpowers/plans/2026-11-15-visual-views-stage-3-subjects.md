# Visual views, stage 3: one card per subject (step 3) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Step 3 (Subjects) gets a second view, Cards, where a subject and its G-levels are one card: the name and code are typed once, a tick box per G-level makes or removes that subject, and one small grid holds the periods.

**Architecture:** A new pure module `static/subjectview.js` (`SubjectView`) groups the setup's subject rows into cards by department and makes the few changes a card needs (tick, untick, a new name, a value for every row, add, remove); Node tests pin it. `static/app.js` draws the cards and wires them. The data stays what it is today, one subject row per G-level, so nothing but the page changes: no workbook, reader, server or skill change.

**Tech Stack:** Vanilla JS in the browser (no build step), Node for the module's tests.

**Spec:** `docs/superpowers/specs/2026-11-15-visual-setup-views-design.md` (stage 3 and "Across all four stages"). Stage 2's plan and notes, for the patterns to repeat: `docs/superpowers/plans/2026-11-15-visual-views-stage-2-venues.md`, `…-stage-2-notes.md`. Branch `visual-views-stage-3`, from `main` at e91f46a.

## Global Constraints

- The Table view of step 3 is today's table, character for character: its code moves into `subjectsTable()` and nothing in it changes.
- Nothing outside the page changes. `git diff --stat main` names only `static/subjectview.js`, `static/app.js`, `static/style.css`, `static/index.html`, `tests/subjectview.test.js`, `README.md` and files under `docs/`. No file under `ttgen/` or `skill/`, no `.py` file, and the skill's version stays `2026-11.4`.
- The data stays one subject row per G-level. Nothing new is stored: no card, no group key, no new field on a row. A setup from before this stage shows as cards with nothing converted.
- A subject made by a tick is named exactly the card's name, one space, the tag ("Mathematics G3"), with that tag as the row's tag: what is typed in the table today.
- Ticking never renames a row, with the two exceptions the spec names: the first tag of a plain subject no lesson uses (its one row takes the tag), and the last tag unticked (its one row loses it).
- One set of data: a periods cell, and a row's own room kind or lesson length, are the table's own `data-k` paths. Each action on a card (a tick, an untick, a name, a code, a department, a room kind, a lesson length, add, delete) is one save and one Undo step, followed by the same `save(); render(); poll();` the table's changes use.
- The view is remembered per person in the browser (`ttsetup.view.subjects`), and the step opens on Cards the first time.
- Department heads see both views and can change nothing on step 3; the view switch still works for them. Every new handler also checks `locked("subjects")` itself.
- Nothing can be done only by dragging (this stage has no dragging). Every box and button is reachable and usable from the keyboard.
- Everything a person typed is drawn through `esc()`, in text and in attributes. A department's name carried in an attribute for a handler is encoded with `encodeURIComponent`, as stage 2's `data-vadd` is.
- No new style rule may match an element that existed before: every new class name is new to `static/style.css` and `static/app.js` (grep each before using it; `scard`, `scol`, `sgrid`, `stags`, `sdept` or `sodd` is already taken somewhere, so this plan's names start with `sj`).
- The school's size: 65 subject rows that make 38 cards in 11 departments, with 4 levels. The Cards view must draw and answer a change without a pause a person would notice.
- Sentences are plain and short, and name things as the page already does (Subject, Code, G-level through `tagLabel()`, Department, Room kind, Lesson length, Teaching groups).
- Tests, samples and documents use made-up names only. The school is "CTSS" or "the school". A run on the real setup reports counts only.
- Browser checks run on a scratch server with a scratch `DATA_DIR` and the README's example codes, never the repository's `data/`. No test or check calls a model API.
- Commits end with `Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>`. Nothing is pushed.

## Decisions this plan makes (to be checked on reading)

The spec leaves these open, or rests on something that is not so. Each is the plan writer's call.

1. **Asking before a removal.** The spec says the card asks "in the same words as the table". The table's Delete does not ask today: it removes the row and Undo takes it back. The card asks in its own words: before unticking a tag whose subject is on lesson rows, and always before deleting a whole card. The table is left as it is.
2. **The two changes in place.** Ticking the first tag of a plain subject that no lesson uses changes that one row (its name gains the tag, its periods stay): the same row, so another person's change to it at the same moment still lands. Unticking a card's last tag changes its one row back (the tag comes off the name and its periods are cleared). Every other tick adds a row and every other untick removes one.
3. **Where a new row goes and what it starts with.** Straight after the card's last row in the list, so the Table shows a subject's rows together. It takes the code, department, room kind and lesson length of the card's first row. Its periods are blank.
4. **"In use" means lesson rows**, as the spec says. A rule, a room's "For" or the Class Parents' list that names the subject is not counted; after a removal or a change of name they are left as the table leaves them.
5. **A Department box on the card.** The table can move a subject to another department; the card must not lose that.
6. **A plain row beside tagged rows** (the school's real setup has one such subject) has a tick box of its own, "no G-level", ticked. Unticking it removes that row. It cannot be ticked back on: the box goes with the row.
7. **A name comes first.** The tick boxes are off until the card has a name, and a card with a tag ticked cannot have its name emptied. Rows with no name never share a card.
8. **Rows shown as they are.** A row is a card of its own, with the table's own boxes, when its G-level is not the end of its name, when its G-level is not one of the school's, when it has no G-level and its name ends in one of the school's, or when a row before it has the same department, code, name and G-level. The card says which in one line.
9. **Order.** Tick boxes and grid rows follow the school's own order of tags (School & day). Cards in a column follow the list's order. Columns follow the school's order of departments, then any other department found on a row, then "No department yet".
10. **Columns wrap.** With 11 departments the columns wrap onto further rows; the page never scrolls sideways at a desk width.

## Review Focus

1. **Rows that fit no card.** A G-level that is not the end of the name, a tag the school no longer has, a plain row named like a tagged one, the same subject twice, a row with no name, a `null` row: every row shows on exactly one card and nothing throws. Pinned in Task 1 (`every_row_shows_on_exactly_one_card_whatever_it_is`).
2. **A tag is plain text.** A school's tag such as "G3+" or "(H)" is matched as typed, never as a pattern. Pinned in Task 1 (`a_tag_is_plain_text_not_a_pattern_and_a_school_with_no_tags_has_plain_cards`).
3. **The first tag of a subject that already has lessons.** The plain row stays, with its lessons, and the tagged row is added beside it; with no lessons the one row is changed and keeps its periods. Pinned in Task 2 (`the_first_tag_of_a_plain_subject_changes_its_row_when_no_lesson_uses_it_and_adds_one_when_lessons_do`).
4. **Places after a tick.** A row added in the middle of the list moves every row below it down one: every other row is still the same row in the same order, and a periods cell typed next lands on the row it shows. Pinned in Task 2 (`ticking_adds_the_row_named_name_and_tag_after_the_cards_last_row`) and checked in a browser in Task 4.
5. **Two people at once, and a head.** Two committee tabs tick the same G-level of one subject at the same moment: the second row shows as a card of its own that can be deleted, and nothing is lost. A head sees every card and can change nothing. Checked in a browser in Task 4.

---

### Task 1: The cards model

**Files:**
- Create: `static/subjectview.js`
- Test: `tests/subjectview.test.js`

**Interfaces:**
- Consumes: nothing but the setup (`spec.subjects`, `spec.lessons`, `spec.school.departments`, `spec.school.tags`, a list of `[tag, letter]` pairs in which `"-"` means no tag).
- Produces: `SubjectView.tags(spec)`, `SubjectView.columns(spec)`, `SubjectView.uses(spec, subject)`.

  ```js
  SubjectView.tags(spec) -> ["G3", "G2", "G1"]          // the school's tags in its order, each once, without "-" and empty ones
  SubjectView.uses(spec, subject) -> 2                   // how many lesson rows name exactly this subject; 0 for ""
  SubjectView.columns(spec) ->
  [{ dept: "Mathematics",
     cards: [{ ri: 0, dept: "Mathematics", code: "MA", name: "Mathematics", odd: "",
               rows: [{ ri: 0, tag: "G3", subject: "Mathematics G3", room_kind: "", lesson_length: null, lessons: 2, groups: 2 }],
               ticked: ["G3"], plain: null, same_kind: true, same_length: true }] }]
  ```

  Rules the tests pin:
  - Only rows of `spec.subjects` that are objects count; each appears on exactly one card, as one entry of that card's `rows`, with `ri` its index in the list.
  - A row's tag is its `tag`, trimmed; `"-"` and `""` mean none. Its name, code and department are trimmed text (`""` when absent).
  - A row with a tag belongs to a subject when the tag is one of the school's and the name is the tag alone or ends with a space and the tag; the subject's name is the rest, trimmed. A row with no tag belongs to the subject of its own name, unless that name is, or ends with a space and, one of the school's tags.
  - Any other row is a card of its own with `odd: "tag"`, `name` its full name, `ticked: []`, `plain: null`.
  - Rows are one card when they have the same department, the same code and the same subject name (compared exactly), and that name is not empty. A row with an empty subject name is a card of its own (`odd: ""`).
  - A row whose card already has a row with its tag is a card of its own with `odd: "twin"`.
  - A card's `ri`, `dept` and `code` are those of its first row in the list. Its `rows` are the row with no tag first, then the school's order of tags. `ticked` is its tags in that order; `plain` is the `ri` of its row with no tag, or `null`.
  - On a row: `room_kind` is text (`""` when none); `lesson_length` is a number or `null`; `lessons` is `uses` of its name; `groups` is the table's "Teaching groups" figure (a lesson row with a band or a code of its own counts once, any other once per class).
  - `same_kind` and `same_length` say whether every row of the card has the same room kind and the same lesson length.
  - Columns: the school's departments in its order, each present even with no card; then departments found only on rows, in first-seen order; then one column `dept: ""` when a row has none. Cards in a column are in the order of their `ri`.

- [ ] **Step 1: Write the failing tests**

`tests/subjectview.test.js`, in the style of `tests/venueview.test.js`:

```js
// Plain-assert tests for static/subjectview.js (step 3's Cards view): run with `node tests/subjectview.test.js`
const assert = require("assert");
const SubjectView = require("../static/subjectview.js");
let n = 0; const t = (name, f) => { f(); n++; };
const fixture = () => ({
  school: { departments: ["Mathematics", "Science", "PE & CCA", "Humanities"], tags: [["G3", "P"], ["G2", "A"], ["G1", "K"], ["-", ""]], levels: ["Sec 1", "Sec 2"] },
  subjects: [
    /*0*/ { _id: "s1", subject: "Mathematics G3", code: "MA", tag: "G3", dept: "Mathematics", room_kind: null, lesson_length: null, periods: { "Sec 1": 6, "Sec 2": 6 } },
    /*1*/ { _id: "s2", subject: "Mathematics G2", code: "MA", tag: "G2", dept: "Mathematics", periods: { "Sec 1": 6 } },
    /*2*/ { _id: "s3", subject: "PE", code: "PE", tag: "-", dept: "PE & CCA", room_kind: "pe venue", lesson_length: 2, periods: { "Sec 1": 4 } },
    /*3*/ { _id: "s4", subject: "Science G1", code: "SC", tag: "G1", dept: "Science", room_kind: "lab", periods: {} },
    /*4*/ { _id: "s5", subject: "Mathematics G1", code: "MA", tag: "G1", dept: "Mathematics", periods: {} },
    /*5*/ { _id: "s6", subject: "Science", code: "SC", tag: "-", dept: "Science", room_kind: "science room", lesson_length: 3, periods: { "Sec 1": 5 } },
    /*6*/ { _id: "s7", subject: "Science G3", code: "SC", tag: "G3", dept: "Science", room_kind: "lab", periods: {} },
    /*7*/ { _id: "s8", subject: "Art", code: "AR", tag: "", dept: "Aesthetics", periods: { "Sec 2": 2 } },
    /*8*/ { _id: "s9", subject: "CP Time", code: "CP", dept: null, periods: {} }],
  lessons: [{ level: "Sec 1", subject: "Mathematics G3", block: "1 Math", classes: ["1A", "1B"] }, { level: "Sec 1", subject: "Mathematics G3", block: "1 Math", classes: ["1A", "1B"] },
            { level: "Sec 1", subject: "Science", classes: ["1A", "1B", "1C"] }, { level: "Sec 1", subject: "PE", classes: ["1A"] },
            { level: "Sec 1", subject: "PE", classes: ["1B"], code_override: "PE1" }, null, { level: "Sec 1", subject: null }]
});
const all = s => SubjectView.columns(s).reduce((a, c) => a.concat(c.cards), []).sort((a, b) => a.ri - b.ri);   // every card, in the order of the list
const card = (s, name) => all(s).find(c => c.name === name);
const same = (s, f) => { const before = JSON.stringify(s); f(); assert.strictEqual(JSON.stringify(s), before); };
/* ---- the model ---- */
t("a_column_per_department_in_the_schools_order_then_the_others", () => {
  assert.deepStrictEqual(SubjectView.columns(fixture()).map(c => [c.dept, c.cards.map(k => k.name)]),
    [["Mathematics", ["Mathematics"]], ["Science", ["Science"]], ["PE & CCA", ["PE"]], ["Humanities", []], ["Aesthetics", ["Art"]], ["", ["CP Time"]]]);
  assert.deepStrictEqual(SubjectView.columns({}), []); assert.deepStrictEqual(SubjectView.columns({ subjects: [null] }), []);
  assert.deepStrictEqual(SubjectView.tags(fixture()), ["G3", "G2", "G1"]); assert.deepStrictEqual(SubjectView.tags({}), []);
});
t("a_card_is_the_rows_of_one_subject_with_its_g_levels_in_the_schools_order", () => {
  const row = (ri, tag, subject, lessons, groups) => ({ ri, tag, subject, room_kind: "", lesson_length: null, lessons, groups });
  assert.deepStrictEqual(card(fixture(), "Mathematics"), { ri: 0, dept: "Mathematics", code: "MA", name: "Mathematics", odd: "",
    rows: [row(0, "G3", "Mathematics G3", 2, 2), row(1, "G2", "Mathematics G2", 0, 0), row(4, "G1", "Mathematics G1", 0, 0)],
    ticked: ["G3", "G2", "G1"], plain: null, same_kind: true, same_length: true });
});
t("a_row_with_no_tag_beside_tagged_rows_is_on_the_same_card", () => {
  const k = card(fixture(), "Science");
  assert.deepStrictEqual([k.ri, k.plain, k.ticked, k.rows.map(r => [r.ri, r.tag])], [3, 5, ["G3", "G1"], [[5, ""], [6, "G3"], [3, "G1"]]]);
  assert.deepStrictEqual([k.same_kind, k.same_length, k.rows.map(r => r.room_kind), k.rows.map(r => r.lesson_length)], [false, false, ["science room", "lab", "lab"], [3, null, null]]);
  assert.deepStrictEqual([k.rows[0].lessons, k.rows[0].groups], [1, 3]);                                    // one whole-class lesson row of three classes
  const pe = card(fixture(), "PE");
  assert.deepStrictEqual([pe.ticked, pe.plain, pe.same_kind, pe.rows[0].lessons, pe.rows[0].groups, pe.rows[0].lesson_length], [[], 2, true, 2, 2, 2]);
});
t("every_row_shows_on_exactly_one_card_whatever_it_is", () => {
  const s = fixture();
  s.subjects.push({ subject: "Chemistry", tag: "G3", dept: "Science", code: "CH" },            // 9: its G-level is not the end of its name
                  { subject: "Physics G3", tag: "-", dept: "Science", code: "PH" },             // 10: its name ends in a G-level it does not have
                  { subject: "Biology Std", tag: "Std", dept: "Science", code: "BI" },          // 11: a tag the school does not have
                  { subject: "Mathematics G3", tag: "G3", dept: "Mathematics", code: "MA" },    // 12: the same subject twice
                  { subject: "", tag: "-", dept: "Mathematics", code: "" }, { subject: "", tag: "-", dept: "Mathematics", code: "" },   // 13, 14: two new cards with no name yet
                  { subject: "G2", tag: "G2", dept: "Mathematics", code: "" },                 // 15: a tag and no name
                  null, "x", {},                                                                // 16, 17 are not rows; 18 is a row with nothing in it
                  { subject: "  Geography   G3 ", tag: " G3 ", dept: " Humanities ", code: " GE " }, { subject: "Geography G2", tag: "G2", dept: "Humanities", code: "GE" });   // 19, 20
  const A = all(s), ris = A.reduce((a, c) => a.concat(c.rows.map(r => r.ri)), []).sort((a, b) => a - b);
  assert.deepStrictEqual(ris, [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 18, 19, 20]);
  const odd = A.filter(c => c.odd).map(c => [c.ri, c.odd, c.name, c.rows.length, c.ticked, c.plain]);
  assert.deepStrictEqual(odd, [[9, "tag", "Chemistry", 1, [], null], [10, "tag", "Physics G3", 1, [], null], [11, "tag", "Biology Std", 1, [], null], [12, "twin", "Mathematics G3", 1, [], null]]);
  assert.deepStrictEqual(A.filter(c => !c.name).map(c => [c.ri, c.odd, c.ticked, c.plain, c.dept]), [[13, "", [], 13, "Mathematics"], [14, "", [], 14, "Mathematics"], [15, "", ["G2"], null, "Mathematics"], [18, "", [], 18, ""]]);
  const g = card(s, "Geography"); assert.deepStrictEqual([g.ri, g.dept, g.code, g.ticked, g.rows.map(r => r.subject)], [19, "Humanities", "GE", ["G3", "G2"], ["Geography   G3", "Geography G2"]]);
  assert.strictEqual(card(s, "Mathematics").rows.length, 3);                                    // the twin did not join it
});
t("a_tag_is_plain_text_not_a_pattern_and_a_school_with_no_tags_has_plain_cards", () => {
  const s = { school: { tags: [["G3+", "P"], ["(H)", "H"], ["-", ""]] }, subjects: [{ subject: "Chinese (H)", tag: "(H)", code: "CL" }, { subject: "Chinese G3+", tag: "G3+", code: "CL" }, { subject: "ChineseG3+", tag: "G3+", code: "CL" }] };
  assert.deepStrictEqual(all(s).map(c => [c.name, c.odd, c.ticked]), [["Chinese", "", ["G3+", "(H)"]], ["ChineseG3+", "tag", []]]);
  const p = { school: { tags: [["-", ""]] }, subjects: [{ subject: "English", tag: "-" }, { subject: "English G3", tag: "G3" }] };
  assert.deepStrictEqual(all(p).map(c => [c.name, c.odd]), [["English", ""], ["English G3", "tag"]]);
});
t("how_many_lesson_rows_name_a_subject", () => {
  const s = fixture();
  assert.deepStrictEqual([SubjectView.uses(s, "Mathematics G3"), SubjectView.uses(s, "PE"), SubjectView.uses(s, "Art"), SubjectView.uses(s, ""), SubjectView.uses({}, "PE")], [2, 2, 0, 0, 0]);
});
console.log(n + " cases passed");
```

- [ ] **Step 2: Run it and see it fail**

Run: `node tests/subjectview.test.js`
Expected: FAIL with `Cannot find module '../static/subjectview.js'`

- [ ] **Step 3: Write `static/subjectview.js`**

Same shape as `static/venueview.js`: a header comment saying what it is and that it is pure; `var SubjectView = (function () { "use strict"; … return { tags: tags, columns: columns, uses: uses }; })();` and `if (typeof module !== "undefined") module.exports = SubjectView;`. Lookup tables keyed by typed names are `Object.create(null)` or a `Map`. A tag is compared as text (`slice`, `===`), never put into a `RegExp`. `spec`, `spec.school` and any list may be missing or not a list.

- [ ] **Step 4: Run the tests and see them pass**

Run: `node tests/subjectview.test.js`
Expected: `6 cases passed`

- [ ] **Step 5: Commit**

```bash
git add static/subjectview.js tests/subjectview.test.js
git commit -m "feat(subjects): the cards model: a subject and its G-levels as one card, by department"
```

---

### Task 2: The changes a card makes

**Files:**
- Modify: `static/subjectview.js`, `tests/subjectview.test.js`

**Interfaces:**
- Consumes: Task 1's cards (a card is found by any `ri` of its rows).
- Produces (each changes `spec.subjects` in place and asks nothing; the page asks before it calls):

  ```js
  SubjectView.tick(spec, ri, tag)   -> { ri, how: "changed" | "added" } | null
  SubjectView.untick(spec, ri, tag) -> { how: "removed" | "emptied" } | null      // tag "" is the card's row with no G-level
  SubjectView.rename(spec, ri, name) -> true | false
  SubjectView.set(spec, ri, field, value) -> true | false                         // field: "code" | "dept" | "room_kind" | "lesson_length"
  SubjectView.remove(spec, ri) -> 3                                               // how many rows went; 0 when there is no such card
  SubjectView.add(spec, dept) -> 9                                                // the new row's index
  ```

  Rules the tests pin:
  - `tick` returns `null` and changes nothing when there is no such card, the card is `odd`, it has no name, the tag is not one of the school's, or it is ticked already.
  - `tick` on a card whose only row has no tag and is named by no lesson row changes that row: `subject` becomes name, space, tag and `tag` the tag; everything else on the row stays, its periods too. Result `{ ri: <that row>, how: "changed" }`.
  - Any other `tick` puts a new row straight after the card's last row in the list: `{ subject, code, tag, dept, periods: {} }` with the code and department of the card's first row, plus `room_kind` and `lesson_length` when that first row has them. Result `{ ri: <the new row>, how: "added" }`.
  - `untick` returns `null` and changes nothing when there is no such card, the card is `odd`, the card has no row with that tag, or the tag is `""` and that row is the card's only row.
  - `untick` on a card with more than one row removes that row (`"removed"`). On a card whose only row has that tag it changes the row: `subject` the card's name, `tag` `"-"`, `periods` `{}` (`"emptied"`).
  - `rename` trims the name and gives every row of the card its new name (with its tag after a space when it has one). It returns `false` and changes nothing for no such card, an `odd` card, or an empty name on a card with a tag ticked. Lesson rows are not touched.
  - `set` stores the value as given on every row of the card; `false` and no change for no such card, an `odd` card, or any other field.
  - `remove` takes every row of the card out of the list. `add` puts `{ subject: "", code: "", tag: "-", dept: <the department, or null for "">, periods: {} }` at the end of the list (making the list when the setup has none).

- [ ] **Step 1: Add the failing tests** to `tests/subjectview.test.js`, before its last line:

```js
/* ---- the changes ---- */
t("ticking_adds_the_row_named_name_and_tag_after_the_cards_last_row", () => {
  const s = fixture(), before = s.subjects.slice();
  assert.deepStrictEqual(SubjectView.tick(s, 5, "G2"), { ri: 7, how: "added" });                             // Science: its rows are 3, 5 and 6
  assert.deepStrictEqual(s.subjects[7], { subject: "Science G2", code: "SC", tag: "G2", dept: "Science", periods: {}, room_kind: "lab" });   // room kind and lesson length as the card's first row has them
  assert.deepStrictEqual(s.subjects.filter(r => r !== s.subjects[7]), before);                              // every other row is the same row, in the same order
  assert.deepStrictEqual(card(s, "Science").rows.map(r => [r.ri, r.tag]), [[5, ""], [6, "G3"], [7, "G2"], [3, "G1"]]);
  assert.deepStrictEqual([card(s, "Art").ri, card(s, "CP Time").ri], [8, 9]);                               // the cards below moved down one place and are still themselves
});
t("the_first_tag_of_a_plain_subject_changes_its_row_when_no_lesson_uses_it_and_adds_one_when_lessons_do", () => {
  const s = fixture(), art = s.subjects[7], pe = s.subjects[2];
  assert.deepStrictEqual(SubjectView.tick(s, 7, "G3"), { ri: 7, how: "changed" });
  assert.strictEqual(s.subjects[7], art); assert.deepStrictEqual(art, { _id: "s8", subject: "Art G3", code: "AR", tag: "G3", dept: "Aesthetics", periods: { "Sec 2": 2 } });   // its periods came across
  assert.strictEqual(s.subjects.length, 9);
  assert.deepStrictEqual(SubjectView.tick(s, 2, "G3"), { ri: 3, how: "added" });                             // PE has lessons: it stays, as the row with no G-level
  assert.strictEqual(s.subjects[2], pe); assert.strictEqual(pe.subject, "PE");
  assert.deepStrictEqual(s.subjects[3], { subject: "PE G3", code: "PE", tag: "G3", dept: "PE & CCA", periods: {}, room_kind: "pe venue", lesson_length: 2 });
  assert.deepStrictEqual([card(s, "PE").plain, card(s, "PE").ticked], [2, ["G3"]]);
});
t("a_tick_that_cannot_be_made_changes_nothing", () => {
  const s = fixture(); s.subjects.push({ subject: "Chemistry", tag: "G3", dept: "Science", code: "CH" }, { subject: "", tag: "-", dept: "Science", code: "" });
  same(s, () => assert.deepStrictEqual([SubjectView.tick(s, 0, "G3"), SubjectView.tick(s, 0, "G9"), SubjectView.tick(s, 0, "-"), SubjectView.tick(s, 0, ""), SubjectView.tick(s, 9, "G2"), SubjectView.tick(s, 10, "G3"), SubjectView.tick(s, 99, "G3"), SubjectView.tick({}, 0, "G3")],
    [null, null, null, null, null, null, null, null]));   // ticked already; not one of the school's tags; a row shown as it is; a card with no name; no such row
});
t("unticking_removes_the_row_and_the_last_tag_leaves_the_subject_with_no_tag_and_no_periods", () => {
  const s = fixture(), g3 = s.subjects[0];
  assert.deepStrictEqual(SubjectView.untick(s, 0, "G2"), { how: "removed" });
  assert.deepStrictEqual(s.subjects.map(r => r.subject).slice(0, 4), ["Mathematics G3", "PE", "Science G1", "Mathematics G1"]);
  assert.deepStrictEqual(SubjectView.untick(s, 0, "G1"), { how: "removed" });
  assert.deepStrictEqual(SubjectView.untick(s, 0, "G3"), { how: "emptied" });
  assert.strictEqual(s.subjects[0], g3); assert.deepStrictEqual(g3, { _id: "s1", subject: "Mathematics", code: "MA", tag: "-", dept: "Mathematics", room_kind: null, lesson_length: null, periods: {} });
  const m = fixture(); assert.deepStrictEqual(SubjectView.untick(m, 3, ""), { how: "removed" });              // Science's row with no G-level
  assert.deepStrictEqual([card(m, "Science").plain, card(m, "Science").ticked, m.subjects.length], [null, ["G3", "G1"], 8]);
  const z = fixture(); same(z, () => assert.deepStrictEqual([SubjectView.untick(z, 2, ""), SubjectView.untick(z, 0, "G9"), SubjectView.untick(z, 2, "G3"), SubjectView.untick(z, 99, "G3")], [null, null, null, null]));   // PE's only row is the card; tags not on the card; no such row
});
t("a_name_a_code_a_department_a_room_kind_or_a_lesson_length_goes_to_every_row_of_the_card", () => {
  const s = fixture(), lessons = JSON.stringify(s.lessons);
  assert.strictEqual(SubjectView.rename(s, 4, "  Maths "), true);
  assert.deepStrictEqual([0, 1, 4].map(i => s.subjects[i].subject), ["Maths G3", "Maths G2", "Maths G1"]);
  assert.strictEqual(JSON.stringify(s.lessons), lessons);                                                    // the lessons keep the name they had, as after a change of name in the table
  same(s, () => assert.strictEqual(SubjectView.rename(s, 0, "  "), false));                                  // a subject with G-levels needs a name
  assert.strictEqual(SubjectView.rename(s, 2, ""), true); assert.strictEqual(s.subjects[2].subject, "");     // one with none may lose it
  assert.strictEqual(SubjectView.set(s, 0, "code", "MT"), true); assert.deepStrictEqual([0, 1, 4].map(i => s.subjects[i].code), ["MT", "MT", "MT"]);
  assert.strictEqual(SubjectView.set(s, 3, "room_kind", "lab"), true); assert.strictEqual(SubjectView.set(s, 3, "lesson_length", null), true);
  assert.deepStrictEqual([card(s, "Science").same_kind, card(s, "Science").same_length], [true, true]);
  assert.strictEqual(SubjectView.set(s, 0, "dept", "Science"), true);
  assert.deepStrictEqual(SubjectView.columns(s).slice(0, 2).map(c => [c.dept, c.cards.map(k => k.name)]), [["Mathematics", []], ["Science", ["Maths", "Science"]]]);
  same(s, () => assert.deepStrictEqual([SubjectView.set(s, 0, "subject", "x"), SubjectView.set(s, 0, "periods", {}), SubjectView.set(s, 99, "code", "x"), SubjectView.rename(s, 99, "x")], [false, false, false, false]));
  const o = fixture(); o.subjects.push({ subject: "Chemistry", tag: "G3", dept: "Science", code: "CH" });
  same(o, () => assert.deepStrictEqual([SubjectView.rename(o, 9, "Chemistry G3"), SubjectView.set(o, 9, "code", "X")], [false, false]));   // a row shown as it is is changed through the table's own boxes
});
t("a_card_is_removed_with_all_its_rows_and_a_new_one_starts_empty_in_its_department", () => {
  const s = fixture();
  assert.strictEqual(SubjectView.remove(s, 1), 3); assert.deepStrictEqual(s.subjects.map(r => r.subject), ["PE", "Science G1", "Science", "Science G3", "Art", "CP Time"]);
  assert.strictEqual(SubjectView.remove(s, 99), 0); assert.strictEqual(s.subjects.length, 6);
  assert.strictEqual(SubjectView.add(s, "Humanities"), 6); assert.deepStrictEqual(s.subjects[6], { subject: "", code: "", tag: "-", dept: "Humanities", periods: {} });
  assert.strictEqual(SubjectView.add(s, ""), 7); assert.strictEqual(s.subjects[7].dept, null);
  const e = {}; assert.strictEqual(SubjectView.add(e, "Science"), 0); assert.strictEqual(e.subjects.length, 1);
});
```

- [ ] **Step 2: Run them and see them fail**

Run: `node tests/subjectview.test.js`
Expected: FAIL with `SubjectView.tick is not a function`

- [ ] **Step 3: Write the six functions** in `static/subjectview.js` and add them to what it returns. One helper finds the card that holds a row's index; each function works out the card afresh from the setup it is given.

- [ ] **Step 4: Run the tests and see them pass**

Run: `node tests/subjectview.test.js`
Expected: `12 cases passed`

- [ ] **Step 5: Commit**

```bash
git add static/subjectview.js tests/subjectview.test.js
git commit -m "feat(subjects): a card's changes: tick and untick a G-level, a name or a value for every row, add and remove"
```

---

### Task 3: Step 3's view switch and the Cards view, with its periods grid

**Files:**
- Modify: `static/index.html` (load `subjectview.js` after `venueview.js`)
- Modify: `static/app.js` (`VIEWS.subjects`, the click handler, `headLocks`)
- Modify: `static/style.css`
- Modify: `README.md` (the test list; step 3's paragraph)

**Interfaces:**
- Consumes: `SubjectView.columns(S.spec)`, `SubjectView.tags(S.spec)` (Task 1); in `app.js`: `VIEWS.subjects()` (near line 1205), `issues()` and `rowCls(out, crit, "subjects", ri)`, `inp`/`sel`, `esc`, `levels()`, `tagLabel()`, `sc()`, `locked("subjects")`, and stage 2's step 1 code as the pattern (`VENUEVIEW`, `VV`, `data-vview`, `venuesTable()`, the `headLocks` exemptions).
- Produces (Task 4 relies on these names):
  - `const SUBJECTVIEW = "ttsetup.view.subjects"` and `const SV = { view: "cards" }`; `SV.view` is `"cards"` or `"table"`, read from `localStorage` at load (anything else means `"cards"`), written on a switch, both inside try/catch.
  - The switch: `<div class="row switch">` with two buttons `data-sview="cards|table"`, labelled Cards and Table, at the top right of the step's card as on step 1. A click sets `SV.view`, stores it and re-renders. On a locked step these buttons stay usable (`headLocks` exempts `data-sview`).
  - `subjectsTable()`: today's table and its "+ Add subject" button, unchanged.
  - `subjectsCards()`: the Cards view.
  - A card is `<div class="sjcard …" data-scard="{card.ri}">`. In it: the name box `<input id="sjname-{ri}" data-sname>`, the code box `<input id="sjcode-{ri}" data-sset="code">`, `<select id="sjdept-{ri}" data-sset="dept">`, `<select id="sjkind-{ri}" data-sset="room_kind">`, `<input type="number" id="sjlen-{ri}" data-sset="lesson_length">`, one `<input type="checkbox" id="sjtick-{ri}-{n}" data-stick="{tag}">` per school tag (`n` its place in `SubjectView.tags`; the "no G-level" box is `id="sjtick-{ri}-plain" data-stick=""`), a `<button data-sremove>` and, at each column's foot, `<button data-sadd="{encodeURIComponent(dept)}">`. The ids let the page keep the keyboard's place across a redraw, as it does for any box with an id.
  - Each grid row is `<tr id="subjects-{row.ri}">`, the id a Things to fix message scrolls to; its periods cells are `inp("spec.subjects.{row.ri}.periods.{level}", …, "number")`, the table's own path.

What the Cards view shows (the spec's "Cards" list is the authority):
- The step's opening paragraph stays above both views and gains one sentence: "On Cards, a subject and its G-levels are one card: type the name once and tick the G-levels." (through `tagLabel()`, so a primary school reads "level tags").
- One column per entry of `SubjectView.columns`: the department's name ("No department yet" for `""`) and "{n} subjects"; its cards one under another; "+ Add a subject" at its foot. Columns sit side by side, each at least about 340px wide, and wrap onto further rows.
- With no subject and no department: one line, "No subjects yet. Add one here, or switch to Table.", and one "+ Add a subject" button (`data-sadd=""`).
- A card:
  - the name ("Subject name" as its placeholder) and the code, then Delete;
  - a tick box per school tag, labelled with the tag, ticked when the card has that row; first of them, only when the card has a row with no tag beside tagged rows, a box "no G-level" (`data-stick=""`), ticked. A school with no tags has no boxes. While the card has no name the tag boxes are off, with the title "Give the subject a name first.";
  - the periods grid: a heading row of the levels; a row per row of the card, labelled with its tag ("no G-level" for the plain row of a card that also has tagged rows; no label on a card's only row when it has no tag), a periods cell per level, and at the row's end the Teaching groups figure with the table's own title text;
  - Department, Room kind and Lesson length for the card. When the card's rows differ in room kind or in lesson length: the line "The G-levels differ in room kind or lesson length: each has its own below.", and that value is shown on each grid row instead, through the table's own paths (`sel("spec.subjects.{row.ri}.room_kind", …)`, `inp("spec.subjects.{row.ri}.lesson_length", …, "number")`);
  - a card with a row under Things to fix carries the worst mark of its rows (`rowCls`), the grid row its own mark, and the messages are listed under the grid.
- A row shown as it is (`odd`): one card with the table's own boxes for that row (`inp`/`sel` on `spec.subjects.{ri}.subject`, `.code`, `.tag`, `.dept`, `.room_kind`, `.lesson_length` and the periods cells), no tick boxes, and one line: for `"tag"`, "This row's name and its G-level do not match, so it is shown as it is. Make them match and it joins its subject's card."; for `"twin"`, "Another row has this name and G-level. Delete one of the two."
- In this task the name, code, Department, Room kind and Lesson length boxes of a card, its tick boxes, "+ Add a subject" and Delete are drawn and do nothing yet (Task 4 wires them). The periods cells, a row's own room kind and lesson length, and every box of a row shown as it is already work: they are the table's paths.

- [ ] **Step 1: Move the table into `subjectsTable()` and add the switch**; `VIEWS.subjects()` chooses by `SV.view`. Load `subjectview.js` in `index.html`.

- [ ] **Step 2: Check nothing else moved**

Run: `node --check static/app.js && .venv/bin/python tests/smoke.py 2>/dev/null | tail -1`
Expected: no syntax error; `90 checks passed`

- [ ] **Step 3: Write `subjectsCards()` and its styles** (new class names only, each grepped first in `static/style.css` and `static/app.js`).

- [ ] **Step 4: Run every page-side suite**

Run: `node --check static/app.js && for f in tests/*.test.js; do node $f | tail -1; done && .venv/bin/python tests/smoke.py 2>/dev/null | tail -1`
Expected: every line ends "passed"; `subjectview.test.js` 12; smoke 90.

- [ ] **Step 5: README**: add `node tests/subjectview.test.js          # step 3's subject cards` to the test list, and two sentences on step 3's two views.

- [ ] **Step 6: Browser check on a scratch server** (the secondary sample school, committee; then a head), written into the task report:
  1. Step 3 opens on Cards; the number of grid rows over all cards equals the number of rows in the Table; the choice survives a reload.
  2. A subject with three G-levels is one card with three boxes ticked and three grid rows; a subject with none is one card with one row and nothing ticked.
  3. Type a number in a periods cell on a card: the Table shows it in the same row and level; Undo takes it back in one step. Tab moves from cell to cell without losing its place.
  4. In the Table, give two rows of one subject different room kinds: on Cards its card says they differ and shows each row's own; set one back and the card shows one value again.
  5. In the Table, set a row's G-level to one its name does not end with: on Cards that row is a card of its own with the line that says why, and the table's own boxes on it work.
  6. Rename a department on School & day to `Sci <b>&"x` and a subject to `Art <i>1"x`: both show as typed in both views.
  7. A subject with no periods at any level (a Things to fix message): its card and its grid row are marked, the message shows on the card, and a click on the message in the panel scrolls to it.
  8. As a department head: both views show and switch, every box on a card is disabled, and "Only the committee can change this step." shows.
  9. Step 1's Blocks view, step 2's three views and School & day look as before (no style of this task reaches them), and the console has no error.

- [ ] **Step 7: Commit**

```bash
git add static/index.html static/app.js static/style.css README.md
git commit -m "feat(subjects): step 3 in two views; a subject and its G-levels as one card with one periods grid"
```

---

### Task 4: Changing subjects from the cards

**Files:**
- Modify: `static/app.js`, `static/style.css`, `README.md` (one sentence)

**Interfaces:**
- Consumes: Task 3's `SV`, `subjectsCards()` and its `data-s…` names; `SubjectView.tick`, `.untick`, `.rename`, `.set`, `.remove`, `.add`, `.columns` (Tasks 1 and 2); in `app.js`: the `change` handler (how a number box's value becomes a number or `null`, near line 1617), the table's delete (`unpick(); save(); render();`, near line 1480), `toast`, `confirm` as the page already uses it, `locked("subjects")`.
- Produces: the handlers for `data-sname`, `data-sset`, `data-stick`, `data-sremove` and `data-sadd`. Each finds its card by `closest("[data-scard]")`, returns at once when `locked("subjects")`, and ends with `save(); render(); poll();` when it changed something.

What it does (the spec's stage 3 list is the authority):
- **The name.** A change calls `SubjectView.rename`. When it is refused, the old name is drawn again and a toast says "A subject with G-levels needs a name."
- **Code, Department, Room kind, Lesson length.** A change calls `SubjectView.set` with the value as the table would store it (a number box gives a number, or `null` when empty; an empty choice gives `null`). After a change of department the card is in its new column and is scrolled into view.
- **Ticking a G-level** calls `SubjectView.tick`. The new row's periods are blank.
- After a tick or an untick the keyboard is put back on that card's box for that tag, found again after the redraw (a card's `ri` changes when its first row is the one removed).
- **Unticking a G-level**, or "no G-level": when lesson rows name that subject (`row.lessons`), the page asks first: "{subject} is on {n} lesson row(s) of step 5. Take it off step 3? Those lessons keep the name and show it as not on the list until they are given a subject. Undo takes it back." On Cancel the box is drawn ticked again and nothing changes. Then `SubjectView.untick`.
- **Delete** always asks: "Remove {name}?" for a card of one row, "Remove {name} and its {n} G-levels?" for more, "Remove this subject?" for a card with no name, each followed, when lesson rows name any of its subjects, by " {m} lesson row(s) of step 5 use it." (or "them") and then " Undo takes it back." Then `SubjectView.remove`.
- **"+ Add a subject"** calls `SubjectView.add` with the column's department; the new card's name box has the keyboard.
- Each of these is one Undo step. After any of them the Table shows the same rows the cards do.
- On a locked step (a head) none of them does anything, and every box and button but the view switch is disabled.

- [ ] **Step 1: Write the handlers** for the name, the four values, the tick boxes, Delete and "+ Add a subject".

- [ ] **Step 2: Run every suite**

Run: `node --check static/app.js && for f in tests/*.test.js; do node $f | tail -1; done && .venv/bin/python tests/smoke.py 2>/dev/null | tail -1`
Expected: every line ends "passed"; `subjectview.test.js` 12; smoke 90.

Run: `.venv/bin/python tests/smoke.py --full 2>/dev/null | tail -1 && git diff --stat main | grep -v "static/\|tests/subjectview.test.js\|README.md\|docs/" | grep "|"`
Expected: `91 checks passed`, and the second command prints nothing (no other file changed).

- [ ] **Step 3: README**: one sentence on making a subject with its G-levels from a card.

- [ ] **Step 4: Browser check on a scratch server** (the secondary sample, committee, two tabs; then a head), written into the task report:
  1. "+ Add a subject" in a department: an empty card with the keyboard in its name. Type "Drama", then the code "DR", then tick the three G-levels: the Table has "Drama G3", "Drama G2" and "Drama G1", one after another, each with code DR, that department and its G-level. Each step is one Undo.
  2. Type periods on the card's three rows: each lands in the Table on the row it shows. Then tick a G-level on a subject higher up the page and type a period on a card lower down: it lands on the right row.
  3. A subject with no G-level and no lessons: tick a tag. Its one row now carries the tag and still has its periods; the Table has no extra row.
  4. A subject with no G-level that has lessons on step 5: tick a tag. The card shows "no G-level" ticked beside the new tag, and step 5's lessons are untouched.
  5. Untick a G-level that lessons use: the question names the subject and the number of lesson rows. Cancel leaves the box ticked and everything as it was. OK removes the row; step 5 shows those lessons' subject as not on the list; one Undo brings the row back.
  6. Untick a card's last G-level: the card stays, with nothing ticked and no periods. Delete a whole card: it asks, the rows go, one Undo brings them back.
  7. Change a card's name: every row has the new name with its tag. Empty the name of a card with a G-level ticked: the old name comes back with the toast. Change the code, the room kind and the lesson length: every row has them. Change the department: the card moves to that column and is in view.
  8. Two committee tabs: tick the same G-level of one subject in both before either has polled. Afterwards one tab's row is on the card and the other shows as a card of its own with the line "Another row has this name and G-level."; deleting it leaves the subject whole.
  9. Two committee tabs: delete a subject high in the list in one. In the other, after the poll, type a number in a periods cell of a card lower down: it lands on the subject and level the cell shows.
  10. As a head: every box and button on a card is disabled, the view switch works, and the setup's version does not change.
  11. No console error at any point.

- [ ] **Step 5: Commit**

```bash
git add static/app.js static/style.css README.md
git commit -m "feat(subjects): make and change a subject and its G-levels from its card"
```

---

## At the whole-branch review

On the school's real setup (counts only, nothing shown): 65 subject rows make 38 cards in 11 departments (20 cards of one row, 9 of two, 9 of three); one card has a plain row beside tagged rows; no row is shown as it is; every row is on exactly one card. On a copy, ticking then unticking a G-level on each card leaves the list of rows as it was. The Cards view's drawing time and a tick's time on the real page are measured and written down. A workbook written from a setup changed only through the cards reads back the same subject rows as the same changes typed in the Table.

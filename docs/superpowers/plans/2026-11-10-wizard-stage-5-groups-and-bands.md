# Wizard stage 5: creating groups and bands on the map — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A head makes teaching groups and bands on step 5 without the table: a "Groups and bands" view where a new group's code and a new band's name form by themselves, bands are lanes, and groups or whole classes are ticked or dragged into them.

**Architecture:** The rules go in a new plain script, `static/groups.js` (global `Groups`, no page access, tested under Node): the band-name suggestion, the group code a new row will get (the same numbering `lessonInfo()` uses), making a group, a band or one row per class, moving rows into and out of a band, and the "which codes change" check that protects a student list. `static/app.js` gets the third view of step 5: a form for a new teaching group, a form for a new band, the bands page (lanes on the right, the pool of unbanded rows on the left). Nothing new is stored: groups are `lessons[]` rows with `block`, bands are `blocks[]`, names and codes are the fields the workbook already has.

**Tech Stack:** vanilla JavaScript with no build step, HTML5 drag and drop (as stage 4), Node for the tests. No server change.

**Spec:** `docs/superpowers/specs/2026-11-09-setup-wizard-design.md`: "Step 5: Department map (2D)" → "Creating groups and bands", and "School and day: naming patterns".

## Global Constraints

- No framework, no bundler, no new package. `static/groups.js` is a fifth plain script, loaded by `static/index.html` after `map.js` and before `app.js`. It defines one global, `Groups`, never touches `document`, `window`, `S` or `Math.random`, and ends with `if (typeof module !== "undefined") module.exports = Groups;`.
- Every change to the setup goes through `save()`; nothing is written while drawing. One Add, move or drop is one `save()`: one sync, one Undo entry.
- Group codes stay as today: level digit + subject code + G-level letter (`school.tags`) + running number, numbered in row order per level and subject (`lessonInfo()` in app.js is the authority; `Groups.codes` must give the same answer and a browser check compares them). "Keep code" (`code_override`) stays for old codes.
- Band names are suggested, never forced: the box is editable, and a name already used at that level is refused.
- Heads may do everything here (the server allows every change to `lessons` and `blocks`: `sync.head_split`). Nothing is committee-only on this view.
- `ttgen/` is not edited. Rows keep the fields the workbook reader knows: `level, subject, block, classes, teachers, students, code_override, periods_override, pattern`, and bands `block, level, classes, everyone, note`.
- Stage 4's map and the table view are not reshaped; the table stays the place for the 15-column bulk edits.
- Works on a laptop and a tablet in landscape; ticking and clicking is the first way to do everything, dragging a second.
- Names, codes and classes in tests, samples and docs are made up. The repository is public: never commit `.claude/launch.json` or `data/`.
- Wording: plain sentences, sentence case, no "please", no exclamation marks. Step numbers stay today's.
- Tests: `node tests/groups.test.js`, `node tests/map.test.js`, `node tests/people.test.js`, `node tests/sync.test.js`, `.venv/bin/python tests/smoke.py`, `.venv/bin/python tests/test_sync.py`, and `node --check static/app.js`. Page checks in the browser preview against a scratch `DATA_DIR`, never the repository's `data/`; the secondary sample (22 bands, 194 lesson rows) is the test school.
- Commit on branch `wizard-stage-5` after each task. Do not push or open a pull request until the committee asks.

## Review Focus

1. Moving a group out of a band, or a whole class into one, renumbers the later groups of that subject at that level (`1MAP3` becomes `1MAP2`); when a student list names the old codes, the page must say which codes change and how many students are affected before it writes, and never renumber silently. Pinned in Task 2 (`shift`) and Task 4.
2. A new band typed with a name already used at that level, in other capitals or with extra spaces → refused with the existing name; the suggestion skips letters already taken ("Sec 3 Option A" exists → "Sec 3 Option B"). Pinned in Task 1.
3. A new group whose band is for another level → refused and the row is not added; a group with a band and no classes picked takes the band's classes. Pinned in Task 2.
4. The code shown in the form before Add is the code the table shows after Add, even when groups of that subject already exist in other bands of the level. Pinned in Task 1 (`codes` against the fixture) and Task 3's browser check (`Groups.codes` against `lessonInfo()` on the sample).
5. A whole-class row that lists several classes dropped on a band → one group with those classes, the band's classes widened to include them, no class lost. Pinned in Task 2.

---

### Task 1: Names and codes

**Files:**
- Create: `static/groups.js`, `tests/groups.test.js`
- Modify: `static/index.html` (load `groups.js` after `map.js`)

**Interfaces:**
- Produces: `Groups.untag(name: string) -> string` — the subject name without a trailing level-of-study tag (`G1`, `G2`, `G3`, `Std`, `Fdn`, `Standard`, `Foundation`), trimmed: `"English Language G3"` → `"English Language"`. (`app.js`'s `untag` becomes a call to it.)
- Produces: `Groups.bandName(level: string, subjects: string[], existing: string[]) -> string` — one subject family (all `untag` to the same name): `"<level> <family>"`; several families: `"<level> Option <letter>"`, the first of A, B, C… not used by a name in `existing` (compared trimmed, ignoring case). No subjects: `"<level> Band"`. A one-family name already in `existing` gets `" 2"`, `" 3"`… appended until free.
- Produces: `Groups.codes(spec) -> string[]` — one per `spec.lessons` row, exactly as `lessonInfo()` in app.js: `code_override` when set; `"Entire Class"` for a row with no `block`; else `<last character of level><subject code or "??"><letter for the subject's tag from school.tags><n>`, `n` counting rows of that level and subject that have a block, in row order; `""` for a row with no subject.
- Produces: `Groups.codeFor(spec, level, subject, block) -> string` — the code a row appended now would get: `"Entire Class"` with no `block`, else the pattern above with `n` = (rows of that level and subject with a block) + 1; `""` when `level` or `subject` is blank.

- [ ] **Step 1: Write `tests/groups.test.js`** (plain `assert`, prints `N cases passed`):

```js
const assert = require("assert");
const Groups = require("../static/groups.js");
let n = 0; const t = (name, f) => { f(); n++; };
const fixture = () => ({
  school: { levels: ["Sec 1", "Sec 2"], departments: ["MA", "EL"], tags: [["G3", "P"], ["G2", "A"], ["G1", "K"], ["-", ""]] },
  classes: [{ class: "1A", level: "Sec 1", size: 30 }, { class: "1B", level: "Sec 1", size: 32 }, { class: "1C", level: "Sec 1", size: 31 }, { class: "2A", level: "Sec 2", size: 30 }],
  subjects: [{ subject: "Mathematics G3", code: "MA", tag: "G3", dept: "MA", periods: { "Sec 1": 6, "Sec 2": 6 } }, { subject: "Mathematics G2", code: "MA", tag: "G2", dept: "MA", periods: { "Sec 1": 6 } },
             { subject: "English Language G3", code: "EL", tag: "G3", dept: "EL", periods: { "Sec 1": 6 } }, { subject: "Art", code: "AR", tag: "-", dept: "AE", periods: { "Sec 1": 2 } }, { subject: "Music", code: "MU", tag: "-", dept: "AE", periods: { "Sec 1": 2 } }],
  teachers: [{ _id: "ta", name: "Arjun Nair", dept: "MA", can_teach: [{ subject: "Mathematics G3", levels: "All" }] }],
  blocks: [{ _id: "b1", block: "Sec 1 Mathematics", level: "Sec 1", classes: ["1A", "1B"] }, { _id: "b2", block: "Sec 1 Option A", level: "Sec 1", classes: ["1A", "1B", "1C"], everyone: false }],
  lessons: [{ _id: "l1", level: "Sec 1", subject: "Mathematics G3", block: "Sec 1 Mathematics", classes: ["1A", "1B"], teachers: ["Arjun Nair"], students: 30 },
            { _id: "l2", level: "Sec 1", subject: "Mathematics G3", block: "Sec 1 Option A", classes: ["1A", "1B", "1C"], teachers: [], students: 20 },
            { _id: "l3", level: "Sec 1", subject: "Mathematics G2", block: "Sec 1 Mathematics", classes: ["1A", "1B"], teachers: [], students: 32 },
            { _id: "l4", level: "Sec 1", subject: "Art", block: null, classes: ["1A", "1B"], teachers: [], students: 62 },
            { _id: "l5", level: "Sec 1", subject: "Art", block: null, classes: ["1C"], teachers: [], students: 31 },
            { _id: "l6", level: "Sec 1", subject: "Music", block: null, classes: ["1C"], teachers: [], students: 9, code_override: "1MU1" },
            { _id: "l7", level: "Sec 1", subject: "", block: null, classes: [], teachers: [] }],
  rules: [], students: [{ id: "s1", name: "Student One", class: "1A", groups: ["1MAP1"] }, { id: "s2", name: "Student Two", class: "1B", groups: ["1MAP2", "1MAA1"] }, { id: "s3", name: "Student Three", class: "1C", groups: [] }], roles: [] });

t("untag strips the level-of-study tag", () => {
  assert.strictEqual(Groups.untag("English Language G3"), "English Language"); assert.strictEqual(Groups.untag("Mathematics Fdn "), "Mathematics");
  assert.strictEqual(Groups.untag("Art"), "Art");
});
t("a band's suggested name: one family, several families, letters and numbers already taken", () => {
  assert.strictEqual(Groups.bandName("Sec 2", ["Mathematics G3", "Mathematics G2"], []), "Sec 2 Mathematics");
  assert.strictEqual(Groups.bandName("Sec 3", ["Geography", "Literature in English"], []), "Sec 3 Option A");
  assert.strictEqual(Groups.bandName("Sec 3", ["Geography", "Literature in English"], ["sec 3 option a ", "Sec 3 Option B"]), "Sec 3 Option C");
  assert.strictEqual(Groups.bandName("Sec 1", ["Mathematics G3"], ["Sec 1 Mathematics"]), "Sec 1 Mathematics 2");
  assert.strictEqual(Groups.bandName("Sec 1", [], []), "Sec 1 Band");
});
t("codes: as the table numbers them, per level and subject in row order", () => {
  assert.deepStrictEqual(Groups.codes(fixture()), ["1MAP1", "1MAP2", "1MAA1", "Entire Class", "Entire Class", "1MU1", ""]);
});
t("the code a new row would get", () => {
  assert.strictEqual(Groups.codeFor(fixture(), "Sec 1", "Mathematics G3", "Sec 1 Option A"), "1MAP3");
  assert.strictEqual(Groups.codeFor(fixture(), "Sec 1", "English Language G3", "Sec 1 Option A"), "1ELP1");
  assert.strictEqual(Groups.codeFor(fixture(), "Sec 1", "Art", null), "Entire Class");
  assert.strictEqual(Groups.codeFor(fixture(), "", "Art", "Sec 1 Option A"), "");
});
console.log(`${n} cases passed`);
```

- [ ] **Step 2: Run** `node tests/groups.test.js` → fails with `Cannot find module '../static/groups.js'`.
- [ ] **Step 3: Implement `static/groups.js`** with the functions under Interfaces, and add `<script src="/static/groups.js"></script>` to `static/index.html` after `map.js`. In app.js, `const untag = s => Groups.untag(s);`.
- [ ] **Step 4: Run** `node tests/groups.test.js` → `4 cases passed`; `node --check static/app.js` clean; the other test commands unchanged.
- [ ] **Step 5: Commit** — `git add static/groups.js static/index.html static/app.js tests/groups.test.js && git commit -m "Groups and bands: band names and group codes as plain functions"`

---

### Task 2: Making and moving

**Files:**
- Modify: `static/groups.js`, `tests/groups.test.js`

**Interfaces:**
- Consumes: Task 1's `codes`, `bandName`.
- Produces: `Groups.newGroup(spec, f) -> { i: number } | { error: string }`, `f = { level, subject, block, classes, students }`:
  - blank `level` or `subject` → `{ error: "Pick a level and a subject." }`;
  - `block` given but no band of that name → `{ error: "There is no band called <block>." }`; a band of another level → `{ error: "<block> is a <its level> band, not <level>." }`;
  - `classes` empty: with a band, the band's classes; without, `{ error: "Pick the classes." }`;
  - otherwise pushes `{ level, subject, block: block || null, classes: [...], teachers: [], students: Number(students) || null }` onto `spec.lessons` and returns its index.
- Produces: `Groups.addOnePerClass(spec, level, subject, classes) -> number` — one whole-class row (`block: null`, `students` = the class's size) per class in `classes` that has no whole-class row of that subject (no `block`, no `code_override`) listing it yet; returns how many were added.
- Produces: `Groups.newBand(spec, f) -> { i } | { error }`, `f = { block, level, classes, everyone }`: blank name → `"Give the band a name."`; a band whose name matches once trimmed, inner runs of spaces made one, ignoring case → `"<existing name> exists already."`; no level → `"Pick a level."`; no classes → `"Pick the band's classes."`; else pushes `{ block (trimmed), level, classes: [...], everyone: !!everyone }` and returns its index.
- Produces: `Groups.toBand(spec, lis: number[], block) -> { moved: number, skipped: number, widened: string[] }` — each row of the band's level gets `block`; a row of another level is skipped; the band's `classes` gains every class of the moved rows it lacked (`widened`), in row order.
- Produces: `Groups.fromBand(spec, li) -> boolean` — sets the row's `block` to `null`; false when the row has none.
- Produces: `Groups.shift(spec, fn) -> { changes: [[id, from, to]][], students: number }` — runs `fn` on a deep copy of `spec`, compares `codes` before and after by row `_id` (rows without an id are skipped), and counts the students whose `groups` name a code that changed. The real `spec` is untouched.

- [ ] **Step 1: Add the failing cases to `tests/groups.test.js`** (before the final `console.log`):

```js
t("a new group: fields, the band's classes by default, and refusals", () => {
  const s = fixture(); const r = Groups.newGroup(s, { level: "Sec 1", subject: "Mathematics G3", block: "Sec 1 Option A", classes: [], students: "18" });
  assert.deepStrictEqual(r, { i: 7 }); assert.deepStrictEqual(s.lessons[7], { level: "Sec 1", subject: "Mathematics G3", block: "Sec 1 Option A", classes: ["1A", "1B", "1C"], teachers: [], students: 18 });
  assert.deepStrictEqual(Groups.newGroup(s, { level: "", subject: "Art" }), { error: "Pick a level and a subject." });
  assert.deepStrictEqual(Groups.newGroup(s, { level: "Sec 2", subject: "Mathematics G3", block: "Sec 1 Mathematics", classes: ["2A"] }), { error: "Sec 1 Mathematics is a Sec 1 band, not Sec 2." });
  assert.deepStrictEqual(Groups.newGroup(s, { level: "Sec 1", subject: "Art", block: "Nope", classes: ["1A"] }), { error: "There is no band called Nope." });
  assert.deepStrictEqual(Groups.newGroup(s, { level: "Sec 1", subject: "Art", block: "", classes: [] }), { error: "Pick the classes." });
  assert.strictEqual(s.lessons.length, 8);
});
t("one row per class, skipping classes that have the subject already", () => {
  const s = fixture(); assert.strictEqual(Groups.addOnePerClass(s, "Sec 1", "Art", ["1A", "1B", "1C"]), 0);
  assert.strictEqual(Groups.addOnePerClass(s, "Sec 1", "Music", ["1A", "1B", "1C"]), 3);
  assert.deepStrictEqual(s.lessons.slice(7).map(x => [x.classes, x.students, x.block]), [[["1A"], 30, null], [["1B"], 32, null], [["1C"], 31, null]]);
});
t("a new band: name, duplicates, level and classes", () => {
  const s = fixture(); assert.deepStrictEqual(Groups.newBand(s, { block: " Sec 1 English ", level: "Sec 1", classes: ["1A", "1B", "1C"], everyone: true }), { i: 2 });
  assert.deepStrictEqual(s.blocks[2], { block: "Sec 1 English", level: "Sec 1", classes: ["1A", "1B", "1C"], everyone: true });
  assert.deepStrictEqual(Groups.newBand(s, { block: "sec 1  mathematics", level: "Sec 1", classes: ["1A"] }), { error: "Sec 1 Mathematics exists already." });
  assert.deepStrictEqual(Groups.newBand(s, { block: "", level: "Sec 1", classes: ["1A"] }), { error: "Give the band a name." });
  assert.deepStrictEqual(Groups.newBand(s, { block: "Sec 1 Science", level: "", classes: ["1A"] }), { error: "Pick a level." });
  assert.deepStrictEqual(Groups.newBand(s, { block: "Sec 1 Science", level: "Sec 1", classes: [] }), { error: "Pick the band's classes." });
  assert.strictEqual(s.blocks.length, 3);
});
t("into a band: whole classes become groups, the band's classes widen, other levels are skipped", () => {
  const s = fixture(); s.lessons.push({ _id: "l8", level: "Sec 2", subject: "Mathematics G3", block: null, classes: ["2A"], teachers: [], students: 30 });
  const r = Groups.toBand(s, [3, 4, 7], "Sec 1 Mathematics");
  assert.deepStrictEqual(r, { moved: 2, skipped: 1, widened: ["1C"] });
  assert.deepStrictEqual([s.lessons[3].block, s.lessons[4].block, s.lessons[7].block], ["Sec 1 Mathematics", "Sec 1 Mathematics", null]);
  assert.deepStrictEqual(s.blocks[0].classes, ["1A", "1B", "1C"]); assert.deepStrictEqual(s.lessons[3].classes, ["1A", "1B"]);   // the shared row is one group of two classes
  assert.deepStrictEqual(Groups.codes(s).slice(3, 5), ["1AR1", "1AR2"]);
});
t("out of a band, and what moving renumbers", () => {
  const s = fixture(); assert.strictEqual(Groups.fromBand(s, 3), false);
  const r = Groups.shift(s, c => Groups.fromBand(c, 0));
  assert.deepStrictEqual(r, { changes: [["l1", "1MAP1", "Entire Class"], ["l2", "1MAP2", "1MAP1"]], students: 2 });
  assert.strictEqual(s.lessons[0].block, "Sec 1 Mathematics");   // the real setup is untouched
  assert.strictEqual(Groups.fromBand(s, 0), true); assert.strictEqual(s.lessons[0].block, null);
  assert.deepStrictEqual(Groups.shift(s, c => Groups.toBand(c, [4], "Sec 1 Mathematics")), { changes: [["l5", "Entire Class", "1AR1"]], students: 0 });
});
```

- [ ] **Step 2: Run** `node tests/groups.test.js` → fails at "a new group…" with `Groups.newGroup is not a function`.
- [ ] **Step 3: Implement** the functions under Interfaces in `static/groups.js`.
- [ ] **Step 4: Run** `node tests/groups.test.js` → `9 cases passed`.
- [ ] **Step 5: Commit** — `git add static/groups.js tests/groups.test.js && git commit -m "Groups and bands: making a group, a band or one row per class, and moving rows between bands"`

---

### Task 3: The "Groups and bands" view: new group, new band

**Files:**
- Modify: `static/app.js` (`VIEWS.lessons` switch, new `VIEWS.groups`, events), `static/style.css`

**Interfaces:**
- Consumes: `Groups.codeFor`, `bandName`, `newGroup`, `addOnePerClass`, `newBand`; stage 4's `M` (view switch, `M.view`), `avatarOf`, `listing`, `sel`, `opt`, `chips`/`openPop` (the classes picker), `subj`, `levels`, `blockNames`.
- Produces: `M.view` gains `"groups"`; the switch at the top of step 5 shows **Map · Groups and bands · Table** (`data-mview="groups"`); the stored choice (`localStorage` `"ttsetup.mapview"`) accepts it.
- Produces: form state `M.gf = { level, tag: "", subject: "", block: "", classes: [], students: "" }` and `M.bf = { level, subjects: [], classes: [], name: "", everyone: true, touched: false }` (`touched`: the name was typed, so the suggestion stops replacing it), both reset when their level changes (`gf.level` defaults to the first level; `bf.classes` to every class of its level).
- Produces: hooks: `#gfLevel #gfTag #gfSubject #gfBlock #gfStudents` (selects and a number box), `data-gfclasses` (a chips picker using the existing `openPop` "classes" pop-up with `data-level`, path `_gf.classes`: `getPath` and `setPath` gain one branch, a path starting `_gf.` reads and writes `M.gf` and `_bf.` `M.bf`; `commitPop` re-renders without `save()` for those paths), `data-gfadd` (Add), `data-gfeach` (Add one per class); `#bfLevel`, `data-bfsubject="<subject>"` (toggle a subject into the band's list, drawn as chips with ✕), `data-bfclasses`, `#bfName`, `#bfEveryone`, `data-bfadd`.
- Produces: `VIEWS.groups()` returns `<div class="gb"><section class="gforms card">…two forms…</section><section class="gpool card"></section><section class="glanes card"></section></div>` (the two empty sections are Task 4's).

- [ ] **Step 1: The switch.** Add `"groups"` to the switch in `VIEWS.lessons` (label "Groups and bands", between Map and Table) and to `mapAction("mview")`; `VIEWS.lessons` draws `VIEWS.groups()` for it.
- [ ] **Step 2: New teaching group** (top of `.gforms`): level (`levels()`), G-level (`sc().tags` first elements, blank = any; filters the subject list to subjects with that `tag`), subject (subjects with periods at the level, as the table filters them), band (`S.spec.blocks` of that level, blank = whole class), classes (chips picker; placeholder "the band's classes" when a band is picked and none chosen), students (number, optional, placeholder "all"). Under the fields a line **Code: `<Groups.codeFor(...)>`** that re-draws on every change (`"Entire Class"` reads "whole class, no code"). Buttons: **Add** → `Groups.newGroup`; an `error` is a `toast`; success → `save(); render()`, toast "Added `<code>` `<subject>` for `<classes>`.", the form keeps level, G-level, subject and band and clears classes and students (so the next group of the same band is two clicks). **Add one per class** (shown only when no band is picked) → `Groups.addOnePerClass` for the picked classes, or every class of the level when none picked; toast "`N` rows added." or "Every class has `<subject>` already."
- [ ] **Step 3: New band** (below): level; subjects — a select "add a subject…" that appends to `M.bf.subjects` (drawn as chips with ✕; same filter by level as above); classes (chips picker, default every class of the level); name — a text box pre-filled with `Groups.bandName(level, subjects, blockNames())` and replaced on every change of level or subjects until the box is typed in (`touched`); "Everyone takes one" tick box (default on; off when the suggestion says Option). **Add** → `Groups.newBand`; error → toast; success → `save(); render()`, the new group form's band select is set to the new band and its level matched, toast "Band `<name>` added. Add its groups above, or move rows into it below."
- [ ] **Step 4: Events** in the existing document `click`/`change`/`input` listeners: the ids and `data-` hooks under Interfaces; typing in `#bfName` sets `touched`. `commitPop` gains the `_gf.`/`_bf.` branch (no `save()` for those paths).
- [ ] **Step 5: CSS**: `.gb{display:grid;grid-template-columns:300px 1fr 1fr;gap:12px;align-items:start}`, `@media (max-width:1100px){.gb{grid-template-columns:1fr 1fr}.gb .gforms{grid-column:1/-1}}`, `.gforms .f{display:block;margin-bottom:8px}`, `.codeline{font-family:ui-monospace,monospace;background:var(--chip);border-radius:6px;padding:4px 8px;display:inline-block}`.
- [ ] **Step 6: Check in the browser preview** (committee, secondary sample as a practice copy, scratch `DATA_DIR`): `Groups.codes(S.spec)` equals `lessonInfo().map(x => x.code)` on the sample (run in the console, compare with `JSON.stringify`); the switch shows three views and the choice survives a reload; new group: pick Sec 1 · G3 · English Language G3 · band Sec 1 English → the code line reads `1ELP4` (three exist) and after Add the table view shows a row with that code; picking band Sec 2 Mathematics with level Sec 1 is impossible (the band select lists Sec 1 bands only) and `Groups.newGroup` with a mismatched band (from the console) says so; Add one per class for Art at Sec 1 with no classes picked → "Every class has Art already." (the sample has it) and for a subject with no rows → 4 rows; new band: Sec 3 + Geography + Literature → the suggested name is `Sec 3 Option A` (the sample's option bands are X and Y, so A is free); typing a name used at that level → refused; after Add the group form's band select shows the new band; one Undo per Add. As a head (role set from the console): the same, no read-only notice.
- [ ] **Step 7: Run** `node --check static/app.js` and the six test commands → pass. **Commit** — `git add static/app.js static/style.css && git commit -m "Step 5: the Groups and bands view, with a new group's code and a new band's name forming by themselves"`

---

### Task 4: The bands page: lanes and the pool

**Files:**
- Modify: `static/groups.js`, `tests/groups.test.js`, `static/app.js`, `static/style.css`

**Interfaces:**
- Consumes: Task 2's `toBand`, `fromBand`, `shift`; stage 4's `DeptMap.cards(spec, info, dept, "bands", level)` is *not* used (lanes here cover every department); `avatarOf`; the drag pattern from stage 4 (`dragstart`/`dragover`/`drop` listeners: extend `dropZone` and the drop handler for `[data-glane]`).
- Produces: `Groups.lanes(spec, level) -> [{ bi, block, level, classes, everyone, groups: [{ li, code, subject, classes, students, teachers }], twice: string[] }]` — the bands of `level` (all levels when `""`), in `blocks` order, each with its rows in row order; `twice` = names on two or more of its groups.
- Produces: `Groups.pool(spec, level, subject) -> [{ li, kind: "class" | "group", code, title, subject, classes, students }]` — rows with no `block` and a subject, of `level` (all when `""`) and `subject` (all when `""`), in row order; `kind` is `"group"` when `code_override` is set, else `"class"`; `title` = classes joined with ", " + " · " + subject.
- Produces: page state `M.gp = { level: first level, subject: "", ticked: new Set() of lesson _ids }`; hooks `#gpLevel #gpSubject`, `data-gtick="<id>"`, `data-gall`, `data-gnone`, `#gpTo` (band select, the lanes of the level), `data-gmove` (Move into band), `data-glane="<block>"` (lane: drop target), `data-gout="<li>"` (✕ on a group in a lane: back to the pool), `data-gdrag="<id>"` on pool rows.
- Produces: `moveRows(lis, block)` and `rowOut(li)` in app.js: each first calls `Groups.shift(S.spec, c => …)`; when `changes` is not empty and `students > 0` → `confirm("This renumbers <k> group code(s): 1MAP3 → 1MAP2, … <students> students' group lists name the old codes and will need updating on the Students step. Go on?")` (list capped at 4 with "and N more"); when `changes` is not empty and no student is affected → the toast after the move says "Codes changed: 1MAP3 → 1MAP2 …". Then the real move, `save(); render()`, and the toast (`"Moved N into <band>."` with `widened` as "<band> now also covers 1C." and `skipped` as "N rows of another level were left.").

- [ ] **Step 1: Add the failing cases to `tests/groups.test.js`**:

```js
t("lanes: each band of the level with its groups and anyone on two of them", () => {
  const s = fixture(); s.lessons[1].teachers = ["Arjun Nair"];
  const L = Groups.lanes(s, "Sec 1");
  assert.deepStrictEqual(L.map(l => [l.block, l.groups.map(g => g.code), l.twice]), [["Sec 1 Mathematics", ["1MAP1", "1MAA1"], []], ["Sec 1 Option A", ["1MAP2"], []]]);
  s.lessons[2].teachers = ["Arjun Nair"]; assert.deepStrictEqual(Groups.lanes(s, "Sec 1")[0].twice, ["Arjun Nair"]);
  assert.deepStrictEqual(Groups.lanes(s, "Sec 2"), []); assert.strictEqual(Groups.lanes(s, "").length, 2);
});
t("the pool: unbanded rows of the level, by subject", () => {
  assert.deepStrictEqual(Groups.pool(fixture(), "Sec 1", "").map(p => [p.li, p.kind, p.code, p.title]), [[3, "class", "Entire Class", "1A, 1B · Art"], [4, "class", "Entire Class", "1C · Art"], [5, "group", "1MU1", "1C · Music"]]);
  assert.deepStrictEqual(Groups.pool(fixture(), "Sec 1", "Music").map(p => p.li), [5]); assert.deepStrictEqual(Groups.pool(fixture(), "Sec 2", ""), []);
});
```

- [ ] **Step 2: Run** `node tests/groups.test.js` → fails with `Groups.lanes is not a function`. **Implement** `lanes` and `pool`; run → `11 cases passed`.
- [ ] **Step 3: The pool** (`.gpool`): level select (`#gpLevel`, defaults to the form's level), subject select (`#gpSubject`, subjects present in the pool at that level), **Select all shown** / **Deselect all**, then one row per pool item: tick box (`data-gtick`), a drag handle (`draggable="true" data-gdrag`), the title, code (for a `group`), students. Under the list: "Move into band" `#gpTo` (lanes of the level) + button `data-gmove` → `moveRows(ticked indexes, band)`. Empty pool: "Every row at `<level>` is in a band."
- [ ] **Step 4: The lanes** (`.glanes`): one `.lane` per `Groups.lanes(S.spec, M.gp.level)`: name, level, classes, "everyone takes one" tag, the line "Its groups have lessons at the same time." in grey, the `twice` line in red ("`<name>` is on two groups of this band: a band's groups meet at the same time"), then its groups: code, subject, classes, students, teacher avatars (24 px), ✕ `data-gout` → `rowOut(li)`. The lane is a drop target (`data-glane`); the drop handler reads the dragged ids (ticked rows when the dragged one is ticked, else just it — the stage 4 rule) and calls `moveRows`. No bands at the level: "No bands at `<level>` yet. Add one on the left."
- [ ] **Step 5: CSS**: `.gpool .prow{display:flex;gap:8px;align-items:center;padding:4px 2px;border-bottom:1px solid var(--line)}`, `.gpool .prow.on{background:#eef5ff}`, `.glanes .lane.over{background:#eef5ff;border-left-color:var(--accent)}`, `.glanes .grow{display:flex;gap:8px;align-items:center;padding:3px 0}`, `.handle{cursor:grab;color:var(--muted)}`; the pool and lanes lists get class `keep` and `max-height:calc(100vh - 300px);overflow:auto`.
- [ ] **Step 6: Check in the browser preview** (sample, practice copy): the Sec 1 pool lists the whole-class rows (Literature, Art…) by subject; tick the four Sec 1 Art rows and Move into band → the lane gains four groups coded `1AR1`…`1AR4`, the band's classes line now covers all four classes, Subjects' Teaching groups count for Art is still 4, one Undo; ✕ on `1AR2` → back in the pool, and the toast says `1AR3 → 1AR2, 1AR4 → 1AR3`; with a student list (the sample has one): move a group out of `Sec 1 English` → the question names the codes and the number of students, Cancel leaves everything, OK moves it; drop a pool row on a lane (synthetic drag events are acceptable) → moved; a teacher placed on two groups of one band (map view) shows the red line on that lane. As a head: the same.
- [ ] **Step 7: Run** `node --check static/app.js` and the six test commands → pass. **Commit** — `git add static/groups.js tests/groups.test.js static/app.js static/style.css && git commit -m "Step 5: the bands page, lanes and the pool, with a warning before codes change"`

---

### Task 5: README and the notes

**Files:**
- Modify: `README.md`

- [ ] **Step 1:** In the README's step 5 section, after the map paragraphs: the **Groups and bands** view — the new-group form (the code forms as you pick; Add one per class), the new-band form (the name forms from level and subjects: "Sec 2 Mathematics", "Sec 3 Option A"; editable; Everyone takes one), the bands page (pool on the left, lanes on the right; tick or drag rows into a band; a whole class moved in becomes a group; ✕ puts a group back; the page says which codes change and asks first when a student list names them), and that the table view remains for bulk edits. Keep the heads' table row current (nothing new is committee-only).
- [ ] **Step 2:** Read it back against the page once: every button name in the README exists on the page with that wording.
- [ ] **Step 3: Commit** — `git add README.md && git commit -m "Docs: creating groups and bands on step 5"`

---

## Not in this plan

Stage 6 (constraints, typed rules, first and second choices). Stage 4's deferred minors (notes file of 2026-11-10) stay deferred unless a task here touches the same line.

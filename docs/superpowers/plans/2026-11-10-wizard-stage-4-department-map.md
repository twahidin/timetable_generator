# Wizard stage 4: the department map — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Step 5 becomes a map a department head can work on without the table: tick teachers on the left, click (or drag them to) a subject basket in the middle to say what they can teach, click (or drag them to) a class, group or band card on the right to deploy them, and open a teacher's profile from any avatar.

**Architecture:** What the map reads and writes is worked out in a new plain script, `static/map.js` (global `DeptMap`, no page access, tested under Node): the roster of a department, the baskets, the cards, each teacher's load, and the rules of a deployment (basket first, at most three teachers, add never replace, a shared whole-class row splits when one class changes). `static/app.js` gets the screen: step 5 opens on the map with a "Table" switch to today's 15-column table (unchanged, still the view for bulk edits). Nothing new is stored: baskets are `teachers[].can_teach`, cards are `lessons[]` rows, bands are `blocks[]`. Every change goes through `save()`, so it syncs, merges and undoes as every other change does, and the server's heads' rules (`sync.head_split`) already allow everything the map writes.

**Tech Stack:** vanilla JavaScript with no build step, HTML5 drag and drop, Node for the tests, Flask untouched except one smoke test.

**Spec:** `docs/superpowers/specs/2026-11-09-setup-wizard-design.md`, section "Step 5: Department map (2D)" (the "Creating groups and bands" part is stage 5, not this plan) and the "Access" table.

## Global Constraints

- No framework, no bundler, no new package. `static/map.js` is a fourth plain script, loaded by `static/index.html` after `people.js` and before `app.js`. It defines one global, `DeptMap`, never touches `document`, `window`, `S` or `Math.random`, takes the setup and whatever it needs as arguments, and ends with `if (typeof module !== "undefined") module.exports = DeptMap;`.
- Every change to the setup goes through `save()`; nothing is written while drawing. One click or drop is one `save()`: one sync, one Undo entry.
- Teachers are named in `lessons[].teachers` by name, as today; the map addresses teachers by their row's `_id` (never by index) so a change from another browser cannot move a tick onto someone else.
- `ttgen/` is not edited; the workbook and the skill's copy stay as they are. The map is a view over the existing fields only: `teachers[].can_teach` (`{subject, levels}`), `lessons[]` (`level, subject, block, classes, teachers, students, code_override, periods_override, pattern`), `blocks[]`.
- Heads: the server already allows a head every change the map makes (lessons, blocks, `can_teach`, adding a teacher, editing a provisional teacher). The page mirrors it: a head's new teacher is provisional (as `addRow` does today), and a head cannot edit a confirmed teacher's details anywhere on the map.
- Works on a laptop and a tablet in landscape. Ticking and clicking is the first way to do everything; dragging is a second way, never the only one.
- Names, departments and codes in tests, samples and docs are made up. The repository is public: never commit `.claude/launch.json` or `data/`.
- Step numbers stay today's; the step is still `lessons` in `STEPS`, labelled "5 Department map". Wording in the page: plain sentences, sentence case, no "please", no exclamation marks.
- Tests: `node tests/map.test.js`, `node tests/people.test.js`, `node tests/sync.test.js`, `.venv/bin/python tests/smoke.py`, `.venv/bin/python tests/test_sync.py`, and `node --check static/app.js`. Page checks in the browser preview against a scratch `DATA_DIR`, never the repository's `data/`; the secondary sample opened as a practice copy is the test school (52 teachers in 9 departments, 194 lesson rows).
- Commit on branch `wizard-stage-4` after each task. Do not push or open a pull request until the committee asks.

## Review Focus

1. A whole-class lesson row listing several classes ("1A, 1B, 1C, 1D · Literature") when a head deploys a teacher to 1B's card → only 1B changes: it becomes its own row with the old teachers plus the new one, the other three classes keep theirs, and the total periods of the subject do not change. Pinned in Task 2.
2. Two teachers dropped on a card that already has two → none is added and the card says so; dropping one who is already on the card adds nothing and says nothing is wrong. Pinned in Task 2.
3. A teacher taken out of a subject's basket while still deployed to a group of it → the group keeps the teacher (nothing is removed quietly), the question says how many lessons will then be flagged, and Things to fix shows them. Pinned in Task 2.
4. "+ New teacher" with a name already in the setup, differently spaced or capitalised → refused with the existing teacher named; nothing is added. Pinned in Task 2.
5. Another browser removes or renames a teacher the map has ticked or open in the profile → the tick and the profile go quietly, nothing else changes, no error. Pinned in Task 1 (`prune`) and Task 5.

---

### Task 1: What the map shows

**Files:**
- Create: `static/map.js`, `tests/map.test.js`
- Modify: `static/index.html` (load `map.js` after `people.js`)

**Interfaces:**
- Consumes: `People.key(name)` (from `static/people.js`); under Node, `map.js` takes it with `typeof People !== "undefined" ? People : require("./people.js")`.
- Consumes: `info`, the array `lessonInfo()` in `app.js` returns, one entry per `spec.lessons` row with `p` (periods a cycle), `tp` (periods the row costs a teacher: `p` per class for a whole-class row), `code` (`"Entire Class"` for a whole-class row).
- Produces: `DeptMap.loads(spec, info) -> { [name]: { lessons, duties, allowance, total, over } }` — `lessons` = sum of `info[i].tp` over the rows naming the teacher, `duties` = `Number(other_duties) || 0`, `allowance` = `Number(allowance) || null`, `total = lessons + duties`, `over = allowance !== null && total > allowance`. Every teacher in `spec.teachers` has an entry.
- Produces: `DeptMap.deptSubjects(spec, dept) -> string[]` — subjects whose `dept` is `dept`, in Subjects order.
- Produces: `DeptMap.roster(spec, dept, extraIds) -> number[]` — indexes of the teachers whose `dept` is `dept`, in setup order, then those in `extraIds` (an array of `_id`) not already there, in setup order. Unknown ids are ignored.
- Produces: `DeptMap.unplaced(spec, idxs) -> number[]` — the given indexes whose teacher has no `can_teach` entry with a subject.
- Produces: `DeptMap.search(spec, q, dept) -> number[]` — indexes of teachers *not* in `dept` whose name or short name contains `q` (both through `People.key`), at most 8; `[]` for a blank `q`.
- Produces: `DeptMap.baskets(spec, dept) -> [{ subject, teachers: number[] }]` — one per `deptSubjects`, `teachers` = indexes of every teacher (any department) with that subject in `can_teach`, in setup order.
- Produces: `DeptMap.staffRoom(spec, idxs) -> number[]` — same as `unplaced` (the middle column's name for it).
- Produces: `DeptMap.cards(spec, info, dept, tab, level) -> card[]`, rows with a blank subject skipped, only rows whose subject is in `deptSubjects(spec, dept)`, and when `level` is not `""` only rows of that level:
  - `tab === "classes"`: one card per class of every whole-class row (`!block && !code_override`): `{ kind: "class", li, cls, title: cls, subject, level, periods: info[li].p, teachers: string[] }`, ordered by level (as `spec.school.levels`), then class, then subject.
  - `tab === "groups"`: one per row with `block` or `code_override`: `{ kind: "group", li, title: info[li].code, subject, level, periods: info[li].p, teachers, block }`, in row order.
  - `tab === "bands"`: one per `spec.blocks` row that has a group card of this department: `{ kind: "band", bi, title: block, level, groups: card[] (the group cards with that block), twice: string[] }` — `twice` = names on two or more of its groups.
  - `teachers` is `(row.teachers || []).filter(Boolean)`.
- Produces: `DeptMap.prune(ids, spec) -> string[]` — the ids in `ids` that are still a teacher's `_id`.

- [ ] **Step 1: Write `tests/map.test.js`** (plain `assert`, prints `N cases passed`), with this fixture at the top and the cases below:

```js
const assert = require("assert");
const DeptMap = require("../static/map.js");
let n = 0; const t = (name, f) => { f(); n++; };
const fixture = () => ({
  school: { levels: ["Sec 1", "Sec 2"], departments: ["MA", "EL"], bands: {} },
  classes: [{ class: "1A", level: "Sec 1", size: 30 }, { class: "1B", level: "Sec 1", size: 30 }, { class: "2A", level: "Sec 2", size: 30 }],
  subjects: [{ subject: "Mathematics", code: "MA", dept: "MA", periods: { "Sec 1": 6, "Sec 2": 6 } }, { subject: "English Language", code: "EL", dept: "EL", periods: { "Sec 1": 6 } }],
  teachers: [{ _id: "ta", name: "Arjun Nair", short: "Arjun", dept: "MA", role: "EO", allowance: 20, can_teach: [{ subject: "Mathematics", levels: "All" }] },
             { _id: "tb", name: "Priya Menon", short: "Priya", dept: "MA", role: "HOD", allowance: 12, other_duties: 4, can_teach: [] },
             { _id: "tc", name: "Wei Lin Tan", short: "Wei Lin", dept: "EL", role: "EO", allowance: 20, can_teach: [{ subject: "English Language", levels: "All" }, { subject: "Mathematics", levels: "Sec 1" }] },
             { _id: "td", name: "Hafiz Osman", short: "Hafiz", dept: "EL", role: "EO", allowance: 20, can_teach: [] }],
  blocks: [{ _id: "b1", block: "Sec 2 Mathematics", level: "Sec 2", classes: ["2A"] }],
  lessons: [{ _id: "l1", level: "Sec 1", subject: "Mathematics", block: null, classes: ["1A", "1B"], teachers: ["Arjun Nair"], students: 30 },
            { _id: "l2", level: "Sec 2", subject: "Mathematics", block: "Sec 2 Mathematics", classes: ["2A"], teachers: ["Arjun Nair"], students: 15 },
            { _id: "l3", level: "Sec 2", subject: "Mathematics", block: "Sec 2 Mathematics", classes: ["2A"], teachers: ["Arjun Nair", "Wei Lin Tan"], students: 15 },
            { _id: "l4", level: "Sec 1", subject: "English Language", block: null, classes: ["1A"], teachers: [], students: 30 }],
  rules: [], students: [], roles: [{ role: "EO", allowance: 20 }, { role: "HOD", allowance: 12 }] });
const infoOf = spec => spec.lessons.map((x, i) => ({ p: 6, tp: 6 * (x.block ? 1 : x.classes.length), code: x.block ? `2MA${i}` : "Entire Class" }));

t("loads: periods deployed plus other duties against the allowance", () => {
  const L = DeptMap.loads(fixture(), infoOf(fixture()));
  assert.deepStrictEqual(L["Arjun Nair"], { lessons: 24, duties: 0, allowance: 20, total: 24, over: true });
  assert.deepStrictEqual(L["Priya Menon"], { lessons: 0, duties: 4, allowance: 12, total: 4, over: false });
  assert.strictEqual(L["Hafiz Osman"].total, 0);
});
t("roster: the department's teachers in setup order, then the visitors", () => {
  assert.deepStrictEqual(DeptMap.roster(fixture(), "MA", []), [0, 1]);
  assert.deepStrictEqual(DeptMap.roster(fixture(), "MA", ["td", "ta", "nobody"]), [0, 1, 3]);
  assert.deepStrictEqual(DeptMap.unplaced(fixture(), [0, 1, 3]), [1, 3]);
});
t("search finds teachers of other departments by name or short name", () => {
  assert.deepStrictEqual(DeptMap.search(fixture(), "wei", "MA"), [2]);
  assert.deepStrictEqual(DeptMap.search(fixture(), "arjun", "MA"), []);
  assert.deepStrictEqual(DeptMap.search(fixture(), "  ", "MA"), []);
});
t("baskets: one per subject of the department, with teachers from any department", () => {
  assert.deepStrictEqual(DeptMap.baskets(fixture(), "MA"), [{ subject: "Mathematics", teachers: [0, 2] }]);
  assert.deepStrictEqual(DeptMap.staffRoom(fixture(), [0, 1]), [1]);
});
t("classes tab: one card per class of a whole-class row, in level then class order", () => {
  const c = DeptMap.cards(fixture(), infoOf(fixture()), "MA", "classes", "");
  assert.deepStrictEqual(c.map(x => [x.kind, x.li, x.cls, x.periods, x.teachers]), [["class", 0, "1A", 6, ["Arjun Nair"]], ["class", 0, "1B", 6, ["Arjun Nair"]]]);
  assert.deepStrictEqual(DeptMap.cards(fixture(), infoOf(fixture()), "EL", "classes", "Sec 2"), []);
});
t("groups and bands tabs", () => {
  const g = DeptMap.cards(fixture(), infoOf(fixture()), "MA", "groups", "");
  assert.deepStrictEqual(g.map(x => [x.kind, x.li, x.title, x.block]), [["group", 1, "2MA1", "Sec 2 Mathematics"], ["group", 2, "2MA2", "Sec 2 Mathematics"]]);
  const b = DeptMap.cards(fixture(), infoOf(fixture()), "MA", "bands", "");
  assert.strictEqual(b.length, 1); assert.strictEqual(b[0].kind, "band"); assert.strictEqual(b[0].groups.length, 2);
  assert.deepStrictEqual(b[0].twice, ["Arjun Nair"]);
  assert.deepStrictEqual(DeptMap.cards(fixture(), infoOf(fixture()), "EL", "bands", ""), []);
});
t("prune keeps only ids that are still teachers", () => { assert.deepStrictEqual(DeptMap.prune(["tb", "gone", "ta"], fixture()), ["tb", "ta"]); });
console.log(`${n} cases passed`);
```

- [ ] **Step 2: Run** `node tests/map.test.js` → fails with `Cannot find module '../static/map.js'`.
- [ ] **Step 3: Implement `static/map.js`** with the functions under Interfaces, and add `<script src="/static/map.js"></script>` to `static/index.html` between `people.js` and `app.js`.
- [ ] **Step 4: Run** `node tests/map.test.js` → `7 cases passed`; `node tests/people.test.js` and `node tests/sync.test.js` still pass.
- [ ] **Step 5: Commit** — `git add static/map.js static/index.html tests/map.test.js && git commit -m "Department map: what the map shows, as plain functions"`

---

### Task 2: What the map writes

**Files:**
- Modify: `static/map.js`, `tests/map.test.js`

**Interfaces:**
- Consumes: Task 1's card shape (`{kind: "class", li, cls}` and `{kind: "group", li}` are enough to address a card).
- Produces: `DeptMap.canTeach(teacher, subject, level, bandOf) -> boolean` — `teacher` is the row, `bandOf` the `spec.school.bands` map (level → band of levels): true when a `can_teach` entry has the subject and its `levels` is empty, `"All"`, `level` or `bandOf[level]`. (`app.js`'s `canTeach(name, subject, level)` becomes a call to this with the row and `bands()`.)
- Produces: `DeptMap.MAX = 3` (teachers on one card).
- Produces: `DeptMap.deploy(spec, card, idxs, opts) -> { placed: string[], already: string[], refused: { name, why }[], split: boolean }`, `opts = { addToBasket: boolean }` (default false). `card` is a card from `cards`, or at least `{ kind, li, cls, title }`; a missing `title` reads as `cls` for a class card and `"The group"` otherwise. In order:
  1. Teachers already on the card's row go to `already` and are not counted again.
  2. A teacher with no `can_teach` entry for the card's subject (any level) goes to `refused` with why `"<name> is not in the <subject> basket."` — unless `opts.addToBasket`, which first pushes `{ subject, levels: "All" }` onto their `can_teach`.
  3. If the row's teachers plus the ones left to place would exceed `MAX`, every one left is refused with why `"<title> would have N teachers; three is the most."` and nothing is written.
  4. For a class card whose row lists several classes: that class is taken out of the row's `classes`, and a new row is pushed onto `spec.lessons` — a copy of the row (every field but `_id`, which Sync gives it on save) with `classes: [cls]` — and the teachers are placed on the new row; `split` is true. Otherwise they are placed on the card's row.
  5. Placing = appending names to `row.teachers` (blanks removed first). `placed` lists them.
- Produces: `DeptMap.undeploy(spec, card, name) -> boolean` — takes the name off the card's row (a class card of a shared row splits first, as in `deploy`); false when the name was not on it.
- Produces: `DeptMap.addToBasket(spec, idxs, subject) -> number` — adds `{ subject, levels: "All" }` to each teacher who lacks the subject; returns how many were added.
- Produces: `DeptMap.removeFromBasket(spec, idx, subject) -> { lessons: number }` — removes every `can_teach` entry for the subject from that teacher; `lessons` = how many rows of that subject still name the teacher (they are left as they are: step 6's check flags them as "not set to teach this").
- Produces: `DeptMap.newTeacher(spec, fields, roles, provisional) -> { i: number } | { error: string }` — `fields = { name, short, dept, role, allowance }`. A blank name → `{ error: "Give the teacher a name." }`; a name already in the setup by `People.key` → `{ error: "<existing name> is already a teacher." }`. Otherwise pushes `{ name, short: short || first word of name, dept, role, allowance: Number(allowance) || the role's guide allowance from roles || null, provisional: provisional ? "Yes" : "No", can_teach: [] }` and returns its index.

- [ ] **Step 1: Add the failing cases to `tests/map.test.js`** (before the final `console.log`):

```js
t("canTeach honours All, a level and a band of levels", () => {
  const tc = fixture().teachers[2];
  assert.ok(DeptMap.canTeach(tc, "Mathematics", "Sec 1", {})); assert.ok(!DeptMap.canTeach(tc, "Mathematics", "Sec 2", {}));
  assert.ok(DeptMap.canTeach({ can_teach: [{ subject: "Mathematics", levels: "Lower Sec" }] }, "Mathematics", "Sec 2", { "Sec 2": "Lower Sec" }));
  assert.ok(!DeptMap.canTeach({ can_teach: [] }, "Mathematics", "Sec 1", {}));
});
t("deploying to one class of a shared whole-class row splits that class off", () => {
  const s = fixture(); const r = DeptMap.deploy(s, { kind: "class", li: 0, cls: "1B" }, [2], {});
  assert.deepStrictEqual(r, { placed: ["Wei Lin Tan"], already: [], refused: [], split: true });
  assert.deepStrictEqual(s.lessons[0].classes, ["1A"]); assert.deepStrictEqual(s.lessons[0].teachers, ["Arjun Nair"]);
  const nw = s.lessons[4]; assert.deepStrictEqual([nw.classes, nw.teachers, nw.subject, nw.level, nw.students], [["1B"], ["Arjun Nair", "Wei Lin Tan"], "Mathematics", "Sec 1", 30]);
  assert.ok(!("_id" in nw) || nw._id !== "l1");
});
t("deploying to a group adds, never replaces, and says who was already there", () => {
  const s = fixture(); const r = DeptMap.deploy(s, { kind: "group", li: 1 }, [0, 2], {});
  assert.deepStrictEqual(r, { placed: ["Wei Lin Tan"], already: ["Arjun Nair"], refused: [], split: false });
  assert.deepStrictEqual(s.lessons[1].teachers, ["Arjun Nair", "Wei Lin Tan"]);
});
t("a teacher not in the basket is refused, or added to it first when asked", () => {
  const s = fixture(); const r = DeptMap.deploy(s, { kind: "group", li: 1 }, [1], {});
  assert.deepStrictEqual(r.refused, [{ name: "Priya Menon", why: "Priya Menon is not in the Mathematics basket." }]);
  assert.deepStrictEqual(s.lessons[1].teachers, ["Arjun Nair"]);
  const r2 = DeptMap.deploy(s, { kind: "group", li: 1 }, [1], { addToBasket: true });
  assert.deepStrictEqual(r2.placed, ["Priya Menon"]); assert.deepStrictEqual(s.teachers[1].can_teach, [{ subject: "Mathematics", levels: "All" }]);
});
t("more than three on a card: none is placed and the card says so", () => {
  const s = fixture(); s.lessons[2].teachers = ["Arjun Nair", "Wei Lin Tan"]; s.teachers[1].can_teach = [{ subject: "Mathematics", levels: "All" }]; s.teachers[3].can_teach = [{ subject: "Mathematics", levels: "All" }];
  const r = DeptMap.deploy(s, { kind: "group", li: 2, title: "2MA2" }, [1, 3], {});
  assert.deepStrictEqual(r.placed, []); assert.strictEqual(r.refused.length, 2); assert.strictEqual(r.refused[0].why, "2MA2 would have 4 teachers; three is the most.");
  assert.deepStrictEqual(s.lessons[2].teachers, ["Arjun Nair", "Wei Lin Tan"]);
});
t("undeploy takes a teacher off a card, splitting a shared row first", () => {
  const s = fixture(); assert.strictEqual(DeptMap.undeploy(s, { kind: "class", li: 0, cls: "1A" }, "Arjun Nair"), true);
  assert.deepStrictEqual(s.lessons[0].classes, ["1B"]); assert.deepStrictEqual(s.lessons[0].teachers, ["Arjun Nair"]); assert.deepStrictEqual([s.lessons[4].classes, s.lessons[4].teachers], [["1A"], []]);
  assert.strictEqual(DeptMap.undeploy(s, { kind: "group", li: 1 }, "Nobody"), false);
});
t("baskets: adding and removing a subject", () => {
  const s = fixture(); assert.strictEqual(DeptMap.addToBasket(s, [0, 1, 3], "Mathematics"), 2);
  assert.deepStrictEqual(DeptMap.removeFromBasket(s, 0, "Mathematics"), { lessons: 3 });
  assert.deepStrictEqual(s.teachers[0].can_teach, []); assert.deepStrictEqual(s.lessons[0].teachers, ["Arjun Nair"]);
});
t("a new teacher: defaults, a head's is provisional, no second teacher with the same name", () => {
  const s = fixture(); const r = DeptMap.newTeacher(s, { name: "New Mathematics teacher 1", short: "", dept: "MA", role: "EO", allowance: "" }, s.roles, true);
  assert.deepStrictEqual(r, { i: 4 }); assert.deepStrictEqual(s.teachers[4], { name: "New Mathematics teacher 1", short: "New", dept: "MA", role: "EO", allowance: 20, provisional: "Yes", can_teach: [] });
  assert.deepStrictEqual(DeptMap.newTeacher(s, { name: "  priya   MENON", dept: "MA", role: "EO" }, s.roles, false), { error: "Priya Menon is already a teacher." });
  assert.deepStrictEqual(DeptMap.newTeacher(s, { name: " ", dept: "MA" }, s.roles, false), { error: "Give the teacher a name." });
  assert.strictEqual(s.teachers.length, 5);
});
```

- [ ] **Step 2: Run** `node tests/map.test.js` → fails at "canTeach honours…" with `DeptMap.canTeach is not a function`.
- [ ] **Step 3: Implement** the functions under Interfaces in `static/map.js`.
- [ ] **Step 4: Run** `node tests/map.test.js` → `15 cases passed`.
- [ ] **Step 5: Add one smoke test** to `tests/smoke.py`, after `test_a_head_can_add_and_fill_in_a_teacher_in_one_request`: `test_a_heads_map_batch_is_applied_whole` — as a head, one `/api/changes` request carrying what one map session sends: `["add", "teachers", {...}]` (a new teacher), `["merge", "teachers", <id>, "can_teach", [{"subject": ..., "levels": "All"}], []]`, `["add", "lessons", {...split row...}, <after id>]`, `["set", "lessons", <id>, "classes", [...]]`, `["set", "lessons", <id>, "teachers", [...]]`. Assert the reply has nothing refused and the setup read back has the new row, the trimmed classes and the new `can_teach` entry. Run `.venv/bin/python tests/smoke.py` → `30 checks passed` (and `SMOKE_NO_HEADS=1` → `21 checks passed`, the new test skipped like the other heads' tests).
- [ ] **Step 6: Commit** — `git add static/map.js tests/map.test.js tests/smoke.py && git commit -m "Department map: deploying, baskets and new teachers, with their rules"`

---

### Task 3: Step 5 opens on the map — the roster

**Files:**
- Modify: `static/app.js` (`STEPS`, `VIEWS.lessons`, new `VIEWS.map`, events), `static/style.css`

**Interfaces:**
- Consumes: Task 1's `DeptMap.roster`, `unplaced`, `search`, `loads`, `prune`; Task 2's `newTeacher`; `avatarOf(t, size)` and `People.avatar` from stage 3.
- Produces: module state `const M = { view: "map", dept: "", tab: "classes", level: "", ticked: new Set(), lastTick: null, extra: [], q: "", profile: null, adding: false }` — `ticked` and `extra` hold teacher `_id`s, `profile` an `_id` or null. `M.view` is kept in `localStorage` under `"ttsetup.mapview"` (`"map"` or `"table"`), read once at start.
- Produces: `data-` hooks later tasks and the events use: `data-mview="map|table"`, `#mDept` (select), `data-mtick="<id>"` (tick box; shift-click ticks the run from `M.lastTick` in roster order), `data-mall`, `data-mnone`, `data-munplaced`, `#mQ` (search box), `data-madd="<id>"` (put a found teacher on the roster), `data-mnew` (open the new-teacher form), `data-mnewgo`, `data-mnewcancel`, form fields `#mnName #mnShort #mnDept #mnRole #mnAllow`.
- Produces: `tickedIdx() -> number[]` — indexes of `M.ticked` teachers, in setup order, after `DeptMap.prune`.

- [ ] **Step 1: The step and the switch.** In `STEPS` relabel `lessons` to `"5 Department map"`. `VIEWS.lessons()` becomes: a header card `Step 5 · Department map` with a two-button switch (`data-mview`), then `VIEWS.map()` when `M.view === "map"`, else today's table content moved whole into `VIEWS.table()` (its heading becomes `h2` "Table view", wording otherwise unchanged). A head sees both views (heads edit this step today).
- [ ] **Step 2: The roster column.** `VIEWS.map()` returns `<div class="map"><section class="roster">…</section><section class="baskets"></section><section class="cards"></section></div>` (the two empty sections are filled in Task 4). The roster:
  - `#mDept` select over `sc().departments`; `M.dept` defaults to the first department. Changing it clears `M.extra` and `M.ticked`.
  - Buttons `Select all` (its label shows `Select all –` when some but not all roster teachers are ticked), `Deselect all`, `Not placed yet`.
  - `#mQ` search box, placeholder `Find, or add a teacher from another department`. Typing filters the roster by name/short (through `People.key`); under the roster, `DeptMap.search` results from other departments each with `+ Add to roster` (`data-madd`), tagged with their department.
  - One row per roster teacher: tick box (`data-mtick`), avatar button (`data-mprofile="<id>"`, drawn by `avatarOf(t, 32)`, `draggable="true"`, `data-mdrag="<id>"`), name, role, a visiting teacher's department in a small tag, and a load bar: `<div class="load"><i style="width:…%"></i></div> <span>24 / 20</span>` — width = total/allowance capped at 100%, class `over` (red) when `loads[name].over`, no bar when there is no allowance.
  - `+ New teacher` opens an inline form (`M.adding`): name, short (placeholder: the first word), department (default `M.dept`), role (from `roles()`, default `EO` when present), allowance (default the role's guide, updated when the role changes). `Add` calls `DeptMap.newTeacher(S.spec, fields, roles(), isHead() && !S.practice)`; an `error` is shown by `toast`; success → `save(); render(); toast("Added. The committee confirms new teachers on step 4.")` for a head, `toast("Added.")` for the committee; the new teacher is ticked.
  - The roster scrolls inside its column (`max-height: calc(100vh - 220px)`).
- [ ] **Step 3: Events.** In the document `click` handler, before `b.dataset.pop`: `data-mview`, `data-mtick` (handle on the `input`, like `data-pick`), `data-mall/mnone/munplaced`, `data-madd`, `data-mnew/mnewgo/mnewcancel`. In the `change` handler: `#mDept`, `#mnRole` (refills `#mnAllow` with the role's guide when the box is empty or still the old guide). In the `input` handler: `#mQ` sets `M.q` and re-renders the roster only (`$(".roster").outerHTML = …` is fine; a full `render()` would lose the caret).
- [ ] **Step 4: CSS** in `static/style.css`: `.map{display:grid;grid-template-columns:260px 1fr 320px;gap:12px;align-items:start}`, `@media (max-width:900px){.map{grid-template-columns:1fr 1fr}.map .cards{grid-column:1/-1}}`, `.roster .trow{display:flex;gap:8px;align-items:center;padding:4px 2px}`, `.load{flex:0 0 60px;height:6px;background:var(--chip);border-radius:3px;overflow:hidden}.load i{display:block;height:100%;background:var(--accent)}.load.over i{background:var(--warn)}`, `.tag{font-size:11px;background:var(--chip);border-radius:999px;padding:1px 6px}`, `.switch button.on{background:var(--accent);color:#fff;border-color:var(--accent)}`.
- [ ] **Step 5: Check in the browser preview** (committee, secondary sample as a practice copy, scratch `DATA_DIR`): step 5 opens on the map; `Table` shows the old table and the choice survives a reload; the MA roster lists 9 teachers with load bars; `Select all` ticks 9 and reads `Select all –` after one is unticked; `Not placed yet` ticks only teachers with no subject; typing `wei` lists an EL teacher with `+ Add to roster`, who then appears with an `EL` tag; `+ New teacher` with a blank name says `Give the teacher a name.`, with an existing name says who it is, and with `New Mathematics teacher 1` adds a provisional-No teacher (as the committee) who is ticked; one Undo removes them. Then as a head (role set from the console as in stages 2-3): the new teacher is provisional, and the step is not read-only.
- [ ] **Step 6: Run** `node --check static/app.js`, all five test commands → pass. **Commit** — `git add static/app.js static/style.css && git commit -m "Step 5 opens on the department map: the roster, ticks, search and new teachers"`

---

### Task 4: Baskets, staff room and cards

**Files:**
- Modify: `static/app.js`, `static/style.css`

**Interfaces:**
- Consumes: Task 1's `baskets`, `staffRoom`, `cards`; Task 2's `deploy`, `undeploy`, `addToBasket`, `removeFromBasket`; Task 3's `M`, `tickedIdx()`, `data-mdrag`.
- Produces: hooks `data-mbasket="<subject>"` (basket, click and drop target), `data-mstaff` (staff room, drop target), `data-mtab="classes|groups|bands"`, `#mLevel` (level filter select), `data-mcard="<li>|<cls>"` (class card: `cls`; group card: `li` only), `data-mx="<li>|<cls>|<name>"` (✕ on a card's avatar), `data-mbx="<id>|<subject>"` (✕ on a basket avatar, shown on hover).
- Produces: `placeTicked(card)` — runs `DeptMap.deploy` for `tickedIdx()`; with nothing ticked: `toast("Tick teachers first, then click a card.")`. Afterwards: refused for the basket → `confirm` "`<names>` are not in the `<subject>` basket. Add them to the basket and place them?" → deploy again with `addToBasket: true`; refused for the count → `toast(why)`; `placed.length` → `save(); render()`, and a `toast` such as `Placed Wei Lin Tan on 1B Mathematics.` (`already` named as `… was already on it.`).
- Produces: `dropIds(e) -> number[]` — the teacher indexes a drop carries: the `dataTransfer` text is a JSON array of `_id`s; `dragstart` on `data-mdrag` puts the ticked ids when the dragged teacher is ticked, else just that one.

- [ ] **Step 1: Baskets column.** `<section class="baskets">`: `h3` `Can teach`, one `.basket` per `DeptMap.baskets(S.spec, M.dept)` with the subject, the count, and the avatars (24 px, `data-mprofile`, `draggable`, `data-mdrag`; a `✕` `data-mbx` appears on hover). Below, the `.basket.staff` "Staff room — no subject yet" with `DeptMap.staffRoom` avatars. Clicking a basket calls `addToBasket` for `tickedIdx()` (`toast` "`N` added to `<subject>`"; nothing ticked → the same "Tick teachers first…" toast). `data-mbx` → `confirm` "Take `<subject>` off `<name>`?" plus, when `removeFromBasket` would report lessons, "They still teach it on `N` lesson rows, which Things to fix will flag." (ask first by calling it on a clone, or count the rows before). Dropping on the staff room removes the dragged teachers from every basket of this department's subjects (same question when any still teach them).
- [ ] **Step 2: Cards column.** `<section class="cards">`: tabs (`data-mtab`), `#mLevel` (`All levels` + `levels()`), then the cards of `DeptMap.cards(S.spec, lessonInfo(), M.dept, M.tab, M.level)`: title, subject, level, `periods` periods, the teachers' avatars (24 px) each with a `✕` (`data-mx`), and `+` when fewer than three. A band card is a lane: its title, `twice` as a red line "`<name>` is on two groups of this band: a band's groups meet at the same time", then its group cards inside. Clicking a class or group card (not an avatar or ✕) → `placeTicked`. Empty tab → "No `<tab>` for `<dept>` at this level yet. Add them in the table view."
- [ ] **Step 3: Drag and drop.** `dragstart` (document, on `[data-mdrag]`) sets `text/plain` and marks `.map` with class `dragging`; `dragover` on `[data-mbasket], [data-mstaff], [data-mcard]` calls `preventDefault()` and adds `.over`; `dragleave` removes it; `drop` reads `dropIds(e)` and runs the same code as a click with those indexes instead of `tickedIdx()`. `dragend` clears the marks.
- [ ] **Step 4: Events** for `data-mbasket`, `data-mstaff`, `data-mtab`, `#mLevel`, `data-mcard`, `data-mx`, `data-mbx`, and the drag events, in the existing document listeners.
- [ ] **Step 5: CSS**: `.basket{border:1px dashed #cdd5e1;border-radius:10px;padding:8px;margin-bottom:8px;min-height:44px}.basket.over,.gcard.over{border-color:var(--accent);background:#eef5ff}`, `.avs{display:flex;flex-wrap:wrap;gap:4px}`, `.gcard{border:1px solid var(--line);border-radius:10px;padding:8px 10px;margin-bottom:8px;cursor:pointer;background:var(--panel)}`, each avatar on a card or in a basket wrapped as `<span class="avx">…svg…<button class="x" …>✕</button></span>` with `.avx{position:relative;display:inline-block}.avx .x{position:absolute;top:-6px;right:-6px;font-size:10px;line-height:1;padding:0 3px;border-radius:999px;color:var(--warn)}`, `.lane{border-left:3px solid var(--navy);padding-left:8px}`, `.map.dragging .gcard,.map.dragging .basket{outline:1px dashed #cdd5e1}`.
- [ ] **Step 6: Check in the browser preview** (committee, sample, practice copy): tick two MA teachers and click the `Mathematics` basket → both avatars appear in it; tick a teacher with no subject and click a Sec 1 class card → the question offers to add them to the basket and place; accept → the card shows them and Things to fix has no new line; a class card whose row lists four classes → after placing, the table view shows that class on a row of its own and the other three unchanged, and Subjects' `Teaching groups` count is unchanged; tick three teachers and click a card with one → toast says four is too many and the card is unchanged; ✕ on a card avatar removes them; the `Bands` tab shows a band's groups in a lane and the red "twice" line after deploying one teacher to two of its groups; one Undo per action. Dragging an avatar onto a card deploys it (laptop). As a head: the same works; the toasts carry no "committee only".
- [ ] **Step 7: Run** `node --check static/app.js` and the five test commands → pass. **Commit** — `git add static/app.js static/style.css && git commit -m "Department map: baskets, the staff room and the class, group and band cards"`

---

### Task 5: The profile, and New look moves there

**Files:**
- Modify: `static/app.js`, `static/style.css`, `tests/people.test.js` (no change expected; run it)

**Interfaces:**
- Consumes: Task 1's `loads`, `prune`; Task 2's `removeFromBasket`, `undeploy`; `M.profile`; `data-mprofile`.
- Produces: `VIEWS.profile(t, i)` — drawn in place of the cards column while `M.profile` is set (a `✕ Close` returns to the cards): avatar at 64 px with a `New look` button under it (`data-avatar="<i>"`, the existing handler), name, short name, role, department, provisional mark when `Yes`, load line "`24` periods deployed + `4` other duties = `28` of `30`" (red when over), **Can teach**: one row per `can_teach` entry with the subject, a levels select (`scopes()`, path `spec.teachers.<i>.can_teach.<k>.levels`, saved by the existing `data-k` handler) and a ✕ (`data-mpx="<subject>"` → the same question as Task 4's basket ✕), **Teaches**: every card from `DeptMap.cards` over *all* departments (`tab` "classes" then "groups", `level` `""`, `dept` each of `sc().departments`) that names the teacher, as "1B · Mathematics · 6 periods" with a ✕ (`data-mx` as in Task 4), and a line "Details are changed on step 4." (for a head: "…by the committee; a provisional teacher's by you on step 4.").
- Produces: the step 4 table's avatar cell becomes a plain avatar (no button, no `New look`): `<td class="avcell">${avatarOf(t, 32)}</td>`; `data-avatar` stays the New look handler, now used by the profile only. The `button.avatar` CSS stays for the profile's button.

- [ ] **Step 1: The profile view** as under Interfaces; `data-mprofile` sets `M.profile` and renders; `data-mclose` clears it. On every `render()` of the map, `M.profile` is dropped when `DeptMap.prune([M.profile], S.spec)` is empty (the teacher was removed elsewhere), and `M.ticked` is pruned the same way.
- [ ] **Step 2: Step 4's avatar** becomes plain (Interfaces). Update the README sentence that puts New look on the teachers table (`README.md`, stage 3's Teachers section) to say it is on the teacher's profile on step 5.
- [ ] **Step 3: Check in the browser preview**: clicking any avatar (roster, basket, card) opens the profile in the right column; `New look` changes the avatar everywhere at once and one Undo brings it back; changing a Can teach level in the profile shows on step 4's table; ✕ on a Teaches line takes the teacher off that card and the card shows it; `✕ Close` returns to the cards with the same tab and level; step 4's avatar is no longer a button. In a second tab (committee), remove the teacher whose profile is open in the first → within a few seconds the first tab's profile closes and its tick is gone, with no error in the console.
- [ ] **Step 4: Run** `node --check static/app.js` and the five test commands → pass. **Commit** — `git add static/app.js static/style.css README.md && git commit -m "Department map: the teacher profile, with New look moved onto it"`

---

### Task 6: README and the heads' guide

**Files:**
- Modify: `README.md`, `docs/DEPLOY.md` (only if it describes step 5)

- [ ] **Step 1:** In `README.md`, replace the step 5 paragraph: what the map is (three columns), that ticking then clicking is the way (dragging also works), the basket-before-deployment rule and its question, add never replace and three at most, that a shared whole-class row splits when one class changes, the staff room, `+ New teacher` (heads' are provisional until step 4), the profile (New look lives here), and that the table view is still there for bulk edits and will gain groups and bands creation in the next stage. In the heads' section: heads can do everything on step 5 and add teachers; a head sees every department.
- [ ] **Step 2:** Read it back against the page once: every button name in the README exists on the page with that wording.
- [ ] **Step 3: Commit** — `git add README.md docs/DEPLOY.md && git commit -m "Docs: the department map"`

---

## Not in this plan (stage 5)

Creating teaching groups and bands on the map (the "Groups and bands" view, automatic codes and band names, the bands page with lanes and a pool), and reshaping the table view. Until then, groups and bands are made in the table view as today.

# Wizard stage 3: teachers — roles first, the teacher list upload, avatars — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** On step 4 the committee fills the roles table, uploads the school's teacher list in one go (new teachers added, existing ones updated, nobody removed without being asked), and every teacher gets a cartoon avatar that is the same on every screen.

**Architecture:** The logic that can be wrong in quiet ways (reading a pasted or uploaded list, matching it to the teachers already in the setup, choosing avatar parts from a name) goes in a new plain script, `static/people.js`, with no page access, so it runs under Node and is tested there. `static/app.js` gets the screens: Roles moved to the top of step 4, an "Upload the teacher list" card with a preview before anything changes, and avatars in the teachers table. Everything is saved through the existing `save()` (stage 2's sync), so an upload is one change and one Undo.

**Tech Stack:** vanilla JavaScript with no build step, Node for the tests, Flask (one small change to an existing route).

**Spec:** `docs/superpowers/specs/2026-11-09-setup-wizard-design.md`, section "Step 4: Teachers".

## Global Constraints

- No framework, no bundler, no new package. `static/people.js` is a third plain script (after `sync.js`), added on purpose so its logic is testable under Node. It defines one global, `People`, never touches `document`, `window`, `S` or `Math.random`, and ends with `if (typeof module !== "undefined") module.exports = People;`. `static/index.html` loads it before `app.js`.
- Every change to the setup goes through `save()`; nothing is written while drawing. An upload that is applied is one `save()`: one sync, one Undo entry.
- Teacher rows keep their `_id` and their `can_teach` when updated: update fields on the existing row object, never replace the row.
- Uploading the list, removing teachers and editing the roles table are committee-only (the server already refuses them for a head: `sync.head_may`). A head still sees step 4 as stage 2 left it: add a teacher, edit provisional teachers, change who can teach what.
- Teacher names, roles and departments in tests, samples and docs are made up. The repository is public: no real names, no codes; never commit `.claude/launch.json` or `data/`.
- `ttgen/` is not edited (so the workbook does not carry the avatar seed; a teacher's "new look" lives in the app's saved setup only). `ttgen/` and the skill's copy stay identical.
- Step numbers stay today's. Wording in the page: plain sentences, sentence case, no "please", no exclamation marks.
- Tests: `node tests/people.test.js`, `node tests/sync.test.js`, `.venv/bin/python tests/smoke.py`, `.venv/bin/python tests/test_sync.py` (plain asserts, no runner). Page checks in the browser preview against a scratch `DATA_DIR`, never the repository's `data/`.
- Commit on branch `wizard-stage-3` after each task. Do not push or open a pull request until the committee asks.

## Review Focus

1. The uploaded list names a teacher already in the setup with different capitals or spacing ("TAN  Wei Ming " for "Tan Wei Ming") → that teacher is updated, not added a second time. Pinned in Task 2.
2. The file is the setup workbook's own `4 Teachers` sheet, or a school export with title rows above the header and extra columns → the header row is found, extra columns are ignored, nothing is misread as a teacher. Pinned in Tasks 2 and 3.
3. The list has no Allowance or Role column → existing teachers keep their allowance and role; nothing is blanked. Pinned in Task 2.
4. The same name appears twice in the list → the second row is not applied and the preview says so. Pinned in Task 2.
5. The committee uploads one department's list by mistake and sees "42 teachers are not in this file" → nothing is removed unless they press the remove button, which names how many and that their lessons lose them; one Undo brings them all back, lessons included. Pinned in Task 3.

---

### Task 1: Avatars from a name

**Files:**
- Create: `static/people.js`, `tests/people.test.js`

**Interfaces:**
- Produces: `People.key(name: string) -> string` — the name lower-cased, trimmed, inner runs of spaces made one (the identity used everywhere in this stage).
- Produces: `People.hash(text: string) -> number` — 32-bit FNV-1a of the text, as an unsigned integer.
- Produces: `People.AVATAR` — the part lists: `bg` (at least 10 colours), `skin` (6), `hair` (at least 8 shapes, one of them none), `hairColor` (6), `glasses` (3: none, round, square), `mouth` (3), `top` (6 colours); and `People.AVATAR_COMBOS` — the product of their lengths, at least 100,000.
- Produces: `People.avatarParts(name: string, seed?: number) -> {bg, skin, hair, hairColor, glasses, mouth, top}` — indexes into those lists, taken from `People.hash(People.key(name) + "|" + (seed || 0))` and a second hash of the same text with `"#"` appended, so every part is decided by the name and the seed alone.
- Produces: `People.avatar(name: string, seed?: number, size?: number) -> string` — one inline `<svg>` (viewBox `0 0 36 36`, `width`/`height` = `size`, default 32, `aria-hidden="true"`), a round face on a coloured disc with hair, eyes, mouth, optional glasses and a coloured top. An empty or missing name gives a plain grey disc with no face.

- [ ] **Step 1: Write `tests/people.test.js`** (plain `assert`, prints `N cases passed`):

```js
const assert = require("assert");
const People = require("../static/people.js");
let n = 0; const t = (name, f) => { f(); n++; };
const NAMES = Array.from({ length: 200 }, (_, i) => `Teacher ${["Tan", "Lim", "Nair", "Osman", "Koh", "Menon", "Ong", "Lee"][i % 8]} ${i}`);
const sig = p => JSON.stringify(p);

t("the same name gives the same avatar, whatever its capitals or spacing", () => {
  assert.strictEqual(People.key("  TAN   Wei Ming "), "tan wei ming");
  assert.deepStrictEqual(People.avatarParts("TAN  Wei Ming "), People.avatarParts("Tan Wei Ming"));
  assert.strictEqual(People.avatar("Tan Wei Ming", 0, 32), People.avatar(" tan wei  ming", 0, 32));
});
t("hash is 32-bit FNV-1a", () => { assert.strictEqual(People.hash(""), 2166136261); assert.strictEqual(People.hash("a"), 3826002220); });
t("there are enough combinations to tell a staff room apart", () => {
  assert.ok(People.AVATAR_COMBOS >= 100000);
  assert.ok(new Set(NAMES.map(x => sig(People.avatarParts(x)))).size >= 195);
});
t("every part index is inside its list", () => {
  for (const x of NAMES) for (const [k, v] of Object.entries(People.avatarParts(x))) assert.ok(Number.isInteger(v) && v >= 0 && v < People.AVATAR[k].length, `${k} ${v}`);
});
t("a new look changes the avatar and is itself repeatable", () => {
  const changed = NAMES.filter(x => sig(People.avatarParts(x, 1)) !== sig(People.avatarParts(x, 0))).length;
  assert.ok(changed >= 195);
  assert.deepStrictEqual(People.avatarParts("Tan Wei Ming", 3), People.avatarParts("Tan Wei Ming", 3));
});
t("the drawing is one svg of the asked size, with no script and no outside link", () => {
  const s = People.avatar("Tan Wei Ming", 0, 48);
  assert.ok(s.startsWith("<svg") && s.endsWith("</svg>") && s.includes('width="48"') && s.includes('viewBox="0 0 36 36"') && s.includes('aria-hidden="true"'));
  assert.ok(!/script|href|http/i.test(s));
});
t("no name gives a plain disc, not a face", () => {
  for (const x of ["", "   ", null, undefined]) { const s = People.avatar(x); assert.ok(s.startsWith("<svg") && !s.includes("<path")); }
});
t("nothing random is used", () => { const r = Math.random; Math.random = () => { throw new Error("random"); }; try { People.avatar("Lim Hui Min", 2); } finally { Math.random = r; } });
console.log(`${n} cases passed`);
```

Run: `node tests/people.test.js` → fails with `Cannot find module '../static/people.js'`.

- [ ] **Step 2: Implement `static/people.js`** with the functions under Interfaces. The face must use at least one `<path>` (the "no name" test tells a face from the plain disc by it).
- [ ] **Step 3: Run** `node tests/people.test.js` → `8 cases passed`.
- [ ] **Step 4: Commit** — `git add static/people.js tests/people.test.js && git commit -m "Avatars drawn from a teacher's name"`

---

### Task 2: Reading a teacher list and matching it to the setup

**Files:**
- Modify: `static/people.js`, `tests/people.test.js`

**Interfaces:**
- Consumes: `People.key`.
- Produces: `People.FIELDS` = `["name", "short", "dept", "role", "allowance", "other_duties", "note"]` and the header words each answers to (compared lower-cased, with anything in brackets and punctuation removed): name ← name, teacher, teacher name, full name; short ← short, short name, initials, abbreviation; dept ← department, dept; role ← role, appointment; allowance ← allowance, allowance periods, periods; other_duties ← other duties, duties; note ← note, notes, remarks.
- Produces: `People.readTeachers(text: string) -> {teachers: object[], columns: string[], skipped: string[]} | {error: string}`
  - `text` is tab-separated or comma-separated rows (a row with a tab is tab-separated; quoted CSV cells with commas are honoured).
  - The header row is the first of the first 10 rows that has a cell answering to `name`; rows above it are ignored. With no such row the columns are taken in `People.FIELDS` order from the first row.
  - `columns` lists the fields the file has. Each teacher object has only those fields, minus the ones empty in its row; `allowance` and `other_duties` are numbers (a cell that is not a number is left out and noted in `skipped`).
  - A row with no name is ignored. A name already seen in the file (by `People.key`) is not added again; `skipped` gets `"<Name> is in the list twice: the second row was left out."`.
  - No teachers found → `{error: "No teachers found in that list. It needs a column of names."}`.
- Produces: `People.planTeachers(existing: object[], incoming: object[], roles: object[], departments: string[]) -> {add: object[], update: {i: number, changes: object}[], missing: number[], unknownRoles: string[], unknownDepts: string[]}`
  - Match by `People.key(name)` (first existing row with that key).
  - `add`: incoming teachers not in the setup, each with `can_teach: []`, `provisional: "No"`, `short` defaulting to the name's first word, and `allowance` defaulting to the guide allowance of its role in `roles` when the row has none.
  - `update`: for a match, `changes` holds only the fields the row has whose value differs from the existing row (so a file without an Allowance column changes no allowance); a row that changes nothing is not listed. The name itself is never changed by an update.
  - `missing`: indexes of existing teachers whose key is not in the file, in order.
  - `unknownRoles` / `unknownDepts`: distinct values in the file that are not in `roles[].role` / `departments`, in first-seen order.

- [ ] **Step 1: Add the failing cases to `tests/people.test.js`**

```js
const EX = [{ _id: "t1", name: "Tan Wei Ming", short: "Tan", dept: "MA", role: "EO", allowance: 104, can_teach: [{ subject: "Mathematics", levels: "All" }] },
            { _id: "t2", name: "Lim Hui Min", short: "Lim", dept: "MA", role: "HOD", allowance: 67, can_teach: [] }];
const ROLES = [{ role: "EO", allowance: 104 }, { role: "HOD", allowance: 67 }, { role: "ST", allowance: 86 }], DEPTS = ["MA", "SC"];

t("a list with a header, in any column order", () => {
  const r = People.readTeachers("Department\tTeacher Name\tRole\tAllowance (periods)\nSC\tArjun Nair\tST\t86\nMA\tPriya Menon\tEO\t\n");
  assert.deepStrictEqual(r.columns.sort(), ["allowance", "dept", "name", "role"]);
  assert.deepStrictEqual(r.teachers, [{ dept: "SC", name: "Arjun Nair", role: "ST", allowance: 86 }, { dept: "MA", name: "Priya Menon", role: "EO" }]);
});
t("title rows above the header and extra columns are ignored", () => {
  const r = People.readTeachers("Step 4 · Teachers\t\t\n\t\t\nTeacher\tShort\tGiven\tSpare\tDepartment\nArjun Nair\tArjun\t40\t46\tSC\n");
  assert.deepStrictEqual(r.teachers, [{ name: "Arjun Nair", short: "Arjun", dept: "SC" }]);
});
t("names only, one per line, with no header", () => {
  assert.deepStrictEqual(People.readTeachers("Arjun Nair\nPriya Menon\n").teachers, [{ name: "Arjun Nair" }, { name: "Priya Menon" }]);
});
t("comma-separated, with a quoted name that has a comma", () => {
  assert.deepStrictEqual(People.readTeachers('Name,Role\n"Nair, Arjun",ST\n').teachers, [{ name: "Nair, Arjun", role: "ST" }]);
});
t("a name twice in the list: the second row is left out and said", () => {
  const r = People.readTeachers("Name\tRole\nArjun Nair\tST\narjun  nair\tEO\n");
  assert.strictEqual(r.teachers.length, 1); assert.strictEqual(r.teachers[0].role, "ST");
  assert.deepStrictEqual(r.skipped, ["arjun  nair is in the list twice: the second row was left out."]);
});
t("an allowance that is not a number is left out and said", () => {
  const r = People.readTeachers("Name\tAllowance\nArjun Nair\tfull\n");
  assert.deepStrictEqual(r.teachers, [{ name: "Arjun Nair" }]); assert.strictEqual(r.skipped.length, 1);
});
t("nothing that looks like a teacher", () => { assert.ok(People.readTeachers("\n\n").error); });
t("an existing teacher is matched whatever the capitals and spacing, and only differences change", () => {
  const p = People.planTeachers(EX, [{ name: "TAN  Wei Ming ", role: "ST" }, { name: "Lim Hui Min", role: "HOD" }], ROLES, DEPTS);
  assert.deepStrictEqual(p.update, [{ i: 0, changes: { role: "ST" } }]);
  assert.deepStrictEqual(p.add, []); assert.deepStrictEqual(p.missing, []);
});
t("a list without allowance or role blanks nothing", () => {
  assert.deepStrictEqual(People.planTeachers(EX, [{ name: "Tan Wei Ming" }, { name: "Lim Hui Min" }], ROLES, DEPTS).update, []);
});
t("a new teacher takes the role's guide allowance, a short name, and is not provisional", () => {
  const p = People.planTeachers(EX, [{ name: "Arjun Nair", role: "ST", dept: "SC" }], ROLES, DEPTS);
  assert.deepStrictEqual(p.add, [{ name: "Arjun Nair", role: "ST", dept: "SC", short: "Arjun", allowance: 86, can_teach: [], provisional: "No" }]);
  assert.deepStrictEqual(p.missing, [0, 1]);
});
t("roles and departments the setup does not have are listed once each", () => {
  const p = People.planTeachers(EX, [{ name: "A B", role: "LT", dept: "HU" }, { name: "C D", role: "LT", dept: "MA" }], ROLES, DEPTS);
  assert.deepStrictEqual(p.unknownRoles, ["LT"]); assert.deepStrictEqual(p.unknownDepts, ["HU"]);
});
```

Run: `node tests/people.test.js` → fails at the first new case (`People.readTeachers is not a function`).

- [ ] **Step 2: Implement** `readTeachers` and `planTeachers` per Interfaces.
- [ ] **Step 3: Run** `node tests/people.test.js` → `19 cases passed`.
- [ ] **Step 4: Commit** — `git commit -m "Read a teacher list and match it to the teachers in the setup"`

---

### Task 3: Step 4 — roles first, and the upload with a preview

**Files:**
- Modify: `static/index.html` (load `/static/people.js` before `app.js`), `static/app.js` (`VIEWS.teachers` ~972-988, `VIEWS.roles`, the click and change handlers, `headLocks`), `static/style.css`, `app.py` (`read_table` ~204-219), `tests/smoke.py`

**Interfaces:**
- Consumes: `People.readTeachers`, `People.planTeachers`, `committee()`, `save()`, `S.pick`, `roles()`.
- Produces (server): `POST /api/read-table` takes an optional form field `sheet`. With `sheet=teachers` it reads the first sheet whose name contains "teacher" (any capitals), else the first sheet; without the field it behaves as today (the Students sheet, else the first). Still committee-only.
- Produces (page), step 4 in this order: the intro card; **Roles** (moved up from the bottom of the step, heading "1 · Roles", with one line: "Fill this first: the teacher list is checked against these roles."); **"2 · Upload the teacher list"**; then the existing "Add teachers" helper, filters, table and "+ Add teacher".
- Produces: the upload card, committee only (not rendered for a head; in a practice copy it works for anyone):
  - a paste box (`#tlPaste`), a file button (`#tlFile`, `.xlsx` or `.csv`; an `.xlsx` goes through `/api/read-table` with `sheet=teachers`, a `.csv` is read in the browser), and **Read the list**. One line of help: "Columns: Name, Short name, Department, Role, Allowance, Other duties, Note. Only Name is needed; a column you leave out is not changed."
  - **Read the list** changes nothing. It shows a preview from `planTeachers`: "N new · M to update · K unchanged", the lines from `skipped`, the unknown roles and departments each with a button (**Add these roles** appends them to the roles table with an empty guide allowance; **Add these departments** appends them to the school's departments), and **Apply** (disabled when there is nothing to add or update).
  - **Apply** makes the adds and the updates in one `save()` and says "Added N, updated M. Undo takes it back."
  - Below, when K′ teachers of the setup are not in the list: "K′ teachers are not in this list." with their names (the first 12, then "and N more") and **Remove these K′ teachers**. It asks first: "Remove K′ teachers who are not in this list? Their lessons on step 5 will have no teacher. Undo takes it back." It then removes the rows and takes their names out of every lesson's teachers, in one `save()`.
  - The preview is cleared whenever the paste box changes or the setup's teachers change by other means.
- The preview state lives in a module variable (not in `S.spec`); drawing writes nothing to the setup.

- [ ] **Step 1: Failing checks.** `tests/smoke.py`: build a two-sheet workbook in the test with openpyxl (sheet "Notes" with one row, sheet "4 Teachers" with a title row, a header `Teacher, Short, Department` and one made-up teacher); `POST /api/read-table` with `sheet=teachers` returns the teachers sheet's rows (the made-up name is in them); without `sheet` it returns the first sheet's rows; a head gets 401. Run → the `sheet=teachers` assertion fails. Browser (scratch data, sample school): step 4 today has Roles at the bottom and no upload card.
- [ ] **Step 2: Implement** the server change, then the page.
- [ ] **Step 3: Check in the browser** (committee, sample secondary school on scratch data):
  - Roles is the first card after the intro; the upload card follows.
  - Paste a list with one existing teacher's name in capitals with a new role, two new teachers (one with a role not in the table) and a duplicate line → the preview reads "2 new · 1 to update", lists the duplicate and the unknown role; nothing in the table has changed yet (`Sync.diff(SYNC.base, S.spec)` is `[]`).
  - **Add these roles** adds the role; **Apply** adds and updates; the existing teacher kept their Can teach and `_id`; one Undo takes the whole apply back.
  - With a list of only two teachers: "N teachers are not in this list" names them; cancelling the question removes nobody; confirming removes them and step 5's groups no longer name them; one Undo brings back the teachers and their groups. (Review Focus 5.)
  - Upload an `.xlsx` made by **Download workbook** on step 7: the teachers sheet is read, the title rows and computed columns are ignored, the preview says every teacher is unchanged. (Review Focus 2.)
  - With the role set to head from the console (as in stage 2's checks): no upload card; Roles is listed read-only; `Sync.diff(SYNC.base, S.spec)` stays `[]`.
- [ ] **Step 4: Run** `node --check static/app.js && node tests/people.test.js && node tests/sync.test.js && .venv/bin/python tests/smoke.py && SMOKE_NO_HEADS=1 .venv/bin/python tests/smoke.py`.
- [ ] **Step 5: Commit** — `git commit -m "Step 4: roles first, and uploading the teacher list with a preview"`

---

### Task 4: Avatars on the page

**Files:**
- Modify: `static/app.js` (`VIEWS.teachers` row, the click handler, `headLocks`), `static/style.css`

**Interfaces:**
- Consumes: `People.avatar(name, seed, size)`.
- Produces: `avatarOf(t, size)` in `app.js` → `People.avatar(t.name, t.avatar, size)`: the one place the page asks for a teacher's avatar (stage 4's map will use it).
- Produces: the teachers table has a first data column with each teacher's avatar (32 px) as a button, `title="New look"`, `aria-label="New look for <name>"`. Pressing it sets `t.avatar = (Number(t.avatar) || 0) + 1` and saves (so it syncs, and Undo takes it back). For a head it follows the row's rule from stage 2: enabled only for a provisional teacher.
- Produces: the ticked-teachers bar shows the avatars of the ticked teachers (24 px, the first 8, then "+N").

- [ ] **Step 1: Failing check, browser:** the teachers table has no avatars.
- [ ] **Step 2: Implement.**
- [ ] **Step 3: Check in the browser** (two tabs, scratch data): every row has an avatar; two different teachers look different; the same teacher looks the same in both tabs and after a reload; **New look** changes it in the pressed tab at once and in the other within 6 seconds; Undo puts the old look back; renaming a teacher changes their avatar (it is drawn from the name); a row with an empty name shows the plain disc. With the role set to head from the console: the avatar button of a confirmed teacher is disabled, of a provisional one enabled.
- [ ] **Step 4: Run** `node --check static/app.js && node tests/people.test.js && .venv/bin/python tests/smoke.py`.
- [ ] **Step 5: Commit** — `git commit -m "Every teacher has an avatar on step 4, with a new look on request"`

---

### Task 5: README

**Files:**
- Modify: `README.md`

- [ ] **Step 1:** Under the steps and "Deploying by hand" paragraphs, describe step 4 as it is now: roles first; uploading the teacher list (the columns, that only Name is needed, that a column left out is not changed, the preview, that nobody is removed without the question, that removing a teacher takes them off their lessons); avatars (drawn from the name, the same everywhere, "New look", not carried in the workbook). Add `static/people.js` and `tests/people.test.js` to "What's inside" and `node tests/people.test.js` to "Run locally".
- [ ] **Step 2: Check:** all four test commands pass; `for f in ttgen/*.py; do cmp -s "$f" "skill/school-timetable-generator/scripts/$f" || echo "differs: $f"; done` prints nothing.
- [ ] **Step 3: Commit** — `git commit -m "Docs: roles first, the teacher list upload and avatars"`

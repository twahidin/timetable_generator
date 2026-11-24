# Step 8: one page beside the board, collisions on a drop, teachers by department: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** On step 8, a click opens no pop-out and shows one page in the side panel; a drop on another lesson lists every collision in place of "Push out"; the two teacher questions suggest the department first and only what does not collide.

**Architecture:** The old Lesson tab folds into the Ask tab: `S.board.about` is the one state of the page and `S.board.lesson` goes. The server's `GET /api/draft/place` gains `clashes`, from a new all-reasons walk beside `Busy._why`; `Board.question` words the box from it. `ask.teachers` drops its busy tail and `ask.trades` and `Ask.verdict` change words only.

**Tech Stack:** Flask, vanilla JS (no build step), plain-assert tests (`.venv/bin/python tests/x.py`, `node tests/x.test.js`).

**Spec:** `docs/superpowers/specs/2026-11-24-step8-one-page-panel-design.md`. Read it first; this plan argues from it.

## Global Constraints

- Work only in the worktree (branch `step8-no-popout`). Use Python through the dev checkout's `.venv/bin/python` (the worktree has no `.venv` of its own).
- NEVER run `git stash`, `git stash pop`, `git checkout -- <file>`, `git reset --hard`, or switch branches. `git stash list` must stay at 2 entries. To see old code: `git show HEAD:path > /scratch/file`.
- Never use `pkill`/`killall` by name or pattern; stop only processes you started, by PID.
- Never print or edit `.claude/launch.json`. Never start a dev server from a builder task; browser checks are the controller's.
- The repo is public: made-up names only in code, tests and docs; the school is only ever "CTSS".
- No test may call a model API or the Telegram API.
- `static/app.js` has very long lines: search with `grep -nF` or Python and print lines cut to about 600 characters. After a block replace, list the `const`/`function` names the old block defined (`git diff`) and check each is still defined or no longer used.
- Everything from the server or the setup that reaches HTML goes through `esc()`.
- Commit after each task, on this branch only. Commit messages end with the line `Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>`. Never push.
- Words on the page are fixed by the spec; copy them exactly: "Lift out", "Delete this lesson", "Put it here anyway", "Nothing collides.", "Direct swap", "Direct swap, bends a rule", "Not a direct swap", "Lesson", "Empty period".
- After every task: `node --check static/app.js`, the suites the task names, and `git stash list | wc -l` equal to 2.

## Review Focus

1. A lesson deleted or lifted while its page is open: the page says "This lesson is no longer on the timetable." (deleted) or "Not placed" (lifted), nothing throws, no list is fetched for a lesson that is gone. Pinned in Task 1 (`Ask.parts(sub, null)`).
2. A slot from before this change, with no `clashes` key: the box still opens, with "another lesson is there." and the reason `beside.why` gives. Pinned in Task 3.
3. A band of many groups in the way: one Class line for the band, not one a class; more than 8 lines are cut with "and {n} more". Pinned in Tasks 2 and 3.
4. A subject whose card has no department: "No one who teaches {subject} is free to take …", never "No one in  is free". Pinned in Task 4.
5. "Delete this lesson" pressed on a lesson that is not selected (after Esc), so its delete judgement was never fetched: the question still comes, after one fetch. Checked by the controller in the browser (Task 5); the code path is named in Task 1.

---

### Task 1: The one page (part 1 of the spec)

**Files:**
- Modify: `static/ask.js`, `tests/ask.test.js`
- Modify: `static/app.js` (the board: `bdPopHTML`, `bdClick`, `bdCellClick`, `bdSideTab`, `bdSideHTML`, the `bdLesson…` functions, `bdTake`, `bdShowTray`, `bdShowWarning`, `bdShowTeacher`, `bdStep`, `bdLineHTML`, `bdHowHTML`, `bdBusy`, the Escape and `contextmenu` listeners, the `change` listener of the lists, `dragstart`; the Ask tab: `akOpen`, `akHTML`, `akEntryHTML`, `akShow`, `akClick`)
- Modify: `static/style.css`

**Interfaces:**
- Produces in `static/ask.js` (exported on `Ask`):
  - `tabLabel(sub) -> "Lesson" | "Empty period"` (`sub.kind === "place"` gives "Empty period").
  - `parts(sub, card) -> { lift: boolean, del: boolean, lists: boolean, group: string | null }`. A place, a missing card (`null`) or an entry of step 5's list (`card.entry`): all false, `group: null`. A lesson: `del: true`, `lists: true`, `lift` true only when it is on the timetable, `group` = `sub.group` when not null/undefined, else its first row's group, else null.
  - `where(card, day, time, was) -> string`: on the timetable `"{day} period {p}"` + `" ({time})"` when time + `" · {n} groups"` when the card is a band (`card.band` truthy; "1 group" singular); in the tray `"Not placed"` + `" (was)"` when `was` + the same groups tail.
- Produces in `static/app.js`: `S.board.about = { sub, card, pick, log, n, pre, back, les }` where `back` is the side tab open before the page was shown and `les = { id, group, got, all, n }` is the lists' state for the one chosen group (`got`: "loading", "fail" or `GET /api/draft/lesson`'s answer). `akOpen(sub, show = true)`.
- Consumes: nothing from other tasks.

- [ ] **Step 1: Write the failing tests** in `tests/ask.test.js`

```js
t("tabLabel: a lesson's page and an empty period's", () => {
  assert.strictEqual(Ask.tabLabel({ kind: "lesson", id: 3 }), "Lesson");
  assert.strictEqual(Ask.tabLabel({ kind: "place", by: "class", name: "1A", d: 0, p: 2 }), "Empty period");
});
t("parts: what the page holds", () => {
  const rows = [{ group: "G1", subject: "Science" }, { group: "G2", subject: "Science" }];
  const on = { id: 3, d: 0, p: 2, n: 1, rows }, tray = { id: 4, d: null, p: null, n: 1, rows };
  assert.deepStrictEqual(Ask.parts({ kind: "lesson", id: 3, group: null }, on), { lift: true, del: true, lists: true, group: "G1" });
  assert.deepStrictEqual(Ask.parts({ kind: "lesson", id: 3, group: "G2" }, on), { lift: true, del: true, lists: true, group: "G2" });
  assert.deepStrictEqual(Ask.parts({ kind: "lesson", id: 4, group: null }, tray), { lift: false, del: true, lists: true, group: "G1" });
  const none = { lift: false, del: false, lists: false, group: null };
  assert.deepStrictEqual(Ask.parts({ kind: "lesson", id: 9, group: null }, null), none);   // deleted meanwhile
  assert.deepStrictEqual(Ask.parts({ kind: "place", by: "class", name: "1A", d: 0, p: 2 }, null), none);
  assert.deepStrictEqual(Ask.parts({ kind: "lesson", id: "a:k" }, { id: "a:k", d: null, p: null, rows: [], entry: {} }), none);
});
t("where: the line under a lesson's name", () => {
  assert.strictEqual(Ask.where({ d: 0, p: 20, band: "" }, "Mon", "2.20", ""), "Mon period 20 (2.20)");
  assert.strictEqual(Ask.where({ d: 0, p: 20, band: "B", rows: [1, 2, 3, 4, 5] }, "Mon", "", ""), "Mon period 20 · 5 groups");
  assert.strictEqual(Ask.where({ d: 0, p: 3, band: "B", rows: [1] }, "Mon", "", ""), "Mon period 3 · 1 group");
  assert.strictEqual(Ask.where({ d: null, p: null, band: "" }, "", "", "was Tue period 4"), "Not placed (was Tue period 4)");
  assert.strictEqual(Ask.where({ d: null, p: null, band: "" }, "", "", ""), "Not placed");
});
```

- [ ] **Step 2: Run** `node tests/ask.test.js`. Expected: FAILED at "tabLabel".

- [ ] **Step 3: Implement** `tabLabel`, `parts`, `where` in `static/ask.js` (ES5 style, as the file is) and export them. Run `node tests/ask.test.js`: passes.

- [ ] **Step 4: Fold the Lesson tab into the page** in `static/app.js`

  The state:
  - Remove `b.lesson`, `bdLessonOn`, `bdLessonSync`, `bdLessonOpen`, `bdLessonHTML`, `bdLessonBlock` and the `data-bdlopen` click. Keep `bdLessonLists`, `bdLessonTeacher`, `bdLessonRoom`, `bdLessonPost`, `bdQuiet`; they read `S.board.about.les` in place of `b.lesson`.
  - `akOpen(sub, show = true)`: as today, and: when making the page shown (`show` and `b.side !== "ask"`), `A.back = b.side`; for a lesson, `A.les = { id, group: Ask.parts(sub, card).group, got: {}, all: {}, n: 0 }` and fetch that group's lists (`GET /api/draft/lesson?id=&group=`), dropping an answer of an older round or another lesson as `bdLessonFetch` does today; for a place `A.les = null`.
  - A group chip (`data-akgroup`): sets `A.sub.group`, `A.les.group`, fetches that group's lists.
  - `bdTake`: where it calls `bdLessonFetch()` today, fetch the page's lists again when the page is about a lesson that still exists.
  - `akBack(b)`: when `b.side === "ask"`, `b.side = b.about ? b.about.back || null : null`.

  What points the page (each replaces a `bdLessonOpen` call or adds an `akOpen`):
  - `bdClick`, the card branch: a click that selects calls `akOpen(Ask.ofCard(c, bd.from))`; a click that lets go calls `akBack(bd)`. An entry of step 5's list (`c.entry`) opens nothing and leaves `b.side` as it is.
  - `bdCellClick` with no lesson selected: marking an empty period calls `akOpen(Ask.ofPlace(at))`; the second click (unmark) calls `akBack(b)`.
  - `contextmenu` on a card: also selects it (`b.sel = id`, `b.from` its row, `b.place`, `b.ask`, `b.del`, `b.note`, `b.held` cleared as a selecting click does; never lets go), then `akOpen`, `bdDraw()`, `bdWant()`. On an empty period: with no lesson selected also `b.place = at` (and `bdPaint()`); with a lesson selected the selection stays and nothing is marked.
  - `bdStep`: `akOpen(Ask.ofCard(c, null))`. `bdShowWarning`: `akOpen(Ask.ofCard(c, null), !stay)`. `bdShowTeacher`: `akOpen(Ask.ofCard(c, b.from), !stay)`. `bdShowTray`: `akOpen(Ask.ofCard(c, null), false)`.
  - `akShow` ("Show on the board"): selects and shows the lesson as today and does not call `akOpen` (the page stays on what it is about).
  - Escape and `data-bdclose`: as today, plus `akBack(b)`.
  - `dragstart`: remove the line that redraws the panel for `b.lesson`.

  The tabs (`bdSideHTML`): Not placed, Warnings, Changes, and `["ask", Ask.tabLabel(b.about.sub), null]` while `b.about`. `bdSideTab` no longer calls `bdLessonSync`.

  The page (`akHTML`), top to bottom, per the spec's "The page, about a lesson":
  1. `<p class="aktitle"><b>{c.what}</b><br><span class="muted">{Ask.where(c, day, time, was)}</span></p>` for a lesson (`was` from `bdWas(d, c)` for a tray lesson); a place keeps `akTitle(b)` in bold; a gone lesson its sentence.
  2. `<div class="row akdo">`: `<button data-bdlift="1">Lift out</button>` when `parts.lift`, `<button data-bddel="1">Delete this lesson</button>` when `parts.del`, both `disabled` while `FX.busy`. When `b.del && b.del.id === A.card`: in their place `<div class="akdel">` with `Delete {c.what}?`, the reason exactly as `bdPopHTML` words it today (`"Step 5 asks for this lesson."` when `j.plan`, then `j.why`), `<button data-bddelgo="1">Delete</button>`, `<button data-bdcancel="1">Cancel</button>`.
  3. The warnings (`bdLineWarnings(c, Infinity)`), 4. the chips, 5. the starters: as today.
  6. When `parts.lists`: `bdLessonLists(A.les, row, got)` for the row of `A.les.group`, "Loading…" or `BDWHY.lessonFailed` as `bdLessonBlock` says them today. No group heading and no fold.
  7. The log and Clear, as today. In `akEntryHTML` the "· {e.title}" tail shows when `!akSame(e.sub, A.sub)` (not by comparing titles).

  The buttons act on the page's lesson, not on `b.sel`:
  - `data-bdlift`: `c = bdCard(A.card)`; `bdSend("/api/draft/fix", Board.liftFix(c), c, true)` when it is on the timetable.
  - `data-bddel`: `j = bdDelOf(c.id)`; with none, `bdSlotsP(c.id)` once and then take `bdDelOf(c.id)` (toast `BDWHY.delWait` only if it still is not there); `"na"` toasts its sentence; else `b.ask = null; b.del = { id, j }; bdSideDraw()`.
  - `data-bddelgo`: as today from `b.del`. `data-bdcancel`: as today, and `bdSideDraw()` when a delete question was open.
  - The lists' `change` listener: guards on "the page is about a lesson that exists and `A.les` holds this group's answer" in place of `bdLessonOn`.

  The pop-out (`bdPopHTML`): keep only the yes or no question and the drop question. Remove the delete question, the selected-lesson branch, the empty-period branch, and the `data-bdask` and `data-bdclose` buttons with their `bdClick` branches (keep the `data-bdclose` behaviour only if something still renders it; nothing should).

  The line under the green box (`bdLineHTML`): after `b.pt`, when the selected card is an entry: `"{name} · {n} period(s) · has {have} of {want}"`, then `" " + BDWHY.switch` off the Classes rows; else `b.note` as today.

  The green box (`bdHowHTML`): the Ask line becomes `<li><b>Ask:</b> click a lesson or an empty period; its questions are on the right.</li>`; in the Keys line "Esc closes the pop-out" becomes "Esc lets go of the lesson".

  `bdBusy`'s selector keeps `[data-bdlift], [data-bddel], [data-bddelgo]` (they are in the panel now) and the lists.

- [ ] **Step 5: CSS** in `static/style.css`: `.akdo{margin:0 0 6px;gap:6px}`, `.akdo [data-bddel],.akdel [data-bddelgo]{color:#b4233b;border-color:#f0c4cc}`, `.akdel` as a block with the `.bdwhy` look the pop-out gave the reason; the lists inside `.akabout` keep the `.bdles` rules (add `.akabout` beside `.bdles` in those selectors). Remove rules only the removed branches used.

- [ ] **Step 6: Verify**

Run: `node --check static/app.js && node tests/ask.test.js && node tests/board.test.js && node tests/draft.test.js`
Expected: no output from the check; each suite prints its passed count.
Run: a short Python script that reads `static/app.js` and asserts none of `bdLessonOpen(`, `bdLessonOn(`, `bdLessonSync(`, `b.lesson`, `data-bdlopen`, `data-bdask` remains, and that `bdLessonLists`, `bdLessonPost`, `bdQuiet`, `akBack` are each defined once.
Expected: no assertion fails.

- [ ] **Step 7: Commit** `feat(step 8): one page beside the board, no pop-out on a click`

---

### Task 2: Every collision at a place, from the server (part 2, server)

**Files:**
- Modify: `fixes.py` (`Busy`, `_placer`), `tests/test_fixes.py`, `tests/test_board.py`

**Interfaces:**
- Produces: `Busy.whys(self, rows, d, p, n, ignore=(), name=None) -> list[dict(kind, text)]`, `kind` in `("teacher", "class", "students", "room")`; `name(lesson_id) -> str` names a lesson in the way (default: `what()` of its first row).
- Produces: the slot `fixes.place` returns gains `clashes`: that list for the plain move or place with the other lessons left there (`ignore={lesson_id}`, `name` = `_placer`'s `name`) where `push` is not None, else `None`. `fixes.slots` with `extras=False` or `"who"` is unchanged (no `clashes` key).

- [ ] **Step 1: Write the failing tests** in `tests/test_fixes.py`, on that file's existing sample model and helpers (read its head for how it builds `m` and a `Busy`):

  - `test_whys_agree_with_the_first_reason`: for every lesson of the model and every `(d, p)` of the week, with `rows` = the lesson's rows and `ignore=(id,)`: `bool(b.whys(rows, d, p, n, ignore)) == bool(b.clash(rows, d, p, n, ignore))`, and when there is a clash, what `_why` names is in the first line: the teacher's name, the class, the group code or the room that starts `clash`'s sentence is in `whys(...)[0]["text"]`.
  - `test_whys_lists_every_kind_in_order`: a lesson dropped where its teacher teaches another class, its class has another lesson, and its room is in use: kinds are `["teacher", "class", "room"]`, texts `"{T} is teaching {what} then."`, `"{C} has {name} then."`, `"{R} is in use then."`.
  - `test_whys_names_a_band_once`: a whole-class lesson of two classes dropped on a band of those classes with three groups: exactly one `class` line, `"{C1} and {C2} have {the band's name} then."` (the name from `name=`), and no `students` line for that band.
  - `test_whys_one_line_a_teacher_and_lesson`: a two-period lesson over one two-period lesson of its teacher gives one teacher line, not two.
  - `test_whys_on_a_double_day`: on a day in `m["double"]` no teacher line (as `_why`).

  In `tests/test_board.py`, `test_place…` (the one asserting the key set at `/api/draft/place`): the key set gains `"clashes"`; `j["clashes"]` is a list of dicts with keys `{"kind", "text"}` where `j["push"]` is not None, and `None` on the free place.

- [ ] **Step 2: Run** `.venv/bin/python tests/test_fixes.py` (through the dev checkout's venv). Expected: FAIL, `AttributeError: 'Busy' object has no attribute 'whys'`.

- [ ] **Step 3: Implement `Busy.whys`** beside `_why`, walking the same indexes in the same order of kinds, collecting instead of returning:
  - teacher: one line for each (teacher, lesson id) pair found, `f"{t} is teaching {what(y)} then."`; skipped on a double day.
  - class: group what `_why`'s class walk finds by lesson id; one line a lesson, its classes in the order met: `"{A} has {name(id)} then."`, `"{A} and {B} have …"`, `"{A}, {B} and {C} have …"`.
  - students: `band_clash`'s sentence once when it hits a lesson not already named by a class line; then `_students(...)` once for each lesson id not already named by a class or students line.
  - room: one line a room (and a rain room), `f"{room} is in use then."`, by `_why`'s own test.
  `_why` and its sentences are not touched.

- [ ] **Step 4: Add `clashes`** in `_placer.at`: where `push` is set (`ids and extras is True`), `clashes = b.whys([dict(x) for x in rows], d, p, n, ignore={lesson_id}, name=name)`; include `clashes` in `more` (None where `push` is None). Update `place`'s and `slots`' docstrings.

- [ ] **Step 5: Run** `.venv/bin/python tests/test_fixes.py`, `tests/test_board.py`, `tests/test_ask.py`, `tests/test_helper.py`, `tests/test_typed.py`, `tests/smoke.py`. Expected: all pass.

- [ ] **Step 6: Commit** `feat(step 8): a place with another lesson lists every collision`

---

### Task 3: The drop box (part 2, page)

**Files:**
- Modify: `static/board.js`, `tests/board.test.js`, `static/app.js` (`bdPopHTML`'s drop branch, `bdJudge`, `bdAsks`, `bdClick`, `bdSend`, `bdTimeThen`, `bdBusy`, `bdWhyText`), `static/style.css`

**Interfaces:**
- Consumes: a slot's `clashes` (Task 2): `[{kind, text}]`, `null`, or missing (an older answer).
- Produces in `static/board.js`:
  - `CLASH = { teacher: "Teacher", class: "Class", students: "Students", room: "Room" }`.
  - `asks(s) -> null | { swap: boolean, beside: boolean, anyway: boolean }`: null without `s.push`; `swap` and `beside` as today; `anyway = !!s.beside && s.beside.state === "no"`.
  - `offers(card, s)`: the same three (a tray lesson never swaps).
  - `fix(card, s, how)`: `how` in `"move" | "swap" | "beside" | "anyway"`; `"anyway"` is the plain move or place with `force: true, why: s.beside.why`. `"push"` is gone, from `fix` and from `addFix`.
  - `question(card, s, board) -> { text, lines, more, why, also, swap, beside, anyway }`:
    - `lines`: the first 8 of `s.clashes || []` as `{ kind: CLASH[kind] || "", text }`; `more`: how many are left out (0 when none).
    - `text`: with lines `"{what} on {day} period {p} collides with:"`, else `"{what} on {day} period {p}: another lesson is there."`.
    - `why`: with no lines: `"Nothing collides."` when `beside` fits; else `s.beside.why` (a rule in the way, a place that is not lesson time, or an older answer's clash); `""` when there are lines.
    - `swap`: `"Swap with {what}"` / `"Swap"` as today, `also` = `s.also` then; `beside`: `"Put it beside {what}"` / `"Put it beside them"` as today; `anyway`: `"Put it here anyway"` when `asks(s).anyway`, else null.
  - `pushWords` and `tell`'s push sentence are removed (the page never reaches it: the board's slots carry no `push`); `tell` on a slot with `push` returns `"Another lesson is there. Drop or click to see what can be done."`.

- [ ] **Step 1: Write the failing tests** in `tests/board.test.js` (replace the tests that assert `push` in `question`, `tell` and `fix`):

```js
t("question: the collisions, cut at 8, and what can be done", () => {
  const c = card(9, 0, 1, 1, ["1A"], { what: "Science" }), b = board([c]);
  const out = [{ id: 5, what: "Maths", classes: ["1A"], groups: 1 }];
  const cl = [{ kind: "teacher", text: "Mr Tan is teaching 1B Art then." }, { kind: "class", text: "1A has Maths then." }];
  const s = { d: 1, p: 2, state: "na", why: "Another lesson is there.", swap: null, also: [], push: { state: "ok", why: "", out },
    beside: { state: "no", why: "Mr Tan is teaching 1B Art then." }, clashes: cl };
  assert.deepStrictEqual(Board.question(c, s, b), { text: "Science on Tue period 2 collides with:",
    lines: [{ kind: "Teacher", text: "Mr Tan is teaching 1B Art then." }, { kind: "Class", text: "1A has Maths then." }], more: 0, why: "",
    also: [], swap: null, beside: null, anyway: "Put it here anyway" });
  const many = Array.from({ length: 11 }, (_, i) => ({ kind: "room", text: "R" + i + " is in use then." }));
  const q = Board.question(c, Object.assign({}, s, { clashes: many }), b); assert.strictEqual(q.lines.length, 8); assert.strictEqual(q.more, 3);
});
t("question: nothing collides, a rule in the way, not lesson time, an older answer", () => {
  const c = card(9, 0, 1, 1, ["1A"], { what: "Science" }), b = board([c]), out = [{ id: 5, what: "Maths G1", classes: ["1A"], groups: 1 }];
  const base = { d: 1, p: 2, state: "na", why: "Another lesson is there.", swap: null, also: [], push: { state: "ok", why: "", out } };
  const free = Board.question(c, Object.assign({}, base, { beside: { state: "ok", why: "" }, clashes: [] }), b);
  assert.strictEqual(free.text, "Science on Tue period 2: another lesson is there."); assert.strictEqual(free.why, "Nothing collides.");
  assert.strictEqual(free.beside, "Put it beside Maths G1"); assert.strictEqual(free.anyway, null);
  const rule = Board.question(c, Object.assign({}, base, { beside: { state: "no", why: "Rule School: no Science after lunch." }, clashes: [] }), b);
  assert.strictEqual(rule.why, "Rule School: no Science after lunch."); assert.strictEqual(rule.anyway, "Put it here anyway"); assert.strictEqual(rule.beside, null);
  const na = Board.question(c, Object.assign({}, base, { beside: { state: "na", why: "That is not lesson time for 1A." }, clashes: [] }), b);
  assert.strictEqual(na.why, "That is not lesson time for 1A."); assert.strictEqual(na.anyway, null); assert.strictEqual(na.beside, null);
  const old = Board.question(c, Object.assign({}, base, { beside: { state: "no", why: "1A has Maths G1 then." } }), b);   // no clashes key
  assert.deepStrictEqual(old.lines, []); assert.strictEqual(old.why, "1A has Maths G1 then."); assert.strictEqual(old.anyway, "Put it here anyway");
});
t("fix: put it here anyway is the plain move forced with the reason shown; no push", () => {
  const c = card(9, 0, 1, 1, ["1A"]), s = { d: 1, p: 2, state: "na", swap: null, push: { state: "ok", why: "", out: [] }, beside: { state: "no", why: "1A has Maths then." } };
  assert.deepStrictEqual(Board.fix(c, s, "anyway"), { kind: "move", id: 9, d: 1, p: 2, force: true, why: "1A has Maths then." });
  assert.deepStrictEqual(Board.fix(card(9, null, null, 1, ["1A"]), s, "anyway"), { kind: "place", id: 9, d: 1, p: 2, force: true, why: "1A has Maths then." });
  assert.deepStrictEqual(Board.asks(s), { swap: false, beside: false, anyway: true });
  assert.strictEqual(Board.states(c, [s], 1, 6)[2], "ask");
  assert.strictEqual(Board.tell(s, ["Mon", "Tue"]), "Another lesson is there. Drop or click to see what can be done.");
});
```

- [ ] **Step 2: Run** `node tests/board.test.js`. Expected: FAILED at "question: the collisions".

- [ ] **Step 3: Implement** the `static/board.js` changes of the Interfaces block; delete the tests that pinned push. Run `node tests/board.test.js`: passes.

- [ ] **Step 4: The box** in `static/app.js`:
  - `bdPopHTML`, drop branch: `<span>{q.text}</span>`, then each line as `<span class="bdcl"><b>{kind}</b> {text}</span>`, `<span class="muted small">and {more} more</span>` when `more`, `<span class="bdwhy">{q.why}</span>` when `q.why`, `q.also` lines as today, then `data-bdswap`, `data-bdbeside`, `<button data-bdanyway="1">{q.anyway}</button>`, Cancel. No `data-bdpush`.
  - `bdJudge`: a slot with `push` judged always asks (`{ act: "ask" }`); the `"stuck"` refusal and its sentence in `bdWhyText` go. A step 5 entry is still refused by `bdTaken` first.
  - `bdClick`: the answer branch reads `data-bdswap`, `data-bdbeside`, `data-bdanyway` (`how` = `"swap" | "beside" | "anyway"`).
  - `bdSend`: drop the `body.push` test (a lift alone shows the tray). `bdTimeThen`: its "plain clean move" test drops `!fix.push`.
  - `bdBusy`'s selector: `[data-bdanyway]` in place of `[data-bdpush]`.
- [ ] **Step 5: CSS**: `.bdpop .bdcl{flex:1 0 100%;font-size:12.5px}` `.bdpop .bdcl b{display:inline-block;min-width:62px;color:#b4233b}`; `.bdpop [data-bdanyway]` keeps the plain button look (only Swap and Yes are filled).

- [ ] **Step 6: Verify** `node --check static/app.js && node tests/board.test.js && node tests/ask.test.js`; a Python script asserting `static/app.js` and `static/board.js` hold none of `data-bdpush`, `bdpush`, `pushWords`, `"Push out`, `how === "push"`.

- [ ] **Step 7: Commit** `feat(step 8): a drop on another lesson lists its collisions; no push out`

---

### Task 4: The teacher questions (part 3)

**Files:**
- Modify: `ask.py` (`teachers`, `trades`, the `BUSY` constant), `tests/test_ask.py`, `static/ask.js` (`verdict`), `tests/ask.test.js`

**Interfaces:**
- Produces: `Ask.verdict(option)`: for an option whose first fix is a trade (`option.fixes && option.fixes[0] && option.fixes[0].kind === "trade"`): `{ text: "Direct swap", cls: "ok" }`, `{ text: "Direct swap, bends a rule", cls: "prefer" }`, `{ text: "Not a direct swap", cls: "no" }`; every other option as today.
- `ask.teachers`' answer: `options` hold only free teachers (`who["free"]` is True for each); `ask.BUSY` is removed.

- [ ] **Step 1: Write the failing tests**

  `tests/ask.test.js`:
```js
t("verdict: a trade is a direct swap or not", () => {
  const tr = st => ({ state: st, fixes: [{ kind: "trade", a: "k1", b: "k2", x: "Mr Tan", y: "Ms Lee" }] });
  assert.deepStrictEqual(Ask.verdict(tr("ok")), { text: "Direct swap", cls: "ok" });
  assert.deepStrictEqual(Ask.verdict(tr("prefer")), { text: "Direct swap, bends a rule", cls: "prefer" });
  assert.deepStrictEqual(Ask.verdict(tr("no")), { text: "Not a direct swap", cls: "no" });
  assert.deepStrictEqual(Ask.verdict({ state: "ok", fixes: [{ kind: "teacher" }] }), { text: "Clean", cls: "ok" });
});
```
  `tests/test_ask.py`:
  - In `test_teachers_words`: replace the busy assertion with `assert all(o["who"]["free"] for o in a["options"])` and `assert not hasattr(ask, "BUSY")`.
  - `test_teachers_department_first_and_the_sentence`: on a setup where the lesson's subject has a department (read the file's `setup_bytes` and its trade tests for how departments are given): the options' `who["rank"]` values are non-decreasing; with every teacher of rank 0 to 2 made busy at the lesson's time (add a lesson for each in the workbook rows) and one outsider free: `a["text"] == f"No one in {DEPT} is free to take {what}. 1 teacher from another department is free."` and the one option is the outsider; with two outsiders `"… 2 teachers from other departments are free."`.
  - `test_teachers_sentence_without_a_department`: the subject's card has no department: `a["text"].startswith(f"No one who teaches {SUBJECT} is free to take ")`.
  - In `test_trades_found` / `test_trades_pretest…` / `test_trades_text_and_refusals`: the sentences become `"1 direct swap is possible for {X}."`, `"{n} direct swaps are possible for {X}."` (+ `" {k} more would land with a problem."` as today), and `"No direct swap is possible for {X}. {k} would land with a problem."`; `"No trade of this lesson can be made."` and the "Only the first …" tail stay.

- [ ] **Step 2: Run** both suites. Expected: FAIL on the new assertions.

- [ ] **Step 3: Implement**
  - `ask.teachers`: remove the busy tail and `BUSY`. `near = [t for t in free if t["rank"] <= 2]`. Text: no free teacher: as today; `free` and no `near`: `f"No one in {dept} is free to take {what}."` (with no department on the subject's card, `f"No one who teaches {subject} is free to take {what}."`; `dept` and `subject` as `fixes.choices` finds them: `fixes._on_card(spec, subject)[1]`, the step 5 row's subject else the row's), then `f" {_plural(len(free), 'teacher from another department is', 'teachers from other departments are')} free."`; else as today. Update the docstring.
  - `ask.trades`: the three sentences above. Update the docstring.
  - `Ask.verdict` in `static/ask.js`.

- [ ] **Step 4: Run** `node tests/ask.test.js`, `.venv/bin/python tests/test_ask.py`, `tests/test_board.py`, `tests/test_typed.py`, `tests/smoke.py`. Expected: all pass. `grep -rnF "ask.BUSY" . --include=*.py` finds nothing.

- [ ] **Step 5: Commit** `feat(step 8): teacher suggestions keep to who is free, department first; a trade reads as a direct swap`

---

### Task 5: README, notes, every suite

**Files:**
- Modify: `README.md` (the step 8 paragraphs: the pop-out, "Lift out", "Push out", the Lesson and Ask tabs, the trade and teacher answers)
- Create: `docs/superpowers/plans/2026-11-24-step8-one-page-panel-notes.md`

- [ ] **Step 1:** In `README.md`, find every sentence about step 8's pop-out, the Lesson tab, the Ask tab, "push", and the two teacher questions (`grep -n -i -e "pop-out" -e "push" -e "Lesson tab" -e "Ask tab" -e "trade" README.md`) and rewrite each to what the spec says. Plain words, short sentences, as the README is written.
- [ ] **Step 2:** Write the notes file: the rulings made while building, known limits (a red place still lands at once; `Board.tell`'s old push sentence gone; the server still accepts `push`), anything not tried in a browser.
- [ ] **Step 3: Every suite.** `node --check static/app.js`; `for f in tests/*.test.js; do node "$f" || echo "FAILED $f"; done`; `for f in tests/test_*.py tests/smoke.py; do "$PY" "$f" > "$LOGS/$(basename "$f").log" 2>&1 || echo "FAILED $f"; done`, with `PY` the dev checkout's `.venv/bin/python` and `LOGS` the scratch folder the controller names (never `/tmp`). Expected: no "FAILED" line. Then `--full` on `test_typed`, `test_helper`, `test_fixes` and `smoke` in the background.
- [ ] **Step 4: Commit** `docs: step 8's one page, the collisions box and the teacher answers`

The browser check (real pointer actions, scratch data folder, sample school) is the controller's, after Task 5: the list is in the spec's "Tests" section.

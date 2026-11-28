# The published timetable's new look, step 1 (the grid, who sees what, the printouts): Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every published timetable page and every PDF printout shows each lesson's own start and end time on a clock scale counted in hours, with striped breaks, and shows planning figures, period counts and "after school" to the committee only.

**Architecture:** Everything across a page is placed by clock minutes. On the web page the sums are small plain functions in the last script of `ttgen/timetable_page.html` (`spanOf`, `bandsOf`, `hourMarks`, `cellTime`), and `gridHTML` draws from them. In `ttgen/export.py` the same sums are `_span`, `_bands`, `_hours` and `_box_lines`, and `draw_page` draws from them. Who sees what is decided twice: the server leaves planning data out of a page that is not the committee's (`html_data`), and the page shows planning things only when `COMMITTEE` is true.

**Tech Stack:** Flask, one self-contained HTML page with plain JS (no build step), ReportLab, plain-assert tests (`$PY tests/x.py`, `node tests/x.test.js`).

**Spec:** `docs/superpowers/specs/2026-11-27-timetable-look-design.md`, sections 1 to 7 (section 8, the phone list, is step 2 and not in this plan). The mockup `2026-11-27-timetable-look-mockup.html` is beside it (made-up names; open with `?a`). Read the spec first; this plan argues from it.

## Global Constraints

- Work only in the worktree `~/Developer/tt-generator/tt-timetable-look` (branch `timetable-look`). Python is the dev checkout's: `PY=/Users/joetay/Developer/tt-generator/timetable_generator/.venv/bin/python` (the worktree has no `.venv`).
- NEVER run `git stash`, `git stash pop`, `git checkout -- <file>`, `git reset --hard`, or switch branches. `git stash list | wc -l` must stay at 2. To see old code: `git show HEAD:path > <scratch file>`.
- Never use `pkill`/`killall` by name or pattern; stop only processes you started, by PID.
- Never print or edit `.claude/launch.json`. Never start a dev server from a builder task: browser checks are the controller's (Task 8 lists them).
- The repo is public: made-up names only in code, tests and docs; the school is only ever "CTSS".
- No test may call a model API or the Telegram API.
- `ttgen/timetable_page.html` keeps many statements on one long line. Search it with `grep -nF` or Python and print lines cut to about 600 characters. Inside a line use `/* */`, never `//`. After every edit of it, cut the last script out and check it:
  `S=$(mktemp -d) && $PY -c "import sys;s=open('ttgen/timetable_page.html',encoding='utf-8').read();open(sys.argv[1],'w',encoding='utf-8').write(s.split('<script>')[-1].split('</script>')[0])" $S/page.js && node --check $S/page.js`
- After a block replace in that page, list the `const`/`function` names the old block defined (`git diff`) and check each is still defined or no longer used.
- Everything from the data that reaches HTML goes through `esc()`.
- `ttgen/` and `skill/school-timetable-generator/scripts/ttgen/` are the same package. After every task that changes `ttgen/`, copy each changed file across; `diff -rq -x __pycache__ ttgen skill/school-timetable-generator/scripts/ttgen` must print nothing. `SKILL.md` and its version number do not change (the skill reads and writes the same files as before).
- The Excel file must come out exactly as before: `write_excel` and what it reads (`v["subtitle"]`, `v["pdf_subtitle"]`, `v["stats"]`, each legend entry's `text`, each cell's `p`, `n`, `ext`) are not changed.
- Words are fixed; copy them exactly. Hour labels: the number alone ("9"), the first label of a row with "am" or "pm", twelve with "noon", one o'clock with "pm" ("8 am", "12 noon", "1 pm"). A time: "8.00–9.00" (12-hour, a full stop, an en dash, no am or pm). Week name at the left of an hour row: the week's word in capitals and " WEEK" ("ODD WEEK"). The note under a web grid: "Striped bands are breaks. Click a lesson for every group, teacher and room in it." The PDF's foot note: "Striped bands are breaks."
- A lesson shorter than 40 minutes shows its start time only on the web page ("12.20"). On the PDF the start and end are shown when they fit the box's width, else the start only.
- Commit after each task, on this branch only. Commit messages end with the line `Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>`. Never push.
- After every task: the `node --check` above (if the page changed), the suites the task names, and `git stash list | wc -l` equal to 2. Judge a suite by its exit status with `if out=$(cmd 2>&1); then …`, and read its last line.

## Review Focus

1. A period length that does not divide the hour (35 minutes from 07:30): hour lines and labels sit at the true hours, between period edges, and a lesson's time is right. Pinned in Task 2 (`hourMarks`, `cellTime`) and Task 5 (`_hours`).
2. A page with no lessons, a day with no lessons, and a teacher whose only lesson is before recess: no error, "No lessons." as today, no band on a row with no lesson after it. Pinned in Task 2 (`spanOf`, `bandsOf`) and Task 5 (`_span`, `_bands`).
3. Things outside the usual day: an exam that starts before the first period (07:35) or ends after the page's last lesson, and three lessons side by side in one row: the page stretches to hold the exam, the row grows by the number side by side, every box keeps its time. Pinned in Task 3.
4. Older data: a lesson row with no after-school element, a class row with four elements, a school with no `start_time` (the page's `PB` falls back to the written times, adding 12 hours when a time goes back), a published model with no `files_look`. Each still draws; the last counts as stale files. Pinned in Task 2 (the fallback school), Task 5 and Task 7.
5. A school with one week, and a page that starts after noon: one hour row with no week name; the first label reads "1 pm" and no label says "am". Pinned in Task 2 and Task 5.

---

### Task 1: The server leaves planning data out of a page that is not the committee's (spec section 5, "The data follows the rule")

**Files:**
- Modify: `ttgen/export.py` (`html_data`, near line 996), and its copy under `skill/`
- Create: `tests/test_look.py`

**Interfaces:**
- Produces: `html_data(m, view="full", student_id=None, app=None)` unchanged in signature. "The committee's page" is `app is None or app.get("mode") == "committee"`. For any other page: every teacher row's fourth element (allowance) is `""`, every class row's third element (size) is `""`, every lesson row's twelfth element (after school) is `0`, and `checks["after"]` and `checks["notes"]` are `[]`. `checks["ok"]` and `checks["problems"]` stay as each view has them today.
- Produces: `tests/test_look.py`, a plain-assert file in the house style (`t(f)` counter, the line `# tests are added above this line by each task`, a last line printing the count), with a helper `school()` that returns a made-up model: build it as `model_for` in `tests/test_combined.py` does (`export._model(spec, days, lessons)` on `ttgen.samples.secondary()` with hand-placed lessons). It needs: two weeks, at least one whole-class lesson with `ext=True`, one class with a size, one teacher with an allowance, a day whose last lesson is before lunch, and one-period, two-period and three-period lessons. Later tasks add to this file.

- [ ] **Step 1: Write the failing test** in `tests/test_look.py`: `a_page_that_is_not_the_committees_carries_no_planning_data`

```python
full = export.html_data(m); com = export.html_data(m, app=dict(mode="committee"))
assert full == dict(com, app=None)                      # a saved copy is the committee's
assert any(t[3] for t in com["teachers"]) and any(c[2] for c in com["classes"]) and any(x[11] for x in com["lessons"])
for view, mode in (("full", "teacher"), ("staff", "staff"), ("student", "student")):
    d = export.html_data(m, view, app=dict(mode=mode))
    assert all(t[3] == "" for t in d["teachers"]) and all(c[2] == "" for c in d["classes"]), mode
    assert all(x[11] == 0 for x in d["lessons"]) and d["checks"]["after"] == [] and d["checks"]["notes"] == [], mode
t_ = export.html_data(m, "full", app=dict(mode="teacher"))
assert t_["checks"]["problems"] == com["checks"]["problems"] and t_["checks"]["ok"] == com["checks"]["ok"]
sid = m["students"][0]["id"]; me = export.html_data(m, "personal", student_id=sid, app=dict(mode="personal"))
assert all(x[11] == 0 for x in me["lessons"]) and all(c[2] == "" for c in me["classes"])
```

- [ ] **Step 2: Run it and see it fail:** `$PY tests/test_look.py` fails on the teacher-mode line.
- [ ] **Step 3: Change `html_data`** as the Interfaces block says. Keep a lesson row's optional thirteenth element (the rain room) in its place.
- [ ] **Step 4: Run** `$PY tests/test_look.py`, `$PY tests/smoke.py`, `$PY tests/test_staff_passwords.py`, `$PY tests/test_routes.py`: all pass.
- [ ] **Step 5: Copy to the skill, check the diff is empty, commit** (`feat: a page that is not the committee's carries no planning data`).

### Task 2: The page's clock sums (spec sections 1, 2, 3)

**Files:**
- Modify: `ttgen/timetable_page.html` (the last script: beside `PB` near line 172, `cellOf` near 198, `dated` near 264, `lanes` near 290), and its copy under `skill/`
- Test: `tests/timetable_page.test.js`

**Interfaces:**
- Produces, in the page's last script:
  - `clk(mins) -> string`: minutes after midnight as the school writes a time: `clk(480) === "8.00"`, `clk(780) === "1.00"`, `clk(760) === "12.40"`.
  - Every cell (what `cellOf` returns, and each exam or event cell `dated` adds) has `a` and `b`: its start and end in minutes. A lesson: `PB[p][0]` and `PB[p + n - 1][1]`, with `p` held inside the day as `time()` holds it. An exam or event: `mins(it.start)` and `mins(it.end)`; when either is not a time, from its `p` and `n` as a lesson.
  - `cellTime(c) -> string`: `"8.00–9.00"`; when `c.b - c.a < 40`, the start alone (`"12.20"`).
  - `bandsOf(v, d) -> [{a, b, name}]`: the runs of `F`, `R`, `U` in `v.codes[d]`, in minutes, each kept only when a cell of `v.cells` on day `d` has `a >= ` the run's end. `[]` when `v.codes` is null.
  - `spanOf(v) -> [a0, b1] | null`: over all days, the earliest of every cell's `a` and every kept band's `a`, and the latest cell `b`. `null` when `v.cells` is empty.
  - `hourMarks(a0, b1) -> [{m, text, sub}]`: one for each whole hour with `a0 <= m <= b1`; `text` is the 12-hour number; `sub` is `"noon"` at 12:00, `"pm"` at 13:00, and for the first mark `"am"` before noon or `"pm"` after it, else `""`.
  - `lanes(cells)` judges overlap by `a` and `b` (today by `p` and `n`); its return shape does not change.
  - `dated(v)` sets `v.span`: `spanOf(v)` taken before it cuts the cells to the day, then widened to hold that day's exam and event cells (earlier `a`, later `b`).
- Consumes: `PB`, `mins`, `BREAK`, `NP`, `ND`, `D.times` as they are today.

- [ ] **Step 1: Write the failing tests** in `tests/timetable_page.test.js` (run the functions with `P.run`, in the file's own style). The made-up school there has 20-minute periods from 07:40, recess at period 4, lunch at periods 10 and 11.

```js
/* the clock */
assert.strictEqual(P.run('clk(480) + " " + clk(780) + " " + clk(760)'), "8.00 1.00 12.40");
/* 3A: English at p0 n2 on Odd Mon */
assert.strictEqual(P.run('JSON.stringify(classView("3A").cells.filter(c => c.d === 0).map(c => [c.a, c.b, cellTime(c)]))'),
  JSON.stringify([[460, 500, "7.40–8.20"], [580, 640, "9.40–10.40"]]));
assert.strictEqual(P.run('cellTime({ a: 740, b: 760 })'), "12.20");                       /* under 40 minutes: the start alone */
/* bands: recess (9.00–9.20) has the science band after it; lunch (11.00–11.40) has nothing after it */
assert.strictEqual(P.run('JSON.stringify(bandsOf(classView("3A"), 0))'), JSON.stringify([{ a: 540, b: 560, name: "Recess" }]));
assert.strictEqual(P.run('JSON.stringify(bandsOf(classView("3A"), 1))'), "[]");               /* a day with no lessons: no bands */
assert.strictEqual(P.run('JSON.stringify(spanOf(classView("3A")))'), "[460,640]");
assert.strictEqual(P.run('spanOf({ cells: [], codes: null })'), null);
assert.strictEqual(P.run('JSON.stringify(hourMarks(460, 800).map(h => h.text + (h.sub ? " " + h.sub : "")))'),
  JSON.stringify(["8 am", "9", "10", "11", "12 noon", "1 pm"]));
assert.strictEqual(P.run('JSON.stringify(hourMarks(790, 900).map(h => h.text + (h.sub ? " " + h.sub : "")))'), JSON.stringify(["2 pm", "3"]));
```

Add two more schools with `boot`'s `tweak`: (a) `period_minutes: 35`, `start_time: "07:30"`, times re-made to match: `hourMarks(450, 660)` gives marks at 480, 540, 600 and 660 whatever the period edges are (they are at 450, 485, 520 …), and a two-period lesson at `p = 1` reads `"8.05–9.15"`; (b) the same 20-minute school with `school.start_time` and `school.period_minutes` deleted: `classView("3A").cells[0].a === 460` (the fallback) and a lesson after noon has `a` above 720.

For the date view, with the file's `DAY` answer (an exam 07:50 to 08:50 for 3A, a duty 07:35 to 09:00 for the teacher): after `P.pick("2026-10-05")` on 3A, `S.current.span` is `[460, 640]`; on the teacher's page the span's start is `455`.

- [ ] **Step 2: Run** `node tests/timetable_page.test.js`: fails with "clk is not defined".
- [ ] **Step 3: Write the functions** and add `a`, `b`, `v.span` as the Interfaces block says. Nothing drawn changes in this task: `gridHTML` still places by `p` and `n`.
- [ ] **Step 4: Run** the `node --check` line, then `node tests/timetable_page.test.js`: passes.
- [ ] **Step 5: Copy to the skill, check the diff is empty, commit** (`feat: the published page's clock sums`).

### Task 3: The page draws the new grid (spec sections 1 to 4 and 7)

**Files:**
- Modify: `ttgen/timetable_page.html` (the styles near lines 50 to 66 and 117 to 121, `gridHTML` near 300, `dated` near 264, `viewHTML`'s note near 326, `drawLessonPage` near 472), and its copy under `skill/`
- Test: `tests/timetable_page.test.js`

**Interfaces:**
- Consumes: Task 2's `clk`, `cellTime`, `bandsOf`, `spanOf`, `hourMarks`, `lanes`, `v.span`. The grid's span is `v.span || spanOf(v)`; with no span (no cells) `viewHTML` shows "No lessons." as today and `gridHTML` is not called.
- Produces: `gridHTML(v)` with this HTML shape (the class names are what tests and step 2 of the work lean on):
  - `<div class="gridwrap"><div class="tt" style="--w:…px">`, where `--w` is the span in minutes times 2, and `.tt` has `min-width: calc(var(--w) + 74px)`.
  - An hour row before the first day of each week, and once at the top of a one-date view: `<div class="ruler"><div class="wk">ODD WEEK</div><div class="ax"><span class="hr" style="left:…%">8<small>am</small></span>…</div></div>`. With one week, or a one-date view, `.wk` is empty.
  - A day row: `<div class="row"><div class="dl">…</div><div class="track" style="height:…px">…</div></div>`. Inside the track, in this order: a faint `<i class="vl">` at each period edge inside the span and a strong `<i class="vl h">` at each whole hour; each band of `bandsOf(v, d)` as `<div class="bk"><span>Recess</span></div>`, with class `v` added (the name turned on its side, as today) when the band is under 40 minutes; then the cells.
  - A cell keeps its classes (`cell`, `dim`, `x`, `exam`), `data-id`, `tabindex`, `--t`/`--a` and its `title` text as today. Inside: `<span class="t">` with `cellTime(c)`, `<b>` with the title, and one `<span class="m">` holding `c.lines.join(" · ")` (left out when there are no lines).
  - Left and width come from `a` and `b` against the span. Track height: 62px for a row with nothing side by side, else 48px times the most lessons side by side in that row.
- Produces: no `.cell.ext` rule, no class `ext` on a cell, and the subject's colour for every lesson, in `gridHTML` and in `drawLessonPage`. `D.ext` is read nowhere.
- Produces: an exam or event cell's lines no longer hold its time (the first line shows it, as `cellTime` writes it).
- Produces: after-school slots (`A`) and no-school time (`.`) draw nothing.
- Produces: the note under the grid is the fixed sentence in Global Constraints.
- Produces: CSS variables for the stripes, the hour line and the hour label, each with a dark-theme value in both dark blocks the file already has (`@media (prefers-color-scheme:dark)` under `:root:not([data-theme="light"])`, and `:root[data-theme="dark"]`). Take the light values from the mockup's `.brk`, `.vl.h` and `.hr` rules. In `@media print` the stripes, the lines and `.tt{min-width:0}` hold, with `print-color-adjust:exact` on `.bk`.

- [ ] **Step 1: Write the failing tests** in `tests/timetable_page.test.js`:

```js
P.run('show("classes", "3A")'); let h = P.view();
assert(count(h, 'class="ruler"') === 2 && h.includes(">ODD WEEK<") && h.includes(">EVEN WEEK<"), "an hour row above each week");
assert(count(h, 'class="row') === 10, "ten day rows");
assert(h.includes('<span class="t">7.40–8.20</span><b>EL</b>'), "the time comes first in a lesson's box");
assert(count(h, ">Recess<") === 1 && !h.includes(">Lunch<"), "a band only where a lesson follows: " + count(h, ">Recess<"));
assert(h.includes("8<small>am</small>") && !h.includes(">noon<"), "3A's page ends at 10.40");
assert(!h.includes("after school") && !/class="cell[^"]* ext/.test(h), "no after-school mark");
assert(h.includes("Striped bands are breaks. Click a lesson for every group, teacher and room in it."));
assert(!h.includes("Times are period start times"));
```

and: a tweak that marks 3A's English as after school (`d.lessons[0][11] = 1`) with `app.mode = "committee"` draws the same cell HTML as without the mark, apart from nothing; a tweak that puts three lessons of 3A at the same time on one day gives that row `height:144px`; on the date view of 3A the exam cell holds `<span class="t">7.50–8.50</span>` and no `07:50`; on the teacher's date view the first hour label is still "8" with "am" and the duty cell starts left of it (`left:0%`). Update the file's older assertions that expect the exam's time as "07:50–08:50" inside a cell, saying in the commit why.

- [ ] **Step 2: Run** `node tests/timetable_page.test.js`: the new assertions fail.
- [ ] **Step 3: Rewrite `gridHTML`, the styles, the note, `dated`'s exam lines and `drawLessonPage`'s colour** to the Interfaces block. Take the look (sizes of type, radius, the stripe's angle) from the mockup's section A.
- [ ] **Step 4: Run** the `node --check` line, `node tests/timetable_page.test.js`, `$PY tests/smoke.py`, `$PY tests/test_routes.py`: all pass. Then the block-replace check from Global Constraints for `gridHTML` and the style block.
- [ ] **Step 5: Copy to the skill, check the diff is empty, commit** (`feat: the published page draws lessons on a clock scale, each with its time`).

### Task 4: Who sees what on the page (spec section 5)

**Files:**
- Modify: `ttgen/timetable_page.html` (`classView`, `teacherView`, `roomView`, `personalView` near 199 to 258, `viewHTML` near 318, `lessonMatches` near 415, the Lessons filters near 439, `drawLessonTable` near 488, `lessonDialog` near 622, `csvDownload` near 647, `route` near 701), and its copy under `skill/`
- Test: `tests/timetable_page.test.js`

**Interfaces:**
- Produces: `const COMMITTEE = !APP || APP.mode === "committee";`
- Produces: `classView(c).stats` is `[]` for everyone, and its `sub` is `"{level} · home room {home}"` followed by the form teachers as today (no "N students").
- Produces: `viewHTML` draws the `.stats` block only when `COMMITTEE` and the view has stats.
- Produces: every legend entry is `{color, label, text, count}`: `text` without the count of periods, `count` like `"6 periods"`. `viewHTML` writes `text` and, when `COMMITTEE`, `" · " + count`. A band's entry, which today begins with its count, ends with it like the others.
- Produces: `lessonDialog` never writes "after school", and writes `" · N periods"` only when `COMMITTEE`.
- Produces: only when `COMMITTEE`: the Lessons tab's "After school only" tick box; the small words "after school" in its Table; the "After school" column of `csvDownload` (the header and the value both left out otherwise); and the `ext` filter (`f.ext` from the tick box or from the link `#lessons?ext`) is ignored otherwise. The Table's swatch takes the subject's colour for everyone.

- [ ] **Step 1: Write the failing tests** in `tests/timetable_page.test.js`, one `boot` for each of `committee`, `teacher`, `staff` (with its `me`), `student` and `personal`, the last four with a `tweak` that cuts the data as Task 1 does:

```js
/* a class page: no figures for anyone, the committee too */
for (const X of [COM, TEA, STF, STU_]) { X.run('show("classes", "3A")'); const h = X.view();
  assert(!h.includes("periods a cycle") && !h.includes(" students") && !h.includes('class="stats"><div>'), "no figures on a class page");
  assert(h.includes("Sec 3 · home room 3-01")); }
/* a teacher page: figures and counts for the committee only */
COM.run('show("teachers", "Mr Ben Ong")'); assert(COM.view().includes("periods a cycle") && COM.view().includes("most in a day") && / · \d+ periods/.test(COM.view()));
for (const X of [TEA, STF]) { X.run('show("teachers", "Mr Ben Ong")'); const h = X.view();
  assert(!h.includes("periods a cycle") && !h.includes("allowance") && !h.includes("most in a day") && !/\d+ periods/.test(h), h); }
/* the lesson box that opens */
COM.run("lessonDialog(3)"); assert(/ · \d+ periods/.test(COM.el("dlgT").innerHTML) && !COM.el("dlgT").innerHTML.includes("after school"));
TEA.run("lessonDialog(3)"); assert(!TEA.el("dlgT").innerHTML.includes("periods"));
/* the Lessons tab */
COM.run('show("lessons", null)'); assert(COM.view().includes("After school only"));
TEA.run('show("lessons", null)'); assert(!TEA.view().includes("After school only") && !TEA.view().includes("after school"));
```

Also: with a committee boot whose first lesson is marked after school, the Lessons Table (`S.lview = "table"`) holds "after school" once and `csvDownload`'s header (catch it by replacing `Blob` in the boot's context) has "After school"; with a teacher boot the header has no "After school" and each row has one value fewer; a student's own page (`personal`) shows no `.stats` block and no "periods". Change the file's two older lines that expect "periods a cycle" on a staff page and "allowance" on a teacher-mode page.

- [ ] **Step 2: Run** `node tests/timetable_page.test.js`: the new assertions fail.
- [ ] **Step 3: Make the changes** in the Interfaces block.
- [ ] **Step 4: Run** the `node --check` line, `node tests/timetable_page.test.js`, `$PY tests/smoke.py`, `$PY tests/test_staff_passwords.py`: all pass.
- [ ] **Step 5: Copy to the skill, check the diff is empty, commit** (`feat: planning figures, period counts and after-school words show to the committee only`).

### Task 5: The printout's sums and words (spec sections 1, 2, 3, 5)

**Files:**
- Modify: `ttgen/export.py` (the four `*_view` functions near 456 to 572, `custom_view` near 1040, `_lanes` near 631, new helpers beside it), and its copy under `skill/`
- Test: `tests/test_look.py`

**Interfaces:**
- Produces, in `ttgen/export.py`:
  - `_mins(m, p) -> int`: minutes after midnight at the start of period `p` (`school["start_time"]` plus `p` times `school["period_minutes"]`); `_mins(m, NP)` is the end of the day.
  - `_clk(t) -> str`: `_clk(780) == "1.00"`.
  - Every cell of every view has `a` and `b` (minutes), set from `p` and `n`.
  - `_bands(m, v, d) -> [(a, b, name)]` and `_span(m, v) -> (a0, b1) | None`, by the same rules as the page's `bandsOf` and `spanOf` (Task 2).
  - `_hours(a0, b1) -> [(minute, label)]`: labels as one string: `"8 am"`, `"9"`, `"12 noon"`, `"1 pm"`.
  - `_lanes(cells)` judges overlap by `a` and `b`; its return shape does not change.
  - `_box_lines(cell, w, h) -> [(text, font, size, colour)]`: the lines a box of width `w` and height `h` (points) draws, top to bottom. Whole: the time, the title, the detail (`" · ".join(cell["lines"])`). The time is `"8.00–9.00"` when that fits `w - 5.5` at its size, else the start alone. Sizes are (6.2, 7.4, 6.3) for time, title, detail, all three made smaller together by a factor not under 0.9 until they fit `h - 3` at 1.16 line height. If they still do not fit: drop the detail; then put time and title on one line (`"8.00 EL"`) if that fits the width; else the title alone.
  - Each view has `print_subtitle`: a class `"{level} · home room {home}"`; a teacher its department and short name as today without the after-school count, or `"Teacher"`; a room and a student what `pdf_subtitle` holds today. `custom_view` removes it as it removes `pdf_subtitle`.
  - Each legend entry has `plain`: its `text` without the count of periods.
- `subtitle`, `pdf_subtitle`, `stats`, each legend `text`, and each cell's `p`, `n`, `ext` are not changed (the Excel file reads them).

- [ ] **Step 1: Write the failing tests** in `tests/test_look.py` on `school()`: `_clk`; a three-period lesson at period 1 has `(a, b)` 20 and 80 minutes after the day's start; `_bands` leaves out lunch on the day that ends before lunch and gives `[]` on a day with no lessons; `_span` of a class is (earliest band or lesson, end of its last lesson) and `None` for a view with no cells; `_hours(460, 800)` is `[(480, "8 am"), (540, "9"), (600, "10"), (660, "11"), (720, "12 noon"), (780, "1 pm")]` and `_hours(790, 900)` is `[(840, "2 pm"), (900, "3")]`; with `period_minutes` 35 and `start_time` "07:30" in a copy of the model, `_hours` of its span starts `(480, "8 am")`; `_box_lines` on a box 84 by 38 gives three lines whose first is `"8.00–9.00"`-shaped and whose third holds `" · "`; on 20 by 38 its first line is the start alone; on 84 by 25 it still gives three lines (the smallest PDF row); on 84 by 12 it gives one line; `class_view(m, c)["print_subtitle"]` has no "students" while `["pdf_subtitle"]` has it; a teacher with an after-school lesson has "after-school" in `pdf_subtitle` and not in `print_subtitle`; every legend entry's `plain` has no "periods" and its `text` has.
- [ ] **Step 2: Run** `$PY tests/test_look.py`: fails with "no attribute '_clk'".
- [ ] **Step 3: Write the helpers and the view keys.** `draw_page` is not changed in this task.
- [ ] **Step 4: Run** `$PY tests/test_look.py`, `$PY tests/smoke.py`, `$PY tests/test_combined.py`: all pass (the Excel checks in `smoke.py` prove the Excel lines did not move).
- [ ] **Step 5: Copy to the skill, check the diff is empty, commit** (`feat: the printout's clock sums and its own words`).

### Task 6: The printout draws the new look (spec section 6)

**Files:**
- Modify: `ttgen/export.py` (`draw_page` near 683, `_legend_layout` near 650), and its copy under `skill/`
- Test: `tests/test_look.py`

**Interfaces:**
- Consumes: Task 5's `_span`, `_bands`, `_hours`, `_lanes`, `_box_lines`, `print_subtitle`, legend `plain`.
- Produces: `draw_page(c, m, v, page=None)`, same signature, drawing: the heading with `v.get("print_subtitle", v.get("pdf_subtitle", v["subtitle"]))` and no figures at the top right; an hour row (14 points high) above each week, its labels from `_hours`, the week's name upright at its left edge as today's rotated label has it; a strong line down the grid at each hour and a faint one at each period edge; each band of `_bands` as a striped rectangle with its name (turned on its side when narrower than its name); each lesson by `a` and `b` in its subject's colour with a solid edge, its lines from `_box_lines`; the legend from each entry's `plain`; the foot note "Striped bands are breaks." (only when the view has codes, as today). No dashed edge, no "after school", no pale yellow or grey columns, no period numbers.
- `_legend_layout` measures `plain`. Row heights are worked out as today, with the hour rows' height taken from the grid in place of today's 21-point header.

- [ ] **Step 1: Write the failing tests** in `tests/test_look.py` with a recording canvas (a class whose `__getattr__` returns a function that appends `(name, args)` to a list; `stringWidth` comes from ReportLab, not the canvas, so `draw_page` runs on it):

```python
def drawn(v): c = Rec(); export.draw_page(c, m, v); return c.calls
def words(calls): return [str(a[-1]) for n_, a in calls if n_ in ("drawString", "drawCentredString", "drawRightString")]
for v in [export.class_view(m, CLASS), export.teacher_view(m, TEACHER), export.room_view(m, ROOM), export.student_view(m, m["students"][0])]:
    w = words(drawn(v)); text = "\n".join(w)
    assert "after school" not in text and "periods" not in text and "students" not in text and "allowance" not in text, v["title"]
    assert not any(n_ == "setDash" and a and a[0] for n_, a in drawn(v)), "no dashed edge"
    assert "8 am" in w and "Striped bands are breaks." in w
w = words(drawn(export.class_view(m, CLASS)))
assert w.count("8 am") == 2 and "ODD WEEK" in w and "EVEN WEEK" in w            # an hour row above each week
assert sum(x == "Lunch" for x in w) == LUNCH_DAYS                                # only on days with a lesson after lunch
assert any(re.fullmatch(r"\d{1,2}\.\d\d–\d{1,2}\.\d\d", x) for x in w)          # a lesson's time
```

(`CLASS`, `TEACHER`, `ROOM` and `LUNCH_DAYS` come from `school()`.) Add a check that no period number is drawn above the grid: the words drawn hold no run "0", "1", "2", "3" as today's header row has. Also: `export.pdf_bytes` gives `b"%PDF"` for every view of `school()`, for the 35-minute copy, for a one-week copy (one hour row, no week name) and for a view with no cells.

- [ ] **Step 2: Run** `$PY tests/test_look.py`: fails ("after school" is drawn, "8 am" is not).
- [ ] **Step 3: Rewrite `draw_page`** to the Interfaces block. Stripes: thin diagonal lines clipped to the band's rectangle over the band's pale fill.
- [ ] **Step 4: Run** `$PY tests/test_look.py`, `$PY tests/smoke.py`, `$PY tests/test_combined.py`, `$PY tests/test_venues.py`: all pass. If a `smoke.py` check compares two PDFs byte for byte, it still compares two new ones and passes; change no assertion there without saying why in the commit.
- [ ] **Step 5: Make pictures for the controller:** write a class, a teacher and a room page of `school()` to a scratch folder with `pdf_bytes`, turn each into a PNG (`sips -s format png x.pdf --out x.png`), and name the files in the task report. Do not commit them.
- [ ] **Step 6: Copy to the skill, check the diff is empty, commit** (`feat: the printouts draw lessons on a clock scale, each with its time`).

### Task 7: Stored printout files are made again after the deploy (spec, "What the builder must check or decide")

**Files:**
- Modify: `ttgen/export.py` (one constant), `store.py` (`publish` near 309, `remake_files` near 374, a new `files_stale`), `students.py` (`_files_run` near 119, `resume_files` near 151), and the skill's copy of `export.py`
- Test: `tests/test_students.py`

**Interfaces:**
- Produces: `ttgen.export.LOOK = 2`, with a comment: the number of the printouts' look; raise it when `draw_page` changes what a stored book shows.
- Produces: `store.publish` and `store.remake_files` write `files_look=LOOK` into the published `meta.json`.
- Produces: `store.files_stale(meta) -> bool`: true when `meta.get("files_behind")` is true or `meta.get("files_look") != LOOK`.
- Produces: `students._files_run` and `students.resume_files` ask `store.files_stale(pub["meta"])` where they read `files_behind` today. Nothing else reads the new key. (The app runs one worker, so one start makes the files once.)

- [ ] **Step 1: Write the failing test** in `tests/test_students.py`, in the style of its `files_now` test near line 317: after a publish `meta["files_look"] == export.LOOK` and `store.files_stale(meta) is False`; write the meta back without `files_look` (an older publish) and `store.files_stale` is true; `students.files_now()` is true and afterwards the meta has `files_look == export.LOOK`, `files_behind` false, the same `published_at`, and the class book file exists.
- [ ] **Step 2: Run** `$PY tests/test_students.py`: fails on `files_look`.
- [ ] **Step 3: Make the changes** in the Interfaces block.
- [ ] **Step 4: Run** `$PY tests/test_students.py`, `$PY tests/smoke.py`, `$PY tests/test_versions.py`, `$PY tests/test_putback.py`: all pass.
- [ ] **Step 5: Copy to the skill, check the diff is empty, commit** (`feat: stored printout files are made again when the printouts' look has changed`).

### Task 8: The whole of it, checked (the controller's task)

**Files:**
- Create: `docs/superpowers/plans/2026-11-27-timetable-look-step-1-notes.md`
- Modify: `README.md` only where a sentence about the published page or the PDFs is no longer true (search it for "after school", "period start", "pale yellow")

- [ ] **Step 1: Every suite, on the final code.** Quick: each `tests/test_*.py` and `tests/smoke.py` with `$PY`, each `tests/*.test.js` with `node`, `node --check static/app.js`, the page's `node --check` line. Then the slow ones alone, nothing else running: `--full` on `test_typed`, `test_helper`, `test_fixes` and `smoke`. A failure of `test_helper --full` or `test_typed --full` is compared with the same suite on main in a detached scratch worktree before it is called this branch's.
- [ ] **Step 2: The skill's copy:** `diff -rq -x __pycache__ ttgen skill/school-timetable-generator/scripts/ttgen` prints nothing.
- [ ] **Step 3: The browser, with made-up data only**, on a scratch data folder and its own host name (`http://look.localhost:<port>`), real pointer clicks. In light and in dark: a class, a teacher, a room and a student page as the committee; the same class and teacher page signed in as a teacher and as a student; a student's own page; a date with an exam on a class and on a teacher; the Lessons tab's three views with and without "After school only"; a lesson's box opened by a click; the search; Download PDF, Download CSV and Copy link; the browser's print preview of a class page; "Preview as it will be published" from step 8. On each, try the old controls as well as look at the new grid. A picture of a class page and of a printed page goes to the lead.
- [ ] **Step 4: Counts on the school's real timetable** (the controller only; a scratch copy, counts only, the copy deleted after): of all lesson boxes on all class, teacher and room pages, how many show the start alone on the web page; how many PDF boxes lose their detail line, and how many their time; how many day rows have lessons side by side, and the most in one row. If more than a few boxes lose anything, stop and go back to the lead before the pull request.
- [ ] **Step 5: The notes file:** the calls made while building; the counts of step 4; what was not tried in a browser (a real phone, a real printer); that a single PDF has the new look at once and the stored books follow about a minute after the app starts (Task 7), with what the lead must do if they do not; that the Excel file is unchanged; what step 2 (the phone list) will build on (`gridHTML`'s shape, `cellTime`, `bandsOf`).
- [ ] **Step 6: Commit** the notes and any README line (`docs: notes for the published timetable's new look`). No push, no pull request and no merge without the lead's own words.

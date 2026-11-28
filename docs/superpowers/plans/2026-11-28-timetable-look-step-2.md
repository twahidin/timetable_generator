# The published timetable's new look, step 2 (the phone day list): Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** On a phone, a class, teacher, room or student timetable shows one day at a time as a list that opens on today, with each lesson's time beside it. Also, by the lead's word of 2026-11-28 ("keep it consistent"): the exam parts of the published page write a time the way the grid does ("1.00", not "13:00").

**Architecture:** The page always draws both the day list and the grid; CSS shows the list on a screen 700 px wide or less, the grid on a wider one, and always the grid in print. The list is drawn from the same cells and the same break rule as the grid (step 1's `bandsOf`, `cellTime`). One small new answer from the app, `GET /api/today`, gives the name of today's school day and nothing else, so the list can open on today for a student's own page too.

**Tech Stack:** Flask, one self-contained HTML page with plain JS (no build step), plain-assert tests (`$PY tests/x.py`, `node tests/x.test.js`).

**Spec:** `docs/superpowers/specs/2026-11-27-timetable-look-design.md`, section 8, and section 9 for Task 4. The mockup `2026-11-27-timetable-look-mockup.html` beside it (open with `?p`) and the picture `2026-11-27-timetable-look-mockup-phone.png` show the look, with made-up names. Step 1's notes are `docs/superpowers/plans/2026-11-27-timetable-look-step-1-notes.md`. Read the spec's section 8 first; this plan argues from it.

## Global Constraints

- Work only in the worktree `~/Developer/tt-generator/tt-timetable-phone` (branch `timetable-look-phone`, from main 7a996ba). Python is the dev checkout's: `PY=/Users/joetay/Developer/tt-generator/timetable_generator/.venv/bin/python` (the worktree has no `.venv`).
- NEVER run `git stash`, `git stash pop`, `git checkout -- <file>`, `git reset --hard`, or switch branches. `git stash list | wc -l` must stay at 2. To see old code: `git show HEAD:path > <scratch file>`.
- Never use `pkill`/`killall` by name or pattern; stop only processes you started, by PID.
- Never print or edit `.claude/launch.json`. Never start a dev server or open a browser from a builder task: browser checks are the controller's (Task 5).
- The repo is public: made-up names only in code, tests and docs; the school is only ever "CTSS". No test may call a model API or the Telegram API.
- `ttgen/timetable_page.html` keeps many statements on one long line. Search it with `grep -nF` or Python and print lines cut to about 600 characters. Inside a line use `/* */`, never `//`. After every edit of it, cut the last script out and check it:
  `S=$(mktemp -d) && $PY -c "import sys;s=open('ttgen/timetable_page.html',encoding='utf-8').read();open(sys.argv[1],'w',encoding='utf-8').write(s.split('<script>')[-1].split('</script>')[0])" $S/page.js && node --check $S/page.js`
- After a block replace in that page, list the `const`/`function` names the old block defined (`git diff`) and check each is still defined or no longer used.
- Everything from the data that reaches HTML goes through `esc()`.
- `ttgen/` and `skill/school-timetable-generator/scripts/ttgen/` are the same package. After every task that changes `ttgen/`, copy each changed file across; `diff -rq -x __pycache__ ttgen skill/school-timetable-generator/scripts/ttgen` must print nothing. `SKILL.md` does not change.
- The grid (`gridHTML`), the PDF and the Excel file are not changed by this plan. On a screen wider than 700 px a page must look exactly as it does on main.
- The list's class names must not be ones the grid uses (`row`, `ruler`, `track`, `cell`, `bk`, `t`, `tf`, `ts`, `dl`, `wk`): tests and styles tell the two apart by them.
- Words are fixed; copy them exactly: the switch "Day" and "Whole week"; a week button is the week's word and " week" ("Odd week", "Even week"); a day with nothing on it reads "No lessons this day."; a time is written as the grid writes it ("8.00–9.00").
- The width that turns the list on is `max-width:700px`.
- Commit after each task, on this branch only. Commit messages end with the line `Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>`. Never push.
- After every task: the `node --check` line (if the page changed), the suites the task names, and `git stash list | wc -l` equal to 2. Judge a suite by its exit status (`if out=$(cmd 2>&1); then …`), one suite at a time.

## Review Focus

1. Today is not known: the calendar has no terms, today is a holiday or a weekend, the request fails or answers 401, or the page is a saved copy with no app. The list opens on the device's weekday in the first week, or on the first day, and never shows an error or a blank. Pinned in Task 1 (the answer's shapes) and Task 3 (`startDay`, `loadToday`).
2. The reader presses a day before the answer about today arrives: their choice stays. Pinned in Task 3.
3. A school with one week, or days named with no week word: no week buttons, the day buttons still work. Pinned in Task 2.
4. A day with no lessons, a page with no lessons at all, and a day whose only lesson is before recess: "No lessons this day.", the page's own "No lessons." as today, and no break strip after the last lesson. Pinned in Task 2.
5. Printing from a phone, and turning the phone on its side: the grid prints, never the list; the chosen day and the "Whole week" choice survive a redraw; a date chosen in the date box shows that date's day in the list with its crossed-out lessons and its exams. Pinned in Task 2 (the style rules, the redraw) and Task 3 (the date view).

---

### Task 1: The app says what school day today is (spec section 8, "Which day it opens on")

**Files:**
- Modify: `app.py` (a new route beside `/api/day`, near line 3462)
- Test: `tests/test_exams.py`

**Interfaces:**
- Produces: `GET /api/today`, open to a session with the right `timetable` or the right `own` (`@need("timetable", "own")`). Answers, always with exactly these keys:
  - `{"date": "2027-01-11", "day": "Odd Mon", "calendar": true}` on a school day (`day` is the item of the published model's `days` that today is, from `relief.calendar.school_day`; `date` is the school's own date, from `_exams_today()`).
  - `{"date": …, "day": null, "calendar": true}` on a weekend, a holiday or outside the terms.
  - `{"date": …, "day": null, "calendar": false}` when the school calendar has no terms.
  - `409` with `{"error": NO_EXAMS_PUB}` when nothing is published; `401` without either right (what `need` gives).
- It carries nothing else: no exams, no lessons, no names.

- [ ] **Step 1: Write the failing test** in `tests/test_exams.py`, in the file's own style (read how `no_calendar_no_new_exam` and the `/api/day` tests publish a made-up timetable, set a calendar, and patch `A._exams_today` near line 1680): `today_says_only_the_school_day`. With a calendar whose term starts on a Monday as "Odd": on that Monday the committee, the shared teacher code, the shared student code and a student's own code session (`/me`'s kind of session) each get `200` and `{"date", "day": "Odd Mon", "calendar": True}` with `set(j) == {"date", "day", "calendar"}`; on the Saturday after it `day` is `None` and `calendar` is `True`; with the calendar's terms emptied `day` is `None` and `calendar` is `False`; a client that is not signed in gets `401`.
- [ ] **Step 2: Run** `$PY tests/test_exams.py`: fails with a `404` for `/api/today`.
- [ ] **Step 3: Add the route** as the Interfaces block says.
- [ ] **Step 4: Run** `$PY tests/test_exams.py`, `$PY tests/test_routes.py`, `$PY tests/test_signin.py`, `$PY tests/smoke.py`: all pass. If `tests/test_routes.py` keeps a list of every route and who may call it, add `/api/today` to it there.
- [ ] **Step 5: Commit** (`feat: the app says what school day today is`).

### Task 2: The page draws the day list (spec section 8, "What it shows", "A way to the whole week")

**Files:**
- Modify: `ttgen/timetable_page.html` (styles near lines 50 to 70 and the two `@media` blocks near 121; `S` near 380; `viewHTML` near 354; the click handling that opens a lesson's box; new functions beside `gridHTML`), and its copy under `skill/`
- Test: `tests/timetable_page.test.js`

**Interfaces:**
- Consumes (step 1, on main): `bandsOf(v, d) -> [{a, b, name}]`, `cellTime(c)`, each cell's `a`, `b`, `d`, `title`, `lines`, `color`, `id`, `exam`, `x`; `weekDay(name) -> [week word, day word]`; `DAYS`, `ND`, `WEEKS`, `PER_WEEK`; `pal`, `clk`, `esc`; `v.only` (the day index of a view on a date) and `v.noday`.
- Produces, in the page's last script:
  - State on `S`: `pd` (the day index the list shows, `0` to start), `pdBy` (`true` once the reader has pressed a day or week button), `whole` (`true` when the reader chose "Whole week").
  - `dayItems(v, d) -> [{a, b, name} | {a, b, c}]`: the kept bands of `bandsOf(v, d)` and the cells of day `d` (as `c`), sorted by `a`, then `b`; on a tie a band comes before a lesson.
  - `dayListHTML(v) -> string`, this shape:
    - `<div class="dwrap">`
    - `<div class="seg pv"><button data-pv="day" class="on">Day</button><button data-pv="week">Whole week</button></div>` (`on` sits on "Whole week" when `S.whole`).
    - Only when `v.only == null` and `WEEKS > 1` and the days have a week word: `<div class="seg pw">` with one `<button data-pw="{w}">Odd week</button>` a week, `class="on"` on the shown day's week.
    - Only when `v.only == null`: `<div class="seg pdy">` with one `<button data-pd="{d}">Mon</button>` for each day of the shown week, `class="on"` on the shown day.
    - `<div class="dlist">`: for each item of `dayItems(v, d)`, where `d` is `v.only` on a date view and `S.pd` otherwise: a break as `<div class="tm q">10.00–10.40</div><div class="bkr">Recess</div>`; a lesson as `<div class="tm">8.00–9.00</div><div class="it" data-id="{id}" tabindex="0" style="--t:#…;--a:#…"><b>{title}</b><span>{line}</span>…</div>`, one `<span>` for each of the cell's lines, none cut off (they may wrap). An exam or event cell is `class="it exam"` with no `data-id` and no colours; a crossed-out lesson is `class="it x"`. A lesson's time is `cellTime(c)`.
    - With no item: `<div class="empty">No lessons this day.</div>` inside `.dlist`.
  - `pickDay(d)`, `pickWeek(w)` (keeps the weekday: `w * PER_WEEK + S.pd % PER_WEEK`), `pickWhole(on)`: set the state (`pdBy` for the first two) and draw the view again as it is now (the same tab, key and date; a student's own page too). The buttons call them through the page's existing click handling (`data-pd`, `data-pw`, `data-pv`).
  - `viewHTML` puts `dayListHTML(v)` just before the grid wherever it draws `gridHTML(v)` today, and gives the card the class `whole` when `S.whole`. The Lessons tab's class grids call `gridHTML` alone, as today.
  - A click or the Enter key on `.it[data-id]` opens the same lesson box as on a grid cell.
  - Styles: on a screen wider than 700 px `.dwrap{display:none}`. Under `@media (max-width:700px)`: `.dwrap` shows; `.card:not(.whole) .gridwrap{display:none}`; under `.card.whole` the week and day buttons and `.dlist` are hidden and the grid shows. Under `@media print`: `.dwrap{display:none!important}` and `.gridwrap{display:block!important}`. The list's look (the two-column grid of time and box, the box's left edge in the subject's colour, the striped strip, the segmented buttons) is the mockup's `.phone`, `.seg`, `.dl`, `.it`, `.bk` rules under new names, with dark-theme values where the mockup has light-only colours (use the page's variables `--panel`, `--line`, `--muted`, `--stripe`, `--stripe2`, `--accent`).

- [ ] **Step 1: Write the failing tests** in `tests/timetable_page.test.js`. The made-up school there has 20-minute periods from 07:40, recess at period 4, lunch at periods 10 and 11; 3A has English at period 0 (two periods) and the science band at period 6 (three periods) on Odd Mon.

```js
P.run('show("classes", "3A")'); let h = P.view();
const list = s => s.slice(s.indexOf('class="dwrap"'), s.indexOf('class="gridwrap"'));
assert(h.indexOf('class="dwrap"') > 0 && h.indexOf('class="dwrap"') < h.indexOf('class="gridwrap"'), "the list comes before the grid, and both are drawn");
let L = list(h);
assert(L.includes('<button data-pv="day" class="on">Day</button><button data-pv="week">Whole week</button>'));
assert(L.includes('<button data-pw="0" class="on">Odd week</button><button data-pw="1">Even week</button>'));
assert(L.includes('<button data-pd="0" class="on">Mon</button>') && L.includes('<button data-pd="4">Fri</button>') && !L.includes('data-pd="5"'), "the shown week's days only");
assert.strictEqual(P.run('JSON.stringify(dayItems(classView("3A"), 0).map(x => [x.a, x.b, x.name || x.c.title]))'),
  JSON.stringify([[460, 500, "EL"], [540, 560, "Recess"], [580, 640, "CS"]]));
assert(L.includes('<div class="tm">7.40–8.20</div><div class="it" data-id="0"') && L.includes('<div class="tm q">9.00–9.20</div><div class="bkr">Recess</div>') && !L.includes("Lunch"));
P.run("pickDay(1)"); L = list(P.view());
assert(L.includes('<button data-pd="1" class="on">Tue</button>') && L.includes('<div class="empty">No lessons this day.</div>') && P.run("S.pdBy") === true);
P.run("pickWeek(1)"); assert.strictEqual(P.run("S.pd"), 6, "the same weekday in the other week");
P.run("pickWhole(true)"); assert(/class="card[^"]* whole/.test(P.view()) && list(P.view()).includes('<button data-pv="week" class="on">Whole week</button>'));
```

And: the title of the science item and each of its lines are in the list whole (no "…"); with a `tweak` to one week and day names with no week word there is no `.pw` and five day buttons; `show("lessons", null)` holds no `dwrap`; a class with no lessons shows the page's "No lessons." and no `dwrap`; the page's style holds `@media (max-width:700px)`, `.card:not(.whole) .gridwrap{display:none}` and, inside the print block, `.dwrap{display:none!important}`; `lessonDialog` opens from an `.it` (call the page's click handler with a fake target as the file's dialog tests do). Older assertions that count things in the whole view (`>Recess<`, `class="cell`, a time text) must be scoped to the grid part with a helper like `list` above, never loosened: say which you changed.

- [ ] **Step 2: Run** `node tests/timetable_page.test.js`: fails ("dayItems is not defined").
- [ ] **Step 3: Write the functions, the styles and the wiring** in the Interfaces block. The list always opens on `S.pd` (0) in this task; Task 3 makes it today.
- [ ] **Step 4: Run** the `node --check` line, `node tests/timetable_page.test.js`, `$PY tests/smoke.py`, `$PY tests/test_routes.py`: all pass. Then the block-replace check for `viewHTML`.
- [ ] **Step 5: Copy to the skill, check the diff is empty, commit** (`feat: on a phone the published timetable shows one day as a list`).

### Task 3: The list opens on today, and follows the date box (spec section 8, "Which day it opens on")

**Files:**
- Modify: `ttgen/timetable_page.html` (beside Task 2's functions, and where the page starts up), and its copy under `skill/`
- Test: `tests/timetable_page.test.js`

**Interfaces:**
- Consumes: Task 1's `GET /api/today` answer; Task 2's `S.pd`, `S.pdBy`, `dayListHTML`, `pickDay`.
- Produces:
  - `startDay(today, wd) -> day index`: `today` is the app's answer or `null`; `wd` is the device's weekday as three letters ("Mon"). When `today.calendar` and `today.day` is one of `DAYS`: its index. When `today.calendar` and `today.day` is null: `0`. Otherwise (no answer, or `calendar` false): the first day of the first week whose day word starts with `wd` (letters compared without case), else `0`.
  - `deviceDay() -> "Mon"`: the device's own weekday as three letters. It is the only place the page reads the clock for this, so a test can compare with it and not depend on the day it runs.
  - `loadToday()`: when the page is served by the app (`APP`) and the screen is 700 px wide or less, asks `/api/today` once. On an answer, and on a failure of any kind, sets `S.pd = startDay(answer or null, deviceDay())` and draws the view again, but only when `S.pdBy` is not set. It never shows a message. It is called once at start-up and again when the screen becomes narrow (`matchMedia("(max-width:700px)")`'s change), and does nothing after its first answer.
  - A saved copy (no `APP`) asks nothing: at start-up `S.pd = startDay(null, deviceDay())`.
  - A view on a date (`v.only != null`, from the date box): the list shows that date's day with no week or day buttons; its exam and event items and its crossed-out lessons are Task 2's `it exam` and `it x`. Leaving the date ("Usual timetable") shows the list on `S.pd` again.
- `tests/timetable_page.test.js`'s `boot` gets a way to say the screen is narrow (its `matchMedia` answers `matches: false` to everything today): a fourth parameter or an option that makes `matchMedia("(max-width:700px)")` match, without changing what the other queries answer.

- [ ] **Step 1: Write the failing tests** in `tests/timetable_page.test.js`:

```js
assert.strictEqual(P.run('startDay({ date: "2026-10-08", day: "Odd Thu", calendar: true }, "Mon")'), 3);
assert.strictEqual(P.run('startDay({ date: "2026-10-22", day: "Even Thu", calendar: true }, "Mon")'), 8);
assert.strictEqual(P.run('startDay({ date: "2026-10-10", day: null, calendar: true }, "Sat")'), 0, "not a school day: the first day");
assert.strictEqual(P.run('startDay({ date: "2026-10-08", day: null, calendar: false }, "Thu")'), 3, "the calendar cannot say: the device's weekday, first week");
assert.strictEqual(P.run('startDay(null, "wed")'), 2);
assert.strictEqual(P.run('startDay(null, "Sun")'), 0);
```

And with narrow boots: `/api/today` answering `{date, day: "Odd Thu", calendar: true}` gives, after `tick()`, a list with `data-pd="3" class="on"` and `fetched` holding `/api/today` exactly once (also after a second `show`); answering `[401, {error: …}]` or not answering at all leaves `S.pd` equal to `startDay(null, deviceDay())` (compare with that call, so the test does not depend on the day it runs) and no message in the view; with `pickDay(1)` run before the answer arrives the list stays on Tue; a boot that is not narrow never asks; a saved copy (no `app`) never asks; a personal page (`mode: "personal"`) asks and opens on today. On 3A with the file's `DAY` answer picked in the date box: the list has no `.pw` and no `.pdy`, holds the exam as `class="it exam"` with the time `7.50–8.50`, and the stopped English lesson as `class="it x"`; after "Usual timetable" the day buttons are back.

- [ ] **Step 2: Run** `node tests/timetable_page.test.js`: fails ("startDay is not defined").
- [ ] **Step 3: Write `startDay`, `loadToday` and the start-up wiring**, and make the list follow a date view.
- [ ] **Step 4: Run** the `node --check` line, `node tests/timetable_page.test.js`, `$PY tests/smoke.py`, `$PY tests/test_staff_passwords.py`: all pass.
- [ ] **Step 5: Copy to the skill, check the diff is empty, commit** (`feat: the phone day list opens on today and follows the date box`).

### Task 4: The exam parts of the page write a time as the grid does (spec section 9)

**Files:**
- Modify: `ttgen/timetable_page.html` (`examHTML` near 580, `eventHTML` near 586, `dutiesHTML` near 593, `myExams` near 639, the duty line of a date view in `dated` near 300), and its copy under `skill/`
- Test: `tests/timetable_page.test.js`

**Interfaces:**
- Consumes: `hm(t)` (on main: `"08:20"` -> `"8.20"`, anything that is not a time unchanged), `clk`, `mins`.
- Produces: `hmAll(text) -> string`: every `HH:MM` inside a text written as `hm` writes it (`"Bus marshal 07:45"` -> `"Bus marshal 7.45"`; a text with no time unchanged; a date such as `2026-10-05` untouched).
- Produces: every time the published page shows from the exams data is written with `hm` or `hmAll`:
  - the Exams and events tab: a paper's and a roster line's start and end (`examHTML`), an event day's start and end and a duty's time (`eventHTML`), "Your duties" start and end (`dutiesHTML`);
  - "My exam timetable": a paper's start and end, an event day's start and end, and the "report" time (`myExams`);
  - the view on a date: the duty text in a teacher's event or exam cell (the cell's own time is already written this way).
- The order of "Your duties" still follows the 24-hour values (sort before writing). The server's answers are not changed: only what the page writes.
- Not in this task: the committee's exam planning pages (`static/exams.js`, their time boxes) and the exam printouts (`exams/printouts.py`). They keep the 24-hour form.

- [ ] **Step 1: Write the failing tests** in `tests/timetable_page.test.js`, with the file's `LIST`, `EVROW`, `STUROW` and `DAY` answers: `hmAll("Bus marshal 07:45") === "Bus marshal 7.45"`, `hmAll("13:00 to 14:30") === "1.00 to 2.30"`, `hmAll("Hall") === "Hall"`, `hmAll("2026-10-05") === "2026-10-05"`; the Exams and events tab for a staff boot holds "7.40–10.40" and "7.45" for the event and no "07:40", "10:40" or "07:45"; a student's "My exam timetable" holds a paper's time in the new form and no `HH:MM`; a teacher's date view with the file's event duty holds "Bus marshal 7.45"; "Your duties" with two duties on one day at 13:00 and 08:00 lists the 8.00 one first. Update the older assertions that expect the 24-hour form in these places, and say which.
- [ ] **Step 2: Run** `node tests/timetable_page.test.js`: fails ("hmAll is not defined").
- [ ] **Step 3: Write `hmAll` and use `hm` or `hmAll` in the five places.**
- [ ] **Step 4: Run** the `node --check` line, `node tests/timetable_page.test.js`, `$PY tests/smoke.py`: all pass.
- [ ] **Step 5: Copy to the skill, check the diff is empty, commit** (`feat: the exam parts of the published page write a time as the grid does`).

### Task 5: The whole of it, checked (the controller's task)

**Files:**
- Create: `docs/superpowers/plans/2026-11-28-timetable-look-step-2-notes.md`

- [ ] **Step 1: Every suite, on the final code.** Quick: each `tests/test_*.py` and `tests/smoke.py` with `$PY`, each `tests/*.test.js` with `node`, `node --check static/app.js`, the page's `node --check` line; the skill copy equal. `tests/test_plan.py` and `tests/test_typed.py --full` are known to fail now and then on a busy computer: a failure of either is run again alone and compared with main before it is called this branch's. Then `--full` on `test_fixes`, `smoke`, `test_typed`, `test_helper`, nothing else running.
- [ ] **Step 2: The browser, with made-up data only**, on a scratch server (its own host name, a scratch data folder with a made-up timetable published and a school calendar set so that today is a school day), the phone size (375 by 812), real pointer clicks: a class page opens on today's day and week; a day button, a week button, "Whole week" and back to "Day"; a lesson's box opened from a list item; a student's own page; a teacher's page; a date with an exam chosen in the date box; the Exams and events tab and "My exam timetable" with a time after noon (1.00, not 13:00); light and dark; the same page at 1366 wide is the grid with no list in sight; the browser's print preview from the phone size is the grid. A picture of the phone list goes to the lead.
- [ ] **Step 3: The notes file:** the calls made while building; what was not tried (a real phone); what the lead must know after the deploy (nothing to do: the list appears on phones at once).
- [ ] **Step 4: Commit** the notes (`docs: notes for the phone day list`). No push, no pull request and no merge without the lead's own words.

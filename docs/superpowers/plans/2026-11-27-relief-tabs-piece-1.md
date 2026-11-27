# Relief piece 1: the words and the new tab — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename four relief tabs, turn "Needs a nudge" into "Not acknowledged" (which also lists today's relief teachers who have not acknowledged), and add the read-only tab "Planned Relief Assignments".

**Architecture:** Words change in the page, the guides, two server constants and the tests that pin them; tab addresses (`#plan`, `#inbox`, `#today`, `#load`) stay. `/api/relief/absences` gains `unacked` per absence. A new team-only route `/api/relief/ahead` lists the covers of the school days after today, reusing Today's row without the who-is-free work; a new page script `static/relief-ahead.js` draws it and hands a date to Today's tab.

**Tech Stack:** Flask blueprint `relief/web.py`, plain JavaScript pages under `static/`, tests as scripts: `.venv/bin/python tests/<name>.py` and `node tests/<name>.test.js`.

**Spec:** `docs/superpowers/specs/2026-11-27-relief-tabs-and-relook-design.md`, section "Piece 1: the words and the new tab" (mockups parts 1 to 3 in `2026-11-27-relief-tabs-mockups.html` beside it). Pieces 2 to 4 of the spec are NOT in this plan.

## Global Constraints

- Tab names, exactly: `Relief Planning`, `All Relief Requests`, `Today's Relief Assignments`, `Planned Relief Assignments`, `Term Relief Report`. The other tabs keep their names.
- Tab addresses stay: `#plan`, `#inbox`, `#today`, `#load`. The new tab is `#ahead` (button `tab-ahead`, pane `pane-ahead`).
- The public repository names the school only as "CTSS" and never a real person. Tests and docs use the made-up names already in the test files (`Ms Evelyn Koh`, `Mr Hugo Ong`, `Ms Grace Wong`, `Mr Team Lee`, `Mr Sam Tan`, `Ms Maya Lee`, `Mr Flex Ng`).
- No real model call in a test. No new dependency.
- NEVER run `git stash`, `git stash pop`, `git checkout -- <file>`, `git reset`, or switch branches. Never `pkill`/`killall` by name: stop only processes you started, by PID. To see old code: `git show HEAD:path > scratch-file`.
- Work only in `/Users/joetay/Developer/tt-generator/tt-relief-tabs` (branch `relief-tabs`). Other worktrees belong to other sessions.
- Commit messages end with the line `Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>`.
- After a block edit of a page script, check that every `const`/`function` the old block defined is still defined or no longer used (`git diff` for removed lines, then `grep -F`).
- A suite passes only when its command exits 0 AND its last line says so; judge with `if out=$(cmd 2>&1); then …`.

## Review Focus

1. **A link already sent** (`/relief#today`, `#inbox`, `#plan`, `#load` in old Telegram messages and bookmarks): each still opens its tab under the new name. Pinned in Task 1 (tab ids unchanged) and the browser check in Task 5.
2. **A relief teacher told of a relief for a later day** (sent out today for tomorrow): not in "Not acknowledged" today; only reliefs dated today count. Pinned in Task 2.
3. **Today outside every term** (holidays) with "This term" chosen on the new tab: the list reaches to the end of the next term, never an error or an empty answer for that reason. Pinned in Task 3.
4. **A split lesson** on the new tab: one row a part, each with its own periods, relief teacher and status. Pinned in Task 3.
5. **"Open this day" before Today's tab was ever opened in this visit**: it opens on the asked date, not on today. Pinned in Task 4 and the browser check.

## File Structure

- `static/relief.html`: tab buttons and panes (Tasks 1, 4).
- `static/relief.js`: the `TABS` list and the wide-table rule (Tasks 1, 4).
- `static/relief-inbox.js`: All Relief Requests, the Not acknowledged view (Tasks 1, 2).
- `static/relief-load.js`, `static/relief-plan.js`, `static/relief-today.js`: headings and words (Task 1); `relief-today.js` also gains `Relief.showDay` (Task 4).
- `static/relief-ahead.js` (new): Planned Relief Assignments (Task 4).
- `relief/web.py`: `TEAM_ONLY`, `unacked` in `whats_in`, `_row(light=)`, the route `ahead` (Tasks 1 to 3).
- `relief/tell.py`: `OPEN_TODAY` (Task 1).
- `README.md`, `docs/DEPLOY.md`: tab names and the new tab (Tasks 1, 5).
- Tests: `tests/test_relief_team.py`, `tests/test_routes.py`, `tests/test_relief_requests.py`, `tests/test_relief_telegram.py`, `tests/relief_inbox.test.js`, new `tests/relief_ahead.test.js`.

---

### Task 1: The tab names and the words that name a tab

**Files:**
- Modify: `static/relief.html` (the four tab buttons, lines 239 to 242, and the two style comments that name a tab), `static/relief.js` (the comments at lines 3 and 91), `static/relief-inbox.js:77` (heading), `static/relief-load.js:56` (heading), `static/relief-today.js:239` (the link "open Today"), the head comments of `relief-inbox.js`, `relief-load.js`, `relief-plan.js`, `relief-today.js`, `relief-dates.js`
- Modify: `relief/web.py:81` (`TEAM_ONLY`), `relief/tell.py:135` (`OPEN_TODAY`), comments in `relief/web.py`, `relief/absences.py`, `relief/bot.py`, `relief/fill.py` that say "What's in" or "Today page"
- Modify: `README.md`, `docs/DEPLOY.md`
- Test: `tests/test_relief_requests.py`, `tests/test_routes.py`, `tests/test_relief_team.py`, `tests/test_relief_telegram.py`, `tests/relief_inbox.test.js`, `tests/relief_today.test.js`

**Interfaces:**
- Produces: `relief.web.TEAM_ONLY == "Only the relief team can open this."`; `relief.tell.OPEN_TODAY == "Open Today's Relief Assignments"`; tab button texts as in Global Constraints; headings `<h2>All Relief Requests</h2>` and `<h2>Term Relief Report</h2>`.

- [ ] **Step 1: Write the failing tests.** In `tests/test_relief_requests.py`, beside the check at line 1149 (it reads `static/relief-inbox.js` and `static/relief.js`), add a test `the_tabs_have_their_new_names`:

```python
@rt
def the_tabs_have_their_new_names():
    html = open(os.path.join(ROOT, "static", "relief.html"), encoding="utf-8").read()
    for tab, name in (("plan", "Relief Planning"), ("inbox", "All Relief Requests"), ("today", "Today's Relief Assignments"), ("load", "Term Relief Report")):
        assert f'id="tab-{tab}" data-tab="{tab}" aria-controls="pane-{tab}" hidden>{name}<' in html, tab
    for old in (">Plan relief<", ">What's in<", ">Today<", ">Load<"): assert old not in html, old
    js = {f: open(os.path.join(ROOT, "static", f), encoding="utf-8").read() for f in ("relief-inbox.js", "relief-load.js", "relief-today.js")}
    assert "<h2>All Relief Requests</h2>" in js["relief-inbox.js"] and "<h2>Term Relief Report</h2>" in js["relief-load.js"]
    assert ">show today</button>" in js["relief-today.js"] and "open Today" not in js["relief-today.js"]
    assert WB.TEAM_ONLY == "Only the relief team can open this." and TE.OPEN_TODAY == "Open Today's Relief Assignments"
```

(Use the module aliases the file already has for `relief.web` and `relief.tell`; import them the way its neighbours do if it has none.)

- [ ] **Step 2: Run it and see it fail.** Run: `.venv/bin/python tests/test_relief_requests.py`. Expected: the new test fails on the first tab name.

- [ ] **Step 3: Change the words.**
  - `static/relief.html`: the four button texts. Nothing else about the buttons changes (ids, `data-tab`, `aria-controls`).
  - `static/relief-inbox.js`: heading `All Relief Requests`. `static/relief-load.js`: heading `Term Relief Report`.
  - `static/relief-plan.js:493` keeps `Plan relief for a colleague` (it names the form, not the tab).
  - `static/relief-today.js:199,507` keep `Relief today` / `Relief on {day}` (they name the date). Line 239: the link text becomes `show today` (it shows today's date in the same tab; "open Today" read as a tab name).
  - `relief/web.py`: `TEAM_ONLY = "Only the relief team can open this."` (it answers every team route, not one tab).
  - `relief/tell.py`: `OPEN_TODAY = "Open Today's Relief Assignments"`.
  - Comments in the listed files: where one names a tab, use the new name.
  - `README.md` and `docs/DEPLOY.md`: every place a tab is named (bold or not) takes the new name: `**Plan relief** for a colleague` becomes `**Relief Planning**: plan relief for a colleague`; `**What's in**` → `**All Relief Requests**`; `**Today**` / "on Today" / "Today opens" (the tab) → `**Today's Relief Assignments**`; `**Load**` (the tab, README line 43) → `**Term Relief Report**`; the quoted page sentence in `docs/DEPLOY.md:249` becomes `"Today still has {n} to arrange: show today."`. "Load your setup", "Load from file" and "What's inside" are not tabs: leave them. The README's test list line for `relief_inbox.test.js` says "All Relief Requests".
- [ ] **Step 4: Bring the pinned tests into line.** `TEAM_ONLY` literals in `tests/test_routes.py:630`, `tests/test_relief_requests.py:591`, `tests/test_relief_team.py:1628`, `tests/test_relief_telegram.py:8019`; the button literals `"Open relief today"` in `tests/test_relief_telegram.py` (lines 4611, 7512, 9025). `tests/test_relief_telegram.py:4646` looks for the label inside an old plan document: old plans are history and are not rewritten, so take `RE.OPEN_TODAY` out of that loop and assert its value directly instead. In `tests/relief_inbox.test.js` and `tests/relief_today.test.js`, any assertion on "What's in" or "open Today" follows the new words; the last line of `relief_inbox.test.js` reads `relief All Relief Requests tests passed`.
- [ ] **Step 5: Run.** `.venv/bin/python tests/test_relief_requests.py`, `tests/test_routes.py`, `tests/test_relief_team.py`, `tests/test_relief_telegram.py`, `tests/test_relief.py`, `tests/test_exams_relief.py`; `node tests/relief_inbox.test.js`, `node tests/relief_today.test.js`. Expected: each exits 0 with its "… tests passed" line. Then `grep -rnF -e "What's in" -e "Needs a nudge" -e "Open relief today" static relief README.md docs/DEPLOY.md` shows only `Needs a nudge` lines in `static/relief-inbox.js` and `README.md:45` (Task 2 changes those).
- [ ] **Step 6: Commit.** `git add -A static relief README.md docs/DEPLOY.md tests && git commit -m "Relief: the tabs take the names the relief team uses"` (with the co-author line).

---

### Task 2: "Not acknowledged", with today's relief teachers

**Files:**
- Modify: `relief/web.py` (`whats_in`, about line 540; a new helper `_unacked` beside `_cover_counts`)
- Modify: `static/relief-inbox.js` (the `VIEWS` entry `nudge`, `row`, the head comment)
- Modify: `README.md:45`
- Test: `tests/test_relief_team.py`, `tests/relief_inbox.test.js`

**Interfaces:**
- Produces: each absence of `GET /api/relief/absences` carries `unacked`: a list, in period order, of `dict(who: str, p: int, n: int, started: bool)`, one for each cover of the absence that is dated today (the school's date), needed, not stopped by an exam or event, approved and not acknowledged nor asked to change (`cover.state == "approved"`), and has reached its teacher (`cover.reached(r, x, c, now, settings, pub)`); `started` is `hours.starts(pub, x, c) <= now`. `[]` for a cancelled absence. `nudge` stays as it is.

- [ ] **Step 1: Write the failing server test** in `tests/test_relief_team.py`, after `whats_in_counts_covers_and_marks_the_nudge`, with that test's helpers (`fresh`, `staff`, `absent`, `at`, `CV`, `ok`, the key constants):

```python
@rt
def whats_in_lists_todays_relief_teachers_who_have_not_acknowledged():
    fresh(); team = staff(TEAMER)
    i = absent()["id"]                                                         # Tue 13 Oct, as the other tests' absence
    un = lambda: {x["id"]: x["unacked"] for x in ok(team.get("/api/relief/absences"))["absences"]}[i]
    with at("2026-10-13T07:00:00+08:00"):
        assert un() == [], "nobody approved"
        CV.change(i, K5, SAM, TEAMER, PUB, ST); assert un() == [], "approved, not sent out"
        CV.send_out(i, K5, SAM, TEAMER, PUB, ST)
        p5 = [x for x in AB.load(i)["lessons"] if x["key"] == K5][0]
        assert un() == [dict(who=SAM, p=p5["p"], n=p5["n"], started=False)], "as soon as it reaches them"
    with at("2026-10-12T10:00:00+08:00"): assert un() == [], "the day before: not a relief of today"
    with at("2026-10-13T14:55:00+08:00"): assert un()[0]["started"] is True, "its lesson has started: still listed"
    with at("2026-10-13T07:00:00+08:00"):
        CV.acknowledge(i, K5, SAM); assert un() == [], "acknowledged"
    with at("2026-10-14T07:00:00+08:00"): assert un() == [], "the day is over"
```

(Adjust the two clock times to the fixture's periods if `K5` does not start between them: the first must be in school hours before the lesson starts, the third after it starts on the same day. Add one more assertion with the file's own helper for a lesson an exam stops, if the file has one: its cover is not listed.)

- [ ] **Step 2: Run** `.venv/bin/python tests/test_relief_team.py`. Expected: FAIL with `KeyError: 'unacked'`.
- [ ] **Step 3: Implement** `_unacked(r, pub, settings, links, now, today) -> list` in `relief/web.py` and set `v["unacked"]` in `whats_in` (one `now` and `today` for the whole answer, as `nudge` uses). A record or cover that cannot be read gives `[]` for that absence and one `current_app.logger.error` line with the error's kind only, as the file's other readers do.
- [ ] **Step 4: Run** the suite again. Expected: PASS, and the old nudge test still passes.
- [ ] **Step 5: Write the failing page tests** in `tests/relief_inbox.test.js`:

```js
t("Not acknowledged is the view's name, and it takes a head's planning or a relief of today", async () => {
  const html = await shown([record({ id: "a", nudge: true, how: "planned", by: "Mr Hugo Ong" }), record({ id: "b", unacked: [{ who: "Mr Sam Tan", p: 6, n: 3, started: false }] }), record({ id: "c" })]);
  assert.ok(html.includes("Not acknowledged (2)") && !html.includes("Needs a nudge"), html);
});
t("a row says which relief teacher has not acknowledged, and when the lesson has started", async () => {
  const html = await shown([record({ unacked: [{ who: "Mr Sam Tan", p: 6, n: 3, started: false }, { who: "Ms Maya Lee", p: 11, n: 1, started: true }] })]);
  assert.ok(html.includes("Not acknowledged: Mr Sam Tan, P7–P9") && html.includes("Not acknowledged: Ms Maya Lee, P12 · started"), html);
});
t("an answer without unacked (an older server) is as before", async () => {
  const html = await shown([record()]);
  assert.ok(html.includes("Not acknowledged (0)") && !html.includes("Not acknowledged:"), html);
});
```

- [ ] **Step 6: Run** `node tests/relief_inbox.test.js`. Expected: the first new test fails.
- [ ] **Step 7: Implement in `static/relief-inbox.js`.** The `VIEWS` entry becomes `["nudge", "Not acknowledged", r => !!r.nudge || (Array.isArray(r.unacked) && r.unacked.length > 0), "Everyone has acknowledged."]` (the key stays `nudge`). In `row`, under the Relief status chip of an absence that is not cancelled, one `<div class="small pl-changed">` for each entry: `Not acknowledged: {who}, {RF.periods({p, n})}` and ` · started` when `started`; every value through `esc`. The head comment says what the view now holds. `README.md:45` says "Not acknowledged" and what it lists.
- [ ] **Step 8: Run** `node tests/relief_inbox.test.js` and `.venv/bin/python tests/test_relief_requests.py` (line 1149 pins `'"Needs a nudge"'` in the script: it becomes `'"Not acknowledged"'`). Expected: PASS.
- [ ] **Step 9: Commit.** `git commit -m "Relief: Not acknowledged also lists today's relief teachers"`.

---

### Task 3: The route for Planned Relief Assignments

**Files:**
- Modify: `relief/web.py` (`_row` gains `light=False`; new route after `today`)
- Test: `tests/test_relief_team.py`, `tests/test_routes.py`

**Interfaces:**
- Consumes: `_row(pub, settings, records, r, x, c, i, links=None, now=None)`, `_gate(*TEAM)`, `_links_or_none`, `relief.calendar.term_of(cal, date)`, `relief.hours.school(settings, pub, date)`.
- Produces: `GET /api/relief/ahead?span=weeks|term` (endpoint `relief_web.ahead`; `span` left out or anything else: `weeks`), relief team only (`TEAM` gate). Answer: `dict(as_of: ISO date-time, span: "weeks"|"term", until: ISO date, days: [dict(date: ISO date, away: int, counts: dict, rows: [row])])`.
  - The window is every date after today (the school's date) up to and including `until`. `weeks`: today + 14 days. `term`: the end of the term today is in (`term_of`); when today is in no term, the end of the first term that starts after today; with no such term, as `weeks`.
  - `rows`: one for each cover of each needed lesson dated in the window, of absences that are not cancelled, as `_row(..., light=True)` gives it: the same keys as Today's row, with `stale`, `over_now`, `nobody` False and `warn` None (who is free is not worked out, so a term's list stays quick), `told` None and `linked` False. In each day sorted by `(p, absent, ckey)`.
  - `away`: how many different absent teachers the day's rows have. `counts`: Today's counts for that day's rows, the same keys, worked out the same way (extract the loop at the end of `today()` into `_counts(rows) -> dict` and use it in both).
  - A date with no row is left out. `days` in date order.
- `_row(..., light=True)` returns the row at the point just before `free_then` is called (after the cancelled and stopped returns).

- [ ] **Step 1: Write the failing tests** in `tests/test_relief_team.py`, with the file's helpers:

```python
@rt
def ahead_lists_the_days_after_today():
    fresh(); team = staff(TEAMER)
    get = lambda q="": ok(team.get("/api/relief/ahead" + q))
    with at("2026-10-12T09:00:00+08:00"):                                        # Mon 12 Oct
        i = absent()["id"]                                                     # Tue 13
        k = absent(teacher=RUTH, dates=["2026-10-16"])["id"]                   # Fri 16
        t_ = absent(teacher=GRACE, dates=["2026-10-12"])["id"]                 # today: never in the list
        j = get()
        assert (j["span"], j["until"]) == ("weeks", "2026-10-26") and [d["date"] for d in j["days"]] == ["2026-10-13", "2026-10-16"], j
        tue = j["days"][0]
        assert tue["away"] == 1 and all(r["id"] == i for r in tue["rows"]) and tue["counts"]["need"] == len(tue["rows"]), tue
        assert [r["p"] for r in tue["rows"]] == sorted(r["p"] for r in tue["rows"])
        assert all(r["warn"] is None and r["nobody"] is False and r["stale"] is False for d in j["days"] for r in d["rows"]), "who is free is not worked out"
        today_rows = ok(team.get("/api/relief/today?date=2026-10-13"))["rows"]
        assert [(r["ckey"], r["state"], r["pick"], r["out"]) for r in tue["rows"]] == [(r["ckey"], r["state"], r["pick"], r["out"]) for r in today_rows], "as Today words them"
        CV.split(i, K2, 3, TEAMER)
        assert len(get()["days"][0]["rows"]) == len(tue["rows"]) + 1, "a split lesson: a row a part"
        AB.cancel(k, "Better", RUTH); assert [d["date"] for d in get()["days"]] == ["2026-10-13"], "a cancelled absence is left out"
        assert get("?span=nonsense")["span"] == "weeks"

@rt
def ahead_this_term_reaches_the_end_of_the_term_and_over_a_holiday_the_next():
    fresh(); team = staff(TEAMER)
    term = RC.term_of(ST["calendar"], D13)
    with at("2026-10-12T09:00:00+08:00"):
        j = ok(team.get("/api/relief/ahead?span=term")); assert (j["span"], j["until"]) == ("term", str(term["end"])[:10]), j
    after = (datetime.date.fromisoformat(str(term["end"])[:10]) + datetime.timedelta(days=1)).isoformat()
    with at(after + "T09:00:00+08:00"):
        j = ok(team.get("/api/relief/ahead?span=term"))
        nxt = [t for t in ST["calendar"]["terms"] if str(t["start"])[:10] > after]
        assert j["until"] == (str(min(nxt, key=lambda t: str(t["start"]))["end"])[:10] if nxt else (datetime.date.fromisoformat(after) + datetime.timedelta(days=14)).isoformat()), j

@rt
def ahead_is_the_relief_teams():
    fresh()
    for name in (SAM, GRACE): no(staff(name).get("/api/relief/ahead"), 403, TEAM_ONLY)
```

(`RC` = `relief.calendar`; use the file's own names for the settings and the date constants. If the fixture calendar has one term only, add a second term to it inside the second test with the file's `saved_settings` helper so both branches run.)

In `tests/test_routes.py`: add `"relief_web.ahead": ('relief',)` beside `"relief_web.today"` and `("GET", "/api/relief/ahead")` to the `RELIEF_INSIDE.update` tuple at line 636.

- [ ] **Step 2: Run** `.venv/bin/python tests/test_relief_team.py` and `.venv/bin/python tests/test_routes.py`. Expected: FAIL (404 for the route; the routes test names the missing endpoint).
- [ ] **Step 3: Implement** `_row(..., light=False)`, `_counts(rows)`, and `@bp.get("/api/relief/ahead") @need("relief") def ahead()` with a docstring in the file's style that says what the answer holds. Read the records, settings and links once for the request.
- [ ] **Step 4: Run** both suites. Expected: PASS; `today`'s own tests pass unchanged (`_counts` gives what the loop gave).
- [ ] **Step 5: Commit.** `git commit -m "Relief: the route for Planned Relief Assignments"`.

---

### Task 4: The Planned Relief Assignments tab

**Files:**
- Create: `static/relief-ahead.js`, `tests/relief_ahead.test.js`
- Modify: `static/relief.html` (tab button after `tab-today`, pane after `pane-today`, script tag after `relief-today.js`, a few style rules), `static/relief.js` (`TABS`: `["ahead", me => !!me.can_team]` after `today`; `ahead` in the wide-table rule; the head comment), `static/relief-today.js` (`Relief.showDay`)
- Test: `tests/relief_ahead.test.js`, `tests/relief_today.test.js`, `tests/test_relief_requests.py`

**Interfaces:**
- Consumes: `GET /api/relief/ahead?span=` (Task 3); `Relief.tab`, `Relief.go`, `Relief.api`, `Relief.say`, `Relief.plural`; `ReliefForm.esc`, `.day`, `.title`, `.periods`.
- Produces: `Relief.showDay(iso: string) -> void` in `static/relief-today.js`: shows Today's Relief Assignments on that date, whether or not the tab was opened before (before its first `init`, the date waits and `init` opens on it instead of the server's day); a text that is not `YYYY-MM-DD` only opens the tab.
- The tab: heading `Planned Relief Assignments`; under it `Every relief on the school days after today · as of {day, HH:MM}`; a choice `Next 2 weeks` | `This term` (`aria-pressed`), and `Refresh`. For each day a heading line `{Mon 30 Nov}` with `{n} teacher(s) away · {n} lesson(s)` and chips from `counts`: `{n} waiting for you` (amber), `{n} no relief teacher yet` (amber), `{n} approved, not sent out`, and `all approved` (green) when `need > 0` and waiting, open, unsent and change are all 0. Then a table `Time | Lesson | For | Relief teacher | Status | ` with one row a cover and one button per day's heading, `Open this day` (`data-ah="open" data-date="…"`). Status words by the row:

| row | status |
|---|---|
| `state` open | `No relief teacher yet` |
| waiting | `Waiting for you` |
| approved, `out` unsent | `Approved · not sent out` |
| approved, `out` held | `Approved · will be sent {Mon 30 Nov, 06:45}` (from `goes_at`; without it `Approved · sent out`) |
| approved, `out` sent | `Approved · sent out` |
| acknowledged | `✓ Acknowledged` |
| change | `Asked to change` |
| stopped | `Not happening` and, small under it, `stopped` |
| cancelled | (never sent by the route; drawn as `—`) |

  The relief teacher cell: `pick.who` (bold), `Planned by {planned_by}` small under it when set; `—` (muted) when open; for `change`, the old name struck through and `New pick: {change.pick.who}` when there is one. Empty list: `No relief on the school days after today.` (weeks) or `No relief for the rest of the term.` (term). While reading: `Loading…`; a failed read: the server's sentence with `Try again`. `shown()` reads again. Nothing on the tab changes a record.

- [ ] **Step 1: Write the failing page tests** in a new `tests/relief_ahead.test.js`, set up as `tests/relief_inbox.test.js` is (the real `relief-form.js`, a stand-in `window.Relief` whose `api` answers `/api/relief/ahead…` from a value written in the test and records each URL asked, `go` and `showDay` recording their calls). Rows are built by a helper `row(more)` with Today's keys. Tests, by name, with these assertions:
  - `"a day's heading counts teachers, lessons and what waits"`: two days; the first has two rows of one absent teacher (one waiting, one open) → the HTML has `Tue 13 Oct`, `1 teacher away · 2 lessons`, `1 waiting for you`, `1 no relief teacher yet`; the second day all acknowledged → `all approved`.
  - `"each status reads as Today says it"`: one row per line of the table above; each expected string is in the HTML, and `Approved · will be sent Wed 14 Oct, 06:45` for `goes_at: "2026-10-14T06:45:00+08:00"`.
  - `"a request to change shows the old name struck and the new pick"`: `<s class="muted">Mr Sam Tan</s>` and `New pick: Ms Maya Lee`.
  - `"This term asks the server for the term"`: clicking the button with `data-ah="span" data-v="term"` makes the next URL asked `/api/relief/ahead?span=term`, and that button then has `aria-pressed="true"`.
  - `"Open this day hands the date to Today"`: clicking `data-ah="open" data-date="2026-10-13"` calls `Relief.showDay("2026-10-13")` once.
  - `"nothing of a name is written into the page as markup"`: a row with `absent: "<b>x</b>"`, `pick.who: "<i>y</i>"` → the HTML has neither `<b>x` nor `<i>y`.
  - `"an empty answer says so for each span"`, `"a failed read shows the server's sentence and Try again"`.
  Last line printed: `{n} relief Planned Relief Assignments tests passed`.
  In `tests/relief_today.test.js` add `"showDay before the tab was opened opens it on that date"` (call `window.Relief.showDay("2026-10-16")` before `init`; after `init` the first URL asked is `/api/relief/today?date=2026-10-16`) and `"showDay on an open tab changes its date"` (the next URL asked carries the date; `Relief.go` was called with `"today"`).
  In `tests/test_relief_requests.py`, extend `the_tabs_have_their_new_names`: `id="tab-ahead" data-tab="ahead" aria-controls="pane-ahead" hidden>Planned Relief Assignments<`, `id="pane-ahead"`, the script tag `/static/relief-ahead.js` after `/static/relief-today.js`, and `["ahead", me => !!me.can_team]` in `static/relief.js`.
- [ ] **Step 2: Run** `node tests/relief_ahead.test.js`, `node tests/relief_today.test.js`, `.venv/bin/python tests/test_relief_requests.py`. Expected: FAIL (no such file; `showDay` is not a function; the tab is not in the page).
- [ ] **Step 3: Implement** `static/relief-ahead.js` (an IIFE as the other tab scripts, with a head comment saying what the tab is and that it is read-only), the page and `relief.js` changes, and `Relief.showDay` in `relief-today.js`. Style: reuse `rtable`, `chip`, `seg`, `ab-top`, `tablewrap`; the few new rules (the day heading) go in `relief.html`'s style block under a comment `/* Planned Relief Assignments */`.
- [ ] **Step 4: Run** the three suites and `node --check static/relief-ahead.js static/relief-today.js static/relief.js`. Expected: PASS.
- [ ] **Step 5: Commit.** `git commit -m "Relief: the Planned Relief Assignments tab"`.

---

### Task 5: The guides, every suite, the notes

**Files:**
- Modify: `README.md` (the relief section: one bullet for **Planned Relief Assignments**; the files table row for `static/relief.html` names `relief-ahead.js`; the test list gains `node tests/relief_ahead.test.js`), `docs/DEPLOY.md` (where the relief team's tabs are listed, the new tab in a line)
- Create: `docs/superpowers/plans/2026-11-27-relief-tabs-piece-1-notes.md`

- [ ] **Step 1: The guides.** The README bullet, in the README's own style: the tab is the relief team's, read-only, lists every relief on the school days after today by date (next two weeks or the rest of the term), and "Open this day" goes to Today's Relief Assignments on that date.
- [ ] **Step 2: Every suite.** Run each `tests/*.py` with `.venv/bin/python` and each `tests/*.test.js` with `node`, one at a time, judging each by its exit status and last line; then `--full` on `test_typed`, `test_helper`, `test_fixes` and `smoke`, alone, with nothing else running. A `--full` failure of `test_helper` or `test_typed` is compared with the same suite on `origin/main` in a detached scratch worktree before it is called this branch's fault.
- [ ] **Step 3: The names check.** `git diff origin/main --stat`, then check that no added line names the school in full or a real person: the only names in added lines are the made-up ones listed in Global Constraints.
- [ ] **Step 4: The notes file**: rulings made while building, known limits (the new tab does not work out who is free, so "no longer free" warnings show only after Open this day), what the browser check covered and what it did not, and anything left for pieces 2 to 4.
- [ ] **Step 5: Commit.** `git commit -m "Relief piece 1: guides and notes"`.

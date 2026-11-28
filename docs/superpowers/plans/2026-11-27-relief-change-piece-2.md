# Relief piece 2: changing a request — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The relief team, the absent teacher and the head who planned it can change a request's dates and times (seeing first what the change does, lesson by lesson); "Relief not needed" takes an optional reason everywhere and is on Today's rows; the whole request can be cancelled from the Edit view; the people concerned are told on Telegram.

**Architecture:** `relief/absences.py` gains `plan_change` (works out Kept / Added / No longer needed, no writing) and `change` (saves it, in place, as `update_exams` does for a backup: dropped lessons end their cover and go to the record's `gone` list; a `changes` list records who changed what and when). Two routes in `relief/web.py` (`…/change/preview`, `…/change`) answer the list in plain lines and save. `relief/tell.py` works the new Telegram messages out from `changes` and `not_needed.at`, as it does every message. One page script, `static/relief-change.js` (`window.ReliefChange`), draws the change controls and is used by My absences and Planned by me (`relief.js` cards) and by All Relief Requests' new Edit button (`relief-inbox.js`); Today's rows get their own "Relief not needed" button (`relief-today.js`).

**Tech Stack:** Flask blueprint `relief/web.py`, plain JavaScript pages under `static/`, tests as scripts: `.venv/bin/python tests/<name>.py` and `node tests/<name>.test.js`.

**Spec:** `docs/superpowers/specs/2026-11-27-relief-tabs-and-relook-design.md`, section "Piece 2: changing a request", and calls 6, 7, 8, 16, 17 of "Calls made in this design"; mockup part 6 in `2026-11-27-relief-tabs-mockups.html` beside it. Pieces 3 and 4 are NOT in this plan (no re-look, no Notify all, no long-run mark).

## Global Constraints

- Who may change, mark not needed or cancel: the absent teacher, the head who planned it (`absences._owner`), and the relief team (`team=True`, asked in `relief/web.py` with `has("relief.team")`). The same people for all three. No new right.
- A backup made for an exam duty or an event (`r["exams"]`) cannot be changed: `absences.BACKUP = "This relief follows the exam or event schedule: change the duty instead."` The pages show no change controls on it. (Its lessons may still be marked not needed and needed again, as now.)
- A lesson dated before today, or one of today whose first period has begun (`absences._started`), is never dropped by a change.
- The same checks as a new request: up to 20 school days, today or later (`_iso_dates`, `lessons.on_date`'s sentences); periods as `new` checks them; the teacher's other absences may not overlap (`_no_overlap`); a shared lesson with a co-teacher who is there is not needed (`as_now`); something must be left to cover (`something_to_cover`).
- Reasons: a change's reason is optional (at most 200 characters); Relief not needed's reason is optional everywhere (at most 200); Cancel the whole request needs a reason (1 to 200, `SAY_WHY`), as now.
- One clock: school time. `absences._now()` for stamps, `fill._when(_now())` for "has it started", `lessons.today()` for the date.
- No message carries a typed reason (the change's, not needed's or the cancel's), the remarks, or a pick's history. The absent teacher who may not open every absence sees a relief teacher's name only once that teacher has acknowledged (as `web._hidden`).
- The public repository names the school only as "CTSS" and never a real person. Tests, mockups and docs use the made-up names already in the test files (`Ms Evelyn Koh`, `Mr Sam Tan`, `Ms Maya Lee`, `Ms Grace Wong`, `Mr Team Lee`, `Mr Busy Chan`, `Ms Ruth Goh`, `Mr Hugo Ong`, and the names `tests/test_relief_telegram.py` already defines, such as its `ROSA` and `LEE`).
- No real model call in a test. No new dependency.
- NEVER run `git stash`, `git stash pop`, `git checkout -- <file>`, `git reset`, or switch branches. Never `pkill`/`killall` by name: stop only processes you started, by PID. To see old code: `git show HEAD:path > scratch-file`.
- Work only in the worktree `tt-relief-change` (branch `relief-change`, from main 3935ccb). Other worktrees belong to other sessions.
- Commit messages end with the line `Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>`.
- After a block edit of a page script, check that every `const`/`function` the old block defined is still defined or no longer used (`git diff` for removed lines, then `grep -F`).
- A suite passes only when its command exits 0 AND its last line says so; judge with `if out=$(cmd 2>&1); then …`.

## Review Focus

1. **A relief already sent out and acknowledged, on a lesson the change drops**: its relief teacher is told "No longer needed" once (the `gone` message), never "moved"; the lesson's history stays in the record's `gone` list. Pinned in Task 2 (record) and Task 4 (message).
2. **A change of today's request after some lessons started** (10:00, whole day → P9 onwards): a started lesson stays even though it is outside the new periods; a lesson not started and outside goes. Pinned in Task 2.
3. **Two people on the same request**: one saves; the other saves from an older list. Refused with `absences.LOOKED`, nothing written. Pinned in Task 2 and Task 3.
4. **The absent teacher alone previews** a head's planned request: no relief teacher's name in any line until that teacher has acknowledged. Pinned in Task 3.
5. **A lesson the change adds that one of the teacher's exam backups holds**: it moves in with its whole cover (as `new` does, `_take_over`); the backup shrinks or is cancelled. Pinned in Task 2.

## File Structure

- `relief/absences.py`: `not_needed` (optional reason, `at`), `_check_periods`, `plan_change`, `change`, `_gone(by=)`, new sentences (Tasks 1, 2).
- `relief/web.py`: routes `change_preview`, `change_save`, the line words `_change_line`, the doc string (Task 3).
- `relief/tell.py`, `relief/words.py`: the messages `changed`, `notneeded`, `edited`, the officer's `officer:{id}:{at}`, the absent teacher on `cancelled` (Task 4).
- `static/relief-change.js` (new): `window.ReliefChange` (Task 5); `static/relief.html`: its script tag and styles (Task 5).
- `static/relief.js`: "Not needed" wording and the cards' "Change dates or times" (Tasks 1, 5).
- `static/relief-inbox.js`: Edit, the "Changed by" line (Task 6); `static/relief-today.js`: the row button (Task 6).
- `README.md`: the relief section (Task 7). `docs/DEPLOY.md` unchanged (nothing new goes to the AI).
- Tests: new `tests/test_relief_change.py` (Tasks 2, 3), new `tests/relief_change.test.js` (Task 5); changed `tests/test_relief_requests.py`, `tests/test_relief_team.py`, `tests/test_relief_telegram.py`, `tests/test_routes.py`, `tests/relief_inbox.test.js`, `tests/relief_today.test.js`.

---

### Task 1: Relief not needed with an optional reason

**Files:**
- Modify: `relief/absences.py:505-516` (`not_needed`)
- Modify: `static/relief.js:207` (the line of a lesson not needed), `:223-224` (the why box)
- Test: `tests/test_relief_requests.py` (`a_shared_lesson_needs_no_relief_unless_asked` and every other test that pins `not_needed == dict(by=…, why=…)` or the "Say why in a line." refusal of `not_needed`), `tests/test_relief_team.py` likewise (grep both for `not_needed(` and `SAY_WHY`)

**Interfaces:**
- Produces: `absences.not_needed(id, key, why, by, *, team=False)`: `why` may be empty or missing; more than 200 characters → `ValueError(absences.WHY_LONG)`, `WHY_LONG = "Keep the reason under 200 characters."`; the lesson's `not_needed` becomes `dict(by=by, why=why, at=absences._now())`. `cancel` keeps `SAY_WHY`.

- [ ] **Step 1: Write the failing test.** In `tests/test_relief_requests.py` add `not_needed_takes_an_optional_reason`: mark a lesson not needed with `""`, then with `None`, then with `"Class on a trip"`; assert `x["not_needed"] == dict(by=EVE, why="", at=AB._now())` (and `why="Class on a trip"` for the last); assert `refuses(AB.WHY_LONG, lambda: AB.not_needed(i, key, "x" * 201, EVE))`; assert `AB.cancel(i, " ", EVE)` still raises `"Say why in a line."`.
- [ ] **Step 2: Run it and see it fail.** `.venv/bin/python tests/test_relief_requests.py`. Expected: fails on the empty reason ("Say why in a line.").
- [ ] **Step 3: Implement.** In `not_needed` replace the `1 <= len(why) <= 200` check with `len(why) <= 200` (else `WHY_LONG`) and store `at`. Update the tests that pinned the old dict to include `at`, and turn the old "Say why in a line." refusal of `not_needed` into the `WHY_LONG` one.
- [ ] **Step 4: Page words.** In `static/relief.js` `lessonRow`: a lesson not needed by a person reads `Relief not needed: {why}` with a reason and `Relief not needed` without; the box label reads `Why is relief not needed? (optional)`; the button `Mark relief not needed`; the small button that opens it `Relief not needed`. In the code that sends it (`notNeeded`, line ~369), send the box's text as it is, empty allowed (remove any client check that refuses an empty reason).
- [ ] **Step 5: Run** `tests/test_relief_requests.py`, `tests/test_relief_team.py`, `tests/test_relief_telegram.py` (it calls `not_needed` too) and `node --check static/relief.js`. Expected: PASS.
- [ ] **Step 6: Commit** `git commit -m "Relief piece 2: Relief not needed takes an optional reason"`.

### Task 2: Working out and saving a change (`plan_change`, `change`)

**Files:**
- Modify: `relief/absences.py` (after `update_exams`; `new` uses the new `_check_periods`; `_gone` gains `by`)
- Create: `tests/test_relief_change.py` (copy the set-up of `tests/test_relief_team.py` lines 1 to 120: the world, `EVE`'s lessons `K2` P3–P5 1C Science, `K5` P6–P7 1A Science, `K8` P9 5A Art shared with `BUSY` on Tue 13 Oct, `KF` P1–P2 1A Art on Fri 16 Oct; today Mon 12 Oct; `fresh`, `absent`, `refuses`, `snap`, `same`; add `from relief import fill as FL`)

**Interfaces:**
- Consumes: `absences._iso_dates`, `as_now`, `something_to_cover`, `_no_overlap`, `_moving`, `_take_over`, `_started`, `_gone`, `_dates_and_periods`; `lessons.on_date`; `fill._when`.
- Produces:
  - `absences._check_periods(pub, periods) -> list | None`: `None` stays `None`; else `[a, b]` or `ValueError("Choose the periods again.")`, exactly as `new` checks now (`new` calls it).
  - `absences.plan_change(r, data, pub, records, links, now) -> dict(dates, periods, kept, added, gone, earlier, unchanged)`. `data = {dates: [ISO], periods: [a, b] | None}`; `now` a school-time `datetime` (`fill._when(...)`); `records` every record (the others are those with another id). `kept`: the record's own lesson dicts dated today or later that stay (key in the new lessons, or started); `added`: new lesson dicts built as `new` builds them (ISO date, `as_now` others; needed unless one of its other teachers is there, then `not_needed=dict(by="app", why="{names} is there")`; `relief=None, relief_by=None`, empty work); `gone`: the record's lesson dicts that go; `earlier`: how many of its lessons are dated before today (they stay, unlisted); `dates`: sorted ISO dates of the new choice plus every date of a lesson that stays because it is earlier or started; `periods`: the checked new periods; `unchanged`: no added, no gone, and `dates`/`periods` equal the record's. Each list in `(date, p, key)` order. Raises: `CANCELLED`, `BACKUP`, `PAST_ABSENCE` (every date before today), the date and period sentences, `NO_LESSONS` (by `something_to_cover` over the new dates), the overlap sentence (`_no_overlap` over the other records, for added lessons that are needed). Writes nothing.
  - `absences.change(id, data, by, pub, *, team=False, links=None, shown=None) -> (record, plan)`. `data` adds `why` (optional, ≤ 200, else `WHY_LONG`); `shown = {added: [keys], gone: [keys]}` as the preview answered, or `None` (no check). Under `_LOCK`: `_editable`, `_may_change`, `plan_change`; `NOTHING` when `unchanged`; `LOOKED` when `shown` is given and its sorted keys differ from the plan's. Then: each gone lesson `_gone(r, x, why or CHANGED_WHY, by)` and its work files deleted when no lesson left lists them (as `update_exams`); added lessons join `r["lessons"]` (sorted by date, p, key); `_take_over(_moving(records, teacher, needed added), r)` moves a backup's lesson in with its cover; `r["dates"], r["periods"]` from the plan; `r["changes"]` gains `dict(at, by, why, dates, periods, before=dict(dates, periods), added=[keys], gone=[keys])`; `r["changed_at"] = at`; when the record is planned (`how == "planned"`), `by != r["teacher"]`, and a needed lesson was added: `r["acknowledged"] = None`. Save the record, then the backups.
  - Sentences: `BACKUP` as in Global Constraints; `NOTHING = "Nothing changes: choose other dates or times."`; `LOOKED = "The request has changed since you looked: look again before saving."`; `CHANGED_WHY = "The request changed."` (the history line of a dropped relief when no reason is given); `WHY_LONG` from Task 1.
  - `absences._gone(r, x, why, by="app")`: as now, with `by` passed to `cover.clear`.

- [ ] **Step 1: Write the failing tests** in `tests/test_relief_change.py`, each starting with `fresh()`:
  - `a_change_lists_kept_added_and_gone`: `r = absent(by=GRACE, lessons=[dict(key=K2, relief=MAYA), dict(key=K5, relief=SAM)])`. `p = AB.plan_change(AB.load(r["id"]), dict(dates=["2026-10-13", "2026-10-16"], periods=None), PUB, AB.all_records(), None, FL._when(NOW))`: `[x["key"] for x in p["kept"]] == [K2, K5, K8]`, `[x["key"] for x in p["added"]] == [KF]`, `p["gone"] == []`, `p["dates"] == ["2026-10-13", "2026-10-16"]`, `p["unchanged"] is False`. Then periods `[5, 11]`, dates `["2026-10-13"]`: kept `[K5, K8]`, added `[]`, gone `[K2]`. Then the record's own dates and periods: `unchanged is True`. And `snap()` is the same before and after every call.
  - `saving_keeps_the_cover_of_a_kept_lesson_and_ends_a_dropped_one`: as above, `r2, p = AB.change(r["id"], dict(dates=["2026-10-13"], periods=[5, 11], why=""), GRACE, PUB, shown=dict(added=[], gone=[K2]))`; `[x["key"] for x in r2["lessons"]] == [K5, K8]`; `AB._lesson(r2, K5)["relief"] == SAM` and its `approved`, `sent_out` equal what they were; `r2["gone"][0]["key"] == K2` and `r2["gone"][0]["gone"]["why"] == AB.CHANGED_WHY`; the dropped relief is in K2's history as `dropped` by `GRACE`; `r2["changes"] == [dict(at=NOW, by=GRACE, why="", dates=["2026-10-13"], periods=[5, 11], before=dict(dates=["2026-10-13"], periods=None), added=[], gone=[K2])]`; `r2["changed_at"] == NOW`; `same(r2, r["id"])`.
  - `an_added_lesson_asks_a_planned_teacher_to_acknowledge_again`: planned by GRACE, `AB.acknowledge(i, EVE)`; GRACE adds Fri 16 → `acknowledged is None`; again with only lessons taken away → acknowledged stays; EVE herself adding a date → acknowledged stays; an asked record (by EVE) never gains or loses `acknowledged`.
  - `a_started_lesson_is_never_dropped`: `LS.today = lambda: D13`, `AB._now = lambda: "2026-10-13T10:00:00+08:00"` (restore both in `finally`); EVE's own whole-day request for 13 Oct; plan with periods `[8, 11]`: kept `[K2, K8]` (K2 started at 09:00), gone `[K5]` (starts 10:30). A record of 13 and 16 Oct with today 16 Oct: `earlier == 3` and those lessons are never in `gone` whatever is chosen.
  - `a_change_is_refused_as_a_new_request_is`, each with `refuses(text, f)` (nothing written): a backup (`AB.from_exams(EVE, …)` with the exam source the exams tests use) → `AB.BACKUP`; `SAM` without `team` → `AB.NOT_YOURS`; the same choice → `AB.NOTHING`; `shown` that does not match → `AB.LOOKED`; a cancelled record → `AB.CANCELLED`; Fri 23 Oct → `"Fri 23 Oct is not a school day in the calendar."`; `[]` dates → `"Choose up to 20 school days, today or later."`; periods `[3, 1]` → `"Choose the periods again."`; EVE already has an absence on Fri 16 Oct → adding 16 Oct is refused with the overlap sentence naming its sender; a why of 201 characters → `AB.WHY_LONG`; `team=True` by `TEAMER` is allowed.
  - `an_added_lesson_held_by_a_backup_moves_in`: a backup of EVE holding `KF` (built with `AB.from_exams` from `LS.on_date(PUB, CAL, EVE, D16)` with ISO dates); EVE's own request for 13 Oct changed to 13 and 16 Oct: `KF` is in the record with the backup's cover; the backup is cancelled with `why == "Moved to Ms Evelyn Koh's own absence."` (or keeps its other lessons, when it had more).
  - `a_shared_lesson_added_is_not_needed_while_the_co_teacher_is_there`: a request for Fri 16 changed to add Tue 13: `K8` comes in with `needed False` and `not_needed == dict(by="app", why="Mr Busy Chan is there")`.
- [ ] **Step 2: Run** `.venv/bin/python tests/test_relief_change.py`. Expected: fails (`plan_change` not defined).
- [ ] **Step 3: Implement** `_check_periods` (and use it in `new`), `plan_change`, `change`, `_gone(by=)` and the sentences in `relief/absences.py`. Build the added lessons with the same loop `new` uses (`lessons.on_date` for each date with the periods, `as_now`), without `_ask`. A lesson key the record has already is never added. Keep `plan_change` free of writes; `change` does all its writing under `_LOCK`, record first, backups after.
- [ ] **Step 4: Run** `tests/test_relief_change.py`, `tests/test_relief_requests.py`, `tests/test_relief_team.py`, `tests/test_exams_relief.py`. Expected: PASS.
- [ ] **Step 5: Commit** `git commit -m "Relief piece 2: work out and save a change of dates and times"`.

### Task 3: The routes and their plain lines

**Files:**
- Modify: `relief/web.py` (after `cancel`; the module doc string's Bodies paragraph)
- Test: `tests/test_relief_change.py` (route tests, signed in as `tests/test_relief_team.py` signs in for its own route tests), `tests/test_routes.py` (the route map, if it lists routes)

**Interfaces:**
- Consumes: `absences.plan_change`, `absences.change` (Task 2); `web._record`, `_change`, `_gate`, `_hidden` rule, `_sees_all`, `_class_group`, `_periods_text`, `_periods`, `_reached`, `_sync_exams`, `_soon`.
- Produces:
  - `POST /api/relief/absences/<id>/change/preview`, `@need("relief")`, body `{dates, periods}` → 200 `{kept: [item], added: [item], gone: [item], earlier, dates, periods, unchanged, day_periods: _periods(pub)}`; `item = {key, date, p, n, title, periods, line}` (`title` from `_class_group`, `periods` from `_periods_text`). 403 `NOT_YOURS` unless `absences._owner(r, me)` or `has("relief.team")`; 400 with the sentence on a refusal. Writes nothing.
  - `POST /api/relief/absences/<id>/change`, `@need("relief")`, body `{dates, periods, why, shown: {added, gone}}`: through `_change` (its `do` returns `absences.change(...)[0]`, the record) with the same who-may check, history `what = "changed"`, words `f"changed to {days} ({away}): {n} added, {m} no longer needed"` (`_words.days(r)`, `_words.away(r)`, from the saved record and the last change), `after`: `_sync_exams(pub)` then `_soon()`. Answers `_out(record)`.
  - `web._change_line(kind, r, x, pub, reached, hide) -> str` (kind "kept", "added", "gone"; `reached` as `_reached(pub)` gives; `hide`: the caller is only the absent teacher, as `_out` decides). Exact words, a name replaced by `a relief teacher` when `hide` and the cover is not acknowledged:
    - kept: `{who} stays (approved)` / `(acknowledged)` / `(asked to change)` / `(waiting for approval)`; `no relief teacher yet`; `relief not needed`; `not happening: {why}` (an exam or event stops it); a split lesson `split into {n} parts: each keeps its relief teacher`; `, the work set stays` appended when its work has text, a link or a file and it is needed; `under way · ` put in front when it has started.
    - added: `a relief teacher will be picked`; or `{names} is there: no relief needed`.
    - gone: `{who} is told the relief is no longer needed` (a cover that has reached its teacher); `{who} was approved, not told yet: the relief ends`; `the waiting pick ({who}) ends`; `nobody was approved yet`. A split lesson: one clause per part joined with `; `.

- [ ] **Step 1: Write the failing tests** in `tests/test_relief_change.py`:
  - `the_preview_says_what_each_lesson_does`: GRACE plans for EVE on 13 Oct with `SAM` on K5 (approved and sent out at once); GRACE previews dates 13 and 16, periods `[5, 11]`: `kept` lines `["Mr Sam Tan stays (approved)", "relief not needed"]`… (K8: shared, `Mr Busy Chan is there`, so the kept line is `relief not needed`), `added` `[]`, `gone` line for K2 `nobody was approved yet`; `day_periods` has 12 entries; nothing written.
  - `the_absent_teacher_alone_sees_no_name_before_it_is_acknowledged`: the same, previewed by EVE (only the absent teacher): `"a relief teacher stays (approved)"`; after `SAM` acknowledges (`cover.acknowledge` as the team tests do): `"Mr Sam Tan stays (acknowledged)"`.
  - `saving_answers_the_record_and_writes_one_history_entry`: GRACE saves with the `shown` the preview gave → 200, the answer's lessons are the new ones, one history entry `changed` whose text holds `changed to Tue 13 Oct (P6–P12): 0 added, 1 no longer needed` and not the typed why; a second save with the old `shown` → 400 `AB.LOOKED`.
  - `who_may_preview_and_save`: SAM (not owner, not team) → 403 `NOT_YOURS` on both routes; TEAMER (relief team) → 200; signed out → 401.
- [ ] **Step 2: Run** `.venv/bin/python tests/test_relief_change.py`. Expected: the new tests fail (404).
- [ ] **Step 3: Implement** the two routes and `_change_line`; add both routes to the Bodies paragraph of the module doc string. If `tests/test_routes.py` holds a list of the relief routes and their rights, add the two (`relief`).
- [ ] **Step 4: Run** `tests/test_relief_change.py`, `tests/test_routes.py`, `tests/test_relief_team.py`. Expected: PASS.
- [ ] **Step 5: Commit** `git commit -m "Relief piece 2: routes to preview and save a change"`.

### Task 4: Who is told on Telegram

**Files:**
- Modify: `relief/tell.py` (texts; `_absence`; `_officer`; `_cancelled`; `TOLD`; `GATES`, `ANY_HOUR`, `CHECKS`; the module doc string's key list), `relief/words.py` (`KINDS`)
- Test: `tests/test_relief_telegram.py` (beside `cancel_tells_the_team_the_planner_and_the_told`, using its `school`, `absent`, `swept`, `said`, `told_of`, `dues`, `at` helpers)

**Interfaces:**
- Consumes: `r["changes"]` and `x["not_needed"]["at"]` (Tasks 1, 2).
- Produces, keys and exact texts:
  - `changed:{id}:{at}` (kind `changed`, ANY_HOUR) to the absent teacher, for the record's LAST change when its `by` is not the teacher, made since the bot was connected, the teacher reachable, the absence not cancelled or past. `changed_text(by, days, away, added, gone, again)`: `"✏️ Your relief request was changed by {by}\nNow: {days} · {away}\n{parts}"` + (`"\nPlease acknowledge again and set work for the new lessons."` when `again`: the change cleared the acknowledgement). `parts`: `"1 lesson added"`, `"2 lessons no longer needed"`, joined with `" · "`; `"No lesson changed."` when both are 0. Button `[[dict(text=OPEN, url=base + "/relief#mine")]]`.
  - `notneeded:{id}:{key}:{at}` (kind `notneeded`, ANY_HOUR) to the absent teacher when a lesson's `not_needed.by` is neither the teacher nor `"app"`, `at` since the bot was connected, the lesson not over. `notneeded_text(by, lesson, periods, day)`: `"🚫 Relief not needed · {day}\n{lesson} · {periods}\nMarked by {by}."`
  - `edited:{id}:{at}:{name}` (kind `edited`, gated by `_team_may`, made again in the window as `unlinked` is) to each of the team but the absent teacher, for the last change when its `by` is the teacher, it was made today (school date) and one of its added or gone keys is dated today. `edited_text(absent, away, added, gone)`: `"✏️ Changed request for today · {absent}\nNow: {away}\n{parts}"` (parts as above). Button `[[dict(text=OPEN_TODAY, url=base + "/relief#today")]]`. Its check: the absence not cancelled and `ref["date"]` is still today.
  - `officer:{id}:{at}` (kind `officer`) to the reporting officer for the last change, when `officer:{id}` was told (state in `SENT`) and the officer is neither the teacher nor the change's `by`. `officer_changed_text(absent, days, away, kind)`: `"{absent}'s absence has changed: now {days} ({away}): {kind}."` (`kind` as `_officer` gives it: one of the four reasons, never typed text).
  - `cancelled:{id}:{name}` now also to the absent teacher (reachable) when the canceller is not the teacher and the record did not end by itself (`by_itself`) nor was taken over.
  - `words.KINDS` gains `changed="Request changed"`, `notneeded="Relief not needed"`, `edited="Changed request for today"`. `TOLD` gains `"changed:", "notneeded:", "edited:"` inserted before `"late:"` (a test pins `TOLD[-1] == "late:"`).

- [ ] **Step 1: Write the failing tests:** `a_change_by_someone_else_tells_the_absent_teacher` (TEAMER changes EVE's request: `said(EVE)[-1]` is the exact `changed_text`; a change by EVE herself tells her nothing; two changes before a sweep: one message, of the last); `a_planned_teacher_is_asked_to_acknowledge_again` (HUGO plans, EVE acknowledges, HUGO adds a day: the text ends with the acknowledge-again line); `relief_not_needed_by_someone_else_tells_the_absent_teacher` (exact text; by EVE: nothing; by the app: nothing; the typed reason never in `rows("outbox")`); `the_team_hears_when_a_teacher_changes_today` (at 08:00 on 13 Oct EVE drops a lesson of today: each of TEAM and LEE gets the exact `edited_text`, EVE does not; a change that touches only 16 Oct: nobody; a change at 05:00: made from the morning time); `the_officer_hears_the_new_dates` (ROSA, told of the first ones, gets the exact `officer_changed_text`; an officer never told of the first gets nothing); `a_teacher_hears_their_request_was_cancelled_by_someone_else` (TEAMER cancels EVE's own request: EVE gets `CANCELLED_EVE.format(TEAMER)`; EVE cancelling her own: she gets nothing). The relief teacher of a dropped lesson gets `GONE_K5`-style "No longer needed" once (Review Focus 1). Update `cancelled_reaches_whoever_was_told_of_the_absence` ("asked by the teacher, cancelled by the team: … `said(EVE) == []`") and `cancel_tells_the_team_the_planner_and_the_told` ("asked by the teacher: there is no planner") to expect the absent teacher too. `every_kind_is_gated_or_may_go_at_any_hour` must pass with the three new kinds.
- [ ] **Step 2: Run** `.venv/bin/python tests/test_relief_telegram.py`. Expected: the new tests fail.
- [ ] **Step 3: Implement** the texts, `_changed(w, r)`, `_notneeded(w, r)`, `_edited(w, r)` called from `_absence` for a record not cancelled; the officer's change message inside `_officer`; the absent teacher in `_cancelled`; the gates, any-hour lines with their reason comments, checks, kinds and the doc string's key list.
- [ ] **Step 4: Run** `tests/test_relief_telegram.py`, `tests/test_relief_team.py`, `tests/test_relief_change.py`. Expected: PASS.
- [ ] **Step 5: Commit** `git commit -m "Relief piece 2: tell the absent teacher, the team and the officer of a change"`.

### Task 5: The change controls (`ReliefChange`) on My absences and Planned by me

**Files:**
- Create: `static/relief-change.js`, `tests/relief_change.test.js` (load the script as `tests/relief_ahead.test.js` loads `relief-ahead.js`, with `tests/dom.js`)
- Modify: `static/relief.html` (a `<script src="/static/relief-change.js">` after `relief-dates.js` and before `relief.js`; a few `.rc-*` styles beside the `.rd-*` ones), `static/relief.js` (the card's actions)

**Interfaces:**
- Consumes: `POST …/change/preview` and `…/change` (Task 3); `ReliefDates.mount(box, {key, picked, max, onChange})`, `ReliefDates.forget(key)`; `ReliefForm` helpers (`esc`, `day`, `today`, `addDays`, `periodSelects`, `title`); `Relief.api`, `Relief.json`, `Relief.say`.
- Produces: `window.ReliefChange = { initial, body, lines, mount }`:
  - `initial(rec, today) -> {day, picked, away, from, to}`: the record's dates today or later; `day` is `"today"` when they are `[today]`, `"tomorrow"` when `[addDays(today, 1)]`, else `"pick"` with `picked` those dates; `away` `"whole"` when `rec.periods` is null, else `"some"` with `from`/`to` = `rec.periods`.
  - `body(state, today) -> {dates, periods}`: dates as Ask for relief's `dates()` gives them; `periods` null for whole day, `[from, to]` for some.
  - `lines(preview) -> [{mark, text}]`: `{mark: "✔", text: "Kept: {day} {periods}, {title} · {line}"}`, `"➕"` with `Added: …`, `"✖"` with `No longer needed: …`, in that order; plus, when `earlier`, `{mark: "", text: "{n} earlier lesson(s) stay as they were."}`.
  - `mount(box, rec, opts)`: draws into `box`: "Change the dates or times" (Dates: Today / Tomorrow / Pick dates with the calendar, key `"change:" + rec.id`; Away for: Whole day / Some periods with From/To from the answer's `day_periods`); "What this change does" (the preview, read again on each change, newest answer wins; `Nothing changes yet.` while unchanged; a refusal's sentence in its place); "Reason for the change (optional)" (maxlength 200); buttons `Save the change` (disabled while reading, unchanged or refused) and `Close`; under them, when the person is not the absent teacher, `{teacher} is told on Telegram what changed.` `opts`: `{lessons: bool, cancel: bool, onDone(record | null, said)}`; `lessons` and `cancel` are used by Task 6 (the per-lesson "Relief not needed" list and "Or cancel the whole request"), left out here. On save: `POST …/change` with `shown` = the preview's added and gone keys; on success `ReliefDates.forget(key)` and `onDone(record, "Changed.")`; `LOOKED` shows its sentence and reads the preview again.
- In `static/relief.js` `card(r)`: when the card is editable, some date is today or later, the record is not a backup (`!r.exams`) and it is not cancelled, a button `Change dates or times` (`data-act="change"`) beside "Not needed at all: cancel"; pressing it mounts `ReliefChange` in a box under the card's lessons (one open at a time per list; open state kept in `M`); `onDone` puts the answered record (`put`) and paints the card with the said line.

- [ ] **Step 1: Write the failing tests** in `tests/relief_change.test.js`: `initial` for `[today]`, `[tomorrow]`, two dates with one past (`picked` holds only the later one), whole day and `[5, 11]`; `body` for each `day`/`away`; `lines` for a preview with one of each kind and `earlier: 2`, exact texts (e.g. `"Kept: Tue 13 Oct P6–P7, 1A Science · Mr Sam Tan stays (approved)"`).
- [ ] **Step 2: Run** `node tests/relief_change.test.js`. Expected: fails (no file).
- [ ] **Step 3: Implement** `static/relief-change.js`, the script tag and styles, and the card button.
- [ ] **Step 4: Run** `node tests/relief_change.test.js`, `node --check static/relief-change.js static/relief.js`, `.venv/bin/python tests/test_relief_requests.py` (it reads the page files). Expected: PASS.
- [ ] **Step 5: Commit** `git commit -m "Relief piece 2: change dates or times on My absences and Planned by me"`.

### Task 6: Edit on All Relief Requests, and Relief not needed on Today's rows

**Files:**
- Modify: `static/relief-change.js` (the `lessons` and `cancel` parts), `static/relief-inbox.js`, `static/relief-today.js`
- Test: `tests/relief_inbox.test.js`, `tests/relief_today.test.js`, `tests/relief_change.test.js`

**Interfaces:**
- Consumes: `ReliefChange.mount` (Task 5); `POST …/lessons/<key>/not-needed {why}`, `…/needed`, `…/cancel {why}` (they already take `team`).
- Produces:
  - `ReliefChange.mount` with `lessons: true`: "Or change one lesson": each lesson dated today or later, `{day} · {periods} · {title} · {relief}` (relief: the name and state in Today's words, or `no relief teacher yet`, or `relief not needed`); `Relief not needed` opens a line `Why? (optional)` with `Mark relief not needed` and `Back`; a lesson a person marked not needed shows `Needed again`. With `cancel: true`: "Or cancel the whole request": `Say why in a line (needed)` (maxlength 200), `Cancel the request` (disabled while empty) and `Keep it`, and the line `Everyone already told (the relief teachers and {teacher}) gets a message that it is cancelled.` Each action calls `onDone(record, said)`.
  - `relief-inbox.js`: a last column with `Edit` on each row that is not cancelled, has a date today or later and is not a backup; one Edit view open at a time, in a row under it spanning the table (`colspan` of every column), mounted with `{lessons: true, cancel: true}`; on `onDone` the view closes, the said line shows above the table, and the list is read again. The Submitted cell gains, under the stamp, `Changed by {by}, {stamp(at)}` for the record's last change (and the row is new by its `changed_at`, as the server already says).
  - `relief-today.js`: on each row not cancelled and not stopped, a button `Relief not needed` (`data-td="nn"`); on a part of a split lesson (`r.split`) it reads `Relief not needed for the whole lesson` and its box says `This ends every part of {title}.`; the box: `Why is relief not needed? (optional)` (maxlength 200), `Mark relief not needed` (`data-td="nn-go"`), `Back` (`data-td="nn-off"`), one open at a time as Split's is; it posts `/api/relief/absences/{id}/lessons/{key}/not-needed`; since the row leaves the list, `{title}: relief not needed.` is said in the line above the rows.
- [ ] **Step 1: Write the failing tests:** in `tests/relief_inbox.test.js`, Edit shows on a live row and not on a cancelled, past or backup row, and the "Changed by" line; in `tests/relief_today.test.js`, the button's label on a whole and on a split row, none on a stopped or cancelled row; in `tests/relief_change.test.js`, the lesson list's words and the cancel button disabled while the reason is empty.
- [ ] **Step 2: Run** the three node suites. Expected: the new tests fail.
- [ ] **Step 3: Implement** them.
- [ ] **Step 4: Run** the three node suites and `node --check static/relief-change.js static/relief-inbox.js static/relief-today.js`. Expected: PASS.
- [ ] **Step 5: Commit** `git commit -m "Relief piece 2: Edit on All Relief Requests, Relief not needed on Today's rows"`.

### Task 7: The guide, every suite, the browser check, the real timetable, the notes

**Files:**
- Modify: `README.md` (the relief section: changing a request, who may, what each is told, that a backup cannot be changed)
- Create: `docs/superpowers/plans/2026-11-27-relief-change-piece-2-notes.md`

- [ ] **Step 1: README.** Say it in the README's plain style; no real names.
- [ ] **Step 2: Every suite.** Run each `tests/*.py` with `.venv/bin/python` and each `tests/*.test.js` with `node`, one at a time, judging each by its exit status and last line; then `--full` on `test_typed`, `test_helper`, `test_fixes` and `smoke`, alone, with nothing else running. A `--full` failure of `test_helper` or `test_typed` is compared with the same suite on `origin/main` in a detached scratch worktree before it is called this branch's fault.
- [ ] **Step 3: Browser check** on a scratch server under its own hostname (`http://change.localhost:<port>`, a temporary launch entry on a scratch data folder, made-up data, removed afterwards and the launch file compared with `cmp`), with the browser tool's real pointer: as a head, change a planned request (Pick dates, then Some periods) and read the list before saving; as the absent teacher, the same on My absences (no name before it is acknowledged); as the relief team, Edit on All Relief Requests: change, one lesson Relief not needed with and without a reason, Needed again, cancel with a reason; on Today's Relief Assignments, Relief not needed on a whole and on a split row. Note which checks used a real click.
- [ ] **Step 4: The school's real timetable, numbers only.** Publish the newest real folder's `timetable data.sqlite` into a scratch `DATA_DIR` with `store.publish(None, db)`; for the teacher with the most lessons, make a made-up whole-day request over 20 school days and time `plan_change` for a change to 10 of them and to Some periods; report the counts (lessons kept, added, gone) and the seconds. Never print a name. Delete the scratch folder.
- [ ] **Step 5: Notes** beside this plan: rulings, the differences from the picture (`Close` in place of the picture's `Cancel` beside Save, so it is not read as cancelling the request; the change list lives in the Edit view, not in a pop-up), known limits (a change made after the cut-off for today pings nobody, as a late request; a record's periods are the new ones even when a started lesson kept from before lies outside them; only the last change of a record is told on Telegram), what was not tried in a browser.
- [ ] **Step 6: Commit** `git commit -m "Relief piece 2: guide and notes"`. No push, no pull request until the lead says so.

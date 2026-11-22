# Re-fit after small setup changes (stage 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A **Re-fit to the setup** button on step 8 that, for everything on the draft that no longer fits the setup, works out the fewest lesson changes that fit it (bands and each class's day pattern staying put), lists them with their reasons, and applies them as one undoable change only when the committee presses Apply.

**Architecture:** A new module `refit.py` turns the draft's open warnings into targets, finds for each the shortest chain of fixes that settles it (reusing `fixes.judge`, `helper.chain` and `helper.settles`, so a fix is only ever offered when the same checks step 8 uses accept it), and returns a plan (groups of changes, "Needs you", totals). A background job in `app.py` runs it once at a time with progress; `draft.refit_apply` keeps a version and writes the plan's fixes as one batch. Step 8 gets a Re-fit window beside Versions, built like it. No solver, no language model.

**Tech Stack:** Python 3 / Flask (gunicorn 1 worker, 8 threads), plain JavaScript and CSS (no build), plain-assert test scripts (`tests/*.py`, run with `.venv/bin/python`), `node --check`.

**Spec:** `docs/superpowers/specs/2026-11-22-saved-versions-and-refit-design.md` (feature 3 "Re-fit", "The lead's rules for the re-fit", Non-goals, Anti-goals, Constraints). Mockups: `docs/superpowers/specs/2026-11-22-saved-versions-and-refit-mockups.html` screen 3. Built on stage 1 (versions; PR #90).

## Global Constraints

- Every new route uses `@need("committee")`. Nothing publishes.
- **Bands stay where they are:** a lesson whose rows are a band (`fixes._block(rows)`) never moves or swaps; a change to a band itself (a banded subject gaining or losing periods, a group joining or leaving a band, a lesson that should be in a band but is not) goes to Needs you with "This changes the band itself: change it on the board, or ask the agent for a new timetable." A teacher or room change on a band's lessons is made.
- **Each class's day pattern stays:** every other lesson keeps its own day. A lesson may go to another day only when **the lesson itself is barred from every period of its own day** by a Must rule or setting that concerns the lesson (its teacher not available that day, a rule forbidding that day); a day that is only full is never a reason. Such a step carries the tag `another day`. A lesson moved by an earlier target is never touched again.
- Only changes `fixes.judge` / `helper.chain` call "ok" are offered; "prefer" is accepted only when its only reasons are teacher allowance lines (text ending " over the allowance."); a plan may never raise the number of open Prefer warnings or critical mistakes.
- **Teacher changes:** only the teacher who changed is swapped (one removed, one added) and only when every lesson row of the key is taught by the same teachers; anything else is Needs you.
- The search: at most `MAX_MOVES = 3` moves or swaps per target besides its direct change; at most `MAX_NODES = 250` fix lists judged per target; the whole search stops after `BUDGET_S = 30.0` seconds and targets not reached in time go to Needs you as "not looked at in time; run Re-fit again".
- Typed rules (T1, T2 … on step 6): **allow and flag.** Every step inside a typed rule's scope that raises a `typed:{n}:again` warning carries the tag `check T{n} again`; Apply clears the `met` answer of every typed rule its steps touched (only the key `typed:{n}:again`, with `#k` suffixes) in `decisions.json`; totals say how many typed rules to check again; between equally short lists, fewer typed rules touched wins.
- Nothing is changed before Apply. Apply keeps a version first (kind `refit`, named "Before re-fit, {day} {month} {time}"); if any step is refused on the current draft, nothing is written and the sentence says which; Undo takes the whole re-fit back (one batch).
- Refusing to Apply a stale list: "The draft changed since this list was made. Run Re-fit again." (the job's stamp against `draft.stamp()` now).
- Step texts are the fixes' own sentences (`helper.say`); a step's grey reason says why in plain words.
- Needs you lines (exact): the judge's own sentence where there is one; otherwise `NO_FIT = "No list of up to 3 moves fits it."`, `BAND = "This changes the band itself: change it on the board, or ask the agent for a new timetable."`, `SPLIT = "Its lessons are taught by different teachers: change them on the board."`, `NOT_ONE = "More than one teacher changes: change it on the board."`, `LATE = "Not looked at in time; run Re-fit again."`.
- One history entry per Apply: `Re-fit: {N} changes ({M} lessons moved, {K} to another day, {T} typed rules to check again)` (kind `draft`, through `_draft_entry` with what `refit`).
- Plain-assert tests; made-up names only (the sample school); never a real staff name, a school name or a key. Never `git stash`, `git stash pop` or `git checkout -- <file>`. Commits end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **The draft changes between the list and Apply** (another tab, or a newer re-fit): refused with the sentence above, nothing written, no version kept. Test in Task 6 (`test_apply_refuses_a_stale_plan`).
2. **The only fix that would work moves a band or a lesson another target already moved:** that target goes to Needs you and the rest of the plan stands. Tests in Task 4 (`test_a_band_is_never_moved`, `test_a_lesson_moved_by_an_earlier_target_is_left_alone`).
3. **A target the setup does not allow at all** (a teacher not on the setup's list, a room kind nobody has): Needs you with the judge's own sentence; the plan is still made for the others. Test in Task 2 (`test_a_teacher_not_on_the_list_needs_you`).
4. **A big setup change** with many targets: the search stops at the time limit, the plan lists what it found, and what was not reached is in Needs you as "not looked at in time". Test in Task 5 (`test_the_time_limit_leaves_the_rest_in_needs_you`, with `BUDGET_S` set to 0).
5. **A re-fit when nothing needs it** (or before any draft): the button is greyed, and the route refuses with "Nothing to re-fit: the timetable fits the setup." (no job started). Test in Task 6 (`test_nothing_to_refit_is_refused`).

---

### Task 1: What needs a re-fit

**Files:**
- Create: `refit.py`
- Test: `tests/test_refit.py` (new; same frame as `tests/test_versions.py`: temp `DATA_DIR`, the primary sample as the setup, a made-up Lessons workbook uploaded as the draft, `test_*` functions run at the end with "N checks passed")

**Interfaces:**
- Produces:
  - `refit.targets(warnings: list) -> list[dict]` — from `draft.info()["warnings"]` (the dicts `verify.warning` makes, each with `decision`): every one with no decision and of kind `deployment`, `clash`, or `rule` with `strength == "Must"`, in order: deployment `teachers`, `missing`, `periods`, `extra`, `venue`, `half`; then clashes; then Must rules; each `dict(kind=<part or "clash"/"rule">, key=w["key"], text=w["text"], w=w)`. Deployment parts other than those six are skipped.
  - `refit.needed(warnings) -> bool` — `bool(targets(warnings))` (the page's and the route's check).

- [ ] **Step 1: Write the failing tests**
  - `test_targets_are_the_open_fixable_warnings`: with the made-up draft, change a teacher on one step 5 row and add a rule "not available" for a teacher (setup PUT); `info = c.get("/api/draft").get_json()`; `targets(info["warnings"])` holds that deployment teachers warning before the rule; every item has kind/key/text/w.
  - `test_answered_warnings_are_left_out`: answer one of them "met" (POST `/api/draft/decide`), it is no longer a target.
  - `test_a_prefer_rule_is_not_a_target`: a Prefer rule warning and a typed warning are not in the list (make a Prefer rule warning from a sample rule; a typed `met` one likewise).

- [ ] **Step 2: Run to see them fail**
  Run: `.venv/bin/python tests/test_refit.py` — Expected: ModuleNotFoundError: refit.

- [ ] **Step 3: Implement**

- [ ] **Step 4: Run** `.venv/bin/python tests/test_refit.py` — Expected: "N checks passed".

- [ ] **Step 5: Commit**
  `git add refit.py tests/test_refit.py && git commit -m "Re-fit: which warnings it works on"`

### Task 2: The direct change for each kind of target

**Files:**
- Modify: `refit.py`
- Test: `tests/test_refit.py`

**Interfaces:**
- Consumes: `helper._dep_parts`, `helper._of_key`, `verify.planned_rows`, `fixes.add_slots`, `fixes.add_room`, `fixes.room_options`, `fixes.can_delete` (the deletion rule used when step 5 has the surplus `delete`), `fixes.short`.
- Produces: `refit.direct(m, spec, days, target, pool) -> tuple[list[list[dict]], str | None]` — (the candidate direct changes for that target, each a list of fixes; a Needs-you sentence when it can never be one of the app's changes, else None). Candidate ordering is the search's preference (best first).
  - `teachers`: rows of the key whose teachers differ from `planned_rows(spec)[k]["teachers"]` (set). Let `gone = have − want`, `new = want − have` (over the rows' union). If `len(gone) == len(new) == 1` and every row's teachers are the same set: one candidate `[dict(kind="teacher", key=kstr, teachers=[<each row's teachers with gone replaced by new>])]`; else (more than one changed) `NOT_ONE`, or (rows' sets differ) `SPLIT`. A band's teacher change is made the same way.
  - `missing` / `periods` (fewer timetabled than planned): `[[dict(kind="add", key=ks, d, p, n, room=fixes.add_room(...))] for each slot in fixes.add_slots(m, spec, days, ks, n, pool) with state "ok"]`, ordered by (periods that class already has that day, day, period); `n` = `fixes.short(m, spec, pool)`'s `n` for that key.
  - `periods` (more timetabled than planned) and `extra`: one candidate per lesson id of the key to delete, `[dict(kind="delete", id=i, **({"group": ENTIRE or k[1]} if the lesson has several rows else {}))]`; order: the class day with the most periods first, then the latest day, then the latest period.
  - `venue`: `[dict(kind="room", id, group, room)]` for every lesson row in a wrong kind (as `verify.deployment`'s venue warning finds them), rooms from `fixes.room_options(..., state "ok" only)` in its order.
  - `half`: no change; Needs you with the warning's own text (unless `room_options` offers one that settles it, then as venue).
  - `clash`, `rule`: `([], None)` (the search moves lessons; no direct change).
  - Any deployment target whose key is a band group (rows have a `block`, or the planned row does): for `missing`/`periods`/`extra` return `([], BAND)`; `teachers`/`venue` are handled as above. A teacher in `new` who is not in `spec["teachers"]`: the judge's own sentence (from `fixes.apply_one`'s ValueError: "{name} is not on the setup's list of teachers.") as the Needs-you sentence.

- [ ] **Step 1: Write the failing tests** (one per case, each with the exact candidate it expects)
  - `test_one_teacher_for_another_is_one_teacher_fix` (Review Focus 3 partner): `direct(...)` for the teachers warning returns one candidate `[dict(kind="teacher", key=…, teachers=[…])]` with the new teacher in place of the old and the rest kept.
  - `test_two_teachers_changing_needs_you`: two names change → `NOT_ONE`.
  - `test_split_lessons_need_you`: a key whose rows have different teachers → `SPLIT`.
  - `test_a_teacher_not_on_the_list_needs_you` (Review Focus 3): the step 5 teacher's name is not in the setup's teachers → the sentence containing "is not on the setup's list of teachers".
  - `test_a_missing_lesson_is_added`, `test_a_surplus_lesson_is_deleted_from_the_fullest_day`, `test_a_wrong_room_kind_is_a_room_fix`.
  - `test_a_bands_periods_need_you`: a banded key with fewer periods → `([], BAND)`; its teacher change is still one teacher fix.

- [ ] **Step 2: Run to see them fail** — AttributeError: direct.

- [ ] **Step 3: Implement**

- [ ] **Step 4: Run** `.venv/bin/python tests/test_refit.py` — Expected: "N checks passed".

- [ ] **Step 5: Commit** `git add refit.py tests/test_refit.py && git commit -m "Re-fit: the direct change for each kind of target"`

### Task 3: Where a lesson may go

**Files:**
- Modify: `refit.py`
- Test: `tests/test_refit.py`

**Interfaces:**
- Consumes: `fixes.slots`, `fixes._ctx`, `fixes._block`, `fixes._rows`, `fixes.judge`, `verify.rules`.
- Produces (pure; never mutate the shared `m`):
  - `refit.barred(m, spec, days, lesson_id, d, pool) -> bool` — True when, with only that lesson's rows on the timetable (everything else off), every period the lesson fits on day `d` breaks a Must rule (`verify.rules(dict(m, lessons=<its rows moved to (d, p)>), spec)[0]` with a Must-strength warning, or `lesson_time` refuses it). Cached by `(lesson_id, d)` in the caller's memo.
  - `refit.day_moves(m, spec, days, lesson_id, ctx, memo, moved: set, limit: int = CAND_SLOTS) -> list[dict]` — the moves and swaps of one lesson the rules allow now, best first: same-day slots (`fixes.slots(extras=False)`, states "ok", and "prefer" only when every prefer reason ends " over the allowance.") by distance in periods from where it is; and only when the lesson's own day is barred (`barred(...)` of its day), slots of other days (nearest day, then nearest period), each item marked `other=True`. Each item `dict(fix=<move or swap fix>, other=bool, dist=int)`; a swap (`s["swap"]`) only with a lesson that is not a band, not in `moved`, and on the same day (never across days). `[]` for a band lesson, for a lesson in `moved`, and for a lesson in the pool.
  - Same-day first, then other days, inside the list; at most `limit` items.

- [ ] **Step 1: Write the failing tests**
  - `test_a_lesson_keeps_its_day`: its same-day "ok" slots are offered nearest first; no other day while `barred` is False.
  - `test_barred_day_opens_other_days`: with a Must rule "Teacher X not available" for the lesson's whole day (setup), `barred(...)` is True and `day_moves` returns other-day items with `other=True`; with the rule for only one period, `barred` is False and no other-day items.
  - `test_a_band_lesson_never_moves` (a lesson of a band): `day_moves` is `[]`.
  - `test_a_swap_never_crosses_days_and_never_touches_a_moved_lesson`.
  - `test_day_moves_does_not_mutate_the_model`: deep-copy of `m["lessons"]` before and after is equal.

- [ ] **Step 2: Run to see them fail** — AttributeError: barred.

- [ ] **Step 3: Implement**

- [ ] **Step 4: Run** `.venv/bin/python tests/test_refit.py` — Expected: "N checks passed".

- [ ] **Step 5: Commit** `git add refit.py tests/test_refit.py && git commit -m "Re-fit: where a lesson may go, bands and the day pattern kept"`

### Task 4: The search for one target

**Files:**
- Modify: `refit.py`
- Test: `tests/test_refit.py`

**Interfaces:**
- Consumes: `refit.direct`, `refit.day_moves`, `helper.chain`, `helper.settles`, `helper.involved`, `helper._before`, `fixes.Busy` (`blocker`).
- Produces:
  - `MAX_MOVES = 3`, `MAX_NODES = 250`, `CAND_LESSONS = 4`, `CAND_SLOTS = 8` (module constants, changeable by tests).
  - `refit.solve(m, spec, days, target, pool, moved: set, deadline: float, stats: dict | None = None) -> dict | None` — the best list of fixes for one target on the timetable `m` as it is now (the caller has already applied the earlier targets' fixes to `m`): `dict(fixes=[...], moved=set(ids moved in this list), other=int (count of moves to another day), typed=set(n, …), why=…)`, or None when there is none within the limits. `needs` reason: when None, `stats["reason"]` is the best sentence seen (the judge's own, else NO_FIT).
    - Nodes are lists of fixes = `moves + direct` where `direct` is one of `refit.direct(...)`'s candidates (deployment targets) or `[]` (clash/rule targets; then the moves alone must settle it). `m` is the base; each node is judged with `helper.chain(m, spec, days, fixes, ctx, memo)`; a node is a solution when the chain's state is "ok" (or accepted "prefer") and `helper.settles(m, spec, days, target["w"], chain["lessons"], memo_before)`.
    - Search in order of the number of moves (0, 1, 2, 3): all nodes with k moves are judged before k + 1, and the first k at which any solution exists decides the answer, ranked by (other-day moves, then typed rules touched, then total distance, then fewest Prefer new, then the fixes' repr).
    - Expanding a node that is not a solution: when the chain stopped at a refused step, the lessons to move are the ones in the way of that step (`fixes.Busy(m_at_prefix).blocker(...)` for the move/add/teacher it concerns, as `helper.pairs` finds them) and, for a lesson a rule or clash is about, the ids from `helper.involved(m_at_prefix, target["w"])`; at most `CAND_LESSONS` of them, none a band, none in `moved`. Each gives its `day_moves(...)` (at most `CAND_SLOTS`), each tried as the new first move of the list; a list whose last fix is a move/swap that already exists is not tried twice (seen set by `repr`).
    - Stops when `stats["nodes"]` reaches `MAX_NODES` or `time.monotonic() > deadline` (then `stats["reason"] = LATE` if no solution).
  - `stats`: `dict(nodes=int, reason=str, late=bool)` filled in, for the notes and tests.

- [ ] **Step 1: Write the failing tests** (each builds a small timetable with the sample's setup plus a made-up draft, and says which one change is expected)
  - `test_a_teacher_change_that_just_fits`: teachers target with the new teacher free → one fix, no moves.
  - `test_the_blocker_is_moved_on_its_own_day`: the new teacher teaches another lesson then; the answer moves that lesson on its own day (or swaps it) and changes the teacher, 2 steps, `moved` is the lesson's id, `other == 0`.
  - `test_the_first_depth_wins`: when one move and two moves both settle it, the one-move answer is returned; among equals the ranking above decides (assert the ranked one).
  - `test_a_band_is_never_moved` (Review Focus 2): the blocker is a band → None and `stats["reason"]` is the judge's sentence or `NO_FIT`; nothing of `m` is changed.
  - `test_a_lesson_moved_by_an_earlier_target_is_left_alone` (Review Focus 2): the blocker is in `moved` → not moved.
  - `test_a_teacher_away_all_day_moves_to_another_day`: a Must "not available" rule for that day → a move to another day with `other == 1`; `test_a_full_day_never_moves_to_another_day` (only full) → Needs you (None).
  - `test_adding_a_period_takes_a_free_slot`: a missing target → one add; the deadline in the past → `stats["late"]` and None.
  - `test_never_more_prefer`: with an accepted "prefer" that adds a Prefer rule, None (only the teacher-allowance prefer is accepted).

- [ ] **Step 2: Run to see them fail** — AttributeError: solve.

- [ ] **Step 3: Implement**

- [ ] **Step 4: Run** `.venv/bin/python tests/test_refit.py` — Expected: "N checks passed".

- [ ] **Step 5: Commit** `git add refit.py tests/test_refit.py && git commit -m "Re-fit: the search for one target"`

### Task 5: The plan

**Files:**
- Modify: `refit.py`
- Test: `tests/test_refit.py`

**Interfaces:**
- Consumes: Tasks 1 to 4; `verify.typed_again`, `verify.typed_rules`, `verify.in_scope`, `helper._apply`, `helper.say`, `draft.counts` (for the before and after numbers: `draft.counts(m, rec, fx, decisions)`).
- Produces: `refit.plan(m, rec, decisions, warnings, progress=lambda done, total: None, budget: float = BUDGET_S, now=time.monotonic) -> dict`:
  - Works target by target: after each solved target, its fixes are applied to a working copy of the lessons, and the model is rebuilt from that copy (`dict(m, lessons=…)`, the pool and caches as `helper` uses them) for the next; `moved` grows with `solution["moved"]`.
  - `dict(stamp=<draft.stamp at start>, groups=[dict(text=target text, kind, steps=[dict(fix, text (helper.say), why, tags=[…])], needs=None)] for solved targets, fixes=[every fix in order], needs=[dict(text, why)] for unsolved, totals=dict(changes=len(fixes), moved=<distinct lesson ids whose (d,p) changed>, another_day=int, critical=[before, after], warnings=[before, after] (after excludes typed `:again` warnings the plan raised), typed=sorted set of typed rule numbers touched), late=bool, seconds=float)`.
  - `why` per step: the plain reason — a blocker move: "{who} teaches {what} then" (or "{class} is busy then", room busy), an add: "it was not on the timetable", a delete: "step 3 plans {n} periods", a teacher change: "step 5 now gives it to {name}", a rule move: "the rule needs it there", a room change: "step 3 asks for {kind}", derived from the warning and the blockers the search used (pass the reasons out of `solve` as `why`).
  - `tags`: `another day` for steps `other`; `check T{n} again` for every typed rule whose `verify.typed_again(model_after, spec, touched, was)` warns because of that step (rules with a Met/Partly report line only, as the function already does).
  - Totals before: `draft.counts(m, rec, decisions=decisions)`; after: the model after the plan with fx (touched and was of the whole list from `helper._apply`), counting the open warnings that are not `typed:{n}:again` ones; if `critical` after is more than before, the last solved target that raised it is dropped to `needs` with `NO_FIT` and totals recomputed until it is not (a safety net; with correct judging it never happens).
  - `progress(done, total)` is called after each target (total = number of targets).

- [ ] **Step 1: Write the failing tests**
  - `test_a_plan_groups_changes_by_target`: two targets (a teacher change and a missing period) → two groups with steps, `fixes` in order, `totals["changes"] == len(fixes)`; `helper.chain(m, spec, days, plan["fixes"])["state"] in ("ok", "prefer")`, and `helper.settles` is true for both targets' warnings on the final lessons.
  - `test_targets_build_on_each_other`: the second target's fixes are judged on the timetable the first left (a lesson the first moved is not proposed again; `moved` respected).
  - `test_the_time_limit_leaves_the_rest_in_needs_you` (Review Focus 4): `budget=0` → at least one target in `needs` with `why` LATE, `late` True, and any group found before is still listed.
  - `test_typed_rules_are_flagged`: a typed rule reported Met whose scope covers a moved lesson → that step's tags contain `check T{n} again` and totals typed contains n.
  - `test_counts_before_and_after`: totals match `draft.counts` on the before model and on the hypothetical after.
  - `test_the_plan_changes_nothing`: the draft's decisions.json and meta.json and the cached model are the same after `plan()` (deep equality).

- [ ] **Step 2: Run to see them fail** — AttributeError: plan.

- [ ] **Step 3: Implement**

- [ ] **Step 4: Run** `.venv/bin/python tests/test_refit.py` — Expected: "N checks passed".

- [ ] **Step 5: Commit** `git add refit.py tests/test_refit.py && git commit -m "Re-fit: the plan, its groups, totals and flags"`

### Task 6: The job, the apply and the preview

**Files:**
- Modify: `app.py`, `draft.py`
- Test: `tests/test_refit.py`

**Interfaces:**
- Consumes: `refit.plan`, `refit.needed`, `refit.targets`, `versions.keep`, `draft.model_now`, `draft.stamp`, `draft._fixes_of`, `helper.chain`, `versions.identity` (nothing new), `history` through `_draft_entry`.
- Produces:
  - `draft.MAX_STEPS = 200`; `draft._fixes_of(moves, m, spec, days, limit=2)` raises "Send up to {limit} fixes." when longer; `draft.preview(moves, many=False)`: with `many` the list may be up to MAX_STEPS, judged with `helper.chain`; the answer shape is as today (`classes`, `gone`, `texts`, `state`, `why`), a refused list showing the timetable up to the refused step.
  - `draft.refit_apply(steps: list, stamp: str, keep_name: str, by: str, fx_why: dict | None = None) -> dict(info, kept, texts)` — under `_lock`: `m, rec, fx = _now()`; `_moved(stamp, rec)` (raises MOVED); `fl = _fixes_of(steps, m, spec, days, limit=MAX_STEPS)`; `c = helper.chain(m, spec, days, fl)`; state "no"/"na" → ValueError(c["why"]) and nothing written; otherwise `kept = versions.keep("refit", by, name=keep_name)` (None when the draft is already kept, that is fine) then one batch: every fix with `at=now`, `text=c["texts"][i]`, the same `batch` id, appended to `meta.json`'s fixes in one write; then the "met" answers for the touched typed rules' keys (`typed:{n}:again`, and `#k` variants) are removed from `decisions.json` where the answer is "met" (the touched numbers come from `verify.typed_again` run on the model after with the chain's touched and was). Returns `draft.info()`, `kept`, the texts.
  - In `app.py` a job registry: `REFIT = dict(id, stamp, state="idle"|"running"|"done"|"failed", done, total, plan, error, started)` with a lock; one job at a time.
    - `POST /api/draft/refit` → 400 `{"error": "Nothing to re-fit: the timetable fits the setup."}` when `refit.needed(info)` is false (and when there is no draft/setup the usual sentences); 409 `{"error": "A re-fit is already running."}` while one runs (started within the last 10 minutes); else starts a daemon thread that computes `m, rec, _ = draft.model_now()`, the warnings and decisions as `draft.info()` gives them, and `refit.plan(...)`, writing `done`/`total` as it goes; answers `{"id": …, "started": true}`.
    - `GET /api/draft/refit` → `{state, done, total, plan (with its fixes only as text lists for the page, not the raw fixes), error, id, stamp}` or `{state: "idle"}`; `plan` carries `groups`, `needs`, `totals`, `late`, `seconds`, `id`.
    - `GET /api/draft/refit/preview?id=` → `draft.preview(plan["fixes"], many=True)` for the stored plan (404 "That re-fit list is gone. Run Re-fit again." when the id is not the current done one).
    - `POST /api/draft/refit/apply` body `{id}` → the stored plan's fixes with its stamp through `draft.refit_apply` (name "Before re-fit, {d Mon h.mm am/pm}" from store.now, by `by()["as"]`); a ValueError with `MOVED` or a stale plan answers 400 with the sentence "The draft changed since this list was made. Run Re-fit again."; success answers the draft info plus `kept` and clears the job, with one `_draft_entry("refit", "Re-fit: {changes} changes ({moved} lessons moved, {other} to another day, {t} typed rules to check again)")`.
  - Existing step 8 routes keep working while a job runs (the job reads only).

- [ ] **Step 1: Write the failing tests**
  - `test_refit_needs_the_committee`: the four routes are 401 without sign-in.
  - `test_nothing_to_refit_is_refused` (Review Focus 5): a clean draft → 400 with the sentence; no job starts (`GET` says idle).
  - `test_a_job_runs_and_is_polled`: with a teachers difference, POST → 200 id; poll GET until `state == "done"`; `plan["totals"]["changes"] >= 1`; a second POST while "running" (monkeypatch the plan function to wait on an event) → 409.
  - `test_apply_changes_exactly_the_plan`: after done, POST apply → 200 with `kept["kind"] == "refit"` and `name` starting "Before re-fit"; the draft's fixes end with the plan's N fixes sharing one `batch`; `GET /api/draft` has no deployment warning for that target any more; the history's newest entry text matches the format; Undo once (`POST /api/draft/undo`) brings back the fixes count from before.
  - `test_apply_refuses_a_stale_plan` (Review Focus 1): change the draft (any fix) after the plan → apply 400 with the sentence "The draft changed since this list was made. Run Re-fit again."; nothing written, no version kept (version count unchanged).
  - `test_apply_refuses_a_step_that_no_longer_fits`: make the draft unsafe for one step (a clash made by another fix before re-judging; without changing the stamp — set the plan's stamp to the current one) → 400 with the judge's sentence; the draft unchanged and no version kept.
  - `test_typed_rules_lose_their_met_answer`: a typed rule with a "met" answer covered by a plan step → after apply its `typed:{n}:again` answer is gone from decisions.json; an unrelated "met" answer stays.
  - `test_preview_of_a_plan`: GET preview shows the classes the plan touches with their changed lessons, writes nothing (meta.json unchanged).

- [ ] **Step 2: Run to see them fail** — 404 from Flask for the unknown routes.

- [ ] **Step 3: Implement**

- [ ] **Step 4: Run the tests** `.venv/bin/python tests/test_refit.py && .venv/bin/python tests/test_versions.py && .venv/bin/python tests/test_board.py && .venv/bin/python tests/test_routes.py` (and add the new endpoints to the GUARDS map in tests/test_routes.py, `("committee",)`) — Expected: all pass.

- [ ] **Step 5: Commit** `git add app.py draft.py refit.py tests/test_refit.py tests/test_routes.py && git commit -m "Re-fit: the background job, apply, preview and undo"`

### Task 7: The Re-fit window on step 8

**Files:**
- Modify: `static/app.js`, `static/style.css`, `README.md`
- Test: browser check (controller, after the review)

**Interfaces:**
- Consumes: the Task 6 routes; `draft.info()`'s `warnings` (the button's check is `warnings.some(w => !w.decision && (w.kind === "deployment" || w.kind === "clash" || (w.kind === "rule" && w.strength === "Must")))` on the page, which must match `refit.needed`).
- Produces, as screen 3 of the mockups:
  - A **Re-fit to the setup** button in the upload card head beside **Versions**, greyed with the title "Nothing to re-fit: the timetable fits the setup." when nothing needs it; the same action as a link on the configuration line ("Made from configuration …") when it is the older one.
  - A window like the Versions one (same overlay, focus, Esc/backdrop/Close rules; its own state object `RF`): starting shows "Starting…"; while running "Looking at {done} of {total}…" polled every 1.5 s (stops when closed? the job keeps running and reopening continues to poll); when done: the header "What doesn’t fit the setup now", the lead's rules line ("Bands stay where they are", "Lessons stay on their day unless a change forces another", "Fewest lessons moved", "No Must rule broken", "Typed rules: moves allowed, flagged"), each group (its text, its steps with number, sentence, grey reason and tags as chips), the "Needs you" box (each `needs` item), the totals ("{M} lessons move, {K} to another day · Critical {a} → {b} · Warnings {a} → {b} · {t} typed rules to check again"), and "The app keeps a version “Before re-fit …” first and applies all {N} changes as one; Undo takes the whole re-fit back." with **Preview on the board** (opens under the list the class weeks from the preview route with the changed lessons outlined, as today's Preview draws them, `fxSmallHTML` per class) and **Apply all {N} changes** (disabled while running, with N from the totals), and **Cancel**.
  - After Apply: the window closes, the draft is redrawn as an upload does (`S.draft`, board, panel), a toast "Re-fit applied: {N} changes. The draft before is kept as version “…”."; the refused (400) sentence is shown in the window, which then offers **Run Re-fit again**.
  - Nothing runs while the window is closed except a job already started; opening again shows its state.
- Copy word for word: "Re-fit to the setup", "What doesn’t fit the setup now", "Needs you", "Preview on the board", "Apply all {N} changes", "Run Re-fit again", and the greyed title sentence.

- [ ] **Step 1: Implement** (escape every server value; the window's keys and focus as the Versions window; no request while nothing is open)
- [ ] **Step 2: Check** `node --check static/app.js` and `for f in tests/*.test.js; do node "$f" >/dev/null || echo FAIL $f; done` and `.venv/bin/python tests/smoke.py && .venv/bin/python tests/test_refit.py && .venv/bin/python tests/test_versions.py`
- [ ] **Step 3: Commit** `git add static/app.js static/style.css README.md && git commit -m "Step 8: the Re-fit window"` (README: a paragraph under Upload and edit: what Re-fit does, its rules, the list, Apply, Undo, the version kept, typed rules flagged.)

### Task 8: Real file, tuning and notes

**Files:**
- Create: `docs/superpowers/plans/2026-11-22-refit-stage-2-notes.md`
- Modify: `refit.py` constants if needed

- [ ] **Step 1: The school's real file, counts and timings only** (scratch `DATA_DIR`, every copy deleted; never print names; as the saved-versions notes): with the newest real setup and timetable, make the kinds of differences a small change makes (one teacher changed, one period more and one fewer on one subject, a teacher unavailable one day, a Must rule added), and measure: number of targets, seconds per `plan()`, nodes judged per target, how many solved / needs you, the longest chain, and that the plan's `settles` is true for each solved target. Tune `MAX_NODES`, `CAND_*` and `BUDGET_S` so a typical small change finishes well under 30 s, and write the numbers.
- [ ] **Step 2: The notes file**: rulings while building, the numbers, what was not tried in a browser, deferred points, and what stage 3 could add (a "Try harder" solver option, placing lessons waiting in Not placed, band fix kinds).
- [ ] **Step 3: Run every suite** named in the saved-versions plan's Task 8 plus `tests/test_refit.py`, each on its own; `node --check` on every static script; every `node tests/*.test.js`.
- [ ] **Step 4: Commit** `git add docs/superpowers/plans/2026-11-22-refit-stage-2-notes.md refit.py && git commit -m "Re-fit: real-file tuning and notes"`

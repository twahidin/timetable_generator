# Wizard stage 2: decisions made while building, and what was left

From the build ledger of `2026-11-09-wizard-stage-2-working-together.md`. Each task had its own review; the whole branch had a final review and one fix wave.

## Rulings (decisions made where the plan was silent or wrong)

- T4 -> T6: T4 removes Start's "Open the school's saved setup" and "Continue in this browser" and the old init, but begin/adopt/importX/loadJson stay until T6. Ruling: in T4 those four send PUT /api/setup {spec, why} at once with no question and then load the server's copy; T6 adds the question and the practice copy — keeps the page usable between the two tasks — cost if wrong: none after T6.
- T4 -> T5: between them Undo still restores whole snapshots, which can undo other people's changes. Ruling: accepted for one task; T4's checks do not use Undo; T5 replaces it — cost if wrong: none after T5.
- Ruling: browser checks in Tasks 4-7 — implementers run them if they have the Browser pane tools, on launch config "timetable-scratch" (port 8003, scratch DATA_DIR, test HEADS_CODE); any they cannot run they list as NOT RUN and the controller runs them before the task is marked complete — cost if wrong: a slower loop.
- Task 3: Ruling: heads can read the unpublished student list through GET /api/setup (the brief gives heads that route; teachers already see student names once published) — accepted for this stage and reported to the committee at the end; stripping students for heads would need the change stream filtered too — cost if wrong: a follow-up task to filter students out of what heads receive.
- Task 4: Ruling: the server applied a POST's ops even when the setup had been replaced since `since` (a gap in the plan's Task 2; Review Focus 4 and Task 6 depend on it). apply_changes gains `since` and raises store.Replaced before applying; the POST answers the reset. Added to Task 4's fix round 1, with the implementer allowed to edit store.py, app.py and tests/smoke.py for it — cost if wrong: one exception and one test to remove.
- Task 6: Ruling: heads can open a practice copy too — the brief gives the sample buttons no role limit and the server lets a head fetch samples; only whole-setup actions are committee-only — cost if wrong: hide two buttons again.
- Task 6: Ruling: the reviewer's Minor "S.practice set before useKind succeeds" is raised to Important and enters the loop — if the meta fetch fails the page sits in practice on the school's setup and edits are neither sent nor kept — cost if wrong: one extra fix in the round.
- Task 7: Ruling: Start stays usable for a head (the brief says every step except 4 and 5 is read-only) — Start holds no setup fields and its sample buttons are how a head opens a practice copy, per the Task 6 ruling; its whole-setup actions are already committee-only — cost if wrong: one condition to tighten.
- Final: Ruling: a head's refused operations are filtered, not the whole request refused (the plan and Task 3's brief said 403 and nothing applied) — the spec's anti-goal is that nobody's work is lost silently, and an hour of offline edits dropped for one stale operation breaks it — the server applies what is allowed and reports what was not; the 403 stays only as a fallback — cost if wrong: Task 3's tests and the 403 path are easy to restore.
- Final: Ruling: the client id is made fresh on every page load instead of kept in sessionStorage (the plan said sessionStorage) — a duplicated tab otherwise hides each tab's changes from the other — cost: after a reload the header counts the old id as "1 other here" for up to 20 seconds.
- Final: Ruling: the reviewer's Minor 5 (the committee's render of step 4 writes default roles into S.spec) is raised to Important and fixed — two committee members opening step 4 on a blank-started setup double the Roles list, and an Undo can delete the roles for everyone — cost if wrong: one more item in the fix wave.
- Final: Ruling: the reviewer's "declined to judge" lines stand as designed and are reported to the committee: last-writer-wins by arrival time, Undo overwriting someone's newer edit to the same field, a typed field landing on a restored setup by row id, a restore point per teacher delete using up the 48 copies, the header's "kept in this browser" when storage is unavailable, a head forging another client id — each follows from the plan's design or needs a product decision — cost if wrong: a follow-up task each.
- Final: parked — a head's refused operation gets no message when the POST's reply is a reset (the page reads `refused` only on the normal reply) — Ruling: real but rare (a head who was behind, on the first send after a redeploy or after 400 other changes); there is no second fix wave, so it is deferred and reported to the committee — cost if wrong: a head loses one refused edit without being told in that case.
- Final: parked — a default role deleted by one committee member can come back when another who opened the same roleless setup sends their defaults late, and deleting every role brings all ten back on the next open — Ruling: accepted; the second matches what the page did before, the first needs two committee members in the first minutes of a blank setup — cost if wrong: a role someone deleted reappears and is deleted again.
- Ruling (before Task 4): Task 4's new localStorage format would overwrite an old-format entry (a whole spec with unsaved changes) before Task 6's rollout question can ask about it. Task 4 moves any old-format entry (has `spec`, no `sync`) to key `ttsetup.v1.old` untouched; Task 6 asks about that key — cost if wrong: one key name to change.
- Ruling (before Task 7): a real head session cannot be opened in the browser pane by a subagent (reading the test HEADS_CODE from launch.json is refused by the permission classifier, and the controller will not route around a refusal). Task 7's browser checks run with the page's role set to head against a committee session; the checks that need the server to treat the session as a head (the 403 and reload, the head's change showing in a committee tab) are listed NOT RUN and reported to the committee, with tests/smoke.py's head client as the server-side evidence — cost if wrong: a page bug that only shows with a real head session reaches the committee's own try-out.

## Deferred (found in review, not fixed)

- Task 1: minor (deferred): _canon writes 1.0 in Python where JS writes 1, so a float merge item could be appended twice.
- Task 1: minor (deferred): JS uses plain {} maps keyed by user strings (school/day/top keys): __proto__ or constructor would misbehave.
- Task 1: minor (deferred): no test for merge removes, students.groups, diff of top keys, a day op that empties a level; Python and JS never run against each other on one input.
- Task 1: minor (deferred): _STR_ARGS defined below apply in sync.py; newId has a slight modulo bias; sort order differs only outside the BMP.
- Task 2: minor (deferred): a change made only of skipped ops still bumps the version, writes setup.json and logs an empty patch.
- Task 2: minor (deferred): apply_changes mutates the cached spec in place; if sync.apply raised part-way the cache would be half-changed with no version bump (apply to a copy and swap).
- Task 2: minor (deferred): no automated test for /api/setup/restore (ok and 404), the 409 with no setup, the restore point on a teacher delete or >20 deletes, or a reset after the 400-entry log overflows.
- Task 2: minor (deferred): a GET /api/setup/changes with no client is counted in presence as ""; load_setup deep-copies the spec when only saved_at is needed; unused `code` in one test.
- Task 3: minor (deferred): sync.py head_may condition `len(op) > 2 and op[2:3]` is redundant; split set and del.
- Task 3: minor (deferred): a head on /timetable gets the teacher view with no link back to the editor.
- Task 3: minor (deferred): test_the_head_check_runs_on_the_setup_held_under_the_lock depends on a teacher created by the test before it.
- Task 4: minor (deferred): rebase reads SYNC.base after the await; if begin/adopt replaced the base while an idle GET was in flight, the reply sets SYNC.v back and can drop edits made in that window. Capture the base with `sent` and discard a reply for another base.
- Task 4: minor (deferred): after a GET-side replaced reset, edits made while the GET was in flight are dropped with no message (the toast is gated on ops.length).
- Task 4: minor (deferred): a 409 (no setup on the server) makes a head's page retry every 5 s under an "Offline" label.
- Task 4: minor (deferred): the focus-out redraw of a held change can swallow the click that caused it and drops focus from the next box.
- Task 4: minor (deferred): a duplicated tab copies sessionStorage, so both tabs share a client id and never see each other's changes; two tabs with unsent changes share one localStorage entry.
- Task 4: minor (deferred): the 403 path sets SYNC.base from S.spec after ensureDays (undocumented drift) and discards the whole batch.
- Task 4: minor (deferred): a POST to /api/setup/changes without `since` is read as since=0 and refused as older than a past replacement (the browser always sends it).
- Task 5: minor (deferred): an Undo entry can be empty when only `_` keys changed (Undo then appears to do nothing); skip the push when both lists are empty.
- Task 5: minor (deferred): no automated test of the undo entries (browser-only evidence).
- Task 6: minor (deferred): openPage's `await poll()` returns at once when a poll is in flight and swallows errors, so a committee member whose /api/status fails on first load sees the head's "not started yet" message.
- Task 6: minor (deferred): holdSync has no time limit: a hung send makes a whole-setup action wait silently.
- Task 6: minor (deferred): no automated check that a practice copy never writes to the server or storage.
- Task 6: minor (deferred): in practice(), a throw after S.practice = true would skip render() and syncNow() (not reachable in practice today).
- Task 7: minor (deferred): for a head, ensureDays/ensureRecessRows run on load and would emit day/school ops (a 403) if the server's setup were ever not normalised.
- Task 7: minor (deferred): a click on a Things-to-fix link to a hidden step still resets the teaching-group and teacher filters; a head's list still shows students-step items that do nothing when clicked.
- Task 7: minor (deferred): the provisional/practice expressions are repeated in addRow, helper, locked, headLocks and bulkTeachers.
- Task 7: minor (deferred): if /api/status fails at startup a head briefly sees an editable page (the server still refuses the changes).
- Task 8: minor (deferred): DEPLOY.md says every open browser reloads the setup after a redeploy; only browsers that are behind do (the rest carry on). Reword.
- Task 8: minor (deferred): README and DEPLOY.md omit that a restore point is also taken before a change that deletes a teacher or more than 20 rows; DEPLOY.md's "about 5 MB" volume figure was not re-measured for 48 copies; the HEADS_CODE row omits that a head can remove a provisional teacher.
- Final: minor (deferred): a POST whose response is lost is retried and re-applied 5 s later, and can overwrite a newer edit to the same field (needs a batch id the server remembers).
- Final: minor (deferred): unsent changes in localStorage belong to the browser, not the person: on a shared computer they are sent under the next sign-in.
- Final: minor (deferred): store.apply_changes's `check` parameter and the Refused -> 403 path have no production caller now (kept as a fallback).
- Final: minor (deferred): if /api/status fails when the committee opens a roleless setup, the default roles are not written on that open and the Roles table is empty until the next open.

## Not exercised in a real browser

- A real department-head sign-in. The head's page was checked with the role set from the console against a committee session; the server side is covered by the head client in `tests/smoke.py`. Worth one pass by hand: sign in with the heads' code, add a teacher, change who can teach what, and have the committee confirm that teacher meanwhile.
- A real duplicated browser tab (the fix is a fresh client id on every page load).
- Start when the school has no setup yet, for the committee and for a head.

# Accounts stage 2: Put back, "Since you last signed in", each person's history, Download

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a committee member put back one change (setup or accounts), let heads and everyone who can change something see the history that is theirs, show "Since you last signed in" on the home page, and download the history as Excel.

**Architecture:** The history stays the month JSONL files of stage 1 (`history.py`). A new pure module `putback.py` decides whether a recorded change can be put back (nothing later touched the same thing) and turns it into the operations that undo it. Setup put backs go through `store.apply_changes` under the store's lock with a check of the current values; account put backs go through `people.update` with the admin page's own checks. Who sees which entries is one predicate built from the rights (`app.history_scope`), used by the page, the API, the download and the home summary.

**Tech Stack:** Flask 3.0.3, one gunicorn worker, plain JS pages, openpyxl 3.1.5 (already in requirements), plain-assert test scripts.

**Spec:** `docs/superpowers/specs/2026-11-21-accounts-and-history-design.md` (sections "The history", "Stages" item 2) and its mockups `docs/superpowers/specs/2026-11-21-accounts-and-history-mockups.html` (tab 4). Stage 1 notes: `docs/superpowers/plans/2026-11-21-accounts-stage-1-notes.md` ("For stage 2", "Known limits").

## Global Constraints

- The repo is public: the school is only ever "CTSS"; tests, samples and docs use made-up names only.
- Never print, log, commit or record in the history a password, a one-time password, a personal code, a shared code, `SECRET_KEY` or `ADMIN_RECOVERY_CODE`. Tests make random values with `secrets.token_hex`.
- No model call anywhere. Tests set `AI_API_KEY=""`.
- Tests are plain-assert scripts run as `.venv/bin/python tests/<name>.py`, `DATA_DIR` a fresh temp folder set before `import app`. `.venv` is a symlink to `../timetable_generator/.venv`.
- No new dependency. Files written atomically with `store.write_json`; the history only appended by `history.add`/`add_many`.
- Rights are read from the records on every request and every route declares them with `@need(...)`; the page hides what a person may not do, but the server decides. `tests/test_routes.py` `GUARDS` pins every guarded endpoint: each new or changed route is listed there on purpose.
- Every change (POST) keeps the stage 1 same-origin check (`same_site_only`); nothing new is reachable by GET that changes data.
- School time is UTC+08:00 (`history.SCHOOL_TZ`), whatever the server's clock zone: every day filter and every time the server writes in words uses it. The browser formats the times it shows from `at`.
- `static/history.js` builds the page with `textContent` only, never `innerHTML` (every text in an entry is untrusted). In `static/*.js`, never put a `//` comment in the middle of a long line; use `/* */`.
- Copy is plain words in the app's style; texts in quotes in this plan are used verbatim.
- Builders and reviewers: NEVER run `git stash`, `git stash pop` or `git checkout -- <file>`. After each task, `git stash list` shows the same entries as before it.
- Commits end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Rulings in this plan (the design left these open; check them when reading)

- **P1 Put back works on one save.** The setup page sends what a person changes in quick succession as one save (one `batch`); a band rename is the band and all its lessons. Put back takes back the whole save, or nothing: "Put back" for one change, "Put back these 3 changes" for a save of three. An account change of several people is one entry and is put back as one (the design says so).
- **P2 Who puts back what.** The committee (signed in with a password, or the shared committee code) puts back any setup change; a head puts back only their own setup changes, and only what the head rules let them make now (the mockup: "They cannot put back someone else's change"); an admin puts back account changes. Nobody else sees the button.
- **P3 What cannot be put back.** Refused changes, sign-ins, the app's own follow-ups, step 8 and 9, relief, exams, whole-setup replacements (they show a link to their own page instead), a person added, a username, a password, a code. A put back is itself a change and can be put back.
- **P4 Who sees which history.** Committee with a password: everything (as stage 1). HOD/SH with a password: entries about their departments' rows, by anyone, and their own entries. Anyone else signed in by name who can change something (the setup, relief planning or settings, exams, admin): their own entries. Sign-ins: only the committee sees others'; everyone else sees their own.
- **P5 The summary counts the person's own changes** as "Your own changes", as the mockup's head example does. It counts changes only: no sign-ins, refusals or the app's follow-ups. Without a previous sign-in there is no summary.
- **P6 Download is the committee's** (the design), with the page's filters, up to 20000 entries.
- **P7 School time is fixed at UTC+08:00** rather than read from the server, which runs in UTC on Railway.
- **P8 The two-year keeping is already built** (stage 1: `history.prune`, test `prune_two_years`); this stage only says so on the page.
- **P9 Stage 1 is not deployed yet,** so entries may change shape (`after`, `level`, `at` in school time) without converting old files; entries without them still work or say why.

## Review Focus

- A head puts back their own change after its row moved to another department: refused by the head rules judged on the setup as it is now (Task 3 test `head_put_back_judged_on_the_setup_now`).
- Put back races a change from another tab: the current values are checked under the store's lock, so a change that lands first makes the put back refuse rather than overwrite it (Task 3 test `put_back_refuses_when_the_value_moved_under_it`).
- A teacher's name, a band name or a lesson text starting with `=`, `+`, `-` or `@` in the Excel download stays text, never a formula (Task 5 test `download_cells_are_never_formulas`).
- The server's clock zone differs from the school's: a day filter, the summary's "since" line and a "Can't put back" sentence all use school time (Task 1 test `days_are_school_days`, Task 2 test `sentences_use_school_time`, Task 7 test `summary_times_are_school_time`).
- Entries written before this stage (no `after`, no `level`) and lines a person hand-edited or cut short: Put back either works or says why, and the page never breaks (Task 2 test `old_entries_say_why`, Task 3 test `a_broken_line_is_skipped`).

---

### Task 1: Who sees which history

**Files:**
- Modify: `accounts/rights.py`, `history.py` (school time, `allow`, month skip), `app.py` (`RIGHTS`, `TILES`, `history_scope`, `/history`, `/api/history`)
- Test: `tests/test_accounts.py`, `tests/test_history.py`, `tests/test_routes.py`

**Interfaces:**
- Produces:
  - rights `"history.dept"` (HOD/SH signed in with a password) and `"history.own"` (a named person, not switched off, whose rights include any of `{"setup", "relief.plan", "relief.settings", "relief.save", "relief.team", "exams", "admin", "committee"}`); both in `app.RIGHTS`.
  - `history.SCHOOL_TZ = datetime.timezone(datetime.timedelta(hours=8))`; entries' `at` is written in it.
  - `history.day_start(text: str) -> float | None`: the timestamp of 00:00 school time on `YYYY-MM-DD`, None when unreadable.
  - `history.when_text(ts: float) -> str` → `"Tuesday 18 Nov, 4:12 pm"`; `history.short_when(ts: float) -> str` → `"19 Nov, 10:02 am"` (school time, 12-hour clock, no leading zero on the hour).
  - `history.read(..., allow=None)`: `allow(entry) -> bool`, applied after every other filter (also to sign-ins). With `since`, month files wholly before `since` (in school time) are not opened.
  - `app.history_scope() -> (scope, allow, depts)`: `("all", None, [])` with right `history`; `("dept", allow, depts)` with `history.dept` (allow: `who` is the person, or one of the entry's `depts` is one of the person's record `depts`); `("own", allow, [])` with `history.own` (allow: `who` is the person); `(None, None, [])` otherwise.
  - `GET /api/history` also takes `since` (seconds since 1970, a number) and answers `scope`, `download` (true with right `history`) and `depts` (for scope `dept`, the person's departments, else the school's as now).

- [ ] **Step 1: Write the failing tests**

`tests/test_accounts.py`, test `history_rights_by_group` (use the file's `person(group)` helper):
```python
hp = R.rights(person("hod"), "password"); assert "history.dept" in hp and "history.own" in hp and "history" not in hp
hc = R.rights(person("hod"), "code"); assert "history.own" in hc and "history.dept" not in hc   # relief settings is a change
assert not {"history", "history.dept", "history.own"} & R.rights(person("teacher"), "code")
assert not {"history", "history.dept", "history.own"} & R.rights(person("executive"), "code")
ex = dict(person("executive"), extras=dict(relief=False, exams="2999-12-31", admin=False))
assert "history.own" in R.rights(ex, "code")
assert {"history", "history.own"} <= R.rights(person("committee"), "password")
assert R.rights(dict(person("hod"), off=True), "password") == frozenset()
assert not {"history.dept", "history.own"} & (R.rights(None, "shared", "committee") | R.rights(None, "shared", "head"))
```

`tests/test_history.py` (sign a named person in as `tests/test_admin.py` `as_person` does: a record in `accounts/people.json` with group and depts, then `s["who"]`, `s["via"]`, `s["n"]`, `s["exp"]`):
- `a_head_sees_their_departments_and_their_own`: entries by "Ann" (Maths row), "Bob" (Science row), the head "Hana" (a row of no department), an account entry by "Ann", a sign-in by "Bob"; Hana (hod, depts ["Maths"], password) gets exactly the Maths entry and her own; `scope == "dept"`, `depts == ["Maths"]`, `download is False`.
- `own_scope_sees_only_own`: an executive with the Exams extra (code) gets only entries with `who` their name, sign-ins included only when `signins=1` and their own; `scope == "own"`.
- `no_history_right_is_401`: a teacher (code) gets 401 from `/api/history` and a redirect to the sign-in page from `/history`.
- `days_are_school_days`: entries with `ts` at 2026-11-18 23:30 and 2026-11-19 00:30 school time; `from=2026-11-19&to=2026-11-19` returns only the second, whatever `TZ` the process has (set `os.environ["TZ"] = "UTC"; time.tzset()` first).
- `since_param`: `since=<ts>` returns entries at or after it; `since=abc` is 400 `{"error": "Pick a time as a number of seconds."}`.
- `months_before_since_are_not_read`: three month files; reading with `since` in the newest month opens only that file (count calls of `history._lines`).
- `when_text_is_school_time`: `when_text` of 2026-11-18 08:12 UTC is `"Tuesday 18 Nov, 4:12 pm"`; `short_when` of 2026-11-19 02:02 UTC is `"19 Nov, 10:02 am"`.

`tests/test_routes.py`: `GUARDS["api_history"]` and `GUARDS["history_page"]` become `('history', 'history.dept', 'history.own')`.

- [ ] **Step 2: Run them and see them fail**

Run: `.venv/bin/python tests/test_accounts.py; .venv/bin/python tests/test_history.py; .venv/bin/python tests/test_routes.py`
Expected: FAIL on the new assertions.

- [ ] **Step 3: Implement**

`accounts/rights.py`: add the two rights as Interfaces says (work out `history.own` last, from the set already built). `history.py`: `SCHOOL_TZ`, `at` in it, `day_start`, `when_text`, `short_when`, `allow`, the month skip. `app.py`: `RIGHTS`, the History tile opens with any of the three rights, `history_scope`, both history routes `@need("history", "history.dept", "history.own")`, `_history_day` replaced by `history.day_start` (`to` is `day_start(to) + 86400 - 0.001`), `since`, the new reply keys.

- [ ] **Step 4: Run them and see them pass**

Run: the three files above, then `.venv/bin/python tests/test_signin.py; .venv/bin/python tests/test_admin.py`
Expected: every file prints its "… passed" line.

- [ ] **Step 5: Commit**

```bash
git add accounts/rights.py history.py app.py tests/test_accounts.py tests/test_history.py tests/test_routes.py
git commit -m "History: heads see their departments, everyone their own; school time; since"
```

---

### Task 2: The rules of Put back (`putback.py`)

**Files:**
- Create: `putback.py`
- Modify: `history.py` (a deleted row's `after`, a day entry's `level`, `find`)
- Test: `tests/test_putback.py` (new)

**Interfaces:**
- Consumes: `history.short_when` (Task 1).
- Produces:
  - `history.setup_entries`: a `del` entry also has `after`: the `_id` of the row before it in its list as it was, `""` when it was first. A `day` entry has `level` (`op[1]`).
  - `history.find(entry_id: str) -> dict | None`: the entry with that id (newest files first, stop once ids are older).
  - `putback.TOUCH_KINDS = {"setup", "app", "setup-replaced", "account"}`
  - `putback.PUTTABLE = {"group", "depts", "relief", "exams", "admin", "note", "off"}`
  - `putback.unit_of(e) -> str | None`: `"b:" + batch` for a kind-`setup` entry with a `batch`; `"a:" + id` for a kind-`account` entry with a non-empty `changes`; None for anything else.
  - `putback.gather(entry_id) -> (unit, unit_entries, newer) | None`: the unit's entries oldest first, and the entries of `TOUCH_KINDS` newer than its newest one, newest first. None when the id is not in the history or its entry has no unit.
  - `putback.why_not(unit_entries, newer, today=None) -> str | None`: None when it can be put back, else the sentence.
  - `putback.reverse(unit_entries) -> list`: the setup operations that undo the save, newest first.
  - `putback.changed_since(spec, unit_entries) -> str | None`: None when every row and field is still as the save left it (set/merge: the row is there and its field equals `now` by `sync._canon`; add: the row is there; del: it is not; school/day/top: the value equals `now`).
  - `putback.annotate(shown, newer_all, may) -> None`: for each entry of `shown` whose unit `may(unit_entries)` allows, sets `e["back"] = {"unit": u, "n": len(unit_entries), "ok": why is None, "why": why}`; `newer_all` holds every `TOUCH_KINDS` entry from the oldest shown one on, newest first.

What touches what (a later entry blocks a put back when it touches what the put back needs; entries of the same unit, and the app's entries with `follows` equal to its batch, never block it):
- set or merge on a row field: touches field `(section, row, field)` and row `(section, row)`; its put back needs the field untouched and the row neither added nor deleted again.
- add or del of a row: touches the row; needs the row untouched.
- school, day or top: touches `(section, level, field)`; needs it untouched.
- setup-replaced: touches everything in the setup.
- account: touches `(name, field)` for each change; needs each of them untouched.

The sentences (`who` is the blocking entry's `as`, written "the app" when it is "The app"; times by `short_when`):
- `"Can't put back: {who} changed this again on {time}"`
- `"Already put back by {who} on {time}"` (the blocking entry's `putback` is this unit)
- `"Can't put back: the whole setup was replaced on {time}. Use a saved copy on the committee page."`
- `"Can't put back a new person, a username or a password here: change it on the admin page."` (an account unit with a change outside `PUTTABLE`)
- `"Can't put back: this change was recorded before Put back existed. Change it on its step."` (a day entry without `level`)
- `"Can't put back: the Exams and events date ({d}) has passed."` (`d` as `app._day` writes it: `"14 Nov 2027"`; an account change whose `was` is an exams date before `today`)
- `changed_since`: `"Can't put back: this was changed again since."`

Reversing (for `reverse`): set or merge → `["set", section, row, field, was]`; add → `["del", section, row]`; del → `["add", section, was, after]` (`after` missing: None, so the row goes last); school → `["school", field, was]`; day → `["day", level, field, was]`; top → `["top", field, was]`.

- [ ] **Step 1: Write the failing tests** in `tests/test_putback.py` (made-up setup from `ttgen.samples`, entries made through `history.setup_entries` so their shape is the real one):
- `each_op_reverses`: for a set, a merge, an add, a del (of the second row of `lessons`), a school, a day and a top op: apply the op to a copy, then `reverse` of its entries; the copy equals the original by `sync._canon` (the deleted row back in its place).
- `a_later_change_blocks_with_its_name`: entries by Ann then by Bob on the same row field; `why_not` for Ann's unit is `"Can't put back: Bob changed this again on " + short_when(bob_ts)`; Bob's unit is None.
- `another_field_does_not_block`: Bob changed another field of the row: Ann's is None.
- `a_deleted_row_blocks_a_field_change`: Bob deleted the row: Ann's set is blocked; an add is blocked by a later set on that row.
- `same_save_and_its_follow_ups_do_not_block`: a batch of two ops on the same row plus an app entry following it: None.
- `already_put_back`: a later entry with `putback` equal to the unit: `"Already put back by Cara on …"`.
- `replaced_blocks_everything_older`: a later setup-replaced entry: the replaced sentence; an account unit is not blocked by it.
- `account_rules`: a group change is blocked by a later change of the same person's group, not by another person's; a unit with an `added` change gives the admin-page sentence; an exams `was` of yesterday gives the date sentence.
- `old_entries_say_why`: a day entry without `level` gives the "before Put back existed" sentence; a del entry without `after` reverses to an add with `after` None.
- `changed_since_sees_the_current_setup`: after the save, a field changed without any entry: the sentence; untouched: None.
- `find_and_gather`: `history.find` returns the entry by id and None for an unknown id; `gather` of any entry of a batch returns the whole batch oldest first and the newer entries only.
- `sentences_use_school_time`: with `TZ=UTC`, the time in the blocking sentence is school time.
- `annotate_marks_each_unit`: two units shown, `may` allowing only one: only that unit's entries get `back`, with `n` its entry count.

- [ ] **Step 2: Run it and see it fail**

Run: `.venv/bin/python tests/test_putback.py`
Expected: FAIL (`No module named 'putback'`).

- [ ] **Step 3: Implement** `putback.py` and the `history.py` changes. `why_not` walks `newer` from the oldest end so it names the first later change.

- [ ] **Step 4: Run it and see it pass**

Run: `.venv/bin/python tests/test_putback.py; .venv/bin/python tests/test_history.py; .venv/bin/python tests/test_history_draft.py`
Expected: each prints its "… passed" line.

- [ ] **Step 5: Commit**

```bash
git add putback.py history.py tests/test_putback.py
git commit -m "Put back: which changes can be put back, and the operations that do it"
```

---

### Task 3: Putting back a setup change

**Files:**
- Modify: `store.py` (`apply_changes(..., tag=None)`), `app.py` (`POST /api/history/back`, `back` in `/api/history`)
- Test: `tests/test_putback.py` (second half: the app), `tests/test_routes.py`

**Interfaces:**
- Consumes: Task 2's `putback.*`; `sync.head_split`; `app.is_head`, `app.head_depts`, `app.who`, `app.by`.
- Produces:
  - `store.apply_changes(ops, client, check=None, since=None, filter=None, by=None, tag=None)`: `tag` (a dict) is added to each kind-`setup` entry of the applied operations (not to refused entries or the app's follow-ups).
  - `POST /api/history/back` with `{"id": entry id}`, endpoint `history_back`, `@need("setup", "admin")`. Answers: 200 `{"done": true, "text": "Put back."}`; 404 `{"error": "That entry is not in the history."}` (`history.find` is None); 409 `{"error": "This change cannot be put back here."}` (the entry has no unit); 403 `{"error": "Only the timetable committee can put back someone else's change."}` (a head and another person's change, or anyone not allowed that unit); 409 `{"error": <a why_not or changed_since sentence, or the head rules' sentence>}`.
  - A put back's entries carry `tag = {"putback": unit, "putback_of": <the unit's first entry's "as">, "putback_ts": <its ts>}`.
  - `GET /api/history` entries carry `back` (Task 2's `annotate`) for the units the viewer may put back: setup units with right `committee`, or a head's own (`who` is the head) setup units; account units with right `admin` (Task 4 makes them work).
  - `app.may_put_back(unit_entries) -> bool` (the rule above, for `annotate` and the route).

The route for a setup unit: `gather` the id; not allowed → 403; `why_not` → 409; then `store.apply_changes(putback.reverse(es), "history", check=check, by=by(), tag=tag)` where `check(spec, ops)` returns `putback.changed_since(spec, es)`, else for a head the sentence of the first refused operation of `sync.head_split(spec, ops, head_depts())` (its second item is `[(index, sentence)]`), else None; `store.Refused` → 409 with its sentence.

- [ ] **Step 1: Write the failing tests** (in `tests/test_putback.py`, after the pure tests; the app imported as `tests/test_history.py` does, people signed in as `tests/test_admin.py` `as_person` does; the setup from `ttgen.samples` saved with `store.replace_setup`):
- `committee_puts_back_a_save`: a set made through `POST /api/setup/changes`; `POST /api/history/back` with its entry id → 200; the field is as before; the new entry has `putback` the unit, `putback_of` the first person's name, `as` the committee member; `GET /api/setup/changes?since=<v before>&client=x` carries the undoing op (other tabs catch up).
- `a_save_of_three_goes_back_whole`: one POST with three ops; any one entry's id puts back all three; `back.n == 3` on each in `/api/history`.
- `put_back_twice_is_refused`: the second time 409 `"Already put back by …"`.
- `put_back_refuses_when_the_value_moved_under_it`: change the field again with `store.apply_changes` while `store._record` is replaced by `lambda es: None` (so no entry is written; put it back after), then put back the first change: the put back is 409 `"Can't put back: this was changed again since."` and the field keeps the newer value.
- `head_puts_back_only_their_own`: a head's own lesson change: 200; the committee's change shown to the head has no `back`; the POST for it is 403 with the sentence above.
- `head_put_back_judged_on_the_setup_now`: a head's own change, then the committee moves that lesson to another department's subject: the head's put back is 409 (the head rules' sentence or the "changed again" one) and nothing changes.
- `cannot_put_back_kinds`: a refused entry, a sign-in, a step 8 entry, a relief entry and a setup-replaced entry: no `back` in `/api/history`; the POST is 409 `"This change cannot be put back here."` for each of them, and 404 for an id that is not in the history.
- `a_broken_line_is_skipped`: a cut-short line in the month file: `/api/history` still answers 200 with `back` on the others.
- `teacher_cannot_post`: a teacher's code → 401.

`tests/test_routes.py`: add `"history_back": ('setup', 'admin')`.

- [ ] **Step 2: Run it and see it fail**

Run: `.venv/bin/python tests/test_putback.py`
Expected: FAIL on the first app test (404 from Flask for the route).

- [ ] **Step 3: Implement** `tag` in `store.apply_changes`, `may_put_back`, the route and `annotate` in `api_history` (one `history.read(since=<oldest shown ts>, kinds=putback.TOUCH_KINDS, limit=10**7)` per page of entries, only when the viewer may put back something).

- [ ] **Step 4: Run it and see it pass**

Run: `.venv/bin/python tests/test_putback.py; .venv/bin/python tests/test_routes.py; .venv/bin/python tests/test_history.py; .venv/bin/python tests/test_sync.py; .venv/bin/python tests/test_smoke.py`
Expected: each prints its "… passed" line.

- [ ] **Step 5: Commit**

```bash
git add store.py app.py tests/test_putback.py tests/test_routes.py
git commit -m "Put back a setup change from the history"
```

---

### Task 4: Putting back an account change

**Files:**
- Modify: `app.py` (the account branch of `history_back`)
- Test: `tests/test_admin.py`

**Interfaces:**
- Consumes: `putback.gather`, `putback.why_not`, `putback.PUTTABLE`; the admin page's `_change(d, name, item, want)`, `_whole(d, touched, before)`, `_update_as(me, fn)`, `_account_entry(...)`, `people.staff`, `people.usable_admins`.
- Produces: `POST /api/history/back` for an account unit (right `admin`): every change of the entry goes back to its `was` in one `people.update`, all or nothing; a new kind-`account` entry `what="putback"`, `text="Put back: " + <the entry's text>`, `changes` the new ones, `putback`/`putback_of`/`putback_ts` as Task 3.

Inside the update, before changing anything: each person is still on the staff list (else `"Can't put back: {name} is no longer on the staff list."`); each field is still at the entry's `now` (else `"Can't put back: this was changed again since."`); then each person's fields are set to `was` with `_change` (so a group change ends the Admin extra outside the committee, as on the admin page, and a change of rights signs the person out); then `_whole` (the last admin who can sign in). Any refusal → 409 with its sentence and nothing written.

- [ ] **Step 1: Write the failing tests** in `tests/test_admin.py`:
- `put_back_a_bulk_change`: give Exams until a date to two teachers with the bulk change; put it back by its entry id → 200; neither has the extra; one new entry with `what == "putback"` naming both; both were signed out (their sign-in number rose).
- `put_back_a_group_change`: a teacher moved to HOD (their step-4 departments copied); put back → teacher again and no departments.
- `put_back_refused_after_a_later_change`: move a teacher to HOD, then to Executive; putting back the first: 409 `"Can't put back: <admin's name> changed this again on …"`.
- `put_back_keeps_an_admin`: an entry that made the second admin; switch off the first admin; putting back the second's Admin extra is 409 with the last-admin sentence and nothing changes.
- `put_back_an_added_person_says_where`: the entry of "Add a person": 409 with the admin-page sentence; no `back.ok` in `/api/history`.
- `only_an_admin_puts_back_accounts`: a committee member without Admin (password): the account entry has no `back`; the POST is 403.

- [ ] **Step 2: Run it and see it fail**

Run: `.venv/bin/python tests/test_admin.py`
Expected: FAIL on `put_back_a_bulk_change`.

- [ ] **Step 3: Implement** the account branch.

- [ ] **Step 4: Run it and see it pass**

Run: `.venv/bin/python tests/test_admin.py; .venv/bin/python tests/test_putback.py; .venv/bin/python tests/test_signin.py`
Expected: each prints its "… passed" line.

- [ ] **Step 5: Commit**

```bash
git add app.py tests/test_admin.py
git commit -m "Put back an account change from the history"
```

---

### Task 5: Download the history (Excel)

**Files:**
- Modify: `app.py` (`_history_query`, `GET /api/history/download`)
- Test: `tests/test_history.py`, `tests/test_routes.py`

**Interfaces:**
- Consumes: Task 1's filters and `history.SCHOOL_TZ`.
- Produces:
  - `app._history_query(args) -> dict | tuple`: the filters of `/api/history` (who, where, dept, from, to, since, signins) as keyword arguments for `history.read`, or `({"error": …}, 400)`; `/api/history` and the download both use it.
  - `GET /api/history/download` with the same query, endpoint `history_download`, `@need("history")`: an `.xlsx` (`Content-Disposition: attachment; filename=history-YYYY-MM-DD.xlsx`, the day in school time), one sheet "History", header row `Day, Time, Who, Signed in with, Where, What, Was, Became, Departments`, newest first, at most `HISTORY_DOWNLOAD_MAX = 20000` entries, then, if there were more, a last row whose first cell is `"There are more entries than one download holds: pick fewer days."`. Day as `2026-11-19`, Time as `10:02 am` (school time); Signed in with as the page words it (password, code, shared code, personal code, by itself, Google); Was and Became filled for setup entries (by `history._show`), else empty; Departments joined by ", ".

- [ ] **Step 1: Write the failing tests** in `tests/test_history.py`:
- `download_is_the_committees`: a head (password) gets 401; the committee gets 200 with the `.xlsx` type and the filename of today in school time.
- `download_keeps_the_filters`: entries in two departments; `?dept=Maths` gives the header row plus the Maths entries only.
- `download_cells_are_never_formulas`: entries whose `as`, `text`, `was` and `now` start with `=`, `+`, `-` and `@`; reopened with openpyxl, every cell has `data_type == "s"` and the same text.
- `download_says_when_there_are_more`: monkeypatch `A.HISTORY_DOWNLOAD_MAX = 3` with five entries: 3 rows after the header, then the sentence.

`tests/test_routes.py`: add `"history_download": ('history',)`.

- [ ] **Step 2: Run them and see them fail**

Run: `.venv/bin/python tests/test_history.py`
Expected: FAIL (404).

- [ ] **Step 3: Implement** with `openpyxl.Workbook(write_only=False)`; set every cell's `data_type = "s"` after its value, so text is never read as a formula.

- [ ] **Step 4: Run them and see them pass**

Run: `.venv/bin/python tests/test_history.py; .venv/bin/python tests/test_routes.py`
Expected: each prints its "… passed" line.

- [ ] **Step 5: Commit**

```bash
git add app.py tests/test_history.py tests/test_routes.py
git commit -m "Download the history as Excel"
```

---

### Task 6: The history page: Put back, links, what you see, Download

**Files:**
- Modify: `static/history.js`, `static/history.html`

**Interfaces:**
- Consumes: `/api/history` (`scope`, `download`, `depts`, `back`, `since`), `POST /api/history/back`, `/api/history/download`.

What the page does:
- Under the header, a line by `scope`: all `"Everything, by everyone."`; dept `"Changes to {depts joined by ', ' and ' and '} rows, by anyone, and your own changes."`; own `"Your own changes."`.
- `since` from the address (as `who` is read now) is sent to the API; while it is set, a note `"Since {Tuesday 18 Nov, 4:12 pm}"` with a button `"Show all"` that clears it.
- Each unit with `back` shows, on the first of its entries in the list, a button `"Put back"` (`n` is 1) or `"Put back these {n} changes"`; when `ok` is false, the button is disabled and its sentence is shown under it in the `why` line. Pressing it asks `window.confirm("Put back this change?")` (`"Put back these {n} changes?"`), posts the id, then on 200 shows `"Put back."` in the message line and loads the list again; on another answer shows its `error` and loads the list again.
- An entry put back by another shows in its `why` line `"Put back {putback_of}'s change of {putback_ts as the page writes a day and a time}"`.
- Links instead of Put back: step 8 `"Undo it on step 8"` (to `/`), step 9 `"Open step 9"` (to `/`), relief `"Open relief"`, exams `"Open exams and events"`, a setup-replaced entry `"Use a saved copy on the committee page"` (to `/`).
- With `download`, a button `"Download (Excel)"` in the filters row opens `/api/history/download?` with the current filters.
- At the foot: `"The history is kept for two years."`
- A department filter for scope dept offers only the person's departments; for scope own, no department filter.

- [ ] **Step 1: Check the page parses**

Run: `node --check static/history.js`
Expected: no output.

- [ ] **Step 2: Implement** with the existing `h()` helper (`textContent` only).

- [ ] **Step 3: Check it again and run the page's API tests**

Run: `node --check static/history.js && .venv/bin/python tests/test_history.py && .venv/bin/python tests/test_putback.py`
Expected: no output from node; both print their "… passed" line.

- [ ] **Step 4: Commit**

```bash
git add static/history.js static/history.html
git commit -m "History page: Put back, links to undo elsewhere, what you see, Download"
```

---

### Task 7: "Since you last signed in" on the home page

**Files:**
- Modify: `history.py` (`summary`), `app.py` (`home`, `POST /home/later`), `README.md`
- Test: `tests/test_signin.py`, `tests/test_routes.py`

**Interfaces:**
- Consumes: Task 1's `history_scope`, `when_text`; the person's record `signins` (the last two sign-in times; the one before this sign-in is `signins[-2]`).
- Produces:
  - `history.summary(since: float, allow, me: str, top: int = 8) -> dict` with `n` (changes), `people` (distinct `as`), `rows` (a list of `(who, where, count)`, most first, `who` is `"Your own changes"` for `me`, at most `top`), `more` (rows left out), `published` (the newest publish time, or None). Changes are entries of kinds `setup`, `setup-replaced`, `draft`, `relief`, `exams`, `account` (no sign-ins, refusals or the app's follow-ups) that `allow` lets through; `published` comes from any kind-`draft` entry with `what == "publish"`, whatever `allow` says.
  - `POST /home/later`, endpoint `home_later`, `@need("timetable")`: keeps `session["later"] = signins[-1]` and goes back to `/home`.

What `/home` shows, above the tiles, when the person has a previous sign-in, `session["later"]` is not this sign-in, and there is something to say:
- Heading `"Since you last signed in"`; a line `"{when_text(previous)} · {n} changes by {people} people"` (`"1 change"`, `"1 person"`).
- A row per `rows` item: `"{who} · {where}"` and its count; then `"and {more} more"` when `more`.
- When `published`: `"The timetable was published again on {when_text(published)}."` (also for someone with no history right, who sees only this line).
- A link `"See them"` to `/history?since={previous}` (only with a history right) and a button `"Later"` (a form posting to `/home/later`).
- With a summary to show, `/home` does not jump to the only tile.
- No previous sign-in, nothing to say, or a shared code: no box.

- [ ] **Step 1: Write the failing tests** in `tests/test_signin.py`:
- `summary_after_a_second_sign_in`: a committee member signs in twice (password); between the two, two setup entries by "Ann" and one by "Bob" and a sign-in by Bob; `/home` shows `"Since you last signed in"`, `"3 changes by 2 people"`, `"Ann · Step 4 · Teachers"`, and a link `/history?since=`.
- `head_summary_is_their_departments_and_own`: a head's summary leaves out another department's change and shows `"Your own changes"`.
- `published_line_for_everyone`: a teacher (code, no history right) with a publish entry since their previous sign-in sees `"The timetable was published again on"` and no `"See them"`.
- `no_box_on_first_sign_in_or_after_later`: the first sign-in shows no box; after `POST /home/later`, `/home` shows no box until the next sign-in.
- `summary_times_are_school_time`: with `TZ=UTC`, the line starts with `when_text` of the previous sign-in.
- `summary_reads_little`: a previous sign-in this month: `history._lines` is called for one file.

`tests/test_routes.py`: add `"home_later": ('timetable',)`.

- [ ] **Step 2: Run them and see them fail**

Run: `.venv/bin/python tests/test_signin.py`
Expected: FAIL on `summary_after_a_second_sign_in`.

- [ ] **Step 3: Implement** `history.summary`, the box (every text through `esc`), the route; in `README.md`, the history paragraph gains Put back, who sees what, "Since you last signed in" and the download in two or three plain sentences.

- [ ] **Step 4: Run them and see them pass, then every suite**

Run: `.venv/bin/python tests/test_signin.py` then each `tests/test_*.py`, `node --test tests/*.test.js` and `node --check` on `static/history.js`, `static/admin.js`, `static/app.js`.
Expected: every file prints its "… passed" line; node reports 0 failures.

- [ ] **Step 5: Commit**

```bash
git add history.py app.py README.md tests/test_signin.py tests/test_routes.py
git commit -m "Home page: since you last signed in"
```

# Wizard stage 2: working together — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Department heads sign in with their own shared code and work on the school's one setup at the same time as the committee; every change saves by itself and nobody's work is overwritten.

**Architecture:** The editor stops sending the whole setup. After each change it works out what changed since the copy the server last confirmed (a list of small operations addressed by row id and field), sends only that, and the server applies it to its current setup under a lock and gives it a version number. Other browsers fetch the operations they have not seen and apply them. Rows get a hidden `_id` so an operation still finds its row after someone else adds or removes rows. The same diff and apply logic exists in Python (`sync.py`) and JavaScript (`static/sync.js`) and is proved identical by one shared file of cases.

**Tech Stack:** Python 3.11, Flask 3, vanilla JavaScript with no build step, Node (already used for `node --check`) to run the JavaScript sync tests.

**Spec:** `docs/superpowers/specs/2026-11-09-setup-wizard-design.md`, section "Working together" (One shared setup, Access, Saving, Seeing each other, Earlier copies).

## Global Constraints

- No framework, no bundler, no new Python or npm package. A second plain script, `static/sync.js`, is added on purpose: the sync logic must run under Node to be tested. It defines one global, `Sync`, and ends with `if (typeof module !== "undefined") module.exports = Sync;`.
- One gunicorn worker with threads (unchanged): the setup, its version and the change log live in the web process, guarded by one lock.
- Data is JSON on the volume. No database server.
- `ttgen/` is not edited; `ttgen/` and `skill/school-timetable-generator/scripts/ttgen/` stay identical. `_id` keys on rows must not reach the workbook as columns (`write_template` reads rows with `.get`, so they are ignored; Task 2 checks it).
- A setup saved before this stage (no `_id`, no version) must open; a workbook from any earlier template must still import.
- Heads may change only: `lessons` and `blocks` (any change), `teachers[].can_teach`, adding a teacher (always provisional), and the details of a teacher who is still provisional. The server enforces it; the page only mirrors it.
- Anti-goal from the spec: one person's save must never overwrite another's work.
- The repository is public: no secrets, no real names; never commit `.claude/launch.json` or `data/`. Test codes are generated in the tests, never typed into chat.
- Step numbers stay today's (School & day unnumbered, 1 Venues … 8 Publish).
- Wording in the page: plain sentences, sentence case, no "please", no exclamation marks.
- Tests: `.venv/bin/python tests/smoke.py`, `.venv/bin/python tests/test_sync.py`, `node tests/sync.test.js` (plain asserts, no runner). Page checks in the browser preview against a scratch `DATA_DIR`, never the repository's `data/`.
- Commit on branch `wizard-stage-2` after each task. Do not push or open a pull request until the committee asks.

## The change format (shared by server and browser)

A change is a JSON array of operations, applied in order:

| Operation | Meaning |
|---|---|
| `["set", section, id, field, value]` | set one field of the row with that `_id`; `null` removes the field; a missing row is skipped |
| `["merge", section, id, field, adds, removes]` | for list fields merged item by item (`teachers.can_teach`, `students.groups`): drop `removes`, then append each of `adds` not already there (items compared as canonical JSON) |
| `["add", section, row, after]` | insert `row` (it carries its `_id`) after the row whose `_id` is `after`; `""` = first; unknown `after` = append; an `_id` already present is skipped |
| `["del", section, id]` | remove the row; a missing row is skipped |
| `["school", key, value]` | `spec.school[key] = value` (the whole value); `null` removes the key |
| `["day", level, day, codes]` | `spec.day_structure[level][day] = codes`; `null` removes the day, and a level left with no days is removed |
| `["top", key, value]` | any other top-level key of the spec (for example `extra_sheets`) |

`section` is one of `venues, classes, subjects, teachers, blocks, lessons, rules, students, combinations, roles`. Keys starting with `_` are never compared or sent, except `_id` inside an added row. A field missing and a field `null` are the same. Canonical JSON = keys sorted, no spaces. `diff(base, cur)` emits, section by section in the order above: `del`s (base order), `add`s (cur order), then for rows in both (cur order) `set`/`merge` with fields in alphabetical order; then `school` (keys sorted), `day` (levels then days, sorted), `top` (keys sorted). The order of rows already in a list is not synced.

## Review Focus

1. Two heads add a different subject to the same teacher's can-teach inside one sync interval → both subjects are kept. Pinned in Task 1 (case `merge-both-adds`) and Task 2.
2. A head's connection drops while they keep editing, or they close the tab offline → the changes are kept in the browser and sent when the server is reachable again; the header says so meanwhile. Pinned in Task 4.
3. The server restarts (a Railway redeploy) in the middle of a session → every browser reloads the setup and re-applies what it had not sent; nothing is lost. Pinned in Task 2 (server side) and Task 4.
4. The committee replaces the whole setup while a head has unsent changes → the head's changes are dropped with a message that says why; they are not merged into the new setup. Pinned in Task 6.
5. Someone else's change arrives while a person is typing in a field or has a pop-up open → what they are typing is not wiped; the change shows once they commit or close. Pinned in Task 4.

---

### Task 1: The change format in Python and JavaScript

**Files:**
- Create: `sync.py`, `static/sync.js`, `tests/sync_cases.json`, `tests/test_sync.py`, `tests/sync.test.js`

**Interfaces:**
- Produces (Python): `sync.LISTS: tuple[str, ...]`; `sync.MERGE: dict[str, tuple[str, ...]]` = `{"teachers": ("can_teach",), "students": ("groups",)}`; `sync.new_id() -> str` (10 chars of `a-z0-9`); `sync.ensure_ids(spec: dict) -> bool` (gives every list row lacking one an `_id`; True if it added any); `sync.diff(base: dict, cur: dict) -> list`; `sync.apply(spec: dict, ops: list) -> int` (mutates `spec`; returns how many operations were skipped).
- Produces (JavaScript, global `Sync`): `Sync.LISTS`, `Sync.MERGE`, `Sync.newId()`, `Sync.ensureIds(spec)`, `Sync.diff(base, cur)`, `Sync.apply(spec, ops)`, `Sync.clone(x)`, and `Sync.rebase(base, sent, now, theirs, ours) -> {base, spec}` where `base` = the last confirmed copy, `sent` = the copy the diff was taken from, `now` = the working copy when the answer came back, `theirs` = other people's operations the server applied first, `ours` = the operations just accepted. It returns `base' = apply(apply(clone(base), theirs), ours)` and `spec' = apply(clone(base'), diff(sent, now))`.

- [ ] **Step 1: Write `tests/sync_cases.json`**

An array of cases, each `{"name", "base", "cur", "ops"}` (diff must give exactly `ops`, and applying `ops` to `base` must give `cur` up to row order) and, for merges, `{"name", "base", "mine", "theirs", "merged"}` (apply `theirs` then `mine` to `base`). At least these, with made-up data:

```json
[
 {"name": "set-one-field",
  "base": {"school": {"name": "A"}, "classes": [{"_id": "c1", "class": "1A", "size": 38}]},
  "cur":  {"school": {"name": "A"}, "classes": [{"_id": "c1", "class": "1A", "size": 40}]},
  "ops":  [["set", "classes", "c1", "size", 40]]},
 {"name": "add-after-and-delete",
  "base": {"classes": [{"_id": "c1", "class": "1A"}, {"_id": "c2", "class": "1B"}]},
  "cur":  {"classes": [{"_id": "c1", "class": "1A"}, {"_id": "c3", "class": "1C"}]},
  "ops":  [["del", "classes", "c2"], ["add", "classes", {"_id": "c3", "class": "1C"}, "c1"]]},
 {"name": "null-equals-missing",
  "base": {"teachers": [{"_id": "t1", "name": "Tan", "note": null}]},
  "cur":  {"teachers": [{"_id": "t1", "name": "Tan"}]},
  "ops":  []},
 {"name": "underscore-keys-ignored",
  "base": {"lessons": [{"_id": "l1", "subject": "Mathematics"}]},
  "cur":  {"lessons": [{"_id": "l1", "subject": "Mathematics", "_counts": {"3": 6}}]},
  "ops":  []},
 {"name": "merge-field-diff",
  "base": {"teachers": [{"_id": "t1", "can_teach": [{"subject": "Mathematics", "levels": "All"}]}]},
  "cur":  {"teachers": [{"_id": "t1", "can_teach": [{"subject": "Mathematics", "levels": "All"}, {"levels": "All", "subject": "Physics"}]}]},
  "ops":  [["merge", "teachers", "t1", "can_teach", [{"levels": "All", "subject": "Physics"}], []]]},
 {"name": "school-and-day",
  "base": {"school": {"name": "A", "weeks": 2}, "day_structure": {"Sec 1": {"Odd Mon": "FLL", "Odd Tue": "FLL"}}},
  "cur":  {"school": {"name": "B", "weeks": 2}, "day_structure": {"Sec 1": {"Odd Mon": "FLR"}}},
  "ops":  [["school", "name", "B"], ["day", "Sec 1", "Odd Mon", "FLR"], ["day", "Sec 1", "Odd Tue", null]]},
 {"name": "merge-both-adds",
  "base": {"teachers": [{"_id": "t1", "can_teach": []}]},
  "mine":   [["merge", "teachers", "t1", "can_teach", [{"levels": "All", "subject": "Physics"}], []]],
  "theirs": [["merge", "teachers", "t1", "can_teach", [{"levels": "All", "subject": "Chemistry"}], []]],
  "merged": {"teachers": [{"_id": "t1", "can_teach": [{"levels": "All", "subject": "Chemistry"}, {"levels": "All", "subject": "Physics"}]}]}},
 {"name": "same-field-later-wins",
  "base": {"classes": [{"_id": "c1", "size": 38}]},
  "mine":   [["set", "classes", "c1", "size", 40]],
  "theirs": [["set", "classes", "c1", "size", 36]],
  "merged": {"classes": [{"_id": "c1", "size": 40}]}},
 {"name": "edit-a-row-someone-deleted",
  "base": {"classes": [{"_id": "c1", "size": 38}, {"_id": "c2", "size": 30}]},
  "mine":   [["set", "classes", "c2", "size", 31]],
  "theirs": [["del", "classes", "c2"]],
  "merged": {"classes": [{"_id": "c1", "size": 38}]}}
]
```

- [ ] **Step 2: Write `tests/test_sync.py` and `tests/sync.test.js`, run them, see them fail**

Both load the cases and assert, for each: `diff(base, cur)` equals `ops` (compare canonical JSON), `apply(copy(base), ops)` equals `cur`, and `apply(apply(copy(base), theirs), mine)` equals `merged`. Each also asserts `ensure_ids` gives ids to rows without one, leaves existing ids alone and reports whether it added any. `tests/sync.test.js` adds one `Sync.rebase` case: base = `set-one-field`'s base; `sent` = base with 1A's size 40; `now` = `sent` plus a new class `c9`; `theirs` = `[["set","classes","c1","size",36]]`; `ours` = `[["set","classes","c1","size",40]]` → `base.classes[0].size === 40`, `spec.classes[0].size === 40`, and `spec` has `c9` while `base` does not.
Run: `.venv/bin/python tests/test_sync.py` → fails with `ModuleNotFoundError: sync`. Run: `node tests/sync.test.js` → fails with `Cannot find module`.

- [ ] **Step 3: Implement `sync.py`**, the functions under Interfaces, per "The change format".
- [ ] **Step 4: Implement `static/sync.js`**, the same logic, plus `clone` (JSON round trip) and `rebase`.
- [ ] **Step 5: Run both** → each prints `N cases passed` with no failure.
- [ ] **Step 6: Commit** — `git add sync.py static/sync.js tests && git commit -m "Setup changes as small operations, the same in Python and JavaScript"`

---

### Task 2: The server keeps one versioned setup

**Files:**
- Modify: `store.py` (`save_setup` 44-53, `past_setups` 55-65, `load_setup`, `setup_record`, `KEEP_SAVES`), `app.py` (`/api/setup` GET and PUT, and new routes beside them), `tests/smoke.py`

**Interfaces:**
- Consumes: `sync.ensure_ids`, `sync.apply`.
- Produces (`store`):
  - `setup_record() -> dict(spec, saved_at, ts, v)` (`spec` None when there is no setup). The record is cached in memory; the first load gives old rows their `_id` and a first version, and writes it back.
  - `apply_changes(ops: list, client: str) -> int` — applies to the current spec under the setup lock, raises `LookupError` when there is no setup, takes a restore point first when the last one is more than 600 seconds old, or when the change deletes a teacher or more than 20 rows, writes `setup.json`, appends `dict(v, client, ops)` to the log (`collections.deque(maxlen=400)`), returns the new version.
  - `changes_since(since: int, client: str) -> dict` — `dict(v, patches=[dict(v, ops)])` with other clients' entries newer than `since`; or `dict(v, reset=True, replaced=bool)` when the log no longer reaches back to `since` (`replaced` is True when a whole-setup replacement happened after `since`).
  - `replace_setup(spec: dict, why: str) -> dict(v, saved_at)` — restore point first, `ensure_ids`, version + 1, log cleared, the replacement's version remembered (and stored in `setup.json` as `replaced_v`).
  - `restore_point(why: str) -> None` (the copy's `what` is `why`; `replace_setup` passes `"Before: " + why`, the timer passes `"While working"`); `copies() -> list[dict(id, what, when)]` newest first (no specs); `restore(copy_id: str) -> dict(v, saved_at)` (a `replace_setup` from that copy; `KeyError` if unknown). `KEEP_SAVES = 48`.
  - `seen(client: str) -> int` — notes this client as here now; returns how many other clients were seen in the last 20 seconds.
  - `save_setup(spec)` stays as a thin wrapper over `replace_setup(spec, "Saved")` (tests and old callers).
- Produces (module state the tests reach into): `store._setup` (the cached record, a dict; empty = not loaded) and `store._log` (the deque).
- Produces (routes; all committee-only in this task, Task 3 widens some):
  - `GET /api/setup` → `{spec, v, saved_at}`.
  - `PUT /api/setup` body `{spec, why}` (a bare spec is still accepted) → `{v, saved_at}`.
  - `GET /api/setup/changes?since=V&client=C` → `changes_since(...)` plus `others`.
  - `POST /api/setup/changes` body `{since, client, ops}` → 409 `{error}` when there is no setup; else applies and answers like the GET (so the caller catches up in the same call), with its own new version as `v`.
  - `GET /api/setup/copies` → `copies()`; `POST /api/setup/restore` body `{id}` → `{v, saved_at}`, 404 for an unknown id.

- [ ] **Step 1: Add the failing checks to `tests/smoke.py`**

```python
def _changes(client, since, ops=None, who=None):
    who = who or c
    r = who.post("/api/setup/changes", json={"since": since, "client": client, "ops": ops}) if ops is not None else who.get(f"/api/setup/changes?since={since}&client={client}")
    return r.status_code, r.get_json()

def test_two_people_change_different_rows():
    c.put("/api/setup", json=c.get("/api/sample/secondary").get_json())
    rec = c.get("/api/setup").get_json(); v0 = rec["v"]; a, b = rec["spec"]["classes"][0], rec["spec"]["classes"][1]
    assert a["_id"] and b["_id"] and a["_id"] != b["_id"]
    _, ja = _changes("A", v0, [["set", "classes", a["_id"], "size", 41]])
    _, jb = _changes("B", v0, [["set", "classes", b["_id"], "size", 42]])
    assert ja["v"] == v0 + 1 and jb["v"] == v0 + 2
    assert jb["patches"] == [{"v": v0 + 1, "ops": [["set", "classes", a["_id"], "size", 41]]}]    # B catches up on A in the same call
    now = c.get("/api/setup").get_json()["spec"]["classes"]
    assert (now[0]["size"], now[1]["size"]) == (41, 42)
    _, ga = _changes("A", ja["v"]); assert [p["v"] for p in ga["patches"]] == [v0 + 2] and ga["others"] >= 1

def test_both_can_teach_additions_are_kept():
    rec = c.get("/api/setup").get_json(); t = rec["spec"]["teachers"][0]; v = rec["v"]
    for who, subj in (("A", "Zzz One"), ("B", "Zzz Two")):
        _changes(who, v, [["merge", "teachers", t["_id"], "can_teach", [{"levels": "All", "subject": subj}], []]])
    got = [x["subject"] for x in c.get("/api/setup").get_json()["spec"]["teachers"][0]["can_teach"]]
    assert "Zzz One" in got and "Zzz Two" in got

def test_a_replaced_setup_resets_everyone():
    v = c.get("/api/setup").get_json()["v"]
    c.put("/api/setup", json={"spec": c.get("/api/sample/primary").get_json(), "why": "Opened a workbook"})
    code, j = _changes("A", v); assert j == {"v": j["v"], "reset": True, "replaced": True, "others": j["others"]}
    assert c.get("/api/setup/copies").get_json()[0]["what"] == "Before: Opened a workbook"

def test_a_restart_resets_without_losing_the_setup():
    v = c.get("/api/setup").get_json()["v"]; _changes("A", v, [["school", "timetable", "Term 9"]])
    store._log.clear(); store._setup.clear()            # what a restart does to the process
    rec = c.get("/api/setup").get_json(); assert rec["v"] == v + 1 and rec["spec"]["school"]["timetable"] == "Term 9"
    _, j = _changes("A", v); assert j["reset"] is True and j["replaced"] is False

def test_ids_do_not_reach_the_workbook():
    import io, openpyxl
    r = c.post("/api/build", json=c.get("/api/setup").get_json()["spec"])
    wb = openpyxl.load_workbook(io.BytesIO(r.data), read_only=True)
    assert not any("_id" in str(cell) for ws in wb.worksheets for row in ws.iter_rows(max_row=8, values_only=True) for cell in row if cell)
```

Run: `.venv/bin/python tests/smoke.py` → fails at `test_two_people_change_different_rows` (`KeyError: 'v'`).

- [ ] **Step 2: Implement the `store` functions** named under Interfaces. One lock (`_setup_lock`) guards `_setup` (the cached record), `_log`, the presence table and every write of `setup.json`. `setup.json` keeps `saved_at, ts, v, replaced_v, spec`. `past_setups()` keeps working for the Students step's restore helper.
- [ ] **Step 3: Implement the routes** in `app.py`.
- [ ] **Step 4: Run** `.venv/bin/python tests/smoke.py` → all pass, including the five new ones.
- [ ] **Step 5: Commit** — `git commit -m "One versioned setup on the server: changes apply as operations, with a log to catch up from"`

---

### Task 3: The heads' code

**Files:**
- Modify: `access.py` (`ROLES`, `configured`, `match`), `app.py` (`CHOICES`, `login`, `index`, `need(...)` on routes, `/api/status`, `POST /api/setup/changes`), `sync.py`, `tests/smoke.py`, `tests/test_sync.py`
- Create: `static/choice-heads.png` (copy `static/choice-committee.png`; new artwork is not part of this stage)

**Interfaces:**
- Produces: role name `"head"`, from the optional variable `HEADS_CODE`. `access.configured()` does not report a missing `HEADS_CODE` as a problem, but does report it when too short or equal to another code. The sign-in page shows a fourth choice, "Department heads" ("Heads of department: who can teach what, teaching groups and bands."), only when `HEADS_CODE` is set. A head lands on `/` and gets the editor.
- Produces: `sync.head_may(spec: dict, ops: list) -> str | None` — `None` when every operation is one a head may make, else one sentence naming the first that is not. Allowed: any operation on `lessons` or `blocks`; `["merge", "teachers", id, "can_teach", …]`; `["add", "teachers", row, after]`; `["set" | "del", "teachers", id, …]` when that teacher's current `provisional` is `"Yes"` and the field is not `provisional`.
- Produces: `POST /api/setup/changes` from a head: checks `head_may` first (403 `{error}` and nothing applied); forces `row["provisional"] = "Yes"` on every teacher a head adds.
- Produces: `GET /api/status` gains `role`; for a head it omits `codes` and `code_problems`.
- Who may call what: head and committee: `GET /`, `GET /api/meta/<kind>`, `GET /api/sample/<kind>`, `GET /api/setup`, `GET` and `POST /api/setup/changes`, `GET /api/status`, and every route teachers may call. Committee only: everything else that is committee-only today, plus `PUT /api/setup`, `/api/setup/copies`, `/api/setup/restore`, `/api/check`, `/api/build`.

- [ ] **Step 1: Failing checks.** In `tests/test_sync.py`: `head_may` is `None` for a `lessons` set, a `blocks` add, a can-teach merge, a teacher add, and a set on a provisional teacher; it is a string for `["set","classes",…]`, `["school","name","X"]`, a set on a teacher whose `provisional` is `"No"`, and `["set","teachers",id,"provisional","No"]`. In `tests/smoke.py` (set `HEADS_CODE` in the environment block beside the others; `h` = a second test client signed in as `{"as": "heads", "code": …}`):

```python
def test_a_head_can_change_groups_but_not_classes():
    rec = c.get("/api/setup").get_json(); v = rec["v"]; sp = rec["spec"]
    assert h.get("/").status_code == 200 and h.get("/api/setup").status_code == 200
    code, _ = _changes("H", v, [["set", "lessons", sp["lessons"][0]["_id"], "students", 12]], who=h); assert code == 200
    code, j = _changes("H", v, [["set", "classes", sp["classes"][0]["_id"], "size", 99]], who=h); assert code == 403 and "classes" in j["error"].lower()
    assert c.get("/api/setup").get_json()["spec"]["classes"][0]["size"] != 99

def test_a_teacher_added_by_a_head_is_provisional():
    v = c.get("/api/setup").get_json()["v"]
    _changes("H", v, [["add", "teachers", {"_id": "newhire001", "name": "New Science teacher 1", "provisional": "No"}, ""]], who=h)
    t = next(x for x in c.get("/api/setup").get_json()["spec"]["teachers"] if x["_id"] == "newhire001"); assert t["provisional"] == "Yes"

def test_a_head_cannot_download_or_publish_or_replace():
    for method, url in (("POST", "/api/build"), ("PUT", "/api/setup"), ("POST", "/api/import-timetable"), ("GET", "/api/codes.csv"), ("POST", "/api/check"), ("GET", "/api/setup/copies")):
        assert h.open(url, method=method, json={}).status_code == 401, url
    s = h.get("/api/status").get_json(); assert s["role"] == "head" and "codes" not in s
```

Run: fails at the heads sign-in (`assert … == 302`).

- [ ] **Step 2: Implement** `access.py`, the sign-in choice, `need(...)` lists, `head_may`, and the head branch of `POST /api/setup/changes`.
- [ ] **Step 3: Run** all three test files → pass. Also run `.venv/bin/python tests/smoke.py` once with `HEADS_CODE` unset in the script's environment: the sign-in page (`c.get("/login").data`) has no "Department heads" and nothing else fails (guard the head tests with `if h:`).
- [ ] **Step 4: Commit** — `git commit -m "A shared code for department heads, limited on the server to groups, bands and who can teach what"`

---

### Task 4: The editor saves by itself

**Files:**
- Modify: `static/index.html` (load `/static/sync.js` before `app.js`; remove the `saveServer` button; add `<span id="others" class="badge" hidden></span>` beside `#saveState`), `static/app.js` (lines 11-76 "storage, server", every `G.server = await getJSON("/api/setup")` after a change (lines ~909, 943, 1299), the init block at the end of the file)

**Interfaces:**
- Consumes: `Sync.*`; the routes of Task 2; `role` from `/api/status`.
- Produces: `SYNC = { v, base, client, state, others, timer, busy }` — `base` the last confirmed copy (an object), `client` a `Sync.newId()` kept in `sessionStorage`, `state` one of `"saved"`, `"saving"`, `"offline"`.
- Produces: `scheduleSync()` (called by `save()` unless `S.practice`; debounced 600 ms) and `async syncNow()`:
  1. `Sync.ensureIds(S.spec)`; `sent = Sync.clone(S.spec)`; `ops = Sync.diff(SYNC.base, sent)`.
  2. `ops.length` → `POST /api/setup/changes {since: SYNC.v, client, ops}`; else `GET …?since=&client=`.
  3. On `{reset: true}`: fetch `GET /api/setup`; when `replaced` → `SYNC.base = S.spec =` the server's copy, clear undo, toast "The committee replaced the school's setup, so the changes you had not sent were dropped." (only if `ops.length`); else → base = server's copy and `S.spec = Sync.apply(Sync.clone(base), ops)`, then sync again.
  4. Otherwise `({base, spec} = Sync.rebase(SYNC.base, sent, S.spec, theirs, ops))`, `SYNC.v = j.v`, `SYNC.others = j.others`; when `theirs` is not empty, `S.spec = spec` and redraw (rule 5), else keep the working object.
  5. Redraw rule: never call `render()` while `#pop` is open, or while the focused element inside `#main` is a text, number or time input whose value differs from its `defaultValue`; in those cases keep the new spec aside and apply it on the next `change`, `focusout` or pop-up close.
  6. A failed request or a 5xx → `state = "offline"`, retry every 5 seconds; 401 → `/login`; 403 → toast the server's sentence, reload the server's copy, clear undo.
- Produces: with nothing to send, `syncNow()` still runs every 4 seconds (it is how other people's changes arrive). `poll()` for `/api/status` stays as it is.
- Produces: `#saveState` reads "Saved", "Saving…" or "Offline: your changes are kept in this browser and will be sent"; `#others` reads "1 other here" / "N others here", hidden at 0.
- Produces: `localStorage[KEY]` holds `{sync: 1, step, at, kind, v, pending}` where `pending` is `Sync.diff(SYNC.base, S.spec)`: no longer the whole spec. On load with a setup on the server: take the server's copy, apply `pending` when `v` still matches or the server has not replaced the setup since, then sync.
- Removed: `saveServer`, `S.dirty`, `S.base` (the timestamp), `G.server`, the "Open the school's saved setup" and "Continue in this browser" buttons on Start (Task 6 rebuilds Start).

- [ ] **Step 1: Browser check that fails first.** Start the app with a scratch `DATA_DIR` holding the secondary sample (a temporary launch config, as stage 1's tests did). Open it in two tabs (A and B). In A change class 1A's size. Expected today: B never shows it without a reload → that is the failure to remove.
- [ ] **Step 2: Implement** the engine per Interfaces.
- [ ] **Step 3: Check in the browser, two tabs:**
  - A changes 1A's size → within 6 seconds B shows it, with no reload; `#saveState` in A goes "Saving…" then "Saved"; both show "1 other here".
  - A and B each change a different class in the same second → both tabs end with both changes.
  - B has a venue's name half typed (focused, not committed) while A changes a class → B's typing is still there; after B presses Tab, B shows A's change. Same with B's can-teach pop-up open.
  - Stop the server; in A change two things: `#saveState` says Offline. Reload A (still stopped): the page says it cannot reach the server and keeps the pending changes. Start the server: A sends them; B shows them. (Review Focus 2 and 3.)
  - `read_network_requests`: a single change sends a `POST /api/setup/changes` whose body is under 1 KB, and no request carries the whole setup.
- [ ] **Step 4: Run** `node --check static/app.js && node tests/sync.test.js && .venv/bin/python tests/smoke.py` → pass.
- [ ] **Step 5: Commit** — `git commit -m "The editor sends each change by itself and shows other people's as they arrive"`

---

### Task 5: Undo takes back only your own changes

**Files:**
- Modify: `static/app.js` (`save` 16-27, `undo` 40-45, `saveState`)

**Interfaces:**
- Consumes: `Sync.diff`, `Sync.apply`.
- Produces: `S.undo` and `S.redo` hold `{undo: ops, redo: ops}` entries, not whole setups. `save()` (not `quiet`) pushes `{undo: Sync.diff(now, before), redo: Sync.diff(before, now)}` where `before` is the working copy at the previous `save()`; changes within one second still merge into one entry (keep the first `before`). `undo(back)` applies the entry's `undo` (or `redo`) operations to `S.spec`, then saves quietly and syncs. Operations arriving from other people never touch these lists. `UNDO_MAX` stays 20.

- [ ] **Step 1: Failing check, two tabs.** A changes 1A's size 38 → 41. B changes 1B's size → 42. A presses Undo. Expected after this task: 1A back to 38 and 1B still 42 in both tabs. Before it (whole-setup snapshots): A's undo also puts 1B back.
- [ ] **Step 2: Implement.**
- [ ] **Step 3: Check:** the case above; Redo puts 41 back; undo of an added row removes it and redo brings the same row (same `_id`) back; undo after someone else deleted the row does nothing and does not throw; ⌘Z inside a text box still does the browser's own undo.
- [ ] **Step 4: Commit** — `git commit -m "Undo and Redo work on your own changes only"`

---

### Task 6: One shared setup, a practice copy, and guarded whole-setup actions

**Files:**
- Modify: `static/app.js` (`VIEWS.start` ~615-630, `begin`, `adopt`, the `importX` and `loadJson` handlers, `VIEWS.download` "Keep a copy" card, `VIEWS.publish`, the init block), `static/style.css` (one rule for the practice banner)

**Interfaces:**
- Consumes: `PUT /api/setup {spec, why}`, `GET /api/setup/copies`, `POST /api/setup/restore`, `SYNC.others`, `S.role`.
- Produces: `S.practice` (boolean). In practice: no sync, no `localStorage` write of pending changes, a banner on every step — "Practice copy: nothing here is saved for the school." with **Back to the school's setup** — and the Publish step shows only "Publishing is off in a practice copy." The sample-school buttons on Start open a practice copy; they never touch the server.
- Produces: `async replaceSetup(spec, why)` — committee only. Asks first: "This replaces the school's setup for everyone." + (`SYNC.others` ? ` ${n} other${s} ${are} working in it now.` : "") + " An earlier copy is kept. Replace it?" Then `PUT`, then loads the server's copy. Used by: Start blank (`why` "Started blank"), Open a setup workbook ("Opened a workbook"), Load from file ("Loaded from a file"). When the school has no setup yet, it does not ask.
- Produces: on Download's "Keep a copy" card, committee only: **Restore an earlier copy** — a list from `/api/setup/copies` (when, what) each with **Restore**, which asks the same question and calls `/api/setup/restore`.
- Produces: Start for a signed-in person when the school has a setup: it opens straight on the school's setup (the step they were on); Start itself shows what the setup is (school, timetable, "N others here") and, for the committee, the whole-setup actions. When there is none: the committee sees the begin choices; a head sees "The committee has not started the setup yet."
- Produces: the rollout question. A browser whose `localStorage[KEY]` has a `spec`, no `sync` marker and `dirty` true is asked once, before anything else: "This browser has changes from before that were never saved for the school." with **Save them to a file** (downloads the spec, then clears it), **Use them** (committee only: `replaceSetup(spec, "Unsaved changes from a browser")`) and **Discard them**. Any old-format entry is cleared after the choice.

- [ ] **Step 1: Failing checks to note first:** today "Secondary school · sample" followed by any change makes the page unsaved-with-a-Save-button (no practice copy), and "Open a setup workbook" replaces the local copy without asking.
- [ ] **Step 2: Implement.**
- [ ] **Step 3: Check in the browser** (scratch data; tab A committee, tab B heads once Task 7 is in, else a second committee tab):
  - Sample → banner shows; change something; `read_network_requests` shows no `/api/setup` write; Back returns to the school's setup unchanged.
  - With B open and holding one unsent change (stop B's network by `SYNC.busy = true` in the page, change a group, then run Load from file in A and answer yes): A's question names "1 other"; B shows the dropped-changes message and A's setup, and B's change is not in it. (Review Focus 4.)
  - Restore an earlier copy lists the copy made by that replacement; restoring it brings the earlier setup back in both tabs.
  - In the page run `localStorage.setItem("ttsetup.v1", JSON.stringify({kind: "secondary", step: 3, at: "classes", dirty: true, base: 0, spec: S.spec}))`, reload: the question appears once; "Save them to a file" downloads a file and the question does not come back.
- [ ] **Step 4: Run** `node --check static/app.js && .venv/bin/python tests/smoke.py`.
- [ ] **Step 5: Commit** — `git commit -m "One shared setup: practice copies for the samples, and whole-setup actions that ask first"`

---

### Task 7: What a head sees

**Files:**
- Modify: `static/app.js` (`render`, the step list, `VIEWS.teachers` ~695-723, `addRow` for `teachers`, the click handler for `[data-pop]`, `[data-del]`, `[data-add]`, `[data-bulk]`), `static/style.css`

**Interfaces:**
- Consumes: `S.role` (`"committee"` or `"head"`), set from `/api/status` before the first `render()`.
- Produces: for a head —
  - the step list has no Download, Publish or Students;
  - on every step except 4 Teachers and 5 TG & deployment, every `input`, `select`, `textarea` and `button` in `#main` is disabled and pop-up chips do not open, with one line at the top: "Only the committee can change this step.";
  - on step 5 everything works;
  - on step 4: **+ Add teacher** works and the new row has `provisional: "Yes"`; the row of a teacher with `provisional === "Yes"` is editable except its Provisional field, and can be removed; for every other teacher only **Can teach** (the pop-up, and "give a subject" / "take a subject off" on ticked teachers) works; department, role and allowance on ticked teachers are disabled.
- Produces: for the committee nothing changes, except that a provisional teacher's row shows a small "added by a head" mark beside its Provisional field so they can confirm it (set it to No).

- [ ] **Step 1: Failing check.** Sign in with the heads' code (scratch data, `HEADS_CODE` in the temporary launch config): today the heads' sign-in does not exist in the page flow, and after Task 3 the editor shows everything as editable.
- [ ] **Step 2: Implement.**
- [ ] **Step 3: Check in the browser as a head:**
  - the step list ends at 6 Configuration & constraints; opening `/#` on a hidden step by its number does nothing;
  - on 2 Classes every field is disabled; forcing a change from the console (`S.spec.classes[0].size = 99; save()`) makes the server answer 403 and the page reloads the server's copy with the server's sentence in a toast;
  - on 5, add a group and deploy a teacher: it saves, and the committee tab shows it within 6 seconds;
  - on 4: add a teacher → row is provisional and editable; change an existing teacher's can-teach → saves; an existing teacher's allowance field is disabled;
  - as the committee: the new teacher shows the mark; setting Provisional to No makes the row read-only in the head's tab.
- [ ] **Step 4: Run** `node --check static/app.js && .venv/bin/python tests/smoke.py && .venv/bin/python tests/test_sync.py && node tests/sync.test.js`.
- [ ] **Step 5: Commit** — `git commit -m "Heads see every step, change groups, bands and who can teach what, and can add new teachers"`

---

### Task 8: README and deployment guide

**Files:**
- Modify: `README.md` (the codes table, "Saving the setup", "What's inside", "Run locally"), `docs/DEPLOY.md` (variables block and table, the volume table, first sign-in), `.env.example`

- [ ] **Step 1:** README: add `HEADS_CODE` to the codes table ("department heads: every step to read; groups, bands, who can teach what, and new teachers to change"); replace "Saving the setup" with how it works now (every change saves by itself; several people at once; Undo is your own changes; offline changes are kept and sent; restore points every 10 minutes while people work, the last 48; samples are practice copies; whole-setup actions ask first and are committee-only); add `sync.py`, `static/sync.js` and the two new test files to "What's inside" and the test commands to "Run locally".
- [ ] **Step 2:** `docs/DEPLOY.md` and `.env.example`: `HEADS_CODE` as optional (without it there is no heads' sign-in); `setup_history/` now holds restore points taken while people work (the last 48) and before every whole-setup action; a redeploy makes every open browser reload the setup, and unsent changes are re-sent.
- [ ] **Step 3: Check:** `grep -n -i "save progress" README.md docs/DEPLOY.md static/app.js static/index.html` → no lines. Run all three test commands.
- [ ] **Step 4: Commit** — `git commit -m "Docs: the heads' code, and saving that happens by itself"`

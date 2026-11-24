# One Student's Groups on the Published Timetable: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The committee opens one student on the Students step, sees their bands, groups, head counts and week on the published timetable, and a save changes that student's own published timetable at once, with no publish on step 9.

**Architecture:** The Students step stays the one list. After every applied setup change that names student rows, a new module `students.py` brings those students up to date in the published model (`model.pkl`, `meta.json`), never touching lessons and never moving `published_at`. The stored download files are remade by one background thread. The page gets a pure module `static/studentview.js` for the working-out and a screen in `static/app.js`.

**Tech Stack:** Python 3 / Flask (`app.py`, `store.py`, new `students.py`), vanilla JS (`static/`), plain-script tests (`<python> tests/x.py`, `node tests/x.test.js`). No new dependency.

**Spec:** `docs/superpowers/specs/2026-11-24-student-groups-design.md` (mockup beside it). Read it before any task; where the plan is silent the spec decides.

## Global Constraints

- Work only in the worktree `tt-student-groups` beside the dev checkout, branch `student-groups`. Never commit to `main`. Never push, open a pull request, merge or deploy.
- **NEVER run `git stash`, `git stash pop`, `git checkout -- <file>`, `git reset --hard` or switch branches.** To see old code use `git show REV:path > <scratch file>`. After each task `git stash list` must still show exactly the two old entries ("On import-publish: verify-base-import-publish", "On main: pre-sync copy of the critical-vs-warning edits").
- Never use `pkill`/`killall` by name or pattern. Stop only processes you started, by PID.
- Python is the dev checkout's `.venv/bin/python` (written `$PY` below). The worktree has no `.venv` of its own.
- Never print, read aloud or edit the values in `.claude/launch.json`. No test may call a model API or the Telegram API. Tests and browser checks use a scratch `DATA_DIR`, never the repo's `data/`.
- The repository is public: made-up names only (the fixture names below), the school is only ever "CTSS". No real student or teacher name, in code, tests, docs or commit text.
- Do not change the `ttgen` package (it is copied under `skill/` and a test keeps the two identical). Import from it freely.
- `published_at` in `meta.json` must never change except in `store.publish`.
- The cached published model (`store.published()["model"]`) is shared with other requests: never change it in place.
- Product wording never says "he" or "she" about a student. Plain, short sentences in the style of the page.
- `static/app.js` has very long lines. Search it with `grep -n … | cut -c1-300` or Python, never read it whole. After replacing a block of it, list the names the old block defined and check each is still defined or unused. Inside a long line use `/* */`, never `//`.
- Run `node --check static/app.js` after every edit of it.
- Commit after each task with a message ending in the line `Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>`. Commit only files the task changed. Use a quoted heredoc for commit text.
- Every new route is `@need("committee")` and is added to `GUARDS` in `tests/test_routes.py`.

## Review Focus

1. **Loading a new list.** "Replace the list" or "Remove all" while a timetable with students is published: nobody may be removed from the published timetable by that save (Task 1 test `a_save_that_deletes_several_removes_nobody`).
2. **Two quick saves of the same student.** The published record must end as the setup ends, whichever update finishes last (Task 1 test `the_update_reads_the_setup_as_it_is_now`).
3. **A student change arriving while the files are being remade.** It must survive the folder swap (Task 4 test `a_change_during_the_remake_is_kept`).
4. **A setup that no longer matches the published timetable** (a group code or class that has no lessons there, a duplicated ID, a blank row): the published record is left exactly as it was (Task 1 tests `each_reason_leaves_the_record_alone`).
5. **A timetable of two weeks, a group with no size, a student in a group outside their class, an optional band**: the screen's working-out must not throw and must count and mark as the spec says (Task 6 tests of those names).

---

## File Structure

| File | Responsibility |
|---|---|
| `students.py` (new) | Students on the published timetable: who can follow, the update after a save, the whole-list update, the status, the skeleton for the screen, the files thread. |
| `store.py` | `apply_changes(…, told=)`; `swap_model`; `remake_files`. |
| `app.py` | Calls `students.follow` after student changes; three committee routes; `pub_info` carries `files_behind`; starts `students.resume_files()`. |
| `history.py`, `static/history.js` | The new kind `students-published`. |
| `static/studentview.js` (new) | Pure working-out for the screen. |
| `static/app.js`, `static/style.css`, `static/index.html` | The screen, the status line, the changed questions. |
| `tests/test_students.py` (new), `tests/studentview.test.js` (new), `tests/test_routes.py` | Tests. |
| `docs/superpowers/plans/2026-11-24-student-groups-notes.md` (new) | Rulings, known limits, what was not tried. |

### The test fixture (Tasks 1 to 5 share it, at the top of `tests/test_students.py`)

Header as `tests/test_board.py` lines 1 to 40 (scratch `DATA_DIR`, random codes, `c` signed in as committee, `NOSE` never signed in, `raises`, `workbook(rows)`, `setup_bytes(spec)`), plus `import access, history, putback, students` and `from ttgen import export as E`. Personal codes need `SECRET_KEY`, which the header sets (see `access.personal_codes_on`). Then:

```python
assert c.put("/api/setup", json=A.sample("primary")).status_code == 200
SPEC = c.get("/api/setup").get_json()["spec"]
LEVEL = SPEC["classes"][0]["level"]
CA, CB = [x["class"] for x in SPEC["classes"] if x["level"] == LEVEL][:2]
DAYS = list(SPEC["day_structure"][LEVEL].keys())
L1 = SPEC["day_structure"][LEVEL][DAYS[0]].index("L")
SUBJ, SUBJ2 = SPEC["subjects"][0]["subject"], SPEC["subjects"][1]["subject"]
T1, T2 = [x["name"] for x in SPEC["teachers"]][:2]
R1, R2 = [v["room"] for v in SPEC["venues"] if (v.get("kind") or "classroom") == "classroom"][:2]
ROWS = [   # Band A: GA1 and GA2 at the same time; GB1 alone; GX at Band A's time (a clash with either)
    dict(id=1, day=DAYS[0], p=L1, n=1, level=LEVEL, classes=[CA], subject=SUBJ, teachers=[T1], room=R1),
    dict(id=2, day=DAYS[1], p=L1, n=2, level=LEVEL, block="Band A", classes=[CA, CB], subject=SUBJ, group="GA1", teachers=[T1], room=R1),
    dict(id=2, day=DAYS[1], p=L1, n=2, level=LEVEL, block="Band A", classes=[CA, CB], subject=SUBJ2, group="GA2", teachers=[T2], room=R2),
    dict(id=3, day=DAYS[2], p=L1, n=1, level=LEVEL, classes=[CA, CB], subject=SUBJ2, group="GB1", teachers=[T2], room=R2),
    dict(id=4, day=DAYS[1], p=L1, n=1, level=LEVEL, classes=[CA, CB], subject=SUBJ2, group="GX", teachers=[T2], room=R2),
]
PEOPLE = [dict(id="S001", name="Aisha Rahman", **{"class": CA}, groups=["GA1", "GB1"]),
          dict(id="S002", name="Ben Koh", **{"class": CB}, groups=["GA2"]),
          dict(id="S003", name="Chen Li", **{"class": CA}, groups=[])]

def set_students(rows):      # the setup's list becomes rows, by a whole replacement (publishes nothing)
def publish():               # store.publish(setup workbook of the setup now, workbook(ROWS), spec=the setup now); returns store.published()
def change(*ops):            # c.post("/api/setup/changes", json=dict(since=<v now>, client="t", ops=list(ops))) -> its JSON
def row_id(sid):             # the _id of the setup row whose id is sid
def pub_student(sid):        # the published record with that id, or None
def fresh(people=PEOPLE):    # set_students(people); publish()
```

`set_students` uses `c.put("/api/setup", json=…)` with the students replaced. `change` reads `v` from `c.get("/api/setup").get_json()["v"]`.

---

### Task 1: The update after a save (`students.follow`)

**Files:**
- Create: `students.py`
- Modify: `store.py` (`apply_changes` near line 166, a new `swap_model` after `publish`)
- Test: `tests/test_students.py` (create, with the fixture above)

**Interfaces:**
- Produces, `store.py`:
  - `apply_changes(ops, client, check=None, since=None, filter=None, by=None, tag=None, told=None)`. When `told` is a dict and operations were applied it sets `told["batch"]` (the batch id, `str`) and `told["students"]`: a list of `(before, after)`, one pair per distinct student row `_id` named by an applied operation whose section is `"students"`; `before` is a deep copy of the row in the setup before the operations (`None` for an added row), `after` a deep copy after them (`None` for a deleted row). `[]` when no student row was named. The return value is unchanged.
  - `swap_model(model, **meta) -> None`. The caller holds `store._publishing`. Writes `PUB/model.pkl` through a temporary file and `os.replace`, then `meta.json` as it is with `meta` laid over it, then clears `_cache` under `_lock`. `FileNotFoundError` when nothing is published.
- Produces, `students.py`:
  - `KIND = "students-published"`
  - `key(row) -> str`: `str(row.get("id") or row.get("name") or "").strip()`
  - `record(row) -> dict`: exactly what `ttgen/export.py` `_model` (lines 120 to 121) makes of one setup row: `dict(id=str(id or name), name=str(name or id), cls=str(class or ""), level=str(level or ""), groups=[str(g) …])`.
  - `why_not(row, model, counts) -> str | None`: `counts` maps `key` to how many setup rows have it. The first that applies, word for word: `"no student ID or name"`; `"this ID is on the list twice"`; `f"class {cls} is not on the published timetable"`; `f"group {g} is not on the published timetable"` (several: `f"groups {a}, {b} are not on the published timetable"`). A class is on it when in `model["class_ix"]`; a group when some lesson in `model["lessons"]` has that `group`.
  - `touched(pairs) -> (keys: list[str], may_remove: set[str], held: int)`: `keys` = the keys of every `after`; `may_remove` = the old key of a pair whose key changed (`follow` removes it only when that row's new key was updated or added in the same update, so a mistyped ID never takes a student off), plus the key of the deleted row **only when exactly one pair has `after is None`**; `held` = the number of deleted rows when more than one, else 0.
  - `follow(pairs, by, batch=None) -> dict | None`: `None` when nothing is published. Under `store._publishing`: reads the setup **now** (`store.setup_record()`) and the published model; for each key in `keys` and `may_remove`: on the list now and `why_not` is `None` → the published record becomes `record(row)` (**updated**, or **added** when absent); on the list now with a reason → nothing, listed in **left**; not on the list now and in `may_remove` and published → **removed**; else nothing. When any record changes: builds a new model (a shallow copy with a new `students` list; `setup` and, when it is a different object, `checked_setup` replaced by shallow copies whose `students` rows for the touched keys are deep copies of the setup's rows now, added or dropped to match), sets `checks` to `ttgen.export.check_model(new)` with `choice_problems` appended to `problems` and `ok` recomputed as `model_from_files` does (lines 292 to 293), and calls `store.swap_model(new, students=len(new["students"]), ok=…, problems=checks["problems"][:20], students_at=store.now(), files_behind=True)`. Writes one history entry `dict(kind=KIND, text=…, where="Students", of=batch, **by)` when anything was updated, added, removed, left or held. Returns `dict(updated=[ids], added=[ids], removed=[ids], left=[dict(id=, name=, why=)], held=int, text=str)`.
  - The history `text` (also returned as `text`), sentences joined by one space, in this order, each only when it applies:
    - one updated or added: `f"Published timetable updated for {name} ({id})."`; more: `f"Published timetable updated for {n} students."`
    - one removed: `f"{name} ({id}) removed from the published timetable."`; more: `f"{n} students removed from the published timetable."`
    - one left: `f"Published timetable not changed for {name} ({id}): {why}."`; more: `f"Published timetable not changed for {n} students: their groups or classes are not on it."`
    - held: `f"{held} students stay on the published timetable until Update the published timetable is pressed."`

- [ ] **Step 1: Write the failing tests** in `tests/test_students.py`, each a function decorated or listed the way `tests/test_board.py` runs its tests, ending with the suite's usual count line:

```python
def a_group_swap_changes_one_record_and_nothing_else():
    fresh(); before = store.published(); m0, meta0 = before["model"], dict(before["meta"])
    j = change(["merge", "students", row_id("S001"), "groups", ["GA2"], ["GA1"]])
    m1 = store.published()["model"]; meta1 = store.published()["meta"]
    assert sorted(pub_student("S001")["groups"]) == ["GA2", "GB1"]
    assert [s for s in m1["students"] if s["id"] != "S001"] == [s for s in m0["students"] if s["id"] != "S001"]
    for k in m0:                                   # every other key of the model is equal
        if k not in ("students", "setup", "checked_setup", "checks"): assert m1[k] == m0[k], k
    assert meta1["published_at"] == meta0["published_at"] and meta1["students_at"] and meta1["files_behind"] is True
    assert m0["students"] is not m1["students"] and pub_student("S001") not in m0["students"]   # the old model was not changed in place

def it_equals_a_full_publish_of_the_same_setup():
    fresh(); change(["merge", "students", row_id("S001"), "groups", ["GA2"], ["GA1"]], ["set", "students", row_id("S002"), "name", "Ben K"])
    got = sorted(store.published()["model"]["students"], key=lambda s: s["id"]); publish()
    assert got == sorted(store.published()["model"]["students"], key=lambda s: s["id"])

def a_new_student_is_added_and_their_code_signs_in():
    fresh(); change(["add", "students", dict(_id="newrow0001", id="S004", name="Devi Nair", **{"class": CB}, groups=["GA1"]), ""])
    assert pub_student("S004") == dict(id="S004", name="Devi Nair", cls=CB, level="", groups=["GA1"])
    assert access.norm(access.personal_code("S004")) in store.published()["codes"]

def one_deleted_student_is_removed_and_their_code_stops():
    fresh(); change(["del", "students", row_id("S003")])
    assert pub_student("S003") is None and access.norm(access.personal_code("S003")) not in store.published()["codes"]

def a_save_that_deletes_several_removes_nobody():
    fresh(); j = change(["del", "students", row_id("S002")], ["del", "students", row_id("S003")])
    assert pub_student("S002") and pub_student("S003") and j["students"]["outcome"]["held"] == 2   # the reply key is Task 2's; until then assert on students.follow's return

def a_changed_id_removes_the_old_and_adds_the_new():
    fresh(); change(["set", "students", row_id("S003"), "id", "S033"])
    assert pub_student("S003") is None and pub_student("S033")["name"] == "Chen Li"

def an_id_changed_to_one_already_taken_removes_nobody():
    fresh(); change(["set", "students", row_id("S003"), "id", "S001"])
    assert pub_student("S003")["name"] == "Chen Li" and pub_student("S001")["name"] == "Aisha Rahman"

def each_reason_leaves_the_record_alone():
    for ops, why in ((lambda: [["merge", "students", row_id("S001"), "groups", ["NOPE"], []]], "group NOPE is not on the published timetable"),
                     (lambda: [["set", "students", row_id("S001"), "class", "9Z"]], "class 9Z is not on the published timetable"),
                     (lambda: [["set", "students", row_id("S003"), "id", "S001"], ["set", "students", row_id("S001"), "name", "A R"]], "this ID is on the list twice")):
        fresh(); was = pub_student("S001"); change(*ops())
        assert pub_student("S001") == was
        # and students.follow's outcome lists S001 in left with exactly `why`

def a_blank_row_is_never_published():
    fresh(); change(["add", "students", dict(_id="blankrow01"), ""]); assert pub_student("None") is None and len(store.published()["model"]["students"]) == 3

def a_whole_replacement_updates_nothing():
    fresh(); set_students(PEOPLE[:1]); assert len(store.published()["model"]["students"]) == 3 and "students_at" not in store.published()["meta"]

def the_update_reads_the_setup_as_it_is_now():
    fresh(); pairs = [(dict(_id=row_id("S001"), id="S001", name="Aisha Rahman", **{"class": CA}, groups=["GA1", "GB1"]),
                       dict(_id=row_id("S001"), id="S001", name="Aisha Rahman", **{"class": CA}, groups=["GA2"]))]   # a stale request
    store.apply_changes([["set", "students", row_id("S001"), "name", "Aisha R"]], "t2")                          # a later save, not followed yet
    students.follow(pairs, history.by_of("Tester", "password")); assert pub_student("S001")["name"] == "Aisha R" and "GA1" in pub_student("S001")["groups"]

def a_saved_clash_shows_in_the_checks():
    fresh(); change(["merge", "students", row_id("S001"), "groups", ["GX"], []])
    assert store.published()["meta"]["ok"] is False and any("students have two lessons at the same time" in p for p in store.published()["meta"]["problems"])

def nothing_published_is_no_error():
    shutil.rmtree(store.PUB, ignore_errors=True); store._cache.update(stamp=None, value=None)
    assert students.follow([(None, dict(id="S009", name="X Y"))], history.by_of("Tester", "password")) is None

def told_names_the_student_rows():
    fresh(); told = {}; store.apply_changes([["set", "students", row_id("S002"), "name", "Ben K"], ["set", "classes", SPEC["classes"][0]["_id"], "size", 31]], "t", told=told)
    assert told["batch"].startswith("b") and [(b["name"], a["name"]) for b, a in told["students"]] == [("Ben Koh", "Ben K")]
```

Until Task 2 wires the route, `change` in this task calls `store.apply_changes(ops, "t", told=told, by=…)` then `students.follow(told["students"], by, told["batch"])` and returns `{"students": {"outcome": …}}`; Task 2 switches it to the route and every test above must still pass unchanged.

- [ ] **Step 2: Run** `$PY tests/test_students.py`. Expected: fails at `import students`.
- [ ] **Step 3: Implement** `told` in `store.apply_changes` (collect the `_id`s from the applied `ops` whose `op[1] == "students"`: `op[2]` for `set`/`merge`/`del`, `op[2]["_id"]` for `add`; `before` rows from a deep copy taken before `sync.apply`), `store.swap_model`, and `students.py` as the Interfaces say.
- [ ] **Step 4: Run** `$PY tests/test_students.py`, then `$PY tests/test_sync.py`, `$PY tests/test_history.py`, `$PY tests/test_putback.py`, `$PY tests/test_board.py`. Expected: all pass.
- [ ] **Step 5: Commit** `feat(students): a saved student follows onto the published timetable`.

---

### Task 2: Wire it in, and the History line

**Files:**
- Modify: `app.py` (`post_setup_changes` near line 754, `history_back` near line 2154), `history.py`, `static/history.js`
- Test: `tests/test_students.py`, `tests/test_history.py` (only if a kinds list there must name the new kind)

**Interfaces:**
- Consumes: `store.apply_changes(…, told=)`, `students.follow`, `students.KIND`.
- Produces: `POST /api/setup/changes` answers with `"students": {"outcome": <follow's dict>}` when the save named student rows and a timetable is published; `{"students": {"error": "The published timetable was not updated. Press Update the published timetable on the Students step."}}` when `follow` raised (the save itself still succeeds; the exception type is printed to stderr as `store._warn` does). Task 3 adds `"status"` beside `"outcome"`.

- [ ] **Step 1: Write the failing tests**

```python
def the_route_follows_and_says_what_happened():
    fresh(); j = change(["merge", "students", row_id("S001"), "groups", ["GA2"], ["GA1"]])   # change() now posts to /api/setup/changes
    assert j["students"]["outcome"]["updated"] == ["S001"] and j["students"]["outcome"]["text"] == "Published timetable updated for Aisha Rahman (S001)."

def a_save_of_other_rows_says_nothing_about_students():
    fresh(); assert "students" not in change(["set", "classes", SPEC["classes"][0]["_id"], "size", 33])

def a_failure_does_not_fail_the_save():
    fresh(); real = students.follow; students.follow = lambda *a, **k: 1 / 0
    try: j = change(["set", "students", row_id("S002"), "name", "Ben K"])
    finally: students.follow = real
    assert j["students"] == {"error": "The published timetable was not updated. Press Update the published timetable on the Students step."}
    assert next(s for s in c.get("/api/setup").get_json()["spec"]["students"] if s["id"] == "S002")["name"] == "Ben K"

def history_has_its_own_line_and_put_back_follows():
    fresh(); change(["merge", "students", row_id("S001"), "groups", ["GA2"], ["GA1"]])
    es = history.read(limit=20); line = next(e for e in es if e["kind"] == students.KIND); setup = next(e for e in es if e["kind"] == "setup")
    assert line["text"] == "Published timetable updated for Aisha Rahman (S001)." and line["of"] == setup["batch"] and line["where"] == "Students"
    assert putback.unit_of(line) is None                                    # it cannot be put back
    assert c.post("/api/history/back", json=dict(id=setup["id"])).get_json() == {"done": True, "text": "Put back."}
    assert sorted(pub_student("S001")["groups"]) == ["GA1", "GB1"]            # the published timetable followed the put back
    assert sum(1 for e in history.read(limit=20) if e["kind"] == students.KIND) == 2
    assert all(e["kind"] != students.KIND for e in putback.gather(setup["id"])[1])   # not part of the save's unit
```

- [ ] **Step 2: Run** `$PY tests/test_students.py`. Expected: the four new tests fail.
- [ ] **Step 3: Implement.** In `post_setup_changes` pass `told={}` and, when `told.get("students")`, call `students.follow(told["students"], by(), told.get("batch"))` inside `try/except Exception`. In `history_back` do the same after `store.apply_changes` (nothing added to its answer). In `history.py` make sure the new kind is read, filtered by `where="Students"` and never treated as a setup change that can be put back; in `static/history.js` show it as a plain line with the link the Students entries get. Check how `history.read`, `history.summary` (`CHANGE_KINDS`) and `putback.TOUCH_KINDS` treat an unknown kind and add the kind only where a list would otherwise hide it from the History page.
- [ ] **Step 4: Run** `$PY tests/test_students.py`, `$PY tests/test_history.py`, `$PY tests/test_putback.py`, `$PY tests/test_routes.py`, `node tests/history.test.js`. Expected: all pass.
- [ ] **Step 5: Commit** `feat(students): the setup save updates the published timetable and History says so`.

---

### Task 3: The status and "Update the published timetable"

**Files:**
- Modify: `students.py`, `app.py`, `tests/test_routes.py` (`GUARDS`)
- Test: `tests/test_students.py`

**Interfaces:**
- Produces, `students.py`:
  - `status() -> dict`: `dict(published=False)` when nothing is published, else `dict(published=True, at=<published_at>, students=<on the published timetable>, listed=<on the list>, same=int, differ=[dict(id=, name=, why=, kind=)] (the first 10), differ_n=int, counts=dict(change=int, add=int, remove=int), can_update=bool, files_behind=bool)`. `kind` and `why`: `"left"` with `why_not`'s sentence; `"waiting"` with `"not updated yet"` (can follow, and the published record is absent or different); `"extra"` with `"on the published timetable but not on this list"`. `counts`: `change` = waiting and published, `add` = waiting and absent, `remove` = extra. `can_update` = any count above 0. Order of `differ`: left, waiting, extra, each in list order.
  - `update_all(by) -> dict | None`: under `store._publishing`, every listed student who can follow is updated or added, every extra is removed, students who cannot follow are left; one `swap_model`; one history entry of `KIND` with `text` = `f"Published timetable brought into step with the list: {change} changed, {add} added, {remove} removed."`; returns `follow`'s shape. Nothing written and no entry when the three counts are 0.
- Produces, `app.py` (all `@need("committee")`):
  - `GET /api/students/published` (endpoint `students_published`) → `students.status()`
  - `POST /api/students/update` (endpoint `students_update`) → `{"outcome": …, "status": students.status()}`; 409 `{"error": "No timetable is published yet."}`
  - `POST /api/setup/changes` now answers `"students": {"outcome": …, "status": students.status()}`.

- [ ] **Step 1: Write the failing tests**

```python
def the_status_when_all_agree():
    fresh(); s = students.status()
    assert (s["published"], s["students"], s["listed"], s["same"], s["differ"], s["can_update"]) == (True, 3, 3, 3, [], False)

def the_status_names_each_kind():
    fresh(); set_students([PEOPLE[0] | dict(groups=["GA2"]), PEOPLE[1] | dict(groups=["NOPE"]), dict(id="S004", name="Devi Nair", **{"class": CB}, groups=[])])
    s = students.status()
    assert [(d["id"], d["kind"], d["why"]) for d in s["differ"]] == [("S002", "left", "group NOPE is not on the published timetable"), ("S001", "waiting", "not updated yet"),
                                                                    ("S004", "waiting", "not updated yet"), ("S003", "extra", "on the published timetable but not on this list")]
    assert s["counts"] == dict(change=1, add=1, remove=1) and s["can_update"] is True and s["same"] == 0

def update_all_brings_the_list_into_step():
    fresh(); set_students([PEOPLE[0] | dict(groups=["GA2"]), PEOPLE[1] | dict(groups=["NOPE"]), dict(id="S004", name="Devi Nair", **{"class": CB}, groups=[])])
    r = c.post("/api/students/update").get_json()
    assert r["outcome"]["text"] == "Published timetable brought into step with the list: 1 changed, 1 added, 1 removed."
    assert pub_student("S001")["groups"] == ["GA2"] and pub_student("S004") and pub_student("S003") is None and pub_student("S002")["groups"] == ["GA2"]   # S002 left as published
    assert r["status"]["counts"] == dict(change=0, add=0, remove=0) and [d["kind"] for d in r["status"]["differ"]] == ["left"]
    n = len(history.read(limit=50)); c.post("/api/students/update"); assert len(history.read(limit=50)) == n   # nothing to do: nothing written

def the_routes_are_the_committees():
    for url, post in (("/api/students/published", False), ("/api/students/update", True)):
        r = (NOSE.post if post else NOSE.get)(url); assert r.status_code == 401, url
    # a head, a teacher and a student are refused: tests/test_routes.py's walk covers them once GUARDS lists the endpoints

def with_nothing_published():
    shutil.rmtree(store.PUB, ignore_errors=True); store._cache.update(stamp=None, value=None)
    assert students.status() == dict(published=False) and c.post("/api/students/update").status_code == 409
```

- [ ] **Step 2: Run** `$PY tests/test_students.py`. Expected: the new tests fail.
- [ ] **Step 3: Implement** `status`, `update_all` and the two routes; add `"students_published": ('committee',)` and `"students_update": ('committee',)` to `GUARDS` in `tests/test_routes.py`.
- [ ] **Step 4: Run** `$PY tests/test_students.py`, `$PY tests/test_routes.py`. Expected: pass.
- [ ] **Step 5: Commit** `feat(students): the list compared with the published timetable, and one button to bring it into step`.

---

### Task 4: The files to download

**Files:**
- Modify: `store.py` (`remake_files`), `students.py` (the thread), `app.py` (`pub_info` near line 1376 gains `files_behind`; call `students.resume_files()` once where the app starts its other background work)
- Test: `tests/test_students.py`

**Interfaces:**
- Consumes: `store.swap_model` sets `files_behind=True` and `students_at`.
- Produces:
  - `store.remake_files() -> bool | None`: `None` when nothing is published. Reads `published_at` and `students_at` and loads **its own** copy of the model from `PUB/model.pkl`; runs `export_all` into a fresh folder beside `PUB` with **no lock held**; then under `_publishing`: if `published_at` changed meanwhile, deletes its folder and returns `True` (a publish made its own files); else copies the **current** `model.pkl`, `setup.xlsx` and `timetable.*` from `PUB` into its folder, removes the single-PDF folders as `publish` does (lines 293 to 294), writes `meta.json` = the current meta with the new `files`, `files_at=now()` and `files_behind = (current students_at != the one read at the start)`, swaps the folder in as `publish` does (lines 305 to 310), and returns `not files_behind`.
  - `students.FILES_WAIT = 60` (seconds); `students.schedule_files() -> None` (called by `follow` and `update_all` after a write: sets the time of the last change and starts the one daemon thread if none is alive; the thread waits until `FILES_WAIT` seconds have passed since the last change, calls `store.remake_files()`, and repeats while that returns `False`; it sleeps at most 0.2 seconds at a time and reads `FILES_WAIT` each time, so a test that lowers it is obeyed at once); `students.files_now() -> bool | None` (calls `store.remake_files()` directly, for tests); `students.resume_files() -> None` (schedules when the published meta has `files_behind`).
  - `pub_info()["files_behind"]: bool`.

- [ ] **Step 1: Write the failing tests**

```python
def the_files_are_remade_and_carry_the_change():
    fresh(); students.FILES_WAIT = 3600; change(["set", "students", row_id("S002"), "name", "Ben K"])
    meta = store.published()["meta"]; assert meta["files_behind"] is True and c.get("/api/published").get_json()["files_behind"] is True   # use the route pub_info serves; find it by grep "pub_info()"
    old = os.path.getmtime(os.path.join(store.PUB, meta["files"]["excel"])); time.sleep(1.1)
    assert students.files_now() is True
    meta2 = store.published()["meta"]
    assert meta2["files_behind"] is False and meta2["files_at"] and meta2["published_at"] == meta["published_at"]
    assert os.path.getmtime(os.path.join(store.PUB, meta2["files"]["excel"])) > old and pub_student("S002")["name"] == "Ben K"
    wb = openpyxl.load_workbook(os.path.join(store.PUB, meta2["files"]["excel"]), read_only=True)
    assert any("Ben K" in str(v) for row in wb["Students"].iter_rows(values_only=True) for v in row if v)
    for f in ("setup.xlsx", "model.pkl", "meta.json"): assert os.path.exists(os.path.join(store.PUB, f)), f
    assert not os.path.isdir(os.path.join(store.PUB, "PDF", "Students"))

def a_change_during_the_remake_is_kept():
    fresh(); students.FILES_WAIT = 3600; change(["set", "students", row_id("S002"), "name", "Ben K"])
    from ttgen import export as E; real = E.export_all
    def slow(m, out, **kw):                      # a student change lands while the files are being written
        r = real(m, out, **kw); change(["set", "students", row_id("S003"), "name", "Chen L"]); return r
    store.export_all = slow                      # patch the name store.remake_files calls
    try: assert students.files_now() is False
    finally: store.export_all = real
    assert pub_student("S003")["name"] == "Chen L" and store.published()["meta"]["files_behind"] is True
    assert students.files_now() is True and store.published()["meta"]["files_behind"] is False

def a_publish_during_the_remake_wins():
    fresh(); students.FILES_WAIT = 3600; change(["set", "students", row_id("S002"), "name", "Ben K"])
    from ttgen import export as E; real = E.export_all; seen = {}
    def slow(m, out, **kw):
        r = real(m, out, **kw)
        if not seen: seen["x"] = 1; time.sleep(1.1); store.export_all = real; publish(); store.export_all = slow
        return r
    store.export_all = slow
    try: assert students.files_now() is True
    finally: store.export_all = real
    assert "files_behind" not in store.published()["meta"] or store.published()["meta"]["files_behind"] is False

def the_thread_runs_after_the_wait_and_after_a_restart():
    fresh(); students.FILES_WAIT = 0; change(["set", "students", row_id("S002"), "name", "Ben K"])
    deadline = time.time() + 60
    while store.published()["meta"].get("files_behind") and time.time() < deadline: time.sleep(0.2)
    assert store.published()["meta"]["files_behind"] is False
    store.swap_model(store.published()["model"], files_behind=True)            # as a restart finds it
    students.resume_files(); deadline = time.time() + 60
    while store.published()["meta"].get("files_behind") and time.time() < deadline: time.sleep(0.2)
    assert store.published()["meta"]["files_behind"] is False
```

`store.swap_model` is called there outside `_publishing` on purpose: take the lock in the test (`with store._publishing:`).

- [ ] **Step 2: Run** `$PY tests/test_students.py`. Expected: the new tests fail.
- [ ] **Step 3: Implement.** `store.py` must call `export_all` through a module-level name the tests can patch (`from ttgen.export import export_all` is already how `publish` gets it: keep one name, `store.export_all`). Set `students.FILES_WAIT = 3600` at the top of `tests/test_students.py` so no earlier test starts a remake; the thread test sets 0 itself.
- [ ] **Step 4: Run** `$PY tests/test_students.py` (expected: pass, well under two minutes), `$PY tests/test_routes.py`, `$PY tests/test_signin.py`, `$PY tests/test_exams.py`.
- [ ] **Step 5: Commit** `feat(students): the download files are remade in the background after a student change`.

---

### Task 5: The skeleton for the screen, and exams

**Files:**
- Modify: `students.py`, `app.py`, `tests/test_routes.py` (`GUARDS`)
- Test: `tests/test_students.py`

**Interfaces:**
- Produces: `students.skeleton() -> dict | None`:

```python
dict(stamp=<published_at>, days=m["days"], NP=m["NP"], times=m["times"],
     classes={name: dict(level=str, codes=<the list student_view passes as codes: m["cgrid"].get(name) or ttgen.export._codes_for(m, [level])>,
                         whole=[[d, p, n, short, room], ...])},          # the class's whole-class lessons, short = ttgen.export.abbrev(subject)
     groups={code: dict(subject=str, short=str, band=<block or "">, classes=[sorted], teachers=[in order met], rooms=[in order met, no blanks],
                        seats=<the room's capacity as int when every lesson of the group is in one room and that capacity is a whole number above 0, else None>,
                        slots=[[d, p, n], ...])})                        # one entry per lesson of the group, sorted
```

  `GET /api/students/skeleton` (endpoint `students_skeleton`, `@need("committee")`) → it, gzip as `/api/draft/board` answers when the client accepts it; 404 `{"error": "No timetable is published yet."}`.

- [ ] **Step 1: Write the failing tests**

```python
def the_skeleton_holds_what_the_screen_needs():
    fresh(); k = c.get("/api/students/skeleton").get_json(); m = store.published()["model"]
    assert k["stamp"] == store.published()["meta"]["published_at"] and k["days"] == m["days"] and k["NP"] == m["NP"]
    d1, d2 = m["days"].index(DAYS[1]), m["days"].index(DAYS[2])
    assert k["groups"]["GA1"] == dict(subject=SUBJ, short=E.abbrev(SUBJ), band="Band A", classes=sorted([CA, CB]), teachers=[T1], rooms=[R1], seats=k["groups"]["GA1"]["seats"], slots=[[d1, L1, 2]])
    assert k["groups"]["GB1"]["slots"] == [[d2, L1, 1]] and k["groups"]["GX"]["band"] == ""
    assert k["classes"][CA]["whole"] == [[m["days"].index(DAYS[0]), L1, 1, E.abbrev(SUBJ), R1]] and k["classes"][CB]["whole"] == []
    assert len(k["classes"][CA]["codes"]) == len(m["days"])
    assert NOSE.get("/api/students/skeleton").status_code == 401

def the_skeleton_has_no_student_in_it():
    fresh(); raw = c.get("/api/students/skeleton").get_data(as_text=True)
    assert "Aisha" not in raw and "S001" not in raw

def a_made_exam_goes_stale_after_a_group_change():
    # build the smallest schedule exams.make.fingerprint accepts with one paper sat by group GA1 (exams/papers.py who_sits reads the paper; tests/test_exams.py has the shapes),
    # take fingerprint(sched, xset, model) before and after change(["merge","students",row_id("S001"),"groups",["GA2"],["GA1"]]) and assert they differ;
    # and assert exams.make.published_at(store.published()) is the same before and after
```

- [ ] **Step 2: Run** `$PY tests/test_students.py`. Expected: the new tests fail.
- [ ] **Step 3: Implement** `skeleton` and the route; add `"students_skeleton": ('committee',)` to `GUARDS`.
- [ ] **Step 4: Run** `$PY tests/test_students.py`, `$PY tests/test_routes.py`. Expected: pass.
- [ ] **Step 5: Commit** `feat(students): the published timetable's skeleton for the student screen`.

---

### Task 6: `static/studentview.js`, the working-out

**Files:**
- Create: `static/studentview.js`, `tests/studentview.test.js`
- Modify: `static/index.html` (a `<script src="/static/studentview.js">` line before `app.js`, beside the other view modules)

**Interfaces:**
- Consumes: the skeleton of Task 5; the setup `spec`; `codes`, an array with the group code of each `spec.lessons` row (`""` or `"Entire Class"` for none), which `static/app.js` gets from `lessonInfo()`.
- Produces `var StudentView = (function () { … })(); if (typeof module !== "undefined") module.exports = StudentView;`, pure functions, no page access, written in the style of `static/groups.js`:
  - `EXEMPT = "exempt"`, `NONE = ""`
  - `counts(spec) -> {code: n}`: students on the list per group code.
  - `bands(spec, codes, cls) -> {bands: [{band, everyone, groups: [{code, subject, size}]}], other: [{code, subject, size}]}` from step 5 for one class: a lessons row counts when its `classes` include `cls` and it has a code; `band` = its `block`; `everyone` = the band's `blocks[].everyone`, or when that is absent `!/option|elective/i.test(band)` (the rule `everyone()` in `static/app.js` line 2104); `size` = `Number(row.students) || null`. Bands in the order of `spec.blocks`, then any others in row order.
  - `open(spec, codes, student) -> picks`: `{cls, band: {<band>: code | NONE}, other: [codes], was: [the student's groups]}`; a group of the student's that is no group of the class goes to `other`.
  - `groupsOf(picks) -> [codes]`: the band picks that are codes, then `other`.
  - `week(skel, cls, groups) -> [{d, p, n, short, room, code}]`: the class's whole-class lessons (`code: ""`) and the slots of each group that the skeleton has.
  - `clashes(skel, cls, groups) -> [{d, p, a, b}]`: every period two of those lessons share, `a` and `b` the codes (`""` for a whole-class lesson), each pair once.
  - `view(spec, codes, skel, student, picks, exempt) -> model`, where `skel` may be `null` and `exempt` is `{<band>: true}` for bands the Note exempts the student from. The model:

```js
{ bands: [{ band, everyone, pick,                         // pick: a code, NONE or EXEMPT
            options: [{ code, subject, teacher, room, n, size, full, over, clash, on, was, off }] }],
  other:  [{ code, subject, teacher, room, n, size, full, over, clash, on, was, off, why }],   // why: "not a group of class 3B" | "not on step 5" | ""
  cells:  [{ d, p, n, short, room, code, state }],        // state: "same" | "new" | "gone" | "clash"
  summary: "…", asks: ["…"], changed: true|false }
```

    - `n`: the count **as it will be after Save** (the list's count, minus one for a group the student leaves, plus one for a group they join). `size`: the step 5 number, else the skeleton's `seats`, else `null`. `full`: not `on` and `size` and `n >= size`. `over`: `on` and `size` and `n > size`.
    - `clash`: for an option not `on`, the sentence it would cause against the lessons the student would still have with it picked (the band's own other pick left out): `"Clashes: Tue period 4, with 3EL2 English"`; day = the skeleton's day name, period = `p + 1`, the other lesson as `code + " " + subject`, or the whole-class lesson's `short`. `""` when none. For an option that is `on`, the same sentence when it clashes now.
    - `off`: `true` when `skel` is given and has no such group (`"not on the published timetable"`).
    - Order of a band's options: subjects in the order first met in `skel.groups` (insertion order; step 5 order when `skel` is null), then most room first (`size - n`, unknown size last), then by code.
    - `cells`: `week` of the picks, plus the lessons of groups in `was` that are no longer picked as `"gone"`; lessons of newly picked groups are `"new"`; any cell that shares a period with another kept or new lesson is `"clash"`. Empty when `skel` is null.
    - `summary`: `"Moves from 3HIS1 History to 3GEO2 Geography."` for one group left and one joined in the same band; `"Joins 3GEO2 Geography."`; `"Leaves 3HIS1 History."`; several joined with spaces; then `"4 lessons change."` (new plus gone cells; `"1 lesson changes."`); then `"No clash."` or `"1 clash."` / `"2 clashes."` (clash sentences among the picks). `"Nothing changed."` when `changed` is false.
    - `asks`, in this order: one per clash among the picks (`"3BIO2 clashes on Tue period 4 with 3EL2 English."`); one per `everyone` band with pick `NONE` and not exempt (`"No Humanities group is chosen."`, the band's name as it is); one per picked group that is `off` (`"3XYZ is not on the published timetable, so the published timetable will not change for this student until the next publish."`).
  - `apply(student, picks) -> {groups}`: the student's new `groups` (order: the old groups kept in their order, then the new ones).

- [ ] **Step 1: Write the failing tests** in `tests/studentview.test.js` (header and `t(name, f)` as `tests/groups.test.js`), with one made-up fixture: class `3B` (and `3C`), bands `Sec 3 English` (`3EL1` size 30, `3EL2` size 30), `Sec 3 Humanities` (`3HIS1` History, `3GEO1` and `3GEO2` Geography), `Sec 3 Option A` (`everyone: false`, `3ART1`), one group outside a band (`3CCA1`), a skeleton of five days and eight periods where `3BIO2`-style clash exists (`3GEO1` at the same time as `3EL2`), and six made-up students. Tests, each asserting exact values:
  - `counts_per_group`, `bands_for_a_class_in_step_5_order`, `an_optional_band_is_marked` (`everyone === false`)
  - `open_puts_a_group_outside_the_class_under_other` (`why === "not a group of class 3B"`), `a_group_no_longer_on_step_5_stays_ticked` (`why === "not on step 5"`)
  - `the_count_is_as_it_will_be_after_save` (leave `3HIS1`, join `3GEO2`: `3HIS1.n` one lower, `3GEO2.n` one higher)
  - `full_and_over` (a size reached by others → `full`; the student's own group above size → `over`), `a_group_with_no_size_is_never_full` (step 5 blank and `seats: null` → `size === null`, `full === false`), `seats_stand_in_for_a_blank_size`
  - `a_clash_is_named` (`"Clashes: Tue period 4, with 3EL2 English"`), `two_groups_of_one_band_do_not_clash_as_options`
  - `the_week_marks_new_gone_and_clash`, `summary_for_a_swap` (`"Moves from 3HIS1 History to 3GEO2 Geography. 4 lessons change. No clash."`), `summary_when_nothing_changed`
  - `asks_for_a_clash_a_missing_band_and_a_group_off_the_timetable`, `an_exempt_band_asks_nothing`
  - `most_room_first_within_a_subject`
  - `a_two_week_timetable` (days `Odd Mon … Even Fri`: `view` returns cells with `d` up to 9 and does not throw)
  - `with_no_skeleton` (`cells` empty, options have `teacher === ""`, counts and band asks still right)
  - `a_new_student_with_no_class` (`bands` empty, no throw), `apply_keeps_old_order_then_new`
- [ ] **Step 2: Run** `node tests/studentview.test.js`. Expected: fails on `require`.
- [ ] **Step 3: Implement** `static/studentview.js`; add the script line to `static/index.html`.
- [ ] **Step 4: Run** `node tests/studentview.test.js`. Expected: `ok` with the count of tests.
- [ ] **Step 5: Commit** `feat(students): the working-out for one student's screen`.

---

### Task 7: The screen on the Students step

**Files:**
- Modify: `static/app.js` (`students() {` near line 1723, the click and change handlers near line 1855, `syncNow` near line 112), `static/style.css`
- Test: by hand in a browser (Step 4), plus `node --check` and every JS suite

**Interfaces:**
- Consumes: `StudentView` (Task 6); `GET /api/students/skeleton`; `lessonInfo()`, `exemptFrom(note, band)`, `setExempt(st, shown, picked)`, `stuKey`, `classNames()`, `clsLevel`, `save()`, `toast`, `Grid.weeks(days)` in `static/app.js` / `static/grid.js`.
- Produces: page state `S.stuOpen` (`null`, or `{i, row, picks}` where `i` is the index in `S.spec.students` or `-1` for a new student and `row` is a working copy) and `S.skel` (the skeleton, `false` when the server said none is published, `undefined` before the first fetch); functions `stuOpen(i)`, `stuScreen()` (the card's HTML), `stuSave()`, `stuClose()`.

Behaviour (the spec's section 1, in full; the mockup shows the look):

- [ ] **Step 1: The card.** Each row of the list gets a button **Open** in its last cell, before ✕. **+ Add student** calls `stuOpen(-1)` instead of adding a row. While `S.stuOpen` is set the card is drawn above the list card and the list stays below it. Two columns as the mockup: left the bands (radio per option, then **None** and **Exempt**), **Other groups** (tick boxes), then the **Note** box; right the week, one table per week from `Grid.weeks(skel.days)`, breaks drawn from the class's `codes`, cells from `view().cells` coloured by `state`; under it the key. Top: name, ID, class (a drop-down of `classNames()`), level, and the line about the personal code. Bottom: `summary`, **Cancel**, **Save · the timetable changes at once**. CSS classes are prefixed `sv-`; colours from the existing variables (`--warn-bg`, `--chip`, `--accent`) and the mockup's blue `#dbeafe` and grey `#f1f3f6`. Usable at a window 1100px wide; the week scrolls sideways inside its column when it is wider.
- [ ] **Step 2: Picking.** A radio, tick, the class drop-down, the ID, name and Note boxes change `S.stuOpen` only and redraw the card (keep the focus and the caret in a text box: redraw on `change`, not on every key). Changing the class runs `StudentView.open` again for the new class, keeping picks that are still groups of it; dropped picks show crossed out under Other groups until Save. The skeleton is fetched on the first `stuOpen` and again when `S.pubStu.at` (Task 8) differs from `S.skel.stamp`. With `S.skel === false`, or in a practice copy (`S.practice`), `view` gets `null` and the right column says `No timetable is published yet, so there is no week to show.` (practice copy: `A practice copy shows no week.`).
- [ ] **Step 3: Save, Cancel.** `stuSave()`: a new student needs ID, name and class (`toast` the first missing: `Type the student's ID.` / `Type the student's name.` / `Pick the student's class.`); an ID that another row has is refused with `` `${id} is already on the list.` ``; when `view().asks` is not empty, `confirm(asks.join("\n") + "\n\nSave anyway?")`; then write into `S.spec.students` (a new row pushed, or the row at `i` changed in place: `id`, `name`, `class`, `note`, `groups = StudentView.apply(…).groups`), call `setExempt(row, <the bands shown>, <the bands picked Exempt>)`, `save()`, set `S.stuSaved = stuKey(row)`, close and `render()`; the saved row gets the class `picked`-style highlight once. Cancel and the Esc key call `stuClose()` with nothing written. Opening another student while one is open with changes asks `Leave this student without saving?`.
- [ ] **Step 4: Check in a browser.** The controller gives a temporary launch entry on a scratch `DATA_DIR` with the sample secondary school published (Task 9 describes how). With **real mouse clicks** (`left_click`, never `.click()` from the console): open a student; swap a band's group and see blue and crossed-out cells; pick a clashing group and see the sentence and the red cell; pick Exempt and see the Note change after Save; change the class; Cancel leaves the list unchanged; Save changes the row; **+ Add student** refuses without an ID, then saves a new row. Then every older control of the step still works: a box in the table, the group chips popup, ticking and **Add to group**, **Move to class**, search, the class filter, ✕. Report each check as one line saying which kind of action it was.
- [ ] **Step 5: Run** `node --check static/app.js` and every `node tests/*.test.js`, one by one. Expected: all pass.
- [ ] **Step 6: Commit** `feat(students): open one student, see the week, change a group`.

---

### Task 8: The status line, the questions, and what the server said

**Files:**
- Modify: `static/app.js` (`students()`, `stuApply` near line 2722, the `data-del` handler for `students`, `syncNow` near line 112, the published card near line 3025)
- Test: by hand in a browser (Step 3), `node --check`, the JS suites

**Interfaces:**
- Consumes: `GET /api/students/published`, `POST /api/students/update`, the `students` key of the `POST /api/setup/changes` answer (`{outcome, status}` or `{error}`), `pub_info().files_behind`.
- Produces: `S.pubStu` (the last status, fetched when the Students step is first drawn and replaced by each answer that carries one).

- [ ] **Step 1: The status line**, a small card between the paste card and the list, from `S.pubStu`:
  - `published: false` → `No timetable is published yet. Students reach the timetable when it is published on step 9.`
  - all agree → `` `On the published timetable: ${students} students, all as listed here.` ``
  - else → `` `${differ_n} student${s} here differ${s ? "" : "s"} from the published timetable:` `` then one line per entry of `differ`: `` `${id} ${name}: ${why}` ``, then `` `and ${differ_n - differ.length} more` `` when there are more.
  - `files_behind` → a second line `The files to download are being refreshed.`
  - `can_update` → a button **Update the published timetable**. It asks `` `${change} students change, ${add} are added.` `` plus, when `remove > 0`, `` ` ${remove} are on the published timetable but not on this list. They will be removed from it.` `` plus ` Go on?`, posts, stores the answer's `status`, `toast`s the outcome's `text`.
  - In a practice copy: `Practice copy: nothing here reaches the published timetable.` and no button.
- [ ] **Step 2: What the server said.** In `syncNow`, an answer with `j.students`: store `j.students.status` in `S.pubStu`; `toast` `j.students.error` when present; when `S.stuSaved` is set, show under the status line (until the next render after another save) `` `Saved. ${outcome.text}` `` with a link **Timetable (PDF)** to `` `/pdf/students/${encodeURIComponent(id)}` `` when that student is in `outcome.updated` or `outcome.added`; redraw the step if it is showing. The questions: ✕ on a student row, when `S.pubStu.published` and the student is on the published timetable, asks `` `Remove ${id} ${name} from the list and from the published timetable?` ``; **Remove all** and **Replace the list** add to their question, when `S.pubStu.published && S.pubStu.students`, the sentence ` The published timetable keeps its students until you press Update the published timetable.` Step 9's published card shows `The files to download are being refreshed after a student change.` when `files_behind`.
- [ ] **Step 3: Check in a browser** with real mouse clicks, on the scratch server: after a group swap the line reads `Saved. Published timetable updated for …` and the PDF link downloads a timetable with the new group; open `/timetable` as committee and see the student's new group on the Students tab; add a student and sign in at `/login` with their personal code from the codes file (never print the code: read it in the test script and type it; a scratch code only); **Replace the list** with two students → the line lists the others as "on the published timetable but not on this list", **Update the published timetable** asks with the removal sentence, and after it the line says all as listed; restore an earlier copy (step 7, Keep a copy) → the line shows "not updated yet" and the button puts it right; History shows the save and the app's line, and **Put back** on the save moves the student back on the published timetable; wait for the files line to go (set `FILES_WAIT` low through the launch entry's environment if the controller provides it; else say it was not seen).
- [ ] **Step 4: Run** `node --check static/app.js`, every `node tests/*.test.js`, `$PY tests/test_students.py`, `$PY tests/test_routes.py`.
- [ ] **Step 5: Commit** `feat(students): the page says whether the list and the published timetable agree`.

---

### Task 9: Whole-branch checks, the real school's counts, the notes

**Files:**
- Create: `docs/superpowers/plans/2026-11-24-student-groups-notes.md`

- [ ] **Step 1: Every suite** on the final code: each `tests/test_*.py` and `tests/smoke.py` with `$PY`, each `tests/*.test.js` with `node`, `node --check static/app.js`, then `--full` for `tests/test_typed.py`, `tests/test_helper.py`, `tests/test_fixes.py` and `tests/smoke.py` (run the slow ones in the background). Expected: all pass; record the counts.
- [ ] **Step 2: The scratch server for browser checks** (the controller does this, not a builder): add by script a temporary entry to `.claude/launch.json` (keep a backup copy outside the repo, never print the file) that runs the app on a free port with `DATA_DIR` in the scratchpad and a plain made-up committee code; load the sample secondary school, solve it with `python -m ttgen solve` (about a minute), upload and publish; afterwards restore `.claude/launch.json` and compare with `cmp`, and delete the scratch data.
- [ ] **Step 3: The real school, counts only.** With the lead's latest setup workbook and timetable (the highest `vN` in the lead's timetable folder) on a scratch `DATA_DIR`: the number of bands and groups the screen shows for the largest class, the size of the skeleton answer in KB and its time, the time `store.remake_files()` takes, and that `students.status()` runs. Numbers only; no name leaves the script.
- [ ] **Step 4: Write the notes file:** rulings made while building, known limits (the spec's list, plus anything found), what was not tried in a browser, and the numbers of Step 3.
- [ ] **Step 5: Commit** `docs(students): notes of the build`.
- [ ] **Step 6:** `git stash list` shows the two old entries; `git status` is clean; `git log main..HEAD -S'<the school's full name>'` finds nothing.

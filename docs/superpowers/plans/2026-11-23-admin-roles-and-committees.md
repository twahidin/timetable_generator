# Admin page: one role, any number of committees, Edit and Remove: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A person on the admin page has one role and any number of committees, is edited from an Edit button with the panel always in view, and can be removed when they are not on the published timetable.

**Architecture:** The stored field `group` keeps its name and becomes the role; "Timetable committee" becomes `extras.timetable`, read from old records on the fly in `accounts/people.py`. `accounts/rights.py` stays the only place that decides rights, and also produces the plain sentences the panel shows. The admin routes in `app.py` take the new tick, and a new route removes a person. The page (`static/admin.js`, `static/admin.html`) is redrawn after the mockup, with its pure helpers in a new `static/adminview.js` that Node can test.

**Tech Stack:** Python 3 (Flask), vanilla JavaScript, plain-script tests (`python tests/x.py`, `node tests/x.test.js`).

**Spec:** `docs/superpowers/specs/2026-11-23-admin-roles-and-committees-design.md`, with the mockup `docs/superpowers/specs/2026-11-23-admin-roles-mockup.html` beside it (the mockup's own script and styles are its last `<script>` and last `<style>`). Where the two differ, the design is right.

## Global Constraints

- Work only in this worktree, `/Users/joetay/Developer/tt-generator/tt-admin-roles`, branch `admin-roles`. Never push, never merge, never touch `main`. Never run `git stash` in any form.
- Run Python with the main checkout's environment: `../timetable_generator/.venv/bin/python tests/x.py`. Run page tests with `node tests/x.test.js`. A suite prints its count on its last line and exits 0 when it passes.
- Every test sets `DATA_DIR` to a temporary folder before it imports `app` (the existing suites do). Never read or write the repo's `data/`.
- No test or probe calls a model API or the real Telegram API.
- The repo is public: made-up people only in tests, samples and docs; the school is only ever "CTSS" or "the school"; never commit secrets, `.claude/launch.json` or `data/`.
- Sentences the page shows are plain English with no dashes used as punctuation. Copy the sentences quoted in this plan and in the design exactly.
- The Python suites share one data folder across their tests, in file order: put a new test where its changes do not disturb the tests after it, or undo them at its end, as the existing tests do.
- The stored field for the role stays `group`. Its values: `leader`, `hod`, `sh`, `teacher`, `executive`. `committee` is not a role.
- Commit after each task. End every commit message with: `Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>`
- `app.py` and `static/*.js` have very long lines: read them by line range or with `grep -n … | cut -c1-240`, never whole.

## Review Focus

1. A stored record with `group: "committee"` and an extras key this version does not know: the move keeps the unknown key and ticks the committee. (Task 1)
2. Relief's one-time move of its Management list (`people.migrate`) running after this change for a person stored in the committee group: they get the role step 4 names and keep the Timetable committee. (Task 1)
3. "Make them management" (a bulk Set role to HOD or SH) on a person with the Timetable committee and Admin: both ticks stay. (Task 3)
4. A person is removed, then a newly published timetable names them: they are back as a Teacher with no committees, and no cookie from before the removal signs them in. (Task 5)
5. Two admins: one removes a person while the other has that person's panel open and presses a tick. The second gets the "not on the staff list" sentence and the list reloads without the person. (Tasks 5 and 6)

---

### Task 1: The record and the rights

**Files:**
- Modify: `accounts/people.py`, `accounts/rights.py`
- Test: `tests/test_accounts.py`

**Interfaces:**
- Produces: `people.GROUPS == ("leader", "hod", "sh", "teacher", "executive")`; `people.LABELS` keeps its `"committee": "Timetable committee"` entry (old history lines use it); `people.COMMITTEES == (("timetable", "Timetable committee"), ("relief", "Relief team"), ("exams", "Exams and events"))`; every cleaned record has `extras["timetable"]` (bool); `people.admins(data)` lists people with `extras.timetable` and `extras.admin` who are not off; `rights(person, via, shared=None, today=None)` in `accounts/rights.py`, unchanged in signature.

- [ ] **Step 1: Write the failing tests** in `tests/test_accounts.py` (the suite imports `accounts.rights` as `R` and `accounts.people` as `P`; add `import itertools`)

```python
OLD_GROUPS = (None, "committee", "leader", "hod", "sh", "teacher", "executive")

def old_rights(person, via, shared=None, today=None):
    ...  # a verbatim copy of accounts/rights.py's rights() as it is before this task, with its STRONG and _SHARED

@t
def the_committee_group_reads_as_a_tick():
    P.update(lambda d: d["people"].update({"Old Shape": {"group": "committee", "extras": {"admin": True, "later": 7}}}))
    r = P.record(P.load(), "Old Shape")
    assert r["group"] is None and r["extras"]["timetable"] is True and r["extras"]["admin"] is True and r["extras"]["later"] == 7, r
    P.update(lambda d: d["people"].update({"Old Shape": P.record(d, "Old Shape")}))            # saved once in the new shape
    stored = P.load()["people"]["Old Shape"]
    assert stored["group"] is None and stored["extras"]["timetable"] is True, stored
    assert P.record(P.load(), "Old Shape") == r                                                # reading again changes nothing
    assert "Old Shape" in P.admins(P.load())

@t
def nobody_s_rights_change_on_the_day():
    today = datetime.date(2026, 11, 23)
    for g, relief, exams, admin, off, via in itertools.product(OLD_GROUPS, (False, True), (None, "2026-11-22", "2026-12-31"), (False, True), (False, True), ("code", "password", "google")):
        stored = {"group": g, "extras": {"relief": relief, "exams": exams, "admin": admin}, "off": off}
        for default in ("teacher", "executive"):                                               # what the staff list shows while no group is set
            before = dict(stored, group=g or default)
            new = P._clean(dict(stored))
            after = dict(new, group=new["group"] or default)
            assert R.rights(after, via, today=today) == old_rights(before, via, today=today), (stored, default, via)

@t
def an_hod_on_the_timetable_committee_has_both():
    p = dict(group="hod", extras=dict(timetable=True, relief=False, exams=None, admin=False), off=False)
    assert {"committee", "setup", "history", "history.dept", "codes", "relief.plan", "relief.save"} <= R.rights(p, "password")
    assert "committee" not in R.rights(p, "code") and "setup" not in R.rights(p, "code")

@t
def admin_needs_the_timetable_committee():
    p = dict(group="leader", extras=dict(timetable=False, relief=False, exams=None, admin=True), off=False)
    assert "admin" not in R.rights(p, "password")
    P.update(lambda d: d["people"].update({"No Tick": {"group": "leader", "extras": {"admin": True}}}))
    assert "No Tick" not in P.admins(P.load())

@t
def relief_s_management_move_keeps_the_committee():       # Review Focus 2
    ...  # a fresh DATA_DIR state: store {"group": "committee"} for a name step 4 lists as HOD, run P.migrate(pub, {"management": [name]})
    ...  # assert record group == "hod", extras.timetable is True, and the returned line is f"{name}: HOD (from relief's Management list)"
```

Bring the suite's existing rights tests (`person(group, **extras)`, `rights_table`, `history_rights_by_group`) to the new shape: where they build a committee member, they pass `timetable=True` and a role.

- [ ] **Step 2: Run** `../timetable_generator/.venv/bin/python tests/test_accounts.py`. Expected: FAIL (`extras` has no `timetable`).

- [ ] **Step 3: Implement.** In `people.py`: `GROUPS`, `COMMITTEES`, `_defaults` and `_KNOWN_EXTRAS` gain `timetable`; `_clean` turns a stored `group == "committee"` into `group None` with `extras.timetable True` (a stored `extras.timetable is True` is also kept); `admins` as above. In `rights.py`, per the design's table: the committee's lines hang on `ex.get("timetable")` instead of `g == "committee"`; `relief` comes from the role (teacher, leader, hod, sh) or the tick; `admin` needs the tick and `ex.get("admin")`, with a strong sign-in. `_SHARED` is untouched.

- [ ] **Step 4: Run** the same suite. Expected: PASS. Then `../timetable_generator/.venv/bin/python tests/test_routes.py` and `tests/test_admin.py`: note which tests now fail only because they post `group="committee"` or read the committee as a group; those are Task 2's and Task 3's to bring in line, list them in your report.

- [ ] **Step 5: Commit** `accounts/people.py accounts/rights.py tests/test_accounts.py`: "Accounts: the Timetable committee is a tick, the group is the role".

---

### Task 2: One person's change, the people list and the first admin

**Files:**
- Modify: `app.py` (the admin block: `PICK_GROUP`, `EXTRA_LABELS`, `SIGNS_OUT`, `_wanted`, `_change`, `_whole`, `_said`, `_what`, `_field_now`, `admin_people`, `admin_first`, `status`)
- Test: `tests/test_admin.py`, and any other suite Task 1 listed

**Interfaces:**
- Consumes: Task 1's `people.GROUPS`, `people.COMMITTEES`, `extras["timetable"]`, `people.admins`.
- Produces: `POST /api/admin/person` accepts `extras.timetable` (bool); `GET /api/admin/people` returns `groups` (the five roles as `[key, label]`) and `committees` (`people.COMMITTEES` as `[key, label]`); `EXTRA_LABELS["timetable"] == "Timetable committee"`; `PICK_GROUP == "Pick a role."`; history says `"role {was} → {now}"` for a role change and `"Timetable committee given"` / `"Timetable committee taken away"` for the tick.

- [ ] **Step 1: Write the failing tests** in `tests/test_admin.py`. The fixture `RECORDS` keeps Alicia and Joseph stored as `group="committee"` on purpose: they are the old shape. Set `PICK_GROUP = "Pick a role."` at the top.

```python
@t
def the_people_list_shows_roles_and_committees():
    j = admin().get("/api/admin/people").get_json()
    assert [g[0] for g in j["groups"]] == ["leader", "hod", "sh", "teacher", "executive"], j["groups"]
    assert j["committees"] == [["timetable", "Timetable committee"], ["relief", "Relief team"], ["exams", "Exams and events"]]
    a = next(p for p in j["people"] if p["name"] == ALICIA)
    assert a["group"] == "teacher" and a["extras"]["timetable"] is True and a["extras"]["admin"] is True, a

@t
def the_timetable_committee_is_a_tick_beside_the_role():
    c = admin(); n0 = rec(DANIEL)["n"]
    code, j = post(c, "/api/admin/person", name=DANIEL, group="hod", extras=dict(timetable=True))
    assert code == 200 and j["group"] == "hod" and j["extras"]["timetable"] is True, (code, j)
    assert rec(DANIEL)["n"] == n0 + 1                                             # the new tick signs them out
    assert "Timetable committee given" in accounts()[0]["text"], accounts()[0]["text"]
    assert post(c, "/api/admin/person", name=JOSEPH, group="hod")[0] == 200       # Joseph: stored in the committee group, now an HOD too
    s = signed_in(JOSEPH).get("/api/status").get_json()
    assert s["role"] == "committee" and s["depts"] is None, s                     # an HOD on the committee changes every department
    assert "role Teacher → HOD" in accounts()[0]["text"], accounts()[0]["text"]

@t
def admin_goes_with_the_timetable_committee():
    c = admin()
    assert post(c, "/api/admin/person", name=NUR, extras=dict(admin=True)) == (400, {"error": ONLY_COMMITTEE})
    assert post(c, "/api/admin/person", name=NUR, extras=dict(timetable=True, admin=True))[0] == 200
    code, j = post(c, "/api/admin/person", name=NUR, extras=dict(timetable=False))
    assert code == 200 and j["extras"]["timetable"] is False and j["extras"]["admin"] is False, j
    assert {x["field"] for x in accounts()[0]["changes"]} == {"timetable", "admin"}

@t
def the_committee_is_not_a_role():
    assert post(admin(), "/api/admin/person", name=NUR, group="committee") == (400, {"error": PICK_GROUP})

@t
def the_last_admin_keeps_the_timetable_committee():
    ...  # with Alicia the only usable admin: extras=dict(timetable=False) for her is refused with last_admin(ALICIA) and nothing is written
```

In the existing first-admin tests, add: a person whose role is HOD makes themselves the first admin and is then `group == "hod"` with `extras.timetable` and `extras.admin` both true. Bring every existing test that posts `group="committee"` or expects "group … → …" wording to the new shape.

- [ ] **Step 2: Run** `../timetable_generator/.venv/bin/python tests/test_admin.py`. Expected: FAIL.

- [ ] **Step 3: Implement.**
  - `_wanted`: `extras` may carry bool `timetable` beside `relief` and `admin`.
  - `_change`: the extras loop is `("timetable", "relief", "exams", "admin")` in that order; when `timetable` becomes False and `admin` is not in `want`, `admin` becomes False. The rule that a group other than the committee drops Admin goes.
  - `_whole`: Admin needs `extras["timetable"]` (sentence unchanged: `ONLY_COMMITTEE_ADMIN`).
  - `_said`, `_what`, `_field_now`, `SIGNS_OUT`: `timetable` treated as `relief` is; a `group` change reads `role {LABELS[was]} → {LABELS[now]}`.
  - `admin_people`: returns `committees`. `admin_first`: sets `timetable=True, admin=True` and leaves the group alone.
  - `status`: the `group` label is the role's label, then " · " and the committees' labels joined by ", " when there are any (Admin last), for example `"HOD · Timetable committee, Relief team"`.

- [ ] **Step 4: Run** `tests/test_admin.py`, `tests/test_accounts.py`, `tests/test_routes.py`, `tests/test_putback.py`, `tests/test_history.py`. Expected: PASS, except tests of the bulk actions and Put back that Task 3 owns; name them in your report.

- [ ] **Step 5: Commit**: "Admin: a person's Timetable committee tick, roles in the list, the first admin keeps their role".

---

### Task 3: Several people at once, and Put back

**Files:**
- Modify: `app.py` (`_BULK_SAY`, `_bulk_lines`, `_bulk`, `_put_back_account`), `putback.py` (the sentence for an entry that cannot go back)
- Test: `tests/test_admin.py`, `tests/test_putback.py`

**Interfaces:**
- Consumes: Task 2's `EXTRA_LABELS`, `_change`, `_whole`.
- Produces: `POST /api/admin/bulk` accepts `extra: "timetable"` for `give` and `take`; `OLD_GROUP = "Can't put back: this is from before roles and committees were separated. Make the change on the admin page."`

Sentences (exact):
- give timetable: `"{names} joins|join the Timetable committee."`; already: `"{n} is on the Timetable committee already."`
- take timetable: `"{names} leaves|leave the Timetable committee."`; not on it: `"{n} is not on the Timetable committee."`; for each who had Admin: `"{n} stops being an admin: only the timetable committee can be admins."`
- set role: `"The role of {names} becomes {label}."`; already: `"{n} is {label} already."`; history text `"Set the role of {them} to {label}"`. A role change no longer says anything about Admin.

- [ ] **Step 1: Write the failing tests**

```python
@t
def ticking_several_onto_the_timetable_committee():
    c = admin()
    code, j = post(c, "/api/admin/bulk", names=[RAVI, NUR, JOSEPH], action="give", extra="timetable")
    assert code == 200 and j["applied"] is False and j["lines"] == [f"{RAVI} and {NUR} join the Timetable committee.", f"{JOSEPH} is on the Timetable committee already."], j
    n = len(accounts())
    code, j = post(c, "/api/admin/bulk", names=[RAVI, NUR, JOSEPH], action="give", extra="timetable", preview=False)
    assert code == 200 and j["applied"] is True and len(accounts()) == n + 1 and accounts()[0]["people"] == [RAVI, NUR]
    assert rec(RAVI)["extras"]["timetable"] and rec(RAVI)["group"] is None       # their role is untouched

@t
def taking_the_committee_from_an_admin_says_so():
    ...  # give NUR timetable and admin; bulk take timetable for [NUR] previews [f"{NUR} leaves the Timetable committee.", f"{NUR} stops being an admin: only the timetable committee can be admins."]

@t
def make_them_management_keeps_the_committee():          # Review Focus 3
    ...  # JOSEPH (stored committee group, step 4 role HOD): bulk action="group", group="hod", preview=False
    ...  # then rec(JOSEPH): group "hod", extras.timetable True; lines[0] == f"The role of {JOSEPH} becomes HOD."

@t
def put_back_the_timetable_committee_tick():
    ...  # give WEI the tick by /api/admin/person, back(c, accounts()[0]["id"]) == (200, {"done": True, "text": "Put back."}), rec(WEI) tick False

@t
def an_old_committee_group_entry_is_not_put_back():
    H.add({"kind": "account", "what": "group", "where": "Admin", "people": [GRACE], "text": f"Moved {GRACE} to the Timetable committee group",
           "changes": [{"name": GRACE, "field": "group", "was": "teacher", "now": "committee"}], "who": ALICIA, "as": ALICIA, "via": "password"})
    e = accounts()[0]; code, j = back(admin(), e["id"])
    assert code == 409 and j["error"] == "Can't put back: this is from before roles and committees were separated. Make the change on the admin page."
    ...  # and the history list shows the same entry with back.ok False and back.why equal to that sentence
```

- [ ] **Step 2: Run** `tests/test_admin.py`. Expected: FAIL.
- [ ] **Step 3: Implement** in the style of the code around it. The old-entry check: any change whose field is `group` and whose `was` or `now` is `"committee"`.
- [ ] **Step 4: Run** `tests/test_admin.py`, `tests/test_putback.py`, `tests/test_history.py`, `node tests/history.test.js`. Expected: PASS.
- [ ] **Step 5: Commit**: "Admin: several people onto a committee at once; Put back knows the tick".

---

### Task 4: What this gives them

**Files:**
- Modify: `accounts/rights.py`, `app.py` (`_admin_item`, `admin_people`)
- Test: `tests/test_accounts.py`, `tests/test_admin.py`

**Interfaces:**
- Produces: in `accounts/rights.py`, `gives(person, depts, today=None) -> list[dict]`, each `{"text": str, "strong": bool}`. `person` is a staff item (`group`, `extras`, `off`); `depts` is the person's own ticked departments (their record's). Every person on `GET /api/admin/people` and the reply of `POST /api/admin/person` carries `gives` (that list) and `strong` (bool: they have a password; later, or a linked Google account).

The lines, in this order, worked out from `rights(person, "password", today=today)` (call the set R):

| Condition | text | strong |
| --- | --- | --- |
| `person["off"]` | `Nothing: switched off, so they cannot sign in.` (the only line) | False |
| always | `Sees the published timetable and the files.` | False |
| `relief` in R, `relief.plan` not in R | `Relief: opens the relief page and asks for cover.` | False |
| `relief.plan` in R, `relief.team` not in R | `Relief: plans cover, as management.` | False |
| `relief.team` in R | `Relief: runs it, with the team's pages and settings.` | False |
| `setup` in R, `committee` not in R, depts | `Setup: changes the teaching groups of {", ".join(depts)} only.` | True |
| `setup` in R, `committee` not in R, no depts | `Setup: no department ticked yet, so nothing to change.` | True |
| `committee` in R | `Setup: every step, the upload, the edit board and Publish.` | True |
| `committee` in R | `Exams and events: plans them and approves them.` | True |
| `exams` in R, `committee` not in R | `Exams and events: plans them, until {day}.` (`day` as `31 Dec 2026`) | False |
| `history` in R | `History: sees everyone's changes.` | True |
| `history.dept` in R, `history` not in R | `History: sees their departments' changes.` | True |
| `admin` in R | `People and access: this page.` | True |

Before you keep a sentence, check in `app.py` what its right opens (`grep -n '@need(' app.py`); if a sentence says more than the right gives, say less and note the change in your report.

- [ ] **Step 1: Write the failing tests**

```python
@t
def what_a_role_and_committees_give():
    T = datetime.date(2026, 11, 23)
    hod = dict(group="hod", extras=dict(timetable=False, relief=False, exams=None, admin=False), off=False)
    assert [g["text"] for g in R.gives(hod, ["MA"], T)] == ["Sees the published timetable and the files.", "Relief: plans cover, as management.",
        "Setup: changes the teaching groups of MA only.", "History: sees their departments' changes."]
    assert R.gives(hod, [], T)[2] == {"text": "Setup: no department ticked yet, so nothing to change.", "strong": True}
    full = dict(group="hod", extras=dict(timetable=True, relief=True, exams="2026-12-31", admin=True), off=False)
    assert [g["text"] for g in R.gives(full, ["MA"], T)] == ["Sees the published timetable and the files.", "Relief: runs it, with the team's pages and settings.",
        "Setup: every step, the upload, the edit board and Publish.", "Exams and events: plans them and approves them.", "History: sees everyone's changes.", "People and access: this page."]
    ex = dict(group="executive", extras=dict(timetable=False, relief=False, exams="2026-12-31", admin=False), off=False)
    assert [g["text"] for g in R.gives(ex, [], T)] == ["Sees the published timetable and the files.", "Exams and events: plans them, until 31 Dec 2026."]
    assert R.gives(dict(full, off=True), ["MA"], T) == [{"text": "Nothing: switched off, so they cannot sign in.", "strong": False}]

@t
def a_marked_line_is_never_given_by_a_code():
    ...  # for every record shape of nobody_s_rights_change_on_the_day: a line with strong False names only rights that rights(person, "code") holds;
    ...  # check through a small table in the test: sentence start -> the right it needs
```

In `tests/test_admin.py`: the people list's item for Alicia has `strong is True` and a `gives` list ending `{"text": "People and access: this page.", "strong": True}`; Ravi (no password) has `strong is False`.

- [ ] **Step 2: Run** both suites. Expected: FAIL (`gives` is not defined).
- [ ] **Step 3: Implement** `gives` beside `rights` in `accounts/rights.py`; add `gives` and `strong` in `_admin_item` and to each person in `admin_people`.
- [ ] **Step 4: Run** both suites. Expected: PASS.
- [ ] **Step 5: Commit**: "Admin: what a person's role and committees give, in sentences from the rights themselves".

---

### Task 5: Remove

**Files:**
- Modify: `accounts/people.py` (`blank`, `_fill`, `record`), `app.py` (a new route beside `admin_person`), `putback.py` (the refusal)
- Test: `tests/test_admin.py`, `tests/test_accounts.py`

**Interfaces:**
- Produces: the accounts file has `removed`, a dict of name to a sign-out number; `people.record(data, name)` for a name with **no stored record** returns the defaults with `n` set to `data["removed"].get(name, 0)`; `POST /api/admin/remove` with `{"name": str}` (right: `admin`) answers `{"done": True, "text": "{name} is removed. What they changed stays in the History."}`.

Why the number is kept: a session is accepted only while its `n` equals the person's `n`. With `removed[name] = their n + 1`, a name with no record reads as `n` one past every cookie that exists, so no old session is accepted, with or without a published timetable; a record made later for that name starts from that number, so it stays true after they are added again.

Refusals (status 400, nothing changed), checked in this order:
- name not on the staff list: `NOT_STAFF.format(name)`
- on the published timetable (their staff item has `staff_only` False): `"{name} is on the published timetable, so they cannot be removed. Switch them off instead."`
- the admin themselves: `"You cannot remove yourself."`
- no usable admin would be left: `LAST_ADMIN.format(name)` (a guard only: the admin doing it is always left, so no test can reach it)

Then, in this order: `relief.links.unlink(name)` (if it raises: status 503, `"Their Telegram chat could not be unlinked, so nothing was removed. Try again."`); then one `_update_as` that checks the refusals again on the data it holds, deletes `d["people"][name]` and sets `d["removed"][name]`. Then one history entry: `what "remove"`, `people [name]`, `text "Removed {name}"`, `changes [{"name": name, "field": "removed", "was": {role label, timetable, relief, exams, admin, depts, username, note, off}, "now": None}]`, never `pw`. Put back on it answers 409 `"Can't put back: add {name} again with Add a person."`, and the history list shows the same reason.

- [ ] **Step 1: Write the failing tests** in `tests/test_admin.py` (add `("POST", "/api/admin/remove")` to `ROUTES`, so the admins-only test covers it)

```python
@t
def remove_each_refusal_has_its_sentence():
    c = admin()
    assert post(c, "/api/admin/remove", name="Nobody Here") == (400, {"error": not_staff("Nobody Here")})
    assert post(c, "/api/admin/remove", name=RAVI) == (400, {"error": f"{RAVI} is on the published timetable, so they cannot be removed. Switch them off instead."})
    ...  # give LEE (added by name, has a password) the Timetable committee and Admin, sign in as LEE: removing LEE answers (400, {"error": "You cannot remove yourself."})
    assert all(x["what"] != "remove" for x in accounts())

@t
def a_removed_person_is_gone_and_signed_out():
    c = admin()
    ...  # add "Mr Zed Added" by name with a username and a one-time password (the existing reset route)
    ...  # pz = as_person("Mr Zed Added", via="password"); cz = as_person("Mr Zed Added"); before the removal neither gets 401 from GET /api/day
    code, j = post(c, "/api/admin/remove", name="Mr Zed Added")
    assert (code, j) == (200, {"done": True, "text": "Mr Zed Added is removed. What they changed stays in the History."})
    assert "Mr Zed Added" not in P.load()["people"] and P.load()["removed"]["Mr Zed Added"] >= 1
    assert all(p["name"] != "Mr Zed Added" for p in c.get("/api/admin/people").get_json()["people"])
    assert pz.get("/api/day").status_code == 401 and cz.get("/api/day").status_code == 401
    e = accounts()[0]
    assert e["what"] == "remove" and e["text"] == "Removed Mr Zed Added" and all(s not in json.dumps(e) for s in SECRETS)
    assert back(c, e["id"]) == (409, {"error": "Can't put back: add Mr Zed Added again with Add a person."})
    assert post(c, "/api/admin/person", name="Mr Zed Added", username="zed.again", added=True)[0] == 200     # the username was free, the name can come back
    assert rec("Mr Zed Added")["n"] >= P.load()["removed"]["Mr Zed Added"]
    assert cz.get("/api/day").status_code == 401                                                            # the old code cookie stays dead after they are added again

@t
def a_removed_person_s_code_session_ends_with_nothing_published():
    ...  # as above, but move the published folder away for the test (and put it back in a finally): the old code client is not signed in

@t
def removed_then_named_by_a_new_timetable():             # Review Focus 4
    ...  # remove an added person, then publish() with that name among TEACHERS: the list shows them as group "teacher", no committees, staff_only False,
    ...  # and a client made with the n they had before the removal is not signed in

@t
def a_failed_telegram_unlink_removes_nothing():
    ...  # replace relief.links.unlink with one that raises for the length of the test: 503 with the sentence, the record still there, no history entry
    ...  # and with a working unlink that records its calls: it was called once with the name, before the record went

@t
def a_tick_for_someone_just_removed_says_so():           # Review Focus 5
    ...  # remove an added person, then post("/api/admin/person", name=that, extras=dict(relief=True)) == (400, {"error": not_staff(that)})
```

In `tests/test_accounts.py`: `record` of an unknown name gives `n == 0`; with `removed == {"X": 4}` and no record it gives `n == 4`; a stored record wins over `removed`; a file whose `removed` is not a dict reads as `{}`.

- [ ] **Step 2: Run** both suites. Expected: FAIL (404 on the route).
- [ ] **Step 3: Implement** as described. Find how `app.py` already reaches relief's links module and reuse it; `unlink` must not need a bot token (check `relief/tgdb.py`: it is a local file under the data folder).
- [ ] **Step 4: Run** `tests/test_admin.py`, `tests/test_accounts.py`, `tests/test_putback.py`, `tests/test_history.py`, and every `tests/test_relief*.py` suite. Expected: PASS.
- [ ] **Step 5: Commit**: "Admin: remove a person who is not on the published timetable".

---

### Task 6: The page

**Files:**
- Create: `static/adminview.js`, `tests/adminview.test.js`
- Modify: `static/admin.js`, `static/admin.html`
- Test: `tests/adminview.test.js`; and if a suite lists the scripts a page loads (`grep -n "admin.js" tests/*`), add the new script there

**Interfaces:**
- Consumes: `GET /api/admin/people` (`people[].group`, `.extras.timetable|relief|exams|admin`, `.gives`, `.strong`, `.staff_only`, `.off`, `groups`, `committees`, `me`), `POST /api/admin/person` with `extras.timetable`, `POST /api/admin/bulk` with `extra: "timetable"`, `POST /api/admin/remove`.
- Produces: `AdminView`, a plain object in the pattern of `static/people.js` (a `var AdminView = (function () { … })();` then `if (typeof module !== "undefined") module.exports = AdminView;`), loaded by `admin.html` before `admin.js`:
  - `AdminView.committees(p) -> [{key, text}]`: in the order timetable, relief, exams, admin; exams' text is `"Exams and events · to 31 Dec 2026"`.
  - `AdminView.shown(people, {q, role, committee, dept}) -> people`: `committee` is `""`, `"timetable"`, `"relief"`, `"exams"`, `"admin"`, `"none"` (none of the three committees) or `"off"`.
  - `AdminView.canRemove(p, me) -> {ok: bool, why: string}`: `why` is `"{name} is on the published timetable, so they cannot be removed: they would come straight back. Switch them off instead."` for a person on the timetable, `""` otherwise; `ok` is false for `me`.
  - `AdminView.noPassword(p) -> string`: `"The lines marked ✱ need a password account. {name} has none yet."` when `p.gives` has a strong line and `p.strong` is false, else `""`.

- [ ] **Step 1: Write the failing tests** in `tests/adminview.test.js` (the shape of `tests/people.test.js`): one test per function above, including a person with all three committees and Admin, a person with none, a switched-off person under the `"off"` and `"none"` filters, a search that ignores capitals, and `canRemove` for `me`, for an added person and for a person on the timetable. Last line prints `adminview: N passed`.

- [ ] **Step 2: Run** `node tests/adminview.test.js`. Expected: FAIL (cannot find module).

- [ ] **Step 3: Implement the page**, following the design's sections "The Staff tab", "The panel", "What this gives them", "Ticking several people" and "Remove", and the mockup for the look:
  - Table columns: tick, Name (link colour, `added by name` beneath for `staff_only`), Role chip, Committees chips (after "Switched off"), Department, Last signed in, an **Edit** button whose cell stays in view (`position: sticky; right: 0`). Name and Edit both open the panel; pressing either again closes it.
  - Filters: Search, Role, Committee (the seven choices above), Department, Tick all shown.
  - Panel, wide (over 900px): beside the list, `position: sticky` below the header, scrolling inside itself when taller than the window. Narrow: over the page from the right on a dimmed backdrop. Esc, ✕ and a press on the backdrop close it. Focus goes to the panel's heading when it opens and back to that row's Edit button when it closes.
  - Panel body in the design's order: Role box; a head's departments as ticks in a row; Committees (three ticks, the "until" date when Exams and events is ticked); Admin (disabled with "needs the Timetable committee" until that is ticked, else "opens this page"); What this gives them (`p.gives`, a ✱ before each strong line, then `AdminView.noPassword(p)`); Way in, Note and the three buttons as today; then Remove or its one-line reason (`AdminView.canRemove`).
  - Remove: the button turns into the question `Remove {name}? Their username and password go, their code stops working and their Telegram chat is unlinked. What they changed stays in the History. This cannot be put back.` with **Yes, remove** and **Cancel**. On success: close the panel, reload the list, show the server's text. On a refusal: show its sentence in the panel and reload the list.
  - Any save that answers "… is not on the published timetable or the staff list." reloads the list, so a person someone else removed disappears.
  - The dark bar: **Add to a committee ▾**, **Take off a committee ▾** (each lists Timetable committee, Relief team, Exams and events, Admin), **Set role ▾**; the rest as today. The buttons' sentences come from the server's preview as today.
  - Every name, note and server text still goes through `esc()`. The one-time password is still kept only in `S.once`.

- [ ] **Step 4: Run** `node tests/adminview.test.js`, `../timetable_generator/.venv/bin/python tests/test_routes.py`, and `node --check static/admin.js`. Expected: PASS and no syntax error. Do not start a server: the browser check is Task 7's.

- [ ] **Step 5: Commit**: "Admin page: roles and committees apart, Edit on every row, the panel in view, Remove".

---

### Task 7: The browser check, the words elsewhere, the notes

This task is the controller's, not a subagent's: it needs the browser pane and a scratch server.

**Files:**
- Modify: `README.md` and any doc that says "the committee group" for a person (`grep -rn -i "committee group" README.md docs/*.md static/*.html`)
- Create: `docs/superpowers/plans/2026-11-23-admin-roles-and-committees-notes.md`

- [ ] **Step 1: Every suite.** `for f in tests/*.test.js; do node "$f" | tail -1; done` and `for f in tests/test_*.py tests/smoke.py; do ../timetable_generator/.venv/bin/python "$f" 2>/dev/null | tail -1; done`. Expected: every suite's passing line, none missing against the list on main.
- [ ] **Step 2: In a browser**, on a scratch data folder with made-up people (the app's sample school published, one admin made by the first-admin page, two people added by name): Edit on every row; the panel at 1280px and at 700px wide; Esc and focus; one person given all three committees and Admin, their sentences and the ✱ line; "Add to a committee" for three people with its preview; Remove with its question, then the person gone and their own tab signed out; the History tab showing the entries. No console error.
- [ ] **Step 3: The words elsewhere.** Bring the docs in line with "role" and "Timetable committee tick".
- [ ] **Step 4: The notes file**: what was built, each ruling made on the way, what was checked in the browser and what was not, and the design's calls the lead should still confirm (the same personal code for the same name; no Put back for a removal; one role; Exams and events as one tick).
- [ ] **Step 5: Commit**: "Admin roles and committees: docs and notes".

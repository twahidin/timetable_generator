# Student codes and head resets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Any member of staff can look up one student's forgotten code; an HOD or SH can give staff in their departments a new temporary password.

**Architecture:** Two new rights worked out in `accounts/rights.py`, two home page tiles, and two small server-made pages in `app.py` (forms in the sign-in pages' style, no page script). A code or password leaves the server only for the one person asked for, and each look-up or reset is one history entry without the secret.

**Tech Stack:** Flask (`app.py`), plain-assert Python test files run as scripts.

**Spec:** `docs/superpowers/specs/2026-11-27-codes-and-resets-design.md`

## Global Constraints

- Branch `login-boxes`, worktree `tt-login-boxes`. The branch already holds the sign-in page change (two boxes, green Open, blue "Staff Sign In"); do not change those.
- Made-up names only in tests and commits; the school is only ever "CTSS". No real codes, passwords or keys in any output.
- NEVER run `git stash`, `git stash pop` or `git checkout -- <file>`. Never `pkill`/`killall` by name or pattern; stop only processes you started, by PID.
- Every new route uses `@need(...)`; add it to `GUARDS` in `tests/test_routes.py`.
- Answers that hold a code or a password carry `Cache-Control: no-store`.
- No code or password in the history, a log, or the accounts file (only `passwords.hash_pw` of a password).
- Words, exactly:
  - Tiles: `("Student codes", "Look up a student's forgotten code", "/student-codes", ("codes.look",))` and `("Reset a password", "A new temporary password for staff in your department", "/staff-reset", ("staff.reset",))`, placed after "Relief" in `TILES`. `"Reset a password"` joins `GREYED`.
  - `CODES_HINT = "Pick the class, then press Show code beside the student. Each look-up is recorded."`
  - `CODES_NOT_PUBLISHED = "The timetable is not published yet, so there are no student codes."`
  - `CODES_EMPTY_CLASS = "This class has no students on the published timetable."`
  - `CODES_NO_STUDENT = "That student is not on the published timetable."`
  - Look-up history text: `f"Looked up the code of {name} ({cls})"`
  - `RESET_HINT = "Give the new temporary password to the person yourself. They choose their own when they sign in."`
  - `RESET_NONE = "No one in your departments can be reset here. Ask an admin."`
  - `RESET_REFUSED = "You cannot reset this person's password. Ask an admin."`
  - Reset shown: `f"New temporary password for {name}"`, then `Username` and `Temporary password` rows.
  - Reset history text: `f"{name}: a new one-time password from their head of department"`
  - `gives()` lines: `"Student codes: looks up a student's forgotten code."` (not strong) for `codes.look`; `"Passwords: gives staff in their departments a new temporary password."` (strong) for `staff.reset`.
- Run with `.venv/bin/python tests/<name>.py`; the suites a task touches must pass, and `tests/test_routes.py`, `tests/test_admin.py`, `tests/test_signin.py`, `tests/test_staff_passwords.py`, `tests/smoke.py` at the end of every task.

## Review Focus

1. A Student ID with spaces, slashes or quotes in it, and a posted `id` that is not on the published timetable: the page names the student safely (escaped) or says `CODES_NO_STUDENT`, never a 500.
2. A head whose department is a teacher's *second* department (`dept2`): that teacher is on the head's list; a head with no departments ticked sees `RESET_NONE`.
3. A posted `name` the head may not reset (themselves, an admin, a School leader, an HOD or SH, a switched-off person, someone outside their departments, someone not on staff): `RESET_REFUSED`, nothing changed, no history entry.
4. A head signed in with a staff code (while staff codes are on): the tile is greyed and both `/staff-reset` routes refuse.
5. The timetable not published: Student codes says `CODES_NOT_PUBLISHED`; Reset a password still works from the accounts.

---

### Task 1: The two rights, the tiles and the admin page's lines

**Files:**
- Modify: `accounts/rights.py` (`rights`, `gives`), `app.py` (`RIGHTS`, `TILES`, `GREYED`)
- Test: `tests/test_codes_resets.py` (new; copy the harness of `tests/test_staff_passwords.py` lines 1-110: temp `DATA_DIR`, `SECRETS`, `publish`, `person`, `account`, `@t`, `admin`, and `signed_in` from its line 471)

**Interfaces:**
- Produces: right names `"codes.look"` (every person not switched off, any `via` except `"personal"`/`"shared"`) and `"staff.reset"` (group `"hod"` or `"sh"`, `via in STRONG`), both in `app.RIGHTS`.

- [ ] **Step 1: Write the failing tests** in `tests/test_codes_resets.py`:

```python
@t
def the_rights():
    R = RT.rights
    for g in ("teacher", "executive", "leader", "hod", "sh"):
        assert "codes.look" in R(dict(group=g, extras={}), "password"), g
        assert "codes.look" in R(dict(group=g, extras={}), "code"), g
    assert "codes.look" not in R(None, "shared", "teacher") and "codes.look" not in R(None, "personal")
    assert R(dict(group="teacher", extras={}, off=True), "password") == frozenset()
    assert "staff.reset" in R(dict(group="hod", extras={}), "password") and "staff.reset" in R(dict(group="sh", extras={}), "password")
    assert "staff.reset" not in R(dict(group="hod", extras={}), "code")
    for g in ("teacher", "executive", "leader"): assert "staff.reset" not in R(dict(group=g, extras={"admin": True, "timetable": True}), "password"), g

@t
def the_tiles():
    c = signed_in(ALICE)                           # a teacher by password
    h = c.get("/home").data.decode()
    assert "Student codes" in h and 'href="/student-codes"' in h and "Reset a password" not in h
    c = signed_in(ERIC, group="hod", depts=["Science"])
    h = c.get("/home").data.decode()
    assert 'href="/staff-reset"' in h
    # a head on a staff code (staff codes on): greyed, to the password page
    c, _ = code_in(staff_code(ERIC))
    h = c.get("/home").data.decode()
    assert "Reset a password" in h and 'href="/staff-reset"' not in h and "Sign in with your password to open this." in h

@t
def the_admin_page_lines():
    texts = [x["text"] for x in RT.gives(dict(group="hod", extras={}), ["Science"])]
    assert "Student codes: looks up a student's forgotten code." in texts
    assert "Passwords: gives staff in their departments a new temporary password." in texts
```

(`RT` is `accounts.rights`; `signed_in` must accept `depts=`; if the copied helper does not pass it to the record, extend it.)

- [ ] **Step 2: Run** `.venv/bin/python tests/test_codes_resets.py` — expect failures on the missing rights and tiles.
- [ ] **Step 3: Implement**: in `rights()` add `r.add("codes.look")` beside `history.own` (persons only, not switched off: the early returns already cover off/shared/personal); in the `via in STRONG` block add `staff.reset` for `g in ("hod", "sh")`. Add both to `RIGHTS`, the two tiles after "Relief" in `TILES`, `"Reset a password"` to `GREYED`, and the two `gives()` lines (codes line right after the first line; passwords line after the history lines).
- [ ] **Step 4: Run** the new file and `tests/test_admin.py`, `tests/test_routes.py`, `tests/test_signin.py`, `tests/test_staff_passwords.py`, `tests/smoke.py`. Where an existing test lists `gives()` lines or a person's tiles exactly, update it to the new lines; change nothing else in it.
- [ ] **Step 5: Commit** `feat(accounts): rights and tiles for student codes and head resets`.

### Task 2: The Student codes page

**Files:**
- Modify: `app.py` (new routes beside the code slip routes), `static/login.css` (only if the list needs a rule)
- Test: `tests/test_codes_resets.py`, `tests/test_routes.py` (`GUARDS`)

**Interfaces:**
- Consumes: right `codes.look` (Task 1); `access.personal_code(id)`, `access.personal_codes_on()`, `NO_PERSONAL`, `store.published()` (`pub["model"]["students"]`: dicts with `id`, `name`, `cls`), `history.add`, `by()`, `page()`, `esc()`.
- Produces: `GET /student-codes` (`student_codes_page`, query `cls`) and `POST /student-codes` (`student_codes_show`, form field `id`), both `@need("codes.look")`.

- [ ] **Step 1: Write the failing tests**:

```python
@t
def student_codes_by_class():
    publish(); pub_students([dict(id="S001", name="Sam Student", cls="1A"), dict(id="S/2 'x'", name="Kim <b>", cls="1A"), dict(id="S003", name="Lee", cls="2B")])
    c = signed_in(ALICE)
    h = c.get("/student-codes").data.decode()
    assert CODES_HINT in h and ">1A<" in h and ">2B<" in h and access.personal_code("S001") not in h
    h = c.get("/student-codes?cls=1A").data.decode()
    assert "Sam Student" in h and "Kim &lt;b&gt;" in h and "Lee" not in h and access.personal_code("S001") not in h
    n = len(H.read(kinds=["look"], limit=100))
    r = c.post("/student-codes", data=dict(id="S001")); h = r.data.decode()
    code = access.personal_code("S001"); SECRETS.append(code)
    assert r.status_code == 200 and code in h and r.headers["Cache-Control"] == "no-store"
    assert access.personal_code("S/2 'x'") not in h                # only the one asked for
    e = H.read(kinds=["look"], limit=1)[0]
    assert len(H.read(kinds=["look"], limit=100)) == n + 1 and e["text"] == "Looked up the code of Sam Student (1A)" and e["who"] == ALICE
    r = c.post("/student-codes", data=dict(id="S/2 'x'")); assert r.status_code == 200 and access.personal_code("S/2 'x'") in r.data.decode()
    SECRETS.append(access.personal_code("S/2 'x'"))

@t
def student_codes_refusals():
    c = signed_in(ALICE)
    r = c.post("/student-codes", data=dict(id="NOPE")); assert r.status_code == 404 and CODES_NO_STUDENT in r.data.decode()
    assert A.app.test_client().get("/student-codes").status_code == 302          # nobody signed in
    sc = access.personal_code("S001"); SECRETS.append(sc)
    s = A.app.test_client(); s.post("/student", data=dict(code=sc))
    assert s.get("/student-codes").status_code in (302, 401) and s.post("/student-codes", data=dict(id="S001")).status_code in (302, 401)
    h = signed_in(ALICE).get("/student-codes?cls=9Z").data.decode(); assert CODES_EMPTY_CLASS in h
    unpublish(); assert CODES_NOT_PUBLISHED in signed_in(ALICE).get("/student-codes").data.decode(); publish()

@t
def student_codes_by_staff_code():
    c, _ = code_in(staff_code(BEN))                # staff codes on: a staff code session is staff
    assert c.get("/student-codes").status_code == 200
```

(`pub_students(list)` is a small helper in the test file that rewrites `model.pkl` with those students and clears `store._cache`, as `publish()` does. The last test of the file stays `nothing_typed_reaches_the_history`, copied from `tests/test_staff_passwords.py`, scanning `DATA` for every value in `SECRETS`.)

- [ ] **Step 2: Run** — expect failures (no routes).
- [ ] **Step 3: Implement**: one page builder `_codes_page(cls=None, shown=None, msg="")` using `_form_page("Student codes", …, back=("/home", "Back"))`. Without `SECRET_KEY` it shows `NO_PERSONAL`; unpublished, `CODES_NOT_PUBLISHED`. Classes are the sorted distinct `cls` values as links `/student-codes?cls=<urlencoded>`; a picked class lists its students (sorted by name), each with a small form posting `id` (hidden) and a **Show code** button. `shown` puts the student's name, class and code in a box at the top. The POST finds the student by `id` among the published students (404 and `CODES_NO_STUDENT` if none), writes `history.add({"kind": "look", "where": "Student codes", "text": …, "people": [], **by()})` (inside try/except like `_account_entry`, so a history failure never hides the code), and answers the page for that student's class with `no-store`. Escape every name, class and id.
- [ ] **Step 4: Run** the new file and the end-of-task suites; add the two routes to `GUARDS` as `('codes.look',)`.
- [ ] **Step 5: Commit** `feat: Student codes, any staff member looks up one student's code`.

### Task 3: The Reset a password page

**Files:**
- Modify: `app.py` (new routes beside `admin_reset`), `README.md` (a short "Forgotten codes and passwords" section beside "Staff passwords")
- Test: `tests/test_codes_resets.py`, `tests/test_routes.py`

**Interfaces:**
- Consumes: right `staff.reset`; `people.staff(pub, d)` (items with `name`, `group`, `depts`, `extras`, `off`, `username`), `people.record`, `people.update`, `passwords.one_time()`, `passwords.hash_pw`, `account_slips.make_username(name, depts, taken)`, `_taken`, `lockout.clear`, `_account_entry`, `by()`; the head's own departments are `people.record(d, me)["depts"]`.
- Produces: `GET /staff-reset` (`staff_reset_page`) and `POST /staff-reset` (`staff_reset_do`, form field `name`), both `@need("staff.reset")`.

- [ ] **Step 1: Write the failing tests**:

```python
@t
def head_resets_their_department():
    publish(TEACHERS + [dict(name=DANA, dept="Mathematics", dept2="Science")])
    account(ALICE, group="teacher"); account(ERIC, group="hod", depts=["Science"])
    c = signed_in(ERIC, group="hod", depts=["Science"])
    h = c.get("/staff-reset").data.decode()
    assert RESET_HINT in h and ALICE in h and DANA in h and BEN not in h and f'value="{ERIC}"' not in h
    n0 = rec(ALICE)["n"]
    r = c.post("/staff-reset", data=dict(name=ALICE)); h = r.data.decode()
    assert r.status_code == 200 and r.headers["Cache-Control"] == "no-store" and f"New temporary password for {ALICE}" in h
    once = re.search(r"[A-Z2-9]{4}-[A-Z2-9]{4}-[A-Z2-9]{4}", h).group(0); SECRETS.append(once)
    rr = rec(ALICE); assert rr["must_change"] and rr["n"] == n0 + 1 and PW.check_pw(rr["pw"], once)
    e = last("account"); assert e["text"] == f"{ALICE}: a new one-time password from their head of department" and e["who"] == ERIC
    r = c.post("/staff-reset", data=dict(name=DANA)); assert r.status_code == 200 and rec(DANA)["username"]   # no username yet: one is made
    SECRETS.append(re.search(r"[A-Z2-9]{4}-[A-Z2-9]{4}-[A-Z2-9]{4}", r.data.decode()).group(0))

@t
def head_reset_refusals():
    account(ERIC, group="hod", depts=["Science"]); account("Ms Ada Lim", group="committee", extras={"admin": True, "timetable": True})
    person("Mr Sid Head", group="sh", depts=["Science"]); person(ALICE, off=True)
    c = signed_in(ERIC, group="hod", depts=["Science"])
    for name in (ERIC, "Ms Ada Lim", "Mr Sid Head", ALICE, BEN, "Nobody At All"):
        before = json.dumps(P.load(), sort_keys=True); n = len(H.read(kinds=["account"], limit=1000))
        r = c.post("/staff-reset", data=dict(name=name))
        assert r.status_code == 403 and RESET_REFUSED in r.data.decode(), name
        assert json.dumps(P.load(), sort_keys=True) == before and len(H.read(kinds=["account"], limit=1000)) == n, name
    person(ALICE, off=False)
    assert signed_in(ALICE).get("/staff-reset").status_code in (302, 401)          # a teacher
    c, _ = code_in(staff_code(ERIC)); assert c.post("/staff-reset", data=dict(name=ALICE)).status_code in (302, 401)
    h = signed_in("Ms Noor Head", group="hod", depts=[]).get("/staff-reset").data.decode(); assert RESET_NONE in h
```

(Names and fixtures may need small changes to fit the copied harness — e.g. the admin record shape `admin()` uses; keep every assertion's meaning. `PW.check_pw(hashed, pw)` is the check in `accounts/passwords.py`.)

- [ ] **Step 2: Run** — expect failures.
- [ ] **Step 3: Implement**: `_resettable(pub, d, me)` → the staff items a head may reset, in listing order: not `me`, not switched off, group not in `("leader", "hod", "sh")`, `extras.admin` false, and `set(item["depts"]) & set(record(d, me)["depts"])` non-empty. GET lists them (name, departments, a form posting `name` with a **Reset** button) or `RESET_NONE`. POST: inside `people.update`, recheck the name is in `_resettable` (else raise to answer 403 `RESET_REFUSED`), make a username with `make_username` when the record has none (taken = every record's lower-case username), set `pw=hash_pw(once)`, `must_change=True`, `n += 1`; after it, `lockout.clear(username)` and `_account_entry("reset", [name], [], text, where="Reset a password", depts=<their departments>)`. Answer the page with the name, username and temporary password, `no-store`.
- [ ] **Step 4: Run** the new file and the end-of-task suites; add the two routes to `GUARDS` as `('staff.reset',)`. Write the README section (who can look up a code, that each look-up is recorded; who a head can reset and who they cannot).
- [ ] **Step 5: Commit** `feat: an HOD or SH gives staff in their departments a new temporary password`.

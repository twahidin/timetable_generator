# Staff passwords and a student code page: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Staff sign in with a username and password only (once the lead turns staff codes off), students keep a code page of their own, the admin page makes every missing staff account and prints the slips, and teachers see only their own timetable, the classes and their own exam duties.

**Architecture:** A `staff_off` time in the accounts file's `ways` is the one switch; the sign-in routes, the session check and the published views all read it. New accounts and slips come from one admin route that returns the PDF and CSV in one answer and keeps only hashes. The narrow teacher view is a new `staff` view cut on the server in `ttgen/export.py html_data`, like the student views, plus a third exams level.

**Tech Stack:** Python 3 / Flask (`app.py`), reportlab for the PDF, plain-assert test scripts, the published page's vanilla JS (`ttgen/timetable_page.html`), the admin page (`static/admin.js`).

**Spec:** `docs/superpowers/specs/2026-11-26-staff-passwords-design.md` (approved 26 November 2026). Read it before any task.

## Global Constraints

- Deploying changes nothing for anyone until an admin turns staff codes off: every behaviour below marked "when staff codes are off" must be exactly today's behaviour while they are on.
- A temporary password exists only in the one HTTP answer that carries the PDF and CSV (`Cache-Control: no-store`). Only `passwords.hash_pw(...)` is stored. Never in the history, a log, the accounts file, a file on disk, or a test's printed output.
- Made-up names only in tests and commits ("Ms Alice Tan" style); the school is "CTSS" or "Sample School". Never print a real code, password or key.
- `ttgen/` and `skill/school-timetable-generator/scripts/ttgen/` are the same package: every change to `export.py` or `timetable_page.html` is made to both, and `cmp` shows them equal. SKILL.md's version line goes from `2026-11.10` to `2026-11.11` with one line saying what changed.
- `ttgen/timetable_page.html` keeps statements on long lines: use `/* */` comments inside a line, never `//`; after each edit cut the last `<script>` out and run `node --check` on it.
- Rights come from the records on every request; every new route has `@need(...)`.
- Words shown to people, exactly:
  - `STAFF_USE_PASSWORD = "Staff now sign in with a username and password. Ask the timetable committee for your slip."`
  - `STAFF_CODES_OFF = "Staff codes are off: staff sign in with a username and password."`
  - `TO_STUDENT = "Students: sign in with your code"`; `TO_STAFF = "Staff: sign in with your username"`
  - `NO_SLIPS = "Everyone has chosen their own password: there is no slip to print."`
- Builders and reviewers: NEVER run `git stash`, `git stash pop` or `git checkout -- <file>`; never `pkill`/`killall` by name or pattern (stop only processes you started, by PID). Commit trailer: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- New suite: `tests/test_staff_passwords.py`, run as `.venv/bin/python tests/test_staff_passwords.py`. Start it by copying the top of `tests/test_signin.py` (temp `DATA_DIR`, `SECRET_KEY`, the shared codes, `SECRETS`/`secret()`, `publish()`, `person()`, `account()`, `code_in()`, `pw_in()`, the `@t` runner and its final count line) and its last test `nothing_typed_reaches_the_history` (which must stay last and also cover every temporary password the suite made).

## Review Focus

1. **A teacher signed in with their code when the switch is pressed**: their next page goes to the sign-in page and their next API call answers 401 "Please sign in again." (test in Task 1).
2. **Names that make awkward usernames**: a title only ("Dr Ng"), an apostrophe or accent ("Mdm Siti Nur'aini", "Ms Zoë Lim"), two people with the same name letters: each gets a valid unique username of 3 to 40 of `[a-z0-9._-]` (test in Task 2).
3. **Printing twice**: the first slip's password stops working, the second's works, and while staff codes are on the teacher's code session is never ended by a slip (test in Task 2).
4. **Someone on a committee whose Exams and events date has passed**: counts as a plain teacher (narrow view), not as a committee member (test in Task 4).
5. **Two teachers in a row**: the cached published page for one is never served to the other, and an executive with no lessons gets no My timetable tab and a 403 on any `/pdf/teachers/...` (test in Task 4).

---

### Task 1: The staff codes switch

**Files:**
- Modify: `accounts/people.py` (`blank`, `_fill`, new `staff_codes_off`)
- Modify: `app.py` (`_check`, `login`, `_ways`, new route `/api/admin/staff-codes`, the relief code slip and CSV routes near lines 1720-1745)
- Create: `tests/test_staff_passwords.py`

**Interfaces:**
- Produces: `people.staff_codes_off(data) -> bool`; `data["ways"]["staff_off"]` is a time (float) or `None`; `_ways()` gains `staff_codes=dict(off=<time or None>, waiting=<int>)` where `waiting` counts staff in `people.staff(pub, data)` who are not switched off and have not chosen a password (no `pw`, or `must_change`); POST `/api/admin/staff-codes` body `{"off": bool}` → `_ways()`.

- [ ] **Step 1: Write the failing tests** in `tests/test_staff_passwords.py`:
  - `staff_codes_are_on_until_turned_off`: fresh accounts file → `P.staff_codes_off(P.load()) is False`; a teacher's code signs in and lands on `/home` as today.
  - `turning_staff_codes_off_refuses_a_staff_code`: an admin (`account(..., group="leader", extras={"timetable": True, "admin": True})`) posts `{"off": True}` → 200 and `json["staff_codes"]["off"]` is a number; then `code_in(staff_code(ALICE))` → 401, body contains `STAFF_USE_PASSWORD`, `strikes() == 1`, and the last signin history entry has `ok` False and `reason == "staff code after staff codes were turned off"`.
  - `a_student_code_and_a_password_still_work_when_staff_codes_are_off`: student code → 302 to `/me`; a password account → 302.
  - `an_open_staff_code_session_ends_when_staff_codes_are_turned_off` (Review Focus 1): sign in with Alice's code, turn off, then `c.get("/home")` → 302 to `/login`, and `c.get("/api/exams/my-duties")` → 401 with `{"error": "Please sign in again."}`.
  - `turning_them_on_again_lets_a_staff_code_in`: `{"off": False}` → `off is None`; Alice's code signs in.
  - `the_switch_is_recorded`: entries with text `"Staff codes turned off"` and `"Staff codes turned on"`, `what == "staff-codes"`, made by the admin.
  - `a_teacher_cannot_press_the_switch`: Alice signed in by code posting to the route → 401.
  - `relief_code_slips_are_refused_when_staff_codes_are_off`: as the admin, `GET /api/relief/code-slips.pdf` and the codes CSV route → 409 with `STAFF_CODES_OFF`.
  - `waiting_counts_staff_without_a_chosen_password`: with 4 published teachers, one with a chosen password and one with `must_change=True` → `staff_codes["waiting"] == 3`.

- [ ] **Step 2: Run** `.venv/bin/python tests/test_staff_passwords.py`. Expected: fails on `staff_codes_off` not defined.

- [ ] **Step 3: Implement.**
  - `people.blank()` ways gets `"staff_off": None`; `_fill` copies `w["staff_off"]` when it is an int or float (not bool), else `None`. `staff_codes_off(data)` is `data["ways"]["staff_off"] is not None`.
  - `_check`: in the `name is not None` branch, a session with `v == "code"` (this includes relief stage 1's `role == "staff"`) ends with `_end()` when `people.staff_codes_off(data)`.
  - `login()`: after `access.match`, when `r == "staff"` and staff codes are off: `limiter.fail(addr)`, `_record_signin(False, "code", reason="staff code after staff codes were turned off")` (no name: it was typed), return the code page with `STAFF_USE_PASSWORD`, 401.
  - Route `POST /api/admin/staff-codes`, `@need("admin")`, shaped like `admin_shared_off` (`_admin_off`, `_body`, `Refused(UNREAD_CHANGE)` for a non-bool, keep the first off time when pressed twice). History through `_account_entry("staff-codes", [], [dict(name="Staff codes", field="off", was=was, now=now)], "Staff codes turned off" | "Staff codes turned on", by_=by_)` only when the state changed.
  - The relief code slip PDF and CSV routes return `STAFF_CODES_OFF, 409` when staff codes are off.

- [ ] **Step 4: Run** the new suite, then `tests/test_signin.py`, `tests/test_admin.py`, `tests/test_accounts.py`, `tests/test_relief.py`. Expected: all pass.

- [ ] **Step 5: Commit** `feat: a switch that turns staff codes off`.

### Task 2: Make accounts and print slips

**Files:**
- Create: `accounts/slips.py`
- Modify: `app.py` (new route `/api/admin/staff-slips`)
- Test: `tests/test_staff_passwords.py`

**Interfaces:**
- Consumes: Task 1's `staff_codes_off`.
- Produces: `slips.make_username(name: str, depts: list[str], taken: set[str]) -> str`; `slips.slips_pdf(school: str, rows: list[dict], url: str, out) -> None`; `slips.slips_csv(rows: list[dict]) -> str`. A row is `dict(name, depts, username, password)`. POST `/api/admin/staff-slips` body `{"names": null | [str], "preview": bool}` → preview: `{"lines": [str], "count": int}`; made: `{"pdf": <base64 str>, "csv": <str>, "count": int}` with `Cache-Control: no-store`.

- [ ] **Step 1: Write the failing tests:**
  - `usernames_from_names` (Review Focus 2): `make_username("Ms Alice Tan", [], set()) == "alicetan"`; a leading title (`mr`, `mrs`, `ms`, `mdm`, `miss`, `dr`, `mx`, any case, with or without a dot) is dropped when a name is left after it; `make_username("Dr Ng", ["Science"], set())` is 3 to 40 of `[a-z0-9._-]` (here `"ngs"`: the department's first letters fill it to 3; with no department, `"ng"` + `"staff"` cut to fit); `"Mdm Siti Nur'aini"` → `"sitinuraini"`; `"Ms Zoë Lim"` → `"zoelim"` (accents folded with `unicodedata` NFKD); `make_username("Ms Alice Tan", [], {"alicetan"}) == "alicetan2"` and with `{"alicetan", "alicetan2"}` → `"alicetan3"`; a 60-letter name gives 40 characters, and its clash form is still at most 40.
  - `the_preview_counts_and_changes_nothing`: 4 teachers: one with no record, one with a username and no password, one with `must_change=True`, one with a chosen password. Preview with `names: null` → `count == 3`; `lines == ["2 staff have no account yet: each gets a username made from their name and a temporary password.", "1 has a temporary password from an admin that they have not used yet (<name>): they get a new one on this slip.", "1 already chose their own password: no slip."]` (`have` for counts above 1 in the first two lines: "2 have a temporary password …"); the accounts file is byte-for-byte unchanged.
  - `making_slips_makes_accounts`: made with `names: null` → `count == 3`; `base64` decodes to bytes starting `%PDF`; the CSV starts with a BOM, its header row is `Name,Department,Username,Temporary password`, and it has 3 rows; for each row the record has that username, `must_change` True, and `PW.check_pw(rec["pw"], row_password)` is True; the person with a chosen password is untouched (same `pw`, same `n`); a person who already had a username keeps it.
  - `a_slip_password_signs_in_and_asks_for_a_new_one`: `pw_in(username, password)` → 302 to `/account/password`.
  - `printing_twice` (Review Focus 3): make, make again → the first password gives `NO_MATCH`, the second works; with staff codes on, a code session of the same teacher opened before both prints still opens `/home` (its `n` was not raised).
  - `ticked_people_with_a_chosen_password_are_named_and_signed_out`: preview with `names: [CARA]` where Cara has a chosen password → a line `"<CARA> has chosen a password: their slip gives a new temporary one and their old password stops working."`; made → her `n` went up by one, her old password fails, her open password session ends.
  - `nothing_to_print`: everyone has chosen → preview `count == 0`, `lines == [NO_SLIPS]`; made → 400 with `NO_SLIPS`.
  - `unknown_and_switched_off_names`: a name not on staff → 400 with `NOT_STAFF.format(name)`; a switched-off person in `names` gets no slip and a line `"<name> is switched off: no slip."`.
  - `only_an_admin_prints`: a teacher by code → 401; the answer has `Cache-Control: no-store`.
  - `the_history_says_how_many_and_never_a_password`: one entry, `what == "slips"`, `people` the names that got a slip, text `"Printed sign-in slips for 3 staff: 2 new accounts"` (and `"; 1 had chosen a password"` when so); add every temporary password from this suite to `SECRETS` so the last test checks the history and the accounts file.

- [ ] **Step 2: Run** the suite. Expected: fails on `accounts.slips` missing.

- [ ] **Step 3: Implement.**
  - `make_username` as the tests pin; `taken` holds lower-case usernames.
  - `slips_pdf` draws like `relief/codes.py slips_pdf` (10 to an A4 page, a new page per first department, dashed cut lines, `_fit` for long text). Page header `f"{school} · sign-in slips · {dept or 'No department'} · cut along the dashed lines"`. On each slip: `f"{school} · your sign-in"`, the name (bold), the departments, `Username` with the username and `Temporary password` with the password (Courier-Bold), then `f"Go to {url}, sign in, then choose your own password."` and `"Keep this slip to yourself until you have."`.
  - `slips_csv` as `relief/codes.py codes_csv` (BOM first, its guard for a cell starting with a formula character).
  - The route, `@need("admin")`, `_admin_off()` first. Who: with `names` null, everyone in `people.staff(pub, d)` not switched off who has not chosen a password (chosen = `pw` set and not `must_change`); with a list (at most 200, else `Refused("Print slips for at most 200 people at a time.")`), those people. Rows in `people.listing` order (first department, then name). Passwords from `passwords.one_time()`, hashes made before `_update_as`. Inside the update: a username kept or made (`taken` from every record's username), `pw` the hash, `must_change` True, and `n + 1` only for a person who had chosen a password. After it: `lockout.clear(username)` for each; the history entry; PDF and CSV made from the rows in memory; `url = request.host_url.rstrip("/")`.

- [ ] **Step 4: Run** the new suite, `tests/test_admin.py`, `tests/test_signin.py`. Expected: all pass.

- [ ] **Step 5: Commit** `feat: make staff accounts and print their sign-in slips`.

### Task 3: The student page and the front page

**Files:**
- Modify: `app.py` (`login_page`, `_code_page`, `_password_page`, `login`, new `GET/POST /student`, `code_slips`)
- Test: `tests/test_staff_passwords.py`

**Interfaces:**
- Consumes: `people.staff_codes_off`.
- Produces: `_code_page(msg="", student=False)`; the POST handler shared by `/login` and `/student`.

- [ ] **Step 1: Write the failing tests:**
  - `while_staff_codes_are_on_the_front_page_is_as_today`: `GET /login` has the code box (`name="code"`) and the link to `/login/password`.
  - `when_staff_codes_are_off_the_front_page_is_the_username_page`: `GET /login` has `name="username"` and `name="password"`, a link to `/student` with `TO_STUDENT`, and no `name="code"`.
  - `the_student_page`: `GET /student` has the code box, the label `"Your personal code (on the slip from the school)"`, `form action="/student"`, and a link with `TO_STAFF` to `/login/password` while staff codes are on and to `/login` when off. `POST /student` with a student code → 302 to `/me`; a wrong code → 401 on the student page (its `action="/student"`); a staff code when off → 401 with `STAFF_USE_PASSWORD`; a shared code that is on → signs in as today.
  - `student_slips_print_the_student_page`: the PDF from `/api/code-slips.pdf` holds the text `"/student"` (check by calling `ttgen.export.code_slips_pdf` through the route with a patched function that records its `url` argument).
  - `post_login_still_takes_codes_when_off`: `POST /login` with a student code → 302 to `/me`.

- [ ] **Step 2: Run** the suite. Expected: the new tests fail.

- [ ] **Step 3: Implement.** `login_page()` returns `_password_page()` when staff codes are off, else `_code_page()`. `_password_page`'s back link is `("/student", TO_STUDENT)` when off (else as now). `_code_page(student=True)` uses `CODE_LABEL`, posts to `/student`, links `TO_STAFF`. The POST handler takes the page to draw errors on. `code_slips()` passes `request.host_url.rstrip("/") + "/student"`.

- [ ] **Step 4: Run** the new suite and `tests/test_signin.py`. Expected: all pass.

- [ ] **Step 5: Commit** `feat: a code page for students; the front page follows the staff codes switch`.

### Task 4: The narrow published timetable for teachers

**Files:**
- Modify: `accounts/rights.py` (new `sees_all`)
- Modify: `app.py` (`TABS`, `files_for`, `timetable`, `pdf_one`, `files`, new `_narrow`, `_my_teacher`)
- Modify: `ttgen/export.py` and `skill/school-timetable-generator/scripts/ttgen/export.py` (`html_data`)
- Modify: `ttgen/timetable_page.html` and the skill copy
- Modify: `skill/school-timetable-generator/SKILL.md` (version line)
- Test: `tests/test_staff_passwords.py`, `tests/timetable_page.test.js`

**Interfaces:**
- Consumes: `people.staff_codes_off`.
- Produces: `rights.sees_all(person: dict | None, today: datetime.date | None = None) -> bool` (True for group leader, hod or sh, or the extras timetable, relief or admin, or an exams date today or later); `app._narrow() -> bool` (staff codes off, not `has("committee")`, and either a person signed in by name with `sees_all` False or the shared teacher code); `app._my_teacher() -> str | None` (the signed-in person's name when it is in the published `teacher_ix`). `html_data(m, "staff", app=...)`; app config key `me`.

- [ ] **Step 1: Write the failing tests** (Python):
  - `sees_all_rules` (Review Focus 4): a teacher → False; hod → True; a teacher with `exams` yesterday → False, today → True; relief tick → True.
  - `nothing_narrows_while_staff_codes_are_on`: a teacher by password gets the cached view key `("view", "teacher", "/home")` as today.
  - `a_teacher_sees_their_own_and_the_classes`: staff codes off, Alice by password: `GET /timetable` → the page's DATA has `app.mode == "staff"`, `app.tabs == ["classes", "teachers", "exams"]`, `app.me == ALICE`, `students == []`, `rooms == []`, every teacher row has `""` in its department place. `/pdf/teachers/<ALICE>` → 200; `/pdf/teachers/<BEN>`, `/pdf/rooms/<any>`, `/pdf/students/S001` → 403; `/pdf/classes/1A` → 200; `/files/book/teachers` → 404 and `/files/book/classes` as today.
  - `two_teachers_in_a_row` (Review Focus 5): Alice's page, then Ben's in another client: Ben's DATA has `me == BEN`.
  - `an_executive_has_no_my_timetable` (Review Focus 5): a person not on the timetable, group executive: `app.tabs == ["classes", "exams"]`, `me` absent or None, any `/pdf/teachers/...` → 403.
  - `management_and_committees_see_all`: an HOD and a teacher with the relief tick get mode `"teacher"` and today's tabs.
  - `the_shared_teacher_code_is_narrow_when_staff_codes_are_off`: turned on again, it gets mode `"staff"` with tabs `["classes", "exams"]`.
  (Use real `render_html` for these: give `publish()` a model `render_html` can draw, as the published test views of `tests/test_routes.py` do, or drop the pre-filled view texts for these tests.)

  And in `tests/timetable_page.test.js`, a test with `app = { mode: "staff", tabs: ["classes", "teachers", "exams"], me: "Mr Ben Ong", ... }`: the tab bar reads `My timetable` and not `Teachers`; the teachers list shows only `Mr Ben Ong`; with no hash the first view is Mr Ben Ong's timetable.

- [ ] **Step 2: Run** both. Expected: fail.

- [ ] **Step 3: Implement.**
  - `html_data`: `"staff"` takes the `"student"` cuts (teacher departments and allowances blank, subject departments blank, checks emptied, rooms emptied) and `students = []`.
  - Page: in mode `"staff"`, the `teachers` tab is labelled `My timetable` with no count, its list holds only `APP.me`, and the opening view (no hash) is `teachers` / `APP.me`. Both copies, `cmp` equal, `node --check` on the cut script.
  - `TABS["staff"] = ["classes", "teachers", "exams"]` (without `"teachers"` when `_my_teacher()` is None); `files_for("staff") = [["Class PDFs", "/files/book/classes"]]`; `timetable()` uses `r = "staff"` when `_narrow()` (home and label worked out as for a teacher today), the cache key `("view", "staff", home, me)`, `view = "staff"`, `me` in the app config.
  - `pdf_one`: when `_narrow()`, only `classes` and `teachers` with `key == _my_teacher()`, else 403. `files`: when `_narrow()`, the book allows `("classes",)` only.
  - SKILL.md: `Skill version: 2026-11.11` and one line: the published page has a `staff` mode (own timetable and classes).

- [ ] **Step 4: Run** the new suite, `node tests/timetable_page.test.js`, `tests/test_routes.py`, `tests/test_signin.py`, `smoke`. Expected: all pass.

- [ ] **Step 5: Commit** `feat: teachers see their own timetable and the classes once staff codes are off`.

### Task 5: Exams for a teacher: own duties and the classes

**Files:**
- Modify: `exams/published.py` (`day`)
- Modify: `app.py` (`_published_reader`, `exams_day`, `exams_published_list`)
- Test: `tests/test_exams.py` (or the new suite, using `tests/test_exams.py`'s fixture for a made exam)

**Interfaces:**
- Consumes: `app._narrow()`.
- Produces: `exams_published.day(pub, cal, scheds, date, full, only=None)`; `_published_reader() -> "full" | "staff" | "student" | None`.

- [ ] **Step 1: Write the failing tests:** on a day with a made exam where Ms A and Mr B invigilate: `day(..., full=False, only="Ms A")["exams"]` has `teachers == {"Ms A": [...]}` (her duty with its room and role) and `rooms == {}`; `full=False, only=None` gives `teachers == {}` as now; `full=True` unchanged. Through the routes with staff codes off: a teacher's `/api/day` (the route of `exams_day`) gives only their own teacher entries and no rooms; `/api/published/exams` gives the student-level listing (no teacher names); a print → 403 with `ONLY_STAFF_PRINTS`; an HOD gets `full`.

- [ ] **Step 2: Run.** Expected: fail.

- [ ] **Step 3: Implement.** In `day`, when not `full` and `only` is set, collect only `only`'s teacher entries (duties and events) and no rooms. `_published_reader()` returns `"staff"` when `_narrow()`. `exams_day` passes `only=who()["name"] if reader == "staff" and who() else None`.

- [ ] **Step 4: Run** `tests/test_exams.py`, `tests/test_exams_relief.py`, the new suite. Expected: all pass.

- [ ] **Step 5: Commit** `feat: a teacher's Exams tab shows their own duties and the classes`.

### Task 6: The admin page

**Files:**
- Modify: `static/admin.js` (`drawWays`, the tick bar, `printSlips` neighbours)
- Test: `tests/adminview.test.js`

**Interfaces:**
- Consumes: `/api/admin/ways` (`staff_codes`, `students` count to add to `_ways()`: `students=len(pub["model"]["students"])` or 0), `/api/admin/staff-codes`, `/api/admin/staff-slips`.

- [ ] **Step 1: Write the failing tests** in `tests/adminview.test.js` from a ways answer: rows in order `Student codes` (`On · 1,284 students`, a Print slips button), `Staff codes` (`On · 92 staff without a password yet`, Turn off; when off, `Off since 26 Nov 2026` in the green style of the shared rows and Turn on), `Username and password` (`On · 7 of 99 staff`, a `Make accounts and print slips` button), then the existing rows. Turn off shows the question `Staff codes stop working at once, on every device. 12 staff have not signed in with a password yet: they will need their slip.` before posting. The tick bar has `Print username slips`; `Print their code slips` is hidden when staff codes are off.

- [ ] **Step 2: Run** `node tests/adminview.test.js`. Expected: fail.

- [ ] **Step 3: Implement.** Make accounts and the tick-bar button post a preview, show its lines with Print and Cancel, then post `preview: false` and save two files from the answer with object URLs: `sign-in slips.pdf` and `sign-in slips.csv`; the passwords are never put in the page's text. A 401 takes the same path as `printSlips`.

- [ ] **Step 4: Run** `node tests/adminview.test.js`, `node --check static/admin.js`, `tests/test_admin.py`. Expected: pass.

- [ ] **Step 5: Commit** `feat: the Ways in tab makes accounts, prints slips and turns staff codes off`.

### Task 7: Finish

- [ ] README: the sign-in section says how staff and students sign in after the switch and what the lead does (print slips, hand them out, turn staff codes off).
- [ ] A notes file `docs/superpowers/plans/2026-11-26-staff-passwords-notes.md`: the calls made (titles dropped from usernames, the CSV, shared codes on `/student`, no admin check on the switch because only a password admin can press it), what was not tried in a browser.
- [ ] Every suite, quick and `--full` (as in the project's list), `node tests/*.test.js` one by one, `node --check static/app.js`, `cmp` of both ttgen copies. Expected: all pass.
- [ ] Browser check on a scratch server (own hostname, made-up data): make accounts and print, sign in with a slip, choose a password, turn staff codes off, the student page, a teacher's narrow page and Exams tab, with real pointer clicks.
- [ ] Commit `docs: staff passwords notes and README`.

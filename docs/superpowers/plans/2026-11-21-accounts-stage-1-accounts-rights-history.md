# Accounts stage 1: accounts, rights and the history — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Everyone who signs in is a known person with rights by group and extras, checked on the server for every
route; committee and management sign in with a username and password; heads change only their own departments; every
change is recorded in a history the committee can read; the named admins run everything from an admin page.

**Architecture:** A new package `accounts/` holds the people records (`people.py`), the rights table (`rights.py`) and
passwords (`passwords.py`). A new module `history.py` appends one JSON line per change to a monthly file and reads it
back. `store.apply_changes` and `store.replace_setup` record setup changes with who made them; `sync.head_split` gains
the head's departments. `app.py` replaces role checks with rights (`@need(*rights)`), a session model for named people,
the layout-A sign-in page, the username page, the tiles page, the admin API and the history API. Two new plain-JS pages
(`static/admin.html`, `static/history.html`); the committee page learns who is signed in and greys other departments'
rows for a head. Relief's three lists (Management, Relief team, extra staff) move into the accounts.

**Tech Stack:** Python 3 / Flask 3.0.3 (one gunicorn worker), Werkzeug's `generate_password_hash` (scrypt, installed
with Flask: no new dependency), plain JavaScript, plain-assert test scripts.

**Spec:** `docs/superpowers/specs/2026-11-21-accounts-and-history-design.md` (approved 21 Nov 2026), stage 1 of
"Stages", and every section it names. Mockups: `docs/superpowers/specs/2026-11-21-accounts-and-history-mockups.html`
tabs 1 to 4 (the "Since you last signed in" panel and Put back are stage 2: leave them out).

**Branch:** `accounts-stage-1`, in a new worktree `~/Developer/tt-generator/tt-accounts-stage-1` cut from `origin/main`
at build time, with the design, the mockups and this plan committed first (Task 0).

## Global Constraints

- The repo is public: the school is only ever "CTSS"; tests, samples and docs use made-up names only. No school domain.
- Never print, log, commit or record in the history a password, a one-time password, a personal code, a shared code,
  `SECRET_KEY` or `ADMIN_RECOVERY_CODE`. Tests make random values with `secrets.token_hex`.
- No model call anywhere. Tests set `AI_API_KEY=""` as `tests/test_relief.py` does.
- Tests are plain-assert scripts run as `.venv/bin/python tests/<name>.py`, `DATA_DIR` a fresh temp folder set before
  `import app`. `.venv` in the worktree is a symlink to `../timetable_generator/.venv`.
- Files are written atomically with `store.write_json`. Accounts live in `os.path.join(store.DATA, "accounts")`, the
  history in `os.path.join(store.DATA, "history")`.
- Accounts (password sign-in, the admin page, first admin) are refused while `SECRET_KEY` is not set; shared codes then
  work exactly as today.
- A person is identified by their name, as relief does (`session["who"]`, relief's "set by").
- Rights are read from the records on every request, never from the cookie.
- Strong sign-in = `password` (Google arrives in stage 3). Rights `committee`, `setup`, `admin`, `history`, `codes`
  need a strong sign-in (the lead: a personal code opens "All but setup and admin").
- Copy is plain words in the app's style; exact texts in quotes in this plan are used verbatim.
- Builders and reviewers: NEVER run `git stash`, `git stash pop` or `git checkout -- <file>`. After each task,
  `git stash list` must show the same entries as before it.
- In `static/*.js`, never put a `//` comment in the middle of a long line; use `/* */`.
- Commits end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **A head adds a row from each "Add …" bar on step 5** (whole-class subject, teaching group, band, a teacher from
   the department map). The add operation the page sends must carry a subject of their department and be accepted;
   only other departments' rows are refused. (Test in Task 3 with operation shapes copied from `static/app.js` and
   `static/groups.js`; browser check in Task 11.)
2. **A publish while people are signed in.** A password session never depends on the published timetable; a code
   session survives the moment nothing is published (a publish swaps folders), as relief's does today; a teacher
   dropped by the publish loses their code session with "Code no longer valid". (Task 5.)
3. **Ticking several people including the last admin** for "Switch off" or "Set group: Teacher": the whole change is
   refused with one sentence naming the last admin, and nothing is applied. (Task 8.)
4. **A shared code turned off while sessions with it are open:** the next request of each ends the session. (Task 5.)
5. **A history file with a half-written last line** (the app stopped mid-write): reading skips the broken line, and the
   next entry starts on a new line. (Task 2.)

---

## File structure

| File | What it is |
|---|---|
| `accounts/__init__.py` | empty package marker |
| `accounts/passwords.py` | password rules, hashing, one-time passwords, the per-account lockout |
| `accounts/people.py` | the people records file, the merged staff list, lookups, migration from relief, the exams end-date sweep |
| `accounts/rights.py` | the rights table: what a person signed in a given way may do |
| `history.py` | the history: append, read with filters, prune, counts; entries for setup operations |
| `sync.py` | heads limited to their departments; band changes judged whole |
| `store.py` | setup changes and replacements recorded with who |
| `app.py` | sessions, `@need(*rights)`, sign-in pages, tiles, admin and history APIs, history hooks |
| `relief/settings.py`, `static/relief-settings.js`, `static/relief.js` | the three lists read from the accounts |
| `static/admin.html`, `static/admin.js` | the admin page (Staff, Students, Ways in, History link) |
| `static/history.html`, `static/history.js` | the history page |
| `static/app.js`, `static/index.html` | who is signed in; a head's other-department rows greyed |
| `tests/test_accounts.py`, `tests/test_history.py`, `tests/test_signin.py`, `tests/test_routes.py`, `tests/test_admin.py` | new suites |
| `README.md` | accounts, the Railway variables, the first admin |

---

### Task 0: The branch

- [ ] **Step 1:** `git -C ~/Developer/tt-generator/timetable_generator fetch origin`, then
  `git -C ~/Developer/tt-generator/timetable_generator worktree add -b accounts-stage-1 ../tt-accounts-stage-1 origin/main`;
  `ln -s ../timetable_generator/.venv ~/Developer/tt-generator/tt-accounts-stage-1/.venv`.
- [ ] **Step 2:** Copy the design, the mockups and this plan from `~/Developer/tt-generator/tt-accounts-design/docs/superpowers/`
  into the same paths; commit `git add docs && git commit -m "Accounts: design, mockups and stage 1 plan"`.
- [ ] **Step 3:** Note whether `exams/` exists on the branch (PR #79 merged before this build): it decides Task 13.

---

### Task 1: People, rights and passwords

**Files:** Create `accounts/__init__.py`, `accounts/passwords.py`, `accounts/people.py`, `accounts/rights.py`,
`tests/test_accounts.py`.

**Interfaces — Produces:**
- `accounts.passwords`:
  - `problem(pw: str, username: str = "", name: str = "") -> str | None` — `"Use at least 10 characters."`;
    `"Don't use your username or your name."` (compared ignoring case, spaces, dots); `"That password is too common.
    Choose another."` (lower-cased in `COMMON`). Else `None`.
  - `COMMON: frozenset[str]` — about 100 of the most common passwords of 10+ characters, lower-cased, inline.
  - `hash_pw(pw: str) -> str` (`werkzeug.security.generate_password_hash`, default method) and
    `check_pw(hashed: str | None, pw: str) -> bool` (with `None`, still checks against a fixed dummy hash, returns False).
  - `one_time() -> str` — 12 letters from `access.ALPHABET` by `secrets`, as `XXXX-XXXX-XXXX`.
  - `class Lockout(n=5, window=900)`: `blocked(key) -> bool`, `fail(key)`, `clear(key)`; in memory, thread-safe.
- `accounts.people`:
  - `PATH = os.path.join(store.DATA, "accounts", "people.json")`
  - `GROUPS = ("committee", "leader", "hod", "sh", "teacher", "executive")`; `LABELS = {"committee": "Timetable committee",
    "leader": "School leader", "hod": "HOD", "sh": "SH", "teacher": "Teacher", "executive": "Executive"}`;
    `MANAGEMENT = {"leader", "hod", "sh"}`; `HEADS = {"hod", "sh"}`; `SHARED = ("committee", "head", "teacher", "student")`.
  - `blank() -> dict`: `{"people": {}, "ways": {"off": {r: None for r in SHARED}, "recovery_used": []}, "moved": None}`.
  - `record(data, name) -> dict`: the record or the defaults `{"group": None, "depts": [], "extras": {"relief": False,
    "exams": None, "admin": False}, "username": None, "pw": None, "must_change": False, "google": None, "code_n": 0,
    "n": 0, "off": False, "added": False, "note": "", "signins": []}` (a copy; not stored until saved).
  - `load() -> dict` (missing or unreadable file → `blank()`, missing keys filled) and `update(fn) -> Any`: under one
    lock, load, `fn(data)` mutates and returns a result, save, return the result. The only write path.
  - `staff(pub, data=None) -> list[dict]`: `relief.people.people(pub, [])` plus records with `added` or a `username`
    that are not in it; each item is relief's dict plus `group` (record's, else `"teacher"` for someone on the
    published timetable, `"executive"` for an added person), `depts` (record's when the group is a head's, else
    relief's), `extras`, `username`, `off`, `has_password` (bool), `last` (newest of `signins` or None). Never `pw`.
  - `find(name, pub, data=None) -> dict | None`: the `staff` item for that name, plus `pw`, `n`, `must_change`; `None`
    when the name is neither in `staff` nor a record with a username.
  - `by_username(data, username) -> tuple[str | None, dict | None]` (case-insensitive, trimmed).
  - `admins(data) -> list[str]`: committee group, `extras.admin`, not off.
  - `sweep(data, today: datetime.date) -> list[str]`: clears `extras.exams` whose date is before today; returns names.
    The end date is the last day it works.
- `accounts.rights`:
  - `STRONG = {"password", "google"}`
  - `rights(person: dict | None, via: str, shared: str | None = None, today: datetime.date | None = None) -> frozenset[str]`
    by this table (a switched-off person gets nothing):

| Who | Rights |
|---|---|
| shared `committee` | committee, setup, timetable, files, history, codes, relief.settings, relief.save |
| shared `head` | setup, timetable, files |
| shared `teacher` | timetable, files |
| shared `student` | timetable |
| via `personal` (a student's own code) | own |
| any person | timetable, files |
| teacher, leader, hod, sh, committee (any way in) | + relief |
| leader, hod, sh | + relief.plan, relief.settings |
| committee | + relief.settings, relief.save |
| extra Relief team | + relief, relief.settings, relief.save |
| extra Exams and events, date ≥ today | + exams |
| committee, signed in strongly | + committee, setup, history, codes |
| hod, sh, signed in strongly | + setup |
| committee with extra Admin, signed in strongly | + admin |

- [ ] **Step 1: Write the failing tests** in `tests/test_accounts.py` (style of `tests/test_relief.py`):
  `password_rules` (9 letters refused with the exact sentence; username `daniel.wong` and name `Daniel Wong` refused
  as `DanielWong` and `daniel.wong`; a `COMMON` member refused; a good one passes); `hash_round_trip` (hash differs
  from the password, `check_pw` true for it, false for another, false for `None`); `one_time_shape`
  (`^[2-9A-HJ-KM-NP-Z]{4}(-[2-9A-HJ-KM-NP-Z]{4}){2}$`, two calls differ); `lockout` (5 fails block, `clear` unblocks,
  the window passes with `time` patched); `rights_table` (one assert per row above, plus: committee via `code` has
  relief and timetable but not committee, setup, admin, history, codes; hod via `code` has relief.plan but not setup;
  exams date yesterday gives no exams, today gives exams; an off person gives `frozenset()`); `staff_merges_records`
  (with `relief.people.fake_pub`: a published teacher with no record is group teacher; an added record appears as
  executive; a record's `pw` never appears in `staff`; `find` of a committee record with a username who is not
  published still returns them); `update_is_the_only_write` (two `update` calls in threads both land);
  `sweep_ends_exams` (date before today cleared and named, today kept).
- [ ] **Step 2: Run** `.venv/bin/python tests/test_accounts.py` — fails on the missing package.
- [ ] **Step 3: Implement** the three modules as specified.
- [ ] **Step 4: Run** it again — all pass; `.venv/bin/python tests/test_relief.py` still passes.
- [ ] **Step 5: Commit** `git add accounts tests/test_accounts.py && git commit -m "Accounts: people, rights and passwords"`

---

### Task 2: The history file

**Files:** Create `history.py`, `tests/test_history.py`.

**Interfaces — Produces** (`history.py`):
- `DIR = os.path.join(store.DATA, "history")`; `KEEP_MONTHS = 24`; `FORBIDDEN = {"password", "pw", "code", "once",
  "token", "secret"}` (keys dropped from any entry, at any depth, before writing).
- An entry is a dict; `add` sets `id` (`"h"` + 13-digit epoch ms + 3-digit counter), `ts` (epoch float) and `at`
  (`datetime.now().astimezone().isoformat(timespec="seconds")`). Common fields: `kind` (`"setup"`, `"setup-refused"`,
  `"setup-replaced"`, `"app"`, `"draft"`, `"relief"`, `"exams"`, `"account"`, `"signin"`), `who` (a name or None),
  `as` (what to show for who: the name, `"Shared committee code"`, `"Shared heads' code"`, `"Shared teacher code"`,
  `"Shared student code"`, `"The app"`, or `"Unknown"`), `via` (`"password"`, `"google"`, `"code"`, `"shared"`,
  `"personal"`, `"app"`, `"?"`), `where` (as shown on the page, e.g. `"Step 5 · Department map"`), `text` (the change
  in words). Kind `setup` adds `section`, `id`, `field`, `was`, `now`, `label`, `depts`, `op`, `v`, `batch`.
- `by_of(who: str | None, via: str, shared: str | None = None) -> dict` → `{"who", "as", "via"}`.
- `add(entry: dict) -> dict`, `add_many(entries: list[dict]) -> list[dict]` (one file write), under a lock, to
  `DIR/YYYY-MM.jsonl` of the entry's own time; each line ends with `"\n"`; before appending, if the file does not end
  with a newline, write one first (a half-written last line stays alone and is skipped by `read`).
- `read(who=None, where=None, dept=None, kinds=None, since=None, until=None, signins=False, before=None, limit=200) -> list[dict]`:
  newest first; `before` is an entry id to page past; unreadable lines skipped; `signins=False` leaves out kind
  `signin`; `dept` matches an entry whose `depts` holds it.
- `prune(today: datetime.date | None = None) -> int`: removes month files older than `KEEP_MONTHS` months; returns how many.
- `uses(days: int = 7, **match) -> int`: entries of the last `days` days whose fields equal `match`.
- `WHERE = {"venues": "Step 1 · Venues", "classes": "Step 2 · Classes", "subjects": "Step 3 · Subjects", "teachers":
  "Step 4 · Teachers", "roles": "Step 4 · Teachers", "lessons": "Step 5 · Department map", "blocks": "Step 5 · Groups
  and bands", "rules": "Step 6 · Configuration & constraints", "students": "Students", "combinations": "Students",
  "choices": "Students"}`; ops `school`, `day`, `top` → `"School & day"`.
- `row_label(section: str, row: dict | None) -> str`: the row's own name as its step shows it (lessons: level, subject
  and classes, `"Sec 3 Physics 3B"`; blocks: band name; teachers: name; others: their name field — read the field
  names in `ttgen/spec.py`). `"(gone)"` for None.
- `setup_entries(spec_before: dict, ops: list, by: dict, batch: str, v: int) -> list[dict]`: one kind-`setup` entry per
  operation, each judged on a working copy as the operations before it leave it (`sync.apply` one at a time): `was` =
  the field's value before (for `add`: None; for `del`: the whole row), `now` = after (for `del`: None; for `add`: the
  row), `depts` = the departments the row belongs to before and after (`sync.lesson_dept` for lessons; for a band, the
  departments of its lessons; for a teacher, `ttgen.spec.teacher_depts`), `text` like
  `"Sec 3 Physics 3B: teachers Grace Ong → Joseph Lim"`.

- [ ] **Step 1: Write the failing tests** in `tests/test_history.py`: `add_and_read_newest_first`; `forbidden_keys_dropped`
  (an entry with `password` and nested `{"code": ...}` is written without them); `half_line_skipped` (append
  `'{"kind": "set'` by hand, then `add` one entry: `read` returns only the good ones and the file's last line parses);
  `filters` (who, where, dept, kinds, since/until, signins hidden by default, `before` pages); `prune_two_years` (files
  for 25 and 23 months ago: one removed); `uses_counts_last_week`; `setup_entries_values` (with `ttgen.samples.secondary()`:
  a `set` of a lesson's teachers gives `was`/`now` and the lesson's `depts`; an `add` then a `set` on the new row in one
  batch both get entries and the second's `was` is the first's value; a `del` keeps the whole row in `was`).
- [ ] **Step 2: Run** `.venv/bin/python tests/test_history.py` — fails.
- [ ] **Step 3: Implement** `history.py` (it imports `sync` for `lesson_dept`, defined in Task 3: write that helper first
  in `sync.py` as `lesson_dept(spec, row) -> str`, the department of the row's subject on the subjects table, trimmed,
  first match by subject name; `""` when none).
- [ ] **Step 4: Run** it again — all pass; `.venv/bin/python tests/test_sync.py` still passes.
- [ ] **Step 5: Commit** `git add history.py sync.py tests/test_history.py && git commit -m "History: the change log file"`

---

### Task 3: Heads to their own departments

**Files:** Modify `sync.py` (`_head_why`, `head_split`, `head_may`, `_head_lessons_why`); Test `tests/test_sync.py`.

**Interfaces:**
- Consumes: `lesson_dept(spec, row)` (Task 2).
- Produces: `head_split(spec, ops, depts=None) -> (allowed, refused)`, `head_may(spec, ops, depts=None)` and
  `head_prepare(ops, depts=None) -> None` (below). `depts`
  `None` = today's behaviour (the shared heads' code); a list = that head's departments. `band_lessons(spec, block_row)
  -> list[dict]` (lessons whose `block` is the band's name and `level` its level).
- Sentences (verbatim): `OTHER_DEPT = "This row is another department's: only its head or the committee can change it."`;
  `NO_SUBJECT = "Choose a subject of your department for this row first."`; `BAND_OTHERS = "This band holds another
  department's groups: only the committee can rename or delete it."`; `BAND_NOT_YOURS = "This band holds none of your
  department's groups."`; `TEACHER_DEPT = "You can put a new teacher only in your own department."`

Rules with `depts` given, after today's rules (Class Parents first, exactly as now):
- A lesson operation is allowed only when `lesson_dept` of the row as it is and as the operation leaves it are both in
  `depts`; an `add` whose row's subject has no department or is empty gets `NO_SUBJECT`; otherwise `OTHER_DEPT`.
- A band (`blocks`): `add` allowed. Any other change to a band row allowed when `band_lessons` is empty or holds at
  least one lesson of `depts`, else `BAND_NOT_YOURS`. A **rename** (`set` of the band's `block` field) or a `del` of
  a band is judged **together with** the batch's lesson operations that set `block` on that band's lessons (from the
  old name, or to None/removed): all allowed when every lesson in the band is of `depts`, else all refused with
  `BAND_OTHERS`.
- Teachers: a `set` of `dept` to a department not in `depts` gets `TEACHER_DEPT`. New
  `head_prepare(ops, depts=None) -> None` takes over what `app.post_setup_changes` does to a head's teacher `add` today
  (`provisional = "Yes"`, `dept2` dropped) and, with `depts`, sets a `dept` not in `depts` to `depts[0]`; the app calls
  it in place of its own loop (Task 6).

- [ ] **Step 1: Write the failing tests** in `tests/test_sync.py`, on `ttgen.samples.secondary()` (departments `SC`,
  `MA`, ...): own lesson row changed — allowed; another department's — `OTHER_DEPT`; a row moved to another subject of
  another department — refused; an `add` from each Add bar shaped as `static/app.js` and `static/groups.js` send it
  (read the shapes there: whole-class subject, teaching group, band) with an own subject — allowed, with an empty
  subject — `NO_SUBJECT`; a new band `add` then a `set` of its classes in one batch — allowed; renaming a band of only
  own groups with its lessons' `block` sets — all allowed; renaming a shared band — all refused with `BAND_OTHERS`,
  nothing applied by `apply`; `head_prepare` on a teacher `add` with another department — `dept` becomes the head's,
  `provisional` "Yes", no `dept2`; `depts=None` —
  every existing head test unchanged.
- [ ] **Step 2: Run** `.venv/bin/python tests/test_sync.py` — new tests fail.
- [ ] **Step 3: Implement** the rules in `sync.py`.
- [ ] **Step 4: Run** `tests/test_sync.py`, `tests/test_parents.py`, `node tests/sync.test.js` — all pass.
- [ ] **Step 5: Commit** `git add sync.py tests/test_sync.py && git commit -m "Heads change only their own departments"`

---

### Task 4: Setup changes recorded with who

**Files:** Modify `store.py` (`apply_changes`, `replace_setup`, `restore`, `restore_point`, `copies`); Test
`tests/test_history.py`.

**Interfaces:**
- Consumes: `history.setup_entries`, `history.add_many`, `history.by_of` (Task 2).
- Produces: `apply_changes(ops, client, check=None, since=None, filter=None, by=None)` — `by` a `history.by_of` dict,
  default `history.by_of(None, "?")` (`as` `"Unknown"`). Under the same lock, before `sync.apply`: the allowed
  operations' entries (`setup_entries` on the spec as it was, one `batch` id for the call, `v` the new version); each
  refused one a kind-`setup-refused` entry with `op` and `why`; the Class Parents' operations a kind-`app` entry per
  operation (`as` `"The app"`, `follows` the batch id). `replace_setup(spec, why, by=None)` and `restore(copy_id,
  by=None)` add one kind-`setup-replaced` entry (`text` = `why`). `restore_point(why, by=None)` saves `by["as"]` in the
  copy as `who`; `copies()` returns `who` too.

- [ ] **Step 1: Write the failing tests**: an `apply_changes` with `by` writes one entry per allowed op with that `as`;
  a head's refused op writes `setup-refused` with the exact sentence; Class Parents ops come as `app` entries with
  `follows`; `replace_setup` writes `setup-replaced`; a copy made with `by` lists `who` in `copies()`.
- [ ] **Step 2: Run** — fails. **Step 3: Implement.** **Step 4: Run** `tests/test_history.py`, `tests/test_sync.py`,
  `tests/smoke.py` — all pass.
- [ ] **Step 5: Commit** `git add store.py tests/test_history.py && git commit -m "History: setup changes recorded with who"`

---

### Task 5: Signing in

**Files:** Modify `app.py` (access section, `setup_problems`, `/login`, new routes); Create `tests/test_signin.py`.
`setup_problems()` stops listing an unset shared code (`"COMMITTEE_CODE is not set …"` and the like) once an admin
exists; `access.py` is not changed (it must not import `accounts`).

**Interfaces:**
- Consumes: Task 1 (`people`, `rights`, `passwords`), Task 2 (`history.add`, `by_of`, `uses`).
- Produces (in `app.py`):
  - `who() -> dict | None` — the signed-in person (`people.find`), checked on each request: record not `off`,
    `session["n"] == person["n"]`, `session["exp"]` not passed (password sessions: 14 days from sign-in), and for a
    `code` session the person still in `people.staff(pub)` (when nothing is published the session stays, as relief's
    does). A failed check clears the session. Sessions from relief stage 1 (`role == "staff"`, `who` set) count as
    `via == "code"`, `n == 0`.
  - `via() -> str`, `shared() -> str | None` (`session["role"]` for shared codes, as today), `rights() ->
    frozenset` (cached on `flask.g`), `has(right) -> bool`, `by() -> dict` (`history.by_of` of the session).
  - `need(*rights)` — passes when `rights()` holds any of them; sets `inner._need = rights`; refusal: 401 JSON
    `{"error": "Please sign in again."}` on `/api/`, `/pdf/`, `/files/`, else redirect `/login`; a person with
    `must_change` is sent to `/account/password` (API: 403 `{"error": "Choose a new password first."}`). A shared
    session whose code is turned off (`people.load()["ways"]["off"][role]`) is cleared.
  - Session keys: shared `role`; student `role = "personal"`, `sid`; person `who`, `via`, `n`, `exp`.
- Routes:
  - `GET /login`: layout A (mockup tab 1) without the Google button: the school name, one box "Your personal code
    (on the slip from the school)", "Open", the link "Committee and management: sign in with your username →"
    (`/login/password`), `setup_problems()` warnings. `?as=` is accepted and ignored.
  - `POST /login` (`code`): `access.match` with personal and staff codes (staff from `people.staff(pub)`, not off). A
    shared code turned off counts as wrong. Wrong: limiter strike, `"That code does not work. Check it and try again."`,
    401. Off person: `"This account is switched off. Ask the timetable committee."`, 403, no strike. Then session and
    redirect: person → `/home`; personal → `/me`; shared committee or head → `/`; shared teacher or student →
    `/timetable`.
  - `GET|POST /login/password` (`username`, `password`): refused while `SECRET_KEY` is unset (`"Accounts need SECRET_KEY
    in Railway variables."`). Limiter by address and `Lockout` by username; the same answer for an unknown username
    and a wrong password: `"That username and password do not match."` (401); locked: `"Too many wrong tries. Wait 15
    minutes and try again."` (429). Success clears the lockout, appends the time to `signins` (keep the last 2),
    session, redirect `/account/password` when `must_change` else `/home`.
  - `GET|POST /account/password` (`current`, `new`, `again`; a person with a username): `passwords.problem`;
    `"The two new passwords are not the same."`; `"Your current password is not right."`; success clears
    `must_change`, raises `n`, keeps this session (new `n`), redirect `/home`.
  - `GET|POST /login/recover`: 404 unless `ADMIN_RECOVERY_CODE` is set. Fields: admin username, recovery code, new
    password twice. Accepted once per value (its `hash_pw` kept in `ways.recovery_used`; checked with `check_pw`
    against each). Success sets the password, clears lockout, signs in.
  - `GET /logout` as today.
  - A `before_request` same-origin check for `POST`, `PUT`, `PATCH`, `DELETE`: an `Origin` (else `Referer`) whose host
    is not `request.host` → 403 `{"error": "That request did not come from this site."}`; neither header → allowed.
  - A `before_request` once a day (date kept in memory): `people.update(lambda d: people.sweep(d, today))`, a history
    entry per ended extra (`kind "account"`, `text "Exams and events access ended (until <date>)"`), `history.prune()`.
- History entries (kind `signin`): every sign-in and every refused try, with `ok`, `via`, `shared` (the code's role
  for a shared code, else None), `who`/`as`, `reason`
  (`"wrong code"`, `"wrong password"`, `"unknown username"`, `"switched off"`, `"locked"`, `"code turned off"`), `addr`.
  Never what was typed: for an unknown username no username is recorded.

- [ ] **Step 1: Write the failing tests** in `tests/test_signin.py` (records made with `people.update` and
  `passwords.hash_pw`; published school from `relief.people.fake_pub` written as relief's tests do): code sign-in of a
  published teacher lands on `/home`; a shared code still works; a turned-off shared code is refused and an open
  shared session ends at its next request; password sign-in; unknown username and wrong password give the same body;
  5 wrong passwords lock the account (and `"locked"` recorded); `must_change` sends every page to `/account/password`
  and the API answers 403; changing the password ends a second session of the same person (its `n` is old); a
  password session older than 14 days ends; a code session survives `store.published()` returning None and ends when
  the teacher is no longer published; a password session of a committee person who is not on the published
  timetable works, with and without anything published; switched-off person refused; recovery works once per value and 404s without the
  variable; a `POST /api/setup/changes` with `Origin: https://elsewhere.example` gets 403; no history line contains
  any password, code or recovery value used in the tests (grep the history files); `SECRET_KEY` unset refuses
  `/login/password`.
- [ ] **Step 2: Run** `.venv/bin/python tests/test_signin.py` — fails.
- [ ] **Step 3: Implement** in `app.py`; keep `limiter` as is.
- [ ] **Step 4: Run** `tests/test_signin.py`, `tests/test_relief.py` (update its sign-in helper for the one-box page:
  post `code` only; its card-specific tests change to the new page's behaviour), `tests/smoke.py` — all pass.
- [ ] **Step 5: Commit** `git add app.py access.py tests && git commit -m "Accounts: signing in as a person"`

---

### Task 6: Every route checks a right

**Files:** Modify `app.py` (every `@need`, every `role()` branch, `/api/status`, `/`, new `/home`); Create
`tests/test_routes.py`.

**Interfaces:**
- Consumes: `need`, `has`, `who`, `shared` (Task 5).
- Produces: `/api/status` adds `who` (name or None), `via`, `depts` (a head's, signed in strongly; `None` otherwise),
  `rights` (sorted list); its `role` is `"committee"` when `has("committee")`, else `"head"`. `GET /home`: the tiles
  page (mockup tab 1, lower half): `"Hello, <name>"`, how they signed in, Sign out; tiles in this order, each only with
  its right: Committee page (`setup` → `/`), Timetables (`timetable` → `/timetable`), Relief (`relief` or
  `relief.settings` → `/relief`), Exams and events (`exams` → `/exams`, only when the route exists), Admin (`admin` →
  `/admin`), History (`history` → `/history`). A committee or HOD/SH person signed in with a code also sees Committee
  page and Admin (when they hold the Admin extra) greyed with `"Sign in with your password to open this."` linking to
  `/login/password`. With exactly one tile and nothing greyed, `/home` redirects to it.

The guards (old → new):

| Today | Now |
|---|---|
| `("committee",)` | `need("committee")` |
| `("committee", "head")` (meta, sample, setup GET, setup changes GET/POST, status) | `need("setup")` |
| timetable, pdf/custom, pdf/kind/key | `need("timetable")` |
| files | `need("files")` |
| `("personal",)` (me, pdf/me) | `need("own")` |
| relief_home | `need("relief", "relief.settings")` |
| relief_me | `need("relief")` |
| relief settings page, GET api | `need("relief.settings")`; PUT `need("relief.save")` |
| relief codes CSV and slips | `need("codes")` |
| new `/admin`, `/api/admin/*` (Task 8) | `need("admin")` |
| new `/history`, `/api/history` (Task 10) | `need("history")` |
| new `/home`, `/account/password` | a person signed in (`need("timetable")` plus a `who()` check) |

Inside routes: `role() == "head"` → `has("setup") and not has("committee")`, with `depts` from the person (shared
heads' code: `None`) passed to `sync.head_prepare` and `sync.head_split`; `post_setup_changes` passes `by=by()`; `put_setup`, `import_xlsx`,
`restore_setup` pass `by=by()`. Timetable view: `"student"` for the shared student code; committee mode (all tabs,
home `/`) when `has("committee")`; else teacher mode with home `/home` labelled `"Home"` for a person, `/relief` kept
only for relief-stage-1 sessions; the view cache key includes the mode. `pdf_one` refuses non-class PDFs only for the
shared student code. `files` uses committee books when `has("committee")`. `/`: `setup` → `index.html`; a person →
`/home`; `own` → `/me`; `timetable` → `/timetable`; else `/login`.

- [ ] **Step 1: Write the failing test** `tests/test_routes.py`: build sessions with `session_transaction` for each
  kind (none; shared committee, head, teacher, student; personal student; committee via password and via code; hod via
  password and via code; leader via password; teacher via code; executive via code; teacher with Relief team; teacher
  with Exams until tomorrow; admin via password and via code). For every rule in `A.app.url_map` except `static`,
  `/login*`, `/logout`, `/healthz`, `/account/password`: assert the view has `_need`; request it (path arguments
  filled with `"x"`, the rule's first method, empty JSON body); a session whose `rights` miss every right in `_need`
  gets 401, 403 or a redirect to `/login`; one that holds one never gets 401 or 403 from the guard (400, 404 and 409
  are fine). Also: `/home` shows exactly the tiles of the table for four of the kinds.
- [ ] **Step 2: Run** `.venv/bin/python tests/test_routes.py` — fails.
- [ ] **Step 3: Implement** the table.
- [ ] **Step 4: Run** `tests/test_routes.py`, `tests/test_signin.py`, `tests/test_relief.py`, `tests/test_board.py`,
  `tests/smoke.py` — all pass.
- [ ] **Step 5: Commit** `git add app.py tests/test_routes.py && git commit -m "Accounts: every route checks a right"`

---

### Task 7: Relief's lists move into the accounts

**Files:** Modify `accounts/people.py` (`migrate`), `app.py` (relief helpers), `relief/settings.py`,
`static/relief-settings.html`, `static/relief-settings.js`, `static/relief.js`; Test `tests/test_relief.py`,
`tests/test_accounts.py`.

**Interfaces:**
- Produces: `people.migrate(pub, relief_raw: dict) -> list[str] | None` — only when `PATH` does not exist and
  `relief_raw` (the saved relief settings JSON as stored) has any of `management`, `team`, `extra_staff`: a
  Management name whose published step-4 role is `HOD` or `SH` becomes that group with `depts` from
  `ttgen.spec.teacher_depts`; any other Management name becomes `leader`; a team name gets `extras.relief`; an extra
  staff entry becomes an `added` record, group `executive`, `note` kept. Returns the lines it did (`"Daniel Wong: HOD
  (from relief's Management list)"`) and stores them in `data["moved"]`; one history entry (kind `account`, `what
  "moved"`). Called at startup and before the admin page's first read; does nothing when the file exists.
- `app.relief_staff(pub)` → `people.staff(pub)`; `_relief_rights(pub)` → `(has("relief.settings"),
  has("relief.save"), by()["as"])`; `relief_me` answers `on_team` = the person's `extras.relief`, `on_management` =
  their group in `MANAGEMENT`, `can_settings = has("relief.save")`. `me_staff` is replaced by `who()`; the shared
  committee code on `/relief` still goes to `/relief/settings`.
- `relief/settings.py`: `save` keeps today's checks for rules, limits, times and calendar, and ignores
  `management`, `team`, `extra_staff` in what it is sent (the stored ones stay untouched for the record). The reply of
  `GET /api/relief/settings` adds `lists`: `{"management": [names], "team": [names], "added": [names]}` from the
  accounts.
- Pages: the three lists on `relief-settings.html` become read-only lists with the line `"Change these on the admin
  page."` linking `/admin` (only when `has("admin")`, else `"Ask an admin to change these."`).

- [ ] **Step 1: Write the failing tests**: `migrate_from_relief` (each rule above; a second call does nothing);
  relief settings save ignores the three lists; a teacher with the Relief team extra (no relief list entry) may save
  relief settings; a leader may read them and not save; `relief/me` flags from the accounts.
- [ ] **Step 2: Run** — fails. **Step 3: Implement.** **Step 4: Run** `tests/test_relief.py`,
  `tests/test_accounts.py`, `tests/test_routes.py` — all pass; open `/relief/settings` in the browser on made-up data
  as a committee person and as a relief-team teacher.
- [ ] **Step 5: Commit** `git add accounts app.py relief static tests && git commit -m "Relief's lists move into the accounts"`

---

### Task 8: The admin API

**Files:** Modify `app.py`; Create `tests/test_admin.py`.

**Interfaces:**
- Consumes: Tasks 1, 2, 5, 6, 7.
- Produces (all `need("admin")` and JSON, except the first-admin pair):
  - `GET /api/admin/people` → `{"people": people.staff(pub), "departments": the setup's school departments (setup being
    edited), "groups": [[key, label]...], "hints": {"heads_on_step4": [names whose step-4 role is HOD or SH and group
    teacher], "no_google": []}, "moved": data["moved"], "me": name}`. `no_google` stays empty until stage 3.
  - `POST /api/admin/person` `{name, group?, depts?, extras?, username?, note?, added?, off?}` → the person's new
    `staff` item. Checks (sentences verbatim): unknown group `"Pick a group."`; Admin extra outside committee `"Only
    the timetable committee can be admins."`; the last admin demoted, switched off or losing Admin `"<name> is the last
    admin: make another admin first."`; Exams with no date or a past date `"Give the last day of the exams and events
    access."`; username not `^[a-z0-9._-]{3,40}$` `"A username is 3 to 40 letters, digits, dots, dashes or
    underscores."`; taken `"That username is taken."`; a department not on the setup `"<dept> is not one of the
    school's departments."`; an added person's name empty, over 100 characters or starting with a spreadsheet
    formula character (`relief.settings.FORMULA`) — relief's sentences. Switching off, a group or extras change raises
    `n`.
  - `POST /api/admin/bulk` `{names, action: "give"|"take"|"group"|"off"|"on", extra?, until?, group?, preview: bool}`
    → `{"lines": [sentences], "applied": bool}`. Preview lists each person's result (`"Ravi Kumar has it already: his
    end date moves to 14 Nov 2027."` — use "their" for every name: no pronoun guessing); apply is all-or-nothing under
    one `people.update`; any refusal above refuses the whole with that sentence.
  - `POST /api/admin/reset` `{name, username?}` → `{"once": one-time password}`: sets the username when given (same
    checks), `pw = hash_pw(once)`, `must_change`, raises `n`. The answer is the only place `once` ever appears.
  - `GET /api/admin/ways` → `{"secret_key": bool, "personal_codes": bool, "password_accounts": int, "shared": [{"code":
    r, "set": bool, "off": at|None, "used_week": history.uses(kind="signin", via="shared", shared=r, ok=True)}],
    "recovery_set": bool}`. `POST /api/admin/shared-off` `{code, off: bool}`.
  - `GET /api/admin/students` → `[{id, name, class}]` of the published Students list.
  - `GET /admin` → `static/admin.html`. `GET /admin/first` and `POST /admin/first` (`need("committee")`, and only while
    `people.admins(people.load())` is empty, else 404): pick a name from `people.staff(pub)` or type one, a username, a password
    twice (`passwords.problem`); creates the committee record with Admin and the password, signs in as them, redirects
    `/admin`.
  - Every change writes one history entry (kind `account`, `what` one of `"group"`, `"extras"`, `"depts"`, `"username"`,
    `"reset"`, `"off"`, `"on"`, `"add"`, `"note"`, `"shared-off"`, `"first-admin"`, `"password"`, `"ended"`,
    `"moved"`; `people`: the names; `changes`: `[{name, field, was, now}]` with no password field ever), so stage 2's
    Put back has what it needs.
  - The relief code slips route takes `?names=a,b` to print only those people (the bulk bar's "Print their code slips").

- [ ] **Step 1: Write the failing tests** in `tests/test_admin.py`: each check's sentence; bulk preview lines for the
  mockup's four people (made-up names) and an apply that writes one entry naming all four; bulk "off" over a list that
  holds the last admin refused whole, nothing changed; reset returns a one-time password that signs in and forces a
  change, and the history has no copy of it; first admin works once then 404s, and only for `committee`; ways counts a
  shared sign-in; a non-admin gets 403 on each route; students list.
- [ ] **Step 2: Run** — fails. **Step 3: Implement.** **Step 4: Run** `tests/test_admin.py`, `tests/test_routes.py` — pass.
- [ ] **Step 5: Commit** `git add app.py tests/test_admin.py && git commit -m "Admin: people, ticking several, ways in"`

---

### Task 9: The admin page

**Files:** Create `static/admin.html`, `static/admin.js` (style as `static/relief-settings.html`); Modify `README.md`.

Mockup tabs 2 and 3. Tabs **Staff (n)**, **Students (n)**, **Ways in**, **History** (a link to `/history`).
- Staff: search, Group, Department and Extra filters; the yellow hint (`"Step 4 lists <n> teachers as HOD or SH who
  are still in the Teacher group."` with "Make them management", which ticks them and opens Set group); the table
  (tick box, name, group pill, departments, extras, last signed in, switched off greyed); "Tick all shown (n)"; with
  ticks, the dark bar: Give extra access ▾ (Relief team; Exams and events with the until date; Admin), Take away
  extra access ▾, Set group ▾, Print their code slips, Switch off, Clear ticks; every bar action shows the preview
  lines first and applies only on "Give it to <n> people" (or the action's own verb); one person's panel (group;
  "Changes the map for" ticks, shown for HOD/SH; extras; username and "Make a password account" / "Reset password"
  showing the one-time password once with `"Shown once. Give it to <name>; they pick their own when they next sign
  in."`; "Their changes" → `/history?who=<name>`; Switch off / Switch on); "Add a person"; "Print code slips". The
  "moved" lines, if any, in a box at the top until dismissed (dismissing is kept in this browser only).
- Students: search; ID, name, class; "Print code slips" (`/api/code-slips.pdf`).
- Ways in: the rows of mockup tab 2's lower table that stage 1 has (no Google row yet), each shared code's Turn off /
  Turn on with its week's use.
- Every error the API gives is shown as its sentence.

- [ ] **Step 1:** Build the page against Task 8's API.
- [ ] **Step 2: Browser check** on a scratch `DATA_DIR` with made-up people (a temporary launch entry added by script,
  removed afterwards, the launch file compared with `cmp`): with real pointer clicks, tick four teachers, give Exams
  until a date, read the preview, apply; reset a password and sign in with it in a private tab; switch off the last
  admin (refused); filters and search; a narrow window (no sideways scroll). Report which checks used real clicks.
- [ ] **Step 3:** `node --check static/admin.js`; README: the admin page and the first admin.
- [ ] **Step 4: Commit** `git add static/admin.* README.md && git commit -m "Admin: the admin page"`

---

### Task 10: The history page

**Files:** Modify `app.py`; Create `static/history.html`, `static/history.js`; Test `tests/test_history.py`.

**Interfaces:** `GET /history` → `static/history.html`; `GET /api/history?who=&where=&dept=&from=&to=&signins=&before=&limit=`
→ `{"entries": history.read(...), "more": bool}` (`from`/`to` as `YYYY-MM-DD`, local days; `limit` capped at 500).
Both `need("history")`.

Mockup tab 4, lower part, without Put back and without Download (stage 2): filters (who, where, department, from–to,
sign-ins shown or hidden); entries grouped by day, newest first: time, who (`as`) with group and way in, where, the
text with `was` struck through and `now` in green for setup changes, "The app" entries in grey tied to the change
before them, step 8 and publish entries with a link to step 8 or 9 (`"/#edit"`, `"/#publish"`), relief entries with a
link to `/relief`; "Show older" pages with `before`. The page reads `?who=` from its address to start filtered (the
admin page's "Their changes").

- [ ] **Step 1: Write the failing tests**: the API filters and pages; a non-history session gets 403.
- [ ] **Step 2: Run** — fails. **Step 3: Implement** the route and the page. **Step 4: Run** `tests/test_history.py`,
  `tests/test_routes.py`; browser check on made-up data (a head's change, a refused one, a Class Parents follow-up, a
  sign-in shown and hidden); `node --check static/history.js`.
- [ ] **Step 5: Commit** `git add app.py static/history.* tests && git commit -m "History: the history page"`

---

### Task 11: The committee page knows who is signed in

**Files:** Modify `static/app.js`, `static/index.html`.

- The header shows `"<name> · <group label>"` beside Sign out (from `G.st.who`; nothing for a shared code) and a
  "Home" link to `/home` for a person.
- For a head signed in as a person (`isHead() && G.st.depts`), outside a practice copy: a step 5 row whose subject's
  department is not in `G.st.depts` is read-only like a Class Parents' row today (`cpBlock`): its teacher selects, delete,
  subject and edit controls disabled, with the title `"Another department's row."`; the Add bars list only subjects of
  their departments; a band holding none of their lessons is read-only, and Rename and Delete are hidden on a band
  holding another department's groups; the step 4 "new teacher" department choice lists only their departments. The
  server's refusals still show as today (the `refused` sentences).
- The shared heads' code (no `depts`) behaves exactly as today.
- Signed in with the shared committee or heads' code while an admin exists (`/api/status` adds `shared`, the code's
  role or None, and `admin_exists`), a warning line under the header: `"You are signed in with a shared code: your
  changes show in the history without a name. Ask an admin for your own account."`

- [ ] **Step 1:** Implement, following how `cpBlock`, `locked` and `headLocks` work today.
- [ ] **Step 2:** `node --check static/app.js`; every `node tests/*.test.js` one by one.
- [ ] **Step 3: Browser check** on made-up data, signed in as an HOD of one department, with real pointer clicks:
  every control on step 5 of an own row works; another department's row cannot be changed; each Add bar adds an own
  row (Review Focus 1); rename a band of own groups works; a shared band offers no rename; then as a committee person
  nothing is greyed; then with the shared heads' code everything is as before. Re-try every old control of step 5 too.
- [ ] **Step 4: Commit** `git add static && git commit -m "Committee page: who is signed in; heads see other departments read-only"`

---

### Task 12: Step 8, publishing and relief in the history

**Files:** Modify `app.py`, `draft.py` (one helper); Test `tests/test_history.py`.

**Interfaces:** `draft.last_fix_text() -> str | None` (the newest `fixes[-1]["text"]` of the draft's `meta.json`).
After each success, one entry with `by()`:
- `POST /api/draft` — kind `draft`, `what "upload"`, where `"Step 8 · Upload and edit"`, text `"Uploaded <file name>"`.
- `/api/draft/fix`, `/api/draft/fixes` — `what "fix"`, text = `last_fix_text()` (for `fixes`: `"<n> fixes"` then the texts);
  `/api/draft/undo` — `what "undo"`, text `"Undid: <text>"` (the text read before the undo); `/api/draft/decide` —
  `what "decide"`, text `"Decided: <answer> — <the warning's text>"` (the warning found by its key in
  `draft.info()["warnings"]` before deciding).
- `/api/draft/publish` — `what "publish"`, where `"Step 9 · Publish"`, text `"Published the timetable"`.
- `PUT /api/relief/settings` — kind `relief`, where `"Relief settings"`, text `"Relief settings saved"`.

- [ ] **Step 1: Write the failing tests** with the board tests' way of making a draft (`tests/test_board.py`): an upload,
  a fix and an undo each write one entry with the committee person's name; a refused fix writes none.
- [ ] **Step 2: Run** — fails. **Step 3: Implement.** **Step 4: Run** `tests/test_history.py`, `tests/test_board.py`,
  `tests/test_fixes.py` — pass.
- [ ] **Step 5: Commit** `git add app.py draft.py tests && git commit -m "History: step 8, publishing and relief"`

---

### Task 13: Exams' committee list (only when `exams/` is on the branch)

Skip this task when Task 0 found no `exams/`; the notes file then says the move is exams' to make when it merges.

- `people.migrate` also reads the exams settings' `committee` list: each name gets `extras.exams` with the date 31
  December of the current year, and the moved lines say `"(from the exams committee list: check the end date)"`.
- `app._exams_rights` reads `has("exams")` (and `has("committee")` as today for the timetable committee); the exams
  settings page shows the committee list read-only with the admin-page line of Task 7; `exams.settings.save` ignores
  `committee`. Exams saves (settings, an exam's create, edit, delete, Make, moves, invigilators, "use anyway") each write
  one entry (kind `exams`, text `"<schedule name>: <what>"`, a link to `/exams`).
- Tests in `tests/test_exams.py` and `tests/test_routes.py` (an exams-extra teacher reaches the exams routes; one past
  the date does not).
- [ ] Steps as in Task 7; commit `git commit -m "Exams' committee list moves into the accounts"`.

---

### Task 14: Finish

- [ ] **Step 1:** Run every suite on the final code: `tests/test_accounts.py`, `test_history`, `test_signin`,
  `test_routes`, `test_admin`, `test_relief`, `test_sync`, `test_board`, `test_teachers`, `test_venues`,
  `test_combined`, `test_ask`, `test_verify`, `test_rules`, `test_choices`, `test_parents`, `test_typed`,
  `test_helper`, `test_fixes` (the last three also `--full`), `test_exams` if present, `smoke.py` and `smoke.py --full`;
  every `node tests/*.test.js` one by one; `node --check` on every changed `static/*.js`.
- [ ] **Step 2:** On the school's newest real setup and timetable (the private folder on the lead's machine) in a scratch
  data folder, run locally and report numbers only: how many staff in `people.staff`, how many step-4 HOD/SH the hint
  would list, for each department with a head how many step-5 rows a head of it may change and how many they may
  not, how many bands are shared between departments (renamed only by the committee), and that a head's typical
  change (a teacher on an own row) is accepted. Delete every scratch file made from it.
- [ ] **Step 3:** Write `docs/superpowers/plans/2026-11-21-accounts-stage-1-notes.md`: rulings, known limits, what was not
  tried in a browser, stage 2 points (Put back reads `changes`/`was`; the head's and own history views).
- [ ] **Step 4:** Grep the branch's commits for the school's full name and real staff names (counts only); then ask the
  lead before opening the pull request, merging or deploying. The deploy notes for the lead: set `SECRET_KEY` if it is
  not set; after "Deploy Latest Commit", sign in with the committee code, open the admin page, make the first admin;
  the shared codes keep working until turned off on Ways in.

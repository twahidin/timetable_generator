# Relief stage 1: who's who and the calendar — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every teacher can sign in as themselves with a personal code (the new **Relief** card, and the Teacher's
timetable card), and the committee and relief team can fill in the relief settings: the two lists, the Flexi Adjunct
role, the rules, the checked limits, the times and the school calendar.

**Architecture:** A new package `relief/` holds what relief needs and nothing else: `people.py` (who is who, from the
published timetable's own setup plus staff added by name), `settings.py` (load, defaults, check, save as one JSON file
under the data folder), `calendar.py` (which cycle day a date is), `codes.py` (the staff code slips). `access.py` gains
personal staff codes beside the student ones; `app.py` gains the Relief card, the `staff` role and the relief routes.
Two plain-JavaScript pages, `static/relief.html` (the signed-in home) and `static/relief-settings.html`, talk to
`/api/relief/...`.

**Tech Stack:** Python 3 / Flask (one gunicorn worker), plain JavaScript, reportlab for the slips, plain-assert test
scripts.

**Spec:** `docs/superpowers/specs/2026-11-20-relief-module-design.md` (approved 20 Nov 2026), "Personal teacher codes",
"Who uses it", "Relief settings" and "Stages" (stage 1). Mockups: `docs/superpowers/specs/2026-11-20-relief-module-mockups.html`,
tabs 0, 1 and 12.

**Branch:** `relief-stage-1`, cut from `origin/main` at build time, with the design and this plan committed first.

## Global Constraints

- The repo is public: the school is only ever "CTSS"; tests, samples and docs use made-up names only.
- Never print, log or commit a real code, key or token. Tests make random codes with `secrets.token_hex`.
- No model or Telegram call anywhere in this stage.
- Tests are plain-assert scripts run as `.venv/bin/python tests/<name>.py`, with `DATA_DIR` set to a fresh temp folder
  before `import app` (as `tests/test_board.py` does).
- Files are written atomically with `store.write_json`; relief data lives under `os.path.join(store.DATA, "relief")`.
- Personal staff codes exist only when `access.personal_codes_on()` (SECRET_KEY set), like personal student codes.
- Everything about teachers is read from the **published** timetable (`store.published()["model"]`), never from the
  setup being edited.
- Copy is plain words in the app's style. Exact texts fixed by this plan are in quotes; use them verbatim.
- Builders and reviewers: NEVER run `git stash`, `git stash pop` or `git checkout -- <file>`. After each task,
  `git stash list` must show the same entries as before it.
- In `static/*.js` and `ttgen/timetable_page.html`, never put a `//` comment in the middle of a long line; use `/* */`.

## Review Focus

1. **A later publish drops or renames a teacher who is on a settings list or signed in.** The settings page must still
   open, listing the name under "No longer on the timetable"; their session ends with "Code no longer valid". (Tests in
   Task 3 and Task 4.)
2. **SECRET_KEY not set.** The Relief card says personal codes are off; the codes CSV and slips answer 409 with
   `NO_PERSONAL_STAFF`; nothing crashes. (Task 4.)
3. **Nothing published yet.** `/relief/settings` and `/api/relief/settings` say "Publish the timetable first: relief
   reads the teachers from it." (409 for the API); no crash. (Task 4.)
4. **Day labels as the school writes them** ("Odd Tues", "Thurs") and a one-week timetable ("Tue") in the calendar.
   (Task 2.)
5. **A code on the wrong card.** TEACHER_CODE on the Relief card is refused with the link to Teacher's timetable; a
   personal staff code on the Teacher's timetable card opens the timetable. (Task 4.)

---

## File structure

| File | What it is |
|---|---|
| `relief/__init__.py` | empty; marks the package |
| `relief/people.py` | the people relief knows: published teachers plus staff added by name |
| `relief/calendar.py` | school calendar: which published day a date is, which term |
| `relief/settings.py` | defaults, load, check, save of `DATA/relief/settings.json` |
| `relief/codes.py` | staff codes CSV and printable slips |
| `access.py` | `staff_code`, and `match` that also knows staff codes |
| `app.py` | Relief card, `staff` role, relief routes, teacher routes open to `staff` |
| `static/relief.html`, `static/relief.js` | the signed-in Relief home |
| `static/relief-settings.html`, `static/relief-settings.js` | the settings page |
| `static/choice-relief.svg` | the Relief card's picture |
| `static/index.html`, `static/app.js` | a "Relief settings" link for the committee |
| `tests/test_relief.py` | every test of this stage |
| `README.md` | the codes table and a Relief section |

---

### Task 1: Personal staff codes and the people relief knows

**Files:**
- Modify: `access.py`
- Create: `relief/__init__.py`, `relief/people.py`
- Test: `tests/test_relief.py` (create; header as `tests/test_board.py`: temp `DATA_DIR`, random codes, `SECRET_KEY`,
  `AI_API_KEY=""`, `import app as A, access, store`; a `t` decorator that runs each test and counts it; print the count)

**Interfaces:**
- Produces: `access.staff_code(name: str) -> str` ("XXXX-XXXX", same alphabet as `personal_code`, HMAC of
  `"timetable-staff:" + name.strip()` with `secret()`).
- Produces: `access.match(code, personal, staff=None) -> (role, value)`: shared codes first, then `personal`
  ({normalised code: student id}) → `("personal", sid)`, then `staff` ({normalised code: name}) → `("staff", name)`,
  else `(None, None)`.
- Produces: `relief.people.people(pub: dict | None, extra: list[dict]) -> list[dict]`, each
  `dict(name, short, depts: list[str], role: str, teaches: bool, staff_only: bool)`, sorted by first department then
  name. Teachers come from `pub["model"]["setup"]["teachers"]` (depts via `ttgen.spec.teacher_depts`, `role` from the
  row or ""), then any name in `pub["model"]["teachers"]` not already there (depts from its `dept`), then `extra`
  (`dict(name, note)`) as `staff_only=True, teaches=False, depts=[]`. `teaches` is True when the name is on any lesson
  of `pub["model"]["lessons"]`. `pub` None gives only `extra`.
- Produces: `relief.people.staff_codes(people: list[dict]) -> dict[str, str]` ({`access.norm(staff_code(name))`: name}),
  `{}` when `not access.personal_codes_on()`.
- Produces: `relief.people.fake_pub(teachers, lessons=(), roles=(), days=None) -> dict` — a test helper building the
  minimal published dict this stage reads, kept in the module so later stages' tests reuse it. `teachers`: setup rows
  `dict(name, dept, dept2=None, role=None, short=None)`; `lessons`: `dict(teachers=[names])`; `roles`:
  `dict(role, what)`; `days` defaults to `ttgen.spec.day_names(2)`. It returns `dict(meta=dict(school="Sample School"),
  codes={}, views={}, model=dict(setup=dict(teachers=..., roles=...), teachers=<setup rows, then lesson-only names, as
  ttgen/export.py builds them>, lessons=..., days=days, school=dict(name="Sample School", weeks=2 if len(days) == 10 else 1)))`.

- [ ] **Step 1: Write the failing tests** in `tests/test_relief.py`:
  - `staff_code_is_stable_and_shaped`: same name twice gives the same code; matches `^[2-9A-HJ-KM-NP-Z]{4}-[2-9A-HJ-KM-NP-Z]{4}$`;
    `staff_code("Ms Evelyn Koh") != staff_code("Mr Darren Lim")`; `staff_code(" Ms Evelyn Koh ") == staff_code("Ms Evelyn Koh")`;
    `staff_code("S0001") != personal_code("S0001")`.
  - `staff_code_changes_with_secret_key`: set `SECRET_KEY` to another value, the code differs; restore it.
  - `match_knows_staff_codes`: `access.match(code, {}, {access.norm(code): "Ms Evelyn Koh"}) == ("staff", "Ms Evelyn Koh")`,
    and the code typed in lower case with spaces matches too; an unknown code gives `(None, None)`; TEACHER_CODE still
    gives `("teacher", None)`.
  - `people_reads_the_published_setup`: `fake_pub` with teachers `Ms Evelyn Koh` (Science, dept2 Mathematics, role
    "FAJT") and `Mr Darren Lim` (Science), a lesson taught by `Mr Darren Lim` and one by `Mr Lesson Only` (not in the
    setup), extra `[dict(name="Mdm Office Staff", note="admin")]` gives four people; `Ms Evelyn Koh` has
    `depts == ["Science", "Mathematics"]`, `role == "FAJT"`, `teaches is False`; `Mr Darren Lim` `teaches is True`;
    `Mr Lesson Only` is there; `Mdm Office Staff` has `staff_only is True`.
  - `staff_codes_off_without_secret_key`: with `SECRET_KEY` removed, `staff_codes(...) == {}`; restore it.

- [ ] **Step 2: Run** `.venv/bin/python tests/test_relief.py` — expect an import or attribute error.

- [ ] **Step 3: Implement** `staff_code`, the `staff` argument of `match`, `relief/__init__.py`, and `relief/people.py`
  (`people`, `staff_codes`, `fake_pub`) as in Interfaces.

- [ ] **Step 4: Run** `.venv/bin/python tests/test_relief.py` — all pass; also `.venv/bin/python tests/smoke.py`
  (unchanged behaviour of `match` for existing callers).

- [ ] **Step 5: Commit** `git add access.py relief tests/test_relief.py && git commit -m "Relief: personal staff codes and the people relief knows"`

---

### Task 2: The school calendar

**Files:**
- Create: `relief/calendar.py`
- Test: `tests/test_relief.py`

**Interfaces:**
- Produces: `relief.calendar.school_day(cal: dict, days: list[str], date: datetime.date) -> str | None` — the published
  day name (an item of `days`, e.g. "Even Tue" or "Odd Tues" or "Tue") that `date` is, or None on a weekend, a holiday,
  outside every term, or a weekday the timetable does not have.
- Produces: `relief.calendar.term_of(cal: dict, date) -> dict | None`.
- Produces: `relief.calendar.week_of(date) -> (monday: date, friday: date)`.
- `cal` shape (stored in the settings, Task 3): `dict(terms=[dict(name, start, end, starts_as)], holidays=[dict(start, end, name)])`,
  dates as "YYYY-MM-DD", `starts_as` "Odd" or "Even" (ignored for a one-week timetable), a holiday's `end` may equal
  its `start`.
- Rule: a two-week timetable's week is `starts_as` in the calendar week (Monday to Sunday) holding the term's `start`,
  and flips every calendar week after it within the term, holidays included. A day name matches when its week part
  (from `ttgen.database._split_day`) equals the week, or is "" for a one-week timetable, and the first three letters of
  its weekday part equal the date's weekday ("Tues" and "Thurs" match Tue and Thu).

- [ ] **Step 1: Write the failing tests** (`CAL = dict(terms=[dict(name="Term 4", start="2026-09-07", end="2026-11-20", starts_as="Odd")], holidays=[dict(start="2026-10-23", end="2026-10-23", name="Deepavali")])`,
  `TWO = day_names(2)`):
  - `school_day_counts_odd_and_even_weeks`: 2026-09-07 → "Odd Mon"; 2026-09-14 → "Even Mon"; 2026-10-13 → "Even Tue";
    2026-10-12 → "Even Mon".
  - `school_day_is_none_off_school`: 2026-10-17 (Sat) → None; 2026-10-23 (holiday) → None; 2026-11-23 (after the term)
    → None; 2026-09-04 (before it) → None.
  - `school_day_reads_the_schools_own_labels`: with days `["Odd Mon", "Odd Tues", "Odd Wed", "Odd Thurs", "Odd Fri", "Even Mon", "Even Tues", "Even Wed", "Even Thurs", "Even Fri"]`,
    2026-10-13 → "Even Tues" and 2026-10-15 → "Even Thurs".
  - `school_day_one_week_timetable`: days `["Mon", "Tue", "Wed", "Thu", "Fri"]`, 2026-10-13 → "Tue".
  - `term_starting_midweek_keeps_its_week`: a term starting 2026-09-09 (Wed) as "Odd": 2026-09-11 → "Odd Fri",
    2026-09-14 → "Even Mon".
  - `term_of_and_week_of`: `term_of(CAL, date(2026,10,13))["name"] == "Term 4"`; `week_of(date(2026,10,15)) == (date(2026,10,12), date(2026,10,16))`.

- [ ] **Step 2: Run** the tests — expect an import error.
- [ ] **Step 3: Implement** `relief/calendar.py` as in Interfaces.
- [ ] **Step 4: Run** the tests — all pass.
- [ ] **Step 5: Commit** `git add relief/calendar.py tests/test_relief.py && git commit -m "Relief: the school calendar"`

---

### Task 3: Relief settings: defaults, check, save

**Files:**
- Create: `relief/settings.py`
- Test: `tests/test_relief.py`

**Interfaces:**
- Consumes: `relief.people.people`, `relief.calendar` shapes.
- Produces: `relief.settings.PATH = os.path.join(store.DATA, "relief", "settings.json")`.
- Produces: `relief.settings.DEFAULT_RULES` — exactly these three strings:
  1. `"Use planned relief first."`
  2. `"Then Flexi Adjunct Teachers: no more than 3 relief periods a day each; match the subject where possible; spread their relief over the week."`
  3. `"Then other teachers, lightest week first (teaching periods plus relief periods this week); if tied, whoever has had less relief this term; spread over the week."`
- Produces: `relief.settings.defaults(pub) -> dict`:
  `dict(management=[], team=[], extra_staff=[], fat_role=<first role of pub["model"]["setup"]["roles"] whose "role" or "what" contains "adjunct" (any case), else "">, rules=list(DEFAULT_RULES), limits=dict(fat_per_day=3, other_per_day=None, never=[]), times=dict(fill_at="15:00", remind_at="15:00", report_every=15, weekly_day="Fri", weekly_at="15:00"), calendar=dict(terms=[], holidays=[]), saved_at=None, saved_by=None)`.
- Produces: `relief.settings.load(pub) -> dict` — the saved file over `defaults(pub)`, plus `missing: list[str]`: names
  on `management`, `team` or `limits.never` that are no longer among `people(pub, extra_staff)`; those names are left
  out of the returned lists (the file keeps them until the next save).
- Produces: `relief.settings.save(new: dict, pub, by: str) -> dict` — checks, writes with `store.write_json` under a
  module lock, returns `load(pub)`. Raises `ValueError(<one plain sentence>)` on the first problem:
  - a name on `management`, `team` or `never` that is not a person: `f"{name} is not on the published timetable or the staff list."`
  - an `extra_staff` name that is empty, repeated, or a teacher's name: `f"{name} is already a teacher on the timetable."` (repeated or teacher), `"A staff member needs a name."` (empty)
  - `fat_role` not "" and not a role in the published setup's roles or on any teacher: `f"There is no role {role} on step 4."`
  - `rules`: more than 20, any empty after trimming, or any over 300 characters: `"Keep each rule under 300 characters, at most 20 rules, none empty."`
  - `limits.fat_per_day` / `other_per_day` not None and not an integer 1 to 20: `"A daily limit is a whole number from 1 to 20, or empty."`
  - a time not "HH:MM" 00:00–23:59: `f"{value} is not a time like 15:00."`; `report_every` not an integer 5 to 60:
    `"Report every 5 to 60 minutes."`; `weekly_day` not Mon–Fri: `"The weekly summary goes out on a weekday."`
  - a term with a missing name, a bad date, `start` after `end`, or overlapping another term:
    `f"Check the dates of {name}."`; on a two-week timetable a term without `starts_as` "Odd"/"Even":
    `f"Say whether {name} starts in an Odd or an Even week."`
  - a holiday with a bad date or `end` before `start`: `f"Check the dates of {name}."`
  `saved_at = store.now()`, `saved_by = by`; unknown keys are dropped.

- [ ] **Step 1: Write the failing tests** (each test removes `PATH` first; `PUB = fake_pub(...)` with `Ms Evelyn Koh`,
  `Mr Darren Lim`, `Ms Grace Wong`, roles `[dict(role="FAJT", what="Flexible Adjunct Teacher (part-time)")]`):
  - `defaults_pick_the_adjunct_role_and_the_schools_rules`: `defaults(PUB)["fat_role"] == "FAJT"`; rules equal
    `DEFAULT_RULES`; with no roles, `fat_role == ""`.
  - `save_and_load_round_trip`: save management `["Ms Grace Wong"]`, team `["Mr Darren Lim"]`, extra staff
    `[dict(name="Mdm Office Staff", note="")]`, team also `"Mdm Office Staff"`, the Term 4 calendar; `load` returns them,
    `saved_by == "Timetable committee"`, and the file is under `DATA/relief/`.
  - `save_refuses_with_one_plain_sentence`: each bad input in the Interfaces list raises `ValueError` with that exact
    sentence (one assert per sentence, using `raises` as in `tests/test_board.py`).
  - `a_name_gone_from_the_timetable_is_missing_not_fatal`: save team `["Mr Darren Lim"]`, then `load` with a
    `fake_pub` without him returns `team == []` and `missing == ["Mr Darren Lim"]`.

- [ ] **Step 2: Run** — expect failures.
- [ ] **Step 3: Implement** `relief/settings.py` as in Interfaces.
- [ ] **Step 4: Run** — all pass.
- [ ] **Step 5: Commit** `git add relief/settings.py tests/test_relief.py && git commit -m "Relief: settings with defaults and checks"`

---

### Task 4: Sign-in as a person, the Relief card, the relief routes, codes and slips

**Files:**
- Modify: `app.py`; Create: `relief/codes.py`, `static/choice-relief.svg`
- Test: `tests/test_relief.py`

**Interfaces:**
- Consumes: Tasks 1 to 3.
- Produces (session): `session["role"] == "staff"`, `session["who"] == <name>`.
- Produces: `app.me_staff() -> dict | None` — the person signed in (`people` entry) or None; a `staff` session whose
  name is no longer among the people is cleared.
- Produces routes:
  - `CHOICES["relief"] = dict(title="Relief", blurb="Ask for or plan relief, set work, see your reliefs.", label="Your personal code", hint="Use the personal code on the slip from the timetable committee.", roles=("staff",), img="/static/choice-relief.svg")`;
    `CHOICES["teacher"]["roles"] = ("teacher", "staff")`; every card's picture is `c.get("img") or f"/static/choice-{k}.png"`.
    When `not access.personal_codes_on()`, the Relief card's form page shows `NO_PERSONAL_STAFF` in place of the form.
  - `POST /login` matches with `relief.people.staff_codes(people(pub, settings.extra_staff))` as the `staff` map; a
    staff code goes to `/relief` from the Relief card and to `/timetable` from the Teacher's timetable card.
  - `GET /` sends `staff` to `/relief`.
  - `/timetable`, `/pdf/custom`, `/pdf/<kind>/<key>` and `/files/...` accept `staff` and treat it as `teacher`.
  - `GET /relief` (staff): `static/relief.html`; a cleared session gets the "Code no longer valid" page with
    "Ask the timetable committee for your code." `GET /relief` for `committee` redirects to `/relief/settings`.
  - `GET /api/relief/me` (staff): `dict(name, depts, on_team, on_management, can_settings)`.
  - `GET /relief/settings` (committee, or staff on the team): `static/relief-settings.html`; others get a page
    "Only the timetable committee and the relief team can change relief settings."
  - `GET /api/relief/settings` (committee, staff on team or management): `dict(settings=load(pub), people=[...], roles=[role names from the published setup and teachers], weeks=pub["model"]["school"]["weeks"], can_save=bool, can_codes=role()=="committee")`;
    409 `{"error": "Publish the timetable first: relief reads the teachers from it."}` when nothing is published.
  - `PUT /api/relief/settings` (committee, or staff on team): `save(json, pub, by)` with `by = "Timetable committee"`
    for the committee or the person's name; 400 `{"error": <sentence>}` on `ValueError`.
  - `GET /api/relief/codes.csv` and `GET /api/relief/code-slips.pdf` (committee only): 409 `NO_PERSONAL_STAFF` when
    codes are off.
  - `NO_PERSONAL_STAFF = "Personal codes are off until SECRET_KEY is set in Railway variables."`
- Produces: `relief.codes.codes_csv(people) -> str` (BOM first, columns `Name, Department, Personal code`, sorted as
  `people`) and `relief.codes.slips_pdf(school: str, people, url: str, out)` — 10 slips to an A4 page, a new page per
  first department, as `ttgen.export.code_slips_pdf` draws them, with the lines: `f"{school} · your relief code"`, the
  name, the department(s), the code, `f"Go to {url}"`, `"choose Relief and enter this code."`,
  `"Keep it to yourself: anyone with it can act as you."`
- `static/choice-relief.svg`: a 112×112 rounded tile in `#ffe6bf` with two curved arrows in `#e08a00`, flat, no text.

- [ ] **Step 1: Write the failing tests** (patch `store.published` to return a `fake_pub` and restore it in `finally`;
  clients from `A.app.test_client()`):
  - `relief_card_is_on_the_front_page`: `b"Relief" in GET /login` and `GET /login?as=relief` shows "Your personal code".
  - `a_staff_code_signs_in_as_that_person`: POST `/login` `as=relief` with `staff_code("Mr Darren Lim")` → 302 to
    `/relief`; `GET /api/relief/me` → name `Mr Darren Lim`, `can_settings` False.
  - `a_staff_code_opens_the_teachers_timetable_card`: `as=teacher` with the same code → 302 to `/timetable`.
  - `teacher_code_on_the_relief_card_is_refused_with_the_right_link`: 403 and `b"?as=teacher"` in the page.
  - `a_dropped_teacher_is_signed_out`: sign in as `Mr Darren Lim`, publish (patch) without him, `GET /relief` shows
    "Code no longer valid" and the session no longer has `who`.
  - `settings_rights`: committee and a team member can GET and PUT; management can GET but PUT is 403; an ordinary
    teacher gets 403 on both; a team member's save has `saved_by == "Mr Darren Lim"`.
  - `nothing_published_says_so`: with `store.published` returning None, `GET /api/relief/settings` → 409 with the exact
    sentence.
  - `codes_off_without_secret_key`: with `SECRET_KEY` removed, `GET /login?as=relief` shows `NO_PERSONAL_STAFF`,
    and `/api/relief/codes.csv` → 409; restore it.
  - `codes_csv_and_slips`: committee gets a CSV whose rows include `Mdm Office Staff` (extra staff) with her code, and
    a PDF starting with `b"%PDF"`; a staff member gets 403 on both.

- [ ] **Step 2: Run** — expect failures.
- [ ] **Step 3: Implement** the routes and `relief/codes.py` as in Interfaces; serve the two pages with
  `app.send_static_file`; make the SVG.
- [ ] **Step 4: Run** `.venv/bin/python tests/test_relief.py` and `.venv/bin/python tests/smoke.py` — all pass.
- [ ] **Step 5: Commit** `git add app.py relief/codes.py static/choice-relief.svg tests/test_relief.py && git commit -m "Relief: sign in as a person, the Relief card, settings routes, staff codes"`

---

### Task 5: The two pages and the committee's link

**Files:**
- Create: `static/relief.html`, `static/relief.js`, `static/relief-settings.html`, `static/relief-settings.js`
- Modify: `static/index.html` (a "Relief settings" link beside "Published timetable", hidden), `static/app.js` (show it
  when the status role is `committee`), `README.md`
- Test: browser check (below); `node --check static/relief.js static/relief-settings.js static/app.js`

**Interfaces:**
- Consumes: the Task 4 routes. Both pages use `static/style.css` and the app's colours.
- **Relief home** (`/relief`, mockup tab 1, stage 1 part only): header "Relief · {name}" with links "Your timetable"
  (`/timetable`), "Relief settings" (when `can_settings`), "Sign out"; one card: "Asking for relief, planning relief
  and the reliefs you cover arrive here in the next stage."
- **Settings page** (`/relief/settings`, mockup tab 12), one form, one **Save** at the bottom and the top, "Saved by
  {saved_by}, {saved_at}" beside it, the server's sentence shown in red on a refused save, nothing lost on a refusal:
  - Management, Relief team: chips with ✕, and an "+ Add" picker of people (type to filter).
  - Other staff (no lessons): name and note rows, "+ Add a staff member".
  - Flexi Adjunct Teachers: a select of roles (and "None"), with the count of people holding it.
  - Relief rules: numbered textareas, ↑ ↓ ✕ on each, "+ Add a rule"; below, the fixed line: "Always true, whatever the
    rules say: only teachers free at that time · never someone away that day · the relief team approves before
    anything is sent."
  - Checked limits: "Most relief periods a day for a Flexi Adjunct Teacher" (number), "for anyone else" (number or
    empty), "Never give relief to" (chips and picker).
  - Reporting officer: the text "Is told when someone who names them asks for relief."
  - Times: fill open lessons at, remind the absent teacher at (both "the school day before"), report every N minutes,
    weekly summary day and time.
  - School calendar: a terms table (name, first day, last day, starts as Odd/Even — the last column only when
    `weeks == 2`) and a holidays table (name, first day, last day), each with add and ✕.
  - Codes (only when `can_codes`): "Download codes (.csv)" and "Print code slips (PDF)".
  - "No longer on the timetable: {names}. Saving removes them." when `missing` is not empty.
- **README.md:** add a row to the codes table — "personal teacher codes (made by the app) | one teacher each | the
  Relief module and everything the teacher code opens" — and a short "Relief" section: what stage 1 gives, where the
  settings are, that codes need SECRET_KEY.

- [ ] **Step 1: Build the pages** as above.
- [ ] **Step 2: Run** `node --check` on the three scripts and the full Python suites listed in Task 6.
- [ ] **Step 3: Browser check** on a scratch data folder with the sample school published (as the smoke `--full` run
  publishes it), using the browser tool's real pointer clicks, one line per check saying which kind of action it was:
  sign in on the Relief card with a staff code from the codes CSV (read inside the test script, never printed); the home
  shows the name; the committee opens Relief settings from the committee page; add a team member, a rule, a term and a
  holiday, Save, reload, all still there; a bad term (end before start) shows "Check the dates of Term 1." and keeps the
  form; the team member signs in and can save; an ordinary teacher sees no settings link and gets the refusal page at
  `/relief/settings`. Screenshots of made-up data only.
- [ ] **Step 4: Commit** `git add static README.md && git commit -m "Relief: the Relief home and the settings page"`

---

### Task 6: Finish

- [ ] **Step 1:** Run every suite on the final code: `.venv/bin/python tests/test_relief.py`; `tests/smoke.py` and
  `tests/smoke.py --full`; `test_typed`, `test_helper`, `test_fixes` (each also `--full`), `test_verify`, `test_rules`,
  `test_choices`, `test_parents`, `test_sync`, `test_board`, `test_teachers`, `test_venues`, `test_combined`; every
  `node tests/*.test.js` one by one; `node --check static/app.js`.
- [ ] **Step 2:** Publish the school's newest real setup and timetable (the private folder on the lead's machine)
  into a scratch data folder, run locally and report numbers only: how many people,
  how many with no department, how many hold the default Flexi Adjunct role, and whether `school_day` gives a day for
  every school date of a made-up term. Delete any scratch file made from it.
- [ ] **Step 3:** Write `docs/superpowers/plans/2026-11-20-relief-stage-1-notes.md`: rulings, known limits, what was not
  tried in a browser.
- [ ] **Step 4:** Grep the branch's commits for the school's full name and for real staff names (counts only) before
  any push; then ask the lead before opening the pull request, merging or deploying.

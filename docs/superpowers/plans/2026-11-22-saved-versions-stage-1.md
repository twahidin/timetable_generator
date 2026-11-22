# Saved Versions and Compare (stage 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** On step 8, keep named versions of the draft (each with its own list of changes and Undo), keep the draft automatically before an upload or Open replaces it, and compare any two of the draft, a version and the published timetable.

**Architecture:** A version is a copy of the draft folder (`DATA_DIR/draft/`) in `DATA_DIR/draft_versions/<id>/` plus a `version.json`. A new server module `versions.py` keeps, lists, opens and deletes them; `draft.py` learns to read and check any such folder. A new module `compare.py` builds two timetables (draft, version, or published), matches their lessons by what they are (not by id) and lists the differences. Step 8 gets a Versions pop-out in `static/app.js`; Compare is its own page (`/compare`, `static/compare.html` + `static/compare.js`) like the History page.

**Tech Stack:** Python 3 / Flask, openpyxl, plain JavaScript and CSS (no build), plain-assert test scripts (`tests/*.py`, run with `.venv/bin/python`), `node --check`.

**Spec:** `docs/superpowers/specs/2026-11-22-saved-versions-and-refit-design.md` (features 1 and 2, "Saved versions" and "Compare"; feature 3 Re-fit is stage 2). Mockups: `docs/superpowers/specs/2026-11-22-saved-versions-and-refit-mockups.html` screens 1 and 2.

## Global Constraints

- Every new route needs the `committee` right: `@need("committee")`, like the other step 8 routes in `app.py`.
- Nothing publishes: versions and Compare work on the draft and on copies.
- Counts shown for a version or the published timetable are checked against the setup as it is now, and the page says so: "“Checked now” means against the setup as it is today: a version saved before step 5 changed can show warnings it did not have then."
- Version kinds: `saved` (by hand), `upload`, `open` (kept by the app before replacing the draft); `refit` is reserved for stage 2.
- Caps: at most `AUTO_KEEP = 10` versions of the kinds the app keeps (the oldest such is dropped when an 11th comes); at most `MAX_SAVED = 30` versions saved by hand (a 31st is refused). Names are trimmed, 1 to `NAME_MAX = 80` characters; names may repeat.
- A version id is 12 lowercase hex characters (`secrets.token_hex(6)`); any other id is refused with "There is no such version." (never used as a path otherwise).
- Uploading no longer asks "Replace the draft?": it keeps the draft as a version first (kind `upload`), unless the draft is the same as a version already kept (same identity: upload id, number of fixes, newest fix time).
- Opening keeps the draft first (kind `open`) with the same "already kept" check, then makes the version the draft with its own file, setup, decisions and fixes.
- History: one entry per hand save, open, delete, and an upload's text names the version kept (via `_draft_entry` in `app.py`).
- Tests use the sample school and made-up names only; never a real staff name, the school's full name, or a key. Never run `git stash`, `git stash pop` or `git checkout -- <file>`.
- Commits end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Copy on the pages, word for word where the spec gives it: button **Versions (n)**, pop-out title **Versions**, **Save the draft as** / **Save version**, row buttons **Open**, **Compare…**, **Download**, **Delete**; the draft row "The draft on step 8" with tag "now"; the published row "Published timetable" with tag "what teachers see"; upload toast "The draft you had is kept as version “{name}”."

## Review Focus

1. **Opening a version while the draft has unpublished fixes or a lesson waiting in Not placed:** the draft is kept whole (fixes, decisions, the waiting lesson) and comes back whole when opened again. Test in Task 2 (`test_open_keeps_the_draft_whole_and_brings_it_back`).
2. **Two tabs:** opening, downloading or deleting a version another tab has already deleted gives "There is no such version." with status 404, never a 500. Test in Task 4 (`test_a_deleted_version_is_refused_plainly`).
3. **A version kept before the setup changed:** its counts are recomputed when the setup version changes (the cache is keyed by setup version). Test in Task 2 (`test_counts_follow_the_setup_version`).
4. **Two uploads whose lesson ids differ, and a lesson only in one of them:** Compare pairs by what the lessons are and lists "only in A" / "only in B" without failing. Test in Task 5 (`test_pairs_ignore_ids_and_list_lessons_on_one_side`).
5. **The caps:** an 11th automatic keep drops the oldest automatic version and never a hand-saved one; a 31st hand save is refused with a sentence. Test in Task 2 (`test_automatic_keeps_are_capped_and_hand_saves_are_kept`).

---

### Task 1: Read and check any draft folder

**Files:**
- Modify: `draft.py` (`paths`, `model_now`, `_build`, `_finish`, `database`; add `model_in`, `tally`, `counts`, `checked_in`)
- Test: `tests/test_versions.py` (new; same frame as `tests/test_board.py`: temp `DATA_DIR`, random codes, sign in as committee, the primary sample as the setup, a made-up Lessons workbook uploaded as the draft; `test_*` functions run at the end with "N checks passed")

**Interfaces:**
- Produces:
  - `draft.paths(folder: str | None = None) -> tuple[str | None, str]` — `folder` defaults to `DIR`.
  - `draft.model_in(folder: str, rec: dict | None = None) -> tuple[dict, dict, dict]` — like `model_now` (fixes from that folder's `meta.json` applied, `config_id` laid on, `fx["pool"]` set) but for any folder and with no shared cache. `model_now` keeps its cache for `DIR`.
  - `draft.tally(warnings: list, decisions: dict) -> dict` — pure: `dict(warnings=[w with decision], open=int, critical=int)` exactly as `_finish` counts today (decisions dropped as `_finish` drops them; "met" and "step5" settle a warning). `_finish` calls it.
  - `draft.counts(m: dict, rec: dict, fx: dict | None = None, decisions: dict | None = None) -> dict(critical: int, warnings: int)` — the warnings `_build` makes for that model (its `verify.warnings`, `_own_warnings`, `_withhold`, `_no_teacher`), tallied; `critical` as `_finish` counts it, `warnings` = those with no decision that are not critical (what step 8 shows as "other warnings open"). Writes nothing.
  - `draft.checked_in(folder: str, rec: dict | None = None) -> dict(critical: int, warnings: int)` — `model_in` + `counts` with that folder's `decisions.json`.
  - `draft.database(path: str, folder: str | None = None) -> None` — as today, for any folder (NotPlaced while a lesson waits).

- [ ] **Step 1: Write the failing tests**
  - `test_checked_in_matches_the_draft`: after an upload and one fix, with `j = c.get("/api/draft").get_json()`: `draft.checked_in(draft.DIR) == dict(critical=j["critical"], warnings=sum(1 for w in j["warnings"] if not w["decision"] and not w.get("crit")))`.
  - `test_model_in_reads_a_copied_folder`: copy `draft.DIR` to a temp folder, add a fix on the draft; `draft.model_in(copy)[0]["lessons"]` equals the draft's lessons before that fix, and `draft.model_now()[0]` after it.
  - `test_tally_is_what_finish_counts`: for the current draft's warnings and a decisions dict with one "met", `draft.tally(ws, d)["open"]` is one less than with `{}`.
  - `test_database_of_a_folder`: `draft.database(p, folder=copy)` writes a file `ttgen.export.model_from_files(None, p, spec=spec)` reads with the copy's lessons.

- [ ] **Step 2: Run them to see them fail**
  Run: `.venv/bin/python tests/test_versions.py`
  Expected: AttributeError for `checked_in` / `model_in` / `tally`.

- [ ] **Step 3: Implement the interfaces above in `draft.py`**
  `_build` takes `folder=None` and reads `meta.json` from it; `paths`, `database` take `folder`. Keep every current caller's behaviour (no folder = `DIR`).

- [ ] **Step 4: Run the new tests and the suites that use the draft**
  Run: `.venv/bin/python tests/test_versions.py && .venv/bin/python tests/test_board.py && .venv/bin/python tests/test_ask.py && .venv/bin/python tests/smoke.py`
  Expected: all print "N checks passed".

- [ ] **Step 5: Commit**
  `git add draft.py tests/test_versions.py && git commit -m "Draft: read and check any draft folder"`

### Task 2: The versions store

**Files:**
- Create: `versions.py`
- Modify: `draft.py` (`summary()` gains `versions`)
- Test: `tests/test_versions.py`

**Interfaces:**
- Consumes: `draft.DIR`, `draft._lock`, `draft._cache`, `draft.exists`, `draft.checked_in`, `store.read_json`, `store.write_json`, `store.now`, `store.setup_record`.
- Produces (all take `draft._lock`, an RLock, so callers may already hold it):
  - `versions.VDIR = os.path.join(store.DATA, "draft_versions")`; `AUTO_KEEP = 10`; `MAX_SAVED = 30`; `NAME_MAX = 80`; `KINDS = ("saved", "upload", "open", "refit")`.
  - `versions.identity(meta: dict) -> list` — `[upload_id, number of fixes, the newest fix's "at" or None]`.
  - `versions.keep(kind: str, by: str, name: str | None = None) -> dict | None` — copy the draft folder (every file but nothing else) into a new version unless there is no draft or a version with the same identity exists (then None). Default name: the draft's `source` without its extension, then " · " and `saved_at`'s day and month ("Agent run 1 · 22 Nov"). Drops the oldest version of an automatic kind beyond `AUTO_KEEP`. Returns the version dict.
  - `versions.save(name: str, by: str) -> dict` — kind `saved`; ValueError sentences: "Give the version a name." (empty after trim), "A version name is at most 80 characters.", "There are 30 saved versions: delete one first.", "There is no draft."
  - `versions.listing(rec: dict | None = None) -> list[dict]` — newest first; each `dict(id, name, kind, saved_at, by, source, fixes, critical, warnings)`. `critical`/`warnings` from `draft.checked_in`, cached in `version.json` as `checked = dict(v=<setup version>, critical, warnings)` and recomputed when the setup version differs.
  - `versions.folder(vid: str) -> str` — ValueError("There is no such version.") unless `vid` is 12 hex characters and the folder exists.
  - `versions.open_version(vid: str, by: str) -> dict(kept: dict | None, opened: dict)` — `keep("open", by)`, then copy the version's files (not `version.json`) into the draft through `DIR + ".new"` / `DIR + ".old"` as `draft.save` swaps folders, and clear `draft._cache`.
  - `versions.delete(vid: str) -> dict` — removes the folder; returns the removed version's dict.
  - `version.json`: `dict(id, name, kind, saved_at, by, source, identity, checked)`.
  - `draft.summary()` gains `versions=<number of version folders>`.

- [ ] **Step 1: Write the failing tests**
  - `test_save_lists_and_counts`: `versions.save(" Run A ", "Tester")["name"] == "Run A"`; `versions.listing()[0]` has `kind == "saved"`, `by == "Tester"`, `fixes` equal to the draft's, and `critical`/`warnings` equal to `draft.checked_in(draft.DIR)`.
  - `test_names_are_checked`: `save("", …)` and `save("x" * 81, …)` raise ValueError with the sentences above.
  - `test_keep_skips_a_draft_already_kept`: `versions.keep("upload", "T")` twice with no change in between returns a dict, then None; after a fix it returns a dict again.
  - `test_open_keeps_the_draft_whole_and_brings_it_back` (Review Focus 1): make a fix and lift a lesson to Not placed; `v = versions.save("Before", "T")`; upload another timetable; `versions.open_version(v["id"], "T")` → `c.get("/api/draft").get_json()["fixes"]` equals the two fixes from before, the lifted lesson is still in Not placed, and `decisions.json` equals the one saved; `kept` names the upload that was replaced.
  - `test_automatic_keeps_are_capped_and_hand_saves_are_kept` (Review Focus 5): one hand save, then 11 automatic keeps (a fix between each so identities differ): 10 automatic versions remain, the oldest automatic one is gone, the hand-saved one is there; with 30 hand saves the 31st raises "There are 30 saved versions: delete one first."
  - `test_counts_follow_the_setup_version` (Review Focus 3): save a version; change a teacher on step 5 (PUT the setup); `listing()` shows that version's `warnings` one higher, and `version.json`'s `checked.v` is the new setup version.
  - `test_bad_ids_are_refused`: `versions.folder("../draft")`, `folder("zz")`, and a well-formed id with no folder raise "There is no such version."

- [ ] **Step 2: Run them to see them fail**
  Run: `.venv/bin/python tests/test_versions.py`
  Expected: ModuleNotFoundError: versions.

- [ ] **Step 3: Implement `versions.py` with the interfaces above**
  Import `draft` at module top; `draft.py` imports `versions` inside functions only (Task 3), so there is no import cycle.

- [ ] **Step 4: Run the tests**
  Run: `.venv/bin/python tests/test_versions.py`
  Expected: "N checks passed".

- [ ] **Step 5: Commit**
  `git add versions.py draft.py tests/test_versions.py && git commit -m "Versions: keep, list, open and delete copies of the draft"`

### Task 3: An upload keeps the draft instead of asking

**Files:**
- Modify: `draft.py` (`save`), `app.py` (`draft_upload`), `static/app.js` (`uploadDraft`), `tests/smoke.py` (the three tests that expect the 409 refusal: `test_a_new_upload_starts_with_no_decisions` (its last three lines, the fixes refusal), `test_an_upload_over_unpublished_fixes_is_refused_by_the_draft_and_replace_clears_them`, `test_a_lesson_not_placed_refuses_the_printouts_the_download_and_a_new_upload`)
- Test: `tests/test_versions.py`, `tests/smoke.py`

**Interfaces:**
- Consumes: `versions.keep`.
- Produces:
  - `draft.save(setup_path, timetable_path, source, spec, replace=False, by="Committee", out=None) -> dict` — after the new files are read successfully and before the folder swap, calls `versions.keep("upload", by)`; when `out` is a dict, sets `out["kept"]` to that result (dict or None). `UnpublishedFixes` is no longer raised (the class stays, unused, so old imports do not break; `replace` is accepted and ignored).
  - `POST /api/draft` answers `dict(<info as today>, kept=<version dict or None>)`; its history text is "Uploaded {name}" plus, when a version was kept, "; the draft before is kept as version “{kept name}”".
  - Page: no "Replace the draft?" question; after an upload with `kept`, `toast("The draft you had is kept as version “" + kept.name + "”.")`.

- [ ] **Step 1: Write the failing test and change the three smoke tests**
  - `test_upload_over_fixes_keeps_the_draft` (test_versions): a fix, then upload another file → status 200, `j["kept"]["kind"] == "upload"`, `j["fixes"] == []`, and the kept version's `fixes == 1`.
  - In `tests/smoke.py`, the three refusals become: status 200, `r.get_json()["kept"]` is a dict with `kind == "upload"`, and `c.get("/api/draft").get_json()["fixes"] == []`; the direct `draft.save(None, None, "x", spec)` check that expects `UnpublishedFixes` is removed (keep the rest of each test). Keep the not-placed test's checks of printouts, download and publish as they are.

- [ ] **Step 2: Run to see them fail**
  Run: `.venv/bin/python tests/test_versions.py; .venv/bin/python tests/smoke.py`
  Expected: the new test fails on status 409; smoke fails on the changed assertions.

- [ ] **Step 3: Implement the interfaces above**
  In `app.py` pass `by=by()["as"]` and `out={}`; in `static/app.js` remove the 409/`confirm` branch of `uploadDraft` and add the toast.

- [ ] **Step 4: Run the tests**
  Run: `.venv/bin/python tests/test_versions.py && .venv/bin/python tests/smoke.py && node --check static/app.js`
  Expected: "N checks passed" twice; no output from node.

- [ ] **Step 5: Commit**
  `git add draft.py app.py static/app.js tests/test_versions.py tests/smoke.py && git commit -m "Upload: keep the draft as a version instead of asking to replace it"`

### Task 4: Version routes

**Files:**
- Modify: `app.py`
- Test: `tests/test_versions.py`

**Interfaces:**
- Consumes: `versions.*`, `draft.database(path, folder=)`, `_draft_entry`, `by()`.
- Produces (all `@need("committee")`; errors as `{"error": sentence}` with 400, or 404 for "There is no such version.", 409 for NotPlaced with `unplaced` as the draft download does):
  - `GET /api/draft/versions` → `dict(versions=listing(), draft=<draft summary with critical/warnings from draft.info() or None>, published=dict(published_at, critical, warnings) or None)`. Published counts come from Task 5's `compare.published_counts()`; until Task 5 lands, `published` may be `None` (Task 5 fills it in).
  - `POST /api/draft/versions` body `{name}` → the new version; history "Saved version “{name}”".
  - `POST /api/draft/versions/<vid>/open` → `dict(info=<draft info>, kept=…, opened=…)`; history "Opened version “{name}”" plus "; the draft before is kept as version “{kept}”" when kept.
  - `DELETE /api/draft/versions/<vid>` → `dict(deleted=<version>)`; history "Deleted version “{name}”".
  - `GET /api/draft/versions/<vid>/download` → the version as `.sqlite`, file name "{version name} - version.sqlite" (through `ttgen.export.safe_name`).

- [ ] **Step 1: Write the failing tests**
  - `test_version_routes_need_the_committee`: each route answers 401 for a client that never signed in.
  - `test_save_open_delete_through_the_routes`: POST a name → 200; GET lists it; POST open → 200 and `info["fixes"]` matches the version; DELETE → 200 and GET no longer lists it; the history (`history.read` or the history API the History page uses) has the three entries' texts.
  - `test_a_deleted_version_is_refused_plainly` (Review Focus 2): after DELETE, open, download and DELETE again each answer 404 `{"error": "There is no such version."}`.
  - `test_download_a_version`: the file reads back with `model_from_files(None, path, spec=spec)` and has the version's lessons.

- [ ] **Step 2: Run to see them fail**
  Run: `.venv/bin/python tests/test_versions.py`
  Expected: 404s from Flask for the unknown routes.

- [ ] **Step 3: Implement the routes**

- [ ] **Step 4: Run the tests**
  Run: `.venv/bin/python tests/test_versions.py && .venv/bin/python tests/smoke.py`
  Expected: "N checks passed" twice.

- [ ] **Step 5: Commit**
  `git add app.py tests/test_versions.py && git commit -m "Versions: routes to save, open, delete and download"`

### Task 5: Compare two timetables

**Files:**
- Create: `compare.py`
- Modify: `app.py` (fill `published` in `GET /api/draft/versions`)
- Test: `tests/test_compare.py` (new, same frame as `tests/test_versions.py`)

**Interfaces:**
- Consumes: `draft.model_now`, `draft.model_in`, `draft.counts`, `versions.folder`, `versions.listing`, `store.published`, `ttgen.database.write_db`, `ttgen.export.model_from_files`, `helper._keys_of` (a row's planned keys), openpyxl.
- Produces:
  - Sources are strings: `"draft"`, `"published"`, `"v:<id>"`. `compare.label(src: str) -> str` ("The draft on step 8", "Published timetable", or the version's name).
  - `compare.model_of(src: str, rec: dict) -> dict` — the timetable with its fixes applied. `published`: write `store.published()["model"]` to a temp `.sqlite` with `write_db` and read it back with `model_from_files(None, path, spec=rec["spec"])`. ValueError sentences: "There is no draft.", "Nothing is published yet.", "There is no such version."
  - `compare.published_counts(rec: dict | None = None) -> dict(published_at, critical, warnings) | None`.
  - `compare.rows(m: dict) -> list[dict]` — one per lesson row: `key` (the planned key as a string: `"C:{class}:{subject}"` for a whole-class row, one row per class; `"G:{code}"` for a group), `id`, `d`, `p`, `n`, `teachers` (sorted), `room`, `subject`, `classes`, `group`, `block`, `what` (`fixes.what`).
  - `compare.pair(a: list[dict], b: list[dict]) -> list[tuple[dict | None, dict | None]]` — per key: rows at the same `(d, p)` pair first; the rest pair in `(d, p)` order; leftovers pair with None. Deterministic (sort keys, then `(d, p, room)`).
  - `compare.diff(src_a: str, src_b: str, rec: dict | None = None) -> dict` with:
    - `totals = dict(lessons=<distinct lesson ids in B>, moved=<distinct B ids with a row at another (d, p)>, teacher=<… another teacher set>, room=<… another room>, critical=[a, b], warnings=[a, b], longest=[a, b])` — `longest` is the most periods any teacher has in one day; critical and warnings from `draft.counts` (draft: `draft.info()`'s own counts).
    - `items = [dict(a=row | None, b=row | None, kinds=list)]` — only pairs that differ; kinds from `"time"`, `"teacher"`, `"room"`, `"only_a"`, `"only_b"`.
    - `names = dict(classes=[…], teachers=[…], rooms=[…])` over both sides, in the setup's order for classes and teachers, sorted for rooms.
  - `compare.line(item: dict, days: list[str]) -> str` — "Mathematics: Mon 3 → Mon 6"; "Social Studies: Fri 2 → Thu 4, teacher Karen Ismail → Hakim Kumar"; "Science: room Lab 1 → Lab 2"; "Science: only in B (Thu 7)"; "Art: only in A (Tue 5)". Day names from `m["days"]`, periods as the board numbers them.
  - `compare.week(m: dict, view: str, name: str) -> dict(days, NP, times, cells)` — `view` in `class`, `teacher`, `room`; `cells` = the rows of that class / teacher / room as `dict(d, p, n, short, what, teachers, room, block, key)`; ValueError("Pick a class, teacher or room on both timetables.") for an unknown name.
  - `compare.xlsx(src_a: str, src_b: str, rec: dict | None = None) -> bytes` — one sheet "Differences", columns Class, Lesson, A, B; one row per item per class of the row, classes in setup order.

- [ ] **Step 1: Write the failing tests** (two made-up Lessons workbooks over the primary sample, with different lesson ids for the same lessons)
  - `test_pairs_ignore_ids_and_list_lessons_on_one_side` (Review Focus 4): B has every lesson of A with new ids, one lesson at another period on the same day, one with another teacher, and one extra lesson. `diff("v:<A>", "draft")["totals"]` has `moved == 1`, `teacher == 1`; `items` has exactly one `only_b`; no item for the unchanged lessons.
  - `test_lines_read_as_the_spec_says`: `line()` of a moved lesson with another teacher reads `"{subject}: {day} {p} → {day} {p}, teacher {a} → {b}"`; an extra lesson reads `"{subject}: only in B ({day} {p})"`.
  - `test_week_of_a_room`: `week(m, "room", r)["cells"]` holds exactly the rows in room `r`.
  - `test_published_compares`: publish the draft (POST `/api/draft/publish` on a draft with no critical mistakes), then `diff("published", "draft")["items"] == []` and `published_counts()["critical"] == 0`.
  - `test_nothing_published_is_said`: on a fresh `DATA_DIR` with no publish, `model_of("published", rec)` raises "Nothing is published yet."
  - `test_excel_has_one_row_per_difference`: the sheet's data rows equal the number of (item, class) pairs.

- [ ] **Step 2: Run to see them fail**
  Run: `.venv/bin/python tests/test_compare.py`
  Expected: ModuleNotFoundError: compare.

- [ ] **Step 3: Implement `compare.py` with the interfaces above; fill `published` in `GET /api/draft/versions`**

- [ ] **Step 4: Run the tests**
  Run: `.venv/bin/python tests/test_compare.py && .venv/bin/python tests/test_versions.py`
  Expected: "N checks passed" twice.

- [ ] **Step 5: Commit**
  `git add compare.py app.py tests/test_compare.py && git commit -m "Compare: match two timetables by lesson and list what differs"`

### Task 6: The Compare page

**Files:**
- Create: `static/compare.html`, `static/compare.js`
- Modify: `app.py` (routes), `README.md` (a "Saved versions and Compare" paragraph under step 8)
- Test: `tests/test_compare.py`; browser check

**Interfaces:**
- Consumes: `compare.diff`, `compare.week`, `compare.line`, `compare.label`, `compare.xlsx`, `versions.listing`.
- Produces:
  - `GET /compare` → `compare.html` (`@need("committee")`), query `a`, `b`, `view`, `name` (defaults: `a` from the query, `b = "draft"`, `view = "class"`, `name` = the first class that has a difference, else the first class).
  - `GET /api/compare?a=&b=&view=&name=` → `dict(a=dict(src, label), b=dict(src, label), sources=[dict(src, label)], totals, names, view, name, weeks=dict(a=week, b=week), marks=dict(a=[[d, p], …], b=[[d, p], …]), lines=[str])` — `marks` are the cells of that class / teacher / room that take part in a differing item; `lines` are `compare.line` of the items that involve that name.
  - `GET /api/compare.xlsx?a=&b=` → the Excel file "Differences {label a} and {label b}.xlsx" (through `safe_name`).
  - The page, as screen 2 of the mockups: two source pickers ("with" between), six tiles (Lessons at another time "of {lessons}", Teacher different, Room different, Critical a → b, Warnings a → b, Teachers' longest day a → b), **Show** picker over classes, teachers and rooms, "mark what differs" box (on), two week grids side by side (stacked below 760 px wide) with differing cells outlined orange and band cells light blue, "What differs for {name}" list, **Download the differences (Excel)**, **Back to step 8** (to `/`). The "Checked now" sentence under the tiles. Styles in the page's own `<style>` like `history.html`, using `style.css` variables.

- [ ] **Step 1: Write the failing route tests**
  - `test_compare_routes_need_the_committee`: `/compare`, `/api/compare`, `/api/compare.xlsx` → 401 (API) or a redirect to `/login` (page) without sign-in.
  - `test_compare_api_shape`: with the two made-up timetables, `/api/compare?a=v:<A>&b=draft&view=class&name=<a class with the moved lesson>` has `len(lines) >= 1`, `marks["b"]` contains the moved lesson's new `[d, p]` and `marks["a"]` its old one.
  - `test_compare_unknown_source`: `a=v:000000000000` → 404 "There is no such version."

- [ ] **Step 2: Run to see them fail**
  Run: `.venv/bin/python tests/test_compare.py`
  Expected: 404 for `/api/compare`.

- [ ] **Step 3: Implement the routes and the page**

- [ ] **Step 4: Run the tests and check the page in a browser**
  Run: `.venv/bin/python tests/test_compare.py && node --check static/compare.js`
  Browser (scratch server, made-up files, real clicks): open `/compare?a=v:<id>&b=draft`; change Show to a teacher and to a room; untick "mark what differs"; press Download (a file arrives); phone width stacks the grids; no script errors.

- [ ] **Step 5: Commit**
  `git add static/compare.html static/compare.js app.py README.md tests/test_compare.py && git commit -m "Compare: the page, its API and the Excel download"`

### Task 7: The Versions pop-out on step 8

**Files:**
- Modify: `static/app.js` (upload card head; pop-out; actions), `static/style.css`, `README.md`
- Test: browser check (no unit test: the logic is on the server)

**Interfaces:**
- Consumes: the Task 4 routes, `/compare`, `draft.summary()["versions"]` via `/api/status`.
- Produces:
  - A **Versions (n)** button in the upload card's head (n from `/api/status`'s `draft.versions`; "Versions" when 0), opening a fixed pop-out over the page (dimmed backdrop; Esc and **Close** shut it), as screen 1 of the mockups: the explanation line, **Save the draft as** with a name box (default "{draft source without extension} · edited {day month}") and **Save version**, then the table (Version, Saved, Changes made in the app, Checked now, buttons) with the draft row ("now", Compare… only), every version (Open, Compare…, Download, Delete), and the published row ("what teachers see", Compare… only) when something is published, then the "Checked now" sentence.
  - **Open** asks nothing (the draft is kept first) and closes the pop-out after redrawing step 8 from the returned `info`, with `toast("Opened “{name}”. The draft you had is kept as version “{kept}”.")` (second sentence only when kept). **Delete** asks `confirm("Delete the version “{name}”? This cannot be undone.")`. **Compare…** goes to `/compare?a=<that row's source>&b=draft` (for the draft row: `a=draft&b=` the newest version, or published when there is none). **Download** fetches the version download and saves the file (a 409 shows the server's sentence).
  - State lives in one object `VS = { open, list, busy }`; the pop-out redraws itself only (like `drawDraft` redraws the upload card), so step 8's board keeps its state.

- [ ] **Step 1: Implement the button, the pop-out and its actions**

- [ ] **Step 2: Check it in a browser** (scratch server, made-up files, real clicks for every button)
  Save a version; upload another timetable (toast names the kept version; n goes up); Open the first (its changes are back in the Changes tab, toast); Compare… opens the compare page with the right pair; Download saves a `.sqlite`; Delete asks and removes the row; Esc closes; phone width; no script errors.

- [ ] **Step 3: Run the suites**
  Run: `node --check static/app.js && for f in tests/*.test.js; do node "$f" >/dev/null || echo FAIL $f; done && .venv/bin/python tests/smoke.py && .venv/bin/python tests/test_versions.py && .venv/bin/python tests/test_compare.py`
  Expected: no FAIL lines; "N checks passed" three times.

- [ ] **Step 4: Commit**
  `git add static/app.js static/style.css README.md && git commit -m "Step 8: the Versions pop-out"`

### Task 8: Real-file check and notes

**Files:**
- Create: `docs/superpowers/plans/2026-11-22-saved-versions-stage-1-notes.md`

- [ ] **Step 1: Time it on the school's real timetable (counts only, nothing printed by name)**
  With a copy of the newest real setup and timetable on a scratch `DATA_DIR`: time `versions.keep`, `versions.listing()` with 10 versions (first call and cached), `versions.open_version`, and `compare.diff` of two versions and of the draft against the published copy. Expected: listing with a warm cache under 1 s; one `checked_in` and one `diff` each a few seconds at most. Write the times and the version folder size in the notes.

- [ ] **Step 2: Write the notes file**
  Rulings made while building, the real-file counts, what was not tried in a browser (the system file picker, a real drag), and the points held for stage 2 (the `refit` kind is reserved; re-fit will call `versions.keep("refit", by, name)`).

- [ ] **Step 3: Run every suite**
  Run, each on its own: `.venv/bin/python tests/<name>.py` for test_typed, test_helper, test_fixes, test_verify, test_rules, test_choices, test_parents, test_sync, test_versions, test_compare and smoke; every `node tests/*.test.js`; `node --check` on every `static/*.js`.
  Expected: every one passes.

- [ ] **Step 4: Commit**
  `git add docs/superpowers/plans/2026-11-22-saved-versions-stage-1-notes.md && git commit -m "Saved versions: notes and real-file counts"`

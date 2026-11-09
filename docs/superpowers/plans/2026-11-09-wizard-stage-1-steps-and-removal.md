# Wizard stage 1: new steps, Generate and Adjust removed — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The committee's editor shows the new step list (School and day → … → Configuration and constraints → Download → Publish), the school-wide settings live on step 7, and everything that generates or adjusts a timetable inside the app is gone.

**Architecture:** This is stage 1 of the six in the spec ("Suggested order of building"); stages 2 to 6 get their own plans when their turn comes. It only moves and removes: no new data, no change to the spec's JSON shape, the workbook or `ttgen`. Not in this stage: the heads' code and self-saving changes (stage 2), the starter prompt, configuration id, rule report and typed rules (stage 6). The server loses its run machinery (`runs.py`, `timetabler.py`, `ai.py`, `adjust.py`); the one-file editor (`static/app.js`) loses the Generate, chat and Adjust code and gains a Publish view built from the existing "A timetable made outside the app" card.

**Tech Stack:** Python 3.11, Flask 3, vanilla JavaScript in one file with no build step, `ttgen` (OR-Tools, openpyxl, reportlab) unchanged.

**Spec:** `docs/superpowers/specs/2026-11-09-setup-wizard-design.md`

## Global Constraints

- Flask and one vanilla JS file with no build step. No framework, no bundler.
- `ttgen/` stays whole and is not edited in this stage; `ttgen/` and `skill/school-timetable-generator/scripts/ttgen/` stay identical.
- A setup saved today, and a workbook from an earlier template, must still open.
- The repository is public: no secrets, no real names; never commit `.claude/launch.json` or `data/`.
- Save progress, Undo and Redo keep working exactly as today (shared editing is stage 2).
- Commit on branch `wizard-redesign` after each task. Do not push or open a pull request until the committee asks.
- Wording in the page: plain sentences, sentence case, no "please", no exclamation marks.
- The project has no test runner. Server checks go in `tests/smoke.py`, run with `.venv/bin/python tests/smoke.py` (plain `assert`, no new dependency). Page checks are done in the browser preview (launch config `timetable-branch`, port 8002; its test codes are in `/Users/joetay/Developer/tt-generator/.claude/launch.json`, never typed into chat or committed).

## Review Focus

1. A browser whose saved step is "generate", "adjust" or "download" (kept by name in `localStorage`) → opens on Publish (first two) or Download, not on a blank page or an exception. Pinned in Task 2.
2. Railway still has `AI_PROVIDER`, `AI_API_KEY`, `SOLVE_SECONDS` set → the app starts, ignores them, and makes no outbound call. Pinned in Task 1.
3. A data folder that still holds `runs/` from earlier generating → the app starts and `/api/past-setups` still lists those copies. Pinned in Task 1.
4. A timetable published earlier from an in-app run (its `meta.json` has `run` set and no `source`) → Publish shows it as published, with its date, and the teacher and student pages still serve it. Pinned in Task 4.
5. A setup with no "Lessons end by" rows, or an imported older workbook → step 7 shows the settings it has and nothing breaks; a bad end time is listed under Things to fix and its link opens step 7, not step 1. Pinned in Task 3.

---

### Task 1: Server without generation, AI or Adjust

**Files:**
- Modify: `app.py` (imports line 15; `startup_log` 51-56; `/api/allocate` 178-189; `/api/import-timetable` 284-306; everything from the "committee: generate, chat, publish" banner at 339 to the end of `/preview` at 517, keeping `pub_info`)
- Delete: `runs.py`, `timetabler.py`, `ai.py`, `adjust.py`
- Modify: `requirements.txt` (drop `anthropic`; drop `requests` only if nothing else imports it)
- Create: `tests/smoke.py`

**Interfaces:**
- Produces: `GET /api/status` → JSON with exactly the keys `codes`, `code_problems`, `volume`, `setup_saved_at`, `published` (`published` is `pub_info()` unchanged, or `null`). Task 2 and Task 4 read only these.
- Produces: `POST /api/import-timetable` behaves as today minus the "wait for the work on Generate" 409.
- Removed for good: `POST /api/generate`, `/api/message`, `/api/stop`, `/api/keep-changes`, `/api/publish`, `/api/allocate`, every `/api/adjust*` route, `GET /preview`.

- [ ] **Step 1: Write `tests/smoke.py` with the failing checks**

```python
"""Server smoke checks. Run: .venv/bin/python tests/smoke.py   (add --full for the slow publish check)"""
import os, secrets, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = tempfile.mkdtemp()
CODES = {k: secrets.token_hex(4) for k in ("COMMITTEE_CODE", "TEACHER_CODE", "STUDENT_CODE")}
# variables an existing deployment may still have: they must be ignored
os.environ.update(DATA_DIR=DATA, SECRET_KEY=secrets.token_hex(16), AI_PROVIDER="anthropic", AI_API_KEY="", SOLVE_SECONDS="60", **CODES)
os.makedirs(os.path.join(DATA, "runs", "old1"))
sys.path.insert(0, ROOT)
import app as A, store

c = A.app.test_client()
assert c.post("/login", data={"as": "committee", "code": CODES["COMMITTEE_CODE"]}).status_code == 302

def test_removed_modules():
    for m in ("runs", "timetabler", "ai", "adjust"):
        assert m not in sys.modules, m
        assert not os.path.exists(os.path.join(ROOT, m + ".py")), m

def test_removed_routes():
    gone = [("POST", "/api/generate"), ("POST", "/api/message"), ("POST", "/api/stop"), ("POST", "/api/keep-changes"), ("POST", "/api/publish"),
            ("POST", "/api/allocate"), ("GET", "/api/adjust"), ("POST", "/api/adjust/move"), ("POST", "/api/adjust/ask"), ("GET", "/preview")]
    for method, url in gone:
        assert c.open(url, method=method).status_code in (404, 405), url

def test_status_shape():
    j = c.get("/api/status").get_json()
    assert set(j) == {"codes", "code_problems", "volume", "setup_saved_at", "published"}, sorted(j)
    assert j["published"] is None

def test_old_runs_folder_is_harmless():
    assert c.get("/api/past-setups").status_code == 200

def test_setup_round_trip():
    spec = c.get("/api/sample/secondary").get_json()
    assert c.put("/api/setup", json=spec).status_code == 200
    assert c.get("/api/setup").get_json()["spec"]["school"]["name"] == spec["school"]["name"]

def test_publish_uploaded_timetable():   # slow: solves the primary sample
    work = tempfile.mkdtemp(); setup, tt = os.path.join(work, "setup.xlsx"), os.path.join(work, "timetable.xlsx")
    env = dict(os.environ, PYTHONPATH=ROOT)
    subprocess.run([sys.executable, "-m", "ttgen", "sample", "primary", "--out", setup], check=True, env=env, cwd=ROOT)
    subprocess.run([sys.executable, "-m", "ttgen", "solve", setup, "--out", tt, "--time", "60"], env=env, cwd=ROOT)
    r = c.post("/api/import-timetable", data={"publish": "1", "setup": (open(setup, "rb"), "setup.xlsx"), "timetable": (open(tt, "rb"), "timetable.xlsx")},
               content_type="multipart/form-data")
    j = r.get_json(); assert r.status_code == 200 and j["published"] is True, j
    p = c.get("/api/status").get_json()["published"]
    assert p and p["source"] == "timetable.xlsx"
    t = A.app.test_client(); t.post("/login", data={"as": "teacher", "code": CODES["TEACHER_CODE"]})
    assert t.get("/timetable").status_code == 200

if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_") and (k != "test_publish_uploaded_timetable" or "--full" in sys.argv)]
    for t in tests: t(); print("ok", t.__name__)
    print(f"{len(tests)} checks passed")
```

- [ ] **Step 2: Run it and see it fail**

Run: `.venv/bin/python tests/smoke.py`
Expected: fails in `test_removed_modules` (`runs` is in `sys.modules`).

- [ ] **Step 3: Remove the run machinery from `app.py`**

- Line 15 becomes `import access, store`.
- `startup_log()` prints `Timetable app: data in {store.DATA}` and the `setup_problems()` warnings; no AI line.
- Delete `/api/allocate`.
- In `import_timetable()`, delete `r = runs.current()` and the 409 that follows.
- `status()` returns only the five keys named under Interfaces.
- Delete `generate`, `message`, `stop`, `keep_changes`, `_publish_job`, `publish`, `_adj_run`, `_adj` and every `/api/adjust*` route, and `preview`. Keep `pub_info`, `NO_PERSONAL`, `codes_csv`, `code_slips` and everything after them.
- Delete `normalise()` if nothing else calls it after this (today only `generate` does).
- Update the module docstring (lines 1-6): the committee fills the setup, downloads it, and publishes a timetable made outside.

- [ ] **Step 4: Delete `runs.py`, `timetabler.py`, `ai.py`, `adjust.py`; trim `requirements.txt`**

`git rm runs.py timetabler.py ai.py adjust.py`. Then `grep -rn "import requests\|from requests\|anthropic" --include=*.py .` (outside `.venv`): remove from `requirements.txt` each package that no remaining file imports.

- [ ] **Step 5: Run the checks**

Run: `.venv/bin/python tests/smoke.py` → `5 checks passed`.
Run: `.venv/bin/python tests/smoke.py --full` → `6 checks passed` (about two minutes).
Run: `.venv/bin/python -m py_compile app.py store.py access.py` → no output.

- [ ] **Step 6: Commit**

```bash
git add -A app.py requirements.txt tests/smoke.py runs.py timetabler.py ai.py adjust.py
git commit -m "Remove in-app generation, the AI timetabler and Adjust from the server"
```

---

### Task 2: The new step list, with Generate and Adjust gone from the page

**Files:**
- Modify: `static/app.js` (`STEPS` 8-9; `saved()` 28-34; `VIEWS.generate` 806-820 and `VIEWS.adjust` 821-844 deleted; click and change handlers 866-985; `helper()` 1074; "generate, chat, publish" 1391-1520; "Adjust timetable" 1582 to the end of file)
- Modify: `static/index.html` (header subtitle, line 13)
- Modify: `static/style.css` (delete rules used only by the removed views)

**Interfaces:**
- Consumes: `GET /api/status` keys from Task 1.
- Produces: `STEPS` ids, in order: `start`, `school`, `venues`, `classes`, `subjects`, `teachers`, `lessons`, `rules`, `download`, `publish`, `students`. Labels: `Start`, `1 School & day`, `2 Venues`, `3 Classes`, `4 Subjects`, `5 Teachers`, `6 Teaching groups`, `7 Configuration & constraints`, `8 Download`, `9 Publish`, `Students`. (Step 6 keeps today's table until stage 4 adds the map.)
- Produces: `G = { server, st, timer, inflight }` and `poll()`, which fetches `/api/status` into `G.st`, redirects to `/login` on 401, calls `paintBanner()`, calls `paintPublished()` if it exists, and re-arms itself every 5 seconds. Task 4 defines `paintPublished()`.
- Produces: `VIEWS.publish` as a stub card ("Publish" heading) that Task 4 fills.

- [ ] **Step 1: Replace `STEPS` and teach `saved()` the old names**

In `saved()`, before looking the name up: `generate` and `adjust` → `publish`; `blocks` → `lessons` (already handled by `stepAt`); anything unknown → `start`.

- [ ] **Step 2: Delete the Generate, chat and Adjust code**

Remove: `VIEWS.generate`, `VIEWS.adjust`; `generate`, `sendChat`, `solveSecs`, `paintGen`, `compromisesHTML`, `fixesHTML` and the event renderers they use; every `adj*` function, `loadAdjust`, the Adjust keydown handler; `allocateTeachers`, the "Teachers for rows left blank" helper row in `VIEWS.lessons`, `blankRows`; the click and change branches for `genAI`, `genPlain`, `genStop`, `publish`, `keepChanges`, `data-answer`, `data-adj*`, `data-lesson`, `td.as`, `solveSecs`, `adjKind`, `adjWho`. Keep `post()`, `exportCard`, `timetableForm`, `makePrintouts`, `importTimetable`, `importHTML`, `buildXlsx`, `paintBanner`.
Shrink `G` and `poll()` to the Interfaces above. `poll()` must no longer read `st.run` or `st.ai`.

- [ ] **Step 3: Add the `VIEWS.publish` stub and fix the wording that names removed things**

`VIEWS.start` lead, `VIEWS.download` lead ("To generate here, use Generate & publish…"), `VIEWS.students` heading ("after the timetable is made") and the header subtitle in `index.html` must not mention generating in the app. Header subtitle: "Committee: build the setup step by step, download it, then publish the finished timetable."

- [ ] **Step 4: Delete dead CSS**

For each selector in `static/style.css` matching `.gen`, `.chat*`, `.ev*`, `.progress`, `.adj*`, `.compbox`: delete it if `grep` finds no use left in `static/app.js` or `app.py`.

- [ ] **Step 5: Check**

Run: `node --check static/app.js` → no output.
Run: `grep -n -E "api/(generate|message|stop|keep-changes|publish\b|adjust|allocate)|/preview|st\.run|st\.ai|solveSecs" static/app.js` → no lines.
Browser (start `timetable-branch`, sign in as committee, open the sample secondary school):
- the step list reads exactly as the labels above, and every step opens with no console error (`read_console_messages`, errors only);
- in the page, run `localStorage.setItem("ttsetup.v1", localStorage.getItem("ttsetup.v1").replace(/"at":"[^"]*"/, '"at":"adjust"'))`, reload, press "Continue in this browser": the Publish step opens;
- Undo, Redo and Save progress still work on a changed class size.

- [ ] **Step 6: Commit**

```bash
git add static/app.js static/index.html static/style.css
git commit -m "New step list; Generate, chat and Adjust removed from the editor"
```

---

### Task 3: School-wide settings move to step 7

**Files:**
- Modify: `static/app.js` (`VIEWS.school` 643-671, `VIEWS.rules` 755-783, `issues()` settings checks near 305-327, `settingRow` 253-261, `stepAt` and `count`, the Day structure notice)

**Interfaces:**
- Consumes: `SET()`, `settingValue`, `setSetting`, `settingRow`, `isRecessRow`, `structureWarnings` (all exist).
- Produces: `VIEWS.rules` opens with a card headed "Configuration" holding every control that is in the "Rules on the Settings sheet" card today, then the three existing cards (Teacher availability, Fixed lessons, More rules) and Rule types. The step's `h1` reads "Step 7 · Configuration and constraints". (The constraint tabs and typed rules are stage 6.)
- Produces: issue kind `config` for problems with a Settings row: `out.config`, row id `config-${i}`, and `stepAt("config")` returns the `rules` step. `settingRow` renders `id="config-${i}"`.

- [ ] **Step 1: Move the card**

Cut the `<div class="card"><h2>Rules on the Settings sheet</h2>…</div>` block from `VIEWS.school` and render it first in `VIEWS.rules`, headed "Configuration", with the muted line "School-wide settings. They apply to every class and teacher." The floating recess rows stay under the Day structure on step 1 (they belong to the W periods painted there). `VIEWS.school`'s lead keeps its text about L, A and W periods.

- [ ] **Step 2: Point the checks at step 7**

In `issues()`: the two checks on "Lessons end by" rows (`add("school", i, …)` inside the `extra_settings` loop) become `add("config", i, …)`. Floating recess checks stay `school`. `structureWarnings()` messages that are not about a fixed lesson stay on `school` (they are fixed by painting the Day structure), and the notice above the Day structure now says "The Day structure and the settings on step 7 disagree."

- [ ] **Step 3: Check in the browser**

- Step 1 shows school details, Day structure and (with W periods) floating recess; no settings card.
- Step 7 shows Configuration first; changing "Most PE classes at the same time" to 3, then opening step 1 and back, still shows 3; Undo restores it.
- Set "Lessons end by (Friday)" to `07:00`: Things to fix lists it as critical; clicking it opens step 7 and scrolls to that field.
- Review Focus 5: in the page run `S.spec.school.extra_settings = []; save(); render()` on step 7 → the Configuration card shows the six standard settings and no error in the console. Then open the school's older workbook through "Open a setup workbook" on Start (any workbook written by `python -m ttgen sample secondary` will do): step 7 shows its settings.
Run: `node --check static/app.js`.

- [ ] **Step 4: Commit**

```bash
git add static/app.js
git commit -m "Move the school-wide settings to step 7, Configuration and constraints"
```

---

### Task 4: The Download and Publish steps

**Files:**
- Modify: `static/app.js` (`VIEWS.download` 845-862, `VIEWS.publish` stub from Task 2, `exportCard` 617-625, the old `#pubCard` painter inside the removed `paintGen` (recover its markup from `git show main:static/app.js`, lines 1508-1519), header handlers for `saveJson` / `loadJson`)
- Modify: `static/index.html` (remove "Save to file" and "Load from file" from the header, lines 20-21)

**Interfaces:**
- Consumes: `G.st.published` (`at`, `ok`, `after`, `students`, `classes`, `files`, `problems`, `personal`, `source`), `G.st.codes`, `G.st.code_problems`, `G.st.volume`; `exportCard()`, `importTimetable()`, `makePrintouts()`.
- Produces: `paintPublished()`: fills `#pubNow` on the Publish step from `G.st`; a no-op when that element is not on the page. Called by `poll()` and at the end of `render()`.

- [ ] **Step 1: Download**

`VIEWS.download`, heading "Step 8 · Download", in this order:
1. the counts and the Things to fix summary line (as today);
2. "Configuration workbook (.xlsx)" with the existing `#build` button;
3. "The timetable skill": **Skill (.zip)** as the primary button, "SKILL.md only" second, with the line "Use the zip when the chatbot can run code: its scripts make a timetable file this app can publish as it is.";
4. "How to make the timetable": the four-step list that is there today, with step 3 ending "…and hands back the timetable file. Bring that file to step 9, Publish.";
5. "Keep a copy": **Save to file** and **Load from file** (the two controls moved from the header, same ids `saveJson` and `loadJson`, so their handlers need no change);
6. "Templates to share" (as today).
`exportCard()` is no longer part of this view.

- [ ] **Step 2: Publish**

`VIEWS.publish`, heading "Step 9 · Publish", two cards:
1. `exportCard()` as it is, retitled "Publish the finished timetable", its first paragraph starting "Upload the timetable the chatbot made, with its setup workbook."
2. `<div class="card" id="pubNow"></div>`, painted by `paintPublished()` with what `#pubCard` showed: nothing published yet, or "Published {at}" (+ " from {source}" when `source` is set), its checks line, the "Open the timetable" button, the access-code status with `code_problems`, the personal codes CSV and code slips links when `personal` is true, and the no-volume warning when `volume` is false. Drop the hint that pointed to Files.
A file input must not sit inside `#pubNow`: polling repaints it.

- [ ] **Step 3: Update the skill's pointer**

`skill/school-timetable-generator/SKILL.md` line 71 says to publish "on Files"; change it to "on step 9, Publish". (`SKILL.md` is not part of the `ttgen` copy; no sync needed.)

- [ ] **Step 4: Check**

Run: `node --check static/app.js`; `.venv/bin/python tests/smoke.py`.
Browser:
- Download: the workbook downloads (`read_network_requests` shows `POST /api/build` 200); Save to file and Load from file work from their new place; the header no longer has them.
- Publish with nothing published: `#pubNow` says so. Then publish a timetable through the card (serve `setup.xlsx` and `timetable.xlsx` made as in `tests/smoke.py` from a local CORS file server and set them on the inputs with a `DataTransfer`, as PR #33's test did): the result shows, `#pubNow` changes to "Published … from timetable.xlsx" within one poll, and the chosen files are still named in the card.
- Review Focus 4: stop the server, edit the published `meta.json` in the scratch data folder to `"source": null, "run": "r1"`, start again: `#pubNow` shows "Published {at}" with no "from", and `/timetable` (teacher code) still opens.

- [ ] **Step 5: Commit**

```bash
git add static/app.js static/index.html skill/school-timetable-generator/SKILL.md
git commit -m "Download and Publish steps replace Files and Generate & publish"
```

---

### Task 5: README and deployment guide

**Files:**
- Modify: `README.md` (the opening description; "How it works" and the AI timetabler section around lines 30-60; Railway setup step near 117; the solver paragraphs 122-131; "Try it without a key" 165; the local run command 173; the file table 185-196)
- Modify: `docs/DEPLOY.md` (variables block 57-58, table rows 71-81, sections at 101, 114, 124, 150, 180)

**Interfaces:** none.

- [ ] **Step 1: README**

Say what the app is now: the committee builds the setup, downloads the workbook and the skill, an outside AI agent makes the timetable, the committee publishes it on step 9. Remove every description of Generate, the chat, Adjust, the AI timetabler's tools, `AI_*`, `SOLVE_SECONDS`, `STAGED_FROM_CLASSES`, and the rows for `runs.py`, `timetabler.py`, `adjust.py`, `ai.py` in the file table; add `tests/smoke.py`. Keep the Rules, Rooms, Command line and skill sections (they describe `ttgen`, which the outside agent uses). The local run command loses `AI_PROVIDER=mock`.

- [ ] **Step 2: `docs/DEPLOY.md`**

Remove the AI and solve-time variables and the sections about the AI timetabler, its cost and what it sends out. Add one short section "Coming from an earlier version": the variables `AI_PROVIDER`, `AI_API_KEY`, `AI_MODEL`, `SOLVE_SECONDS`, `STAGED_FROM_CLASSES` and `MOCK_SOLVE_SECONDS` are no longer read and can be deleted in Railway; a timetable already published stays published; the `runs` folder on the volume is no longer written and can be left.

- [ ] **Step 3: Check**

Run: `grep -n -i -E "AI_PROVIDER|AI_API_KEY|SOLVE_SECONDS|Generate & publish|Adjust timetable|timetabler\.py|adjust\.py|runs\.py|ai\.py" README.md docs/DEPLOY.md` → only the lines of "Coming from an earlier version".
Run: `for f in ttgen/*.py; do cmp -s "$f" "skill/school-timetable-generator/scripts/$f" || echo "differs: $f"; done` → no output.
Run: `.venv/bin/python tests/smoke.py --full` → `6 checks passed`.

- [ ] **Step 4: Commit**

```bash
git add README.md docs/DEPLOY.md
git commit -m "Docs: the app builds the setup and publishes; generation happens outside"
```

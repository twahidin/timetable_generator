# Upload and edit, stage 1: two steps and the Publish rule Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Step 8 becomes "Upload and edit" (today's upload, check and editor); a new step 9, "Publish", shows the critical mistakes and every warning and refuses to publish while a critical mistake remains; printouts and the draft's download move to step 9; the answer "Leave it" goes.

**Architecture:** The check that already lists a timetable's warnings marks each one as critical or not (`ttgen/verify.py`), and the draft counts them and refuses to publish while one is there (`draft.py`). The page splits today's one step in two: the existing upload card, warnings list and Fix card stay on step 8 unchanged in how they work, and step 9 is a new read-only view of the same draft with the Publish button, the printouts and the published card. No board yet: that is stage 2.

**Tech Stack:** Python 3 (Flask app, `ttgen` package, plain-assert test scripts), vanilla JS in the browser (no build step), Node for the page modules' tests.

**Spec:** `docs/superpowers/specs/2026-11-16-upload-and-edit-design.md` ("Step 9. Publish", "Critical mistakes", "Across both steps", stage 1 of "Suggested order of building"), and the design it reworks, `docs/superpowers/specs/2026-11-10-return-trip-design.md`. Branch `upload-and-edit`, from `main` at 49033b1.

## Global Constraints

- **What is critical** (the design's list, as far as stage 1 can know it): a lesson with no teacher; a teacher in two lessons at once; a class clash as the check finds it today (a whole-class lesson at the same time as another lesson of that class); a room holding more lessons at once than the setup says it takes; a lesson in a break, in its class's recess, outside its level's day or past the day's "Lessons end by". "A lesson not placed" arrives with stage 3 and is not in this stage.
- **Two bands, or two groups, of one class at the same time are not a mistake** and are never counted as a clash.
- **Everything else is a warning** and never stops publishing: a difference from step 5, a rule broken (Must or Prefer), a room's rain use, a student in two lessons, periods timetabled against periods planned, a rule in words, a choice used.
- **Publish refuses only for a critical mistake.** The server refuses, not only the page. With none, publishing works as today, after the same confirmation, with every open warning shown.
- **"Leave it" goes.** The answers that stay are "update step 5" and, for a rule in words to look at again, "Still met".
- **Nothing is lost.** A draft from before this stage (with fixes, with "left" decisions) opens with its fixes kept; its "left" warnings are simply open again. A timetable published before this stage still shows on the Published card. The agent's file is kept as it came.
- **The editor is not changed.** The upload, the check, the warnings list's "Fix the timetable" and "Update step 5", the Fix card, the helper, the typed request and Undo work on step 8 exactly as they do today.
- **Steps.** The list reads "7 Download", "8 Upload and edit", "9 Publish", "Students". Both new steps are for the committee only: hidden from department heads, and their routes refuse a head, as today's are.
- `ttgen/` and `skill/school-timetable-generator/scripts/ttgen/` stay byte-identical. The skill's version becomes `2026-11.6` everywhere it is named (`ttgen/spec.py` `SKILL_VERSION`, `SKILL.md`, `README.md`, the tests that pin it in `tests/test_parents.py` and `tests/test_rules.py`).
- Everything a person typed is drawn through `esc()`. Sentences are plain and short, with no em-dashes and no arrows.
- Do not edit the part of `render()` that restores the keyboard focus, nor `teacherOptions` and the lessons table: other unmerged branches (`tab-keeps-place`, `step5-table-quick`) change them.
- **The school's size.** A returned timetable has about 1,950 lesson rows. On the school's file of 10 November the new rule finds 99 critical mistakes (31 teachers in two places, one more than the old list's limit of 30 showed, and 68 lessons in a break or outside the day) and 46 warnings; on its newest file it finds none critical and 198 warnings, 188 of them differences from step 5. The lists must open and stay usable at those sizes.
- Tests, samples and documents use made-up names only. The school is "CTSS" or "the school". A run on the real files reports counts only.
- Browser checks run on a scratch server with a scratch `DATA_DIR` and the README's example codes, never the repository's `data/`. No test or check calls a model API.
- `tests/test_helper.py --full` fails about one run in three on `main` (fixed on the unmerged branch `helper-full-flake`). That one failure is not this branch's.
- Commits end with `Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>`. Nothing is pushed.

## Decisions this plan makes (to be checked on reading)

1. **The list's limit of 30 goes for the critical kinds.** Today the check shows at most 30 teacher clashes, 30 class clashes and 30 room lines. A count that stops at 30 would tell the lead there are 30 mistakes when there are more, and fixing one would not lower it. All are listed and counted.
2. **A lesson with no teacher is a new line of the check**, so the outside agent's own check reports it too.
3. **A lesson with no room is not listed in this stage.** The design makes it a warning with its own counter; the counter is stage 3's.
4. **A lesson past "Lessons end by"** counts as outside the day, so it is critical.
5. **The published record keeps its field name `left`** for the sentences of the warnings that were open at publishing, so the Published card reads old and new records alike. Its sentence becomes "N warnings were open when it was published".
6. **Step 9's Make printouts makes them from the draft**, with the changes made in the app, not from files chosen again. The old route that made printouts from two uploaded files stays on the server for now and no page control uses it.
7. **Step 9 is read-only.** Its lists have no "Fix the timetable" or "Update step 5" buttons; each critical mistake has "Show on step 8", which goes there and opens the Fix card on it as "Fix the timetable" does today.
8. **The Publish button is disabled while a critical mistake remains**, with the reason in words above it; the server refuses as well.
9. **The filter on step 8's list** is "Open" and "All" ("Left for now" goes with the answer).
10. **The skill's version rises to 2026-11.6**, because the check in `ttgen` changes and `SKILL.md` names the steps.

## Review Focus

1. **A draft from before.** Decisions holding "left", fixes made, a file uploaded last week: the draft opens, the fixes are there, the "left" warnings are open again, and nothing asks about it. Pinned in Task 2 (`a_draft_from_before_opens_and_its_left_warnings_are_open_again`).
2. **More than 30 of one critical kind.** Every one is listed and counted, and fixing one lowers the count by one. Pinned in Task 1 (`every_teacher_clash_is_listed_past_thirty`).
3. **A critical mistake that appears after the page last looked** (another committee member's change, or a change on step 5): the click on Publish is refused by the server in words, and the page shows the mistake. Pinned in Task 2 (`publish_is_refused_while_a_critical_mistake_remains`) and checked in a browser in Task 4.
4. **Two bands of one class at the same time, and a band lesson with one group lacking a teacher.** The first is not counted at all; the second is one critical mistake naming that group. Pinned in Task 1 (`two_bands_of_one_class_at_once_are_not_a_mistake`, `a_lesson_with_no_teacher_is_critical`).
5. **A timetable published before this stage**, whose record has no count of critical mistakes and a list of "left" warnings: the Published card still reads right. Checked in a browser in Task 4.

---

### Task 1: What is critical

**Files:**
- Modify: `ttgen/verify.py`, `ttgen/export.py` (`check_model`), `ttgen/spec.py` (`SKILL_VERSION`), and the same three under `skill/school-timetable-generator/scripts/ttgen/`
- Modify: `skill/school-timetable-generator/SKILL.md`, `README.md` (the version line)
- Test: `tests/test_verify.py`, `tests/test_parents.py` and `tests/test_rules.py` (the version)

**Interfaces:**
- Produces: every warning from `verify.warnings(m)` carries `crit`: `""` for a warning, else one of `"teacher"`, `"class"`, `"room"`, `"break"`, `"noteacher"`. `verify.warning(...)` takes `crit=""`.
- Produces: `verify.crit_of(text) -> str` for a line of `check_model`'s problems: `"teacher"` when it starts `Teacher double-booked:`; `"room"` when it starts `Room over capacity:`; `"class"` when it starts `Class clash:`; `"break"` when it holds ` sits in a break or outside the day on `, ` sits in a class's recess on `, or ends `(Settings: Lessons end by).`; else `""`.
- Produces: one clash warning for each lesson row with no teacher: key `clash:noteacher:{id}:{group}`, text `No teacher: {what} on {day} period {p}.` (`{what}` as `verify._what` words a row), `crit="noteacher"`, `where` its first class, so "Fix the timetable" opens that class's week.
- Changes: `check_model` lists every teacher clash, every room line and every class clash (the three `[:30]` limits go; the rain-room limits stay).
- Produces: `spec.SKILL_VERSION == "2026-11.6"`.

- [ ] **Step 1: Write the failing tests** in `tests/test_verify.py` (its helpers `run`, `rule`, `primary`; a lesson is the tuple `(d, p, n, classes, subject, group, teachers, room)` those tests already use)

```python
@t
def what_is_critical_and_what_is_not():
    C = verify.crit_of
    assert C("Teacher double-booked: Tan Wei Ming on Odd Mon 8.00-8.40 (periods 1-2).") == "teacher"
    assert C("Class clash: 1A on Odd Mon period 3 (8.40).") == "class" and C("Room over capacity: Lab 1 on Odd Tue period 4 (9.00) (holds 1 at once).") == "room"
    assert C("Art Entire Class sits in a break or outside the day on Odd Mon period 5 (9.20).") == "break"
    assert C("PE Entire Class sits in a class's recess on Odd Mon period 5 (9.20).") == "break"
    assert C("Mathematics G3 1EMP ends after 1.00 on Odd Fri period 16 (1.00) (Settings: Lessons end by).") == "break"
    for text in ("Rain room in use: B4-1 on Odd Mon period 3 (8.40) is the home room of a class at PE, but a lesson is in it.",
                 "3 students have two lessons at the same time, e.g. S1 A.", "group 1EMP: 4 periods timetabled, 6 planned.", ""):
        assert C(text) == "", text

@t
def a_teacher_in_two_places_is_critical_and_a_rule_is_not():
    sp = primary(); a, b = sp["classes"][0]["class"], sp["classes"][1]["class"]; t = sp["teachers"][0]["name"]
    (rule_ws, nc), m = run(sp, [rule("Teacher", t, "Not available", 0, 1)], [(0, 1, 1, [a], "English", "Entire Class", [t], ""), (0, 1, 1, [b], "English", "Entire Class", [t], "")])
    crit = [w for w in verify.clashes(m) if w["crit"]]
    assert [w["crit"] for w in crit] == ["teacher"] and crit[0]["kind"] == "clash" and crit[0]["text"].startswith("Teacher double-booked: " + t)
    assert rule_ws and all(w["crit"] == "" for w in rule_ws)                # a broken Must rule is a warning

@t
def a_lesson_with_no_teacher_is_critical():
    # a band lesson of two groups, the second with no teacher: one critical mistake, naming that group
    ...   # assert exactly one warning with crit == "noteacher", key "clash:noteacher:{id}:{second group}", text starting "No teacher: ", where == dict(cls=first class of that row)

@t
def two_bands_of_one_class_at_once_are_not_a_mistake():
    # two group lessons (two different bands) of one class in the same period, different teachers and rooms: no warning with crit, and no "Class clash" line
    ...

@t
def every_teacher_clash_is_listed_past_thirty():
    # one teacher on two classes' lessons in each of 35 different periods across the days: 35 warnings with crit == "teacher"; take one of the two lessons away from one period: 34
    ...
```

`run` returns the rule warnings and the model; the clash warnings come from `verify.clashes(m)` (if the helper's model carries no `checks`, give it them with `export.check_model(m)`, as `model_from_files` does). Write the three bodies marked `...` out in full on made-up rows, with exact counts and keys. In `tests/test_parents.py` rename the version test to `the_skill_version_is_2026_11_6` with its three strings; in `tests/test_rules.py` the version assertion becomes `"2026-11.6"`.

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/bin/python tests/test_verify.py; .venv/bin/python tests/test_parents.py; .venv/bin/python tests/test_rules.py`
Expected: `test_verify.py` fails at `verify.crit_of` (no such function); the other two fail on the version.

- [ ] **Step 3: Change `ttgen`**

`verify.py`: `crit_of`, the `crit` field on `warning`, `clashes` setting it from each line and adding the no-teacher warnings. `export.py` `check_model`: the three limits go. `spec.py`: the version. Copy the three files to `skill/school-timetable-generator/scripts/ttgen/`.

- [ ] **Step 4: Change `SKILL.md` and `README.md`**

`SKILL.md`: the version line; where it tells the school how to publish ("on step 8, **Publish**, upload…") it says: "on step 8, **Upload and edit**, upload the .sqlite (or the timetable workbook with the setup workbook), look at what the check found, then publish on step 9, **Publish**. The app will not publish while a critical mistake remains: a lesson with no teacher, a teacher or a whole class in two lessons at once, a room holding more lessons than it takes, or a lesson in a break or outside the day. Run `python -m ttgen check-timetable` before handing back and settle these first."; where it says the app shows the rule report "on Publish" it says "on step 8". `README.md`: the version line only (Task 4 does the rest).

- [ ] **Step 5: Run the suites**

Run: `.venv/bin/python tests/test_verify.py && .venv/bin/python tests/test_parents.py && .venv/bin/python tests/test_rules.py && .venv/bin/python tests/test_fixes.py && .venv/bin/python tests/test_helper.py && .venv/bin/python tests/test_typed.py && .venv/bin/python tests/test_teachers.py && .venv/bin/python tests/smoke.py && diff -rq ttgen skill/school-timetable-generator/scripts/ttgen`
Expected: every script prints its pass line; `diff` shows no differing file (an untracked `__pycache__` in one folder is not a difference). A test that pinned a list of exactly 30 lines is rewritten to the new rule, never deleted, and named in the report.

- [ ] **Step 6: Commit** `feat(check): each warning says whether it is critical; a lesson with no teacher is listed; every clash is listed; skill 2026-11.6`

---

### Task 2: The draft counts critical mistakes, and Publish refuses

**Files:**
- Modify: `draft.py` (`ANSWERS`, `save`, `_finish`, `decide`, `publish`; new `Critical`, `critical_text`, `printouts`), `app.py` (the publish route; a new printouts route)
- Test: `tests/smoke.py`

**Interfaces:**
- Consumes: `crit` on each warning (Task 1).
- Changes: `draft.ANSWERS == ("step5", "open", "met")`. `draft.decide(key, "left")` raises `ValueError("Choose what to do with the warning.")`.
- Changes: `draft.info()` returns `critical` (the number of warnings with `crit`) and `open` (the number with no decision), and no `left`. A stored decision whose answer is `"left"` is dropped the next time the draft is read; `save()` carries no decision over to a new upload.
- Produces: `draft.critical_text(n) -> str`: `"1 critical mistake must be settled on step 8 before the timetable can be published."` for 1, `"{n} critical mistakes must be settled on step 8 before the timetable can be published."` for more.
- Produces: `class draft.Critical(Exception)` with `.count`; `draft.publish()` raises it when `critical > 0`, before anything is written. The published record's `left` is the sentences of every warning open at publishing; `open` is their count.
- Produces: `draft.printouts(out_dir, individual) -> (model, base_name)`: the printouts of the draft with its fixes applied, written under `out_dir` by `ttgen.export.export_all`, from a model built for this call (never the shared cached one).
- Routes: `POST /api/draft/publish` answers 409 `{"error": critical_text(n), "critical": n}` for `Critical`. `POST /api/draft/printouts` (form field `single`, "1" or "0") answers a zip exactly as `/api/export` does, with the same `X-Checks` header; 404 `{"error": "There is no draft."}` with no draft; 409 with no setup; committee only.

- [ ] **Step 1: Write the failing tests** in `tests/smoke.py` (named in the file's own style, `test_…`, and added wherever it lists or runs its tests; pattern-match its draft tests about lines 320 to 400 and the publish test about line 929)

- `test_the_draft_counts_critical_mistakes`: upload a timetable with one teacher on two classes at once: `j["critical"] == 1`, the warning has `crit == "teacher"`, `"left" not in j`.
- `test_publish_is_refused_while_a_critical_mistake_remains`: with that draft, `POST /api/draft/publish` is 409, its `error` is `draft.critical_text(1)` and `critical` is 1, and the published timetable is what it was before (or still none); after a fix that settles it (a move through `/api/draft/fix`, as the fix tests do), publishing answers 200.
- `test_leave_it_is_gone`: `POST /api/draft/decide` with `"answer": "left"` is 400 with "Choose what to do with the warning."; "step5" and "open" still work as today's tests show.
- `test_a_draft_from_before_opens_and_its_left_warnings_are_open_again`: write `decisions.json` with one `"left"` and one `"step5"` decision and a fix in `meta.json`, as an older version would have left them: `GET /api/draft` is 200, the fix is in `fixes`, the warning with the left decision has no decision and counts in `open`, the step5 one is kept, and `decisions.json` no longer holds "left".
- `test_printouts_come_from_the_draft_with_its_fixes`: after one fix, `POST /api/draft/printouts` is a zip whose timetable database (read back with `ttgen.export.model_from_files`) has the lesson where the fix put it, not where the file had it; with no draft it is 404; a head is refused.
- `test_publishing_records_the_open_warnings`: publish a draft with warnings and no critical mistake: the published record's `open` equals the draft's `open` and `left` is the list of those warnings' sentences.
- Change every existing test that uses the answer "left", `j["left"]` or `test_a_new_upload_keeps_left_decisions` to the new rule (the last becomes: a new upload starts with no decisions). Name each in the report.

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/bin/python tests/smoke.py`
Expected: the new tests fail (`critical` missing; publish answers 200; "left" accepted; no printouts route).

- [ ] **Step 3: Change `draft.py` and `app.py`** as in Interfaces. `publish()` judges and writes under the lock it holds today, so a critical mistake cannot arrive between the judgement and the write.

- [ ] **Step 4: Run the suites**

Run: `.venv/bin/python tests/smoke.py && .venv/bin/python tests/test_fixes.py && .venv/bin/python tests/test_helper.py && .venv/bin/python tests/test_typed.py && .venv/bin/python tests/test_verify.py`
Expected: every script passes.

- [ ] **Step 5: Commit** `feat(draft): critical mistakes are counted and stop publishing; Leave it goes; printouts of the draft`

---

### Task 3: The page's words and counts for the draft

**Files:**
- Modify: `static/draft.js`
- Test: `tests/draft.test.js`

**Interfaces:**
- Changes: `Draft.isOpen(w)`: true when the warning has no decision (an old `"left"` counts as none). `Draft.keep(w, filter)`: `filter` is `"open"` or `"all"`. `Draft.answerText` has no "Left for now".
- Changes: `Draft.counts(ws) -> { open, critical, step5, met, must, prefer }` (no `left`; `critical` is the number with `crit`).
- Produces: `Draft.critical(ws) -> [warning]`: the warnings with `crit`, in their order.
- Produces: `Draft.gateText(n) -> ""` for 0, `"1 critical mistake to settle on step 8 first."` for 1, `"{n} critical mistakes to settle on step 8 first."` for more.
- Produces: `Draft.critWord(crit) -> ` `"Teacher in two places"`, `"Class clash"`, `"Room used twice"`, `"In a break or outside the day"`, `"No teacher"` for the five values, `""` otherwise.

- [ ] **Step 1: Change the tests** in `tests/draft.test.js`: the fixture's warnings gain `crit` on two of them; `counts` expects the new shape; `isOpen` of a `"left"` decision is true; `group(ws, "left")` goes; add tests for `critical`, `gateText` (0, 1, 3) and `critWord` (the five values and an unknown one). Run `node tests/draft.test.js`: the changed tests fail.

- [ ] **Step 2: Change `static/draft.js`.** Run `node tests/draft.test.js && node tests/grid.test.js`: all pass.

- [ ] **Step 3: Commit** `feat(draft): the page's counts know critical from open; Left for now goes`

---

### Task 4: Step 8 "Upload and edit" and step 9 "Publish"

**Files:**
- Modify: `static/app.js` (`STEPS`, `HEAD_HIDDEN`, `VIEWS.publish`, a new `VIEWS.edit`, `exportCard`, `draftHTML`, `fixesHTML`, `paintPublished`, `makePrintouts`, `publishDraft`, `loadDraft`, the click handlers), `static/style.css` only if a new rule is needed (new class names start with `pb`), `README.md`, `docs/DEPLOY.md`

**Interfaces:**
- Consumes: `critical`, `open` and `crit` from the server (Tasks 1 and 2); `Draft.counts`, `critical`, `gateText`, `critWord` (Task 3); `POST /api/draft/printouts`; the 409 of `POST /api/draft/publish`.
- Produces: step ids `"edit"` ("8 Upload and edit") and `"publish"` ("9 Publish"). `"edit"` joins `HEAD_HIDDEN`. Wherever the page sends someone to the old Publish step to work on the draft (a Things to fix link, the old steps mapped onto "publish" near the top of the file), it now sends them to `"edit"`.

- [ ] **Step 1: Step 8, Upload and edit**

`VIEWS.edit()`: the heading card "Step 8 · Upload and edit" with the lead "Bring back the timetable the AI agent made and check it. Change it here until it is right, then publish it on step 9. Nothing is visible to teachers or students until you publish."; then today's upload card and draft area with these changes only:

- The card is headed "Upload the timetable". Its second paragraph becomes: "**Check** keeps the file as a draft, checks it against the setup and lists what it found. Fix it here, then go to step 9 to publish." The tick box for separate PDFs and the "Make printouts (.zip)" button leave this card.
- The summary line reads "`{c} critical · {n} warnings open · {s} settled on step 5`", with the critical part in the page's warning colour when it is not 0.
- A warning that is critical shows `Draft.critWord(w.crit)` as a mark before its first line.
- "Leave it" and its "Reopen" go; "Reopen" stays for "Still met". The filter is "Open" and "All".
- The Publish button and the line "you can still publish" go. In their place: "`{gate}` Publish is on step 9." with a button "Go to step 9", where `{gate}` is `Draft.gateText(critical)`.
- The link "Download the draft" leaves the Fixes block (it is on step 9).
- In a practice copy the step says "Uploading a timetable is off in a practice copy."

Everything else on the step (the Fix card, the helper, the typed request, Undo, the notes, the rule report, the choices used) is today's code, moved, not rewritten.

- [ ] **Step 2: Step 9, Publish**

`VIEWS.publish()`: the heading card "Step 9 · Publish" with the lead "Publish the timetable for teachers and students. Every warning is shown here. A critical mistake has to be settled on step 8 first."; then:

- **With no draft:** "Nothing to publish yet. Upload a timetable on step 8." and a button "Go to step 8".
- **The timetable to publish** (a card): the school and term, the counts line, the configuration line and the other-school warning as step 8 shows them; then
  - "Critical mistakes · {c}": each with its `critWord`, its sentence and a button "Show on step 8", which goes to step 8 and opens the Fix card on that warning exactly as "Fix the timetable" does there. With none: "Nothing critical." in the page's ok style.
  - "Warnings · {n}": every open warning that is not critical, grouped as step 8 groups them, each kind folded shut when it holds more than 20, with no buttons.
  - "Changes made in the app · {k}": the list of fixes, without Undo.
  - When `critical > 0`: `Draft.gateText(critical)` in the page's issue style, and the button "Publish this timetable" disabled with that sentence as its title. Otherwise the line "Publishing replaces the timetable published {when}." (or "Nothing is published yet.") and the button enabled. A click asks the same confirmation as today.
  - When the server refuses with 409 (a critical mistake arrived meanwhile): the sentence it sends is shown as a toast and the draft is fetched again, so the list shows the mistake.
- **Printouts** (a card): the tick box "Also a separate PDF for every class, teacher, room and student", the button "Make printouts (.zip)" (it posts to `/api/draft/printouts`, with today's waiting sentence and download), and the link "Download the draft (.sqlite)". With no draft the card is not drawn.
- **Published now**: today's card (`paintPublished`), unchanged but for its sentence about open warnings, which becomes "{n} warning(s) were open when it was published" over the same list; a record with no such figures reads as it does today.
- In a practice copy: "Publishing is off in a practice copy.", as today.

- [ ] **Step 3: The words elsewhere**

`README.md`: the step list, the description of the return trip (upload and check on step 8, publish on step 9, what stops publishing, where the printouts are), and any sentence that says "you can still publish" or names "Leave it". `docs/DEPLOY.md`: the lines that name step 8 and Publish (the first-run list, the heads' hidden steps, the typed request box on step 8).

- [ ] **Step 4: Check it**

Run: `node --check static/app.js && for f in tests/*.test.js; do node "$f" || break; done && .venv/bin/python tests/smoke.py && grep -n "Leave it\|Left for now\|you can still publish\|Step 8 · Publish" static/app.js static/draft.js README.md docs/DEPLOY.md`
Expected: the checks pass and the `grep` prints nothing.

In a browser, on a scratch server (the controller says how it is reached) holding the made-up secondary sample as the school's setup, as the committee. A sample timetable to upload is made the way `tests/smoke.py` makes one for its draft tests; the controller provides the file or the way to send it.

1. The list on the left reads 7 Download, 8 Upload and edit, 9 Publish, Students. Step 8 has the upload card and no Publish button; step 9 with no draft says "Nothing to publish yet." and its button goes to step 8.
2. With a clean timetable as the draft: step 8's summary says 0 critical; step 9 shows "Nothing critical.", the warnings, and an enabled Publish button; publishing works and the Published card shows it.
3. With a timetable where one teacher is on two classes at once: step 8 marks that warning "Teacher in two places" and says "1 critical mistake to settle on step 8 first."; step 9 lists it, the Publish button is disabled with the sentence; "Show on step 8" opens the Fix card on it; after the fix, step 9's button is enabled and publishing works.
4. Publish refused by the server: with step 9 open and nothing critical, upload the critical file from a second tab (it replaces the draft); click Publish in the first tab: the refusal's sentence shows and the list now shows the mistake.
5. "Leave it" is nowhere; "Update step 5" and "Fix the timetable" work on step 8 as before; Undo works.
6. Printouts on step 9 download a zip; "Download the draft" downloads the file.
7. A department head (sign out, sign in with the heads' example code, then back): neither step 8 nor step 9 is in the list.
8. A timetable published before this change (the scratch data's published record edited to have no `open` and an old `left` list, or one published by `main`'s code): the Published card reads without an error.
9. The console has no error.

- [ ] **Step 5: Commit** `feat(publish): step 8 is Upload and edit, step 9 is Publish and refuses for a critical mistake`

---

## The whole-branch review

On the most capable model, with this plan's Review Focus and Decisions, and these checks on top of the diff.

**The suites.** Every `node tests/*.test.js`; `test_teachers`, `test_venues`, `test_typed`, `test_helper`, `test_fixes`, `test_verify`, `test_rules`, `test_choices`, `test_parents`, `test_sync`, `smoke`; `node --check static/app.js`; `diff -rq ttgen skill/school-timetable-generator/scripts/ttgen` shows no differing file.

**The school's real files (counts only; every derived file deleted afterwards).** For the timetable of 10 November and for the newest one, against the newest setup workbook: the number of critical mistakes by kind and of warnings by kind, on `main` and on the branch (the plan's count before building: 99 critical on the first, none on the second; no warning of `main` is missing on the branch); that no two bands of one class are counted; the time to build the draft's lists. A draft made by `main`'s code from the real file, with one fix and one "left" decision, opens on the branch with both the fix and the warning there.

**In a browser, on made-up data:** Task 4's list once more on the finished branch, plus steps 1 to 7 still open; the page at 1280 and at about 1000 pixels wide; step 9 with 100 critical mistakes and 200 warnings (a made-up timetable built for it) opens and scrolls without a pause.

**Names.** No real name and no full school name in the diff or the commit messages.

Then the notes file `docs/superpowers/plans/2026-11-16-upload-and-edit-stage-1-notes.md`.

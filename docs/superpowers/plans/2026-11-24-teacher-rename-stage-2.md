# Teacher rename, stage 2: the question on step 9, and the account. Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Before publishing, step 9 asks for each renamed teacher who has an account or a Telegram link whether it is the same person or a different person, and the publish then moves or removes the account and the link.

**Architecture:** The server works out the pairs (old name, new name) from the published timetable's teacher rows and the `earlier_names` of the setup about to be published (`accounts/renames.py`, pure). `POST /api/draft/publish` takes the choices, refuses when one is missing or needs an admin, publishes, then joins or removes the account (`accounts/people.py`, through its one write path) and moves or forgets the Telegram link (`relief/links.py`). The page draws the card from a pure module (`static/renames.js`).

**Tech Stack:** Python 3 / Flask (tests are plain scripts run with `../timetable_generator/.venv/bin/python tests/x.py`), vanilla JS (`node tests/x.test.js`).

**Spec:** `docs/superpowers/specs/2026-11-24-teacher-rename-design.md`, Part 3. Stage 1 (Parts 1 and 2) is merged. Parts 4 and 5 (reliefs, exam duties, the hold on relief and exams during a publish, the "unfinished rename" retry) are stage 3: build nothing of them, and do not mention reliefs or exam duties on the page.

## Global Constraints

- The repository is public: made-up names only in code, tests and docs ("Mdm Lee", "New Teacher 3"); the school is "CTSS" only.
- The accounts file is written only through `people.update(fn)`; the Telegram tables only inside `tgdb.db()`.
- An old name can only be a teacher row's name on the timetable published now. `earlier_names` is setup data any committee member can write: it is never trusted beyond that test.
- Account details (role, committees, username, a note, switched off) are shown to admins only. Anyone else who may publish sees "has an account" and "Telegram", nothing more.
- A publish that must carry or remove an account can only be made by an admin (the right `admin`). There is no second place to decide and nothing waits afterwards.
- A different person never gets anything of the old account. Same person is never assumed.
- No test may call the real Telegram API or a model API. Never import `app` without `DATA_DIR` set to a scratch folder.
- Never run `git stash`, `git stash pop` or `git checkout -- <file>`. Never use `pkill`/`killall`; stop only processes you started, by PID. Never read or print `.claude/launch.json`. Do not push.
- Commits end with the line `Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>`.
- `static/app.js` keeps many statements on very long lines: edit by exact string replacement, never by slicing between markers; run `node --check static/app.js` after every edit; search it with `grep -F` or Python.

## Review Focus

1. The person publishing is the one renamed: after "same person" they must still be signed in, under the new name, and must not be able to pick "a different person" for themselves. Pinned in Task 3.
2. The old name is the last admin who can sign in: its account must never be removed; the line says why and Publish stays off for that choice. Pinned in Task 1 (the route cannot reach it: see Task 3, case 8).
3. `earlier_names` names someone who was only added by name (a school leader, not a teacher row of the published timetable): no pair, whatever the setup says. Pinned in Task 1.
4. A second press of Publish, or a publish from a second tab, after the pairs were settled: no pair is left, nothing is applied twice, and a choice sent for a pair that no longer exists is ignored, not an error. Pinned in Task 3.
5. A committee member who is not an admin (or the shared committee code) with a pair that has an account: Publish is refused by the server too, with the sentence, and nothing is published. Pinned in Task 3.

---

### Task 1: The pairs, and the account's join and removal

**Files:**
- Create: `accounts/renames.py`
- Modify: `accounts/people.py` (add `join`, `drop`)
- Test: `tests/test_renames.py` (new; begin it like `tests/test_admin.py`: a temp `DATA_DIR` and the environment set before any import of `store`)

**Interfaces:**
- Consumes: `people.record(data, name)`, `people.LABELS`, `people.usable_admins(data)`, `people.HEADS`.
- Produces:
  - `renames.kept(rec, linked) -> list[str]`: what a cleaned record has that is worth keeping, as words in this order, each only when it holds: the role's label (`LABELS[group]`, when `group` is not None), `"Timetable committee"`, `"Relief team"`, `"Exams and events"` (when `extras["exams"]` is not None), `"Admin"`, `"username"`, `"password"`, `"Google sign-in"`, `"a note"` (a non-blank note), `"switched off"`, `"added by name"`, and last `"Telegram"` when `linked`. Departments alone are not a word (they belong to the role). Sign-ins alone give `[]`.
  - `renames.pairs(old_names, spec, data, linked, me=None) -> list[dict]`. `old_names`: the set of teacher-row names of the timetable published now. `linked`: the set of names that have a Telegram link. One dict per pair, in the setup's teacher order: `old`, `new`, `has` (the `kept` words of the old name), `account` (any word but "Telegram"), `telegram`, `joins` (False when the new name's record has a username, a password or a Google sign-in), `no_remove` (None, or the sentence why the old account cannot be removed: `"You cannot remove your own account."` when `old == me`; `people-style "{} is the last admin: make another admin first."` with the old name when the old name is a usable admin and no other usable admin exists). A pair is made for a teacher row of `spec` with a non-blank string name `new`, for each string `e` in its `earlier_names` list such that: `e` is in `old_names`; `e` is not the name of any teacher row of `spec`; `kept` of `e` is not empty. An old name makes at most one pair (the first row in order that claims it).
  - `renames.refusal(pairs, choices, admin) -> str | None`: why a publish with these choices (`{old: "same" | "different"}`) is refused, the first that applies, else None: a pair with `account` when `admin` is False: `"An admin has to publish this one: {new}'s account must follow or be removed."`; a pair with no valid choice: `"Choose first for {old}, now {new}: the same person, or a different person."`; a choice that would remove an account that cannot be removed (`"different"` with `account`, or `"same"` with `account` and not `joins`, when `no_remove` is set): that `no_remove` sentence. Choices for names that make no pair are ignored.
  - `people.join(d, old, new) -> list[dict]`: inside a `people.update`. The new name's record takes from the old name's whatever the old one has set: `group` (and then `depts` too), `username`, `pw` (and then `must_change` too), `google`, a non-blank `note`, `off` when True; `extras`: `timetable`, `relief`, `admin` are True when either has it, `exams` is the later date of the two (None when neither); `code_n` the larger. `added` and `signins` stay the new name's. `n` becomes `max(old n, new n) + 1`. The old key is popped and `d["removed"][old] = old n + 1`. Returns the changes for the History: one `dict(name=new, field=…, was=…, now=…)` per field that changed on the new record (never a password hash: for `pw` use `was`/`now` of `"set"` or `None`). Raises `ValueError` when the new name's record has a username, a password or a Google sign-in (the caller must not ask).
  - `people.drop(d, old) -> dict`: inside a `people.update`. Pops the old record, sets `d["removed"][old] = old n + 1`, and returns what it had as `app.py`'s `admin_remove` records it: `dict(role=<label or None>, timetable, relief, exams, admin, depts, username, note, off)`.

- [ ] **Step 1: Write the failing tests** in `tests/test_renames.py`. Build records with `people.update` on the scratch accounts file. The cases, each an assert on exact values:
  1. `kept`: a record with group `"hod"`, depts `["MA"]`, extras relief True, a username, a password, a note → `["HOD", "Relief team", "username", "password", "a note"]`; with `linked=True` it ends with `"Telegram"`; the defaults with three sign-ins → `[]`; only `linked` → `["Telegram"]`.
  2. `pairs`, the plain case: published names `{"New Teacher 3", "Arjun Nair"}`; setup rows `Mdm Lee` (earlier `["New Teacher 3"]`) and `Arjun Nair`; `New Teacher 3` has group `"hod"` and a username → one pair `old="New Teacher 3"`, `new="Mdm Lee"`, `account=True`, `telegram=False`, `joins=True`, `no_remove=None`, `has=["HOD", "username"]`.
  3. No pair when: the old name has nothing to keep; the earlier name is not in the published names (Review Focus 3: give that name a record with Admin and a password, added by name, and assert no pair); the earlier name is still a teacher row of the setup; `earlier_names` is not a list or holds non-strings; the row has no name.
  4. Only a Telegram link: `account=False`, `telegram=True`, `has=["Telegram"]`.
  5. `joins=False` when the new name has a username, or a password, or a Google sign-in.
  6. `no_remove`: `"You cannot remove your own account."` when `me` is the old name; the last-admin sentence when the old name is the only usable admin (timetable and admin ticks, a username and a password), and None once a second usable admin exists.
  7. Two rows claiming one old name: one pair, for the first row.
  8. `refusal`: None when there are no pairs; the admin sentence for an account pair with `admin=False`, even when a choice is given; None for a Telegram-only pair with `admin=False` and a choice; the "Choose first…" sentence for a missing choice and for a choice of `"maybe"`; the `no_remove` sentence for `"different"` on such a pair and for `"same"` when `joins` is False; None for `"same"` when `joins` is True on that pair (nothing is removed from the person: the record moves); a choice for an unknown name is ignored.
  9. `join`: old has group `"hod"`, depts `["MA"]`, relief True, exams `"2026-12-31"`, username `"lee"`, a password hash, must_change True, note `"x"`, n 4; new has timetable True, exams `"2027-03-01"`, n 1, two sign-ins. After: new has group `"hod"`, depts `["MA"]`, timetable and relief True, exams `"2027-03-01"`, the username, the same hash, must_change True, note `"x"`, n 5, its own two sign-ins; the old key is gone; `removed[old] == 5`; `people.record(d, old)["n"] == 5` (a session made under the old name is never accepted again); the returned changes name every changed field and hold no hash. Old with nothing set but `off` → only `off` changes. `ValueError` when the new name has a username.
  10. `drop`: the record goes, `removed[old]` is its n + 1, and the returned dict has the nine keys.
- [ ] **Step 2: Run it and see it fail**

Run: `../timetable_generator/.venv/bin/python tests/test_renames.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'accounts.renames'`.

- [ ] **Step 3: Implement** `accounts/renames.py` (no imports beyond `accounts.people`; nothing in it writes) and `people.join`, `people.drop`.
- [ ] **Step 4: Run** `tests/test_renames.py`, `tests/test_accounts.py`, `tests/test_admin.py`. Expected: all pass.
- [ ] **Step 5: Commit**

```bash
git add accounts/renames.py accounts/people.py tests/test_renames.py
git commit -m "feat(accounts): the pairs of a renamed teacher, and an account joined or removed"
```

---

### Task 2: The Telegram link follows

**Files:**
- Modify: `relief/links.py` (add `move`)
- Test: `tests/test_renames.py` (it already has a scratch `DATA_DIR`; the Telegram tables are made on first use)

**Interfaces:**
- Consumes: `tgdb.db()`, the `links`, `codes`, `talks` and `state` tables, `links.BLOCKED`, `links.ALERT`, `links.forget(name)`.
- Produces: `links.move(old, new) -> str`, in one transaction:
  - `"none"`: the old name has no link (its unused link codes and its blocked note and alerts still go, as `forget` does).
  - `"kept"`: the new name already has a link: it keeps its own, and everything of the old name goes as `forget(old)` does.
  - `"moved"`: the old name's link row now has the new name (same chat, handle and time); the old name's `blocked:` note, if any, becomes the new name's unless the new name has one; the old name's link codes go; the old name's alerts (`alert:{old}:{date}`) go; an open talk in that chat stays.
  - `links.linked_names() -> set[str]`: every name that has a link, in one read (if a function giving that already exists in the file, use it and do not add this one; say so in the report).

- [ ] **Step 1: Write the failing tests**: one for each of the three answers, asserting the rows of `links`, `codes` and `state` after the call (use `links.link`, `links.new_code`, `links.note_blocked`, `links.note_alert` to set up, and read the tables with `tgdb.db(read=True)`); `move` twice in a row is harmless (the second answers `"none"`); a name with a colon in it does not delete another name's alerts.
- [ ] **Step 2: Run and see them fail** (`AttributeError: module 'relief.links' has no attribute 'move'`).
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `tests/test_renames.py` and `tests/test_relief_telegram.py`. Expected: all pass.
- [ ] **Step 5: Commit**

```bash
git add relief/links.py tests/test_renames.py
git commit -m "feat(relief): a Telegram link moves to a teacher's new name"
```

---

### Task 3: The publish asks, refuses and applies

**Files:**
- Modify: `app.py` (`draft_get`, `draft_publish`, the status route's `published` part), `store.py` (add `published_note`)
- Test: `tests/test_renames.py`

**Interfaces:**
- Consumes: Task 1's `renames.pairs`, `renames.refusal`, `people.join`, `people.drop`; Task 2's `links.move`, `links.linked_names`, `links.forget`; `app.py`'s `has("admin")`, `who()`, `by()`, `_account_entry`, `_update_as`, `people.readable`.
- Produces:
  - `store.published_note(key, value)`: writes one more key into the published timetable's `meta.json` under the store's lock and clears the cache; does nothing when nothing is published.
  - `GET /api/draft`: when there is a draft, the answer gains `renames`: the pairs for the setup as it is now against the timetable published now, each as `dict(old, new, has, account, telegram, joins, no_remove, needs_admin)`. For someone without the right `admin`, `has` is cut down to `["an account"]` (when `account`) plus `["Telegram"]` (when `telegram`), and `needs_admin` is True for a pair with `account`. An empty list when nothing is published, accounts are off (`accounts_on()` is False) or the accounts file cannot be read.
  - `POST /api/draft/publish`: reads an optional JSON body `{"renames": {old: "same" | "different"}}`. Before publishing it works the pairs out again; `renames.refusal(...)` answering a sentence gives `409` with `{"error": sentence, "renames": <the pairs as GET gives them>}` and nothing is published. After a publish that went through, for each pair whose new name is a person on the timetable just published, in order:
    - `"same"`: `links.move(old, new)`; then, when `account`: `people.join` if `joins`, else `people.drop` and `links.forget(old)` is not needed (the link was moved or kept).
    - `"different"`: `links.forget(old)`; then `people.drop` when `account`.
    - One History entry per account change: `_account_entry("rename", [old, new], changes, f"{old} is now {new}: their account followed")` for a join; `_account_entry("remove", [old], [dict(name=old, field="removed", was=<drop's dict>, now=None)], f"Removed {old}: {new} took over their timetable")` for a removal.
    - The person publishing, when they are the old name of a joined pair, stays signed in: the session's `who` becomes the new name and its `n` the new record's.
    - The answer gains `renamed`: one sentence per pair, and the same list is kept with `store.published_note("renamed", lines)` (an empty list when there was none, so an older list never lingers). The sentences: a join: `"{new} (was {old}): their account followed."`; plus `" Their Telegram link followed too."` when the link moved; a removal: `"{old}'s account is removed: {new} starts fresh."`; only a link moved: `"{new} (was {old}): their Telegram link followed."`; only a link forgotten: `"{old}'s Telegram link is removed: {new} starts fresh."`. Every sentence ends with `" They need a new code slip."`.
    - A failure in one pair's account or link step never undoes the publish and never stops the other pairs: it is logged, and that pair's sentence is `"{new} (was {old}): could not be finished. Tell whoever looks after the app."`.
  - The exams-to-relief sync that follows a publish runs after all of this, as today.
  - `GET /api/status`: `published.renamed` is the list kept in the meta (absent or `[]` when none).

- [ ] **Step 1: Write the failing tests** in `tests/test_renames.py`, with the Flask test client. Put a published timetable in place the way `tests/test_admin.py` does (`relief.people.fake_pub` written to `store.PUB`), save a setup through `PUT /api/setup`, and stand in for the slow publish by replacing `app.draft.publish` with a function that writes a new fake published timetable from the setup's teacher rows and returns `{"published": True}` (put the real one back in a `finally`). The cases:
  1. `GET /api/draft` as an admin (make one with `people.update`: timetable and admin ticks, a username, a password, signed in through the app's password sign-in as `tests/test_admin.py` does) lists the pair with the full `has`; as the shared committee code it lists `has == ["an account"]` and `needs_admin True`; with nothing published, `renames == []`.
  2. Publish as an admin with no body → `409`, the "Choose first…" sentence, `renames` in the answer, and the published timetable is unchanged (the stand-in was not called).
  3. Publish as the shared committee code with a choice → `409` with the admin sentence; nothing published (Review Focus 5). A pair with only a Telegram link and a choice → `200` for the shared committee code.
  4. Same person: the new name's record has the old role and username, the old key is gone, `removed[old]` is set, the link row carries the new name, the History has one `account` entry with `what == "rename"`, `renamed` in the answer and in `GET /api/status` is the join sentence with the Telegram part. Putting that History entry back is refused (use the route `tests/test_putback.py` uses).
  5. A different person: the old record is gone, the link is gone, the new name's record is the defaults, one `account` entry with `what == "remove"`, the removal sentence.
  6. Same person when the new name already has a username: the old account is removed, the new one is untouched, the link moves only if the new name had none.
  7. The publisher is the renamed person (Review Focus 1): sign in by password as the old name (an admin), choose same person → `200`; the next request with the same client is still signed in, `GET /api/status` or `/api/admin/people` answers `200`, and the session's person is the new name. Choosing a different person for oneself → `409` with `"You cannot remove your own account."`.
  8. The last admin (Review Focus 2) cannot be reached through the route: whoever publishes an account pair is an admin who can sign in, so another usable admin always exists unless the publisher is the old name, and then the "own account" sentence answers first. Task 1's unit test pins the sentence; here, assert only that the route passes `me` (the publisher's name) to `renames.pairs` by checking case 7's refusal.
  9. A second publish with the same body after the pairs were settled (Review Focus 4) → `200`, `renamed == []`, the accounts file unchanged, no new History entry.
  10. A pair whose new name is not on the timetable just published (make the stand-in publish a timetable without it) is skipped: nothing of its account or link changes.
  11. The stand-in raising `draft.Critical` → `409` as today and no account change.
- [ ] **Step 2: Run and see them fail.**
- [ ] **Step 3: Implement.** Keep the route readable: put the working-out and the applying in two helpers in `app.py` beside `admin_remove` (`_rename_pairs()` and `_apply_renames(pairs, choices, pub_after)`), and have `draft_publish` call them.
- [ ] **Step 4: Run** `tests/test_renames.py`, `tests/test_admin.py`, `tests/test_accounts.py`, `tests/test_putback.py`, `tests/test_history.py`, `tests/test_routes.py`, `tests/test_board.py`, `tests/smoke.py`. Expected: all pass.
- [ ] **Step 5: Commit**

```bash
git add app.py store.py tests/test_renames.py
git commit -m "feat(step 9): a publish asks about each renamed teacher and moves or removes their account"
```

---

### Task 4: Step 9's card

**Files:**
- Create: `static/renames.js`, `tests/renames.test.js`
- Modify: `static/index.html` (one `<script src>` line beside `teacherview.js`'s), `static/app.js` (step 9's publish card, `publishDraft`, the "Published now" card)

**Interfaces:**
- Consumes: `S.draft.renames` (Task 3's list), the publish answer's `renamed` and `renames`, the status's `published.renamed`.
- Produces (on `Renames`, a plain module like `TeacherView`, exported for Node):
  - `gate(pairs, picks) -> string`: `""` when Publish may go; else the first that applies: for a pair with `needs_admin`: `"An admin has to publish this one: {new}'s account must follow or be removed."`; for a pair with no pick: `"Choose for each teacher with a new name first."`.
  - `offers(pair) -> { same: boolean, different: boolean, note: string }`: `different` is false when the pair has `account` and `no_remove`; `same` is false when the pair has `account`, not `joins`, and `no_remove`; `note` is `no_remove` when either is false, else `"{new} already has their own account: {old}'s account is removed either way."` when `account` and not `joins`, else `""`.
  - `card(pairs, picks, esc) -> string`: `""` for no pairs; else a card headed `New names since the last publish`, one line per pair: `"{old} is now {new}."`, then `has` joined with `" · "` in a muted span, then (unless `needs_admin`) two radio inputs named `rn-{index}` with `data-rn="{index}|same"` and `data-rn="{index}|different"`, checked from `picks[old]`, disabled when `offers` says so, labelled `Same person` with the muted sentence `"Everything {old} has goes to {new}."` and `A different person` with `"{new} starts fresh. {old}'s account is removed."` (for a pair with no `account`, only a Telegram link: `"{new} starts fresh. {old}'s Telegram link is removed."`); then `offers(pair).note` when not empty; a `needs_admin` line has no inputs and says the admin sentence instead. Every name and word goes through `esc`.
  - `body(pairs, picks) -> object`: `{ renames: { old: pick } }` for the pairs that have a pick.

- [ ] **Step 1: Write the failing tests** in `tests/renames.test.js` (plain `assert`, like `tests/teacherview.test.js`): `gate` for no pairs, a missing pick, all picked, a `needs_admin` pair; `offers` for the four combinations above; `card` holds the heading, each sentence, `checked` on the picked input, `disabled` where not offered, no input for a `needs_admin` pair, and an escaped name (`"<b>"` in a name must not appear raw); `body` leaves out pairs with no pick.
- [ ] **Step 2: Run and see them fail** (`Cannot find module '../static/renames.js'`).
- [ ] **Step 3: Implement `static/renames.js`** and add its `<script>` line to `static/index.html`.
- [ ] **Step 4: Wire the page** in `static/app.js`:
  - In step 9's publish card (the function that ends with the `id="pbPublish"` button): above the row of buttons, `Renames.card(S.draft.renames || [], RN, esc)`; the Publish button is also disabled, with the sentence as its title and shown above it in the style the critical gate uses, when `Renames.gate(...)` is not empty. `RN` is a page-level object of picks by old name, emptied whenever the list of pairs changes (compare the old names).
  - A change on an input with `data-rn` sets the pick and draws the step again (handle it at the top of the `change` listener, before the `data-k` code).
  - `publishDraft` sends `Renames.body(...)` as JSON. A `409` whose answer has `renames` shows the error as a toast and takes the new list.
  - After a publish, and in the "Published now" card from the status, each sentence of `renamed` is shown as its own muted line under "Published …".
- [ ] **Step 5: Check** `node --check static/app.js && for f in tests/*.test.js; do node "$f" > /dev/null || echo "FAIL $f"; done` prints nothing.
- [ ] **Step 6: Commit**

```bash
git add static/renames.js static/index.html static/app.js tests/renames.test.js
git commit -m "feat(step 9): the card that asks about each renamed teacher"
```

(The browser check of this task is the controller's.)

---

### Task 5: The guide and the notes

**Files:**
- Modify: `README.md` (the "**Renaming a teacher.**" paragraphs, the Publish item of "From setup to published timetable", the Admin page part)
- Create: `docs/superpowers/plans/2026-11-24-teacher-rename-stage-2-notes.md`

- [ ] **Step 1: README.** Replace the "Not yet" sentences with what is true now: before publishing, step 9 lists each renamed teacher who has an account or a Telegram link and asks same person or a different person; what each does; that only an admin can publish when an account is involved; that the personal code is new either way; that reliefs and exam duties still stay under the old name (planned, not built). Check every sentence against the code, citing the line in your report.
- [ ] **Step 2: Notes file**: rulings from the ledger, known limits (a failure after the publish leaves a pair "could not be finished" with no retry until stage 3; reliefs and exam duties do not follow; a rename published before this stage is not asked about), what was checked in a browser and what was not.
- [ ] **Step 3: Commit** `README.md` and the notes file.

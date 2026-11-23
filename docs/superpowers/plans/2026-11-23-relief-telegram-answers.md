# Relief on Telegram: the lead's answers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Five small additions to relief on Telegram that the committee lead asked for on 23 Nov 2026: the relief team is pinged for
a request for today (A), the app's form says when the reporting officer is not on Telegram (B), `/relief` takes any number of
messages a lesson until **Next** (C), a person is told in the app that their Telegram was unlinked because the bot was blocked (D),
and Relief settings shows which messages could not be sent (E).

**Architecture:** Nothing new is sent from a route. A is one more message worked out by the sweep (`relief/tell.py` `due`), under a
key claimed once and checked again by `still_true`, like every other. B is one more field in the answer of the existing route that
sends an absence. C changes the work question of `relief/asking.py` only. D keeps one row in the existing `state` table of
`telegram.db` (no new table, no migration) and shows it in the existing status route. E reads the existing `outbox` table in the
existing settings route. No new route, no new right, no new dependency.

**Tech Stack:** Python 3 / Flask, sqlite3, plain JavaScript, plain-assert test scripts (as stage 4).

**Spec:** `docs/superpowers/specs/2026-11-20-relief-module-design.md` ("Telegram", "Module 1 ... Ask for relief"), stage 4's notes
`docs/superpowers/plans/2026-11-22-relief-stage-4-notes.md` ("Open questions for the lead" 1 to 11, "Known limits", "Follow-ups"), and
the lead's answers of 23 Nov 2026: 1 yes, 2 keep, 3 keep, 4 keep, 5 yes, 6 build it ("fixed for both": a text and a file must both land
on the same lesson), 7 keep, 8 keep, 9 not now, 10 yes, 11 ok, 12 yes, 13 fix next time Today is touched (not now). Stage 4's plan
`2026-11-22-relief-stage-4-telegram.md` (its message table and button labels) is the copy this plan extends.

**Branch:** `relief-telegram-answers`, cut from main ebdccb9 (stage 4 merged), worktree `tt-relief-stage-4`. Nothing is pushed.

## Global Constraints

From stage 4's plan, verbatim where they apply:
- The repo is public: the school is only ever "CTSS"; tests, samples and docs use made-up names only.
- **Never print, log, show or commit a real token, code or key.** The bot's address holds the token: no URL, no exception
  text and no Telegram answer body is ever logged; failures are logged to `relief.telegram` by kind alone.
- **No real Telegram call anywhere in tests or checks.** `relief/tg.py` has one network function, `_send`; every test
  replaces it at import with a function that fails if called. Browser checks use `TELEGRAM_BOT_TOKEN=practice`.
- **Nothing is sent to a relief teacher before a relief team member approves it.** Only covers in state `approved` make
  a relief message.
- **A Telegram message carries a person's name, class, subject, room, period, time, work; never the typed absence reason,
  remarks, a pick's history, or anything from the model except the pick's own reason line to the team.**
- A button press or typed answer does exactly what the page's button does: same functions, same rights
  (`rights.rights(person, "telegram")`), same sentences, one history entry by that person with via `telegram`.
- Nothing network-bound runs under `absences._LOCK`. The webhook handler makes no model call.
- "Today" and "now" are school time (`lessons.today()`, `absences._now()`); lesson times come from `exams.days.bounds`.
- Tests are plain-assert scripts run as `.venv/bin/python tests/<name>.py`, `DATA_DIR` set to a fresh temp folder before
  `import app`; `RELIEF_JOBS` never set; `TELEGRAM_BOT_TOKEN` set to `practice` or a random made-up string, never real.
- Rights names used: `relief`, `relief.plan`, `relief.team`, `relief.save`. No new right name.
- Builders and reviewers: NEVER run `git stash`, `git stash pop` or `git checkout -- <file>`; `git stash list` unchanged
  after each task. In `static/*.js`, never a `//` comment in the middle of a long line; use `/* */`.
- Dates read "Tue 13 Oct"; periods "P9–P11"; times "10:40". The sentences below are used verbatim.
- Every commit ends with `Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>`, written with a quoted heredoc.

Added for this plan:
- Nothing is pushed. No real Telegram or model call. Made-up names only; the school only "CTSS". Logs by kind alone.
- A message never holds the typed reason (nor the reason's kind, except the officer's message as before).
- Every new route goes through `need()` and is listed in `tests/test_routes.py` (this plan adds none: B, D and E extend existing
  routes). Every save writes one history entry as existing relief saves do (this plan adds no save by a person).
- No em-dashes and no arrows in copy, docs or notes. `·` is U+00B7.
- Tasks run one after another, in the order below, never in parallel (they share `tests/test_relief_telegram.py` and the notes).
  Each task appends its tests in a new section at the end of `tests/test_relief_telegram.py`, headed `# ---- Answers, Task N: ... ----`.
- "Run the suites" means, one at a time: `.venv/bin/python tests/test_relief_telegram.py`, `tests/test_relief_team.py`,
  `tests/test_relief_requests.py`, `tests/test_routes.py`, `tests/smoke.py`, and `node tests/<file>` for each node file the task
  touched. Each prints its count and no failure.

## Review Focus

1. **A storm of pings**: a head plans several absences for today, or an exam's schedule makes 40 backups at once. Expected: one
   message an absence a team member, never one a lesson, never for a backup, never a second for the same absence. (Task 3,
   `one_ping_an_absence_never_a_lesson_never_a_backup`.)
2. **A ping before any pick**: the sweep that follows the save runs before the picks of that absence are made, or between two of
   them. Expected: no ping while a lesson of today is still open and the absence is under five minutes old. (Task 3,
   `no_ping_while_a_pick_is_on_its_way`.)
3. **A blocked line that never clears, or shows to the wrong person**: expected to show to that person alone, and to go when they
   link again in any way (code, Start, moved link). (Task 2, `the_blocked_line_is_theirs_alone_and_goes_when_they_link`.)
4. **A `/relief` conversation where work lands on the wrong lesson, or is lost when Next is not pressed**: a text, a file and an
   album meant for one lesson all stay on it until Next; Later for all the rest keeps it; a file at the list goes nowhere silently.
   (Task 5, `work_waits_for_next_and_lands_on_its_lesson`.)
5. **The settings line leaking a message's text, a key or a reason**: expected to hold only a plain kind, a name, a time and a state.
   (Task 4, `the_unsent_line_never_holds_a_text_a_key_or_a_reason`.)

---

## Decisions taken in this plan (the lead may change any)

1. **A: relief planned by somebody else for today pings too**, as a request does: the team must approve it just as soon. If wrong:
   one condition.
2. **A: only an absence sent today pings.** One sent yesterday evening for today (picked at once, since its fill time has passed)
   does not: a message at 21:00 would wake people, and the team opens Today in the morning, where it waits. If wrong: a late
   request is seen only when someone opens Today.
3. **A: the ping waits until no lesson of today of that absence is still open, or five minutes after it was sent**, then counts
   the lessons waiting for a pick's approval and those still open (nobody free, or the pick did not come). So it never goes
   before the picks, and a "nobody is free" absence is pinged within five minutes. If wrong: such an absence is pinged up to five
   minutes late.
4. **A: never to who sent the absence, nor to the absent teacher**, when either is on the team. If wrong: one name in a set.
5. **A: the number in the text is the one when it was made**; the message is dropped if nothing of today waits when it goes, but
   not rewritten. If wrong: it may say "2 lessons" when one is left.
6. **A: claimed once, even when dropped**: if the team approves everything before the ping goes, no ping comes later for that
   absence, even if a pick goes back to open. If wrong: a second ping for one absence is never possible.
7. **B: the form says only the "not on Telegram" sentence**, after "Sent. The relief team can see it." on the same line; it does not
   say "{officer} will be told." If wrong: copy.
8. **B: the same rule as the officer's message**: an officer is named, is neither the absent teacher nor who sent it, and the bot is
   connected. If wrong: one condition.
9. **C: a second text for a lesson is added to the first, on a new line, not put in its place.** People type in pieces on a phone
   ("Read p. 5", then "Collect at the end"); a slip is mended in the app, or with Start again. If wrong: a corrected line shows both.
10. **C: a second link replaces the first** (a lesson has one link, as in the app), and the bot says so. If wrong: copy.
11. **C: before anything is set, the buttons are as now** (Later does what Next would). Once something is set: **Next**, and **Later for
    all the rest** when two lessons or more are left; Same as before and Later are gone, so nothing set is thrown away by a press.
    If wrong: a button.
12. **C: after each message the lesson's question is asked again at the bottom of the chat** (a new message, the one before loses its
    buttons), saying what is set; the later files of an album change it in place. If wrong: one message more a piece.
13. **D: the note is the row `blocked:{name}` in the existing `state` table**, written only while that person has no link, and taken
    away only when they link again. If wrong: the line stays for someone who never links again.
14. **D: no history entry.** `app.py`'s `_relief_entry` reads the session (`by()`) when no person's name is given, and the sender
    has none, so an entry "by The app" cannot be written through the hook as it is. One condition in `_relief_entry` would allow it
    (an open question). If wrong: one condition and one entry.
15. **E: report and all clear are left out** (each is true for 30 minutes only; a late one is never sent), and so is the relief
    itself (Today shows it). The weekly summary is shown. A kind this plan does not name (exams' own, later) shows as "Message".
    If wrong: one list.
16. **E: newest first, 20 at most, then "and {n} more"; "since Monday" by when it was tried** (may not have been sent) or queued
    (could not be sent). If wrong: one number, one column.

## File structure

| File | Change |
|---|---|
| `relief/tell.py` | A: `new_text`, `_new`, `_waiting_today`, `_new_true`, `NEW_WAIT`, `OPEN_TODAY`, `NOT_TOLD` (B), `TOLD` gains `"new:"` |
| `relief/web.py` | B: `_not_told(r, pub)`; `create` adds `officer_not_told` |
| `static/relief.js` | B: `R.sentSays(data)` and the confirmation |
| `relief/links.py`, `relief/outbox.py` | D: `note_blocked`, `blocked`; `_put` clears it; `_blocked` notes it |
| `relief/tgweb.py` | D: `_status` gains `blocked`; E: `_unsent()`, `UNSENT`, `UNSENT_SHOWN`, `_admin` gains `unsent` |
| `static/relief-telegram.js` | D: the blocked line |
| `static/relief-settings.js` | E: the unsent line and list |
| `relief/asking.py` | C: the work question, Next, adding work, albums |
| `tests/test_relief_telegram.py`, `tests/relief_telegram.test.js`, `tests/relief_settings.test.js` | the tests |
| `docs/DEPLOY.md`, `README.md`, stage 4's plan and notes, the new notes file | Task 6 |

---

### Task 1: The form says when the reporting officer is not on Telegram (B)

**Files:**
- Modify: `relief/tell.py` (top constants), `relief/asking.py:63`, `relief/web.py` (`create`, about line 448), `static/relief.js` (`send`, about line 600; `R`, line 20)
- Test: `tests/test_relief_telegram.py`, `tests/relief_telegram.test.js`

**Interfaces:**
- Produces: `tell.NOT_TOLD = "{officer} is not on Telegram: please tell them yourself."` (moved from asking.py; `asking.NOT_TOLD = tell.NOT_TOLD`).
  `web._not_told(r: dict, pub) -> str | None`. The answer of `POST /api/relief/absences` holds `officer_not_told` (the sentence) only when there is
  something to say; the key is absent otherwise. `window.Relief.sentSays(data) -> str`.

- [ ] **Step 1: Write the failing tests** (Python, at the end of the test file)

```python
# ---- Answers, Task 1: the form and the reporting officer ----
NOT_TOLD_ROSA = "Ms Rosa Ng is not on Telegram: please tell them yourself."
ASKED = dict(dates=["2026-10-13"], periods=None, reason="Medical", reason_text="", reporting_officer=ROSA, lessons=[])

@t
def the_form_says_when_the_officer_is_not_on_telegram():
    with school(EVE):
        assert call(EVE, "post", "/api/relief/absences", ASKED)["officer_not_told"] == NOT_TOLD_ROSA
        assert AK.NOT_TOLD is TE.NOT_TOLD
    with school(EVE, ROSA): assert "officer_not_told" not in call(EVE, "post", "/api/relief/absences", ASKED), "she will be told"
    with school(EVE):
        tgdb.set_state("bot", None); assert "officer_not_told" not in call(EVE, "post", "/api/relief/absences", ASKED), "no bot: nothing is said of it"
    with school(EVE):
        assert "officer_not_told" not in call(HUGO, "post", "/api/relief/absences", dict(ASKED, teacher=EVE, reporting_officer="")), "no officer named"
        assert "officer_not_told" not in call(HUGO, "post", "/api/relief/absences", dict(ASKED, teacher=EVE, dates=["2026-10-14"], reporting_officer=HUGO)), "the officer sent it"
    with school(EVE):
        def boom(*a, **k): raise RuntimeError("made up")
        with stand_in(links, "reachable", boom): r = call(EVE, "post", "/api/relief/absences", ASKED)
        assert "officer_not_told" not in r and len(mine()) == 1, "never the save's failure"
```

JavaScript, in `tests/relief_telegram.test.js` (its `opened()` loads `relief.js`):

```js
t("the ask form's Sent says when the officer is not on Telegram", async () => {
  const p = await opened({ "GET ": ok(FREE) }), say = p.window.Relief.sentSays, plain = "Sent. The relief team can see it.";
  assert.strictEqual(say({}), plain);
  assert.strictEqual(say({ officer_not_told: "Ms Rosa Ng is not on Telegram: please tell them yourself." }), `${plain} Ms Rosa Ng is not on Telegram: please tell them yourself.`);
  for (const odd of [null, 7, "", ["x"], { x: 1 }]) assert.strictEqual(say({ officer_not_told: odd }), plain, JSON.stringify(odd));
  assert.strictEqual(say(null), plain);
});
```

- [ ] **Step 2: Run them to see them fail**: `.venv/bin/python tests/test_relief_telegram.py` (KeyError `officer_not_told`), `node tests/relief_telegram.test.js` (`sentSays` is not a function).
- [ ] **Step 3: Implement.** `_not_told(r, pub)`: `None` unless `r["reporting_officer"]` is set and not in `(r["teacher"], r["by"])` and `_connected()`;
  then `_tell.NOT_TOLD.format(officer=...)` when the officer is not in `_chats.reachable(pub)`; any exception is logged by kind
  (`current_app.logger.error("relief: whether the officer is on Telegram could not be read (%s)", ...)`) and gives `None`. In `create`, after
  `created(how, r, pub)`: `out = _out(r, pub, me)`, add the key when `_not_told` gives a sentence, `jsonify(out)`. In `relief.js`: `sentSays(d)` gives
  `"Sent. The relief team can see it."` plus `" " + d.officer_not_told` when that is a non-empty string; `send()` uses it for `A.msg.text`; add
  `sentSays` to `window.Relief`.
- [ ] **Step 4: Run the suites** (node: `relief_telegram.test.js`). All pass.
- [ ] **Step 5: Commit** `Relief: the form says when the reporting officer is not on Telegram`.

### Task 2: Told in the app that the bot was blocked (D)

**Files:**
- Modify: `relief/links.py` (`_put`, new `note_blocked`, `blocked`), `relief/outbox.py` (`_blocked`, about line 235), `relief/tgweb.py` (`_status`, line 129), `static/relief-telegram.js` (`line`, line 29)
- Test: `tests/test_relief_telegram.py`, `tests/relief_telegram.test.js`

**Interfaces:**
- Produces: `links.BLOCKED = "blocked:"`; `links.note_blocked(name: str) -> bool` (writes state `blocked:{name}` = `_absences._now()` in one
  `tgdb.db()` block, only while `links` has no row for name; True when written); `links.blocked(name: str) -> str | None` (the ISO time);
  `_put` deletes `blocked:{name}` in its own transaction. `GET /api/relief/telegram` gains `blocked`: the ISO time while not linked, else `None`.
- Consumes: `outbox._blocked` keeps calling `links.unlink(item["name"], chat)` (stage 4's tests stand in for it); when that returns a chat it calls
  `links.note_blocked(item["name"])`, inside the same `try`.
- Copy: `Your Telegram was unlinked on {day}: the bot was blocked there. Unblock it in Telegram, then link again.`

- [ ] **Step 1: Write the failing tests**

```python
# ---- Answers, Task 2: unlinked because the bot was blocked ----
def status_of(name): return who(name).get("/api/relief/telegram").get_json()

@t
def the_blocked_line_is_theirs_alone_and_goes_when_they_link():
    with made_up():
        links.link(TIA, 501, None); links.link(HUGO, 502, None); f, seen = tele(BLOCKED)
        with now_is("2026-10-13T07:10:00+08:00"): q("a"); with_send(f, OB.send_due)
        assert links.blocked(TIA) == "2026-10-13T07:10:00+08:00" and status_of(TIA)["blocked"] == "2026-10-13T07:10:00+08:00" and status_of(TIA)["linked"] is False
        assert links.blocked(HUGO) is None and status_of(HUGO)["blocked"] is None, "nobody else's"
        links.link(TIA, 601, None); assert links.blocked(TIA) is None and status_of(TIA)["blocked"] is None, "linked again"
        links.unlink(TIA); links.note_blocked(TIA); c = links.new_code(TIA)["code"]; assert links.use(c, 601, None) == TIA and links.blocked(TIA) is None, "by a code too"
        assert links.note_blocked(TIA) is False and links.blocked(TIA) is None, "never while they are linked"
        assert [r["k"] for r in rows("state") if r["k"].startswith("blocked:")] == []

@t
def only_a_blocked_bot_makes_the_line():
    with made_up():
        links.link(TIA, 501, None); links.unlink(TIA); assert links.blocked(TIA) is None, "Unlink, /stop or the team"
        links.link(TIA, 501, None); tgweb_unlink = who(TEAM).post("/api/relief/telegram/unlink", json=dict(name=TIA)); assert tgweb_unlink.status_code == 200 and links.blocked(TIA) is None
        links.link(TIA, 501, None); f, seen = tele(BLOCKED, before=lambda *a: tgdb.set_state("bot", None)); q("a"); with_send(f, OB.send_due)
        assert links.blocked(TIA) is None, "the bot disconnected meanwhile: nobody unlinked, no line"
        bot_on("ctss_made_up_bot"); real = links.unlink
        def late(name, *a): links.link(TIA, 601, None); return real(name, *a)
        with stand_in(links, "unlink", late): f, seen = tele(BLOCKED); q("b"); with_send(f, OB.send_due)
        assert links.chat_of(TIA) == 601 and links.blocked(TIA) is None, "linked again on another phone between: no line"
```

JavaScript (`tests/relief_telegram.test.js`):

```js
const BLOCKED = "Your Telegram was unlinked on Tue 13 Oct: the bot was blocked there. Unblock it in Telegram, then link again.";
t("unlinked because the bot was blocked: said until they link again", async () => {
  const p = await opened({ "GET ": ok(Object.assign({}, FREE, { blocked: "2026-10-13T07:10:00+08:00" })) });
  assert.strictEqual(p.card(), `Telegram ${BLOCKED} Link Telegram`);
  p.api["POST /code"] = () => code(p); await p.click("button", "Link Telegram"); hasNot(p, BLOCKED);
  const q = await opened({ "GET ": ok(Object.assign({}, LINKED, { blocked: "2026-10-13T07:10:00+08:00" })) }); hasNot(q, BLOCKED); has(q, "Linked as @sam_made_up");
  const r = await opened({ "GET ": ok(Object.assign({}, FREE, { blocked: null })) }); has(r, LINE);
});
```

- [ ] **Step 2: Run them to see them fail** (`links.blocked` does not exist; the card shows LINE).
- [ ] **Step 3: Implement** the interfaces above. In `relief-telegram.js` `line(st)`: when not linked and no code shows, `C.out` first
  ("That code has run out."), then `st.blocked` (the sentence with `day(st.blocked)`), then LINE. Update the module docstrings of
  `links.py` and `outbox.py` (blocked: unlinked, the item removed, and the note).
- [ ] **Step 4: Run the suites** (node: `relief_telegram.test.js`). Stage 4's `a_blocked_chat_is_unlinked` passes unchanged.
- [ ] **Step 5: Commit** `Relief: a person unlinked because the bot was blocked is told so in the app`.

### Task 3: The relief team is pinged for a request for today (A)

**Files:**
- Modify: `relief/tell.py` (`TOLD`, `_absence`, `CHECKS`, new functions; the module docstring's list of keys)
- Test: `tests/test_relief_telegram.py`

**Interfaces:**
- Produces: kind `new`, key `new:{absence id}:{name}`, ref `dict(id=..., date=today ISO)`; `tell.NEW_WAIT = datetime.timedelta(minutes=5)`;
  `tell.OPEN_TODAY = "Open relief today"` (equal to `report.OPEN_TODAY`); `tell.new_text(absent: str, away: str, n: int) -> str`;
  `tell._waiting_today(r: dict, today: str, now, bnds, links) -> tuple[int, int]` (waiting, open: covers of r on today, needed, not over,
  not stopped as far as is known, of an absence not cancelled; state `waiting`, and state `open`); `tell._new(w, r) -> list` (items);
  `tell._new_true(ref: dict, name: str) -> bool`, in `CHECKS["new"]`. `TOLD` gains `"new:"`.
- Rule (`_new`): nothing when `r.get("exams")`, `r.get("cancelled")`, `str(r["at"])[:10] != w.today.isoformat()`, or not `_since(w, r["at"])`.
  `(waiting, open) = _waiting_today(...)`; nothing while `open` and `w.now - _time(r["at"]) < NEW_WAIT`; nothing when `waiting + open == 0`.
  Then one item to each of `w.team` not in `(r.get("by"), r["teacher"])` whose key is not in `w.told` at all (any state, dropped too: claimed once).
  Buttons `[[dict(text=OPEN_TODAY, url=w.base + "/relief#today")]]`.
- `_new_true`: the record (`_read`) is there and not cancelled, `ref["date"]` is today (`_fill._when(None).date()`), `_on_team(name)`, and
  `sum(_waiting_today(...))` with the published timetable's bounds and `_exams()[2]` is above 0.
- Copy (three lines): `🆕 Relief asked for today · {absent}` / `{whole day or periods}` (`words.away(r)`) / `{n} lessons are waiting for your approval.`
  (one: `1 lesson is waiting for your approval.`).

- [ ] **Step 1: Write the failing tests**

```python
# ---- Answers, Task 3: the team pinged for a request for today ----
from relief import report as RO  # noqa: E402
NEW_EVE = "🆕 Relief asked for today · Ms Evelyn Koh\nwhole day\n2 lessons are waiting for your approval."
OPEN_TODAY = [[dict(text="Open relief today", url=BASE + "/relief#today")]]
def news(): return sorted((r["key"], r["name"], r["text"]) for r in outs("new"))
def pick(i, ckey, who_=SAM): return CV.set_pick(i, ckey, dict(who=who_, by="ai", reason="Free then.", at=clock.now), SCHOOL, rs())

@t
def the_team_hears_once_of_a_request_for_today():
    assert TE.new_text("{absent}", "{whole day or periods}", 1).endswith("\n1 lesson is waiting for your approval.") and TE.OPEN_TODAY == RO.OPEN_TODAY
    with school(EVE, TEAM, LEE):
        at("07:00", day=13); i = absent(reason="Other", reason_text="zebra-private"); swept(); assert news() == [], "not before a pick"
        FL.run(ids=[i]); swept()
        assert news() == [(f"new:{i}:{LEE}", LEE, NEW_EVE), (f"new:{i}:{TEAM}", TEAM, NEW_EVE)] and all(buttons_of(r) == OPEN_TODAY for r in outs("new"))
        assert said(TEAM)[-1] == NEW_EVE and not any("zebra" in r["text"] or "Other" in r["text"] for r in outs())
        FL.run(ids=[i]); at("07:30", day=13); swept(); assert len(outs("new")) == 2, "one a person, whatever comes after"

@t
def no_ping_while_a_pick_is_on_its_way():
    with school(EVE, TEAM, LEE):
        at("07:00", day=13); i = absent(); pick(i, K2); at("07:04:59", day=13); swept(); assert news() == [], "one picked, one still to come"
        at("07:05", day=13); swept(); assert [x[2] for x in news()] == [NEW_EVE] * 2, "five minutes on: the open one waits for the team too"
    with school(EVE, TEAM, LEE, limits=dict(fat_per_day=3, other_per_day=None, never=[SAM, MAYA, RUTH, BUSY, HUGO, LEE, TEAM, ROSA, OFFIE])):
        at("07:00", day=13); i = absent(); FL.run(ids=[i]); swept(); assert news() == []
        at("07:05", day=13); swept(); assert len(news()) == 2, "nobody free: the team must choose"

@t
def one_ping_an_absence_never_a_lesson_never_a_backup():
    with school(EVE, TEAM, LEE):
        at("07:00", day=13); ids = [absent(), absent(teacher=SAM, by=HUGO), absent(teacher=RUTH, by=HUGO)]
        j = absent(teacher=BUSY, by=HUGO); change_record(j, lambda r: r.update(exams=dict(source="made-up")))
        FL.run(); swept(); assert sorted(k.split(":")[1] for k, n, x in news()) == sorted(ids * 2), "planned by a head too; a backup never"
        swept(); FL.run(); swept(); assert len(news()) == 6

@t
def only_today_only_since_connected_never_to_who_sent_it():
    with school(EVE, TEAM, LEE):
        at("07:00", day=13); i = absent(by=TEAM); FL.run(ids=[i]); swept(); assert [n for k, n, x in news()] == [LEE], "not to who planned it"
    with school(EVE, TEAM, LEE):
        at("07:00", day=13); i = absent(dates=("2026-10-14",)); FL.run(ids=[i]); swept(); assert news() == [], "another day"
    with school(EVE, TEAM, LEE):
        at("20:00", day=12); i = absent(); FL.run(ids=[i]); swept(); at("07:00", day=13); swept(); assert news() == [], "sent the evening before"
    with school(EVE, TEAM, LEE, since="2026-10-13T08:00:00+08:00"):
        at("07:00", day=13); i = absent(); FL.run(ids=[i]); at("08:01", day=13); swept(); assert news() == [], "before the bot was connected"

@t
def a_ping_no_longer_true_is_dropped_and_not_made_again():
    def approve_all(i):
        for k in (K2, K5): CV.approve(i, k, covered(i, k)[2]["relief"], TEAM, SCHOOL, rs())
    with school(EVE, TEAM, LEE):
        at("07:00", day=13); i = absent(); FL.run(ids=[i]); TE.sweep(); approve_all(i); send()
        assert [state(f"new:{i}:{n}") for n in (LEE, TEAM)] == ["dropped"] * 2; TE.sweep(); assert [state(f"new:{i}:{n}") for n in (LEE, TEAM)] == ["dropped"] * 2, "claimed once"
    with school(EVE, TEAM, LEE):
        at("07:00", day=13); i = absent(); FL.run(ids=[i]); TE.sweep(); absences.cancel(i, "Better", EVE); send(); assert state(f"new:{i}:{TEAM}") == "dropped"
    with school(EVE, TEAM, LEE):
        at("07:00", day=13); i = absent(dates=("2026-10-13", "2026-10-14")); FL.run(ids=[i]); TE.sweep(); at("07:00", day=14); send(); assert state(f"new:{i}:{TEAM}") == "dropped", "the day is past"
    with school(EVE, TEAM, LEE):
        at("07:00", day=13); i = absent(); FL.run(ids=[i]); TE.sweep()
        with record(LEE, extras=dict(relief=False, exams=None, admin=False)): send()
        assert (state(f"new:{i}:{LEE}"), state(f"new:{i}:{TEAM}")) == ("dropped", "sent"), "off the team by then"
```

- [ ] **Step 2: Run them to see them fail** (`TE.new_text` does not exist).
- [ ] **Step 3: Implement** the interfaces above. `_absence` returns `_new(w, r) + ...` for an absence not cancelled. Add the key and the rule to the
  module docstring ("new:{id}:{name} to each of the team but who sent it and the absent teacher ...").
- [ ] **Step 4: Run the suites.** Stage 4's tests that count every queued message of a day today (if any fail on a new `new` row) are put right by
  adding the team ping to what they expect, never by weakening the rule; name each one in the commit message.
- [ ] **Step 5: Commit** `Relief: the relief team is pinged on Telegram for a request for today`.

### Task 4: Relief settings shows messages that could not be sent (E)

**Files:**
- Modify: `relief/tgweb.py` (`_admin`, new `_unsent`, `UNSENT`, `UNSENT_LEFT_OUT`, `UNSENT_SHOWN`), `static/relief-settings.js` (`tgPaint`, new `tgUnsent`)
- Test: `tests/test_relief_telegram.py`, `tests/relief_settings.test.js`

**Interfaces:**
- Consumes: kind `new` (Task 3).
- Produces: `tgweb.UNSENT = dict(planned="Relief planned", remind="Reminder to acknowledge", officer="To the reporting officer", ask="Request to change",
  askpick="New pick for a request to change", kept="Relief kept", cancelled="Absence cancelled", gone="No longer needed", moved="Relief moved",
  stopped="Not happening", again="On again", weekly="Weekly summary", new="New request for today")`; any other kind: `"Message"`;
  `tgweb.UNSENT_LEFT_OUT = ("relief", "report", "clear")`; `tgweb.UNSENT_SHOWN = 20`.
  `tgweb._unsent() -> dict | None`: `dict(failed: int, unsure: int, since: ISO Monday, more: int, items: [dict(what, name, at, state)])`, newest first
  (then by name), counts over every row kept, items the first `UNSENT_SHOWN`,
  from `SELECT kind, name, state, at, sent_at FROM outbox WHERE state IN ('failed', 'unsure')` (never `text`, `key`, `ref`, `buttons`), "at" as
  outbox's `_state` has it (`sent_at` for unsure, else `at`), kept when at or after Monday 00:00 school time (`calendar.week_of(lessons.today())[0]`);
  `None` when there is none. `GET /api/relief/telegram/admin` (and connect, disconnect, unlink, which answer `_admin()`) gains `unsent`.
- Copy (page): `{n} message(s) could not be sent, {m} may not have been sent, since {day}.`; one part alone: `{n} message(s) could not be sent since {day}.`
  or `{m} message(s) may not have been sent since {day}.` ("message" for 1, "messages" otherwise; `{day}` "Mon 12 Oct"). Each row:
  `{what} · {name} · {day} {hh:mm} · could not be sent` or `· may not have been sent`; then `and {more} more` when more.

- [ ] **Step 1: Write the failing tests**

```python
# ---- Answers, Task 4: what could not be sent, on the settings card ----
ADMIN = "/api/relief/telegram/admin"
def unsent_rows(*rows_):
    for key, name, kind, st, when in rows_: q(key, name, kind=kind); put(key, state=st, at=when, sent_at=when if st == "unsure" else None)

@t
def the_settings_say_what_could_not_be_sent_since_monday():
    with school(EVE, ROSA, TEAM, LEE):
        at("09:00", day=13); assert call(TEAM, "get", ADMIN)["unsent"] is None
        unsent_rows(("planned:a", EVE, "planned", "failed", "2026-10-13T07:10:00+08:00"), ("officer:a", ROSA, "officer", "unsure", "2026-10-12T15:00:00+08:00"),
                    (f"weekly:w:{TEAM}", TEAM, "weekly", "failed", "2026-10-12T15:00:00+08:00"), ("relief:x", EVE, "relief", "failed", "2026-10-13T07:00:00+08:00"),
                    (f"report:x:{TEAM}", TEAM, "report", "failed", "2026-10-13T07:15:00+08:00"), (f"clear:x:{LEE}", LEE, "clear", "unsure", "2026-10-13T07:30:00+08:00"),
                    ("planned:b", EVE, "planned", "failed", "2026-10-11T20:00:00+08:00"), (f"ask:x:{TEAM}", TEAM, "ask", "sent", "2026-10-13T08:00:00+08:00"),
                    (f"new:x:{LEE}", LEE, "new", "queued", "2026-10-13T08:30:00+08:00"), ("exam:x", ROSA, "exam-made-up", "failed", "2026-10-12T09:00:00+08:00"))
        u = call(TEAM, "get", ADMIN)["unsent"]
        assert u == dict(failed=3, unsure=1, since="2026-10-12", more=0, items=[
            dict(what="Relief planned", name=EVE, at="2026-10-13T07:10:00+08:00", state="failed"), dict(what="To the reporting officer", name=ROSA, at="2026-10-12T15:00:00+08:00", state="unsure"),
            dict(what="Weekly summary", name=TEAM, at="2026-10-12T15:00:00+08:00", state="failed"), dict(what="Message", name=ROSA, at="2026-10-12T09:00:00+08:00", state="failed")]), u
        assert set(tgweb.UNSENT) == {"planned", "remind", "officer", "ask", "askpick", "kept", "cancelled", "gone", "moved", "stopped", "again", "weekly", "new"} and tgweb.UNSENT["new"] == "New request for today"
        call(EVE, "get", ADMIN, code=401)                                                  # need("relief.save"): as before

@t
def the_unsent_line_never_holds_a_text_a_key_or_a_reason():
    with school(EVE, ROSA, TEAM):
        at("09:00", day=13); i = absent(reason="Other", reason_text="zebra-private")
        for n in range(25): q(f"planned:{i}:{n}", EVE, text="A made-up message zebra-private", kind="planned"); put(f"planned:{i}:{n}", state="failed", at=f"2026-10-13T07:{n:02d}:00+08:00")
        got = call(TEAM, "get", ADMIN); u = got["unsent"]
        assert (u["failed"], len(u["items"]), u["more"], u["items"][0]["at"]) == (25, 20, 5, "2026-10-13T07:24:00+08:00"), "newest first, 20 at most"
        text = json.dumps(got); assert "made-up message" not in text and "zebra" not in text and "planned:" not in text and i not in text
```

JavaScript (`tests/relief_settings.test.js`):

```js
const UNSENT = { failed: 2, unsure: 1, since: "2026-10-12", more: 0, items: [
  { what: "Relief planned", name: EVE, at: "2026-10-13T07:10:00+08:00", state: "failed" }, { what: "To the reporting officer", name: "Ms Rosa <b>Ng", at: "2026-10-12T15:00:00+08:00", state: "unsure" }] };
t("what could not be sent is said, by kind, name and time alone", async () => {
  const p = await opened({ "GET admin": ok(Object.assign({}, CONNECTED, { unsent: UNSENT })) });
  for (const x of ["2 messages could not be sent, 1 may not have been sent, since Mon 12 Oct.", `Relief planned · ${EVE} · Tue 13 Oct 07:10 · could not be sent`,
                   "To the reporting officer · Ms Rosa <b>Ng · Mon 12 Oct 15:00 · may not have been sent"]) assert.ok(p.card().includes(x), x);
  assert.ok(!p.$("#telegram").innerHTML.includes("<b>Ng"), "escaped");
  const one = await opened({ "GET admin": ok(Object.assign({}, CONNECTED, { unsent: Object.assign({}, UNSENT, { failed: 1, unsure: 0, items: UNSENT.items.slice(0, 1) }) })) });
  assert.ok(one.card().includes("1 message could not be sent since Mon 12 Oct."));
  const unsure = await opened({ "GET admin": ok(Object.assign({}, CONNECTED, { unsent: Object.assign({}, UNSENT, { failed: 0, unsure: 1, more: 5, items: UNSENT.items.slice(1) }) })) });
  assert.ok(unsure.card().includes("1 message may not have been sent since Mon 12 Oct.") && unsure.card().includes("and 5 more"));
  for (const none of [null, undefined, {}, 7]) { const q = await opened({ "GET admin": ok(Object.assign({}, CONNECTED, { unsent: none })) }); assert.ok(!/could not be sent|may not have been sent/.test(q.card()), String(none)); }
});
```

- [ ] **Step 2: Run them to see them fail** (`unsent` is missing).
- [ ] **Step 3: Implement** the interfaces. On the page: a `<div id="tgUnsent" class="small">` after `tgCount` in the card's skeleton, drawn with
  `tgPut` (not a live region), the line in a `<p>` and the rows in a `<ul>`; nothing when `unsent` is not an object with items.
- [ ] **Step 4: Run the suites** (node: `relief_settings.test.js`).
- [ ] **Step 5: Commit** `Relief: the settings card says which messages could not be sent`.

### Task 5: /relief takes any number of messages a lesson until Next (C)

**Files:**
- Modify: `relief/asking.py` (`WORK_SET`, `NEXT`, `LINK_REPLACED`, `_work`, `_on_work`, `_say_work`, `_add`, `_held`, `_more`, the module docstring)
- Test: `tests/test_relief_telegram.py` (new tests, and Task 8's tests that walk the work by messages)

**Interfaces:**
- Produces: `asking.WORK_SET = "Work for {lesson} {periods} on {day}{start}: {what}. Send more, or press Next."` (`{what}` is `_what`'s,
  "work set (text, 1 file)"); `asking.NEXT = "Next"`; `asking.LINK_REPLACED = "One link a lesson: this one is in place of the one before."`;
  `WORK` unchanged. A lesson's work in the conversation gains `typed: [str]` (each typed line as it came, beside `captions`).
- Behaviour:
  - `_work(d, at, work)`: the lesson's question is `WORK` with stage 4's rows while nothing is set for it (`_has(_work_of(...))` False), else
    `WORK_SET` with rows `[[(NEXT, "next")], [(LATER_ALL, "rest")] when two lessons or more are left]`.
  - `_on_work`: `"next"` moves to `at + 1` (after the last lesson, the list, as now); `"same"`, `"later"`, `"rest"` as now.
  - `_say_work`: a line or a file is added to the current lesson and the conversation stays at it (`_work(d, d["at"], ...)`), asked again as a new
    message (`_move(..., typed=True)`). A typed line that is a link alone (`_LINK`) sets the link, saying `LINK_REPLACED` first when one was set;
    any other line is added to the text on a new line, and to `typed`; the whole is checked by `absences._check_work` (refused: the app's sentence,
    the question asked again, the work as it was). Files and the link are kept when text is added, and text and files when a link is set.
  - `_add` keeps the lesson's link (today it writes `link=""`, which was harmless while a message moved on) and its `typed`.
  - `_held` holds the `typed` lines too, so a link's preview that comes as an edit of any piece is not answered.
  - `_more` (an album's later file): when the album's lesson is the one asked about, its question's text becomes `_work(...)["ask"]` (rows kept: they
    are already Next's) and is changed in place by `_redraw`; at the list, as now; at another lesson, nothing is redrawn.
  - The list, Send, PRESS_ONE at the list, Start again, `/cancel` and the 30 minutes are unchanged.
  - Stage 4's known limits, after this: lost, "two messages meant for one lesson go to two lessons" and a second file for the last lesson meeting
    PRESS_ONE; kept, a file sent at the list is on no lesson, an album's files are its first file's lesson whatever is pressed meanwhile, an edit is
    never an answer; gained, one more tap a lesson with work, and a message meant for the next lesson sent before Next lands on the one asked about.

- [ ] **Step 1: Write the failing tests**

```python
# ---- Answers, Task 5: /relief, a lesson's work until Next ----
WORK_SET_2 = "Work for 1C Science P3–P5 on Tue 13 Oct (09:00): {}. Send more, or press Next."
WORK_SET_5 = "Work for 1A, 1B Science (G2) P6–P7 on Tue 13 Oct (10:30): {}. Send more, or press Next."
SET_ROWS, LAST_SET_ROWS = [["Next"], ["Later for all the rest"]], [["Next"]]
LINK_REPLACED = "One link a lesson: this one is in place of the one before."

@t
def work_waits_for_next_and_lands_on_its_lesson():
    assert (AK.NEXT, AK.LINK_REPLACED, AK.WORK_SET) == ("Next", LINK_REPLACED, "Work for {lesson} {periods} on {day}{start}: {what}. Send more, or press Next.")
    with school(EVE, ROSA):
        to_work(); assert says(EVE, "Read p. 5") == [(WORK_SET_2.format(SET_), SET_ROWS)]
        assert doc(EVE, "a.pdf", "F-a") == [(WORK_SET_2.format(SET_BOTH), SET_ROWS)] and says(EVE, "then Q1 to Q5") == [(WORK_SET_2.format(SET_BOTH), SET_ROWS)]
        assert tap(EVE, "Next") == [(WORK_5, LAST_ROWS)] and photo(EVE, "P") == [(WORK_SET_5.format(SET_FILE), LAST_SET_ROWS)]
        assert tap(EVE, "Next") == [(f"{LIST_HEAD}\n{ON_2}{SET_BOTH}\n{ON_5}{SET_FILE}", LIST_ROWS)]
        sends(); a, b = [x["work"] for x in only()["lessons"][:2]]
        assert a["text"] == "Read p. 5\nthen Q1 to Q5" and [f["name"] for f in a["files"]] == ["a.pdf"] and [f["name"] for f in b["files"]] == ["photo 1.jpg"]
    with school(EVE, ROSA):
        to_work(); say(EVE, "Read p. 5"); assert tap(EVE, "Later for all the rest")[0][0] == f"{LIST_HEAD}\n{ON_2}{SET_}\n{ON_5}{NONE_YET}", "kept, the rest later"
    with school(EVE, ROSA):
        to_work(); say(EVE, "Read p. 5"); assert says(EVE, "/cancel") == [(NOTHING_SENT, None)] and mine() == [], "not pressed: nothing is sent, as before"

@t
def the_one_press_choices_still_work():
    with school(EVE, ROSA):
        to_work(); assert rows_now(EVE) == FIRST_ROWS, "no Next before anything is set"
        say(EVE, "x"); assert rows_now(EVE) == SET_ROWS
        tap(EVE, "Next"); assert rows_now(EVE) == LAST_ROWS and tap(EVE, "Same as before")[0][0].endswith(f"{ON_5}{SET_}")
    with school(EVE, ROSA): to_work(); assert tap(EVE, "Later, in the app") == [(WORK_5, [["Later, in the app"]])], "nothing set before: nothing to repeat"

@t
def a_second_text_is_added_and_a_second_link_replaces_the_first():
    with school(EVE, ROSA):
        to_work(); say(EVE, "https://x.example.org/a"); doc(EVE, "a.pdf", "F-a"); say(EVE, "Read p. 5")
        assert says(EVE, "https://x.example.org/b") == [(LINK_REPLACED, None), (WORK_SET_2.format("work set (text, link, 1 file)"), SET_ROWS)]
        assert says(EVE, "x" * 1995) == [("Keep the work under 2000 characters.", None), (WORK_SET_2.format("work set (text, link, 1 file)"), SET_ROWS)]
        tap(EVE, "Later for all the rest"); sends(); w = only()["lessons"][0]["work"]
        assert (w["text"], w["link"], [f["name"] for f in w["files"]]) == ("Read p. 5", "https://x.example.org/b", ["a.pdf"])

@t
def an_edit_of_any_piece_is_not_answered():
    def edit(text): return heard(EVE, lambda: hook(dict(update_id=next(_ids), edited_message=msg(text, CHATS[EVE])["message"])))
    with school(EVE, ROSA):
        to_work(); say(EVE, "Read p. 5"); say(EVE, "see https://x.example.org/a")
        assert edit("Read p. 5") == edit("see https://x.example.org/a") == [], "a link's preview, of either piece"
        assert edit("Read p. 6") == [(SEND_ONE, None), (WORK_SET_2.format(SET_), SET_ROWS)]

@t
def an_album_redraws_the_question_of_its_lesson():
    with school(EVE, ROSA):
        to_work(); assert photo(EVE, "A1", media_group_id="g1") == [(WORK_SET_2.format(SET_FILE), SET_ROWS)]; q_ = asking_of(EVE)["question"]
        assert photo(EVE, "A2", media_group_id="g1") == [] and (calls("editMessageText")[-1]["message_id"], calls("editMessageText")[-1]["text"]) == (q_, WORK_SET_2.format("work set (2 files)"))
        tap(EVE, "Next"); assert photo(EVE, "A3", media_group_id="g1") == [] and len(AK._work_of(asking_of(EVE), K2)["files"]) == 3 and asking_of(EVE)["ask"] == WORK_5, "after Next: its album's lesson still"

@t
def a_file_at_the_list_is_put_on_no_lesson():
    with school(EVE, ROSA):
        to_work(); tap(EVE, "Later, in the app"); doc(EVE, "a.pdf", "F-a"); tap(EVE, "Next")
        assert doc(EVE, "b.pdf", "F-b") == [(PRESS_ONE, None), (f"{LIST_HEAD}\n{ON_2}{NONE_YET}\n{ON_5}{SET_FILE}", LIST_ROWS)]
```

- [ ] **Step 2: Run them to see them fail** (`AK.NEXT` does not exist).
- [ ] **Step 3: Implement** the behaviour above.
- [ ] **Step 4: Update stage 4's Task 8 tests that walk the work by messages**, and only in this way: where a message used to move to the next lesson's
  question (`WORK_5`, `LAST_ROWS`, or the list), it now gets that lesson's `WORK_SET_*` with `SET_ROWS` or `LAST_SET_ROWS`, and a `tap(EVE, "Next")`
  follows to reach what came before; an album's later file now changes the question in place (`editMessageText`) where `tg.PRACTICE_LOG[n:] == []`
  was asserted. Known to need it: `a_whole_conversation_sends_an_absence`, `a_photo_and_a_document_are_attached`, `too_big_or_wrong_kind_is_named`
  (its "just within" line), `an_edit_that_says_what_is_held_is_not_answered`, `the_list_says_what_is_set` (its first case is now the fixed one: both
  files on lesson 1, say so in its comment), `the_files_of_an_album_belong_to_one_lesson`, and any other the run names. No other meaning of a test
  changes; list every test touched in the commit message.
- [ ] **Step 5: Run the suites.** Then once more `.venv/bin/python tests/test_relief_telegram.py` alone.
- [ ] **Step 6: Commit** `Relief: /relief keeps a lesson's work until Next`.

### Task 6: Finish: the guides, stage 4's plan and notes, the new notes

**Files:**
- Modify: `docs/DEPLOY.md` ("What leaves the server": the relief team row gains "that relief was asked for today: whose absence, whole day or
  which periods, and how many lessons wait for approval"; the `/relief` row says that a lesson takes several messages until Next; section 6 or
  "When Telegram is down": one sentence that Relief settings lists the messages other than reliefs that could not be sent since Monday; one
  sentence that a person unlinked because they blocked the bot sees why on their Link Telegram card), `README.md` (the relief team's line gains
  "a ping when relief is asked for today, once its picks wait for approval"; the `/relief` line; Relief settings' line), stage 4's plan's message table
  (rows `NEW` and, under the `/relief` copy, `WORK_SET`, `LINK_REPLACED`, the button `Next`).
- Modify: `docs/superpowers/plans/2026-11-22-relief-stage-4-notes.md`: "Open questions for the lead" each marked answered with the lead's answer and,
  for 1, 5, 6, 10 and 12, "built: 2026-11-23-relief-telegram-answers"; "What the final review left to the lead" first paragraph; "Known limits": the
  `/relief` two-lessons limit and "That unlinking writes no history entry" point to the new notes; "Follow-ups": the first is done (E), the second
  stays (answer 13: when Today is next touched).
- Create: `docs/superpowers/plans/2026-11-23-relief-telegram-answers-notes.md`: the lead's thirteen answers verbatim (as in this plan's Spec line),
  what each change gives, the rulings made during the build with their cost if wrong, the copy the lead should see (every new sentence of this plan,
  verbatim), known limits (below), open questions (below), and the checks (every suite with its count; the names check).
- Known limits to carry: A says nothing of an absence sent the evening before; its count is not rewritten; a ping dropped is never made again. C: a
  message meant for the next lesson but sent before Next lands on the one asked about (the question says which); a file sent at the list is on no
  lesson ("Please press one of the buttons."); one more tap a lesson with work. D: no history entry for the unlinking. E: blocked messages are removed
  from the queue (stage 4's P3), so they are not in the list: D's line says it to the person instead.
- Open questions to carry: D's history entry by "The app" (one condition in `_relief_entry`); whether the form should also say "{officer} will be told.";
  whether the evening-before request should ping at the report's start instead.

- [ ] **Step 1: Check what is untrue.** `grep -n "not pinged\|two lessons\|one message a lesson\|shown to nobody\|writes no history" README.md docs/DEPLOY.md docs/superpowers/plans/2026-11-22-relief-stage-4-*.md`; each hit is put right or pointed to the new notes.
- [ ] **Step 2: Write the docs and the notes** as listed.
- [ ] **Step 3: The names check**, counts only: the added lines and commit messages since ebdccb9 hold 0 real staff names (from the newest CTSS setup file),
  0 of the school's full name, 0 token or key shapes, 0 em-dashes (`git diff ebdccb9 | grep -c "—"` on added lines).
- [ ] **Step 4: Run every suite once more**, one at a time: all `tests/*.py` and all `tests/*.test.js`; write the counts in the new notes.
- [ ] **Step 5: Commit** `Relief: the lead's answers: guides, plan and notes`.

# Relief stage 4: Telegram — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The school's own Telegram bot tells the right person at the right moment — the relief teacher when their relief
is approved, the absent teacher when relief is planned for them, the reporting officer, the relief team about requests to
change, unacknowledged reliefs and the week — and people answer, and ask for relief, on Telegram with buttons, every
answer checked by the app exactly as on its own pages.

**Architecture:** Nothing is sent from the routes. A sweep (`relief/tell.py`) reads the absence records after every save
and every minute, works out which messages should exist, and queues each under a unique key in a small SQLite file; one
sender thread (`relief/outbox.py`) delivers them. Telegram calls the app back on one webhook address, checked by a secret
header; `relief/bot.py` links chats to people, runs buttons and typed answers through the same `cover.py` and
`absences.py` functions as the pages, and `relief/asking.py` holds the "ask for relief" conversation.

**Tech Stack:** Python 3 / Flask (one gunicorn worker, 8 threads), the standard library only for Telegram (`urllib`,
`sqlite3`), plain JavaScript, plain-assert test scripts. No new dependency.

**Spec:** `docs/superpowers/specs/2026-11-20-relief-module-design.md` (approved 20 Nov 2026): "Telegram", "Module 2 … 15-minute
report, Weekly summary", "Module 1 … Ask for relief, Acknowledge, set work or cancel", "Stages" item 4. Mockups: tabs 3, 4,
7, 8, 10 and 12 of `2026-11-20-relief-module-mockups.html`. Stage 3's notes: `2026-11-21-relief-stage-3-notes.md`.

**Branch:** `relief-stage-4`, cut from `relief-stage-3` (d693183, PR #88), with this plan committed first.

## Decisions taken in this plan (the lead may change any)

1. **Linking uses a one-time code from the app, not the personal code** (this differs from the design). A personal code
   is a permanent sign-in: sent to the bot it would stay in the chat for anyone who picks up the phone, and people who
   sign in with a password or Google have none. Instead: Relief → "Link Telegram" shows a button that opens the bot and a
   code (8 letters, 15 minutes, one use). Anything shaped like a code that is not a current link code is deleted from the chat, and the answer says to use the app
   (the bot never compares it with the real personal codes, so it cannot be used to guess one).
2. **A link is not tied to the account's sign-in number.** Giving somebody a new right raises that number for everyone
   in a bulk change, and tying links to it would silently stop everyone's messages. Instead every press is checked
   against the person's rights at that moment; a person switched off or gone from the timetable gets nothing; moving a
   link to another phone tells the old one; the settings page can unlink anyone.
3. **A message is sent once, or marked "may not have been sent".** If the app stops while a message is going out, it is
   not sent again by itself; the team sees "may not have been sent" and can press Remind.
4. **The absence reason is in one message only: the reporting officer's**, and then only its kind (Medical, Child sick,
   Course, Other), never the typed line. The design allows the reason to go to the officer, the team and management.
5. **Work text, links and files go to the relief teacher on Telegram**, as the design says. (Work files then pass
   through Telegram's servers: the lead may prefer "open in the app" for files.)
6. **The "not acknowledged" report runs from one hour before the day's first period** until every relief has started or
   is acknowledged, at round times (07:00, 07:15 …).
7. **Asking on Telegram offers the next ten school days**; a later date is asked in the app. Lessons shared with someone
   who is there are left out of the Telegram list, as "no relief needed"; the app can still ask for them.
8. **The bot works on one copy of the app.** "Connect the bot" on the relief settings page points Telegram at the
   address it was pressed on, so the token goes on ct-timetable only, never on the second Railway copy.
9. **Practice mode:** `TELEGRAM_BOT_TOKEN=practice` runs everything with no network, for local tries and the browser
   check.
10. **Exams' messages (duties moved, replacements)** are built by the exams stages with `outbox.queue`; this stage only
    provides it.

## Global Constraints

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
- The webhook route answers only a request whose `X-Telegram-Bot-Api-Secret-Token` equals `tg.hook_secret()` (compared
  with `hmac.compare_digest`), over 256 KB is refused, each `update_id` is acted on once, private chats only.
- Nothing network-bound runs under `absences._LOCK`. The webhook handler makes no model call.
- "Today" and "now" are school time (`lessons.today()`, `absences._now()`); lesson times come from `exams.days.bounds`.
- Tests are plain-assert scripts run as `.venv/bin/python tests/<name>.py`, `DATA_DIR` set to a fresh temp folder before
  `import app`; `RELIEF_JOBS` never set; `TELEGRAM_BOT_TOKEN` set to `practice` or a random made-up string, never real.
- Rights names used: `relief`, `relief.plan`, `relief.team`, `relief.save`. No new right name.
- Builders and reviewers: NEVER run `git stash`, `git stash pop` or `git checkout -- <file>`; `git stash list` unchanged
  after each task. In `static/*.js`, never a `//` comment in the middle of a long line; use `/* */`.
- Dates read "Tue 13 Oct"; periods "P9–P11"; times "10:40". The sentences below are used verbatim.
- Every commit ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`, written with a quoted heredoc.
- "Step 2–5 as before" in Tasks 5–8 means: run the new tests (they fail), implement, run the file with
  `test_relief_team`, `test_relief_requests`, `test_routes` and `smoke` (pass), commit.

Messages (exact text; `·` is U+00B7, `–` U+2013; `{periods}` as "P9–P11", `{time}` as "10:40–11:40", `{start}` as "10:40"):

| Name | Text |
|---|---|
| `RELIEF` | `🔔 Relief for you · {day}` / `{lesson} · {periods} · {time}` / `Room {room}` (left out when none) / `For {absent}` / `Work from {absent}: {text}` or `No work set yet: look in Reliefs I'm covering.` / `Link: {link}` (when set) / `Files: {n}, sent after this message.` (when any) |
| `PLANNED` | `📋 Relief planned for you` / `{days} · {whole day or periods}` / `Planned by {by}` / `{n} lessons will be covered.` / `Please acknowledge and set work for the relief teachers.` |
| `REMIND` | `⏰ Reminder: please acknowledge your relief for {days} and set work.` |
| `OFFICER` | `{absent} is away on {days} ({whole day or periods}): {kind}.` / `Relief is being arranged.` |
| `CANCELLED` | `❌ Cancelled by {by}: {absent}'s absence on {days}. Its reliefs are no longer needed.` |
| `GONE` | `❌ No longer needed: {lesson} {periods} ({start}) on {day}. You're free then.` |
| `MOVED` | `✔ The relief team has moved {lesson} {periods} on {day} to someone else. You're free then.` |
| `KEPT` | `The relief team has kept {lesson} {periods} on {day} with you.` |
| `ASK` | `↩ Request to change` / `{who} · {lesson} · {periods} ({start}) on {day}` / `“{why}”` / `New pick: {name}` / `{pick reason}`; nobody free: `Nobody else is free then: choose someone in the app.`; no pick after 2 minutes: `No new pick yet: open the app.` |
| `REPORT` | `⏰ {hh:mm} · Not yet acknowledged ({n})` / `• {who} · {lesson} {periods} · starts {start} · sent {hh:mm}` or `· not on Telegram` (each) / `Started without acknowledgement:` / `• {who} · {lesson} {periods} ({start})` (each, once) |
| `CLEAR` | `✅ {hh:mm} · All {n} reliefs for today are acknowledged.` or, when some never were, `No reliefs are waiting now: {k} started without acknowledgement.` |
| `SUMMARY` | `📊 Relief summary · {dates}` then the lines of mockup tab 10 (Task 7) |
| `HELLO` | `Linked: {name}. You'll get your reliefs here. Send /relief to ask for relief, /stop to unlink.` |
| `NOT_LINKED` | `This Telegram is not linked. Open Relief in the school's app, press Link Telegram and follow the link there.` |
| `BAD_CODE` | `That code is not right or has run out. Get a new one in the app. If it was your personal code, do not send it here: it opens the app. I have deleted your message.` |

| `MOVED_LINK` | `Your relief messages now go to another Telegram. If this was not you, tell the relief team.` |
| `TAKEN` | `This Telegram was linked to someone else before. Their relief messages no longer come here.` (a chat taken over by another person) |
| `STOPPED` | `Unlinked. Your relief messages stop here. To link again, open Relief in the school's app and press Link Telegram.` |
| `NOT_YOURS_BUTTON` | `This button is not for you.` |
| `OLD_BUTTON` | `This button is no longer active.` |
| `WHY_CHANGE` | `Say why in one line. Until the relief team replies, this relief is still yours.` |
| `WHY_CANCEL` | `Cancel this absence? Say why in one line.` |

Button labels: `✅ Acknowledge`, `↩ Request to change`, `✅ Acknowledge and set work`, `❌ Not needed: cancel`, `Approve {short name}`, `Remind them again`, `Open in the app`, `Open relief today`, `Open the full summary`.

## Review Focus

1. **The app restarts (or Railway swaps copies) while a message is being sent**: the item becomes `unsure`, is never sent
   again by itself, and the team sees "may not have been sent". (Task 3.)
2. **A relief is moved, cancelled or not needed between queueing and sending**: the message is dropped, not sent; a relief
   teacher already told gets `GONE` or `MOVED` once. (Tasks 3, 4.)
3. **A forged or replayed webhook call, a stranger's chat, a forwarded button**: wrong secret gives 403 and changes
   nothing; the same `update_id` acts once; an unlinked chat gets only `NOT_LINKED` (at most 5 replies in 10 minutes, then
   nothing); a button pressed from another chat gives `NOT_YOURS_BUTTON` and changes nothing. (Task 2, 5.)
4. **A teacher blocks the bot, or Telegram says 429**: blocked unlinks and shows "not on Telegram"; 429 waits
   `retry_after` and sends later, with no storm and no second copy. (Task 3.)
5. **A teacher presses Acknowledge twice, or after the relief has moved, or types a reply late**: the app's own sentence
   comes back, the buttons go, nothing is saved. (Task 5.)

---

## File structure

| File | What it is |
|---|---|
| `relief/tg.py` | the Bot API client: token, practice mode, `call`, `download`, the hook secret. One network function |
| `relief/tgdb.py` | the SQLite file `DATA/relief/telegram.db` and its tables; state; seen updates |
| `relief/links.py` | one-time codes, linking, who a chat is, who can be reached, their rights |
| `relief/outbox.py` | the queue, the sender, retries, `told` |
| `relief/words.py` | the words for a lesson, its periods, times and dates (moved from web.py) |
| `relief/tell.py` | message texts; what should be told now; `sweep`; `still_true` |
| `relief/bot.py` | an update in: commands, linking, buttons, typed answers |
| `relief/asking.py` | the `/relief` conversation |
| `relief/summary.py` | one week's numbers |
| `relief/report.py` | the acknowledgement report, all clear, weekly summary message |
| `relief/tgweb.py` | the blueprint: hook, link status and code, connect, unlink, remind, summary |
| `relief/web.py` | Today rows carry `told`; `_noted` and `init` take the person and via |
| `relief/fill.py` | `AFTER`: what runs after each tick and run |
| `app.py` | starts the sender and registers `AFTER` when `RELIEF_JOBS=on`; `_relief_entry` takes who and via |
| `static/relief-telegram.js` | the Link Telegram card; `static/relief-summary.js` the weekly page |
| `static/relief-today.js`, `relief-settings.js`, `relief.html`, `relief.js`, `history.js` | told status and Remind; the settings card; tabs; "Telegram" as a via |
| `tests/test_relief_telegram.py` | every server test of this stage |
| `docs/DEPLOY.md`, `README.md`, `.env.example` | making the bot, `TELEGRAM_BOT_TOKEN`, what leaves the server |

---

### Task 1: The client and the store

**Files:** Create `relief/tg.py`, `relief/tgdb.py`; Test `tests/test_relief_telegram.py`

**Interfaces:**
- Produces, `tg.py`: `token() -> str` (the env value, stripped; `""` when unset), `on() -> bool`, `practice() -> bool`
  (token == `"practice"`), `hook_secret() -> str` (hex HMAC-SHA256 of `"telegram-hook:" + token()` under env `SECRET_KEY`;
  `""` when `SECRET_KEY` is unset), `call(method, params=None, files=None, timeout=15) -> dict(ok, result, kind,
  retry_after)`, never raising: `kind` None on ok, else `"blocked"` (HTTP 403), `"slow"` (429; `retry_after` from
  `parameters`, default 5), `"refused"` (other 4xx), `"network"` (5xx, or never connected), `"unsure"` (the request went
  out and no answer came: a read timeout or reset). `files` is a list of `(field, filename, bytes)` sent as multipart.
  `download(file_id, limit) -> bytes | None` (getFile then the file, None when larger than `limit` or failed).
  Practice answers: `getMe` → `dict(username="practice_bot", first_name="Practice")`, anything else → ok with
  `dict(message_id=<counter>)`, kept in `PRACTICE_LOG` (list) for tests.
  `_send(url, data, headers, timeout) -> (status, body bytes)` is the only network function (urllib).
- Produces, `tgdb.py`: `PATH`; `db() -> context manager` giving a connection (`timeout=10`, WAL, row factory, commits on
  exit); `get_state(k, default=None)`, `set_state(k, v)` (JSON); `first_time(update_id) -> bool` (inserts; keeps the last
  1000). Tables: `links(name PRIMARY KEY, chat INTEGER UNIQUE NOT NULL, handle, at)`, `codes(hash PRIMARY KEY, name, until
  REAL)`, `outbox(key PRIMARY KEY, name, chat, kind, text, buttons, files, ref, state, at, sent_at, message_id, tries,
  next_at REAL)`, `buttons(token PRIMARY KEY, name, what, id, ckey, who, extra, until REAL)`, `talks(chat PRIMARY KEY,
  kind, data, until REAL)`, `updates(id INTEGER PRIMARY KEY)`, `state(k PRIMARY KEY, v)`.

- [ ] **Step 1: Write the failing tests** (header as `tests/test_relief_team.py`; `tg._send = never` at import):
  `without_a_token_it_is_off_and_calls_nothing` (token unset: `on()` False, `call("getMe")` → `kind == "refused"`, `_send`
  not called), `the_hook_secret_depends_on_the_token_and_the_key` (two tokens differ, two keys differ, 64 hex chars, `""`
  without `SECRET_KEY`), `every_failure_becomes_its_kind` (`_send` returning 403, 429 with and without `retry_after`, 400,
  502, raising `URLError`, raising `TimeoutError`, raising `ConnectionResetError` → blocked, slow, refused, network,
  network, unsure, unsure), `no_failure_text_is_logged` (`_send` raising an exception whose text holds the token; the log
  records hold the kind and nothing else), `files_go_as_multipart` (the body carries each filename and byte string),
  `practice_never_reaches_the_network`, `state_and_seen_updates_survive_a_reopen` (`first_time(5)` True then False; a
  fresh connection still False; only the last 1000 kept).
- [ ] **Step 2: Run** `.venv/bin/python tests/test_relief_telegram.py` — fails, modules missing.
- [ ] **Step 3: Implement** both files.
- [ ] **Step 4: Run** the file — pass.
- [ ] **Step 5: Commit** "Relief: the Telegram client and its store".

### Task 2: Linking a person, the hook, connect

**Files:** Create `relief/links.py`, `relief/bot.py` (linking part), `relief/tgweb.py`; Modify `app.py`, `relief/web.py`
(`_noted(…, by=None)`, `_relief_entry` who/via), `static/history.js` (`VIA.telegram = "Telegram"`),
`tests/test_routes.py`; Test as Task 1.

**Interfaces:**
- Consumes: `tg`, `tgdb`, `access.ALPHABET`, `access.norm`, `accounts.people.find`, `accounts.rights.rights`.
- Produces, `links.py`: `CODE_MINUTES = 15`; `new_code(name) -> dict(code "XXXX-XXXX", until)` (replaces that name's earlier
  codes; only a SHA-256 hash is stored); `use(code, chat, handle) -> str | None` (the name; one use; expiry);
  `chat_of(name) -> int | None` and `name_of(chat) -> str | None`, both only while the person is found
  (`accounts.people.find`, or nothing published) and not `off`; `person(chat) -> dict | None`; `rights_of(chat) ->
  frozenset`; `link(name, chat, handle) -> int | None` (the replaced chat, when the link moved), `unlink(name) -> int |
  None`, `unlink_chat(chat) -> str | None`, `linked() -> {name: dict(handle, at)}`, `reachable(pub=None) -> {name: chat}` (all
  at once, reading the accounts once: the sweep and Today use it, never `chat_of` in a loop); `tries` is an
  `access.Limiter(n=5, window=600)` keyed by `"tg:" + chat`.
- Produces, `bot.py`: `handle(update: dict) -> None`, never raising; `/start <code>`, `/start`, a bare code, `/stop`,
  `/help`; text whose `access.norm` is 8 characters of `access.ALPHABET` (linked or not) is tried as a link code
  (`links.use`); when it is not one, the message is deleted (`deleteMessage`) and answered `BAD_CODE`, one `tries.fail`;
  a chat over `tries` gets no answer at all. An unlinked chat otherwise → `NOT_LINKED`, one `tries.fail` each.
  `callback_query` updates are ignored until Task 5.
  Replies go through `reply(chat, text, buttons=None)` = `tg.call("sendMessage", …, disable_web_page_preview, timeout=8)`.
- Produces, `tgweb.py` (blueprint `relief_tg`, `init(has, me, need, note)`): `POST /telegram/hook` (the only unguarded
  route: 404 when `not tg.on()` or not connected, 403 on a wrong secret, 413 over 256 KB (read from the stream, never more than one byte past it), else `bot.handle` and 200);
  `GET /api/relief/telegram` → `dict(on, connected, bot, linked, handle, since)` (right `relief`);
  `POST /api/relief/telegram/code` → `dict(code, url, until)` (`url = https://t.me/{bot}?start={code}`; 409
  `"Telegram is not connected yet."` when not); `DELETE /api/relief/telegram/link`; `GET /api/relief/telegram/admin` →
  `dict(token_set, practice, connected, bot, base, at, linked: [{name, handle, at}], not_linked: [names], people)`,
  `POST /api/relief/telegram/connect` (body none; uses `request.host_url` as the base, refused unless https or
  practice, and unless `SECRET_KEY` is set; `getMe`, `setWebhook(url=base/telegram/hook, secret_token=hook_secret(),
  allowed_updates=["message","callback_query"], max_connections=4, drop_pending_updates=True)`, `setMyCommands` of
  `relief`, `stop`, `help`; saves `state.bot = dict(username, base, at)`), `POST …/disconnect` (`deleteWebhook`),
  `POST …/unlink {name}`; all four `relief.save`. Link, move and unlink write a history entry ("Telegram linked",
  "Telegram unlinked") by the person (via `telegram` from the bot, else the signed-in person).
- `app.py`: `_relief_entry(what, text, absence=None, who=None, via=None)`; registers `relief_tg`; `tests/test_routes.py`:
  `walked()` skips `/telegram/hook` by name, the new guarded routes are in `GUARDS`, and a new test pins that the hook
  refuses every kind of session without the header.

- [ ] **Step 1: Write the failing tests**: `a_code_links_once_and_then_is_gone` (a second use → None; an expired one →
  None; a new code replaces the earlier), `linking_again_moves_it_and_tells_the_old_chat` (old chat gets `MOVED_LINK`),
  `a_chat_links_one_person_and_a_person_one_chat`, `an_off_or_gone_person_is_not_reachable` (`chat_of` None),
  `rights_from_telegram_are_the_codes_rights` (an admin by password has no `admin` from Telegram; HOD has
  `relief.plan`), `the_hook_needs_the_secret` (wrong → 403; missing → 403; right → 200; body over 256 KB → 413),
  `the_same_update_acts_once`, `only_private_chats_are_answered` (a group → nothing sent), `a_stranger_gets_five_replies`
  (then none in 10 minutes), `a_code_that_is_not_a_link_code_is_deleted` (a real personal code and a made-up one give the same answer, `BAD_CODE`,
  with `deleteMessage` called and nothing linked), `the_code_route_needs_a_person_and_a_connection`, `connect_saves_the_bot_and_points_the_hook_here` (practice;
  a http base refused unless practice; `SECRET_KEY` unset refused), `admin_lists_who_is_not_linked`,
  `the_link_and_unlink_are_in_the_history` (via `telegram`, no chat id, no code).
- [ ] **Step 2: Run** — fails. **Step 3: Implement.** **Step 4: Run** the file, `tests/test_routes.py`,
  `tests/smoke.py` — pass. **Step 5: Commit** "Relief: link Telegram, the hook and connecting the bot".

### Task 3: The outbox and the sender

**Files:** Create `relief/outbox.py`; Modify `app.py` (start the sender when `RELIEF_JOBS=on` and `tg.on()`); Test as
Task 1.

**Interfaces:**
- Produces: `queue(key, name, text, *, kind, buttons=(), files=(), ref=None) -> bool` (True when new; False when the key
  exists or `links.chat_of(name)` is None); `buttons`: rows of `dict(text, what, id, ckey, who, extra)` or `dict(text,
  url)`; `files`: `[dict(id, file, name)]`; `ref` is JSON, given to `still_true`.
  States `queued`, `sending`, `sent`, `failed`, `unsure`, `dropped`. `send_due(now=None, limit=50) -> dict(sent,
  waiting)`: one run at a time (non-blocking lock); for each due item (`queued`, `next_at <= now`, oldest first): skip
  as `dropped` when `VALID(item)` (default True; `tell` sets it to `still_true` at import) is False; mark `sending` and commit; register
  its buttons (`buttons` table, 16-character tokens, `until` 30 days after queueing; what a press may do is decided by
  the state then); cut text over 4000 characters at a line end with `…and more in the app.`; `tg.call`; `ok` →
  `sent`, `sent_at`, `message_id`, then each file through `sendDocument` (failure marks the item sent with
  `files_failed`, shown to the team); `slow` → `queued`, `next_at = now + retry_after`; `network` → `queued`,
  `next_at` by tries 5 s, 30 s, 2 min, 10 min, 30 min, then `failed`; `blocked` → `links.unlink(name)` and the item is removed (a person who links again gets what is still to come);
  `refused` → `failed`; `unsure` → `unsure`. `recover()` (at start): every `sending` → `unsure`. `told(key) -> dict(state,
  at) | None`, `told_for(prefix) -> {key: dict(state, at, name, ref)}` (compared with `substr`, never `LIKE`: keys hold any character). `start()` /
  `wake()`: one daemon thread `relief-telegram` calling `send_due` when woken or every 5 s, errors logged by kind.
- [ ] **Step 1: Write the failing tests**: `a_key_queues_once_and_only_for_a_linked_person`,
  `a_sent_message_is_not_sent_again` (second `send_due` sends nothing), `a_restart_mid_send_is_unsure_not_resent`
  (mark `sending`, `recover()`, `send_due` sends nothing, `told` says `unsure`), `slow_and_network_wait_and_retry` (the
  clock moved by hand; tries 1..5 then `failed`), `a_blocked_chat_is_unlinked`, `an_item_no_longer_true_is_dropped`,
  `buttons_carry_a_token_under_64_bytes`, `files_follow_the_message_and_a_failed_file_is_noted`,
  `two_runs_never_send_the_same_item` (two threads, one `CALL` that sleeps: one send).
- [ ] **Step 2: Run** — fails. **Step 3: Implement.** **Step 4: Run** — pass. **Step 5: Commit** "Relief: the message
  queue and its sender".

### Task 4: What to tell, and telling it

**Files:** Create `relief/tell.py`; Create `relief/words.py` (below); Modify `relief/fill.py` (`AFTER` list called after `run`, `_queued` and `tick`,
  once `_busy` is released, each in its own try), `relief/web.py` (after each save: `_tell_soon()` beside `_soon`, a thread unless `SYNC`), `app.py`
(registers `AFTER`); Test as Task 1.

**Interfaces:**
- Produces, `words.py` (moved from `relief/web.py`, which keeps its private names as aliases): `class_group(x)`,
  `periods_text(c)`, `times(pub, x, c)`, `day(iso) -> "Tue 13 Oct"`, `days(record)`, `away(record)` ("whole day" or
  "P1–P9"); `fill.nudge(r, pub, settings, now, today)` (moved from `web._nudge`, which calls it). So `tell` imports neither
  `web` nor `bot`: `web` → `tell`, `bot` and `asking` → `web`, `report` → `tell`.
- Produces, `tell.py`: `due(pub, settings, records, now, reach, told, since) -> list[dict(key, name, kind, text, buttons, files,
  ref)]` (pure: `reach` is `links.reachable()`, `told` is `outbox.told_for("relief:")`, `since` is `state.bot.at`; only
  people reached are listed; a message to several people ends its key with `:{name}`), built from them alone:
  `planned:{id}` (teacher; `how == "planned"`, `by != teacher`, not acknowledged, not cancelled, its last date ≥ today),
  `remind:{id}` (teacher; `_nudge` true and the absence `at` before that remind time), `officer:{id}` (reporting officer ≠
  teacher and ≠ `by`, not cancelled, last date ≥ today, absence `at` ≥ `since`; the same for `planned`), `relief:{absent}:{ckey}:{approved.at}` (state `approved`, lesson not over; `absent` is the absent teacher's name, not
  the absence id: exams' takeover moves an approved cover into another absence, which must be neither gone nor sent
  again), `ask:{id}:{ckey}:{change.at}:{name}` (each team member; when the new pick is in, or 2 minutes after the request
  without one, when `free.free_then` says whether it reads `Nobody else is free then…` or `No new pick yet…`; a pick that
  arrives after that goes once more as `askpick:{id}:{ckey}:{change.at}:{name}` with the Approve button), `gone:{relief key}` and `moved:{relief key}` (a base relief key told `sent` or `unsure` whose cover is no longer approved to that person: `moved` when the cover is
  approved to another person, else `gone`, also when the cover key is no longer there; the same person approved again is
  neither; lesson not over), `kept:{id}:{ckey}:{history at}` (the relief teacher; from history `kept`), `cancelled:{id}:{name}` (team members and the planner, not the canceller; `cancelled.at` ≥ `since` and the absence was
  still to come). `sweep(now=None) -> int` (reads published,
  settings, records; queues; `wake`s the sender; 0 when `not tg.on()` or not connected). `still_true(item) -> bool`
  (relief: still approved to them with that `approved.at` and the lesson not over; planned/remind/officer: not cancelled
  and still to come; others true). `soon()` (a daemon thread unless `SYNC`).
- A relief message's `ref` holds `dict(id, absent, ckey, approved_at, who, lesson, periods, start, day, date, ends)` (`lesson`
  and the words as sent, `ends` the lesson's end as an ISO time), so `gone`, `moved` and reminders can be written when the
  cover, or its absence, is no longer there (exams' `relief_links.sync` takes a lesson off a backup outside our routes).
- The texts are built by functions named after the table above (`relief_text(...)`, `planned_text(...)` …), each tested
  against its exact text.
- [ ] **Step 1: Write the failing tests**, one per key kind and each rule above, among them: `approve_queues_the_relief_once`
  (approve in the app → one `relief:` message with both buttons; a second sweep queues nothing), `nothing_goes_before_approval`
  (waiting pick → no message to anyone but the team), `a_moved_relief_tells_the_first_teacher_once` (and the second gets
  theirs), `cancel_tells_the_team_the_planner_and_the_told`, `a_person_who_links_later_gets_what_is_still_to_come` and
  `nothing_old_is_sent_when_the_bot_first_connects` (officer and planned older than `bot.at`; lessons over),
  `an_ask_waits_for_the_pick_then_goes`, `kept_tells_the_asker`, `the_reminder_goes_once_after_its_time` (and never when the
  absence was sent after that time), `the_officer_message_has_only_the_kind_of_reason` (Other's typed line absent),
  `no_message_carries_remarks_or_the_typed_reason` (distinctive words in every field, none in any text), `the_sweep_is_quick`
  (200 records, under 2 seconds).
- [ ] **Step 2: Run** — fails. **Step 3: Implement.** **Step 4: Run** the file, `tests/test_relief_team.py`,
  `tests/test_relief_requests.py`, `tests/smoke.py` — pass. **Step 5: Commit** "Relief: telling people on Telegram".

### Task 5: Answering on Telegram

**Files:** Modify `relief/bot.py`, `relief/tell.py` (buttons), `relief/web.py` (`_noted` by/via used); Test as Task 1.

**Interfaces:**
- Consumes: `cover.acknowledge`, `cover.ask_change`, `cover.approve`, `absences.cancel`, `links.*`, `outbox`. A button whose
  stored absence id no longer holds the cover finds it by absent teacher and cover key (`extra`) in the records not
  cancelled, and while a talk waits for a line, code-shaped text is the answer, never a code.
- Produces in `bot.py`: button kinds `ack`, `change` (asks `WHY_CHANGE`, a talk of kind `change`), `cancel` (asks
  `WHY_CANCEL`, a talk of kind `cancel`), `approve` (needs `relief.team`; uses the name the message showed, so
  `PICK_CHANGED` comes back when it moved on), `remind`, and `url` (opened by Telegram, never sent here). Every press:
  the token is looked up (`OLD_BUTTON` when gone or expired), the chat's person must be the button's `name`
  (`NOT_YOURS_BUTTON`), the action runs, the history entry is by the person via `telegram`, `fill.soon` and `tell.soon`
  are asked, the press is answered (`answerCallbackQuery`, at most 200 characters) and the message's buttons are
  replaced by a line such as `✅ Acknowledged 07:46.`; a refusal answers with its own sentence and leaves the buttons.
  A typed answer to a talk (`why` 1–200 characters after strip, else the question again) ends it; `/cancel` ends it.
- [ ] **Step 1: Write the failing tests**: `pressing_acknowledge_acknowledges_and_says_so`, `pressing_twice_says_the_same` (the second answers the same line; nothing is saved and no second history entry), `a_moved_relief_pressed_late_says_so`,
  `a_forwarded_button_is_refused_for_another_chat`, `request_to_change_asks_why_then_sends`, `cancel_asks_why_then_cancels`,
  `approve_needs_the_team_right_and_the_pick_shown` (a teacher without `relief.team` refused; `PICK_CHANGED` when the pick
  moved), `a_button_expires`, `a_rights_change_between_is_honoured` (a team member who lost the extra is refused),
  `the_history_names_the_person_and_telegram` (never the why, never a chat id).
- [ ] **Step 2–5** as before; commit "Relief: answering a relief on Telegram".

### Task 6: Remind, the not-acknowledged report and all clear

**Files:** Create `relief/report.py`; Modify `relief/tgweb.py` (`POST
/api/relief/today/remind`), `relief/web.py` (`today()` rows gain `told: dict(state, at) | None` and `linked`),
`relief/fill.py` (`AFTER` calls `report.tick`); Test as Task 1.

**Interfaces:**
- Produces: `report.tick(now=None) -> list[str]` (the keys queued, for tests): at each `report_every`-minute mark of the
  school day (minutes from midnight a multiple of it), from one hour before the first period (`exams.days.bounds`) until
  every approved relief of that date has started or been acknowledged: to each linked team member, `report:{date}:{hhmm}:
  {name}` with `REPORT` when at least one relief is not acknowledged and has not been listed as started, or one is newly
  started; a relief started unacknowledged is listed under "Started without acknowledgement" exactly once (state
  `started:{relief key}`); once at least one report went and none waits, `clear:{date}:{n}:{name}` with `CLEAR` once per
  time of waiting (a new unacknowledged relief starts the reports again). Nothing on a date with no reliefs. The mark is the last one at or before now (state `report_last:{date}` keeps it, so a
  tick a little late, or after a restart, still sends it once); the time written in the text is now. `report.remind(date,
  covers, by, now=None) -> dict(sent, skipped)` (it queues with `outbox.queue`): each approved, not acknowledged relief of `covers` whose last told is
  older than 5 minutes gets `…:r{n}` (next number, same buttons); others skipped with the sentence "Reminded at {hh:mm}:
  wait a few minutes.". The Telegram button "Remind them again" calls the same function with the covers in that report.
  Route: `POST /api/relief/today/remind {date, covers: [{id, ckey}]}` (relief.team).
- [ ] **Step 1: Write the failing tests** with the clock moved by hand: `the_report_goes_at_its_marks_and_once_each`,
  `not_before_an_hour_before_the_first_period`, `a_started_relief_is_listed_once_then_dropped`, `all_clear_goes_once_and_again_after_new_waiting`,
  `nothing_is_sent_when_nothing_waits`, `the_report_goes_to_team_members_only`, `not_on_telegram_is_said_in_the_report`,
  `remind_resends_once_every_five_minutes`, `today_rows_say_when_it_was_told_and_if_not_on_telegram`.
- [ ] **Step 2–5** as before; commit "Relief: the not-acknowledged report, all clear and Remind".

### Task 7: The weekly summary

**Files:** Create `relief/summary.py`, `static/relief-summary.js`; Modify `relief/tgweb.py` (`GET /api/relief/summary?week=`),
`relief/report.py` (weekly part of `tick`), `static/relief.html`, `static/relief.js` (`TABS` gains `["summary", me => !!me.can_team]`); Test as Task 1.

**Interfaces:**
- Produces: `summary.week(pub, settings, records, monday, now) -> dict(start, end, periods, absences, fat_periods,
  fat_percent, ahead, on_day, on_time, late, never, waiting, asked, moved, kept, top: [(name, periods)] (first 3), by_dept:
  [(dept, periods)], by_day: {Mon..Fri: periods}, rows: [dict(date, lesson, absent, relief, ack: "07:15" | "late 09:30" |
  "never" | "waiting")])`. A relief counts when its cover is in `web.APPROVED`, dated that week, its absence not
  cancelled; periods are summed. `ahead` when `approved.at` is before the lesson's date, else `on_day`. `on_time`: `ack.at`
  at or before the lesson's start; `late`: after; `never`: none and the lesson is over; `waiting`: none and not over.
  `asked`: covers with an "asked to change" in history that week; `moved`: of those, another name relieved it after;
  `kept`: the rest that were settled. `by_dept`: the absent teacher's first department. `weeks` with no relief give zeros.
  Message `SUMMARY` (the lines of mockup tab 10: periods and absences; "Flexi Adjuncts covered {n} ({p}%)"; "Planned ahead {a}
  · arranged on the day {b}"; "Acknowledged on time {x} · late {y} · never {z}"; "Asked to change {n} ({m} moved)"; "Most relief
  this week: …"; "By department of the absent teacher: …" first three and "others {k}") at `weekly_day` `weekly_at` to each
  linked team member, key `weekly:{monday}:{name}`, once, only when the week had at least one relief, with "Open the full
  summary". The page (team): week choice (‹ ›, this week by default), counters, the two bars (by day), the full list.
- [ ] **Step 1: Write the failing tests**: `the_numbers_add_up` (a hand-made week with each case, every number asserted),
  `a_cancelled_absence_does_not_count`, `ahead_and_on_the_day_by_approval_date`, `ack_on_time_late_never_waiting`,
  `the_message_goes_once_at_its_time_and_not_without_reliefs`, `the_summary_route_needs_the_team`, `a_split_lesson_counts_its_parts`.
- [ ] **Step 2–5** as before (`node --check` the script); commit "Relief: the weekly summary".

### Task 8: Asking for relief on Telegram

**Files:** Create `relief/asking.py`; Modify `relief/bot.py` (`/relief`, files and photos in a talk), `relief/absences.py`
(`set_via`), `static/relief-inbox.js` (how it was asked); Test as Task 1.

**Interfaces:**
- Produces: `start(chat, me)`, `step(chat, me, text=None, press=None, file=None) -> None` over a talk of kind `ask` (30 minutes;
  each step answers with the next question and buttons; `/cancel` ends it). Steps, in order, as mockup tab 3: day (Today,
  Tomorrow, Several days, Another day: the next 10 school days as buttons, ticked with ✓, then Done; `/relief` on a
  calendar with no terms answers `lessons.NO_CALENDAR`), whole day or some periods (From and To as P buttons with their
  times), reason (the four, Other asks one line), officer ("Your reporting officer is {name}. Right?" Yes / Someone
  else: type part of a name, up to 8 matches as buttons; the officer of that person's latest absence is offered), work per lesson (type text, send a file or a photo, "Same as before", "Later, in the app"),
  then a list of the lessons with Send / Start again. Send calls `absences.new(data, pub, me, "asked", may_choose=False)`
  (its sentences answer the person), marks the record `via="telegram"` (`absences.set_via(id, "telegram")`, under the
  lock; What's in shows "asked on Telegram"), then saves each file with `files.save` and `absences.set_work` (a file that cannot be
  saved is named: "{name} could not be attached: add it in the app."), writes the history entry, asks `fill.soon` and
  `tell.soon`, and answers `✅ Sent to the relief team: {n} lessons, work set for {m}. {officer} will be told.`
- [ ] **Step 1: Write the failing tests**: `an_absence_asked_on_telegram_is_marked_so`, `a_whole_conversation_sends_an_absence` (the saved record equals what the app's
  form would make: same teacher, dates, periods, reason, officer, work, files), `several_days_and_some_periods`,
  `other_asks_a_line_and_refuses_an_empty_one`, `an_overlap_is_refused_with_the_apps_sentence`,
  `a_shared_lesson_is_left_out`, `a_photo_and_a_document_are_attached`, `too_big_or_wrong_kind_is_named`, `a_talk_ends_after_thirty_minutes_and_on_cancel`,
  `an_unlinked_chat_cannot_ask`, `the_last_officer_is_offered`.
- [ ] **Step 2–5** as before; commit "Relief: asking for relief on Telegram".

### Task 9: The pages

**Files:** Create `static/relief-telegram.js`; Modify `static/relief.html`, `relief.js` (the Link Telegram card on My absences),
`static/relief-today.js` (told: "Sent 07:20", "may not have been sent", "not on Telegram", Remind per row and "Remind all not
acknowledged"), `static/relief-settings.js` (the Telegram card), `static/relief-settings.html`.

- **Link card** (everyone with `relief`): not connected → nothing shown; connected, not linked → "Link Telegram" button →
  the open-bot link, the code and "The code runs out in 15 minutes."; linked → "Linked as @handle since {date}", Unlink.
- **Today:** a row in `approved` shows `told` ("Sent {hh:mm}"; "May not have been sent: remind them"; "Not on Telegram: they
  see it in Reliefs I'm covering"), a Remind button; "Remind all not acknowledged" beside Approve all.
- **Settings card** (relief.save): the token not set ("Ask the lead to add TELEGRAM_BOT_TOKEN in Railway"), practice mode
  said plainly, Connect the bot / Disconnect, who is linked with Unlink, who is not linked, a line on one copy only.
- [ ] **Step 1:** Build; every text through `esc`; `node --check`.
- [ ] **Step 2:** Browser check in practice mode on the made-up sample (controller's temporary launch entry,
  `TELEGRAM_BOT_TOKEN=practice`, a small script posting webhook updates with the hook secret): connect, link a teacher
  with the code, approve a relief and see "Sent", press Acknowledge through the hook and see it on Today, ask to change,
  approve the new pick, remind, the not-acknowledged report, the weekly page, phone width. Screenshots of made-up data.
- [ ] **Step 3: Commit** "Relief: the Telegram pages".

### Task 10: Finish

- [ ] `docs/DEPLOY.md`: making the bot with BotFather in plain steps, `TELEGRAM_BOT_TOKEN` on ct-timetable only, pressing
  Connect, what leaves the server (Telegram gets the messages above, and work files when attached), the second copy.
  `README.md` Relief section; `.env.example` gains `TELEGRAM_BOT_TOKEN=`.
- [ ] Every suite, `.venv/bin/python tests/*.py` one by one, `node tests/*.test.js`, `--full` runs alone.
- [ ] The school's real published timetable, numbers only, scratch deleted: made-up absences for the five teachers with
  the most lessons, all approved; `tell.due` time with 200 records and 60 reliefs, the sweep's time, number of messages.
- [ ] No real staff name, the school's full name, or any token shape in the branch's commits.
- [ ] Notes `docs/superpowers/plans/2026-11-22-relief-stage-4-notes.md` (rulings, checks, what exams uses: `outbox.queue`,
  and the open questions).

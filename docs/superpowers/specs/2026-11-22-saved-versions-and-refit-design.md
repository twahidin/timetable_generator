# Saved versions and re-fit on step 8: design

Date: 2026-11-22. Status: written for the lead's approval. Mockups (made-up names, approved by the lead as "Looks right"):
`2026-11-22-saved-versions-and-refit-mockups.html` beside this file (screens 1 Saved versions, 2 Compare, 3 Re-fit).

## Why

The committee gets its timetable from an outside agent, uploads it on step 8, fixes it there and publishes it. Two things
are missing.

1. **Keeping more than one timetable.** Step 8 holds one draft. The lead wants to keep an edited timetable, ask the agent
   for another, upload it and compare the two, without losing the first. Today the only way is Download the draft (.sqlite)
   on step 9 and uploading it again later, which brings the lessons back but not the list of changes or Undo.
2. **Small setup changes after the timetable is made.** A teacher changes on step 5, a subject gains a period, a teacher
   becomes unavailable on a day. The lead does not want to regenerate the whole timetable, and does not want to do many
   swaps by hand. In the lead's words: help "shift the lessons while keeping the overall structure intact", and say "these
   are the changes that will be made before it apply the changes". Step 8 already shows the red line "Made from
   configuration v489; the setup is now v524. Changes since then are not in this timetable." and lists the differences as
   warnings; it settles them one warning at a time (Ways to settle this, Ask about this, Ask in words).

## Goals

- Save the draft as a named version; list the versions; open one as the draft with its own list of changes and Undo;
  download or delete one. Nothing is ever lost: replacing the draft (an upload, opening a version, a re-fit) first keeps
  the draft as a version.
- Compare any two of: the versions, the draft, the published timetable. Totals, then one class, teacher or room side by
  side with what differs marked, then the list of differences (also as an Excel download).
- Re-fit: one button works out, for everything on the draft that no longer fits the setup, the fewest lesson changes that
  fit it, shows them as a list grouped by what caused them, and changes nothing until the lead presses Apply. Apply makes
  them as one change; Undo takes the whole re-fit back.

## The lead's rules for the re-fit (decided by the lead)

- **Bands stay where they are.** A band's lessons keep their day and period.
- **Each class's day pattern stays the same.** A lesson moves only to another period of the same day.
- **When a change forces another day** (for example a teacher who is now away every Friday), the lesson moves to another
  day and the list flags it ("another day").
- **Another day as the last resort** (added by the lead on 23 November 2026, "Yes, allow it"): when nothing works on a
  lesson's own day, it may move to another day, or change places with a lesson of another day, flagged the same way.
  Same-day answers always come first.
- The finding is done by **the app's own search** (approach A below), not by the solver and not by a language model.
- **Typed rules (T1, T2… on step 6): allow and flag.** The app cannot check them, so the re-fit may move lessons a typed
  rule covers. Every such change says which rule to check again, the totals count them, and Apply reopens any of those
  rules the committee had answered "met". Between two equally short lists, the one touching fewer typed rules wins.

## Non-goals

- Generating a timetable in the app, or running the solver on the server (the November decision stands; see Approaches).
- Settling Prefer warnings that are already open (the re-fit only must not add to them).
- Placing lessons that wait in Not placed (the board and the helper do that today). A later stage may add it.
- Versions of the setup (the setup has its own restore points and history).
- Merging two versions, or comparing more than two at once.
- Any language model in either feature.

## Anti-goals (a failure even if it works)

- The re-fit changes anything before Apply.
- The re-fit moves a band, or moves a lesson to another day without the flag.
- The re-fit's list contains a change that step 8's own checks then call a clash or a broken Must rule (the typed rules'
  "check it again" excepted: those are allowed, flagged on the change and counted).
- Any action loses a draft the lead had (an upload, Open, a re-fit) without keeping it as a version first.
- A long, opaque list: every change must say why it is there.

## Approaches considered (for the re-fit)

- **A · The app's own search (chosen by the lead).** Extend the helper (`helper.py`, which today finds up to three ways of
  one or two fixes for one warning, each judged by `fixes.judge`) into a search over all the open differences at once,
  with longer chains of moves and swaps, held to the lead's rules. Seconds, judged by exactly the same checks as step 8,
  speaks in the same sentences. Limit: a tight knot may be beyond a short search and go to "Needs you".
- **B · A repair run of the solver.** `ttgen/solver.py` already has `previous=` (start from a timetable and charge for
  every lesson moved) and `pins=`. It finds the true fewest moves and untangles knots, but brings solving back onto the
  server, which the committee moved outside in November because it was slow; its run time on the real school is unknown.
  Not chosen; it may come later as a "Try harder" button if A leaves too much under "Needs you" on the real timetable.
- **C · A language model proposes moves, the app checks them.** Not chosen: unreliable at this search (many proposals
  would fail the checks), costly per run, and it would send timetable data out.

Saved versions has one sensible way: a version is a copy of the draft's folder.

## How it works today (what this builds on)

- The draft lives in `DATA_DIR/draft/`: `setup.xlsx` (absent for a database that holds its setup), `timetable.<ext>`,
  `decisions.json` (answers to warnings: step5, open, met) and `meta.json` (`source`, `uploaded_at`, `upload_id`,
  `fixes` (the list of changes made in the app, each with `at`, `text`, and a `batch` id when made together),
  `published_fixes`, `school`, `config_id`, `open`, `critical`). `draft.save()` replaces the folder through `.new`/`.old`.
- The draft is rebuilt by reading the file and applying `fixes` in order (`fixes.editor`), then checked against the setup
  as it is now (`draft._build`, `ttgen.verify`, including `verify.deployment`: keys `dep:{key}:missing`, `:teachers`,
  `:periods`, `:venue`, `:half`, `:extra`).
- `draft.fix_many` writes one or two fixes as one batch (each judged on what the earlier ones leave, via `helper.chain`);
  `draft.undo` drops the last fix and every fix of its batch; `draft.preview` shows one or two fixes on the class weeks
  without writing. Fix kinds: move, swap, teacher, trade, room, add, delete, lift, place.
- Uploading over a draft with unpublished fixes is refused (`UnpublishedFixes`) and the page asks "Replace the draft?".
- Step 8 routes need the `committee` right; draft actions are written to the history (`_draft_entry` in `app.py`).
- The published timetable is `store.published()["model"]` (its lessons have the fixes applied).

## Feature 1: Saved versions

**Where:** a **Versions (n)** button on step 8 (in the upload card's head, beside "Upload a timetable"), opening a pop-out
(screen 1 of the mockups).

**A version** is a copy of the draft's folder at a moment, plus `version.json`: `id`, `name`, `saved_at`, `by` (the
signed-in person's name, or "Committee" for a shared-code session), `kind` (`saved` by hand, or `upload`, `open`, `refit`
for the ones the app keeps before replacing the draft), and the copy's `upload_id`, number of fixes and newest fix time
(its identity). Versions live in `DATA_DIR/draft_versions/<id>/`.

**The pop-out:**
- "Save the draft as" with a name box (default: the draft's file name and the date, e.g. "Agent run 2 · edited 22 Nov")
  and **Save version**.
- The list, newest first: the draft on step 8 (marked "now"), every version, and the published timetable (marked "what
  teachers see"; Compare only). Each row: name, where it came from (the file name), when and by whom it was saved, how
  many changes were made in the app, and its critical and warning counts **checked against the setup as it is now** (the
  line under the list says so). Buttons: **Open**, **Compare…**, **Download** (as .sqlite, like step 9's download; refused
  with the same sentence while a lesson waits in Not placed), **Delete** (asks first).

**Rules:**
- **Open** keeps the draft as a version first (kind `open`), unless the draft is the same as a version already kept (same
  identity), then makes the chosen version the draft: its file, setup, decisions and fixes, so its list of changes and
  Undo come back. The version stays in the list.
- **Uploading** keeps the draft as a version first (kind `upload`, named from its file), with the same "already kept"
  check. The "Replace the draft?" question then goes: the upload says in its result "The draft you had is kept as version
  '…'". (A draft with no fixes and identical to a kept version is simply replaced.)
- A re-fit's Apply keeps a version first (kind `refit`, named "Before re-fit, 22 Nov 2.10 pm").
- Versions kept by the app (`upload`, `open`, `refit`): at most 10; the oldest such is dropped when an 11th comes.
  Versions saved by hand stay until deleted. Builder: also refuse a hand save past 30 versions with a sentence.
- Names are trimmed, 1 to 80 characters; two versions may share a name (the date tells them apart).
- Publishing is of the draft only: to publish a version, open it first.
- History entries: version saved, opened, deleted, and the automatic keeps (one line each, with the name).

## Feature 2: Compare

**Where:** **Compare…** on a row opens the compare page (screen 2) with that row as A and the draft as B; both are
pickers over the same list as the pop-out.

**Matching lessons across two timetables:** lesson ids differ between two uploads, so lessons are matched by what they
are, not by id: each lesson row's planned key (`C:{class}:{subject}` for a whole-class row, `G:{code}` for a group),
with its placements (day, period, length, teachers, room). For each key, placements at the same day and period pair
first; the rest pair in order of day and period; any left over are "only in A" or "only in B". The builder may refine the
pairing, but must keep it deterministic.

**What it shows:**
- Tiles: lessons at another time (out of the total), lessons with another teacher, lessons in another room, critical
  A → B, warnings A → B (both checked against the setup as it is now), the teachers' longest day (most periods any
  teacher has in one day) A → B.
- **Show**: one class, teacher or room, as two week grids side by side (A and B), with every cell that differs outlined;
  a band's cells in light blue as on step 5. A box "mark what differs" turns the outlines off.
- **What differs for {name}**: one line per difference, e.g. "Mathematics: Mon 3 → Mon 6", "Social Studies: Fri 2 →
  Thu 4, teacher Karen Ismail → Hakim Kumar", "Science: only in B (Thu 7)".
- **Download the differences (Excel)**: every difference, class by class (one row per difference: class, lesson, A, B).

## Feature 3: Re-fit

**Where:** a **Re-fit to the setup** button on step 8 beside Versions, and a link in the red "Made from configuration…"
line. It is offered when the draft has open warnings the re-fit works on (below); otherwise it is greyed with "Nothing
to re-fit: the timetable fits the setup."

**What it works on (the targets):** the draft's open warnings, as step 8 lists them now, of these kinds: the deployment
differences (`dep:*`: another teacher on step 5, more or fewer periods, a lesson on step 5 but not on the timetable, a
lesson on the timetable but not on step 5, a room of the wrong kind), clashes, and broken Must rules. Warnings answered
"met" (accepted by the committee) and Prefer warnings already open are left alone.

**The direct change for each kind** (then the search clears what it causes):
- another teacher → swap **only the teacher who changed**: compare the timetable's teachers with step 5's for that class
  and subject (or group); where one teacher is replaced by one other (B → C), a `teacher` fix gives C the lessons B
  taught and leaves the other teachers as they are (a class and subject split between A and B stays split). One teacher
  added (C joins A) or one taken off (B leaves A) is a `teacher` fix too, the others kept as they are. When more than
  one teacher changes (two replaced by one, two added) or the rows' teachers cannot be told apart, it goes to Needs you
  with the step 5 sentence;
- more periods → `add` the missing periods (one per lesson length), for a lesson that is not in a band;
- fewer periods, or not on step 5 → `delete` the surplus (the lessons whose removal leaves the class's day pattern most
  even; builder's call how to pick, deterministically);
- on step 5 but not on the timetable → `add` its periods;
- a room of the wrong kind → a `room` fix to a free room of the right kind;
- a clash or a broken Must rule → no direct change; the search moves the lessons involved (`helper.involved`).

**The search (approach A):** for each target in turn (deployment first, then clashes, then Must rules), on the timetable
the earlier targets leave:
1. Try the direct change. If `helper.chain` judges it ok or prefer and it adds no clash or broken Must rule, take it.
2. Otherwise look for the shortest chain that makes it fit: the direct change plus up to three moves or swaps of the
   lessons in the way (the same class, teacher or room at that time), each judged by `fixes.judge` on what the earlier
   ones leave. Held to the lead's rules: a lesson of a band never changes day or period (its teacher or room may change);
   any other lesson keeps its day. A lesson **barred from every period of its own day** (its teacher, or one of them,
   is not available at any period of that day, or a setting or a Must rule forbids every period of that day for it)
   may go to another day at once. For every other lesson, another day is **the last resort** (the lead's answer of
   23 November 2026, after the measurement on the real file): only when no chain of up to three moves answers the
   warning with the lessons on their own days may a lesson move to another day, or change places with a lesson of
   another day. Same-day answers come first, always, for every warning of the list. Each such step is flagged
   "another day". Two teachers who change places on step 5 are **traded** in one step (no lesson moves).
3. Choose among the chains that fit: fewest lessons moved; then fewest "another day"; then fewest typed rules touched;
   then the moves nearest in period; then fewest new Prefer warnings. Never a chain that raises the number of open
   Prefer warnings overall; never one that touches a lesson an earlier target already moved (so the list never undoes
   itself). The "T{n} … check it again" warnings that a move inside a typed rule's scope raises (`verify.typed_again`)
   are not counted as broken Must rules by the search: they are allowed and shown (below).
4. A target with no fitting chain goes to **Needs you** with the sentence why (the judge's own sentence, or "A band stays
   where it is, so the app leaves it: …"), and nothing of it is changed.
- **A change to a band itself goes to Needs you** in this design: a banded subject gaining or losing periods on step 3, a
  group added to or taken out of a band on step 5, a lesson that should be in a band but is not. The fix kinds today
  cannot express these without splitting the band into separate lessons, and adding periods for a whole mixed band
  would put its other subjects over step 3. The line says: "This changes the band itself: change it on the board, or
  ask the agent for a new timetable." A teacher or room change on a band's lessons is not a band change and is made.
  A later stage may add band fix kinds (one lesson with a row per group; a row added to a band's lessons).
- Time limit: about 30 seconds for the whole search on the server (builder: tune with the real file); targets not reached
  in time go to Needs you as "not looked at in time; run Re-fit again". The search runs in a background thread with a
  progress line ("Looking at 12 of 31…") polled by the page, like the printouts.

**The list (screen 3):** "What doesn't fit the setup now" (the targets, in the step 8 sentences), the lead's rules as a
reminder line, then the changes grouped under the target that caused them, numbered, each in the fix's own sentence with
its reason in grey ("Farhan Hakim teaches 1A at Mon 3"); "another day" as a tag, and "check T7 again" (one per typed
rule whose scope the change touches) as a tag; **Needs you**; totals ("6 lessons move, 2 to another day · Critical
1 → 0 · Warnings 9 → 7 · 3 typed rules to check again"); **Preview on the board** (the board shows
the timetable as it would be, every changed lesson marked, like Preview today but for the whole list); **Apply all N
changes**; Cancel.

**Apply:** refused if the draft changed since the list was made (the draft's stamp, as Ask about this does today: "The
draft changed since this list was made. Run Re-fit again."). Otherwise: keep a version (kind `refit`), then write every
change as one batch on `meta.json` (`fix_many` widened to N fixes, each judged again on what the earlier leave; if any is
now refused, nothing is written and the sentence says which). Then the "met" answer of every typed rule whose scope a
change touched is cleared in `decisions.json`, so its "check it again" warning shows as open. Undo takes the whole batch
back (it already drops a whole batch; the cleared answers stay cleared, which is safe). One history entry: "Re-fit: N
changes (M lessons moved, K to another day, T typed rules to check again)".

## Constraints

- Committee only (`need("committee")`), like the rest of step 8. Department heads never see these.
- Never publish anything: both features work on the draft and on copies.
- The checks are always against the setup as it is now; every count says so where it could surprise.
- Server work must not block other requests (the search in a thread, one at a time; a second Re-fit while one runs is
  refused with a sentence).
- No real staff names, school name or keys in tests or docs; tests use the sample school (made-up names).
- Disk: a version is a copy of the draft folder (the timetable file plus the setup workbook); the caps above keep it small.

## Stages

1. **Saved versions and Compare** (features 1 and 2), including the keep-before-replace on upload. Its own plan and pull
   request.
2. **Re-fit** (feature 3), which uses stage 1's keep-a-version. Its own plan and pull request.

## Left to the builder

- The exact layout of the pop-out and the compare page within the mockups' look; the default version name; how to pick
  which surplus periods to delete; the pairing details for Compare (deterministic); the search's beam width and
  ordering inside the rules above, tuned on the real timetable (counts only) so a typical re-fit finishes in seconds.
- Where Download of a version and the differences' Excel sit in the code (reuse `draft.database` and openpyxl).
- Whether Compare's grids reuse the board's week view or a simpler table.

## Decided by the writer (for the lead to check)

- Uploading keeps the draft as a version and no longer asks "Replace the draft?".
- At most 10 versions kept automatically; hand-saved ones stay until deleted (30 at most).
- The re-fit leaves open Prefer warnings alone and never adds to them; it does not place lessons waiting in Not placed.
- A change to a band itself (periods, groups joining or leaving) goes to Needs you; bands never move, gain or lose
  periods in this design. (This replaces the earlier idea of adding a whole period to a band.)
- A lesson leaves its day at once when it is barred from that whole day; otherwise only as the last resort, when
  nothing works on its own day (changed on 23 November 2026: before, a full day was never a reason), and flagged.
- One teacher changed for another, one added or one taken off is made; more than one teacher changing goes to Needs you
  (changed by the lead on 23 November 2026: before, only one for another).
- Deleting surplus periods picks the ones that keep each class's days most even.
- The re-fit's targets are all open deployment differences, clashes and broken Must rules, not only the ones caused by
  setup changes since the upload (the app cannot tell those apart; the list shows each target so the lead sees them).

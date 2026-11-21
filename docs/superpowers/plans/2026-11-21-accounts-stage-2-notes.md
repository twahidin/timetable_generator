# Accounts stage 2: notes

Plan: `docs/superpowers/plans/2026-11-21-accounts-stage-2-put-back-and-since.md`. Design: `docs/superpowers/specs/2026-11-21-accounts-and-history-design.md`
("The history", "Stages" item 2). Built 21 Nov 2026 on branch `accounts-stage-2` from main 6ba7101 (stage 1, PR #83, merged, not deployed).

## What stage 2 gives

- **Who sees which history.** The committee signed in with a password (and the shared committee code) sees everything. A HOD or SH signed in
  with a password sees the changes to their departments' rows (lessons, bands, teachers, subjects), by anyone, and their own changes. Anyone
  else signed in by name who can change something (the setup, relief planning or settings, exams, the admin page) sees their own changes.
  Only the committee sees other people's sign-ins.
- **Put back** on the history page. One save (everything a person changed in one go, e.g. a band and all its lessons, with the Class Parents
  lessons the app adjusted because of it) goes back whole, or not at all. The committee puts back any setup change; a head only their own, and
  only what the head rules let them change now; an admin any account change (a change to several people goes back as one, the last admin who
  can sign in is kept). When something later touched the same thing, the button is greyed with the reason ("Can't put back: Ravi Das changed
  this again on 21 Nov, 9:24 pm", "Already put back by …", "another band is called … now", "lessons or rules joined … after this change"). A put
  back is a new change by the person who pressed it, and can itself be put back. The current values are checked again under the setup's lock,
  so a change that lands first makes the put back refuse rather than overwrite it.
- **Links instead of Put back** for step 8 ("Undo it on step 8"), step 9 ("Open step 9"), relief, exams and whole-setup replacements ("Use a saved
  copy on the committee page").
- **Download (Excel)** for the committee, with the page's filters, up to 20000 entries; every cell is text (never a formula), characters Excel
  refuses are dropped.
- **"Since you last signed in"** on the home page: the changes since the person's previous sign-in, by person and step, with "See them" (the
  history from that moment) and "Later". Everyone signed in by name sees "The timetable was published again on …" when it was.
- School time is fixed at UTC+08:00 for day filters and for the times the server writes, whatever the server's clock zone.
- A save sent twice (a lost reply and a retry) is recorded once; a history line with a mistyped field no longer breaks any page.

## Rulings made during the build (what each costs if wrong)

Plan rulings P1-P9 are in the plan. During the build:

1. putback.py writes the exams date like the admin page does, with its own small function (it must not import app). Costs a second copy of a
   two-line formatter.
2. Someone with no history right gets only the "published again" line in the summary, never a count of everything. Costs nothing (they see less).
3. Until account put back was built (Task 4), the route refused account changes. Replaced; costs nothing.
4. The skipped and unchanged operations a retried save used to record are no longer recorded. Costs a small change to how stage 1 records.
5. Marking which changes can be put back is done in one pass over the newer entries (it took 5.8 s on a long history before). Costs nothing.
6. The app's Class Parents follow-ups are part of the save they follow: put back with it, and checked like it. Costs: some Class Parents put
   backs refuse more often.
7. For everyone, a band put back is refused when another band now has the name, or when lessons or Block rules now name the band that the save
   did not carry. Costs: such band put backs are done by hand on step 5. (The design's "same row and field" rule did not cover names that other
   rows point at.)
8. An account put back keeps a head's current departments when the change did not record any, so step 4's are never copied in. Costs nothing.
9. Also fixed in the last round: the step 8 and 9 link words; the account put back's text written first; a setup replaced meanwhile refuses the
   put back; subject rows carry their department, so heads see step 3 changes to their subjects; the success message in green; README.
10. Known limit kept (below, first item): no second fix round by the build's rules; offered to the lead as a small follow-up.
11. A rare Class Parents case that refuses (below, second item) is kept: it refuses rather than overwrites.

## Known limits

- **A lesson can be put back into a band that is gone.** Move groups from band A to band B, then rename or delete band A, then put back the older
  move: the lesson names band A, which no band has, and step 5's bands page no longer shows it (the same for a group's delete or a Block rule's
  target). Uncommon; fix by hand on step 5. A small follow-up would refuse it ("Can't put back: the band … is gone now.").
- A Class Parents lesson the committee deletes and the app re-adds at once under the same id: the history page offers Put back, and pressing it
  refuses with "this was changed again since".
- An admin who signs in with their personal code gets "Please sign in again." (401) from Put back of an account change, not a 403.
- `/home` works out the summary on every visit until Later is pressed (about 130 ms on a large history).
- A deleted row whose neighbours were deleted too comes back at the end of its list.
- Smaller items (test hygiene, "Please sign in again." shown twice after a failed put back, "Changes to  rows" for a head with no departments,
  the download showing the server's answer when the session has ended) are listed in the build ledger and left for later.

## Not tried in a browser

- The Download button (the file was checked by tests and on the real setup, not opened from the page).
- An own-scope person's page and summary (a teacher on the exams committee); the head and the committee were checked.
- The step 8 and 9 link words (no step 8 entries in the made-up data; covered by `tests/history.test.js`).

## For later stages

- Relief stage 2 should add "relief" to the rights that give `history.own` when teachers' requests are recorded.
- Stage 3 (Google) and stage 4 (codes for everyone) as planned.

## Checked

- Every Python suite, `tests/smoke.py` and every node test on the final code; `node --check` on the pages.
- The school's real setup (v23, numbers only, scratch copy deleted): a typical change by a head of each of the 9 departments that had one, put
  back exactly (9 of 9); all 63 band renames (largest 16 changes, with their Block rules) put back exactly; a retried save recorded once; the
  history page in about 0.27 s and the download in 1.5 s with 30000 extra entries; the home summary in about 0.13 s.
- Browser (made-up people, real clicks): the summary on the home page, See them, the Since note and Show all, a six-change band rename put back,
  an account change put back, the greyed reasons, a head's view (scope line, own Put back only, Department filter), phone width.

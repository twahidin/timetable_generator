# Admin page, roles and committees: notes

Plan: `docs/superpowers/plans/2026-11-23-admin-roles-and-committees.md`. Design:
`docs/superpowers/specs/2026-11-23-admin-roles-and-committees-design.md` (mockup beside it). Built 23 Nov 2026 on branch
`admin-roles` from main d2dfbaf, subagent-driven: six tasks, each built by a fresh builder and read by a reviewer, then a
whole-branch review and one fix wave. All names in tests and docs are made up.

## What it gives

- **One role, any number of committees.** A person's role is School leader, HOD, SH, Teacher or Executive. Timetable
  committee, Relief team and Exams and events (until a date) are ticks beside it. Each tick adds its own access and
  none takes any away, so an HOD can also be on the Timetable committee and the Relief team. Admin is a tick that needs
  the Timetable committee; unticking the Timetable committee takes Admin away with it.
- **Nobody's access changes on the day.** People stored in the old "Timetable committee" group are read as "no role
  set, Timetable committee ticked" and shown as Teacher (on the published timetable) or Executive (not on it). The
  record is written in the new shape the next time it is saved. A test compares the rights before and after for every
  shape of record that can exist (each old group, each extra, switched off, each kind of sign-in).
- **Edit on every row.** The name (now in the link colour) and the Edit button both open the person's panel. In a wide
  window the panel sits beside the list and stays in view while the list scrolls. In a narrow window it opens over the
  page. Esc, the ✕ and a press outside it close it.
- **What this gives them.** The panel says in sentences what the person's role and committees let them do. The
  sentences are worked out from the same function that decides access, so the page cannot promise what the server
  refuses. Lines marked ✱ need a password account.
- **Several people at once.** The dark bar has Add to a committee, Take off a committee and Set role. Each previews in
  sentences before it applies.
- **Remove this person**, for anyone who is not on the published timetable. Their username and password go, their code
  stops working, their Telegram chat and any link code are dropped, and every session of theirs ends for good. What
  they changed stays in the History. A removal cannot be put back.
- **The first admin keeps their role.** The first-admin page ticks Timetable committee and Admin and leaves the role
  alone (before, it moved the person into the committee group).
- **History.** A role change reads "role HOD → Teacher". The tick reads "Timetable committee given" or "taken away" and
  can be put back like the others. Old entries still read as they were written.

## Things the committee lead should know

1. **The hint "Step 4 lists N teachers as HOD or SH whose role here is still Teacher" will now also name Timetable
   committee members** whom step 4 lists as HOD or SH (their role now reads as Teacher). One press of "Make them
   management" makes them HOD or SH and keeps their committees and Admin.
2. **The same name added again gets the same personal code as before** (a code is made from the name alone), so an old
   printed slip works again. Their old sessions do not come back.
3. **A removal has no Put back.** Add the person again with Add a person. Older entries about a person who was removed
   since cannot be put back either: make the change on the admin page.
4. **One role per person** (not School leader and HOD together), and **Exams and events is one tick**. Both were my
   calls in the design; say if either should change.
5. **Do not roll the app back past this change without care.** An older version reads records saved since as "no
   group, no Timetable committee", would offer "Make the first admin" again, and drops the list of removed people at
   its first save (see the design's rollback section).
6. A person on the Timetable committee signed in with only their **personal code** still does not get the setup, the
   History of everyone or the admin page. That is unchanged: those need a password.

## Rulings made during the build (what each costs if wrong)

1. The test file keeps a word-for-word copy of the old rights function, as the design orders, to prove nothing
   changes. Costs a duplicated block in a test.
2. The server refuses to remove a person on the published timetable with the design's full sentence ("…so they cannot
   be removed: they would come straight back. Switch them off instead."), the same one the panel shows. The plan had a
   shorter one. Costs one string.
3. Several people's role change previews as "The role of {names} becomes {label}." (the plan's), not the design's
   example "Priya Nair's role becomes HOD.", because it reads right for several names. Costs one sentence.
4. One more check than the plan asked: an old password session stays dead after the same name is added again and given
   a new password. Costs nothing.
5. Remove keeps a guard for "no admin would be left". It can only fire when another admin changes the acting admin at
   the same moment. Costs three lines.
6. For the admin's own row the panel says "You cannot remove yourself." where the plan would show nothing. Costs one
   string.
7. An Exams and events date that has passed still shows as a chip and counts in the Committee filter, as before this
   change. The server clears passed dates at the first request of the next day. Costs a chip that can be a day stale.
8. Typing the "until" date by keyboard was broken (also on the live site): the page saved at the first digit of the
   year, the server refused and the box emptied. Fixed here, in the panel and in the bar: the page waits for a whole
   date. Costs a small guard.
9. "Add to a committee" and "Take off a committee" open with Relief team chosen, as before and as in the mockup, not
   Timetable committee. Costs one default.
10. The unreachable sentence "Pick an extra." was left as it is. Costs nothing a person can meet.

Found and fixed on the way, beyond the plan:

- A first sign-in used to make a person's record from nothing, with its sign-out number at 0. For a removed person
  named again by a later timetable, that could have matched an old cookie. First records now start from the kept
  number, and a sign-in or a password change in flight during a removal no longer leaves a record behind.
- Telegram: while nothing is published, a removed name is no longer treated as "there", and a removal drops the
  person's link codes as well as their link, before and after the record goes.
- A removal re-reads the published timetable at the moment it writes, so a publish that names the person in between
  refuses it.
- The bar reloads the list when a ticked person was removed by another admin in the meantime.
- Put back is refused on an older entry about a person who was removed since, so a person added again cannot be given
  their old access by one press.

## Checked in a browser

On a scratch data folder with a made-up school of 14 teachers, one admin made through the first-admin route, people
added by name. Real mouse and keyboard, at 1024px, 1280px and 700px wide. No console error from the page.

- Edit on every row; name and Edit open the panel, a second press closes it; focus goes to the panel's heading and back
  to that row's Edit; Esc; the ✕; the dimmed page at 700px.
- The panel beside the list at 1024px and 1280px (it stays under the header and scrolls inside itself); over the page
  at 700px.
- Role box; departments for an HOD; all three committees and Admin on one person; the sentences, the ✱ lines and the
  "has none yet" line; the until date typed by keyboard (panel and bar).
- The only admin unticking their own Timetable committee: refused with the last-admin sentence, the tick stays.
- Add to a committee for three people with its preview and Apply; Take off a committee with its "stops being an admin"
  line; Set role; the keyboard through the bar and its choices; "Make them management".
- Add a person; Remove with its question; the person gone; their own session (held by a script, signed in with their
  personal code) answering 401 afterwards; their code refused.
- A second admin removing a person while this admin has that person's panel open, then a tick: the "not on the staff
  list" sentence and the list without the person. The same through the bar's Apply.
- The History page's entries for all of the above; the Ways in and Students tabs; Make a password account; Switch off.

## Not checked

- In a browser: Change username, Reset password, printing code slips, Put back pressed on the History page, the
  first-admin page itself (the admin was made through its route by a script), dark mode, a real phone, a second
  browser.
- The live site's own accounts file. The move of old records is proven on every shape a record can have, and on files
  written by the old code in the reviewer's probes, not on the school's real file (it is on the server).
- No real Telegram bot and no model API was called by any test or probe.

## Known limits and follow-ups (not built)

- The narrow-window panel does not trap the keyboard's focus or lock the page behind it from scrolling.
- At 1024px with the panel open the table scrolls sideways (the Edit column stays in view).
- The server's preview and History sentences still say "changes the map for X" where the panel now says "Changes the
  teaching groups of". Old History entries keep the old words in any case.
- Putting back "Timetable committee given" also takes away an Admin given later (as unticking does). The confirm box
  does not say so.
- A date box cleared by hand is not saved (the stored date returns): untick Exams and events to clear it.
- A removed person's name stays as text in relief records, exam duties and older History entries, as the design says.
- The removed person's username and note are in the removal's History entry, which everyone who sees the whole History
  can read. The design lists both.

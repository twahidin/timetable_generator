# The admin page: one role, any number of committees, Edit and Remove

Date: 23 November 2026. Status: **written for the committee lead to approve**. The lead saw the clickable mockup on
23 November 2026 and said "Yes, write it up". Read once by a builder; its four questions are settled below, each
marked "design's call". A follow-up to the accounts design
(`2026-11-21-accounts-and-history-design.md`, stages 1 and 2 live). Mockup with made-up names:
`2026-11-23-admin-roles-mockup.html` beside this file. Where this file and the mockup differ, this file is right.

## Why

The lead's words, looking at the live admin page: "I thought the admin page will be abit more robust, ie a person can
be in management, a HOD/SH and in relief or timetable or exam or event committee at the same time. This will allow a
person to have access to different parts of the app. I also cannot remove the person or edit the person".

What the page does today:

- A person has **one group** (Timetable committee, School leader, HOD, SH, Teacher, Executive) and up to three
  **extras** (Relief team, Exams and events until a date, Admin). So an HOD can be on the Relief team, but nobody can
  be an HOD **and** on the Timetable committee, because both are groups.
- Editing exists but is hidden: pressing a person's name opens a panel. The name does not look like a link, and in a
  window narrower than 900px the panel opens below the whole list (103 people on the live site), out of sight.
- There is no way to remove a person. They can only be switched off.

## Goals

- A person has **one role** and **any number of committees**. Each committee adds its own access; none takes any away.
- Nobody loses or gains access on the day this goes live: every person can do exactly what they could before.
- Editing a person is obvious, and the panel is always in view.
- A person who is not on the published timetable can be removed.
- The page says in plain words what a person's role and committees let them do.

## Non-goals

- Two roles for one person (School leader and HOD together). One role; my call, shown to the lead twice, not objected to.
- Splitting "Exams and events" into two committees. It stays one tick with an end date; my call, same.
- New rights, new pages, or a change to what any existing right opens.
- The shared codes (`COMMITTEE_CODE` and the others) and the Ways in tab: unchanged.
- Renaming a person. A person added by name with a misspelt name is removed and added again.
- Removing a person who is on the published timetable. They come from the timetable, so they are switched off.
- Putting a removal back from the History (see Remove).
- Warning about relief or exam duties a removed person still holds. Their name stays in those records as text, as it
  does today for a teacher who leaves the timetable on a later publish.

## Anti-goals

- Anyone locked out, or the app left with no admin who can sign in, because of the move.
- A person shown as on a committee on the page while the server does not give them its access, or the other way round.
- A removed person still signed in.

## Approaches

1. **Timetable committee becomes a tick beside the other two (picked).** The group box keeps the person's role;
   "committee" stops being a role. Smallest change that gives what the lead asked: the rights code is one small
   function, and the rest of the app asks for rights by name, never for the group. Picked by the lead from the mockup.
2. **Any number of groups, all ticks.** A person could be School leader, HOD and Teacher at once. More freedom than
   asked for, and it makes "whose departments does this HOD change" and the role chip on every list unclear.
3. **Keep one group and add a "second group" box.** Stops at two, and is harder to explain than ticks.

## The design

### What is kept about a person

Nothing new is stored except one tick.

- **Role**: the stored field keeps its name `group`. Its values are now `leader`, `hod`, `sh`, `teacher`,
  `executive`. `committee` is no longer a role. A person with none set shows as Teacher when they are on the published
  timetable and Executive when they are not, as today.
- **Committees**: `extras.timetable` (new, true or false), `extras.relief` (as today), `extras.exams` (as today: the
  last day, or none).
- **Admin**: `extras.admin`, as today. It needs the Timetable committee tick, where today it needs the committee group.

### Moving the people who are in the Timetable committee group today

Done when a record is read (`accounts/people.py`, `_clean`), not by a one-time job: a stored record whose group is
`committee` is read as **no role set** and **Timetable committee ticked**. It is written back in the new shape the
next time that record is saved. This cannot half-happen and needs no flag.

- Their role then shows as Teacher or Executive by the rule above.
- The page's existing hint ("Step 4 lists N teachers as HOD or SH who are still in the Teacher group. Make them
  management") will now also name committee members whom step 4 lists as HOD or SH. That is wanted: one press makes
  them HOD or SH and keeps their committees.
- A request that sets the group to `committee` is refused with the page's "Pick a group" sentence, reworded to "Pick a role."

### What each role and committee gives

`accounts/rights.py` stays the only place that decides. The table below is today's rules with "the committee group"
replaced by "the Timetable committee tick". Rights add up. "With a password" means signed in with a password (or
Google, when that comes); a personal code never gives those lines, as today.

| Who | Any sign-in by name | Only with a password |
| --- | --- | --- |
| Everyone | `timetable`, `files`, `history.own` | |
| Role Teacher, School leader, HOD or SH | `relief` | |
| Role School leader, HOD or SH | `relief.plan`, `relief.settings` | |
| Role HOD or SH | | `setup`, `history.dept` |
| Timetable committee | `relief`, `relief.settings`, `relief.save` | `committee`, `setup`, `history`, `codes` |
| Relief team | `relief`, `relief.plan`, `relief.settings`, `relief.save`, `relief.team` | |
| Exams and events, date not passed | `exams` | |
| Admin (with Timetable committee) | | `admin` |

Two things follow and must hold:

- **An HOD on the Timetable committee changes every department**, not only their own. The app already treats a head
  as "has `setup` and not `committee`" (`is_head` in `app.py`), so this needs no change, only a test.
- **Nobody's rights change on the day.** For every shape of record that can exist today (each group, with and
  without each extra, each kind of sign-in), the rights worked out after the change equal the rights before. A test
  proves it by keeping a copy of today's function in the test file and comparing over all the shapes.

### The Staff tab

Columns: tick, Name, Role, Committees, Department, Last signed in, and an **Edit** button.

- **Name** is in the link colour. Pressing the name or Edit opens that person's panel; pressing either again closes it.
- **Role** is one chip, coloured as the group chips are today.
- **Committees** shows a chip for each: Timetable committee, Relief team, "Exams and events · to 31 Dec 2026", Admin.
  A dash when none. "Switched off" shows here, before the chips, as it does today under Extra.
- A person not on the published timetable has "added by name" under their name.
- The Edit column stays in view when the table is too narrow to show every column.

Filters: Search a name, **Role** (all, then the five roles), **Committee** (any, Timetable committee, Relief team,
Exams and events, Admin, No committee, Switched off), Department, Tick all shown.

### The panel

Wide window (over 900px): beside the list, as today. It stays below the header while the list scrolls, and scrolls
inside itself when it is taller than the window. Narrow window: it opens **over** the page from the right, the page
dimmed behind it. Esc, the ✕ and a press on the dimmed page close it. Focus goes to the panel when it opens and back to
that row's Edit button when it closes.

Top to bottom:

1. The name; "On the published timetable" or "Added by name: not on the published timetable"; "switched off" when so.
2. **Role** · one: a box with the five roles.
3. For an HOD or SH: **Changes the teaching groups of**, the school's departments as ticks in a row (today's "Changes
   the map for", same rules).
4. **Committees** · tick any number: Timetable committee, Relief team, Exams and events (with its "until" date box when ticked).
5. **Admin**: one tick. Greyed with "needs the Timetable committee" until that is ticked; "opens this page" when it can be ticked.
6. **What this gives them**: the sentences below.
7. Way in, Note, and the buttons Reset password (or Make a password account), Their changes, Switch off or on: all as today.
8. Remove (see below).

Every tick and box saves at once, as today, through the same call (`POST /api/admin/person`), which now also takes
`extras.timetable`. The server's rules, each refusing the whole change with a sentence:

- Admin only with the Timetable committee. Unticking the Timetable committee also takes Admin away (today: leaving
  the committee group does).
- The app always keeps an admin who can sign in (today's rule, unchanged).
- A change to role, departments, any committee, Admin or switched off signs the person out everywhere (today's rule,
  with the new tick added to it).

### What this gives them

The server sends, with each person on the admin page, a list of sentences worked out **from the rights function
itself** for that person as they would be with a password. The page only shows them. Lines that need a password carry
a mark; when the person has no password account, one line under the box says "The lines marked ✱ need a password
account. {name} has none yet."

| When the person has | Sentence | ✱ |
| --- | --- | --- |
| switched off | Nothing: switched off, so they cannot sign in. (the only line) | |
| always | Sees the published timetable and the files. | |
| `relief`, not `relief.plan` | Relief: opens the relief page and asks for cover. | |
| `relief.plan`, not `relief.team` | Relief: plans cover, as management. | |
| `relief.team` | Relief: runs it, with the team's pages and settings. | |
| `setup`, not `committee`, departments ticked | Setup: changes the teaching groups of {departments} only. | ✱ |
| `setup`, not `committee`, none ticked | Setup: no department ticked yet, so nothing to change. | ✱ |
| `committee` | Setup: every step, the upload, the edit board and Publish. | ✱ |
| `committee` | Exams and events: plans them and approves them. | ✱ |
| `exams`, not `committee` | Exams and events: plans them, until {date}. | |
| `history` | History: sees everyone's changes. | ✱ |
| `history.dept`, not `history` | History: sees their departments' changes. | ✱ |
| `admin` | People and access: this page. | ✱ |

The builder checks each sentence against what its right opens in `app.py` and tones down any that says more than the
right gives. A sentence never promises something the server refuses.

### Ticking several people

The dark bar's buttons become **Add to a committee ▾**, **Take off a committee ▾**, **Set role ▾**, then Print their
code slips, Switch off, Switch on and Clear ticks as today. The two committee menus list Timetable committee, Relief
team, Exams and events (with its date when adding) and Admin (the mockup leaves Admin out of these menus; it stays,
as it is there today). Every action still previews in sentences before it applies, in today's style, for example:

- "Priya Nair and Chloe Yeo join the Timetable committee." / "Arjun Menon is on the Timetable committee already."
- "Grace Ong leaves the Timetable committee." / "Grace Ong stops being an admin: only the timetable committee can be admins."
- "Priya Nair's role becomes HOD." (today: "moves to the HOD group")

### Remove

A **Remove this person** button at the foot of the panel, only for a person who is **not on the published timetable**
(added by name, or still holding a record after leaving the timetable). For anyone else the panel says instead:
"{name} is on the published timetable, so they cannot be removed: they would come straight back. Switch them off
instead."

"On the published timetable" means the published one only, never step 4 of the setup being edited (design's call).
While nothing is published the list holds only people added by name and people with a username, and each of them can
be removed; anyone a later publish names comes back as a new person.

Pressing it asks in the panel: "Remove {name}? Their username and password go, their code stops working and their
Telegram chat is unlinked. What they changed stays in the History. This cannot be put back." with **Yes, remove**
and **Cancel**.

A new call, `POST /api/admin/remove` (the `admin` right), with the person's name. It refuses, changing nothing, when:

- the person is on the published timetable (the sentence above);
- the person is the admin doing it: "You cannot remove yourself.";
- it would leave no admin who can sign in (today's last-admin sentence);
- the name is not on the staff list.

Otherwise, in this order:

1. **Their Telegram chat is unlinked** (relief keeps the links by name in its own store). If this fails, nothing is
   removed and the page says so. If the next step fails after this one worked, the person is still there and only
   has to link Telegram again.
2. In one write to the accounts file:
   - Their record is deleted. Their username is free for someone else.
   - The accounts file keeps one thing about them, in a new `removed` list: the name and its sign-out number plus
     one. **No old session can come alive again**: a person added later under the same name starts from that number,
     and while the name is on the `removed` list and has no record, no session by that name is accepted, with or
     without a published timetable. (Today a code session whose name has no record can carry on while nothing is
     published, and a new record starts its number at 0, which an old cookie could match. Design's call: this is why
     Remove leaves the number behind.)

After it:

- **Every session of theirs has ended**, signed in by password, by code or through Telegram.
- Their personal code stops working, because the name is off the staff list. A code is made from the name alone, so
  **adding the same name again gives the same code as before** and an old printed slip works again. Design's call:
  an admin who adds the same name back means the same person. The lead should know it.
- The History gets one entry, "Removed {name}", by the admin, listing what they had (role, committees, departments,
  username, note, switched off) and never their password. It has **no Put back**: pressing Put back on it answers
  "Can't put back: add {name} again with Add a person."
- Relief, exams and older History entries that name them keep the name as text.

The person can be added again with Add a person; they start with no role set, no committees, no username and no
password, and must link Telegram again.

### History and Put back

- A role change reads "role HOD → Teacher" (today "group …"). Entries written before this change still read correctly,
  and an old entry that names the Timetable committee as a group still shows that label.
- The Timetable committee tick reads like the other extras: "Timetable committee given" / "taken away". It can be put
  back like them, under the same rules (nothing later touched the same thing; an admin is always left).
- Put back on an **old** entry that moved a person into or out of the Timetable committee group answers "Can't put
  back: this is from before roles and committees were separated. Make the change on the admin page."

### Everywhere else

- The first admin page ticks Timetable committee and Admin for the person and **keeps the role they have** (today
  it moves them into the committee group, which would take an HOD out of HOD). Design's call. The recovery code finds
  admins as "Timetable committee ticked, Admin ticked, not switched off".
- Relief's Management (School leader, HOD, SH) and Team (the Relief team tick) read the same fields as today.
- Wherever the app shows the signed-in person's group label, it shows the role, then the committees.
- Tests and docs that say "the committee group" are brought in line.

## If the app is ever rolled back

A version from before this change reads a record saved in the new shape as "no group, no Timetable committee". So
after a rollback, people whose records were saved since would lose the committee's access until the new version is
back. An admin saved in the new shape would not count as an admin either, so the old version would offer "Make the
first admin" to anyone holding the committee's rights (the shared committee code) and refuse changes to a person who
has Admin ticked. The shared committee code and the first-admin page still let the lead in. No account is lost. So: do
not roll back past this change without telling the lead first.

Added after the build's review (23 November 2026): one thing is lost in a rollback. The old version does not know the
`removed` list and drops it at its first save. A person removed before the rollback would then be treated as never
removed: while no timetable is published, a code session of theirs from before the removal could be accepted again.
With a timetable published it stays refused.

## What is left to the builder

- How the sentences travel from `rights.py` to the page, and the names of the helpers.
- The shape of the `removed` list and where the checks that read it sit.
- The exact preview and history sentences not written above, in the style of the ones that exist.
- The look of the committee chips and the dimmed narrow-window panel, close to the mockup, using the page's own styles.

## Testing

- Rights: the before-and-after proof above; an HOD on the Timetable committee changes any department; Admin without
  the Timetable committee is refused; unticking the Timetable committee takes Admin away; the last admin is kept.
- The move: a stored `committee` record reads as ticked with no role; saving it writes the new shape; reading twice
  changes nothing more.
- Remove: each refusal; sessions by password, by code and through Telegram end, with and without a published
  timetable; the username is free; the code stops; the same name added again cannot be reached by any old cookie
  (old password cookie after a new password is set, old code cookie); a failed Telegram unlink removes nothing; the
  History entry holds no password and refuses Put back.
- The first admin: an HOD who makes themselves the first admin is still an HOD, with both ticks.
- Put back: the new tick goes back; an old committee-group entry is refused with its sentence.
- The page (in a browser, with made-up people, on a scratch data folder): Edit on every row; the panel in view at a
  wide and a narrow window; keyboard and focus; a person with all three committees; the sentences; the two menus.
- Every existing suite still passes.

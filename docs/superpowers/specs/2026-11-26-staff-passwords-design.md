# Staff sign in with a username and password; students keep their code

Date: 26 November 2026. Status: **approved by the committee lead on 26 November 2026** ("Approved, plan it"). Follows the accounts design of
21 November 2026 (`2026-11-21-accounts-and-history-design.md`) and changes one of its rules: a member of staff no longer
signs in with a personal code at all.

## Intent and the why

Today one code box serves everyone: students and all 99 staff type their personal code there, and a staff code opens
almost everything that person's group gives (every published tab, relief, exams), only not the setup or the admin page.
Only 7 people have a username and password.

The lead wants (their words, 26 November): "no code for teacher, but one username and password to access both relief
and timetable. I need print their usernames and temp passwords, only students uses code; all teachers will do relief or
some sort, and they may access different parts of the application if they are in exam committee or event committee."
Earlier the same day: a separate personal code page for students; non-management staff "can access their own and the
rest of the classes"; management "can see everything".

The reason, as far as the lead gave it: anything that does something (relief first of all) should be done by a named
person with their own password, not by whoever holds a slip. Looking is for students, with a code.

## Who signs in how (after the lead turns staff codes off)

| Who | Signs in with | Sees on the published timetable | Can do |
|---|---|---|---|
| Student | personal code, on the student page | their own timetable (as now) | nothing (as now) |
| Teacher, Executive | username and password | **their own timetable and every class timetable** | relief as now (a teacher asks for cover, sets work); executives as now |
| School leader, HOD, SH | username and password | everything published (every tab a teacher sees today) | as now: plan cover; heads their departments' setup |
| Anyone with a committee tick (Timetable committee, Relief team, Exams and events) | username and password | everything published (**design's call**: they plan around other people's timetables) | what the tick gives, as now |

The ticks on the admin page stay exactly as they are. "Exams and events" is one tick today and stays one tick: the lead
spoke of an "exam committee or event committee"; the design reads them as that one tick (**design's call**; split it
later only if the lead asks).

## Goals

1. **A student page** with only the code box, at its own address (`/student`). Student code slips print that address.
2. **One click on the admin page makes every missing staff account and prints the slips**: a username for each member of
   staff who has none, a temporary password for each, and a PDF of slips (one person each, by department, as the relief
   code slips are drawn) with the name, username, temporary password and the site address. Each person must choose their
   own password the first time they sign in (the existing "must change" step).
3. **A switch to turn staff codes off**, pressed by the lead once the slips are out. Until then nothing changes for
   teachers. Once off, a staff code opens nothing, on the sign-in page or anywhere else.
4. **Teachers and executives see a narrower published timetable**: their own timetable and the class timetables.
   Management and committee members see all of it. **This starts with the switch, not with the deploy** (from the
   lead's approved "nothing changes for teachers until the slips are out"): while staff codes are on, every staff
   session sees what it sees today; once they are off, the view follows the person's group and ticks.
5. **The front page follows the switch.** While staff codes are on, `/login` is the code page as today (with the link
   to the username page). Once they are off, `/login` is the username and password page, with a link
   "Students: sign in with your code" to `/student`; `/student` links back with "Staff: sign in with your username".

## Non-goals

- Sign in with Google (still a later piece of the accounts design).
- Changing what relief, exams or the setup do, or who may do them. Only how staff get in, and the published tabs a
  teacher sees, change.
- Student passwords. Students keep their code.
- A separate "Events committee" tick.
- Self-service password reset by email. A forgotten password is still "ask an admin" (the admin page's existing reset).

## Anti-goals (a failure even if it works)

- **Staff locked out on the day it goes live.** Deploying this must change nothing for a teacher until the lead presses
  the switch. Making accounts never turns codes off by itself.
- **A temporary password stored or shown anywhere but the slip.** Only its hash is kept; it is in the PDF answer and
  nowhere else: not the history, not a log, not the admin page afterwards, not a CSV kept on the server.
- **Printing slips overwrites a password someone already chose** without the admin being told first.
- **A teacher can still open another teacher's timetable, the rooms, the student list or Who's free from what the
  server shows or serves** (a page, a PDF address, an API). The narrowing covers what is shown and what the server
  serves as files and APIs, done on the server as the student views already are, never by hiding tabs alone. Every
  lesson, with its teacher and room, stays in the page's data, because the class timetables need it (see "Data sent"
  below). (changed in the build, 26 November 2026: see the notes file)
- **A staff code session started before the switch keeps working after it.** Turning staff codes off ends those
  sessions at their next request.
- **The school locked out of the admin page.** The switch refuses while no admin has a usable password account (the
  existing `usable_admins` rule).

## How it works

### The admin page, Ways in tab

The "Personal codes (staff and students)" row becomes two rows:

```
Way in                     State                                   
Student codes              On · 1,284 students                      [Print slips]
Staff codes                On · 92 staff without a password yet     [Turn off]
Username and password      On · 7 of 99 staff                       [Make accounts and print slips]
Recovery code              Not set
Shared committee code      Off since 26 Nov 2026                    [Turn on]
...
```

- **Make accounts and print slips** opens a short preview: "92 staff have no account yet: each gets a username made
  from their name and a temporary password. 2 more have a temporary password from an admin that they have not used yet
  (named): they get a new one on this slip. 5 have chosen their own password and are left as they are." One rule for
  the first press and every later one: everyone who has not chosen their own password gets a slip (**design's call**,
  from the builder check).Then **Print** downloads
  the PDF (and, beside it, the same list as a CSV for a mail merge, **design's call**, from the same answer: both made
  once, never kept on the server).
- **Printing again** gives a new temporary password only to people who have not yet chosen their own (still "must
  change"); those slips replace the old ones. People who have chosen a password are left out, and the preview says how
  many.
- The People tab's tick bar gets **Print username slips** for the ticked people. For a ticked person who has already
  chosen a password, the preview says so by name ("Tan Ah Kow has chosen a password: their slip gives a new temporary
  one and their old password stops working"), and printing goes ahead only after that. This is also how an admin
  re-issues a forgotten password for several people at once; the existing one-person Reset stays.
- **Turn off** staff codes asks once: "Staff codes stop working at once, on every device. 12 staff have not signed in
  with a password yet: they will need their slip." Turn on puts them back (as the shared codes do). The row shows
  "Off since 26 Nov 2026" in green once off, as the shared code rows do.
- The old "Print code slips" for staff (relief code slips) is hidden while staff codes are off.

### Usernames

Made from the person's name as it is on step 4: lower case, letters and digits kept, everything else dropped
(`Tan Ah Kow` → `tanahkow`), cut to 40 characters; fewer than 3 characters gets the department's first letters added;
a clash gets 2, 3, … at the end (`tanahkow2`). Existing usernames are never changed. An admin can still change any
username with the existing Change username. (**design's call**; the lead can ask for another pattern, such as
initials and surname.)

### Temporary passwords

The existing `passwords.one_time()` (12 letters as `XXXX-XXXX-XXXX`, from the slip alphabet with no 0/O/1/I/L). Stored
as a hash with `must_change` set, so the first sign-in goes straight to "Choose your own password", as a reset does now.
**Making a slip never signs a teacher out of a code session** (the sign-out number `n` is shared by code and password
sessions): a person who has not chosen a password keeps their `n`, so their code keeps working until the switch. Only a
slip for someone who **has** chosen a password (the ticked-people case, after the named warning) bumps `n`, ending their
sessions as a reset does (**design's call**, from the builder check).

### The slip

As the relief code slips: 10 to an A4 page, a new page per first department, cut lines. On each: school name, "your
sign-in", the person's name and departments, **Username**, **Temporary password**, "Go to <site address>, sign in, then
choose your own password. Keep this slip to yourself until you have." No other person's details on it.

### The published timetable for a teacher

A new view, `staff`, built on the server like the existing `student` and `personal` views in
`ttgen/export.py html_data`:

- Tabs: **My timetable** (their own teacher timetable, opened first), **Classes**, **Exams**.
- **Exams for a plain teacher: their own duties and the class exam timetables** (the lead's answer, 26 November, "Own
  duties, classes"). They see each class's papers, dates and times, and their own invigilation duties with the room.
  They do not see other teachers' duties, the rosters, or the seating plans (which list students). This is a third
  level of the published exams data beside today's "full" and "student" (`_published_reader` in app.py,
  `exams/published.py`), made on the server, and every exams route a teacher can call (`/api/day`, the prints, the
  roster) answers with that level or 403. Management and committee members keep "full".
- Data sent: every class and every lesson (a class timetable names the teacher of each lesson, as it does now, so this
  narrows what a teacher is shown, it does not hide who teaches which class), the teacher list with names and short
  names only (as the student view), no student list, no rooms list, no Who's free.
- Files: the class PDFs and their own teacher PDF, not the whole teacher book.
- `/pdf/teachers/<name>` answers only their own name; rooms and students answer 403, as the shared student code's are.
- Executives (no lessons of their own) get Classes and Exams only.

Who gets the full teacher view: the group is School leader, HOD or SH, or any committee tick is set. Everyone else
signed in by name gets the `staff` view. The cached views (`pub["views"]`) get the teacher's name in their key, since
each teacher's page differs.

The shared teacher code (off now) gets the `staff` view without My timetable if it is ever turned back on
(**design's call**: a shared code cannot be "everything").

### Signing in, while staff codes are on and after

- **On (as now):** the code page at `/login` accepts student and staff codes; a staff code gives what it gives today,
  relief included. Nothing changes for teachers until the switch, so they can keep working while slips go round.
- **Off:** `/login` is the username page; `/student` is the code page. `/student` also accepts any shared code that
  is still on (the Ways in rows keep their own switches; today all three are off), so turning a shared code back on
  still lets it in (**design's call**, from the builder check). A staff code typed on either page gets
  "Staff now sign in with a username and password. Ask the timetable committee for your slip." (recorded in the history as
  "staff code after staff codes were turned off"; not a strike for the lockout, changed in the build on 26 November
  2026: the lockout counts per address, and a school behind one address would otherwise lock everyone out). Every existing session
  with `via == "code"` for a member of staff is refused at its next request and goes to the sign-in page.
- Telegram for relief is not affected: a chat is linked with a one-time code from the app, and linking needs the person
  signed in, which after the switch means by password.

### History

One entry per click: "Made accounts for 92 staff and printed their slips", "Printed new slips for 5 staff (2 had chosen
a password)", "Staff codes turned off", "Staff codes turned on", each with who did it. Never a password, never a
username beside a password.

## Approaches considered

1. **Make accounts and print slips on the admin page, plus a switch the lead presses later (chosen).** Nothing changes
   for teachers until the slips are out; the lead decides the day.
2. **Make every account and turn staff codes off automatically on deploy.** Fewer clicks, but all 92 staff without a
   password would be locked out until a slip reaches them. Ruled out.
3. **Only a spreadsheet of usernames and passwords for a mail merge.** Puts the work on the lead and leaves a file of
   passwords on someone's computer. Kept only as a CSV beside the PDF.

## Constraints

- The real school's names never appear in tests, commits or this document (made-up names only, "CTSS" for the school).
- No real codes, passwords or keys printed in any output or report.
- Rights are worked out on the server from the records on every request (`accounts/rights.py`); no new route may be
  reachable without its right.
- `ttgen/export.py` lives in the skill folder; a change there is a change to the skill (version line in SKILL.md).

## Left to the builder

- Where the `staff` view's "My timetable" sits in the page's tab code, and its exact label.
- How the switch's state is stored (beside `ways.off` in the accounts file is the obvious place).
- The CSV's columns (Name, Department, Username, Temporary password).
- Splitting the work into stages, if it is too large for one branch: the natural cut is (1) accounts, slips and the
  switch, (2) the student page and the front page, (3) the `staff` view.

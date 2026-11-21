# Accounts, rights and the history of changes

Date: 21 November 2026. Status: **approved by the committee lead on 21 November 2026** ("Approved, plan it"). Read once by a builder; the lead
answered its one open question (what a personal code opens for committee and management); the design settled the
other three (bands, shared codes, relief and exams entries), each marked "design's call". Project 3 of the four agreed on
9 November 2026 ("who sees what after publishing"), widened by the lead to personal accounts, an admin page and a
history of every change. Mockups, all with made-up names: `2026-11-21-accounts-and-history-mockups.html` beside this
file (sign-in, admin page, ticking several people, the history).

## Why

The lead's words: "I need a way to create special accounts for different people so that any changes to the site, there
is a history and log of the changes since last login and we can trace, example TT commitee has all rights, HODs can
only access certain parts of the deployment only .. etc as well as access for certain groups of personnel to access
this app. I need an admin page and control them via username and password."

Today everyone signs in with a shared code per role (`COMMITTEE_CODE`, `HEADS_CODE`, `TEACHER_CODE`,
`STUDENT_CODE`), so a change cannot be traced to a person, and a head of department can change any department's part
of the department map. Relief (stage 1, merged as PR #77) added a personal code for every member of staff and exams
(stage 1, PR #79, open) reads the same people; both keep their own lists of who may do more (relief's Management and
Relief team, the Exams committee). This design makes one list of people, one set of rights and one history for the
whole app, and absorbs those lists.

Later in the conversation the lead added: "I am going to make the teacher and student google access login", and asked
for both: "the google login will appear if I have set it up backend".

## Goals

- Every person who signs in is known by name; every change is recorded against that person.
- Rights by group, checked on the server for every page and every action, not only on the page.
- A head of department or subject head changes only their own department's part of the department map.
- An admin page where the named admins create people, give and take away rights (several people at once), reset
  passwords, switch people off, issue a new personal code, and link Google accounts.
- A history of every change: who, when, where, what it was and what it became; "Put back" on one change; "Since you
  last signed in" after signing in.
- Sign in with Google when the lead has set it up; personal codes and passwords keep working beside it.
- The shared codes can be switched off once everyone has their own way in.

## Non-goals

- Sending email (the app has none). Password resets go through an admin.
- Generating timetables (dropped on 9 November 2026).
- Changing what relief or exams do. Only who may do it moves here.
- A second sign-in system beside relief's. Relief's personal codes become one of the ways in of this design.
- Student accounts with passwords. Students use their personal code or Google.

## Anti-goals (a failure even if it works)

- Any route that changes something is reachable by a person without the right, by calling it directly.
- A password, a one-time password, a personal code or a Google token appears in the history, a log or a download.
- The history says something happened that did not, or misses a change that did (a change applied with no entry).
- "Put back" overwrites a later change by someone else.
- The school is locked out: no admin can sign in and there is no way back.
- Student or staff emails or names sent to any outside service other than Google's own sign-in.

## Who's who

Every member of staff is one **person** on one list: the teachers of the published timetable plus staff added by name
(relief's `extra_staff` today). Students are the Students list of the published timetable. Each person has one
**group** and any number of **extras**.

| Group | Signs in with | Sees | Can change |
|---|---|---|---|
| **Timetable committee** | username and password, or Google; their personal code without the setup and admin page | everything; the full history | everything; the admin page only with the Admin extra |
| **School leader** (management) | username and password, or Google; or their personal code | every published timetable (classes, teachers, rooms, students, lessons, Who's free) | plan relief for a colleague (relief's Management) |
| **HOD / SH** (management) | username and password, or Google; their personal code without the setup | as a school leader, plus the setup steps a head sees today (greyed where not theirs); the history of their department | their departments' rows on step 5 (department map), groups and bands holding their lessons, add teachers (provisional, in their department); plan relief |
| **Teacher** | personal code, or Google | what `TEACHER_CODE` opens today; their own relief | ask for relief, set work, acknowledge a relief (relief's own rules) |
| **Executive** (staff who do not teach) | personal code, or Google | the published timetable, as a teacher sees it | nothing |
| **Student** | personal code, or Google | their own timetable (what a personal student code opens today) | nothing |

**A personal code opens everything except the setup and the admin page** (the lead's answer to the builder check:
"All but setup and admin"). Committee and management members also hold a personal code slip (relief's). Signed in
with it, they get everything their group and extras give **except** the committee page and the setup steps (seeing or
changing steps 1 to 9 and the Students step, heads' changes to step 5 included) and the admin page; those need their
password or Google. So their code still opens the timetables, relief (management's planning, the relief team's pages)
and the exams pages. The tiles page shows the committee page and admin tiles as "Sign in with your password or Google to
open this". Rights therefore depend on the group, the extras **and** how the person signed in; the route test covers
each way in.

**Extras**, given on the admin page to any person whatever their group:
- **Relief team**: relief's team pages and settings (relief's `team` list today).
- **Exams and events committee**, with an **end date**: the exams pages (exams' `committee` list). On the end date
  the extra ends by itself and the history records it.
- **Admin** (committee group only): the admin page. The lead named "Named admins only": the lead plus one backup.

Rules taken from the conversation:
- "School Leaders, HODS and SHs are management." Management does **not** get the committee's rights ("they not be able
  to have the same previlege as Timetable committee, they can see all teh teachers anda students timetable and they
  may have access to exam and event committee dependening").
- A head changes **only their own department's** part of the map (the lead chose "Own department only"). Their
  departments come from step 4 (`dept`, and `dept2` if set) and can be changed on the admin page.
- An SH gets the same rights as an HOD over the whole department (proposed, not objected to).
- Executives: "view only for timetable".
- Teachers on the exams and events committee "need temp access": the extra with an end date.
- The Class Parents' lessons stay the committee's, as today (`sync._head_lessons_why`).
- Steps 7 to 9 and the Students step stay committee only, as today (`HEAD_HIDDEN`).

**What a head may change, exactly** (extends `sync._head_why`, judged one operation at a time under the store's lock,
as today):
- A lesson row: only when its department is one of theirs, both as the row is and as the operation would leave it
  (a head cannot move a row into or out of another department). A row's department is its subject's department.
- A group or band (`blocks`): only when it holds at least one lesson of their departments. A band shared between
  departments may be changed by each head with a lesson in it; the history shows who. (Proposed, not objected to.)
  **Design's call** (from the builder check): a head may **create** a band (it holds no lessons yet). A head may
  **rename or delete** a band only when every group in it is of their departments; a band holding another department's
  groups is renamed or deleted by the committee, and the head is told so. A head's change to a band and the groups it
  carries along (a rename rewrites every group's `block`; a delete drops or releases them) is judged **as one**: all of
  it is applied or none of it, so no other department's group is left pointing at a band that is gone. Everything else
  a head sends is still judged one operation at a time, as today.
- Adding a teacher: provisional, as today, and their department is one of the head's.
- Everything else refused with a sentence, as today. The page greys other departments' rows; the server refuses them
  anyway.

## Ways in: the sign-in page (mockup tab 1, layout A chosen)

One page for everyone (the lead chose A over cards):
- **Sign in with Google**, shown only when `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` are set.
- **Your personal code** box (staff and students).
- A link "Committee and management: sign in with your username" to a username and password page.

After signing in, a person sees only the tiles they may open (Committee page, Timetables, Relief, Exams and events,
Admin); with one tile it opens at once. The "Since you last signed in" panel shows on that page.

**Google sign-in**
- Asks Google only for name and email (`openid email profile`), so no Google review is needed beyond the optional
  brand check (which shows the school's name and logo on Google's screen).
- The app accepts a Google account only when its email is verified, its domain is in `GOOGLE_DOMAINS` (a Railway
  variable; the school's domains never appear in the repository), and the email is on a person's or a student's entry.
  An unknown email gets "Your Google account is not on the school's list. Ask the timetable committee." and the try is
  recorded.
- Emails get onto entries by **Upload emails** on the admin page (staff: name and email; students: Student ID and
  email) or typed on one person's panel.

**What the lead (or school IT) does for Google, outside the app.** The app shows these steps on the Ways in tab:
1. An address on a domain the school controls. Google turns down Railway's own `*.up.railway.app` addresses. Either
   a domain bought through Railway (attached by itself; Railway manages its DNS, so Google's ownership check may need
   the file method, which the app can serve from a Railway variable) or an address under the school's own domain added
   by school IT (looks official to students and parents).
2. A Google Cloud project and a web OAuth client with that address's `/auth/google/callback` as the redirect. "Internal"
   if every user is in the school's own Google Workspace; "External" if students are on another organisation's
   accounts (MOE's Student iCON). Published to production (testing allows only 100 named users).
3. For students under 18: Google blocks unapproved outside apps by default; the admin of the students' Google accounts
   must allow the app (for iCON that admin is MOE, not the school). Until then students use their personal codes.
4. `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_DOMAINS` set as Railway variables, then "Deploy Latest Commit".
   The app never shows the secret.

**Personal codes** (relief's, unchanged for slips already printed):
- Staff codes stay made from the name and `SECRET_KEY` (`access.staff_code`); student codes from the Student ID
  (`access.personal_code`). A person may get a **new code** from the admin page: a number kept on their entry is added
  to what the code is made from (number 0 gives today's code, so no printed slip changes), and the old code stops
  working at once.
- A code opens the person's group rights and extras except the setup and the admin page (above): the exams pages for a
  teacher with the extra, relief planning for management.

**Username and password** (committee and management; anyone else only if the admin gives one):
- Username set by the admin, suggested from the name (`daniel.wong`), compared ignoring case.
- New account or reset: the admin sees a one-time password once ("Shown once. Give it to …"); the person picks their
  own at the next sign-in. Anyone can change their own password.
- At least 10 characters; not the username or the name; not one of the commonest passwords (a short list kept in the
  app). No other rules.

**Shared codes** (design's call after the builder check, replacing "the committee code stops at the first admin",
so nobody is cut off between the deploy and having an account)
- Every shared code keeps today's rights until an admin presses **Turn off** for it on the Ways in tab, which shows
  how often it was used this week. The lead: "each teacher and each student should have their own code".
- `COMMITTEE_CODE` is how the lead makes the first admin account (the admin page offers "Make the first admin" only
  while no admin exists). Changes made with `COMMITTEE_CODE` or `HEADS_CODE` while they are on are recorded under
  "Shared committee code" or "Shared heads' code", so the history shows they were nameless; the Ways in tab and the
  committee page warn while either is on and an admin exists.
- `TEACHER_CODE` and `STUDENT_CODE` never could change anything; their sign-ins are counted and recorded.
- While `SECRET_KEY` is not set, accounts cannot be made and the shared codes work exactly as today.

**Getting back in.** An admin cannot switch off or demote the last admin. If every admin forgets their password, the
lead sets a Railway variable (`ADMIN_RECOVERY_CODE`): while it is set, the username page accepts it once, with an
admin's username, to set a new password; the use is recorded and the Ways in tab warns until the variable is removed.

## The admin page (mockup tabs 2 and 3)

Admins only. Tabs: **Staff**, **Students**, **Ways in**, **History**.

**Staff**: the list of people (name, group, departments, extras, last signed in, switched off), with search and
filters (group, department, extra). A hint uses step 4: "5 teachers are HOD or SH on step 4 but still in the Teacher
group: Make them management"; "3 staff have no Google email yet: Show them".
- **One person's panel**: group; "Changes the map for" (departments, ticked from step 4); extras (Relief team; Exams
  and events with an end date; Admin); ways in (Google email, username, personal code); buttons Reset password,
  New personal code, His/Her changes (the history filtered to them), Switch off.
- **Ticking several** (the lead asked for it): tick boxes on rows and "Tick all shown" after a filter. A bar offers
  give or take away an extra, set group, print their code slips, switch off. Before it applies it says exactly what
  will happen, naming each person and anything already so ("Ravi Kumar has it already: his end date moves"). It is
  one history entry naming everyone, put back as one.
- **Add a person** (staff who are not on the published timetable: an executive, a non-teaching Vice-Principal).
- **Upload emails**, **Print code slips** (relief's slips and CSV, moved here).

**Students**: search by name, class or Student ID; Google email; last signed in; new code; print slips; upload emails.
No groups or extras.

**Ways in**: each way in with its state (Google set up or not and the steps above; personal codes on; how many
password accounts; each shared code on or off with its use this week and Turn off; recovery variable set or not;
`SECRET_KEY` set or not).

**History**: the full history (below).

Switching a person off, resetting their password, giving them a new code or changing their rights signs them out
everywhere at once.

## The history (mockup tab 4)

**What is recorded** (one entry per change, at the moment it is made, never edited afterwards):
- Every setup change: who, when, how they signed in, which step, which row, which field, what it was and what it
  became. Recorded inside `store.apply_changes`, under the same lock, from the setup as it was before the operation;
  the operations a head may not make are recorded as refused, with the sentence they were shown. The Class Parents'
  lessons the app sets by itself are entries by "The app", tied to the change that caused them.
- Whole-setup events: a workbook uploaded, the setup replaced or restored from a saved copy (the saved copies now
  record who made them).
- Step 8: a timetable uploaded, each fix and undo, each decision; publishing (step 9).
- Relief and exams (design's call after the builder check): **every save** in them gets one entry naming who, what kind
  of thing and which one ("Mid-year exam: invigilators changed", "Relief settings: limits saved", "Relief for 3B on
  12 Jan approved"), with a link to it; not field by field, and no Put back (they are undone on their own pages, under
  their own checks). This covers relief settings, exams settings, an exam's create, edit, delete, Make, moves,
  invigilators and "use anyway", and, as they are built, relief's requests, picks, approvals and cancellations and
  exams' sent, approved, sent back and withdrawn. Relief and exams keep their own detailed records as their designs say.
- Accounts: a person added, group or extras changed, an extra ended by its date, password reset or changed, switched
  off or on, a new code, emails uploaded, a shared code turned off, the recovery code used.
- Sign-ins (who, how, from which device's address) and failed tries (by username or code kind; never what was typed).

**Never recorded**: a password, a one-time password, a personal code, a Google token, a student's or teacher's email
in a sign-in failure (only "a Google account not on the list, from domain X").

**Who sees it**
- Committee: everything, with filters (who, where, department, dates, sign-ins shown or hidden) and Download (Excel).
- HOD / SH: the changes to their departments' rows by anyone, and their own changes.
- Everyone else who can change something: their own changes.

**Since you last signed in**: on the page after signing in, a summary from the person's previous sign-in to now,
grouped by person and step ("41 changes by 4 people since Tuesday 4:12 pm"), opening into the history. A committee
member sees everything; a head sees their departments; everyone sees "The timetable was published again on …" when it
was.

**Put back** (the lead chose "Put back one change"):
- On a setup change and an account change. It makes the change that returns the field (or row) to what it was, as a
  new entry by the person who pressed it, through the same checks as any change (a head can put back only what they
  could change).
- Only when nothing later touched the same thing (the same row and field; for an added or deleted row, the row). Else
  it is greyed with the reason: "Can't put back: Daniel Wong changed this again on 19 Nov, 10:02 am".
- A change of several people at once is put back as one.
- Step 8 fixes, publishing, relief and exams show a link to their own page ("Undo it on step 8"), where they are undone
  under their own checks. Whole-setup replacements go back through the saved copies, as today.

**Kept for two years**, then the oldest entries are dropped.

## Security (checked by the builder and the review)

- Passwords stored only as a slow, salted hash (Werkzeug's `generate_password_hash`, scrypt, already installed with
  Flask). One-time passwords the same. Never logged, never in the history, never sent back.
- Wrong tries: the existing limiter (10 wrong codes per address per 10 minutes) covers passwords too; plus 5 wrong
  passwords on one account and that account waits 15 minutes (the wait is recorded). The same answer for an unknown
  username and a wrong password.
- Sessions stay Flask's signed cookies with `SECRET_KEY`. Accounts are refused while `SECRET_KEY` is not set (the Ways
  in tab and the sign-in page say so). The session holds the person and a sign-in number kept on their entry; a reset,
  a switch-off, a new code or a rights change raises the number and every older session ends. Rights are read from the
  list on every request, never from the cookie. Password and Google sessions last up to 14 days; code sessions as today
  (120 days).
- Every route declares the right it needs (`@need` becomes a check of rights, not of a role name); the page hides what
  a person may not do, but the server decides. A test walks every route of the app for every group and checks the
  answer.
- Changes from the page are JSON calls; they keep requiring the session cookie (SameSite=Lax) and also check that the
  request comes from the app's own address, so another site cannot make a signed-in person's browser send one.
- Google: the standard OpenID Connect code flow with a state value and the ID token checked (issuer, audience, expiry,
  verified email). A well-known library rather than hand-written checks.
- The names and emails uploaded are checked for spreadsheet formulas, as relief's names are.

## How relief and exams fit

- **People**: relief's people (`relief.people.people`) become this list's source; `extra_staff` moves to the admin
  page's "Add a person". Relief and exams keep using the person's name as they do now.
- **Relief's Management list** becomes the management groups (school leaders, HOD, SH). **Relief's team list** becomes
  the Relief team extra. **Exams' committee list** becomes the Exams and events extra (with an end date). Relief's and
  exams' settings pages stop showing those lists and link to the admin page; their rights functions
  (`app._relief_rights`, `app._exams_rights`) read from the accounts.
- **Codes**: relief's slips, CSV and `staff_code` stay; a new code per person is added.
- **Telegram** (relief stage 2, not built yet): linking by personal code still works; with Google, the bot linking
  needs a code the app shows to the signed-in person. Left to relief stage 2.
- On the first start after this is deployed, the existing lists are turned into groups and extras (a person on relief's
  Management list and a HOD/SH on step 4 becomes HOD/SH; a Management person who is not becomes School leader), and
  the admin page shows what it did for the lead to check.
- Exams stage 1 (PR #79) is not merged yet: whichever merges second moves its committee list to the extra.

## What is kept

In the app's data folder on the Railway volume, beside the setup and relief:
- `accounts/people.json`: each person's entry (name, group, departments, extras with end dates, username, password hash,
  must-change flag, Google email, code number, sign-in number, last two sign-ins, switched off). Students' emails and
  code numbers in `accounts/students.json`. Written whole, atomically, under a lock, as the other JSON files are.
- `history/YYYY-MM.jsonl`: one line per entry, appended; one file a month; files older than two years removed.

## Approaches considered

- **A. Everything inside the app.** People, rights and history in the app's data folder; passwords hashed with what
  Flask already has; Google's standard sign-in. No new service or cost; student and staff emails stay in the school's
  app. Resets go through an admin (no email). **The lead chose A.**
- **B. An outside sign-in service** (Auth0, Firebase and the like) keeps accounts, passwords and Google, and emails
  resets; the app keeps rights and history. Every staff and student email with another company, usually overseas;
  another account to look after; the free tier may not cover about 1,400 people; rights, the admin page and the history
  are built either way.
- Dropped: keeping the shared codes and asking people to type their name (anyone could type anyone's name, so the
  history could not be trusted).

## Stages

Each stage is its own plan, build, review on made-up data, notes file and pull request; merged and deployed only on the
lead's word.

1. **Accounts, rights and the history.** The people list and groups; username and password; the sign-in page (layout
   A, without Google); the tiles page; the admin page (Staff, Students, Ways in; ticking several); rights checked on
   every route; heads to their own departments; the first admin and the committee code stopping; the recovery variable;
   relief's and exams' lists moved; the history recorded for everything listed above and the History tab with filters.
2. **Put back and "Since you last signed in"**, the head's and each person's view of the history, Download (Excel), the
   two-year keeping.
3. **Google sign-in**: the button, the callback, Upload emails, the Ways in steps, the domain file.
4. **Codes for everyone**: a new code per person, students' Google emails, Turn off for the shared teacher and student
   codes with their use counted.

## Left to the builder

- The exact rights names behind each tile and route, and the table of every route against every group (the test).
- How the page greys another department's rows and bands (the server's refusal is the rule; the page follows).
- The Google library (Authlib or similar) and its pinned version; the callback path.
- The short list of common passwords.
- The wording of every sentence, in the app's plain style.
- How a renamed teacher on step 4 keeps their entry (proposed: the admin page shows "no longer on the published
  timetable" with a way to link the entry to the new name; their history stays under the old name).

## The calls made in the design, not by the lead (check these while reading)

- SH rights = HOD rights over the whole department.
- A band shared by departments can be changed by each head with a lesson in it.
- A teacher added by a head goes into the head's department.
- Each person sees their own changes; heads see their departments' changes; school leaders see no setup history.
- Password rules: 10 characters, no common passwords, 5 wrong tries then 15 minutes, 14 days signed in.
- Every shared code (committee and heads' too) keeps working until an admin turns it off; changes made with one are
  recorded as "Shared committee code" or "Shared heads' code". (Earlier proposed: the committee code stops at the first
  admin; changed so nobody is cut off before they have an account.)
- A head may create a band; renaming or deleting a band holding another department's groups is the committee's; a
  head's band change is applied whole or not at all.
- Relief and exams saves get one entry each (who, what, which, a link), not field by field, and no Put back.
- The Admin extra only for the committee group; the last admin cannot be removed; the recovery variable.
- History kept two years; sign-ins recorded; Put back only on setup and account changes.
- Students have no passwords; their code and Google only.

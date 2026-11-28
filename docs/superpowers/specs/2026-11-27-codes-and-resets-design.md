# A forgotten student code or staff password: a person helps

Date: 27 November 2026. Status: **approved by the committee lead on 27 November 2026** ("Approved, plan it"). A short
design (a small change). Builds on the staff passwords design of 26 November 2026
(`2026-11-26-staff-passwords-design.md`).

## Intent and the why

The lead asked that students may change their code on their first try and that teachers may reset their password or
code. Asked why, the lead said: "They may forget the code, at least the teacher can reveal for them if they forget."
So the need is a forgotten code or password, met by a person on the spot, not a student-chosen code.

- A student's code is worked out from their Student ID and `SECRET_KEY` (`access.personal_code`), nothing is stored,
  and the code alone signs in. A code a student picked would have to be unique and hard to guess; looking up the
  existing code avoids both.
- A teacher who forgot their password has no second way to prove who they are (no email on the records; Telegram only
  for relief, and off). A person who knows them vouches instead.

## The lead's answers (27 November 2026)

- Who may look up a student's code: **any staff member** (not "form teachers" or "teachers who teach them").
- Who may give a teacher a new temporary password: **their HOD or SH** (as well as the admins, as today).

## Goals

1. **Student codes** (any member of staff signed in by name, by password or, while staff codes are on, by staff
   code): a home page tile opens a page where they pick a class, see its students, and press **Show code** beside one
   to see that student's code. The code is the one on the slip; nothing changes for the student.
2. **Reset a password** (an HOD or SH signed in with their password): a home page tile opens a page listing the staff
   in their own departments, each with **Reset**. Reset shows a new temporary password once; the teacher signs in with
   it, must choose their own (the existing "must change" step), and any old sign-ins end.
3. The admins keep their own Reset on the People tab, unchanged.

## Non-goals

- Students choosing or changing their code.
- A reset by email, Telegram or a security question.
- Changing one student's code (it cannot change without changing every code).

## Anti-goals

- **Every code in the browser at once.** A code reaches the browser only for the one student whose Show code was
  pressed. (Ruled out for this reason: codes inside the published timetable page.)
- **A head takes over a more powerful account.** An HOD or SH cannot reset their own password, an admin's, a School
  leader's, another HOD's or SH's, or a switched-off person's; those go to an admin.
- **A code or password in the history or a log.** The history records who looked up whose code and who reset whose
  password, never the code or the password.

## Decisions (the design's calls, the lead may change them)

- Each Show code is one history entry ("Looked up the code of Sam Student (1A)"), kind `look`, where "Student codes",
  so a misused code can be traced. Not a change: it does not count in "Since you last signed in".
- Students, and anyone signed in with a shared code, cannot open Student codes.
- The class list comes from the published timetable's students; a class with no students says so. Without
  `SECRET_KEY` the page says personal codes are off (as the slip printing does).
- A head signed in with a staff code sees Reset a password greyed, "Sign in with your password to open this", as the
  committee page and the admin page are.
- A person a head resets who has no username yet gets one made as the slips make it (`accounts.slips.make_username`).
- Each reset is one history entry, as the admin's Reset writes it, with the person's departments so it shows in the
  heads' department history.
- Pages are server-made forms in the sign-in pages' style (`static/login.css`), answered with `Cache-Control:
  no-store`; posts pass the existing same-site check.

## Approaches

1. **Two small pages from the home page tiles (chosen).** Only the one code or password asked for ever leaves the
   server, and each is recorded.
2. Codes inside the published timetable page: every student's code would sit in every teacher's browser. Ruled out.
3. A narrowed admin page for heads: the admin page holds far more than heads should reach. Ruled out.

## Left to the builder

The exact layout of the two pages within the sign-in style; the right names (`codes.look`, `staff.reset` are
suggested).

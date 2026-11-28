# Notes: student code look-up and head password resets (27 November 2026)

Built subagent-driven on branch login-boxes: three tasks, each reviewed; a whole-branch review (one critical finding,
fixed); one fix round, re-reviewed; a browser check on made-up data.

## Rulings made during the build (each with what it costs if wrong)

- A head may reset only someone whose rights by password are a subset of the head's own, besides the design's
  exclusions. So anyone with the Timetable committee, Relief team, admin or a current Exams and events tick goes to an
  admin. Found by the whole-branch review: before it, a head could reset a teacher on the Timetable committee and reach
  the committee page. Cost if wrong: a teacher with a current exams tick asks an admin.
- A head's reset ends the teacher's staff-code session too, as the design says ("any old sign-ins end") and as the
  admin's Reset does. Cost if wrong: the teacher signs in again with the new password.
- Staff not on the published timetable have no departments, so only an admin can reset them (README says so).
- Pressing Show code again (or reloading after it) writes another look-up line in the history. Cost: a few extra lines.
- Show code with no SECRET_KEY or nothing published answers the notice with 200, not 404.
- Left as they are (correct, or unreachable): one long condition in student_codes_show; no test of the page without
  SECRET_KEY (no one can be signed in by name then); the person just reset stays in the list; the success page reads
  the accounts again (people.load never raises); the 503 path; a person in the old "committee" group without the tick
  can be reset (they have a teacher's rights).

## Browser check (made-up data, scratch server)

A teacher by password sees the Student codes tile and no Reset tile; classes wrap as small buttons ("1 A&B" opens
correctly); a 40-student class is a compact list; Show code shows that one student's code in a box at the top. An HOD
(English) sees the English teachers, not themselves and not a teacher with the Timetable committee tick; Reset shows
the username and temporary password once. The Reset rows were given the compact layout after this check.

## Not checked

A real phone; the History page's Where filter in a browser (in code and the node test only).

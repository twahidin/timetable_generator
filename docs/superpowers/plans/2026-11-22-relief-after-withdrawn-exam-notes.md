# Relief after an exam is withdrawn: notes

Asked by the lead on 22 November 2026 ("Yes, fix it"), from a point the relief session found while building stage 4. Branch
`exams-withdrawn` from main 9fa041b. No plan of its own: one rule of `2026-11-22-exams-relief-join.md` (J1) carried through.

## What was wrong

A lesson an approved exam or event stops is never written as stopped: it is worked out on reading, so withdrawing the exam puts
everything back (J1). `absences.new()` broke that. An absence sent while the exam stood wrote such a lesson "Not needed", so when
the exam was withdrawn the lesson happened and nobody was asked to cover it.

## What changed

- `new()` keeps a stopped lesson needed, as any other (the client or a co-teacher may still say not). A relief chosen for it on a
  page opened earlier is left out, not refused. The pages showed "Not happening" already and still do.
- **An absence whose lessons all stop is taken** (it was refused with "There are no lessons to cover in that time."): the exams
  committee sees the person is away, and the lessons are there if the exam is withdrawn. With no lesson at all it is still refused.
- A lesson no longer on the timetable under the key the absence holds (a publish moved it or renamed its group) is read by its own
  periods and classes, so a publish does not make a stopped lesson run.
- A stopped lesson of one's own takes no time from a relief one covers.
- The exams page says "Not happening" before "Sent to relief" for a lesson both hold.

With it, the relief session's three smaller points:

- `Links.unread(date)`: a schedule's file or its own dates, the date, or the duties of a schedule holding it could not be read. For
  stage 4, which sends nothing about stopping for such a date. Nothing on main asks it yet. Links never raises on damage now.
- Acknowledge, Request to change and Keep refuse a stopped lesson, as Approve and Change do.
- A cancel by the app ("Moved to X's own absence.") reads "Cancelled: ...", not "Cancelled by app: ...".

## Checked

- Independent review: none Critical, one Important (the key changed by a publish), six Minor; a re-review: five Minor. Fixed except
  those below. A damaged duty no longer hides its schedule's others, and a sync leaves the backups as they are when a date it needs
  could not be read. Deliberate single-line breaks (40) each fail a test.
- Browser, made-up school, real clicks: the form with its only lesson stopped, sent; My absences ("Not happening"); Today before
  (not happening, nothing to cover) and after the exam was withdrawn (one lesson, no relief teacher yet, Choose).

## Known limits

- A co-teacher who is on the exam's own duty when the absence is sent counts as not there, so after a withdrawal the lesson asks for
  a relief although the co-teacher is back: the relief team approves every pick and can mark the lesson not needed.
- A past lesson an exam stopped shows as open once that exam is withdrawn (it must be before it can be deleted): the stop is worked
  out, for past dates too. Nothing is picked for a past lesson.
- If the exams cannot be read, relief works as if there were none (J8), for these lessons too.
- A class renamed by a publish is not on the exam's list under its new name, so a stopped lesson of it reads as running until the
  exam is sent and approved again.
- An absence whose lessons all stop and none of which is needed (a co-teacher is there) can be sent twice, as one with only a duty
  could be; the exams committee then sees "is away then" twice.
- `Links.unread` does not know a damaged duty dated outside its schedule's own dates, and an approved copy that is no schedule at
  all makes `Links.load` fail, which callers read as "no exams can be read".

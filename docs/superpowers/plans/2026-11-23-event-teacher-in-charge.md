# Changing an event's teacher in charge: plan

Asked by the lead on 23 November 2026 ("Yes, build it"). Open point K10 of `2026-11-21-exams-stage-4-notes.md`: an event's teacher in
charge is kept for everyone, so when they leave or are away for long nobody can be put in their place. It waited for the accounts,
which are in main. Branch `events-in-charge` from main f39b518.

**Goal:** the timetable committee gives an event to another teacher in charge.

## Decisions

- **T1. The timetable committee only** (the committee right: the shared committee code, or a committee member signed in with their
  password). The teacher in charge asks them; the exams committee does not manage events.
- **T2. Anyone relief and exams know** (the published timetable's teachers and the staff added in the accounts), as when the committee
  starts an event for someone; not the one in charge already.
- **T3. It goes on at once**, in the working copy and in the approved copy, and waits for no approval: the committee that approves
  events is the one changing it. A sent event stays as sent (its fingerprint moves with it), and nothing is listed as a change waiting.
- **T4. The event goes with it.** The new teacher in charge opens it and changes it; the one before no longer does (a save from a
  page left open is refused, as for any event not theirs). Who is going, and the duties at the event, stay as they are: being in charge
  is not going.
- **T5. In any state**, ended events too.
- **T6. Relief follows.** The backups of the event are by its teacher in charge: the sync that runs after every step brings them to the
  new one. A colleague's absence form names the new one ("... replaces you").
- **T7. Written down:** one History entry, "<event>: teacher in charge changed (A → B)", and one line in the event's own log.
- **T8. Nobody is told** by message: there are none yet.

## Files

`exams/approval.py` (`set_in_charge`), `app.py` (POST `/api/events/<id>/in-charge`, the step's words), `static/exams.js` (Change beside
the name in the event's heading, for the committee), `README.md`, `tests/test_exams.py`, `tests/test_exams_relief.py`,
`tests/test_routes.py`.

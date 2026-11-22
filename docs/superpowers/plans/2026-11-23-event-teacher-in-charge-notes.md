# Changing an event's teacher in charge: notes

Built 23 November 2026 on the lead's "Yes, build it", on branch `events-in-charge` from main f39b518. Plan and decisions T1 to T8:
`2026-11-23-event-teacher-in-charge.md`. It closes open point K10 of `2026-11-21-exams-stage-4-notes.md`.

## What it gives

In an event's heading the timetable committee sees **Change** beside the teacher in charge. It opens a list of everyone relief and
exams know; **Put them in charge** gives them the event at once, in any state, with no approval. The one before no longer opens it, and
a save from a page they left open is refused. A waiting event stays as it was sent and can be approved; nothing is listed as a change
waiting. The main site, colleagues' absence forms ("... replaces you") and the event's relief backups name the new one. One History
entry, "<event>: teacher in charge changed (A → B)", and a line in the event's log. Who goes, and the duties, stay as they are.

## Rulings (each with what it costs if wrong)

1. The timetable committee only, not the teacher in charge (T1). If wrong: one condition in the route.
2. At once, with no approval (T3): the committee that approves events makes the change. If wrong: the step is removed from the approved
   copy and the fingerprint.
3. The page changes only the heading and the name, with one request of its own: a send-back note, an edit being typed or an open fold
   on the tab below is not touched. If wrong: nothing; `approvalAction` would have done it and lost them.
4. Someone whose account is off is on the list, as when the committee starts an event. If wrong: one filter, in both places.

## Checked

- An independent review: none Critical, two Important (the page wiped a typed send-back note, and could drop an edit typed while the
  change was on its way), seven Minor; fixed except the limits below. A re-review of the fixes: one
  Important (the page took the keyboard focus from someone typing on the tab below) and four Minor; fixed, but for the one in the
  limits. The last fixes were checked by their tests and not reviewed again.
- Deliberate single-line breaks, on the server and on the page, each fail a test.
- Browser, made-up school, real clicks: no Change for the teacher in charge; for the committee, the list without the one in charge,
  the change with an unsaved edit kept, on a waiting event with a note typed (kept) and then approved; the event gone from the old
  teacher's list ("Only the teacher in charge and the timetable committee can open this event.") and on the new one's; phone width.

## Known limits

- Nobody is told: there are no messages yet.
- Backups that are cancelled, or past ones of a withdrawn event, keep the name they were sent by, so they stay the old teacher's to open.
- A waiting event with an edit not sent yet must be sent again after a change, even if the edit is undone: what was sent is kept as a
  fingerprint only.
- After a change the tab is drawn again, as after every save, so an open "Or pick classes" with nothing ticked closes.

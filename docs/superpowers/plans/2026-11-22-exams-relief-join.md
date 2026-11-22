# Exams stage 3 meets relief stage 3: plan

Asked by the lead on 22 November 2026 ("continue on to next stage") after exams stages 2 and 4 were merged (PRs #81, #82).
The exams design says its stage 3 "needs relief stages 2 and 3": stage 3 (PR #85) was built on relief stage 2, and relief
stage 3 (PR #88) was built beside it. This joins them. Branch `exams-relief-join`: exams-stage-3 (07b002a) + main (a5ca928) +
relief-stage-3 (d693183).

**Goal:** the relief team's module (picks, approval, Today, Reliefs I'm covering, Load) knows approved exams and events, and
the exams side knows which reliefs have been approved.

## Decisions

- **J1. A lesson an approved exam or event stops is not picked for and not approved, and its relief takes nobody's time.**
  Worked out on reading (`Links.stopped`), never written: withdrawing the exam puts everything back as it was. Today lists it
  as "Not happening: …" outside the counts; What's in does not count it; the planned relief sheet says "Not happening: …" in
  the relief teacher's column; Reliefs I'm covering shows "Not happening: …" without buttons. Approve, Approve all, Change
  and a saved pick refuse it: "This lesson is not happening: {why}."
- **J2. Someone on an exam duty or at an event is never picked, approved or changed to** (`free_then`'s `links=`, carried
  through `cover`, `pick`, `fill` and the routes). A waiting pick of theirs goes back to open and is picked again; an approved
  relief stays, flagged "is no longer free then: change it", until the team changes it, as for any other reason.
- **J3. Own absence takes over a backup with its whole cover** (relief, relief_by, pick, approved, ack, change, history,
  parts). A planner's choice on the new absence replaces a pick still waiting (written down as dropped). It is refused, as
  `choose` refuses it, when the relief team has approved someone else or split the lesson, naming the lesson. A lesson the
  new absence says needs no relief ends its cover, with the reason, as "not needed" does.
- **J4. A lesson that leaves a backup** (the duty changed, "Handled ourselves", withdrawn) has its cover cleared first (the
  relief written down as dropped) and is kept, without its work, in the record's `gone` list, so no history is lost and stage 4
  can tell the relief teacher.
- **J5. The exams side counts approved reliefs only**, each part of a split lesson by its own periods, and shows a relief
  teacher's name only once approved (relief's Decision 4). A pick still waiting is relief's to make again. A relief on a lesson
  that another approved schedule, or this one, stops holds nobody.
- **J6. Load's "Week so far" and the numbers the AI is given count exam duties and events and leave out lessons that stop**
  (the lead's decision of 21 November: invigilation counts in relief's week so far). Load gets a column "Exams and events".
- **J7. Today says when the "absent" teacher is on a duty** ("Invigilating: …" or "At event: …"), since they are in school.
- **J8. If the exams cannot be read, relief still works** (as if there were none), with one log line.

## Files

`relief/free.py`, `cover.py`, `pick.py`, `fill.py`, `absences.py`, `web.py`; `exams/relief_links.py`, `exams/schedules.py`;
`static/relief-today.js`, `relief-covering.js`, `relief-load.js`; `README.md`; `tests/test_exams_relief.py`.

## Left out

Telling anyone (stage 4 of relief). Picking at once when an exam approval sends a backup for today: the ticker picks it up
within a minute. A part of a split lesson that an exam stops while another part runs: a lesson counts as running while any of
its periods runs, as in stage 3.

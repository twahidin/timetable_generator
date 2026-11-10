# Wizard stage 5: decisions made while building, and what was left

From the build ledger of `2026-11-10-wizard-stage-5-groups-and-bands.md`. Built inline (one executor), with one fresh whole-branch review at the end and one fix pass.

## Rulings (decisions made where the plan was silent or wrong)

- Task 4: a row moving into a band and getting its first code ("Entire Class" → 1AR1) is not a renumbering. The move messages and the student-list question list only codes that existed before. Cost if wrong: a head reads the new codes on the lane rather than in the toast.
- Final: a Keep-code group joining a band loses its kept code and takes the band's numbering; otherwise its old code and the band's next number collide ("Code used twice"). The move reports the change. Cost if wrong: a school with deliberate old codes inside bands retypes them in Keep code.
- Final: `Groups.codes` counts a banded row that keeps its own code, exactly as the table does (the review's one critical finding: without it, moving such a group renumbered others silently and made a duplicate code).
- Final: a new group with no band for fewer students than its classes hold, and a group taken out of a band, get a kept code as the table's rule gives it; the form's code line predicts it.
- Final: a new band stores "Everyone takes one" only when the box was set; otherwise the name decides (option, elective), as the table does.
- Final: moves that renumber codes named by Group rules on step 6 ask first, like codes named by a student list.
- Final, left as they are (the reviewer set them aside; each stands): the table can still make a duplicate code by hand (Things to fix flags it); quick saves merge into one Undo entry; a held remote change is applied at the next change or sync after a form pop-up closes; the forms column was checked at laptop width only.

## Deferred minor points

- `shift` recomputes the codes once per row (quadratic); harmless at 200 rows.
- A band renamed or deleted in another browser leaves the "Move into band" select and the group form's band stale until used again.
- After "Add band", the pool's level is not switched to the new band's level.
- The classes pop-up offers other levels, which the new-group form and "Add one per class" accept; a new group made with a band does not widen the band's classes (moving a row in does).
- "Add one per class" adds whole-class rows for a subject the level already has in a band.
- Pool ticks have no shift-click run (Select all shown covers the long-list case).

## Not exercised in a real browser

- A real head-of-department sign-in (the role was set from the console): the view with no read-only notice.
- Real mouse drags: drag and drop was driven with synthetic drag events.
- A tablet: the layout was checked at 1440 px only.
- The user's own school: only the sample school (22 bands, 194 lesson rows) was used; the sample has no Keep-code rows, so those were checked with rows made in the practice copy.

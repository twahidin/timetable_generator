# Teacher rename, stage 1: notes

For whoever builds stages 2 and 3 (the account, reliefs and exam duties follow the new name) and for the lead. Design: `docs/superpowers/specs/2026-11-24-teacher-rename-design.md` (stage 1 is Parts 1 and 2).

## Rulings

- The browser check was done by the controller, not an implementer: one shared browser pane, and it would be repeated anyway.
- `TeacherView.settle` runs in `save()` only when the page is not a head's, as `Parents.settle` does: on a head's page it would change other departments' teacher rows, which the server refuses and reports as a change the head never made.
- No guard inside `rename()` for a head: a guard puts a rights question into a pure function for a rare case, and the server refuses that op anyway. Cost: a possibly confusing "refused" toast.
- The latest rename wins when two rows share an old name: an earlier name already on a later row does not beat the renaming row.
- Toasts stay as long as their length needs (3200 ms up to 60 characters, plus 45 ms per character, at most 12000 ms), so the long rename sentence can be read.
- History shows "earlier_names" in a page word (`FIELD_WORDS` in `static/history.js`), so the raw key never shows; the stored `field` is unchanged.
- The suites were run by the controller on the final code, once, not by each task.

## Known limits

- Typed sentences (rules, notes) keep the old name; the message names them for a person to check.
- Replacing the whole setup from a workbook drops `earlier_names`, so a draft made before that no longer follows.
- Two people changing one teacher at once is best effort.
- A head's rename can leave another row's `earlier_names` in place, or be refused a change to it (the server ignores an earlier name that is in use; the next committee save settles it).
- `settle` does not run from `save()` on a head's page.
- History stores the field as the key `earlier_names`; only the page's word differs.
- Toasts now stay longer when long, for every toast, not only this one.
- Minor, left as is: `uses` matches a name exactly as stored, spaces included; the handler and `rename()` each clean the new name (two copies of one rule); `fixes.apply` works the rename map out again.
- Not built: the account (role, committees, username, password, Telegram link), reliefs and exam duties still stay under the old name; the new name needs a new code slip.

## Checked in a browser

By the controller, with real clicks and typing, on a scratch copy of the secondary sample school:

- Table view rename carried (9 groups, form teacher of 1A, 1 rule); the toast read exactly; the server held the name, earlier names, groups, form-teacher places and rule.
- Undo and Redo each took the whole rename, in one entry, server too.
- A name another teacher has was refused, the box came back, nothing saved.
- A blank row given an earlier name took it off the renamed row.
- A case-only rename on a card carried (4 groups) and the card stayed open.
- As a head with the shared heads code: only provisional teachers' boxes are enabled; a blocked rename was refused with the sentence, box back, nothing saved; an unblocked head rename carried.
- End to end: a made-up Lessons workbook naming the old name uploaded with no warning or fix problem; a teacher change made on step 8, then the teacher renamed on step 4: the card read the new name and step 8 drew.

## Not checked

- A head signed in as a person with departments (only the shared heads code was tried).
- A narrow window; dark mode.
- The real school's setup: the controller checks it by counts before the pull request.

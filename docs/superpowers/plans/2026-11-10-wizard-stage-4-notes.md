# Wizard stage 4: decisions made while building, and what was left

From the build ledger of `2026-11-10-wizard-stage-4-department-map.md`. Built inline (one executor), with one fresh whole-branch review at the end and one fix pass.

## Rulings (decisions made where the plan was silent or wrong)

- Task 3: the new-teacher form shows the role's guide allowance as the allowance box's placeholder and applies it when the box is left empty, instead of refilling the box when the role changes. Same result; nothing typed is overwritten. Cost if wrong: a head who wants to see the number reads the placeholder.
- Task 4: a deployment judges the three-teacher limit before anyone joins a basket, so a refused drop changes nothing. The plan's order would have added them to the basket and then refused.
- Final: the basket question is asked before any write, and the deployment is one write. The plan said "deploy again with addToBasket", which, after a class had been split off by the first run, wrote the teachers onto the classes left behind (the review's one critical finding). Cost if wrong: none seen; two tests pin it.
- Final: the ✕ on an avatar in a basket or on a card shows on hover, on keyboard focus, and always on a touch screen (the plan said hover only, which a tablet cannot do).
- Final, left as they are (the reviewer set them aside; each stands): two browsers adding the same new name at once make two teachers, as by hand; blank Teacher 1–3 slots are closed up when the map writes a row; a renamed teacher's old name stays on lessons as "(not on list)", as before; a 40-teacher department redraws fast enough at 200 lesson rows; a card clicked in the moment between another browser's change and the redraw acts on the row at that index (the stage 2 pattern everywhere; one Undo).
- The plan's Review Focus 5 said a *renamed* teacher's tick and profile go away; by the `_id` design they follow the person under the new name, which is better. Only a removed teacher's tick and profile go.

## Deferred minor points

- A split copies the row's Students onto the one-class row and leaves the original's as it was; the new row goes to the end of the lessons list rather than after its source.
- In the profile, the ✕ on one Can teach row removes every entry of that subject (a Sec 1 row and a Sec 2 row go together). Baskets have one entry per subject, so this only shows for levels set by hand on step 4.
- Shift-click runs and Select all use the whole roster, including rows the search box is hiding.
- A subject with a blank department, or one not on School & day, is on no map and nothing says so.
- `VIEWS.map()` gives rows ids while drawing (harmless: `save()` does the same before every diff).
- On a card, a click on the text of a "(not on list)" chip, outside its ✕, deploys the ticked teachers.
- An allowance typed as 0 in the new-teacher form is read as empty and takes the role's guide.
- Firefox may not start a drag from a button; clicking still does everything.
- The smoke test's split batch moves every class to the new row rather than one.
- The scroll keeper matches boxes by position, so switching Map and Table can carry a scroll offset across.

## Not exercised in a real browser

- A real head-of-department sign-in (the role was set from the console, as in stages 2 and 3): the map with no committee-only wording, a head's new teacher provisional, New look only on a provisional teacher's profile.
- Real mouse drags: drag and drop was driven with synthetic drag events; clicks were real and from the console.
- A tablet: the layout was checked at 1024 × 768, not on a touch screen.
- The user's own school: only the sample school (52 teachers, 194 lesson rows) was used.

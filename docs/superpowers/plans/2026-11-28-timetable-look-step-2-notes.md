# The published timetable's new look, step 2 (the phone day list): notes

Notes beside the plan `2026-11-28-timetable-look-step-2.md` and the design `../specs/2026-11-27-timetable-look-design.md`
(sections 8 and 9). Built 2026-11-28 on branch `timetable-look-phone`, subagent-driven (the lead's choice): a fresh
builder and a fresh reviewer a task, one whole-branch review on the most capable model, one fix wave, one re-review,
then the controller's check at phone size on a scratch server.

## What was built

1. **`GET /api/today`** (`app.py`): the name of today's school day (`{date, day, calendar}`) and nothing else, for anyone
   who may see a timetable or their own.
2. **The day list** (`dayItems`, `dayListHTML`, `pickDay`, `pickWeek`, `pickWhole`, `redraw` in
   `ttgen/timetable_page.html`). The page always draws the list before the grid. CSS shows the list on a screen 700 px
   wide or less, the grid on a wider one, and always the grid in print.
3. **Opening on today** (`startDay`, `deviceDay`, `loadToday`, `dayChanged`).
4. **Exam times written like the grid** (`hm`, `hmAll`): the Exams and events tab, "My exam timetable" (with its report
   time and its notes), "Your duties", and the duty line of a date view.

## Rulings made while building (each can be undone)

- **Every page starts on the device's own weekday**, in the first week, then moves to the app's answer when it comes.
  The plan started a served page on the first day until the answer came; every phone would have shown Monday first.
- **A tab left open overnight asks again.** When the page is shown again on a later date it lets go of yesterday's
  pressed day and asks the app once more. The plan asked once for the life of the page.
- **A date view has no Day / Whole week switch.** It shows one day either way, so "Whole week" would mislead there.
  The reader's choice comes back after "Usual timetable".
- **A redraw happens only when the day really changes**, and a pressed button keeps keyboard focus without moving the
  page.
- **The buttons are 36 px high on a phone and say their state** to screen readers (`aria-pressed`).
- **A note's time is rewritten too** ("then lessons from 10.40"). The plan's list did not name notes.
- **No lookbehind in the page's script.** The first `hmAll` used one; Safari before 16.4 cannot read it and the whole
  page would have been blank on an older iPhone. A test now guards the script against any lookbehind.
- **On an old phone in the dark theme** the list's boxes take the panel colour, so their text stays readable where the
  browser cannot mix colours.
- **A wrapped line in the list never starts with a dot**: the dot stays with the word before it.
- **The page asks `/api/today` with no cache**, so a phone never opens on yesterday's day from its own store.
- **Weekend or holiday opens on the first day**, as the design says; with no school calendar set, every phone opens in
  the first week on the device's weekday.

## What was checked, and how

- Every quick suite and the four slow ones on the final merged code (see the hand-over).
- A scratch server with a made-up timetable and a made-up calendar, phone size 375 by 812, real taps, signed in with the
  shared student code. The school's date there was a Friday while the device's day was a Saturday, so the check saw
  both steps: the first day at once, then Even week and Fri when the app answered. Thu and Odd week pressed; a list
  item opened its lesson box; Whole week showed the grid, which moves sideways inside itself with the day names fixed;
  Day brought the list back; a date chosen showed that date's list with no buttons; at 1366 wide the list is hidden,
  the grid fits and no time is cut. Light and dark both seen.

## Not tried

- Exam times in the Exams and events tab and in "My exam timetable", in a browser (the scratch server had no exams).
  The page's own tests cover them.
- A student's own page (it needs a personal code) and a staff member's own page, in a browser. The page's tests cover them.
- The browser's print from a phone, and a real phone.

## For the lead after the deploy

Nothing to do. The list appears on phones at once; the grid, the printouts and the Excel file are unchanged.
Until the school calendar has its terms, a phone opens on its own weekday in the first week, not the right week.

## Open points for the lead

1. Times have no am or pm, on the grid and now on the exam parts too. A span of twelve hours would read the same at
   both ends ("7.40–7.40"). School hours make that very unlikely.
2. (Settled 2026-11-28, branch `exam-times`.) The exam printouts and the exam planning pages now write 1.00 too:
   see the design's section 9. Still writing 13:00: the Excel export of an exam, the Plan with AI page, the relief
   pages, Telegram messages and history lines. On the planning pages a typed text that looks like a time ("Paper 1:30")
   is shown as "1.30"; what is stored is never changed. Not tried on the real Exams page with a real schedule in a
   browser: the script was tried in a real browser engine on a made-up page, and its tests fail when it is broken on
   purpose (two ways tried).
3. On a weekend the list opens on the first day (Odd Mon), not on the next school day.
4. At phone width the page's header squeezes the school's name while the date box is empty. It is so on main too.

## Other work on the same page

"Lift one group out of a band lesson" (branch `band-one-group`) and "staff-only periods" (branch `staff-periods`)
touch the published page. Whichever merges after this merges main first and looks at a phone-sized page again.

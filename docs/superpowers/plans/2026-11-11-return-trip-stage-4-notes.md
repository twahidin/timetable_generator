# Return trip stage 4: decisions made while building, and what was left

From the build ledger of `2026-11-11-return-trip-stage-4-the-typed-request.md`. Built subagent-driven on 2026-11-11 (a fresh implementer per task, a reviewer per task, one whole-branch review, one fix wave, one re-review) on branch `return-trip-stage-4` from `main` at 846487a.

## Decided in the plan, not in the design

- Nothing of the setup or the timetable is sent to the language model. Only the typed words (at most 300 characters) and a fixed instruction go out. The model copies names as the lead wrote them; the app matches them to the school's own classes, subjects, teachers, rooms and days itself, and asks which one when a name could be several.
- Three kinds of request: move lessons, change who teaches a lesson, change a lesson's room. Anything else gets a plain reply saying what the box can do.
- Things the lead asks to keep ("keep the doubles together") are repeated back as not checked.
- A limit of 30 typed requests in 10 minutes for the whole server, kept in memory.
- `TYPED_REQUEST_MODEL=mock` turns on a small practice reader with no network call, for local runs, tests and browser checks.
- The model is `claude-opus-5-5` unless `TYPED_REQUEST_MODEL` names another.

## Rulings (decisions made where the plan was silent or wrong)

Reading the words

- The SDK is pinned to the 1.x line (`anthropic>=1.17,<2`), the line the reference material at hand documents. The call uses the beta path with the server-side refusal fallback and a structured output; the installed SDK accepts all of it as the plan wrote it. Neither the model id nor the beta header was tried live: no key is used in the build.
- Days in an ask are held to 15 forms (`Mon` to `Fri`, with `Odd ` or `Even ` in front) in the schema and in the check; periods to -1..60 in the check.
- The check of an ask is its own function (`typed.check`), so an ask the page sends back with a choice is checked without calling the model again.
- The request limit is guarded by a lock and counts a read just before the call, so slow calls in flight cannot double it.
- One SDK client for the process, made on first use. Its timeout is 12 seconds with one retry (about 25 seconds at worst). The plan's 20 seconds with a retry meant about 40.

Finding the lessons and the ways

- "Off a day" means the lessons that are on that day: with `not_days` and no `from_day`, only the lessons now on those days are answered. The plan's wording let the first eight matching lessons be answered wherever they were. Overturned at the task review.
- A band is read row by row: a lesson is picked when any of its rows matches what was said; the teacher key and the room fix come from the matching rows. A move still moves the whole lesson, and the suggestion says so ("This lesson is a band: it moves for ... too.").
- A subject word needs three letters to match by prefix or as a whole word; "and", "of", "the", "for", "in" are dropped; shorter words match only an exact name or code. An exact name with no lesson for the class tries the subject's family.
- A day is matched to the timetable's own labels by the first three letters of the label's last word and, when a week is named, by its week word, as the rules check does. Found at the whole-branch review on the school's real timetable, whose days are labelled "Tues" and "Thurs": until then Tuesday and Thursday could not be named there, and every test passed because the samples spell them "Tue" and "Thu".
- A day only partly excluded ("to Friday, not Odd Friday") is not a contradiction.
- Choices carry an id (`field|said`) and a pick is `{id: option}`; a pick that was not offered is ignored and the choice asked again.
- A teacher or room change that adds a step 5 difference says so in the suggestion.
- Swaps between two lessons that are the same in every way are not offered.

The route and the page

- With no draft the route answers 404 and with no saved setup 409, as the other draft routes do. The page shows the sentence of any refusal that carries one.
- A fault after the words were read answers "Something went wrong working that out. The suggestions below still work." and is logged by its type and the traceback's frames, never by its message, which could hold the words.
- The reader runs with no lock held; the answer is worked out on the draft as it is when the reader returns.
- The box shows whenever the Fix card is open, not only when it was opened from a warning (the design's helper also serves a lesson picked on the grid).
- After a refused Apply the typed answer is cleared and the words kept.
- The box is three rows and the full width of the helper's column, so a sentence is visible whole.

## Checked at the whole-branch review

On the school's real setup and the timetable the outside agent made on 10 November (1,018 lessons, 10 days, 272 banded lessons; counts only), before the fix wave with the day matching patched for the run and again after it with no patch (42 hand-built requests and 24 Tuesday and Thursday requests through the route, written as a person would): no sentence untrue for the school was left. 306 offered suggestions were each applied and checked with the full list of warnings. Every one did what was asked, none added a Must break or a real clash, and the two that differ from step 5 say so. Teacher changes written with a title, a short name or a first name gave the right teacher or a choice that held them. The slowest answer took half a second. What leaves the server is the words and the fixed instruction only; no suggestion applies itself; an ask sent back by the page gets no power the grid does not give; free text is drawn as text; nothing is stored; no key-shaped string is in the diff.

## Known limits, ruled to stand

- The real model's reading was never tried. The first use with a key is the first live call; if the model id or the beta header is refused, the box says the request could not be read and the helper carries on.
- The server only reads the draft when asked: a typed answer (or a way of the helper) made stale by another committee member looks live until its Apply is refused whole.
- The request limit is per server and resets on a redeploy.
- A first name can open a long choice of teachers; "Chinese" also takes Higher Chinese, by the subject-family rule.
- Period numbers are taken as the lead writes them, and the timetable numbers its periods from 0.
- A timetable that writes the week last in its day labels ("Mon Odd") cannot have a week named in a request: it answers the one-week sentence. The rules check has the same limit; the school's labels put the week first.

## Deferred minor points

- `reply` can echo up to 200 characters of what the lead typed (drawn as text); the instruction says "helper" in one place and "box" in another.
- A room matched by holding the words has a three-character floor on the whole text, not on each word. The past-the-day check uses the longest day, not each level's.
- A failed re-ask after a choice drops the choices (the words stay and the model is read again). A full redraw of the step keeps the box's text but not its focus.
- The list of teacher double-bookings the checks give is capped at 30, so settling one can let a hidden one into the list (older than this stage).

## Not exercised in a real browser

The browser checks (a scratch server, the secondary sample, the practice reader) covered: a move with Show, Apply and Undo; a move off a day the lesson is not on; teacher changes to a free, a busy and the present teacher; a choice of three answered by a click; the 300-character limit; angle brackets shown as text; typing surviving a redraw and a poll; a late answer dropped; faked server and network failures; a sentence of 64 characters visible whole; a refused Apply clearing the answer; and no box without the practice reader or a key.

Not tried in a browser: a real model; the server's own sentences for a failed read, the request limit and a too-long request; two choices settled one after the other; a refusal caused by another committee tab; the page on the school's real timetable (its data was run through the server's functions and the route, not the page).

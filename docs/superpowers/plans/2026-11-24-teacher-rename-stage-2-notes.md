# A teacher's new name carries: stage 2 notes

Stage 2 is the publish question on step 9: each renamed teacher with an account or a Telegram link is asked "Same person" or "A different person", and the account and link are moved or removed. Reliefs and exam duties (spec Parts 4 and 5) are not built: that is stage 3.

## Rulings

- The pairs have their own route, `GET /api/draft/renames`, not a place inside `GET /api/draft`: every answer that carries the draft must equal `/api/draft`'s (the page compares them so as not to redraw). Cost: one more fetch on step 9.
- The hold on relief and exams during a publish (spec Part 3) is not built. In stage 2 nothing in relief or exams follows a rename, so the old name is treated as gone exactly as before. The hold protects records that follow, so stage 3 must build it before it moves any record.
- A failure in the account or link step after the publish is said in that teacher's sentence ("could not be finished") and is not retried. The retry belongs to stage 3. Cost: in that rare case the old account stays under a name no longer on the timetable.
- The last-admin guard is pinned by unit test only (Task 1). The route cannot reach it, because the person publishing an account pair is always a usable admin.
- The blocked-bot note follows only while there is no link. When the link moves, neither name keeps a note; when there is no link under the old name, the note passes to the new name if the new name has no link and no note of its own; when the new name already has a link, the old note is deleted. A person who blocked the bot is still that person after a rename.
- A choice is sent and judged by the pair (old and new name): once the old name is claimed by another new name, the publish is refused and the page forgets its picks.
- One lock is held around a publish's three steps (the pairs, the publish, applying the choices); the exams-to-relief sync runs after it, under its own lock.
- Same person is not offered when the join would leave no admin who can sign in; the publish's join checks again and writes nothing if so.

## Known limits

- A Telegram message waiting to be sent to the old name at the moment of the publish is not delivered, and buttons on messages already sent under the old name stop matching. Stage 3 removes both.
- Reliefs and exam duties do not follow a rename.
- A rename published before this stage is not asked about: the pair needs the old name on the timetable published now.
- The setup is still read twice at a publish, inside the lock: a rename saved on step 4 in the moment between is published without being asked about, and its old account stays under the old name.
- A failure after the publish shows "could not be finished" and is not retried.
- Two old names claiming one new name, both "same": the second join raises after its link was already dropped.
- A Telegram link moved or forgotten on its own (a pair with no account) leaves no History entry.
- "Published now" shows only the last publish's lines.

## Checked in a browser

On a scratch copy of the sample school, after a first publish, with one admin and one teacher who had a role, the Relief team and a username: the teacher was renamed on step 4. Signed in with the shared committee code, step 9 showed the pair with "an account", no choices, the admin sentence in red, and Publish off. Signed in as the admin, the card showed the account's details, two unpicked choices and "Choose for each teacher with a new name first."; picking Same person turned Publish on; Publish went through; the page and the status said the account followed and a new code slip is needed; the admin list showed the new name with the role, committee and username, and not the old name.

## Not checked

- A different person, in the browser.
- A Telegram link, in the browser.
- The refusal toast (a publish answered with 409).
- A narrow window.
- Dark mode.
- The live site.

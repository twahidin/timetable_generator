# A teacher's new name carries to their groups, their account, their reliefs and their exam duties: design

Date: 2026-11-24. Status: written for the lead's approval. Names in this file are made up.

## Why

Timetables are made with some teachers not known yet ("New Teacher 3"), and a person's name is sometimes typed wrongly or
changes. Today a new name on step 4 changes that one box and nothing else:

- the teacher's groups on step 5 still hold the old name, marked "(not on list)", and each is picked again by hand; the same
  for form teachers (step 2) and a rule that names the teacher (step 6);
- the draft on step 8 names the old teacher on every lesson, and Re-fit is run to change them;
- after Publish the new name is a new person: the role, committees, username, password and Telegram link the old name had
  stay under a name that is no longer on the timetable.

The lead asked, on 2026-11-24, for a rename that carries to the groups and the account, chose the middle of three sizes
("Groups and account"), and on reading the design asked: "can you link it to reliefs and exam duties too?" So this design
is the largest size, built in three stages (below, Approaches and Stages).

Everywhere in the app a person is their name: the setup, the timetable, the accounts file, relief and exams all hold the
name as text. There is no id for a person. This design does not change that.

## Goals

1. On step 4, typing a new name over a teacher's name changes it everywhere in the setup that names them, in one save,
   with one Undo.
2. The draft on step 8 (and every saved version) follows by itself: no Re-fit, no warning that the timetable and step 5
   name different teachers because of the rename.
3. Before publishing, step 9 asks once per renamed teacher who has anything worth keeping whether it is the **same
   person** or **a different person**. For the same person, the account (role, committees, username, password, Telegram
   link) follows at the publish.
4. For the same person, their relief records and their exam duties follow at the same moment, so relief and exams never
   see them as someone who left the timetable.

## Non-goals

- The History keeps the old name: entries are never rewritten, so a renamed person's earlier entries are not listed as
  their own.
- Free text is never rewritten anywhere: a reason someone typed, a log line ("A (away) → B"), a message already sent.
- For a different person nothing but the timetable follows: the old name's exam duties and reliefs are treated as those of
  someone who left, exactly as today.
- The personal sign-in code is made from the name, so a new name has a new code and needs a new code slip. Not changed.
- The published timetable does not change until the committee publishes again.
- No carry for renamed classes, subjects or rooms (a combined venue already follows its rooms).
- A person still has no id.

## Anti-goals

- An account (a password, a role, a Telegram chat) must never pass to a different person without an admin choosing
  "Same person" for that pair of names.
- The page must never make half a rename: every place in the setup that names the teacher changes in the one save, or the
  rename is refused before anything is saved. (Two people changing the same teacher at the same moment is best effort, as
  with every other change: a group left with the old name shows it marked "(not on list)", as today.)
- Relief and exams must never act on a renamed same person as if they had left (an exam backup cancelled, a waiting
  message dropped, a name falling off a "never" list) in a gap between the publish and the records following.
- No Telegram message is sent twice because of a rename.

## Approaches

1. **Groups only.** The setup and the draft follow; after Publish the new name is a new person and nothing else is carried.
2. **Groups and account.** As 1, plus the choice of same person or a different person, which moves or removes the account
   and the Telegram link. The lead's first choice.
3. **Everything (chosen by the lead).** As 2, plus relief records and exam duties move to the new name for the same person.
   The largest: it touches approved exam schedules (a rename changes the fingerprint of what was sent) and the keys that
   stop a Telegram message being sent twice.

Two ways to make size 3 work were weighed. **Rewrite the records once** at the publish (chosen): each store gets one
function that changes the name wherever it is held. **Or keep the records and translate names whenever they are read**:
nothing is rewritten, but every reader in relief and exams would have to translate, and one that forgot would be a silent
fault. Rewriting is one piece of work per store that can be tested on its own.

**Where the question is asked.** The first version of this design asked on the Admin page after the publish. With reliefs
and exam duties in, that leaves a gap in which relief and exams see the old name as gone: the exams-to-relief sync (it runs
at every publish and after many other actions) cancels the old name's exam backups with "The duty changed.", the sender
drops messages waiting for someone it cannot reach, and a settings save writes its lists without the name. So the question
is asked on **step 9, before publishing**, and everything moves in the one press.

**Who may answer.** Account changes are the admins'. Rather than let a committee member answer and keep the account part
waiting for an admin (which needs a second place to decide, a way to change one's mind, and an answer for records that
already moved), a publish that has to carry or remove an account can only be made by an admin. Anyone else who may publish
is told so on step 9. In this school the lead publishes and is an admin.

## Stages

Each stage is planned, built, reviewed and merged on its own, and is useful alone.

1. **The setup and the draft follow** (Parts 1 and 2).
2. **The question on step 9, and the account** (Part 3).
3. **Reliefs and exam duties** (Parts 4 and 5).

## Part 1: the setup follows (step 4)

Where a teacher's name is held in the setup: `teachers[].name`; `lessons[].teachers[]` (step 5); `classes[].parents[]`
(form teachers, step 2); `rules[].target` where the rule's `scope` is "Teacher" (step 6).

**The rename.** When the name box of an existing teacher (the card on step 4, or the Table view's Name column) changes from
a non-blank name to another non-blank name:

- The new name is trimmed and runs of spaces are made one. (This is new for this box: today it stores the text as typed.
  The accounts know a person by the trimmed name.) The old name is matched exactly as it is stored.
- If another teacher already has that name (compared as `People.key` does: case and spacing ignored), the rename is refused
  with "{name} is already a teacher." and the box goes back. Nothing changes.
- Otherwise, in the same save: every `lessons[].teachers[]` entry, every `classes[].parents[]` entry and every Teacher
  rule's `target` that is exactly the old name becomes the new name. Empty places in a list stay where they are. A change of
  only case or spacing ("mdm lee" to "Mdm Lee") is a rename too, as names are matched exactly everywhere else.
- The teacher's row keeps the old name in a new list field, `earlier_names` (see below).
- If another teacher row has exactly the old name too (nothing stops two rows of one name today), nobody can tell whose
  the groups are: the name changes, nothing follows, and the toast says "Two teachers were called {old}, so their groups
  were not changed: pick the right teacher on each."
- A toast says what followed, for example: "New Teacher 3 is now Mdm Lee: on 6 groups, form teacher of 2A, 1 rule. Undo,
  at the top, brings it back." Parts that are zero are left out; with nothing to follow it says only "New Teacher 3 is now
  Mdm Lee."
- Free text is never rewritten. If a typed rule (step 6) or a note holds the old name, the toast adds one sentence naming
  where ("Typed rule T3 still says New Teacher 3: check it.").

Clearing the box (a blank name), and giving a name to a row that had none, are not renames: they behave as today.

The carry is one pure function over the setup (testable in Node, like `VenueView.renameRoom`), called by the page before it
saves, so the server receives ordinary changes in one batch. One batch is one Undo on the page and one unit for History's
Put back, which puts back the whole rename or none of it.

**`earlier_names`** on a teacher row: the names this row had before, oldest first, no duplicates, never the row's current
name. A name is the earlier name of at most one row, and never of any row while a teacher has it as their name:

- on a rename, the old name is added to this row's list and taken off every other row's (the latest rename wins), and the
  new name is taken off every row's list, this one's included (renaming back clears it);
- when a teacher is added, by any way the page adds one, their name is taken off every row's list. So a placeholder name
  used again next year ("New Teacher 3") belongs to the new row, not to last year's person.

It is not shown on the page and not written to the setup workbook. A setup that comes from a workbook or a file made before
this has none, which reads as an empty list; replacing the setup from a workbook therefore drops the lists, and a draft
made before an older rename then shows the old name again (a known limit; Re-fit settles it as it does today).

**Heads of department.** Nothing a head may do widens. Today a head can change the name only of a teacher who is still
provisional (one a head added; the box is disabled otherwise), and cannot change form teachers, rules, other departments'
groups, or the teachers of a Class Parents lesson. A head's rename of such a teacher goes through only when every place
that names the teacher is one the server lets that head change. Otherwise it is refused before anything is saved, with a
sentence that names what stands in the way, for example "Only the committee can rename New Teacher 3: they are a form
teacher of 2A and on 2 groups of other departments." The server judges a head's changes one by one as it does today.

## Part 2: the draft follows (steps 8 and 9)

Wherever the app reads a timetable against the school's setup (the draft, a saved version, Compare, Re-fit, Make
printouts, the preview, Publish), a teacher named by an earlier name of a setup teacher is read as that teacher's current
name. An earlier name that a current teacher has as their name is never mapped. The files are not rewritten: the mapping is
made each time they are read, so a rename undone on step 4 is undone on step 8 too.

The changes already made on step 8 ("Changes") may name the old teacher: a draft with such a change must still open, and
the lesson reads with the new name. The sentences step 8 lists under "Changes" are stored text and keep the old name; the
sentences made again when the changes are replayed (the publish record, the printouts) may carry the new one. Either is fine.

This also means a timetable an outside agent made from a workbook downloaded before the rename can still be uploaded.

The route that makes printouts from an uploaded setup workbook and timetable, with no school setup involved, is untouched.

## Part 3: the question on step 9, and the account

**Which teachers are asked about.** For each teacher row of the setup about to be published: a name in its `earlier_names`
that is a teacher row's name on the timetable published now, is not a teacher in the setup about to be published, and has
**something to keep**, makes a pair (old name, new name). Something to keep is:

- an **account part**: a role, departments, a committee or Admin, a username, a password, a Google sign-in, a note,
  switched off, or added by name;
- a **Telegram link**;
- from stage 3, any relief record or exam record that holds the name (Parts 4 and 5).

Sign-ins alone are not. A placeholder that never had anything makes no pair and asks nothing.

So an old name can only ever be a teacher on the timetable being replaced. A person who was only added by name (a school
leader, say) can never be offered as an old name, whatever `earlier_names` says: that field is ordinary setup data that any
committee member can write, and is not trusted beyond this.

**On step 9**, above the Publish button, when there are pairs: a card "New names since the last publish", one line per
pair, "New Teacher 3 is now Mdm Lee.", and two choices, neither picked at first:

- **Same person:** "Everything New Teacher 3 has goes to Mdm Lee."
- **A different person:** "Mdm Lee starts fresh. New Teacher 3's account is removed, and their reliefs and exam duties are
  treated as those of a teacher who left."

An admin also sees what the old name has ("HOD · Relief team · username · Telegram · 2 absences · 5 exam duties").
Account details are shown to admins only, as everywhere else: anyone else sees the counts of absences and exam duties, and
"has an account" with no more. Until stage 3 is built the card and its sentences speak of the account only.

**A pair with an account part needs an admin.** When the person on step 9 is not an admin (a committee member, or the
shared committee code), such a line has no choices and says "An admin has to publish this one: Mdm Lee's account must
follow or be removed." Publish is off with that reason. A pair with no account part (from stage 3: only reliefs, exam
duties or a Telegram link) can be answered by anyone who may publish.

**Publish this timetable** is off, with the reason above it, until every pair has a choice; the server refuses too, and
names the pairs it still needs an answer for. The choices are sent with the publish and the server works the pairs out
again against the timetable as it is at that moment: a pair the page did not send a choice for, or one that needs an admin
when the sender is not one, refuses the publish before anything is made.

**Choices that are not offered**, each with its reason on the line:

- Same person for the account, when the new name already has a username, a password or a Google sign-in of its own ("Mdm
  Lee already has their own account"): their reliefs, exam duties and Telegram link may still follow, and the old account
  is removed.
- A different person, when that would remove the account of the person publishing, or of the last admin who can sign in.

**At the publish**, in this order:

1. The new timetable is put in place.
2. For each same person pair: the relief and exam records and the Telegram link move to the new name (stage 3; Parts 4 and
   5. In stage 2 only the Telegram link moves).
3. For each pair: the account part moves or is removed (below).
4. The exams-to-relief sync that follows every publish runs.

From step 1 to the end of step 3 **nothing in relief or exams acts**: this is the gap the anti-goal is about. The background
work (filling reliefs, telling people, the reports, the morning message, the sender) skips its turn, the sync does not run,
and a request or a Telegram button that would change a relief or exam record is answered "The timetable is being
published: try again in a moment." Reading is not stopped. If the app runs as more than one process, the hold must hold in
all of them. A relief run that began before the publish must not undo this: when it comes to apply what it found, an
approved or sent relief is never changed by it (as today); a pick still waiting for approval may be made again, which is
accepted.

**The account, same person.** The new name's record takes from the old name's, field by field, whatever the old one has
set: role (with its departments), username, password (and whether it must be changed), Google sign-in, note, switched off.
Committees and Admin are joined: a tick either name has stays (for Exams and events, the later end date). Where the old
record has nothing set, the new name keeps its own. The old name's record goes, and no session made under it is ever
accepted again (as a removal does); every other session of the new name ends too. The person publishing, if they are the
one renamed, stays signed in under the new name.

**The account, a different person.** The old name's record goes, its sessions end for good, and its Telegram link and link
codes are forgotten: what "Remove this person" does, through a path of its own, because an old name with only a role or a
Telegram link is not on the Staff list and Remove would refuse it.

**The Telegram link, same person.** It moves to the new name with the old name's blocked-bot notes; the old name's unused
link codes go. If the new name already has a link of its own, it keeps it and the old one is dropped.

Every account move or removal writes one entry to the History ("New Teacher 3 is now Mdm Lee: their account followed" /
"Removed New Teacher 3: Mdm Lee took over their timetable"). Neither can be put back from the History.

After the publish, "Published now" says what followed, for example "Mdm Lee (was New Teacher 3): account, 2 absences and 5
exam duties followed. They need a new code slip."

The old name's personal code stops working at the publish, and the new name's code is new: that is how codes work today.

## Part 4: reliefs follow (stage 3)

For a same person pair, relief's records are changed once, at the publish, so that everything relief knows about the old
name it knows about the new one:

- **Absences** (one file each): whose absence it is; who reported it and their reporting officer; who cancelled it; and
  in every lesson and part of a lesson: the other teachers of the lesson, who relieves it and who gave the relief, the
  pick and who picked, who approved, who sent out, who marked it not needed, and each line of the lesson's own history.
- **Relief settings:** the "never" list.
- **What each person last saw** (the inbox's seen marks).
- In an absence, also: the people a backup has lost (`gone`), and the new pick of a change request.
- **Telegram:** the link itself (Part 3), messages waiting to be sent (the name on the row and inside its reference),
  buttons still live (whose they are and whom they are about), a conversation with the bot that is open, and the notes
  kept per person (a blocked bot, its alerts, a report already started for a relief). Messages waiting go to the person's
  chat as it is after the rename. The keys that stop a message being sent twice hold names: they are changed with the
  rest, so that after the rename relief sees each message it already sent as sent.

Sentences people typed and messages already sent keep the old name, and so does text kept only to be shown ("Planned by
…", "saved by …"). One sentence is not only shown: a relief's history line says why it was released, and the app compares
that sentence with a name to send "Relief needed again" when the relief teacher is away. That must still work after a
rename. The settings files also keep old lists that nothing reads any more; they are left alone.

Where a record holds both names (the new name was already known to relief, say as a relief teacher added by name), they
become one: one entry in a list, and in anything kept per person the new name's own entry stays.

A relief or an absence dated today or later must come out of the rename exactly as it went in apart from the name: the
same relief, approved and sent out as it was, with nothing sent again and nothing asked again.

## Part 5: exam duties follow (stage 3)

For a same person pair, at the same moment:

- **Exams settings:** the backups, chiefs and "never" lists.
- **Every schedule:** the teacher in charge; who is going; each duty's person; the made duties' names and chiefs; the
  reasons, backups and "not free" notes kept per person; the pinned duties; the lessons marked "handled ourselves"; who
  created, saved, sent and approved it; who made each log line. The **approved copy** inside a schedule is changed the
  same way.
- The rename is not itself a change for anyone to send or approve again: the fingerprint of what was sent is made from
  names, so it is brought in step. (Every publish already marks each made exam "The timetable changed since this was
  made"; that note is unchanged.)

Log sentences keep the old name, as do the sentences inside a duty's reasons ("replaces X, who is away") and the list of
people a made schedule lost. Where both names appear, the same joining rule as Part 4.

**For both parts.** Each store's rename runs under that store's own lock and can be run twice without harm. If one fails
part-way, the publish stands and the hold of Part 3 stays on: what is left is kept as unfinished, is tried again at the
next background turn and when the app starts, and shows on the Admin page and on relief's page ("Finishing a rename: Mdm
Lee") with **Try again** for an admin, until done. The sync does not run for anyone while a rename is unfinished. A pair is
never left looking finished when it is not.

## Constraints

- The repository is public: made-up names in tests, samples and docs; the school is "CTSS" only.
- `ttgen` has a copy under `skill/school-timetable-generator/scripts/ttgen`; a test keeps the two the same. The workbook
  format does not change, so the skill version does not change.
- The accounts file has one write path (`people.update`); the Telegram tables one (`tgdb.db()`).
- No test may call a model API or the real Telegram API.
- Plain language on every page, as elsewhere in the app; step numbers as on the page.

## My calls (the lead may change any)

- The question is asked on step 9 and blocks Publish until answered. A publish that must carry or remove an account can
  only be made by an admin; there is no second place to decide and nothing waits afterwards (see Approaches).
- The Telegram link follows with the reliefs, not with the account: messages find a person by their link.
- Relief and exams hold still for the moment of a publish that renames someone. A relief pick still waiting for approval
  may be made again by a run that began before the publish; nothing approved or sent changes.
- A teacher renamed and published while only stages 1 and 2 are live keeps their relief and exam records under the old
  name: stage 3 does not go back for them.
- A different person takes nothing: the old name's exam duties and reliefs are left as those of a teacher who left, for the
  relief team and the exams committee to give to someone, as they do today when a teacher leaves.
- Who did something (reported, approved, sent, saved) follows the rename too, not only who it was done for.
- A rename to a name another teacher has is refused, not merged.
- A head's rename is refused unless everything that names the teacher is theirs; a head still renames only a provisional
  teacher.
- A pair is offered only when the old name is a teacher on the timetable being replaced and has something to keep;
  otherwise nothing is asked. The choice, made with both names in front of the person, is the safeguard.
- The accounts cannot be joined when the new name already has a username, a password or a Google sign-in; otherwise the
  two records are joined as set out above.
- When two teacher rows share the old name, the name changes and nothing follows.
- A placeholder name used again belongs to the new row (the latest use wins).
- Replacing the whole setup from a workbook drops the earlier names, so a rename not yet published is then not asked
  about.
- The History stays under the old name; the personal code changes with the name.

## Left to the builder

- Where the earlier-name mapping lives in the code, as long as every reader in Part 2 goes through it and the two copies
  of `ttgen` stay the same.
- The names of functions, routes and tests; the exact look of step 9's card and of the "Finishing a rename" line, in the
  pages' existing style.
- Where an unfinished rename is kept and how the hold is made, as long as both survive a restart and hold in every
  process the app runs.
- How each store's rename finds every place a name is held. The lists in Parts 4 and 5 are what was found on 2026-11-24;
  the builder checks them against the code, and a test for each store walks a full record and fails if the old name is
  left anywhere but in the text this design says is kept.

## What to check before calling it done

- Every suite, and the slow runs.
- In a browser on a scratch copy with real pointer clicks: a rename on the card and in the Table view, Undo, a refused
  duplicate, a head's refused rename; step 8 opening a draft made before the rename, one with a change under "Changes"
  that names the old teacher; step 9's question as an admin and as a committee member who is not one; a publish by an
  admin who is the renamed person.
- Stage 3, on a scratch copy: an absence with a relief approved and sent out, and an exam schedule sent and approved, each
  under the old name; after a same person publish, relief and exams show them under the new name, unchanged, with no
  message waiting to be sent and nothing more asking to be sent or approved than any publish asks. "Relief needed again"
  still goes out for a relief teacher who was renamed and is then away.
- Stage 3: with the background work running, a publish that renames someone cancels no exam backup, drops no waiting
  message and loses no name from a "never" list.
- That a name added by hand on the Admin page, written into a row's `earlier_names`, never appears as an old name.
- On the school's real setup, as counts only: renaming one teacher changes exactly the rows that named them, and a draft
  uploaded before the rename opens with the same number of warnings as before it.

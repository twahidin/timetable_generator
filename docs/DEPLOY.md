# Deploy for your school

Each school runs its own copy of the app: one Railway service with its own volume and its own access codes. Nothing is
shared between schools. The setup, the student list and the published timetable stay on that school's server and
volume. The timetable itself is made outside the app, by an AI agent the committee gives the setup to (see
[What leaves the server](#what-leaves-the-server)).

You need a Railway account and about 20 minutes.

## 1. Create the service

1. On GitHub, fork this repository (or copy it into a repository of your own). Railway deploys from it, and you choose
   when to take updates.
2. In Railway: **New Project → GitHub repo** (link GitHub if it asks), and pick your repository. Choose **Add
   variables** instead of **Deploy Now** if you want to do step 3 first.
3. Railway builds it with the `Dockerfile`. `railway.json` sets the health check (`/healthz`) and restarts the app if it
   crashes. Nothing needs changing. Each push to the connected branch deploys again.

If the first deploy starts without a volume or variables, that is fine: the sign-in page lists what is missing (step 6).

## 2. Attach a volume

The setup, its restore points and the published timetable are files on the volume. Without
one, everything is lost on the next deploy.

1. Add a volume to the service: in the project canvas, right-click the service → **Attach Volume** (or open the command
   palette with ⌘K / Ctrl K, create a volume and pick the service).
2. Set the **mount path** to `/data`.

Railway then sets `RAILWAY_VOLUME_MOUNT_PATH=/data` and the app keeps everything there. On the volume:

| Folder or file | What |
|---|---|
| `setup.json` | the school's setup, including the Students sheet, as the committee and heads last changed it |
| `setup_history/` | restore points: one about every 10 minutes while people work (the last 48 are kept), and one before every whole-setup action (starting blank, opening a workbook, loading from a file, restoring a copy) |
| `runs/` | only on a volume used by an earlier version, which generated in the app. No longer written; safe to leave |
| `published/` | the published timetable, PDFs, workbooks and the personal codes |
| `relief/telegram.db` | Telegram for relief (section 6): who has linked (name, the number Telegram gives their chat, their @name), the messages sent and waiting (kept about 400 days), and the conversations the bot is in the middle of (what was typed goes when one ends). Not the bot's token. `telegram.db-wal` and `telegram.db-shm` beside it belong to it |

A school's data is small. The CTSS test copy (two runs and 48 restore points) is about 5 MB before publishing; publishing
adds the PDFs and workbooks (about 30 MB for the 624-student sample school). The smallest volume Railway offers is
plenty.

A service with a volume runs one replica (Railway does not allow more), which is what the app needs: publishing is
guarded by a lock in the web process. Because of the volume, each redeploy has a short downtime. After a redeploy, open
browsers carry on; any that missed changes fetch the setup again, and changes not yet sent are sent.

## 3. Set the variables

In the service, open **Variables**. **New Variable** adds one at a time; the **Raw Editor** takes the lines below in one paste. Replace every value; never put
real values in the repository.

```
SECRET_KEY=paste-a-long-random-string-here
COMMITTEE_CODE=
TEACHER_CODE=
STUDENT_CODE=
HEADS_CODE=
SCHOOL_NAME=
ANTHROPIC_API_KEY=
```

To make a random string, run `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`, or use a password
manager's generator.

| Variable | Needed? | What it does | Safe default |
|---|---|---|---|
| `SECRET_KEY` | **yes** | Signs the sign-in cookies, and makes each student's personal code from their Student ID. Keep it once set: changing it signs everyone out and changes every personal code. | none: set a long random string. Without it, sign-ins end at every restart and personal codes are off: made without a key, anyone who knows a Student ID could work out that student's code. |
| `COMMITTEE_CODE` | **yes** | The timetable committee's code: setup editor, downloads, publish, personal codes. | none. At least 6 letters or digits. |
| `TEACHER_CODE` | **yes** | Teachers' code: every class, teacher, room and student timetable, Who's free, PDFs. | none. At least 6 letters or digits. |
| `STUDENT_CODE` | **yes** | Students' code: class timetables and **Build my timetable**. | none. At least 6 letters or digits. |
| `HEADS_CODE` | no | Heads of department's code. With it set, the sign-in page has a fourth choice, **Department heads**. A head sees every step except Download, Upload and edit, Publish and Students, and can change everything on step 5's department map and table (who teaches which class and group, teaching groups, bands); they can add a teacher (marked provisional until the committee confirms them) and edit a teacher who is still provisional. The server refuses any other change: a refused change is skipped and reported to the head, and the rest of their work is kept. | none: leave it out and there is no heads' sign-in. At least 6 letters or digits, different from the other codes. |
| `ANTHROPIC_API_KEY` | no | With it set, the Fix card on step 8 has a box to type a request in your own words. The committee adds it in Railway themselves; the app never shows it. Only the words typed in the box (at most 300 characters) and a fixed instruction go to Anthropic: no list of teachers, classes, students or lessons. A name the lead types is part of their words. The same key and model also make the relief picks (see What leaves the server). A server that still holds `AI_PROVIDER=anthropic` and `AI_API_KEY` from an earlier version has the box too: that key is used when `ANTHROPIC_API_KEY` is not set. | none: leave it out and the box is not there; the Fix card works as before. |
| `TYPED_REQUEST_MODEL` | no | The model that reads the words in the box. `mock` turns on a practice reader that needs no key and understands two sentence shapes, for trying the box locally. When the key in use is the earlier `AI_API_KEY`, `AI_MODEL` names the model unless this is set. | `claude-opus-5-5` |
| `TELEGRAM_BOT_TOKEN` | no | With it set, the school's own Telegram bot can be connected in **Relief settings**: people are told of their relief on Telegram and answer there. [Section 6](#6-telegram-for-relief) has the steps. The app never shows it. It is a password: whoever has it can write as the bot and read what people send it. **On one service only**: the one the school uses. The word `practice` in place of a token tries everything with nothing sent. | none: leave it out and there is no Telegram; relief works in the app as before. |
| `RELIEF_JOBS` | no | `on` starts a one-minute background timer that makes relief picks when they are due: at once for today, and at the fill time (15:00 by default) on the school day before. With `TELEGRAM_BOT_TOKEN` set and the bot connected, it also sends the Telegram messages, the reports and the weekly summary. The Dockerfile sets it. | off outside the container, so a local run picks only on **Fill now**, and no message goes out by itself |
| `SCHOOL_NAME` | no | Shown on the sign-in page until a timetable is published (then the published school name is shown), and used to name a blank setup. | `School timetable` on the sign-in page |
| `DATA_DIR` | no | Where the data goes, if not the volume. Do not set it on Railway. | the volume's mount path, else `data/` in the app folder |

The access codes are compared ignoring case, spaces and dashes, and must all be different. After ten wrong codes in ten
minutes from one address, that address has to wait (up to ten minutes).

Railway sets `PORT`, `RAILWAY_ENVIRONMENT_NAME`, `RAILWAY_VOLUME_MOUNT_PATH` and `RAILWAY_PUBLIC_DOMAIN` itself; don't set them.

Variable changes are staged: Railway shows them, and **Deploy** applies them with a redeploy.

## 4. Memory and CPU

The app is light: it does not solve timetables. Publishing (making the PDFs, the Excel workbook and the pages) takes
about a minute for a 600-student school and uses one vCPU.

- **Memory:** about 1 GB is enough for a 1,500-student school.
- **Keep one gunicorn worker** (the `Dockerfile` runs `--workers 1 --threads 8`). Publishing swaps the files in under a
  lock held in the web process, so more workers or replicas could publish over each other.

## 5. First sign-in and loading the setup

1. In the service: **Settings → Networking → Public Networking → Generate Domain**, then open the domain.
2. The sign-in page lists anything missing in amber: a code or `SECRET_KEY` not set, codes too short or the same, or no
   volume. Fix those first. The service's deploy logs show the same list at startup.
3. Choose **Build and publish the timetable** and enter the committee code. (Heads of department choose **Department
   heads** and use their own code, once `HEADS_CODE` is set.)
4. Load your setup. On **Start**:
   - **Open a setup workbook (.xlsx)** reads a setup workbook into every step. It reads the app's own template and the
     CTSS layout (G-levels, "Class (2027)" on Students, Block and "Floor / level" on Venues, and extra sheets such as Roles,
     Combinations and notes). A school starting from the CTSS template can open a copy of it with its own data.
   - **Secondary school · blank** starts with typical subjects and a day shape, and you add rooms, classes, teachers and
     lessons. **Secondary school · sample** is a made-up 16-class school, to see how everything fits.
   - Blank and sample workbooks to fill in Excel are on step 7, **Download → Templates to share**.
5. The panel on the right lists anything that does not add up. Every change is saved on the server by itself, and the
   setup opens by itself for the committee and the heads on any browser. The header shows Saved, Saving or Offline.
6. On step 7, **Download**, get the configuration workbook and the timetable skill, and give both to an AI agent that
   can run code. It hands back the timetable file.
7. On step 8, **Upload and edit**, upload that file, press **Upload and check** and read what it found; fix what it lists there.
   Then, on step 9, **Publish**, read the critical mistakes and warnings and press **Publish this timetable**: it is
   off while a critical mistake remains. Give teachers the teacher code and students the student code.
8. Once the timetable is out, add students class by class on the Students step (optional; with them, no student gets two lessons at once and, with `SECRET_KEY` set, each
   gets a personal code). Once published, **Personal student codes** on step 9 has the slips to print, one page per
   class, and the list as a CSV.

## 6. Telegram for relief

This part is optional. The school's own Telegram bot tells people about relief on their phones, and they can answer
there. Whoever does not use it finds their reliefs and absences in the app, as before. (Reporting officers are told on
Telegram alone.) It is set up once, by one person with Telegram on a phone, on the copy of the app the school uses. It
takes about 10 minutes.

### Make the bot

1. Open Telegram and search for **@BotFather**. Take the one with the blue tick: it is Telegram's own.
2. Send `/newbot`.
3. It asks for a name. Type one people will recognise, such as "CTSS Relief".
4. It asks for a username. It has to end in "bot" and nobody else may have it.
5. BotFather answers with a token. The token is a password. Copy it straight into Railway (next part). Never put it in a
   chat, an email, a picture or the repository.

If somebody else has ever seen the token, send `/revoke` to BotFather and pick the bot. The old token stops working
and BotFather gives a new one. ("When something changes", below, has the order once the bot is in use.)

### Give the token to the app

1. In Railway, open the service the school uses. One service only: a second copy must not have the token.
2. Open **Variables**. Check that `SECRET_KEY` is there. The app makes a password out of it that Telegram has to show
   with everything it passes on, so nobody else can pretend to be Telegram.
3. Press **New Variable**, name it `TELEGRAM_BOT_TOKEN`, paste the token, and press **Deploy**.

### Connect the bot

1. Open the app at the address the school uses. Sign in as the timetable committee or as somebody on the relief team,
   and open **Relief settings**. The **Telegram** card is at the bottom.
2. It says "The token is set. Connect points Telegram at this copy of the app." Press **Connect the bot**.
3. It says "Connected." and "Connected as @", the bot's username, the day and the app's address. Under it is how many
   people have linked, and two lists: **Not linked** and **Linked**.

Connecting tells Telegram to pass on what people send the bot to this copy of the app, and gives the bot its menu
(`/relief`, `/stop`, `/help`). The address is the one Railway gives the service, or the one you opened when Railway
gives none. Nobody gets anything yet: each person links first. Reliefs approved before then are sent too, as long as
their lessons are still to come; so are a request to change that still waits for the team, and a reminder still to come.
An absence planned, asked for or cancelled before the bot was connected is not told afterwards.

| If it says | Do this |
|---|---|
| "Not set up yet. The bot's token goes in Railway's variables (TELEGRAM_BOT_TOKEN) …" | The app has no token. Do the part above, and wait until the deploy is done. |
| "Set SECRET_KEY in Railway variables first: the bot needs it." | Set `SECRET_KEY`, deploy, and press **Connect the bot** again. |
| "Telegram needs a secure address: open the app at its https address and press Connect there." | Open the app at the address that starts with https. |
| "Telegram did not answer, or did not accept the bot. Check TELEGRAM_BOT_TOKEN in Railway variables and try again." | The token was pasted wrongly or has been revoked, or Telegram is down for the moment. |

### Each person links their own Telegram

Everyone does this once, on their own phone.

1. Sign in to the app with your own name (your personal code, or your username and password). Open **Relief**, then
   **My absences**. The **Telegram** card is at the top. It is not there until the bot is connected.
2. Press **Link Telegram**, then **Open the bot**. Telegram opens: press **Start** there.
3. The bot answers "Linked:" and your name, and the card in the app says that you are linked and since when.

If Telegram is not on that computer, send the code on the card to the bot from your phone instead (the card says the
bot's @name). The code works once and runs out in 15 minutes; **Get a new code** makes another.

- Never send the bot your personal code: that one opens the app. The bot asks for a code from the card only. It deletes
  what looks like a code and is not one, and says so (while it waits for an answer it has asked you for, whatever you
  type is the answer).
- One person has one Telegram. Linking on another phone moves it there, and the old one is told.
- To stop, press **Unlink** on the card, or send `/stop` to the bot.
- The relief team and the timetable committee can unlink anyone: **Relief settings**, the **Telegram** card, **Linked**,
  **Unlink**. Do this when somebody has lost their phone. The messages that went there stay on it.
- Somebody who blocks the bot is unlinked by the next message that cannot reach them.
- The relief team sees on **Today** who is not on Telegram. They see their relief in the app, in **Reliefs I'm covering**.

### Turning it off

Press **Disconnect** on the **Telegram** card. It asks "Disconnect? Nobody gets messages until it is connected again."
Press **Disconnect** there too. If it then says "Disconnected here, but Telegram did not answer. The app reads and sends nothing now.", it is off all
the same. Or delete `TELEGRAM_BOT_TOKEN` in Railway and press **Deploy**. Either way nobody is unlinked, and relief goes
on in the app.

After a **Disconnect**, **Connect the bot** turns it on again, and what was done while it was off is told or not told as
at the first time (above). With the variable put back (the same token), the bot is connected again by itself.

### When something changes

| What changes | What happens | What to do |
|---|---|---|
| The app's address | Messages still go out, but their buttons open the old address, and what people press or type goes there. | Press **Connect again** on the card, in the app at its new address. |
| `SECRET_KEY` | The bot is off: nothing is sent and nothing people press is answered. (Everyone is also signed out, and every personal code changes.) Nobody is unlinked. | Press **Connect the bot**. |
| The token of the same bot (`/revoke`) | The old token is refused, so what was to go out fails ("Could not be sent: remind them" on **Today**). Nobody is unlinked. | Press **Disconnect** first. Then `/revoke`, put the new token in Railway, deploy, and press **Connect the bot**. |
| Another bot | The new bot can write to nobody yet: a bot may write only to people who have pressed **Start** in it. | Press **Disconnect** first. Put the new token in Railway, deploy, and press **Connect the bot**. Then everyone presses **Unlink** and links again. |

Connecting drops what people sent the bot while it could not be answered: they press or type it again.

**One copy only.** Telegram passes what people send a bot to one address. If somebody puts the same token on a second
copy and presses Connect there, what people press and type goes to that copy, which knows nobody. To put it right, take
the token off the second copy and press **Connect again** on the one the school uses.

### Trying it without a bot

Set `TELEGRAM_BOT_TOKEN=practice` (with `SECRET_KEY` and `RELIEF_JOBS=on`) on a copy for trying things, such as a local
run. The card says "Practice mode: nothing is sent to Telegram." and everything else goes on as if it were: the messages
are made, queued and marked as sent. Never on the copy the school uses: it would look as if people had been told. Do not
press **Open the bot** there: the bot it opens ("practice_bot") is not the school's and may be a stranger's. With a real
token afterwards, press **Connect the bot** once more.

## What leaves the server

Nothing, unless you set `ANTHROPIC_API_KEY` (or the server still holds `AI_PROVIDER=anthropic` with `AI_API_KEY` from an earlier version, which counts as the same thing) or `TELEGRAM_BOT_TOKEN`. The app has no AI inside, and these two are the only places outside the server it calls: Anthropic's API and Telegram's. With `ANTHROPIC_API_KEY` set, two things go to Anthropic's API at its usual address (do not set `ANTHROPIC_BASE_URL` on the service, which would send them to another address):

- **The box on the Fix card** sends the words the lead types in it (at most 300 characters) and a fixed instruction, and nothing else: no list of teachers, classes, students or lessons, and no part of the timetable. A name the lead types is part of their words. Nothing typed is stored.
- **Relief picks** (relief stage 3) send, for each lesson to cover, the teachers who are free as labels ("Teacher 4"), their departments, subjects, teaching and relief period counts, and the school's relief rules text with names replaced by labels. They never send staff names, absence reasons, work or remarks. Write people in the rules by their full name, so the app can replace them. The model is the same `ANTHROPIC_API_KEY` and `TYPED_REQUEST_MODEL` as the typed requests. With no key, every pick uses the app's own order. The app makes at most 60 AI picks in any 10 minutes for the whole server; past that it uses its own order and says so.

With `TELEGRAM_BOT_TOKEN` set and the bot connected, **Telegram** gets these messages, each for one person who has linked their own Telegram. Somebody not linked who writes to the bot is told only that their Telegram is not linked.

| For | What the message holds |
|---|---|
| the relief teacher, once the relief team has approved the relief | the absent teacher's name, the day, the lesson (classes, subject, group), its periods, times and room, the work text and the link the absent teacher left, and the work files, sent after it. Later, when that changes: that the relief was moved, kept, is no longer needed, or that the lesson is not happening (with the name of the exam or event and the class) or is on again |
| the absent teacher, for relief somebody else planned | the dates, whole day or which periods, who planned it, how many lessons will be covered, and one reminder to acknowledge it |
| the reporting officer | who is away, on which dates, whole day or which periods, and the kind of reason (Medical, Child sick, Course or Other). This is the only message to somebody else that says anything of why a person is away |
| the relief team | a request to change: who asks, the lesson, the line they typed, the new pick's name and the reason for it; who has not acknowledged which lesson and when they were told; that all have; which teacher's absence was cancelled, for which dates and by whom; and once a week the numbers of the week, with the three teachers who took most relief and the departments |
| whoever was told of an absence, and whoever planned it | that it was cancelled, by whom, for which dates |
| anyone asking for relief with `/relief` | the questions and their buttons: their own name, dates, periods, the kinds of reason, the names of staff who match what they type for a reporting officer, their lessons, and a list of what was chosen before **Send** |

Telegram also gets everything people type or send to the bot: the line for **Other**, why they ask to change (which goes on to the relief team) or cancel (which is shown back to them before they confirm), the work they type for a lesson, and the files and photos they send as work (the app fetches those from Telegram after **Send**). Of what Telegram knows about a person, the app keeps the number of their chat and their @name.

The app never sends Telegram the typed line of an absence's reason, the remarks for the relief team, anybody's phone number (it has none and asks for none), passwords, personal codes, the student list or the timetable. A code for linking (one use, 15 minutes) is in the link that opens the bot.

Chats with a bot are not end-to-end encrypted: Telegram, the company, can read them, and what was sent stays in the chat and on Telegram's servers after somebody unlinks. Work for a lesson and reasons typed to the bot should hold nothing that must not leave the school. A personal code sent to the bot by mistake is deleted from the chat when Telegram allows it (section 6), but has passed through Telegram by then.

**The relief timer.** `RELIEF_JOBS=on` (the Dockerfile sets it) starts a background timer that makes picks when due and, with `TELEGRAM_BOT_TOKEN`, sends the Telegram messages. The unused second Railway copy builds from the same Dockerfile, so it runs its own timer on its own data. Without the token it sends nothing on Telegram: do not add it there. Importing `app` in the container (for example running `tests/smoke.py` in a Railway shell) starts a timer too. Picks for the first school day of a term fall due on the last school day of the term before, as the design says.

Who sees what inside the app: a head's browser receives the whole setup, because the editor works on all of it, including
the student list once students are added, although the Students, Download, Upload and edit and Publish steps are hidden from heads and
the server refuses their changes to anything but groups, bands, who teaches which class and group, and new teachers. Give `HEADS_CODE`
only to people who may see the student list. Teachers and students never receive the setup.

What an outside AI agent sees is what the committee gives it: the configuration workbook from step 7. That workbook
holds teachers' names, and the **Students** sheet once students have been added. The timetable does not need the
student list: download the workbook before adding students, or delete the Students sheet from the copy you hand over,
if the agent should not see students' names.

## Coming from an earlier version

Earlier versions generated the timetable inside the app, with an optional AI timetabler.

- These variables are no longer read and can be deleted in Railway: `AI_EFFORT`, `AI_BASE_URL`, `SOLVE_SECONDS`,
  `SOLVE_MAX_SECONDS`, `SOLVE_WORKERS`, `STAGED_FROM_CLASSES`, `MOCK_SOLVE_SECONDS`. Leaving them set does no harm.
- `AI_PROVIDER`, `AI_API_KEY` and `AI_MODEL` are read for one thing only: with `AI_PROVIDER=anthropic` and a key in
  `AI_API_KEY`, the Fix card on step 8 has the box to type a request in (see `ANTHROPIC_API_KEY` above), read by the
  model `AI_MODEL` names. A key with another provider, or with no provider named, is never used. Delete
  `AI_API_KEY` if you do not want the box.
- A timetable already published stays published.
- The `runs/` folder on the volume is no longer written and can be left.
- Generate, the chat and Adjust timetable are gone: make the timetable with the skill outside the app, then upload it on step 8
  and publish it on step 9.

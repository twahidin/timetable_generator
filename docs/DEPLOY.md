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
| `HEADS_CODE` | no | Heads of department's code. With it set, the sign-in page has a fourth choice, **Department heads**. A head sees every step except Download, Publish and Students, and can change everything on step 5's department map and table (who can teach what, who teaches which class, group or band, teaching groups, bands); they can add a teacher (marked provisional until the committee confirms them) and edit a teacher who is still provisional. The server refuses any other change: a refused change is skipped and reported to the head, and the rest of their work is kept. | none: leave it out and there is no heads' sign-in. At least 6 letters or digits, different from the other codes. |
| `ANTHROPIC_API_KEY` | no | With it set, the Fix card on step 8 has a box to type a request in your own words. The committee adds it in Railway themselves; the app never shows it. Only the words typed in the box (at most 300 characters) and a fixed instruction go to Anthropic: no list of teachers, classes, students or lessons. A name the lead types is part of their words. | none: leave it out and the box is not there; the Fix card works as before. |
| `TYPED_REQUEST_MODEL` | no | The model that reads the words in the box. `mock` turns on a practice reader that needs no key and understands two sentence shapes, for trying the box locally. | `claude-opus-5-5` |
| `SCHOOL_NAME` | no | Shown on the sign-in page until a timetable is published (then the published school name is shown), and used to name a blank setup. | `School timetable` on the sign-in page |
| `DATA_DIR` | no | Where the data goes, if not the volume. Leave it unset on Railway. | the volume's mount path, else `data/` in the app folder |

The access codes are compared ignoring case, spaces and dashes, and must all be different. After ten wrong codes in ten
minutes from one address, that address has to wait (up to ten minutes).

Railway sets `PORT`, `RAILWAY_ENVIRONMENT_NAME` and `RAILWAY_VOLUME_MOUNT_PATH` itself; don't set them.

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
7. On step 8, **Publish**, upload that file, press **Check, then publish** and read what it found, then **Publish this
   timetable**. Give teachers the teacher code and students the student code.
8. Once the timetable is out, add students class by class on the Students step (optional; with them, no student gets two lessons at once and, with `SECRET_KEY` set, each
   gets a personal code). Once published, **Personal student codes** on step 8 has the slips to print, one page per
   class, and the list as a CSV.

## What leaves the server

Nothing, unless you set `ANTHROPIC_API_KEY`. The app has no AI inside and makes no outbound calls of its own. With the key set, the box on the Fix card sends the words the lead types in it (at most 300 characters) and a fixed instruction to Anthropic, and nothing else: no list of teachers, classes, students or lessons, and no part of the timetable. The words go to Anthropic's API at its usual address; do not set `ANTHROPIC_BASE_URL` on the service, which would send them to another address. The app finds the lessons and people itself. A name the lead types is part of their words. Nothing typed is stored.

Who sees what inside the app: a head's browser receives the whole setup, because the editor works on all of it, including
the student list once students are added, although the Students, Download and Publish steps are hidden from heads and
the server refuses their changes to anything but groups, bands, who can teach what and new teachers. Give `HEADS_CODE`
only to people who may see the student list. Teachers and students never receive the setup.

What an outside AI agent sees is what the committee gives it: the configuration workbook from step 7. That workbook
holds teachers' names, and the **Students** sheet once students have been added. The timetable does not need the
student list: download the workbook before adding students, or delete the Students sheet from the copy you hand over,
if the agent should not see students' names.

## Coming from an earlier version

Earlier versions generated the timetable inside the app, with an optional AI timetabler.

- These variables are no longer read and can be deleted in Railway: `AI_PROVIDER`, `AI_API_KEY`, `AI_MODEL`,
  `AI_EFFORT`, `AI_BASE_URL`, `SOLVE_SECONDS`, `SOLVE_MAX_SECONDS`, `SOLVE_WORKERS`, `STAGED_FROM_CLASSES`,
  `MOCK_SOLVE_SECONDS`. Leaving them set does no harm.
- A timetable already published stays published.
- The `runs/` folder on the volume is no longer written and can be left.
- Generate, the chat and Adjust timetable are gone: make the timetable with the skill outside the app, then publish it
  on step 8.

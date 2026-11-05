# Deploy for your school

Each school runs its own copy of the app: one Railway service with its own volume, its own access codes and, if it
wants the AI timetabler, its own AI key. Nothing is shared between schools. The setup, the student list, every
generation run and the published timetable stay on that school's server and volume.

You need a Railway account and about 20 minutes. You can leave the AI key out: the app runs without AI, and you can add
a key later.

## 1. Create the service

1. On GitHub, fork this repository (or copy it into a repository of your own). Railway deploys from it, and you choose
   when to take updates.
2. In Railway: **New Project → GitHub repo** (link GitHub if it asks), and pick your repository. Choose **Add
   variables** instead of **Deploy Now** if you want to do step 3 first.
3. Railway builds it with the `Dockerfile`. `railway.json` sets the health check (`/healthz`) and restarts the app if it
   crashes. Nothing needs changing. Each push to the connected branch deploys again.

If the first deploy starts without a volume or variables, that is fine: the sign-in page lists what is missing (step 6).

## 2. Attach a volume

The setup, the saved copies of it, every generation run and the published timetable are files on the volume. Without
one, everything is lost on the next deploy.

1. Add a volume to the service: in the project canvas, right-click the service → **Attach Volume** (or open the command
   palette with ⌘K / Ctrl K, create a volume and pick the service).
2. Set the **mount path** to `/data`.

Railway then sets `RAILWAY_VOLUME_MOUNT_PATH=/data` and the app keeps everything there. On the volume:

| Folder or file | What |
|---|---|
| `setup.json` | the committee's saved setup, including the Students sheet |
| `setup_history/` | the last 20 copies that **Save progress** replaced |
| `runs/` | each Generate run: its copy of the setup, the chat (if the AI was on), the timetables it made |
| `published/` | the published timetable, PDFs, workbooks and the personal codes |

A school's data is small. The CTSS test copy (two runs and 20 saved setups) is about 5 MB before publishing; publishing
adds the PDFs and workbooks (about 30 MB for the 624-student sample school). The smallest volume Railway offers is
plenty.

A service with a volume runs one replica (Railway does not allow more), which is what the app needs: a generation run
lives in the web process. Because of the volume, each redeploy has a short downtime.

## 3. Set the variables

In the service, open **Variables**. **New Variable** adds one at a time; the **Raw Editor** takes the lines below in one paste. Replace every value; never put
real values in the repository.

```
SECRET_KEY=paste-a-long-random-string-here
COMMITTEE_CODE=
TEACHER_CODE=
STUDENT_CODE=
SCHOOL_NAME=
AI_PROVIDER=
AI_API_KEY=
```

To make a random string, run `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`, or use a password
manager's generator.

| Variable | Needed? | What it does | Safe default |
|---|---|---|---|
| `SECRET_KEY` | **yes** | Signs the sign-in cookies, and makes each student's personal code from their Student ID. Keep it once set: changing it signs everyone out and changes every personal code. | none: set a long random string. Without it, sign-ins end at every restart and personal codes are off: made without a key, anyone who knows a Student ID could work out that student's code. |
| `COMMITTEE_CODE` | **yes** | The timetable committee's code: setup editor, Generate, chat, preview, publish, downloads, personal codes. | none. At least 6 letters or digits. |
| `TEACHER_CODE` | **yes** | Teachers' code: every class, teacher, room and student timetable, Who's free, PDFs. | none. At least 6 letters or digits. |
| `STUDENT_CODE` | **yes** | Students' code: class timetables and **Build my timetable**. | none. At least 6 letters or digits. |
| `SCHOOL_NAME` | no | Shown on the sign-in page until a timetable is published (then the published school name is shown), and used to name a blank setup. | `School timetable` on the sign-in page |
| `AI_PROVIDER` | no | `anthropic`, `openai` or `openrouter` turns on the AI timetabler; `mock` is a scripted stand-in for testing; empty turns the AI off. | empty (AI off) |
| `AI_API_KEY` | with AI | The provider's API key. It stays on the server; browsers never see it. `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` or `OPENROUTER_API_KEY` also work. | empty (AI off) |
| `AI_MODEL` | with OpenAI or OpenRouter | The model name exactly as the provider lists it. | `claude-opus-5-5` for Anthropic; no default for the others |
| `AI_EFFORT` | no | Anthropic only: how hard the model thinks each turn, `low`, `medium`, `high`, `xhigh` or `max`; `none` leaves it to the model. Higher thinks longer and costs more. | `xhigh` |
| `AI_BASE_URL` | no | Another OpenAI-compatible endpoint. | the provider's own |
| `SOLVE_SECONDS` | no | The default time for one solve. The committee can pick longer on **Generate & publish** (**Solve for up to**). | `300` (5 min) |
| `SOLVE_MAX_SECONDS` | no | The longest one solve may run, for the committee and the AI. | `28800` (8 hours) |
| `SOLVE_WORKERS` | no | Solver threads. Match it to the service's vCPU (step 4). | `8` |
| `STAGED_FROM_CLASSES` | no | A school with this many classes or more gets its first timetable level by level, hardest level first (faster for a big, tight school). | `30` |
| `DATA_DIR` | no | Where the data goes, if not the volume. Leave it unset on Railway. | the volume's mount path, else `data/` in the app folder |
| `MOCK_SOLVE_SECONDS` | no | Testing only: how long each solve runs with `AI_PROVIDER=mock`. | `30` |

The access codes are compared ignoring case, spaces and dashes, and must all be different. After ten wrong codes in ten
minutes from one address, that address has to wait (up to ten minutes).

Railway sets `PORT`, `RAILWAY_ENVIRONMENT_NAME` and `RAILWAY_VOLUME_MOUNT_PATH` itself; don't set them.

Variable changes are staged: Railway shows them, and **Deploy** applies them with a redeploy. A redeploy stops a solve
that is running (step 4), so change variables when nobody is generating.

## 4. CPU and memory

The solver (OR-Tools CP-SAT) runs `SOLVE_WORKERS` search threads, 8 by default, and uses all the CPU it is given: more
vCPU gives better timetables in the same time.

- **Plan:** a service may use up to its plan's limit. The Free and Trial plans allow only a vCPU or two and up to 1 GB,
  too little for the solver; use Hobby or Pro. The current limits are on Railway's
  [plan resources](https://docs.railway.com/pricing/plans#default-plan-resources) page.
- **CPU:** 8 vCPU for the default 8 workers. With fewer vCPU, set `SOLVE_WORKERS` to the number of vCPU.
- **Memory:** about 1 GB is enough for a 1,500-student school; 2 GB leaves headroom.
- **Time:** a solve for a typical secondary school takes 5 to 30 minutes. The default is 5 minutes (`SOLVE_SECONDS`); for
  a tight timetable, pick a longer **Solve for up to** time (up to 8 hours). **Stop** keeps the best timetable found so
  far. A school with 30 or more classes gets its first timetable level by level; later solves start from the latest
  timetable, so they are quicker.
- **Billing:** Railway bills for what the service uses. A solve keeps every vCPU busy for as long as it runs; the rest of
  the time the app is idle.
- **Keep one gunicorn worker** (the `Dockerfile` runs `--workers 1 --threads 8`). A generation run lives in the web
  process, so more workers or replicas would lose track of it.
- **A redeploy or restart stops a running solve.** The run then shows read-only, and its last timetable can still be
  previewed and published.

## 5. Running without AI

Leave `AI_PROVIDER` (or `AI_API_KEY`) empty. On **Generate & publish** the committee sees "The AI timetabler is off" and
uses **Generate without AI**: it checks the setup, runs the same solver and shows the results, with why no timetable was
found and what to change, if it comes to that. The committee then changes the setup and generates again.

Everything else works without AI: the setup editor, **Fill blank teachers** on step 5, **Adjust timetable** (moves,
swaps, **Let the solver make room**), preview, publish, the teacher and student pages, personal codes and PDFs. Only
the chat, what-ifs, moves by chat and **Ask the AI** on Adjust need it.

With the AI off, nothing leaves the school's server (see [What the AI sees](#what-the-ai-sees)).

To try the whole flow before adding a key, set `AI_PROVIDER=mock`: a scripted stand-in checks, solves, asks one
question and finishes, and sends nothing out. Test once with the real key afterwards.

## 6. First sign-in and loading the setup

1. In the service: **Settings → Networking → Public Networking → Generate Domain**, then open the domain.
2. The sign-in page lists anything missing in amber: a code or `SECRET_KEY` not set, codes too short or the same, or no
   volume. Fix those first. The service's deploy logs show the same list at startup, with whether the AI is on.
3. Choose **Generate a new timetable** and enter the committee code.
4. Load your setup. On **Start**:
   - **Open a setup workbook (.xlsx)** reads a setup workbook into every step. It reads the app's own template and the
     CTSS layout (G-levels, "Class (2027)" on Students, Block and "Floor / level" on Venues, and extra sheets such as Roles,
     Combinations and notes). A school starting from the CTSS template can open a copy of it with its own data.
   - **Secondary school · blank** starts with typical subjects and a day shape, and you add rooms, classes, teachers and
     lessons. **Secondary school · sample** is a made-up 16-class school, to see how everything fits.
   - Blank and sample workbooks to fill in Excel are on **Files → Templates to share**.
5. The panel on the right lists anything that does not add up. Press **Save progress** to keep the setup on the server,
   where it opens by itself for the committee on any browser.
6. Add students on step 7 (optional; with them, no student gets two lessons at once and, with `SECRET_KEY` set, each
   gets a personal code).
7. On **Generate & publish**, generate, look at the preview, and **Publish**. Then give teachers the teacher code and
   students the student code. Once published, **Personal student codes** has the slips to print, one page per class,
   and the list as a CSV.

## What the AI sees

Only when the AI timetabler is on (`AI_PROVIDER` is `anthropic`, `openai` or `openrouter`, with a key). The school's
server then sends requests to that provider with the school's own key. What goes in them:

- **Instructions:** `skill/school-timetable-generator/SKILL.md`, the school's name and timetable name, and the
  committee's solve time.
- **The committee's chat messages**, as typed. Anything typed there is sent, so don't type students' details.
- **What the AI's tools return** (`timetabler.py`):
  - the setup's rules, lesson rows, teachers, classes (with their size and home room), subjects, bands, venues, day
    structure and settings. Teachers come with their names, short names, departments, roles, allowances, other duties
    and the subjects they can teach.
  - the timetable: each lesson's day, time, classes, subject, band, group code, teachers and room.
  - the results of checks, solves, what-ifs and moves: problems, after-school lessons, compromises (such as teachers over
    their allowance, by name) and which lessons moved.
  - for students, **numbers only**: how many students there are, how many have two lessons at once, how many students
    are in a group or take two clashing lessons, and (when Settings asks for no free periods) their free periods:
    average, most, and how many have none.
- **Ask the AI** on Adjust sends the clashing move: the lessons, group codes, teachers and how many students each
  group has.

What the AI never gets: the Students sheet (IDs, names, classes, groups), the Combinations sheet, personal codes, access
codes, `SECRET_KEY` and the published files. The solver uses the student list on the server, and the tool that shows
the setup refuses the Students and Combinations sheets. The AI cannot run code, open files or publish.

This was checked on the CTSS 2027 setup (1,219 students) and the sample schools: no student name or ID appears in the
instructions, in what check_setup, show_setup (every section), show_timetable and solve return, or in a run's chat
history.

The chat is kept on the school's volume, with each run (`runs/<run>/history.json`). How long the provider keeps
requests is set by the provider's terms for API use; check them before turning the AI on.

**With the AI off** (`AI_PROVIDER` or `AI_API_KEY` empty, or `AI_PROVIDER=mock`), nothing leaves the school's server:
the AI code (`ai.py`) is the only place the app calls out. The committee's editor page loads its font (Inter) from Google Fonts in the browser; no school data goes
with that request.

# School timetable app

One deployment per school. The timetable committee fills the setup step by step, presses **Generate**, talks
through any conflicts with the AI timetabler in a chat, and **publishes**. Teachers and students then open the
published timetable with their access code and download PDFs.

| Code (Railway variable) | Who | What they see |
|---|---|---|
| `COMMITTEE_CODE` | timetable committee | the setup editor, Generate with the chat, preview, publish, every download, the personal student codes |
| `TEACHER_CODE` | teachers | every class, teacher, room and student timetable, the lesson search, Who's free, PDFs |
| `STUDENT_CODE` | students | class timetables and **Build my timetable** (pick class and groups), PDFs of those |
| personal codes (made by the app) | one student each | only that student's own timetable and its PDF |

The student list goes in on step 8 of the setup (**Students**): paste it from Excel or a CSV, or upload an .xlsx or
.csv, with each student's ID, name, class and group codes; the committee can then edit each student's groups there.
It is optional, but with it the solver makes sure no student has two lessons at once, and every student gets a
personal code. Personal codes are made from each student's ID and `SECRET_KEY`, so they stay the same when the
timetable is republished. The committee downloads them as a list (CSV) or as slips to print, one page per class.
Students not on the list use the general student code and Build my timetable.

## How generating works

The AI does not place lessons itself; the solver does (OR-Tools, the same one the skill uses). The AI works as the
timetabler, with `skill/school-timetable-generator/SKILL.md` as its instructions and these tools:
check the setup and do the capacity sums, show parts of the setup, solve, diagnose (find which rule blocks a
timetable), ask the committee, change the setup (only what the committee chose), and finish. It cannot run code,
see anything outside the setup, or publish. The chat shows each step; a question appears with buttons, and the
committee can type at any time.

The AI works on a copy of the setup. **Keep the AI's changes in my setup** copies its changes back; **Publish** makes
the PDFs, the Excel workbook and the timetable pages and swaps them in for teachers and students (about a minute).
Without an AI set up, **Generate without AI** checks and solves, and the committee reads the results.

## Deploy on Railway

1. Put this folder in a GitHub repository (it has a `Dockerfile` and `railway.json`).
2. Railway: **New Project → Deploy from GitHub repo** → pick the repository.
3. **Add a volume** to the service, mounted at `/data`. The saved setup, generation runs and the published timetable
   live there; without a volume they are lost on every deploy (the committee page warns you).
4. **Variables** (service → Variables):

   | Variable | Value |
   |---|---|
   | `SECRET_KEY` | a long random string. Keep it: changing it signs everyone out and changes every personal student code |
   | `COMMITTEE_CODE`, `TEACHER_CODE`, `STUDENT_CODE` | at least 6 letters or digits each, all different (case, spaces and dashes are ignored) |
   | `AI_PROVIDER` | `anthropic`, `openai` or `openrouter` |
   | `AI_API_KEY` | **fill in:** the provider's API key (stays on the server). Left blank, the AI chat stays off and the committee can still generate without AI |
   | `AI_MODEL` | the model name exactly as the provider lists it. Anthropic defaults to `claude-opus-5-5` |
   | `SCHOOL_NAME` | optional: shown on the sign-in page before anything is published |
   | `SOLVE_SECONDS` | optional: the default time for one solve, 300 s. The committee can pick a longer **Solve for up to** time on Generate & publish, up to `SOLVE_MAX_SECONDS` (default 8 hours) |
   | `SOLVE_WORKERS` | optional: solver threads, default 8 |
   | `AI_BASE_URL` | optional: another OpenAI-compatible endpoint |

5. **Settings → Networking → Generate Domain**, open it and sign in with the committee code.

The solver uses all the CPU it is given, so more vCPU gives better timetables in the same time. A tight timetable can
take a long time to find: pick a longer **Solve for up to** time, and press Stop to keep the best one found so far.
When no timetable is found, the committee page shows why (classes with no room to spare, teacher loads, rooms,
rules) and what to change, with a button to each step. When the setup rules out every timetable (a room kind that
cannot hold its lessons, a class with more periods than its days), it says so straight away instead of solving.

A school with 30 or more classes (`STAGED_FROM_CLASSES`) gets its first timetable level by level, hardest level first,
then clashes between levels are cleared and the whole school is checked together (`ttgen/staged.py`, the skill's
`--staged` solve): one whole-school search can find nothing for hours on a big, tight school. Later solves start from
the latest timetable. A room holds one class at a time unless step 7 has a "Room · At most N at once" rule; a note on
a Settings row such as "Field and Hall take 2 classes each" is read as those rules.

**Rooms:** a group only goes in a room of its subject's kind that seats it (Venues **Capacity** = seats; the group size
is the Students sheet count for its code, the row's Students, or the class size). A room's **For** column keeps it for
some subjects, departments or levels (blank = anyone). A lesson row's **Special room weeks** (Odd or Even) gives the
group its lab or studio on that week only and a classroom on the other. The solver keeps enough suitable rooms free at
every period; afterwards each group gets the smallest free room that seats it (whole-class lessons their home room,
and a group keeps its room where it can). The checks flag a room too small, a room used against its purpose, a lesson
with no free room, and groups bigger than every room they may use (fix the seats or split the group). About 1 GB of
memory is enough for a 1,500-student school.

**Try it without a key:** `AI_PROVIDER=mock` runs a scripted stand-in for the AI (it checks, solves, asks one
question and finishes), so you can test the whole flow before adding a real key. Test once with your real key
after deploying.

## Run locally

```bash
pip install -r requirements.txt
export SECRET_KEY=dev COMMITTEE_CODE=COMMIT1 TEACHER_CODE=TEACH1 STUDENT_CODE=STUDY1 AI_PROVIDER=mock
python app.py            # http://localhost:8000  (or: gunicorn app:app --workers 1 --threads 8 --timeout 600)
```
Keep one gunicorn worker (with threads): a generation run lives in the web process.

**Saving the setup:** **Save progress** saves it for the school (on the volume), and it opens by itself after signing
in, on any browser. Every change is also kept in the browser until then (the header says "Unsaved changes"), and
**Undo** / **Redo** (⌘Z / ⇧⌘Z) step back through changes. **Save to file** and **Load from file** keep copies as
files. If someone else saved a newer setup in the meantime, Save progress asks before replacing it.

**Adjusting by hand before publishing:** the **Adjust timetable** step shows the latest timetable for any class,
teacher or room. Click a lesson, then move it earlier or later (← →), or cut it and click where it should go; make it
a period shorter or longer where it is. Each move is checked against the same rules as the solver (teachers, classes,
students, rooms, teacher availability and the rules on step 7). A move that clashes lists why and the ways out: free
times for that lesson, clean swaps, **Let the solver make room** (it keeps the lesson there and moves as few other
lessons as it can), **Ask the AI** (merging or splitting a group, another teacher), or placing it anyway. Moved lessons
are pinned, so later solves keep them; **Undo move** steps back. A shorter or longer lesson changes the plan (that
group gets a period fewer or more a cycle): **Keep these changes in my setup** puts it in the setup too. The exact
lesson lengths are kept in the app; in the setup workbook only the new number of periods is kept.

## What's inside

| Path | What |
|---|---|
| `app.py` | routes: sign-in, the committee's editor and generate/chat/publish API, the timetable pages, PDFs, downloads |
| `access.py` | access codes, personal codes, wrong-code limit (10 per 10 minutes per address) |
| `runs.py` | generation runs in a background thread with the event log the chat shows |
| `timetabler.py` | the timetabler's tools (check, show, solve, diagnose, ask, change, finish) and the no-AI flow |
| `adjust.py` | changing the latest timetable by hand: move, swap, shorten, check against the solver's rules, make room |
| `ai.py` | Anthropic / OpenAI / OpenRouter tool-calling loop; SKILL.md is the system prompt |
| `store.py` | saved setup, runs and the published timetable on the volume |
| `static/` | the committee's step-by-step editor and the sign-in page style |
| `ttgen/` | the Python package: template, reader, solver, checks and the Excel/PDF/HTML outputs |
| `skill/school-timetable-generator/` | the skill (`SKILL.md` + `scripts/ttgen`) for any AI agent outside the app |

`ttgen/` and `skill/school-timetable-generator/scripts/ttgen/` are the same package; change both together.

## Command line (without the app)

```bash
cd skill/school-timetable-generator/scripts
pip install -r requirements.txt
python -m ttgen check  My_School_Timetable_Setup.xlsx
python -m ttgen solve  My_School_Timetable_Setup.xlsx --out My_School_Timetable.xlsx --time 300 --export My_School_Outputs
python -m ttgen export My_School_Timetable_Setup.xlsx My_School_Timetable.xlsx --out My_School_Outputs
```

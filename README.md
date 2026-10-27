# Timetable Setup

A small web app that helps a school fill the **timetable setup workbook** step by step (rooms → classes → subjects →
teachers → blocks → lessons → rules), checks it as you go, and lets you download:

- your filled setup workbook (`.xlsx`, keeps drop-downs and formulas so it can still be edited in Excel);
- the **school-timetable-generator** skill (`SKILL.md` + solver scripts + sample templates) for an AI agent;
- sample and blank templates for Singapore secondary and primary schools (fictional data).

An AI agent with the skill (for example Claude with code execution) turns the workbook into a clash-free timetable:
a grid for every class, teacher and room.

## Run locally

```bash
pip install -r requirements.txt
python app.py            # http://localhost:8000
# or: gunicorn app:app --bind 0.0.0.0:8000
```

## Deploy on Railway

**From GitHub (recommended)**
1. Put this folder in a GitHub repository (it already has `Dockerfile` and `railway.json`).
2. In Railway: **New Project → Deploy from GitHub repo** → pick the repository. Railway builds the Dockerfile.
3. In the service: **Settings → Networking → Generate Domain**. Health check: `/healthz`.

**With the Railway CLI**
```bash
npm i -g @railway/cli
railway login
railway init        # create a project
railway up          # build and deploy this folder
railway domain      # get a public URL
```

**As a Railway template (one-click deploy for others)**
1. Deploy the service from GitHub as above and check it works.
2. In the project canvas: **Settings → Generate Template from Project** (or Workspace → **Templates → New Template** and add
   this GitHub repo as the service source).
3. Name it (e.g. *School Timetable Setup*), add a description, and **Create / Publish**. No variables or volumes are needed.
4. Railway gives you a template URL `https://railway.com/deploy/<code>`. Add the button below with that code:

```markdown
[![Deploy on Railway](https://railway.com/button.svg)](https://railway.com/deploy/<code>)
```

No database or environment variables are needed. Each person's progress is kept in their own browser
(and can be saved/loaded as a `.json` file from the top bar).

## What's inside

| Path | What |
|---|---|
| `app.py` | Flask app: pages, `/api/*` (sample, blank, build, import), `/download/*` |
| `static/` | the step-by-step editor (plain HTML/CSS/JS, no build step) |
| `ttgen/` | Python package that writes and reads the workbook (and solves it, used by the skill) |
| `skill/school-timetable-generator/` | the skill: `SKILL.md`, `scripts/ttgen` (same package), `scripts/requirements.txt` |

`ttgen/` and `skill/school-timetable-generator/scripts/ttgen/` are the same package; change both together.

## Generate a timetable yourself (without an agent)

```bash
cd skill/school-timetable-generator/scripts
pip install -r requirements.txt
python -m ttgen check  My_School_Timetable_Setup.xlsx
python -m ttgen solve  My_School_Timetable_Setup.xlsx --out My_School_Timetable.xlsx --time 300
```

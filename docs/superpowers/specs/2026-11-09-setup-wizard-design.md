# Setup wizard redesign: build the configuration in the app, generate the timetable outside

Date: 9 November 2026. Status: design, awaiting the committee's approval of this document. Project 1 of 4.

## Why

The committee gets better timetables when it hands the setup workbook and `SKILL.md` to an outside AI agent (Claude
Cowork) than from the app's own Generate. Generating inside the app is slow for a school this size (one level did not
solve in 10 minutes with whole-school CCE slots), and effort spent there is effort not spent on what the committee
actually struggles with: getting a complete, correct configuration out of many people.

So the app's job changes. It becomes:

1. the place where the committee and the department heads **build the configuration** together;
2. the place where the finished timetable is **published** to teachers and students.

The timetable itself is made outside, from two downloaded files, and comes back in a format the app can publish.

This document covers the first job only. The other projects, in the agreed order, are:

- Project 2: the return trip (upload, clash check, verify every parameter and constraint is accounted for, publish).
- Project 3: who sees what after publishing (students, per-teacher sign-in, heads see all).
- Project 4: relief (Telegram requests, AI assignment, relief load, morning notifications, ad hoc timetables).

## Who uses it

- **The timetable committee**: sets up the school, the day, venues, classes, subjects, roles and the constraints; uploads
  the teacher list; downloads the files; publishes.
- **Department heads and subject heads** (about 10 people): say which subjects each teacher can teach, create their
  teaching groups and bands, and put teachers on classes and groups. They work at the same time as each other.

Heads are not IT people. The current step 4 (a wide table with a "Can teach" pop-up per teacher) and step 5 (a 15-column
table) are what this redesign replaces as the main way in.

## Goals

- A head can deploy a department in one sitting, mostly by ticking teachers and dropping them into baskets.
- Several heads can work at once and nobody's work is lost.
- The committee can express every constraint: standard ones from drop-downs, anything else typed in plain words.
- One download gives an outside agent everything it needs, and what comes back can be published.

## Non-goals

- Generating or adjusting a timetable in the app. Both are removed (see "What is removed").
- Verifying the returned timetable against typed constraints (project 2).
- Students, per-teacher sign-in, relief (projects 3 and 4). The Students step stays as it is for now.
- A 3D map. A three.js mockup was tried and rejected; the map is 2D.
- Teacher photos.

## Anti-goals (it has failed if)

- One head's save overwrites another's work. Today `PUT /api/setup` replaces the whole setup; that must not survive.
- A setup saved today, or a workbook made by an earlier template (the school's v17 file), no longer opens.
- A rule is dropped without the committee being told (the fault PR #34 fixed; do not reintroduce it).
- Real teacher or student data lands in the public repository. Samples and tests use made-up names.
- The map only works by dragging. It must work with ticks and clicks (touch screens, keyboards).

## The steps

The left-hand step list becomes the one below. The numbers are today's, so they still match the workbook's sheets
(1 Venues … 4 Teachers) and the "step N" in every message; School and day stays unnumbered. *(Changed while building
stage 1: an earlier draft numbered School and day as 1, which would have shifted every message and sheet name.)*

| # | Step | Who mostly | What changes |
|---|------|-----------|--------------|
| – | Start | committee | opens the school's setup; whole-setup actions are guarded (see "One shared setup") |
| – | School and day | committee | school details, naming patterns, Day structure. The "Rules on the Settings sheet" card and the other Settings rows (end times, no free periods, floating recess) move to step 6 |
| 1 | Venues | committee | unchanged |
| 2 | Classes | committee | unchanged |
| 3 | Subjects | committee | unchanged |
| 4 | Teachers | committee (heads read, and may add a new teacher) | roles table first, then upload the teacher list; avatars |
| 5 | Department map | heads | new: capability, teaching groups, deployment, banding |
| 6 | Configuration and constraints | committee | replaces "Availability & rules" |
| 7 | Download | committee | workbook + the skill for the outside agent |
| 8 | Publish | committee | upload the finished timetable, check, publish (moved from Files) |
| – | Students | committee | unchanged, until project 3 |

"Generate & publish", "Adjust timetable" and "Files" go; what was useful there (the downloads, Make printouts, the
published status and codes) moves to Download and Publish, with Save to file and Load from file from the header.

### School and day: naming patterns

Group codes and band names are not typed by heads; they build themselves.

- **Group code**: as today (level digit + subject code + G-level letter + running number: `2MAP1`). The "Keep code"
  override stays for schools with old codes.
- **Band name**: suggested from level and subject ("Sec 2 Mathematics"); for a band of several subjects, level plus
  "Option" and a letter ("Sec 3 Option A"). The suggestion is editable. *(Designer's call: the committee said names
  form from Settings; the exact pattern was a guess they accepted.)*

### Step 4: Teachers

1. **Roles table** (exists as a card today): role, what it is, guide allowance, group. Filled first, because the upload
   checks roles against it.
2. **Upload the teacher list**: an Excel or CSV file, or pasted rows, like the Students upload today. Columns: Name,
   Short name, Department, Role, Allowance, Other duties, Note. Header names are matched loosely; a missing Allowance
   takes the role's guide allowance. *(Designer's call on the columns.)*
   - A teacher already in the setup (same name, ignoring case and spacing) is updated, never duplicated.
   - Teachers in the setup but not in the file are listed ("5 teachers are not in this file") with a button to remove
     them; nothing is removed silently, because removing a teacher empties their deployments.
   - Unknown roles and departments are listed for the committee to fix or add.
3. **Avatars**: every teacher gets a cartoon avatar drawn from their name (background colour, skin tone, hair shape
   and colour, glasses), as an inline SVG. The same name always gives the same avatar on every screen and device. A
   "new look" button on the profile stores a different seed for that teacher. No photos, no uploads. Avatar parts are
   picked from the name's hash, never from guessing anything about the person.
4. The existing teachers table stays as a "table view" for corrections.

### Step 5: Department map (2D)

The committee chose a 2D clickable mockup shown to them in conversation (it is not in the repository), plus the tick
boxes from a 3D try. Everything that mockup settled is written out below; where this text is silent, the builder
decides.

**Layout, three columns:**

- **Left, the roster.** A department switcher at the top (opens on the first department; every head can see and edit
  every department). The department's teachers, each with a tick box, avatar, name, role and a load bar (periods
  deployed + other duties against allowance; red when over). Above the list: **Select all** (shows a dash when only some
  are ticked), **Deselect all**, **Not placed yet** (ticks teachers with no subject). Shift-click ticks a run. A search
  box "Add a teacher from another department" puts that teacher on the roster for this visit: a teacher belongs to one
  department but may teach subjects of others.
  **+ New teacher** adds someone the department has just hired, or a post still to be filled: name (or a placeholder
  such as "New Mathematics teacher 1"), short name, department (the one on show), role and allowance (the role's
  guide by default). Heads may do this. The new teacher is marked provisional (the `provisional` field that exists
  today) until the committee confirms them on step 5, and gets an avatar like everyone else. A head can correct the
  details of a teacher still marked provisional; confirmed teachers' details are the committee's. *(Designer's call
  on the provisional mark and on who may correct what; the committee asked only that heads can add new teachers.)*
- **Middle, the baskets.** One basket per subject of the chosen department, showing the avatars of every teacher who
  can teach it (from any department), and a **staff room** for roster teachers with no subject yet. Ticking teachers and
  clicking a basket, or dragging them in, records "can teach". Dragging a ticked teacher drags all ticked teachers.
  Removing: drag out to the staff room, or ✕ on the profile.
- **Right, where they teach.** Tabs **Classes** (whole-class lessons), **Teaching groups** and **Bands**, filtered to
  the chosen department's subjects, with a level filter. Each card shows the code, subject, level, periods and the
  avatars of its teachers (up to three). Clicking a card, or dropping teachers on it, deploys the ticked teachers.
  - Deploying **adds** to the card's teachers (co-teaching); it never replaces. A card that would go past three says
    so and takes none. A teacher comes off a card with the ✕ on their avatar there.
  - On **Classes**, a card is one class with one subject ("1B Mathematics"). A lesson row that lists several classes
    shows as one card per class; changing the teachers of one of them moves that class to a row of its own (the
    solver and the checks already treat each class's whole-class lesson separately). *(Designer's call.)*
  - On **Teaching groups**, a card is one group code. On **Bands**, a card is a band, opening its groups; teachers go
    on the groups, not on the band.

**Profile.** Clicking an avatar (not its tick box) opens the teacher's profile beside the map: avatar, name, role,
department, load against allowance, subjects they can teach with the levels (All by default; editable here, as
`can_teach[].levels` today), and what they teach. Each item has a ✕ to remove it.

**Rule: basket before deployment.** A teacher must be in a subject's basket before going on a class or group of that
subject. Dropping one who is not says so and offers "Add to the basket and place". *(Designer's call, shown in the
mockup and not objected to.)*

**Creating groups and bands (same step, a second view "Groups and bands").**

- **New teaching group**: level, subject, G-level, classes it draws from, students (optional), band (optional). The
  code appears as they pick. "Add one per class" for a whole-class subject, as the helper does today.
- **Bands page**: bands as lanes; unbanded groups and classes in a pool on the left. Tick or drag groups (or whole
  classes, for a subject) into a band; everything in a band has lessons at the same time. New band: level and subject
  give the suggested name. The lane warns at once when one teacher is on two groups of the same band (today's critical
  check "twice in this band").
- The existing 15-column table stays as a "table view" of the same data, for bulk edits (lesson pattern, periods
  override, special room weeks, Teacher 3).

**What it writes.** Nothing new in the data: baskets are `teachers[].can_teach`, cards are `lessons[]` rows with
`teachers`, bands are `blocks[]` and `lessons[].block`. The map is a new view over the existing spec, so the workbook
and `ttgen` reader need no change for it.

### Step 6: Configuration and constraints

- **Configuration**: the school-wide settings that are on School & day today (once a day per group, after-school slots,
  most PE classes at once, a teacher's daily cap, a recess a day, rain rooms, end times, students' free periods,
  floating recess). Same fields, new home.
- **Constraints**, under tabs **School · Levels and classes · Subjects · Venues · Teachers**. Each tab has:
  - **Standard rules**, from drop-downs: the rule types that exist today (after PR #34), shown under the tab their
    "applies to" belongs to. Teacher block-outs (clock times) are under Teachers; fixed lessons, the HBL day and
    "every class at one time" under School or Levels and classes; "only in venues" under Subjects; room limits under
    Venues. The one-click buttons from PR #34 stay. The warnings under a rule that cannot be used stay.
  - **Typed rules**, for anything the list cannot say: a sentence, **Must** or **Prefer**, and what it applies to
    (whole school, a level, a class, a subject, a venue, a teacher; picked from the same lists). Example: "Must · Sec 1 ·
    No PE in the first period".

**How typed rules are stored and handed over.** *(Designer's call.)* A typed rule is a rule row with rule type "In
words" and the sentence as its text. The workbook gets them on the More rules sheet with Rule = "In words" and the
sentence in a new "In words" column (older workbooks without the column still read). `ttgen` does not enforce them;
`ttgen check` lists them as "for the agent to honour". `SKILL.md` tells the agent: honour every Must, try every
Prefer, and in the hand-back say for each typed rule how it was met or why it could not be. Project 2 builds its
verification on that list.

### Step 7: Download

- **Configuration workbook (.xlsx)**: as "Build workbook" today, with the typed rules and a **configuration id** on
  the Settings sheet (the setup's version when it was downloaded), so a returned timetable can be matched to the
  configuration it was made from.
- **The skill (.zip)**: `SKILL.md` with the `ttgen` scripts. This is the hand-over the page leads with, because only
  the scripts make a file that matches. `SKILL.md` on its own is offered second, for a chatbot that cannot run code.
  *(Designer's call: the committee asked for "SKILL.md and the configuration files"; the zip is how the agent gets
  the scripts.)*
- **A starter prompt** to paste into the chatbot with the files, with a Copy button. It says: use the attached skill,
  not an older installed copy; what to produce; in which format; and to fill in the rule report (below).
- Before downloading, the page shows "Things to fix" (critical first), so the committee does not hand over a setup
  with rules that cannot be used or teachers in two places.
- Save to file and Load from file (in the page header today). Restoring an earlier copy of the whole setup is one of
  the whole-setup actions under "One shared setup".

**What must come back.** *(Designer's calls.)*

- An agent that can run code hands back the timetable database (`.sqlite`) written by the skill's `ttgen export`. An
  agent that cannot hands back a workbook with a Lessons sheet, the simple format `SKILL.md` documents. `SKILL.md`'s
  "Building it without the scripts" section stays, but ends in that Lessons workbook, never in a database of the
  agent's own design. (The school's last outside timetable came back as a custom database that needed the setup
  workbook beside it and showed 47 differences; the instructions should stop that at the source.)
- **The agent does not change the configuration.** It may turn a typed rule into whatever its solver needs, but the
  setup inside the returned database is the one downloaded, with the same configuration id.
- **A rule report comes back as data, not as chat.** One line per typed rule: its number, Must or Prefer, the
  sentence, **Met / Partly / Not met**, and a sentence saying how or why. It is a `Rule report` sheet in the Lessons
  workbook; `ttgen export` carries it into the database as a table. Both copies of `ttgen` change for this. In this
  project the app only keeps and shows it on Publish; project 2 checks it.
- `SKILL.md` gets a version line, and the workbook's README sheet names the version it needs, so an agent working
  from an older installed skill can tell.

### Step 8: Publish

The "A timetable made outside the app" card (PR #33) becomes this step: choose the file, **Check, then publish**,
**Make printouts**, and below it what is published now, the access codes and the personal-code slips (from Generate &
publish today). Project 2 extends the check.

## Working together

### One shared setup

There is one setup, the school's, kept on the server. The wizard always works on it; the browser's own copy
(`localStorage`) is only a cache for a dropped connection. *(Designer's calls in this section.)*

- **Whole-setup actions** replace the school's setup for everyone: start blank, open a setup workbook, load from
  file, restore an earlier copy. They are committee-only, say plainly what they replace and who else is working in it,
  and take a restore point first.
- **The sample schools** open as a **practice copy**: in this browser only, with a banner saying nothing here is saved
  for the school, no sharing and no publish. Leaving it returns to the school's setup.
- **Rollout day.** A browser holding unsaved changes from before the change is asked once: use them (replacing the
  school's setup, committee only), save them to a file, or discard them.

### Access

Heads share one code (`HEADS_CODE`, a Railway variable like the others) and see every department. The committee code
does everything.

**What the heads' code may change** (confirmed by the committee: the department map, and adding new teachers):

| | Heads | Committee |
|---|---|---|
| Step 6: can teach, teaching groups, bands, who teaches what | edit | edit |
| Adding a new teacher (a new hire), from the map's roster or step 5 | yes | yes |
| Step 5: changing an existing teacher's details, the upload, removing teachers, the roles table | read | edit |
| Steps 1 to 4 and 7: school, day, venues, classes, subjects, constraints | read | edit |
| Step 8: downloads (the workbook holds the student list) | no | yes |
| Step 9: publish, access codes, personal-code slips | no | yes |
| Whole-setup actions | no | yes |
| Students step | no | yes |

Permissions are enforced on the server for each kind of change, not only hidden in the page.
- **Saving.** Every change saves by itself; "Save progress" goes. Two people changing different things both keep
  their work. Two people changing the same thing: the later one wins, and the other sees it change within a few
  seconds. Each person's Undo undoes their own changes only.
- **Seeing each other.** A change made by someone else appears without reloading (the page already polls every few
  seconds). A small "3 others here" marker is enough; no cursors, no chat.
- **Earlier copies.** The server keeps restore points as today (the last 20), now taken on a timer or before bulk
  actions (teacher upload, removing teachers), since there is no Save press.
- The server runs one gunicorn worker with threads, so an in-process lock is enough to apply changes in order.

How changes are sent and merged (per-field operations, row identities, version numbers) is left to the builder. The
spec refers to rows by position and by name today; the builder decides whether rows need stable ids.

## What is removed

*(Designer's call, from "generation should not be done in the app itself".)*

- Routes: `/api/generate`, `/api/message`, `/api/stop`, `/api/keep-changes`, `/api/publish` (the in-app run's publish),
  `/api/adjust/*`, `/api/allocate`.
- Files: `timetabler.py`, `ai.py`, `adjust.py`, `runs.py`, and their parts of `static/app.js`.
- Variables: `AI_PROVIDER`, `AI_API_KEY`, `AI_MODEL`, `SOLVE_SECONDS`, `STAGED_FROM_CLASSES`. `docs/DEPLOY.md` and the
  README say so.
- `ttgen/` stays whole, in the app and in the skill: the app needs the reader, template, checks and exports; the
  outside agent needs the solver. The two copies stay identical.

"Fill blank teachers" (`/api/allocate`) goes with the rest; deployment is the heads' job on the map.

## Constraints on the build

- Flask and one vanilla JS file with no build step, as today. No framework, no bundler. The map is HTML and SVG.
- Data is JSON on the Railway volume. No database server.
- The repository is public: no secrets, no real names, never commit `.claude/launch.json` or `data/`.
- Dark and light are not a concern today (the editor is light only); keep it so.
- Works on a laptop and on a tablet in landscape.
- Tests: the project has no test suite. Each phase is checked by hand in the browser preview and with scripts against
  the sample schools, as PRs #33 and #34 were. A builder may add tests but is not asked to.

## Suggested order of building

Each is a pull request the committee can try on its own.

1. **Steps and removal**: the new step list, settings moved to step 7, Download and Publish steps, Generate and
   Adjust removed.
2. **Working together**: heads' code, changes that save themselves and merge.
3. **Teachers**: roles first, upload, avatars.
4. **Department map**: roster with ticks, baskets, cards, profile.
5. **Groups and bands**: creation with automatic names, the bands page.
6. **Constraints**: the tabs, typed rules, workbook and SKILL.md changes, starter prompt.

## Left to the builder

- The change-merging mechanism and whether rows get ids.
- The avatar artwork (parts and palette), as long as it is deterministic and cartoon-like.
- Exact wording and layout within the screens described.
- How the map behaves with a large department (40 teachers): scrolling, grouping or a filter.
- Whether the old steps' code is reshaped or rewritten.

"""School timetable app (one school per deployment).

Committee (COMMITTEE_CODE): fill the setup step by step, download it with the timetable skill for an outside AI agent
to make the timetable, then upload that timetable, check it and publish it.
Teachers (TEACHER_CODE): every published class, teacher, room and student timetable, Who's free, PDFs.
Students (STUDENT_CODE): class timetables and 'Build my timetable'; personal codes show one student's own timetable.
Staff (a personal code each, made from their name): the Relief module and everything the teacher code opens."""
import copy, gzip, io, os, re, shutil, sys, tempfile, traceback, zipfile
from functools import wraps
from flask import Flask, jsonify, request, send_file, abort, session, redirect, Response
from werkzeug.middleware.proxy_fix import ProxyFix
from ttgen.samples import secondary, primary
from ttgen.template import write_template
from ttgen.reader import read_template
from ttgen.spec import RULE_TYPES, SCOPES, CODES, SETTING_RULES, ROLES, SKILL_VERSION, defaults, typed_rules
import access, checks, draft, store, sync, typed
from relief import codes as relief_codes, lessons as relief_lessons, people as relief_people, settings as relief_settings, web as relief_web
from relief import absences as relief_absences
import exams.relief_links as exams_relief_links
from ttgen import choices
import datetime
import exams.approval as exams_approval, exams.review as exams_review, exams.days as exams_days, exams.settings as exams_settings, exams.schedules as exams_schedules, exams.papers as exams_papers, exams.invigilate as exams_invigilate, exams.make as exams_make, exams.seating as exams_seating, exams.printouts as exams_printouts, exams.published as exams_published, exams.events as exams_events

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.join(HERE, "skill", "school-timetable-generator")
app = Flask(__name__, static_folder="static", static_url_path="/static")
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
app.secret_key = os.environ.get("SECRET_KEY") or os.urandom(32)
app.json.sort_keys = False   # the setup's days (Mon..Fri) and levels keep their order through the API; the grid lists days in it
app.config.update(MAX_CONTENT_LENGTH=40 * 1024 * 1024, SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
                  SESSION_COOKIE_SECURE=store.on_railway(), PERMANENT_SESSION_LIFETIME=60 * 60 * 24 * 120)
limiter = access.Limiter()
_cache = {}
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

# ------------------------------------------------------------------------------------------------ access
def role(): return session.get("role")

def need(*roles):
    def deco(f):
        @wraps(f)
        def inner(*a, **k):
            if role() not in roles:
                if request.path.startswith(("/api/", "/pdf/", "/files/")): return {"error": "Please sign in again."}, 401
                return redirect("/login")
            if role() == "staff" and me_staff() is None:   # dropped or renamed on a later publish: me_staff has ended the session
                if request.path.startswith(("/api/", "/pdf/", "/files/")): return {"error": "Please sign in again."}, 401
                if store.published(): return _no_longer_valid()
                # nothing published (a publish is swapping folders): the session stays; the page says "Not published yet"
            return f(*a, **k)
        return inner
    return deco

def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

def setup_problems():
    """what this deployment is missing (Railway variables, a volume): on the sign-in page and in the logs at startup"""
    _, probs = access.configured()
    if not store.on_volume(): probs.append("No Railway volume: the setup and the published timetable are lost on the next deploy. Add a volume mounted at /data.")
    return probs

def startup_log():
    print(f"Timetable app: data in {store.DATA}", file=sys.stderr, flush=True)
    for p in setup_problems(): print(f"WARNING: {p}", file=sys.stderr, flush=True)

def page(title, body):
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)}</title>
<link rel="stylesheet" href="/static/login.css"></head><body>{body}</body></html>"""

# the choices on the front page; each one accepts only its own kind of code
CHOICES = {
    "committee": dict(title="Build and publish the timetable", blurb="Timetable committee: build the setup, download it, publish the timetable.",
                      label="Committee code", hint="Use the code given to the timetable committee.", roles=("committee",)),
    "heads": dict(title="Department heads", blurb="Heads of department: who teaches which class and group, teaching groups and bands.",
                  label="Heads' code", hint="Use the code given to heads of department.", roles=("head",)),
    "teacher": dict(title="Teacher's timetable", blurb="Every class, teacher and room timetable, Who's free and PDFs.",
                    label="Teacher code", hint="Use the teacher code the school gave you.", roles=("teacher", "staff")),
    "relief": dict(title="Relief", blurb="Ask for or plan relief, set work, see your reliefs.", label="Your personal code",
                   hint="Use the personal code on the slip from the timetable committee.", roles=("staff",), img="/static/choice-relief.svg"),
    "exams": dict(title="Exams and events", blurb="Exam and test schedules, seating and invigilation; school events.", label="Your personal code",
                  hint="Use the personal code on the slip from the timetable committee.", roles=("staff",), img="/static/choice-exams.svg"),
    "student": dict(title="Student timetable", blurb="Your class timetable, or your own with a personal code.",
                    label="Student code or personal code", hint="Use the student code the school gave you. A personal code shows only your own timetable.",
                    roles=("student", "personal")),
}
CHOICE_OF = {r: k for k, c in CHOICES.items() for r in c["roles"]}   # a staff code on another card points to Relief (the later card)
CHOICE_OF["staff"] = "relief"
NO_PERSONAL_STAFF = "Personal codes are off until SECRET_KEY is set in Railway variables."

def img_of(k): return CHOICES[k].get("img") or f"/static/choice-{k}.png"

@app.get("/login")
def login_page(msg="", choice=None, fix=None):
    pub = store.published(); school = (pub["meta"]["school"] if pub else None) or os.environ.get("SCHOOL_NAME") or "School timetable"
    warn = "".join(f"<p class='warn'>{esc(p)}</p>" for p in setup_problems())
    link = f' <a href="/login?as={fix}">Open {esc(CHOICES[fix]["title"])}</a>' if fix else ""
    err = f"<p class='err'>{esc(msg)}{link}</p>" if msg else ""
    choice = choice or request.args.get("as")
    c = CHOICES.get(choice or "") if choice != "heads" or os.environ.get("HEADS_CODE") else None
    if not c:
        cards = "".join(f"""<a class="choice" href="/login?as={k}"><img src="{img_of(k)}" alt="" width="112" height="112">
<span class="txt"><b>{esc(v["title"])}</b><span class="muted small">{esc(v["blurb"])}</span></span><span class="go">Enter code &rarr;</span></a>""" for k, v in CHOICES.items() if k != "heads" or os.environ.get("HEADS_CODE"))
        return page("Sign in", f"""<main class="front"><header class="hero"><h1>{esc(school)}</h1><p>Timetable</p></header>
<nav class="choices">{cards}</nav>{f'<div class="notes">{err}{warn}</div>' if err or warn else ""}</main>""")
    form = f"""<form method="post" action="/login"><input type="hidden" name="as" value="{choice}"><label for="code">{esc(c["label"])}</label>
<input id="code" name="code" autocomplete="off" autocapitalize="characters" autofocus required>
<button type="submit">Open</button></form>"""
    if choice == "relief" and not access.personal_codes_on(): form = f"<p class='warn'>{esc(NO_PERSONAL_STAFF)}</p>"
    return page(c["title"], f"""<main class="login"><p class="small"><a class="back" href="/login">&larr; Other choices</a></p>
<div class="picked"><img src="{img_of(choice)}" alt="" width="56" height="56"><span><h1>{esc(c["title"])}</h1><p class="muted">{esc(school)}</p></span></div>
{form}{err}
<p class="muted small">{esc(c["hint"])}</p>{warn}</main>""")

@app.post("/login")
def login():
    who = request.remote_addr or "?"
    choice = request.form.get("as")
    if choice not in CHOICES: return redirect("/login")
    if limiter.blocked(who): return login_page("Too many wrong codes. Wait ten minutes and try again.", choice), 429
    pub = store.published()
    r, sid = access.match(request.form.get("code"), pub["codes"] if pub else {}, relief_people.staff_codes(relief_staff(pub)) if pub else {})
    if not r:
        limiter.fail(who); return login_page("That code does not work. Check it and try again.", choice), 401
    if r not in CHOICES[choice]["roles"]:   # a real code, but for another choice: not a guess, so no limiter strike
        return login_page(f"That code is not for {CHOICES[choice]['title']}.", choice, fix=CHOICE_OF[r]), 403
    session.clear(); session.permanent = True; session["role"] = r
    if r == "staff": session["who"] = sid; return redirect({"relief": "/relief", "exams": "/exams"}.get(choice, "/timetable"))
    if sid is not None: session["sid"] = sid
    return redirect({"committee": "/", "head": "/", "personal": "/me"}.get(r, "/timetable"))

@app.get("/logout")
def logout():
    session.clear(); return redirect("/login")

@app.get("/healthz")
def health(): return {"ok": True}

# ------------------------------------------------------------------------------------------------ committee: setup editor
@app.get("/")
def index():
    if role() in ("committee", "head"): return app.send_static_file("index.html")
    if role() == "personal": return redirect("/me")
    if role() == "staff": return redirect("/relief")
    if role() in ("teacher", "student"): return redirect("/timetable")
    return redirect("/login")

def kind_ok(kind):
    if kind not in ("primary", "secondary"): abort(404)
    return kind

def sample(kind):
    if ("s", kind) not in _cache: _cache[("s", kind)] = secondary() if kind == "secondary" else primary()
    return copy.deepcopy(_cache[("s", kind)])

def blank(kind):
    s = sample(kind)
    keep = [r for r in s["rules"] if r["rule"] in ("Once a day per group", "Avoid after-school slots")]
    s.update(venues=[], classes=[], teachers=[], blocks=[], lessons=[], students=[], combinations=[], rules=keep)
    s["school"]["name"] = os.environ.get("SCHOOL_NAME") or "My School"
    return s

def xlsx_bytes(spec):
    buf = io.BytesIO(); write_template(spec, buf); buf.seek(0); return buf

@app.get("/api/meta/<kind>")
@need("committee", "head")
def meta(kind):
    sc = defaults(kind_ok(kind))
    return jsonify(rule_types=[dict(rule=a, scopes=b, needs_time=c == "Y", needs_number=d == "Y", meaning=e, example=f) for a, b, c, d, e, f in RULE_TYPES],
                   scopes=SCOPES, codes=CODES, defaults=sc, setting_rules=SETTING_RULES,
                   roles=[dict(role=a, what=b, allowance=c, group=d) for a, b, c, d in ROLES], skill_version=SKILL_VERSION)

@app.get("/api/sample/<kind>")
@need("committee", "head")
def api_sample(kind): return jsonify(sample(kind_ok(kind)))

@app.get("/api/blank/<kind>")
@need("committee")
def api_blank(kind): return jsonify(blank(kind_ok(kind)))

@app.post("/api/build")
@need("committee")
def build():
    spec = request.get_json(force=True, silent=True)
    if not spec or "school" not in spec: return {"error": "No setup data sent."}, 400
    for k in ("venues", "classes", "subjects", "teachers", "blocks", "lessons", "rules", "students", "choices"): spec.setdefault(k, [])
    spec["school"]["config_id"] = store.config_id(spec)
    try: buf = xlsx_bytes(spec)
    except Exception as e: return {"error": f"Could not build the workbook: {e}"}, 400
    name = "".join(ch for ch in (spec["school"].get("name") or "School") if ch.isalnum() or ch in " -_").strip().replace(" ", "_") or "School"
    return send_file(buf, as_attachment=True, download_name=f"{name}_Timetable_Setup.xlsx", mimetype=XLSX)

@app.post("/api/import")
@need("committee")
def import_xlsx():
    f = request.files.get("file")
    if not f: return {"error": "No file."}, 400
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        f.save(tmp.name); path = tmp.name
    try: spec = read_template(path)
    except Exception as e: return {"error": f"That does not look like a setup workbook from this app ({e})."}, 400
    finally: os.unlink(path)
    return jsonify(spec)

def normalise(spec):
    """the editor's JSON -> the exact spec an agent would read from the workbook (codes, periods and lesson lengths worked out)"""
    for k in ("venues", "classes", "subjects", "teachers", "blocks", "lessons", "rules", "students", "choices"): spec.setdefault(k, [])
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp: path = tmp.name
    try:
        write_template(spec, path); return read_template(path)
    finally: os.unlink(path)

@app.post("/api/check")
@need("committee")
def check_setup():
    """Will it fit? The sums on the setup as it is in the editor, before it goes to an outside agent: class periods
    against the day, lessons against the stretches between breaks, special rooms, teachers' time, rules that cannot be
    used. Returns every finding, critical first"""
    spec = request.get_json(force=True, silent=True)
    if not spec or "school" not in spec: return {"error": "No setup data sent."}, 400
    try:
        norm = normalise(copy.deepcopy(spec)); found = checks.findings(norm)
        fall = checks.with_fallbacks(norm) if norm.get("choices") else None
    except Exception as e: return {"error": f"The setup could not be checked: {e}"}, 400
    crit = sum(1 for f in found if f["level"] == checks.CRITICAL)
    return jsonify(findings=found, critical=crit, warnings=len(found) - crit, fallbacks=fall)

@app.post("/api/read-table")
@need("committee")
def read_table():
    """the rows of an uploaded spreadsheet. On the Students step: its Students sheet if it has one, else its first sheet.
    With the form field sheet=teachers (step 4): the first sheet whose name contains "teacher", else its first sheet"""
    import openpyxl
    f = request.files.get("file")
    if not f: return {"error": "No file."}, 400
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        f.save(tmp.name); path = tmp.name
    try:
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        if request.form.get("sheet") == "teachers":
            ws = next((w for w in wb.worksheets if "teacher" in w.title.lower()), wb.worksheets[0])
        else: ws = wb["Students"] if "Students" in wb.sheetnames else wb.worksheets[0]
        cell = lambda v: "" if v is None else str(int(v)) if isinstance(v, float) and v.is_integer() else str(v).strip()
        rows = [[cell(v) for v in r] for r in ws.iter_rows(max_row=5000, max_col=60, values_only=True)]
        wb.close()
        width = max((max((i + 1 for i, v in enumerate(r) if v), default=0) for r in rows), default=0)
        rows = [r[:width] for r in rows]   # max_col pads every row to 60: keep only the columns that hold something
    except Exception as e: return {"error": f"Could not read that file ({e})."}, 400
    finally: os.unlink(path)
    return {"rows": [r for r in rows if any(r)]}

@app.get("/api/setup")
@need("committee", "head")
def get_setup():
    r = store.setup_record()
    return jsonify(spec=r["spec"], v=r["v"], saved_at=r["saved_at"])

@app.put("/api/setup")
@need("committee")
def put_setup():
    """Save the whole setup (body {spec, why}; a bare spec is accepted too): everyone who has it open fetches it again"""
    body = request.get_json(force=True, silent=True)
    body = body if isinstance(body, dict) else {}
    spec, why = (body, "Saved") if "school" in body else (body.get("spec"), str(body.get("why") or "Saved")[:80])
    if not isinstance(spec, dict) or "school" not in spec: return {"error": "No setup data sent."}, 400
    return store.replace_setup(spec, why)

def _changes_reply(since, client, upto=None):
    return {**store.changes_since(since, client, upto), "others": store.seen(client)}

def _int(x):
    try: return int(x)
    except (TypeError, ValueError): return 0

@app.get("/api/setup/changes")
@need("committee", "head")
def get_setup_changes():
    return _changes_reply(_int(request.args.get("since")), str(request.args.get("client") or "")[:40])

@app.post("/api/setup/changes")
@need("committee", "head")
def post_setup_changes():
    """a change as operations; the answer carries what others changed meanwhile, so the caller catches up in the same call"""
    body = request.get_json(force=True, silent=True)
    body = body if isinstance(body, dict) else {}
    client, ops = str(body.get("client") or "")[:40], body.get("ops")
    if not isinstance(ops, list): return {"error": "No changes sent."}, 400
    split = None
    if role() == "head":
        # judged one operation at a time on the setup as it is under the store's lock, when the change is applied: what a
        # head may not make is skipped and named in the answer, the rest of their work is applied
        split = sync.head_split
        for op in ops:      # a teacher added by a head is provisional until the committee confirms
            if isinstance(op, list) and len(op) == 4 and op[0] == "add" and op[1] == "teachers" and isinstance(op[2], dict): op[2]["provisional"] = "Yes"; op[2].pop("dept2", None)
    since = _int(body.get("since"))
    try: v, refused, mine = store.apply_changes(ops, client, since=since, filter=split)
    except store.Replaced: return _changes_reply(since, client)
    except store.Refused as e: return {"error": str(e)}, 403
    except LookupError: return {"error": "There is no saved setup to change yet."}, 409
    reply = _changes_reply(since, client, v)
    if mine is not None: reply["mine"] = mine    # the version of the sender's own ops: the page applies patches below it first and above it last
    if refused: reply["refused"] = [dict(i=i, why=why) for i, why in refused]
    return reply

@app.get("/api/setup/copies")
@need("committee")
def get_setup_copies():
    return jsonify(store.copies())

@app.post("/api/setup/restore")
@need("committee")
def restore_setup():
    body = request.get_json(force=True, silent=True)
    try: return store.restore(str((body or {}).get("id") or ""))
    except KeyError: return {"error": "That copy is not there any more."}, 404

@app.get("/api/past-setups")
@need("committee")
def past_setups():
    """earlier copies to restore emptied student groups and band classes from: who has groups and which bands have
    classes in each (the editor fills only what is empty now)"""
    return {"copies": [dict(id=x["id"], what=x["what"], when=x["when"],
                            groups={str(s.get("id") or s.get("name") or "").strip(): s["groups"] for s in x["spec"].get("students") or [] if s.get("groups")},
                            classes={b["block"]: b["classes"] for b in x["spec"].get("blocks") or [] if b.get("block") and b.get("classes")})
                       for x in store.past_setups()[:12]]}

def _save_uploads(work):
    """the setup workbook and timetable sent with the request, saved in work: (setup path or None, timetable path). A
    database this app or the skill made holds its setup, so it can come alone."""
    from ttgen.database import is_db
    a, b = request.files.get("setup"), request.files.get("timetable")
    if not b: raise ValueError("Send the timetable: a workbook with a Lessons sheet, or a timetable database (.sqlite).")
    tp = os.path.join(work, "timetable" + (".sqlite" if str(b.filename or "").lower().endswith((".sqlite", ".sqlite3", ".db")) else ".xlsx")); b.save(tp)
    sp = None
    if a: sp = os.path.join(work, "setup.xlsx"); a.save(sp)
    elif not is_db(tp): raise ValueError("Send the setup workbook too (only a timetable database from this app can come alone).")
    return sp, tp

def _uploaded_timetable(work):
    """the files sent with the request, read against their own setup: (setup path or None, timetable path, export model)"""
    from ttgen.export import model_from_files
    sp, tp = _save_uploads(work)
    try: m = model_from_files(sp, tp)
    except Exception as e: raise ValueError(f"Could not read the files: {e}")
    if not m["lessons"]: raise ValueError("The timetable has no lessons.")
    return sp, tp, m

def _zip_response(m, out, base):
    """the printouts folder out (named base inside the zip) as the zip answer, with the X-Checks sentence of the model m"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _, files in os.walk(out):
            for fn in sorted(files): full = os.path.join(root, fn); z.write(full, os.path.join(base, os.path.relpath(full, out)))
    buf.seek(0); ch = m["checks"]
    resp = send_file(buf, as_attachment=True, download_name=f"{base} - timetables.zip", mimetype="application/zip")
    resp.headers["X-Checks"] = "All checks passed." if ch["ok"] else f"{len(ch['problems'])} problems found: see the Read me sheet or the Checks tab."
    return resp

@app.post("/api/export")
@need("committee")
def export_printouts():
    """setup workbook + timetable (a workbook with a Lessons sheet, or a timetable database) -> zip with the combined
    Excel, the HTML finder, the PDFs and the database. A database this app made holds its setup, so it can come alone."""
    from ttgen.export import export_all, safe_name
    work = tempfile.mkdtemp(prefix="tt-")
    try:
        try: _, _, m = _uploaded_timetable(work)
        except ValueError as e: return {"error": str(e)}, 400
        base = safe_name(f"{m['school']['name']} {m['school']['timetable']}")
        out = os.path.join(work, "out", base)
        export_all(m, out, individual=request.form.get("single", "1") == "1", zip_individual=False, log=lambda *x: None)
        return _zip_response(m, out, base)
    finally: shutil.rmtree(work, ignore_errors=True)

NO_SETUP = "Save the school's setup first: the timetable is checked against it."

def _checked(build, sentences=False):
    """the draft checked against the setup, as JSON; a check that goes wrong is a sentence (400), not a server error.
    sentences: a ValueError is already a sentence for the committee, and no draft is a 404"""
    try: return jsonify(build())
    except draft.NoDraft as e: return {"error": str(e)}, 404
    except ValueError as e: return {"error": str(e) if sentences else f"Could not read the files: {e}"}, 400
    except Exception as e:
        if type(e) is LookupError: return {"error": NO_SETUP}, 409   # no setup saved (a KeyError or IndexError is a fault in the check)
        app.logger.exception("checking the draft")
        return {"error": f"Could not check the timetable against the setup: {e}"}, 400

@app.post("/api/draft")
@need("committee")
def draft_upload():
    """a timetable made outside the app (the skill with an AI agent, or another program) becomes the draft: kept on the
    server and checked against the saved setup. A draft with fixes that were never published is replaced only with replace=1."""
    spec, _ = store.load_setup()
    if not spec: return {"error": NO_SETUP}, 409
    work = tempfile.mkdtemp(prefix="tt-")
    try:
        try:
            sp, tp = _save_uploads(work)
            m = draft.save(sp, tp, os.path.basename(str(request.files["timetable"].filename or "").replace("\\", "/"))[:120] or "an uploaded file", spec,
                           replace=request.form.get("replace") == "1")
        except draft.UnpublishedFixes as e: return {"error": str(e), "fixes": e.count}, 409
        except ValueError as e: return {"error": str(e)}, 400
        return _checked(lambda: draft.info(model=m))
    finally: shutil.rmtree(work, ignore_errors=True)

@app.get("/api/draft")
@need("committee")
def draft_get():
    return _checked(lambda: draft.info() or {"draft": None})

@app.post("/api/draft/decide")
@need("committee")
def draft_decide():
    body = request.get_json(force=True, silent=True); body = body if isinstance(body, dict) else {}
    try: return jsonify(draft.decide(str(body.get("key") or ""), body.get("answer")))
    except ValueError as e: return {"error": str(e)}, 400
    except LookupError: return {"error": NO_SETUP}, 409

@app.get("/api/draft/grid")
@need("committee")
def draft_grid():
    return _checked(lambda: draft.grid(request.args.get("view"), request.args.get("name")), sentences=True)

@app.get("/api/draft/options")
@need("committee")
def draft_options():
    q = request.args
    if q.get("add") is None and q.get("id") is None: return {"error": "Say which lesson."}, 400
    return _checked(lambda: draft.options(q.get("id"), q.get("group"), q.get("add"), q.get("n")), sentences=True)

def _gz(r):
    """a 200 answer gzip'd when the request accepts it (the board is large and repeats itself)"""
    r.vary.add("Accept-Encoding")
    if r.status_code != 200 or "gzip" not in request.headers.get("Accept-Encoding", "").lower(): return r
    r.set_data(gzip.compress(r.get_data(), 5)); r.headers["Content-Encoding"] = "gzip"; return r

@app.get("/api/draft/board")
@need("committee")
def draft_board():
    r = _checked(draft.board, sentences=True)
    return _gz(r) if isinstance(r, Response) else r

@app.get("/api/draft/slots")
@need("committee")
def draft_slots():
    if request.args.get("id") is None: return {"error": "Say which lesson."}, 400
    return _checked(lambda: draft.slots(request.args.get("id")), sentences=True)

@app.get("/api/draft/place")
@need("committee")
def draft_place():
    """one place a lesson may be dropped on, judged with a push out and a place beside (nothing is changed)"""
    if request.args.get("id") is None: return {"error": "Say which lesson."}, 400
    try: d, p = int(request.args.get("d")), int(request.args.get("p"))
    except (TypeError, ValueError): return {"error": "Say which place."}, 400
    return _checked(lambda: draft.place(request.args.get("id"), d, p), sentences=True)

@app.get("/api/draft/lesson")
@need("committee")
def draft_lesson():
    """who and which room could take one lesson row, for the board's editor (nothing is changed)"""
    if request.args.get("id") is None: return {"error": "Say which lesson."}, 400
    return _checked(lambda: draft.lesson(request.args.get("id"), request.args.get("group") or None), sentences=True)

@app.get("/api/draft/about")
@need("committee")
def draft_about():
    """a read-only look-up about one lesson (kind=lesson&id, optionally group and teacher) or empty period (kind=place&by&name&d&p), q one of ask.QUESTIONS; other: the
    teacher a trade is with. What the page sent is cleaned by ask.subject: a number that is not one stays text and is refused there with its sentence"""
    a = request.args; num = lambda v: int(v) if v and re.fullmatch(r"-?\d{1,9}", v) else v
    raw = dict(kind=a.get("kind"), id=num(a.get("id")), group=a.get("group") or None, teacher=a.get("teacher") or None, by=a.get("by"), name=a.get("name"), d=num(a.get("d")), p=num(a.get("p")))
    return _checked(lambda: draft.about(a.get("q"), raw, a.get("other") or None), sentences=True)

@app.post("/api/draft/fix")
@need("committee")
def draft_fix():
    body = request.get_json(force=True, silent=True); return _checked(lambda: draft.fix(body, stamp=_stamp_of(body)), sentences=True)

@app.post("/api/draft/undo")
@need("committee")
def draft_undo():
    return _checked(draft.undo, sentences=True)

@app.get("/api/draft/suggest")
@need("committee")
def draft_suggest():
    return _checked(lambda: draft.suggest(request.args.get("key") or ""), sentences=True)

def _stamp_of(body):
    """the stamp a request carries (the draft's, as the page last read it), or None when it has none or it is not text"""
    s = body.get("stamp") if isinstance(body, dict) else None; return s if isinstance(s, str) else None

def _posted_fixes():
    body = request.get_json(force=True, silent=True); return body.get("fixes") if isinstance(body, dict) else None

@app.post("/api/draft/fixes")
@need("committee")
def draft_fixes():
    return _checked(lambda: draft.fix_many(_posted_fixes(), stamp=_stamp_of(request.get_json(force=True, silent=True))), sentences=True)

@app.post("/api/draft/preview")
@need("committee")
def draft_preview():
    return _checked(lambda: draft.preview(_posted_fixes()), sentences=True)

NO_TYPED = "Typing a request is not set up on this server."

@app.post("/api/draft/ask")
@need("committee")
def draft_ask():
    """the lead's typed request: the words read into an ask by a language model, then answered from the draft with the helper's own checks. 200 for every outcome
    about the request itself (ok false carries the sentence). Nothing is stored or logged: not the words, the ask or the answer."""
    if not typed.enabled(): return {"error": NO_TYPED}, 404
    body = request.get_json(force=True, silent=True)
    if not isinstance(body, dict): return {"error": "Send the request as JSON."}, 400
    try: return jsonify(draft.ask(body.get("words"), body.get("pick"), body.get("ask")))
    except draft.NoDraft as e: return {"error": str(e)}, 404            # as the other draft routes say it
    except Exception as e:
        if type(e) is LookupError: return {"error": NO_SETUP}, 409
        # typed.read never raises, so a fault here came after the words were read. Logged as the type and the frames only: the message could hold the key or the words.
        app.logger.error("typed request failed after reading: %s\n%s", type(e).__name__, "".join(traceback.format_tb(e.__traceback__)))
        return jsonify(ok=False, error=typed.BROKE)                    # 200, never a 500

@app.get("/api/draft/download")
@need("committee")
def draft_download():
    """the draft with its fixes as a timetable database, to carry on elsewhere"""
    from ttgen.export import safe_name
    work = tempfile.mkdtemp(prefix="tt-")
    try:
        try: m = draft._now()[0]; path = os.path.join(work, "draft.sqlite"); draft.database(path)
        except draft.NoDraft as e: return {"error": str(e)}, 404
        except draft.NotPlaced as e: return {"error": str(e), "unplaced": e.count}, 409
        except LookupError: return {"error": NO_SETUP}, 409
        except Exception as e:
            app.logger.exception("downloading the draft"); return {"error": f"Could not make the file: {e}"}, 400
        with open(path, "rb") as f: data = io.BytesIO(f.read())
        return send_file(data, as_attachment=True, download_name=safe_name(f"{m['school']['name']} {m['school']['timetable']}") + " - draft.sqlite", mimetype="application/vnd.sqlite3")
    finally: shutil.rmtree(work, ignore_errors=True)

@app.post("/api/draft/publish")
@need("committee")
def draft_publish():
    try: return jsonify(draft.publish())
    except FileNotFoundError: return {"error": "There is no draft to publish."}, 404
    except draft.Critical as e: return {"error": str(e), "critical": e.count}, 409
    except draft.NotPlaced as e: return {"error": str(e), "unplaced": e.count}, 409
    except LookupError: return {"error": NO_SETUP}, 409
    except ValueError as e: return {"error": f"Could not read the files: {e}"}, 400

@app.post("/api/draft/printouts")
@need("committee")
def draft_printouts():
    """the printouts (as /api/export makes them) of the draft with its fixes applied: a zip, with the same X-Checks header"""
    work = tempfile.mkdtemp(prefix="tt-")
    try:
        try: m, base = draft.printouts(os.path.join(work, "out"), request.form.get("single", "1") == "1")
        except draft.NoDraft as e: return {"error": str(e)}, 404
        except draft.NotPlaced as e: return {"error": str(e), "unplaced": e.count}, 409
        except ValueError as e: return {"error": f"Could not read the files: {e}"}, 400
        except Exception as e:
            if type(e) is LookupError: return {"error": NO_SETUP}, 409
            app.logger.exception("making the printouts of the draft"); return {"error": f"Could not make the printouts: {e}"}, 400
        return _zip_response(m, os.path.join(work, "out", base), base)
    finally: shutil.rmtree(work, ignore_errors=True)

@app.get("/download/template/<kind>")
@need("committee")
def dl_sample(kind):
    kind_ok(kind)
    return send_file(xlsx_bytes(sample(kind)), as_attachment=True, download_name=f"Sample_{kind.title()}_Timetable_Setup.xlsx", mimetype=XLSX)

@app.get("/download/blank/<kind>")
@need("committee")
def dl_blank(kind):
    kind_ok(kind)
    return send_file(xlsx_bytes(blank(kind)), as_attachment=True, download_name=f"Blank_{kind.title()}_Timetable_Setup.xlsx", mimetype=XLSX)

@app.get("/download/SKILL.md")
@need("committee")
def dl_skill_md():
    return send_file(os.path.join(SKILL_DIR, "SKILL.md"), as_attachment=True, download_name="SKILL.md", mimetype="text/markdown")

@app.get("/download/skill.zip")
@need("committee")
def dl_skill_zip():
    if "zip" not in _cache:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for root, _, files in os.walk(SKILL_DIR):
                for fn in files:
                    if fn.endswith(".pyc"): continue
                    full = os.path.join(root, fn); z.write(full, os.path.join("school-timetable-generator", os.path.relpath(full, SKILL_DIR)))
            for kind in ("secondary", "primary"):
                z.writestr(f"school-timetable-generator/templates/Sample_{kind.title()}_Timetable_Setup.xlsx", xlsx_bytes(sample(kind)).getvalue())
        _cache["zip"] = buf.getvalue()
    return send_file(io.BytesIO(_cache["zip"]), as_attachment=True, download_name="school-timetable-generator.zip", mimetype="application/zip")

# ------------------------------------------------------------------------------------------------ committee: what is published
def pub_info():
    pub = store.published()
    if not pub: return None
    m = pub["meta"]
    return dict(at=m["published_at"], ok=m["ok"], after=len(m.get("after_school", [])), students=m.get("students", 0), classes=m.get("classes", 0),
                files=m.get("files", {}), problems=m.get("problems", []), personal=access.personal_codes_on(), source=m.get("source"), rule_report=m.get("rule_report", []),
                choices_used=m.get("choices_used", []), choice_problems=m.get("choice_problems", []), config_id=m.get("config_id", ""),
                compared_v=m.get("compared_v", ""), open=m.get("open", 0), left=m.get("left", []), fixes=m.get("fixes", []))

@app.get("/api/status")
@need("committee", "head")
def status():
    have, probs = access.configured()
    _, at = store.load_setup()
    if role() == "head": return jsonify(role="head", volume=store.on_volume(), setup_saved_at=at, published=pub_info())
    return jsonify(role="committee", codes=have, code_problems=probs, volume=store.on_volume(), setup_saved_at=at, published=pub_info(), draft=draft.summary(), typed=typed.enabled())

NO_PERSONAL = "Personal student codes are off until SECRET_KEY is set in Railway variables: without it, anyone who knows a Student ID could work out that student's code."

@app.get("/api/codes.csv")
@need("committee")
def codes_csv():
    pub = store.published()
    if not pub: abort(404)
    if not access.personal_codes_on(): return NO_PERSONAL, 409
    return Response(store.codes_csv(pub["model"]), mimetype="text/csv", headers={"Content-Disposition": 'attachment; filename="personal timetable codes.csv"'})

@app.get("/api/code-slips.pdf")
@need("committee")
def code_slips():
    from ttgen.export import code_slips_pdf
    pub = store.published()
    if not pub: abort(404)
    if not access.personal_codes_on(): return NO_PERSONAL, 409
    buf = io.BytesIO()
    code_slips_pdf(pub["model"], {s["id"]: access.personal_code(s["id"]) for s in pub["model"]["students"]}, request.host_url.rstrip("/"), buf)
    buf.seek(0)
    return send_file(buf, as_attachment=True, download_name="timetable code slips.pdf", mimetype="application/pdf")

# ------------------------------------------------------------------------------------------------ everyone: the published timetable
TABS = dict(committee=None, teacher=["classes", "teachers", "rooms", "students", "lessons", "free", "exams"], student=["classes", "students", "exams"])

def files_for(r):
    if r == "committee": return [["Excel (all)", "/files/excel"], ["PDFs (zip)", "/files/zip"]]
    if r == "teacher": return [["Class PDFs", "/files/book/classes"], ["Teacher PDFs", "/files/book/teachers"]]
    return []

@app.get("/timetable")
@need("committee", "head", "teacher", "student", "staff")
def timetable():
    from ttgen.export import render_html
    pub = store.published()
    if not pub:
        return page("Timetable", "<main class='login'><h1>Not published yet</h1><p class='muted'>The timetable committee has not published the timetable yet. Please check again later.</p><p><a href='/logout'>Sign out</a></p></main>")
    r = "teacher" if role() in ("head", "staff") else role()   # a head, and a teacher signed in with their own code, see what a teacher sees
    key = ("view", "staff" if role() == "staff" else r)          # ...but staff have their own copy, with the way back to Relief
    if key not in pub["views"]:
        view = "student" if r == "student" else "full"
        home, label = {"committee": ("/", "Committee page"), "staff": ("/relief", "Relief")}.get(role(), (None, None))
        app_cfg = dict(mode=r, tabs=TABS[r], pdf=True, logout="/logout", files=files_for(r), dates=True, exams=True, published_at=(pub.get("meta") or {}).get("published_at"),
                       placeholder="Search a class" if r == "student" else None, home=home, homeLabel=label)
        pub["views"][key] = render_html(pub["model"], view, app=app_cfg)
    return Response(pub["views"][key], mimetype="text/html")

@app.get("/draft/preview")
@need("committee")
def draft_preview_page():
    """the draft as the published page would show it, before it is published (step 8's and step 9's Preview)"""
    try: return Response(draft.preview_page(), mimetype="text/html")
    except draft.NoDraft:
        return page("Preview", "<main class='login'><h1>Nothing to preview</h1><p class='muted'>There is no draft. Upload the timetable on step 8 first.</p><p><a href='/'>Back to the committee page</a></p></main>"), 404
    except LookupError:
        return page("Preview", "<main class='login'><h1>Nothing to preview</h1><p class='muted'>No setup is saved yet.</p><p><a href='/'>Back to the committee page</a></p></main>"), 409

@app.get("/me")
@need("personal")
def me():
    from ttgen.export import render_html
    pub = store.published(); sid = session.get("sid")
    if not pub or sid not in {s["id"] for s in pub["model"]["students"]}:
        session.clear()
        return page("Timetable", "<main class='login'><h1>Code no longer valid</h1><p class='muted'>Your timetable is not in the published timetable. Ask your form teacher for a new code.</p><p><a href='/login'>Back</a></p></main>")
    return Response(render_html(pub["model"], "personal", student_id=sid, app=dict(mode="personal", tabs=[], pdf=True, logout="/logout", exams=True)), mimetype="text/html")

def _pdf(v, name):
    from ttgen.export import pdf_bytes, safe_name
    return send_file(io.BytesIO(pdf_bytes(store.published()["model"], v)), as_attachment=True, download_name=safe_name(name) + ".pdf", mimetype="application/pdf")

@app.get("/pdf/me")
@need("personal")
def pdf_me():
    from ttgen.export import student_view
    pub = store.published(); sid = session.get("sid")
    s = next((x for x in pub["model"]["students"] if x["id"] == sid), None) if pub else None
    if not s: abort(404)
    return _pdf(student_view(pub["model"], s), f"{s['name']} timetable")

@app.get("/pdf/custom")
@need("committee", "head", "teacher", "student", "staff")
def pdf_custom():
    from ttgen.export import custom_view, group_options
    pub = store.published()
    if not pub: abort(404)
    m = pub["model"]; cls = request.args.get("cls", "")
    if cls not in m["class_ix"]: abort(404)
    allowed = {g for gs in group_options(m, cls).values() for g in gs}
    groups = [g for g in (request.args.get("groups") or "").split(",") if g in allowed]
    return _pdf(custom_view(m, cls, groups), f"Class {cls} my timetable")

@app.get("/pdf/<kind>/<path:key>")
@need("committee", "head", "teacher", "student", "staff")
def pdf_one(kind, key):
    from ttgen.export import class_view, teacher_view, room_view, student_view
    pub = store.published()
    if not pub: abort(404)
    m = pub["model"]; r = role()
    if r == "student" and kind != "classes": abort(403)
    if kind == "classes" and key in m["class_ix"]: return _pdf(class_view(m, key), f"Class {key}")
    if kind == "teachers" and key in m["teacher_ix"]: return _pdf(teacher_view(m, key), key)
    if kind == "rooms" and key in m["room_ix"]: return _pdf(room_view(m, key), f"Room {key}")
    if kind == "students":
        s = next((x for x in m["students"] if x["id"] == key), None)
        if s: return _pdf(student_view(m, s), f"{s['id']} {s['name']}")
    abort(404)

@app.get("/files/<what>")
@app.get("/files/<what>/<kind>")
@need("committee", "head", "teacher", "staff")
def files(what, kind=None):
    pub = store.published()
    if not pub: abort(404)
    f = pub["meta"].get("files", {}); r = "teacher" if role() in ("head", "staff") else role()
    if what == "book":
        allowed = {"committee": ("classes", "teachers", "rooms", "students"), "teacher": ("classes", "teachers", "rooms")}[r]
        if kind not in allowed or kind not in f.get("books", {}): abort(404)
        return send_file(os.path.join(store.PUB, f["books"][kind]), as_attachment=True, download_name=os.path.basename(f["books"][kind]))
    if r != "committee": abort(403)
    if what in ("excel", "zip", "html", "db") and f.get(what):
        return send_file(os.path.join(store.PUB, f[what]), as_attachment=True, download_name=f[what])
    abort(404)

# ------------------------------------------------------------------------------------------------ staff: relief
NO_RELIEF_PUB = relief_web.NO_PUB          # "Publish the timetable first: relief reads the teachers from it."
ONLY_SETTINGS = "Only the timetable committee and the relief team can change relief settings."
ONLY_CODES = "Only the timetable committee can download the codes."

def relief_staff(pub):
    """the people relief knows: the published timetable's teachers and the staff added in the relief settings"""
    return relief_people.people(pub, relief_settings.load(pub)["extra_staff"])

def me_staff(pub=None):
    """the person signed in with their own code (their entry in relief_staff), or None; a staff session whose person
    is no longer on the published timetable or the staff list is ended"""
    if role() != "staff": return None
    pub = pub or store.published(); who = session.get("who")
    if not pub: return None   # nothing published (a publish may be swapping folders): no one to find, but the session stays
    p = next((x for x in relief_staff(pub) if x["name"] == who), None) if who else None
    if p is None: session.clear()
    return p

def _relief_rights(pub):
    """(may read the settings, may save them, saved by) for whoever is signed in; None when a staff session has ended"""
    if role() == "committee": return True, True, "Timetable committee"
    p = me_staff(pub)
    if p is None: return None
    s = relief_settings.load(pub); team = p["name"] in s["team"]
    return team or p["name"] in s["management"], team, p["name"]

def relief_has(right):
    """the one place relief asks what the person signed in may do (the accounts work's `has` takes over here, same names):
    relief = signed in with their own code; relief.plan = on the Management list or the Relief team; relief.team = on the
    Relief team; relief.settings / relief.save = may read / save the relief settings (the timetable committee too).
    Any other name is refused."""
    pub = store.published()
    if right in ("relief.settings", "relief.save"):
        rights = _relief_rights(pub)
        return bool(rights and rights[0 if right == "relief.settings" else 1])
    if right not in ("relief", "relief.plan", "relief.team"): return False
    p = me_staff(pub)
    if p is None: return False
    if right == "relief": return True
    s = relief_settings.load(pub)
    return p["name"] in s["team"] or (right == "relief.plan" and p["name"] in s["management"])

def _no_longer_valid():
    return page("Relief", "<main class='login'><h1>Code no longer valid</h1><p class='muted'>You are not on the published timetable or the relief staff list. Ask the timetable committee for your code.</p><p><a href='/login'>Back</a></p></main>")

@app.get("/relief")
@need("staff", "committee")
def relief_home():
    if role() == "committee": return redirect("/relief/settings")
    return app.send_static_file("relief.html")   # need() has checked the person is still there

@app.get("/api/relief/me")
@need("staff")
def relief_me():
    pub = store.published(); p = me_staff(pub)
    if p is None: return {"error": "Please sign in again."}, 401
    s = relief_settings.load(pub); team = p["name"] in s["team"]
    return jsonify(name=p["name"], depts=p["depts"], on_team=team, on_management=p["name"] in s["management"], can_settings=team,
                   can_plan=relief_has("relief.plan"), can_team=relief_has("relief.team"), today=relief_lessons.today().isoformat())

@app.get("/relief/settings")
def relief_settings_page():
    if not role(): return redirect("/login")
    if role() == "staff" and me_staff() is None: return _no_longer_valid()
    if role() == "committee" or (role() == "staff" and (_relief_rights(store.published()) or (0, 0))[1]):
        return app.send_static_file("relief-settings.html")
    return page("Relief settings", f"<main class='login'><h1>Relief settings</h1><p class='muted'>{esc(ONLY_SETTINGS)}</p><p><a href='/'>Back</a></p></main>"), 403

def _relief_settings_reply(pub, settings):
    m = pub["model"]; rights = _relief_rights(pub) or (False, False, None)
    return jsonify(settings=settings, people=relief_staff(pub), roles=relief_settings.role_names(pub), weeks=m["school"]["weeks"], can_save=rights[1], can_codes=role() == "committee")

@app.get("/api/relief/settings")
@need("committee", "staff")
def relief_settings_get():
    pub = store.published()
    if not pub: return {"error": NO_RELIEF_PUB}, 409
    rights = _relief_rights(pub)
    if rights is None: return {"error": "Please sign in again."}, 401
    if not rights[0]: return {"error": ONLY_SETTINGS}, 403
    return _relief_settings_reply(pub, relief_settings.load(pub))

@app.put("/api/relief/settings")
@need("committee", "staff")
def relief_settings_put():
    pub = store.published()
    if not pub: return {"error": NO_RELIEF_PUB}, 409
    rights = _relief_rights(pub)
    if rights is None: return {"error": "Please sign in again."}, 401
    if not rights[1]: return {"error": ONLY_SETTINGS}, 403
    try: saved = relief_settings.save(request.get_json(force=True, silent=True), pub, rights[2])
    except ValueError as e: return {"error": str(e)}, 400
    return _relief_settings_reply(pub, saved)

def _relief_codes_refused():
    """the answer that refuses the staff codes to whoever is signed in, or None (the routes check what is published)"""
    if role() != "committee": return {"error": ONLY_CODES}, 403
    if not access.personal_codes_on(): return NO_PERSONAL_STAFF, 409
    return None

@app.get("/api/relief/codes.csv")
@need("committee", "staff")
def relief_codes_csv():
    refused = _relief_codes_refused(); pub = store.published()
    if refused: return refused
    if not pub: return NO_RELIEF_PUB, 409
    return Response(relief_codes.codes_csv(relief_staff(pub)), mimetype="text/csv", headers={"Content-Disposition": 'attachment; filename="personal relief codes.csv"'})

@app.get("/api/relief/code-slips.pdf")
@need("committee", "staff")
def relief_code_slips():
    refused = _relief_codes_refused(); pub = store.published()
    if refused: return refused
    if not pub: return NO_RELIEF_PUB, 409
    buf = io.BytesIO()
    relief_codes.slips_pdf(pub["model"]["school"]["name"], relief_staff(pub), request.host_url.rstrip("/"), buf)
    buf.seek(0)
    return send_file(buf, as_attachment=True, download_name="relief code slips.pdf", mimetype="application/pdf")

relief_web.init(has=relief_has, me=me_staff, role=role)     # relief requests: relief/web.py, every right through relief_has
app.register_blueprint(relief_web.bp)

# ------------------------------------------------------------------------------------------------ staff: exams and events
NO_EXAMS_PUB = "Publish the timetable first: exams read the classes, students and lessons from it."
ONLY_EXAMS = "Only the exams committee and the timetable committee can open exams."
NO_STUDENTS = "The published timetable has no students. Add them on the Students step and publish again to seat them."
NO_EXAM = "That exam is not there any more."
NO_EVENT = "That event is not there any more."
ONLY_IN_CHARGE = "Only the teacher in charge and the timetable committee can open this event."
PICK_IN_CHARGE = "Pick the teacher in charge."
EVENT_KEEPS = ("id", "kind", "in_charge", "created_at", "created_by", "status", "approved", "approved_at", "approved_by", "sent_at",
               "sent_by", "sent_fp", "note", "log", "handled")
ONLY_APPROVE = "Only the timetable committee can approve, send back or withdraw."
ON_SITE = "This schedule is on the main site: the timetable committee must withdraw it before it can be deleted."
EXAM_KEEPS = ("id", "created_at", "created_by", "made", "pins", "use_anyway", "status", "approved", "approved_at", "approved_by",
              "sent_at", "sent_by", "sent_fp", "note", "log", "handled")    # handled: Handled ourselves, changed by its own route
BAD_INPUT = (TypeError, KeyError, AttributeError)
NO_BACKUP = "That lesson no longer needs a backup."

def _exams_rights(pub):
    """(may use exams, saved by) for whoever is signed in; None when a staff session has ended"""
    if role() == "committee": return True, "Timetable committee"
    p = me_staff(pub)
    if p is None: return None
    return p["name"] in exams_settings.load(pub)["committee"], p["name"]

def _exams_can_approve():
    """the timetable committee approves, sends back and withdraws"""
    return role() == "committee"

def _exams_can_keep_list():
    """the timetable committee keeps the exams committee list in Exam settings (an exams committee member cannot change it)"""
    return role() == "committee"

def _event_rights(sched):
    """(may open this event, saved by, may see every event) for whoever is signed in; None when a staff session has ended.
    The committee may open any event; a teacher only the one they are in charge of (sched None: any, to start one)"""
    if role() == "committee": return True, "Timetable committee", True
    p = me_staff()
    if p is None: return None
    return (sched is None or sched.get("in_charge") == p["name"]), p["name"], False

def _exams_today(): return datetime.date.today()

def _published_reader():
    """who may read the published exams data, and how much: "full" (teacher names, duty rooms, roster, prints) for the
    committee, a head, a teacher and staff; "student" (classes, rooms and times only) for the shared student code"""
    r = role()
    if r in ("committee", "head", "teacher", "staff"): return "full"
    if r == "student": return "student"
    return None

def _exams_student():
    """the student a personal code is signed in as, whose own exam timetable /api/me/exams shows; None for anyone else"""
    return session.get("sid") if role() == "personal" else None

BAD_DATE = "Give a date such as 2026-10-05."
REPUBLISHED = "The timetable was published again: reload the page."
NO_DAY_CAL = "The school calendar is not set yet, so the timetable cannot be shown on a date."
ONLY_STAFF_PRINTS = "Only staff can open the seating plans and rosters."

def _exams_gate():
    """-> (pub, who, None) when the person may use exams, else (None, None, the refusing answer)"""
    pub = store.published()
    if not pub: return None, None, ({"error": NO_EXAMS_PUB}, 409)
    rights = _exams_rights(pub)
    if rights is None: return None, None, ({"error": "Please sign in again."}, 401)
    if not rights[0]: return None, None, ({"error": ONLY_EXAMS}, 403)
    return pub, rights[1], None

def _event_gate(id=None):
    """-> (pub, who, the event, sees every event, None) when the person may open the event (or, with no id, events), else
    (None, None, None, None, the refusing answer)"""
    no = lambda ans: (None, None, None, None, ans)
    pub = store.published()
    if not pub: return no(({"error": NO_EXAMS_PUB}, 409))
    sched = None
    if id is not None:
        sched = exams_schedules.load(id)
        if not sched or sched.get("kind") != "event": return no(({"error": NO_EVENT}, 404))
    rights = _event_rights(sched)
    if rights is None: return no(({"error": "Please sign in again."}, 401))
    if not rights[0]: return no(({"error": ONLY_IN_CHARGE}, 403))
    return pub, rights[1], sched, rights[2], None

def _exam_cal(pub): return relief_settings.load(pub)["calendar"]

def _exam_json():
    d = request.get_json(force=True, silent=True)
    return d if isinstance(d, dict) else {}

def _save_exam(sched, pub, by, check=True, event=False):
    """save a schedule; (the saved schedule, None) or (None, the 400 answer): malformed JSON never gives a 500"""
    try: return exams_schedules.save(sched, pub, _exam_cal(pub), by, check=check), None
    except ValueError as e: return None, ({"error": str(e)}, 400)
    except BAD_INPUT: return None, ({"error": exams_schedules.EVENT_WRONG if event else exams_schedules.WRONG}, 400)

def _marked(lists, sched, pub, cal):
    """the lessons lists with each backup's state in relief, its relief teacher and why it stops (exams.relief_links.mark,
    with the other schedules' approved copies)"""
    links = exams_relief_links.Links(pub, cal, [x for x in exams_schedules.on_site() if x.get("id") != sched.get("id")])
    exams_relief_links.mark(lists["backup"], sched, relief_absences.all_records(), links, _exams_today())
    return lists

def _backups_left(rv, lists, s, pub):
    """the review's backup count (what.backups; lists: a function giving the lessons lists) read again as the backup items of the reviewed copy that still go to the relief
    team: not handled, stopped, past or elsewhere"""
    if rv and isinstance(rv.get("what"), dict):
        try:
            items = _marked(lists(), s, pub, _exam_cal(pub))["backup"]
            rv["what"]["backups"] = sum(1 for x in items if x.get("state") in ("later", "sent", "relief"))
        except Exception:     # the state is saved already: keep the unmarked count
            app.logger.exception("exams: backup count failed")
    return rv

def _relief_sync(pub, s):
    """relief's backups in step (exams.relief_links.sync) after every approval action and Handled ourselves change that saved:
    the schedule acted on first, then every other one a sync may change (to_sync), so a lesson one schedule gives up or stops
    goes to (or leaves) another at once. Each sync is idempotent; one failing never stops the others and never fails the
    action: each error is logged and the next action syncs again"""
    say = lambda: app.logger.exception("exams: relief sync failed")
    try: cal, today, copies = _exam_cal(pub), _exams_today(), exams_schedules.on_site()
    except Exception: return say()
    try: exams_relief_links.sync(s, pub, cal, today, copies=copies)
    except Exception: say()
    try: others = exams_relief_links.to_sync(s.get("id"), exams_schedules.all_saved(), relief_absences.all_records(), today)
    except Exception: return say()
    for o in others:
        try: exams_relief_links.sync(o, pub, cal, today, copies=copies)
        except Exception: say()

def _exam_view(pub, sched):
    model, cal = pub["model"], _exam_cal(pub)
    by_id = {x["id"]: x for x in model.get("students") or []}
    papers = sched.get("papers") or []
    levels, classes = set(sched.get("levels") or []), set(sched.get("classes") or [])
    mine = {x["id"] for x in model.get("students") or [] if exams_papers._student_level(model, x) in levels or x.get("cls") in classes}
    sids = sorted(mine | {i for p in papers for i in exams_papers.who_sits(p, model)})
    return dict(summary=exams_make.summary(pub, cal, sched, exams_settings.load(pub)), lessons=_marked(exams_make.lesson_lists(pub, cal, sched), sched, pub, cal),
                made=sched.get("made"), students={i: [by_id[i]["name"], by_id[i]["cls"]] for i in sids if i in by_id},
                counts={p.get("id"): len(exams_papers.who_sits(p, model)) for p in papers}, periods=[[exams_days.hhmm(a), exams_days.hhmm(b)] for a, b in exams_days.bounds(model)],
                rooms=exams_settings.load(pub)["rooms"], students_missing=not model.get("students"), levels=list(model.get("levels") or []),
                rooms_by_key=_exam_rooms_by_key(pub, cal, sched), stale=exams_make.stale(sched, exams_settings.load(pub), model))

def _exam_rooms_by_key(pub, cal, sched):
    """for each sitting, every exam room with its seats and what keeps it busy then (empty text: free); a room another
    overlapping sitting of the made schedule holds is busy, so the move selects do not offer it"""
    xset = exams_settings.load(pub)
    held = exams_make.held(pub, sched, xset)
    return {x["key"]: [[r["name"], r["seats"], r["busy"]] for r in exams_seating.rooms_free(pub, cal, sched, x, xset, held.get(x["key"], set()), elsewhere=exams_schedules.elsewhere(sched.get("id"), pub["model"]))]
            for x in exams_seating.sittings(sched)}

@app.get("/exams")
@need("committee", "staff")
def exams_home(): return app.send_static_file("exams.html")

@app.get("/exams/settings")
@need("committee", "staff")
def exams_settings_page(): return app.send_static_file("exams-settings.html")

@app.get("/exams/<id>")
@need("committee", "staff")
def exams_one_page(id): return app.send_static_file("exams.html")

@app.get("/api/exams/me")
@need("committee", "staff")
def exams_me():
    pub = store.published()
    if not pub: return {"error": NO_EXAMS_PUB}, 409
    rights = _exams_rights(pub)
    if rights is None: return {"error": "Please sign in again."}, 401
    return jsonify(name=rights[1], can_use=rights[0], can_approve=_exams_can_approve())

def _exam_settings_reply(pub, settings):
    """committee_ok: only the timetable committee changes the exams committee list"""
    m = pub["model"]
    return jsonify(settings=settings, people=relief_staff(pub), rooms=[[r["name"], r.get("kind"), r.get("capacity")] for r in m.get("rooms") or []],
                   committee_ok=_exams_can_keep_list())

@app.get("/api/exams/settings")
@need("committee", "staff")
def exams_settings_get():
    pub, who, err = _exams_gate()
    if err: return err
    return _exam_settings_reply(pub, exams_settings.load(pub))

@app.put("/api/exams/settings")
@need("committee", "staff")
def exams_settings_put():
    pub, who, err = _exams_gate()
    if err: return err
    body = request.get_json(force=True, silent=True)
    if not _exams_can_keep_list() and isinstance(body, dict): body = dict(body, committee=exams_settings.load(pub)["committee"])   # kept as it is
    try: saved = exams_settings.save(body, pub, who)
    except ValueError as e: return {"error": str(e)}, 400
    except BAD_INPUT: return {"error": exams_settings.WRONG}, 400
    return _exam_settings_reply(pub, saved)

@app.get("/api/exams")
@need("committee", "staff")
def exams_list():
    pub, who, err = _exams_gate()
    if err: return err
    m = pub["model"]
    return jsonify(schedules=_with_away(exams_schedules.listing(_exams_today(), exams_make.published_at(pub), kinds=("exam", "test")), pub), levels=m.get("levels") or [], classes=[[c["name"], c["level"]] for c in m.get("classes") or []],
                   calendar_ok=bool(_exam_cal(pub).get("terms")))

@app.post("/api/exams")
@need("committee", "staff")
def exams_create():
    pub, who, err = _exams_gate()
    if err: return err
    if not _exam_cal(pub).get("terms"): return {"error": exams_schedules.NO_CALENDAR}, 409
    b = _exam_json()
    try:
        if b.get("kind") not in ("exam", "test"): raise ValueError(exams_schedules.WRONG)
        sched = exams_schedules.new(b["kind"], b.get("name"), b.get("levels"), b.get("start"), b.get("end"), who, pub=pub)
    except ValueError as e: return {"error": str(e)}, 400
    except BAD_INPUT: return {"error": exams_schedules.WRONG}, 400
    saved, bad = _save_exam(sched, pub, who)
    return bad or jsonify(saved)

def _exam_or_404(id):
    s = exams_schedules.load(id)
    return (s, None) if s and s.get("kind") != "event" else (None, ({"error": NO_EXAM}, 404))   # an event has its own routes

@app.get("/api/exams/<id>")
@need("committee", "staff")
def exams_get(id):
    pub, who, err = _exams_gate()
    if err: return err
    s, err = _exam_or_404(id)
    return err or jsonify(s)

@app.put("/api/exams/<id>")
@need("committee", "staff")
def exams_put(id):
    pub, who, err = _exams_gate()
    if err: return err
    with exams_schedules.editing():   # from loading to saving: what is kept is what is stored now
        old, err = _exam_or_404(id)
        if err: return err
        new = dict(_exam_json(), **{k: old.get(k) for k in EXAM_KEEPS})
        new["log"] = old.get("log") or []
        if new.get("kind") not in exams_schedules.KINDS: return {"error": exams_schedules.WRONG}, 400   # an exam never becomes an event
        saved, bad = _save_exam(new, pub, who)
    return bad or jsonify(saved)

@app.delete("/api/exams/<id>")
@need("committee", "staff")
def exams_delete(id):
    pub, who, err = _exams_gate()
    if err: return err
    with exams_schedules.editing():   # an approve cannot land between the check and the delete
        s, err = _exam_or_404(id)
        if err: return err
        if s.get("approved"): return {"error": ON_SITE}, 409
        exams_schedules.delete(id)
    return {"ok": True}

@app.post("/api/exams/<id>/fill")
@need("committee", "staff")
def exams_fill(id):
    pub, who, err = _exams_gate()
    if err: return err
    with exams_schedules.editing():
        s, err = _exam_or_404(id)
        if err: return err
        s["papers"] = list(s.get("papers") or []) + exams_papers.fill_from_subjects(s, pub["model"])
        saved, bad = _save_exam(s, pub, who)
    return bad or jsonify(saved)

@app.get("/api/exams/<id>/papers.xlsx")
@need("committee", "staff")
def exams_papers_download(id):
    pub, who, err = _exams_gate()
    if err: return err
    s, err = _exam_or_404(id)
    if err: return err
    from ttgen.export import safe_name
    return send_file(io.BytesIO(exams_papers.paper_list_xlsx(s)), as_attachment=True, download_name=safe_name(f"{s.get('name')} papers") + ".xlsx", mimetype=XLSX)

@app.post("/api/exams/<id>/papers.xlsx")
@need("committee", "staff")
def exams_papers_upload(id):
    pub, who, err = _exams_gate()
    if err: return err
    f = request.files.get("file")
    if not f: return {"error": "Choose the paper list to upload."}, 400
    try: rows = exams_papers.read_paper_list(f.read())
    except ValueError as e: return {"error": str(e)}, 400
    with exams_schedules.editing():
        s, err = _exam_or_404(id)
        if err: return err
        s["papers"] = [p for p in s.get("papers") or [] if p.get("who") == "students"] + rows
        saved, bad = _save_exam(s, pub, who)
    return bad or jsonify(saved)

def _exam_view_reply(pub, sched):
    """the view as JSON; a schedule the code cannot read answers 400 with a sentence, never 500"""
    try: return jsonify(_exam_view(pub, sched))
    except ValueError as e: return {"error": str(e)}, 400
    except BAD_INPUT + (IndexError,): return {"error": exams_schedules.WRONG}, 400

@app.get("/api/exams/<id>/view")
@need("committee", "staff")
def exams_view(id):
    pub, who, err = _exams_gate()
    if err: return err
    s, err = _exam_or_404(id)
    return err or _exam_view_reply(pub, s)

def _exam_changed(id, change):
    """run change(pub, sched, body) on the stored schedule, save it and answer as the view does. The schedule is locked from
    loading to saving (a Make takes a while), so an approve or an edit meanwhile waits and is not undone by it"""
    pub, who, err = _exams_gate()
    if err: return err
    with exams_schedules.editing():
        s, err = _exam_or_404(id)
        if err: return err
        try: err = change(pub, s, _exam_json())
        except ValueError as e: return {"error": str(e)}, 400
        except BAD_INPUT: return {"error": exams_schedules.WRONG}, 400
        if err: return err
        saved, bad = _save_exam(s, pub, who)
    return bad or _exam_view_reply(pub, saved)

def _exam_make(pub, s, b):
    model, cal = pub["model"], _exam_cal(pub)
    if not model.get("students"): return {"error": NO_STUDENTS}, 409
    errors = exams_papers.check(s, model, cal, exams_settings.load(pub)["rules"])["errors"]
    if errors: return {"error": f"Fix the paper times first: {errors[0]}"}, 400
    only = b.get("only")
    if only is not None and not isinstance(only, str): raise ValueError(exams_schedules.WRONG)
    exams_make.make(pub, cal, s, exams_settings.load(pub), only=only)

def _exam_sitting(s, key):
    if key not in {x["key"] for x in exams_seating.sittings(s)}: raise ValueError("That sitting is not in this exam.")

def _exam_remake(pub, s, key):
    """a made schedule is made again for that sitting alone, so the answer shows the change"""
    if s.get("made"): exams_make.make(pub, _exam_cal(pub), s, exams_settings.load(pub), only=key)

def _exam_move(pub, s, b):
    if not isinstance(b["students"], list) or not all(isinstance(x, str) for x in b["students"]): raise ValueError(exams_schedules.WRONG)
    if not isinstance(b["key"], str) or not isinstance(b["room"], str): raise ValueError(exams_schedules.WRONG)
    _exam_sitting(s, b["key"])
    exams_make.move(s, b["key"], b["students"], b["room"])
    _exam_remake(pub, s, b["key"])

def _exam_invigilators(pub, s, b):
    """names: the names chosen by hand, or null to let the app choose again"""
    if b["names"] is not None and (not isinstance(b["names"], list) or not all(isinstance(x, str) for x in b["names"])): raise ValueError(exams_schedules.WRONG)
    if not isinstance(b["key"], str) or not isinstance(b["room"], str): raise ValueError(exams_schedules.WRONG)
    _exam_sitting(s, b["key"])
    exams_make.set_invigilators(s, b["key"], b["room"], b["names"])
    _exam_remake(pub, s, b["key"])

def _exam_use_anyway(pub, s, b):
    if not isinstance(b["key"], str) or not isinstance(b["room"], str): raise ValueError(exams_schedules.WRONG)
    _exam_sitting(s, b["key"])
    pair = [b["key"], b["room"]]
    if pair not in s.setdefault("use_anyway", []): s["use_anyway"].append(pair)
    _exam_remake(pub, s, b["key"])

@app.post("/api/exams/<id>/make")
@need("committee", "staff")
def exams_make_route(id): return _exam_changed(id, _exam_make)

@app.post("/api/exams/<id>/move")
@need("committee", "staff")
def exams_move(id): return _exam_changed(id, _exam_move)

@app.post("/api/exams/<id>/invigilators")
@need("committee", "staff")
def exams_invigilators(id): return _exam_changed(id, _exam_invigilators)

@app.post("/api/exams/<id>/use-anyway")
@need("committee", "staff")
def exams_use_anyway(id): return _exam_changed(id, _exam_use_anyway)

@app.get("/api/exams/<id>/print/<what>.pdf")
@need("committee", "staff")
def exams_print(id, what):
    pub, who, err = _exams_gate()
    if err: return err
    s, err = _exam_or_404(id)
    if err: return err
    if what not in exams_printouts.WHATS: abort(404)
    if not s.get("made"): return {"error": "Press Make first."}, 409
    if exams_make.stale(s, exams_settings.load(pub), pub["model"]): return {"error": exams_make.STALE}, 409
    from ttgen.export import safe_name
    buf = io.BytesIO()
    exams_printouts.pdf(what, pub, _exam_cal(pub), s, exams_settings.load(pub), buf)
    buf.seek(0)
    return send_file(buf, as_attachment=False, download_name=safe_name(f"{s.get('name')} {exams_printouts.TITLES[what]}") + ".pdf", mimetype="application/pdf")

@app.get("/api/day")
@need("committee", "head", "teacher", "student", "staff")
def exams_day():
    pub = store.published()
    if not pub: return {"error": NO_EXAMS_PUB}, 409
    stamp = exams_make.published_at(pub)
    seen = request.args.get("published_at")   # the publish the asking page was drawn from: another one would draw wrong cells
    if seen is not None and seen != (stamp or ""): return {"error": REPUBLISHED, "published_at": stamp}, 409
    raw = request.args.get("date") or ""
    try:
        if datetime.date.fromisoformat(raw).isoformat() != raw: raise ValueError(raw)   # only YYYY-MM-DD: no week or short forms
    except ValueError: return {"error": BAD_DATE}, 400
    cal = _exam_cal(pub)
    if not cal.get("terms"): return {"error": NO_DAY_CAL}, 409
    return jsonify(dict(exams_published.day(pub, cal, exams_schedules.on_site(), raw, _published_reader() == "full"), published_at=stamp))

@app.get("/api/published/exams")
@need("committee", "head", "teacher", "student", "staff")
def exams_published_list():
    pub = store.published()
    if not pub: return {"error": NO_EXAMS_PUB}, 409
    return jsonify(exams_published.listing(pub, exams_schedules.on_site(), _exams_today(), _published_reader() == "full", cal=_exam_cal(pub)))

@app.get("/api/published/exams/<id>/print/<what>.pdf")
@need("committee", "head", "teacher", "student", "staff")
def exams_published_print(id, what):
    pub = store.published()
    if not pub: return {"error": NO_EXAMS_PUB}, 409
    if _published_reader() != "full": return {"error": ONLY_STAFF_PRINTS}, 403
    if what not in exams_published.PRINTS: abort(404)
    site = next((x for x in exams_schedules.on_site() if x["id"] == id), None)
    if site is None or site.get("kind") == "event": abort(404)
    from ttgen.export import safe_name
    buf = io.BytesIO()
    exams_printouts.pdf(what, pub, _exam_cal(pub), site, exams_settings.load(pub), buf)
    buf.seek(0)
    return send_file(buf, as_attachment=False, download_name=safe_name(f"{site.get('name')} {exams_printouts.TITLES[what]}") + ".pdf", mimetype="application/pdf")

@app.get("/api/exams/my-duties")
@need("committee", "staff")
def exams_my_duties():
    pub = store.published()
    if not pub: return {"error": NO_EXAMS_PUB}, 409
    rights = _exams_rights(pub)
    if rights is None: return {"error": "Please sign in again."}, 401
    return jsonify(exams_published.my_duties(pub, _exam_cal(pub), exams_schedules.on_site(), rights[1], _exams_today()))

@app.get("/api/me/exams")
@need("personal")
def exams_my_exams():
    pub = store.published(); sid = _exams_student()
    if not pub or sid not in {x["id"] for x in pub["model"].get("students") or []}: return {"error": "Please sign in again."}, 401
    return jsonify(exams_published.my_exams(pub, _exam_cal(pub), exams_schedules.on_site(), sid, _exams_today()))

@app.get("/api/exams/<id>/download.xlsx")
@need("committee", "staff")
def exams_download(id):
    pub, who, err = _exams_gate()
    if err: return err
    s, err = _exam_or_404(id)
    if err: return err
    if not s.get("made"): return {"error": "Press Make first."}, 409
    if exams_make.stale(s, exams_settings.load(pub), pub["model"]): return {"error": exams_make.STALE}, 409
    from ttgen.export import safe_name
    return send_file(io.BytesIO(exams_printouts.xlsx(pub, _exam_cal(pub), s, exams_settings.load(pub))), as_attachment=True,
                     download_name=safe_name(s.get("name")) + ".xlsx", mimetype=XLSX)

def _exam_candidates(pub, s, key, room, approved=False):
    """(the duty, who may stand in for it) for the duty of one sitting room, read from the copy s; (None, None) if it is not there"""
    duties = (s.get("made") or {}).get("duties") or []
    d = next((x for x in duties if x["key"] == key and x["room"] == room), None)
    if d is None: return None, None
    sit = next((x for x in exams_seating.sittings(s) if x["key"] == key), None)
    papers = {p["id"]: p for p in s.get("papers") or []}
    subjects = [papers[i]["subject"] for i in (sit or {}).get("papers", []) if i in papers]
    rest = [x for x in duties if x is not d]
    return d, exams_invigilate.candidates(pub, _exam_cal(pub), s, exams_settings.load(pub), d["date"], d["start"], d["end"], rest, subjects=subjects,
                                          exclude=d["names"] if approved else (), elsewhere=exams_schedules.elsewhere(s.get("id"), pub["model"]))

@app.get("/api/exams/<id>/who")
@need("committee", "staff")
def exams_who(id):
    pub, who, err = _exams_gate()
    if err: return err
    s, err = _exam_or_404(id)
    if err: return err
    approved = request.args.get("copy") == "approved"
    if approved:
        s = exams_approval.as_schedule(s)
        if s is None: return {"error": exams_approval.NOT_ON_SITE}, 400
    d, got = _exam_candidates(pub, s, request.args.get("key", ""), request.args.get("room", ""), approved=approved)
    if d is None: return {"error": "That duty is not on the main site." if approved else "Press Make first."}, 404
    return jsonify(got)

# ------------------------------------------------------------------------------------------------ staff: exams, approval
def _away_texts(pub, s):
    """the texts that say who on an approved schedule is away in relief (from today); [] for any other schedule"""
    try:
        return [x["text"] for x in exams_relief_links.away_on(s, pub["model"], relief_absences.all_records(), _exams_today())]
    except (ValueError, KeyError, TypeError):
        return []

def _with_away(rows, pub):
    saved = {s["id"]: s for s in exams_schedules._all()}
    for r in rows:
        r["away"] = _away_texts(pub, saved[r["id"]]) if r["id"] in saved and r.get("status") in ("approved", "changes") else []
    return rows

def _exam_review_reply(pub, s):
    """the Approval tab: state, who sent and approved, what is waiting and the review a committee reads"""
    model, xset = pub["model"], exams_settings.load(pub)
    stale = exams_make.stale(s, xset, model)
    errors = exams_papers.check(s, model, _exam_cal(pub), xset["rules"])["errors"]
    st = s.get("status") or "draft"
    rv = exams_review.review(pub, _exam_cal(pub), s, xset, exams_schedules.elsewhere(s.get("id"), pub["model"])) if s.get("made") else None
    if rv: _backups_left(rv, lambda: exams_make.lesson_lists(pub, _exam_cal(pub), exams_approval.as_schedule(s) if rv.get("copy") == "approved" else s), s, pub)
    return jsonify(status=st, label=exams_approval.label(s, _exams_today()), note=s.get("note") or "", sent_at=s.get("sent_at"), sent_by=s.get("sent_by"),
                   approved_at=s.get("approved_at"), approved_by=s.get("approved_by"),
                   changed=s.get("sent_fp") is not None and s.get("sent_fp") != exams_approval.fp(s),
                   can_send=exams_approval.blocked(s, model, stale, errors), can_approve=_exams_can_approve(),
                   unsent=exams_approval.changes(s, model) if st == "approved" else [], review=rv, away=_away_texts(pub, s))

def _exam_approval(id, act, approver=False, check=False, event=False):
    """run act(pub, sched, who, now, body) on the stored schedule, save and answer with the review; locked from loading to
    saving, as _exam_changed is. Only Send checks the schedule against the timetable (check=True): approve, send back,
    withdraw and someone is away still work after a new publish. event=True: the same for an event (its rights and reply)"""
    with exams_schedules.editing():
        if event: pub, who, s, _, err = _event_gate(id)
        else: (pub, who, err), s = _exams_gate(), None
        if err: return err
        if approver and not _exams_can_approve(): return {"error": ONLY_APPROVE}, 403
        if not event:
            s, err = _exam_or_404(id)
            if err: return err
        try: act(pub, s, who, exams_schedules._now(), _exam_json())
        except ValueError as e: return {"error": str(e)}, 400
        except BAD_INPUT: return {"error": exams_schedules.EVENT_WRONG if event else exams_schedules.WRONG}, 400
        saved, bad = _save_exam(s, pub, who, check=check, event=event)
        if not bad: _relief_sync(pub, saved)     # inside the lock: two syncs of one schedule never run at once
    return bad or (_event_review_reply if event else _exam_review_reply)(pub, saved)

@app.get("/api/exams/<id>/review")
@need("committee", "staff")
def exams_review_get(id):
    pub, who, err = _exams_gate()
    if err: return err
    s, err = _exam_or_404(id)
    if err: return err
    if not s.get("made"): return {"error": "Press Make first."}, 409
    return _exam_review_reply(pub, s)

def _exam_send(pub, s, by, now, b):
    xset, model = exams_settings.load(pub), pub["model"]
    exams_approval.send(s, model, by, now, exams_make.stale(s, xset, model), exams_papers.check(s, model, _exam_cal(pub), xset["rules"])["errors"])

@app.post("/api/exams/<id>/send")
@need("committee", "staff")
def exams_send(id): return _exam_approval(id, _exam_send, check=True)

def _act_approve(pub, s, by, now, b): exams_approval.approve(s, by, now)
def _act_send_back(pub, s, by, now, b): exams_approval.send_back(s, b.get("note"), by, now)
def _act_withdraw(pub, s, by, now, b): exams_approval.withdraw(s, by, now)

@app.post("/api/exams/<id>/approve")
@need("committee", "staff")
def exams_approve(id): return _exam_approval(id, _act_approve, approver=True)

@app.post("/api/exams/<id>/send-back")
@need("committee", "staff")
def exams_send_back(id): return _exam_approval(id, _act_send_back, approver=True)

@app.post("/api/exams/<id>/withdraw")
@need("committee", "staff")
def exams_withdraw(id): return _exam_approval(id, _act_withdraw, approver=True)

def _exam_away(pub, s, by, now, b):
    key, room, away, name = b["key"], b["room"], b["away"], b["name"]
    if not all(isinstance(x, str) for x in (key, room, away, name)): raise ValueError(exams_schedules.WRONG)
    ap = exams_approval.as_schedule(s)
    if ap is None: raise ValueError(exams_approval.NOT_ON_SITE)
    d, got = _exam_candidates(pub, ap, key, room, approved=True)
    if d is None: raise ValueError("That duty is not on the main site.")
    if name not in {c["name"] for g in ("freed", "free", "backups") for c in got[g]}: raise ValueError("%s is not free then." % name)
    exams_approval.replace(s, key, room, away, name, by, now)

@app.post("/api/exams/<id>/away")
@need("committee", "staff")
def exams_away(id): return _exam_approval(id, _exam_away)

def _set_handled(pub, s, b, event):
    """Handled ourselves on (handled true) or off for one backup lesson: body {teacher, key, handled}; refused unless it is a
    backup of the working copy now. The list stays out of the approved copy and the fingerprint"""
    teacher, key, on = b.get("teacher"), b.get("key"), b.get("handled")
    if not isinstance(teacher, str) or not isinstance(key, str) or not isinstance(on, bool):
        raise ValueError(exams_schedules.EVENT_WRONG if event else exams_schedules.WRONG)
    items = (exams_events if event else exams_make).lesson_lists(pub, _exam_cal(pub), s)["backup"]
    if not any(x["teacher"] == teacher and x["key"] == key for x in items): raise ValueError(NO_BACKUP)
    tag = "%s|%s" % (teacher, key)
    s["handled"] = [x for x in s.get("handled") or [] if isinstance(x, str) and x != tag] + ([tag] if on else [])

def _handled(pub, who, s, event):
    """save a Handled ourselves change (no check: it works after a new publish too), sync relief and answer as the view"""
    try: _set_handled(pub, s, _exam_json(), event)
    except ValueError as e: return {"error": str(e)}, 400
    except BAD_INPUT + (IndexError,): return {"error": exams_schedules.EVENT_WRONG if event else exams_schedules.WRONG}, 400
    saved, bad = _save_exam(s, pub, who, check=False, event=event)
    if bad: return bad
    _relief_sync(pub, saved)
    return (_event_view_reply if event else _exam_view_reply)(pub, saved)

@app.post("/api/exams/<id>/handled")
@need("committee", "staff")
def exams_handled(id):
    pub, who, err = _exams_gate()
    if err: return err
    with exams_schedules.editing():
        s, err = _exam_or_404(id)
        return err or _handled(pub, who, s, False)

# ------------------------------------------------------------------------------------------------ staff: events
def _event_others(pub, s):
    """(the other schedules' copies, what they hold busy) for an event"""
    others = exams_schedules.copies(s.get("id"))
    return others, exams_schedules.busies(others, pub["model"]) + exams_schedules.relief_busy(pub["model"])

def _event_review(pub, cal, s, busy, others):
    rv = exams_events.review(pub, cal, s, busy, others)
    copy = lambda: exams_approval.as_schedule(s) if rv.get("copy") == "approved" else s
    return _backups_left(rv, lambda: exams_events.lesson_lists(pub, cal, copy()), s, pub)

def _event_review_reply(pub, s):
    """the Approval tab of an event: as an exam's, with the event's own review and what stops Send"""
    model, cal = pub["model"], _exam_cal(pub)
    others, busy = _event_others(pub, s)
    st = s.get("status") or "draft"
    return jsonify(status=st, label=exams_approval.label(s, _exams_today()), note=s.get("note") or "", sent_at=s.get("sent_at"), sent_by=s.get("sent_by"),
                   approved_at=s.get("approved_at"), approved_by=s.get("approved_by"),
                   changed=s.get("sent_fp") is not None and s.get("sent_fp") != exams_approval.fp(s),
                   can_send=exams_approval.blocked(s, model, False, exams_events.send_errors(pub, cal, s, busy, others)), can_approve=_exams_can_approve(),
                   unsent=exams_approval.changes(s, model) if st == "approved" else [], review=_event_review(pub, cal, s, busy, others), away=_away_texts(pub, s))

def _event_view(pub, s):
    model, cal = pub["model"], _exam_cal(pub)
    others, busy = _event_others(pub, s)
    dts = exams_events.on_dates(pub, cal, s)
    inside = {c for e in dts for c in e["classes"]}
    people = relief_staff(pub)
    entry = lambda date: (s.get("days") or {}).get(date) or {}
    return dict(summary=dict(days=[dict(date=e["date"], day=e["day"], levels=e["levels"], whole=bool(entry(e["date"]).get("whole", True)),
                                        window=[exams_days.hhmm(e["start"]), exams_days.hhmm(e["end"])]) for e in exams_days.dates(s, cal, model)]),
                classes=[c["name"] for c in model.get("classes") or [] if c["name"] in inside], going=exams_events.going(pub, cal, s, busy),
                lessons=_marked(exams_events.lesson_lists(pub, cal, s), s, pub, cal), freed=exams_events.freed(pub, cal, s, busy), flags=exams_events.flags(pub, cal, s),
                cuts=exams_events.cuts(pub, cal, s), clashes=exams_events.clashes(pub, cal, s, busy, others),
                periods=[[exams_days.hhmm(a), exams_days.hhmm(b)] for a, b in exams_days.bounds(model)], rooms=[r["name"] for r in model.get("rooms") or []],
                depts=sorted({d for p in people for d in p["depts"]}), people=[p["name"] for p in people])

@app.get("/events/<id>")
@need("committee", "staff")
def events_one_page(id): return app.send_static_file("exams.html")

@app.get("/api/events")
@need("committee", "staff")
def events_list():
    pub, who, _, every, err = _event_gate()
    if err: return err
    m = pub["model"]
    return jsonify(schedules=_with_away(exams_schedules.listing(_exams_today(), exams_make.published_at(pub), ("event",), None if every else who), pub),
                   levels=m.get("levels") or [], classes=[[c["name"], c["level"]] for c in m.get("classes") or []],
                   calendar_ok=bool(_exam_cal(pub).get("terms")), people=[p["name"] for p in relief_staff(pub)] if every else [])

@app.post("/api/events")
@need("committee", "staff")
def events_create():
    pub, who, _, every, err = _event_gate()
    if err: return err
    if not _exam_cal(pub).get("terms"): return {"error": exams_schedules.NO_CALENDAR}, 409
    b = _exam_json()
    in_charge = b.get("in_charge")
    if every:
        if not isinstance(in_charge, str) or not in_charge.strip(): return {"error": PICK_IN_CHARGE}, 400
        if in_charge not in {p["name"] for p in relief_staff(pub)}: return {"error": f"{in_charge} is not on the published timetable or the staff list."}, 400
    else: in_charge = who
    try: sched = exams_schedules.new_event(b["name"], b["levels"], b.get("classes") or [], b["start"], b["end"], who, in_charge)
    except ValueError as e: return {"error": str(e)}, 400
    except BAD_INPUT: return {"error": exams_schedules.EVENT_WRONG}, 400
    with exams_schedules.editing():
        saved, bad = _save_exam(sched, pub, who, event=True)
    return bad or jsonify(saved)

@app.get("/api/events/<id>")
@need("committee", "staff")
def events_get(id):
    pub, who, s, _, err = _event_gate(id)
    return err or jsonify(s)

@app.put("/api/events/<id>")
@need("committee", "staff")
def events_put(id):
    with exams_schedules.editing():   # from loading to saving: what is kept is what is stored now
        pub, who, old, _, err = _event_gate(id)
        if err: return err
        new = dict(_exam_json(), **{k: old.get(k) for k in EVENT_KEEPS})
        new["log"] = old.get("log") or []
        saved, bad = _save_exam(new, pub, who, event=True)
    return bad or jsonify(saved)

@app.delete("/api/events/<id>")
@need("committee", "staff")
def events_delete(id):
    with exams_schedules.editing():
        pub, who, s, _, err = _event_gate(id)
        if err: return err
        if s.get("approved"): return {"error": ON_SITE}, 409
        exams_schedules.delete(id)
    return {"ok": True}

def _event_view_reply(pub, s):
    try: return jsonify(_event_view(pub, s))
    except ValueError as e: return {"error": str(e)}, 400
    except BAD_INPUT + (IndexError,): return {"error": exams_schedules.EVENT_WRONG}, 400

@app.get("/api/events/<id>/view")
@need("committee", "staff")
def events_view(id):
    pub, who, s, _, err = _event_gate(id)
    return err or _event_view_reply(pub, s)

@app.post("/api/events/<id>/fill")
@need("committee", "staff")
def events_fill(id):
    with exams_schedules.editing():
        pub, who, s, _, err = _event_gate(id)
        if err: return err
        b = _exam_json()
        try:
            names = b.get("names") or []
            if not isinstance(names, list) or not all(isinstance(x, str) for x in names) or not isinstance(b.get("dept") or "", str): raise ValueError(exams_schedules.EVENT_WRONG)
            added = exams_events.fill(pub, _exam_cal(pub), s, b.get("way"), b.get("dept") or "", names)
            if not added: return jsonify(s)   # nobody to add: nothing changes, so a sent event keeps its fingerprint
            s["going"] = list(s.get("going") or []) + added
            s["going_by"] = b["way"]
        except ValueError as e: return {"error": str(e)}, 400
        except BAD_INPUT: return {"error": exams_schedules.EVENT_WRONG}, 400
        saved, bad = _save_exam(s, pub, who, event=True)
    return bad or jsonify(saved)

def _event_send(pub, s, by, now, b):
    others, busy = _event_others(pub, s)
    exams_approval.send(s, pub["model"], by, now, False, exams_events.send_errors(pub, _exam_cal(pub), s, busy, others))

def _event_free(pub, s):
    """who may stand in for someone going with the approved event: the names relief finds free then (freed, then free)"""
    ap = exams_approval.as_schedule(s)
    if ap is None: raise ValueError(exams_approval.NOT_ON_SITE)
    return exams_events.who_free(pub, _exam_cal(pub), ap, exams_schedules.elsewhere(s.get("id"), pub["model"]))

def _event_away(pub, s, by, now, b):
    away, name = b["away"], b["name"]
    if not all(isinstance(x, str) for x in (away, name)): raise ValueError(exams_schedules.EVENT_WRONG)
    if name not in {c["name"] for g in ("freed", "free") for c in _event_free(pub, s)[g]}: raise ValueError("%s is not free then." % name)
    exams_approval.replace_going(s, away, name, by, now)

@app.get("/api/events/<id>/review")
@need("committee", "staff")
def events_review_get(id):
    pub, who, s, _, err = _event_gate(id)
    return err or _event_review_reply(pub, s)

@app.post("/api/events/<id>/send")
@need("committee", "staff")
def events_send(id): return _exam_approval(id, _event_send, check=True, event=True)

@app.post("/api/events/<id>/approve")
@need("committee", "staff")
def events_approve(id): return _exam_approval(id, _act_approve, approver=True, event=True)

@app.post("/api/events/<id>/send-back")
@need("committee", "staff")
def events_send_back(id): return _exam_approval(id, _act_send_back, approver=True, event=True)

@app.post("/api/events/<id>/withdraw")
@need("committee", "staff")
def events_withdraw(id): return _exam_approval(id, _act_withdraw, approver=True, event=True)

@app.post("/api/events/<id>/away")
@need("committee", "staff")
def events_away(id): return _exam_approval(id, _event_away, event=True)

@app.post("/api/events/<id>/handled")
@need("committee", "staff")
def events_handled(id):
    with exams_schedules.editing():
        pub, who, s, _, err = _event_gate(id)
        return err or _handled(pub, who, s, True)

@app.get("/api/events/<id>/who")
@need("committee", "staff")
def events_who(id):
    pub, who, s, _, err = _event_gate(id)
    if err: return err
    try: return jsonify(_event_free(pub, s))
    except ValueError as e: return {"error": str(e)}, 400

startup_log()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), debug=False)

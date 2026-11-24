"""School timetable app (one school per deployment).

Committee (COMMITTEE_CODE): fill the setup step by step, download it with the timetable skill for an outside AI agent
to make the timetable, then upload that timetable, check it and publish it.
Teachers (TEACHER_CODE): every published class, teacher, room and student timetable, Who's free, PDFs.
Students (STUDENT_CODE): class timetables and 'Build my timetable'; personal codes show one student's own timetable.
Staff (a personal code each, made from their name): the Relief module and everything the teacher code opens."""
import copy, datetime, gzip, hmac, io, json, os, re, secrets, shutil, sys, tempfile, threading, time, traceback, urllib.parse, zipfile
from functools import wraps
from flask import Flask, jsonify, request, send_file, abort, session, redirect, Response, g
from werkzeug.middleware.proxy_fix import ProxyFix
from ttgen.samples import secondary, primary
from ttgen.template import write_template
from ttgen.reader import read_template
from ttgen.spec import RULE_TYPES, SCOPES, CODES, SETTING_RULES, ROLES, SKILL_VERSION, defaults, typed_rules
import access, checks, compare, draft, history, putback, refit, refit_plan, store, students, sync, typed, versions
from accounts import passwords, people, rights as rights_table
from relief import bot as relief_bot, codes as relief_codes, fill as relief_fill, lessons as relief_lessons, morning as relief_morning, outbox as relief_outbox, people as relief_people, report as relief_report, settings as relief_settings, tell as relief_tell, tg as relief_tg, tgweb as relief_tgweb, web as relief_web
from relief import absences as relief_absences
from relief import links as relief_links
import exams.relief_links as exams_relief_links
from plan import ai as plan_ai, steps as plan_steps, web as plan_web
from ttgen import choices
import exams.approval as exams_approval, exams.review as exams_review, exams.days as exams_days, exams.settings as exams_settings, exams.schedules as exams_schedules, exams.papers as exams_papers, exams.invigilate as exams_invigilate, exams.make as exams_make, exams.seating as exams_seating, exams.printouts as exams_printouts, exams.published as exams_published, exams.events as exams_events

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.join(HERE, "skill", "school-timetable-generator")
app = Flask(__name__, static_folder="static", static_url_path="/static")
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
app.secret_key = os.environ.get("SECRET_KEY") or os.urandom(32)
app.json.sort_keys = False   # the setup's days (Mon..Fri) and levels keep their order through the API; the grid lists days in it
app.config.update(MAX_CONTENT_LENGTH=40 * 1024 * 1024, SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
                  SESSION_COOKIE_SECURE=store.on_railway(), PERMANENT_SESSION_LIFETIME=60 * 60 * 24 * 120)
limiter = access.Limiter()        # 10 wrong codes or passwords from one address in 10 minutes
lockout = passwords.Lockout()     # 5 wrong passwords for one username in 15 minutes
_cache = {}
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

# ------------------------------------------------------------------------------------------------ access
# Who is signed in. Session keys: a shared code `role` (committee, head, teacher, student); a student's personal code
# `role` "personal" and `sid`; a person (staff, by name) `who`, `via` ("code" or "password"), `n` (the sign-in number on
# their record: raising it ends every older session) and, signed in with a password, `exp` (14 days). Relief stage 1's
# sessions (`role` "staff" and `who`) count as code sessions with `n` 0. Rights come from the records on each request,
# never from the cookie.
API = ("/api/", "/pdf/", "/files/")
FORTNIGHT = 14 * 24 * 3600
SHARED_AS = {"committee": "Shared committee code", "head": "Shared heads' code", "teacher": "Shared teacher code", "student": "Shared student code"}
_KEYS = ("role", "who", "via", "n", "exp", "sid")
_NOBODY = dict(person=None, via=None, shared=None)

def _api(): return request.path.startswith(API)

def _end(gone=False):
    """end the session; gone: a code session whose person is no longer on the published timetable ("Code no longer valid")"""
    session.clear(); g._gone = gone
    return _NOBODY

def _stand_in(name, data):
    """a code session's person while nothing is published (a publish swaps folders): from their record, so the session
    stays, as relief's did"""
    r = people.record(data, name)
    return dict(name=name, short=name, depts=list(r["depts"]), role="", teaches=False, staff_only=False, group=r["group"] or "teacher",
                extras=r["extras"], username=r["username"], off=r["off"], has_password=bool(r["pw"]), last=max(r["signins"], default=None),
                n=r["n"], must_change=r["must_change"])

def _check():
    """the session held against the records: dict(person, via, shared); a session that no longer holds is cleared"""
    name, r = session.get("who"), session.get("role")
    if name is not None:
        v = session.get("via", "code")
        if not isinstance(name, str) or v not in ("code", "password") or r not in (None, "staff"): return _end()
        exp = session.get("exp")
        if v == "password" and not (isinstance(exp, (int, float)) and time.time() < exp): return _end()
        if not people.readable(): return _end()    # the records cannot be read: no one is let in by name (shared codes still work)
        data, pub = people.load(), store.published()
        p = people.find(name, pub, data)
        if p is None:
            if v == "password": return _end()       # a password session never depends on the published timetable
            if pub: return _end(gone=True)          # dropped or renamed on a later publish
            p = _stand_in(name, data)
        if p["off"] or p["n"] != session.get("n", 0): return _end()
        if v == "password" and not p.get("pw"): return _end()   # no password on the record (removed, or never set): no password session
        p.pop("pw", None)
        return dict(person=p, via=v, shared=None)
    if r in people.SHARED:
        if people.load()["ways"]["off"].get(r) is not None: return _end()   # turned off on the admin page
        return dict(person=None, via="shared", shared=r)
    if r == "personal": return dict(person=None, via="personal", shared=None)
    return _NOBODY

def _state():
    """(session key, checked session, rights), worked out once a request and again only when the session changes"""
    key = tuple(session.get(k) for k in _KEYS)
    got = g.get("_signed")
    if got is None or got[0] != key:
        st = _check()
        got = g._signed = (tuple(session.get(k) for k in _KEYS), st, rights_table.rights(st["person"], st["via"], st["shared"]))
    return got

def who():
    """the person signed in by name (people.find, without the password hash), or None"""
    return _state()[1]["person"]

def via(): return _state()[1]["via"]

def shared(): return _state()[1]["shared"]

def rights(): return _state()[2]

def has(right): return right in rights()

def by():
    """who the history records for this session"""
    st = _state()[1]
    if st["person"]: return history.by_of(st["person"]["name"], st["via"])
    if st["via"] == "shared": return history.by_of(None, "shared", SHARED_AS[st["shared"]])
    if st["via"] == "personal": return history.by_of(None, "personal", "A student")
    return history.by_of(None, "?")

def is_head():
    """a head of department at the setup: the shared heads' code, or an HOD or SH signed in with their password"""
    return has("setup") and not has("committee")

def head_depts():
    """the departments a head signed in by name may change: their record's, as a list in its order ([] when none, and then
    every lesson change is refused); None for anyone else (the shared heads' code changes every department, as today)"""
    p = who()
    if p is None or not is_head(): return None
    return list(people.record(people.load(), p["name"])["depts"])

def _relief_stage_1():
    """a session started before accounts (relief stage 1: `role` "staff" and `who`)"""
    return session.get("role") == "staff" and who() is not None

def _must_change_first():
    """a person signed in with a one-time password chooses their own before anything else (their code sessions are not
    stopped: the code is not the password)"""
    p = who()
    if p is None or via() != "password" or not (p.get("must_change") and p.get("username") and p.get("has_password")): return None
    if _api(): return {"error": "Choose a new password first."}, 403
    return redirect("/account/password")

# every right a session can hold (accounts/rights.py gives them); need() refuses any other name when the app starts
RIGHTS = frozenset({"committee", "setup", "timetable", "files", "history", "history.dept", "history.own", "codes", "admin", "own", "exams",
                    "relief", "relief.plan", "relief.settings", "relief.save", "relief.team"})

def need(*names):
    """the route needs one of these rights: the server decides, from the records, on every request. Without one, the
    API answers 401 "Please sign in again." and a page goes to the sign-in page ("Code no longer valid" for a code
    session whose person has left the published timetable)"""
    wrong = sorted(set(names) - RIGHTS)
    if not names or wrong: raise ValueError(f"need() takes right names only, not {wrong or 'nothing'}")
    def deco(f):
        @wraps(f)
        def inner(*a, **k):
            stop = _must_change_first()
            if stop: return stop
            if not rights() & set(names):
                if _api(): return {"error": "Please sign in again."}, 401
                return _no_longer_valid() if g.get("_gone") else redirect("/login")
            return f(*a, **k)
        inner._need = names
        return inner
    return deco

def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

def setup_problems():
    """what this deployment is missing (Railway variables, a volume): on the sign-in page and in the logs at startup"""
    _, probs = access.configured()
    if not people.readable(): probs.append(ACCOUNTS_UNREADABLE)
    if people.usable_admins(people.load()):   # people sign in as themselves now: a shared code left unset is not a problem
        unset = {f"{var} is not set in Railway variables." for _, var in access.ROLES}
        probs = [p for p in probs if p not in unset]
    if recovery_too_short(): probs.append(RECOVERY_SHORT)
    if not store.on_volume(): probs.append("No Railway volume: the setup and the published timetable are lost on the next deploy. Add a volume mounted at /data.")
    return probs

RECOVERY_MIN = 16
RECOVERY_SHORT = "ADMIN_RECOVERY_CODE is too short (use at least 16 letters or digits); recovery is off."
RECOVERY_ON = "A recovery code is set in Railway variables: remove it once you are back in."

def _recovery_raw():
    return (os.environ.get("ADMIN_RECOVERY_CODE") or "").strip()

def recovery_code():
    """ADMIN_RECOVERY_CODE (trimmed) when it is long enough to use: 16 characters or more. A shorter one counts as not
    set (/login/recover is not there), so a weak value can never open an admin account"""
    c = _recovery_raw()
    return c if len(c) >= RECOVERY_MIN else None

def recovery_too_short():
    """ADMIN_RECOVERY_CODE is set but too short to use (the Ways in tab and the warnings say so)"""
    return 0 < len(_recovery_raw()) < RECOVERY_MIN

def startup_log():
    print(f"Timetable app: data in {store.DATA}", file=sys.stderr, flush=True)
    for p in setup_problems(): print(f"WARNING: {p}", file=sys.stderr, flush=True)

def page(title, body):
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)}</title>
<link rel="stylesheet" href="/static/login.css"></head><body>{body}</body></html>"""

# ------------------------------------------------------------------------------------------------ signing in
CODE_LABEL = "Your personal code (on the slip from the school)"
CODE_LABEL_SHARED = "Your code (the one the school gave you)"   # while a shared code still opens the site
TO_USERNAME = "Committee and management: sign in with your username"
WRONG_CODE = "That code does not work. Check it and try again."
TOO_MANY_CODES = "Too many wrong codes. Wait ten minutes and try again."
SWITCHED_OFF = "This account is switched off. Ask the timetable committee."
NO_ACCOUNTS = "Accounts need SECRET_KEY in Railway variables."
NO_MATCH = "That username and password do not match."
LOCKED = "Too many wrong tries. Wait 15 minutes and try again."
TOO_MANY = "Too many wrong tries. Wait ten minutes and try again."
NOT_SAME = "The two new passwords are not the same."
NOT_CURRENT = "Your current password is not right."
NO_PASSWORD = "You sign in with your personal code, so you have no password to change. Ask an admin if you need a username."
NO_RECOVERY = "That username and recovery code do not match."
RECOVERY_USED = "That recovery code has been used. Set a new ADMIN_RECOVERY_CODE in Railway variables."
CROSS_SITE = "That request did not come from this site."
PERSON_OFF = "Signing in as a person is off for now. Use the code the school gave your group, or ask the timetable committee."
ACCOUNTS_UNREADABLE = "The accounts file could not be read: signing in as a person is off until it is fixed."
NO_PERSONAL_STAFF = "Personal codes are off until SECRET_KEY is set in Railway variables."
_SIGNED_IN = {"code": "Signed in with their code", "password": "Signed in with their password", "shared": "Signed in with a shared code",
              "personal": "Signed in with a personal code", "recovery": "Signed in with the recovery code and set a new password"}

def accounts_on():
    """accounts (passwords) need SECRET_KEY: without it the sessions are signed with a key that changes at every restart"""
    return bool(os.environ.get("SECRET_KEY"))

def school_name():
    pub = store.published()
    return ((pub or {}).get("meta") or {}).get("school") or os.environ.get("SCHOOL_NAME") or "School timetable"

def _warnings():
    return "".join(f"<p class='warn'>{esc(p)}</p>" for p in setup_problems())

def _code_label():
    """the code box's words: the plain ones people already know while any shared code is set and not turned off (a teacher
    with the shared teacher code is not told they need a personal one); "personal code" once every shared code is off.
    Accounts that cannot be read count as on, as the sign-in does (a turned-off code works again then)"""
    have, _ = access.configured()
    try: off = people.load()["ways"]["off"]
    except Exception: off = {}
    return CODE_LABEL_SHARED if any(have.get(r) and off.get(r) is None for r in people.SHARED) else CODE_LABEL

def _code_page(msg=""):
    err, warn = (f"<p class='err'>{esc(msg)}</p>" if msg else ""), _warnings()
    return page("Sign in", f"""<main class="front"><header class="hero"><h1>{esc(school_name())}</h1><p>Timetable</p></header>
<div class="login one"><form method="post" action="/login"><label for="code">{esc(_code_label())}</label>
<input id="code" name="code" autocomplete="off" autocapitalize="characters" spellcheck="false" placeholder="XXXX-XXXX" autofocus required>
<button type="submit">Open</button></form>{err}
<p class="way"><a href="/login/password">{esc(TO_USERNAME)}&nbsp;&rarr;</a></p></div>{f'<div class="notes">{warn}</div>' if warn else ""}</main>""")

def _form_page(title, form, msg="", hint="", back=("/login", "Sign in with a code"), tail=None):
    """a small page with one form; tail: the HTML at its foot (the setup warnings unless given)"""
    err = f"<p class='err'>{esc(msg)}</p>" if msg else ""
    return page(title, f"""<main class="login"><p class="small"><a class="back" href="{back[0]}">&larr; {esc(back[1])}</a></p>
<h1>{esc(title)}</h1><p class="muted">{esc(school_name())}</p>{form}{err}{f'<p class="muted small">{esc(hint)}</p>' if hint else ""}{_warnings() if tail is None else tail}</main>""")

def _field(name, label, kind="password", auto="off", focus=False):
    t = ' type="password"' if kind == "password" else ' autocapitalize="none" spellcheck="false"'
    return f"""<label for="{name}">{esc(label)}</label><input id="{name}" name="{name}" class="plain"{t} autocomplete="{auto}"{" autofocus" if focus else ""} required>"""

def _password_page(msg=""):
    form = f"""<form method="post" action="/login/password">{_field("username", "Username", "text", "username", True)}
{_field("password", "Password", auto="current-password")}<button type="submit">Sign in</button></form>""" if accounts_on() and people.readable() else ""
    return _form_page("Sign in with your username", form, msg, "Forgotten your password? Ask an admin to give you a new one.")

def _change_page(p, msg="", form=True):
    first = "<p>Choose your own password before you go on.</p>" if p.get("must_change") else ""
    f = f"""{first}<form method="post" action="/account/password">{_field("current", "Your current password", auto="current-password", focus=True)}
{_field("new", "New password (at least 10 characters)", auto="new-password")}{_field("again", "New password again", auto="new-password")}
<button type="submit">Change password</button></form>""" if form else ""
    return _form_page("Change your password", f, msg, f"Signed in as {p['name']}.", back=("/home", "Back"), tail='<p class="small"><a href="/logout">Sign out</a></p>')

def _recover_page(msg=""):
    form = "" if not (accounts_on() and people.readable()) else f"""<form method="post" action="/login/recover">{_field("username", "Admin username", "text", "username", True)}
{_field("code", "Recovery code (ADMIN_RECOVERY_CODE)")}{_field("new", "New password (at least 10 characters)", auto="new-password")}
{_field("again", "New password again", auto="new-password")}<button type="submit">Set the password and sign in</button></form>"""
    return _form_page("Admin recovery", form, msg, "The recovery code works once. Remove ADMIN_RECOVERY_CODE from Railway variables once you are back in.")

def _record_signin(ok, how, name=None, shared_=None, reason=None):
    """one history entry for a sign-in or a refused try. Never what was typed: a name only when it is a person's"""
    as_ = name or (SHARED_AS.get(shared_) if shared_ else None) or ("A student" if how == "personal" else "Unknown")
    entry = {"kind": "signin", "where": "Sign-in", "ok": ok, "via": how, "shared": shared_, "who": name, "as": as_, "reason": reason,
             "addr": request.remote_addr or "?", "text": _SIGNED_IN.get(how, "Signed in") if ok else f"Sign-in refused: {reason}"}
    try: history.add(entry)
    except Exception as e: print(f"WARNING: a sign-in could not be recorded in the history ({type(e).__name__})", file=sys.stderr, flush=True)

_quiet = {}   # (what, address or username) -> when its last locked try was recorded: one line per ten minutes, however many tries

def _record_locked(key, how, name=None):
    now = time.time()
    if now - _quiet.get(key, 0) < 600: return
    if len(_quiet) > 5000: _quiet.clear()
    _quiet[key] = now
    _record_signin(False, how, name, reason="locked")

def _record_account(what, name, text):
    try: history.add({"kind": "account", "what": what, "where": "Admin", "people": [name], "changes": [], "text": text, **by()})
    except Exception as e: print(f"WARNING: an account change could not be recorded in the history ({type(e).__name__})", file=sys.stderr, flush=True)

def _note_signin(name):
    """the time on the person's record (the last two are kept); a sign-in never fails for want of it"""
    def change(d):
        r = d["people"].get(name)
        if not isinstance(r, dict):
            if not any(p["name"] == name for p in people.staff(store.published(), d)): return   # removed meanwhile: no record comes back
            r = d["people"][name] = people.record(d, name)   # a first record starts from their sign-out number
        s = r.get("signins") if isinstance(r.get("signins"), list) else []
        r["signins"] = [x for x in s if isinstance(x, (int, float)) and not isinstance(x, bool)][-1:] + [time.time()]
    try: people.update(change)
    except Exception as e: print(f"WARNING: a sign-in time could not be kept ({type(e).__name__})", file=sys.stderr, flush=True)

def _lock_key(data, name, typed):
    """the lockout's key: the account's own username when the typed one finds it (however it was typed), else what was typed"""
    return (people.record(data, name)["username"] or typed).lower() if name else typed.lower()

def _start(**keys):
    session.clear(); session.permanent = True; session.update(keys)

@app.get("/login")
def login_page():
    return _code_page()   # ?as= (the old cards) is accepted and ignored

@app.post("/login")
def login():
    addr = request.remote_addr or "?"
    if limiter.blocked(addr):
        _record_locked(("addr", addr), "code"); return _code_page(TOO_MANY_CODES), 429
    pub, data = store.published(), people.load()
    r, val = access.match(request.form.get("code"), pub["codes"] if pub else {}, relief_people.staff_codes(people.staff(pub, data)))
    if r in people.SHARED and data["ways"]["off"].get(r) is not None:   # a shared code turned off is a wrong code
        limiter.fail(addr); _record_signin(False, "shared", shared_=r, reason="code turned off"); return _code_page(WRONG_CODE), 401
    if not r:
        limiter.fail(addr); _record_signin(False, "code", reason="wrong code"); return _code_page(WRONG_CODE), 401
    if r == "staff":
        if not people.readable():   # the right code, but the records cannot be read: refused, and no strike
            _record_signin(False, "code", val, reason="accounts file unreadable"); return _code_page(PERSON_OFF), 403
        rec = people.record(data, val)
        if rec["off"]:   # the right code: not a guess, so no strike
            _record_signin(False, "code", val, reason="switched off"); return _code_page(SWITCHED_OFF), 403
        _note_signin(val); _start(who=val, via="code", n=rec["n"]); _record_signin(True, "code", val)
        return redirect("/home")
    if r == "personal":
        _start(role="personal", sid=val); _record_signin(True, "personal"); return redirect("/me")
    _start(role=r); _record_signin(True, "shared", shared_=r)
    return redirect("/" if r in ("committee", "head") else "/timetable")

@app.route("/login/password", methods=["GET", "POST"])
def login_password():
    if not accounts_on(): return _password_page(NO_ACCOUNTS), 403 if request.method == "POST" else 200
    if not people.readable(): return _password_page(PERSON_OFF), 403 if request.method == "POST" else 200
    if request.method == "GET": return _password_page()
    addr, data = request.remote_addr or "?", people.load()
    username = str(request.form.get("username") or "").strip()[:200].strip()   # as by_username reads it
    name, _ = people.by_username(data, username)
    key = _lock_key(data, name, username)
    if limiter.blocked(addr):
        _record_locked(("addr", addr), "password", name); return _password_page(TOO_MANY), 429
    if lockout.blocked(key):   # an unknown username locks the same way, so the answer never shows which usernames exist
        _record_locked(("user", key), "password", name); return _password_page(LOCKED), 429
    rec = people.record(data, name) if name else None
    if not passwords.check_pw(rec["pw"] if rec else None, request.form.get("password")):
        limiter.fail(addr); lockout.fail(key)
        _record_signin(False, "password", name, reason="wrong password" if name else "unknown username")
        return _password_page(NO_MATCH), 401
    if rec["off"]:
        _record_signin(False, "password", name, reason="switched off"); return _password_page(SWITCHED_OFF), 403
    lockout.clear(key); _note_signin(name)
    _start(who=name, via="password", n=rec["n"], exp=time.time() + FORTNIGHT); _record_signin(True, "password", name)
    return redirect("/account/password" if rec["must_change"] else "/home")

@app.route("/account/password", methods=["GET", "POST"])
def account_password():
    p = who()
    if p is None: return redirect("/login")
    if not accounts_on(): return _change_page(p, NO_ACCOUNTS, form=False), 403
    if not p.get("username"): return _change_page(p, NO_PASSWORD, form=False), 403
    if request.method == "GET": return _change_page(p)
    addr, key = request.remote_addr or "?", p["username"].lower()
    if limiter.blocked(addr): return _change_page(p, TOO_MANY), 429
    if lockout.blocked(key): return _change_page(p, LOCKED), 429
    cur, new, again = (str(request.form.get(k) or "") for k in ("current", "new", "again"))
    rec = people.record(people.load(), p["name"])
    if not passwords.check_pw(rec["pw"], cur):
        limiter.fail(addr); lockout.fail(key); return _change_page(p, NOT_CURRENT), 403
    why = passwords.problem(new, rec["username"] or "", p["name"])
    if why: return _change_page(p, why), 400
    if new != again: return _change_page(p, NOT_SAME), 400
    h = passwords.hash_pw(new)
    def change(d):
        x = d["people"].get(p["name"])
        if not isinstance(x, dict): return None   # removed meanwhile (a username is on a record): no record comes back
        x.update(pw=h, must_change=False, n=people.record(d, p["name"])["n"] + 1)
        return x["n"]
    try: n = people.update(change)
    except people.Unreadable: return _change_page(p, people.UNREADABLE), 503
    if n is None:
        session.clear(); return redirect("/login")   # as for a session that no longer holds
    session["n"] = n   # this session stays; every other one of this person's ends (its number is old)
    _record_account("password", p["name"], "Changed their password")
    return redirect("/home")

def _recovery_used(data, code):
    return any(passwords.check_pw(h, code) for h in data["ways"]["recovery_used"] if isinstance(h, str))

@app.route("/login/recover", methods=["GET", "POST"])
def login_recover():
    """while ADMIN_RECOVERY_CODE is set: an admin's username and that code (accepted once per value) set a new password"""
    code = recovery_code()
    if not code: abort(404)   # not set, or too short to use
    if not accounts_on(): return _recover_page(NO_ACCOUNTS), 403 if request.method == "POST" else 200
    if not people.readable(): return _recover_page(PERSON_OFF), 403 if request.method == "POST" else 200
    if request.method == "GET": return _recover_page()
    addr = request.remote_addr or "?"
    if limiter.blocked(addr):
        _record_locked(("addr", addr), "recovery"); return _recover_page(TOO_MANY), 429
    username = str(request.form.get("username") or "").strip()[:200].strip()
    given, new, again = (str(request.form.get(k) or "") for k in ("code", "new", "again"))
    data = people.load(); name, _ = people.by_username(data, username)
    right = hmac.compare_digest(given.strip().encode(), code.encode())
    if right and _recovery_used(data, code):
        limiter.fail(addr); _record_signin(False, "recovery", name, reason="recovery code already used"); return _recover_page(RECOVERY_USED), 403
    if not right or name not in people.admins(data):   # any admin found by their username, with a password or without one
        limiter.fail(addr); _record_signin(False, "recovery", name, reason="wrong code"); return _recover_page(NO_RECOVERY), 401
    why = passwords.problem(new, username, name)
    if why: return _recover_page(why), 400
    if new != again: return _recover_page(NOT_SAME), 400
    h, used = passwords.hash_pw(new), passwords.hash_pw(code)
    def change(d):
        if _recovery_used(d, code) or name not in people.admins(d): return None   # used meanwhile
        x = d["people"][name]
        s = x.get("signins") if isinstance(x.get("signins"), list) else []
        n = people.record(d, name)["n"] + 1
        x.update(pw=h, must_change=False, n=n, signins=[t for t in s if isinstance(t, (int, float)) and not isinstance(t, bool)][-1:] + [time.time()])
        d["ways"]["recovery_used"].append(used)
        return n
    try: n = people.update(change)
    except people.Unreadable: return _recover_page(people.UNREADABLE), 503
    if n is None: return _recover_page(RECOVERY_USED), 403
    lockout.clear(_lock_key(data, name, username))
    _start(who=name, via="password", n=n, exp=time.time() + FORTNIGHT); _record_signin(True, "recovery", name)
    _record_account("recovery", name, "Password set with the recovery code")
    return redirect("/home")

@app.get("/logout")
def logout():
    plan_web.signed_out(_plan_owners_of_session())   # a talk of Plan with AI is gone when its person signs out
    session.clear(); return redirect("/login")

# the tiles of the home page, in order: (title, what it opens, link, the rights that show it)
TILES = (("Committee page", "Set up, check and publish the timetable", "/", ("setup",)),
         ("Timetables", "Classes, teachers, rooms, Who's free", "/timetable", ("timetable",)),
         ("Relief", "Ask for relief, your reliefs", "/relief", ("relief", "relief.settings")),
         ("Exams and events", "", "/exams", ("exams", "committee")),
         ("Plan with AI", "Plan an exam or a common test by talking it through", "/plan", ("exams", "committee")),
         ("Admin", "Staff, students and the ways in", "/admin", ("admin",)),
         ("History", "Who changed what, and when", "/history", ("history", "history.dept", "history.own")))
OWN_HISTORY = "Your own changes"
GREYED = ("Committee page", "Admin")   # signed in with a code, these wait for the password
DUTIES_TILE = ("My exam and event duties", "Your duties, your events and the lessons that don't happen")   # in place of Exams and events for everyone else
TO_PASSWORD = "Sign in with your password to open this."
_HOW = {"code": "Signed in with your code", "password": "Signed in with your password"}

def _route_exists(path):
    return any(r.rule == path for r in app.url_map.iter_rules())

def _tiles(p):
    """the tiles for the person p, in order, as (title, line, link, greyed): those they may open, and greyed those only
    their password opens (a committee member's or a head's code opens all but the setup and the admin page). Without the
    exams rights, Exams and events is My exam and event duties: the same page shows them only their own duties (exams stage
    2) and the events they are in charge of, where they may start one (stage 4)"""
    mine, strong = rights(), (rights_table.rights(p, "password") if via() == "code" else frozenset())
    out = []
    for title, line, link, need_ in TILES:
        if link == "/exams" and not _route_exists("/exams"): continue
        if link == "/plan" and not plan_ai.enabled(): continue        # no AI on the server: no tile, for anyone
        if mine & set(need_):
            until = p["extras"].get("exams") if link == "/exams" else None
            if link == "/history" and not mine & {"history", "history.dept"}: line = OWN_HISTORY     # only their own changes are there
            out.append((title, f"Until {_day(until)}" if until else line, link, False))
        elif title in GREYED and strong & set(need_): out.append((title, TO_PASSWORD, "/login/password", True))
        elif link == "/exams": out.append((*DUTIES_TILE, link, False))   # anyone else signed in by name: their own exam duties there
    return out

def _since_box(p):
    """the "Since you last signed in" box for the person p, or "" (no previous sign-in, hidden with Later, or nothing to say)"""
    s = people.record(people.load(), p["name"])["signins"]
    if len(s) < 2 or session.get("later") == s[-1]: return ""
    previous = s[-2]
    scope, allow, _ = history_scope()
    if scope in (None, "own"): allow = lambda e: False     # only the committee and heads get the summary; everyone gets the published line
    try: got = history.summary(previous, allow, p["name"])
    except Exception as e:
        print(f"WARNING: the summary since the last sign-in could not be made ({type(e).__name__})", file=sys.stderr, flush=True)
        return ""
    if not got["n"] and not got["published"]: return ""
    out = ['<section class="since"><h2>Since you last signed in</h2>']
    if got["n"]:
        n, pe = got["n"], got["people"]
        out.append(f'<p class="muted small">{esc(history.when_text(previous))} · {n} change{"" if n == 1 else "s"} by {pe} {"person" if pe == 1 else "people"}</p><ul>')
        out += [f'<li><span>{esc(who)} · {esc(where)}</span><b>{c}</b></li>' for who, where, c in got["rows"]]
        if got["more"]: out.append(f'<li class="muted">and {got["more"]} more</li>')
        out.append("</ul>")
    if got["published"]:
        out.append(f'<p>{esc("The timetable was published again on " + history.when_text(got["published"]) + ".")}</p>')
    out.append('<div class="row">')
    if scope and got["n"]: out.append(f'<a href="/history?since={int(previous)}">See them</a>')
    out.append('<form method="post" action="/home/later"><button type="submit">Later</button></form></div></section>')
    return "".join(out)

@app.post("/home/later")
@need("timetable")
def home_later():
    """hides the box until the next sign-in"""
    p = who()
    if p is None: return redirect("/")
    s = people.record(people.load(), p["name"])["signins"]
    if s: session["later"] = s[-1]
    return redirect("/home")

@app.get("/home")
@need("timetable")
def home():
    """a person's tiles: only what they may open; with one tile (and nothing waiting for the password) it opens at once
    (someone signed in by name has several now)"""
    p = who()
    if p is None: return redirect("/")   # a shared code is nobody's: its own page
    got = _tiles(p)
    since_box = _since_box(p)
    if len(got) == 1 and not got[0][3] and not since_box: return redirect(got[0][2])
    tiles = "".join(f'<a class="tile{" off" if off else ""}" href="{link}"><b>{esc(title)}</b><span class="muted small">{esc(line)}</span></a>'
                    for title, line, link, off in got)
    change = ' · <a href="/account/password">Change password</a>' if via() == "password" else ""
    return page("Home", f"""<main class="home"><header class="hello"><h1>Hello, {esc(p["name"])}</h1>
<p class="muted small">{esc(_HOW.get(via(), "Signed in"))}{change} · <a href="/logout">Sign out</a></p></header>
{since_box}<nav class="tiles">{tiles}</nav><p class="muted small foot">{esc(school_name())}</p></main>""")

# ------------------------------------------------------------------------------------------------ every request
@app.before_request
def same_site_only():
    """a change (POST, PUT, PATCH, DELETE) whose Origin, else Referer, names another site is refused, so another site
    cannot make a signed-in person's browser send one; a request with neither header is allowed"""
    if request.method not in ("POST", "PUT", "PATCH", "DELETE"): return None
    src = request.headers.get("Origin") or request.headers.get("Referer")
    if not src: return None
    try: host = urllib.parse.urlsplit(src).netloc
    except ValueError: host = ""
    return ({"error": CROSS_SITE}, 403) if host.lower() != request.host.lower() else None

_tidied_on = None   # the day the accounts and the history were last tidied: kept in memory (once a day, and after a restart)

def _day(iso):
    try: d = datetime.date.fromisoformat(iso)
    except (TypeError, ValueError): return str(iso)
    return f"{d.day} {d.strftime('%b %Y')}"

@app.before_request
def tidy_once_a_day():
    """the first request of each day ends the Exams and events extras whose date has passed, and removes history files
    over two years old. A failure here never breaks the request"""
    global _tidied_on
    today = datetime.date.today()
    if _tidied_on == today: return None
    _tidied_on = today
    try:
        ended = []
        if people.sweep(copy.deepcopy(people.load()), today):   # write the accounts only when an end date has passed
            def sweep(d):
                was = {n: r["extras"].get("exams") for n, r in d["people"].items() if isinstance(r, dict) and isinstance(r.get("extras"), dict)}
                return [(n, was.get(n)) for n in people.sweep(d, today)]
            ended = people.update(sweep)
        if ended:
            history.add_many([{"kind": "account", "what": "ended", "where": "Admin", "who": None, "as": "The app", "via": "app", "people": [n],
                               "changes": [{"name": n, "field": "exams", "was": until, "now": None}],
                               "text": f"Exams and events access ended (until {_day(until)})"} for n, until in ended])
        history.prune(today)
    except Exception as e:
        print(f"WARNING: the daily tidy of the accounts and the history failed ({type(e).__name__})", file=sys.stderr, flush=True)
    return None

_OPEN = {"/login", "/login/password", "/login/recover", "/logout", "/account/password", "/healthz"}

@app.before_request
def password_first():
    """a one-time password is changed before any page or call"""
    if request.path in _OPEN or request.path.startswith("/static/"): return None
    return _must_change_first()

@app.get("/healthz")
def health(): return {"ok": True}

# ------------------------------------------------------------------------------------------------ committee: setup editor
@app.get("/")
@need("setup", "timetable", "own")
def index():
    """the committee page for whoever may see the setup; everyone else to their own page"""
    if has("setup"): return app.send_static_file("index.html")
    if who() is not None: return redirect("/home")
    if has("own"): return redirect("/me")
    return redirect("/timetable")

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
@need("setup")
def meta(kind):
    sc = defaults(kind_ok(kind))
    return jsonify(rule_types=[dict(rule=a, scopes=b, needs_time=c == "Y", needs_number=d == "Y", meaning=e, example=f) for a, b, c, d, e, f in RULE_TYPES],
                   scopes=SCOPES, codes=CODES, defaults=sc, setting_rules=SETTING_RULES,
                   roles=[dict(role=a, what=b, allowance=c, group=d) for a, b, c, d in ROLES], skill_version=SKILL_VERSION)

@app.get("/api/sample/<kind>")
@need("setup")
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

def unfilled_rows(spec):
    """a sentence about the teaching-group rows of step 5 with no subject, which the workbook leaves out ("+ Add teaching group"
    makes such a row, and a row nobody filled in is saved with no fields at all); "" when every row has its subject"""
    rows = [x if isinstance(x, dict) else {} for x in spec.get("lessons") or []]
    rows = [x for x in rows if not str(x.get("subject") or "").strip()]
    if not rows: return ""
    said = lambda x: " ".join(str(v) for v in (x.get("block") or "", ", ".join(str(c) for c in x.get("classes") or [] if c) or "", ", ".join(str(t) for t in x.get("teachers") or [] if t) or "") if v)
    part = [said(x) for x in rows if said(x)]; n, e = len(rows), len(rows) - len(part)
    which = ([f"{e} with nothing filled in"] if e else []) + ([f"{len(part)} with {'; '.join(part[:6])}{' and more' if len(part) > 6 else ''}"] if part else [])
    return (f"{n} teaching group row{'s' if n > 1 else ''} on step 5 {'have' if n > 1 else 'has'} no subject, so {'they are' if n > 1 else 'it is'} left out of the workbook and of the timetable "
            f"({', '.join(which)}). On step 5's Table view, give {'each' if n > 1 else 'it'} a subject or delete {'them' if n > 1 else 'it'}.")

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
    if (left := unfilled_rows(spec)): found.append(dict(level=checks.WARNING, area="lessons", text=left))
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
@need("setup")
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
    return store.replace_setup(spec, why, by=by())

def _changes_reply(since, client, upto=None):
    return {**store.changes_since(since, client, upto), "others": store.seen(client)}

def _int(x):
    try: return int(x)
    except (TypeError, ValueError): return 0

@app.get("/api/setup/changes")
@need("setup")
def get_setup_changes():
    return _changes_reply(_int(request.args.get("since")), str(request.args.get("client") or "")[:40])

@app.post("/api/setup/changes")
@need("setup")
def post_setup_changes():
    """a change as operations; the answer carries what others changed meanwhile, so the caller catches up in the same call"""
    body = request.get_json(force=True, silent=True)
    body = body if isinstance(body, dict) else {}
    client, ops = str(body.get("client") or "")[:40], body.get("ops")
    if not isinstance(ops, list): return {"error": "No changes sent."}, 400
    split = None
    if is_head():
        # judged on the setup as it is under the store's lock, when the change is applied: what a head may not make is
        # skipped and named in the answer, the rest of their work is applied. A head signed in by name changes only their
        # departments (their record's; the shared heads' code: every department, as today)
        depts = head_depts()
        sync.head_prepare(ops, depts)    # a teacher a head adds is provisional, in one of their departments
        split = lambda spec, o: sync.head_split(spec, o, depts)
    since = _int(body.get("since"))
    told = {}
    try: v, refused, mine = store.apply_changes(ops, client, since=since, filter=split, by=by(), told=told)
    except store.Replaced: return _changes_reply(since, client)
    except store.Refused as e: return {"error": str(e)}, 403
    except LookupError: return {"error": "There is no saved setup to change yet."}, 409
    reply = _changes_reply(since, client, v)
    if mine is not None: reply["mine"] = mine    # the version of the sender's own ops: the page applies patches below it first and above it last
    if refused: reply["refused"] = [dict(i=i, why=why) for i, why in refused]
    said = _follow_students(told)
    if said: reply["students"] = said
    return reply

STUDENTS_NOT_UPDATED = "The published timetable was not updated. Press Update the published timetable on the Students step."

def _follow_students(told):
    """bring the students a save named up to date on the published timetable: {"outcome": ...}, {"error": ...} when that
    failed (the save itself stands; only the exception's type is printed), or None when there is nothing to say"""
    if not told.get("students"): return None
    try: out = students.follow(told["students"], by(), told.get("batch"))
    except Exception as e:
        print(f"students.follow failed: {type(e).__name__}", file=sys.stderr)
        return {"error": STUDENTS_NOT_UPDATED}
    if out is None: return None
    try: return {"outcome": out, "status": students.status()}
    except Exception as e:    # the update is made: only the status line is missing
        print(f"students.status failed: {type(e).__name__}", file=sys.stderr)
        return {"outcome": out}

@app.get("/api/students/published")
@need("committee")
def students_published():
    return jsonify(students.status())

@app.get("/api/students/skeleton")
@need("committee")
def students_skeleton():
    k = students.skeleton()
    if k is None: return {"error": "No timetable is published yet."}, 404
    return _gz(jsonify(k))

@app.post("/api/students/update")
@need("committee")
def students_update():
    """bring the whole student list into step with the published timetable. expect: the counts {change, add, remove}
    the member was asked about (an older page sends none); when they no longer hold nothing is written"""
    body = request.get_json(force=True, silent=True)
    expect = None
    if isinstance(body, dict) and "expect" in body:
        e = body["expect"]
        if not (isinstance(e, dict) and all(type(e.get(k)) is int for k in ("change", "add", "remove"))):
            return {"error": "Check the numbers and press Update again."}, 400
        expect = {k: e[k] for k in ("change", "add", "remove")}
    out = students.update_all(by(), expect=expect)
    if out is None: return {"error": "No timetable is published yet."}, 409
    if out.get("changed"):
        return {"error": "The list or the published timetable changed. Check the numbers and press Update again.", "status": students.status()}, 409
    return jsonify(outcome=out, status=students.status())

@app.get("/api/setup/copies")
@need("committee")
def get_setup_copies():
    return jsonify(store.copies())

@app.post("/api/setup/restore")
@need("committee")
def restore_setup():
    body = request.get_json(force=True, silent=True)
    try: return store.restore(str((body or {}).get("id") or ""), by=by())
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

def _draft_entry(what, text, where="Step 8 · Upload and edit", kind="draft"):
    """one history entry for step 8 or 9 (call after the action worked). A failure to write it never fails the action"""
    e = {"kind": kind, "what": what, "where": where, "text": text, "link": "/", **by()}
    try: history.add(e)
    except Exception as x: print(f"WARNING: a timetable change could not be recorded in the history ({type(x).__name__})", file=sys.stderr, flush=True)

def _worked(r):
    return not isinstance(r, tuple) and getattr(r, "status_code", 200) == 200

@app.post("/api/draft")
@need("committee")
def draft_upload():
    """a timetable made outside the app (the skill with an AI agent, or another program) becomes the draft: kept on the
    server and checked against the saved setup. The draft it replaces is kept as a version (replace=1 is still accepted and ignored)."""
    spec, _ = store.load_setup()
    if not spec: return {"error": NO_SETUP}, 409
    work = tempfile.mkdtemp(prefix="tt-")
    try:
        try:
            sp, tp = _save_uploads(work)
            name = os.path.basename(str(request.files["timetable"].filename or "").replace("\\", "/"))[:120] or "an uploaded file"
            got = {}
            m = draft.save(sp, tp, name, spec, by=by()["as"], out=got)
            kept = got.get("kept")
        except ValueError as e: return {"error": str(e)}, 400
        r = _checked(lambda: dict(draft.info(model=m), kept=kept))
        if _worked(r): _draft_entry("upload", f"Uploaded {name}" + (f"; the draft before is kept as version “{kept['name']}”" if kept else ""))
        return r
    finally: shutil.rmtree(work, ignore_errors=True)

@app.get("/api/draft")
@need("committee")
def draft_get():
    return _checked(lambda: draft.info() or {"draft": None})

@app.post("/api/draft/decide")
@need("committee")
def draft_decide():
    body = request.get_json(force=True, silent=True); body = body if isinstance(body, dict) else {}
    key = str(body.get("key") or "")
    try:
        try: w = next((w for w in (draft.info() or {}).get("warnings", []) if w.get("key") == key), None)
        except Exception: w = None
        uid = body.get("upload_id"); out = jsonify(draft.decide(key, body.get("answer"), by=by(), upload_id=uid if isinstance(uid, str) else None))
        _draft_entry("decide", f"Decided: {body.get('answer')} — {w['text'] if w else key}")
        return out
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
    """one place a lesson may be dropped on, judged with a place beside, and the collisions there listed (nothing is changed)"""
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
    body = request.get_json(force=True, silent=True); r = _checked(lambda: draft.fix(body, stamp=_stamp_of(body)), sentences=True)
    if _worked(r): _draft_entry("fix", draft.last_fix_text() or "A fix")
    return r

@app.post("/api/draft/undo")
@need("committee")
def draft_undo():
    was = draft.last_batch_texts(); r = _checked(draft.undo, sentences=True)   # read before: the undo drops the newest fix and its batch
    if _worked(r): _draft_entry("undo", f"Undid: {(was or [None])[0]}" if len(was) <= 1 else f"Undid {len(was)} fixes: " + "; ".join(t or "" for t in was))
    return r

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
    r = _checked(lambda: draft.fix_many(_posted_fixes(), stamp=_stamp_of(request.get_json(force=True, silent=True))), sentences=True)
    if _worked(r):
        ts = draft.last_batch_texts(); _draft_entry("fix", (f"{len(ts)} fixes: " if len(ts) != 1 else "1 fix: ") + "; ".join(t or "" for t in ts))
    return r

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

def _version_error(e):
    """a ValueError from versions.* as a sentence: 404 for a version that is not there, else 400"""
    return {"error": str(e)}, (404 if str(e) == "There is no such version." else 400)

@app.get("/api/draft/versions")
@need("committee")
def draft_versions():
    """the saved versions of the draft, newest first, with the draft's own counts and the published timetable's"""
    try:
        j = draft.info(); summary = None
        if j: summary = dict(source=j.get("source"), fixes=len(j.get("fixes") or []), critical=j["critical"], warnings=sum(1 for w in j["warnings"] if not w.get("decision") and not w.get("crit")))
        return jsonify(versions=versions.listing(), draft=summary, published=compare.published_counts())
    except LookupError: return {"error": NO_SETUP}, 409
    except Exception as e:
        app.logger.exception("listing the versions"); return {"error": f"Could not list the versions: {e}"}, 400

@app.post("/api/draft/versions")
@need("committee")
def draft_version_save():
    body = request.get_json(force=True, silent=True); body = body if isinstance(body, dict) else {}
    try: v = versions.save(body.get("name"), by()["as"])
    except ValueError as e: return _version_error(e)
    _draft_entry("version", f"Saved version “{v['name']}”")
    return jsonify(v)

@app.post("/api/draft/versions/<vid>/open")
@need("committee")
def draft_version_open(vid):
    try: got = versions.open_version(vid, by()["as"])
    except ValueError as e: return _version_error(e)
    kept, opened = got["kept"], got["opened"]
    _draft_entry("version", f"Opened version “{opened['name']}”" + (f"; the draft before is kept as version “{kept['name']}”" if kept else ""))   # the version is the draft now, whatever the check below says
    r = _checked(lambda: dict(info=draft.info() or {"draft": None}, kept=kept, opened=opened))
    return r if _worked(r) else (dict(r[0], kept=kept, opened=opened), r[1])

@app.delete("/api/draft/versions/<vid>")
@need("committee")
def draft_version_delete(vid):
    try: v = versions.delete(vid)
    except ValueError as e: return _version_error(e)
    _draft_entry("version", f"Deleted version “{v['name']}”")
    return jsonify(deleted=v)

@app.get("/api/draft/versions/<vid>/download")
@need("committee")
def draft_version_download(vid):
    """a saved version as a timetable database, like the draft's own download"""
    from ttgen.export import safe_name
    try: f = versions.folder(vid); name = versions._read(vid)["name"]
    except (ValueError, TypeError): return {"error": "There is no such version."}, 404
    work = tempfile.mkdtemp(prefix="tt-")
    try:
        try: path = os.path.join(work, "version.sqlite"); draft.database(path, folder=f)
        except draft.NotPlaced as e: return {"error": str(e), "unplaced": e.count}, 409
        except LookupError: return {"error": NO_SETUP}, 409
        except Exception as e:
            app.logger.exception("downloading a version"); return {"error": f"Could not make the file: {e}"}, 400
        with open(path, "rb") as fh: data = io.BytesIO(fh.read())
        return send_file(data, as_attachment=True, download_name=safe_name(name) + " - version.sqlite", mimetype="application/vnd.sqlite3")
    finally: shutil.rmtree(work, ignore_errors=True)

# ------------------------------------------------------------------------------------------------ Re-fit: the job
REFIT_DEAD_S = 600       # a running job older than this counts as dead: a new request starts over, and the old thread's answer is dropped
REFIT_FAILED = "The re-fit could not be worked out. Run Re-fit again."
REFIT_STALE = "The draft changed since this list was made. Run Re-fit again."
REFIT_GONE = "That re-fit list is gone. Run Re-fit again."
REFIT_UNCHECKED = "The re-fit was made, but the timetable could not be checked. Open step 8 again."
REFIT_LOCK = threading.Lock()   # guards REFIT only: never held while draft's or store's functions run, and they are never called from under it
REFIT = dict(state="idle")      # the one job: id, state (idle, running, done, failed), done, total, plan (with its raw fixes: the server's own), error, started, thread (kept for the tests)

def _refit_reset():
    """the job is idle (the caller holds REFIT_LOCK)"""
    REFIT.clear(); REFIT.update(state="idle")

def _refit_clear():
    with REFIT_LOCK: _refit_reset()

def _refit_live(job):
    """whether a job (a copy of REFIT, or REFIT under its lock) is running and not yet counted as dead"""
    return job.get("state") == "running" and time.monotonic() - job["started"] < REFIT_DEAD_S

def _refit_set(jid, **kw):
    """change the job, only while it is still the one with this id and running (a thread whose job was replaced writes nothing)"""
    with REFIT_LOCK:
        if REFIT.get("id") != jid or REFIT.get("state") != "running": return False
        REFIT.update(kw); return True

def _fault(what, e):
    """log what was being done and the error's type and last frame (file:line) only: the text of an error may hold a name from the timetable, and so may its traceback's arguments"""
    frames = list(traceback.walk_tb(e.__traceback__)); where = f"{os.path.basename(frames[-1][0].f_code.co_filename)}:{frames[-1][1]}" if frames else "?"
    app.logger.error("Re-fit: %s failed (%s at %s)", what, type(e).__name__, where)

def _refit_run(jid, given):
    """the thread of a job: the plan of the one model it was given, which it reads only (no lock of draft's is held while it searches)"""
    try:
        p = refit_plan.plan(*given, progress=lambda done, total: _refit_set(jid, done=done, total=total))
        _refit_set(jid, state="done", plan=dict(p, id=jid))
    except BaseException as e:
        _fault("the job", e); _refit_set(jid, state="failed", error=REFIT_FAILED)
    finally: _refit_set(jid, state="failed", error=REFIT_FAILED)   # a no-op unless the thread is leaving with the job still running

def _refit_text(t):
    """the history line of a re-fit that was made, from the plan's totals"""
    n = lambda k, one, many: f"{k} {one if k == 1 else many}"
    return f"Re-fit: {n(t['changes'], 'change', 'changes')} ({n(t['moved'], 'lesson moved', 'lessons moved')}, {t['another_day']} to another day, {n(len(t['typed']), 'typed rule', 'typed rules')} to check again)"

def _refit_name():
    """the name of the version kept before a re-fit: "Before re-fit, 22 Nov 1.12 pm" """
    day, _, at = versions.when(store.now()).partition(", ")
    return f"Before re-fit, {' '.join(day.split()[:2])} {at}"

@app.post("/api/draft/refit")
@need("committee")
def draft_refit_start():
    """start working out a re-fit of the draft in a thread (one at a time); the page polls GET"""
    with REFIT_LOCK: busy = _refit_live(REFIT)
    if busy: return {"error": "A re-fit is already running."}, 409
    try:
        m, rec, fx = draft._now(); decisions = draft.decisions_now(); ws = draft.listed(m, fx, decisions)["warnings"]   # one model, for the check and the thread
    except draft.NoDraft as e: return {"error": str(e)}, 404
    except Exception as e:
        if type(e) is LookupError: return {"error": NO_SETUP}, 409
        _fault("starting it", e); return {"error": "The re-fit could not be started. Run Re-fit again."}, 400
    if not refit.needed(ws): return {"error": "Nothing to re-fit: the timetable fits the setup."}, 400
    jid = secrets.token_hex(6); t = threading.Thread(target=_refit_run, args=(jid, (m, rec, fx, decisions, ws)), daemon=True); error = None
    with REFIT_LOCK:
        if _refit_live(REFIT): return {"error": "A re-fit is already running."}, 409
        REFIT.clear(); REFIT.update(id=jid, state="running", done=0, total=None, plan=None, error=None, started=time.monotonic(), thread=t)
        try: t.start()
        except Exception as e: _refit_reset(); error = e   # a thread that cannot be started leaves the job idle
    if error: _fault("starting its thread", error); return {"error": "The re-fit could not be started. Run Re-fit again."}, 400
    return {"id": jid, "started": True}

def _refit_stale(plan):
    """whether the draft is not the one the plan was made for (true when that cannot be told)"""
    try: return not draft.exists() or plan["stamp"] != draft.stamp()
    except Exception: return True

def _refit_shown(p):
    """a plan as the page gets it: the same without the raw fixes (the list's and each step's)"""
    groups = [dict(g, steps=[{f: x for f, x in s.items() if f != "fix"} for s in g["steps"]]) for g in p["groups"]]
    return {k: v for k, v in dict(p, groups=groups).items() if k != "fixes"}

@app.get("/api/draft/refit")
@need("committee")
def draft_refit_get():
    """the job as the page polls it: no raw fixes, only what the page shows (groups with the text of each step, also, needs, totals, late, seconds). A running job past its time is told as failed, so the page stops polling"""
    with REFIT_LOCK: job = dict(REFIT)
    if job["state"] == "idle": return {"state": "idle"}
    if job["state"] == "running" and not _refit_live(job): job.update(state="failed", error=REFIT_FAILED)
    out = {k: job.get(k) for k in ("state", "id", "done", "total", "error")}
    if job["state"] == "done": out.update(plan=_refit_shown(job["plan"]), stale=_refit_stale(job["plan"]))
    return jsonify(out)

def _refit_plan_of(jid):
    """the plan of the done job with this id, or None"""
    with REFIT_LOCK: return REFIT["plan"] if REFIT.get("state") == "done" and isinstance(jid, str) and jid == REFIT.get("id") else None

@app.get("/api/draft/refit/preview")
@need("committee")
def draft_refit_preview():
    """what the stored list would do (draft.preview of it, written nowhere): 404 when the id is not the done job's, the stale sentence when the draft has moved on or cannot be read"""
    p = _refit_plan_of(request.args.get("id"))
    if p is None: return {"error": REFIT_GONE}, 404
    if _refit_stale(p): return {"error": REFIT_STALE}, 400
    try: return jsonify(draft.preview(list(p["fixes"]), many=True))
    except ValueError as e: return {"error": str(e)}, 400
    except Exception as e:
        if isinstance(e, draft.NoDraft) or type(e) is LookupError: return {"error": REFIT_STALE}, 400
        _fault("the preview", e); return {"error": "The preview could not be made. Run Re-fit again."}, 400

@app.post("/api/draft/refit/apply")
@need("committee")
def draft_refit_apply():
    """make the stored list (never one the page sent): the job is taken out first, so a second click finds it gone, and put back when the apply is refused (before or in
    the writes). Once draft.refit_apply has returned the re-fit is made: it is recorded in the history, the job stays gone, and a check of the timetable that fails is told as such"""
    body = request.get_json(force=True, silent=True); jid = body.get("id") if isinstance(body, dict) else None
    with REFIT_LOCK:
        if not (REFIT.get("state") == "done" and isinstance(jid, str) and jid == REFIT.get("id")): return {"error": REFIT_GONE}, 404
        if not REFIT["plan"]["fixes"]: return {"error": "There is nothing to apply."}, 400
        job = dict(REFIT); _refit_reset()
    def refused(text, status):
        with REFIT_LOCK:
            if REFIT.get("state") == "idle": REFIT.clear(); REFIT.update(job)   # unless a new job has started since
        return {"error": text}, status
    p = job["plan"]
    if _refit_stale(p): return refused(REFIT_STALE, 400)   # also when there is no draft or no setup
    try: out = draft.refit_apply(list(p["fixes"]), p["stamp"], _refit_name(), by()["as"])
    except ValueError as e: return refused(REFIT_STALE if str(e) == draft.MOVED else str(e), 400)
    except Exception as e:
        if isinstance(e, draft.NoDraft) or type(e) is LookupError: return refused(REFIT_STALE, 400)
        _fault("making it", e); return refused("The re-fit could not be made. Run Re-fit again.", 400)
    _draft_entry("refit", _refit_text(p["totals"])); made = dict(kept=out["kept"], changes=len(p["fixes"]))
    try: return jsonify(info=draft.info() or {"draft": None}, **made)
    except Exception as e:
        _fault("checking the timetable after it", e); return dict(made, error=REFIT_UNCHECKED), (409 if type(e) is LookupError else 400)

# ------------------------------------------------------------------------------------------------ the Compare page
@app.get("/compare")
@need("committee")
def compare_page():
    return app.send_static_file("compare.html")

def _compare_sources():
    """the pickers of the Compare page: the draft (when there is one), every version newest first, the published timetable (when there is one)"""
    out = [dict(src="draft", label=compare.label("draft"))] if draft.exists() else []
    out += [dict(src="v:" + v["id"], label=versions.label(v)) for v in versions.listing(counts=False)]
    if store.published(): out.append(dict(src="published", label=compare.label("published")))
    return out

def _compare_error(e):
    """404 for a version that is not there, 400 for any other sentence, 409 without a setup; a compare that goes wrong is a sentence too (400), as _checked does, never a server error"""
    if type(e) is LookupError: return {"error": NO_SETUP}, 409   # no setup saved (a KeyError or IndexError is a fault in the compare)
    if isinstance(e, ValueError): return {"error": str(e)}, 404 if str(e) == compare.NO_VERSION else 400
    app.logger.exception("comparing two timetables"); return {"error": f"Could not compare the timetables: {e}"}, 400

def _compare_pair():
    """(a, b) from the query: b is the draft unless given; a is the first picker entry that is not b"""
    b = request.args.get("b") or "draft"; a = request.args.get("a")
    if not a:
        a = next((s["src"] for s in _compare_sources() if s["src"] != b), None)
        if not a: raise ValueError("There is nothing to compare with yet.")
    return a, b

def _involves(row, view, name):
    if row is None: return False
    return name in row["classes"] if view == "class" else name in row["teachers"] if view == "teacher" else row["room"] == name

@app.get("/api/compare")
@need("committee")
def api_compare():
    """two timetables side by side: ?a=&b=&view=class|teacher|room&name=. The totals, the pickers, the week of the chosen class, teacher or room on
    each side with the cells that take part in a difference (`marks`, [day, period]) and a sentence for each difference that involves it (`lines`)"""
    rec = store.setup_record()
    try:
        a, b = _compare_pair(); la, lb = compare.label(a), compare.label(b); d, ma, mb = compare.both(a, b, rec)
    except Exception as e: return _compare_error(e)
    view = request.args.get("view") or "class"; name = request.args.get("name")
    if view not in ("class", "teacher", "room"): return {"error": compare.NO_NAME}, 400
    names = d["names"][{"class": "classes", "teacher": "teachers", "room": "rooms"}[view]]
    if not name:
        name = next((n for n in names if any(_involves(i["a"], view, n) or _involves(i["b"], view, n) for i in d["items"])), names[0] if names else None)
    if name not in names: return {"error": compare.NO_NAME}, 400
    try:
        weeks = {}
        for k, m in (("a", ma), ("b", mb)):
            try: weeks[k] = compare.week(m, view, name)
            except ValueError as e:
                if str(e) != compare.NO_NAME: raise
                weeks[k] = None   # the name is on the other timetable only
    except Exception as e: return _compare_error(e)
    have = weeks["a"] or weeks["b"]
    if have is None: return {"error": compare.NO_NAME}, 400
    for k in ("a", "b"):
        if weeks[k] is None: weeks[k] = dict(have, cells=[])
    mine = [i for i in d["items"] if _involves(i["a"], view, name) or _involves(i["b"], view, name)]
    marks = {k: [] for k in "ab"}
    for i in mine:
        for k in "ab":
            r = i[k]
            if _involves(r, view, name) and [r["d"], r["p"]] not in marks[k]: marks[k].append([r["d"], r["p"]])
    return jsonify(a=dict(src=a, label=la), b=dict(src=b, label=lb), sources=_compare_sources(), totals=d["totals"], names=d["names"], view=view, name=name,
                   weeks=weeks, marks=marks, lines=list(dict.fromkeys(compare.line(i, d["days"]) for i in mine)))

@app.get("/api/compare.xlsx")
@need("committee")
def api_compare_xlsx():
    from ttgen.export import safe_name
    try:
        a, b = _compare_pair(); la, lb = compare.name(a), compare.name(b); data = compare.xlsx(a, b, store.setup_record())
    except Exception as e: return _compare_error(e)
    return send_file(io.BytesIO(data), as_attachment=True, download_name=safe_name(f"Differences {la} and {lb}") + ".xlsx", mimetype=XLSX)

@app.post("/api/draft/publish")
@need("committee")
def draft_publish():
    try:
        got = draft.publish()
        _draft_entry("publish", "Published the timetable", "Step 9 · Publish")
    except FileNotFoundError: return {"error": "There is no draft to publish."}, 404
    except draft.Critical as e: return {"error": str(e), "critical": e.count}, 409
    except draft.NotPlaced as e: return {"error": str(e), "unplaced": e.count}, 409
    except LookupError: return {"error": NO_SETUP}, 409
    except ValueError as e: return {"error": f"Could not read the files: {e}"}, 400
    pub = store.published()
    if pub:      # a lesson that moved into (or out of) a duty or an event window goes to (or leaves) relief at once
        with exams_schedules.editing(): _relief_sync(pub)
    return jsonify(got)

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
                compared_v=m.get("compared_v", ""), open=m.get("open", 0), left=m.get("left", []), fixes=m.get("fixes", []),
                files_behind=bool(m.get("files_behind")))

def _group_label(p):
    """the committee page's label for a person: their role's label, then " · " and their committees' labels joined by
    ", " when they have any (Admin last), e.g. "HOD · Timetable committee, Relief team"
    """
    ex, today = p.get("extras") or {}, datetime.date.today().isoformat()
    on = [label for k, label in people.COMMITTEES if (bool(ex.get(k)) and str(ex[k]) >= today if k == "exams" else ex.get(k) is True)]
    if ex.get("admin") is True: on.append(EXTRA_LABELS["admin"])
    return " · ".join(x for x in (people.LABELS.get(p.get("group")), ", ".join(on)) if x) or None

@app.get("/api/status")
@need("setup")
def status():
    """what the committee page shows. who: the person signed in (None for a shared code), group: their role's and committees' label; depts: a head's departments
    when signed in by name (None otherwise); shared: the shared code's role; admin_exists: an admin who can sign in has been named (else the first admin is offered)"""
    have, probs = access.configured()
    _, at = store.load_setup()
    p = who()
    mine = dict(who=p["name"] if p else None, group=_group_label(p) if p else None, via=via(), depts=head_depts(), rights=sorted(rights()), shared=shared(),
                admin_exists=bool(people.usable_admins(people.load())))
    if not has("committee"): return jsonify(role="head", volume=store.on_volume(), setup_saved_at=at, published=pub_info(), **mine)
    return jsonify(role="committee", codes=have, code_problems=probs, volume=store.on_volume(), setup_saved_at=at, published=pub_info(), draft=draft.summary(), versions=versions.count(), typed=typed.enabled(), **mine)

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
@need("timetable")
def timetable():
    from ttgen.export import render_html
    pub = store.published()
    if not pub:
        return page("Timetable", "<main class='login'><h1>Not published yet</h1><p class='muted'>The timetable committee has not published the timetable yet. Please check again later.</p><p><a href='/logout'>Sign out</a></p></main>")
    # the committee sees every tab; the shared student code what a student sees; everyone else what a teacher sees, a
    # person with the way back to their tiles (a relief stage 1 session: to Relief). Each kept apart, by mode and way back
    if has("committee"): r, home, label = "committee", "/", "Committee page"
    elif shared() == "student": r, home, label = "student", None, None
    elif who() is None: r, home, label = "teacher", None, None
    elif _relief_stage_1() and has("relief"): r, home, label = "teacher", "/relief", "Relief"
    else: r, home, label = "teacher", "/home", "Home"
    key = ("view", r, home)
    if key not in pub["views"]:
        view = "student" if r == "student" else "full"
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
@need("own")
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
@need("own")
def pdf_me():
    from ttgen.export import student_view
    pub = store.published(); sid = session.get("sid")
    s = next((x for x in pub["model"]["students"] if x["id"] == sid), None) if pub else None
    if not s: abort(404)
    return _pdf(student_view(pub["model"], s), f"{s['name']} timetable")

@app.get("/pdf/custom")
@need("timetable")
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
@need("timetable")
def pdf_one(kind, key):
    from ttgen.export import class_view, teacher_view, room_view, student_view
    pub = store.published()
    if not pub: abort(404)
    m = pub["model"]
    if shared() == "student" and kind != "classes": abort(403)   # the shared student code: class timetables only
    if kind == "classes" and key in m["class_ix"]: return _pdf(class_view(m, key), f"Class {key}")
    if kind == "teachers" and key in m["teacher_ix"]: return _pdf(teacher_view(m, key), key)
    if kind == "rooms" and key in m["room_ix"]: return _pdf(room_view(m, key), f"Room {key}")
    if kind == "students":
        s = next((x for x in m["students"] if x["id"] == key), None)
        if s: return _pdf(student_view(m, s), f"{s['id']} {s['name']}")
    abort(404)

@app.get("/files/<what>")
@app.get("/files/<what>/<kind>")
@need("files")
def files(what, kind=None):
    pub = store.published()
    if not pub: abort(404)
    f = pub["meta"].get("files", {}); r = "committee" if has("committee") else "teacher"
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
    """the people relief and exams know: the published timetable's teachers and the staff added in the accounts, as
    name, short, depts (step 4's), role, teaches and staff_only only. Every reply to a page that is not the admin page
    uses this, never people.staff (which carries usernames, groups, extras and sign-ins)"""
    return people.listing(pub)

def _relief_depts(pub, p):
    """the departments relief shows for the person p (a staff item): a head's ticked ones, else step 4's. Relief keeps
    step 4's for a head with none ticked (the admin page shows them none, and they change no rows)"""
    if p["group"] in people.HEADS and p["depts"]: return list(p["depts"])
    return next((list(x["depts"]) for x in relief_staff(pub) if x["name"] == p["name"]), list(p["depts"]))

def move_relief_lists():
    """relief's own Management, Relief team and extra staff lists, and exams' committee list, move into the accounts, once
    each (a no-op after); never raises: a failure only prints one line"""
    try: return people.migrate(store.published(), store.read_json(relief_settings.PATH, {}), store.read_json(exams_settings.PATH, None))
    except Exception as e:
        print(f"WARNING: relief's lists or exams' committee list could not be moved into the accounts ({type(e).__name__})", file=sys.stderr, flush=True)
        return None

def _relief_rights(pub):
    """(may read the settings, may save them, saved by) for whoever is signed in; None for a person while nothing is
    published"""
    if has("committee"): return True, True, "Timetable committee"
    p = who()
    if p is None or not pub: return None
    return has("relief.settings"), has("relief.save"), by()["as"]

def _no_longer_valid():
    return page("Relief", "<main class='login'><h1>Code no longer valid</h1><p class='muted'>You are not on the published timetable or the relief staff list. Ask the timetable committee for your code.</p><p><a href='/login'>Back</a></p></main>")

@app.get("/relief")
@need("relief", "relief.settings")
def relief_home():
    if not has("relief"): return redirect("/relief/settings")   # the shared committee code: nobody's relief, its settings
    return app.send_static_file("relief.html")   # need() has checked the person is still there

@app.get("/api/relief/me")
@need("relief")
def relief_me():
    # relief's old lists move into the accounts here too (a no-op after the first run), so a relief team member has their
    # tabs on the first open; when they moved just now, the rights are worked out again from the records in this request
    if move_relief_lists(): g.pop("_signed", None)
    p = who()
    if p is None: return {"error": "Please sign in again."}, 401
    pub_ = store.published(); pub = bool(pub_)   # nothing published: a publish may be swapping folders, so no departments, but the person still answers
    return jsonify(name=p["name"], depts=_relief_depts(pub_, p) if pub else [], published=pub, on_team=bool(p["extras"].get("relief")), on_management=p["group"] in people.MANAGEMENT,
                   can_settings=has("relief.save"), can_plan=has("relief.plan"), can_team=has("relief.team"), today=relief_lessons.today().isoformat())

@app.get("/relief/settings")
@need("relief.settings")
def relief_settings_page():
    move_relief_lists()
    r = _relief_rights(store.published())
    if r is None: return _no_longer_valid()
    if r[1]: return app.send_static_file("relief-settings.html")
    return page("Relief settings", f"<main class='login'><h1>Relief settings</h1><p class='muted'>{esc(ONLY_SETTINGS)}</p><p><a href='/'>Back</a></p></main>"), 403

def _relief_lists(pub):
    """who is on management, on the relief team and added as extra staff, as the accounts say"""
    ps = people.staff(pub)
    return dict(management=[p["name"] for p in ps if p["group"] in people.MANAGEMENT], team=[p["name"] for p in ps if p["extras"].get("relief")],
                added=[p["name"] for p in ps if p["staff_only"]])

def _relief_settings_reply(pub, settings):
    m = pub["model"]; rights = _relief_rights(pub) or (False, False, None)
    lists = _relief_lists(pub)
    return jsonify(settings=settings, lists=lists, can_admin=has("admin"), people=relief_staff(pub), roles=relief_settings.role_names(pub), weeks=m["school"]["weeks"], can_save=rights[1], can_codes=has("codes"))

@app.get("/api/relief/settings")
@need("relief.settings")
def relief_settings_get():
    move_relief_lists()
    pub = store.published()
    if not pub: return {"error": NO_RELIEF_PUB}, 409
    rights = _relief_rights(pub)
    if rights is None: return {"error": "Please sign in again."}, 401
    if not rights[0]: return {"error": ONLY_SETTINGS}, 403
    return _relief_settings_reply(pub, relief_settings.load(pub))

@app.put("/api/relief/settings")
@need("relief.save")
def relief_settings_put():
    move_relief_lists()
    pub = store.published()
    if not pub: return {"error": NO_RELIEF_PUB}, 409
    rights = _relief_rights(pub)
    if rights is None: return {"error": "Please sign in again."}, 401
    if not rights[1]: return {"error": ONLY_SETTINGS}, 403
    try: saved = relief_settings.save(request.get_json(force=True, silent=True), pub, rights[2])
    except ValueError as e: return {"error": str(e)}, 400
    try: history.add({"kind": "relief", "what": "settings", "where": "Relief settings", "text": "Relief settings saved", "link": "/relief", **by()})
    except Exception as x: print(f"WARNING: relief settings could not be recorded in the history ({type(x).__name__})", file=sys.stderr, flush=True)
    return _relief_settings_reply(pub, saved)

def _relief_codes_refused():
    """the answer that refuses the staff codes to whoever is signed in, or None (the routes check what is published)"""
    if not has("codes"): return {"error": ONLY_CODES}, 403
    if not access.personal_codes_on(): return NO_PERSONAL_STAFF, 409
    return None

@app.get("/api/relief/codes.csv")
@need("codes")
def relief_codes_csv():
    refused = _relief_codes_refused(); pub = store.published()
    if refused: return refused
    if not pub: return NO_RELIEF_PUB, 409
    return Response(relief_codes.codes_csv(relief_staff(pub)), mimetype="text/csv", headers={"Content-Disposition": 'attachment; filename="personal relief codes.csv"'})

@app.get("/api/relief/code-slips.pdf")
@need("codes")
def relief_code_slips():
    """everyone's slips; ?names=a,b only those people's (the admin page's "Print their code slips")"""
    refused = _relief_codes_refused(); pub = store.published()
    if refused: return refused
    if not pub: return NO_RELIEF_PUB, 409
    ps = relief_staff(pub)
    if request.args.get("names") is not None:
        mine = {n.strip() for n in request.args["names"].split(",") if n.strip()}
        ps = [p for p in ps if p["name"] in mine]
        if not ps: return {"error": NO_ONE}, 400
    buf = io.BytesIO()
    relief_codes.slips_pdf(pub["model"]["school"]["name"], ps, request.host_url.rstrip("/"), buf)
    buf.seek(0)
    return send_file(buf, as_attachment=True, download_name="relief code slips.pdf", mimetype="application/pdf")

def _relief_entry(what, text, absence=None, who=None, via=None):
    """one history entry for a relief request's save (relief/web.py): who, what, which, a link (not field by field; relief
    keeps its own record, and the entry never holds the reason). who and via: the person who did it without a session (on
    Telegram), or via "app" for what the app did by itself (By "The app": no request, no session), else whoever is signed in. A
    failure to write it never fails the save"""
    e = {"kind": "relief", "what": what, "where": "Relief", "text": text, "link": "/relief", **(history.by_of(who, via) if who or via == "app" else by())}
    if absence: e["absence"] = absence
    try: history.add(e)
    except Exception as x: print(f"WARNING: a relief change could not be recorded in the history ({type(x).__name__})", file=sys.stderr, flush=True)

# relief requests: relief/web.py, every route through need(), every right through has(), every save in the history
relief_web.init(has=has, me=who, need=need, note=_relief_entry)
app.register_blueprint(relief_web.bp)
# Telegram: linking, connecting the bot, and the hook it posts to (relief/tgweb.py: the hook alone has no guard, it needs Telegram's secret header)
relief_tgweb.init(has=has, me=who, need=need, note=_relief_entry)
app.register_blueprint(relief_tgweb.bp)
relief_outbox.UNLINKED.append(lambda name: _relief_entry("telegram unlinked", f"Telegram unlinked for {name}: the bot was blocked", via="app"))   # from the sender's thread
relief_bot.at_start()                                             # what was typed in a Telegram conversation that has run out is deleted, whatever is on
if os.environ.get("RELIEF_JOBS") == "on":                         # relief picks when due, every minute (the Dockerfile sets it; tests and local runs never do)
    relief_fill.AFTER.append(relief_tell.sweep)                   # and then what there is to say on Telegram (nothing while the bot is off)
    relief_fill.start()
if os.environ.get("RELIEF_JOBS") == "on" and relief_tg.on():
    relief_tell.MINUTE.append(relief_tell.sweep)                  # what there is to say by the clock, every minute, whatever the picks are waiting for
    relief_tell.MINUTE.append(relief_report.tick)                 # and then the relief team's report of who has not acknowledged, and their weekly summary
    relief_tell.MINUTE.append(relief_morning.tick)                # and then the morning message to the people on duty, once a day
    relief_tell.MINUTE.append(relief_bot.forget)                  # and what was typed in a conversation that has run out is deleted
    relief_tell.start()
    relief_outbox.start()                                         # the Telegram messages, every 5 seconds

# ------------------------------------------------------------------------------------------------ admins: people and the ways in
# The named admins (Timetable committee tick, Admin extra, signed in with their password) manage people here; every check is the
# server's. A change is judged whole inside one people.update, so two admins at once cannot both remove the other, and a
# refused change writes nothing. Any change to a person's rights (their role, the departments they change, a committee or extra
# given or taken away), switching them off or on, a username changed or removed, and a password reset raise their
# sign-in number `n`, so they are signed out everywhere (the design: "changing their rights signs them out everywhere at
# once", a gain as well as a loss); a note or a first username does not. Each change is one history entry, `changes`
# [{name, field, was, now}], never a password, recorded under who made it as they were before it (their own change may
# end their session).
PICK_GROUP = "Pick a role."
ONLY_COMMITTEE_ADMIN = "Only the timetable committee can be admins."
LAST_ADMIN = "{} is the last admin: make another admin first."
EXAMS_UNTIL = "Give the last day of the exams and events access."
BAD_USERNAME = "A username is 3 to 40 letters, digits, dots, dashes or underscores."
TAKEN = "That username is taken."
NOT_A_DEPT = "{} is not one of the school's departments."
NOT_STAFF = "{} is not on the published timetable or the staff list."
NAMELESS = "A staff member needs a name."
FORMULA_NAME = "A name cannot start with {}."
LONG_NAME = "Keep a name under 100 characters."
ON_TIMETABLE = "{} is already a teacher on the timetable."
ON_STAFF = "{} is already on the staff list."
LONG_NOTE = "Keep a note under 200 characters."
NO_ONE = "Tick at least one person."
PICK_ACTION = "Pick what to do."
PICK_EXTRA = "Pick an extra."
NO_USERNAME = "Give them a username first."
PICK_SHARED = "Pick a shared code."
UNREAD_CHANGE = "The change could not be read. Reload the page and try again."
FIRST_ADMIN = "Make the first admin"
HAS_PASSWORD = "{} has a password already: they make themselves the first admin, signed in with it."
REMOVE_ON_TIMETABLE = "{} is on the published timetable, so they cannot be removed: they would come straight back. Switch them off instead."
REMOVE_SELF = "You cannot remove yourself."
REMOVE_UNLINK = "Their Telegram chat could not be unlinked, so nothing was removed. Try again."
REMOVED = "{} is removed. What they changed stays in the History."
EXTRA_LABELS = {"timetable": "Timetable committee", "relief": "Relief team", "exams": "Exams and events", "admin": "Admin"}
SIGNS_OUT = {"group", "depts", "timetable", "relief", "exams", "admin", "off"}   # and a username changed or removed
_USERNAME = re.compile(r"[a-z0-9._-]{3,40}")
_ISO_DAY = re.compile(r"\d{4}-\d{2}-\d{2}")

class Refused(Exception):
    """one check's sentence: the whole change is refused and nothing is written"""

def _admin_off():
    """the admin calls are refused while SECRET_KEY is not set (accounts are off)"""
    return ({"error": NO_ACCOUNTS}, 403) if not accounts_on() else None

def _body():
    b = request.get_json(force=True, silent=True)
    if not isinstance(b, dict): raise Refused(UNREAD_CHANGE)
    return b

def school_depts():
    """the departments of the school in the setup being edited; [] with no setup"""
    spec = store.setup_record()["spec"]
    school = spec.get("school") if isinstance(spec, dict) else None
    d = school.get("departments") if isinstance(school, dict) else None
    return [x.strip() for x in d if isinstance(x, str) and x.strip()] if isinstance(d, list) else []

def _name_problem(name):
    """relief's checks of a typed name (the codes CSV is opened in a spreadsheet): the sentence, or None"""
    if not name: return NAMELESS
    if name[0] in relief_settings.FORMULA: return FORMULA_NAME.format(name[0])
    if len(name) > 100: return LONG_NAME
    return None

def _username(v):
    """a username as typed -> as kept (lower case); None when none is given"""
    if v is None or (isinstance(v, str) and not v.strip()): return None
    u = v.strip().lower() if isinstance(v, str) else ""
    if not _USERNAME.fullmatch(u): raise Refused(BAD_USERNAME)
    return u

def _taken(d, u, name):
    """another person's record holds this username (compared ignoring case)"""
    return bool(u) and any(n != name and isinstance(r, dict) and str(r.get("username") or "").lower() == u for n, r in d["people"].items())

def _until(v, today):
    """an Exams and events end date: an ISO date, today or later; None or False takes the extra away"""
    if v is None or v is False: return None
    try: d = datetime.date.fromisoformat(v.strip()) if isinstance(v, str) and _ISO_DAY.fullmatch(v.strip()) else None
    except ValueError: d = None
    if d is None or d < today: raise Refused(EXAMS_UNTIL)
    return d.isoformat()

def _wanted(b, today):
    """the fields of one person the body sets, each checked on its own -> {field: value}"""
    want = {}
    if "group" in b:
        if b["group"] not in people.GROUPS: raise Refused(PICK_GROUP)
        want["group"] = b["group"]
    if "depts" in b:
        if not isinstance(b["depts"], list) or not all(isinstance(x, str) for x in b["depts"]): raise Refused(UNREAD_CHANGE)
        school, got = school_depts(), []
        for x in (x.strip() for x in b["depts"]):
            if x and x not in got:
                if x not in school: raise Refused(NOT_A_DEPT.format(x))
                got.append(x)
        want["depts"] = got
    if "extras" in b:
        ex = b["extras"]
        if not isinstance(ex, dict) or any(not isinstance(ex[k], bool) for k in ("timetable", "relief", "admin") if k in ex): raise Refused(UNREAD_CHANGE)
        want.update({k: ex[k] for k in ("timetable", "relief", "admin") if k in ex})
        if "exams" in ex: want["exams"] = _until(ex["exams"], today)
    if "username" in b: want["username"] = _username(b["username"])
    if "note" in b:
        if b["note"] is not None and not isinstance(b["note"], str): raise Refused(UNREAD_CHANGE)
        want["note"] = (b["note"] or "").strip()
        if len(want["note"]) > 200: raise Refused(LONG_NOTE)
    if "off" in b:
        if not isinstance(b["off"], bool): raise Refused(UNREAD_CHANGE)
        want["off"] = b["off"]
    return want

def _change(d, name, item, want):
    """make `want` true of name's record in d. item: their staff item before the change (None: they are being added).
    -> the changes [{name, field, was, now}] against what they have now; nothing that is so already"""
    r, out, want = people.record(d, name), [], dict(want)
    def put(field, was, now): out.append(dict(name=name, field=field, was=copy.deepcopy(was), now=copy.deepcopy(now)))
    if item is None and not r["added"]: r["added"] = True; put("added", False, True)
    group = item["group"] if item else (r["group"] or "executive")
    if "group" in want and want["group"] != group:
        put("group", group, want["group"]); r["group"] = want["group"]
        if want["group"] in people.HEADS and not r["depts"] and "depts" not in want and item and item["depts"]:
            want["depts"] = list(item["depts"])                      # a new head changes the map for their step-4 departments
    if want.get("timetable") is False and "admin" not in want: want["admin"] = False   # the Admin extra is the committee's
    if "depts" in want and want["depts"] != r["depts"]: put("depts", r["depts"], want["depts"]); r["depts"] = list(want["depts"])
    for k in ("timetable", "relief", "exams", "admin"):
        if k in want and want[k] != r["extras"][k]: put(k, r["extras"][k], want[k]); r["extras"][k] = want[k]
    if "username" in want and want["username"] != r["username"]:
        put("username", r["username"], want["username"]); r["username"] = want["username"]
        if not r["username"]: r.update(pw=None, must_change=False)   # no username, no password: a later username starts without one
    if "note" in want and want["note"] != r["note"]: put("note", r["note"], want["note"]); r["note"] = want["note"]
    if "off" in want and want["off"] != r["off"]: put("off", r["off"], want["off"]); r["off"] = want["off"]
    if any(c["field"] in SIGNS_OUT or (c["field"] == "username" and c["was"]) for c in out): r["n"] += 1
    if out: d["people"][name] = r
    return out

def _whole(d, touched, before):
    """the checks of a change as a whole, on d as it leaves it: Admin only with the Timetable committee tick, and an admin left who can
    sign in (an Admin with no username or password, or switched off, keeps no one in). before: people.usable_admins
    before the change"""
    for n in touched:
        r = people.record(d, n)
        if r["extras"]["admin"] and not r["extras"]["timetable"]: raise Refused(ONLY_COMMITTEE_ADMIN)
    if not people.usable_admins(d):
        raise Refused(LAST_ADMIN.format(next((n for n in touched if n in before), before[0] if before else touched[0])))

def _admin_item(pub, data, name):
    """one person as the admin page shows them: their staff item and their note; None when not on the staff list"""
    p = next((p for p in people.staff(pub, data) if p["name"] == name), None)
    return _with_gives(p, data) if p else None

def _with_gives(p, data):
    """a staff item with its note, what its role and committees give (worked out by the rights themselves) and whether they have a strong sign-in"""
    rec = people.record(data, p["name"])
    return dict(p, note=rec["note"], gives=rights_table.gives(p, p["depts"]), strong=bool(p["has_password"] or rec["google"]))

def _said(c):
    f, was, now = c["field"], c["was"], c["now"]
    if f == "added": return "added to the staff list"
    if f == "group": return f"role {people.LABELS.get(was, was)} → {people.LABELS.get(now, now)}"
    if f == "depts": return "changes the map for " + (", ".join(now) or "no department")
    if f == "exams": return f"Exams and events until {_day(now)}" if now else "Exams and events taken away"
    if f in ("timetable", "relief", "admin"): return f"{EXTRA_LABELS[f]} {'given' if now else 'taken away'}"
    if f == "username": return f"username {now}" if now else "username and password removed"
    if f == "note": return "note changed"
    return "switched off" if now else "switched on"

def _what(out):
    """the kind of a change to one person, by its weightiest field"""
    fields = [c["field"] for c in out]
    if "added" in fields: return "add"
    if "off" in fields: return "off" if next(c for c in out if c["field"] == "off")["now"] else "on"
    for f, what in (("group", "group"), ("timetable", "extras"), ("relief", "extras"), ("exams", "extras"), ("admin", "extras"), ("depts", "depts"), ("username", "username")):
        if f in fields: return what
    return "note"

def _account_entry(what, names, changes, text, by_=None, **more):
    """one kind-account entry; a change is never undone for want of its entry"""
    try: history.add({"kind": "account", "what": what, "where": "Admin", "people": names, "changes": changes, "text": text, **more, **(by_ or by())})
    except Exception as e: print(f"WARNING: an account change could not be recorded in the history ({type(e).__name__})", file=sys.stderr, flush=True)

def _update_as(me, fn):
    """people.update(fn) for the admin `me` -> fn's result. Their own change signs out their other sessions, not this
    one: the new number is read inside the update, and kept only when this session's number was still theirs as the
    update began (so a sign-out by another admin at the same moment is never undone) and they are not switched off"""
    held = session.get("n", 0)
    def run(d):
        n0 = people.record(d, me)["n"]
        out = fn(d)
        r = people.record(d, me)
        return out, (r["n"] if n0 == held and r["n"] != n0 and not r["off"] else None)
    out, keep = people.update(run)
    if keep is not None: session["n"] = keep
    return out

def _and(names):
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]

_BULK_SAY = {("give", "timetable"): (("joins", "join"), "the Timetable committee", "{} is on the Timetable committee already."),
             ("give", "relief"): (("joins", "join"), "the relief team", "{} is on the relief team already."),
             ("give", "admin"): (("gets", "get"), "the admin page", "{} is an admin already."),
             ("take", "timetable"): (("leaves", "leave"), "the Timetable committee", "{} is not on the Timetable committee."),
             ("take", "relief"): (("leaves", "leave"), "the relief team", "{} is not on the relief team."),
             ("take", "exams"): (("loses", "lose"), "the exams and events pages", "{} does not have the exams and events pages."),
             ("take", "admin"): (("loses", "lose"), "the admin page", "{} is not an admin.")}

def _bulk_lines(act, key, val, names, done, d):
    """what a change to several people does, naming each person and anything already so ("their" for everyone)"""
    moved, same = [n for n in names if done[n]], [n for n in names if not done[n]]
    def verb(one, many): return one if len(moved) == 1 else many
    def had(n, f): return next((c["was"] for c in done[n] if c["field"] == f), None)
    lines = []
    if act == "give" and key == "exams":
        if moved: lines.append(f"{_and(moved)} {verb('gets', 'get')} the exams and events pages until {_day(val)}.")
        lines += [f"{n} has it already: their end date moves to {_day(val)}." for n in moved if had(n, "exams")]
        lines += [f"{n} has it already, until {_day(val)}: nothing changes for them." for n in same]
    elif act in ("give", "take"):
        verbs, what, already = _BULK_SAY[(act, key)]
        if moved: lines.append(f"{_and(moved)} {verb(*verbs)} {what}.")
        if act == "take" and key == "timetable":
            lines += [f"{n} stops being an admin: only the timetable committee can be admins." for n in moved if had(n, "admin")]
        lines += [already.format(n) for n in same]
    elif act == "group":
        label = people.LABELS[val]
        if moved: lines.append(f"The role of {_and(moved)} becomes {label}.")
        for n in moved:
            if val in people.HEADS:
                ds = people.record(d, n)["depts"]
                if not ds: lines.append(f"{n} has no department on step 4: tick their departments on their panel, or they can change no rows.")
                else: lines.append(f"{n} changes the map for {', '.join(ds)}{' (from step 4)' if any(c['field'] == 'depts' for c in done[n]) else ''}.")
        lines += [f"{n} is {label} already." for n in same]
    elif act == "off":
        if moved: lines.append(f"{_and(moved)} {verb('is', 'are')} switched off and signed out everywhere.")
        lines += [f"{n} is switched off already." for n in same]
    else:
        if moved: lines.append(f"{_and(moved)} can sign in again.")
        lines += [f"{n} is not switched off." for n in same]
    return lines

def _bulk(d, pub, b, today):
    """one change for every ticked person, made on d -> dict(lines, touched, changes, what, text). The preview runs it
    on a copy of the records and the apply inside people.update, so the preview's lines are what the apply does"""
    names = b.get("names")
    if not isinstance(names, list) or not all(isinstance(n, str) for n in names): raise Refused(UNREAD_CHANGE)
    names = list(dict.fromkeys(names))
    if not names: raise Refused(NO_ONE)
    act = b.get("action")
    if act not in ("give", "take", "group", "off", "on"): raise Refused(PICK_ACTION)
    if act in ("give", "take"):
        key = b.get("extra")
        if not isinstance(key, str) or key not in EXTRA_LABELS: raise Refused(PICK_EXTRA)
        if key != "exams": val = act == "give"
        elif act == "take": val = None
        elif b.get("until") is None or b.get("until") is False: raise Refused(EXAMS_UNTIL)
        else: val = _until(b["until"], today)
    elif act == "group":
        if b.get("group") not in people.GROUPS: raise Refused(PICK_GROUP)
        key, val = "group", b["group"]
    else: key, val = "off", act == "off"
    items = {p["name"]: p for p in people.staff(pub, d)}
    for n in names:
        if n not in items: raise Refused(NOT_STAFF.format(n))
    before = people.usable_admins(d)
    done = {n: _change(d, n, items[n], {key: val}) for n in names}
    touched = [n for n in names if done[n]]
    if touched: _whole(d, touched, before)
    them = ", ".join(touched)
    text = {"give": lambda: f"Gave {EXTRA_LABELS[key]}{' until ' + _day(val) if key == 'exams' else ''} to {them}",
            "take": lambda: f"Took away {EXTRA_LABELS[key]} from {them}", "group": lambda: f"Set the role of {them} to {people.LABELS[val]}",
            "off": lambda: f"Switched off {them}", "on": lambda: f"Switched on {them}"}[act]()
    return dict(lines=_bulk_lines(act, key, val, names, done, d), touched=touched, changes=[c for n in touched for c in done[n]],
                what="extras" if act in ("give", "take") else act, text=text)

def _ways():
    data, (have, _) = people.load(), access.configured()
    recs = [people.record(data, n) for n in data["people"]]
    return dict(secret_key=accounts_on(), personal_codes=access.personal_codes_on(), password_accounts=sum(1 for r in recs if r["username"] and r["pw"]),
                shared=[dict(code=x, set=bool(have.get(x)), off=data["ways"]["off"].get(x), used_week=history.uses(kind="signin", via="shared", shared=x, ok=True))
                        for x in people.SHARED],
                recovery_set=bool(recovery_code()), recovery_short=recovery_too_short(),
                recovery_warn=RECOVERY_SHORT if recovery_too_short() else RECOVERY_ON if recovery_code() else None)

# ------------------------------------------------------------------------------------------------ the history page
HISTORY_MAX = 500
_SAFE_LINK = re.compile(r"^/(?![/\\\s])")   # a link inside this app: one leading slash, not followed by /, \ or whitespace
HISTORY_TOP = "Pick a day as year-month-day, like 2026-11-19."

def history_scope():
    """(scope, allow, depts) of the signed-in person's history: "all" with right history; "dept" with history.dept (entries by
    them, or about a department of theirs); "own" with history.own (entries by them); (None, None, []) otherwise"""
    if has("history"): return "all", None, []
    p = who(); me = p["name"] if p else None
    if has("history.dept") and p:
        mine = list(people.record(people.load(), me)["depts"])
        def about_mine(e):   # a line whose departments are not a list of names is no one's department
            ds = e.get("depts")
            return isinstance(ds, list) and any(isinstance(d, str) and d in mine for d in ds)
        return "dept", (lambda e: e.get("who") == me or about_mine(e)), mine
    if has("history.own") and p:
        shut = via() == "code"     # a personal code does not open the setup or the admin page: nor their history
        return "own", (lambda e: e.get("who") == me and not (shut and e.get("kind") in _NOT_BY_CODE)), []
    return None, None, []

_NOT_BY_CODE = {"setup", "setup-refused", "setup-replaced", "app", "account"}

def _own_line():
    """the piece of text a stored line about the signed-in person must hold, for history.read's raw (own scope only)"""
    return json.dumps(who()["name"], ensure_ascii=False)

@app.get("/history")
@need("history", "history.dept", "history.own")
def history_page():
    return app.send_static_file("history.html")

def _history_query(args):
    """the filters of /api/history as keyword arguments for history.read, or ({"error": …}, 400)"""
    q = args
    since = until = None
    if q.get("from"):
        since = history.day_start(q["from"])
        if since is None: return {"error": HISTORY_TOP}, 400
    if q.get("to"):
        d = history.day_start(q["to"])
        if d is None: return {"error": HISTORY_TOP}, 400
        until = d + 86400 - 0.001
    if q.get("since"):
        try: after = float(q["since"])
        except ValueError: return {"error": "Pick a time as a number of seconds."}, 400
        if after != after or after in (float("inf"), float("-inf")): return {"error": "Pick a time as a number of seconds."}, 400
        since = after if since is None else max(since, after)
    if since is not None and until is not None and since > until: return {"error": "The first day is after the last day."}, 400
    return dict(where=q.get("where") or None, dept=q.get("dept") or None, since=since, until=until,
                signins=q.get("signins") == "1", who_contains=(q.get("who") or "").strip().lower() or None)

HISTORY_DOWNLOAD_MAX = 20000
HISTORY_MORE = "There are more entries than one download holds: pick fewer days."
_VIA = {"password": "password", "code": "code", "shared": "shared code", "personal": "personal code", "app": "by itself", "google": "Google", "telegram": "Telegram"}

@app.get("/api/history/download")
@need("history")
def history_download():
    """the history with the page's filters as an Excel file, newest first, up to HISTORY_DOWNLOAD_MAX entries"""
    import openpyxl
    f = _history_query(request.args)
    if isinstance(f, tuple): return f
    found = history.read(limit=HISTORY_DOWNLOAD_MAX + 1, **f)
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "History"
    from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
    txt = lambda v: ILLEGAL_CHARACTERS_RE.sub("", v)       # Excel refuses control characters
    def put(cells): ws.append([txt(c) for c in cells])
    put(["Day", "Time", "Who", "Signed in with", "Where", "What", "Was", "Became", "Departments"])
    for e in found[:HISTORY_DOWNLOAD_MAX]:
        day = clock = ""
        try:
            d = datetime.datetime.fromtimestamp(history.ts_of(e), history.SCHOOL_TZ)
            day, clock = d.strftime("%Y-%m-%d"), f"{d.hour % 12 or 12}:{d.minute:02d} {'am' if d.hour < 12 else 'pm'}"
        except (TypeError, ValueError, OverflowError, OSError): pass
        via = str(e.get("via") or "")
        setup = e.get("kind") == "setup"
        depts = e.get("depts")
        put([day, clock, str(e.get("as") or e.get("who") or ""), _VIA.get(via) or via, str(e.get("where") or ""),
             str(e.get("text") or ""), history._show(e.get("was")) if setup else "", history._show(e.get("now")) if setup else "",
             ", ".join(str(x) for x in depts) if isinstance(depts, list) else ""])
    if len(found) > HISTORY_DOWNLOAD_MAX: put([HISTORY_MORE])
    for row in ws.iter_rows():
        for c in row: c.data_type = "s"                    # text is never read as a formula
    out = io.BytesIO(); wb.save(out); out.seek(0)
    name = datetime.datetime.now(history.SCHOOL_TZ).strftime("history-%Y-%m-%d.xlsx")
    return send_file(out, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", as_attachment=True, download_name=name)

@app.get("/api/history")
@need("history", "history.dept", "history.own")
def api_history():
    """the history, newest first, filtered: who (part of the name it shows), where, dept, from and to (school days, `to`
    included), since (seconds since 1970), signins=1, before (an entry id: the entries after it), limit (up to 500). `more`: older ones exist"""
    q = request.args
    try: limit = int(q.get("limit") or 200)
    except ValueError: return {"error": "The number of entries must be a number."}, 400
    if limit < 1: return {"error": "The number of entries must be at least 1."}, 400
    limit = min(limit, HISTORY_MAX)
    f = _history_query(q)
    if isinstance(f, tuple): return f
    dept = f["dept"]
    before = q.get("before") or None
    scope, allow, mine = history_scope()
    if scope == "dept" and dept is not None and dept not in mine: return jsonify(entries=[], more=False, admin=has("admin"), depts=mine, scope=scope, download=False)
    found = history.read(before=before, limit=limit + 1, allow=allow, raw=_own_line() if scope == "own" else None, **f)
    if scope != "all":
        for e in found: e.pop("addr", None)     # where a refused try came from is the committee's to read
    shown = found[:limit]
    times = [t for t in map(history.ts_of, shown) if t is not None]     # a line whose ts cannot be read is skipped here
    if times and (has("setup") or has("admin")):
        putback.annotate(shown, history.read(since=min(times) - 60, kinds=putback.TOUCH_KINDS, limit=10 ** 7), may_put_back)
    for e in found:
        if "link" in e and not _SAFE_LINK.match(e["link"] if isinstance(e["link"], str) else ""): del e["link"]
    try: depts = [str(d) for d in store.setup_record()["spec"]["school"]["departments"]]
    except Exception: depts = []
    if scope == "dept": depts = mine
    return jsonify(entries=found[:limit], more=len(found) > limit, admin=has("admin"), depts=depts, scope=scope, download=has("history"))

CANT_BACK = "This change cannot be put back here."

def may_put_back(es):
    """may the signed-in person put back this unit (its entries, oldest first)? The committee any setup change, a head
    signed in by name their own (the app's follow-ups to it are nobody's); an admin an account change. The shared heads'
    code never puts back"""
    es = putback.own(es)
    if not es: return False
    if putback.unit_of(es[0]).startswith("a:"): return has("admin")
    if has("committee"): return True
    p = who()
    return is_head() and p is not None and all(e.get("who") == p["name"] for e in es)

AGAIN_SINCE = "Can't put back: this was changed again since."
REPLACED_MEANWHILE = "Can't put back: the whole setup was replaced meanwhile. Use a saved copy on the committee page."

def _field_now(d, item, name, field):
    """what the admin page's _change compares against for one field of one person"""
    r = people.record(d, name)
    if field == "group": return item["group"]
    if field in ("timetable", "relief", "exams", "admin"): return r["extras"][field]
    return r[field]                                   # depts, note, off

def _put_back_account(unit, e):
    """put back an admin-page change: every field of every person goes back to what the entry says it was, all in one
    people.update and only while each is still as the entry left it; nothing is written when any check refuses"""
    me, by_, pub = who()["name"], by(), store.published()
    text = "Put back: " + str(e.get("text") or "")
    per = {}
    for c in e.get("changes") or []:
        per.setdefault(c["name"], {})[c["field"]] = (c.get("was"), c.get("now"))
    def go(d):
        items = {p["name"]: p for p in people.staff(pub, d)}
        for n in per:
            if n not in items: raise Refused(f"Can't put back: {n} is no longer on the staff list.")
        for n, fs in per.items():
            if any(_field_now(d, items[n], n, f) != now for f, (was, now) in fs.items()): raise Refused(AGAIN_SINCE)
        before = people.usable_admins(d)
        def want(n, fs):   # a head again keeps the departments they have now: _change would otherwise give them step 4's
            w = {f: was for f, (was, now) in fs.items()}
            if w.get("group") in people.HEADS and "depts" not in w: w["depts"] = list(people.record(d, n)["depts"])
            return w
        done = {n: _change(d, n, items[n], want(n, fs)) for n, fs in per.items()}
        touched = [n for n in per if done[n]]
        if not touched: raise Refused(AGAIN_SINCE)
        _whole(d, touched, before)
        return touched, [c for n in touched for c in done[n]]
    try: touched, changes = _update_as(me, go)
    except Refused as x: return {"error": str(x)}, 409
    except people.Unreadable: return {"error": people.UNREADABLE}, 503
    _account_entry("putback", touched, changes, text, by_=by_, putback=unit, putback_of=e.get("as"), putback_ts=e.get("ts"))
    return {"done": True, "text": "Put back."}

@app.post("/api/history/back")
@need("setup", "admin")
def history_back():
    """put back one setup change (the whole save it was made in): the reverse operations are applied under the store's
    lock, only when every row and field is still as the save left it and no band is left under another's name or
    named by lessons or rules once it is gone"""
    body = request.get_json(force=True, silent=True)
    eid = body.get("id") if isinstance(body, dict) else None
    e = history.find(eid)
    if e is None: return {"error": "That entry is not in the history."}, 404
    if putback.unit_of(e) is None: return {"error": CANT_BACK}, 409
    v0 = store.setup_record()["v"]    # the setup the history is read against: a whole replacement after it refuses the put back
    got = putback.gather(eid)
    if got is None: return {"error": CANT_BACK}, 409
    unit, es, newer = got
    if not may_put_back(es): return {"error": "Only the timetable committee can put back someone else's change."}, 403
    why = putback.why_not(es, newer)
    if why: return {"error": why}, 409
    if unit.startswith("a:"): return _put_back_account(unit, es[0])
    ops = putback.reverse(es)
    depts = head_depts() if is_head() else None
    def check(spec, o):
        sentence = putback.changed_since(spec, es) or putback.band_clash(spec, o)
        if sentence or not is_head(): return sentence
        refused = sync.head_split(spec, o, depts)[1]
        return refused[0][1] if refused else None
    tag = {"putback": unit, "putback_of": es[0].get("as"), "putback_ts": es[0].get("ts")}
    told = {}
    try: store.apply_changes(ops, "history", check=check, since=v0, by=by(), tag=tag, told=told)
    except store.Replaced: return {"error": REPLACED_MEANWHILE}, 409
    except store.Refused as x: return {"error": str(x)}, 409
    except LookupError: return {"error": "There is no saved setup to change yet."}, 409
    said = _follow_students(told)    # the published timetable follows a put back too
    if said and "error" in said:
        return {"done": True, "text": "Put back. The published timetable was not updated: press Update the published timetable on the Students step."}
    return {"done": True, "text": "Put back."}

ONLY_ADMIN = "Only an admin can open this page."

@app.get("/admin")
@need("admin", "committee")
def admin_page():
    """the admin page for an admin. The committee without the Admin extra (the committee code on deploy day, or a
    committee member) is sent to "Make the first admin" while no admin can sign in, and is told the page is an admin's
    once one can"""
    move_relief_lists()
    if not has("admin"):
        if not people.usable_admins(people.load()): return redirect("/admin/first")
        return page("Admin", f"<main class='login'><h1>Admin</h1><p class='muted'>{esc(ONLY_ADMIN)}</p><p><a href='/'>Back</a></p></main>"), 403
    if not accounts_on(): return page("Admin", f"<main class='login'><h1>Admin</h1><p class='muted'>{esc(NO_ACCOUNTS)}</p></main>"), 403
    return app.send_static_file("admin.html")

@app.get("/api/admin/people")
@need("admin")
def admin_people():
    """the staff list with its hints and, once, what moved from relief's and exams' own lists"""
    stop = _admin_off()
    if stop: return stop
    move_relief_lists()
    pub, data = store.published(), people.load()
    ps = [_with_gives(p, data) for p in people.staff(pub, data)]
    group, heads = {p["name"]: p["group"] for p in ps}, []
    spec = store.setup_record()["spec"]   # step 4 of the setup being edited; the published one's while no setup is saved
    rows = spec.get("teachers") if isinstance(spec, dict) else (((pub or {}).get("model") or {}).get("setup") or {}).get("teachers")
    for x in rows if isinstance(rows, list) else []:
        if not isinstance(x, dict): continue
        n = str(x.get("name") or "").strip()
        if str(x.get("role") or "").strip().upper() in ("HOD", "SH") and group.get(n) == "teacher" and n not in heads: heads.append(n)
    no_dept = [p["name"] for p in ps if p["group"] in people.HEADS and not people.record(data, p["name"])["depts"]]   # they change no rows (R8)
    return jsonify(people=ps, departments=school_depts(), groups=[[k, people.LABELS[k]] for k in people.GROUPS],
                   committees=[[k, label] for k, label in people.COMMITTEES], hints=dict(heads_on_step4=heads, no_google=[], heads_no_dept=no_dept), moved=data["moved"] if isinstance(data["moved"], list) else [],
                   me=who()["name"])

@app.post("/api/admin/person")
@need("admin")
def admin_person():
    """change one person, or add one by name (added: true) -> their staff item"""
    stop = _admin_off()
    if stop: return stop
    me, by_, pub, today = who()["name"], by(), store.published(), datetime.date.today()   # by_ before: their own change may end this session
    try:
        b = _body()
        if not isinstance(b.get("name"), str): raise Refused(UNREAD_CHANGE)
        adding = b.get("added") is True
        name = b["name"].strip() if adding else b["name"]
        if adding and _name_problem(name): raise Refused(_name_problem(name))
        want = _wanted(b, today)
        def change(d):
            item = next((p for p in people.staff(pub, d) if p["name"] == name), None)
            if adding and item: raise Refused((ON_STAFF if item["staff_only"] else ON_TIMETABLE).format(name))
            if not adding and item is None: raise Refused(NOT_STAFF.format(name))
            if want.get("username") and _taken(d, want["username"], name): raise Refused(TAKEN)
            before = people.usable_admins(d)
            out = _change(d, name, item, want)
            if out: _whole(d, [name], before)
            return out
        out = _update_as(me, change)
    except Refused as e: return {"error": str(e)}, 400
    except people.Unreadable: return {"error": people.UNREADABLE}, 503
    if out: _account_entry(_what(out), [name], out, f"{name}: " + "; ".join(_said(c) for c in out), by_=by_)
    return jsonify(_admin_item(pub, people.load(), name))

def _remove_refusal(d, pub, me, name):
    """why name cannot be removed, checked in order on the records d (Refused), else their staff item"""
    item = next((p for p in people.staff(pub, d) if p["name"] == name), None)
    if item is None: raise Refused(NOT_STAFF.format(name))
    if not item["staff_only"]: raise Refused(REMOVE_ON_TIMETABLE.format(name))
    if name == me: raise Refused(REMOVE_SELF)
    if not [n for n in people.usable_admins(d) if n != name]: raise Refused(LAST_ADMIN.format(name))   # a guard: the admin doing it stays
    return item

@app.post("/api/admin/remove")
@need("admin")
def admin_remove():
    """remove a person who is not on the published timetable (added by name, or a record left after they left it): their
    Telegram chat and link codes go first, then their record goes and `removed[name]` becomes their n + 1 in one update, so every
    session of theirs ends and none comes back, even once they are added again; the chat and codes are dropped once more after
    the write. What they changed stays in the History"""
    stop = _admin_off()
    if stop: return stop
    me, by_, pub = who()["name"], by(), store.published()
    try:
        b = _body()
        name = b.get("name")
        if not isinstance(name, str): raise Refused(UNREAD_CHANGE)
        if not people.readable(): raise people.Unreadable(people.UNREADABLE)
        _remove_refusal(people.load(), pub, me, name)
        try: relief_links.forget(name)   # their Telegram chat and link codes
        except Exception as e:
            print(f"WARNING: a Telegram chat could not be unlinked ({type(e).__name__})", file=sys.stderr, flush=True)
            return {"error": REMOVE_UNLINK}, 503
        def change(d):
            item = _remove_refusal(d, store.published(), me, name)   # again, on the records and the timetable as they are now
            r = people.record(d, name)
            was = dict(role=people.LABELS.get(item["group"], item["group"]), timetable=r["extras"]["timetable"], relief=r["extras"]["relief"],
                       exams=r["extras"]["exams"], admin=r["extras"]["admin"], depts=list(r["depts"]), username=r["username"], note=r["note"], off=r["off"])
            d["people"].pop(name, None)
            d["removed"][name] = r["n"] + 1
            return was
        was = _update_as(me, change)
    except Refused as e: return {"error": str(e)}, 400
    except people.Unreadable: return {"error": people.UNREADABLE}, 503
    try: relief_links.forget(name)   # again: a link or a code made since the first one goes too (the removal stands either way)
    except Exception as e: print(f"WARNING: a Telegram chat could not be unlinked after a removal ({type(e).__name__})", file=sys.stderr, flush=True)
    _account_entry("remove", [name], [dict(name=name, field="removed", was=was, now=None)], f"Removed {name}", by_=by_)
    return jsonify(done=True, text=REMOVED.format(name))

@app.post("/api/admin/bulk")
@need("admin")
def admin_bulk():
    """one change for several people: the preview's lines, then (preview: false) all of it or none of it"""
    stop = _admin_off()
    if stop: return stop
    me, by_, pub, today = who()["name"], by(), store.published(), datetime.date.today()
    try:
        b = _body()
        if b.get("preview", True) is not False:   # only an explicit preview: false changes anything
            if not people.readable(): raise people.Unreadable(people.UNREADABLE)
            return jsonify(lines=_bulk(people.load(), pub, b, today)["lines"], applied=False)
        got = _update_as(me, lambda d: _bulk(d, pub, b, today))
    except Refused as e: return {"error": str(e)}, 400
    except people.Unreadable: return {"error": people.UNREADABLE}, 503
    if got["touched"]: _account_entry(got["what"], got["touched"], got["changes"], got["text"], by_=by_)
    return jsonify(lines=got["lines"], applied=bool(got["touched"]))

@app.post("/api/admin/reset")
@need("admin")
def admin_reset():
    """a one-time password (and the username, when given): the answer is the only place it ever appears"""
    stop = _admin_off()
    if stop: return stop
    me, by_, pub = who()["name"], by(), store.published()
    try:
        b = _body()
        name = b.get("name")
        if not isinstance(name, str): raise Refused(UNREAD_CHANGE)
        given = _username(b.get("username"))
        if not any(p["name"] == name for p in people.staff(pub)): raise Refused(NOT_STAFF.format(name))
        once = passwords.one_time(); h = passwords.hash_pw(once)
        def change(d):
            if not any(p["name"] == name for p in people.staff(pub, d)): raise Refused(NOT_STAFF.format(name))
            r = people.record(d, name)
            u = given or r["username"]
            if not u: raise Refused(NO_USERNAME)
            if _taken(d, u, name): raise Refused(TAKEN)
            out = [dict(name=name, field="username", was=r["username"], now=u)] if u != r["username"] else []
            r.update(username=u, pw=h, must_change=True, n=r["n"] + 1)
            d["people"][name] = r
            return out, u
        out, u = _update_as(me, change)
    except Refused as e: return {"error": str(e)}, 400
    except people.Unreadable: return {"error": people.UNREADABLE}, 503
    lockout.clear(u)
    _account_entry("reset", [name], out, f"{name}: a new one-time password" + (f"; username {u}" if out else ""), by_=by_)
    r = jsonify(once=once); r.headers["Cache-Control"] = "no-store"
    return r

@app.get("/api/admin/ways")
@need("admin")
def admin_ways():
    stop = _admin_off()
    return stop or jsonify(_ways())

@app.post("/api/admin/shared-off")
@need("admin")
def admin_shared_off():
    """turn a shared code off (its open sessions end at their next request) or on again -> the ways in"""
    stop = _admin_off()
    if stop: return stop
    by_ = by()
    try:
        b = _body()
        r, off = b.get("code"), b.get("off")
        if r not in people.SHARED: raise Refused(PICK_SHARED)
        if not isinstance(off, bool): raise Refused(UNREAD_CHANGE)
        at = time.time()
        def change(d):
            was = d["ways"]["off"].get(r)
            d["ways"]["off"][r] = now = (was if was is not None else at) if off else None
            return was, now
        was, now = people.update(change)
    except Refused as e: return {"error": str(e)}, 400
    except people.Unreadable: return {"error": people.UNREADABLE}, 503
    if (was is None) != (now is None):
        label = SHARED_AS[r]
        _account_entry("shared-off", [], [dict(name=label, field="off", was=was, now=now)],
                       f"Turned {'off' if off else 'on'} the {label[0].lower() + label[1:]}", by_=by_, shared=r)
    return jsonify(_ways())

@app.get("/api/admin/students")
@need("admin")
def admin_students():
    stop = _admin_off()
    if stop: return stop
    pub = store.published()
    return jsonify([{"id": s.get("id"), "name": s.get("name"), "class": s.get("cls")} for s in ((pub or {}).get("model") or {}).get("students") or []])

def _first_page(msg="", form=True, name="", username=""):
    f = ""
    if form:
        opts = "".join(f'<option value="{esc(p["name"])}"></option>' for p in people.staff(store.published()))
        f = f"""<p>No one is an admin yet. Make yourself the first: you then sign in with this username and password, and give everyone else their access on the admin page.</p>
<form method="post" action="/admin/first"><label for="name">Your name (pick it from the list, or type it)</label>
<input id="name" name="name" class="plain" list="staff" value="{esc(name)}" autocomplete="off" required><datalist id="staff">{opts}</datalist>
<label for="username">Username (for example daniel.wong)</label><input id="username" name="username" class="plain" value="{esc(username)}" autocapitalize="none" spellcheck="false" autocomplete="username" required>
{_field("new", "Password (at least 10 characters)", auto="new-password")}{_field("again", "Password again", auto="new-password")}
<button type="submit">Make me the first admin</button></form>"""
    return _form_page(FIRST_ADMIN, f, msg, back=("/", "Committee page"))

@app.route("/admin/first", methods=["GET", "POST"])
@need("committee")
def admin_first():
    """while no admin can sign in: whoever holds the committee's rights makes themselves the first admin, with a password,
    and is signed in as them. Once an admin who can sign in exists this page is not there"""
    if not people.readable(): return _first_page(ACCOUNTS_UNREADABLE, form=False), 503
    if people.usable_admins(people.load()): abort(404)
    if not accounts_on(): return _first_page(NO_ACCOUNTS, form=False), 403
    if request.method == "GET": return _first_page()
    name, typed = (str(request.form.get(k) or "").strip() for k in ("name", "username"))
    new, again = (str(request.form.get(k) or "") for k in ("new", "again"))
    pub = store.published()
    def back(msg): return _first_page(msg, name=name, username=typed), 400
    if not any(p["name"] == name for p in people.staff(pub)) and _name_problem(name): return back(_name_problem(name))
    try: u = _username(typed)
    except Refused as e: return back(str(e))
    if not u: return back(BAD_USERNAME)
    why = passwords.problem(new, u, name)
    if why: return back(why)
    if new != again: return back(NOT_SAME)
    h, by_, me = passwords.hash_pw(new), by(), (who() or {}).get("name")
    def change(d):
        if people.usable_admins(d): return None                   # someone was quicker
        if _taken(d, u, name): raise Refused(TAKEN)
        if people.record(d, name)["pw"] and name != me: raise Refused(HAS_PASSWORD.format(name))   # no one else's password is replaced
        item = next((p for p in people.staff(pub, d) if p["name"] == name), None)
        out = _change(d, name, item, dict(timetable=True, admin=True, username=u, off=False))   # their role stays as it is
        r = people.record(d, name)
        r.update(pw=h, must_change=False, n=r["n"] + 1)
        d["people"][name] = r
        return out, r["n"]
    try: got = people.update(change)
    except Refused as e: return back(str(e))
    except people.Unreadable: return _first_page(people.UNREADABLE, form=False), 503
    if got is None: abort(404)
    out, n = got
    _account_entry("first-admin", [name], out, f"{name}: made the first admin", by_=by_)
    _start(who=name, via="password", n=n, exp=time.time() + FORTNIGHT); _note_signin(name)
    return redirect("/admin")

# ------------------------------------------------------------------------------------------------ Plan with AI (plan/)
# The chat has exactly the rights of the person typing: its Env is built in the request from a snapshot of who is asking and
# then never reads the request again (an answer runs on a thread of its own, with no request), re-reading the records at
# every step. Its saves are the exam pages' own (plan.steps' rules), recorded as "<name>, with Plan with AI".
def _plan_snapshot():
    """who is asking, as the chat's Env keeps it: the person's name (None for the shared committee code), how they signed
    in, their record's sign-in number, the password session's end, the shared code, the saved-by name and by()"""
    p = who()
    rights = _exams_rights(store.published())
    return dict(name=p["name"] if p else None, via=via(), n=p["n"] if p else None, exp=session.get("exp"), shared=shared(),
                saved_by=rights[1] if rights else None, by=by())

class AppEnv:
    """plan.steps' Env for the app (plan/steps.py's Env protocol). No method touches the request, the session, g, who(),
    has(), rights(), via() or by(): each works on a plain thread"""
    def __init__(self, snap):
        self._snap, self.name = dict(snap), snap["saved_by"]

    def may(self):
        """the person may change exams now, from the records read again (as _check and accounts/rights.py work it out on every
        request), else Refused with the exam page's sentence"""
        s, no = self._snap, plan_steps.Refused(ONLY_EXAMS)
        if s["name"] is None:
            if s["via"] != "shared" or s["shared"] != "committee" or people.load()["ways"]["off"].get("committee") is not None: raise no
            return
        if not people.readable(): raise no
        data, pub = people.load(), store.published()
        p = people.find(s["name"], pub, data)
        if p is None:
            if s["via"] == "password" or pub: raise no
            p = _stand_in(s["name"], data)
        if p["off"] or p["n"] != s["n"]: raise no
        if s["via"] == "password" and not (p.get("pw") and isinstance(s["exp"], (int, float)) and time.time() < s["exp"]): raise no
        if not rights_table.rights(p, s["via"], None) & {"exams", "committee"}: raise no

    def pub(self): return store.published()
    def cal(self): return _exam_cal(self.pub())
    def settings(self): return exams_settings.load(self.pub())
    def people(self): return people.listing(self.pub())
    def all_saved(self): return exams_schedules.all_saved()
    def today(self): return _exams_today()
    def load(self, id): return exams_schedules.load(id)

    def _record(self, what):
        """plan.steps' record(entry): one history entry as an exam page's save writes it, by "<name>, with Plan with AI" """
        def record(entry):
            _exams_entry(what, entry["text"], entry.get("exam"), "/exams", by_=dict(self._snap["by"], **{"as": entry["by"]}))
        return record

    def create(self, kind, name, levels, classes, start, end, words):
        return plan_steps.do_create(self, kind, name, levels, classes, start, end, words, self._record("create"))
    def change(self, id, fn, words): return plan_steps.do_change(self, id, fn, words, self._record("edit"))
    def remove(self, id, rev, words): return plan_steps.do_remove(self, id, rev, words, self._record("delete"))

def _plan_person(name):
    """a person's talks are theirs in any browser: keyed by a keyed hash of their name, never the name itself"""
    key = app.secret_key if isinstance(app.secret_key, bytes) else str(app.secret_key).encode()
    return "p:" + hmac.new(key, name.encode(), "sha256").hexdigest()[:32]

def _plan_owner(create=False):
    """the owner of this session's talks: the person's, or the shared committee code's browser session's (its own random
    plan_sid, given at its first talk when create); None for anyone else"""
    p = who()
    if p: return _plan_person(p["name"])
    if shared() != "committee": return None
    sid = session.get("plan_sid")
    if not isinstance(sid, str) or not sid:
        if not create: return None
        sid = session["plan_sid"] = secrets.token_urlsafe(16)
    return "s:" + sid

def _plan_owners_of_session():
    """the owners whose talks this session holds, from the session as it stands (signing out drops them)"""
    name, sid = session.get("who"), session.get("plan_sid")
    return [_plan_person(name) if isinstance(name, str) and name else None, "s:" + sid if isinstance(sid, str) and sid else None]

plan_web.init(need=need, env=lambda: AppEnv(_plan_snapshot()), owner=_plan_owner)
app.register_blueprint(plan_web.bp)

# ------------------------------------------------------------------------------------------------ staff: exams and events
NO_EXAMS_PUB = "Publish the timetable first: exams read the classes, students and lessons from it."
ONLY_EXAMS = "Only the exams committee and the timetable committee can open exams."
NO_STUDENTS = "The published timetable has no students. Add them on the Students step and publish again to seat them."
NO_EXAM = "That exam is not there any more."
NO_EVENT = "That event is not there any more."
ONLY_IN_CHARGE = "Only the teacher in charge and the timetable committee can open this event."
PICK_IN_CHARGE = "Pick the teacher in charge."
ONLY_GIVES = "Only the timetable committee can change the teacher in charge."
EVENT_KEEPS = ("id", "kind", "in_charge", "created_at", "created_by", "status", "approved", "approved_at", "approved_by", "sent_at",
               "sent_by", "sent_fp", "note", "log", "handled")
ONLY_APPROVE = "Only the timetable committee can approve, send back or withdraw."
ON_SITE = "This schedule is on the main site: the timetable committee must withdraw it before it can be deleted."
EXAM_KEEPS = ("id", "created_at", "created_by", "made", "pins", "use_anyway", "status", "approved", "approved_at", "approved_by",
              "sent_at", "sent_by", "sent_fp", "note", "log", "handled")    # handled: Handled ourselves, changed by its own route
BAD_INPUT = (TypeError, KeyError, AttributeError)
NO_BACKUP = "That lesson no longer needs a backup."

def _exams_rights(pub):
    """(may use exams, saved by) for whoever is signed in, from the accounts: the Exams and events extra (until its end
    date) or the timetable committee; saved by the person's name, or "Timetable committee" for the shared committee code.
    None when nobody is signed in by name or with the committee code"""
    p = who()
    if p is None: return (True, "Timetable committee") if has("committee") else None
    return has("exams") or has("committee"), p["name"]

def _exams_can_approve():
    """the timetable committee approves, sends back and withdraws: the committee right (the shared committee code, or a
    committee member signed in with their password)"""
    return has("committee")

def _event_rights(sched):
    """(may open this event, saved by, sees every event) for whoever is signed in, from the accounts: the timetable
    committee (the committee right: the shared committee code, or a committee member signed in with their password) opens
    every event; anyone else signed in by name (any way in) only an event they are in charge of (sched None: the list, and
    starting one, as its teacher in charge). Saved by the person's name, or "Timetable committee" for the shared committee
    code. None for the shared heads', teacher and student codes: they are nobody's, so no event is theirs. The Exams and
    events extra gives nothing here: the exams committee does not manage events"""
    p = who()
    if has("committee"): return True, p["name"] if p else "Timetable committee", True
    if p is None: return None
    return (sched is None or sched.get("in_charge") == p["name"]), p["name"], False

def _exams_today():
    """the school's date, as relief has it: the live server runs on UTC, where it is still yesterday until 8 in the morning"""
    return relief_lessons.today()

def _published_reader():
    """who may read the published exams data, and how much: "full" (teacher names, duty rooms, roster, prints) for everyone
    who sees the published timetable as staff (the committee, the heads' and teachers' codes, a person signed in by name);
    "student" (classes, rooms and times only) for the shared student code"""
    if not has("timetable"): return None
    return "student" if shared() == "student" else "full"

def _exams_student():
    """the student a personal code is signed in as, whose own exam timetable /api/me/exams shows; None for anyone else"""
    return session.get("sid") if has("own") else None

BAD_DATE = "Give a date such as 2026-10-05."
REPUBLISHED = "The timetable was published again: reload the page."
NO_DAY_CAL = "The school calendar is not set yet, so the timetable cannot be shown on a date."
ONLY_STAFF_PRINTS = "Only staff can open the seating plans and rosters."
ONLY_OWN_DUTIES = "Sign in with your own code or password to see your exam and event duties."
ONLY_OWN_EVENTS = "Sign in with your own code or password to start or open an event."

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
    if _event_rights(None) is None: return no(({"error": ONLY_OWN_EVENTS}, 403))   # a shared code other than the committee's: before any event is read
    sched = None
    if id is not None:
        sched = exams_schedules.load(id)
        if not sched or sched.get("kind") != "event": return no(({"error": NO_EVENT}, 404))
    rights = _event_rights(sched)
    if not rights[0]: return no(({"error": ONLY_IN_CHARGE}, 403))
    return pub, rights[1], sched, rights[2], None

def _exam_cal(pub): return relief_settings.load(pub)["calendar"]

def _exam_json():
    d = request.get_json(force=True, silent=True)
    return d if isinstance(d, dict) else {}

def _exams_entry(what, text, exam=None, link="/exams", by_=None):
    """one history entry for an exams or events save: who, what, which, a link (not field by field; exams keeps its own
    record). An event's entry links to the event itself (/events/<id>). A failure to write it never fails the save.
    by_: who it is by when not this request's by() (Plan with AI's steps, which run with no request)"""
    e = {"kind": "exams", "what": what, "where": "Exams and events", "text": text, "link": link, **(by() if by_ is None else by_)}
    if exam: e["exam"] = exam
    try: history.add(e)
    except Exception as x: print(f"WARNING: an exams change could not be recorded in the history ({type(x).__name__})", file=sys.stderr, flush=True)

def _save_exam(sched, pub, saved_by, what, words, check=True, event=False):
    """save a schedule and record it in the history as "<its name>: <words>"; (the saved schedule, None) or (None, the
    400 answer): malformed JSON never gives a 500. check=False: saved without the timetable check (approve, send back,
    withdraw and someone is away still work after a new publish). event=True: an event's wording and its own link"""
    try: saved = exams_schedules.save(sched, pub, _exam_cal(pub), saved_by, check=check)
    except ValueError as e: return None, ({"error": str(e)}, 400)
    except BAD_INPUT: return None, ({"error": exams_schedules.EVENT_WRONG if event else exams_schedules.WRONG}, 400)
    _exams_entry(what, f"{saved['name']}: {words}", saved.get("id"), f"/events/{saved.get('id')}" if event else "/exams")
    return saved, None

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

def _relief_sync(pub, s=None):
    """relief's backups in step (exams.relief_links.sync_all) after every approval action and Handled ourselves change that
    saved, and after a publish (s None): the schedule acted on first, then every other one a sync may change (to_sync), so a
    lesson one schedule gives up or stops goes to (or leaves) another at once. Each sync is idempotent; one failing never stops
    the others and never fails the action: each error is logged and the next action syncs again. The caller holds
    exams_schedules.editing()"""
    try: cal, today = _exam_cal(pub), _exams_today()
    except Exception: return app.logger.exception(exams_relief_links.SYNC_FAILED)
    exams_relief_links.sync_all(pub, cal, today, first=s)

def _exam_view(pub, sched):
    model, cal = pub["model"], _exam_cal(pub)
    by_id = {x["id"]: x for x in model.get("students") or []}
    papers = sched.get("papers") or []
    levels, classes = set(sched.get("levels") or []), set(sched.get("classes") or [])
    mine = {x["id"] for x in model.get("students") or [] if exams_papers._student_level(model, x) in levels or x.get("cls") in classes}
    sids = sorted(mine | {i for p in papers for i in exams_papers.who_sits(p, model)})
    return dict(rev=exams_schedules.rev_of(sched), summary=exams_make.summary(pub, cal, sched, exams_settings.load(pub)), lessons=_marked(exams_make.lesson_lists(pub, cal, sched), sched, pub, cal),
                made=sched.get("made"), students={i: [by_id[i]["name"], by_id[i]["cls"]] for i in sids if i in by_id},
                counts={p.get("id"): len(exams_papers.who_sits(p, model)) for p in papers}, periods=[[exams_days.hhmm(a), exams_days.hhmm(b)] for a, b in exams_days.bounds(model)],
                rooms=exams_settings.load(pub)["rooms"], students_missing=not model.get("students"), levels=list(model.get("levels") or []),
                rooms_by_key=_exam_rooms_by_key(pub, cal, sched), stale=exams_make.stale(sched, exams_settings.load(pub), model))

def _exam_rooms_by_key(pub, cal, sched):
    """for each sitting, every exam room with its seats and what keeps it busy then (empty text: free); a room another
    overlapping sitting of the made schedule holds is busy, so the move selects do not offer it"""
    xset = exams_settings.load(pub)
    held = exams_make.held(pub, sched, xset)
    busy = exams_schedules.elsewhere(sched.get("id"), pub["model"], own=sched)
    return {x["key"]: [[r["name"], r["seats"], r["busy"]] for r in exams_seating.rooms_free(pub, cal, sched, x, xset, held.get(x["key"], set()), elsewhere=busy)]
            for x in exams_seating.sittings(sched)}

@app.get("/exams")
@need("exams", "committee", "timetable")
def exams_home():
    """the exams committee and the timetable committee use exams here; anyone else signed in by name sees only their own
    exam duties (My exam duties); the shared heads', teacher and student codes are nobody's: their own page"""
    if _exams_rights(store.published()) is None: return redirect("/")
    return app.send_static_file("exams.html")

@app.get("/exams/settings")
@need("exams", "committee")
def exams_settings_page():
    move_relief_lists()
    return app.send_static_file("exams-settings.html")

@app.get("/exams/<id>")
@need("exams", "committee")
def exams_one_page(id): return app.send_static_file("exams.html")

@app.get("/api/exams/me")
@need("exams", "committee", "timetable")
def exams_me():
    """who is asking: can_use false for a person who only sees their own exam duties"""
    pub = store.published()
    if not pub: return {"error": NO_EXAMS_PUB}, 409
    rights = _exams_rights(pub)
    if rights is None: return {"error": ONLY_EXAMS}, 403   # a shared code other than the committee's
    return jsonify(name=rights[1], can_use=rights[0], can_approve=_exams_can_approve(), home="/home" if who() else "/")   # a person's way back is their home page

def _exams_committee(pub):
    """the exams committee as the accounts hold it: [name, last day] of each person whose Exams and events extra has not
    ended (only an admin changes it, on the admin page)"""
    today = datetime.date.today().isoformat()
    return [[p["name"], p["extras"]["exams"]] for p in people.staff(pub) if (p["extras"].get("exams") or "") >= today and not p["off"]]

def _exam_settings_reply(pub, settings):
    """lists: the exams committee from the accounts, shown and never changed here; can_admin: the line links to the admin page"""
    m = pub["model"]
    return jsonify(settings=settings, lists=dict(committee=_exams_committee(pub)), can_admin=has("admin"), people=relief_staff(pub),
                   rooms=[[r["name"], r.get("kind"), r.get("capacity")] for r in m.get("rooms") or []])

@app.get("/api/exams/settings")
@need("exams", "committee")
def exams_settings_get():
    move_relief_lists()
    pub, who, err = _exams_gate()
    if err: return err
    return _exam_settings_reply(pub, exams_settings.load(pub))

@app.put("/api/exams/settings")
@need("exams", "committee")
def exams_settings_put():
    move_relief_lists()
    pub, who, err = _exams_gate()
    if err: return err
    try: saved = exams_settings.save(request.get_json(force=True, silent=True), pub, who)   # a committee list sent is ignored
    except ValueError as e: return {"error": str(e)}, 400
    except BAD_INPUT: return {"error": exams_settings.WRONG}, 400
    _exams_entry("settings", "Exam settings saved")
    return _exam_settings_reply(pub, saved)

@app.get("/api/exams")
@need("exams", "committee")
def exams_list():
    pub, who, err = _exams_gate()
    if err: return err
    m = pub["model"]
    return jsonify(schedules=_with_away(exams_schedules.listing(_exams_today(), exams_make.published_at(pub), kinds=("exam", "test")), pub), levels=m.get("levels") or [], classes=[[c["name"], c["level"]] for c in m.get("classes") or []],
                   calendar_ok=bool(_exam_cal(pub).get("terms")), plan=plan_ai.enabled())   # plan: the page shows its Plan with AI button

@app.post("/api/exams")
@need("exams", "committee")
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
    saved, bad = _save_exam(sched, pub, who, "create", "created")
    return bad or jsonify(saved)

def _stale_rev(old, b, event=False):
    """None when the page's copy (the body's rev) is the stored one; else the 409 answer naming who saved last. A schedule
    saved before revisions has no rev: a body without one passes (once: the next save gives it one)"""
    stored, got = exams_schedules.rev_of(old), b.get("rev")
    if got is None and "rev" not in old or (isinstance(got, int) and not isinstance(got, bool) and got == stored): return None
    what = "event" if event else "exam"
    return {"error": f"This {what} was changed by {old.get('saved_by') or 'someone'} since you opened it. Reload to carry on."}, 409

def _exam_or_404(id):
    s = exams_schedules.load(id)
    return (s, None) if s and s.get("kind") != "event" else (None, ({"error": NO_EXAM}, 404))   # an event has its own routes

@app.get("/api/exams/<id>")
@need("exams", "committee")
def exams_get(id):
    pub, who, err = _exams_gate()
    if err: return err
    s, err = _exam_or_404(id)
    return err or jsonify(s)

def _drop_moved_suggestions(old, new):
    """a suggested time stops being suggested when that paper's date or start is changed: its id goes from the new body"""
    sug = new.get("suggested")
    if not isinstance(sug, list): return
    def at(p):
        st = p.get("start") or None
        try: st = exams_days.minutes(st) if st else None   # "7:50" and "07:50" are one time
        except ValueError: pass
        return (p.get("date") or None, st)
    was = {p.get("id"): at(p) for p in old.get("papers") or [] if isinstance(p, dict)}
    now = {p.get("id"): at(p) for p in new.get("papers") or [] if isinstance(p, dict)}
    new["suggested"] = [i for i in sug if not (isinstance(i, str) and i in was and i in now and was[i] != now[i])]

@app.put("/api/exams/<id>")
@need("exams", "committee")
def exams_put(id):
    pub, who, err = _exams_gate()
    if err: return err
    with exams_schedules.editing():   # from loading to saving: what is kept is what is stored now
        old, err = _exam_or_404(id)
        if err: return err
        stale = _stale_rev(old, _exam_json())
        if stale: return stale
        new = dict(_exam_json(), **{k: old.get(k) for k in EXAM_KEEPS})
        new["log"] = old.get("log") or []
        if new.get("kind") not in exams_schedules.KINDS: return {"error": exams_schedules.WRONG}, 400   # an exam never becomes an event
        _drop_moved_suggestions(old, new)
        saved, bad = _save_exam(new, pub, who, "edit", "changed")
    return bad or jsonify(saved)

@app.delete("/api/exams/<id>")
@need("exams", "committee")
def exams_delete(id):
    pub, who, err = _exams_gate()
    if err: return err
    with exams_schedules.editing():   # an approve cannot land between the check and the delete
        s, err = _exam_or_404(id)
        if err: return err
        if s.get("approved"): return {"error": ON_SITE}, 409
        exams_schedules.delete(id)
    if s: _exams_entry("delete", f"{s.get('name')}: deleted", s.get("id"))   # nothing there, nothing deleted: no entry
    return {"ok": True}

@app.post("/api/exams/<id>/fill")
@need("exams", "committee")
def exams_fill(id):
    pub, who, err = _exams_gate()
    if err: return err
    with exams_schedules.editing():
        s, err = _exam_or_404(id)
        if err: return err
        s["papers"] = list(s.get("papers") or []) + exams_papers.fill_from_subjects(s, pub["model"])
        saved, bad = _save_exam(s, pub, who, "fill", "papers added from the subjects")
    return bad or jsonify(saved)

@app.get("/api/exams/<id>/papers.xlsx")
@need("exams", "committee")
def exams_papers_download(id):
    pub, who, err = _exams_gate()
    if err: return err
    s, err = _exam_or_404(id)
    if err: return err
    from ttgen.export import safe_name
    return send_file(io.BytesIO(exams_papers.paper_list_xlsx(s)), as_attachment=True, download_name=safe_name(f"{s.get('name')} papers") + ".xlsx", mimetype=XLSX)

@app.post("/api/exams/<id>/papers.xlsx")
@need("exams", "committee")
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
        was = dict(s)
        s["papers"] = [p for p in s.get("papers") or [] if p.get("who") == "students"] + rows
        _drop_moved_suggestions(was, s)
        saved, bad = _save_exam(s, pub, who, "papers", "paper list uploaded")
    return bad or jsonify(saved)

def _exam_view_reply(pub, sched):
    """the view as JSON; a schedule the code cannot read answers 400 with a sentence, never 500"""
    try: return jsonify(_exam_view(pub, sched))
    except ValueError as e: return {"error": str(e)}, 400
    except BAD_INPUT + (IndexError,): return {"error": exams_schedules.WRONG}, 400

@app.get("/api/exams/<id>/view")
@need("exams", "committee")
def exams_view(id):
    pub, who, err = _exams_gate()
    if err: return err
    s, err = _exam_or_404(id)
    return err or _exam_view_reply(pub, s)

def _exam_changed(id, change, what, words):
    """run change(pub, sched, body) on the stored schedule, save it (words(body): what the history says) and answer as the
    view does. The schedule is locked from loading to saving (a Make takes a while), so an approve or an edit meanwhile
    waits and is not undone by it"""
    pub, who, err = _exams_gate()
    if err: return err
    with exams_schedules.editing():
        s, err = _exam_or_404(id)
        if err: return err
        b = _exam_json()
        try: err = change(pub, s, b)
        except ValueError as e: return {"error": str(e)}, 400
        except BAD_INPUT: return {"error": exams_schedules.WRONG}, 400
        if err: return err
        saved, bad = _save_exam(s, pub, who, what, words(b))
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
@need("exams", "committee")
def exams_make_route(id): return _exam_changed(id, _exam_make, "make", lambda b: "seats and duties made")

@app.post("/api/exams/<id>/move")
@need("exams", "committee")
def exams_move(id): return _exam_changed(id, _exam_move, "move", lambda b: "students moved")

@app.post("/api/exams/<id>/invigilators")
@need("exams", "committee")
def exams_invigilators(id): return _exam_changed(id, _exam_invigilators, "invigilators", lambda b: "invigilators changed")

@app.post("/api/exams/<id>/use-anyway")
@need("exams", "committee")
def exams_use_anyway(id): return _exam_changed(id, _exam_use_anyway, "use-anyway", lambda b: f"{_short(b['room'], 60)} used anyway")

def _short(text, n):
    """text cut to n characters (the last one an ellipsis) for the history: a room name sent by the page is not trusted to be short"""
    return text if len(text) <= n else text[:n - 1] + "…"

@app.get("/api/exams/<id>/print/<what>.pdf")
@need("exams", "committee")
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
@need("timetable")
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
@need("timetable")
def exams_published_list():
    pub = store.published()
    if not pub: return {"error": NO_EXAMS_PUB}, 409
    return jsonify(exams_published.listing(pub, exams_schedules.on_site(), _exams_today(), _published_reader() == "full", cal=_exam_cal(pub)))

@app.get("/api/published/exams/<id>/print/<what>.pdf")
@need("timetable")
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
@need("timetable")
def exams_my_duties():
    """a person's own exam duties, signed in by name any way (the shared committee code: no one's, so none)"""
    pub = store.published()
    if not pub: return {"error": NO_EXAMS_PUB}, 409
    rights = _exams_rights(pub)
    if rights is None: return {"error": ONLY_OWN_DUTIES}, 403   # the shared heads', teacher and student codes are nobody's
    return jsonify(exams_published.my_duties(pub, _exam_cal(pub), exams_schedules.on_site(), rights[1], _exams_today()))

@app.get("/api/me/exams")
@need("own")
def exams_my_exams():
    pub = store.published(); sid = _exams_student()
    if not pub or sid not in {x["id"] for x in pub["model"].get("students") or []}: return {"error": "Please sign in again."}, 401
    return jsonify(exams_published.my_exams(pub, _exam_cal(pub), exams_schedules.on_site(), sid, _exams_today()))

@app.get("/api/exams/<id>/download.xlsx")
@need("exams", "committee")
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
                                          exclude=d["names"] if approved else (), elsewhere=exams_schedules.elsewhere(s.get("id"), pub["model"], own=s))

@app.get("/api/exams/<id>/who")
@need("exams", "committee")
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
def _away_texts(pub, s, records=None):
    """the texts that say who on an approved schedule is away in relief (from today); [] for any other schedule. records:
    relief's (read here when None)"""
    try:
        return [x["text"] for x in exams_relief_links.away_on(s, pub["model"], relief_absences.all_records() if records is None else records, _exams_today())]
    except (ValueError, KeyError, TypeError):
        return []

def _with_away(rows, pub):
    """each list row with away (_away_texts) for an approved schedule, [] for any other; relief's records are read once"""
    saved, records = {s["id"]: s for s in exams_schedules.all_saved()}, None
    for r in rows:
        on = r["id"] in saved and r.get("status") in ("approved", "changes")
        if on and records is None: records = relief_absences.all_records()
        r["away"] = _away_texts(pub, saved[r["id"]], records) if on else []
    return rows

def _reviewed(s):
    """the copy a review reads (exams.review.review, exams.events.review): the approved one when s is approved, else s"""
    return (exams_approval.as_schedule(s) if s.get("status") == "approved" else None) or s

def _exam_review_reply(pub, s):
    """the Approval tab: state, who sent and approved, what is waiting and the review a committee reads"""
    model, xset = pub["model"], exams_settings.load(pub)
    stale = exams_make.stale(s, xset, model)
    errors = exams_papers.check(s, model, _exam_cal(pub), xset["rules"])["errors"]
    st = s.get("status") or "draft"
    rv = exams_review.review(pub, _exam_cal(pub), s, xset, exams_schedules.elsewhere(s.get("id"), pub["model"], own=_reviewed(s))) if s.get("made") else None
    if rv: _backups_left(rv, lambda: exams_make.lesson_lists(pub, _exam_cal(pub), exams_approval.as_schedule(s) if rv.get("copy") == "approved" else s), s, pub)
    return jsonify(rev=exams_schedules.rev_of(s), status=st, label=exams_approval.label(s, _exams_today()), note=s.get("note") or "", sent_at=s.get("sent_at"), sent_by=s.get("sent_by"),
                   approved_at=s.get("approved_at"), approved_by=s.get("approved_by"),
                   changed=s.get("sent_fp") is not None and s.get("sent_fp") != exams_approval.fp(s),
                   can_send=exams_approval.blocked(s, model, stale, errors), can_approve=_exams_can_approve(),
                   unsent=exams_approval.changes(s, model) if st == "approved" else [], review=rv, away=_away_texts(pub, s))

# what the history says for each step the schedule's own log records (the log keeps the note and the details); "sent back"
# names who it goes back to: the exams committee, or an event's teacher in charge
EXAM_STEPS = {"sent": "sent to the timetable committee", "sent again": "sent to the timetable committee again",
              "changes sent": "changes sent to the timetable committee", "approved": "approved: on the main site",
              "changes approved": "changes approved: on the main site", "sent back": "sent back to {who}",
              "changes sent back": "changes sent back to {who}", "withdrawn": "withdrawn from the main site",
              "replaced": "someone away replaced at once", "in charge": "teacher in charge changed"}

def _exam_step_words(s):
    """the history's words for the step act() has just logged on s: its log's newest entry"""
    e = (s.get("log") or [{}])[-1]
    words = EXAM_STEPS.get(e.get("what"), str(e.get("what") or "changed")).replace("{who}", exams_approval.WHO.get(s.get("kind"), "the exams committee"))
    return f"{words} ({e['detail']})" if e.get("what") in ("changes sent", "replaced", "in charge") and e.get("detail") else words

def _exam_approval(id, act, what, approver=False, check=False, event=False):
    """run act(pub, sched, who, now, body) on the stored schedule, save, record it in the history (what: the entry's kind
    of step) and answer with the review; locked from loading to saving, as _exam_changed is. Only Send checks the schedule
    against the timetable (check=True): approve, send back, withdraw and someone is away still work after a new publish.
    event=True: the same for an event (its rights, wording and reply). approver: the timetable committee's alone (True, or
    the sentence anyone else is refused with)"""
    with exams_schedules.editing():
        if event: pub, who, s, _, err = _event_gate(id)
        else: (pub, who, err), s = _exams_gate(), None
        if err: return err
        if approver and not _exams_can_approve(): return {"error": ONLY_APPROVE if approver is True else approver}, 403
        if not event:
            s, err = _exam_or_404(id)
            if err: return err
        try: act(pub, s, who, exams_schedules._now(), _exam_json())
        except ValueError as e: return {"error": str(e)}, 400
        except BAD_INPUT: return {"error": exams_schedules.EVENT_WRONG if event else exams_schedules.WRONG}, 400
        saved, bad = _save_exam(s, pub, who, what, _exam_step_words(s), check=check, event=event)
        if not bad: _relief_sync(pub, saved)     # inside the lock: two syncs of one schedule never run at once
    return bad or (_event_review_reply if event else _exam_review_reply)(pub, saved)

@app.get("/api/exams/<id>/review")
@need("exams", "committee")
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
@need("exams", "committee")
def exams_send(id): return _exam_approval(id, _exam_send, "send", check=True)

def _act_approve(pub, s, by, now, b): exams_approval.approve(s, by, now)
def _act_send_back(pub, s, by, now, b): exams_approval.send_back(s, b.get("note"), by, now)
def _act_withdraw(pub, s, by, now, b): exams_approval.withdraw(s, by, now)

@app.post("/api/exams/<id>/approve")
@need("exams", "committee")
def exams_approve(id): return _exam_approval(id, _act_approve, "approve", approver=True)

@app.post("/api/exams/<id>/send-back")
@need("exams", "committee")
def exams_send_back(id): return _exam_approval(id, _act_send_back, "send-back", approver=True)

@app.post("/api/exams/<id>/withdraw")
@need("exams", "committee")
def exams_withdraw(id): return _exam_approval(id, _act_withdraw, "withdraw", approver=True)

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
@need("exams", "committee")
def exams_away(id): return _exam_approval(id, _exam_away, "away")

def _set_handled(pub, s, b, event):
    """Handled ourselves on (handled true) or off for one backup lesson: body {teacher, key, handled}; refused unless it is a
    backup of the working copy now. The list stays out of the approved copy and the fingerprint. -> the history's words
    for the change"""
    teacher, key, on = b.get("teacher"), b.get("key"), b.get("handled")
    if not isinstance(teacher, str) or not isinstance(key, str) or not isinstance(on, bool):
        raise ValueError(exams_schedules.EVENT_WRONG if event else exams_schedules.WRONG)
    items = (exams_events if event else exams_make).lesson_lists(pub, _exam_cal(pub), s)["backup"]
    item = next((x for x in items if x["teacher"] == teacher and x["key"] == key), None)
    if item is None: raise ValueError(NO_BACKUP)
    tag = "%s|%s" % (teacher, key)
    s["handled"] = [x for x in s.get("handled") or [] if isinstance(x, str) and x != tag] + ([tag] if on else [])
    lesson = f"{teacher}'s {', '.join(item.get('classes') or [])} {item.get('subject') or ''} on {exams_days.nice(item['date'])} {item['start']}–{item['end']}"
    return f"{lesson} handled ourselves" if on else f"{lesson} no longer handled ourselves"

def _handled(pub, who, s, event):
    """save a Handled ourselves change (no check: it works after a new publish too), record it in the history (what
    "handled"), sync relief and answer as the view"""
    try: words = _set_handled(pub, s, _exam_json(), event)
    except ValueError as e: return {"error": str(e)}, 400
    except BAD_INPUT + (IndexError,): return {"error": exams_schedules.EVENT_WRONG if event else exams_schedules.WRONG}, 400
    saved, bad = _save_exam(s, pub, who, "handled", words, check=False, event=event)
    if bad: return bad
    _relief_sync(pub, saved)
    return (_event_view_reply if event else _exam_view_reply)(pub, saved)

@app.post("/api/exams/<id>/handled")
@need("exams", "committee")
def exams_handled(id):
    pub, who, err = _exams_gate()
    if err: return err
    with exams_schedules.editing():
        s, err = _exam_or_404(id)
        return err or _handled(pub, who, s, False)

# ------------------------------------------------------------------------------------------------ staff: events
def _event_others(pub, s):
    """(the other schedules' copies, what they and relief hold busy) for an event (the copy s)"""
    others = exams_schedules.copies(s.get("id"))
    return others, exams_schedules.busies(others, pub["model"]) + exams_schedules.relief_busy(pub["model"], s.get("id"), s)

def _event_review(pub, cal, s, busy, others):
    """others and busy: _event_others of s (what Send reads); an approved event's review reads its approved copy instead"""
    own = _reviewed(s)
    if own is not s: others, busy = _event_others(pub, own)
    rv = exams_events.review(pub, cal, s, busy, others)
    copy = lambda: exams_approval.as_schedule(s) if rv.get("copy") == "approved" else s
    return _backups_left(rv, lambda: exams_events.lesson_lists(pub, cal, copy()), s, pub)

def _event_review_reply(pub, s):
    """the Approval tab of an event: as an exam's, with the event's own review and what stops Send"""
    model, cal = pub["model"], _exam_cal(pub)
    others, busy = _event_others(pub, s)
    st = s.get("status") or "draft"
    return jsonify(rev=exams_schedules.rev_of(s), status=st, label=exams_approval.label(s, _exams_today()), note=s.get("note") or "", sent_at=s.get("sent_at"), sent_by=s.get("sent_by"),
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
    return dict(rev=exams_schedules.rev_of(s), summary=dict(days=[dict(date=e["date"], day=e["day"], levels=e["levels"], whole=bool(entry(e["date"]).get("whole", True)),
                                        window=[exams_days.hhmm(e["start"]), exams_days.hhmm(e["end"])]) for e in exams_days.dates(s, cal, model)]),
                classes=[c["name"] for c in model.get("classes") or [] if c["name"] in inside], going=exams_events.going(pub, cal, s, busy),
                lessons=_marked(exams_events.lesson_lists(pub, cal, s), s, pub, cal), freed=exams_events.freed(pub, cal, s, busy), flags=exams_events.flags(pub, cal, s),
                cuts=exams_events.cuts(pub, cal, s), clashes=exams_events.clashes(pub, cal, s, busy, others),
                periods=[[exams_days.hhmm(a), exams_days.hhmm(b)] for a, b in exams_days.bounds(model)], rooms=[r["name"] for r in model.get("rooms") or []],
                depts=sorted({d for p in people for d in p["depts"]}), people=[p["name"] for p in people])

@app.get("/events/<id>")
@need("committee", "timetable")
def events_one_page(id):
    """the event editor, for the timetable committee and anyone signed in by name (the event then says whether they may
    open it: its teacher in charge); the shared heads', teacher and student codes are nobody's: their own page"""
    if _event_rights(None) is None: return redirect("/")
    return app.send_static_file("exams.html")

def _may_be_in_charge(pub, name):
    """raises unless name is someone the timetable committee may put in charge of an event: anyone relief and exams know"""
    if not isinstance(name, str) or not name.strip(): raise ValueError(PICK_IN_CHARGE)
    if name not in {p["name"] for p in relief_staff(pub)}: raise ValueError(f"{name} is not on the published timetable or the staff list.")

@app.get("/api/events")
@need("committee", "timetable")
def events_list():
    pub, who, _, every, err = _event_gate()
    if err: return err
    m = pub["model"]
    return jsonify(schedules=_with_away(exams_schedules.listing(_exams_today(), exams_make.published_at(pub), ("event",), None if every else who), pub),
                   levels=m.get("levels") or [], classes=[[c["name"], c["level"]] for c in m.get("classes") or []],
                   calendar_ok=bool(_exam_cal(pub).get("terms")), people=[p["name"] for p in relief_staff(pub)] if every else [])

@app.post("/api/events")
@need("committee", "timetable")
def events_create():
    pub, who, _, every, err = _event_gate()
    if err: return err
    if not _exam_cal(pub).get("terms"): return {"error": exams_schedules.NO_CALENDAR}, 409
    b = _exam_json()
    in_charge = b.get("in_charge")
    if every:
        try: _may_be_in_charge(pub, in_charge)
        except ValueError as e: return {"error": str(e)}, 400
    else: in_charge = who
    try: sched = exams_schedules.new_event(b["name"], b["levels"], b.get("classes") or [], b["start"], b["end"], who, in_charge)
    except ValueError as e: return {"error": str(e)}, 400
    except BAD_INPUT: return {"error": exams_schedules.EVENT_WRONG}, 400
    with exams_schedules.editing():
        saved, bad = _save_exam(sched, pub, who, "create", "created", event=True)
    return bad or jsonify(saved)

@app.get("/api/events/<id>")
@need("committee", "timetable")
def events_get(id):
    pub, who, s, _, err = _event_gate(id)
    return err or jsonify(s)

@app.put("/api/events/<id>")
@need("committee", "timetable")
def events_put(id):
    with exams_schedules.editing():   # from loading to saving: what is kept is what is stored now
        pub, who, old, _, err = _event_gate(id)
        if err: return err
        stale = _stale_rev(old, _exam_json(), event=True)
        if stale: return stale
        new = dict(_exam_json(), **{k: old.get(k) for k in EVENT_KEEPS})
        new["log"] = old.get("log") or []
        saved, bad = _save_exam(new, pub, who, "edit", "changed", event=True)
    return bad or jsonify(saved)

@app.delete("/api/events/<id>")
@need("committee", "timetable")
def events_delete(id):
    with exams_schedules.editing():
        pub, who, s, _, err = _event_gate(id)
        if err: return err
        if s.get("approved"): return {"error": ON_SITE}, 409
        exams_schedules.delete(id)
    _exams_entry("delete", f"{s.get('name')}: deleted", s.get("id"), "/exams")   # the event is gone: the entry links to the list
    return {"ok": True}

def _event_view_reply(pub, s):
    try: return jsonify(_event_view(pub, s))
    except ValueError as e: return {"error": str(e)}, 400
    except BAD_INPUT + (IndexError,): return {"error": exams_schedules.EVENT_WRONG}, 400

@app.get("/api/events/<id>/view")
@need("committee", "timetable")
def events_view(id):
    pub, who, s, _, err = _event_gate(id)
    return err or _event_view_reply(pub, s)

@app.post("/api/events/<id>/fill")
@need("committee", "timetable")
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
        saved, bad = _save_exam(s, pub, who, "fill", f"{len(added)} added to the people going ({EVENT_FILLS[b['way']]})", event=True)
    return bad or jsonify(saved)

# how the history names each way of filling the going list
EVENT_FILLS = {"form teachers": "the form teachers", "teachers then": "the teachers who would teach them then",
               "department": "a department", "people": "picked people"}

def _event_send(pub, s, by, now, b):
    others, busy = _event_others(pub, s)
    exams_approval.send(s, pub["model"], by, now, False, exams_events.send_errors(pub, _exam_cal(pub), s, busy, others))

def _event_free(pub, s):
    """who may stand in for someone going with the approved event: the names relief finds free then (freed, then free)"""
    ap = exams_approval.as_schedule(s)
    if ap is None: raise ValueError(exams_approval.NOT_ON_SITE)
    return exams_events.who_free(pub, _exam_cal(pub), ap, exams_schedules.elsewhere(s.get("id"), pub["model"], own=ap))

def _event_away(pub, s, by, now, b):
    away, name = b["away"], b["name"]
    if not all(isinstance(x, str) for x in (away, name)): raise ValueError(exams_schedules.EVENT_WRONG)
    if name not in {c["name"] for g in ("freed", "free") for c in _event_free(pub, s)[g]}: raise ValueError("%s is not free then." % name)
    exams_approval.replace_going(s, away, name, by, now)

@app.get("/api/events/<id>/review")
@need("committee", "timetable")
def events_review_get(id):
    pub, who, s, _, err = _event_gate(id)
    return err or _event_review_reply(pub, s)

@app.post("/api/events/<id>/send")
@need("committee", "timetable")
def events_send(id): return _exam_approval(id, _event_send, "send", check=True, event=True)

@app.post("/api/events/<id>/approve")
@need("committee", "timetable")
def events_approve(id): return _exam_approval(id, _act_approve, "approve", approver=True, event=True)

@app.post("/api/events/<id>/send-back")
@need("committee", "timetable")
def events_send_back(id): return _exam_approval(id, _act_send_back, "send-back", approver=True, event=True)

@app.post("/api/events/<id>/withdraw")
@need("committee", "timetable")
def events_withdraw(id): return _exam_approval(id, _act_withdraw, "withdraw", approver=True, event=True)

@app.post("/api/events/<id>/away")
@need("committee", "timetable")
def events_away(id): return _exam_approval(id, _event_away, "away", event=True)

@app.post("/api/events/<id>/handled")
@need("committee", "timetable")
def events_handled(id):
    with exams_schedules.editing():
        pub, who, s, _, err = _event_gate(id)
        return err or _handled(pub, who, s, True)

def _event_in_charge(pub, s, by, now, b):
    _may_be_in_charge(pub, b.get("name"))
    exams_approval.set_in_charge(s, b["name"], by, now)

@app.post("/api/events/<id>/in-charge")
@need("committee", "timetable")
def events_in_charge(id):
    """{name}: the timetable committee gives the event to another teacher in charge, at once (exams.approval.set_in_charge)"""
    return _exam_approval(id, _event_in_charge, "in-charge", approver=ONLY_GIVES, event=True)

@app.get("/api/events/<id>/who")
@need("committee", "timetable")
def events_who(id):
    pub, who, s, _, err = _event_gate(id)
    if err: return err
    try: return jsonify(_event_free(pub, s))
    except ValueError as e: return {"error": str(e)}, 400

startup_log()
move_relief_lists()
try: students.resume_files()                                     # the files to download, if a restart found them behind a student change
except Exception as e: print("warning: the files to download were not resumed (" + type(e).__name__ + ")", file=sys.stderr)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), debug=False)

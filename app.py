"""School timetable app (one school per deployment).

Committee (COMMITTEE_CODE): fill the setup step by step, download it with the timetable skill for an outside AI agent
to make the timetable, then upload that timetable, check it and publish it.
Teachers (TEACHER_CODE): every published class, teacher, room and student timetable, Who's free, PDFs.
Students (STUDENT_CODE): class timetables and 'Build my timetable'; personal codes show one student's own timetable.
Staff (a personal code each, made from their name): the Relief module and everything the teacher code opens."""
import copy, datetime, gzip, hmac, io, os, re, shutil, sys, tempfile, time, traceback, urllib.parse, zipfile
from functools import wraps
from flask import Flask, jsonify, request, send_file, abort, session, redirect, Response, g
from werkzeug.middleware.proxy_fix import ProxyFix
from ttgen.samples import secondary, primary
from ttgen.template import write_template
from ttgen.reader import read_template
from ttgen.spec import RULE_TYPES, SCOPES, CODES, SETTING_RULES, ROLES, SKILL_VERSION, defaults, typed_rules
import access, checks, draft, history, store, sync, typed
from accounts import passwords, people, rights as rights_table
from relief import codes as relief_codes, people as relief_people, settings as relief_settings
from ttgen import choices
import exams.days as exams_days, exams.settings as exams_settings, exams.schedules as exams_schedules, exams.papers as exams_papers, exams.invigilate as exams_invigilate, exams.make as exams_make, exams.seating as exams_seating, exams.printouts as exams_printouts

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
RIGHTS = frozenset({"committee", "setup", "timetable", "files", "history", "codes", "admin", "own", "exams",
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
    if people.admins(people.load()):   # people sign in as themselves now: a shared code left unset is not a problem
        unset = {f"{var} is not set in Railway variables." for _, var in access.ROLES}
        probs = [p for p in probs if p not in unset]
    if not store.on_volume(): probs.append("No Railway volume: the setup and the published timetable are lost on the next deploy. Add a volume mounted at /data.")
    return probs

def startup_log():
    print(f"Timetable app: data in {store.DATA}", file=sys.stderr, flush=True)
    for p in setup_problems(): print(f"WARNING: {p}", file=sys.stderr, flush=True)

def page(title, body):
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)}</title>
<link rel="stylesheet" href="/static/login.css"></head><body>{body}</body></html>"""

# ------------------------------------------------------------------------------------------------ signing in
CODE_LABEL = "Your personal code (on the slip from the school)"
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

def _code_page(msg=""):
    err, warn = (f"<p class='err'>{esc(msg)}</p>" if msg else ""), _warnings()
    return page("Sign in", f"""<main class="front"><header class="hero"><h1>{esc(school_name())}</h1><p>Timetable</p></header>
<div class="login one"><form method="post" action="/login"><label for="code">{esc(CODE_LABEL)}</label>
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
    entry = {"kind": "signin", "ok": ok, "via": how, "shared": shared_, "who": name, "as": as_, "reason": reason,
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
    try: history.add({"kind": "account", "what": what, "people": [name], "changes": [], "text": text, **by()})
    except Exception as e: print(f"WARNING: an account change could not be recorded in the history ({type(e).__name__})", file=sys.stderr, flush=True)

def _note_signin(name):
    """the time on the person's record (the last two are kept); a sign-in never fails for want of it"""
    def change(d):
        r = d["people"].get(name)
        if not isinstance(r, dict): r = d["people"][name] = {}
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
        x = d["people"].setdefault(p["name"], {})
        n = people.record(d, p["name"])["n"] + 1
        x.update(pw=h, must_change=False, n=n)
        return n
    try: n = people.update(change)
    except people.Unreadable: return _change_page(p, people.UNREADABLE), 503
    session["n"] = n   # this session stays; every other one of this person's ends (its number is old)
    _record_account("password", p["name"], "Changed their password")
    return redirect("/home")

def _recovery_used(data, code):
    return any(passwords.check_pw(h, code) for h in data["ways"]["recovery_used"] if isinstance(h, str))

@app.route("/login/recover", methods=["GET", "POST"])
def login_recover():
    """while ADMIN_RECOVERY_CODE is set: an admin's username and that code (accepted once per value) set a new password"""
    code = (os.environ.get("ADMIN_RECOVERY_CODE") or "").strip()
    if not code: abort(404)
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
    if not right or name not in people.admins(data):
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
    session.clear(); return redirect("/login")

# the tiles of the home page, in order: (title, what it opens, link, the rights that show it)
TILES = (("Committee page", "Set up, check and publish the timetable", "/", ("setup",)),
         ("Timetables", "Classes, teachers, rooms, Who's free", "/timetable", ("timetable",)),
         ("Relief", "Ask for relief, your reliefs", "/relief", ("relief", "relief.settings")),
         ("Exams and events", "", "/exams", ("exams",)),
         ("Admin", "Staff, students and the ways in", "/admin", ("admin",)),
         ("History", "Who changed what, and when", "/history", ("history",)))
GREYED = ("Committee page", "Admin")   # signed in with a code, these wait for the password
TO_PASSWORD = "Sign in with your password to open this."
_HOW = {"code": "Signed in with your code", "password": "Signed in with your password"}

def _route_exists(path):
    return any(r.rule == path for r in app.url_map.iter_rules())

def _tiles(p):
    """the tiles for the person p, in order, as (title, line, link, greyed): those they may open, and greyed those only
    their password opens (a committee member's or a head's code opens all but the setup and the admin page)"""
    mine, strong = rights(), (rights_table.rights(p, "password") if via() == "code" else frozenset())
    out = []
    for title, line, link, need_ in TILES:
        if link == "/exams" and not _route_exists("/exams"): continue
        if mine & set(need_):
            out.append((title, f"Until {_day(p['extras'].get('exams'))}" if link == "/exams" else line, link, False))
        elif title in GREYED and strong & set(need_): out.append((title, TO_PASSWORD, "/login/password", True))
    return out

@app.get("/home")
@need("timetable")
def home():
    """a person's tiles: only what they may open; with one tile (and nothing waiting for the password) it opens at once"""
    p = who()
    if p is None: return redirect("/")   # a shared code is nobody's: its own page
    got = _tiles(p)
    if len(got) == 1 and not got[0][3]: return redirect(got[0][2])
    tiles = "".join(f'<a class="tile{" off" if off else ""}" href="{link}"><b>{esc(title)}</b><span class="muted small">{esc(line)}</span></a>'
                    for title, line, link, off in got)
    change = ' · <a href="/account/password">Change password</a>' if via() == "password" else ""
    return page("Home", f"""<main class="home"><header class="hello"><h1>Hello, {esc(p["name"])}</h1>
<p class="muted small">{esc(_HOW.get(via(), "Signed in"))}{change} · <a href="/logout">Sign out</a></p></header>
<nav class="tiles">{tiles}</nav><p class="muted small foot">{esc(school_name())}</p></main>""")

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
            history.add_many([{"kind": "account", "what": "ended", "who": None, "as": "The app", "via": "app", "people": [n],
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
    try: v, refused, mine = store.apply_changes(ops, client, since=since, filter=split, by=by())
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
@need("setup")
def status():
    """what the committee page shows. who: the person signed in (None for a shared code); depts: a head's departments
    when signed in by name (None otherwise); shared: the shared code's role; admin_exists: an admin has been named"""
    have, probs = access.configured()
    _, at = store.load_setup()
    p = who()
    mine = dict(who=p["name"] if p else None, via=via(), depts=head_depts(), rights=sorted(rights()), shared=shared(),
                admin_exists=bool(people.admins(people.load())))
    if not has("committee"): return jsonify(role="head", volume=store.on_volume(), setup_saved_at=at, published=pub_info(), **mine)
    return jsonify(role="committee", codes=have, code_problems=probs, volume=store.on_volume(), setup_saved_at=at, published=pub_info(), draft=draft.summary(), typed=typed.enabled(), **mine)

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
TABS = dict(committee=None, teacher=["classes", "teachers", "rooms", "students", "lessons", "free"], student=["classes", "students"])

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
        app_cfg = dict(mode=r, tabs=TABS[r], pdf=True, logout="/logout", files=files_for(r),
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
    return Response(render_html(pub["model"], "personal", student_id=sid, app=dict(mode="personal", tabs=[], pdf=True, logout="/logout")), mimetype="text/html")

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
NO_RELIEF_PUB = "Publish the timetable first: relief reads the teachers from it."
ONLY_SETTINGS = "Only the timetable committee and the relief team can change relief settings."
ONLY_CODES = "Only the timetable committee can download the codes."

def relief_staff(pub):
    """the people relief knows: the published timetable's teachers and the staff added in the accounts"""
    return people.staff(pub)

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
    p = who()
    if p is None: return {"error": "Please sign in again."}, 401
    pub = bool(store.published())   # nothing published: a publish may be swapping folders, so no departments, but the person still answers
    return jsonify(name=p["name"], depts=p["depts"] if pub else [], published=pub, on_team=bool(p["extras"].get("relief")), on_management=p["group"] in people.MANAGEMENT,
                   can_settings=has("relief.save"))

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
    return jsonify(settings=settings, lists=lists, can_admin=has("admin"), people=relief_people.people(pub, [dict(name=n) for n in lists["added"]]), roles=relief_settings.role_names(pub), weeks=m["school"]["weeks"], can_save=rights[1], can_codes=has("codes"))

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
    refused = _relief_codes_refused(); pub = store.published()
    if refused: return refused
    if not pub: return NO_RELIEF_PUB, 409
    buf = io.BytesIO()
    relief_codes.slips_pdf(pub["model"]["school"]["name"], relief_staff(pub), request.host_url.rstrip("/"), buf)
    buf.seek(0)
    return send_file(buf, as_attachment=True, download_name="relief code slips.pdf", mimetype="application/pdf")

# ------------------------------------------------------------------------------------------------ staff: exams and events
NO_EXAMS_PUB = "Publish the timetable first: exams read the classes, students and lessons from it."
ONLY_EXAMS = "Only the exams committee and the timetable committee can open exams."
NO_STUDENTS = "The published timetable has no students. Add them on the Students step and publish again to seat them."
NO_EXAM = "That exam is not there any more."
EXAM_KEEPS = ("id", "created_at", "created_by", "made", "pins", "use_anyway", "status")
BAD_INPUT = (TypeError, KeyError, AttributeError)

def _exams_rights(pub):
    """(may use exams, saved by) for whoever is signed in, from the accounts: the Exams and events extra (until its end
    date) or the timetable committee; saved by the person's name, or "Timetable committee" for the shared committee code.
    None when nobody is signed in by name or with the committee code"""
    p = who()
    if p is None: return (True, "Timetable committee") if has("committee") else None
    return has("exams") or has("committee"), p["name"]

def _exams_gate():
    """-> (pub, who, None) when the person may use exams, else (None, None, the refusing answer)"""
    pub = store.published()
    if not pub: return None, None, ({"error": NO_EXAMS_PUB}, 409)
    rights = _exams_rights(pub)
    if rights is None: return None, None, ({"error": "Please sign in again."}, 401)
    if not rights[0]: return None, None, ({"error": ONLY_EXAMS}, 403)
    return pub, rights[1], None

def _exam_cal(pub): return relief_settings.load(pub)["calendar"]

def _exam_json():
    d = request.get_json(force=True, silent=True)
    return d if isinstance(d, dict) else {}

def _exams_entry(what, text, exam=None):
    """one history entry for an exams save: who, what, which, a link (not field by field; exams keeps its own record). A
    failure to write it never fails the save"""
    e = {"kind": "exams", "what": what, "where": "Exams and events", "text": text, "link": "/exams", **by()}
    if exam: e["exam"] = exam
    try: history.add(e)
    except Exception as x: print(f"WARNING: an exams change could not be recorded in the history ({type(x).__name__})", file=sys.stderr, flush=True)

def _save_exam(sched, pub, saved_by, what, words):
    """save a schedule and record it in the history as "<its name>: <words>"; (the saved schedule, None) or (None, the
    400 answer): malformed JSON never gives a 500"""
    try: saved = exams_schedules.save(sched, pub, _exam_cal(pub), saved_by)
    except ValueError as e: return None, ({"error": str(e)}, 400)
    except BAD_INPUT: return None, ({"error": exams_schedules.WRONG}, 400)
    _exams_entry(what, f"{saved['name']}: {words}", saved.get("id"))
    return saved, None

def _exam_view(pub, sched):
    model, cal = pub["model"], _exam_cal(pub)
    by_id = {x["id"]: x for x in model.get("students") or []}
    papers = sched.get("papers") or []
    levels, classes = set(sched.get("levels") or []), set(sched.get("classes") or [])
    mine = {x["id"] for x in model.get("students") or [] if exams_papers._student_level(model, x) in levels or x.get("cls") in classes}
    sids = sorted(mine | {i for p in papers for i in exams_papers.who_sits(p, model)})
    return dict(summary=exams_make.summary(pub, cal, sched, exams_settings.load(pub)), lessons=exams_make.lesson_lists(pub, cal, sched),
                made=sched.get("made"), students={i: [by_id[i]["name"], by_id[i]["cls"]] for i in sids if i in by_id},
                counts={p.get("id"): len(exams_papers.who_sits(p, model)) for p in papers}, periods=[[exams_days.hhmm(a), exams_days.hhmm(b)] for a, b in exams_days.bounds(model)],
                rooms=exams_settings.load(pub)["rooms"], students_missing=not model.get("students"), levels=list(model.get("levels") or []),
                rooms_by_key=_exam_rooms_by_key(pub, cal, sched), stale=exams_make.stale(sched, exams_settings.load(pub)))

def _exam_rooms_by_key(pub, cal, sched):
    """for each sitting, every exam room with its seats and what keeps it busy then (empty text: free); a room another
    overlapping sitting of the made schedule holds is busy, so the move selects do not offer it"""
    xset = exams_settings.load(pub)
    held = exams_make.held(pub, sched, xset)
    return {x["key"]: [[r["name"], r["seats"], r["busy"]] for r in exams_seating.rooms_free(pub, cal, sched, x, xset, held.get(x["key"], set()))]
            for x in exams_seating.sittings(sched)}

@app.get("/exams")
@need("exams", "committee")
def exams_home(): return app.send_static_file("exams.html")

@app.get("/exams/settings")
@need("exams", "committee")
def exams_settings_page():
    move_relief_lists()
    return app.send_static_file("exams-settings.html")

@app.get("/exams/<id>")
@need("exams", "committee")
def exams_one_page(id): return app.send_static_file("exams.html")

@app.get("/api/exams/me")
@need("exams", "committee")
def exams_me():
    pub = store.published()
    if not pub: return {"error": NO_EXAMS_PUB}, 409
    rights = _exams_rights(pub)
    if rights is None: return {"error": "Please sign in again."}, 401
    return jsonify(name=rights[1], can_use=rights[0], home="/home" if who() else "/")   # a person's way back is their home page

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
    return jsonify(schedules=exams_schedules.listing(), levels=m.get("levels") or [], classes=[[c["name"], c["level"]] for c in m.get("classes") or []],
                   calendar_ok=bool(_exam_cal(pub).get("terms")))

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

def _exam_or_404(id):
    s = exams_schedules.load(id)
    return (s, None) if s else (None, ({"error": NO_EXAM}, 404))

@app.get("/api/exams/<id>")
@need("exams", "committee")
def exams_get(id):
    pub, who, err = _exams_gate()
    if err: return err
    s, err = _exam_or_404(id)
    return err or jsonify(s)

@app.put("/api/exams/<id>")
@need("exams", "committee")
def exams_put(id):
    pub, who, err = _exams_gate()
    if err: return err
    old, err = _exam_or_404(id)
    if err: return err
    new = dict(_exam_json(), **{k: old.get(k) for k in EXAM_KEEPS})
    saved, bad = _save_exam(new, pub, who, "edit", "changed")
    return bad or jsonify(saved)

@app.delete("/api/exams/<id>")
@need("exams", "committee")
def exams_delete(id):
    pub, who, err = _exams_gate()
    if err: return err
    s = exams_schedules.load(id)
    exams_schedules.delete(id)
    if s: _exams_entry("delete", f"{s.get('name')}: deleted", s.get("id"))   # nothing there, nothing deleted: no entry
    return {"ok": True}

@app.post("/api/exams/<id>/fill")
@need("exams", "committee")
def exams_fill(id):
    pub, who, err = _exams_gate()
    if err: return err
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
    s, err = _exam_or_404(id)
    if err: return err
    f = request.files.get("file")
    if not f: return {"error": "Choose the paper list to upload."}, 400
    try: rows = exams_papers.read_paper_list(f.read())
    except ValueError as e: return {"error": str(e)}, 400
    s["papers"] = [p for p in s.get("papers") or [] if p.get("who") == "students"] + rows
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
    view does"""
    pub, who, err = _exams_gate()
    if err: return err
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
def exams_use_anyway(id): return _exam_changed(id, _exam_use_anyway, "use-anyway", lambda b: f"{b['room']} used anyway")

@app.get("/api/exams/<id>/print/<what>.pdf")
@need("exams", "committee")
def exams_print(id, what):
    pub, who, err = _exams_gate()
    if err: return err
    s, err = _exam_or_404(id)
    if err: return err
    if what not in exams_printouts.WHATS: abort(404)
    if not s.get("made"): return {"error": "Press Make first."}, 409
    if exams_make.stale(s, exams_settings.load(pub)): return {"error": exams_make.STALE}, 409
    from ttgen.export import safe_name
    buf = io.BytesIO()
    exams_printouts.pdf(what, pub, _exam_cal(pub), s, exams_settings.load(pub), buf)
    buf.seek(0)
    return send_file(buf, as_attachment=False, download_name=safe_name(f"{s.get('name')} {exams_printouts.TITLES[what]}") + ".pdf", mimetype="application/pdf")

@app.get("/api/exams/<id>/download.xlsx")
@need("exams", "committee")
def exams_download(id):
    pub, who, err = _exams_gate()
    if err: return err
    s, err = _exam_or_404(id)
    if err: return err
    if not s.get("made"): return {"error": "Press Make first."}, 409
    if exams_make.stale(s, exams_settings.load(pub)): return {"error": exams_make.STALE}, 409
    from ttgen.export import safe_name
    return send_file(io.BytesIO(exams_printouts.xlsx(pub, _exam_cal(pub), s, exams_settings.load(pub))), as_attachment=True,
                     download_name=safe_name(s.get("name")) + ".xlsx", mimetype=XLSX)

@app.get("/api/exams/<id>/who")
@need("exams", "committee")
def exams_who(id):
    pub, who, err = _exams_gate()
    if err: return err
    s, err = _exam_or_404(id)
    if err: return err
    key, room = request.args.get("key", ""), request.args.get("room", "")
    duties = (s.get("made") or {}).get("duties") or []
    d = next((x for x in duties if x["key"] == key and x["room"] == room), None)
    if d is None: return {"error": "Press Make first."}, 404
    sit = next((x for x in exams_seating.sittings(s) if x["key"] == key), None)
    papers = {p["id"]: p for p in s.get("papers") or []}
    subjects = [papers[i]["subject"] for i in (sit or {}).get("papers", []) if i in papers]
    rest = [x for x in duties if x is not d]
    return jsonify(exams_invigilate.candidates(pub, _exam_cal(pub), s, exams_settings.load(pub), d["date"], d["start"], d["end"], rest, subjects=subjects))

startup_log()
move_relief_lists()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), debug=False)

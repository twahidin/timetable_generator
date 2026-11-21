"""Plain-assert tests: every route checks a right, for every kind of session (accounts stage 1).
.venv/bin/python tests/test_routes.py"""
import datetime, html, itertools, os, pickle, re, secrets, sys, tempfile, time, urllib.parse
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = tempfile.mkdtemp()
CODES = {k: secrets.token_hex(4) for k in ("COMMITTEE_CODE", "TEACHER_CODE", "STUDENT_CODE", "HEADS_CODE")}
for k in ("ADMIN_RECOVERY_CODE", "ANTHROPIC_API_KEY", "TYPED_REQUEST_MODEL", "AI_MODEL"): os.environ.pop(k, None)
os.environ.update(DATA_DIR=DATA, SECRET_KEY=secrets.token_hex(16), AI_PROVIDER="anthropic", AI_API_KEY="", **CODES)
sys.path.insert(0, ROOT)
import app as A, history as H, store, sync  # noqa: E402
from accounts import passwords as PW, people as P, rights as R  # noqa: E402
from relief import people as RP  # noqa: E402
from ttgen.samples import secondary  # noqa: E402

AGAIN = {"error": "Please sign in again."}
GREY = "Sign in with your password to open this."
TOMORROW = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
YESTERDAY = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()

# made-up people: four on the published timetable, four added by name
TINA, HAL, RIA, ELI = "Ms Tina Teo", "Mr Hal Ong", "Ms Ria Tan", "Mr Eli Ng"
CORA, ADA, LEE, EVE = "Ms Cora Lim", "Ms Ada Koh", "Mr Lee Chua", "Mdm Eve Sim"
MAX = "Mr Max Ho"   # a teacher added by name whose Exams and events extra ended yesterday
TEACHERS = [dict(name=TINA, dept="SC"), dict(name=HAL, dept="SC", role="HOD"), dict(name=RIA, dept="MA"), dict(name=ELI, dept="EL")]
PW_HASH = PW.hash_pw(secrets.token_hex(8))   # a password session ends when its record holds no password
RECORDS = {HAL: dict(group="hod", depts=["SC", "MA"], username="hal.ong", pw=PW_HASH),
           RIA: dict(extras=dict(relief=True, exams=None, admin=False)),
           ELI: dict(extras=dict(relief=False, exams=TOMORROW, admin=False)),
           CORA: dict(group="committee", added=True, username="cora.lim", pw=PW_HASH),
           ADA: dict(group="committee", added=True, username="ada.koh", pw=PW_HASH, extras=dict(relief=False, exams=None, admin=True)),
           LEE: dict(group="leader", added=True, username="lee.chua", pw=PW_HASH),
           EVE: dict(group="executive", added=True),
           MAX: dict(group="teacher", added=True, extras=dict(relief=False, exams=YESTERDAY, admin=False))}

def publish():
    """what store.published() reads: a fake school with the teachers, one class and one student"""
    pub = RP.fake_pub(TEACHERS)
    pub["meta"].update(published_at="1 Nov 2026, 09:00", ok=True)
    pub["model"].update(classes=[dict(name="1A", level="Sec 1")], class_ix={}, teacher_ix={}, room_ix={}, students=[dict(id="S001", name="Sam Student", cls="1A")])
    pub["model"]["school"]["timetable"] = "2027 Timetable"
    os.makedirs(store.PUB, exist_ok=True)
    with open(os.path.join(store.PUB, "model.pkl"), "wb") as f: pickle.dump(pub["model"], f)
    store.write_json(os.path.join(store.PUB, "meta.json"), pub["meta"])
    store._cache.update(stamp=None, value=None)
    views = store.published()["views"]   # the pages already made, so no page is rendered from the fake model
    for mode, home in itertools.product(("committee", "teacher", "student"), (None, "/", "/home", "/relief")):
        views[("view", mode, home)] = f"the {mode} page {home}"

publish()
P.update(lambda d: [d["people"].setdefault(n, {}).update(r) for n, r in RECORDS.items()])

def person(name, via):
    s = dict(who=name, via=via, n=0)
    if via == "password": s["exp"] = time.time() + 3600
    return s

BASE = {"timetable", "files", "relief"}
# every kind of session, and the rights it must hold (worked out here by hand, not by the app)
KINDS = {
    "nobody": ({}, set()),
    "shared committee": (dict(role="committee"), {"committee", "setup", "timetable", "files", "history", "codes", "relief.settings", "relief.save"}),
    "shared head": (dict(role="head"), {"setup", "timetable", "files"}),
    "shared teacher": (dict(role="teacher"), {"timetable", "files"}),
    "shared student": (dict(role="student"), {"timetable"}),
    "personal student": (dict(role="personal", sid="S001"), {"own"}),
    "committee by password": (person(CORA, "password"), BASE | {"relief.settings", "relief.save", "committee", "setup", "history", "codes"}),
    "committee by code": (person(CORA, "code"), BASE | {"relief.settings", "relief.save"}),
    "hod by password": (person(HAL, "password"), BASE | {"relief.plan", "relief.settings", "setup"}),
    "hod by code": (person(HAL, "code"), BASE | {"relief.plan", "relief.settings"}),
    "leader by password": (person(LEE, "password"), BASE | {"relief.plan", "relief.settings"}),
    "teacher by code": (person(TINA, "code"), BASE),
    "executive by code": (person(EVE, "code"), {"timetable", "files"}),
    "teacher on the relief team": (person(RIA, "code"), BASE | {"relief.plan", "relief.settings", "relief.save", "relief.team"}),
    "teacher on exams until tomorrow": (person(ELI, "code"), BASE | {"exams"}),
    "teacher whose exams ended yesterday": (person(MAX, "code"), BASE),
    "admin by password": (person(ADA, "password"), BASE | {"relief.settings", "relief.save", "committee", "setup", "history", "codes", "admin"}),
    "admin by code": (person(ADA, "code"), BASE | {"relief.settings", "relief.save"}),
    "relief stage 1 session": (dict(role="staff", who=TINA), BASE),
}

def client(keys):
    c = A.app.test_client()
    if keys:
        with c.session_transaction() as s: s.update(keys)
    return c

def kept(c):
    with c.session_transaction() as s: return dict(s)

def to_login(r): return r.status_code == 302 and urllib.parse.urlsplit(r.headers["Location"]).path == "/login"

def went(r, where): return r.status_code == 302 and urllib.parse.urlsplit(r.headers["Location"]).path == where

def by_guard(r):
    """the guard's refusal: 401 or 403 with its one sentence on the API, or a redirect to the sign-in page"""
    return (r.status_code in (401, 403) and r.get_json(silent=True) == AGAIN) or to_login(r)

def walked():
    """every rule of the app the walk covers: all but the static files and the sign-in pages, which have no guard"""
    for rule in A.app.url_map.iter_rules():
        if rule.endpoint == "static" or rule.rule.startswith("/login") or rule.rule in ("/logout", "/healthz", "/account/password"): continue
        yield rule

def walk(rules):
    """each kind of session against each rule: refused by the guard without a right the rule needs, never with one"""
    for kind, (keys, have) in KINDS.items():
        c = client(keys)
        for rule in rules:
            need = set(A.app.view_functions[rule.endpoint]._need)
            url = re.sub(r"<(?:[^:<>]+:)?[^<>]+>", "x", rule.rule)
            for method in sorted(rule.methods - {"HEAD", "OPTIONS"}):
                r = c.open(url, method=method, json={})
                if have & need:
                    assert not by_guard(r), (kind, method, url, r.status_code, r.headers.get("Location"), r.get_data(as_text=True)[:200])
                    assert r.status_code != 500, (kind, method, url)
                else:
                    assert by_guard(r), (kind, method, url, r.status_code, r.get_data(as_text=True)[:200])
                r.close()
                assert kept(c) == keys, (kind, method, url, kept(c))   # no route ends a session that still holds

COUNT = 0
def t(f):
    global COUNT
    f(); COUNT += 1
    return f

@t
def every_kind_holds_the_rights_of_the_table():
    for kind, (keys, want) in KINDS.items():
        with A.app.test_request_context():
            A.session.update(keys)
            assert set(A.rights()) == want, (kind, sorted(A.rights()), sorted(want))

@t
def every_route_has_a_guard_and_the_guard_decides():
    rules = list(walked())
    assert len(rules) > 50, len(rules)
    for rule in rules:
        view = A.app.view_functions[rule.endpoint]
        need = getattr(view, "_need", None)
        assert need and set(need) <= A.RIGHTS, (rule.rule, need)
    from ttgen import export as E
    real = E.render_html, E.student_view, E.pdf_bytes          # the walk is about the guards: no page is made from the fake school
    E.render_html, E.student_view, E.pdf_bytes = (lambda *a, **k: "a page"), (lambda *a, **k: {}), (lambda *a, **k: b"%PDF-")
    try: walk(rules)
    finally: E.render_html, E.student_view, E.pdf_bytes = real

# every guarded endpoint and the rights that open it, written out: a new or changed route must be listed here on purpose
GUARDS = {
    "admin_bulk": ('admin',),
    "admin_first": ('committee',),
    "admin_page": ('admin', 'committee'),
    "admin_people": ('admin',),
    "admin_person": ('admin',),
    "admin_reset": ('admin',),
    "admin_shared_off": ('admin',),
    "admin_students": ('admin',),
    "admin_ways": ('admin',),
    "api_blank": ('committee',),
    "api_history": ('history',),
    "api_sample": ('setup',),
    "build": ('committee',),
    "check_setup": ('committee',),
    "code_slips": ('committee',),
    "codes_csv": ('committee',),
    "dl_blank": ('committee',),
    "dl_sample": ('committee',),
    "dl_skill_md": ('committee',),
    "dl_skill_zip": ('committee',),
    "draft_about": ('committee',),
    "draft_ask": ('committee',),
    "draft_board": ('committee',),
    "draft_decide": ('committee',),
    "draft_download": ('committee',),
    "draft_fix": ('committee',),
    "draft_fixes": ('committee',),
    "draft_get": ('committee',),
    "draft_grid": ('committee',),
    "draft_lesson": ('committee',),
    "draft_options": ('committee',),
    "draft_place": ('committee',),
    "draft_preview": ('committee',),
    "draft_preview_page": ('committee',),
    "draft_printouts": ('committee',),
    "draft_publish": ('committee',),
    "draft_slots": ('committee',),
    "draft_suggest": ('committee',),
    "draft_undo": ('committee',),
    "draft_upload": ('committee',),
    "exams_create": ('exams', 'committee'),
    "exams_delete": ('exams', 'committee'),
    "exams_download": ('exams', 'committee'),
    "exams_fill": ('exams', 'committee'),
    "exams_get": ('exams', 'committee'),
    "exams_home": ('exams', 'committee'),
    "exams_invigilators": ('exams', 'committee'),
    "exams_list": ('exams', 'committee'),
    "exams_make_route": ('exams', 'committee'),
    "exams_me": ('exams', 'committee'),
    "exams_move": ('exams', 'committee'),
    "exams_one_page": ('exams', 'committee'),
    "exams_papers_download": ('exams', 'committee'),
    "exams_papers_upload": ('exams', 'committee'),
    "exams_print": ('exams', 'committee'),
    "exams_put": ('exams', 'committee'),
    "exams_settings_get": ('exams', 'committee'),
    "exams_settings_page": ('exams', 'committee'),
    "exams_settings_put": ('exams', 'committee'),
    "exams_use_anyway": ('exams', 'committee'),
    "exams_view": ('exams', 'committee'),
    "exams_who": ('exams', 'committee'),
    "export_printouts": ('committee',),
    "files": ('files',),
    "files": ('files',),
    "get_setup": ('setup',),
    "get_setup_changes": ('setup',),
    "get_setup_copies": ('committee',),
    "history_page": ('history',),
    "home": ('timetable',),
    "import_xlsx": ('committee',),
    "index": ('setup', 'timetable', 'own'),
    "me": ('own',),
    "meta": ('setup',),
    "past_setups": ('committee',),
    "pdf_custom": ('timetable',),
    "pdf_me": ('own',),
    "pdf_one": ('timetable',),
    "post_setup_changes": ('setup',),
    "put_setup": ('committee',),
    "read_table": ('committee',),
    "relief_code_slips": ('codes',),
    "relief_codes_csv": ('codes',),
    "relief_home": ('relief', 'relief.settings'),
    "relief_me": ('relief',),
    "relief_settings_get": ('relief.settings',),
    "relief_settings_page": ('relief.settings',),
    "relief_settings_put": ('relief.save',),
    # relief requests (relief/web.py): the guard is relief on every route; the narrower rights (relief.plan, relief.team)
    # are checked inside the routes, with their own sentences, and pinned in RELIEF_INSIDE further down
    "relief_web.acknowledge": ('relief',),
    "relief_web.cancel": ('relief',),
    "relief_web.create": ('relief',),
    "relief_web.download": ('relief',),
    "relief_web.free": ('relief',),
    "relief_web.lessons": ('relief',),
    "relief_web.mine": ('relief',),
    "relief_web.needed": ('relief',),
    "relief_web.not_needed": ('relief',),
    "relief_web.one": ('relief',),
    "relief_web.people": ('relief',),
    "relief_web.planned": ('relief',),
    "relief_web.planned_csv": ('relief',),
    "relief_web.relief": ('relief',),
    "relief_web.seen": ('relief',),
    "relief_web.upload": ('relief',),
    "relief_web.whats_in": ('relief',),
    "relief_web.work": ('relief',),
    "restore_setup": ('committee',),
    "status": ('setup',),
    "timetable": ('timetable',),
}

@t
def the_whole_endpoint_map_is_pinned():
    got = {r.endpoint: tuple(A.app.view_functions[r.endpoint]._need) for r in A.app.url_map.iter_rules()
           if getattr(A.app.view_functions[r.endpoint], "_need", None)}
    assert got == GUARDS, ({k: (got.get(k), GUARDS.get(k)) for k in set(got) | set(GUARDS) if got.get(k) != GUARDS.get(k)})

@t
def a_shared_code_session_is_sent_from_the_password_page_to_login():
    for role in ("teacher", "committee"):
        r = client(dict(role=role)).get("/account/password")
        assert to_login(r), (role, r.status_code, r.headers.get("Location"))

# every exams page and API route: the Exams and events extra (until its end date) or the timetable committee
EXAMS_ENDPOINTS = ("exams_home", "exams_settings_page", "exams_one_page", "exams_me", "exams_settings_get", "exams_settings_put", "exams_list",
                   "exams_create", "exams_get", "exams_put", "exams_delete", "exams_fill", "exams_papers_download", "exams_papers_upload",
                   "exams_view", "exams_make_route", "exams_move", "exams_invigilators", "exams_use_anyway", "exams_print", "exams_download", "exams_who")

# every admin API route: the Admin extra (a committee member signed in with their password); the first admin: the committee; the
# admin page: an admin, or the committee (sent to the first admin while there is none, else told it is an admin's)
ADMIN_ENDPOINTS = ("admin_people", "admin_person", "admin_bulk", "admin_reset", "admin_ways", "admin_shared_off", "admin_students")

@t
def the_guards_are_the_brief_s_table():
    need = lambda endpoint: A.app.view_functions[endpoint]._need
    for endpoint, want in (("meta", ("setup",)), ("api_sample", ("setup",)), ("get_setup", ("setup",)), ("get_setup_changes", ("setup",)),
                           ("post_setup_changes", ("setup",)), ("status", ("setup",)), ("put_setup", ("committee",)), ("draft_publish", ("committee",)),
                           ("timetable", ("timetable",)), ("pdf_custom", ("timetable",)), ("pdf_one", ("timetable",)), ("files", ("files",)),
                           ("me", ("own",)), ("pdf_me", ("own",)), ("relief_home", ("relief", "relief.settings")), ("relief_me", ("relief",)),
                           ("relief_settings_page", ("relief.settings",)), ("relief_settings_get", ("relief.settings",)), ("relief_settings_put", ("relief.save",)),
                           ("relief_codes_csv", ("codes",)), ("relief_code_slips", ("codes",)), ("home", ("timetable",)), ("draft_preview_page", ("committee",))) + tuple(
                               (e, ("exams", "committee")) for e in EXAMS_ENDPOINTS) + tuple((e, ("admin",)) for e in ADMIN_ENDPOINTS) + (("admin_first", ("committee",)),
                               ("admin_page", ("admin", "committee"))):
        assert need(endpoint) == want, (endpoint, need(endpoint))
    admin = {r.endpoint for r in A.app.url_map.iter_rules() if r.rule.startswith(("/admin", "/api/admin"))}
    assert admin == set(ADMIN_ENDPOINTS) | {"admin_first", "admin_page"}, sorted(admin ^ (set(ADMIN_ENDPOINTS) | {"admin_first", "admin_page"}))
    for bad in (("staff",), ("head",), ("personal",), ("committee", "teacher"), ()):
        try: A.need(*bad)
        except ValueError: pass
        else: raise AssertionError(f"need{bad} was accepted")
    assert not hasattr(A, "role") and not hasattr(A, "_legacy")
    exams = {r.endpoint for r in A.app.url_map.iter_rules() if "/exams" in r.rule}
    assert exams == set(EXAMS_ENDPOINTS), sorted(exams ^ set(EXAMS_ENDPOINTS))

@t
def the_known_rights_are_every_right_the_table_gives():
    seen = set()
    for shared in R._SHARED: seen |= R.rights(None, "shared", shared)
    seen |= R.rights(None, "personal")
    for group, via, relief, exams, admin in itertools.product(P.GROUPS, ("code", "password"), (False, True), (None, TOMORROW), (False, True)):
        seen |= R.rights(dict(group=group, extras=dict(relief=relief, exams=exams, admin=admin)), via)
    assert seen == A.RIGHTS, (sorted(seen ^ A.RIGHTS))

@t
def an_executive_does_not_reach_relief():
    c = client(person(EVE, "code"))
    assert to_login(c.get("/relief")) and c.get("/api/relief/me").get_json() == AGAIN and c.get("/api/relief/me").status_code == 401
    assert went(c.get("/home"), "/timetable")                         # one tile: it opens straight away
    assert kept(c)["who"] == EVE

@t
def the_front_door_sends_each_kind_to_its_page():
    for kind, where in (("shared committee", None), ("shared head", None), ("committee by password", None), ("hod by password", None),
                        ("committee by code", "/home"), ("teacher by code", "/home"), ("hod by code", "/home"), ("executive by code", "/home"),
                        ("personal student", "/me"), ("shared teacher", "/timetable"), ("shared student", "/timetable"), ("nobody", "/login")):
        r = client(KINDS[kind][0]).get("/")
        if where is None: assert r.status_code == 200 and b"app.js" in r.data, (kind, r.status_code); r.close()
        else: assert went(r, where), (kind, r.status_code, r.headers.get("Location"))
    assert went(client(dict(role="committee")).get("/home"), "/")    # a shared code is nobody's: no tiles
    assert to_login(client({}).get("/home")) and to_login(client(dict(role="personal", sid="S001")).get("/home"))

def tiles(c):
    """(shown, greyed): the tiles of /home as (title, link)"""
    r = c.get("/home"); assert r.status_code == 200, (r.status_code, r.headers.get("Location"))
    page = r.data.decode()
    got = re.findall(r'<a class="tile( off)?" href="([^"]+)"[^>]*>.*?<b>([^<]+)</b>(.*?)</a>', page, re.S)
    shown = [(html.unescape(b), a) for off, a, b, _ in got if not off]
    greyed = [(html.unescape(b), a) for off, a, b, rest in got if off]
    assert all(GREY in rest for off, a, b, rest in got if off) and page.count(GREY) == len(greyed)
    return shown, greyed, page

@t
def home_shows_exactly_the_tiles_of_the_table():
    shown, greyed, page = tiles(client(person(TINA, "code")))
    assert shown == [("Timetables", "/timetable"), ("Relief", "/relief")] and greyed == [], (shown, greyed)
    assert f"Hello, {TINA}" in page and "Signed in with your code" in page and 'href="/logout"' in page and "Sign out" in page
    shown, greyed, page = tiles(client(person(ADA, "password")))
    assert shown == [("Committee page", "/"), ("Timetables", "/timetable"), ("Relief", "/relief"), ("Exams and events", "/exams"), ("Admin", "/admin"), ("History", "/history")], shown
    assert greyed == [] and "Signed in with your password" in page
    assert "Until" not in page.split("Exams and events")[1].split("</a>")[0], "the committee's tile has no end date"
    shown, greyed, _ = tiles(client(person(ADA, "code")))           # the committee's code: all but the setup and the admin page
    assert shown == [("Timetables", "/timetable"), ("Relief", "/relief")], shown
    assert greyed == [("Committee page", "/login/password"), ("Admin", "/login/password")], greyed
    shown, greyed, _ = tiles(client(person(CORA, "code")))          # no Admin extra: no Admin tile, greyed or not
    assert greyed == [("Committee page", "/login/password")], greyed
    shown, greyed, _ = tiles(client(person(HAL, "code")))
    assert shown == [("Timetables", "/timetable"), ("Relief", "/relief")] and greyed == [("Committee page", "/login/password")], (shown, greyed)
    shown, greyed, _ = tiles(client(person(HAL, "password")))
    assert shown == [("Committee page", "/"), ("Timetables", "/timetable"), ("Relief", "/relief")] and greyed == [], shown
    shown, greyed, _ = tiles(client(person(LEE, "password")))
    assert shown == [("Timetables", "/timetable"), ("Relief", "/relief")] and greyed == [], shown
    # Exams and events: the exams pages are on the app now; the tile only while they are
    assert any(r.rule == "/exams" for r in A.app.url_map.iter_rules())
    shown, _, page = tiles(client(person(ELI, "code")))
    assert shown == [("Timetables", "/timetable"), ("Relief", "/relief"), ("Exams and events", "/exams")], shown
    d = datetime.date.fromisoformat(TOMORROW); assert f"Until {d.day} {d.strftime('%b %Y')}" in page
    real = A._route_exists
    A._route_exists = lambda path: path != "/exams" and real(path)
    try: shown, _, _ = tiles(client(person(ELI, "code"))); assert [x for x, _ in shown] == ["Timetables", "Relief"], shown
    finally: A._route_exists = real

@t
def an_exams_extra_opens_exams_until_its_end_date():
    eli, max_ = client(person(ELI, "code")), client(person(MAX, "code"))
    assert eli.get("/exams").status_code == 200 and eli.get("/exams/settings").status_code == 200
    assert eli.get("/api/exams/me").get_json() == dict(name=ELI, can_use=True, home="/home")
    j = eli.get("/api/exams/settings").get_json()
    assert [ELI, TOMORROW] in j["lists"]["committee"] and j["can_admin"] is False, j["lists"]
    assert client(person(ADA, "password")).get("/api/exams/settings").get_json()["can_admin"] is True
    assert to_login(max_.get("/exams")) and max_.get("/api/exams/me").get_json() == AGAIN and max_.get("/api/exams").status_code == 401
    assert MAX not in [n for n, _ in j["lists"]["committee"]]
    assert "Exams and events" not in max_.get("/home").get_data(as_text=True)
    assert kept(max_)["who"] == MAX, "an ended extra ends no session"

@t
def a_name_on_home_is_escaped():
    odd = "Mr <b>Odd</b> & Co"
    P.update(lambda d: d["people"].setdefault(odd, {}).update(group="leader", added=True))
    try:
        page = client(person(odd, "code")).get("/home").data.decode()
        assert "Mr &lt;b&gt;Odd&lt;/b&gt; &amp; Co" in page and "<b>Odd</b>" not in page
    finally: P.update(lambda d: d["people"].pop(odd))

@t
def the_timetable_page_each_kind_sees():
    for kind, want in (("shared committee", "the committee page /"), ("committee by password", "the committee page /"),
                       ("committee by code", "the teacher page /home"), ("hod by password", "the teacher page /home"),
                       ("teacher by code", "the teacher page /home"), ("shared teacher", "the teacher page None"), ("shared head", "the teacher page None"),
                       ("shared student", "the student page None"), ("relief stage 1 session", "the teacher page /relief")):
        r = client(KINDS[kind][0]).get("/timetable"); assert r.data.decode() == want, (kind, r.data[:80])
    r = client(dict(role="staff", who=EVE)).get("/timetable")        # no relief of her own: no way back to Relief
    assert r.data.decode() == "the teacher page /home", r.data[:80]
    from ttgen import export as E
    seen, real = [], E.render_html
    E.render_html = lambda model, view, app=None: seen.append((view, app)) or f"page {len(seen)}"
    views = store.published()["views"]; old = dict(views); views.clear()
    try:
        for kind in ("teacher by code", "relief stage 1 session", "shared teacher", "shared student", "admin by password"): client(KINDS[kind][0]).get("/timetable")
    finally: E.render_html = real; views.clear(); views.update(old)
    (v1, a1), (v2, a2), (v3, a3), (v4, a4), (v5, a5) = seen
    assert (a1["mode"], a1["home"], a1["homeLabel"]) == ("teacher", "/home", "Home") and v1 == "full", a1
    assert (a2["mode"], a2["home"], a2["homeLabel"]) == ("teacher", "/relief", "Relief"), a2
    assert (a3["mode"], a3["home"]) == ("teacher", None) and (v4, a4["mode"], a4["tabs"]) == ("student", "student", ["classes", "students"])
    assert (a5["mode"], a5["home"], a5["homeLabel"], a5["tabs"]) == ("committee", "/", "Committee page", None)
    assert a1["tabs"] == a3["tabs"] and a1["files"] == a3["files"] == A.files_for("teacher") and a5["files"] == A.files_for("committee")

@t
def status_says_who_is_signed_in():
    j = client(person(HAL, "password")).get("/api/status").get_json()
    assert (j["role"], j["who"], j["via"], j["depts"], j["shared"], j["admin_exists"]) == ("head", HAL, "password", ["SC", "MA"], None, True), j
    assert j["group"] == "HOD", j
    assert j["rights"] == sorted(KINDS["hod by password"][1]) and "codes" not in j and "volume" in j and "published" in j
    j = client(dict(role="head")).get("/api/status").get_json()
    assert (j["role"], j["who"], j["via"], j["depts"], j["shared"]) == ("head", None, "shared", None, "head") and j["group"] is None, j
    j = client(person(ADA, "password")).get("/api/status").get_json()
    assert (j["role"], j["who"], j["via"], j["depts"], j["shared"]) == ("committee", ADA, "password", None, None) and "codes" in j and "draft" in j, j
    assert j["group"] == "Timetable committee", j
    j = client(dict(role="committee")).get("/api/status").get_json()
    assert (j["role"], j["who"], j["shared"], j["admin_exists"]) == ("committee", None, "committee", True) and j["rights"] == sorted(KINDS["shared committee"][1]), j
    P.update(lambda d: d["people"][ADA]["extras"].update(admin=False))
    try: assert client(dict(role="committee")).get("/api/status").get_json()["admin_exists"] is False
    finally: P.update(lambda d: d["people"][ADA]["extras"].update(admin=True))

RELIEF_SHAPED = {"name", "short", "depts", "role", "teaches", "staff_only"}
USERNAMES = ("hal.ong", "cora.lim", "ada.koh", "lee.chua")

@t
def no_account_field_reaches_a_page_that_is_not_the_admin_page():
    for kind, url in (("teacher on exams until tomorrow", "/api/exams/settings"), ("teacher on the relief team", "/api/relief/settings"),
                      ("shared committee", "/api/exams/settings"), ("shared committee", "/api/relief/settings"), ("hod by code", "/api/relief/settings")):
        r = client(KINDS[kind][0]).get(url); j = r.get_json()
        assert r.status_code == 200 and j["people"], (kind, url, r.status_code, j)
        assert all(set(p) == RELIEF_SHAPED for p in j["people"]), (kind, url, j["people"][:1])
        body = r.get_data(as_text=True)
        assert not any(u in body for u in USERNAMES) and '"has_password"' not in body and '"extras"' not in body and '"last"' not in body, (kind, url)
        names = {p["name"] for p in j["people"]}; assert {TINA, HAL, CORA, ADA} <= names, names   # the staff added by name are there, without their accounts
    assert all(set(p) == RELIEF_SHAPED for p in A.relief_staff(store.published()))
    j = client(person(HAL, "code")).get("/api/relief/me").get_json(); assert j["depts"] == ["SC", "MA"], j   # a head's ticked departments
    P.update(lambda d: d["people"][HAL].update(depts=[]))
    try: assert client(person(HAL, "code")).get("/api/relief/me").get_json()["depts"] == ["SC"]   # none ticked: relief keeps step 4's
    finally: P.update(lambda d: d["people"][HAL].update(depts=["SC", "MA"]))

# relief requests (relief stage 2, relief/web.py): every route needs relief (the map above); these also ask a narrower
# right inside, answered with their own sentence (a 403 that is not the guard's): relief.plan to see who is free, the
# planned list and the relief sheet; relief.team for What's in. School leaders, HODs and SHs plan; the Relief team extra
# plans and is the relief team (R16)
PLAN_ONLY = "Only management and the relief team plan relief for a colleague."
CHOOSE_ONLY = "Only management and the relief team choose relief teachers."
TEAM_ONLY = "Only the relief team can open What's in."
RELIEF_INSIDE = {("GET", "/api/relief/free"): ("relief.plan", CHOOSE_ONLY), ("GET", "/api/relief/absences/planned"): ("relief.plan", PLAN_ONLY),
                 ("GET", "/api/relief/planned.csv"): ("relief.plan", PLAN_ONLY), ("GET", "/api/relief/absences"): ("relief.team", TEAM_ONLY),
                 ("POST", "/api/relief/absences/seen"): ("relief.team", TEAM_ONLY)}

@t
def relief_requests_ask_the_narrower_right_inside():
    for kind, (keys, have) in KINDS.items():
        if "relief" not in have: continue
        c = client(keys)
        j = c.get("/api/relief/me").get_json()
        assert (j["can_plan"], j["can_team"]) == ("relief.plan" in have, "relief.team" in have), (kind, j)
        for (method, url), (right, sentence) in RELIEF_INSIDE.items():
            r = c.open(url, method=method, json={})
            if right in have: assert r.status_code not in (401, 403, 500), (kind, method, url, r.status_code, r.get_data(as_text=True)[:200])
            else: assert r.status_code == 403 and r.get_json() == {"error": sentence}, (kind, method, url, r.status_code, r.get_data(as_text=True)[:200])
            r.close()
        assert kept(c) == keys, (kind, kept(c))

ONLY_ADMIN = "Only an admin can open this page."

@t
def the_admin_page_sends_the_committee_to_the_first_admin_while_there_is_none():
    for kind in ("shared committee", "committee by password"):        # an admin can sign in: the page is an admin's
        r = client(KINDS[kind][0]).get("/admin"); body = r.get_data(as_text=True)
        assert r.status_code == 403 and ONLY_ADMIN in body and "href='/'" in body, (kind, r.status_code)
    r = client(person(ADA, "password")).get("/admin"); assert r.status_code == 200 and b"admin.js" in r.data; r.close()
    for kind in ("admin by code", "committee by code", "hod by password", "shared head", "shared teacher", "nobody"):
        assert to_login(client(KINDS[kind][0]).get("/admin")), kind
    P.update(lambda d: d["people"][ADA]["extras"].update(admin=False))   # deploy day: no admin yet
    try:
        for kind in ("shared committee", "committee by password"):
            assert went(client(KINDS[kind][0]).get("/admin"), "/admin/first"), kind
        r = client(dict(role="committee")).get("/admin/first"); assert r.status_code == 200 and 'name="new"' in r.data.decode()
        assert to_login(client(KINDS["admin by code"][0]).get("/admin")) and to_login(client(KINDS["shared head"][0]).get("/admin"))
    finally: P.update(lambda d: d["people"][ADA]["extras"].update(admin=True))

@t
def the_committee_page_links_the_first_admin_admin_and_history_by_right():
    page = open(os.path.join(ROOT, "static", "index.html"), encoding="utf-8").read()
    js = open(os.path.join(ROOT, "static", "app.js"), encoding="utf-8").read()
    assert re.search(r'<div id="firstAdmin"[^>]*hidden>No admin account yet\. <a href="/admin/first">Make the first admin</a></div>', page), "the first admin line"
    assert re.search(r'<a [^>]*id="adminLink" href="/admin" hidden>Admin</a>', page) and re.search(r'<a [^>]*id="historyLink" href="/history" hidden>History</a>', page)
    assert 'al.hidden = !rights.includes("admin")' in js and 'hy.hidden = !rights.includes("history")' in js
    assert 'fa.hidden = !(G.st.admin_exists === false && rights.includes("committee"))' in js
    j = client(dict(role="committee")).get("/api/status").get_json()   # what the page reads: the rights and whether an admin exists
    assert "committee" in j["rights"] and "history" in j["rights"] and "admin" not in j["rights"] and j["admin_exists"] is True, j
    assert "admin" in client(person(ADA, "password")).get("/api/status").get_json()["rights"]

def sent(base, edit):
    """the ops the page sends for an edit (sync.diff of the setup before and after), as tests/test_sync.py makes them"""
    import copy
    cur = copy.deepcopy(base); edit(cur); sync.ensure_ids(cur); return sync.diff(base, cur)

@t
def heads_change_only_their_own_departments_and_are_named_in_the_history():
    com = client(person(CORA, "password"))
    r = com.put("/api/setup", json=dict(spec=secondary(), why="Saved")); assert r.status_code == 200, r.get_json()
    e = H.read(kinds=["setup-replaced"], limit=1)[0]; assert (e["who"], e["via"]) == (CORA, "password"), e
    base = com.get("/api/setup").get_json()["spec"]
    sc = next(x for x in base["lessons"] if sync.lesson_dept(base, x) == "SC")
    el = next(x for x in base["lessons"] if sync.lesson_dept(base, x) == "EL")
    def touch(row): return lambda s: next(x for x in s["lessons"] if x["_id"] == row["_id"]).update(teachers=["Typed Teacher"])
    ops = sent(base, touch(sc)) + sent(base, touch(el)); assert len(ops) == 2, ops
    def post(c, ops):
        v = c.get("/api/setup").get_json()["v"]
        return c.post("/api/setup/changes", json=dict(client="t", since=v, ops=ops)).get_json()
    j = post(client(person(HAL, "password")), ops)                   # Science and Mathematics: the English row is refused
    assert [x["i"] for x in j.get("refused", [])] == [1] and j["refused"][0]["why"] == sync.OTHER_DEPT, j
    e = H.read(kinds=["setup"], limit=1)[0]; assert (e["who"], e["via"]) == (HAL, "password"), e
    e = H.read(kinds=["setup-refused"], limit=1)[0]; assert (e["who"], e["as"]) == (HAL, HAL), e
    assert "refused" not in post(client(dict(role="head")), ops)       # the shared heads' code: every department, as today
    P.update(lambda d: d["people"][HAL].update(depts=[]))             # a head with no department changes no row (R8)
    try:
        j = post(client(person(HAL, "password")), ops); assert [x["i"] for x in j["refused"]] == [0, 1], j
    finally: P.update(lambda d: d["people"][HAL].update(depts=["SC", "MA"]))
    add = [["add", "teachers", dict(name="New Hire", short="New", dept="EL", dept2="PE", _id="newhire0001"), ""]]
    j = post(client(person(HAL, "password")), add); assert "refused" not in j, j
    t_ = next(x for x in com.get("/api/setup").get_json()["spec"]["teachers"] if x["name"] == "New Hire")
    assert (t_["dept"], t_["provisional"], t_.get("dept2")) == ("SC", "Yes", None), t_   # in the head's first department
    assert client(person(HAL, "code")).post("/api/setup/changes", json=dict(client="t", ops=ops)).status_code == 401   # the code opens no setup
    copies = com.get("/api/setup/copies").get_json(); assert copies
    r = com.post("/api/setup/restore", json=dict(id=copies[0]["id"])); assert r.status_code == 200, r.get_json()
    e = H.read(kinds=["setup-replaced"], limit=1)[0]; assert (e["who"], e["text"][:8]) == (CORA, "Restored"), e

print(f"{COUNT} route tests passed")

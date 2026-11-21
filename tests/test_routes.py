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
from accounts import people as P, rights as R  # noqa: E402
from relief import people as RP  # noqa: E402
from ttgen.samples import secondary  # noqa: E402

AGAIN = {"error": "Please sign in again."}
GREY = "Sign in with your password to open this."
TOMORROW = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()

# made-up people: four on the published timetable, four added by name
TINA, HAL, RIA, ELI = "Ms Tina Teo", "Mr Hal Ong", "Ms Ria Tan", "Mr Eli Ng"
CORA, ADA, LEE, EVE = "Ms Cora Lim", "Ms Ada Koh", "Mr Lee Chua", "Mdm Eve Sim"
TEACHERS = [dict(name=TINA, dept="SC"), dict(name=HAL, dept="SC", role="HOD"), dict(name=RIA, dept="MA"), dict(name=ELI, dept="EL")]
RECORDS = {HAL: dict(group="hod", depts=["SC", "MA"], username="hal.ong"),
           RIA: dict(extras=dict(relief=True, exams=None, admin=False)),
           ELI: dict(extras=dict(relief=False, exams=TOMORROW, admin=False)),
           CORA: dict(group="committee", added=True, username="cora.lim"),
           ADA: dict(group="committee", added=True, username="ada.koh", extras=dict(relief=False, exams=None, admin=True)),
           LEE: dict(group="leader", added=True, username="lee.chua"),
           EVE: dict(group="executive", added=True)}

def publish():
    """what store.published() reads: a fake school with the teachers, one class and one student"""
    pub = RP.fake_pub(TEACHERS)
    pub["meta"].update(published_at="1 Nov 2026, 09:00", ok=True)
    pub["model"].update(classes=[dict(name="1A")], class_ix={}, teacher_ix={}, room_ix={}, students=[dict(id="S001", name="Sam Student", cls="1A")])
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
    "teacher on the relief team": (person(RIA, "code"), BASE | {"relief.settings", "relief.save", "relief.team"}),
    "teacher on exams until tomorrow": (person(ELI, "code"), BASE | {"exams"}),
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

@t
def the_guards_are_the_brief_s_table():
    need = lambda endpoint: A.app.view_functions[endpoint]._need
    for endpoint, want in (("meta", ("setup",)), ("api_sample", ("setup",)), ("get_setup", ("setup",)), ("get_setup_changes", ("setup",)),
                           ("post_setup_changes", ("setup",)), ("status", ("setup",)), ("put_setup", ("committee",)), ("draft_publish", ("committee",)),
                           ("timetable", ("timetable",)), ("pdf_custom", ("timetable",)), ("pdf_one", ("timetable",)), ("files", ("files",)),
                           ("me", ("own",)), ("pdf_me", ("own",)), ("relief_home", ("relief", "relief.settings")), ("relief_me", ("relief",)),
                           ("relief_settings_page", ("relief.settings",)), ("relief_settings_get", ("relief.settings",)), ("relief_settings_put", ("relief.save",)),
                           ("relief_codes_csv", ("codes",)), ("relief_code_slips", ("codes",)), ("home", ("timetable",)), ("draft_preview_page", ("committee",))):
        assert need(endpoint) == want, (endpoint, need(endpoint))
    for bad in (("staff",), ("head",), ("personal",), ("committee", "teacher"), ()):
        try: A.need(*bad)
        except ValueError: pass
        else: raise AssertionError(f"need{bad} was accepted")
    assert not hasattr(A, "role") and not hasattr(A, "_legacy")

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
    assert shown == [("Committee page", "/"), ("Timetables", "/timetable"), ("Relief", "/relief"), ("Admin", "/admin"), ("History", "/history")], shown
    assert greyed == [] and "Signed in with your password" in page
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
    # Exams and events only once the exams pages exist (they do not on this branch)
    assert not any(r.rule == "/exams" for r in A.app.url_map.iter_rules())
    shown, _, _ = tiles(client(person(ELI, "code"))); assert [x for x, _ in shown] == ["Timetables", "Relief"], shown
    real = A._route_exists
    A._route_exists = lambda path: path == "/exams" or real(path)
    try: shown, _, page = tiles(client(person(ELI, "code")))
    finally: A._route_exists = real
    assert shown == [("Timetables", "/timetable"), ("Relief", "/relief"), ("Exams and events", "/exams")], shown
    d = datetime.date.fromisoformat(TOMORROW); assert f"Until {d.day} {d.strftime('%b %Y')}" in page

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
    assert j["rights"] == sorted(KINDS["hod by password"][1]) and "codes" not in j and "volume" in j and "published" in j
    j = client(dict(role="head")).get("/api/status").get_json()
    assert (j["role"], j["who"], j["via"], j["depts"], j["shared"]) == ("head", None, "shared", None, "head"), j
    j = client(person(ADA, "password")).get("/api/status").get_json()
    assert (j["role"], j["who"], j["via"], j["depts"], j["shared"]) == ("committee", ADA, "password", None, None) and "codes" in j and "draft" in j, j
    j = client(dict(role="committee")).get("/api/status").get_json()
    assert (j["role"], j["who"], j["shared"], j["admin_exists"]) == ("committee", None, "committee", True) and j["rights"] == sorted(KINDS["shared committee"][1]), j
    P.update(lambda d: d["people"][ADA]["extras"].update(admin=False))
    try: assert client(dict(role="committee")).get("/api/status").get_json()["admin_exists"] is False
    finally: P.update(lambda d: d["people"][ADA]["extras"].update(admin=True))

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

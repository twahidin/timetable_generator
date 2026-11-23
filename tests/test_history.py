"""Plain-assert tests for the history file: .venv/bin/python tests/test_history.py"""
import contextlib, copy, datetime, io, os, re, sys, tempfile, time, urllib.parse
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = tempfile.mkdtemp()
os.environ.update(DATA_DIR=DATA, AI_API_KEY="")
sys.path.insert(0, ROOT)
import history as H, store, sync  # noqa: E402
from ttgen import samples  # noqa: E402

COUNT = 0
def t(f):
    global COUNT
    f(); COUNT += 1
    return f

def fresh():
    if os.path.isdir(H.DIR):
        for n in os.listdir(H.DIR): os.remove(os.path.join(H.DIR, n))

def month_file(entry):
    return os.path.join(H.DIR, entry["at"][:7] + ".jsonl")

@t
def add_and_read_newest_first():
    fresh()
    a = H.add({"kind": "app", "text": "one"}); b = H.add({"kind": "app", "text": "two"})
    assert a["id"].startswith("h") and len(a["id"]) == 17 and a["id"] < b["id"], (a["id"], b["id"])
    assert isinstance(a["ts"], float) and a["at"][:4].isdigit()
    assert [e["text"] for e in H.read()] == ["two", "one"]
    both = H.add_many([{"kind": "app", "text": "x"}, {"kind": "app", "text": "y"}])
    assert len(both) == 2 and both[0]["id"] < both[1]["id"]
    assert H.read(limit=2)[0]["text"] == "y"
    assert H.by_of("Ann Lee", "password") == {"who": "Ann Lee", "as": "Ann Lee", "via": "password"}
    assert H.by_of(None, "shared", "Shared teacher code") == {"who": None, "as": "Shared teacher code", "via": "shared"}
    assert H.by_of(None, "?")["as"] == "Unknown"
    assert H.by_of(None, "app") == {"who": None, "as": "The app", "via": "app"}

@t
def forbidden_keys_dropped():
    fresh()
    e = H.add({"kind": "account", "text": "t", "password": "p", "now": {"code": "c", "keep": 1, "l": [{"token": "z", "ok": 2}]}})
    assert "password" not in e and e["now"] == {"keep": 1, "l": [{"ok": 2}]}, e
    raw = open(month_file(e)).read()
    assert '"password"' not in raw and '"code"' not in raw and '"token"' not in raw

@t
def half_line_skipped():
    fresh()
    e = H.add({"kind": "app", "text": "good1"})
    with open(month_file(e), "a") as f: f.write('{"kind": "set')
    H.add({"kind": "app", "text": "good2"})
    assert [x["text"] for x in H.read()] == ["good2", "good1"]
    last = open(month_file(e)).read().splitlines()[-1]
    import json; assert json.loads(last)["text"] == "good2"

@t
def filters():
    fresh()
    H.add({"kind": "setup", "who": "Ann", "where": "Step 4 · Teachers", "depts": ["Maths"], "text": "a"})
    H.add({"kind": "setup", "who": "Bob", "where": "Step 5 · Teacher Deployment Editor", "depts": ["Science", "Maths"], "text": "b"})
    H.add({"kind": "signin", "who": "Ann", "text": "in"})
    H.add({"kind": "relief", "who": "Bob", "text": "c"})
    assert [e["text"] for e in H.read()] == ["c", "b", "a"]
    assert len(H.read(signins=True)) == 4
    assert [e["text"] for e in H.read(who="Ann")] == ["a"]
    assert [e["text"] for e in H.read(where="Step 5 · Teacher Deployment Editor")] == ["b"]
    assert [e["text"] for e in H.read(dept="Maths")] == ["b", "a"]
    assert [e["text"] for e in H.read(kinds=["relief"])] == ["c"]
    allr = H.read()
    assert [e["text"] for e in H.read(before=allr[0]["id"])] == ["b", "a"]
    assert [e["text"] for e in H.read(before=allr[0]["id"], limit=1)] == ["b"]
    now = time.time()
    assert len(H.read(since=now - 60, until=now + 60)) == 3
    assert H.read(until=now - 3600) == [] and H.read(since=now + 3600) == []

@t
def prune_two_years():
    fresh()
    today = datetime.date(2026, 11, 21)
    for n in ("2024-10.jsonl", "2024-11.jsonl", "2026-11.jsonl", "notes.txt"):
        open(os.path.join(H.DIR, n), "w").write("")
    assert H.prune(today) == 1
    assert sorted(os.listdir(H.DIR)) == ["2024-11.jsonl", "2026-11.jsonl", "notes.txt"]
    assert H.prune(today) == 0

@t
def uses_counts_last_week():
    fresh()
    H.add({"kind": "app", "text": "n"})
    H.add({"kind": "app", "text": "n"})
    H.add({"kind": "relief", "text": "n"})
    old = time.time() - 10 * 86400
    H.add({"kind": "app", "text": "n", "ts": old})
    assert H.uses() == 3 and H.uses(kind="app") == 2 and H.uses(30, kind="app") == 3 and H.uses(kind="zzz") == 0

@t
def setup_entries_values():
    spec = samples.secondary(); sync.ensure_ids(spec)
    before = copy.deepcopy(spec)
    L = next(r for r in spec["lessons"] if r["level"] == "Sec 3" and r["teachers"] and sync.lesson_dept(spec, r))
    old = L["teachers"]; new = ["Joseph Lim"]
    dept = sync.lesson_dept(spec, L)
    assert dept
    by = H.by_of("Ann Lee", "password")
    row = {"_id": "newrow0001", "name": "Zed Ng", "dept": "Maths"}
    ops = [["set", "lessons", L["_id"], "teachers", new],
           ["add", "teachers", row, ""],
           ["set", "teachers", "newrow0001", "dept", "Science"],
           ["del", "classes", spec["classes"][0]["_id"]]]
    ops_copy = copy.deepcopy(ops)
    es = H.setup_entries(spec, ops, by, "b1", 7)
    assert spec == before and ops == ops_copy
    assert len(es) == 4 and all(e["kind"] == "setup" and e["batch"] == "b1" and e["v"] == 7 and e["as"] == "Ann Lee" for e in es)
    e = es[0]
    assert (e["was"], e["now"], e["section"], e["field"]) == (old, new, "lessons", "teachers") and e["row"] == L["_id"]
    assert dept in e["depts"] and e["where"] == "Step 5 · Teacher Deployment Editor" and e["op"] == "set"
    assert e["text"] == f"{H.row_label('lessons', L)}: teachers {', '.join(old)} → Joseph Lim", e["text"]
    assert e["label"].startswith("Sec 3 ")
    assert es[1]["was"] is None and es[1]["now"]["name"] == "Zed Ng" and es[1]["text"] == "Added Zed Ng"
    assert es[2]["was"] == "Maths" and es[2]["now"] == "Science" and set(es[2]["depts"]) == {"Maths", "Science"}
    assert es[3]["now"] is None and es[3]["was"]["class"] == spec["classes"][0]["class"] and es[3]["text"].startswith("Deleted ")
    assert H.row_label("x", None) == "(gone)"
    s2 = H.setup_entries(spec, [["school", "name", "X"], ["day", "Sec 1", "Odd Mon", None], ["top", "k", 1]], by, "b2", 8)
    assert [e["where"] for e in s2] == ["School & day"] * 3 and s2[0]["text"].startswith("name: ")

@t
def code_kept_in_setup_rows_only():
    fresh()
    spec = samples.secondary(); sync.ensure_ids(spec)
    L = spec["lessons"][0]
    assert L.get("code")
    [e] = H.setup_entries(spec, [["del", "lessons", L["_id"]]], H.by_of("Ann", "password"), "b", 1)
    w = H.add(e)["was"]
    assert w["code"] == L["code"] and H.read()[0]["was"]["code"] == L["code"]
    a = H.add({"kind": "account", "password": "p", "changes": [{"field": "pw", "code": "x"}], "now": {"code": "y"}})
    assert a["changes"] == [{"field": "pw"}] and "password" not in a and a["now"] == {}

@t
def setup_entries_never_raises():
    spec = samples.secondary(); sync.ensure_ids(spec)
    T = spec["teachers"][0]
    ops = [["merge", "teachers", T["_id"], "can_teach", ["X"]], ["set", "nosuch", "a", "f", 1],
           ["set", "teachers", T["_id"], "note", "hi"], 5, [], ["merge"], ["add", "teachers", "notadict", ""]]
    err = io.StringIO()
    with contextlib.redirect_stderr(err): es = H.setup_entries(spec, ops, H.by_of("Ann", "password"), "b", 1)
    assert [e["op"] for e in es] == ["set"] and es[0]["now"] == "hi", es
    lines = err.getvalue().splitlines()                                 # an operation dropped is said, as the store says it: its type only (the short merge is skipped by apply: no entry, nothing said)
    assert len(lines) == 2 and all(re.fullmatch(r"warning: the history could not be written \((IndexError|TypeError)\)", x) for x in lines), lines

@t
def row_label_every_section():
    spec = samples.secondary(); sync.ensure_ids(spec)
    spec["roles"] = [{"role": "Head of Department", "_id": "r1"}]
    for sec, f in (("venues", "room"), ("classes", "class"), ("subjects", "subject"), ("teachers", "name"),
                   ("blocks", "block"), ("students", "name"), ("roles", "role")):
        row = spec[sec][0]
        assert H.row_label(sec, row) == row[f], (sec, H.row_label(sec, row))
    c = spec["combinations"][0]
    assert H.row_label("combinations", c) == (c.get("name") or c["code"])
    assert H.row_label("combinations", {"code": "S1"}) == "S1"
    r = spec["rules"][0]
    assert H.row_label("rules", r) == f"{r['target']} · {r['rule']}"
    assert H.row_label("choices", {"kind": "recess", "level": "Sec 1"}) == "recess Sec 1"
    assert H.row_label("choices", {"kind": "setting", "key": "k"}) == "setting k"
    assert H.row_label("lessons", {"level": "Sec 3", "subject": "Physics", "classes": ["3B"]}) == "Sec 3 Physics 3B"

@t
def stray_files_and_non_dict():
    fresh()
    H.add({"kind": "app", "text": "a"})
    for n in ("2024-xx.jsonl", "notes.txt"):
        open(os.path.join(H.DIR, n), "w").write("junk\n")
    assert H.prune(datetime.date(2026, 11, 21)) == 0 and len(H.read()) == 1
    assert {"2024-xx.jsonl", "notes.txt"} <= set(os.listdir(H.DIR))
    for bad in ("x", None, [1]):
        try: H.add(bad)
        except TypeError: pass
        else: raise AssertionError("no TypeError")
    try: H.add_many([{"kind": "app"}, 3])
    except TypeError: pass
    else: raise AssertionError("no TypeError")
    assert len(H.read()) == 1

def _setup_in_store(parents=False):
    fresh()
    spec = samples.secondary()
    if parents:
        spec["subjects"].append({"subject": "Pastoral Care", "code": "PC", "periods": {"Sec 1": 2}})
        spec["school"]["parents_subjects"] = ["Pastoral Care"]
        next(x for x in spec["classes"] if x["class"] == "1A")["parents"] = ["Pastoral A"]
    store._setup.clear()
    store.replace_setup(spec, "Test start")
    fresh()
    return store.setup_record()["spec"]

@t
def apply_changes_writes_who():
    spec = _setup_in_store()
    cid = spec["classes"][0]["_id"]; cid2 = spec["classes"][1]["_id"]
    by = H.by_of("Ann Lee", "password")
    ops = [["set", "classes", cid, "class", "Zeta"], ["school", "timetable", "Term 9"]]
    v, refused, mine = store.apply_changes(ops, "c1", by=by)
    es = H.read(kinds=["setup"])
    assert len(es) == 2 and {e["as"] for e in es} == {"Ann Lee"} and {e["v"] for e in es} == {v}, es
    assert len({e["batch"] for e in es}) == 1 and es[0]["batch"].startswith("b")
    store.apply_changes([["school", "timetable", "Term 8"]], "c1")
    assert H.read(limit=1)[0]["as"] == "Unknown"
    def flt(sp, ops):
        return [ops[1]], [(0, "Not your department.")]
    fresh()
    store.apply_changes([["set", "classes", cid2, "class", "Eta"], ["school", "timetable", "Term 7"]], "c1", filter=flt, by=by)
    es = H.read()
    ref = [e for e in es if e["kind"] == "setup-refused"]; ok = [e for e in es if e["kind"] == "setup"]
    assert len(ref) == 1 and len(ok) == 1, es
    r = ref[0]
    assert r["why"] == "Not your department." and r["op"] == ["set", "classes", cid2, "class", "Eta"]
    assert r["as"] == "Ann Lee" and r["via"] == "password" and r["where"] == "Step 2 · Classes", r

@t
def refused_entries_name_the_row_and_its_departments():
    spec = _setup_in_store()
    L = next(r for r in spec["lessons"] if sync.lesson_dept(spec, r))
    d0 = sync.lesson_dept(spec, L)
    other = next(x for x in spec["subjects"] if str(x.get("dept") or "").strip() not in ("", d0))
    d1 = str(other["dept"]).strip()
    lab = H.row_label("lessons", L)
    ops = [["set", "lessons", L["_id"], "subject", other["subject"]], ["set", "lessons", L["_id"], "periods", 3],
           ["add", "teachers", {"_id": "newt000001", "name": "Zed Ng", "dept": "Maths"}, ""], ["school", "name", "X"],
           ["set", ["odd"], "x", "y", 1]]
    def flt(sp, ops): return [], [(i, "Not yours.") for i in range(len(ops))]
    v0 = store.setup_record()["v"]
    store.apply_changes(ops, "c1", filter=flt, by=H.by_of("Ann Lee", "password"))
    assert store.setup_record()["v"] == v0, "nothing was applied"
    a, b, c, d, e = H.read(kinds=["setup-refused"])[::-1]
    assert (a["label"], a["where"], a["why"]) == (lab, "Step 5 · Teacher Deployment Editor", "Not yours.") and a["depts"] == [d0, d1], a
    assert a["text"] == H._cut(f"Refused: {lab}: subject → {other['subject']}"), a["text"]
    assert b["depts"] == [d0] and b["text"] == H._cut(f"Refused: {lab}: periods → 3"), b
    assert (c["label"], c["depts"], c["text"], c["where"]) == ("Zed Ng", ["Maths"], "Refused: Add Zed Ng", "Step 4 · Teachers"), c
    assert (d["label"], d["where"], d["depts"]) == ("name", "School & day", []) and d["text"].startswith("Refused: name: "), d
    assert (e["label"], e["text"], e["where"], e["depts"], e["op"]) == (None, "Refused", "Setup", [], ["set", ["odd"], "x", "y", 1]), e
    assert [x["text"] for x in H.read(dept=d1, kinds=["setup-refused"])] == [a["text"]], "the department filter finds it"
    assert all(x["as"] == "Ann Lee" and x["via"] == "password" for x in (a, b, c, d, e))

@t
def an_automatic_saved_copy_is_by_the_app():
    _setup_in_store()
    store._last_point[0] = 0                                           # long enough since the last one: the change takes a copy first
    store.apply_changes([["school", "timetable", "Term 3"]], "c1", by=H.by_of("Ann Lee", "password"))
    cp = store.copies()[0]; assert (cp["what"], cp["who"]) == ("While working", "The app"), cp

@t
def where_admin_and_sign_in_also_find_entries_by_their_kind():
    fresh()
    H.add({"kind": "account", "as": "A", "text": "old account"})        # written before account entries carried a where
    H.add({"kind": "account", "as": "A", "where": "Admin", "text": "new account"})
    H.add({"kind": "signin", "as": "A", "text": "old sign-in"})
    H.add({"kind": "signin", "as": "A", "where": "Sign-in", "text": "new sign-in"})
    H.add({"kind": "setup-replaced", "as": "A", "where": "Setup", "text": "Saved"})
    H.add({"kind": "setup", "as": "A", "where": "Step 4 · Teachers", "text": "a row"})
    assert [e["text"] for e in H.read(where="Admin")] == ["new account", "old account"]
    assert [e["text"] for e in H.read(where="Sign-in")] == ["new sign-in", "old sign-in"], "picking Sign-in shows the sign-ins"
    assert [e["text"] for e in H.read(where="Setup")] == ["Saved"] and [e["text"] for e in H.read(where="Step 4 · Teachers")] == ["a row"]
    assert [e["text"] for e in H.read()] == ["a row", "Saved", "new account", "old account"], "sign-ins stay hidden otherwise"

@t
def class_parents_ops_are_app_entries():
    spec = _setup_in_store(parents=True)
    cid = next(x["_id"] for x in spec["classes"] if x["class"] == "1A")
    by = H.by_of("Ann Lee", "password")
    store.apply_changes([["set", "classes", cid, "parents", ["Pastoral B"]]], "c1", by=by)
    es = H.read()
    mine = [e for e in es if e["kind"] == "setup" and e["as"] == "Ann Lee"]; app = [e for e in es if e["kind"] == "app"]
    assert len(mine) == 1 and app, es
    assert all(e["as"] == "The app" and e["via"] == "app" and e["follows"] == mine[0]["batch"] for e in app), app
    assert all(e["v"] == mine[0]["v"] + 1 for e in app)

@t
def replace_and_restore_record_who():
    spec = _setup_in_store()
    by = H.by_of("Ann Lee", "password")
    spec2 = copy.deepcopy(spec); spec2["school"]["timetable"] = "Whole"
    store.replace_setup(spec2, "Saved", by=by)
    e = H.read(limit=1)[0]
    assert e["kind"] == "setup-replaced" and e["text"] == "Saved" and e["where"] == "Setup" and e["as"] == "Ann Lee", e
    cp = store.copies()
    assert cp[0]["who"] == "Ann Lee" and "Before: Saved" in cp[0]["what"], cp   # the point taken before the save
    store.replace_setup(spec2, "Second", by=by)
    assert store.copies()[0]["who"] == "Ann Lee", store.copies()
    store.restore(store.copies()[0]["id"], by=H.by_of("Bo Tan", "password"))
    e = H.read(limit=1)[0]
    assert e["kind"] == "setup-replaced" and e["as"] == "Bo Tan" and e["text"].startswith("Restored "), e
    assert store.copies()[0]["who"] == "Bo Tan"
    f = os.path.join(store.HIST, store._points()[0]); x = store.read_json(f); x.pop("who", None); store.write_json(f, x)
    assert store.copies()[-1]["who"] == "Unknown"

@t
def history_failure_does_not_stop_the_change():
    _setup_in_store()
    real = H.add_many
    def boom(es): raise OSError("disk")
    H.add_many = boom
    err = io.StringIO()
    try:
        v0 = store.setup_record()["v"]
        with contextlib.redirect_stderr(err):
            v, _, _ = store.apply_changes([["school", "timetable", "Term 5"]], "c1")
    finally:
        H.add_many = real
    assert v == v0 + 1 and store.setup_record()["spec"]["school"]["timetable"] == "Term 5"
    assert err.getvalue() == "warning: the history could not be written (OSError)\n", err.getvalue()

@t
def entry_building_failure_is_not_silent():
    _setup_in_store()
    real = H.setup_entries
    def boom(*a, **k): raise ValueError("secret-ish contents")
    H.setup_entries = boom
    err = io.StringIO()
    try:
        v0 = store.setup_record()["v"]
        with contextlib.redirect_stderr(err):
            v, _, _ = store.apply_changes([["school", "timetable", "Term 4"]], "c1")
    finally:
        H.setup_entries = real
    assert v == v0 + 1 and store.setup_record()["spec"]["school"]["timetable"] == "Term 4"
    assert err.getvalue() == "warning: the history could not be written (ValueError)\n", err.getvalue()

# ------------------------------------------------------------------------------------------------ the history API
import json, secrets  # noqa: E402
os.environ.update(SECRET_KEY=secrets.token_hex(16), COMMITTEE_CODE=secrets.token_hex(8))
import app as A  # noqa: E402

def committee():
    c = A.app.test_client()
    with c.session_transaction() as s: s["role"] = "committee"
    return c

def api(c, q=""):
    r = c.get("/api/history" + q); return r.status_code, r.get_json()

@t
def api_needs_the_history_right():
    fresh()
    c = A.app.test_client()
    with c.session_transaction() as s: s["role"] = "teacher"
    assert c.get("/api/history").status_code in (401, 403) and c.get("/history").status_code in (302, 401, 403)
    assert A.app.test_client().get("/api/history").status_code == 401

@t
def api_filters_pages_and_caps():
    fresh()
    day = datetime.datetime(2026, 11, 18, 12, 0).timestamp()
    H.add({"kind": "setup", "who": "Ann Lee", "as": "Ann Lee", "where": "Step 4 · Teachers", "depts": ["MA"], "text": "a", "ts": day})
    H.add({"kind": "setup", "who": "Bob Tan", "as": "Bob Tan", "where": "Step 6 · Configuration & constraints", "depts": ["SC"], "text": "b", "ts": day + 86400})
    H.add({"kind": "signin", "who": "Ann Lee", "as": "Ann Lee", "text": "in", "ts": day + 86400})
    c = committee()
    s, d = api(c)
    assert s == 200 and [e["text"] for e in d["entries"]] == ["b", "a"] and d["more"] is False and d["admin"] is False, d
    assert [e["text"] for e in api(c, "?signins=1")[1]["entries"]] == ["in", "b", "a"]
    assert [e["text"] for e in api(c, "?who=ann")[1]["entries"]] == ["a"]
    assert [e["text"] for e in api(c, "?who=ann&signins=1")[1]["entries"]] == ["in", "a"]
    assert [e["text"] for e in api(c, "?where=Step 4 · Teachers")[1]["entries"]] == ["a"]
    assert [e["text"] for e in api(c, "?dept=SC")[1]["entries"]] == ["b"]
    assert [e["text"] for e in api(c, "?from=2026-11-19")[1]["entries"]] == ["b"]
    assert [e["text"] for e in api(c, "?to=2026-11-18")[1]["entries"]] == ["a"]
    assert [e["text"] for e in api(c, "?from=2026-11-18&to=2026-11-19")[1]["entries"]] == ["b", "a"]
    d = api(c, "?limit=1")[1]
    assert [e["text"] for e in d["entries"]] == ["b"] and d["more"] is True
    d2 = api(c, "?limit=1&before=" + d["entries"][-1]["id"])[1]
    assert [e["text"] for e in d2["entries"]] == ["a"] and d2["more"] is False
    for q in ("?from=yesterday", "?to=2026-13-40", "?limit=abc", "?limit=0", "?from=2026-11-19&to=2026-11-18"):
        s, d = api(c, q); assert s == 400 and isinstance(d["error"], str) and d["error"].endswith("."), (q, s, d)
    for i in range(3): H.add({"kind": "app", "text": f"x{i}"})
    assert len(api(c, "?limit=100000")[1]["entries"]) == 5   # capped at 500, never an error
    assert A.HISTORY_MAX == 500

@t
def api_says_whether_the_viewer_is_admin():
    fresh()
    c = committee()
    with c.session_transaction() as s: s["role"] = "committee"
    assert api(c)[1]["admin"] is False

@t
def history_page_is_served():
    r = committee().get("/history")
    assert r.status_code == 200 and b"history.js" in r.data

@t
def who_filter_is_one_read_and_pages_cleanly():
    fresh()
    for i in range(1200):
        H.add({"kind": "setup", "as": "Rare Person" if i % 400 == 0 else "Bulk Bob", "text": f"n{i}"})
    calls = []
    real = H.read
    def spy(*a, **k):
        if not k.get("kinds"): calls.append(1)    # the read for Put back marks (kinds given) is a second one, by design
        return real(*a, **k)
    A.history.read = spy
    try:
        c = committee()
        d = api(c, "?who=rare&limit=2")[1]
    finally:
        A.history.read = real
    assert len(calls) == 1 and [e["text"] for e in d["entries"]] == ["n1200"[:0] or "n800", "n400"] and d["more"] is True, (calls, d["entries"])
    d2 = api(c, "?who=RARE&limit=2&before=" + d["entries"][-1]["id"])[1]
    assert [e["text"] for e in d2["entries"]] == ["n0"] and d2["more"] is False
    assert [e["text"] for e in api(c, "?who=rare&limit=3")[1]["entries"]] == ["n800", "n400", "n0"]

def offered():
    js = open(os.path.join(ROOT, "static", "history.js"), encoding="utf-8").read()
    return re.findall(r'"([^"]+)"', re.search(r"const WHERES = \[(.*?)\];", js, re.S).group(1))

@t
def the_page_offers_every_where_the_app_writes():
    written = set(H.WHERE.values()) | {"School & day", "Setup", "Step 8 · Upload and edit", "Step 9 · Publish", "Relief", "Relief settings", "Exams and events", "Admin", "Sign-in"}
    assert written <= set(offered()), written - set(offered())

@t
def api_each_where_returns_its_entries():
    fresh()
    kind = {"Admin": "account", "Sign-in": "signin", "Setup": "setup-replaced", "Relief": "relief", "Relief settings": "relief", "Exams and events": "exams"}
    for w in offered(): H.add({"kind": kind.get(w, "draft" if w.startswith(("Step 8", "Step 9")) else "setup"), "as": "A", "where": w, "text": "in " + w})
    H.add({"kind": "account", "as": "A", "text": "an older account entry"}); H.add({"kind": "signin", "as": "A", "text": "an older sign-in"})
    c = committee()
    for w in offered():
        got = [e["text"] for e in api(c, "?where=" + urllib.parse.quote(w))[1]["entries"]]
        want = ["in " + w] + {"Admin": ["an older account entry"], "Sign-in": ["an older sign-in"]}.get(w, [])
        assert sorted(got) == sorted(want), (w, got)

@t
def unsafe_links_are_dropped():
    fresh()
    for l in ("//evil.example", "/\\evil.example", "/\t/evil.example", "http://x.example", "/exams"):
        H.add({"kind": "exams", "as": "A", "text": l, "link": l})
    got = {e["text"]: e.get("link") for e in api(committee())[1]["entries"]}
    assert got == {"//evil.example": None, "/\\evil.example": None, "/\t/evil.example": None, "http://x.example": None, "/exams": "/exams"}, got

# ------------------------------------------------------------------------------------------------ who sees which history
from accounts import passwords as PW, people as P  # noqa: E402
HANA, ANN, BOB, EVA, TOM = "Hana Test", "Ann Test", "Bob Test", "Eva Test", "Tom Test"
P.update(lambda d: d["people"].update({
    HANA: dict(group="hod", added=True, depts=["Maths"], username="hana.t", pw=PW.hash_pw(secrets.token_hex(8))),
    EVA: dict(group="executive", added=True, extras=dict(exams="2999-12-31")),
    TOM: dict(group="teacher", added=True)}))

def as_person(name, via="code"):
    c = A.app.test_client()
    with c.session_transaction() as s:
        s.update(who=name, via=via, n=P.record(P.load(), name)["n"])
        if via == "password": s["exp"] = time.time() + 3600
    return c

def texts(c, q=""): return [e["text"] for e in api(c, q)[1]["entries"]]

@t
def a_head_sees_their_departments_and_their_own():
    fresh()
    H.add({"kind": "setup", "who": ANN, "as": ANN, "where": "Step 4 · Teachers", "depts": ["Maths"], "text": "maths"})
    H.add({"kind": "setup", "who": BOB, "as": BOB, "where": "Step 4 · Teachers", "depts": ["Science"], "text": "science"})
    H.add({"kind": "setup", "who": HANA, "as": HANA, "where": "Step 6 · Configuration & constraints", "depts": [], "text": "hana's own"})
    H.add({"kind": "account", "who": ANN, "as": ANN, "where": "Admin", "text": "account by Ann"})
    H.add({"kind": "signin", "who": BOB, "as": BOB, "text": "Bob in"})
    c = as_person(HANA, "password")
    s, d = api(c)
    assert s == 200 and [e["text"] for e in d["entries"]] == ["hana's own", "maths"], d
    assert d["scope"] == "dept" and d["depts"] == ["Maths"] and d["download"] is False, d
    assert texts(c, "?signins=1") == ["hana's own", "maths"]
    assert texts(c, "?dept=Science") == [] and texts(c, "?dept=Maths") == ["maths"]
    H.add({"kind": "signin", "who": HANA, "as": HANA, "text": "Hana in"})
    assert texts(c, "?signins=1") == ["Hana in", "hana's own", "maths"]
    k = api(committee())[1]; assert k["scope"] == "all" and k["download"] is True and len(k["entries"]) == 4, k

@t
def own_scope_sees_only_own():
    fresh()
    H.add({"kind": "exams", "who": EVA, "as": EVA, "text": "mine"})
    H.add({"kind": "exams", "who": ANN, "as": ANN, "text": "not mine"})
    H.add({"kind": "signin", "who": EVA, "as": EVA, "text": "Eva in"})
    H.add({"kind": "signin", "who": ANN, "as": ANN, "text": "Ann in"})
    c = as_person(EVA)
    s, d = api(c)
    assert s == 200 and [e["text"] for e in d["entries"]] == ["mine"] and d["scope"] == "own" and d["download"] is False, d
    assert texts(c, "?signins=1") == ["Eva in", "mine"]
    assert c.get("/history").status_code == 200

@t
def a_teacher_sees_only_their_own():
    fresh()
    H.add({"kind": "relief", "who": TOM, "as": TOM, "where": "Relief", "text": "mine"}); H.add({"kind": "relief", "who": "Someone Else", "as": "Someone Else", "where": "Relief", "text": "theirs"})
    code, j = api(as_person(TOM))
    assert code == 200 and [e["text"] for e in j["entries"]] == ["mine"] and j["scope"] == "own" and j["download"] is False, j
    assert as_person(TOM).get("/history").status_code == 200

@t
def own_scope_hides_addresses_and_what_a_code_does_not_open():
    fresh()
    H.add({"kind": "signin", "who": TOM, "as": TOM, "ok": False, "addr": "10.0.0.9", "where": "Sign-in", "text": "refused"})
    H.add({"kind": "account", "who": TOM, "as": TOM, "where": "Admin", "text": "gave access", "changes": [{"name": "X", "field": "note", "was": None, "now": "Only admins see this"}]})
    H.add({"kind": "setup", "who": TOM, "as": TOM, "where": "Step 5 · Teacher Deployment Editor", "text": "a row"})
    H.add({"kind": "relief", "who": TOM, "as": TOM, "where": "Relief", "text": "mine"})
    es = api(as_person(TOM), "?signins=1")[1]["entries"]
    assert [e["text"] for e in es] == ["mine", "refused"] and "addr" not in es[1], es      # a code does not open the setup or the admin page
    by = {e["text"]: e for e in api(committee(), "?signins=1")[1]["entries"]}
    assert by["refused"]["addr"] == "10.0.0.9" and "gave access" in by and "a row" in by, by

@t
def own_scope_parses_only_the_lines_that_name_them():
    fresh()
    H.add_many([{"kind": "relief", "who": f"Person {i}", "as": f"Person {i}", "where": "Relief", "text": f"t{i}"} for i in range(300)])
    H.add({"kind": "relief", "who": TOM, "as": TOM, "where": "Relief", "text": "mine"})
    n, real = [], H.json.loads
    def spy(x, *a, **k):
        if isinstance(x, str) and '"relief"' in x: n.append(1)     # the history's lines only (other json is read too)
        return real(x, *a, **k)
    H.json.loads = spy
    try: got = api(as_person(TOM))[1]["entries"]
    finally: H.json.loads = real
    assert [e["text"] for e in got] == ["mine"] and len(n) == 1, len(n)

@t
def a_line_separator_inside_a_text_keeps_the_entry():
    fresh()
    H.add({"kind": "exams", "who": "Ann", "as": "Ann", "where": "Exams and events", "text": "Mid\u2028year\u0085test"})
    assert [e["text"] for e in H.read()] == ["Mid\u2028year\u0085test"]

@t
def no_history_right_is_401():
    fresh()
    c = A.app.test_client()
    with c.session_transaction() as s: s["role"] = "teacher"   # the shared teacher code: nobody's own history
    assert c.get("/api/history").status_code == 401
    r = c.get("/history"); assert r.status_code == 302 and r.headers["Location"].endswith("/login"), r.headers

@t
def old_files_in_the_server_s_clock_are_read_at_a_month_s_edge():
    fresh()
    # stage 1 (live) named its files by the server's UTC clock: 1 Oct 04:00 school time is 30 Sep 20:00 UTC, kept in 2026-09.jsonl
    ts = datetime.datetime(2026, 10, 1, 4, 0, tzinfo=H.SCHOOL_TZ).timestamp()
    e = {"id": H._new_id(), "kind": "setup", "ts": ts, "at": "2026-09-30T20:00:00+00:00", "who": "Ann", "as": "Ann", "where": "Step 1 \u00b7 Venues", "text": "old clock"}
    os.makedirs(H.DIR, exist_ok=True)
    with open(os.path.join(H.DIR, "2026-09.jsonl"), "w") as f: f.write(json.dumps(e) + "\n")
    since = datetime.datetime(2026, 10, 1, 2, 0, tzinfo=H.SCHOOL_TZ).timestamp()
    assert [x["text"] for x in H.read(since=since)] == ["old clock"]

@t
def days_are_school_days():
    fresh()
    os.environ["TZ"] = "UTC"; time.tzset()
    ev = lambda *a: datetime.datetime(*a, tzinfo=H.SCHOOL_TZ).timestamp()
    a = H.add({"kind": "app", "text": "late", "ts": ev(2026, 11, 18, 23, 30)})
    b = H.add({"kind": "app", "text": "early", "ts": ev(2026, 11, 19, 0, 30)})
    assert a["at"].endswith("+08:00") and a["at"].startswith("2026-11-18T23:30"), a["at"]
    c = committee()
    assert texts(c, "?from=2026-11-19&to=2026-11-19") == ["early"]
    assert texts(c, "?from=2026-11-18&to=2026-11-18") == ["late"]
    assert H.day_start("2026-11-19") == ev(2026, 11, 19) and H.day_start("nope") is None and H.day_start(None) is None

@t
def since_param():
    fresh()
    for i in range(3): H.add({"kind": "app", "text": f"e{i}", "ts": 1800000000 + i * 10})
    c = committee()
    assert texts(c, "?since=1800000010") == ["e2", "e1"]
    s, d = api(c, "?since=abc"); assert s == 400 and d == {"error": "Pick a time as a number of seconds."}, d

@t
def months_before_since_are_not_read():
    fresh()
    ev = lambda m, d=10: datetime.datetime(2026, m, d, 12, tzinfo=H.SCHOOL_TZ).timestamp()
    for m in (8, 9, 10): H.add({"kind": "app", "text": f"m{m}", "ts": ev(m)})
    calls = []
    real = H._lines
    def spy(name): calls.append(name); return real(name)
    H._lines = spy
    try: got = H.read(since=ev(10, 1))
    finally: H._lines = real
    assert [e["text"] for e in got] == ["m10"] and calls == ["2026-10.jsonl"], calls
    assert [e["text"] for e in H.read(since=ev(9, 1))] == ["m10", "m9"]
    # an entry at the very start of a month is in that month's file, and a `since` after the month ends skips it
    assert H.read(since=ev(11, 1), allow=lambda e: True) == []

@t
def allow_filters_last_and_when_text_is_school_time():
    fresh()
    H.add({"kind": "signin", "who": "A", "as": "A", "text": "in"}); H.add({"kind": "app", "text": "x"})
    assert [e["text"] for e in H.read(signins=True, allow=lambda e: e.get("who") == "A")] == ["in"]
    assert H.when_text(datetime.datetime(2026, 11, 18, 8, 12, tzinfo=datetime.timezone.utc).timestamp()) == "Wednesday 18 Nov, 4:12 pm"   # 18 Nov 2026 is a Wednesday (the plan says Tuesday)
    assert H.short_when(datetime.datetime(2026, 11, 19, 2, 2, tzinfo=datetime.timezone.utc).timestamp()) == "19 Nov, 10:02 am"
    assert H.short_when(datetime.datetime(2026, 11, 19, 4, 0, tzinfo=datetime.timezone.utc).timestamp()) == "19 Nov, 12:00 pm"
    assert H.short_when(datetime.datetime(2026, 11, 19, 16, 5, tzinfo=datetime.timezone.utc).timestamp()) == "20 Nov, 12:05 am"

def _sheet(r):
    import openpyxl
    return openpyxl.load_workbook(io.BytesIO(r.data))["History"]

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
HEAD_ROW = ["Day", "Time", "Who", "Signed in with", "Where", "What", "Was", "Became", "Departments"]

@t
def download_is_the_committees():
    fresh()
    H.add({"kind": "setup", "who": ANN, "as": ANN, "where": "Step 4 · Teachers", "depts": ["Maths"], "text": "maths"})
    assert as_person(HANA, "password").get("/api/history/download").status_code == 401
    r = committee().get("/api/history/download")
    today = datetime.datetime.now(H.SCHOOL_TZ).strftime("%Y-%m-%d")
    assert r.status_code == 200 and r.mimetype == XLSX, (r.status_code, r.mimetype)
    assert r.headers["Content-Disposition"] == f"attachment; filename=history-{today}.xlsx", r.headers["Content-Disposition"]
    rows = [[c.value for c in row] for row in _sheet(r).iter_rows()]
    assert rows[0] == HEAD_ROW and len(rows) == 2 and rows[1][2] == ANN and rows[1][5] == "maths" and rows[1][8] == "Maths", rows
    assert committee().get("/api/history/download?from=nope").status_code == 400

@t
def download_keeps_the_filters():
    fresh()
    H.add({"kind": "setup", "who": ANN, "as": ANN, "where": "Step 4 · Teachers", "depts": ["Maths"], "text": "maths"})
    H.add({"kind": "setup", "who": BOB, "as": BOB, "where": "Step 4 · Teachers", "depts": ["Science"], "text": "science"})
    H.add({"kind": "signin", "who": BOB, "as": BOB, "via": "shared", "text": "in"})
    rows = [[c.value for c in row] for row in _sheet(committee().get("/api/history/download?dept=Maths")).iter_rows()]
    assert [r[5] for r in rows] == ["What", "maths"], rows
    rows = [[c.value for c in row] for row in _sheet(committee().get("/api/history/download?signins=1&who=bob")).iter_rows()]
    assert [(r[5], r[3]) for r in rows[1:]] == [("in", "shared code"), ("science", None)], rows

@t
def download_cells_are_never_formulas():
    fresh()
    for ch in "=+-@":
        H.add({"kind": "setup", "who": ANN, "as": ch + "as", "where": "Step 4 · Teachers", "depts": [ch + "d"], "text": ch + "text",
               "was": ch + "was", "now": ch + "now"})
    ws = _sheet(committee().get("/api/history/download"))
    seen = set()
    for row in list(ws.iter_rows())[1:]:
        assert row[2].value[1:] == "as" and row[5].value[1:] == "text" and row[6].value[1:] == "was" and row[7].value[1:] == "now" and row[8].value[1:] == "d", [c.value for c in row]
        for c in row:
            if c.value is not None: assert c.data_type == "s", (c.coordinate, c.data_type, c.value)   # an empty cell has no value to misread
        seen.add(row[5].value[0])
    assert seen == set("=+-@"), seen

@t
def download_says_when_there_are_more():
    fresh()
    for i in range(5): H.add({"kind": "app", "text": f"e{i}"})
    real = A.HISTORY_DOWNLOAD_MAX; A.HISTORY_DOWNLOAD_MAX = 3
    try: rows = [[c.value for c in row] for row in _sheet(committee().get("/api/history/download")).iter_rows()]
    finally: A.HISTORY_DOWNLOAD_MAX = real
    assert [r[5] for r in rows[1:4]] == ["e4", "e3", "e2"] and len(rows) == 5, rows
    assert rows[4][0] == "There are more entries than one download holds: pick fewer days.", rows[4]
    assert len(_sheet(committee().get("/api/history/download"))["A"]) == 6


@t
def download_of_many_rows_is_quick():
    fresh()
    H.add_many([{"kind": "app", "text": f"e{i}"} for i in range(3000)])
    real = A.HISTORY_DOWNLOAD_MAX; A.HISTORY_DOWNLOAD_MAX = 5000
    try:
        t0 = time.time(); r = committee().get("/api/history/download"); took = time.time() - t0
    finally: A.HISTORY_DOWNLOAD_MAX = real
    print(f"3000-row download took {took:.2f}s")
    assert r.status_code == 200 and took < 5, (r.status_code, took)
    assert len(list(_sheet(r).iter_rows())) == 3001

@t
def download_drops_characters_excel_refuses():
    fresh()
    H.add({"kind": "setup", "who": ANN, "as": "An\x0bn", "where": "Step 4 · Teachers", "text": "te\x01xt", "was": "w\x01", "now": "n\x02"})
    r = committee().get("/api/history/download")
    assert r.status_code == 200, r.status_code
    row = [c.value for c in list(_sheet(r).iter_rows())[1]]
    assert row[2] == "Ann" and row[5] == "text" and row[6] == "w" and row[7] == "n", row

SINCE = "Since you last signed in"

@t
def a_mistyped_line_never_takes_the_page_down():
    fresh()
    CY = "Cy Test"
    P.update(lambda d: d["people"].update({CY: dict(group="committee", added=True, username="cy.t", pw=PW.hash_pw(secrets.token_hex(8)))}))
    t0 = time.time() - 3600
    P.update(lambda d: [d["people"][n].update(signins=[t0, time.time()]) for n in (CY, HANA)])
    row = dict(kind="setup", op="set", section="teachers", row="r1", field="short", who=ANN, where="Step 4 · Teachers", depts=["Maths"], **{"as": ANN})
    good = H.add(dict(row, batch="bgood", was="A", now="B", text="good"))
    bad = [dict(row, batch="bts", was="B", now="C", text="ts as text", ts="soon"),
           dict(row, batch="bdepts", field="name", text="depts as a number", depts=5),
           dict(row, batch="bnested", field="dept", text="depts holding a list", depts=[["Maths"]]),
           dict(row, batch="bvia", field="note", text="via as a list", via=["password"]),
           dict(row, batch="bkind", text="kind as a list", kind=["setup"])]
    with open(month_file(good), "a") as f:
        for i, b in enumerate(bad): f.write(json.dumps(dict(b, id=good["id"] + str(i), at=good["at"], ts=b.get("ts", good["ts"] + i + 1))) + "\n")
    cy, hana = as_person(CY, "password"), as_person(HANA, "password")
    for c in (cy, hana, committee()):
        for q in ("", "?from=2020-01-01", f"?since={t0}", "?dept=Maths", "?signins=1"):
            s, d = api(c, q); assert s == 200, (q, s)
    s, d = api(cy)
    assert {"good", "ts as text", "depts as a number", "via as a list"} <= {e["text"] for e in d["entries"]}, d
    assert "back" in next(e for e in d["entries"] if e["text"] == "good"), d        # still marked (a line with no readable time is not placed after it)
    seen = {e["text"] for e in api(hana)[1]["entries"]}                    # the head: Maths rows; a line whose departments cannot be read is no one's department
    assert {"good", "ts as text", "via as a list"} <= seen and not {"depts as a number", "depts holding a list"} & seen, seen
    r = cy.get("/api/history/download"); assert r.status_code == 200, r.status_code
    rows = {x[5]: x for x in ([c.value for c in row] for row in _sheet(r).iter_rows())}
    assert rows["via as a list"][3] == "['password']" and rows["ts as text"][0] in (None, ""), rows
    for c in (cy, hana):
        r = c.get("/home"); assert r.status_code == 200 and SINCE in r.data.decode(), r.data.decode()[:300]
    assert cy.post("/api/history/back", json={"id": good["id"] + "0"}).status_code == 409

print(f"{COUNT} history tests passed")

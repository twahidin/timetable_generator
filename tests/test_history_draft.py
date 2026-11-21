"""Plain-assert tests for step 8, publishing and relief in the history: .venv/bin/python tests/test_history_draft.py"""
import io, os, secrets, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = tempfile.mkdtemp()
os.environ.pop("HEADS_CODE", None)
os.environ.update(DATA_DIR=DATA, SECRET_KEY=secrets.token_hex(16), AI_PROVIDER="anthropic", AI_API_KEY="", COMMITTEE_CODE=secrets.token_hex(4), TEACHER_CODE=secrets.token_hex(4), STUDENT_CODE=secrets.token_hex(4))
sys.path.insert(0, ROOT)
import openpyxl  # noqa: E402
import app as A, draft, history as H, store  # noqa: E402
from accounts import passwords as PW, people as P  # noqa: E402
from ttgen.template import write_template  # noqa: E402

NAME = "Ms Dana Yeo"; PWD = secrets.token_hex(8)
P.update(lambda d: d["people"].setdefault(NAME, {}).update(group="committee", username="dana.yeo", pw=PW.hash_pw(PWD)))
c = A.app.test_client()
assert c.post("/login/password", data=dict(username="dana.yeo", password=PWD)).status_code == 302

def workbook(rows):
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Lessons"
    ws.append(["Lesson ID", "Day", "Start period", "End period", "Periods", "Starts", "Ends", "Level", "Block", "Classes", "Subject", "Group", "Teachers", "Room", "After school", "Rain room"])
    for r in rows:
        ws.append([r["id"], r["day"], r["p"], r["p"] + r["n"] - 1, r["n"], "", "", r["level"], "", ", ".join(r["classes"]), r["subject"], "Entire Class", ", ".join(r.get("teachers", [])), "", "", ""])
    buf = io.BytesIO(); wb.save(buf); return buf.getvalue()

assert c.put("/api/setup", json=A.sample("primary")).status_code == 200
SPEC = c.get("/api/setup").get_json()["spec"]
LEVEL = SPEC["classes"][0]["level"]
CL = [x["class"] for x in SPEC["classes"] if x["level"] == LEVEL][0]
DAYS = list(SPEC["day_structure"][LEVEL].keys())
SUBJ = SPEC["subjects"][0]["subject"]; TEACHER = SPEC["teachers"][0]["name"]
p = os.path.join(tempfile.mkdtemp(), "setup.xlsx"); write_template(SPEC, p); SETUP = open(p, "rb").read()
ROWS = [dict(id=1, day=DAYS[0], p=0, n=1, level=LEVEL, classes=[CL], subject=SUBJ, teachers=[TEACHER])]

def entries(kind): return H.read(kinds=[kind])
def count(): return len(H.read())
def mine(e): assert e["who"] == NAME and e["as"] == NAME and e["via"] == "password", e

def upload():
    return c.post("/api/draft", data=dict(setup=(io.BytesIO(SETUP), "setup.xlsx"), timetable=(io.BytesIO(workbook(ROWS)), "plan one.xlsx"), replace="1"), content_type="multipart/form-data")

COUNT = 0
def t(f):
    global COUNT
    f(); COUNT += 1

@t
def upload_fix_undo_are_recorded():
    n = count(); r = upload(); assert r.status_code == 200, r.get_json()
    e = H.read(kinds=["draft"], limit=1)[0]; mine(e)
    assert (e["what"], e["where"], e["text"], e["link"]) == ("upload", "Step 8 · Upload and edit", "Uploaded plan one.xlsx", "/"), e
    r = c.post("/api/draft/fix", json=dict(kind="lift", id=1)); assert r.status_code == 200, r.get_json()
    f = H.read(kinds=["draft"], limit=1)[0]; mine(f); text = draft.last_fix_text()
    assert f["what"] == "fix" and f["text"] == text and text and f["where"] == "Step 8 · Upload and edit", f
    r = c.post("/api/draft/undo"); assert r.status_code == 200
    u = H.read(kinds=["draft"], limit=1)[0]; mine(u); assert u["what"] == "undo" and u["text"] == f"Undid: {text}", u
    assert count() >= n + 3 and draft.last_fix_text() is None

@t
def two_fixes_are_one_entry():
    r = c.post("/api/draft/fixes", json=dict(fixes=[dict(kind="move", id=1, d=1, p=1)])); assert r.status_code == 200, r.get_json()
    e = H.read(kinds=["draft"], limit=1)[0]; mine(e)
    assert e["what"] == "fix" and e["text"].startswith("1 fix: ") and draft.last_fix_text() in e["text"], e
    assert c.post("/api/draft/undo").status_code == 200

@t
def undoing_a_batch_names_every_fix_in_it():
    r = c.post("/api/draft/fixes", json=dict(fixes=[dict(kind="move", id=1, d=1, p=1), dict(kind="move", id=1, d=2, p=1)])); assert r.status_code == 200, r.get_json()
    ts = draft.last_batch_texts(); assert len(ts) == 2 and all(ts), ts
    assert c.post("/api/draft/undo").status_code == 200
    u = H.read(kinds=["draft"], limit=1)[0]; mine(u)
    assert (u["what"], u["text"]) == ("undo", "Undid 2 fixes: " + "; ".join(ts)), u
    assert draft.last_fix_text() is None

@t
def refused_actions_write_nothing():
    n = count()
    assert c.post("/api/draft/undo").status_code == 400          # nothing to undo
    assert c.post("/api/draft/fix", json=dict(kind="move", id=999, d=DAYS[0], p=0)).status_code == 400
    assert c.post("/api/draft/decide", json=dict(key="nope", answer="accept")).status_code == 400
    bad = A.app.test_client()
    assert bad.post("/api/draft/undo").status_code in (401, 403)
    assert count() == n, H.read(limit=count() - n)

@t
def a_decision_is_recorded_and_threads_who_to_the_setup():
    w = draft.info()["warnings"]; assert w, "the sample draft has no warning to decide"
    if w:
        k = next((x for x in w if x["kind"] == "deployment" and x["ops"]), None)
        if k:
            r = c.post("/api/draft/decide", json=dict(key=k["key"], answer="step5")); assert r.status_code == 200, r.get_json()
            s = H.read(kinds=["setup"], limit=1)
            assert s and s[0]["who"] == NAME and s[0]["as"] == NAME, s
            d = H.read(kinds=["draft"], limit=1)[0]; mine(d)
            assert d["what"] == "decide" and d["text"] == f"Decided: step5 — {k['text']}", d
            cp = store.copies()[0]                                     # the saved copy taken first names who pressed it
            assert (cp["what"], cp["who"]) == ("Before updating step 5 from the timetable", NAME), cp
            global STEP5; STEP5 = True; return
        k = w[0]
        r = c.post("/api/draft/decide", json=dict(key=k["key"], answer="accept")); assert r.status_code == 200, r.get_json()
        d = H.read(kinds=["draft"], limit=1)[0]; mine(d)
        assert d["what"] == "decide" and d["text"] == f"Decided: accept — {k['text']}", d

@t
def publishing_is_recorded():
    real = draft.publish; draft.publish = lambda: dict(published=True)
    try:
        n = len(entries("draft")); r = c.post("/api/draft/publish"); assert r.status_code == 200, r.get_json()
        assert len(entries("draft")) == n + 1
        e = entries("draft")[0]; mine(e)
        assert (e["what"], e["where"], e["text"], e["link"]) == ("publish", "Step 9 · Publish", "Published the timetable", "/"), e
    finally: draft.publish = real

@t
def a_refused_publish_writes_nothing():
    real = draft.publish
    def refuse(): raise draft.Critical(1)
    draft.publish = refuse
    try:
        n = count(); r = c.post("/api/draft/publish"); assert r.status_code == 409, r.status_code; assert count() == n
    finally: draft.publish = real

@t
def a_history_failure_never_fails_the_action():
    real = H.add
    H.add = lambda e: (_ for _ in ()).throw(OSError("full"))
    try:
        assert c.post("/api/draft/fix", json=dict(kind="lift", id=1)).status_code == 200
        assert c.post("/api/draft/undo").status_code == 200
    finally: H.add = real

assert globals().get("STEP5"), "no decision changed the setup"
@t
def relief_settings_save_is_recorded_a_refused_one_is_not():
    from relief import people as RP
    pub = RP.fake_pub([dict(name="Ms Evelyn Koh", dept="Science")])
    TERM = dict(terms=[dict(name="Term 4", start="2026-09-07", end="2026-11-20", starts_as="Odd")], holidays=[])
    old = store.published; store.published = lambda: pub
    try:
        n = count(); r = c.put("/api/relief/settings", json=dict(calendar=dict(terms=[dict(name=" ", start="soon", end="later", starts_as="Odd")], holidays=[])))
        assert r.status_code == 400 and count() == n
        r = c.put("/api/relief/settings", json=dict(calendar=TERM)); assert r.status_code == 200, r.get_json()
        e = H.read(kinds=["relief"], limit=1)[0]; mine(e)
        assert (e["what"], e["where"], e["text"], e["link"]) == ("settings", "Relief settings", "Relief settings saved", "/relief"), e
    finally: store.published = old

print(f"test_history_draft: {COUNT} passed")

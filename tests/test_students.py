"""Plain-assert tests for a saved student following onto the published timetable: .venv/bin/python tests/test_students.py"""
import copy, io, json, os, secrets, shutil, sys, tempfile, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = tempfile.mkdtemp()
CODE = secrets.token_hex(4)
os.environ.pop("HEADS_CODE", None)
os.environ.update(DATA_DIR=DATA, SECRET_KEY=secrets.token_hex(16), AI_PROVIDER="anthropic", AI_API_KEY="", COMMITTEE_CODE=CODE, TEACHER_CODE=secrets.token_hex(4), STUDENT_CODE=secrets.token_hex(4))
sys.path.insert(0, ROOT)
import openpyxl  # noqa: E402
import app as A, store  # noqa: E402
import access, history, putback, students  # noqa: E402,F401
from ttgen import export as E  # noqa: E402,F401
from ttgen.template import write_template  # noqa: E402
students.FILES_WAIT = 3600   # no test before the thread test starts a remake by accident

c = A.app.test_client()
assert c.post("/login", data={"as": "committee", "code": CODE}).status_code == 302
NOSE = A.app.test_client()   # never signed in

def raises(exc, f, text=None):
    try: f()
    except exc as e:
        if text is not None: assert str(e) == text, str(e)
        return
    raise AssertionError("did not raise")

def workbook(rows):
    """a made-up Lessons workbook: rows = [dict(id, day, p, n, level, block, classes, subject, group, teachers)]"""
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Lessons"
    ws.append(["Lesson ID", "Day", "Start period", "End period", "Periods", "Starts", "Ends", "Level", "Block", "Classes", "Subject", "Group", "Teachers", "Room", "After school", "Rain room"])
    for r in rows:
        ws.append([r["id"], r["day"], r["p"], r["p"] + r["n"] - 1, r["n"], "", "", r["level"], r.get("block", ""), ", ".join(r["classes"]), r["subject"], r.get("group", "Entire Class"), ", ".join(r.get("teachers", [])), r.get("room", ""), "", r.get("rain", "")])
    buf = io.BytesIO(); wb.save(buf); return buf.getvalue()

def setup_bytes(spec):
    p = os.path.join(tempfile.mkdtemp(), "setup.xlsx"); write_template(spec, p); return open(p, "rb").read()

assert c.put("/api/setup", json=A.sample("primary")).status_code == 200
SPEC = c.get("/api/setup").get_json()["spec"]
LEVEL = SPEC["classes"][0]["level"]
CA, CB = [x["class"] for x in SPEC["classes"] if x["level"] == LEVEL][:2]
DAYS = list(SPEC["day_structure"][LEVEL].keys())
L1 = SPEC["day_structure"][LEVEL][DAYS[0]].index("L")
SUBJ, SUBJ2 = SPEC["subjects"][0]["subject"], SPEC["subjects"][1]["subject"]
T1, T2 = [x["name"] for x in SPEC["teachers"]][:2]
R1, R2 = [v["room"] for v in SPEC["venues"] if (v.get("kind") or "classroom") == "classroom"][:2]
ROWS = [   # Band A: GA1 and GA2 at the same time; GB1 alone; GX at Band A's time (a clash with either)
    dict(id=1, day=DAYS[0], p=L1, n=1, level=LEVEL, classes=[CA], subject=SUBJ, teachers=[T1], room=R1),
    dict(id=2, day=DAYS[1], p=L1, n=2, level=LEVEL, block="Band A", classes=[CA, CB], subject=SUBJ, group="GA1", teachers=[T1], room=R1),
    dict(id=2, day=DAYS[1], p=L1, n=2, level=LEVEL, block="Band A", classes=[CA, CB], subject=SUBJ2, group="GA2", teachers=[T2], room=R2),
    dict(id=3, day=DAYS[2], p=L1, n=1, level=LEVEL, classes=[CA, CB], subject=SUBJ2, group="GB1", teachers=[T2], room=R2),
    dict(id=4, day=DAYS[1], p=L1, n=1, level=LEVEL, classes=[CA, CB], subject=SUBJ2, group="GX", teachers=[T2], room=R2),
]
PEOPLE = [dict(id="S001", name="Aisha Rahman", **{"class": CA}, groups=["GA1", "GB1"]),
          dict(id="S002", name="Ben Koh", **{"class": CB}, groups=["GA2"]),
          dict(id="S003", name="Chen Li", **{"class": CA}, groups=[])]
BY = history.by_of("Tester", "password")
SNAP = os.path.join(tempfile.mkdtemp(), "published")   # the published folder of a real publish for PEOPLE, copied back by fresh()

def set_students(rows):
    """the setup's list becomes rows, by a whole replacement (publishes nothing)"""
    spec = c.get("/api/setup").get_json()["spec"]; spec["students"] = copy.deepcopy(rows)
    assert c.put("/api/setup", json=spec).status_code == 200

def publish():
    """a real publish of the setup now, with the made-up lessons; returns store.published()"""
    spec = store.setup_record()["spec"]; d = tempfile.mkdtemp()
    sp, tp = os.path.join(d, "setup.xlsx"), os.path.join(d, "timetable.xlsx")
    with open(sp, "wb") as f: f.write(setup_bytes(spec))
    with open(tp, "wb") as f: f.write(workbook(ROWS))
    store.publish(sp, tp, spec=spec, log=lambda *a: None)
    return store.published()

def change(*ops):
    """a save as the app makes it: the route answers with what happened to the students"""
    r = c.post("/api/setup/changes", json=dict(client="t", since=store.setup_record()["v"], ops=list(ops)))
    assert r.status_code == 200, r.get_data(as_text=True)
    return r.get_json()

def row_id(sid):
    return next(r["_id"] for r in store.setup_record()["spec"]["students"] if str(r.get("id")) == sid)

def pub_student(sid):
    return next((s for s in store.published()["model"]["students"] if s["id"] == sid), None)

def fresh(people=PEOPLE):
    set_students(people)
    if people is not PEOPLE: return publish()
    if not os.path.isdir(SNAP):
        publish(); shutil.copytree(store.PUB, SNAP)
    else:
        shutil.rmtree(store.PUB, ignore_errors=True); shutil.copytree(SNAP, store.PUB)
        store._cache.update(stamp=None, value=None)
    return store.published()

TESTS = []
def t(f): TESTS.append(f); return f

@t
def a_group_swap_changes_one_record_and_nothing_else():
    fresh(); before = store.published(); m0, meta0 = before["model"], dict(before["meta"])
    j = change(["merge", "students", row_id("S001"), "groups", ["GA2"], ["GA1"]])
    m1 = store.published()["model"]; meta1 = store.published()["meta"]
    assert sorted(pub_student("S001")["groups"]) == ["GA2", "GB1"]
    assert [s for s in m1["students"] if s["id"] != "S001"] == [s for s in m0["students"] if s["id"] != "S001"]
    for k in m0:                                   # every other key of the model is equal
        if k not in ("students", "setup", "checked_setup", "checks"): assert m1[k] == m0[k], k
    assert meta1["published_at"] == meta0["published_at"] and meta1["students_at"] and meta1["files_behind"] is True
    assert m0["students"] is not m1["students"] and pub_student("S001") not in m0["students"]   # the old model was not changed in place
    assert j["students"]["outcome"]["updated"] == ["S001"] and j["students"]["outcome"]["text"] == "Published timetable updated for Aisha Rahman (S001)."

@t
def it_equals_a_full_publish_of_the_same_setup():
    fresh(); change(["merge", "students", row_id("S001"), "groups", ["GA2"], ["GA1"]], ["set", "students", row_id("S002"), "name", "Ben K"])
    got = sorted(store.published()["model"]["students"], key=lambda s: s["id"]); publish()
    assert got == sorted(store.published()["model"]["students"], key=lambda s: s["id"])

@t
def a_new_student_is_added_and_their_code_signs_in():
    fresh(); change(["add", "students", dict(_id="newrow0001", id="S004", name="Devi Nair", **{"class": CB}, groups=["GA1"]), ""])
    assert pub_student("S004") == dict(id="S004", name="Devi Nair", cls=CB, level="", groups=["GA1"])
    assert access.norm(access.personal_code("S004")) in store.published()["codes"]

@t
def one_deleted_student_is_removed_and_their_code_stops():
    fresh(); change(["del", "students", row_id("S003")])
    assert pub_student("S003") is None and access.norm(access.personal_code("S003")) not in store.published()["codes"]

@t
def a_save_that_deletes_several_removes_nobody():
    fresh(); j = change(["del", "students", row_id("S002")], ["del", "students", row_id("S003")])
    assert pub_student("S002") and pub_student("S003") and j["students"]["outcome"]["held"] == 2   # the reply key is Task 2's; until then assert on students.follow's return
    assert j["students"]["outcome"]["text"] == "2 students stay on the published timetable until Update the published timetable is pressed."

@t
def a_changed_id_removes_the_old_and_adds_the_new():
    fresh(); change(["set", "students", row_id("S003"), "id", "S033"])
    assert pub_student("S003") is None and pub_student("S033")["name"] == "Chen Li"

@t
def an_id_changed_to_one_already_taken_removes_nobody():
    fresh(); change(["set", "students", row_id("S003"), "id", "S001"])
    assert pub_student("S003")["name"] == "Chen Li" and pub_student("S001")["name"] == "Aisha Rahman"

@t
def each_reason_leaves_the_record_alone():
    for ops, why in ((lambda: [["merge", "students", row_id("S001"), "groups", ["NOPE"], []]], "group NOPE is not on the published timetable"),
                     (lambda: [["set", "students", row_id("S001"), "class", "9Z"]], "class 9Z is not on the published timetable"),
                     (lambda: [["set", "students", row_id("S003"), "id", "S001"], ["set", "students", row_id("S001"), "name", "A R"]], "this ID is on the list twice")):
        fresh(); was = pub_student("S001"); j = change(*ops())
        assert pub_student("S001") == was
        assert [(x["id"], x["why"]) for x in j["students"]["outcome"]["left"]] == [("S001", why)], j

@t
def a_blank_row_is_never_published():
    fresh(); n = len(history.read(kinds=[students.KIND]))
    j = change(["add", "students", dict(_id="blankrow01"), ""]); assert pub_student("None") is None and len(store.published()["model"]["students"]) == 3
    assert j["students"]["outcome"]["left"] == [] and j["students"]["outcome"]["text"] == "" and len(history.read(kinds=[students.KIND])) == n

@t
def a_whole_replacement_updates_nothing():
    fresh(); set_students(PEOPLE[:1]); assert len(store.published()["model"]["students"]) == 3 and "students_at" not in store.published()["meta"]

@t
def the_update_reads_the_setup_as_it_is_now():
    fresh(); pairs = [(dict(_id=row_id("S001"), id="S001", name="Aisha Rahman", **{"class": CA}, groups=["GA1", "GB1"]),
                       dict(_id=row_id("S001"), id="S001", name="Aisha Rahman", **{"class": CA}, groups=["GA2"]))]   # a stale request
    store.apply_changes([["set", "students", row_id("S001"), "name", "Aisha R"]], "t2")                          # a later save, not followed yet
    students.follow(pairs, history.by_of("Tester", "password")); assert pub_student("S001")["name"] == "Aisha R" and "GA1" in pub_student("S001")["groups"]

@t
def a_saved_clash_shows_in_the_checks():
    clash = "1 students have two lessons at the same time, e.g. S001 Aisha Rahman."   # the made-up setup has over 20 other problems, so meta's first 20 do not reach it
    assert clash not in fresh()["model"]["checks"]["problems"]
    change(["merge", "students", row_id("S001"), "groups", ["GX"], []])
    pub = store.published(); assert pub["meta"]["ok"] is False and clash in pub["model"]["checks"]["problems"] and pub["meta"]["problems"] == pub["model"]["checks"]["problems"][:20]

@t
def the_history_entry_is_written_once():
    fresh(); n = len(history.read(kinds=[students.KIND]))
    change(["set", "students", row_id("S002"), "name", "Ben K"])
    got = history.read(kinds=[students.KIND]); assert len(got) == n + 1 and got[0]["text"] == "Published timetable updated for Ben K (S002)." and got[0]["where"] == "Students"

@t
def nothing_published_is_no_error():
    shutil.rmtree(store.PUB, ignore_errors=True); store._cache.update(stamp=None, value=None)
    assert students.follow([(None, dict(id="S009", name="X Y"))], history.by_of("Tester", "password")) is None

@t
def told_names_the_student_rows():
    fresh(); told = {}; store.apply_changes([["set", "students", row_id("S002"), "name", "Ben K"], ["set", "classes", SPEC["classes"][0]["_id"], "size", 31]], "t", told=told)
    assert told["batch"].startswith("b") and [(b["name"], a["name"]) for b, a in told["students"]] == [("Ben Koh", "Ben K")]

@t
def the_route_follows_and_says_what_happened():
    fresh(); j = change(["merge", "students", row_id("S001"), "groups", ["GA2"], ["GA1"]])
    assert j["students"]["outcome"]["updated"] == ["S001"] and j["students"]["outcome"]["text"] == "Published timetable updated for Aisha Rahman (S001)."

@t
def a_save_of_other_rows_says_nothing_about_students():
    fresh(); assert "students" not in change(["set", "classes", SPEC["classes"][0]["_id"], "size", 33])

@t
def a_failure_does_not_fail_the_save():
    fresh(); real, err = students.follow, sys.stderr; students.follow = lambda *a, **k: 1 / 0; sys.stderr = io.StringIO()
    try: j = change(["set", "students", row_id("S002"), "name", "Ben K"]); said = sys.stderr.getvalue()
    finally: students.follow = real; sys.stderr = err
    assert said == "students.follow failed: ZeroDivisionError\n"
    assert j["students"] == {"error": "The published timetable was not updated. Press Update the published timetable on the Students step."}
    assert next(s for s in c.get("/api/setup").get_json()["spec"]["students"] if s["id"] == "S002")["name"] == "Ben K"

@t
def history_has_its_own_line_and_put_back_follows():
    fresh(); n0 = len(history.read(kinds=[students.KIND], limit=10 ** 6)); change(["merge", "students", row_id("S001"), "groups", ["GA2"], ["GA1"]])
    es = history.read(limit=20); line = next(e for e in es if e["kind"] == students.KIND); setup = next(e for e in es if e["kind"] == "setup")
    assert line["text"] == "Published timetable updated for Aisha Rahman (S001)." and line["of"] == setup["batch"] and line["where"] == "Students"
    assert putback.unit_of(line) is None                                    # it cannot be put back
    shown = [e for e in c.get("/api/history?where=Students").get_json()["entries"] if e["kind"] == students.KIND]   # the page's own list: found by Where, no Put back
    assert shown and shown[0]["id"] == line["id"] and "back" not in shown[0]
    assert c.post("/api/history/back", json=dict(id=setup["id"])).get_json() == {"done": True, "text": "Put back."}
    assert sorted(pub_student("S001")["groups"]) == ["GA1", "GB1"]            # the published timetable followed the put back
    assert len(history.read(kinds=[students.KIND], limit=10 ** 6)) == n0 + 2   # the save's line and the put back's
    assert all(e["kind"] != students.KIND for e in putback.gather(setup["id"])[1])   # not part of the save's unit

@t
def the_status_when_all_agree():
    fresh(); s = students.status()
    assert (s["published"], s["students"], s["listed"], s["same"], s["differ"], s["can_update"]) == (True, 3, 3, 3, [], False)

@t
def the_status_names_each_kind():
    fresh(); set_students([PEOPLE[0] | dict(groups=["GA2"]), PEOPLE[1] | dict(groups=["NOPE"]), dict(id="S004", name="Devi Nair", **{"class": CB}, groups=[])])
    s = students.status()
    assert [(d["id"], d["kind"], d["why"]) for d in s["differ"]] == [("S002", "left", "group NOPE is not on the published timetable"), ("S001", "waiting", "not updated yet"),
                                                                    ("S004", "waiting", "not updated yet"), ("S003", "extra", "on the published timetable but not on this list")]
    assert s["counts"] == dict(change=1, add=1, remove=1) and s["can_update"] is True and s["same"] == 0

@t
def update_all_brings_the_list_into_step():
    fresh(); set_students([PEOPLE[0] | dict(groups=["GA2"]), PEOPLE[1] | dict(groups=["NOPE"]), dict(id="S004", name="Devi Nair", **{"class": CB}, groups=[])])
    r = c.post("/api/students/update").get_json()
    assert r["outcome"]["text"] == "Published timetable brought into step with the list: 1 changed, 1 added, 1 removed."
    assert pub_student("S001")["groups"] == ["GA2"] and pub_student("S004") and pub_student("S003") is None and pub_student("S002")["groups"] == ["GA2"]   # S002 left as published
    assert r["status"]["counts"] == dict(change=0, add=0, remove=0) and [d["kind"] for d in r["status"]["differ"]] == ["left"]
    n = len(history.read(limit=50)); c.post("/api/students/update"); assert len(history.read(limit=50)) == n   # nothing to do: nothing written

@t
def the_routes_are_the_committees():
    for url, post in (("/api/students/published", False), ("/api/students/update", True)):
        r = (NOSE.post if post else NOSE.get)(url); assert r.status_code == 401, url
    # a head, a teacher and a student are refused: tests/test_routes.py's walk covers them once GUARDS lists the endpoints

@t
def with_nothing_published():
    shutil.rmtree(store.PUB, ignore_errors=True); store._cache.update(stamp=None, value=None)
    assert students.status() == dict(published=False) and c.post("/api/students/update").status_code == 409

@t
def blank_rows_are_ignored_by_status_and_update_all():
    fresh(); set_students(PEOPLE + [dict(_id="blankrow02")])
    s = students.status(); assert s["listed"] == 3 and s["differ"] == [] and not s["can_update"]
    assert c.post("/api/students/update").get_json()["outcome"]["text"] == "" and len(store.published()["model"]["students"]) == 3

@t
def a_row_with_no_class_says_so():
    fresh(); set_students([PEOPLE[0] | {"class": ""}] + PEOPLE[1:])
    assert [(d["id"], d["kind"], d["why"]) for d in students.status()["differ"]] == [("S001", "left", "no class")]

@t
def the_route_reply_carries_the_status():
    fresh(); j = change(["merge", "students", row_id("S001"), "groups", ["GA2"], ["GA1"]])
    assert j["students"]["status"]["published"] is True and j["students"]["status"]["files_behind"] is True and j["students"]["status"]["can_update"] is False

@t
def two_students_updated_or_left_in_one_save():
    fresh(); j = change(["set", "students", row_id("S001"), "name", "Aisha R"], ["set", "students", row_id("S002"), "name", "Ben K"])
    assert j["students"]["outcome"]["text"] == "Published timetable updated for 2 students."
    fresh(); j = change(["merge", "students", row_id("S001"), "groups", ["NOPE"], []], ["merge", "students", row_id("S002"), "groups", ["NOPE2"], []])
    assert j["students"]["outcome"]["text"] == "Published timetable not changed for 2 students: their groups or classes are not on it."

@t
def a_failing_status_does_not_hide_the_update():
    fresh(); real, err = students.status, sys.stderr
    def boom(): raise KeyError("x")
    students.status = boom; sys.stderr = io.StringIO()
    try: j = change(["merge", "students", row_id("S001"), "groups", ["GA2"], ["GA1"]]); said = sys.stderr.getvalue()
    finally: students.status = real; sys.stderr = err
    assert said == "students.status failed: KeyError\n" and list(j["students"]) == ["outcome"] and j["students"]["outcome"]["updated"] == ["S001"]
    assert sorted(pub_student("S001")["groups"]) == ["GA2", "GB1"]

@t
def no_setup_is_not_an_empty_list():
    fresh(); real = store.setup_record
    store.setup_record = lambda *a, **k: dict(v=1, spec=None)
    try:
        n0 = len(history.read(kinds=[students.KIND], limit=10 ** 6))
        s = students.status(); r = c.post("/api/students/update").get_json(); n = len(history.read(kinds=[students.KIND], limit=10 ** 6))
    finally: store.setup_record = real
    assert n == n0, (n0, n)
    assert (s["published"], s["listed"], s["same"], s["differ"], s["differ_n"], s["counts"], s["can_update"], s["no_setup"]) == (True, 0, 0, [], 0, dict(change=0, add=0, remove=0), False, True)
    assert r["outcome"]["text"] == "" and len(store.published()["model"]["students"]) == 3

@t
def an_empty_list_removes_everybody():
    fresh(); set_students([]); assert students.status()["counts"]["remove"] == 3
    c.post("/api/students/update"); assert store.published()["model"]["students"] == []

@t
def a_repeated_id_is_left_once():
    fresh(); set_students(PEOPLE + [PEOPLE[0] | dict(name="Aisha Two")])
    s = students.status(); assert [(d["id"], d["kind"], d["why"]) for d in s["differ"]] == [("S001", "left", "this ID is on the list twice")]
    c.post("/api/students/update"); assert pub_student("S001")["name"] == "Aisha Rahman" and len(store.published()["model"]["students"]) == 3

@t
def the_files_are_remade_and_carry_the_change():
    fresh(); students.FILES_WAIT = 3600; change(["set", "students", row_id("S002"), "name", "Ben K"])
    meta = store.published()["meta"]; assert meta["files_behind"] is True and c.get("/api/status").get_json()["published"]["files_behind"] is True
    old = os.path.getmtime(os.path.join(store.PUB, meta["files"]["excel"])); time.sleep(1.1)
    assert students.files_now() is True
    meta2 = store.published()["meta"]
    assert meta2["files_behind"] is False and meta2["files_at"] and meta2["published_at"] == meta["published_at"]
    assert c.get("/api/status").get_json()["published"]["files_behind"] is False
    assert os.path.getmtime(os.path.join(store.PUB, meta2["files"]["excel"])) > old and pub_student("S002")["name"] == "Ben K"
    wb = openpyxl.load_workbook(os.path.join(store.PUB, meta2["files"]["excel"]), read_only=True)
    assert any("Ben K" in str(v) for row in wb["Students"].iter_rows(values_only=True) for v in row if v)
    for f in ("setup.xlsx", "model.pkl", "meta.json"): assert os.path.exists(os.path.join(store.PUB, f)), f
    assert not os.path.isdir(os.path.join(store.PUB, "PDF", "Students"))

@t
def a_change_during_the_remake_is_kept():
    fresh(); students.FILES_WAIT = 3600; change(["set", "students", row_id("S002"), "name", "Ben K"])
    from ttgen import export as E; real = E.export_all
    def slow(m, out, **kw):                      # a student change lands while the files are being written
        r = real(m, out, **kw); change(["set", "students", row_id("S003"), "name", "Chen L"]); return r
    store.export_all = slow                      # patch the name store.remake_files calls
    try: assert students.files_now() is False
    finally: store.export_all = real
    assert pub_student("S003")["name"] == "Chen L" and store.published()["meta"]["files_behind"] is True
    assert students.files_now() is True and store.published()["meta"]["files_behind"] is False

@t
def a_publish_during_the_remake_wins():
    fresh(); students.FILES_WAIT = 3600; change(["set", "students", row_id("S002"), "name", "Ben K"])
    from ttgen import export as E; real = E.export_all; seen = {}
    def slow(m, out, **kw):
        r = real(m, out, **kw)
        if not seen:
            seen["x"] = 1; set_students([dict(PEOPLE[2], name="Chen New")])   # the publish carries a name the remake's model does not
            store.export_all = real; publish(); store.export_all = slow; seen["turns"] = dict(store._turns)
        return r
    store.export_all = slow
    try: assert students.files_now() is True
    finally: store.export_all = real
    meta = store.published()["meta"]
    assert "files_at" not in meta and "files_behind" not in meta and "students_at" not in meta   # the publish's own meta.json stands
    assert pub_student("S003")["name"] == "Chen New" and pub_student("S002") is None and store._turns == seen["turns"]

@t
def a_failed_remake_leaves_the_files_behind():
    fresh(); students.FILES_WAIT = 3600; change(["set", "students", row_id("S002"), "name", "Ben K"])
    before = sorted(os.listdir(store.PUB)); real = store.export_all
    def boom(m, out, **kw): raise KeyError("x")
    store.export_all = boom
    try: raises(KeyError, students.files_now)
    finally: store.export_all = real
    assert store.published()["meta"]["files_behind"] is True and sorted(os.listdir(store.PUB)) == before
    assert [d for d in os.listdir(os.path.dirname(store.PUB)) if d.startswith("published.")] == []

@t
def a_reader_never_sees_the_folder_mid_swap():
    fresh(); students.FILES_WAIT = 3600; change(["set", "students", row_id("S002"), "name", "Ben K"])
    import threading
    real = os.replace; between, done, got = threading.Event(), threading.Event(), {}
    def reader():
        between.wait(5)
        try: got["v"] = store.published()
        except Exception as e: got["e"] = e
        done.set()
    def rename(a, b):
        real(a, b)
        if a == store.PUB and not between.is_set():   # the published folder has just moved aside
            between.set(); done.wait(0.5)             # the reader blocks on _lock, so it is not done yet
    th = threading.Thread(target=reader, daemon=True); th.start()
    os.replace = rename
    try: assert students.files_now() is True
    finally: os.replace = real
    th.join(5)
    assert between.is_set() and done.is_set() and "e" not in got, got
    assert got["v"] is not None and pub_student("S002")["name"] == "Ben K" and got["v"]["meta"]["published_at"]

@t
def the_thread_runs_after_the_wait_and_after_a_restart():
    fresh(); students.FILES_WAIT = 0
    try:
        change(["set", "students", row_id("S002"), "name", "Ben K"])
        deadline = time.time() + 60
        while store.published()["meta"].get("files_behind") and time.time() < deadline: time.sleep(0.2)
        assert store.published()["meta"]["files_behind"] is False
        with store._publishing: store.swap_model(store.published()["model"], files_behind=True)   # as a restart finds it
        students.resume_files(); deadline = time.time() + 60
        while store.published()["meta"].get("files_behind") and time.time() < deadline: time.sleep(0.2)
        assert store.published()["meta"]["files_behind"] is False
    finally: students.FILES_WAIT = 3600

@t
def the_skeleton_holds_what_the_screen_needs():
    fresh(); k = c.get("/api/students/skeleton").get_json(); m = store.published()["model"]
    assert k["stamp"] == students.stamp(store.published()) and k["stamp"].startswith(store.published()["meta"]["published_at"] + "|")
    assert k["days"] == m["days"] and k["NP"] == m["NP"] and k["times"] == m["times"]
    d1, d2 = m["days"].index(DAYS[1]), m["days"].index(DAYS[2])
    assert k["groups"]["GA1"] == dict(subject=SUBJ, short=E.abbrev(SUBJ), band="Band A", classes=sorted([CA, CB]), teachers=[T1], rooms=[R1], seats=k["groups"]["GA1"]["seats"], slots=[[d1, L1, 2]])
    assert k["groups"]["GB1"]["slots"] == [[d2, L1, 1]] and k["groups"]["GX"]["band"] == ""
    assert k["classes"][CA]["whole"] == [[m["days"].index(DAYS[0]), L1, 1, E.abbrev(SUBJ), R1]] and k["classes"][CB]["whole"] == []
    assert len(k["classes"][CA]["codes"]) == len(m["days"])
    assert NOSE.get("/api/students/skeleton").status_code == 401

@t
def the_skeleton_has_no_student_in_it():
    fresh(); raw = c.get("/api/students/skeleton").get_data(as_text=True)
    assert "Aisha" not in raw and "S001" not in raw

@t
def the_skeleton_is_gzipped_when_asked_and_404_when_nothing_is_published():
    fresh(); r = c.get("/api/students/skeleton", headers={"Accept-Encoding": "gzip"})
    assert r.headers.get("Content-Encoding") == "gzip"
    import gzip
    assert json.loads(gzip.decompress(r.get_data()))["stamp"] == students.stamp(store.published())

def _swap(**over):
    """the published model replaced by a shallow copy with the given keys changed (the cached model is never changed)"""
    m = dict(store.published()["model"]); m.update(over)
    with store._publishing: store.swap_model(m)

def _lessons_with(code, **kw):
    out = []
    for L in store.published()["model"]["lessons"]:
        out.append(dict(L, **kw) if L["group"] == code else L)
    return out

@t
def a_changed_lesson_changes_the_stamp():
    for kw in (dict(room=R2), dict(p=L1 + 1)):
        fresh(); before = students.stamp(store.published()); at = store.published()["meta"]["published_at"]
        _swap(lessons=_lessons_with("GA1", **kw))
        after = students.stamp(store.published())
        assert after != before and after.startswith(at + "|") and before.startswith(at + "|"), kw

@t
def seats_read_a_whole_number_in_any_form():
    def seats(caps, lessons=None):
        fresh(); m = store.published()["model"]
        rooms = [dict(r, capacity=caps[r["name"]]) if r["name"] in caps else r for r in m["rooms"]]
        _swap(rooms=rooms, **(dict(lessons=lessons(m)) if lessons else {}))
        return c.get("/api/students/skeleton").get_json()["groups"]
    for cap, want in ((12, 12), (12.0, 12), ("12", 12), ("12.0", 12), (12.5, None), (0, None), ("", None), (None, None), ("abc", None)):
        assert seats({R1: cap})["GA1"]["seats"] == want, cap
    assert seats({R1: 20, R2: 30}, lambda m: [dict(L, room=R2) if L["group"] == "GA1" and L is [x for x in m["lessons"] if x["group"] == "GA1"][0] else L for L in m["lessons"]])["GA1"]["seats"] == 30
    two = lambda m: m["lessons"] + [dict([x for x in m["lessons"] if x["group"] == "GA1"][0], id=99, d=0, room=R2)]
    assert seats({R1: 20, R2: 30}, two)["GA1"]["seats"] is None

@t
def the_stamp_ignores_a_student_change_and_status_carries_it():
    fresh(); before = c.get("/api/students/skeleton").get_json()["stamp"]
    change(["merge", "students", row_id("S002"), "groups", ["GA1"], ["GA2"]])
    k = c.get("/api/students/skeleton").get_json()
    assert k["stamp"] == before == students.status()["stamp"]
    assert students.status()["at"] == store.published()["meta"]["published_at"]

@t
def a_made_exam_goes_stale_after_a_group_change():
    from exams import make as XM, papers as XP
    fresh(); sched = dict(papers=[dict(id="p1", who="groups", level=LEVEL, subject=SUBJ)]); xset = {}
    at = XM.published_at(store.published())
    fp1, sit1 = XM.fingerprint(sched, xset, store.published()["model"]), XP.who_sits(sched["papers"][0], store.published()["model"])
    change(["merge", "students", row_id("S002"), "groups", ["GA1"], ["GA2"]])
    fp2, sit2 = XM.fingerprint(sched, xset, store.published()["model"]), XP.who_sits(sched["papers"][0], store.published()["model"])
    assert "S002" not in sit1 and "S002" in sit2 and fp1 != fp2
    assert XM.published_at(store.published()) == at

# ------------------------------------------------------------------------------------------------ the fix wave after the review
CHANGED = "The list or the published timetable changed. Check the numbers and press Update again."

def kind_lines(): return len(history.read(kinds=[students.KIND], limit=10 ** 6))

@t
def update_refuses_when_the_counts_it_was_asked_for_have_changed():
    fresh(); set_students([PEOPLE[0] | dict(groups=["GA2"])] + PEOPLE[1:])   # the page saw: 1 changes
    set_students([PEOPLE[0] | dict(groups=["GA2"])])                          # another member's save meanwhile: 2 more to remove
    was, n = copy.deepcopy(store.published()["model"]["students"]), kind_lines()
    r = c.post("/api/students/update", json=dict(expect=dict(change=1, add=0, remove=0)))
    assert r.status_code == 409 and r.get_json()["error"] == CHANGED, r.get_json()
    assert r.get_json()["status"]["counts"] == dict(change=1, add=0, remove=2)
    assert store.published()["model"]["students"] == was and kind_lines() == n and "students_at" not in store.published()["meta"]
    r = c.post("/api/students/update", json=dict(expect=dict(change=1, add=0, remove=2)))   # the counts agree: as before
    assert r.status_code == 200 and r.get_json()["outcome"]["text"] == "Published timetable brought into step with the list: 1 changed, 0 added, 2 removed."
    assert [s["id"] for s in store.published()["model"]["students"]] == ["S001"] and kind_lines() == n + 1

@t
def update_with_no_expect_is_as_before_and_a_bad_expect_is_refused():
    fresh(); set_students([PEOPLE[0] | dict(groups=["GA2"])] + PEOPLE[1:])
    for body in (dict(expect=None), dict(expect=dict(change=1, add=0)), dict(expect=dict(change="1", add=0, remove=0)), dict(expect=[1, 0, 0]), dict(expect=dict(change=True, add=0, remove=0))):
        r = c.post("/api/students/update", json=body)
        assert r.status_code == 400 and r.get_json() == {"error": "Check the numbers and press Update again."}, body
    assert pub_student("S001")["groups"] == ["GA1", "GB1"]
    r = c.post("/api/students/update", json=dict())   # an old page: no expect at all
    assert r.status_code == 200 and pub_student("S001")["groups"] == ["GA2"]

@t
def update_all_changes_only_the_students():
    fresh(); m0 = store.published()["model"]; at = store.published()["meta"]["published_at"]
    set_students([PEOPLE[0] | dict(groups=["GA2"]), PEOPLE[1], dict(id="S004", name="Devi Nair", **{"class": CB}, groups=[])])
    c.post("/api/students/update"); m1 = store.published()["model"]
    for k in m0:
        if k not in ("students", "setup", "checked_setup", "checks"): assert m1[k] == m0[k], k
    assert store.published()["meta"]["published_at"] == at and [s["id"] for s in m1["students"]] == ["S001", "S002", "S004"]

def upload_draft():
    spec = store.setup_record()["spec"]
    r = c.post("/api/draft", data=dict(setup=(io.BytesIO(setup_bytes(spec)), "setup.xlsx"), timetable=(io.BytesIO(workbook(ROWS)), "timetable.xlsx"), replace="1"), content_type="multipart/form-data")
    assert r.status_code == 200, r.get_data(as_text=True)

@t
def a_publish_does_not_undo_a_student_save_made_while_it_was_checked():
    import draft
    fresh(); upload_draft(); n = kind_lines()
    real_pub, real_info = store.publish, draft.info
    def late(*a, **k):                     # the setup was read and the draft checked: a student save lands and follows
        change(["merge", "students", row_id("S001"), "groups", ["GA2"], ["GA1"]]); return real_pub(*a, **k)
    store.publish, draft.info = late, (lambda **k: dict(real_info(**k), critical=0))   # the made-up setup has critical mistakes of its own
    try: draft.publish()
    finally: store.publish, draft.info = real_pub, real_info
    pub = store.published()
    assert sorted(pub_student("S001")["groups"]) == ["GA2", "GB1"] and pub["meta"]["students"] == 3 and pub["meta"]["files_behind"] is True
    assert pub["meta"]["problems"] == pub["model"]["checks"]["problems"][:20] and students.status()["can_update"] is False
    got = history.read(kinds=[students.KIND], limit=10 ** 6); assert len(got) == n + 2   # the save's line and the publish's
    assert got[0]["text"] == "Published timetable updated for Aisha Rahman (S001)." and got[0]["as"] == "The app" and got[0]["via"] == "app"

@t
def catch_up_removes_nobody_and_writes_nothing_when_all_agree():
    fresh(); set_students(PEOPLE[:2]); n = kind_lines(); mt = os.path.getmtime(os.path.join(store.PUB, "model.pkl"))
    got = students.catch_up()
    assert got["text"] == "" and pub_student("S003") and kind_lines() == n
    assert os.path.getmtime(os.path.join(store.PUB, "model.pkl")) == mt and "students_at" not in store.published()["meta"] and "files_behind" not in store.published()["meta"]

@t
def a_failing_catch_up_does_not_fail_the_publish():
    import draft
    fresh(); upload_draft(); real_cu, real_info, err = students.catch_up, draft.info, sys.stderr
    students.catch_up, draft.info, sys.stderr = (lambda *a, **k: 1 / 0), (lambda **k: dict(real_info(**k), critical=0)), io.StringIO()
    try: j = draft.publish(); said = sys.stderr.getvalue()
    finally: students.catch_up, draft.info, sys.stderr = real_cu, real_info, err
    assert j["published"] is True and said == "students.catch_up failed: ZeroDivisionError\n", said

@t
def a_paste_of_listed_students_holds_nobody():
    fresh(); ops = [["del", "students", row_id(p["id"])] for p in PEOPLE] + [["add", "students", dict(copy.deepcopy(p), _id=f"paste{i:05d}"), ""] for i, p in enumerate(PEOPLE)]
    o = change(*ops)["students"]["outcome"]
    assert o["held"] == 0 and "stay" not in o["text"], o

@t
def a_replace_keeping_one_of_three_holds_two():
    fresh(); ops = [["del", "students", row_id(p["id"])] for p in PEOPLE] + [["add", "students", dict(copy.deepcopy(PEOPLE[0]), _id="paste00001"), ""]]
    o = change(*ops)["students"]["outcome"]
    assert o["held"] == 2 and o["text"] == "2 students stay on the published timetable until Update the published timetable is pressed.", o
    assert pub_student("S002") and pub_student("S003")

@t
def one_held_student_is_said_in_the_singular():
    fresh(); ops = [["del", "students", row_id(p["id"])] for p in PEOPLE] + [["add", "students", dict(copy.deepcopy(p), _id=f"paste{i:05d}"), ""] for i, p in enumerate(PEOPLE[:2])]
    o = change(*ops)["students"]["outcome"]
    assert o["held"] == 1 and o["text"] == "1 student stays on the published timetable until Update the published timetable is pressed.", o

@t
def an_unreadable_meta_is_never_overwritten():
    for bad in ("{ not json", "[1, 2]"):
        fresh(); mp, kp = os.path.join(store.PUB, "meta.json"), os.path.join(store.PUB, "model.pkl")
        model = dict(store.published()["model"], students=[])
        with open(mp, "w") as f: f.write(bad)
        kb = open(kp, "rb").read()
        with store._publishing: raises(ValueError, lambda: store.swap_model(model, students=0), "The published meta.json could not be read.")
        assert open(mp).read() == bad and open(kp, "rb").read() == kb
        raises(ValueError, store.remake_files, "The published meta.json could not be read.")
        assert open(mp).read() == bad and [d for d in os.listdir(os.path.dirname(store.PUB)) if d.startswith("published.")] == []
    fresh(); mp = os.path.join(store.PUB, "meta.json"); meta = store.read_json(mp); meta.pop("published_at"); store.write_json(mp, meta)
    raises(ValueError, store.remake_files, "The published meta.json could not be read.")
    assert [d for d in os.listdir(os.path.dirname(store.PUB)) if d.startswith("published.")] == []
    fresh(); os.remove(os.path.join(store.PUB, "meta.json"))
    with store._publishing: raises(FileNotFoundError, lambda: store.swap_model({}, students=0))

@t
def a_failed_meta_write_still_drops_the_cache():
    fresh(); model = dict(store.published()["model"], students=[]); real = store.write_json
    def boom(path, obj): raise OSError("disk full")
    store.write_json = boom
    try:
        with store._publishing: raises(OSError, lambda: store.swap_model(model, students=0))
    finally: store.write_json = real
    assert store.published()["model"]["students"] == []   # the model on disk is what readers see

@t
def a_put_back_whose_follow_fails_says_so():
    fresh(); change(["set", "students", row_id("S002"), "name", "Ben K"])
    setup = next(e for e in history.read(limit=20) if e["kind"] == "setup")
    real, err = students.follow, sys.stderr; students.follow = lambda *a, **k: 1 / 0; sys.stderr = io.StringIO()
    try: r = c.post("/api/history/back", json=dict(id=setup["id"])); said = sys.stderr.getvalue()
    finally: students.follow = real; sys.stderr = err
    assert r.status_code == 200 and r.get_json() == {"done": True, "text": "Put back. The published timetable was not updated: press Update the published timetable on the Students step."}
    assert said == "students.follow failed: ZeroDivisionError\n" and next(s for s in store.setup_record()["spec"]["students"] if s["id"] == "S002")["name"] == "Ben Koh"
    assert pub_student("S002")["name"] == "Ben K"

@t
def status_waits_for_no_publish():
    import threading
    fresh(); got = {}
    th = threading.Thread(target=lambda: got.update(s=students.status()), daemon=True)
    with store._publishing:
        th.start(); th.join(5)
    assert got.get("s", {}).get("published") is True

@t
def the_files_thread_does_nothing_when_the_files_are_fresh():
    fresh(); real, calls = store.remake_files, []
    store.remake_files = lambda: calls.append(1) or True
    students.FILES_WAIT = 0
    try:
        students._files.update(pending=True, running=True); students._files_run()          # a publish made fresh files meanwhile
        assert calls == [] and students._files["running"] is False
        with store._publishing: store.swap_model(store.published()["model"], files_behind=True)
        students._files.update(pending=True, running=True); students._files_run()
        assert calls == [1]
    finally: store.remake_files = real; students.FILES_WAIT = 3600

@t
def a_new_students_code_signs_in_and_a_removed_ones_does_not():
    fresh(); change(["add", "students", dict(_id="newrow0002", id="S004", name="Devi Nair", **{"class": CB}, groups=["GA1"]), ""])
    s = A.app.test_client(); r = s.post("/login", data=dict(code=access.personal_code("S004")))
    assert r.status_code == 302 and r.headers["Location"].endswith("/me") and s.get("/me").status_code == 200
    change(["del", "students", row_id("S004")])
    s2 = A.app.test_client(); r = s2.post("/login", data=dict(code=access.personal_code("S004")))
    assert r.status_code != 302 and s2.get("/me").status_code != 200

@t
def a_heads_save_of_students_is_refused_and_follows_nothing():
    fresh(); h = A.app.test_client()
    with h.session_transaction() as s: s.update(role="head")
    was, n = copy.deepcopy(store.published()["model"]["students"]), kind_lines()
    r = h.post("/api/setup/changes", json=dict(client="h", since=store.setup_record()["v"], ops=[["merge", "students", row_id("S001"), "groups", ["GA2"], ["GA1"]], ["del", "students", row_id("S003")]]))
    j = r.get_json(); assert r.status_code == 200 and len(j.get("refused") or []) == 2 and "students" not in j, j
    assert store.published()["model"]["students"] == was and kind_lines() == n

@t
def a_renumbered_row_onto_an_equal_published_record_removes_the_old_id():
    fresh(); change(["add", "students", dict(_id="dup0000001", id="S009", name="Chen Li", **{"class": CA}, groups=[]), ""])
    set_students(PEOPLE)                                                    # S009 stays published, off the list
    change(["set", "students", row_id("S003"), "id", "S009"])
    assert pub_student("S003") is None and pub_student("S009")["name"] == "Chen Li"
    assert access.norm(access.personal_code("S003")) not in store.published()["codes"]

@t
def seats_of_an_endless_or_odd_capacity_are_none():
    for cap in ("inf", "1e400", "nan", float("inf"), float("nan"), "-inf"):
        fresh(); m = store.published()["model"]
        _swap(rooms=[dict(r, capacity=cap) if r["name"] == R1 else r for r in m["rooms"]])
        assert c.get("/api/students/skeleton").get_json()["groups"]["GA1"]["seats"] is None, cap

@t
def the_people_stamp_moves_with_the_students_only():
    fresh(); a = students.people_stamp(store.published())
    assert a and a == students.people_stamp(store.published()) and students.people_stamp(None) == ""
    change(["set", "students", row_id("S002"), "name", "Ben K"]); b = students.people_stamp(store.published())
    change(["merge", "students", row_id("S002"), "groups", ["GA1"], ["GA2"]]); d = students.people_stamp(store.published())
    assert len({a, b, d}) == 3
    _swap(lessons=_lessons_with("GA1", room=R2)); assert students.people_stamp(store.published()) == d

if __name__ == "__main__":
    for f in TESTS: f()
    print(f"{len(TESTS)} checks passed")

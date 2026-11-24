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
    """a save as the route will make it (Task 2): the change applied, then the students it named followed"""
    told = {}
    store.apply_changes(list(ops), "t", told=told, by=BY)
    return {"students": {"outcome": students.follow(told.get("students") or [], BY, told.get("batch"))}}

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

if __name__ == "__main__":
    for f in TESTS: f()
    print(f"{len(TESTS)} checks passed")

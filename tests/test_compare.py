"""Plain-assert tests for comparing two timetables: .venv/bin/python tests/test_compare.py"""
import gzip, io, json, os, secrets, shutil, sys, tempfile, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = tempfile.mkdtemp()
CODE = secrets.token_hex(4)
os.environ.pop("HEADS_CODE", None)
os.environ.update(DATA_DIR=DATA, SECRET_KEY=secrets.token_hex(16), AI_PROVIDER="anthropic", AI_API_KEY="", COMMITTEE_CODE=CODE, TEACHER_CODE=secrets.token_hex(4), STUDENT_CODE=secrets.token_hex(4))
sys.path.insert(0, ROOT)
import openpyxl  # noqa: E402
import app as A, compare, draft, store, versions  # noqa: E402
from ttgen.template import write_template  # noqa: E402

c = A.app.test_client()
assert c.post("/login", data={"as": "committee", "code": CODE}).status_code == 302
NOSE = A.app.test_client()   # never signed in
NOT_FOUND = "There is no lesson with that id on the timetable."

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

def save_draft(rows):
    r = c.post("/api/draft", data=dict(setup=(io.BytesIO(setup_bytes(SPEC)), "setup.xlsx"), timetable=(io.BytesIO(workbook(rows)), "timetable.xlsx"), replace="1"), content_type="multipart/form-data")
    assert r.status_code == 200, r.get_json()

assert c.put("/api/setup", json=A.sample("primary")).status_code == 200
SPEC = c.get("/api/setup").get_json()["spec"]
LEVEL = SPEC["classes"][0]["level"]
CLASSES = [x["class"] for x in SPEC["classes"] if x["level"] == LEVEL][:2]; assert len(CLASSES) == 2
DAYS = list(SPEC["day_structure"][LEVEL].keys()); NPD = len(next(iter(SPEC["day_structure"][LEVEL].values())))
TEACHERS = [x["name"] for x in SPEC["teachers"]][:3]
SUBJ = SPEC["subjects"][0]["subject"]; SUBJ2 = SPEC["subjects"][1]["subject"]
PLAIN_ID, OTHER_ID, BAND_ID, ODD_ID = 1, 2, 3, 4
BAND_CLASSES = set(CLASSES)
ROWS = [
    dict(id=PLAIN_ID, day=DAYS[0], p=0, n=1, level=LEVEL, classes=[CLASSES[0]], subject=SUBJ, teachers=[TEACHERS[0]]),
    dict(id=OTHER_ID, day=DAYS[1], p=1, n=1, level=LEVEL, classes=[CLASSES[0]], subject=SUBJ2),
    dict(id=BAND_ID, day=DAYS[2], p=0, n=2, level=LEVEL, block=f"{LEVEL} Band A", classes=CLASSES, subject=SUBJ, group="G1", teachers=[TEACHERS[1]]),
    dict(id=BAND_ID, day=DAYS[2], p=0, n=2, level=LEVEL, block=f"{LEVEL} Band A", classes=[CLASSES[0]], subject=SUBJ2, group="G2", teachers=[TEACHERS[2]]),
    dict(id=BAND_ID, day=DAYS[2], p=0, n=2, level=LEVEL, block=f"{LEVEL} Band A", classes=[CLASSES[1]], subject=SUBJ, group="G3", teachers=["Nobody Known"]),
    dict(id=ODD_ID, day=DAYS[3], p=0, n=1, level=LEVEL, classes=["9Z"], subject=SUBJ, teachers=[TEACHERS[0]]),
]
save_draft(ROWS)

NOW = store.now
def shift(rows, by): return [dict(r, id=r["id"] + 100, **by.get(r["id"], {})) for r in rows]
CLEAN = [dict(ROWS[0], p=2), dict(ROWS[1], p=3, teachers=[TEACHERS[1]])]   # two lessons that break no rule
LAST = DAYS[-1]
EXTRA = dict(id=200, day=LAST, p=3, n=1, level=LEVEL, classes=[CLASSES[1]], subject=SUBJ2, teachers=[TEACHERS[2]])
ROOM = next(iter(SPEC.get("rooms") or [dict(room="Room 1")]))
ROOM = ROOM.get("room") or ROOM.get("name") if isinstance(ROOM, dict) else ROOM
B_ROWS = shift(ROWS, {PLAIN_ID: dict(p=2, room=ROOM), OTHER_ID: dict(teachers=[TEACHERS[1]])}) + [EXTRA]

def two_timetables():
    """A is saved as a version, B is the draft; returns the version's source string"""
    shutil.rmtree(versions.VDIR, ignore_errors=True)
    save_draft(ROWS); v = versions.save("Run A", "Tester"); save_draft(B_ROWS)
    return "v:" + v["id"]

def test_pairs_ignore_ids_and_list_lessons_on_one_side():
    a = two_timetables(); d = compare.diff(a, "draft")
    t = d["totals"]; assert (t["moved"], t["teacher"], t["room"]) == (1, 1, 1), t
    assert t["lessons"] == len({r["id"] for r in compare.rows(compare.model_of("draft", None))}), t
    only_b = [i for i in d["items"] if "only_b" in i["kinds"]]; assert len(only_b) == 1 and only_b[0]["b"]["id"] == 200 and only_b[0]["a"] is None
    assert not [i for i in d["items"] if "only_a" in i["kinds"]]
    assert len(d["items"]) == 3, [compare.line(i, DAYS) for i in d["items"]]   # nothing for the unchanged lessons, bands included
    assert compare.diff("draft", a)["totals"]["lessons"] != 0
    assert compare.diff(a, a)["items"] == [] and compare.diff("draft", "draft")["items"] == []
    assert compare.diff(a, "draft") == compare.diff(a, "draft")   # deterministic
    assert d["names"]["classes"][:2] == CLASSES and d["names"]["teachers"][:3] == TEACHERS

def test_lines_read_as_the_spec_says():
    a = two_timetables(); d = compare.diff(a, "draft"); lines = [compare.line(i, DAYS) for i in d["items"]]
    assert f"{SUBJ}: {DAYS[0]} 0 → {DAYS[0]} 2, room none → {ROOM}" in lines, lines
    assert f"{SUBJ2}: teacher none → {TEACHERS[1]}" in lines, lines
    assert f"{SUBJ2}: only in B ({LAST} 3)" in lines, lines
    one = dict(a=dict(d=4, p=2, teachers=["Karen Ismail"], room="", subject="Social Studies"), b=dict(d=3, p=4, teachers=["Hakim Kumar"], room="", subject="Social Studies"), kinds=["time", "teacher"])
    days = ["Mon", "Tue", "Wed", "Thu", "Fri"]
    assert compare.line(one, days) == "Social Studies: Fri 2 → Thu 4, teacher Karen Ismail → Hakim Kumar"
    assert compare.line(dict(a=dict(d=0, p=3, teachers=[], room="", subject="Mathematics"), b=dict(d=0, p=6, teachers=[], room="", subject="Mathematics"), kinds=["time"]), days) == "Mathematics: Mon 3 → Mon 6"
    assert compare.line(dict(a=dict(d=0, p=3, teachers=[], room="Lab 1", subject="Science"), b=dict(d=0, p=3, teachers=[], room="Lab 2", subject="Science"), kinds=["room"]), days) == "Science: room Lab 1 → Lab 2"
    assert compare.line(dict(a=dict(d=1, p=5, teachers=[], room="", subject="Art"), b=None, kinds=["only_a"]), days) == "Art: only in A (Tue 5)"

def test_pair_matches_same_slot_first():
    r = lambda i, d, p: dict(key="G:X", id=i, d=d, p=p, room="")
    got = compare.pair([r(1, 0, 1), r(2, 0, 4)], [r(9, 0, 4), r(8, 0, 6), r(7, 0, 7)])
    assert [(x and x["p"], y and y["p"]) for x, y in got] == [(4, 4), (1, 6), (None, 7)], got

def test_week_of_a_room():
    two_timetables(); m = compare.model_of("draft", None); before = list(m["lessons"])
    rooms = sorted({x["room"] for x in m["lessons"] if x["room"]}); assert rooms, "the sample has rooms"
    r = rooms[0]; w = compare.week(m, "room", r)
    assert sorted((c["d"], c["p"], c["key"]) for c in w["cells"]) == sorted((x["d"], x["p"], k) for x in m["lessons"] if x["room"] == r for k in [":".join(kk) for kk in __import__("helper")._keys_of(x)])
    assert w["NP"] == m["NP"] and w["days"] == list(m["days"])
    assert compare.week(m, "class", CLASSES[0])["cells"] and compare.week(m, "teacher", TEACHERS[0])["cells"]
    for bad in (("room", "Nowhere"), ("class", "Nobody"), ("teacher", ""), ("thing", "x")): raises(ValueError, lambda: compare.week(m, *bad), "Pick a class, teacher or room on both timetables.")
    assert m["lessons"] == before and compare.model_of("draft", None)["lessons"] == before   # the shared model is untouched

def test_published_compares():
    shutil.rmtree(versions.VDIR, ignore_errors=True); save_draft(CLEAN)
    assert draft.info()["critical"] == 0, [w["text"] for w in draft.info()["warnings"] if w.get("crit")]
    r = c.post("/api/draft/publish"); assert r.status_code == 200, r.get_json()
    assert compare.diff("published", "draft")["items"] == [], [compare.line(i, DAYS) for i in compare.diff("published", "draft")["items"]]
    pc = compare.published_counts(); assert pc["critical"] == 0 and pc["published_at"], pc
    assert c.get("/api/draft/versions").get_json()["published"] == pc
    assert compare.label("published") == "Published timetable" and compare.label("draft") == "The draft on step 8"
    tmp = tempfile.gettempdir(); assert not [f for f in os.listdir(tmp) if f.startswith("tmp") and os.path.exists(os.path.join(tmp, f, "published.sqlite"))]
    save_draft(B_ROWS); assert compare.diff("published", "draft")["items"]   # a changed draft differs from what is published

def test_nothing_published_is_said():
    old = os.environ["DATA_DIR"]; store_pub = store.PUB
    store.PUB = os.path.join(tempfile.mkdtemp(), "none"); store._cache.update(stamp=None, value=None)
    try:
        raises(ValueError, lambda: compare.model_of("published", store.setup_record()), "Nothing is published yet.")
        assert compare.published_counts() is None
    finally: store.PUB = store_pub; store._cache.update(stamp=None, value=None)
    raises(ValueError, lambda: compare.model_of("v:" + "0" * 12, store.setup_record()), "There is no such version.")
    shutil.rmtree(draft.DIR, ignore_errors=True); raises(ValueError, lambda: compare.model_of("draft", store.setup_record()), "There is no draft.")

def test_excel_has_one_row_per_difference():
    a = two_timetables(); d = compare.diff(a, "draft")
    want = sum(len((i["b"] or i["a"])["classes"]) for i in d["items"]); assert want >= 3
    ws = openpyxl.load_workbook(io.BytesIO(compare.xlsx(a, "draft"))).active
    assert ws.title == "Differences" and [x.value for x in ws[1]] == ["Class", "Lesson", "A", "B"]
    assert ws.max_row - 1 == want, (ws.max_row, want)

if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for f in tests: f()
    print(f"{len(tests)} checks passed")

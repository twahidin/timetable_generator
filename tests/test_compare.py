"""Plain-assert tests for comparing two timetables: .venv/bin/python tests/test_compare.py"""
import contextlib, copy, gzip, io, json, os, secrets, shutil, sys, tempfile, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = tempfile.mkdtemp()
CODE = secrets.token_hex(4)
os.environ.pop("HEADS_CODE", None)
os.environ.update(DATA_DIR=DATA, SECRET_KEY=secrets.token_hex(16), AI_PROVIDER="anthropic", AI_API_KEY="", COMMITTEE_CODE=CODE, TEACHER_CODE=secrets.token_hex(4), STUDENT_CODE=secrets.token_hex(4))
sys.path.insert(0, ROOT)
import openpyxl  # noqa: E402
import app as A, compare, draft, store, versions  # noqa: E402
from ttgen.export import ENTIRE  # noqa: E402
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

_made = {}   # the setup workbook is made once: every upload here sends the same one
def setup_bytes(spec):
    if "b" not in _made: p = os.path.join(tempfile.mkdtemp(), "setup.xlsx"); write_template(spec, p); _made["b"] = open(p, "rb").read()
    return _made["b"]

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

@contextlib.contextmanager
def patched(obj, name, value):
    old = getattr(obj, name); setattr(obj, name, value)
    try: yield
    finally: setattr(obj, name, old)

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
    # the other way round, the lesson is only in A: it is listed, in the diff, on the page and in the Excel file
    o = compare.diff("draft", a); only_a = [i for i in o["items"] if "only_a" in i["kinds"]]; said = f"{CLASSES[1]} {SUBJ2}: only in A ({LAST} 3)"
    assert len(only_a) == 1 and only_a[0]["a"]["id"] == 200 and only_a[0]["b"] is None and not [i for i in o["items"] if "only_b" in i["kinds"]] and len(o["items"]) == 3
    assert compare.line(only_a[0], o["days"]) == said
    assert said in c.get(f"/api/compare?a=draft&b={a}&view=class&name={CLASSES[1]}").get_json()["lines"]
    rows = [[x.value for x in r] for r in openpyxl.load_workbook(io.BytesIO(compare.xlsx("draft", a))).active.iter_rows(min_row=2)]
    assert [r for r in rows if r[0] == CLASSES[1] and r[2].startswith(f"{LAST} 3") and not r[3]], rows

def test_the_names_are_of_both_sides():
    """a class, a teacher and a room that only one of the two timetables has can be picked, whichever side it is on"""
    shutil.rmtree(versions.VDIR, ignore_errors=True)
    few = [dict(ROWS[1], teachers=[TEACHERS[1]])]
    save_draft(ROWS[:2] + [dict(id=9, day=DAYS[3], p=0, n=1, level=LEVEL, classes=["9Z"], subject=SUBJ, teachers=["Odd Visitor"], room="Odd Hut")]); v = "v:" + versions.save("With 9Z", "Tester")["id"]; save_draft(few)
    for a, b in ((v, "draft"), ("draft", v)):
        n = compare.diff(a, b)["names"]; assert "9Z" in n["classes"] and "Odd Visitor" in n["teachers"] and "Odd Hut" in n["rooms"], n
        for view, name in (("class", "9Z"), ("teacher", "Odd Visitor"), ("room", "Odd Hut")):
            r = c.get("/api/compare", query_string=dict(a=a, b=b, view=view, name=name)); assert r.status_code == 200, (view, r.get_json())
            assert r.get_json()["lines"] == [f"9Z {SUBJ}: only in {'A' if a == v else 'B'} ({DAYS[3]} 0)"], r.get_json()["lines"]

def test_lines_read_as_the_spec_says():
    a = two_timetables(); d = compare.diff(a, "draft"); lines = [compare.line(i, DAYS) for i in d["items"]]
    assert f"{CLASSES[0]} {SUBJ}: {DAYS[0]} 0 → {DAYS[0]} 2, room none → {ROOM}" in lines, lines
    assert f"{CLASSES[0]} {SUBJ2}: teacher none → {TEACHERS[1]}" in lines, lines
    assert f"{CLASSES[1]} {SUBJ2}: only in B ({LAST} 3)" in lines, lines
    row = lambda subject, d, p, teachers=(), room="", cls="3B", group=ENTIRE: dict(d=d, p=p, teachers=list(teachers), room=room, subject=subject, classes=[cls], group=group)
    days = ["Mon", "Tue", "Wed", "Thu", "Fri"]; say = lambda a, b, *kinds: compare.line(dict(a=a, b=b, kinds=list(kinds)), days)
    assert say(row("Social Studies", 4, 2, ["Karen Ismail"]), row("Social Studies", 3, 4, ["Hakim Kumar"]), "time", "teacher") == "3B Social Studies: Fri 2 → Thu 4, teacher Karen Ismail → Hakim Kumar"
    assert say(row("Mathematics", 0, 3), row("Mathematics", 0, 6), "time") == "3B Mathematics: Mon 3 → Mon 6"
    assert say(row("Science", 0, 3, room="Lab 1"), row("Science", 0, 3, room="Lab 2"), "room") == "3B Science: room Lab 1 → Lab 2"
    assert say(row("Art", 1, 5), None, "only_a") == "3B Art: only in A (Tue 5)" and say(None, row("Science", 3, 7), "only_b") == "3B Science: only in B (Thu 7)"
    assert say(row("Mathematics", 0, 3, group="3MA1"), row("Mathematics", 0, 6, group="3MA1"), "time") == "Mathematics (3MA1): Mon 3 → Mon 6"   # a group is named by its code

def test_lines_tell_two_classes_and_two_groups_apart():
    shutil.rmtree(versions.VDIR, ignore_errors=True); both = dict(id=1, n=1, level=LEVEL, classes=CLASSES, subject=SUBJ, teachers=[TEACHERS[0]])
    band = lambda p: [dict(id=3, day=DAYS[2], p=p, n=1, level=LEVEL, block=f"{LEVEL} Band A", classes=[CLASSES[0]], subject=SUBJ, group=g, teachers=[TEACHERS[i]]) for i, g in ((1, "G1"), (2, "G2"))]
    save_draft([dict(both, day=DAYS[0], p=2)] + band(1)); v = "v:" + versions.save("One", "Tester")["id"]; save_draft([dict(both, day=DAYS[0], p=3)] + band(4))
    j = c.get("/api/compare", query_string=dict(a=v, view="teacher", name=TEACHERS[0])).get_json()
    assert j["lines"] == [f"{x} {SUBJ}: {DAYS[0]} 2 → {DAYS[0]} 3" for x in CLASSES], j["lines"]
    j = c.get("/api/compare", query_string=dict(a=v, view="class", name=CLASSES[0])).get_json()
    assert j["lines"] == [f"{CLASSES[0]} {SUBJ}: {DAYS[0]} 2 → {DAYS[0]} 3"] + [f"{SUBJ} ({g}): {DAYS[2]} 1 → {DAYS[2]} 4" for g in ("G1", "G2")], j["lines"]
    cells = {(x["d"], x["p"], x["group"]) for x in j["weeks"]["a"]["cells"]}; assert cells == {(0, 2, ""), (2, 1, "G1"), (2, 1, "G2")}, cells   # the group code is in the cell too
    with patched(compare, "line", lambda i, days: "the same line"): assert c.get("/api/compare", query_string=dict(a=v)).get_json()["lines"] == ["the same line"]   # said once

def test_pair_matches_same_slot_first():
    r = lambda i, d, p: dict(key="G:X", id=i, d=d, p=p, room="", teachers=[])
    got = compare.pair([r(1, 0, 1), r(2, 0, 4)], [r(9, 0, 4), r(8, 0, 6), r(7, 0, 7)])
    assert [(x and x["p"], y and y["p"]) for x, y in got] == [(4, 4), (1, 6), (None, 7)], got

def test_two_rows_of_one_key_at_one_time_pair_by_teacher():
    r = lambda i, *teachers, room="": dict(key="G:X", id=i, d=0, p=1, n=1, room=room, teachers=list(teachers))
    a, b = [r(1, "Ann Lee"), r(2, "Ben Tan")], [r(1, "Ben Tan"), r(2, "Ann Lee")]   # the ids the other way round
    for x, y in ((a, b), (a[::-1], b), (a, b[::-1]), (b, a)):
        got = compare.pair(x, y); assert len(got) == 2 and all(compare._kinds(*p) == [] for p in got), got
    got = compare.pair(a + [r(3, "Cy Ong")], b); assert [(p[0] and p[0]["teachers"], p[1] and p[1]["teachers"]) for p in got] == [(["Ann Lee"], ["Ann Lee"]), (["Ben Tan"], ["Ben Tan"]), (["Cy Ong"], None)], got   # one more on one side
    got = compare.pair([r(1, "Ann Lee", room="Lab 2"), r(2, "Ann Lee", room="Lab 1")], [r(7, "Ann Lee", room="Lab 1"), r(8, "Ann Lee", room="Lab 2")]); assert all(compare._kinds(*p) == [] for p in got), got   # the room first

def test_week_of_a_room():
    two_timetables(); m = compare.model_of("draft", None); before = copy.deepcopy(m["lessons"])
    rooms = sorted({x["room"] for x in m["lessons"] if x["room"]}); assert rooms, "the sample has rooms"
    r = rooms[0]; w = compare.week(m, "room", r)
    assert sorted((c["d"], c["p"], c["key"]) for c in w["cells"]) == sorted((x["d"], x["p"], k) for x in m["lessons"] if x["room"] == r for k in [":".join(kk) for kk in __import__("helper")._keys_of(x)])
    assert w["NP"] == m["NP"] and w["days"] == list(m["days"])
    assert compare.week(m, "class", CLASSES[0])["cells"] and compare.week(m, "teacher", TEACHERS[0])["cells"]
    for bad in (("room", "Nowhere"), ("class", "Nobody"), ("teacher", ""), ("thing", "x")): raises(ValueError, lambda: compare.week(m, *bad), "Pick a class, teacher or room on both timetables.")
    compare.diff("draft", "draft"); compare.rows(m); compare.xlsx("draft", "draft"); compare.week(m, "class", CLASSES[0])
    assert m["lessons"] == before and compare.model_of("draft", None)["lessons"] == before   # the shared model is untouched, lesson by lesson

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

def test_a_name_that_looks_like_a_formula_is_text():
    a = two_timetables(); real = compare.both
    def both(*k):
        d, ma, mb = real(*k)
        for i, text in zip(d["items"], ("=SUM(A1)", "+1", "@cmd")):
            for k in "ab":
                if i[k]: i[k] = dict(i[k], subject=text, what=f"{text} for {CLASSES[0]}", room="-2+3", teachers=[], classes=["=1+1"])
        return d, ma, mb
    plain = [[x.value for x in r] for r in openpyxl.load_workbook(io.BytesIO(compare.xlsx(a, "draft"))).active.iter_rows()]
    with patched(compare, "both", both): ws = openpyxl.load_workbook(io.BytesIO(compare.xlsx(a, "draft"))).active
    cells = [x for r in ws.iter_rows(min_row=2) for x in r if isinstance(x.value, str)]
    assert all(x.data_type == "s" for x in cells) and not [x for x in cells if x.data_type == "f"], [(x.value, x.data_type) for x in cells]
    assert {x.value for x in ws["B"][1:]} == {f"{t} for {CLASSES[0]}" for t in ("=SUM(A1)", "+1", "@cmd")} and {x.value for x in ws["A"][1:]} == {"=1+1"}
    assert all(x.quotePrefix for r in ws.iter_rows(min_row=2, max_col=2) for x in r)
    assert [x.value for x in ws[1]] == ["Class", "Lesson", "A", "B"] and not any(x.quotePrefix for x in ws[1])   # a plain cell is as it was
    again = openpyxl.load_workbook(io.BytesIO(compare.xlsx(a, "draft"))).active; assert [[x.value for x in r] for r in again.iter_rows()] == plain and not any(x.quotePrefix for r in again.iter_rows() for x in r)

def test_versions_are_labelled_with_their_time():
    shutil.rmtree(versions.VDIR, ignore_errors=True); save_draft(ROWS)
    with patched(store, "now", lambda: "22 Nov 2026, 13:12"): v = "v:" + versions.save("Run A · edited", "Tester")["id"]
    with patched(store, "now", lambda: "22 Nov 2026, 09:05"): w = "v:" + versions.save("Run A · edited", "Tester")["id"]   # the same name
    assert compare.label(v) == "Run A · edited (22 Nov 2026, 1.12 pm)" and compare.label(w) == "Run A · edited (22 Nov 2026, 9.05 am)"
    assert compare.label("draft") == "The draft on step 8" and compare.label("published") == "Published timetable"
    j = c.get(f"/api/compare?a={v}&b={w}").get_json(); by = {s["src"]: s["label"] for s in j["sources"]}
    assert by[v] == compare.label(v) == j["a"]["label"] and by[w] == compare.label(w) == j["b"]["label"] and by["draft"] == "The draft on step 8"
    raises(ValueError, lambda: compare.label("v:" + "0" * 12), "There is no such version."); raises(ValueError, lambda: compare.label("thing"), "There is no such timetable.")

def test_a_version_that_cannot_be_read_is_said():
    a = two_timetables(); said = {"error": "That version could not be read."}; f = versions.folder(a[2:]); tp = draft.paths(f)[1]; good = open(tp, "rb").read()
    def spoil(): open(tp, "wb").write(b"garbage")
    def lose(): os.remove(tp)
    for breakage in (spoil, lose):
        breakage()
        for u in (f"/api/compare?a={a}&b=draft", f"/api/compare?a=draft&b={a}", f"/api/compare.xlsx?a={a}&b=draft"):
            r = c.get(u); assert r.status_code == 400 and r.get_json() == said, (u, r.status_code, r.get_json())
        assert c.get("/compare").status_code == 200 and a in [s["src"] for s in c.get("/api/compare?a=draft&b=draft").get_json()["sources"]]
        open(tp, "wb").write(good)
    assert c.get(f"/api/compare?a={a}&b=draft").status_code == 200
    # a fault in the compare itself is a sentence, and never "Save the school's setup first"
    def fault(*k): raise KeyError("odd")
    with patched(compare, "both", fault), patched(A.app.logger, "disabled", True):
        for u in (f"/api/compare?a={a}&b=draft", f"/api/compare.xlsx?a={a}&b=draft"):
            r = c.get(u); assert r.status_code == 400 and r.get_json()["error"].startswith("Could not compare the timetables: ") and A.NO_SETUP not in r.get_json()["error"], (u, r.get_json())
    with patched(compare, "week", fault), patched(A.app.logger, "disabled", True): assert c.get(f"/api/compare?a={a}&b=draft").status_code == 400
    # no setup is still said
    def none(*k): raise LookupError("no setup")
    with patched(compare, "both", none): r = c.get(f"/api/compare?a={a}&b=draft"); assert r.status_code == 409 and r.get_json() == {"error": A.NO_SETUP}
    # a version deleted in the middle of it is no such version
    def gone(folder, rec=None): shutil.rmtree(folder); raise OSError("gone")
    with patched(draft, "model_in", gone): r = c.get(f"/api/compare?a={a}&b=draft"); assert r.status_code == 404 and r.get_json()["error"] == "There is no such version.", r.get_json()

def test_one_compare_loads_each_side_once():
    a = two_timetables(); real, calls = compare._load, []
    with patched(compare, "_load", lambda src, rec: (calls.append(src), real(src, rec))[1]):
        assert c.get(f"/api/compare?a={a}&b=draft&view=class&name={CLASSES[0]}").status_code == 200
    assert calls == [a, "draft"], calls

def test_a_length_change_is_a_time_difference():
    shutil.rmtree(versions.VDIR, ignore_errors=True)
    save_draft([dict(ROWS[0], p=2, n=1)]); v = versions.save("Short", "Tester"); save_draft([dict(ROWS[0], id=77, p=2, n=2)])
    d = compare.diff("v:" + v["id"], "draft"); assert len(d["items"]) == 1 and d["items"][0]["kinds"] == ["time"], d["items"]
    assert d["totals"]["moved"] == 0
    assert compare.line(d["items"][0], DAYS) == f"{CLASSES[0]} {SUBJ}: {DAYS[0]} 2 (1 period) → {DAYS[0]} 2 (2 periods)", compare.line(d["items"][0], DAYS)

def test_published_counts_are_cached_until_the_setup_or_the_publish_changes():
    shutil.rmtree(versions.VDIR, ignore_errors=True); save_draft(CLEAN); assert c.post("/api/draft/publish").status_code == 200
    real, calls = compare._published_model, []
    compare._published_model = lambda rec: (calls.append(1), real(rec))[1]; compare._counts_cache.clear()
    try:
        first = compare.published_counts(); compare.published_counts(); compare.published_counts()
        assert len(calls) == 1, calls
        rec = store.setup_record(); compare.published_counts(dict(rec, v=rec["v"] + 1)); assert len(calls) == 2   # another setup version: fresh
        time.sleep(0.05); assert c.post("/api/draft/publish").status_code == 200
        again = compare.published_counts(); assert len(calls) == 3 and again["published_at"] is not None and first["critical"] == again["critical"] == 0
        def bad(rec): calls.append(1); raise ValueError(compare.UNREADABLE)
        compare._published_model = bad; compare._counts_cache.clear(); n = len(calls)
        assert compare.published_counts()["error"] == compare.UNREADABLE and compare.published_counts()["error"] == compare.UNREADABLE
        assert len(calls) == n + 2, calls   # an unreadable timetable is read again on the next call
    finally: compare._published_model = real

def test_an_unreadable_published_timetable_does_not_break_the_list():
    shutil.rmtree(versions.VDIR, ignore_errors=True); save_draft(CLEAN); versions.save("Kept", "Tester"); assert c.post("/api/draft/publish").status_code == 200
    import pickle
    path = os.path.join(store.PUB, "model.pkl"); good = open(path, "rb").read()
    m = pickle.loads(good); m["lessons"] = [dict(x, d=object()) for x in m["lessons"]]
    open(path, "wb").write(pickle.dumps(m)); store._cache.update(stamp=None, value=None); compare._counts_cache.clear()
    try:
        r = c.get("/api/draft/versions"); assert r.status_code == 200, r.get_json(); j = r.get_json()
        assert j["published"]["critical"] is None and j["published"]["error"] == "The published timetable could not be read." and j["published"]["published_at"], j["published"]
        assert "Kept" in [v["name"] for v in j["versions"]]
    finally: open(path, "wb").write(good); store._cache.update(stamp=None, value=None); compare._counts_cache.clear()

def test_compare_routes_need_the_committee():
    r = NOSE.get("/compare"); assert r.status_code == 302 and "/login" in r.headers["Location"], (r.status_code, r.headers.get("Location"))
    for u in ("/api/compare", "/api/compare.xlsx"):
        r = NOSE.get(u); assert r.status_code == 401, (u, r.status_code)
    assert c.get("/compare").status_code == 200 and b"compare.js" in c.get("/compare").data

def test_compare_api_shape():
    a = two_timetables()
    r = c.get(f"/api/compare?a={a}&b=draft&view=class&name={CLASSES[0]}"); assert r.status_code == 200, r.get_json(); j = r.get_json()
    assert j["a"] == dict(src=a, label=compare.label(a)) and j["a"]["label"].startswith("Run A (") and j["b"]["src"] == "draft" and j["view"] == "class" and j["name"] == CLASSES[0]
    assert len(j["lines"]) >= 1 and j["totals"]["moved"] == 1 and j["names"]["classes"][:2] == CLASSES
    assert [DAYS.index(DAYS[0]), 2] in j["marks"]["b"] and [0, 0] in j["marks"]["a"], j["marks"]   # the moved lesson: new time on b, old time on a
    assert sorted(j["weeks"]) == ["a", "b"] and j["weeks"]["a"]["NP"] == j["weeks"]["b"]["NP"]
    srcs = [s["src"] for s in j["sources"]]; assert srcs[0] == "draft" and a in srcs, srcs
    assert next(s for s in j["sources"] if s["src"] == "draft")["label"] == "The draft on step 8"
    # no b -> the draft; no view or name -> the first class with a difference
    j2 = c.get(f"/api/compare?a={a}").get_json(); assert j2["b"]["src"] == "draft" and j2["view"] == "class" and j2["name"] in j2["names"]["classes"] and j2["lines"], j2
    # a teacher and a room
    jt = c.get(f"/api/compare?a={a}&view=teacher&name={TEACHERS[1]}").get_json(); assert jt["lines"] and jt["marks"]["a"] + jt["marks"]["b"], jt
    jr = c.get(f"/api/compare?a={a}&view=room&name={ROOM}").get_json(); assert jr["lines"] and jr["marks"]["b"] and not jr["marks"]["a"], jr
    # unknown name on both sides: 400; a name on one side only: two grids, the missing one empty
    r = c.get(f"/api/compare?a={a}&view=class&name=Nobody"); assert r.status_code == 400 and r.get_json()["error"] == "Pick a class, teacher or room on both timetables.", r.get_json()
    one = c.get(f"/api/compare?a={a}&view=class&name={CLASSES[1]}"); assert one.status_code == 200
    # the same timetable twice: nothing differs, still a page
    same = c.get("/api/compare?a=draft&b=draft"); assert same.status_code == 200 and same.get_json()["lines"] == [] and same.get_json()["marks"] == dict(a=[], b=[])
    x = c.get(f"/api/compare.xlsx?a={a}&b=draft"); assert x.status_code == 200 and "Differences Run A and The draft on step 8.xlsx" in x.headers["Content-Disposition"], x.headers
    assert openpyxl.load_workbook(io.BytesIO(x.data)).active.max_row >= 4

def test_compare_a_class_on_one_side_only():
    shutil.rmtree(versions.VDIR, ignore_errors=True)
    save_draft(ROWS[:2]); v = versions.save("Few", "Tester"); save_draft(ROWS[:2] + [dict(EXTRA, classes=[CLASSES[1]])])
    j = c.get(f"/api/compare?a=v:{v['id']}&view=class&name={CLASSES[1]}"); assert j.status_code == 200, j.get_json(); j = j.get_json()
    assert j["weeks"]["a"]["cells"] == [] and j["weeks"]["b"]["cells"] and j["weeks"]["a"]["NP"] == j["weeks"]["b"]["NP"] and j["marks"]["b"] and not j["marks"]["a"], j

def test_compare_unknown_source():
    two_timetables()
    r = c.get("/api/compare?a=v:000000000000&b=draft"); assert r.status_code == 404 and r.get_json()["error"] == "There is no such version.", r.get_json()
    r = c.get("/api/compare?a=draft&b=published")
    if r.status_code != 200: assert r.status_code == 400 and r.get_json()["error"], r.get_json()
    assert c.get("/api/compare.xlsx?a=v:000000000000&b=draft").status_code == 404

if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for f in tests: f()
    print(f"{len(tests)} checks passed")

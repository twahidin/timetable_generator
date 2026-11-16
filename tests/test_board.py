"""Plain-assert tests for the board and the slots the server answers: .venv/bin/python tests/test_board.py"""
import gzip, io, json, os, secrets, shutil, sys, tempfile, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = tempfile.mkdtemp()
CODE = secrets.token_hex(4)
os.environ.pop("HEADS_CODE", None)
os.environ.update(DATA_DIR=DATA, SECRET_KEY=secrets.token_hex(16), AI_PROVIDER="anthropic", AI_API_KEY="", COMMITTEE_CODE=CODE, TEACHER_CODE=secrets.token_hex(4), STUDENT_CODE=secrets.token_hex(4))
sys.path.insert(0, ROOT)
import openpyxl  # noqa: E402
import app as A, draft, store  # noqa: E402
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
        ws.append([r["id"], r["day"], r["p"], r["p"] + r["n"] - 1, r["n"], "", "", r["level"], r.get("block", ""), ", ".join(r["classes"]), r["subject"], r.get("group", "Entire Class"), ", ".join(r.get("teachers", [])), "", "", ""])
    buf = io.BytesIO(); wb.save(buf); return buf.getvalue()

def setup_bytes(spec):
    p = os.path.join(tempfile.mkdtemp(), "setup.xlsx"); write_template(spec, p); return open(p, "rb").read()

def save_draft(rows):
    r = c.post("/api/draft", data=dict(setup=(io.BytesIO(setup_bytes(SPEC)), "setup.xlsx"), timetable=(io.BytesIO(workbook(rows)), "timetable.xlsx")), content_type="multipart/form-data")
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

def placed(b):
    """every class of a card is in exactly one entry of levels and has codes"""
    names = [x for l in b["levels"] for x in l["classes"]]
    assert len(names) == len(set(names)) and set(names) == set(b["codes"]), names
    for x in b["cards"]: assert x["classes"] and all(k in b["codes"] for k in x["classes"]), x

def board():
    b = draft.board(); placed(b); return b

def card(i): return next(x for x in board()["cards"] if x["id"] == i)

def test_every_lesson_is_on_exactly_one_card():
    b = board(); m = draft._now()[0]
    assert sorted(x["id"] for x in b["cards"]) == sorted({x["id"] for x in m["lessons"]})
    assert sum(len(x["rows"]) for x in b["cards"]) == len(m["lessons"]) == len(ROWS)

def test_a_band_is_one_card_with_all_its_classes_and_rows():
    x = card(BAND_ID)
    assert x["band"] == "Band A" and len(x["rows"]) == 3 and set(x["classes"]) == BAND_CLASSES and x["classes"] == list(dict.fromkeys(x["classes"]))
    assert [r["group"] for r in x["rows"]] == ["G1", "G2", "G3"] and (x["d"], x["p"], x["n"]) == (2, 0, 2)
    assert x["rows"][2]["tshorts"] == ["Nobody Known"]   # a teacher who is not in the setup keeps the name

def test_a_plain_lesson_has_no_band_and_its_teachers_short_names():
    x = card(PLAIN_ID)
    assert x["band"] == "" and len(x["rows"]) == 1 and len(x["rows"][0]["tshorts"]) == len(x["rows"][0]["teachers"]) == 1 and x["what"] == f"{SUBJ} for {CLASSES[0]}"
    assert x["rows"][0]["tshorts"][0] != "" and x["rows"][0]["subject"] == SUBJ and x["classes"] == [CLASSES[0]]

def test_a_band_with_no_block_is_named_by_its_subjects():
    m = draft._now()[0]; rows = [dict(x, block="") for x in m["lessons"] if x["id"] == BAND_ID]
    shorts = [m["subjects"][s]["short"] for s in dict.fromkeys(x["subject"] for x in rows)]
    real = draft._now
    try:
        draft._now = lambda: (dict(m, lessons=[x for x in m["lessons"] if x["id"] != BAND_ID] + rows), None, None)
        assert card(BAND_ID)["band"] == " / ".join(shorts) and len(shorts) == 2
    finally: draft._now = real

def test_codes_cover_every_class_and_day():
    b = board(); names = [x for l in b["levels"] for x in l["classes"]]
    assert set(names) == set(b["codes"]) and all(len(v) == len(b["days"]) and all(len(s) == b["NP"] for s in v) for v in b["codes"].values())
    assert b["days"] == DAYS and b["NP"] == NPD and len(b["times"]) == NPD
    assert b["levels"][0]["level"] == SPEC["classes"][0]["level"] and CLASSES[0] in b["levels"][0]["classes"]
    assert b["subjects"][SUBJ][0] and len(b["subjects"][SUBJ]) == 3 and all(len(p) == 2 and all(isinstance(h, str) for h in p) for p in b["palette"]) and len(b["palette"]) >= 10
    json.dumps(b)

def test_a_class_not_in_the_setup_has_a_row():
    b = board()
    assert b["levels"][-1] == dict(level="Not in the setup", classes=["9Z"]) and b["codes"]["9Z"] == ["." * b["NP"]] * len(b["days"])
    assert [l["level"] for l in b["levels"][:-1]] == draft._now()[0]["levels"]

def test_a_setup_class_on_a_level_the_model_lacks_is_not_lost():
    m = draft._now()[0]; spec = m["checked_setup"]; real = draft._now
    row = dict(m["lessons"][0], id=50, classes=["E1"], block="", group="Entire Class", level="")
    m2 = dict(m, classes=m["classes"] + [dict(name="E1", level="", size="", home="", parents=[])], lessons=m["lessons"] + [row],
              checked_setup=dict(spec, classes=spec["classes"] + [{"class": "E1", "level": ""}]))
    try:
        draft._now = lambda: (m2, None, None)
        b = board()
        assert b["levels"][-1] == dict(level="Not in the setup", classes=["9Z", "E1"])
        assert b["codes"]["E1"] == ["." * b["NP"]] * len(b["days"])
        assert next(x for x in b["cards"] if x["id"] == 50)["classes"] == ["E1"]
    finally: draft._now = real

def test_slots_are_the_editors_slots():
    assert draft.slots(PLAIN_ID) == dict(id=PLAIN_ID, slots=draft.options(PLAIN_ID)["slots"])
    assert draft.slots(str(PLAIN_ID))["id"] == PLAIN_ID

def test_slots_of_an_unknown_lesson_is_a_sentence():
    for bad in (None, "x", "1.5", 999999): raises(ValueError, lambda: draft.slots(bad), NOT_FOUND)

def test_a_move_refused_after_the_draft_changed_leaves_the_board_as_it_was():
    mine = {(x["d"], x["p"]): x for x in draft.slots(PLAIN_ID)["slots"] if x["state"] == "ok" and x["swap"] is None}
    s = next(x for x in draft.slots(OTHER_ID)["slots"] if x["state"] == "ok" and x["swap"] is None and (x["d"], x["p"]) in mine)
    draft.fix(dict(kind="move", id=OTHER_ID, d=s["d"], p=s["p"]))   # someone else takes the place first
    before = draft.board()
    raises(ValueError, lambda: draft.fix(dict(kind="move", id=PLAIN_ID, d=s["d"], p=s["p"])))
    assert draft.board() == before

def test_the_routes():
    b = draft.board()
    r = c.get("/api/draft/board", headers={"Accept-Encoding": "gzip"})
    assert r.status_code == 200 and r.headers["Content-Encoding"] == "gzip" and "Accept-Encoding" in r.headers["Vary"] and r.get_data()[:2] == b"\x1f\x8b"
    assert json.loads(gzip.decompress(r.get_data())) == b
    r = c.get("/api/draft/board", headers={"Accept-Encoding": "identity"})
    assert r.status_code == 200 and "Content-Encoding" not in r.headers and r.get_json() == b
    r = c.get("/api/draft/slots"); assert r.status_code == 400 and r.get_json() == {"error": "Say which lesson."}
    r = c.get("/api/draft/slots?id=999999"); assert r.status_code == 400 and r.get_json() == {"error": NOT_FOUND}
    r = c.get(f"/api/draft/slots?id={PLAIN_ID}"); assert r.status_code == 200 and r.get_json() == draft.slots(PLAIN_ID) and "Content-Encoding" not in r.headers
    for url in ("/api/draft/board", f"/api/draft/slots?id={PLAIN_ID}"):
        r = NOSE.get(url, headers={"Accept-Encoding": "gzip"}); assert r.status_code == 401 and "Content-Encoding" not in r.headers, url
    shutil.rmtree(draft.DIR)
    for url in ("/api/draft/board", f"/api/draft/slots?id={PLAIN_ID}"):
        r = c.get(url, headers={"Accept-Encoding": "gzip"}); assert r.status_code == 404 and "Content-Encoding" not in r.headers and r.get_json() == {"error": "There is no draft."}, url
        assert NOSE.get(url).status_code == 401

def test_every_upload_has_its_own_id_and_an_old_draft_without_one_still_opens():
    save_draft(ROWS); one = draft.summary(), draft.info()
    save_draft(ROWS); two = draft.summary(), draft.info()   # at once: the same minute, so uploaded_at may be the same
    assert one[0]["upload_id"] and two[0]["upload_id"] and one[0]["upload_id"] != two[0]["upload_id"], (one[0], two[0])
    assert one[1]["upload_id"] == one[0]["upload_id"] and two[1]["upload_id"] == two[0]["upload_id"]
    meta = store.read_json(draft._p("meta.json")); meta.pop("upload_id"); store.write_json(draft._p("meta.json"), meta)   # a draft saved before upload ids
    assert draft.summary()["upload_id"] is None and draft.info()["upload_id"] is None
    assert draft.summary()["upload_id"] is None   # steadily
    placed(draft.board()); assert len(draft.board()["cards"]) == 4
    save_draft(ROWS); assert draft.summary()["upload_id"]   # its next upload gets one

def test_the_board_of_two_thousand_rows_is_quick_and_small():
    rows = [dict(id=i + 1, day=DAYS[i % len(DAYS)], p=(i // len(DAYS)) % NPD, n=1, level=LEVEL, classes=[f"T{i % 32 + 1:02d}"], subject=(SUBJ, SUBJ2)[i % 2], teachers=[TEACHERS[i % 3]]) for i in range(2000)]
    save_draft(rows); draft._now()   # the model is built once and kept: the time is the board's own
    t0 = time.time(); b = draft.board(); placed(b); took = time.time() - t0
    assert len(b["cards"]) == 2000 and took < 1, took
    size = len(gzip.compress(json.dumps(b).encode()))
    assert size < 200000, size
    r = c.get("/api/draft/board", headers={"Accept-Encoding": "gzip"}); assert r.status_code == 200 and len(r.get_data()) < 200000

if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for f in tests: f()
    print(f"{len(tests)} checks passed")

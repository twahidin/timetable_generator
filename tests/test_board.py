"""Plain-assert tests for the board and the slots the server answers: .venv/bin/python tests/test_board.py"""
import gzip, io, json, os, secrets, shutil, sys, tempfile, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = tempfile.mkdtemp()
CODE = secrets.token_hex(4)
os.environ.pop("HEADS_CODE", None)
os.environ.update(DATA_DIR=DATA, SECRET_KEY=secrets.token_hex(16), AI_PROVIDER="anthropic", AI_API_KEY="", COMMITTEE_CODE=CODE, TEACHER_CODE=secrets.token_hex(4), STUDENT_CODE=secrets.token_hex(4))
sys.path.insert(0, ROOT)
import openpyxl  # noqa: E402
import app as A, draft, fixes as fixes_mod, store  # noqa: E402
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
        draft._now = lambda: (dict(m, lessons=[x for x in m["lessons"] if x["id"] != BAND_ID] + rows), None, dict(pool=[]))
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
        draft._now = lambda: (m2, None, dict(pool=[]))
        b = board()
        assert b["levels"][-1] == dict(level="Not in the setup", classes=["9Z", "E1"])
        assert b["codes"]["E1"] == ["." * b["NP"]] * len(b["days"])
        assert next(x for x in b["cards"] if x["id"] == 50)["classes"] == ["E1"]
    finally: draft._now = real

def test_slots_are_the_editors_slots():
    b, o = draft.slots(PLAIN_ID), draft.options(PLAIN_ID); bare = lambda s: {k: v for k, v in s.items() if k != "there"}
    assert [bare(s) for s in b["slots"]] == o["slots"] and b["delete"] == o["delete"] and b["id"] == PLAIN_ID
    assert all(set(s) == {"d", "p", "state", "why", "swap", "also", "there"} for s in b["slots"])   # the board's own: who is there, no push or place beside judged
    assert all(set(s) == {"d", "p", "state", "why", "swap", "also"} for s in o["slots"])   # without the extras (the helper's, the typed request's): as before this stage
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

# ------------------------------------------------------------------------------------------------ Not placed, forcing, a push
from ttgen.export import ENTIRE  # noqa: E402
L1 = SPEC["day_structure"][LEVEL][DAYS[0]].index("L"); assert SPEC["day_structure"][LEVEL][DAYS[0]][L1:L1 + 3] == "LLL"   # three lesson periods in a row, from L1
ROOMS = [v["room"] for v in SPEC["venues"] if (v.get("kind") or "classroom") == "classroom"][:2]; assert len(ROOMS) == 2
BAND = dict(level=LEVEL, block=f"{LEVEL} Band A")
PLAY = [   # the same lessons as ROWS, in lesson periods; only the first has a room
    dict(id=PLAIN_ID, day=DAYS[0], p=L1, n=1, level=LEVEL, classes=[CLASSES[0]], subject=SUBJ, teachers=[TEACHERS[0]], room=ROOMS[0]),
    dict(id=OTHER_ID, day=DAYS[1], p=L1 + 1, n=1, level=LEVEL, classes=[CLASSES[0]], subject=SUBJ2),
    dict(id=BAND_ID, day=DAYS[2], p=L1, n=2, classes=CLASSES, subject=SUBJ, group="G1", teachers=[TEACHERS[1]], **BAND),
    dict(id=BAND_ID, day=DAYS[2], p=L1, n=2, classes=[CLASSES[0]], subject=SUBJ2, group="G2", teachers=[TEACHERS[2]], **BAND),
    dict(id=BAND_ID, day=DAYS[2], p=L1, n=2, classes=[CLASSES[1]], subject=SUBJ, group="G3", teachers=["Nobody Known"], **BAND),
    dict(id=ODD_ID, day=DAYS[3], p=L1, n=1, level=LEVEL, classes=["9Z"], subject=SUBJ, teachers=[TEACHERS[0]]),
]
CLEAN = [dict(id=1, day=DAYS[0], p=L1, n=1, level=LEVEL, classes=[CLASSES[0]], subject=SUBJ, teachers=[TEACHERS[0]], room=ROOMS[0]),
         dict(id=2, day=DAYS[1], p=L1, n=1, level=LEVEL, classes=[CLASSES[1]], subject=SUBJ2, teachers=[TEACHERS[1]], room=ROOMS[1])]
P0, O0, B0 = (0, L1), (1, L1 + 1), (2, L1)   # where PLAIN, OTHER and the band are in PLAY, as (d, p)

def fresh(rows=None): save_draft(rows or PLAY)
def ids(b, key="cards"): return sorted(x["id"] for x in b[key])
def waiting(j): return [w for w in j["warnings"] if w.get("crit") == "notplaced"]
def fixes_stored(): return store.read_json(draft._p("meta.json"))["fixes"]
def move(i, at, **kw): return dict(kind="move", id=i, d=at[0], p=at[1], **kw)
def forced(f):
    """a fix as the board posts it when the place is red: with force and the sentence the server gives for it now (a clean one needs neither)"""
    plain = {k: v for k, v in f.items() if k not in ("force", "why")}
    try: return draft.fix(plain)
    except ValueError as e: return draft.fix(dict(plain, force=True, why=str(e)))

def test_a_lift_is_in_info_the_board_and_the_counts():
    fresh(CLEAN); j0 = draft.info(); assert j0["unplaced"] == 0 and j0["critical"] == 0 and not waiting(j0) and draft.board()["unplaced"] == []
    j = draft.fix(dict(kind="lift", id=1))
    assert j["unplaced"] == 1 and j["critical"] == j0["critical"] + 1 == sum(1 for w in j["warnings"] if w["crit"]), (j["critical"], j0["critical"])
    w = waiting(j); assert len(w) == 1 and w[0]["text"] == f"Not placed: {SUBJ} for {CLASSES[0]}." and w[0]["key"] == "clash:notplaced:1", w
    assert (w[0]["kind"], w[0]["strength"], w[0]["group"], w[0]["where"]) == ("clash", "Must", CLASSES[0], dict(cls=CLASSES[0], id=1))
    b = board(); assert ids(b) == [2] and ids(b, "unplaced") == [1]
    u = b["unplaced"][0]; assert u["d"] is None and u["p"] is None and u["was"] == dict(d=0, p=L1) and u["marks"] == ["notplaced"] and u["why"] == "" and u["rows"][0]["subject"] == SUBJ and u["classes"] == [CLASSES[0]]
    assert draft.info()["fixes"][-1]["text"] == f"Lifted out {SUBJ} for {CLASSES[0]} from {DAYS[0]} period {L1}."
    assert draft.undo()["critical"] == 0 and draft.info()["unplaced"] == 0

def test_a_forced_move_needs_force():
    fresh(); f = move(OTHER_ID, P0); why = f"{CLASSES[0]} has {SUBJ} for {CLASSES[0]} then."
    raises(ValueError, lambda: draft.fix(f), why); raises(ValueError, lambda: draft.fix(dict(f, force=1, why=why)), why); raises(ValueError, lambda: draft.fix(dict(f, force="yes", why=why)), why)
    raises(ValueError, lambda: draft.fix(dict(f, force=True)), why)   # force with no why is refused as one without force
    raises(ValueError, lambda: draft.fix(dict(f, force=True, why="Another reason.")), why); raises(ValueError, lambda: draft.fix(dict(f, force=True, why=None)), why)
    assert fixes_stored() == []
    j = draft.fix(dict(f, force=True, why=why)); assert len(j["fixes"]) == 1 and not {"force", "push", "why"} & set(fixes_stored()[0])
    x = card(OTHER_ID); assert "class" in x["marks"] and x["why"] == why and (x["d"], x["p"]) == P0, x
    assert "class" in card(PLAIN_ID)["marks"] and len(board()["cards"]) == 4

def test_a_place_judged_na_is_refused_even_forced():
    fresh(); draft.fix(dict(kind="lift", id=PLAIN_ID)); f = dict(kind="place", id=PLAIN_ID, d=0, p=NPD)
    raises(ValueError, lambda: draft.fix(f), "That is outside the day."); raises(ValueError, lambda: draft.fix(dict(f, force=True, why="That is outside the day.")), "That is outside the day.")
    raises(ValueError, lambda: draft.fix(move(PLAIN_ID, (0, 2))), "That lesson is not placed. Place it first.")
    assert len(fixes_stored()) == 1 and draft.info()["unplaced"] == 1

def test_a_push_is_worked_out_by_the_server():
    fresh(); forced(move(OTHER_ID, (0, L1 + 1), force=True))
    j = forced(move(BAND_ID, (0, L1), push=True, force=True)); f = fixes_stored()[-1]
    assert f["out"] == [PLAIN_ID, OTHER_ID] and "push" not in f and "force" not in f and "Pushed out:" in f["text"], f
    b = board(); assert ids(b, "unplaced") == [PLAIN_ID, OTHER_ID] and ids(b) == [BAND_ID, ODD_ID] and j["unplaced"] == 2
    assert [x["was"] for x in b["unplaced"]] == [dict(d=0, p=L1), dict(d=0, p=L1 + 1)]
    b = draft.undo() and board(); assert ids(b, "unplaced") == [] and ids(b) == [1, 2, 3, 4] and (card(BAND_ID)["d"], card(BAND_ID)["p"]) == B0
    j = forced(move(OTHER_ID, (3, 3), push=True, force=True)); assert "out" not in fixes_stored()[-1] and j["unplaced"] == 0   # nothing in the way: no out key
    raises(ValueError, lambda: draft.fix(move(PLAIN_ID, (3, 3))), f"{CLASSES[0]} has {SUBJ2} for {CLASSES[0]} then.")   # a push is never assumed
    draft.fix(move(PLAIN_ID, (3, 3), push=True)); assert fixes_stored()[-1]["out"] == [OTHER_ID]   # with the push the clash is gone, so no force was needed

def test_a_push_never_takes_a_lesson_of_another_class():
    fresh(); forced(move(ODD_ID, P0, push=True, force=True))   # 9Z shares a teacher and now a period with PLAIN, but not a class
    assert "out" not in fixes_stored()[-1] and ids(board(), "unplaced") == []
    assert {"teacher"} <= set(card(PLAIN_ID)["marks"])

def test_a_second_push_of_the_same_lesson_finds_it_gone():
    fresh(); forced(move(OTHER_ID, B0, push=True, force=True)); assert fixes_stored()[-1]["out"] == [BAND_ID]
    forced(move(PLAIN_ID, B0, push=True, force=True)); assert fixes_stored()[-1]["out"] == [OTHER_ID]
    b = board(); assert not set(ids(b)) & set(ids(b, "unplaced")) and ids(b, "unplaced") == [OTHER_ID, BAND_ID]
    draft.undo(); assert ids(board(), "unplaced") == [BAND_ID]

def test_a_place_with_a_push_and_an_add_with_a_push():
    fresh(); draft.fix(dict(kind="lift", id=BAND_ID)); forced(dict(kind="place", id=BAND_ID, d=1, p=L1 + 1, push=True, force=True)); f = fixes_stored()[-1]
    assert f["out"] == [OTHER_ID] and ids(board(), "unplaced") == [OTHER_ID] and "push" not in f and "force" not in f, f
    draft.undo(); draft.undo(); b = board(); assert ids(b, "unplaced") == [] and all(isinstance(s["classes"], list) and s["classes"] for s in b["short"])
    sh = next(s for s in b["short"] if CLASSES[0] in s["classes"])
    forced(dict(kind="add", key=sh["key"], d=P0[0], p=P0[1], n=sh["n"], push=True, force=True)); f = fixes_stored()[-1]
    assert f["out"] == [PLAIN_ID] and "push" not in f and "force" not in f and f["text"].endswith(f"Pushed out: {SUBJ} for {CLASSES[0]}."), f
    assert ids(board(), "unplaced") == [PLAIN_ID]

def test_publish_printouts_and_download_are_refused_while_a_lesson_waits():
    fresh(CLEAN); assert draft.info()["critical"] == 0, [w for w in draft.info()["warnings"] if w["crit"]]
    sent, real = [], store.publish; store.publish = lambda *a, **k: sent.append(k)
    try:
        draft.fix(dict(kind="lift", id=1)); one = "1 lesson is not placed. Place it or delete it on step 8 first."
        raises(draft.Critical, draft.publish); assert sent == []
        raises(draft.NotPlaced, lambda: draft.printouts(os.path.join(tempfile.mkdtemp(), "o"), False), one)
        raises(draft.NotPlaced, lambda: draft.database(os.path.join(tempfile.mkdtemp(), "d.sqlite")), one)
        r = c.post("/api/draft/printouts", data=dict(single="0")); assert r.status_code == 409 and r.get_json() == dict(error=one, unplaced=1), r.get_json()
        r = c.get("/api/draft/download"); assert r.status_code == 409 and r.get_json() == dict(error=one, unplaced=1)
        draft.fix(dict(kind="lift", id=2)); two = "2 lessons are not placed. Place them or delete them on step 8 first."
        raises(draft.NotPlaced, lambda: draft.database(os.path.join(tempfile.mkdtemp(), "d.sqlite")), two)
        assert c.get("/api/draft/download").get_json() == dict(error=two, unplaced=2)
        draft.fix(dict(kind="place", id=1, d=0, p=L1)); draft.fix(dict(kind="place", id=2, d=1, p=L1))
        assert draft.info()["unplaced"] == 0 and draft.publish()["published"] and len(sent) == 1
        assert c.get("/api/draft/download").status_code == 200
        m, base = draft.printouts(os.path.join(tempfile.mkdtemp(), "o"), False); assert base
    finally: store.publish = real

def test_slots_of_a_waiting_lesson():
    fresh(); draft.fix(dict(kind="lift", id=PLAIN_ID)); s = draft.slots(PLAIN_ID)
    assert s["id"] == PLAIN_ID and len(s["slots"]) == len(DAYS) * NPD and all(x["swap"] is None for x in s["slots"]) and {"d", "p", "state", "why", "there"} <= set(s["slots"][0])
    assert next(x for x in s["slots"] if (x["d"], x["p"]) == O0)["there"] == [dict(id=OTHER_ID, what=f"{SUBJ2} for {CLASSES[0]}", classes=[CLASSES[0]], groups=1)]
    raises(ValueError, lambda: draft.slots(99), NOT_FOUND); raises(ValueError, lambda: draft.options(lesson_id=PLAIN_ID), NOT_FOUND)
    assert c.get(f"/api/draft/slots?id={PLAIN_ID}").status_code == 200 and draft.slots(OTHER_ID)["id"] == OTHER_ID

def test_no_room_is_a_warning_of_its_own_kind():
    fresh(); j = draft.info(); w = [x for x in j["warnings"] if x["kind"] == "room"]
    assert len(w) == 5 and len({x["key"] for x in w}) == 5 and all(x["crit"] == "" and x["strength"] == "Prefer" for x in w)   # PLAIN has a room: the other lesson and the three band rows and ODD have none
    x = next(x for x in w if x["key"] == f"room:none:{OTHER_ID}:{ENTIRE}"); assert x["text"] == f"No room: {SUBJ2} for {CLASSES[0]} on {DAYS[1]} period {L1 + 1}." and x["group"] == CLASSES[0]
    assert x["where"] == dict(cls=CLASSES[0], day=DAYS[1], period=L1 + 1, id=OTHER_ID, row=ENTIRE)
    assert next(y for y in w if y["key"] == f"room:none:{ODD_ID}:{ENTIRE}")["group"] == "9Z" and f"room:none:{BAND_ID}:G2" in {y["key"] for y in w}
    draft.fix(dict(kind="lift", id=OTHER_ID)); assert not [y for y in draft.info()["warnings"] if y["key"].startswith(f"room:none:{OTHER_ID}:")]   # a lesson not placed has none
    fresh(CLEAN); assert not [y for y in draft.info()["warnings"] if y["kind"] == "room"]

def test_update_step_5_is_withheld_for_a_waiting_lesson():
    fresh(); draft.fix(dict(kind="lift", id=PLAIN_ID)); suffix = " A lesson of it is waiting in Not placed."
    w = [x for x in draft.info()["warnings"] if x["key"] in (f"dep:C:{CLASSES[0]}:{SUBJ}:missing", f"dep:C:{CLASSES[0]}:{SUBJ}:periods")]
    assert w and all(x["ops"] is None and x["text"].endswith(suffix) for x in w), w
    raises(ValueError, lambda: draft.decide(w[0]["key"], "step5"))
    other = [x for x in draft.info()["warnings"] if x["key"].startswith("dep:") and not x["text"].endswith(suffix)]; assert other   # the rest are as they were

def test_update_step_5_is_withheld_for_every_class_of_a_waiting_lesson():
    two = [dict(id=1, day=DAYS[0], p=L1, n=1, level=LEVEL, classes=CLASSES, subject=SUBJ, teachers=[TEACHERS[0]], room=ROOMS[0])]
    fresh(two); draft.fix(dict(kind="lift", id=1)); suffix = " A lesson of it is waiting in Not placed."
    keys = [f"dep:C:{k}:{SUBJ}:missing" for k in CLASSES]; ws = {w["key"]: w for w in draft.info()["warnings"]}
    assert all(k in ws and ws[k]["ops"] is None and ws[k]["text"].endswith(suffix) for k in keys), [ws.get(k) for k in keys]
    raises(ValueError, lambda: draft.decide(keys[1], "step5"), "A lesson of it is waiting in Not placed. Place it or delete it first.")
    raises(ValueError, lambda: draft.decide(f"clash:notplaced:1", "step5"), "This warning cannot be settled by updating step 5.")
    fresh(); raises(ValueError, lambda: draft.decide(f"room:none:{OTHER_ID}:{ENTIRE}", "step5"), "This warning cannot be settled by updating step 5.")
    k = next(w["key"] for w in draft.info()["warnings"] if w["kind"] == "deployment" and w["ops"] is None and not w["text"].endswith(suffix))
    raises(ValueError, lambda: draft.decide(k, "step5"), "This difference is set on step 3 for the whole level; the app does not change it from here.")

def test_publish_refuses_on_the_pool_itself_too():
    fresh(CLEAN); draft.fix(dict(kind="lift", id=1)); sent, real, info = [], store.publish, draft.info
    store.publish = lambda *a, **k: sent.append(k); draft.info = lambda **kw: dict(info(**kw), critical=0)   # the critical count forced to 0
    try:
        raises(draft.NotPlaced, draft.publish, "1 lesson is not placed. Place it or delete it on step 8 first."); assert sent == []
        r = c.post("/api/draft/publish"); assert r.status_code == 409 and r.get_json() == dict(error="1 lesson is not placed. Place it or delete it on step 8 first.", unplaced=1), r.get_json()
    finally: store.publish, draft.info = real, info

def test_slots_answer_the_delete_of_any_lesson():
    from ttgen import verify
    P = verify.planned_rows(SPEC)[("C", CLASSES[0], SUBJ)]["periods"]
    leave = lambda k: f"That would leave {SUBJ} for {CLASSES[0]} with {k} periods; step 3 plans {P}."
    row = lambda j: dict(id=j + 1, day=DAYS[j % len(DAYS)], p=L1 + j // len(DAYS), n=1, level=LEVEL, classes=[CLASSES[0]], subject=SUBJ, teachers=[TEACHERS[0]], room=ROOMS[0])
    fresh([row(j) for j in range(P)]); a = draft.slots(2); assert set(a) == {"id", "slots", "delete"} and a["delete"] == dict(state="no", why=leave(P - 1), plan=True)   # a placed lesson step 5 asks for
    draft.fix(dict(kind="lift", id=1)); assert draft.slots(1)["delete"] == dict(state="no", why=leave(P - 1), plan=True)   # a waiting one
    fresh([row(j) for j in range(P + 1)]); assert draft.slots(2)["delete"] == dict(state="ok", why="", plan=False)   # a surplus one
    draft.fix(dict(kind="lift", id=1)); assert draft.slots(1)["delete"] == dict(state="ok", why="", plan=False) and draft.options(lesson_id=2)["delete"] == dict(state="ok", why="", plan=False)

def test_the_helper_and_the_batch_never_force():
    fresh(); f = move(OTHER_ID, P0, force=True, push=True)
    raises(ValueError, lambda: draft.fix_many([f]), f"{CLASSES[0]} has {SUBJ} for {CLASSES[0]} then."); assert fixes_stored() == []
    draft.fix_many([move(OTHER_ID, (3, 3), force=True, push=True)]); assert set(fixes_stored()[0]) == {"kind", "id", "d", "p", "at", "text", "batch"}, fixes_stored()
    draft.fix(dict(kind="lift", id=PLAIN_ID)); r = draft.suggest(f"clash:notplaced:{PLAIN_ID}"); assert r["suggestions"] == [] and r["blocked"] == []
    r = c.post("/api/draft/fixes", json=dict(fixes=[dict(kind="place", id=PLAIN_ID, d=0, p=L1)])); assert r.status_code == 400 and ids(board(), "unplaced") == [PLAIN_ID]
    r = c.post("/api/draft/preview", json=dict(fixes=[dict(kind="place", id=PLAIN_ID, d=0, p=L1), dict(kind="move", id=OTHER_ID, d=1, p=L1)])); assert r.status_code == 400 and r.get_json() == {"error": "This kind of fix is not known."}   # a batch of two never holds a place
    assert c.post("/api/draft/preview", json=dict(fixes=[dict(kind="place", id=PLAIN_ID, d=0, p=L1)])).status_code == 200 and ids(board(), "unplaced") == [PLAIN_ID]   # one place may be looked at, and is not made
    raises(ValueError, lambda: draft.fix_many([dict(kind="lift", id=OTHER_ID)]), "This kind of fix is not known."); assert len(fixes_stored()) == 2

def test_a_draft_from_before_this_stage_opens():
    fresh(); meta = store.read_json(draft._p("meta.json"))
    old = [dict(kind="move", id=OTHER_ID, d=3, p=3, at="2026-01-01", text="Moved."), dict(kind="swap", a=PLAIN_ID, b=OTHER_ID, at="2026-01-01", text="Swapped.")]
    store.write_json(draft._p("meta.json"), dict(meta, fixes=old)); draft._cache.clear()
    j = draft.info(); b = board(); assert j["unplaced"] == 0 and b["unplaced"] == [] and len(b["cards"]) == 4 and all("marks" in x and "why" in x for x in b["cards"]) and (card(PLAIN_ID)["d"], card(PLAIN_ID)["p"]) == (3, 3)

def test_a_stale_force_is_refused_with_the_reason_as_it_now_is():
    from ttgen import verify
    P = verify.planned_rows(SPEC)[("C", CLASSES[0], SUBJ)]["periods"]
    leave = lambda k: f"That would leave {SUBJ} for {CLASSES[0]} with {k} periods; step 3 plans {P}."
    row = lambda j: dict(id=j + 1, day=DAYS[j % len(DAYS)], p=L1 + j // len(DAYS), n=1, level=LEVEL, classes=[CLASSES[0]], subject=SUBJ, teachers=[TEACHERS[0]], room=ROOMS[0])
    fresh([row(j) for j in range(P)]); seen = draft.slots(2)["delete"]["why"]; assert seen == leave(P - 1)   # what the page showed for deleting lesson 2
    draft.fix(dict(kind="delete", id=3, force=True, why=leave(P - 1)))   # meanwhile a colleague deletes another lesson of it, for the same reason
    raises(ValueError, lambda: draft.fix(dict(kind="delete", id=2, force=True, why=seen)), leave(P - 2)); assert len(fixes_stored()) == 1
    raises(ValueError, lambda: draft.fix(dict(kind="delete", id=2, force=True)), leave(P - 2))
    draft.fix(dict(kind="delete", id=2, force=True, why=leave(P - 2))); assert len(fixes_stored()) == 2 and not {"force", "why"} & set(fixes_stored()[-1])
    r = c.post("/api/draft/fix", json=dict(kind="delete", id=4, force=True, why="Not the reason.")); assert r.status_code == 400 and r.get_json() == {"error": leave(P - 3)}, r.get_json()
    r = c.post("/api/draft/fix", json=dict(kind="delete", id=4, force=True, why=leave(P - 3))); assert r.status_code == 200 and len(fixes_stored()) == 3
    fresh(); f = move(OTHER_ID, P0, push=True); assert draft.slots(OTHER_ID) and draft.fix(f)   # a push that lands clean needs no force and no why
    assert fixes_stored()[-1]["out"] == [PLAIN_ID]

def test_a_band_pushed_out_is_named_as_a_band():
    fresh(); forced(move(OTHER_ID, (0, L1 + 1)))
    s = next(x for x in draft.slots(PLAIN_ID)["slots"] if (x["d"], x["p"]) == B0)
    assert s["there"] == [dict(id=BAND_ID, what="the Band A band", classes=CLASSES, groups=3)] and draft.place(PLAIN_ID, *B0)["push"]["out"] == s["there"], s["there"]
    forced(move(PLAIN_ID, B0, push=True)); assert fixes_stored()[-1]["text"].endswith(" Pushed out: the Band A band."), fixes_stored()[-1]["text"]

def test_marks_on_the_board_of_a_clean_draft_are_empty():
    fresh(CLEAN); b = board(); assert [x["marks"] for x in b["cards"]] == [[], []] and [x["why"] for x in b["cards"]] == ["", ""] and b["unplaced"] == []
    assert isinstance(b["short"], list) and all("classes" in s for s in b["short"])
    fresh(); assert "noteacher" in card(OTHER_ID)["marks"] and "noroom" in card(OTHER_ID)["marks"] and card(PLAIN_ID)["marks"] == []

# ------------------------------------------------------------------------------------------------ teachers and rooms
SABRINA, PRIYA, ZACH, FREE = "Sabrina Koh", "Priya Chua", "Zachary Ho", "Yasmin Ong"   # step 5's teacher of English Language for 1A, one of another department, one more, one on no lesson
HALL = "Hall"   # takes two lessons at once
C1, C3 = CLASSES[0], "1C"
KEY1 = f"C:{C1}:{SUBJ}"
TR = [   # lessons 1 and 6 are the key of PLAIN (1A, SUBJ); 5 and 7 keep Sabrina and Priya busy at the times of those two; 8 and 9 fill the Hall at the time of 1
    dict(id=1, day=DAYS[0], p=L1, n=1, level=LEVEL, classes=[C1], subject=SUBJ, teachers=[TEACHERS[0]], room=ROOMS[0]),
    dict(id=6, day=DAYS[3], p=L1, n=1, level=LEVEL, classes=[C1], subject=SUBJ, teachers=[TEACHERS[0]], room=ROOMS[1]),
    dict(id=5, day=DAYS[0], p=L1, n=1, level=LEVEL, classes=[CLASSES[1]], subject=SUBJ2, teachers=[SABRINA], room=ROOMS[1]),
    dict(id=7, day=DAYS[3], p=L1, n=1, level=LEVEL, classes=[CLASSES[1]], subject=SUBJ2, teachers=[PRIYA]),
    dict(id=8, day=DAYS[0], p=L1, n=1, level=LEVEL, classes=[C3], subject=SUBJ2, teachers=[ZACH], room=HALL),
]
W5 = W7 = f"{SUBJ2} for {CLASSES[1]}"; W8 = f"{SUBJ2} for {C3}"

def by_name(j, k="teachers", f="name"): return {x[f]: x for x in j[k]}

def test_the_board_lists_teachers_by_department_and_rooms_by_kind():
    fresh(); b = board()
    depts = list(dict.fromkeys((t.get("dept") or "") for t in SPEC["teachers"] if t.get("dept")))
    want = [dict(dept=d, teachers=[dict(name=t["name"], short=draft._now()[0]["teacher_ix"][t["name"]]["short"]) for t in SPEC["teachers"] if (t.get("dept") or "") == d]) for d in depts]
    assert want and all(g["teachers"] for g in want) and all(x["short"] for g in want for x in g["teachers"])
    assert b["teachers"] == want + [dict(dept="Not in the setup", teachers=[dict(name="Nobody Known", short="Nobody Known")])], b["teachers"]
    kinds = list(dict.fromkeys(v.get("kind") or "classroom" for v in SPEC["venues"]))
    assert b["rooms"] == [dict(kind=k, rooms=[v["room"] for v in SPEC["venues"] if (v.get("kind") or "classroom") == k]) for k in kinds], b["rooms"]
    code = lambda d, p: "L" if any(g[d][p] in "LA" for g in SPEC["day_structure"].values()) else "."
    assert b["day"] == ["".join(code(DAYS[d], p) for p in range(NPD)) for d in range(len(DAYS))] and len(b["day"]) == len(DAYS) and all(len(x) == NPD for x in b["day"]), b["day"]
    assert "L" in b["day"][0] and "." in b["day"][0]
    assert all(r["key"] for x in b["cards"] for r in x["rows"]) and card(PLAIN_ID)["rows"][0]["key"] == KEY1
    assert [r["key"] for r in card(BAND_ID)["rows"]] == ["G:G1", "G:G2", "G:G3"]
    draft.fix(dict(kind="lift", id=PLAIN_ID)); assert board()["unplaced"][0]["rows"][0]["key"] == KEY1
    rows = [dict(TR[0], room="Mystery Room"), dict(TR[1], room="TBC"), dict(TR[3], teachers=[]), dict(TR[4], room="")]   # a room only a lesson names; TBC and empty are no room
    save_draft(rows); b = board()
    assert b["rooms"][-1] == dict(kind="Not in the setup", rooms=["Mystery Room"]) and [g["kind"] for g in b["rooms"][:-1]] == kinds
    assert not [g for g in b["teachers"] if g["dept"] == "Not in the setup"] and [g["dept"] for g in b["teachers"]] == depts
    spec = draft._now()[0]["checked_setup"]; real = draft._now; m = draft._now()[0]
    teach = [dict(t) for t in spec["teachers"]] + [dict(name="Floating Teacher", dept=None, dept2=None)]; teach[0] = dict(teach[0], dept="", dept2="MT")
    try:   # a teacher with no home department is listed last, with none; a teacher with a second department is under the home one only
        draft._now = lambda: (dict(m, checked_setup=dict(spec, teachers=teach)), None, dict(pool=[]))
        g = draft.board()["teachers"]; assert g[-1] == dict(dept="", teachers=[dict(name=teach[0]["name"], short=m["teacher_ix"][teach[0]["name"]]["short"]), dict(name="Floating Teacher", short="Floating Teacher")]), g[-1]
        assert [x["dept"] for x in g] == depts + [""] and depts[0] == "MT", (depts, [x["dept"] for x in g])   # the teacher with no home department is last; the one moved out of MT leaves MT first
    finally: draft._now = real

def test_lesson_lists_free_teachers_first_in_the_editors_order():
    save_draft(TR); j = draft.lesson(PLAIN_ID); T = by_name(j)
    assert j["id"] == PLAIN_ID and j["group"] == ENTIRE and j["key"] == KEY1 and j["what"] == f"{SUBJ} for {C1}" and j["n_lessons"] == 2
    names = [SPEC_T["name"] for SPEC_T in SPEC["teachers"]]; assert sorted(T) == sorted(names) and len(j["teachers"]) == len(names)   # every teacher of the setup, once
    assert (T[SABRINA]["rank"], T[SABRINA]["free"], T[SABRINA]["doing"]) == (0, False, f"{W5} on {DAYS[0]} period {L1}"), T[SABRINA]
    assert (T[PRIYA]["rank"], T[PRIYA]["free"], T[PRIYA]["doing"]) == (3, False, f"{W7} on {DAYS[3]} period {L1}"), T[PRIYA]   # busy at the key's other lesson
    assert (T[TEACHERS[0]]["rank"], T[TEACHERS[0]]["free"], T[TEACHERS[0]]["doing"]) == (3, True, ""), T[TEACHERS[0]]   # on the key's own lessons: not busy because of them
    assert (T[ZACH]["rank"], T[ZACH]["free"], T[ZACH]["doing"]) == (3, False, f"{W8} on {DAYS[0]} period {L1}")
    assert (T[FREE]["rank"], T[FREE]["free"], T[FREE]["doing"]) == (3, True, "") and (T["Jasper Wong"]["rank"], T["Jasper Wong"]["free"]) == (1, True)   # an English teacher on the card, free; a mathematics teacher, free
    assert all(x["short"] for x in j["teachers"]) and all(x["free"] == (x["doing"] == "") for x in j["teachers"])
    setup_order = {n: i for i, n in enumerate(names)}
    keys = [(not x["free"], x["rank"], setup_order[x["name"]]) for x in j["teachers"]]; assert keys == sorted(keys), keys
    assert j["teachers"][0]["free"] and not j["teachers"][-1]["free"] and [x["name"] for x in j["teachers"] if not x["free"]] == [SABRINA, PRIYA, ZACH]
    save_draft(PLAY); b = draft.lesson(BAND_ID); assert (b["group"], b["key"], b["what"], b["n_lessons"]) == ("G1", "G:G1", "group G1", 1)
    assert draft.lesson(BAND_ID, "G3")["key"] == "G:G3" and draft.lesson(str(BAND_ID), "G2")["what"] == "group G2"
    raises(ValueError, lambda: draft.lesson(999), NOT_FOUND); raises(ValueError, lambda: draft.lesson("x"), NOT_FOUND); raises(ValueError, lambda: draft.lesson(BAND_ID, "G9"), "There is no row of G9 in that lesson.")

def test_lesson_lists_free_rooms_of_the_right_kind_first():
    rows = TR + [dict(id=9, day=DAYS[0], p=L1, n=1, level=LEVEL, classes=["1D"], subject=SUBJ2, teachers=[FREE], room=HALL)]
    save_draft(rows); j = draft.lesson(PLAIN_ID); R = by_name(j, "rooms", "room")
    venues = [str(v["room"]) for v in SPEC["venues"]]; assert sorted(R) == sorted(venues) and len(j["rooms"]) == len(venues)
    assert R[ROOMS[0]] == dict(room=ROOMS[0], kind="classroom", right=True, free=True, holding="")   # its own room: this lesson does not count
    assert R[ROOMS[1]] == dict(room=ROOMS[1], kind="classroom", right=True, free=False, holding=W5), R[ROOMS[1]]
    assert R[HALL]["free"] is False and R[HALL]["right"] is False and R[HALL]["kind"] == "pe venue" and R[HALL]["holding"] == W8
    assert R["Field"]["free"] and not R["Field"]["right"] and R["Science Room 1"]["kind"] == "science room"
    rows[-1] = dict(rows[-1], room=""); save_draft(rows); R = by_name(draft.lesson(PLAIN_ID), "rooms", "room"); assert R[HALL]["free"] and R[HALL]["holding"] == ""   # one lesson in a room of two
    order = [(0 if r["free"] and r["right"] else 1 if r["free"] else 2, venues.index(r["room"])) for r in draft.lesson(PLAIN_ID)["rooms"]]; assert order == sorted(order), order
    rooms = draft.lesson(PLAIN_ID)["rooms"]; assert [r["room"] for r in rooms][:2] == [ROOMS[0], "1-03"] and rooms[-1]["room"] == ROOMS[1] and rooms[-2]["room"] != HALL
    assert all(r["right"] == (r["kind"] == "classroom") for r in rooms)   # the kind of its present room is classroom

def test_lesson_of_a_waiting_lesson():
    save_draft(TR); draft.fix(dict(kind="lift", id=PLAIN_ID)); j = draft.lesson(PLAIN_ID); T = by_name(j)
    assert j["n_lessons"] == 2 and j["key"] == KEY1 and all(r["free"] and r["holding"] == "" for r in j["rooms"])
    assert T[SABRINA]["free"] and not T[PRIYA]["free"] and T[PRIYA]["doing"] == f"{W7} on {DAYS[3]} period {L1}"   # judged against lesson 6, the key's other lesson on the timetable
    draft.fix(dict(kind="lift", id=6)); j = draft.lesson(PLAIN_ID); assert all(x["free"] and x["doing"] == "" for x in j["teachers"]) and j["n_lessons"] == 2 and len(j["teachers"]) == len(SPEC["teachers"])
    assert draft.lesson(6)["n_lessons"] == 2

def taught(i):
    m, rec, fx = draft._now(); return [x["teachers"] for x in m["lessons"] + fx["pool"] if x["id"] == i]

def test_a_change_of_teacher_touches_every_lesson_of_the_key():
    save_draft(TR); draft.fix(dict(kind="lift", id=6)); n = draft.lesson(PLAIN_ID)["n_lessons"]; assert n == 2
    j = draft.fix(dict(kind="teacher", key=KEY1, teachers=[FREE])); assert len(j["fixes"]) == 2
    assert taught(1) == [[FREE]] and taught(6) == [[FREE]] and sum(taught(i) == [[FREE]] for i in (1, 6)) == n and taught(5) == [[SABRINA]]   # the lesson in the pool too, no other
    assert fixes_stored()[-1]["text"].endswith(f"is now taught by {FREE}, not {TEACHERS[0]}.")
    draft.undo(); assert taught(1) == [[TEACHERS[0]]] and taught(6) == [[TEACHERS[0]]] and [f["kind"] for f in fixes_stored()] == ["lift"]   # one undo; the lift stays

def test_a_busy_teacher_needs_force_with_the_reason():
    save_draft(TR); f = dict(kind="teacher", key=KEY1, teachers=[SABRINA]); why = f"{SABRINA} is teaching {W5} then."
    raises(ValueError, lambda: draft.fix(f), why); raises(ValueError, lambda: draft.fix(dict(f, force=True)), why); raises(ValueError, lambda: draft.fix(dict(f, force=True, why="Another reason.")), why)
    raises(ValueError, lambda: draft.fix(dict(f, force=1, why=why)), why); assert fixes_stored() == []
    j = draft.fix(dict(f, force=True, why=why)); assert len(j["fixes"]) == 1 and not {"force", "why"} & set(fixes_stored()[0]) and taught(1) == [[SABRINA]] and taught(6) == [[SABRINA]]
    assert "teacher" in card(1)["marks"] and "teacher" in card(5)["marks"] and taught(5) == [[SABRINA]]   # both lessons are marked; the other is not pushed out
    try: draft.fix(dict(kind="teacher", key="C:9Q:Nothing", teachers=[FREE]))
    except ValueError as e: sentence = str(e)
    assert sentence.startswith("There is no lesson of ")
    raises(ValueError, lambda: draft.fix(dict(kind="teacher", key="C:9Q:Nothing", teachers=[FREE], force=True, why=sentence)), sentence)   # a na is refused forced
    raises(ValueError, lambda: draft.fix(dict(kind="teacher", key=KEY1, teachers=["Not A Teacher"], force=True, why="x")), "Not A Teacher is not on the setup's list of teachers.")
    rw = dict(kind="room", id=1, group=ENTIRE, room=ROOMS[1]); rwhy = f"{ROOMS[1]} is in use then."   # a busy room: 5 is in it
    raises(ValueError, lambda: draft.fix(rw), rwhy); raises(ValueError, lambda: draft.fix(dict(rw, force=True, why="x")), rwhy)
    draft.fix(dict(rw, force=True, why=rwhy)); assert "room" in card(1)["marks"] and "room" in card(5)["marks"]

def test_a_teacher_who_breaks_a_must_rule_needs_force_with_the_rules_sentence():
    """the page's teacher list says why (the rule's sentence) and asks "Give it anyway?": the server makes the change only with force and that very sentence"""
    import copy
    sp = copy.deepcopy(SPEC); sp["rules"] = [dict(scope="School", target="Whole school", rule="Max periods in a row", number=1, strength="Must", week="Both", day="All")]
    assert c.put("/api/setup", json=sp).status_code == 200
    try:
        save_draft([dict(id=1, day=DAYS[0], p=L1, n=1, level=LEVEL, classes=[C1], subject=SUBJ, teachers=[TEACHERS[0]], room=ROOMS[0]),
                    dict(id=2, day=DAYS[0], p=L1 + 1, n=1, level=LEVEL, classes=[CLASSES[1]], subject=SUBJ2, teachers=[FREE], room=ROOMS[1])])   # FREE teaches the period after lesson 1
        assert next(x for x in draft.lesson(1)["teachers"] if x["name"] == FREE)["free"]   # no clash: the list offers them as free
        f = dict(kind="teacher", key=KEY1, teachers=[FREE]); why = None
        try: draft.fix(f)
        except ValueError as e: why = str(e)
        assert why and why.startswith("Rule School \u00b7 Whole school \u00b7 Max periods in a row: ") and FREE in why, why
        raises(ValueError, lambda: draft.fix(dict(f, force=True)), why); raises(ValueError, lambda: draft.fix(dict(f, force=True, why="Another reason.")), why); assert fixes_stored() == []
        j = draft.fix(dict(f, force=True, why=why)); assert len(j["fixes"]) == 1 and taught(1) == [[FREE]] and not {"force", "why"} & set(fixes_stored()[0])
        assert any(w["kind"] == "rule" and FREE in w["text"] for w in j["warnings"])   # the broken rule is then on the list of warnings
    finally:
        assert c.put("/api/setup", json=SPEC).status_code == 200; save_draft(TR)

def test_room_for_all_the_groups_lessons_is_one_undo():
    save_draft(TR); R = "1-03"; a = dict(kind="room", id=1, group=ENTIRE, room=R, all=True)
    j = draft.fix(a); fl = fixes_stored(); assert len(fl) == 2 and [f["id"] for f in fl] == [1, 6] and len({f["batch"] for f in fl}) == 1 and fl[0]["batch"]
    assert all(f["kind"] == "room" and f["group"] == ENTIRE and f["room"] == R and not {"all", "force", "why"} & set(f) for f in fl)
    assert fl[0]["text"] == f"{SUBJ} for {C1} on {DAYS[0]} period {L1} is now in {R}, not {ROOMS[0]}." and fl[1]["text"] == f"{SUBJ} for {C1} on {DAYS[3]} period {L1} is now in {R}, not {ROOMS[1]}."
    assert card(1)["rows"][0]["room"] == R and card(6)["rows"][0]["room"] == R and card(5)["rows"][0]["room"] == ROOMS[1]
    draft.undo(); assert fixes_stored() == [] and card(1)["rows"][0]["room"] == ROOMS[0] and card(6)["rows"][0]["room"] == ROOMS[1]   # one undo takes all
    draft.fix(dict(kind="lift", id=6)); draft.fix(a); assert [f["id"] for f in fixes_stored()] == [6, 1, 6] and len({f["batch"] for f in fixes_stored()[1:]}) == 1   # the lesson in the pool is in the batch
    assert card(1)["rows"][0]["room"] == R and draft._now()[2]["pool"][0]["room"] == R
    draft.undo(); assert len(fixes_stored()) == 1
    draft.undo(); rows = TR + [dict(id=10, day=DAYS[3], p=L1, n=1, level=LEVEL, classes=[C3], subject=SUBJ2, teachers=[FREE], room=R)]   # R is taken when lesson 6 is
    save_draft(rows); why = f"{R} is in use then."
    raises(ValueError, lambda: draft.fix(a), why); assert fixes_stored() == []   # lesson 1 would pass, lesson 6 refuses: nothing is stored
    raises(ValueError, lambda: draft.fix(dict(a, force=True, why="Another reason.")), why); raises(ValueError, lambda: draft.fix(dict(a, force=True)), why); assert fixes_stored() == []
    raises(ValueError, lambda: draft.fix(dict(a, force=True, why=why)), why); assert fixes_stored() == []   # a change of room for all the group's lessons never forces
    assert card(1)["rows"][0]["room"] == ROOMS[0] and card(6)["rows"][0]["room"] == ROOMS[1] and "room" not in card(6)["marks"]
    draft.fix(dict(kind="room", id=6, group=ENTIRE, room=R, force=True, why=why)); assert len(fixes_stored()) == 1 and "room" in card(6)["marks"]   # one lesson may still be forced
    draft.undo(); assert fixes_stored() == []
    draft.fix(dict(kind="room", id=1, group=ENTIRE, room="1-03", all=1)); assert len(fixes_stored()) == 1 and "batch" not in fixes_stored()[0]   # all only when exactly true
    raises(ValueError, lambda: draft.fix(dict(a, id=999)), NOT_FOUND); raises(ValueError, lambda: draft.fix(dict(a, group="G9")), "There is no row of G9 in that lesson.")
    raises(ValueError, lambda: draft.fix(dict(a, room="No Such Room")), "No Such Room is not on the setup's list of rooms.")

def test_none_for_a_teacher_is_critical_and_none_for_a_room_is_a_warning():
    fresh(CLEAN); j0 = draft.info(); assert j0["critical"] == 0
    j = draft.fix(dict(kind="teacher", key=KEY1, teachers=[])); assert fixes_stored()[-1]["text"].endswith(f"now has no teacher; it had {TEACHERS[0]}.")   # no force: it is never a clash
    assert "noteacher" in card(1)["marks"] and j["critical"] == j0["critical"] + 1, (j["critical"], card(1)["marks"])
    draft.undo(); assert draft.info()["critical"] == 0
    j = draft.fix(dict(kind="room", id=1, group=ENTIRE, room="")); assert "noroom" in card(1)["marks"] and j["critical"] == 0
    assert [w["strength"] for w in j["warnings"] if w["kind"] == "room"] == ["Prefer"]
    draft.fix(dict(kind="teacher", key=KEY1, teachers=[ZACH])); draft.fix(dict(kind="teacher", key=KEY1, teachers=[])); assert taught(1) == [[]]   # taking away a teacher who was put there

def test_a_lesson_with_no_teacher_reads_has_no_teacher_against_step_5():
    fresh(CLEAN); j = draft.fix(dict(kind="teacher", key=KEY1, teachers=[]))
    w = [x for x in j["warnings"] if x["key"].startswith("dep:") and x["key"].endswith(":teachers")]
    assert len(w) == 1 and w[0]["text"].endswith(f" has no teacher on the timetable; step 5 says {w[0]['sides']['step5']}.") and w[0]["sides"]["step5"], [x["text"] for x in w]
    assert "taught by  on" not in w[0]["text"]
    draft.fix(dict(kind="teacher", key=KEY1, teachers=[ZACH])); w = [x for x in draft.info()["warnings"] if x["key"].startswith("dep:") and x["key"].endswith(":teachers")]
    assert len(w) == 1 and w[0]["text"].endswith(f" is taught by {ZACH} on the timetable; step 5 says {w[0]['sides']['step5']}."), [x["text"] for x in w]   # a teacher named: the sentence as before

def test_the_lesson_route():
    save_draft(TR); r = c.get(f"/api/draft/lesson?id={PLAIN_ID}"); assert r.status_code == 200 and r.get_json() == draft.lesson(PLAIN_ID) and "Content-Encoding" not in r.headers
    save_draft(PLAY); r = c.get(f"/api/draft/lesson?id={BAND_ID}&group=G2"); assert r.status_code == 200 and r.get_json() == draft.lesson(BAND_ID, "G2") and r.get_json()["group"] == "G2"
    r = c.get("/api/draft/lesson"); assert r.status_code == 400 and r.get_json() == {"error": "Say which lesson."}
    r = c.get("/api/draft/lesson?id=999999"); assert r.status_code == 400 and r.get_json() == {"error": NOT_FOUND}
    r = c.get(f"/api/draft/lesson?id={BAND_ID}&group=G9"); assert r.status_code == 400 and r.get_json() == {"error": "There is no row of G9 in that lesson."}
    assert NOSE.get(f"/api/draft/lesson?id={PLAIN_ID}").status_code == 401
    shutil.rmtree(draft.DIR); r = c.get(f"/api/draft/lesson?id={PLAIN_ID}"); assert r.status_code == 404 and r.get_json() == {"error": "There is no draft."}
    assert NOSE.get(f"/api/draft/lesson?id={PLAIN_ID}").status_code == 401

def test_a_teacher_of_the_subjects_department_on_no_lesson_of_its_card_is_rank_two():
    save_draft(TR); m = draft._now()[0]; spec = m["checked_setup"]; real = draft._now
    teach = [dict(t) for t in spec["teachers"]] + [dict(name="Floating Teacher", dept="EL", dept2=None)]
    try:
        draft._now = lambda: (dict(m, checked_setup=dict(spec, teachers=teach)), None, dict(pool=[]))
        T = by_name(draft.lesson(PLAIN_ID))
        assert (T["Floating Teacher"]["rank"], T["Floating Teacher"]["free"]) == (2, True) and T["Jasper Wong"]["rank"] == 1 and T[ZACH]["rank"] == 3 and T[SABRINA]["rank"] == 0
        names = [x["name"] for x in draft.lesson(PLAIN_ID)["teachers"] if x["free"]]; assert names.index("Jasper Wong") < names.index("Floating Teacher") < names.index(FREE)   # by rank among the free
    finally: draft._now = real

def test_a_class_home_room_is_right_when_step_5_asks_for_another_kind():
    art = dict(id=20, day=DAYS[2], p=L1, n=1, level=LEVEL, classes=[C1], subject="Art", teachers=[TEACHERS[1]], room="Art Room")
    save_draft(TR + [art]); j = draft.lesson(20); R = by_name(j, "rooms", "room"); home = str(draft._now()[0]["class_ix"][C1]["home"]); assert home == "1-01"
    assert R["Art Room"]["right"] and R[home]["right"] and R[home]["kind"] == "classroom"   # the kind step 5 asks for, and the class's own room
    assert not R["1-02"]["right"] and not R["Science Room 1"]["right"] and not R[HALL]["right"]
    assert [r["room"] for r in j["rooms"]][:2] == [home, "Art Room"]   # free and right first, in the setup's order

def test_a_room_is_free_when_a_room_fix_would_not_be_refused():
    def at(i): return next(x for x in draft._now()[0]["lessons"] if x["id"] == i)
    band = [dict(id=11, day=DAYS[0], p=L1, n=1, classes=[C3], subject=SUBJ2, group="G1", teachers=[ZACH], room=HALL, **BAND),
            dict(id=11, day=DAYS[0], p=L1, n=1, classes=["1D"], subject=SUBJ, group="G2", teachers=[FREE], room=HALL, **BAND)]
    save_draft([x for x in TR if x["id"] != 8] + band); R = by_name(draft.lesson(PLAIN_ID), "rooms", "room")
    assert R[HALL] == dict(room=HALL, kind="pe venue", right=False, free=False, holding="group G1"), R[HALL]   # one lesson, two rows: the Hall is full
    raises(ValueError, lambda: draft.fix(dict(kind="room", id=1, group=ENTIRE, room=HALL)), f"{HALL} is in use then.")
    rain = dict(id=12, day=DAYS[0], p=L1, n=1, level=LEVEL, classes=[C3], subject=SUBJ2, teachers=[ZACH], room="1-03", rain="Science Room 2")
    save_draft(TR + [rain]); R = by_name(draft.lesson(PLAIN_ID), "rooms", "room")
    assert R["Science Room 2"] == dict(room="Science Room 2", kind="science room", right=False, free=False, holding=W8), R["Science Room 2"]   # another lesson's rain room
    raises(ValueError, lambda: draft.fix(dict(kind="room", id=1, group=ENTIRE, room="Science Room 2")), "Science Room 2 is in use then.")
    assert R[ROOMS[0]]["free"] and R["Science Room 1"]["free"] and R["Field"]["free"]
    own = dict(rain, id=1, classes=[C1], subject=SUBJ, teachers=[TEACHERS[0]], room=ROOMS[0], rain="Science Room 2")   # its own rain room is no obstacle
    save_draft([own] + [x for x in TR if x["id"] != 1]); R = by_name(draft.lesson(1), "rooms", "room"); assert R["Science Room 2"]["free"] and R["Science Room 2"]["holding"] == ""
    save_draft(TR); assert all(r["free"] == (r["holding"] == "") for r in draft.lesson(PLAIN_ID)["rooms"])

def test_a_room_change_that_changes_nothing_is_not_stored():
    S = "That changes nothing."; save_draft(TR + [dict(id=13, day=DAYS[1], p=L1, n=1, level=LEVEL, classes=[C3], subject=SUBJ2, teachers=[ZACH])])
    f = dict(kind="room", id=1, group=ENTIRE, room=ROOMS[0])
    raises(ValueError, lambda: draft.fix(f), S); raises(ValueError, lambda: draft.fix(dict(f, force=True, why=S)), S)
    raises(ValueError, lambda: draft.fix(dict(kind="room", id=13, group=ENTIRE, room="")), S)   # a row with no room, to none
    assert fixes_stored() == []
    draft.fix(dict(f, room="")); assert card(1)["rows"][0]["room"] == "" and len(fixes_stored()) == 1   # a real change is still made
    r = c.post("/api/draft/fix", json=dict(kind="room", id=1, group=ENTIRE, room="")); assert r.status_code == 400 and r.get_json() == {"error": S} and len(fixes_stored()) == 1
    draft.undo(); R = "1-03"; a = dict(kind="room", id=1, group=ENTIRE, room=R, all=True)
    draft.fix(dict(kind="room", id=6, group=ENTIRE, room=R)); draft.fix(a); fl = fixes_stored()   # lesson 6 is in R already: only lesson 1 is changed
    assert [x["id"] for x in fl] == [6, 1] and "batch" in fl[1] and card(1)["rows"][0]["room"] == R and card(6)["rows"][0]["room"] == R
    raises(ValueError, lambda: draft.fix(a), S); raises(ValueError, lambda: draft.fix(dict(a, force=True, why=S)), S); assert len(fixes_stored()) == 2
    draft.undo(); draft.undo(); draft.fix(dict(kind="lift", id=6)); draft.fix(dict(kind="room", id=6, group=ENTIRE, room=R)); draft.fix(a)   # a lesson waiting in Not placed is judged the same way
    assert [x["id"] for x in fixes_stored()] == [6, 6, 1] and draft._now()[2]["pool"][0]["room"] == R
    raises(ValueError, lambda: draft.fix(a), S); raises(ValueError, lambda: draft.fix(dict(kind="room", id=6, group=ENTIRE, room=R)), S); assert len(fixes_stored()) == 3

def test_the_place_route_and_the_slots_route_agree_with_the_draft():
    fresh(); s = draft.slots(PLAIN_ID)["slots"]; x = next(x for x in s if x["there"]); d, p = x["d"], x["p"]
    assert x["there"][0]["id"] == OTHER_ID and (d, p) == O0 and x["swap"] == OTHER_ID
    r = c.get(f"/api/draft/place?id={PLAIN_ID}&d={d}&p={p}"); j = r.get_json()
    assert r.status_code == 200 and j == draft.place(PLAIN_ID, d, p) and set(j) == {"d", "p", "state", "why", "swap", "also", "push", "beside"} and j["push"]["out"] == x["there"] and j["beside"]["state"] in ("ok", "prefer", "no", "na")
    assert {k: j[k] for k in x if k != "there"} == {k: x[k] for k in x if k != "there"}
    free = next(y for y in s if y["there"] is None); j = c.get(f"/api/draft/place?id={PLAIN_ID}&d={free['d']}&p={free['p']}").get_json()
    assert j["push"] is None and j["beside"] is None and j["state"] == free["state"]
    say = lambda url, code, text: (lambda r: r.status_code == code and r.get_json() == {"error": text})(c.get(url))
    assert say("/api/draft/place", 400, "Say which lesson.") and say(f"/api/draft/place?d=0&p=0", 400, "Say which lesson.")
    for q in ("", "&d=0", "&p=0", "&d=x&p=0", "&d=0&p=1.5", "&d=&p=", "&d=0&p="): assert say(f"/api/draft/place?id={PLAIN_ID}{q}", 400, "Say which place."), q
    assert say("/api/draft/place?id=999999&d=0&p=0", 400, NOT_FOUND) and say("/api/draft/place?id=x&d=0&p=0", 400, NOT_FOUND)
    for q in (f"d={len(DAYS)}&p=0", f"d=0&p={NPD}", "d=-1&p=0", "d=0&p=-1"): assert say(f"/api/draft/place?id={PLAIN_ID}&{q}", 400, "That is outside the day."), q
    url = f"/api/draft/place?id={PLAIN_ID}&d=0&p=0"; assert "Content-Encoding" not in c.get(url).headers
    draft.fix(dict(kind="lift", id=PLAIN_ID)); j = c.get(f"/api/draft/place?id={PLAIN_ID}&d={O0[0]}&p={O0[1]}").get_json()   # a waiting lesson: a place
    assert j["swap"] is None and j["push"]["out"][0]["id"] == OTHER_ID
    assert NOSE.get(url).status_code == 401
    shutil.rmtree(draft.DIR); r = c.get(url); assert r.status_code == 404 and r.get_json() == {"error": "There is no draft."}; assert NOSE.get(url).status_code == 401

def test_an_empty_group_in_the_lesson_route_is_no_group():
    save_draft(PLAY); a = c.get(f"/api/draft/lesson?id={BAND_ID}&group=").get_json(); assert a == draft.lesson(BAND_ID) and a["group"] == "G1"
    assert c.get(f"/api/draft/lesson?id={PLAIN_ID}&group=").get_json() == draft.lesson(PLAIN_ID)

def test_who_is_much_quicker_than_the_push_and_the_place_beside():
    cl = [x["class"] for x in SPEC["classes"] if x["level"] == LEVEL]   # classes of the setup, so its rules bear on every lesson
    rows = [dict(id=i + 1, day=DAYS[i % len(DAYS)], p=(i // len(DAYS)) % NPD, n=1, level=LEVEL, classes=[cl[i % len(cl)]], subject=(SUBJ, SUBJ2)[i % 2], teachers=[TEACHERS[i % 3]]) for i in range(2000)]
    for i in range(len(DAYS) * 4): rows[i] = dict(rows[i], classes=[cl[0]], day=DAYS[i % len(DAYS)], p=i // len(DAYS))   # lesson 1 is of cl[0], which has four lessons on every day
    save_draft(rows); m, rec, fx = draft._now(); spec, days = m["checked_setup"], m["days"]
    best = lambda f: min((lambda t0: (f(), time.time() - t0)[1])(time.time()) for _ in range(3))
    who = best(lambda: draft.slots(1)); full = best(lambda: fixes_mod.slots(m, spec, days, 1, fx["pool"], extras=True))
    s = draft.slots(1)["slots"]; print(f"slots of 2,000 rows: who {who:.3f} s (draft.slots), push and beside {full:.3f} s")
    assert len({x["d"] for x in s if x["there"]}) == len(DAYS) and sum(1 for x in s if x["there"]) >= 15, "many places have a lesson of the class"
    assert who < full / 3, (who, full)

def test_the_board_of_two_thousand_rows_is_quick_and_small():
    rows = [dict(id=i + 1, day=DAYS[i % len(DAYS)], p=(i // len(DAYS)) % NPD, n=1, level=LEVEL, classes=[f"T{i % 32 + 1:02d}"], subject=(SUBJ, SUBJ2)[i % 2], teachers=[TEACHERS[i % 3]]) for i in range(2000)]
    save_draft(rows); draft._now()   # the model is built once and kept: the time is the board's own
    t0 = time.time(); b = draft.board(); placed(b); took = time.time() - t0
    assert len(b["cards"]) == 2000 and took < 1, took
    size = len(gzip.compress(json.dumps(b).encode()))
    assert size < 200000, size
    r = c.get("/api/draft/board", headers={"Accept-Encoding": "gzip"}); assert r.status_code == 200 and len(r.get_data()) < 200000

def test_two_bands_at_once_is_one_critical_warning_and_a_mark_on_both_cards():
    bx, by = f"{LEVEL} Band X", f"{LEVEL} Band Y"; one = [CLASSES[0]]
    spec = dict(SPEC, blocks=list(SPEC.get("blocks") or []) + [dict(block=bx, level=LEVEL, classes=one), dict(block=by, level=LEVEL, classes=one)])
    assert c.put("/api/setup", json=dict(spec=spec, why="two bands")).status_code == 200
    try:
        g = lambda i, day, blk, code, tch: dict(id=i, day=day, p=0, n=1, level=LEVEL, block=blk, classes=one, subject=SUBJ, group=code, teachers=[tch], room="TBC")
        save_draft([g(1, DAYS[0], bx, "X1", TEACHERS[0]), g(1, DAYS[0], bx, "X2", TEACHERS[1]), g(2, DAYS[0], by, "Y1", TEACHERS[2]), g(3, DAYS[1], by, "Y2", TEACHERS[2])])
        j = draft.info(); ws = [w for w in j["warnings"] if w["key"].startswith("clash:bands:")]
        assert len(ws) == 1 and ws[0]["crit"] == "class" and j["critical"] >= 1, [w["text"] for w in j["warnings"]]
        assert ws[0]["text"].startswith("Two bands at the same time: ") and f"on {DAYS[0]} period 0." in ws[0]["text"] and f"Every student of {CLASSES[0]} is in both" in ws[0]["text"], ws[0]["text"]
        assert ws[0]["where"]["cls"] == CLASSES[0] and ws[0]["where"]["id"] in (1, 2)
        b = board(); marks = {x["id"]: x["marks"] for x in b["cards"]}
        assert "class" in marks[1] and "class" in marks[2] and "class" not in marks[3], marks
        assert all("out" not in x for x in b["cards"])   # none is outside the day
        save_draft([g(1, DAYS[0], bx, "X1", TEACHERS[0]), g(4, DAYS[3], bx, "X2", TEACHERS[1]), g(2, DAYS[0], by, "Y1", TEACHERS[2]), g(3, DAYS[1], by, "Y2", TEACHERS[2])])
        j = draft.info(); ws = [w for w in j["warnings"] if w["key"].startswith(("clash:bands:", "bands:beside:"))]   # one group of each: perhaps different students
        assert len(ws) == 1 and ws[0]["key"].startswith("bands:beside:") and ws[0]["crit"] == "" and ws[0]["strength"] == "Prefer", ws
        assert "(1 of its 2 groups)" in ws[0]["text"] and ws[0]["text"].startswith("Two bands share a period: ") and f"on {DAYS[0]} period 0, for {CLASSES[0]}." in ws[0]["text"], ws[0]["text"]
        assert all("class" not in x["marks"] for x in board()["cards"])
    finally:
        assert c.put("/api/setup", json=dict(spec=SPEC, why="back")).status_code == 200; save_draft(ROWS)

def test_a_setup_with_rows_not_filled_in_still_takes_a_timetable():
    """step 5's "+ Add teaching group" leaves a row with no subject, saved with few fields or none: an upload used to fail on it ("Could not read the files: 'subject'")"""
    from ttgen import spec as spec_mod
    rows = [{}, {"level": LEVEL}, {"level": LEVEL, "classes": [CLASSES[0]]}, {"subject": SUBJ}]   # the last names a subject and nothing else
    assert [sorted(x) for x in spec_mod.filled_lessons(rows + [None, "x"])] == [["block", "classes", "level", "subject", "teachers"]] and spec_mod.filled_lessons(None) == []
    assert c.put("/api/setup", json=dict(spec=dict(SPEC, lessons=list(SPEC["lessons"]) + rows), why="rows not filled in")).status_code == 200
    try:
        save_draft(ROWS); j = draft.info(); b = board()
        assert j["lessons"] == len({x["id"] for x in ROWS}) and len(b["cards"]) == j["lessons"]
        assert len(draft.model_now()[0]["checked_setup"]["lessons"]) == len(SPEC["lessons"]) + 1   # the three with no subject are left out of the copy the timetable is checked against
        assert len(c.get("/api/setup").get_json()["spec"]["lessons"]) == len(SPEC["lessons"]) + 4   # and stay on step 5 for the committee to fill in or delete
        assert c.get("/draft/preview").status_code == 200 and draft.slots(PLAIN_ID)["slots"]
    finally:
        assert c.put("/api/setup", json=dict(spec=SPEC, why="back")).status_code == 200; save_draft(ROWS)

def test_a_group_with_an_emptied_teacher_box_still_takes_a_timetable():
    """step 5's Table view keeps a teacher box that was emptied as an empty place in the row's list (["Mdm Lee", null]); the workbook leaves empty
    cells out. An upload used to fail on such a row of a band ("Could not check the timetable against the setup: '<' not supported between instances
    of 'str' and 'NoneType'"), and so did everything else on step 8"""
    import copy
    from ttgen import reader, spec as spec_mod
    f = spec_mod.filled_lessons
    assert [x["teachers"] for x in f([{"subject": SUBJ, "teachers": v} for v in (["A", None], [None, "A"], [None], ["", "A", "  "], None, "A", ["A", "B"])])] \
        == [["A"], ["A"], [], ["A"], [], [], ["A", "B"]]
    given = [{"subject": SUBJ, "teachers": ["A", None]}]; f(given); assert given[0]["teachers"] == ["A", None]   # the setup it was given is not changed
    d = copy.deepcopy(SPEC); reader.derive(d)
    i = next(i for i, x in enumerate(d["lessons"]) if x.get("block") and x.get("teachers") and x.get("periods")); g = d["lessons"][i]; T = g["teachers"][0]
    rows = [dict(id=1, day=DAYS[0], p=0, n=1, level=g["level"], block=g["block"], classes=g["classes"], subject=g["subject"], group=g["code"], teachers=list(g["teachers"]))]
    key = f"dep:G:{g['code']}:teachers"
    upload = lambda rows: c.post("/api/draft", data=dict(setup=(io.BytesIO(setup_bytes(SPEC)), "setup.xlsx"), timetable=(io.BytesIO(workbook(rows)), "timetable.xlsx"), replace="1"), content_type="multipart/form-data")
    try:
        for v in ([T, None], [None, T], [T, ""], [None, None, T]):
            spec = copy.deepcopy(SPEC); spec["lessons"][i]["teachers"] = v + list(g["teachers"][1:])
            assert c.put("/api/setup", json=dict(spec=spec, why="an emptied teacher box")).status_code == 200
            r = upload(rows); assert r.status_code == 200, r.get_json()
            j = draft.info(); assert j["lessons"] == 1 and not any(w["key"] == key for w in j["warnings"]), v   # its teachers are step 5's: no warning says otherwise
            assert board()["cards"] and c.get("/api/compare?a=draft&b=draft").status_code == 200
            assert c.get("/api/setup").get_json()["spec"]["lessons"][i]["teachers"][:len(v)] == v   # step 5 keeps the row as it was typed
        spec = copy.deepcopy(SPEC); spec["lessons"][i]["teachers"] = [None]   # every box emptied: the group has no teacher, and the timetable names one
        assert c.put("/api/setup", json=dict(spec=spec, why="no teacher")).status_code == 200
        r = upload(rows); assert r.status_code == 200, r.get_json()
        w = next(w for w in draft.info()["warnings"] if w["key"] == key); assert "None" not in w["text"], w["text"]
    finally:
        assert c.put("/api/setup", json=dict(spec=SPEC, why="back")).status_code == 200; save_draft(ROWS)

def test_the_preview_is_the_draft_as_the_published_page_would_show_it():
    import re
    fresh()
    r = NOSE.get("/draft/preview"); assert r.status_code == 302 and r.headers["Location"].endswith("/login")   # the committee only
    r = c.get("/draft/preview"); html = r.get_data(as_text=True); assert r.status_code == 200 and r.mimetype == "text/html"
    data = json.loads(re.search(r"<script>const DATA = (.*?);</script>", html, re.S).group(1).replace("<\\/", "</"))
    m = draft._now()[0]; assert sorted({x[0] for x in data["lessons"]}) == sorted({x["id"] for x in m["lessons"]}) and data["lessons"]   # the draft's lessons, as they are now
    app_cfg = data["app"]; assert app_cfg["pdf"] is False and app_cfg["files"] == [] and app_cfg["tabs"] is None and app_cfg["home"] == "/" and app_cfg["mode"] == "committee"   # nothing on it leads to the published files
    assert app_cfg["banner"].startswith("Preview: this is the draft as it stands, not the published timetable.") and "Not placed" not in app_cfg["banner"]
    assert "Preview" in re.search(r"<title>(.*?)</title>", html, re.S).group(1)
    n = len({x[0] for x in data["lessons"]}); draft.fix(dict(kind="lift", id=PLAIN_ID))   # a lesson lifted out is not on the page, and the banner says so
    data = json.loads(re.search(r"<script>const DATA = (.*?);</script>", c.get("/draft/preview").get_data(as_text=True), re.S).group(1).replace("<\\/", "</"))
    assert len({x[0] for x in data["lessons"]}) == n - 1 and "1 lesson waiting in Not placed is not on it." in data["app"]["banner"] and "critical mistake" in data["app"]["banner"]
    assert store.published() is None   # looking at the preview publishes nothing
    shutil.rmtree(draft.DIR)
    r = c.get("/draft/preview"); assert r.status_code == 404 and "There is no draft" in r.get_data(as_text=True)

def test_a_trade_is_one_fix_judged_as_a_whole_never_forced_and_undone_at_once():
    T0, T1 = TEACHERS[0], TEACHERS[1]; ka, kb = f"C:{CLASSES[0]}:{SUBJ}", f"C:{CLASSES[1]}:{SUBJ}"
    rows = [dict(id=1, day=DAYS[0], p=L1, n=1, level=LEVEL, classes=[CLASSES[0]], subject=SUBJ, teachers=[T0], room=ROOMS[0]),
            dict(id=2, day=DAYS[1], p=L1, n=1, level=LEVEL, classes=[CLASSES[1]], subject=SUBJ, teachers=[T1], room=ROOMS[1])]
    save_draft(rows); f = dict(kind="trade", a=ka, b=kb, x=T0, y=T1)
    sentence = f"{T0} and {T1} traded: {T0} now teaches {SUBJ} for {CLASSES[1]}, {T1} {SUBJ} for {CLASSES[0]}."
    r = c.post("/api/draft/fix", json=f); assert r.status_code == 200, r.get_json()
    assert [(x["kind"], x["text"]) for x in fixes_stored()] == [("trade", sentence)] and [x["kind"] for x in c.get("/api/draft").get_json()["fixes"]] == ["trade"]
    assert set(fixes_stored()[0]) == {"kind", "a", "b", "x", "y", "at", "text"} and taught(1) == [[T1]] and taught(2) == [[T0]]
    assert draft.model_now()[2]["texts"][-1] == sentence   # what the published timetable's record of changes is written from
    assert c.post("/api/draft/undo").status_code == 200 and fixes_stored() == [] and taught(1) == [[T0]] and taught(2) == [[T1]]   # one undo takes it back
    assert "trade" not in draft.FORCED and draft.FIELDS["trade"] == ("a", "b", "x", "y")
    raises(ValueError, lambda: draft.fix(dict(f, x=5)), "The fix is not complete.")
    save_draft(rows + [dict(id=3, day=DAYS[0], p=L1, n=1, level=LEVEL, classes=["1C"], subject=SUBJ2, teachers=[T1], room=ROOMS[2 % len(ROOMS)])])   # T1 is with 1C when 1A meets
    why = f"{T1} is teaching {SUBJ2} for 1C then."; raises(ValueError, lambda: draft.fix(f), why)
    r = c.post("/api/draft/fix", json=dict(f, force=True, why=why)); assert r.status_code == 400 and r.get_json() == {"error": why} and fixes_stored() == []   # force is not heard

def test_the_stamp_moves_with_every_change_to_the_draft():
    fresh(CLEAN); a = draft.info()["stamp"]; assert len(a) == 12 and int(a, 16) >= 0 and c.get("/api/draft").get_json()["stamp"] == a == draft.stamp() and draft.info()["stamp"] == a
    draft.fix(dict(kind="lift", id=1)); b = draft.info()["stamp"]; assert b != a
    draft.undo(); assert draft.info()["stamp"] != b   # the undo is a change too
    fresh(CLEAN); assert draft.info()["stamp"] != a   # the same files uploaded again are a new draft
    rec = store.setup_record(); assert draft.stamp(rec=dict(rec, v=rec["v"] + 1)) != draft.stamp()   # and a new setup version

def test_a_change_asked_for_a_timetable_that_moved_on_is_refused():
    fresh(CLEAN); old = draft.info()["stamp"]; assert draft.fix(dict(kind="lift", id=1))["stamp"] != old; n = len(fixes_stored()); sent = dict(kind="lift", id=2)
    for r in (c.post("/api/draft/fix", json=dict(sent, stamp=old)), c.post("/api/draft/fixes", json=dict(fixes=[sent], stamp=old))): assert r.status_code == 400 and r.get_json() == {"error": draft.MOVED}, r.get_json()
    assert draft.MOVED == "The timetable changed. Ask again." and len(fixes_stored()) == n
    raises(ValueError, lambda: draft.fix(sent, stamp=old), draft.MOVED); raises(ValueError, lambda: draft.fix_many([sent], stamp=old), draft.MOVED)
    now = draft.info()["stamp"]; r = c.post("/api/draft/fix", json=dict(sent, stamp=now)); assert r.status_code == 200 and len(fixes_stored()) == n + 1
    fresh(CLEAN)
    s = draft.info()["stamp"]; r = c.post("/api/draft/fix", json=dict(kind="lift", id=1, stamp=12)); assert r.status_code == 200 and fixes_stored()[-1]["kind"] == "lift"   # a stamp that is not text is not a stamp
    assert s != draft.info()["stamp"]
    r = c.post("/api/draft/fix", json=dict(kind="lift", id=2)); assert r.status_code == 200   # no stamp: as before
    fresh(CLEAN); r = c.post("/api/draft/fixes", json=dict(fixes=[dict(kind="move", id=1, d=1, p=L1 + 1)])); assert r.status_code == 200   # no stamp: as before
    fresh(CLEAN); r = c.post("/api/draft/fixes", json=dict(fixes=[dict(kind="move", id=1, d=1, p=L1 + 1)], stamp=draft.info()["stamp"])); assert r.status_code == 200   # the current one
    assert c.post("/api/draft/fixes", json=dict(fixes=[dict(kind="move", id=2, d=2, p=L1)], stamp="0" * 12)).status_code == 400 and len(fixes_stored()) == 1

def _week(j, cls): return next(g for g in j["classes"] if g["name"] == cls)
def _row(j, cls, i): return next(r for r in _week(j, cls)["lessons"] if r["id"] == i)

def test_a_preview_of_a_place_shows_the_lesson_back_on_its_class_week():
    fresh(CLEAN); draft.fix(dict(kind="lift", id=1)); at = (0, L1 + 1); n = len(fixes_stored())
    j = draft.preview([dict(kind="place", id=1, d=at[0], p=at[1])]); assert j["state"] == "ok" and j["why"] == "" and len(j["texts"]) == 1 and j["texts"][0].startswith("Placed "), j
    r = _row(j, CLASSES[0], 1); assert (r["d"], r["p"], r["mark"]) == (at[0], at[1], "moved") and r["was"] == dict(d=0, p=L1) and j["gone"] == []
    j2 = c.post("/api/draft/preview", json=dict(fixes=[dict(kind="place", id=1, d=at[0], p=at[1])])).get_json(); assert j2 == j
    assert len(fixes_stored()) == n and board()["unplaced"][0]["id"] == 1   # nothing was kept, and the lesson still waits
    j = draft.preview([dict(kind="place", id=1, d=0, p=NPD + 5)]); assert j["state"] == "na" and j["why"] and j["texts"] == [] and not any(r["mark"] for g in j["classes"] for r in g["lessons"]) and j["gone"] == []   # nothing changed

def test_a_preview_of_a_change_that_lands_with_a_problem_shows_it_made():
    T0, T1 = TEACHERS[0], TEACHERS[1]
    fresh(CLEAN + [dict(id=3, day=DAYS[0], p=L1, n=1, level=LEVEL, classes=["1C"], subject=SUBJ2, teachers=[CLEAN[1]["teachers"][0]], room=ROOMS[0])]); why = f"{T1} is teaching {SUBJ2} for 1C then."
    j = draft.preview([dict(kind="move", id=2, d=0, p=L1)]); assert j["state"] == "no" and j["why"] == why, j
    r = _row(j, CLASSES[1], 2); assert (r["d"], r["p"], r["mark"]) == (0, L1, "moved") and r["was"] == dict(d=1, p=L1) and len(j["texts"]) == 1
    raises(ValueError, lambda: draft.fix(dict(kind="move", id=2, d=0, p=L1)), why)   # making it is still refused
    j = draft.preview([dict(kind="move", id=2, d=0, p=L1), dict(kind="move", id=1, d=2, p=L1)]); assert j["state"] == "no" and j["why"] == why and j["texts"] == []   # two fixes: as before, the timetable up to the one refused
    j = draft.preview([dict(kind="move", id=1, d=0, p=L1)]); assert j["state"] == "na" and j["why"] == "That changes nothing." and j["texts"] == []

def test_a_preview_of_a_trade_shows_both_classes_changed():
    T0, T1 = TEACHERS[0], TEACHERS[1]; ka, kb = f"C:{CLASSES[0]}:{SUBJ}", f"C:{CLASSES[1]}:{SUBJ}"
    fresh([dict(id=1, day=DAYS[0], p=L1, n=1, level=LEVEL, classes=[CLASSES[0]], subject=SUBJ, teachers=[T0], room=ROOMS[0]),
           dict(id=2, day=DAYS[1], p=L1, n=1, level=LEVEL, classes=[CLASSES[1]], subject=SUBJ, teachers=[T1], room=ROOMS[1])])
    j = draft.preview([dict(kind="trade", a=ka, b=kb, x=T0, y=T1)]); assert j["state"] == "ok" and len(j["texts"]) == 1 and j["texts"][0].startswith(f"{T0} and {T1} traded"), j
    assert sorted(g["name"] for g in j["classes"]) == sorted(CLASSES) and _row(j, CLASSES[0], 1)["mark"] == "changed" and _row(j, CLASSES[1], 2)["mark"] == "changed"
    assert _row(j, CLASSES[0], 1)["teachers"] == [T1] and _row(j, CLASSES[1], 2)["teachers"] == [T0] and fixes_stored() == [] and taught(1) == [[T0]]

if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for f in tests: f()
    print(f"{len(tests)} checks passed")

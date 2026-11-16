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
        ws.append([r["id"], r["day"], r["p"], r["p"] + r["n"] - 1, r["n"], "", "", r["level"], r.get("block", ""), ", ".join(r["classes"]), r["subject"], r.get("group", "Entire Class"), ", ".join(r.get("teachers", [])), r.get("room", ""), "", ""])
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
    b, o = draft.slots(PLAIN_ID), draft.options(PLAIN_ID); bare = lambda s: {k: v for k, v in s.items() if k not in ("push", "beside")}
    assert [bare(s) for s in b["slots"]] == o["slots"] and b["delete"] == o["delete"] and b["id"] == PLAIN_ID
    assert all(set(s) == {"d", "p", "state", "why", "swap", "also", "push", "beside"} for s in b["slots"])   # the board's own: with the push and the place beside
    assert all(set(s) == {"d", "p", "state", "why", "swap", "also"} for s in o["slots"])   # the Fix card's: as before this stage
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
    assert s["id"] == PLAIN_ID and len(s["slots"]) == len(DAYS) * NPD and all(x["swap"] is None for x in s["slots"]) and {"d", "p", "state", "why", "push"} <= set(s["slots"][0])
    assert next(x for x in s["slots"] if (x["d"], x["p"]) == O0)["push"]["out"] == [dict(id=OTHER_ID, what=f"{SUBJ2} for {CLASSES[0]}", classes=[CLASSES[0]], groups=1)]
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
    r = c.post("/api/draft/preview", json=dict(fixes=[dict(kind="place", id=PLAIN_ID, d=0, p=L1)])); assert r.status_code == 400 and r.get_json() == {"error": "This kind of fix is not known."}
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
    assert s["push"]["out"] == [dict(id=BAND_ID, what="the Band A band", classes=CLASSES, groups=3)], s["push"]
    forced(move(PLAIN_ID, B0, push=True)); assert fixes_stored()[-1]["text"].endswith(" Pushed out: the Band A band."), fixes_stored()[-1]["text"]

def test_marks_on_the_board_of_a_clean_draft_are_empty():
    fresh(CLEAN); b = board(); assert [x["marks"] for x in b["cards"]] == [[], []] and [x["why"] for x in b["cards"]] == ["", ""] and b["unplaced"] == []
    assert isinstance(b["short"], list) and all("classes" in s for s in b["short"])
    fresh(); assert "noteacher" in card(OTHER_ID)["marks"] and "noroom" in card(OTHER_ID)["marks"] and card(PLAIN_ID)["marks"] == []

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

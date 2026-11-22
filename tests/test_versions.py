"""Plain-assert tests for reading and checking any draft folder: .venv/bin/python tests/test_versions.py"""
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

from ttgen.export import model_from_files  # noqa: E402

def one_fix():
    """a move of the plain lesson to some place the server judges clean"""
    for d in range(len(DAYS)):
        for p in range(NPD):
            try: draft.fix(dict(kind="move", id=PLAIN_ID, d=d, p=p)); return
            except ValueError: continue
    raise AssertionError("no place to move to")

def copy_of_draft():
    dst = os.path.join(tempfile.mkdtemp(), "copy"); shutil.copytree(draft.DIR, dst); return dst

def test_checked_in_matches_the_draft():
    save_draft(ROWS); one_fix()
    j = c.get("/api/draft").get_json()
    want = dict(critical=j["critical"], warnings=sum(1 for w in j["warnings"] if not w["decision"] and not w.get("crit")))
    assert draft.checked_in(draft.DIR) == want, (draft.checked_in(draft.DIR), want)

def test_model_in_reads_a_copied_folder():
    save_draft(ROWS); cp = copy_of_draft(); before = draft.model_now()[0]["lessons"]
    one_fix()
    after = draft.model_now()[0]["lessons"]; assert after != before
    assert draft.model_in(cp)[0]["lessons"] == before and draft.model_in(draft.DIR)[0]["lessons"] == after
    assert draft.model_in(cp)[2]["pool"] == [] and draft.model_in(cp)[0]["pool"] == []

def test_tally_is_what_finish_counts():
    save_draft(ROWS); ws = draft.info()["warnings"]; assert ws
    ws = [{k: v for k, v in w.items() if k != "decision"} for w in ws]
    base = draft.tally(ws, {}); assert base["open"] == len(ws)
    plain = next(w for w in ws if not w.get("crit"))
    assert draft.tally(ws, {plain["key"]: dict(answer="met")})["open"] == base["open"] - 1
    assert draft.tally(ws, {plain["key"]: dict(answer="left")})["open"] == base["open"]   # "left" is dropped
    assert draft.tally(ws, {"gone:key": dict(answer="met")})["open"] == base["open"]      # a decision with no warning is dropped
    assert draft.tally(ws, {plain["key"]: dict(answer="met"), "gone:key": dict(answer="met"), "s": dict(answer="step5")})["decisions"].keys() == {plain["key"], "s"}   # the kept decisions are what _finish saves
    assert draft.tally(ws, {})["critical"] == sum(1 for w in ws if w.get("crit")) == draft.info()["critical"]

def test_database_of_a_folder():
    save_draft(ROWS); cp = copy_of_draft(); one_fix()
    spec = store.setup_record()["spec"]; p = os.path.join(tempfile.mkdtemp(), "t.db")
    draft.database(p, folder=cp)
    got = model_from_files(None, p, spec=spec)
    at = lambda m: sorted((x["id"], x["d"], x["p"]) for x in m["lessons"])
    assert at(got) == at(draft.model_in(cp)[0]) and at(got) != at(draft.model_now()[0])

if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for f in tests: f()
    print(f"{len(tests)} checks passed")

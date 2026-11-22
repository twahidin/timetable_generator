"""Plain-assert tests for reading and checking any draft folder: .venv/bin/python tests/test_versions.py"""
import gzip, io, json, os, secrets, shutil, sys, tempfile, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = tempfile.mkdtemp()
CODE = secrets.token_hex(4)
os.environ.pop("HEADS_CODE", None)
os.environ.update(DATA_DIR=DATA, SECRET_KEY=secrets.token_hex(16), AI_PROVIDER="anthropic", AI_API_KEY="", COMMITTEE_CODE=CODE, TEACHER_CODE=secrets.token_hex(4), STUDENT_CODE=secrets.token_hex(4))
sys.path.insert(0, ROOT)
import openpyxl  # noqa: E402
import app as A, draft, fixes as fixes_mod, store, versions  # noqa: E402
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

def lift_one():
    draft.fix(dict(kind="lift", id=OTHER_ID))

def a_decision():
    """write one decision straight into the draft's decisions.json (a "step5" one is kept whether or not its warning is there); returns it"""
    d = {"clash:made:up": dict(answer="step5", at=store.now())}
    store.write_json(draft._p("decisions.json"), d); return d

def wipe_versions():
    shutil.rmtree(versions.VDIR, ignore_errors=True)

def test_save_lists_and_counts():
    save_draft(ROWS); one_fix(); wipe_versions()
    v = versions.save(" Run A ", "Tester"); assert v["name"] == "Run A" and v["kind"] == "saved"
    e = versions.listing()[0]
    assert e["id"] == v["id"] and e["kind"] == "saved" and e["by"] == "Tester" and e["fixes"] == 1, e
    ck = draft.checked_in(draft.DIR); assert (e["critical"], e["warnings"]) == (ck["critical"], ck["warnings"])
    assert os.path.isfile(os.path.join(versions.VDIR, v["id"], "timetable.xlsx")) and os.path.isfile(os.path.join(versions.VDIR, v["id"], "setup.xlsx"))
    assert draft.summary()["versions"] == 1
    save_draft(ROWS); k = versions.keep("upload", "T"); day_month = " ".join(k["saved_at"].split()[:2])
    assert k["name"] == f"timetable · {day_month}", k["name"]
    assert versions.listing(counts=False)[0]["critical"] is None and versions.listing(counts=False)[0]["warnings"] is None
    versions.save("Run A", "Tester")   # names may repeat
    assert [x["name"] for x in versions.listing()].count("Run A") == 2

def test_names_are_checked():
    save_draft(ROWS); wipe_versions()
    raises(ValueError, lambda: versions.save("", "T"), "Give the version a name.")
    raises(ValueError, lambda: versions.save("   ", "T"), "Give the version a name.")
    raises(ValueError, lambda: versions.save("x" * 81, "T"), "A version name is at most 80 characters.")
    assert versions.save("x" * 80, "T")["name"] == "x" * 80
    shutil.rmtree(draft.DIR)
    raises(ValueError, lambda: versions.save("A", "T"), "There is no draft.")
    assert versions.keep("upload", "T") is None
    save_draft(ROWS)

def test_keep_skips_a_draft_already_kept():
    save_draft(ROWS); wipe_versions()
    assert versions.keep("upload", "T") is not None and versions.keep("upload", "T") is None
    one_fix(); assert versions.keep("upload", "T") is not None
    assert len(versions.listing()) == 2

def test_open_keeps_the_draft_whole_and_brings_it_back():
    save_draft(ROWS); wipe_versions(); one_fix(); lift_one(); d = a_decision()
    before = c.get("/api/draft").get_json()["fixes"]; assert len(before) == 2
    v = versions.save("Before", "T")
    save_draft(ROWS); other = store.read_json(draft._p("meta.json"))["upload_id"]
    assert c.get("/api/draft").get_json()["fixes"] == []
    r = versions.open_version(v["id"], "T")
    j = c.get("/api/draft").get_json()
    assert j["fixes"] == before, (j["fixes"], before)
    assert [x for x in c.get("/api/draft/board").get_json()["unplaced"]] and draft.info()["unplaced"] == 1
    assert store.read_json(draft._p("decisions.json")) == d
    assert r["kept"]["kind"] == "open" and r["kept"]["identity"][0] == other and r["opened"]["id"] == v["id"]
    assert not os.path.exists(os.path.join(draft.DIR, "version.json")) and not os.path.exists(draft.DIR + ".new") and not os.path.exists(draft.DIR + ".old")
    assert versions.keep("open", "T") is None   # the opened draft is the saved one
    raises(ValueError, lambda: versions.open_version("0" * 12, "T"), "There is no such version.")

def test_automatic_keeps_are_capped_and_hand_saves_are_kept():
    save_draft(ROWS); wipe_versions(); hand = versions.save("Mine", "T"); firsts = []
    for i in range(11):
        save_draft(ROWS); firsts.append(versions.keep("upload", "T")["id"])
    ids = [x["id"] for x in versions.listing(counts=False)]
    auto = [x for x in versions.listing(counts=False) if x["kind"] != "saved"]
    assert len(auto) == versions.AUTO_KEEP == 10 and firsts[0] not in ids and all(i in ids for i in firsts[1:]) and hand["id"] in ids
    wipe_versions()
    for i in range(30): versions.save(f"V{i}", "T")
    raises(ValueError, lambda: versions.save("one more", "T"), "There are 30 saved versions: delete one first.")
    assert len(versions.listing(counts=False)) == 30
    save_draft(ROWS); assert versions.keep("upload", "T") is not None   # automatic keeps are not held back by the hand-saved cap
    d = versions.delete(versions.listing(counts=False)[-1]["id"]); assert d["kind"] == "saved" and len(versions.listing(counts=False)) == 30
    wipe_versions()

def test_counts_follow_the_setup_version():
    save_draft(ROWS); wipe_versions(); v = versions.save("Counts", "T")
    first = versions.listing()[0]; vj = lambda: store.read_json(os.path.join(versions.VDIR, v["id"], "version.json"))
    rec = store.setup_record(); assert vj()["checked"]["v"] == rec["v"]
    # step 5 says another teacher takes English for the first class than the one the draft has: the draft's lesson is listed under
    # "taught by X on the timetable; step 5 says Y". Putting the draft's own teacher into step 5 removes exactly that one warning
    spec2 = json.loads(json.dumps(rec["spec"]))
    rows = [l for l in spec2["lessons"] if l["subject"] == SUBJ and l["classes"] == [CLASSES[0]]]; assert len(rows) == 1
    rows[0]["teachers"] = [TEACHERS[0]]
    assert c.put("/api/setup", json=spec2).status_code == 200
    after = versions.listing()[0]
    assert after["warnings"] == first["warnings"] - 1 and after["critical"] == first["critical"], (first, after)
    assert vj()["checked"]["v"] == store.setup_record()["v"] != rec["v"]
    ck = draft.checked_in(os.path.join(versions.VDIR, v["id"])); assert (after["critical"], after["warnings"]) == (ck["critical"], ck["warnings"])
    assert c.put("/api/setup", json=rec["spec"]).status_code == 200

def test_opening_the_oldest_automatic_version_keeps_it():
    save_draft(ROWS); wipe_versions(); ids = []
    for i in range(10):
        save_draft(ROWS); ids.append(versions.keep("upload", "T")["id"])
    save_draft(ROWS); one_fix()   # the draft now matches no version
    assert len(versions.listing(counts=False)) == 10
    r = versions.open_version(ids[0], "T")
    got = [x["id"] for x in versions.listing(counts=False)]
    assert ids[0] in got and r["kept"]["id"] in got and ids[1] not in got and len(got) == 10, got   # the next oldest went instead
    assert store.read_json(draft._p("meta.json"))["upload_id"] == r["opened"]["identity"][0] and c.get("/api/draft").get_json()["fixes"] == []

def test_a_broken_version_json_blocks_nothing():
    save_draft(ROWS); wipe_versions(); good = versions.save("Good", "T")
    for i, text in enumerate(["", "{not json", "[1, 2]", '{"kind": "saved"}', '{"identity": [1, 2, 3]}', '{"kind": "saved", "identity": "x"}']):
        d = os.path.join(versions.VDIR, secrets.token_hex(6)); os.makedirs(d)
        if text: open(os.path.join(d, "version.json"), "w").write(text)
    os.makedirs(os.path.join(versions.VDIR, secrets.token_hex(6)))   # no version.json at all
    save_draft(ROWS); k = versions.keep("upload", "T"); assert k is not None
    ls = versions.listing(); assert [x["id"] for x in ls] == [k["id"], good["id"]]
    assert draft.summary()["versions"] == len(ls) == len(versions.listing(counts=False)) == 2
    bad = next(x for x in os.listdir(versions.VDIR) if x not in (k["id"], good["id"]))
    raises(ValueError, lambda: versions.folder(bad), "There is no such version.")
    wipe_versions()

def test_a_version_that_cannot_be_read_does_not_hide_the_others():
    save_draft(ROWS); wipe_versions(); one_fix(); a = versions.save("A", "T"); save_draft(ROWS); b = versions.save("B", "T")
    open(os.path.join(versions.VDIR, a["id"], "timetable.xlsx"), "wb").write(b"junk")
    rec = store.setup_record(); spec2 = json.loads(json.dumps(rec["spec"])); spec2["school"]["name"] = "Made-up School"   # a new setup version: every count is redone
    assert c.put("/api/setup", json=spec2).status_code == 200
    import contextlib
    err = io.StringIO()
    with contextlib.redirect_stderr(err): ls = versions.listing()
    by = {x["id"]: x for x in ls}; assert set(by) == {a["id"], b["id"]}
    assert (by[a["id"]]["critical"], by[a["id"]]["warnings"]) == (None, None) and by[a["id"]]["fixes"] == 1
    ck = draft.checked_in(draft.DIR); assert (by[b["id"]]["critical"], by[b["id"]]["warnings"]) == (ck["critical"], ck["warnings"])
    assert a["id"] in err.getvalue()
    # the lock is free while counts are built
    import threading; seen = []
    orig = draft.checked_in
    def spy(folder, rec=None):
        got = []; t = threading.Thread(target=lambda: got.append(draft._lock.acquire(timeout=2) and (draft._lock.release() or True))); t.start(); t.join(); seen.append(got[0]); return orig(folder, rec)
    c.put("/api/setup", json=rec["spec"]); draft.checked_in = spy
    try: versions.listing()
    finally: draft.checked_in = orig
    assert seen and all(seen), seen
    wipe_versions()

def test_bad_ids_are_refused():
    for bad in ("../draft", "zz", "0" * 12, "A" * 12, "", None, "0" * 13):
        raises(ValueError, lambda: versions.folder(bad), "There is no such version.")
        raises(ValueError, lambda: versions.delete(bad), "There is no such version.")
    save_draft(ROWS); v = versions.save("Ok", "T"); assert versions.folder(v["id"]) == os.path.join(versions.VDIR, v["id"])

def test_upload_over_fixes_keeps_the_draft():
    save_draft(ROWS); wipe_versions(); one_fix()
    r = c.post("/api/draft", data=dict(setup=(io.BytesIO(setup_bytes(SPEC)), "setup.xlsx"), timetable=(io.BytesIO(workbook(ROWS[:2])), "timetable.xlsx")), content_type="multipart/form-data")
    assert r.status_code == 200, r.get_json()
    j = r.get_json(); assert j["kept"]["kind"] == "upload" and j["fixes"] == [], j
    kept = [v for v in versions.listing(counts=False) if v["id"] == j["kept"]["id"]]; assert len(kept) == 1 and kept[0]["fixes"] == 1
    # a file that cannot be read leaves the draft and the versions as they were
    n = len(versions.listing(counts=False))
    r = c.post("/api/draft", data=dict(setup=(io.BytesIO(setup_bytes(SPEC)), "setup.xlsx"), timetable=(io.BytesIO(b"not a workbook"), "timetable.xlsx")), content_type="multipart/form-data")
    assert r.status_code == 400 and len(versions.listing(counts=False)) == n
    wipe_versions()

def newest_entry():
    return A.history.read(limit=1)[0]

def texts(n=3):
    return [e["text"] for e in A.history.read(limit=n)]

def test_version_routes_need_the_committee():
    save_draft(ROWS); wipe_versions()
    for m, u in [("get", "/api/draft/versions"), ("post", "/api/draft/versions"), ("post", "/api/draft/versions/abc/open"), ("delete", "/api/draft/versions/abc"), ("get", "/api/draft/versions/abc/download")]:
        r = getattr(NOSE, m)(u); assert r.status_code == 401 and r.get_json() == {"error": "Please sign in again."}, (m, u, r.status_code)

def test_save_open_delete_through_the_routes():
    save_draft(ROWS); wipe_versions(); one_fix()
    r = c.post("/api/draft/versions", json=dict(name="Before the trial")); assert r.status_code == 200, r.get_json()
    v = r.get_json(); assert v["name"] == "Before the trial" and v["kind"] == "saved"
    j = c.get("/api/draft/versions").get_json(); assert [x["id"] for x in j["versions"]] == [v["id"]] and j["published"] is None and j["draft"]["fixes"] == 1, j
    assert c.post("/api/draft/versions", json=dict(name=" ")).status_code == 400
    c.post("/api/draft/undo"); assert c.get("/api/draft").get_json()["fixes"] == []
    r = c.post(f"/api/draft/versions/{v['id']}/open"); assert r.status_code == 200, r.get_json()
    o = r.get_json(); assert len(o["info"]["fixes"]) == 1 and o["opened"]["id"] == v["id"] and o["kept"]["kind"] == "open", o
    r = c.delete(f"/api/draft/versions/{v['id']}"); assert r.status_code == 200 and r.get_json()["deleted"]["id"] == v["id"]
    assert v["id"] not in [x["id"] for x in c.get("/api/draft/versions").get_json()["versions"]]
    got = texts(4); assert [got[0], got[1], got[3]] == ["Deleted version “Before the trial”", f"Opened version “Before the trial”; the draft before is kept as version “{o['kept']['name']}”", "Saved version “Before the trial”"], got
    wipe_versions()

def test_a_deleted_version_is_refused_plainly():
    save_draft(ROWS); wipe_versions()
    v = c.post("/api/draft/versions", json=dict(name="Gone soon")).get_json(); assert c.delete(f"/api/draft/versions/{v['id']}").status_code == 200
    said = {"error": "There is no such version."}
    for r in (c.post(f"/api/draft/versions/{v['id']}/open"), c.get(f"/api/draft/versions/{v['id']}/download"), c.delete(f"/api/draft/versions/{v['id']}"), c.delete("/api/draft/versions/not-a-version")):
        assert r.status_code == 404 and r.get_json() == said, (r.status_code, r.get_json())

def test_download_a_version():
    save_draft(ROWS); wipe_versions(); one_fix()
    v = c.post("/api/draft/versions", json=dict(name="For the file")).get_json()
    r = c.get(f"/api/draft/versions/{v['id']}/download")
    if r.status_code == 409: assert r.get_json()["unplaced"] >= 1; wipe_versions(); return   # the made-up draft may have a lesson waiting
    assert r.status_code == 200 and "For the file - version.sqlite" in r.headers["Content-Disposition"], r.headers
    p = os.path.join(tempfile.mkdtemp(), "v.sqlite"); open(p, "wb").write(r.data)
    spec = c.get("/api/setup").get_json()["spec"]
    m = model_from_files(None, p, spec=spec); assert len(m["lessons"]) == len(draft.model_now()[0]["lessons"]) and m["lessons"]
    wipe_versions()

def test_an_upload_over_a_kept_draft_keeps_nothing_new():
    save_draft(ROWS); wipe_versions(); one_fix()
    assert c.post("/api/draft/versions", json=dict(name="Already kept")).status_code == 200
    n = len(versions.listing(counts=False))
    r = c.post("/api/draft", data=dict(setup=(io.BytesIO(setup_bytes(SPEC)), "setup.xlsx"), timetable=(io.BytesIO(workbook(ROWS[:2])), "again.xlsx")), content_type="multipart/form-data")
    assert r.status_code == 200 and r.get_json()["kept"] is None, r.get_json()
    assert len(versions.listing(counts=False)) == n and newest_entry()["text"] == "Uploaded again.xlsx", newest_entry()
    wipe_versions()

def test_the_history_names_the_version_kept():
    save_draft(ROWS); wipe_versions(); one_fix()
    r = c.post("/api/draft", data=dict(setup=(io.BytesIO(setup_bytes(SPEC)), "setup.xlsx"), timetable=(io.BytesIO(workbook(ROWS[:2])), "next.xlsx")), content_type="multipart/form-data")
    k = r.get_json()["kept"]; assert k, r.get_json()
    assert newest_entry()["text"].endswith(f"; the draft before is kept as version “{k['name']}”"), newest_entry()
    wipe_versions()

if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for f in tests: f()
    print(f"{len(tests)} checks passed")

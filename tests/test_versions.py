"""Plain-assert tests for reading and checking any draft folder: .venv/bin/python tests/test_versions.py"""
import contextlib, gzip, io, json, os, secrets, shutil, sys, tempfile, time
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

def workbook(rows, report=()):
    """a made-up Lessons workbook: rows = [dict(id, day, p, n, level, block, classes, subject, group, teachers)]; report: the lines of its Rule report"""
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Lessons"
    ws.append(["Lesson ID", "Day", "Start period", "End period", "Periods", "Starts", "Ends", "Level", "Block", "Classes", "Subject", "Group", "Teachers", "Room", "After school", "Rain room"])
    for r in rows:
        ws.append([r["id"], r["day"], r["p"], r["p"] + r["n"] - 1, r["n"], "", "", r["level"], r.get("block", ""), ", ".join(r["classes"]), r["subject"], r.get("group", "Entire Class"), ", ".join(r.get("teachers", [])), r.get("room", ""), "", r.get("rain", "")])
    if report:
        wr = wb.create_sheet("Rule report"); wr.append(["No.", "Must / Prefer", "Applies to", "Rule", "Result", "How"])
        for line in report: wr.append(list(line))
    buf = io.BytesIO(); wb.save(buf); return buf.getvalue()

_made = {}   # the setup workbook is made once: every upload here sends the same one
def setup_bytes(spec):
    if "b" not in _made: p = os.path.join(tempfile.mkdtemp(), "setup.xlsx"); write_template(spec, p); _made["b"] = open(p, "rb").read()
    return _made["b"]

def upload(rows, report=(), name="timetable.xlsx"):
    """the answer of an upload of the rows"""
    return c.post("/api/draft", data=dict(setup=(io.BytesIO(setup_bytes(SPEC)), "setup.xlsx"), timetable=(io.BytesIO(workbook(rows, report)), name)), content_type="multipart/form-data")

def save_draft(rows, report=()):
    r = upload(rows, report); assert r.status_code == 200, r.get_json()

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

def two_places():
    """two places the server judges clean for the plain lesson, other than where it is"""
    d = [(s["d"], s["p"]) for s in draft.slots(PLAIN_ID)["slots"] if s["state"] == "ok" and (s["d"], s["p"]) != (0, 0)]; assert len(d) >= 2, d
    return d[0], d[1]

def move_to(at): draft.fix(dict(kind="move", id=PLAIN_ID, d=at[0], p=at[1]))

def plain_at(folder=None):
    """where the plain lesson is on the draft, or on a version's copy of it"""
    m = draft.model_in(folder)[0] if folder else draft.model_now()[0]
    return next((x["d"], x["p"]) for x in m["lessons"] if x["id"] == PLAIN_ID)

@contextlib.contextmanager
def patched(obj, name, value):
    old = getattr(obj, name); setattr(obj, name, value)
    try: yield
    finally: setattr(obj, name, old)

def same_minute(): return patched(store, "now", lambda: "22 Nov 2026, 13:12")

def decisions(folder=None): return store.read_json(os.path.join(folder or draft.DIR, "decisions.json"))
def fixes_in(folder=None): return store.read_json(os.path.join(folder or draft.DIR, "meta.json"))["fixes"]
def kept_folder(v): return versions.folder(v["id"])

TYPED = dict(scope="School", target="Whole school", rule="In words", text="Nobody is rushed", strength="Prefer", week="Both", day="All")
REPORT = [(1, "Prefer", "Whole school", "Nobody is rushed", "Met", "Checked.")]

@contextlib.contextmanager
def typed_rule():
    """the setup with one rule in words, then as it was"""
    was = store.setup_record()["spec"]
    assert c.put("/api/setup", json=dict(json.loads(json.dumps(was)), rules=list(was.get("rules") or []) + [TYPED])).status_code == 200
    try: yield
    finally: assert c.put("/api/setup", json=was).status_code == 200

def met():
    """the typed rule's "check it again" warning answered met, through the route"""
    r = c.post("/api/draft/decide", json=dict(key="typed:1:again", answer="met")); assert r.status_code == 200, r.get_json()
    assert decisions()["typed:1:again"]["answer"] == "met"; return decisions()

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
    assert versions.count() == 1 == c.get("/api/status").get_json()["versions"]
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

def test_another_change_in_the_same_minute_is_kept_by_an_upload():
    with same_minute():   # the two changes have the same "at"
        save_draft(ROWS); wipe_versions(); first, second = two_places()
        move_to(first); v = versions.save("First", "T"); draft.undo(); move_to(second)
        j = upload(ROWS[:2]).get_json()
    assert isinstance(j["kept"], dict), j["kept"]
    assert plain_at(kept_folder(j["kept"])) == second and plain_at(kept_folder(v)) == first

def test_another_change_in_the_same_minute_is_kept_by_open():
    with same_minute():
        save_draft(ROWS); wipe_versions(); first, second = two_places()
        move_to(first); v = versions.save("First", "T"); draft.undo(); move_to(second)
        r = versions.open_version(v["id"], "T")
    assert isinstance(r["kept"], dict) and plain_at(kept_folder(r["kept"])) == second and plain_at() == first

def test_an_answer_alone_is_kept_by_an_upload():
    with typed_rule():
        save_draft(ROWS, REPORT); wipe_versions(); move_to(two_places()[0]); versions.save("Before the answer", "T"); met()
        j = upload(ROWS[:2]).get_json()
        assert isinstance(j["kept"], dict) and decisions(kept_folder(j["kept"]))["typed:1:again"]["answer"] == "met", j["kept"]

def test_an_answer_alone_is_kept_by_open():
    with typed_rule():
        save_draft(ROWS, REPORT); wipe_versions(); move_to(two_places()[0]); v = versions.save("Before the answer", "T"); met()
        r = versions.open_version(v["id"], "T")
        assert isinstance(r["kept"], dict) and decisions(kept_folder(r["kept"]))["typed:1:again"]["answer"] == "met", r["kept"]
        assert "typed:1:again" not in (decisions() or {})   # the opened one has no answer
        assert versions.open_version(r["kept"]["id"], "T")["kept"] is None and decisions()["typed:1:again"]["answer"] == "met"   # and the answer comes back

def test_updating_step_5_alone_is_kept_by_an_upload():
    was = store.setup_record()["spec"]
    try:
        save_draft(ROWS); wipe_versions(); w = next(w for w in draft.info()["warnings"] if w["kind"] == "deployment" and w["ops"]); versions.save("Before", "T")
        assert c.post("/api/draft/decide", json=dict(key=w["key"], answer="step5")).status_code == 200
        j = upload(ROWS[:2]).get_json()
        assert isinstance(j["kept"], dict) and decisions(kept_folder(j["kept"]))[w["key"]]["answer"] == "step5", j["kept"]
    finally: assert c.put("/api/setup", json=was).status_code == 200

def test_an_unchanged_draft_is_not_kept_twice():
    with typed_rule():
        save_draft(ROWS, REPORT); wipe_versions(); move_to(two_places()[0]); lift_one(); met(); v = versions.save("All of it", "T")
        c.get("/api/draft"); c.get("/api/draft/versions")   # looking at it changes nothing
        assert versions.keep("open", "T") is None and versions.open_version(v["id"], "T")["kept"] is None
        assert upload(ROWS[:2]).get_json()["kept"] is None and versions.count() == 1

def test_the_identity_is_the_content():
    fx = dict(kind="move", id=1, d=1, p=2, at="22 Nov 2026, 13:12", text="Moved."); one = dict(upload_id="u", fixes=[fx])
    i = versions.identity(one, {}); assert i[:2] == ["u", 1] and len(i) == 3 and isinstance(i[2], str)
    assert versions.identity(json.loads(json.dumps(one)), None) == i   # no decisions read is no decisions
    assert versions.identity(dict(one, open=4, critical=1, published_fixes=1), {}) == i   # the counts kept beside the draft are not the draft
    for other in (dict(one, upload_id="v"), dict(one, fixes=[]), dict(one, fixes=[dict(fx, p=3)]), dict(one, fixes=[dict(fx, id=2)]), dict(one, fixes=[fx, fx])): assert versions.identity(other, {}) != i, other
    a = versions.identity(one, {"k": dict(answer="met", at="x")}); assert a != i and versions.identity(one, {"k": dict(answer="step5", at="x")}) != a
    assert versions.identity(one, {"k": dict(answer="left", at="x")}) == i   # no longer an answer
    save_draft(ROWS); wipe_versions(); meta = store.read_json(draft._p("meta.json")); meta.pop("upload_id"); store.write_json(draft._p("meta.json"), meta)   # a draft from before upload ids
    assert versions.keep("upload", "T") and versions.keep("upload", "T")   # it cannot be told from another such draft, so it is kept each time
    wipe_versions(); save_draft(ROWS)

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

def test_what_open_keeps_is_whole():
    save_draft(ROWS); wipe_versions(); plain = versions.save("Plain", "T")
    move_to(two_places()[0]); lift_one(); d = a_decision(); before, at = fixes_in(), plain_at(); assert len(before) == 2
    k = versions.open_version(plain["id"], "T")["kept"]; f = kept_folder(k)
    assert fixes_in() == [] and not decisions()   # the plain one is the draft now
    assert k["kind"] == "open" and k["identity"][1] == 2 and fixes_in(f) == before and decisions(f) == d, (k, fixes_in(f), decisions(f))
    assert plain_at(f) == at and draft.model_in(f)[2]["pool"] and [x["id"] for x in draft.model_in(f)[2]["pool"]] == [OTHER_ID]
    assert versions.open_version(k["id"], "T")["kept"] is None   # the plain one is kept already
    assert fixes_in() == before and decisions() == d and plain_at() == at and draft.info()["unplaced"] == 1 and draft.paths()[0] and len(c.get("/api/draft").get_json()["fixes"]) == 2
    draft.undo(); assert draft.info()["unplaced"] == 0   # and Undo works on it

def test_what_an_upload_keeps_is_whole():
    save_draft(ROWS); wipe_versions(); move_to(two_places()[0]); lift_one(); d = a_decision(); before, at = fixes_in(), plain_at()
    k = upload(ROWS[:2]).get_json()["kept"]; f = kept_folder(k)
    assert k["kind"] == "upload" and k["identity"][1] == 2 and fixes_in(f) == before and decisions(f) == d, (k, fixes_in(f), decisions(f))
    assert sorted(x for x in os.listdir(f)) == ["decisions.json", "meta.json", "setup.xlsx", "timetable.xlsx", "version.json"]
    versions.open_version(k["id"], "T"); assert fixes_in() == before and decisions() == d and plain_at() == at and draft.info()["unplaced"] == 1

# the swap, and two tabs
def failing_swap(times=1):
    """os.replace that fails when a folder is put in place as the draft, the first `times` times"""
    real, left = os.replace, [times]
    def replace(a, b, *more):
        if b == draft.DIR and str(a).endswith(".new") and left[0]: left[0] -= 1; raise OSError("no room")
        return real(a, b, *more)
    return patched(os, "replace", replace)

def test_a_swap_that_fails_leaves_the_draft_there():
    save_draft(ROWS); wipe_versions(); v = versions.save("Plain", "T"); move_to(two_places()[0]); lift_one(); d = a_decision(); before, at = fixes_in(), plain_at()
    for go in (lambda: versions.open_version(v["id"], "T"), lambda: draft.save(*reversed(uploaded_paths(ROWS[:2])), "again.xlsx", store.setup_record()["spec"])):
        with failing_swap(): raises(OSError, go, "no room")
        assert draft.exists() and fixes_in() == before and decisions() == d and plain_at() == at and draft.info()["unplaced"] == 1
        assert not os.path.exists(draft.DIR + ".new") and not os.path.exists(draft.DIR + ".old")
        assert c.get("/api/status").get_json()["versions"] == versions.count() == 2 and c.get("/api/draft").get_json()["fixes"]
    with failing_swap(), patched(A.app.logger, "disabled", True): r = c.post(f"/api/draft/versions/{v['id']}/open")
    assert r.status_code >= 400 and fixes_in() == before
    assert versions.open_version(v["id"], "T")["opened"]["id"] == v["id"] and fixes_in() == []   # and the next try works

def uploaded_paths(rows):
    """(timetable, setup) files on disk, as the upload route hands them over"""
    d = tempfile.mkdtemp(); t, s = os.path.join(d, "timetable.xlsx"), os.path.join(d, "setup.xlsx")
    open(t, "wb").write(workbook(rows)); open(s, "wb").write(setup_bytes(SPEC)); return t, s

def test_the_status_counts_the_versions_without_a_draft():
    save_draft(ROWS); wipe_versions(); v = versions.save("Safe", "T"); shutil.rmtree(draft.DIR)
    try:
        st = c.get("/api/status").get_json(); assert st["draft"] is None and st["versions"] == 1, st
        j = c.get("/api/draft/versions"); assert j.status_code == 200 and j.get_json()["draft"] is None and [x["id"] for x in j.get_json()["versions"]] == [v["id"]]
        r = c.post(f"/api/draft/versions/{v['id']}/open"); assert r.status_code == 200 and r.get_json()["kept"] is None and draft.exists(), r.get_json()
    finally:
        if not draft.exists(): save_draft(ROWS)

def test_an_answer_built_on_another_draft_writes_nothing():
    with typed_rule():
        save_draft(ROWS, REPORT); wipe_versions(); move_to(two_places()[0]); met(); b = versions.save("B", "T")   # B has an answer
        bd, bf = decisions(), fixes_in(); n = draft.info()["open"]
        save_draft(ROWS[:2]); a = draft._build()                                                                  # the other tab is checking A
        k = versions.open_version(b["id"], "T")["kept"]; assert k
        meta = store.read_json(draft._p("meta.json"))
        j = draft._finish(a); assert j["upload_id"] == k["identity"][0] and j["lessons"] == 2 and "decision" in j["warnings"][0]   # the answer is still A's
        assert decisions() == bd and fixes_in() == bf and store.read_json(draft._p("meta.json")) == meta, (decisions(), bd)
        draft._finish(a, ("typed:1:again", None)); assert decisions() == bd   # an answer is not withdrawn on the other draft either
        # the current draft is still written: a decision whose warning is gone is dropped and the counts are put right
        store.write_json(draft._p("decisions.json"), dict(bd, **{"gone:key": dict(answer="met", at="x")})); store.write_json(draft._p("meta.json"), dict(meta, open=-1, critical=-1))
        j = draft.info(); assert decisions() == bd and store.read_json(draft._p("meta.json"))["open"] == j["open"] == n, (j["open"], n)
        # A and B may be of one upload: the fixes tell them apart
        a2 = draft._build(); draft.undo(); a3 = draft._build(); versions.open_version(b["id"], "T"); draft._finish(a3); assert decisions() == bd
        assert draft._finish(a2)["open"] == n and decisions() == bd

def test_a_version_opened_while_the_draft_is_checked_keeps_its_answers():
    """the other tab opens the version in the middle of this tab's check: after the model is built, before the answer is written"""
    with typed_rule():
        save_draft(ROWS, REPORT); wipe_versions(); move_to(two_places()[0]); met(); b = versions.save("B", "T"); bd, bf = decisions(), fixes_in()
        for look in (lambda: draft.info(), lambda: draft.preview_page(), lambda: c.get("/api/draft")):
            save_draft(ROWS[:2]); aid = store.read_json(draft._p("meta.json"))["upload_id"]; real, done = draft.model_now, []
            def slow(rec=None):
                got = real(rec)
                if not done: done.append(1); versions.open_version(b["id"], "T")
                return got
            with patched(draft, "model_now", slow): look()
            assert done and store.read_json(draft._p("meta.json"))["upload_id"] != aid and decisions() == bd and fixes_in() == bf, decisions()
        save_draft(ROWS[:2]); t, s = uploaded_paths(ROWS[:3]); m = draft.save(s, t, "next.xlsx", store.setup_record()["spec"])   # an upload, then the other tab opens B before the upload is checked
        versions.open_version(b["id"], "T"); j = draft.info(model=m); assert j["source"] == "next.xlsx" and decisions() == bd and fixes_in() == bf

def test_a_decision_is_never_written_on_another_draft():
    with typed_rule():
        save_draft(ROWS, REPORT); wipe_versions(); move_to(two_places()[0]); shown = draft.info()["upload_id"]
        save_draft(ROWS, REPORT); move_to(two_places()[0]); assert any(w["key"] == "typed:1:again" for w in draft.info()["warnings"])   # another tab's upload has a warning of the same key
        r = c.post("/api/draft/decide", json=dict(key="typed:1:again", answer="met", upload_id=shown))
        assert r.status_code == 400 and r.get_json() == {"error": "The draft was replaced while this was happening. Check the list again."} and not decisions(), (r.get_json(), decisions())
        r = c.post("/api/draft/decide", json=dict(key="typed:1:again", answer="met", upload_id=draft.info()["upload_id"])); assert r.status_code == 200 and decisions()["typed:1:again"]["answer"] == "met"
        # from the build to the write the lock is held: the other tab's Open waits
        import threading; v = versions.save("V", "T"); real, seen = draft._build, []
        def build(*a, **k):
            got = []; t = threading.Thread(target=lambda: got.append(draft._lock.acquire(timeout=0.2) and (draft._lock.release() or True))); t.start(); t.join(); seen.append(got[0]); return real(*a, **k)
        with patched(draft, "_build", build): draft.decide("typed:1:again", "open"); draft.decide("typed:1:again", "met")
        assert seen == [False, False], seen

def test_a_copy_that_fails_leaves_nothing_behind():
    save_draft(ROWS); wipe_versions(); v = versions.save("Plain", "T"); move_to(two_places()[0]); before = fixes_in(); real = shutil.copytree
    def copytree(src, dst, *a, **k):
        real(src, dst, *a, **k); os.remove(os.path.join(dst, "meta.json")); raise OSError("no room")   # a copy half made
    with patched(shutil, "copytree", copytree):
        raises(OSError, lambda: versions.save("Full", "T"), "no room"); raises(OSError, lambda: versions.keep("upload", "T"), "no room")
        raises(OSError, lambda: versions.open_version(v["id"], "T"), "no room")
    assert os.listdir(versions.VDIR) == [v["id"]] and not os.path.exists(draft.DIR + ".new") and fixes_in() == before, os.listdir(versions.VDIR)
    open_copy = lambda src, dst, *a, **k: copytree(src, dst) if dst == draft.DIR + ".new" else real(src, dst, *a, **k)   # the keep works, the copy of the version does not
    with patched(shutil, "copytree", open_copy): raises(OSError, lambda: versions.open_version(v["id"], "T"), "no room")
    assert not os.path.exists(draft.DIR + ".new") and fixes_in() == before and versions.count() == 2
    def copy(src, dst, *a, **k): raise OSError("no room")
    t, s = uploaded_paths(ROWS[:2])
    with patched(shutil, "copy", copy): raises(OSError, lambda: draft.save(s, t, "x.xlsx", store.setup_record()["spec"]), "no room")
    with patched(store, "write_json", copy):
        raises(OSError, lambda: draft.save(s, t, "x.xlsx", store.setup_record()["spec"]), "no room"); raises(OSError, lambda: versions.save("Full", "T"), "no room")
    assert not os.path.exists(draft.DIR + ".new") and fixes_in() == before and not [x for x in os.listdir(versions.VDIR) if x.endswith(".new")]

def test_the_version_just_kept_is_never_trimmed():
    save_draft(ROWS); wipe_versions()
    for i in range(10):
        save_draft(ROWS)
        versions.keep("upload", "T")
    save_draft(ROWS)
    with patched(versions.time, "time_ns", lambda: 1): k = versions.keep("upload", "T")   # a clock that went back
    ids = [x["id"] for x in versions.listing(counts=False)]; assert k["id"] in ids and len(ids) == 10, ids
    wipe_versions()

def test_names_are_one_line_of_words():
    save_draft(ROWS); wipe_versions()
    for bad in (123, ["Run A"], {"a": 1}, True, None, "\n\t ", ""):
        r = c.post("/api/draft/versions", json=dict(name=bad)); assert r.status_code == 400 and r.get_json() == {"error": "Give the version a name."}, (bad, r.status_code, r.get_json())
    assert c.post("/api/draft/versions", json=["x"]).status_code == 400 and versions.count() == 0
    r = c.post("/api/draft/versions", json=dict(name=" Run\nA\t\r\n  edited ")); assert r.status_code == 200 and r.get_json()["name"] == "Run A edited"
    assert newest_entry()["text"] == "Saved version “Run A edited”"
    assert versions.save("a" * 40 + "\n\n\n" + "b" * 39, "T")["name"] == "a" * 40 + " " + "b" * 39   # one line first, then at most 80
    raises(ValueError, lambda: versions.save("a" * 40 + "\n" + "b" * 40, "T"), "A version name is at most 80 characters.")

def test_a_time_reads_as_a_person_says_it():
    for text, said in (("22 Nov 2026, 13:12", "22 Nov 2026, 1.12 pm"), ("05 Nov 2026, 00:05", "05 Nov 2026, 12.05 am"), ("22 Nov 2026, 12:00", "22 Nov 2026, 12.00 pm"), ("22 Nov 2026, 09:40", "22 Nov 2026, 9.40 am"), ("last week", "last week"), ("", ""), (None, "")):
        assert versions.when(text) == said, (text, versions.when(text))
    assert versions.label(dict(name="Run A", saved_at="22 Nov 2026, 13:12")) == "Run A (22 Nov 2026, 1.12 pm)" and versions.label(dict(name="Run A")) == "Run A"

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

def test_counts_follow_the_checking_code():
    save_draft(ROWS); wipe_versions(); v = versions.save("Counts", "T"); calls, real = [], draft.checked_in
    spy = lambda folder, rec=None: (calls.append(folder), real(folder, rec))[1]
    with patched(draft, "checked_in", spy):
        versions.listing(); versions.listing(); assert len(calls) == 1   # kept
        with patched(versions, "CHECKS", versions.CHECKS + 1): versions.listing(); versions.listing(); assert len(calls) == 2   # a deploy with newer checks
        versions.listing(); assert len(calls) == 3   # and one that went back
    assert store.read_json(os.path.join(versions.VDIR, v["id"], "version.json"))["checked"]["code"] == versions.CHECKS
    assert versions.CHECKS == max(os.stat(m.__file__).st_mtime_ns for m in (draft, versions, fixes_mod, draft.helper, draft.verify))

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
    assert versions.count() == len(ls) == len(versions.listing(counts=False)) == 2
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

def test_an_open_whose_check_fails_is_in_the_history_and_says_what_was_kept():
    save_draft(ROWS); wipe_versions(); v = versions.save("Plain", "T"); one_fix()
    def broken(*a, **k): raise RuntimeError("the check broke")
    with patched(draft, "info", broken), patched(A.app.logger, "disabled", True): r = c.post(f"/api/draft/versions/{v['id']}/open")
    j = r.get_json(); assert r.status_code == 400 and "the check broke" in j["error"] and j["kept"]["kind"] == "open" and j["opened"]["id"] == v["id"], j
    assert newest_entry()["text"] == f"Opened version “Plain”; the draft before is kept as version “{j['kept']['name']}”", newest_entry()
    assert fixes_in() == []   # the version is the draft

def test_a_deleted_version_is_refused_plainly():
    save_draft(ROWS); wipe_versions()
    v = c.post("/api/draft/versions", json=dict(name="Gone soon")).get_json(); assert c.delete(f"/api/draft/versions/{v['id']}").status_code == 200
    said = {"error": "There is no such version."}
    for r in (c.post(f"/api/draft/versions/{v['id']}/open"), c.get(f"/api/draft/versions/{v['id']}/download"), c.delete(f"/api/draft/versions/{v['id']}"), c.delete("/api/draft/versions/not-a-version")):
        assert r.status_code == 404 and r.get_json() == said, (r.status_code, r.get_json())

def test_download_a_version():
    save_draft(ROWS); wipe_versions(); one_fix()
    assert draft.model_now()[2]["pool"] == [], "the made-up draft must have nothing in Not placed"
    v = c.post("/api/draft/versions", json=dict(name="For the file")).get_json()
    r = c.get(f"/api/draft/versions/{v['id']}/download")
    assert r.status_code == 200 and "For the file - version.sqlite" in r.headers["Content-Disposition"], (r.status_code, r.get_json())
    p = os.path.join(tempfile.mkdtemp(), "v.sqlite"); open(p, "wb").write(r.data)
    spec = c.get("/api/setup").get_json()["spec"]
    m = model_from_files(None, p, spec=spec); assert m["lessons"] and len(m["lessons"]) == len(draft.model_now()[0]["lessons"])
    wipe_versions()

def test_a_version_with_an_unplaced_lesson_is_not_downloaded():
    save_draft(ROWS); wipe_versions()
    j = c.post("/api/draft/fix", json=dict(kind="lift", id=PLAIN_ID)).get_json(); assert j["unplaced"] == 1, j
    v = c.post("/api/draft/versions", json=dict(name="With a gap")).get_json()
    r = c.get(f"/api/draft/versions/{v['id']}/download"); w = c.get("/api/draft/download")
    assert r.status_code == 409 and r.get_json()["unplaced"] == 1 and r.get_json() == w.get_json() and w.status_code == 409, (r.get_json(), w.get_json())
    wipe_versions()

def test_a_corrupt_version_is_not_opened():
    save_draft(ROWS); wipe_versions(); one_fix()
    v = c.post("/api/draft/versions", json=dict(name="Spoiled")).get_json()
    tp = draft.paths(versions.folder(v["id"]))[1]; open(tp, "wb").write(b"garbage")
    before = (draft.model_now()[0]["lessons"], c.get("/api/draft").get_json()["fixes"]); n = len(versions.listing(counts=False))
    r = c.post(f"/api/draft/versions/{v['id']}/open")
    assert r.status_code == 400 and r.get_json() == {"error": "That version cannot be opened: its files could not be read."}, (r.status_code, r.get_json())
    assert (draft.model_now()[0]["lessons"], c.get("/api/draft").get_json()["fixes"]) == before and len(versions.listing(counts=False)) == n
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

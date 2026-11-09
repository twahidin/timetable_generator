"""Server smoke checks. Run: .venv/bin/python tests/smoke.py   (add --full for the slow publish check)"""
import os, secrets, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = tempfile.mkdtemp()
CODES = {k: secrets.token_hex(4) for k in ("COMMITTEE_CODE", "TEACHER_CODE", "STUDENT_CODE", "HEADS_CODE")}
if os.environ.get("SMOKE_NO_HEADS"): del CODES["HEADS_CODE"]      # SMOKE_NO_HEADS=1 runs the script without the optional heads' code
os.environ.pop("HEADS_CODE", None)
# variables an existing deployment may still have: they must be ignored
os.environ.update(DATA_DIR=DATA, SECRET_KEY=secrets.token_hex(16), AI_PROVIDER="anthropic", AI_API_KEY="", SOLVE_SECONDS="60", **CODES)
os.makedirs(os.path.join(DATA, "runs", "old1"))
sys.path.insert(0, ROOT)
import app as A, store

c = A.app.test_client()
assert c.post("/login", data={"as": "committee", "code": CODES["COMMITTEE_CODE"]}).status_code == 302
h = A.app.test_client() if "HEADS_CODE" in CODES else None
if h: assert h.post("/login", data={"as": "heads", "code": CODES["HEADS_CODE"]}).status_code == 302

def test_removed_modules():
    for m in ("runs", "timetabler", "ai", "adjust"):
        assert m not in sys.modules, m
        assert not os.path.exists(os.path.join(ROOT, m + ".py")), m

def test_removed_routes():
    gone = [("POST", "/api/generate"), ("POST", "/api/message"), ("POST", "/api/stop"), ("POST", "/api/keep-changes"), ("POST", "/api/publish"),
            ("POST", "/api/allocate"), ("GET", "/api/adjust"), ("POST", "/api/adjust/move"), ("POST", "/api/adjust/ask"), ("GET", "/preview")]
    for method, url in gone:
        assert c.open(url, method=method).status_code in (404, 405), url

def test_status_shape():
    j = c.get("/api/status").get_json()
    assert set(j) == {"role", "codes", "code_problems", "volume", "setup_saved_at", "published"}, sorted(j)
    assert j["published"] is None and j["role"] == "committee"

def test_old_runs_folder_is_harmless():
    assert c.get("/api/past-setups").status_code == 200

def test_setup_round_trip():
    spec = c.get("/api/sample/secondary").get_json()
    assert c.put("/api/setup", json=spec).status_code == 200
    assert c.get("/api/setup").get_json()["spec"]["school"]["name"] == spec["school"]["name"]

def _check(spec): return c.post("/api/check", json=spec)

def test_check_passes_the_sample():
    r = _check(c.get("/api/sample/secondary").get_json()); j = r.get_json()
    assert r.status_code == 200 and j["critical"] == 0, j
    assert j["warnings"] == sum(1 for f in j["findings"] if f["level"] == "warning")

def test_check_lists_a_class_with_more_periods_than_its_days():
    spec = c.get("/api/sample/secondary").get_json()
    subject = next(x for x in spec["subjects"] if (x.get("periods") or {}).get("Sec 1")); subject["periods"]["Sec 1"] = 200
    j = _check(spec).get_json()
    assert j["critical"] >= 1 and j["findings"][0]["level"] == "critical", j["findings"][:2]
    assert any("lesson periods a cycle" in f["text"] and f["area"] == "classes" for f in j["findings"]), [f["text"][:80] for f in j["findings"][:5]]

def test_check_refuses_an_empty_setup():
    assert c.post("/api/check", json={}).status_code == 400

def _changes(client, since, ops=None, who=None):
    who = who or c
    r = who.post("/api/setup/changes", json={"since": since, "client": client, "ops": ops}) if ops is not None else who.get(f"/api/setup/changes?since={since}&client={client}")
    return r.status_code, r.get_json()

def test_two_people_change_different_rows():
    c.put("/api/setup", json=c.get("/api/sample/secondary").get_json())
    rec = c.get("/api/setup").get_json(); v0 = rec["v"]; a, b = rec["spec"]["classes"][0], rec["spec"]["classes"][1]
    assert a["_id"] and b["_id"] and a["_id"] != b["_id"]
    _, ja = _changes("A", v0, [["set", "classes", a["_id"], "size", 41]])
    _, jb = _changes("B", v0, [["set", "classes", b["_id"], "size", 42]])
    assert ja["v"] == v0 + 1 and jb["v"] == v0 + 2
    assert jb["patches"] == [{"v": v0 + 1, "ops": [["set", "classes", a["_id"], "size", 41]]}]    # B catches up on A in the same call
    now = c.get("/api/setup").get_json()["spec"]["classes"]
    assert (now[0]["size"], now[1]["size"]) == (41, 42)
    _, ga = _changes("A", ja["v"]); assert [p["v"] for p in ga["patches"]] == [v0 + 2] and ga["others"] >= 1

def test_both_can_teach_additions_are_kept():
    rec = c.get("/api/setup").get_json(); t = rec["spec"]["teachers"][0]; v = rec["v"]
    for who, subj in (("A", "Zzz One"), ("B", "Zzz Two")):
        _changes(who, v, [["merge", "teachers", t["_id"], "can_teach", [{"levels": "All", "subject": subj}], []]])
    got = [x["subject"] for x in c.get("/api/setup").get_json()["spec"]["teachers"][0]["can_teach"]]
    assert "Zzz One" in got and "Zzz Two" in got

def test_a_replaced_setup_resets_everyone():
    v = c.get("/api/setup").get_json()["v"]
    c.put("/api/setup", json={"spec": c.get("/api/sample/primary").get_json(), "why": "Opened a workbook"})
    code, j = _changes("A", v); assert j == {"v": j["v"], "reset": True, "replaced": True, "others": j["others"]}
    assert c.get("/api/setup/copies").get_json()[0]["what"] == "Before: Opened a workbook"

def test_a_restart_resets_without_losing_the_setup():
    v = c.get("/api/setup").get_json()["v"]; _changes("A", v, [["school", "timetable", "Term 9"]])
    store._log.clear(); store._setup.clear()            # what a restart does to the process
    rec = c.get("/api/setup").get_json(); assert rec["v"] == v + 1 and rec["spec"]["school"]["timetable"] == "Term 9"
    _, j = _changes("A", v); assert j["reset"] is True and j["replaced"] is False

def test_ids_do_not_reach_the_workbook():
    import io, openpyxl
    r = c.post("/api/build", json=c.get("/api/setup").get_json()["spec"])
    wb = openpyxl.load_workbook(io.BytesIO(r.data), read_only=True)
    assert not any("_id" in str(cell) for ws in wb.worksheets for row in ws.iter_rows(max_row=8, values_only=True) for cell in row if cell)

def test_the_heads_choice_shows_only_when_the_code_is_set():
    assert (b"Department heads" in c.get("/login").data) == bool(h)
    if not h: assert b"Department heads" not in c.get("/login?as=heads").data

def test_a_head_can_change_groups_but_not_classes():
    rec = c.get("/api/setup").get_json(); v = rec["v"]; sp = rec["spec"]
    assert h.get("/").status_code == 200 and h.get("/api/setup").status_code == 200
    code, _ = _changes("H", v, [["set", "lessons", sp["lessons"][0]["_id"], "students", 12]], who=h); assert code == 200
    code, j = _changes("H", v, [["set", "classes", sp["classes"][0]["_id"], "size", 99]], who=h); assert code == 403 and "classes" in j["error"].lower()
    assert c.get("/api/setup").get_json()["spec"]["classes"][0]["size"] != 99

def test_a_refused_batch_applies_nothing():
    rec = c.get("/api/setup").get_json(); v = rec["v"]; lid = rec["spec"]["lessons"][0]["_id"]
    code, _ = _changes("H", v, [["set", "lessons", lid, "students", 7], ["school", "name", "X"]], who=h); assert code == 403
    r = c.get("/api/setup").get_json(); assert r["v"] == v and r["spec"]["lessons"][0].get("students") != 7

def test_a_teacher_added_by_a_head_is_provisional():
    v = c.get("/api/setup").get_json()["v"]
    _changes("H", v, [["add", "teachers", {"_id": "newhire001", "name": "New Science teacher 1", "provisional": "No"}, ""]], who=h)
    t = next(x for x in c.get("/api/setup").get_json()["spec"]["teachers"] if x["_id"] == "newhire001"); assert t["provisional"] == "Yes"

def test_a_head_can_edit_only_provisional_teachers():
    rec = c.get("/api/setup").get_json(); v = rec["v"]
    firm = next(x for x in rec["spec"]["teachers"] if x.get("provisional") != "Yes")
    code, _ = _changes("H", v, [["set", "teachers", firm["_id"], "name", "Zed"]], who=h); assert code == 403
    code, _ = _changes("H", v, [["set", "teachers", "newhire001", "provisional", "No"]], who=h); assert code == 403
    code, _ = _changes("H", v, [["set", "teachers", "newhire001", "name", "Renamed"]], who=h); assert code == 200
    code, _ = _changes("H", v, [["merge", "teachers", firm["_id"], "can_teach", [{"levels": "All", "subject": "Qqq"}], []]], who=h); assert code == 200

def test_a_head_cannot_download_or_publish_or_replace():
    for method, url in (("POST", "/api/build"), ("PUT", "/api/setup"), ("POST", "/api/import-timetable"), ("GET", "/api/codes.csv"), ("POST", "/api/check"), ("GET", "/api/setup/copies"), ("POST", "/api/setup/restore")):
        assert h.open(url, method=method, json={}).status_code == 401, url
    s = h.get("/api/status").get_json(); assert s["role"] == "head" and "codes" not in s and "code_problems" not in s

def test_heads_code_is_optional_but_checked():
    import access
    keep = os.environ.get("HEADS_CODE")
    try:
        os.environ["HEADS_CODE"] = "abc"; assert any("HEADS_CODE" in p and "6 letters" in p for p in access.configured()[1])
        os.environ["HEADS_CODE"] = CODES["TEACHER_CODE"]; assert any("same" in p for p in access.configured()[1])
        os.environ.pop("HEADS_CODE", None); assert not any("HEADS_CODE" in p for p in access.configured()[1])
    finally:
        if keep: os.environ["HEADS_CODE"] = keep

def test_publish_uploaded_timetable():   # slow: solves the primary sample
    work = tempfile.mkdtemp(); setup, tt = os.path.join(work, "setup.xlsx"), os.path.join(work, "timetable.xlsx")
    env = dict(os.environ, PYTHONPATH=ROOT)
    subprocess.run([sys.executable, "-m", "ttgen", "sample", "primary", "--out", setup], check=True, env=env, cwd=ROOT)
    subprocess.run([sys.executable, "-m", "ttgen", "solve", setup, "--out", tt, "--time", "60"], env=env, cwd=ROOT)
    r = c.post("/api/import-timetable", data={"publish": "1", "setup": (open(setup, "rb"), "setup.xlsx"), "timetable": (open(tt, "rb"), "timetable.xlsx")},
               content_type="multipart/form-data")
    j = r.get_json(); assert r.status_code == 200 and j["published"] is True, j
    p = c.get("/api/status").get_json()["published"]
    assert p and p["source"] == "timetable.xlsx"
    t = A.app.test_client(); t.post("/login", data={"as": "teacher", "code": CODES["TEACHER_CODE"]})
    assert t.get("/timetable").status_code == 200

NEED_HEADS = {"test_a_head_can_change_groups_but_not_classes", "test_a_refused_batch_applies_nothing", "test_a_teacher_added_by_a_head_is_provisional",
              "test_a_head_can_edit_only_provisional_teachers", "test_a_head_cannot_download_or_publish_or_replace"}

if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_") and (k != "test_publish_uploaded_timetable" or "--full" in sys.argv)
             and (h or k not in NEED_HEADS)]
    for t in tests: t(); print("ok", t.__name__)
    print(f"{len(tests)} checks passed")

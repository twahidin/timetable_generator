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
import app as A, store, sync

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

def test_check_tries_the_fallbacks_in_order():
    spec = c.get("/api/setup").get_json()["spec"]
    row = next(r for r in spec["lessons"] if r.get("level") == "Sec 1" and not r.get("block") and r.get("subject") and len(r.get("classes") or []) == 1)
    cls, subj, NP = row["classes"][0], row["subject"], int(spec["school"]["periods_per_day"])
    spec["rules"] = list(spec.get("rules") or []) + [dict(scope="Class", target=cls, subject=subj, rule="Fixed at", level="Sec 1", week="Odd", day="Fri", **{"from": NP - 1}, strength="Must")]
    spec["choices"] = [dict(kind="rule", rule=len(spec["rules"]) - 1, fallback="Drop", order=1)]
    j = _check(spec).get_json()
    assert j["critical"] > 0 and j["fallbacks"]["critical"][0] >= 1, j
    assert j["fallbacks"]["pass_at"] == 1 and j["fallbacks"]["items"][0].startswith("Rule: Class · "), j["fallbacks"]
    spec["choices"] = []
    assert _check(spec).get_json()["fallbacks"] is None

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

def test_a_change_sent_from_before_a_replacement_is_not_applied():
    v = c.get("/api/setup").get_json()["v"]
    c.put("/api/setup", json={"spec": c.get("/api/sample/primary").get_json(), "why": "Opened a workbook"})
    after = c.get("/api/setup").get_json()["v"]
    code, j = _changes("A", v, [["school", "timetable", "Should not land"]])
    assert code == 200 and j["reset"] is True and j["replaced"] is True
    rec = c.get("/api/setup").get_json(); assert rec["v"] == after and rec["spec"]["school"].get("timetable") != "Should not land"

def _points_after(ops):
    """1 when applying ops takes a restore point (given one taken just now), else 0"""
    import datetime
    newest = lambda: (store._points() or [None])[-1]
    store._last_point[0] = datetime.datetime.now().timestamp(); before = newest()
    store.apply_changes(ops, "C"); return int(newest() != before)

def test_a_teacher_delete_takes_a_restore_point():
    t = c.get("/api/setup").get_json()["spec"]["teachers"][-1]
    assert _points_after([["del", "teachers", t["_id"]]]) == 1

def test_a_teacher_upload_of_ten_takes_a_restore_point_and_nine_does_not():
    adds = lambda tag, n: [["add", "teachers", {"_id": f"up{tag}{i}", "name": f"Upload Teacher {tag}{i}"}, ""] for i in range(n)]
    assert _points_after(adds("a", 10)) == 1
    assert _points_after(adds("b", 9)) == 0
    sets = [["set", "teachers", f"upa{i}", "allowance", 50] for i in range(9)] + [["merge", "teachers", "upa0", "can_teach", [{"levels": "All", "subject": "Qqq"}], []]]
    assert _points_after(sets) == 1
    lessons = c.get("/api/setup").get_json()["spec"]["lessons"][:10]
    assert _points_after([["set", "lessons", x["_id"], "students", 5] for x in lessons]) == 0

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
    code, j = _changes("H", v, [["set", "classes", sp["classes"][0]["_id"], "size", 99]], who=h)
    assert code == 200 and [x["i"] for x in j["refused"]] == [0] and "classes" in j["refused"][0]["why"].lower(), j
    assert c.get("/api/setup").get_json()["spec"]["classes"][0]["size"] != 99

def test_a_heads_refused_change_is_skipped_and_the_rest_applied():
    rec = c.get("/api/setup").get_json(); v = rec["v"]; lid = rec["spec"]["lessons"][0]["_id"]; name = rec["spec"]["school"]["name"]
    code, j = _changes("H", v, [["set", "lessons", lid, "students", 7], ["school", "name", "X"]], who=h)
    assert code == 200 and j["v"] == v + 1, (code, j)
    assert j["refused"] == [{"i": 1, "why": sync.head_may(rec["spec"], [["school", "name", "X"]])}], j
    r = c.get("/api/setup").get_json(); assert r["v"] == v + 1 and r["spec"]["lessons"][0].get("students") == 7 and r["spec"]["school"]["name"] == name
    assert store._log[-1]["ops"] == [["set", "lessons", lid, "students", 7]]          # the log holds only what was applied

def test_a_heads_batch_that_is_all_refused_changes_nothing():
    rec = c.get("/api/setup").get_json(); v = rec["v"]; cid = rec["spec"]["classes"][0]["_id"]; size = rec["spec"]["classes"][0].get("size")
    code, j = _changes("H", v, [["set", "classes", cid, "size", 77], ["school", "name", "X"]], who=h)
    assert code == 200 and j["v"] == v and [x["i"] for x in j["refused"]] == [0, 1], (code, j)
    r = c.get("/api/setup").get_json(); assert r["v"] == v and r["spec"]["classes"][0].get("size") == size and r["spec"]["school"]["name"] != "X"

def test_the_committees_reply_has_nothing_refused():
    rec = c.get("/api/setup").get_json(); v = rec["v"]
    code, j = _changes("C", v, [["school", "timetable", "Term 2"]]); assert code == 200 and not j.get("refused") and j["v"] == v + 1

def test_a_teacher_added_by_a_head_is_provisional():
    v = c.get("/api/setup").get_json()["v"]
    _changes("H", v, [["add", "teachers", {"_id": "newhire001", "name": "New Science teacher 1", "provisional": "No"}, ""]], who=h)
    t = next(x for x in c.get("/api/setup").get_json()["spec"]["teachers"] if x["_id"] == "newhire001"); assert t["provisional"] == "Yes"

def test_a_head_can_edit_only_provisional_teachers():
    v = c.get("/api/setup").get_json()["v"]
    _changes("H", v, [["add", "teachers", {"_id": "newhire002", "name": "Own hire"}, ""]], who=h)
    rec = c.get("/api/setup").get_json(); v = rec["v"]
    firm = next(x for x in rec["spec"]["teachers"] if x.get("provisional") != "Yes")
    code, j = _changes("H", v, [["set", "teachers", firm["_id"], "name", "Zed"]], who=h); assert code == 200 and len(j["refused"]) == 1
    code, j = _changes("H", v, [["set", "teachers", "newhire002", "provisional", "No"]], who=h); assert code == 200 and len(j["refused"]) == 1
    code, j = _changes("H", v, [["set", "teachers", "newhire002", "name", "Renamed"]], who=h); assert code == 200 and not j.get("refused")
    code, j = _changes("H", v, [["merge", "teachers", firm["_id"], "can_teach", [{"levels": "All", "subject": "Qqq"}], []]], who=h); assert code == 200 and not j.get("refused")
    ts = {x["_id"]: x for x in c.get("/api/setup").get_json()["spec"]["teachers"]}
    assert ts[firm["_id"]]["name"] != "Zed" and ts["newhire002"]["provisional"] == "Yes" and ts["newhire002"]["name"] == "Renamed"

def test_a_head_can_add_and_fill_in_a_teacher_in_one_request():
    v = c.get("/api/setup").get_json()["v"]
    code, _ = _changes("H", v, [["add", "teachers", {"_id": "newhire003", "name": "Batch hire"}, ""], ["set", "teachers", "newhire003", "short", "BH"]], who=h); assert code == 200
    t = next(x for x in c.get("/api/setup").get_json()["spec"]["teachers"] if x["_id"] == "newhire003"); assert t["provisional"] == "Yes" and t["short"] == "BH"

def test_a_heads_map_batch_is_applied_whole():
    # one department-map session: a new teacher, a basket, a class split off a shared whole-class row, and a deployment
    rec = c.get("/api/setup").get_json(); v = rec["v"]; sp = rec["spec"]
    row = next(x for x in sp["lessons"] if not x.get("block") and x.get("subject"))
    ops = [["add", "teachers", {"_id": "maphire001", "name": "New Mathematics teacher 1", "dept": "MA"}, ""],
           ["merge", "teachers", "maphire001", "can_teach", [{"subject": row["subject"], "levels": "All"}], []],
           ["set", "lessons", row["_id"], "classes", []],
           ["add", "lessons", {"_id": "mapsplit001", "level": row["level"], "subject": row["subject"], "block": None, "classes": row["classes"], "teachers": [], "students": row.get("students")}, row["_id"]],
           ["set", "lessons", "mapsplit001", "teachers", (row.get("teachers") or []) + ["New Mathematics teacher 1"]]]
    code, j = _changes("H", v, ops, who=h); assert code == 200 and not j.get("refused"), j
    now = c.get("/api/setup").get_json()["spec"]
    t = next(x for x in now["teachers"] if x["_id"] == "maphire001"); assert t["provisional"] == "Yes" and t["can_teach"] == [{"subject": row["subject"], "levels": "All"}]
    L = {x["_id"]: x for x in now["lessons"]}
    assert L[row["_id"]]["classes"] == [] and L["mapsplit001"]["classes"] == row["classes"] and L["mapsplit001"]["teachers"][-1] == "New Mathematics teacher 1"

def test_the_head_check_runs_on_the_setup_held_under_the_lock():
    rec = c.get("/api/setup").get_json(); v = rec["v"]; spec = rec["spec"]
    firm = next(x for x in spec["teachers"] if x.get("provisional") != "Yes")
    stale = [["set", "teachers", "newhire003", "name", "Late"]]
    assert sync.head_may(spec, stale) is None                      # judged on a copy taken earlier, the teacher is still provisional
    c.post("/api/setup/changes", json={"since": v, "client": "C", "ops": [["set", "teachers", "newhire003", "provisional", "No"]]})   # the committee confirms the teacher meanwhile
    v2 = c.get("/api/setup").get_json()["v"]
    v3, refused = store.apply_changes(stale, "H", filter=sync.head_split)
    assert v3 == v2 and [i for i, _ in refused] == [0] and "provisional" in refused[0][1]
    now = c.get("/api/setup").get_json()
    assert now["v"] == v2 and next(x for x in now["spec"]["teachers"] if x["_id"] == "newhire003")["name"] == "Batch hire"

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

def test_read_table_picks_the_teachers_sheet():
    import io, openpyxl
    wb = openpyxl.Workbook(); notes = wb.active; notes.title = "Notes"; notes.append(["Read me first"])
    ws = wb.create_sheet("4 Teachers"); ws.append(["Teachers of a made-up school"]); ws.append(["Teacher", "Short", "Department"]); ws.append(["Made Up Teacher", "MUT", "Science"])
    buf = io.BytesIO(); wb.save(buf); data = buf.getvalue()
    post = lambda who, form: who.post("/api/read-table", data={"file": (io.BytesIO(data), "list.xlsx"), **form}, content_type="multipart/form-data")
    r = post(c, {"sheet": "teachers"}); assert r.status_code == 200 and ["Made Up Teacher", "MUT", "Science"] in r.get_json()["rows"], r.get_json()
    r = post(c, {}); assert r.status_code == 200 and r.get_json()["rows"] == [["Read me first"]], r.get_json()
    if h: assert post(h, {"sheet": "teachers"}).status_code == 401

def test_read_table_reads_no_more_than_60_columns():
    import io, openpyxl
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Teachers"
    ws.append(["Teacher", "Short"]); ws.append(["Made Up Teacher", "MUT"]); ws.cell(row=1, column=300, value="far right")
    buf = io.BytesIO(); wb.save(buf)
    r = c.post("/api/read-table", data={"file": (io.BytesIO(buf.getvalue()), "list.xlsx"), "sheet": "teachers"}, content_type="multipart/form-data")
    rows = r.get_json()["rows"]; assert r.status_code == 200 and max(len(x) for x in rows) <= 60, max(len(x) for x in rows)
    assert ["Made Up Teacher", "MUT"] == rows[1][:2] and not any(rows[1][2:])

def test_the_workbook_carries_the_configuration_id():
    import io, openpyxl
    spec = c.get("/api/setup").get_json()["spec"]; v = c.get("/api/setup").get_json()["v"]
    wb = openpyxl.load_workbook(io.BytesIO(c.post("/api/build", json=spec).data), read_only=True)
    rows = {str(r[0]): r[1] for r in wb["Settings"].iter_rows(min_row=5, max_row=12, values_only=True) if r[0]}
    assert rows["Configuration id"] == f"v{v}", rows
    spec["school"]["name"] = "Changed School"
    wb = openpyxl.load_workbook(io.BytesIO(c.post("/api/build", json=spec).data), read_only=True)
    assert {str(r[0]): r[1] for r in wb["Settings"].iter_rows(min_row=5, max_row=12, values_only=True) if r[0]}["Configuration id"] == f"v{v}+"

def test_publish_uploaded_timetable():   # slow: solves the primary sample
    work = tempfile.mkdtemp(); setup, tt = os.path.join(work, "setup.xlsx"), os.path.join(work, "timetable.xlsx")
    env = dict(os.environ, PYTHONPATH=ROOT)
    subprocess.run([sys.executable, "-m", "ttgen", "sample", "primary", "--out", setup], check=True, env=env, cwd=ROOT)
    import openpyxl
    v = c.get("/api/setup").get_json()["v"]
    wbs = openpyxl.load_workbook(setup); ws0 = wbs["Settings"]
    for row in ws0.iter_rows(min_col=1, max_col=2):
        if row[0].value == "Configuration id": row[1].value = f"v{v}"
    wbs.save(setup)
    subprocess.run([sys.executable, "-m", "ttgen", "solve", setup, "--out", tt, "--time", "60"], env=env, cwd=ROOT)
    import openpyxl   # the agent's rule report rides on the timetable workbook
    wb = openpyxl.load_workbook(tt); ws = wb.create_sheet("Rule report"); ws.append(["No.", "Must / Prefer", "Applies to", "Rule", "Result", "How"]); ws.append([1, "Must", "Whole school", "Nothing in words", "Met", "Checked."])
    wc = wb.create_sheet("Choices used"); wc.append(["No.", "Item", "Used", "How"]); wc.append([1, "x", "First choice", ""]); wb.save(tt)
    r = c.post("/api/import-timetable", data={"publish": "1", "setup": (open(setup, "rb"), "setup.xlsx"), "timetable": (open(tt, "rb"), "timetable.xlsx")},
               content_type="multipart/form-data")
    j = r.get_json(); assert r.status_code == 200 and j["published"] is True, j
    assert j["rule_report"][0]["result"] == "Met" and j["typed"] == 0, j["rule_report"]
    assert j["config_id"] == f"v{v}" and j["config_state"] == "same", j
    assert j["choices_used"][0]["used"] == "First choice" and j["choice_problems"] and j["choices"] == 0, j
    p = c.get("/api/status").get_json()["published"]
    assert p and p["source"] == "timetable.xlsx" and p["rule_report"][0]["how"] == "Checked.", p
    assert p["choices_used"] == j["choices_used"] and p["choice_problems"] == j["choice_problems"] and p["config_id"] == j["config_id"], p
    t = A.app.test_client(); t.post("/login", data={"as": "teacher", "code": CODES["TEACHER_CODE"]})
    assert t.get("/timetable").status_code == 200

NEED_HEADS = {"test_a_head_can_change_groups_but_not_classes", "test_a_heads_map_batch_is_applied_whole", "test_a_heads_refused_change_is_skipped_and_the_rest_applied", "test_a_heads_batch_that_is_all_refused_changes_nothing", "test_a_teacher_added_by_a_head_is_provisional",
              "test_a_head_can_edit_only_provisional_teachers", "test_a_head_can_add_and_fill_in_a_teacher_in_one_request", "test_the_head_check_runs_on_the_setup_held_under_the_lock", "test_a_head_cannot_download_or_publish_or_replace"}

if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_") and (k != "test_publish_uploaded_timetable" or "--full" in sys.argv)
             and (h or k not in NEED_HEADS)]
    for t in tests: t(); print("ok", t.__name__)
    print(f"{len(tests)} checks passed")

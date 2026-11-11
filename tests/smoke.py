"""Server smoke checks. Run: .venv/bin/python tests/smoke.py   (add --full for the slow publish check)"""
import copy, os, secrets, subprocess, sys, tempfile
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
    assert set(j) == {"role", "codes", "code_problems", "volume", "setup_saved_at", "published", "draft"}, sorted(j)
    assert j["published"] is None and j["role"] == "committee" and j["draft"] is None

def test_old_runs_folder_is_harmless():
    assert c.get("/api/past-setups").status_code == 200

def _lessons_workbook(rows, report=()):   # the Lessons sheet an agent hands over: rows = [(day, start, periods, level, class, subject, teachers)]; report: lines of its Rule report
    import io, openpyxl
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Lessons"
    ws.append(["Lesson ID", "Day", "Start period", "End period", "Periods", "Starts", "Ends", "Level", "Block", "Classes", "Subject", "Group", "Teachers", "Room", "After school", "Rain room"])
    for i, (day, p, n, lv, cls, subj, tch) in enumerate(rows, 1): ws.append([i, day, p, p + n - 1, n, "", "", lv, "", cls, subj, "Entire Class", ", ".join(tch), "", "", ""])
    if report:
        wr = wb.create_sheet("Rule report"); wr.append(["No.", "Must / Prefer", "Applies to", "Rule", "Result", "How"])
        for line in report: wr.append(list(line))
    buf = io.BytesIO(); wb.save(buf); return buf.getvalue()

def _setup_workbook(spec):
    import io
    from ttgen.template import write_template
    d = tempfile.mkdtemp(); p = os.path.join(d, "setup.xlsx"); write_template(spec, p)
    return open(p, "rb").read()

def _draft_form(spec, rows, report=(), **more):
    import io
    return dict(setup=(io.BytesIO(_setup_workbook(spec)), "setup.xlsx"), timetable=(io.BytesIO(_lessons_workbook(rows, report)), "timetable.xlsx"), **more)

def _one_class_row(spec, skip=()):   # a step 5 row for exactly one class, with a teacher and periods
    return next(r for r in spec["lessons"] if not r.get("block") and r.get("code") == "Entire Class" and len(r.get("classes") or []) == 1 and r.get("teachers")
                and r.get("periods") and r["classes"][0] not in skip)

def _lesson_of(spec, row, teachers):
    lv = row.get("level") or next(x["level"] for x in spec["classes"] if x["class"] == row["classes"][0]); ds = spec["day_structure"][lv]; day = next(iter(ds))
    return (day, ds[day].index("L"), int(row["periods"]), lv, row["classes"][0], row["subject"], teachers)

def test_draft_needs_a_saved_setup():   # runs before any test that saves a setup
    r = c.post("/api/draft", data=_draft_form(A.sample("primary"), []), content_type="multipart/form-data")
    assert r.status_code == 409 and "Save the school's setup first" in r.get_json()["error"], r.get_json()
    assert c.get("/api/draft").get_json() == {"draft": None}

def test_setup_round_trip():
    spec = c.get("/api/sample/secondary").get_json()
    assert c.put("/api/setup", json=spec).status_code == 200
    assert c.get("/api/setup").get_json()["spec"]["school"]["name"] == spec["school"]["name"]

def test_the_days_keep_their_order_through_the_api():   # the grid lists days in the setup's order, not alphabetically
    spec = c.get("/api/sample/secondary").get_json(); ds = c.get("/api/setup").get_json()["spec"]["day_structure"]
    days = lambda d: list(next(iter(d.values())).keys())
    assert days(ds) == days(spec["day_structure"]) and days(ds)[:2] in (["Mon", "Tue"], ["Odd Mon", "Odd Tue"]), days(ds)

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
    for method, url in (("POST", "/api/build"), ("PUT", "/api/setup"), ("POST", "/api/draft"), ("GET", "/api/codes.csv"), ("POST", "/api/check"), ("GET", "/api/setup/copies"), ("POST", "/api/setup/restore")):
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

def _warn_keys(j): return [w["key"] for w in j["warnings"]]

def test_draft_upload_check_decide_publish():
    spec = A.sample("primary"); assert c.put("/api/setup", json=spec).status_code == 200
    spec = c.get("/api/setup").get_json()["spec"]; row = _one_class_row(spec)
    rows = [_lesson_of(spec, row, ["Nobody"])]
    r = c.post("/api/draft", data=_draft_form(spec, rows), content_type="multipart/form-data"); j = r.get_json()
    assert r.status_code == 200 and j["open"] == len(j["warnings"]) and j["config_state"] in ("same", "older", "unknown", "unsaved"), j
    assert len(set(_warn_keys(j))) == len(j["warnings"]) and j["left"] == 0 and j["fixes"] == [] and j["lessons"] == 1
    k = f"dep:C:{row['classes'][0]}:{row['subject']}:teachers"; assert k in _warn_keys(j)
    j2 = c.post("/api/draft/decide", json={"key": k, "answer": "left"}).get_json()
    assert j2["left"] == 1 and j2["open"] == j["open"] and next(w for w in j2["warnings"] if w["key"] == k)["decision"]["answer"] == "left"
    j3 = c.post("/api/draft/decide", json={"key": k, "answer": "step5"}).get_json(); assert k not in _warn_keys(j3), _warn_keys(j3)[:5]
    assert j3["step5"] == 1 and store.read_json(os.path.join(store.DATA, "draft", "decisions.json"))[k]["answer"] == "step5"
    now = c.get("/api/setup").get_json()["spec"]; assert next(x["teachers"] for x in now["lessons"] if x["_id"] == row["_id"]) == ["Nobody"]
    assert any("Before updating step 5 from the timetable" == x["what"] for x in c.get("/api/setup/copies").get_json())
    kp = next((w["key"] for w in j3["warnings"] if w["key"].endswith(":periods")), None)
    if kp is None:   # make a periods warning: one period too few for another class
        row2 = _one_class_row(spec, skip=(row["classes"][0],)); l2 = _lesson_of(spec, row2, row2["teachers"]); l2 = l2[:2] + (max(1, l2[2] - 1),) + l2[3:]
        c.post("/api/draft", data=_draft_form(spec, [_lesson_of(spec, row, ["Nobody"]), l2]), content_type="multipart/form-data")
        kp = f"dep:C:{row2['classes'][0]}:{row2['subject']}:periods"
    r = c.post("/api/draft/decide", json={"key": kp, "answer": "step5"}); assert r.status_code == 400 and "step 3" in r.get_json()["error"], r.get_json()
    st = c.get("/api/status").get_json()["draft"]; assert st["open"] == c.get("/api/draft").get_json()["open"] and st["source"] == "timetable.xlsx" and st["uploaded_at"]
    assert c.post("/api/draft/decide", json={"key": k, "answer": "open"}).status_code == 200
    assert h is None or h.post("/api/draft/decide", json={"key": k, "answer": "left"}).status_code == 401

def test_draft_decisions_survive_a_setup_change_and_stale_ones_go():
    spec = c.get("/api/setup").get_json()["spec"]; row = _one_class_row(spec); other = _one_class_row(spec, skip=(row["classes"][0],))
    c.post("/api/draft", data=_draft_form(spec, [_lesson_of(spec, row, row["teachers"])]), content_type="multipart/form-data")
    k = f"dep:C:{other['classes'][0]}:{other['subject']}:missing"; j = c.get("/api/draft").get_json(); assert k in _warn_keys(j)
    assert c.post("/api/draft/decide", json={"key": k, "answer": "left"}).get_json()["left"] >= 1
    v = c.get("/api/setup").get_json()["v"]
    assert c.post("/api/setup/changes", json={"client": "t", "since": v, "ops": [["del", "lessons", other["_id"]]]}).status_code == 200
    j = c.get("/api/draft").get_json(); assert k not in _warn_keys(j) and j["setup_version"] == f"v{v + 1}"
    assert k not in store.read_json(os.path.join(store.DATA, "draft", "decisions.json"), {})
    r = c.post("/api/draft/decide", json={"key": k, "answer": "step5"}); assert r.status_code == 400 and "no longer on the list" in r.get_json()["error"]

def test_a_new_upload_keeps_left_decisions():
    spec = c.get("/api/setup").get_json()["spec"]; row = _one_class_row(spec); rows = [_lesson_of(spec, row, ["Somebody"])]
    c.post("/api/draft", data=_draft_form(spec, rows), content_type="multipart/form-data")
    k = f"dep:C:{row['classes'][0]}:{row['subject']}:teachers"; c.post("/api/draft/decide", json={"key": k, "answer": "left"})
    j = c.post("/api/draft", data=_draft_form(spec, rows), content_type="multipart/form-data").get_json()
    assert j["left"] == 1 and next(w for w in j["warnings"] if w["key"] == k)["decision"]["answer"] == "left"
    store.write_json(os.path.join(store.DATA, "draft", "meta.json"), dict(store.read_json(os.path.join(store.DATA, "draft", "meta.json")), fixes=[{"x": 1}]))
    r = c.post("/api/draft", data=_draft_form(spec, rows), content_type="multipart/form-data")
    assert r.status_code == 409 and r.get_json() == {"error": "The draft has fixes that were never published.", "fixes": 1}, r.get_json()
    assert c.post("/api/draft", data=_draft_form(spec, rows, replace="1"), content_type="multipart/form-data").status_code == 200
    assert c.get("/api/draft").get_json()["fixes"] == []

def test_draft_for_another_school_is_said():
    spec = c.get("/api/setup").get_json()["spec"]; row = _one_class_row(spec); theirs = A.sample("primary"); theirs["school"]["name"] = "Somewhere Else Primary"
    j = c.post("/api/draft", data=_draft_form(theirs, [_lesson_of(spec, row, row["teachers"])]), content_type="multipart/form-data").get_json()
    assert j["other_school"] == spec["school"]["name"], j.get("other_school")
    assert c.post("/api/draft", data=dict(setup=(__import__("io").BytesIO(b"not a workbook"), "s.xlsx"), timetable=(__import__("io").BytesIO(b"x"), "t.xlsx")), content_type="multipart/form-data").status_code == 400

def test_a_decision_made_during_a_build_is_not_lost():
    import draft
    spec = c.get("/api/setup").get_json()["spec"]; row = _one_class_row(spec, skip=("zz",)); rows = [_lesson_of(spec, row, ["Somebody"])]
    c.post("/api/draft", data=_draft_form(spec, rows), content_type="multipart/form-data")
    ws = c.get("/api/draft").get_json()["warnings"]; k = ws[0]["key"]; k2 = ws[1]["key"]
    orig = draft._build
    def slow(*a, **kw):
        j = orig(*a, **kw); store.write_json(os.path.join(draft.DIR, "decisions.json"), {k2: dict(answer="left", at="now")}); return j
    draft._build = slow
    try: got = c.get("/api/draft").get_json()
    finally: draft._build = orig
    assert store.read_json(os.path.join(draft.DIR, "decisions.json"))[k2]["answer"] == "left" and c.get("/api/draft").get_json()["left"] == 1
    assert k != k2

def test_the_draft_says_which_school_the_file_is_for_and_one_build_per_upload():
    import draft
    spec = c.get("/api/setup").get_json()["spec"]; row = _one_class_row(spec); theirs = A.sample("primary"); theirs["school"]["name"] = "Somewhere Else Primary"
    builds = []; orig = draft._build
    draft._build = lambda *a, **kw: (builds.append(1), orig(*a, **kw))[1]
    from ttgen import export; reads = []; ot = export.read_template
    export.read_template = lambda *a, **kw: (reads.append(1), ot(*a, **kw))[1]
    try: j = c.post("/api/draft", data=_draft_form(theirs, [_lesson_of(spec, row, row["teachers"])]), content_type="multipart/form-data").get_json()
    finally: draft._build = orig; export.read_template = ot
    assert j["file_school"] == "Somewhere Else Primary" and j["school"] == spec["school"]["name"] and j["other_school"] == spec["school"]["name"], j["school"]
    assert len(builds) == 1 and len(reads) == 1, (builds, reads)

def test_a_step5_change_does_not_land_on_a_replaced_setup():
    import draft
    spec = c.get("/api/setup").get_json()["spec"]; row = _one_class_row(spec); rows = [_lesson_of(spec, row, ["Elsewhere"])]
    c.post("/api/draft", data=_draft_form(spec, rows), content_type="multipart/form-data")
    k = f"dep:C:{row['classes'][0]}:{row['subject']}:teachers"; orig = draft._build
    def replaced(*a, **kw):
        j = orig(*a, **kw); store.replace_setup(c.get("/api/setup").get_json()["spec"], "test"); return j
    draft._build = replaced
    try: r = c.post("/api/draft/decide", json={"key": k, "answer": "step5"})
    finally: draft._build = orig
    assert r.status_code == 400 and "replaced" in r.get_json()["error"], r.get_json()
    assert next(x["teachers"] for x in c.get("/api/setup").get_json()["spec"]["lessons"] if x["_id"] == row["_id"]) != ["Elsewhere"]

def test_step5_on_an_extra_lesson_adds_the_row_once_at_the_end():   # finding 1: the add had no id and was skipped
    import draft, threading, time
    spec = c.get("/api/setup").get_json()["spec"]; row = _one_class_row(spec); cls, subj = row["classes"][0], row["subject"]
    v = c.get("/api/setup").get_json()["v"]
    assert c.post("/api/setup/changes", json={"client": "t", "since": v, "ops": [["del", "lessons", row["_id"]]]}).status_code == 200
    spec = c.get("/api/setup").get_json()["spec"]; lesson = _lesson_of(spec, row, row["teachers"]); lesson = lesson[:3] + ("",) + lesson[4:]   # no Level column value
    c.post("/api/draft", data=_draft_form(spec, [lesson]), content_type="multipart/form-data")
    k = f"dep:C:{cls}:{subj}:extra"; j = c.get("/api/draft").get_json(); assert k in _warn_keys(j), _warn_keys(j)[:8]
    assert next(w for w in j["warnings"] if w["key"] == k)["ops"], "the extra lesson has no step 5 update"
    orig, out = draft._build, []
    def slow(*a, **kw): r = orig(*a, **kw); time.sleep(0.3); return r   # a double click: the second request comes while the first is building
    def click():
        try: out.append(draft.decide(k, "step5"))
        except ValueError as e: out.append(e)
    draft._build = slow
    try:
        ts = [threading.Thread(target=click) for _ in range(2)]
        for t_ in ts: t_.start()
        for t_ in ts: t_.join()
    finally: draft._build = orig
    now = c.get("/api/setup").get_json()["spec"]["lessons"]; added = [x for x in now if x["subject"] == subj and x.get("classes") == [cls]]
    assert len(added) == 1 and now[-1] == added[0], (len(added), now[-1] if now else None)
    lv = next(x["level"] for x in spec["classes"] if x["class"] == cls)
    assert added[0]["level"] == lv and added[0]["teachers"] == sorted(row["teachers"]) and added[0].get("_id") and not added[0].get("block"), added[0]
    assert sum(1 for o in out if isinstance(o, dict)) == 1 and sum(1 for o in out if isinstance(o, ValueError)) == 1, out
    j = c.get("/api/draft").get_json(); assert k not in _warn_keys(j) and f"dep:C:{cls}:{subj}:periods" not in _warn_keys(j), [x for x in _warn_keys(j) if cls in x]

def test_a_draft_that_cannot_be_checked_is_a_sentence_not_a_500():   # finding 5
    from ttgen import verify
    spec = c.get("/api/setup").get_json()["spec"]; row = _one_class_row(spec)
    real = verify.warnings
    def boom(*a, **kw): raise KeyError("something odd")
    verify.warnings = boom
    try:
        r = c.post("/api/draft", data=_draft_form(spec, [_lesson_of(spec, row, row["teachers"])]), content_type="multipart/form-data")
        g = c.get("/api/draft")
    finally: verify.warnings = real
    for x in (r, g): assert x.status_code == 400 and x.get_json()["error"].startswith("Could not check the timetable against the setup"), (x.status_code, x.get_data()[:200])
    assert c.get("/api/draft").status_code == 200

def _grid_draft():   # three lessons of two classes: U's Art for 1A (Mon p1), Art for 1B (Tue p1) and a Mathematics of 1B (Wed p3) that U also teaches
    spec = c.get("/api/setup").get_json()["spec"]; ds = spec["day_structure"]["P1"]; days = list(ds); p = ds[days[0]].index("L"); U = "Umairah Tan"
    rows = [(days[0], p, 1, "P1", "1A", "Art", [U]), (days[1], p, 1, "P1", "1B", "Art", [U]), (days[2], p + 2, 1, "P1", "1B", "Mathematics", [U])]
    assert c.post("/api/draft", data=_draft_form(spec, rows, replace="1"), content_type="multipart/form-data").status_code == 200
    return days, p

def _lid(cls="1A", subject="Art"):
    return next(x["id"] for x in c.get("/api/draft/grid?view=class&name=" + cls).get_json()["lessons"] if x["subject"] == subject)

def test_the_grid_of_a_class_and_a_teacher():
    A.app.testing = True; days, p = _grid_draft()
    j = c.get("/api/draft/grid?view=class&name=1A").get_json()
    assert j["view"] == "class" and j["name"] == "1A" and j["days"] == days and len(j["codes"]) == len(days) and "1A" in j["classes"] and "Umairah Tan" in j["teachers"], j
    assert [(x["subject"], x["d"], x["p"], x["n"]) for x in j["lessons"]] == [("Art", 0, p, 1)] and j["lessons"][0]["what"] == "Art for 1A" and set(j["lessons"][0]) == {"id", "group", "subject", "classes", "teachers", "room", "d", "p", "n", "block", "what", "short", "tshorts"}
    r0 = j["lessons"][0]; assert r0["short"] and isinstance(r0["short"], str) and len(r0["tshorts"]) == len(r0["teachers"]) and all(r0["tshorts"]), r0
    assert any(s["key"] == "C:1A:Art" and s["have"] == 1 for s in j["short"]) and len(j["times"]) == j["NP"]
    t = c.get("/api/draft/grid?view=teacher&name=Umairah%20Tan").get_json()
    assert len(t["lessons"]) == 3 and t["short"] == [] and all(set(r) <= set("L.") for r in t["codes"]) and "L" in t["codes"][0]
    assert c.get("/api/draft/grid?view=class&name=Nobody").status_code == 400
    assert c.get("/api/draft/grid?view=room&name=1A").status_code == 400

def test_the_options_of_a_lesson_and_of_an_add():
    _grid_draft(); lid = _lid(); j = c.get(f"/api/draft/options?id={lid}").get_json()
    assert set(j) == {"slots", "teachers", "rooms", "delete", "key"} and j["key"] == "C:1A:Art" and j["delete"]["state"] in ("ok", "prefer", "no", "na") and j["slots"]
    assert all(set(s) == {"d", "p", "state", "why", "swap", "also"} for s in j["slots"])
    r = c.get(f"/api/draft/options?id={lid}&group=Entire%20Class"); assert r.status_code == 200
    a = c.get("/api/draft/options?add=C:1A:Art&n=1").get_json(); assert set(a) == {"slots"} and a["slots"] and set(a["slots"][0]) == {"d", "p", "state", "why"}
    assert c.get("/api/draft/options?id=99999").status_code == 400 and c.get("/api/draft/options").status_code == 400

def test_a_fix_moves_the_lesson_and_undo_brings_it_back():
    _grid_draft(); lid = _lid(); s = next(s for s in c.get(f"/api/draft/options?id={lid}").get_json()["slots"] if s["state"] == "ok" and not s["swap"])
    j = c.post("/api/draft/fix", json=dict(kind="move", id=lid, d=s["d"], p=s["p"])).get_json(); assert len(j["fixes"]) == 1 and j["fixes"][0]["text"].startswith("Moved "), j
    g = c.get("/api/draft/grid?view=class&name=1A").get_json(); assert (s["d"], s["p"]) in {(x["d"], x["p"]) for x in g["lessons"] if x["id"] == lid}
    assert c.get("/api/status").get_json()["draft"]["open"] == j["open"]
    assert store.read_json(os.path.join(store.DATA, "draft", "meta.json"))["fixes"][0]["at"]
    j = c.post("/api/draft/undo").get_json(); assert j["fixes"] == [] and c.post("/api/draft/undo").status_code == 400
    assert c.post("/api/draft/undo").get_json() == {"error": "There is nothing to undo."}

def test_a_typed_rule_is_checked_again_after_a_fix_and_the_lead_can_settle_it():
    _grid_draft(); spec = c.get("/api/setup").get_json()["spec"]; ds = spec["day_structure"]["P1"]; days = list(ds); p = ds[days[0]].index("L")
    saved = copy.deepcopy(spec)
    spec["rules"] = list(spec.get("rules") or []) + [dict(scope="School", target="Whole school", rule="In words", text="Nobody is rushed", strength="Prefer", week="Both", day="All")]
    try:
        assert c.put("/api/setup", json=spec).status_code == 200
        rows = [(days[0], p, 1, "P1", "1A", "Art", ["Umairah Tan"]), (days[1], p, 1, "P1", "1B", "Art", ["Umairah Tan"])]
        rep = [(1, "Prefer", "Whole school", "Nobody is rushed", "Met", "Checked.")]
        assert c.post("/api/draft", data=_draft_form(spec, rows, rep, replace="1"), content_type="multipart/form-data").status_code == 200
        j = c.get("/api/draft").get_json(); assert "typed:1:again" not in _warn_keys(j) and j["typed"] == 1 and not any(w["kind"] == "typed" for w in j["warnings"]), j["warnings"]
        lid = _lid(); s = next(s for s in c.get(f"/api/draft/options?id={lid}").get_json()["slots"] if s["state"] == "ok" and not s["swap"])
        j = c.post("/api/draft/fix", json=dict(kind="move", id=lid, d=s["d"], p=s["p"])).get_json(); w = next(w for w in j["warnings"] if w["key"] == "typed:1:again")
        assert w["kind"] == "typed" and w["strength"] == "Prefer" and w["decision"] is None and w["text"] == "T1 was reported met, but lessons it is about were changed in the app. Check it again: Nobody is rushed.", w
        n0 = j["open"]; assert c.post("/api/draft/decide", json=dict(key="deployment:x", answer="met")).status_code == 400
        r = c.post("/api/draft/decide", json=dict(key="typed:1:again", answer="met")); j = r.get_json(); w = next(w for w in j["warnings"] if w["key"] == "typed:1:again")
        assert r.status_code == 200 and w["decision"]["answer"] == "met" and w["decision"]["at"] and j["open"] == n0 - 1, j
        dec = store.read_json(os.path.join(store.DATA, "draft", "decisions.json")); assert dec["typed:1:again"]["answer"] == "met"
        r = c.post("/api/draft/decide", json=dict(key=_warn_keys(j)[0], answer="met")); assert r.status_code == 400 and r.get_json() == {"error": "That answer is only for a rule to check again."}, r.get_json()
        assert c.post("/api/draft/decide", json=dict(key="typed:1:again", answer="open")).status_code == 200
        assert next(w for w in c.get("/api/draft").get_json()["warnings"] if w["key"] == "typed:1:again")["decision"] is None
    finally:
        c.put("/api/setup", json=saved)

def test_deleting_a_lesson_of_a_class_marks_its_typed_rule_to_check_again():
    spec = c.get("/api/setup").get_json()["spec"]; saved = copy.deepcopy(spec)
    spec["rules"] = list(spec.get("rules") or []) + [dict(scope="Class", target="1A", rule="In words", text="1A is not rushed", strength="Must", week="Both", day="All")]
    try:
        assert c.put("/api/setup", json=spec).status_code == 200
        rows = [("Mon", 1, 1, "P1", "1A", "Zzz Extra", ["Umairah Tan"])]; rep = [(1, "Must", "1A", "1A is not rushed", "Met", "Checked.")]
        assert c.post("/api/draft", data=_draft_form(spec, rows, rep, replace="1"), content_type="multipart/form-data").status_code == 200
        assert "typed:1:again" not in _warn_keys(c.get("/api/draft").get_json())
        j = c.post("/api/draft/fix", json=dict(kind="delete", id=_lid("1A", "Zzz Extra"))).get_json(); assert len(j["fixes"]) == 1, j
        w = next(w for w in j["warnings"] if w["key"] == "typed:1:again"); assert w["text"].endswith("Check it again: 1A is not rushed."), w
    finally:
        c.put("/api/setup", json=saved)

def test_an_add_without_a_room_and_a_delete():
    _grid_draft(); a = c.get("/api/draft/options?add=C:1A:Art&n=1").get_json()["slots"]; s = next(s for s in a if s["state"] in ("ok", "prefer"))
    j = c.post("/api/draft/fix", json=dict(kind="add", key="C:1A:Art", d=s["d"], p=s["p"], n=1)).get_json(); assert j["fixes"][0]["text"].startswith("Added "), j
    assert len(c.get("/api/draft/grid?view=class&name=1A").get_json()["lessons"]) == 2
    r = c.post("/api/draft/fix", json=dict(kind="delete", id=_lid("1B", "Mathematics"))); assert r.status_code == 400 and "step 3 plans" in r.get_json()["error"], r.get_json()   # the plan would be broken
    spec = c.get("/api/setup").get_json()["spec"]; rows = [("Mon", 1, 1, "P1", "1A", "Zzz Extra", ["Umairah Tan"])]
    assert c.post("/api/draft", data=_draft_form(spec, rows, replace="1"), content_type="multipart/form-data").status_code == 200
    j = c.post("/api/draft/fix", json=dict(kind="delete", id=_lid("1A", "Zzz Extra"))).get_json(); assert len(j["fixes"]) == 1 and j["fixes"][0]["text"].startswith("Deleted "), j
    assert c.post("/api/draft/fix", json=dict(kind="nonsense")).status_code == 400 and c.post("/api/draft/fix", json=[1]).status_code == 400

def test_a_teacher_fix_and_a_room_fix():
    _grid_draft(); lid = _lid(); o = c.get(f"/api/draft/options?id={lid}").get_json()
    t = next(x for x in o["teachers"] if x["state"] in ("ok", "prefer"))["teachers"]
    j = c.post("/api/draft/fix", json=dict(kind="teacher", key="C:1A:Art", teachers=t)).get_json(); assert j["fixes"][0]["text"].startswith("Art for 1A is now taught by "), j
    assert all(x["teachers"] == t for x in c.get("/api/draft/grid?view=class&name=1A").get_json()["lessons"] if x["subject"] == "Art")
    rm = next(x for x in c.get(f"/api/draft/options?id={lid}").get_json()["rooms"] if x["state"] in ("ok", "prefer"))["room"]
    j = c.post("/api/draft/fix", json=dict(kind="room", id=lid, group="Entire Class", room=rm)).get_json(); assert j["fixes"][1]["text"].startswith("Art for 1A on ") and f"is now in {rm}" in j["fixes"][1]["text"], j
    assert next(x for x in c.get("/api/draft/grid?view=class&name=1A").get_json()["lessons"] if x["id"] == lid)["room"] == rm

def test_options_of_a_group_row_name_that_groups_key():
    spec = c.get("/api/setup").get_json()["spec"]; ds = spec["day_structure"]["P1"]; day = list(ds)[0]; p = ds[day].index("L")
    import io, openpyxl
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Lessons"
    ws.append(["Lesson ID", "Day", "Start period", "End period", "Periods", "Starts", "Ends", "Level", "Block", "Classes", "Subject", "Group", "Teachers", "Room", "After school", "Rain room"])
    for subj, g, t in (("Chinese Language", "1CL1", "Adeline Tan"), ("Malay Language", "1ML1", "Charmaine Yeo")): ws.append([1, day, p, p, 1, "", "", "P1", "P1 Mother Tongue", "1A, 1B, 1C", subj, g, t, "", "", ""])
    buf = io.BytesIO(); wb.save(buf)
    assert c.post("/api/draft", data=dict(setup=(io.BytesIO(_setup_workbook(spec)), "setup.xlsx"), timetable=(io.BytesIO(buf.getvalue()), "timetable.xlsx"), replace="1"), content_type="multipart/form-data").status_code == 200
    j = c.get("/api/draft/options?id=1&group=1ML1").get_json(); assert j["key"] == "G:1ML1" and j["rooms"] is not None, j
    assert all(x["teachers"] != ["Adeline Tan"] for x in j["teachers"]) and any(x["teachers"] != ["Charmaine Yeo"] for x in j["teachers"]), j["teachers"]
    assert c.get("/api/draft/options?id=1&group=1CL1").get_json()["key"] == "G:1CL1" and c.get("/api/draft/options?id=1").get_json()["key"] == "G:1CL1"

def _free_slot(lid, skip=()):   # the first slot of a lesson the lead is allowed to move it to, that is not skip
    return next(s for s in c.get(f"/api/draft/options?id={lid}").get_json()["slots"] if s["state"] in ("ok", "prefer") and not s["swap"] and (s["d"], s["p"]) not in skip)

def _mv(lid, s): return dict(kind="move", id=lid, d=s["d"], p=s["p"])

def test_suggest_for_a_warning_and_for_one_that_is_gone():
    _grid_draft(); k = "dep:C:1B:Mathematics:teachers"; assert k in _warn_keys(c.get("/api/draft").get_json())   # U teaches it, step 5 names another
    j = c.get("/api/draft/suggest", query_string={"key": k}).get_json()
    assert set(j) == {"suggestions", "none", "blocked"} and j["suggestions"] and j["suggestions"][0]["fixes"][0]["kind"] == "teacher", j
    assert set(j["suggestions"][0]) == {"fixes", "text", "disturbs", "state", "moved"} and c.get("/api/draft").get_json()["fixes"] == []
    r = c.get("/api/draft/suggest", query_string={"key": "dep:C:Nobody:Nothing:teachers"}); assert r.status_code == 400 and r.get_json() == {"error": "That warning is no longer on the list."}

def test_a_batch_is_all_or_nothing_and_undone_together():
    _grid_draft(); a, b = _lid("1A", "Art"), _lid("1B", "Art"); s1 = _free_slot(a); s2 = _free_slot(b, skip={(s1["d"], s1["p"])})
    j = c.post("/api/draft/fix", json=_mv(b, s2)).get_json(); assert len(j["fixes"]) == 1 and j["fixes"][0]["batch"] is None   # the grid's own click: no batch
    before = c.get("/api/draft").get_json()
    r = c.post("/api/draft/fixes", json={"fixes": [_mv(a, s1), dict(kind="move", id=_lid("1B", "Mathematics"), d=s1["d"], p=s1["p"])]})   # the second clashes with the first, after it
    assert r.status_code == 400 and "is teaching" in r.get_json()["error"] and c.get("/api/draft").get_json()["fixes"] == before["fixes"], r.get_json()
    j = c.post("/api/draft/fixes", json={"fixes": [_mv(a, s1), _mv(b, _free_slot(b, skip={(s1["d"], s1["p"])}))]}).get_json()
    assert len(j["fixes"]) == len(before["fixes"]) + 2 and j["fixes"][-1]["batch"] == j["fixes"][-2]["batch"] is not None and j["fixes"][-1]["text"].startswith("Moved "), j["fixes"]
    saved = store.read_json(os.path.join(store.DATA, "draft", "meta.json"))["fixes"]; assert all(f["at"] and f["batch"] for f in saved[-2:]) and "batch" not in saved[0]
    j = c.post("/api/draft/undo").get_json(); assert j["fixes"] == before["fixes"]
    j = c.post("/api/draft/fixes", json={"fixes": [_mv(a, s1)]}).get_json(); assert j["fixes"][-1]["batch"]   # a list of one is a batch too
    assert c.post("/api/draft/undo").get_json()["fixes"] == before["fixes"] and c.post("/api/draft/undo").get_json()["fixes"] == []   # the single click goes alone
    for body in ({"fixes": []}, {"fixes": [_mv(a, s1)] * 3}, {"fixes": "x"}, {"nothing": 1}, [1]):
        r = c.post("/api/draft/fixes", json=body); assert r.status_code == 400, body
    assert c.post("/api/draft/fixes", json={"fixes": [_mv(a, s1)] * 3}).get_json() == {"error": "Send one or two fixes."} and c.get("/api/draft").get_json()["fixes"] == []

def test_a_batch_add_without_a_room_gets_one():
    _grid_draft(); s = next(s for s in c.get("/api/draft/options?add=C:1A:Art&n=1").get_json()["slots"] if s["state"] in ("ok", "prefer"))
    j = c.post("/api/draft/fixes", json={"fixes": [dict(kind="add", key="C:1A:Art", d=s["d"], p=s["p"], n=1)]}).get_json()
    assert j["fixes"][-1]["kind"] == "add" and j["fixes"][-1]["batch"] and j["fixes"][-1]["text"].startswith("Added "), j["fixes"]
    assert c.post("/api/draft/fixes", json={"fixes": [dict(kind="add", key="C:1A:Art", d=s["d"], p=s["p"], n=0)]}).status_code == 400

def _pair_draft():   # Task 2's frame: 1A's English at period 0 breaks a Must rule; its only open slot S is taken by Sabrina Koh's lesson of 1B, which can itself move
    import io, openpyxl
    spec = c.get("/api/setup").get_json()["spec"]; ds = spec["day_structure"]["P1"]; days = list(ds); every = [(d, p) for d in range(len(days)) for p in range(len(ds[days[d]])) if ds[days[d]][p] == "L"]; S, T0 = (2, 3), "Sabrina Koh"
    assert S in every and (3, 5) in every
    rows = [(days[0], 0, 1, "P1", "1A", "English Language", [T0]), (days[S[0]], S[1], 1, "P1", "1B", "Other", [T0])]
    rows += [(days[d], p, 1, "P1", "1A", "Art", ["Umairah Tan"]) for d, p in every if (d, p) != S] + [(days[d], p, 1, "P1", "1B", "Music", ["Jasper Wong"]) for d, p in every if (d, p) not in (S, (3, 5))]
    saved = copy.deepcopy(spec); spec["rules"] = list(spec.get("rules") or []) + [dict(scope="Class", target="1A", rule="Not in periods", week="Both", day="All", strength="Must", **{"from": 0, "to": 0})]
    assert c.put("/api/setup", json=spec).status_code == 200
    assert c.post("/api/draft", data=_draft_form(spec, rows, replace="1"), content_type="multipart/form-data").status_code == 200
    w = next(w for w in c.get("/api/draft").get_json()["warnings"] if w["key"].startswith("rule:") and "English Language" in w["text"])
    return saved, w["key"], _lid("1A", "English Language"), _lid("1B", "Other"), _lid("1B", "Music")

def test_a_stale_pair_is_refused_whole():
    saved, k, eng, other, music = _pair_draft()
    try:
        S = c.get("/api/draft/suggest", query_string={"key": k}).get_json()["suggestions"]; pair = next(s for s in S if len(s["fixes"]) == 2)
        assert pair["fixes"] == [dict(kind="move", id=other, d=3, p=5), dict(kind="move", id=eng, d=2, p=3)], S
        assert c.post("/api/draft/fix", json=dict(kind="move", id=music, d=3, p=5)).status_code == 200   # another fix takes the slot the pair moves the first lesson to
        before = c.get("/api/draft").get_json()["fixes"]; assert len(before) == 1
        r = c.post("/api/draft/fixes", json={"fixes": pair["fixes"]}); assert r.status_code == 400 and r.get_json()["error"], r.get_json()
        assert c.get("/api/draft").get_json()["fixes"] == before
        assert c.post("/api/draft/preview", json={"fixes": pair["fixes"]}).get_json()["state"] == "no"
    finally: c.put("/api/setup", json=saved)

def test_two_identical_fixes_are_refused_whole_and_undo_takes_a_batch_whole():
    _grid_draft(); a, b = _lid("1A", "Art"), _lid("1B", "Art"); s1 = _free_slot(a); s2 = _free_slot(b, skip={(s1["d"], s1["p"])}); x = _mv(a, s1)
    r = c.post("/api/draft/fixes", json={"fixes": [x, x]}); assert r.status_code == 400 and r.get_json() == {"error": "That changes nothing."} and c.get("/api/draft").get_json()["fixes"] == []
    c.post("/api/draft/fixes", json={"fixes": [x, _mv(b, s2)]}); s3 = _free_slot(_lid("1B", "Mathematics"), skip={(s1["d"], s1["p"]), (s2["d"], s2["p"])})
    assert c.post("/api/draft/fix", json=_mv(_lid("1B", "Mathematics"), s3)).status_code == 200 and len(c.get("/api/draft").get_json()["fixes"]) == 3
    assert len(c.post("/api/draft/undo").get_json()["fixes"]) == 2 and c.post("/api/draft/undo").get_json()["fixes"] == []   # the single alone, then the pair together

def test_fix_many_writes_nothing_when_a_fix_was_skipped():
    import helper
    _grid_draft(); a, b = _lid("1A", "Art"), _lid("1B", "Art"); real = helper.chain
    helper.chain = lambda *x, **k: dict(real(*x, **k), texts=["only one"])
    try: r = c.post("/api/draft/fixes", json={"fixes": [_mv(a, _free_slot(a)), _mv(b, _free_slot(b, skip={(_free_slot(a)["d"], _free_slot(a)["p"])}))]})
    finally: helper.chain = real
    assert r.status_code == 400 and r.get_json() == {"error": "That fix could not be made. Check the list again."} and c.get("/api/draft").get_json()["fixes"] == []

def _marks(j, cls): return {x["id"]: (x["mark"], x.get("was")) for x in next(k for k in j["classes"] if k["name"] == cls)["lessons"]}

def test_the_preview_shows_every_class_touched_and_changes_nothing():
    days, p = _grid_draft(); a, b, m3 = _lid("1A", "Art"), _lid("1B", "Art"), _lid("1B", "Mathematics")
    before = c.get("/api/draft").get_json()["fixes"]
    j = c.post("/api/draft/preview", json={"fixes": [dict(kind="swap", a=a, b=b)]}).get_json()
    assert set(j) == {"state", "why", "texts", "classes", "gone"} and j["state"] in ("ok", "prefer") and j["texts"][0].startswith("Swapped ") and j["gone"] == [], j
    assert sorted(k["name"] for k in j["classes"]) == ["1A", "1B"] and all(set(k) >= {"view", "name", "days", "NP", "times", "codes", "lessons", "classes", "teachers", "short"} for k in j["classes"])
    assert _marks(j, "1A") == {a: ("moved", dict(d=0, p=p))} and _marks(j, "1B") == {b: ("moved", dict(d=1, p=p)), m3: ("", None)}, j["classes"]
    g = next(k for k in j["classes"] if k["name"] == "1A")["lessons"][0]; assert (g["d"], g["p"]) == (1, p) and set(g) >= {"id", "group", "subject", "classes", "teachers", "room", "d", "p", "n", "block", "what", "tshorts", "mark"}
    assert c.get("/api/draft").get_json()["fixes"] == before and c.get(f"/api/draft/grid?view=class&name=1A").get_json()["lessons"][0]["d"] == 0
    r = c.post("/api/draft/preview", json={"fixes": [dict(kind="move", id=a, d=2, p=p + 2)]}); j = r.get_json()   # refused: 200, and the timetable as it was
    assert r.status_code == 200 and j["state"] == "no" and "is teaching" in j["why"] and j["classes"] == [] and j["gone"] == [], j
    j = c.post("/api/draft/preview", json={"fixes": [_mv(a, _free_slot(a)), _mv(b, dict(d=2, p=p + 2))]}).get_json()   # the second refused: the first shows
    assert j["state"] == "no" and _marks(j, "1A")[a][0] == "moved" and len(j["texts"]) == 1, j
    for body in ({"fixes": []}, {"fixes": [1, 2, 3]}, {"fixes": "x"}, {}): assert c.post("/api/draft/preview", json=body).status_code == 400, body
    assert c.get("/api/draft").get_json()["fixes"] == before

def test_the_preview_of_a_block_and_of_a_delete():
    import io, openpyxl
    spec = c.get("/api/setup").get_json()["spec"]; rows = [("Mon", 1, 1, "P1", "1A, 1B", "Art", ["Umairah Tan"]), ("Tue", 1, 1, "P1", "1A", "Zzz Extra", ["Umairah Tan"])]
    wb = openpyxl.load_workbook(io.BytesIO(_lessons_workbook(rows))); wb.active["I2"] = "Blk"; buf = io.BytesIO(); wb.save(buf)   # the Art lesson is a block of 1A and 1B
    assert c.post("/api/draft", data=dict(setup=(io.BytesIO(_setup_workbook(spec)), "setup.xlsx"), timetable=(io.BytesIO(buf.getvalue()), "timetable.xlsx"), replace="1"), content_type="multipart/form-data").status_code == 200
    art, extra = _lid("1B", "Art"), _lid("1A", "Zzz Extra"); s = _free_slot(art)
    j = c.post("/api/draft/preview", json={"fixes": [_mv(art, s)]}).get_json()
    assert j["state"] in ("ok", "prefer") and sorted(k["name"] for k in j["classes"]) == ["1A", "1B"] and _marks(j, "1B")[art][0] == "moved" and _marks(j, "1A")[art] == _marks(j, "1B")[art], j
    j = c.post("/api/draft/preview", json={"fixes": [dict(kind="delete", id=extra)]}).get_json()
    assert j["state"] in ("ok", "prefer") and j["gone"] == [dict(cls="1A", what="Zzz Extra for 1A", d=1, p=1)] and [k["name"] for k in j["classes"]] == ["1A"] and extra not in _marks(j, "1A"), j
    j = c.post("/api/draft/preview", json={"fixes": [dict(kind="room", id=art, group="Entire Class", room=next(x for x in c.get(f"/api/draft/options?id={art}").get_json()["rooms"] if x["state"] in ("ok", "prefer"))["room"])]}).get_json()
    assert _marks(j, "1A")[art] == ("changed", None), j
    assert c.get("/api/draft").get_json()["fixes"] == []

def test_marks_are_of_the_row_that_changed_not_of_its_lesson():
    import io, openpyxl
    spec = c.get("/api/setup").get_json()["spec"]   # lesson 1 is a block of two groups; 1A has two Mathematics lessons
    rows = [("Mon", 1, 1, "P1", "1A, 1B", "Art", ["Umairah Tan"]), ("Mon", 1, 1, "P1", "1A, 1B", "Art", ["Jasper Wong"]), ("Tue", 1, 1, "P1", "1A", "Mathematics", ["Umairah Tan"]), ("Wed", 1, 1, "P1", "1A", "Mathematics", ["Umairah Tan"])]
    wb = openpyxl.load_workbook(io.BytesIO(_lessons_workbook(rows))); ws = wb.active; ws["A3"] = 1; ws["I2"] = ws["I3"] = "BX"; ws["L2"], ws["L3"] = "GX1", "GX2"; buf = io.BytesIO(); wb.save(buf)
    assert c.post("/api/draft", data=dict(setup=(io.BytesIO(_setup_workbook(spec)), "setup.xlsx"), timetable=(io.BytesIO(buf.getvalue()), "timetable.xlsx"), replace="1"), content_type="multipart/form-data").status_code == 200
    blk = _lid("1A", "Art"); pv = lambda f: c.post("/api/draft/preview", json={"fixes": [f]}).get_json()
    by = lambda j, cls: {(x["id"], x["group"]): x["mark"] for x in next(k for k in j["classes"] if k["name"] == cls)["lessons"]}
    o = c.get(f"/api/draft/options?id={blk}&group=GX1").get_json()
    j = pv(dict(kind="teacher", key="G:GX1", teachers=[next(x for x in o["teachers"] if x["state"] in ("ok", "prefer"))["teachers"][0]])); assert j["state"] in ("ok", "prefer"), j
    assert by(j, "1A")[(blk, "GX1")] == "changed" and by(j, "1A")[(blk, "GX2")] == "" and by(j, "1B") == {(blk, "GX1"): "changed", (blk, "GX2"): ""}, j["classes"]
    j = pv(dict(kind="room", id=blk, group="GX2", room=next(x for x in o["rooms"] if x["state"] in ("ok", "prefer"))["room"])); assert by(j, "1A")[(blk, "GX2")] == "changed" and by(j, "1A")[(blk, "GX1")] == "", j
    t = next(x for x in c.get(f"/api/draft/options?id={_lid('1A', 'Mathematics')}").get_json()["teachers"] if x["state"] in ("ok", "prefer"))["teachers"]
    j = pv(dict(kind="teacher", key="C:1A:Mathematics", teachers=t)); assert [v for (i, g), v in by(j, "1A").items() if i != blk] == ["changed", "changed"] and all(v == "" for (i, g), v in by(j, "1A").items() if i == blk), j
    assert c.get("/api/draft").get_json()["fixes"] == []

def test_a_head_cannot_reach_the_helper_routes():
    for method, url in (("GET", "/api/draft/suggest?key=x"), ("POST", "/api/draft/fixes"), ("POST", "/api/draft/preview")):
        assert h.open(url, method=method, json={"fixes": []}).status_code in (401, 403), url

def test_an_upload_over_unpublished_fixes_is_refused_by_the_draft_and_replace_clears_them():
    spec = _grid_draft() and c.get("/api/setup").get_json()["spec"]; days, p = _grid_draft(); lid = _lid(); s = next(s for s in c.get(f"/api/draft/options?id={lid}").get_json()["slots"] if s["state"] == "ok" and not s["swap"])
    c.post("/api/draft/fix", json=dict(kind="move", id=lid, d=s["d"], p=s["p"])); rows = [("Mon", p, 1, "P1", "1A", "Art", ["Umairah Tan"])]
    r = c.post("/api/draft", data=_draft_form(spec, rows), content_type="multipart/form-data")
    assert r.status_code == 409 and r.get_json() == {"error": "The draft has fixes that were never published.", "fixes": 1} and len(c.get("/api/draft").get_json()["fixes"]) == 1
    import draft
    try: draft.save(None, None, "x", spec); raise AssertionError("save took no notice of the fixes")
    except draft.UnpublishedFixes as e: assert e.count == 1
    assert c.post("/api/draft", data=_draft_form(spec, rows, replace="1"), content_type="multipart/form-data").status_code == 200 and c.get("/api/draft").get_json()["fixes"] == []

def test_a_fix_into_a_clash_is_refused_with_the_sentence():   # judged on the server's draft, whatever the page showed
    days, p = _grid_draft(); lid = _lid()
    r = c.post("/api/draft/fix", json=dict(kind="move", id=lid, d=2, p=p + 2)); assert r.status_code == 400 and "is teaching" in r.get_json()["error"], r.get_json()
    assert c.get("/api/draft").get_json()["fixes"] == []

def _first_ok(options, key="slots", **no):
    return next(x for x in options[key] if x["state"] in ("ok", "prefer") and not x.get("swap"))

def test_a_fix_that_changes_nothing_is_refused():
    days, p = _grid_draft(); lid = _lid(); g = c.get("/api/draft/grid?view=class&name=1A").get_json(); x = next(x for x in g["lessons"] if x["id"] == lid)
    for f in (dict(kind="move", id=lid, d=x["d"], p=x["p"]), dict(kind="swap", a=lid, b=lid)):
        r = c.post("/api/draft/fix", json=f); assert r.status_code == 400 and r.get_json() == {"error": "That changes nothing."}, (f, r.get_json())
    assert c.get("/api/draft").get_json()["fixes"] == []

def test_an_add_must_say_a_length_inside_the_day():
    days, p = _grid_draft(); NP = c.get("/api/draft/grid?view=class&name=1A").get_json()["NP"]; said = {"error": "Say how many periods the lesson is."}
    for n in (0, -1, NP + 1, 10 ** 9, "x", 1.5, True):
        r = c.get(f"/api/draft/options?add=C:1A:Art&n={n}"); assert r.status_code == 400 and r.get_json() == said, (n, r.get_json())
        r = c.post("/api/draft/fix", json=dict(kind="add", key="C:1A:Art", d=4, p=p, n=n)); assert r.status_code == 400 and r.get_json() == said, (n, r.get_json())
    assert c.get(f"/api/draft/options?add=C:1A:Art&n={NP}").status_code == 200 and c.get("/api/draft").get_json()["fixes"] == []

def test_a_fix_still_applies_after_a_step5_change_that_keeps_it_valid():
    _grid_draft(); lid = _lid(); s = next(s for s in c.get(f"/api/draft/options?id={lid}").get_json()["slots"] if s["state"] == "ok" and not s["swap"])
    c.post("/api/draft/fix", json=dict(kind="move", id=lid, d=s["d"], p=s["p"]))
    rec = c.get("/api/setup").get_json(); row = next(x for x in rec["spec"]["lessons"] if x["classes"] == ["1A"] and x["subject"] == "Art")
    assert _changes("Z", rec["v"], [["set", "lessons", row["_id"], "teachers", ["Umairah Tan", "Michelle Goh"]]])[0] == 200
    r = c.get("/api/draft"); j = r.get_json(); assert r.status_code == 200 and j["fix_problems"] == [] and len(j["fixes"]) == 1, j
    assert {(x["d"], x["p"]) for x in c.get("/api/draft/grid?view=class&name=1A").get_json()["lessons"] if x["id"] == lid} == {(s["d"], s["p"])}

def test_a_fix_the_setup_no_longer_allows_is_named_and_the_file_shows():
    _grid_draft(); key = "C:1A:Art"; t = next(x for x in c.get(f"/api/draft/options?id={_lid()}").get_json()["teachers"] if x["state"] in ("ok", "prefer") and len(x["teachers"]) == 1)["teachers"]
    j = c.post("/api/draft/fix", json=dict(kind="teacher", key=key, teachers=t)).get_json(); assert len(j["fixes"]) == 1, j
    rec = c.get("/api/setup").get_json(); tid = next(x["_id"] for x in rec["spec"]["teachers"] if x["name"] == t[0])
    assert _changes("Z", rec["v"], [["del", "teachers", tid]])[0] == 200
    r = c.get("/api/draft"); j = r.get_json(); assert r.status_code == 200 and len(j["fix_problems"]) == 1 and j["fix_problems"][0].startswith("A fix could not be applied: "), j
    assert c.get("/api/draft/grid?view=class&name=1A").get_json()["lessons"][0]["teachers"] == ["Umairah Tan"]

def test_the_draft_downloads_with_its_fixes():
    import io
    from ttgen.database import read_db
    _grid_draft(); lid = _lid(); s = next(s for s in c.get(f"/api/draft/options?id={lid}").get_json()["slots"] if s["state"] == "ok" and not s["swap"])
    c.post("/api/draft/fix", json=dict(kind="move", id=lid, d=s["d"], p=s["p"]))
    r = c.get("/api/draft/download"); assert r.status_code == 200 and "draft.sqlite" in r.headers["Content-Disposition"], r.headers
    path = os.path.join(tempfile.mkdtemp(), "d.sqlite"); open(path, "wb").write(r.data); header, rows = read_db(path)[:2]
    ix = {h: i for i, h in enumerate(header)}; art = [x for x in rows if x[ix["Subject"]] == "Art" and x[ix["Classes"]] == "1A"]
    assert len(art) == 1 and art[0][ix["Day"]] == c.get("/api/draft/grid?view=class&name=1A").get_json()["days"][s["d"]] and art[0][ix["Start period"]] == s["p"]
    rec = c.get("/api/setup").get_json(); row = next(x for x in rec["spec"]["lessons"] if x["classes"] == ["1B"] and x["subject"] == "Art")
    assert _changes("Z", rec["v"], [["set", "lessons", row["_id"], "teachers", ["Umairah Tan", "Michelle Goh"]]])[0] == 200
    r = c.get("/api/draft/download"); open(path, "wb").write(r.data); got = read_db(path)[5]
    assert got["school"]["config_id"] == f"v{rec['v'] + 1}" and c.get("/api/draft").get_json()["config_id"] != f"v{rec['v'] + 1}", got["school"]
    shutil = __import__("shutil"); shutil.rmtree(os.path.join(store.DATA, "draft"))
    assert c.get("/api/draft/download").status_code == 404 and c.get("/api/draft/grid?view=class&name=1A").status_code == 404 and c.post("/api/draft/undo").status_code == 404

def test_a_draft_whose_fixes_are_published_is_replaced_without_the_question():
    spec = c.get("/api/setup").get_json()["spec"]; rows = [_lesson_of(spec, _one_class_row(spec), ["Nobody"])]
    c.post("/api/draft", data=_draft_form(spec, rows), content_type="multipart/form-data")
    mp = os.path.join(store.DATA, "draft", "meta.json"); meta = store.read_json(mp)
    store.write_json(mp, dict(meta, fixes=[{"x": 1}], published_fixes=1))
    assert c.post("/api/draft", data=_draft_form(spec, rows), content_type="multipart/form-data").status_code == 200
    store.write_json(mp, dict(store.read_json(mp), fixes=[{"x": 1}, {"x": 2}], published_fixes=1))
    assert c.post("/api/draft", data=_draft_form(spec, rows), content_type="multipart/form-data").status_code == 409

def test_publish_uses_the_setup_the_draft_was_checked_against():   # finding 10
    import draft
    spec = c.get("/api/setup").get_json()["spec"]; row = _one_class_row(spec)
    c.post("/api/draft", data=_draft_form(spec, [_lesson_of(spec, row, row["teachers"])]), content_type="multipart/form-data")
    real_rec, real_pub, calls, got = store.setup_record, store.publish, [], {}
    def rec():
        r = real_rec(); calls.append(1); r["v"] += len(calls) - 1; r["spec"]["school"]["name"] = f"Read {len(calls)}"; return r   # the setup changes between reads
    def pub(sp, tp, **kw): got.update(kw)
    store.setup_record, store.publish = rec, pub
    try: j = draft.publish()
    finally: store.setup_record, store.publish = real_rec, real_pub
    assert got["extra"]["compared_v"] == j["setup_version"] and got["spec"]["school"]["name"] == f"Read {int(j['setup_version'][1:]) - real_rec()['v'] + 1}", (got["extra"]["compared_v"], got["spec"]["school"]["name"], j["setup_version"])

def test_publishing_with_no_draft_is_404():
    shutil = __import__("shutil"); shutil.rmtree(os.path.join(store.DATA, "draft"), ignore_errors=True)
    assert c.post("/api/draft/publish").status_code == 404 and c.get("/api/status").get_json()["draft"] is None

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
    r = c.post("/api/draft", data={"setup": (open(setup, "rb"), "setup.xlsx"), "timetable": (open(tt, "rb"), "timetable.xlsx")}, content_type="multipart/form-data")
    d = r.get_json(); assert r.status_code == 200 and d["open"] >= 0 and len(set(w["key"] for w in d["warnings"])) == len(d["warnings"]), d
    assert d["rule_report"][0]["result"] == "Met" and d["typed"] == 0, d["rule_report"]
    assert d["config_id"] == f"v{v}" and d["config_state"] == "same", d
    assert d["choices_used"][0]["used"] == "First choice" and d["choices"] == 0, d
    fixed = None   # the first lesson of any class with a slot that is not refused: a move, or a swap when the week is full
    for cl in c.get("/api/setup").get_json()["spec"]["classes"]:
        for x in c.get("/api/draft/grid?view=class&name=" + cl["class"]).get_json()["lessons"]:
            sl = next((s for s in c.get(f"/api/draft/options?id={x['id']}").get_json()["slots"] if s["state"] in ("ok", "prefer")), None)
            if sl: fixed = c.post("/api/draft/fix", json=dict(kind="swap", a=x["id"], b=sl["swap"]) if sl["swap"] else dict(kind="move", id=x["id"], d=sl["d"], p=sl["p"])).get_json(); break
        if fixed: break
    assert fixed and len(fixed["fixes"]) == 1, fixed
    r = c.post("/api/draft/publish"); j = r.get_json(); assert r.status_code == 200 and j["published"] is True, j
    p = c.get("/api/status").get_json()["published"]
    assert p and p["source"] == "timetable.xlsx" and p["rule_report"][0]["how"] == "Checked.", p
    assert p["compared_v"] == f"v{v}" == d["setup_version"] and p["open"] == fixed["open"] and p["fixes"] == [fixed["fixes"][0]["text"]] and isinstance(p["left"], list), p
    assert p["choices_used"] == d["choices_used"] and p["choice_problems"] and p["config_id"] == d["config_id"], p
    import openpyxl
    wb = openpyxl.load_workbook(os.path.join(store.PUB, store.published()["meta"]["files"]["excel"])); col = [r[0] for r in wb["Read me"].iter_rows(max_col=1, values_only=True)]
    assert "Fixes made in the app" in col and fixed["fixes"][0]["text"] in col, col
    assert store.read_json(os.path.join(store.DATA, "draft", "meta.json"))["published_fixes"] == 1
    t = A.app.test_client(); t.post("/login", data={"as": "teacher", "code": CODES["TEACHER_CODE"]})
    assert t.get("/timetable").status_code == 200

# Class Parents on the server: one named subject (made up), class 1A with a Class Parent; each test starts from the sample and the last puts it back
PSUBJ = "Pastoral Care"
def _cp_start():
    c.put("/api/setup", json=c.get("/api/sample/secondary").get_json()); return c.get("/api/setup").get_json()

def _cp_name(rec, client="A", parents=("Pastoral A",)):   # what a stale page sends: the subject, the name, the box, and no lesson ops
    cid = next(x["_id"] for x in rec["spec"]["classes"] if x["class"] == "1A")
    return _changes(client, rec["v"], [["add", "subjects", {"_id": "pcsubj001", "subject": PSUBJ, "code": "PC", "periods": {"Sec 1": 2}}, ""],
                                       ["school", "parents_subjects", [PSUBJ]], ["set", "classes", cid, "parents", list(parents)]])

def _cp_rows(spec): return {r["classes"][0]: r for r in spec["lessons"] if r.get("subject") == PSUBJ}

def test_class_parents_are_kept_right_on_the_server():               # Review Focus 1
    rec = _cp_start(); v0 = rec["v"]
    code, j = _cp_name(rec)
    assert code == 200 and j["v"] == v0 + 2, (code, j)                # the caller's change, then what the server put right
    rows = _cp_rows(c.get("/api/setup").get_json()["spec"])
    sec1 = [x["class"] for x in rec["spec"]["classes"] if x["level"] == "Sec 1"]
    assert sorted(rows) == sorted(sec1) and rows["1A"]["teachers"] == ["Pastoral A"] and all(not rows[k]["teachers"] for k in sec1 if k != "1A"), rows
    assert rows["1A"]["_id"].startswith("cp-")
    assert len(j["patches"]) == 1 and j["patches"][0]["v"] == v0 + 2 and any(o[0] == "add" and o[1] == "lessons" for o in j["patches"][0]["ops"]), j   # the sender is told too
    code, k = _changes("B", v0)                                       # a second browser gets both entries
    assert [p["v"] for p in k["patches"]] == [v0 + 1, v0 + 2], k
    assert [e["client"] for e in list(store._log)[-2:]] == ["A", "parents"]

def test_a_stale_tab_cannot_undo_a_following_lesson():
    rec = _cp_start(); _cp_name(rec)
    rec = c.get("/api/setup").get_json(); row = _cp_rows(rec["spec"])["1A"]
    code, j = _changes("A", rec["v"], [["set", "lessons", row["_id"], "teachers", ["Koh"]]])
    assert code == 200 and j["v"] == rec["v"] + 2, j
    assert _cp_rows(c.get("/api/setup").get_json()["spec"])["1A"]["teachers"] == ["Pastoral A"]
    assert ["set", "lessons", row["_id"], "teachers", ["Pastoral A"]] in j["patches"][0]["ops"], j     # and the sender is told

def test_a_hand_change_with_its_mark_is_kept():
    rec = _cp_start(); _cp_name(rec)
    rec = c.get("/api/setup").get_json(); row = _cp_rows(rec["spec"])["1A"]; cid = next(x["_id"] for x in rec["spec"]["classes"] if x["class"] == "1A")
    code, j = _changes("A", rec["v"], [["set", "lessons", row["_id"], "teachers", ["Koh"]], ["set", "lessons", row["_id"], "by_hand", True]])
    assert code == 200 and j["v"] == rec["v"] + 1 and not j["patches"], j
    code, j = _changes("A", j["v"], [["set", "classes", cid, "parents", ["Pastoral B"]]]); assert j["v"] == rec["v"] + 2, j
    r = _cp_rows(c.get("/api/setup").get_json()["spec"])["1A"]; assert r["teachers"] == ["Koh"] and r["by_hand"] is True, r

def test_a_head_cannot_change_a_staffed_lesson():                    # in NEED_HEADS
    rec = _cp_start(); _cp_name(rec)
    rec = c.get("/api/setup").get_json(); row = _cp_rows(rec["spec"])["1A"]
    code, j = _changes("H", rec["v"], [["set", "lessons", row["_id"], "teachers", ["Koh"]], ["set", "lessons", row["_id"], "students", 5]], who=h)
    assert code == 200 and j["refused"] == [{"i": 0, "why": sync.PARENTS_WHY}] and j["v"] == rec["v"] + 1, j
    r = _cp_rows(c.get("/api/setup").get_json()["spec"])["1A"]; assert r["teachers"] == ["Pastoral A"] and r["students"] == 5, r

def test_a_setup_put_whole_is_put_right():
    spec = c.get("/api/sample/secondary").get_json()
    spec["subjects"].append({"subject": PSUBJ, "code": "PC", "periods": {"Sec 1": 2}}); spec["school"]["parents_subjects"] = [PSUBJ]
    next(x for x in spec["classes"] if x["class"] == "1A")["parents"] = ["Pastoral A"]
    spec["lessons"].append({"level": "Sec 1", "subject": PSUBJ, "block": None, "classes": ["1A"], "teachers": ["Someone Else"], "students": None})
    assert c.put("/api/setup", json=spec).status_code == 200
    rows = _cp_rows(c.get("/api/setup").get_json()["spec"])
    assert rows["1A"]["teachers"] == ["Pastoral A"] and "by_hand" not in rows["1A"] and len(rows) == 4, rows
    _cp_start()                                                       # the sample back, for the tests after

NEED_HEADS = {"test_a_head_cannot_change_a_staffed_lesson", "test_a_head_can_change_groups_but_not_classes", "test_a_heads_map_batch_is_applied_whole", "test_a_heads_refused_change_is_skipped_and_the_rest_applied", "test_a_heads_batch_that_is_all_refused_changes_nothing", "test_a_teacher_added_by_a_head_is_provisional",
              "test_a_head_can_edit_only_provisional_teachers", "test_a_head_can_add_and_fill_in_a_teacher_in_one_request", "test_the_head_check_runs_on_the_setup_held_under_the_lock", "test_a_head_cannot_download_or_publish_or_replace", "test_a_head_cannot_reach_the_helper_routes"}

if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_") and (k != "test_publish_uploaded_timetable" or "--full" in sys.argv)
             and (h or k not in NEED_HEADS)]
    for t in tests: t(); print("ok", t.__name__)
    print(f"{len(tests)} checks passed")

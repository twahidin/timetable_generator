"""Server smoke checks. Run: .venv/bin/python tests/smoke.py   (add --full for the slow publish check)"""
import copy, io, os, secrets, subprocess, sys, tempfile
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
    assert set(j) == {"role", "codes", "code_problems", "volume", "setup_saved_at", "published", "draft", "versions", "typed",
                      "who", "group", "via", "depts", "rights", "shared", "admin_exists"}, sorted(j)   # who is signed in (accounts)
    assert j["published"] is None and j["role"] == "committee" and j["draft"] is None and j["versions"] == 0   # the saved versions are counted whether or not there is a draft
    assert (j["who"], j["group"], j["via"], j["depts"], j["shared"], j["admin_exists"]) == (None, None, "shared", None, "committee", False) and "committee" in j["rights"], j

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
    r = c.post("/api/draft/printouts", data=dict(single="0"))   # neither a setup nor a draft: the draft is asked after first, so it is 404 (the 409 is for a draft with no setup)
    assert r.status_code == 404 and r.get_json() == {"error": "There is no draft."}, r.get_json()

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

def test_rows_with_no_subject_are_left_out_and_said():
    """step 5's "+ Add teaching group" leaves a row with no subject; saved, it has no fields at all. The check and the download used to fail on it ('subject')"""
    spec = c.get("/api/sample/secondary").get_json(); base = _check(spec).get_json(); lv = spec["school"]["levels"][0]; cls = spec["classes"][0]["class"]
    spec["lessons"] += [{}, {"level": lv}, {"level": lv, "classes": [cls]}]
    r = _check(spec); j = r.get_json(); assert r.status_code == 200 and j["critical"] == base["critical"] and j["warnings"] == base["warnings"] + 1, j
    said = [f for f in j["findings"] if "no subject" in f["text"]]; assert len(said) == 1 and said[0]["level"] == "warning" and said[0]["area"] == "lessons", said
    assert said[0]["text"].startswith("3 teaching group rows on step 5 have no subject, so they are left out of the workbook and of the timetable (2 with nothing filled in, 1 with ") and cls in said[0]["text"], said[0]["text"]
    assert [f for f in j["findings"] if "no subject" not in f["text"]] == base["findings"]   # everything else is judged as without them
    r = c.post("/api/build", json=spec); assert r.status_code == 200 and r.mimetype.endswith("sheet"), r.get_data()[:200]
    back = c.post("/api/import", data=dict(file=(io.BytesIO(r.get_data()), "s.xlsx")), content_type="multipart/form-data").get_json()
    assert len(back["lessons"]) == len(spec["lessons"]) - 3 and all(x.get("subject") for x in back["lessons"])
    spec["lessons"] = spec["lessons"][:-3] + [{"level": lv}]; one = [f["text"] for f in _check(spec).get_json()["findings"] if "no subject" in f["text"]]
    assert one == ["1 teaching group row on step 5 has no subject, so it is left out of the workbook and of the timetable (1 with nothing filled in). On step 5's Table view, give it a subject or delete it."], one
    assert A.unfilled_rows(c.get("/api/sample/secondary").get_json()) == ""

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

def test_the_heads_code_goes_in_the_one_box():   # the sign-in page is one box for every code: no card for the heads
    page = c.get("/login").data
    assert b"Department heads" not in page and page.count(b'name="code"') == 1 and c.get("/login?as=heads").data == page
    if h:
        with h.session_transaction() as s: assert s["role"] == "head"

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
    code, j = _changes("H", v, [["merge", "teachers", firm["_id"], "can_teach", [{"levels": "All", "subject": "Qqq"}], []]], who=h); assert code == 200 and len(j["refused"]) == 1
    ts = {x["_id"]: x for x in c.get("/api/setup").get_json()["spec"]["teachers"]}
    assert ts[firm["_id"]]["name"] != "Zed" and ts["newhire002"]["provisional"] == "Yes" and ts["newhire002"]["name"] == "Renamed"

def test_a_head_can_add_and_fill_in_a_teacher_in_one_request():
    v = c.get("/api/setup").get_json()["v"]
    code, _ = _changes("H", v, [["add", "teachers", {"_id": "newhire003", "name": "Batch hire"}, ""], ["set", "teachers", "newhire003", "short", "BH"]], who=h); assert code == 200
    t = next(x for x in c.get("/api/setup").get_json()["spec"]["teachers"] if x["_id"] == "newhire003"); assert t["provisional"] == "Yes" and t["short"] == "BH"

def test_a_heads_map_batch_is_applied_whole():
    # one department-map session: a new teacher, a class split off a shared whole-class row, and a deployment
    rec = c.get("/api/setup").get_json(); v = rec["v"]; sp = rec["spec"]
    row = next(x for x in sp["lessons"] if not x.get("block") and x.get("subject"))
    ops = [["add", "teachers", {"_id": "maphire001", "name": "New Mathematics teacher 1", "dept": "MA"}, ""],
           ["set", "lessons", row["_id"], "classes", []],
           ["add", "lessons", {"_id": "mapsplit001", "level": row["level"], "subject": row["subject"], "block": None, "classes": row["classes"], "teachers": [], "students": row.get("students")}, row["_id"]],
           ["set", "lessons", "mapsplit001", "teachers", (row.get("teachers") or []) + ["New Mathematics teacher 1"]]]
    code, j = _changes("H", v, ops, who=h); assert code == 200 and not j.get("refused"), j
    now = c.get("/api/setup").get_json()["spec"]
    t = next(x for x in now["teachers"] if x["_id"] == "maphire001"); assert t["provisional"] == "Yes"
    L = {x["_id"]: x for x in now["lessons"]}
    assert L[row["_id"]]["classes"] == [] and L["mapsplit001"]["classes"] == row["classes"] and L["mapsplit001"]["teachers"][-1] == "New Mathematics teacher 1"

def test_a_head_cannot_give_a_second_department():
    v = c.get("/api/setup").get_json()["v"]
    _changes("H", v, [["add", "teachers", {"_id": "newhire004", "name": "Two dept hire", "dept": "MA", "dept2": "SC"}, ""]], who=h)
    rec = c.get("/api/setup").get_json(); v = rec["v"]
    t = next(x for x in rec["spec"]["teachers"] if x["_id"] == "newhire004"); assert t["provisional"] == "Yes" and "dept2" not in t
    code, j = _changes("H", v, [["set", "teachers", "newhire004", "dept2", "SC"]], who=h); assert code == 200 and len(j["refused"]) == 1
    assert "dept2" not in next(x for x in c.get("/api/setup").get_json()["spec"]["teachers"] if x["_id"] == "newhire004")
    code, j = _changes("C", v, [["set", "teachers", "newhire004", "dept2", "SC"]]); assert code == 200 and not j.get("refused")
    assert next(x for x in c.get("/api/setup").get_json()["spec"]["teachers"] if x["_id"] == "newhire004")["dept2"] == "SC"

def test_a_heads_old_can_teach_change_is_refused_and_the_rest_of_the_batch_lands():
    rec = c.get("/api/setup").get_json(); v = rec["v"]; sp = rec["spec"]
    row = next(x for x in sp["lessons"] if not x.get("block") and x.get("subject") and x.get("classes"))
    ops = [["add", "teachers", {"_id": "maphire002", "name": "New Mathematics teacher 2", "dept": "MA"}, ""],
           ["merge", "teachers", "maphire002", "can_teach", [{"subject": row["subject"], "levels": "All"}], []],
           ["set", "lessons", row["_id"], "classes", []],
           ["add", "lessons", {"_id": "mapsplit002", "level": row["level"], "subject": row["subject"], "block": None, "classes": row["classes"], "teachers": [], "students": row.get("students")}, row["_id"]],
           ["set", "lessons", "mapsplit002", "teachers", (row.get("teachers") or []) + ["New Mathematics teacher 2"]]]
    code, j = _changes("H", v, ops, who=h); assert code == 200 and len(j["refused"]) == 1, j
    now = c.get("/api/setup").get_json()["spec"]
    t = next(x for x in now["teachers"] if x["_id"] == "maphire002"); assert t["provisional"] == "Yes" and "can_teach" not in t
    L = {x["_id"]: x for x in now["lessons"]}
    assert L[row["_id"]]["classes"] == [] and L["mapsplit002"]["classes"] == row["classes"] and L["mapsplit002"]["teachers"][-1] == "New Mathematics teacher 2"

def test_the_head_check_runs_on_the_setup_held_under_the_lock():
    rec = c.get("/api/setup").get_json(); v = rec["v"]; spec = rec["spec"]
    firm = next(x for x in spec["teachers"] if x.get("provisional") != "Yes")
    stale = [["set", "teachers", "newhire003", "name", "Late"]]
    assert sync.head_may(spec, stale) is None                      # judged on a copy taken earlier, the teacher is still provisional
    c.post("/api/setup/changes", json={"since": v, "client": "C", "ops": [["set", "teachers", "newhire003", "provisional", "No"]]})   # the committee confirms the teacher meanwhile
    v2 = c.get("/api/setup").get_json()["v"]
    v3, refused, _ = store.apply_changes(stale, "H", filter=sync.head_split)
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
    assert len(set(_warn_keys(j))) == len(j["warnings"]) and "left" not in j and j["critical"] == sum(1 for w in j["warnings"] if w["crit"]) and j["fixes"] == [] and j["lessons"] == 1
    st = c.get("/api/status").get_json()["draft"]; assert st["critical"] == j["critical"] and st["fixes"] == 0 and st["open"] == j["open"], (st, j["critical"])   # right after the upload
    assert j == dict(c.get("/api/draft").get_json(), kept=j["kept"])   # the upload's answer is the draft's, with kept beside it and nothing else
    k = f"dep:C:{row['classes'][0]}:{row['subject']}:teachers"; assert k in _warn_keys(j)
    j2 = c.post("/api/draft/decide", json={"key": k, "answer": "open"}).get_json()
    assert j2["open"] == j["open"] and "left" not in j2 and next(w for w in j2["warnings"] if w["key"] == k)["decision"] is None
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
    assert h is None or h.post("/api/draft/decide", json={"key": k, "answer": "open"}).status_code == 401

def test_draft_decisions_survive_a_setup_change_and_stale_ones_go():
    spec = c.get("/api/setup").get_json()["spec"]; row = _one_class_row(spec); other = _one_class_row(spec, skip=(row["classes"][0],))
    c.post("/api/draft", data=_draft_form(spec, [_lesson_of(spec, row, row["teachers"])]), content_type="multipart/form-data")
    k = f"dep:C:{other['classes'][0]}:{other['subject']}:missing"; j = c.get("/api/draft").get_json(); assert k in _warn_keys(j)
    dp = os.path.join(store.DATA, "draft", "decisions.json"); store.write_json(dp, {k: dict(answer="met", at="now")})   # a decision as the page's "Still met" leaves it
    assert next(w for w in c.get("/api/draft").get_json()["warnings"] if w["key"] == k)["decision"]["answer"] == "met"
    v = c.get("/api/setup").get_json()["v"]
    assert c.post("/api/setup/changes", json={"client": "t", "since": v, "ops": [["del", "lessons", other["_id"]]]}).status_code == 200
    j = c.get("/api/draft").get_json(); assert k not in _warn_keys(j) and j["setup_version"] == f"v{v + 1}"
    assert k not in store.read_json(os.path.join(store.DATA, "draft", "decisions.json"), {})
    r = c.post("/api/draft/decide", json={"key": k, "answer": "step5"}); assert r.status_code == 400 and "no longer on the list" in r.get_json()["error"]

def test_a_new_upload_starts_with_no_decisions():
    spec = c.get("/api/setup").get_json()["spec"]; row = _one_class_row(spec); rows = [_lesson_of(spec, row, ["Somebody"])]
    c.post("/api/draft", data=_draft_form(spec, rows), content_type="multipart/form-data")
    k = f"dep:C:{row['classes'][0]}:{row['subject']}:teachers"; dp = os.path.join(store.DATA, "draft", "decisions.json")
    store.write_json(dp, {k: dict(answer="met", at="now")}); assert next(w for w in c.get("/api/draft").get_json()["warnings"] if w["key"] == k)["decision"]["answer"] == "met"
    j = c.post("/api/draft", data=_draft_form(spec, rows), content_type="multipart/form-data").get_json()
    assert next(w for w in j["warnings"] if w["key"] == k)["decision"] is None and j["open"] == len(j["warnings"]) and store.read_json(dp) == {}
    store.write_json(os.path.join(store.DATA, "draft", "meta.json"), dict(store.read_json(os.path.join(store.DATA, "draft", "meta.json")), fixes=[{"x": 1}]))
    r = c.post("/api/draft", data=_draft_form(spec, rows), content_type="multipart/form-data")
    assert r.status_code == 200 and r.get_json()["kept"]["kind"] == "upload", r.get_json()
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
        j = orig(*a, **kw); store.write_json(os.path.join(draft.DIR, "decisions.json"), {k2: dict(answer="met", at="now")}); return j
    draft._build = slow
    try: got = c.get("/api/draft").get_json()
    finally: draft._build = orig
    assert store.read_json(os.path.join(draft.DIR, "decisions.json"))[k2]["answer"] == "met" and c.get("/api/draft").get_json()["open"] == len(ws) - 1
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
    assert all(set(s) == {"d", "p", "state", "why", "swap", "also"} for s in j["slots"])   # without the extras: no push or place beside is read
    r = c.get(f"/api/draft/options?id={lid}&group=Entire%20Class"); assert r.status_code == 200
    a = c.get("/api/draft/options?add=C:1A:Art&n=1").get_json(); assert set(a) == {"slots"} and a["slots"] and set(a["slots"][0]) == {"d", "p", "state", "why"}
    assert c.get("/api/draft/options?id=99999").status_code == 400 and c.get("/api/draft/options").status_code == 400

def test_the_slots_say_who_and_the_place_route_judges_the_one_dropped_on():
    _grid_draft(); lid = _lid(); j = c.get(f"/api/draft/slots?id={lid}").get_json()
    assert set(j) == {"id", "slots", "delete"} and j["id"] == lid and j["slots"] and all(set(s) == {"d", "p", "state", "why", "swap", "also", "there"} for s in j["slots"])
    s = j["slots"][0]; r = c.get(f"/api/draft/place?id={lid}&d={s['d']}&p={s['p']}"); assert r.status_code == 200
    k = r.get_json(); assert set(k) == {"d", "p", "state", "why", "swap", "also", "push", "beside", "clashes"} and (k["d"], k["p"]) == (s["d"], s["p"]) and (k["push"] is None) == (s["there"] is None) and (isinstance(k["clashes"], list) if s["there"] is not None else k["clashes"] is None or bool(k["clashes"]))
    assert c.get("/api/draft/place").status_code == 400 and c.get(f"/api/draft/place?id={lid}").get_json() == {"error": "Say which place."} and c.get("/api/draft/place?id=99999&d=0&p=0").status_code == 400
    assert c.get(f"/api/draft/place?id={lid}&d=99&p=0").get_json() == {"error": "That is outside the day."}

def test_the_lesson_route_and_the_board_lists_for_teachers_and_rooms():
    _grid_draft(); lid = _lid(); j = c.get(f"/api/draft/lesson?id={lid}").get_json()
    assert set(j) == {"id", "group", "key", "what", "n_lessons", "teachers", "rooms"} and j["key"] == "C:1A:Art" and j["n_lessons"] >= 1 and j["teachers"] and j["rooms"]
    assert set(j["teachers"][0]) == {"name", "short", "free", "doing", "rank"} and set(j["rooms"][0]) == {"room", "kind", "right", "free", "holding"}
    assert c.get("/api/draft/lesson").status_code == 400 and c.get("/api/draft/lesson?id=99999").status_code == 400
    b = c.get("/api/draft/board").get_json(); assert b["teachers"] and b["rooms"] and len(b["day"]) == len(b["days"]) and all(r["key"] for x in b["cards"] for r in x["rows"])
    r = c.post("/api/draft/fix", json=dict(kind="teacher", key=j["key"], teachers=[], force=True)); assert r.status_code == 200   # no teacher is never a clash, so force is not needed and does no harm
    assert c.post("/api/draft/undo").status_code == 200

def test_a_fix_moves_the_lesson_and_undo_brings_it_back():
    _grid_draft(); lid = _lid(); s = next(s for s in c.get(f"/api/draft/options?id={lid}").get_json()["slots"] if s["state"] == "ok" and not s["swap"])
    j = c.post("/api/draft/fix", json=dict(kind="move", id=lid, d=s["d"], p=s["p"])).get_json(); assert len(j["fixes"]) == 1 and j["fixes"][0]["text"].startswith("Moved "), j
    g = c.get("/api/draft/grid?view=class&name=1A").get_json(); assert (s["d"], s["p"]) in {(x["d"], x["p"]) for x in g["lessons"] if x["id"] == lid}
    assert c.get("/api/status").get_json()["draft"]["open"] == j["open"]
    st = c.get("/api/status").get_json()["draft"]; assert st["critical"] == j["critical"] and st["fixes"] == 1, (st, j["critical"])   # after a fix
    assert j == c.get("/api/draft").get_json()   # the page compares the two: the same draft is not redrawn
    assert store.read_json(os.path.join(store.DATA, "draft", "meta.json"))["fixes"][0]["at"]
    j = c.post("/api/draft/undo").get_json(); assert j["fixes"] == [] and c.post("/api/draft/undo").status_code == 400
    st = c.get("/api/status").get_json()["draft"]; assert st["critical"] == j["critical"] and st["fixes"] == 0 and st["open"] == j["open"], (st, j["critical"])   # after the undo
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
    # the offers are for the named group row: its own teacher is left out and the other group's teacher, of the same department, is offered
    assert all(x["teachers"] != ["Charmaine Yeo"] for x in j["teachers"]) and any(x["teachers"] == ["Adeline Tan"] for x in j["teachers"]), j["teachers"]
    j2 = c.get("/api/draft/options?id=1&group=1CL1").get_json(); assert j2["key"] == "G:1CL1" and c.get("/api/draft/options?id=1").get_json()["key"] == "G:1CL1"
    assert all(x["teachers"] != ["Adeline Tan"] for x in j2["teachers"]) and any(x["teachers"] == ["Charmaine Yeo"] for x in j2["teachers"]), j2["teachers"]

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
    r = c.post("/api/draft/preview", json={"fixes": [dict(kind="move", id=a, d=2, p=p + 2)]}); j = r.get_json()   # judged no: 200, and the timetable with the one change made (it is only looked at)
    assert r.status_code == 200 and j["state"] == "no" and "is teaching" in j["why"] and _marks(j, "1A")[a][0] == "moved" and j["gone"] == [], j
    assert c.get("/api/draft").get_json()["fixes"] == before
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

class _typed_env:   # TYPED_REQUEST_MODEL and ANTHROPIC_API_KEY as the test says (None removes), with the guard and the client reset; the earlier values come back after
    def __init__(self, **kw): self.kw = kw
    def __enter__(self):
        import typed; self.old = {k: os.environ.get(k) for k in self.kw}; self.keep = (typed._call, typed.read)
        for k, v in self.kw.items(): os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
        typed._seen.clear(); typed._cached = None
    def __exit__(self, *a):
        import typed
        for k, v in self.old.items(): os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
        typed._call, typed.read = self.keep; typed._seen.clear(); typed._cached = None

NOT_ON = "Typing a request is not set up on this server."
def _ask(c_=None, **body): return (c_ or c).post("/api/draft/ask", json=body)

def test_the_typed_request_is_off_without_a_key_and_on_with_the_mock_reader():
    with _typed_env(TYPED_REQUEST_MODEL=None, ANTHROPIC_API_KEY=None):
        assert c.get("/api/status").get_json()["typed"] is False
        r = _ask(words="move Art for 1A off Mon"); assert r.status_code == 404 and r.get_json() == {"error": NOT_ON}, r.get_json()
    with _typed_env(TYPED_REQUEST_MODEL="mock", ANTHROPIC_API_KEY=None): assert c.get("/api/status").get_json()["typed"] is True
    with _typed_env(TYPED_REQUEST_MODEL=None, ANTHROPIC_API_KEY="sk-ant-test-not-a-key"): assert c.get("/api/status").get_json()["typed"] is True
    with _typed_env(TYPED_REQUEST_MODEL=None, ANTHROPIC_API_KEY=None, AI_PROVIDER="anthropic", AI_API_KEY="sk-ant-test-not-a-key"): assert c.get("/api/status").get_json()["typed"] is True   # the key under an earlier version's name
    with _typed_env(TYPED_REQUEST_MODEL=None, ANTHROPIC_API_KEY=None, AI_PROVIDER="openai", AI_API_KEY="sk-test-not-a-key"):                                                                   # another provider's key is not used
        assert c.get("/api/status").get_json()["typed"] is False and _ask(words="move Art for 1A off Mon").status_code == 404

def test_the_typed_route_needs_a_draft_a_setup_and_a_json_object():
    import shutil; shutil.rmtree(os.path.join(store.DATA, "draft"), ignore_errors=True)
    with _typed_env(TYPED_REQUEST_MODEL="mock"):
        import typed; real_read = typed.read; typed.read = lambda *a, **k: (_ for _ in ()).throw(AssertionError("the reader was called with no draft"))
        r = _ask(words="move Art for 1A off Mon"); assert r.status_code == 404 and r.get_json() == {"error": "There is no draft."}, r.get_json()
        assert c.post("/api/draft/preview", json={"fixes": []}).status_code == 404       # the other draft routes say no draft the same way
        typed.read = real_read; _grid_draft()
        real = A.draft._now
        def nosetup(): raise LookupError()                                                # what no saved setup raises
        A.draft._now = nosetup
        try: r = _ask(words="move Art for 1A off Mon"); assert r.status_code == 409 and r.get_json() == {"error": A.NO_SETUP}, (r.status_code, r.get_json())
        finally: A.draft._now = real
        for body in ("x", [1], 5, None):
            r = c.post("/api/draft/ask", json=body); assert r.status_code == 400 and r.get_json()["error"], body
        assert c.post("/api/draft/ask", data="not json", content_type="text/plain").status_code == 400

def test_a_typed_request_finds_the_lesson_and_its_ways_are_applied_through_the_fixes_route():   # Review Focus 5
    days, p = _grid_draft(); import typed
    with _typed_env(TYPED_REQUEST_MODEL="mock"):
        a = _lid("1A", "Art"); said = days[0]; assert typed._day(said), said
        j = _ask(words=f"move Art for 1A off {said}").get_json()
        assert j["ok"] is True and j["understood"] is True and set(j) == {"ok", "ask", "understood", "reply", "choices", "problems", "groups", "more", "keep", "narrow"}, j
        assert j["ask"]["action"] == "move" and j["choices"] == [] and j["problems"] == [] and [g["lesson"] for g in j["groups"]] == [a], j
        sug = j["groups"][0]["suggestions"]; assert sug and all(s["state"] in ("ok", "prefer") for s in sug), j["groups"]
        assert c.get("/api/draft").get_json()["fixes"] == []                                    # asking changes nothing
        r = c.post("/api/draft/fixes", json={"fixes": sug[0]["fixes"]}); assert r.status_code == 200, r.get_json()
        assert next(x for x in c.get("/api/draft/grid?view=class&name=1A").get_json()["lessons"] if x["id"] == a)["d"] != 0

def test_a_way_left_over_after_the_draft_changed_is_refused_whole():   # Review Focus 5
    days, p = _grid_draft()
    with _typed_env(TYPED_REQUEST_MODEL="mock"):
        a, b = _lid("1A", "Art"), _lid("1B", "Art"); j = _ask(words=f"move Art for 1A off {days[0]}").get_json()
        mv = next(s for s in j["groups"][0]["suggestions"] if s["fixes"][0]["kind"] == "move"); f = mv["fixes"][0]
        r = c.post("/api/draft/fix", json=dict(kind="move", id=b, d=f["d"], p=f["p"])); assert r.status_code == 200, r.get_json()    # the same teacher's other lesson takes the target slot
        before = c.get("/api/draft").get_json()["fixes"]; assert len(before) == 1
        r = c.post("/api/draft/fixes", json={"fixes": mv["fixes"]}); assert r.status_code == 400 and r.get_json()["error"], (r.status_code, r.get_json())
        assert c.get("/api/draft").get_json()["fixes"] == before

def test_a_choice_answered_with_pick_and_the_ask_does_not_read_the_words_again():
    _grid_draft(); import typed
    with _typed_env(TYPED_REQUEST_MODEL="mock"):
        j = _ask(words="give 1A Art to Tan").get_json(); assert j["ok"] and len(j["choices"]) == 1 and j["groups"] == [], j
        ch = j["choices"][0]; assert ch["id"] == "new_teacher|Tan" and len(ch["options"]) > 1, ch
        def fail(*a, **k): raise AssertionError("the reader was called again")
        typed.read = fail
        j2 = _ask(words="give 1A Art to Tan", ask=j["ask"], pick={ch["id"]: ch["options"][0]}).get_json()
        assert j2["ok"] and j2["choices"] == [] and j2["problems"] == [] and len(j2["groups"]) == 1 and j2["ask"] == j["ask"], j2
        for bad in ({"new_teacher|Tan": "Nobody Atall"}, "x", {"a": 1}, {str(i): "x" for i in range(11)}, {"k": "x" * 251}):       # not offered, or the wrong shape: asked again
            j3 = _ask(words="", ask=j["ask"], pick=bad).get_json(); assert j3["ok"] and len(j3["choices"]) == 1 and j3["groups"] == [], bad
        bad_ask = dict(j["ask"], action="delete"); j4 = _ask(words="x", ask=bad_ask).get_json(); assert j4 == {"ok": False, "error": typed.FAILED}, j4
        j5 = _ask(words="x", ask="not a dict").get_json(); assert j5 == {"ok": False, "error": typed.FAILED}, j5

def test_a_failed_call_is_the_one_sentence_and_the_key_is_nowhere():   # Review Focus 1
    import io, logging, contextlib, typed; _grid_draft(); KEY = "sk-ant-test-not-a-key"
    for names in (dict(ANTHROPIC_API_KEY=KEY), dict(ANTHROPIC_API_KEY=None, AI_PROVIDER="anthropic", AI_API_KEY=KEY)):   # the key under either name
      with _typed_env(TYPED_REQUEST_MODEL=None, **names):
          def boom(words): raise RuntimeError("401 invalid x-api-key " + KEY)
          typed._call = boom                                                                     # never the real client
          logs, out, err = io.StringIO(), io.StringIO(), io.StringIO(); hd = logging.StreamHandler(logs); root = logging.getLogger(); root.addHandler(hd); old = root.level; root.setLevel(logging.DEBUG)
          try:
              with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err): r = _ask(words="move Art for 1A off Mon")
          finally: root.removeHandler(hd); root.setLevel(old)
          assert r.status_code == 200 and r.get_json() == {"ok": False, "error": typed.FAILED}, r.get_json()
          assert KEY not in r.get_data(as_text=True) and KEY not in logs.getvalue() and KEY not in out.getvalue() and KEY not in err.getvalue()
          assert c.get("/api/draft").get_json()["fixes"] == []

def test_a_fault_after_the_reading_says_so_and_leaves_a_trace_without_the_message():
    import io, logging, contextlib, typed; _grid_draft(); KEY = "sk-ant-test-not-a-key"; real = typed.answer
    with _typed_env(TYPED_REQUEST_MODEL="mock"):
        assert typed.BROKE == "Something went wrong working that out. The suggestions below still work."
        def broken(*a, **k): raise KeyError(KEY + " in a message")
        typed.answer = broken
        logs, err = io.StringIO(), io.StringIO(); hd = logging.StreamHandler(logs); lg = A.app.logger; lg.addHandler(hd); old = lg.level; lg.setLevel(logging.DEBUG)
        try:
            with contextlib.redirect_stderr(err): r = _ask(words="move Art for 1A off Mon")
        finally: lg.removeHandler(hd); lg.setLevel(old); typed.answer = real
        assert r.status_code == 200 and r.get_json() == {"ok": False, "error": typed.BROKE}, r.get_json()
        seen = logs.getvalue(); assert KEY not in r.get_data(as_text=True) and KEY not in seen and KEY not in err.getvalue() and "move Art" not in seen + err.getvalue()
        assert seen.count("typed request failed after reading: KeyError") == 1 and "draft.py" in seen and "in ask" in seen, seen           # the type name once, and the frames

def test_nobody_but_the_committee_reaches_the_typed_route_whether_it_is_on_or_off():
    def who(role_):
        k = A.app.test_client()
        if role_: 
            with k.session_transaction() as ss: ss["role"] = role_; ss["sid"] = "s1" if role_ == "personal" else None
        return k
    clients = {r: who(r) for r in ("teacher", "student", "personal", None)}
    if h: clients["head"] = h
    for env in (dict(TYPED_REQUEST_MODEL=None, ANTHROPIC_API_KEY=None), dict(TYPED_REQUEST_MODEL="mock")):
        with _typed_env(**env):
            for name, k in clients.items():
                ref = k.get("/api/draft/suggest?key=x"); r = _ask(k, words="move Art for 1A off Mon")
                assert r.status_code in (401, 403) and (r.status_code, r.get_json()) == (ref.status_code, ref.get_json()) and NOT_ON not in r.get_data(as_text=True), (name, env, r.status_code, r.get_json())
                assert "typed" not in (k.get("/api/status").get_json() or {})

def test_an_upload_over_unpublished_fixes_keeps_the_draft_as_a_version():
    spec = _grid_draft() and c.get("/api/setup").get_json()["spec"]; days, p = _grid_draft(); lid = _lid(); s = next(s for s in c.get(f"/api/draft/options?id={lid}").get_json()["slots"] if s["state"] == "ok" and not s["swap"])
    c.post("/api/draft/fix", json=dict(kind="move", id=lid, d=s["d"], p=s["p"])); rows = [("Mon", p, 1, "P1", "1A", "Art", ["Umairah Tan"])]
    r = c.post("/api/draft", data=_draft_form(spec, rows), content_type="multipart/form-data")
    assert r.status_code == 200 and isinstance(r.get_json()["kept"], dict) and r.get_json()["kept"]["kind"] == "upload", r.get_json()
    assert c.get("/api/draft").get_json()["fixes"] == []

def test_a_lesson_not_placed_refuses_the_printouts_and_the_download_and_a_new_upload_keeps_the_draft():
    spec = c.get("/api/setup").get_json()["spec"]; days, p = _grid_draft(); lid = _lid()
    j = c.post("/api/draft/fix", json=dict(kind="lift", id=lid)).get_json(); assert j["unplaced"] == 1 and j["critical"] >= 1, j
    one = "1 lesson is not placed. Place it or delete it on step 8 first."
    r = c.post("/api/draft/printouts", data=dict(single="0")); assert r.status_code == 409 and r.get_json() == {"error": one, "unplaced": 1}, r.get_json()
    r = c.get("/api/draft/download"); assert r.status_code == 409 and r.get_json() == {"error": one, "unplaced": 1}, r.get_json()
    assert c.post("/api/draft/publish").status_code == 409
    b = c.get("/api/draft/board").get_json(); assert [x["id"] for x in b["unplaced"]] == [lid] and b["unplaced"][0]["marks"] == ["notplaced"]
    r = c.post("/api/draft", data=_draft_form(spec, [("Mon", p, 1, "P1", "1A", "Art", ["Umairah Tan"])]), content_type="multipart/form-data")
    assert r.status_code == 200 and r.get_json()["kept"]["kind"] == "upload", r.get_json()
    assert c.get("/api/draft").get_json()["fixes"] == []

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

def test_a_draft_whose_fixes_are_published_or_not_is_replaced_without_the_question():
    spec = c.get("/api/setup").get_json()["spec"]; rows = [_lesson_of(spec, _one_class_row(spec), ["Nobody"])]
    c.post("/api/draft", data=_draft_form(spec, rows), content_type="multipart/form-data")
    mp = os.path.join(store.DATA, "draft", "meta.json"); meta = store.read_json(mp)
    store.write_json(mp, dict(meta, fixes=[{"x": 1}], published_fixes=1))
    assert c.post("/api/draft", data=_draft_form(spec, rows), content_type="multipart/form-data").status_code == 200
    store.write_json(mp, dict(store.read_json(mp), fixes=[{"x": 1}, {"x": 2}], published_fixes=1))
    assert c.post("/api/draft", data=_draft_form(spec, rows), content_type="multipart/form-data").status_code == 200

def test_publish_uses_the_setup_the_draft_was_checked_against():   # finding 10
    import draft
    spec = c.get("/api/setup").get_json()["spec"]; ds = spec["day_structure"]["P1"]; days = list(ds)   # one period at a time that is a lesson: no critical mistake
    c.post("/api/draft", data=_draft_form(spec, [(days[0], ds[days[0]].index("L"), 1, "P1", "1A", "Art", ["Umairah Tan"])], replace="1"), content_type="multipart/form-data")
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

def _clash_draft():   # 1A's Art and 1B's Art at the same time with one teacher: one critical mistake (a teacher in two places)
    spec = c.get("/api/setup").get_json()["spec"]; ds = spec["day_structure"]["P1"]; days = list(ds); p = ds[days[0]].index("L"); U = "Umairah Tan"
    rows = [(days[0], p, 1, "P1", "1A", "Art", [U]), (days[0], p, 1, "P1", "1B", "Art", [U])]
    r = c.post("/api/draft", data=_draft_form(spec, rows, replace="1"), content_type="multipart/form-data"); assert r.status_code == 200, r.get_json()
    return r.get_json()

def _settle_clash():   # a move of 1B's Art that leaves the clash, through the fix route
    lid = _lid("1B", "Art"); s = next(s for s in c.get(f"/api/draft/options?id={lid}").get_json()["slots"] if s["state"] == "ok" and not s["swap"])
    r = c.post("/api/draft/fix", json=dict(kind="move", id=lid, d=s["d"], p=s["p"])); assert r.status_code == 200, r.get_json()
    return r.get_json(), s

def test_the_draft_counts_critical_mistakes():
    j = _clash_draft(); crit = [w for w in j["warnings"] if w["crit"]]
    assert j["critical"] == 1 and len(crit) == 1 and crit[0]["crit"] == "teacher" and "left" not in j, (j["critical"], [w["key"] for w in crit])
    assert c.get("/api/draft").get_json()["critical"] == 1

def test_publish_is_refused_while_a_critical_mistake_remains():
    import draft
    _clash_draft(); before = store.published(); stamp = (before or {}).get("meta", {}).get("published_at")   # None while nothing is published
    r = c.post("/api/draft/publish"); j = r.get_json()
    assert r.status_code == 409 and j == {"error": draft.critical_text(1), "critical": 1}, j
    assert draft.critical_text(1) == "1 critical mistake must be settled on step 8 before the timetable can be published."
    assert draft.critical_text(3) == "3 critical mistakes must be settled on step 8 before the timetable can be published."
    assert (store.published() or {}).get("meta") == (before or {}).get("meta")   # the same record as before the refused attempt, or still none
    fixed, s = _settle_clash(); assert fixed["critical"] == 0, fixed["critical"]
    r = c.post("/api/draft/publish"); assert r.status_code == 200 and r.get_json()["published"] is True, r.get_json()
    assert store.published()["meta"]["published_at"] != stamp and store.published()["meta"]["open"] == c.get("/api/status").get_json()["published"]["open"]

def test_leave_it_is_gone():
    import draft
    j = _clash_draft(); k = next(w["key"] for w in j["warnings"] if not w["crit"]); assert draft.ANSWERS == ("step5", "open", "met")
    r = c.post("/api/draft/decide", json={"key": k, "answer": "left"}); assert r.status_code == 400 and r.get_json() == {"error": "Choose what to do with the warning."}, r.get_json()
    assert next(w for w in c.get("/api/draft").get_json()["warnings"] if w["key"] == k)["decision"] is None
    assert c.post("/api/draft/decide", json={"key": k, "answer": "open"}).status_code == 200

def test_a_draft_from_before_opens_and_its_left_warnings_are_open_again():
    import draft
    _clash_draft(); fixed, s = _settle_clash(); ws = [w for w in fixed["warnings"] if not w["crit"]]; kl, k5 = ws[0]["key"], ws[1]["key"]
    dp = os.path.join(draft.DIR, "decisions.json"); store.write_json(dp, {kl: dict(answer="left", at="then"), k5: dict(answer="step5", at="then")})
    r = c.get("/api/draft"); j = r.get_json(); assert r.status_code == 200 and len(j["fixes"]) == 1 and "left" not in j, j
    by = {w["key"]: w for w in j["warnings"]}
    assert by[kl]["decision"] is None and by[k5]["decision"]["answer"] == "step5" and j["open"] == len(ws) + sum(1 for w in j["warnings"] if w["crit"]) - 1, j["open"]
    assert set(store.read_json(dp)) == {k5} and store.read_json(dp)[k5]["answer"] == "step5"

def test_printouts_come_from_the_draft_with_its_fixes():
    import io, zipfile
    from ttgen.export import model_from_files
    _clash_draft(); fixed, s = _settle_clash()
    r = c.post("/api/draft/printouts", data=dict(single="0")); assert r.status_code == 200 and r.mimetype == "application/zip" and r.headers["X-Checks"], (r.status_code, r.get_data()[:200])
    z = zipfile.ZipFile(io.BytesIO(r.data)); db = next(n for n in z.namelist() if n.endswith(".sqlite")); tmp = tempfile.mkdtemp(); path = os.path.join(tmp, "p.sqlite")
    with open(path, "wb") as f: f.write(z.read(db))
    m = model_from_files(None, path); __import__("shutil").rmtree(tmp, ignore_errors=True); art = [x for x in m["lessons"] if x["subject"] == "Art" and x["classes"] == ["1B"]]
    assert len(art) == 1 and (art[0]["d"], art[0]["p"]) == (s["d"], s["p"]), [(x["d"], x["p"]) for x in art]
    assert any(n.endswith(".xlsx") for n in z.namelist()) and any(n.endswith(".html") for n in z.namelist())
    assert h is None or h.post("/api/draft/printouts", data=dict(single="0")).status_code == 401
    shutil = __import__("shutil"); shutil.rmtree(os.path.join(store.DATA, "draft"))
    r = c.post("/api/draft/printouts", data=dict(single="0")); assert r.status_code == 404 and r.get_json() == {"error": "There is no draft."}, r.get_json()

def test_printouts_with_a_draft_but_no_setup_are_409():   # the order of checks: no draft is 404 first, then a draft with no setup is 409
    _clash_draft(); real = store.setup_record
    store.setup_record = lambda: dict(real(), spec=None)
    try: r = c.post("/api/draft/printouts", data=dict(single="0"))
    finally: store.setup_record = real
    assert r.status_code == 409 and "Save the school's setup first" in r.get_json()["error"], (r.status_code, r.get_json())

def test_publishing_records_the_open_warnings():
    spec = c.get("/api/setup").get_json()["spec"]; ds = spec["day_structure"]["P1"]; days = list(ds)   # one period of Art for 1A at a time that is a lesson
    j = c.post("/api/draft", data=_draft_form(spec, [(days[0], ds[days[0]].index("L"), 1, "P1", "1A", "Art", ["Umairah Tan"])], replace="1"), content_type="multipart/form-data").get_json()
    assert j["critical"] == 0 and j["open"] > 0, (j["critical"], j["open"])
    r = c.post("/api/draft/publish"); assert r.status_code == 200, r.get_json()
    p = store.published()["meta"]; texts = [w["text"] for w in j["warnings"] if not w["decision"]]
    assert p["open"] == j["open"] == len(texts) and p["left"] == texts, (p["open"], j["open"])

def _ask_every_question():   # Ask about this: every look-up answers on the solved sample, and every option it offers is a change the board's preview accepts
    import ask as lookups
    m, rec, fx = A.draft._now(); x = m["lessons"][0]; c0 = x["classes"][0]; day = m["grid"][m["class_ix"][c0]["level"]]
    taken = {(y["d"], q) for y in m["lessons"] if c0 in y["classes"] for q in range(y["p"], y["p"] + y["n"])}
    d, p = next(((d, p) for d in range(len(m["days"])) for p in range(m["NP"]) if day[d][p] in "LA" and (d, p) not in taken), (0, 0))   # an empty period of that class
    asked = 0
    for q in lookups.QUESTIONS:
        for sub in ([dict(kind="place", by=by, name=name, d=d, p=p) for by, name in (("class", c0), ("teacher", x["teachers"][0]), ("room", x["room"] or next(iter(m["room_ix"]))))] if q in ("fill", "free") else [])\
                   + ([dict(kind="lesson", id=x["id"])] if q != "fill" else []):
            r = c.get("/api/draft/about", query_string=dict(q=q, **{k: v for k, v in sub.items()})); j = r.get_json(); assert r.status_code == 200, (q, sub, j)
            assert (j["text"] or q == "here") and j["title"] and isinstance(j["options"], list) and len(j["options"]) <= lookups.MOST + lookups.USED and j["stamp"] == c.get("/api/draft").get_json()["stamp"], (q, sub, j)
            for o in j["options"]:
                pv = A.draft.preview(o["fixes"]); assert pv["state"] in ("ok", "prefer", "no"), (q, o, pv); asked += 1
    assert asked, "no option was offered by any look-up"

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
    _ask_every_question()
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

class _Page:   # a browser's copy kept the way the page does (static/app.js syncNow): patches before our ops, our accepted ops, patches after
    def __init__(s, cid, rec, who=None): s.id, s.who, s.spec, s.v = cid, who or c, copy.deepcopy(rec["spec"]), rec["v"]
    def post(s, ops):
        j = s.who.post("/api/setup/changes", json={"since": s.v, "client": s.id, "ops": ops}).get_json(); return s._take(j, ops)
    def poll(s): return s._take(s.who.get(f"/api/setup/changes?since={s.v}&client={s.id}").get_json(), [])
    def _take(s, j, ops):
        assert not j.get("reset"), j
        ps, mine = j.get("patches", []), j.get("mine"); no = {x["i"] for x in j.get("refused", [])}
        sync.apply(s.spec, [o for p in ps if mine is None or p["v"] < mine for o in p["ops"]])
        sync.apply(s.spec, [o for i, o in enumerate(ops) if i not in no])
        sync.apply(s.spec, [o for p in ps if mine is not None and p["v"] > mine for o in p["ops"]])
        s.v = j["v"]; return j
    def same(s, what):
        r = c.get("/api/setup").get_json()
        assert s.v == r["v"] and not sync.diff(r["spec"], s.spec) and not sync.diff(s.spec, r["spec"]) and [x["_id"] for x in s.spec["lessons"]] == [x["_id"] for x in r["spec"]["lessons"]], (what, s.id, s.v, r["v"], sync.diff(r["spec"], s.spec)[:3])

def _cp_name(rec, client="A", parents=("Pastoral A",)):   # what a stale page sends: the subject, the name, the box, and no lesson ops
    cid = next(x["_id"] for x in rec["spec"]["classes"] if x["class"] == "1A")
    return [["add", "subjects", {"_id": "pcsubj001", "subject": PSUBJ, "code": "PC", "periods": {"Sec 1": 2}}, ""],
            ["school", "parents_subjects", [PSUBJ]], ["set", "classes", cid, "parents", list(parents)]]

def _cp_rows(spec): return {r["classes"][0]: r for r in spec["lessons"] if r.get("subject") == PSUBJ}

def test_class_parents_are_kept_right_on_the_server():               # Review Focus 1
    rec = _cp_start(); v0 = rec["v"]; a = _Page("A", rec); b = _Page("B", rec)
    j = a.post(_cp_name(rec))
    assert j["v"] == v0 + 2 and j["mine"] == v0 + 1, j                # the caller's change, then what the server put right
    a.same("sender")
    rows = _cp_rows(c.get("/api/setup").get_json()["spec"])
    sec1 = [x["class"] for x in rec["spec"]["classes"] if x["level"] == "Sec 1"]
    assert sorted(rows) == sorted(sec1) and rows["1A"]["teachers"] == ["Pastoral A"] and all(not rows[k]["teachers"] for k in sec1 if k != "1A"), rows
    assert rows["1A"]["_id"].startswith("cp-")
    assert len(j["patches"]) == 1 and j["patches"][0]["v"] == v0 + 2 and any(o[0] == "add" and o[1] == "lessons" for o in j["patches"][0]["ops"]), j   # the sender is told too
    k = b.poll(); assert [p["v"] for p in k["patches"]] == [v0 + 1, v0 + 2] and "mine" not in k, k    # a second browser gets both entries
    b.same("poller")
    assert [e["client"] for e in list(store._log)[-2:]] == ["A", "parents"]

def test_a_stale_tab_cannot_undo_a_following_lesson():
    rec = _cp_start(); a = _Page("A", rec); b = _Page("B", rec); a.post(_cp_name(rec))
    rec = c.get("/api/setup").get_json(); row = _cp_rows(rec["spec"])["1A"]; b.poll()
    stale = _Page("S", rec); stale.v = rec["v"]
    j = stale.post([["set", "lessons", row["_id"], "teachers", ["Koh"]]])
    assert j["v"] == rec["v"] + 2 and j["mine"] == rec["v"] + 1, j
    assert _cp_rows(c.get("/api/setup").get_json()["spec"])["1A"]["teachers"] == ["Pastoral A"]
    assert ["set", "lessons", row["_id"], "teachers", ["Pastoral A"]] in j["patches"][0]["ops"], j     # and the sender is told
    stale.same("stale sender (its copy must not keep Koh)"); b.poll(); b.same("poller"); a.poll(); a.same("A")

def test_a_hand_change_with_its_mark_is_kept():
    rec = _cp_start(); a = _Page("A", rec); a.post(_cp_name(rec))
    rec = c.get("/api/setup").get_json(); row = _cp_rows(rec["spec"])["1A"]; cid = next(x["_id"] for x in rec["spec"]["classes"] if x["class"] == "1A")
    j = a.post([["set", "lessons", row["_id"], "teachers", ["Koh"]], ["set", "lessons", row["_id"], "by_hand", True]])
    assert j["v"] == rec["v"] + 1 and not j["patches"] and j["mine"] == j["v"], j
    j = a.post([["set", "classes", cid, "parents", ["Pastoral B"]]]); assert j["v"] == rec["v"] + 2, j
    r = _cp_rows(c.get("/api/setup").get_json()["spec"])["1A"]; assert r["teachers"] == ["Koh"] and r["by_hand"] is True, r
    a.same("A")

def test_a_head_cannot_change_a_staffed_lesson():                    # in NEED_HEADS
    rec = _cp_start(); _Page("A", rec).post(_cp_name(rec))
    rec = c.get("/api/setup").get_json(); row = _cp_rows(rec["spec"])["1A"]; hp = _Page("H", rec, h)
    j = hp.post([["set", "lessons", row["_id"], "teachers", ["Koh"]], ["set", "lessons", row["_id"], "students", 5]])
    assert j["refused"] == [{"i": 0, "why": sync.PARENTS_WHY}] and j["v"] == rec["v"] + 1, j
    r = _cp_rows(c.get("/api/setup").get_json()["spec"])["1A"]; assert r["teachers"] == ["Pastoral A"] and r["students"] == 5, r
    hp.same("head")
    rec = c.get("/api/setup").get_json(); one = dict(_id="hb1", level="Sec 1", subject="Mathematics", block=None, classes=["1A"], teachers=["Typed T"])   # two steps of one batch
    j = hp.post([["add", "lessons", one, ""], ["set", "lessons", "hb1", "subject", PSUBJ]])
    assert [x["i"] for x in j["refused"]] == [1] and j["refused"][0]["why"] == sync.PARENTS_WHY, j
    r = next(x for x in c.get("/api/setup").get_json()["spec"]["lessons"] if x["_id"] == "hb1"); assert r["subject"] == "Mathematics" and r["teachers"] == ["Typed T"], r

def test_a_head_sends_a_malformed_lessons_op():                     # in NEED_HEADS
    rec = _cp_start(); _Page("A", rec).post(_cp_name(rec))
    rec = c.get("/api/setup").get_json(); row = _cp_rows(rec["spec"])["1A"]; hp = _Page("H", rec, h)
    other = next(x for x in rec["spec"]["lessons"] if x["subject"] != PSUBJ)     # a row the rule does not take: the old code read op[4] here
    j = hp.post([["set", "lessons", other["_id"], "note"], ["merge", "lessons", row["_id"], "block", [], []]])
    assert [x["i"] for x in j["refused"]] == [0, 1], j
    r = _cp_rows(c.get("/api/setup").get_json()["spec"])["1A"]; assert r["teachers"] == ["Pastoral A"] and r["block"] is None, r

def test_a_school_not_using_class_parents_gets_one_version_and_one_entry():
    rec = _cp_start(); n = len(store._log); v = rec["v"]
    code, j = _changes("A", v, [["school", "timetable", "Term 3"]]); assert j["v"] == v + 1 and j["mine"] == v + 1 and len(store._log) == n + 1, j

def test_a_setup_put_whole_is_put_right():
    spec = c.get("/api/sample/secondary").get_json()
    spec["subjects"].append({"subject": PSUBJ, "code": "PC", "periods": {"Sec 1": 2}}); spec["school"]["parents_subjects"] = [PSUBJ]
    next(x for x in spec["classes"] if x["class"] == "1A")["parents"] = ["Pastoral A"]
    spec["lessons"].append({"level": "Sec 1", "subject": PSUBJ, "block": None, "classes": ["1A"], "teachers": ["Someone Else"], "students": None})
    assert c.put("/api/setup", json=spec).status_code == 200
    rows = _cp_rows(c.get("/api/setup").get_json()["spec"])
    assert rows["1A"]["teachers"] == ["Pastoral A"] and "by_hand" not in rows["1A"] and len(rows) == 4, rows
    _cp_start()                                                       # the sample back, for the tests after

def _cp_draft(spec, teachers):   # a draft of one lesson: the staffed Pastoral Care lesson of 1A taken by the given teachers
    row = _cp_rows(spec)["1A"]; c.post("/api/draft", data=_draft_form(spec, [_lesson_of(spec, dict(row, periods=2), teachers)]), content_type="multipart/form-data"); return row

def test_update_step_5_on_a_staffed_lesson_keeps_the_timetables_teachers():
    rec = _cp_start(); a = _Page("A", rec); a.post(_cp_name(rec))
    spec = c.get("/api/setup").get_json()["spec"]; row = _cp_rows(spec)["1A"]; assert row["teachers"] == ["Pastoral A"] and "by_hand" not in row
    _cp_draft(spec, ["Elsewhere T"]); k = f"dep:C:1A:{PSUBJ}:teachers"; j = c.get("/api/draft").get_json(); w = next(x for x in j["warnings"] if x["key"] == k)
    assert w["ops"] == [["set", "lessons", row["_id"], "teachers", ["Elsewhere T"]], ["set", "lessons", row["_id"], "by_hand", True]], w["ops"]
    assert c.post("/api/draft/decide", json={"key": k, "answer": "step5"}).status_code == 200
    spec = c.get("/api/setup").get_json()["spec"]; r = _cp_rows(spec)["1A"]; assert r["teachers"] == ["Elsewhere T"] and r["by_hand"] is True, r
    cid = next(x["_id"] for x in spec["classes"] if x["class"] == "1A")                       # another change: the box changes, the marked lesson stays
    assert c.post("/api/setup/changes", json={"client": "t", "since": c.get("/api/setup").get_json()["v"], "ops": [["set", "classes", cid, "parents", ["Pastoral B"]]]}).status_code == 200
    r = _cp_rows(c.get("/api/setup").get_json()["spec"])["1A"]; assert r["teachers"] == ["Elsewhere T"] and r["by_hand"] is True, r
    _cp_start()

def test_published_pages_name_the_class_parents():
    import io, pickle
    from ttgen import export
    rec = _cp_start(); a = _Page("A", rec); a.post(_cp_name(rec, parents=("Pastoral A", "Pastoral B")))
    spec = c.get("/api/setup").get_json()["spec"]; row = _cp_rows(spec)["1A"]
    _cp_draft(spec, ["Pastoral A", "Pastoral B"]); assert c.post("/api/draft/publish").status_code == 200
    m = store.published()["model"]; line = " · Form teachers: Pastoral A, Pastoral B"
    assert next(x for x in m["classes"] if x["name"] == "1A")["parents"] == ["Pastoral A", "Pastoral B"] and m["parents_name"] == "Form teachers"
    assert next(x for x in m["classes"] if x["name"] == "1B")["parents"] == []
    assert export.class_view(m, "1A")["subtitle"].endswith(line) and "Form teachers" not in export.class_view(m, "1B")["subtitle"]
    assert export.teacher_view(m, "Pastoral A")["subtitle"].endswith(" · Form teachers of 1A")
    d = export.html_data(m); assert next(x for x in d["classes"] if x[0] == "1A")[4] == ["Pastoral A", "Pastoral B"] and d["parents_name"] == "Form teachers", d
    assert all(len(v) == 3 and v[2] == (m["subjects"][k].get("dept") or "") for k, v in d["subjects"].items()) and any(v[2] for v in d["subjects"].values()), d["subjects"]   # each subject's department travels to the page, for the Lessons view's Department filter
    assert all(v[2] == "" for vw in ("student",) for v in export.html_data(m, vw)["subjects"].values())   # not to a student's page
    src0 = open(os.path.join(ROOT, "ttgen", "timetable_page.html"), encoding="utf-8").read()
    assert all(t in src0 for t in ('data-lview="${k}"', "function drawLessonGrids()", "function drawLessonPage()", 'data-f="dept"', "deptOf(x.subject) !== f.dept")), "the Lessons view's three views and its Department filter"["classes"][:2]
    pdf = c.get("/pdf/classes/1A"); assert pdf.status_code == 200 and pdf.data[:4] == b"%PDF"
    assert '"parents_name":"Form teachers"' in c.get("/timetable").get_data(as_text=True)
    old = pickle.loads(pickle.dumps(m)); old.pop("parents_name")                                  # a model pickled before this change
    for x in old["classes"]: x.pop("parents")
    assert export.class_view(old, "1A")["subtitle"] == export.class_view(m, "1A")["subtitle"].replace(line, "")
    assert export.teacher_view(old, "Pastoral A")["subtitle"] == "Teacher" and export.html_data(old)["parents_name"] == "Form teachers" and all(len(x) == 5 and x[4] == [] for x in export.html_data(old)["classes"])
    assert export.pdf_bytes(old, export.class_view(old, "1A"))[:4] == b"%PDF" and export.pdf_bytes(old, export.teacher_view(old, "Pastoral A"))[:4] == b"%PDF"
    shutil = __import__("shutil"); shutil.rmtree(os.path.join(store.DATA, "draft"), ignore_errors=True); _cp_start()

def test_a_class_form_teachers_are_never_cut_off_the_printed_timetable():
    import copy as cp
    from ttgen import export
    from reportlab.pdfbase.pdfmetrics import stringWidth
    rec = _cp_start(); a = _Page("A", rec); names = ["Mrs Alexandrina Featherstonehaugh-Smythe", "Mr Bartholomew Wolfeschlegelstein", "Ms Cornelia Vandenberghe-Okonkwo", "Dr Maximilian Papadopoulos-Lindqvist"]
    a.post(_cp_name(rec, parents=names)); spec = c.get("/api/setup").get_json()["spec"]; _cp_draft(spec, names); assert c.post("/api/draft/publish").status_code == 200
    m = store.published()["model"]; v = export.class_view(m, "1A"); lines = export._parents_block(v)
    assert len(lines) >= 2 and "…" not in "".join(lines) and all(any(n in l for l in lines) for n in names), lines   # each name whole on one line
    R, _ = export._fonts(); assert all(stringWidth(l, R, 8.6) <= 420 for l in lines), lines
    assert "Form teachers" not in v["pdf_subtitle"] and v["subtitle"].endswith(", ".join(names))
    assert export.pdf_bytes(m, v)[:4] == b"%PDF"
    plain = cp.deepcopy(m)                                         # no form teachers: the page comes out exactly as a model without the keys draws it
    for x in plain["classes"]: x["parents"] = []
    old = cp.deepcopy(m); old.pop("parents_name")
    for x in old["classes"]: x.pop("parents")
    import re; same = lambda x: re.sub(rb"/(CreationDate|ModDate)\s*\([^)]*\)|/ID\s*\[[^\]]*\]", b"", x)   # a PDF's date and id differ on every run
    assert export._parents_block(export.class_view(plain, "1B")) == [] and same(export.pdf_bytes(plain, export.class_view(plain, "1A"))) == same(export.pdf_bytes(old, export.class_view(old, "1A")))
    for cl in m["classes"]:                                        # every class page still draws, with the block, within the page
        pb = export.pdf_bytes(m, dict(export.class_view(m, cl["name"]), parents_line="Form teachers: " + ", ".join(names))); assert pb[:4] == b"%PDF"
    shutil = __import__("shutil"); shutil.rmtree(os.path.join(store.DATA, "draft"), ignore_errors=True); _cp_start()

def test_a_published_room_page_shows_its_equipment():
    import copy as cp, io, pickle
    from ttgen import export
    from reportlab.pdfbase.pdfmetrics import stringWidth
    rec = _cp_start(); a = _Page("A", rec); a.post(_cp_name(rec)); spec = c.get("/api/setup").get_json()["spec"]
    shutil = __import__("shutil"); _cp_draft(spec, ["Pastoral A"]); assert c.post("/api/draft/publish").status_code == 200
    used, other = spec["venues"][0]["room"], spec["venues"][1]["room"]   # the timetable file here names no room: every room of the setup is on the published model
    shutil.rmtree(os.path.join(store.DATA, "draft"), ignore_errors=True)
    spec = c.get("/api/setup").get_json()["spec"]; vid = next(v["_id"] for v in spec["venues"] if v["room"] == used)
    assert c.post("/api/setup/changes", json={"client": "t", "since": c.get("/api/setup").get_json()["v"], "ops": [
        ["set", "venues", vid, "equipment", ["30 keyboards", "2 amps"]], ["set", "venues", vid, "configuration", "cluster seating"]]}).status_code == 200
    _cp_draft(c.get("/api/setup").get_json()["spec"], ["Pastoral A"]); assert c.post("/api/draft/publish").status_code == 200
    m = store.published()["model"]; ix = {r["name"]: r for r in m["rooms"]}
    assert ix[used]["equipment"] == ["30 keyboards", "2 amps"] and ix[used]["configuration"] == "cluster seating"
    assert ix[other]["equipment"] == [] and ix[other]["configuration"] == ""
    end = " · Equipment: 30 keyboards, 2 amps · Configuration: cluster seating"; v = export.room_view(m, used)
    assert v["subtitle"].endswith(end) and v["pdf_subtitle"] == v["subtitle"][:-len(end)], v["subtitle"]
    info = ix[other]
    want = info["kind"].capitalize() + (f" · holds {info['capacity']}" if info["capacity"] else "")
    vo = export.room_view(m, other); assert vo["subtitle"] == want and export._parents_block(vo) == [], vo["subtitle"]
    pdf = c.get(f"/pdf/rooms/{used}"); assert pdf.status_code == 200 and pdf.data[:4] == b"%PDF"
    old = pickle.loads(pickle.dumps(m))
    for r in old["rooms"]: r.pop("equipment"); r.pop("configuration")
    assert export.room_view(old, used)["subtitle"] == v["subtitle"][:-len(end)] and export.room_view(old, other)["subtitle"] == want
    assert export.pdf_bytes(old, export.room_view(old, used))[:4] == b"%PDF"
    big = cp.deepcopy(m); items = [f"{i:02d} " + "x" * 27 for i in range(12)]; assert all(len(i) == 30 for i in items)
    next(r for r in big["rooms"] if r["name"] == used)["equipment"] = items
    vb = export.room_view(big, used); lines = export._parents_block(vb); R, _ = export._fonts()
    assert len(lines) >= 2 and all(stringWidth(l, R, 8.6) <= 420 for l in lines) and all(any(i in l for l in lines) for i in items), lines
    assert export.pdf_bytes(big, vb)[:4] == b"%PDF"
    # the Excel heading line keeps every stat the plain subtitle does not hold (equipment text must not hide "30 periods used")
    import openpyxl
    three = cp.deepcopy(m); next(r for r in three["rooms"] if r["name"] == used)["equipment"] = ["30 keyboards", "2 amps", "1 projector"]
    three["lessons"][0]["room"] = used                                 # the sample timetable names no room: put one lesson in it so the room has a sheet and stats
    vt = export.room_view(three, used); xp = os.path.join(tempfile.mkdtemp(), "t.xlsx"); export.write_excel(three, xp, log=lambda *a: None)
    ws = openpyxl.load_workbook(xp)["Rooms"]
    r0 = next(r for r in range(1, ws.max_row + 1) if ws.cell(r, 1).value == used); head = ws.cell(r0 + 1, 1).value
    for a_, b_ in vt["stats"]:
        if str(a_) not in vt["pdf_subtitle"]: assert f"{a_} {b_}" in head, (a_, b_, head)
    # the published web page: its data rows, an older model, and the served page
    rows = {r[0]: r for r in export.html_data(m)["rooms"]}
    assert rows[used][3:] == [["30 keyboards", "2 amps"], "cluster seating", []] and rows[other][3:] == [[], "", []], rows[used]
    assert all(r[3:] == [[], "", []] for r in export.html_data(old)["rooms"])
    page = c.get("/timetable").get_data(as_text=True); assert "30 keyboards" in page and "Equipment: " in page
    xs = cp.deepcopy(m); next(r for r in xs["rooms"] if r["name"] == used)["equipment"] = ["<b>x</b>"]
    html = export.render_html(xs)                                    # the item travels as JSON in a script, its "</" escaped: no raw tag anywhere in the page text
    assert "<b>x</b>" not in html and "<b>x<\\/b>" in html
    src = open(os.path.join(ROOT, "ttgen", "timetable_page.html"), encoding="utf-8").read()
    assert "${esc(v.sub || \"\")}" in src and "Equipment: ${" in src                                # the header is built from sub through esc(), as the Class Parents line is
    # a long configuration wraps at " · " too: every line within the subtitle's width
    lg = cp.deepcopy(m); rr = next(r for r in lg["rooms"] if r["name"] == used); rr["equipment"] = ["30 keyboards", "2 amps", "1 projector"]; rr["configuration"] = "cluster seating " + "with a very long note about the layout " * 2 + "end"
    assert len(rr["configuration"]) >= 90; ls = export._parents_block(export.room_view(lg, used))
    assert len(ls) >= 2 and all(stringWidth(l, R, 8.6) <= 420 for l in ls), ls
    assert export.pdf_bytes(lg, export.room_view(lg, used))[:4] == b"%PDF"
    # a pasted inventory does not push the printed grid off the page: at most six lines, the last ending "…"; a list that fits is whole
    assert "…" not in " ".join(lines) and len(lines) <= 6, lines
    inv = cp.deepcopy(m); next(r for r in inv["rooms"] if r["name"] == used)["equipment"] = [f"{i:03d} " + "y" * 26 for i in range(120)]
    vi_ = export.room_view(inv, used); li = export._parents_block(vi_)
    assert len(li) == 6 and li[-1].endswith(" …") and all(stringWidth(l, R, 8.6) <= 420 for l in li) and "000 " in li[0], li
    assert "119 " in vi_["subtitle"] and export.pdf_bytes(inv, vi_)[:4] == b"%PDF"            # the web page and the Excel file still hold the whole list
    many = cp.deepcopy(m); cv = export.class_view(many, many["classes"][0]["name"]); cv["parents_line"] = "Form teachers: " + ", ".join(f"Teacher Number {i:02d}" for i in range(60))
    assert len(export._parents_block(cv)) > 6 and "…" not in " ".join(export._parents_block(cv))   # form teachers are never cut, however many
    shutil.rmtree(os.path.join(store.DATA, "draft"), ignore_errors=True); _cp_start()

NEED_HEADS = {"test_a_head_cannot_give_a_second_department", "test_a_heads_old_can_teach_change_is_refused_and_the_rest_of_the_batch_lands", "test_a_head_cannot_change_a_staffed_lesson", "test_a_head_sends_a_malformed_lessons_op", "test_a_head_can_change_groups_but_not_classes", "test_a_heads_map_batch_is_applied_whole", "test_a_heads_refused_change_is_skipped_and_the_rest_applied", "test_a_heads_batch_that_is_all_refused_changes_nothing", "test_a_teacher_added_by_a_head_is_provisional",
              "test_a_head_can_edit_only_provisional_teachers", "test_a_head_can_add_and_fill_in_a_teacher_in_one_request", "test_the_head_check_runs_on_the_setup_held_under_the_lock", "test_a_head_cannot_download_or_publish_or_replace", "test_a_head_cannot_reach_the_helper_routes"}

if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_") and (k != "test_publish_uploaded_timetable" or "--full" in sys.argv)
             and (h or k not in NEED_HEADS)]
    for t in tests: t(); print("ok", t.__name__)
    print(f"{len(tests)} checks passed")

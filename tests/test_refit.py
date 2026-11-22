"""Plain-assert tests for the re-fit: .venv/bin/python tests/test_refit.py"""
import contextlib, copy, gzip, io, json, logging, os, re, secrets, shutil, sys, tempfile, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = tempfile.mkdtemp()
CODE = secrets.token_hex(4)
os.environ.pop("HEADS_CODE", None)
os.environ.update(DATA_DIR=DATA, SECRET_KEY=secrets.token_hex(16), AI_PROVIDER="anthropic", AI_API_KEY="", COMMITTEE_CODE=CODE, TEACHER_CODE=secrets.token_hex(4), STUDENT_CODE=secrets.token_hex(4))
sys.path.insert(0, ROOT)
import openpyxl  # noqa: E402
import app as A, draft, fixes, helper, refit, refit_plan, store  # noqa: E402
from ttgen import export, verify  # noqa: E402
from ttgen.export import ENTIRE  # noqa: E402
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
        for x in report: wr.append(list(x))
    buf = io.BytesIO(); wb.save(buf); return buf.getvalue()

_made = {}   # the setup workbook is made once: every upload here sends the same one
def setup_bytes(spec):
    if "b" not in _made: p = os.path.join(tempfile.mkdtemp(), "setup.xlsx"); write_template(spec, p); _made["b"] = open(p, "rb").read()
    return _made["b"]

def save_draft(rows, report=()):
    r = c.post("/api/draft", data=dict(setup=(io.BytesIO(setup_bytes(SPEC)), "setup.xlsx"), timetable=(io.BytesIO(workbook(rows, report)), "timetable.xlsx"), replace="1"), content_type="multipart/form-data")
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
SPEC_CHECKED = draft.model_now()[0]["checked_setup"]

NOW = store.now

PREFER_RULE = dict(scope="Teacher", target=TEACHERS[0], rule="Not available", week="Both", day=DAYS[0], **{"from": 0, "to": 0}, strength="Prefer", note="made-up wish")
MUST_RULE = dict(PREFER_RULE, strength="Must", note="made-up need")

def put_setup(spec):
    r = c.put("/api/setup", json=spec); assert r.status_code == 200, r.get_json()

def changed(rules=()):
    """the sample setup with the plain lesson's row taught by another teacher, and these rules added; returns the spec to put back"""
    was = json.loads(json.dumps(store.setup_record()["spec"])); s = json.loads(json.dumps(was))
    row = next(x for x in s["lessons"] if x["subject"] == SUBJ and CLASSES[0] in x["classes"] and x.get("code") == ENTIRE)
    row["teachers"] = [TEACHERS[1]]; s["rules"] = list(s["rules"]) + list(rules); put_setup(s); return was

def warnings(): return c.get("/api/draft").get_json()["warnings"]

def test_targets_are_the_open_fixable_warnings():
    save_draft(ROWS); was = changed([MUST_RULE])
    try:
        ws = warnings(); ts = refit.targets(ws)
        assert ts and all(set(t) == {"kind", "key", "text", "w"} and t["key"] == t["w"]["key"] and t["text"] == t["w"]["text"] for t in ts), ts
        teach = f"dep:C:{CLASSES[0]}:{SUBJ}:teachers"
        keys = [t["key"] for t in ts]; assert teach in keys, keys
        rule = [t for t in ts if t["kind"] == "rule"]; assert rule and all(t["w"]["strength"] == "Must" for t in rule), ts
        assert keys.index(teach) < keys.index(rule[0]["key"])
        order = ["teachers", "missing", "periods", "extra", "venue", "half", "clash", "rule"]
        ranks = [order.index(t["kind"]) for t in ts]; assert ranks == sorted(ranks), [t["kind"] for t in ts]
        assert {"teachers", "missing", "extra", "clash", "rule"} <= {t["kind"] for t in ts}, [t["kind"] for t in ts]
        assert all(t["w"]["kind"] in ("deployment", "clash", "rule") for t in ts)
        assert refit.needed(ws) is True and refit.needed([]) is False and refit.targets([]) == []
        assert refit.targets(ws) == ts   # pure: the same list gives the same answer
    finally: put_setup(was)

def test_answered_warnings_are_left_out():
    save_draft(ROWS); was = changed([MUST_RULE])
    try:
        ts = refit.targets(warnings()); first = ts[0]["key"]
        # a decision laid on as the draft does it (draft.tally); the route's "met" is only for a rule to check again, so the answer here is "step5"
        ws = draft.tally(warnings(), {first: dict(answer="step5", at=store.now())})["warnings"]
        after = refit.targets(ws); assert first not in [t["key"] for t in after] and len(after) == len(ts) - 1
        assert [w["decision"] for w in ws if w["key"] == first][0]["answer"] == "step5"
        assert refit.needed([dict(w, decision=dict(answer="step5")) for w in warnings()]) is False
    finally: put_setup(was)

def test_a_prefer_rule_is_not_a_target():
    save_draft(ROWS); was = changed([PREFER_RULE])
    try:
        ws = warnings(); prefer = [w for w in ws if w["kind"] == "rule" and w["strength"] == "Prefer" and not w.get("decision")]
        assert prefer, [w["key"] for w in ws if w["kind"] == "rule"]
        ts = refit.targets(ws); assert not [t for t in ts if t["w"]["strength"] != "Must"] and not [t for t in ts if t["kind"] == "rule"]
        made = [dict(w, kind="typed", key="typed:1:Not met", strength="Must", decision=None) for w in prefer[:1]] + [dict(prefer[0], kind="deployment", key="dep:C:1A:English Language:other", strength="Must", decision=None)]
        assert refit.targets(made) == [], refit.targets(made)   # a typed warning, and a deployment part that is not one of the six
    finally: put_setup(was)

def test_an_allowed_double_is_not_a_target():
    w = lambda crit: dict(key="clash:made up " + crit, kind="clash", text="x", strength="Must", decision=None, crit=crit)
    assert refit.targets([w("")]) == [] and refit.needed([w("")]) is False and [t["kind"] for t in refit.targets([w("teacher"), w(""), w("room")])] == ["clash", "clash"]
    two = [one(2, 0, 1, CLS, EL, T1), one(3, 0, 1, CLS_B, EL, T1)]; said = lambda ts, start: [k for k in ts if k.startswith("clash:" + start)]
    m, spec, days, pool, ts = case(two); assert said(ts, "Teacher double-booked: ")
    allow = lambda s: s["school"].update(extra_settings=list(s["school"].get("extra_settings") or []) + [["Teachers may take two lessons at once on", DAYS[0]]])
    m, spec, days, pool, ts = case(two, allow); assert m["double"] == {0} and not said(ts, "Teacher")   # the day the setup allows it
    ws = [w for w in verify.warnings(m, spec)["warnings"] if w["key"].startswith("clash:Teacher in two lessons (allowed that day)")]; assert len(ws) == 1 and ws[0]["crit"] == ""   # step 8 still says it

def test_a_subject_with_a_colon_and_a_repeated_key_keep_their_part():
    w = lambda key: dict(key=key, kind="deployment", text="x", strength="Must", decision=None)
    ts = refit.targets([w("dep:C:1A:English Language (Standard):extra"), w("dep:C:1A:Maths: Extra:teachers#2"), w("dep:G:G1:half")])
    assert [t["kind"] for t in ts] == ["teachers", "extra", "half"] and ts[0]["key"] == "dep:C:1A:Maths: Extra:teachers#2", ts

# ----------------------------------------------------------------------------------------------- direct: the change itself for each kind
CLS = CLASSES[0]; EL = SUBJ   # the plain lesson's class and subject (an entire-class key of step 5)
KEY = f"C:{CLS}:{EL}"

def world(rows):
    """save the draft and return (model, a copy of the checked setup to change, days, pool)"""
    save_draft(rows); m, rec, fx = draft.model_now()
    return m, copy.deepcopy(m["checked_setup"]), m["days"], fx["pool"]

def target(kind, key, text="made-up warning text"):
    part = "dep:" + key + ":" + kind if kind not in ("clash", "rule") else key
    return dict(kind=kind, key=part, text=text, w=dict(key=part, kind="deployment", text=text))

def step5_row(spec, key=KEY):
    k = key.split(":", 2); return next(r for r in spec["lessons"] if r["subject"] == k[2] and k[1] in r["classes"] and r.get("code") == ENTIRE)

def snapshot(m, pool): return json.dumps([m["lessons"], list(pool)], sort_keys=True, default=str)

def test_one_teacher_for_another_is_one_teacher_fix():
    m, spec, days, pool = world(ROWS); before = snapshot(m, pool)
    step5_row(spec)["teachers"] = [TEACHERS[1]]   # the plain lesson is taught by TEACHERS[0] on the timetable
    got = refit.direct(m, spec, days, target("teachers", KEY), pool)
    assert got == ([[dict(kind="teacher", key=KEY, teachers=[TEACHERS[1]])]], None), got
    row = next(x for x in m["lessons"] if x["id"] == PLAIN_ID); row_t = list(row["teachers"])
    # the rest of a row's teachers are kept, in that row's order
    ROW2 = [dict(r, teachers=[TEACHERS[2], TEACHERS[0]]) if r["id"] == PLAIN_ID else r for r in ROWS]
    m2, spec2, days2, pool2 = world(ROW2)
    step5_row(spec2)["teachers"] = [TEACHERS[2], TEACHERS[1]]
    assert refit.direct(m2, spec2, days2, target("teachers", KEY), pool2) == ([[dict(kind="teacher", key=KEY, teachers=[TEACHERS[2], TEACHERS[1]])]], None)
    assert snapshot(m, pool) == before and row["teachers"] == row_t

def test_two_teachers_changing_needs_you():
    m, spec, days, pool = world(ROWS)
    step5_row(spec)["teachers"] = [TEACHERS[1], TEACHERS[2]]   # one on the timetable, two on step 5
    assert refit.direct(m, spec, days, target("teachers", KEY), pool) == ([], refit.NOT_ONE)
    step5_row(spec)["teachers"] = []
    c, s = refit.direct(m, spec, days, target("teachers", KEY, "its own words"), pool); assert c == [] and s == "its own words", (c, s)

def test_a_teacher_added_or_taken_off_is_not_a_change():
    m, spec, days, pool = world(ROWS); says = "A teacher is added or taken off, not changed for another: change it on the board."; assert refit.ONE_SIDED == says
    step5_row(spec)["teachers"] = [TEACHERS[0], TEACHERS[1]]; assert refit.direct(m, spec, days, target("teachers", KEY), pool) == ([], says)   # added
    m, spec, days, pool = world([dict(r, teachers=[TEACHERS[0], TEACHERS[1]]) if r["id"] == PLAIN_ID else r for r in ROWS]); step5_row(spec)["teachers"] = [TEACHERS[1]]; assert refit.direct(m, spec, days, target("teachers", KEY), pool) == ([], says)   # taken off
    m, spec, days, pool = world([dict(r, teachers=[]) if r["id"] == PLAIN_ID else r for r in ROWS]); step5_row(spec)["teachers"] = [TEACHERS[0]]; assert refit.direct(m, spec, days, target("teachers", KEY), pool) == ([], says)   # nobody has it
    step5_row(spec)["teachers"] = [TEACHERS[0], TEACHERS[1]]; assert refit.direct(m, spec, days, target("teachers", KEY), pool) == ([], refit.NOT_ONE)   # two added
    m, spec, days, pool = world([dict(r, teachers=[TEACHERS[0], TEACHERS[1]]) if r["id"] == PLAIN_ID else r for r in ROWS]); step5_row(spec)["teachers"] = [TEACHERS[2]]; assert refit.direct(m, spec, days, target("teachers", KEY), pool) == ([], refit.NOT_ONE)   # two for one

def test_a_lesson_of_a_row_with_nobody_is_not_offered():
    bare = lambda key, **k: lambda s: step5_row(s, key).update(teachers=[], **k); key = f"C:{CLASSES[1]}:{EL}"; says = "Step 5 has no teacher for it: choose one there first, then run Re-fit again."; assert refit.NO_STAFF == says
    m, spec, days, pool, ts = case([], bare(key, periods=2, length=1)); t = ts[f"dep:{key}:missing"]; assert refit.direct(m, spec, days, t, pool) == ([], says)
    got, stats = hunt(m, spec, days, t, pool); assert got is None and stats == dict(nodes=0, reason=says, late=False), (got, stats)
    m, spec, days, pool, ts = case([one(1, 0, 1)], bare(KEY, periods=2, length=1)); t = ts[f"dep:{KEY}:periods"]; assert refit.direct(m, spec, days, t, pool) == ([], says)
    m, spec, days, pool, ts = case([one(1, 0, 1), one(2, 1, 1)], bare(KEY, periods=1, length=1)); c_, s_ = refit.direct(m, spec, days, ts[f"dep:{KEY}:periods"], pool); assert s_ is None and [x[0]["kind"] for x in c_] == ["delete"] * 2   # one too many may go
    b = next(k for k, e in verify.planned_rows(SPEC_CHECKED).items() if k[0] == "G" and any(r.get("block") for r in e["rows"]))
    def empty(s): [r.update(teachers=[]) for r in s["lessons"] if r.get("code") == b[1]]
    m, spec, days, pool, ts = case([], empty); assert refit.direct(m, spec, days, ts[f"dep:G:{b[1]}:missing"], pool) == ([], refit.BAND)   # a band's comes first

def test_split_lessons_need_you():
    split = ROWS + [dict(id=5, day=DAYS[4], p=0, n=1, level=LEVEL, classes=[CLS], subject=EL, teachers=[TEACHERS[2]])]
    m, spec, days, pool = world(split)
    step5_row(spec)["teachers"] = [TEACHERS[0], TEACHERS[1]]   # the timetable has TEACHERS[0] on one lesson, TEACHERS[2] on the other
    assert refit.direct(m, spec, days, target("teachers", KEY), pool) == ([], refit.SPLIT)
    step5_row(spec)["teachers"] = [TEACHERS[1]]   # both a split and more than one change: NOT_ONE wins
    assert refit.direct(m, spec, days, target("teachers", KEY), pool) == ([], refit.NOT_ONE)

def test_a_teacher_not_on_the_list_needs_you():
    m, spec, days, pool = world(ROWS)
    step5_row(spec)["teachers"] = [TEACHERS[1]]; spec["teachers"] = [t for t in spec["teachers"] if t["name"] != TEACHERS[1]]
    c, s = refit.direct(m, spec, days, target("teachers", KEY), pool)
    assert c == [] and s == f"{TEACHERS[1]} is not on the setup's list of teachers.", (c, s)
    try: fixes.apply_one(copy.deepcopy(m["lessons"]), dict(kind="teacher", key=KEY, teachers=[TEACHERS[1]]), spec, days, touched=set(), was=[], pool=[])
    except ValueError as e: assert str(e) == s, str(e)
    else: raise AssertionError("the judge would have allowed it")

def test_a_missing_lesson_is_added():
    m, spec, days, pool = world(ROWS); before = snapshot(m, pool)
    key = f"C:{CLASSES[1]}:{EL}"   # step 5 has it, the timetable does not
    assert not helper._of_key(m["lessons"], fixes._key(key))
    want = next(x for x in fixes.short(m, spec, pool) if x["key"] == key)
    c, s = refit.direct(m, spec, days, target("missing", key), pool); assert s is None and c, (c, s)
    assert all(len(x) == 1 and x[0]["kind"] == "add" and x[0]["key"] == key and x[0]["n"] == want["n"] for x in c)
    assert all(x[0]["room"] == fixes.add_room(m, spec, key, x[0]["d"], x[0]["p"], want["n"]) for x in c)
    assert all(fixes.judge(m, spec, days, x[0], pool=pool)["state"] == "ok" for x in c)
    assert len({(x[0]["d"], x[0]["p"]) for x in c}) == len(c) and {(x[0]["d"], x[0]["p"]) for x in c} == {(s_["d"], s_["p"]) for s_ in fixes.add_slots(m, spec, days, key, want["n"], pool) if s_["state"] == "ok"}
    busy = lambda d: len({x["id"] for x in m["lessons"] if CLASSES[1] in x["classes"] and x["d"] == d})
    order = [(busy(x[0]["d"]), x[0]["d"], x[0]["p"]) for x in c]; assert order == sorted(order), order
    assert snapshot(m, pool) == before
    # a lesson of the key waiting in the pool counts as timetabled: nothing short of a whole class's plan is added then
    short_id = next(x for x in fixes.short(m, spec, pool) if x["key"] == KEY); assert short_id["have"] == 1   # the plain lesson: a periods target
    c, s = refit.direct(m, spec, days, target("periods", KEY), pool); assert s is None and c and all(x[0]["key"] == KEY and x[0]["n"] == short_id["n"] for x in c)
    pooled = [dict(x, id=99, d=0, p=5) for x in m["lessons"] if x["id"] == PLAIN_ID]   # a copy of it waiting in the pool: the key counts two periods
    left = next(x for x in fixes.short(m, spec, pooled) if x["key"] == KEY); assert left["have"] == 2 and left["want"] == short_id["want"]
    c2, s2 = refit.direct(m, spec, days, target("periods", KEY), pooled); assert s2 is None and c2 and all(x[0]["n"] == left["n"] for x in c2)
    assert all(fixes.judge(m, spec, days, x[0], pool=pooled)["state"] == "ok" for x in c2)

def test_a_surplus_lesson_is_deleted_from_the_fullest_day():
    nine = lambda i, d, p: dict(id=i, day=DAYS[d], p=p, n=1, level=LEVEL, classes=["9Z"], subject=SUBJ, teachers=[TEACHERS[0]])
    rows = [r for r in ROWS if r["id"] != ODD_ID] + [nine(4, 3, 0), nine(5, 0, 2), nine(6, 0, 3), nine(7, 4, 0)]
    m, spec, days, pool = world(rows); before = snapshot(m, pool)
    c, s = refit.direct(m, spec, days, target("extra", f"C:9Z:{SUBJ}"), pool)
    assert s is None and c == [[dict(kind="delete", id=i)] for i in (6, 5, 7, 4)], c   # day 0 has two periods (latest period first), then the latest day
    assert snapshot(m, pool) == before
    # more timetabled than planned: a periods target deletes too, with the group named for a lesson of several rows
    more = [r for r in ROWS] + [dict(id=8, day=DAYS[1], p=2, n=1, level=LEVEL, classes=[CLS], subject=EL, teachers=[TEACHERS[0]]), dict(id=9, day=DAYS[1], p=3, n=1, level=LEVEL, classes=[CLS], subject=EL, teachers=[TEACHERS[0]])]
    m3, spec3, days3, pool3 = world(more); step5_row(spec3)["periods"] = 1
    c, s = refit.direct(m3, spec3, days3, target("periods", KEY), pool3)
    ids = [x[0]["id"] for x in c]; assert s is None and ids == [9, 8, 1] and all(x[0]["kind"] == "delete" for x in c), c   # day 1 holds three of the class's periods: its lessons first, latest period first; then the plain lesson

def test_a_wrong_room_kind_is_a_room_fix():
    rows = [dict(r, room="1-01") if r["id"] == PLAIN_ID else r for r in ROWS]
    m, spec, days, pool = world(rows); before = snapshot(m, pool)
    step5_row(spec)["room_kind"] = "art room"   # the lesson is in a classroom
    art = [str(v["room"]) for v in spec["venues"] if v.get("kind") == "art room"]; assert art
    c, s = refit.direct(m, spec, days, target("venue", KEY), pool); assert s is None and c, (c, s)
    want = [[dict(kind="room", id=PLAIN_ID, group=ENTIRE, room=o["room"])] for o in fixes.room_options(m, spec, days, PLAIN_ID, ENTIRE, pool) if o["state"] == "ok"]
    assert c == want and {x[0]["room"] for x in c} <= set(art), (c, art)
    assert snapshot(m, pool) == before
    step5_row(spec)["room_kind"] = "classroom"   # nothing is in a wrong kind now: nothing to change
    assert refit.direct(m, spec, days, target("venue", KEY, "venue text"), pool) == ([], "venue text")
    assert refit.direct(m, spec, days, target("half", KEY, "half text"), pool) == ([], "half text")   # no combined venue in the sample school

def test_a_delete_names_its_group_only_when_the_lesson_has_several_rows():
    def two(i, d, p, groups):   # one lesson id with a row for each group, no block
        return [dict(id=i, day=DAYS[d], p=p, n=1, level=LEVEL, classes=["9Z"], subject=SUBJ, group=g, teachers=[TEACHERS[0]]) for g in groups]
    rows = [r for r in ROWS if r["id"] != ODD_ID] + two(30, 3, 0, [ENTIRE, "G7"]) + two(31, 3, 1, [ENTIRE])
    m, spec, days, pool = world(rows); before = snapshot(m, pool)
    assert len(fixes._rows(m["lessons"], 30)) == 2 and len(fixes._rows(m["lessons"], 31)) == 1
    c, s = refit.direct(m, spec, days, target("extra", f"C:9Z:{SUBJ}"), pool)
    assert s is None and c == [[dict(kind="delete", id=31)], [dict(kind="delete", id=30, group=ENTIRE)]], c   # a whole-class row of the key: ENTIRE; a lesson of one row: no group; latest period first
    c, s = refit.direct(m, spec, days, target("extra", "G:G7"), pool)
    assert s is None and c == [[dict(kind="delete", id=30, group="G7")]], c   # a group's row: its code
    assert snapshot(m, pool) == before

def test_a_delete_the_app_refuses_for_a_rule_is_left_out_but_one_that_misses_the_plan_is_kept():
    two = [dict(r, n=2) if r["id"] == PLAIN_ID else r for r in ROWS]   # the key has one two-period lesson
    m, spec, days, pool = world(two); step5_row(spec)["periods"] = 1
    j = fixes.can_delete(m, spec, days, PLAIN_ID, None, pool); assert j["state"] == "no" and j["plan"] is True, j   # deleting it leaves 0 periods, below the plan of 1
    c, s = refit.direct(m, spec, days, target("periods", KEY), pool)
    assert s is None and c == [[dict(kind="delete", id=PLAIN_ID)]], c   # kept: the search judges what it leaves
    more = [r for r in two] + [dict(id=8, day=DAYS[1], p=2, n=1, level=LEVEL, classes=[CLS], subject=EL, teachers=[TEACHERS[0]])]
    m, spec, days, pool = world(more); step5_row(spec)["periods"] = 1
    was = fixes.can_delete
    try:   # the app refuses deleting lesson 8 for a rule (a refusal that is not about the plan)
        fixes.can_delete = lambda m_, sp, dy, i, g=None, pl=(), ctx=None: dict(state="no", why="a made-up rule", plan=False) if i == 8 else was(m_, sp, dy, i, g, pl, ctx)
        c, s = refit.direct(m, spec, days, target("periods", KEY), pool)
        assert s is None and [x[0]["id"] for x in c] == [PLAIN_ID], c
    finally: fixes.can_delete = was
    c, s = refit.direct(m, spec, days, target("periods", KEY), pool); assert {x[0]["id"] for x in c} == {PLAIN_ID, 8}, c

def test_a_half_room_is_moved_to_a_room_that_seats_the_group():
    rows = [dict(r, room="1-01") if r["id"] == PLAIN_ID else r for r in ROWS]
    m, spec, days, pool = world(rows); k = fixes._key(KEY); e = verify.planned_rows(spec)[k]
    n = verify._group_size(spec, k, e); assert n and n > 1
    spec["venues"] = list(spec["venues"]) + [dict(room="Combo", kind="classroom", capacity=n)]
    ix = {r: dict(v) for r, v in m["room_ix"].items()}; ix["Combo"] = dict(room="Combo", kind="classroom", capacity=n)
    ix["1-01"]["capacity"] = n - 1; ix["1-02"]["capacity"] = n - 1   # two small halves of the combined venue
    ix["1-03"]["capacity"] = None   # a room with no known size is not offered either
    m2 = dict(m, room_parts={"Combo": ["1-01", "1-02"]}, room_ix=ix)
    assert verify._half_venue(m2, spec, k, e, verify.placed(m2)[k]), "the fixture makes the half warning"
    c, s = refit.direct(m2, spec, days, target("half", KEY, "half text"), pool); assert s is None, s
    rooms = [x[0]["room"] for x in c]
    ok = [o["room"] for o in fixes.room_options(m2, spec, days, PLAIN_ID, ENTIRE, pool) if o["state"] == "ok"]
    assert "Combo" in rooms and "1-02" not in rooms and "1-03" not in rooms and "1-01" not in rooms, rooms
    assert rooms == [r for r in ok if r not in ("1-02", "1-03")], (rooms, ok)   # room_options' order
    assert all(x == [dict(kind="room", id=PLAIN_ID, group=ENTIRE, room=x[0]["room"])] for x in c)
    for x in c:   # each one settles it
        L = [dict(r, room=x[0]["room"]) if r["id"] == PLAIN_ID else r for r in m2["lessons"]]
        assert verify._half_venue(m2, spec, k, e, verify.placed(dict(m2, lessons=L))[k]) is None, x

def test_a_classroom_in_its_other_week_is_not_a_wrong_room():
    rows = [dict(r, room="1-01") if r["id"] == PLAIN_ID else r for r in ROWS]
    m, spec, days, pool = world(rows); step5_row(spec)["room_kind"] = "art room"; step5_row(spec)["room_weeks"] = "Odd"
    d0 = list(m["days"]); d0[0] = "Even Monday"; mine = dict(m, days=d0)   # the lesson is on day 0, in an Even week: art is asked for only in Odd weeks
    assert refit.direct(mine, spec, d0, target("venue", KEY, "venue text"), pool) == ([], "venue text")
    d1 = list(m["days"]); d1[0] = "Odd Monday"; odd = dict(m, days=d1)   # in an Odd week it is wrong
    c, s = refit.direct(odd, spec, d1, target("venue", KEY), pool); assert s is None and c and all(x[0]["kind"] == "room" for x in c), (c, s)

def test_a_bands_periods_need_you():
    band = next(k for k, e in verify.planned_rows(SPEC_CHECKED).items() if k[0] == "G" and any(r.get("block") for r in e["rows"]))
    ks = f"G:{band[1]}"
    m, spec, days, pool = world(ROWS)
    assert not helper._of_key(m["lessons"], band)   # not on the timetable at all: missing
    for part in ("missing", "periods"): assert refit.direct(m, spec, days, target(part, ks), pool) == ([], refit.BAND), part
    # on the timetable (one period, taught by someone else): periods are still the band's; the teacher change is one teacher fix
    rows = ROWS + [dict(id=20, day=DAYS[0], p=3, n=1, level=LEVEL, block=f"{LEVEL} Band X", classes=[CLS], subject=EL, group=band[1], teachers=[TEACHERS[2]])]
    m, spec, days, pool = world(rows); before = snapshot(m, pool)
    planned = sorted(verify.planned_rows(spec)[band]["teachers"]); assert len(planned) == 1 and planned[0] != TEACHERS[2]
    assert refit.direct(m, spec, days, target("periods", ks), pool) == ([], refit.BAND)
    assert refit.direct(m, spec, days, target("teachers", ks), pool) == ([[dict(kind="teacher", key=ks, teachers=planned)]], None)
    # a group of the timetable that step 5 lacks, in a band: extra is the band's too
    assert "G1" not in {k[1] for k in verify.planned_rows(spec) if k[0] == "G"}
    assert refit.direct(m, spec, days, target("extra", "G:G1"), pool) == ([], refit.BAND)
    assert snapshot(m, pool) == before

def test_clash_rule_and_a_stale_key_give_nothing():
    m, spec, days, pool = world(ROWS); before = snapshot(m, pool)
    assert refit.direct(m, spec, days, dict(kind="clash", key="clash:x", text="t", w={}), pool) == ([], None)
    assert refit.direct(m, spec, days, dict(kind="rule", key="rule:1:x", text="t", w={}), pool) == ([], None)
    for kind in ("teachers", "missing", "periods", "extra", "venue", "half"):
        assert refit.direct(m, spec, days, target(kind, "C:Nowhere:Nothing", "gone"), pool) == ([], "gone"), kind
        assert refit.direct(m, spec, days, dict(kind=kind, key="dep:rubbish", text="gone", w={}), pool) == ([], "gone"), kind
    assert snapshot(m, pool) == before

# ----------------------------------------------------------------------------------------------- where a lesson may go
def moves(m, spec, days, i, moved=(), limit=refit.CAND_SLOTS, memo=None):
    return refit.day_moves(m, spec, days, i, fixes._ctx(m), {} if memo is None else memo, set(moved), limit)

def test_a_lesson_keeps_its_day():
    m, spec, days, pool = world(ROWS); before = snapshot(m, pool)
    got = moves(m, spec, days, PLAIN_ID, limit=50)
    assert got and all(not g["other"] and g["fix"]["kind"] in ("move", "swap") for g in got), got
    assert all(g["fix"]["d"] == 0 for g in got if g["fix"]["kind"] == "move")
    assert [g["dist"] for g in got] == sorted(g["dist"] for g in got) and all(g["dist"] == g["fix"]["p"] for g in got)
    assert not refit.barred(m, spec, days, PLAIN_ID, 0, pool)
    assert len(moves(m, spec, days, PLAIN_ID)) <= refit.CAND_SLOTS
    assert snapshot(m, pool) == before

def test_barred_day_opens_other_days():
    was = json.loads(json.dumps(store.setup_record()["spec"]))
    try:
        s = json.loads(json.dumps(was)); s["rules"] = list(s["rules"]) + [dict(MUST_RULE, to=99)]; put_setup(s)   # the teacher is not there that whole day
        m, spec, days, pool = world(ROWS); before = snapshot(m, pool)
        assert refit.barred(m, spec, days, PLAIN_ID, 0, pool) is True
        assert refit.barred(m, spec, days, PLAIN_ID, 1, pool) is False
        memo = {}; got = moves(m, spec, days, PLAIN_ID, memo=memo, limit=50)
        far = [g for g in got if g["other"]]
        assert far and got == far   # the day is barred: no same-day items, only other days
        assert all(g["fix"]["kind"] == "move" and g["fix"]["d"] != 0 and g["dist"] == 10 * g["fix"]["d"] + abs(g["fix"]["p"]) for g in far), far
        assert [g["fix"]["d"] for g in far] == sorted(g["fix"]["d"] for g in far)
        assert memo[("barred", PLAIN_ID, 0)] is True
        assert snapshot(m, pool) == before
        s["rules"][-1] = dict(MUST_RULE, to=0); put_setup(s)   # one period only: the day stays open
        m, spec, days, pool = world(ROWS)
        assert refit.barred(m, spec, days, PLAIN_ID, 0, pool) is False
        got = moves(m, spec, days, PLAIN_ID, limit=50); assert got and not any(g["other"] for g in got)
        s["rules"][-1] = dict(MUST_RULE, strength="Prefer", to=99); put_setup(s)   # a Prefer rule bars nothing
        m, spec, days, pool = world(ROWS); assert refit.barred(m, spec, days, PLAIN_ID, 0, pool) is False
    finally: put_setup(was)

def test_a_band_lesson_never_moves():
    m, spec, days, pool = world(ROWS)
    assert moves(m, spec, days, BAND_ID) == []
    assert moves(m, spec, days, PLAIN_ID, moved={PLAIN_ID}) == []
    assert moves(m, spec, days, 999) == []

def test_a_swap_never_crosses_days_and_never_touches_a_moved_lesson():
    cl = lambda i, d, p, **k: dict(id=i, day=DAYS[d], p=p, n=1, level=LEVEL, classes=[CLASSES[0]], subject=SUBJ2, teachers=[TEACHERS[2]], **k)
    rows = ROWS + [cl(30, 4, 2), cl(31, 4, 3), cl(32, 4, 4, block=f"{LEVEL} Band B", group="G9"), cl(33, 3, 2)]
    m, spec, days, pool = world(rows)
    got_all = moves(m, spec, days, 30, limit=100); swaps = lambda **k: [g["fix"] for g in moves(m, spec, days, 30, limit=100, **k) if g["fix"]["kind"] == "swap"]
    got = swaps(); assert dict(kind="swap", a=30, b=31) in got, [g["fix"] for g in got_all]
    assert all(f["b"] not in (BAND_ID, 32, 33) and f["a"] == 30 for f in got), got   # not a band, not on another day
    assert not any(f["b"] == 31 for f in swaps(moved={31}))
    assert not any(g["other"] for g in got_all)

def test_day_moves_does_not_mutate_the_model():
    m, spec, days, pool = world(ROWS); before = copy.deepcopy(m["lessons"]); sp = copy.deepcopy(spec)
    for i in (PLAIN_ID, OTHER_ID, BAND_ID): moves(m, spec, days, i); refit.barred(m, spec, days, i, 0, pool)
    assert m["lessons"] == before and spec == sp

# ----------------------------------------------------------------------------------------------- the search for one target
T0, T1, T2 = TEACHERS; T3 = SPEC["teachers"][3]["name"]; CLS_B = CLASSES[1]
OPEN = [p for p, code in enumerate(SPEC["day_structure"][LEVEL][DAYS[0]]) if code == "L"]; assert OPEN[:4] == [1, 2, 3, 5] and len(OPEN) == 9   # 0 is the assembly, 4 the recess
ADD_OK = " over the allowance."
def one(i, d, p, cls=CLS, subject=EL, teacher=T0, n=1, **k): return dict(id=i, day=DAYS[d], p=p, n=n, level=LEVEL, classes=[cls], subject=subject, teachers=[teacher], **k)
def band(i, d, p, cls=CLS, teacher=T2): return one(i, d, p, cls, teacher=teacher, block=f"{LEVEL} Band Q", group=f"Q{i}")
def full(*keep, d=0, cls=CLS, start=1000): return [band(start + 100 * d + p, d, p, cls, T3) for p in OPEN if p not in keep]   # a band in every lesson period of the class's day but these

def case(rows, change=None, rules=(), report=()):
    """a timetable of these rows against the setup with only these rules and this change made to it -> (m, spec, days, pool, its
    targets by key). The model is made as the draft's is, without the upload (test_a_teacher_change_that_just_fits has one of the draft)"""
    spec = copy.deepcopy(SPEC_CHECKED); spec["rules"] = [dict(r) for r in rules]
    if change: change(spec)
    L = [dict(id=r["id"], d=DAYS.index(r["day"]), p=r["p"], n=r["n"], level=r["level"], block=r.get("block", ""), classes=list(r["classes"]), subject=r["subject"], group=r.get("group", ENTIRE),
              teachers=list(r["teachers"]), room=r.get("room", ""), ext=False, rain="") for r in rows]
    m = export._model(spec, DAYS, L); m.update(checked_setup=spec, rule_report=list(report), choice_problems=[], pool=[])
    return m, spec, m["days"], m["pool"], {t["key"]: t for t in refit.targets(verify.warnings(m, spec)["warnings"])}

def gives(teacher, key=KEY): return lambda spec: step5_row(spec, key).update(teachers=[teacher])
def plans(periods, length=1, key=KEY): return lambda spec: step5_row(spec, key).update(periods=periods, length=length)
def hunt(m, spec, days, t, pool, moved=(), wait=60.0):
    stats = {}; got = refit.solve(m, spec, days, t, pool, set(moved), time.monotonic() + wait, stats)
    assert set(stats) == {"nodes", "reason", "late"} and isinstance(stats["nodes"], int), stats
    return got, stats

@contextlib.contextmanager
def limits(**k):
    was = {n: getattr(refit, n) for n in k}
    for n, v in k.items(): setattr(refit, n, v)
    try: yield
    finally:
        for n, v in was.items(): setattr(refit, n, v)

@contextlib.contextmanager
def watching():
    """every list solve judges, with its chain and how many timetables were kept for it"""
    out, was = [], helper.chain
    def chain(m, spec, days, fx, ctx=None, memo=None):
        kept = len(memo); c_ = was(m, spec, days, fx, ctx, memo); out.append((fx, c_, kept)); return c_
    helper.chain = chain
    try: yield out
    finally: helper.chain = was

def at_once(lessons):
    """the pairs of lessons of one key of step 5 that share a period"""
    cells = [(x["id"], set(helper._keys_of(x)), {(x["d"], q) for q in range(x["p"], x["p"] + x["n"])}) for x in lessons]
    return {(i, j) for i, ki, ci in cells for j, kj, cj in cells if i < j and ki & kj and ci & cj}

def solved(m, spec, days, t, pool, moved=()):
    """the answer, checked for everything every answer must be, and that nothing given to solve was changed"""
    before = (snapshot(m, pool), copy.deepcopy(spec), copy.deepcopy(t), sorted(moved)); rows = [id(x) for x in m["lessons"]]
    got, stats = hunt(m, spec, days, t, pool, moved); assert got is not None, stats
    assert before == (snapshot(m, pool), spec, t, sorted(moved)) and rows == [id(x) for x in m["lessons"]]
    assert set(got) == {"fixes", "moved", "other", "typed", "why"} and stats["reason"] == "" and stats["late"] is False, (got, stats)
    c = helper.chain(m, spec, days, got["fixes"])
    assert c["state"] == "ok" or (c["state"] == "prefer" and all(s.endswith(ADD_OK) for j in c["steps"] for s in j["prefer"])), c
    assert helper.settles(m, spec, days, t["w"], c["lessons"])
    subjects = lambda L: set(fixes.rule_subjects(m, spec, L)); assert subjects(c["lessons"]) <= subjects(m["lessons"])   # no rule, Must or Prefer, broken anew
    problems = lambda L: {p for p in export.check_model(dict(m, lessons=L))["problems"] if not p.endswith("planned.")}; assert problems(c["lessons"]) <= problems(m["lessons"])
    assert at_once(c["lessons"]) <= at_once(m["lessons"]), got   # no two lessons of a key in one period that were not
    at = lambda L: {x["id"]: (x["d"], x["p"]) for x in L}; a, b = at(m["lessons"]), at(c["lessons"]); went = {i for i in a if i in b and a[i] != b[i]}
    assert got["moved"] == went and not went & set(moved) and not any(fixes._block(fixes._rows(m["lessons"], i)) for i in went), (got, went)
    assert got["other"] == sum(a[i][0] != b[i][0] for i in went)
    made = [f for f in got["fixes"] if f["kind"] in ("move", "swap")]; assert len(made) <= refit.MAX_MOVES and got["fixes"][:len(made)] == made
    ids = [i for f in made for i in ((f["a"], f["b"]) if f["kind"] == "swap" else (f["id"],))]; assert len(ids) == len(set(ids))   # none moved twice
    assert len(got["why"]) == len(got["fixes"]) and all(isinstance(s, str) and s.endswith(".") for s in got["why"]), got["why"]
    assert hunt(m, spec, days, t, pool, moved) == (got, stats)   # the same again: the same answer, after the same steps
    return got, stats

TEACH = f"dep:{KEY}:teachers"
GONE = dict(fixes=[], moved=set(), other=0, typed=set(), why=[])   # an earlier target's fixes settled it: nothing more is moved for it
GIVE = dict(kind="teacher", key=KEY, teachers=[T1])
BUSY = [one(1, 0, 1), one(2, 0, 1, CLS_B, SUBJ2, T1)]   # 1A's English is to go to T1, who has 1B in that period

def test_a_teacher_change_that_just_fits():
    m, spec, days, pool, ts = case([one(1, 0, 1)], gives(T1))
    got, stats = solved(m, spec, days, ts[TEACH], pool)
    assert got == dict(fixes=[GIVE], moved=set(), other=0, typed=set(), why=[f"Step 5 now gives it to {T1}."]), got
    assert stats == dict(nodes=1, reason="", late=False)
    assert refit.solve(m, spec, days, ts[TEACH], pool, set(), time.monotonic() + 60) == got   # stats is not needed
    m, spec, days, pool = world(BUSY); gives(T1)(spec); spec["rules"] = []   # the same from an uploaded draft, with T1 busy then
    t = next(t for t in refit.targets(verify.warnings(m, spec)["warnings"]) if t["key"] == TEACH)
    got, _ = solved(m, spec, days, t, pool, moved={1}); assert got["fixes"] == [dict(kind="move", id=2, d=0, p=2), GIVE], got

def test_the_blocker_is_moved_on_its_own_day():
    m, spec, days, pool, ts = case(BUSY + full(1), gives(T1))   # 1A's day is full: its own lesson stays
    got, stats = solved(m, spec, days, ts[TEACH], pool)
    assert got == dict(fixes=[dict(kind="move", id=2, d=0, p=2), GIVE], moved={2}, other=0, typed=set(),
                       why=[f"{T1} teaches {SUBJ2} for {CLS_B} on {DAYS[0]} period 1.", f"Step 5 now gives it to {T1}."]), got   # the nearest period of the same day
    assert stats["nodes"] == 1 + len(moves(m, spec, days, 2)) == 9   # the change alone, then every place of lesson 2
    m, spec, days, pool, ts = case(BUSY + full(1) + [one(3, 0, 2, CLS_B, "Mathematics", T2)] + full(1, 2, cls=CLS_B, start=2000), gives(T1))   # 1B's day is full as well: its two lessons change places
    got, stats = solved(m, spec, days, ts[TEACH], pool)
    assert got["fixes"] == [dict(kind="swap", a=2, b=3), GIVE] and got["moved"] == {2, 3} and got["other"] == 0 and stats["nodes"] == 2, (got, stats)

def test_the_lesson_itself_is_moved():
    # the new teacher's lesson is a band's, or one an earlier target moved: the key's own lesson goes to another period of its day
    m, spec, days, pool, ts = case([one(1, 0, 1), band(3, 0, 1, CLS_B, T1)], gives(T1))
    got, stats = solved(m, spec, days, ts[TEACH], pool)
    assert got == dict(fixes=[dict(kind="move", id=1, d=0, p=2), GIVE], moved={1}, other=0, typed=set(), why=[f"{T1} teaches group Q3 on {DAYS[0]} period 1.", f"Step 5 now gives it to {T1}."]), got
    assert stats["nodes"] == 1 + len(moves(m, spec, days, 1)) == 9
    m, spec, days, pool, ts = case(BUSY, gives(T1)); got, _ = solved(m, spec, days, ts[TEACH], pool, moved={2}); assert got["fixes"] == [dict(kind="move", id=1, d=0, p=2), GIVE] and got["why"][0] == f"{T1} teaches {SUBJ2} for {CLS_B} on {DAYS[0]} period 1.", got
    # it ranks with the moves of the lesson in the way: the nearest wins, whichever it is
    m, spec, days, pool, ts = case(BUSY + [band(8, 0, 2, CLS_B, T3)], gives(T1)); t = ts[TEACH]   # 1B has a band in the next period, 1A is free
    got, stats = solved(m, spec, days, t, pool); assert got["fixes"] == [dict(kind="move", id=1, d=0, p=2), GIVE], got
    assert stats["nodes"] == 1 + len(moves(m, spec, days, 2)) + len(moves(m, spec, days, 1)) and moves(m, spec, days, 2)[0]["dist"] == 2, stats
    m, spec, days, pool, ts = case(BUSY + [band(8, 0, 2, CLS, T3)], gives(T1)); got, _ = solved(m, spec, days, ts[TEACH], pool); assert got["fixes"] == [dict(kind="move", id=2, d=0, p=2), GIVE], got
    m, spec, days, pool, ts = case(BUSY + [one(7, 0, 2, CLS, "Mathematics", T2)] + full(1, 2), gives(T1)); got, _ = solved(m, spec, days, ts[TEACH], pool, moved={2}); assert got["fixes"] == [dict(kind="swap", a=1, b=7), GIVE], got
    got, stats = hunt(m, spec, days, ts[TEACH], pool, moved={2, 7}); assert got is None and stats["nodes"] == 1, (got, stats)   # nor with one an earlier target moved
    m, spec, days, pool, ts = case([one(1, 0, 2), one(2, 0, 1, CLS_B, SUBJ2, T1, n=2)], gives(T1)); got, _ = solved(m, spec, days, ts[TEACH], pool)
    assert got["why"][0] == f"{T1} teaches {SUBJ2} for {CLS_B} on {DAYS[0]} period 1.", got   # the time is that of the lesson in the way
    # after the lessons in the way: with one lesson to try it is not reached
    m, spec, days, pool, ts = case(BUSY, gives(T1))
    with limits(CAND_LESSONS=1): got, stats = solved(m, spec, days, ts[TEACH], pool); assert got["moved"] == {2} and stats["nodes"] == 9, (got, stats)
    # one of two lessons is blocked by a band, the other by a lesson whose class has a full day round it: one move of each kind
    m, spec, days, pool, ts = case([one(1, 0, 1), band(3, 0, 1, CLS_B, T1), one(4, 1, 1), one(5, 1, 1, CLS_B, SUBJ2, T1)] + full(1, d=1), gives(T1))
    with limits(CAND_SLOTS=3): got, _ = solved(m, spec, days, ts[TEACH], pool); assert got["moved"] == {1, 5}, got

AWAY = lambda who, d=0, a=0, b=NPD - 1: dict(MUST_RULE, target=who, day=DAYS[d], **{"from": a, "to": b})
def test_a_lesson_the_new_teacher_may_not_take_then_is_moved():
    m, spec, days, pool, ts = case([one(1, 0, 1)], gives(T1), rules=[AWAY(T1, 0, 1, 1)])   # T1 is not there in that period: no lesson is in the way
    got, stats = solved(m, spec, days, ts[TEACH], pool)
    assert got["fixes"] == [dict(kind="move", id=1, d=0, p=2), GIVE] and got["moved"] == {1} and got["other"] == 0 and got["why"][1] == f"Step 5 now gives it to {T1}.", got
    assert got["why"][0].startswith(f"Rule Teacher · {T1} · Not available: ") and f"on {DAYS[0]} period 1" in got["why"][0], got
    got, stats = hunt(m, spec, days, ts[TEACH], pool, moved={1}); assert got is None and stats["nodes"] == 1 and stats["reason"].startswith(f"Rule Teacher · {T1} · "), (got, stats)
    m, spec, days, pool, ts = case([one(1, 0, 1)], gives(T1), rules=[AWAY(T1, 0, 1, 3)])   # it goes to a time allowed for the new teacher, and no other is looked at
    got, stats = solved(m, spec, days, ts[TEACH], pool); assert got["fixes"] == [dict(kind="move", id=1, d=0, p=5), GIVE] and stats["nodes"] == 1 + 6, (got, stats)
    m, spec, days, pool, ts = case(BUSY, gives(T1), rules=[AWAY(T1, 0, 1, 1)])   # T1 has a lesson then as well: moving that one would not help
    got, stats = solved(m, spec, days, ts[TEACH], pool); assert got["moved"] == {1} and stats["nodes"] == 9, (got, stats)
    m, spec, days, pool, ts = case([one(1, 0, 1), one(4, 1, 1)], gives(T1), rules=[AWAY(T1, 0, 1, 1), AWAY(T1, 1, 1, 1)])   # two such lessons, two moves
    with limits(CAND_SLOTS=2): got, stats = solved(m, spec, days, ts[TEACH], pool)
    assert got["moved"] == {1, 4} and stats["nodes"] == 1 + 2 * 2, (got, stats)
    m, spec, days, pool, ts = case([one(10 + d, d, 1) for d in range(4)], gives(T1), rules=[AWAY(T1, d, 1, 1) for d in range(4)]); got, stats = hunt(m, spec, days, ts[TEACH], pool); assert got is None and stats["nodes"] == 1, stats   # four are too many
    # a rule of the new teacher's day: T1 may teach two periods in a row, and has the next two
    row = dict(scope="Teacher", target=T1, rule="Max periods in a row", number=2, week="Both", day="All", strength="Must")
    m, spec, days, pool, ts = case([one(1, 0, 1), one(2, 0, 2, CLS_B, SUBJ2, T1), one(3, 0, 3, "1C", "Mathematics", T1)], gives(T1), rules=[row])
    got, _ = solved(m, spec, days, ts[TEACH], pool); assert got["fixes"] == [dict(kind="move", id=1, d=0, p=5), GIVE] and got["why"][0].startswith(f"Rule Teacher · {T1} · Max periods in a row: "), got
    # with a lesson on every day, it is the one of the day the rule is broken on that moves, wherever that is in the week
    two_more = lambda d: [one(50, d, 2, CLS_B, SUBJ2, T1), one(51, d, 3, "1C", "Mathematics", T1)]
    for n, bad in ((5, 4), (6, 4), (5, 0), (5, 2)):
        m, spec, days, pool, ts = case([one(1 + d, d % 5, 1 if d < 5 else 7) for d in range(n)] + two_more(bad), gives(T1), rules=[row])
        got, stats = solved(m, spec, days, ts[TEACH], pool); assert got["fixes"] == [dict(kind="move", id=1 + bad, d=bad, p=5), GIVE] and stats["nodes"] == 9, (n, bad, got, stats)   # and no other is looked at
        assert got["why"][0].startswith(f"Rule Teacher · {T1} · Max periods in a row: ") and DAYS[bad] in got["why"][0], got
    m, spec, days, pool, ts = case([one(1 + d, d, 1) for d in range(5)] + two_more(4) + [one(60, 2, 2, CLS_B, SUBJ2, T1), one(61, 2, 3, "1C", "Mathematics", T1)], gives(T1), rules=[row])   # on two days: both, each for its own day's sentence
    with limits(CAND_SLOTS=5): got, _ = solved(m, spec, days, ts[TEACH], pool)
    assert got["moved"] == {3, 5} and all(DAYS[f["d"]] in w for f, w in zip(got["fixes"][:2], got["why"])), got
    before = [one(70 + p, 1, p, "1C", "Science", T1) for p in (5, 6, 7)]; liked = dict(scope="Teacher", target=T1, rule="Max periods a day", number=1, week="Both", day="All", strength="Prefer")   # a day T1 has too many on already, and one where only a wish gives, are not days of it
    m5, spec5, days5, pool5, ts5 = case([one(1 + d, d, 1) for d in range(5)] + two_more(4) + before, gives(T1), rules=[row]); got, stats = solved(m5, spec5, days5, ts5[TEACH], pool5); assert got["moved"] == {5} and stats["nodes"] == 9, (got, stats)
    m5, spec5, *_ = case([one(1 + d, d, 1) for d in range(5)] + two_more(4) + [one(80, 0, 7, "1C", "Science", T1)], gives(T1), rules=[row, liked]); assert list(refit._day_rules(m5, spec5, GIVE)) == [4]
    must = fixes.judge(m, spec, days, GIVE)["must"]; ways = refit._in_the_way(m, spec, days, fixes.Busy(m), GIVE, must)
    assert len(must) == 2 and [i for i, _ in ways] == [3, 5] and DAYS[2] in ways[0][1] and DAYS[4] in ways[1][1], ways
    free = case([one(1 + d, d, 1) for d in range(5)], gives(T1)); assert refit._in_the_way(*free[:3], fixes.Busy(free[0]), GIVE, ["a made-up rule"]) == [(i, "a made-up rule") for i in (1, 2, 3, 4, 5)]   # a rule that names no day: all of them
    # a rule the lesson breaks with either teacher is not the new teacher's
    cls_rule = dict(scope="Class", target=CLS, rule="Not in periods", week="Both", day="All", strength="Must", **{"from": 1, "to": 3})
    m, spec, days, pool, ts = case([one(1, 0, 1)], gives(T1), rules=[cls_rule]); got, _ = solved(m, spec, days, ts[TEACH], pool); assert got["fixes"] == [GIVE], got
    m, spec, days, pool, ts = case(BUSY, gives(T1), rules=[cls_rule]); got, _ = solved(m, spec, days, ts[TEACH], pool, moved={1}); assert got["moved"] == {2}, got   # so the lesson in the way may still move for it
    got, _ = solved(m, spec, days, ts[TEACH], pool, moved={2}); assert got["fixes"] == [dict(kind="move", id=1, d=0, p=2), GIVE], got   # and it may go where it breaks that rule as it did

def test_the_lesson_keeps_its_day_unless_it_is_barred_for_the_new_teacher():
    m, spec, days, pool, ts = case([one(1, 0, 1), band(3, 0, 1, CLS_B, T1)], gives(T1), rules=[AWAY(T0)])   # the teacher it has is away that whole day, the one it will have is not
    assert refit.barred(m, spec, days, 1, 0, pool) is True
    got, stats = solved(m, spec, days, ts[TEACH], pool); assert got["fixes"] == [dict(kind="move", id=1, d=0, p=2), GIVE] and got["other"] == 0, got
    m, spec, days, pool, ts = case([one(1, 0, 1)], gives(T1), rules=[AWAY(T1)])   # the one it will have is away
    assert refit.barred(m, spec, days, 1, 0, pool) is False
    got, _ = solved(m, spec, days, ts[TEACH], pool); assert got["fixes"] == [dict(kind="move", id=1, d=1, p=1), GIVE] and got["other"] == 1, got
    m, spec, days, pool, ts = case([one(1, 0, 1)], gives(T1), rules=[AWAY(T1), AWAY(T1, 1)])   # and the next day too: the places of that day are none
    got, _ = solved(m, spec, days, ts[TEACH], pool); assert got["fixes"] == [dict(kind="move", id=1, d=2, p=1), GIVE] and got["other"] == 1, got
    m, spec, days, pool, ts = case([one(1, 0, 1), band(3, 0, 1, CLS_B, T1)] + full(1), gives(T1), rules=[AWAY(T0)])   # nor does a full day open another
    got, stats = hunt(m, spec, days, ts[TEACH], pool); assert got is None and stats["nodes"] == 1 and stats["reason"] == f"{T1} is teaching group Q3 then.", (got, stats)
    m, spec, days, pool, ts = case(BUSY + full(1), gives(T1), rules=[AWAY(T1)]); t = ts[TEACH]   # the lesson in the way is barred by its own teacher: it may go to another day
    got, _ = solved(m, spec, days, ts[f"rule:0:{CLS_B}|{SUBJ2}|0|1"], pool); assert got["moved"] == {2} and got["other"] == 1, got

def test_a_move_of_one_lesson_comes_before_a_swap():
    m, spec, days, pool, ts = case(BUSY + full(1) + [one(3, 0, 2, CLS_B, "Mathematics", T2)], gives(T1)); t = ts[TEACH]
    first, second = moves(m, spec, days, 2)[:2]; assert first["fix"] == dict(kind="swap", a=2, b=3) and second["fix"] == dict(kind="move", id=2, d=0, p=3) and first["dist"] < second["dist"]
    for g in (first, second):   # both settle it
        c_ = helper.chain(m, spec, days, [g["fix"], GIVE]); assert c_["state"] == "ok" and helper.settles(m, spec, days, t["w"], c_["lessons"])
    got, _ = solved(m, spec, days, t, pool); assert got["fixes"] == [dict(kind="move", id=2, d=0, p=3), GIVE] and got["moved"] == {2}, got   # one lesson moves, though a period further
    words = dict(scope="Class", target=CLS, rule="In words", text="made-up words", strength="Must")   # before the typed rules as well: 2's move has one to check again, the swap of 3 with 5 has none
    m, spec, days, pool, ts = case(TWICE + [one(5, 0, 2, CLS_B, "Mathematics", T2)] + full(1, 2, cls=CLS_B, start=2000), rules=[words], report=[dict(no=1, result="Met")]); t = clash_of(ts)
    assert [g["fix"] for g in moves(m, spec, days, 3)] == [dict(kind="swap", a=3, b=5)]
    got, _ = solved(m, spec, days, t, pool); assert got["fixes"] == [dict(kind="move", id=2, d=0, p=2)] and got["typed"] == {1}, got
    got, _ = solved(m, spec, days, t, pool, moved={2}); assert got["fixes"] == [dict(kind="swap", a=3, b=5)] and got["typed"] == set(), got

def test_two_lessons_in_the_way_are_two_moves():
    own = {1, 4, 6, 8}   # the key's own lessons are held where they are
    rows = BUSY + [one(4, 1, 1), one(5, 1, 1, CLS_B, SUBJ2, T1)]
    m, spec, days, pool, ts = case(rows, gives(T1))
    with limits(CAND_SLOTS=3):
        got, stats = solved(m, spec, days, ts[TEACH], pool, moved=own)
        assert got["fixes"] == [dict(kind="move", id=5, d=1, p=2), dict(kind="move", id=2, d=0, p=2), GIVE] and got["moved"] == {2, 5}, got   # both the nearest; the later move is put first
        assert got["why"] == [f"{T1} teaches {SUBJ2} for {CLS_B} on {DAYS[1]} period 1.", f"{T1} teaches {SUBJ2} for {CLS_B} on {DAYS[0]} period 1.", f"Step 5 now gives it to {T1}."], got["why"]   # each with its own time
        assert stats["nodes"] == 1 + 3 * 3, stats   # the change alone; one move of each (the same two the other way round are not looked at again; one move leaves T1 busy at the other time, which needs no looking at)
        three = rows + [one(6, 2, 1), one(7, 2, 1, CLS_B, SUBJ2, T1)]
        m, spec, days, pool, ts = case(three, gives(T1))
        got, stats = solved(m, spec, days, ts[TEACH], pool, moved=own); assert got["moved"] == {2, 5, 7} and len(got["fixes"]) == 4 and stats["nodes"] == 1 + 3 * 3 * 3, (got, stats)
        got, _ = solved(m, spec, days, ts[TEACH], pool); assert len(got["moved"]) == 3, got
    m, spec, days, pool, ts = case(three, gives(T1))   # with every place of every lesson tried, the third move is still reached before the limit of steps
    got, stats = hunt(m, spec, days, ts[TEACH], pool); assert got and len(got["moved"]) == 3 and stats["nodes"] <= refit.MAX_NODES, (got, stats)
    m, spec, days, pool, ts = case(three + [one(8, 3, 1), one(9, 3, 1, CLS_B, SUBJ2, T1)], gives(T1))   # a fourth is one too many, which needs no looking at either
    got, stats = hunt(m, spec, days, ts[TEACH], pool)
    assert got is None and stats == dict(nodes=1, reason=f"{T1} is teaching {SUBJ2} for {CLS_B} then.", late=False), stats
    two = [one(1, 0, 1), one(4, 0, 2), one(2, 0, 1, CLS_B, SUBJ2, T1, n=2)]   # one lesson of two periods in the way of two lessons: one move
    m, spec, days, pool, ts = case(two, gives(T1)); got, _ = solved(m, spec, days, ts[TEACH], pool); assert got["moved"] == {2} and len(got["fixes"]) == 2, got
    six = [one(10 * d + p, d, p) for d in range(3) for p in (1, 2)] + [one(50 + d, d, 1, CLS_B, SUBJ2, T1, n=2) for d in range(3)]   # six lessons, three of two periods in the way: three moves
    with limits(CAND_SLOTS=2):   # the nearest place of each still meets a lesson of the key, the next does not
        m, spec, days, pool, ts = case(six, gives(T1)); got, stats = solved(m, spec, days, ts[TEACH], pool, moved={x["id"] for x in m["lessons"] if x["classes"] == [CLS]})
        assert got["moved"] == {50, 51, 52} and stats["nodes"] == 1 + 2 * 2 * 2, (got, stats)

def test_the_lessons_in_the_way_are_read_after_the_earlier_moves():
    m, spec, days, pool, ts = case(BUSY + [one(5, 0, 1, "1C", "Mathematics", T1)], gives(T1))   # T1 is in two places then: the second is in the way once the first is gone
    with limits(CAND_SLOTS=3): got, _ = solved(m, spec, days, ts[TEACH], pool, moved={1})
    assert got["moved"] == {2, 5} and got["why"] == [f"{T1} teaches Mathematics for 1C on {DAYS[0]} period 1.", f"{T1} teaches {SUBJ2} for {CLS_B} on {DAYS[0]} period 1.", f"Step 5 now gives it to {T1}."], got
    # only a teacher who was not there is in the way of anything: T2 is in two places already and stays so
    rows = [dict(one(1, 0, 1), teachers=[T2, T0]), one(2, 0, 1, CLS_B, SUBJ2, T1), one(6, 0, 1, "1C", "Mathematics", T2)]
    m, spec, days, pool, ts = case(rows, lambda s: step5_row(s).update(teachers=[T2, T1]))
    got, _ = solved(m, spec, days, ts[TEACH], pool, moved={1}); assert got["fixes"] == [dict(kind="move", id=2, d=0, p=2), dict(kind="teacher", key=KEY, teachers=[T2, T1])], got

def test_no_list_moves_a_lesson_twice():
    rows = [one(1, 0, 1), one(4, 0, 2), one(2, 0, 1, CLS_B, SUBJ2, T1), one(5, 0, 2, CLS_B, "Mathematics", T1), one(6, 0, 3, CLS_B, "Science", T2)]   # 2 and 5 can change places, and with 6
    m, spec, days, pool, ts = case(rows, gives(T1))
    with watching() as judged, limits(MAX_KEPT=3): got, stats = hunt(m, spec, days, ts[TEACH], pool)
    ids = lambda fx: [i for f in fx for i in ((f["a"], f["b"]) if f["kind"] == "swap" else (f["id"],) if f["kind"] == "move" else ())]
    assert got and stats["nodes"] == len(judged) and any(f["kind"] == "swap" for fx, *_ in judged for f in fx)
    assert all(len(ids(fx)) == len(set(ids(fx))) and fx[-1] == GIVE for fx, *_ in judged), [fx for fx, *_ in judged]
    assert len({json.dumps(sorted(map(repr, fx))) for fx, *_ in judged}) == len(judged)   # none twice, in any order
    assert max(kept for *_, kept in judged) <= 3 and hunt(m, spec, days, ts[TEACH], pool) == (got, stats)   # the timetables kept are few, and make no difference

TWICE = [one(2, 0, 1, CLS, EL, T1), one(3, 0, 1, CLS_B, EL, T1)]   # T1 has 1A and 1B in one period
def clash_of(ts, start="clash:Teacher double-booked: "): return next(t for k, t in ts.items() if k.startswith(start))

def test_the_first_depth_wins():
    m, spec, days, pool, ts = case(TWICE); t = clash_of(ts); assert t["kind"] == "clash"
    both = helper.chain(m, spec, days, [dict(kind="move", id=2, d=0, p=2), dict(kind="move", id=3, d=0, p=3)])
    assert both["state"] == "ok" and helper.settles(m, spec, days, t["w"], both["lessons"])   # two moves settle it as well
    got, stats = solved(m, spec, days, t, pool)
    assert got == dict(fixes=[dict(kind="move", id=2, d=0, p=2)], moved={2}, other=0, typed=set(), why=["The clash needs it."]), got   # one move, the nearest period, then the words
    assert stats["nodes"] == 1 + len(moves(m, spec, days, 2)) + len(moves(m, spec, days, 3)), stats   # the empty list and all lists of one move; none of two
    # fewer typed rules touched comes before the distance and the words
    words = lambda cls: dict(scope="Class", target=cls, rule="In words", text="made-up words", strength="Must")
    line = lambda n, result="Met": dict(no=n, result=result)
    m, spec, days, pool, ts = case(TWICE, rules=[words(CLS)], report=[line(1)])
    got, _ = solved(m, spec, days, clash_of(ts), pool); assert got["fixes"] == [dict(kind="move", id=3, d=0, p=2)] and got["typed"] == set(), got
    m, spec, days, pool, ts = case(TWICE, rules=[words(CLS), words(CLS_B), words(CLS_B)], report=[line(1), line(2, "Partly"), line(3)])
    got, _ = solved(m, spec, days, clash_of(ts), pool); assert got["fixes"] == [dict(kind="move", id=2, d=0, p=2)] and got["typed"] == {1}, got   # one rule rather than two
    m, spec, days, pool, ts = case(TWICE, rules=[words(CLS), words(CLS_B)], report=[line(1), line(2, "Not met")])
    got, _ = solved(m, spec, days, clash_of(ts), pool); assert got["fixes"] == [dict(kind="move", id=3, d=0, p=2)] and got["typed"] == set(), got   # a rule not reported met has nothing to check again
    # with the nearest periods taken, the next nearest
    near = [one(10 + p, 0, p, "1C", "Science", T1) for p in (2, 3)]
    m, spec, days, pool, ts = case(TWICE + near); t = clash_of(ts)
    got, _ = solved(m, spec, days, t, pool); assert got["fixes"] == [dict(kind="move", id=2, d=0, p=5)], got

def test_fewer_moves_to_another_day_come_first():
    barred = dict(AWAY(CLS), scope="Class"); words = dict(scope="Class", target=CLS_B, rule="In words", text="made-up words", strength="Must")   # 1A's lesson must leave Monday; 1B's stays, with a typed rule to check again
    m, spec, days, pool, ts = case(TWICE, rules=[barred, words], report=[dict(no=1, result="Met")]); t = clash_of(ts)
    assert moves(m, spec, days, 2)[0] == dict(fix=dict(kind="move", id=2, d=1, p=1), other=True, dist=10)
    far = helper.chain(m, spec, days, [dict(kind="move", id=2, d=1, p=1)]); assert far["state"] == "ok" and helper.settles(m, spec, days, t["w"], far["lessons"])   # one lesson as well, with no typed rule
    got, _ = solved(m, spec, days, t, pool); assert got["fixes"] == [dict(kind="move", id=3, d=0, p=2)] and got["other"] == 0 and got["typed"] == {1}, got
    got, _ = solved(m, spec, days, t, pool, moved={3}); assert got["fixes"] == [dict(kind="move", id=2, d=1, p=1)] and got["other"] == 1, got

def test_fewer_allowance_lines_come_first():
    m, spec, days, pool, ts = case(TWICE); t = clash_of(ts); was = helper.chain
    def chain(*a, **k):   # as if the moves of lesson 2 went over an allowance (nothing in one search can differ in it but by the judge's word)
        c_ = was(*a, **k)
        if c_["state"] == "ok" and any(f["id"] == 2 for f in a[3]): c_ = dict(c_, state="prefer", steps=[dict(j, state="prefer", prefer=[f"{T1} would have 9 periods, 1 over the allowance."]) for j in c_["steps"]])
        return c_
    try: helper.chain = chain; got, _ = hunt(m, spec, days, t, pool)
    finally: helper.chain = was
    assert got["fixes"] == [dict(kind="move", id=3, d=0, p=2)] and hunt(m, spec, days, t, pool)[0]["fixes"] == [dict(kind="move", id=2, d=0, p=2)], got

def test_a_search_may_be_held_to_fewer_moves():
    least = lambda m, spec, days, t, pool, most: refit.solve(m, spec, days, t, pool, set(), time.monotonic() + 60, None, most)
    m, spec, days, pool, ts = case(BUSY, gives(T1)); stats = {}
    assert refit.solve(m, spec, days, ts[TEACH], pool, set(), time.monotonic() + 60, stats, max_moves=0) is None and stats == dict(nodes=1, reason=f"{T1} is teaching {SUBJ2} for {CLS_B} then.", late=False), stats
    was = refit._blocked
    try: refit._blocked = lambda *a: 1 / 0; assert least(m, spec, days, ts[TEACH], pool, 0) is None   # with no moves to come nothing is worked out for them
    finally: refit._blocked = was
    assert least(m, spec, days, ts[TEACH], pool, 1)["moved"] == {1} == least(m, spec, days, ts[TEACH], pool, 3)["moved"]
    m, spec, days, pool, ts = case([one(1, 0, 1)], gives(T1)); assert least(m, spec, days, ts[TEACH], pool, 0)["fixes"] == [GIVE]   # direct answers are made all the same
    m, spec, days, pool, ts = case([one(1, 0, 1), one(2, 1, 1, CLS, "Other")], plans(2)); assert [f["kind"] for f in least(m, spec, days, ts[f"dep:{KEY}:periods"], pool, 0)["fixes"]] == ["add"]
    m, spec, days, pool, ts = case(TWICE); assert least(m, spec, days, clash_of(ts), pool, 0) is None
    m, spec, days, pool, ts = case(BUSY + [one(4, 1, 1), one(5, 1, 1, CLS_B, SUBJ2, T1)], gives(T1)); assert least(m, spec, days, ts[TEACH], pool, 1) is None and len(least(m, spec, days, ts[TEACH], pool, 2)["moved"]) == 2

def test_no_list_of_more_moves_is_looked_at_once_one_is_found():
    row = dict(scope="Teacher", target=T1, rule="Max periods in a row", number=2, week="Both", day="All", strength="Must")
    m, spec, days, pool, ts = case([one(i, 0, p, CLASSES[i % 2], EL, T1) for i, p in enumerate((1, 2, 3, 5, 6), 1)], rules=[row]); t = clash_of(ts, "rule:")   # three in a row, then two
    first = [g for i in (1, 2, 3, 4) for g in moves(m, spec, days, i)]; assert helper.involved(m, t["w"]) == [1, 2, 3, 4, 5]   # at most four lessons are tried
    how = [helper.settles(m, spec, days, t["w"], helper.chain(m, spec, days, [g["fix"]])["lessons"]) for g in first]; assert True in how and False in how   # some do it and some make another row of three
    got, stats = solved(m, spec, days, t, pool); assert stats["nodes"] == 1 + len(first) and len(got["fixes"]) == 1 and got["why"] == ["The rule needs it."], (got, stats)
    best = min(g["dist"] for g, ok in zip(first, how) if ok); assert got["fixes"][0] in [g["fix"] for g, ok in zip(first, how) if ok and g["dist"] == best], got
    thrice = TWICE + [one(4, 0, 1, "1C", EL, T1)]   # three at once: two must move
    m, spec, days, pool, ts = case(thrice)
    with limits(CAND_SLOTS=2): got, _ = solved(m, spec, days, clash_of(ts), pool); assert len(got["moved"]) == 2 and got["why"] == ["The clash needs it."] * 2, got
    with limits(CAND_LESSONS=1):   # those that cannot be moved do not take the place of one that can
        m, spec, days, pool, ts = case(TWICE); got, _ = solved(m, spec, days, clash_of(ts), pool, moved={2}); assert got["moved"] == {3}, got
        m, spec, days, pool, ts = case([band(1, 0, 1, CLS, T1), TWICE[1]]); got, _ = solved(m, spec, days, clash_of(ts), pool); assert got["moved"] == {3}, got
        m, spec, days, pool, ts = case(thrice); got, _ = solved(m, spec, days, clash_of(ts), pool); assert len(got["moved"]) == 2, got
        runs = [one(i, 0, p, CLASSES[i % 2], EL, T1) for i, p in enumerate((2, 6, 1, 3, 5, 7), 1)]   # two rows of three: the first lesson, moved by the list already, is one the rule is about still
        m, spec, days, pool, ts = case(runs, rules=[row]); got, _ = solved(m, spec, days, clash_of(ts, "rule:"), pool); assert got["moved"] == {1, 2}, got

def test_a_band_is_never_moved():
    m, spec, days, pool, ts = case([one(1, 0, 1), band(3, 0, 1, CLS_B, T1)] + full(1), gives(T1)); before = snapshot(m, pool)   # nor can 1A's own lesson move
    got, stats = hunt(m, spec, days, ts[TEACH], pool)
    assert got is None and stats == dict(nodes=1, reason=f"{T1} is teaching group Q3 then.", late=False), (got, stats)
    assert snapshot(m, pool) == before
    more = [one(1, 0, 1), band(3, 0, 1, CLS_B, T1), one(4, 1, 1), one(5, 1, 1, CLS_B, SUBJ2, T1)]   # a lesson that stays blocked whatever moves: nothing is tried for the other one
    m, spec, days, pool, ts = case(more, gives(T1)); was = refit.day_moves
    try:
        refit.day_moves = lambda *a: 1 / 0
        got, stats = hunt(m, spec, days, ts[TEACH], pool, moved={1}); assert got is None and stats == dict(nodes=1, reason=f"{T1} is teaching group Q3 then.", late=False), (got, stats)
    finally: refit.day_moves = was
    # a band's own teacher change is made; with the new teacher busy, the band is not moved for it
    b = next(k for k, e in verify.planned_rows(SPEC_CHECKED).items() if k[0] == "G" and any(r.get("block") for r in e["rows"]) and len(e["teachers"]) == 1)
    planned = sorted(verify.planned_rows(SPEC_CHECKED)[b]["teachers"]); row = verify.planned_rows(SPEC_CHECKED)[b]["rows"][0]
    had = next(x for x in (T0, T1, T2) if x not in planned)
    rows = [one(20, 0, 2, row["classes"][0], row["subject"], had, block=row["block"], group=b[1])]
    m, spec, days, pool, ts = case(rows); t = ts[f"dep:G:{b[1]}:teachers"]
    got, _ = solved(m, spec, days, t, pool); assert got["fixes"] == [dict(kind="teacher", key=f"G:{b[1]}", teachers=planned)] and got["moved"] == set(), got
    m, spec, days, pool, ts = case(rows + [band(21, 0, 2, "2A", planned[0])]); got, stats = hunt(m, spec, days, ts[t["key"]], pool)
    assert got is None and stats == dict(nodes=1, reason=f"{planned[0]} is teaching group Q21 then.", late=False), (got, stats)

def test_the_reason_is_about_the_timetable_as_it_is():
    busy = f"{T1} is teaching {SUBJ2} for {CLS_B} then."
    rows = [one(1, 0, 1), one(4, 0, 2), one(2, 0, 1, CLS_B, SUBJ2, T1), one(5, 0, 2, "1C", "Mathematics", T1)]   # both of T1's lessons are in the way, and the nearest place of both is period 3
    m, spec, days, pool, ts = case(rows, gives(T1)); t = ts[TEACH]
    with limits(CAND_SLOTS=1), watching() as judged:
        got, stats = hunt(m, spec, days, t, pool, moved={1, 4}); assert got is None and stats == dict(nodes=1 + 1, reason=busy, late=False), stats
    assert judged[-1][1]["why"] != busy   # the two moves meet in one place
    # the period tried for the lesson itself is one where T1 has a band: that is not why it stays
    m, spec, days, pool, ts = case(BUSY + [band(5, 0, 2, "1C", T1)] + full(1, 2), gives(T1))
    with watching() as judged: got, stats = hunt(m, spec, days, ts[TEACH], pool, moved={2})
    assert got is None and stats["reason"] == busy and judged[-1][1]["why"] == f"{T1} is teaching group Q5 then.", (got, stats)
    # with the lesson in the way moved, a wish about the other lesson refuses it
    wish = dict(AWAY(T1, 1, 1, 1), strength="Prefer")
    m, spec, days, pool, ts = case(BUSY + [one(4, 1, 1)], gives(T1), rules=[wish])
    with watching() as judged: got, stats = hunt(m, spec, days, ts[TEACH], pool, moved={1, 4})
    assert got is None and stats["reason"] == busy and judged[-1][1]["why"].endswith("(Prefer)"), (got, stats)
    # a lesson put in by the list itself is never the reason, nor is a place tried for a missing one
    key = f"C:{CLS_B}:{EL}"; other = [x for d in range(5) for x in full(*([1] if d == 0 else []), d=d, cls=CLS_B)]
    m, spec, days, pool, ts = case(other, plans(2, 1, key))   # one free period in the week, two lessons missing
    with watching() as judged: got, stats = hunt(m, spec, days, ts[f"dep:{key}:missing"], pool)
    assert got is None and stats["reason"] == refit.NO_FIT and [len(fx) for fx, *_ in judged][0] == 1, (got, stats)
    m, spec, days, pool, ts = case([x for x in other if x["id"] != 1002], lambda s: (plans(1, 1, key)(s), gives(T3, key)(s))); t = ts[f"dep:{key}:missing"]   # two free periods, and the teacher has bands then
    m = dict(m, lessons=m["lessons"] + [dict(next(x for x in m["lessons"] if x["id"] == 1003), id=1000 + p, p=p, classes=["1C"], group=f"R{p}") for p in (1, 2)])
    got, stats = hunt(m, spec, days, t, pool); assert got is None and stats["reason"] == refit.NO_FIT, (got, stats)
    # a delete the plan refuses is refused on the timetable as it is
    m, spec, days, pool, ts = case([one(1, 0, 1, n=2)], plans(1)); got, stats = hunt(m, spec, days, ts[f"dep:{KEY}:periods"], pool)
    assert got is None and stats["reason"] == f"That would leave {EL} for {CLS} with 0 periods; step 3 plans 1.", (got, stats)
    m, spec, days, pool, ts = case([one(1, 0, 1, n=3), one(2, 1, 1, n=2)], plans(4)); got, stats = hunt(m, spec, days, ts[f"dep:{KEY}:periods"], pool)
    assert got is None and stats["nodes"] == 2 and stats["reason"] == f"That would leave {EL} for {CLS} with 2 periods; step 3 plans 4.", (got, stats)   # the best candidate's
    m, spec, days, pool, ts = case([one(1, 0, 1, n=2), one(2, 1, 1, n=2), one(3, 2, 1)], plans(1)); t = ts[f"dep:{KEY}:periods"]   # four periods over in lessons of 2, 2 and 1: the first two fit
    got, _ = solved(m, spec, days, t, pool); assert {f["id"] for f in got["fixes"]} == {1, 2}, got
    m, spec, days, pool, ts = case([one(1, 0, 1, n=2), one(3, 2, 1)], plans(2)); t = ts[f"dep:{KEY}:periods"]; got, _ = solved(m, spec, days, t, pool); assert got["fixes"] == [dict(kind="delete", id=3)], got
    m, spec, days, pool, ts = case([one(1, 0, 1, n=3), one(3, 2, 1, n=2), one(4, 3, 1, n=2)], plans(4)); t = ts[f"dep:{KEY}:periods"]   # three periods over: the lesson of three goes
    got, _ = solved(m, spec, days, t, pool); assert got["fixes"] == [dict(kind="delete", id=1)], got
    m, spec, days, pool, ts = case([one(1, 0, 1, n=2), one(3, 2, 1, n=2), one(4, 3, 1, n=5)], plans(6)); t = ts[f"dep:{KEY}:periods"]   # three over in lessons of 2, 2 and 5: one of two fits by itself, so that five is too many is not why
    got, stats = hunt(m, spec, days, t, pool); assert got is None and stats["reason"] == refit.NO_FIT, (got, stats)

def test_a_lesson_moved_by_an_earlier_target_is_left_alone():
    m, spec, days, pool, ts = case(BUSY, gives(T1))
    got, stats = hunt(m, spec, days, ts[TEACH], pool, moved={1, 2})   # neither the lesson in the way nor the lesson itself
    assert got is None and stats == dict(nodes=1, reason=f"{T1} is teaching {SUBJ2} for {CLS_B} then.", late=False), stats
    got, _ = solved(m, spec, days, ts[TEACH], pool, moved={1}); assert got["moved"] == {2}, got
    got, _ = solved(m, spec, days, ts[TEACH], pool, moved={2}); assert got["moved"] == {1}, got
    rows = BUSY + full(1) + [one(3, 0, 2, CLS_B, "Mathematics", T2)] + full(1, 2, cls=CLS_B, start=2000)   # nor does one change places with it
    m, spec, days, pool, ts = case(rows, gives(T1)); got, stats = hunt(m, spec, days, ts[TEACH], pool, moved={3}); assert got is None and stats["nodes"] == 1, (got, stats)
    extra = [one(1, 0, 1, CLS, "Other", T0), one(2, 1, 1, CLS, "Other", T0)]   # nor is one deleted: the list would undo itself
    m, spec, days, pool, ts = case(extra); t = ts[f"dep:C:{CLS}:Other:extra"]
    got, stats = hunt(m, spec, days, t, pool, moved={2}); assert got is None and stats["reason"] == refit.NO_FIT, (got, stats)
    got, _ = solved(m, spec, days, t, pool); assert got["fixes"] == [dict(kind="delete", id=2), dict(kind="delete", id=1)], got

def test_a_teacher_away_all_day_moves_to_another_day():
    away = dict(MUST_RULE, target=T0, **{"from": 0, "to": NPD - 1})
    m, spec, days, pool, ts = case([one(1, 0, 1)], rules=[away]); t = clash_of(ts, "rule:"); assert t["kind"] == "rule"
    got, _ = solved(m, spec, days, t, pool)
    assert got == dict(fixes=[dict(kind="move", id=1, d=1, p=1)], moved={1}, other=1, typed=set(), why=["The rule needs it."]), got   # the nearest day, then the nearest period

def test_a_full_day_never_moves_to_another_day():
    then = dict(MUST_RULE, target=T0, **{"from": 1, "to": 1})   # away in that one period: the day is not barred
    full = [one(1, 0, 1)] + [band(30 + p, 0, p) for p in OPEN if p != 1]   # every other period of the day is a band's
    m, spec, days, pool, ts = case(full, rules=[then]); t = clash_of(ts, "rule:")
    assert any(s["state"] == "ok" and s["d"] != 0 for s in fixes.slots(m, spec, days, 1, pool, extras=False))   # another day would do
    got, stats = hunt(m, spec, days, t, pool); assert got is None and stats == dict(nodes=1, reason=refit.NO_FIT, late=False), (got, stats)
    m, spec, days, pool, ts = case(full[:-1], rules=[then])   # one period is free: the lesson goes there
    got, _ = solved(m, spec, days, clash_of(ts, "rule:"), pool); assert got["fixes"] == [dict(kind="move", id=1, d=0, p=OPEN[-1])] and got["other"] == 0, got

def test_adding_a_period_takes_a_free_slot():
    key = f"C:{CLS_B}:{EL}"; t_of = lambda ts, part="missing": ts[f"dep:{key}:{part}"]
    m, spec, days, pool, ts = case([one(2, 0, 1, CLS_B, "Other", T2)], plans(1, 1, key)); t = t_of(ts)
    got, stats = solved(m, spec, days, t, pool)
    cands = refit.direct(m, spec, days, t, pool)[0]; assert [got["fixes"]] == cands[:1] and len(cands) > 10, got   # the best of direct's own order (the class's emptiest day), not of the words
    assert got["fixes"][0]["d"] == 1 and got["moved"] == set() and got["other"] == 0 and got["why"] == ["It was not on the timetable."], got
    assert stats["nodes"] == len(cands)
    m, spec, days, pool, ts = case([one(1, 0, 2, CLS_B, EL, T0)], lambda s: (plans(3, 1, key)(s), gives(T0, key)(s)))   # two periods short: two adds, on two days
    got, _ = solved(m, spec, days, t_of(ts, "periods"), pool)
    assert [(f["kind"], f["d"]) for f in got["fixes"]] == [("add", 1), ("add", 2)] and got["why"] == ["Step 3 plans 3 periods of it."] * 2, got
    m, spec, days, pool, ts = case([one(2, 0, 1, CLS_B, "Other", T2)], plans(3, 2, key))   # three periods in lessons of two: one of two, then one of one, on another day
    got, stats = solved(m, spec, days, t_of(ts), pool); assert [(f["kind"], f["n"], f["d"]) for f in got["fixes"]] == [("add", 2, 1), ("add", 1, 2)] and got["why"] == ["It was not on the timetable."] * 2, got
    m, spec, days, pool, ts = case([one(1, 0, 1, CLS_B, EL, T0, n=2)], lambda s: (plans(5, 2, key)(s), gives(T0, key)(s)))   # the same for a lesson that is short of periods
    got, _ = solved(m, spec, days, t_of(ts, "periods"), pool); assert [f["n"] for f in got["fixes"]] == [2, 1] and got["why"] == ["Step 3 plans 5 periods of it."] * 2, got
    m, spec, days, pool, ts = case([], plans(9, 1, key)); got, stats = hunt(m, spec, days, t_of(ts), pool); assert got is None and stats["reason"] == refit.TOO_MANY == "More than 8 changes: change it on the board.", (got, stats)
    m, spec, days, pool, ts = case([], plans(8, 1, key)); got, _ = solved(m, spec, days, t_of(ts), pool); assert len(got["fixes"]) == 8, got
    eight = [x for d in range(5) for x in full(*(OPEN[:8] if d == 0 else []), d=d, cls=CLS_B)]
    m, spec, days, pool, ts = case(eight, plans(9, 1, key)); got, stats = hunt(m, spec, days, t_of(ts), pool); assert got is None and stats["reason"] == refit.NO_FIT, (got, stats)   # a ninth has no place at all: that is the reason
    crowd = [one(100 * d + p, d, p, CLS_B, "Other", T2) for d in range(1, 5) for p in OPEN[:3]]   # Monday is far the emptiest: the second goes to another day all the same
    m, spec, days, pool, ts = case(crowd, plans(2, 1, key)); got, _ = solved(m, spec, days, t_of(ts), pool); assert [f["d"] for f in got["fixes"]] == [0, 1], got
    with limits(MAX_GROWN=0): got, stats = hunt(m, spec, days, t_of(ts), pool); assert got is None and stats["reason"] == refit.NO_FIT, (got, stats)
    m, spec, days, pool, ts = case([one(2, 0, 1, CLS_B, "Other", T2)], plans(3, 2, key))
    stats = {}; before = snapshot(m, pool)
    assert refit.solve(m, spec, days, t_of(ts), pool, set(), time.monotonic() - 1, stats) is None and stats == dict(nodes=0, reason=refit.LATE, late=True), stats
    assert snapshot(m, pool) == before

def test_a_missing_lesson_takes_the_place_of_one_that_can_move():
    key = f"C:{CLS_B}:{EL}"; part = f"dep:{key}:missing"; week = [x for d in range(5) for x in full(*([1, 2] if d == 0 else []), d=d, cls=CLS_B)]   # 1B's week is full of bands but for two periods of Monday
    home = case([])[0]["class_ix"][CLS_B]["home"]; assert home
    rows = week + [one(2, 0, 1, CLS_B, "Mathematics", T2, room=home), band(9, 0, 2, CLS, T0)]   # in the first 1B has Maths in its home room; in the second the missing lesson's teacher has a band
    need = lambda s: (plans(1, 1, key)(s), gives(T0, key)(s))
    m, spec, days, pool, ts = case(rows, need); t = ts[part]
    cands, says = refit.direct(m, spec, days, t, pool); add = dict(kind="add", key=key, d=0, p=1, n=1, room=home); assert (cands, says) == ([[add]], None), (cands, says)   # only the place of a lesson that may move, in the room it leaves
    got, stats = solved(m, spec, days, t, pool)
    assert got == dict(fixes=[dict(kind="move", id=2, d=0, p=2), add], moved={2}, other=0, typed=set(), why=[f"{CLS_B} has Mathematics for {CLS_B} on {DAYS[0]} period 1.", "It was not on the timetable."]) and stats["nodes"] == 2, (got, stats)
    got, stats = hunt(m, spec, days, t, pool, moved={2}); assert got is None and stats == dict(nodes=0, reason=refit.NO_FIT, late=False), stats
    m, spec, days, pool, ts = case(rows, need, rules=[AWAY(T0, 0, 1, 1)]); assert refit.direct(m, spec, days, ts[part], pool) == ([], None)   # not a place a Must rule shuts
    m, spec, days, pool, ts = case(rows + [band(8, 0, 1, CLS, T0)], need); assert refit.direct(m, spec, days, ts[part], pool) == ([], None)   # nor one where a band is in the way as well
    m, spec, days, pool, ts = case(rows + [one(8, 1, 1, "1C", "Mathematics", T0)], need); assert refit.direct(m, spec, days, ts[part], pool) == ([[add]], None)   # whichever of the two is found first
    most = dict(scope="Teacher", target=T0, rule="Max periods a day", number=1, week="Both", day="All", strength="Must")   # nor one refused for a rule of the teacher's day, with no lesson in the way
    m, spec, days, pool, ts = case(week + [one(8, 0, 5, "1C", "Mathematics", T0)], need, rules=[most]); assert {s_["state"] for s_ in fixes.add_slots(m, spec, days, key, 1, pool)} == {"no", "na"} and refit.direct(m, spec, days, ts[part], pool) == ([], None)
    m, spec, days, pool, ts = case(rows[:-1], need); cands = refit.direct(m, spec, days, ts[part], pool)[0]; assert [c[0]["p"] for c in cands] == [2]   # with a free place, only free places
    plain = [one(100 * d + p, d, p, CLS_B, "Mathematics", T2) for d in range(5) for p in OPEN]   # 45 lessons that may move: six places, on the emptiest day first
    m, spec, days, pool, ts = case(plain[:-1], need); t = ts[part]; m = dict(m, lessons=m["lessons"] + [dict(m["lessons"][-1], id=999, p=10)])
    busy = lambda d: len({x["id"] for x in m["lessons"] if x["d"] == d}); cands = refit.direct(m, spec, days, t, pool)[0]
    assert len(cands) == 6 and [(c[0]["d"], c[0]["p"]) for c in cands] == [(0, p) for p in OPEN[:6]], cands
    assert all(fixes.judge(m, spec, days, c[0], pool=pool)["state"] == "no" for c in cands)

def over(m, allowance, teacher=T0): return dict(m, teacher_ix=dict(m["teacher_ix"], **{teacher: dict(m["teacher_ix"][teacher], allowance=allowance)}))

def test_an_add_over_the_allowance_needs_no_move():
    key = f"C:{CLS_B}:{EL}"; part = f"dep:{key}:missing"; need = lambda n: lambda s: (plans(n, 1, key)(s), gives(T0, key)(s)); maths = [one(2, 0, 1, CLS_B, "Mathematics", T2)]
    m, spec, days, pool, ts = case(maths, need(1)); usual = refit.direct(m, spec, days, ts[part], pool)[0]; assert len(usual) > 10
    m = over(m, 0); states = {(s_["state"], s_["why"].endswith(ADD_OK)) for s_ in fixes.add_slots(m, spec, days, key, 1, pool) if s_["state"] in ("ok", "prefer")}; assert states == {("prefer", True)}   # every free place is over it
    assert refit.direct(m, spec, days, ts[part], pool) == (usual, None)   # they are offered all the same, in the same order, and no place that is taken
    got, _ = solved(m, spec, days, ts[part], pool); assert [got["fixes"]] == usual[:1] and got["moved"] == set(), got
    m, spec, days, pool, ts = case(maths, need(2)); m = over(m, 1)   # the first add is within it, only the second goes over
    got, _ = solved(m, spec, days, ts[part], pool); assert [(f["kind"], f["d"]) for f in got["fixes"]] == [("add", 1), ("add", 2)] and got["moved"] == set(), got
    wish = dict(AWAY(T0), strength="Prefer"); wishes = [dict(wish, day=x) for x in DAYS]   # a wish of the teacher's is not given up for it
    m, spec, days, pool, ts = case(maths, need(1), rules=wishes); assert refit.direct(over(m, 0), spec, days, ts[part], pool) == ([], None)
    full_week = [x for d in range(5) for x in full(*([1, 2] if d == 0 else []), d=d, cls=CLS_B)] + maths + [band(9, 0, 2, CLS, T0)]   # no free place: one that a lesson may leave, over the allowance or not
    m, spec, days, pool, ts = case(full_week, need(1)); m = over(m, 0); got, _ = solved(m, spec, days, ts[part], pool); assert got["moved"] == {2} and [f["kind"] for f in got["fixes"]] == ["move", "add"], got

def test_a_place_the_add_could_not_take_afterwards_is_not_tried():
    key = f"C:{CLS_B}:{EL}"; part = f"dep:{key}:missing"; need = lambda s: (plans(1, 1, key)(s), gives(T0, key)(s)); last = OPEN[-1]
    week = [one(100 * d + p, d, p, CLS_B, "Mathematics", T2) for d in range(5) for p in OPEN if not (d in (0, 1) and p == last)]   # 1B's week is full but for the last period of Monday and Tuesday
    bands = [band(900, 0, last, CLS, T0), band(901, 1, last, CLS, T0)]   # when the missing lesson's teacher has a band
    most = dict(scope="Teacher", target=T0, rule="Max periods a day", number=2, week="Both", day="All", strength="Must")
    m, spec, days, pool, ts = case(week + bands + [one(950, 0, OPEN[-2], "1C", "Science", T0)], need, rules=[most]); t = ts[part]   # with two periods on Monday T0 may have no more that day
    cands = [c[0] for c in refit.direct(m, spec, days, t, pool)[0]]; assert [(c["d"], c["p"]) for c in cands] == [(0, OPEN[-2])] + [(1, p) for p in OPEN[:5]], cands   # none of Monday's but the place of that teacher's own lesson, which the rule is not broken without
    got, _ = solved(m, spec, days, t, pool); assert got["fixes"][0] == dict(kind="move", id=100 + OPEN[4], d=1, p=last) and [(f["kind"], f["d"], f["p"]) for f in got["fixes"][1:]] == [("add", 1, OPEN[4])], got   # the nearest of the places tried
    m, spec, days, pool, ts = case(week + bands, need); t = ts[part]; held = {p for p in OPEN[:6]}   # nor a place of a lesson an earlier target moved
    assert [(c[0]["d"], c[0]["p"]) for c in refit.direct(m, spec, days, t, pool)[0]] == [(0, p) for p in OPEN[:6]]
    assert [(c[0]["d"], c[0]["p"]) for c in refit.direct(m, spec, days, t, pool, held)[0]] == [(0, p) for p in OPEN[6:8]] + [(1, p) for p in OPEN[:4]]
    got, _ = solved(m, spec, days, t, pool, moved=held); assert got["moved"] == {OPEN[7]} and got["fixes"][1]["p"] == OPEN[7], got
    two = lambda s: (plans(2, 1, key)(s), gives(T0, key)(s))   # nor one of a lesson the list itself moved or put in
    m, spec, days, pool, ts = case(week + bands, two)
    asked, was = [], refit.direct
    def watch(m_, *a): asked.append((m_["lessons"], a[-1])); return was(m_, *a)
    try:
        refit.direct = watch
        with watching() as judged: got, _ = hunt(m, spec, days, ts[part], pool, moved={OPEN[0]})
    finally: refit.direct = was
    assert got and len(got["moved"]) == 2, got
    at = {x["id"]: (x["d"], x["p"]) for x in m["lessons"]}; differ = [{x["id"] for x in L if at.get(x["id"]) != (x["d"], x["p"])} for L, _ in asked]
    assert all(d_ <= held_ and OPEN[0] in held_ for d_, (_, held_) in zip(differ, asked)) and max(map(len, differ)) >= 2, differ   # direct is told of both, and of the earlier targets'
    for fx, c_, _ in judged:
        gone = [f["id"] for f in fx if f["kind"] == "move"]; put = [(f["d"], f["p"]) for f in fx if f["kind"] == "add"]; assert len(set(gone)) == len(gone) and len(set(put)) == len(put), fx

def test_an_add_is_judged_in_the_room_it_takes():
    key = f"C:{CLS_B}:{EL}"; part = f"dep:{key}:missing"; need = lambda s: (plans(1, 1, key)(s), gives(T0, key)(s)); last = OPEN[-1]
    home = case([])[0]["class_ix"][CLS_B]["home"]; shut = dict(scope="Room", target=home, rule="Not available", week="Both", day=DAYS[0], strength="Must", **{"from": 0, "to": NPD - 2})   # 1B's home room is shut on Monday
    plain = lambda first: [one(100 * d + p, d, p, CLS_B, "Mathematics", T2) for d in range(first, 5) for p in OPEN if not (d in (0, 1) and p == last)]
    m, spec, days, pool, ts = case(plain(1) + [band(901, 1, last, CLS, T0)], need, rules=[shut]); t = ts[part]   # Monday is free for 1B, the rest of the week is taken
    assert {(s_["state"], s_["why"].startswith("Rule Room")) for s_ in fixes.add_slots(m, spec, days, key, 1, pool) if s_["d"] == 0 and s_["state"] != "na"} == {("no", True)}
    cands = [c[0] for c in refit.direct(m, spec, days, t, pool)[0]]; assert [(c["d"], c["p"], c["room"]) for c in cands] == [(1, p, home) for p in OPEN[:6]], cands   # with nothing to move on Monday its places are none
    got, _ = solved(m, spec, days, t, pool); assert got["fixes"] == [dict(kind="move", id=100 + OPEN[5], d=1, p=last), dict(kind="add", key=key, d=1, p=OPEN[5], n=1, room=home)], got
    m, spec, days, pool, ts = case(plain(0) + [band(900, 0, last, CLS, T0), band(901, 1, last, CLS, T0)], need, rules=[shut]); t = ts[part]   # Monday is taken too: its lessons could move, but the add could not have the room
    assert [c[0]["d"] for c in refit.direct(m, spec, days, t, pool)[0]] == [1] * 6
    got, _ = solved(m, spec, days, t, pool); assert got["fixes"][0]["d"] == 1 and got["moved"] == {100 + OPEN[5]}, got
    m, spec, days, pool, ts = case([], need, rules=[dict(shut, day="All")]); assert refit.direct(m, spec, days, ts[part], pool) == ([], None)   # a place that is refused with no lesson in it is not one

PULL = "G:PULL1"; ONLY_MONDAY = [AWAY(T0, d) for d in range(1, 5)]
def group(teachers, periods, length=1, double=False):
    """a group outside a band on step 5, and (double) Monday as a day a teacher may take two lessons at once"""
    def change(s):
        base = next(r for r in s["lessons"] if r.get("code") == ENTIRE and CLS in r["classes"])
        s["lessons"].append(dict(base, code="PULL1", code_override="PULL1", classes=[CLS], block="", subject=EL, teachers=list(teachers), periods=periods, length=length, room_kind=None))
        if double: s["school"].update(extra_settings=list(s["school"].get("extra_settings") or []) + [["Teachers may take two lessons at once on", DAYS[0]]])
    return change
def pull(i, p, *teachers): return dict(one(i, 0, p, CLS, EL, T0, group="PULL1"), teachers=list(teachers))   # a lesson of it on Monday
def rest(*keep): return [one(100 * (d + 1) + p, d, p, CLS, "Other", T3) for d in range(5) for p in OPEN if not (d == 0 and p in keep)]   # whole-class lessons in all of 1A's week but these periods of Monday
def ids(rows): return {x["id"] for x in rows}

def test_an_add_is_never_on_top_of_another_lesson_of_the_key():
    key = PULL; part = lambda p: f"dep:{key}:{p}"; only_monday = ONLY_MONDAY
    def adds(got): return [(f["d"], f["p"], f["n"]) for f in got["fixes"]]
    def apart(got): cells = [(d, q) for d, p, n in adds(got) for q in range(p, p + n)]; assert len(cells) == len(set(cells)), got; return adds(got)
    for teachers, periods, double, rules, want in (([T0], 2, True, only_monday, [(0, 1, 1), (0, 2, 1)]), ([T0], 2, False, only_monday, [(0, 1, 1), (0, 2, 1)]), ([T0], 6, True, [], [(d, 1, 1) for d in range(5)] + [(0, 2, 1)])):
        m, spec, days, pool, ts = case([], group(teachers, periods, double=double), rules=rules); got, _ = solved(m, spec, days, ts[part("missing")], pool); assert apart(got) == want, got
    m, spec, days, pool, ts = case([], group([T0], 4, 2, True), rules=only_monday); got, _ = solved(m, spec, days, ts[part("missing")], pool); assert apart(got) == [(0, 1, 2), (0, 5, 2)], got   # lessons of two: not over half of one either
    # nor on top of one that is on the timetable
    mine = [one(40, 0, 1, CLS, EL, T0, group="PULL1")]
    m, spec, days, pool, ts = case(mine, group([T0], 2, double=True), rules=only_monday); t = ts[part("periods")]
    assert fixes.judge(m, spec, days, dict(kind="add", key=key, d=0, p=1, n=1, room=""), pool=pool)["state"] == "ok"   # the judge itself would have it
    assert (0, 1) not in {(c[0]["d"], c[0]["p"]) for c in refit.direct(m, spec, days, t, pool)[0]}; got, _ = solved(m, spec, days, t, pool); assert adds(got) == [(0, 2, 1)], got
    m, spec, days, pool, ts = case([one(40, 0, 2, CLS, EL, T0, group="PULL1")], group([T0], 3, 2, True), rules=only_monday); got, _ = solved(m, spec, days, ts[part("periods")], pool); assert adds(got) == [(0, 5, 2)], got   # nor with one of its two periods on it

def test_an_add_takes_the_place_of_a_lesson_of_its_key_that_can_move():
    key = f"C:{CLS_B}:{EL}"; part = f"dep:{key}:periods"; need = lambda n: lambda s: (plans(n, 2, key)(s), gives(T0, key)(s)); bands = lambda d, *keep: full(*keep, d=d, cls=CLS_B)
    home = case([])[0]["class_ix"][CLS_B]["home"]; add = lambda d, p: dict(kind="add", key=key, d=d, p=p, n=2, room=home)
    # five periods in lessons of two, of which 2 + 1 are there; 1B's week is bands but for Monday's periods 1 (the single), 2 and 5
    rows = [one(1, 1, 1, CLS_B, EL, T0, n=2), one(2, 0, 1, CLS_B, EL, T0)] + bands(0, 1, 2, 5) + bands(1, 1, 2) + [x for d in (2, 3, 4) for x in bands(d)]
    m, spec, days, pool, ts = case(rows, need(5)); t = ts[part]
    assert refit.direct(m, spec, days, t, pool) == ([[add(0, 1)]], None)   # not the place of lesson 1 as well: that lesson would only be put elsewhere
    got, _ = solved(m, spec, days, t, pool)
    assert got == dict(fixes=[dict(kind="move", id=2, d=0, p=5), add(0, 1)], moved={2}, other=0, typed=set(), why=[f"{T0} teaches {EL} for {CLS_B} on {DAYS[0]} period 1.", "Step 3 plans 5 periods of it."]), got
    assert refit.direct(m, spec, days, t, pool, {2}) == ([], None)   # nor that of one that stays where it is
    got, stats = hunt(m, spec, days, t, pool, moved={2}); assert got is None and stats == dict(nodes=0, reason=refit.NO_FIT, late=False), (got, stats)
    # one more lesson of two, beside one with a free period on each side: that one goes a period along
    double = one(1, 0, 6, CLS_B, EL, T0, n=2); m, spec, days, pool, ts = case([double] + bands(0, 5, 6, 7, 8) + [x for d in range(1, 5) for x in bands(d)], need(4)); t = ts[part]
    assert refit.direct(m, spec, days, t, pool) == ([[add(0, 5)], [add(0, 7)]], None)   # over half of it, and not just where it is
    got, _ = solved(m, spec, days, t, pool); assert got["fixes"] == [dict(kind="move", id=1, d=0, p=7), add(0, 5)] and got["moved"] == {1}, got
    others = [one(100 * d + p + 10, d, p, CLS_B, "Mathematics", T2) for d in range(5) for p in OPEN if not (d == 0 and p in (5, 6, 7, 8))]; m, spec, days, pool, ts = case([double] + others, need(4)); t = ts[part]   # among places of other lessons it has its turn in direct's order
    assert [(c[0]["d"], c[0]["p"]) for c in refit.direct(m, spec, days, t, pool)[0]] == [(0, 1), (0, 2), (0, 5), (0, 7), (0, 8), (0, 9)]
    got, _ = solved(m, spec, days, t, pool); assert got["fixes"] == [dict(kind="move", id=1, d=0, p=7), add(0, 5)], got
    # nor is a place inside a longer lesson of the key tried for a shorter one: it would take the turn of another lesson's
    rows = [one(1, 0, 1, CLS_B, EL, T0, n=2), band(9, 0, 10, CLS, T0)] + [one(100 * d + p + 10, d, p, CLS_B, "Mathematics", T2) for d in range(5) for p in OPEN if not (d == 0 and p in (1, 2, 10))]
    m, spec, days, pool, ts = case(rows, need(3)); t = ts[part]; assert [(c[0]["d"], c[0]["p"], c[0]["n"]) for c in refit.direct(m, spec, days, t, pool)[0]] == [(0, p, 1) for p in (3, 5, 6, 7, 8, 9)]
    got, _ = solved(m, spec, days, t, pool); assert got["fixes"] == [dict(kind="move", id=19, d=0, p=10), dict(add(0, 9), n=1)], got
    # a lesson of the key that the judge would leave there (a day of doubles) is not one the list moves out: no place that meets it
    z = one(50, 0, 3, CLS, "Mathematics", T2); m, spec, days, pool, ts = case([pull(40, 2, T0), z] + rest(1, 2, 3), group([T0], 3, 2, True), rules=ONLY_MONDAY); t = ts[f"dep:{PULL}:periods"]; stays = ids(rest(1, 2, 3))
    assert fixes.judge(m, spec, days, dict(kind="add", key=PULL, d=0, p=2, n=2, room="", out=[50]), pool=pool)["state"] == "ok" and refit.direct(m, spec, days, t, pool, stays) == ([], None)

def test_a_swap_never_brings_a_lesson_of_the_key_onto_the_add():
    part = f"dep:{PULL}:periods"; z = one(50, 0, 2, CLS, "Mathematics", T2)
    for who, double, rules in (([T0], True, ONLY_MONDAY),):   # a day of doubles: the judge would have the two at once
        m, spec, days, pool, ts = case([pull(40, 1, *who), z] + rest(1, 2), group(who, 2, double=double), rules=rules); t = ts[part]
        add = dict(kind="add", key=PULL, d=0, p=2, n=1, room=""); c_ = helper.chain(m, spec, days, [dict(kind="swap", a=50, b=40), add]); assert c_["state"] == "ok" and helper.settles(m, spec, days, t["w"], c_["lessons"])
        got, stats = hunt(m, spec, days, t, pool, moved=ids(rest(1, 2))); assert got is None and stats["reason"] == refit.NO_FIT and not stats["late"], (got, stats)
    m, spec, days, pool, ts = case([pull(40, 1, T0), z] + rest(1, 2, 10), group([T0], 2, double=True), rules=ONLY_MONDAY + [AWAY(T0, 0, 10, 10)])   # with one place more for the lesson in the way (T0 is away then, so not for the add)
    got, _ = solved(m, spec, days, ts[part], pool, moved=ids(rest(1, 2, 10))); assert [(f["kind"], f["p"]) for f in got["fixes"]] == [("move", 10), ("add", 2)] and got["moved"] == {50}, got

def test_two_lessons_of_a_key_are_never_moved_to_one_place():
    give = dict(kind="teacher", key=PULL, teachers=[T1]); m, spec, days, pool, ts = case([pull(40, 1, T0), pull(41, 2, T0)], group([T1], 2, double=True), rules=[AWAY(T1, 0, 1, 3)]); t = ts[f"dep:{PULL}:teachers"]
    to = lambda i, p: dict(kind="move", id=i, d=0, p=p); c_ = helper.chain(m, spec, days, [to(41, 5), to(40, 5), give]); assert c_["state"] == "ok" and helper.settles(m, spec, days, t["w"], c_["lessons"])   # the nearest for both
    got, _ = solved(m, spec, days, t, pool); assert got["fixes"] == [to(41, 5), to(40, 6), give], got   # the nearest two
    # nor for a clash: each of them has a whole-class lesson of 1A in its period, which stays
    m, spec, days, pool, ts = case([pull(40, 1, T0), pull(41, 2, T0), one(60, 0, 1, CLS, "Mathematics", T2), one(61, 0, 2, CLS, "Mathematics", T2)], group([T0], 2, double=True)); t = clash_of(ts, f"clash:Class clash: {CLS} ")
    c_ = helper.chain(m, spec, days, [to(41, 3), to(40, 3)]); assert c_["state"] == "ok" and helper.settles(m, spec, days, t["w"], c_["lessons"])
    got, _ = solved(m, spec, days, t, pool, moved={60, 61}); assert sorted(f["p"] for f in got["fixes"]) == [3, 5] and got["moved"] == {40, 41}, got
    # lessons of one key that are in the way of another
    key = f"C:{CLS}:{EL}"; m, spec, days, pool, ts = case([pull(40, 1), pull(41, 2)] + rest(1, 2, 5, 8), lambda s: (group([], 2)(s), plans(2, 2, key)(s), gives(T0, key)(s))); t = ts[f"dep:{key}:missing"]
    got, _ = solved(m, spec, days, t, pool, moved=ids(rest(1, 2, 5, 8))); assert got["moved"] == {40, 41} and sorted(f["p"] for f in got["fixes"][:2]) == [5, 8] and [(f["kind"], f["d"], f["p"]) for f in got["fixes"][2:]] == [("add", 0, 1)], got

def test_a_list_with_two_lessons_of_a_key_at_once_is_not_carried_on():
    # two periods short; the lesson in the place of the first add changes places with one of the key's four nearest (no answer), or goes further
    free = (2, 3, 5, 6, 7, 8, 9, 10); rows = [pull(40 + i, p, T0) for i, p in enumerate((3, 5, 7, 8))] + [one(50, 0, 6, CLS, "Mathematics", T2), one(51, 0, 2, CLS, "Science", T2)] + rest(*free)
    m, spec, days, pool, ts = case(rows, group([T0], 6, double=True), rules=ONLY_MONDAY + [AWAY(T0, 0, 9, 10)]); assert refit.MAX_GROWN == 4 and [x["fix"]["kind"] for x in moves(m, spec, days, 51, moved=ids(rest(*free)) | {50})] == ["swap"] * 4 + ["move"] * 2
    got, _ = solved(m, spec, days, ts[f"dep:{PULL}:periods"], pool, moved=ids(rest(*free)))
    assert got["moved"] == {50, 51} and [f["kind"] for f in got["fixes"]] == ["move", "move", "add", "add"] and {f["p"] for f in got["fixes"][2:]} == {2, 6}, got

def test_lessons_of_a_key_that_are_at_once_already_are_no_reason():
    both = [pull(40, 1, T0), pull(41, 1, T0)]; give = dict(kind="teacher", key=PULL, teachers=[T1]); teach = f"dep:{PULL}:teachers"
    m, spec, days, pool, ts = case(both, group([T1], 2, double=True)); assert at_once(m["lessons"]) == {(40, 41)}; got, _ = hunt(m, spec, days, ts[teach], pool); assert got["fixes"] == [give], got   # they stay
    m, spec, days, pool, ts = case(both, group([T1], 2, double=True), rules=[AWAY(T1, 0, 1, 3)]); got, _ = hunt(m, spec, days, ts[teach], pool); assert {f["id"]: f["p"] for f in got["fixes"][:2]} == {40: 5, 41: 5}, got   # or go on together
    m, spec, days, pool, ts = case(both, group([T0], 3, double=True), rules=ONLY_MONDAY); got, _ = solved(m, spec, days, ts[f"dep:{PULL}:periods"], pool); assert [(f["kind"], f["d"], f["p"]) for f in got["fixes"]] == [("add", 0, 2)], got   # another is added elsewhere
    m, spec, days, pool, ts = case(both + [pull(42, 2, T0)], group([T1], 3, double=True), rules=[AWAY(T1, 0, 1, 3)]); got, _ = hunt(m, spec, days, ts[teach], pool)   # a third is not put with them
    p = {f["id"]: f["p"] for f in got["fixes"][:3]}; assert p[40] == p[41] != p[42], got
    m, spec, days, pool, ts = case(both[:1], group([T1], 2, double=True), rules=[AWAY(T1, 0, 1, 3)]); waits = [dict(m["lessons"][0], id=45, p=5)]   # one that waits to be placed is on no period
    got, _ = solved(dict(m, pool=waits), spec, days, ts[teach], waits); assert got["fixes"] == [dict(kind="move", id=40, d=0, p=5), give], got

def test_lessons_of_a_key_at_once_are_found():
    x = lambda i, p, n=1, d=0, classes=(CLS,), subject=EL, code=ENTIRE: dict(id=i, d=d, p=p, n=n, classes=list(classes), subject=subject, group=code)
    for rows, want in (([x(1, 1), x(2, 1)], {(1, 2)}), ([x(1, 1), x(2, 2)], set()), ([x(1, 1), x(2, 1, d=1)], set()), ([x(1, 1, 3), x(2, 3)], {(1, 2)}), ([x(2, 2, 2), x(1, 1, 2)], {(1, 2)}), ([x(1, 1, 2), x(2, 3)], set()),
                       ([x(1, 1), x(2, 1), x(3, 1)], {(1, 2), (1, 3), (2, 3)}), ([x(1, 1), x(2, 1, subject=SUBJ2)], set()), ([x(1, 1), x(2, 1, classes=[CLS_B])], set()),
                       ([x(1, 1, classes=[CLS, CLS_B]), x(2, 1, classes=["1C", CLS_B])], {(1, 2)}),   # a whole-class lesson of several classes is of the key of each
                       ([x(1, 1, code="Q"), x(2, 1, code="Q", classes=[CLS_B], subject=SUBJ2)], {(1, 2)}), ([x(1, 1, code="Q"), x(2, 1, code="R")], set()), ([x(1, 1), x(2, 1, code="Q")], set()),   # a group is of its code's, whatever its classes
                       ([x(1, 1, code="Q"), x(1, 1, code="R"), x(1, 1, code="Q", classes=[CLS_B])], set()),   # the rows of one lesson
                       ([x(1, 1, classes=[]), x(2, 1, classes=[])], set()), ([x(1, 1, code=""), x(2, 1, code="")], set()), ([x(1, 1, subject=""), x(2, 1, subject="")], set())):   # of no key
        assert refit._at_once(rows) == refit._at_once(rows, {2}) | refit._at_once(rows, {1}) == want, (rows, want)
    rows = [x(1, 1, code="Q"), x(2, 1, code="Q"), x(3, 1), x(4, 1)]; assert refit._at_once(rows) == {(1, 2), (3, 4)} and refit._at_once(rows, {2}) == {(1, 2)} and refit._at_once(rows, {4, 9}) == {(3, 4)} and refit._at_once(rows, set()) == set()   # only of the keys of these lessons

def test_a_surplus_is_deleted_from_the_fullest_days():
    rows = [one(1, 0, 1), one(2, 0, 2), one(5, 0, 3, CLS, "Other"), one(3, 1, 1), one(4, 1, 2), one(6, 1, 3, CLS, "Other"), one(7, 2, 1)]   # Mon and Tue have three periods each, Wed one
    m, spec, days, pool, ts = case(rows, plans(4)); t = ts[f"dep:{KEY}:periods"]; assert [c[0]["id"] for c in refit.direct(m, spec, days, t, pool)[0]] == [4, 3, 2, 1, 7]
    got, _ = solved(m, spec, days, t, pool); assert got["fixes"] == [dict(kind="delete", id=4)] and got["why"] == ["Step 3 plans 4 periods of it."], got   # the best of direct's order (the words alone would take 1)
    m, spec, days, pool, ts = case(rows, plans(3)); got, _ = solved(m, spec, days, ts[f"dep:{KEY}:periods"], pool); assert [f["id"] for f in got["fixes"]] == [4, 2], got   # Mon is the fullest once 4 is gone
    m, spec, days, pool, ts = case(rows, plans(1)); got, _ = solved(m, spec, days, ts[f"dep:{KEY}:periods"], pool)
    assert len(got["fixes"]) == 4 and {f["id"] for f in got["fixes"]} == {4, 2, 3, 1} and got["why"] == ["Step 3 plans 1 period of it."] * 4, got
    m, spec, days, pool, ts = case(rows); t = ts[f"dep:C:{CLS}:Other:extra"]
    got, _ = solved(m, spec, days, t, pool); assert got["fixes"] == [dict(kind="delete", id=6), dict(kind="delete", id=5)] and got["why"] == ["Step 3 plans 0 periods of it."] * 2, got
    ten = [one(i, i % 5, OPEN[i // 5], CLS, "Other") for i in range(1, 11)]   # ten lessons: more than one answer may delete
    m, spec, days, pool, ts = case(ten); got, stats = hunt(m, spec, days, ts[f"dep:C:{CLS}:Other:extra"], pool); assert got is None and stats["reason"] == refit.TOO_MANY and stats["nodes"] == 10 + 7, (got, stats)
    fewer = [one(1, 2, 1, n=2), one(2, 0, 1), one(3, 0, 2), one(4, 0, 3, CLS, "Other")]   # two periods over: one lesson of two rather than two of one, though those are on the fullest day
    m, spec, days, pool, ts = case(fewer, plans(2)); t = ts[f"dep:{KEY}:periods"]; assert [c[0]["id"] for c in refit.direct(m, spec, days, t, pool)[0]] == [3, 2, 1]
    got, _ = solved(m, spec, days, t, pool); assert got["fixes"] == [dict(kind="delete", id=1)], got
    two = [one(1, 0, 1, n=2), one(2, 1, 1), one(3, 2, 1)]   # one period over: the lesson of two is not the one to go, though its day is the fullest
    m, spec, days, pool, ts = case(two, plans(3)); t = ts[f"dep:{KEY}:periods"]; assert refit.direct(m, spec, days, t, pool)[0][0] == [dict(kind="delete", id=1)]
    got, _ = solved(m, spec, days, t, pool); assert got["fixes"] == [dict(kind="delete", id=3)], got

def test_each_wrong_room_is_changed_once():
    rows = [one(1, 0, 1, room="1-01"), one(2, 1, 1, room="1-01")]; studio = dict(room="Studio", kind="art room", capacity=40)
    m, spec, days, pool, ts = case(rows, lambda s: (step5_row(s).update(room_kind="art room"), s.update(venues=list(s["venues"]) + [studio]))); t = ts[f"dep:{KEY}:venue"]
    m = dict(m, room_ix=dict(m["room_ix"], Studio=studio)); cands = [c[0] for c in refit.direct(m, spec, days, t, pool)[0]]
    assert [(f["id"], f["room"]) for f in cands] == [(1, cands[0]["room"]), (1, "Studio"), (2, cands[0]["room"]), (2, "Studio")], cands
    with watching() as judged: hunt(m, spec, days, t, pool)
    assert all(len({f["id"] for f in fx}) == len(fx) for fx, *_ in judged), [fx for fx, *_ in judged]   # never two rooms for one lesson
    got, _ = solved(m, spec, days, t, pool); assert got["fixes"] == [cands[0], cands[2]] and got["why"] == ["Step 3 asks for art room."] * 2 and got["moved"] == set(), got

def test_never_more_prefer():
    wish = dict(PREFER_RULE, target=T1, **{"from": 1, "to": 1})
    m, spec, days, pool, ts = case([one(1, 0, 1)], gives(T1), rules=[wish]); t = ts[TEACH]
    assert helper.chain(m, spec, days, [GIVE])["state"] == "prefer"
    got, stats = hunt(m, spec, days, t, pool)
    assert got is None and stats["nodes"] == 1 and stats["reason"].startswith("Rule ") and stats["reason"].endswith("(Prefer)"), (got, stats)
    def low(spec): gives(T1)(spec)
    m, spec, days, pool, ts = case([one(1, 0, 1)], gives(T1)); ix = dict(m["teacher_ix"]); ix[T1] = dict(ix[T1], allowance=0)
    m = dict(m, teacher_ix=ix); c_ = helper.chain(m, spec, days, [GIVE]); assert c_["state"] == "prefer" and c_["why"].endswith(ADD_OK)
    got, _ = solved(m, spec, days, ts[TEACH], pool); assert got["fixes"] == [GIVE], got   # a teacher's allowance alone is accepted
    m2, spec, days, pool, ts = case([one(1, 0, 1)], gives(T1), rules=[wish]); m2 = dict(m2, teacher_ix=ix)   # both: the wish is what refuses it
    got, stats = hunt(m2, spec, days, ts[TEACH], pool); assert got is None and stats["reason"].endswith("(Prefer)"), (got, stats)
    # a move that would put another wish aside is passed over for one that does not
    hope = dict(PREFER_RULE, scope="Class", target=CLS_B, rule="Not in periods", day=DAYS[0], **{"from": 2, "to": 3})
    m, spec, days, pool, ts = case(BUSY, gives(T1), rules=[hope])
    got, _ = solved(m, spec, days, ts[TEACH], pool, moved={1}); assert got["fixes"] == [dict(kind="move", id=2, d=0, p=5), GIVE], got

def test_a_must_rule_is_never_broken():
    m, spec, days, pool, ts = case([one(1, 0, 1)] + full(1), gives(T1), rules=[AWAY(T1, 0, 1, 1)])   # the new teacher is not there in that period, and 1A's day is full
    got, stats = hunt(m, spec, days, ts[TEACH], pool); assert got is None and stats["reason"].startswith("Rule ") and T1 in stats["reason"], (got, stats)
    must = dict(MUST_RULE, scope="Class", target=CLS_B, rule="Not in periods", day=DAYS[0], **{"from": 2, "to": 3})
    m, spec, days, pool, ts = case(BUSY, gives(T1), rules=[must])
    got, _ = solved(m, spec, days, ts[TEACH], pool, moved={1}); assert got["fixes"] == [dict(kind="move", id=2, d=0, p=5), GIVE], got

def test_the_limits_of_the_search():
    m, spec, days, pool, ts = case(BUSY, gives(T1)); t = ts[TEACH]; why = f"{T1} is teaching {SUBJ2} for {CLS_B} then."
    with limits(MAX_NODES=1): got, stats = hunt(m, spec, days, t, pool, moved={1}); assert got is None and stats == dict(nodes=1, reason=why, late=False), stats
    with limits(MAX_NODES=3): got, stats = hunt(m, spec, days, t, pool, moved={1}); assert got["fixes"][0] == dict(kind="move", id=2, d=0, p=2) and stats == dict(nodes=3, reason="", late=False), (got, stats)   # the best found so far
    with limits(MAX_MOVES=0): got, stats = hunt(m, spec, days, t, pool, moved={1}); assert got is None and stats == dict(nodes=1, reason=why, late=False), stats
    with limits(CAND_LESSONS=0): got, stats = hunt(m, spec, days, t, pool, moved={1}); assert got is None and stats["nodes"] == 1, stats
    def ticking(at):   # a clock that passes the deadline at its at-th reading
        n = [0]
        def now(): n[0] += 1; return 0.0 if n[0] < at else 100.0
        return type("Clock", (), dict(monotonic=staticmethod(now)))
    was = refit.time
    try:
        seen = []
        for at in range(1, 7):
            refit.time = ticking(at); stats = {}; got = refit.solve(m, spec, days, t, pool, {1}, 50.0, stats); seen.append((stats["nodes"], bool(got), stats["late"], stats["reason"]))
    finally: refit.time = was
    late = lambda n: (n, False, True, refit.LATE)   # at the start, before the first list, before the first lesson's places, before the first list of a move; then the best found so far is the answer
    assert seen == [late(0), late(0), late(1), late(1), (2, True, False, ""), (3, True, False, "")], seen
    was = refit.direct
    try:   # with no time left nothing is worked out
        refit.direct = lambda *a: 1 / 0
        assert hunt(m, spec, days, t, pool, wait=-1.0) == (None, dict(nodes=0, reason=refit.LATE, late=True))
    finally: refit.direct = was

def test_a_target_that_needs_you_and_one_already_gone():
    m, spec, days, pool, ts = case([one(1, 0, 1)], lambda s: step5_row(s).update(teachers=[T1, T2]))
    got, stats = hunt(m, spec, days, ts[TEACH], pool); assert got is None and stats == dict(nodes=0, reason=refit.NOT_ONE, late=False), stats
    none = dict(one(1, 0, 1), teachers=[])
    m, spec, days, pool, ts = case([none]); t = clash_of(ts, "clash:noteacher:")   # a move never gives it a teacher
    got, stats = hunt(m, spec, days, t, pool); assert got is None and stats == dict(nodes=0, reason=helper.NO_TEACHER, late=False), stats
    m, spec, days, pool, ts = case(TWICE + [one(8, 1, 1, CLS, EL, T1), one(9, 1, 1, CLS_B, EL, T1)]); mon, tue = [t for k, t in ts.items() if k.startswith("clash:Teacher double-booked: ")]
    now = dict(m, lessons=helper._apply(m["lessons"], [dict(kind="move", id=2, d=0, p=2)], spec, days)["lessons"])
    got, stats = hunt(now, spec, days, mon, pool); assert got == GONE and stats == dict(nodes=0, reason="", late=False), (got, stats)
    got, _ = solved(now, spec, days, tue, pool); assert got["moved"] == {8}, got
    away = dict(MUST_RULE, target=T0, **{"from": 1, "to": 1})
    m, spec, days, pool, ts = case([one(1, 0, 1)], rules=[away]); t = clash_of(ts, "rule:")
    now = dict(m, lessons=helper._apply(m["lessons"], [dict(kind="move", id=1, d=0, p=2)], spec, days)["lessons"])
    assert hunt(now, spec, days, t, pool)[0] == GONE
    m, spec, days, pool, ts = case([one(1, 0, 1)], gives(T1)); now = dict(m, lessons=helper._apply(m["lessons"], [GIVE], spec, days)["lessons"])
    assert hunt(now, spec, days, ts[TEACH], pool)[0] == GONE

def test_a_lesson_in_a_break_is_moved_out_of_it():
    m, spec, days, pool, ts = case([one(1, 0, 0)]); t = clash_of(ts, f"clash:{EL} "); assert t["w"]["crit"] == "break"
    got, stats = solved(m, spec, days, t, pool); assert got["fixes"] == [dict(kind="move", id=1, d=0, p=1)] and got["why"] == ["The clash needs it."], got   # the empty list is never the answer
    now = dict(m, lessons=helper._apply(m["lessons"], got["fixes"], spec, days)["lessons"]); assert hunt(now, spec, days, t, pool) == (GONE, dict(nodes=0, reason="", late=False))
    assert hunt(dict(m, lessons=[]), spec, days, t, pool)[0] == GONE   # deleted by an earlier target

def test_a_full_room_is_emptied():
    rows = [one(1, 0, 1, CLS, EL, T0, room="1-01"), one(2, 0, 1, CLS_B, EL, T1, room="1-01")]
    m, spec, days, pool, ts = case(rows); t = clash_of(ts, "clash:Room over capacity: 1-01 "); assert t["w"]["crit"] == "room"
    got, _ = solved(m, spec, days, t, pool); assert got["fixes"] == [dict(kind="move", id=1, d=0, p=2)], got
    now = dict(m, lessons=helper._apply(m["lessons"], got["fixes"], spec, days)["lessons"]); assert hunt(now, spec, days, t, pool)[0] == GONE
    m, spec, days, pool, ts = case(rows + [one(3, 0, 1, "1C", EL, T2, room="1-01")]); t = clash_of(ts, "clash:Room over capacity: 1-01 ")
    one_less = helper.chain(m, spec, days, [dict(kind="move", id=1, d=0, p=2)]); assert one_less["state"] == "ok" and helper.settles(m, spec, days, t["w"], one_less["lessons"])   # a clash of a room says nothing of the room
    assert t["text"] in export.check_model(dict(m, lessons=one_less["lessons"]))["problems"]
    got, stats = hunt(m, spec, days, t, pool); assert got is None and stats["reason"] == refit.NO_FIT, (got, stats)   # two lessons are still in it: no answer

def test_the_lessons_not_placed_count():
    m, spec, days, pool, ts = case([one(1, 0, 1), one(3, 1, 1)], plans(3)); waiting = [x for x in m["lessons"] if x["id"] == 3]; part = f"dep:{KEY}:periods"
    m = dict(m, lessons=[x for x in m["lessons"] if x["id"] != 3], pool=[]); t = next(t for t in refit.targets(verify.warnings(m, spec)["warnings"]) if t["key"] == part)
    got, _ = solved(m, spec, days, t, []); assert [f["kind"] for f in got["fixes"]] == ["add", "add"], got   # two short
    got, stats = hunt(m, spec, days, t, waiting); assert got is None and stats["reason"] == refit.NO_FIT, (got, stats)   # one of them waits to be placed: two more would be one too many, and one does not settle it
    assert hunt(dict(m, pool=waiting), spec, days, t, waiting) == hunt(dict(m, pool=waiting), spec, days, t, []) == (got, stats) and m["pool"] == []   # the model's own pool is the same thing

# ----------------------------------------------------------------------------------------------- the plan
TIMES = (refit.BUDGET_S, refit_plan.LOOK_S, refit_plan.SIFT_S); refit.BUDGET_S = refit_plan.SIFT_S = 600.0   # what a test finds does not depend on how busy the machine is
def ready(rows, change=None, rules=(), report=(), lifted=()):
    """what plan is given for a timetable of these rows (see case), with no edit made yet: (m, rec, fx); lifted: the ids of lessons that wait in Not placed"""
    m, spec, *_ = case(rows, change, rules, report); pool = [x for x in m["lessons"] if x["id"] in lifted]
    m.update(lessons=[x for x in m["lessons"] if x["id"] not in lifted], pool=pool, draft_meta={}); return m, dict(v=1, spec=spec), dict(texts=[], problems=[], touched=set(), was=[], pool=pool)

def said(m, fx, *starts, decisions=None):
    """the warnings step 8 lists of this timetable, with these answers; only those whose key starts so, when any start is given"""
    return [w for w in draft.tally(draft._warned(m, fx)["warnings"], decisions or {})["warnings"] if not starts or w["key"].startswith(starts)]

def again(w): return w["key"].startswith("typed:") and ":again" in w["key"]
def opened(ws): return [w for w in ws if not w["decision"]]

def planned(given, *starts, decisions=None, progress=None, **k):
    """the plan for those warnings, checked for everything every plan must be, and that nothing given to it was changed"""
    m, rec, fx = given; spec, days = m["checked_setup"], m["days"]; decisions = decisions or {}; ws = said(m, fx, *starts, decisions=decisions); ts = refit.targets(ws); told = []
    def tell(*a): told.append(a); (progress or (lambda *a: None))(*a)
    before, rows = copy.deepcopy([m, rec, fx, decisions, ws]), [id(x) for x in m["lessons"]]
    p = refit_plan.plan(m, rec, fx, decisions, ws, progress=tell, **k)
    assert before == [m, rec, fx, decisions, ws] and rows == [id(x) for x in m["lessons"]]
    assert json.loads(json.dumps(p)) == p and set(p) == {"stamp", "groups", "fixes", "needs", "also", "totals", "late", "seconds"}, p
    assert p["stamp"] == draft.stamp(m["draft_meta"], rec) and p["seconds"] >= 0
    done = [d for d, _ in told]; assert done == sorted(set(done)) and all(n == len(ts) for _, n in told) and done[-1:] == [len(ts)] * bool(ts), told
    steps = [s for g in p["groups"] for s in g["steps"]]; assert [s["n"] for s in steps] == list(range(1, len(steps) + 1)) and [s["fix"] for s in steps] == p["fixes"]
    L, first, held, pool, waited = m["lessons"], {x["id"] for x in m["lessons"]}, {}, list(m["pool"]), []
    for s in steps:   # each on the timetable the earlier ones leave
        f, r = s["fix"], helper._apply(L, [s["fix"]], spec, days); assert not r["problems"] and all(f[v] in first for v in ("id", "a", "b") if v in f), f   # a fix names no lesson the list itself puts in
        tags = (["another day"] if f["kind"] == "move" and next(x["d"] for x in L if x["id"] == f["id"]) != f["d"] else []) + (["no room"] if f["kind"] == "add" and not f["room"] else [])
        mine = [x for x in pool if f["kind"] == "teacher" and fixes._key(f["key"]) in helper._keys_of(x)]; waited += mine; pool = [dict(x, teachers=f["teachers"]) if x in mine else x for x in pool]   # a teacher fix reaches the key's lessons in Not placed too
        tags += [f"check T{w['key'].split(':')[1]} again" for w in verify.typed_again(dict(m, lessons=r["lessons"]), spec, r["touched"], r["was"] + mine)]
        assert s == dict(n=s["n"], fix=f, text=helper.say(dict(m, lessons=L), spec, days, f), why=s["why"], tags=tags) and s["why"].endswith("."), (s, tags)
        L = r["lessons"]
    c_ = helper.chain(m, spec, days, p["fixes"]); assert c_["state"] == "ok" or (c_["state"] == "prefer" and all(t.endswith(ADD_OK) for j in c_["steps"] for t in j["prefer"])), c_
    assert len(c_["texts"]) == len(p["fixes"]); by = {t["key"]: t for t in ts}; part = lambda t: dict(key=t["key"], kind=t["kind"], text=t["text"])
    assert all(g == dict(part(by[g["key"]]), steps=g["steps"]) and g["steps"] and helper.settles(m, spec, days, by[g["key"]]["w"], c_["lessons"]) for g in p["groups"]), p["groups"]
    assert all(n == dict(part(by[n["key"]]), why=n["why"]) and n["why"] for n in p["needs"]), p["needs"]
    solved_, needs = {g["key"] for g in p["groups"]}, {n["key"] for n in p["needs"]}; assert len(solved_) == len(p["groups"]) and not solved_ & needs
    assert [n["key"] for n in p["needs"]] == [t["key"] for t in ts if t["key"] in needs] and p["also"] == [t["text"] for t in ts if t["key"] not in solved_ | needs]   # each target once, in their order
    assert p["late"] is any(n["why"] == refit.LATE for n in p["needs"])
    at = lambda L: {x["id"]: (x["d"], x["p"]) for x in L}; a, b = at(m["lessons"]), at(c_["lessons"]); went = {i for i in a if i in b and a[i] != b[i]}; assert not any(fixes._block(fixes._rows(m["lessons"], i)) for i in went)
    for g in p["groups"]:   # no lesson is moved for two of them
        for i in {f[v] for s in g["steps"] if (f := s["fix"])["kind"] in ("move", "swap") for v in ("id", "a", "b") if v in f}: assert held.setdefault(i, g["key"]) == g["key"], (i, p["groups"])
    m2 = export._model(copy.deepcopy(spec), days, copy.deepcopy(c_["lessons"])); m2.update(checked_setup=spec, rule_report=m["rule_report"], choice_problems=m["choice_problems"])   # made anew
    ws1, ws2 = said(m, fx, decisions=decisions), said(m2, dict(fx, touched=fx["touched"] | c_["touched"], was=list(fx["was"]) + c_["was"] + waited), decisions=decisions); was = {w["key"] for w in opened(ws1) if again(w)}
    count = lambda ws_: [sum(bool(w["crit"]) for w in ws_), sum(not w["crit"] and (not again(w) or w["key"] in was) for w in opened(ws_))]; (c1, w1), (c2, w2) = count(ws1), count(ws2)
    assert dict(critical=c1, warnings=w1) == draft.counts(m, rec, fx, decisions)
    typed = sorted(int(w["key"].split(":")[1]) for w in verify.typed_again(dict(m, lessons=c_["lessons"]), spec, c_["touched"], c_["was"] + waited)); assert {f"check T{n} again" for n in typed} == {t for s in steps for t in s["tags"] if t.startswith("check")}
    left = [(w["text"], w["where"]) for w in ws2]; assert not [t["text"] for t in ts if t["key"] not in needs and (any(x == t["text"] for x, _ in left) if t["w"]["kind"] == "deployment" else (t["text"], t["w"]["where"]) in left)]   # what it settles is no longer on step 8's list
    assert p["totals"] == dict(changes=len(steps), moved=len(went), another_day=sum(a[i][0] != b[i][0] for i in went), critical=[c1, c2], warnings=[w1, w2], typed=typed), (p["totals"], went, c1, c2, w1, w2, typed)
    assert mistakes(m, c_["lessons"]) <= mistakes(m, m["lessons"]), mistakes(m, c_["lessons"]) - mistakes(m, m["lessons"])
    wishes = lambda L: {k for k, w in fixes.rule_subjects(m, spec, L).items() if w["strength"] == "Prefer"}; assert wishes(c_["lessons"]) <= wishes(m["lessons"]), wishes(c_["lessons"]) - wishes(m["lessons"])
    return p

def mistakes(m, lessons):
    """the critical mistakes of these lessons, each period of a place in two lessons by itself: a teacher, a class with a whole-class lesson, a room over what it holds; a row nobody teaches; a lesson out of lesson time"""
    cells = {}
    for x in lessons:
        for q in range(x["p"], x["p"] + x["n"]):
            for k in [("teacher", t) for t in x["teachers"] if x["d"] not in (m.get("double") or ())] + [("class", k_) for k_ in x["classes"]]: cells.setdefault((k, x["d"], q), set()).add((x["id"], x["group"] == ENTIRE))
            for r in fixes.Busy(m, []).rooms(x["room"]) if x["room"] and x["room"] != "TBC" else (): cells.setdefault((("room", r), x["d"], q), []).append(x["id"])
    out = {k for k, v in cells.items() if (len(v) > m["room_cap"].get(k[0][1], 1) if k[0][0] == "room" else len({i for i, _ in v}) > 1 and (k[0][0] == "teacher" or any(w for _, w in v)))}
    by = {}
    for x in lessons: by.setdefault(x["id"], []).append(x)
    b = fixes.Busy(m, []); return out | {("nobody", x["id"], x["group"]) for x in lessons if not x["teachers"]} | {("time", i) for i, rows in by.items() if b.lesson_time(rows, rows[0]["d"], rows[0]["p"], rows[0]["n"])}

def keys(p): return [g["key"] for g in p["groups"]]
def needs(p): return {n["key"]: n["why"] for n in p["needs"]}
def of(p, key): return [s["fix"] for g in p["groups"] if g["key"] == key for s in g["steps"]]

MATHS_B = f"C:{CLS_B}:Mathematics"; MISS_B = f"dep:{MATHS_B}:missing"; HOME_B = next(x["home_room"] for x in SPEC["classes"] if x["class"] == CLS_B)
def wants(teacher=T2, key=MATHS_B, n=1): return lambda s: (plans(n, 1, key)(s), gives(teacher, key)(s))   # step 5 has n periods of the key by that teacher
def both(*changes): return lambda s: [f(s) for f in changes]
ADD_B = dict(kind="add", key=MATHS_B, d=1, p=1, n=1, room=HOME_B)   # its free place: Tuesday, where 1B has nothing yet

def test_a_plan_groups_changes_by_target():
    given = ready(BUSY + full(1), both(gives(T1), wants())); m = given[0]; text = {t["key"]: t["text"] for t in refit.targets(said(m, given[2]))}
    p = planned(given, TEACH, MISS_B)
    assert p["groups"] == [   # the one that needs no move is settled first
        dict(key=MISS_B, kind="missing", text=text[MISS_B], steps=[dict(n=1, fix=ADD_B, text=f"Add Mathematics for {CLS_B} on {DAYS[1]} period 1 (1 period).", why="It was not on the timetable.", tags=[])]),
        dict(key=TEACH, kind="teachers", text=text[TEACH], steps=[
            dict(n=2, fix=dict(kind="move", id=2, d=0, p=2), text=f"Move {SUBJ2} for {CLS_B} from {DAYS[0]} period 1 to {DAYS[0]} period 2.", why=f"{T1} teaches {SUBJ2} for {CLS_B} on {DAYS[0]} period 1.", tags=[]),
            dict(n=3, fix=GIVE, text=f"Give {EL} for {CLS} to {T1}.", why=f"Step 5 now gives it to {T1}.", tags=[])])], p["groups"]
    assert p["needs"] == [] == p["also"] and p["late"] is False and p["fixes"] == [ADD_B, dict(kind="move", id=2, d=0, p=2), GIVE]
    n = draft.counts(m, given[1], given[2], {}); assert p["totals"] == dict(changes=3, moved=1, another_day=0, critical=[n["critical"]] * 2, warnings=[n["warnings"], n["warnings"] - 2], typed=[]), (p["totals"], n)
    assert dict(p, seconds=0) == dict(planned(given, TEACH, MISS_B), seconds=0)   # the same again: the same plan
    assert dict(p, seconds=0) == dict(refit_plan.plan(*given, {}, said(m, given[2], TEACH, MISS_B)), seconds=0)   # progress is not needed
    none = planned(given, "nothing"); assert none["groups"] == none["fixes"] == none["needs"] == none["also"] == [] and none["late"] is False and none["totals"] == dict(changes=0, moved=0, another_day=0, critical=[n["critical"]] * 2, warnings=[n["warnings"]] * 2, typed=[]), none

TWO_KEYS = f"C:1C:Mathematics"; TEACH_C = f"dep:{TWO_KEYS}:teachers"; GIVE_C = dict(kind="teacher", key=TWO_KEYS, teachers=[T1])
def test_targets_build_on_each_other():
    # T1 is to take 1A's English at period 1 and 1C's Maths at period 2 (their days are full), and has a lesson of 1B at both times
    rows = BUSY + full(1) + [one(11, 0, 2, "1C", "Mathematics", T2), one(13, 0, 2, CLS_B, "Science", T1)] + full(2, cls="1C", start=3000)
    given = ready(rows, both(gives(T1), gives(T1, TWO_KEYS))); to = lambda i, p: dict(kind="move", id=i, d=0, p=p)
    assert of(planned(given, TEACH_C), TEACH_C) == [to(13, 3), GIVE_C]   # by itself
    p = planned(given, TEACH, TEACH_C); assert keys(p) == [TEACH, TEACH_C] and p["fixes"] == [to(2, 3), GIVE, to(13, 5), GIVE_C], p["fixes"]   # period 3 is taken by the first; in period 1 T1 has 1A then
    asked, was = [], refit.solve
    def watch(m_, spec, days, t, pool, moved, *a): asked.append((t["key"], m_, set(moved))); return was(m_, spec, days, t, pool, moved, *a)
    given = ready(rows, both(gives(T1), gives(T1, TWO_KEYS), wants()))
    try: refit.solve = watch; p = planned(given, TEACH, TEACH_C, MISS_B)
    finally: refit.solve = was
    assert keys(p) == [MISS_B, TEACH, TEACH_C]; m = given[0]; put = max(x["id"] for x in m["lessons"]) + 1
    last = {k: (m_, held) for k, m_, held in asked}; assert last[MISS_B][1] == set() and last[TEACH][1] == {put} and last[TEACH_C][1] == {put, 2}   # the lesson the first put in and the one the second moved stay where they are
    L = m["lessons"]
    for k in keys(p):
        assert last[k][0]["lessons"] == L and last[k][0]["pool"] is m["pool"]; L = helper._apply(L, of(p, k), m["checked_setup"], m["days"])["lessons"]
    mine = {id(x) for x in m["lessons"]}; assert [x["id"] for x in last[TEACH_C][0]["lessons"] if id(x) not in mine] == [1, 2, put]   # the rows no fix changes are the timetable's own

def test_a_lesson_is_moved_for_one_target_only():
    late = dict(scope="Class", target=CLS_B, rule="Only in periods", week="Both", day="All", strength="Must", **{"from": 5, "to": 10})
    given = ready([BUSY[1]], rules=[AWAY(T1, 0, 1, 1), late]); r1, r2 = (t["key"] for t in refit.targets(said(given[0], given[2], "rule:")))
    assert [f["p"] for f in of(planned(given, r2), r2)] == [5]   # by itself
    p = planned(given, "rule:"); assert of(p, r1) == [dict(kind="move", id=2, d=0, p=2)] and needs(p) == {r2: refit.NO_FIT}, p

def test_one_settled_by_the_changes_of_another():
    rows = [one(1, 0, 1), one(3, 0, 1, CLS_B, "Mathematics", T0)]; clash = "clash:Teacher double-booked: "   # T0 has both, and is to lose the first
    given = ready(rows, gives(T1)); t = next(t for t in refit.targets(said(given[0], given[2], clash)))
    assert [f["kind"] for f in planned(given, clash)["fixes"]] == ["move"]   # by itself it is a move
    p = planned(given, TEACH, clash); assert keys(p) == [TEACH] and p["fixes"] == [GIVE] and p["also"] == [t["text"]] and p["needs"] == [] and p["totals"]["critical"] == [1, 0] and p["totals"]["moved"] == 0, p
    # nor is one that comes before it
    rule = AWAY(T1, 0, 1, 1); given = ready([one(2, 0, 1, CLS_B, "Other", T1)], rules=[rule]); extra = f"dep:C:{CLS_B}:Other:extra"
    p = planned(given, extra, "rule:"); assert keys(p) == [extra] and len(p["also"]) == 1 and p["also"][0].startswith("Rule Teacher"), p

def test_a_lesson_not_placed_and_two_bands_at_once_need_you():
    given = ready([one(1, 0, 1), one(6, 2, 1, "1C", "Other", T2)], gives(T1), lifted={6}); m, rec, fx = given; p = planned(given, TEACH, "clash:notplaced:")   # no list places a lesson
    assert keys(p) == [TEACH] and p["also"] == [] and needs(p) == {"clash:notplaced:6": "That lesson is not placed. Place it first."}, p
    assert fixes.judge(m, m["checked_setup"], m["days"], dict(kind="move", id=6, d=2, p=2), pool=m["pool"])["why"] == refit.NOT_PLACED   # the judge's own words
    t = next(t for t in refit.targets(said(m, fx, "clash:notplaced:"))); got, stats = hunt(m, m["checked_setup"], m["days"], t, m["pool"]); assert got is None and stats == dict(nodes=0, reason=refit.NOT_PLACED, late=False), (got, stats)
    two = lambda s: s.update(blocks=[dict(block=f"{LEVEL} Band {x}", level=LEVEL, everyone=True) for x in "XY"]); row = lambda i, p, x: one(i, 0, p, CLS, EL, T2 if x == "X" else T3, n=2, block=f"{LEVEL} Band {x}", group=f"{x}1")
    given = ready([one(1, 2, 1), row(40, 1, "X"), row(41, 2, "Y")], both(gives(T1), two)); m, rec, fx = given; p = planned(given, TEACH, "clash:bands:")   # the second band starts a period after the first
    assert keys(p) == [TEACH] and p["also"] == [] and list(needs(p).values()) == [refit.BAND], p
    t = next(t for t in refit.targets(said(m, fx, "clash:bands:"))); got, stats = hunt(m, m["checked_setup"], m["days"], t, m["pool"]); assert got is None and stats == dict(nodes=0, reason=refit.BAND, late=False), (got, stats)

@contextlib.contextmanager
def swapped(*names):
    """(module, name, value): these put in place for a while"""
    was = [(m_, n, getattr(m_, n)) for m_, n, _ in names]
    for m_, n, v in names: setattr(m_, n, v)
    try: yield
    finally:
        for m_, n, v in was: setattr(m_, n, v)
def at(clock): return (refit, "time", clock), (refit_plan, "time", clock)

@contextlib.contextmanager
def asking():
    """every look: (the target's key, max_moves)"""
    out, was = [], refit.solve
    def solve(m, spec, days, t, pool, moved, deadline, stats=None, max_moves=None): out.append((t["key"], max_moves)); return was(m, spec, days, t, pool, moved, deadline, stats, max_moves)
    refit.solve = solve
    try: yield out
    finally: refit.solve = was

def test_what_one_deletion_makes_room_for_needs_no_move():
    # 1B's week is full of bands but for a lesson that is not on step 5; the missing one, first on the list, fits once that is deleted
    rows = [x for d in range(5) for x in full(*([2] if d == 0 else []), d=d, cls=CLS_B)] + [one(2, 0, 2, CLS_B, "Other", T0)]; extra = f"dep:C:{CLS_B}:Other:extra"
    given = ready(rows, wants())
    with asking() as asked: p = planned(given, MISS_B, extra)
    assert keys(p) == [extra, MISS_B] and p["fixes"] == [dict(kind="delete", id=2), dict(ADD_B, d=0, p=2)] and asked == [(MISS_B, 0), (extra, 0), (MISS_B, 0)], (p["fixes"], asked)   # no full look at either
    assert planned(given, MISS_B)["needs"][0]["why"] == refit.NO_FIT
    given = ready(rows + [one(9, 1, 2, "1C", "Other", T0)], wants())   # one that was looked at after the last change is not looked at again
    with asking() as asked: p = planned(given, MISS_B, extra, "dep:C:1C:Other:extra")
    assert asked == [(MISS_B, 0), (extra, 0), ("dep:C:1C:Other:extra", 0), (MISS_B, 0)], asked

def checked_as(answer):
    """helper.chain of the plan's own check (the search gives it a memo): answer(fixes, chain's dict) -> the dict to take for it"""
    real = helper.chain
    def chain(m_, sp, dy, fx, ctx=None, memo=None): c_ = real(m_, sp, dy, fx, ctx, memo); return c_ if memo is not None else answer(fx, c_)
    return helper, "chain", chain
def listing(when, *a, **k):
    """verify.warnings with one more, verify.warning(*a, **k), for a timetable when says so of (the three made in it)"""
    real = verify.warnings
    def warnings(m_, *b, **kw):
        ws = real(m_, *b, **kw)
        if when(made_in(m_["lessons"])): ws["warnings"].append(verify.warning(*a, **k))
        return ws
    return verify, "warnings", warnings
def open_at_end(*which):
    """refit._settled that says no of these once every target was looked at: which are (key, a test of the lessons) -> (the swap, the progress to give)"""
    real, end = refit._settled, []
    return (refit, "_settled", lambda m_, sp, dy, w, L, *a: real(m_, sp, dy, w, L, *a) and not (end and any(w["key"] == k and t(L) for k, t in which))), lambda done, total: end.append(1) if done == total else None

# ------------------------------------------------------------ a teacher and the periods of one key
SHORT = f"dep:{KEY}:periods"; STUCK = [one(1, 0, 1), band(3, 0, 1, CLS_B, T1)] + full(1)   # 1A's English can have T1 neither then nor at another time of its day
def lessons_of(p, given, key=KEY): m = given[0]; return helper._of_key(helper._apply(m["lessons"], p["fixes"], m["checked_setup"], m["days"])["lessons"], fixes._key(key))   # the rows of the key once the list is made

def test_a_period_is_added_after_its_teacher_change():
    given = ready(BUSY + full(1), both(gives(T1), plans(2)))   # the change needs a move; a period is missing as well
    with asking() as asked: p = planned(given, TEACH, SHORT)
    assert keys(p) == [TEACH, SHORT] and p["fixes"][:2] == [dict(kind="move", id=2, d=0, p=2), GIVE] and [f["kind"] for f in p["fixes"]] == ["move", "teacher", "add"] and p["needs"] == [] and asked == [(TEACH, 0), (TEACH, None), (SHORT, 0)], (p["fixes"], asked)   # the add is first looked at once the change is made
    assert [x["teachers"] for x in lessons_of(p, given)] == [[T1], [T1]], lessons_of(p, given)
    ws = said(given[0], given[2], TEACH, SHORT); again_ = [dict(w, key=w["key"] + "#2") if w["key"] == SHORT else dict(w, key=w["key"] + "#3") if w["key"] == TEACH else w for w in ws]; p2 = refit_plan.plan(*given, {}, again_); assert p2["fixes"] == p["fixes"], p2   # a repeated key's number makes no difference
    with asking() as asked: p = planned(ready([one(1, 0, 1)], both(gives(T1), plans(2))), TEACH, SHORT)
    assert keys(p) == [TEACH, SHORT] and asked == [(TEACH, 0), (SHORT, 0)], asked   # a change that needs none is settled before its turn comes
    looks, real = [], refit.solve   # nor is one that others' fixes have settled waited for (made up: theirs cannot leave the key short)
    def gone(m, spec, days, t, *a): looks.append(t["key"]); return dict(GONE) if t["key"] == TEACH else real(m, spec, days, t, *a)
    given = ready(BUSY + full(1), both(gives(T1), plans(2)))
    try: refit.solve = gone; refit_plan.plan(*given, {}, said(given[0], given[2], TEACH, SHORT)); assert looks == [TEACH, SHORT], looks
    finally: refit.solve = real

def test_a_period_is_not_added_when_its_teacher_change_has_no_answer():
    given = ready(STUCK, both(gives(T1), plans(2)))
    with asking() as asked: p = planned(given, TEACH, SHORT)
    assert p["fixes"] == [] and needs(p) == {TEACH: f"{T1} is teaching group Q3 then.", SHORT: "Its teachers differ from step 5 too: settle that first, then run Re-fit again."} and refit_plan.TEACHER_FIRST == needs(p)[SHORT] and p["late"] is False and asked == [(TEACH, 0), (TEACH, None)], (p, asked)
    p = planned(ready([one(1, 0, 1)], both(lambda s: step5_row(s).update(teachers=[T1, T2]), plans(2))), TEACH, SHORT); assert needs(p) == {TEACH: refit.NOT_ONE, SHORT: refit_plan.TEACHER_FIRST} and p["fixes"] == [], p
    was, log = refit.solve, logging.getLogger("refit_plan")   # nor when the search breaks on it
    def solve(m, spec, days, t, *a):
        if t["key"] == TEACH: raise KeyError("x")
        return was(m, spec, days, t, *a)
    try: refit.solve, log.disabled = solve, True; p = planned(ready([one(1, 0, 1)], both(gives(T1), plans(2))), TEACH, SHORT)
    finally: refit.solve, log.disabled = was, False
    assert needs(p) == {TEACH: refit_plan.BROKEN, SHORT: refit_plan.TEACHER_FIRST} and p["fixes"] == [], p
    # other targets are worked on all the same, and one that is taken out of the list says so
    given = ready(STUCK, both(gives(T1), plans(2), wants())); p = planned(given, TEACH, SHORT, MISS_B); assert keys(p) == [MISS_B] and list(needs(p)) == [TEACH, SHORT], p
    # nor when the change is taken out of the list, however it is found to be at fault
    given = ready([one(1, 0, 1)], both(gives(T1), plans(2))); ws = said(given[0], given[2], TEACH, SHORT)
    with swapped(checked_as(lambda fx_, c_: dict(c_, texts=[]) if fx_ == [GIVE] else c_)): p = refit_plan.plan(*given, {}, ws); assert p["fixes"] == [] and needs(p) == {TEACH: refit.NO_FIT, SHORT: refit_plan.TEACHER_FIRST}, p
    swap, progress = open_at_end((TEACH, lambda L: len([x for x in L if x["subject"] == EL]) == 2))   # open again only with the period added
    with swapped(swap): p = refit_plan.plan(*given, {}, ws, progress=progress); assert p["fixes"] == [] and needs(p) == {TEACH: refit.NO_FIT, SHORT: refit_plan.TEACHER_FIRST}, p
    with swapped(checked_as(lambda fx_, c_: dict(c_, texts=[]) if fx_ and fx_[0]["kind"] == "add" else c_)): p = refit_plan.plan(*given, {}, ws); assert keys(p) == [TEACH] and needs(p) == {SHORT: refit.NO_FIT}, p   # (the add itself)
    with swapped(checked_as(lambda fx_, c_: dict(c_, texts=[])), (refit_plan, "SIFT_S", 0)): p = refit_plan.plan(*given, {}, ws); assert needs(p) == {TEACH: refit.LATE, SHORT: refit.LATE}, p

def test_a_period_is_late_when_its_teacher_change_is():
    given = ready(BUSY + full(1), both(gives(T1), plans(2)))
    p = planned(given, TEACH, SHORT, budget=0); assert needs(p) == {TEACH: refit.LATE, SHORT: refit.LATE} and p["late"] is True, p
    clock, real, told = Clock(), refit.solve, []
    def solve(m, spec, days, t, pool, moved, deadline, stats=None, most=None): got = real(m, spec, days, t, pool, moved, deadline, stats, most); clock.t += 1000; return got
    with swapped(*at(clock), (refit, "solve", solve)):
        p = planned(given, TEACH, SHORT, progress=lambda *a: told.append(a)); assert needs(p) == {TEACH: refit.LATE, SHORT: refit.LATE} and told == [(2, 2)], (p, told)   # after the look without moves
        p = planned(ready([one(1, 0, 1)], both(gives(T1), plans(2))), TEACH, SHORT); assert keys(p) == [TEACH] and needs(p) == {SHORT: refit.LATE}, p   # the change is made and no time is left for the add
    p = planned(ready(STUCK, both(gives(T1), plans(2))), TEACH, SHORT, progress=lambda *a: told.append(a)); assert told[-2:] == [(1, 2), (2, 2)] and p["late"] is False, told   # progress reaches the total when the add was never looked at

def test_only_an_add_of_the_same_key_waits():
    # a surplus helps the teacher change: one of two lessons goes, and it is the one whose period the new teacher has not free
    given = ready(BUSY + full(1) + [one(4, 1, 1)], both(gives(T1), plans(1)))
    with asking() as asked: p = planned(given, TEACH, SHORT)
    assert p["fixes"] == [dict(kind="delete", id=1), GIVE] and keys(p) == [SHORT, TEACH] and asked == [(TEACH, 0), (SHORT, 0), (TEACH, 0)], (p, asked)
    for key in (f"C:{CLS_B}:{EL}", f"C:{CLS}:Mathematics"):   # two keys do not wait for each other
        other = f"dep:{key}:periods"; given = ready(STUCK + [one(2, 2, 1, key.split(":")[1], key.split(":")[2], T0)], both(gives(T1), plans(2, 1, key), gives(T0, key))); p = planned(given, TEACH, other)
        assert keys(p) == [other] and list(needs(p)) == [TEACH], p
    rooms = lambda s: step5_row(s).update(room_kind="planetarium"); given = ready([one(1, 0, 1, room="1-01")], both(plans(2), gives(T0), rooms)); p = planned(given, f"dep:{KEY}:venue", SHORT); assert keys(p) == [SHORT] and list(needs(p)) == [f"dep:{KEY}:venue"], p   # nor for another difference of the key
    # it is the timetable that says whether a period is missing: one that waits in Not placed is not, whatever the warning says
    given = ready(STUCK + [one(6, 2, 1)], both(gives(T1), plans(2)), lifted={6}); text = next(w["text"] for w in said(given[0], given[2], SHORT)); assert "1 periods timetabled, 2 on step 3" in text
    p = planned(given, TEACH, SHORT); assert p["fixes"] == [] and needs(p)[SHORT] == text, p
    m, rec, fx = given = ready(STUCK, both(gives(T1), plans(2))); work = refit_plan._Plan(m, refit.targets(said(m, fx, TEACH, SHORT)), None, 0.0); assert work._waits(0) == [] and work._waits(1) == [0]   # as it is at that moment
    work.now = dict(m, lessons=m["lessons"] + [dict(m["lessons"][0], id=999, d=2)]); assert work._waits(1) == []
    # a band's periods are never added: they say so
    b = next(k for k, e in verify.planned_rows(SPEC_CHECKED).items() if k[0] == "G" and any(r.get("block") for r in e["rows"]) and len(e["teachers"]) == 1); row = verify.planned_rows(SPEC_CHECKED)[b]["rows"][0]; who = row["teachers"][0]; had = next(x for x in (T0, T1, T2) if x != who)
    given = ready([one(20, 0, 2, row["classes"][0], row["subject"], had, block=row["block"], group=b[1]), band(21, 0, 2, "2A", who)]); teach, periods = f"dep:G:{b[1]}:teachers", f"dep:G:{b[1]}:periods"
    p = planned(given, teach, periods); assert needs(p) == {teach: f"{who} is teaching group Q21 then.", periods: refit.BAND}, p

# ------------------------------------------------------------ the time
def sec(x): return round(x, 6)
PAST = 1 / 1024   # how far past its deadline a look that is cut short ends
class Clock:
    """a clock that goes on only as a test says"""
    def __init__(self): self.t = 1000.0
    def monotonic(self): return self.t

@contextlib.contextmanager
def played(part):
    """refit.solve played by part(key, max_moves, how often the target was looked at in full before) -> (fixes or None, its sentence, the seconds it takes; None: until the deadline) on a clock of its own; yields
    (the looks, each (key, max_moves, the seconds it was given), the clock). What it answers counts as settled"""
    clock, looks, gone = Clock(), [], set()
    def solve(m, spec, days, t, pool, moved, deadline, stats=None, max_moves=None):
        before = sum(k == t["key"] and most is None for k, most, _ in looks); looks.append((t["key"], max_moves, sec(deadline - clock.t)))
        got, why, takes = part(t["key"], max_moves, before); late = takes is None; clock.t = deadline + PAST if late else clock.t + takes
        stats.update(nodes=1, reason=refit.LATE if late else why, late=late); gone.update([t["key"]] if got == [] else ()); return None if got is None else dict(fixes=got, moved=set(), other=0, typed=set(), why=["It is made up."] * len(got))
    with swapped(*at(clock), (refit, "solve", solve), (refit, "_settled", lambda *a: True), (refit, "_gone", lambda m, spec, days, w, *a: w["key"] in gone)): yield looks, clock

A_, B_, C_ = KEYS = ["rule:0:a", "rule:0:b", "rule:0:c"]
def made_up(*keys): return [dict(verify.warning(k, "rule", f"Text of {k}."), decision=None) for k in keys]
def play(part, *keys, budget=30, given=None):
    """the plan for made-up targets -> (plan, looks, progress)"""
    told = []; given = given or ready([one(1, 0, 1), one(2, 1, 1), one(3, 2, 1)])
    with played(part) as (looks, clock): p = refit_plan.plan(*given, {}, made_up(*(keys or KEYS)), progress=lambda *a: told.append(a), budget=budget)
    return p, looks, told
def full_looks(looks): return [(k, s) for k, most, s in looks if most is None]
TO = lambda i, p: [dict(kind="move", id=i, d=i - 1, p=p)]

def test_each_full_look_has_its_share_of_the_time():
    p, looks, told = play(lambda k, most, n: (None, f"About {k}.", 0 if most == 0 else 1))
    assert looks == [(k, 0, 30) for k in KEYS] + [(A_, None, 10), (B_, None, 14.5), (C_, None, 28)], looks   # every target without moves, then each in full: what is left shared by those left
    assert needs(p) == {k: f"About {k}." for k in KEYS} and p["late"] is False and p["groups"] == p["also"] == [] and told == [(1, 3), (2, 3), (3, 3)], (p, told)
    p, looks, _ = play(lambda k, most, n: (None, f"About {k}.", 0 if most == 0 else 1), budget=3); assert full_looks(looks) == [(A_, 2), (B_, 2), (C_, 1)] and refit_plan.LOOK_S == 2.0, looks   # never less than two seconds, nor past the end
    p, looks, _ = play(lambda k, most, n: (None, "x.", 7 if most == 0 else 1)); assert looks[:3] == [(A_, 0, 30), (B_, 0, 23), (C_, 0, 16)] and full_looks(looks)[0] == (A_, 3), looks

def test_a_look_that_was_cut_short_is_made_again_with_more_time():
    about = lambda cut: lambda k, most, n: (None, f"About {k}.", 0 if most == 0 else None if cut(k, n) else 1)   # a full look takes a second, or until just past its deadline
    p, looks, told = play(about(lambda k, n: k == A_ and n == 0))
    assert full_looks(looks) == [(A_, 10), (B_, sec(10 - PAST / 2)), (C_, sec(19 - PAST)), (A_, sec(18 - PAST))] and len(looks) == 3 + 4, looks   # nothing changed: no other target again, and none without moves
    assert needs(p) == {k: f"About {k}." for k in KEYS} and p["late"] is False and told == [(1, 3), (2, 3), (3, 3)], (p, told)
    p, looks, _ = play(about(lambda k, n: k == A_)); assert full_looks(looks)[3:] == [(A_, sec(18 - PAST))] and needs(p) == {A_: refit.LATE, B_: f"About {B_}.", C_: f"About {C_}."} and p["late"] is True, (looks, p)
    p, looks, _ = play(lambda k, most, n: (None, "x.", 0 if most == 0 else None if k == A_ else 6)); assert [k for k, _ in full_looks(looks)] == KEYS and needs(p)[A_] == refit.LATE, looks   # eight seconds are left: less than it had
    p, looks, _ = play(lambda k, most, n: (None, "x.", 0 if most == 0 else None if k == A_ else 5 - PAST if k == B_ else 5)); assert [k for k, _ in full_looks(looks)] == KEYS and needs(p)[A_] == refit.LATE, looks   # just what it had
    # of two that were cut short each is looked at again when its share is more than it had: first the second alone has more
    D_ = "rule:0:d"; p, looks, _ = play(lambda k, most, n: (None, f"About {k}.", 0 if most == 0 or k in (C_, D_) else None if n == 0 else 2), *KEYS, D_)
    assert [k for k, _ in full_looks(looks)] == [A_, B_, C_, D_, B_, A_] and [s for _, s in full_looks(looks)][:2] == [7.5, sec(7.5 - PAST / 3)] and [s for _, s in full_looks(looks)][4:] == [sec(15 - PAST * 5 / 3), sec(13 - PAST * 5 / 3)] and p["late"] is False, looks
    # it is looked at again whatever time is left when the timetable has changed
    p, looks, _ = play(lambda k, most, n: (TO(3, 2) if k == C_ and most is None else None, f"About {k}.", 0 if most == 0 else None if k == A_ and n == 0 else 9)); assert full_looks(looks)[3:] == [(A_, sec(2 - PAST))] and needs(p)[A_] == f"About {A_}.", looks

def test_a_target_is_looked_at_again_only_after_a_change():
    def order(looks): return [(k, most) for k, most, _ in looks]
    short_, long_ = [(k, 0) for k in KEYS], [(k, None) for k in KEYS]
    p, looks, told = play(lambda k, most, n: (TO(2, 2) if k == B_ and most is None else None, f"{k} after {n}.", 0))
    assert order(looks) == short_ + long_ + [(A_, 0), (A_, None)] and keys(p) == [B_] and needs(p) == {A_: f"{A_} after 1.", C_: f"{C_} after 0."} and told == [(1, 3), (2, 3), (3, 3)], (looks, p, told)   # only the one looked at before the change, first without moves
    p, looks, _ = play(lambda k, most, n: (TO(3, 2) if k == C_ and most is None else TO(1, 2) if (k, most, n) == (A_, None, 1) else None, f"{k} after {n}.", 0))   # an answer in the second round, before the other's turn
    assert order(looks) == short_ + long_ + [(A_, 0), (B_, 0), (A_, None), (B_, None)] and keys(p) == [C_, A_] and needs(p) == {B_: f"{B_} after 1."}, looks
    p, looks, _ = play(lambda k, most, n: (TO(3, 2) if k == C_ and most is None else TO(2, 2) if (k, most, n) == (B_, None, 1) else None, f"{k} after {n}.", 0))   # and after it: a third round
    assert order(looks) == short_ + long_ + [(A_, 0), (B_, 0), (A_, None), (B_, None), (A_, 0), (A_, None)] and keys(p) == [C_, B_] and needs(p) == {A_: f"{A_} after 2."}, looks
    p, looks, _ = play(lambda k, most, n: (TO(3, 2) if k == C_ and most is None else TO(1, 2) if (k, most, n) == (A_, 0, 1) else None, f"{k} after {n}.", 0))   # in the passes without moves of a later round, which go on until one settles nothing
    assert order(looks) == short_ + long_ + [(A_, 0), (B_, 0), (B_, None)] and keys(p) == [C_, A_], looks

def test_the_time_limit_leaves_the_rest_in_needs_you():
    given = ready(BUSY + full(1), both(gives(T1), wants()))
    with asking() as asked: p = planned(given, TEACH, MISS_B, budget=0)
    assert asked == [] and needs(p) == {TEACH: refit.LATE, MISS_B: refit.LATE} and p["late"] is True and p["groups"] == [] and p["totals"]["changes"] == 0, p
    with limits(BUDGET_S=0): assert planned(given, TEACH, MISS_B)["late"] is True   # read when the plan is called
    clock, real = Clock(), refit.solve
    def stop(after):   # the time is up after so many looks
        n = [0]
        def solve(m, spec, days, t, pool, moved, deadline, stats=None, most=None):
            got = real(m, spec, days, t, pool, moved, deadline, stats, most); n[0] += 1; clock.t += 1000 if n[0] == after else 0; return got
        return solve
    with swapped(*at(clock), (refit, "solve", stop(2))):
        p = planned(given, TEACH, MISS_B); assert keys(p) == [MISS_B] and needs(p) == {TEACH: refit.LATE} and p["late"] is True, p   # what was found before is listed, and the sentence of the look without moves is not
        stats = {}; assert real(given[0], given[0]["checked_setup"], given[0]["days"], refit.targets(said(given[0], given[2], TEACH))[0], [], set(), clock.t + 9, stats, 0) is None and stats["reason"] == f"{T1} is teaching {SUBJ2} for {CLS_B} then."
    with swapped(*at(clock), (refit, "solve", stop(1))): p = planned(given, TEACH, MISS_B); assert p["groups"] == [] and needs(p) == {TEACH: refit.LATE, MISS_B: refit.LATE}, p
    p, looks, told = play(lambda k, most, n: (None, "x.", 40)); assert looks == [(A_, 0, 30)] and set(needs(p).values()) == {refit.LATE} and told == [(3, 3)], (looks, told)   # nothing is looked at any more
    # the last full look speaks, also when the time is up before another, and when an earlier one had finished
    p, looks, told = play(lambda k, most, n: (TO(2, 2) if k == B_ and most is None else None, f"About {k}.", 0 if most == 0 else 40 if k == B_ else 0)); assert keys(p) == [B_] and needs(p) == {A_: f"About {A_}.", C_: refit.LATE} and p["late"] is True and told == [(1, 3), (2, 3), (3, 3)], (p, told)
    p, looks, told = play(lambda k, most, n: (TO(2, 2) if k == B_ and most is None else None, f"About {k}.", 0 if most == 0 or n == 0 else None)); assert full_looks(looks)[-1][0] == A_ and needs(p) == {A_: refit.LATE, C_: f"About {C_}."}, (looks, p)

def test_what_the_list_settles_is_never_said_to_need_you():
    rows = [one(1, 0, 1), one(3, 0, 1, CLS_B, "Mathematics", T0)]; start = "clash:Teacher double-booked: "; given = ready(rows, gives(T1)); t = next(t for t in refit.targets(said(given[0], given[2], start)))
    clock, real, gone, told = Clock(), refit.solve, refit._gone, []; miss = f"dep:C:{CLS}:Mathematics:missing"; two = ready(rows, both(gives(T1), wants(T3, f"C:{CLS}:Mathematics"))); ws = said(given[0], given[2], TEACH, start)
    def solve(m, spec, days, t_, pool, moved, deadline, stats=None, most=None): got = real(m, spec, days, t_, pool, moved, deadline, stats, most); clock.t += 1000; return got
    with swapped(*at(clock), (refit, "solve", solve)):
        p = planned(given, TEACH, start, progress=lambda *a: told.append(a)); assert keys(p) == [TEACH] and p["also"] == [t["text"]] and p["needs"] == [] and p["late"] is False and told == [(1, 2), (2, 2)], (p, told)   # the time is up right after the change that settles it
        p = planned(two, TEACH, miss, start); assert keys(p) == [TEACH] and p["also"] == [t["text"]] and needs(p) == {miss: refit.LATE}, p   # and one that is not settled stays
    with swapped((refit, "_gone", lambda *a: True)): p = refit_plan.plan(*given, {}, ws, budget=0); assert p["also"] == [] and needs(p) == {TEACH: refit.LATE, t["key"]: refit.LATE}, p   # with nothing changed nothing is settled by the list
    with swapped((refit, "_gone", lambda *a: True)): p = refit_plan.plan(*given, {}, made_up(A_), budget=0); assert p["also"] == [] and needs(p) == {A_: refit.LATE}, p   # not even one that step 8 has not on its list
    log, lines = logging.getLogger("refit_plan"), []; keep = logging.Handler(); keep.emit = lines.append; log.addHandler(keep); log.propagate = False
    def broken(m, spec, days, t_, *a):
        if t_["key"] == t["key"]: raise KeyError("x")
        return real(m, spec, days, t_, *a)
    def breaks(m_, sp, dy, w, *a):
        if w["key"] == t["key"]: raise KeyError("x")
        return gone(m_, sp, dy, w, *a)
    try:
        with swapped((refit, "solve", broken)): p = refit_plan.plan(*given, {}, ws); assert keys(p) == [TEACH] and p["also"] == [] and needs(p) == {t["key"]: refit_plan.BROKEN} and len(lines) == 1, p   # one the search broke on stays under Needs you, gone or not
        clock = Clock(); lines.clear()
        with swapped(*at(clock), (refit, "solve", solve), (refit, "_gone", breaks)): p = refit_plan.plan(*given, {}, ws); assert keys(p) == [TEACH] and needs(p) == {t["key"]: refit_plan.BROKEN} and len(lines) == 1, (p, lines)   # a last look that breaks is the target's own: the rest stands
    finally: log.removeHandler(keep); log.propagate = True
    # after a target was taken out of the list as well, and then also that target itself, when the rest settles it
    given = ready([one(1, 0, 1), one(2, 1, 1), one(3, 2, 1)]); end = []
    with played(lambda k, most, n: (TO(1, 2) if k == A_ else TO(2, 2) if k == B_ else None, "x.", 0)), swapped(checked_as(lambda fx_, c_: dict(c_, texts=[]) if fx_ == TO(1, 2) else c_)), swapped((refit, "_gone", lambda m_, sp, dy, w, *a: bool(end) and w["key"] in (A_, C_))):
        p = refit_plan.plan(*given, {}, made_up(*KEYS), progress=lambda done, total: end.append(1) if done == total else None); assert keys(p) == [B_] and p["needs"] == [] and p["also"] == [f"Text of {A_}.", f"Text of {C_}."], p

def test_progress_goes_up_to_the_total():
    told = []; given = ready(BUSY + full(1) + [one(80, 3, 1, "1C", "Mathematics", T3)], both(gives(T1), wants(), lambda s: step5_row(s, TWO_KEYS).update(teachers=[T1, T2]))); m, _, fx = given
    p = planned(given, TEACH, MISS_B, TEACH_C, progress=lambda *a: told.append(a)); assert keys(p) == [MISS_B, TEACH] and needs(p) == {TEACH_C: refit.NOT_ONE} and told == [(1, 3), (2, 3), (3, 3)], (p, told)
    told.clear(); planned(given, TEACH, MISS_B, TEACH_C, progress=lambda *a: told.append(a), budget=0); assert told == [(3, 3)], told   # nothing was looked at
    p, looks, told = play(lambda k, most, n: (None, "x.", 0 if most == 0 else 40)); assert told == [(1, 3), (3, 3)] and needs(p) == {A_: "x.", B_: refit.LATE, C_: refit.LATE}, told   # the time ran out after the first
    p, looks, told = play(lambda k, most, n: (TO(1, 2) if k == A_ else [] if k == C_ else None, "x.", 0)); assert told == [(1, 3), (2, 3), (3, 3)] and keys(p) == [A_] and list(needs(p)) == [B_] and p["also"] == [f"Text of {C_}."], (p, told)   # one is settled and one settled already in the look without moves
    assert [k for k, _, _ in looks] == [A_, B_, C_, B_], looks   # neither is looked at again
    p, *_ = play(lambda k, most, n: (TO(1, 2) if k == A_ and most is None else [] if k == C_ or (k == B_ and most is None) else None, "x.", 0)); assert p["also"] == [f"Text of {B_}.", f"Text of {C_}."], p["also"]   # in the targets' order, not in that they were found settled in
    assert refit_plan.plan(*given, {}, said(m, fx, TEACH, MISS_B), budget=0)["late"] is True   # progress is not needed

def test_one_the_search_breaks_on_needs_you():
    given = ready(BUSY + full(1), both(gives(T1), wants())); lines, was, log = [], refit.solve, logging.getLogger("refit_plan"); tries, looks, told = [], [], []
    class Keep(logging.Handler):
        def emit(self, r): lines.append(r)
    def solve(m, spec, days, t, *a):
        looks.append(t["key"])
        if t["key"] == TEACH: tries.append(a[-1]); raise KeyError(f"{T1} {EL} {CLS}")
        return was(m, spec, days, t, *a)
    keep = Keep(); log.addHandler(keep); log.propagate = False
    try: refit.solve = solve; p = planned(given, TEACH, MISS_B, progress=lambda done, total: told.append((done, len(looks))))
    finally: refit.solve = was; log.removeHandler(keep); log.propagate = True
    assert keys(p) == [MISS_B] and needs(p) == {TEACH: "The app could not work this one out: change it on the board."} and p["late"] is False and tries == [0] and told == [(1, 1), (2, 2)], (p, tries, told)   # it is not tried again, and is done with
    r = lines[0]; assert len(lines) == 1 and r.levelno == logging.ERROR and r.exc_info is None and r.exc_text is None and r.stack_info is None and not any(x in repr((r.getMessage(), r.msg, r.args)) for x in (T1, EL, CLS, TEACH)), vars(r)   # no word of the timetable, and no traceback, which has the error's own words
    at = next(n for n, x in enumerate(open(os.path.abspath(__file__)), 1) if x.strip().startswith('if t["key"] == TEACH: tries.append')); assert "teachers" in r.getMessage() and "KeyError" in r.getMessage() and f"test_refit.py:{at}" in r.getMessage(), r.getMessage()

def test_each_step_is_worded_on_the_timetable_the_earlier_ones_leave():
    p, *_ = play(lambda k, most, n: (TO(1, 2) if k == A_ else TO(1, 3) if k == B_ else TO(3, 2), "x.", 0)); at = lambda d, p_: f"{DAYS[d]} period {p_}"   # (a real list moves no lesson twice)
    assert [(s["n"], s["text"]) for g in p["groups"] for s in g["steps"]] == [(1, f"Move {EL} for {CLS} from {at(0, 1)} to {at(0, 2)}."), (2, f"Move {EL} for {CLS} from {at(0, 2)} to {at(0, 3)}."), (3, f"Move {EL} for {CLS} from {at(2, 1)} to {at(2, 2)}.")] and p["totals"]["moved"] == 2, p

# ------------------------------------------------------------ what a plan never does
def test_a_fix_never_names_a_lesson_the_list_puts_in():
    key = f"C:{CLS_B}:{EL}"; near = next(x["home_room"] for x in SPEC["classes"] if x["class"] == "1C")
    def rooms(s): s["venues"] = [dict(v, capacity=20) if v["room"] in (HOME_B, near) else v for v in s["venues"]] + [dict(room="Combo", kind="classroom", capacity=40, made_of=[HOME_B, near])]
    given = ready([one(1, 0, 1, CLS_B, EL, T0, room=HOME_B)], both(wants(T0, key, 2), rooms)); short_, half = f"dep:{key}:periods", f"dep:{key}:half"   # a lesson more, which is put in 1B's home room: half of a room that seats it
    assert of(planned(given, half), half)[0]["kind"] == "room"   # by itself
    p = planned(given, short_, half); assert of(p, short_) == [dict(ADD_B, key=key)] and needs(p) == {half: refit.NO_FIT} and p["late"] is False, p
    m, spec, days = given[0], given[0]["checked_setup"], given[0]["days"]; now = dict(m, lessons=helper._apply(m["lessons"], p["fixes"], spec, days)["lessons"]); t = refit.targets(said(m, given[2], half))[0]
    got, _ = hunt(now, spec, days, t, []); assert [(f["kind"], f["id"]) for f in got["fixes"]] == [("room", 1), ("room", 2)], got   # the search has an answer, which names it
    for bad in (dict(kind="move", id=9, d=0, p=2), dict(kind="swap", a=1, b=9), dict(kind="swap", a=9, b=1), dict(kind="delete", id=9), dict(kind="room", id=9, group=ENTIRE, room="")):
        p, looks, told = play(lambda k, most, n: ([bad] if k == A_ else None, "x.", 0)); assert p["fixes"] == [] and needs(p) == {A_: refit.NO_FIT, B_: "x.", C_: "x."} and [x[:2] for x in looks if x[0] == A_] == [(A_, 0), (A_, None)] and told[-1] == (3, 3), (bad, p, looks)

def test_a_lesson_put_in_never_has_the_number_of_one_deleted():
    key = f"C:{CLS_B}:{EL}"; over_, short_ = f"dep:{KEY}:periods", f"dep:{key}:periods"; last = dict(one(3, 0, 2), teachers=[])   # 1A has one lesson too many, the last of the list, which nobody teaches; 1B has one too few
    given = ready([one(1, 0, 1), last, one(2, 1, 1, CLS_B, EL, T0)], both(plans(1), wants(T0, key, 2))); none = "clash:noteacher:3:"
    p = planned(given, over_, short_, none); assert keys(p) == [over_, short_] and p["fixes"][0] == dict(kind="delete", id=3) and p["fixes"][1]["kind"] == "add" and p["needs"] == [] and len(p["also"]) == 1 and p["totals"]["moved"] == 0, p

ABC = (TEACH, MISS_B, "dep:C:1C:Other:extra"); FIX = dict(zip(ABC, (GIVE, ADD_B, dict(kind="delete", id=7))))   # three targets that have nothing to do with each other, and the one change of each
def three(**k): return ready([one(1, 0, 1), one(5, 0, 1, CLS_B, "Other", T3), one(7, 2, 1, "1C", "Other", T2)], both(gives(T1), wants()), **k)
def made_in(lessons): return {k for k, yes in zip(ABC, (any(x["id"] == 1 and x["teachers"] == [T1] for x in lessons), any(x["subject"] == "Mathematics" for x in lessons), not any(x["id"] == 7 for x in lessons))) if yes}   # which of the three are made
def test_only_the_answer_at_fault_is_given_up():
    given = three(); m, rec, fx = given; ws = said(m, fx, *ABC); assert keys(planned(given, *ABC)) == list(ABC) and planned(given, *ABC)["fixes"] == [FIX[k] for k in ABC]
    wish = lambda t: dict(state="prefer", steps=[dict(state="prefer", why=t, must=[], prefer=[t])])
    for k in ABC:   # the first, the one in the middle and the last
        def given_up(p): assert keys(p) == [x for x in ABC if x != k] and p["fixes"] == [FIX[x] for x in ABC if x != k] and needs(p) == {k: refit.NO_FIT} and p["late"] is False and p["totals"]["changes"] == 2, (k, p)
        for bad in (dict(state="no", why="No."), dict(state="na", why="No."), wish("A made-up wish. (Prefer)"), dict(texts=[])):   # refused, one that gives up a wish, one that could not be made
            with swapped(checked_as(lambda fx_, c_: dict(c_, **bad) if fx_ == [FIX[k]] else c_)): given_up(refit_plan.plan(*given, {}, ws))
        with swapped(checked_as(lambda fx_, c_: dict(c_, **wish(f"{T2} would have 9 periods, 1{ADD_OK}")) if fx_ == [FIX[k]] else c_)): assert keys(refit_plan.plan(*given, {}, ws)) == list(ABC)   # an allowance is no reason
        swap, progress = open_at_end((k, lambda L: True))
        with swapped(swap): given_up(refit_plan.plan(*given, {}, ws, progress=progress))   # one that is not settled
        mine = lambda made: k in made
        with swapped(listing(mine, k, "deployment", "x")): given_up(refit_plan.plan(*given, {}, ws))   # one that step 8 lists still
        for crit in ("room", "break"):
            with swapped(listing(mine, "clash:made up", "clash", "x", crit=crit)): given_up(refit_plan.plan(*given, {}, ws))   # a new mistake
        for x in (("rule:0:x", "rule", "x"), ("bands:beside:x", "clash", "x"), ("typed:1:none", "typed", "x")):
            with swapped(listing(mine, *x, strength="Prefer")): given_up(refit_plan.plan(*given, {}, ws))   # a new wish
        for x, strength in ((("clash:made up", "clash", "x"), "Must"), (("room:none:5:x", "room", "x"), "Prefer"), (("typed:1:again", "typed", "x"), "Prefer"), (("typed:12:again#2", "typed", "x"), "Prefer")):
            with swapped(listing(mine, *x, strength=strength)): assert keys(refit_plan.plan(*given, {}, ws)) == list(ABC), x   # neither a mistake nor a wish that counts
        with swapped(listing(mine, "rule:0:x", "rule", "x", strength="Prefer")): assert keys(refit_plan.plan(*given, {"rule:0:x": dict(answer="step5")}, ws)) == list(ABC)   # nor one that is answered
        with swapped(listing(lambda made: True, "rule:0:x", "rule", "x", strength="Prefer")): assert keys(refit_plan.plan(*given, {}, ws)) == list(ABC)   # nor one that is there before
        with swapped(listing(lambda made: True, "rule:0:x", "rule", "x", strength="Prefer")):
            with swapped(listing(mine, "rule:0:x#2", "rule", "x", strength="Prefer")): assert keys(refit_plan.plan(*given, {}, ws)) == list(ABC)   # a second line of what is there before is none

def test_a_mistake_brought_is_not_made_good_by_one_settled():
    rows = [one(1, 0, 1), one(2, 2, 1, "1C", EL, T2), one(3, 2, 1, "1B", EL, T2)]; given = ready(rows, both(gives(T1), gives(T2, f"C:1C:{EL}"))); m, rec, fx = given; clash = "clash:Teacher double-booked: "
    with swapped(listing(lambda made: TEACH in made, "clash:made up", "clash", "x", crit="teacher")):   # the list settles one and the teacher change brings another: as many as before
        p = refit_plan.plan(*given, {}, said(m, fx, TEACH, clash)); assert needs(p) == {TEACH: refit.NO_FIT} and len(p["groups"]) == 1 and p["groups"][0]["kind"] == "clash" and p["totals"]["critical"] == [1, 0], p

def test_a_mistake_settled_on_the_way_is_not_brought_back():
    given = three(); m, rec, fx = given; ws = said(m, fx, *ABC); there = lambda made: TEACH not in made or ABC[2] in made   # there before, gone with the teacher change, and back with the deletion
    with swapped(listing(there, "clash:made up", "clash", "x", crit="room")):
        assert keys(refit_plan.plan(*given, {}, ws)) == list(ABC)   # the list as a whole has no mistake that was not there
        with swapped(checked_as(lambda fx_, c_: dict(c_, texts=[]) if fx_ == [ADD_B] else c_)): p = refit_plan.plan(*given, {}, ws); assert keys(p) == [TEACH] and needs(p) == {MISS_B: refit.NO_FIT, ABC[2]: refit.NO_FIT}, p   # but when the answers are gone through, each is asked of what the one before it left

def test_what_is_new_on_a_list_is_told():
    def crit(*rows, change=None): m_, rec_, fx_ = ready(list(rows), change); return refit_plan._mistakes(m_, said(m_, fx_))
    late = [(CLS_B, T1), ("1C", T2), ("1D", T3)]; cells = lambda kind, who, *qs: {(kind, who, 1, q) for q in qs}   # a lesson of three periods of Tuesday, and three of one beside it, in one line, then without the one in the middle in two: the periods are what counts
    for kind, who, long_, short_ in (("teacher", T0, one(1, 1, 1, CLS, "Mathematics", T0, n=3), [one(2 + i, 1, 1 + i, cls, EL, T0) for i, (cls, _) in enumerate(late)]), ("class", CLS, one(1, 1, 1, CLS, "Mathematics", T0, n=3), [one(2 + i, 1, 1 + i, CLS, EL, t) for i, (_, t) in enumerate(late)]),
                                     ("room", "1-01", one(1, 1, 1, CLS, "Mathematics", T0, n=3, room="1-01"), [one(2 + i, 1, 1 + i, cls, EL, t, room="1-01") for i, (cls, t) in enumerate(late)])):
        assert crit(long_, *short_) == cells(kind, who, 1, 2, 3) and crit(long_, short_[0], short_[2]) == cells(kind, who, 1, 3), (kind, crit(long_, *short_))
    assert crit(dict(one(1, 1, 1), teachers=[])) == {("noteacher", f"clash:noteacher:1:{ENTIRE}")}; two = crit(one(1, 0, 0), one(2, 0, 0, CLS_B, EL, T1)); assert len(two) == 1 and next(iter(two))[0] == "break" and "#" not in next(iter(two))[1]   # any other by its key, without its number
    double = lambda s: s["school"].update(extra_settings=list(s["school"].get("extra_settings") or []) + [["Teachers may take two lessons at once on", DAYS[1]]]); assert crit(one(1, 1, 1), one(2, 1, 1, CLS_B), change=double) == set()   # what is no mistake is none
    w = lambda key, kind="rule", strength="Prefer", decision=None, **k: dict(verify.warning(key, kind, "x", strength=strength, **k), decision=decision); at_ = lambda i, p_: dict(cls=CLS, day=DAYS[0], period=p_, id=i, row=ENTIRE); wishes = refit_plan._wishes
    assert wishes([w("rule:r1:a|0|1", where=at_(1, 1))]) == wishes([w("rule:r1:a|0|5#2", where=at_(1, 5))]) != wishes([w("rule:r1:a|0|1", where=at_(2, 1))]) and wishes([w("rule:r1:a|0|1", where=at_(1, 1))]) != wishes([w("rule:r2:a|0|1", where=at_(1, 1))])   # a rule and a lesson, wherever it is
    assert wishes([w("rule:r1:a|0")]) == wishes([w("rule:r1:a|0#3")]) != wishes([w("rule:r1:a|1")]) and wishes([w("bands:beside:0:X:Y", "clash")]) == wishes([w("bands:beside:0:X:Y#2", "clash")]) == {"bands:beside:0:X:Y"}
    assert wishes([w("rule:r1:a|0", strength="Must"), w("rule:r1:a|0", decision=dict(answer="step5")), w("room:none:1:x", "room"), w("typed:1:again#2", "typed")]) == set()
    on, t = refit_plan._on, w("clash:x", "clash", where=at_(1, 1)); assert on(t, [t]) and on(t, [dict(t, key="clash:x#2")]) and on(dict(t, key="clash:x#2"), [t]) and not on(t, [dict(t, key="clash:y")]) and not on(t, [dict(t, where=at_(2, 1))]) and not on(t, [])   # the same line of another lesson is another
    d = w("dep:C:1A:x:teachers", "deployment", where=at_(1, 1)); assert on(d, [dict(d, where=at_(9, 2))]) and not on(d, [dict(d, key="dep:C:1A:x:periods")])   # a difference from step 5 is itself wherever its first lesson is

def test_a_line_that_comes_in_two_is_no_new_mistake():
    # T0 is in two places for three periods of Tuesday: a lesson of 1A, and three of 1B, 1C and 1D. Step 5 gives the one in the middle to T2
    key = f"C:1C:{EL}"; teach = f"dep:{key}:teachers"; rows = [one(1, 1, 1, CLS, "Mathematics", T0, n=3), one(2, 1, 1, CLS_B, EL, T0), one(3, 1, 2, "1C", EL, T0), one(4, 1, 3, "1D", EL, T0), one(9, 3, 1, "1C", "Other", T3), one(10, 3, 2, "1C", "Other2", T3)]
    given = ready(rows, gives(T2, key)); p = planned(given, teach); assert keys(p) == [teach] and p["needs"] == [] and p["totals"]["critical"] == [1, 2], p   # "(periods 1-3)" becomes two lines of one period
    p = planned(given, teach, "dep:C:1C:Other"); assert len(p["groups"]) == 3 and p["needs"] == [], p
    lines = [w["text"] for w in said(given[0], given[2], "clash:Teacher double-booked")]; assert len(lines) == 1 and "(periods 1-3)" in lines[0]

def test_what_hangs_on_an_answer_at_fault_is_judged_again():
    # the missing lesson of 1B fits once the extra one is deleted; the teacher change has nothing to do with them
    rows = [x for d in range(5) for x in full(*([2] if d == 0 else []), d=d, cls=CLS_B)] + [one(2, 0, 2, CLS_B, "Other", T0), one(1, 3, 1)]; extra = f"dep:C:{CLS_B}:Other:extra"; given = ready(rows, both(gives(T1), wants())); m, rec, fx = given
    assert keys(planned(given, TEACH, MISS_B, extra)) == [TEACH, extra, MISS_B]
    with swapped(checked_as(lambda fx_, c_: dict(c_, state="no", why="No.") if fx_[0]["kind"] == "delete" else c_)): p = refit_plan.plan(*given, {}, said(m, fx, TEACH, MISS_B, extra)); assert keys(p) == [TEACH] and needs(p) == {MISS_B: refit.NO_FIT, extra: refit.NO_FIT}, p
    swap, progress = open_at_end((extra, lambda L: any(x["subject"] == "Mathematics" for x in L)))   # the same when it is found at fault only with all of them made
    with swapped(swap): p = refit_plan.plan(*given, {}, said(m, fx, TEACH, MISS_B, extra), progress=progress); assert keys(p) == [TEACH] and needs(p) == {MISS_B: refit.NO_FIT, extra: refit.NO_FIT}, p

def test_the_going_through_has_a_time_of_its_own():
    given = three(); m, rec, fx = given; ws = said(m, fx, *ABC); fault = checked_as(lambda fx_, c_: dict(c_, texts=[]) if fx_ == [FIX[ABC[2]]] else c_); assert TIMES == (30.0, 2.0, 10.0)
    with swapped(fault, (refit_plan, "SIFT_S", 0)): p = refit_plan.plan(*given, {}, ws); assert p["fixes"] == [] and needs(p) == {k: refit.LATE for k in ABC} and p["late"] is True, p   # nothing was gone through
    clock, real = Clock(), draft.listed
    def listed(*a): clock.t += 6; return real(*a)
    with swapped(fault, *at(clock), (draft, "listed", listed), (refit_plan, "SIFT_S", 10.0)): p = refit_plan.plan(*given, {}, ws); assert keys(p) == list(ABC[:2]) and needs(p) == {ABC[2]: refit.LATE} and p["late"] is True, p   # ten seconds: two of the three
    first = checked_as(lambda fx_, c_: dict(c_, texts=[]) if fx_ == [FIX[ABC[0]]] else c_); clock = Clock()
    with swapped(first, *at(clock), (draft, "listed", listed), (refit_plan, "SIFT_S", 10.0)): p = refit_plan.plan(*given, {}, ws); assert keys(p) == list(ABC[1:]) and needs(p) == {ABC[0]: refit.NO_FIT}, p   # one that is refused costs no listing

def test_the_list_offered_always_holds():
    given = three(); m, rec, fx = given; ws = said(m, fx, *ABC); made = lambda *which: lambda L: made_in(L) >= set(which)
    swap, progress = open_at_end((ABC[0], made(ABC[2])))   # settled as each is gone through, and open again with the last: it is the one named
    with swapped(swap): p = refit_plan.plan(*given, {}, ws, progress=progress); assert keys(p) == list(ABC[1:]) and needs(p) == {ABC[0]: refit.NO_FIT}, p
    swap, progress = open_at_end((ABC[0], made(ABC[2])), (ABC[1], lambda L: ABC[2] in made_in(L) and ABC[0] not in made_in(L)))   # and with that one out another is: nothing is offered
    with swapped(swap): p = refit_plan.plan(*given, {}, ws, progress=progress); assert p["fixes"] == [] and needs(p) == {k: refit.NO_FIT for k in ABC} and p["totals"]["changes"] == 0, p

def test_what_a_dropped_target_had_settled_needs_you_again():
    rows = [one(1, 0, 1), one(3, 0, 1, CLS_B, "Other", T0)]; clash = "clash:Teacher double-booked: "
    given = ready(rows, gives(T1)); ws = said(given[0], given[2], TEACH, clash); key = refit.targets(said(given[0], given[2], clash))[0]["key"]; assert planned(given, TEACH, clash)["also"]
    two = ready(rows, both(gives(T1), wants())); gone, end = refit._gone, []
    with swapped(checked_as(lambda fx_, c_: dict(c_, state="no", why="No.") if fx_ == [GIVE] else c_)): p = refit_plan.plan(*given, {}, ws); assert p["fixes"] == p["also"] == [] and needs(p) == {TEACH: refit.NO_FIT, key: refit.NO_FIT}, p
    with swapped(checked_as(lambda fx_, c_: dict(c_, texts=[]) if fx_[0]["kind"] == "add" else c_)): p = planned(two, TEACH, MISS_B, clash); assert keys(p) == [TEACH] and len(p["also"]) == 1 and needs(p) == {MISS_B: refit.NO_FIT}, p   # what the rest of the list settles stays
    # one that is open again at the end, though it was settled when it was looked at, needs you; no answer is given up for it
    with swapped((refit, "_gone", lambda *a: gone(*a) and not end)): p = refit_plan.plan(*two, {}, said(two[0], two[2], TEACH, MISS_B, clash), progress=lambda done, total: end.append(1) if done == total else None); assert keys(p) == [TEACH, MISS_B] and p["also"] == [] and needs(p) == {key: refit.NO_FIT}, p
    with swapped(listing(lambda made: True, key, "clash", "x", where=dict(teacher=T0))): p = refit_plan.plan(*given, {}, ws); assert keys(p) == [TEACH] and needs(p) == {key: refit.NO_FIT}, p   # nor one that step 8 lists still

def test_two_warnings_that_read_the_same_are_told_apart():
    rows = [one(1, 0, 0), one(2, 0, 0, CLS_B)] + full(cls=CLS_B, start=2000); given = ready(rows); m, rec, fx = given; a, b = [w["key"] for w in said(m, fx, f"clash:{EL} ")]; assert b == a + "#2"   # both sit in the assembly; 1B's lesson has nowhere to go
    p = planned(given, f"clash:{EL} "); assert keys(p) == [a] and needs(p) == {b: refit.NO_FIT} and [w["key"] for w in said(m, fx, f"clash:{EL} ")] == [a, b], p   # (the one left is listed with the first one's key then)

def test_a_class_name_with_a_colon_breaks_nothing():
    # "1:A" has keys that cannot be read apart (nowhere in the app): what is asked of them is never an error, and they are not said to be settled
    name = "1:A"; key = f"C:{name}:{EL}"
    def change(s):
        r = copy.deepcopy(step5_row(s)); r.update(classes=[name], teachers=[T1], periods=2, length=1); s["lessons"].append(r); gives(T1)(s); s["classes"].append(dict(next(x for x in s["classes"] if x["class"] == CLS), **{"class": name}))
    given = ready([one(1, 0, 1), one(2, 0, 2, name, EL, T0)], change); m, rec, fx = given; ws = said(m, fx, TEACH, f"dep:{key}:"); assert len(ws) == 3
    p = refit_plan.plan(*given, {}, ws); assert keys(p) == [TEACH] and p["also"] == [] and set(needs(p)) == {f"dep:{key}:teachers", f"dep:{key}:periods"} and refit_plan.BROKEN not in needs(p).values(), p
    p = refit_plan.plan(*given, {}, ws, budget=0); assert set(needs(p).values()) == {refit.LATE} and p["also"] == [], p

# ------------------------------------------------------------ a step 5 row with nobody on it
def test_a_lesson_nobody_would_teach_is_not_added():
    nobody = lambda key=MATHS_B, n=1: both(plans(n, 1, key), lambda s: step5_row(s, key).update(teachers=[])); other = "dep:C:1C:Other:extra"
    p = planned(ready([one(5, 0, 1, CLS_B, "Other", T3)], nobody()), MISS_B); assert p["fixes"] == [] and needs(p) == {MISS_B: "Step 5 has no teacher for it: choose one there first, then run Re-fit again."} and refit.NO_STAFF in needs(p).values(), p
    p = planned(ready(BUSY + full(1) + [one(7, 2, 1, "1C", "Other", T2)], both(gives(T1), nobody())), TEACH, MISS_B, other); assert keys(p) == [other, TEACH] and needs(p) == {MISS_B: refit.NO_STAFF} and p["totals"]["critical"][0] == p["totals"]["critical"][1], p   # the others stand
    p = planned(ready([one(1, 0, 1), one(3, 0, 1, "1C", EL, T0)], nobody()), MISS_B, "clash:Teacher"); assert [g["kind"] for g in p["groups"]] == ["clash"] and needs(p) == {MISS_B: refit.NO_STAFF} and p["totals"]["critical"] == [1, 0], p   # nor beside a mistake that is settled
    bare = dict(one(1, 0, 1), teachers=[]); p = planned(ready([bare, one(7, 2, 1, "1C", "Other", T2)], nobody(KEY, 2)), SHORT, other); assert keys(p) == [other] and needs(p) == {SHORT: refit.NO_STAFF}, p   # nor a period more of one nobody teaches
    p = planned(ready([bare, dict(one(4, 1, 1), teachers=[])], nobody(KEY, 1)), SHORT); assert [f["kind"] for f in p["fixes"]] == ["delete"], p   # (one too many may go)
    given = ready([one(1, 0, 1)], nobody(KEY, 2)); text = said(given[0], given[2], TEACH)[0]["text"]; p = planned(given, TEACH, SHORT); assert needs(p) == {TEACH: text, SHORT: refit.NO_STAFF} and p["fixes"] == [], p   # it does not wait for a change that step 5 does not name

# ------------------------------------------------------------ the tags and the numbers
def words(scope, target, strength="Must"): return dict(scope=scope, target=target, rule="In words", text="made-up words", strength=strength)
def line(n, result="Met"): return dict(no=n, result=result)

def test_typed_rules_are_flagged():
    given = ready(BUSY + full(1), both(gives(T1), wants()), rules=[words("Class", CLS_B), words("Teacher", T1, "Prefer"), words("Class", "1C"), words("Class", CLS), words("School", "Whole school")], report=[line(1), line(2, "Partly"), line(3), line(4, "Not met"), line(5, "Met")])
    p = planned(given, TEACH, MISS_B); tags = [s["tags"] for g in p["groups"] for s in g["steps"]]
    assert tags == [["check T1 again", "check T5 again"], ["check T1 again", "check T2 again", "check T5 again"], ["check T2 again", "check T5 again"]] and p["totals"]["typed"] == [1, 2, 5], (tags, p["totals"])   # the add is 1B's; the move is of T1's lesson of 1B; the change gives T1 a lesson of 1A; T4 is not reported met
    assert p["totals"]["warnings"][1] == p["totals"]["warnings"][0] - 2, p["totals"]   # the rules to check again are not in the number after
    m, rec, fx = given; done = dict(fx, touched={2}); assert [w["key"] for w in said(m, done) if again(w)] == ["typed:1:again", "typed:2:again", "typed:5:again"]   # 1B's lesson was moved on the board: these are open already
    p = planned((m, rec, done), TEACH, MISS_B); assert p["totals"]["warnings"][1] == p["totals"]["warnings"][0] - 2 and p["totals"]["typed"] == [1, 2, 5], p["totals"]   # so they count before and after
    p = planned((m, rec, done), TEACH, MISS_B, decisions={"typed:1:again": dict(answer="met")}); assert p["totals"]["warnings"][1] == p["totals"]["warnings"][0] - 2, p["totals"]   # one that is answered counts in neither
    given = ready([one(2, 0, 1, CLS_B, "Other", T0)], rules=[words("Class", CLS_B)], report=[line(1)]); m, rec, fx = given; put = dict(fx, touched={2}); p = planned((m, rec, put), f"dep:C:{CLS_B}:Other:extra"); assert [f["kind"] for f in p["fixes"]] == ["delete"] and [w["key"] for w in said(m, put) if again(w)] == ["typed:1:again"], p   # one put in on the board, which the list deletes: its rule is to be checked again all the same (planned counts it so)
    given = ready([one(1, 0, 1), one(15, 2, 1, "1C", "Other", T2)], gives(T1), rules=[words("Class", "1C")], report=[line(1)]); m, rec, fx = given   # one that was changed on the board and that the list leaves alone: open before and after, and none of the list's
    for edited in (dict(fx, touched={15}), dict(fx, was=[dict(m["lessons"][1], id=16)])):
        p = planned((m, rec, edited), TEACH); assert [w["key"] for w in said(m, edited) if again(w)] == ["typed:1:again"] and p["totals"]["typed"] == [] and p["totals"]["warnings"][1] == p["totals"]["warnings"][0] - 1, p["totals"]
    not_then = dict(scope="Class", target=CLS, rule="Not in periods", week="Both", day="All", strength="Must", **{"from": 1, "to": 1}); given = ready([one(1, 0, 1)], gives(T1), rules=[not_then, words("Teacher", T1), words("Teacher", T0)], report=[line(1), line(2)]); p = planned(given, TEACH, "rule:")
    assert [(f["kind"], s["tags"]) for g in p["groups"] for s in g["steps"] for f in [s["fix"]]] == [("teacher", ["check T1 again", "check T2 again"]), ("move", ["check T1 again"])], p   # each step by itself, on the timetable the earlier ones leave: the lesson is T1's when it moves
    given = ready([one(1, 0, 1), one(2, 0, 1, "1C", SUBJ2, T1)] + full(1), both(gives(T1), wants()), rules=[words("Class", CLS_B)], report=[line(1)]); p = planned(given, TEACH, MISS_B); assert keys(p) == [MISS_B, TEACH] and p["totals"]["typed"] == [1], p   # what an answer before the last put in counts as well
    gone = words("Teacher", T0); given = ready([one(1, 0, 1)], gives(T1), rules=[gone], report=[line(1)]); p = planned(given, TEACH); assert p["groups"][0]["steps"][0]["tags"] == ["check T1 again"], p   # the teacher who had it

def test_another_day_and_no_room_are_flagged():
    given = ready([one(1, 0, 1)], rules=[AWAY(T0), words("Class", CLS)], report=[line(1)]); p = planned(given, "rule:")
    assert p["groups"][0]["steps"][0]["tags"] == ["another day", "check T1 again"] and p["totals"]["moved"] == p["totals"]["another_day"] == 1, p
    given = ready([one(1, 0, 1), one(2, 1, 1)], rules=[AWAY(T0), AWAY(T0, 1, 1, 1)]); p = planned(given, "rule:"); assert sorted(s["tags"] for g in p["groups"] for s in g["steps"]) == [[], ["another day"]] and p["totals"]["moved"] == 2 and p["totals"]["another_day"] == 1, p
    given = ready([], both(wants(), lambda s: step5_row(s, MATHS_B).update(room_kind="planetarium")), rules=[words("Class", CLS_B)], report=[line(1)]); p = planned(given, MISS_B)   # no room is of that kind
    assert p["fixes"] == [dict(ADD_B, d=0, p=1, room="")] and p["groups"][0]["steps"][0]["tags"] == ["no room", "check T1 again"] and p["totals"]["warnings"][0] == p["totals"]["warnings"][1], p   # one warning fewer (it was missing) and one more (it has no room)

def test_a_swap_moves_two_and_a_deleted_lesson_moves_none():
    rows = BUSY + full(1) + [one(3, 0, 2, CLS_B, "Mathematics", T2), one(7, 3, 1, "1C", "Other", T2)] + full(1, 2, cls=CLS_B, start=2000); extra = "dep:C:1C:Other:extra"
    p = planned(ready(rows, gives(T1)), TEACH, extra); assert p["fixes"] == [dict(kind="delete", id=7), dict(kind="swap", a=2, b=3), GIVE] and p["totals"]["moved"] == 2 and p["totals"]["another_day"] == 0 and p["totals"]["changes"] == 3, p

def test_a_mistake_settled_is_one_critical_less():
    given = ready(TWICE); p = planned(given, "clash:"); assert len(p["fixes"]) == 1 and p["totals"]["critical"] == [1, 0], p   # the clashes after are the new timetable's, not the old one's
    given[0]["choice_problems"] = ["A made-up second choice."]; given[0]["checks"]["problems"].append("A made-up second choice."); n = draft.counts(*given, {})   # as the draft's model says one: a warning before and after, and no clash
    p = planned(given, "clash:Teacher"); assert p["totals"]["critical"] == [1, 0] and p["totals"]["warnings"] == [n["warnings"]] * 2, p
    given = ready([one(1, 0, 1), one(2, 0, 2, CLS_B, "Other", T0), one(6, 2, 1)], gives(T1), lifted={6}); p = planned(given, TEACH); assert keys(p) == [TEACH] and p["totals"]["critical"] == [1, 1], p   # one waits in Not placed: a mistake before and after

# ------------------------------------------------------------ on a draft
def a_draft():
    """a draft with edits made to it and a setup that does not agree with it: (model, rec, fx, its meta.json, its decisions.json); step 5 has five rows"""
    s = json.loads(json.dumps(store.setup_record()["spec"])); row = lambda k, *v: dict(next(r for r in s["lessons"] if r["subject"] == k[1] and k[0] in r["classes"] and r.get("code") == ENTIRE), periods_override=v[0], teachers=[v[1]])
    s["school"]["lesson_length"] = 1; s["lessons"] = [row((CLS, EL), 1, T1), row((CLS, "Mathematics"), 2, T0), row((CLS_B, EL), 2, T0), row((CLS_B, "Mathematics"), 2, T2), row(("1C", EL), 2, T2)]
    s["rules"] = [words("Class", CLS_B), words("Class", CLS), dict(AWAY(T2, 3), note="away")]; put_setup(s)
    rows = BUSY + full(1) + [one(5, 1, 2, CLS_B, "Mathematics", T2), one(6, 3, 2, CLS_B, "Mathematics", T2), one(7, 2, 1, CLS, "Mathematics", T0), one(8, 2, 2, CLS, "Mathematics", T0), one(9, 2, 3, CLS, "Mathematics", T0),
        one(20, 4, 1, "1C", EL, T2), one(21, 4, 2, "1C", EL, T2), one(30, 4, 3, "9Z", EL, T2), dict(one(31, 4, 5, "9Z", EL, T2), teachers=[]), one(5000, 4, 6, "9Z", EL, T0)]   # the last is the highest number of the file
    save_draft(rows, report=[(1, "Must", CLS_B, "made-up words", "Met", ""), (2, "Must", CLS, "made-up words", "Met", "")])
    draft.fix(dict(kind="delete", id=5000)); draft.fix(dict(kind="move", id=5, d=1, p=3)); draft.fix(dict(kind="lift", id=21)); draft.fix(dict(kind="room", id=20, group=ENTIRE, room="1-03"))
    draft.decide("typed:1:again", "met"); m, rec, fx = draft.model_now(); read = lambda n: store.read_json(os.path.join(draft.DIR, n)); return m, rec, fx, read("meta.json"), read("decisions.json")

def test_counts_before_and_after():
    was = json.loads(json.dumps(store.setup_record()["spec"]))
    try:
        m, rec, fx, meta, decisions = a_draft(); assert len(meta["fixes"]) == 4 and [k for k, v in decisions.items()] == ["typed:1:again"] and fx["pool"] and m["rule_report"]
        p = planned((m, rec, fx), decisions=decisions); kinds = {g["kind"] for g in p["groups"]}; assert p["stamp"] == draft.stamp() == c.get("/api/draft").get_json()["stamp"]
        assert kinds >= {"teachers", "missing", "periods", "extra", "rule"} and p["needs"] and {f["kind"] for f in p["fixes"]} >= {"teacher", "move", "add", "delete"} and p["totals"]["another_day"] >= 1 and p["totals"]["typed"] == [1, 2], (kinds, p["fixes"], p["needs"], p["totals"])
        m2, _, fx2 = draft._model_of(draft.paths(), dict(meta, fixes=meta["fixes"] + p["fixes"]), rec); assert not fx2["problems"] and len(fx2["texts"]) == len(meta["fixes"]) + len(p["fixes"])   # the draft as Apply would leave it
        one_, two = draft.counts(m, rec, fx, decisions), draft.counts(m2, rec, fx2, decisions); new = [w["key"] for w in opened(said(m2, fx2, decisions=decisions)) if again(w)]; assert new == ["typed:2:again"] and not [w for w in opened(said(m, fx, decisions=decisions)) if again(w)], new
        assert p["totals"]["critical"] == [one_["critical"], two["critical"]] and p["totals"]["warnings"] == [one_["warnings"], two["warnings"] - 1] and two["critical"] < one_["critical"], (p["totals"], one_, two)
        c_ = helper.chain(m, m["checked_setup"], m["days"], p["fixes"]); first = {x["id"] for x in m["lessons"]}; plain = lambda L: [dict(x, id=x["id"] if x["id"] in first else "new") for x in L]
        assert plain(c_["lessons"]) == plain(m2["lessons"]) and {x["id"] for x in m2["lessons"]} != {x["id"] for x in c_["lessons"]}   # row for row (Apply numbers the added ones from the file's highest)
    finally: put_setup(was)

def test_a_lesson_not_placed_that_a_teacher_change_reaches_is_flagged():
    was = json.loads(json.dumps(store.setup_record()["spec"]))
    try:   # two lessons of 1A's English, one of them waiting in Not placed, in 1-03, which a typed rule is about (met, and answered so after the lift); step 5 gives the English to T1
        s = json.loads(json.dumps(was)); row = dict(next(r for r in s["lessons"] if r["subject"] == EL and CLS in r["classes"] and r.get("code") == ENTIRE), periods_override=2, teachers=[T1])
        s["school"]["lesson_length"] = 1; s["lessons"] = [row]; s["rules"] = [words("Room", "1-03"), words("Room", "1-02")]; put_setup(s)
        save_draft([one(1, 0, 1, room="1-01"), one(9, 2, 1, room="1-03"), one(5, 3, 1, "1C", "Other", T2, room="1-03")], report=[(1, "Must", "", "made-up words", "Met", ""), (2, "Must", "", "made-up words", "Met", "")])
        draft.fix(dict(kind="lift", id=9)); draft.decide("typed:1:again", "met"); m, rec, fx = draft.model_now(); read = lambda n: store.read_json(os.path.join(draft.DIR, n)); meta, decisions = read("meta.json"), read("decisions.json")
        ws = [w for w in c.get("/api/draft").get_json()["warnings"] if w["key"] == TEACH]; p = refit_plan.plan(m, rec, fx, decisions, ws); step = p["groups"][0]["steps"]; assert [x["fix"] for x in step] == [GIVE] and step[0]["tags"] == ["check T1 again"] and p["totals"]["typed"] == [1], p
        base = draft._model_of(draft.paths(), meta, rec)[2]; m2, _, fx2 = draft._model_of(draft.paths(), dict(meta, fixes=meta["fixes"] + p["fixes"]), rec)   # as Apply makes it
        assert [w["key"] for w in verify.typed_again(m2, m2["checked_setup"], fx2["touched"] - base["touched"], fx2["was"][len(base["was"]):])] == ["typed:1:again"]
    finally: put_setup(was)
    # one that waits and is of two classes is changed twice: each step is flagged for the lesson as it is then
    shared = dict(one(9, 2, 1), classes=[CLS, CLS_B]); key_b = f"C:{CLS_B}:{EL}"; given = ready([one(1, 0, 1), one(2, 1, 1, CLS_B), shared], both(gives(T1), gives(T2, key_b)), rules=[words("Teacher", T1)], report=[line(1)], lifted={9})
    p = planned(given, TEACH, f"dep:{key_b}:teachers"); assert [s_["tags"] for g in p["groups"] for s_ in g["steps"]] == [["check T1 again"]] * 2, p
    # the rows that wait, as they are just before each change
    spec = dict(SPEC_CHECKED, rules=[words("Teacher", x) for x in (T0, T1, T2, T3)]); m = case([])[0]; m["rule_report"] = [line(n) for n in (1, 2, 3, 4)]; wait = lambda i, cls, t: dict(id=i, d=0, p=1, n=1, level=LEVEL, block="", classes=list(cls), subject=EL, group=ENTIRE, teachers=[t], room="", ext=False, rain="")
    give = lambda cls, t: dict(kind="teacher", key=f"C:{cls}:{EL}", teachers=[t]); again_for = lambda pool, *fx_: refit.rechecked(dict(m, pool=pool), spec, [], set(), [], list(fx_)); before = wait(9, [CLS], T0)
    assert again_for([], give(CLS, T1)) == [] and again_for([before], give(CLS, T1)) == [1] and again_for([before], give(CLS_B, T1)) == [] and again_for([before], dict(kind="move", id=9, d=0, p=2)) == []
    assert again_for([wait(9, [CLS, CLS_B], T0)], give(CLS, T1), give(CLS_B, T2)) == [1, 2] and before == wait(9, [CLS], T0)   # one of two classes is changed twice: T0 had it, then T1

def test_the_plan_changes_nothing():
    was = json.loads(json.dumps(store.setup_record()["spec"]))
    try:
        m, rec, fx, meta, decisions = a_draft(); files = lambda: {n: open(os.path.join(draft.DIR, n), "rb").read() for n in sorted(os.listdir(draft.DIR))}; info = c.get("/api/draft").get_json(); kept = files(), copy.deepcopy([draft._cache["m"], draft._cache["fx"], rec, info["warnings"]])
        assert draft._cache["m"] is m and draft._cache["fx"] is fx and {"meta.json", "decisions.json"} <= set(kept[0])
        p = refit_plan.plan(m, rec, fx, decisions, info["warnings"]); assert p["fixes"] and draft._cache["m"] is m
        assert files() == kept[0] and [draft._cache["m"], draft._cache["fx"], rec, info["warnings"]] == kept[1] and store.read_json(os.path.join(draft.DIR, "decisions.json")) == decisions and c.get("/api/draft").get_json() == info
    finally: put_setup(was)

# ----------------------------------------------------------------------------------------------- the job, the apply and the preview
import threading  # noqa: E402
import versions  # noqa: E402
REFIT_STALE = "The draft changed since this list was made. Run Re-fit again."
REFIT_GONE = "That re-fit list is gone. Run Re-fit again."

@contextlib.contextmanager
def scene(rows=None, rules=(), report=(), lifted=None, decide=None):
    """a setup whose one lesson (1A's English) is taught by T1, against a draft that has T0 teach it: step 8 says the teachers differ, and a re-fit gives it to T1.
    lifted: a lesson put in Not placed first; decide: a typed rule decided "met" at that point. The setup is put back after, and the job with it"""
    was = json.loads(json.dumps(store.setup_record()["spec"])); s = json.loads(json.dumps(was))
    row = dict(next(r for r in s["lessons"] if r["subject"] == EL and CLS in r["classes"] and r.get("code") == ENTIRE), periods_override=1, teachers=[T1])
    s["school"]["lesson_length"] = 1; s["lessons"] = [row]; s["rules"] = list(rules)
    try:
        put_setup(s); save_draft(rows or [one(1, 0, 1)], report=report); A._refit_clear()
        if lifted: draft.fix(dict(kind="lift", id=lifted))
        if decide: draft.decide(decide, "met")
        yield
    finally:
        job = A.REFIT.get("thread")
        if job: job.join(60)
        A._refit_clear(); put_setup(was)

def poll(limit=60):
    """the answer of GET once the job is done or failed (polled, up to limit seconds)"""
    end = time.monotonic() + limit
    while time.monotonic() < end:
        r = c.get("/api/draft/refit").get_json()
        if r["state"] in ("done", "failed", "idle"): return r
        time.sleep(0.02)
    raise AssertionError("the job did not finish")

def run_job():
    r = c.post("/api/draft/refit"); assert r.status_code == 200 and r.get_json()["started"] is True, r.get_json()
    got = poll(); assert got["state"] == "done" and got["id"] == r.get_json()["id"], got; return got

def read(name): return open(os.path.join(draft.DIR, name), "rb").read()
def fixes_now(): return store.read_json(os.path.join(draft.DIR, "meta.json"))["fixes"]

def test_refit_needs_the_committee():
    with scene():
        for r in (NOSE.post("/api/draft/refit"), NOSE.get("/api/draft/refit"), NOSE.get("/api/draft/refit/preview?id=x"), NOSE.post("/api/draft/refit/apply", json=dict(id="x"))): assert r.status_code == 401, r.status_code
        assert A.REFIT["state"] == "idle"

def test_nothing_to_refit_is_refused():
    with scene(rows=[one(1, 0, 1, teacher=T1)]):   # taught as step 5 says
        assert not refit.needed(c.get("/api/draft").get_json()["warnings"])
        r = c.post("/api/draft/refit"); assert r.status_code == 400 and r.get_json() == dict(error="Nothing to re-fit: the timetable fits the setup."), r.get_json()
        assert c.get("/api/draft/refit").get_json() == dict(state="idle") and A.REFIT["state"] == "idle"
        assert c.post("/api/draft/refit/apply", json=dict(id="x")).status_code == 404

def test_no_draft_and_no_setup_say_so():
    with scene():
        os.rename(draft.DIR, draft.DIR + ".away")
        try:
            r = c.post("/api/draft/refit"); assert r.status_code == 404 and r.get_json() == dict(error="There is no draft."), r.get_json()
            assert c.get("/api/draft/refit").get_json() == dict(state="idle")
        finally: os.rename(draft.DIR + ".away", draft.DIR)

def test_a_job_runs_and_is_polled():
    with scene():
        gate, hold = threading.Event(), threading.Event(); real = refit_plan.plan
        def slow(*a, progress=None, **k):
            hold.set(); assert gate.wait(60); return real(*a, progress=progress, **k)
        refit_plan.plan = slow
        try:
            r = c.post("/api/draft/refit"); assert r.status_code == 200 and r.get_json()["started"] and len(r.get_json()["id"]) == 12, r.get_json(); jid = r.get_json()["id"]
            assert hold.wait(60); g = c.get("/api/draft/refit").get_json(); assert g["state"] == "running" and g["id"] == jid and "plan" not in g and set(g) == {"state", "id", "done", "total", "error"}, g
            r2 = c.post("/api/draft/refit"); assert r2.status_code == 409 and r2.get_json() == dict(error="A re-fit is already running."), r2.get_json()
            assert c.get("/api/draft/refit/preview?id=" + jid).status_code == 404 and c.post("/api/draft/refit/apply", json=dict(id=jid)).status_code == 404   # not done yet
            assert c.get("/api/draft").status_code == 200   # step 8 works while it runs
        finally: gate.set(); refit_plan.plan = real
        got = poll(); assert got["state"] == "done" and got["id"] == jid and got["error"] is None and got["done"] == got["total"] and got["stale"] is False, got
        p = got["plan"]; assert set(p) == {"id", "stamp", "groups", "needs", "also", "totals", "late", "seconds"} and p["totals"]["changes"] >= 1 and p["id"] == jid and p["stamp"] == draft.stamp(), p
        assert all(set(s) == {"n", "text", "why", "tags"} for g in p["groups"] for s in g["steps"]) and '"fixes"' not in json.dumps(p) and '"fix"' not in json.dumps(p)   # no raw fixes
        draft.fix(dict(kind="room", id=1, group=ENTIRE, room="1-03"))   # the draft moves on: the list is stale
        assert c.get("/api/draft/refit").get_json()["stale"] is True

def test_stale_is_true_when_there_is_no_draft():
    with scene():
        run_job(); os.rename(draft.DIR, draft.DIR + ".away")
        try: assert c.get("/api/draft/refit").get_json()["stale"] is True
        finally: os.rename(draft.DIR + ".away", draft.DIR)

def test_apply_changes_exactly_the_plan():
    with scene():
        got = run_job(); n = got["plan"]["totals"]["changes"]; before, versions_before = fixes_now(), {v["id"] for v in versions._all()}; stored = copy.deepcopy(A.REFIT["plan"]["fixes"]); assert len(stored) == n
        r = c.post("/api/draft/refit/apply", json=dict(id=got["id"])); j = r.get_json(); assert r.status_code == 200 and j["changes"] == n and set(j) == {"info", "kept", "changes"}, j
        assert j["kept"]["kind"] == "refit" and j["kept"]["name"].startswith("Before re-fit, ") and re.fullmatch(r"Before re-fit, \d{1,2} [A-Z][a-z]{2} \d{1,2}\.\d\d [ap]m", j["kept"]["name"]), j["kept"]
        assert j["kept"]["id"] not in versions_before and j["kept"]["id"] in {v["id"] for v in versions._all()} and len(store.read_json(os.path.join(versions.folder(j["kept"]["id"]), "meta.json"))["fixes"]) == len(before)   # (the newest of ten automatic ones is kept, the oldest dropped) the version holds the draft as it was
        now = fixes_now(); new = now[len(before):]; assert now[:len(before)] == before and len(new) == n and len({f["batch"] for f in new}) == 1 and new[0]["batch"], new
        assert [{k: v for k, v in f.items() if k not in ("at", "text", "batch")} for f in new] == stored and all(f["text"] and f["at"] for f in new)
        assert not [w for w in c.get("/api/draft").get_json()["warnings"] if w["key"] == TEACH] and j["info"]["stamp"] == draft.stamp() and len(j["info"]["fixes"]) == len(now)
        assert A.REFIT["state"] == "idle" and c.get("/api/draft/refit").get_json() == dict(state="idle")
        t = A.history.read(limit=1)[0]; assert t["kind"] == "draft" and t["what"] == "refit" and t["text"] == f"Re-fit: {n} change{'s' * (n != 1)} ({got['plan']['totals']['moved']} lesson{'s' * (got['plan']['totals']['moved'] != 1)} moved, {got['plan']['totals']['another_day']} to another day, 0 typed rules to check again)", t["text"]
        u = c.post("/api/draft/undo"); assert u.status_code == 200 and len(fixes_now()) == len(before) and len(u.get_json()["fixes"]) == len(before)   # one Undo takes the batch back
        assert c.post("/api/draft/refit/apply", json=dict(id=got["id"])).status_code == 404   # the job is gone: no second batch

def test_the_history_text_has_its_singulars():
    t = lambda **k: A._refit_text(dict(dict(changes=0, moved=0, another_day=0, typed=[]), **k))
    assert t(changes=1, moved=1, another_day=1, typed=[2]) == "Re-fit: 1 change (1 lesson moved, 1 to another day, 1 typed rule to check again)"
    assert t(changes=4, moved=3, typed=[1, 2]) == "Re-fit: 4 changes (3 lessons moved, 0 to another day, 2 typed rules to check again)"
    assert t() == "Re-fit: 0 changes (0 lessons moved, 0 to another day, 0 typed rules to check again)"

def test_apply_refuses_a_stale_plan():
    with scene():
        got = run_job(); draft.fix(dict(kind="room", id=1, group=ENTIRE, room="1-03"))   # any change to the draft
        before, files, nversions = fixes_now(), (read("meta.json"), read("decisions.json")), versions.count()
        for r in (c.post("/api/draft/refit/apply", json=dict(id=got["id"])), c.get("/api/draft/refit/preview?id=" + got["id"])): assert r.status_code == 400 and r.get_json() == dict(error=REFIT_STALE), r.get_json()
        assert (read("meta.json"), read("decisions.json")) == files and fixes_now() == before and versions.count() == nversions   # nothing written, no version kept
        assert A.REFIT["state"] == "done"   # the job stays: the page offers a new run

def test_apply_refuses_a_step_that_no_longer_fits():
    with scene():
        got = run_job(); A.REFIT["plan"]["fixes"] = A.REFIT["plan"]["fixes"] + [dict(kind="move", id=9999, d=0, p=1)]   # the stamp is the draft's now, but the step cannot be made
        files, nversions = (read("meta.json"), read("decisions.json")), versions.count()
        r = c.post("/api/draft/refit/apply", json=dict(id=got["id"])); assert r.status_code == 400 and r.get_json()["error"] and r.get_json()["error"] != REFIT_STALE, r.get_json()
        assert (read("meta.json"), read("decisions.json")) == files and versions.count() == nversions and A.REFIT["state"] == "done"
        A.REFIT["plan"]["fixes"] = []; r = c.post("/api/draft/refit/apply", json=dict(id=got["id"])); assert r.status_code == 400 and r.get_json() == dict(error="There is nothing to apply."), r.get_json()   # an empty list
        assert (read("meta.json"), read("decisions.json")) == files and versions.count() == nversions

def test_a_wrong_id_finds_no_list():
    with scene():
        got = run_job()
        for r in (c.get("/api/draft/refit/preview?id=nope"), c.get("/api/draft/refit/preview"), c.post("/api/draft/refit/apply", json=dict(id="nope")), c.post("/api/draft/refit/apply", json=dict(id=5)), c.post("/api/draft/refit/apply", data="x")):
            assert r.status_code == 404 and r.get_json() == dict(error=REFIT_GONE), (r.status_code, r.get_json())
        assert A.REFIT["state"] == "done" and A.REFIT["id"] == got["id"]

REFIT_TYPED = dict(rules=[words("Room", "1-03"), words("Room", "1-02")], report=[(1, "Must", "", "made-up words", "Met", ""), (2, "Must", "", "made-up words", "Met", "")])
def typed_scene(): return scene(rows=[one(1, 0, 1, room="1-01"), one(9, 2, 1, room="1-03"), one(5, 3, 1, "1C", "Other", T2, room="1-03")], lifted=9, decide="typed:1:again", **REFIT_TYPED)

def test_typed_rules_lose_their_met_answer():
    with typed_scene():   # the teacher change reaches the lesson waiting in 1-03: T1 is to check again; its "met" answer goes, and only that
        assert store.read_json(os.path.join(draft.DIR, "decisions.json")).get("typed:1:again", {}).get("answer") == "met"
        got = run_job(); assert got["plan"]["totals"]["typed"] == [1], got["plan"]["totals"]
        r = c.post("/api/draft/refit/apply", json=dict(id=got["id"])); assert r.status_code == 200, r.get_json()
        assert "typed:1:again" not in store.read_json(os.path.join(draft.DIR, "decisions.json")) and [w for w in r.get_json()["info"]["warnings"] if w["key"] == "typed:1:again" and not w["decision"]]
        assert A.history.read(limit=1)[0]["text"].endswith("1 typed rule to check again)")

def test_only_met_answers_of_the_touched_rules_go():
    with typed_scene():
        got = run_job(); old = dict(at="1 Jan 2026, 09:00"); write = lambda d: store.write_json(os.path.join(draft.DIR, "decisions.json"), d)
        keep = {"typed:1:again": dict(old, answer="met"), "typed:1:again#2": dict(old, answer="met"), "typed:2:again": dict(old, answer="met"), "typed:1:again#3": dict(old, answer="step5"), "dep:x:teachers": dict(old, answer="step5")}
        write(keep); stamp = draft.stamp(); out = draft.refit_apply(copy.deepcopy(A.REFIT["plan"]["fixes"]), stamp, "Before re-fit, test", "Test")
        assert out["typed"] == [1] and out["kept"] is not None and set(out) == {"kept", "texts", "typed"} and len(out["texts"]) == len(A.REFIT["plan"]["fixes"]), out
        assert store.read_json(os.path.join(draft.DIR, "decisions.json")) == {k: v for k, v in keep.items() if k not in ("typed:1:again", "typed:1:again#2")}

def test_preview_of_a_plan():
    with scene():
        got = run_job(); files, nversions = (read("meta.json"), read("decisions.json")), versions.count()
        r = c.get("/api/draft/refit/preview?id=" + got["id"]); j = r.get_json(); assert r.status_code == 200 and j["state"] in ("ok", "prefer") and len(j["texts"]) == got["plan"]["totals"]["changes"] and set(j) >= {"classes", "gone", "texts", "state", "why"}, j
        assert len(j["classes"]) == 1
        mine = [x for g in j["classes"] for x in g["lessons"] if x["id"] == 1]; assert mine and all(x["teachers"] == [T1] and x["mark"] == "changed" for x in mine), mine
        assert (read("meta.json"), read("decisions.json")) == files and versions.count() == nversions   # nothing written

def test_a_failed_plan_says_so_and_names_nothing():
    with scene():
        real, logged = refit_plan.plan, []
        class Grab(logging.Handler):
            def emit(self, rec): logged.append(rec.getMessage() + "|" + (rec.exc_text or "") + str(rec.exc_info))
        h = Grab(); A.app.logger.addHandler(h)
        def broken(*a, **k): raise ValueError("secret name Zephyr Quill")
        refit_plan.plan = broken
        try:
            assert c.post("/api/draft/refit").status_code == 200; got = poll()
        finally: refit_plan.plan = real; A.app.logger.removeHandler(h)
        assert got["state"] == "failed" and got["error"] == "The re-fit could not be worked out. Run Re-fit again." and "plan" not in got and "Zephyr" not in json.dumps(got), got
        assert logged and all("Zephyr" not in x and "Quill" not in x for x in logged) and any("ValueError" in x for x in logged), logged
        assert c.post("/api/draft/refit").status_code == 200 and poll()["state"] == "done"   # a failed job does not block the next

def test_a_thread_never_leaves_the_state_at_running():
    with scene():
        real = refit_plan.plan
        def die(*a, **k): raise SystemExit
        refit_plan.plan = die
        try: c.post("/api/draft/refit"); A.REFIT["thread"].join(60); got = c.get("/api/draft/refit").get_json()
        finally: refit_plan.plan = real
        assert got["state"] == "failed" and got["error"], got

def test_the_old_thread_of_a_dead_job_writes_nothing():
    with scene():
        real, gate, hold, calls = refit_plan.plan, threading.Event(), threading.Event(), []
        def plan(m, rec, fx, decisions, ws, progress=None, **k):
            calls.append(1)
            if len(calls) == 1:
                hold.set(); assert gate.wait(60); progress(1, 1); return dict(stamp="old", groups=[], fixes=[], needs=[], also=[], totals={}, late=False, seconds=-1)
            return real(m, rec, fx, decisions, ws, progress=progress, **k)
        refit_plan.plan = plan
        try:
            first = c.post("/api/draft/refit").get_json()["id"]; assert hold.wait(60); old = A.REFIT["thread"]
            assert c.post("/api/draft/refit").status_code == 409
            A.REFIT["started"] -= 11 * 60   # the first one counts as dead
            second = c.post("/api/draft/refit"); assert second.status_code == 200 and second.get_json()["id"] != first
            got = poll(); assert got["state"] == "done" and got["id"] == second.get_json()["id"]
            gate.set(); old.join(60); assert not old.is_alive()   # the old thread comes in late
            again = c.get("/api/draft/refit").get_json(); assert again == got and again["plan"]["seconds"] != -1 and again["plan"]["stamp"] != "old", again
        finally: gate.set(); refit_plan.plan = real

def test_two_applies_at_once_make_one_batch():
    with scene():
        got = run_job(); n = got["plan"]["totals"]["changes"]; before = len(fixes_now()); real, entered, gate, out = draft.refit_apply, threading.Event(), threading.Event(), []
        def slow(*a, **k): entered.set(); assert gate.wait(60); return real(*a, **k)
        draft.refit_apply = slow; other = A.app.test_client(); other.post("/login", data={"as": "committee", "code": CODE})
        t = threading.Thread(target=lambda: out.append(other.post("/api/draft/refit/apply", json=dict(id=got["id"])))); t.start()
        try:
            assert entered.wait(60)
            assert c.post("/api/draft/refit/apply", json=dict(id=got["id"])).status_code == 404 and c.get("/api/draft/refit").get_json() == dict(state="idle")   # taken out, not given twice
        finally: gate.set(); t.join(60); draft.refit_apply = real
        assert out[0].status_code == 200 and len(fixes_now()) == before + n and len({f["batch"] for f in fixes_now()[before:]}) == 1

def test_a_refused_apply_puts_the_job_back():
    with scene():
        got = run_job(); A.REFIT["plan"]["fixes"] = [dict(kind="move", id=9999, d=0, p=1)]
        assert c.post("/api/draft/refit/apply", json=dict(id=got["id"])).status_code == 400
        assert A.REFIT["state"] == "done" and A.REFIT["id"] == got["id"] and c.get("/api/draft/refit").get_json()["state"] == "done"

def test_apply_when_the_draft_is_already_kept():
    with scene():
        got = run_job(); assert versions.keep("saved", "Test") is not None; n = versions.count()   # this very draft is kept already
        r = c.post("/api/draft/refit/apply", json=dict(id=got["id"])); assert r.status_code == 200 and r.get_json()["kept"] is None and versions.count() == n and len(fixes_now()) >= 1, r.get_json()

def test_the_job_changes_nothing():
    with scene():
        c.get("/api/draft"); m, rec, fx = draft.model_now(); was = copy.deepcopy([m, fx]); files = (read("meta.json"), read("decisions.json")); run_job()
        assert (read("meta.json"), read("decisions.json")) == files and draft.model_now()[0] is m and [m, fx] == was
        c.get("/api/draft/refit"); assert (read("meta.json"), read("decisions.json")) == files


# ------------------------------------------------------------ fix round 1: lists of many fixes, failures after the write, names kept out of the log
@contextlib.contextmanager
def logged():
    """every log record of the app's logger, as text (message, exc_text, exc_info), while the block runs"""
    got = []
    class Grab(logging.Handler):
        def emit(self, rec): got.append(rec.getMessage() + "|" + str(rec.exc_text) + "|" + str(rec.exc_info) + "|" + str(rec.args))
    h = Grab(); A.app.logger.addHandler(h)
    try: yield got
    finally: A.app.logger.removeHandler(h)

@contextlib.contextmanager
def patched(obj, name, new):
    was = getattr(obj, name); setattr(obj, name, new)
    try: yield was
    finally: setattr(obj, name, was)

NAME = "Zephyr Quill"
def boom(*a, **k): raise RuntimeError(f"secret {NAME}")
def no_name(got, *answers): assert got and not any("Zephyr" in x or "Quill" in x for x in got) and not any("Zephyr" in json.dumps(a) for a in answers), (got, answers)

def test_a_failure_in_the_start_the_apply_the_preview_and_the_check_names_nothing():
    with scene():
        with logged() as got, patched(draft, "listed", boom):   # the start
            r = c.post("/api/draft/refit"); assert r.status_code == 400 and r.get_json() == dict(error="The re-fit could not be started. Run Re-fit again."), r.get_json(); no_name(got, r.get_json())
        assert A.REFIT["state"] == "idle"
        j = run_job()
        with logged() as got, patched(helper, "chain", boom):   # the preview, then the apply
            r = c.get("/api/draft/refit/preview?id=" + j["id"]); assert r.status_code == 400 and r.get_json() == dict(error="The preview could not be made. Run Re-fit again."), r.get_json(); no_name(got, r.get_json())
            files, n = (read("meta.json"), read("decisions.json")), versions.count()
            r2 = c.post("/api/draft/refit/apply", json=dict(id=j["id"])); assert r2.status_code == 400 and r2.get_json() == dict(error="The re-fit could not be made. Run Re-fit again."), r2.get_json(); no_name(got, r2.get_json(), r.get_json())
        assert (read("meta.json"), read("decisions.json")) == files and versions.count() == n and A.REFIT["state"] == "done" and A.REFIT["id"] == j["id"]   # not made: the job is back
        before = len(fixes_now())
        with logged() as got, patched(draft, "info", boom):   # the check after the apply: the re-fit is made
            r = c.post("/api/draft/refit/apply", json=dict(id=j["id"])); b = r.get_json()
            assert r.status_code == 400 and b["error"] == "The re-fit was made, but the timetable could not be checked. Open step 8 again." and b["changes"] >= 1 and b["kept"]["kind"] == "refit", b; no_name(got, b)
        assert len(fixes_now()) == before + b["changes"] and A.REFIT["state"] == "idle" and A.history.read(limit=1)[0]["what"] == "refit"   # recorded, and the job is not put back

def test_the_check_after_the_apply_with_no_setup_is_a_409():
    with scene():
        j = run_job()
        with patched(draft, "info", lambda *a, **k: (_ for _ in ()).throw(LookupError())):
            r = c.post("/api/draft/refit/apply", json=dict(id=j["id"])); assert r.status_code == 409 and r.get_json()["error"] == A.REFIT_UNCHECKED and r.get_json()["kept"] is not None, r.get_json()

def test_a_start_with_no_setup_is_a_409():
    with scene():
        with patched(store, "setup_record", lambda *a, **k: dict(v=1, spec=None)):
            r = c.post("/api/draft/refit"); assert r.status_code == 409 and r.get_json() == dict(error=A.NO_SETUP), r.get_json()
        assert A.REFIT["state"] == "idle"

def test_a_thread_that_cannot_start_leaves_the_job_idle():
    with scene():
        class Dead:
            def __init__(self, *a, **k): pass
            def start(self): raise RuntimeError(f"no thread for {NAME}")
        with logged() as got, patched(A.threading, "Thread", Dead):
            r = c.post("/api/draft/refit"); assert r.status_code == 400 and r.get_json() == dict(error="The re-fit could not be started. Run Re-fit again."), r.get_json(); no_name(got, r.get_json())
        assert A.REFIT["state"] == "idle" and c.get("/api/draft/refit").get_json() == dict(state="idle")

def test_a_running_job_past_its_time_is_told_as_failed():
    with scene():
        A._refit_clear(); A.REFIT.update(id="abc", state="running", done=0, total=None, plan=None, error=None, started=time.monotonic() - A.REFIT_DEAD_S - 1)
        g = c.get("/api/draft/refit").get_json(); assert g["state"] == "failed" and g["error"] == A.REFIT_FAILED, g
        A.REFIT["started"] = time.monotonic(); assert c.get("/api/draft/refit").get_json()["state"] == "running"

def test_apply_with_no_draft_is_the_stale_sentence_and_the_job_stays():
    with scene():
        j = run_job(); os.rename(draft.DIR, draft.DIR + ".away")
        try: r = c.post("/api/draft/refit/apply", json=dict(id=j["id"])); assert r.status_code == 400 and r.get_json() == dict(error=REFIT_STALE), r.get_json()
        finally: os.rename(draft.DIR + ".away", draft.DIR)
        assert A.REFIT["state"] == "done" and A.REFIT["id"] == j["id"]

def test_a_setup_saved_while_the_list_is_judged_makes_it_stale():
    with scene():
        j = run_job(); files, n = (read("meta.json"), read("decisions.json")), versions.count(); real = helper.chain; s = json.loads(json.dumps(store.setup_record()["spec"]))
        def saving(*a, **k):
            out = real(*a, **k); s["rules"] = list(s["rules"]) + [dict(PREFER_RULE, note="made-up second wish")]; put_setup(s); return out
        with patched(helper, "chain", saving):
            r = c.post("/api/draft/refit/apply", json=dict(id=j["id"])); assert r.status_code == 400 and r.get_json() == dict(error=REFIT_STALE), r.get_json()
        assert (read("meta.json"), read("decisions.json")) == files and versions.count() == n and A.REFIT["id"] == j["id"]

def test_a_refused_apply_leaves_a_new_job_alone():
    with scene():
        j = run_job(); other = A.app.test_client(); other.post("/login", data={"as": "committee", "code": CODE}); made = []
        def meanwhile(*a, **k):
            r = other.post("/api/draft/refit"); made.append(r.get_json()["id"]); poll(); raise ValueError("refused here")
        with patched(draft, "refit_apply", meanwhile):
            r = c.post("/api/draft/refit/apply", json=dict(id=j["id"])); assert r.status_code == 400 and r.get_json() == dict(error="refused here")
        assert A.REFIT["id"] == made[0] != j["id"] and A.REFIT["state"] == "done"

def test_a_clash_at_apply_is_refused_with_the_judges_sentence():
    with scene(rows=[one(1, 0, 1), one(2, 0, 2, CLS, "Other", T2)]):
        j = run_job(); bad = [dict(kind="move", id=1, d=0, p=2)]; m, rec, fx = draft.model_now(); why = helper.chain(m, m["checked_setup"], m["days"], bad)["why"]; assert why and len(why) > 5
        A.REFIT["plan"]["fixes"] = bad   # the stamp is the draft's now
        files, n = (read("meta.json"), read("decisions.json")), versions.count()
        r = c.post("/api/draft/refit/apply", json=dict(id=j["id"])); assert r.status_code == 400 and r.get_json() == dict(error=why), (r.get_json(), why)
        assert (read("meta.json"), read("decisions.json")) == files and versions.count() == n and A.REFIT["state"] == "done" and A.REFIT["id"] == j["id"]
        A.REFIT["plan"]["fixes"] = [dict(kind="teacher", key=KEY, teachers=[T1]), dict(bad[0]), dict(kind="teacher", key=KEY, teachers=[T0])]   # a preview whose middle step is refused
        r = c.get("/api/draft/refit/preview?id=" + j["id"]); b = r.get_json(); assert r.status_code == 200 and b["state"] == "no" and b["why"] == why and len(b["texts"]) == 1, b
        assert (read("meta.json"), read("decisions.json")) == files

def forced(c_, state, prefer=(), cut=0):
    """helper.chain's answer made to say state, with these reasons on its first step, and cut texts missing"""
    steps = [dict(j) for j in c_["steps"]]; steps[0] = dict(steps[0], prefer=list(prefer), state=state)
    return dict(c_, state=state, why=prefer[0] if prefer else "", steps=steps, texts=c_["texts"][:len(c_["texts"]) - cut])

def test_a_prefer_is_applied_only_when_it_is_an_allowance_line():
    with scene():
        j = run_job(); real = helper.chain; files, n = (read("meta.json"), read("decisions.json")), versions.count(); other = "Made-up wish is not met."
        with patched(helper, "chain", lambda *a, **k: forced(real(*a, **k), "prefer", [other])):
            r = c.post("/api/draft/refit/apply", json=dict(id=j["id"])); assert r.status_code == 400 and r.get_json() == dict(error=other), r.get_json()
        assert (read("meta.json"), read("decisions.json")) == files and versions.count() == n and A.REFIT["state"] == "done"
        with patched(helper, "chain", lambda *a, **k: forced(real(*a, **k), "prefer", ["Made-up teacher is over the allowance."])):
            r = c.post("/api/draft/refit/apply", json=dict(id=j["id"])); assert r.status_code == 200, r.get_json()

def test_a_list_not_all_made_is_refused():
    with scene():
        j = run_job(); real = helper.chain; files, n = (read("meta.json"), read("decisions.json")), versions.count()
        with patched(helper, "chain", lambda *a, **k: forced(real(*a, **k), "ok", cut=1)):
            r = c.post("/api/draft/refit/apply", json=dict(id=j["id"])); assert r.status_code == 400 and r.get_json() == dict(error="That fix could not be made. Check the list again."), r.get_json()
        assert (read("meta.json"), read("decisions.json")) == files and versions.count() == n and A.REFIT["state"] == "done"

def test_a_list_of_many_fixes_is_shown_made_and_taken_back_whole():
    was = json.loads(json.dumps(store.setup_record()["spec"]))
    try:
        a_draft(); A._refit_clear(); j = run_job(); stored = copy.deepcopy(A.REFIT["plan"]["fixes"]); n = len(stored); assert n >= 4, n
        shown = c.get("/api/draft/refit").get_json()["plan"]; assert sum(len(g["steps"]) for g in shown["groups"]) == n and shown["totals"]["changes"] == n and '"fix"' not in json.dumps(shown) and '"fixes"' not in json.dumps(shown)
        files = (read("meta.json"), read("decisions.json")); r = c.get("/api/draft/refit/preview?id=" + j["id"]); pre = r.get_json(); assert r.status_code == 200 and len(pre["texts"]) == n and pre["state"] in ("ok", "prefer"), pre
        assert (read("meta.json"), read("decisions.json")) == files
        before = fixes_now(); r = c.post("/api/draft/refit/apply", json=dict(id=j["id"])); b = r.get_json(); assert r.status_code == 200 and b["changes"] == n and b["kept"]["kind"] == "refit", b
        now = fixes_now(); new = now[len(before):]; assert now[:len(before)] == before and len(new) == n and len({f["batch"] for f in new}) == 1 and new[0]["batch"] and all(f["at"] == new[0]["at"] for f in new)
        assert [{k: v for k, v in f.items() if k not in ("at", "text", "batch")} for f in new] == stored and [f["text"] for f in new] == pre["texts"]   # all, in order, as shown
        assert A.history.read(limit=1)[0]["text"] == A._refit_text(shown["totals"]) and len(b["info"]["fixes"]) == len(now)
        u = c.post("/api/draft/undo"); assert u.status_code == 200 and fixes_now() == before   # one Undo takes them all back
    finally: A._refit_clear(); put_setup(was)


def test_info_says_whether_there_is_anything_to_refit():
    flag = lambda: (c.get("/api/draft").get_json(), draft.info())
    with scene():   # the teachers differ from step 5
        j, i = flag(); assert j["refit"] is True and i["refit"] is True and refit.needed(j["warnings"]) is True
    fits = [one(1, 0, 1, CLS, EL, T1)]
    with scene(rows=fits):   # the timetable is what step 5 says
        j, i = flag(); assert j["refit"] is False and i["refit"] is False and not refit.targets(j["warnings"]), [w["key"] for w in j["warnings"]]
    with scene(rows=fits, rules=[dict(AWAY(T1, 0, 1, 1), strength="Prefer")]):   # only a Prefer rule is broken
        j, i = flag(); assert any(w["kind"] == "rule" and not w.get("decision") for w in j["warnings"]) and j["refit"] is False and i["refit"] is False, [w["key"] for w in j["warnings"]]
    with scene():   # the one warning answered: step 8 counts it settled
        draft.decide(TEACH, "step5"); j, i = flag(); assert j["refit"] is False and i["refit"] is False


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for f in tests: f()
    print(f"{len(tests)} checks passed")

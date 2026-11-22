"""Plain-assert tests for the re-fit: .venv/bin/python tests/test_refit.py"""
import contextlib, copy, gzip, io, json, os, secrets, shutil, sys, tempfile, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = tempfile.mkdtemp()
CODE = secrets.token_hex(4)
os.environ.pop("HEADS_CODE", None)
os.environ.update(DATA_DIR=DATA, SECRET_KEY=secrets.token_hex(16), AI_PROVIDER="anthropic", AI_API_KEY="", COMMITTEE_CODE=CODE, TEACHER_CODE=secrets.token_hex(4), STUDENT_CODE=secrets.token_hex(4))
sys.path.insert(0, ROOT)
import openpyxl  # noqa: E402
import app as A, draft, fixes, helper, refit, store  # noqa: E402
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

def workbook(rows):
    """a made-up Lessons workbook: rows = [dict(id, day, p, n, level, block, classes, subject, group, teachers)]"""
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Lessons"
    ws.append(["Lesson ID", "Day", "Start period", "End period", "Periods", "Starts", "Ends", "Level", "Block", "Classes", "Subject", "Group", "Teachers", "Room", "After school", "Rain room"])
    for r in rows:
        ws.append([r["id"], r["day"], r["p"], r["p"] + r["n"] - 1, r["n"], "", "", r["level"], r.get("block", ""), ", ".join(r["classes"]), r["subject"], r.get("group", "Entire Class"), ", ".join(r.get("teachers", [])), r.get("room", ""), "", r.get("rain", "")])
    buf = io.BytesIO(); wb.save(buf); return buf.getvalue()

_made = {}   # the setup workbook is made once: every upload here sends the same one
def setup_bytes(spec):
    if "b" not in _made: p = os.path.join(tempfile.mkdtemp(), "setup.xlsx"); write_template(spec, p); _made["b"] = open(p, "rb").read()
    return _made["b"]

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
    got, stats = hunt(m, spec, days, t, pool, moved={2}); assert got is None and stats == dict(nodes=1, reason=refit.NO_FIT, late=False), stats
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

if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for f in tests: f()
    print(f"{len(tests)} checks passed")

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
from ttgen import verify  # noqa: E402
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
        far = [g for g in got if g["other"]]; near = [g for g in got if not g["other"]]
        assert far and got == near + far   # same-day items first, then the other days
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

if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for f in tests: f()
    print(f"{len(tests)} checks passed")

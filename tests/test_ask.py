"""Plain-assert tests for the look-ups about one lesson (ask.py): .venv/bin/python tests/test_ask.py"""
import io, os, secrets, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = tempfile.mkdtemp()
CODE = secrets.token_hex(4)
os.environ.pop("HEADS_CODE", None)
os.environ.update(DATA_DIR=DATA, SECRET_KEY=secrets.token_hex(16), AI_PROVIDER="anthropic", AI_API_KEY="", COMMITTEE_CODE=CODE, TEACHER_CODE=secrets.token_hex(4), STUDENT_CODE=secrets.token_hex(4))
sys.path.insert(0, ROOT)
import openpyxl  # noqa: E402
import app as A, ask, draft, fixes, helper, store, typed  # noqa: E402
from ttgen.template import write_template  # noqa: E402

c = A.app.test_client()
assert c.post("/login", data={"as": "committee", "code": CODE}).status_code == 302

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

assert c.put("/api/setup", json=A.sample("primary")).status_code == 200
SPEC = c.get("/api/setup").get_json()["spec"]
LEVEL = SPEC["classes"][0]["level"]
CA, CB, CC = [x["class"] for x in SPEC["classes"] if x["level"] == LEVEL][:3]
DAYS = list(SPEC["day_structure"][LEVEL].keys())
L1 = SPEC["day_structure"][LEVEL][DAYS[0]].index("L"); assert SPEC["day_structure"][LEVEL][DAYS[0]][L1:L1 + 3] == "LLL"
ROOMS = [v["room"] for v in SPEC["venues"] if (v.get("kind") or "classroom") == "classroom"][:2]
T0, T1, T2, T3 = [x["name"] for x in SPEC["teachers"]][:4]
SUBJ, SUBJ2 = SPEC["subjects"][0]["subject"], SPEC["subjects"][1]["subject"]
UNKNOWN = "Nobody Known"
BAND = dict(level=LEVEL, block=f"{LEVEL} Band A")
LESSON, SWAP_OK, SWAP_CLASH, CLASH_T, BANDID, POOLED, NO_TEACHER, UNKNOWN_ID, HOLDER = 1, 2, 3, 5, 6, 7, 8, 9, 10
ROWS = [   # lesson 1 swaps cleanly with 2 and clashes with 3 (T0 teaches lesson 5 then); the band has three groups; 7 is lifted; 8 has no teacher; 9 names a teacher who is not in the setup; 10 holds a room lesson 1 could use
    dict(id=LESSON, day=DAYS[0], p=L1, n=1, level=LEVEL, classes=[CA], subject=SUBJ, teachers=[T0], room=ROOMS[0]),
    dict(id=SWAP_OK, day=DAYS[1], p=L1, n=1, level=LEVEL, classes=[CA], subject=SUBJ2, teachers=[T1]),
    dict(id=SWAP_CLASH, day=DAYS[2], p=L1, n=1, level=LEVEL, classes=[CA], subject=SUBJ, teachers=[T2]),
    dict(id=CLASH_T, day=DAYS[2], p=L1, n=1, level=LEVEL, classes=[CB], subject=SUBJ2, teachers=[T0]),
    dict(id=BANDID, day=DAYS[3], p=L1, n=2, classes=[CA, CB], subject=SUBJ, group="G1", teachers=[T1], **BAND),
    dict(id=BANDID, day=DAYS[3], p=L1, n=2, classes=[CA], subject=SUBJ2, group="G2", teachers=[T2], **BAND),
    dict(id=BANDID, day=DAYS[3], p=L1, n=2, classes=[CB], subject=SUBJ, group="G3", teachers=[UNKNOWN], **BAND),
    dict(id=POOLED, day=DAYS[1], p=L1 + 2, n=1, level=LEVEL, classes=[CB], subject=SUBJ, teachers=[T1]),
    dict(id=NO_TEACHER, day=DAYS[3], p=L1 + 2, n=1, level=LEVEL, classes=[CB], subject=SUBJ2),
    dict(id=UNKNOWN_ID, day=DAYS[4], p=L1, n=1, level=LEVEL, classes=[CB], subject=SUBJ, teachers=[UNKNOWN]),
    dict(id=HOLDER, day=DAYS[0], p=L1, n=1, level=LEVEL, classes=[CB], subject=SUBJ2, teachers=[T3], room=ROOMS[1]),
    dict(id=11, day=DAYS[0], p=L1, n=1, level=LEVEL, classes=[CC], subject=SUBJ2, teachers=[T2]),   # T2 is busy when lesson 10 is, so T2 cannot take it
]
r = c.post("/api/draft", data=dict(setup=(io.BytesIO(setup_bytes(SPEC)), "setup.xlsx"), timetable=(io.BytesIO(workbook(ROWS)), "timetable.xlsx"), replace="1"), content_type="multipart/form-data"); assert r.status_code == 200, r.get_json()
draft.fix(dict(kind="lift", id=POOLED))

def now():
    m, rec, fx = draft._now(); return m, m["checked_setup"], m["days"], fx["pool"]

def pre(m, spec, days, pool): return (m, spec, days, pool)
def lesson(i, **kw): return dict(kind="lesson", id=i, group=kw.get("group"), teacher=kw.get("teacher"))
def mv(i, d, p): return dict(kind="move", id=i, d=d, p=p)
def stored(): return store.read_json(draft._p("meta.json"))["fixes"]
def undo_all():
    while stored() and stored()[-1]["kind"] != "lift": draft.undo()

def test_subject_clean():
    m, spec, days, pool = now()
    assert ask.subject(m, pool, dict(kind="lesson", id=LESSON)) == dict(kind="lesson", id=LESSON, group=None, teacher=None)
    assert ask.subject(m, pool, dict(kind="lesson", id=BANDID, group="G2", teacher=T2)) == dict(kind="lesson", id=BANDID, group="G2", teacher=T2)
    assert ask.subject(m, pool, dict(kind="lesson", id=POOLED))["id"] == POOLED   # a lesson in the pool is a lesson
    assert ask.subject(m, pool, dict(kind="place", by="class", name=CA, d=1, p=L1)) == dict(kind="place", by="class", name=CA, d=1, p=L1)
    assert ask.subject(m, pool, dict(kind="place", by="teacher", name=T0, d=0, p=0))["by"] == "teacher"
    assert ask.subject(m, pool, dict(kind="place", by="room", name=ROOMS[0], d=0, p=0))["name"] == ROOMS[0]

def test_subject_refused():
    m, spec, days, pool = now(); bad = lambda raw, text: raises(ValueError, lambda: ask.subject(m, pool, raw), text)
    bad(dict(kind="lesson", id=999), "There is no lesson with that id on the timetable.")
    bad(dict(kind="lesson", id="x"), "There is no lesson with that id on the timetable.")
    bad(dict(kind="lesson", id=BANDID, group="G9"), "There is no row of G9 in that lesson.")
    bad(dict(kind="place", by="class", name=CA, d=99, p=0), "That is outside the day.")
    bad(dict(kind="place", by="class", name=CA, d=0, p=99), "That is outside the day.")
    bad(dict(kind="place", by="class", name="Nowhere", d=0, p=0), "There is no class called Nowhere.")
    bad(dict(kind="place", by="teacher", name="Nobody At All", d=0, p=0), "There is no teacher called Nobody At All.")
    bad(dict(kind="place", by="room", name="Nowhere", d=0, p=0), "There is no room called Nowhere.")
    bad(dict(kind="place", by="teacher", name="", d=0, p=0), "Pick a teacher's row.")
    bad(dict(kind="place", by="room", name="", d=0, p=0), "Pick a room's row.")

def test_check_one():
    m, spec, days, pool = now(); P = (m, spec, days, pool)
    f = mv(LESSON, 1, L1 + 1); o = ask.check(*P, [f])
    assert o["state"] in ("ok", "prefer") and o["apply"] == "yes" and o["text"] == helper.say(m, spec, days, f) and o["fixes"] == [f] and isinstance(o["disturbs"], list) and o["disturbs"], o
    f = mv(LESSON, 2, L1); o = ask.check(*P, [f]); j = fixes.judge(m, spec, days, f, pool=pool)   # T0 teaches lesson 5 then
    assert o["state"] == "no" and o["apply"] == "anyway" and o["why"] == j["why"] and j["why"], o
    o = ask.check(*P, [dict(kind="swap", a=LESSON, b=SWAP_CLASH)]); assert o["state"] == "no" and o["apply"] == "none", o
    o = ask.check(*P, [dict(kind="swap", a=LESSON, b=SWAP_OK)]); assert o["apply"] == "yes" and o["text"].startswith("Swap "), o
    t = dict(kind="trade", a=f"C:{CA}:{SUBJ}", b=f"C:{CB}:{SUBJ2}", x=T2, y=T3); o = ask.check(*P, [t])   # T2 would take lesson 10, while teaching lesson 11
    assert o is not None and o["state"] == "no" and o["apply"] == "none" and o["text"] == helper.say(m, spec, days, t), o
    assert ask.check(*P, [mv(LESSON, 0, 0)]) is None   # a break
    assert ask.check(*P, []) is None
    o = ask.check(*P, [dict(kind="teacher", key=f"C:{CA}:{SUBJ}", teachers=[T3])]); assert o["apply"] in ("yes", "anyway") and any(T3 in d for d in o["disturbs"]), o

def test_check_two():
    m, spec, days, pool = now(); P = (m, spec, days, pool)
    a, b = mv(LESSON, 1, L1 + 1), mv(SWAP_OK, 0, L1 + 2)
    o = ask.check(*P, [a, b]); assert o["state"] in ("ok", "prefer") and o["fixes"] == [a, b] and o["apply"] == "yes" and o["text"] == helper.says(m, spec, days, [a, b]), o
    bad = mv(SWAP_OK, 2, L1); o = ask.check(*P, [a, bad])
    assert o is not None and o["state"] == "no" and o["apply"] == "none" and o["why"], o
    assert ask.check(*P, [dict(kind="place", id=POOLED, d=0, p=L1 + 2), a]) is None
    assert ask.check(*P, [a, dict(kind="lift", id=SWAP_OK)]) is None
    assert ask.check(*P, [a, b, mv(SWAP_CLASH, 0, 0)]) is None

def test_place_is_worded():
    m, spec, days, pool = now()
    assert ask.say(m, spec, days, pool, dict(kind="place", id=POOLED, d=0, p=L1 + 2)) == f"Place {fixes.what(pool[0])} on {days[0]} period {L1 + 2}."
    assert ask.say(m, spec, days, pool, mv(LESSON, 1, L1 + 1)) == helper.say(m, spec, days, mv(LESSON, 1, L1 + 1))

def test_check_is_the_board():
    m, spec, days, pool = now(); n = len(stored())
    for ans in (ask.swaps(m, spec, days, pool, lesson(LESSON)), ask.moves(m, spec, days, pool, lesson(LESSON))):
        assert ans["options"]
        for o in ans["options"]:
            (f,) = o["fixes"]; plain = dict(f)
            if o["apply"] == "none":   # the board refuses it too, forced or not
                raises(ValueError, lambda: draft.fix(plain)); raises(ValueError, lambda: draft.fix(dict(plain, force=True, why=o["why"]))); assert len(stored()) == n; continue
            try: draft.fix(plain)
            except ValueError as e:
                assert o["apply"] == "anyway", (o, str(e)); draft.fix(dict(plain, force=True, why=str(e)))
            else: assert o["apply"] == "yes", o
            want = fixes.apply_one([dict(x) for x in m["lessons"]], f, spec, days, pool=[dict(x) for x in pool])
            assert stored()[-1]["text"] == want, (stored()[-1]["text"], want)
            draft.undo(); assert len(stored()) == n

def test_swaps_lists():
    m, spec, days, pool = now(); a = ask.swaps(m, spec, days, pool, lesson(LESSON))
    assert [o["fixes"][0]["b"] for o in a["options"]] == [SWAP_OK, SWAP_CLASH] and [o["apply"] for o in a["options"]] == ["yes", "none"], a
    assert a["text"] == "This lesson can swap with 2 lessons." and a["more"] == 0 and a["stopped"] is False and a["title"].startswith(fixes.what(m["lessons"][0]) + " · ") and isinstance(a["lines"], list)
    assert a["options"][0]["fixes"][0] == dict(kind="swap", a=LESSON, b=SWAP_OK)
    p = ask.swaps(m, spec, days, pool, lesson(POOLED)); assert p["options"] == [] and p["text"] == "A lesson that is not placed cannot be swapped. Ask where it can go."
    n = ask.swaps(m, spec, days, pool, lesson(BANDID)); assert n["text"] == "Nothing can swap with this lesson." and n["options"] == [], n

def test_moves_pool():
    m, spec, days, pool = now(); a = ask.moves(m, spec, days, pool, lesson(POOLED))
    assert a["options"] and all(o["fixes"][0]["kind"] == "place" and o["fixes"][0]["id"] == POOLED and o["text"].startswith("Place ") for o in a["options"]), a
    assert a["title"].endswith("Not placed"), a["title"]

def test_moves_lists_ok_first_then_no_when_few():
    m, spec, days, pool = now(); a = ask.moves(m, spec, days, pool, lesson(LESSON))
    ok = [o for o in a["options"] if o["state"] != "no"]; no = [o for o in a["options"] if o["state"] == "no"]
    assert ok and a["options"][:len(ok)] == ok and all(o["fixes"][0]["kind"] == "move" for o in a["options"]) and len(a["options"]) <= ask.MOST + 3
    assert all(o["state"] != "na" for o in a["options"]) and (len(ok) >= 3 or len(no) <= 3)
    ds = [o["fixes"][0]["d"] for o in no]; assert ds == sorted(ds, key=lambda d: (abs(d - 0), d))   # nearest day first

def test_moves_band():
    m, spec, days, pool = now(); a = ask.moves(m, spec, days, pool, lesson(BANDID))
    assert a["options"] and all(o["fixes"][0]["kind"] == "move" and o["fixes"][0]["id"] == BANDID for o in a["options"])
    o = a["options"][0]; text = " ".join(o["disturbs"]); assert CA in text and CB in text and "G2" in text, o["disturbs"]
    assert a["title"].startswith("the Band A band · "), a["title"]; assert len(a["lines"]) == 3 and a["lines"][0].startswith("group G1: "), a["lines"]
    assert a["lines"][2] == f"group G3: {SUBJ}, {UNKNOWN}, no room", a["lines"]

def test_teachers_one_group():
    m, spec, days, pool = now(); a = ask.teachers(m, spec, days, pool, lesson(BANDID, group="G2"))
    assert a["options"], a; key = f"G:G2"
    assert all(o["fixes"][0]["kind"] == "teacher" and o["fixes"][0]["key"] == key for o in a["options"])
    o = next(o for o in a["options"] if o["apply"] == "yes"); n = len(stored())
    draft.fix(o["fixes"][0]); m2, spec2, days2, pool2 = now(); by = {x["group"]: x["teachers"] for x in m2["lessons"] if x["id"] == BANDID}
    assert by["G1"] == [T1] and by["G3"] == [UNKNOWN] and by["G2"] == o["fixes"][0]["teachers"]; draft.undo()
    for who in a["options"][0]["who"], :
        assert set(who) == {"name", "depts", "subjects", "free", "doing", "rank", "load", "after", "allowance"}, who

def test_teachers_replace():
    m, spec, days, pool = now(); a = ask.teachers(m, spec, days, pool, lesson(BANDID, group="G1", teacher=T1)); assert a["options"]
    assert all(o["fixes"][0]["teachers"] == [o["who"]["name"]] for o in a["options"])
    # a row of two teachers: the second is replaced
    two = [dict(x, teachers=[T0, T1]) if x["id"] == LESSON else x for x in m["lessons"]]; m2 = dict(m, lessons=two)
    a = ask.teachers(m2, spec, days, pool, lesson(LESSON, teacher=T1)); assert a["options"]
    assert all(o["fixes"][0]["teachers"][0] == T0 and len(o["fixes"][0]["teachers"]) == 2 and o["fixes"][0]["teachers"][1] == o["who"]["name"] for o in a["options"]), a["options"][0]
    a = ask.teachers(m2, spec, days, pool, lesson(LESSON, teacher=T0)); assert all(o["fixes"][0]["teachers"][1] == T1 for o in a["options"])   # a teacher not asked about stays
    a = ask.teachers(m2, spec, days, pool, lesson(LESSON, teacher="Somebody Else")); assert all(o["fixes"][0]["teachers"][1] == T1 for o in a["options"])   # not on the row: the first is replaced

def test_teachers_words():
    m, spec, days, pool = now(); a = ask.teachers(m, spec, days, pool, lesson(LESSON)); o = a["options"][0]; w = o["who"]
    assert w["free"] and w["after"] >= w["load"] and any(" · " in d and f"{w['load']} to {w['after']}" in d for d in o["disturbs"]), o["disturbs"]
    assert f"It changes all 2 lessons of {fixes.what(m['lessons'][0])}." in o["disturbs"]   # lessons 1 and 3 are of the same class and subject
    one = ask.teachers(m, spec, days, pool, lesson(BANDID, group="G2"))["options"][0]; assert not any("It changes all" in d for d in one["disturbs"])   # a group is one lesson
    busy = [o for o in a["options"] if not o["who"]["free"]]; assert len(busy) <= ask.BUSY and all(o["who"]["doing"] and o["state"] == "no" and o["apply"] == "anyway" for o in busy)
    assert a["options"].index(busy[0]) > max(i for i, o in enumerate(a["options"]) if o["who"]["free"]) if busy else True

def test_teachers_none_and_unknown():
    m, spec, days, pool = now()
    a = ask.teachers(m, spec, days, pool, lesson(NO_TEACHER)); assert a["options"] and all(o["fixes"][0]["teachers"] == [o["who"]["name"]] for o in a["options"]), a
    a = ask.teachers(m, spec, days, pool, lesson(UNKNOWN_ID)); assert a["options"] and all(len(o["fixes"][0]["teachers"]) == 1 and UNKNOWN not in o["fixes"][0]["teachers"] for o in a["options"]), a
    a = ask.teachers(m, spec, days, pool, lesson(UNKNOWN_ID, teacher="Nobody At All")); assert a["options"]
    a = ask.teachers(m, spec, days, pool, lesson(POOLED)); assert a["options"] and a["options"][0]["fixes"][0]["kind"] == "teacher"
    gone = ask.teachers(dict(m, lessons=[x for x in m["lessons"] if x["id"] != LESSON]), spec, days, pool, lesson(LESSON))
    assert gone["options"] == [] and gone["text"]

def test_rooms_lists():
    m, spec, days, pool = now(); a = ask.rooms(m, spec, days, pool, lesson(LESSON)); opts = a["options"]; assert opts
    assert all(o["fixes"][0]["kind"] == "room" and o["fixes"][0]["id"] == LESSON and "all" not in o["fixes"][0] for o in opts)
    used = [o for o in opts if o["fixes"][0]["room"] == ROOMS[1]]; assert len(used) == 1 and used[0]["apply"] == "anyway" and used[0]["state"] == "no"
    assert any(d.startswith("It holds ") and d.endswith(" then.") and fixes.what([x for x in m["lessons"] if x["id"] == HOLDER][0]) in d for d in used[0]["disturbs"]), used[0]["disturbs"]
    assert opts.index(used[0]) > max(i for i, o in enumerate(opts) if o["state"] != "no" and o["fixes"][0]["room"] != ROOMS[1])
    assert all(o["fixes"][0]["room"] != ROOMS[0] for o in opts)   # not the room it is in

def test_the_other_lookups_refuse_a_place():
    m, spec, days, pool = now(); place = dict(kind="place", by="class", name=CA, d=0, p=0)
    for f in (ask.swaps, ask.moves, ask.teachers, ask.rooms): raises(ValueError, lambda: f(m, spec, days, pool, place), "Point at a lesson for this.")

def test_here_for_a_place():
    m, spec, days, pool = now(); h = ask.here(m, spec, days, pool, dict(kind="place", by="class", name=CA, d=1, p=L1))
    assert h["title"] == f"{CA} · {days[1]} period {L1} · empty" and h["lines"] == [], h
    h = ask.here(m, spec, days, pool, lesson(BANDID)); assert h["title"] == f"the Band A band · {days[3]} periods {L1} to {L1 + 1}", h["title"]

def test_cap():
    m, spec, days, pool = now(); n = len(m["teacher_ix"]); a = ask.teachers(m, spec, days, pool, lesson(NO_TEACHER))
    free = [o for o in a["options"] if o["who"]["free"]]; assert len(free) == ask.MOST and a["more"] > 0, (len(free), a["more"], n)
    cands = [t for t in helper.fixes.choices(m, spec, days, NO_TEACHER, None, pool)["teachers"] if t["free"]]
    assert len(free) + a["more"] == len(cands), (len(free), a["more"], len(cands))
    r = ask.moves(m, spec, days, pool, lesson(POOLED)); assert len([o for o in r["options"] if o["state"] != "no"]) <= ask.MOST
    if r["more"]: assert len(r["options"]) == ask.MOST

if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for f in tests: f(); undo_all()
    print(f"{len(tests)} checks passed")

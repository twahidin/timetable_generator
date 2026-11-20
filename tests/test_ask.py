"""Plain-assert tests for the look-ups about one lesson (ask.py): .venv/bin/python tests/test_ask.py"""
import contextlib, io, os, secrets, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = tempfile.mkdtemp()
CODE = secrets.token_hex(4)
os.environ.pop("HEADS_CODE", None)
os.environ.update(DATA_DIR=DATA, SECRET_KEY=secrets.token_hex(16), AI_PROVIDER="anthropic", AI_API_KEY="", COMMITTEE_CODE=CODE, TEACHER_CODE=secrets.token_hex(4), STUDENT_CODE=secrets.token_hex(4))
sys.path.insert(0, ROOT)
import openpyxl  # noqa: E402
import app as A, ask, draft, fixes, helper, store, typed  # noqa: E402
from ttgen import verify  # noqa: E402
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
    bad(dict(kind="place", by="class", name="", d=0, p=0), "Pick a class's row.")
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
    assert a["text"] == "This lesson can swap with 1 lesson. 1 more would land with a problem." and a["more"] == 0 and a["stopped"] is False and a["title"].startswith(fixes.what(m["lessons"][0]) + " · ") and isinstance(a["lines"], list)
    assert a["options"][0]["fixes"][0] == dict(kind="swap", a=LESSON, b=SWAP_OK)
    p = ask.swaps(m, spec, days, pool, lesson(POOLED)); assert p["options"] == [] and p["text"] == "A lesson that is not placed cannot be swapped. Ask where it can go."
    n = ask.swaps(m, spec, days, pool, lesson(BANDID)); assert n["text"] == "Nothing can swap with this lesson." and n["options"] == [], n

def test_moves_pool():
    m, spec, days, pool = now(); a = ask.moves(m, spec, days, pool, lesson(POOLED))
    assert a["options"] and all(o["fixes"][0]["kind"] == "place" and o["fixes"][0]["id"] == POOLED and o["text"].startswith("Place ") for o in a["options"]), a
    assert " · Not placed · " in a["title"], a["title"]

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

def test_the_band_line_names_the_other_groups():
    m, spec, days, pool = now(); line = lambda g: " ".join(ask.moves(m, spec, days, pool, lesson(BANDID, group=g))["options"][0]["disturbs"])
    t = line("G2"); assert "G1 (" in t and "G3 (" in t and "G2" not in t, t
    t = line(None); assert "G2 (" in t and "G3 (" in t and "G1" not in t, t   # no group asked: the first row is the one asked about

def test_the_anyway_kinds_are_the_forced_kinds_but_a_delete():
    assert set(ask.ANYWAY) == set(draft.FORCED) - {"delete"}

def test_swaps_text_counts_clean_and_problem_swaps():
    m, spec, days, pool = now(); P = (m, spec, days, pool)
    rows = [x for x in m["lessons"] if x["id"] != SWAP_OK]   # only the clashing swap is left
    a = ask.swaps(dict(m, lessons=rows), spec, days, pool, lesson(LESSON)); assert a["text"] == "No swap of this lesson is clean. 1 would land with a problem.", a["text"]

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
    assert w["free"] and w["after"] >= w["load"] and w["depts"] and w["allowance"] is not None, w
    assert f"{w['name']} is in {' and '.join(w['depts'])}. Allowance {w['allowance']:g} periods." in o["disturbs"] and not any(" · " in d for d in o["disturbs"]), o["disturbs"]
    t = w["name"]; two = [dict(x, dept2="PE") if x["name"] == t else x for x in spec["teachers"]]   # a second department
    o2 = next(o for o in ask.teachers(m, dict(spec, teachers=two), days, pool, lesson(LESSON))["options"] if o["who"]["name"] == t)
    assert f"{t} is in {w['depts'][0]} and PE. Allowance {w['allowance']:g} periods." in o2["disturbs"], o2["disturbs"]
    bare = [dict(x, dept="", dept2="") if x["name"] == t else x for x in spec["teachers"]]; ix = dict(m["teacher_ix"], **{t: dict(m["teacher_ix"][t], allowance=None)})
    o3 = next(o for o in ask.teachers(dict(m, teacher_ix=ix), dict(spec, teachers=bare), days, pool, lesson(LESSON))["options"] if o["who"]["name"] == t)
    assert not any(d.startswith(t + " is in") or "Allowance" in d for d in o3["disturbs"]), o3["disturbs"]   # no department and no allowance: no line
    o4 = next(o for o in ask.teachers(m, dict(spec, teachers=bare), days, pool, lesson(LESSON))["options"] if o["who"]["name"] == t)
    assert f"Allowance {w['allowance']:g} periods." in o4["disturbs"], o4["disturbs"]   # an allowance alone
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

def test_here_for_a_lesson_of_one_row():
    m, spec, days, pool = now(); w = lambda i: fixes.what(next(x for x in m["lessons"] + pool if x["id"] == i))
    assert ask.here(m, spec, days, pool, lesson(LESSON))["title"] == f"{w(LESSON)} · {days[0]} period {L1} · {T0} · {ROOMS[0]}"
    assert ask.here(m, spec, days, pool, lesson(NO_TEACHER))["title"] == f"{w(NO_TEACHER)} · {days[3]} period {L1 + 2} · no teacher · no room"
    assert ask.here(m, spec, days, pool, lesson(POOLED))["title"] == f"{w(POOLED)} · Not placed · {T1} · no room"
    two = [dict(x, n=2, teachers=[T0, T3]) if x["id"] == LESSON else x for x in m["lessons"]]
    assert ask.here(dict(m, lessons=two), spec, days, pool, lesson(LESSON))["title"] == f"{w(LESSON)} · {days[0]} periods {L1} to {L1 + 1} · {T0}, {T3} · {ROOMS[0]}"

def test_cap():
    m, spec, days, pool = now(); n = len(m["teacher_ix"]); a = ask.teachers(m, spec, days, pool, lesson(NO_TEACHER))
    free = [o for o in a["options"] if o["who"]["free"]]; assert len(free) == ask.MOST and a["more"] > 0, (len(free), a["more"], n)
    cands = [t for t in helper.fixes.choices(m, spec, days, NO_TEACHER, None, pool)["teachers"] if t["free"]]
    assert len(free) + a["more"] == len(cands), (len(free), a["more"], len(cands))
    r = ask.moves(m, spec, days, pool, lesson(POOLED)); assert len([o for o in r["options"] if o["state"] != "no"]) <= ask.MOST
    if r["more"]: assert len(r["options"]) == ask.MOST

# ----------------------------------------------------------------------------------------------- a fresh draft for one test (the base draft is put back after it)
def up(rows, lifts=()):
    r = c.post("/api/draft", data=dict(setup=(io.BytesIO(setup_bytes(SPEC)), "setup.xlsx"), timetable=(io.BytesIO(workbook(rows)), "timetable.xlsx"), replace="1"), content_type="multipart/form-data"); assert r.status_code == 200, r.get_json()
    for i in lifts: draft.fix(dict(kind="lift", id=i))

@contextlib.contextmanager
def fresh(rows, lifts=()):
    up(rows, lifts)
    try: yield now()
    finally: up(ROWS, (POOLED,))

E1, E2, E3 = [t["name"] for t in SPEC["teachers"] if t.get("dept") == "EL"][:3]
MT_SUBJ = next(s["subject"] for s in SPEC["subjects"] if s.get("dept") == "MT")
KA, KB = f"C:{CA}:{SUBJ}", f"C:{CB}:{SUBJ}"
def lw(i, d, p, classes, subj, teachers, n=1, **kw): return dict(id=i, day=DAYS[d], p=p, n=n, level=LEVEL, classes=classes, subject=subj, teachers=teachers, **kw)
def trade(a, b, x, y): return dict(kind="trade", a=a, b=b, x=x, y=y)
def key_name(k): return verify._name(fixes._key(k))
@contextlib.contextmanager
def most(n):
    old = ask.MOST; ask.MOST = n
    try: yield
    finally: ask.MOST = old
def recorded():
    """patch ask.check to record the fixes of every candidate judged -> (list the fixes are appended to, a restore function)"""
    real, seen = ask.check, []
    ask.check = lambda *a, **k: (seen.append(a[4]), real(*a, **k))[1]
    def back(): ask.check = real
    return seen, back
def recorded_judge():
    """patch fixes.judge to record the fix of every candidate judged (the cheap judgement every candidate that passes the emptiness test gets) -> (list of [fix], restore)"""
    real, seen = fixes.judge, []
    fixes.judge = lambda m, spec, days, f, *a, **k: (seen.append([f]), real(m, spec, days, f, *a, **k))[1]
    def back(): fixes.judge = real
    return seen, back
def judged(seen): return [(f["kind"], f.get("id") or f.get("key")) for fx in seen for f in fx]

# ----------------------------------------------------------------------------------------------- swaps alike, places of a lesson not placed
def test_swaps_leave_out_a_lesson_alike_in_every_way():
    rows = [lw(1, 0, L1, [CA], SUBJ, [E1], room=ROOMS[0]), lw(2, 1, L1, [CA], SUBJ, [E1], room=ROOMS[0]), lw(3, 2, L1, [CA], SUBJ2, [E2]), lw(4, 3, L1, [CA], SUBJ, [E1], room=ROOMS[1])]
    with fresh(rows) as (m, spec, days, pool):
        assert typed._sig(m, 1) == typed._sig(m, 2) != typed._sig(m, 4)
        a = ask.swaps(m, spec, days, pool, lesson(1)); got = {o["fixes"][0]["b"] for o in a["options"]}
        assert got == {3, 4} and a["more"] == 0, a   # lesson 2 changes nothing anyone can see; lesson 4 is in another room
        assert a["text"] == "This lesson can swap with 2 lessons.", a["text"]   # and it is not counted
        assert 1 not in {o["fixes"][0]["b"] for o in ask.swaps(m, spec, days, pool, lesson(2))["options"]}

def test_moves_of_a_lesson_not_placed_leave_out_its_classes_lessons():
    grid = SPEC["day_structure"][LEVEL]; free = (4, max(p for p, ch in enumerate(grid[DAYS[4]]) if ch == "L"))   # one period of CB's week left empty
    week = [(d, p) for d in range(5) for p, ch in enumerate(grid[DAYS[d]]) if ch == "L" and (d, p) != free]
    rows = [lw(i, d, p, [CB], (SUBJ, SUBJ2)[i % 2], [T0]) for i, (d, p) in enumerate(week, 1)]
    with fresh(rows, (1,)) as (m, spec, days, pool):   # lesson 1 waits in Not placed: two places are free for CB, its own and the one left empty
        a = ask.moves(m, spec, days, pool, lesson(1)); good = [o for o in a["options"] if o["state"] in helper.OK]
        assert a["options"] and len(good) < 3, a   # so the nearest places judged no are offered after them
        cb = lambda d, p: any(CB in x["classes"] and x["d"] == d and x["p"] <= p < x["p"] + x["n"] for x in m["lessons"])
        assert not [o["fixes"][0] for o in a["options"] if cb(o["fixes"][0]["d"], o["fixes"][0]["p"])], a["options"]   # never on top of another lesson of CB

# ----------------------------------------------------------------------------------------------- trades
def test_trades_found():
    rows = [lw(1, 0, L1, [CA], SUBJ, [E1]), lw(2, 1, L1, [CB], SUBJ, [E2])]
    with fresh(rows) as (m, spec, days, pool):
        a = ask.trades(m, spec, days, pool, lesson(1)); assert ask.TRADES == 40
        assert len(a["options"]) == 1, a; o = a["options"][0]
        assert o["fixes"] == [trade(KA, KB, E1, E2)] and o["apply"] == "yes" and o["state"] in helper.OK and o["text"] == helper.say(m, spec, days, o["fixes"][0]), o
        assert f"It changes 1 lesson of {key_name(KA)} and 1 of {key_name(KB)}." in o["disturbs"], o["disturbs"]
        assert a["stopped"] is False and a["more"] == 0 and a["text"] and a["title"].startswith(fixes.what(m["lessons"][0]) + " · "), a
        n = len(stored()); r = c.post("/api/draft/fix", json=o["fixes"][0]); assert r.status_code == 200 and len(stored()) == n + 1, r.get_json()
        assert stored()[-1]["kind"] == "trade"; assert c.post("/api/draft/undo").status_code == 200 and len(stored()) == n

def test_trades_meet_at_once():
    rows = [lw(1, 0, L1, [CA], SUBJ, [E1]), lw(2, 0, L1, [CB], SUBJ, [E2])]   # both teach at the same time: each simply takes the other's class
    with fresh(rows) as (m, spec, days, pool):
        a = ask.trades(m, spec, days, pool, lesson(1)); assert [o["fixes"][0]["y"] for o in a["options"]] == [E2] and a["options"][0]["apply"] == "yes", a

def test_trades_other():
    rows = [lw(1, 0, L1, [CA], SUBJ, [E1]), lw(2, 1, L1, [CB], MT_SUBJ, [T0]), lw(3, 2, L1, [CC], SUBJ2, [E2])]
    with fresh(rows) as (m, spec, days, pool):
        a = ask.trades(m, spec, days, pool, lesson(1), other=T0)
        assert a["options"] and all(o["fixes"][0]["y"] == T0 and o["fixes"][0]["x"] == E1 for o in a["options"]), a
        assert any(o["fixes"][0]["b"] == f"C:{CB}:{MT_SUBJ}" for o in a["options"]), a   # a key of any subject
        assert not any(o["fixes"][0]["y"] == T0 for o in ask.trades(m, spec, days, pool, lesson(1))["options"])   # without other, a teacher of another department is not tried
        assert ask.trades(m, spec, days, pool, lesson(1), other=E1)["options"] == []   # the lesson's own teacher is not a partner

def test_trades_stopped():
    E4 = [t["name"] for t in SPEC["teachers"] if t.get("dept") == "EL"][3]
    rows = [lw(1, 0, L1, [CA], SUBJ, [E1]), lw(2, 1, L1, [CB], SUBJ, [E2]), lw(3, 2, L1, [CC], SUBJ, [E3]), dict(lw(4, 3, L1, ["2A"], SUBJ, [E4]), level="P2")]
    with fresh(rows) as (m, spec, days, pool):
        whole = ask.trades(m, spec, days, pool, lesson(1)); assert len(whole["options"]) == 3 and whole["stopped"] is False and "were checked" not in whole["text"], whole
        ask.TRADES = 3
        try: a = ask.trades(m, spec, days, pool, lesson(1))
        finally: ask.TRADES = 40
        assert a["stopped"] is False and len(a["options"]) == 3, a   # three candidates, three judged: none left over
        ask.TRADES = 2; seen, back = recorded()
        try: a = ask.trades(m, spec, days, pool, lesson(1))
        finally: ask.TRADES = 40; back()
        assert len(seen) == 2 and a["stopped"] is True and len(a["options"]) == 2 and a["text"].endswith("Only the first 2 possible trades were checked."), a   # every judgement counts

def test_trades_pretest_counts_a_clash_without_judging_it():
    rows = [lw(1, 0, L1, [CA], SUBJ, [E1]), lw(2, 1, L1, [CB], SUBJ, [E2]), lw(3, 0, L1, [CC], MT_SUBJ, [E2])]   # E2 teaches lesson 3 when lesson 1 meets
    with fresh(rows) as (m, spec, days, pool):
        assert fixes.judge(m, spec, days, trade(KA, KB, E1, E2), pool=pool)["state"] == "no"   # what the pre-test saves: a judgement of "no"
        seen, back = recorded_judge()
        try:
            with most(0): a = ask.trades(m, spec, days, pool, lesson(1))
        finally: back()
        assert seen == [] and a["options"] == [] and a["more"] == 1 and a["text"] == "No trade of this lesson is clean. 1 would land with a problem.", (seen, a)
        a = ask.trades(m, spec, days, pool, lesson(1)); (o,) = a["options"]   # shown, it is judged as every option is
        assert o["fixes"] == [trade(KA, KB, E1, E2)] and o["state"] == "no" and o["apply"] == "none" and E2 in o["why"] and a["more"] == 0, a
    rows = [lw(1, 0, L1, [CA], SUBJ, [E1]), lw(2, 1, L1, [CB], SUBJ, [E2]), lw(3, 1, L1, [CC], MT_SUBJ, [E1])]   # E1 teaches lesson 3 when lesson 2 meets
    with fresh(rows) as (m, spec, days, pool):
        seen, back = recorded_judge()
        try:
            with most(0): a = ask.trades(m, spec, days, pool, lesson(1))
        finally: back()
        assert seen == [] and a["text"] == "No trade of this lesson is clean. 1 would land with a problem.", (seen, a)
    rows = [lw(1, 0, L1, [CA], SUBJ, [E1]), lw(2, 0, L1, [CB], SUBJ, [E2])]   # E2 busy then with the lesson E2 gives away: no clash, so it is judged
    with fresh(rows) as (m, spec, days, pool):
        seen, back = recorded_judge()
        try:
            with most(0): a = ask.trades(m, spec, days, pool, lesson(1))
        finally: back()
        assert len(seen) == 1 and a["text"].startswith("1 trade is possible"), (seen, a["text"])

def test_trades_time_budget():
    E4 = [t["name"] for t in SPEC["teachers"] if t.get("dept") == "EL"][3]
    rows = [lw(1, 0, L1, [CA], SUBJ, [E1]), lw(2, 1, L1, [CB], SUBJ, [E2]), lw(3, 2, L1, [CC], SUBJ, [E3]), dict(lw(4, 3, L1, ["2A"], SUBJ, [E4]), level="P2")]
    assert ask.BUDGET == 0.35
    with fresh(rows) as (m, spec, days, pool):
        ask.BUDGET = 0
        try: a = ask.trades(m, spec, days, pool, lesson(1))
        finally: ask.BUDGET = 0.35
        assert a["stopped"] is True and len(a["options"]) == 1 and a["text"].endswith(" Only the first possible trade was checked."), a   # at least one is always checked

def test_trades_text_and_refusals():
    rows = [lw(1, 0, L1, [CA], SUBJ, []), lw(2, 1, L1, [CB], SUBJ, [E2])]
    with fresh(rows) as (m, spec, days, pool):
        a = ask.trades(m, spec, days, pool, lesson(1)); assert a["options"] == [] and a["text"], a   # nobody on the lesson to trade
        raises(ValueError, lambda: ask.trades(m, spec, days, pool, dict(kind="place", by="class", name=CA, d=0, p=0)), "Point at a lesson for this.")

# ----------------------------------------------------------------------------------------------- filling a period
FILL = [lw(1, 0, L1, [CA], SUBJ, [E1]), lw(2, 0, L1 + 2, [CA], SUBJ2, [E2]), lw(3, 1, L1, [CA], SUBJ, [E1], n=2), lw(4, 2, L1, [CA], SUBJ2, [E2]),
        lw(5, 0, L1, [CA], SUBJ, [E3], n=2), lw(6, 0, L1, [CA], SUBJ2, [T0]),
        lw(7, 3, L1, [CA, CB], "Chinese Language", [T0], block=f"{LEVEL} Mother Tongue", group="1CL1"), lw(8, 2, L1 + 1, [CB], SUBJ, [E2])]   # 5 and 6 are lifted: waiting in Not placed
def fill(m, spec, days, pool, by, name, d, p): return ask.fill(m, spec, days, pool, dict(kind="place", by=by, name=name, d=d, p=p))

def test_fill_class():
    with fresh(FILL, (5, 6)) as (m, spec, days, pool), most(1000):   # the cap would show only places and adds
        a = fill(m, spec, days, pool, "class", CA, 4, L1); assert a["options"] and all(o["state"] in helper.OK for o in a["options"]), a
        kinds = [o["fixes"][0]["kind"] for o in a["options"]]; assert kinds[:3] == ["place", "add", "move"], kinds   # taken in turn: the pooled lesson first, then the add, then the move
        place = [o for o in a["options"] if o["fixes"][0]["kind"] == "place"]; assert place and {o["fixes"][0]["id"] for o in place} <= {5, 6} and all(o["fixes"][0]["d"] == 4 and o["fixes"][0]["p"] == L1 for o in place)
        assert place[0]["text"].startswith("Place "), place[0]
        add = [o for o in a["options"] if o["fixes"][0]["kind"] == "add"]; assert add and all(o["fixes"][0]["room"] for o in add), a   # a room from add_room
        assert all(f"It goes in {o['fixes'][0]['room']}." in o["disturbs"] for o in add), [o["disturbs"] for o in add]   # the room Apply uses is said
        assert all(CA in verify.planned_rows(spec)[fixes._key(o["fixes"][0]["key"])]["classes"] for o in add)
        move = [o for o in a["options"] if o["fixes"][0]["kind"] == "move"]; assert move, a
        for o in move: x = next(x for x in m["lessons"] if x["id"] == o["fixes"][0]["id"]); assert (f"Leaves {days[x['d']]} period {x['p']} empty." if x["n"] == 1 else f"Leaves {days[x['d']]} periods {x['p']} to {x['p'] + x['n'] - 1} empty.") in o["disturbs"] and CA in x["classes"], o
        assert a["text"] == f"{len(a['options']) + a['more']} lessons could go here." and a["title"] == f"{CA} · {days[4]} period {L1} · empty", a["text"]
        n = len(stored())
        for o in a["options"]:   # the board accepts each as it stands
            draft.fix(o["fixes"][0]); draft.undo(); assert len(stored()) == n

def test_fill_add_with_no_room():
    with fresh(FILL, (5, 6)) as (m, spec, days, pool), most(1000):
        real = fixes.add_room; fixes.add_room = lambda *a, **k: ""   # every room of its kind in use then
        try: a = fill(m, spec, days, pool, "class", CA, 4, L1)
        finally: fixes.add_room = real
        add = [o for o in a["options"] if o["fixes"][0]["kind"] == "add"]
        assert add and all(o["fixes"][0]["room"] == "" and "No room of its kind is free then, so it has no room." in o["disturbs"] and not any(d.startswith("It goes in") for d in o["disturbs"]) for o in add), [o["disturbs"] for o in add]

def test_fill_overrun():
    with fresh(FILL, (5, 6)) as (m, spec, days, pool), most(1000):
        seen, back = recorded_judge()
        try:
            fill(m, spec, days, pool, "class", CA, 0, L1 + 1)   # the second period of a two-period lesson would hold lesson 2
            assert ("place", 5) not in judged(seen) and ("move", 3) not in judged(seen) and ("place", 6) in judged(seen), judged(seen)
            assert not any(f["kind"] == "add" and f["n"] > 1 for fx in seen for f in fx), seen
            seen.clear(); grid = m["grid"][LEVEL][0]; q = next(q for q in range(len(grid) - 1) if grid[q] == "L" and grid[q + 1] not in "LA")   # the period before a break
            fill(m, spec, days, pool, "class", CA, 4, q); j = judged(seen); assert ("place", 6) in j and ("place", 5) not in j and not any(f["kind"] == "add" and f["n"] > 1 for fx in seen for f in fx), j
            seen.clear(); a = fill(m, spec, days, pool, "class", CA, 4, m["NP"] - 1); assert seen == [] and a["options"] == [], seen   # the last period of the day
            seen.clear(); fill(m, spec, days, pool, "class", CA, 2, L1 + 1)   # the band's other class has lesson 8 then
            assert ("move", 7) not in judged(seen), judged(seen)
            seen.clear(); fill(m, spec, days, pool, "class", CA, 2, L1 + 4); assert ("move", 7) in judged(seen), judged(seen)   # and where it is free the band is tried
        finally: back()
        assert a["text"] == "Nothing fits here without a clash or a broken rule.", a["text"]

def test_fill_teacher():
    with fresh(FILL, (5, 6)) as (m, spec, days, pool), most(1000):
        a = fill(m, spec, days, pool, "teacher", T0, 4, L1); assert a["options"], a
        kinds = {o["fixes"][0]["kind"] for o in a["options"]}; assert kinds == {"place", "add", "move"}, kinds
        for o in a["options"]:
            f = o["fixes"][0]
            if f["kind"] == "place": assert f["id"] == 6   # the only pooled lesson T0 is on
            elif f["kind"] == "add": assert T0 in verify.planned_rows(spec)[fixes._key(f["key"])]["teachers"]
            else: assert T0 in next(x for x in m["lessons"] if x["id"] == f["id"])["teachers"] and f["id"] == 7, f

def test_fill_room():
    g2, g3 = [next(r for r in SPEC["lessons"] if r["level"] == lv and r.get("code") != "Entire Class" and r.get("block") and r.get("periods")) for lv in ("P2", "P3")]
    cl = lambda i, g, room: dict(id=i, day=DAYS[0], p=L1, n=1, level=g["level"], block=g["block"], classes=g["classes"], subject=g["subject"], group=g["code"], teachers=g["teachers"][:1], room=room)
    rows = [lw(1, 0, L1, [CA], SUBJ, [E1]), cl(2, g2, "Computer Lab"), cl(3, g3, ROOMS[1]), lw(4, 1, L1, [CA], SUBJ, [E1])]
    with fresh(rows) as (m, spec, days, pool):
        a = fill(m, spec, days, pool, "room", ROOMS[0], 0, L1)
        got = {o["fixes"][0]["id"]: o for o in a["options"]}; assert set(got) == {1, 2}, a   # no room; a computer lab for a lesson of classrooms; not 3 (right kind already) or 4 (not then)
        assert all(o["fixes"][0]["kind"] == "room" and o["fixes"][0]["room"] == ROOMS[0] and o["state"] in helper.OK for o in a["options"]), a
        assert got[1]["fixes"][0]["group"] == "Entire Class" and got[2]["fixes"][0]["group"] == g2["code"], got
        assert a["text"] == "2 lessons could go here.", a["text"]

def test_fill_room_rulings():
    art = next(r for r in SPEC["lessons"] if r["level"] == LEVEL and r.get("code") == "Entire Class" and r.get("room_kind") not in (None, "", "classroom") and r.get("teachers") and len(r["classes"]) == 1)
    rows = [lw(1, 0, L1, art["classes"], art["subject"], art["teachers"][:1]), lw(2, 0, L1, [x for x in (CA, CB, CC) if x not in art["classes"]][:1], SUBJ, [E1], room="Mystery Room")]
    with fresh(rows) as (m, spec, days, pool):
        assert fixes._room_kind(m, spec, m["lessons"][0]) == art["room_kind"] != "classroom"
        a = fill(m, spec, days, pool, "room", ROOMS[0], 0, L1); ids = {o["fixes"][0]["id"] for o in a["options"]}
        assert 1 not in ids and 2 in ids, a   # a lesson that asks for another kind of room is not offered this classroom; one whose room is not on the setup's list is

def test_fill_interleaves_and_judges_before_it_words():
    rows = [lw(i, 1 + (i - 1) // 3, L1 + (i - 1) % 3 + (0 if (i - 1) % 3 < 2 else 1), [CA], SUBJ2, [E1], ) for i in range(1, 7)] + [lw(i, 0, L1, [CA], SUBJ, [E1]) for i in (7, 8, 9)]
    for i, t in zip(range(1, 10), (E1, E2, E3, E1, E2, E3, E1, E2, E3)): rows[i - 1]["teachers"] = [t]
    with fresh(rows, (7, 8, 9)) as (m, spec, days, pool):
        seen, back = recorded()
        try: a = fill(m, spec, days, pool, "class", CA, 4, L1)
        finally: back()
        kinds = [o["fixes"][0]["kind"] for o in a["options"]]
        assert kinds == ["place", "add", "move", "place", "add", "move", "place", "add"], kinds
        assert len(seen) == ask.MOST and a["more"] > 0 and a["text"] == f"{len(a['options']) + a['more']} lessons could go here.", (len(seen), a["more"])   # check ran for the 8 shown only
        with most(3): assert [o["fixes"][0]["kind"] for o in fill(m, spec, days, pool, "class", CA, 4, L1)["options"]] == ["place", "add", "move"]
    with fresh(FILL, (5, 6)) as (m, spec, days, pool), most(1000):   # a lesson of two periods leaves two
        a = fill(m, spec, days, pool, "class", CA, 4, L1)
        assert any(o["disturbs"][0].startswith(f"Leaves {days[1]} periods {L1} to {L1 + 1} empty.") for o in a["options"] if o["fixes"][0]["kind"] == "move" and o["fixes"][0]["id"] == 3), a

def test_fill_unknown():
    rows = [lw(1, 0, L1, ["9Z"], SUBJ, [UNKNOWN], room="Mystery Room"), lw(2, 1, L1, [CA], SUBJ, [E1])]
    with fresh(rows) as (m, spec, days, pool):
        for by, name in (("class", "9Z"), ("teacher", UNKNOWN), ("room", "Mystery Room")):
            a = fill(m, spec, days, pool, by, name, 3, L1); assert a["text"] and a["title"].startswith(name), (by, a)   # no crash; only lesson 1, which names it, can come
            assert all(o["fixes"][0]["kind"] == "move" and o["fixes"][0]["id"] == 1 for o in a["options"]) and len(a["options"]) <= 1, (by, a)
        a = fill(m, spec, days, pool, "room", "Mystery Room", 0, L1); assert a["options"] == [] and a["text"] == "Nothing fits here without a clash or a broken rule.", a   # the only lesson there is in it already
        a = fill(m, spec, days, pool, "class", "9Z", 0, 0); assert a["options"] == [] and a["text"] == "Nothing fits here without a clash or a broken rule.", a   # not lesson time

def test_fill_refuses_lesson():
    m, spec, days, pool = now()
    raises(ValueError, lambda: ask.fill(m, spec, days, pool, lesson(LESSON)), "Point at an empty period for this.")

# ----------------------------------------------------------------------------------------------- who is free
def free_now(m, d, p, n=1):
    busy = [x for x in m["lessons"] if x["d"] == d and x["p"] < p + n and p < x["p"] + x["n"]]
    return {t for x in busy for t in x["teachers"]}, {x["room"] for x in busy if x["room"]}

def test_free_counts():
    m, spec, days, pool = now(); d, p = 0, L1; bt, br = free_now(m, d, p)
    a = ask.free(m, spec, days, pool, dict(kind="place", by="class", name=CA, d=d, p=p)); assert a["options"] == [] and a["more"] == 0
    ft = [t["name"] for t in SPEC["teachers"] if t["name"] not in bt]; fr = [v["room"] for v in SPEC["venues"] if v["room"] not in br]
    assert a["text"] == f"{len(ft)} teachers and {len(fr)} rooms are free on {days[d]} period {p}.", a["text"]
    lines = {l.split(": ")[0]: l.split(": ")[1].split(", ") for l in a["lines"]}
    teach = {n for k, v in lines.items() for n in v if k in {t.get("dept") for t in SPEC["teachers"]} | {"No department"}}
    assert set(ft) <= teach and not teach & bt and T0 in bt and T3 in bt and ROOMS[0] not in sum(lines.values(), []) and ROOMS[1] not in sum(lines.values(), []), lines
    assert lines["MT"] == [t["name"] for t in SPEC["teachers"] if t.get("dept") == "MT" and t["name"] not in bt]   # one line a department, in the setup's order
    assert any(k.lower().startswith("classroom") for k in lines) and set(lines["Classroom"]) == {r for r in fr if next(v for v in SPEC["venues"] if v["room"] == r).get("kind") == "classroom"}, lines
    l = ask.free(m, spec, days, pool, lesson(BANDID))   # a lesson: its day, period and length
    bt, br = free_now(m, 3, L1, 2); assert l["text"].startswith(f"{len([t for t in SPEC['teachers'] if t['name'] not in bt])} teachers and ") and l["text"].endswith(f"are free on {days[3]} periods {L1} to {L1 + 1}."), l["text"]
    assert T1 in bt and T1 not in sum(([n for n in v] for v in (x.split(": ")[1].split(", ") for x in l["lines"])), [])
    n = ask.free(m, spec, days, pool, lesson(POOLED)); assert n["options"] == [] and n["lines"] == [] and "not placed" in n["text"], n

def test_free_one_of_each():
    m, spec, days, pool = now(); rows = [x for x in m["lessons"] if x["id"] != 10]
    one = ask.free(dict(m, lessons=rows), spec, days, pool, dict(kind="place", by="room", name=ROOMS[0], d=0, p=L1)); bt, br = free_now(dict(m, lessons=rows), 0, L1)
    assert one["text"] == f"{len([t for t in SPEC['teachers'] if t['name'] not in bt])} teachers and {len([v for v in SPEC['venues'] if v['room'] not in br])} rooms are free on {days[0]} period {L1}.", one["text"]
    two = [lw(1, 0, L1, [CA], SUBJ, [E1], room=ROOMS[0])]; tiny = dict(SPEC, teachers=[t for t in SPEC["teachers"] if t["name"] in (E1, E2)], venues=[v for v in SPEC["venues"] if v["room"] in ROOMS])
    with fresh(two) as (m2, spec2, days2, pool2):
        o = ask.free(m2, tiny, days2, pool2, dict(kind="place", by="class", name=CA, d=0, p=L1)); assert o["text"] == f"1 teacher and 1 room are free on {days2[0]} period {L1}.", o["text"]

# ----------------------------------------------------------------------------------------------- rooms: the Task 3 gaps
def test_rooms_right_kind_before_another_kind():
    m, spec, days, pool = now(); old = ask.MOST; ask.MOST = 1000
    try: a = ask.rooms(m, spec, days, pool, lesson(LESSON))
    finally: ask.MOST = old
    kinds = [m["room_ix"][o["fixes"][0]["room"]]["kind"] for o in a["options"] if o["state"] != "no"]
    assert "classroom" in kinds and any(k != "classroom" for k in kinds), kinds
    last = max(i for i, k in enumerate(kinds) if k == "classroom"); assert all(k != "classroom" for k in kinds[last + 1:]) and all(k == "classroom" for k in kinds[:last + 1]), kinds   # the right kind first

def test_rooms_no_room_and_a_room_not_in_the_setup():
    m, spec, days, pool = now(); a = ask.rooms(m, spec, days, pool, lesson(NO_TEACHER))   # lesson 8 has no room
    assert a["options"] and all(o["fixes"][0]["room"] for o in a["options"]) and a["text"].endswith("free for " + fixes.what([x for x in m["lessons"] if x["id"] == NO_TEACHER][0]) + "."), a
    a = ask.rooms(m, spec, days, pool, lesson(POOLED)); assert a["options"] and all(o["text"].startswith("Put ") and o["fixes"][0]["id"] == POOLED for o in a["options"]), a   # a lesson waiting in Not placed
    with fresh([lw(1, 0, L1, [CA], SUBJ, [E1], room="Mystery Room")]) as (m, spec, days, pool):
        a = ask.rooms(m, spec, days, pool, lesson(1)); assert a["options"] and all(o["fixes"][0]["room"] != "Mystery Room" for o in a["options"]), a

# ----------------------------------------------------------------------------------------------- draft.about and the route
def test_about_unknown_question():
    assert ask.QUESTIONS == ("here", "swaps", "moves", "teachers", "trades", "rooms", "fill", "free")
    for q in ("nothing", None, "", "HERE"): raises(ValueError, lambda: draft.about(q, lesson(LESSON)), "That question is not known.")

def test_about_answers_every_question():
    place = dict(kind="place", by="class", name=CB, d=1, p=L1 + 1)
    for q in ask.QUESTIONS:
        a = draft.about(q, place if q in ("fill", "free", "here") else lesson(LESSON))
        assert set(a) >= {"subject", "title", "stamp", "text", "options", "more", "stopped", "lines"}, (q, sorted(a)); assert a["stamp"] == draft.stamp() and a["subject"]["kind"] == ("place" if q in ("fill", "free", "here") else "lesson"), q
    assert draft.about("here", lesson(LESSON))["options"] == [] and draft.about("free", lesson(LESSON))["subject"]["id"] == LESSON
    raises(ValueError, lambda: draft.about("moves", place), "Point at a lesson for this."); raises(ValueError, lambda: draft.about("fill", lesson(LESSON)), "Point at an empty period for this.")
    raises(ValueError, lambda: draft.about("moves", dict(kind="lesson", id=999)), "There is no lesson with that id on the timetable.")
    assert draft.about("trades", lesson(LESSON), other=T1)["options"] is not None

def test_about_route():
    anon = A.app.test_client(); assert anon.get(f"/api/draft/about?q=here&kind=lesson&id={LESSON}").status_code == 401
    stamp = c.get("/api/draft").get_json()["stamp"]
    r = c.get(f"/api/draft/about?q=swaps&kind=lesson&id={LESSON}"); j = r.get_json(); assert r.status_code == 200 and j["title"] and j["stamp"] == stamp and j["options"], j
    r = c.get(f"/api/draft/about?q=teachers&kind=lesson&id={BANDID}&group=G2&teacher={T2}"); j = r.get_json(); assert r.status_code == 200 and j["subject"] == dict(kind="lesson", id=BANDID, group="G2", teacher=T2), j
    r = c.get(f"/api/draft/about?q=fill&kind=place&by=class&name={CB}&d=1&p={L1 + 1}"); j = r.get_json(); assert r.status_code == 200 and j["title"] == f"{CB} · {SPEC['day_structure'] and DAYS[1]} period {L1 + 1} · empty" and j["stamp"] == stamp and "options" in j, j
    r = c.get(f"/api/draft/about?q=trades&kind=lesson&id={LESSON}&other={T1}"); assert r.status_code == 200 and all(o["fixes"][0]["y"] == T1 for o in r.get_json()["options"]), r.get_json()
    bad = lambda url, text: (lambda r: (r.status_code, r.get_json()) == (400, {"error": text}) or (_ for _ in ()).throw(AssertionError((url, r.status_code, r.get_json()))))(c.get(url))
    bad("/api/draft/about?q=here&kind=lesson&id=999", "There is no lesson with that id on the timetable.")
    bad("/api/draft/about?q=here&kind=lesson&id=abc", "There is no lesson with that id on the timetable.")
    bad("/api/draft/about?q=fill&kind=place&by=teacher&name=&d=0&p=1", "Pick a teacher's row.")
    bad("/api/draft/about?q=fill&kind=place&by=class&name=" + CA + "&d=x&p=1", "That is outside the day.")
    bad("/api/draft/about?q=nope&kind=lesson&id=1", "That question is not known.")
    bad("/api/draft/about?q=fill&kind=lesson&id=1", "Point at an empty period for this.")
    bad("/api/draft/about?kind=lesson&id=1", "That question is not known.")

@contextlib.contextmanager
def saved_meanwhile():
    """store.setup_record answers as the setup is on the first call and as a colleague's save left it on every call after (a save in between) ->
    yields the list of the specs fixes.judge saw ("saved": the setup after the save)"""
    real_rec, real_judge, calls, seen = store.setup_record, fixes.judge, [], []
    def rec():
        r = real_rec(); calls.append(1)
        return r if len(calls) == 1 else dict(r, v=r["v"] + 1, spec=dict(r["spec"], _saved=True))
    store.setup_record = rec; fixes.judge = lambda m, spec, *a, **k: (seen.append("saved" if spec.get("_saved") else "named"), real_judge(m, spec, *a, **k))[1]
    try: yield seen
    finally: store.setup_record = real_rec; fixes.judge = real_judge; draft._cache.clear()

def test_a_setup_saved_meanwhile_is_not_judged_on():
    s = draft.stamp(); n = len(stored()); f = mv(LESSON, 1, L1 + 1)
    with saved_meanwhile() as seen:
        try: draft.fix(f, stamp=s)
        except ValueError as e: assert str(e) == draft.MOVED, str(e)   # refused, or judged on the setup its stamp names
        assert seen and seen[0] == "named", seen
    while len(stored()) > n: draft.undo()
    with saved_meanwhile() as seen:
        try: draft.fix_many([f], stamp=s)
        except ValueError as e: assert str(e) == draft.MOVED, str(e)
        assert seen and seen[0] == "named", seen
    while len(stored()) > n: draft.undo()
    with saved_meanwhile() as seen:
        a = draft.about("moves", lesson(LESSON)); assert seen and set(seen) == {"named"} and a["stamp"] == s, (set(seen), a["stamp"], s)   # the answer is of the setup its stamp names
    assert draft.stamp() == s and len(stored()) == n

def test_about_writes_nothing():
    def snap(): return {os.path.join(r, f): open(os.path.join(r, f), "rb").read() for r, _, fs in os.walk(DATA) for f in fs}
    before = snap(); place = dict(kind="place", by="class", name=CB, d=1, p=L1 + 1)
    for q in ask.QUESTIONS:
        draft.about(q, place if q in ("fill", "free", "here") else lesson(LESSON)); draft.about(q, place if q == "here" else lesson(POOLED) if q not in ("fill", "free") else dict(place, by="teacher", name=T0))
        c.get(f"/api/draft/about?q={q}&kind=lesson&id={LESSON}")
    assert snap() == before

if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for f in tests: f(); undo_all()
    print(f"{len(tests)} checks passed")

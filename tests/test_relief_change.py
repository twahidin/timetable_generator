"""Plain-assert tests for changing a relief request (relief piece 2): .venv/bin/python tests/test_relief_change.py"""
import os, secrets, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = tempfile.mkdtemp()
os.environ.pop("HEADS_CODE", None)
os.environ.update(DATA_DIR=DATA, SECRET_KEY=secrets.token_hex(16), AI_PROVIDER="anthropic", AI_API_KEY="", COMMITTEE_CODE=secrets.token_hex(4), TEACHER_CODE=secrets.token_hex(4), STUDENT_CODE=secrets.token_hex(4))
os.environ.pop("SCHOOL_TZ", None)
os.environ.pop("RELIEF_JOBS", None)
sys.path.insert(0, ROOT)
import app as A, store  # noqa: E402,F401
from relief import people as P  # noqa: E402
from relief import lessons as LS  # noqa: E402
from relief import free as FR  # noqa: E402
from relief import absences as AB  # noqa: E402
from relief import settings as RS  # noqa: E402
from accounts import people as AP  # noqa: E402
from ttgen.spec import day_names  # noqa: E402
import datetime, json, shutil  # noqa: E402

def raises(exc, f, text=None):
    try: f()
    except exc as e:
        if text is not None: assert str(e) == text, str(e)
        return
    raise AssertionError("did not raise")

COUNT = 0
def t(f):
    global COUNT
    f(); COUNT += 1
    return f

CAL = dict(terms=[dict(name="Term 4", start="2026-09-07", end="2026-11-20", starts_as="Odd")],
           holidays=[dict(start="2026-10-23", end="2026-10-23", name="Deepavali")])
D = datetime.date
DAYS = day_names(2)
TUE = [d for d in DAYS if d.startswith("Even") and d.split()[-1].startswith("Tue")][0]
FRI = [d for d in DAYS if d.startswith("Even") and d.split()[-1].startswith("Fri")][0]
D13, D16 = D(2026, 10, 13), D(2026, 10, 16)

LS.today = lambda: D(2026, 10, 12)                      # "today" is Mon 12 Oct 2026, as in tests/test_relief_requests.py
NOW = "2026-10-12T09:00:00+08:00"
AB._now = lambda: NOW

FAT = "Flexi Adjunct Teacher"
EVE, SAM, RUTH, MAYA, BUSY, FLEX, NEVER = "Ms Evelyn Koh", "Mr Sam Tan", "Ms Ruth Goh", "Ms Maya Lee", "Mr Busy Chan", "Mr Flex Ng", "Mr Never Yap"
GRACE, TEAMER = "Ms Grace Wong", "Mr Team Lee"

def L(day, p, n, classes, subject, teachers, group="", room="R1"):
    return dict(d=DAYS.index(day), p=p, n=n, classes=classes, subject=subject, group=group, teachers=teachers, room=room, level="Sec 1")

ROWS = [dict(name=EVE, dept="Science"), dict(name=SAM, dept="Science"), dict(name=RUTH, dept="Science"), dict(name=MAYA, dept="Mathematics"),
        dict(name=BUSY, dept="Mathematics"), dict(name=NEVER, dept="PE"), dict(name=FLEX, role=FAT), dict(name=GRACE, dept="Mathematics"),
        dict(name=TEAMER, dept="Mathematics")]
LESSONS = [L(TUE, 2, 3, ["1C"], "Science", [EVE]), L(TUE, 5, 2, ["1A"], "Science", [EVE]), L(TUE, 8, 1, ["5A"], "Art", [EVE, BUSY]),
           L(FRI, 0, 2, ["1A"], "Art", [EVE]), L(TUE, 0, 1, ["2A"], "Science", [SAM]), L(TUE, 9, 1, ["2B"], "Science", [SAM]),
           L(TUE, 2, 1, ["3A"], "Physics", [RUTH]), L(TUE, 6, 1, ["3B"], "Physics", [RUTH]), L(TUE, 6, 1, ["4A"], "Maths", [BUSY]),
           L(FRI, 0, 2, ["3B"], "Maths", [MAYA])]

def world(extra=()):
    pub = P.fake_pub(ROWS, LESSONS + list(extra), roles=[dict(role=FAT, what="Flexi adjunct teachers")])
    pub["model"]["school"].update(start_time="08:00", period_minutes=30)
    pub["model"]["NP"] = 12
    pub["model"]["setup"]["rules"] = []
    return pub

PUB = world()
os.makedirs(os.path.dirname(RS.PATH), exist_ok=True)
store.write_json(RS.PATH, dict(calendar=CAL, limits=dict(fat_per_day=3, other_per_day=None, never=[NEVER]), fat_role=FAT))   # who plans and who is on the team: the accounts
ST = RS.load(PUB)
ADIR = os.path.join(DATA, "relief", "absences")

def key(who, p, date=D13):
    return [x for x in LS.on_date(PUB, CAL, who, date) if x["p"] == p][0]["key"]
K2, K5, K8, KF = key(EVE, 2), key(EVE, 5), key(EVE, 8), key(EVE, 0, D16)
KR2, KR6 = key(RUTH, 2), key(RUTH, 6)

def fresh():
    """every test starts with no absence records"""
    shutil.rmtree(ADIR, ignore_errors=True)

def absent(teacher=EVE, by=None, lessons=(), dates=("2026-10-13",), **kw):
    """an absence of teacher: asked by them (by None), or planned by by with the relief teachers in lessons (stage 2's absences.new)"""
    d = dict(teacher=teacher, dates=list(dates), periods=None, reason="Medical", reason_text="", remarks="", reporting_officer=GRACE, lessons=list(lessons))
    d.update(kw)
    return AB.new(d, PUB, by, "planned", may_choose=True) if by else AB.new(d, PUB, teacher, "asked")

def waiting_choice(i, key, who, by):
    """a planner's choice waiting for the relief team, written as a record from before a head's own choice was approved at once
    holds it (stage 2's shape: relief and relief_by, no pick, no approval; its history kept): for tests about something else
    -> the record"""
    r = AB.load(i); x = AB._lesson(r, key)
    for k in ("pick", "approved", "sent_out", "ack", "change"): x.pop(k, None)
    x.update(relief=who, relief_by=by); AB._save(r)
    return r

def absent_waiting(teacher=EVE, by=GRACE, lessons=(), **kw):
    """as absent planned by by (who is free is checked as it was), each lesson's chosen relief then a waiting choice with no
    history (waiting_choice) -> the record"""
    r = absent(teacher=teacher, by=by, lessons=lessons, **kw)
    for x in lessons:
        if x.get("relief"):
            change = AB.load(r["id"]); AB._lesson(change, x["key"]).pop("history", None); AB._save(change)
            r = waiting_choice(r["id"], x["key"], x["relief"], by)
    return r

def pk(who, by="ai", reason="Teacher 1 is free and teaches Science."):
    return dict(who=who, by=by, reason=reason, at=NOW)

def snap():
    return {f: open(os.path.join(ADIR, f)).read() for f in sorted(os.listdir(ADIR))} if os.path.isdir(ADIR) else {}

def refuses(text, f):
    before = snap()
    raises(ValueError, f, text)
    assert snap() == before, "a refused call wrote something"

def same(got, i):
    """what a call returned is what it saved"""
    assert json.loads(json.dumps(got)) == AB.load(i), "returned and saved records differ"

from relief import fill as FL  # noqa: E402

def plan(i, dates, periods=None, records=None):
    """plan_change of record i over dates and periods, at NOW (writes nothing: checked)"""
    before = snap()
    got = AB.plan_change(AB.load(i), dict(dates=list(dates), periods=periods), PUB, AB.all_records() if records is None else records, None, FL._when(AB._now()))
    assert snap() == before, "plan_change wrote something"
    return got

def keys(xs): return [x["key"] for x in xs]

def change(i, dates, periods=None, by=EVE, why="", **kw):
    return AB.change(i, dict(dates=list(dates), periods=periods, why=why), by, PUB, **kw)


@t
def the_new_sentences_are_exact():
    assert AB.BACKUP == "This relief follows the exam or event schedule: change the duty instead."
    assert AB.NOTHING == "Nothing changes: choose other dates or times."
    assert AB.LOOKED == "The request has changed since you looked: look again before saving."
    assert AB.CHANGED_WHY == "The request changed."
    assert AB._check_periods(PUB, None) is None and AB._check_periods(PUB, (2, 4)) == [2, 4]
    for bad in ([3, 1], [0, 12], [1], "1-2", [True, 2], [-1, 2]):
        raises(ValueError, lambda: AB._check_periods(PUB, bad), "Choose the periods again.")


@t
def a_change_lists_kept_added_and_gone():
    fresh()
    r = absent(by=GRACE, lessons=[dict(key=K2, relief=MAYA), dict(key=K5, relief=SAM)])
    p = plan(r["id"], ["2026-10-13", "2026-10-16"])
    assert keys(p["kept"]) == [K2, K5, K8] and keys(p["added"]) == [KF] and p["gone"] == [], p
    assert p["dates"] == ["2026-10-13", "2026-10-16"] and p["periods"] is None and p["earlier"] == 0 and p["unchanged"] is False, p
    f = p["added"][0]
    assert f["date"] == "2026-10-16" and f["needed"] is True and f["not_needed"] is None and f["relief"] is None and f["relief_by"] is None, f
    assert f["work"] == dict(text="", link="", files=[]) and "stopped" not in f and "_ask" not in f, f
    p = plan(r["id"], ["2026-10-13"], [5, 11])
    assert keys(p["kept"]) == [K5, K8] and p["added"] == [] and keys(p["gone"]) == [K2], p
    assert p["dates"] == ["2026-10-13"] and p["periods"] == [5, 11] and p["unchanged"] is False, p
    assert p["gone"][0]["relief"] == MAYA, "the plan lists the lesson as the record has it"
    p = plan(r["id"], ["2026-10-13"])
    assert p["unchanged"] is True and keys(p["kept"]) == [K2, K5, K8] and p["added"] == p["gone"] == [], p
    assert AB.load(r["id"]) == json.loads(json.dumps(r)), "nothing written"


@t
def saving_keeps_the_cover_of_a_kept_lesson_and_ends_a_dropped_one():
    fresh()
    r = absent(by=GRACE, lessons=[dict(key=K2, relief=MAYA), dict(key=K5, relief=SAM)])
    k5 = AB._lesson(r, K5)
    r2, p = change(r["id"], ["2026-10-13"], [5, 11], by=GRACE, shown=dict(added=[], gone=[K2]))
    assert keys(r2["lessons"]) == [K5, K8] and keys(p["gone"]) == [K2], r2
    x = AB._lesson(r2, K5)
    assert x["relief"] == SAM and x["approved"] == k5["approved"] and x["sent_out"] == k5["sent_out"] and x["history"] == k5["history"], x
    g = r2["gone"][0]
    assert g["key"] == K2 and g["gone"]["why"] == AB.CHANGED_WHY and g["gone"]["at"] == NOW and "work" not in g, g
    assert g["relief"] is None and g["approved"] is None and g["sent_out"] is None, g
    assert g["history"][-1] == dict(what="dropped", who=MAYA, by=GRACE, at=NOW, why=AB.CHANGED_WHY), g["history"]
    assert r2["changes"] == [dict(at=NOW, by=GRACE, why="", dates=["2026-10-13"], periods=[5, 11], before=dict(dates=["2026-10-13"], periods=None),
                                  added=[], gone=[K2], again=False)], r2["changes"]
    assert r2["changed_at"] == NOW and r2["dates"] == ["2026-10-13"] and r2["periods"] == [5, 11], r2
    same(r2, r["id"])
    r3, p = change(r["id"], ["2026-10-13", "2026-10-16"], [0, 1], by=GRACE, why="  Only the first two now  ")
    assert keys(r3["lessons"]) == [KF] and r3["changes"][-1]["why"] == "Only the first two now" and keys(p["gone"]) == [K5, K8], r3
    assert keys(r3["gone"]) == [K2, K5], "a lesson with nothing to keep (K8: not needed, no relief) is not listed in gone"
    assert r3["gone"][-1]["gone"]["why"] == "Only the first two now" and r3["gone"][-1]["history"][-1]["why"] == "Only the first two now", r3["gone"]
    assert r3["changes"][-1]["before"] == dict(dates=["2026-10-13"], periods=[5, 11]) and r3["changes"][-1]["added"] == [KF], r3["changes"]
    assert r3["dates"] == ["2026-10-13", "2026-10-16"] and r3["periods"] == [0, 1], "the dates are the choice's, though no lesson of 13 Oct is left"
    same(r3, r["id"])


@t
def a_dropped_lesson_loses_its_work_files():
    fresh()
    from relief import files as RF
    r = absent(by=GRACE, lessons=[dict(key=K2, relief=MAYA)])
    f2 = RF.save(r["id"], "a.pdf", b"%PDF-1.4 a")
    f5 = RF.save(r["id"], "b.pdf", b"%PDF-1.4 b")
    AB.set_work(r["id"], K2, dict(text="Read", link="", files=[f2], known=[]), EVE)
    AB.set_work(r["id"], K5, dict(text="Do", link="", files=[f5], known=[]), EVE)
    r2, _ = change(r["id"], ["2026-10-13"], [5, 11], by=GRACE)
    assert not RF.path(r["id"], f2["id"]) and RF.path(r["id"], f5["id"]), "the dropped lesson's file goes, a kept one's stays"
    assert [f["id"] for f in AB._lesson(r2, K5)["work"]["files"]] == [f5["id"]], r2


@t
def an_added_lesson_asks_a_planned_teacher_to_acknowledge_again():
    fresh()
    i = absent(by=GRACE, lessons=[dict(key=K2, relief=MAYA)])["id"]
    AB.acknowledge(i, EVE)
    r, _ = change(i, ["2026-10-13", "2026-10-16"], by=GRACE)
    assert r["acknowledged"] is None and r["changes"][-1]["again"] is True and keys(r["lessons"]) == [K2, K5, K8, KF], r
    AB.acknowledge(i, EVE)
    r, _ = change(i, ["2026-10-13"], by=GRACE)
    assert r["acknowledged"] and r["changes"][-1]["again"] is False, "only taking lessons away keeps the acknowledgement"
    r, _ = change(i, ["2026-10-13", "2026-10-16"], by=EVE)
    assert r["acknowledged"] and r["changes"][-1]["again"] is False, "the teacher adding a date herself keeps it"
    r, _ = change(i, ["2026-10-16"], by=TEAMER, team=True)
    assert r["acknowledged"] and keys(r["lessons"]) == [KF], r
    r, _ = change(i, ["2026-10-13"], [5, 11], by=TEAMER, team=True)
    assert r["acknowledged"] is None and r["changes"][-1]["again"] is True, "the relief team adding a needed lesson asks again"
    fresh()
    a = absent()["id"]                                   # an asked record never gains or loses acknowledged
    r, _ = change(a, ["2026-10-13", "2026-10-16"], by=EVE)
    assert r["acknowledged"] is None and r["changes"][-1]["again"] is False, r
    r, _ = change(a, ["2026-10-16"], by=TEAMER, team=True)
    assert r["acknowledged"] is None and r["changes"][-1]["again"] is False, r


@t
def a_started_lesson_is_never_dropped():
    fresh()
    old_today, old_now = LS.today, AB._now
    try:
        LS.today = lambda: D13
        AB._now = lambda: "2026-10-13T10:00:00+08:00"
        i = absent()["id"]
        p = plan(i, ["2026-10-13"], [8, 11])
        assert keys(p["kept"]) == [K2, K8] and keys(p["gone"]) == [K5] and p["added"] == [], p        # K2 began at 09:00, K5 begins 10:30
        assert p["dates"] == ["2026-10-13"] and p["periods"] == [8, 11] and p["earlier"] == 0, p
        r, _ = change(i, ["2026-10-13"], [8, 11])
        assert keys(r["lessons"]) == [K2, K8] and r["periods"] == [8, 11], "the started lesson stays though it is outside the new periods"
        fresh()
        i = absent(dates=("2026-10-13", "2026-10-16"))["id"]
        LS.today = lambda: D16
        AB._now = lambda: "2026-10-16T07:00:00+08:00"
        for dates, periods in ((["2026-10-16"], None), (["2026-10-16"], [0, 0]), (["2026-10-16"], [0, 11])):
            p = plan(i, dates, periods)
            assert p["earlier"] == 3 and keys(p["kept"]) == [KF] and p["gone"] == [] and p["dates"] == ["2026-10-13", "2026-10-16"], p
        refuses(AB.NO_LESSONS, lambda: change(i, ["2026-10-16"], [5, 11]))
        refuses("Choose up to 20 school days, today or later.", lambda: change(i, ["2026-10-13"]))
        AB._now = lambda: "2026-10-16T08:10:00+08:00"          # KF has begun: it stays outside the new periods, and is something to cover
        p = plan(i, ["2026-10-16"], [5, 11])
        assert p["earlier"] == 3 and keys(p["kept"]) == [KF] and p["gone"] == [] and p["dates"] == ["2026-10-13", "2026-10-16"] and p["periods"] == [5, 11], p
        old = dict(AB.load(i)); old["dates"] = ["2026-10-13"]
        refuses(AB.PAST_ABSENCE, lambda: AB.plan_change(old, dict(dates=["2026-10-16"], periods=None), PUB, AB.all_records(), None, FL._when(AB._now())))
    finally:
        LS.today, AB._now = old_today, old_now


@t
def a_change_is_refused_as_a_new_request_is():
    fresh()
    lessons16 = [dict(x, date=x["date"].isoformat()) for x in LS.on_date(PUB, CAL, EVE, D16)]
    b = AB.from_exams(EVE, lessons16, dict(id="s1", kind="exam"), "Exams committee", "Invigilating: X", None)
    refuses(AB.BACKUP, lambda: change(b["id"], ["2026-10-13", "2026-10-16"]))
    refuses(AB.BACKUP, lambda: AB.plan_change(AB.load(b["id"]), dict(dates=["2026-10-16"], periods=None), PUB, AB.all_records(), None, FL._when(NOW)))
    fresh()
    i = absent()["id"]
    refuses(AB.NOT_YOURS, lambda: change(i, ["2026-10-16"], by=SAM))
    refuses(AB.NOTHING, lambda: change(i, ["2026-10-13"]))
    refuses(AB.NOTHING, lambda: change(i, ["2026-10-13"], None, by=GRACE, team=True, why="x"))
    refuses(AB.LOOKED, lambda: change(i, ["2026-10-13", "2026-10-16"], shown=dict(added=[], gone=[])))
    refuses(AB.LOOKED, lambda: change(i, ["2026-10-13"], [5, 11], shown=dict(added=[], gone=[K5])))
    refuses("Fri 23 Oct is not a school day in the calendar.", lambda: change(i, ["2026-10-13", "2026-10-23"]))
    refuses("Choose up to 20 school days, today or later.", lambda: change(i, []))
    refuses("Choose up to 20 school days, today or later.", lambda: change(i, ["2026-10-09"]))
    refuses("Choose the periods again.", lambda: change(i, ["2026-10-13"], [3, 1]))
    refuses(AB.WHY_LONG, lambda: change(i, ["2026-10-16"], why="x" * 201))
    refuses(AB.WRONG, lambda: AB.change(i, "nope", EVE, PUB))
    refuses(AB.NO_LESSONS, lambda: change(i, ["2026-10-13"], [11, 11]))
    other = absent(by=GRACE, dates=("2026-10-16",))
    refuses(f"{GRACE} has already sent an absence for {EVE} on Fri 16 Oct.", lambda: change(i, ["2026-10-13", "2026-10-16"]))
    assert keys(plan(i, ["2026-10-13", "2026-10-16"], records=[x for x in AB.all_records() if x["id"] != other["id"]])["added"]) == [KF]
    r, p = change(i, ["2026-10-13"], [5, 11], by=TEAMER, team=True, why="x" * 200, shown=dict(added=[], gone=[K2]))
    assert keys(r["lessons"]) == [K5, K8] and r["changes"][-1]["by"] == TEAMER and r["changes"][-1]["why"] == "x" * 200, r
    same(r, i)
    AB.cancel(i, "Back at school", EVE)
    refuses(AB.CANCELLED, lambda: change(i, ["2026-10-13"]))


@t
def an_added_lesson_held_by_a_backup_moves_in():
    fresh()
    lessons16 = [dict(x, date=x["date"].isoformat()) for x in LS.on_date(PUB, CAL, EVE, D16)]
    b = AB.from_exams(EVE, lessons16, dict(id="s1", kind="exam"), "Exams committee", "Invigilating: X", None)
    AB.choose(b["id"], KF, SAM, GRACE, PUB)
    y = AB._lesson(AB.load(b["id"]), KF)
    assert y["relief"] == SAM and y["approved"], y
    i = absent()["id"]
    r, p = change(i, ["2026-10-13", "2026-10-16"])
    x = AB._lesson(r, KF)
    assert keys(p["added"]) == [KF] and x["relief"] == SAM and x["approved"] == y["approved"] and x["sent_out"] == y["sent_out"], x
    assert x["history"] == y["history"], x
    o = AB.load(b["id"])
    assert o["cancelled"] == dict(at=NOW, by="app", why="Moved to Ms Evelyn Koh's own absence."), o["cancelled"]
    assert o["lessons"] == [], o
    same(r, i)


@t
def a_backup_with_more_lessons_keeps_the_others():
    fresh()
    lessons = [dict(x, date=x["date"].isoformat()) for d in (D13, D16) for x in LS.on_date(PUB, CAL, EVE, d)]
    b = AB.from_exams(EVE, lessons, dict(id="s1", kind="exam"), "Exams committee", "Invigilating: X", None)
    i = absent(dates=("2026-10-16",))["id"]           # her own absence of Fri took KF over already
    assert keys(AB.load(b["id"])["lessons"]) == [K2, K5, K8], AB.load(b["id"])["lessons"]
    r, p = change(i, ["2026-10-13", "2026-10-16"], [0, 4])
    o = AB.load(b["id"])
    assert keys(p["added"]) == [K2] and keys(r["lessons"]) == [K2, KF], r
    assert o["cancelled"] is None and keys(o["lessons"]) == [K5, K8] and o["dates"] == ["2026-10-13"] and o["periods"] == [5, 8], o


@t
def a_shared_lesson_added_is_not_needed_while_the_co_teacher_is_there():
    fresh()
    i = absent(dates=("2026-10-16",))["id"]
    r, p = change(i, ["2026-10-13", "2026-10-16"])
    assert keys(p["added"]) == [K2, K5, K8], p
    x = AB._lesson(r, K8)
    assert x["needed"] is False and x["not_needed"] == dict(by="app", why="Mr Busy Chan is there") and x["others"] == [BUSY], x
    assert AB._lesson(r, K2)["needed"] is True and AB._lesson(r, K2)["not_needed"] is None
    assert keys(r["lessons"]) == [K2, K5, K8, KF] and r["dates"] == ["2026-10-13", "2026-10-16"] and r["periods"] is None, r


@t
def the_old_gone_still_writes_app():
    fresh()
    r = absent(by=GRACE, lessons=[dict(key=K2, relief=MAYA)])
    x = AB._lesson(r, K2)
    AB._gone(r, x, "The duty changed.")
    assert r["gone"][0]["history"][-1]["by"] == "app" and r["gone"][0]["gone"]["why"] == "The duty changed.", r["gone"]


print(f"{COUNT} relief change tests passed")

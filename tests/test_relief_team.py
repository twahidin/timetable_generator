"""Plain-assert tests for the relief team's module (relief stage 3): .venv/bin/python tests/test_relief_team.py"""
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
store.write_json(RS.PATH, dict(calendar=CAL, team=[TEAMER], management=[GRACE], limits=dict(fat_per_day=3, other_per_day=None, never=[NEVER]), fat_role=FAT))
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

def names(free):
    return [x["name"] for g in free["groups"] for x in g["people"]]

def nf(name): return f"{name} is no longer free then. Choose someone else."

# ---- Task 1: the cover of a lesson and its state ----
from relief import cover as CV  # noqa: E402

def cov(i, ckey):
    r = AB.load(i); x, c = CV.find(r, ckey)
    return r, x, c

def st(i, ckey):
    return CV.state(*cov(i, ckey))

@t
def the_sentences_are_exact():
    assert CV.NOT_FREE.format(name=SAM) == "Mr Sam Tan is no longer free then. Choose someone else."
    assert CV.NOBODY == "Nobody is free then."
    assert CV.PLANNED.format(by=GRACE, date="Sat 17 Oct") == "Planned by Ms Grace Wong on Sat 17 Oct."
    assert CV.NOT_YOURS_COVER == "This relief is not yours."
    assert CV.NOT_WAITING == "This relief is not waiting for approval."
    assert CV.NO_SPLIT == "A lesson of one period cannot be split."
    assert CV.SPLIT_APPROVED == "This lesson's relief is approved already, so it cannot be split."
    assert CV.NO_CHANGE_ASKED == "Nobody has asked to change this relief."
    assert CV.SPLIT_SENT == "Part of this lesson is approved already, so it cannot be joined again."
    assert CV.CHANGE_WHY == "Say in a line why you cannot take it."
    assert AB.PAST_LESSON == "This lesson is in the past." and AB.CHANGED.startswith("Your timetable has changed")

@t
def a_stage_2_record_reads_as_waiting_with_the_planned_reason():
    fresh()
    r = absent(by=GRACE, lessons=[dict(key=K5, relief=SAM)]); i = r["id"]
    x = AB._lesson(r, K5)
    assert "pick" not in x and "approved" not in x and x["relief"] == SAM and x["relief_by"] == GRACE, x
    assert CV.covers(x) == [x] and CV.cover_key(x, 0) == K5 and CV.find(r, K5) == (x, x)
    assert CV.state(r, x, x) == "waiting"
    assert CV.pick_of(r, x) == dict(who=SAM, by="planner", reason=f"Planned by {GRACE} on Mon 12 Oct.", at=NOW)
    o = AB._lesson(r, K2)
    assert CV.state(r, o, o) == "open" and CV.pick_of(r, o) is None
    s = AB._lesson(r, K8)
    assert s["needed"] is False and CV.state(r, s, s) == "cancelled", "a shared lesson with its other teacher there needs no cover"
    refuses(AB.CHANGED, lambda: CV.find(r, "2026-10-13/nope"))
    # written before stage 3 and before relief_by: the planner is whoever sent it, on the day it was sent
    old = json.loads(json.dumps(r)); old["at"] = "2026-10-09T15:00:00+08:00"
    AB._lesson(old, K5)["relief_by"] = None
    AB._save(old)
    r, x, c = cov(i, K5)
    want = dict(who=SAM, by="planner", reason=f"Planned by {GRACE} on Fri 9 Oct.", at="2026-10-09T15:00:00+08:00")
    assert CV.pick_of(r, c) == want and CV.state(r, x, c) == "waiting"
    same(CV.approve(i, K5, TEAMER, PUB, ST), i)
    r, x, c = cov(i, K5)
    assert CV.state(r, x, c) == "approved" and c["pick"] == want and c["approved"] == dict(by=TEAMER, at=NOW), c

@t
def approve_makes_it_approved_and_records_who():
    fresh()
    r = absent(by=GRACE); i = r["id"]
    refuses(CV.NOT_WAITING, lambda: CV.approve(i, K5, TEAMER, PUB, ST))          # open: nothing to approve
    same(AB.choose(i, K5, SAM, GRACE, PUB), i)
    want = dict(who=SAM, by="planner", reason=f"Planned by {GRACE} on Mon 12 Oct.", at=NOW)
    r, x, c = cov(i, K5)
    assert c["relief"] == SAM and c["relief_by"] == GRACE and c["pick"] == want, c
    assert c["history"] == [dict(what="pick", who=SAM, by="planner", at=NOW, why=want["reason"])], c["history"]
    assert CV.state(r, x, c) == "waiting" and CV.pick_of(r, c) == want
    same(CV.approve(i, K5, TEAMER, PUB, ST), i)
    r, x, c = cov(i, K5)
    assert CV.state(r, x, c) == "approved" and c["approved"] == dict(by=TEAMER, at=NOW) and c["relief"] == SAM and c["pick"] == want
    assert c["ack"] is None and c["change"] is None
    assert c["history"][-1] == dict(what="approved", who=SAM, by=TEAMER, at=NOW, why=None), c["history"]
    refuses(CV.NOT_WAITING, lambda: CV.approve(i, K5, TEAMER, PUB, ST))
    refuses(CV.NOT_WAITING, lambda: AB.choose(i, K5, MAYA, GRACE, PUB))           # the planner no longer changes an approved relief
    refuses(CV.NOT_WAITING, lambda: AB.choose(i, K5, None, GRACE, PUB))
    refuses(CV.NOT_WAITING, lambda: CV.approve(i, K8, TEAMER, PUB, ST))           # not needed
    refuses(AB.CHANGED, lambda: CV.approve(i, "nokey", TEAMER, PUB, ST))
    refuses(AB.WRONG, lambda: CV.approve("nope", K5, TEAMER, PUB, ST))
    # the planner takes a waiting choice off: history keeps it
    AB.choose(i, K2, MAYA, GRACE, PUB)
    AB.choose(i, K2, None, GRACE, PUB)
    r, x, c = cov(i, K2)
    assert CV.state(r, x, c) == "open" and c["relief"] is None and c["pick"] is None
    assert [h["what"] for h in c["history"]] == ["pick", "dropped"] and c["history"][-1]["who"] == MAYA and c["history"][-1]["by"] == GRACE
    # over a checked limit is no reason to refuse: a person decides
    fresh()
    absent(teacher=SAM, by=GRACE, lessons=[dict(key=key(SAM, 0), relief=FLEX), dict(key=key(SAM, 9), relief=FLEX)])
    r = absent(by=GRACE, lessons=[dict(key=K2, relief=FLEX)]); i = r["id"]
    r, x, c = cov(i, K2)
    f = [y for g in FR.free_then(PUB, ST, AB.all_records(), dict(x, key=K2), EVE)["groups"] for y in g["people"] if y["name"] == FLEX][0]
    assert f["over"] is True and f["today"] == 2, f
    CV.approve(i, K2, TEAMER, PUB, ST)
    assert st(i, K2) == "approved"

@t
def approve_refuses_someone_no_longer_free():
    fresh()
    r = absent(by=GRACE, lessons=[dict(key=K5, relief=SAM)]); i = r["id"]
    r, x, c = cov(i, K5)
    assert CV.still_free(PUB, ST, AB.all_records(), r, x, c, SAM), "the cover's own relief does not take its own time"
    assert not CV.stale(PUB, ST, AB.all_records(), r, x, c)
    absent(teacher=SAM)                                                          # the picked teacher asks for relief for that date first
    r, x, c = cov(i, K5)
    assert CV.stale(PUB, ST, AB.all_records(), r, x, c) and not CV.still_free(PUB, ST, AB.all_records(), r, x, c, SAM)
    refuses(nf(SAM), lambda: CV.approve(i, K5, TEAMER, PUB, ST))
    assert st(i, K5) == "waiting"
    # teaching then: the published timetable changed under the pick
    AB.choose(i, K5, MAYA, GRACE, PUB)
    refuses(nf(MAYA), lambda: CV.approve(i, K5, TEAMER, world([L(TUE, 6, 1, ["4B"], "Maths", [MAYA])]), ST))
    # on the "never" list since
    never = dict(ST, limits=dict(ST["limits"], never=[MAYA]))
    r, x, c = cov(i, K5)
    assert CV.stale(PUB, never, AB.all_records(), r, x, c)
    refuses(nf(MAYA), lambda: CV.approve(i, K5, TEAMER, PUB, never))
    # given an overlapping relief somewhere else
    other = dict(id="x", teacher=RUTH, dates=["2026-10-13"], periods=None, cancelled=None,
                 lessons=[dict(key=KR6, date="2026-10-13", p=6, n=1, needed=True, relief=MAYA)])
    assert CV.stale(PUB, ST, AB.all_records() + [other], r, x, c)
    assert not CV.stale(PUB, ST, AB.all_records() + [dict(other, cancelled=dict(by=RUTH))], r, x, c)
    assert not CV.stale(PUB, ST, AB.all_records(), r, x, c)
    CV.approve(i, K5, TEAMER, PUB, ST)
    r, x, c = cov(i, K5)
    assert CV.state(r, x, c) == "approved" and c["relief"] == MAYA
    assert CV.stale(PUB, never, AB.all_records(), r, x, c), "an approved relief can go stale too (the page says so)"

@t
def approve_all_skips_the_stale_and_counts_the_rest():
    fresh()
    i = absent(by=GRACE, lessons=[dict(key=K5, relief=SAM), dict(key=K2, relief=MAYA)])["id"]
    j = absent(teacher=RUTH, by=GRACE, lessons=[dict(key=KR6, relief=FLEX)])["id"]
    f = absent(by=GRACE, dates=["2026-10-16"], lessons=[dict(key=KF, relief=SAM)])["id"]
    absent(teacher=SAM)
    got = CV.approve_all(D13, TEAMER, PUB, ST)
    assert got == dict(approved=2, skipped=[dict(ckey=K5, name=SAM, why=nf(SAM))]), got
    assert (st(i, K5), st(i, K2), st(j, KR6), st(f, KF), st(j, KR2)) == ("waiting", "approved", "approved", "waiting", "open")
    assert cov(i, K2)[2]["approved"] == dict(by=TEAMER, at=NOW)
    assert CV.approve_all("2026-10-13", TEAMER, PUB, ST) == dict(approved=0, skipped=[dict(ckey=K5, name=SAM, why=nf(SAM))])
    assert CV.approve_all(D16, GRACE, PUB, ST) == dict(approved=1, skipped=[])
    assert cov(f, KF)[2]["approved"]["by"] == GRACE

@t
def change_chooses_and_approves_in_one():
    fresh()
    r = absent(by=GRACE); i = r["id"]
    same(CV.change(i, K5, FLEX, TEAMER, PUB, ST), i)
    r, x, c = cov(i, K5)
    assert CV.state(r, x, c) == "approved" and c["relief"] == FLEX and c["relief_by"] == TEAMER
    assert c["pick"] == dict(who=FLEX, by="team", reason=f"Chosen by {TEAMER} on Mon 12 Oct.", at=NOW), c["pick"]
    assert c["approved"] == dict(by=TEAMER, at=NOW)
    assert [(h["what"], h["who"], h["by"]) for h in c["history"]] == [("pick", FLEX, "team"), ("changed", FLEX, TEAMER)], c["history"]
    refuses(nf(BUSY), lambda: CV.change(i, K5, BUSY, TEAMER, PUB, ST))               # teaching at P7
    refuses(nf(EVE), lambda: CV.change(i, K5, EVE, TEAMER, PUB, ST))                 # the absent teacher herself
    refuses(nf(NEVER), lambda: CV.change(i, K5, NEVER, TEAMER, PUB, ST))
    refuses(AB.WRONG, lambda: CV.change(i, K5, "", TEAMER, PUB, ST))
    refuses(AB.WRONG, lambda: CV.change(i, K5, ["x"], TEAMER, PUB, ST))
    refuses(AB.NO_NEED, lambda: CV.change(i, K8, SAM, TEAMER, PUB, ST))
    CV.acknowledge(i, K5, FLEX)
    CV.change(i, K5, MAYA, GRACE, PUB, ST)                                           # an acknowledged relief changed: a new acknowledgement is due
    r, x, c = cov(i, K5)
    assert CV.state(r, x, c) == "approved" and c["relief"] == MAYA and c["ack"] is None and c["approved"]["by"] == GRACE
    CV.ask_change(i, K5, "A meeting", MAYA)
    CV.change(i, K5, SAM, TEAMER, PUB, ST)                                           # the team picks someone itself: the request closes
    r, x, c = cov(i, K5)
    assert CV.state(r, x, c) == "approved" and c["relief"] == SAM and c["change"] is None
    assert FR.relief_periods(AB.all_records(), SAM, {D13}) == 2 and FR.relief_periods(AB.all_records(), MAYA, {D13}) == 0

@t
def split_at_a_boundary_gives_two_open_parts_and_join_undoes_it():
    fresh()
    r = absent(by=GRACE); i = r["id"]
    AB.choose(i, K2, SAM, GRACE, PUB)                                                # a waiting planner's choice for P3-P5
    for bad in (2, 5, 1, 9, "3", True, None):
        refuses(AB.WRONG, lambda: CV.split(i, K2, bad, TEAMER))
    same(CV.split(i, K2, 3, TEAMER), i)
    r = AB.load(i); x = AB._lesson(r, K2)
    parts = CV.covers(x)
    assert [(c["p"], c["n"]) for c in parts] == [(2, 1), (3, 2)], parts
    assert [CV.cover_key(x, j) for j in range(2)] == [K2 + "#0", K2 + "#1"]
    assert all(CV.state(r, x, c) == "open" and CV.pick_of(r, c) is None for c in parts)
    assert x["relief"] is None and x["pick"] is None
    assert [(h["what"], h["who"], h["by"]) for h in x["history"]] == [("pick", SAM, "planner"), ("split", SAM, TEAMER)], x["history"]
    refuses(AB.CHANGED, lambda: CV.find(r, K2))
    assert CV.find(r, K2 + "#1") == (x, parts[1])
    refuses(AB.CHANGED, lambda: CV.find(r, K2 + "#2"))
    refuses(AB.WRONG, lambda: CV.split(i, K2, 3, TEAMER))                            # a boundary already
    refuses(CV.NO_SPLIT, lambda: CV.split(i, K2, 2, TEAMER))                         # P3 is a part of one period
    refuses(AB.WRONG, lambda: CV.split(i, K2, 5, TEAMER))
    refuses(AB.WRONG, lambda: CV.split(i, K2, "4", TEAMER))
    refuses(AB.CHANGED, lambda: AB.choose(i, K2, SAM, GRACE, PUB))                   # a split lesson is chosen part by part
    CV.set_pick(i, K2 + "#1", pk(FLEX), PUB, ST)
    assert st(i, K2 + "#1") == "waiting" and st(i, K2 + "#0") == "open"
    same(CV.join(i, K2, TEAMER), i)
    r = AB.load(i); x = AB._lesson(r, K2)
    assert not x.get("parts") and CV.covers(x) == [x] and CV.state(r, x, x) == "open" and x["relief"] is None
    assert [h["what"] for h in x["history"]] == ["pick", "split", "pick", "dropped", "joined"], x["history"]
    assert x["history"][2]["who"] == FLEX and x["history"][3]["who"] == FLEX and x["history"][-1]["by"] == TEAMER
    refuses(AB.CHANGED, lambda: CV.find(r, K2 + "#0"))
    refuses(AB.CHANGED, lambda: CV.join(i, K2, TEAMER))                               # not split

@t
def split_refused_for_one_period_and_after_approval():
    fresh()
    r = absent(by=GRACE, lessons=[dict(key=K8, needed=True)]); i = r["id"]
    refuses(CV.NO_SPLIT, lambda: CV.split(i, K8, 9, TEAMER))
    CV.change(i, K5, FLEX, TEAMER, PUB, ST)
    refuses(CV.SPLIT_APPROVED, lambda: CV.split(i, K5, 6, TEAMER))
    refuses(CV.SPLIT_APPROVED, lambda: CV.split(i, K5, 9, TEAMER)), "approved is said before a period outside"
    CV.split(i, K2, 4, TEAMER)
    CV.change(i, K2 + "#0", MAYA, TEAMER, PUB, ST)
    refuses(CV.SPLIT_SENT, lambda: CV.join(i, K2, TEAMER))
    AB.not_needed(i, K8, "Mr Busy Chan takes it", EVE)
    refuses(AB.NO_NEED, lambda: CV.split(i, K8, 9, TEAMER))

@t
def the_relief_teacher_acknowledges_and_asks_to_change_only_their_own():
    fresh()
    r = absent(by=GRACE, lessons=[dict(key=K5, relief=SAM)]); i = r["id"]
    refuses(CV.NOT_YOURS_COVER, lambda: CV.acknowledge(i, K5, SAM))                  # waiting: not theirs until approved
    refuses(CV.NOT_YOURS_COVER, lambda: CV.ask_change(i, K5, "A meeting", SAM))
    CV.approve(i, K5, TEAMER, PUB, ST)
    for who in (MAYA, EVE, TEAMER, GRACE):
        refuses(CV.NOT_YOURS_COVER, lambda: CV.acknowledge(i, K5, who))
        refuses(CV.NOT_YOURS_COVER, lambda: CV.ask_change(i, K5, "A meeting", who))
    refuses(CV.NOT_YOURS_COVER, lambda: CV.acknowledge(i, K2, SAM))                  # open
    same(CV.acknowledge(i, K5, SAM), i)
    r, x, c = cov(i, K5)
    assert CV.state(r, x, c) == "acknowledged" and c["ack"] == dict(at=NOW)
    assert c["history"][-1] == dict(what="acknowledged", who=SAM, by=SAM, at=NOW, why=None)
    n = len(c["history"])
    CV.acknowledge(i, K5, SAM)                                                       # twice is once
    assert len(cov(i, K5)[2]["history"]) == n
    refuses(CV.CHANGE_WHY, lambda: CV.ask_change(i, K5, "  ", SAM))
    refuses(CV.CHANGE_WHY, lambda: CV.ask_change(i, K5, "x" * 201, SAM))
    refuses(CV.CHANGE_WHY, lambda: CV.ask_change(i, K5, None, SAM))
    same(CV.ask_change(i, K5, " I teach a make-up class then ", SAM), i)
    r, x, c = cov(i, K5)
    assert CV.state(r, x, c) == "change" and c["change"] == dict(why="I teach a make-up class then", at=NOW, pick=None) and c["ack"] is None
    assert c["history"][-1] == dict(what="asked to change", who=SAM, by=SAM, at=NOW, why="I teach a make-up class then")
    assert c["relief"] == SAM and FR.relief_periods(AB.all_records(), SAM, {D13}) == 2, "until the team acts, the relief stays with them"
    refuses(CV.ASKED_ALREADY, lambda: CV.ask_change(i, K5, "Again", SAM))
    CV.acknowledge(i, K5, SAM)                                                       # they take it after all: the request closes
    r, x, c = cov(i, K5)
    assert CV.state(r, x, c) == "acknowledged" and c["change"] is None

@t
def approving_a_change_request_moves_it_and_keep_leaves_it():
    fresh()
    i = absent(by=GRACE)["id"]
    CV.change(i, K5, SAM, TEAMER, PUB, ST)
    CV.ask_change(i, K5, "A meeting", SAM)
    refuses(CV.NOT_WAITING, lambda: CV.approve(i, K5, TEAMER, PUB, ST))             # no new pick yet
    refuses(nf(BUSY), lambda: CV.set_pick(i, K5, pk(BUSY), PUB, ST, into="change"))
    same(CV.set_pick(i, K5, pk(FLEX), PUB, ST, into="change"), i)
    r, x, c = cov(i, K5)
    assert CV.state(r, x, c) == "change" and c["change"]["pick"] == pk(FLEX) and c["relief"] == SAM
    assert c["history"][-1] == dict(what="pick", who=FLEX, by="ai", at=NOW, why=pk(FLEX)["reason"])
    refuses(nf(MAYA), lambda: CV.set_pick(i, K5, pk(MAYA), PUB, ST, into="change"))  # it has its new pick already
    refuses(nf(MAYA), lambda: CV.set_pick(i, K5, pk(MAYA), PUB, ST))                 # not open
    same(CV.approve(i, K5, GRACE, PUB, ST), i)
    r, x, c = cov(i, K5)
    assert CV.state(r, x, c) == "approved" and c["relief"] == FLEX and c["pick"] == pk(FLEX)
    assert c["approved"] == dict(by=GRACE, at=NOW) and c["change"] is None and c["ack"] is None
    assert FR.relief_periods(AB.all_records(), SAM, {D13}) == 0 and FR.relief_periods(AB.all_records(), FLEX, {D13}) == 2
    # the new pick is checked again when approved; Keep leaves the relief where it is
    CV.ask_change(i, K5, "Not today", FLEX)
    CV.set_pick(i, K5, pk(MAYA), PUB, ST, into="change")
    refuses(nf(MAYA), lambda: CV.approve(i, K5, TEAMER, PUB, dict(ST, limits=dict(ST["limits"], never=[MAYA]))))
    refuses(CV.NO_CHANGE_ASKED, lambda: CV.keep(i, K2, TEAMER))
    same(CV.keep(i, K5, TEAMER), i)
    r, x, c = cov(i, K5)
    assert CV.state(r, x, c) == "approved" and c["relief"] == FLEX and c["change"] is None
    assert c["history"][-1] == dict(what="kept", who=FLEX, by=TEAMER, at=NOW, why=None)
    assert "asked to change" in [h["what"] for h in c["history"]] and [h["who"] for h in c["history"] if h["what"] == "pick"][-1] == MAYA
    refuses(CV.NO_CHANGE_ASKED, lambda: CV.keep(i, K5, TEAMER))

@t
def cancel_and_not_needed_end_the_cover_and_its_load():
    fresh()
    i = absent(by=GRACE)["id"]
    CV.change(i, K5, SAM, TEAMER, PUB, ST)
    CV.ask_change(i, K5, "A meeting", SAM)
    CV.set_pick(i, K5, pk(FLEX), PUB, ST, into="change")
    CV.split(i, K2, 3, TEAMER)
    CV.change(i, K2 + "#0", MAYA, TEAMER, PUB, ST)
    CV.set_pick(i, K2 + "#1", pk(FLEX), PUB, ST)
    recs = AB.all_records()
    assert [FR.relief_periods(recs, n, {D13}) for n in (SAM, MAYA, FLEX)] == [2, 1, 2]
    same(AB.not_needed(i, K5, "The class is on a trip", EVE), i)
    r, x, c = cov(i, K5)
    assert CV.state(r, x, c) == "cancelled" and CV.pick_of(r, c) is None
    assert [c[f] for f in ("relief", "relief_by", "pick", "approved", "ack", "change")] == [None] * 6, c
    assert c["history"][-1] == dict(what="dropped", who=SAM, by=EVE, at=NOW, why="The class is on a trip")
    assert FR.relief_periods(AB.all_records(), SAM, {D13}) == 0
    AB.needed_again(i, K5, EVE)
    assert st(i, K5) == "open"
    same(AB.cancel(i, "Better now", EVE), i)
    r = AB.load(i)
    for ck in (K5, K2 + "#0", K2 + "#1"):
        x, c = CV.find(r, ck)
        assert CV.state(r, x, c) == "cancelled" and c["relief"] is None and c["approved"] is None and c["change"] is None, (ck, c)
    assert CV.find(r, K2 + "#0")[1]["history"][-1] == dict(what="dropped", who=MAYA, by=EVE, at=NOW, why="Better now")
    recs = AB.all_records()
    assert [FR.relief_periods(recs, n, {D13}) for n in (SAM, MAYA, FLEX)] == [0, 0, 0]
    assert MAYA in names(FR.free_then(PUB, ST, recs, LS.on_date(PUB, CAL, RUTH, D13)[0], RUTH))
    refuses(AB.CANCELLED, lambda: CV.acknowledge(i, K2 + "#0", MAYA))
    refuses(AB.CANCELLED, lambda: CV.approve(i, K2 + "#1", TEAMER, PUB, ST))
    refuses(AB.CANCELLED, lambda: CV.change(i, K5, MAYA, TEAMER, PUB, ST))
    refuses(nf(MAYA), lambda: CV.set_pick(i, K5, pk(MAYA), PUB, ST))                 # not open: a pick worked out meanwhile is not saved
    # an absence cancelled by stage 2 kept its relief: it still reads cancelled, never stale, and counts nothing
    old = AB.load(i); x = AB._lesson(old, K5); x["relief"] = SAM
    AB._save(old)
    r, x, c = cov(i, K5)
    assert CV.state(r, x, c) == "cancelled" and not CV.stale(PUB, ST, AB.all_records(), r, x, c)
    assert FR.relief_periods(AB.all_records(), SAM, {D13}) == 0

@t
def relief_periods_counts_split_parts_by_their_own_n():
    fresh()
    i = absent(by=GRACE, lessons=[dict(key=K2, relief=FLEX)])["id"]
    assert FR.relief_periods(AB.all_records(), FLEX, {D13}) == 3
    CV.split(i, K2, 3, TEAMER)
    assert FR.relief_periods(AB.all_records(), FLEX, {D13}) == 0
    CV.set_pick(i, K2 + "#0", pk(FLEX), PUB, ST)
    CV.set_pick(i, K2 + "#1", pk(MAYA), PUB, ST)
    recs = AB.all_records()
    assert FR.relief_periods(recs, FLEX, {D13}) == 1 and FR.relief_periods(recs, MAYA, {D13}) == 2
    assert FR.relief_periods(recs, MAYA, {D13}, skip=(EVE, K2 + "#1")) == 0 and FR.relief_periods(recs, MAYA, {D13}, skip=(EVE, K2)) == 2
    assert FR.week_so_far(PUB, CAL, recs, MAYA, D13) == 2 + 2
    # someone given one part is busy only for that part
    ruth2 = [x for x in LS.on_date(PUB, CAL, RUTH, D13) if x["p"] == 2][0]
    free = names(FR.free_then(PUB, ST, recs, ruth2, RUTH))
    assert FLEX not in free and MAYA in free, free
    r = AB.load(i)
    x, c0 = CV.find(r, K2 + "#0"); _, c1 = CV.find(r, K2 + "#1")
    assert CV.still_free(PUB, ST, recs, r, x, c1, MAYA) and CV.still_free(PUB, ST, recs, r, x, c0, FLEX), "a part does not take its own time"
    assert CV.still_free(PUB, ST, recs, r, x, c1, FLEX) and CV.still_free(PUB, ST, recs, r, x, c0, MAYA), "the other part does not overlap"
    whole = names(FR.free_then(PUB, ST, recs, dict(x, date=D13), EVE))
    assert FLEX not in whole and MAYA not in whole, "for the whole lesson both are taken"

@t
def set_pick_drop_and_stale():
    fresh()
    i = absent(by=GRACE)["id"]
    refuses(nf(BUSY), lambda: CV.set_pick(i, K5, pk(BUSY), PUB, ST))                 # teaching at P7
    refuses(nf(MAYA), lambda: CV.set_pick(i, K5, pk(MAYA), PUB, ST, into="change"))  # not asked to change
    refuses(AB.WRONG, lambda: CV.set_pick(i, K5, dict(who=MAYA, by="someone", reason="x", at=NOW), PUB, ST))
    refuses(AB.WRONG, lambda: CV.set_pick(i, K5, "Ms Maya Lee", PUB, ST))
    same(CV.set_pick(i, K5, pk(SAM), PUB, ST), i)
    r, x, c = cov(i, K5)
    assert CV.state(r, x, c) == "waiting" and c["relief"] == SAM and c["relief_by"] is None and c["pick"] == pk(SAM)
    assert c["history"] == [dict(what="pick", who=SAM, by="ai", at=NOW, why=pk(SAM)["reason"])]
    refuses(nf(MAYA), lambda: CV.set_pick(i, K5, pk(MAYA), PUB, ST))                 # not open any more
    CV.set_pick(i, K2, pk(SAM, "app", "Picked by the app's own order: the AI was not available."), PUB, ST)   # P3-P5 does not overlap P6-P7
    j = absent(teacher=RUTH)["id"]
    refuses(nf(SAM), lambda: CV.set_pick(j, KR6, pk(SAM), PUB, ST))                  # RUTH's P7 overlaps SAM's P6-P7
    r, x, c = cov(i, K5)
    assert not CV.stale(PUB, ST, AB.all_records(), r, x, c)
    absent(teacher=SAM)
    r, x, c = cov(i, K5)
    assert CV.stale(PUB, ST, AB.all_records(), r, x, c)
    same(CV.drop(i, K5, nf(SAM)), i)
    r, x, c = cov(i, K5)
    assert CV.state(r, x, c) == "open" and c["relief"] is None and c["pick"] is None
    assert c["history"][-1] == dict(what="dropped", who=SAM, by="app", at=NOW, why=nf(SAM))
    assert not CV.stale(PUB, ST, AB.all_records(), r, x, c), "an open cover is never stale"
    refuses(CV.NOT_WAITING, lambda: CV.drop(i, K5, "x"))
    CV.change(i, K5, MAYA, TEAMER, PUB, ST)
    refuses(CV.NOT_WAITING, lambda: CV.drop(i, K5, "x"))                              # an approved one is never dropped
    assert st(i, K2) == "waiting" and cov(i, K2)[2]["pick"]["by"] == "app"

@t
def actions_on_an_ended_lesson_are_refused():
    fresh()
    i = absent(by=GRACE, lessons=[dict(key=K5, relief=SAM)])["id"]
    CV.change(i, K2, MAYA, TEAMER, PUB, ST)
    j = absent(teacher=RUTH)["id"]
    old = LS.today
    try:
        LS.today = lambda: D(2026, 10, 14)
        PAST = AB.PAST_LESSON
        refuses(PAST, lambda: CV.approve(i, K5, TEAMER, PUB, ST))
        refuses(PAST, lambda: CV.approve_all(D13, TEAMER, PUB, ST))
        refuses(PAST, lambda: CV.change(i, K5, FLEX, TEAMER, PUB, ST))
        refuses(PAST, lambda: CV.set_pick(j, KR6, pk(FLEX), PUB, ST))
        refuses(PAST, lambda: CV.drop(i, K5, "x"))
        refuses(PAST, lambda: CV.split(i, K5, 6, TEAMER))
        refuses(PAST, lambda: CV.join(i, K5, TEAMER))
        refuses(PAST, lambda: CV.keep(i, K2, TEAMER))
        refuses(PAST, lambda: CV.acknowledge(i, K2, MAYA))
        refuses(PAST, lambda: CV.ask_change(i, K2, "A meeting", MAYA))
    finally: LS.today = old
    CV.approve(i, K5, TEAMER, PUB, ST)
    CV.acknowledge(i, K2, MAYA)
    assert (st(i, K5), st(i, K2)) == ("approved", "acknowledged")

# ---- Task 1 fix round 1 ----
def whats(c): return [(h["what"], h["who"], h["by"]) for h in c.get("history") or []]

@t
def approve_all_approves_a_waiting_split_part():
    fresh()
    i = absent(by=GRACE)["id"]
    CV.split(i, K2, 3, TEAMER)
    CV.set_pick(i, K2 + "#1", pk(FLEX), PUB, ST)
    assert CV.approve_all(D13, TEAMER, PUB, ST) == dict(approved=1, skipped=[])
    assert (st(i, K2 + "#0"), st(i, K2 + "#1")) == ("open", "approved")
    assert cov(i, K2 + "#1")[2]["approved"] == dict(by=TEAMER, at=NOW)
    absent(teacher=SAM)
    CV.set_pick(i, K2 + "#0", pk(MAYA), PUB, ST)
    r = AB.load(i); x = AB._lesson(r, K2); x["parts"][0]["relief"] = SAM; x["parts"][0]["pick"] = pk(SAM)   # SAM is away now
    AB._save(r)
    assert CV.approve_all(D13, TEAMER, PUB, ST) == dict(approved=0, skipped=[dict(ckey=K2 + "#0", name=SAM, why=nf(SAM))])

@t
def cancel_across_a_past_and_a_future_date_keeps_the_past_relief():
    fresh()
    k27 = key(EVE, 5, D(2026, 10, 27))
    i = absent(by=GRACE, dates=["2026-10-13", "2026-10-27"], lessons=[dict(key=K5, relief=SAM), dict(key=k27, relief=SAM)])["id"]
    CV.approve(i, K5, TEAMER, PUB, ST)
    CV.approve(i, k27, TEAMER, PUB, ST)
    old = LS.today
    try:
        LS.today = lambda: D(2026, 10, 14)
        AB.cancel(i, "Back early", GRACE)
    finally: LS.today = old
    r = AB.load(i)
    x, c = CV.find(r, K5)
    assert c["relief"] == SAM and c["approved"] == dict(by=TEAMER, at=NOW) and c["pick"]["who"] == SAM, "the lesson before today keeps what it had"
    assert whats(c)[-1] == ("approved", SAM, TEAMER) and CV.state(r, x, c) == "cancelled"
    x, c = CV.find(r, k27)
    assert c["relief"] is None and c["approved"] is None and c["pick"] is None
    assert whats(c)[-1] == ("dropped", SAM, GRACE) and c["history"][-1]["why"] == "Back early"

@t
def acknowledging_during_a_change_request_drops_its_new_pick():
    fresh()
    i = absent(by=GRACE)["id"]
    CV.change(i, K5, SAM, TEAMER, PUB, ST)
    CV.ask_change(i, K5, "A meeting", SAM)
    CV.set_pick(i, K5, pk(FLEX), PUB, ST, into="change")
    same(CV.acknowledge(i, K5, SAM), i)
    r, x, c = cov(i, K5)
    assert CV.state(r, x, c) == "acknowledged" and c["relief"] == SAM and c["change"] is None
    assert whats(c)[-3:] == [("pick", FLEX, "ai"), ("dropped", FLEX, SAM), ("acknowledged", SAM, SAM)], whats(c)

@t
def a_lesson_splits_into_three_parts_and_keys_keep_their_part():
    fresh()
    i = absent(by=GRACE)["id"]
    CV.split(i, K2, 4, TEAMER)                                                       # P3-P4 and P5
    CV.set_pick(i, K2 + "#0", pk(SAM), PUB, ST)
    CV.change(i, K2 + "#1", MAYA, TEAMER, PUB, ST)
    same(CV.split(i, K2, 3, TEAMER), i)                                              # the waiting part P3-P4 splits; P5 keeps its key
    r = AB.load(i); x = AB._lesson(r, K2)
    assert [(c["p"], c["n"]) for c in CV.covers(x)] == [(2, 1), (4, 1), (3, 1)], CV.covers(x)
    assert [CV.state(r, x, c) for c in CV.covers(x)] == ["open", "approved", "open"]
    assert CV.find(r, K2 + "#1")[1]["relief"] == MAYA and CV.find(r, K2 + "#2")[1]["p"] == 3
    assert whats(x)[-1] == ("split", SAM, TEAMER) and whats(CV.find(r, K2 + "#0")[1])[0] == ("pick", SAM, "ai")
    for at in (2, 3, 4):                                                             # every part is one period now (P5 approved too:
        refuses(CV.NO_SPLIT, lambda: CV.split(i, K2, at, TEAMER))                    # one period is what stops it)
    CV.set_pick(i, K2 + "#2", pk(FLEX), PUB, ST)
    recs = AB.all_records()
    assert [FR.relief_periods(recs, n, {D13}) for n in (MAYA, FLEX, SAM)] == [1, 1, 0]
    refuses(CV.SPLIT_SENT, lambda: CV.join(i, K2, TEAMER))
    # three parts of a longer lesson, none approved, joined again
    fresh()
    j = absent(by=GRACE)["id"]
    CV.split(j, K2, 3, TEAMER); CV.split(j, K2, 4, TEAMER)
    r = AB.load(j); x = AB._lesson(r, K2)
    assert sorted((c["p"], c["n"]) for c in CV.covers(x)) == [(2, 1), (3, 1), (4, 1)] and len(CV.covers(x)) == 3
    CV.join(j, K2, TEAMER)
    assert st(j, K2) == "open" and [h["what"] for h in AB._lesson(AB.load(j), K2)["history"]] == ["split", "split", "joined"]
    # only the part holding the period is asked: an approved part of two periods is not split, an open one beside it is
    CV.split(j, K2, 3, TEAMER)
    CV.change(j, K2 + "#1", MAYA, TEAMER, PUB, ST)                                   # P4-P5 approved
    refuses(CV.SPLIT_APPROVED, lambda: CV.split(j, K2, 4, TEAMER))
    refuses(CV.NO_SPLIT, lambda: CV.split(j, K2, 2, TEAMER))

@t
def the_planners_pick_stays_in_history():
    fresh()
    planned = ("pick", SAM, "planner")
    reason = f"Planned by {GRACE} on Mon 12 Oct."
    i = absent(by=GRACE, lessons=[dict(key=K5, relief=SAM), dict(key=K2, relief=SAM)])["id"]  # stage 2's new: no pick, no history
    assert "history" not in cov(i, K5)[2]
    CV.approve(i, K5, TEAMER, PUB, ST)
    c = cov(i, K5)[2]
    assert whats(c) == [planned, ("approved", SAM, TEAMER)] and c["history"][0]["why"] == reason and c["history"][0]["at"] == NOW
    CV.ask_change(i, K5, "A meeting", SAM)
    CV.set_pick(i, K5, pk(FLEX), PUB, ST, into="change")
    CV.approve(i, K5, TEAMER, PUB, ST)
    c = cov(i, K5)[2]
    assert c["pick"] == pk(FLEX) and whats(c)[0] == planned and c["history"][0]["why"] == reason, "the planner's pick outlives the new one"
    assert whats(c) == [planned, ("approved", SAM, TEAMER), ("asked to change", SAM, SAM), ("pick", FLEX, "ai"), ("approved", FLEX, TEAMER)], whats(c)
    # change, choose, drop, not needed and cancel each write the planner's pick down before they end it
    CV.change(i, K2, MAYA, TEAMER, PUB, ST)
    assert whats(cov(i, K2)[2]) == [planned, ("pick", MAYA, "team"), ("changed", MAYA, TEAMER)]
    fresh()
    i = absent(by=GRACE, lessons=[dict(key=K5, relief=SAM), dict(key=K2, relief=SAM)])["id"]
    AB.choose(i, K5, MAYA, GRACE, PUB)
    assert whats(cov(i, K5)[2]) == [planned, ("dropped", SAM, GRACE), ("pick", MAYA, "planner")]
    AB.choose(i, K5, MAYA, GRACE, PUB)                                               # the same person again is not a drop
    assert [w for w, _, _ in whats(cov(i, K5)[2])] == ["pick", "dropped", "pick", "pick"]
    CV.drop(i, K2, nf(SAM))
    assert whats(cov(i, K2)[2]) == [planned, ("dropped", SAM, "app")]
    fresh()
    i = absent(by=GRACE, lessons=[dict(key=K5, relief=SAM), dict(key=K2, relief=MAYA)])["id"]
    AB.not_needed(i, K5, "On a trip", EVE)
    assert whats(cov(i, K5)[2]) == [planned, ("dropped", SAM, EVE)]
    AB.cancel(i, "Better now", EVE)
    assert whats(cov(i, K2)[2]) == [("pick", MAYA, "planner"), ("dropped", MAYA, EVE)]
    fresh()
    i = absent(by=GRACE, lessons=[dict(key=K2, relief=SAM)])["id"]
    CV.split(i, K2, 3, TEAMER)
    assert whats(AB._lesson(AB.load(i), K2)) == [planned, ("split", SAM, TEAMER)]

# ---- Task 2: the pick: the app's own order and the AI's, checked ----
import re, time, typed  # noqa: E402
from relief import pick as PK  # noqa: E402
for _k in ("ANTHROPIC_API_KEY", "TYPED_REQUEST_MODEL", "AI_MODEL"): os.environ.pop(_k, None)   # no key and no practice picker unless a test says so
REAL = []                                                                        # every time a test reached the real call
REAL_CALL = PK._call
def _never(data):
    REAL.append(1); raise AssertionError("the real client")
PK._call = _never                                                                # never the real client (as tests/smoke.py does for typed)

class env:
    """patch os.environ for a block: env(A="1", B=None) (None removes)"""
    def __init__(s, **kw): s.kw = kw
    def __enter__(s):
        s.old = {k: os.environ.get(k) for k in s.kw}
        for k, v in s.kw.items(): os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
    def __exit__(s, *a):
        for k, v in s.old.items(): os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)

def pt(f):
    """a pick test: no hook, an empty guard"""
    PK.CALL = None; PK._seen.clear()
    try: return t(f)
    finally: PK.CALL = None; PK._seen.clear()

SAYS = []
def says(label, reason):
    """a stand-in for the model: records the data it is sent and answers label and reason"""
    def call(data):
        SAYS.append(data); return dict(label=label, reason=reason)
    return call

APP = dict(who=FLEX, by="app", reason="Picked by the app's own order: the AI was not available.", at=NOW)
ORDER5 = [FLEX, SAM, TEAMER, GRACE, MAYA]                                       # K5 with nobody given relief yet
WEEK0 = dict(Mon=0, Tue=0, Wed=0, Thu=0, Fri=0)
SHORTS = {EVE: "EKH", SAM: "STN", RUTH: "RGH", MAYA: "Lee", BUSY: "Mr Busy", FLEX: "FNG", NEVER: "NYP", GRACE: "GWG", TEAMER: "TLE"}   # Lee: inside Mr Team Lee's name; Mr Busy: the start of his

def shorts_pub():
    pub = world()
    for x in pub["model"]["setup"]["teachers"]: x["short"] = SHORTS[x["name"]]
    return pub

def choose(i, ckey, call=None, st=None, pub=None, **kw):
    r, x, c = cov(i, ckey)
    return PK.choose_for(pub or PUB, st or ST, AB.all_records(), r, x, c, call=call, **kw)

def by_label(data, lab): return next(x for x in data["teachers"] if x["label"] == lab)

@pt
def app_order_puts_flexi_adjunct_first_then_lightest_week():
    def row(name, fat=False, g=2, marks=(), week=0, term=0): return dict(name=name, fat=fat, g=g, marks=list(marks), week=week, term=term)
    rows = [row("A", week=1), row("B", fat=True, week=5), row("C", fat=True, g=0, week=9), row("D", g=0, marks=["prefers not"]),
            row("E", g=0, week=3), row("F", g=1, week=7), row("H", week=1, term=2), row("G", week=1),
            row("I", fat=True, g=0, week=1, marks=["department meeting time"])]
    assert [x["name"] for x in PK.app_order(rows)] == ["C", "I", "B", "E", "D", "F", "A", "G", "H"], [x["name"] for x in PK.app_order(rows)]
    assert [x["name"] for x in rows][:2] == ["A", "B"], "the list given is not reordered"
    fresh()
    i = absent(by=GRACE, dates=["2026-10-13", "2026-10-16"])["id"]
    r, x, c = cov(i, K5)
    short = PK.shortlist(PUB, ST, AB.all_records(), r, x, c)
    assert [y["name"] for y in PK.app_order(short)] == ORDER5, [y["name"] for y in PK.app_order(short)]
    assert {y["name"]: y["g"] for y in short} == {SAM: 0, FLEX: 2, TEAMER: 2, GRACE: 2, MAYA: 2}
    # Friday's Art: the Science teachers teach other subjects (group 1); Ruth and Sam tie on the week, so by name
    r, x, c = cov(i, KF)
    short = PK.shortlist(PUB, ST, AB.all_records(), r, x, c)
    assert {y["name"]: y["g"] for y in short} == {SAM: 1, RUTH: 1, FLEX: 2, BUSY: 2, TEAMER: 2, GRACE: 2}, {y["name"]: y["g"] for y in short}
    assert [y["name"] for y in PK.app_order(short)] == [FLEX, SAM, RUTH, TEAMER, GRACE, BUSY]

@pt
def over_the_limit_is_not_on_the_shortlist():
    fresh()
    absent(teacher=SAM, by=GRACE, lessons=[dict(key=key(SAM, 0), relief=FLEX), dict(key=key(SAM, 9), relief=FLEX)])   # Flex has 2 periods that day
    i = absent(by=GRACE)["id"]
    j = absent(teacher=RUTH)["id"]
    r, x, c = cov(i, K5)
    recs = AB.all_records()
    f = [y for g in FR.free_then(PUB, ST, recs, dict(x, key=K5), EVE)["groups"] for y in g["people"] if y["name"] == FLEX]
    assert f and f[0]["over"] is True, "free then, but 2 + 2 is over the 3 a day"
    short = PK.shortlist(PUB, ST, recs, r, x, c)
    assert sorted(y["name"] for y in short) == sorted([TEAMER, GRACE, MAYA]) and not any(y["over"] for y in short), short
    assert choose(i, K5) == dict(APP, who=TEAMER)
    r, x, c = cov(j, KR2)                                                        # one period: 2 + 1 is the limit, not over it
    assert PK.app_order(PK.shortlist(PUB, ST, recs, r, x, c))[0]["name"] == FLEX

@pt
def nothing_sent_carries_a_name_or_a_reason():
    fresh()
    pub = shorts_pub()
    staff = P.people(pub, ST.get("extra_staff"))
    assert {p["name"]: p["short"] for p in staff} == SHORTS
    i = absent(by=GRACE, reason="Child sick", reason_text="Zebracrossing appendix", remarks="Quokka marmalade remark")["id"]
    rec = AB.load(i)
    assert rec["reporting_officer"] == GRACE and rec["remarks"] == "Quokka marmalade remark"
    AB._lesson(rec, K5)["work"] = dict(text="Photosynthesis worksheet xylophone", link="https://example.com/kumquat-folder",
                                       files=[dict(id="kiwifile9", name="narwhal-notes.pdf", size=10)])
    AB._save(rec)
    rules = ["Use planned relief first.", f"Ask {SAM} before {MAYA}; never {EVE}, ms evelyn koh or her friend RGH.",
             f"Then {TEAMER} or Lee, then STN, then FNG's colleagues; never {BUSY}; Leeds is a city."]
    st = dict(ST, rules=rules)
    r, x, c = cov(i, K5)
    assert x["work"]["text"].startswith("Photosynthesis")
    data, names = PK.labelled(PK.shortlist(pub, st, AB.all_records(), r, x, c), r, x, c, st, staff)
    sent = json.dumps(data, ensure_ascii=False)
    for name in SHORTS: assert name.lower() not in sent.lower(), name
    for s in SHORTS.values(): assert not re.search(rf"(?<!\w){re.escape(s)}(?!\w)", sent), s
    for word in ("child sick", "zebracrossing", "appendix", "quokka", "marmalade", "photosynthesis", "worksheet", "xylophone", "kumquat",
                 "example.com", "narwhal", "kiwifile9", "1A", "R1"):
        assert word.lower() not in sent.lower(), word
    assert names == {f"Teacher {n}": who for n, who in enumerate(ORDER5, 1)}, names
    assert data["rules"] == ["Use planned relief first.",
                             "Ask Teacher 2 before Teacher 5; never another teacher, another teacher or her friend another teacher.",
                             "Then Teacher 3 or Teacher 5, then Teacher 2, then Teacher 1's colleagues; never another teacher; Leeds is a city."], data["rules"]
    # the exact shape
    assert set(data) == {"lesson", "teachers", "rules", "limits"}
    assert data["lesson"] == dict(subject="Science", level="Sec 1", periods="P6–P7", weekday="Tue", date="2026-10-13"), data["lesson"]
    assert data["limits"] == dict(flexi_adjunct_per_day=3, others_per_day=None)
    assert [x["label"] for x in data["teachers"]] == [f"Teacher {n}" for n in range(1, 6)]
    keys = {"label", "departments", "subjects", "teaches_this_subject", "flexi_adjunct", "teaching_this_week", "relief_this_week", "relief_today",
            "relief_this_term", "relief_today_at", "relief_by_day", "marks"}
    assert all(set(x) == keys for x in data["teachers"]), data["teachers"]
    assert by_label(data, "Teacher 2") == dict(label="Teacher 2", departments=["Science"], subjects=["Science"], teaches_this_subject=True,
                                               flexi_adjunct=False, teaching_this_week=2, relief_this_week=0, relief_today=0, relief_this_term=0,
                                               relief_today_at=[], relief_by_day=WEEK0, marks=[]), by_label(data, "Teacher 2")
    t1, t5 = by_label(data, "Teacher 1"), by_label(data, "Teacher 5")
    assert t1["flexi_adjunct"] is True and t1["departments"] == [] and t1["teaches_this_subject"] is False and t1["teaching_this_week"] == 0
    assert t5["departments"] == ["Mathematics"] and t5["subjects"] == ["Maths"] and t5["teaching_this_week"] == 2
    # what the model gets is exactly this
    del SAYS[:]
    choose(i, K5, call=says("Teacher 1", "Teacher 1 is free."), st=st, pub=pub)
    assert len(SAYS) == 1 and json.dumps(SAYS[0], ensure_ascii=False) == sent

@pt
def the_numbers_sent_are_the_relief_already_given():
    fresh()
    k27 = key(EVE, 5, D(2026, 10, 27))
    i = absent(by=GRACE, dates=["2026-10-13", "2026-10-16", "2026-10-27"])["id"]
    CV.split(i, K2, 3, TEAMER)                                                   # P3, and P4-P5
    CV.set_pick(i, K2 + "#0", pk(SAM), PUB, ST)
    CV.set_pick(i, k27, pk(SAM), PUB, ST)                                        # the same term, another week
    # the part P4-P5 is picked for on its own periods and key: Ruth (Physics at P3 and P7) is free for it
    r, x, c = cov(i, K2 + "#1")
    short = PK.shortlist(PUB, ST, AB.all_records(), r, x, c)
    assert {y["name"]: y["g"] for y in short}.get(RUTH) == 1, short
    data, names = PK.labelled(short, r, x, c, ST, P.people(PUB, []))
    assert data["lesson"]["periods"] == "P4–P5"
    sam = by_label(data, next(k for k, v in names.items() if v == SAM))
    assert sam["relief_today_at"] == ["P3"] and sam["relief_today"] == 1, sam
    CV.set_pick(i, K2 + "#1", pk(MAYA), PUB, ST)
    data, names = PK.labelled(PK.shortlist(PUB, ST, AB.all_records(), r, x, c), r, x, c, ST, P.people(PUB, []))
    maya = by_label(data, next(k for k, v in names.items() if v == MAYA))
    assert maya["relief_today_at"] == [] and maya["relief_today"] == 0 and maya["relief_this_week"] == 0, "this cover is not counted against itself"
    # Tuesday P6-P7: Sam has P3 that day, Maya P4-P5
    r, x, c = cov(i, K5)
    data, names = PK.labelled(PK.shortlist(PUB, ST, AB.all_records(), r, x, c), r, x, c, ST, P.people(PUB, []))
    assert names == {f"Teacher {n}": who for n, who in enumerate(ORDER5, 1)}, names
    assert {k: v for k, v in by_label(data, "Teacher 2").items() if k.startswith(("relief", "teaching"))} == dict(
        teaching_this_week=2, relief_this_week=1, relief_today=1, relief_this_term=3, relief_today_at=["P3"], relief_by_day=dict(WEEK0, Tue=1))
    assert {k: v for k, v in by_label(data, "Teacher 5").items() if k.startswith(("relief", "teaching"))} == dict(
        teaching_this_week=2, relief_this_week=2, relief_today=2, relief_this_term=2, relief_today_at=["P4–P5"], relief_by_day=dict(WEEK0, Tue=2))
    # Friday: none of it is today's, all of it is this week's
    r, x, c = cov(i, KF)
    data, names = PK.labelled(PK.shortlist(PUB, ST, AB.all_records(), r, x, c), r, x, c, ST, P.people(PUB, []))
    sam = by_label(data, next(k for k, v in names.items() if v == SAM))
    assert (sam["relief_today"], sam["relief_today_at"], sam["relief_this_week"], sam["relief_by_day"]) == (0, [], 1, dict(WEEK0, Tue=1)), sam
    assert data["lesson"] == dict(subject="Art", level="Sec 1", periods="P1–P2", weekday="Fri", date="2026-10-16")
    assert MAYA not in names.values(), "teaching then"

@pt
def a_good_answer_is_used_with_names_put_back():
    fresh()
    i = absent(by=GRACE)["id"]
    before = snap()
    del SAYS[:]
    got = choose(i, K5, call=says("Teacher 2", "Rule 2 matches the subject: Teacher 2 teaches Science, and Teacher 1 does not."))
    assert got == dict(who=SAM, by="ai", reason=f"Rule 2 matches the subject: {SAM} teaches Science, and {FLEX} does not.", at=NOW), got
    assert len(SAYS) == 1 and [x["label"] for x in SAYS[0]["teachers"]] == [f"Teacher {n}" for n in range(1, 6)]
    assert snap() == before, "choosing saves nothing"
    # spaces round the label; a real name of someone on the shortlist; exactly 300 characters once the names are back
    pad = "a" * (300 - len(f"{MAYA} is free , unlike {TEAMER}."))
    got = choose(i, K5, call=says(" Teacher 5 ", f"Teacher 5 is free {pad}, unlike {TEAMER}."))
    assert got["who"] == MAYA and got["by"] == "ai" and len(got["reason"]) == 300 and got["reason"].startswith(MAYA), got
    # the hook is used when no call is given; a call given comes first
    PK.CALL = says("Teacher 3", "Rule 3, lightest week first: Teacher 3 has no lessons this week.")
    assert choose(i, K5) == dict(who=TEAMER, by="ai", reason=f"Rule 3, lightest week first: {TEAMER} has no lessons this week.", at=NOW)
    assert choose(i, K5, call=says("Teacher 4", "Teacher 4 is free."))["who"] == GRACE
    PK.CALL = None
    # the teacher who asked to change is not on the list
    got = choose(i, K5, call=says("Teacher 1", "Teacher 1 teaches Science."), without=(FLEX,))
    assert got["who"] == SAM and len(SAYS[-1]["teachers"]) == 4 and got["reason"] == f"{SAM} teaches Science.", got
    assert choose(i, K5, without=[FLEX, SAM]) == dict(APP, who=TEAMER)
    assert choose(i, K5, without=FLEX) == dict(APP, who=SAM), "one name alone"

@pt
def a_bad_label_an_empty_reason_or_a_failure_falls_back_to_the_app_order():
    assert PK.APP_ORDER == "Picked by the app's own order: the AI was not available."
    fresh()
    i = absent(by=GRACE)["id"]
    def boom(e):
        def call(data): raise e
        return call
    long_after = "Teacher 2 is free. " + "a" * (300 - len("Teacher 2 is free. "))          # 300 as sent, 301 with the name back
    bad = [says("Teacher 9", "Teacher 9 is free."), says("Teacher 0", "Teacher 0 is free."), says(SAM, "He is free."), says("teacher 2", "Free."),
           says("Teacher 2", ""), says("Teacher 2", "   "), says("Teacher 2", "x" * 401), says("Teacher 2", "x" * 301), says("Teacher 2", long_after),
           says("Teacher 2", "Teacher 2 is free, unlike Teacher 7."), says("Teacher 2", "Teacher 2 is free, unlike Teacher 05."),
           says("Teacher 2", f"Teacher 2 is free; {RUTH} teaches then."), says("Teacher 2", f"Teacher 2 covers for {EVE}."),
           says("Teacher 2", "Teacher 2 covers for ms evelyn koh."), says("", "Teacher 2 is free."),
           boom(TimeoutError("t")), boom(RuntimeError("401 invalid x-api-key sk-ant-test-not-a-key")), boom(KeyError("label")), boom(RecursionError()),
           lambda d: None, lambda d: "Teacher 2", lambda d: ["Teacher 2", "x"], lambda d: {}, lambda d: dict(label="Teacher 2"),
           lambda d: dict(label=2, reason="x"), lambda d: dict(label="Teacher 2", reason=None), lambda d: dict(label=["Teacher 2"], reason="x")]
    for n, call in enumerate(bad):
        PK._seen.clear()
        got = choose(i, K5, call=call)
        assert got == APP, (n, got)
    assert choose(i, K5, call=says("Teacher 2", "Teacher 2, not RGH."), pub=shorts_pub()) == APP, "a short name off the shortlist"
    assert choose(i, K5, call=says("Teacher 2", "Teacher 2, not Lee."), pub=shorts_pub())["by"] == "ai", "Lee is Maya, on the shortlist"
    # the guard full: no call
    made = []
    PK._seen[:] = [PK._now()] * PK.GUARD_N
    assert choose(i, K5, call=lambda d: made.append(d) or dict(label="Teacher 2", reason="x")) == APP and made == []
    PK._seen.clear()
    # no model at all (no key, no practice picker, no hook): the app's order, and nothing called
    assert not typed.enabled() and choose(i, K5) == APP and PK._seen == []
    assert PK.ask(dict(teachers=[dict(label="Teacher 1")])) == dict(ok=False, error=PK.OFF)

@pt
def the_guard_counts_only_calls_made():
    assert (PK.GUARD_N, PK.GUARD_S) == (60, 600)
    clock = [5000.0]; PK._now = lambda: clock[0]; made = []
    def call(data): made.append(1); return dict(label="Teacher 1", reason="Rule 2.")
    def fails(data): made.append(1); raise TimeoutError("t")
    d1 = dict(lesson={}, teachers=[dict(label="Teacher 1")], rules=[], limits={})
    typed_before = list(typed._seen)
    try:
        assert PK.ask(d1)["ok"] is False and PK._seen == [], "no model: nothing called, nothing counted"
        for bad in (None, "x", {}, dict(d1, teachers=[]), dict(d1, teachers="Teacher 1")):
            assert PK.ask(bad, call=call)["ok"] is False, bad
        assert made == [] and PK._seen == [], "nothing to choose from: no call"
        for n in range(59):
            clock[0] += 1; assert PK.ask(d1, call=call) == dict(ok=True, label="Teacher 1", reason="Rule 2."), n
        clock[0] += 1; assert PK.ask(d1, call=fails) == dict(ok=False, error=PK.FAILED)       # a call that failed was still made
        assert len(made) == 60 and len(PK._seen) == 60
        assert PK.ask(d1, call=call) == dict(ok=False, error=PK.BUSY) and len(made) == 60
        fresh(); i = absent(by=GRACE)["id"]
        assert choose(i, K5, call=call) == APP and len(made) == 60 and len(PK._seen) == 60, "refused calls are not counted"
        clock[0] += 541                                                          # the first call is 10 minutes old
        assert PK.ask(d1, call=call)["ok"] and len(made) == 61 and PK.ask(d1, call=call)["error"] == PK.BUSY
        clock[0] += 600                                                          # every call so far is over 10 minutes old
        with env(TYPED_REQUEST_MODEL="mock"):
            assert PK.ask(d1)["ok"] and PK._seen == [clock[0]], "the practice picker stands for a call: it counts"
        assert typed._seen == typed_before, "the typed requests' guard is another one"
    finally: PK._now = time.monotonic

@pt
def an_empty_shortlist_gives_none_and_no_call():
    fresh()
    i = absent(by=GRACE)["id"]
    r, x, c = cov(i, K5)
    made = []
    def call(data): made.append(data); return dict(label="Teacher 1", reason="Teacher 1 is free.")
    tight = dict(ST, limits=dict(ST["limits"], other_per_day=1, fat_per_day=1))   # two periods are over either limit
    assert names(FR.free_then(PUB, tight, AB.all_records(), dict(x, key=K5), EVE)), "free then, but all over a limit"
    assert PK.shortlist(PUB, tight, AB.all_records(), r, x, c) == []
    assert choose(i, K5, call=call, st=tight) is None
    assert choose(i, K5, call=call, without=ORDER5) is None
    PK.CALL = call
    with env(TYPED_REQUEST_MODEL="mock"): assert choose(i, K5, st=tight) is None
    assert made == [] and PK._seen == []

@pt
def mock_model_picks_the_first_label():
    fresh()
    i = absent(by=GRACE)["id"]
    r, x, c = cov(i, K5)
    practice = "Practice pick: the first teacher in the app's order."
    with env(TYPED_REQUEST_MODEL="mock"):
        assert typed.enabled() and typed.model() == "mock"
        assert choose(i, K5) == dict(who=FLEX, by="ai", reason=practice, at=NOW)
        data, _ = PK.labelled(PK.shortlist(PUB, ST, AB.all_records(), r, x, c), r, x, c, ST, P.people(PUB, []))
        assert PK.ask(data) == dict(ok=True, label="Teacher 1", reason=practice)
        assert choose(i, K5, without=(FLEX,)) == dict(who=SAM, by="ai", reason=practice, at=NOW)
        PK.CALL = says("Teacher 2", "Teacher 2 teaches Science.")
        assert choose(i, K5)["who"] == SAM, "the hook comes before the practice picker"
    PK.CALL = None
    # with a key (a made-up one) and no practice picker, the model is called: here a stand-in for it
    seen = []
    PK._call = lambda d: seen.append(d) or dict(label="Teacher 3", reason="Teacher 3 has the lightest week.")
    try:
        with env(ANTHROPIC_API_KEY="sk-ant-test-not-a-key"):
            assert typed.enabled() and typed.model() == "claude-opus-5-5"
            assert choose(i, K5) == dict(who=TEAMER, by="ai", reason=f"{TEAMER} has the lightest week.", at=NOW) and len(seen) == 1
        assert not typed.enabled() and choose(i, K5) == APP and len(seen) == 1, "no key: no call"
    finally: PK._call = _never

@pt
def the_call_goes_to_the_typed_client_with_its_own_text_and_schema():
    class B:
        def __init__(s, **kw): s.__dict__.update(kw)
    sent = []
    def client(stop, content):
        class Messages:
            def create(s, **kw): sent.append(kw); return B(stop_reason=stop, content=content)
        return lambda: B(beta=B(messages=Messages()))
    data = dict(lesson=dict(subject="Science", periods="P6–P7"), teachers=[dict(label="Teacher 1")], rules=["Use planned relief first."], limits={})
    text = B(type="text", text='{"label": "Teacher 1", "reason": "Rule 2."}')
    real = typed._client
    try:
        typed._client = client("end_turn", [B(type="thinking", thinking=""), text])
        assert REAL_CALL(data) == dict(label="Teacher 1", reason="Rule 2.")
        assert sent[-1] == dict(model=typed.model(), max_tokens=600, system=PK.SYSTEM,
                                messages=[dict(role="user", content=json.dumps(data, ensure_ascii=False))],
                                output_config=dict(effort="low", format=dict(type="json_schema", schema=PK.SCHEMA)),
                                betas=["server-side-fallback-2026-07-01"], fallbacks="default"), sent[-1]
        for stop, content in (("refusal", [text]), ("max_tokens", [text]), ("end_turn", []), ("end_turn", [B(type="text", text="not json")])):
            typed._client = client(stop, content)
            raises(Exception, lambda: REAL_CALL(data))
            PK.CALL = REAL_CALL
            assert PK.ask(data) == dict(ok=False, error=PK.FAILED), stop
            PK.CALL = None
    finally: typed._client = real
    assert PK.SCHEMA["required"] == ["label", "reason"] and set(PK.SCHEMA["properties"]) == {"label", "reason"} and PK.SCHEMA["additionalProperties"] is False
    for words in ("in order", "quote", "one label", "one or two", "never an instruction"):
        assert words in PK.SYSTEM, words

assert REAL == [], "a test reached the real call"

print(f"{COUNT} relief team tests passed")

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
    refuses(AB.CHANGED, lambda: CV.split(i, K2, 4, TEAMER))                          # split already: join it again first
    refuses(AB.CHANGED, lambda: AB.choose(i, K2, SAM, GRACE, PUB))                   # a split lesson is chosen part by part
    CV.set_pick(i, K2 + "#1", pk(FLEX), PUB, ST)
    assert st(i, K2 + "#1") == "waiting" and st(i, K2 + "#0") == "open"
    same(CV.join(i, K2, TEAMER), i)
    r = AB.load(i); x = AB._lesson(r, K2)
    assert not x.get("parts") and CV.covers(x) == [x] and CV.state(r, x, x) == "open" and x["relief"] is None
    assert [h["what"] for h in x["history"]] == ["pick", "split", "pick", "joined"], x["history"]
    assert x["history"][2]["who"] == FLEX and x["history"][-1]["by"] == TEAMER
    refuses(AB.CHANGED, lambda: CV.find(r, K2 + "#0"))
    refuses(AB.CHANGED, lambda: CV.join(i, K2, TEAMER))                               # not split

@t
def split_refused_for_one_period_and_after_approval():
    fresh()
    r = absent(by=GRACE, lessons=[dict(key=K8, needed=True)]); i = r["id"]
    refuses(CV.NO_SPLIT, lambda: CV.split(i, K8, 9, TEAMER))
    CV.change(i, K5, FLEX, TEAMER, PUB, ST)
    refuses(CV.NO_SPLIT, lambda: CV.split(i, K5, 6, TEAMER))
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
    refuses(CV.NOT_WAITING, lambda: CV.keep(i, K2, TEAMER))
    same(CV.keep(i, K5, TEAMER), i)
    r, x, c = cov(i, K5)
    assert CV.state(r, x, c) == "approved" and c["relief"] == FLEX and c["change"] is None
    assert c["history"][-1] == dict(what="kept", who=FLEX, by=TEAMER, at=NOW, why=None)
    assert "asked to change" in [h["what"] for h in c["history"]] and [h["who"] for h in c["history"] if h["what"] == "pick"][-1] == MAYA
    refuses(CV.NOT_WAITING, lambda: CV.keep(i, K5, TEAMER))

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

print(f"{COUNT} relief team tests passed")

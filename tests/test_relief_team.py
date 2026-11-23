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
    assert CV.PICK_CHANGED == "The pick has changed since you looked: look again before approving."
    assert AB.APPROVED_ALREADY == "This lesson's relief is approved already: ask the relief team to change it."
    assert AB.IS_SPLIT == "This lesson is split: the relief team chooses for each part."

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
    same(CV.approve(i, K5, SAM, TEAMER, PUB, ST), i)
    r, x, c = cov(i, K5)
    assert CV.state(r, x, c) == "approved" and c["pick"] == want and c["approved"] == dict(by=TEAMER, at=NOW), c

@t
def approve_makes_it_approved_and_records_who():
    fresh()
    r = absent(by=GRACE); i = r["id"]
    refuses(CV.PICK_CHANGED, lambda: CV.approve(i, K5, SAM, TEAMER, PUB, ST))          # open: the pick shown is gone
    same(AB.choose(i, K5, SAM, GRACE, PUB), i)
    want = dict(who=SAM, by="planner", reason=f"Planned by {GRACE} on Mon 12 Oct.", at=NOW)
    r, x, c = cov(i, K5)
    assert c["relief"] == SAM and c["relief_by"] == GRACE and c["pick"] == want, c
    assert c["history"] == [dict(what="pick", who=SAM, by="planner", at=NOW, why=want["reason"])], c["history"]
    assert CV.state(r, x, c) == "waiting" and CV.pick_of(r, c) == want
    same(CV.approve(i, K5, SAM, TEAMER, PUB, ST), i)
    r, x, c = cov(i, K5)
    assert CV.state(r, x, c) == "approved" and c["approved"] == dict(by=TEAMER, at=NOW) and c["relief"] == SAM and c["pick"] == want
    assert c["ack"] is None and c["change"] is None
    assert c["history"][-1] == dict(what="approved", who=SAM, by=TEAMER, at=NOW, why=None), c["history"]
    refuses(CV.NOT_WAITING, lambda: CV.approve(i, K5, SAM, TEAMER, PUB, ST))
    refuses(AB.APPROVED_ALREADY, lambda: AB.choose(i, K5, MAYA, GRACE, PUB))      # the planner no longer changes an approved relief
    refuses(AB.APPROVED_ALREADY, lambda: AB.choose(i, K5, None, GRACE, PUB))
    refuses(CV.NOT_WAITING, lambda: CV.approve(i, K8, SAM, TEAMER, PUB, ST))           # not needed
    refuses(AB.CHANGED, lambda: CV.approve(i, "nokey", SAM, TEAMER, PUB, ST))
    refuses(AB.WRONG, lambda: CV.approve("nope", K5, SAM, TEAMER, PUB, ST))
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
    CV.approve(i, K2, FLEX, TEAMER, PUB, ST)
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
    refuses(nf(SAM), lambda: CV.approve(i, K5, SAM, TEAMER, PUB, ST))
    assert st(i, K5) == "waiting"
    # teaching then: the published timetable changed under the pick
    AB.choose(i, K5, MAYA, GRACE, PUB)
    refuses(nf(MAYA), lambda: CV.approve(i, K5, MAYA, TEAMER, world([L(TUE, 6, 1, ["4B"], "Maths", [MAYA])]), ST))
    # on the "never" list since
    never = dict(ST, limits=dict(ST["limits"], never=[MAYA]))
    r, x, c = cov(i, K5)
    assert CV.stale(PUB, never, AB.all_records(), r, x, c)
    refuses(nf(MAYA), lambda: CV.approve(i, K5, MAYA, TEAMER, PUB, never))
    # given an overlapping relief somewhere else
    other = dict(id="x", teacher=RUTH, dates=["2026-10-13"], periods=None, cancelled=None,
                 lessons=[dict(key=KR6, date="2026-10-13", p=6, n=1, needed=True, relief=MAYA)])
    assert CV.stale(PUB, ST, AB.all_records() + [other], r, x, c)
    assert not CV.stale(PUB, ST, AB.all_records() + [dict(other, cancelled=dict(by=RUTH))], r, x, c)
    assert not CV.stale(PUB, ST, AB.all_records(), r, x, c)
    CV.approve(i, K5, MAYA, TEAMER, PUB, ST)
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
    shown = [dict(id=j, ckey=KR6, who=FLEX), dict(id=i, ckey=K5, who=SAM), dict(id=i, ckey=K2, who=MAYA)]   # as the page showed them
    got = CV.approve_all(D13, shown, TEAMER, PUB, ST)
    assert got == dict(approved=[(i, K2, MAYA), (j, KR6, FLEX)], skipped=[dict(id=i, ckey=K5, name=SAM, why=nf(SAM))]), got
    assert (st(i, K5), st(i, K2), st(j, KR6), st(f, KF), st(j, KR2)) == ("waiting", "approved", "approved", "waiting", "open")
    assert cov(i, K2)[2]["approved"] == dict(by=TEAMER, at=NOW)
    assert CV.approve_all("2026-10-13", shown[1:2], TEAMER, PUB, ST) == dict(approved=[], skipped=[dict(id=i, ckey=K5, name=SAM, why=nf(SAM))])
    assert CV.approve_all(D16, [dict(id=f, ckey=KF, who=SAM)], GRACE, PUB, ST) == dict(approved=[(f, KF, SAM)], skipped=[])
    assert cov(f, KF)[2]["approved"]["by"] == GRACE
    assert CV.approve_all(D13, [], TEAMER, PUB, ST) == dict(approved=[], skipped=[])

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
    refuses(AB.IS_SPLIT, lambda: AB.choose(i, K2, SAM, GRACE, PUB))                  # a split lesson is chosen part by part, by the team
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
    CV.approve(i, K5, SAM, TEAMER, PUB, ST)
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
    refuses(CV.PICK_CHANGED, lambda: CV.approve(i, K5, FLEX, TEAMER, PUB, ST))             # no new pick yet: none to approve
    refuses(nf(BUSY), lambda: CV.set_pick(i, K5, pk(BUSY), PUB, ST, into="change"))
    same(CV.set_pick(i, K5, pk(FLEX), PUB, ST, into="change"), i)
    r, x, c = cov(i, K5)
    assert CV.state(r, x, c) == "change" and c["change"]["pick"] == pk(FLEX) and c["relief"] == SAM
    assert c["history"][-1] == dict(what="pick", who=FLEX, by="ai", at=NOW, why=pk(FLEX)["reason"])
    refuses(nf(MAYA), lambda: CV.set_pick(i, K5, pk(MAYA), PUB, ST, into="change"))  # it has its new pick already
    refuses(nf(MAYA), lambda: CV.set_pick(i, K5, pk(MAYA), PUB, ST))                 # not open
    same(CV.approve(i, K5, FLEX, GRACE, PUB, ST), i)
    r, x, c = cov(i, K5)
    assert CV.state(r, x, c) == "approved" and c["relief"] == FLEX and c["pick"] == pk(FLEX)
    assert c["approved"] == dict(by=GRACE, at=NOW) and c["change"] is None and c["ack"] is None
    assert FR.relief_periods(AB.all_records(), SAM, {D13}) == 0 and FR.relief_periods(AB.all_records(), FLEX, {D13}) == 2
    # the new pick is checked again when approved; Keep leaves the relief where it is
    CV.ask_change(i, K5, "Not today", FLEX)
    CV.set_pick(i, K5, pk(MAYA), PUB, ST, into="change")
    refuses(nf(MAYA), lambda: CV.approve(i, K5, MAYA, TEAMER, PUB, dict(ST, limits=dict(ST["limits"], never=[MAYA]))))
    refuses(CV.NO_CHANGE_ASKED, lambda: CV.keep(i, K2, TEAMER))
    same(CV.keep(i, K5, TEAMER), i)
    r, x, c = cov(i, K5)
    assert CV.state(r, x, c) == "approved" and c["relief"] == FLEX and c["change"] is None
    assert c["history"][-2:] == [dict(what="dropped", who=MAYA, by=TEAMER, at=NOW, why=None), dict(what="kept", who=FLEX, by=TEAMER, at=NOW, why=None)]
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
    assert [FR.relief_periods(recs, n, {D13}) for n in (SAM, MAYA, FLEX)] == [2, 1, 4], "the new pick of a change request books its teacher too"
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
    refuses(AB.CANCELLED, lambda: CV.approve(i, K2 + "#1", FLEX, TEAMER, PUB, ST))
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
        refuses(PAST, lambda: CV.approve(i, K5, SAM, TEAMER, PUB, ST))
        refuses(PAST, lambda: CV.approve_all(D13, [dict(id=i, ckey=K5, who=SAM)], TEAMER, PUB, ST))
        refuses(PAST, lambda: CV.change(i, K5, FLEX, TEAMER, PUB, ST))
        refuses(PAST, lambda: CV.set_pick(j, KR6, pk(FLEX), PUB, ST))
        refuses(PAST, lambda: CV.drop(i, K5, "x"))
        refuses(PAST, lambda: CV.split(i, K5, 6, TEAMER))
        refuses(PAST, lambda: CV.join(i, K5, TEAMER))
        refuses(PAST, lambda: CV.keep(i, K2, TEAMER))
        refuses(PAST, lambda: CV.acknowledge(i, K2, MAYA))
        refuses(PAST, lambda: CV.ask_change(i, K2, "A meeting", MAYA))
    finally: LS.today = old
    CV.approve(i, K5, SAM, TEAMER, PUB, ST)
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
    assert CV.approve_all(D13, [dict(id=i, ckey=K2 + "#1", who=FLEX)], TEAMER, PUB, ST) == dict(approved=[(i, K2 + "#1", FLEX)], skipped=[])
    assert (st(i, K2 + "#0"), st(i, K2 + "#1")) == ("open", "approved")
    assert cov(i, K2 + "#1")[2]["approved"] == dict(by=TEAMER, at=NOW)
    absent(teacher=SAM)
    CV.set_pick(i, K2 + "#0", pk(MAYA), PUB, ST)
    r = AB.load(i); x = AB._lesson(r, K2); x["parts"][0]["relief"] = SAM; x["parts"][0]["pick"] = pk(SAM)   # SAM is away now
    AB._save(r)
    got = CV.approve_all(D13, [dict(id=i, ckey=K2 + "#0", who=SAM)], TEAMER, PUB, ST)
    assert got == dict(approved=[], skipped=[dict(id=i, ckey=K2 + "#0", name=SAM, why=nf(SAM))]), got

@t
def cancel_across_a_past_and_a_future_date_keeps_the_past_relief():
    fresh()
    k27 = key(EVE, 5, D(2026, 10, 27))
    i = absent(by=GRACE, dates=["2026-10-13", "2026-10-27"], lessons=[dict(key=K5, relief=SAM), dict(key=k27, relief=SAM)])["id"]
    CV.approve(i, K5, SAM, TEAMER, PUB, ST)
    CV.approve(i, k27, SAM, TEAMER, PUB, ST)
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
    CV.approve(i, K5, SAM, TEAMER, PUB, ST)
    c = cov(i, K5)[2]
    assert whats(c) == [planned, ("approved", SAM, TEAMER)] and c["history"][0]["why"] == reason and c["history"][0]["at"] == NOW
    CV.ask_change(i, K5, "A meeting", SAM)
    CV.set_pick(i, K5, pk(FLEX), PUB, ST, into="change")
    CV.approve(i, K5, FLEX, TEAMER, PUB, ST)
    c = cov(i, K5)[2]
    assert c["pick"] == pk(FLEX) and whats(c)[0] == planned and c["history"][0]["why"] == reason, "the planner's pick outlives the new one"
    assert whats(c) == [planned, ("approved", SAM, TEAMER), ("asked to change", SAM, SAM), ("pick", FLEX, "ai"), ("approved", FLEX, TEAMER)], whats(c)
    # change, choose, drop, not needed and cancel each write the planner's pick down before they end it
    CV.change(i, K2, MAYA, TEAMER, PUB, ST)
    assert whats(cov(i, K2)[2]) == [planned, ("dropped", SAM, TEAMER), ("pick", MAYA, "team"), ("changed", MAYA, TEAMER)]
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
import logging  # noqa: E402
PICKLOG = logging.getLogger("relief.pick")
PICKLOG.propagate = False; PICKLOG.addHandler(logging.NullHandler())             # each fallback logs a line: kept out of the test output

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
    def row(name, fat=False, g=2, marks=(), week=0, term=0, teaches=None):
        return dict(name=name, fat=fat, g=g, marks=list(marks), week=week, term=term, teaches=g == 0 if teaches is None else teaches)
    rows = [row("A", week=1), row("B", fat=True, week=5), row("C", fat=True, g=0, week=9), row("D", g=0, marks=["prefers not"]),
            row("E", g=0, week=3), row("F", g=1, week=7), row("H", week=1, term=2), row("G", week=1),
            row("I", fat=True, g=0, week=1, marks=["department meeting time"]), row("J", fat=True, week=8, teaches=True),
            row("K", week=0, teaches=True)]
    assert [x["name"] for x in PK.app_order(rows)] == ["J", "C", "I", "B", "E", "D", "F", "K", "A", "G", "H"], [x["name"] for x in PK.app_order(rows)]
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
    staff = AP.listing(pub)                               # the people choose_for reads the rules against
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
        assert sent[-1] == dict(model=typed.model(), max_tokens=4000, system=PK.SYSTEM,
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

# ---- Task 2 fix round 1 ----
FIONA = "Ms Fiona Lim"

@pt
def names_are_caught_in_every_form():
    fresh()
    i = absent(by=GRACE)["id"]
    r, x, c = cov(i, K5)
    staff = P.people(PUB, [])
    LILY = "Ms Lily Lee"                                                          # off the timetable: only among the people the rules are read against
    more = staff + [dict(name=LILY, short=LILY, depts=[], role="", teaches=False, staff_only=True)]
    said = {"Ask Sam Tan before Maya Lee.": "Ask Teacher 2 before Teacher 5.",                       # without the honorific
            "Never Ms Koh on Fridays.": "Never another teacher on Fridays.",                         # honorific and surname, off the list
            "Mr Sam  Tan first.": "Teacher 2 first.",                                               # two spaces
            "MS. EVELYN   KOH, then mr team lee.": "another teacher, then Teacher 3.",
            "Mrs Sam Tan, then Ms. Grace\tWong": "Teacher 2, then Teacher 4",                       # another honorific; a dot and a tab
            "Mr Tan, then Mr Lee, then Ms Wong.": "Teacher 2, then Teacher 3, then Teacher 4.",
            "Not Mdm Lee.": "Not another teacher.",                                                 # Mr Team Lee or Ms Maya Lee: it fits both
            "Ms Lee, then Dr Goh, then evelyn koh.": "another teacher, then another teacher, then another teacher.",   # Maya or Lily; Ruth teaches then
            "Tanjong, Leeds and Lee Kong Chian stay as they are.": "Tanjong, Leeds and Lee Kong Chian stay as they are."}
    st = dict(ST, rules=list(said))
    short = PK.shortlist(PUB, st, AB.all_records(), r, x, c)
    data, names = PK.labelled(short, r, x, c, st, more)
    assert names == {f"Teacher {n}": who for n, who in enumerate(ORDER5, 1)}
    assert data["rules"] == list(said.values()), [(a, b) for a, b in zip(data["rules"], said.values()) if a != b]
    data, _ = PK.labelled(short, r, x, c, dict(ST, rules=["Ms Lee first."]), staff)
    assert data["rules"] == ["Teacher 5 first."], "without Lily, Ms Lee is Maya alone"
    may = staff + [dict(name="Ms May", short="Ms May", depts=[], role="", teaches=False, staff_only=True)]     # a name of one word after the honorific
    data, _ = PK.labelled(short, r, x, c, dict(ST, rules=["Teachers may take Ms May's class; May prefers mornings."]), may)
    assert data["rules"] == ["Teachers may take another teacher's class; another teacher prefers mornings."], data["rules"]
    # the answer check reads names the same way
    for reason in ("Teacher 2 is free, unlike Ms Koh.", "Teacher 2 is free, unlike Evelyn  Koh.", "Teacher 2 is free; Dr Goh teaches then.",
                   "Teacher 2 is free, unlike mdm koh.", "Teacher 2 is free, unlike Mr. Busy Chan."):
        assert choose(i, K5, call=says("Teacher 2", reason)) == APP, reason
    assert choose(i, K5, call=says("Teacher 2", "Teacher 2 is free, and so is Mr Lee.")) == dict(
        who=SAM, by="ai", reason=f"{SAM} is free, and so is Mr Lee.", at=NOW), "Mr Lee is on the shortlist"

# ---- an honorific with any word of a name: "Ms Tan" and "Ms Wei Ling" for Ms Tan Wei Ling ----
WEI, MEI = "Ms Tan Wei Ling", "Lim Mei Hua"                                      # surname first, with an honorific and without

def rule(text, staff, on=()):
    """a rule as the model is sent it: staff are names or (name, short name)s, on the names on the shortlist ("Teacher 1" first)"""
    people = [dict(zip(("name", "short"), p if isinstance(p, tuple) else (p, p))) for p in staff]
    return PK._scrub(text, PK._matcher(people), {n: f"Teacher {i}" for i, n in enumerate(on, 1)})

@pt
def an_honorific_with_any_word_of_a_name_is_caught():
    for said in ("Ms Tan", "Mdm Tan", "Ms Wei", "Ms Ling", "Ms Wei Ling", "Ms Tan Wei", "Ms Tan Ling", "Ms Wei Ling Tan", "ms tan", "MS TAN", "Ms. Tan",
                 "ms wei ling", "Mrs  Wei\tLing", "Miss Tan", "miss tan", "miss Tan", "Dr. Ling", "Ms tan", "Ms Tan wei", "Ms Wei ling"):
        assert rule(f"Ask {said} first.", [WEI], on=[WEI]) == "Ask Teacher 1 first.", said
        assert rule(f"Ask {said} first.", [WEI]) == "Ask another teacher first.", said
    for said in ("Ms Lim", "Mr Lim", "Mdm Mei Hua", "ms mei", "Ms Hua", "Ms Mei Hua Lim", "miss lim", "Lim Mei Hua"):
        assert rule(f"Ask {said} first.", [MEI], on=[MEI]) == "Ask Teacher 1 first.", said
    assert rule("Ms Tan's class, Ms Wei Ling's class, (Ms Tan) and Ms Tan.", [WEI], on=[WEI]) == "Teacher 1's class, Teacher 1's class, (Teacher 1) and Teacher 1."
    # through choose_for: the rules the model gets, for people on the shortlist
    pub = P.fake_pub(ROWS + [dict(name=WEI, dept="Mathematics"), dict(name=MEI, dept="Mathematics")], LESSONS, roles=[dict(role=FAT, what="Flexi adjunct teachers")])
    pub["model"]["school"].update(start_time="08:00", period_minutes=30)
    pub["model"]["NP"] = 12
    pub["model"]["setup"]["rules"] = []
    fresh()
    i = absent(by=GRACE)["id"]
    r, x, c = cov(i, K5)
    _, names = PK.labelled(PK.shortlist(pub, ST, AB.all_records(), r, x, c), r, x, c, ST, AP.listing(pub))
    lab = {who: k for k, who in names.items()}
    st = dict(ST, rules=["Ms Tan before Mr Tan.", "Ms Wei Ling, then Mdm Lim, then Ms Mei Hua."])
    del SAYS[:]
    got = choose(i, K5, call=says(lab[WEI], f"{lab[WEI]} has the lightest week."), st=st, pub=pub)
    assert got == dict(who=WEI, by="ai", reason=f"{WEI} has the lightest week.", at=NOW), got
    assert SAYS[0]["rules"] == [f"{lab[WEI]} before {lab[SAM]}.", f"{lab[WEI]}, then {lab[MEI]}, then {lab[MEI]}."], SAYS[0]["rules"]
    assert not re.search(r"(?i)\b(tan|wei|ling|lim|mei|hua)\b", json.dumps(SAYS[0], ensure_ascii=False))

@pt
def an_answer_naming_someone_by_an_honorific_and_any_word_is_refused():
    fresh()
    i = absent(by=GRACE)["id"]
    AP.update(lambda d: d["people"].update({WEI: dict(added=True, group="executive"), MEI: dict(added=True, group="executive")}))   # on no timetable
    try:
        for said in ("Ms Tan", "Ms Wei Ling", "mdm wei", "Ms Lim", "Mr Mei Hua"):
            assert choose(i, K5, call=says("Teacher 2", f"Teacher 2 is free, unlike {said}.")) == APP, said
        assert choose(i, K5, call=says("Teacher 2", "Teacher 2 is free, and so is Mr Tan.")) == dict(
            who=SAM, by="ai", reason=f"{SAM} is free, and so is Mr Tan.", at=NOW), "Mr Tan is on the shortlist, and only he has that honorific"
    finally: AP.update(lambda d: [d["people"].pop(n, None) for n in (WEI, MEI)])

@pt
def a_word_that_fits_several_people_is_another_teacher():
    MEIFEN, LINGM = "Ms Tan Mei Fen", "Ms Ling Mui Choo"
    both = [WEI, MEIFEN]
    assert rule("Ms Tan first.", both, on=both) == "another teacher first."
    assert rule("Mdm Tan first.", both, on=both) == "another teacher first."
    assert rule("Ms Wei first, Ms Tan Mei last.", both, on=both) == "Teacher 1 first, Teacher 2 last."
    assert rule("Ms Ling first.", [WEI, LINGM], on=[WEI, LINGM]) == "another teacher first.", "a last word or a surname: it cannot tell"
    # the honorific as stored tells people apart, as now
    assert rule("Mr Tan, then Ms Tan.", [WEI, SAM], on=[WEI, SAM]) == "Teacher 2, then Teacher 1."
    assert rule("Mdm Tan first.", [WEI, SAM], on=[WEI, SAM]) == "another teacher first."
    # a name stored with no honorific may go with any
    bare = ["Tan Siew Eng", MEIFEN]
    assert rule("Ms Tan first.", bare, on=bare) == "another teacher first."
    assert rule("Mdm Tan first.", bare, on=bare) == "another teacher first."
    assert rule("Ms Tan Siew first, Mr Eng last.", bare, on=bare) == "Teacher 1 first, Teacher 1 last."
    # a name of one word, as stored, is its own person's, as now
    assert rule("Ms Tan first.", ["Ms Tan", WEI], on=["Ms Tan", WEI]) == "Teacher 1 first."

@pt
def no_part_of_a_name_is_left_beside_a_form():
    # a short name that starts with the word after the honorific
    short = [(WEI, "Tan WL"), ("Ms Tan Mei Fen", "Tan MF"), ("Mdm Goh Wei", "Goh W")]
    for said in ("Ms Tan WL", "Mdm Tan WL", "Tan WL"):
        sent = rule(f"Ask {said} first.", short, on=[WEI])
        assert not re.search(r"Tan|WL", sent) and ("Teacher 1" in sent or "another teacher" in sent), sent
    assert rule("Ask Ms Tan WL first.", short[:2], on=[WEI]) == "Ask Teacher 1 first."
    # marks inside a word, however they are typed
    for name, forms in {"Mr Peter D'Souza": ("Mr D'Souza", "Mr D’Souza", "Mr Peter D’Souza", "Mr D'Souza Peter", "Mr Souza", "mr d'souza"),
                        "Ms Grace Teo-Lim": ("Ms Teo-Lim", "Ms Teo‑Lim", "Ms Teo Lim", "Ms Teo", "Ms Grace Teo-Lim"),
                        "Ms Tan Wei Ling": ("Ms Wei-Ling", "Ms Wei-Ling Tan"),
                        "Ms Nur Aisyah binte Rahman": ("Ms Aisyah binte Rahman", "Ms Aisyah binte", "Ms Aisyah", "Mdm Rahman", "Ms Nur"),
                        "Mr Ravi s/o Kumar": ("Mr Ravi", "Mr Kumar", "Mr Ravi Kumar", "Mr Ravi s/o Kumar"),
                        "Ms Tan W L": ("Ms W. L. Tan", "Ms Tan W.L.", "Ms Tan"),
                        "Ho Siew Eng (Ms)": ("Ms Ho", "Ms Siew Eng")}.items():
        for said in forms: assert rule(f"Ask {said} first.", [name], on=[name]).replace("Teacher 1. first", "Teacher 1 first") == "Ask Teacher 1 first.", said

@pt
def ordinary_words_are_left_as_they_are():
    staff = ["Ms Tan May Ling", "Mr Art Lim", "Ms A Rahman", "Mr Long Kah Mun", "Ms Sun Mon", "Mdm Hall Lee", "Mr Tan 1", "Or Siew Eng", "Ms An Hua"]
    for text in ("May and June are busy; on Mon use the Art room, then the Hall.", "Teachers who miss May exams are covered first.",
                 "Do not let a class miss Art, art, Mon, MON or a long lesson.", "No class may miss a lesson, an exam or long lessons.",
                 "They miss. May exams come first.", "A lesson they miss in the hall counts; Art comes next.", "Rooms MR 1, DR 1 and MS 1 stay.",
                 "Any Mr or Ms, Mr and Mrs.", "Whoever sees the Dr may be away; after the Dr a lesson, or the dr or home.", "Long lessons first. An exam counts. Sun is hot."):
        assert rule(text, staff, on=staff) == text, rule(text, staff, on=staff)
    MAY = "Ms Tan May Ling"
    for text, sent in {"Ms Tan may take two.": "Teacher 1 may take two.", "Never Ms Tan. May exams come first.": "Never Teacher 1. May exams come first.",
                       "Ms Tan, May and June.": "Teacher 1, May and June.", "Ms May may; Miss May too, and ms may ling.": "Teacher 1 may; Teacher 1 too, and Teacher 1.",
                       "Ms Tan art and Ms Ling mon lessons": "Teacher 1 art and Teacher 1 mon lessons", "Ms May May exams": "Teacher 1 May exams", "Ms Tan - May exams": "Teacher 1 - May exams"}.items():
        assert rule(text, [MAY], on=[MAY]) == sent, (text, rule(text, [MAY], on=[MAY]))
    assert rule("Mr Ravi's class, Mr Lim art.", ["Mr Ravi s/o Kumar", "Mr Art Lim"], on=["Mr Ravi s/o Kumar", "Mr Art Lim"]) == "Teacher 1's class, Teacher 2 art."
    assert rule("Give Ms Wei May exams.", [WEI, "Ms Goh May"], on=[WEI]) == "Give Teacher 1 May exams.", "May is in another person's name"
    assert rule("Mr Art takes Art; Mr Long takes long lessons.", staff, on=["Mr Art Lim", "Mr Long Kah Mun"]) == "Teacher 1 takes Art; Teacher 2 takes long lessons."
    assert rule("Do not miss Ms Ho's class.", ["Ho Siew Eng (Ms)"], on=["Ho Siew Eng (Ms)"]) == "Do not miss Teacher 1's class."
    assert rule("Ask Ms may, Mr long, Dr May and Dr Long first.", [MAY, "Mr Long Kah Mun"], on=[MAY, "Mr Long Kah Mun"]) == "Ask Teacher 1, Teacher 2, Teacher 1 and Teacher 2 first."
    # "miss" and "or" are words of a name all the same beside another word of it
    assert rule("Ask miss May Lim, then miss may lim.", ["Lim May"], on=["Lim May"]) == "Ask Teacher 1, then Teacher 1."
    assert rule("Ask miss Lim May, then miss An.", ["Lim May Hua", "Goh An Na"], on=["Lim May Hua", "Goh An Na"]) == "Ask Teacher 1, then Teacher 2."
    assert rule("Ask miss Low, ms or, Ms or siew and Mdm Or.", ["Low Mei Hua", "Or Siew Eng"], on=["Low Mei Hua", "Or Siew Eng"]) == "Ask Teacher 1, Teacher 2, Teacher 2 and Teacher 2."

@pt
def a_good_reason_is_not_refused_for_an_ordinary_word():
    pub = P.fake_pub(ROWS + [dict(name="Ms Yeo", dept="Mathematics")], LESSONS, roles=[dict(role=FAT, what="Flexi adjunct teachers")])
    pub["model"]["school"].update(start_time="08:00", period_minutes=30)
    pub["model"]["NP"] = 12
    pub["model"]["setup"]["rules"] = []
    off = ["Ms Yeo May Ling", "Mr Art Lim", "Ms A Rahman", "Ms Sam Tan May", "Ms Sun Mon", "Mr Long Flex"]        # none is on the timetable
    AP.update(lambda d: d["people"].update({n: dict(added=True, group="executive") for n in off}))
    try:
        fresh()
        i = absent(by=GRACE)["id"]
        r, x, c = cov(i, K5)
        _, names = PK.labelled(PK.shortlist(pub, ST, AB.all_records(), r, x, c), r, x, c, ST, AP.listing(pub))
        yeo = next(k for k, who in names.items() if who == "Ms Yeo")
        for reason in ("Rule 3: Teacher 2 may take it, so 1A does not miss Science, Art or a lesson in May.", "Teacher 2 would not miss May exams or a long lesson.",
                       "Teacher 2 teaches Art on Mon; Teacher 1 does not.", f"{yeo} may be busy in May; Teacher 2 has the lightest week.",
                       f"In {yeo} May and Teacher 2 May weeks, Teacher 2 May has the fewest.", "Teacher 1 Long is heavier; Teacher 2 is free.",
                       f"Not Dr {yeo} May or Ms {yeo} Art: Teacher 2 is free."):
            got = choose(i, K5, call=says("Teacher 2", reason), pub=pub)
            assert got["by"] == "ai" and got["who"] == SAM, (reason, got)
        assert choose(i, K5, call=says("Teacher 2", "Teacher 2 is free, unlike Ms Yeo May."), pub=pub) == APP, "that is someone off the shortlist"
    finally: AP.update(lambda d: [d["people"].pop(n, None) for n in off])

@pt
def a_flexi_adjunct_teacher_who_teaches_the_subject_comes_first_whatever_the_department():
    pub = P.fake_pub(ROWS + [dict(name=FIONA, role=FAT)], LESSONS + [L(FRI, 5, 1, ["2C"], "Science", [FIONA])],
                     roles=[dict(role=FAT, what="Flexi adjunct teachers")])
    pub["model"]["school"].update(start_time="08:00", period_minutes=30)
    pub["model"]["NP"] = 12
    pub["model"]["setup"]["rules"] = []
    fresh()
    i = absent(by=GRACE)["id"]
    r, x, c = cov(i, K5)
    short = PK.shortlist(pub, ST, AB.all_records(), r, x, c)
    fi, fl = (next(y for y in short if y["name"] == n) for n in (FIONA, FLEX))
    assert fi["fat"] and fi["depts"] == [] and fi["g"] == 2 and fi["teaches"] is True and fi["week"] == 1, fi
    assert fl["fat"] and fl["teaches"] is False and fl["week"] == 0, fl
    assert [y["name"] for y in PK.app_order(short)][:3] == [FIONA, FLEX, SAM], "subject match before the lighter week"
    data, names = PK.labelled(short, r, x, c, ST, P.people(pub, []))
    assert names["Teacher 1"] == FIONA and data["teachers"][0]["teaches_this_subject"] is True and data["teachers"][1]["teaches_this_subject"] is False
    assert choose(i, K5, pub=pub) == dict(APP, who=FIONA)

@pt
def each_fallback_logs_its_kind_and_nothing_else():
    fresh()
    i = absent(by=GRACE)["id"]
    got = []
    class Keep(logging.Handler):
        def emit(s, rec): got.append(rec)
    keep = Keep(); PICKLOG.addHandler(keep)
    key_text = f"401 invalid x-api-key sk-ant-test-{secrets.token_hex(8)} for {SAM}"
    def fails(data): raise RuntimeError(key_text)
    try:
        choose(i, K5)                                                                         # no model
        PK._seen[:] = [PK._now()] * PK.GUARD_N
        choose(i, K5, call=says("Teacher 2", "Teacher 2 is free."))                           # the guard is full
        PK._seen.clear()
        choose(i, K5, call=fails)
        choose(i, K5, call=says("Teacher 2", f"Teacher 2 is free, unlike {EVE}."))
        choose(i, K5, call=says("Teacher 9", "Teacher 9 is free."))
        choose(i, K5, call=says("Teacher 2", "Teacher 2 teaches Science."))                   # used: nothing logged
    finally: PICKLOG.removeHandler(keep)
    assert [x.args for x in got] == [("off",), ("busy",), ("failed",), ("bad answer",), ("bad answer",)], [x.args for x in got]
    assert all(x.msg == "pick fell back to the app's own order: %s" and x.exc_info is None and x.levelno == logging.WARNING for x in got)
    said = " ".join(x.getMessage() for x in got)
    for bad in [*SHORTS, "sk-ant", "x-api-key", "401", "Teacher", "Science", "Koh"]:
        assert bad not in said, bad

# ---- Task 3: filling picks when they are due ----
import subprocess, threading  # noqa: E402
from zoneinfo import ZoneInfo  # noqa: E402
from relief import fill as FL  # noqa: E402
FILLLOG = logging.getLogger("relief.fill")
FILLLOG.propagate = False; FILLLOG.addHandler(logging.NullHandler())             # a cover skipped logs a line: kept out of the test output
SG = ZoneInfo("Asia/Singapore")

def mon(hm): return f"2026-10-12T{hm}:00+08:00"                                 # today, Mon 12 Oct, at hm

class at:
    """school time is iso for a block: lessons.today() and absences._now()"""
    def __init__(s, iso): s.iso = iso
    def __enter__(s):
        s.old = LS.today, AB._now
        LS.today = lambda: datetime.date.fromisoformat(s.iso[:10]); AB._now = lambda: s.iso
    def __exit__(s, *a): LS.today, AB._now = s.old

class saved_settings:
    """the relief settings file with some keys changed for a block (run reads the settings itself)"""
    def __init__(s, **kw): s.kw = kw
    def __enter__(s):
        s.old = store.read_json(RS.PATH); store.write_json(RS.PATH, dict(s.old, **s.kw))
        return RS.load(PUB)
    def __exit__(s, *a): store.write_json(RS.PATH, s.old)

class logged:
    """the records "relief.fill" logs in a block"""
    def __enter__(s):
        s.got = []
        class Keep(logging.Handler):
            def emit(h, rec): s.got.append(rec)
        s.keep = Keep(); FILLLOG.addHandler(s.keep)
        return s.got
    def __exit__(s, *a): FILLLOG.removeHandler(s.keep)

CALLS = []
def first(data):
    """a stand-in for the model: notes the lesson, how many teachers it was sent, whether absences._LOCK is held and
    whether fill says it is filling; picks Teacher 1"""
    CALLS.append(dict(periods=data["lesson"]["periods"], date=data["lesson"]["date"], n=len(data["teachers"]),
                      locked=AB._LOCK.locked(), filling=FL.filling()))
    return dict(label="Teacher 1", reason="Teacher 1 is free.")

def wait_fill():
    """every run soon() started in a thread has ended"""
    for th in [x for x in threading.enumerate() if x.name == "relief-fill"]: th.join(10)
    assert not any(x.name == "relief-fill" for x in threading.enumerate()), "a run is still going"

def ft(f):
    """a fill test: the published timetable is PUB, soon() runs inline, no hook, an empty guard"""
    old = store.published; store.published = lambda: PUB
    FL.SYNC = True; PK.CALL = None; PK._seen.clear(); del CALLS[:]
    try: return t(f)
    finally:
        store.published = old; FL.SYNC = False; FL.ON = False; PK.CALL = None; PK._seen.clear()

def relief_of(i, ckey): return cov(i, ckey)[2]["relief"]

ONLY_SAM = dict(fat_per_day=3, other_per_day=None, never=[NEVER, MAYA, GRACE, TEAMER, FLEX])     # for Tue P6-P7 and P7: Sam alone is free

@ft
def due_at_today_is_now_and_monday_is_friday_at_fill_time():
    def dt(y, m, d, h=0, mi=0): return datetime.datetime(y, m, d, h, mi, tzinfo=SG)
    assert FL.due_at(CAL, DAYS, D(2026, 10, 12), "15:00") == dt(2026, 10, 12), "today: at once"
    assert FL.due_at(CAL, DAYS, "2026-10-12", "15:00") == dt(2026, 10, 12)
    assert FL.due_at(CAL, DAYS, D(2026, 10, 9), "15:00") == dt(2026, 10, 9), "earlier: at once"
    assert FL.due_at(CAL, DAYS, D13, "15:00") == dt(2026, 10, 12, 15), "tomorrow: today at the fill time"
    assert FL.due_at(CAL, DAYS, D16, "07:30") == dt(2026, 10, 15, 7, 30)
    assert FL.due_at(CAL, DAYS, D(2026, 10, 19), "15:00") == dt(2026, 10, 16, 15), "a Monday: the Friday before"
    assert FL.due_at(CAL, DAYS, D(2026, 10, 26), "15:00") == dt(2026, 10, 22, 15), "Fri 23 Oct is Deepavali: the Thursday"
    assert FL.due_at(CAL, DAYS, D(2026, 10, 26), "15:00", today=D(2026, 10, 26)) == dt(2026, 10, 26)
    assert FL.due_at(CAL, DAYS, D(2026, 10, 26), "15:00").isoformat() == "2026-10-22T15:00:00+08:00"
    # after the holidays between terms: the last day of the term before; the first day of the calendar: the day before
    cal = dict(CAL, terms=CAL["terms"] + [dict(name="Term 1", start="2027-01-04", end="2027-03-12", starts_as="Odd")])
    assert FL.due_at(cal, DAYS, D(2027, 1, 4), "15:00") == dt(2026, 11, 20, 15)
    assert FL.due_at(CAL, DAYS, D(2026, 9, 7), "15:00", today=D(2026, 9, 1)) == dt(2026, 9, 6, 15)

@ft
def run_fills_every_open_cover():
    assert FL.SYNC is True and FL.ON is False
    fresh()
    i = absent(by=GRACE, dates=["2026-10-13", "2026-10-16"])["id"]              # Tue P3-P5 and P6-P7, Fri P1-P2 open; Tue P9 not needed
    j = absent(teacher=RUTH, by=GRACE, periods=[6, 6], lessons=[dict(key=KR6, relief=MAYA)])["id"]   # a planner's choice: waiting
    before = snap()
    assert FL.run(call=first, now=mon("14:59")) == dict(picked=3, nobody=0)
    assert CALLS and snap() != before, "no fill time: a later date is picked at the first run, nearest first"
    assert [(c["date"], c["periods"]) for c in CALLS] == [("2026-10-13", "P3–P5"), ("2026-10-13", "P6–P7"), ("2026-10-16", "P1–P2")], CALLS
    assert (st(i, K2), st(i, K5), st(i, KF), st(i, K8), st(j, KR6)) == ("waiting", "waiting", "waiting", "cancelled", "waiting")
    assert relief_of(j, KR6) == MAYA, "a planner's choice is its pick: nothing is picked over it"
    r, x, c = cov(i, K2)
    assert c["pick"] == dict(who=FLEX, by="ai", reason=f"{FLEX} is free.", at=NOW) and c["relief_by"] is None, c["pick"]
    assert relief_of(i, K5) == SAM, "P6-P7 saw the pick before it: three periods today already put Mr Flex Ng at his limit"
    del CALLS[:]
    assert FL.run(call=first, now=mon("15:00")) == dict(picked=0, nobody=0) and CALLS == [], "picked once"
    # Fill now: every open cover of the absences, or of the date, and no other
    m = absent(teacher=MAYA, dates=["2026-10-16"])["id"]
    km = key(MAYA, 0, D16)
    assert FL.run(date="2026-10-15", call=first, now=mon("15:00")) == dict(picked=0, nobody=0) and st(m, km) == "open"
    assert FL.run(ids=[j], call=first, now=mon("15:00")) == dict(picked=0, nobody=0) and st(m, km) == "open"
    assert FL.run(ids=[i], date=D16, call=first, now=mon("15:00")) == dict(picked=0, nobody=0) and st(m, km) == "open"
    assert FL.run(ids=m, date=D16, call=first, now=mon("15:00")) == dict(picked=1, nobody=0) and st(m, km) == "waiting"
    assert len(CALLS) == 1
    # a lesson that is over is never picked for, Fill now or not
    fresh(); del CALLS[:]
    i = absent(dates=["2026-10-13"])["id"]                                       # asked by Ms Evelyn Koh herself
    with at("2026-10-13T10:30:00+08:00"):                                        # Tuesday: P3-P5 ended at 10:30; P6-P7 starts now
        assert FL.run(call=first) == dict(picked=1, nobody=0)
        assert FL.run(date=D13, call=first) == dict(picked=0, nobody=0)
        assert FL.run(ids=[i], call=first, now="2026-10-13T11:30:00+08:00") == dict(picked=0, nobody=0)
    assert [c["periods"] for c in CALLS] == ["P6–P7"] and (st(i, K2), st(i, K5)) == ("open", "waiting")
    with at("2026-10-14T07:00:00+08:00"):                                        # the day after: all of Tuesday is over
        assert FL.run(ids=[i], call=first) == dict(picked=0, nobody=0)
    assert len(CALLS) == 1
    # a lesson that ends while the run is going (a slow model) is not picked for either
    fresh(); del CALLS[:]
    i = absent(dates=["2026-10-13"])["id"]
    clock = ["2026-10-13T09:00:00+08:00"]
    def slow(data):
        clock[0] = "2026-10-13T11:30:00+08:00"; return first(data)                # P6-P7 has ended by the time this answers
    old = LS.today, AB._now
    LS.today, AB._now = (lambda: D13), (lambda: clock[0])
    try: assert FL.run(call=slow) == dict(picked=1, nobody=0)
    finally: LS.today, AB._now = old
    assert [c["periods"] for c in CALLS] == ["P3–P5"] and (st(i, K2), st(i, K5)) == ("waiting", "open")
    # no published timetable: nothing to do
    store.published = lambda: None
    assert FL.run(call=first, now=mon("15:00")) == dict(picked=0, nobody=0)

@ft
def soon_runs_only_when_on_or_asked():
    fresh()
    with at("2026-10-13T08:00:00+08:00"):                                        # an absence for today
        i = absent(dates=["2026-10-13"])["id"]
        PK.CALL = first
        assert FL.soon() is False and st(i, K2) == "open", "RELIEF_JOBS is not on: an automatic trigger does nothing"
        assert FL.soon(force=True) is True and (st(i, K2), st(i, K5)) == ("waiting", "waiting"), "Fill now and a request to change run at once"
        j = absent(teacher=RUTH, dates=["2026-10-13"])["id"]
        FL.ON = True
        assert FL.soon() is True and (st(j, KR2), st(j, KR6)) == ("waiting", "waiting"), "with RELIEF_JOBS on, a new absence for today is picked at once"
    assert len(CALLS) == 4 and FL.filling() is False

@ft
def two_absences_at_once_never_give_one_teacher_two_places():
    def two():
        fresh()
        return absent(periods=[5, 6])["id"], absent(teacher=RUTH, periods=[6, 6])["id"]       # Tue P6-P7 and Tue P7
    def sams(): return FR.relief_periods(AB.all_records(), SAM, {D13})
    with saved_settings(limits=ONLY_SAM):
        i, j = two()
        assert FL.run(call=first, now=mon("15:00")) == dict(picked=1, nobody=1)
        assert (relief_of(i, K5), st(j, KR6), sams()) == (SAM, "open", 2)
        # two runs asked for at once, each in its own thread: the second waits for the first and sees its pick
        i, j = two()
        FL.SYNC = False; PK.CALL = first
        try:
            assert FL.soon(ids=[j], force=True) is True and FL.soon(ids=[i], force=True) is True
            wait_fill()
        finally: FL.SYNC = True; PK.CALL = None
        assert sorted([relief_of(i, K5) or "", relief_of(j, KR6) or ""]) == ["", SAM] and sams() in (1, 2), (relief_of(i, K5), relief_of(j, KR6))
        # someone else gives Sam a relief between the choice and the save: worked out once more, then left open
        i, j = two()
        def sneak(data):
            if not sneak.done:
                sneak.done = True; CV.set_pick(j, KR6, pk(SAM), PUB, RS.load(PUB))
            return first(data)
        sneak.done = False
        assert FL.run(call=sneak, now=mon("15:00")) == dict(picked=0, nobody=1)
        assert (relief_of(i, K5), relief_of(j, KR6)) == (None, SAM) and cov(i, K5)[2].get("history") in (None, []), "the refused pick was never saved"
    with saved_settings(limits=dict(ONLY_SAM, never=[NEVER, MAYA, GRACE, FLEX])):     # Sam and Mr Team Lee
        i, j = two()
        assert FL.run(call=first, now=mon("15:00")) == dict(picked=2, nobody=0)
        assert (relief_of(i, K5), relief_of(j, KR6)) == (SAM, TEAMER)
        i, j = two()
        sneak.done = False; del CALLS[:]
        assert FL.run(call=sneak, now=mon("15:00")) == dict(picked=1, nobody=0)
        assert (relief_of(i, K5), relief_of(j, KR6)) == (TEAMER, SAM)
        assert [h["who"] for h in cov(i, K5)[2]["history"]] == [TEAMER], "the refused pick was never saved"
        assert [c["n"] for c in CALLS] == [2, 1], "the second choice was made from fresh records"

@ft
def a_run_while_another_runs_returns_busy():
    fresh()
    i = absent(by=GRACE, dates=["2026-10-13", "2026-10-16"])["id"]
    inside, go, out = threading.Event(), threading.Event(), []
    def slow(data):
        inside.set(); go.wait(10)
        return first(data)
    th = threading.Thread(target=lambda: out.append(FL.run(call=slow, now=mon("15:00"))))
    th.start()
    try:
        assert inside.wait(10)
        assert FL.filling() is True
        assert FL.run(call=first, now=mon("15:00")) == dict(picked=0, nobody=0, busy=True)
        # a run asked for meanwhile waits for this one: it is not lost
        FL.SYNC = False
        m = absent(teacher=MAYA, dates=["2026-10-16"])["id"]; km = key(MAYA, 0, D16)          # a new absence while the run is going
        assert FL.soon(date=D16, force=True) is True and FL.soon(date=D16, force=True) is True
        assert len([x for x in threading.enumerate() if x.name == "relief-fill"]) == 1, "the same run asked for twice is one run"
        assert st(i, KF) == "open" and st(m, km) == "open" and FL.filling() is True
    finally:
        go.set(); th.join(10); wait_fill(); FL.SYNC = True
    assert out == [dict(picked=3, nobody=0)], out
    assert st(i, KF) == "waiting" and cov(i, KF)[2]["pick"]["by"] == "ai", "a later date is picked at once"
    assert st(m, km) == "waiting" and cov(m, km)[2]["pick"]["by"] == "app", "the run asked for meanwhile ran after, with no hook: the app's own order"
    assert FL.filling() is False and not FL._busy.locked()

@ft
def no_model_call_is_made_while_the_lock_is_held():
    fresh()
    i = absent(by=GRACE)["id"]
    CV.change(i, K5, SAM, TEAMER, PUB, ST); CV.ask_change(i, K5, "A meeting", SAM)          # a request to change as well
    assert FL.run(call=first, now=mon("15:00")) == dict(picked=2, nobody=0)
    assert len(CALLS) == 2 and not any(c["locked"] for c in CALLS) and all(c["filling"] for c in CALLS), CALLS
    fresh(); del CALLS[:]
    i = absent(by=GRACE)["id"]
    FL.SYNC = False; PK.CALL = first
    try:
        FL.soon(force=True, date=D13); wait_fill()
    finally: FL.SYNC = True; PK.CALL = None
    assert len(CALLS) == 2 and not any(c["locked"] for c in CALLS) and (st(i, K2), st(i, K5)) == ("waiting", "waiting")
    assert FL.filling() is False and not AB._LOCK.locked()

@ft
def a_change_request_gets_a_new_pick_without_the_teacher_who_asked():
    fresh()
    i = absent(by=GRACE)["id"]
    CV.change(i, K5, SAM, TEAMER, PUB, ST)
    CV.ask_change(i, K5, "A meeting", SAM)
    assert FL.run(call=first, now=mon("09:00")) == dict(picked=2, nobody=0), "at once: Tuesday's open lesson and the request"
    assert [c["periods"] for c in CALLS] == ["P3–P5", "P6–P7"] and CALLS[1]["n"] == len(ORDER5) - 2, CALLS      # less the teacher who asked and Mr Flex Ng, just picked for P3-P5
    r, x, c = cov(i, K5)
    assert CV.state(r, x, c) == "change" and c["relief"] == SAM, "the relief stays with the teacher who asked until the team acts"
    assert c["change"]["pick"] == dict(who=TEAMER, by="ai", reason=f"{TEAMER} is free.", at=NOW), c["change"]      # Mr Flex Ng has P3-P5 now
    assert c["history"][-1] == dict(what="pick", who=TEAMER, by="ai", at=NOW, why=f"{TEAMER} is free.")
    assert st(i, K2) == "waiting"
    assert FL.run(call=first, now=mon("09:00")) == dict(picked=0, nobody=0) and len(CALLS) == 2, "it has its new pick"
    # set_pick never saves the teacher who asked as the new pick
    CV.keep(i, K5, TEAMER); CV.ask_change(i, K5, "Still a meeting", SAM)
    refuses(nf(SAM), lambda: CV.set_pick(i, K5, pk(SAM), PUB, ST, into="change"))
    # nobody else free: the request waits, open to the team
    with saved_settings(limits=dict(ONLY_SAM, never=ONLY_SAM["never"] + [BUSY])):
        assert FL.run(call=first, now=mon("09:00")) == dict(picked=1, nobody=1), "P3-P5's pick is no longer free and is made again; the request finds nobody"
    assert cov(i, K5)[2]["change"]["pick"] is None and len(CALLS) == 3
    assert FL.run(call=first, now=mon("09:00")) == dict(picked=1, nobody=0)

@ft
def a_stale_waiting_pick_is_dropped_and_picked_again():
    fresh()
    i = absent(by=GRACE, lessons=[dict(key=K5, relief=SAM)])["id"]              # the planner's choice, waiting for the team
    s = absent(teacher=SAM)["id"]                                                # then Mr Sam Tan's own absence for that day
    planned = ("pick", SAM, "planner")
    assert FL.run(call=first, now=mon("09:00")) == dict(picked=4, nobody=0), "dropped, then picked at once with Tue P3-P5 and Mr Sam Tan's two lessons"
    assert [c["periods"] for c in CALLS] == ["P1", "P3–P5", "P6–P7", "P10"], CALLS
    assert cov(i, K5)[2]["history"][-2]["why"] == nf(SAM)
    assert whats(cov(i, K5)[2]) == [planned, ("dropped", SAM, "app"), ("pick", relief_of(i, K5), "ai")] and relief_of(i, K5) not in (SAM, None)
    assert st(s, key(SAM, 0)) == "waiting"
    # a lesson that is over keeps what it had: nothing dropped, nothing picked
    fresh(); del CALLS[:]
    i = absent(by=GRACE, lessons=[dict(key=K2, relief=SAM)])["id"]
    absent(teacher=SAM)
    with at("2026-10-13T10:30:00+08:00"), logged() as got:                     # Tue P3-P5 has just ended
        FL.run(ids=[i], call=first)
        assert st(i, K2) == "waiting" and relief_of(i, K2) == SAM and got == [], got
        assert [c["periods"] for c in CALLS] == ["P6–P7"]
    # an approved relief is never dropped by the app: the team sees it is no longer free and changes it
    fresh()
    i = absent(by=GRACE)["id"]
    CV.change(i, K5, SAM, TEAMER, PUB, ST)
    absent(teacher=SAM)
    FL.run(call=first, now=mon("09:00"))
    assert st(i, K5) == "approved" and relief_of(i, K5) == SAM
    # drop(who=): a relief that is someone else's by now is not dropped
    fresh()
    i = absent(by=GRACE, lessons=[dict(key=K5, relief=SAM)])["id"]
    before = snap()
    same(CV.drop(i, K5, nf(MAYA), who=MAYA), i)
    assert snap() == before and st(i, K5) == "waiting" and relief_of(i, K5) == SAM
    CV.drop(i, K5, nf(SAM), who=SAM)
    assert st(i, K5) == "open"
    same(CV.drop(i, K5, nf(SAM), who=SAM), i)                                    # open now: nothing to drop
    refuses(CV.NOT_WAITING, lambda: CV.drop(i, K5, nf(SAM)))
    # the planner chooses again between the run's check and its drop: the fresh choice stays
    AB.choose(i, K5, SAM, GRACE, PUB)
    absent(teacher=SAM)
    real = CV.stale
    def stale_then_choose(*a, **kw):
        got = real(*a, **kw)
        if a[4]["key"] == K5 and AB._lesson(AB.load(i), K5)["relief"] == SAM: AB.choose(i, K5, MAYA, GRACE, PUB)
        return got
    CV.stale = stale_then_choose
    try: FL.run(call=first, now=mon("09:00"))
    finally: CV.stale = real
    assert st(i, K5) == "waiting" and relief_of(i, K5) == MAYA and cov(i, K5)[2]["pick"]["by"] == "planner"
    assert whats(cov(i, K5)[2])[-2:] == [("dropped", SAM, GRACE), ("pick", MAYA, "planner")], "the app dropped nothing"

@ft
def a_cover_that_cannot_be_picked_is_left_open_and_the_rest_go_on():
    fresh()
    i = absent(by=GRACE, dates=["2026-10-13", "2026-10-16"], lessons=[dict(key=K5, relief=SAM)])["id"]
    closed = dict(CAL, holidays=CAL["holidays"] + [dict(start="2026-10-13", end="2026-10-13", name="A sudden closure")])
    with saved_settings(calendar=closed), logged() as got:                       # Tuesday is no longer a school day
        assert FL.run(ids=[i], call=first, now=mon("15:00")) == dict(picked=1, nobody=0)
    assert (st(i, K2), st(i, K5), st(i, KF)) == ("open", "waiting", "waiting") and [c["periods"] for c in CALLS] == ["P1–P2"]
    assert [x.args for x in got] == [("ValueError",), ("ValueError",)], [x.args for x in got]
    said = " ".join(x.getMessage() for x in got)
    for bad in ("13 Oct", "school day", EVE, SAM, "Science"): assert bad not in said, bad
    assert all(x.exc_info is None for x in got)

@ft
def the_ticker_is_not_started_in_tests():
    assert "RELIEF_JOBS" not in os.environ and FL.ON is False and FL.EVERY == 60
    assert not any(x.name == "relief-ticker" for x in threading.enumerate()), "RELIEF_JOBS is unset: app.py starts no ticker"
    # with RELIEF_JOBS=on, importing the app starts it (in another process, with its own empty data folder)
    env = dict(os.environ, DATA_DIR=tempfile.mkdtemp(), RELIEF_JOBS="on")
    code = "import threading, app; from relief import fill; print(fill.ON, sorted(x.name for x in threading.enumerate() if x.name.startswith('relief')))"
    done = subprocess.run([sys.executable, "-c", code], env=env, cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert done.returncode == 0 and done.stdout.strip().splitlines()[-1] == "True ['relief-ticker']", (done.stdout[-300:], done.stderr[-300:])
    docker = open(os.path.join(ROOT, "Dockerfile")).read().splitlines()
    assert "ENV RELIEF_JOBS=on" in docker and docker.index("ENV RELIEF_JOBS=on") < [n for n, x in enumerate(docker) if x.startswith("CMD")][0]
    # a tick catches every error, logs its kind alone, and the ticker keeps going
    def boom(): raise RuntimeError(f"{EVE} Child sick sk-ant-test-{secrets.token_hex(4)}")
    store.published = boom
    with logged() as got:
        assert FL.tick() is None
        th = FL.start(every=0.01)
        try:
            assert th.name == "relief-ticker" and th.daemon and FL.start(every=0.01) is th, "started once"
            for _ in range(500):
                if len(got) >= 4: break
                time.sleep(0.01)
        finally: FL._stop.set(); th.join(5)
    assert not th.is_alive() and len(got) >= 4, len(got)
    assert {x.args for x in got} == {("RuntimeError",)} and all(x.exc_info is None and x.levelno == logging.ERROR for x in got)
    said = " ".join(x.getMessage() for x in got)
    for bad in (EVE, "Child sick", "sk-ant"): assert bad not in said, bad
    assert not FL._busy.locked()

# ---- Task 3 fix round 1 ----
@ft
def filling_is_true_from_fill_now_until_its_run_ends():
    fresh()
    i = absent(by=GRACE, dates=["2026-10-16"])["id"]
    inside, go = threading.Event(), threading.Event()
    def slow_pub():                                                              # a run that takes a moment before its first pick
        inside.set(); go.wait(10); return PUB
    store.published = slow_pub
    FL.SYNC = False
    try:
        assert FL.filling() is False
        assert FL.soon(date=D16, force=True) is True and FL.filling() is True, "at once after Fill now"
        assert inside.wait(10) and FL._busy.locked()
        assert FL.filling() is True, "while the run reads the timetable, before any pick"
    finally:
        go.set(); wait_fill(); FL.SYNC = True
    assert FL.filling() is False and st(i, KF) == "waiting"

@ft
def a_change_requests_new_pick_books_its_teacher():
    with saved_settings(limits=dict(ONLY_SAM, never=[NEVER, MAYA, GRACE, FLEX])) as s:     # for Tue P6-P7 and P7: Sam and Mr Team Lee
        def asked():
            i = absent(periods=[5, 6])["id"]                                     # Tue P6-P7, approved to Sam, who asks to change
            CV.change(i, K5, SAM, TEAMER, PUB, s); CV.ask_change(i, K5, "A meeting", SAM)
            return i
        fresh()
        i = asked()
        j = absent(teacher=RUTH, periods=[6, 6])["id"]                           # Tue P7, at the same time: open
        assert FL.run(call=first, now=mon("15:00")) == dict(picked=1, nobody=1)
        assert cov(i, K5)[2]["change"]["pick"]["who"] == TEAMER and st(j, KR6) == "open"
        recs = AB.all_records()
        assert FR.relief_periods(recs, TEAMER, {D13}) == 2 and FR.relief_periods(recs, TEAMER, {D13}, skip=(EVE, K5)) == 0
        assert FR.relief_periods(recs, SAM, {D13}) == 2, "the teacher who asked still counts until the team acts"
        assert TEAMER not in names(FR.free_then(PUB, s, recs, dict(cov(j, KR6)[1], key=KR6), RUTH))
        refuses(nf(TEAMER), lambda: CV.set_pick(j, KR6, pk(TEAMER), PUB, s))
        r, x, c = cov(i, K5)
        assert CV.still_free(PUB, s, recs, r, x, c, TEAMER), "the cover's own new pick takes nobody's time"
        e = absent(periods=[2, 4])["id"]                                         # the same teacher's Tue P3-P5: Mr Team Lee is free for it
        r, x, c = cov(e, K2)
        tl = next(y for y in PK.shortlist(PUB, s, AB.all_records(), r, x, c) if y["name"] == TEAMER)
        assert (tl["today"], tl["today_at"], tl["week_relief"], tl["by_day"]["Tue"]) == (2, [(5, 2)], 2, 2), "what the model is told counts it too"
        # across runs: the new pick first, the other absence after it
        fresh()
        i = asked()
        assert FL.run(call=first, now=mon("09:00")) == dict(picked=1, nobody=0)
        j = absent(teacher=RUTH, periods=[6, 6])["id"]
        assert FL.run(call=first, now=mon("15:00")) == dict(picked=0, nobody=1) and st(j, KR6) == "open"
        CV.approve(i, K5, TEAMER, TEAMER, PUB, s)
        recs = AB.all_records()
        assert relief_of(i, K5) == TEAMER and FR.relief_periods(recs, TEAMER, {D13}) == 2 and FR.relief_periods(recs, SAM, {D13}) == 0

@ft
def a_stale_new_pick_for_a_change_is_dropped_and_picked_again():
    def busiest(data):
        """a stand-in for the model: the teacher with the most teaching this week"""
        lab = max(data["teachers"], key=lambda x: x["teaching_this_week"])["label"]
        return dict(label=lab, reason=f"{lab} is free.")
    with saved_settings(limits=dict(ONLY_SAM, never=[NEVER, MAYA, GRACE, FLEX])) as s:     # for Tue P3-P5: Sam, Mr Busy Chan, Mr Team Lee
        fresh()
        i = absent(by=GRACE)["id"]
        CV.change(i, K2, SAM, TEAMER, PUB, s); CV.ask_change(i, K2, "A meeting", SAM)
        assert FL.run(call=busiest, now=mon("09:00")) == dict(picked=2, nobody=0), "the request and the open P6-P7 beside it"
        r, x, c = cov(i, K2)
        assert c["change"]["pick"]["who"] == BUSY and not CV.stale(PUB, s, AB.all_records(), r, x, c, into="change")
        absent(teacher=BUSY)                                                     # then Mr Busy Chan's own absence for that day
        r, x, c = cov(i, K2)
        assert CV.stale(PUB, s, AB.all_records(), r, x, c, into="change") and not CV.stale(PUB, s, AB.all_records(), r, x, c)
        assert FL.run(call=first, now=mon("09:00")) == dict(picked=3, nobody=0), "the new pick again, and Mr Busy Chan's own two lessons at once"
        r, x, c = cov(i, K2)
        assert CV.state(r, x, c) == "change" and c["relief"] == SAM and c["change"]["pick"]["who"] == TEAMER
        assert whats(c)[-3:] == [("pick", BUSY, "ai"), ("dropped", BUSY, "app"), ("pick", TEAMER, "ai")], whats(c)
        assert c["history"][-2]["why"] == nf(BUSY)
        # drop(into="change"): only the new pick it names, only while a request waits
        before = snap()
        same(CV.drop(i, K2, nf(BUSY), who=BUSY, into="change"), i)
        assert snap() == before and cov(i, K2)[2]["change"]["pick"]["who"] == TEAMER
        refuses(AB.WRONG, lambda: CV.drop(i, K2, "x", into="later"))
        CV.keep(i, K2, TEAMER)
        refuses(CV.NOT_WAITING, lambda: CV.drop(i, K2, nf(TEAMER), into="change"))
        assert not CV.stale(PUB, s, AB.all_records(), *cov(i, K2), into="change")

assert REAL == [], "a test reached the real call"

# ---- merged with relief stage 2 and the accounts: the rules are read against everyone the accounts know ----
@pt
def the_rules_are_read_against_everyone_the_accounts_know():
    fresh()
    OLIVE = "Mdm Olive Quek"                    # added on the admin page: on no timetable, so never on the shortlist
    AP.update(lambda d: d["people"].setdefault(OLIVE, {}).update(added=True, group="executive"))
    try:
        assert OLIVE in [p["name"] for p in AP.listing(PUB)] and OLIVE not in [p["name"] for p in P.people(PUB, [])]
        i = absent(by=GRACE)["id"]
        del SAYS[:]
        assert choose(i, K5, call=says("Teacher 1", "Teacher 1 is free."), st=dict(ST, rules=[f"Ask {OLIVE} first."]))["by"] == "ai"
        assert len(SAYS) == 1 and SAYS[0]["rules"] == ["Ask another teacher first."], SAYS
        assert choose(i, K5, call=says("Teacher 1", f"Teacher 1 is free, unlike {OLIVE}.")) == APP, "an answer naming her is refused"
    finally: AP.update(lambda d: d["people"].pop(OLIVE, None))

# ---- Task 4: routes for the team and the relief teacher ----
import csv, io, urllib.parse  # noqa: E402
import access, history as H  # noqa: E402
from relief import files as RF  # noqa: E402
# who plans and who is on the team: the accounts. Grace is a school leader (relief.plan); Mr Team Lee has the Relief team extra
AP.update(lambda d: d["people"].update({GRACE: dict(group="leader"), TEAMER: dict(extras=dict(relief=True, exams=None, admin=False))}))
TEAM_ONLY = "Only the relief team can open What's in."
NOT_YOURS = "This absence is not yours to open."
GONE_ABS = "That absence is not there any more."
SIGN_IN = "Please sign in again."
NO_PUB = "Publish the timetable first: relief reads the teachers from it."
STALE = "{name} is no longer free then: change it"
D2, D27 = D(2026, 10, 2), D(2026, 10, 27)
K5_27, K2_27 = K5.replace("2026-10-13", "2026-10-27"), K2.replace("2026-10-13", "2026-10-27")
HEAD = f"Relief for {EVE} on Tue 13 Oct: "

def q(s): return urllib.parse.quote(s, safe="")
def cover_url(i, ckey, what): return f"/api/relief/absences/{i}/covers/{q(ckey)}/{what}"
def lesson_url(i, key, what): return f"/api/relief/absences/{i}/lessons/{q(key)}/{what}"

def ok(r, code=200):
    assert r.status_code == code, (r.status_code, r.get_data(as_text=True)[:400])
    return r.get_json()

def no(r, code, text):
    assert r.status_code == code, (code, r.status_code, r.get_data(as_text=True)[:400])
    assert r.get_json() == {"error": text}, r.get_json()

def staff(name):
    """a client signed in by name with the person's own code"""
    c = A.app.test_client()
    r = c.post("/login", data={"code": access.staff_code(name)}); assert r.status_code == 302, (name, r.status_code)
    return c

def notes():
    """every relief history entry so far, oldest first: (what, who, text)"""
    return [(e["what"], e["who"], e["text"]) for e in reversed(H.read(kinds=["relief"], limit=2000)) if e.get("where") == "Relief"]

def body(teacher=EVE, **kw):
    """the body of POST /api/relief/absences: teacher's whole day on Tue 13 Oct"""
    d = dict(teacher=teacher, dates=["2026-10-13"], periods=None, reason="Medical", reason_text="", remarks="", reporting_officer=GRACE, lessons=[])
    d.update(kw); return d

def rt(f):
    """a route test: the published timetable is PUB, fill runs inline, no hook, an empty guard, automatic triggers off"""
    old = store.published; store.published = lambda: PUB
    FL.SYNC = True; FL.ON = False; PK.CALL = None; PK._seen.clear(); del CALLS[:]
    try: return t(f)
    finally:
        store.published = old; FL.SYNC = False; FL.ON = False; PK.CALL = None; PK._seen.clear()

ROW = {"id", "ckey", "key", "split", "absent", "classes", "subject", "group", "room", "p", "n", "start", "end", "work_set", "state", "pick",
       "approved", "ack", "change", "stale", "over_now", "nobody", "warn", "stopped", "duty", "told", "linked"}

@rt
def today_lists_covers_in_time_order_with_counts_and_no_reason():
    fresh()
    team = staff(TEAMER)
    i = absent(by=GRACE, reason="Other", reason_text="A private matter", remarks="Quiet please", lessons=[dict(key=K5, relief=SAM)])["id"]
    j = absent(teacher=RUTH, by=GRACE, reason="Child sick", lessons=[dict(key=KR6, relief=FLEX)])["id"]
    CV.approve(i, K5, SAM, TEAMER, PUB, ST)
    CV.change(i, K2, FLEX, TEAMER, PUB, ST)                          # P3-P5 to Mr Flex Ng, approved: with P7 too he goes over his 3
    AB.set_work(i, K5, dict(text="Read p.4", link="", files=[], known=[]), EVE)
    s = absent(teacher=SAM)["id"]                                     # Mr Sam Tan away too: his approved P6-P7 is stale now
    got = ok(team.get("/api/relief/today?date=2026-10-13"))
    assert got["date"] == "2026-10-13" and got["filling"] is False
    rows = got["rows"]
    assert [(r["p"], r["absent"]) for r in rows] == [(0, SAM), (2, EVE), (2, RUTH), (5, EVE), (6, RUTH), (9, SAM)], rows
    assert all(set(r) == ROW for r in rows), [set(r) ^ ROW for r in rows]
    assert got["counts"] == dict(need=6, waiting=1, approved=2, acknowledged=0, change=0, nobody=0, open=3), got["counts"]
    r5 = rows[3]
    assert r5 == dict(id=i, ckey=K5, key=K5, split=False, absent=EVE, classes=["1A"], subject="Science", group="", room="R1", p=5, n=2,
                      start="10:30", end="11:30", work_set=True, state="approved",
                      pick=dict(who=SAM, by="planner", reason=f"Planned by {GRACE} on Mon 12 Oct."), approved=dict(by=TEAMER, at=NOW),
                      ack=None, change=None, stale=True, over_now=False, nobody=False, warn=STALE.format(name=SAM), stopped="", duty="", told=None, linked=False), r5
    r2, r6 = rows[1], rows[4]
    assert (r2["state"], r2["pick"]["who"], r2["pick"]["by"], r2["stale"], r2["over_now"], r2["work_set"]) == ("approved", FLEX, "team", False, True, False), r2
    assert (r6["id"], r6["state"], r6["pick"], r6["approved"], r6["over_now"], r6["warn"]) == (
        j, "waiting", dict(who=FLEX, by="planner", reason=f"Planned by {GRACE} on Mon 12 Oct."), None, True, None), r6
    assert rows[0]["id"] == s and rows[0]["state"] == "open" and rows[0]["pick"] is None and rows[0]["nobody"] is False
    text = json.dumps(got)
    for secret in ("A private matter", "Other", "Child sick", "Medical", "Quiet please", "reason_text", "remarks", "reporting_officer"):
        assert secret not in text, secret
    # a request to change shows its new pick
    CV.ask_change(i, K5, "A parents' meeting", SAM)
    CV.set_pick(i, K5, pk(MAYA), PUB, ST, into="change")
    rows = ok(team.get("/api/relief/today?date=2026-10-13"))["rows"]
    c5 = rows[3]["change"]
    assert rows[3]["state"] == "change" and c5 == dict(why="A parents' meeting", at=NOW, pick=dict(who=MAYA, by="ai", reason=pk(MAYA)["reason"]), stale=False), c5
    # nobody free then at all (everyone on the "never" list): the open lessons say so, and so do the picks no longer free
    with saved_settings(limits=dict(fat_per_day=3, other_per_day=None, never=[x["name"] for x in ROWS])):
        got = ok(team.get("/api/relief/today?date=2026-10-13"))
    opened = [r for r in got["rows"] if r["state"] == "open"]
    assert opened and all(r["nobody"] and r["warn"] == "Nobody is free then." for r in opened) and got["counts"]["nobody"] == len(opened)
    rows = got["rows"]
    assert (rows[4]["state"], rows[4]["stale"], rows[4]["warn"]) == ("waiting", True, nf(FLEX)), rows[4]
    assert (rows[1]["state"], rows[1]["stale"], rows[1]["warn"]) == ("approved", True, STALE.format(name=FLEX)), rows[1]
    assert rows[3]["change"]["stale"] is True and rows[3]["warn"] == STALE.format(name=SAM), rows[3]
    # a cancelled absence stays on the day as cancelled, out of the counts; the default date is today; a bad date is refused
    AB.cancel(j, "Better", GRACE)
    got = ok(team.get("/api/relief/today?date=2026-10-13"))
    assert [r["state"] for r in got["rows"] if r["id"] == j] == ["cancelled", "cancelled"] and got["counts"]["need"] == 4, got["counts"]
    assert ok(team.get("/api/relief/today")) == dict(date="2026-10-12", filling=False, rows=[], telegram=False,
                                                    counts=dict(need=0, waiting=0, approved=0, acknowledged=0, change=0, nobody=0, open=0))
    no(team.get("/api/relief/today?date=13/10/2026"), 400, "Choose the dates again.")

OVER_ONLY = "Only teachers over a limit are free then: choose one yourself."

@rt
def today_says_when_only_people_over_a_limit_are_free():
    """an open cover where everyone free is over a checked limit: the app's run leaves it open (its shortlist drops them),
    so Today says the team must choose; it is not "nobody" """
    fresh()
    team = staff(TEAMER)
    absent()                                                          # Ms Evelyn Koh asks for Tue 13 Oct: P3-P5 and P6-P7 to cover
    rows = [r for r in ok(team.get("/api/relief/today?date=2026-10-13"))["rows"] if r["state"] == "open"]
    assert [(r["p"], r["n"], r["nobody"], r["warn"]) for r in rows] == [(2, 3, False, None), (5, 2, False, None)], rows
    with saved_settings(limits=dict(fat_per_day=1, other_per_day=1, never=[])):   # two periods or more take anyone over 1
        got = ok(team.get("/api/relief/today?date=2026-10-13"))
    rows = [r for r in got["rows"] if r["state"] == "open"]
    assert [(r["p"], r["nobody"], r["warn"]) for r in rows] == [(2, False, OVER_ONLY), (5, False, OVER_ONLY)], rows
    assert (got["counts"]["open"], got["counts"]["nobody"]) == (2, 0), got["counts"]

TEAM_ROUTES = lambda i: [("GET", "/api/relief/today?date=2026-10-13", None), ("POST", cover_url(i, K5, "approve"), None),
                         ("POST", "/api/relief/today/approve-all", dict(date="2026-10-13")), ("PUT", cover_url(i, K5, "relief"), dict(relief=MAYA)),
                         ("GET", cover_url(i, K5, "free"), None), ("POST", lesson_url(i, K2, "split"), dict(at=3)), ("POST", lesson_url(i, K2, "join"), None),
                         ("POST", cover_url(i, K5, "keep"), None), ("POST", "/api/relief/today/fill", dict(date="2026-10-13")),
                         ("GET", "/api/relief/load", None), ("GET", f"/api/relief/load/{q(SAM)}", None), ("GET", "/api/relief/load.csv", None)]

@rt
def approve_routes_need_the_team():
    fresh()
    i = absent(by=GRACE, lessons=[dict(key=K5, relief=SAM)])["id"]
    PK.CALL = first
    before, n = snap(), len(notes())
    for c in (staff(SAM), staff(GRACE), staff(EVE)):         # an ordinary teacher, a planner not on the team (her own absence), the absent teacher
        for method, url, b in TEAM_ROUTES(i) + TEAM_ROUTES("abcdef123456"):
            no(c.open(url, method=method, json=b), 403, TEAM_ONLY)
    assert snap() == before and len(notes()) == n and CALLS == [], "nothing written, nothing picked"

@rt
def the_team_approves_changes_splits_and_keeps_through_the_api():
    fresh()
    team = staff(TEAMER)
    i = absent(by=GRACE, lessons=[dict(key=K5, relief=SAM)])["id"]           # P3-P5 open, P6-P7 waiting for Mr Sam Tan
    j = absent(teacher=RUTH, by=GRACE, lessons=[dict(key=KR6, relief=FLEX)])["id"]
    n = len(notes())
    got = ok(team.post(cover_url(i, K5, "approve"), json=dict(who=SAM)))
    assert [x["covers"] for x in got["lessons"] if x["key"] == K5] == [[dict(ckey=K5, p=5, n=2, start="10:30", end="11:30", state="approved", relief=SAM, planned=None)]]
    assert got["reason"] == "Medical", "the team sees the whole record"
    no(team.post(cover_url(i, K5, "approve"), json=dict(who=SAM)), 400, CV.NOT_WAITING)
    no(team.post(cover_url(i, "nokey", "approve"), json=dict(who=SAM)), 400, AB.CHANGED)
    no(team.post(cover_url("abcdef123456", K5, "approve"), json=dict(who=SAM)), 404, GONE_ABS)
    # approve all: the waiting ones of the day in time order, a stale one skipped and named
    CV.set_pick(i, K2, pk(BUSY), PUB, ST)
    absent(teacher=BUSY)                                                       # then Mr Busy Chan asks for relief himself
    for bad in ("13/10/2026", 5, None, "", "2026-13-40"):
        no(team.post("/api/relief/today/approve-all", json=dict(date=bad)), 400, AB.WRONG)
    no(team.post("/api/relief/today/approve-all", json=dict(date="2026-10-09")), 400, AB.PAST_LESSON)
    no(team.post("/api/relief/today/approve-all", json=dict(date="2026-10-13")), 400, CV.PICK_CHANGED)   # not what the page showed
    shown = [dict(id=i, ckey=K2, who=BUSY), dict(id=j, ckey=KR6, who=FLEX)]
    for bad in ("x", [None], [dict(id=i, ckey=5, who=BUSY)], [dict(ckey=K2, who=BUSY)]):
        no(team.post("/api/relief/today/approve-all", json=dict(date="2026-10-13", covers=bad)), 400, AB.WRONG)
    assert (st(j, KR6), st(i, K2)) == ("waiting", "waiting")
    got = ok(team.post("/api/relief/today/approve-all", json=dict(date="2026-10-13", covers=shown)))
    assert got == dict(approved=1, skipped=[dict(id=i, ckey=K2, name=BUSY, why=nf(BUSY))]), got
    assert (st(j, KR6), st(i, K2)) == ("approved", "waiting")
    # Change: the free-then list for the cover, then chosen and approved in one
    free = ok(team.get(cover_url(i, K2, "free")))
    assert BUSY not in names(free) and MAYA in names(free) and set(free) == {"groups", "teaching", "busy"}, free
    no(team.get(cover_url(i, "nokey", "free")), 400, AB.CHANGED)
    no(team.get(cover_url(i, K8, "free")), 400, AB.NO_NEED)
    no(team.put(cover_url(i, K2, "relief"), json=dict(relief=BUSY)), 400, nf(BUSY))
    for bad in ({}, dict(relief=None), dict(relief=["x"])):
        no(team.put(cover_url(i, K2, "relief"), json=bad), 400, AB.WRONG)
    ok(team.put(cover_url(i, K2, "relief"), json=dict(relief=MAYA)))
    assert st(i, K2) == "approved" and relief_of(i, K2) == MAYA
    # Split and Join again
    l = absent(by=GRACE, dates=["2026-10-16"])["id"]                          # Fri P1-P2
    no(team.post(lesson_url(j, KR6, "split"), json=dict(at=6)), 400, CV.NO_SPLIT)
    no(team.post(lesson_url(l, KF, "split"), json=dict(at="1")), 400, AB.WRONG)
    got = ok(team.post(lesson_url(l, KF, "split"), json=dict(at=1)))
    assert [c["ckey"] for x in got["lessons"] for c in x["covers"]] == [KF + "#0", KF + "#1"]
    ok(team.post(lesson_url(l, KF, "join")))
    no(team.post(lesson_url(l, KF, "join")), 400, AB.CHANGED)
    # Keep: a request to change closed, the relief stays
    CV.ask_change(i, K5, "A meeting", SAM)
    no(team.post(cover_url(i, K2, "keep")), 400, CV.NO_CHANGE_ASKED)
    ok(team.post(cover_url(i, K5, "keep")))
    assert st(i, K5) == "approved" and relief_of(i, K5) == SAM
    # Fill now: every open cover of the date, due or not
    PK.CALL = first
    for bad in (dict(date="nope"), dict(date=7)):
        no(team.post("/api/relief/today/fill", json=bad), 400, AB.WRONG)
    assert st(l, KF) == "open"
    assert ok(team.post("/api/relief/today/fill", json=dict(date="2026-10-16"))) == dict(date="2026-10-16", started=True, filling=False)
    assert st(l, KF) == "waiting" and len(CALLS) == 1
    # one history entry a save, by whoever made it; a refusal and the app's own picks write none
    got = notes()[n:]
    fri = f"Relief for {EVE} on Fri 16 Oct: "
    assert got == [("approved", TEAMER, HEAD + f"{SAM} approved for 1A Science P6–P7 on Tue 13 Oct"),
                   ("approved", TEAMER, f"Relief for {RUTH} on Tue 13 Oct: {FLEX} approved for 3B Physics P7 on Tue 13 Oct"),
                   ("changed", TEAMER, HEAD + f"{MAYA} chosen and approved for 1C Science P3–P5 on Tue 13 Oct"),
                   ("split", TEAMER, fri + "1A Art on Fri 16 Oct split before P2"),
                   ("joined", TEAMER, fri + "1A Art on Fri 16 Oct joined again"),
                   ("kept", TEAMER, HEAD + f"{SAM} kept for 1A Science P6–P7 on Tue 13 Oct")], got

COVER = {"id", "ckey", "date", "start", "end", "p", "n", "classes", "subject", "group", "room", "absent", "work", "state", "ack", "change", "stopped"}

@rt
def covering_lists_only_approved_and_never_the_reason():
    fresh()
    k2 = key(EVE, 0, D2)
    with at("2026-10-02T07:00:00+08:00"):                                     # Fri 2 Oct, last week's: approved to Mr Sam Tan
        old = absent(by=GRACE, dates=["2026-10-02"], lessons=[dict(key=k2, relief=SAM)])["id"]
        CV.approve(old, k2, SAM, TEAMER, PUB, ST)
    i = absent(by=GRACE, dates=["2026-10-13", "2026-10-16"], reason="Other", reason_text="A private matter", remarks="Quiet please",
               lessons=[dict(key=K5, relief=SAM), dict(key=K2, relief=SAM), dict(key=KF, relief=SAM)])["id"]
    j = absent(teacher=RUTH, by=GRACE, lessons=[dict(key=KR6, relief=MAYA)])["id"]
    f = RF.save(i, "notes.pdf", b"%PDF-1 notes")
    AB.set_work(i, K5, dict(text="Read p.4", link="https://x.test/a", files=[f], known=[]), EVE)
    for ckey in (K5, KF): CV.approve(i, ckey, SAM, TEAMER, PUB, ST)
    CV.approve(j, KR6, MAYA, TEAMER, PUB, ST)
    sam = staff(SAM)
    with at("2026-10-14T08:00:00+08:00"):                                     # Wednesday: Tuesday's is earlier this week
        r = sam.get("/api/relief/covering"); got = ok(r)
    assert [(c["date"], c["ckey"]) for c in got["covers"]] == [("2026-10-13", K5), ("2026-10-16", KF)], got
    assert all(set(c) == COVER for c in got["covers"]), [set(c) ^ COVER for c in got["covers"]]
    assert got["covers"][0] == dict(id=i, ckey=K5, date="2026-10-13", start="10:30", end="11:30", p=5, n=2, classes=["1A"], subject="Science",
                                    group="", room="R1", absent=EVE, work=dict(text="Read p.4", link="https://x.test/a", files=[f]),
                                    state="approved", ack=None, change=None, stopped=""), got["covers"][0]
    text = r.get_data(as_text=True)
    for secret in ("A private matter", "Other", "Quiet please", "Medical", GRACE, "Planned by", "history", "reason", "remarks", "reporting_officer", "pick"):
        assert secret not in text, secret
    assert ok(staff(MAYA).get("/api/relief/covering"))["covers"][0]["ckey"] == KR6
    assert ok(staff(RUTH).get("/api/relief/covering"))["covers"] == []
    # not needed, or cancelled: it leaves the list
    AB.not_needed(i, KF, "Covered", EVE)
    assert [c["ckey"] for c in ok(sam.get("/api/relief/covering"))["covers"]] == [K5]
    AB.cancel(i, "Better", GRACE)
    assert ok(sam.get("/api/relief/covering"))["covers"] == []

NOT_YOURS_COVER = "This relief is not yours."

@rt
def acknowledge_and_ask_change_are_the_relief_teachers_alone():
    fresh()
    sam, ruth, team, eve, grace = staff(SAM), staff(RUTH), staff(TEAMER), staff(EVE), staff(GRACE)
    i = absent(by=GRACE, lessons=[dict(key=K5, relief=SAM), dict(key=K2, relief=FLEX)])["id"]
    PK.CALL = first
    before = snap()
    for c in (sam, ruth, team, eve, grace):                                   # waiting: nobody's yet, not even Mr Sam Tan's
        no(c.post(cover_url(i, K5, "acknowledge")), 403, NOT_YOURS_COVER)
        no(c.post(cover_url(i, K5, "ask-change"), json=dict(why="A meeting")), 403, NOT_YOURS_COVER)
    assert snap() == before
    CV.approve(i, K5, SAM, TEAMER, PUB, ST)
    before, n = snap(), len(notes())
    for c in (ruth, team, eve, grace):
        no(c.post(cover_url(i, K5, "acknowledge")), 403, NOT_YOURS_COVER)
        no(c.post(cover_url(i, K5, "ask-change"), json=dict(why="A meeting")), 403, NOT_YOURS_COVER)
    for url in (cover_url("abcdef123456", K5, "acknowledge"), cover_url("nope", K5, "acknowledge"), cover_url(i, "nokey", "acknowledge"), cover_url(i, K2, "acknowledge")):
        no(sam.post(url), 403, NOT_YOURS_COVER)
    assert snap() == before and len(notes()) == n and CALLS == []
    got = ok(sam.post(cover_url(i, K5, "acknowledge")))
    assert set(got) == COVER and (got["state"], got["ack"], got["change"]) == ("acknowledged", dict(at=NOW), None), got
    ok(sam.post(cover_url(i, K5, "acknowledge")))                             # twice is once: one entry
    for bad in (dict(why=" "), dict(why="x" * 201), {}):
        no(sam.post(cover_url(i, K5, "ask-change"), json=bad), 400, CV.CHANGE_WHY)
    assert CALLS == []
    r = sam.post(cover_url(i, K5, "ask-change"), json=dict(why="A parents' meeting then"))
    got = ok(r)
    assert (got["state"], got["ack"], got["change"]) == ("change", None, dict(why="A parents' meeting then", at=NOW)), got
    assert "pick" not in r.get_data(as_text=True) and "reason" not in r.get_data(as_text=True)
    new = cov(i, K5)[2]["change"]["pick"]
    assert len(CALLS) == 1 and new and new["who"] not in (SAM, None), "a request to change gets a new pick at once (Fill now's force)"
    assert ok(sam.get("/api/relief/covering"))["covers"][0]["change"] == dict(why="A parents' meeting then", at=NOW)
    no(sam.post(cover_url(i, K5, "ask-change"), json=dict(why="Again")), 400, CV.ASKED_ALREADY)
    got = notes()[n:]
    assert got == [("relief acknowledged", SAM, HEAD + f"{SAM} acknowledged 1A Science P6–P7 on Tue 13 Oct"),
                   ("asked to change", SAM, HEAD + f"{SAM} asked to change 1A Science P6–P7 on Tue 13 Oct")], got
    assert "parents" not in json.dumps(got), "never the why"

@rt
def the_relief_teacher_can_open_the_work_file():
    fresh()
    sam, ruth, maya = staff(SAM), staff(RUTH), staff(MAYA)
    i = absent(by=GRACE, lessons=[dict(key=K5, relief=SAM)])["id"]
    f, g = RF.save(i, "notes.pdf", b"%PDF-1 notes"), RF.save(i, "other.pdf", b"%PDF-1 other")
    AB.set_work(i, K5, dict(text="", link="", files=[f], known=[]), EVE)
    AB.set_work(i, K2, dict(text="", link="", files=[g], known=[]), EVE)
    url = lambda x: f"/api/relief/files/{i}/{x['id']}"
    no(sam.get(url(f)), 403, NOT_YOURS)                                       # waiting: not his yet
    CV.approve(i, K5, SAM, TEAMER, PUB, ST)
    r = sam.get(url(f))
    assert r.status_code == 200 and r.data == b"%PDF-1 notes" and "notes.pdf" in r.headers["Content-Disposition"] and "no-store" in r.headers["Cache-Control"]
    r.close()
    no(sam.get(url(g)), 403, NOT_YOURS)                                       # another lesson's file
    no(sam.get(f"/api/relief/files/{i}/abcdef123456"), 403, NOT_YOURS)
    no(ruth.get(url(f)), 403, NOT_YOURS)
    no(sam.get(f"/api/relief/files/abcdef123456/{f['id']}"), 403, NOT_YOURS)
    # a part of a split lesson: its relief teacher opens the lesson's files
    CV.split(i, K2, 3, TEAMER); CV.change(i, K2 + "#1", MAYA, TEAMER, PUB, ST)
    r = maya.get(url(g)); assert r.status_code == 200 and r.data == b"%PDF-1 other"; r.close()
    no(maya.get(url(f)), 403, NOT_YOURS)
    AB.cancel(i, "Better", GRACE)
    no(sam.get(url(f)), 403, NOT_YOURS)
    no(maya.get(url(g)), 403, NOT_YOURS)

@rt
def the_absent_teacher_sees_the_name_only_once_approved():
    fresh()
    eve, grace, team = staff(EVE), staff(GRACE), staff(TEAMER)
    i = absent(by=GRACE, lessons=[dict(key=K5, relief=SAM)])["id"]           # the planner's choice, waiting
    CV.set_pick(i, K2, pk(FLEX), PUB, ST)                                     # the AI's pick, waiting
    def lesson(c, k, url=None):
        got = ok(c.get(url or f"/api/relief/absences/{i}"))
        rec = got if url is None else next(x for x in got["absences"] if x["id"] == i)
        return next(x for x in rec["lessons"] if x["key"] == k)
    for url in (None, "/api/relief/absences/mine"):
        e5, e2 = lesson(eve, K5, url), lesson(eve, K2, url)
        assert (e5["relief"], e5["relief_by"], e2["relief"]) == (None, None, None), (e5, e2)
        assert not {"pick", "history", "change", "planned"} & (set(e5) | set(e2)), (set(e5), set(e2))
        assert e5["covers"] == [dict(ckey=K5, p=5, n=2, start="10:30", end="11:30", state="waiting", relief=None)], e5["covers"]
    text = eve.get(f"/api/relief/absences/{i}").get_data(as_text=True) + eve.get("/api/relief/absences/mine").get_data(as_text=True)
    assert SAM not in text and FLEX not in text and "Teacher 1 is free" not in text and "Planned by" not in text
    for c in (grace, team):                                                   # the planner and the team: the name, and the planner's own choice
        g5, g2 = lesson(c, K5), lesson(c, K2)
        assert (g5["relief"], g5["planned"], g5["covers"][0]["planned"], g2["relief"], g2["planned"]) == (SAM, SAM, SAM, FLEX, None), (g5, g2)
        assert g2["pick"]["by"] == "ai" and g2["history"], g2
    CV.approve(i, K5, SAM, TEAMER, PUB, ST)
    e5 = lesson(eve, K5)
    assert e5["relief"] == SAM and e5["covers"][0]["state"] == "approved" and e5["covers"][0]["relief"] == SAM and "pick" not in e5, e5
    assert lesson(grace, K5)["planned"] is None
    no(grace.put(lesson_url(i, K5, "relief"), json=dict(relief=MAYA)), 400, AB.APPROVED_ALREADY)   # the planner no longer changes it (Ruling 11)
    CV.ask_change(i, K5, "A parents' meeting", SAM); CV.set_pick(i, K5, pk(MAYA), PUB, ST, into="change")
    e5 = lesson(eve, K5)
    assert e5["relief"] == SAM and e5["covers"][0]["state"] == "change" and "change" not in e5, e5
    assert MAYA not in eve.get(f"/api/relief/absences/{i}").get_data(as_text=True) and "parents" not in eve.get("/api/relief/absences/mine").get_data(as_text=True)
    # an absence the teacher asked for herself: the same
    j = absent(teacher=RUTH)["id"]
    CV.set_pick(j, KR6, pk(TEAMER), PUB, ST)
    got = ok(staff(RUTH).get(f"/api/relief/absences/{j}"))
    assert [(x["relief"], x["covers"][0]["state"]) for x in got["lessons"]] == [(None, "open"), (None, "waiting")] and TEAMER not in json.dumps(got["lessons"])
    # a split lesson's parts are hidden the same way
    CV.split(i, K2, 3, TEAMER); CV.set_pick(i, K2 + "#1", pk(GRACE), PUB, ST)
    no(grace.put(lesson_url(i, K2, "relief"), json=dict(relief=MAYA)), 400, AB.IS_SPLIT)          # the team chooses part by part
    e2 = lesson(eve, K2)
    assert [p.get("relief") for p in e2["parts"]] == [None, None] and not any({"pick", "history", "change"} & set(p) for p in e2["parts"]), e2["parts"]
    assert "history" not in e2 and [c["state"] for c in e2["covers"]] == ["open", "waiting"]

LOAD = {"name", "depts", "fat", "teaching", "relief", "exams", "week", "term", "changes"}

@rt
def load_counts_teaching_and_relief_for_the_week_and_term():
    fresh()
    team = staff(TEAMER)
    i = absent(by=GRACE, lessons=[dict(key=K5, relief=SAM)])["id"]
    CV.approve(i, K5, SAM, TEAMER, PUB, ST)
    CV.set_pick(i, K2, pk(FLEX), PUB, ST)                                     # waiting: counted, as the free-then counts do
    absent(by=GRACE, dates=["2026-10-27"], lessons=[dict(key=K5_27, relief=SAM)])   # later in the term
    CV.ask_change(i, K5, "A meeting", SAM); CV.set_pick(i, K5, pk(MAYA), PUB, ST, into="change")   # the new pick books Ms Maya Lee too
    got = ok(team.get("/api/relief/load"))
    assert got["week"] == dict(start="2026-10-12", end="2026-10-16") and got["term"] == dict(name="Term 4", start="2026-09-07", end="2026-11-20"), got
    rows = {r["name"]: r for r in got["rows"]}
    assert all(set(r) == LOAD for r in got["rows"])
    assert [r["name"] for r in got["rows"]] == [BUSY, MAYA, SAM, EVE, RUTH, FLEX], "by first department then name, none last; nobody with no teaching and no relief"
    assert rows[SAM] == dict(name=SAM, depts=["Science"], fat=False, teaching=2, relief=2, exams=0, week=4, term=4, changes=1), rows[SAM]
    assert rows[FLEX] == dict(name=FLEX, depts=[], fat=True, teaching=0, relief=3, exams=0, week=3, term=3, changes=0), rows[FLEX]
    assert rows[MAYA] == dict(name=MAYA, depts=["Mathematics"], fat=False, teaching=2, relief=2, exams=0, week=4, term=2, changes=0), rows[MAYA]
    assert (rows[EVE]["teaching"], rows[EVE]["relief"], rows[BUSY]["teaching"]) == (8, 0, 2)
    for want in (BUSY, MAYA, SAM, EVE, RUTH, FLEX):
        assert FR.week_so_far(PUB, CAL, AB.all_records(), want, D13) == rows[want]["week"], want
    later = {r["name"]: r for r in ok(team.get("/api/relief/load?week=2026-10-27"))["rows"]}
    assert (later[SAM]["relief"], later[SAM]["term"], later[FLEX]["relief"], later[FLEX]["term"]) == (2, 4, 0, 3), later
    assert ok(team.get("/api/relief/load?term=Term%204"))["rows"] == got["rows"]
    no(team.get("/api/relief/load?term=Term%209"), 400, "Choose the term again.")
    no(team.get("/api/relief/load?week=nope"), 400, "Choose the dates again.")
    # a name: every relief they took this term, with the pick's reason and who approved it
    one = ok(team.get(f"/api/relief/load/{q(SAM)}"))
    assert one["name"] == SAM and one["term"]["name"] == "Term 4"
    assert [(x["date"], x["lesson"], x["absent"], x["state"], x["reason"], x["approved_by"]) for x in one["reliefs"]] == [
        ("2026-10-13", "1A Science P6–P7", EVE, "change", f"Planned by {GRACE} on Mon 12 Oct.", TEAMER),
        ("2026-10-27", "1A Science P6–P7", EVE, "waiting", f"Planned by {GRACE} on Mon 12 Oct.", None)], one["reliefs"]
    m = ok(team.get(f"/api/relief/load/{q(MAYA)}"))["reliefs"]
    assert [(x["date"], x["state"], x["reason"], x["approved_by"]) for x in m] == [("2026-10-13", "new pick", pk(MAYA)["reason"], None)], m
    no(team.get(f"/api/relief/load/{q('Mr Nobody')}"), 400, "Mr Nobody is not on the published timetable or the staff list.")
    with saved_settings(calendar=dict(terms=[], holidays=[])):
        no(team.get("/api/relief/load"), 400, LS.NO_CALENDAR)

@rt
def load_csv_neutralises_formulas():
    fresh()
    odd = "=HYPERLINK(1)"
    pub = world(extra=[L(TUE, 0, 1, ["9Z"], "Art", [odd])])
    pub["model"]["setup"]["teachers"].append(dict(name=odd, dept="+Dept", dept2=None, role=None, short=None))
    store.published = lambda: pub
    team = staff(TEAMER)
    i = absent(by=GRACE, lessons=[dict(key=K5, relief=SAM)])["id"]
    CV.approve(i, K5, SAM, TEAMER, pub, ST)
    r = team.get("/api/relief/load.csv?week=2026-10-13")
    assert r.status_code == 200 and r.mimetype == "text/csv" and r.headers["Content-Disposition"] == 'attachment; filename="relief load 2026-10-12.csv"', r.headers
    text = r.data.decode("utf-8")
    assert text.startswith("﻿")
    rows = list(csv.reader(io.StringIO(text.lstrip("﻿"))))
    assert rows[0] == ["Name", "Departments", "Flexi Adjunct", "Teaching this week", "Relief this week", "Exams and events this week", "Week so far",
                       "Relief this term", "Requests to change this term"], rows[0]
    assert ["'=HYPERLINK(1)", "'+Dept", "", "1", "0", "0", "1", "0", "0"] in rows, rows
    assert [SAM, "Science", "", "2", "2", "0", "4", "2", "0"] in rows and [FLEX, "", "Yes", "0", "0", "0", "0", "0", "0"] not in rows, rows
    names_ = [x["name"] for x in ok(team.get("/api/relief/load?week=2026-10-13"))["rows"]]
    assert [x[0] for x in rows[1:]] == ["'" + n if n.startswith("=") else n for n in names_] and names_[0] == odd, (rows, names_)
    no(team.get("/api/relief/load.csv?week=nope"), 400, "Choose the dates again.")

@rt
def whats_in_counts_covers_and_marks_the_nudge():
    fresh()
    team = staff(TEAMER)
    i = absent(by=GRACE, lessons=[dict(key=K5, relief=SAM)])["id"]           # Tue 13: P3-P5 open, P6-P7 waiting, P9 not needed
    j = absent(teacher=RUTH)["id"]                                             # asked by Ms Ruth Goh herself: never a nudge
    k = absent(by=GRACE, dates=["2026-10-16"])["id"]                           # Fri 16: a nudge from Thu 15 at 15:00
    def got():
        rows = {x["id"]: x for x in ok(team.get("/api/relief/absences"))["absences"]}
        return {x: (rows[x]["cover"], rows[x]["nudge"]) for x in (i, j, k)}
    g = got()
    assert g[i] == (dict(total=2, approved=0, waiting=1, open=1), False) and g[j] == (dict(total=2, approved=0, waiting=0, open=2), False), g
    CV.approve(i, K5, SAM, TEAMER, PUB, ST)
    CV.split(i, K2, 3, TEAMER); CV.set_pick(i, K2 + "#1", pk(FLEX), PUB, ST)
    assert got()[i][0] == dict(total=3, approved=1, waiting=1, open=1), got()[i]
    with at("2026-10-12T14:59:00+08:00"): assert [v[1] for v in got().values()] == [False, False, False]
    with at("2026-10-12T15:00:00+08:00"): assert [v[1] for v in got().values()] == [True, False, False]
    with at("2026-10-15T15:00:00+08:00"): assert [v[1] for v in got().values()] == [False, False, True], "Tuesday's is past"
    with saved_settings(times=dict(fill_at="15:00", remind_at="16:30", report_every=15, weekly_day="Fri", weekly_at="15:00")):
        with at("2026-10-15T16:00:00+08:00"): assert got()[k][1] is False
        with at("2026-10-15T16:30:00+08:00"): assert got()[k][1] is True
    AB.acknowledge(k, EVE)
    with at("2026-10-15T15:00:00+08:00"): assert got()[k][1] is False, "acknowledged"
    AB.cancel(i, "Better", GRACE)
    with at("2026-10-12T15:00:00+08:00"): assert got()[i] == (dict(total=0, approved=0, waiting=0, open=0), False), "cancelled"

@rt
def an_absence_for_today_gets_its_picks_at_once():
    fresh()
    calls, real = [], FL.soon
    def spy(*a, **kw):
        calls.append((a, kw, AB._LOCK.locked())); return real(*a, **kw)
    FL.soon = spy
    try:
        with at("2026-10-13T08:00:00+08:00"):
            eve, sam = staff(EVE), staff(SAM)
            PK.CALL = first
            i = ok(eve.post("/api/relief/absences", json=body(EVE)))["id"]
            assert (st(i, K2), st(i, K5)) == ("open", "open") and CALLS == [], "RELIEF_JOBS is not on: an automatic trigger does nothing"
            ok(eve.post(f"/api/relief/absences/{i}/cancel", json=dict(why="Better")))
            FL.ON = True
            j = ok(eve.post("/api/relief/absences", json=body(EVE)))["id"]
            assert (st(j, K2), st(j, K5), st(j, K8)) == ("waiting", "waiting", "cancelled"), "with RELIEF_JOBS on, picked at once"
            ok(eve.post(lesson_url(j, K8, "needed")))
            assert st(j, K8) == "waiting", "needed again: picked at once"
            assert relief_of(j, K5) == SAM
            ok(sam.post("/api/relief/absences", json=body(SAM)))   # Mr Sam Tan away too: no longer anyone's waiting pick
            assert relief_of(j, K5) not in (None, SAM) and st(j, K5) == "waiting", relief_of(j, K5)
        assert [(a, kw, locked) for a, kw, locked in calls] == [((), {}, False)] * 5, calls
    finally: FL.soon = real

@rt
def soon_logs_and_returns_when_no_thread_can_start():
    team = staff(TEAMER)
    FL.SYNC = False
    old = threading.Thread.start
    def refuse(self): raise RuntimeError("can't start new thread")
    try:
        with logged() as got:
            threading.Thread.start = refuse
            try:
                assert FL.soon(date=D16, force=True) is False and FL.filling() is False and not FL._asked
                assert ok(team.post("/api/relief/today/fill", json=dict(date="2026-10-16"))) == dict(date="2026-10-16", started=False, filling=False)
            finally: threading.Thread.start = old
        assert [(x.args, x.levelno) for x in got] == [(("RuntimeError",), logging.ERROR)] * 2, [(x.args, x.levelno) for x in got]
    finally: FL.SYNC = True

@rt
def a_split_lesson_reads_its_parts_in_the_record_and_the_sheet():
    fresh()
    team, grace = staff(TEAMER), staff(GRACE)
    i = absent(by=GRACE)["id"]
    CV.split(i, K2, 4, TEAMER); CV.split(i, K2, 3, TEAMER)                    # parts P3, P5, P4: the newest part is last
    CV.change(i, K2 + "#1", FLEX, TEAMER, PUB, ST); CV.set_pick(i, K2 + "#2", pk(SAM), PUB, ST)
    x = next(x for x in ok(team.get(f"/api/relief/absences/{i}"))["lessons"] if x["key"] == K2)
    assert x["covers"] == [dict(ckey=K2 + "#0", p=2, n=1, start="09:00", end="09:30", state="open", relief=None, planned=None),
                           dict(ckey=K2 + "#2", p=3, n=1, start="09:30", end="10:00", state="waiting", relief=SAM, planned=None),
                           dict(ckey=K2 + "#1", p=4, n=1, start="10:00", end="10:30", state="approved", relief=FLEX, planned=None)], x["covers"]
    # the parts themselves are sent in time order too, each with its own key: parts[i] is never key#i (Ruling 22)
    stored = AB._lesson(AB.load(i), K2)["parts"]
    assert [(c["p"], c["relief"]) for c in stored] == [(2, None), (4, FLEX), (3, SAM)], "stored: the newest part last"
    want = [(K2 + "#0", 2, None), (K2 + "#2", 3, SAM), (K2 + "#1", 4, FLEX)]
    for c, who in ((team, TEAMER), (grace, GRACE)):
        parts = next(x for x in ok(c.get(f"/api/relief/absences/{i}"))["lessons"] if x["key"] == K2)["parts"]
        assert [(p["ckey"], p["p"], p["relief"]) for p in parts] == want, (who, parts)
        assert parts[1]["pick"]["who"] == SAM and parts[2]["approved"]["by"] == TEAMER, (who, parts)
    for url in (f"/api/relief/absences/{i}", "/api/relief/absences/mine"):     # the absent teacher's view: hidden, in the same order
        got = ok(staff(EVE).get(url))
        rec = got if "lessons" in got else next(v for v in got["absences"] if v["id"] == i)
        parts = next(x for x in rec["lessons"] if x["key"] == K2)["parts"]
        assert [(p["ckey"], p["p"], p["relief"]) for p in parts] == [(K2 + "#0", 2, None), (K2 + "#2", 3, None), (K2 + "#1", 4, FLEX)], (url, parts)
        assert not any({"pick", "history", "change"} & set(p) for p in parts), parts
    assert AB._lesson(AB.load(i), K2)["parts"] == stored and "ckey" not in stored[0], "sending never changes the record"
    assert next(v for v in ok(team.get("/api/relief/absences"))["absences"] if v["id"] == i)["cover"] == dict(total=4, approved=1, waiting=1, open=2)
    rows = list(csv.reader(io.StringIO(grace.get("/api/relief/planned.csv?start=2026-10-13").data.decode("utf-8").lstrip("﻿"))))
    assert [r[2:6] for r in rows[1:]] == [["1C Science", "P3", "09:00–09:30", "Not chosen yet"], ["1C Science", "P4", "09:30–10:00", "Waiting for the relief team"],
                                          ["1C Science", "P5", "10:00–10:30", FLEX], ["1A Science", "P6–P7", "10:30–11:30", "Not chosen yet"]], rows
    rows = ok(team.get("/api/relief/today?date=2026-10-13"))["rows"]
    assert [(r["ckey"], r["key"], r["split"], r["p"], r["start"]) for r in rows] == [(K2 + "#0", K2, True, 2, "09:00"), (K2 + "#2", K2, True, 3, "09:30"),
                                                                                    (K2 + "#1", K2, True, 4, "10:00"), (K5, K5, False, 5, "10:30")], rows

@rt
def the_new_routes_answer_signed_out_and_unpublished():
    x = "abcdef123456"
    routes = [(m, u) for m, u, b in TEAM_ROUTES(x)] + [("GET", "/api/relief/covering"), ("POST", cover_url(x, K5, "acknowledge")),
                                                       ("POST", cover_url(x, K5, "ask-change"))]
    team = staff(TEAMER)
    for method, url in routes:
        no(A.app.test_client().open(url, method=method, json={}), 401, SIGN_IN)
    store.published = lambda: None
    for method, url in routes:
        no(team.open(url, method=method, json={}), 409, NO_PUB)

# ---- the final fix wave: Approve approves what the team member saw (Rulings 26 to 29) ----
def who_shown(row):
    """the name a Today row shows beside Approve: the waiting pick, or a request to change's new pick"""
    return row["change"]["pick"]["who"] if row["state"] == "change" else row["pick"]["who"]

def today_row(c, i, ckey, date="2026-10-13"):
    return next(r for r in ok(c.get(f"/api/relief/today?date={date}"))["rows"] if (r["id"], r["ckey"]) == (i, ckey))

RUTH7 = f"Relief for {RUTH} on Tue 13 Oct: {FLEX} approved for 3B Physics P7 on Tue 13 Oct"

@rt
def approve_is_refused_when_the_pick_changed_since_the_page_read_it():
    fresh()
    team = staff(TEAMER)
    i = absent(by=GRACE, lessons=[dict(key=K5, relief=SAM)])["id"]           # P6-P7 waiting for Mr Sam Tan
    seen = today_row(team, i, K5)
    assert (seen["state"], who_shown(seen)) == ("waiting", SAM), seen
    absent(teacher=SAM)                                                       # then he asks for relief himself: a run drops him and picks again
    FL.run(date=D13, call=first, now=mon("09:00"))
    new = relief_of(i, K5)
    assert st(i, K5) == "waiting" and new not in (None, SAM), new
    before, n = snap(), len(notes())
    no(team.post(cover_url(i, K5, "approve"), json=dict(who=SAM)), 400, CV.PICK_CHANGED)
    for bad in ({}, dict(who=None), dict(who=""), dict(who=[new])):            # a request without the name it showed
        no(team.post(cover_url(i, K5, "approve"), json=bad), 400, CV.PICK_CHANGED)
    no(team.post(cover_url(i, K5, "approve")), 400, CV.PICK_CHANGED)
    assert snap() == before and len(notes()) == n and st(i, K5) == "waiting", "nothing approved, nothing noted"
    refuses(CV.PICK_CHANGED, lambda: CV.approve(i, K5, SAM, TEAMER, PUB, ST))
    refuses(CV.PICK_CHANGED, lambda: CV.approve(i, K5, None, TEAMER, PUB, ST))
    # read again: the new pick is shown, approved and named
    assert who_shown(today_row(team, i, K5)) == new
    ok(team.post(cover_url(i, K5, "approve"), json=dict(who=new)))
    assert st(i, K5) == "approved" and relief_of(i, K5) == new
    assert notes()[n:] == [("approved", TEAMER, HEAD + f"{new} approved for 1A Science P6–P7 on Tue 13 Oct")], notes()[n:]

@rt
def approve_the_new_pick_is_refused_when_it_changed_since_the_page_read_it():
    fresh()
    team = staff(TEAMER)
    i = absent(by=GRACE)["id"]
    CV.change(i, K5, SAM, TEAMER, PUB, ST); CV.ask_change(i, K5, "A meeting", SAM)
    CV.set_pick(i, K5, pk(MAYA), PUB, ST, into="change")
    seen = today_row(team, i, K5)
    assert (seen["state"], who_shown(seen)) == ("change", MAYA), seen
    CV.drop(i, K5, nf(MAYA), who=MAYA, into="change"); CV.set_pick(i, K5, pk(FLEX), PUB, ST, into="change")   # a run picks again meanwhile
    before, n = snap(), len(notes())
    no(team.post(cover_url(i, K5, "approve"), json=dict(who=MAYA)), 400, CV.PICK_CHANGED)
    no(team.post(cover_url(i, K5, "approve"), json={}), 400, CV.PICK_CHANGED)
    refuses(CV.PICK_CHANGED, lambda: CV.approve(i, K5, SAM, TEAMER, PUB, ST))          # the teacher who asked is not the new pick
    assert snap() == before and len(notes()) == n
    r, x, c = cov(i, K5)
    assert CV.state(r, x, c) == "change" and c["relief"] == SAM and CV.new_pick(c)["who"] == FLEX
    CV.drop(i, K5, nf(FLEX), who=FLEX, into="change")                                   # dropped, not picked again yet: the same sentence
    no(team.post(cover_url(i, K5, "approve"), json=dict(who=FLEX)), 400, CV.PICK_CHANGED)
    CV.set_pick(i, K5, pk(FLEX), PUB, ST, into="change")
    ok(team.post(cover_url(i, K5, "approve"), json=dict(who=FLEX)))
    assert st(i, K5) == "approved" and relief_of(i, K5) == FLEX
    assert notes()[n:] == [("approved", TEAMER, HEAD + f"{FLEX} approved for 1A Science P6–P7 on Tue 13 Oct")], notes()[n:]

@rt
def approve_all_approves_only_the_picks_the_page_showed():
    fresh()
    team, tab2 = staff(TEAMER), staff(TEAMER)
    i = absent(by=GRACE, lessons=[dict(key=K5, relief=SAM)])["id"]                  # P3-P5 open, P6-P7 waiting for Mr Sam Tan
    j = absent(teacher=RUTH, by=GRACE, lessons=[dict(key=KR6, relief=FLEX)])["id"]  # P7 waiting for Mr Flex Ng
    rows = ok(team.get("/api/relief/today?date=2026-10-13"))["rows"]
    shown = [dict(id=r["id"], ckey=r["ckey"], who=who_shown(r)) for r in rows if r["state"] == "waiting"]
    assert shown == [dict(id=i, ckey=K5, who=SAM), dict(id=j, ckey=KR6, who=FLEX)], shown
    absent(teacher=SAM)                                                              # then a run drops Mr Sam Tan, picks again, and picks P3-P5
    FL.run(date=D13, call=first, now=mon("09:00"))
    assert (st(i, K5), st(i, K2)) == ("waiting", "waiting") and relief_of(i, K5) not in (None, SAM)
    n = len(notes())
    got = ok(team.post("/api/relief/today/approve-all", json=dict(date="2026-10-13", covers=shown)))
    assert got == dict(approved=1, skipped=[dict(id=i, ckey=K5, name=SAM, why=CV.PICK_CHANGED)]), got
    assert (st(j, KR6), st(i, K5), st(i, K2)) == ("approved", "waiting", "waiting"), "a pick the page never showed is not approved"
    assert notes()[n:] == [("approved", TEAMER, RUTH7)], notes()[n:]
    # pressed again (a second tab, or a double click): nothing more is approved and no entry is written again
    got = ok(tab2.post("/api/relief/today/approve-all", json=dict(date="2026-10-13", covers=shown)))
    assert got == dict(approved=0, skipped=[dict(id=i, ckey=K5, name=SAM, why=CV.PICK_CHANGED), dict(id=j, ckey=KR6, name=FLEX, why=CV.NOT_WAITING)]), got
    assert len(notes()) == n + 1
    # a row whose name is missing is skipped, the rest approved
    k = relief_of(i, K5)
    got = ok(team.post("/api/relief/today/approve-all", json=dict(date="2026-10-13", covers=[dict(id=i, ckey=K5), dict(id=i, ckey=K2, who=relief_of(i, K2))])))
    assert got == dict(approved=1, skipped=[dict(id=i, ckey=K5, name=None, why=CV.PICK_CHANGED)]) and st(i, K2) == "approved" and st(i, K5) == "waiting", got
    assert relief_of(i, K5) == k

@rt
def approve_all_notes_exactly_the_covers_it_approved():
    real = CV.approve_all
    def setup():
        fresh()
        i = absent(by=GRACE, lessons=[dict(key=K5, relief=SAM)])["id"]
        j = absent(teacher=RUTH, by=GRACE, lessons=[dict(key=KR6, relief=FLEX)])["id"]
        return i, j, [dict(id=i, ckey=K5, who=SAM), dict(id=j, ckey=KR6, who=FLEX)]
    def press(c, shown, meanwhile):
        def hooked(*a, **kw):                   # what happens after the request arrives and before the approvals take the lock
            CV.approve_all = real
            meanwhile()
            return real(*a, **kw)
        CV.approve_all = hooked
        try: return ok(c.post("/api/relief/today/approve-all", json=dict(date="2026-10-13", covers=shown)))
        finally: CV.approve_all = real
    team, tab2 = staff(TEAMER), staff(TEAMER)
    # a background run saves a pick for the open P3-P5 meanwhile: it is not approved, and no entry names it
    i, j, shown = setup()
    n = len(notes())
    got = press(team, shown, lambda: CV.set_pick(i, K2, pk(MAYA), PUB, ST))
    assert got == dict(approved=2, skipped=[]), got
    assert (st(i, K5), st(j, KR6), st(i, K2)) == ("approved", "approved", "waiting"), "the pick saved meanwhile is not approved"
    assert notes()[n:] == [("approved", TEAMER, HEAD + f"{SAM} approved for 1A Science P6–P7 on Tue 13 Oct"), ("approved", TEAMER, RUTH7)], notes()[n:]
    # two presses at once (two tabs): the second gets there first; each cover has one entry
    i, j, shown = setup()
    n = len(notes())
    got = press(team, shown, lambda: ok(tab2.post("/api/relief/today/approve-all", json=dict(date="2026-10-13", covers=shown))))
    assert got == dict(approved=0, skipped=[dict(id=i, ckey=K5, name=SAM, why=CV.NOT_WAITING), dict(id=j, ckey=KR6, name=FLEX, why=CV.NOT_WAITING)]), got
    assert notes()[n:] == [("approved", TEAMER, HEAD + f"{SAM} approved for 1A Science P6–P7 on Tue 13 Oct"), ("approved", TEAMER, RUTH7)], notes()[n:]

@rt
def the_planned_sheet_names_only_an_approved_relief():
    fresh()
    grace = staff(GRACE)
    i = absent(by=GRACE, lessons=[dict(key=K5, relief=SAM)])["id"]           # the planner's own choice, waiting
    CV.set_pick(i, K2, pk(FLEX), PUB, ST)                                     # the AI's pick, waiting
    j = absent(teacher=RUTH)["id"]                                            # nothing picked yet
    def sheet():
        text = grace.get("/api/relief/planned.csv?start=2026-10-13").data.decode("utf-8")
        return text, [(r[1], r[3], r[5]) for r in csv.reader(io.StringIO(text.lstrip("\ufeff")))][1:]
    W, N = "Waiting for the relief team", "Not chosen yet"
    text, rows = sheet()
    assert rows == [(EVE, "P3–P5", W), (RUTH, "P3", N), (EVE, "P6–P7", W), (RUTH, "P7", N)], rows
    assert SAM not in text and FLEX not in text, "no name before the relief team approves it"
    CV.approve(i, K5, SAM, TEAMER, PUB, ST); CV.approve(i, K2, FLEX, TEAMER, PUB, ST); CV.change(j, KR6, MAYA, TEAMER, PUB, ST)
    CV.acknowledge(i, K2, FLEX); CV.ask_change(i, K5, "A meeting", SAM); CV.set_pick(i, K5, pk(TEAMER), PUB, ST, into="change")
    text, rows = sheet()
    assert rows == [(EVE, "P3–P5", FLEX), (RUTH, "P3", N), (EVE, "P6–P7", SAM), (RUTH, "P7", MAYA)], rows
    assert TEAMER not in text, "a request to change's new pick is not approved either"

@t
def keep_and_change_write_down_the_pick_they_drop():
    fresh()
    i = absent(by=GRACE)["id"]
    CV.change(i, K5, SAM, TEAMER, PUB, ST)                                    # open: nothing is dropped
    assert whats(cov(i, K5)[2]) == [("pick", SAM, "team"), ("changed", SAM, TEAMER)]
    CV.ask_change(i, K5, "A meeting", SAM); CV.set_pick(i, K5, pk(FLEX), PUB, ST, into="change")
    CV.change(i, K5, MAYA, GRACE, PUB, ST)                                    # the teacher who asked and the new pick both end
    c = cov(i, K5)[2]
    assert whats(c)[-4:] == [("dropped", SAM, GRACE), ("dropped", FLEX, GRACE), ("pick", MAYA, "team"), ("changed", MAYA, GRACE)], whats(c)
    assert c["history"][-4] == dict(what="dropped", who=SAM, by=GRACE, at=NOW, why=None)
    CV.ask_change(i, K5, "Not today", MAYA); CV.set_pick(i, K5, pk(FLEX), PUB, ST, into="change")
    CV.change(i, K5, FLEX, TEAMER, PUB, ST)                                   # given to the new pick itself: only the teacher who asked ends
    assert whats(cov(i, K5)[2])[-3:] == [("dropped", MAYA, TEAMER), ("pick", FLEX, "team"), ("changed", FLEX, TEAMER)], whats(cov(i, K5)[2])
    CV.set_pick(i, K2, pk(SAM), PUB, ST)                                      # a waiting pick changed
    CV.change(i, K2, MAYA, TEAMER, PUB, ST)
    assert whats(cov(i, K2)[2]) == [("pick", SAM, "ai"), ("dropped", SAM, TEAMER), ("pick", MAYA, "team"), ("changed", MAYA, TEAMER)], whats(cov(i, K2)[2])
    CV.change(i, K2, MAYA, TEAMER, PUB, ST)                                   # the same person again is not a drop
    assert [w for w, _, _ in whats(cov(i, K2)[2])] == ["pick", "dropped", "pick", "changed", "pick", "changed"]
    CV.ask_change(i, K2, "A meeting", MAYA); CV.set_pick(i, K2, pk(SAM), PUB, ST, into="change")
    same(CV.keep(i, K2, GRACE), i)                                            # Keep: the request's new pick ends
    assert whats(cov(i, K2)[2])[-3:] == [("pick", SAM, "ai"), ("dropped", SAM, GRACE), ("kept", MAYA, GRACE)], whats(cov(i, K2)[2])
    CV.ask_change(i, K2, "Again", MAYA)                                       # no new pick yet: Keep drops nothing
    CV.keep(i, K2, GRACE)
    assert whats(cov(i, K2)[2])[-2:] == [("asked to change", MAYA, MAYA), ("kept", MAYA, GRACE)], whats(cov(i, K2)[2])

@rt
def a_request_to_change_runs_the_picks_of_its_own_absence_alone():
    fresh()
    sam = staff(SAM)
    i = absent(by=GRACE, lessons=[dict(key=K5, relief=SAM)])["id"]
    CV.approve(i, K5, SAM, TEAMER, PUB, ST)
    k = absent(teacher=RUTH)["id"]                                            # another absence, its lessons open
    calls, real = [], FL.soon
    def spy(*a, **kw):
        calls.append((a, kw)); return real(*a, **kw)
    FL.soon, PK.CALL = spy, first
    try:
        with at("2026-10-12T15:30:00+08:00"):                                # past the fill time: Tuesday's picks are all due
            ok(sam.post(cover_url(i, K5, "ask-change"), json=dict(why="A meeting")))
    finally: FL.soon = real
    assert calls == [((), dict(ids=[i], force=True))], calls
    assert CV.new_pick(cov(i, K5)[2]) and (st(k, KR2), st(k, KR6)) == ("open", "open"), "only this absence is run"

# ---- Send-out, Task 2: picked at once, nearest first ----
import contextlib  # noqa: E402

@contextlib.contextmanager
def stand_in(module, name, f):
    old = getattr(module, name); setattr(module, name, f)
    try: yield
    finally: setattr(module, name, old)

@ft
def every_open_lesson_is_picked_at_once_whatever_its_date():
    fresh()
    a = absent(dates=("2026-10-16",))["id"]; b = absent(teacher=RUTH, dates=("2026-10-13",))["id"]
    got = FL.run(now=mon("09:00"), call=first)
    assert got == dict(picked=3, nobody=0) and st(a, KF) == "waiting" and st(b, KR6) == "waiting", "Friday too, on Monday at 09:00"

@ft
def a_full_guard_leaves_the_rest_open_for_the_next_run():
    fresh()
    far = absent(dates=("2026-10-16",))["id"]; near = absent(teacher=RUTH, dates=("2026-10-13",))["id"]
    with stand_in(PK, "GUARD_N", 1):
        PK._seen.clear(); got = FL.run(now=mon("09:00"), call=first)
        assert got == dict(picked=1, nobody=0, held=2) and st(near, KR2) == "waiting" and st(far, KF) == "open", "the nearest first; not the app's order"
        assert [h["by"] for h in cov(near, KR2)[2]["history"]] == ["ai"]
        PK._seen.clear(); FL.run(now=mon("09:01"), call=first); assert st(near, KR6) == "waiting" and st(far, KF) == "open"
        PK._seen.clear(); FL.run(now=mon("09:02"), call=first); assert st(far, KF) == "waiting"
    PK._seen.clear()
    with stand_in(PK, "CALL", None), stand_in(PK.typed, "enabled", lambda: False): fresh(); i = absent()["id"]; assert FL.run(now=mon("09:00"))["picked"] == 2 and cov(i, K2)[2]["pick"]["by"] == "app", "no model: the app's order, as today"

# ---- Send-out, Task 2 fix round 1: a lesson of today never waits for the guard ----
@ft
def a_lesson_of_today_never_waits_for_a_full_guard():
    fresh()
    i = absent(dates=("2026-10-13", "2026-10-16"))["id"]
    with at("2026-10-13T08:00:00+08:00"), stand_in(PK, "GUARD_N", 0):
        got = FL.run(call=first)
        assert got == dict(picked=2, nobody=0, held=1), got
        assert (st(i, K2), st(i, K5), st(i, KF)) == ("waiting", "waiting", "open")
        assert cov(i, K2)[2]["pick"]["by"] == "app" and cov(i, K5)[2]["pick"]["by"] == "app", "today: the app's own order at once"
        assert cov(i, K2)[2]["pick"]["reason"] == PK.APP_ORDER
    with at("2026-10-13T08:01:00+08:00"):
        PK._seen.clear(); assert FL.run(call=first) == dict(picked=1, nobody=0) and cov(i, KF)[2]["pick"]["by"] == "ai", "the later date: the next run, the model's"
    fresh(); PK._seen.clear()
    i = absent(dates=("2026-10-13",))["id"]
    with at("2026-10-13T08:00:00+08:00"):
        assert FL.run(call=first) == dict(picked=2, nobody=0) and cov(i, K2)[2]["pick"]["by"] == "ai", "guard not full: today is the model's pick"

@ft
def a_request_to_change_for_today_is_picked_at_once_by_a_full_guard():
    fresh()
    i = absent(by=GRACE, dates=("2026-10-13",))["id"]
    CV.change(i, K5, SAM, TEAMER, PUB, ST); CV.ask_change(i, K5, "A meeting", SAM)
    with at("2026-10-13T08:00:00+08:00"), stand_in(PK, "GUARD_N", 0):
        assert FL.run(call=first) == dict(picked=2, nobody=0)
        c = cov(i, K5)[2]
        assert c["change"]["pick"]["by"] == "app" and c["change"]["pick"]["who"] != SAM, c["change"]

@ft
def a_stale_pick_dropped_under_a_full_guard_waits_or_not_by_its_date():
    fresh()
    i = absent(by=GRACE, dates=("2026-10-13",), lessons=[dict(key=K5, relief=SAM)])["id"]
    absent(teacher=SAM, dates=("2026-10-13",))
    with at("2026-10-13T08:00:00+08:00"), stand_in(PK, "GUARD_N", 0):
        FL.run(call=first)
        assert st(i, K5) == "waiting" and relief_of(i, K5) != SAM and cov(i, K5)[2]["history"][-1]["by"] == "app", "today: dropped and picked by the app's order in the same run"
        assert [h["what"] for h in cov(i, K5)[2]["history"]][:2] == ["pick", "dropped"]
    fresh(); PK._seen.clear()
    i = absent(by=GRACE, dates=("2026-10-16",), lessons=[dict(key=KF, relief=SAM)])["id"]
    with at("2026-10-13T08:00:00+08:00"), stand_in(PK, "GUARD_N", 0), saved_settings(limits=dict(never=[SAM])):          # Mr Sam Tan is no longer to be asked
        FL.run(call=first)
        assert st(i, KF) == "open" and [h["what"] for h in cov(i, KF)[2]["history"]] == ["pick", "dropped"], "later date: dropped, held open, no app pick"
    with at("2026-10-13T08:01:00+08:00"):
        PK._seen.clear(); FL.run(call=first); assert st(i, KF) == "waiting" and cov(i, KF)[2]["pick"]["by"] == "ai"

assert REAL == [], "a test reached the real call"

print(f"{COUNT} relief team tests passed")

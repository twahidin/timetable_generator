"""Plain-assert tests for what approved exams and events mean for relief: .venv/bin/python tests/test_exams_relief.py"""
import os, secrets, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = tempfile.mkdtemp()
os.environ.pop("HEADS_CODE", None)
os.environ.update(DATA_DIR=DATA, SECRET_KEY=secrets.token_hex(16), AI_PROVIDER="anthropic", AI_API_KEY="",
                  COMMITTEE_CODE=secrets.token_hex(4), TEACHER_CODE=secrets.token_hex(4), STUDENT_CODE=secrets.token_hex(4))
sys.path.insert(0, ROOT)
import app as A, store  # noqa: E402
from exams import fake as F, days as D, schedules as SC, approval as AP  # noqa: E402
from exams import relief_links as RL  # noqa: E402
from relief import lessons as LS  # noqa: E402
from datetime import date  # noqa: E402

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

CAL = dict(terms=[dict(name="Term 1", start="2027-01-04", end="2027-03-12", starts_as="Odd")], holidays=[])
MON = date(2027, 1, 4)          # Odd Mon
ISO = MON.isoformat()
PUB = F.sample_pub()
M = PUB["model"]
EXAM, EVENT = "Sec 3 End-of-Year Exam", "Sec 4 Learning Journey"
AISHA, BEN = "Ms Aisha Rahman", "Mr Ben Ong"

def _approve(s, status="approved"):
    s["status"] = status
    s["approved"] = AP.public(s) if status == "approved" else None
    return SC.save(s, PUB, CAL, "x", check=False)

def _exam(status="approved", duty_names=(AISHA,)):
    e = SC.new("exam", EXAM, ["Sec 3"], ISO, ISO, "Ms Grace Yeo", pub=PUB)
    e["days"] = {ISO: dict(levels=["Sec 3"], whole=True)}
    e["made"] = dict(seats=[], unseated=[], published_at=None,
                     duties=[dict(date=ISO, start=460, end=550, room="3-01", names=list(duty_names))])
    return _approve(e, status)

def _event(status="approved"):
    e = SC.new_event(EVENT, ["Sec 4"], [], ISO, ISO, "Ms Grace Yeo", "Ms Grace Yeo")
    e["days"] = {ISO: dict(levels=["Sec 4"], whole=False, **{"from": "07:40", "to": "09:00"})}
    e["going"] = [BEN]
    return _approve(e, status)

def _clear():
    for s in SC.all_saved(): SC.delete(s["id"])

def _links():
    return RL.Links(PUB, CAL, SC.on_site())

def _lesson(row, d=MON):
    L = M["lessons"][row]
    return dict(key=RL.key_of(M, row, d, "Odd Mon"), date=d, classes=L["classes"])

@t
def key_matches_relief():
    got = LS.on_date(PUB, CAL, AISHA, MON)[0]
    assert RL.key_of(M, 0, MON, "Odd Mon") == got["key"] == RL.key_of(M, 0, ISO, "Odd Mon")

@t
def links_stopped_names_the_schedule():
    _clear(); _exam(); _event()
    L = _links()
    assert L.stopped(_lesson(0)) == "3A is on " + EXAM
    assert L.stopped(_lesson(0)) == "3A is on " + EXAM
    assert L.stopped(dict(_lesson(0), date=ISO)) == "3A is on " + EXAM
    assert L.stopped(_lesson(3)) == "3A, 3B are on " + EXAM
    assert L.stopped(_lesson(8)) == "", "a mixed lesson with a Sec 4 class still runs"

@t
def links_event_window_stops_only_inside():
    _clear(); _event()
    L = _links()
    assert L.stopped(_lesson(2)) == "4A is on " + EVENT, "period 1-2 (07:40..08:20) inside 07:40-09:00"
    assert L.stopped(_lesson(6)) == "", "period 9 is outside the event window"

@t
def links_shortened_lesson_still_happens():
    _clear(); _event()
    M["lessons"][2]["n"] = 8        # 07:40+20..: periods 1..8 run past 09:00
    try:
        assert _links().stopped(_lesson(2)) == ""
    finally:
        M["lessons"][2]["n"] = 2

@t
def links_busy_and_duties():
    _clear(); _exam(); _event()
    L = _links()
    assert L.busy(AISHA, MON, 0, 1) == "Invigilating: " + EXAM
    assert L.busy(AISHA, ISO, 3, 2) == "Invigilating: " + EXAM
    assert L.busy(AISHA, MON, 8, 1) == ""
    assert L.busy(BEN, MON, 0, 1) == "At event: " + EVENT
    assert L.busy(BEN, MON, 10, 1) == ""
    assert L.busy("Mr Nobody", MON, 0, 1) == ""
    d = L.duties(AISHA, MON)
    assert d == [dict(start="07:40", end="09:10", what="Invigilating: %s · 3-01" % EXAM, replaces="the exams committee")], d
    d = L.duties(BEN, MON)
    assert d[0]["start"] == "07:40" and d[0]["end"] == "09:00" and d[0]["what"] == "At event: " + EVENT
    assert d[0]["replaces"] == "Ms Grace Yeo, the teacher in charge"
    assert L.duties(AISHA, MON, periods=(10, 12)) == []
    assert len(L.duties(AISHA, MON, periods=(0, 0))) == 1

@t
def links_only_approved():
    _clear(); _exam("waiting"); _event("waiting")
    L = _links()
    assert L.stopped(_lesson(0)) == "" and L.busy(AISHA, MON, 0, 1) == "" and L.busy(BEN, MON, 0, 1) == ""
    assert L.duties(AISHA, MON) == [] and L.week_change(AISHA, [MON]) == 0

@t
def links_week_change():
    _clear(); _exam(duty_names=(BEN,))
    L = _links()
    # Ben: duty 07:40-09:10 touches periods 0..4 (5); his only lesson is period 6..8 (Sec 3, stops: -3)
    assert L.week_change(BEN, [MON]) == 5 - 3
    # Grace teaches 3A+3B period 6..8 (stops, -3) and 4A at period 9..10 (runs)
    assert L.week_change("Ms Grace Yeo", [MON]) == -3 + 0
    assert L.week_change("Mr Nobody", [MON]) == 0
    _clear(); _exam(duty_names=("Mr Daniel Koh",))
    L = _links()
    # Daniel: duty periods 0..4; his 4A lesson at periods 1-2 runs: only periods 0, 3 and 4 are added
    assert L.week_change("Mr Daniel Koh", [MON]) == 3
    _clear(); _exam(duty_names=(AISHA,))
    assert _links().week_change(AISHA, [MON]) == 5 - 2, "her 3A lesson at 0..1 stops (-2); duty periods 0..4 (+5)"

@t
def links_week_change_duty_where_nothing_is_taught():
    _clear(); e = _exam(duty_names=("Mr Ivan Lee",))
    e["made"]["duties"][0].update(start=480, end=520)
    _approve(e)
    assert _links().week_change("Mr Ivan Lee", [MON]) == 2

@t
def links_never_raise():
    _clear(); _exam(); _event()
    L = _links()
    sat = date(2027, 1, 9)
    assert L.stopped(dict(_lesson(0), date=sat)) == "" and L.busy(AISHA, sat, 0, 1) == ""
    assert L.duties(AISHA, sat) == [] and L.week_change(AISHA, [sat]) == 0
    blank = RL.Links(PUB, dict(terms=[], holidays=[]), SC.on_site())
    assert blank.stopped(_lesson(0)) == "" and blank.busy(AISHA, MON, 0, 1) == "" and blank.duties(AISHA, MON) == []
    assert blank.week_change(AISHA, [MON]) == 0
    nop = dict(PUB, model=dict(M, NP=0, times=[], school={}))
    q = RL.Links(nop, CAL, SC.on_site())
    assert q.stopped(_lesson(0)) == "" and q.busy(AISHA, MON, 0, 1) == "" and q.duties(AISHA, MON) == [] and q.week_change(AISHA, [MON]) == 0
    n = RL.Links.load(None, CAL)
    assert n.stopped(_lesson(0)) == "" and n.busy(AISHA, MON, 0, 1) == "" and n.duties(AISHA, MON) == [] and n.week_change(AISHA, [MON]) == 0
    assert RL.Links.load(PUB, CAL).busy(AISHA, MON, 0, 1) == "Invigilating: " + EXAM

@t
def links_two_schedules_one_day():
    _clear(); _exam(); _event()
    PUB["model"]["lessons"].append(F._lesson(10, 0, 2, 1, "Sec 4", ["4A"], "Maths", "Entire Class", [AISHA], "4-01"))
    try:
        L = _links()
        lesson = dict(key=RL.key_of(M, 10, MON, "Odd Mon"), date=MON, classes=["4A"])
        assert L.busy(AISHA, MON, 2, 1) == "Invigilating: " + EXAM
        assert L.stopped(lesson) == "4A is on " + EVENT, "the lesson does not run: the event holds 4A"
        both = dict(key=RL.key_of(M, 3, MON, "Odd Mon"), date=MON, classes=["3A", "3B"])
        assert L.stopped(both) == "3A, 3B are on " + EXAM
    finally:
        PUB["model"]["lessons"].pop()

# ---- Task 2: relief's free list and week count know exams and events
import contextlib, json, urllib.parse  # noqa: E402
import access  # noqa: E402
from relief import free as FR, settings as RS  # noqa: E402
from relief.calendar import school_day  # noqa: E402

DANIEL, GRACE = "Mr Daniel Koh", "Ms Grace Yeo"
os.makedirs(os.path.dirname(RS.PATH), exist_ok=True)
store.write_json(RS.PATH, dict(calendar=CAL, team=[], management=[GRACE], limits=dict(fat_per_day=3, other_per_day=None, never=[]), fat_role=""))
SETTINGS = dict(fat_role="", limits=dict(fat_per_day=3, other_per_day=None, never=[]), calendar=CAL, extra_staff=[])

def _need(p, n=1, absent=DANIEL):
    """a 4A lesson of the absent teacher at periods p.., as relief.lessons.on_date gives it"""
    return dict(date=MON, day="Odd Mon", p=p, n=n, subject="Mathematics", classes=["4A"], key="k%d" % p)

def _free_names(got):
    return [x["name"] for g in got["groups"] for x in g["people"]]

@t
def free_then_leaves_out_the_invigilator():
    _clear(); _exam()
    L = _links()
    got = FR.free_then(PUB, SETTINGS, [], _need(3), DANIEL, links=L)
    assert AISHA not in _free_names(got), got
    assert dict(name=AISHA, why="Invigilating: " + EXAM) in got["busy"], got["busy"]
    assert AISHA not in got["teaching"]
    plain = FR.free_then(PUB, SETTINGS, [], _need(3), DANIEL)
    assert AISHA in _free_names(plain) and plain["busy"] == [], plain

@t
def free_then_offers_a_freed_teacher():
    _clear(); _exam()
    BEN_LESSON = _need(6)
    plain = FR.free_then(PUB, SETTINGS, [], BEN_LESSON, DANIEL)
    assert BEN in plain["teaching"] and BEN not in _free_names(plain), plain
    got = FR.free_then(PUB, SETTINGS, [], BEN_LESSON, DANIEL, links=_links())
    assert BEN in _free_names(got) and BEN not in got["teaching"], got
    assert all(x["name"] != BEN for x in got["busy"])

@t
def week_so_far_counts_duties():
    _clear(); _exam(duty_names=(BEN,))
    L = _links()
    week = FR._week_dates(CAL, M["days"], MON)
    base = FR.week_so_far(PUB, CAL, [], BEN, MON)
    with_links = FR.week_so_far(PUB, CAL, [], BEN, MON, links=L)
    assert with_links - base == L.week_change(BEN, week) == 5 - 3, (with_links, base)
    assert FR.week_so_far(PUB, CAL, [], BEN, MON, links=None) == base

@t
def there_then_leaves_out_someone_on_duty():
    _clear(); _exam()
    L = _links()
    assert FR.there_then([], [AISHA, BEN], MON, 0, 1) == [AISHA, BEN]
    assert FR.there_then([], [AISHA, BEN], MON, 0, 1, links=L) == [BEN]
    assert FR.there_then([], [AISHA, BEN], ISO, 9, 1, links=L) == [AISHA, BEN]

@contextlib.contextmanager
def published(pub):
    old = store.published; store.published = lambda: pub
    try: yield
    finally: store.published = old

def staff(name):
    c = A.app.test_client()
    r = c.post("/login", data={"as": "relief", "code": access.staff_code(name)})
    assert r.status_code == 302, (name, r.status_code)
    return c

@t
def free_route_uses_links():
    _clear(); _exam()
    old = LS.today
    key = RL.key_of(M, 2, MON, "Odd Mon")
    try:
        with published(PUB):
            c = staff(GRACE)
            r = c.get("/api/relief/free?absent=%s&key=%s" % (urllib.parse.quote(DANIEL), urllib.parse.quote(key)))
            assert r.status_code == 200, r.get_data(as_text=True)[:300]
            j = r.get_json()
            assert dict(name=AISHA, why="Invigilating: " + EXAM) in j["busy"], j
            assert AISHA not in _free_names(j)
            _clear()
            j = c.get("/api/relief/free?absent=%s&key=%s" % (urllib.parse.quote(DANIEL), urllib.parse.quote(key))).get_json()
            assert j["busy"] == [], j
    finally:
        LS.today = old

@t
def relief_plan_page_shows_the_busy_fold():
    js = open(os.path.join(ROOT, "static", "relief-plan.js"), encoding="utf-8").read()
    assert "on an exam duty or at an event then" in js

_clear()
print(f"{COUNT} exams and relief tests passed")

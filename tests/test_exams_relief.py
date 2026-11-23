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
LS.today = A._exams_today = lambda: date(2026, 12, 1)       # the dates here are made up: the real clock never reaches them
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
from accounts import people as ACC  # noqa: E402    (AP is exams.approval here)

DANIEL, GRACE = "Mr Daniel Koh", "Ms Grace Yeo"
os.makedirs(os.path.dirname(RS.PATH), exist_ok=True)
store.write_json(RS.PATH, dict(calendar=CAL, limits=dict(fat_per_day=3, other_per_day=None, never=[]), fat_role=""))
# management comes from the accounts (as tests/test_relief_requests.py): Grace a school leader, who plans relief (relief.plan)
ACC.update(lambda d: d["people"].update({GRACE: dict(group="leader")}))
SETTINGS = dict(fat_role="", limits=dict(fat_per_day=3, other_per_day=None, never=[]), calendar=CAL)

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
    """a person signed in by name with their own code, on the accounts' one sign-in page"""
    c = A.app.test_client()
    r = c.post("/login", data={"code": access.staff_code(name)})
    assert r.status_code == 302, (name, r.status_code)
    with c.session_transaction() as s: assert s["who"] == name and s["via"] == "code", dict(s)
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

# ---- Task 3: asking for and planning relief on an exam or event day
from relief import absences as AB  # noqa: E402

def _ask(teacher, lessons=None, **kw):
    return dict(teacher=teacher, dates=[ISO], reason="Medical", reporting_officer=GRACE, lessons=lessons or [], **kw)

def _q(c, teacher, path="lessons"):
    return c.get("/api/relief/%s?teacher=%s&dates=%s" % (path, urllib.parse.quote(teacher), ISO))

@t
def lessons_route_marks_not_happening():
    _clear(); _exam()
    with published(PUB):
        j = _q(staff(GRACE), AISHA).get_json()
    by = {x["classes"][0]: x for x in j["lessons"]}
    assert by["3A"]["stopped"] == "3A is on " + EXAM, j["lessons"]
    assert all(x["stopped"] == "" for x in j["lessons"] if x["classes"] == ["4A"])
    assert j["duties"][ISO] == [dict(start="07:40", end="09:10", what="Invigilating: %s · 3-01" % EXAM, replaces="the exams committee")], j["duties"]
    _clear()
    with published(PUB):
        j = _q(staff(GRACE), AISHA).get_json()
    assert all(x["stopped"] == "" for x in j["lessons"]) and j["duties"][ISO] == []

@t
def new_absence_marks_stopped_lessons():
    _clear(); _exam()
    with published(PUB):
        mine = LS.on_date(PUB, CAL, AISHA, MON)
        stopped = [x for x in mine if "3A" in x["classes"]]
        assert stopped
        asks = [dict(key=x["key"], needed=True) for x in mine]
        r = AB.new(_ask(AISHA, asks), PUB, GRACE, "planned", may_choose=True, links=_links())
        for x in r["lessons"]:
            if x["key"] in {y["key"] for y in stopped}:
                assert x["needed"] is True and x["not_needed"] is None, "the stop is worked out, never written: %s" % x
        AB.cancel(r["id"], "test", GRACE, team=True)

@t
def duty_only_absence_is_accepted():
    _clear(); _exam()
    old = LS.today
    with published(PUB):
        c = staff(GRACE)
        mine = LS.on_date(PUB, CAL, AISHA, MON)
        body = _ask(AISHA, [dict(key=x["key"], needed=False) for x in mine])
        r = c.post("/api/relief/absences", json=body)
        assert r.status_code == 200, r.get_data(as_text=True)[:300]
        AB.cancel(r.get_json()["id"], "test", GRACE, team=True)
        _clear()
        r = c.post("/api/relief/absences", json=body)
        assert r.status_code in (400, 409, 422) and r.get_json()["error"] == "There are no lessons to cover in that time.", r.get_data(as_text=True)[:300]

@t
def choosing_an_invigilator_is_refused():
    _clear()
    with published(PUB):
        c = staff(GRACE)
        mine = LS.on_date(PUB, CAL, DANIEL, MON)
        row = next(x for x in mine if x["p"] == 1)
        r = c.post("/api/relief/absences", json=_ask(DANIEL, [dict(key=x["key"], needed=True) for x in mine]))
        assert r.status_code == 200, r.get_data(as_text=True)[:300]
        rid = r.get_json()["id"]
        url = "/api/relief/absences/%s/lessons/%s/relief" % (rid, urllib.parse.quote(row["key"]))
        _exam(duty_names=(BEN,))
        r = c.put(url, json=dict(relief=BEN))
        err = r.get_json()["error"]
        assert r.status_code != 200 and err.startswith(BEN + " is not free for ") and err.endswith(" then."), (r.status_code, err)
        _clear()
        r = c.put(url, json=dict(relief=BEN))
        assert r.status_code == 200, r.get_data(as_text=True)[:300]
        AB.cancel(rid, "test", GRACE, team=True)

@t
def forms_say_not_happening():
    for f in ("relief.js", "relief-plan.js"):
        js = open(os.path.join(ROOT, "static", f), encoding="utf-8").read()
        assert "Not happening: " in js and "no relief needed" in js, f
    assert "replaces you" in open(os.path.join(ROOT, "static", "relief.js"), encoding="utf-8").read()
    assert "replaces them" in open(os.path.join(ROOT, "static", "relief-plan.js"), encoding="utf-8").read()

# ---- Task 4: exams see relief: someone away or covering relief is not free; away notices
from exams import invigilate as INV, settings as XS, review as RV, events as EV  # noqa: E402

def _rec(teacher, periods=None, dates=(ISO,), lessons=(), cancelled=None, **kw):
    return dict(id="rec-" + secrets.token_hex(4), teacher=teacher, dates=list(dates), periods=periods, cancelled=cancelled,
                lessons=list(lessons), **kw)

def _put(r):
    os.makedirs(AB.DIR, exist_ok=True)
    store.write_json(os.path.join(AB.DIR, r["id"] + ".json"), r)
    return r

def _drop(r):
    try: os.remove(os.path.join(AB.DIR, r["id"] + ".json"))
    except FileNotFoundError: pass

COVER = dict(date=ISO, p=0, n=1, classes=["1A"], subject="Art", needed=True, relief=BEN, approved=dict(by="x", at="x"))

@t
def relief_busies_shapes():
    away = _rec(DANIEL, periods=[1, 2])
    whole = _rec(AISHA)
    gone = _rec(GRACE, cancelled=dict(by="x"))
    backup = _rec(BEN, exams=dict(id="e", kind="exam"), lessons=[dict(COVER, relief=DANIEL, classes=["1A", "1B"])])
    unneeded = _rec(AISHA, cancelled=None, lessons=[dict(COVER, needed=False), dict(COVER, relief="")])
    got = RL.relief_busies(M, [away, whole, gone, backup, unneeded])
    bnds = D.bounds(M)
    for b in got:
        assert b["id"] == "relief" and b["kind"] == "relief" and b["name"] == "Relief" and b["status"] == "approved" and b["room"] == "", b
    mine = [(b["names"], b["start"], b["end"], b["why"]) for b in got]
    assert ([DANIEL], bnds[1][0], bnds[2][1], "is away then (relief)") in mine, mine
    assert ([AISHA], bnds[0][0], bnds[-1][1], "is away then (relief)") in mine, mine
    assert ([DANIEL], bnds[0][0], bnds[0][1], "covers relief then (1A, 1B Art)") in mine, mine
    assert not any(GRACE in b["names"] for b in got) and not any(BEN in b["names"] for b in got)
    assert len(got) == 4, mine

@t
def away_person_is_not_a_candidate():
    _clear()
    r = _put(_rec(AISHA, periods=[0, 4]))
    try:
        xset = XS.load(PUB)
        busy = SC.elsewhere("x", M)
        view = D.day_view(PUB, CAL, SC.new("exam", "T", ["Sec 3"], ISO, ISO, GRACE, pub=PUB), ISO)
        why, _ = INV._free(AISHA, view, 460, 550, [], xset, elsewhere=busy)
        assert why == "is away then (relief)", why
        s = SC.new("exam", "T", ["Sec 3"], ISO, ISO, GRACE, pub=PUB)
        got = INV.candidates(PUB, CAL, s, xset, ISO, 460, 550, [], elsewhere=busy)
        assert AISHA not in [c["name"] for g in got.values() for c in g], got
        got2 = INV.candidates(PUB, CAL, s, xset, ISO, 460, 550, [])
        assert AISHA in [c["name"] for g in got2.values() for c in g], "free without the relief busy"
    finally:
        _drop(r)

@t
def relief_cover_is_busy():
    _clear()
    r = _put(_rec(DANIEL, lessons=[COVER]))
    try:
        s = SC.new("exam", "T", ["Sec 3"], ISO, ISO, GRACE, pub=PUB)
        view = D.day_view(PUB, CAL, s, ISO)
        why, _ = INV._free(BEN, view, 460, 550, [], XS.load(PUB), elsewhere=SC.elsewhere("x", M))
        assert why == "covers relief then (1A Art)", why
    finally:
        _drop(r)

@t
def relief_busies_are_not_other_schedules():
    _clear()
    e = _exam(duty_names=(AISHA,))
    ev = _event()
    r = _put(_rec(AISHA, periods=[0, 4]))
    r2 = _put(_rec(BEN, lessons=[COVER]))
    try:
        xset = XS.load(PUB)
        busy = SC.elsewhere(e["id"], M)
        assert any(b.get("kind") == "relief" for b in busy)
        rv = RV.review(PUB, CAL, SC.load(e["id"]), xset, busy)
        other = next(c for c in rv["checks"] if c["key"] == "others")
        assert other["ok"] and "Relief" not in " ".join(other["lines"]), other
        busy = SC.elsewhere(ev["id"], M)
        lines = EV.other_lines(PUB, CAL, ev, busy, [])
        assert not any("Relief" in l for l in lines), lines
        assert EV.freed(PUB, CAL, ev, busy) == EV.freed(PUB, CAL, ev, [])
    finally:
        _drop(r); _drop(r2)

@t
def away_notice_on_an_approved_exam_and_event():
    _clear()
    e, ev = _exam(duty_names=(AISHA,)), _event()
    today = date(2026, 12, 1)
    recs = [_rec(AISHA, periods=[0, 1]), _rec(BEN)]
    got = RL.away_on(e, M, recs, today)
    assert got == [dict(name=AISHA, date=ISO, text="Away (from relief): %s on Mon 4 Jan, on duty in 3-01 07:40\u201309:10. "
                                                    "Replace them under Someone is away." % AISHA)], got
    got = RL.away_on(ev, M, recs, today)
    assert got == [dict(name=BEN, date=ISO, text="Away (from relief): %s on Mon 4 Jan, going with the event. "
                                                  "Replace them under Someone is away." % BEN)], got
    assert RL.away_on(e, M, [_rec(AISHA, cancelled=dict(by="x"))], today) == []
    assert RL.away_on(e, M, [_rec(AISHA, periods=[9, 10])], today) == [], "away outside the duty"
    assert RL.away_on(e, M, [_rec(AISHA, exams=dict(id="x", kind="exam"))], today) == []
    assert RL.away_on(e, M, recs, date(2027, 1, 5)) == [], "past date"
    assert RL.away_on(_exam("waiting"), M, recs, today) == [], "only approved"

@t
def lists_and_reviews_carry_away():
    _clear()
    e, ev = _exam(duty_names=(AISHA,)), _event()
    for sv in (e,):
        sv["made"]["duties"][0]["key"] = "k"; sv["approved"] = AP.public(sv); SC.save(sv, PUB, CAL, "x", check=False)
    r = _put(_rec(AISHA, periods=[0, 1], dates=[ISO]))
    r2 = _put(_rec(BEN))
    old, oldp = A._exams_today, store.published
    A._exams_today = lambda: date(2026, 12, 1)
    store.published = lambda: PUB
    try:
        with A.app.test_request_context():
            pass
        c = staff(GRACE)
        c.post("/login", data={"code": os.environ["COMMITTEE_CODE"]})
        j = c.get("/api/exams").get_json()
        row = next(x for x in j["schedules"] if x["id"] == e["id"])
        assert row["away"] and row["away"][0].startswith("Away (from relief): " + AISHA), row
        j = c.get("/api/events").get_json()
        row = next(x for x in j["schedules"] if x["id"] == ev["id"])
        assert row["away"] and "going with the event" in row["away"][0], row
        rr = c.get("/api/exams/%s/review" % e["id"]); assert rr.status_code == 200, (rr.status_code, rr.get_data(as_text=True)[:200])
        assert rr.get_json()["away"][0].startswith("Away (from relief)")
        assert "going with the event" in c.get("/api/events/%s/review" % ev["id"]).get_json()["away"][0]
    finally:
        A._exams_today, store.published = old, oldp
        _drop(r); _drop(r2)

@t
def exams_page_shows_away():
    js = open(os.path.join(ROOT, "static", "exams.js"), encoding="utf-8").read()
    assert "Away (from relief)" in js and ".away" in js

# ---- Task 5: backups go to relief when a schedule is approved
import copy, shutil  # noqa: E402
from exams import make as MK  # noqa: E402

CHLOE, HAFIZ = "Ms Chloe Tan", "Mr Hafiz Rahman"
store.write_json(RS.PATH, dict(calendar=CAL, limits=dict(fat_per_day=3, other_per_day=None, never=[]), fat_role=""))
# and now on the relief team too: the Relief team extra (relief.team, for What's in)
ACC.update(lambda d: d["people"][GRACE].update(extras=dict(relief=True, exams=None, admin=False)))
DKEY = RL.key_of(M, 2, MON, "Odd Mon")      # Daniel's 4A Mathematics, periods 2-3 (08:00-08:40): 4A is not on a Sec 3 exam
DUTY_KEY = ISO + " 07:50"
SOON = date(2026, 12, 1)

def _fresh():
    _clear()
    shutil.rmtree(AB.DIR, ignore_errors=True)

def _duty(names, start=460, end=550, room="3-01", key=DUTY_KEY):
    return dict(key=key, date=ISO, start=start, end=end, room=room, need=1, names=list(names), chief=None, reasons={}, backup={},
                not_free={}, short=0, locked=False)

def _made_exam(duties):
    """a Sec 3 exam on MON, made by hand (no papers) so that it can be sent"""
    e = SC.new("exam", EXAM, ["Sec 3"], ISO, ISO, GRACE, pub=PUB)
    e["days"] = {ISO: dict(levels=["Sec 3"], whole=True)}
    e = SC.save(e, PUB, CAL, GRACE)          # the check sets the day's from and to, which Make's fingerprint reads
    e["made"] = dict(seats={}, unseated={}, duties=duties, gone=[], made_at="x", fingerprint=MK.fingerprint(e, XS.load(PUB), M), published_at=None)
    return SC.save(e, PUB, CAL, GRACE)

def committee():
    c = A.app.test_client()
    assert c.post("/login", data={"code": os.environ["COMMITTEE_CODE"]}).status_code == 302
    return c

def ok(r):
    assert r.status_code == 200, (r.status_code, r.get_data(as_text=True)[:400])
    return r.get_json()

def _send_approve(c, id, base="/api/exams"):
    ok(c.post(f"{base}/{id}/send"))
    return ok(c.post(f"{base}/{id}/approve"))

def _backups(id):
    return AB.exams_records(id)

@t
def approve_sends_backups():
    _fresh()
    with published(PUB):
        c = committee()
        e = _made_exam([_duty([DANIEL])]); id = e["id"]
        ok(c.post(f"/api/exams/{id}/send"))
        assert _backups(id) == [], "nothing goes to relief before approval"
        ok(c.post(f"/api/exams/{id}/approve"))
        got = _backups(id)
        assert len(got) == 1, got
        r = got[0]
        assert r["teacher"] == DANIEL and r["reason_text"] == "Invigilating: " + EXAM and r["by"] == "Exams committee", r
        assert r["how"] == "planned" and r["reason"] == "Other" and r["exams"] == dict(id=id, kind="exam") and r["dates"] == [ISO], r
        assert r["cancelled"] is None and r["acknowledged"] is None
        assert [(x["key"], x["needed"], x["relief"]) for x in r["lessons"]] == [(DKEY, True, None)], r["lessons"]
        j = ok(staff(GRACE).get("/api/relief/absences"))
        assert r["id"] in [x["id"] for x in j["absences"]], "it shows in What's in"
        v = ok(c.get(f"/api/exams/{id}/view"))
        item = next(x for x in v["lessons"]["backup"] if x["key"] == DKEY)
        assert item["teacher"] == DANIEL and item["state"] == "sent" and item["relief"] is None, item

@t
def event_backup_by_the_teacher_in_charge():
    _fresh()
    with published(PUB):
        c = committee()
        ev = SC.new_event(EVENT, ["Sec 4"], [], ISO, ISO, GRACE, GRACE)
        ev["days"] = {ISO: dict(levels=["Sec 4"], whole=False, **{"from": "07:40", "to": "09:00"})}
        ev["going"] = [AISHA]      # her 3A English (07:40-08:20) runs: 3A is not on the event
        id = SC.save(ev, PUB, CAL, GRACE)["id"]
        _send_approve(c, id, "/api/events")
        got = _backups(id)
        assert len(got) == 1 and got[0]["teacher"] == AISHA and got[0]["reason_text"] == "At event: " + EVENT and got[0]["by"] == GRACE, got
        assert got[0]["exams"] == dict(id=id, kind="event") and [x["classes"] for x in got[0]["lessons"]] == [["3A"]], got[0]
        key, rid = got[0]["lessons"][0]["key"], got[0]["id"]
        v = ok(c.post(f"/api/events/{id}/handled", json=dict(teacher=AISHA, key=key, handled=True)))
        assert next(x for x in v["lessons"]["backup"] if x["key"] == key)["state"] == "handled"
        assert _backups(id) == [] and AB.load(rid)["cancelled"]["why"] == "Handled by the teacher in charge.", AB.load(rid)["cancelled"]
        ok(c.post(f"/api/events/{id}/handled", json=dict(teacher=AISHA, key=key, handled=False)))
        assert len(_backups(id)) == 1

@t
def handled_ourselves_sends_nothing():
    _fresh()
    with published(PUB):
        c = committee()
        e = _made_exam([_duty([DANIEL])]); id = e["id"]
        _send_approve(c, id)
        rid = _backups(id)[0]["id"]
        fp0, sent0 = AP.fp(SC.load(id)), SC.load(id)["sent_fp"]
        url = f"/api/exams/{id}/handled"
        j = ok(c.post(url, json=dict(teacher=DANIEL, key=DKEY, handled=True)))
        item = next(x for x in j["lessons"]["backup"] if x["key"] == DKEY)
        assert item["teacher"] == DANIEL and item["state"] == "handled" and item["relief"] is None, item
        assert SC.load(id)["handled"] == [DANIEL + "|" + DKEY]
        assert _backups(id) == [] and AB.load(rid)["cancelled"]["by"] == "app"
        assert AB.load(rid)["cancelled"]["why"] == "Handled by the exams committee.", AB.load(rid)["cancelled"]
        j = ok(c.post(url, json=dict(teacher=DANIEL, key=DKEY, handled=False)))
        assert next(x for x in j["lessons"]["backup"] if x["key"] == DKEY)["state"] == "sent"
        again = _backups(id)
        assert len(again) == 1 and again[0]["id"] != rid, "unmarking sends it again"
        ok(c.put("/api/exams/" + id, json=dict(SC.load(id), handled=[DANIEL + "|" + DKEY])))
        assert SC.load(id)["handled"] == [] and [r["id"] for r in _backups(id)] == [again[0]["id"]], "a PUT cannot change handled"
        assert AP.fp(SC.load(id)) == fp0 and SC.load(id)["sent_fp"] == sent0 and SC.load(id)["status"] == "approved"
        assert "handled" not in AP.SNAP and "handled" not in SC.load(id)["approved"]
        r = c.post(url, json=dict(teacher=DANIEL, key="nope", handled=True))
        assert r.status_code == 400 and r.get_json() == {"error": "That lesson no longer needs a backup."}, r.get_data(as_text=True)
        r = c.post(url, json=dict(teacher=DANIEL, key=DKEY, handled="yes"))
        assert r.status_code == 400

@t
def sync_is_idempotent_and_keeps_the_chosen_relief():
    _fresh()
    with published(PUB):
        c = committee()
        e = _made_exam([_duty([HAFIZ])]); id = e["id"]      # his 4A PE (08:40-09:20) runs into the duty
        _send_approve(c, id)
        first = _backups(id)
        assert len(first) == 1 and [x["subject"] for x in first[0]["lessons"]] == ["PE"], first
        assert RL.sync(SC.load(id), PUB, CAL, SOON) == dict(sent=0, cancelled=0)
        assert [r["id"] for r in _backups(id)] == [first[0]["id"]], "a second sync changes nothing"
        pe = first[0]["lessons"][0]["key"]
        AB.choose(first[0]["id"], pe, BEN, GRACE, PUB, links=_links())
        AB.set_work(first[0]["id"], pe, dict(text="Run the fitness test", link="", files=[], known=[]), HAFIZ)
        AB.acknowledge(first[0]["id"], HAFIZ)
        s = SC.load(id)
        s["made"]["duties"].append(_duty([HAFIZ], start=690, end=730, room="3-02", key=ISO + " 11:40"))    # the Assembly at 11:20
        SC.save(s, PUB, CAL, GRACE, check=False)
        _send_approve(c, id)
        now = _backups(id)
        assert [r["id"] for r in now] == [first[0]["id"]], "the backup is changed in place, never made again"
        by = {x["subject"]: x for x in now[0]["lessons"]}
        assert set(by) == {"PE", "Assembly"}, by
        assert by["PE"]["relief"] == BEN and by["PE"]["relief_by"] == GRACE and by["PE"]["work"]["text"] == "Run the fitness test", by["PE"]
        assert by["Assembly"]["relief"] is None and by["Assembly"]["needed"] is True
        assert now[0]["acknowledged"] is None and now[0]["periods"] == [4, 12], "a lesson came in: the person must look again"
        assert RL.sync(SC.load(id), PUB, CAL, SOON) == dict(sent=0, cancelled=0)

@t
def withdraw_cancels_but_keeps_the_past():
    _fresh()
    with published(PUB):
        c = committee()
        id = _made_exam([_duty([DANIEL])])["id"]
        _send_approve(c, id)
        rid = _backups(id)[0]["id"]
        ok(c.post(f"/api/exams/{id}/withdraw"))
        got = AB.load(rid)["cancelled"]
        assert got["why"] == "The schedule was withdrawn." and got["by"] == "app" and got["at"], got
        assert _backups(id) == []
        id2 = _made_exam([_duty([DANIEL])])["id"]
        _send_approve(c, id2)
        rid2 = _backups(id2)[0]["id"]
        old, oldx = LS.today, A._exams_today
        LS.today = A._exams_today = lambda: date(2027, 1, 5)
        try:
            ok(c.post(f"/api/exams/{id2}/withdraw"))
        finally:
            LS.today, A._exams_today = old, oldx
        assert AB.load(rid2)["cancelled"] is None, "a backup whose every date is past stays as it is"

@t
def own_absence_takes_over():
    _fresh()
    with published(PUB):
        c = committee()
        id = _made_exam([_duty([DANIEL])])["id"]
        _send_approve(c, id)
        b = _backups(id)[0]
        AB.choose(b["id"], DKEY, CHLOE, GRACE, PUB, links=_links())     # Chloe's 3B lesson then stops: she is free
        AB.set_work(b["id"], DKEY, dict(text="Do page 5", link="", files=[], known=[]), DANIEL)
        j = ok(staff(DANIEL).post("/api/relief/absences", json=dict(dates=[ISO], reason="Medical", reporting_officer=GRACE, lessons=[])))
        x = next(x for x in j["lessons"] if x["key"] == DKEY)
        assert x["needed"] is True and x["relief"] is None and x["work"]["text"] == "Do page 5", "the absent teacher sees a name once approved"
        x = next(x for x in AB.load(j["id"])["lessons"] if x["key"] == DKEY)
        assert x["relief"] == CHLOE and x["relief_by"] == GRACE, x
        gone = AB.load(b["id"])
        assert gone["cancelled"]["why"] == "Moved to %s's own absence." % DANIEL and gone["cancelled"]["by"] == "app", gone["cancelled"]
        assert gone["lessons"] == []
        assert ok(c.get(f"/api/exams/{id}/review"))["away"][0].startswith("Away (from relief): " + DANIEL)
        assert RL.sync(SC.load(id), PUB, CAL, SOON)["sent"] == 0 and _backups(id) == [], "no backup for someone away then"
        ok(c.post(f"/api/exams/{id}/away", json=dict(key=DUTY_KEY, room="3-01", away=DANIEL, name=BEN)))
        assert SC.load(id)["approved"]["made"]["duties"][0]["names"] == [BEN]
        assert _backups(id) == [], "Ben has no lesson then, and Daniel is away"
        mine = AB.load(j["id"])
        assert mine["cancelled"] is None and [(y["key"], y["relief"]) for y in mine["lessons"]] == [(DKEY, CHLOE)], "covered once"

@t
def republish_drops_a_vanished_backup():
    _fresh()
    with published(PUB):
        c = committee()
        id = _made_exam([_duty([DANIEL, HAFIZ])])["id"]          # Daniel's 4A Mathematics and Hafiz's 4A PE both run then
        _send_approve(c, id)
        rec = {r["teacher"]: r for r in _backups(id)}
        assert set(rec) == {DANIEL, HAFIZ}, rec
        pe = rec[HAFIZ]["lessons"][0]["key"]
    gone = HAFIZ + "|2027-01-04/Odd Mon/20/1/4A/Gone/Entire Class"      # a handled lesson no longer on the timetable
    s = SC.load(id); s["handled"] = [gone]
    SC.save(s, PUB, CAL, GRACE, check=False)
    pub2 = copy.deepcopy(PUB)
    pub2["model"]["lessons"][2]["teachers"] = [CHLOE]           # Daniel no longer teaches 4A Mathematics then
    with published(pub2):
        s = SC.load(id); s["scripts"] = "The office"
        ok(c.put("/api/exams/" + id, json=s))
        ok(c.post(f"/api/exams/{id}/send"))                     # an approval action: relief is synced
        d = AB.load(rec[DANIEL]["id"])
        assert d["lessons"] == [] and d["cancelled"]["why"] == "The duty changed.", "the backup lost the vanished lesson"
        h = AB.load(rec[HAFIZ]["id"])
        assert h["cancelled"] is None and [x["key"] for x in h["lessons"]] == [pe], h
        v = ok(c.get(f"/api/exams/{id}/view"))
        items = {(x["teacher"], x["key"]): x for x in v["lessons"]["backup"]}
        assert list(items) == [(HAFIZ, pe)] and items[(HAFIZ, pe)]["state"] == "sent", items
        assert SC.load(id)["handled"] == [gone], "the vanished handled entry is kept and ignored by name"

@t
def class_on_another_schedule_needs_no_backup():
    _fresh()
    e = _exam(duty_names=(DANIEL,)); _event()       # Daniel's 4A lesson during the duty: 4A is on the event then
    assert RL.backups(PUB, CAL, SC.load(e["id"]), _links(), [], SOON) == {}
    assert RL.sync(SC.load(e["id"]), PUB, CAL, SOON) == dict(sent=0, cancelled=0) and _backups(e["id"]) == []
    _clear(); e = _exam(duty_names=(DANIEL,))
    got = RL.backups(PUB, CAL, SC.load(e["id"]), _links(), [], SOON)
    assert list(got) == [DANIEL] and [x["key"] for x in got[DANIEL]] == [DKEY] and got[DANIEL][0]["date"] == ISO, got
    assert RL.backups(PUB, CAL, SC.load(e["id"]), _links(), [], date(2027, 1, 5)) == {}, "dated before today"
    assert RL.backups(PUB, CAL, dict(SC.load(e["id"]), handled=[DANIEL + "|" + DKEY]), _links(), [], SOON) == {}
    assert RL.backups(PUB, CAL, SC.load(e["id"]), _links(), [_rec(DANIEL, periods=[1, 2])], SOON) == {}, "away then"
    assert list(RL.backups(PUB, CAL, SC.load(e["id"]), _links(), [_rec(DANIEL, periods=[9, 10])], SOON)) == [DANIEL]
    assert RL.backups(PUB, CAL, _exam("waiting"), _links(), [], SOON) == {}, "no approved copy"

@t
def sync_failure_does_not_fail_approve():
    _fresh()
    old, lg = RL.sync, RL.logger
    old_exc, seen = lg.exception, []
    def boom(*a, **k): raise RuntimeError("test")
    RL.sync, lg.exception = boom, lambda msg, *a, **k: seen.append(msg)
    try:
        with published(PUB):
            c = committee()
            id = _made_exam([_duty([DANIEL])])["id"]
            ok(c.post(f"/api/exams/{id}/send"))
            j = ok(c.post(f"/api/exams/{id}/approve"))
            assert j["status"] == "approved" and _backups(id) == []
            assert seen and set(seen) == {"exams: relief sync failed"}, seen
    finally:
        RL.sync, lg.exception = old, old_exc

@t
def backup_periods_hide_nobody_and_update_in_place():
    _fresh()
    src = dict(id="s1", kind="exam")
    mine = [dict(x, date=ISO) for x in LS.on_date(PUB, CAL, HAFIZ, MON)]       # PE (periods 5-6) and the Assembly (period 13)
    pe, asm = mine[0]["key"], mine[1]["key"]
    r = AB.from_exams(HAFIZ, mine, src, "Exams committee", "Invigilating: X", None)
    assert r["periods"] == [4, 12] and r["dates"] == [ISO] and all(x["needed"] for x in r["lessons"]), r
    recs = AB.all_records()             # F1: the span is for the pages; relief reads a backup by its needed lessons
    assert HAFIZ in _free_names(FR.free_then(PUB, SETTINGS, recs, _need(8), DANIEL)), "free in the gap between his backup lessons"
    assert FR.there_then(recs, [HAFIZ], MON, 8, 1) == [HAFIZ] and FR.there_then(recs, [HAFIZ], MON, 4, 1) == []
    AB.choose(r["id"], pe, BEN, GRACE, PUB)
    AB.set_work(r["id"], pe, dict(text="Laps", link="", files=[], known=[]), HAFIZ)
    AB.acknowledge(r["id"], HAFIZ)
    got = AB.update_exams(r["id"], {pe}, [], "Exams committee", "Invigilating: Y", SOON)
    assert got["id"] == r["id"] and [x["key"] for x in got["lessons"]] == [pe] and got["periods"] == [4, 5], got
    assert got["lessons"][0]["relief"] == BEN and got["lessons"][0]["work"]["text"] == "Laps" and got["reason_text"] == "Invigilating: Y"
    assert got["acknowledged"], "taking a lesson off keeps the acknowledgement"
    got = AB.update_exams(r["id"], {pe, asm}, [mine[1]], None, None, SOON)
    assert [x["key"] for x in got["lessons"]] == [pe, asm] and got["acknowledged"] is None and got["reason_text"] == "Invigilating: Y"
    got = AB.update_exams(r["id"], set(), [], None, None, date(2027, 1, 5))
    assert len(got["lessons"]) == 2 and got["cancelled"] is None, "a lesson dated before today always stays"
    got = AB.update_exams(r["id"], set(), [], None, None, SOON, why="The schedule was withdrawn.")
    assert got["lessons"] == [] and got["cancelled"]["why"] == "The schedule was withdrawn." and got["cancelled"]["by"] == "app"
    assert AB.from_exams(HAFIZ, [dict(mine[1], others=[BEN])], src, "Exams committee", "x", None) is None, "Ben is there: nothing saved"
    away = _put(_rec(HAFIZ, periods=[4, 5]))
    r3 = AB.from_exams(HAFIZ, mine, src, "Exams committee", "x", None)
    assert [x["key"] for x in r3["lessons"]] == [asm], "a lesson while away in an absence of their own is left to it"
    _drop(away)
    assert not hasattr(AB, "cancel_exams"), "sync changes backups in place: nothing cancels a whole backup (past lessons included)"

def _two_duties():
    """Hafiz on two duties: his 4A PE and the Assembly both need a backup"""
    return [_duty([HAFIZ]), _duty([HAFIZ], start=690, end=730, room="3-02", key=ISO + " 11:40")]

@t
def relief_team_not_needed_survives_sync():
    _fresh()
    with published(PUB):
        c = committee()
        id = _made_exam(_two_duties())["id"]
        _send_approve(c, id)
        b = _backups(id)[0]
        by = {x["subject"]: x["key"] for x in b["lessons"]}
        AB.not_needed(b["id"], by["PE"], "The class is on a trip", GRACE, team=True)
        j = ok(staff(HAFIZ).post("/api/relief/absences", json=dict(dates=[ISO], periods=[12, 12], reason="Medical", reporting_officer=GRACE, lessons=[])))
        assert [x["key"] for x in j["lessons"]] == [by["Assembly"]]
        left = AB.load(b["id"])
        assert left["cancelled"] is None and [(x["key"], x["needed"]) for x in left["lessons"]] == [(by["PE"], False)], left
        assert RL.sync(SC.load(id), PUB, CAL, SOON) == dict(sent=0, cancelled=0)
        assert RL.sync(SC.load(id), PUB, CAL, SOON) == dict(sent=0, cancelled=0)
        now = _backups(id)
        assert [r["id"] for r in now] == [b["id"]] and now[0]["lessons"][0]["not_needed"]["by"] == GRACE, now
        s = SC.load(id); s["approved"]["name"] = "Sec 3 Mid-Year Exam"
        SC.save(s, PUB, CAL, GRACE, check=False)
        RL.sync(SC.load(id), PUB, CAL, SOON)
        now = _backups(id)
        assert [r["id"] for r in now] == [b["id"]] and now[0]["reason_text"] == "Invigilating: Sec 3 Mid-Year Exam", now
        assert now[0]["lessons"][0]["needed"] is False, "the relief team's Not needed is kept"

@t
def change_and_withdraw_keep_past_lessons():
    _fresh()
    d2 = "2027-01-18"                                           # the next Odd Mon: Daniel's 4A Mathematics again
    e = SC.new("exam", EXAM, ["Sec 3"], ISO, d2, GRACE, pub=PUB)
    e["days"] = {ISO: dict(levels=["Sec 3"], whole=True), d2: dict(levels=["Sec 3"], whole=True)}
    e["made"] = dict(seats={}, unseated={}, published_at=None, duties=[_duty([DANIEL]), dict(_duty([DANIEL], key=d2 + " 07:50"), date=d2)])
    e = _approve(e)
    RL.sync(SC.load(e["id"]), PUB, CAL, SOON)
    r = _backups(e["id"])[0]
    assert r["dates"] == [ISO, d2] and len(r["lessons"]) == 2, r
    mid = date(2027, 1, 5)
    s = SC.load(e["id"]); s["made"]["duties"] = s["made"]["duties"][:1]
    _approve(s)
    assert RL.sync(SC.load(e["id"]), PUB, CAL, mid) == dict(sent=0, cancelled=0)
    got = AB.load(r["id"])
    assert got["cancelled"] is None and [x["date"] for x in got["lessons"]] == [ISO] and got["dates"] == [ISO], "the past lesson stays"
    s = SC.load(e["id"]); s["made"]["duties"] = e["made"]["duties"]
    _approve(s)
    RL.sync(SC.load(e["id"]), PUB, CAL, mid)
    got = AB.load(r["id"])
    assert [x["date"] for x in got["lessons"]] == [ISO, d2] and got["id"] == r["id"], "the same backup takes the lesson again"
    s = SC.load(e["id"]); s.update(status="withdrawn", approved=None)
    SC.save(s, PUB, CAL, GRACE, check=False)
    assert RL.sync(SC.load(e["id"]), PUB, CAL, mid) == dict(sent=0, cancelled=0)
    got = AB.load(r["id"])
    assert got["cancelled"] is None and [x["date"] for x in got["lessons"]] == [ISO], "withdraw takes only the lessons to come"

@t
def one_lesson_one_schedule():
    _fresh()
    with published(PUB):
        c = committee()
        a = _made_exam([_duty([DANIEL])])["id"]; _send_approve(c, a)
        b = _made_exam([_duty([DANIEL])])["id"]; _send_approve(c, b)
        assert [len(_backups(a)), len(_backups(b))] == [1, 0], "the lesson is sent once"
        item = next(x for x in ok(c.get(f"/api/exams/{b}/view"))["lessons"]["backup"] if x["key"] == DKEY)
        assert item["state"] == "elsewhere", item
        ok(c.post(f"/api/exams/{a}/withdraw"))
        assert _backups(a) == [] and [[x["key"] for x in r["lessons"]] for r in _backups(b)] == [[DKEY]], "handed to the other at once"
        ev = SC.new_event(EVENT, ["Sec 4"], [], ISO, ISO, GRACE, GRACE)
        ev["days"] = {ISO: dict(levels=["Sec 4"], whole=False, **{"from": "07:40", "to": "09:00"})}
        ev["going"] = [BEN]
        _send_approve(c, SC.save(ev, PUB, CAL, GRACE)["id"], "/api/events")
        assert _backups(b) == [], "4A is on the event: the other schedule's backup gives the lesson up at once"
        item = next(x for x in ok(c.get(f"/api/exams/{b}/view"))["lessons"]["backup"] if x["key"] == DKEY)
        assert item["state"] == "stopped" and item["stopped"] == "4A is on " + EVENT, item

@t
def one_item_per_teacher_and_states():
    _fresh()
    M["lessons"][2]["teachers"] = [DANIEL, CHLOE]           # a 4A Mathematics lesson both teach
    old = A._exams_today
    try:
        with published(PUB):
            c = committee()
            id = _made_exam([_duty([DANIEL, CHLOE])])["id"]
            items = [(x["teacher"], x["key"], x["state"]) for x in ok(c.get(f"/api/exams/{id}/view"))["lessons"]["backup"] if x["key"] == DKEY]
            assert items == [(DANIEL, DKEY, "later"), (CHLOE, DKEY, "later")], items
            v = ok(c.post(f"/api/exams/{id}/handled", json=dict(teacher=CHLOE, key=DKEY, handled=True)))
            assert [x["state"] for x in v["lessons"]["backup"] if x["key"] == DKEY] == ["later", "handled"]
            A._exams_today = lambda: date(2027, 1, 5)
            v = ok(c.get(f"/api/exams/{id}/view"))
            assert [x["state"] for x in v["lessons"]["backup"] if x["key"] == DKEY] == ["past", "handled"]
    finally:
        A._exams_today = old
        M["lessons"][2]["teachers"] = [DANIEL]

@t
def malformed_records_are_skipped():
    _clear(); e = _exam(duty_names=(DANIEL,))
    bad = [_rec(DANIEL, periods="x"), _rec(DANIEL, periods=[1]), _rec(DANIEL, periods=[None, 2]), _rec(DANIEL, dates=["Monday"]),
           dict(_rec(DANIEL), dates=ISO), _rec(AISHA, exams=dict(id="e", kind="exam"), lessons=["x", dict(needed=True, relief=BEN), dict(COVER, relief=["x"])]),
           dict(id="no-teacher", dates=[ISO]), _rec(["x"]), "not a record", None]
    assert RL.relief_busies(M, bad) == []
    assert RL.away_on(SC.load(e["id"]), M, bad, SOON) == []
    assert list(RL.backups(PUB, CAL, SC.load(e["id"]), _links(), bad, SOON)) == [DANIEL]


@t
def handled_on_one_schedule_covers_every_schedule():
    _fresh()
    with published(PUB):
        c = committee()
        a = _made_exam([_duty([DANIEL])])["id"]; _send_approve(c, a)
        b = _made_exam([_duty([DANIEL])])["id"]; _send_approve(c, b)
        assert [len(_backups(a)), len(_backups(b))] == [1, 0]
        ok(c.post(f"/api/exams/{a}/handled", json=dict(teacher=DANIEL, key=DKEY, handled=True)))
        assert [len(_backups(a)), len(_backups(b))] == [0, 0], "the other schedule sends nothing for it either"
        item = next(x for x in ok(c.get(f"/api/exams/{b}/view"))["lessons"]["backup"] if x["key"] == DKEY)
        assert item["state"] == "handled_elsewhere", item
        assert ok(c.get(f"/api/exams/{b}/review"))["review"]["what"]["backups"] == 0, "not counted on the Approval tab"
        ok(c.post(f"/api/exams/{a}/handled", json=dict(teacher=DANIEL, key=DKEY, handled=False)))
        assert [len(_backups(a)), len(_backups(b))] == [1, 0]
        assert ok(c.get(f"/api/exams/{a}/review"))["review"]["what"]["backups"] == 1
        ok(c.post(f"/api/exams/{a}/handled", json=dict(teacher=DANIEL, key=DKEY, handled=True)))
        assert ok(c.get(f"/api/exams/{a}/review"))["review"]["what"]["backups"] == 0, "handled ourselves is not counted"


@t
def event_review_counts_and_a_failing_count_keeps_the_answer():
    _fresh()
    with published(PUB):
        c = committee()
        ev = SC.new_event(EVENT, ["Sec 4"], [], ISO, ISO, GRACE, GRACE)
        ev["days"] = {ISO: dict(levels=["Sec 4"], whole=False, **{"from": "07:40", "to": "09:00"})}
        ev["going"] = [AISHA]
        id = SC.save(ev, PUB, CAL, GRACE)["id"]
        _send_approve(c, id, "/api/events")
        key = _backups(id)[0]["lessons"][0]["key"]
        assert ok(c.get(f"/api/events/{id}/review"))["review"]["what"]["backups"] == 1
        ok(c.post(f"/api/events/{id}/handled", json=dict(teacher=AISHA, key=key, handled=True)))
        assert ok(c.get(f"/api/events/{id}/review"))["review"]["what"]["backups"] == 0, "handled is not counted"
        ok(c.post(f"/api/events/{id}/handled", json=dict(teacher=AISHA, key=key, handled=False)))
        old = A._marked
        def boom(*a, **k): raise RuntimeError("test")
        A._marked = boom
        try:
            raw = ok(c.get(f"/api/events/{id}/review"))["review"]["what"]["backups"]
            e = _made_exam([_duty([DANIEL])])["id"]
            ok(c.post(f"/api/exams/{e}/send"))
            r = ok(c.post(f"/api/exams/{e}/approve"))
        finally:
            A._marked = old
        assert raw == 1, "the unmarked count stays"
        assert r["review"]["what"]["backups"] == 0, "approve still answers, with the review's own (unmarked) count: the hand-made duty lists no backup name"
        ok(c.post(f"/api/events/{id}/withdraw"))      # 4A was on the event: its lessons stop, so Mr Koh needs none
        assert ok(c.get(f"/api/exams/{e}/review"))["review"]["what"]["backups"] == 1, "and the marked count is back once it works"


# ---- the final review's fix wave
@t
def cancelled_own_absence_gives_the_lesson_back():
    _fresh()
    with published(PUB):
        c = committee()
        id = _made_exam([_duty([DANIEL])])["id"]
        _send_approve(c, id)
        b = _backups(id)[0]
        d = staff(DANIEL)
        j = ok(d.post("/api/relief/absences", json=dict(dates=[ISO], reason="Medical", reporting_officer=GRACE, lessons=[])))
        assert _backups(id) == [] and AB.load(b["id"])["cancelled"]["why"] == "Moved to %s's own absence." % DANIEL
        ok(d.post("/api/relief/absences/%s/cancel" % j["id"], json=dict(why="Better now")))
        got = _backups(id)
        assert len(got) == 1 and got[0]["teacher"] == DANIEL and [(x["key"], x["needed"]) for x in got[0]["lessons"]] == [(DKEY, True)], got
        item = next(x for x in ok(c.get(f"/api/exams/{id}/view"))["lessons"]["backup"] if x["key"] == DKEY)
        assert item["state"] == "sent", item

@t
def a_republish_sends_a_lesson_that_moved_into_a_duty():
    _fresh()
    cur, pub2 = [PUB], copy.deepcopy(PUB)
    pub2["model"]["lessons"][2]["teachers"] = [CHLOE]       # 4A Mathematics (08:00-08:40, during the duty) is Chloe's now
    def publish():
        cur[0] = pub2
        return dict(published=True)
    old_pub, old_publish = store.published, A.draft.publish
    store.published, A.draft.publish = (lambda: cur[0]), publish
    try:
        c = committee()
        id = _made_exam([_duty([CHLOE])])["id"]
        _send_approve(c, id)
        assert _backups(id) == [], "her only lesson then (3B) stops for the exam"
        assert ok(c.post("/api/draft/publish")) == dict(published=True)
        got = _backups(id)
        assert len(got) == 1 and got[0]["teacher"] == CHLOE and [x["key"] for x in got[0]["lessons"]] == [DKEY], got
    finally:
        store.published, A.draft.publish = old_pub, old_publish

@t
def one_failing_sync_does_not_stop_the_others():
    _fresh()
    a, b = _exam(duty_names=(DANIEL,))["id"], _exam(duty_names=(HAFIZ,))["id"]
    real, lg, bad, seen = RL.sync, RL.logger, [a], []
    old_exc = lg.exception
    def flaky(s, *x, **k):
        if s["id"] == bad[0]: raise RuntimeError("test")
        return real(s, *x, **k)
    RL.sync, lg.exception = flaky, lambda msg, *x, **k: seen.append(msg)
    try:
        RL.sync_all(PUB, CAL, SOON, first=SC.load(a))
        assert _backups(a) == [] and [r["teacher"] for r in _backups(b)] == [HAFIZ] and seen == [RL.SYNC_FAILED], seen
        shutil.rmtree(AB.DIR, ignore_errors=True)
        bad[0], seen[:] = b, []
        RL.sync_all(PUB, CAL, SOON)          # both from to_sync, in whatever order the folder lists them
        assert [r["teacher"] for r in _backups(a)] == [DANIEL] and _backups(b) == [] and seen == [RL.SYNC_FAILED], seen
    finally:
        RL.sync, lg.exception = real, old_exc

@t
def a_lesson_added_to_a_backup_is_new_in_whats_in():
    _fresh()
    mine = [dict(x, date=ISO) for x in LS.on_date(PUB, CAL, HAFIZ, MON)]        # PE and the Assembly
    r = AB.from_exams(HAFIZ, mine[:1], dict(id="s1", kind="exam"), "Exams committee", "Invigilating: X", None)
    r["at"] = "2026-11-01T08:00:00+08:00"
    _put(r)
    with published(PUB):
        g = staff(GRACE)
        ok(g.post("/api/relief/absences/seen", json={}))
        new = lambda: next(x for x in ok(g.get("/api/relief/absences"))["absences"] if x["id"] == r["id"])["new"]
        assert new() is False, "seen already"
        AB.update_exams(r["id"], {mine[0]["key"]}, [], None, None, SOON)
        assert new() is False and "changed_at" not in AB.load(r["id"]), "nothing came in"
        AB.update_exams(r["id"], {mine[0]["key"]}, mine[1:], None, None, SOON)
        assert AB.load(r["id"])["changed_at"] and new() is True, "a lesson came in: new again"

@t
def an_absence_sent_before_approval_marks_its_stopped_lesson():
    _fresh()
    with published(PUB):
        d, g = staff(DANIEL), staff(GRACE)
        j = ok(d.post("/api/relief/absences", json=dict(dates=[ISO], reason="Medical", reporting_officer=GRACE, lessons=[])))
        assert [(x["key"], x["needed"], x["stopped"]) for x in j["lessons"]] == [(DKEY, True, "")], j["lessons"]
        _event()                                            # approved afterwards: 4A is on it 07:40-09:00
        why = "4A is on " + EVENT
        x = ok(d.get("/api/relief/absences/" + j["id"]))["lessons"][0]
        assert x["stopped"] == why and x["needed"] is True, x
        mine = next(r for r in ok(g.get("/api/relief/absences"))["absences"] if r["id"] == j["id"])
        assert mine["lessons"][0]["stopped"] == why, "What's in marks it too"
        url = "/api/relief/absences/%s/lessons/%s/relief" % (j["id"], urllib.parse.quote(DKEY))
        r = g.put(url, json=dict(relief=CHLOE))
        assert r.status_code == 400 and r.get_json() == {"error": "This lesson is not happening: %s." % why}, r.get_data(as_text=True)
        raises(ValueError, lambda: AB.choose(j["id"], DKEY, CHLOE, GRACE, PUB, links=_links()), "This lesson is not happening: %s." % why)
        assert AB.choose(j["id"], DKEY, BEN, GRACE, PUB)["lessons"][0]["relief"] == BEN, "without links, as before"
        assert ok(g.put(url, json=dict(relief=None)))["lessons"][0]["relief"] is None, "taking the choice off still works"
        ok(d.post("/api/relief/absences/%s/cancel" % j["id"], json=dict(why="Better now")))
        assert ok(d.get("/api/relief/absences/" + j["id"]))["lessons"][0]["stopped"] == "", "a cancelled absence is not marked"
    _clear()

@t
def relief_pages_work_when_the_exams_cannot_be_read():
    _fresh()
    with published(PUB):
        d = staff(DANIEL)
        j = ok(d.post("/api/relief/absences", json=dict(dates=[ISO], reason="Medical", reporting_officer=GRACE, lessons=[])))
        real = RL.Links.__dict__["load"]          # the classmethod itself, put back as it was
        def boom(*a, **k): raise KeyError("test")
        RL.Links.load = boom
        try:
            got = ok(d.get("/api/relief/absences/mine"))["absences"]
        finally:
            RL.Links.load = real
        assert [x["stopped"] for r in got for x in r["lessons"]] == [""], got
        AB.cancel(j["id"], "test", DANIEL)

@t
def the_absence_page_shows_not_happening():
    js = open(os.path.join(ROOT, "static", "relief.js"), encoding="utf-8").read()
    row = js[js.index("function lessonRow("):js.index("function fileLink(")]
    assert 'esc("Not happening: " + x.stopped)' in row and "${stop}" in row, "the absence's lesson line says why it is not happening"

@t
def a_stale_handled_tag_counts_for_nothing():
    _fresh()
    with published(PUB):
        c = committee()
        a = _made_exam([_duty([DANIEL])])["id"]; _send_approve(c, a)
        b = _made_exam([_duty([DANIEL])])["id"]; _send_approve(c, b)
        ok(c.post(f"/api/exams/{a}/handled", json=dict(teacher=DANIEL, key=DKEY, handled=True)))
        assert [len(_backups(a)), len(_backups(b))] == [0, 0]
        ok(c.post(f"/api/exams/{a}/away", json=dict(key=DUTY_KEY, room="3-01", away=DANIEL, name=BEN)))
        assert SC.load(a)["handled"] == [DANIEL + "|" + DKEY], "the tag stays on the first schedule"
        got = _backups(b)
        assert len(got) == 1 and got[0]["teacher"] == DANIEL and [x["key"] for x in got[0]["lessons"]] == [DKEY], \
            "Daniel is off the first schedule's duty: its tag no longer covers his lesson"
        item = next(x for x in ok(c.get(f"/api/exams/{b}/view"))["lessons"]["backup"] if x["key"] == DKEY)
        assert item["state"] == "sent", item

@t
def a_backup_emptied_partly_by_a_duty_change_says_the_duty_changed():
    _fresh()
    with published(PUB):
        c = committee()
        id = _made_exam(_two_duties())["id"]
        _send_approve(c, id)
        b = _backups(id)[0]
        pe = next(x["key"] for x in b["lessons"] if x["subject"] == "PE")
    s = SC.load(id)
    s["made"]["duties"], s["handled"] = s["made"]["duties"][:1], [HAFIZ + "|" + pe]      # PE handled, the Assembly duty gone
    _approve(s)
    assert RL.sync(SC.load(id), PUB, CAL, SOON) == dict(sent=0, cancelled=1)
    assert AB.load(b["id"])["cancelled"]["why"] == "The duty changed.", AB.load(b["id"])["cancelled"]

@t
def links_log_what_they_cannot_read_once():
    _clear(); e = _exam(); _event()
    lg, seen = RL.logger, []
    old_exc, old_view, old_busies = lg.exception, RL._days.merged_view, RL._schedules.busies
    def no_view(*a, **k): raise KeyError("test")
    def busies(copies, model):
        if copies[0]["id"] == e["id"]: raise KeyError("test")
        return old_busies(copies, model)
    old_err = lg.error
    lg.exception = lg.error = lambda msg, *a, **k: seen.append(msg % a)
    RL._days.merged_view = no_view
    try:
        L = _links()
        tue = date(2027, 1, 5)
        assert L.stopped(_lesson(0)) == L.stopped(_lesson(0)) == L.stopped(dict(_lesson(0), date=tue)) == ""
        assert seen == ["exams: relief links could not read %s" % ISO], "once a date; nothing is read on a date no schedule holds"
        seen[:] = []
        RL._days.merged_view, RL._schedules.busies = old_view, busies
        L = _links()
        assert L.busy(AISHA, MON, 0, 1) == L.busy(AISHA, MON, 0, 1) == "", "the exam that cannot be read gives no duty"
        assert L.busy(BEN, MON, 0, 1) == "At event: " + EVENT, "the event still counts"
        assert seen == ["exams: relief links could not read the duties of schedule %s" % e["id"]], seen
    finally:
        lg.exception, lg.error, RL._days.merged_view, RL._schedules.busies = old_exc, old_err, old_view, old_busies

@t
def links_name_the_classes_when_two_windows_meet_mid_period():
    _clear()
    for name, a, b in (("Sec 4 Talk", "08:40", "08:50"), ("Sec 4 Visit", "08:50", "09:00")):
        e = SC.new_event(name, ["Sec 4"], [], ISO, ISO, GRACE, GRACE)
        e["days"] = {ISO: dict(levels=["Sec 4"], whole=False, **{"from": a, "to": b})}
        _approve(e)
    real = RL._days.merged_view
    def joined(pub, cal, scheds, iso):        # as a view that joins windows meeting mid-period would give it
        v = real(pub, cal, scheds, iso)
        for r in v["lessons"]:
            if r["row"] == 7: r["stopped"], r["running"] = [(520, 540)], []       # 4A Literature, period 4 (08:40-09:00)
        return v
    RL._days.merged_view = joined
    try:
        assert _links().stopped(_lesson(7)) == "4A is on Sec 4 Talk and Sec 4 Visit", _links().stopped(_lesson(7))
    finally:
        RL._days.merged_view = real
    assert _links().stopped(_lesson(7)) == "", "the view as it is: no one window holds the period, so it runs"
    _clear()

@t
def the_lists_read_relief_once():
    _fresh()
    _exam(duty_names=(AISHA,)); _exam(duty_names=(BEN,)); _event()
    r = _put(_rec(AISHA, periods=[0, 1])); r2 = _put(_rec(BEN))
    real, calls = AB.all_records, []
    AB.all_records = lambda: calls.append(1) or real()
    try:
        with published(PUB):
            j = ok(committee().get("/api/exams"))
        assert len(calls) == 1, calls
        assert sorted(len(x["away"]) for x in j["schedules"]) == [1, 1], j["schedules"]
    finally:
        AB.all_records = real
        _drop(r); _drop(r2)
    assert "exams_schedules._all(" not in open(os.path.join(ROOT, "app.py"), encoding="utf-8").read()

# ---- after the accounts merges: a Handled ourselves change is one history entry, as every exams and events save
import history as H  # noqa: E402

@t
def handled_ourselves_is_one_history_entry():
    _fresh()
    def entries(): return [x for x in H.read(kinds=["exams"], limit=10000) if x.get("what") == "handled"]
    with published(PUB):
        c = committee()
        e = _made_exam([_duty([DANIEL])]); id = e["id"]
        _send_approve(c, id)
        n = len(entries())
        ok(c.post(f"/api/exams/{id}/handled", json=dict(teacher=DANIEL, key=DKEY, handled=True)))
        ok(c.post(f"/api/exams/{id}/handled", json=dict(teacher=DANIEL, key=DKEY, handled=False)))
        assert c.post(f"/api/exams/{id}/handled", json=dict(teacher=DANIEL, key="nope", handled=True)).status_code == 400
        got = list(reversed(entries()[:len(entries()) - n]))
        lesson = f"{DANIEL}'s 4A Mathematics on Mon 4 Jan 08:00–08:40"
        assert [(x["text"], x["link"], x["exam"], x["where"], x["who"], x["as"]) for x in got] == [
            (f"{EXAM}: {lesson} handled ourselves", "/exams", id, "Exams and events", None, "Shared committee code"),
            (f"{EXAM}: {lesson} no longer handled ourselves", "/exams", id, "Exams and events", None, "Shared committee code")], got
        _fresh()        # the exam stops 3A: the event's backup below is a 3A lesson
        ev = SC.new_event(EVENT, ["Sec 4"], [], ISO, ISO, GRACE, GRACE)
        ev["days"] = {ISO: dict(levels=["Sec 4"], whole=False, **{"from": "07:40", "to": "09:00"})}
        ev["going"] = [AISHA]
        eid = SC.save(ev, PUB, CAL, GRACE)["id"]
        _send_approve(c, eid, "/api/events")
        key = _backups(eid)[0]["lessons"][0]["key"]
        n = len(entries())
        ok(staff(GRACE).post(f"/api/events/{eid}/handled", json=dict(teacher=AISHA, key=key, handled=True)))     # the teacher in charge
        got = entries()[:len(entries()) - n]
        assert [(x["text"], x["link"], x["exam"], x["who"], x["via"]) for x in got] == [
            (f"{EVENT}: {AISHA}'s 3A English on Mon 4 Jan 07:40–08:20 handled ourselves", f"/events/{eid}", eid, GRACE, "code")], got
    _clear()


# ---- the join with relief stage 3 (picks, approval, Today, Reliefs I'm covering, Load)
from relief import cover as CV, fill as FL, pick as PK  # noqa: E402

IVAN = "Mr Ivan Lee"
CKEY = RL.key_of(M, 1, MON, "Odd Mon")      # Chloe's 3B Mathematics, periods 1-2: a Sec 3 exam stops it
PEKEY = RL.key_of(M, 5, MON, "Odd Mon")     # Hafiz's 4A PE, periods 5-6
STOP = "3B is on " + EXAM
NOT_ON = "This lesson is not happening: %s." % STOP
ST = RS.load(PUB)
DEC = "2026-12-01T08:00:00+08:00"

def _plan(teacher, key=None, relief=None, links=None, periods=None):
    """a planned absence on MON sent by Grace, with the planner's choice for one lesson"""
    lessons = [dict(key=key, relief=relief)] if relief else []
    return AB.new(dict(teacher=teacher, dates=[ISO], periods=periods, reason="Other", reason_text="A course", lessons=lessons), PUB, GRACE, "planned",
                  may_choose=True, links=links)

def _cov(id, key):
    r = AB.load(id)
    x, c = CV.find(r, key)
    return r, x, c

def _pk(who, by="app"):
    return dict(who=who, by=by, reason="Because.", at="2026-11-30T08:00:00+08:00")

def _hist(c):
    return [(h["what"], h["who"], h["by"]) for h in c.get("history") or []]

def _relief_team():
    return staff(GRACE)

@t
def a_stopped_lesson_books_nobody():
    _fresh()
    i = _plan(CHLOE, CKEY, HAFIZ)["id"]
    recs = AB.all_records()
    assert FR.relief_periods(recs, HAFIZ, {MON}) == 2 and FR.relief_periods(recs, HAFIZ, {MON}, links=_links()) == 2
    _exam()
    L = _links()
    assert L.stopped(AB.load(i)["lessons"][0]) == STOP
    assert FR.relief_periods(recs, HAFIZ, {MON}) == 2 and FR.relief_periods(recs, HAFIZ, {MON}, links=L) == 0
    assert FR.week_so_far(PUB, CAL, recs, HAFIZ, MON, links=L) == FR.week_so_far(PUB, CAL, [], HAFIZ, MON, links=L)
    need = dict(_need(1), key=DKEY)              # Daniel's 4A lesson then: Hafiz is free once his relief does not happen
    assert HAFIZ not in _free_names(FR.free_then(PUB, SETTINGS, recs, need, DANIEL))
    got = FR.free_then(PUB, SETTINGS, recs, need, DANIEL, links=L)
    hafiz = next(x for g in got["groups"] for x in g["people"] if x["name"] == HAFIZ)
    assert hafiz["today"] == 0 and hafiz["term"] == 0, hafiz
    given = PK._given(recs, [HAFIZ], [MON], (DANIEL, DKEY), links=L)
    assert given == {HAFIZ: []} and PK._given(recs, [HAFIZ], [MON], (DANIEL, DKEY)) == {HAFIZ: [(ISO, 0, 2)]}, given

@t
def a_stopped_lesson_is_not_picked_or_approved():
    _fresh()
    with published(PUB):
        i = _plan(CHLOE)["id"]
        j = _plan(AISHA, RL.key_of(M, 0, MON, "Odd Mon"), HAFIZ)["id"]
        e = _exam(duty_names=(BEN, HAFIZ))
        L = _links()
        assert L.busy(HAFIZ, MON, 0, 2) and CV.stale(PUB, ST, AB.all_records(), *_cov(j, RL.key_of(M, 0, MON, "Odd Mon")), links=L) is False
        for f in (lambda: CV.set_pick(i, CKEY, _pk(HAFIZ), PUB, ST, links=L), lambda: CV.change(i, CKEY, HAFIZ, GRACE, PUB, ST, links=L)):
            raises(ValueError, f, NOT_ON)
        old, asked = PK.choose_for, []
        PK.choose_for = lambda *a, **k: asked.append(a[4]["key"]) or old(*a, **k)
        try: got = FL.run(ids=[i, j], now=DEC)
        finally: PK.choose_for = old
        assert got == dict(picked=0, nobody=0) and asked == [], "the model is not even asked"
        assert CV.state(*_cov(i, CKEY)) == "open" and _cov(i, CKEY)[2].get("history") in (None, [])
        assert _cov(j, RL.key_of(M, 0, MON, "Odd Mon"))[2]["relief"] == HAFIZ, "a waiting pick of a stopped lesson is left as it is"
        AKEY = RL.key_of(M, 0, MON, "Odd Mon")
        raises(ValueError, lambda: CV.approve(j, AKEY, HAFIZ, GRACE, PUB, ST, links=L), NOT_ON.replace("3B", "3A"))
        raises(ValueError, lambda: CV.split(j, AKEY, 1, GRACE, links=L), NOT_ON.replace("3B", "3A"))
        all_ = CV.approve_all(ISO, [dict(id=j, ckey=AKEY, who=HAFIZ)], GRACE, PUB, ST, links=L)
        assert all_["approved"] == [] and all_["skipped"][0]["why"] == NOT_ON.replace("3B", "3A"), all_
        s = SC.load(e["id"]); s.update(status="withdrawn", approved=None); SC.save(s, PUB, CAL, GRACE, check=False)
        assert FL.run(ids=[i], now=DEC)["picked"] == 1, "withdrawn: the lesson happens, and is picked for"
        CV.approve(j, AKEY, HAFIZ, GRACE, PUB, ST, links=_links())
        assert CV.state(*_cov(j, AKEY)) == "approved"

@t
def someone_on_a_duty_is_never_picked_or_approved():
    _fresh()
    with published(PUB):
        i = _plan(DANIEL)["id"]                     # 4A Mathematics, periods 2-3: it runs
        free = _free_names(FR.free_then(PUB, ST, [], AB.load(i)["lessons"][0], DANIEL))
        assert AISHA not in free and HAFIZ in free and BEN in free, free
        _exam(duty_names=[n for n in (BEN, GRACE, CHLOE, AISHA, HAFIZ, IVAN) if n != BEN])
        L = _links()
        raises(ValueError, lambda: CV.set_pick(i, DKEY, _pk(HAFIZ), PUB, ST, links=L), CV.NOT_FREE.format(name=HAFIZ))
        raises(ValueError, lambda: CV.change(i, DKEY, HAFIZ, GRACE, PUB, ST, links=L), CV.NOT_FREE.format(name=HAFIZ))
        assert [p["name"] for p in PK.shortlist(PUB, ST, AB.all_records(), *_cov(i, DKEY), links=L)] == [BEN]
        assert FL.run(ids=[i], now=DEC) == dict(picked=1, nobody=0) and _cov(i, DKEY)[2]["relief"] == BEN
        _clear(); _exam(duty_names=(BEN,))          # now Ben is on duty: his waiting pick is dropped and picked again
        assert CV.stale(PUB, ST, AB.all_records(), *_cov(i, DKEY), links=_links()) is True
        assert FL.run(ids=[i], now=DEC)["picked"] == 1
        c = _cov(i, DKEY)[2]
        assert c["relief"] not in (None, BEN) and ("dropped", BEN, "app") in _hist(c), c
        _clear()
        who = HAFIZ                                 # free then with or without the exam, so only the duty can flag them
        CV.change(i, DKEY, who, GRACE, PUB, ST, links=_links())
        row = next(v for v in ok(_relief_team().get("/api/relief/today?date=" + ISO))["rows"] if v["ckey"] == DKEY)
        assert row["stale"] is False and row["warn"] is None, row
        _exam(duty_names=(who,))                    # an approved relief stays, flagged on Today
        FL.run(ids=[i], now=DEC)
        assert _cov(i, DKEY)[2]["relief"] == who and CV.state(*_cov(i, DKEY)) == "approved"
        row = next(v for v in ok(_relief_team().get("/api/relief/today?date=" + ISO))["rows"] if v["ckey"] == DKEY)
        assert row["stale"] is True and row["warn"] == who + " is no longer free then: change it", row
        free = ok(_relief_team().get("/api/relief/absences/%s/covers/%s/free" % (i, urllib.parse.quote(DKEY))))
        assert dict(name=who, why="Invigilating: " + EXAM) in free["busy"], free["busy"]
        url = "/api/relief/absences/%s/covers/%s" % (i, urllib.parse.quote(DKEY))
        raises_to = _relief_team().put(url + "/relief", json=dict(relief=who))
        assert raises_to.status_code == 400 and raises_to.get_json()["error"] == CV.NOT_FREE.format(name=who)
        j = _plan(GRACE, periods=[9, 10])["id"]     # 4A English: a waiting pick of someone then put on a duty is not approved
        ekey = RL.key_of(M, 6, MON, "Odd Mon")
        CV.set_pick(j, ekey, _pk(CHLOE), PUB, ST)
        s = SC.load(SC.on_site()[0]["id"]); s["made"]["duties"] += [dict(date=ISO, start=640, end=700, room="3-02", names=[CHLOE])]; _approve(s)
        no = CV.NOT_FREE.format(name=CHLOE)
        r = _relief_team().post("/api/relief/absences/%s/covers/%s/approve" % (j, urllib.parse.quote(ekey)), json=dict(who=CHLOE))
        assert r.status_code == 400 and r.get_json()["error"] == no, r.get_json()
        r = ok(_relief_team().post("/api/relief/today/approve-all", json=dict(date=ISO, covers=[dict(id=j, ckey=ekey, who=CHLOE)])))
        assert r["approved"] == 0 and r["skipped"][0]["why"] == no, r

@t
def fill_works_when_the_exams_cannot_be_read():
    _fresh()
    with published(PUB):
        i = _plan(DANIEL)["id"]
        old = RL.Links.load
        def broken(pub, cal): raise ValueError("the schedules cannot be read")
        RL.Links.load = broken
        import logging
        seen = []
        class H_(logging.Handler):
            def emit(self, rec): seen.append(rec.getMessage())
        h = H_(); logging.getLogger("relief.fill").addHandler(h)
        try: got = FL.run(ids=[i], now=DEC)
        finally:
            RL.Links.load = old; logging.getLogger("relief.fill").removeHandler(h)
        assert got["picked"] == 1, got
        assert len([m for m in seen if "exams" in m]) == 1 and "cannot be read" not in " ".join(seen), seen

@t
def own_absence_takes_over_the_whole_cover():
    _fresh()
    with published(PUB):
        id = _made_exam([_duty([DANIEL])])["id"]
        _send_approve(committee(), id)
        b = _backups(id)[0]["id"]
        CV.set_pick(b, DKEY, _pk(CHLOE), PUB, ST, links=_links())
        CV.approve(b, DKEY, CHLOE, GRACE, PUB, ST, links=_links())
        CV.acknowledge(b, DKEY, CHLOE)
        was = _cov(b, DKEY)[2]
        r = AB.new(dict(teacher=DANIEL, dates=[ISO], reason="Medical", reporting_officer=GRACE, lessons=[]), PUB, DANIEL, "asked", links=_links())
        rec, x, c = _cov(r["id"], DKEY)
        assert CV.state(rec, x, c) == "acknowledged", c
        assert {k: c.get(k) for k in AB.COVER} == {k: was.get(k) for k in AB.COVER}, c
        assert AB.load(b)["cancelled"] and AB.load(b)["lessons"] == []
        FL.run(ids=[r["id"]], now=DEC)
        assert _cov(r["id"], DKEY)[2]["relief"] == CHLOE
        mine = ok(staff(CHLOE).get("/api/relief/covering"))["covers"]
        assert [(v["id"], v["ckey"], v["state"]) for v in mine] == [(r["id"], DKEY, "acknowledged")], mine

@t
def own_absence_takes_over_a_split_lesson_and_a_planners_pick():
    _fresh()
    with published(PUB):
        id = _made_exam([_duty([DANIEL])])["id"]
        _send_approve(committee(), id)
        b = _backups(id)[0]["id"]
        CV.split(b, DKEY, 2, GRACE)
        CV.set_pick(b, DKEY + "#0", _pk(CHLOE), PUB, ST, links=_links())
        CV.approve(b, DKEY + "#0", CHLOE, GRACE, PUB, ST, links=_links())
        raises(ValueError, lambda: _plan(DANIEL, DKEY, BEN, links=_links()), "4A Mathematics: this lesson is split: the relief team chooses for each part.")
        assert len(AB.all_records()) == 1 and AB.load(b)["cancelled"] is None, "a refused absence changes nothing"
        r = _plan(DANIEL, links=_links())
        rec, x, c = _cov(r["id"], DKEY + "#0")
        assert CV.state(rec, x, c) == "approved" and c["relief"] == CHLOE and CV.state(*_cov(r["id"], DKEY + "#1")) == "open"
        _fresh()
        id = _made_exam([_duty([DANIEL])])["id"]
        _send_approve(committee(), id)
        b = _backups(id)[0]["id"]
        AB.choose(b, DKEY, CHLOE, GRACE, PUB, links=_links())       # a planner's pick, still waiting
        r = _plan(DANIEL, DKEY, BEN, links=_links())                # another planner's choice on the new absence replaces it
        c = _cov(r["id"], DKEY)[2]
        assert c["relief"] == BEN and CV.state(*_cov(r["id"], DKEY)) == "waiting" and CV.pick_of(rec, c)["who"] == BEN
        assert _hist(c) == [("pick", CHLOE, "planner"), ("dropped", CHLOE, GRACE)], c["history"]
        for who, want in ((None, [("pick", CHLOE, "planner")]), (CHLOE, [("pick", CHLOE, "planner")]), (BEN, [("pick", CHLOE, "planner"), ("dropped", CHLOE, GRACE)])):
            _fresh()
            id = _made_exam([_duty([DANIEL])])["id"]
            _send_approve(committee(), id)
            o = _backups(id)[0]
            o["lessons"][0].update(relief=CHLOE, relief_by="Mr Planner"); o["at"] = "2026-11-02T09:00:00+08:00"     # relief stage 2's shape: no pick
            _put(o)
            r = _plan(DANIEL, DKEY, who, links=_links())
            c = _cov(r["id"], DKEY)[2]
            assert _hist(c) == want and c["history"][0]["why"] == "Planned by Mr Planner on Mon 2 Nov.", (who, c["history"])
            assert c["relief"] == (who or CHLOE) and c["relief_by"] == (GRACE if who else "Mr Planner"), c
        _fresh()
        id = _made_exam([_duty([DANIEL])])["id"]
        _send_approve(committee(), id)
        b = _backups(id)[0]["id"]
        CV.split(b, DKEY, 2, GRACE)
        CV.change(b, DKEY + "#0", CHLOE, GRACE, PUB, ST, links=_links())
        raises(ValueError, lambda: _plan(DANIEL, DKEY, CHLOE, links=_links()), "4A Mathematics: this lesson is split: the relief team chooses for each part.")

@t
def an_approved_relief_is_not_replaced_by_a_new_absence():
    _fresh()
    with published(PUB):
        id = _made_exam([_duty([DANIEL])])["id"]
        _send_approve(committee(), id)
        b = _backups(id)[0]["id"]
        CV.change(b, DKEY, CHLOE, GRACE, PUB, ST, links=_links())
        raises(ValueError, lambda: _plan(DANIEL, DKEY, BEN, links=_links()),
               "4A Mathematics: this lesson's relief is approved already: ask the relief team to change it.")
        assert len(AB.all_records()) == 1 and AB.load(b)["cancelled"] is None
        r = _plan(DANIEL, DKEY, CHLOE, links=_links())              # the same person: the approval stands
        assert CV.state(*_cov(r["id"], DKEY)) == "approved" and _cov(r["id"], DKEY)[2]["pick"]["by"] == "team"

@t
def a_taken_over_lesson_that_needs_no_relief_ends_its_cover():
    _fresh()
    with published(PUB):
        id = _made_exam([_duty([DANIEL])])["id"]
        _send_approve(committee(), id)
        b = _backups(id)[0]["id"]
        CV.change(b, DKEY, CHLOE, GRACE, PUB, ST, links=_links())
        M["lessons"].append(F._lesson(10, 0, 4, 1, "Sec 4", ["4A"], "Mathematics", "Entire Class", [DANIEL], "4-01"))
        try:
            r = AB.new(dict(teacher=DANIEL, dates=[ISO], reason="Medical", reporting_officer=GRACE, lessons=[dict(key=DKEY, needed=False)]), PUB, DANIEL, "asked",
                       links=_links())
        finally: M["lessons"].pop()
        x = next(x for x in r["lessons"] if x["key"] == DKEY)
        assert x["needed"] is False and x["relief"] is None and not x.get("approved"), x
        assert _hist(x)[-1] == ("dropped", CHLOE, DANIEL) and x["history"][-1]["why"] == "Not needed", x["history"]
        assert CV.state(*_cov(r["id"], DKEY)) == "cancelled"
        assert ok(staff(CHLOE).get("/api/relief/covering"))["covers"] == []

@t
def a_lesson_that_leaves_a_backup_is_kept_in_gone():
    _fresh()
    with published(PUB):
        c = committee()
        id = _made_exam(_two_duties())["id"]
        _send_approve(c, id)
        b = _backups(id)[0]["id"]
        by = {x["subject"]: x["key"] for x in AB.load(b)["lessons"]}
        CV.change(b, by["PE"], BEN, GRACE, PUB, ST, links=_links())
        AB.set_work(b, by["PE"], dict(text="Run", link="", files=[], known=[]), HAFIZ)
        ok(c.post(f"/api/exams/{id}/handled", json=dict(teacher=HAFIZ, key=by["PE"], handled=True)))
        r = AB.load(b)
        assert [x["subject"] for x in r["lessons"]] == ["Assembly"] and r["cancelled"] is None, r
        g = r["gone"]
        assert [(x["key"], x["relief"], x.get("approved"), x["gone"]["why"]) for x in g] == [(by["PE"], None, None, "Handled by the exams committee.")], g
        assert _hist(g[0])[-1] == ("dropped", BEN, "app") and g[0]["history"][-1]["why"] == "Handled by the exams committee." and "work" not in g[0], g[0]
        assert FR.relief_periods(AB.all_records(), BEN, {MON}) == 0 and ok(staff(BEN).get("/api/relief/covering"))["covers"] == []
        ok(c.post(f"/api/exams/{id}/withdraw"))
        r = AB.load(b)
        assert r["cancelled"]["why"] == "The schedule was withdrawn." and r["lessons"] == [] and [x["subject"] for x in r["gone"]] == ["PE"], \
            "a lesson with no relief and no history leaves nothing behind"

@t
def the_exams_side_sees_approved_reliefs_only():
    _fresh()
    with published(PUB):
        id = _made_exam([_duty([DANIEL])])["id"]
        c = committee()
        _send_approve(c, id)
        b = _backups(id)[0]["id"]
        item = lambda: next(x for x in ok(c.get(f"/api/exams/{id}/view"))["lessons"]["backup"] if x["key"] == DKEY)
        CV.set_pick(b, DKEY, _pk(CHLOE), PUB, ST, links=_links())
        assert RL.relief_busies(M, AB.all_records()) == [], "a pick still waiting is relief's to make again"
        assert (item()["state"], item()["relief"]) == ("sent", None), item()
        CV.approve(b, DKEY, CHLOE, GRACE, PUB, ST, links=_links())
        bnds = D.bounds(M)
        assert [(x["names"], x["start"], x["end"], x["why"]) for x in RL.relief_busies(M, AB.all_records())] == \
            [([CHLOE], bnds[1][0], bnds[2][1], "covers relief then (4A Mathematics)")]
        assert (item()["state"], item()["relief"]) == ("relief", CHLOE), item()
        CV.ask_change(b, DKEY, "A meeting", CHLOE)
        assert len(RL.relief_busies(M, AB.all_records())) == 1, "until the team acts the relief stays"
        _fresh()
        id = _made_exam([_duty([DANIEL])])["id"]
        _send_approve(c, id)
        b = _backups(id)[0]["id"]
        CV.split(b, DKEY, 2, GRACE)
        CV.change(b, DKEY + "#0", CHLOE, GRACE, PUB, ST, links=_links())
        assert (item()["state"], item()["relief"]) == ("sent", None), "a part is still open"
        CV.change(b, DKEY + "#1", BEN, GRACE, PUB, ST, links=_links())
        assert (item()["state"], item()["relief"]) == ("relief", BEN + " and " + CHLOE), item()
        _fresh()
        b = _plan(DANIEL)["id"]
        CV.split(b, DKEY, 2, GRACE)
        CV.change(b, DKEY + "#1", BEN, GRACE, PUB, ST)
        assert [(x["names"], x["start"], x["end"]) for x in RL.relief_busies(M, AB.all_records()) if "covers" in x["why"]] == [([BEN], bnds[2][0], bnds[2][1])]
        assert RL.relief_busies(M, [dict(AB.load(b), lessons=[dict(AB.load(b)["lessons"][0], parts="x")])])[0]["why"] == "is away then (relief)"

@t
def a_relief_the_exam_itself_stops_holds_nobody():
    _fresh()
    with published(PUB):
        i = _plan(CHLOE)["id"]
        CV.change(i, CKEY, HAFIZ, GRACE, PUB, ST)
        covers = lambda busy: [b["names"] for b in busy if b["why"].startswith("covers relief")]
        e = _made_exam([])                              # a Sec 3 exam being set up: 3B's lesson stops for it
        assert covers(RL.relief_busies(M, AB.all_records())) == [[HAFIZ]]
        assert covers(SC.elsewhere(e["id"], M)) == [], "this schedule stops the lesson"
        assert covers(SC.elsewhere("x", M)) == [[HAFIZ]], "another schedule does not, while this one is not approved"
        _approve(SC.load(e["id"]))
        assert covers(SC.elsewhere("x", M)) == [], "an approved schedule stops it for everyone"
        s = SC.load(e["id"]); s["days"] = {ISO: dict(levels=[], whole=True)}; s["classes"] = ["3A"]; s["status"] = "changes"
        SC.save(s, PUB, CAL, GRACE, check=False)
        assert covers(SC.elsewhere(e["id"], M)) == [[HAFIZ]], "its working copy no longer stops 3B: its own approved copy does not count"
        assert covers(SC.elsewhere(e["id"], M, own=AP.as_schedule(SC.load(e["id"])))) == [], "replacing someone on the approved copy"
        assert covers(SC.elsewhere("x", M)) == [], "for others the approved copy still stops it"
        n = []
        old = SC.on_site
        SC.on_site = lambda: n.append(1) or old()
        try:
            SC.elsewhere("x", M); assert len(n) == 1
            AB.cancel(i, "x", GRACE); SC.elsewhere("x", M); assert len(n) == 1, "with nobody approved the schedules are not read"
        finally: SC.on_site = old

@t
def todays_page_and_the_lists_show_a_stopped_lesson():
    _fresh()
    with published(PUB):
        i = _plan(CHLOE)["id"]
        CV.change(i, CKEY, HAFIZ, GRACE, PUB, ST)
        j = _plan(DANIEL)["id"]
        team = _relief_team()
        got = ok(team.get("/api/relief/today?date=" + ISO))
        assert (got["counts"]["need"], got["counts"]["approved"], got["counts"]["unsent"], got["counts"]["open"]) == (2, 0, 1, 1), got["counts"]   # approved, not sent out
        _exam(duty_names=(IVAN,))
        got = ok(team.get("/api/relief/today?date=" + ISO))
        row = next(v for v in got["rows"] if v["ckey"] == CKEY)
        assert row["state"] == "stopped" and row["stopped"] == STOP and row["pick"]["who"] == HAFIZ and row["warn"] is None, row
        assert (got["counts"]["need"], got["counts"]["approved"], got["counts"]["open"]) == (1, 0, 1), got["counts"]
        assert next(v for v in got["rows"] if v["ckey"] == DKEY)["stopped"] == ""
        r = team.post("/api/relief/absences/%s/covers/%s/approve" % (i, urllib.parse.quote(CKEY)), json=dict(who=HAFIZ))
        assert r.status_code == 400 and r.get_json()["error"] == NOT_ON, r.get_json()
        free = team.get("/api/relief/absences/%s/covers/%s/free" % (i, urllib.parse.quote(CKEY)))
        assert free.status_code == 400 and free.get_json()["error"] == NOT_ON, free.get_json()
        mine = ok(staff(HAFIZ).get("/api/relief/covering"))["covers"]
        assert [(v["ckey"], v["state"], v["stopped"]) for v in mine] == [(CKEY, "approved", STOP)], mine
        rows = {r["id"]: r for r in ok(team.get("/api/relief/absences"))["absences"]}
        assert rows[i]["cover"] == dict(total=0, approved=0, waiting=0, open=0), rows[i]["cover"]
        assert rows[j]["cover"]["total"] == 1 and rows[j]["cover"]["open"] == 1
        sheet = team.get("/api/relief/planned.csv?start=" + ISO).get_data(as_text=True)
        line = next(l for l in sheet.splitlines() if "3B" in l)
        assert "Not happening: " + STOP in line and HAFIZ not in line, line

@t
def today_says_who_is_on_a_duty():
    _fresh()
    with published(PUB):
        id = _made_exam([_duty([DANIEL])])["id"]
        _send_approve(committee(), id)
        _plan(HAFIZ)
        rows = {v["ckey"]: v for v in ok(_relief_team().get("/api/relief/today?date=" + ISO))["rows"]}
        assert rows[DKEY]["duty"] == "Invigilating: " + EXAM and rows[PEKEY]["duty"] == "", rows

@t
def load_and_the_ai_count_exam_duties():
    _fresh()
    with published(PUB):
        team = _relief_team()
        rows = lambda: {v["name"]: v for v in ok(team.get("/api/relief/load?week=" + ISO))["rows"]}
        before = rows()
        assert before[BEN]["exams"] == 0 and before[BEN]["week"] == before[BEN]["teaching"] + before[BEN]["relief"]
        _exam(duty_names=(BEN, IVAN))
        L, week = _links(), FR._week_dates(CAL, M["days"], MON)
        now = rows()
        assert now[BEN]["exams"] == L.week_change(BEN, week) == 5 - 3 and now[BEN]["teaching"] == before[BEN]["teaching"]
        assert now[BEN]["week"] == now[BEN]["teaching"] + now[BEN]["relief"] + 2, now[BEN]
        assert now[CHLOE]["exams"] == -2 and now[CHLOE]["week"] == 0, "her only lesson that week stops"
        k = _plan(CHLOE)["id"]
        CV.change(k, CKEY, HAFIZ, GRACE, PUB, ST)           # (no links: as it was chosen before the exam)
        hafiz = rows()[HAFIZ]
        assert (hafiz["relief"], hafiz["term"]) == (0, 0), hafiz
        one = ok(team.get("/api/relief/load/%s?week=%s" % (urllib.parse.quote(HAFIZ), ISO)))["reliefs"]
        assert [(v["ckey"], v["state"]) for v in one] == [(CKEY, "not happening")], one
        AB.cancel(k, "x", GRACE)
        csv_ = team.get("/api/relief/load.csv?week=" + ISO).get_data(as_text=True)
        head = csv_.lstrip("\ufeff").splitlines()[0]
        assert "Exams and events" in head, head
        cells = next(l for l in csv_.splitlines() if l.startswith(BEN)).split(",")
        assert cells[head.split(",").index("Exams and events this week")] == "2", cells
        i = _plan(HAFIZ)["id"]                          # 4A PE, periods 5-6 (09:00-09:40): Ben's duty ends at 09:10, so he is out
        short = {p["name"]: p for p in PK.shortlist(PUB, ST, AB.all_records(), *_cov(i, PEKEY), links=L)}
        plain = {p["name"]: p for p in PK.shortlist(PUB, ST, AB.all_records(), *_cov(i, PEKEY))}
        assert BEN not in short and BEN in plain and short[CHLOE]["teaching"] == plain[CHLOE]["teaching"] - 2 == 0, (short, plain)

@t
def a_load_row_for_duties_alone():
    _fresh()
    with published(PUB):
        M["lessons"][9]["teachers"] = [CHLOE]           # Ivan teaches nothing that week
        try:
            _exam(duty_names=(IVAN,))
            rows = {v["name"]: v for v in ok(_relief_team().get("/api/relief/load?week=" + ISO))["rows"]}
            assert rows[IVAN]["teaching"] == 0 and rows[IVAN]["exams"] == 5 and rows[IVAN]["week"] == 5, rows.get(IVAN)
        finally: M["lessons"][9]["teachers"] = [IVAN]

@t
def relief_team_pages_work_when_the_exams_cannot_be_read():
    _fresh()
    with published(PUB):
        i = _plan(DANIEL)["id"]
        old = RL.Links.load
        def broken(pub, cal): raise ValueError("no")
        RL.Links.load = broken
        A.app.logger.disabled = True
        try:
            team = _relief_team()
            for u in ("/api/relief/today?date=" + ISO, "/api/relief/load?week=" + ISO, "/api/relief/covering", "/api/relief/absences",
                      "/api/relief/planned.csv?start=" + ISO):
                r = team.get(u)
                assert r.status_code == 200, (u, r.status_code)
            j = ok(team.get("/api/relief/lessons?dates=%s&teacher=%s" % (ISO, urllib.parse.quote(HAFIZ))))
            assert [x["stopped"] for x in j["lessons"]] == ["", ""] and j["duties"] == {ISO: []}, j
            ok(team.get("/api/relief/free?absent=%s&key=%s" % (urllib.parse.quote(DANIEL), urllib.parse.quote(DKEY))))
            ok(team.put("/api/relief/absences/%s/lessons/%s/relief" % (i, urllib.parse.quote(DKEY)), json=dict(relief=BEN)))
            ok(team.put("/api/relief/absences/%s/covers/%s/relief" % (i, urllib.parse.quote(DKEY)), json=dict(relief=BEN)))
            ok(staff(HAFIZ).post("/api/relief/absences", json=dict(dates=[ISO], reason="Medical", reporting_officer=GRACE, lessons=[])))
        finally:
            RL.Links.load = old; A.app.logger.disabled = False
        e = _exam(duty_names=(BEN,))                    # an approved copy that cannot be used
        s = SC.load(e["id"]); s["approved"]["days"] = {ISO: "x"}; SC.save(s, PUB, CAL, GRACE, check=False)
        old_log, RL.logger.disabled = RL.logger.disabled, True
        try:
            for u in ("/api/relief/today?date=" + ISO, "/api/relief/load?week=" + ISO, "/api/relief/planned.csv?start=" + ISO):
                assert team.get(u).status_code == 200, u
            FL.run(ids=[i], now=DEC)
        finally: RL.logger.disabled = old_log

@t
def a_links_date_with_no_schedule_reads_nothing():
    _clear(); _exam(duty_names=(BEN,))
    L = _links()
    old, seen = D.merged_view, []
    def spy(*a): seen.append(a[-1]); return old(*a)
    D.merged_view = spy
    try:
        assert L.stopped(dict(key="k", date="2027-02-01")) == "" and L.busy(BEN, "2027-02-01", 0, 1) == ""
        assert seen == [], "a date no approved schedule holds costs nothing"
        assert L.stopped(dict(key=CKEY, date=ISO)) == STOP and seen == [ISO]
    finally: D.merged_view = old
    s = SC.load(SC.on_site()[0]["id"]); s["made"]["duties"][0]["date"] = "2027-01-18"; _approve(s)      # a duty outside the schedule's own dates
    L = _links()
    assert L.busy(BEN, "2027-01-18", 0, 1) == "Invigilating: " + EXAM and L.duties(BEN, "2027-01-18")
    assert L.week_change(BEN, [date(2027, 1, 18)]) == L.week_change(BEN, [date(2027, 1, 18)]) == 5

@t
def the_pages_show_not_happening_and_duties():
    js = {f: open(os.path.join(ROOT, "static", f), encoding="utf-8").read() for f in ("relief-today.js", "relief-covering.js", "relief-load.js", "relief-plan.js")}
    assert 'case "stopped"' in js["relief-today.js"] and "Not happening" in js["relief-today.js"] and "r.duty" in js["relief-today.js"]
    assert "pl-duty" in js["relief-today.js"] and "c.stopped" in js["relief-covering.js"]
    assert "Exams and events" in js["relief-load.js"] and "busy_open" not in js["relief-plan.js"]

@t
def what_left_a_backup_is_sent_to_nobody():
    _fresh()
    with published(PUB):
        c = committee()
        id = _made_exam(_two_duties())["id"]
        _send_approve(c, id)
        b = _backups(id)[0]["id"]
        pe = {x["subject"]: x["key"] for x in AB.load(b)["lessons"]}["PE"]
        CV.set_pick(b, pe, dict(_pk(BEN, "ai"), reason="Rule 3 says so."), PUB, ST, links=_links())
        ok(c.post(f"/api/exams/{id}/handled", json=dict(teacher=HAFIZ, key=pe, handled=True)))
        assert AB.load(b)["gone"], "kept"
        for who, u in ((HAFIZ, "/api/relief/absences/mine"), (HAFIZ, "/api/relief/absences/" + b), (GRACE, "/api/relief/absences"),
                       (GRACE, "/api/relief/absences/" + b)):
            text = json.dumps(ok(staff(who).get(u)))
            assert "gone" not in text and "Rule 3" not in text and "Because" not in text, (who, u)
        text = json.dumps(ok(staff(HAFIZ).get("/api/relief/absences/mine")))
        assert BEN not in text

@t
def replacing_someone_on_an_approved_exam_sees_the_approved_copy():
    _fresh()
    with published(PUB):
        c = committee()
        i = _plan(DANIEL)["id"]
        CV.change(i, DKEY, BEN, GRACE, PUB, ST)             # Ben is approved to cover Daniel's 4A Mathematics: a Sec 3 exam does not stop it
        e = _made_exam([_duty([AISHA])]); id = e["id"]
        _send_approve(c, id)
        s = SC.load(id); s["levels"] = ["Sec 3", "Sec 4"]; s["days"] = {ISO: dict(levels=["Sec 3", "Sec 4"], whole=True)}      # an edit not sent
        SC.save(s, PUB, CAL, GRACE, check=False)
        assert SC.load(id)["approved"]["days"][ISO]["levels"] == ["Sec 3"]
        r = c.post(f"/api/exams/{id}/away", json=dict(key=DUTY_KEY, room="3-01", away=AISHA, name=BEN))
        assert r.status_code == 400 and "not free" in r.get_json()["error"], r.get_json()
        assert SC.load(id)["approved"]["made"]["duties"][0]["names"] == [AISHA]
        s = SC.load(id); s["made"]["duties"][0]["names"] = [BEN]; s["approved"]["made"]["duties"][0]["names"] = [BEN]
        SC.save(s, PUB, CAL, GRACE, check=False)            # Ben on the live duty and on a relief that runs
        rv = ok(c.get(f"/api/exams/{id}/review"))["review"]
        assert rv["copy"] == "approved" and "covers relief then (4A Mathematics)" in json.dumps(rv["checks"]), rv["checks"]

@t
def an_event_that_stops_a_lesson_frees_its_relief():
    _fresh()
    with published(PUB):
        c = committee()
        i = _plan(DANIEL)["id"]
        CV.change(i, DKEY, HAFIZ, GRACE, PUB, ST)
        ev = SC.new_event(EVENT, [], ["4A"], ISO, ISO, GRACE, GRACE)
        ev["days"] = {ISO: dict(whole=False, **{"from": "07:40", "to": "09:00"})}; ev["going"] = [HAFIZ]
        ev = SC.save(ev, PUB, CAL, GRACE, check=False)
        others, busy = A._event_others(PUB, ev)
        assert not any(b["why"].startswith("covers relief") for b in busy if b.get("why")), busy
        ev["days"] = {ISO: dict(whole=False, **{"from": "10:00", "to": "11:00"})}
        others, busy = A._event_others(PUB, ev)
        assert [b["names"] for b in busy if b.get("why", "").startswith("covers relief")] == [[HAFIZ]], "the copy worked on, not the saved one"
        # an approved event with an unsent edit: its review and replacing someone going read the approved copy, Send the edit
        _approve(SC.load(ev["id"]))
        s = SC.load(ev["id"]); s["days"] = {ISO: dict(whole=False, **{"from": "10:00", "to": "11:00"})}; SC.save(s, PUB, CAL, GRACE, check=False)
        rv = ok(c.get("/api/events/%s/review" % ev["id"]))["review"]
        going = next(x for x in rv["checks"] if x["key"] == "going")
        assert rv["copy"] == "approved" and going["ok"], going
        s["going"] = [BEN]; s["days"] = {ISO: dict(whole=False, **{"from": "08:00", "to": "08:40"})}; s = _approve(s)
        SC.save(dict(SC.load(s["id"]), days={ISO: dict(whole=False, **{"from": "10:00", "to": "11:00"})}), PUB, CAL, GRACE, check=False)
        free = A._event_free(PUB, SC.load(s["id"]))
        assert HAFIZ in [x["name"] for g in ("freed", "free") for x in free[g]], "the approved copy stops the lesson he covers"

@t
def whats_in_leaves_out_a_stopped_lesson_after_its_date_too():
    _fresh()
    old = LS.today
    with published(PUB):
        i = _plan(CHLOE)["id"]
        _exam(duty_names=(IVAN,))
        r = AB.load(i); r["dates"] = [ISO, "2027-01-05"]; _put(r)            # still coming up the next day
        LS.today = lambda: date(2027, 1, 5)
        try: rows = {r["id"]: r for r in ok(_relief_team().get("/api/relief/absences"))["absences"]}
        finally: LS.today = old
        assert rows[i]["cover"] == dict(total=0, approved=0, waiting=0, open=0), rows[i]["cover"]
        assert rows[i]["lessons"][0]["stopped"] == STOP, "the pages say so after its date too"

@t
def a_request_to_changes_new_pick_on_a_duty_is_picked_again():
    _fresh()
    with published(PUB):
        i = _plan(DANIEL)["id"]
        CV.change(i, DKEY, HAFIZ, GRACE, PUB, ST)
        CV.ask_change(i, DKEY, "A meeting", HAFIZ)
        CV.set_pick(i, DKEY, _pk(BEN), PUB, ST, into="change")
        _exam(duty_names=(BEN,))
        assert CV.stale(PUB, ST, AB.all_records(), *_cov(i, DKEY), into="change", links=_links()) is True
        assert FL.run(ids=[i], now=DEC)["picked"] == 1
        new = CV.new_pick(_cov(i, DKEY)[2])
        assert new and new["who"] not in (BEN, HAFIZ), new

@t
def the_shortlist_leaves_out_reliefs_of_stopped_lessons():
    _fresh()
    with published(PUB):
        k = _plan(CHLOE)["id"]
        CV.change(k, CKEY, HAFIZ, GRACE, PUB, ST)
        i = _plan(GRACE, periods=[9, 10])["id"]
        ekey = RL.key_of(M, 6, MON, "Odd Mon")
        hafiz = lambda **kw: next(p for p in PK.shortlist(PUB, ST, AB.all_records(), *_cov(i, ekey), **kw) if p["name"] == HAFIZ)
        assert (hafiz()["week_relief"], hafiz()["today_at"]) == (2, [(0, 2)])
        _exam(duty_names=(IVAN,))
        got = hafiz(links=_links())
        assert (got["week_relief"], got["today_at"], got["by_day"]["Mon"]) == (0, [], 0), got

@t
def the_pages_offer_nothing_for_a_stopped_lesson():
    js = {f: open(os.path.join(ROOT, "static", f), encoding="utf-8").read() for f in ("relief.js", "relief-plan.js", "relief-inbox.js", "relief-today.js")}
    assert "!x.changed && !x.stopped && x.date" in js["relief-plan.js"] and "x.needed && !x.stopped && !r.cancelled" in js["relief.js"]
    assert "x.needed && !x.stopped)" in js["relief-inbox.js"] and 'r.state !== "cancelled" && r.state !== "stopped"; };' in js["relief-today.js"]

@t
def a_stopped_lesson_is_not_split_or_joined_by_the_team():
    _fresh()
    with published(PUB):
        i, j = _plan(CHLOE)["id"], _plan(AISHA)["id"]
        AKEY = RL.key_of(M, 0, MON, "Odd Mon")
        CV.split(i, CKEY, 1, GRACE)
        CV.set_pick(i, CKEY + "#0", _pk(HAFIZ), PUB, ST)
        _exam(duty_names=(IVAN,))
        raises(ValueError, lambda: CV.join(i, CKEY, GRACE, links=_links()), NOT_ON)
        team, q = _relief_team(), lambda id, key, what: "/api/relief/absences/%s/lessons/%s/%s" % (id, urllib.parse.quote(key), what)
        for r in (team.post(q(i, CKEY, "join"), json={}), team.post(q(j, AKEY, "split"), json=dict(at=1))):
            assert r.status_code == 400 and r.get_json()["error"].startswith("This lesson is not happening: "), r.get_json()
        assert _cov(i, CKEY + "#0")[2]["relief"] == HAFIZ and not AB.load(j)["lessons"][0].get("parts")

@t
def a_lesson_not_needed_is_not_refused_for_its_choice():
    _fresh()
    with published(PUB):
        id = _made_exam([_duty([DANIEL])])["id"]
        _send_approve(committee(), id)
        CV.change(_backups(id)[0]["id"], DKEY, CHLOE, GRACE, PUB, ST, links=_links())
        r = AB.new(dict(teacher=DANIEL, dates=[ISO], reason="Other", reason_text="A course", lessons=[dict(key=DKEY, needed=False, relief=BEN)]), PUB, GRACE,
                   "planned", may_choose=True, links=_links())
        assert r["lessons"][0]["needed"] is False and r["lessons"][0]["relief"] is None

@t
def a_co_teacher_on_a_duty_is_not_there():
    _fresh()
    M["lessons"][2]["teachers"] = [DANIEL, CHLOE]           # a 4A Mathematics lesson both teach
    try:
        with published(PUB):
            c = committee()
            _made_exam([_duty([CHLOE])]); e = SC.all_saved()[0]["id"]; _send_approve(c, e)
            assert _plan(DANIEL, links=_links())["lessons"][0]["needed"] is True, "Chloe is on a duty: she is not there"
            x = ok(_relief_team().get("/api/relief/lessons?dates=%s&teacher=%s" % (ISO, urllib.parse.quote(DANIEL))))["lessons"][0]
            assert x["others"] == [], x
            _fresh()
            id = _made_exam([_duty([DANIEL, CHLOE])])["id"]; _send_approve(c, id)
            got = {r["teacher"]: r["lessons"][0]["needed"] for r in _backups(id)}
            assert got == {DANIEL: True, CHLOE: True}, "both are on a duty: neither is there for the other"
    finally: M["lessons"][2]["teachers"] = [DANIEL]

@t
def the_free_list_shows_the_week_with_duties():
    _fresh(); _exam(duty_names=(BEN,))
    L = _links()
    got = FR.free_then(PUB, SETTINGS, [], _need(9), DANIEL, links=L)
    ben = next(x for g in got["groups"] for x in g["people"] if x["name"] == BEN)
    assert ben["week"] == FR.week_so_far(PUB, CAL, [], BEN, MON, links=L) != FR.week_so_far(PUB, CAL, [], BEN, MON), ben

@t
def schedules_that_cannot_be_read_are_not_taken_as_none():
    _fresh()
    with published(PUB):
        i = _plan(DANIEL)["id"]
        CV.change(i, DKEY, HAFIZ, GRACE, PUB, ST)
        def broken(): raise KeyError("status")
        raises(KeyError, lambda: RL.relief_busies(M, AB.all_records(), broken))
        assert [b["names"] for b in RL.relief_busies(M, AB.all_records(), [dict(id="x")]) if b["why"].startswith("covers")] == [[HAFIZ]], "one odd schedule stops nothing"

# ---- an absence sent while an exam stops a lesson, and the exam withdrawn later
def _withdraw(id):
    s = SC.load(id); s.update(status="withdrawn", approved=None); SC.save(s, PUB, CAL, GRACE, check=False)

@t
def a_lesson_stopped_when_the_absence_was_sent_is_covered_once_the_exam_is_withdrawn():
    _fresh()
    with published(PUB):
        e = _exam(duty_names=(IVAN,))
        j = ok(staff(CHLOE).post("/api/relief/absences", json=dict(dates=[ISO], reason="Medical", reporting_officer=GRACE, lessons=[])))
        x = j["lessons"][0]
        assert (x["key"], x["needed"], x["stopped"], x["not_needed"]) == (CKEY, True, STOP, None), x
        team, i = _relief_team(), j["id"]
        row = lambda: next(v for v in ok(team.get("/api/relief/today?date=" + ISO))["rows"] if v["ckey"] == CKEY)
        counts = lambda: next(r for r in ok(team.get("/api/relief/absences"))["absences"] if r["id"] == i)["cover"]
        assert row()["state"] == "stopped" and counts() == dict(total=0, approved=0, waiting=0, open=0)
        assert FL.run(ids=[i], now=DEC) == dict(picked=0, nobody=0), "nothing to pick for while it is stopped"
        _withdraw(e["id"])
        assert row()["state"] == "open" and counts()["open"] == 1, "the lesson happens: it needs a relief teacher"
        assert FL.run(ids=[i], now=DEC)["picked"] == 1

@t
def an_absence_whose_lessons_all_stop_is_taken():
    _fresh()
    with published(PUB):
        _exam(duty_names=(IVAN,))                   # Chloe's only lesson that day stops, and she has no duty
        r = staff(CHLOE).post("/api/relief/absences", json=dict(dates=[ISO], reason="Medical", reporting_officer=GRACE, lessons=[]))
        assert r.status_code == 200, r.get_json()
        busy = SC.elsewhere("x", M)
        assert [b["why"] for b in busy if b["names"] == [CHLOE] and b["id"] == "relief"] == ["is away then (relief)"], "the exams committee sees who is away"
        _fresh()
        M["lessons"][1]["teachers"] = [CHLOE, HAFIZ]            # with a co-teacher there, its lesson is not needed, and still stopped
        try:
            _exam(duty_names=(IVAN,))
            r = staff(CHLOE).post("/api/relief/absences", json=dict(dates=[ISO], reason="Medical", reporting_officer=GRACE, lessons=[]))
            assert r.status_code == 200 and r.get_json()["lessons"][0]["needed"] is False, r.get_json()
        finally: M["lessons"][1]["teachers"] = [CHLOE]
        _fresh()
        r = staff(BEN).post("/api/relief/absences", json=dict(dates=["2027-01-05"], reason="Medical", reporting_officer=GRACE, lessons=[]))
        assert r.status_code == 400 and r.get_json()["error"] == "There are no lessons to cover in that time.", "still refused with no lesson at all"

@t
def the_same_stopped_lesson_is_not_sent_twice():
    _fresh()
    with published(PUB):
        _exam(duty_names=(IVAN,))
        _plan(CHLOE, links=_links())
        r = staff(CHLOE).post("/api/relief/absences", json=dict(dates=[ISO], reason="Medical", reporting_officer=GRACE, lessons=[]))
        assert r.status_code == 400 and r.get_json()["error"] == f"{GRACE} has already sent an absence for {CHLOE} on Mon 4 Jan.", r.get_json()

@t
def a_choice_for_a_stopped_lesson_is_left_out():
    _fresh()
    with published(PUB):
        e = _exam(duty_names=(IVAN,))
        r = _plan(CHLOE, CKEY, HAFIZ, links=_links())                   # the planner's page was opened before the exam was approved
        x = r["lessons"][0]
        assert x["needed"] is True and x["relief"] is None and "_stopped" not in x and "_ask" not in x, x
        r = AB.load(r["id"])
        assert [sorted(y) for y in r["lessons"]] == [sorted(k for k in y if not k.startswith("_")) for y in r["lessons"]]
        _withdraw(e["id"])
        assert CV.state(*_cov(r["id"], CKEY)) == "open"
        _fresh(); _exam(duty_names=(IVAN,))
        r = AB.new(dict(teacher=CHLOE, dates=[ISO], reason="Medical", reporting_officer=GRACE, lessons=[dict(key=CKEY, relief=HAFIZ)]), PUB, CHLOE, "asked",
                   links=_links())
        assert r["lessons"][0]["relief"] is None, "someone who may not choose is not refused for a lesson that does not happen"

@t
def what_the_client_said_is_kept_for_a_stopped_lesson():
    _fresh()
    with published(PUB):
        _exam(duty_names=(CHLOE,))
        r = AB.new(dict(teacher=CHLOE, dates=[ISO], reason="Medical", reporting_officer=GRACE, lessons=[dict(key=CKEY, needed=False)]), PUB, CHLOE, "asked", links=_links())
        assert r["lessons"][0]["needed"] is False and r["lessons"][0]["not_needed"] == dict(by=CHLOE, why="Not needed"), r["lessons"]
        _fresh()
        M["lessons"][1]["teachers"] = [CHLOE, HAFIZ]                    # Hafiz is there
        try:
            _exam(duty_names=(CHLOE,))
            x = AB.new(dict(teacher=CHLOE, dates=[ISO], reason="Medical", reporting_officer=GRACE, lessons=[]), PUB, CHLOE, "asked", links=_links())["lessons"][0]
            assert x["needed"] is False and x["not_needed"] == dict(by="app", why=HAFIZ + " is there"), x
        finally: M["lessons"][1]["teachers"] = [CHLOE]

@t
def a_takeover_keeps_the_relief_of_a_lesson_stopped_by_then():
    _fresh()
    with published(PUB):
        id = _made_exam([_duty([DANIEL])])["id"]
        _send_approve(committee(), id)
        b = _backups(id)[0]["id"]
        CV.change(b, DKEY, CHLOE, GRACE, PUB, ST, links=_links())
        ev = _event()                                                   # saved as approved, with no sync: 4A is on it, and the backup still holds the lesson
        r = AB.new(dict(teacher=DANIEL, dates=[ISO], reason="Medical", reporting_officer=GRACE, lessons=[]), PUB, DANIEL, "asked", links=_links())
        assert r["lessons"][0]["needed"] is True and CV.state(*_cov(r["id"], DKEY)) == "approved" and _links().stopped(AB.load(r["id"])["lessons"][0])
        _withdraw(ev["id"])
        mine = ok(staff(CHLOE).get("/api/relief/covering"))["covers"]
        assert [(v["ckey"], v["state"], v["stopped"]) for v in mine] == [(DKEY, "approved", "")], "the relief stands again"
        _fresh()
        id = _made_exam([_duty([DANIEL])])["id"]
        _send_approve(committee(), id)
        CV.change(_backups(id)[0]["id"], DKEY, CHLOE, GRACE, PUB, ST, links=_links())
        _event()
        r = _plan(DANIEL, DKEY, BEN, links=_links())                    # the choice is left out, so it is not refused against the approved relief
        assert _cov(r["id"], DKEY)[2]["relief"] == CHLOE and CV.state(*_cov(r["id"], DKEY)) == "approved"

@t
def the_exams_page_says_stopped_before_sent():
    _fresh()
    with published(PUB):
        ev = _event()                                                   # 4A is on it 07:40-09:00: Daniel's 4A Mathematics stops
        _plan(DANIEL, links=_links())
        e = _exam(duty_names=(DANIEL,))
        items = [dict(teacher=DANIEL, key=DKEY, date=ISO)]
        got = RL.mark(items, SC.load(e["id"]), AB.all_records(), RL.Links(PUB, CAL, [AP.as_schedule(SC.load(ev["id"]))]), SOON)[0]
        assert got["state"] == "stopped" and got["stopped"] == "4A is on " + EVENT, got

# ---- the relief session's points: unread, the relief teacher's steps, and the words of a takeover
@t
def links_say_what_they_could_not_read():
    _fresh()
    e = _exam(duty_names=(AISHA,))
    L = RL.Links.load(PUB, CAL)
    assert not L.unread(MON) and not L.unread("2027-02-01")
    path = os.path.join(SC.DIR, "broken1.json")
    with open(path, "w", encoding="utf-8") as f: f.write("{not json")
    try:
        L = RL.Links.load(PUB, CAL)
        assert L.unread(MON) and L.unread("2027-02-01"), "its dates are not known: every date is unread"
        assert L.stopped(dict(key=CKEY, date=ISO)) == STOP, "what can be read still counts"
        assert [s["id"] for s in SC.on_site()] == [e["id"]]
    finally: os.remove(path)
    with open(path, "w", encoding="utf-8") as f: f.write('["no id"]')
    try: assert RL.Links.load(PUB, CAL).unread(MON), "not a schedule"
    finally: os.remove(path)
    lg, old_view, old_busies, old_err = RL.logger.exception, RL._days.merged_view, RL._schedules.busies, RL.logger.error
    RL.logger.exception = RL.logger.error = lambda *a, **k: None
    try:
        def no_view(*a, **k): raise KeyError("test")
        RL._days.merged_view = no_view
        L = _links()
        assert L.unread(MON) and not L.unread("2027-02-01"), "the date that could not be read, alone"
        RL._days.merged_view = old_view
        def no_busies(*a): raise KeyError("test")
        RL._schedules.busies = no_busies
        L = _links()
        assert L.unread(MON) and not L.unread("2027-02-01"), "the duties of a schedule could not be read: the dates it holds"
    finally: RL.logger.exception, RL._days.merged_view, RL._schedules.busies, RL.logger.error = lg, old_view, old_busies, old_err
    assert not RL.Links(None, CAL, []).unread(MON)
    # damage inside a schedule: it never raises, once or again, and says so
    RL.logger.exception = RL.logger.error = lambda *a, **k: None
    def hurt(f, far="2027-02-01"):
        _clear(); e = _exam(duty_names=(AISHA,)); ap = AP.as_schedule(SC.load(e["id"])); f(ap)
        L = RL.Links(PUB, CAL, [ap])
        for _ in range(2):
            L.stopped(dict(key=CKEY, date=ISO)); L.busy(AISHA, MON, 0, 1); L.duties(AISHA, MON); L.week_change(AISHA, [MON])
        return L.unread(MON), L.unread(MON), L.unread(far)
    try:
        assert hurt(lambda ap: ap.pop("name")) == (True, True, False), "the text of a stop needs the name"
        for bad in (dict(start="07:40"), dict(start=None), dict(names=[1]), dict(date="Monday")):
            assert hurt(lambda ap: ap["made"]["duties"][0].update(bad)) == (True, True, False), bad
        assert hurt(lambda ap: ap["made"]["duties"].append(dict(ap["made"]["duties"][0], start="x")))[0], "one good duty and one bad"
        for k in ("start", "end"):
            for v in ("x", None): assert hurt(lambda ap: ap.update({k: v})) == (True, True, True), (k, v)
        _clear(); e = _exam(duty_names=(AISHA,)); ap = AP.as_schedule(SC.load(e["id"]))
        ap["made"]["duties"].insert(0, dict(ap["made"]["duties"][0], names=[BEN], start=None))
        L = RL.Links(PUB, CAL, [ap])
        assert L.busy(AISHA, MON, 0, 1) == "Invigilating: " + EXAM and L.busy(BEN, MON, 0, 1) == "" and L.unread(MON), "the good duty still counts"
    finally: RL.logger.exception, RL.logger.error = lg, old_err
    _clear()
    with open(path, "w", encoding="utf-8") as f: f.write("{}")
    old = store.read_json
    def gone(p, default=None):              # deleted between the listing and the reading
        if p == path and os.path.exists(path): os.remove(path)
        return old(p, default)
    store.read_json = gone
    try: assert not RL.Links.load(PUB, CAL).unread(MON), "a file deleted meanwhile is simply gone"
    finally:
        store.read_json = old
        if os.path.exists(path): os.remove(path)

@t
def the_relief_teachers_steps_and_keep_refuse_a_stopped_lesson():
    _fresh()
    with published(PUB):
        i = _plan(CHLOE)["id"]
        CV.change(i, CKEY, HAFIZ, GRACE, PUB, ST)
        e = _exam(duty_names=(IVAN,))
        h, url = staff(HAFIZ), "/api/relief/absences/%s/covers/%s/" % (i, urllib.parse.quote(CKEY))
        for r in (h.post(url + "acknowledge", json={}), h.post(url + "ask-change", json=dict(why="A meeting"))):
            assert r.status_code == 400 and r.get_json()["error"] == NOT_ON, r.get_json()
        assert CV.state(*_cov(i, CKEY)) == "approved"
        r = staff(BEN).post(url + "acknowledge", json={})
        assert r.status_code == 403 and r.get_json()["error"] == CV.NOT_YOURS_COVER, "someone else is told nothing about it"
        _withdraw(e["id"])
        ok(h.post(url + "ask-change", json=dict(why="A meeting")))
        _approve(SC.load(e["id"]), "approved")
        r = _relief_team().post(url + "keep", json={})
        assert r.status_code == 400 and r.get_json()["error"] == NOT_ON, r.get_json()
        _withdraw(e["id"])
        ok(_relief_team().post(url + "keep", json={}))
        ok(h.post(url + "acknowledge", json={}))
        assert CV.state(*_cov(i, CKEY)) == "acknowledged"

@t
def a_cancel_by_the_app_is_not_shown_as_a_person():
    js = {f: open(os.path.join(ROOT, "static", f), encoding="utf-8").read() for f in ("relief.js", "relief-plan.js", "relief-inbox.js")}
    for f, code in (("relief.js", 'r.cancelled.by === "app" ? ""'), ("relief-plan.js", 'r.cancelled.by === "app" ? ""'), ("relief-inbox.js", 'c.by === "app" ? ""')):
        assert code in js[f], f

@t
def a_stopped_lesson_stays_stopped_when_a_publish_changes_its_key():
    _fresh()
    with published(PUB):
        _exam(duty_names=(IVAN,))
        i = _plan(CHLOE, links=_links())["id"]
        was = M["lessons"][1]["group"]
        M["lessons"][1]["group"] = "Renamed"                # a new publish: the key the absence holds is no longer on the timetable
        try:
            x = AB.load(i)["lessons"][0]
            assert x["key"] not in _links()._day(ISO)["runs"] and _links().stopped(x) == STOP
            assert FL.run(ids=[i], now=DEC) == dict(picked=0, nobody=0) and CV.state(*_cov(i, CKEY)) == "open"
            row = next(v for v in ok(_relief_team().get("/api/relief/today?date=" + ISO))["rows"] if v["ckey"] == CKEY)
            assert row["state"] == "stopped" and row["stopped"] == STOP, row
            for odd in (dict(x, p="x"), dict(x, p=None), dict(x, classes=None), dict(x, classes=[]), dict(x, p=99)): assert _links().stopped(odd) == "", odd
            assert _links().stopped(dict(x, classes=["3B", "4A"])) == "", "a class of it is not on the exam"
            assert _links().stopped(dict(x, p=20, n=1)) == STOP, "read by its own periods (a whole day)"
        finally: M["lessons"][1]["group"] = was

@t
def a_stopped_lesson_of_ones_own_takes_no_time_from_a_relief():
    _fresh()
    with published(PUB):
        i = _plan(DANIEL)["id"]                             # 4A Mathematics, periods 2-3
        CV.change(i, DKEY, CHLOE, GRACE, PUB, ST, links=RL.Links(PUB, CAL, [AP.as_schedule(_exam(duty_names=(IVAN,)))]))
        _plan(CHLOE, links=_links(), periods=[0, 0])        # away from period 1 alone; her stopped double is periods 1-2
        assert CV.stale(PUB, ST, AB.all_records(), *_cov(i, DKEY), links=_links()) is False, "she is there for period 2: the double does not happen"
        assert CHLOE in FR.there_then(AB.all_records(), [CHLOE], MON, 1, 1, links=_links())
        assert CHLOE not in FR.there_then(AB.all_records(), [CHLOE], MON, 0, 1, links=_links()), "period 1 she is away"
        _clear()
        assert CV.stale(PUB, ST, AB.all_records(), *_cov(i, DKEY), links=_links()) is True, "the exam withdrawn, the double happens, and she is away for it"

@t
def a_sync_changes_nothing_on_a_date_that_could_not_be_read():
    _fresh()
    with published(PUB):
        id = _made_exam([_duty([DANIEL, HAFIZ])])["id"]
        _send_approve(committee(), id)
        before = {r["teacher"]: (r["id"], [x["key"] for x in r["lessons"]], r["cancelled"]) for r in _backups(id)}
        assert set(before) == {DANIEL, HAFIZ}, before
        ev = SC.load(_event()["id"]); ev["approved"].pop("name"); SC.save(ev, PUB, CAL, GRACE, check=False)        # damaged: 4A's stop cannot be worded
        s = SC.load(id); s["approved"]["made"]["duties"][0]["names"] = [DANIEL, HAFIZ, GRACE]; SC.save(s, PUB, CAL, GRACE, check=False)
        RL.logger.disabled = True
        try: assert RL.sync(SC.load(id), PUB, CAL, SOON) == dict(sent=0, cancelled=0)
        finally: RL.logger.disabled = False
        assert {r["teacher"]: (r["id"], [x["key"] for x in r["lessons"]], r["cancelled"]) for r in _backups(id)} == before, "left as it is"
        SC.delete(ev["id"])
        assert RL.sync(SC.load(id), PUB, CAL, SOON)["sent"] == 1, "mended: Grace's lesson is sent"

# ---- an event's teacher in charge, changed by the timetable committee
@t
def a_new_teacher_in_charge_takes_the_events_backups():
    _fresh()
    with published(PUB):
        c = committee()
        ev = SC.new_event(EVENT, ["Sec 4"], [], ISO, ISO, BEN, BEN)
        ev["days"] = {ISO: dict(levels=["Sec 4"], whole=False, **{"from": "07:40", "to": "09:00"})}
        ev["going"] = [AISHA]
        id = SC.save(ev, PUB, CAL, BEN)["id"]
        _send_approve(c, id, "/api/events")
        b = _backups(id)[0]
        key = b["lessons"][0]["key"]
        CV.change(b["id"], key, HAFIZ, GRACE, PUB, ST, links=_links())
        AB.acknowledge(b["id"], AISHA)
        assert b["by"] == BEN and _links().duties(AISHA, MON)[0]["replaces"] == BEN + ", the teacher in charge"
        d, was = staff(DANIEL), staff(BEN)
        assert was.get(f"/api/relief/absences/{b['id']}").status_code == 200 and d.get(f"/api/relief/absences/{b['id']}").status_code == 403
        ok(c.post(f"/api/events/{id}/in-charge", json=dict(name=DANIEL)))
        now = _backups(id)
        assert [(r["id"], r["by"], [x["key"] for x in r["lessons"]], bool(r["acknowledged"])) for r in now] == [(b["id"], DANIEL, [key], True)], now
        assert CV.state(*_cov(b["id"], key)) == "approved", "what relief did on it stays"
        assert _links().duties(AISHA, MON)[0]["replaces"] == DANIEL + ", the teacher in charge"
        assert ok(d.get(f"/api/relief/absences/{b['id']}"))["by"] == DANIEL, "the new teacher in charge may open the backup"
        r = was.get(f"/api/relief/absences/{b['id']}")
        assert r.status_code == 403 and was.get(f"/api/events/{id}").status_code == 403, "the one before opens neither any more"
        ok(c.post(f"/api/events/{id}/handled", json=dict(teacher=AISHA, key=key, handled=True)))
        assert AB.load(b["id"])["cancelled"]["why"] == "Handled by the teacher in charge."
        ok(d.post(f"/api/events/{id}/handled", json=dict(teacher=AISHA, key=key, handled=False)))
        assert [r["by"] for r in _backups(id)] == [DANIEL], "sent again by the new one"


_clear()
print(f"{COUNT} exams and relief tests passed")

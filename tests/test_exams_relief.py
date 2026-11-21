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
                assert x["needed"] is False and x["not_needed"] == dict(by="app", why="Not happening: 3A is on " + EXAM), x
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

COVER = dict(date=ISO, p=0, n=1, classes=["1A"], subject="Art", needed=True, relief=BEN)

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
        c.post("/login", data={"as": "committee", "code": os.environ["COMMITTEE_CODE"]})
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
store.write_json(RS.PATH, dict(calendar=CAL, team=[GRACE], management=[GRACE], limits=dict(fat_per_day=3, other_per_day=None, never=[]), fat_role=""))
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
    assert c.post("/login", data={"as": "committee", "code": os.environ["COMMITTEE_CODE"]}).status_code == 302
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
        assert x["needed"] is True and x["relief"] == CHLOE and x["relief_by"] == GRACE and x["work"]["text"] == "Do page 5", x
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


_clear()
print(f"{COUNT} exams and relief tests passed")

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


_clear()
print(f"{COUNT} exams and relief tests passed")

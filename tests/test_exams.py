"""Plain-assert tests for exams: .venv/bin/python tests/test_exams.py"""
import os, secrets, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = tempfile.mkdtemp()
KEY = secrets.token_hex(16)
os.environ.pop("HEADS_CODE", None)
os.environ.update(DATA_DIR=DATA, SECRET_KEY=KEY, AI_PROVIDER="anthropic", AI_API_KEY="", COMMITTEE_CODE=secrets.token_hex(4), TEACHER_CODE=secrets.token_hex(4), STUDENT_CODE=secrets.token_hex(4))
sys.path.insert(0, ROOT)
import app as A, access, store  # noqa: E402
from relief import calendar as C  # noqa: E402
from exams import settings as ES, fake as F, days as D, schedules as SC, papers as P  # noqa: E402
from exams import seating as SE, invigilate as IV, make as MK  # noqa: E402
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

@t
def sample_school_is_consistent():
    m = F.sample_pub()["model"]
    assert len(m["students"]) == 90 and len(m["lessons"]) == 10 and len(m["rooms"]) == 9
    assert len(m["times"]) == 26 and m["times"][0] == ["7.40", "8.00"] and m["times"][6][0] == "9.40" and m["times"][9][0] == "10.40"
    assert m["times"][15] == ["12.40", "1.00"] and m["times"][-1] == ["4.00", "4.20"], "the real dotted 12-hour clock"
    assert C.school_day(F.CAL, m["days"], date(2026, 10, 5)) == "Odd Mon"
    assert C.school_day(F.CAL, m["days"], date(2026, 10, 12)) is None

def _fresh():
    if os.path.exists(ES.PATH): os.remove(ES.PATH)

@t
def settings_defaults_and_round_trip():
    _fresh()
    pub = F.sample_pub()
    d = ES.load(pub)
    want = ES.defaults(); want.update(missing=[], missing_rooms=[])
    assert d == want, d
    out = ES.save(dict(committee=["Ms Grace Yeo"], rooms={"Hall": dict(seats=240, rows=24, cols=10, hall=True, access=False, note="")},
                       backups=["Mr Ivan Lee"]), pub, "Ms Grace Yeo")
    assert out["committee"] == ["Ms Grace Yeo"] and out["backups"] == ["Mr Ivan Lee"] and out["saved_by"] == "Ms Grace Yeo"
    assert out["rooms"]["Hall"]["seats"] == 240
    assert ES.load(pub) == out

@t
def settings_refuse_bad_values():
    pub = F.sample_pub()
    hall = dict(seats=240, rows=24, cols=10, hall=True, access=False, note="")
    raises(ValueError, lambda: ES.save(dict(committee=["Mr Nobody"]), pub, "x"), "Mr Nobody is not on the published timetable or the staff list.")
    raises(ValueError, lambda: ES.save(dict(rooms={"Gym": hall}), pub, "x"), "Gym is not a room of the published timetable.")
    raises(ValueError, lambda: ES.save(dict(rooms={"Hall": dict(hall, seats=0)}), pub, "x"), "Give Hall a number of exam seats.")
    raises(ValueError, lambda: ES.save(dict(rooms={"Hall": dict(hall, rows=10, cols=10)}), pub, "x"), "Hall: rows times columns is less than its exam seats.")
    raises(ValueError, lambda: ES.save(dict(rules=dict(per_classroom="two")), pub, "x"), "Give a whole number for invigilators per classroom.")
    raises(ValueError, lambda: ES.save(dict(committee="Ms Grace Yeo"), pub, "x"), "Check the settings and try again.")

@t
def settings_drop_people_no_longer_there():
    _fresh()
    pub = F.sample_pub()
    os.makedirs(os.path.dirname(ES.PATH), exist_ok=True)
    store.write_json(ES.PATH, dict(backups=["Mr Gone Away", "Mr Ivan Lee"], rooms={"Old Hall": dict(seats=5)}))
    d = ES.load(pub)
    assert d["backups"] == ["Mr Ivan Lee"] and d["missing"] == ["Mr Gone Away"]
    assert d["rooms"] == {} and d["missing_rooms"] == ["Old Hall"]

def _sched(**kw):
    s = dict(levels=["Sec 3"], classes=[], start="2026-10-05", end="2026-10-06", days={})
    s.update(kw)
    return s

SEC3 = {"2026-10-05": dict(levels=["Sec 3"], whole=True)}

def _rows(view):
    return {r["row"]: r for r in view["lessons"]}

@t
def times_round_trip():
    assert D.minutes("07:40") == 460 and D.hhmm(460) == "07:40" and D.minutes("8:05") == 485
    raises(ValueError, lambda: D.minutes("7.40"), "7.40 is not a time.")
    m = F.sample_pub()["model"]
    b = D.bounds(m)
    assert len(b) == 26 and b[0] == (460, 480) and b[15] == (760, 780) and b[16] == (780, 800) and b[-1] == (960, 980), b
    m.pop("school")
    assert D.bounds(m) == b, "without a start time the dotted times are read, 12 hours added after noon"
    m["times"] = [["%02d:%02d" % divmod(a, 60), "%02d:%02d" % divmod(z, 60)] for a, z in b]
    assert D.bounds(m) == b

@t
def whole_day_stops_afternoon_periods():
    pub = F.sample_pub()
    pub["model"]["lessons"].append(F._lesson(10, 0, 18, 2, "Sec 3", ["3A"], "Art", "Entire Class", ["Ms Aisha Rahman"], "3-01"))
    r = _rows(D.day_view(pub, F.CAL, _sched(days=SEC3), "2026-10-05"))[10]
    assert r["stopped"] == [(820, 860)] and r["running"] == [], r

@t
def part_day_after_noon_saves_and_stops_the_right_periods():
    pub = F.sample_pub()
    pub["model"]["lessons"].append(F._lesson(10, 0, 14, 4, "Sec 3", ["3A"], "Art", "Entire Class", ["Ms Aisha Rahman"], "3-01"))
    e = SC.new("exam", "Afternoon", ["Sec 3"], "2026-10-05", "2026-10-05", "Ms Grace Yeo", pub=pub)
    e["days"] = {"2026-10-05": dict(levels=["Sec 3"], whole=False, **{"from": "12:40", "to": "13:20"})}
    e["papers"] = [dict(id="p1", level="Sec 3", subject="Art", paper="", minutes=30, date="2026-10-05", start="12:45", who="level",
                        students=[], together="")]
    saved = SC.save(e, pub, F.CAL, "x")
    assert saved["days"]["2026-10-05"]["from"] == "12:40" and saved["days"]["2026-10-05"]["to"] == "13:20"
    r = _rows(D.day_view(pub, F.CAL, saved, "2026-10-05"))[10]
    assert r["stopped"] == [(760, 800)] and r["running"] == [(740, 760), (800, 820)], r
    assert P.check(saved, pub["model"], F.CAL)["errors"] == []

@t
def whole_day_stops_every_sec3_lesson():
    pub = F.sample_pub()
    v = D.day_view(pub, F.CAL, _sched(days=SEC3), "2026-10-05")
    r = _rows(v)
    for i in (0, 1, 3, 4): assert r[i]["stopped"] and not r[i]["running"], i
    for i in (2, 5, 6, 7): assert r[i]["running"] and not r[i]["stopped"], i
    assert v["day"] == "Odd Mon" and set(v["window"]) == {"3A", "3B"}
    assert v["window"]["3A"] == (460, 460 + 26 * 20)

@t
def part_day_edge_shortens_a_lesson():
    pub = F.sample_pub()
    pub["model"]["lessons"][0]["n"] = 8
    s = _sched(days={"2026-10-05": {"levels": ["Sec 3"], "whole": False, "from": "07:40", "to": "09:00"}})
    v = D.day_view(pub, F.CAL, s, "2026-10-05")
    r0 = _rows(v)[0]
    assert r0["stopped"] == [(460, 540)] and r0["running"] == [(540, 620)], r0
    assert r0["start"] == 460 and r0["end"] == 620
    assert D.edge_cuts(v) == 1

@t
def mixed_level_lesson_runs():
    v = D.day_view(F.sample_pub(), F.CAL, _sched(days=SEC3), "2026-10-05")
    r8 = _rows(v)[8]
    assert r8["running"] and not r8["stopped"]

@t
def chosen_classes_only():
    v = D.day_view(F.sample_pub(), F.CAL, _sched(classes=["3A"], days=SEC3), "2026-10-05")
    assert set(v["window"]) == {"3A"}
    assert _rows(v)[0]["stopped"] and not _rows(v)[1]["stopped"] and _rows(v)[1]["running"]

@t
def not_a_school_day_has_no_lessons():
    pub = F.sample_pub()
    s = _sched(start="2026-10-12", end="2026-10-12")
    ds = D.dates(s, F.CAL, pub["model"])
    assert len(ds) == 1 and ds[0]["day"] is None and ds[0]["date"] == "2026-10-12"
    assert D.day_view(pub, F.CAL, s, "2026-10-12")["lessons"] == []

@t
def dates_lists_each_day_with_window():
    pub = F.sample_pub()
    ds = D.dates(_sched(days={"2026-10-06": dict(levels=["Sec 4"], whole=False, **{"from": "08:00", "to": "09:00"})}), F.CAL, pub["model"])
    assert [d["date"] for d in ds] == ["2026-10-05", "2026-10-06"]
    assert ds[0]["levels"] == ["Sec 3"] and (ds[0]["start"], ds[0]["end"]) == (460, 980)
    assert ds[1]["levels"] == ["Sec 4"] and (ds[1]["start"], ds[1]["end"]) == (480, 540) and ds[1]["day"] == "Odd Tue"

@t
def make_up_date_outside_has_no_window():
    v = D.day_view(F.sample_pub(), F.CAL, _sched(), "2026-10-07")
    assert v["window"] == {} and not any(r["stopped"] for r in v["lessons"])

@t
def must_rule_blocks_on_mondays():
    pub = F.sample_pub()
    v = D.day_view(pub, F.CAL, _sched(days=SEC3), "2026-10-05")
    assert v["blocked"]["Mr Ivan Lee"] == [(460, 580)], v["blocked"]
    assert "Mr Ivan Lee" not in D.day_view(pub, F.CAL, _sched(), "2026-10-06")["blocked"]

@t
def must_rule_without_strength_still_blocks():
    pub = F.sample_pub()
    for r in pub["model"]["setup"]["rules"]: r.pop("strength", None)
    v = D.day_view(pub, F.CAL, _sched(days=SEC3), "2026-10-05")
    assert v["blocked"]["Mr Ivan Lee"] == [(460, 580)], v["blocked"]
    pub["model"]["setup"]["rules"][0]["strength"] = "Prefer"
    assert "Mr Ivan Lee" not in D.day_view(pub, F.CAL, _sched(days=SEC3), "2026-10-05")["blocked"]

def _new(kind="exam"):
    return SC.new(kind, "Sec 3 End-of-Year Exam", ["Sec 3"], "2026-10-05", "2026-10-06", "Ms Grace Yeo", pub=F.sample_pub())

@t
def new_exam_has_the_defaults():
    e = _new()
    assert e["supervision"] == "invigilators" and e["seating"]["home_rooms"] is True and e["status"] == "draft"
    assert _new("test")["supervision"] == "lesson"

@t
def save_load_list_delete():
    pub, e = F.sample_pub(), _new()
    saved = SC.save(e, pub, F.CAL, "Ms Grace Yeo")
    assert SC.load(e["id"]) == saved and saved["saved_by"] == "Ms Grace Yeo"
    assert SC.listing()[0]["name"] == "Sec 3 End-of-Year Exam"
    SC.delete(e["id"])
    assert SC.load(e["id"]) is None and not [r for r in SC.listing() if r["id"] == e["id"]]

@t
def save_refuses_bad_input():
    pub = F.sample_pub()
    def bad(text, **kw):
        e = _new(); e.update(kw)
        raises(ValueError, lambda: SC.save(e, pub, F.CAL, "x"), text)
    bad("Give the exam a name.", name=" ")
    bad("Pick at least one level or class.", levels=[])
    bad("Check the dates: the last day is before the first.", start="2026-10-06", end="2026-10-05")
    bad("An exam can cover at most 31 days.", start="2026-10-01", end="2026-11-01")
    bad("07:50 is not the start of a period.", days={"2026-10-05": dict(levels=["Sec 3"], whole=False, **{"from": "07:50", "to": "09:00"})})
    bad("10:30 is not the end of a period.", days={"2026-10-05": dict(levels=["Sec 3"], whole=False, **{"from": "08:00", "to": "10:30"})})
    bad("On 2026-10-05 the end is before the start.", days={"2026-10-05": dict(levels=["Sec 3"], whole=False, **{"from": "09:00", "to": "08:20"})})
    bad("Sec 9 is not a level of the published timetable.", levels=["Sec 9"])
    bad("9Z is not a class of the published timetable.", classes=["9Z"])
    bad("Give Sec 3 English Paper 1 a length in minutes.", papers=[dict(id="p1", level="Sec 3", subject="English", paper="Paper 1", minutes=0)])
    bad("Extra time for 3A-05 must be 0 to 100 percent.", access=[dict(student="3A-05", extra=150)])
    bad("ZZ-99 is not on the published timetable.", access=[dict(student="ZZ-99", extra=10)])
    bad("Check the exam and try again.", levels="Sec 3")

@t
def saved_times_are_24_hour_hhmm():
    pub = F.sample_pub()
    e = _new()
    e["days"] = {"2026-10-05": dict(levels=["Sec 3"], whole=False, **{"from": "7:40", "to": "9:00"})}
    e["papers"] = [dict(id="p1", level="Sec 3", subject="English", paper="Paper 1", minutes=30, date="2026-10-05", start="8:05",
                        who="level", students=[], together="")]
    saved = SC.save(e, pub, F.CAL, "x")
    assert saved["days"]["2026-10-05"]["from"] == "07:40" and saved["days"]["2026-10-05"]["to"] == "09:00", saved["days"]
    assert saved["papers"][0]["start"] == "08:05" and SC.load(e["id"])["papers"][0]["start"] == "08:05"
    SC.delete(e["id"])

@t
def access_arrangements_carry_forward():
    old = _new()
    old["access"] = [dict(student="3A-05", extra=25, own_room=False, reader=False, scribe=False, note=""),
                     dict(student="ZZ-99", extra=10, own_room=False, reader=False, scribe=False, note="")]
    store.write_json(os.path.join(SC.DIR, old["id"] + ".json"), old)
    assert [a["student"] for a in _new()["access"]] == ["3A-05"]

_PUB = F.sample_pub()
_M = _PUB["model"]

def _paper(level="Sec 3", subject="English", paper="Paper 1", minutes=60, date=None, start=None, who="groups", students=None, together=""):
    return dict(id=secrets.token_hex(3), level=level, subject=subject, paper=paper, minutes=minutes, date=date, start=start,
                who=who, students=students or [], together=together)

@t
def who_sits_by_level_groups_and_list():
    assert len(P.who_sits(_paper(who="level"), _M)) == 60
    ids = P.who_sits(_paper(subject="Pure Chemistry"), _M)
    assert len(ids) == 20 and ids[0] == "3A-01" and ids[-1] == "3B-10" and ids == sorted(ids)
    assert P.who_sits(_paper(), _M) == ["3A-%02d" % k for k in range(1, 31)]
    assert P.who_sits(_paper(subject="Assembly"), _M) == ["3A-%02d" % k for k in range(1, 31)]
    assert P.who_sits(_paper(who="students", students=["3B-04", "ZZ-99"]), _M) == ["3B-04"]

@t
def fill_from_subjects_once():
    s = _new(); s["levels"] = ["Sec 3"]
    got = P.fill_from_subjects(s, _M)
    assert [p["subject"] for p in got] == ["Assembly", "Combined Science", "English", "Mathematics", "Pure Chemistry"]
    assert all(p["paper"] == "Paper 1" and p["minutes"] == 60 and p["who"] == "groups" and p["date"] is None for p in got)
    s["papers"] = got
    assert P.fill_from_subjects(s, _M) == []

@t
def paper_list_round_trip():
    s = _new()
    s["papers"] = [_paper(date="2026-10-05", start="07:50", who="level", together="MT2"), _paper(subject="Pure Chemistry", paper="")]
    back = P.read_paper_list(P.paper_list_xlsx(s))
    keys = ("level", "subject", "paper", "minutes", "date", "start", "who", "together")
    assert [{k: p[k] for k in keys} for p in back] == [{k: p[k] for k in keys} for p in s["papers"]]
    import io, openpyxl
    wb = openpyxl.Workbook(); wb.active.append(["Level", "Subject"]); b = io.BytesIO(); wb.save(b)
    raises(ValueError, lambda: P.read_paper_list(b.getvalue()), "The first row must be: Level, Subject, Paper, Minutes, Date, Start, Who sits, Sits with.")
    wb = openpyxl.Workbook(); ws = wb.active
    ws.append(["Level", "Subject", "Paper", "Minutes", "Date", "Start", "Who sits", "Sits with"]); ws.append(["Sec 3", "English", "", "abc"])
    b = io.BytesIO(); wb.save(b)
    raises(ValueError, lambda: P.read_paper_list(b.getvalue()), "Row 2: the minutes must be a whole number.")

def _chk(papers, days=None, access=None, start="2026-10-05", end="2026-10-06"):
    s = _new(); s.update(papers=papers, start=start, end=end, days=days or {}, access=access or [])
    return P.check(s, _M, F.CAL)

@t
def check_finds_missing_times_and_non_school_days():
    r = _chk([_paper(), _paper(subject="Mathematics", date="2026-10-12", start="08:00")], start="2026-10-05", end="2026-10-12")
    assert "Sec 3 English Paper 1 needs a date and a start time." in r["errors"]
    assert "Sec 3 Mathematics Paper 1 is on 2026-10-12, which is not a school day." in r["errors"] and len(r["errors"]) == 2, r
    r = _chk([_paper(date="2026-10-07", start="08:00")])
    assert r["errors"] == ["Sec 3 English Paper 1 is on 2026-10-07, which is not one of Sec 3's exam days."], r
    assert _chk([_paper(date="2026-10-07", start="08:00", who="students", students=["3A-01"])])["errors"] == []

@t
def extra_time_makes_a_clash():
    pcs = [_paper(subject="Pure Chemistry", date="2026-10-05", start="07:50"), _paper(who="level", date="2026-10-05", start="08:55")]
    r = _chk(pcs)
    assert r["errors"] == [] and any("less than 20 minutes between Sec 3 Pure Chemistry Paper 1 and Sec 3 English Paper 1 on 2026-10-05" in w for w in r["warnings"]), r
    r = _chk(pcs, access=[dict(student="3A-02", extra=25, own_room=False, reader=False, scribe=False, note="")])
    assert r["errors"] == ["1 student has Sec 3 Pure Chemistry Paper 1 and Sec 3 English Paper 1 at the same time on 2026-10-05."], r

@t
def check_window_and_together():
    d = {"2026-10-05": dict(levels=["Sec 3"], whole=False, **{"from": "07:40", "to": "09:00"})}
    r = _chk([_paper(date="2026-10-05", start="08:30")], days=d)
    assert r["errors"] == ["Sec 3 English Paper 1 runs outside Sec 3's exam time on 2026-10-05 (07:40\u201309:00)."], r
    a, b = _paper(date="2026-10-05", start="08:00", together="MT2"), _paper(subject="Mathematics", date="2026-10-05", start="09:00", together="MT2")
    r = _chk([a, b])
    assert "Sec 3 English Paper 1 and Sec 3 Mathematics Paper 1 share \u201cMT2\u201d but start at different times." in r["errors"], r


def _xset(rooms=None):
    x = ES.defaults()
    full = {"3-01": (40, 6, 7, False, False), "3-02": (40, 6, 7, False, False), "4-01": (40, 6, 7, False, False),
            "Hall": (240, 24, 10, True, False), "3-11": (24, 4, 6, False, True), "LT1&2": (80, None, None, False, False),
            "LT1": (40, None, None, False, False), "LT2": (40, None, None, False, False)}
    x["rooms"] = {n: dict(seats=v[0], rows=v[1], cols=v[2], hall=v[3], access=v[4], note="") for n, v in full.items()
                  if rooms is None or n in rooms}
    return x

def _sit(papers, **kw):
    s = _new(); s.update(papers=papers, levels=["Sec 3"], start="2026-10-05", end="2026-10-06", access=[]); s.update(kw)
    return s

def _first(s):
    return SE.sittings(s)[0]

def _seated(sched, rooms=None, pins=None):
    s = sched
    sit = _first(s)
    st = SE.sitting_students(sit, s, _M)
    free = [r for r in SE.rooms_free(_PUB, F.CAL, s, sit, _xset(rooms), set()) if r["busy"] == ""]
    return st, SE.seat(sit, st, free, s, _M, pins or {})

@t
def sittings_group_by_start():
    s = _sit([_paper(date="2026-10-05", start="10:00"), _paper(subject="Mathematics", date="2026-10-05", start="07:50"),
              _paper(subject="Science", date="2026-10-05", start="07:50"), _paper(subject="Art")])
    got = SE.sittings(s)
    assert [g["key"] for g in got] == ["2026-10-05 07:50", "2026-10-05 10:00"], got
    assert got[0]["start"] == 470 and len(got[0]["papers"]) == 2 and len(got[1]["papers"]) == 1

@t
def rooms_busy_with_running_lessons():
    s = _sit([_paper(who="level", date="2026-10-05", start="07:50")])
    got = {r["name"]: r["busy"] for r in SE.rooms_free(_PUB, F.CAL, s, _first(s), _xset(), set())}
    assert got["4-01"] == "Mathematics with 4A until 08:40", got
    assert got["LT1"] != "" and got["LT1&2"] != "" and got["LT2"] == "", got
    assert got["3-01"] == "" and got["Hall"] == "", got
    assert SE.rooms_free(_PUB, F.CAL, s, _first(s), _xset(), {"3-02"})[1]["busy"] == "used by another sitting"
    s = _sit([_paper(who="level", date="2026-10-05", start="09:00")])
    got = {r["name"]: r["busy"] for r in SE.rooms_free(_PUB, F.CAL, s, _first(s), _xset(), set())}
    assert got["Hall"] == "rain room for PE with 4A", got
    s["use_anyway"] = [["2026-10-05 09:00", "Hall"]]
    got = {r["name"]: r["busy"] for r in SE.rooms_free(_PUB, F.CAL, s, _first(s), _xset(), set())}
    assert got["Hall"] == "", got

@t
def own_class_in_own_room():
    s = _sit([_paper(who="level", date="2026-10-05", start="07:50")])
    st, r = _seated(s, rooms=("3-01", "3-02", "4-01", "Hall"))
    assert r["unseated"] == [] and len(r["rooms"]["3-01"]) == 30 and len(r["rooms"]["3-02"]) == 30, r
    assert r["rooms"]["3-01"][0] == ["3A-01", "A1"] and r["rooms"]["3-01"][1] == ["3A-02", "A2"], r["rooms"]["3-01"][:2]
    assert all(x[0].startswith("3B") for x in r["rooms"]["3-02"])

@t
def access_students_apart():
    s = _sit([_paper(who="level", date="2026-10-05", start="07:50")],
             access=[dict(student="3A-05", extra=25, own_room=True, reader=False, scribe=False, note="")])
    st, r = _seated(s)
    assert r["rooms"]["3-11"] == [["3A-05", "A1"]], r["rooms"]["3-11"]
    assert len(r["rooms"]["3-01"]) == 29 and r["unseated"] == [], r

@t
def shared_hall_alternates_levels():
    s = _sit([_paper(who="level", date="2026-10-05", start="07:50"), _paper(level="Sec 4", who="level", date="2026-10-05", start="07:50")], levels=["Sec 3", "Sec 4"])
    s["seating"]["home_rooms"] = False
    st, r = _seated(s, rooms=("3-01", "Hall"))
    hall = dict((sid, seat) for sid, seat in r["rooms"]["Hall"])
    assert len(hall) == 90 and r["unseated"] == [], r
    assert all(hall[x].startswith("A") for x in hall if x.startswith("3A") and int(x[-2:]) <= 24)
    assert {seat[0] for sid, seat in hall.items() if st[sid]["level"] == "Sec 4"} <= {"B", "D"}
    assert any(seat == "B1" and st[sid]["level"] == "Sec 4" for sid, seat in hall.items())

@t
def not_enough_seats():
    s = _sit([_paper(who="level", date="2026-10-05", start="07:50")])
    st, r = _seated(s, rooms=("3-01",))
    assert len(r["rooms"]["3-01"]) == 40 and len(r["unseated"]) == 20, r
    assert sum(1 for x, _ in r["rooms"]["3-01"] if x.startswith("3A")) == 30 and all(x.startswith("3B") for x in r["unseated"])

@t
def pins_win():
    s = _sit([_paper(who="level", date="2026-10-05", start="07:50")])
    st, r = _seated(s, pins={"3A-07": "3-02", "9Z-01": "3-02", "3A-08": "Nowhere"})
    assert "3A-07" in [x for x, _ in r["rooms"]["3-02"]] and "3A-07" not in [x for x, _ in r["rooms"]["3-01"]], r

def _duties(s, rooms=("3-01", "3-02"), xset=None, **kw):
    x = xset or _xset()
    seats = {}
    for sit in SE.sittings(s):
        st = SE.sitting_students(sit, s, _M)
        free = [r for r in SE.rooms_free(_PUB, F.CAL, s, sit, _xset(rooms), set()) if r["busy"] == ""]
        seats[sit["key"]] = SE.seat(sit, st, free, s, _M, {})["rooms"]
    return IV.assign(_PUB, F.CAL, s, x, seats), x

@t
def need_per_room():
    r = ES.defaults()["rules"]
    assert IV.need(dict(hall=False, access=False), 30, [], r) == 2
    assert IV.need(dict(hall=True, access=False), 100, [], r) == 4
    assert IV.need(dict(hall=False, access=True), 3, [None, dict(reader=True, scribe=False), dict(reader=False, scribe=False)], r) == 2
    assert IV.need(dict(hall=False, access=False), 0, [], r) == 0

@t
def freed_teachers_first():
    s = _sit([_paper(who="level", date="2026-10-05", start="07:50")])
    x = _xset(); x["backups"] = ["Mr Ivan Lee"]
    d, _ = _duties(s, xset=x)
    d1 = d[0]
    assert d1["room"] == "3-01" and d1["start"] == 455 and d1["end"] == 540 and d1["need"] == 2, d1
    assert d1["names"] == ["Ms Aisha Rahman", "Ms Chloe Tan"], d1
    assert d1["reasons"] == {"Ms Aisha Rahman": "freed: 3A on the exam then", "Ms Chloe Tan": "freed: 3B on the exam then"}, d1
    assert d1["short"] == 0 and d1["locked"] is False and d1["chief"] is None

@t
def busy_teacher_needs_a_backup():
    s = _sit([_paper(who="level", date="2026-10-05", start="07:50")])
    x = _xset(); x["backups"] = ["Mr Ivan Lee"]
    x["never"] = ["Ms Aisha Rahman", "Mr Ben Ong", "Ms Chloe Tan", "Ms Grace Yeo", "Mr Hafiz Rahman"]
    d, _ = _duties(s, xset=x)
    assert d[0]["names"] == ["Mr Daniel Koh"] and d[0]["backup"] == {"Mr Daniel Koh": [2]} and d[0]["short"] == 1, d[0]
    assert "needs a backup" in d[0]["reasons"]["Mr Daniel Koh"] and d[1]["names"] == [] and d[1]["short"] == 2

@t
def backups_kept_for_later():
    s = _sit([_paper(who="level", date="2026-10-06", start="07:50")])
    x = _xset(); x["backups"] = ["Mr Ivan Lee"]
    d, _ = _duties(s, xset=x)
    picked = d[0]["names"] + d[1]["names"]
    assert len(picked) == 4 and len(set(picked)) == 4 and "Mr Ivan Lee" not in picked, picked
    got = IV.candidates(_PUB, F.CAL, s, x, "2026-10-06", d[0]["start"], d[0]["end"], [d[1]])
    assert got["backups"][0]["name"] == "Mr Ivan Lee" and got["backups"][0]["reason"] == "backup invigilator", got
    assert "Mr Ivan Lee" not in [c["name"] for c in got["freed"] + got["free"]]

@t
def common_test_supervised_by_lesson_teacher():
    s = _sit([_paper(subject="Mathematics", minutes=30, date="2026-10-05", start="07:50")], kind="test", supervision="lesson")
    d, _ = _duties(s)
    duty = next(x for x in d if x["room"] == "3-02")
    assert duty["names"] == ["Ms Chloe Tan"] and duty["reasons"] == {"Ms Chloe Tan": "supervises their own lesson"} and duty["need"] == 1

@t
def locked_names_kept():
    s = _sit([_paper(who="level", date="2026-10-05", start="07:50")])
    s["pins"]["duties"] = {"2026-10-05 07:50|3-01": ["Ms Grace Yeo", "Mr Gone Away"]}
    d, _ = _duties(s)
    d1 = d[0]
    assert "Ms Grace Yeo" in d1["names"] and "Mr Gone Away" not in d1["names"] and len(d1["names"]) == d1["need"] and d1["locked"] is True, d1
    assert len(set(d1["names"])) == 2
    assert IV.duty_minutes(d)["Ms Grace Yeo"] == 85

def _made_sched(**kw):
    s = _sit([_paper(subject="English", date="2026-10-05", start="07:50"),
              _paper(subject="Pure Chemistry", date="2026-10-05", start="10:00")], days=dict(SEC3))
    s.update(kw)
    return s

def _mk(s, only=None, rooms=("3-01", "3-02", "4-01", "Hall")):
    return MK.make(_PUB, F.CAL, s, _xset(rooms), only=only)

@t
def make_seats_and_duties():
    s = _mk(_made_sched())
    m = s["made"]
    assert len(m["seats"]) == 2 and all(not v for v in m["unseated"].values()) and m["gone"] == [], m
    assert m["duties"] and all(d["short"] == 0 for d in m["duties"]), m["duties"]
    for a in m["duties"]:
        for b in m["duties"]:
            if a is not b and a["date"] == b["date"] and a["start"] < b["end"] and a["end"] > b["start"]:
                assert not set(a["names"]) & set(b["names"]), (a, b)

@t
def move_keeps_hand_changes():
    s = _made_sched()
    key = "2026-10-05 07:50"
    MK.move(s, key, ["3A-07"], "3-02")
    _mk(s, only=key)
    assert "3A-07" in [x for x, _ in s["made"]["seats"][key]["3-02"]]
    other = s["made"]["seats"]["2026-10-05 10:00"]
    _mk(s)
    assert "3A-07" in [x for x, _ in s["made"]["seats"][key]["3-02"]]
    assert s["made"]["seats"]["2026-10-05 10:00"] == other
    MK.set_invigilators(s, key, "3-01", ["Mr Ivan Lee"])
    _mk(s, only=key)
    d = next(x for x in s["made"]["duties"] if x["key"] == key and x["room"] == "3-01")
    assert "Mr Ivan Lee" in d["names"] and d["locked"] is True, d

@t
def gone_people_are_named_once():
    s = _made_sched()
    key = "2026-10-05 07:50"
    MK.move(s, key, ["ZZ-99"], "3-02")
    MK.set_invigilators(s, key, "3-01", ["Mr Gone Away"])
    _mk(s)
    m = s["made"]
    assert sorted(m["gone"]) == ["Mr Gone Away is no longer on the timetable.", "ZZ-99 is no longer on the timetable."], m["gone"]
    d = next(x for x in m["duties"] if x["key"] == key and x["room"] == "3-01")
    assert d["names"] and "Mr Gone Away" not in d["names"] and d["short"] == 0 and d["locked"] is False, d
    assert s["pins"] == dict(rooms={}, duties={}), s["pins"]
    _mk(s)
    assert s["made"]["gone"] == []

@t
def summary_counts():
    s = _mk(_made_sched())
    r = MK.summary(_PUB, F.CAL, s, _xset())
    assert [d["date"] for d in r["days"]] == ["2026-10-05", "2026-10-06"]
    d = r["days"][0]
    assert d["freed"] >= 4 and d["whole"] is True and d["window"] == ["07:40", "16:20"], d
    assert d["papers"]["Sec 3"] == [dict(label="Sec 3 English Paper 1", start="07:50", end="08:50"),
                                    dict(label="Sec 3 Pure Chemistry Paper 1", start="10:00", end="11:00")], d["papers"]
    c = r["counts"]
    assert c["papers"] == 2 and c["with_time"] == 2 and c["two_a_day"] == 10 and c["duties"] == len(s["made"]["duties"]), c
    assert c["short"] == 0 and c["unseated"] == 0
    assert MK.summary(_PUB, F.CAL, _made_sched(), _xset())["counts"]["duties"] == 0

@t
def lesson_lists_three_ways():
    s = _made_sched()
    r = MK.lesson_lists(_PUB, F.CAL, s)
    subj = lambda L: sorted((i["subject"], i["date"]) for i in L if i["date"] == "2026-10-05")
    assert subj(r["none"]) == [("Combined Science", "2026-10-05"), ("English", "2026-10-05"), ("Mathematics", "2026-10-05"),
                               ("Pure Chemistry", "2026-10-05")], r["none"]
    assert any(i["subject"] == "Mathematics" and i["classes"] == ["4A"] for i in r["runs"]) and r["backup"] == []
    MK.set_invigilators(s, "2026-10-05 07:50", "3-01", ["Mr Daniel Koh"])
    _mk(s)
    r = MK.lesson_lists(_PUB, F.CAL, s)
    b = [i for i in r["backup"] if i["classes"] == ["4A"] and i["subject"] == "Mathematics"]
    assert b and b[0]["note"] == "Mr Daniel Koh is invigilating 3-01", r["backup"]
    assert not any(i["classes"] == ["4A"] and i["subject"] == "Mathematics" for i in r["runs"])

# ---- the card, the rights and the routes
import contextlib  # noqa: E402

@contextlib.contextmanager
def published(pub):
    old = store.published; store.published = lambda: pub
    try: yield
    finally: store.published = old

def signed_in(card, code):
    c = A.app.test_client()
    return c, c.post("/login", data={"as": card, "code": code})

def committee():
    c, r = signed_in("committee", os.environ["COMMITTEE_CODE"]); assert r.status_code == 302
    return c

def staff(name, card="exams"):
    c, r = signed_in(card, access.staff_code(name)); assert r.status_code == 302, (name, r.status_code)
    return c

def _cal(on=True):
    import relief.settings as RS
    os.makedirs(os.path.dirname(RS.PATH), exist_ok=True)
    store.write_json(RS.PATH, dict(calendar=F.CAL if on else dict(terms=[], holidays=[])))

def _reset():
    _fresh()
    import shutil
    shutil.rmtree(SC.DIR, ignore_errors=True)

def _rooms_saved():
    x = _xset(("3-01", "3-02", "4-01", "Hall"))
    os.makedirs(os.path.dirname(ES.PATH), exist_ok=True)
    store.write_json(ES.PATH, dict(committee=[], rooms=x["rooms"]))

@t
def exams_card_on_the_front_page():
    c = A.app.test_client()
    with published(_PUB):
        front = c.get("/login").data
        assert b"Exams and events" in front and b'src="/static/choice-exams.svg"' in front
        _, r = signed_in("exams", access.staff_code("Ms Grace Yeo"))
        assert r.status_code == 302 and r.headers["Location"] == "/exams", r.headers
        _, r = signed_in("exams", os.environ["TEACHER_CODE"])
        assert r.status_code == 403 and b"/login?as=teacher" in r.data, r.data
        _, r = signed_in("relief", access.staff_code("Ms Grace Yeo"))
        assert r.headers["Location"] == "/relief"
    assert A.CHOICE_OF["staff"] == "relief"

@t
def only_the_committees_get_in():
    _reset(); _cal()
    with published(_PUB):
        s = staff("Ms Grace Yeo")
        r = s.get("/api/exams"); assert r.status_code == 403 and r.get_json()["error"] == A.ONLY_EXAMS, r.data
        assert s.get("/api/exams/me").get_json() == dict(name="Ms Grace Yeo", can_use=False)
        assert s.get("/api/exams/settings").status_code == 403
        c = committee()
        assert c.get("/api/exams").status_code == 200
        assert c.get("/api/exams/me").get_json() == dict(name="Timetable committee", can_use=True)
        d = c.get("/api/exams/settings").get_json()
        assert d["settings"]["committee"] == [] and {"name": "Hall", "kind": "pe venue", "capacity": 400} in [dict(zip(("name", "kind", "capacity"), r)) if isinstance(r, list) else r for r in d["rooms"]], d["rooms"]
        d["settings"]["committee"] = ["Ms Grace Yeo"]
        r = c.put("/api/exams/settings", json=d["settings"]); assert r.status_code == 200, r.data
        assert s.get("/api/exams").status_code == 200
        assert s.get("/api/exams/me").get_json()["can_use"] is True
        assert s.get("/exams").status_code == 200 and s.get("/exams/settings").status_code == 200
        assert c.put("/api/exams/settings", json="x").status_code == 400
        assert c.put("/api/exams/settings", data="{bad", content_type="application/json").status_code == 400
    r = A.app.test_client().get("/api/exams"); assert r.status_code == 401
    with published(None):
        assert committee().get("/api/exams").status_code == 409

@t
def no_calendar_no_new_exam():
    _reset(); _cal(False)
    with published(_PUB):
        c = committee()
        assert c.get("/api/exams").get_json()["calendar_ok"] is False
        r = c.post("/api/exams", json=dict(kind="exam", name="X", levels=["Sec 3"], start="2026-10-05", end="2026-10-06"))
        assert r.status_code == 409 and r.get_json()["error"] == SC.NO_CALENDAR, r.data

def _exam(c):
    r = c.post("/api/exams", json=dict(kind="exam", name="Sec 3 Exam", levels=["Sec 3"], start="2026-10-05", end="2026-10-06"))
    assert r.status_code == 200, r.data
    s = r.get_json()
    s["days"] = dict(SEC3)
    r = c.put("/api/exams/" + s["id"], json=s); assert r.status_code == 200, r.data
    r = c.post(f"/api/exams/{s['id']}/fill"); assert r.status_code == 200, r.data
    s = r.get_json()
    assert {p["subject"] for p in s["papers"]} >= {"English", "Pure Chemistry"}, s["papers"]
    return s

@t
def create_fill_make_view():
    _reset(); _cal(); _rooms_saved()
    with published(_PUB):
        c = committee()
        assert c.get("/api/exams").get_json()["classes"][0] == ["3A", "Sec 3"]
        s = _exam(c)
        times = {"English": "07:50", "Pure Chemistry": "10:00"}
        s["papers"] = [dict(p, date="2026-10-05", start=times[p["subject"]]) for p in s["papers"] if p["subject"] in times]
        third = dict(s["papers"][0], id="zzzz", subject="Mathematics", start=None)
        r = c.put("/api/exams/" + s["id"], json=dict(s, papers=s["papers"] + [third])); assert r.status_code == 200
        r = c.post(f"/api/exams/{s['id']}/make", json={})
        assert r.status_code == 400 and r.get_json()["error"].startswith("Fix the paper times first: "), r.data
        r = c.put("/api/exams/" + s["id"], json=s); assert r.status_code == 200
        r = c.post(f"/api/exams/{s['id']}/make", json={}); assert r.status_code == 200, r.data
        v = c.get(f"/api/exams/{s['id']}/view").get_json()
        assert v["summary"]["counts"]["papers"] == 2 and v["summary"]["counts"]["unseated"] == 0, v["summary"]["counts"]
        assert v["made"] and v["students_missing"] is False and "Hall" in v["rooms"]
        assert v["students"] and all(k.startswith("3") for k in v["students"]) and v["students"]["3A-01"] == ["Student 3A-01", "3A"], list(v["students"])[:3]
        assert not any(k.startswith("4") for k in v["students"]) and 30 <= len(v["students"]) <= 60
        assert c.get(f"/api/exams/{s['id']}").get_json()["made"] is not None
        key = "2026-10-05 07:50"; room = next(iter(v["made"]["seats"][key]))
        r = c.post(f"/api/exams/{s['id']}/move", json=dict(key=key, students=["3A-07"], room="3-02")); assert r.status_code == 200
        assert c.get(f"/api/exams/{s['id']}").get_json()["pins"]["rooms"][key] == {"3A-07": "3-02"}
        assert "3A-07" in [x for x, _ in r.get_json()["made"]["seats"][key]["3-02"]]
        r = c.post(f"/api/exams/{s['id']}/invigilators", json=dict(key=key, room="3-01", names=["Mr Ivan Lee"])); assert r.status_code == 200
        d1 = next(x for x in r.get_json()["made"]["duties"] if x["key"] == key and x["room"] == "3-01")
        assert "Mr Ivan Lee" in d1["names"] and d1["locked"] is True, d1
        for path, body in (("move", dict(key="bad", students=["3A-07"], room="3-02")), ("invigilators", dict(key="bad", room="3-01", names=[])),
                           ("use-anyway", dict(key="bad", room="Hall"))):
            r = c.post(f"/api/exams/{s['id']}/{path}", json=body)
            assert r.status_code == 400 and r.get_json() == {"error": "That sitting is not in this exam."}, (path, r.data)
        assert c.get(f"/api/exams/{s['id']}").get_json()["pins"]["duties"][key + "|3-01"] == ["Mr Ivan Lee"]
        r = c.get(f"/api/exams/{s['id']}/who?key={key}&room=3-01"); assert r.status_code == 200 and "freed" in r.get_json(), r.data
        assert c.get(f"/api/exams/{s['id']}/who?key=nope&room=3-01").get_json() == {"error": "Press Make first."}
        r = c.post(f"/api/exams/{s['id']}/use-anyway", json=dict(key=key, room="Hall")); assert r.status_code == 200
        assert [key, "Hall"] in c.get(f"/api/exams/{s['id']}").get_json()["use_anyway"]
        r = c.get(f"/api/exams/{s['id']}/papers.xlsx"); assert r.status_code == 200 and "Sec 3 Exam papers.xlsx" in r.headers["Content-Disposition"]
        import io
        r2 = c.post(f"/api/exams/{s['id']}/papers.xlsx", data=dict(file=(io.BytesIO(r.data), "p.xlsx"))); assert r2.status_code == 200, r2.data
        assert len(r2.get_json()["papers"]) == 2
        r2 = c.post(f"/api/exams/{s['id']}/papers.xlsx", data=dict(file=(io.BytesIO(b"junk"), "p.xlsx"))); assert r2.status_code == 400
        assert c.get("/api/exams/ffff").status_code == 404 and c.get("/api/exams/ffff").get_json()["error"] == "That exam is not there any more."
        assert len(c.get("/api/exams").get_json()["schedules"]) == 1
        assert c.delete(f"/api/exams/{s['id']}").status_code == 200
        assert c.get("/api/exams").get_json()["schedules"] == []
        assert c.get("/exams").status_code == 200 and c.get("/exams/" + s["id"]).status_code == 200

@t
def view_carries_counts_periods_and_the_levels_students():
    _reset(); _cal()
    with published(_PUB):
        c = committee()
        s = _exam(c)
        v = c.get(f"/api/exams/{s['id']}/view").get_json()
        assert v["periods"][0] == ["07:40", "08:00"] and v["periods"][16] == ["13:00", "13:20"] and len(v["periods"]) == 26, v["periods"][:2]
        assert set(v["counts"]) == {p["id"] for p in s["papers"]} and all(n >= 0 for n in v["counts"].values())
        eng = next(p for p in s["papers"] if p["subject"] == "English")
        assert v["counts"][eng["id"]] > 0
        assert v["students"] and all(k.startswith("3") for k in v["students"]), list(v["students"])[:3]
        assert len(v["students"]) == len([x for x in _PUB["model"]["students"] if x["level"] == "Sec 3"])
        s["papers"] = []
        assert c.put("/api/exams/" + s["id"], json=s).status_code == 200
        v = c.get(f"/api/exams/{s['id']}/view").get_json()
        assert v["counts"] == {} and len(v["students"]) > 0, "students come from the levels even with no papers"

@t
def view_carries_levels_and_the_rooms_of_each_sitting():
    _reset(); _cal(); _rooms_saved()
    with published(_PUB):
        c = committee()
        s = _exam(c)
        s["papers"] = [dict(p, date="2026-10-05", start="09:00") for p in s["papers"] if p["subject"] == "English"]
        assert c.put("/api/exams/" + s["id"], json=s).status_code == 200
        v = c.get(f"/api/exams/{s['id']}/view").get_json()
        assert v["levels"] == _PUB["model"]["levels"] and "Sec 3" in v["levels"], v["levels"]
        assert list(v["rooms_by_key"]) == ["2026-10-05 09:00"], list(v["rooms_by_key"])
        rooms = {n: (seats, busy) for n, seats, busy in v["rooms_by_key"]["2026-10-05 09:00"]}
        assert rooms["Hall"][1] == "rain room for PE with 4A" and rooms["3-01"][1] == "", rooms
        assert rooms["Hall"][0] > 0

@t
def make_refuses_without_students():
    import copy
    _reset(); _cal()
    pub = copy.deepcopy(_PUB); pub["model"]["students"] = []
    with published(pub):
        c = committee()
        s = _exam(c)
        r = c.post(f"/api/exams/{s['id']}/make", json={})
        assert r.status_code == 409 and r.get_json()["error"] == A.NO_STUDENTS, r.data
        assert c.get(f"/api/exams/{s['id']}/view").get_json()["students_missing"] is True

@t
def client_cannot_write_made():
    _reset(); _cal(); _rooms_saved()
    with published(_PUB):
        c = committee()
        s = _exam(c)
        s["papers"] = [dict(p, date="2026-10-05", start="07:50") for p in s["papers"] if p["subject"] == "English"]
        c.put("/api/exams/" + s["id"], json=s)
        assert c.post(f"/api/exams/{s['id']}/make", json={}).status_code == 200
        c.post(f"/api/exams/{s['id']}/invigilators", json=dict(key="2026-10-05 07:50", room="3-01", names=["Mr Ivan Lee"]))
        kept = c.get(f"/api/exams/{s['id']}").get_json()
        forged = dict(kept, made=dict(seats={}, unseated={}, duties=[], gone=[]), pins=dict(rooms={}, duties={}), use_anyway=[["x", "y"]],
                      created_by="someone", status="final", id=s["id"])
        r = c.put("/api/exams/" + s["id"], json=forged); assert r.status_code == 200, r.data
        now = c.get(f"/api/exams/{s['id']}").get_json()
        for k in ("made", "pins", "use_anyway", "created_by", "created_at", "status", "id"):
            assert now[k] == kept[k], k
        assert c.put("/api/exams/" + s["id"], json=dict(kept, papers="x")).status_code == 400
        assert c.put("/api/exams/" + s["id"], json=dict(kept, days=5)).status_code == 400

def _made_exam(c, mutate=None):
    s = _exam(c)
    times = {"English": "07:50", "Pure Chemistry": "10:00"}
    s["papers"] = [dict(p, date="2026-10-05", start=times[p["subject"]]) for p in s["papers"] if p["subject"] in times]
    assert c.put("/api/exams/" + s["id"], json=s).status_code == 200
    assert c.post(f"/api/exams/{s['id']}/make", json={}).status_code == 200
    return s

@t
def printouts_and_excel():
    import io, openpyxl
    _reset(); _cal(); _rooms_saved()
    with published(_PUB):
        c = committee()
        s = _exam(c)
        r = c.get(f"/api/exams/{s['id']}/print/seating.pdf")
        assert r.status_code == 409 and r.get_json() == {"error": "Press Make first."}, r.data
        assert c.get(f"/api/exams/{s['id']}/download.xlsx").status_code == 409
        s = _made_exam(c)
        for what in ("seating", "doors", "attendance", "classes", "roster-day", "roster-teacher", "timetable"):
            r = c.get(f"/api/exams/{s['id']}/print/{what}.pdf")
            assert r.status_code == 200 and r.data.startswith(b"%PDF"), (what, r.status_code)
            assert f"Sec 3 Exam {what}.pdf" in r.headers["Content-Disposition"] and r.headers["Content-Disposition"].startswith("inline"), r.headers["Content-Disposition"]
        assert c.get(f"/api/exams/{s['id']}/print/nothing.pdf").status_code == 404
        r = c.get(f"/api/exams/{s['id']}/download.xlsx"); assert r.status_code == 200 and "Sec 3 Exam.xlsx" in r.headers["Content-Disposition"]
        wb = openpyxl.load_workbook(io.BytesIO(r.data))
        assert wb.sheetnames == ["Papers", "Seats", "Duties", "Lessons"], wb.sheetnames
        made = c.get(f"/api/exams/{s['id']}").get_json()["made"]
        want = sum(len(rows) for rooms in made["seats"].values() for rows in rooms.values())
        assert wb["Seats"].max_row == 1 + want == 1 + 30 + 20, (wb["Seats"].max_row, want)
        assert [x.value for x in wb["Seats"][1]] == ["Date", "Start", "Room", "Seat", "Student ID", "Name", "Class", "Paper"]
        assert [x.value for x in wb["Duties"][1]][-1] == "Needs backup" and wb["Duties"].max_row > 1
        assert [x.value for x in wb["Lessons"][1]][0] == "List"
        assert {x.value for x in wb["Lessons"]["A"][1:]} <= {"No relief needed", "Backup needed", "Runs as usual"} and wb["Lessons"].max_row > 1
        assert [x.value for x in wb["Papers"][1]][0] == "Level"
        assert not [1 for ws in wb for row in ws.iter_rows() for x in row if isinstance(x.value, str) and x.value[:1] in "=+-@\t\r"]
        import copy
        pub = copy.deepcopy(_PUB); pub["model"]["students"][0]["name"] = "=SUM(1)"
        first = pub["model"]["students"][0]["id"]
    with published(pub):
        c = committee()
        assert c.post(f"/api/exams/{s['id']}/make", json={}).status_code == 200
        wb = openpyxl.load_workbook(io.BytesIO(c.get(f"/api/exams/{s['id']}/download.xlsx").data))
        assert "'=SUM(1)" in [x.value for row in wb["Seats"].iter_rows() for x in row], first
        assert c.get(f"/api/exams/{s['id']}/print/seating.pdf").data.startswith(b"%PDF")
    assert A.app.test_client().get(f"/api/exams/{s['id']}/download.xlsx").status_code in (401, 403)

print(f"{COUNT} exams tests passed")

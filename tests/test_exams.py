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
from exams import seating as SE  # noqa: E402
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
    assert len(m["times"]) == 26 and m["times"][0] == ["07:40", "08:00"] and m["times"][6][0] == "09:40" and m["times"][9][0] == "10:40"
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
    assert D.minutes("07:40") == 460 and D.hhmm(460) == "07:40"
    raises(ValueError, lambda: D.minutes("7.40"), "7.40 is not a time.")

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

print(f"{COUNT} exams tests passed")

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
from exams import seating as SE, invigilate as IV, make as MK, approval as AP, printouts as PR  # noqa: E402
import exams.published as PB  # noqa: E402
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
    SC.delete(e["id"])

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
    assert SC.listing(date(2026, 10, 1))[0]["name"] == "Sec 3 End-of-Year Exam"
    SC.delete(e["id"])
    assert SC.load(e["id"]) is None and not [r for r in SC.listing(date(2026, 10, 1)) if r["id"] == e["id"]]

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
    bad("Check the exam and try again.", kind="party")
    bad("Check the exam and try again.", supervision="nobody")
    bad("Check the exam and try again.", levels=[5])
    bad("Check the exam and try again.", days={"2026-10-05": dict(levels="Sec 3", whole=True)})
    bad("Check the exam and try again.", days={"not a date": dict(whole=True)})
    bad("Check the exam and try again.", times=dict(report="07:30", min_break="abc", max_papers=2))
    bad("Give a whole number of minutes between two papers.", times=dict(report="07:30", min_break=-1, max_papers=2))
    bad("Give a whole number for the most papers a day.", times=dict(report="07:30", min_break=20, max_papers=0))
    bad("Give the report time as a time such as 07:30.", times=dict(report="7.30", min_break=20, max_papers=2))
    for k, v in (("order", 5), ("shared", "x"), ("spacing", "wide"), ("home_rooms", "yes")):
        e = _new(); e["seating"][k] = v
        raises(ValueError, lambda: SC.save(e, pub, F.CAL, "x"), "Check the exam and try again.")
    good = dict(id="p1", level="Sec 3", subject="English", paper="Paper 1", minutes=60, date="2026-10-05", start="07:50", who="level",
                students=[], together="")
    for k, v in (("together", 5), ("date", "2026-13-40"), ("who", "all"), ("students", "3A-01"), ("students", [5]), ("level", 5),
                 ("subject", None), ("id", "")):
        bad("Check the exam and try again.", papers=[dict(good, **{k: v})])
    bad("Give Sec 3 English Paper 1 a start time such as 08:00.", papers=[dict(good, start="8.00")])
    bad("Check the exam and try again.", papers=[good, dict(good)])
    e = _new(); e["seating"] = dict(order="name", shared="blocks", spacing="gap", home_rooms=False)
    e["papers"] = [dict(good, date=None, start=None, paper=None, together=None)]
    saved = SC.save(e, pub, F.CAL, "x")
    assert saved["seating"] == dict(order="name", shared="blocks", spacing="gap", home_rooms=False)
    assert saved["papers"][0]["paper"] == "" and saved["papers"][0]["together"] == "" and saved["times"]["report"] == "07:30"
    SC.delete(e["id"])

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


@t
def classes_only_exam_uses_their_levels():
    s = _sched(levels=[], classes=["3A"], days={})
    v = D.day_view(F.sample_pub(), F.CAL, s, "2026-10-05")
    assert set(v["window"]) == {"3A"} and _rows(v)[0]["stopped"] and not _rows(v)[1]["stopped"], v["window"]
    assert D.dates(s, F.CAL, _M)[0]["levels"] == ["Sec 3"]
    s["days"] = {"2026-10-05": dict(levels=[], whole=True)}
    assert set(D.day_view(F.sample_pub(), F.CAL, s, "2026-10-05")["window"]) == {"3A"}
    e = _new(); e.update(levels=[], classes=["3A"], access=[], papers=[_paper(date="2026-10-05", start="07:50")])
    assert P.check(e, _M, F.CAL)["errors"] == []
    assert [p["subject"] for p in P.fill_from_subjects(e, _M)] == ["Assembly", "Combined Science", "Pure Chemistry"]

@t
def count_sentences_say_the_number_once():
    r = _chk([_paper(who="level", date="2026-10-05", start="07:50"), _paper(subject="Mathematics", who="level", date="2026-10-05", start="09:00"),
              _paper(subject="Science", who="level", date="2026-10-05", start="10:30")])
    assert "60 students have 3 papers on 2026-10-05." in r["warnings"], r["warnings"]
    pcs = [_paper(subject="Pure Chemistry", date="2026-10-05", start="07:50"), _paper(who="level", date="2026-10-05", start="08:55")]
    aa = [dict(student=x, extra=25, own_room=False, reader=False, scribe=False, note="") for x in ("3A-02", "3A-03")]
    assert _chk(pcs, access=aa)["errors"] == ["2 students have Sec 3 Pure Chemistry Paper 1 and Sec 3 English Paper 1 at the same time on 2026-10-05."]

@t
def a_paper_at_the_edge_of_a_part_day_is_warned():
    d = {"2026-10-05": dict(levels=["Sec 3"], whole=False, **{"from": "09:40", "to": "10:40"})}
    r = _chk([_paper(minutes=30, date="2026-10-05", start="09:40")], days=d)
    assert r["errors"] == [] and r["warnings"] == ["Sec 3 English Paper 1 starts at 09:40, less than 15 minutes after the exam time begins: "
                                                   "rooms of lessons just before may be busy."], r
    r = _chk([_paper(minutes=30, date="2026-10-05", start="10:05")], days=d)
    assert r["warnings"] == ["Sec 3 English Paper 1 ends at 10:35, less than 10 minutes before the exam time ends: "
                             "rooms of lessons just after may be busy."], r
    s = _new(); s.update(papers=[_paper(minutes=30, date="2026-10-05", start="10:05")], days=d, access=[])
    assert P.check(s, _M, F.CAL, dict(arrive=0, stay=0))["warnings"] == []
    assert _chk([_paper(minutes=30, date="2026-10-05", start="07:40")])["warnings"] == [], "a whole day has no lessons before it"
    aa = [dict(student=x, extra=50, own_room=False, reader=False, scribe=False, note="") for x in ("3A-02",)]
    r = _chk([_paper(minutes=40, date="2026-10-05", start="09:50")], days=d, access=aa)
    assert "1 student with extra time finishes Sec 3 English Paper 1 after the exam time ends on 2026-10-05." in r["warnings"], r
    aa.append(dict(aa[0], student="3A-03"))
    r = _chk([_paper(minutes=40, date="2026-10-05", start="09:50")], days=d, access=aa)
    assert "2 students with extra time finish Sec 3 English Paper 1 after the exam time ends on 2026-10-05." in r["warnings"], r

@t
def edge_cut_is_warned():
    import copy
    m = copy.deepcopy(_M); m["lessons"][0]["n"] = 8
    s = _new(); s.update(papers=[], access=[], days={"2026-10-05": dict(levels=["Sec 3"], whole=False, **{"from": "07:40", "to": "09:00"})})
    assert P.check(s, m, F.CAL)["warnings"] == ["On 2026-10-05 the exam time ends in the middle of 1 lesson."]
    assert P.check(s, _M, F.CAL)["warnings"] == []

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
    s9 = _sit([_paper(date="2026-10-05", start="09:00")])
    got = {r["name"]: r["busy"] for r in SE.rooms_free(_PUB, F.CAL, s9, _first(s9), _xset(), set())}
    assert got["LT1"] == "Literature with 4A until 09:00 (invigilators arrive 08:45)", got
    s9 = _sit([_paper(date="2026-10-05", start="09:45", minutes=50)])
    got = {r["name"]: r["busy"] for r in SE.rooms_free(_PUB, F.CAL, s9, _first(s9), _xset(), set())}
    assert got["4-01"] == "English with 4A from 10:40 (invigilators stay until 10:45)", got
    s = _sit([_paper(who="level", date="2026-10-05", start="09:00")])
    got = {r["name"]: r["busy"] for r in SE.rooms_free(_PUB, F.CAL, s, _first(s), _xset(), set())}
    assert got["Hall"] == "rain room for PE with 4A", got
    s["use_anyway"] = [["2026-10-05 09:00", "Hall"]]
    got = {r["name"]: r["busy"] for r in SE.rooms_free(_PUB, F.CAL, s, _first(s), _xset(), set())}
    assert got["Hall"] == "", got

@t
def a_lesson_with_two_rain_rooms_keeps_both():
    import copy
    pub = copy.deepcopy(_PUB); pub["model"]["lessons"][5]["rain"] = "Hall, LT2"
    s = _sit([_paper(who="level", date="2026-10-05", start="09:00")])
    got = {r["name"]: r["busy"] for r in SE.rooms_free(pub, F.CAL, s, _first(s), _xset(), set())}
    assert got["Hall"] == "rain room for PE with 4A" and got["LT2"] == "rain room for PE with 4A", got

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

@t
def combined_venue_and_its_part_not_both_used():
    import copy
    s = _sit([_paper(who="level", date="2026-10-06", start="08:00")])
    s["seating"]["home_rooms"] = False
    x = _xset(("LT1&2", "LT2")); x["rooms"]["LT1&2"]["seats"] = 50
    sit = _first(s)
    free = [r for r in SE.rooms_free(_PUB, F.CAL, s, sit, x, set()) if r["busy"] == ""]
    assert sorted(r["name"] for r in free) == ["LT1&2", "LT2"], free
    r = SE.seat(sit, SE.sitting_students(sit, s, _M), free, s, _M, {})
    assert [k for k, v in r["rooms"].items() if v] == ["LT1&2"] and len(r["unseated"]) == 10, r["unseated"]
    m = copy.deepcopy(_M); m["classes"][0]["home"] = "LT2"
    s["seating"]["home_rooms"] = True
    x = _xset(("LT1&2", "LT2"))
    free = [r for r in SE.rooms_free(dict(model=m), F.CAL, s, sit, x, set()) if r["busy"] == ""]
    r = SE.seat(sit, SE.sitting_students(sit, s, m), free, s, m, {})
    assert [k for k, v in r["rooms"].items() if v] == ["LT2"] and len(r["rooms"]["LT2"]) == 40 and len(r["unseated"]) == 20, r

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

def _overlaps(duties):
    return [(a["room"], b["room"], n) for i, a in enumerate(duties) for b in duties[i + 1:]
            if a["date"] == b["date"] and a["start"] < b["end"] and a["end"] > b["start"] for n in set(a["names"]) & set(b["names"])]

@t
def common_test_lesson_of_three_classes_is_one_teachers_one_room():
    import copy
    pub = copy.deepcopy(_PUB)
    pub["model"]["lessons"].append(F._lesson(10, 1, 2, 4, "Sec 3", ["3A", "3B", "4A"], "CCE", "Entire Class", ["Mr Ben Ong", "Ms Chloe Tan"], "Hall"))
    s = _sit([_paper(who="level", minutes=30, date="2026-10-06", start="08:40"),
              _paper(level="Sec 4", who="level", minutes=30, date="2026-10-06", start="08:40")],
             levels=["Sec 3", "Sec 4"], kind="test", supervision="lesson")
    x = _xset()
    MK.make(pub, F.CAL, s, x)
    d = s["made"]["duties"]
    assert {x["room"] for x in d} == {"3-01", "3-02", "4-01"}, d
    assert _overlaps(d) == [], _overlaps(d)
    own = [(x["room"], n) for x in d for n, why in x["reasons"].items() if why == "supervises their own lesson"]
    assert sorted(n for _, n in own) == ["Mr Ben Ong", "Ms Chloe Tan"] and len({r for r, _ in own}) == 2, own
    rest = next(x for x in d if not any(v == "supervises their own lesson" for v in x["reasons"].values()))
    assert len(rest["names"]) == 2 and rest["short"] == 0, rest

@t
def common_test_teacher_not_free_is_not_used_and_halls_get_invigilators():
    s = _sit([_paper(subject="Mathematics", minutes=30, date="2026-10-05", start="07:50")], kind="test", supervision="lesson")
    x = _xset(); x["never"] = ["Ms Chloe Tan"]
    d, _ = _duties(s, xset=x)
    duty = next(y for y in d if y["room"] == "3-02")
    assert "Ms Chloe Tan" not in duty["names"] and duty["need"] == 2 and len(duty["names"]) == 2, duty
    s["seating"]["home_rooms"] = False
    d, _ = _duties(s, rooms=("Hall",))
    assert d[0]["room"] == "Hall" and d[0]["need"] == 2 and "supervises their own lesson" not in d[0]["reasons"].values(), d[0]

@t
def hall_chief_comes_from_the_chiefs_list():
    s = _sit([_paper(who="level", date="2026-10-05", start="07:50")])
    s["seating"]["home_rooms"] = False
    x = _xset(); x["chiefs"] = ["Mr Hafiz Rahman"]
    d, _ = _duties(s, rooms=("Hall",), xset=x)
    assert d[0]["room"] == "Hall" and d[0]["need"] == 3 and d[0]["chief"] == "Mr Hafiz Rahman" and "Mr Hafiz Rahman" in d[0]["names"], d[0]
    d, _ = _duties(s, rooms=("Hall",))
    assert d[0]["chief"] == d[0]["names"][0] and "Mr Hafiz Rahman" not in d[0]["names"], d[0]

@t
def locked_names_kept():
    s = _sit([_paper(who="level", date="2026-10-05", start="07:50")])
    s["pins"]["duties"] = {"2026-10-05 07:50|3-01": ["Ms Grace Yeo"]}
    d, _ = _duties(s)
    d1 = d[0]
    assert d1["names"] == ["Ms Grace Yeo"] and d1["need"] == 2 and d1["short"] == 1 and d1["locked"] is True, d1
    assert IV.duty_minutes(d)["Ms Grace Yeo"] == 85
    s["pins"]["duties"] = {"2026-10-05 07:50|3-01": ["Ms Grace Yeo", "Mr Gone Away"]}
    d1 = _duties(s)[0][0]
    assert "Ms Grace Yeo" in d1["names"] and "Mr Gone Away" not in d1["names"] and len(d1["names"]) == d1["need"] == 2, d1
    assert d1["short"] == 0 and d1["locked"] is True and len(set(d1["names"])) == 2

def _made_sched(**kw):
    s = _sit([_paper(subject="English", date="2026-10-05", start="07:50"),
              _paper(subject="Pure Chemistry", date="2026-10-05", start="10:00")], days=dict(SEC3))
    s.update(kw)
    return s

def _mk(s, only=None, rooms=("3-01", "3-02", "4-01", "Hall")):
    return MK.make(_PUB, F.CAL, s, _xset(rooms), only=only, elsewhere=[])

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

def _duty(s, key, room):
    return next(x for x in s["made"]["duties"] if x["key"] == key and x["room"] == room)

@t
def cross_leaves_short_by_one_and_the_name_stays_off():
    s = _mk(_made_sched())
    key = "2026-10-05 07:50"
    first, second = _duty(s, key, "3-01")["names"]
    MK.set_invigilators(s, key, "3-01", [first])
    _mk(s, only=key)
    d = _duty(s, key, "3-01")
    assert d["names"] == [first] and d["short"] == 1 and d["locked"] is True, d
    _mk(s)
    d = _duty(s, key, "3-01")
    assert d["names"] == [first] and second not in d["names"] and d["short"] == 1, d
    assert MK.summary(_PUB, F.CAL, s, _xset())["counts"]["short"] == 1
    MK.set_invigilators(s, key, "3-01", None)
    assert key + "|3-01" not in s["pins"]["duties"]
    _mk(s, only=key)
    d = _duty(s, key, "3-01")
    assert len(d["names"]) == 2 and d["short"] == 0 and d["locked"] is False, d

@t
def a_name_that_left_is_replaced_and_the_replacement_kept():
    s = _mk(_made_sched())
    key = "2026-10-05 07:50"
    MK.set_invigilators(s, key, "3-01", ["Ms Grace Yeo", "Mr Gone Away"])
    _mk(s)
    d = _duty(s, key, "3-01")
    assert d["names"][0] == "Ms Grace Yeo" and len(d["names"]) == 2 and "Mr Gone Away" not in d["names"] and d["short"] == 0, d
    assert d["locked"] is True and s["made"]["gone"] == ["Mr Gone Away is no longer on the timetable."]
    assert s["pins"]["duties"][key + "|3-01"] == d["names"], s["pins"]["duties"]
    _mk(s)
    assert _duty(s, key, "3-01")["names"] == d["names"] and s["made"]["gone"] == []

@t
def hand_picked_names_are_checked():
    s = _mk(_sit([_paper(who="level", date="2026-10-05", start="07:50")], days=dict(SEC3)))
    key = "2026-10-05 07:50"
    MK.set_invigilators(s, key, "3-01", ["Mr Daniel Koh"])
    _mk(s, only=key)
    d = _duty(s, key, "3-01")
    assert d["names"] == ["Mr Daniel Koh"] and d["backup"] == {"Mr Daniel Koh": [2]}, d
    assert d["reasons"]["Mr Daniel Koh"] == "chosen by hand; teaches 4A Mathematics 08:00–08:40: needs a backup", d["reasons"]
    assert MK.summary(_PUB, F.CAL, s, _xset())["counts"]["backups"] >= 1
    other = _duty(s, key, "3-02")["names"]
    MK.set_invigilators(s, key, "3-01", ["Mr Ivan Lee", other[0]])
    MK.set_invigilators(s, key, "3-02", [other[0]])
    _mk(s, only=key)
    d = _duty(s, key, "3-01")
    assert d["names"] == ["Mr Ivan Lee", other[0]], d
    assert d["not_free"] == {"Mr Ivan Lee": "is not available then (a Must rule)", other[0]: "is on another duty then (3-02)"}, d["not_free"]
    assert _duty(s, key, "3-02")["not_free"] == {other[0]: "is on another duty then (3-01)"}
    x = _xset(); x["never"] = ["Mr Ivan Lee"]
    MK.make(_PUB, F.CAL, s, x, only=key)
    assert _duty(s, key, "3-01")["not_free"]["Mr Ivan Lee"] == "is on the never list"

@t
def only_keeps_the_other_sittings_duties_as_they_were():
    s = _mk(_made_sched())
    later = "2026-10-05 10:00"
    before = [x for x in s["made"]["duties"] if x["key"] == later]
    _mk(s, only="2026-10-05 07:50")
    assert [x for x in s["made"]["duties"] if x["key"] == later] == before
    assert later + "|3-01" not in s["pins"]["duties"] and not any(k.startswith(later) for k in s["pins"]["duties"])

@t
def remaking_one_sitting_leaves_a_later_sittings_room():
    papers = [_paper(minutes=120, date="2026-10-06", start="08:00", who="students", students=["3A-%02d" % i for i in range(1, 31)]),
              _paper(subject="Mathematics", date="2026-10-06", start="09:00", who="students", students=["3B-%02d" % i for i in range(1, 31)])]
    s = _sit(papers, days={"2026-10-06": dict(levels=["Sec 3"], whole=True)})
    s["seating"]["home_rooms"] = False
    x = ES.defaults()
    x["rooms"] = {"Hall": dict(seats=40, rows=None, cols=None, hall=True, access=False, note=""),
                  "Lab 3-08": dict(seats=40, rows=None, cols=None, hall=False, access=False, note="")}
    MK.make(_PUB, F.CAL, s, x)
    first, later = "2026-10-06 08:00", "2026-10-06 09:00"
    assert list(s["made"]["seats"][first]) == ["Hall"] and list(s["made"]["seats"][later]) == ["Lab 3-08"], s["made"]["seats"]
    assert MK.held(_PUB, s, x) == {first: {"Lab 3-08"}, later: {"Hall"}}
    got = {r["name"]: r["busy"] for r in SE.rooms_free(_PUB, F.CAL, s, SE.sittings(s)[0], x, MK.held(_PUB, s, x)[first])}
    assert got == {"Hall": "", "Lab 3-08": "used by another sitting"}, got
    MK.move(s, first, ["3A-01"], "Lab 3-08")
    MK.make(_PUB, F.CAL, s, x, only=first)
    assert list(s["made"]["seats"][first]) == ["Hall"] and list(s["made"]["seats"][later]) == ["Lab 3-08"], s["made"]["seats"]

@t
def a_change_after_make_is_stale():
    x = _xset(("3-01", "3-02", "4-01", "Hall"))
    s = _mk(_made_sched())
    assert MK.stale(s, x, _M) is False and s["made"]["fingerprint"] == MK.fingerprint(s, x, _M)
    s["papers"][0]["minutes"] = 70
    assert MK.stale(s, x, _M) is True
    _mk(s, only="2026-10-05 07:50")
    assert MK.stale(s, x, _M) is True, "a one-sitting Make keeps the other sitting as it was"
    _mk(s)
    assert MK.stale(s, x, _M) is False
    for k, v in (("seating", dict(s["seating"], spacing="gap")), ("access", [dict(student="3A-01", extra=25)]), ("supervision", "lesson"),
                 ("days", {}), ("classes", ["3A"]), ("levels", ["Sec 3", "Sec 4"])):
        assert MK.stale(dict(s, **{k: v}), x, _M) is True, k
    x2 = _xset(("3-01", "3-02", "4-01")); assert MK.stale(s, x2, _M) is True
    assert MK.stale(dict(s, name="Another name", times=dict(s["times"], report="07:00")), x, _M) is False
    assert MK.stale(dict(s, made=None), x, _M) is False

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
def gone_is_named_before_make_again():
    import copy
    s = _mk(_made_sched())
    key = "2026-10-05 07:50"
    picked = _duty(s, key, "3-01")["names"][0]
    MK.set_invigilators(s, key, "3-02", ["Mr Ivan Lee"])
    pub = copy.deepcopy(_PUB); m = pub["model"]
    for k in ("teachers",):
        m[k] = [x for x in m[k] if x["name"] not in (picked, "Mr Ivan Lee")]
    m["setup"]["teachers"] = [x for x in m["setup"]["teachers"] if x["name"] not in (picked, "Mr Ivan Lee")]
    m["students"] = [x for x in m["students"] if x["id"] != "3A-02"]
    MK.move(s, key, ["3A-03"], "3-02")
    m["students"] = [x for x in m["students"] if x["id"] != "3A-03"]
    got = MK.summary(pub, F.CAL, s, _xset())["gone"]
    assert sorted(got) == sorted("%s is no longer on the timetable." % x for x in ("3A-02", "3A-03", picked, "Mr Ivan Lee")), got
    MK.make(pub, F.CAL, s, _xset(("3-01", "3-02", "4-01", "Hall")))
    MK.make(pub, F.CAL, s, _xset(("3-01", "3-02", "4-01", "Hall")))
    assert MK.summary(pub, F.CAL, s, _xset())["gone"] == []

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
        assert s.get("/api/exams/me").get_json() == dict(name="Ms Grace Yeo", can_use=False, can_approve=False)
        assert s.get("/api/exams/settings").status_code == 403
        c = committee()
        assert c.get("/api/exams").status_code == 200
        assert c.get("/api/exams/me").get_json() == dict(name="Timetable committee", can_use=True, can_approve=True)
        d = c.get("/api/exams/settings").get_json()
        assert d["settings"]["committee"] == [] and {"name": "Hall", "kind": "pe venue", "capacity": 400} in [dict(zip(("name", "kind", "capacity"), r)) if isinstance(r, list) else r for r in d["rooms"]], d["rooms"]
        d["settings"]["committee"] = ["Ms Grace Yeo"]
        r = c.put("/api/exams/settings", json=d["settings"]); assert r.status_code == 200, r.data
        assert s.get("/api/exams").status_code == 200
        assert s.get("/api/exams/me").get_json()["can_use"] is True
        assert s.get("/exams").status_code == 200 and s.get("/exams/settings").status_code == 200
        mine = s.get("/api/exams/settings").get_json()
        assert mine["committee_ok"] is False and d["committee_ok"] is True
        for names in (["Ms Grace Yeo", "Mr Ben Ong"], []):
            r = s.put("/api/exams/settings", json=dict(mine["settings"], committee=names, backups=["Mr Ivan Lee"]))
            assert r.status_code == 200 and r.get_json()["settings"]["committee"] == ["Ms Grace Yeo"], r.data
            assert ES.load(_PUB)["committee"] == ["Ms Grace Yeo"] and ES.load(_PUB)["backups"] == ["Mr Ivan Lee"]
        r = c.put("/api/exams/settings", json=dict(mine["settings"], committee=["Ms Grace Yeo", "Mr Ben Ong"]))
        assert r.status_code == 200 and ES.load(_PUB)["committee"] == ["Ms Grace Yeo", "Mr Ben Ong"]
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
        assert d1["names"] == ["Mr Ivan Lee"] and d1["locked"] is True and d1["short"] == 1, d1
        r = c.post(f"/api/exams/{s['id']}/invigilators", json=dict(key=key, room="3-01", names=None)); assert r.status_code == 200, r.data
        d1 = next(x for x in r.get_json()["made"]["duties"] if x["key"] == key and x["room"] == "3-01")
        assert d1["locked"] is False and d1["short"] == 0 and key + "|3-01" not in c.get(f"/api/exams/{s['id']}").get_json()["pins"]["duties"], d1
        assert c.post(f"/api/exams/{s['id']}/invigilators", json=dict(key=key, room="3-01", names="x")).status_code == 400
        r = c.post(f"/api/exams/{s['id']}/invigilators", json=dict(key=key, room="3-01", names=["Mr Ivan Lee"])); assert r.status_code == 200
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
        s["papers"] = [dict(p, date="2026-10-05", start="09:00") for p in s["papers"] if p["subject"] == "English"]
        s["papers"] += [dict(s["papers"][0], id="zz", subject="Mathematics", start="09:30")]
        assert c.put("/api/exams/" + s["id"], json=s).status_code == 200
        assert c.post(f"/api/exams/{s['id']}/make", json={}).status_code == 200
        v = c.get(f"/api/exams/{s['id']}/view").get_json()
        first = {n: busy for n, _, busy in v["rooms_by_key"]["2026-10-05 09:00"]}
        later = set(v["made"]["seats"]["2026-10-05 09:30"])
        assert later and all(first[n] == "used by another sitting" for n in later), (first, later)

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
        assert c.put("/api/exams/" + s["id"], json=dict(kept, kind="party")).status_code == 400 and SC.load(s["id"])["kind"] == "exam"
        broken = dict(SC.load(s["id"]), papers=[dict(kept["papers"][0], minutes="sixty")])
        store.write_json(os.path.join(SC.DIR, s["id"] + ".json"), broken)
        r = c.get(f"/api/exams/{s['id']}/view")
        assert r.status_code == 400 and r.get_json() == {"error": "Check the exam and try again."}, (r.status_code, r.data[:200])

def _made_exam(c, mutate=None):
    s = _exam(c)
    times = {"English": "07:50", "Pure Chemistry": "10:00"}
    s["papers"] = [dict(p, date="2026-10-05", start=times[p["subject"]]) for p in s["papers"] if p["subject"] in times]
    assert c.put("/api/exams/" + s["id"], json=s).status_code == 200
    assert c.post(f"/api/exams/{s['id']}/make", json={}).status_code == 200
    return s

import exams.printouts as PR  # noqa: E402

@t
def printout_titles_use_the_page_words():
    import io
    assert PR.TITLES == {"seating": "Seating plan", "doors": "Door list", "attendance": "Attendance sheet", "classes": "Class lists",
                         "roster-day": "Roster by day", "roster-teacher": "Roster by teacher", "timetable": "Exam timetable"}
    assert set(PR.TITLES) == set(PR.WHATS)
    assert PR._day("2026-10-05") == "Mon 5 Oct" and PR._day("2026-11-01") == "Sun 1 Nov"
    assert PR._sitting_title(dict(date="2026-10-05", start=470), "Hall") == "Mon 5 Oct · 07:50 · Hall"
    assert PR._Doc(_PUB, dict(name="Sec 3 Exam"), "roster-day", io.BytesIO()).head == "Sample School · Sec 3 Exam · Roster by day"

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
            title = PR.TITLES[what]
            assert f"Sec 3 Exam {title}.pdf" in r.headers["Content-Disposition"] and r.headers["Content-Disposition"].startswith("inline"), r.headers["Content-Disposition"]
        assert c.get(f"/api/exams/{s['id']}/print/nothing.pdf").status_code == 404
        assert c.get(f"/api/exams/{s['id']}/view").get_json()["stale"] is False
        now = c.get(f"/api/exams/{s['id']}").get_json()
        assert c.put("/api/exams/" + s["id"], json=dict(now, papers=[dict(now["papers"][0], minutes=50)] + now["papers"][1:])).status_code == 200
        assert c.get(f"/api/exams/{s['id']}/view").get_json()["stale"] is True
        for url in ("print/seating.pdf", "download.xlsx"):
            r = c.get(f"/api/exams/{s['id']}/{url}")
            assert r.status_code == 409 and r.get_json() == {"error": "The exam changed since Make: press Make again."}, (url, r.data[:100])
        assert c.post(f"/api/exams/{s['id']}/make", json={}).status_code == 200
        assert c.get(f"/api/exams/{s['id']}/view").get_json()["stale"] is False
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

def _page(name):
    with open(os.path.join(ROOT, "static", name), encoding="utf-8") as f:
        return f.read()

@t
def the_pages_carry_the_words():
    assert "Only the timetable committee can change this list." in _page("exams-settings.js")
    js = _page("exams.js")
    for words in ("How to seat", "Own class in own home room", "Mix classes", "Alternate levels by column", "Alternate papers",
                  "One level per block", "Class, then Student ID", "Every seat", "A seat left between", "Let the app choose",
                  "Not free: ", "The exam changed since Make: press Make again.",
                  "The published timetable has no students yet: add them on the Students step and publish again to check clashes and seat students.",
                  "lessons outside "):
        assert words in js, words

NOW = "2026-10-01T09:00:00"

def _approved(access=None, rooms=None):
    s = _made_sched()
    if access is not None: s["access"] = list(access)
    s = _mk(s) if rooms is None else _mk(s, rooms=rooms)
    AP.send(s, _M, "Ms Grace Yeo", NOW, False, [])
    AP.approve(s, "Timetable committee", NOW)
    return s

@t
def dates_read_as_on_the_page():
    assert D.nice("2026-10-05") == "Mon 5 Oct" and D.nice("2026-10-02T09:30:00") == "Fri 2 Oct"
    assert PR._day("2026-11-01") == "Sun 1 Nov" and D.nice("soon") == "soon"

@t
def states_and_labels():
    s = _mk(_made_sched())
    assert AP.label(s, date(2026, 10, 1)) == "Draft"
    AP.send(s, _M, "Ms Grace Yeo", NOW, False, [])
    assert s["status"] == "waiting" and s["sent_by"] == "Ms Grace Yeo" and s["log"][-1]["what"] == "sent"
    assert AP.label(s, date(2026, 10, 1)) == "Waiting for the timetable committee"
    AP.approve(s, "Timetable committee", NOW)
    assert s["status"] == "approved" and s["approved"]["papers"] == s["papers"]
    assert s["approved"]["made"]["duties"] == s["made"]["duties"]
    assert set(s["approved"]["made"]) == {"seats", "unseated", "duties", "published_at"}
    assert AP.as_schedule(s)["id"] == s["id"] and AP.as_schedule(s)["status"] == "approved"
    assert AP.label(s, date(2026, 10, 6)) == "Approved · on the main site"
    assert AP.label(s, date(2026, 10, 7)) == "Ended"
    assert AP.as_schedule(_made_sched()) is None

@t
def send_needs_make_fresh_and_no_errors():
    assert AP.blocked(_made_sched(), _M, False, []) == "Press Make first."
    s = _mk(_made_sched())
    assert AP.blocked(s, _M, True, []) == "The exam changed since Make: press Make again."
    assert AP.blocked(s, _M, False, ["X."]) == "Fix the paper times first: X."
    raises(ValueError, lambda: AP.send(s, _M, "x", NOW, False, ["X."]), "Fix the paper times first: X.")
    raises(ValueError, lambda: AP.send(s, _M, "x", NOW, True, []), "The exam changed since Make: press Make again.")
    assert s["status"] == "draft"
    a = _approved()
    assert AP.blocked(a, _M, False, []) == "Nothing on the main site changes."
    raises(ValueError, lambda: AP.send(a, _M, "x", NOW, False, []), "Nothing on the main site changes.")

@t
def send_back_and_withdraw():
    s = _mk(_made_sched())
    raises(ValueError, lambda: AP.approve(s, "x", NOW), "There is nothing waiting for approval.")
    AP.send(s, _M, "Ms Grace Yeo", NOW, False, [])
    AP.send(s, _M, "Ms Grace Yeo", NOW, False, [])
    assert s["log"][-1]["what"] == "sent again"
    raises(ValueError, lambda: AP.send_back(s, "  ", "x", NOW), "Write a note for the exams committee.")
    AP.send_back(s, " 2C has a WA then ", "Timetable committee", NOW)
    assert s["status"] == "draft" and AP.label(s, date(2026, 10, 1)) == "Sent back" and s["note"] == "2C has a WA then"
    assert s["log"][-1]["detail"] == "2C has a WA then"
    AP.send(s, _M, "Ms Grace Yeo", NOW, False, [])
    assert s["note"] == ""
    AP.approve(s, "Timetable committee", NOW)
    AP.withdraw(s, "Timetable committee", NOW)
    assert s["approved"] is None and s["status"] == "withdrawn" and AP.label(s, date(2026, 10, 1)) == "Withdrawn"
    raises(ValueError, lambda: AP.withdraw(s, "x", NOW), "This schedule is not on the main site.")

@t
def approve_refuses_a_change_after_sending():
    s = _mk(_made_sched())
    AP.send(s, _M, "Ms Grace Yeo", NOW, False, [])
    s["papers"][0]["minutes"] = 50
    raises(ValueError, lambda: AP.approve(s, "x", NOW), "This schedule changed after it was sent. Ask the exams committee to send it again.")

KEY1 = "2026-10-05 07:50"

@t
def changes_list_what_shows():
    s = _approved()
    MK.set_invigilators(s, KEY1, "3-01", ["Ms Aisha Rahman", "Mr Hafiz Rahman"])
    _mk(s, only=KEY1)
    s["name"] = "Sec 3 EOY Exam"
    s["times"]["report"] = "07:20"
    next(p for p in s["papers"] if p["subject"] == "Pure Chemistry")["start"] = "10:20"
    assert [c["text"] for c in AP.changes(s, _M)] == [
        "Name: Sec 3 End-of-Year Exam → Sec 3 EOY Exam.", "Report time: 07:30 → 07:20.",
        "Sec 3 Pure Chemistry Paper 1: Mon 5 Oct 10:00–11:00 → Mon 5 Oct 10:20–11:20.",
        "Mon 5 Oct 07:50, 3-01: Ms Chloe Tan → Mr Hafiz Rahman (invigilator)."], [c["text"] for c in AP.changes(s, _M)]

@t
def changes_list_a_moved_student():
    s = _approved()
    MK.move(s, KEY1, ["3A-07"], "3-02")
    _mk(s, only=KEY1)
    assert [c["text"] for c in AP.changes(s, _M)] == [
        "Mon 5 Oct 07:50, 3-02: no one → Mr Ben Ong, Mr Hafiz Rahman (invigilators).",
        "Mon 5 Oct 07:50, 3A: 3-01 → 3-01 (29), 3-02 (1).", "Mon 5 Oct 07:50: 23 students have a new seat."], [c["text"] for c in AP.changes(s, _M)]
    AP.send(s, _M, "Ms Grace Yeo", NOW, False, [])
    assert s["status"] == "changes" and s["log"][-1] == dict(at=NOW, by="Ms Grace Yeo", what="changes sent", detail="3 changes")

@t
def someone_away_goes_on_at_once():
    s = _approved()
    got = AP.replace(s, KEY1, "3-01", "Ms Chloe Tan", "Mr Hafiz Rahman", "Ms Grace Yeo", NOW)
    assert got == "Mon 5 Oct 07:35–09:00, 3-01: Ms Chloe Tan (away) → Mr Hafiz Rahman", got
    for d in (_duty(s, KEY1, "3-01"), next(x for x in s["approved"]["made"]["duties"] if x["key"] == KEY1 and x["room"] == "3-01")):
        assert d["names"] == ["Ms Aisha Rahman", "Mr Hafiz Rahman"] and d["reasons"]["Mr Hafiz Rahman"] == "replaces Ms Chloe Tan, who is away", d
        assert "Ms Chloe Tan" not in d["reasons"]
    assert s["pins"]["duties"][KEY1 + "|3-01"] == ["Ms Aisha Rahman", "Mr Hafiz Rahman"] == s["approved"]["pins"]["duties"][KEY1 + "|3-01"]
    assert s["status"] == "approved" and AP.changes(s, _M) == [] and AP.done_without(s)[0]["by"] == "Ms Grace Yeo"
    raises(ValueError, lambda: AP.replace(s, KEY1, "3-01", "Mr Ben Ong", "Mr Ivan Lee", "x", NOW), "Mr Ben Ong is not on that duty.")
    raises(ValueError, lambda: AP.replace(s, KEY1, "3-01", "Ms Aisha Rahman", "Mr Hafiz Rahman", "x", NOW), "Mr Hafiz Rahman is on that duty already.")
    raises(ValueError, lambda: AP.replace(s, KEY1, "Hall", "Ms Aisha Rahman", "Mr Ivan Lee", "x", NOW), "That duty is not on the main site.")
    raises(ValueError, lambda: AP.replace(_mk(_made_sched()), KEY1, "3-01", "Ms Chloe Tan", "Mr Ivan Lee", "x", NOW), "This schedule is not on the main site.")

@t
def an_away_replacement_keeps_a_sent_schedule_approvable():
    s = _approved()
    s["papers"][1]["start"] = "10:20"
    _mk(s, only="2026-10-05 10:00")
    AP.send(s, _M, "Ms Grace Yeo", NOW, False, [])
    sent = s["sent_fp"]
    AP.replace(s, KEY1, "3-01", "Ms Chloe Tan", "Mr Hafiz Rahman", "Ms Grace Yeo", NOW)
    assert s["sent_fp"] == AP.fp(s) != sent
    AP.approve(s, "Timetable committee", NOW)
    assert s["status"] == "approved"


import copy  # noqa: E402

def _days_view(s):
    return D.day_view(_PUB, F.CAL, s, "2026-10-05")

@t
def other_schedules_take_rooms_and_people():
    s = _sit([_paper(date="2026-10-05", start="07:50")], days=dict(SEC3))
    busy = [dict(id="b", name="Sec 4 Exam", status="approved", date="2026-10-05", start=455, end=540, room="Hall", names=["Mr Hafiz Rahman"])]
    sit = _first(s)
    r = SE.rooms_free(_PUB, F.CAL, s, sit, _xset(("Hall",)), set(), elsewhere=busy)
    assert r[0]["busy"] == "taken by Sec 4 Exam until 09:00", r
    assert SE.rooms_free(_PUB, F.CAL, s, sit, _xset(("Hall",)), set())[0]["busy"] == ""
    got = IV.candidates(_PUB, F.CAL, s, _xset(), "2026-10-05", 455, 540, [])
    assert "Mr Hafiz Rahman" in [c["name"] for g in got.values() for c in g] and "Mr Hafiz Rahman" in [c["name"] for c in got["free"]], got
    got = IV.candidates(_PUB, F.CAL, s, _xset(), "2026-10-05", 455, 540, [], elsewhere=busy)
    assert "Mr Hafiz Rahman" not in [c["name"] for g in got.values() for c in g], got
    assert IV._free("Mr Hafiz Rahman", _days_view(s), 455, 540, [], _xset(), elsewhere=busy)[0] == "is on Sec 4 Exam then (Hall)"
    m = MK.make(_PUB, F.CAL, s, _xset(("Hall",)), elsewhere=busy)["made"]
    assert len(m["unseated"][sit["key"]]) == 30 and not m["seats"][sit["key"]], m

def _stored(id, status, names, approved=None):
    s = _sit([_paper(date="2026-10-05", start="07:50")], days=dict(SEC3))
    s.update(id=id, name="Exam " + id, status=status)
    duty = lambda n: dict(key="2026-10-05 07:50", room="Hall", date="2026-10-05", start=455, end=540, names=n)
    s["made"] = dict(duties=[duty(names)],seats={}, unseated={})
    if approved:
        s["approved"] = dict(name="Exam " + id, made=dict(duties=[duty(approved)], seats={}, unseated={}))
    SC.save(s, _PUB, F.CAL, "t")

@t
def elsewhere_reads_waiting_and_approved_copies():
    for f in os.listdir(SC.DIR) if os.path.isdir(SC.DIR) else []: os.remove(os.path.join(SC.DIR, f))
    _stored("aaaa", "approved", ["X"], approved=["Ms Grace Yeo"])
    _stored("bbbb", "waiting", ["Mr Ben Ong"])
    _stored("cccc", "draft", ["Z"])
    _stored("dddd", "withdrawn", ["Z"])
    _stored("eeee", "changes", ["Y"], approved=["Mr Ivan Lee"])
    every = SC.elsewhere("zzzz")
    got = {b["id"]: b for b in every if b["status"] == "approved" or b["id"] != "eeee"}   # changes waiting: both copies (the fix wave)
    assert sorted(got) == ["aaaa", "bbbb", "eeee"], got
    assert [b["names"] for b in every if b["id"] == "eeee" and b["status"] == "waiting"] == [["Y"]], every
    assert got["aaaa"]["names"] == ["Ms Grace Yeo"] and got["aaaa"]["status"] == "approved" and got["aaaa"]["name"] == "Exam aaaa"
    assert got["bbbb"]["status"] == "waiting" and got["bbbb"]["names"] == ["Mr Ben Ong"] and got["bbbb"]["room"] == "Hall"
    assert got["eeee"]["status"] == "approved"
    assert got["eeee"]["names"] == ["Mr Ivan Lee"] and (got["bbbb"]["start"], got["bbbb"]["end"]) == (455, 540)
    assert "aaaa" not in {b["id"] for b in SC.elsewhere("aaaa")}
    assert sorted(x["id"] for x in SC.on_site()) == ["aaaa", "eeee"]
    assert SC.new("exam", "n", ["Sec 3"], "2026-10-05", "2026-10-06", "t", pub=_PUB)["scripts"] == ""
    bad = SC.new("exam", "n", ["Sec 3"], "2026-10-05", "2026-10-06", "t", pub=_PUB); bad["scripts"] = 5
    raises(ValueError, lambda: SC._check(bad, _PUB), SC.WRONG)
    ok = SC.new("exam", "n", ["Sec 3"], "2026-10-05", "2026-10-06", "t", pub=_PUB); del ok["scripts"]
    SC._check(ok, _PUB)
    for f in os.listdir(SC.DIR): os.remove(os.path.join(SC.DIR, f))

@t
def make_keeps_the_published_at():
    pub = copy.deepcopy(_PUB); pub["meta"]["published_at"] = "2026-10-01T08:00:00"
    s = MK.make(pub, F.CAL, _made_sched(), _xset(("3-01", "3-02", "4-01", "Hall")), elsewhere=[])
    assert s["made"]["published_at"] == "2026-10-01T08:00:00"
    assert _mk(_made_sched())["made"]["published_at"] is None

@t
def a_full_make_clears_a_pin_of_a_vanished_sitting():
    s = _mk(_made_sched())
    s["pins"]["duties"]["2026-10-05 09:00|3-01"] = ["Mr Gone Away"]
    _mk(s)
    assert "2026-10-05 09:00|3-01" not in s["pins"]["duties"] and MK.gone_now(_PUB, s) == [], s["pins"]

@t
def approved_make_keeps_unchanged_sittings():
    s = _approved()
    x = _xset(("3-01", "3-02", "4-01", "Hall")); x["never"] = ["Ms Aisha Rahman"]
    was = copy.deepcopy(s["approved"]["made"])
    s["papers"][1]["minutes"] = 50
    MK.make(_PUB, F.CAL, s, x, elsewhere=[])
    d = _duty(s, KEY1, "3-01")
    assert d["names"] == ["Ms Aisha Rahman", "Ms Chloe Tan"] and d["not_free"] == {"Ms Aisha Rahman": "is on the never list"}, d
    assert s["made"]["seats"][KEY1] == was["seats"][KEY1] and s["made"]["unseated"][KEY1] == was["unseated"][KEY1]
    assert _duty(s, "2026-10-05 10:00", "3-01")["end"] == 660
    assert s["approved"]["made"] == was
    t2 = _mk(_made_sched()); t2["papers"][1]["minutes"] = 50
    MK.make(_PUB, F.CAL, t2, x, elsewhere=[])
    assert "Ms Aisha Rahman" not in _duty(t2, KEY1, "3-01")["names"]

@t
def approved_make_keeps_the_names_of_a_changed_sitting():
    s = _approved()
    key2 = "2026-10-05 10:00"
    was = {d["room"]: list(d["names"]) for d in s["approved"]["made"]["duties"] if d["key"] == key2}
    s["papers"][1]["minutes"] = 50
    MK.make(_PUB, F.CAL, s, _xset(("3-01", "3-02", "4-01", "Hall")), elsewhere=[])
    now = {d["room"]: list(d["names"]) for d in s["made"]["duties"] if d["key"] == key2}
    assert now == was, (now, was)
    assert not s["pins"]["duties"], s["pins"]

@t
def approved_make_after_a_new_timetable_flags_the_clash():
    s = _approved()
    pub2 = copy.deepcopy(_PUB)
    pub2["model"]["lessons"].append(F._lesson(10, 0, 2, 2, "Sec 4", ["4A"], "Science", "Entire Class", ["Ms Aisha Rahman"], "LT2"))
    MK.make(pub2, F.CAL, s, _xset(("3-01", "3-02", "4-01", "Hall")), elsewhere=[])
    d = _duty(s, KEY1, "3-01")
    assert d["names"] == ["Ms Aisha Rahman", "Ms Chloe Tan"] and d["backup"] == {"Ms Aisha Rahman": [10]}, d

@t
def a_schedule_with_nothing_approved_is_made_whole():
    s = _mk(_made_sched()); s["approved"] = None
    assert _mk(s)["made"]["duties"]

@t
def a_never_list_clash_in_a_kept_duty_is_flagged_without_mk():
    s = _approved()
    s["made"] = copy.deepcopy(s["approved"]["made"])
    for d in s["made"]["duties"]: d["not_free"] = {}
    x = _xset(("3-01", "3-02", "4-01", "Hall")); x["never"] = ["Ms Chloe Tan"]
    IV.recheck(_PUB, F.CAL, s, x, s["made"]["duties"], s["made"]["duties"], elsewhere=[])
    assert _duty(s, KEY1, "3-01")["not_free"] == {"Ms Chloe Tan": "is on the never list"}


@t
def approved_make_does_not_keep_someone_who_teaches_the_new_subject():
    key2 = "2026-10-05 10:00"
    def names(rule):
        s = _approved()
        assert "Mr Ben Ong" in [n for d in s["approved"]["made"]["duties"] if d["key"] == key2 for n in d["names"]]
        x = _xset(("3-01", "3-02", "4-01", "Hall")); x["rules"]["not_own_subject"] = rule
        s["papers"][1]["paper"] = "Paper 2"   # a changed paper: Mr Ben Ong teaches Pure Chemistry
        MK.make(_PUB, F.CAL, s, x, elsewhere=[])
        return [n for d in s["made"]["duties"] if d["key"] == key2 for n in d["names"]]
    assert "Mr Ben Ong" in names(False) and "Mr Ben Ong" not in names(True)

import exams.review as RV  # noqa: E402

def _waiting():
    s = _mk(_made_sched())
    AP.send(s, _M, "Ms Grace Yeo", NOW, False, [])
    return s

_X4 = ("3-01", "3-02", "4-01", "Hall")

@t
def review_of_a_waiting_schedule():
    s = _waiting()
    r = RV.review(_PUB, F.CAL, s, _xset(_X4), [])
    assert r["copy"] == "working" and r["changes"] == [] and r["done_without"] == []
    w = r["what"]
    assert w["classes"] == ["3A", "3B"] and w["levels"] == ["Sec 3"] and w["papers"] == 2 and w["stopped"] == 5, w
    assert w["teachers"] == 6 and w["duties"] == 3 and w["most"] == ["Mr Ben Ong", 1] and w["backups"] == 0 and w["anyway"] == [], w
    assert w["venues"] == [dict(room="3-01", dates=1, start="07:35", end="11:10"), dict(room="3-02", dates=1, start="09:45", end="11:10")], w["venues"]
    assert [c["key"] for c in r["checks"]] == ["papers", "seats", "free", "others", "timetable"], r["checks"]
    assert all(c["ok"] for c in r["checks"]), r["checks"]
    assert r["checks"][2]["lines"] == ["Every invigilator is free then."]

@t
def review_after_a_new_timetable():
    pub1 = copy.deepcopy(_PUB); pub1["meta"]["published_at"] = "2026-10-01T08:00:00"
    s = MK.make(pub1, F.CAL, _made_sched(), _xset(_X4), elsewhere=[])
    AP.send(s, _M, "Ms Grace Yeo", NOW, False, []); AP.approve(s, "Timetable committee", NOW)
    pub2 = copy.deepcopy(pub1); pub2["meta"]["published_at"] = "2026-10-02T09:30:00"
    pub2["model"]["lessons"].append(F._lesson(10, 0, 2, 2, "Sec 4", ["4A"], "Science", "Entire Class", ["Ms Aisha Rahman"], "LT2"))
    assert RV.review(pub1, F.CAL, s, _xset(_X4), [])["checks"][4]["ok"]
    r = RV.review(pub2, F.CAL, s, _xset(_X4), [])
    assert r["copy"] == "approved"
    assert r["checks"][4]["lines"] == ["The timetable changed since this was made: a new timetable was published on Fri 2 Oct. "
                                       "Ask the exams committee to make it again."], r["checks"][4]
    assert r["checks"][2]["lines"] == ["Ms Aisha Rahman, 3-01 on Mon 5 Oct 07:35\u201309:00: teaches 4A Science 08:20\u201309:00."], r["checks"][2]

@t
def review_names_other_schedules():
    s = _waiting()
    other = [dict(id="b", name="Sec 4 Exam", status="waiting", date="2026-10-05", start=500, end=560, room="3-01",
                  names=["Ms Aisha Rahman", "Mr Ben Ong"])]
    c = RV.review(_PUB, F.CAL, s, _xset(_X4), other)["checks"]
    assert c[3]["ok"] is False and c[3]["lines"] == ["Sec 4 Exam (waiting) takes 1 of these invigilators on Mon 5 Oct.",
                                                      "Sec 4 Exam (waiting) uses 3-01 on Mon 5 Oct too."], c[3]

@t
def review_counts_seats_and_short_places():
    s = _waiting()
    s["made"]["unseated"][KEY1] = ["3A-30"]
    _duty(s, KEY1, "3-01")["short"] = 1
    c = RV.review(_PUB, F.CAL, s, _xset(_X4), [])["checks"]
    assert c[1]["lines"] == ["1 student has no seat."] and not c[1]["ok"]
    assert c[2]["lines"][-1] == "3-01 on Mon 5 Oct 07:35\u201309:00 is short by 1.", c[2]
    s["made"]["unseated"][KEY1] = ["3A-30", "3A-29"]
    assert RV.review(_PUB, F.CAL, s, _xset(_X4), [])["checks"][1]["lines"] == ["2 students have no seat."]

@t
def review_of_changes_lists_them():
    s = _approved()
    MK.move(s, KEY1, ["3A-07"], "3-02")
    _mk(s, only=KEY1)
    AP.send(s, _M, "Ms Grace Yeo", NOW, False, [])
    r = RV.review(_PUB, F.CAL, s, _xset(_X4), [])
    assert r["copy"] == "working" and [c["text"] for c in r["changes"]] == [c["text"] for c in AP.changes(s, _M)] and len(r["changes"]) == 3

@t
def review_and_gone_list_agree_for_kept_sittings():
    s = _approved()
    pub2 = copy.deepcopy(_PUB)
    gone = "Ms Chloe Tan"
    for l in pub2["model"]["lessons"]:
        l["teachers"] = [x for x in l["teachers"] if x != gone]
    pub2["model"]["teachers"] = [x for x in pub2["model"]["teachers"] if x["name"] != gone]
    pub2["model"]["setup"]["teachers"] = [x for x in pub2["model"]["setup"]["teachers"] if x["name"] != gone]
    MK.make(pub2, F.CAL, s, _xset(_X4), elsewhere=[])
    assert _duty(s, KEY1, "3-01")["names"].count(gone) == 1, "kept sitting keeps the name"
    line = "%s is no longer on the timetable." % gone
    for sch in (s, dict(s, status="waiting")):
        got = RV.review(pub2, F.CAL, sch, _xset(_X4), [])["checks"][2]
        assert line in got["lines"] and not got["ok"], got
    assert line in MK.summary(pub2, F.CAL, s, _xset(_X4))["gone"]

# ---- the approval routes
@contextlib.contextmanager
def _today(d):
    old = A._exams_today; A._exams_today = lambda: d
    try: yield
    finally: A._exams_today = old

def _committee_of(*names):
    x = _xset(("3-01", "3-02", "4-01", "Hall"))
    os.makedirs(os.path.dirname(ES.PATH), exist_ok=True)
    store.write_json(ES.PATH, dict(committee=list(names), rooms=x["rooms"]))

def _approved_exam(c):
    s = _made_exam(c)
    r = c.post(f"/api/exams/{s['id']}/send"); assert r.status_code == 200, r.data
    r = c.post(f"/api/exams/{s['id']}/approve"); assert r.status_code == 200, r.data
    return s

def _setup():
    _reset(); _cal(); _committee_of("Ms Grace Yeo")

@t
def send_and_approve_by_the_right_people():
    _setup()
    with published(_PUB):
        c = committee(); g = staff("Ms Grace Yeo")
        s = _made_exam(g); id = s["id"]
        r = g.post(f"/api/exams/{id}/send"); assert r.status_code == 200, r.data
        assert r.get_json()["label"] == "Waiting for the timetable committee" and r.get_json()["status"] == "waiting"
        r = g.post(f"/api/exams/{id}/approve"); assert r.status_code == 403 and r.get_json() == {"error": A.ONLY_APPROVE}, r.data
        assert g.post(f"/api/exams/{id}/withdraw").status_code == 403 and g.post(f"/api/exams/{id}/send-back", json=dict(note="x")).status_code == 403
        r = c.post(f"/api/exams/{id}/approve"); assert r.status_code == 200, r.data
        assert SC.load(id)["approved"]["made"]["duties"] == SC.load(id)["made"]["duties"]
        with _today(date(2026, 10, 1)):
            row = next(x for x in c.get("/api/exams").get_json()["schedules"] if x["id"] == id)
            assert row["label"] == "Approved · on the main site" and row["on_site"] == ["2026-10-05", "2026-10-06"] and row["retimed"] is False, row
            assert row["approved_at"] and row["sent_by"] == "Ms Grace Yeo"
        with _today(date(2026, 10, 7)):
            assert next(x for x in c.get("/api/exams").get_json()["schedules"] if x["id"] == id)["label"] == "Ended"
        pub2 = dict(_PUB, meta=dict(_PUB.get("meta") or {}, published_at="2026-10-09T10:00:00"))
    with published(pub2), _today(date(2026, 10, 1)):
        assert next(x for x in committee().get("/api/exams").get_json()["schedules"] if x["id"] == id)["retimed"] is True

@t
def send_refused_until_made_and_fresh():
    _setup()
    with published(_PUB):
        c = committee()
        s = _exam(c); id = s["id"]
        r = c.post(f"/api/exams/{id}/send"); assert r.status_code == 400 and r.get_json() == {"error": "Press Make first."}, r.data
        assert c.get(f"/api/exams/{id}/review").status_code == 409
        s = _made_exam(c); id = s["id"]
        s = SC.load(id); s["papers"][0]["minutes"] = 55
        assert c.put("/api/exams/" + id, json=s).status_code == 200
        r = c.post(f"/api/exams/{id}/send"); assert r.status_code == 400 and r.get_json() == {"error": "The exam changed since Make: press Make again."}, r.data
        assert c.post("/api/exams/nope/send").status_code == 404

@t
def approve_refuses_a_schedule_changed_after_sending():
    _setup()
    with published(_PUB):
        c = committee()
        s = _made_exam(c); id = s["id"]
        assert c.post(f"/api/exams/{id}/send").status_code == 200
        s = SC.load(id); s["papers"][0]["minutes"] = 55
        assert c.put("/api/exams/" + id, json=s).status_code == 200
        assert c.post(f"/api/exams/{id}/make", json={}).status_code == 200
        r = c.post(f"/api/exams/{id}/approve")
        assert r.status_code == 400 and r.get_json() == {"error": "This schedule changed after it was sent. Ask the exams committee to send it again."}, r.data

@t
def changes_wait_for_approval():
    _setup()
    with published(_PUB):
        c = committee()
        s = _approved_exam(c); id = s["id"]
        s = SC.load(id)
        eng = next(p for p in s["papers"] if p["subject"] == "English"); eng["start"] = "08:00"
        assert c.put("/api/exams/" + id, json=s).status_code == 200
        assert c.post(f"/api/exams/{id}/make", json={}).status_code == 200
        r = c.get(f"/api/exams/{id}/review"); assert r.status_code == 200, r.data
        d = r.get_json()
        assert "Sec 3 English Paper 1: Mon 5 Oct 07:50–08:50 → Mon 5 Oct 08:00–09:00." in [u["text"] for u in d["unsent"]], d["unsent"]
        eng_on_site = next(p for p in SC.on_site()[0]["papers"] if p["subject"] == "English")
        assert eng_on_site["start"] == "07:50"
        r = c.post(f"/api/exams/{id}/send"); assert r.status_code == 200, r.data
        d = r.get_json(); assert d["status"] == "changes" and any("08:00" in x["text"] for x in d["review"]["changes"]), d
        r = c.post(f"/api/exams/{id}/send-back", json=dict(note="Not that day")); assert r.status_code == 200, r.data
        d = r.get_json(); assert d["status"] == "approved" and d["note"] == "Not that day"
        assert next(p for p in SC.on_site()[0]["papers"] if p["subject"] == "English")["start"] == "07:50"
        assert c.post(f"/api/exams/{id}/send-back", json=dict(note="x")).status_code == 400
        assert c.post(f"/api/exams/{id}/send").status_code == 200
        assert c.post(f"/api/exams/{id}/approve").status_code == 200
        assert next(p for p in SC.on_site()[0]["papers"] if p["subject"] == "English")["start"] == "08:00"

@t
def withdraw_and_delete():
    _setup()
    with published(_PUB):
        c = committee()
        s = _approved_exam(c); id = s["id"]
        r = c.delete("/api/exams/" + id); assert r.status_code == 409 and r.get_json() == {"error": A.ON_SITE}, r.data
        r = c.post(f"/api/exams/{id}/withdraw"); assert r.status_code == 200 and r.get_json()["label"] == "Withdrawn", r.data
        assert SC.on_site() == []
        assert c.delete("/api/exams/" + id).status_code == 200 and SC.load(id) is None

@t
def put_cannot_forge_an_approval():
    _setup()
    with published(_PUB):
        c = committee()
        s = _exam(c); id = s["id"]
        forged = dict(SC.load(id), status="approved", approved=dict(SC.load(id)), approved_by="Me", approved_at="x", sent_by="Me", sent_at="x", sent_fp="x", note="n", log=[dict(what="x")])
        assert c.put("/api/exams/" + id, json=forged).status_code == 200
        now = SC.load(id)
        assert now["status"] == "draft" and now["approved"] is None and now["approved_by"] is None and now["note"] == "" and now["log"] == [] and now.get("sent_by") is None, now
        assert SC.on_site() == []
        assert c.put("/api/exams/" + id, json=dict(SC.load(id))).status_code == 200 and c.post(f"/api/exams/{id}/send").status_code == 400

@t
def away_on_the_main_site():
    _setup()
    with published(_PUB):
        c = committee()
        s = _made_exam(c); id = s["id"]
        body = dict(key=KEY1, room="3-01", away="Ms Chloe Tan", name="Mr Hafiz Rahman")
        r = c.post(f"/api/exams/{id}/away", json=body); assert r.status_code == 400 and r.get_json() == {"error": "This schedule is not on the main site."}, r.data
        assert c.post(f"/api/exams/{id}/send").status_code == 200 and c.post(f"/api/exams/{id}/approve").status_code == 200
        r = c.post(f"/api/exams/{id}/away", json=dict(body, name="Mr Daniel Koh"))
        assert r.status_code == 400 and r.get_json() == {"error": "Mr Daniel Koh is not free then."}, r.data
        assert c.post(f"/api/exams/{id}/away", json=dict(body, key=3)).status_code == 400
        r = c.post(f"/api/exams/{id}/away", json=body); assert r.status_code == 200, r.data
        d = next(x for x in SC.on_site()[0]["made"]["duties"] if x["key"] == KEY1 and x["room"] == "3-01")
        assert d["names"] == ["Ms Aisha Rahman", "Mr Hafiz Rahman"], d
        assert r.get_json()["review"]["done_without"][0]["detail"] == "Mon 5 Oct 07:35–09:00, 3-01: Ms Chloe Tan (away) → Mr Hafiz Rahman"
        who = c.get(f"/api/exams/{id}/who?key={KEY1}&room=3-01&copy=approved"); assert who.status_code == 200
        assert "Mr Hafiz Rahman" not in [x["name"] for g in ("freed", "free", "backups") for x in who.get_json()[g]]

@t
def a_draft_with_a_null_log_still_sends():
    _setup()
    with published(_PUB):
        c = committee()
        s = _made_exam(c); id = s["id"]
        raw = SC.load(id); raw["log"] = None
        store.write_json(os.path.join(SC.DIR, id + ".json"), raw)
        assert c.put("/api/exams/" + id, json=SC.load(id)).status_code == 200
        assert SC.load(id)["log"] == []
        assert c.post(f"/api/exams/{id}/send").status_code == 200


import json  # noqa: E402
A1 = AP.as_schedule(_approved())
D5 = "2026-10-05"

@t
def merged_view_matches_day_view():
    s = _made_sched()
    d = date(2026, 10, 5).isoformat()
    assert D.merged_view(_PUB, F.CAL, [s], d)["lessons"] == D.day_view(_PUB, F.CAL, s, d)["lessons"]
    m = D.merged_view(_PUB, F.CAL, [s], d)
    assert m["date"] == d and m["day"] == "Odd Mon"

@t
def day_layer_from_the_approved_copy():
    e = PB.day(_PUB, F.CAL, [A1], D5, True)
    assert e["day"] == "Odd Mon"
    e = e["exams"]
    assert e["stopped"] == [0, 1, 3, 4] and e["shortened"] == [], e
    a = e["classes"]["3A"]
    assert [(x["start"], x["end"], x["label"], x["room"], x["seat_note"]) for x in a] == [
        ("07:50", "08:50", "Sec 3 English Paper 1", "3-01", ""), ("10:00", "11:00", "Sec 3 Pure Chemistry Paper 1", "3-01", "")], a
    assert a[0]["p"] == 0.5 and a[0]["n"] == 3.0 and a[0]["exam"] == "Sec 3 End-of-Year Exam", a[0]
    assert len(e["classes"]["3B"]) == 1 and e["classes"]["3B"][0]["room"] == "3-02" and "4A" not in e["classes"]
    assert e["teachers"]["Ms Aisha Rahman"] == [dict(start="07:35", end="09:00", label="Sec 3 English Paper 1", room="3-01",
                                                      role="Invigilate", exam="Sec 3 End-of-Year Exam", p=0.0, n=4.0)], e["teachers"]["Ms Aisha Rahman"]
    assert set(e["rooms"]) == {"3-01", "3-02"} and e["banner"] == "Sec 3 End-of-Year Exam"
    assert e["rooms"]["3-02"][0]["exam"] == "Sec 3 End-of-Year Exam" and "room" not in e["rooms"]["3-02"][0]

@t
def student_code_sees_no_names_or_duty_rooms():
    acc = [dict(student="3A-05", extra=25, own_room=True, reader=False, scribe=False, note="")]
    s = AP.as_schedule(_approved(access=acc, rooms=("3-01", "3-02", "4-01", "Hall", "3-11")))
    full = PB.day(_PUB, F.CAL, [s], D5, True)["exams"]
    assert "3-11" in json.dumps(full["rooms"]), "the access room is a duty room for staff"
    out = PB.day(_PUB, F.CAL, [s], D5, False)
    e = out["exams"]
    assert e["teachers"] == {} and e["rooms"] == {}, e
    a = e["classes"]["3A"][0]
    assert a["room"] == "3-01" and a["seat_note"] == "", a
    text = json.dumps(out)
    assert "3-11" not in text and "Aisha" not in text and "Chloe" not in text, text
    lst = PB.listing(_PUB, [s], date(2026, 10, 1), False)
    assert "roster" not in lst["schedules"][0] and "prints" not in lst["schedules"][0] and "3-11" not in json.dumps(lst)

@t
def not_a_school_day_is_empty():
    for d in ("2026-10-12", "2026-12-01"):
        out = PB.day(_PUB, F.CAL, [A1], d, True)
        assert out["day"] is None and out["exams"] == dict(classes={}, stopped=[], shortened=[], teachers={}, rooms={}, banner=""), out

@t
def two_approved_schedules_on_one_date():
    b = SC.new("exam", "Sec 4 Exam", ["Sec 4"], D5, D5, "Ms Grace Yeo", pub=_PUB)
    b.update(papers=[_paper(level="Sec 4", subject="English", date=D5, start="07:50", who="level")], days={D5: dict(levels=["Sec 4"], whole=True)},
             access=[])
    b = MK.make(_PUB, F.CAL, b, _xset(("3-01", "3-02", "4-01", "Hall")), elsewhere=[])
    AP.send(b, _M, "Ms Grace Yeo", NOW, False, [])
    AP.approve(b, "Timetable committee", NOW)
    e = PB.day(_PUB, F.CAL, [A1, AP.as_schedule(b)], D5, True)["exams"]
    assert e["stopped"] == [0, 1, 2, 3, 4, 5, 6, 7, 8], e["stopped"]
    assert set(e["classes"]) == {"3A", "3B", "4A"} and e["banner"] == "Sec 3 End-of-Year Exam · Sec 4 Exam", e["banner"]
    e = PB.day(_PUB, F.CAL, [A1], D5, True)["exams"]
    assert 8 not in e["stopped"]

@t
def unsent_changes_stay_off_the_main_site():
    s = _approved()
    for p in s["papers"]:
        if p["subject"] == "English": p["start"] = "08:00"
    s = _mk(s)
    site = [AP.as_schedule(s)]
    assert s["papers"][0]["start"] == "08:00" and site[0]["papers"][0]["start"] == "07:50"
    e = PB.day(_PUB, F.CAL, site, D5, True)["exams"]
    assert e["classes"]["3A"][0]["start"] == "07:50"
    lst = PB.listing(_PUB, site, date(2026, 10, 1), True)
    assert lst["schedules"][0]["levels"]["Sec 3"][0]["start"] == "07:50"
    assert PB.my_exams(_PUB, F.CAL, site, "3A-07", date(2026, 10, 1))["schedules"][0]["papers"][0]["start"] == "07:50"

@t
def published_listing_and_banner():
    out = PB.listing(_PUB, [A1], date(2026, 10, 1), True)
    sc = out["schedules"][0]
    assert sc["levels"]["Sec 3"] == [dict(date=D5, start="07:50", end="08:50", label="Sec 3 English Paper 1"),
                                     dict(date=D5, start="10:00", end="11:00", label="Sec 3 Pure Chemistry Paper 1")], sc["levels"]
    assert sc["roster"][0] == dict(date=D5, start="07:35", end="09:00", room="3-01", label="Sec 3 English Paper 1",
                                   names=["Ms Aisha Rahman", "Ms Chloe Tan"], chief=None), sc["roster"][0]
    assert len(sc["roster"]) == 3
    assert sc["prints"][0] == ["Seating plan", f"/api/published/exams/{A1['id']}/print/seating.pdf"]
    assert [x[1].split("/")[-1][:-4] for x in sc["prints"]] == list(PB.PRINTS)
    assert out["banner"] == "Sec 3 End-of-Year Exam: Mon 5 Oct\u2013Tue 6 Oct.", out["banner"]
    r = PB.listing(_PUB, [A1], date(2026, 10, 1), False)["schedules"][0]
    assert "roster" not in r and "prints" not in r
    assert PB.listing(_PUB, [A1], date(2026, 9, 27), True)["banner"] is None
    assert PB.listing(_PUB, [A1], date(2026, 10, 7), True)["schedules"] == []

@t
def a_teachers_duties():
    out = PB.my_duties(_PUB, F.CAL, [A1], "Ms Aisha Rahman", date(2026, 10, 1))
    assert len(out["schedules"]) == 1 and out["schedules"][0]["minutes"] == 85, out["schedules"]
    assert out["schedules"][0]["duties"] == [dict(date=D5, start="07:35", end="09:00", room="3-01", label="Sec 3 English Paper 1",
                                                  students=30, others=["Ms Chloe Tan"], chief=None, role="Invigilate")], out["schedules"][0]["duties"]
    assert out["lessons"] == [dict(date=D5, start="07:40", end="08:20", classes=["3A"], subject="English")], out["lessons"]
    iv = PB.my_duties(_PUB, F.CAL, [A1], "Mr Ivan Lee", date(2026, 10, 1))
    assert iv["lessons"] == [dict(date="2026-10-06", start="07:40", end="08:20", classes=["3A"], subject="English")], iv
    assert PB.my_duties(_PUB, F.CAL, [A1], "Mr Nobody", date(2026, 10, 1)) == dict(schedules=[], lessons=[])

@t
def a_students_papers():
    out = PB.my_exams(_PUB, F.CAL, [A1], "3A-07", date(2026, 10, 1))
    assert out["schedules"][0]["papers"] == [
        dict(date=D5, report="07:30", start="07:50", end="08:50", label="Sec 3 English Paper 1", room="3-01", seat="B1", note=""),
        dict(date=D5, report=None, start="10:00", end="11:00", label="Sec 3 Pure Chemistry Paper 1", room="3-01", seat="B1", note="")], out
    assert PB.my_exams(_PUB, F.CAL, [A1], "3B-15", date(2026, 10, 1))["schedules"] == []
    acc = [dict(student="3A-05", extra=25, own_room=True, reader=False, scribe=False, note="")]
    s = AP.as_schedule(_approved(access=acc, rooms=("3-01", "3-02", "4-01", "Hall", "3-11")))
    p = PB.my_exams(_PUB, F.CAL, [s], "3A-05", date(2026, 10, 1))["schedules"][0]["papers"][0]
    assert (p["room"], p["seat"], p["end"]) == ("3-11", "A1", "09:05"), p
    q = _made_sched()
    q["papers"] = [q["papers"][0]]
    q["days"] = {D5: dict(levels=["Sec 3"], whole=False, **{"from": "07:40", "to": "09:00"})}
    q = _mk(q)
    AP.send(q, _M, "x", NOW, False, [])
    AP.approve(q, "x", NOW)
    p = PB.my_exams(_PUB, F.CAL, [AP.as_schedule(q)], "3A-07", date(2026, 10, 1))["schedules"][0]["papers"][0]
    assert p["report"] == "07:30" and p["note"] == "then lessons from 09:00", p


# ---- the main site's routes
def as_role(role, **sess):
    c = A.app.test_client()
    with c.session_transaction() as s:
        s["role"] = role
        s.update(sess)
    return c

def _site_setup():
    _setup()
    c = committee()
    s = _approved_exam(c)
    return c, s

@t
def day_for_staff_and_for_the_student_code():
    with published(_PUB):
        c, s = _site_setup()
        with _today(date(2026, 10, 1)):
            d = c.get("/api/day?date=2026-10-05").get_json()
            assert d["day"] == "Odd Mon" and d["exams"]["stopped"] == [0, 1, 3, 4], d["exams"]["stopped"]
            assert "Ms Aisha Rahman" in d["exams"]["teachers"], list(d["exams"]["teachers"])
            r = as_role("student").get("/api/day?date=2026-10-05"); assert r.status_code == 200
            st = r.get_json()
            assert st["exams"]["classes"] == d["exams"]["classes"] and st["exams"]["stopped"] == d["exams"]["stopped"]
            assert st["exams"]["teachers"] == {} and st["exams"]["rooms"] == {}
            assert as_role("personal", sid="3A-07").get("/api/day?date=2026-10-05").status_code == 401
            assert as_role("teacher").get("/api/day?date=2026-10-05").get_json()["exams"]["teachers"]

@t
def day_refuses_bad_dates():
    with published(_PUB):
        c, s = _site_setup()
        with _today(date(2026, 10, 1)):
            r = c.get("/api/day?date=2026-10-12"); assert r.status_code == 200
            d = r.get_json(); assert d["day"] is None and d["exams"]["classes"] == {} and d["exams"]["teachers"] == {}, d
            for q in ("?date=05-10-2026", "", "?date=2026-13-45", "?date=%20", "?date=20261005"):
                r = c.get("/api/day" + q); assert r.status_code == 400 and r.get_json() == {"error": A.BAD_DATE}, (q, r.status_code, r.data)
        _cal(False)
        r = c.get("/api/day?date=2026-10-05"); assert r.status_code == 409 and r.get_json() == {"error": A.NO_DAY_CAL}, r.data
    r = committee().get("/api/day?date=2026-10-05"); assert r.status_code in (409, 200)

@t
def published_exams_and_prints():
    with published(_PUB):
        c, s = _site_setup(); id = s["id"]
        with _today(date(2026, 10, 1)):
            t_ = as_role("teacher"); st = as_role("student")
            d = t_.get("/api/published/exams").get_json()
            assert d["banner"] == "Sec 3 Exam: Mon 5 Oct\u2013Tue 6 Oct." and d["schedules"][0]["roster"] and d["schedules"][0]["prints"], d
            d2 = st.get("/api/published/exams").get_json()
            assert "roster" not in d2["schedules"][0] and "prints" not in d2["schedules"][0]
            assert as_role("personal", sid="3A-07").get("/api/published/exams").status_code == 401
            r = t_.get(f"/api/published/exams/{id}/print/seating.pdf"); assert r.status_code == 200 and r.data[:4] == b"%PDF", r.status_code
            assert "inline" in r.headers["Content-Disposition"]
            r = st.get(f"/api/published/exams/{id}/print/seating.pdf"); assert r.status_code == 403 and r.get_json() == {"error": A.ONLY_STAFF_PRINTS}, r.data
            assert st.get(f"/api/published/exams/{id}/print/doors.pdf").status_code == 403
            assert t_.get(f"/api/published/exams/{id}/print/doors.pdf").status_code == 404
            assert t_.get("/api/published/exams/nope/print/seating.pdf").status_code == 404
            before = t_.get("/api/published/exams").get_json()["schedules"][0]["roster"]
            w = SC.load(id)
            eng = next(p for p in w["papers"] if p["subject"] == "English"); eng["start"] = "08:00"
            assert c.put("/api/exams/" + id, json=w).status_code == 200
            assert c.post(f"/api/exams/{id}/make", json={}).status_code == 200
            assert t_.get("/api/published/exams").get_json()["schedules"][0]["roster"] == before
            assert t_.get("/api/day?date=2026-10-05").get_json()["exams"]["classes"]["3A"][0]["start"] == "07:50"

@t
def my_duties_and_my_exams():
    with published(_PUB):
        c, s = _site_setup()
        with _today(date(2026, 10, 1)):
            r = as_role("staff", who="Ms Aisha Rahman").get("/api/exams/my-duties"); assert r.status_code == 200, r.data
            assert any(d["room"] == "3-01" for x in r.get_json()["schedules"] for d in x["duties"]), r.get_json()
            assert c.get("/api/exams/my-duties").get_json()["schedules"] == []
            assert as_role("teacher").get("/api/exams/my-duties").status_code == 401
            r = as_role("personal", sid="3A-07").get("/api/me/exams"); assert r.status_code == 200
            assert r.get_json()["schedules"][0]["papers"][0]["seat"] == "B1", r.get_json()
            assert as_role("personal", sid="nobody").get("/api/me/exams").status_code == 401
            assert as_role("student").get("/api/me/exams").status_code == 401
            r = as_role("personal", sid="3A-07").get("/api/me/exams?sid=3B-15"); assert r.get_json()["schedules"][0]["papers"]

@t
def timetable_and_me_ask_for_exams():
    from ttgen import export as E
    seen = []
    def fake_render(model, view, app=None, student_id=None): seen.append(app); return "page"
    old, E.render_html = E.render_html, fake_render
    pub = copy.deepcopy(_PUB); pub["views"] = {}
    try:
        with published(pub):
            tc, _ = signed_in("teacher", os.environ["TEACHER_CODE"])
            assert tc.get("/timetable").status_code == 200
            assert seen[0]["dates"] is True and seen[0]["exams"] is True and "exams" in seen[0]["tabs"], seen[0]
            sc, _ = signed_in("student", os.environ["STUDENT_CODE"])
            assert sc.get("/timetable").status_code == 200 and "exams" in seen[1]["tabs"] and seen[1]["exams"] is True
            r = as_role("personal", sid="3A-07").get("/me"); assert r.status_code == 200
            assert seen[2]["exams"] is True and seen[2]["mode"] == "personal", seen[2]
    finally: E.render_html = old

@t
def the_published_page_has_the_date_choice():
    src = open(os.path.join(ROOT, "ttgen", "timetable_page.html"), encoding="utf-8").read()
    for words in ("Usual timetable", 'id="onDate"', 'aria-label="Show the timetable on a date"', "Not a school day.",
                  " is outside the terms or a holiday in the school calendar.", "Lessons that don't happen are crossed out.",
                  ": no exams, tests or events. This is the usual ", "See Exams and events", "No exams, tests or events on the main site now.",
                  "My exam timetable", "Roster by day", " (chief)", "/api/day?date=", "/api/published/exams", "/api/me/exams", ".cell.x", ".cell.exam",
                  ".datepick", "runs ", "Duties, events and the rooms they take count as busy; lessons that don't happen do not.", "Exams and events",
                  "Teacher in charge: ", "Going: "):
        assert words in src, words
    for old in ("no exams or tests", "No exams or tests on the main site now.", "See Exams</a>", "Duties and exam rooms count as busy"):
        assert old not in src, old
    skill = open(os.path.join(ROOT, "skill", "school-timetable-generator", "scripts", "ttgen", "timetable_page.html"), encoding="utf-8").read()
    assert src == skill, "the skill's copy of the page is the same"


@t
def the_exams_pages_carry_the_approval_words():
    js = _page("exams.js")
    for words in ("Approval", "Send to the timetable committee", "Send again", "Send the changes", "Approve: show on the main site",
                  "Approve the changes", "Send back with a note", "Withdraw from the main site", "Done without approval", "Someone is away",
                  "Replace now", "My exam duties", "You have no exam duties on the main site.", "Scripts go to",
                  "On the main site. Changes you make here wait for the timetable committee: send them from the Approval tab.",
                  "Changes not sent yet", "Nothing on the main site has changed since it was approved.", "What changes on the main site",
                  "Lessons that won't happen: ", "Rain rooms used anyway: ", "Take ${S.sched.name} off the main site now?", "/api/exams/my-duties",
                  "&copy=approved", "Lessons that don't happen: "):
        assert words in js, words
    assert "g.includes(` is on ${m[1]} then (`)" not in js and "f.includes(` is on ${m[1]} then (`)" in js, "a takes line goes only when a free line names that schedule"
    assert "S.abMsg" in js, "a refusal shows beside the Approval buttons"
    assert "Exams · " in _page("app.js"), "the committee page counts the schedules waiting"


# ---- the final review's fix wave
@t
def an_approve_during_a_make_is_kept():
    import threading, time
    _setup()
    with published(_PUB):
        c, c2 = committee(), committee()
        s = _made_exam(c); id = s["id"]
        assert c.post(f"/api/exams/{id}/send").status_code == 200
        started, real, got = threading.Event(), A.exams_make.make, {}
        def slow(*a, **k):
            started.set(); time.sleep(0.4)
            return real(*a, **k)
        A.exams_make.make = slow
        try:
            th = threading.Thread(target=lambda: got.setdefault("make", c.post(f"/api/exams/{id}/make", json={}).status_code))
            th.start(); assert started.wait(5)
            got["approve"] = c2.post(f"/api/exams/{id}/approve").status_code
            th.join(10)
        finally: A.exams_make.make = real
        assert got == dict(make=200, approve=200), got
        now = SC.load(id)
        assert now["status"] == "approved" and now["approved"] and now["log"][-1]["what"] == "approved", (now["status"], now["log"])

def _without(sid, at="2026-10-02T09:30:00"):
    """the timetable published again without one student"""
    pub = copy.deepcopy(_PUB); pub["meta"]["published_at"] = at
    pub["model"]["students"] = [x for x in pub["model"]["students"] if x["id"] != sid]
    return pub

@t
def approval_actions_work_after_a_publish_drops_a_student():
    _setup()
    acc = [dict(student="3A-05", extra=25, own_room=False, reader=False, scribe=False, note="")]
    with published(_PUB):
        c = committee()
        s = _exam(c); id = s["id"]
        times = {"English": "07:50", "Pure Chemistry": "10:00"}
        s["papers"] = [dict(p, date="2026-10-05", start=times[p["subject"]]) for p in s["papers"] if p["subject"] in times]
        s["access"] = acc
        assert c.put("/api/exams/" + id, json=s).status_code == 200
        assert c.post(f"/api/exams/{id}/make", json={}).status_code == 200
        assert c.post(f"/api/exams/{id}/send").status_code == 200 and c.post(f"/api/exams/{id}/approve").status_code == 200
    with published(_without("3A-05")):
        body = dict(key=KEY1, room="3-01", away="Ms Chloe Tan", name="Mr Ben Ong")
        r = c.post(f"/api/exams/{id}/away", json=body); assert r.status_code == 200, r.data
        assert c.get(f"/api/exams/{id}/review").status_code == 200
        r = c.put("/api/exams/" + id, json=SC.load(id))
        assert r.status_code == 400 and r.get_json()["error"] == "3A-05 is not on the published timetable.", r.data
        r = c.post(f"/api/exams/{id}/withdraw"); assert r.status_code == 200, r.data
        assert SC.on_site() == [] and SC.load(id)["status"] == "withdrawn"

def _ap_duty(s, key, room):
    return next(x for x in s["approved"]["made"]["duties"] if x["key"] == key and x["room"] == room)

@t
def someone_away_keeps_the_working_copys_own_change():
    _reset()   # the picks count the minutes of the schedules saved by earlier tests
    s = _approved()
    MK.set_invigilators(s, KEY1, "3-01", ["Ms Aisha Rahman", "Mr Hafiz Rahman"]); _mk(s, only=KEY1)   # waiting: Chloe -> Hafiz
    pk = KEY1 + "|3-01"
    AP.replace(s, KEY1, "3-01", "Ms Aisha Rahman", "Mr Ivan Lee", "Ms Grace Yeo", NOW)
    assert _ap_duty(s, KEY1, "3-01")["names"] == ["Mr Ivan Lee", "Ms Chloe Tan"] == s["approved"]["pins"]["duties"][pk]
    assert _duty(s, KEY1, "3-01")["names"] == ["Mr Ivan Lee", "Mr Hafiz Rahman"] == s["pins"]["duties"][pk], s["pins"]
    _mk(s)
    assert _duty(s, KEY1, "3-01")["names"] == ["Mr Ivan Lee", "Mr Hafiz Rahman"], _duty(s, KEY1, "3-01")
    assert "Mon 5 Oct 07:50, 3-01: Ms Chloe Tan → Mr Hafiz Rahman (invigilator)." in [c["text"] for c in AP.changes(s, _M)], AP.changes(s, _M)

@t
def someone_away_already_on_the_working_duty_is_not_named_twice():
    _reset()   # the picks count the minutes of the schedules saved by earlier tests
    s = _approved()
    MK.set_invigilators(s, KEY1, "3-01", ["Ms Aisha Rahman", "Mr Hafiz Rahman"]); _mk(s, only=KEY1)
    AP.replace(s, KEY1, "3-01", "Ms Aisha Rahman", "Mr Hafiz Rahman", "Ms Grace Yeo", NOW)
    assert _ap_duty(s, KEY1, "3-01")["names"] == ["Mr Hafiz Rahman", "Ms Chloe Tan"]
    d = _duty(s, KEY1, "3-01")
    assert d["names"] == ["Mr Hafiz Rahman"] == s["pins"]["duties"][KEY1 + "|3-01"] and d["short"] == 1 and "Ms Aisha Rahman" not in d["reasons"], d
    other = _approved()   # a working duty without the person away is left as it is, pin and all
    MK.set_invigilators(other, KEY1, "3-01", ["Mr Ben Ong", "Mr Hafiz Rahman"]); _mk(other, only=KEY1)
    AP.replace(other, KEY1, "3-01", "Ms Aisha Rahman", "Mr Ivan Lee", "Ms Grace Yeo", NOW)
    assert _duty(other, KEY1, "3-01")["names"] == ["Mr Ben Ong", "Mr Hafiz Rahman"] == other["pins"]["duties"][KEY1 + "|3-01"]

def _joined(sid="3A-31", at="2026-10-02T09:30:00"):
    """the timetable published again with one more student in 3A, in the Pure Chemistry group"""
    pub = copy.deepcopy(_PUB); pub["meta"]["published_at"] = at
    pub["model"]["students"].append(dict(id=sid, name="Student " + sid, cls="3A", level="Sec 3", groups=["3PC1"]))
    return pub

def _placed(made, key):
    return {sid for rows in (made.get("seats") or {}).get(key, {}).values() for sid, _ in rows} | set((made.get("unseated") or {}).get(key) or [])

@t
def a_student_who_joins_after_approval_makes_it_stale_and_is_flagged():
    _reset()
    s, x = _approved(), _xset(_X4)
    pub2 = _joined()
    assert MK.stale(s, x, _M) is False and MK.stale(s, x, pub2["model"]) is True, "who sits each paper is part of what Make used"
    c = RV.review(pub2, F.CAL, s, x, [])["checks"][1]
    assert c["ok"] is False and c["lines"] == ["1 student has no seat."], c
    assert RV.review(_PUB, F.CAL, s, x, [])["checks"][1]["ok"] is True

@t
def make_again_seats_a_student_who_joins_after_approval():
    _reset()
    s, x = _approved(), _xset(_X4)
    pub2 = _joined()
    MK.make(pub2, F.CAL, s, x, elsewhere=[])
    m2 = pub2["model"]
    for sit in SE.sittings(s):
        assert set(SE.sitting_students(sit, s, m2)) == _placed(s["made"], sit["key"]), sit["key"]
    assert "3A-31" in _placed(s["made"], KEY1) and "3A-31" in _placed(s["made"], "2026-10-05 10:00")
    assert MK.stale(s, x, m2) is False and RV._seats_check(s, m2)["ok"] is True
    texts = [c["text"] for c in AP.changes(s, m2)]
    assert "Mon 5 Oct 07:50, 3A: 3-01 (30) → 3-01 (31)." in texts, texts
    assert "3A-31" not in _placed(s["approved"]["made"], KEY1), "the main site waits for the change to be approved"

# ---- the fix wave's minor items
@t
def day_refuses_any_date_not_written_as_yyyy_mm_dd():
    with published(_PUB):
        c, s = _site_setup()
        for q in ("2026-W41-1", "2026W411", "20261005", "2026-10-5", " 2026-10-05"):
            r = c.get("/api/day?date=" + q); assert r.status_code == 400 and r.get_json() == {"error": A.BAD_DATE}, (q, r.status_code, r.data)
        assert c.get("/api/day?date=2026-10-05").status_code == 200

@t
def changes_waiting_hold_both_copies_for_other_schedules():
    _reset()
    s = _sit([_paper(date="2026-10-05", start="07:50")], days=dict(SEC3))
    s.update(id="ffff", name="Exam ffff", status="changes")
    duty = lambda room, names, start=455: dict(key="2026-10-05 07:50", room=room, date="2026-10-05", start=start, end=540, names=names)
    s["made"] = dict(duties=[duty("Hall", ["Ms Grace Yeo"]), duty("3-01", ["Mr Ben Ong"])], seats={}, unseated={})
    s["approved"] = dict(name="Exam ffff", made=dict(duties=[duty("Hall", ["Ms Grace Yeo"]), duty("3-02", ["Mr Ivan Lee"])], seats={}, unseated={}))
    SC.save(s, _PUB, F.CAL, "t")
    got = sorted((b["room"], b["status"], tuple(b["names"])) for b in SC.elsewhere("zzzz"))
    assert got == [("3-01", "waiting", ("Mr Ben Ong",)), ("3-02", "approved", ("Mr Ivan Lee",)), ("Hall", "approved", ("Ms Grace Yeo",))], got
    _reset()

@t
def rights_reads_go_through_named_helpers():
    import re
    src = open(os.path.join(ROOT, "app.py"), encoding="utf-8").read()
    part = src.split("# ------------------------------------------------------------------------------------------------ staff: exams and events")[1]
    helpers = ("_exams_rights", "_exams_can_approve", "_exams_can_keep_list", "_published_reader", "_exams_student", "_event_rights")
    for name, body in re.findall(r"\ndef (\w+)\(.*?\):(.*?)(?=\n(?:def |@app|# -{20}))", part, re.S):
        if name not in helpers:
            assert "role()" not in body and 'session.get("sid")' not in body and "session[" not in body, name
    with published(_PUB):
        _setup()
        c, g = committee(), staff("Ms Grace Yeo")
        assert c.get("/api/exams/settings").get_json()["committee_ok"] is True and g.get("/api/exams/settings").get_json()["committee_ok"] is False

@t
def the_away_panel_lists_every_duty_of_the_approved_copy():
    js = _page("exams.js")
    for words in ('data-aw="duty"', "Duty on the main site", "Choose the duty on the main site that someone cannot do.", "S.aw.duty || S.duty"):
        assert words in js, words

@t
def my_exam_duties_lists_lessons_that_stop_with_no_duties():
    assert not any("Ms Grace Yeo" in d["names"] for d in A1["made"]["duties"]), "Ms Grace Yeo has no duty"
    out = PB.my_duties(_PUB, F.CAL, [A1], "Ms Grace Yeo", date(2026, 10, 1))
    assert out == dict(schedules=[], lessons=[dict(date=D5, start="09:40", end="10:40", classes=["3A", "3B"], subject="Combined Science")]), out
    assert PB.my_duties(_PUB, F.CAL, [A1], "Mr Daniel Koh", date(2026, 10, 1))["lessons"] == [], "his Sec 4 lesson runs"
    assert "!(D.lessons || []).length && !alone" in _page("exams.js")

@t
def the_timetable_check_reads_well_without_a_date():
    s = MK.make(dict(_PUB, meta=dict(published_at="2026-10-01T08:00:00")), F.CAL, _made_sched(), _xset(_X4), elsewhere=[])
    c = RV.review(dict(_PUB, meta={}), F.CAL, s, _xset(_X4), [])["checks"][4]
    assert c["lines"] == ["The timetable changed since this was made: a new timetable was published. Ask the exams committee to make it again."], c

@t
def the_schedule_list_needs_today():
    import inspect, glob
    assert inspect.signature(SC.listing).parameters["today"].default is inspect.Parameter.empty
    for f in glob.glob(os.path.join(ROOT, "exams", "*.py")):
        assert "date.today()" not in open(f, encoding="utf-8").read(), f
    _reset()
    _stored("gggg", "approved", ["Ms Grace Yeo"], approved=["Ms Grace Yeo"])
    assert IV._other_minutes(dict(id="zzzz"), "2026") == {"Ms Grace Yeo": 85} and IV._other_minutes(dict(id="gggg"), "2026") == {}
    _reset()

@t
def who_on_the_main_site_names_a_missing_duty():
    with published(_PUB):
        c, s = _site_setup()
        r = c.get(f"/api/exams/{s['id']}/who?key=2026-10-05 07:50&room=Hall&copy=approved")
        assert r.status_code == 404 and r.get_json() == {"error": "That duty is not on the main site."}, r.data

@t
def the_readme_says_what_send_needs():
    txt = open(os.path.join(ROOT, "README.md"), encoding="utf-8").read()
    assert "every check is clear" not in txt and "once Make is done, nothing has changed since Make, and the paper times have no errors" in txt

@t
def a_page_from_an_older_publish_is_told_to_reload():
    from ttgen import export as E
    pub = copy.deepcopy(_PUB); pub["views"] = {}; pub["meta"]["published_at"] = "2026-10-01T08:00:00"
    seen = []
    old, E.render_html = E.render_html, lambda model, view, app=None, student_id=None: seen.append(app) or "page"
    try:
        with published(pub):
            c, s = _site_setup()
            tc, _ = signed_in("teacher", os.environ["TEACHER_CODE"])
            assert tc.get("/timetable").status_code == 200 and seen[-1]["published_at"] == "2026-10-01T08:00:00", seen
            r = tc.get("/api/day?date=2026-10-05&published_at=2026-10-01T08:00:00"); assert r.status_code == 200
            assert r.get_json()["published_at"] == "2026-10-01T08:00:00"
            r = tc.get("/api/day?date=2026-10-05&published_at=2026-09-01T08:00:00")
            assert r.status_code == 409 and r.get_json() == dict(error=A.REPUBLISHED, published_at="2026-10-01T08:00:00"), r.data
            assert A.REPUBLISHED == "The timetable was published again: reload the page."
            assert tc.get("/api/day?date=2026-10-05").status_code == 200, "no stamp sent: answered"
    finally: E.render_html = old

@t
def a_combined_venue_and_its_rooms_clash_in_the_review():
    s = _waiting()
    for d in s["made"]["duties"]:
        if d["key"] == KEY1: d["room"] = "LT1&2"
    other = [dict(id="b", name="Sec 4 Exam", status="approved", date="2026-10-05", start=500, end=560, room="LT1", names=[])]
    c = RV.review(_PUB, F.CAL, s, _xset(_X4), other)["checks"][3]
    assert c["lines"] == ["Sec 4 Exam (approved) uses LT1 on Mon 5 Oct too."], c


# ---- tests the final review recommended
@t
def reader_and_scribe_students_are_left_out_of_the_class_room_line():
    _reset()
    for kind in ("reader", "scribe"):
        acc = [dict(student="3A-05", extra=0, own_room=False, reader=kind == "reader", scribe=kind == "scribe", note="")]
        s = AP.as_schedule(_approved(access=acc, rooms=("3-01", "3-02", "4-01", "Hall", "3-11")))
        assert "3A-05" in [x for x, _ in s["made"]["seats"][KEY1]["3-11"]], kind
        out = PB.day(_PUB, F.CAL, [s], D5, False)
        a = out["exams"]["classes"]["3A"][0]
        assert (a["room"], a["seat_note"]) == ("3-01", "") and "3-11" not in json.dumps(out), (kind, a)
    _reset()

@t
def make_treats_a_stored_neighbours_rooms_and_invigilators_as_taken():
    _reset()
    nb = _sit([_paper(level="Sec 4", subject="English", date=D5, start="07:50", who="level")], levels=["Sec 4"], days={D5: dict(levels=["Sec 4"], whole=True)})
    nb.update(id="nbnb", name="Sec 4 Exam")
    nb["pins"]["duties"][KEY1 + "|Hall"] = ["Ms Aisha Rahman", "Ms Chloe Tan"]   # the two the Sec 3 sitting would pick first
    nb = MK.make(_PUB, F.CAL, nb, _xset(("Hall",)), elsewhere=[])
    AP.send(nb, _M, "Ms Grace Yeo", NOW, False, []); AP.approve(nb, "Timetable committee", NOW)
    SC.save(nb, _PUB, F.CAL, "Timetable committee", check=False)
    hall = next(d for d in nb["approved"]["made"]["duties"] if d["room"] == "Hall")
    def made(rooms, elsewhere):
        s = _made_sched()
        MK.make(_PUB, F.CAL, s, _xset(rooms), **({} if elsewhere is None else dict(elsewhere=elsewhere)))
        return s["made"]
    over = lambda m: {n for d in m["duties"] if d["date"] == D5 and d["start"] < hall["end"] and d["end"] > hall["start"] for n in d["names"]}
    assert made(("Hall",), [])["seats"][KEY1].get("Hall"), "with nothing else saved, the Hall is free"
    assert set(hall["names"]) & over(made(("3-01", "3-02"), [])), "and the neighbour's invigilators would be picked"
    m = made(("Hall",), None)   # elsewhere read from the saved schedules
    assert not m["seats"][KEY1].get("Hall") and len(m["unseated"][KEY1]) == 30, m["seats"][KEY1]
    m = made(("3-01", "3-02"), None)
    assert not set(hall["names"]) & over(m) and all(d["short"] == 0 for d in m["duties"]), (hall["names"], over(m))
    _reset()

@t
def changes_list_the_other_kinds():
    s = _approved()
    s.update(levels=[], classes=["3A"], end="2026-10-07", scripts="the general office")
    s["access"] = [dict(student="3A-05", extra=25, own_room=False, reader=False, scribe=False, note="")]
    s["days"]["2026-10-06"] = dict(levels=["Sec 3"], whole=False, **{"from": "07:40", "to": "09:00"})
    s["papers"] = [p for p in s["papers"] if p["subject"] != "Pure Chemistry"] + [
        _paper(subject="Mathematics", date="2026-10-06", start="08:00"), _paper(subject="Art")]
    s["made"]["published_at"] = "2026-10-02T09:30:00"
    assert [c["kind"] for c in AP.changes(s, _M)] == ["dates", "levels", "day", "scripts", "access", "paper", "paper", "paper", "timetable"], AP.changes(s, _M)
    assert [c["text"] for c in AP.changes(s, _M)] == [
        "Dates: Mon 5 Oct–Tue 6 Oct → Mon 5 Oct–Wed 7 Oct.", "Levels and classes: Sec 3 → 3A.",
        "Tue 6 Oct: as the exam → part of the day 07:40–09:00 (Sec 3).", "Scripts go to: not set → the general office.",
        "Access arrangements changed for 1 student.", "Added Sec 3 Mathematics Paper 1: Tue 6 Oct 08:00–09:00.", "Added Sec 3 Art Paper 1 with no time.",
        "Removed Sec 3 Pure Chemistry Paper 1.", "Made again for the timetable published on Fri 2 Oct."], [c["text"] for c in AP.changes(s, _M)]


import exams.events as EV  # noqa: E402

def _ev(**kw):
    e = SC.new_event("Sec 3 Learning Journey", ["Sec 3"], [], "2026-10-05", "2026-10-05", "Ms Aisha Rahman", "Ms Aisha Rahman")
    e["days"] = {"2026-10-05": dict(levels=["Sec 3"], whole=False, **{"from": "07:40", "to": "10:40"})}
    e["where"] = "Off site (museum)"
    e["going"] = ["Ms Aisha Rahman", "Ms Grace Yeo", "Mr Hafiz Rahman"]
    e["duties"] = [dict(duty="Bus marshal", who="Mr Hafiz Rahman", time="07:45")]
    e.update(kw)
    return e

def _ev_bad(sentence, **kw):
    try: SC._check(_ev(**kw), _PUB)
    except ValueError as x: assert str(x) == sentence, (str(x), sentence); return
    raise AssertionError("passed: " + sentence)

@t
def event_record_and_its_check():
    e = _ev(going=[])
    assert e["kind"] == "event" and e["in_charge"] == "Ms Aisha Rahman" and e["going"] == [] and e["going_by"] == "people"
    assert e["status"] == "draft" and e["approved"] is None and e["made"] is None and e["created_by"] == "Ms Aisha Rahman"
    SC._check(_ev(), _PUB)
    _ev_bad("Give the event a name.", name=" ")
    _ev_bad("Pick at least one level or class.", levels=[])
    _ev_bad("An event can cover at most 31 days.", end="2026-11-30")
    _ev_bad("Gym is not a room of the published timetable.", venues=["Gym"])
    _ev_bad("Mr Nobody is not on the published timetable or the staff list.", going=["Mr Nobody"])
    _ev_bad(SC.WRONG, going_by="friends")
    _ev_bad(SC.WRONG, duties=[dict(duty="x", who=5, time="")])
    _ev_bad("07:50 is not the start of a period.", days={"2026-10-05": dict(whole=False, **{"from": "07:50", "to": "10:40"})})
    ok = _ev(going=["Ms Grace Yeo", "Ms Grace Yeo"]); SC._check(ok, _PUB)
    assert ok["going"] == ["Ms Grace Yeo"]
    d = _ev(duties=[dict(duty="gate", who=None, time=None)]); SC._check(d, _PUB)
    assert d["duties"] == [dict(duty="gate", who="", time="")]
    assert SC.place(_ev(where="", venues=["LT1&2", "Hall"])) == "LT1&2, Hall" and SC.place(_ev(where=" Field ")) == "Field" and SC.place(_ev(where="")) == ""

@t
def a_forged_event_carries_no_exam_items():
    e = _ev(made=dict(duties=[1]), papers=[_paper()], access=[dict(student="3A-01")], times=dict(report="x"), seating=dict(order="x"),
            supervision="lesson", scripts="the office", pins=dict(rooms={"k": {}}, duties={}), use_anyway=[["k", "r"]])
    SC._check(e, _PUB)
    assert (e["made"], e["papers"], e["access"], e["times"], e["seating"], e["supervision"], e["scripts"], e["use_anyway"]) == (
        None, [], [], {}, {}, "", "", []) and e["pins"] == dict(rooms={}, duties={})

@t
def fill_the_going_list():
    e = _ev(going=[])
    assert EV.fill(_PUB, F.CAL, e, "form teachers") == ["Ms Aisha Rahman", "Ms Chloe Tan"]
    assert EV.fill(_PUB, F.CAL, e, "teachers then") == ["Ms Aisha Rahman", "Ms Chloe Tan", "Mr Ben Ong", "Ms Grace Yeo"]
    assert EV.fill(_PUB, F.CAL, e, "department", dept="English") == ["Mr Ivan Lee", "Ms Aisha Rahman", "Ms Grace Yeo"]
    try: EV.fill(_PUB, F.CAL, e, "department", dept="")
    except ValueError as x: assert str(x) == "Pick a department."
    else: raise AssertionError
    assert EV.fill(_PUB, F.CAL, e, "people", names=["Mr Daniel Koh", "Mr Nobody"]) == ["Mr Daniel Koh"]
    try: EV.fill(_PUB, F.CAL, e, "friends")
    except ValueError as x: assert str(x) == SC.WRONG
    else: raise AssertionError
    assert EV.fill(_PUB, F.CAL, _ev(going=["Ms Aisha Rahman"]), "form teachers") == ["Ms Chloe Tan"]

@t
def who_goes_free_or_backup():
    e = _ev(going=["Ms Aisha Rahman", "Ms Grace Yeo", "Mr Hafiz Rahman", "Mr Ivan Lee"])
    assert EV.going(_PUB, F.CAL, e, []) == [
        dict(name="Ms Aisha Rahman", tag="teacher in charge · 3A form teacher", status="free", text="free then: lessons with 3A stop"),
        dict(name="Ms Grace Yeo", tag="", status="backup", text="teaches 4A Literature 08:40–09:00 → backup"),
        dict(name="Mr Hafiz Rahman", tag="", status="backup", text="teaches 4A PE 09:00–09:40 → backup"),
        dict(name="Mr Ivan Lee", tag="", status="not_free", text="is not available then (a Must rule)")]

@t
def event_lesson_lists():
    L = EV.lesson_lists(_PUB, F.CAL, _ev(going=["Mr Hafiz Rahman", "Ms Grace Yeo"]))
    assert [(i["subject"], i["classes"]) for i in L["none"]] == [("English", ["3A"]), ("Mathematics", ["3B"]),
                                                                  ("Pure Chemistry", ["3A", "3B"]), ("Combined Science", ["3A", "3B"])]
    assert [(i["subject"], i["start"], i["note"]) for i in L["backup"]] == [
        ("PE", "09:00", "Mr Hafiz Rahman is at Sec 3 Learning Journey"), ("Literature", "08:40", "Ms Grace Yeo is at Sec 3 Learning Journey")]
    assert [i["subject"] for i in L["runs"]] == ["Mathematics", "English", "Assembly"]
    assert EV.freed(_PUB, F.CAL, _ev()) == [dict(date="2026-10-05", start="07:40", end="10:40", rooms=["3-01", "3-02", "Lab 3-08"])]
    assert EV.freed(_PUB, F.CAL, _ev(venues=["3-01"]))[0]["rooms"] == ["3-02", "Lab 3-08"]

@t
def venues_taken_flag_running_lessons():
    assert EV.flags(_PUB, F.CAL, _ev(venues=["LT1&2", "Hall"])) == [
        "Mon 5 Oct 08:40–09:00: Literature with 4A uses LT1 then.", "Mon 5 Oct 09:00–09:40: PE with 4A uses Hall in wet weather then."]
    assert EV.flags(_PUB, F.CAL, _ev()) == []
    cut = _ev(days={"2026-10-05": dict(whole=False, **{"from": "07:40", "to": "08:00"})})
    assert EV.cuts(_PUB, F.CAL, cut) == ["On Mon 5 Oct the event time ends in the middle of 2 lessons."]
    assert EV.on_dates(_PUB, F.CAL, _ev(start="2026-10-12", end="2026-10-12", days={})) == []
    assert EV.on_dates(_PUB, F.CAL, _ev())[0]["classes"] == ["3A", "3B"]

@t
def event_busies_for_other_schedules():
    busy = SC.busies([dict(_ev(venues=["Hall"]), id="ev1", status="approved")], _M)
    assert busy == [dict(id="ev1", name="Sec 3 Learning Journey", status="approved", date="2026-10-05", start=460, end=640, room="",
                         names=["Ms Aisha Rahman", "Ms Grace Yeo", "Mr Hafiz Rahman"], classes=["3A", "3B"], kind="event"),
                    dict(id="ev1", name="Sec 3 Learning Journey", status="approved", date="2026-10-05", start=460, end=640, room="Hall",
                         names=[], classes=[], kind="event")], busy
    s = _sit([_paper(date="2026-10-05", start="07:50")], days=dict(SEC3))
    r = SE.rooms_free(_PUB, F.CAL, s, _first(s), _xset(), set(), elsewhere=busy)
    assert next(x for x in r if x["name"] == "Hall")["busy"] == "taken by Sec 3 Learning Journey until 10:40", r
    why = IV._free("Ms Aisha Rahman", D.day_view(_PUB, F.CAL, s, "2026-10-05"), 455, 540, [], _xset(), elsewhere=busy)[0]
    assert why == "is on Sec 3 Learning Journey then" and "()" not in why
    _reset()
    SC.save(dict(_ev(venues=["Hall"]), id="ev2", status="waiting"), _PUB, F.CAL, "t")
    SC.save(dict(_ev(), id="ev3", status="draft"), _PUB, F.CAL, "t")
    got = SC.elsewhere("zzzz", _M)
    assert [(b["id"], b["status"], b["room"]) for b in got] == [("ev2", "waiting", ""), ("ev2", "waiting", "Hall")], got
    assert [b["id"] for b in SC.elsewhere("ev2", _M)] == []
    _reset()
    SC.save(dict(_ev(), id="ev4", status="approved", approved=dict(_ev())), _PUB, F.CAL, "t")
    assert [(b["id"], b["status"]) for b in SC.elsewhere("zzzz", _M)] == [("ev4", "approved")]
    assert [c["status"] for c in SC.copies("zzzz")] == ["approved"]
    _reset()
    assert SC.event_busy(dict(_ev(), id="x", status="waiting"), dict(_M, NP=0, times=[], school={})) == []

@t
def event_busies_leave_out_a_waiting_copy_equal_to_the_approved_one():
    a = dict(_ev(), id="ev5", status="approved")
    w = dict(_ev(going=["Ms Aisha Rahman"]), id="ev5", status="waiting")
    got = SC.busies([a, w], _M)
    assert [(b["status"], b["names"]) for b in got] == [("approved", ["Ms Aisha Rahman", "Ms Grace Yeo", "Mr Hafiz Rahman"]), ("waiting", ["Ms Aisha Rahman"])], got
    assert [b["status"] for b in SC.busies([a, dict(a, status="waiting")], _M)] == ["approved"]

@t
def event_clashes_with_an_exam_for_the_same_class():
    A = _approved()
    others = [dict(AP.as_schedule(A), status="approved")]
    busy = SC.busies(others, _M)
    got = EV.clashes(_PUB, F.CAL, _ev(), busy, others)
    assert got == ["Ms Aisha Rahman, Mon 5 Oct 07:40–10:40: is on Sec 3 End-of-Year Exam then (3-01).",
                   "Mr Hafiz Rahman, Mon 5 Oct 07:40–10:40: is on Sec 3 End-of-Year Exam then (3-02).",
                   "Sec 3 End-of-Year Exam (approved) has 3A, 3B on Mon 5 Oct too."], got
    assert EV.send_errors(_PUB, F.CAL, _ev(), busy, others) == [
        "Fix the clashes first: Ms Aisha Rahman, Mon 5 Oct 07:40–10:40: is on Sec 3 End-of-Year Exam then (3-01)."]
    rv = RV.review(_PUB, F.CAL, A, _xset(("3-01", "3-02", "4-01", "Hall")), SC.busies([dict(_ev(), id="ev1", status="waiting")], _M))
    ch = {c["key"]: c["lines"] for c in rv["checks"]}
    assert ch["others"] == ["Sec 3 Learning Journey (waiting) takes 2 of these invigilators on Mon 5 Oct.",
                            "Sec 3 Learning Journey (waiting) has 3A, 3B on Mon 5 Oct too."], ch["others"]
    assert ch["free"] == ["Ms Aisha Rahman, 3-01 on Mon 5 Oct 07:35–09:00: is on Sec 3 Learning Journey then.",
                          "Mr Hafiz Rahman, 3-02 on Mon 5 Oct 09:45–11:10: is on Sec 3 Learning Journey then."], ch["free"]
    assert not any("()" in l for l in ch["free"] + got)

@t
def event_venue_taken_by_another_schedule():
    others = [dict(_ev(name="Sec 3 Talk", going=[], venues=["LT1"]), id="ev2", status="waiting")]
    mine = _ev(name="Sec 4 Talk", levels=["Sec 4"], days={"2026-10-05": dict(levels=["Sec 4"], whole=False, **{"from": "07:40", "to": "10:40"})},
               venues=["LT1&2"], going=["Mr Daniel Koh"], duties=[])
    assert EV.other_lines(_PUB, F.CAL, mine, SC.busies(others, _M), others) == ["Sec 3 Talk (waiting) uses LT1 on Mon 5 Oct too."]

@t
def event_send_errors():
    S = lambda e: EV.send_errors(_PUB, F.CAL, e, [], [])
    assert S(_ev()) == []
    assert S(_ev(going=[], duties=[])) == ["Add at least one person going with the classes."]
    assert S(_ev(start="2026-10-12", end="2026-10-12", days={})) == ["Pick at least one school day for the event."]
    assert S(_ev(duties=[dict(duty="First aid", who="Mr Ben Ong", time="all day")])) == ["Pick a person going for every duty."]
    assert S(_ev(going=["Ms Aisha Rahman", "Ms Grace Yeo", "Mr Hafiz Rahman", "Mr Ivan Lee"])) == [
        "Fix the clashes first: Mr Ivan Lee, Mon 5 Oct 07:40–10:40: is not available then (a Must rule)."]

@t
def who_may_replace_someone_going():
    assert EV.who_free(_PUB, F.CAL, _ev(), []) == dict(freed=[dict(name="Mr Ben Ong", reason="freed: lessons with 3A, 3B stop"),
                                                               dict(name="Ms Chloe Tan", reason="freed: lessons with 3B stop")], free=[])

@t
def a_multi_date_event_names_each_date():
    day = dict(levels=None, whole=False, **{"from": "07:40", "to": "10:40"})
    e = _ev(end="2026-10-06", going=["Ms Grace Yeo", "Mr Ivan Lee"], days={"2026-10-05": day, "2026-10-06": dict(day)})
    got = EV.going(_PUB, F.CAL, e, [])
    assert len(EV.on_dates(_PUB, F.CAL, e)) == 2, EV.on_dates(_PUB, F.CAL, e)
    assert got[0]["status"] == "backup" and "(Mon 5 Oct)" in got[0]["text"], got
    assert got[1]["status"] == "not_free" and got[1]["text"].endswith("(Mon 5 Oct)"), got

def _ev_ok(**kw):
    e = _ev(**kw)
    AP.send(e, _M, "Ms Aisha Rahman", NOW, False, [])
    AP.approve(e, "Timetable committee", NOW)
    return e

E1 = AP.as_schedule(_ev_ok(venues=["Hall"]))

@t
def event_states_and_copy():
    e = _ev()
    assert AP.blocked(e, _M, False, []) == ""
    assert AP.blocked(e, _M, False, ["Add at least one person going with the classes."]) == "Add at least one person going with the classes."
    e = _ev_ok()
    assert e["approved"]["going"] == e["going"] and set(AP.public(e)) == set(AP.SNAP + AP.EVENT_KEYS)
    assert AP.blocked(e, _M, False, []) == "Nothing on the main site changes."
    assert AP.label(e, date(2026, 10, 5)) == "Approved · on the main site" and AP.label(e, date(2026, 10, 6)) == "Ended"
    assert set(AP.public(_made_sched())) == set(AP.SNAP)
    w = _ev(); AP.send(w, _M, "Ms Aisha Rahman", NOW, False, [])
    try: AP.send_back(w, "  ", "Timetable committee", NOW)
    except ValueError as x: assert str(x) == "Write a note for the teacher in charge.", x
    else: raise AssertionError
    w["where"] = "Elsewhere"
    try: AP.approve(w, "Timetable committee", NOW)
    except ValueError as x: assert str(x) == "This schedule changed after it was sent. Ask the teacher in charge to send it again.", x
    else: raise AssertionError

@t
def event_changes_list():
    e = _ev_ok()
    e.update(where="Science Centre", venues=["Hall"], going=["Ms Aisha Rahman", "Mr Hafiz Rahman", "Mr Daniel Koh"], duties=[])
    assert [c["text"] for c in AP.changes(e, _M)] == ["Where: Off site (museum) → Science Centre.", "Venues taken: none → Hall.",
        "Mr Daniel Koh now goes with the classes.", "Ms Grace Yeo no longer goes with the classes.", "Duties at the event changed."]
    AP.send(e, _M, "Ms Aisha Rahman", NOW, False, [])
    assert e["status"] == "changes" and e["log"][-1]["detail"] == "5 changes"
    f = _ev_ok(); f["days"]["2026-10-05"]["to"] = "11:00"
    assert [c["text"] for c in AP.changes(f, _M)] == ["Mon 5 Oct: part of the day 07:40–10:40 (Sec 3) → part of the day 07:40–11:00 (Sec 3)."]
    g = _ev_ok(); g["days"] = {}
    assert [c["text"] for c in AP.changes(g, _M)] == ["Mon 5 Oct: part of the day 07:40–10:40 (Sec 3) → as the event."]

@t
def someone_away_from_an_event():
    e = _ev_ok()
    assert AP.replace_going(e, "Mr Hafiz Rahman", "Mr Ben Ong", "Ms Aisha Rahman", NOW) == "Mon 5 Oct, going: Mr Hafiz Rahman (away) → Mr Ben Ong"
    for c in (e, e["approved"]):
        assert c["going"] == ["Ms Aisha Rahman", "Ms Grace Yeo", "Mr Ben Ong"] and c["duties"][0]["who"] == "Mr Ben Ong", c
    assert e["status"] == "approved" and AP.changes(e, _M) == [] and AP.done_without(e)[0]["by"] == "Ms Aisha Rahman"
    for away, name, said in (("Mr Daniel Koh", "Mr Ben Ong", "Mr Daniel Koh is not going."), ("Ms Aisha Rahman", "Ms Grace Yeo", "Ms Grace Yeo is going already.")):
        try: AP.replace_going(_ev_ok(), away, name, "x", NOW)
        except ValueError as x: assert str(x) == said, x
        else: raise AssertionError
    try: AP.replace_going(_ev(), "Mr Hafiz Rahman", "Mr Ben Ong", "x", NOW)
    except ValueError as x: assert str(x) == "This schedule is not on the main site."
    else: raise AssertionError
    w = _ev_ok(); w["going"] = ["Ms Aisha Rahman", "Ms Grace Yeo", "Mr Ben Ong"]
    AP.replace_going(w, "Mr Hafiz Rahman", "Mr Ben Ong", "x", NOW)
    assert w["going"] == ["Ms Aisha Rahman", "Ms Grace Yeo", "Mr Ben Ong"]
    ev9 = dict(_ev_ok(), id="ev9")
    SC.save(ev9, _PUB, F.CAL, "t")
    got = [b for b in SC.elsewhere("zzzz", _M) if b["id"] == "ev9"]
    assert any(b["names"] == ev9["going"] and b["status"] == "approved" for b in got), got

@t
def event_review():
    e = _ev(venues=["LT1&2", "Hall"]); AP.send(e, _M, "Ms Aisha Rahman", NOW, False, [])
    r = EV.review(_PUB, F.CAL, e, [], [])
    assert r["copy"] == "working" and r["changes"] == [] and r["done_without"] == []
    assert r["what"] == dict(kind="event", classes=["3A", "3B"], levels=["Sec 3"], start="2026-10-05", end="2026-10-05",
        days=[dict(date="2026-10-05", whole=False, window=["07:40", "10:40"])], where="Off site (museum)", in_charge="Ms Aisha Rahman",
        stopped=4, going=3, backups=2, venues=[dict(room="Hall", dates=1, start="07:40", end="10:40"), dict(room="LT1&2", dates=1, start="07:40", end="10:40")],
        flagged=2), r["what"]
    assert [c["key"] for c in r["checks"]] == ["going", "venues", "others"]
    c = {x["key"]: x for x in r["checks"]}
    assert c["going"]["ok"] and c["going"]["lines"] == ["Everyone going is free then."]
    assert not c["venues"]["ok"] and c["venues"]["lines"] == EV.flags(_PUB, F.CAL, e) and len(c["venues"]["lines"]) == 2
    assert c["others"]["ok"] and c["others"]["lines"] == ["No clash with other schedules."]
    v = _ev(going=["Mr Ivan Lee"]); AP.send(v, _M, "Ms Aisha Rahman", NOW, False, [])
    assert EV.review(_PUB, F.CAL, v, [], [])["checks"][0]["lines"] == ["Mr Ivan Lee, Mon 5 Oct 07:40–10:40: is not available then (a Must rule)."]
    assert not EV.review(_PUB, F.CAL, v, [], [])["checks"][0]["ok"]


def _event(a):
    r = a.post("/api/events", json=dict(name="Sec 3 Learning Journey", levels=["Sec 3"], classes=[], start="2026-10-05", end="2026-10-05"))
    assert r.status_code == 200, r.data
    id = r.get_json()["id"]
    e = a.get("/api/events/" + id).get_json()
    e["days"] = {"2026-10-05": dict(levels=["Sec 3"], whole=False, **{"from": "07:40", "to": "10:40"})}
    e["where"] = "Off site (museum)"
    r = a.put("/api/events/" + id, json=e); assert r.status_code == 200, r.data
    return r.get_json()

def _approved_event(a, c):
    e = _event(a); id = e["id"]
    r = a.post(f"/api/events/{id}/fill", json=dict(way="form teachers")); assert r.status_code == 200, r.data
    r = a.post(f"/api/events/{id}/fill", json=dict(way="department", dept="PE")); assert r.status_code == 200, r.data
    r = a.post(f"/api/events/{id}/send"); assert r.status_code == 200, r.data
    r = c.post(f"/api/events/{id}/approve"); assert r.status_code == 200, r.data
    return e

@t
def any_teacher_may_start_an_event():
    _setup()
    with published(_PUB):
        a, c = staff("Ms Aisha Rahman"), committee()
        r = a.post("/api/events", json=dict(name="Sec 3 Learning Journey", levels=["Sec 3"], classes=[], start="2026-10-05", end="2026-10-05", in_charge="Mr Ben Ong"))
        assert r.status_code == 200 and r.get_json()["in_charge"] == "Ms Aisha Rahman" and r.get_json()["kind"] == "event", r.data
        id = r.get_json()["id"]
        rows = a.get("/api/events").get_json()["schedules"]
        assert len(rows) == 1 and rows[0]["label"] == "Draft" and rows[0]["in_charge"] == "Ms Aisha Rahman" and rows[0]["n_going"] == 0, rows
        r = a.get("/api/exams"); assert r.status_code == 403 and r.get_json() == {"error": A.ONLY_EXAMS}, r.data
        assert a.get("/api/events").get_json()["people"] == []
        assert a.get(f"/events/{id}").status_code == 200
        body = dict(name="Sec 3 Sports", levels=["Sec 3"], classes=[], start="2026-10-05", end="2026-10-05")
        r = c.post("/api/events", json=body); assert r.status_code == 400 and r.get_json() == {"error": A.PICK_IN_CHARGE}, r.data
        r = c.post("/api/events", json=dict(body, in_charge="Mr Nobody")); assert r.status_code == 400 and r.get_json() == {"error": "Mr Nobody is not on the published timetable or the staff list."}, r.data
        r = c.post("/api/events", json=dict(body, in_charge="Mr Ben Ong")); assert r.status_code == 200 and r.get_json()["in_charge"] == "Mr Ben Ong", r.data
        d = c.get("/api/events").get_json()
        assert len(d["schedules"]) == 2 and "Mr Ben Ong" in d["people"], d
        assert not any(x["kind"] == "event" for x in c.get("/api/exams").get_json()["schedules"])
        _cal(False)
        r = a.post("/api/events", json=body); assert r.status_code == 409 and r.get_json() == {"error": SC.NO_CALENDAR}, r.data

@t
def only_the_teacher_in_charge_and_the_committee():
    _setup()
    with published(_PUB):
        a, b, g, c = staff("Ms Aisha Rahman"), staff("Mr Ben Ong"), staff("Ms Grace Yeo"), committee()
        e = _event(a); id = e["id"]
        no = dict(error=A.ONLY_IN_CHARGE)
        for r in (b.get(f"/api/events/{id}"), b.put(f"/api/events/{id}", json=e), b.delete(f"/api/events/{id}"), b.post(f"/api/events/{id}/send"),
                  b.post(f"/api/events/{id}/fill", json=dict(way="form teachers")), b.post(f"/api/events/{id}/away", json=dict(away="x", name="y")),
                  b.get(f"/api/events/{id}/view"), b.get(f"/api/events/{id}/who")):
            assert r.status_code == 403 and r.get_json() == no, (r.status_code, r.data)
        assert b.get("/api/events").get_json()["schedules"] == []
        for r in (g.get(f"/api/exams/{id}"), g.put(f"/api/exams/{id}", json=e), g.delete(f"/api/exams/{id}")):
            assert r.status_code == 404 and r.get_json() == {"error": A.NO_EXAM}, (r.status_code, r.data)
        assert a.get(f"/api/events/{id}").status_code == 200, "the delete did not remove it"
        assert not any(x["id"] == id for x in g.get("/api/exams").get_json()["schedules"])
        x = _exam(g); x["kind"] = "event"
        r = g.put("/api/exams/" + x["id"], json=x); assert r.status_code == 400 and r.get_json() == {"error": SC.WRONG}, r.data
        assert g.get("/api/exams/" + x["id"]).get_json()["kind"] == "exam"
        assert c.get(f"/api/events/{id}").status_code == 200 and any(r_["id"] == id for r_ in c.get("/api/events").get_json()["schedules"])
        e = a.get(f"/api/events/{id}").get_json()
        r = a.put(f"/api/events/{id}", json=dict(e, in_charge="Mr Ben Ong", status="approved", approved=dict(start="2026-10-05"), approved_by="x")); assert r.status_code == 200, r.data
        got = a.get(f"/api/events/{id}").get_json()
        assert got["in_charge"] == "Ms Aisha Rahman" and got["status"] == "draft" and not got["approved"] and got["approved_by"] is None, got
        r = a.post(f"/api/events/{id}/approve"); assert r.status_code == 403 and r.get_json() == {"error": A.ONLY_APPROVE}, r.data
        r = g.get(f"/api/events/{x['id']}"); assert r.status_code == 404 and r.get_json() == {"error": A.NO_EVENT}, r.data
        assert c.get(f"/api/events/{x['id']}").status_code == 404

@t
def a_forged_event_put_puts_no_exam_items_on_the_site():
    _setup()
    with published(_PUB):
        a, c = staff("Ms Aisha Rahman"), committee()
        id = _event(a)["id"]
        a.post(f"/api/events/{id}/fill", json=dict(way="form teachers"))
        got = a.get(f"/api/events/{id}").get_json()
        forged = dict(got, papers=[_paper()], access=[dict(student="3A-01", extra=25)], times=dict(report="07:30", min_break=20, max_papers=2),
                      made=dict(duties=[dict(key="k", room="3-01", date="2026-10-05", start=460, end=540, names=["Mr Ben Ong"], backup=[], short=0)], seats={}, unseated={}),
                      supervision="lesson", scripts="x", pins=dict(rooms={"a": 1}, duties={}), use_anyway=["x"])
        r = a.put(f"/api/events/{id}", json=forged); assert r.status_code == 200, r.data
        s = SC.load(id)
        assert s["papers"] == [] and s["access"] == [] and s["made"] is None and s["use_anyway"] == [] and s["scripts"] == "", s
        r = a.post(f"/api/events/{id}/send"); assert r.status_code == 200, r.data
        assert c.post(f"/api/events/{id}/approve").status_code == 200
        site = [x for x in SC.on_site() if x["id"] == id][0]
        assert site["papers"] == [] and not (site.get("made") or {}).get("duties") and not (site.get("made") or {}).get("seats") and site["access"] == [], site

@t
def fill_view_send_approve():
    _setup()
    with published(_PUB):
        a, c = staff("Ms Aisha Rahman"), committee()
        e = _event(a); id = e["id"]
        r = a.post(f"/api/events/{id}/send"); assert r.status_code == 400 and r.get_json() == {"error": "Add at least one person going with the classes."}, r.data
        r = a.post(f"/api/events/{id}/fill", json=dict(way="form teachers")); assert r.status_code == 200, r.data
        assert r.get_json()["going"] == ["Ms Aisha Rahman", "Ms Chloe Tan"] and r.get_json()["going_by"] == "form teachers", r.get_json()
        r = a.post(f"/api/events/{id}/fill", json=dict(way="department", dept="PE")); assert r.status_code == 200, r.data
        assert r.get_json()["going"] == ["Ms Aisha Rahman", "Ms Chloe Tan", "Mr Hafiz Rahman"] and r.get_json()["going_by"] == "department"
        r = a.post(f"/api/events/{id}/fill", json=dict(way="people", names="x")); assert r.status_code == 400, r.data
        v = a.get(f"/api/events/{id}/view").get_json()
        assert [x["status"] for x in v["going"]] == ["free", "free", "backup"], v["going"]
        assert len(v["lessons"]["none"]) == 4 and v["freed"][0]["rooms"] == ["3-01", "3-02", "Lab 3-08"], (v["lessons"]["none"], v["freed"])
        assert v["summary"]["days"][0]["date"] == "2026-10-05" and v["summary"]["days"][0]["whole"] is False and v["summary"]["days"][0]["window"] == ["07:40", "10:40"], v["summary"]
        assert v["classes"] == ["3A", "3B"] and "PE" in v["depts"] and "Ms Aisha Rahman" in v["people"] and "Hall" in v["rooms"], v
        for k in ("flags", "cuts", "clashes", "periods"): assert k in v, k
        r = a.post(f"/api/events/{id}/send"); assert r.status_code == 200, r.data
        assert r.get_json()["label"] == "Waiting for the timetable committee" and r.get_json()["review"]["what"]["kind"] == "event", r.data
        assert a.get(f"/api/events/{id}/review").status_code == 200
        r = c.post(f"/api/events/{id}/approve"); assert r.status_code == 200, r.data
        site = [x for x in SC.on_site() if x["id"] == id][0]
        assert site["going"] == ["Ms Aisha Rahman", "Ms Chloe Tan", "Mr Hafiz Rahman"], site
        assert a.get(f"/api/events/{id}/who").status_code == 200

@t
def event_send_refused_on_a_clash():
    _setup()
    with published(_PUB):
        a, c = staff("Ms Aisha Rahman"), committee()
        _approved_exam(c)
        e = _event(a); id = e["id"]
        a.post(f"/api/events/{id}/fill", json=dict(way="form teachers"))
        r = a.post(f"/api/events/{id}/send"); assert r.status_code == 400 and r.get_json()["error"].startswith("Fix the clashes first: "), r.data
        rv = a.get(f"/api/events/{id}/review").get_json()
        others = [x for x in rv["review"]["checks"] if x["key"] == "others"][0]["lines"]
        assert "Sec 3 Exam (approved) has 3A, 3B on Mon 5 Oct too." in others, others

@t
def away_on_an_approved_event():
    _setup()
    with published(_PUB):
        a, c = staff("Ms Aisha Rahman"), committee()
        e = _approved_event(a, c); id = e["id"]
        w = a.get(f"/api/events/{id}/who").get_json()
        assert [x["name"] for x in w["freed"]] == ["Mr Ben Ong"], w
        r = a.post(f"/api/events/{id}/away", json=dict(away="Mr Hafiz Rahman", name="Mr Daniel Koh")); assert r.status_code == 400 and r.get_json() == {"error": "Mr Daniel Koh is not free then."}, r.data
        r = a.post(f"/api/events/{id}/away", json=dict(away="Mr Hafiz Rahman", name="Mr Ben Ong")); assert r.status_code == 200, r.data
        site = [x for x in SC.on_site() if x["id"] == id][0]
        assert site["going"] == ["Ms Aisha Rahman", "Ms Chloe Tan", "Mr Ben Ong"], site["going"]
        assert r.get_json()["review"]["done_without"][0]["detail"] == "Mon 5 Oct, going: Mr Hafiz Rahman (away) \u2192 Mr Ben Ong", r.get_json()["review"]["done_without"]
        r = a.delete(f"/api/events/{id}"); assert r.status_code == 409 and r.get_json() == {"error": A.ON_SITE}, r.data
        assert c.post(f"/api/events/{id}/withdraw").status_code == 200 and SC.on_site() == []
        assert a.delete(f"/api/events/{id}").status_code == 200 and SC.load(id) is None

@t
def event_rights_stay_inside_helpers():
    src = open(os.path.join(ROOT, "app.py"), encoding="utf-8").read()
    assert "def _event_rights(" in src and "def _event_gate(" in src


# ---- events on the main site (stage 4, task 5)
_EVK = {"start", "end", "label", "room", "seat_note", "exam", "kind", "p", "n"}

@t
def event_on_a_date():
    e = PB.day(_PUB, F.CAL, [E1], "2026-10-05", True)["exams"]
    assert e["stopped"] == [0, 1, 3, 4], e["stopped"]
    assert e["classes"]["3A"] == [dict(start="07:40", end="10:40", label="Sec 3 Learning Journey", room="Off site (museum)",
                                       seat_note="", exam="Sec 3 Learning Journey", kind="event", p=0.0, n=9.0)], e["classes"]
    assert "4A" not in e["classes"]
    assert e["teachers"]["Mr Hafiz Rahman"] == [dict(start="07:40", end="10:40", label="Sec 3 Learning Journey", room="Off site (museum)",
                                                     role="At event", duty="Bus marshal 07:45", exam="Sec 3 Learning Journey", kind="event", p=0.0, n=9.0)]
    assert e["teachers"]["Ms Grace Yeo"][0]["duty"] == "", e["teachers"]["Ms Grace Yeo"]
    assert set(e["rooms"]) == {"Hall"}, e["rooms"]
    assert e["banner"] == "Sec 3 Learning Journey"

@t
def student_code_sees_name_where_time_only():
    d = PB.day(_PUB, F.CAL, [E1], "2026-10-05", False)
    assert d["exams"]["teachers"] == {} and d["exams"]["rooms"] == {}
    assert d["exams"]["classes"] == PB.day(_PUB, F.CAL, [E1], "2026-10-05", True)["exams"]["classes"]
    blob = json.dumps(d) + json.dumps(PB.listing(_PUB, [E1], date(2026, 10, 1), False, cal=F.CAL))
    for w in ("Ms Aisha Rahman", "Ms Grace Yeo", "Mr Hafiz Rahman", "Bus marshal"):
        assert w not in blob, w
    r = PB.listing(_PUB, [E1], date(2026, 10, 1), False, cal=F.CAL)["schedules"][0]
    assert set(r) == {"id", "name", "kind", "start", "end", "classes", "where", "days"}, set(r)
    out = PB.listing(_PUB, [E1], date(2026, 10, 1), True, cal=F.CAL)
    f = out["schedules"][0]
    assert f["in_charge"] == "Ms Aisha Rahman" and f["going"] == _ev()["going"], f
    assert f["duties"] == [dict(duty="Bus marshal", who="Mr Hafiz Rahman", time="07:45")], f["duties"]
    assert f["days"] == [dict(date="2026-10-05", start="07:40", end="10:40")], f["days"]
    assert out["banner"] == "Sec 3 Learning Journey: Mon 5 Oct.", out["banner"]

@t
def event_and_exam_on_one_date():
    e = PB.day(_PUB, F.CAL, [A1, E1], "2026-10-05", True)["exams"]
    assert [(x["start"], x["label"]) for x in e["classes"]["3A"]] == [
        ("07:40", "Sec 3 Learning Journey"), ("07:50", "Sec 3 English Paper 1"), ("10:00", "Sec 3 Pure Chemistry Paper 1")], e["classes"]["3A"]
    assert [(x["start"], x["role"]) for x in e["teachers"]["Ms Aisha Rahman"]] == [("07:35", "Invigilate"), ("07:40", "At event")], e["teachers"]["Ms Aisha Rahman"]
    assert e["banner"] == "Sec 3 End-of-Year Exam · Sec 3 Learning Journey", e["banner"]
    assert 7 not in e["stopped"]

@t
def my_event_duties_and_timetable():
    d = date(2026, 10, 1)
    out = PB.my_duties(_PUB, F.CAL, [E1], "Mr Hafiz Rahman", d)
    assert out == dict(schedules=[dict(id=E1["id"], name="Sec 3 Learning Journey", kind="event", where="Off site (museum)", in_charge="Ms Aisha Rahman",
                                       minutes=180, duties=[dict(date="2026-10-05", start="07:40", end="10:40", duty="Bus marshal 07:45")])], lessons=[]), out
    g = PB.my_duties(_PUB, F.CAL, [E1], "Ms Grace Yeo", d)
    assert g["lessons"] == [dict(date="2026-10-05", start="09:40", end="10:40", classes=["3A", "3B"], subject="Combined Science")], g["lessons"]
    b = PB.my_duties(_PUB, F.CAL, [E1], "Mr Ben Ong", d)
    assert b["schedules"] == [] and [(x["start"], x["end"], x["subject"]) for x in b["lessons"]] == [("09:40", "10:40", "Pure Chemistry")], b["lessons"]
    ev = dict(id=E1["id"], name="Sec 3 Learning Journey", kind="event", where="Off site (museum)", papers=[],
              days=[dict(date="2026-10-05", start="07:40", end="10:40", note="then lessons from 10:40")])
    assert PB.my_exams(_PUB, F.CAL, [E1], "3A-07", d)["schedules"] == [ev]
    assert PB.my_exams(_PUB, F.CAL, [E1], "4A-01", d)["schedules"] == []
    both = PB.my_exams(_PUB, F.CAL, [A1, E1], "3A-07", d)["schedules"]
    assert [x["name"] for x in both] == ["Sec 3 End-of-Year Exam", "Sec 3 Learning Journey"] and both[0]["kind"] == "exam" and both[1] == ev, both

@t
def event_routes_on_the_main_site():
    _setup()
    with published(_PUB):
        a, c = staff("Ms Aisha Rahman"), committee()
        e = _approved_event(a, c); id = e["id"]
        with _today(date(2026, 10, 1)):
            r = as_role("student").get("/api/day?date=2026-10-05"); assert r.status_code == 200, r.data
            it = r.get_json()["exams"]["classes"]["3A"][0]
            assert set(it) == _EVK and it["kind"] == "event", it
            assert r.get_json()["exams"]["teachers"] == {}
            for n in ("Ms Aisha Rahman", "Ms Chloe Tan", "Mr Hafiz Rahman", "Bus marshal"):
                assert n not in r.get_data(as_text=True), n
            s = [x for x in as_role("student").get("/api/published/exams").get_json()["schedules"] if x["id"] == id][0]
            assert "going" not in s and "in_charge" not in s, s
            t_ = [x for x in as_role("teacher").get("/api/published/exams").get_json()["schedules"] if x["id"] == id][0]
            assert t_["going"] == ["Ms Aisha Rahman", "Ms Chloe Tan", "Mr Hafiz Rahman"], t_["going"]
            assert c.get(f"/api/published/exams/{id}/print/seating.pdf").status_code == 404
            md = as_role("staff", who="Mr Hafiz Rahman").get("/api/exams/my-duties").get_json()
            assert [x["id"] for x in md["schedules"]] == [id] and md["schedules"][0]["kind"] == "event", md
            me = as_role("personal", sid="3A-07").get("/api/me/exams").get_json()
            assert [x["id"] for x in me["schedules"]] == [id] and me["schedules"][0]["days"][0]["date"] == "2026-10-05", me

@t
def event_cannot_be_forged_or_decided_by_its_teacher():
    _setup()
    with published(_PUB):
        a, c = staff("Ms Aisha Rahman"), committee()
        e = _event(a); id = e["id"]
        e["kind"] = "exam"
        assert a.put("/api/events/" + id, json=e).status_code == 200
        assert SC.load(id)["kind"] == "event"
        a.post(f"/api/events/{id}/fill", json=dict(way="form teachers"))
        assert a.post(f"/api/events/{id}/send").status_code == 200
        assert a.post(f"/api/events/{id}/send-back").status_code != 200 and SC.load(id)["status"] == "waiting", SC.load(id)["status"]
        assert c.post(f"/api/events/{id}/approve").status_code == 200
        assert a.post(f"/api/events/{id}/withdraw").status_code != 200 and SC.load(id)["status"] == "approved"

print(f"{COUNT} exams tests passed")

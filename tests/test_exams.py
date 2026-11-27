"""Plain-assert tests for exams: .venv/bin/python tests/test_exams.py"""
import os, re, secrets, sys, tempfile, time
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

from flask.testing import FlaskClient  # noqa: E402

class _Page(FlaskClient):
    """a test client that saves like a page that has just reloaded: a PUT of an exam or event carries the stored revision,
    so the many tests that save an old copy of a schedule they hold still test what they were written for. A PUT with the
    header X-Old-Page is sent as it is: the tests of the revision check itself use that"""
    def open(self, *args, **kw):
        body, path = kw.get("json"), str(args[0]) if args and isinstance(args[0], str) else ""
        m = re.fullmatch(r"/api/(exams|events)/([A-Za-z0-9]+)", path)
        if kw.get("method") == "PUT" and m and isinstance(body, dict) and "X-Old-Page" not in (kw.get("headers") or {}):
            kw["json"] = dict(body, rev=SC.rev_of(SC.load(m.group(2)))) if SC.load(m.group(2)) else body
        return super().open(*args, **kw)

A.app.test_client_class = _Page

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
    assert "committee" not in d, "the exams committee is the accounts' Exams and events extra now"
    out = ES.save(dict(committee=["Ms Grace Yeo"], rooms={"Hall": dict(seats=240, rows=24, cols=10, hall=True, access=False, note="")},
                       backups=["Mr Ivan Lee"]), pub, "Ms Grace Yeo")
    assert "committee" not in out and out["backups"] == ["Mr Ivan Lee"] and out["saved_by"] == "Ms Grace Yeo"
    assert "committee" not in store.read_json(ES.PATH), "a committee list sent is not saved"
    assert out["rooms"]["Hall"]["seats"] == 240
    assert ES.load(pub) == out

@t
def settings_refuse_bad_values():
    pub = F.sample_pub()
    hall = dict(seats=240, rows=24, cols=10, hall=True, access=False, note="")
    raises(ValueError, lambda: ES.save(dict(backups=["Mr Nobody"]), pub, "x"), "Mr Nobody is not on the published timetable or the staff list.")
    raises(ValueError, lambda: ES.save(dict(rooms={"Gym": hall}), pub, "x"), "Gym is not a room of the published timetable.")
    raises(ValueError, lambda: ES.save(dict(rooms={"Hall": dict(hall, seats=0)}), pub, "x"), "Give Hall a number of exam seats.")
    raises(ValueError, lambda: ES.save(dict(rooms={"Hall": dict(hall, rows=10, cols=10)}), pub, "x"), "Hall: rows times columns is less than its exam seats.")
    raises(ValueError, lambda: ES.save(dict(rules=dict(per_classroom="two")), pub, "x"), "Give a whole number for invigilators per classroom.")
    raises(ValueError, lambda: ES.save(dict(backups="Ms Grace Yeo"), pub, "x"), "Check the settings and try again.")

@t
def settings_save_ignores_the_committee_list():
    _fresh()
    pub = F.sample_pub()
    os.makedirs(os.path.dirname(ES.PATH), exist_ok=True)
    store.write_json(ES.PATH, dict(committee=["Ms Grace Yeo", "Mr Gone Away"], backups=["Mr Ivan Lee"]))
    d = ES.load(pub)
    assert "committee" not in d and d["missing"] == [] and d["backups"] == ["Mr Ivan Lee"], d
    for sent in ("not a list", ["Mr Nobody"], [5], []):                           # ignored, never refused
        out = ES.save(dict(committee=sent, backups=["Mr Ben Ong"]), pub, "x")
        raw = store.read_json(ES.PATH)
        assert raw["committee"] == ["Ms Grace Yeo", "Mr Gone Away"] and raw["backups"] == ["Mr Ben Ong"], raw   # kept as stored
        assert "committee" not in out
    _fresh()

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

from accounts import people as ACC  # noqa: E402   (AP is exams.approval)
import datetime as _dt  # noqa: E402
AGAIN = {"error": "Please sign in again."}
LATER = (_dt.date.today() + _dt.timedelta(days=30)).isoformat()
EARLIER = (_dt.date.today() - _dt.timedelta(days=1)).isoformat()

def signed_in(code):
    """the one box of the sign-in page"""
    c = A.app.test_client()
    return c, c.post("/login", data={"code": code})

def committee():
    c, r = signed_in(os.environ["COMMITTEE_CODE"]); assert r.status_code == 302
    return c

def exams_until(name, until):
    """the person's Exams and events extra in the accounts (None: taken off)"""
    ACC.update(lambda d: d["people"].setdefault(name, {}).setdefault("extras", {}).update(exams=until))

def staff(name, via="code", until=None):
    """a session of the person signed in by name, as tests/test_routes.py builds them; until: their Exams and events extra"""
    if until is not None: exams_until(name, until)
    c = A.app.test_client()
    with c.session_transaction() as s:
        s.update(who=name, via=via, n=ACC.record(ACC.load(), name)["n"])
        if via == "password": s["exp"] = time.time() + 3600
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
def exams_tile_on_the_home_page():
    with published(_PUB):
        front = A.app.test_client().get("/login").data
        assert b"Exams and events" not in front and b"choice-exams.svg" not in front, "one box, no cards"
        c, r = signed_in(access.staff_code("Ms Grace Yeo"))
        assert r.status_code == 302 and r.headers["Location"] == "/home", r.headers
        page = c.get("/home").data.decode()
        assert 'href="/exams"' in page and "My exam and event duties" in page and "Exams and events" not in page and 'href="/relief"' in page, "no Exams and events extra: her own duties and events only"
        exams_until("Ms Grace Yeo", LATER)
        try:
            page = c.get("/home").data.decode()
            d = _dt.date.fromisoformat(LATER)
            assert 'href="/exams"' in page and "Exams and events" in page and f"Until {d.day} {d.strftime('%b %Y')}" in page, page
        finally: exams_until("Ms Grace Yeo", None)
        _, r = signed_in(os.environ["TEACHER_CODE"])
        assert r.status_code == 302 and r.headers["Location"] == "/timetable", r.headers
    assert not hasattr(A, "CHOICES") and not hasattr(A, "CHOICE_OF")

@t
def only_the_committees_get_in():
    _reset(); _cal()
    with published(_PUB):
        s = staff("Ms Grace Yeo")
        r = s.get("/api/exams"); assert r.status_code == 401 and r.get_json() == AGAIN, r.data
        assert s.get("/api/exams/settings").status_code == 401
        # no extra: the exams page opens for her own exam and event duties and her own events only (stage 2's My exam duties,
        # stage 4's My exam and event duties), nothing of the exams' working
        assert s.get("/api/exams/me").get_json() == dict(name="Ms Grace Yeo", can_use=False, can_approve=False, home="/home")
        assert s.get("/exams").status_code == 200
        r = s.get("/exams/settings"); assert r.status_code == 302 and r.headers["Location"].endswith("/login"), r.headers
        c = committee()
        assert c.get("/api/exams").status_code == 200
        assert c.get("/api/exams/me").get_json() == dict(name="Timetable committee", can_use=True, can_approve=True, home="/")
        d = c.get("/api/exams/settings").get_json()
        assert d["lists"] == dict(committee=[]) and d["can_admin"] is False and "committee_ok" not in d and "committee" not in d["settings"], d
        assert {"name": "Hall", "kind": "pe venue", "capacity": 400} in [dict(zip(("name", "kind", "capacity"), r)) if isinstance(r, list) else r for r in d["rooms"]], d["rooms"]
        r = c.put("/api/exams/settings", json=dict(d["settings"], committee=["Ms Grace Yeo"])); assert r.status_code == 200, r.data
        assert "committee" not in store.read_json(ES.PATH) and r.get_json()["lists"] == dict(committee=[]), "only an admin, on the admin page"
        assert s.get("/api/exams").status_code == 401, "the exams committee list no longer opens exams: the accounts do"
        exams_until("Ms Grace Yeo", LATER)
        assert s.get("/api/exams").status_code == 200
        assert s.get("/api/exams/me").get_json() == dict(name="Ms Grace Yeo", can_use=True, can_approve=False, home="/home")
        assert s.get("/exams").status_code == 200 and s.get("/exams/settings").status_code == 200
        mine = s.get("/api/exams/settings").get_json()
        assert mine["lists"] == dict(committee=[["Ms Grace Yeo", LATER]]) and mine["can_admin"] is False, mine["lists"]
        assert c.get("/api/exams/settings").get_json()["lists"] == mine["lists"]
        for names in (["Ms Grace Yeo", "Mr Ben Ong"], [], "x"):
            r = s.put("/api/exams/settings", json=dict(mine["settings"], committee=names, backups=["Mr Ivan Lee"]))
            assert r.status_code == 200 and r.get_json()["lists"] == mine["lists"], r.data
            assert "committee" not in store.read_json(ES.PATH) and ES.load(_PUB)["backups"] == ["Mr Ivan Lee"]
            assert ES.load(_PUB)["saved_by"] == "Ms Grace Yeo"
        r = c.put("/api/exams/settings", json=dict(mine["settings"], committee=["Ms Grace Yeo", "Mr Ben Ong"]))
        assert r.status_code == 200 and "committee" not in store.read_json(ES.PATH) and ACC.record(ACC.load(), "Mr Ben Ong")["extras"]["exams"] is None
        from werkzeug.security import generate_password_hash
        ACC.update(lambda d: d["people"].setdefault("Ms Ada Koh", {}).update(group="committee", added=True, username="ada.koh",
                                                                            pw=generate_password_hash(secrets.token_hex(8)),   # a password session needs one
                                                                            extras=dict(relief=False, exams=None, admin=True)))
        try:
            a = staff("Ms Ada Koh", via="password")                      # an admin: the line links to the admin page
            j = a.get("/api/exams/settings").get_json(); assert j["can_admin"] is True and j["lists"] == mine["lists"], j
            assert a.get("/api/exams/me").get_json() == dict(name="Ms Ada Koh", can_use=True, can_approve=True, home="/home")
            assert staff("Ms Ada Koh").get("/api/exams").status_code == 401, "her code opens no committee rights and she has no Exams extra"
        finally: ACC.update(lambda d: d["people"].pop("Ms Ada Koh"))
        assert c.put("/api/exams/settings", json="x").status_code == 400
        assert c.put("/api/exams/settings", data="{bad", content_type="application/json").status_code == 400
        exams_until("Ms Grace Yeo", EARLIER)
        assert s.get("/api/exams").status_code == 401 and s.get("/api/exams/me").get_json()["can_use"] is False, "past the end date: her own duties only"
        exams_until("Ms Grace Yeo", None)
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

# ---- exams' committee list moves into the accounts (the Exams and events extra, until 31 December), once
import history as H  # noqa: E402

DEC = "%d-12-31" % _dt.date.today().year

def moved_line(name, until=None):
    d = _dt.date.fromisoformat(until or DEC)
    return f"{name}: Exams and events until {d.day} {d.strftime('%b %Y')} (from the exams committee list: check the end date)"

def _no_accounts():
    if os.path.exists(ACC.PATH): os.remove(ACC.PATH)

@t
def migrate_moves_the_exams_committee_list_once():
    _no_accounts()
    assert ACC.blank()["migrated_exams"] is False and ACC._fill({"migrated_exams": "yes"})["migrated_exams"] is False
    assert ACC.migrate(_PUB, {}, None) is None and not os.path.exists(ACC.PATH), "no exams settings: nothing to move yet"
    assert ACC.migrate(_PUB, {}, dict(committee=[])) is None and not os.path.exists(ACC.PATH), "nothing to move: no file is made"
    n0 = len(H.read(kinds=["account"], limit=10000))
    raw = dict(committee=["Ms Grace Yeo", " Mr Ben Ong ", "Ms Grace Yeo", 5, ""], backups=["Mr Ivan Lee"])
    lines = ACC.migrate(None, {}, raw)                    # an extra needs no role: it moves while nothing is published too
    assert lines == [moved_line("Ms Grace Yeo"), moved_line("Mr Ben Ong")], lines
    d = ACC.load()
    assert d["migrated_exams"] is True and d["moved"] == lines, d
    assert ACC.record(d, "Ms Grace Yeo")["extras"]["exams"] == DEC and ACC.record(d, "Mr Ben Ong")["extras"]["exams"] == DEC
    assert ACC.record(d, "Mr Ivan Lee")["extras"]["exams"] is None and "Mr Ivan Lee" not in d["people"]
    got = H.read(kinds=["account"], limit=10000); assert len(got) == n0 + 1, (n0, len(got))
    e = got[0]
    assert (e["what"], e["text"], e["people"]) == ("moved", "Moved from the exams committee list", ["Ms Grace Yeo", "Mr Ben Ong"]), e
    assert (e["who"], e["as"], e["via"]) == (None, "The app", "app"), e
    assert ACC.migrate(_PUB, {}, dict(committee=["Ms Chloe Tan"])) is None and ACC.load()["moved"] == lines, "once"
    assert ACC.record(ACC.load(), "Ms Chloe Tan")["extras"]["exams"] is None and len(H.read(kinds=["account"], limit=10000)) == n0 + 1
    # a live install whose relief lists moved before exams arrived: the exams list still moves once, its lines after relief's
    relief_line = "Mr Ivan Lee: Relief team (from relief's Team list)"
    ACC.update(lambda d: d.update(people={"Ms Grace Yeo": dict(extras=dict(relief=False, exams="2099-03-31", admin=False))},
                                 migrated=True, migrated_exams=False, moved=[relief_line]))
    lines = ACC.migrate(_PUB, dict(team=["Mr Daniel Koh"]), dict(committee=["Ms Grace Yeo", "Ms Chloe Tan"]))
    assert lines == [moved_line("Ms Grace Yeo", "2099-03-31"), moved_line("Ms Chloe Tan")], lines   # a later end date given is kept
    d = ACC.load()
    assert d["moved"] == [relief_line] + lines and d["migrated"] is True and d["migrated_exams"] is True, d["moved"]
    assert ACC.record(d, "Ms Grace Yeo")["extras"]["exams"] == "2099-03-31" and ACC.record(d, "Ms Chloe Tan")["extras"]["exams"] == DEC
    assert ACC.record(d, "Mr Daniel Koh")["extras"]["relief"] is False, "relief's part is not done twice"
    # a new install: both lists in one call, an entry each
    _no_accounts(); n0 = len(H.read(kinds=["account"], limit=10000))
    lines = ACC.migrate(_PUB, dict(team=["Mr Daniel Koh"]), dict(committee=["Ms Chloe Tan"]))
    assert lines == ["Mr Daniel Koh: Relief team (from relief's Team list)", moved_line("Ms Chloe Tan")], lines
    d = ACC.load(); assert d["migrated"] is True and d["migrated_exams"] is True and d["moved"] == lines
    got = H.read(kinds=["account"], limit=10000); assert len(got) == n0 + 2
    assert [e["text"] for e in got[:2]] == ["Moved from the exams committee list", "Moved from relief's lists"], [e["text"] for e in got[:2]]
    # relief waits for a publish (a Management name needs its role): the exams list does not wait
    _no_accounts()
    assert ACC.migrate(None, dict(management=["Ms Chloe Tan"]), dict(committee=["Mr Ben Ong"])) == [moved_line("Mr Ben Ong")]
    d = ACC.load(); assert d["migrated"] is False and d["migrated_exams"] is True and ACC.record(d, "Ms Chloe Tan")["group"] is None
    _no_accounts()

@t
def the_startup_call_and_the_settings_routes_move_the_list():
    _reset(); _cal(); _no_accounts()
    os.makedirs(os.path.dirname(ES.PATH), exist_ok=True)
    store.write_json(ES.PATH, dict(committee=["Ms Chloe Tan"], backups=["Mr Ivan Lee"]))
    with published(_PUB):
        assert A.move_relief_lists() == [moved_line("Ms Chloe Tan")] and A.move_relief_lists() is None
        _no_accounts()
        r = committee().get("/exams/settings"); assert r.status_code == 200
        assert ACC.load()["migrated_exams"] is True and ACC.record(ACC.load(), "Ms Chloe Tan")["extras"]["exams"] == DEC
        for call in (lambda c: c.get("/api/exams/settings"), lambda c: c.put("/api/exams/settings", json=dict(backups=["Mr Ivan Lee"]))):
            _no_accounts()
            j = call(committee()).get_json()
            assert j["lists"] == dict(committee=[["Ms Chloe Tan", DEC]]), j
        assert staff("Ms Chloe Tan").get("/api/exams").status_code == 200, "the moved name opens exams"
        assert store.read_json(ES.PATH)["committee"] == ["Ms Chloe Tan"], "the old list stays in the file, for the record"
    _no_accounts(); _reset()

@t
def each_exams_save_writes_one_entry():
    import io
    _reset(); _cal(); _rooms_saved()
    with published(_PUB):
        s = staff("Ms Grace Yeo", until=LATER)
        n = [len(H.read(kinds=["exams"], limit=10000))]
        def wrote(r, what, text):
            assert r.status_code == 200, (what, r.status_code, r.data[:200])
            got = H.read(kinds=["exams"], limit=10000)
            assert len(got) == n[0] + 1, (what, n[0], len(got)); n[0] += 1
            e = got[0]
            assert (e["what"], e["text"], e["where"], e["link"]) == (what, text, "Exams and events", "/exams"), e
            assert (e["who"], e["as"], e["via"]) == ("Ms Grace Yeo", "Ms Grace Yeo", "code"), e
            return e
        def none(r, code):
            assert r.status_code == code, (r.status_code, r.data[:200])
            assert len(H.read(kinds=["exams"], limit=10000)) == n[0], "no entry"
        st = s.get("/api/exams/settings").get_json()["settings"]
        wrote(s.put("/api/exams/settings", json=st), "settings", "Exam settings saved")
        none(s.put("/api/exams/settings", json="x"), 400)
        r = s.post("/api/exams", json=dict(kind="exam", name="Mid-year exam", levels=["Sec 3"], start="2026-10-05", end="2026-10-06"))
        x = r.get_json(); e = wrote(r, "create", "Mid-year exam: created"); assert e["exam"] == x["id"], e
        none(s.post("/api/exams", json=dict(kind="party", name="X")), 400)
        x["days"] = dict(SEC3)
        wrote(s.put("/api/exams/" + x["id"], json=x), "edit", "Mid-year exam: changed")
        none(s.put("/api/exams/" + x["id"], json=dict(x, papers="x")), 400)
        none(s.put("/api/exams/ffff", json=x), 404)
        r = s.post(f"/api/exams/{x['id']}/fill"); x = r.get_json()
        wrote(r, "fill", "Mid-year exam: papers added from the subjects")
        times = {"English": "07:50", "Pure Chemistry": "10:00"}
        x["papers"] = [dict(p, date="2026-10-05", start=times[p["subject"]]) for p in x["papers"] if p["subject"] in times]
        wrote(s.put("/api/exams/" + x["id"], json=x), "edit", "Mid-year exam: changed")
        r = s.get(f"/api/exams/{x['id']}/papers.xlsx"); none(r, 200)
        wrote(s.post(f"/api/exams/{x['id']}/papers.xlsx", data=dict(file=(io.BytesIO(r.data), "p.xlsx"))), "papers", "Mid-year exam: paper list uploaded")
        none(s.post(f"/api/exams/{x['id']}/papers.xlsx", data=dict(file=(io.BytesIO(b"junk"), "p.xlsx"))), 400)
        wrote(s.post(f"/api/exams/{x['id']}/make", json={}), "make", "Mid-year exam: seats and duties made")
        none(s.post(f"/api/exams/{x['id']}/make", json=dict(only=5)), 400)
        key = "2026-10-05 07:50"
        wrote(s.post(f"/api/exams/{x['id']}/move", json=dict(key=key, students=["3A-07"], room="3-02")), "move", "Mid-year exam: students moved")
        none(s.post(f"/api/exams/{x['id']}/move", json=dict(key="bad", students=["3A-07"], room="3-02")), 400)
        wrote(s.post(f"/api/exams/{x['id']}/invigilators", json=dict(key=key, room="3-01", names=["Mr Ivan Lee"])), "invigilators", "Mid-year exam: invigilators changed")
        none(s.post(f"/api/exams/{x['id']}/invigilators", json=dict(key=key, room="3-01", names="x")), 400)
        wrote(s.post(f"/api/exams/{x['id']}/use-anyway", json=dict(key=key, room="Hall")), "use-anyway", "Mid-year exam: Hall used anyway")
        long = "Room " + "x" * 300                                       # the page's room text is cut to 60 characters for the history
        e = wrote(s.post(f"/api/exams/{x['id']}/use-anyway", json=dict(key=key, room=long)), "use-anyway", f"Mid-year exam: {long[:59]}… used anyway")
        assert len(e["text"]) == len("Mid-year exam: ") + 60 + len(" used anyway"), e["text"]
        for url in ("", "/view", "/print/seating.pdf", "/download.xlsx", f"/who?key={key}&room=3-01"): none(s.get(f"/api/exams/{x['id']}{url}"), 200)
        none(s.get("/api/exams"), 200)
        wrote(s.delete("/api/exams/" + x["id"]), "delete", "Mid-year exam: deleted")
        none(s.delete("/api/exams/" + x["id"]), 404)                       # nothing there: nothing deleted, no entry (404 since stage 4)
        r = committee().put("/api/exams/settings", json=st); assert r.status_code == 200
        e = H.read(kinds=["exams"], limit=1)[0]; assert (e["who"], e["as"], e["via"], e["text"]) == (None, "Shared committee code", "shared", "Exam settings saved"), e
    exams_until("Ms Grace Yeo", None); _reset()

def _page(name):
    with open(os.path.join(ROOT, "static", name), encoding="utf-8") as f:
        return f.read()

@t
def the_pages_carry_the_words():
    xs = _page("exams-settings.js")
    assert "Change these on the admin page." in xs and "Ask an admin to change these." in xs and 'href="/admin"' in xs
    assert "Only the timetable committee can change this list." not in xs and "committee_ok" not in xs
    js = _page("exams.js")
    for words in ("How to seat", "Own class in own home room", "Mix classes", "Alternate levels by column", "Alternate papers",
                  "One level per block", "Class, then Student ID", "Every seat", "A seat left between", "Let the app choose",
                  "Not free: ", "The exam changed since Make: press Make again.",
                  "The published timetable has no students yet: add them on the Students step and publish again to check clashes and seat students.",
                  "lessons outside "):
        assert words in js, words

NOW = "2026-10-01T09:00:00"

def _approved(access=None, rooms=None):
    return F.approved_exam(_PUB, access=access, **({} if rooms is None else dict(rooms=rooms)))

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
    """the exam rooms saved, and the exams committee as the accounts hold it: the Exams and events extra (until LATER) for
    each name, taken off everyone else"""
    x = _xset(("3-01", "3-02", "4-01", "Hall"))
    os.makedirs(os.path.dirname(ES.PATH), exist_ok=True)
    store.write_json(ES.PATH, dict(rooms=x["rooms"]))
    ACC.update(lambda d: [r.setdefault("extras", {}).update(exams=None) for r in d["people"].values()])
    for n in names: exams_until(n, LATER)

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
def approve_by_the_committee_right_only():
    """a committee member signed in with their password approves; signed in by code, even with the Exams and events extra,
    they use exams but do not approve"""
    from werkzeug.security import generate_password_hash
    _setup()
    pw, code = "Ms Cora Lim", "Mr Leo Tan"
    ACC.update(lambda d: (d["people"].setdefault(pw, {}).update(group="committee", added=True, username="cora.lim",
                                                                pw=generate_password_hash(secrets.token_hex(8))),
                          d["people"].setdefault(code, {}).update(group="committee", added=True, extras=dict(relief=False, exams=LATER, admin=False))))
    try:
        with published(_PUB):
            p, k = staff(pw, via="password"), staff(code)
            s = _made_exam(committee()); id = s["id"]
            assert k.post(f"/api/exams/{id}/send").status_code == 200, "the extra uses exams"
            assert k.get("/api/exams/me").get_json()["can_approve"] is False and p.get("/api/exams/me").get_json()["can_approve"] is True
            for step, body in (("approve", None), ("send-back", dict(note="x")), ("withdraw", None)):
                r = k.post(f"/api/exams/{id}/{step}", json=body); assert r.status_code == 403 and r.get_json() == {"error": A.ONLY_APPROVE}, (step, r.data)
            assert SC.load(id)["status"] == "waiting"
            r = p.post(f"/api/exams/{id}/approve"); assert r.status_code == 200 and r.get_json()["status"] == "approved", r.data
            assert SC.load(id)["approved_by"] == pw and H.read(kinds=["exams"], limit=1)[0]["who"] == pw
    finally:
        ACC.update(lambda d: [d["people"].pop(n, None) for n in (pw, code)])
        _reset()

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
        e = H.read(kinds=["exams"], limit=1)[0]
        assert e["what"] == "send" and e["text"].startswith("Sec 3 Exam: changes sent to the timetable committee (") and re.search(r"\(\d+ changes?\)$", e["text"]), e
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
def each_approval_step_writes_one_history_entry():
    """send, approve, send back, withdraw and someone away: one exams entry each, named by who did it; a refusal writes none"""
    _setup()
    with published(_PUB):
        c, g = committee(), staff("Ms Grace Yeo")
        s = _made_exam(g); id = s["id"]
        n = [len(H.read(kinds=["exams"], limit=10000))]
        def wrote(r, what, text, who_):
            assert r.status_code == 200, (what, r.status_code, r.data[:200])
            got = H.read(kinds=["exams"], limit=10000); assert len(got) == n[0] + 1, (what, n[0], len(got)); n[0] += 1
            e = got[0]
            assert (e["what"], e["text"], e["where"], e["link"], e["exam"]) == (what, text, "Exams and events", "/exams", id), e
            assert e["as"] == who_, e
        def none(r, code):
            assert r.status_code == code, (r.status_code, r.data[:200])
            assert len(H.read(kinds=["exams"], limit=10000)) == n[0], "no entry"
        none(g.post(f"/api/exams/{id}/approve"), 403)                   # the exams committee does not approve
        wrote(g.post(f"/api/exams/{id}/send"), "send", "Sec 3 Exam: sent to the timetable committee", "Ms Grace Yeo")
        none(c.post(f"/api/exams/{id}/send-back", json=dict(note="")), 400)
        wrote(c.post(f"/api/exams/{id}/send-back", json=dict(note="Not that day")), "send-back", "Sec 3 Exam: sent back to the exams committee", "Shared committee code")
        assert "Not that day" not in H.read(kinds=["exams"], limit=1)[0]["text"], "the note stays in the schedule's own log"
        wrote(g.post(f"/api/exams/{id}/send"), "send", "Sec 3 Exam: sent to the timetable committee", "Ms Grace Yeo")
        wrote(c.post(f"/api/exams/{id}/approve"), "approve", "Sec 3 Exam: approved: on the main site", "Shared committee code")
        body = dict(key=KEY1, room="3-01", away="Ms Chloe Tan", name="Mr Hafiz Rahman")
        wrote(g.post(f"/api/exams/{id}/away", json=body), "away",
              "Sec 3 Exam: someone away replaced at once (Mon 5 Oct 07:35–09:00, 3-01: Ms Chloe Tan (away) → Mr Hafiz Rahman)", "Ms Grace Yeo")
        wrote(c.post(f"/api/exams/{id}/withdraw"), "withdraw", "Sec 3 Exam: withdrawn from the main site", "Shared committee code")
        none(c.post(f"/api/exams/{id}/withdraw"), 400)
        assert [e["what"] for e in SC.load(id)["log"]] == ["sent", "sent back", "sent", "approved", "replaced", "withdrawn"], SC.load(id)["log"]

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
            for code in ("head", "teacher", "student"):                  # shared codes are nobody's: no exams page, no duties
                k = as_role(code)
                r = k.get("/exams"); assert r.status_code == 302 and r.headers["Location"] in ("/", "http://localhost/"), (code, r.status_code, r.headers.get("Location"))
                r = k.get("/api/exams/me"); assert r.status_code == 403 and r.get_json() == {"error": A.ONLY_EXAMS}, (code, r.data)
                r = k.get("/api/exams/my-duties"); assert r.status_code == 403 and r.get_json() == {"error": A.ONLY_OWN_DUTIES}, (code, r.data)
                assert k.get("/api/exams").status_code == 401 and k.get("/exams/settings").status_code == 302, code
            r = staff("Ms Aisha Rahman").get("/api/exams/my-duties"); assert r.status_code == 200, r.data   # her own code, no Exams extra
            assert any(d["room"] == "3-01" for x in r.get_json()["schedules"] for d in x["duties"]), r.get_json()
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
            tc, _ = signed_in(os.environ["TEACHER_CODE"])
            assert tc.get("/timetable").status_code == 200
            assert seen[0]["dates"] is True and seen[0]["exams"] is True and "exams" in seen[0]["tabs"], seen[0]
            sc, _ = signed_in(os.environ["STUDENT_CODE"])
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
                  "Replace now", "My exam and event duties", "You have no exam or event duties on the main site.", "Scripts go to",
                  "On the main site. Changes you make here wait for the timetable committee: send them from the Approval tab.",
                  "Changes not sent yet", "Nothing on the main site has changed since it was approved.", "What changes on the main site",
                  "Lessons that won't happen: ", "Rain rooms used anyway: ", "Take ${S.sched.name} off the main site now?", "/api/exams/my-duties",
                  "&copy=approved", "Lessons that don't happen: "):
        assert words in js, words
    assert "g.includes(` is on ${m[1]} then`)" not in js and "f.includes(` is on ${m[1]} then`)" in js, "a takes line goes only when a free line names that schedule, with or without a room"
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
    helpers = ("_exams_rights", "_exams_can_approve", "_published_reader", "_exams_student", "_event_rights")
    for name, body in re.findall(r"\ndef (\w+)\(.*?\):(.*?)(?=\n(?:def |@app|# -{20}))", part, re.S):
        if name not in helpers:
            assert "role()" not in body and 'session.get("sid")' not in body and "session[" not in body and "shared()" not in body, name
    assert not hasattr(A, "_exams_can_keep_list"), "the exams committee list is the accounts' (the admin page)"
    with published(_PUB):
        _setup()
        c, g = committee(), staff("Ms Grace Yeo", until=LATER)
        try: assert c.get("/api/exams/me").get_json()["can_approve"] is True and g.get("/api/exams/me").get_json()["can_approve"] is False
        finally: exams_until("Ms Grace Yeo", None)

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
            tc, _ = signed_in(os.environ["TEACHER_CODE"])
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
    _ev_bad(SC.EVENT_WRONG, going_by="friends")
    _ev_bad(SC.EVENT_WRONG, duties=[dict(duty="x", who=5, time="")])
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
    except ValueError as x: assert str(x) == SC.EVENT_WRONG
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
                                                               dict(name="Ms Chloe Tan", reason="freed: lessons with 3B stop")], free=[], period=[])

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
    assert w["going"] == ["Ms Aisha Rahman", "Ms Grace Yeo", "Mr Ben Ong"] and w["approved"]["duties"][0]["who"] == "Mr Ben Ong"
    sent = _ev_ok()
    assert sent["sent_fp"] == AP.fp(sent)
    AP.replace_going(sent, "Mr Hafiz Rahman", "Mr Ben Ong", "Ms Aisha Rahman", NOW)
    assert sent["sent_fp"] == AP.fp(sent) and "Mr Ben Ong" in sent["going"], "a replacement keeps a sent copy unchanged"
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
        r = a.get("/api/exams"); assert r.status_code == 401 and r.get_json() == AGAIN, r.data   # accounts: the guard refuses (no exams right)
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
    import re
    src = open(os.path.join(ROOT, "app.py"), encoding="utf-8").read()
    assert "def _event_rights(" in src and "def _event_gate(" in src
    body = re.search(r"\ndef _event_rights\(.*?\):(.*?)\n(?:def |@app)", src, re.S).group(1)
    assert 'has("committee")' in body and "who()" in body, "the accounts' rights decide"
    assert "role()" not in body and "session" not in body and "shared()" not in body and 'has("exams")' not in body, "no role names; the exams extra gives nothing here"

@t
def event_rights_by_the_accounts():
    """the teacher in charge (anyone signed in by name, any way in) and the timetable committee (the committee right) open
    and change an event; the shared heads', teacher and student codes, a personal student code and the exams committee do not"""
    from werkzeug.security import generate_password_hash
    _setup()
    pw, code, lead = "Ms Cora Lim", "Mr Leo Tan", "Mr Max Ho"
    hashed = lambda: generate_password_hash(secrets.token_hex(8))
    ACC.update(lambda d: (d["people"].setdefault(pw, {}).update(group="committee", added=True, username="cora.lim", pw=hashed()),
                          d["people"].setdefault(code, {}).update(group="committee", added=True),
                          d["people"].setdefault(lead, {}).update(group="leader", added=True, username="max.ho", pw=hashed())))
    try:
        with published(_PUB):
            a, g = staff("Ms Aisha Rahman"), staff("Ms Grace Yeo")     # Ms Grace Yeo holds the Exams and events extra (_setup)
            cp, ck, lp = staff(pw, via="password"), staff(code), staff(lead, via="password")
            e = _event(a); id = e["id"]
            for kind in ("head", "teacher", "student"):               # the shared codes are nobody's: no event is theirs
                k = as_role(kind)
                for r in (k.get("/api/events"), k.post("/api/events", json=dict(name="X")), k.get(f"/api/events/{id}"), k.get("/api/events/ffff"),
                          k.post(f"/api/events/{id}/send"), k.get(f"/api/events/{id}/who")):
                    assert r.status_code == 403 and r.get_json() == {"error": A.ONLY_OWN_EVENTS}, (kind, r.status_code, r.data)
                r = k.get(f"/events/{id}"); assert r.status_code == 302 and r.headers["Location"].endswith("/") and not r.headers["Location"].endswith("/login"), (kind, r.headers)
            st = as_role("personal", sid="3A-07")
            assert st.get("/api/events").status_code == 401 and st.get("/api/events").get_json() == AGAIN
            r = st.get(f"/events/{id}"); assert r.status_code == 302 and r.headers["Location"].endswith("/login"), r.headers
            no = {"error": A.ONLY_IN_CHARGE}
            for who_, k in (("the exams committee", g), ("a committee member by code", ck), ("a leader by password", lp)):
                for r in (k.get(f"/api/events/{id}"), k.put(f"/api/events/{id}", json=e), k.post(f"/api/events/{id}/fill", json=dict(way="form teachers"))):
                    assert r.status_code == 403 and r.get_json() == no, (who_, r.status_code, r.data)
                d = k.get("/api/events").get_json()
                assert d["schedules"] == [] and d["people"] == [], (who_, d)
                assert k.get(f"/events/{id}").status_code == 200, "the page opens; the event then says it is not theirs"
            r = lp.post("/api/events", json=dict(name="Sec 3 Sports", levels=["Sec 3"], classes=[], start="2026-10-05", end="2026-10-05", in_charge="Mr Ben Ong"))
            assert r.status_code == 200 and r.get_json()["in_charge"] == lead and r.get_json()["created_by"] == lead, r.data
            assert [x["in_charge"] for x in lp.get("/api/events").get_json()["schedules"]] == [lead]
            r = ck.post("/api/events", json=dict(name="Sec 3 Camp", levels=["Sec 3"], classes=[], start="2026-10-05", end="2026-10-05"))
            assert r.status_code == 200 and r.get_json()["in_charge"] == code, "by code a committee member is a teacher in charge, not the committee"
            r = g.post("/api/events", json=dict(name="Sec 3 Walk", levels=["Sec 3"], classes=[], start="2026-10-05", end="2026-10-05"))
            assert r.status_code == 200 and r.get_json()["in_charge"] == "Ms Grace Yeo", "the exams committee may start its own, as anyone"
            d = cp.get("/api/events").get_json()                       # the committee by password: every event, and names the teacher in charge
            assert len(d["schedules"]) == 4 and "Mr Ben Ong" in d["people"], d
            assert cp.get(f"/api/events/{id}").status_code == 200
            got = cp.get(f"/api/events/{id}").get_json(); got["where"] = "Science Centre"
            r = cp.put(f"/api/events/{id}", json=got); assert r.status_code == 200 and r.get_json()["saved_by"] == pw, r.data
            assert H.read(kinds=["exams"], limit=1)[0]["who"] == pw
            body = dict(name="Sec 3 Talk", levels=["Sec 3"], classes=[], start="2026-10-05", end="2026-10-05")
            r = cp.post("/api/events", json=body); assert r.status_code == 400 and r.get_json() == {"error": A.PICK_IN_CHARGE}, r.data
            r = cp.post("/api/events", json=dict(body, in_charge="Mr Ben Ong")); assert r.status_code == 200 and r.get_json()["in_charge"] == "Mr Ben Ong", r.data
            assert a.post(f"/api/events/{id}/fill", json=dict(way="form teachers")).status_code == 200
            assert a.post(f"/api/events/{id}/send").status_code == 200
            for k in (a, ck, g):
                r = k.post(f"/api/events/{id}/approve"); assert r.status_code == 403, r.data
            r = cp.post(f"/api/events/{id}/approve"); assert r.status_code == 200 and r.get_json()["status"] == "approved", r.data
            assert SC.load(id)["approved_by"] == pw
    finally:
        ACC.update(lambda d: [d["people"].pop(n, None) for n in (pw, code, lead)])
        _reset()

@t
def each_event_save_and_step_writes_one_history_entry():
    """as exams: create, edit, fill, send, approve, send back, withdraw, someone away and delete write one entry each,
    named by who did it and linked to the event; a refusal, or a fill that adds no one, writes none"""
    _setup()
    with published(_PUB):
        a, b, c = staff("Ms Aisha Rahman"), staff("Mr Ben Ong"), committee()
        n = [len(H.read(kinds=["exams"], limit=10000))]
        name = "Sec 3 Learning Journey"
        def wrote(r, what, text, who_, link=None):
            assert r.status_code == 200, (what, r.status_code, r.data[:200])
            got = H.read(kinds=["exams"], limit=10000); assert len(got) == n[0] + 1, (what, n[0], len(got)); n[0] += 1
            e = got[0]
            assert (e["what"], e["text"], e["where"], e["link"], e["exam"]) == (what, f"{name}: {text}", "Exams and events", link or f"/events/{id}", id), e
            assert e["as"] == who_, e
            return e
        def none(r, code):
            assert r.status_code == code, (r.status_code, r.data[:200])
            assert len(H.read(kinds=["exams"], limit=10000)) == n[0], "no entry"
        r = a.post("/api/events", json=dict(name=name, levels=["Sec 3"], classes=[], start="2026-10-05", end="2026-10-05"))
        id = r.get_json()["id"]
        e = wrote(r, "create", "created", "Ms Aisha Rahman"); assert e["via"] == "code" and e["who"] == "Ms Aisha Rahman", e
        x = a.get(f"/api/events/{id}").get_json(); none(a.get(f"/api/events/{id}"), 200)
        x["days"] = {"2026-10-05": dict(levels=["Sec 3"], whole=False, **{"from": "07:40", "to": "10:40"})}; x["where"] = "Off site (museum)"
        wrote(a.put(f"/api/events/{id}", json=x), "edit", "changed", "Ms Aisha Rahman")
        none(b.put(f"/api/events/{id}", json=x), 403)
        none(a.put(f"/api/events/{id}", json=dict(x, going="x")), 400)
        wrote(a.post(f"/api/events/{id}/fill", json=dict(way="form teachers")), "fill", "2 added to the people going (the form teachers)", "Ms Aisha Rahman")
        none(a.post(f"/api/events/{id}/fill", json=dict(way="form teachers")), 200)          # no one new: nothing saved
        wrote(a.post(f"/api/events/{id}/fill", json=dict(way="department", dept="PE")), "fill", "1 added to the people going (a department)", "Ms Aisha Rahman")
        for url in ("/view", "/review", "/who"): a.get(f"/api/events/{id}{url}")
        none(a.get("/api/events"), 200)
        none(a.post(f"/api/events/{id}/approve"), 403)                  # the teacher in charge does not approve
        wrote(a.post(f"/api/events/{id}/send"), "send", "sent to the timetable committee", "Ms Aisha Rahman")
        none(c.post(f"/api/events/{id}/send-back", json=dict(note="")), 400)
        wrote(c.post(f"/api/events/{id}/send-back", json=dict(note="Not that day")), "send-back", "sent back to the teacher in charge", "Shared committee code")
        assert "Not that day" not in H.read(kinds=["exams"], limit=1)[0]["text"], "the note stays in the event's own log"
        wrote(a.post(f"/api/events/{id}/send"), "send", "sent to the timetable committee", "Ms Aisha Rahman")
        wrote(c.post(f"/api/events/{id}/approve"), "approve", "approved: on the main site", "Shared committee code")
        none(a.post(f"/api/events/{id}/away", json=dict(away="Mr Hafiz Rahman", name="Mr Daniel Koh")), 400)
        wrote(a.post(f"/api/events/{id}/away", json=dict(away="Mr Hafiz Rahman", name="Mr Ben Ong")), "away",
              "someone away replaced at once (Mon 5 Oct, going: Mr Hafiz Rahman (away) \u2192 Mr Ben Ong)", "Ms Aisha Rahman")
        none(a.post(f"/api/events/{id}/in-charge", json=dict(name="Mr Ben Ong")), 403)
        none(c.post(f"/api/events/{id}/in-charge", json=dict(name="Ms Aisha Rahman")), 400)
        wrote(c.post(f"/api/events/{id}/in-charge", json=dict(name="Mr Ben Ong")), "in-charge", "teacher in charge changed (Ms Aisha Rahman \u2192 Mr Ben Ong)", "Shared committee code")
        wrote(c.post(f"/api/events/{id}/in-charge", json=dict(name="Ms Aisha Rahman")), "in-charge", "teacher in charge changed (Mr Ben Ong \u2192 Ms Aisha Rahman)", "Shared committee code")
        none(a.delete(f"/api/events/{id}"), 409)
        wrote(c.post(f"/api/events/{id}/withdraw"), "withdraw", "withdrawn from the main site", "Shared committee code")
        none(c.post(f"/api/events/{id}/withdraw"), 400)
        wrote(a.delete(f"/api/events/{id}"), "delete", "deleted", "Ms Aisha Rahman", link="/exams")
        none(a.delete(f"/api/events/{id}"), 404)
        assert H.read(kinds=["exams"], limit=1)[0]["link"] == "/exams", "a deleted event's entry links to the list"
    _reset()


# ---- the teacher in charge, changed by the timetable committee
BY_NAME = "Only the timetable committee can change the teacher in charge."

@t
def in_charge_goes_to_both_copies_and_stays_as_sent():
    e = dict(id="e", kind="event", name="E", status="waiting", in_charge="Ms A", going=["Ms A"], duties=[dict(duty="Bus", who="Ms A", time="")], approved=None, log=[])
    AP.send(dict(e), _PUB["model"], "Ms A", "t0", False, [])
    AP.send(e, _PUB["model"], "Ms A", "t0", False, [])
    assert AP.set_in_charge(e, "Mr B", "Timetable committee", "t1") == "Ms A \u2192 Mr B"
    assert e["in_charge"] == "Mr B" and e["going"] == ["Ms A"] and e["duties"][0]["who"] == "Ms A", "being in charge is not going"
    assert e["log"][-1] == dict(at="t1", by="Timetable committee", what="in charge", detail="Ms A \u2192 Mr B")
    AP.approve(e, "Timetable committee", "t2")          # the sent copy is still the one the committee reads
    assert e["approved"]["in_charge"] == "Mr B" and AP.changes(e, _PUB["model"]) == []
    AP.set_in_charge(e, "Ms C", "x", "t3")
    assert e["in_charge"] == e["approved"]["in_charge"] == "Ms C" and AP.changes(e, _PUB["model"]) == [] and e["status"] == "approved"
    assert AP.fp(e) == e["sent_fp"], "nothing is waiting: the fingerprint moved with it"
    raises(ValueError, lambda: AP.set_in_charge(e, "Ms C", "x", "t4"), "Ms C is in charge already.")
    assert len([x for x in e["log"] if x["what"] == "in charge"]) == 2
    e["where"] = "Elsewhere"                            # an edit not sent yet is still not sent
    AP.set_in_charge(e, "Mr B", "x", "t5")
    assert AP.fp(e) != e["sent_fp"] and [c["kind"] for c in AP.changes(e, _PUB["model"])] == ["where"]
    n = dict(id="n", kind="event", name="N", status="draft", going=[], approved=None)
    assert AP.set_in_charge(n, "Mr B", "x", "t") == "nobody \u2192 Mr B" and n["in_charge"] == "Mr B" and "sent_fp" not in n

@t
def the_committee_changes_an_events_teacher_in_charge():
    _setup()
    with published(_PUB):
        a, b, c, g = staff("Ms Aisha Rahman"), staff("Mr Ben Ong"), committee(), staff("Ms Grace Yeo")
        e = _event(a); id = e["id"]; url = f"/api/events/{id}/in-charge"
        for k, want in ((a, BY_NAME), (b, A.ONLY_IN_CHARGE), (g, A.ONLY_IN_CHARGE)):      # the teacher in charge may open it, and still may not
            r = k.post(url, json=dict(name="Mr Ben Ong")); assert r.status_code == 403 and r.get_json() == {"error": want}, r.data
        for kind in ("head", "teacher", "student"):
            r = as_role(kind).post(url, json=dict(name="Mr Ben Ong")); assert r.status_code == 403 and r.get_json() == {"error": A.ONLY_OWN_EVENTS}, r.data
        for bad, want in ((dict(), A.PICK_IN_CHARGE), (dict(name=""), A.PICK_IN_CHARGE), (dict(name="  "), A.PICK_IN_CHARGE), (dict(name=["x"]), A.PICK_IN_CHARGE),
                          (dict(name=None), A.PICK_IN_CHARGE), (dict(name="Mr Nobody"), "Mr Nobody is not on the published timetable or the staff list."),
                          (dict(name="Ms Aisha Rahman"), "Ms Aisha Rahman is in charge already.")):
            r = c.post(url, json=bad); assert r.status_code == 400 and r.get_json() == {"error": want}, (bad, r.data)
        r = c.post(url, data="[1]", content_type="application/json"); assert r.status_code == 400 and r.get_json() == {"error": A.PICK_IN_CHARGE}, r.data
        assert c.post("/api/events/ffff/in-charge", json=dict(name="Mr Ben Ong")).status_code == 404
        assert SC.load(id)["in_charge"] == "Ms Aisha Rahman" and [x["what"] for x in SC.load(id).get("log") or []] == []
        r = c.post(url, json=dict(name="Mr Ben Ong")); assert r.status_code == 200 and r.get_json()["status"] == "draft", r.data
        s = SC.load(id)
        assert s["in_charge"] == "Mr Ben Ong" and s["created_by"] == "Ms Aisha Rahman" and s["saved_by"] == "Timetable committee", s
        # the event goes with it
        assert b.get(f"/api/events/{id}").status_code == 200 and [x["id"] for x in b.get("/api/events").get_json()["schedules"]] == [id]
        assert a.get(f"/api/events/{id}").status_code == 403 and a.get("/api/events").get_json()["schedules"] == []
        r = a.put(f"/api/events/{id}", json=dict(e, in_charge="Ms Aisha Rahman")); assert r.status_code == 403 and r.get_json() == {"error": A.ONLY_IN_CHARGE}
        r = b.put(f"/api/events/{id}", json=dict(e, in_charge="Ms Aisha Rahman")); assert r.status_code == 200 and r.get_json()["in_charge"] == "Mr Ben Ong", "a page opened before takes nothing back"
        # waiting: still approved as it was sent; approved: on the main site at once
        r = b.post(f"/api/events/{id}/fill", json=dict(way="form teachers")); assert r.status_code == 200, r.data
        assert b.post(f"/api/events/{id}/send").status_code == 200
        r = c.post(url, json=dict(name="Mr Daniel Koh")); assert r.status_code == 200 and r.get_json()["status"] == "waiting" and r.get_json()["changed"] is False, r.data
        r = c.post(f"/api/events/{id}/approve"); assert r.status_code == 200, r.data
        assert SC.load(id)["approved"]["in_charge"] == "Mr Daniel Koh"
        r = c.post(url, json=dict(name="Ms Chloe Tan")); j = r.get_json()
        assert r.status_code == 200 and j["status"] == "approved" and j["unsent"] == [] and j["changed"] is False, j
        with _today(date(2026, 9, 28)):
            assert [x["in_charge"] for x in c.get("/api/published/exams").get_json()["schedules"] if x["id"] == id] == ["Ms Chloe Tan"], "the main site too"
        assert c.post(f"/api/events/{id}/withdraw").status_code == 200
        assert c.post(url, json=dict(name="Mr Ben Ong")).status_code == 200 and SC.load(id)["status"] == "withdrawn", "in any state"
        ex = c.post("/api/exams", json=dict(kind="exam", name="Sec 3 Exam", levels=["Sec 3"], start="2026-10-05", end="2026-10-05")).get_json()
        assert c.post(f"/api/events/{ex['id']}/in-charge", json=dict(name="Mr Ben Ong")).status_code == 404, "an exam has no teacher in charge"
    _reset()

@t
def a_committee_member_by_password_changes_it_and_by_code_does_not():
    from werkzeug.security import generate_password_hash
    _setup()
    pw, code = "Ms Cora Lim", "Mr Leo Tan"
    ACC.update(lambda d: (d["people"].setdefault(pw, {}).update(group="committee", added=True, username="cora.lim", pw=generate_password_hash(secrets.token_hex(8))),
                          d["people"].setdefault(code, {}).update(group="committee", added=True)))
    try:
        with published(_PUB):
            a = staff("Ms Aisha Rahman"); id = _event(a)["id"]; url = f"/api/events/{id}/in-charge"
            assert staff(code).post(url, json=dict(name=code)).status_code == 403
            r = staff(pw, via="password").post(url, json=dict(name=code)); assert r.status_code == 200, r.data      # staff added in the accounts may be in charge
            s = SC.load(id); assert s["in_charge"] == code and s["saved_by"] == pw and s["log"][-1]["by"] == pw, s
            r = staff(code).post(url, json=dict(name=pw)); assert r.status_code == 403 and r.get_json() == {"error": BY_NAME}, "in charge, and by code no committee"
    finally:
        ACC.update(lambda d: (d["people"].pop(pw, None), d["people"].pop(code, None)))
        _reset()

@t
def a_new_publish_does_not_stop_the_change():
    _setup()
    with published(_PUB):
        a, c = staff("Ms Aisha Rahman"), committee()
        id = _event(a)["id"]
        s = SC.load(id); s["classes"] = ["9Z"]; s["levels"] = []; SC.save(s, _PUB, F.CAL, "x", check=False)      # a class the timetable no longer has
        r = c.post(f"/api/events/{id}/in-charge", json=dict(name="Mr Ben Ong")); assert r.status_code == 200, r.data
        assert SC.load(id)["in_charge"] == "Mr Ben Ong"
    _reset()

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
def a_plain_teacher_gets_only_their_own_duties():
    own = PB.day(_PUB, F.CAL, [A1], D5, False, only="Mr Ben Ong")["exams"]
    full = PB.day(_PUB, F.CAL, [A1], D5, True)["exams"]
    assert own["teachers"] == {"Mr Ben Ong": full["teachers"]["Mr Ben Ong"]} and own["rooms"] == {}, own
    assert own["teachers"]["Mr Ben Ong"][0]["room"] == "3-01" and own["teachers"]["Mr Ben Ong"][0]["role"] == "Invigilate"
    import copy
    c = copy.deepcopy(A1); d0 = c["made"]["duties"][0]; d0["chief"] = d0["names"][0]; boss = d0["chief"]
    got = PB.day(_PUB, F.CAL, [c], D5, False, only=boss)["exams"]["teachers"][boss]
    assert got[0]["role"] == "Chief invigilator" and got[0]["room"] == d0["room"], got
    none = PB.day(_PUB, F.CAL, [A1], D5, False)["exams"]
    assert none["teachers"] == {} and none["rooms"] == {}
    assert PB.day(_PUB, F.CAL, [A1], D5, True, only="Mr Ben Ong")["exams"] == full
    ev = PB.day(_PUB, F.CAL, [E1], "2026-10-05", False, only="Mr Hafiz Rahman")["exams"]
    assert list(ev["teachers"]) == ["Mr Hafiz Rahman"] and ev["rooms"] == {}, ev
    assert PB.day(_PUB, F.CAL, [A1], D5, False, only="Ms Nobody Here")["exams"]["teachers"] == {}

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

def _rain_pub(rain):
    import copy
    p = copy.deepcopy(_PUB)
    next(l for l in p["model"]["lessons"] if l["subject"] == "PE")["rain"] = rain
    return p

@t
def several_rain_rooms_are_each_taken_or_used():
    P = _rain_pub("Hall, LT2")
    assert EV.flags(P, F.CAL, _ev(venues=["LT2"])) == ["Mon 5 Oct 09:00–09:40: PE with 4A uses LT2 in wet weather then."]
    assert EV.flags(P, F.CAL, _ev(venues=["Hall"])) == ["Mon 5 Oct 09:00–09:40: PE with 4A uses Hall in wet weather then."]
    Q = _rain_pub("3-01, LT2")
    assert EV.freed(Q, F.CAL, _ev())[0]["rooms"] == ["3-02", "Lab 3-08"], EV.freed(Q, F.CAL, _ev())
    assert EV.freed(_PUB, F.CAL, _ev())[0]["rooms"] == ["3-01", "3-02", "Lab 3-08"]

@t
def freed_rooms_leave_out_what_another_schedule_uses_then():
    busy = SC.busies([dict(_ev(name="Sec 3 Talk", going=[], venues=["Lab 3-08"]), id="ev2", status="waiting")], _M)
    assert EV.freed(_PUB, F.CAL, _ev(), busy)[0]["rooms"] == ["3-01", "3-02"], EV.freed(_PUB, F.CAL, _ev(), busy)
    assert EV.freed(_PUB, F.CAL, _ev(), [])[0]["rooms"] == ["3-01", "3-02", "Lab 3-08"]

@t
def a_waiting_event_copy_that_adds_a_class_still_shows():
    a = dict(_ev(levels=["Sec 3"], classes=["3A"]), id="ev6", status="approved")
    w = dict(_ev(levels=["Sec 3"], classes=["3A", "3B"]), id="ev6", status="waiting")
    got = [b for b in SC.busies([a, w], _M) if b["room"] == ""]
    assert [(b["status"], b["classes"]) for b in got] == [("approved", ["3A"]), ("waiting", ["3A", "3B"])], got

@t
def event_text_limits_and_wording():
    _ev_bad("Where can be at most 120 characters.", where="x" * 121)
    _ev_bad("A duty can be at most 120 characters and its time at most 60.", duties=[dict(duty="x", who="", time="t" * 61)])
    SC._check(_ev(where="x" * 120, duties=[dict(duty="d" * 120, who="", time="t" * 60)]), _PUB)
    assert SC.EVENT_WRONG == "Check the event and try again." and SC.WRONG == "Check the exam and try again."

@t
def a_multi_date_event_lists_lessons_in_time_order_and_per_date_busies():
    import copy
    P = copy.deepcopy(_PUB)
    P["model"]["lessons"].insert(0, dict(P["model"]["lessons"][7], id=50, p=6, n=1, subject="Art", room="4-01"))   # Ms Grace Yeo, later than her Literature
    day = dict(levels=None, whole=False, **{"from": "07:40", "to": "10:40"})
    e = _ev(end="2026-10-06", going=["Ms Grace Yeo"], days={"2026-10-05": day, "2026-10-06": dict(day)})
    got = EV.going(P, F.CAL, e, [])[0]["text"]
    assert got == "teaches 4A Literature 08:40–09:00 (Mon 5 Oct); teaches 4A Art 09:40–10:00 (Mon 5 Oct) → backup", got
    busy = SC.event_busy(dict(e, id="evm", status="approved"), _M)
    assert sorted({b["date"] for b in busy}) == ["2026-10-05", "2026-10-06"], busy
    assert [d["date"] for d in EV.on_dates(_PUB, F.CAL, e)] == ["2026-10-05", "2026-10-06"]

@t
def a_fill_that_adds_no_one_leaves_a_sent_event_unchanged():
    _setup()
    with published(_PUB):
        a, c = staff("Ms Aisha Rahman"), committee()
        e = _event(a); id = e["id"]
        assert a.post(f"/api/events/{id}/fill", json=dict(way="form teachers")).status_code == 200
        assert a.post(f"/api/events/{id}/send").status_code == 200
        r = a.post(f"/api/events/{id}/fill", json=dict(way="department", dept="Nobody here")); assert r.status_code == 200, r.data
        assert r.get_json()["going_by"] == "form teachers" and SC.load(id)["going_by"] == "form teachers"
        assert a.get(f"/api/events/{id}/review").get_json()["changed"] is False
        assert c.post(f"/api/events/{id}/approve").status_code == 200, "Approve is not refused after an empty fill"

@t
def a_committee_put_cannot_change_in_charge():
    _setup()
    with published(_PUB):
        a, c = staff("Ms Aisha Rahman"), committee()
        e = _event(a); id = e["id"]
        for who_, cl in (("committee", c), ("teacher", a)):
            e2 = dict(e, in_charge="Mr Ben Ong", status="approved")
            assert cl.put("/api/events/" + id, json=e2).status_code in (200, 403)
            assert SC.load(id)["in_charge"] == "Ms Aisha Rahman" and SC.load(id)["status"] == "draft", who_

@t
def the_exams_pages_carry_the_event_words():
    js = _page("exams.js")
    for words in ("Exams, tests and events", "+ New event", "New event", "Teacher in charge", "Venues in school",
                  "Venues ticked here are taken: exams and other events cannot use them then.", "Who goes", "Form teachers of ",
                  "Teachers who'd teach them then", "A department", "Pick people", " off the list", "+ Add a duty", "Clashes",
                  "Lessons that use a venue taken", "Venues freed: ", "My exam and event duties", "You have no exam or event duties on the main site.",
                  "You are not in charge of an event yet.", "People going: ", " goes in their place on the main site now. The timetable committee sees it under Done without approval.",
                  "/api/events"):
        assert words in js, words
    assert "/api/events" in _page("app.js"), "the committee page counts the events waiting too"
    assert "ev-kind" in _page("exams.html"), "the Event chip has a colour"

# ---- the school's date and time: the live server runs on UTC, 8 hours behind the school
import contextlib, datetime as DT  # noqa: E402
from zoneinfo import ZoneInfo  # noqa: E402
from relief import lessons as RLS  # noqa: E402

@contextlib.contextmanager
def school_tz(name):
    old = os.environ.get("SCHOOL_TZ"); os.environ["SCHOOL_TZ"] = name
    try: yield
    finally:
        if old is None: os.environ.pop("SCHOOL_TZ")
        else: os.environ["SCHOOL_TZ"] = old

@t
def today_is_the_schools_date_as_relief_has_it():
    old = RLS.today; RLS.today = lambda: date(2031, 3, 4)
    try: assert A._exams_today() == date(2031, 3, 4)
    finally: RLS.today = old
    for tz in ("Pacific/Kiritimati", "Pacific/Pago_Pago"):      # 25 hours apart, so never one date: the server's own zone gives one at most
        with school_tz(tz): assert A._exams_today() == RLS.today() == DT.datetime.now(ZoneInfo(tz)).date(), tz

@t
def stamps_are_in_school_time_and_keep_their_shape():
    for tz in ("Pacific/Kiritimati", "Pacific/Pago_Pago"):
        with school_tz(tz):
            want = DT.datetime.now(ZoneInfo(tz)).replace(tzinfo=None)
            for now in (SC._now(), MK._now()):
                assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d", now), now     # no offset: as every stamp saved before
                assert abs((DT.datetime.fromisoformat(now) - want).total_seconds()) < 60, (tz, now, want)
    with school_tz("Pacific/Kiritimati"):
        assert SC.new("test", "T", ["Sec 3"], "2026-10-05", "2026-10-05", "Ms Grace Yeo", pub=F.sample_pub())["created_at"][:10] == RLS.today().isoformat()

# ------------------------------------------------------------------------------------------------ the save check
_OLD = {"X-Old-Page": "1"}

def _a_draft(c):
    r = c.post("/api/exams", json=dict(kind="exam", name="Sec 3 Exam", levels=["Sec 3"], start="2026-10-05", end="2026-10-06"))
    assert r.status_code == 200, r.data
    return r.get_json()

@t
def a_save_raises_the_revision():
    _reset(); _cal(); _rooms_saved()
    pub = F.sample_pub()
    s = SC.new("exam", "Sec 3 Exam", ["Sec 3"], "2026-10-05", "2026-10-06", "Ms A", pub=pub)
    assert SC.rev_of(s) == 0
    s = SC.save(s, pub, F.CAL, "Ms A"); assert s["rev"] == 1
    assert SC.save(s, pub, F.CAL, "Ms A")["rev"] == 2 and SC.load(s["id"])["rev"] == 2
    with published(_PUB):
        c = committee()
        x = _a_draft(c); assert x["rev"] == 1
        assert c.put("/api/exams/" + x["id"], json=x, headers=_OLD).get_json()["rev"] == 2
        assert c.get("/api/exams/" + x["id"]).get_json()["rev"] == 2

@t
def an_older_page_is_refused():
    _reset(); _cal(); _rooms_saved()
    with published(_PUB):
        c = committee()
        x = _a_draft(c); id = x["id"]
        old = c.get("/api/exams/" + id).get_json()
        assert c.put("/api/exams/" + id, json=dict(old, name="Second"), headers=_OLD).status_code == 200
        before = SC.load(id)
        r = c.put("/api/exams/" + id, json=dict(old, name="Third"), headers=_OLD)
        who = before["saved_by"]
        assert r.status_code == 409 and r.get_json() == {"error": f"This exam was changed by {who} since you opened it. Reload to carry on."}, r.data
        assert SC.load(id) == before, "nothing saved"
        for bad in ("2", True, 1.0, [2]):
            assert c.put("/api/exams/" + id, json=dict(old, rev=bad), headers=_OLD).status_code == 409, bad
        assert c.put("/api/exams/" + id, json={k: v for k, v in old.items() if k != "rev"}, headers=_OLD).status_code == 409
        cur = c.get("/api/exams/" + id).get_json()
        assert cur["rev"] == 2 and c.put("/api/exams/" + id, json=dict(cur, name="X"), headers=_OLD).status_code == 200
        assert SC.load(id)["name"] == "X" and SC.load(id)["rev"] == 3
        raw = dict(SC.load(id)); raw["saved_by"] = None; store.write_json(SC._path(id), raw)
        r = c.put("/api/exams/" + id, json=dict(old, name="Y"), headers=_OLD)
        assert r.status_code == 409 and r.get_json()["error"] == "This exam was changed by someone since you opened it. Reload to carry on."

@t
def a_schedule_from_before_has_no_rev():
    _reset(); _cal(); _rooms_saved()
    with published(_PUB):
        c = committee()
        x = _a_draft(c); id = x["id"]
        raw = {k: v for k, v in SC.load(id).items() if k != "rev"}; store.write_json(SC._path(id), raw)
        assert "rev" not in c.get("/api/exams/" + id).get_json()
        body = {k: v for k, v in c.get("/api/exams/" + id).get_json().items() if k != "rev"}
        assert c.put("/api/exams/" + id, json=body, headers=_OLD).status_code == 200 and SC.load(id)["rev"] == 1
        assert c.put("/api/exams/" + id, json=body, headers=_OLD).status_code == 409
        raw = {k: v for k, v in SC.load(id).items() if k != "rev"}; store.write_json(SC._path(id), raw)
        assert c.put("/api/exams/" + id, json=dict(body, rev=0), headers=_OLD).status_code == 200, "0 is what none is"

@t
def make_and_approve_raise_it_and_tell_it():
    _reset(); _cal(); _rooms_saved()
    with published(_PUB):
        c = committee()
        s = _exam(c); id = s["id"]
        times = {"English": "07:50", "Pure Chemistry": "10:00"}
        s = c.get("/api/exams/" + id).get_json()
        s["papers"] = [dict(p, date="2026-10-05", start=times[p["subject"]]) for p in s["papers"] if p["subject"] in times]
        assert c.put("/api/exams/" + id, json=s, headers=_OLD).status_code == 200
        def follow(r, where=lambda j: j):
            assert r.status_code == 200, r.data
            j = r.get_json(); assert where(j)["rev"] == SC.load(id)["rev"], "the answer tells the revision it saved"
            assert c.put("/api/exams/" + id, json=dict(c.get("/api/exams/" + id).get_json(), rev=where(j)["rev"]), headers=_OLD).status_code == 200
            return j
        before = SC.load(id)["rev"]
        r = c.post(f"/api/exams/{id}/make", json={}); v = follow(r); assert v["rev"] == before + 1
        assert c.get(f"/api/exams/{id}/view").get_json()["rev"] == SC.load(id)["rev"]
        key = "2026-10-05 07:50"
        follow(c.post(f"/api/exams/{id}/move", json=dict(key=key, students=["3A-07"], room="3-02")))
        follow(c.post(f"/api/exams/{id}/send"))
        follow(c.post(f"/api/exams/{id}/approve"))
        assert c.get(f"/api/exams/{id}/review").get_json()["rev"] == SC.load(id)["rev"]
        f = _a_draft(c)["id"]
        r = c.post(f"/api/exams/{f}/fill"); assert r.status_code == 200 and r.get_json()["rev"] == SC.load(f)["rev"]

@t
def an_event_has_the_same_check():
    _reset(); _cal(); _rooms_saved()
    with published(_PUB):
        c = committee()
        r = c.post("/api/events", json=dict(name="Sec 3 Learning Journey", levels=["Sec 3"], classes=[], start="2026-10-05", end="2026-10-05", in_charge="Mr Ben Ong"))
        assert r.status_code == 200, r.data
        e = r.get_json(); id = e["id"]; assert e["rev"] == 1
        assert c.get(f"/api/events/{id}").get_json()["rev"] == 1 and c.get(f"/api/events/{id}/view").get_json()["rev"] == 1
        assert c.put(f"/api/events/{id}", json=e, headers=_OLD).get_json()["rev"] == 2
        before = SC.load(id)
        r = c.put(f"/api/events/{id}", json=dict(e, name="Other"), headers=_OLD)
        assert r.status_code == 409 and r.get_json() == {"error": f"This event was changed by {before['saved_by']} since you opened it. Reload to carry on."}, r.data
        assert SC.load(id) == before
        e = dict(c.get(f"/api/events/{id}").get_json(), where="Off site (museum)", days={"2026-10-05": dict(levels=["Sec 3"], whole=False, **{"from": "07:40", "to": "10:40"})})
        r = c.put(f"/api/events/{id}", json=e, headers=_OLD); assert r.status_code == 200 and r.get_json()["rev"] == 3, r.data
        r = c.post(f"/api/events/{id}/fill", json=dict(way="form teachers")); assert r.status_code == 200 and r.get_json()["rev"] == 4, r.data
        assert c.get(f"/api/events/{id}/review").get_json()["rev"] == 4
        r = c.post(f"/api/events/{id}/fill", json=dict(way="department", dept="PE")); assert r.status_code == 200, r.data
        r = c.post(f"/api/events/{id}/send"); assert r.status_code == 200, r.data
        assert r.get_json()["rev"] == SC.load(id)["rev"] == 6
        assert c.put(f"/api/events/{id}", json=dict(c.get(f"/api/events/{id}").get_json()), headers=_OLD).status_code == 200

# ------------------------------------------------------------------------------------------------ the suggested mark
def _papers_for_mark():
    base = dict(level="Sec 3", subject="English", paper="Paper 1", minutes=60, who="level", students=[], together="")
    return [dict(base, id="pa", date="2026-10-05", start="07:50"), dict(base, id="pb", paper="Paper 2", date="2026-10-06", start="07:50")]

@t
def suggested_keeps_ids_of_papers_that_exist():
    pub = F.sample_pub(); e = _new(); e["papers"] = _papers_for_mark()
    e["suggested"] = ["pb", "gone", "pa", "pb"]
    saved = SC.save(e, pub, F.CAL, "x"); assert saved["suggested"] == ["pb", "pa"], saved["suggested"]
    e2 = _new(); e2["papers"] = _papers_for_mark()
    assert SC.save(e2, pub, F.CAL, "x")["suggested"] == []     # a missing key becomes []
    s = dict(suggested=["a", "b", "a", "z"], papers=[dict(id="b"), dict(id="a")])
    assert SC.clean_suggested(s) is None and s["suggested"] == ["a", "b"]
    s = dict(papers=[dict(id="a")]); SC.clean_suggested(s); assert "suggested" not in s or s["suggested"] == []

@t
def suggested_must_be_a_list_of_strings():
    pub = F.sample_pub()
    for bad in (None, "pa", {"pa": 1}, 5, [1], ["pa", None], [["pa"]]):
        e = _new(); e["papers"] = _papers_for_mark(); e["suggested"] = bad
        raises(ValueError, lambda: SC.save(e, pub, F.CAL, "x"), SC.WRONG)

@t
def suggested_never_changes_what_the_site_or_make_see():
    x = _xset(("3-01", "3-02", "4-01", "Hall"))
    s = _mk(_made_sched()); fp0, pub0, mk0 = AP.fp(s), AP.public(s), MK.fingerprint(s, x, _M)
    s["suggested"] = [p["id"] for p in s["papers"]]
    assert "suggested" not in AP.SNAP and "suggested" not in MK._USED and "suggested" not in AP.public(s)
    assert AP.fp(s) == fp0 and AP.public(s) == pub0 and MK.fingerprint(s, x, _M) == mk0 and MK.stale(s, x, _M) is False

@t
def a_put_drops_a_suggested_id_when_its_date_or_start_changes():
    _reset(); _cal(); _rooms_saved()
    with published(_PUB):
        c = committee(); e = _a_draft(c); id = e["id"]
        ps = [dict(p, date=None, start=None) for p in _papers_for_mark()]
        e = dict(e, papers=ps, suggested=["pa", "pb"])
        r = c.put(f"/api/exams/{id}", json=e); assert r.status_code == 200, r.data
        e = r.get_json(); assert e["suggested"] == ["pa", "pb"], "papers that are new keep their mark"
        for field, val in (("minutes", 70), ("paper", "Paper 9")):
            ps = [dict(p, **({field: val} if p["id"] == "pa" else {})) for p in e["papers"]]
            r = c.put(f"/api/exams/{id}", json=dict(e, papers=ps)); assert r.status_code == 200, r.data
            e = r.get_json(); assert e["suggested"] == ["pa", "pb"], (field, e["suggested"])
        ps = [dict(p, date="2026-10-06") if p["id"] == "pa" else p for p in e["papers"]]
        r = c.put(f"/api/exams/{id}", json=dict(e, papers=ps)); e = r.get_json()
        assert e["suggested"] == ["pb"], e["suggested"]
        ps = [dict(p, start="08:20") if p["id"] == "pb" else p for p in e["papers"]]
        r = c.put(f"/api/exams/{id}", json=dict(e, papers=ps)); e = r.get_json()
        assert e["suggested"] == [], e["suggested"]
        new = dict(_papers_for_mark()[0], id="pn", date="2026-10-05", start="07:50")
        r = c.put(f"/api/exams/{id}", json=dict(e, papers=e["papers"] + [new], suggested=["pn"])); e = r.get_json()
        assert e["suggested"] == ["pn"], "a new paper keeps its mark"
        r = c.put(f"/api/exams/{id}", json=dict(e, suggested="pn")); assert r.status_code == 400 and r.get_json() == {"error": SC.WRONG}
        assert "suggested" not in json.dumps(c.get(f"/api/exams/{id}/view").get_json().get("summary", {}))

@t
def an_older_schedule_without_the_key_behaves_as_empty():
    _reset(); _cal(); _rooms_saved()
    with published(_PUB):
        c = committee(); e = _a_draft(c)
        r = c.put(f"/api/exams/{e['id']}", json={k: v for k, v in e.items() if k != "suggested"}); assert r.status_code == 200, r.data
        assert r.get_json().get("suggested") == []

@t
def an_upload_keeps_a_make_up_papers_mark_and_drops_the_rest():
    import io
    _reset(); _cal(); _rooms_saved()
    with published(_PUB):
        c = committee(); e = _a_draft(c); id = e["id"]
        ps = _papers_for_mark() + [dict(_papers_for_mark()[0], id="pm", who="students", students=["3A-01"], paper="Make-up", date="2026-10-06", start="09:00")]
        r = c.put(f"/api/exams/{id}", json=dict(e, papers=ps, suggested=["pa", "pb", "pm"])); assert r.status_code == 200, r.data
        assert r.get_json()["suggested"] == ["pa", "pb", "pm"]
        x = c.get(f"/api/exams/{id}/papers.xlsx"); assert x.status_code == 200
        r2 = c.post(f"/api/exams/{id}/papers.xlsx", data=dict(file=(io.BytesIO(x.data), "p.xlsx"))); assert r2.status_code == 200, r2.data
        got = r2.get_json(); assert "pm" in [p["id"] for p in got["papers"]], got["papers"]
        assert got["suggested"] == ["pm"], got["suggested"]
        assert SC.load(id)["suggested"] == ["pm"]

@t
def a_start_given_as_7_50_is_the_stored_07_50():
    _reset(); _cal(); _rooms_saved()
    with published(_PUB):
        c = committee(); e = _a_draft(c); id = e["id"]
        e = c.put(f"/api/exams/{id}", json=dict(e, papers=_papers_for_mark(), suggested=["pa"])).get_json()
        ps = [dict(p, start="7:50") if p["id"] == "pa" else p for p in e["papers"]]
        e = c.put(f"/api/exams/{id}", json=dict(e, papers=ps)).get_json()
        assert e["suggested"] == ["pa"] and e["papers"][0]["start"] == "07:50", e["suggested"]
        ps = [dict(p, start="7:55") if p["id"] == "pa" else p for p in e["papers"]]
        assert c.put(f"/api/exams/{id}", json=dict(e, papers=ps)).get_json()["suggested"] == []

# ------------------------------------------------------------------------------------------------ the teacher in charge and the save check
@t
def the_change_of_teacher_in_charge_keeps_to_the_save_check():
    _setup()
    with published(_PUB):
        a, c = staff("Ms Aisha Rahman"), committee()
        id = _event(a)["id"]; url = f"/api/events/{id}/in-charge"
        old = c.get(f"/api/events/{id}").get_json(); r0 = old["rev"]; assert r0 == SC.load(id)["rev"]
        r = c.post(url, json=dict(name="Mr Ben Ong")); assert r.status_code == 200, r.data
        j = r.get_json(); assert j["rev"] == r0 + 1 == SC.load(id)["rev"], (j.get("rev"), SC.load(id).get("rev"))
        before = SC.load(id)
        for body in (dict(old, where="Somewhere else"), dict(old, where="Somewhere else", in_charge="Mr Ben Ong")):   # the other tab, opened before
            r = c.put(f"/api/events/{id}", json=body, headers=_OLD)
            assert r.status_code == 409 and r.get_json() == {"error": "This event was changed by Timetable committee since you opened it. Reload to carry on."}, r.data
            assert SC.load(id) == before, "nothing is saved"
        r = c.put(f"/api/events/{id}", json=dict(old, rev=j["rev"], where="Somewhere else"), headers=_OLD)
        assert r.status_code == 200 and r.get_json()["rev"] == r0 + 2, r.data
        s = SC.load(id); assert s["where"] == "Somewhere else" and s["in_charge"] == "Mr Ben Ong", "the page's save after it keeps the change"
        r = c.post(url, json=dict(name="Mr Ben Ong")); assert r.status_code == 400 and SC.load(id)["rev"] == r0 + 2, "a refused change saves nothing"
        import history, putback
        e = [x for x in history.read(kinds={"exams"}, limit=50) if x.get("what") == "in-charge"][0]
        assert putback.unit_of(e) is None and "exams" not in putback.TOUCH_KINDS, "Put back never reaches a schedule"
        r = c.post("/api/history/back", json=dict(id=e["id"])); assert r.status_code == 409 and r.get_json() == {"error": A.CANT_BACK}, r.data
        assert SC.load(id)["rev"] == r0 + 2 and SC.load(id)["in_charge"] == "Mr Ben Ong"
    _reset()

# ---- teacher-only periods: a mark, never a refusal ----
import contextlib  # noqa: E402
import copy  # noqa: E402

TP = "Mr Ben Ong"
TP_NAME = "Zone computing class"
TP_MARK = "has Zone computing class then"
MONDAY = "2026-10-05"

def _with_period(pub, times=("15:00", "17:30")):
    """a copy of pub whose setup holds one teacher-only period for TP on Mondays"""
    pub = copy.deepcopy(pub)
    st = pub["model"]["setup"]
    st["school"] = dict(start_time="07:40", period_minutes=20, periods_per_day=26)
    st["staff_periods"] = [dict(_id="z1", name=TP_NAME, all=False, depts=[], teachers=[TP], week="Both", days=["Mon"], times=list(times), place="")]
    return pub

@contextlib.contextmanager
def _period_published(times):
    """the shared _PUB with the period in its setup, put back after"""
    old = dict(_PUB["model"]["setup"])
    try:
        _PUB["model"]["setup"].update(_with_period(_PUB, times)["model"]["setup"])
        yield
    finally:
        _PUB["model"]["setup"].clear(); _PUB["model"]["setup"].update(old)

@t
def a_teacher_only_period_marks_and_never_blocks():
    pub = _with_period(F.sample_pub())
    P = TP
    view = D.day_view(pub, F.CAL, _sched(days=SEC3), MONDAY)
    assert P not in view["blocked"] and view["periods"][P] == [(900, 1050, TP_NAME)] and view["blocked"]["Mr Ivan Lee"] == [(460, 580)], view
    xset = _xset()
    assert IV._free(P, view, 930, 990, [], xset)[0] == "" and IV.marked(P, view, 930, 990) == TP_MARK
    assert IV.marked(P, view, 1050, 1100) == "" and IV.marked(P, view, 990, 1080) == TP_MARK      # an exam that runs after the last period
    assert D.day_view(pub, F.CAL, _sched(days=SEC3), "2026-10-06")["periods"] == {}
    got = IV.candidates(pub, F.CAL, _sched(days=SEC3), xset, MONDAY, 930, 990, [])
    assert [c["name"] for c in got["period"]] == [P] and got["period"][0]["reason"] == TP_MARK, got["period"]
    assert P not in [c["name"] for g in ("freed", "free", "backups", "need_backup") for c in got[g]]
    # a marked row of the setup never blocks, and a setup with no school gives no periods and no error
    pub["model"]["setup"]["rules"].append(dict(rule="Not available", scope="Teacher", target=P, strength="Must", day="Mon", week="Both", staff="x", **{"from": 0, "to": 5}))
    assert P not in D.day_view(pub, F.CAL, _sched(days=SEC3), MONDAY)["blocked"]
    assert F.sample_pub()["model"]["setup"].get("school") is None and D.day_view(F.sample_pub(), F.CAL, _sched(days=SEC3), MONDAY)["periods"] == {}

@t
def make_calls_them_only_when_the_free_run_out():
    s = _sit([_paper(who="level", date=MONDAY, start="15:30")], days=dict(SEC3))
    pub = _with_period(_PUB)
    names = [p["name"] for p in ACC.staff(pub)]
    F_ = "Ms Aisha Rahman"
    x = _xset(("3-01",)); x["rules"]["per_classroom"] = 1
    x["never"] = [n for n in names if n not in (TP, F_)]
    MK.make(pub, F.CAL, s, x, only=None, elsewhere=[])
    d = _duty(s, "%s 15:30" % MONDAY, "3-01")
    assert d["names"] == [F_] and d["marks"] == {}, d
    x["never"] = [n for n in names if n != TP]
    s = _sit([_paper(who="level", date=MONDAY, start="15:30")], days=dict(SEC3))
    MK.make(pub, F.CAL, s, x, only=None, elsewhere=[])
    d = _duty(s, "%s 15:30" % MONDAY, "3-01")
    assert d["names"] == [TP] and d["marks"] == {TP: TP_MARK} and not d.get("not_free"), d

@t
def a_name_chosen_by_hand_is_kept_with_a_mark():
    s = _sit([_paper(who="level", date=MONDAY, start="15:30")], days=dict(SEC3))
    pub = _with_period(_PUB)
    key = "%s 15:30" % MONDAY
    MK.make(pub, F.CAL, s, _xset(("3-01", "3-02")), only=None, elsewhere=[])
    MK.set_invigilators(s, key, "3-01", [TP, "Mr Ivan Lee"])
    MK.make(pub, F.CAL, s, _xset(("3-01", "3-02")), only=key, elsewhere=[])
    d = _duty(s, key, "3-01")
    assert d["names"] == [TP, "Mr Ivan Lee"] and d["marks"] == {TP: TP_MARK}, d
    assert TP not in d["not_free"] and not d["not_free"], d["not_free"]
    # a Monday morning: the plain Must rule still refuses and carries no mark
    s = _sit([_paper(who="level", date=MONDAY, start="07:50")], days=dict(SEC3))
    key = "%s 07:50" % MONDAY
    MK.make(pub, F.CAL, s, _xset(("3-01", "3-02")), only=None, elsewhere=[])
    MK.set_invigilators(s, key, "3-01", ["Mr Ivan Lee"])
    MK.make(pub, F.CAL, s, _xset(("3-01", "3-02")), only=key, elsewhere=[])
    d = _duty(s, key, "3-01")
    assert d["not_free"] == {"Mr Ivan Lee": "is not available then (a Must rule)"} and d["marks"] == {}, d

@t
def an_event_with_such_a_person_can_be_sent():
    pub = _with_period(_PUB, ("08:00", "09:00"))
    e = _ev(going=["Ms Aisha Rahman", TP])
    got = {g["name"]: g for g in EV.going(pub, F.CAL, e, [])}
    assert got[TP]["status"] == "period" and got[TP]["text"] == TP_MARK, got
    assert got["Ms Aisha Rahman"]["status"] == "free"
    assert EV.people_lines(pub, F.CAL, e, []) == [] and EV.clashes(pub, F.CAL, e, [], []) == []
    assert not any("Fix the clashes" in x for x in EV.send_errors(pub, F.CAL, e, [], []))
    w = EV.who_free(pub, F.CAL, _ev(going=["Ms Aisha Rahman"]), [])
    assert [x["name"] for x in w["period"]] == [TP] and w["period"][0]["reason"] == TP_MARK, w
    assert TP not in [x["name"] for g in ("freed", "free") for x in w[g]]
    # a plain Must rule still stops it
    assert EV.going(pub, F.CAL, _ev(going=["Mr Ivan Lee"]), [])[0]["status"] == "not_free"

@t
def a_replacement_in_a_period_is_accepted():
    _setup()
    with published(_PUB), _period_published(("08:00", "09:00")):
        a, c = staff("Ms Aisha Rahman"), committee()
        # the exam: Mr Ben Ong has the period during the duty, Mr Ivan Lee is still refused on a Monday morning
        s = _made_exam(c); id = s["id"]
        assert c.post(f"/api/exams/{id}/send").status_code == 200 and c.post(f"/api/exams/{id}/approve").status_code == 200
        who = c.get(f"/api/exams/{id}/who?key={KEY1}&room=3-01&copy=approved").get_json()
        assert TP in [x["name"] for x in who["period"]] and TP not in [x["name"] for g in ("freed", "free", "backups") for x in who[g]], who
        body = dict(key=KEY1, room="3-01", away="Ms Chloe Tan", name="Mr Ivan Lee")
        r = c.post(f"/api/exams/{id}/away", json=body); assert r.status_code == 400 and r.get_json() == {"error": "Mr Ivan Lee is not free then."}, r.data
        r = c.post(f"/api/exams/{id}/away", json=dict(body, name=TP)); assert r.status_code == 200, r.data
        # the event (on a fresh setup: the exam above would clash with it)
        _setup()
        a, c = staff("Ms Aisha Rahman"), committee()
        e = _approved_event(a, c); eid = e["id"]
        w = a.get(f"/api/events/{eid}/who").get_json()
        assert [x["name"] for x in w["period"]] == [TP], w
        r = a.post(f"/api/events/{eid}/away", json=dict(away="Mr Hafiz Rahman", name="Mr Ivan Lee")); assert r.status_code == 400 and r.get_json() == {"error": "Mr Ivan Lee is not free then."}, r.data
        r = a.post(f"/api/events/{eid}/away", json=dict(away="Mr Hafiz Rahman", name=TP)); assert r.status_code == 200, r.data
    _reset()


print(f"{COUNT} exams tests passed")

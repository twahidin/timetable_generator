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
from exams import settings as ES, fake as F, days as D  # noqa: E402
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

print(f"{COUNT} exams tests passed")

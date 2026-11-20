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
from exams import settings as ES, fake as F  # noqa: E402
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

print(f"{COUNT} exams tests passed")

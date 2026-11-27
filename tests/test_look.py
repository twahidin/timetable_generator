"""Plain-assert tests for the timetable look (the published page and the PDFs): run with .venv/bin/python tests/test_look.py"""
import copy, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(HERE))
from ttgen import reader, export  # noqa: E402
from ttgen.samples import secondary  # noqa: E402
n = 0
def t(f): global n; f(); n += 1

CLASS, TEACHER, ROOM = "1A", "Adeline Tan", "A1-01"   # CLASS has lessons in both weeks; TEACHER has an allowance and an after-school lesson; ROOM is in use

def school():
    """a made-up model (no solver): sample secondary school, two weeks, lessons placed by hand for class 1A:
    one, two and three periods long; a lesson after lunch on both Mondays; Thursday ends before lunch; an after-school whole-class lesson (ext)"""
    sp = copy.deepcopy(secondary()); reader.derive(sp); days = list(sp["day_structure"][sp["school"]["levels"][0]].keys())
    level = {c["class"]: c["level"] for c in sp["classes"]}
    E = export.ENTIRE; c = [CLASS]
    placed = [(0, 1, 3, c, "English Language G3", E, [TEACHER], ROOM), (0, 9, 1, c, "Mathematics G3", E, ["Benjamin Teo"], ROOM),
              (0, 20, 3, c, "Science G3", E, ["Benjamin Teo"], "Science Lab 1"), (1, 1, 2, c, "Mathematics G3", E, ["Benjamin Teo"], ROOM),
              (3, 1, 3, c, "English Language G3", E, [TEACHER], ROOM), (5, 1, 3, c, "English Language G3", E, [TEACHER], ROOM),
              (5, 20, 3, c, "Science G3", E, ["Benjamin Teo"], "Science Lab 1"), (5, 9, 2, c, "Mathematics G3", E, ["Benjamin Teo"], ROOM),
              (0, 23, 2, c, "English Language G3", E, [TEACHER], ROOM)]
    L = [dict(id=i + 1, d=d, p=p, n=n_, level=level.get(cls[0], "") if cls else "", block="", classes=cls, subject=s, group=g, teachers=tt, room=r, ext=(p == 23), rain="")
         for i, (d, p, n_, cls, s, g, tt, r) in enumerate(placed)]
    m = export._model(sp, days, L); m.setdefault("checked_setup", sp); return m

def _lunch_days():
    m = school(); row = m["grid"][m["class_ix"][CLASS]["level"]]
    return len({x["d"] for x in m["lessons"] if CLASS in x["classes"] and "U" in row[x["d"]] and x["p"] > row[x["d"]].rindex("U")})
LUNCH_DAYS = _lunch_days()   # day rows of CLASS's timetable with a lesson starting at or after the end of lunch

def a_page_that_is_not_the_committees_carries_no_planning_data():
    m = school()
    full = export.html_data(m); com = export.html_data(m, app=dict(mode="committee"))
    assert full == dict(com, app=None)                      # a saved copy is the committee's
    assert any(t[3] for t in com["teachers"]) and any(c[2] for c in com["classes"]) and any(x[11] for x in com["lessons"])
    for view, mode in (("full", "teacher"), ("staff", "staff"), ("student", "student")):
        d = export.html_data(m, view, app=dict(mode=mode))
        assert all(t[3] == "" for t in d["teachers"]) and all(c[2] == "" for c in d["classes"]), mode
        assert all(x[11] == 0 for x in d["lessons"]) and d["checks"]["after"] == [] and d["checks"]["notes"] == [], mode
    t_ = export.html_data(m, "full", app=dict(mode="teacher"))
    assert t_["checks"]["problems"] == com["checks"]["problems"] and t_["checks"]["ok"] == com["checks"]["ok"]
    sid = m["students"][0]["id"]; me = export.html_data(m, "personal", student_id=sid, app=dict(mode="personal"))
    assert all(x[11] == 0 for x in me["lessons"]) and all(c[2] == "" for c in me["classes"])
t(a_page_that_is_not_the_committees_carries_no_planning_data)

# tests are added above this line by each task
if __name__ == "__main__": print(f"{n} checks passed")

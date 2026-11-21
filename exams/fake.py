"""A made-up school for the exams tests, shaped as ttgen/export.py builds the published model. Made-up names only."""
from ttgen.report import clock
from ttgen.spec import day_names

CAL = dict(terms=[dict(name="Term 4", start="2026-09-07", end="2026-11-20", starts_as="Odd")],
           holidays=[dict(start="2026-10-12", end="2026-10-12", name="School holiday")])

TEACHERS = [("Ms Aisha Rahman", "English"), ("Mr Ben Ong", "Science"), ("Ms Chloe Tan", "Mathematics"),
            ("Mr Daniel Koh", "Mathematics"), ("Ms Grace Yeo", "English"), ("Mr Hafiz Rahman", "PE"), ("Mr Ivan Lee", "English")]


def _lesson(i, d, p, n, level, classes, subject, group, teachers, room, rain=""):
    return dict(id=i, d=d, p=p, n=n, level=level, block="", classes=classes, subject=subject, group=group,
                teachers=teachers, room=room, ext=False, rain=rain)


def sample_pub() -> dict:
    NP = 26
    sc = dict(start_time="07:40", period_minutes=20)
    times = [[clock(sc, p), clock(sc, p + 1)] for p in range(NP)]   # the real model's dotted 12-hour clock: "12.40", "1.00"
    classes = [dict(name="3A", level="Sec 3", size=30, home="3-01", parents=[]),
               dict(name="3B", level="Sec 3", size=30, home="3-02", parents=[]),
               dict(name="4A", level="Sec 4", size=30, home="4-01", parents=[])]
    students = []
    for c in classes:
        for k in range(1, 31):
            sid = "%s-%02d" % (c["name"], k)
            groups = [] if c["name"] == "4A" else (["3PC1"] if k <= 10 else ["3CS1"])
            students.append(dict(id=sid, name="Student " + sid, cls=c["name"], level=c["level"], groups=groups))
    teachers = [dict(name=n, dept=d) for n, d in TEACHERS]
    model_teachers = [dict(name=n, short=n, dept=d, allowance="", other="") for n, d in TEACHERS]
    rooms = [dict(name=n, kind="classroom", capacity=40, parts=[]) for n in ("3-01", "3-02", "4-01")]
    rooms += [dict(name="Hall", kind="pe venue", capacity=400, parts=[]),
              dict(name="3-11", kind="special room", capacity=24, parts=[]),
              dict(name="Lab 3-08", kind="lab", capacity=40, parts=[]),
              dict(name="LT1", kind="classroom", capacity=40, parts=[]),
              dict(name="LT2", kind="classroom", capacity=40, parts=[]),
              dict(name="LT1&2", kind="classroom", capacity=80, parts=["LT1", "LT2"])]
    E = "Entire Class"
    lessons = [
        _lesson(0, 0, 0, 2, "Sec 3", ["3A"], "English", E, ["Ms Aisha Rahman"], "3-01"),
        _lesson(1, 0, 0, 2, "Sec 3", ["3B"], "Mathematics", E, ["Ms Chloe Tan"], "3-02"),
        _lesson(2, 0, 1, 2, "Sec 4", ["4A"], "Mathematics", E, ["Mr Daniel Koh"], "4-01"),
        _lesson(3, 0, 6, 3, "Sec 3", ["3A", "3B"], "Pure Chemistry", "3PC1", ["Mr Ben Ong"], "Lab 3-08"),
        _lesson(4, 0, 6, 3, "Sec 3", ["3A", "3B"], "Combined Science", "3CS1", ["Ms Grace Yeo"], "3-01"),
        _lesson(5, 0, 4, 2, "Sec 4", ["4A"], "PE", E, ["Mr Hafiz Rahman"], "Field", rain="Hall"),
        _lesson(6, 0, 9, 2, "Sec 4", ["4A"], "English", E, ["Ms Grace Yeo"], "4-01"),
        _lesson(7, 0, 3, 1, "Sec 4", ["4A"], "Literature", E, ["Ms Grace Yeo"], "LT1"),
        _lesson(8, 0, 12, 1, "Sec 3", ["3A", "4A"], "Assembly", E, ["Mr Hafiz Rahman"], "Hall"),
        _lesson(9, 1, 0, 2, "Sec 3", ["3A"], "English", E, ["Mr Ivan Lee"], "3-01"),
    ]
    rules = [dict(rule="Not available", scope="Teacher", target="Mr Ivan Lee", strength="Must", day="Mon", week="Both", **{"from": 0, "to": 5})]
    days = day_names(2)
    model = dict(school=dict(name="Sample School", timetable="2027", weeks=2, period_minutes=20, start_time="07:40"),
                 days=days, NP=NP, ND=len(days), times=times, levels=["Sec 3", "Sec 4"], classes=classes, students=students,
                 teachers=model_teachers, rooms=rooms, room_parts={"LT1&2": ["LT1", "LT2"]}, lessons=lessons,
                 setup=dict(teachers=teachers, roles=[], rules=rules))
    return dict(meta=dict(school="Sample School"), codes={}, views={}, model=model)

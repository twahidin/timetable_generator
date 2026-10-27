"""Shared vocabulary for the timetable setup template.

A *spec* is a plain dict (JSON friendly) holding everything the template holds:
  school        settings (type, name, cycle, period length, start time, levels, tags ...)
  day_structure {level: {day name: code string}}  codes: F flag/assembly, L lesson, R recess,
                U lunch, A after-school slot (used only if needed), '.' no school
  venues, classes, subjects, teachers, blocks, lessons, rules, students, combinations (lists of dicts)
"""
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"]
CODES = {"F": "Flag / assembly", "L": "Lessons", "R": "Recess", "U": "Lunch", "A": "After-school slot", ".": "No school"}
SCOPES = ["School", "Level", "Class", "Teacher", "Department", "Subject", "Block", "Room"]

# rule name, scopes it applies to, needs from/to periods, needs number, meaning, example
RULE_TYPES = [
    ("Not available", "Teacher, Class, Room, Level, Block", "Y", "N", "No lessons in these periods (part-time days, meetings, room bookings).", "Teacher · Ms Tan · All days · 18 to 19"),
    ("Keep free together", "Department, Level", "Y", "N", "Every teacher in the department (or every class in the level) is free at the same time.", "Department · EL · Wed · 20 to 22"),
    ("Fixed at", "Class, Block, Subject", "Y", "N", "The lesson starts at the From period on that Day (Day All: every lesson of it starts at From). Use Subject to say which lesson of a class.", "Class · 3A · Character Education · Mon · 1"),
    ("Not in periods", "Subject, Level, Class, Block", "Y", "N", "Not placed in these periods. Use Subject to narrow a level or class rule.", "Level · Sec 1 · Physical Education · All · 20 to 22"),
    ("Only in periods", "Subject, Level, Class, Block", "Y", "N", "Only placed in these periods.", "Subject · Mathematics G3 · All · 1 to 17"),
    ("Finish by", "Level, Class", "Y", "N", "No lessons after the To period on that day.", "Class · 4A · Fri · to 14"),
    ("Max periods a day", "Teacher, Class, Level, School", "N", "Y", "At most Number periods of lessons in a day (School = every teacher).", "School · Whole school · 15"),
    ("Max periods in a row", "Teacher, School", "N", "Y", "At most Number periods without a break (checked after solving).", "School · Whole school · 9"),
    ("At least one recess a day", "Teacher, School", "N", "N", "The teacher is free in at least one recess each day (checked after solving).", "School · Whole school"),
    ("At most N at once", "Room, Subject", "N", "Y", "At most Number lessons at the same time (rooms that hold two classes, PE).", "Room · Field · 2"),
    ("Same time across classes", "Level", "N", "N", "Every class of the level has the Subject at the same time (level talks, CCE).", "Level · Sec 3 · Character Education"),
    ("Not on the same day as", "Subject", "N", "N", "Applies to and Subject are never on the same day for a class.", "Subject · Physical Education · Design & Technology"),
    ("Once a day per group", "School, Subject", "N", "N", "A group meets at most once a day for a subject.", "School · Whole school"),
    ("Avoid after-school slots", "School, Level, Class", "N", "N", "Use the 'A' periods in Day structure only when a class cannot fit otherwise.", "School · Whole school"),
]

def day_names(weeks):
    return [f"{w} {d}" for w in ("Odd", "Even") for d in WEEKDAYS] if int(weeks) == 2 else list(WEEKDAYS)

def defaults(kind):
    """school settings for 'secondary' or 'primary'"""
    if kind == "secondary":
        return dict(type="secondary", name="Sample Secondary School", timetable="2027 Semester 1", weeks=2, period_minutes=20,
                    start_time="07:30", periods_per_day=26, lesson_length=3,
                    levels=["Sec 1", "Sec 2", "Sec 3", "Sec 4"],
                    bands={"Sec 1": "Sec 1-2", "Sec 2": "Sec 1-2", "Sec 3": "Sec 3-4", "Sec 4": "Sec 3-4", "Sec 5": "Sec 3-4"},
                    tags=[["G3", "P"], ["G2", "A"], ["G1", "K"], ["-", ""]],
                    departments=["EL", "MT", "MA", "SC", "HU", "AE", "CT", "IT", "PE", "CCE", "ALP"],
                    room_kinds=["classroom", "lab", "computer lab", "art room", "d&t studio", "food lab", "music room", "pe venue", "special room"])
    return dict(type="primary", name="Sample Primary School", timetable="2027 Term 1", weeks=1, period_minutes=30,
                start_time="07:30", periods_per_day=14, lesson_length=2,
                levels=["P1", "P2", "P3", "P4", "P5", "P6"],
                bands={"P1": "P1-2", "P2": "P1-2", "P3": "P3-4", "P4": "P3-4", "P5": "P5-6", "P6": "P5-6"},
                tags=[["Std", "S"], ["Fdn", "F"], ["Higher", "H"], ["-", ""]],
                departments=["EL", "MT", "MA", "SC", "SS", "AE", "PE", "CCE", "PAL"],
                room_kinds=["classroom", "science room", "computer lab", "art room", "music room", "pe venue", "hall", "special room"])

def scopes_for(school):
    lv = school["levels"]; bands = []
    for b in school["bands"].values():
        if b not in bands: bands.append(b)
    return ["All"] + lv + bands

def lesson_split(periods, length):
    """periods a cycle -> (full lessons, short lessons, length). Short lessons are length-1 periods long."""
    p, L = int(periods or 0), int(length or 1)
    if p <= 0: return 0, 0, L
    if L <= 1: return p, 0, 1
    short = (-p) % L
    if short * (L - 1) > p: short = 0
    return (p - short * (L - 1)) // L, short, L


def family(s):
    """subject family without level tags or brackets: 'Higher Chinese G3' -> 'Chinese'"""
    import re
    s = re.sub(r"\s*\(.*?\)", "", str(s)); s = re.sub(r"\b(G[123]|Std|Fdn|Standard|Foundation)\b", "", s).strip()
    return re.sub(r"^(Higher |Combined |Lower Secondary )", "", s)

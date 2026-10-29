"""Shared vocabulary for the timetable setup template.

A *spec* is a plain dict (JSON friendly) holding everything the template holds:
  school        settings (type, name, cycle, period length, start time, levels, tags ...)
  day_structure {level: {day name: code string}}  codes: F flag/assembly, L lesson, R recess,
                W recess window (the solver puts the recess in it; the rest is lesson time), U lunch,
                A after-school slot (used only if needed), '.' no school
  venues, classes, subjects, teachers, blocks, lessons, rules, students, combinations (lists of dicts)
"""
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"]
CODES = {"F": "Flag / assembly", "L": "Lessons", "R": "Recess", "W": "Recess window (the solver puts the recess in it)", "U": "Lunch", "A": "After-school slot", ".": "No school"}
SCOPES = ["School", "Level", "Class", "Teacher", "Department", "Subject", "Block", "Group", "Room"]

# rule name, scopes it applies to, needs from/to periods, needs number, meaning, example
RULE_TYPES = [
    ("Not available", "Teacher, Class, Room, Level, Block", "Y", "N", "No lessons in these periods (part-time days, meetings, room bookings).", "Teacher · Ms Tan · All days · 18 to 19"),
    ("Keep free together", "Department, Level", "Y", "N", "Every teacher in the department (or every class in the level) is free at the same time.", "Department · EL · Wed · 20 to 22"),
    ("Fixed at", "Class, Block, Group, Subject", "Y", "N", "The lesson starts at the From period on that Day (Day All: every lesson of it starts at From). Use Subject to say which lesson of a class; Group is a group code from 6 Lessons.", "Class · 3A · Character Education · Mon · 1"),
    ("Not in periods", "Subject, Level, Class, Block", "Y", "N", "Not placed in these periods. Use Subject to narrow a level or class rule.", "Level · Sec 1 · Physical Education · All · 20 to 22"),
    ("Only in periods", "Subject, Level, Class, Block", "Y", "N", "Only placed in these periods.", "Subject · Mathematics G3 · All · 1 to 17"),
    ("Finish by", "Level, Class", "Y", "N", "No lessons after the To period on that day.", "Class · 4A · Fri · to 14"),
    ("Max periods a day", "Teacher, Class, Level, School", "N", "Y", "At most Number periods of lessons in a day (School = every teacher).", "School · Whole school · 15"),
    ("Max periods in a row", "Teacher, School", "N", "Y", "At most Number periods without a break (checked after solving).", "School · Whole school · 9"),
    ("At least one recess a day", "Teacher, School", "N", "N", "The teacher is free for a recess each day: a whole recess (R), or the recess length inside a recess window (W), of any level.", "School · Whole school"),
    ("At most N at once", "Room, Subject, Department", "N", "Y", "At most Number lessons at the same time (rooms that hold two classes; Department PE = PE classes at once).", "Department · PE · 6"),
    ("Same time across classes", "Level", "N", "N", "Every class of the level has the Subject at the same time (level talks, CCE).", "Level · Sec 3 · Character Education"),
    ("Not on the same day as", "Subject", "N", "N", "Applies to and Subject are never on the same day for a class.", "Subject · Physical Education · Design & Technology"),
    ("Once a day per group", "School, Subject", "N", "N", "A group meets at most once a day for a subject.", "School · Whole school"),
    ("Avoid after-school slots", "School, Level, Class", "N", "N", "Use the 'A' periods in Day structure only when a class cannot fit otherwise.", "School · Whole school"),
]

# rule rows on the Settings sheet: the row's label, a key, whether its value is a number (else Yes/No), and the rule it
# stands for (after_school and pe_rain_home are school settings instead: No means the 'A' periods are never used; Yes keeps
# each class's home room free during its PE, as the rain room)
_SCHOOL = dict(scope="School", target="Whole school", week="Both", day="All", strength="Must")
SETTING_RULES: list[dict] = [
    dict(key="once_a_day", label="Same subject at most once a day (per group)", number=False, rule=dict(_SCHOOL, rule="Once a day per group")),
    dict(key="after_school", label="After-school slot allowed when a class cannot fit", number=False, rule=None),
    dict(key="pe_at_once", label="Most PE classes at the same time", number=True, rule=dict(_SCHOOL, scope="Department", target="PE", rule="At most N at once")),
    dict(key="max_day", label="Most teaching periods a teacher has in a day", number=True, rule=dict(_SCHOOL, rule="Max periods a day")),
    dict(key="recess", label="Every teacher gets at least one recess a day", number=False, rule=dict(_SCHOOL, rule="At least one recess a day")),
    dict(key="pe_rain_home", label="In rain, PE goes to the class's home room", number=False, rule=None),
]
PE_KIND = "pe venue"   # the room kind of PE lessons (field, hall, courts): with pe_rain_home their class's home room stays free


def end_by(school):
    """'Lessons end by (Monday to Thursday)' rows on Settings -> [(weekdays, minutes after midnight)]: no lesson runs
    past that time on those days (the Day structure holds the longest possible day; these trim it)"""
    import re
    full = ["monday", "tuesday", "wednesday", "thursday", "friday"]
    idx = lambda w: next((i for i, d in enumerate(full) if d[:3] == w[:3].lower()), None)
    out = []
    for row in school.get("extra_settings") or []:
        label, v = str(row[0] or ""), row[1] if len(row) > 1 else None
        if not label.lower().startswith("lessons end by") or v in (None, ""): continue
        found = re.search(r"\((.*?)\)", label); txt = (found.group(1) if found else "monday to friday").lower()
        span = re.match(r"\s*(\w+)\s+to\s+(\w+)", txt)
        a, b = (idx(span.group(1)), idx(span.group(2))) if span else (None, None)
        days = WEEKDAYS[a:b + 1] if a is not None and b is not None else [WEEKDAYS[i] for i in (idx(w) for w in re.findall(r"[a-z]+", txt)) if i is not None]
        h, m = (str(v).replace(".", ":").split(":") + ["0"])[:2]
        if h.strip().isdigit() and (m[:2] or "0").isdigit(): out.append((set(days), int(h) * 60 + int(m[:2] or 0)))   # not a time: ignored (the editor flags it)
    return out

def periods_by_day(school, days):
    """{day name: periods of the day lessons may use} for the days a 'Lessons end by' row trims: a lesson must end by the time"""
    h, m = map(int, str(school["start_time"]).split(":")[:2]); NP = int(school["periods_per_day"]); out = {}
    for weekdays, cut in end_by(school):
        keep = max(0, min(NP, (cut - h * 60 - m) // int(school["period_minutes"])))
        for d in days:
            if str(d).split()[-1][:3] in weekdays: out[d] = min(out.get(d, NP), keep)
    return out

def trim_day(row, keep):
    """a Day structure row with the periods from `keep` on turned into no school"""
    return row if keep is None else row[:keep] + "." * (len(row) - keep)

# Settings rows for floating recess (the W periods on Day structure): label, default, note
RECESS_ROWS = [("Floating recess goes by", "Level", "Level: each level has its recess together. Class: each class has its own recess time. For the W (recess window) periods on Day structure."),
               ("Floating recess length (periods)", 2, "How long the recess is inside each recess window."),
               ("Most classes at recess at once", None, "Leave empty for no limit (canteen space). Counts fixed (R) and floating recess.")]

def floating_recess(school):
    """the floating recess rows on Settings: dict(by='Level' or 'Class', length=periods, at_once=classes or None)"""
    def val(label):
        row = next((r for r in school.get("extra_settings") or [] if str(r[0] or "").strip().lower().startswith(label.lower())), None)
        return row[1] if row and len(row) > 1 and row[1] not in (None, "") else None
    def num(v):
        try: return int(float(str(v)))
        except (TypeError, ValueError): return None
    by = str(val("Floating recess goes by") or "Level").strip().capitalize()
    return dict(by="Class" if by.startswith("Cl") else "Level", length=max(1, num(val("Floating recess length")) or 2),
                at_once=num(val("Most classes at recess at once")) or None)

def windows(row):
    """the recess windows of a Day structure row: [(first period, last period)] of each run of W"""
    import re
    return [(m.start(), m.end() - 1) for m in re.finditer(r"W+", row)]

def resolve_row(row, spans):
    """a Day structure row as one class has it: its recess (spans [(period, length)]) as R, the rest of each window as L"""
    out = list(row.replace("W", "L"))
    for p, n in spans:
        for q in range(p, min(len(out), p + n)): out[q] = "R"
    return "".join(out)

def no_free_periods(school):
    """the 'Students have no free periods' row on Settings: 'Yes', 'Prefer', 'No' or None"""
    row = next((r for r in school.get("extra_settings") or [] if str(r[0] or "").lower().startswith("students have no free periods")), None)
    return str(row[1]).strip().capitalize() if row and len(row) > 1 and row[1] not in (None, "") else None

def split_rules(spec) -> dict:
    """where each rule lives in the workbook: a rule row on Settings ({key: value}), Teacher availability (Must 'Not
    available' for a teacher), Fixed lessons (Must 'Fixed at' for a class or group), or More rules (everything else)"""
    settings, availability, fixed, more = {}, [], [], []
    for r in spec.get("rules", []):
        must = str(r.get("strength") or "Must") == "Must"
        key = next((s["key"] for s in SETTING_RULES if s["rule"] and r.get("rule") == s["rule"]["rule"] and r.get("scope") == s["rule"]["scope"]
                    and (r.get("scope") != "Department" or r.get("target") == s["rule"]["target"])), None)
        if key and must and key not in settings:
            settings[key] = r.get("number") if next(s for s in SETTING_RULES if s["key"] == key)["number"] else "Yes"
        elif r.get("rule") == "Not available" and r.get("scope") == "Teacher" and must and r.get("from") not in (None, ""): availability.append(r)
        elif r.get("rule") == "Fixed at" and r.get("scope") in ("Class", "Group") and must and r.get("from") not in (None, ""): fixed.append(r)
        else: more.append(r)
    return dict(settings=settings, availability=availability, fixed=fixed, more=more)

# the usual Singapore school roles and the periods a cycle each usually carries (2-week cycle; the Roles sheet can change them)
ROLES = [("HOD", "Head of Department", 67, "Management"), ("SH", "Subject Head", 88, "Management"), ("LT", "Lead Teacher", 67, "Teacher leader"),
         ("ST", "Senior Teacher", 86, "Teacher leader"), ("EO", "Education Officer (teacher)", 104, "Teacher"), ("BT", "Beginning Teacher", 86, "Teacher"),
         ("FAJT", "Flexible Adjunct Teacher (part-time)", 75, "Part-time"), ("UT", "Untrained Teacher: should not teach alone", 104, "Teacher (needs support)"),
         ("New hire", "Post to be filled", 86, "Teacher"), ("Relief", "Relief teacher", 86, "Teacher")]

def order_days(names):
    """day names in calendar order (Odd week before Even, Monday to Friday), whatever order they arrive in"""
    def key(d):
        w = str(d).split()
        return (1 if w[0] == "Even" else 0, next((i for i, x in enumerate(WEEKDAYS) if w[-1][:3].lower() == x.lower()), 9))
    return sorted(names, key=key)

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

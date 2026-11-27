"""Shared vocabulary for the timetable setup template.

A *spec* is a plain dict (JSON friendly) holding everything the template holds:
  school        settings (type, name, cycle, period length, start time, levels, tags ...)
  day_structure {level: {day name: code string}}  codes: F flag/assembly, L lesson, R recess,
                W recess window (the solver puts the recess in it; the rest is lesson time), U lunch,
                A after-school slot (used only if needed), '.' no school
  venues, classes, subjects, teachers, blocks, lessons, rules, students, combinations (lists of dicts)
"""
import re
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"]
CODES = {"F": "Flag / assembly", "L": "Lessons", "R": "Recess", "W": "Recess window (the solver puts the recess in it)", "U": "Lunch", "A": "After-school slot", ".": "No school"}
SCOPES = ["School", "Level", "Class", "Teacher", "Department", "Subject", "Block", "Group", "Room"]

# rule name, scopes it applies to, needs from/to periods, needs number, meaning, example
RULE_TYPES = [
    ("Not available", "Teacher, Class, Room, Level, Block", "Y", "N", "No lessons in these periods (part-time days, meetings, room bookings).", "Teacher · Ms Tan · All days · 18 to 19"),
    ("Keep free together", "Department, Level", "Y", "N", "Every teacher in the department (or every class in the level) is free at the same time.", "Department · EL · Wed · 20 to 22"),
    ("Fixed at", "Class, Block, Group, Subject, Level, School", "Y", "N", "The lesson starts at the From period on that Day (Day All: every lesson of it starts at From). Use Subject to say which lesson of a class; Group is a group code from 6 Lessons. Level or School with a Subject: that lesson of every class (whole-school CCE); on Fixed lessons, Class 'Every class'.", "School · Whole school · Character Education 1 · Odd · Fri · 11"),
    ("Not in periods", "Subject, Level, Class, Block, School", "Y", "N", "Not placed in these periods. Use Subject to narrow a level, class or school rule.", "Level · Sec 1 · Physical Education · All · 20 to 22"),
    ("Only in periods", "Subject, Level, Class, Block, School", "Y", "N", "Only placed in these periods.", "Subject · Mathematics G3 · All · 1 to 17"),
    ("Finish by", "Level, Class, School", "Y", "N", "No lessons after the To period on that day.", "Class · 4A · Fri · to 14"),
    ("Only these subjects", "School, Level, Class", "Y", "N", "In these periods only lessons of the subjects named in Subject, separated by commas, are placed; every other lesson is kept out (a home-based learning day). A name without its G1/G2/G3 tag covers every tag; a department code (MT, SC) covers its subjects. Blank periods: the whole day.", "School · Whole school · English Language, Mathematics, MT, SC · Even · Fri"),
    ("Only in venues", "Subject, Level, Class, School", "Y", "N", "A lesson that runs into these periods is held only in the rooms listed under Venues, separated by commas (PE late in the day only in a sheltered hall). Use Subject to narrow a level or school rule. Prefer: those rooms when one is free.", "Subject · Physical Education · All · 10 to 25 · Hall, ISH"),
    ("Max periods a day", "Teacher, Class, Level, School", "N", "Y", "At most Number periods of lessons in a day (School = every teacher).", "School · Whole school · 15"),
    ("Max periods in a row", "Teacher, School", "N", "Y", "At most Number periods without a break (checked after solving).", "School · Whole school · 9"),
    ("At least one recess a day", "Teacher, School", "N", "N", "The teacher is free for a recess each day: a whole recess (R), or the recess length inside a recess window (W), of any level.", "School · Whole school"),
    ("At most N at once", "Room, Subject, Department", "N", "Y", "At most Number lessons at the same time (rooms that hold two classes; Department PE = PE classes at once).", "Department · PE · 6"),
    ("Same time across classes", "Level", "N", "N", "Every class of the level has the Subject at the same time (level talks, CCE).", "Level · Sec 3 · Character Education"),
    ("Not on the same day as", "Subject", "N", "N", "Applies to and Subject are never on the same day for a class.", "Subject · Physical Education · Design & Technology"),
    ("Once a day per group", "School, Subject", "N", "N", "A group meets at most once a day for a subject.", "School · Whole school"),
    ("Avoid after-school slots", "School, Level, Class", "N", "N", "Use the 'A' periods in Day structure only when a class cannot fit otherwise.", "School · Whole school"),
    ("In words", "School, Level, Class, Subject, Room, Teacher", "N", "N", "A rule in plain words that the list cannot say. The timetable scripts do not enforce it: the agent honours a Must, tries a Prefer, and reports how each was met.", "Level · Sec 1 · No PE in the first period"),
]
TYPED = "In words"             # a rule the agent honours and reports on; never enforced by the solver
SKILL_VERSION = "2026-11.12"     # SKILL.md's version line and the one the workbook's README names

def teacher_depts(t):
    """A teacher row's departments, home first: the trimmed, non-empty, different ones of dept and dept2"""
    out = []
    for k in ("dept", "dept2"):
        d = str(t.get(k) or "").strip()
        if d and d not in out: out.append(d)
    return out

# ---- teacher-only periods: spec["staff_periods"], weekly periods for named teachers with no students ----
def _clock_min(v):
    """"HH:MM" -> minutes after midnight, or None when it is not a time"""
    m = re.fullmatch(r"(\d{1,2}):(\d{2})", v.strip(), re.ASCII) if isinstance(v, str) else None
    return int(m[1]) * 60 + int(m[2]) if m and int(m[1]) < 24 and int(m[2]) < 60 else None

def _slist(v): return [x.strip() for x in v if isinstance(x, str) and x.strip()] if isinstance(v, list) else []
def _sstr(v): return v if isinstance(v, str) else ""

def staff_rows(spec):
    """the rows of spec['staff_periods'] that are dicts; [] when the key is missing or not a list"""
    v = (spec or {}).get("staff_periods")
    return [r for r in v if isinstance(r, dict)] if isinstance(v, list) else []

def staff_people(spec, row):
    """the names on step 4 that the row means now (all, a department, or named), in step 4's order, each once"""
    ts = [t for t in (spec or {}).get("teachers") or [] if isinstance(t, dict)]
    depts, names = set(_slist(row.get("depts"))), set(_slist(row.get("teachers")))
    out = []
    for t in ts:
        nm = str(t.get("name") or "").strip()
        if nm and nm not in out and (row.get("all") is True or nm in names or depts & set(teacher_depts(t))): out.append(nm)
    return out

def staff_faults(spec, row):
    """[(hard, sentence)] for a row: soft ones (names or departments that mean nobody) first, then hard ones, which hide the row"""
    ts = [t for t in (spec or {}).get("teachers") or [] if isinstance(t, dict)]
    have = {str(t.get("name") or "").strip() for t in ts}; have_d = {d for t in ts for d in teacher_depts(t)}
    out = [(False, f"{x} is not on step 4.") for x in _slist(row.get("teachers")) if x not in have]
    out += [(False, f"Department {x} has no teacher.") for x in _slist(row.get("depts")) if x not in have_d]
    name = _sstr(row.get("name")).strip()
    if not name: out.append((True, "It has no name."))
    if len(_sstr(row.get("name"))) > 60: out.append((True, "Its name is longer than 60 letters."))
    if len(_sstr(row.get("place"))) > 60: out.append((True, "Its place is longer than 60 letters."))
    if not staff_people(spec, row): out.append((True, "Nobody is in it."))
    if not _slist(row.get("days")): out.append((True, "It has no day."))
    tm = row.get("times") if isinstance(row.get("times"), (list, tuple)) and len(row.get("times")) == 2 else [None, None]
    a, b = _clock_min(tm[0]), _clock_min(tm[1])
    if a is None or b is None: out.append((True, "Its From and To times are not times."))
    elif b <= a: out.append((True, "Its To time is not after its From time."))
    return out

def clock12(hhmm):
    """"15:00" -> "3.00": 12-hour, a dot, no am or pm"""
    m = _clock_min(hhmm)
    return "" if m is None else f"{(m // 60) % 12 or 12}.{m % 60:02d}"

def staff_items(spec):
    """one dict per row without a hard fault, per person, per day: the teacher-only period as it falls on one teacher's one weekday"""
    sc = (spec or {}).get("school") or {}
    try: st, pl, NP = _clock_min(str(sc.get("start_time"))), int(sc.get("period_minutes")), int(sc.get("periods_per_day"))
    except (TypeError, ValueError): return []
    if st is None or pl <= 0 or NP <= 0: return []
    out = []
    for i, row in enumerate(staff_rows(spec)):
        if any(h for h, _ in staff_faults(spec, row)): continue
        a, b = _clock_min(row["times"][0]), _clock_min(row["times"][1])
        lo, hi = (a - st) // pl, -(-(b - st) // pl) - 1
        per = None if lo > NP - 1 or hi < 0 else (max(0, lo), min(NP - 1, hi))
        wk = row.get("week") if row.get("week") in ("Odd", "Even") else "Both"
        days = list(dict.fromkeys(_slist(row.get("days"))))
        for who in staff_people(spec, row):
            for d in days:
                out.append(dict(id=f"tp.{row.get('_id') or i}.{who}.{d}".replace(":", " "), row=i, name=row["name"].strip(), place=_sstr(row.get("place")).strip(),
                                teacher=who, week=wk, day=d, times=[row["times"][0].strip(), row["times"][1].strip()], minutes=(a, b), periods=per,
                                before=a < st, after=b > st + NP * pl))
    return out

def staff_blocks(spec):
    """the 'Not available' Must rows (marked with staff=name) that the teacher-only periods stand for in the grid"""
    return [dict(scope="Teacher", target=x["teacher"], rule="Not available", week=x["week"], day=x["day"], strength="Must", note=x["name"], times=x["times"],
                 staff=x["name"], place=x["place"], _id=x["id"], **{"from": x["periods"][0], "to": x["periods"][1]}) for x in staff_items(spec) if x["periods"]]

def plain_rules(spec):
    """spec['rules'] without the rows that stand for teacher-only periods (those with a staff key)"""
    v = (spec or {}).get("rules")
    return [r for r in v if not (isinstance(r, dict) and "staff" in r)] if isinstance(v, list) else []

def rules_with_staff(spec):
    """the plain rules and then the teacher-only blocks; the same list whether or not the blocks are already in spec['rules']"""
    return plain_rules(spec) + staff_blocks(spec)

def staff_day_indexes(days, item):
    """the indexes of day names ('Odd Mon' ... or 'Mon' ...) that an item or block with week and day falls on (as verify.rule_days, for one weekday)"""
    wk, dy = str(item.get("week") or "Both"), str(item.get("day") or "")
    return [i for i, d in enumerate(days) if not (wk in ("Odd", "Even") and not d.startswith(wk)) and (d.split() or [""])[-1][:3] == dy[:3]]

def staff_days_text(week, days):
    """'Tue and Thu', 'Odd Mon', 'Even Mon, Wed and Fri'"""
    ds = list(days or [])
    txt = ds[0] if len(ds) == 1 else (", ".join(ds[:-1]) + " and " + ds[-1] if ds else "")
    return f"{week} {txt}" if week in ("Odd", "Even") else txt

def staff_legend_line(x):
    """the legend line: name · week and days · from to to · place (no last part without a place)"""
    tm = x.get("times") if isinstance(x.get("times"), (list, tuple)) and len(x.get("times")) == 2 else [None, None]
    days = _slist(x["days"]) if "days" in x else _slist([x.get("day")])
    parts = [_sstr(x.get("name")), staff_days_text(x.get("week"), days)]
    if clock12(tm[0]) and clock12(tm[1]): parts.append(f"{clock12(tm[0])} to {clock12(tm[1])}")
    parts = [q for q in parts if q]
    if _sstr(x.get("place")).strip(): parts.append(x["place"].strip())
    return " · ".join(parts)

def typed_rules(spec):
    """[(number, index, rule)] for every rule row in words, numbered 1, 2, 3... in spec['rules'] order"""
    out, n = [], 0
    for i, r in enumerate(spec.get("rules", []) or []):
        if isinstance(r, dict) and r.get("rule") == TYPED:
            n += 1; out.append((n, i, r))
    return out

def typed_label(number, r):
    """'T1 · Must · Sec 1 · No PE in the first period' (a blank target is left out)"""
    parts = [f"T{number}", str(r.get("strength") or "Must")]
    if str(r.get("target") or "").strip(): parts.append(str(r.get("target")).strip())
    parts.append(str(r.get("text") or "").strip())
    return " · ".join(parts)

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
EVERY_CLASS = "Every class"   # Fixed lessons: that lesson of every class of the level (or of the school, Level All)
ALL_LEVELS = ("all", "all levels", "every level", "whole school")   # 'Level · All' in a workbook: the whole school

def is_fixed_lesson(r):
    """a 'Fixed at' rule that belongs on Fixed lessons: a class, a group, or every class of a level or the school (with a
    subject; one without is flagged and skipped)"""
    return r.get("scope") in ("Class", "Group", "Level", "School")

def clean_name(v):
    """a name as typed, with runs of spaces made one and the ends trimmed"""
    return " ".join(str(v if v is not None else "").split())

def _made_of(v):
    """the distinct cleaned room names a venue row is made of, in the order listed; blank ones dropped, and a made_of that
    is not a list counts as empty (as the page's madeOf)"""
    out, mo = [], v.get("made_of") if isinstance(v, dict) else None
    for x in (mo if isinstance(mo, (list, tuple)) else []):
        x = clean_name(x)
        if x and x not in out: out.append(x)
    return out

def venue_parts(venues):
    """{combined venue: its rooms} for each venue row that is a sound combined venue: made of at least two distinct rooms,
    each another row's room, none of them a combined venue itself. Any other row is an ordinary room."""
    made = {clean_name(v.get("room")): _made_of(v) for v in venues if clean_name(v.get("room"))}
    out = {}
    for name, rooms in made.items():
        if len(rooms) >= 2 and all(r != name and r in made and not made[r] for r in rooms): out[name] = rooms
    return out

def clean_rooms(spec):
    """room names made clean in place (idempotent): venue rows and what they are made of, classes' home rooms, Room rules' targets"""
    for v in spec.get("venues") or []:
        if isinstance(v, dict):
            if "room" in v: v["room"] = clean_name(v["room"]) if v["room"] is not None else v["room"]
            if isinstance(v.get("made_of"), (list, tuple)): v["made_of"] = [x for x in map(clean_name, v["made_of"]) if x]
    for c in spec.get("classes") or []:
        if isinstance(c, dict) and c.get("home_room"): c["home_room"] = clean_name(c["home_room"])
    for r in spec.get("rules") or []:
        if isinstance(r, dict) and r.get("scope") == "Room" and r.get("target") is not None: r["target"] = clean_name(r["target"])
    return spec

def whole(v):
    """a positive whole number from a cell (20, "20", " 20 ", "20.0", 20.0 are 20); None for blank, text, zero, negative, booleans"""
    if isinstance(v, bool) or v is None: return None
    try: f = float(str(v).strip()); n = int(f)
    except (ValueError, OverflowError): return None
    return n if n > 0 and f == n else None

def single_rooms(name, parts):
    """the single rooms a venue stands for: its rooms when it is a combined venue, else itself"""
    return list(parts[name]) if name in parts else [name]

def venue_problems(spec):
    """what is wrong with the combined venues on step 1: [(venue row index, text, critical)]"""
    venues = spec.get("venues") or []
    row = {}
    for v in venues: row.setdefault(clean_name(v.get("room")), v)
    made = {n: _made_of(v) for n, v in row.items()}
    claimed = {}   # room -> the combined venues (in row order) that list it
    out = []
    for i, v in enumerate(venues):
        name = clean_name(v.get("room")); rooms = _made_of(v)
        if not rooms: continue
        if len(rooms) < 2: out.append((i, f"{name}: a combined venue needs at least two rooms.", True))
        for r in rooms:
            if r not in row: out.append((i, f"{name}: made of {r}, which is not on step 1 (Venues).", True))
            elif made.get(r): out.append((i, f"{name}: made of {r}, which is a combined venue itself.", True))
        for r in rooms:
            if r in claimed and name not in claimed[r]:
                out.append((i, f"{r} is in more than one combined venue ({', '.join(claimed[r] + [name])}): a room can be in one only.", True))
            claimed.setdefault(r, [])
            if name not in claimed[r]: claimed[r].append(name)
        found = [r for r in rooms if r in row]
        kinds = sorted({str(x.get("kind") or "classroom") for x in [v] + [row[r] for r in found]})
        if len(kinds) > 1: out.append((i, f"{name}: it and its rooms are of different kinds ({', '.join(kinds)}); they must all be one kind.", True))
        for r in rooms + [name]:
            for ru in spec.get("rules") or []:
                if ru.get("scope") == "Room" and clean_name(ru.get("target")) == r and ru.get("rule") == "At most N at once" \
                        and str(ru.get("strength") or "Must") == "Must":
                    try: k = int(ru.get("number"))
                    except (TypeError, ValueError): continue
                    if k > 1: out.append((i, f'{name}: {r} takes {k} groups at once (an "At most N at once" rule); a combined venue and its rooms take one group at a time.', True))
        def seats(x):
            try: return int(x.get("capacity"))
            except (TypeError, ValueError): return None
        mine = seats(v)
        if not mine: out.append((i, f"{name}: give its seats (seats decide which groups get it).", False))
        elif len(found) == len(rooms) and all(seats(row[r]) for r in found):
            total = sum(seats(row[r]) for r in found)
            if mine > total * 1.1: out.append((i, f"{name}: {mine} seats, but its rooms seat {total} together.", False))
    return out

def names_list(v):
    """a cell that names several things (subjects, venues), separated by commas, as a list"""
    if isinstance(v, (list, tuple)): return [str(x).strip() for x in v if str(x).strip()]
    return [x.strip() for x in str(v or "").split(",") if x.strip()]

def untag(s):
    """a subject without its level tag: 'English Language G3' -> 'English Language'"""
    import re
    return re.sub(r"\s+(G[123]|Std|Fdn|Standard|Foundation)$", "", str(s or "").strip())

def subject_test(names):
    """for 'Only these subjects': is a lesson (subject, department) one of these names? A name matches the subject, the
    subject without its G1/G2/G3 tag, or its department code"""
    want = {str(n).strip().lower() for n in names_list(names)}
    return lambda subject, dept=None: bool({str(subject or "").lower(), untag(subject).lower(), str(dept or "").lower()} & want)



DOUBLE = "Teachers may take two lessons at once on"   # a Settings row: the days a teacher in two lessons is allowed (a self-directed or home-based learning day)
DOUBLE_NOTE = ("Days when a teacher may be in two lessons at once, such as a self-directed or home-based learning day: the day names as on "
               "Day structure, separated by commas (Even Fri), or a weekday for every week (Fri). Empty: never.")
def _day_words(s): return tuple(w[:3] for w in str(s or "").lower().split())
def double_tokens(school):
    """the day names typed on the Settings row 'Teachers may take two lessons at once on'"""
    import re
    for row in school.get("extra_settings") or []:
        if str(row[0] or "").strip().lower().startswith(DOUBLE.lower()): return [t.strip() for t in re.split(r"[,;]", str(row[1] if len(row) > 1 and row[1] is not None else "")) if t.strip()]
    return []
def double_days(school, days):
    """the days (indices of days) on which a teacher may be in two lessons at once: a name as on Day structure ('Even Fri',
    'Even Friday'), or a weekday alone for that weekday of every week ('Fri')"""
    want = [_day_words(t) for t in double_tokens(school)]
    return {i for i, d in enumerate(days) if any(w and (w == _day_words(d) or (len(w) == 1 and w[0] == _day_words(d)[-1:][0])) for w in want)}

def filled_lessons(rows):
    """the lesson rows that name a subject, each with the fields a row read from the workbook always has. A row added in the
    editor and not filled in yet is saved with no subject, and may have no level, classes or teachers either; the workbook
    leaves such a row out, so a setup given as it is in the editor is read the same way. A teacher box emptied in the editor
    stays in the row's list as an empty place (["Mdm Lee", None]); the workbook leaves an empty cell out, so it is left out here
    (in the copy: the rows given are not changed)"""
    named = lambda v: [t for t in v if t is not None and str(t).strip()] if isinstance(v, list) else []
    return [{"level": None, "block": None, "classes": [], **x, "teachers": named(x.get("teachers"))} for x in rows or [] if isinstance(x, dict) and str(x.get("subject") or "").strip()]

def renamed_teachers(spec):
    """{earlier name: name now} from the teachers' earlier_names (a teacher renamed on step 4 keeps the names the row had
    before). A name is matched exactly. Left out: a row that is not a dict or has no name; an earlier_names that is not a
    list; an entry that is not a non-blank string; an earlier name that is a teacher's name now; one two rows claim"""
    rows = (spec or {}).get("teachers") if isinstance(spec, dict) else None
    rows = [t for t in (rows if isinstance(rows, list) else []) if isinstance(t, dict) and isinstance(t.get("name"), str) and t["name"].strip()]
    now = {t["name"] for t in rows}
    claims = {}
    for t in rows:
        e = t.get("earlier_names")
        for n in e if isinstance(e, list) else ():
            if isinstance(n, str) and n.strip() and n not in now and t["name"] not in claims.get(n, ()): claims.setdefault(n, []).append(t["name"])
    return {n: v[0] for n, v in claims.items() if len(v) == 1}

def renamed(names, m):
    """the names with each earlier name read as the name now (by m from renamed_teachers); a name met twice is kept once, in its first place"""
    out = []
    for n in names:
        v = m.get(n, n) if isinstance(n, str) else n
        if not (isinstance(v, str) and v in out): out.append(v)
    return out

def end_rows(school):
    """'Lessons end by (Monday to Thursday)' rows on Settings -> [(label, weekdays, minutes after midnight)]"""
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
        if h.strip().isdigit() and (m[:2] or "0").isdigit(): out.append((label, set(days), int(h) * 60 + int(m[:2] or 0)))   # not a time: ignored (the editor flags it)
    return out

def end_by(school):
    """'Lessons end by (...)' rows -> [(weekdays, minutes after midnight)]: no lesson runs past that time on those days
    (the Day structure holds the longest possible day; these trim it)"""
    return [(days, cut) for _, days, cut in end_rows(school)]

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

def ampm(minutes):
    """minutes after midnight -> '12.40pm'"""
    h, m = divmod(int(minutes), 60)
    return f"{(h - 1) % 12 + 1}.{m:02d}{'am' if h % 24 < 12 else 'pm'}"

def _listing(items, n=4):
    items = list(items)
    return ", ".join(items[:n]) + (f" and {len(items) - n} more" if len(items) > n else "")

def structure_vs_rules(spec):
    """places where the Day structure and the rules (rule rows on Settings, Fixed lessons) say different things, as
    warnings. The rules win where they are stricter, so a solver that reads only the Day structure would differ."""
    sc = spec["school"]; ds = spec.get("day_structure") or {}; NP = int(sc["periods_per_day"]); pl = int(sc["period_minutes"])
    h, m = map(int, str(sc["start_time"]).split(":")[:2]); st = h * 60 + m
    levels = [lv for lv in sc.get("levels", []) if ds.get(lv)] or list(ds)
    days = list(next((d for d in ds.values() if d), {}))
    after = sc.get("after_school", True) is not False
    lesson = "LWA" if after else "LW"   # periods a lesson may use (W: a recess window, lesson time but for the recess)
    row = lambda lv, d: (ds.get(lv, {}).get(d) or "").ljust(NP, ".")[:NP]
    last = lambda r: max((p for p, ch in enumerate(r) if ch in lesson), default=-1)
    at = lambda p: ampm(st + p * pl)
    every = lambda lvs: "every level" if len(lvs) == len(levels) > 1 else ", ".join(lvs)
    out, end_at = [], {}   # end_at: day -> 'Lessons end by (Friday) (12.40pm)', for the fixed lessons below
    for label, weekdays, cut in end_rows(sc):
        keep = max(0, min(NP, (cut - st) // pl))
        covered = [d for d in days if str(d).split()[-1][:3] in weekdays]
        if not covered:
            out.append(f"{label} matches no day of the Day structure, so it changes nothing."); continue
        end_at.update({d: f"{label} ({ampm(cut)})" for d in covered})
        over, ends = {}, []
        for d in covered:
            for lv in levels:
                p = last(row(lv, d))
                if p < 0: continue
                ends.append(p)
                if p >= keep: over.setdefault(d, []).append((lv, p))
        if over:
            parts = [f"{d} ({every([lv for lv, _ in v])}, until {at(max(p for _, p in v) + 1)})" for d, v in over.items()]
            latest = at(max(p for v in over.values() for _, p in v) + 1)
            out.append(f"{label} is {ampm(cut)}, but the Day structure has lessons after it on {_listing(parts)}. The time wins, so those periods stay empty: "
                       f"end the Day structure at {ampm(cut)} on those days, or set the time to {latest}.")
        elif ends and max(ends) + 1 < keep:
            out.append(f"{label} is {ampm(cut)}, but the Day structure has no lesson after {at(max(ends) + 1)} on those days, so the time changes nothing: the Day structure decides.")
    if not after:
        withA = [d for d in days if any("A" in row(lv, d) for lv in levels)]
        if withA: out.append(f"After-school slot allowed when a class cannot fit is No, but the Day structure has after-school slots (A) on {_listing(withA)}: they are never used.")
    if any(r.get("rule") == "At least one recess a day" and r.get("scope") == "School" for r in spec.get("rules", [])):
        bare = [d for d in days if any(last(row(lv, d)) >= 0 for lv in levels) and not any(set("RW") & set(row(lv, d)) for lv in levels)]
        if bare: out.append(f"Every teacher gets at least one recess a day, but on {_listing(bare)} no level has a recess (R or W) in the Day structure, "
                            "so a teacher who teaches that day cannot have one.")
    keep_by = periods_by_day(sc, days)
    level_of = {c["class"]: c.get("level") for c in spec.get("classes", [])}
    level_of.update({str(x["code"]): x.get("level") for x in spec.get("lessons", []) if x.get("code") and x["code"] != "Entire Class"})
    for r in spec.get("rules", []):
        if r.get("rule") != "Fixed at" or r.get("from") in (None, ""): continue
        p, lv = int(r["from"]), r.get("level") or level_of.get(str(r.get("target")))
        if lv not in ds: continue
        wk, dy = str(r.get("week") or "Both"), str(r.get("day") or "All")
        for d in days:
            if (wk in ("Odd", "Even") and not str(d).startswith(wk)) or (dy != "All" and str(d).split()[-1][:3] != dy[:3]): continue
            ch = row(lv, d)[p] if 0 <= p < NP else "."
            if ch not in lesson: why = f"is {CODES.get(ch, 'not a lesson period').lower()} ({ch}) in the {lv} Day structure"
            elif p >= keep_by.get(d, NP): why = f"is after {end_at.get(d, 'the end time on Settings')}"
            else: continue
            what = " ".join(str(x) for x in (r.get("target"), r.get("subject")) if x)
            out.append(f"Fixed lesson {what} on {d} at period {p} ({at(p)}): that period {why}, so it can never be met."); break
    return out

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
    available' for a teacher), Fixed lessons (Must 'Fixed at' for a class, a group, or every class with a subject), or More
    rules (everything else)"""
    settings, availability, fixed, more = {}, [], [], []
    for r in plain_rules(spec):
        must = str(r.get("strength") or "Must") == "Must"
        key = next((s["key"] for s in SETTING_RULES if s["rule"] and r.get("rule") == s["rule"]["rule"] and r.get("scope") == s["rule"]["scope"]
                    and (r.get("scope") != "Department" or r.get("target") == s["rule"]["target"])), None)
        if key and must and key not in settings:
            settings[key] = r.get("number") if next(s for s in SETTING_RULES if s["key"] == key)["number"] else "Yes"
        elif r.get("rule") == "Not available" and r.get("scope") == "Teacher" and must and r.get("from") not in (None, ""): availability.append(r)
        elif r.get("rule") == "Fixed at" and is_fixed_lesson(r) and must and r.get("from") not in (None, ""): fixed.append(r)
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

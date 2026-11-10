"""The timetable as a SQLite database, for other systems to import, and read back as a timetable.

write_db(m, path) writes the export model (the same one the Excel, PDFs and HTML are drawn from, so all of them agree):

  meta            key/value: format, school, timetable, weeks, period length, day start, generated, solver status,
                  notes (JSON), and the whole setup (JSON) so the file alone is enough to rebuild every output
  days            id, name ("Odd Mon"), week ("Odd"/"Even"/""), weekday ("Mon"), day_index (0-based, cycle order)
  periods         period, starts, ends (clock times)
  day_structure   level, day, period, code (L lesson, R recess, U lunch, F flag/assembly, A after school, ...)
  classes         name, level, students, home_room
  teachers        name, short, department, allowance, other_duties
  rooms           name, kind, capacity
  subjects        name, short, department
  lessons         one row per group per lesson: id, lesson_id (shared by a band's groups meeting together), day, week,
                  weekday, day_index, start_period, end_period, periods, starts, ends, level, block, subject, group_code
                  ("Entire Class" for a whole-class lesson), room, after_school (0/1), rain_room, classes, teachers
                  (comma-separated, also in the two link tables)
  lesson_classes  lesson -> class_name;   lesson_teachers  lesson -> teacher
  students        id, name, class_name, level (only when the setup has a student list);  student_groups  student -> group_code
  recess          class_name, day, start_period, periods (a class's floating recess, when the school uses recess windows)
  views           class_timetable, teacher_timetable, room_timetable (ordered, ready to read)

read_db(path) gives the lessons back in the hand-over format (the Lessons sheet's columns), so model_from_files reads a
database exactly as it reads a timetable workbook. It also reads a database made by another tool, as long as it has a
`lessons` table with day, start_period, periods (or end_period), subject and classes columns.
"""
import json, os, sqlite3

FORMAT = "ttgen-timetable-db 1"
DB_SUFFIXES = (".sqlite", ".sqlite3", ".db")
MEANING = {"L": "lesson", "R": "recess", "U": "lunch", "F": "flag / assembly", "A": "after school", "W": "recess window", "C": "class period"}


def is_db(path):
    if str(path).lower().endswith(DB_SUFFIXES): return True
    try:
        with open(path, "rb") as f: return f.read(16) == b"SQLite format 3\x00"
    except OSError: return False


def _split_day(name):
    parts = str(name).split()
    return (parts[0], " ".join(parts[1:])) if len(parts) > 1 and parts[0] in ("Odd", "Even") else ("", str(name))


def write_db(m, path, spec=None):
    """the export model m as a SQLite file at path (replaced if it exists); spec: the setup, kept in meta"""
    if os.path.exists(path): os.remove(path)
    spec = spec if spec is not None else m.get("setup")
    times, days = m["times"], m["days"]
    con = sqlite3.connect(path)
    try:
        q = con.execute
        q("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
        sc = m["school"]
        meta = dict(format=FORMAT, school=sc.get("name"), timetable=sc.get("timetable"), weeks=sc.get("weeks"), period_minutes=sc.get("period_minutes"),
                    day_starts=sc.get("start_time"), generated=m.get("generated"), solver_status=m.get("status") or "", notes=json.dumps(m.get("notes") or []),
                    checks=json.dumps({k: m["checks"].get(k) for k in ("ok", "problems", "lessons") if k in (m.get("checks") or {})}, default=str))
        if spec is not None: meta["setup"] = json.dumps(spec, default=str)
        con.executemany("INSERT INTO meta VALUES (?, ?)", [(k, "" if v is None else str(v)) for k, v in meta.items()])
        q("CREATE TABLE rule_report (no INTEGER, strength TEXT, applies TEXT, rule TEXT, result TEXT, how TEXT)")   # the agent's answer per typed rule
        con.executemany("INSERT INTO rule_report VALUES (?, ?, ?, ?, ?, ?)",
                        [(r.get("no"), r.get("strength") or "", r.get("applies") or "", r.get("rule") or "", r.get("result") or "", r.get("how") or "") for r in (m.get("rule_report") or [])])
        q("CREATE TABLE choices_used (no INTEGER, item TEXT, used TEXT, how TEXT)")   # which choices the agent gave way on
        con.executemany("INSERT INTO choices_used VALUES (?, ?, ?, ?)",
                        [(r.get("no"), r.get("item") or "", r.get("used") or "", r.get("how") or "") for r in (m.get("choices_used") or [])])

        q("CREATE TABLE days (id INTEGER PRIMARY KEY, name TEXT UNIQUE, week TEXT, weekday TEXT, day_index INTEGER)")
        con.executemany("INSERT INTO days VALUES (?, ?, ?, ?, ?)", [(i + 1, d, *_split_day(d), i) for i, d in enumerate(days)])
        q("CREATE TABLE periods (period INTEGER PRIMARY KEY, starts TEXT, ends TEXT)")
        con.executemany("INSERT INTO periods VALUES (?, ?, ?)", [(p, a, b) for p, (a, b) in enumerate(times)])
        q("CREATE TABLE day_structure (level TEXT, day TEXT, period INTEGER, code TEXT, meaning TEXT, PRIMARY KEY (level, day, period))")
        con.executemany("INSERT INTO day_structure VALUES (?, ?, ?, ?, ?)",
                        [(lv, days[d], p, ch, MEANING.get(ch, ch)) for lv, rows in m["grid"].items() for d, row in enumerate(rows) for p, ch in enumerate(row) if ch not in (".", " ")])

        q("CREATE TABLE classes (name TEXT PRIMARY KEY, level TEXT, students INTEGER, home_room TEXT)")
        con.executemany("INSERT INTO classes VALUES (?, ?, ?, ?)", [(c["name"], c["level"], c["size"] or None, c["home"] or None) for c in m["classes"]])
        q("CREATE TABLE teachers (name TEXT PRIMARY KEY, short TEXT, department TEXT, allowance INTEGER, other_duties INTEGER)")
        con.executemany("INSERT INTO teachers VALUES (?, ?, ?, ?, ?)", [(t["name"], t["short"], t["dept"] or None, t["allowance"] or None, t.get("other") or None) for t in m["teachers"]])
        q("CREATE TABLE rooms (name TEXT PRIMARY KEY, kind TEXT, capacity INTEGER)")
        con.executemany("INSERT INTO rooms VALUES (?, ?, ?)", [(r["name"], r["kind"], r["capacity"] or None) for r in m["rooms"]])
        q("CREATE TABLE subjects (name TEXT PRIMARY KEY, short TEXT, department TEXT)")
        con.executemany("INSERT INTO subjects VALUES (?, ?, ?)", [(k, v["short"], v["dept"] or None) for k, v in m["subjects"].items()])

        q("""CREATE TABLE lessons (id INTEGER PRIMARY KEY, lesson_id INTEGER, day TEXT, week TEXT, weekday TEXT, day_index INTEGER,
               start_period INTEGER, end_period INTEGER, periods INTEGER, starts TEXT, ends TEXT, level TEXT, block TEXT, subject TEXT,
               group_code TEXT, room TEXT, after_school INTEGER, rain_room TEXT, classes TEXT, teachers TEXT)""")
        q("CREATE TABLE lesson_classes (lesson INTEGER REFERENCES lessons(id), class_name TEXT)")
        q("CREATE TABLE lesson_teachers (lesson INTEGER REFERENCES lessons(id), teacher TEXT)")
        order = sorted(m["lessons"], key=lambda L: (L["d"], L["p"], L["level"], L["block"], L["subject"], L["group"]))
        for i, L in enumerate(order, 1):
            d, p, n = L["d"], L["p"], L["n"]; week, wd = _split_day(days[d])
            q("INSERT INTO lessons VALUES (?" + ", ?" * 19 + ")",
              (i, L["id"], days[d], week, wd, d, p, p + n - 1, n, times[p][0], times[min(p + n - 1, len(times) - 1)][1], L["level"], L["block"] or None,
               L["subject"], L["group"], L["room"] or None, int(bool(L.get("ext"))), L.get("rain") or None, ", ".join(L["classes"]), ", ".join(L["teachers"])))
            con.executemany("INSERT INTO lesson_classes VALUES (?, ?)", [(i, c) for c in L["classes"]])
            con.executemany("INSERT INTO lesson_teachers VALUES (?, ?)", [(i, t) for t in L["teachers"]])

        if m.get("students"):
            q("CREATE TABLE students (id TEXT PRIMARY KEY, name TEXT, class_name TEXT, level TEXT)")
            q("CREATE TABLE student_groups (student TEXT REFERENCES students(id), group_code TEXT)")
            seen = set()
            for s in m["students"]:
                if s["id"] in seen: continue
                seen.add(s["id"]); q("INSERT INTO students VALUES (?, ?, ?, ?)", (s["id"], s["name"], s["cls"], s["level"] or None))
                con.executemany("INSERT INTO student_groups VALUES (?, ?)", [(s["id"], g) for g in s["groups"]])
        if m.get("recess"):
            q("CREATE TABLE recess (class_name TEXT, day TEXT, start_period INTEGER, periods INTEGER)")
            con.executemany("INSERT INTO recess VALUES (?, ?, ?, ?)", [(c, days[d], p, n) for c, v in m["recess"].items() for d, p, n in v])

        q("CREATE INDEX ix_lessons_time ON lessons(day_index, start_period)")
        q("CREATE INDEX ix_lc ON lesson_classes(class_name)"); q("CREATE INDEX ix_lt ON lesson_teachers(teacher)")
        cols = "l.day, l.starts, l.ends, l.subject, l.group_code"
        q(f"CREATE VIEW class_timetable AS SELECT lc.class_name, {cols}, l.teachers, l.room FROM lessons l JOIN lesson_classes lc ON lc.lesson = l.id ORDER BY lc.class_name, l.day_index, l.start_period")
        q(f"CREATE VIEW teacher_timetable AS SELECT lt.teacher, {cols}, l.classes, l.room FROM lessons l JOIN lesson_teachers lt ON lt.lesson = l.id ORDER BY lt.teacher, l.day_index, l.start_period")
        q(f"CREATE VIEW room_timetable AS SELECT l.room, {cols}, l.classes, l.teachers FROM lessons l WHERE l.room IS NOT NULL ORDER BY l.room, l.day_index, l.start_period")
        con.commit()
    finally:
        con.close()
    return path


HANDOVER = ["Lesson ID", "Day", "Start period", "End period", "Periods", "Level", "Block", "Classes", "Subject", "Group", "Teachers", "Room", "After school", "Rain room"]


def read_db(path):
    """(header, rows, notes, status, recess, spec, rule_report, choices_used) with rows in the hand-over format. spec is the setup kept in the file
    (None if it has none, such as a database made by another tool); recess is {class: [[day name, period, length]]}."""
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type IN ('table', 'view')")}
        if "lessons" not in tables: raise ValueError("The database has no lessons table.")
        cols = [r[1] for r in con.execute("PRAGMA table_info(lessons)")]
        need = {"day", "start_period", "subject", "classes"}
        if need - set(cols) or not ({"periods", "end_period"} & set(cols)):
            raise ValueError(f"The database's lessons table needs the columns day, start_period, periods (or end_period), subject and classes; it has {', '.join(cols)}.")
        get = lambda r, k, d=None: r[k] if k in r.keys() and r[k] is not None else d
        con.row_factory = sqlite3.Row
        rows = []
        for r in con.execute("SELECT * FROM lessons ORDER BY " + ("id" if "id" in cols else "rowid")):
            p = int(get(r, "start_period")); n = get(r, "periods"); n = int(n) if n is not None else int(get(r, "end_period", p)) - p + 1
            ext = get(r, "after_school", "")
            rows.append((get(r, "lesson_id"), get(r, "day"), p, p + n - 1, n, get(r, "level", ""), get(r, "block", ""), get(r, "classes", ""),
                         get(r, "subject", ""), get(r, "group_code", get(r, "group", "")) or "Entire Class", get(r, "teachers", ""), get(r, "room", ""),
                         "yes" if str(ext).strip().lower() in ("1", "yes", "y", "true", "x") else "", get(r, "rain_room", "")))
        meta = {k: v for k, v in con.execute("SELECT key, value FROM meta")} if "meta" in tables else {}
        try: notes = json.loads(meta.get("notes") or "[]")
        except ValueError: notes = []
        try: spec = json.loads(meta["setup"]) if meta.get("setup") else None
        except ValueError: spec = None
        recess = {}
        if "recess" in tables:
            for c, d, p, n in con.execute("SELECT class_name, day, start_period, periods FROM recess"): recess.setdefault(str(c), []).append([d, int(p), int(n or 1)])
        report = []
        if "rule_report" in tables:
            for r in con.execute("SELECT * FROM rule_report ORDER BY rowid"):
                report.append(dict(no=get(r, "no"), strength=get(r, "strength", ""), applies=get(r, "applies", ""), rule=get(r, "rule", ""), result=get(r, "result", ""), how=get(r, "how", "")))
        used = []
        if "choices_used" in tables:
            for r in con.execute("SELECT * FROM choices_used ORDER BY rowid"):
                used.append(dict(no=get(r, "no"), item=get(r, "item", ""), used=get(r, "used", ""), how=get(r, "how", "")))
        return HANDOVER, rows, notes, meta.get("solver_status") or None, recess, spec, report, used
    finally:
        con.close()

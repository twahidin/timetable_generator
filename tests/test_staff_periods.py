"""Plain-assert tests for teacher-only periods: run with .venv/bin/python tests/test_staff_periods.py"""
import copy, json, os, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, ROOT)
from ttgen import spec as S, reader, template, solver, export  # noqa: E402,F401
from ttgen.samples import secondary  # noqa: E402
n = 0
def t(f): global n; f(); n += 1

def school():
    sp = secondary(); sp["school"].update(start_time="07:40", period_minutes=20, periods_per_day=26)
    sp["teachers"] = [dict(name="Mr Arjun Rao", dept="English", dept2=None), dict(name="Ms Mei Ling Koh", dept="Mathematics", dept2="English"),
                      dict(name="Mr Farhan Aziz", dept="Mathematics", dept2=None)]
    return sp
ZONE = dict(_id="z1", name="Zone computing class", all=False, depts=[], teachers=["Mr Arjun Rao", "Mr Farhan Aziz"], week="Both", days=["Tue", "Thu"], times=["15:00", "17:30"], place="West Zone centre")

@t
def people_by_name_department_and_all():
    sp = school()
    assert S.staff_people(sp, ZONE) == ["Mr Arjun Rao", "Mr Farhan Aziz"]
    assert S.staff_people(sp, dict(ZONE, teachers=[], depts=["English"])) == ["Mr Arjun Rao", "Ms Mei Ling Koh"]      # first and second department
    assert S.staff_people(sp, dict(ZONE, all=True, teachers=["Mr Arjun Rao"])) == [t_["name"] for t_ in sp["teachers"]]   # once each
    assert S.staff_people(sp, dict(ZONE, teachers=["Mr Gone", "Mr Arjun Rao"])) == ["Mr Arjun Rao"]

@t
def missing_or_broken_lists_are_empty():
    for v in ("absent", None, "x", [None, 3, "row"]):
        sp = school()
        if v != "absent": sp["staff_periods"] = v
        assert S.staff_rows(sp) == [] and S.staff_items(sp) == [] and S.staff_blocks(sp) == [] and S.rules_with_staff(sp) == S.plain_rules(sp)
    assert S.staff_items({}) == [] and S.staff_blocks(dict(rules=[])) == [] and S.rules_with_staff({}) == []     # a test fixture's setup may have no school at all

@t
def faults():
    sp = school(); f = lambda **k: S.staff_faults(sp, dict(ZONE, **k))
    assert f() == []
    assert f(name=" ") == [(True, "It has no name.")]
    assert f(teachers=[]) == [(True, "Nobody is in it.")]
    assert f(days=[]) == [(True, "It has no day.")]
    assert f(times=["15:00", "15:00"]) == [(True, "Its To time is not after its From time.")]
    assert f(times=["x", None]) == [(True, "Its From and To times are not times.")]
    assert f(times=["25:00", "26:00"]) == [(True, "Its From and To times are not times.")]
    assert f(teachers=["Mr Gone", "Mr Arjun Rao"]) == [(False, "Mr Gone is not on step 4.")]
    assert f(teachers=["Mr Gone"]) == [(False, "Mr Gone is not on step 4."), (True, "Nobody is in it.")]
    assert f(teachers=[], depts=["Science"]) == [(False, "Department Science has no teacher."), (True, "Nobody is in it.")]
    assert f(name="x" * 61) == [(True, "Its name is longer than 60 letters.")]
    assert f(place="x" * 61) == [(True, "Its place is longer than 60 letters.")]
    assert S.staff_faults(sp, {}) == [(True, "It has no name."), (True, "Nobody is in it."), (True, "It has no day."), (True, "Its From and To times are not times.")]

@t
def items_periods_and_edges():
    sp = school(); sp["staff_periods"] = [ZONE]; it = S.staff_items(sp)
    assert len(it) == 4 and [(x["teacher"], x["day"]) for x in it] == [("Mr Arjun Rao", "Tue"), ("Mr Arjun Rao", "Thu"), ("Mr Farhan Aziz", "Tue"), ("Mr Farhan Aziz", "Thu")]
    assert it[0]["periods"] == (22, 25) and it[0]["minutes"] == (900, 1050) and it[0]["after"] and not it[0]["before"]
    assert it[0]["id"] == "tp.z1.Mr Arjun Rao.Tue"
    one = lambda a, b: S.staff_items(dict(sp, staff_periods=[dict(ZONE, times=[a, b])]))[0]
    assert one("07:00", "07:30")["periods"] is None and one("07:00", "07:30")["before"]                 # wholly before the day
    assert one("16:20", "17:00")["periods"] is None and one("16:20", "17:00")["after"]                  # wholly after
    assert one("07:15", "08:00")["periods"] == (0, 0) and one("07:15", "08:00")["before"]
    assert one("14:50", "15:10")["periods"] == (21, 22)                                                  # half periods count whole
    assert one("14:20", "15:20")["periods"] == (20, 22) and not one("14:20", "15:20")["after"]

@t
def blocks_are_must_not_available_rows():
    sp = school(); sp["staff_periods"] = [ZONE, dict(ZONE, _id="m1", name="Briefing", times=["07:00", "07:30"])]
    sp["rules"] = [dict(scope="Teacher", target="Mr Farhan Aziz", rule="Not available", week="Both", day="Mon", strength="Must", **{"from": 0, "to": 3})]
    b = S.staff_blocks(sp)
    assert len(b) == 4 and b[0] == dict(scope="Teacher", target="Mr Arjun Rao", rule="Not available", week="Both", day="Tue", strength="Must", note="Zone computing class",
                                        times=["15:00", "17:30"], staff="Zone computing class", place="West Zone centre", _id="tp.z1.Mr Arjun Rao.Tue", **{"from": 22, "to": 25})
    once = S.rules_with_staff(sp); assert len(once) == 5 and once[0] is sp["rules"][0]
    assert S.rules_with_staff(dict(sp, rules=once)) == once and S.plain_rules(dict(sp, rules=once)) == sp["rules"]
    assert S.split_rules(dict(sp, rules=once))["availability"] == sp["rules"]                            # marked rows never reach the Teacher availability sheet

@t
def odd_days_long_day_names_and_one_week():
    sp = school(); sp["staff_periods"] = [dict(ZONE, days=["Tues", "Thursday"])]
    assert [x["day"] for x in S.staff_items(sp)][:2] == ["Tues", "Thursday"]
    from ttgen.verify import rule_days
    days = S.day_names(2); blocks = S.staff_blocks(sp)
    assert rule_days(days, blocks[0]) == [1, 6] and rule_days(days, blocks[1]) == [3, 8]
    assert rule_days(S.day_names(1), dict(blocks[0], week="Odd")) == []
    assert S.staff_day_indexes(days, blocks[0]) == rule_days(days, blocks[0]) and S.staff_day_indexes(days, blocks[1]) == rule_days(days, blocks[1])
    assert S.staff_day_indexes(S.day_names(1), dict(blocks[0], week="Odd")) == rule_days(S.day_names(1), dict(blocks[0], week="Odd")) == []
    assert S.staff_day_indexes(S.day_names(1), blocks[0]) == [1]

@t
def odd_times_and_days_never_raise():
    sp = school(); NOT = [(True, "Its From and To times are not times.")]
    for bad in ("\u00b2:30", "\u0661\u0662:\u0663\u0660", "1:2", "12:3x"):
        row = dict(ZONE, times=[bad, "17:30"])
        assert S.staff_faults(sp, row) == NOT and S.staff_items(dict(sp, staff_periods=[row])) == [] and S.clock12(bad) == ""
    assert S.clock12(None) == "" and S.clock12(5) == ""
    for row in (dict(ZONE, times=["15:00"]), dict(ZONE, days="Tue"), dict(ZONE, days=[3, None]), dict(name="Solo")):
        assert S.staff_legend_line(row).startswith(row["name"])
    assert S.staff_legend_line(dict(ZONE, times=["15:00"])) == "Zone computing class · Tue and Thu · West Zone centre"
    assert S.staff_legend_line(dict(name="Solo")) == "Solo"
    assert S.staff_day_indexes(["Mon", ""], dict(week="Both", day="Mon")) == [0]
    assert S.staff_faults(sp, dict(ZONE, days=[" "])) == [(True, "It has no day.")]
    sp["staff_periods"] = [None, 3, ZONE]
    assert len(S.staff_items(sp)) == 4 and S.staff_items(sp)[0]["id"] == "tp.z1.Mr Arjun Rao.Tue"
    assert S.staff_people(sp, dict(ZONE, teachers=[" Mr Arjun Rao "])) == ["Mr Arjun Rao"]
    sp["teachers"][0]["name"] = "Mr A: Rao"
    assert S.staff_items(dict(sp, staff_periods=[dict(ZONE, teachers=["Mr A: Rao"])]))[0]["id"] == "tp.z1.Mr A  Rao.Tue"

@t
def words():
    assert [S.clock12(x) for x in ("15:00", "17:30", "07:40", "12:40", "00:05")] == ["3.00", "5.30", "7.40", "12.40", "12.05"]
    assert S.staff_days_text("Both", ["Tue", "Thu"]) == "Tue and Thu" and S.staff_days_text("Odd", ["Mon"]) == "Odd Mon"
    assert S.staff_days_text("Even", ["Mon", "Wed", "Fri"]) == "Even Mon, Wed and Fri"
    assert S.staff_legend_line(ZONE) == "Zone computing class · Tue and Thu · 3.00 to 5.30 · West Zone centre"
    assert S.staff_legend_line(dict(ZONE, place="")) == "Zone computing class · Tue and Thu · 3.00 to 5.30"

def round_trip(sp):
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f: path = f.name
    try: template.write_template(sp, path); return reader.read_template(path)
    finally: os.unlink(path)

@t
def the_workbook_keeps_every_shape_of_row():
    sp = secondary(); names = [x["name"] for x in sp["teachers"]][:2]; dept = sp["teachers"][0]["dept"]
    rows = [dict(name="Zone computing class", all=False, depts=[], teachers=names, week="Both", days=["Tue", "Thu"], times=["15:00", "17:30"], place="West Zone centre"),
            dict(name="Staff meeting", all=True, depts=[], teachers=[], week="Odd", days=["Mon"], times=["15:00", "16:20"], place="Hall"),
            dict(name="Department meeting", all=False, depts=[dept], teachers=names[:1], week="Even", days=["Wed"], times=["14:20", "15:20"], place=""),
            dict(name="", all=False, depts=[], teachers=[], week="Both", days=[], times=["15:00", "16:00"], place="")]            # a row just added on step 6
    sp["staff_periods"] = copy.deepcopy(rows)
    assert round_trip(sp)["staff_periods"] == rows
    assert round_trip(secondary())["staff_periods"] == []
    back = round_trip(sp); avail = [r for r in back["rules"] if r.get("rule") == "Not available" and r.get("scope") == "Teacher"]
    assert len(avail) == len([r for r in secondary()["rules"] if r.get("rule") == "Not available" and r.get("scope") == "Teacher"])   # not written to Teacher availability too

@t
def names_with_full_stops_and_apostrophes_survive_and_odd_times_do_not_raise():
    sp = secondary(); sp["teachers"][0]["name"] = "Mdm. Ng O'Neil"
    row = dict(name="Zone class", all=False, depts=[], teachers=["Mdm. Ng O'Neil"], week="Both", days=["Fri"], times=["15:00", "17:30"], place="")
    sp["staff_periods"] = [row]; assert round_trip(sp)["staff_periods"] == [row]
    sp["staff_periods"] = [dict(row, times=["x", None])]
    back = round_trip(sp)["staff_periods"]; assert len(back) == 1 and back[0]["name"] == "Zone class" and back[0]["teachers"] == ["Mdm. Ng O'Neil"]

@t
def a_derived_setup_writes_the_same_sheets_as_before_derive():
    sp = secondary(); t0 = sp["teachers"][0]["name"]
    sp["staff_periods"] = [dict(name="Zone computing class", all=False, depts=[], teachers=[t0], week="Both", days=["Tue"], times=["15:00", "17:30"], place="")]
    plain = round_trip(sp); d = copy.deepcopy(sp); reader.derive(d); back = round_trip(d)
    assert back["staff_periods"] == plain["staff_periods"] == S.staff_rows(sp)
    assert [r for r in back["rules"] if not r.get("staff")] == [r for r in plain["rules"] if not r.get("staff")] and not any(r.get("staff") for r in back["rules"])

@t
def derive_appends_the_block_outs_once():
    sp = secondary(); t0 = sp["teachers"][0]["name"]; before = len(sp["rules"])
    sp["staff_periods"] = [dict(name="Zone computing class", all=False, depts=[], teachers=[t0], week="Both", days=["Tue"], times=["15:00", "17:30"], place="")]
    reader.derive(sp); n1 = len(sp["rules"]); reader.derive(sp)
    assert n1 == len(sp["rules"]) == before + 1 and sp["rules"][-1]["staff"] == "Zone computing class" and sp["rules"][:before] == S.plain_rules(sp)
    assert not any(i >= before for i, _ in solver.rule_problems(sp))

@t
def the_solver_keeps_a_teachers_lessons_out():            # only with --full
    if "--full" not in sys.argv: return
    from ttgen import report
    sp = secondary(); who = next(x for x in sp["lessons"] if x.get("teachers"))["teachers"][0]
    sp["staff_periods"] = [dict(name="Zone computing class", all=False, depts=[], teachers=[who], week="Both", days=["Mon"], times=["07:40", "09:40"], place="")]
    res = solver.solve(copy.deepcopy(sp), time_limit=240, log=lambda *a: None); assert res["status"] in ("OPTIMAL", "FEASIBLE"), res["status"]
    report.assign_rooms(res)
    m = export.model_from_result(res); mon = [i for i, d in enumerate(m["days"]) if d.endswith("Mon")]
    assert [x for x in m["lessons"] if who in x["teachers"]] and not [x for x in m["lessons"] if who in x["teachers"] and x["d"] in mon and x["p"] < 6]

@t
def will_it_fit_and_the_database_know_the_list():
    from ttgen import checks, database
    sp = secondary(); who = next(x for x in sp["lessons"] if x.get("teachers"))["teachers"][0]
    fit = lambda s: [f["text"] for f in checks.findings(copy.deepcopy(s)) if f["text"].startswith(f"{who} teaches") and "no timetable can fit them" in f["text"]]
    assert not fit(sp)
    row = dict(name="Zone computing class", all=False, depts=[], teachers=[who], week="Both", days=["Mon", "Tue", "Wed", "Thu", "Fri"], times=["00:00", "23:59"], place="")
    sp["staff_periods"] = [row]
    assert len(fit(sp)) == 1, fit(sp)
    d = copy.deepcopy(sp); reader.derive(d); days = list(d["day_structure"][d["school"]["levels"][0]].keys())
    m = export._model(d, days, []); path = os.path.join(tempfile.mkdtemp(), "t.sqlite"); database.write_db(m, path)
    assert S.staff_rows(database.read_db(path)[5]) == [row]

@t
def the_skill_names_the_sheet_and_the_version():
    s = open(os.path.join(ROOT, "skill/school-timetable-generator/SKILL.md"), encoding="utf-8").read()
    assert S.SKILL_VERSION == "2026-11.12" and "Skill version: 2026-11.12" in s and "`Teacher-only periods`" in s
    assert "Teacher-only periods" in open(os.path.join(ROOT, "README.md"), encoding="utf-8").read()

# ---- Task 5: the teacher's timetable (page data, printout, Excel)
import openpyxl  # noqa: E402
def model_for(sp, placed):
    """a timetable model from hand-placed lessons: placed = [(day index, p, n, classes, subject, group, teachers, room)]
    (as tests/test_combined.py builds one; copied, because importing that file runs its tests)"""
    sp = copy.deepcopy(sp); reader.derive(sp); days = list(sp["day_structure"][sp["school"]["levels"][0]].keys())
    level = {c["class"]: c["level"] for c in sp["classes"]}
    L = [dict(id=i + 1, d=d, p=p, n=n_, level=level.get(cls[0], "") if cls else "", block="", classes=cls, subject=s, group=g, teachers=tt, room=r, ext=False, rain="")
         for i, (d, p, n_, cls, s, g, tt, r) in enumerate(placed)]
    m = export._model(sp, days, L); m.setdefault("checked_setup", sp); return m
def _sample():
    sp = secondary(); sp["school"].update(start_time="07:40", period_minutes=20, periods_per_day=26); return sp
sp0 = _sample()
_x = next(x for x in sp0["lessons"] if x.get("teachers") and x["classes"])
T, CLS, SUBJECT = _x["teachers"][0], _x["classes"][0], _x["subject"]
ROOM = next(v["room"] for v in sp0["venues"] if v["kind"] == "classroom")
SUBJECT_SHORT = export.abbrev(SUBJECT); TEACHER_SHEET = "Teachers"
_days0 = list(sp0["day_structure"][sp0["school"]["levels"][0]].keys()); TUE = next(i for i, d in enumerate(_days0) if d.endswith("Tue"))
PLACED = [(TUE, 22, 3, [CLS], SUBJECT, export.ENTIRE, [T], ROOM)]
ZONE5 = dict(_id="z5", name="Zone computing class", all=False, depts=[], teachers=[T], week="Both", days=["Tue", "Thu"], times=["15:00", "17:30"], place="West Zone centre")
BRIEF = dict(_id="b5", name="Briefing", all=False, depts=[], teachers=[T], week="Both", days=["Mon"], times=["07:00", "07:30"], place="")
sp_with_zone = dict(copy.deepcopy(sp0), staff_periods=[ZONE5]); sp_with_briefing = dict(copy.deepcopy(sp0), staff_periods=[BRIEF])
LINE = "Zone computing class · Tue and Thu · 3.00 to 5.30 · West Zone centre"

@t
def the_teachers_view_gets_the_box_and_the_line_and_no_new_counts():
    m0 = model_for(sp0, PLACED); m = model_for(sp_with_zone, PLACED)
    v0, v = export.teacher_view(m0, T), export.teacher_view(m, T)
    boxes = [c for c in v["cells"] if c.get("staff")]
    assert v["stats"] == v0["stats"] and v["subtitle"] == v0["subtitle"] and len(v["cells"]) == len(v0["cells"]) + len(boxes)
    assert len(boxes) == sum(1 for d in m["days"] if d.split()[-1] in ("Tue", "Thu")) and all((c["p"], c["n"], c["after"], c["before"]) == (22, 4, True, False) for c in boxes)
    assert boxes[0]["title"] == "Zone computing class" and boxes[0]["lines"] == ["3.00 (to 5.30)", "West Zone centre"] and boxes[0]["id"] is None
    assert [e["text"] for e in v["legend"] if e.get("staff")] == [LINE]
    assert [e for e in v["legend"] if not e.get("staff")] == v0["legend"]
    assert not any(c.get("staff") for c in export.class_view(m, CLS)["cells"]) and not any(c.get("staff") for c in export.room_view(m, ROOM)["cells"])
    assert [v_["key"] for v_ in export.all_views(m, "teachers")] == [v_["key"] for v_ in export.all_views(m0, "teachers")]      # a teacher with no lessons still has no page

@t
def the_time_words_and_old_models():
    m = model_for(sp_with_zone, PLACED)
    assert export.staff_cells(dict(m, setup={}), None) == [] and export.staff_lines(dict(m, setup={}), T) == []
    m_ = dict(m); m_.pop("setup"); assert export.staff_cells(m_) == [] and export.staff_lines(m_, T) == []
    plain = dict(ZONE5, times=["09:00", "10:20"], days=["Mon"])
    mm = model_for(dict(sp0, staff_periods=[plain]), PLACED); c = [c for c in export.teacher_view(mm, T)["cells"] if c.get("staff")][0]
    assert c["lines"][0] == "9.00–10.20" and not c["before"] and not c["after"], c
    mb = model_for(dict(sp0, staff_periods=[dict(plain, times=["07:00", "08:00"])]), PLACED); c = [c for c in export.teacher_view(mb, T)["cells"] if c.get("staff")][0]
    assert c["lines"][0] == "(from 7.00) 8.00" and c["before"] and not c["after"] and c["p"] == 0, c
    assert export.staff_cells(m, "Nobody") == [] and {x["teacher"] for x in export.staff_cells(m)} == {T}

@t
def a_period_wholly_outside_the_day_is_a_line_only():
    m = model_for(sp_with_briefing, PLACED)
    v = export.teacher_view(m, T)
    assert not [c for c in v["cells"] if c.get("staff")] and [e["text"] for e in v["legend"] if e.get("staff")] == ["Briefing · Mon · 7.00 to 7.30"]

@t
def the_page_data_by_view():
    m = model_for(sp_with_zone, PLACED)
    full = export.html_data(m, "full")
    assert [T, m["days"].index(next(d for d in m["days"] if d.endswith("Tue"))), 22, 4, "Zone computing class", "West Zone centre", "3.00", "5.30", False, True] in full["staff"]
    assert full["staff_lines"] == {T: [LINE]}
    for view in ("student", "staff"): assert export.html_data(m, view)["staff"] == [] and export.html_data(m, view)["staff_lines"] == {}
    sid = m["students"][0]["id"]; assert export.html_data(m, "personal", student_id=sid)["staff"] == []
    assert export.html_data(m, "personal", student_id=sid)["staff_lines"] == {}
    assert "Zone computing class" not in json.dumps(export.html_data(m, "student")) and "Zone computing class" not in json.dumps(export.html_data(m, "personal", student_id=sid))
    assert "Zone computing class" not in json.dumps(export.html_data(m, "staff"))

@t
def the_printout_and_the_excel_file_keep_the_lesson():
    m = model_for(sp_with_zone, PLACED)
    assert export.pdf_bytes(m, export.teacher_view(m, T))[:4] == b"%PDF"
    assert export.pdf_bytes(m, export.teacher_view(model_for(sp_with_briefing, PLACED), T))[:4] == b"%PDF"
    cs = export.teacher_view(m, T)["cells"]; lanes = export._lanes(cs)
    tue = [c for c in cs if c["d"] == TUE and c["p"] >= 22]
    assert len(tue) == 2 and {lanes[id(c)][1] for c in tue} == {2}             # they share the row, neither hides the other
    path = os.path.join(tempfile.mkdtemp(), "x.xlsx"); export.write_excel(m, path, log=lambda *a: None)
    ws = openpyxl.load_workbook(path)[TEACHER_SHEET]; text = " ".join(str(c.value) for row in ws.iter_rows() for c in row if c.value)
    assert "Zone computing class" in text and SUBJECT_SHORT in text and LINE in text
    assert f" / Zone computing class" in text, "the lesson's cell gains the period's name"
    cs_ = [c for row in ws.iter_rows() for c in row if c.value and " / Zone computing class" in str(c.value)]
    assert cs_ and all(c.fill.fgColor.rgb != "00FFFFFF" for c in cs_)          # it keeps the lesson's own fill

# tests are added above this line by each task
if __name__ == "__main__": print(f"{n} checks passed")

"""Plain-assert tests for the timetable look (the published page and the PDFs): run with .venv/bin/python tests/test_look.py"""
import copy, os, re, sys
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

def the_lunch_days_are_pinned():
    assert LUNCH_DAYS == 2
t(the_lunch_days_are_pinned)

def a_lesson_is_placed_by_the_clock():
    assert export._clk(780) == "1.00" and export._clk(480) == "8.00" and export._clk(0) == "12.00" and export._clk(1230) == "8.30"
    m = school(); v = export.class_view(m, CLASS); st = export._mins(m, 0)
    assert st == 450 and export._mins(m, m["NP"]) == 450 + 26 * 20
    c = next(x for x in v["cells"] if x["d"] == 0 and x["p"] == 1)
    assert (c["a"] - st, c["b"] - st) == (20, 80) and (c["a"], c["b"]) == (470, 530)
    assert all("a" in x and "b" in x and x["b"] > x["a"] for x in v["cells"])
    for view in (export.teacher_view(m, TEACHER), export.room_view(m, ROOM), export.student_view(m, m["students"][0])):
        assert view["cells"] and all(x["b"] - x["a"] == 20 * x["n"] for x in view["cells"])
t(a_lesson_is_placed_by_the_clock)

def bands_and_span_follow_the_page():
    m = school(); v = export.class_view(m, CLASS); row = m["grid"][m["class_ix"][CLASS]["level"]]
    lunch = [d for d in range(m["ND"]) if "U" in row[d]]
    names = {d: [b[2] for b in export._bands(m, v, d)] for d in range(m["ND"])}
    assert sum("Lunch" in names[d] for d in range(m["ND"])) == LUNCH_DAYS and any("Lunch" in names[d] for d in lunch)
    assert names[4] == [] and not any(x["d"] == 4 for x in v["cells"])                      # a day with no lessons
    thu = [d for d in range(m["ND"]) if d not in (0, 5) and any(x["d"] == d for x in v["cells"]) and "Lunch" not in names[d]]
    assert thu and all(a < b for d in range(m["ND"]) for a, b, _ in export._bands(m, v, d))
    a0, b1 = export._span(m, v)
    starts = [x["a"] for x in v["cells"]] + [b[0] for d in range(m["ND"]) for b in export._bands(m, v, d)]
    assert a0 == min(starts) and b1 == max(x["b"] for x in v["cells"])
    assert export._span(m, dict(v, cells=[])) is None
    m2 = copy.deepcopy(m); m2["school"]["period_minutes"] = 35; m2["school"]["start_time"] = "07:30"
    v2 = export.class_view(m2, CLASS); h = export._hours(*export._span(m2, v2))
    assert h[0] == (480, "8 am"), h
t(bands_and_span_follow_the_page)

def hour_marks_read_as_the_school_writes_them():
    assert export._hours(460, 800) == [(480, "8 am"), (540, "9"), (600, "10"), (660, "11"), (720, "12 noon"), (780, "1 pm")]
    assert export._hours(790, 900) == [(840, "2 pm"), (900, "3")]
    assert export._hours(700, 760) == [(720, "12 noon")] and export._hours(780, 800) == [(780, "1 pm")]
t(hour_marks_read_as_the_school_writes_them)

def lanes_judge_overlap_by_the_clock():
    mk = lambda a, b: dict(d=0, p=0, n=1, a=a, b=b)
    x, y, z = mk(480, 540), mk(500, 560), mk(560, 600)      # p and n say the same for all three: only a and b tell them apart
    L = export._lanes([x, y, z])
    assert L[id(x)] == [0, 2] and L[id(y)] == [1, 2] and L[id(z)] == [0, 1]
t(lanes_judge_overlap_by_the_clock)

def a_box_draws_what_fits():
    m = school(); c = dict(export.class_view(m, CLASS)["cells"][0])
    L = export._box_lines(c, 84, 38)
    assert len(L) == 3 and "–" in L[0][0] and L[0][0][0].isdigit() and " · " in L[2][0] and L[1][0] == c["title"]
    assert L[0][3] == export.SUB and L[1][3] == export.INK
    assert export._box_lines(c, 20, 38)[0][0] == export._clk(c["a"])
    assert len(export._box_lines(c, 84, 25)) == 3
    assert len(export._box_lines(c, 84, 12)) == 1
t(a_box_draws_what_fits)

def the_printout_has_its_own_words_and_the_excel_words_stay():
    m = school(); v = export.class_view(m, CLASS)
    assert "students" not in v["print_subtitle"] and "students" in v["pdf_subtitle"] and "home room" in v["print_subtitle"]
    tv = export.teacher_view(m, TEACHER)
    assert "after-school" in tv["pdf_subtitle"] and "after-school" not in tv["print_subtitle"]
    for view in (v, tv, export.room_view(m, ROOM), export.student_view(m, m["students"][0])):
        assert view["legend"] and all("periods" not in e["plain"] and "periods" in e["text"] for e in view["legend"]), view["kind"]
    assert "print_subtitle" not in export.custom_view(m, CLASS, [])
t(the_printout_has_its_own_words_and_the_excel_words_stay)

def a_box_tries_each_fallback_in_turn():
    m = school(); c = dict(export.class_view(m, CLASS)["cells"][0])
    two = export._box_lines(c, 84, 20)                                          # three lines do not fit, time and title do at full size
    assert [x[0] for x in two] == [f"{export._clk(c['a'])}–{export._clk(c['b'])}", c["title"]] and (two[0][2], two[1][2]) == (6.2, 7.4), two
    one = export._box_lines(c, 84, 12)
    assert one == [(f"{export._clk(c['a'])} {c['title']}",) + one[0][1:]], one       # one line: the start only, then the title
    long_ = dict(c, title="A title far too long to share a line")
    assert [x[0] for x in export._box_lines(long_, 40, 12)] == [long_["title"]]       # start and title do not fit the width: the title alone
t(a_box_tries_each_fallback_in_turn)

def bands_read_any_codes_safely():
    m = school(); v = export.class_view(m, CLASS); NP = m["NP"]
    assert export._bands(m, dict(v, codes=None), 0) == []
    assert export._bands(m, dict(v, codes=[]), 0) == [] and export._bands(m, dict(v, codes=v["codes"][:1]), 3) == []   # no row for the day
    row = v["codes"][0]; u = row.index("U")
    assert export._bands(m, dict(v, codes=[row[:u]] + v["codes"][1:]), 0) and all(b[2] != "Lunch" for b in export._bands(m, dict(v, codes=[row[:u]] + v["codes"][1:]), 0))
    assert export._bands(m, dict(v, codes=[""] + v["codes"][1:]), 0) == []
    fr = "".join("F" if p < 2 else "R" if p in (4, 5) else "L" for p in range(NP))
    cell = dict(d=0, a=export._mins(m, 6), b=export._mins(m, 8))                         # starts exactly at recess's end
    got = export._bands(m, dict(codes=[fr], cells=[cell]), 0)
    assert got == [(export._mins(m, 0), export._mins(m, 2), "Assembly"), (export._mins(m, 4), export._mins(m, 6), "Recess")], got
    assert export._bands(m, dict(codes=[fr], cells=[dict(cell, a=export._mins(m, 5))]), 0) == [(export._mins(m, 0), export._mins(m, 2), "Assembly")]
t(bands_read_any_codes_safely)

class Rec:
    """a canvas that records each call as (name, args)"""
    def __init__(self): self.calls = []
    def __getattr__(self, name):
        def f(*a, **k): self.calls.append((name, a))
        return f

def the_printout_draws_the_clock_scale():
    m = school()
    def drawn(v): c = Rec(); export.draw_page(c, m, v); return c.calls
    def words(calls): return [str(a[-1]) for n_, a in calls if n_ in ("drawString", "drawCentredString", "drawRightString")]
    for v in [export.class_view(m, CLASS), export.teacher_view(m, TEACHER), export.room_view(m, ROOM), export.student_view(m, m["students"][0])]:
        w = words(drawn(v)); text = "\n".join(w)
        assert "after school" not in text and "periods" not in text and "students" not in text and "allowance" not in text, v["title"]
        assert not any(n_ == "setDash" and a and a[0] for n_, a in drawn(v)), "no dashed edge"
        assert "8 am" in w and "Striped bands are breaks." in w
        assert not any(w[i:i + 4] == ["0", "1", "2", "3"] for i in range(len(w))), "no period numbers"
    w = words(drawn(export.class_view(m, CLASS)))
    assert w.count("8 am") == 2 and "ODD WEEK" in w and "EVEN WEEK" in w            # an hour row above each week
    assert sum(x == "Lunch" for x in w) == LUNCH_DAYS                                # only on days with a lesson after lunch
    assert any(re.fullmatch(r"\d{1,2}\.\d\d–\d{1,2}\.\d\d", x) for x in w)          # a lesson's time
    empty = export.room_view(m, ROOM); empty = dict(empty, cells=[])
    w = words(drawn(empty)); assert "No lessons." in w and "8 am" not in w
t(the_printout_draws_the_clock_scale)

def every_printout_is_a_pdf():
    m = school()
    for kind in export.KINDS:
        for v in export.all_views(m, kind): assert export.pdf_bytes(m, v)[:4] == b"%PDF", v["title"]
    m2 = copy.deepcopy(m); m2["school"]["period_minutes"] = 35
    for v in (export.class_view(m2, CLASS), export.teacher_view(m2, TEACHER)): assert export.pdf_bytes(m2, v)[:4] == b"%PDF"
    one = copy.deepcopy(m); per = one["ND"] // one["school"]["weeks"]
    one["school"]["weeks"] = 1; one["ND"] = per; one["days"] = [export._week_day(d)[1] for d in one["days"][:per]]
    one["lessons"] = [x for x in one["lessons"] if x["d"] < per]
    v = export.class_view(one, CLASS); c = Rec(); export.draw_page(c, one, v)
    w = [str(a[-1]) for n_, a in c.calls if n_ in ("drawString", "drawCentredString", "drawRightString")]
    assert w.count("8 am") == 1 and not any("WEEK" in x for x in w), w
    assert export.pdf_bytes(one, v)[:4] == b"%PDF"
    assert export.pdf_bytes(m, dict(export.room_view(m, ROOM), cells=[]))[:4] == b"%PDF"
    assert export.pdf_bytes(m, export.custom_view(m, CLASS, []))[:4] == b"%PDF"
t(every_printout_is_a_pdf)

# tests are added above this line by each task
if __name__ == "__main__": print(f"{n} checks passed")

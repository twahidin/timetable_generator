"""Plain-assert tests for combined venues: run with .venv/bin/python tests/test_combined.py (add --full for the solve)"""
import collections, copy, os, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(HERE))
from ttgen import reader, template, spec as SPEC  # noqa: E402
from ttgen.samples import secondary  # noqa: E402
PAIR, S1, S2 = "D&T Studio 1&2", "D&T Studio 1", "D&T Studio 2"
n = 0
def t(f): global n; f(); n += 1

def pair_school(seats=40):
    """the sample school with 20-seat studios, the pair on top, and the two upper secondary D&T groups cut to 15 students"""
    sp = secondary()
    for v in sp["venues"]:
        if v["room"] in (S1, S2): v["capacity"] = 20
    sp["venues"].append(dict(room=PAIR, kind="d&t studio", capacity=seats, made_of=[S1, S2]))
    for code in ("3DTP1", "4DTP1"):
        for x in sp["lessons"]:
            if x.get("code") == code: x["students"] = 15
        have = [s for s in sp.get("students", []) if code in (s.get("groups") or [])]
        for s in have[15:]: s["groups"] = [g for g in s["groups"] if g != code]
    return sp

def model_for(sp, placed):
    """a timetable model from hand-placed lessons: placed = [(day index, p, n, classes, subject, group, teachers, room)]
    (as tests/test_verify.py builds one; copied, because importing that file runs its tests)"""
    from ttgen import export
    sp = copy.deepcopy(sp); reader.derive(sp); days = list(sp["day_structure"][sp["school"]["levels"][0]].keys())
    level = {c["class"]: c["level"] for c in sp["classes"]}
    L = [dict(id=i + 1, d=d, p=p, n=n_, level=level.get(cls[0], "") if cls else "", block="", classes=cls, subject=s, group=g, teachers=tt, room=r, ext=False, rain="")
         for i, (d, p, n_, cls, s, g, tt, r) in enumerate(placed)]
    m = export._model(sp, days, L); m.setdefault("checked_setup", sp); return m
def helpers():
    sp = pair_school()
    assert SPEC.clean_name("  D&T  Lab 1 ") == "D&T Lab 1"
    P = SPEC.venue_parts(sp["venues"]); assert P == {PAIR: [S1, S2]}
    assert SPEC.single_rooms(PAIR, P) == [S1, S2] and SPEC.single_rooms(S1, P) == [S1] and SPEC.single_rooms("Nowhere", P) == ["Nowhere"]
    assert SPEC.venue_parts(secondary()["venues"]) == {} and SPEC.venue_problems(secondary()) == [] and SPEC.venue_problems(sp) == []
t(helpers)

def broken_ones_are_ordinary_rooms_and_are_reported():
    def probs(change):
        sp = pair_school(); v = sp["venues"][-1]; change(sp, v); return sp, [(t_, hard) for _, t_, hard in SPEC.venue_problems(sp)]
    sp, p = probs(lambda sp, v: v.update(made_of=[S1]))
    assert SPEC.venue_parts(sp["venues"]) == {} and (f"{PAIR}: a combined venue needs at least two rooms.", True) in p
    sp, p = probs(lambda sp, v: v.update(made_of=[S1, "Studio 9"]))
    assert SPEC.venue_parts(sp["venues"]) == {} and (f"{PAIR}: made of Studio 9, which is not on step 1 (Venues).", True) in p
    sp, p = probs(lambda sp, v: sp["venues"].append(dict(room="Other pair", kind="d&t studio", capacity=40, made_of=[S2, "Art Room 1"])))
    assert (f"{S2} is in more than one combined venue ({PAIR}, Other pair): a room can be in one only.", True) in p
    sp, p = probs(lambda sp, v: sp["venues"].append(dict(room="Big", kind="d&t studio", capacity=80, made_of=[PAIR, "Art Room 1"])))
    assert ("Big: made of D&T Studio 1&2, which is a combined venue itself.", True) in p
    sp, p = probs(lambda sp, v: v.update(made_of=[S1, "Art Room 1"]))
    assert (f"{PAIR}: it and its rooms are of different kinds (art room, d&t studio); they must all be one kind.", True) in p
    sp, p = probs(lambda sp, v: sp["rules"].append(dict(scope="Room", target=S1, rule="At most N at once", number=2, strength="Must", week="Both", day="All")))
    assert (f'{PAIR}: {S1} takes 2 groups at once (an "At most N at once" rule); a combined venue and its rooms take one group at a time.', True) in p
    sp, p = probs(lambda sp, v: v.update(capacity=None)); assert (f"{PAIR}: give its seats (seats decide which groups get it).", False) in p
    sp, p = probs(lambda sp, v: v.update(capacity=50)); assert (f"{PAIR}: 50 seats, but its rooms seat 40 together.", False) in p
    sp, p = probs(lambda sp, v: v.update(capacity=44)); assert p == []   # within 10%
t(broken_ones_are_ordinary_rooms_and_are_reported)

def the_workbook_keeps_made_of():
    sp = pair_school(); d = tempfile.mkdtemp(); p = os.path.join(d, "s.xlsx"); template.write_template(sp, p)
    import openpyxl
    ws = openpyxl.load_workbook(p)["1 Venues"]; heads = [ws.cell(5, j).value for j in range(1, 13)]
    assert heads[10] == "Made of (rooms used together)"
    back = reader.read_template(p); back = back[0] if isinstance(back, tuple) else back
    by = {v["room"]: v for v in back["venues"]}; assert by[PAIR]["made_of"] == [S1, S2] and not by[S1].get("made_of")
    wb = openpyxl.load_workbook(p); wb["1 Venues"].delete_cols(11); wb.save(p)   # an older workbook: no such column
    old = reader.read_template(p); old = old[0] if isinstance(old, tuple) else old
    assert all(not v.get("made_of") for v in old["venues"]) and len(old["venues"]) == len(sp["venues"])
t(the_workbook_keeps_made_of)

def check_reports_them_and_names_are_clean():
    sp = pair_school(); sp["venues"][-1]["made_of"] = [S1]
    assert any("a combined venue needs at least two rooms." in str(x) for x in reader.derive(sp))
    sp = pair_school(); d = tempfile.mkdtemp(); p = os.path.join(d, "s.xlsx"); template.write_template(sp, p)
    import openpyxl
    wb = openpyxl.load_workbook(p); ws = wb["1 Venues"]
    r = next(r for r in range(6, 80) if ws.cell(r, 1).value == S1); ws.cell(r, 1).value = "D&T  Studio 1 "; wb.save(p)
    back = reader.read_template(p); back = back[0] if isinstance(back, tuple) else back
    assert S1 in [v["room"] for v in back["venues"]]   # runs of spaces made one, ends trimmed
t(check_reports_them_and_names_are_clean)

from ttgen import solver  # noqa: E402
from ttgen.solver import Problem  # noqa: E402

def rows_of(P, pred): return [(r, u) for u in P.units for r in u["rows"] if pred(r, u)]

def the_problem_knows_the_pair():
    P = Problem(pair_school())
    assert P.parts == {PAIR: [S1, S2]} and P.singles(PAIR) == [S1, S2] and P.singles(S1) == [S1]
    assert P.seats[PAIR] == 40 and P.room_kind[PAIR] == "d&t studio" and P.room_cap[PAIR] == 1
    for r, u in rows_of(P, lambda r, u: r["subject"] == "Design & Technology"): assert P.allowed(r, u)[1] == frozenset([PAIR])   # 37 to 39 students: only the pair seats them
    for r, u in rows_of(P, lambda r, u: r["code"] in ("3DTP1", "4DTP1")): assert P.allowed(r, u)[1] == frozenset([S1, S2, PAIR])
    assert Problem(secondary()).parts == {}
t(the_problem_knows_the_pair)

def a_group_too_big_for_everything_gets_the_biggest():
    P = Problem(pair_school(seats=30))   # nothing seats a class of 37 to 39
    for r, u in rows_of(P, lambda r, u: r["subject"] == "Design & Technology"):
        kind, E, size, over = P.allowed(r, u); assert E == frozenset([PAIR]) and over
    sp = secondary()   # no combined venue of the kind: as today, every room of the kind
    for v in sp["venues"]:
        if v["room"] in (S1, S2): v["capacity"] = 20
    P = Problem(sp)
    for r, u in rows_of(P, lambda r, u: r["subject"] == "Design & Technology"): assert P.allowed(r, u)[1] == frozenset([S1, S2])
t(a_group_too_big_for_everything_gets_the_biggest)

def counting():
    parts = {PAIR: [S1, S2]}; f = frozenset
    assert solver.under(f([PAIR]), parts) == f([S1, S2]) and solver.under(f([S1, PAIR]), parts) == f([S1, S2]) and solver.under(f(["X"]), parts) == f(["X"])
    assert solver.weight(f([PAIR]), parts) == 2 and solver.weight(f([S1, S2, PAIR]), parts) == 1 and solver.weight(f(["X"]), parts) == 1 and solver.weight(f(), parts) == 0
    fam = lambda sets, every: set(solver.room_families(sets, f(every), parts))
    # the kind has only the two studios and the pair
    assert fam([f([PAIR]), f([S1, S2, PAIR])], [S1, S2, PAIR]) == {f([S1, S2])}
    # a third studio as well
    assert fam([f([PAIR]), f([S1, S2, "S3", PAIR])], [S1, S2, "S3", PAIR]) == {f([S1, S2]), f([S1, S2, "S3"])}
    # a group kept to one studio by a rule
    assert fam([f([PAIR]), f([S1])], [S1, S2, "S3", PAIR]) == {f([S1]), f([S1, S2]), f([S1, S2, "S3"])}
    assert solver.room_families([f(["A"]), f(["A", "B"])], f(["A", "B"]), {}) == [f(["A"]), f(["A", "B"])]
t(counting)

def not_available_carries_up_but_not_down():
    sp = pair_school(); sp["rules"].append(dict(scope="Room", target=S1, rule="Not available", strength="Must", week="Both", day="All", **{"from": 1, "to": 2}))
    P = Problem(sp); assert P.off[PAIR] and P.off[PAIR] == P.off[S1] and not P.off.get(S2)
    r, u = rows_of(P, lambda r, u: r["subject"] == "Design & Technology")[0]; q = min(P.off[PAIR])
    assert P.allowed_at(r, u, q, 1)[1] == frozenset() and P.allowed_at(r, u, max(P.off[PAIR]) + 1, 1)[1] == frozenset([PAIR])
    sp = pair_school(); sp["rules"].append(dict(scope="Room", target=PAIR, rule="Not available", strength="Must", week="Both", day="All", **{"from": 1, "to": 2}))
    P = Problem(sp); assert P.off[PAIR] and not P.off.get(S1)
t(not_available_carries_up_but_not_down)

def a_rule_finds_a_room_typed_with_a_stray_space():
    sp = pair_school(); next(v for v in sp["venues"] if v["room"] == S1)["room"] = S1 + " "
    sp["venues"][-1]["made_of"] = [S1 + " ", S2]
    sp["rules"].append(dict(scope="Level", target="Sec 3", subject="Design & Technology G3", rule="Only in venues", venues=f"{S1}, {S2}", strength="Must", week="Both", day="All"))
    P = Problem(sp); assert len(P.venue_rules[-1]["V"]) == 2
    assert not any("not on step 1" in x for x in map(str, solver.rule_problems(sp)))
t(a_rule_finds_a_room_typed_with_a_stray_space)

def room_names_are_cleaned_when_the_problem_is_built():
    sp = pair_school(); next(v for v in sp["venues"] if v["room"] == S1)["room"] = S1 + " "; sp["venues"][-1]["made_of"] = [S1 + " ", S2]
    sp["classes"][0]["home_room"] = S1 + " "
    sp["rules"].append(dict(scope="Room", target=S1 + " ", rule="Not available", strength="Must", week="Both", day="All", **{"from": 1, "to": 2}))
    P = Problem(sp); assert S1 in P.room_kind and P.spec["classes"][0]["home_room"] == S1 and P.off[S1]
    assert not any("not a room" in str(x) for x in solver.rule_problems(sp))
    assert SPEC.clean_rooms({}) == {}
    once = copy.deepcopy(SPEC.clean_rooms(copy.deepcopy(sp))); assert SPEC.clean_rooms(copy.deepcopy(once)) == once
t(room_names_are_cleaned_when_the_problem_is_built)

from ttgen import report  # noqa: E402

def placed(P, picks):
    """a result with the picked rows placed by hand: picks = [(row test, start, length)] -> res"""
    L = []
    for pred, start, ln in picks:
        r, u = rows_of(P, pred)[0]; L.append(dict(unit=u, part=[r], start=start, ln=ln, ext=False, key=f"{u['id']}:{len(L)}"))   # ext: inside the school day
    return dict(status="FEASIBLE", problem=P, lessons=L, recess={}, notes=[])

def first_l(P, level, d=0): row = P.grid[level][d]; return d * P.NP + row.index("L")
dt1 = lambda c: (lambda r, u: r["subject"] == "Design & Technology" and u["classes"] == [c])
grp = lambda code: (lambda r, u: r["code"] == code)
room_of = lambda res, i: next(iter(res["lessons"][i]["rooms"].values()))

def rooms_are_handed_out_by_the_one_rule():
    P = Problem(pair_school()); q = first_l(P, "Sec 1")
    res = placed(P, [(grp("3DTP1"), q, 1), (grp("4DTP1"), q, 1)]); report.assign_rooms(res)   # two small groups: a studio each
    assert {room_of(res, 0), room_of(res, 1)} == {S1, S2}
    res = placed(P, [(dt1("1A"), q, 1), (grp("3DTP1"), q, 1)]); report.assign_rooms(res)      # a class and a group: the class has the pair, the group nothing
    assert room_of(res, 0) == PAIR and room_of(res, 1) == "TBC"
    res = placed(P, [(dt1("1A"), q, 1), (dt1("1B"), q, 1)]); report.assign_rooms(res)          # two classes: one pair
    assert sorted([room_of(res, 0), room_of(res, 1)]) == sorted([PAIR, "TBC"])
    res = placed(P, [(dt1("1A"), q, 1), (grp("3DTP1"), q + 1, 1)]); report.assign_rooms(res)  # one after the other: both served
    assert room_of(res, 0) == PAIR and room_of(res, 1) in (S1, S2)
t(rooms_are_handed_out_by_the_one_rule)

def the_check_counts_a_pair_lesson_in_each_room():
    P = Problem(pair_school()); q = first_l(P, "Sec 1")
    res = placed(P, [(dt1("1A"), q, 1), (grp("3DTP1"), q, 1)]); report.assign_rooms(res)
    r3 = res["lessons"][1]["part"][0]; res["lessons"][1]["rooms"][id(r3)] = S1   # forced into half of the pair
    probs = report.check(res)[0]; assert any(p.startswith(f"Room over capacity: {S1} at ") for p in probs) and not any(S2 in p for p in probs if p.startswith("Room over"))
    res["lessons"][1]["rooms"][id(r3)] = PAIR
    probs = report.check(res)[0]; assert sum(p.startswith("Room over capacity:") for p in probs) == 2   # both studios
t(the_check_counts_a_pair_lesson_in_each_room)

def a_solve_keeps_the_rule():   # slow: only with --full
    res = solver.solve(pair_school(), time_limit=240, workers=8, log=lambda *a: None); assert res["status"] in ("OPTIMAL", "FEASIBLE"), res["status"]
    report.assign_rooms(res); probs = report.check(res)[0]; assert not [p for p in probs if p.startswith("Room over capacity")] and not [p for p in probs if "TBC" in p], probs[:5]
    use = collections.defaultdict(list)
    for L in res["lessons"]:
        for r in L["part"]:
            room = L["rooms"][id(r)]
            if r["subject"] == "Design & Technology": assert room == PAIR
            if r["code"] in ("3DTP1", "4DTP1"): assert room in (S1, S2)
            for s in res["problem"].singles(room):
                if s in (S1, S2):   # the Field takes two classes at once by its own rule; the studios take one
                    for k in range(L["ln"]): use[(s, L["start"] + k)].append(id(L))
    assert all(len(set(v)) == 1 for v in use.values())
if "--full" in sys.argv: t(a_solve_keeps_the_rule)

import checks  # noqa: E402
from ttgen import staged  # noqa: E402

def the_sums_never_count_the_pair_as_a_room():
    sp = pair_school(); P = Problem(sp)
    rows = [x for x in checks.room_sums(P) if x["kind"] == "d&t studio"]
    assert rows and all(set(x["rooms"]) <= {S1, S2} for x in rows)           # sums are over single rooms
    one = [x for x in checks.room_sums(Problem(secondary())) if x["kind"] == "d&t studio"]
    assert max(x["have"] for x in rows) == max(x["have"] for x in one)        # two studios' worth, as without the pair
    assert max(x["need"] for x in rows) > max(x["need"] for x in one)         # a class in the pair weighs two; the small groups one
t(the_sums_never_count_the_pair_as_a_room)

def a_band_needing_three_studios_is_not_helped_by_the_pair():
    sp = pair_school(); row = next(x for x in sp["lessons"] if x.get("code") == "3DTP1")
    for i, code in enumerate(("3DTP8", "3DTP9")):   # two more d&t studio groups in the same band: three studios at once
        sp["lessons"].append(dict(copy.deepcopy(row), code=code, code_override=code, teachers=[f"Teacher {i + 4}"], students=15))
    out = [x[1] for x in checks._loads_and_rooms(sp, Problem(sp)) if "rooms at once" in x[1]]
    assert any(x.startswith("Band Sec 3 Option Y needs 3 'd&t studio' rooms at once; Venues has 2:") for x in out), out
t(a_band_needing_three_studios_is_not_helped_by_the_pair)

def an_unknown_size_is_warned_about():
    sp = pair_school()
    for x in sp["lessons"]:
        if x.get("code") == "3DTP1": x["students"] = None
    for s in sp["students"]: s["groups"] = [g for g in s.get("groups") or [] if g != "3DTP1"]
    out = checks._loads_and_rooms(sp, Problem(sp))
    assert ("lessons", f"Design & Technology G3 3DTP1: no group size is known, so it may be given any d&t studio, {PAIR} included. Give its Students on step 5.") in out
t(an_unknown_size_is_warned_about)

def a_held_pair_holds_both_studios():
    run = staged._Run(pair_school(), 5, 1, lambda *a: None)
    rules = run.hold_rules(PAIR, "Both", "Mon", dict({"from": 1, "to": 3}))
    assert sorted(r["target"] for r in rules) == [S1, S2] and all(r["rule"] == "Not available" and r["scope"] == "Room" for r in rules)
    assert [r["target"] for r in run.hold_rules(S1, "Both", "Mon", dict({"from": 1, "to": 3}))] == [S1]
t(a_held_pair_holds_both_studios)

from ttgen import export, verify, database  # noqa: E402
ENTIRE = export.ENTIRE

def a_model(placed, sp=None):
    sp = sp or pair_school(); return sp, model_for(sp, placed)

def lessons_for():
    """the pair school, a lesson period of its first day, and three made-up teachers (so only rooms can clash)"""
    sp = pair_school(); p0 = sp["day_structure"]["Sec 1"][sp_days(sp)[0]].index("L")
    return sp, p0, ["Teacher One"], ["Teacher Two"], ["Teacher Three"]
def sp_days(sp): return list(sp["day_structure"]["Sec 1"].keys())

def the_model_and_its_check():
    sp, p0, t1, t2, t3 = lessons_for()
    _, m = a_model([(0, p0, 1, ["1A"], "Design & Technology", ENTIRE, t1, PAIR), (0, p0, 1, ["3A"], "Design & Technology G3", "3DTP1", t3, S1)], sp)
    assert m["room_parts"] == {PAIR: [S1, S2]} and m["room_ix"][PAIR]["parts"] == [S1, S2] and m["room_ix"][S1]["parts"] == []
    over = [p for p in m["checks"]["problems"] if p.startswith("Room over capacity:")]
    assert len(over) == 1 and over[0].startswith(f"Room over capacity: {S1} on ") and over[0].endswith(f"(holds 1 at once; in use as part of {PAIR}).")
    _, m = a_model([(0, p0, 1, ["1A"], "Design & Technology", ENTIRE, t1, PAIR), (0, p0, 1, ["1B"], "Design & Technology", ENTIRE, t2, PAIR)])
    assert sum(p.startswith("Room over capacity:") for p in m["checks"]["problems"]) == 2
    _, m = a_model([(0, p0, 1, ["3A"], "Design & Technology G3", "3DTP1", t3, S1), (0, p0 + 1, 1, ["1A"], "Design & Technology", ENTIRE, t1, PAIR)])
    assert not [p for p in m["checks"]["problems"] if p.startswith("Room over capacity:")]
t(the_model_and_its_check)

def a_class_in_half_of_its_venue_is_warned_about():
    sp, p0, t1, t2, t3 = lessons_for()
    _, m = a_model([(0, p0, 1, ["1A"], "Design & Technology", ENTIRE, t1, S1), (0, p0, 1, ["3A"], "Design & Technology G3", "3DTP1", t3, S2)], sp)
    texts = [w["text"] for w in verify.deployment(m, sp)]
    assert f"Design & Technology for 1A (38 students) is in {S1} (20 seats); {PAIR} seats it." in texts
    assert not any("3DTP1" in x and "seats it" in x for x in texts)
t(a_class_in_half_of_its_venue_is_warned_about)

def room_rules_reach_a_lesson_in_the_pair():
    sp, p0, t1, t2, t3 = lessons_for(); day = sp_days(sp)[0].split()[-1]
    sp["rules"].append(dict(scope="Room", target=S1, rule="Not available", strength="Must", week="Both", day=day, **{"from": p0, "to": p0}))
    sp["rules"].append(dict(scope="Level", target="Sec 3", subject="Design & Technology G3", rule="Only in venues", venues=f"{S1} ,  {S2}", strength="Must", week="Both", day="All"))
    _, m = a_model([(0, p0, 1, ["1A"], "Design & Technology", ENTIRE, t1, PAIR), (0, p0 + 1, 1, ["3A"], "Design & Technology G3", "3DTP1", t3, S2)], sp)
    ws = verify.rules(m, sp)[0]; na, only = len(sp["rules"]) - 2, len(sp["rules"]) - 1   # the two rows just added
    assert any(w["key"].startswith(f"rule:{na}:") for w in ws)          # 1A is in the pair while Studio 1 is not available
    assert not any(w["key"].startswith(f"rule:{only}:") for w in ws)    # "D&T Studio 1 ,  D&T Studio 2" still names Studio 2
t(room_rules_reach_a_lesson_in_the_pair)

def the_database_lists_the_rooms_of_a_venue():
    import sqlite3
    sp, m = a_model([]); p = os.path.join(tempfile.mkdtemp(), "t.sqlite"); database.write_db(m, p, spec=sp)
    con = sqlite3.connect(p); assert con.execute("SELECT venue, room FROM room_parts ORDER BY room").fetchall() == [(PAIR, S1), (PAIR, S2)]
    assert [r[1] for r in con.execute("PRAGMA table_info(rooms)")] == ["name", "kind", "capacity"]; con.close()
    m2 = export.model_from_files(None, p); assert m2["room_parts"] == {PAIR: [S1, S2]}
t(the_database_lists_the_rooms_of_a_venue)

def an_old_model_still_checks():
    sp, p0, t1, t2, t3 = lessons_for()
    _, new = a_model([(0, p0, 1, ["1A"], "Design & Technology", ENTIRE, t1, "A1-01"), (0, p0 + 1, 1, ["3A"], "Design & Technology G3", "3DTP1", t3, S1)], sp)
    old = copy.deepcopy(new); old.pop("room_parts"); [r.pop("parts") for r in old["rooms"]]; old["room_ix"] = {r["name"]: r for r in old["rooms"]}
    assert export.check_model(old)["problems"] == export.check_model(new)["problems"]
    assert [w["text"] for w in verify.deployment(old, sp)] == [w["text"] for w in verify.deployment(new, sp)]
t(an_old_model_still_checks)

def odd_numbers_do_not_throw():
    sp0, p0, t1, t2, t3 = lessons_for()
    def edit(f): sp = pair_school(); f(sp); return sp
    def cap(room, v): return lambda sp: [x.update(capacity=v) for x in sp["venues"] if x["room"] == room]
    def size(sp): [c.update(size="abc") for c in sp["classes"] if c["class"] == "1A"]
    def stud(sp): [x.update(students="abc") for x in sp["lessons"] if x.get("subject") == "Design & Technology" and "1A" in x["classes"]]
    texts = {}
    for name, f in dict(s1_abc=cap(S1, "abc"), s1_dec=cap(S1, "20.0"), pair_abc=cap(PAIR, "abc"), pair_none=cap(PAIR, None), size=size, stud=stud).items():
        sp = edit(f); _, m = a_model([(0, p0, 1, ["1A"], "Design & Technology", ENTIRE, t1, S1)], sp)
        w = verify.deployment(m, sp); assert isinstance(w, list); export.check_model(m); texts[name] = [x["text"] for x in w]
    assert f"Design & Technology for 1A (38 students) is in {S1} (20 seats); {PAIR} seats it." in texts["s1_dec"]
    assert not any("seats it" in x for x in texts["s1_abc"])
    for v in (20, "20", " 20 ", "20.0", 20.0): assert SPEC.whole(v) == 20
    for v in (None, "", "abc", 0, -3, True): assert SPEC.whole(v) is None
t(odd_numbers_do_not_throw)

import fixes  # noqa: E402

def busy_follows_the_one_rule():
    sp, p0, t1, t2, t3 = lessons_for()
    _, m = a_model([(0, p0, 1, ["1A"], "Design & Technology", ENTIRE, t1, PAIR), (0, p0 + 1, 1, ["3A"], "Design & Technology G3", "3DTP1", t3, S1),
                    (0, p0 + 2, 1, ["1B"], "Design & Technology", ENTIRE, t2, PAIR)], sp)
    b = fixes.Busy(m); L = m["lessons"]; g = [x for x in L if x["group"] == "3DTP1"]; i_g = g[0]["id"]; c2 = [x for x in L if x["classes"] == ["1B"]]; i_c2 = c2[0]["id"]
    assert b.rooms(PAIR) == [S1, S2] and b.rooms(S1) == [S1]
    assert b.clash(g, 0, p0, 1, ignore={i_g}) == f"{S1} is in use then."          # the group into a studio while 1A has the pair
    assert b.clash(c2, 0, p0 + 1, 1, ignore={i_c2}) == f"{PAIR} is in use then."  # a class into the pair while the group has Studio 1
    assert b.clash(c2, 0, p0, 1, ignore={i_c2}) == f"{PAIR} is in use then."      # two classes in the pair
    other = [dict(g[0], room=S2)]; assert b.clash(other, 0, p0 + 1, 1, ignore={i_g}) is None
    assert "room" not in fixes.marks(b, g)
    _, m = a_model([(0, p0, 1, ["1A"], "Design & Technology", ENTIRE, t1, PAIR), (0, p0, 1, ["3A"], "Design & Technology G3", "3DTP1", t3, S1)], sp)
    b = fixes.Busy(m); by = collections.defaultdict(list); [by[x["id"]].append(x) for x in m["lessons"]]
    assert all("room" in fixes.marks(b, rows) for rows in by.values())
t(busy_follows_the_one_rule)

def one_lessons_own_rows():
    sp, p0, t1, t2, t3 = lessons_for()
    _, m = a_model([(0, p0, 1, ["1A"], "Design & Technology", ENTIRE, t1, PAIR)], sp)
    x = m["lessons"][0]; m["lessons"].append(dict(x, group="3DTP1", classes=["3A"], teachers=t3, room=S1))   # the same lesson id: a band's rows
    b = fixes.Busy(m); assert "room" not in fixes.marks(b, m["lessons"])                                     # marks: other lessons only
    why = b.clash(m["lessons"], 0, p0, 1, ignore={x["id"]}); assert why and why.endswith(" is in use then."), why   # but its own rows stand twice on Studio 1
    assert any(p.startswith(f"Room over capacity: {S1} on ") for p in export.check_model(m)["problems"])
    _, m = a_model([(0, p0, 1, ["3A"], "Design & Technology G3", "3DTP1", t3, S1)], sp)
    y = m["lessons"][0]; m["lessons"].append(dict(y, group="4DTP1", classes=["4A"], teachers=t2, room=S2))   # a band: one row in each studio
    assert fixes.Busy(m).clash(m["lessons"], 0, p0, 1, ignore={y["id"]}) is None
t(one_lessons_own_rows)

def the_room_list_says_what_holds_a_studio():
    sp, p0, t1, t2, t3 = lessons_for()
    _, m = a_model([(0, p0, 1, ["1A"], "Design & Technology", ENTIRE, t1, PAIR), (0, p0, 1, ["3A"], "Design & Technology G3", "3DTP1", t3, "")], sp)
    g = next(x for x in m["lessons"] if x["group"] == "3DTP1"); out = fixes.choices(m, sp, m["days"], g["id"], "3DTP1")
    r = {x["room"]: x for x in out["rooms"]}; assert not r[S1]["free"] and not r[S2]["free"] and "Design & Technology" in r[S1]["holding"]
t(the_room_list_says_what_holds_a_studio)

def room_pages_show_the_pair_on_each_studio():
    sp, p0, t1, t2, t3 = lessons_for()
    _, m = a_model([(0, p0, 2, ["1A"], "Design & Technology", ENTIRE, t1, PAIR), (1, p0, 1, ["3A"], "Design & Technology G3", "3DTP1", t3, S1)], sp)
    v1, v2, vp = export.room_view(m, S1), export.room_view(m, S2), export.room_view(m, PAIR)
    assert len(v1["cells"]) == 2 and len(v2["cells"]) == 1 and len(vp["cells"]) == 1
    mine = next(c for c in v1["cells"] if c["d"] == 0); assert f"with {S2}, as {PAIR}" in mine["lines"]
    assert dict((b, a) for a, b in v1["stats"])["periods used"] == "3" and dict((b, a) for a, b in v2["stats"])["periods used"] == "2"
    assert f"made of {S1} + {S2}" in vp["subtitle"]
    assert {S1, S2, PAIR} <= {v["key"] for v in export.all_views(m, "rooms")}   # Studio 2 is named by no lesson and still has a page
    d = export.html_data(m); row = next(r for r in d["rooms"] if r[0] == PAIR); assert row[5] == [S1, S2]
    assert next(r for r in d["rooms"] if r[0] == S1)[5] == []
t(room_pages_show_the_pair_on_each_studio)

def the_skill_explains_made_of():
    root = os.path.dirname(HERE); s = open(os.path.join(root, "skill", "school-timetable-generator", "SKILL.md"), encoding="utf-8").read()
    assert SPEC.SKILL_VERSION == "2026-11.9" and "Skill version: 2026-11.9" in s and "2026-11.9" in open(os.path.join(root, "README.md"), encoding="utf-8").read()
    for words in ("Made of", "combined venue", "room_parts", "takes every one of its rooms"): assert words in s, words
t(the_skill_explains_made_of)

def lessons_sheet(path, rows):
    """a Lessons workbook as an agent hands it over: rows = [(day, start, periods, level, classes, subject, group, teachers, room, rain)]"""
    import openpyxl
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Lessons"
    ws.append(["Lesson ID", "Day", "Start period", "End period", "Periods", "Starts", "Ends", "Level", "Block", "Classes", "Subject", "Group", "Teachers", "Room", "After school", "Rain room"])
    for i, (day, p, n_, lv, cls, subj, grp_, tch, room, rain) in enumerate(rows, 1): ws.append([i, day, p, p + n_ - 1, n_, "", "", lv, "", cls, subj, grp_, ", ".join(tch), room, "", rain])
    wb.save(path)

def a_stray_space_in_the_room_column_still_clashes():
    sp, p0, t1, t2, t3 = lessons_for(); day = sp_days(sp)[0]
    with tempfile.TemporaryDirectory() as d:
        setup, tt = os.path.join(d, "s.xlsx"), os.path.join(d, "t.xlsx"); template.write_template(sp, setup)
        lessons_sheet(tt, [(day, p0, 1, "Sec 1", "1A", "Design & Technology", ENTIRE, t1, PAIR + " ", ""),
                           (day, p0, 1, "Sec 3", "3A, 3B, 3C, 3D", "Design & Technology G3", "3DTP1", t3, S1, "")])
        m = export.model_from_files(setup, tt)
    over = [p for p in m["checks"]["problems"] if p.startswith("Room over capacity:")]
    assert len(over) == 1 and over[0].startswith(f"Room over capacity: {S1} on ") and over[0].endswith(f"in use as part of {PAIR})."), over
    assert {x["room"] for x in m["lessons"]} <= {v["room"] for v in sp["venues"]}
    pe = [dict(id=1, d=0, p=p0, n=1, level="Sec 1", block="", classes=["1C"], subject="Physical Education", group=ENTIRE, teachers=t2, room="Field", ext=False, rain="")]
    sp2 = pair_school(); reader.derive(sp2); fx = dict(kind="room", id=1, group=ENTIRE, room=" D&T  Studio 1")   # a stored fix with the old spacing
    out = fixes.apply(pe, [fx], sp2, sp_days(sp2)); assert not out["problems"] and out["lessons"][0]["room"] == S1, out["problems"]
t(a_stray_space_in_the_room_column_still_clashes)

def rain_rooms_follow_the_one_rule():
    sp, p0, t1, t2, t3 = lessons_for()
    for rain, room in ((PAIR, S1), (S1, PAIR)):
        _, m = a_model([(0, p0, 1, ["1C"], "Physical Education", ENTIRE, t2, "Field"), (0, p0, 1, ["3A"], "Design & Technology G3", "3DTP1", t3, room)], sp)
        m["lessons"][0]["rain"] = rain; probs = export.check_model(m)["problems"]
        assert any(p.startswith("Rain room in use: ") for p in probs), (rain, probs)
        b = fixes.Busy(m); g = [m["lessons"][1]]
        assert b.clash(g, 0, p0, 1, ignore={g[0]["id"]}) == f"{room} is in use then."               # the lesson into the rain room's time
        pe = [m["lessons"][0]]; assert b.clash(pe, 0, p0, 1, ignore={pe[0]["id"]}) == f"{rain} is in use then."   # PE into the lesson's time
t(rain_rooms_follow_the_one_rule)

def small(sp):
    """the sample cut down to its D&T lessons, each with its own teacher, and only the Room rules that cap a room (a solve in about 0.4 s)"""
    sp["lessons"] = [x for x in sp["lessons"] if str(x.get("subject", "")).startswith("Design & Technology")]
    sp["rules"] = [r for r in sp["rules"] if r.get("rule") == "At most N at once" and r.get("scope") == "Room"]
    for i, x in enumerate(sp["lessons"]): x["teachers"] = [f"Teacher {i + 1}"]
    return sp
def fixed_at(sp, scope, target, subject, p):
    sp["rules"].append(dict(scope=scope, target=target, subject=subject, rule="Fixed at", week="Odd", day="Mon", strength="Must", **{"from": p, "to": None}))
def with_third(sp): sp["venues"].append(dict(room="D&T Studio 3", kind="d&t studio", capacity=20)); return sp
CA, CB, G3_, G4_ = ("Class", "1A", "Design & Technology"), ("Class", "1B", "Design & Technology"), ("Group", "3DTP1", None), ("Group", "4DTP1", None)
def solved(sp, at):
    for who, p in at: fixed_at(sp, *who, p)
    return solver.solve(sp, time_limit=20, workers=4, log=lambda *a: None)

def a_third_studio_is_a_known_limit():
    res = solved(with_third(small(pair_school())), [(("Class", "1D", "Design & Technology"), 9), (G3_, 11), (G4_, 12), (CA, 14)])
    assert res["status"] in ("OPTIMAL", "FEASIBLE"), res["status"]   # the per-period count is met (at most 3 single rooms at once) ...
    report.assign_rooms(res); probs = report.check(res)[0]
    assert any(p.endswith("lesson-groups have no free room (marked TBC).") for p in probs), probs   # ... but no hand-out exists: reported, not silent
t(a_third_studio_is_a_known_limit)

def the_table_holds_in_the_model():
    def only_s1(sp): sp["rules"].append(dict(scope="Group", target="3DTP1", rule="Only in venues", venues=[S1], strength="Must", week="Both", day="All")); return sp
    setups = dict(pair=lambda: small(pair_school()), third=lambda: with_third(small(pair_school())), rule=lambda: only_s1(with_third(small(pair_school()))))
    ok = ("OPTIMAL", "FEASIBLE")
    for name, make in setups.items():
        crowd = [(CA, 1), (G3_, 1)] + ([(G4_, 1)] if name == "third" else [])   # a class in the pair and groups no other room can take
        assert solved(make(), crowd)["status"] == "INFEASIBLE", name
        assert solved(make(), [(CA, 1), (CB, 1)])["status"] == "INFEASIBLE", name   # two classes in the pair at once
        assert solved(make(), [(G3_, 1), (G4_, 1)])["status"] in ok, name            # two groups at once: a studio each
        assert solved(make(), [(CA, 1)])["status"] in ok, name                       # a class alone
    assert solved(setups["third"](), [(CA, 1), (G3_, 1)])["status"] in ok           # the third studio takes the group
t(the_table_holds_in_the_model)

def venue_problems_reach_things_to_fix_as_critical():
    sp = pair_school(); sp["venues"][-1]["made_of"] = [S1]; text = f"{PAIR}: a combined venue needs at least two rooms."
    out = checks.findings(copy.deepcopy(sp))
    hit = [f for f in out if f["text"] == text]; assert len(hit) == 1 and hit[0]["level"] == checks.CRITICAL and hit[0]["area"] == "venues", hit
    assert not [f for f in out if f["area"] == "lessons" and "combined venue" in f["text"]]
    assert f"Venue row {len(sp['venues']) - 1 + 6}: {text}" in reader.derive(copy.deepcopy(sp))   # the sheet row: data starts on row 6
t(venue_problems_reach_things_to_fix_as_critical)

def a_pair_nobody_needs_is_warned_about():
    want = ("venues", f"No lesson is limited to {PAIR}: every group that may use it also fits one of its rooms, so each will be given one room. Check the seats on step 1.")
    sp = pair_school(seats=80)
    for v in sp["venues"]:
        if v["room"] in (S1, S2): v["capacity"] = 40
    assert want in checks._loads_and_rooms(sp, Problem(sp))
    sp = pair_school(); assert want not in checks._loads_and_rooms(sp, Problem(sp))
t(a_pair_nobody_needs_is_warned_about)

def a_pair_no_lesson_can_use_is_worded_for_what_is_wrong():
    limited = f"No lesson is limited to {PAIR}"
    sp = pair_school()   # its rooms of a kind no lesson has
    for v in sp["venues"]:
        if v["room"] in (S1, S2, PAIR): v["kind"] = "spare studio"
    out = [t_ for a, t_ in checks._loads_and_rooms(sp, Problem(sp)) if a == "venues" and PAIR in t_]
    assert out == [f"No lesson uses {PAIR}'s kind ('spare studio'), so nobody will be given it. Check its rooms' kind on step 1, or the room kind of the subjects "
                   "meant for it on step 3."], out
    sp = pair_school(); sp["venues"][-1]["only_for"] = ["Sec 9"]   # kept for nobody on the setup
    out = [t_ for a, t_ in checks._loads_and_rooms(sp, Problem(sp)) if a == "venues" and PAIR in t_]
    assert out == [f"No lesson may use {PAIR}: no 'd&t studio' group is both kept to it and seated by it, so nobody will be given it. Check its For box and seats on "
                   "step 1."], out
    assert not any(limited in t_ for _, t_ in checks._loads_and_rooms(sp, Problem(sp)))
t(a_pair_no_lesson_can_use_is_worded_for_what_is_wrong)

def at_most_n_on_a_room_of_the_pair_is_one():
    sp = pair_school(); sp["rules"].append(dict(scope="Room", target=S1, rule="At most N at once", number=2, strength="Must", week="Both", day="All"))
    assert Problem(copy.deepcopy(sp)).room_cap[S1] == 1
    p0 = sp["day_structure"]["Sec 1"][sp_days(sp)[0]].index("L")
    _, m = a_model([(0, p0, 1, ["1A"], "Design & Technology", ENTIRE, ["Teacher One"], PAIR), (0, p0, 1, ["3A"], "Design & Technology G3", "3DTP1", ["Teacher Three"], S1)], sp)
    assert m["room_cap"][S1] == 1 and any(p.startswith(f"Room over capacity: {S1} on ") for p in m["checks"]["problems"])
    P = Problem(copy.deepcopy(sp)); q = first_l(P, "Sec 1"); res = placed(P, [(dt1("1A"), q, 1), (grp("3DTP1"), q, 1)]); report.assign_rooms(res)
    r3 = res["lessons"][1]["part"][0]; res["lessons"][1]["rooms"][id(r3)] = S1
    assert any(p.startswith(f"Room over capacity: {S1} at ") for p in report.check(res)[0])
t(at_most_n_on_a_room_of_the_pair_is_one)

def a_pair_with_no_kind_takes_its_rooms_kind():
    sp, p0, t1, t2, t3 = lessons_for(); sp["venues"][-1]["kind"] = None
    _, m = a_model([(0, p0, 1, ["1A"], "Design & Technology", ENTIRE, t1, PAIR)], sp)
    assert m["room_ix"][PAIR]["kind"] == "d&t studio"
    assert not [w["text"] for w in verify.deployment(m, sp) if "(classroom); step 3 asks for d&t studio" in w["text"]]
t(a_pair_with_no_kind_takes_its_rooms_kind)

def odd_made_of_values_are_empty_or_cleaned():
    for odd in ("abc", 5, [5, None, ""]):
        sp = secondary(); sp["venues"].append(dict(room="Odd", kind="classroom", capacity=40, made_of=odd))
        assert SPEC.venue_parts(sp["venues"]) == {}                      # an ordinary room
        SPEC.venue_problems(sp); SPEC.clean_rooms(sp)
        template.write_template(sp, os.path.join(tempfile.mkdtemp(), "s.xlsx"))
        assert SPEC.venue_parts(sp["venues"]) == {} and Problem(copy.deepcopy(sp)).parts == {}
    assert SPEC._made_of(dict(made_of="abc")) == [] and SPEC._made_of(dict(made_of=[5, None, " ", " A  1 "])) == ["5", "A 1"]
    assert [x[1] for x in SPEC.venue_problems(dict(venues=[dict(room="Odd", made_of="abc")]))] == []
t(odd_made_of_values_are_empty_or_cleaned)

def the_skill_says_how_far_the_count_goes():
    root = os.path.dirname(HERE); s = open(os.path.join(root, "skill", "school-timetable-generator", "SKILL.md"), encoding="utf-8").read()
    for words in ("does not guarantee a hand-out", "never leave TBC unreported", "Venues \"For\" column", "take the venue out of the allowed set E", "counts in each of its\n   rooms"): assert words in s, words
    src = open(os.path.join(root, "ttgen", "solver.py"), encoding="utf-8").read(); assert "does not guarantee a hand-out" in src
    assert "room_parts" in (database.__doc__ or "")
t(the_skill_says_how_far_the_count_goes)

# tests are added above this line by each task
if __name__ == "__main__": print(f"{n} checks passed")

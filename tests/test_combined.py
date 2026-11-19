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

# tests are added above this line by each task
if __name__ == "__main__": print(f"{n} checks passed")

# Combined Venues Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A venue on step 1 can be made of two or more rooms; a lesson in it is in each of those rooms, everywhere the solver, the checks, the board and the published timetable count room use.

**Architecture:** A venue row gains `made_of` (a list of room names). Two small helper sets, one in `ttgen/spec.py` and one in `static/venueview.js`, turn a venue name into "the single rooms it stands for"; every place that counts room use calls them instead of comparing names. A lesson still names one room. A setup with no combined venue takes the old code path unchanged.

**Tech Stack:** Python 3 (Flask, openpyxl, OR-Tools CP-SAT), plain JavaScript in `static/`, plain-assert tests run one file at a time.

**Spec:** `docs/superpowers/specs/2026-11-19-combined-venues-design.md`. Read it first; this plan argues from it.

## Global Constraints

- Worktree `/Users/joetay/Developer/tt-generator/tt-combined-venues`, branch `combined-venues`. It has no `.venv`: run Python as `PY=/Users/joetay/Developer/tt-generator/timetable_generator/.venv/bin/python`.
- NEVER run `git stash`, `git stash pop`, `git checkout -- <file>`, `git push`, or any git command outside this worktree. To see old behaviour use `git show HEAD:path > scratch-file`. Commit locally only.
- Every commit message ends with the line `Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>`.
- `skill/school-timetable-generator/scripts/ttgen/` must stay byte-identical to `ttgen/` (`tests/test_rules.py::the_skill_copy_is_identical`). After any change under `ttgen/`: `cp ttgen/<file> skill/school-timetable-generator/scripts/ttgen/<file>`.
- Tests and fixtures use the sample school (`ttgen.samples.secondary()`) only. No real school name, teacher, student or workbook in the repository.
- No `console.log` left in `static/`. `node --check static/app.js` must pass.
- Words on the page: "combined venue", "made of", "its rooms". Message texts quoted in this plan are exact.
- A setup with no combined venue must behave exactly as today: each changed function keeps today's path when `parts` is empty.
- Limits (spec): a room is in at most one combined venue; no combined venue inside another; all rooms of one kind and the combined venue of that kind; rooms and the combined venue take one group at a time.
- The one rule, as a table (D&T Studio 1&2 made of D&T Studio 1 and D&T Studio 2):

  | At the same time | Result |
  |---|---|
  | a class in the pair, nothing in either studio | fine |
  | a group in Studio 1, another in Studio 2 | fine |
  | a class in the pair and a group in Studio 1 (or 2) | room clash |
  | two classes in the pair | room clash |

- Suites, each run as its own command and all green before a task is done: `$PY tests/test_venues.py`, `test_rules.py`, `test_verify.py`, `test_fixes.py`, `test_helper.py`, `test_board.py`, `test_choices.py`, `test_parents.py`, `test_sync.py`, `test_teachers.py`, `test_typed.py`, `smoke.py`, the new `test_combined.py`; `for f in tests/*.test.js; do node "$f" || break; done`.

## Review Focus

1. **A setup saved before this change with a stray space in a room name** ("D&T Lab 1 "): the "Only in venues" rule must match the room, on the page and in Python, without the committee retyping anything. (Tests in Tasks 1 and 7.)
2. **A combined venue whose `made_of` is broken** (a room deleted, one room left, a room in two venues): nothing may throw, on any step; it is treated as an ordinary room and Things to fix says why. (Tests in Tasks 1, 2, 7.)
3. **A group whose size is unknown, or bigger than the pair's seats** (a class of 41, pair said to seat 40): it gets the pair, not a single studio. (Task 2.)
4. **A band whose groups sit in the pair and in one of its rooms inside one lesson** (same lesson id): today a lesson's own groups sharing a room is not a clash in `marks`; that must still hold, and must not double count in `_why`. (Task 6.)
5. **A timetable published before this change** (a stored model or database with no `room_parts`, rooms without `parts`): every reader uses `.get` and draws it as today. (Tasks 5 and 8.)

---

## File Structure

| File | Responsibility in this plan |
|---|---|
| `ttgen/spec.py` | `clean_name`, `venue_parts`, `single_rooms`, `venue_problems`; `SKILL_VERSION` |
| `ttgen/reader.py`, `ttgen/template.py` | the "Made of" column |
| `ttgen/solver.py` | `Problem` knows parts; `under`, `weight`, `room_families`; the model's room limits; venue names matched clean |
| `ttgen/report.py` | `assign_rooms`, `check`, `compromises` by single rooms |
| `ttgen/staged.py`, `checks.py` | holding a pair; both room sums |
| `ttgen/export.py`, `ttgen/verify.py`, `ttgen/database.py` | the timetable model, its checks, the half-venue warning, the `room_parts` table |
| `fixes.py`, `helper.py`, `draft.py` | `Busy` by single rooms; the board's payload |
| `ttgen/timetable_page.html` | published room pages and "Who's free" |
| `static/venueview.js` | page-side helpers: parts, problems, combine, names |
| `static/board.js` | `roomsMeet` |
| `static/app.js`, `static/style.css` | step 1 (Combine, card, table column), the rule picker and check, `bdBusyFor` |
| `tests/test_combined.py` (new) | every Python test of this plan |
| `tests/venueview.test.js`, `tests/board.test.js` | page-side tests |
| `skill/.../SKILL.md`, `README.md` | what Made of means; version 2026-11.9 |

`tests/test_combined.py` starts with this fixture, used by every Python task:

```python
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
# tests are added above this line by each task
if __name__ == "__main__": print(f"{n} checks passed")
```

---

### Task 1: The setup knows a combined venue (helpers, workbook, problems)

**Files:**
- Modify: `ttgen/spec.py`, `ttgen/reader.py` (venues at ~164-167, `derive`), `ttgen/template.py` (~225-240)
- Create: `tests/test_combined.py`
- Test: `tests/test_combined.py`, `tests/test_venues.py`

**Interfaces:**
- Produces, in `ttgen/spec.py`:
  - `clean_name(v) -> str`: `" ".join(str(v if v is not None else "").split())`.
  - `venue_parts(venues) -> dict[str, list[str]]`: `{combined venue: its rooms}`, names cleaned, only for a row that is a *sound* combined venue: `made_of` has at least two distinct names, each is another row's room, none of them has a non-empty `made_of` itself. Anything else is left out (an ordinary room). Order of rooms as listed.
  - `single_rooms(name, parts) -> list[str]`: `parts[name]` when `name in parts`, else `[name]`.
  - `venue_problems(spec) -> list[tuple[int, str, bool]]`: `(venue row index, text, critical)`, texts below.
- Produces, in the setup: venue row key `made_of` (list of str; absent or `[]` for an ordinary room).

- [ ] **Step 1: Write the failing tests** (in `tests/test_combined.py`)

```python
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
```

- [ ] **Step 2: Run** `$PY tests/test_combined.py`. Expected: FAIL, `AttributeError: module 'ttgen.spec' has no attribute 'clean_name'`.

- [ ] **Step 3: Implement the four helpers in `ttgen/spec.py`.** `venue_problems` reports, for each row with a non-empty `made_of`, in this order: fewer than two rooms; each room not on step 1; each room that is a combined venue itself; a room already claimed by an earlier combined venue (reported on the later venue's row, text names both venues in row order); kinds differ (the venue's own kind and its rooms' kinds, sorted, joined by ", "; a missing kind is "classroom"); an "At most N at once" Must rule for the venue or one of its rooms with number above 1; no seats; seats above the sum of its rooms' seats by more than 10% (only when every room has seats). The first six are critical (`True`), the last two warnings.

- [ ] **Step 4: Reader and template.** Reader: `made_of=_names(next((v for h, v in x.items() if h.startswith("Made of")), None))`; every room name read on `1 Venues` (the room, `made_of`), a class's home room and a rule's Venues list goes through `clean_name`. `derive(spec)` appends `venue_problems` as `f"Venue row {i + 1}: {text}"` after its existing problems. Template: column 11 `("Made of (rooms used together)", 30)`, `VIN` gains 11, `B.paint(vw, LAST(nV), VIN, 11)`, the cell is `", ".join(x["made_of"])` when present; the sheet's second help line ends with: `Made of: for a venue that is several rooms used together as one (a class too big for one lab), the rooms, separated by commas. A lesson there takes every one of them.`

- [ ] **Step 5: Run** `$PY tests/test_combined.py` (4 checks passed), `$PY tests/test_venues.py`, `$PY tests/test_rules.py`. Copy the three changed files to the skill copy first. Expected: all pass.

- [ ] **Step 6: Commit** `feat(setup): a venue can be made of rooms (Made of column, helpers, problems)`.

---

### Task 2: `Problem` and the counting functions

**Files:**
- Modify: `ttgen/solver.py` (`Problem._rooms` ~45-68, `allowed` ~81-92, `allowed_at` ~100-106, `rule_problems` ~753-765)
- Test: `tests/test_combined.py`

**Interfaces:**
- Consumes: `spec.venue_parts`, `spec.single_rooms`, `spec.clean_name`.
- Produces on `Problem`: `P.parts: dict[str, list[str]]`; `P.singles(x) -> list[str]`; `P.off: dict[str, set[int]]` (venue -> period positions where a Must "Not available" Room rule holds for it; for a combined venue: its own rule's periods and those of each of its rooms); `P.seats[combined]` = its capacity, else the sum of its rooms' seats when all are known, else `None`; `P.room_kind[combined]` = the kind of its first room; `P.room_cap[combined]` = 1.
- Produces in `ttgen/solver.py` (module level, pure):
  - `under(E, parts) -> frozenset[str]`: the single rooms under a set of venues.
  - `weight(E, parts) -> int`: 1 if `E` holds any venue not in `parts`, else the fewest rooms of any venue in `E` (0 for an empty `E`).
  - `room_families(sets, every, parts) -> list[frozenset[str]]`: distinct, order stable: `under(E)` for each `E` in `sets`, `frozenset(parts[c])` for each combined venue `c` in `every`, and `under(every)`.

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: Run** `$PY tests/test_combined.py`. Expected: FAIL at `the_problem_knows_the_pair` (`AttributeError: 'Problem' object has no attribute 'parts'`).

- [ ] **Step 3: Implement.** In `_rooms`: every key of `room_kind`, `seats`, `only_for`, `room_cap` is `clean_name(v["room"])`; set `parts`, the combined venue's seats, kind and cap as in Interfaces; build `off` from the Must "Not available" Room rules (`rule_positions`); venue-rule names and the names in `rule_problems` (the `unknown` list and `V`) are matched through `clean_name`. `allowed`: when no venue seats the group and some venue of the kind is in `parts`, the set is the venues of `ok` with the most seats (unknown seats count as 0); otherwise today's line. `allowed_at`: after the venue rules, drop each combined venue `c` in `E` with any period of the lesson in `off[c]`. Add `under`, `weight`, `room_families` at module level.

- [ ] **Step 4: Run** `$PY tests/test_combined.py` (9 checks passed), then `$PY tests/test_rules.py`, `$PY tests/test_choices.py`, `$PY tests/smoke.py` after copying `solver.py` to the skill copy.

- [ ] **Step 5: Commit** `feat(solver): Problem knows a combined venue's rooms; counting functions`.

---

### Task 3: The model's room limits, handing out rooms, and the solver's own check

**Files:**
- Modify: `ttgen/solver.py` (the room block ~556-607 in `solve`), `ttgen/report.py` (`assign_rooms` 34-102, `check` ~140-146, `compromises` ~293)
- Test: `tests/test_combined.py`

**Interfaces:**
- Consumes: `P.parts`, `P.singles`, `P.off`, `under`, `weight`, `room_families`.
- Produces: `report.assign_rooms(res)` and `report.check(res)` follow the one rule; `check`'s line stays `Room over capacity: {single room} at {day} period {p}.`.

- [ ] **Step 1: Write the failing tests.** `assign_rooms` and `check` are tested on hand-placed lessons; the solve itself only with `--full`. If `assign_rooms` or `check` reads a key of a lesson that `placed` does not set, add it to `placed` with the value `solve` gives it.

```python
from ttgen import report  # noqa: E402

def placed(P, picks):
    """a result with the picked rows placed by hand: picks = [(row test, start, length)] -> res"""
    L = []
    for pred, start, ln in picks:
        r, u = rows_of(P, pred)[0]; L.append(dict(unit=u, part=[r], start=start, ln=ln, key=f"{u['id']}:{len(L)}"))
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
    probs, _ = report.check(res); assert any(p.startswith(f"Room over capacity: {S1} at ") for p in probs) and not any(S2 in p for p in probs if p.startswith("Room over"))
    res["lessons"][1]["rooms"][id(r3)] = PAIR
    probs, _ = report.check(res); assert sum(p.startswith("Room over capacity:") for p in probs) == 2   # both studios
t(the_check_counts_a_pair_lesson_in_each_room)

def a_solve_keeps_the_rule():   # slow: only with --full
    res = solver.solve(pair_school(), time_limit=240, workers=8, log=lambda *a: None); assert res["status"] in ("OPTIMAL", "FEASIBLE"), res["status"]
    probs, _ = report.check(res); assert not [p for p in probs if p.startswith("Room over capacity")] and not [p for p in probs if "TBC" in p], probs[:5]
    use = collections.defaultdict(list)
    for L in res["lessons"]:
        for r in L["part"]:
            room = L["rooms"][id(r)]
            if r["subject"] == "Design & Technology": assert room == PAIR
            if r["code"] in ("3DTP1", "4DTP1"): assert room in (S1, S2)
            for s in res["problem"].singles(room):
                for k in range(L["ln"]): use[(s, L["start"] + k)].append(id(L))
    assert all(len(set(v)) == 1 for v in use.values())
if "--full" in sys.argv: t(a_solve_keeps_the_rule)
```

- [ ] **Step 2: Run** `$PY tests/test_combined.py`. Expected: FAIL in `rooms_are_handed_out_by_the_one_rule` (the class and the group both get rooms).

- [ ] **Step 3: `assign_rooms`.** Replace the direct uses of `occ` with two inner helpers: `free(x, pos)`: every single room `s` of `x` has `occ[s][q] < cap.get(s, 1)` for `q` in `pos`, and, when `x` is a combined venue, `occ[x][q] == 0` (its own "Not available" mark); `take(x, pos, k=1)` / `give_back(x, pos)`: add or subtract on each single room of `x`. A "Not available" rule marks only its own target, as today. Everything else (the order rooms are tried, the make-way pass, rain rooms) stays, calling the helpers.

- [ ] **Step 4: `check` and `compromises`.** `rb` counts `(s, q)` for each single room `s` of the lesson's room. In `compromises`, "Not available" for a Room hits a lesson whose room is the target or has the target among its single rooms.

- [ ] **Step 5: The model in `solve`.** For a kind none of whose venues is in `P.parts`: today's loop, untouched. For a kind with a combined venue:
  - each entry of `need[kind]` keeps its `E`; its demand is `n * weight(E, P.parts)`;
  - for each `G` in `room_families({E ...}, every, P.parts)`: capacity `sum(P.room_cap[s] for s in G)`; members are the entries with `under(E) <= G`; busy runs are those of the single rooms in `G` (never a combined venue's own); `m.AddCumulative` as today, the `too_big` note only for `G == under(every)`;
  - the "rooms depend on when it starts" branch (today entered only when the row has venue rules) is also entered when `E` holds a combined venue `c` with `P.off[c]`, so a start that leaves the group no venue is forbidden.

- [ ] **Step 6: Run** `$PY tests/test_combined.py` (11 checks passed), then `$PY tests/test_combined.py --full` (12; allow five minutes), `$PY tests/test_typed.py`, `$PY tests/smoke.py`. Copy `solver.py` and `report.py` to the skill copy first.

- [ ] **Step 7: Commit** `feat(solver): room limits, room hand-out and the check follow combined venues`.

---

### Task 4: The staged solve and the setup's room sums

**Files:**
- Modify: `ttgen/staged.py` (~168-172), `checks.py` (`_room_fit` 65-108, the band sum in `_loads_and_rooms` ~242-248 and the oversize block after it)
- Test: `tests/test_combined.py`

**Interfaces:**
- Consumes: `P.parts`, `P.singles`, `under`, `weight`, `room_families`.
- Produces: `checks.room_sums(P) -> list[dict]`, one `dict(kind, rooms, need, have, all)` per sum (`rooms`: sorted single rooms; `need`: class-periods a cycle, rounded; `have`: rooms at a time times lesson periods; `all`: true for the sum over every room of the kind). `_room_fit(P)` keeps its return and its texts, built from `room_sums`. `staged._Run.hold_rules(room, wk, dy, span) -> list[dict]`.

- [ ] **Step 1: Write the failing tests**

```python
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

def a_band_needing_two_studios_is_not_helped_by_the_pair():
    sp = pair_school(); out = checks._loads_and_rooms(sp, Problem(sp))
    base = secondary(); want = [x for x in checks._loads_and_rooms(base, Problem(base)) if "rooms at once" in x[1]]
    assert [x for x in out if "rooms at once" in x[1]] == want
t(a_band_needing_two_studios_is_not_helped_by_the_pair)

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
```

Before Step 3, save today's findings of the plain sample for the comparison: `$PY -c "import json,checks; from ttgen.samples import secondary; print(json.dumps(checks.findings(secondary()), default=str, sort_keys=True))" > /tmp/plain-findings.json`, and after Step 3 run it again and `diff`: no difference.

- [ ] **Step 2: Run.** Expected: FAIL (`module 'checks' has no attribute 'room_sums'`).

- [ ] **Step 3: Implement.**
  - `staged._Run.hold_rules(self, room, wk, dy, span) -> list[dict]`: one Must "Not available" Room rule per single room of `room` (`self.P.singles`); the two places that append such a rule (a group's kept room, a rain room) call it.
  - `checks.room_sums(P)`: today's loop of `_room_fit` up to the `row = dict(...)` line, returning every row. For a kind with a combined venue, the sets are `room_families(...)`, a demand's weight is multiplied by `weight(E, P.parts)`, it belongs to a family when `under(E) <= G`, `rooms` lists the single rooms, `have` is `sum(room_cap) * slots` over them. Other kinds: today's sets and sums. `_room_fit` turns the rows into its "impossible" and "tight" findings with today's texts.
  - band sum: `kinds` counts venues that are not in `P.parts`.
  - after the oversize block: for each row whose room kind has a combined venue and `P.size(r, u) is None`, the warning `("lessons", f"{subject} {code, or the class for a whole-class row}: no group size is known, so it may be given any {kind}, {combined venue} included. Give its Students on step 5.")`.

- [ ] **Step 4: Run** `$PY tests/test_combined.py` (15 checks passed), the findings `diff` (empty), `$PY tests/smoke.py`, `$PY tests/test_typed.py`. Copy `staged.py` to the skill copy first.

- [ ] **Step 5: Commit** `feat(checks): staged holds and the room sums count single rooms`.

---

### Task 5: The returned timetable: model, checks, the half-venue warning, the database

**Files:**
- Modify: `ttgen/export.py` (rooms ~90-96, model ~112-130, `check_model` ~308-315), `ttgen/verify.py` (Room test ~154, `_only_in_venues` ~237-243, `deployment` ~99-104), `ttgen/database.py` (~80, ~116)
- Test: `tests/test_combined.py`

**Interfaces:**
- Consumes: `spec.venue_parts`, `spec.single_rooms`, `spec.clean_name`.
- Produces: `m["room_parts"]: dict[str, list[str]]` (always present on a new model; readers use `m.get("room_parts") or {}`); each `m["rooms"][i]` gains `parts: list[str]` (empty for an ordinary room); a combined venue's `capacity` is its own, else the sum of its rooms'. `check_model` text: `Room over capacity: {single room} on {when} (holds {cap} at once).`, and when a lesson counted there names a combined venue `C`: `Room over capacity: {single room} on {when} (holds {cap} at once; in use as part of {C}).` Database table `room_parts (venue TEXT, room TEXT)`.

- [ ] **Step 1: Write the failing tests.** Models come from the fixture's `model_for(sp, placed)`.

```python
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
    sp, m = a_model([]); m.pop("room_parts"); [r.pop("parts") for r in m["rooms"]]
    assert export.check_model(m)["ok"] in (True, False) and verify.deployment(m, sp) is not None
t(an_old_model_still_checks)
```

`verify.warning(...)` builds each warning; if its dict names the key differently from `"key"`, use that name.

- [ ] **Step 2: Run.** Expected: FAIL at `the_model_and_its_check` (`KeyError: 'room_parts'`).

- [ ] **Step 3: Implement.**
  - `export`: build `parts = venue_parts(spec["venues"])`; `rooms` rows get `parts` and the capacity rule above; `m["room_parts"] = parts`. `check_model`: `rb` counts each single room of the lesson's room; the line's first lesson (used for its place) is the first lesson standing on that single room in that period; the text as in Interfaces.
  - `verify`: the Room test is `x["room"] == tg or tg in single_rooms(x["room"], parts)`; `_only_in_venues` compares `clean_name` of both sides; in `deployment`, after the room-kind warning, one warning per key (id `dep:{k}:half`, kind `"deployment"`): the first lesson whose room is a single room of a combined venue `C`, with group size `n`, `seats(room) < n <= seats(C)`; text `f"{what} ({n} students) is in {room} ({seats} seats); {C} seats it."`. Group size: the number of students on the Students sheet holding the code; else the step 5 row's Students; else, for a whole-class row, the class's size; unknown: no warning.
  - `database.write_db`: `CREATE TABLE room_parts (venue TEXT, room TEXT)` filled from `m.get("room_parts")`; nothing else changes.

- [ ] **Step 4: Run** `$PY tests/test_combined.py` (20 checks passed), `$PY tests/test_verify.py`, `$PY tests/test_rules.py`, `$PY tests/smoke.py --full`. Copy `export.py`, `verify.py`, `database.py` to the skill copy first.

- [ ] **Step 5: Commit** `feat(step 8): the timetable's checks count a combined venue's rooms; half-venue warning; room_parts table`.

---

### Task 6: Moving lessons by hand: `Busy`, marks, room choices, the board

**Files:**
- Modify: `fixes.py` (`Busy.__init__` ~197-212, `_why` ~284-291, `marks` ~525-526, `choices` ~656-659), `draft.py` (the board payload ~391-395), `static/board.js` (new `roomsMeet`, exported), `static/app.js` (`bdBusyFor` ~3846-3859)
- Test: `tests/test_combined.py`, `tests/board.test.js`

**Interfaces:**
- Consumes: `m.get("room_parts")`, `spec.single_rooms`.
- Produces: `Busy.rooms(room) -> list[str]` (its single rooms); `Busy.at["r", s, d, q]` and `["h", s, d, q]` are keyed by single room; the refusal sentence stays exactly `f"{room} is in use then."` with `room` the venue the row names; the board payload gains `room_parts`; `Board.roomsMeet(parts, a, b) -> boolean` (true when venues `a` and `b` share a single room; `parts` may be undefined).

- [ ] **Step 1: Write the failing tests**

```python
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

def one_lessons_own_rows_do_not_clash():
    sp, p0, t1, t2, t3 = lessons_for()
    _, m = a_model([(0, p0, 1, ["1A"], "Design & Technology", ENTIRE, t1, PAIR)], sp)
    x = m["lessons"][0]; m["lessons"].append(dict(x, group="3DTP1", classes=["3A"], teachers=t3, room=S1))   # the same lesson id: a band's rows
    b = fixes.Busy(m); assert "room" not in fixes.marks(b, m["lessons"])
t(one_lessons_own_rows_do_not_clash)

def the_room_list_says_what_holds_a_studio():
    sp, p0, t1, t2, t3 = lessons_for()
    _, m = a_model([(0, p0, 1, ["1A"], "Design & Technology", ENTIRE, t1, PAIR), (0, p0, 1, ["3A"], "Design & Technology G3", "3DTP1", t3, "")], sp)
    g = next(x for x in m["lessons"] if x["group"] == "3DTP1"); out = fixes.choices(m, sp, m["days"], g["id"], "3DTP1")
    r = {x["room"]: x for x in out["rooms"]}; assert not r[S1]["free"] and not r[S2]["free"] and "Design & Technology" in r[S1]["holding"]
t(the_room_list_says_what_holds_a_studio)
```

In `tests/board.test.js`:

```js
t("roomsMeet: a venue meets its own rooms and itself, not its neighbour's", () => {
  const parts = { "Lab 1&2": ["Lab 1", "Lab 2"] };
  assert.strictEqual(Board.roomsMeet(parts, "Lab 1&2", "Lab 1"), true);
  assert.strictEqual(Board.roomsMeet(parts, "Lab 2", "Lab 1&2"), true);
  assert.strictEqual(Board.roomsMeet(parts, "Lab 1&2", "Lab 1&2"), true);
  assert.strictEqual(Board.roomsMeet(parts, "Lab 1", "Lab 2"), false);
  assert.strictEqual(Board.roomsMeet(undefined, "A", "A"), true);
  assert.strictEqual(Board.roomsMeet(undefined, "A", "B"), false);
  assert.strictEqual(Board.roomsMeet(parts, "", "Lab 1"), false);
});
```

- [ ] **Step 2: Run** both. Expected: FAIL (`'Busy' object has no attribute 'rooms'`; `Board.roomsMeet is not a function`).

- [ ] **Step 3: Implement.**
  - `Busy`: `self.parts = m.get("room_parts") or {}`; `rooms(room)`; the index loops over `self.rooms(x["room"])` for `"r"` and over the single rooms of each rain room for `"h"`.
  - `_why`: for each of the rows' own venues, in the rows' order: for each of its single rooms `s` and each period, the lessons at `("r", s)` not in `ignore` and not this lesson's own, plus the number of the rows' own venues standing on `s`, above `room_cap.get(s, 1)`, or a rain hold on `s`: return `f"{venue} is in use then."`. The rain lines use the same single-room test.
  - `marks`: `rooms` is the union of the rows' single rooms; the test is unchanged otherwise (other lesson ids only).
  - `choices`: `held` looks under each single room of `room`.
  - `draft.py`: the board dict gains `room_parts=m.get("room_parts") or {}`.
  - `Board.roomsMeet`; `bdBusyFor`'s room branch becomes `has = x => (x.rows || []).some(y => Board.roomsMeet(d.room_parts, y.room, fix.room))`.

- [ ] **Step 4: Run** `$PY tests/test_combined.py` (23 checks passed), `node tests/board.test.js`, `$PY tests/test_fixes.py`, `$PY tests/test_helper.py`, `$PY tests/test_board.py`, `$PY tests/test_fixes.py --full`, `$PY tests/test_helper.py --full`, `node --check static/app.js`.

- [ ] **Step 5: Commit** `feat(step 8): moving a lesson respects a combined venue's rooms`.

---

### Task 7: Step 1 on the page, and the rule picker

**Files:**
- Modify: `static/venueview.js`, `static/app.js` (the `vv*` functions ~998-1110, `venuesTable` ~1022-1027, `issues` ~705, the input handler ~1934-1938, the delete handler ~1763, the rule check ~808-845, the "rooms" picker ~2750-2756), `static/style.css`
- Test: `tests/venueview.test.js`

**Interfaces:**
- Produces on `VenueView` (pure; `spec` is the setup object):
  - `cleanName(s) -> string`
  - `parts(spec) -> { [venue]: string[] }` (same rule as `spec.venue_parts`)
  - `problems(spec) -> [{ vi, text, hard }]` (same texts and order as `spec.venue_problems`)
  - `canCombine(spec, vis) -> { ok: boolean, why: string }`
  - `suggestName(names) -> string`
  - `combine(spec, vis) -> number` (the new row's index; pushes the row)
  - `renameRoom(spec, was, now) -> number` (rows changed) and `dropRoom(spec, name) -> number`
  - `blocks(spec)` rooms gain `made_of: string[]`; a combined venue is last on its floor and is not counted in the block's `rooms` and `seats`.

- [ ] **Step 1: Write the failing tests** (append to `tests/venueview.test.js`; `fixture()` has B1-1 and B1-2, classrooms of 44 on Block B floor 1)

```js
const paired = () => { const s = fixture(); s.venues.push({ _id: "v9", room: "B1-1&2", kind: "classroom", capacity: 88, building: "Block B", floor: 1, made_of: ["B1-1", "B1-2"] }); return s; };
t("parts_and_clean_names", () => {
  assert.deepStrictEqual(VenueView.parts(paired()), { "B1-1&2": ["B1-1", "B1-2"] });
  assert.deepStrictEqual(VenueView.parts(fixture()), {});
  assert.strictEqual(VenueView.cleanName("  D&T  Lab 1 "), "D&T Lab 1");
  const s = paired(); s.venues[8].made_of = ["B1-1"]; assert.deepStrictEqual(VenueView.parts(s), {});
});
t("suggested_names", () => {
  assert.strictEqual(VenueView.suggestName(["D&T Lab 1", "D&T Lab 2"]), "D&T Lab 1&2");
  assert.strictEqual(VenueView.suggestName(["E3-2A", "E3-2B"]), "E3-2A&B");
  assert.strictEqual(VenueView.suggestName(["Hall", "Dance Studio"]), "Hall + Dance Studio");
  assert.strictEqual(VenueView.suggestName(["Lab 1", "Lab 2", "Lab 3"]), "Lab 1&2&3");
});
t("can_combine_says_why_not", () => {
  const s = paired(), ix = n => s.venues.findIndex(v => v.room === n);
  assert.deepStrictEqual(VenueView.canCombine(s, [ix("B2-1"), ix("B2-9")]), { ok: true, why: "" });
  assert.strictEqual(VenueView.canCombine(s, [ix("B2-1")]).why, "Tick two or more rooms to combine them.");
  assert.strictEqual(VenueView.canCombine(s, [ix("B2-1"), ix("B2-10")]).why, "Rooms of different kinds cannot be combined.");
  assert.strictEqual(VenueView.canCombine(s, [ix("B1-1"), ix("B2-1")]).why, "B1-1 is already in B1-1&2.");
  assert.strictEqual(VenueView.canCombine(s, [ix("B1-1&2"), ix("B2-1")]).why, "B1-1&2 is a combined venue already.");
  s.rules = [{ scope: "Room", target: "B2-9", rule: "At most N at once", number: 2, strength: "Must" }];
  assert.strictEqual(VenueView.canCombine(s, [ix("B2-1"), ix("B2-9")]).why, "B2-9 takes 2 groups at once, so it cannot be combined.");
});
t("combine_makes_the_row", () => {
  const s = fixture(), vi = VenueView.combine(s, [0, 1]), v = s.venues[vi];
  assert.deepStrictEqual([v.room, v.kind, v.capacity, v.building, String(v.floor), v.made_of], ["B1-1&2", "classroom", 88, "Block B", "1", ["B1-1", "B1-2"]]);
  const f = VenueView.blocks(s).find(b => b.block === "Block B").floors.find(f => f.floor === "1");
  assert.deepStrictEqual(f.rooms.map(r => [r.room, r.made_of]), [["B1-1", []], ["B1-2", []], ["B1-1&2", ["B1-1", "B1-2"]]]);
  assert.deepStrictEqual(VenueView.blocks(s).map(b => [b.block, b.rooms, b.seats]), [["Block A", 2, 50], ["Block B", 5, 198], ["", 1, 0]]);   // the pair adds no room and no seats
  const t2 = fixture(); t2.venues[1].capacity = ""; assert.strictEqual(t2.venues[VenueView.combine(t2, [0, 1])].capacity, null);
});
t("rename_and_delete_keep_it_whole", () => {
  const s = paired(); assert.strictEqual(VenueView.renameRoom(s, "B1-2", "B1-2x"), 1); assert.deepStrictEqual(s.venues[8].made_of, ["B1-1", "B1-2x"]);
  assert.strictEqual(VenueView.dropRoom(s, "B1-2x"), 1); assert.deepStrictEqual(s.venues[8].made_of, ["B1-1"]);
  assert.deepStrictEqual(VenueView.problems(s).map(p => [p.vi, p.text, p.hard]), [[8, "B1-1&2: a combined venue needs at least two rooms.", true]]);
  assert.deepStrictEqual(VenueView.problems(fixture()), []);
});
```

Also port each case of Task 1's `broken_ones_are_ordinary_rooms_and_are_reported` to `VenueView.problems` with the same texts (one `t(...)` with eight asserts).

- [ ] **Step 2: Run** `node tests/venueview.test.js`. Expected: FAIL, `VenueView.parts is not a function`.

- [ ] **Step 3: Implement the `VenueView` functions.** `suggestName`: when every name is `prefix + ending` with one shared prefix and endings that are a single run of digits or a single letter, `prefix + endings joined by "&"`; else the names joined by `" + "`. `combine`: kind of the first room, capacity the sum (or `null` when any is missing), block and floor of the first room, a fresh `_id` the way the page makes ids for a new room (`vvAddRoom` shows how), name made unique by adding `" (2)"`, `" (3)"` if taken.

- [ ] **Step 4: Wire the page.**
  - **Bar:** beside Move, `<button data-vcombine="1">Combine</button>`, disabled with `canCombine(...).why` as a muted line beside it when not ok. Handler `vvCombine()`: guard `locked("venues")`, call `combine`, clear the ticks, open the new card, one `save(); render();`, toast `Combined into ${name}. Its rooms stay as they are. Undo, at the top, takes it back.`
  - **Tile:** a combined venue's tile has class `vcombo` and always shows the line `made of ${made_of.join(" + ")}`; `style.css` gives `.vcombo` a dashed border in the kind's colour (one rule).
  - **Open card of a combined venue:** Room, Capacity (label "Seats"), For, Equipment, Configuration, Note as today; Kind is shown as text (`the kind of its rooms`), not a list; Block and Floor as today; one more wide field `Made of <input data-names="spec.venues.${vi}.made_of" list="roomNames">` with a datalist of the ordinary rooms of that kind.
  - **Table view:** a last column "Made of" with the same `data-names` input, empty for an ordinary room.
  - **Things to fix:** in `issues()`, `VenueView.problems(S.spec).forEach(p => add("venues", p.vi, p.text, p.hard))`.
  - **Names:** in the input handler, a value for `spec.venues.N.room` is stored as `VenueView.cleanName(value)` (empty stays `null`), and when it replaces a non-empty name, `VenueView.renameRoom(S.spec, was, now)` runs before the one `save()`. The venues delete handler calls `VenueView.dropRoom(S.spec, name)` before the splice.
  - **Rules:** `roomKind` (line ~808) is keyed by `VenueView.cleanName(v.room)`; `namesList(r.venues)` entries are cleaned before the `in roomKind` tests at ~834 and ~842. The "rooms" picker lists each venue once by its clean name, a combined venue as `${name} (${made_of.join(" + ")})` with `value` the clean name, and ticks by clean name.

- [ ] **Step 5: Run** `node tests/venueview.test.js`, every other `tests/*.test.js`, `node --check static/app.js`, `$PY tests/smoke.py`.

- [ ] **Step 6: Check in a browser, with the real pointer** (the controller gives the launch entry and a scratch data folder; sample school only). One line per check, saying it was a real click: tick two studios, Combine, the card opens with the suggested name and seats; Undo takes it back; rename a studio and the card's "made of" line follows; delete a studio and Things to fix shows "a combined venue needs at least two rooms."; in step 6 add "Only in venues" and tick the pair in the picker; type a room name with a space at the end and see it stored without it; load a saved setup whose room name ends in a space and whose rule names that room (the controller makes one by script): the rule shows no "not on step 1" message and the picker shows the room ticked.

- [ ] **Step 7: Commit** `feat(step 1): combine rooms into a venue; rules can pick it; room names are trimmed`.

---

### Task 8: The published timetable

**Files:**
- Modify: `ttgen/export.py` (`room_view` ~512-532, the rooms page list ~562-565, `html_data` ~984), `ttgen/timetable_page.html` (`roomView` ~214-222, `busyRooms` ~154, `renderFree` ~436-443)
- Test: `tests/test_combined.py`

**Interfaces:**
- Consumes: `m.get("room_parts")`, each room's `.get("parts")`.
- Produces: `html_data(...)["rooms"]` rows gain a sixth item, the venue's rooms (`[]` for an ordinary room); the page reads it as `info.parts`.

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: Run.** Expected: FAIL (Studio 1 has one cell).

- [ ] **Step 3: Implement in `export.py`.** `room_view(m, r)`: rows are the lessons whose room is `r` or has `r` among its single rooms; a cell drawn from a lesson in a combined venue `C` gets one more line, `with {the other rooms of C joined by ", "}, as {C}`; a combined venue's subtitle and `pdf_subtitle` end with ` · made of {rooms joined by " + "}`. The rooms branch of `all_views` yields a room when a lesson names it or names a combined venue it belongs to. `html_data` rooms rows end with `r.get("parts") or []`.

- [ ] **Step 4: Implement in `ttgen/timetable_page.html`,** mirroring Step 3: a helper `singles(name)` from the rooms' sixth item; `roomView` rows `L.filter(x => x.room === r || singles(x.room).includes(r))` with the same extra line and subtitle; `busyRooms` holds every single room of every lesson's room as well as the room named; in `renderFree`, a lesson (and a rain room) marks its room and each of its single rooms busy, and a combined venue is listed free only when it and all its rooms are unmarked. A page whose data has five-item room rows (published earlier) must draw as today.

- [ ] **Step 5: Run** `$PY tests/test_combined.py` (24 checks passed), `$PY tests/smoke.py --full`, `$PY tests/test_verify.py`. Copy `export.py` and `timetable_page.html` to the skill copy first. Then in a browser, on the sample with the pair and a small hand-made timetable (the controller provides it): Rooms tab lists both studios and the pair; Studio 2's page shows the class lesson with "with D&T Studio 1, as D&T Studio 1&2"; "Who's free" at that time lists neither studio nor the pair.

- [ ] **Step 6: Commit** `feat(publish): room pages and Who's free follow combined venues`.

---

### Task 9: The skill, the version, the README

**Files:**
- Modify: `skill/school-timetable-generator/SKILL.md`, `ttgen/spec.py` (`SKILL_VERSION`), `README.md`, `tests/test_parents.py:182-184`, `tests/test_rules.py:17`
- Test: `tests/test_combined.py`

**Interfaces:** none new.

- [ ] **Step 1: Write the failing test**

```python
def the_skill_explains_made_of():
    root = os.path.dirname(HERE); s = open(os.path.join(root, "skill", "school-timetable-generator", "SKILL.md"), encoding="utf-8").read()
    assert SPEC.SKILL_VERSION == "2026-11.9" and "Skill version: 2026-11.9" in s and "2026-11.9" in open(os.path.join(root, "README.md"), encoding="utf-8").read()
    for words in ("Made of", "combined venue", "room_parts", "takes every one of its rooms"): assert words in s, words
t(the_skill_explains_made_of)
```

- [ ] **Step 2: Run.** Expected: FAIL on the version.

- [ ] **Step 3: Write.**
  - Version `2026-11.9` in `ttgen/spec.py`, `SKILL.md` line 8, `README.md` line ~82, and the two tests that pin it.
  - `SKILL.md`, the sheet table's `1 Venues` row: add `Made of (rooms used together)`.
  - `SKILL.md`, after "A room holds one class at a time.": a paragraph in the skill's voice saying: a venue whose Made of lists rooms is a combined venue; a lesson there takes every one of its rooms, so nothing else may be in any of them then, and it is free only when all of them are; it takes one group at a time and adds no room to any count; seats decide who gets it (a class too big for one room fits only the combined venue), and where nothing seats a group it goes to the biggest venue of its kind; "Not available" on a room also closes the combined venue it is in.
  - `SKILL.md`, **Building it without the scripts**, the Rooms item: the counting of Task 2 (`under`, `weight`, the three kinds of family) in three or four sentences.
  - `SKILL.md`, the database line (~86): name the table `room_parts` (venue, room).
  - `README.md`: under the Venues part, four lines on combined venues for the committee (tick, Combine, what "made of" means, the limits), and `tests/test_combined.py` in the list of suites (~386).

- [ ] **Step 4: Run every suite in Global Constraints,** quick and `--full` (`test_typed`, `test_helper`, `test_fixes`, `smoke`, `test_combined`), `diff -rq ttgen skill/school-timetable-generator/scripts/ttgen -x __pycache__` (no output), `grep -n "console.log" static/*.js` (none new).

- [ ] **Step 5: Commit** `docs(skill): combined venues; skill 2026-11.9`.

---

### Task 10: The school's real setup, and the notes file

Done by the controller, not a builder: it reads private files. Counts only in anything written down.

- [ ] **Step 1:** Read the newest setup workbook (the highest version folder) with `reader.read_template`. In memory: replace "D&T Lab 1&2" by two 20-seat studios plus the pair (seats 44), the same for the food labs; drop the "At most N at once" rule on the old room. Record: `venue_problems` (expect none), the number of rows limited to each pair by `Problem.allowed`, the rows `checks._room_fit` raises before and after (expect nothing new), render time of step 1 if a scratch server is used.
- [ ] **Step 2:** Write `docs/superpowers/plans/2026-11-19-combined-venues-notes.md`: rulings made while building, known limits (spec's Limits; the model's limits being looser than the truth where a kind has a combined venue and other odd shapes), what was and was not tried in a browser, the counts from Step 1.
- [ ] **Step 3:** Commit `docs: combined venues notes`. No push, no pull request without the committee lead's word.

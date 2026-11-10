"""Plain-assert tests for the helper, ways to settle one warning: .venv/bin/python tests/test_helper.py"""
import copy, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, ROOT)
import fixes, helper  # noqa: E402
from ttgen import export, reader, verify  # noqa: E402
from ttgen.export import ENTIRE  # noqa: E402
from ttgen.samples import primary  # noqa: E402
n = 0
def t(f): global n; f(); n += 1

# the model-building helpers of tests/test_fixes.py, copied (importing that file would run its checks)
def lesson(i, d, p, n_, cls, subject, group, teachers, room="", level="", block=""):
    return dict(id=i, d=d, p=p, n=n_, level=level, block=block, classes=cls, subject=subject, group=group, teachers=teachers, room=room, ext=False, rain="")
SP = primary(); reader.derive(SP); DAYS = list(SP["day_structure"][SP["school"]["levels"][0]].keys()); LV = "P1"
def model_with(L, **over):
    """a model of the primary setup holding only the lessons L; over replaces setup fields (rules default to none)"""
    sp = dict(SP, **dict(dict(rules=[]), **over)); m = export._model(sp, DAYS, L); m["checked_setup"] = sp; return m, sp
def rows_of(m, i): return [x for x in m["lessons"] if x["id"] == i]

A, B = "1A", "1B"
OPEN = [1, 2, 3, 5, 6, 7, 8, 9, 10]   # lesson time of a P1 day in the sample: 0 is the assembly, 4 the recess, 11 on outside the day
def rule(target, rule_, a, b, strength="Must", scope="Class"):
    return dict(scope=scope, target=target, rule=rule_, week="Both", day="All", strength=strength, **{"from": a, "to": b})
def frozen(m): return copy.deepcopy(m["lessons"])
def one_of(ws, end): return next(w for w in ws if w["key"].endswith(end))

@t
def a_wrong_teacher_is_settled_by_giving_the_lesson_back():
    right, wrong, key = "Michelle Goh", "Sabrina Koh", "C:1A:Mathematics"
    m, sp = model_with([lesson(1, 0, 2, 1, [A], "Mathematics", ENTIRE, [wrong], level=LV), lesson(2, 1, 3, 1, [A], "Mathematics", ENTIRE, [wrong], level=LV)])
    before = frozen(m); w = one_of(verify.deployment(m, sp), "1A:Mathematics:teachers")
    assert helper.involved(m, w) == [1, 2] and helper.candidates(m, sp, DAYS, w) == [[dict(kind="teacher", key=key, teachers=[right])]]
    out = helper.suggest(m, sp, DAYS, w); s = out["suggestions"][0]
    assert s["fixes"] == [dict(kind="teacher", key=key, teachers=[right])] and s["state"] == "ok" and s["moved"] == 2, s
    assert s["text"] == f"Give Mathematics for {A} to {right}." and out["none"] is None and out["blocked"] == [] and len(out["suggestions"]) == 1
    assert s["disturbs"] == [f"{wrong} drops to 0 periods, {right} rises to 2."], s["disturbs"]
    c = helper.chain(m, sp, DAYS, s["fixes"]); assert c["state"] == "ok" and c["touched"] == {1, 2} and len(c["was"]) == 2 and c["texts"][0].endswith(f"is now taught by {right}, not {wrong}.")
    assert all(x["teachers"] == [right] for x in c["lessons"]) and m["lessons"] == before   # the cached model is never changed

@t
def a_lesson_breaking_a_rule_gets_moves_that_stop_breaking_it():
    m, sp = model_with([lesson(1, 1, 0, 1, [A], "Mathematics", ENTIRE, ["Michelle Goh"], level=LV), lesson(2, 1, 5, 1, [A], "Art", ENTIRE, ["Umairah Tan"], level=LV)],
                       rules=[rule(A, "Not in periods", 0, 1)])
    before = frozen(m); w = next(w for w in verify.rules(m, sp)[0] if w["where"]["id"] == 1)
    assert helper.involved(m, w) == [1]
    out = helper.suggest(m, sp, DAYS, w); S = out["suggestions"]
    assert [s["fixes"] for s in S] == [[dict(kind="move", id=1, d=1, p=q)] for q in (2, 3, 6)], S   # the same day first; the swap at period 5 moves two lessons
    assert [s["text"] for s in S] == [f"Move Mathematics for {A} to {DAYS[1]} period {q}." for q in (2, 3, 6)] and all(s["disturbs"] == ["Nothing else moves."] and s["moved"] == 1 for s in S)
    swap, ok = dict(kind="swap", a=1, b=2), dict(state="ok", why="", must=[], prefer=[])
    assert helper.say(m, sp, DAYS, swap) == f"Swap Mathematics for {A} with Art for {A} ({DAYS[1]} period 5)." and helper.disturbs(m, sp, DAYS, [swap], [ok]) == [f"Art for {A} moves to {DAYS[1]} period 0."]
    for s in S:
        L = helper.chain(m, sp, DAYS, s["fixes"])["lessons"]; assert helper.settles(m, sp, DAYS, w, L)
        assert not [v for v in verify.rules(dict(m, lessons=L), sp)[0] if fixes._subject(v) == fixes._subject(w)]
    assert not helper.settles(m, sp, DAYS, w, m["lessons"]) and m["lessons"] == before
    assert [helper.rank(m, sp, DAYS, s) for s in S] == sorted(helper.rank(m, sp, DAYS, s) for s in S)
    day = dict(key=f"rule:0:{A}|1", kind="rule", text="x", where=None); assert helper.involved(m, day) == [1, 2]   # a day-level key: that class's lessons that day

@t
def a_suggestion_never_trades_one_warning_for_another():       # Review Focus 1
    right, other = "Sabrina Koh", "Jasper Wong"
    m, sp = model_with([lesson(1, 0, 2, 1, [A], "English Language", ENTIRE, [right], level=LV), lesson(2, 0, 2, 1, [B], "English Language", ENTIRE, [right], level=LV)])
    w = next(w for w in verify.clashes(m) if w["where"] == dict(teacher=right))
    assert sorted(helper.involved(m, w)) == [1, 2]
    give = dict(kind="teacher", key="C:1A:English Language", teachers=[other])
    assert [give] in helper.candidates(m, sp, DAYS, w) and fixes.judge(m, sp, DAYS, give)["state"] == "ok"
    assert not helper.settles(m, sp, DAYS, w, helper.chain(m, sp, DAYS, [give])["lessons"])   # a new deployment difference: not settled
    out = helper.suggest(m, sp, DAYS, w); assert len(out["suggestions"]) == 3 and not [s for s in out["suggestions"] if s["fixes"][0]["kind"] == "teacher"], out
    assert all(s["state"] == "ok" and s["fixes"][0]["kind"] == "move" for s in out["suggestions"])
    assert helper.settles(m, sp, DAYS, w, helper.chain(m, sp, DAYS, out["suggestions"][0]["fixes"])["lessons"])
    pref = rule(A, "Not in periods", 5, 10, "Prefer")
    m, sp = model_with([lesson(1, 0, 1, 1, [A], "Mathematics", ENTIRE, ["Michelle Goh"], level=LV)], rules=[rule(A, "Not in periods", 1, 3), pref])
    w = next(w for w in verify.rules(m, sp)[0]); out = helper.suggest(m, sp, DAYS, w); S = out["suggestions"]
    assert len(S) == 3 and all(s["state"] == "prefer" and s["fixes"][0]["kind"] == "move" and s["fixes"][0]["p"] in range(5, 11) for s in S), S
    assert all(len(s["disturbs"]) == 1 and s["disturbs"][0].startswith(f"Rule Class · {A} · Not in periods: ") and s["disturbs"][0].endswith("(Prefer)") for s in S), S

@t
def missing_extra_and_venue():
    m, sp = model_with([lesson(1, 2, 5, 1, [A], "Music", ENTIRE, ["Umairah Tan"], room="Music Room", level=LV), lesson(2, 1, 6, 1, [A], "Other", ENTIRE, ["Umairah Tan"], level=LV)])
    ws = verify.deployment(m, sp); w = one_of(ws, "1A:Music:periods")
    out = helper.suggest(m, sp, DAYS, w); S = out["suggestions"]
    assert len(S) == 3 and all(s["fixes"][0]["kind"] == "add" and s["fixes"][0]["n"] == 1 and s["text"].endswith("(1 period).") for s in S), S
    assert S[0]["text"] == f"Add Music for {A} on {DAYS[0]} period 1 (1 period)." and S[0]["fixes"][0]["room"] == "Music Room"
    assert helper.involved(m, w) == [1]
    w = one_of(ws, "1A:Other:extra"); S = helper.suggest(m, sp, DAYS, w)["suggestions"]
    assert [s["fixes"] for s in S] == [[dict(kind="delete", id=2)]] and S[0]["text"] == f"Delete Other for {A} on {DAYS[1]} period 6."
    m, sp = model_with([lesson(1, 2, 5, 1, [A], "Music", ENTIRE, ["Umairah Tan"], room="1-01", level=LV)])
    w = one_of(verify.deployment(m, sp), "1A:Music:venue"); S = helper.suggest(m, sp, DAYS, w)["suggestions"]
    assert [s["text"] for s in S] == [f"Put Music for {A} in Music Room."] and S[0]["fixes"] == [dict(kind="room", id=1, group=ENTIRE, room="Music Room")], S
    over = [lesson(1, 2, 5, 1, [A], "Music", ENTIRE, ["Umairah Tan"], room="Music Room", level=LV), lesson(3, 3, 5, 1, [A], "Music", ENTIRE, ["Umairah Tan"], room="Music Room", level=LV),
            lesson(4, 4, 5, 1, [A], "Music", ENTIRE, ["Umairah Tan"], room="Music Room", level=LV)]
    m, sp = model_with(over); w = one_of(verify.deployment(m, sp), "1A:Music:periods")
    S = helper.suggest(m, sp, DAYS, w)["suggestions"]; assert [s["fixes"][0] for s in S] == [dict(kind="delete", id=i) for i in (1, 3, 4)], S

@t
def nothing_to_suggest_is_a_sentence():                         # Review Focus 4
    m, sp = model_with([lesson(1, 0, 2, 1, [A], "Mathematics", ENTIRE, ["Michelle Goh"], level=LV)])
    for w in (dict(key="typed:1:none", kind="typed", text="x", where=None), dict(key="choice:x", kind="choice", text="x", where=None),
              dict(key="clash:Room over capacity: R1 on Mon period 2.", kind="clash", text="x", where=None), dict(key="rule:0:1A|Maths|0|0", kind="rule", text="x", where=dict(cls="1A", day="Mon", period=0, id=999, row="Entire Class"))):
        out = helper.suggest(m, sp, DAYS, w); assert out == dict(suggestions=[], none=helper.NOTHING, blocked=[]), (w, out)
    assert helper.NOTHING == "The app has no suggestion for this one. Select a lesson on the grid to see where it can go."

@t
def blocked_when_nothing_passes():
    t0 = "Sabrina Koh"; fill = [(d, p) for d in range(len(DAYS)) for p in OPEN if (d, p) != (0, 1)]
    L = [lesson(1, 0, 1, 1, [A], "English Language", ENTIRE, [t0], level=LV)] + [lesson(10 + k, d, p, 1, [B], "Other", ENTIRE, [t0], level=LV) for k, (d, p) in enumerate(fill)]
    m, sp = model_with(L, rules=[rule(A, "Not in periods", 1, 1)])
    w = next(w for w in verify.rules(m, sp)[0] if w["where"]["id"] == 1); out = helper.suggest(m, sp, DAYS, w)
    assert out["suggestions"] == [] and out["none"] == "Nothing settles this without breaking a rule or a clash." and 1 <= len(out["blocked"]) <= 3, out
    assert all(set(b) == {"text", "why"} and b["text"].startswith(f"Move English Language for {A} to ") and b["why"] == f"{t0} is teaching Other for {B} then." for b in out["blocked"]), out

@t
def blocker_names_the_lesson_in_the_way():
    t0 = "Sabrina Koh"
    m, sp = model_with([lesson(1, 0, 2, 1, [A], "English Language", ENTIRE, [t0], level=LV), lesson(2, 1, 3, 1, [B], "Other", ENTIRE, [t0], level=LV),
                        lesson(3, 2, 3, 1, [B], "Art", ENTIRE, ["Umairah Tan"], room="1-01", level=LV)])
    b = fixes.Busy(m); rows = rows_of(m, 1)
    assert b.clash(rows, 1, 3, 1, ignore={1}) == f"{t0} is teaching Other for {B} then." and b.blocker(rows, 1, 3, 1, ignore={1}) == 2
    assert b.clash(rows, 3, 3, 1, ignore={1}) is None and b.blocker(rows, 3, 3, 1, ignore={1}) is None
    roomy = [dict(rows[0], room="1-01")]
    assert b.clash(roomy, 2, 3, 1, ignore={1}) == "1-01 is in use then." and b.blocker(roomy, 2, 3, 1, ignore={1}) is None   # a room is not a lesson in the way

print(f"{n} checks passed")

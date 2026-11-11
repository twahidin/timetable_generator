"""Plain-assert tests for the helper, ways to settle one warning: .venv/bin/python tests/test_helper.py"""
import copy, os, subprocess, sys, tempfile, time
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
    assert [s["text"] for s in S] == [f"Move Mathematics for {A} from {DAYS[1]} period 0 to {DAYS[1]} period {q}." for q in (2, 3, 6)] and all(s["disturbs"] == ["Nothing else moves."] and s["moved"] == 1 for s in S)
    swap, ok = dict(kind="swap", a=1, b=2), dict(state="ok", why="", must=[], prefer=[])
    assert helper.say(m, sp, DAYS, swap) == f"Swap Mathematics for {A} ({DAYS[1]} period 0) with Art for {A} ({DAYS[1]} period 5)." and helper.disturbs(m, sp, DAYS, [swap], [ok]) == [f"Art for {A} moves to {DAYS[1]} period 0."]
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
    assert all(set(b) == {"text", "why"} and b["text"].startswith(f"Move English Language for {A} from ") and b["why"] == f"{t0} is teaching Other for {B} then." for b in out["blocked"]), out

@t
def a_new_difference_is_not_settling_even_when_another_goes():   # review round 1
    m, sp = model_with([lesson(1, 2, 5, 3, [A], "Music", ENTIRE, ["Umairah Tan"], room="Music Room", level=LV)])
    w = one_of(verify.deployment(m, sp), "1A:Music:periods"); gone = helper.chain(m, sp, DAYS, [dict(kind="delete", id=1)])["lessons"]
    assert "dep:C:1A:Music:missing" in {v["key"] for v in verify.deployment(dict(m, lessons=gone), sp)}
    assert not helper.settles(m, sp, DAYS, w, gone)   # periods traded for missing: one difference for another
    out = helper.suggest(m, sp, DAYS, w); assert not [b for b in out["blocked"] if b["text"].startswith("Delete")], out
    m, sp = model_with([lesson(1, 0, 2, 1, [A], "Mathematics", ENTIRE, ["Sabrina Koh"], level=LV), lesson(2, 1, 2, 1, [A], "English Language", ENTIRE, ["Michelle Goh"], level=LV)])
    ws = verify.deployment(m, sp); w = one_of(ws, "1A:Mathematics:teachers"); assert one_of(ws, "1A:English Language:teachers")
    L = helper.chain(m, sp, DAYS, [dict(kind="teacher", key="C:1A:Mathematics", teachers=["Michelle Goh"])])["lessons"]
    assert helper.settles(m, sp, DAYS, w, L)   # the English difference was there before: not new

@t
def the_none_sentences_and_a_row_with_no_teacher():   # review round 1
    m, sp = model_with([lesson(1, 0, 1, 1, [A], "Mathematics", ENTIRE, ["Michelle Goh"], level=LV)], rules=[rule(A, "Not in periods", 1, 10)])
    w = next(w for w in verify.rules(m, sp)[0]); assert helper.candidates(m, sp, DAYS, w)   # every move still breaks it: nothing settles, nothing is refused
    assert helper.suggest(m, sp, DAYS, w) == dict(suggestions=[], none="The app found no fix that settles this. Select a lesson on the grid to see where it can go.", blocked=[])
    rows = [dict(x, teachers=[]) if x["classes"] == [A] and x["subject"] == "Mathematics" and x["code"] == ENTIRE else x for x in SP["lessons"]]
    m, sp = model_with([lesson(1, 0, 2, 1, [A], "Mathematics", ENTIRE, ["Sabrina Koh"], level=LV)], lessons=rows)
    w = one_of(verify.deployment(m, sp), "1A:Mathematics:teachers")
    assert helper.candidates(m, sp, DAYS, w) == [] and helper.suggest(m, sp, DAYS, w)["none"] == helper.NOTHING

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

@t
def nothing_refused_shows_is_not_breaking_a_rule():   # carried from Task 1's review: NONE_PASS only with a blocked entry
    t0 = "Sabrina Koh"; fill = [(d, p) for d in range(len(DAYS)) for p in OPEN if (d, p) != (0, 1)]
    L = [lesson(1, 0, 1, 1, [A], "English Language", ENTIRE, [t0], level=LV)] + [lesson(10 + k, d, p, 1, [B], "Other", ENTIRE, [t0], level=LV) for k, (d, p) in enumerate(fill)]
    m, sp = model_with(L, rules=[rule(A, "Not in periods", 1, 10)])   # every move is refused (a clash) and would not settle it anyway
    w = next(w for w in verify.rules(m, sp)[0] if w["where"]["id"] == 1)
    assert helper.suggest(m, sp, DAYS, w) == dict(suggestions=[], none=helper.NO_FIX, blocked=[])
    assert helper.NO_FIX == "The app found no fix that settles this. Select a lesson on the grid to see where it can go."

# a frame for the pairs: lesson 1 of 1A (Sabrina Koh) sits in period 0, which a Must rule forbids; 1A's other lesson time is
# full of Art except S and a_free; Sabrina Koh teaches lesson 2 (1B) at S; 1B's lesson time is full of Music except S and b_free
T0, S0 = "Sabrina Koh", (2, 3)
def frame(a_free=(), b_free=((3, 5),), block=False):
    every = [(d, p) for d in range(len(DAYS)) for p in OPEN]
    L = [lesson(1, 0, 0, 1, [A], "English Language", ENTIRE, [T0], level=LV)]
    L += [lesson(2, *S0, 1, [B], "Other", g, [t], level=LV, block="BX") for g, t in (("GX1", T0), ("GX2", "Benjamin Teo"), ("GX3", "Charmaine Yeo"))] if block \
        else [lesson(2, *S0, 1, [B], "Other", ENTIRE, [T0], level=LV)]
    L += [lesson(20 + k, d, p, 1, [A], "Art", ENTIRE, ["Umairah Tan"], level=LV) for k, (d, p) in enumerate(s for s in every if s != S0 and s not in a_free)]
    L += [lesson(200 + k, d, p, 1, [B], "Music", ENTIRE, ["Jasper Wong"], level=LV) for k, (d, p) in enumerate(s for s in every if s != S0 and s not in b_free)]
    m, sp = model_with(L, rules=[rule(A, "Not in periods", 0, 0)]); w = next(w for w in verify.rules(m, sp)[0] if w["where"]["id"] == 1); return m, sp, w

@t
def a_pair_frees_the_slot_first():
    m, sp, w = frame(); before = frozen(m)
    assert helper.candidates(m, sp, DAYS, w) == []   # every single move is a swap into the assembly or the clash at S
    out = helper.suggest(m, sp, DAYS, w); S = out["suggestions"]
    first, second = dict(kind="move", id=2, d=3, p=5), dict(kind="move", id=1, d=S0[0], p=S0[1])
    assert len(S) == 1 and S[0]["fixes"] == [first, second] and S[0]["state"] == "ok" and S[0]["moved"] == 2, out
    assert S[0]["text"] == f"Move Other for {B} from {DAYS[2]} period 3 to {DAYS[3]} period 5. Then Move English Language for {A} from {DAYS[0]} period 0 to {DAYS[2]} period 3.", S[0]["text"]
    assert S[0]["disturbs"] == [f"Other for {B} moves to {DAYS[3]} period 5."], S[0]["disturbs"]
    c = helper.chain(m, sp, DAYS, S[0]["fixes"]); assert c["state"] == "ok" and [j["state"] for j in c["steps"]] == ["ok", "ok"]
    assert fixes.judge(m, sp, DAYS, second)["state"] == "no"   # alone, the second is a clash
    L = fixes.apply(m["lessons"], S[0]["fixes"], sp, DAYS); assert not L["problems"]
    assert not [v for v in verify.rules(dict(m, lessons=L["lessons"]), sp)[0] if (v["where"] or {}).get("id") == 1] and helper.settles(m, sp, DAYS, w, c["lessons"])
    assert out["none"] is None and out["blocked"] == [] and m["lessons"] == before

@t
def singles_come_before_pairs_and_three_at_most():
    m, sp, w = frame(a_free=((1, 2), (1, 6), (4, 7))); out = helper.suggest(m, sp, DAYS, w); S = out["suggestions"]
    assert len(S) == 3 and all(len(s["fixes"]) == 1 for s in S), S
    assert helper.pairs(m, sp, DAYS, w, S) == [] and helper.pairs(m, sp, DAYS, w, [])   # pairs exist, but three singles are enough
    m, sp, w = frame(a_free=((4, 7),), b_free=((3, 5), (1, 6))); S = helper.suggest(m, sp, DAYS, w)["suggestions"]
    assert [len(s["fixes"]) for s in S] == [1, 2, 2] and S[0]["fixes"] == [dict(kind="move", id=1, d=4, p=7)], S
    assert {s["fixes"][0]["d"] for s in S[1:]} == {1, 3} and all(s["fixes"][1] == dict(kind="move", id=1, d=S0[0], p=S0[1]) for s in S[1:])
    assert [helper.rank(m, sp, DAYS, s) for s in S] == sorted(helper.rank(m, sp, DAYS, s) for s in S)
    P = helper.pairs(m, sp, DAYS, w, S[:1]); assert 1 <= len(P) <= 40 and all(len(fx) == 2 for fx in P)
    m, sp, w = frame(b_free=tuple((d, p) for d in range(len(DAYS)) for p in OPEN if (d, p) != S0))   # 1B empty but for lesson 2: many moves of it
    assert len(helper.pairs(m, sp, DAYS, w, [])) == 3   # one slot in the way, three of the blocker's moves
    near = [fx[0] for fx in helper.pairs(m, sp, DAYS, w, [])]; assert all(f["d"] == S0[0] for f in near), near   # the nearest day first

@t
def a_teacher_handback_after_moving_the_lesson_in_the_way():
    right, wrong, F = "Michelle Goh", "Sabrina Koh", (1, 3)
    every = [(d, p) for d in range(len(DAYS)) for p in OPEN]
    L = [lesson(1, 0, 2, 1, [A], "Mathematics", ENTIRE, [wrong], level=LV), lesson(2, 0, 2, 1, [B], "Other", ENTIRE, [right], level=LV)]
    L += [lesson(200 + k, d, p, 1, [B], "Music", ENTIRE, ["Jasper Wong"], level=LV) for k, (d, p) in enumerate(s for s in every if s not in ((0, 2), F))]
    m, sp = model_with(L); before = frozen(m); w = one_of(verify.deployment(m, sp), "1A:Mathematics:teachers")
    give = dict(kind="teacher", key="C:1A:Mathematics", teachers=[right]); j = fixes.judge(m, sp, DAYS, give)
    assert j["state"] == "no" and j["why"] == f"{right} is teaching Other for {B} then."
    out = helper.suggest(m, sp, DAYS, w); S = out["suggestions"]
    assert len(S) == 1 and S[0]["fixes"] == [dict(kind="move", id=2, d=F[0], p=F[1]), give] and S[0]["state"] == "ok" and S[0]["moved"] == 2, out
    assert S[0]["text"] == f"Move Other for {B} from {DAYS[0]} period 2 to {DAYS[1]} period 3. Then Give Mathematics for {A} to {right}."
    assert S[0]["disturbs"] == [f"Other for {B} moves to {DAYS[1]} period 3.", f"{wrong} drops to 0 periods, {right} rises to 2."], S[0]["disturbs"]
    assert helper.chain(m, sp, DAYS, S[0]["fixes"])["state"] == "ok" and m["lessons"] == before

@t
def a_block_lesson_counts_once():                               # Review Focus 5
    m, sp, w = frame(block=True); before = frozen(m); S = helper.suggest(m, sp, DAYS, w)["suggestions"]
    assert len(S) == 1 and S[0]["fixes"] == [dict(kind="move", id=2, d=3, p=5), dict(kind="move", id=1, d=S0[0], p=S0[1])] and S[0]["moved"] == 2, S
    c = helper.chain(m, sp, DAYS, S[0]["fixes"]); assert len(c["was"]) == 4 and all((x["d"], x["p"]) == (3, 5) for x in c["lessons"] if x["id"] == 2)
    assert m["lessons"] == before

@t
def two_moves_to_the_same_slot_read_differently_and_each_names_where_its_lesson_is_now():
    T = "Michelle Goh"   # a double and a single lesson of one class and subject, in a clash at period 6: either can go to the same open slot
    m, sp = model_with([lesson(1, 0, 5, 2, [A], "Mathematics", ENTIRE, [T], level=LV), lesson(2, 0, 6, 1, [A], "Mathematics", ENTIRE, [T], level=LV)])
    w = next(w for w in verify.clashes(m) if w["where"] == dict(teacher=T))
    S = helper.suggest(m, sp, DAYS, w, limit=50)["suggestions"]
    to = lambda s: (s["fixes"][0]["d"], s["fixes"][0]["p"]); same = [(a, b) for a in S for b in S if a is not b and a["fixes"][0]["id"] == 1 and b["fixes"][0]["id"] == 2 and to(a) == to(b)]
    assert same, [s["text"] for s in S]
    for a, b in same:
        assert a["text"] != b["text"], a["text"]
        assert a["text"] == f"Move Mathematics for {A} from {DAYS[0]} period 5 to {DAYS[to(a)[0]]} period {to(a)[1]}." and b["text"] == f"Move Mathematics for {A} from {DAYS[0]} period 6 to {DAYS[to(b)[0]]} period {to(b)[1]}.", (a["text"], b["text"])
    assert len({s["text"] for s in S}) == len(S)

@t
def the_second_fix_of_a_pair_names_the_slot_its_lesson_is_in_after_the_first():
    m, sp = model_with([lesson(1, 0, 2, 1, [A], "Mathematics", ENTIRE, ["Michelle Goh"], level=LV)])
    first, second = dict(kind="move", id=1, d=1, p=3), dict(kind="move", id=1, d=2, p=6)
    assert helper.says(m, sp, DAYS, [first, second]) == f"Move Mathematics for {A} from {DAYS[0]} period 2 to {DAYS[1]} period 3. Then Move Mathematics for {A} from {DAYS[1]} period 3 to {DAYS[2]} period 6."

if "--full" in sys.argv:
    SOLVED = []
    def solved_primary():
        """the primary sample solved as tests/test_fixes.py --full does (copied: importing that file would run its checks) -> (m, days)"""
        if SOLVED: return SOLVED[0]
        work = tempfile.mkdtemp(); setup, tt = os.path.join(work, "setup.xlsx"), os.path.join(work, "timetable.xlsx"); env = dict(os.environ, PYTHONPATH=ROOT)
        subprocess.run([sys.executable, "-m", "ttgen", "sample", "primary", "--out", setup], check=True, env=env, cwd=ROOT, capture_output=True)
        done = subprocess.run([sys.executable, "-m", "ttgen", "solve", setup, "--out", tt, "--time", "30"], env=env, cwd=ROOT, capture_output=True)
        assert done.returncode == 0 and os.path.exists(tt), "The solve did not finish in the time given, so there is no timetable to check."
        m = export.model_from_files(setup, tt); SOLVED.append((m, m["days"])); return SOLVED[0]

    def rebuilt(m, sp, days, lessons):
        m2 = export._model(sp, days, lessons, recess={c: [tuple(x) for x in v] for c, v in m["recess"].items()})
        m2["checked_setup"] = sp; m2["rule_report"] = []; m2["choice_problems"] = []; return m2

    def spoiled_primary():
        """the solved primary sample with five lessons moved into each other, one teacher swapped, one lesson deleted, one duplicated"""
        m, days = solved_primary(); sp = m["checked_setup"]; by = {}
        for x in m["lessons"]: by.setdefault(x["id"], []).append(x)
        whole = [i for i, r in by.items() if len(r) == 1 and r[0]["group"] == ENTIRE and r[0]["n"] == 1 and not r[0]["block"]]
        fx, used = [], set()
        for i in whole:   # onto the slot of another one-period lesson of its class
            if len(fx) == 5: break
            x = by[i][0]; y = next((by[j][0] for j in whole if j != i and j not in used and i not in used and by[j][0]["classes"] == x["classes"] and by[j][0]["d"] != x["d"]), None)
            if y: fx.append(dict(kind="move", id=i, d=y["d"], p=y["p"])); used |= {i, y["id"]}
        rest = [i for i in whole if i not in used]; x = by[rest[0]][0]; key = verify._kstr(fixes._row_key(x))
        other = next(t["name"] for t in sp["teachers"] if t["name"] not in x["teachers"])
        fx += [dict(kind="teacher", key=key, teachers=[other]), dict(kind="delete", id=rest[1])]
        y = by[rest[2]][0]; fx.append(dict(kind="add", key=verify._kstr(fixes._row_key(y)), d=y["d"], p=y["p"] + 1 if y["p"] + 1 < m["NP"] else y["p"] - 1, n=1, room=""))
        r = fixes.apply(m["lessons"], fx, sp, days); assert not r["problems"], r["problems"]
        return rebuilt(m, sp, days, r["lessons"]), sp, days

    @t
    def every_warning_of_a_spoiled_timetable_is_answered_quickly_and_truly():
        m, sp, days = spoiled_primary(); ws = verify.warnings(m)["warnings"]; dep0 = {v["key"] for v in verify.deployment(m, sp)}
        assert {w["kind"] for w in ws} >= {"clash", "deployment"}, {w["kind"] for w in ws}
        slow, offered, pairs = 0.0, 0, 0
        for w in ws:
            t0 = time.time(); out = helper.suggest(m, sp, days, w); dt = time.time() - t0; slow = max(slow, dt); assert dt < 2, (w["key"], dt)
            assert len({s["text"] for s in out["suggestions"]}) == len(out["suggestions"]), (w["key"], [s["text"] for s in out["suggestions"]])   # never two lines that read the same
            for s in out["suggestions"]:
                offered += 1; pairs += len(s["fixes"]) == 2
                assert helper.chain(m, sp, days, s["fixes"])["state"] in ("ok", "prefer"), (w["key"], s["text"])
                L = fixes.apply(m["lessons"], s["fixes"], sp, days); assert not L["problems"], L["problems"]
                m2 = rebuilt(m, sp, days, L["lessons"])
                assert w["key"] not in {x["key"] for x in verify.warnings(m2)["warnings"]}, (w["key"], s["text"])   # the full check agrees the warning is gone
                assert not {v["key"] for v in verify.deployment(m2, sp)} - dep0 - {w["key"]}, (w["key"], s["text"])   # and no new step 5 difference
        print(f"  {len(ws)} warnings, {offered} suggestions ({pairs} pairs), the slowest {slow:.2f} s")

print(f"{n} checks passed")

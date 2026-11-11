"""Plain-assert tests for typed.py, the typed request read into an ask (no network, no key): .venv/bin/python tests/test_typed.py"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, ROOT)
import typed, fixes, helper  # noqa: E402
from ttgen import export, reader  # noqa: E402
from ttgen.export import ENTIRE  # noqa: E402
from ttgen.samples import primary  # noqa: E402
n = 0
def t(f): global n; typed._seen.clear(); f(); n += 1

ASK = dict(understood=True, reply="Move PE for 2A off Friday.", action="move", classes=["2A"], subject="PE", teacher="", group="", from_day="", from_period=-1,
           to_days=[], not_days=["Fri"], to_period_from=-1, to_period_to=-1, new_teacher="", new_room="", keep=[])

class env:
    """patch os.environ for a block: env(A="1", B=None) (None removes)"""
    def __init__(s, **kw): s.kw = kw
    def __enter__(s):
        s.old = {k: os.environ.get(k) for k in s.kw}
        for k, v in s.kw.items(): os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
    def __exit__(s, *a):
        for k, v in s.old.items(): os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)

@t
def a_good_answer_is_returned_as_the_ask():
    assert typed.read("move PE for 2A off Friday", call=lambda w: dict(ASK)) == dict(ok=True, ask=ASK)

@t
def every_failure_of_the_call_is_the_one_sentence():
    def boom(kind):
        def call(w): raise kind
        return call
    for e in (TimeoutError("t"), RuntimeError("sk-ant-secret in the message"), KeyError("x"), ValueError("refusal")):
        out = typed.read("move PE off Friday", call=boom(e)); assert out == dict(ok=False, error=typed.FAILED), out
    for bad in (None, "text", {}, dict(ASK, action="delete"), dict(ASK, classes="2A"), {k: v for k, v in ASK.items() if k != "keep"}, dict(ASK, extra=1), dict(ASK, subject="x" * 201),
                dict(ASK, classes=["c"] * 21), dict(ASK, understood=1), dict(ASK, from_period=True), dict(ASK, from_period="3"), dict(ASK, keep=[1]), dict(ASK, not_days=[None])):
        assert typed.read("move PE off Friday", call=lambda w, bad=bad: bad) == dict(ok=False, error=typed.FAILED), bad
    for bad in (dict(ASK, from_day="Friday please"), dict(ASK, not_days=["Friday"]), dict(ASK, to_days=["odd Fri"]), dict(ASK, from_period=-5), dict(ASK, from_period=61), dict(ASK, to_period_from=10**100), dict(ASK, to_period_to=-2)):
        assert typed.check(bad) is False, bad
    assert typed.check(dict(ASK, from_day="Odd Fri", not_days=["Even Mon", "Tue"], to_days=["Thu"], from_period=60, to_period_from=-1)) is True and typed.check(dict(ASK, from_day="")) is True
    assert typed.check(ASK) is True and typed.check(dict(ASK, from_period=4, classes=["c"] * 20, subject="x" * 200)) is True

@t
def long_and_blank_words_never_reach_the_call():
    called = []
    assert typed.read("x" * 301, call=called.append)["error"] == typed.TOO_LONG and typed.read("   ", call=called.append) == dict(ok=False, error="Type what you want changed.") and not called
    assert typed.read("x" * 300, call=lambda w: dict(ASK))["ok"] is True

@t
def the_cost_guard_stops_the_thirty_first_request():
    clock = [1000.0]; typed._now = lambda: clock[0]; calls = []
    def call(w): calls.append(w); return dict(ASK)
    try:
        for i in range(30): clock[0] += 1; assert typed.read("move PE off Friday", call=call)["ok"], i
        assert typed.read("move PE off Friday", call=call) == dict(ok=False, error=typed.BUSY) and len(calls) == 30
        assert typed.read("", call=call)["error"] != typed.BUSY and typed.read("x" * 400, call=call)["error"] == typed.TOO_LONG   # refused words do not count
        clock[0] += 601; assert typed.read("move PE off Friday", call=call)["ok"] and len(calls) == 31
    finally: import time; typed._now = time.monotonic

@t
def enabled_follows_the_key_and_the_mock_setting():
    with env(ANTHROPIC_API_KEY=None, TYPED_REQUEST_MODEL=None): assert typed.enabled() is False and typed.model() == "claude-opus-5-5"
    with env(ANTHROPIC_API_KEY="  ", TYPED_REQUEST_MODEL=None): assert typed.enabled() is False
    with env(ANTHROPIC_API_KEY="k", TYPED_REQUEST_MODEL=None): assert typed.enabled() is True
    with env(ANTHROPIC_API_KEY=None, TYPED_REQUEST_MODEL="mock"): assert typed.enabled() is True and typed.model() == "mock"
    with env(ANTHROPIC_API_KEY=None, TYPED_REQUEST_MODEL=" other-model "): assert typed.enabled() is False and typed.model() == "other-model"
    with env(ANTHROPIC_API_KEY=None, TYPED_REQUEST_MODEL="  "): assert typed.model() == "claude-opus-5-5"

@t
def the_mock_reader_understands_its_two_shapes():
    a = typed._mock("Move PE for 2A off Friday"); assert typed.check(a) and a["understood"] and a["action"] == "move" and a["classes"] == ["2A"] and a["subject"] == "PE" and a["not_days"] == ["Fri"], a
    a = typed._mock("move Mathematics for 3B off odd friday"); assert a["not_days"] == ["Odd Fri"] and a["subject"] == "Mathematics", a
    assert typed._mock("move PE for 2A off even week Monday")["not_days"] == ["Even Mon"]
    a = typed._mock("GIVE 2A Mathematics to Mdm Lee"); assert typed.check(a) and a["understood"] and a["action"] == "teacher" and a["classes"] == ["2A"] and a["subject"] == "Mathematics" and a["new_teacher"] == "Mdm Lee", a
    for w in ("move PE for 2A off friend", "move PE for 2A off monkey", "move PE for 2A off fridays"): assert typed._mock(w)["understood"] is False, w
    for w, d in (("off thurs", "Thu"), ("off Tues", "Tue"), ("off even week thursday", "Even Thu"), ("off Weds", "Wed"), ("off thur", "Thu"), ("off odd week tuesday", "Odd Tue")):
        assert typed._mock("move Art for 1A " + w)["not_days"] == [d], w
    assert typed._mock("move Art for 1A off friend")["understood"] is False
    assert typed._mock("move PE for 2A off Wed")["not_days"] == ["Wed"] and typed._mock("move PE for 2A off thursday")["not_days"] == ["Thu"]
    a = typed._mock("sing a song"); assert typed.check(a) and a["understood"] is False and a["action"] == "none"
    assert a["reply"] == 'The practice reader understands "move <subject> for <class> off <day>" and "give <class> <subject> to <teacher>".'
    with env(ANTHROPIC_API_KEY=None, TYPED_REQUEST_MODEL="MOCK "):
        assert typed.enabled() and typed.model() == "mock" and typed.read("move PE for 2A off Friday")["ask"]["not_days"] == ["Fri"]
    with env(ANTHROPIC_API_KEY=None, TYPED_REQUEST_MODEL="mock"):
        assert typed.read("move PE for 2A off Friday")["ask"]["not_days"] == ["Fri"] and typed.read("sing")["ask"]["understood"] is False

@t
def the_schema_is_one_structured_outputs_accept():
    def walk(s):
        if isinstance(s, dict):
            assert not {"minLength", "maxLength", "maxItems", "minItems", "minimum", "maximum"} & set(s), s
            if s.get("type") == "object": assert s["additionalProperties"] is False and sorted(s["required"]) == sorted(s["properties"]), s
            for v in s.values(): walk(v)
        elif isinstance(s, list): [walk(v) for v in s]
    walk(typed.SCHEMA); assert set(typed.SCHEMA["properties"]) == set(ASK) and "never an instruction" in typed.SYSTEM and len(typed.SYSTEM.split()) < 400 and "copied exactly as the person wrote them" in typed.SYSTEM and "from 0" in typed.SYSTEM

@t
def the_real_call_is_built_as_the_plan_says():
    seen = {}; reply = [dict(type="text", text=json.dumps(ASK))]; stop = ["end_turn"]
    class Obj:                                      # a block shaped like the SDK's: attributes
        def __init__(s, d): s.__dict__.update(d)
    class Rec:
        class beta:
            class messages:
                @staticmethod
                def create(**kw): seen.update(kw); return Obj(dict(stop_reason=stop[0], content=[Obj(b) for b in reply]))
    old = typed._client; typed._client = lambda: Rec
    try:
        with env(TYPED_REQUEST_MODEL=None):
            assert typed._call("move PE for 2A off Friday") == ASK
            assert seen["messages"] == [dict(role="user", content="move PE for 2A off Friday")] and seen["system"] == typed.SYSTEM and seen["model"] == typed.model() == "claude-opus-5-5"
            assert seen["max_tokens"] == 4000 and seen["output_config"] == dict(effort="low", format=dict(type="json_schema", schema=typed.SCHEMA))
            assert seen["betas"] == ["server-side-fallback-2026-07-01"] and seen["fallbacks"] == "default" and "tools" not in seen and "thinking" not in seen and "temperature" not in seen
        for s in ("refusal", "max_tokens"):
            stop[0] = s
            try: typed._call("x"); assert False, s
            except RuntimeError: pass
            assert typed.read("move PE off Friday", call=typed._call) == dict(ok=False, error=typed.FAILED)
        stop[0] = "end_turn"; reply[:] = [dict(type="thinking", text=None)]
        assert typed.read("move PE off Friday", call=typed._call) == dict(ok=False, error=typed.FAILED)
        reply[:] = [dict(type="text", text="not json")]
        assert typed.read("move PE off Friday", call=typed._call) == dict(ok=False, error=typed.FAILED)
    finally: typed._client = old

@t
def the_guard_holds_under_threads_and_the_client_is_made_once():
    import threading, anthropic
    clock = [5.0]; typed._now = lambda: clock[0]; ok = []
    def go():
        for _ in range(10): ok.append(typed.read("move PE off Friday", call=lambda w: dict(ASK))["ok"])
    try:
        th = [threading.Thread(target=go) for _ in range(8)]; [x.start() for x in th]; [x.join() for x in th]
    finally: import time; typed._now = time.monotonic
    assert ok.count(True) == 30 and len(typed._seen) == 30, (ok.count(True), len(typed._seen))
    made = []; real = anthropic.Anthropic; old = typed._cached
    class Fake:
        def __init__(s, **kw): made.append(kw)
    anthropic.Anthropic = Fake; typed._cached = None
    try: a = typed._client(); b = typed._client(); assert a is b and made == [dict(timeout=12.0, max_retries=1)], made
    finally: anthropic.Anthropic = real; typed._cached = old


# ----------------------------------------------------------------------------------------------- resolve and answer (small models built as tests/test_helper.py builds them)
def lesson(i, d, p, n_, cls, subject, group, teachers, room="", level="P1", block=""):
    return dict(id=i, d=d, p=p, n=n_, level=level, block=block, classes=cls, subject=subject, group=group, teachers=teachers, room=room, ext=False, rain="")
SP = primary(); reader.derive(SP); DAYS = list(SP["day_structure"][SP["school"]["levels"][0]].keys())
def model_with(L, **over):
    sp = dict(SP, **dict(dict(rules=[]), **over)); m = export._model(sp, DAYS, L); m["checked_setup"] = sp; return m, sp
def ask(**kw): return dict(typed._ask(understood=True, reply="ok"), **kw)
A, MG, SK = "1A", "Michelle Goh", "Sabrina Koh"

@t
def move_off_a_day_offers_only_other_days_and_every_way_is_clean_or_prefer():
    m, sp = model_with([lesson(1, 0, 2, 1, [A], "Mathematics", ENTIRE, [MG]), lesson(2, 1, 3, 1, [A], "Mathematics", ENTIRE, [MG])])
    r = typed.answer(m, sp, DAYS, ask(action="move", classes=[A], subject="Mathematics", from_day="Mon", not_days=["Mon"]))
    assert r["problems"] == [] and r["choices"] == [] and [g["lesson"] for g in r["groups"]] == [1] and r["more"] == 0 and r["narrow"] is None, r   # from_day Mon picks lesson 1 only
    g = r["groups"][0]; assert g["text"] == f"Mathematics for {A}, now Mon period 2" and g["none"] is None
    ss = g["suggestions"]; assert 1 <= len(ss) <= 3
    for s in ss:
        f = s["fixes"][0]; assert f["kind"] in ("move", "swap") and f["d"] != 0 if f["kind"] == "move" else True
        c = helper.chain(m, sp, DAYS, s["fixes"]); assert c["state"] == s["state"] in ("ok", "prefer") and set(s) == {"fixes", "text", "disturbs", "state", "moved"}
        if f["kind"] == "move": assert f["id"] == 1
    assert [helper.rank(m, sp, DAYS, s) for s in ss] == sorted(helper.rank(m, sp, DAYS, s) for s in ss)
    r = typed.answer(m, sp, DAYS, ask(action="move", classes=[A], subject="Mathematics", to_days=["Tue"], to_period_from=2, to_period_to=3))
    for g in r["groups"]: assert all(s["fixes"][0].get("d") == 1 and 2 <= s["fixes"][0].get("p", 2) <= 3 for s in g["suggestions"] if s["fixes"][0]["kind"] == "move")
    assert [g["lesson"] for g in r["groups"]] == [1, 2]
    full = [lesson(10 + k, d, p, 1, [A], "Art", ENTIRE, ["Umairah Tan"]) for k, (d, p) in enumerate((d, p) for d in range(len(DAYS)) for p in (1, 2, 3, 5, 6, 7, 8, 9, 10) if (d, p) != (0, 2))]
    m, sp = model_with([lesson(1, 0, 2, 1, [A], "Mathematics", ENTIRE, [MG])] + full)
    g = typed.answer(m, sp, DAYS, ask(action="move", classes=[A], subject="Mathematics", not_days=["Mon"]))["groups"][0]
    assert all(s["fixes"][0]["kind"] == "swap" for s in g["suggestions"])        # only swaps remain, and they are judged like any fix
    g = typed.answer(m, sp, DAYS, ask(action="move", classes=[A], subject="Mathematics", to_days=["Mon"], to_period_from=4, to_period_to=4))["groups"][0]
    assert g["suggestions"] == [] and g["none"] == typed.NO_SLOT == "Nowhere that fits is free for this lesson without breaking a rule or a clash."

@t
def a_teacher_change_is_one_fix_for_the_class_and_subject():
    key = "C:1A:Mathematics"
    m, sp = model_with([lesson(1, 0, 2, 1, [A], "Mathematics", ENTIRE, [SK]), lesson(2, 1, 3, 1, [A], "Mathematics", ENTIRE, [SK])])
    r = typed.answer(m, sp, DAYS, ask(action="teacher", classes=[A], subject="Mathematics", new_teacher="michelle goh"))
    assert r["problems"] == [] and len(r["groups"]) == 1, r
    g = r["groups"][0]; assert g["none"] is None and len(g["suggestions"]) == 1 and g["suggestions"][0]["text"] == f"Give Mathematics for {A} to {MG}." and g["suggestions"][0]["fixes"] == [dict(kind="teacher", key=key, teachers=[MG])]
    assert g["text"] == f"Mathematics for {A}, 2 lessons"
    m, sp = model_with([lesson(1, 0, 2, 1, [A], "Mathematics", ENTIRE, [SK]), lesson(3, 0, 2, 1, ["1B"], "Mathematics", ENTIRE, [MG])])   # she teaches 1B then
    g = typed.answer(m, sp, DAYS, ask(action="teacher", classes=[A], subject="Mathematics", new_teacher=MG))["groups"][0]
    c = helper.chain(m, sp, DAYS, [dict(kind="teacher", key=key, teachers=[MG])]); assert c["state"] == "no"
    assert g["suggestions"] == [] and g["none"] == c["why"] and "1B" in g["none"], g
    g = typed.answer(m, sp, DAYS, ask(action="teacher", classes=["1B"], subject="Mathematics", new_teacher=MG))["groups"][0]
    assert g["none"] == typed.SAME == "That is how it is already." and g["suggestions"] == []
    r = typed.answer(m, sp, DAYS, ask(action="teacher", classes=[A], subject="Mathematics")); assert r["problems"] == ["Say who should take it."] and r["groups"] == []
    r = typed.answer(m, sp, DAYS, ask(action="room", classes=[A], subject="Mathematics")); assert r["problems"] == ["Say which room."]

@t
def a_room_change_is_one_fix_per_row_of_each_lesson():
    m, sp = model_with([lesson(1, 0, 2, 1, [A], "Mathematics", ENTIRE, [MG], room="1-01")])
    r = typed.answer(m, sp, DAYS, ask(action="room", classes=[A], subject="Mathematics", new_room="1-02"))
    g = r["groups"][0]; assert len(r["groups"]) == 1 and g["suggestions"][0]["fixes"] == [dict(kind="room", id=1, group=ENTIRE, room="1-02")] and g["suggestions"][0]["text"] == f"Put Mathematics for {A} in 1-02.", r
    g = typed.answer(m, sp, DAYS, ask(action="room", classes=[A], subject="Mathematics", new_room="1-01"))["groups"][0]; assert g["none"] == "That is how it is already." and g["suggestions"] == []
    assert typed.answer(m, sp, DAYS, ask(action="room", classes=[A], new_room="Tower"))["problems"] == ['There is no room called "Tower".']

@t
def names_are_never_guessed():
    sp2 = dict(SP, teachers=SP["teachers"] + [dict(name="Quek Mei Ling", short="Mei Ling Q", dept="X", allowance=36, can_teach=[]), dict(name="Quek Hong Wei", short="Hong Wei Q", dept="X", allowance=36, can_teach=[])],
               subjects=SP["subjects"] + [dict(subject="Additional Mathematics", code="AM", tag="-", dept="MA", room_kind=None, lesson_length=None, periods={})])
    L = [lesson(1, 0, 2, 1, [A], "Mathematics", ENTIRE, [MG]), lesson(2, 1, 3, 1, [A], "Additional Mathematics", ENTIRE, [MG]), lesson(3, 2, 3, 1, ["1B"], "Mathematics", ENTIRE, [MG])]
    m, sp = model_with(L, teachers=sp2["teachers"], subjects=sp2["subjects"])
    r = typed.answer(m, sp, DAYS, ask(action="teacher", classes=[A], subject="Mathematics", new_teacher="Quek"))
    assert r["choices"] == [dict(id="new_teacher|Quek", field="new_teacher", said="Quek", options=["Quek Mei Ling", "Quek Hong Wei"])] and r["groups"] == [] and r["problems"] == [], r
    r = typed.answer(m, sp, DAYS, ask(action="teacher", classes=[A], subject="Mathematics", new_teacher="Quek"), pick={"new_teacher|Quek": "Quek Hong Wei"})
    assert r["choices"] == [] and len(r["groups"]) == 1 and r["groups"][0]["suggestions"][0]["fixes"][0]["teachers"] == ["Quek Hong Wei"], r
    assert typed.resolve(m, sp, ask(action="teacher", new_teacher="Mdm. Quek Mei"), None)["new_teacher"] == "Quek Mei Ling" and typed.resolve(m, sp, ask(action="teacher", new_teacher="Hong Wei Q"))["new_teacher"] == "Quek Hong Wei"
    r = typed.answer(m, sp, DAYS, ask(action="move", classes=[A], subject="maths", not_days=["Mon"]))      # Mathematics and Additional Mathematics are both 1A's
    assert r["choices"] == [dict(id="subject|maths", field="subject", said="maths", options=["Mathematics", "Additional Mathematics"])] and r["groups"] == [], r
    r = typed.answer(m, sp, DAYS, ask(action="move", classes=[A], subject="maths", to_days=["Mon"]), pick={"subject|maths": "Additional Mathematics"}); assert [g["lesson"] for g in r["groups"]] == [2], r
    r = typed.answer(m, sp, DAYS, ask(action="move", classes=["1B"], subject="maths", to_days=["Mon"])); assert r["choices"] == [] and [g["lesson"] for g in r["groups"]] == [3]   # only one is 1B's
    r = typed.answer(m, sp, DAYS, ask(action="move", classes=["9Z"], not_days=["Mon"])); assert r["problems"] == ['There is no class or level called "9Z".'] and r["groups"] == [], r
    r = typed.answer(m, sp, DAYS, ask(action="move", classes=[A], teacher="Nobody Here", not_days=["Mon"])); assert r["problems"] == ['There is no teacher called "Nobody Here".']
    r = typed.answer(m, sp, DAYS, ask(action="move", classes=[A], subject="Basket Weaving", not_days=["Mon"])); assert r["problems"] == ['There is no subject called "Basket Weaving".']
    assert typed.resolve(m, sp, ask(action="move", teacher="Ms Goh's"))["lessons"] == [1, 2, 3] and typed.resolve(m, sp, ask(action="move", group="nothing"))["problems"] == [typed.NO_LESSON]
    for s in ("Mdm", "Dr."): assert typed.resolve(m, sp, ask(action="move", teacher=s))["problems"], s     # a title alone names nobody
    # a class written two ways that differ only in case or spaces, with no exact match, is a choice
    m2 = dict(m, classes=[dict(name="2 A", level="S2"), dict(name="2  A", level="S2"), dict(name="3A", level="S3")])
    assert typed.resolve(m2, sp, ask(action="move", classes=["2a"]))["choices"] == [dict(id="classes|2a", field="classes", said="2a", options=["2 A", "2  A"])]
    assert typed.resolve(m2, sp, ask(action="move", classes=["2a"]), pick={"classes|2a": "2  A"})["choices"] == [] and typed.resolve(m2, sp, ask(action="move", classes=["2 a"]))["choices"] == []
    assert typed.resolve(m2, sp, ask(action="move", classes=["3 a"]))["problems"] == ['There is no class or level called "3 a".']     # one loose match is still not an exact one

@t
def an_ask_outside_the_actions_does_nothing():
    m, sp = model_with([lesson(1, 0, 2, 1, [A], "Mathematics", ENTIRE, [MG])])
    for a in (ask(understood=False, reply="Not understood.", action="none"), ask(understood=True, reply="Fine.", action="none", classes=[A], keep=["x"]), ask(understood=False, reply="no", action="move", classes=[A], not_days=["Mon"])):
        r = typed.answer(m, sp, DAYS, a); assert r["groups"] == [] and r["reply"] == a["reply"] and r["problems"] == [] and r["choices"] == [] and r["more"] == 0 and r["understood"] is a["understood"], r
    r = typed.answer(m, sp, DAYS, ask(action="move", classes=[A], subject="Mathematics")); assert r["problems"] == [typed.NO_WHERE] == ["Say where it should go, or which day or periods to keep it off."] and r["groups"] == []
    r = typed.answer(m, sp, DAYS, ask(action="move", classes=[A], subject="Mathematics", not_days=["Mon"], keep=["keep the doubles"])); assert r["keep"] == ["keep the doubles"]
    before = repr(m["lessons"]); typed.answer(m, sp, DAYS, ask(action="move", classes=[A], not_days=["Mon"])); assert repr(m["lessons"]) == before

@t
def many_lessons_are_answered_eight_at_a_time():
    m, sp = model_with([lesson(i, i % 5, 1 + i // 5, 1, [A], "Mathematics", ENTIRE, [MG]) for i in range(1, 13)])
    r = typed.answer(m, sp, DAYS, ask(action="move", classes=[A], subject="Mathematics", to_days=["Fri"]))
    assert len(r["groups"]) == 8 and r["more"] == 4 and r["narrow"] == "That matches 12 lessons. Here are the first 8; name a class or a day to narrow it.", r
    order = [(x["d"], x["p"]) for g in r["groups"] for x in m["lessons"] if x["id"] == g["lesson"]]; assert order == sorted(order)
    r = typed.answer(m, sp, DAYS, ask(action="move", classes=[A], subject="Mathematics", from_day="Mon", to_days=["Fri"])); assert r["more"] == 0 and r["narrow"] is None and len(r["groups"]) == 2
    r = typed.answer(m, sp, DAYS, ask(action="move", group="nothing", to_days=["Fri"])); assert r["problems"] == [typed.NO_LESSON]

@t
def a_level_means_its_classes_and_a_bare_weekday_means_every_week():
    days = [w + d for w in ("Odd ", "Even ") for d in ("Mon", "Tue", "Wed", "Thu", "Fri")]
    L = [lesson(1, 4, 1, 1, ["2A"], "Art", ENTIRE, []), lesson(2, 9, 1, 1, ["2B"], "Art", ENTIRE, []), lesson(3, 0, 1, 1, ["3A"], "Art", ENTIRE, [])]
    m = dict(days=days, classes=[dict(name="2A", level="S2"), dict(name="2B", level="S2"), dict(name="3A", level="S3")], lessons=L); spc = dict(subjects=[], teachers=[], venues=[])
    r = typed.resolve(m, spc, ask(action="move", classes=["s2"], not_days=["Fri"], to_days=["Even Mon", "odd tue"], from_day="Odd Fri"))
    assert r["lessons"] == [1] and r["days"] == dict(from_day=[4], to_days=[1, 5], not_days=[4, 9]) and r["problems"] == [], r
    assert typed.resolve(m, spc, ask(action="move", classes=["S2"]))["lessons"] == [1, 2] and typed.resolve(m, spc, ask(action="move", classes=["2b", "3A"]))["lessons"] == [3, 2]
    one = dict(m, days=["Mon", "Tue", "Wed", "Thu", "Fri"])
    assert typed.resolve(one, spc, ask(action="move", not_days=["Odd Fri"]))["problems"] == ["This timetable has one week: say the day without Odd or Even."]
    assert typed.resolve(one, spc, ask(action="move", not_days=["Fri"]))["days"]["not_days"] == [4]
    assert typed.resolve(m, spc, ask(action="move", classes=["2A"], from_day="Even Mon"))["problems"] == [typed.NO_LESSON]

@t
def a_subject_is_found_by_name_code_or_everyday_word():
    spc = dict(subjects=[dict(subject="Physical Education", code="PE"), dict(subject="Mathematics", code="MA"), dict(subject="Mathematics (Standard)", code="MA"), dict(subject="Art", code="AR")], teachers=[], venues=[])
    L = [lesson(1, 0, 1, 1, ["2A"], "Physical Education", ENTIRE, []), lesson(2, 1, 1, 1, ["2A"], "Mathematics", ENTIRE, []), lesson(3, 2, 1, 1, ["2A"], "Mathematics (Standard)", ENTIRE, []), lesson(4, 3, 1, 1, ["2A"], "Art", ENTIRE, [])]
    m = dict(days=DAYS, classes=[dict(name="2A", level="S2")], lessons=L)
    for said, want in (("pe", [1]), ("PE", [1]), ("physical", [1]), ("education", [1]), ("Maths", [2, 3]), ("MA", [2, 3]), ("art", [4]), ("Mathematics", [2])):
        r = typed.resolve(m, spc, ask(action="move", subject=said)); assert r["lessons"] == want and r["choices"] == [], (said, r)
    assert typed.resolve(m, spc, ask(action="move", subject="phys"))["lessons"] == [1] and typed.resolve(m, spc, ask(action="move", subject="ed"))["problems"] == ['There is no subject called "ed".']

# ----------------------------------------------------------------------------------------------- fix round: what was asked is what is offered
# ----------------------------------------------------------------------------------------------- days spelled as a real school spells them
def model_days(names, L):
    """a small model whose day labels are `names` (the setup's day structure renamed to match, cycling the sample's five days)"""
    base = list(SP["day_structure"][SP["school"]["levels"][0]].keys())
    sp = dict(SP, rules=[], day_structure={lv: {names[i]: ds[base[i % 5]] for i in range(len(names))} for lv, ds in SP["day_structure"].items()})
    m = export._model(sp, names, L); m["checked_setup"] = sp; return m, sp
REAL = ["Odd Mon", "Odd Tues", "Odd Wed", "Odd Thurs", "Odd Fri", "Even Mon", "Even Tues", "Even Wed", "Even Thurs", "Even Fri"]
def _dest_days(r, m):
    out = set()
    for g in r["groups"]:
        for s in g["suggestions"]:
            f = s["fixes"][0]; out.add(f["d"] if f["kind"] == "move" else next(x for x in m["lessons"] if x["id"] == f["b"])["d"])
    return out

@t
def days_are_matched_by_weekday_however_the_timetable_spells_them():
    L = [lesson(i, d, 2, 1, [A], "Mathematics", ENTIRE, [MG]) for i, d in ((1, 0), (2, 1), (3, 3), (4, 6), (5, 8))]
    m, sp = model_days(REAL, L); run = lambda **kw: typed.answer(m, sp, REAL, ask(action="move", classes=[A], subject="Mathematics", **kw))
    r = run(not_days=["Thu"]); assert r["problems"] == [] and [g["lesson"] for g in r["groups"]] == [3, 5], r
    assert r["groups"][0]["text"] == "Mathematics for 1A, now Odd Thurs period 2" and r["groups"][1]["text"].startswith("Mathematics for 1A, now Even Thurs") and _dest_days(r, m) and not _dest_days(r, m) & {3, 8}, _dest_days(r, m)
    r = run(from_day="Odd Tue", not_days=["Odd Tue"]); assert r["problems"] == [] and [g["lesson"] for g in r["groups"]] == [2], r
    r = run(not_days=["Even Thu"]); assert r["problems"] == [] and [g["lesson"] for g in r["groups"]] == [5], r
    r = run(to_days=["Even Thu"]); assert r["problems"] == [] and _dest_days(r, m) == {8}, (r["problems"], _dest_days(r, m))
    r = run(to_days=["Tue"], not_days=["Odd Tue"]); assert r["problems"] == [] and _dest_days(r, m) == {6}, (r["problems"], _dest_days(r, m))
    r = run(to_days=["Even Tue"], not_days=["Even Tue"]); assert r["problems"] == [typed.CONTRA], r["problems"]
    r = run(not_days=["Sat"]); assert r["problems"] == ['This timetable has no day called "Sat".'], r["problems"]

@t
def a_one_week_timetable_with_long_day_names_still_reads_a_bare_weekday():
    one = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    m, sp = model_days(one, [lesson(1, 1, 2, 1, [A], "Mathematics", ENTIRE, [MG]), lesson(2, 2, 2, 1, [A], "Mathematics", ENTIRE, [MG])])
    r = typed.answer(m, sp, one, ask(action="move", classes=[A], subject="Mathematics", not_days=["Tue"])); assert r["problems"] == [] and [g["lesson"] for g in r["groups"]] == [1], r
    r = typed.answer(m, sp, one, ask(action="move", classes=[A], subject="Mathematics", not_days=["Odd Tue"])); assert r["problems"] == [typed.ONE_WEEK], r["problems"]

def rule(target, rule_, a, b, strength="Must", scope="Class"):
    return dict(scope=scope, target=target, rule=rule_, week="Both", day="All", strength=strength, **{"from": a, "to": b})

def spec_of(**kw): return dict(subjects=[], teachers=[], venues=[], **kw)
def fake(L, classes=("1A",), days=None): return dict(days=days or DAYS, classes=[dict(name=c, level="P1") for c in classes], lessons=L, NP=12)
BAND = lambda i=1, d=0, p=2: [lesson(i, d, p, 1, [A], "Tamil Language", "TL1", ["Benjamin Teo"], room="1-01", block="BX"), lesson(i, d, p, 1, [A], "Chinese Language", "CL1", ["Adeline Tan"], room="1-02", block="BX")]

@t
def off_a_day_means_the_lessons_on_that_day():
    m, sp = model_with([lesson(1, 0, 2, 1, [A], "Mathematics", ENTIRE, [MG]), lesson(2, 1, 2, 1, [A], "Mathematics", ENTIRE, [MG]), lesson(3, 4, 2, 1, [A], "Mathematics", ENTIRE, [MG])])
    r = typed.answer(m, sp, DAYS, ask(action="move", classes=[A], subject="Mathematics", not_days=["Fri"])); assert [g["lesson"] for g in r["groups"]] == [3] and r["problems"] == [], r
    r = typed.answer(m, sp, DAYS, ask(action="move", classes=[A], subject="Mathematics", not_days=["Wed"])); assert r["problems"] == ["No lesson that matches is on that day."] and r["groups"] == [], r
    r = typed.answer(m, sp, DAYS, ask(action="move", classes=[A], subject="Mathematics", from_day="Mon", not_days=["Fri"])); assert [g["lesson"] for g in r["groups"]] == [1]   # a day named as where it is now wins
    r = typed.answer(m, sp, DAYS, ask(action="move", classes=[A], subject="Mathematics", to_days=["Wed"])); assert [g["lesson"] for g in r["groups"]] == [1, 2, 3]       # not_days not given: every lesson

@t
def a_band_is_read_row_by_row():
    m, sp = model_with(BAND() + [lesson(2, 1, 2, 1, [A], "Mathematics", ENTIRE, [MG])])
    r = typed.resolve(m, sp, ask(action="move", classes=[A], subject="Tamil Language")); assert r["lessons"] == [1] and [x["group"] for x in r["rows"][1]] == ["TL1"], r
    assert typed.resolve(m, sp, ask(action="move", classes=[A], subject="Chinese Language", teacher="Benjamin Teo"))["problems"] == [typed.NO_LESSON]    # no one row has both
    assert typed.resolve(m, sp, ask(action="move", classes=[A], teacher="Benjamin Teo"))["lessons"] == [1]
    r = typed.answer(m, sp, DAYS, ask(action="teacher", teacher="Benjamin Teo", new_teacher=MG))
    assert [g["lesson"] for g in r["groups"]] == [1] and r["groups"][0]["text"] == "group TL1, now Mon period 2" and r["groups"][0]["suggestions"][0]["fixes"] == [dict(kind="teacher", key="G:TL1", teachers=[MG])], r
    r = typed.answer(m, sp, DAYS, ask(action="teacher", classes=[A], subject="Chinese Language", new_teacher=MG)); assert r["groups"][0]["suggestions"][0]["fixes"][0]["key"] == "G:CL1"
    r = typed.answer(m, sp, DAYS, ask(action="room", classes=[A], subject="Tamil Language", new_room="1-03")); assert r["groups"][0]["suggestions"][0]["fixes"] == [dict(kind="room", id=1, group="TL1", room="1-03")], r
    r = typed.answer(m, sp, DAYS, ask(action="room", classes=[A], subject="Tamil Language", new_room="1-01")); assert r["groups"][0]["none"] == typed.SAME           # that row is there already
    r = typed.answer(m, sp, DAYS, ask(action="room", classes=[A], teacher="Adeline Tan", new_room="1-03")); assert r["groups"][0]["suggestions"][0]["fixes"][0]["group"] == "CL1"
    r = typed.answer(m, sp, DAYS, ask(action="teacher", classes=[A], new_teacher=MG, from_day="Mon"))     # both rows match: each key is its own group
    assert sorted(g["suggestions"][0]["fixes"][0]["key"] for g in r["groups"] if g["suggestions"]) == ["G:CL1", "G:TL1"], r
    r = typed.answer(m, sp, DAYS, ask(action="move", classes=[A], subject="Tamil Language", to_days=["Tue"]))
    ss = r["groups"][0]["suggestions"]; assert ss and all("This lesson is a band: it moves for CL1 (1A) too." in s["disturbs"] for s in ss), r
    r = typed.answer(m, sp, DAYS, ask(action="move", classes=[A], from_day="Mon", to_days=["Tue"]))        # every row matches: nothing else moves
    assert all(not any("band" in d for d in s["disturbs"]) for s in r["groups"][0]["suggestions"])

@t
def a_subject_with_no_lesson_falls_back_to_its_family():
    m, sp = model_with([lesson(1, 0, 2, 1, [A], "Science (Standard)", ENTIRE, [MG]), lesson(2, 1, 2, 1, [A], "Science (Foundation)", ENTIRE, [MG])])
    r = typed.resolve(m, sp, ask(action="move", classes=[A], subject="Science")); assert r["lessons"] == [1, 2] and r["choices"] == [] and r["problems"] == [], r
    assert typed.resolve(m, sp, ask(action="move", classes=["1B"], subject="Science"))["problems"] == [typed.NO_LESSON]

@t
def short_words_never_match():
    m, sp = model_with([lesson(1, 0, 2, 1, [A], "Art", ENTIRE, [MG]), lesson(2, 1, 2, 1, [A], "Character and Citizenship Education", ENTIRE, [MG]), lesson(3, 2, 2, 1, [A], "Physical Education", ENTIRE, [MG])])
    for w in ("a", "p", "and", "of the", "ed"): assert typed.resolve(m, sp, ask(action="move", subject=w))["problems"] == [f'There is no subject called "{w}".'], w
    assert typed.resolve(m, sp, ask(action="move", subject="PE"))["lessons"] == [3] and typed.resolve(m, sp, ask(action="move", subject="art"))["lessons"] == [1] and typed.resolve(m, sp, ask(action="move", subject="citizenship and character"))["lessons"] == [2]
    f = fake([lesson(1, 0, 2, 1, [A], "Art", ENTIRE, [])]); sv = spec_of(); sv["venues"] = [dict(room="Hall 2"), dict(room="Lab")]
    assert typed.resolve(f, sv, ask(action="room", new_room="2"))["problems"] == ['There is no room called "2".'] and typed.resolve(f, sv, ask(action="room", new_room="la"))["problems"]
    assert typed.resolve(f, sv, ask(action="room", new_room="hall"))["new_room"] == "Hall 2" and typed.resolve(f, sv, ask(action="room", new_room="LAB"))["new_room"] == "Lab" and typed.resolve(f, sv, ask(action="room", new_room="hall 2"))["new_room"] == "Hall 2"

@t
def a_swap_of_two_lessons_alike_is_not_offered():
    every = [(d, p) for d in range(len(DAYS)) for p in (1, 2, 3, 5, 6, 7, 8, 9, 10) if (d, p) != (0, 2)]
    L = [lesson(1, 0, 2, 1, [A], "Mathematics", ENTIRE, [MG], room="1-01")] + [lesson(10 + k, d, p, 1, [A], "Mathematics", ENTIRE, [MG], room="1-01") for k, (d, p) in enumerate(every)]
    m, sp = model_with(L); g = typed.answer(m, sp, DAYS, ask(action="move", from_day="Mon", from_period=2, to_days=["Tue"]))["groups"][0]
    assert g["suggestions"] == [] and g["none"] == typed.NO_SLOT, g
    L[1 + every.index((1, 3))] = lesson(500, 1, 3, 1, [A], "Art", ENTIRE, ["Umairah Tan"], room="1-01"); m, sp = model_with(L)
    g = typed.answer(m, sp, DAYS, ask(action="move", from_day="Mon", from_period=2, to_days=["Tue"]))["groups"][0]
    assert [s["fixes"] for s in g["suggestions"]] == [[dict(kind="swap", a=1, b=500)]] and g["suggestions"][0]["disturbs"].count("Art for 1A moves to Mon period 2.") == 1, g

@t
def a_change_that_differs_from_step_5_says_so():
    m, sp = model_with([lesson(1, 0, 2, 1, [A], "Mathematics", ENTIRE, [MG])])
    g = typed.answer(m, sp, DAYS, ask(action="teacher", classes=[A], subject="Mathematics", new_teacher=SK))["groups"][0]
    assert g["suggestions"] and typed.STEP5 == "This differs from step 5, so it will show as a warning." and typed.STEP5 in g["suggestions"][0]["disturbs"], g
    m, sp = model_with([lesson(1, 0, 2, 1, [A], "Mathematics", ENTIRE, [SK])])      # step 5 plans Michelle Goh: giving it to her fixes the difference
    g = typed.answer(m, sp, DAYS, ask(action="teacher", classes=[A], subject="Mathematics", new_teacher=MG))["groups"][0]
    assert g["suggestions"] and typed.STEP5 not in g["suggestions"][0]["disturbs"], g

@t
def contradictory_asks_are_one_sentence():
    m, sp = model_with([lesson(1, 0, 2, 1, [A], "Mathematics", ENTIRE, [MG])]); one = ["That asks for days or periods that cannot all hold. Say it another way."]
    for kw in (dict(to_days=["Mon"], not_days=["Mon"]), dict(to_days=["Tue"], to_period_from=5, to_period_to=3), dict(to_days=["Tue"], to_period_from=99), dict(to_days=["Tue"], to_period_from=m["NP"])):
        r = typed.answer(m, sp, DAYS, ask(action="move", classes=[A], **kw)); assert r["problems"] == one and r["groups"] == [], (kw, r)
    r = typed.answer(m, sp, DAYS, ask(action="move", classes=[A], to_days=["Tue"], to_period_from=3, to_period_to=3)); assert r["problems"] == [] and r["groups"]
    r = typed.answer(m, sp, DAYS, ask(action="move", classes=[A], to_days=["Tue"], to_period_from=3)); assert r["problems"] == []        # one end only is fine

@t
def a_day_half_excluded_is_not_a_contradiction():
    import copy; days2 = [w + d for w in ("Odd ", "Even ") for d in ("Mon", "Tue", "Wed", "Thu", "Fri")]; sp = copy.deepcopy(dict(SP, rules=[]))   # a two-week timetable: the same day twice
    sp["day_structure"] = {lv: {d: ds[DAYS[i % 5]] for i, d in enumerate(days2)} for lv, ds in sp["day_structure"].items()}
    m = export._model(sp, days2, [lesson(1, 4, 2, 1, [A], "Mathematics", ENTIRE, [MG])]); m["checked_setup"] = sp
    r = typed.answer(m, sp, days2, ask(action="move", classes=[A], to_days=["Fri"], not_days=["Odd Fri"]))
    assert typed.CONTRA not in r["problems"] and r["problems"] == [], r              # Even Fri is left
    assert r["groups"] and all(s["fixes"][0].get("d") != 4 for g in r["groups"] for s in g["suggestions"]), r
    r = typed.answer(m, sp, days2, ask(action="move", classes=[A], to_days=["Fri"], not_days=["Fri"])); assert r["problems"] == [typed.CONTRA], r
    r = typed.answer(m, sp, days2, ask(action="move", classes=[A], to_days=["Odd Fri", "Even Fri"], not_days=["Fri"])); assert r["problems"] == [typed.CONTRA], r

@t
def a_swaps_other_lesson_does_not_depend_on_the_wording_of_a_sentence():
    every = [(d, p) for d in range(len(DAYS)) for p in (1, 2, 3, 5, 6, 7, 8, 9, 10) if (d, p) != (0, 2)]
    L = [lesson(1, 0, 2, 1, [A], "Mathematics", ENTIRE, [MG], room="1-01")] + [lesson(10 + k, d, p, 1, [A], "Mathematics", ENTIRE, [MG], room="1-01") for k, (d, p) in enumerate(every)]
    L[1 + every.index((1, 3))] = lesson(500, 1, 3, 1, [A, "1B"], "Art", ENTIRE, ["Umairah Tan"], room="1-01"); m, sp = model_with(L)
    real = fixes.slots
    def reworded(*a, **k): return [dict(s, also=["Something else goes too." for _ in s["also"]]) for s in real(*a, **k)]
    fixes.slots = reworded
    try: g = typed.answer(m, sp, DAYS, ask(action="move", from_day="Mon", from_period=2, to_days=["Tue"]))["groups"][0]
    finally: fixes.slots = real
    assert [s["fixes"] for s in g["suggestions"]] == [[dict(kind="swap", a=1, b=500)]] and g["suggestions"][0]["disturbs"] == ["Art for 1A, 1B moves to Mon period 2."], g   # already said by the swap itself: not said twice

@t
def a_pick_must_be_one_of_the_options_for_that_choice():
    sp2 = dict(SP, teachers=SP["teachers"] + [dict(name="Quek Mei Ling", short="x", dept="X", allowance=36, can_teach=[]), dict(name="Quek Hong Wei", short="y", dept="X", allowance=36, can_teach=[])])
    m, sp = model_with([lesson(1, 0, 2, 1, [A], "Mathematics", ENTIRE, [MG])], teachers=sp2["teachers"]); a = ask(action="teacher", classes=[A], subject="Mathematics", new_teacher="Quek")
    for bad in ({"new_teacher|Quek": MG}, {"new_teacher|Quek": "Quek"}, {"new_teacher": "Quek Hong Wei"}, {"teacher|Quek": "Quek Hong Wei"}, {"new_teacher|Quek": None}, {"new_teacher|Quek": ["Quek Hong Wei"]}, "Quek Hong Wei", 5):
        r = typed.answer(m, sp, DAYS, a, pick=bad); assert len(r["choices"]) == 1 and r["choices"][0]["id"] == "new_teacher|Quek" and r["groups"] == [], (bad, r)
    r = typed.answer(m, sp, DAYS, a, pick={"new_teacher|Quek": "Quek Mei Ling", "junk|x": "y"}); assert r["choices"] == [] and r["groups"][0]["suggestions"][0]["fixes"][0]["teachers"] == ["Quek Mei Ling"]
    f = fake([lesson(1, 0, 2, 1, ["2 A"], "Art", ENTIRE, []), lesson(2, 1, 2, 1, ["3 B"], "Art", ENTIRE, [])], classes=("2 A", "2  A", "3 B", "3  B")); sv = spec_of()
    ch = typed.resolve(f, sv, ask(action="move", classes=["2a", "3b"]))["choices"]; assert [c["id"] for c in ch] == ["classes|2a", "classes|3b"], ch
    r = typed.resolve(f, sv, ask(action="move", classes=["2a", "3b"]), pick={"classes|2a": "2 A", "classes|3b": "3  B"}); assert r["choices"] == [] and r["lessons"] == [1] or r["lessons"] == [1, 2], r
    r = typed.resolve(f, sv, ask(action="move", classes=["2a", "3b"]), pick={"classes|2a": "2 A"}); assert [c["id"] for c in r["choices"]] == ["classes|3b"]

@t
def the_rules_of_the_period_range_and_the_start_are_held():
    m, sp = model_with([lesson(1, 0, 2, 2, [A], "Mathematics", ENTIRE, [MG])])
    g = typed.answer(m, sp, DAYS, ask(action="move", classes=[A], to_days=["Tue"], to_period_from=1, to_period_to=2))["groups"][0]       # two periods long: it must end by period 2
    assert sorted(s["fixes"][0]["p"] for s in g["suggestions"]) == [1], g
    m, sp = model_with([lesson(1, 0, 2, 1, [A], "Mathematics", ENTIRE, [MG]), lesson(2, 0, 3, 1, [A], "Mathematics", ENTIRE, [MG]), lesson(3, 1, 3, 1, [A], "Mathematics", ENTIRE, [MG])])
    r = typed.answer(m, sp, DAYS, ask(action="move", classes=[A], from_period=3, to_days=["Wed"])); assert [g["lesson"] for g in r["groups"]] == [2, 3], r
    r = typed.answer(m, sp, DAYS, ask(action="move", classes=[A], from_period=3, from_day="Tue", to_days=["Wed"])); assert [g["lesson"] for g in r["groups"]] == [3], r
    m, sp = model_with([lesson(1, 0, 2, 1, [A], "Mathematics", ENTIRE, [MG])], rules=[dict(rule(A, "Not in periods", 5, 5), strength="Prefer")])
    g = typed.answer(m, sp, DAYS, ask(action="move", classes=[A], to_days=["Tue"], to_period_from=5, to_period_to=5))["groups"][0]
    assert g["suggestions"] and all(s["state"] == "prefer" for s in g["suggestions"]) and g["none"] is None, g            # a prefer way is still a way

@t
def the_teacher_cap_counts_keys_and_a_refused_room_says_why():
    cls = [c["class"] for c in SP["classes"]][:10]; lv = {c["class"]: c["level"] for c in SP["classes"]}
    m, sp = model_with([lesson(i + 1, i % 5, 1 + i // 5, 1, [c], "Mathematics", ENTIRE, [SK], level=lv[c]) for i, c in enumerate(cls)])
    r = typed.answer(m, sp, DAYS, ask(action="teacher", subject="Mathematics", new_teacher=MG))
    assert len(r["groups"]) == 8 and r["more"] == 2 and r["narrow"] == "That matches 10 classes or groups. Here are the first 8; name a class to narrow it.", r
    m, sp = model_with([lesson(1, 0, 2, 1, [A], "Mathematics", ENTIRE, [MG], room="1-01"), lesson(2, 0, 2, 1, ["1B"], "Mathematics", ENTIRE, [SK], room="1-02")])
    g = typed.answer(m, sp, DAYS, ask(action="room", classes=[A], new_room="1-02"))["groups"][0]
    c = helper.chain(m, sp, DAYS, [dict(kind="room", id=1, group=ENTIRE, room="1-02")]); assert c["state"] == "no" and g["suggestions"] == [] and g["none"] == c["why"] and g["none"], (g, c["why"])

if "--full" in sys.argv:
    import subprocess, tempfile, time
    @t
    def a_solved_secondary_sample_answers_a_move_quickly_and_truly():
        work = tempfile.mkdtemp(); setup, tt = os.path.join(work, "setup.xlsx"), os.path.join(work, "timetable.xlsx"); e = dict(os.environ, PYTHONPATH=ROOT)
        subprocess.run([sys.executable, "-m", "ttgen", "sample", "secondary", "--out", setup], check=True, env=e, cwd=ROOT, capture_output=True)
        done = subprocess.run([sys.executable, "-m", "ttgen", "solve", setup, "--out", tt, "--time", "30"], env=e, cwd=ROOT, capture_output=True)
        assert done.returncode == 0 and os.path.exists(tt)
        m = export.model_from_files(setup, tt); sp = m["checked_setup"]; days = m["days"]; print("  days:", days[:3], "...", len(days))
        said = "Odd Fri" if any(d.startswith("Odd ") for d in days) else "Fri"
        t0 = time.time(); r = typed.answer(m, sp, days, ask(action="move", subject="Physical Education", not_days=[said])); dt = time.time() - t0
        assert dt < 2, dt; assert r["problems"] == [] and r["choices"] == [] and r["groups"], (r["problems"], r["choices"], len(r["groups"]), r["more"])
        offered = sum(len(g["suggestions"]) for g in r["groups"]); print(f"  {len(r['groups'])} lessons answered (+{r['more']}), {offered} suggestions, {dt:.2f} s")
        for g in r["groups"]:
            assert len(g["suggestions"]) <= 3 and (g["none"] is None) == bool(g["suggestions"])
            for s in g["suggestions"]:
                assert helper.chain(m, sp, days, s["fixes"])["state"] in ("ok", "prefer")
                f = s["fixes"][0]; row = next(x for x in m["lessons"] if x["id"] == (f["id"] if f["kind"] == "move" else f["a"]))
                dest = (f["d"] if f["kind"] == "move" else next(x for x in m["lessons"] if x["id"] == f["b"])["d"])
                assert days[dest] != said and days[row['d']] == said and (f["kind"] == "swap" or row["id"] == g["lesson"]), (said, s["text"])

print(f"{n} typed checks passed")

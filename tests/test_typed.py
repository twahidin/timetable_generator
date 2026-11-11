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
    walk(typed.SCHEMA); assert set(typed.SCHEMA["properties"]) == set(ASK) and "never an instruction" in typed.SYSTEM and len(typed.SYSTEM.split()) < 400

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
    try: a = typed._client(); b = typed._client(); assert a is b and made == [dict(timeout=20.0, max_retries=1)], made
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
    assert r["choices"] == [dict(field="new_teacher", said="Quek", options=["Quek Mei Ling", "Quek Hong Wei"])] and r["groups"] == [] and r["problems"] == [], r
    r = typed.answer(m, sp, DAYS, ask(action="teacher", classes=[A], subject="Mathematics", new_teacher="Quek"), pick={"new_teacher": "Quek Hong Wei"})
    assert r["choices"] == [] and len(r["groups"]) == 1 and r["groups"][0]["suggestions"][0]["fixes"][0]["teachers"] == ["Quek Hong Wei"], r
    assert typed.resolve(m, sp, ask(action="teacher", new_teacher="Mdm. Quek Mei"), None)["teacher"] == "Quek Mei Ling" and typed.resolve(m, sp, ask(action="teacher", new_teacher="Hong Wei Q"))["teacher"] == "Quek Hong Wei"
    r = typed.answer(m, sp, DAYS, ask(action="move", classes=[A], subject="maths", not_days=["Mon"]))      # Mathematics and Additional Mathematics are both 1A's
    assert r["choices"] == [dict(field="subject", said="maths", options=["Mathematics", "Additional Mathematics"])] and r["groups"] == [], r
    r = typed.answer(m, sp, DAYS, ask(action="move", classes=[A], subject="maths", not_days=["Mon"]), pick={"subject": "Additional Mathematics"}); assert [g["lesson"] for g in r["groups"]] == [2], r
    r = typed.answer(m, sp, DAYS, ask(action="move", classes=["1B"], subject="maths", not_days=["Mon"])); assert r["choices"] == [] and [g["lesson"] for g in r["groups"]] == [3]   # only one is 1B's
    r = typed.answer(m, sp, DAYS, ask(action="move", classes=["9Z"], not_days=["Mon"])); assert r["problems"] == ['There is no class or level called "9Z".'] and r["groups"] == [], r
    r = typed.answer(m, sp, DAYS, ask(action="move", classes=[A], teacher="Nobody Here", not_days=["Mon"])); assert r["problems"] == ['There is no teacher called "Nobody Here".']
    r = typed.answer(m, sp, DAYS, ask(action="move", classes=[A], subject="Basket Weaving", not_days=["Mon"])); assert r["problems"] == [typed.NO_LESSON] == ["No lesson of the timetable matches that."]
    assert typed.resolve(m, sp, ask(action="move", teacher="Ms Goh's"))["lessons"] == [1, 2, 3] and typed.resolve(m, sp, ask(action="move", group="nothing"))["problems"] == [typed.NO_LESSON]
    for s in ("Mdm", "Dr."): assert typed.resolve(m, sp, ask(action="move", teacher=s))["problems"], s     # a title alone names nobody
    # a class written two ways that differ only in case or spaces, with no exact match, is a choice
    m2 = dict(m, classes=[dict(name="2 A", level="S2"), dict(name="2  A", level="S2"), dict(name="3A", level="S3")])
    assert typed.resolve(m2, sp, ask(action="move", classes=["2a"]))["choices"] == [dict(field="classes", said="2a", options=["2 A", "2  A"])]
    assert typed.resolve(m2, sp, ask(action="move", classes=["2a"]), pick={"classes": "2  A"})["choices"] == [] and typed.resolve(m2, sp, ask(action="move", classes=["2 a"]))["choices"] == []
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
    r = typed.answer(m, sp, DAYS, ask(action="move", classes=[A], subject="Mathematics", not_days=["Fri"]))
    assert len(r["groups"]) == 8 and r["more"] == 4 and r["narrow"] == "That matches 12 lessons. Here are the first 8; name a class or a day to narrow it.", r
    order = [(x["d"], x["p"]) for g in r["groups"] for x in m["lessons"] if x["id"] == g["lesson"]]; assert order == sorted(order)
    r = typed.answer(m, sp, DAYS, ask(action="move", classes=[A], subject="Mathematics", from_day="Mon", not_days=["Fri"])); assert r["more"] == 0 and r["narrow"] is None and len(r["groups"]) == 2
    r = typed.answer(m, sp, DAYS, ask(action="move", group="nothing", not_days=["Fri"])); assert r["problems"] == [typed.NO_LESSON]

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
    assert typed.resolve(m, spc, ask(action="move", subject="phys"))["lessons"] == [1] and typed.resolve(m, spc, ask(action="move", subject="ed"))["problems"] == [typed.NO_LESSON]

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
        assert dt < 2, dt; assert r["problems"] == [] and r["choices"] == [] and len(r["groups"]) == 8 and r["more"] > 0, (r["problems"], r["choices"], len(r["groups"]), r["more"])
        offered = sum(len(g["suggestions"]) for g in r["groups"]); print(f"  {len(r['groups'])} lessons answered (+{r['more']}), {offered} suggestions, {dt:.2f} s")
        for g in r["groups"]:
            assert len(g["suggestions"]) <= 3 and (g["none"] is None) == bool(g["suggestions"])
            for s in g["suggestions"]:
                assert helper.chain(m, sp, days, s["fixes"])["state"] in ("ok", "prefer")
                f = s["fixes"][0]; row = next(x for x in m["lessons"] if x["id"] == (f["id"] if f["kind"] == "move" else f["a"]))
                dest = (f["d"] if f["kind"] == "move" else next(x for x in m["lessons"] if x["id"] == f["b"])["d"])
                assert days[dest] != said and (f["kind"] == "swap" or row["id"] == g["lesson"]), (said, s["text"])

print(f"{n} typed checks passed")

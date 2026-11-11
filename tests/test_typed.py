"""Plain-assert tests for typed.py, the typed request read into an ask (no network, no key): .venv/bin/python tests/test_typed.py"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, ROOT)
import typed  # noqa: E402
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
    a = typed._mock("sing a song"); assert typed.check(a) and a["understood"] is False and a["action"] == "none"
    assert a["reply"] == 'The practice reader understands "move <subject> for <class> off <day>" and "give <class> <subject> to <teacher>".'
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
            assert seen["betas"] == ["server-side-fallback-2026-07-01"] and seen["fallbacks"] == "default" and "tools" not in seen
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

print(f"{n} typed checks passed")

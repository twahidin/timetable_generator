"""The AI timetabler: SKILL.md as its instructions, the tools in timetabler.py as its hands.

Set in Railway variables:
  AI_PROVIDER  anthropic | openai | openrouter      (mock = scripted stand-in for testing)
  AI_API_KEY   the provider's key (ANTHROPIC_API_KEY / OPENAI_API_KEY / OPENROUTER_API_KEY also work)
  AI_MODEL     model name exactly as the provider lists it (Anthropic defaults to claude-opus-5-5)
  AI_BASE_URL  optional, for an OpenAI-compatible endpoint other than the default
  AI_EFFORT    Anthropic only: how hard the model thinks, low | medium | high | xhigh | max (default xhigh; none = the model's own)
The key stays on the server; the browser never sees it."""
import json, os, re, time
import anthropic
import requests
import timetabler

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.join(HERE, "skill", "school-timetable-generator", "SKILL.md")
DEFAULT_MODEL = {"anthropic": "claude-opus-5-5"}
DEFAULT_BASE = {"anthropic": "https://api.anthropic.com", "openai": "https://api.openai.com/v1", "openrouter": "https://openrouter.ai/api/v1"}
KEY_VARS = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY", "openrouter": "OPENROUTER_API_KEY"}
MAX_STEPS = 120   # model calls in one go: a long run with many solves and questions still finishes
MAX_TOKENS = 64000   # thinking counts toward this as well as the reply; replies are streamed, so a long one neither times out nor is cut short
EFFORTS = ("low", "medium", "high", "xhigh", "max")
# models that take fallbacks "default" on Anthropic's own API: if a safety filter declines, Anthropic re-runs the request on a fallback model
FALLBACK_MODELS = {"claude-opus-5-5", "claude-opus-5", "claude-fable-5-1", "claude-sonnet-5-5"}

def config():
    p = (os.environ.get("AI_PROVIDER") or "").strip().lower()
    key = os.environ.get("AI_API_KEY") or os.environ.get(KEY_VARS.get(p, "-"), "")
    model = os.environ.get("AI_MODEL") or DEFAULT_MODEL.get(p, "")
    base = (os.environ.get("AI_BASE_URL") or DEFAULT_BASE.get(p, "")).rstrip("/")
    effort = (os.environ.get("AI_EFFORT") or "xhigh").strip().lower()
    effort = None if effort in ("none", "off", "default") or p != "anthropic" else effort if effort in EFFORTS else "xhigh"
    ok = p == "mock" or (p in DEFAULT_BASE and bool(key) and bool(model))
    why = "" if ok else ("AI_PROVIDER is not set." if not p else f"AI_PROVIDER '{p}' is not one of anthropic, openai, openrouter." if p not in DEFAULT_BASE
                         else "AI_API_KEY is not set." if not key else "AI_MODEL is not set.")
    return dict(provider=p, key=key, model=model or ("mock" if p == "mock" else ""), base=base, ok=ok, why=why, effort=effort)

def public_config():
    c = config()
    return dict(ok=c["ok"], provider=c["provider"], model=c["model"], why=c["why"], effort=c["effort"])

def system_prompt(run):
    try: skill = open(SKILL, encoding="utf-8").read()
    except OSError: skill = ""
    skill = re.sub(r"^---.*?---\s*", "", skill, flags=re.S)
    sc = run.spec["school"]
    return f"""You are the timetabler for {sc.get('name')} ({sc.get('timetable')}), working inside the school's timetable app with its timetable committee.

How you work here:
- You act only through the tools. You cannot run code or open files; the tools do what the skill below describes: check_setup is `ttgen check` plus the capacity sums, solve is `ttgen solve`, diagnose is the 'If no timetable is found' steps. The Excel workbook, PDFs and the HTML finder are made when the committee presses Publish, so never try to make them.
- Start with check_setup. If an input problem would stop a sensible timetable, ask the committee how to fix it before solving; otherwise solve.
- After a solve: if every check passed and nothing (or very little) is after school, call finish with a short summary. If lessons fell after school, if checks failed, or if no timetable was found, find out why (show_setup, diagnose), then explain it in plain words and offer the smallest changes as options with ask_committee.
- Never change the setup unless the committee chose that change in answer to your question or asked for it in a message. Use change_setup only to carry out their choice, then solve again.
- Tweaks after a timetable exists ("move 3A Maths off Friday", "Mr Tan needs Wednesday afternoon free"): look first with show_timetable, then make the smallest setup change that does it (usually a rule such as Not available, Not in periods or Fixed at), then solve. The solve starts from the latest timetable and keeps every other lesson where it is unless the change forces it to move; tell the committee which lessons moved. Use keep_previous false only when they ask for a fresh timetable.
- One-off tweaks to the finished timetable ("swap 2B's English and Science on Tuesday", "move 3A Maths to Thursday 10.30"): find the lessons with show_timetable, then use move_lessons. A clean move goes on the timetable and they click Apply or No. If it clashes, nothing changes: offer the clean alternatives it returns (with ask_committee), or, if they want that time, call it again with make_room true. Lasting wishes (a teacher never free on Wednesdays) go into the setup instead, as below.
- What-ifs: when the committee wants to see what a change would do before agreeing ("what if Mr Tan had Wednesdays free?"), or there are two ways out and they want to compare, use try_change instead of change_setup. It solves the change on a copy, shows them a comparison with Keep and Drop buttons and waits; then tell them in a sentence what the change cost (lessons moved, after school, free periods). Try one option at a time.
- Questions about the timetable itself (who teaches 2B on Monday, when is the lab free): answer with show_timetable, without solving.
- Talk like a helpful colleague: short messages (2-5 sentences), names and clock times rather than row numbers or period numbers, one question at a time with 2-4 concrete options.
- The committee may type messages at any time; treat them as their instructions.
- A solve takes minutes: the committee chose up to {timetabler.span_text(run.seconds or timetabler.SOLVE_SECONDS)} each, so leave `seconds` out unless you have a reason. Do not solve more often than needed.

The skill (your reference for the template, the rules and what usually goes wrong):
<skill>
{skill}
</skill>"""


# --------------------------------------------------------------------------------------------- providers
def _post(url, headers, body, tries=4):
    for k in range(tries):
        try:
            r = requests.post(url, headers=headers, json=body, timeout=600)
        except requests.RequestException as e:
            if k == tries - 1: raise RuntimeError(f"could not reach the AI service ({e})")
            time.sleep(3 * (k + 1)); continue
        if r.status_code in (429, 500, 502, 503, 504, 529) and k < tries - 1:
            time.sleep(4 * (k + 1)); continue
        if r.status_code >= 400:
            try: msg = r.json().get("error", {}); msg = msg.get("message", msg) if isinstance(msg, dict) else msg
            except ValueError: msg = r.text[:300]
            raise RuntimeError(f"the AI service said {r.status_code}: {msg}")
        return r.json()
    raise RuntimeError("could not reach the AI service")

def anthropic_body(cfg, system, history, tools):
    msgs = []
    def add(role, block):
        if msgs and msgs[-1]["role"] == role: msgs[-1]["content"].append(block)
        else: msgs.append(dict(role=role, content=[block]))
    for h in history:
        if h["role"] == "user": add("user", dict(type="text", text=h["text"]))
        elif h.get("blocks") and h.get("model") == cfg["model"]: msgs.append(dict(role="assistant", content=h["blocks"]))   # the reply as it came, thinking included
        elif h["role"] == "assistant":
            blocks = ([dict(type="text", text=h["text"])] if h.get("text") else []) + \
                     [dict(type="tool_use", id=c["id"], name=c["name"], input=c["args"] or {}) for c in h.get("calls", [])]
            msgs.append(dict(role="assistant", content=blocks or [dict(type="text", text="...")]))
        elif h["role"] == "tool": add("user", dict(type="tool_result", tool_use_id=h["id"], content=h["result"]))
    return dict(model=cfg["model"], max_tokens=MAX_TOKENS, system=[dict(type="text", text=system, cache_control=dict(type="ephemeral"))], messages=msgs,
                **({"tools": [dict(name=t["name"], description=t["description"], input_schema=t["schema"]) for t in tools]} if tools else {}))

_clients = {}

def _client(cfg):
    k = (cfg["key"], cfg["base"])
    if k not in _clients: _clients[k] = anthropic.Anthropic(api_key=cfg["key"], base_url=cfg["base"], max_retries=4)
    return _clients[k]

KEEP = ("thinking", "redacted_thinking", "text", "tool_use")   # the blocks of a reply that go back on the next request

def call_anthropic(cfg, system, history, tools):
    """one model turn, streamed. Returns (text, tool calls, the reply's content blocks): the blocks go back unchanged on
    the next request, so the model keeps its reasoning across tool calls. Tool inputs are buffered by the API (no eager
    input streaming): they are small, and buffered inputs arrive validated."""
    body = anthropic_body(cfg, system, history, tools)
    if cfg.get("effort"): body["output_config"] = dict(effort=cfg["effort"])
    client = _client(cfg)
    def ask(**extra):
        with client.beta.messages.stream(**body, **extra) as stream: return stream.get_final_message()
    try:
        if cfg["model"] in FALLBACK_MODELS and cfg["base"] == DEFAULT_BASE["anthropic"]:
            try: msg = ask(betas=["server-side-fallback-2026-07-01"], fallbacks="default")
            except anthropic.BadRequestError as e:
                if "fallback" not in str(e).lower(): raise
                msg = ask()   # this account or model does not take fallbacks: ask without them
        else: msg = ask()
    except anthropic.APIConnectionError as e: raise RuntimeError(f"could not reach the AI service ({e})")
    except anthropic.APIStatusError as e: raise RuntimeError(f"the AI service said {e.status_code}: {e.message}")
    # a cut-off or declined reply can hold a half-written tool call, so none of its tools run
    if msg.stop_reason == "max_tokens": raise RuntimeError(f"its reply was cut off at the {MAX_TOKENS:,}-token limit before it finished")
    if msg.stop_reason == "refusal":
        cat = getattr(msg.stop_details, "category", None) if msg.stop_details else None
        raise RuntimeError("the AI service's safety filter declined this request" + (f" ({cat})" if cat else ""))
    text = "\n".join(b.text for b in msg.content if b.type == "text").strip()
    calls = [dict(id=b.id, name=b.name, args=b.input or {}) for b in msg.content if b.type == "tool_use"]
    return text, calls, [b.model_dump(mode="json", exclude_none=True) for b in msg.content if b.type in KEEP and not (b.type == "text" and not b.text)]

def openai_body(cfg, system, history, tools):
    msgs = [dict(role="system", content=system)]
    for h in history:
        if h["role"] == "user": msgs.append(dict(role="user", content=h["text"]))
        elif h["role"] == "assistant":
            m = dict(role="assistant", content=h.get("text") or None)
            if h.get("calls"): m["tool_calls"] = [dict(id=c["id"], type="function", function=dict(name=c["name"], arguments=json.dumps(c["args"] or {}))) for c in h["calls"]]
            msgs.append(m)
        elif h["role"] == "tool": msgs.append(dict(role="tool", tool_call_id=h["id"], content=h["result"]))
    return dict(model=cfg["model"], messages=msgs, **({"tools": [dict(type="function", function=dict(name=t["name"], description=t["description"], parameters=t["schema"])) for t in tools]} if tools else {}))

def call_openai(cfg, system, history, tools):
    headers = {"Authorization": f"Bearer {cfg['key']}", "Content-Type": "application/json"}
    if cfg["provider"] == "openrouter": headers.update({"X-Title": "School timetable app"})
    r = _post(cfg["base"] + "/chat/completions", headers, openai_body(cfg, system, history, tools))
    choice = (r.get("choices") or [{}])[0]
    if choice.get("finish_reason") == "length": raise RuntimeError("its reply was cut off at the model's length limit before it finished")
    if choice.get("finish_reason") == "content_filter": raise RuntimeError("the AI service's content filter stopped the reply")
    msg = choice.get("message") or {}
    calls = []
    for c in msg.get("tool_calls") or []:
        try: args = json.loads(c["function"].get("arguments") or "{}")
        except ValueError: args = {}
        calls.append(dict(id=c.get("id") or f"call{len(calls)}", name=c["function"]["name"], args=args))
    return (msg.get("content") or "").strip(), calls

def call_mock(run, history):
    """scripted stand-in used for testing the app without a real key"""
    tools_done = [h for h in history if h["role"] == "tool"]; last = history[-1]
    secs = int(os.environ.get("MOCK_SOLVE_SECONDS") or 30)
    cid = lambda: f"m{len(history)}"
    if last["role"] == "user" and not tools_done:
        return "I'll check the setup first.", [dict(id=cid(), name="check_setup", args={})]
    if last["role"] == "user":
        return f"(Test assistant) Noted: “{last['text']}”. A real AI model would act on this now.", []
    name, res = last["name"], last["result"]
    if name == "check_setup": return "The setup is consistent. Solving now.", [dict(id=cid(), name="solve", args=dict(seconds=secs))]
    if name == "solve":
        if res.startswith("No timetable found"):
            return "", [dict(id=cid(), name="finish", args=dict(summary="No timetable was found. Read the capacity warnings and notes above: they say what does not fit."))]
        if not any(h["name"] == "ask_committee" for h in tools_done):
            n = res.count("\n- ") if "After-school lessons:\n" in res else 0
            return ("A timetable is ready." + (" Some lessons fall in after-school slots." if "After-school lessons: none" not in res else "")), [dict(
                id=cid(), name="ask_committee", args=dict(question="Keep this timetable, or let PE run in five classes at once instead of four and solve again?",
                                                          options=["Keep this timetable", "Allow 5 PE classes at once and solve again"]))]
        return "", [dict(id=cid(), name="finish", args=dict(summary="Timetable ready. Preview it and publish when the committee is happy."))]
    if name == "ask_committee":
        if "5" in res or "allow" in res.lower():
            idx = next((i for i, r in enumerate(run.spec.get("rules", [])) if r.get("rule") == "At most N at once" and r.get("scope") == "Subject"), None)
            if idx is not None:
                return "Changing the PE rule as agreed.", [dict(id=cid(), name="change_setup", args=dict(
                    changes=[dict(action="set", section="rules", index=idx, field="number", value=5)], reason="Committee agreed: up to 5 PE classes at once"))]
        return "", [dict(id=cid(), name="finish", args=dict(summary="Timetable kept as it is. Preview it and publish when ready."))]
    if name == "change_setup": return "Solving again with the change.", [dict(id=cid(), name="solve", args=dict(seconds=secs))]
    if name == "finish": return "", []
    return "", [dict(id=cid(), name="finish", args=dict(summary="Done."))]

ADVISE = """You help a school timetable committee adjust a finished timetable by hand before it is published. They want to
move one lesson and the move clashes. Suggest 2-4 ways out, best first, as a short numbered list. Each option says
exactly what to change and where: a swap or another time (from the free times and swaps given), moving the clashing
lesson, merging the group with another group of the same subject and level (only if one teacher and one room can take
the combined size), splitting a large group, or giving the lesson or the clashing one to another teacher. Changes to
groups and teachers are made on step 6 (Lessons) of the setup and need a new solve; say so. Use names and clock times.
Do not invent lessons, teachers or rooms that are not in the message. 120 words at most."""

def advise(question):
    """one question to the AI, without tools: ways out of a clashing move on the Adjust page"""
    cfg = config()
    if not cfg["ok"]: raise RuntimeError(f"the AI is not set up ({cfg['why']})")
    if cfg["provider"] == "mock":
        return ("(Test assistant) 1. Pick one of the free times listed, or a clean swap. 2. Let the solver make room: it keeps this lesson "
                "there and moves the few lessons in the way. 3. If the clash is a teacher, give one of the two lessons to another teacher "
                "on step 6, or merge it with a small group of the same subject, then solve again.")
    history = [dict(role="user", text=question)]
    call = call_anthropic if cfg["provider"] == "anthropic" else call_openai
    text = call(cfg, ADVISE, history, [])[0]
    return text

def call_model(cfg, run, system, history):
    """(text, tool calls, content blocks to send back next time, or None)"""
    if cfg["provider"] == "mock": return call_mock(run, history) + (None,)
    if cfg["provider"] == "anthropic": return call_anthropic(cfg, system, history, timetabler.TOOLS)
    return call_openai(cfg, system, history, timetabler.TOOLS) + (None,)


# --------------------------------------------------------------------------------------------- the loop
def run_agent(run, user_text=None):
    cfg = config()
    if not cfg["ok"]:
        run.emit("error", text=f"The AI is not set up ({cfg['why']}). Set AI_PROVIDER, AI_API_KEY and AI_MODEL in Railway, or generate without AI.")
        return
    system = system_prompt(run)
    if not run.history:
        run.history.append(dict(role="user", text="Please generate the timetable from the committee's setup. Check it first, then solve, and work through any conflicts with us."))
    elif user_text:
        run.history.append(dict(role="user", text=user_text))
    for _ in range(MAX_STEPS):
        if run.stop.is_set(): return
        run.progress = "The AI is thinking..."
        try: text, calls, blocks = call_model(cfg, run, system, run.history)
        except Exception as e:
            run.progress = ""; run.emit("error", text=f"The AI could not answer: {e}. Type a message to try again, or generate without AI."); run.save(); return
        run.progress = ""
        run.history.append(dict(role="assistant", text=text, calls=calls, **({"blocks": blocks, "model": cfg["model"]} if blocks else {}))); run.save()
        if text: run.emit("assistant", text=text)
        if not calls: return
        for c in calls:
            if run.stop.is_set():
                result = "Stopped by the committee."
            else:
                result = timetabler.call_tool(run, c["name"], c["args"])
            run.history.append(dict(role="tool", id=c["id"], name=c["name"], result=result[:30000])); run.save()
        if run.stop.is_set(): return
        extra = run.drain_inbox()
        if extra: run.history.append(dict(role="user", text="\n".join(extra)))
        if run.finished and not extra: return
    run.emit("error", text="The AI took too many steps; stopped. Type a message to continue.")

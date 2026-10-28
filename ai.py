"""The AI timetabler: SKILL.md as its instructions, the tools in timetabler.py as its hands.

Set in Railway variables:
  AI_PROVIDER  anthropic | openai | openrouter      (mock = scripted stand-in for testing)
  AI_API_KEY   the provider's key (ANTHROPIC_API_KEY / OPENAI_API_KEY / OPENROUTER_API_KEY also work)
  AI_MODEL     model name exactly as the provider lists it (Anthropic defaults to claude-opus-5-5)
  AI_BASE_URL  optional, for an OpenAI-compatible endpoint other than the default
The key stays on the server; the browser never sees it."""
import json, os, re, time
import requests
import timetabler

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.join(HERE, "skill", "school-timetable-generator", "SKILL.md")
DEFAULT_MODEL = {"anthropic": "claude-opus-5-5"}
DEFAULT_BASE = {"anthropic": "https://api.anthropic.com", "openai": "https://api.openai.com/v1", "openrouter": "https://openrouter.ai/api/v1"}
KEY_VARS = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY", "openrouter": "OPENROUTER_API_KEY"}
MAX_STEPS = 40
MAX_TOKENS = 16000   # the model's thinking counts toward this as well as its reply
# models that take fallbacks "default" on Anthropic's own API: if a safety filter declines, Anthropic re-runs the request on a fallback model
FALLBACK_MODELS = {"claude-opus-5-5", "claude-opus-5", "claude-fable-5-1", "claude-sonnet-5-5"}

def config():
    p = (os.environ.get("AI_PROVIDER") or "").strip().lower()
    key = os.environ.get("AI_API_KEY") or os.environ.get(KEY_VARS.get(p, "-"), "")
    model = os.environ.get("AI_MODEL") or DEFAULT_MODEL.get(p, "")
    base = (os.environ.get("AI_BASE_URL") or DEFAULT_BASE.get(p, "")).rstrip("/")
    ok = p == "mock" or (p in DEFAULT_BASE and bool(key) and bool(model))
    why = "" if ok else ("AI_PROVIDER is not set." if not p else f"AI_PROVIDER '{p}' is not one of anthropic, openai, openrouter." if p not in DEFAULT_BASE
                         else "AI_API_KEY is not set." if not key else "AI_MODEL is not set.")
    return dict(provider=p, key=key, model=model or ("mock" if p == "mock" else ""), base=base, ok=ok, why=why)

def public_config():
    c = config()
    return dict(ok=c["ok"], provider=c["provider"], model=c["model"], why=c["why"])

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
- Questions about the timetable itself (who teaches 2B on Monday, when is the lab free): answer with show_timetable, without solving.
- Talk like a helpful colleague: short messages (2-5 sentences), names and clock times rather than row numbers or period numbers, one question at a time with 2-4 concrete options.
- The committee may type messages at any time; treat them as their instructions.
- A solve takes minutes (default {timetabler.SOLVE_SECONDS} s). Do not solve more often than needed.

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
        elif h["role"] == "assistant":
            blocks = ([dict(type="text", text=h["text"])] if h.get("text") else []) + \
                     [dict(type="tool_use", id=c["id"], name=c["name"], input=c["args"] or {}) for c in h.get("calls", [])]
            msgs.append(dict(role="assistant", content=blocks or [dict(type="text", text="...")]))
        elif h["role"] == "tool": add("user", dict(type="tool_result", tool_use_id=h["id"], content=h["result"]))
    return dict(model=cfg["model"], max_tokens=MAX_TOKENS, system=[dict(type="text", text=system, cache_control=dict(type="ephemeral"))], messages=msgs,
                tools=[dict(name=t["name"], description=t["description"], input_schema=t["schema"]) for t in tools])

def call_anthropic(cfg, system, history, tools):
    body = anthropic_body(cfg, system, history, tools)
    url, headers = cfg["base"] + "/v1/messages", {"x-api-key": cfg["key"], "anthropic-version": "2023-06-01", "content-type": "application/json"}
    if cfg["model"] in FALLBACK_MODELS and cfg["base"] == DEFAULT_BASE["anthropic"]:
        try: r = _post(url, {**headers, "anthropic-beta": "server-side-fallback-2026-07-01"}, {**body, "fallbacks": "default"})
        except RuntimeError as e:
            if "said 400" not in str(e) or "fallback" not in str(e).lower(): raise
            r = _post(url, headers, body)   # this account or model does not take fallbacks: ask without them
    else:
        r = _post(url, headers, body)
    # a cut-off or declined reply can hold a half-written tool call, so none of its tools run
    if r.get("stop_reason") == "max_tokens": raise RuntimeError(f"its reply was cut off at the {MAX_TOKENS:,}-token limit before it finished")
    if r.get("stop_reason") == "refusal":
        cat = (r.get("stop_details") or {}).get("category")
        raise RuntimeError("the AI service's safety filter declined this request" + (f" ({cat})" if cat else ""))
    text ="\n".join(b.get("text", "") for b in r.get("content", []) if b.get("type") == "text").strip()
    calls = [dict(id=b["id"], name=b["name"], args=b.get("input") or {}) for b in r.get("content", []) if b.get("type") == "tool_use"]
    return text, calls

def openai_body(cfg, system, history, tools):
    msgs = [dict(role="system", content=system)]
    for h in history:
        if h["role"] == "user": msgs.append(dict(role="user", content=h["text"]))
        elif h["role"] == "assistant":
            m = dict(role="assistant", content=h.get("text") or None)
            if h.get("calls"): m["tool_calls"] = [dict(id=c["id"], type="function", function=dict(name=c["name"], arguments=json.dumps(c["args"] or {}))) for c in h["calls"]]
            msgs.append(m)
        elif h["role"] == "tool": msgs.append(dict(role="tool", tool_call_id=h["id"], content=h["result"]))
    return dict(model=cfg["model"], messages=msgs, tools=[dict(type="function", function=dict(name=t["name"], description=t["description"], parameters=t["schema"])) for t in tools])

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

def call_model(cfg, run, system, history):
    if cfg["provider"] == "mock": return call_mock(run, history)
    if cfg["provider"] == "anthropic": return call_anthropic(cfg, system, history, timetabler.TOOLS)
    return call_openai(cfg, system, history, timetabler.TOOLS)


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
        try: text, calls = call_model(cfg, run, system, run.history)
        except Exception as e:
            run.progress = ""; run.emit("error", text=f"The AI could not answer: {e}. Type a message to try again, or generate without AI."); run.save(); return
        run.progress = ""
        run.history.append(dict(role="assistant", text=text, calls=calls)); run.save()
        if text: run.emit("assistant", text=text)
        if not calls: return
        for c in calls:
            if run.stop.is_set():
                result = "Stopped by the committee."
            else:
                result = timetabler.call_tool(run, c["name"], c["args"])
            run.history.append(dict(role="tool", id=c["id"], name=c["name"], result=result[:12000])); run.save()
        if run.stop.is_set(): return
        extra = run.drain_inbox()
        if extra: run.history.append(dict(role="user", text="\n".join(extra)))
        if run.finished and not extra: return
    run.emit("error", text="The AI took too many steps; stopped. Type a message to continue.")

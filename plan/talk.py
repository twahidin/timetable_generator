"""The talks of the planning chat. A talk lives only in the server's memory, belongs to the person (or the shared committee
session) that started it, holds the lines the page shows and the history the AI is sent, and runs each answer on a thread of
its own while the page polls. It is the one place where names become codes on the way to the AI (Names.out, Names.scrub)
and codes become names on the way back (Names.back), where a tool the AI asks for becomes a step on the draft, and where the
limits are kept. No Flask here and nothing of app.py. Nothing of a talk is written to disk or to a log.

Locks: the server's lock (_server) guards the list of talks and the answer slots; each talk's own lock guards its lines,
steps and notes. Neither is ever held while the AI is called or while a step runs (schedules.editing() is taken inside a
step only). When both are taken, the talk's lock comes first."""
import collections
import copy
import logging
import secrets
import threading
import time
import traceback

from exams import approval as _approval
from exams import make as _make
from exams import schedules as _schedules
from plan import ai as _ai
from plan import facts as _facts
from plan import steps as _steps
from plan.names import Names
from plan.steps import Refused

log = logging.getLogger("plan")

LIMITS = dict(typed=2000, list=20000, rounds=12, answer=180, list_job=300, messages=60, at_once=2,
              an_hour=60, idle=12 * 3600, talks=5)        # seconds for answer, list_job and idle; talks: at most an owner

EMPTY = "Type what you want to say first."
TOO_LONG = "Keep it under 2,000 characters."
NO_PICK = "That answer is not offered now. Type what you mean instead."
WORKING = "The AI is still answering. Wait, or press Stop."
LONG = "This talk is long. Start a new one; your exam carries on."
BUSY = "The AI is busy. Try again in a few minutes."
AT_ONCE = "The AI is working on other answers. Try again in a moment."
LOST = "This talk was lost when the app restarted. Your exam is safe: press Carry on."
REPUBLISHED = "The timetable was published again: codes and checks are fresh."
WAIT_UNDO = "Wait for the answer, or press Stop."
NO_STEP = "That step is not in this talk."
NO_EXAM = "No exam is started in this talk yet."
HIDDEN = "There are points the app does not show you. The person is told where to look."
NO_SLOTS = "The app has no time to offer for that paper."
SHOWN = "Shown."
NO_LIST = "No list is waiting."
READING = "A list is being read. Wait, or press Stop."
WAIT_LIST = "Say Yes, all or Not now to the list above first."
NEED_EXAM = "Start the exam first: say what it is, its name and its dates."
EMPTY_LIST = "Paste the list, or give an Excel or Word file."
NOT_WAITING = "That list is not waiting any more."
CARRY_ON = "This talk carries on with {name}. Say what you want to do next."
GONE = _steps.GONE

THINKING = "Thinking"
PROGRESS = dict(read_exam="Reading the draft", read_school="Reading the timetable", read_checks="Checking the times",
                offer_slots="Looking for times that fit")
FILLING = "Filling in the draft"
CHANGES = ("papers", "times", "suggested", "days", "put_list")      # the steps after which the app adds its own check lines
QUICK, QUICK_LEN = 4, 60

_now = time.time                    # the clock of the idle limit and the hour's answers (the tests put in their own)
_server = threading.Lock()
_talks = {}                         # id -> Talk
_running = [0]                      # answers running now, on the whole server
_starts = collections.deque()       # when each answer of the last hour started


def _fault(e):
    """the type of a fault and its frames, never its text"""
    frames = "; ".join(f"{f.filename.rsplit('/', 1)[-1]}:{f.lineno} {f.name}" for f in traceback.extract_tb(e.__traceback__))
    log.error("plan.talk fault %s at %s", type(e).__name__, frames)


def _hidden_line(n) -> str:
    return f"{n} more {'point' if n == 1 else 'points'} with extra time: see the Papers tab."


def _names(env, pub) -> Names:
    return Names(pub, env.people(), ((pub or {}).get("model") or {}).get("students"))


def _exam_of(env, id):
    s = env.load(id) if isinstance(id, str) and id else None
    return s if isinstance(s, dict) and s.get("kind") in _schedules.KINDS else None


# ---------------------------------------------------------------- a talk
class Talk:
    """the talk state of plan.steps (exam, words, offered, last_rev) and its own: id, owner, lines, messages, steps, names,
    stamp, notes, lock, halt (the stop of the answer or list job running), working, progress; reading (a list job runs),
    lists (list id -> what waits for a yes) and waiting (the id of the list that waits, or None)"""

    def __init__(self, owner, names, stamp):
        self.id, self.owner = secrets.token_urlsafe(18), owner
        self.exam, self.words, self.offered, self.last_rev = None, [], {}, None
        self.lines, self.messages, self.steps, self.notes = [], [], {}, []
        self.names, self.stamp = names, stamp
        self.lock, self.halt = threading.Lock(), threading.Event()
        self.working, self.busy, self.progress, self.closed, self.begun, self.gone_said = False, False, "", False, False, False
        self.thread, self.used, self._n = None, _now(), 0
        self.reading, self.lists, self.waiting = False, {}, None
        self.checked = None                         # (key, checklist): the last checklist view made, and what it was made from

    def add(self, kind, text, step=None, undo=None, quick=None) -> dict:
        """a line (under the talk's lock); n counts from 1 and never changes"""
        self._n += 1
        line = dict(n=self._n, kind=kind, text=text, step=step, undo=undo, buttons=[], table=None, quick=list(quick or []))
        self.lines.append(line)
        return line


def open(owner, env, exam=None) -> Talk:
    """a new talk for owner (a person's id or the shared session's plan_sid), on exam when given"""
    if not isinstance(owner, str) or not owner:
        raise ValueError("a talk needs its owner")
    sweep(_now())
    env.may()
    s = None
    if exam is not None:
        s = _exam_of(env, exam)
        if s is None:
            raise Refused(GONE)
    pub = env.pub()
    talk = Talk(owner, _names(env, pub), _make.published_at(pub or {}))
    if s is not None:
        talk.exam, talk.last_rev = s["id"], _schedules.rev_of(s)
        talk.add("sys", CARRY_ON.format(name=s.get("name") or "this exam"))        # the page's line only: the AI has its own note
    with _server:
        mine = [t for t in _talks.values() if t.owner == owner]
        while len(mine) >= LIMITS["talks"]:
            idle = [t for t in mine if not t.working]
            if not idle:
                break
            old = min(idle, key=lambda t: t.used)
            _drop(old)
            mine.remove(old)
        _talks[talk.id] = talk
    return talk


def _drop(talk):
    """(under _server) the talk is gone; an answer still running ends at its next check"""
    _talks.pop(talk.id, None)
    talk.closed = True
    talk.halt.set()


def get(id, owner) -> Talk | None:
    """the talk with this id when it is owner's; None for any other owner, a closed one, or after a restart"""
    sweep(_now())
    with _server:
        t = _talks.get(id) if isinstance(id, str) else None
        if t is None or t.closed or t.owner != owner or not isinstance(owner, str):
            return None
        t.used = _now()
        return t


def sweep(now):
    """drop the talks left idle 12 hours, and the closed ones"""
    with _server:
        for t in [t for t in _talks.values() if t.closed or now - t.used >= LIMITS["idle"]]:
            _drop(t)


def close(talk):
    with _server:
        _drop(talk)


def drop_owner(owner):
    """every talk of this owner is gone (they signed out); an answer still running ends at its next check"""
    with _server:
        for t in [t for t in _talks.values() if t.owner == owner]:
            _drop(t)


def stop(talk):
    """the answer running ends at its next check; a step already running finishes whole. Nothing when not working"""
    with talk.lock:
        if talk.working:
            talk.halt.set()


def wait(talk, timeout) -> bool:
    """join the answer's thread (for the tests): True when it has ended"""
    th = talk.thread
    if th is not None:
        th.join(timeout)
        return not th.is_alive()
    return True


# ---------------------------------------------------------------- the server's slots
def _take():
    """(a stamp) one of the 2 at a time and of the 60 an hour, or Refused"""
    with _server:
        now = _now()
        while _starts and now - _starts[0] >= 3600:
            _starts.popleft()
        if len(_starts) >= LIMITS["an_hour"]:
            raise Refused(BUSY)
        if _running[0] >= LIMITS["at_once"]:
            raise Refused(AT_ONCE)
        _running[0] += 1
        _starts.append(now)
        return now


def _give(stamp, used=True):
    with _server:
        _running[0] = max(0, _running[0] - 1)
        if not used:
            try:
                _starts.remove(stamp)
            except ValueError:
                pass


# ---------------------------------------------------------------- an answer
def _last_quick(talk) -> list:
    """the quick answers that may be pressed now: the last ai line's, when no message of the person came after it"""
    for l in reversed(talk.lines):
        if l["kind"] == "me":
            return []
        if l["kind"] == "ai":
            return l["quick"]
    return []


def _first_notes(talk, env, pub) -> list:
    """what the AI is told in the first message of a talk: the exam it is on and its status, and what is missing"""
    out = []
    if talk.exam:
        s = _exam_of(env, talk.exam)
        if s is not None:
            out.append(f"This talk is on the exam {s.get('name')}. Its status: {_approval.label(s, env.today())}.")
            why = _steps.editable(s, env.today())
            if why:
                out.append(why)
    out += [m["text"] for m in _facts.missing(pub, env.cal(), env.settings())]
    return out


def say(talk, env, text, pick=None, call=None):
    """the person's message (or the quick answer pick they pressed: then it is the message) -> the answer starts on its own
    thread and say returns at once. Refused with a sentence when it cannot start"""
    words = pick if pick is not None else text
    if not isinstance(words, str) or not words.strip():
        raise Refused(EMPTY)
    words = words.strip()
    if len(words) > LIMITS["typed"]:
        raise Refused(TOO_LONG)
    env.may()                                           # a right that ended is refused before anything is sent
    with talk.lock:
        if talk.closed:
            raise Refused(LOST)
        if pick is not None and words not in _last_quick(talk):
            raise Refused(NO_PICK)
        if talk.working or talk.busy:
            raise Refused(READING if talk.reading else WORKING)
        if sum(l["kind"] == "me" for l in talk.lines) >= LIMITS["messages"]:
            raise Refused(LONG)
        stamp = _take()
        talk.working, talk.progress, talk.halt = True, THINKING, threading.Event()
        halt = talk.halt
    started = False
    try:
        pub = env.pub()
        fresh = _make.published_at(pub or {})
        names = _names(env, pub) if fresh != talk.stamp else None          # built outside the lock: it reads the timetable
        first = [] if talk.begun else _first_notes(talk, env, pub)
        with talk.lock:
            if names is not None:
                talk.names, talk.stamp, talk.offered = names, fresh, {}
                talk.add("sys", REPUBLISHED)
                talk.notes.append("The timetable was published again: the codes of people start again from this message, "
                                  "so a code in an earlier message may stand for someone else now.")
            notes, talk.notes, talk.begun = first + talk.notes, [], True
            sent = talk.names.out(words, "typed")
            if notes:
                talk.messages.append(dict(role="user", content="\n".join(f"[The app: {talk.names.out(n, 'app')}]" for n in notes)))
            talk.messages.append(dict(role="user", content=sent))
            talk.words = [sent]
            talk.add("me", words)
            talk.used = _now()
            deadline = time.monotonic() + LIMITS["answer"]
            talk.thread = threading.Thread(target=_answer, args=(talk, env, halt, deadline, call, stamp), daemon=True)
            talk.thread.start()
            started = True
    finally:
        if not started:
            with talk.lock:
                talk.working, talk.progress, talk.words = False, "", []
            _give(stamp, used=False)


def _mend(messages):
    """every tool_use of the last reply has its tool_result (run_loop sees to it; this is for a fault inside it)"""
    last = messages[-1] if messages else None
    if not isinstance(last, dict) or last.get("role") != "assistant" or not isinstance(last.get("content"), list):
        return
    ids = [_ai._get(b, "id") for b in last["content"] if _ai._get(b, "type") == "tool_use"]
    if ids:
        messages.append(dict(role="user", content=[dict(type="tool_result", tool_use_id=i, content=_ai.STOPPED, is_error=True)
                                                   for i in ids]))


def _answer(talk, env, halt, deadline, call, stamp):
    """the thread of one answer: the loop, then its lines; working ends and the slot is given back whatever happens"""
    texts, quick, seen, status = [], [], {}, "failed"
    try:
        got = _ai.run_loop(talk.messages, texts.append, lambda name, args: _tool(talk, env, name, args, quick, seen), halt,
                           deadline, call=call, max_rounds=LIMITS["rounds"])
        status = got.get("status") if isinstance(got, dict) else "failed"
    except Exception as e:
        _fault(e)
        status = "failed"
    finally:
        try:
            _mend(talk.messages)
            with talk.lock:
                _end(talk, status if status == "done" or not halt.is_set() else "stopped", texts, quick)   # a whole answer is shown
        except Exception as e:
            _fault(e)
        finally:
            _give(stamp)                                # first: the talk's next answer never finds its own slot still taken
            with talk.lock:
                talk.working, talk.progress, talk.words, talk.used = False, "", [], _now()


def _end(talk, status, texts, quick):
    """(under the talk's lock) the answer's lines: its text with the quick answers when done; else the text there was, then
    the sentence of how it ended. A stopped answer gives no ai line"""
    text = talk.names.back("\n\n".join(t for t in texts if isinstance(t, str) and t.strip()).strip())
    if status == "done":
        if text or quick:
            talk.add("ai", text, quick=[talk.names.back(q) for q in quick])
        return
    if status == "stopped":
        talk.add("sys", _ai.STOPPED)
        return
    if text:
        talk.add("ai", text)
    talk.add("sys", _ai.SENTENCES.get(status, _ai.SENTENCES["failed"]))


# ---------------------------------------------------------------- the tools
def _tool(talk, env, name, args, quick, seen):
    """one tool the AI asked for -> its result, names made codes. Never raises for a refusal: the sentence is the result"""
    with talk.lock:
        talk.progress = FILLING if name in _ai.ACTIONS else PROGRESS.get(name, THINKING)
    try:
        try:
            env.may()                                   # a right that ended while the AI answered: reads are refused too
            r = _handle(talk, env, name, args, quick, seen)
        except Refused as e:
            r = str(e)
        return talk.names.scrub(r, "app")
    finally:
        with talk.lock:
            talk.progress = THINKING


def _back(names, x):
    """every string value put back to names, to any depth (keys never)"""
    if isinstance(x, str):
        return names.back(x)
    if isinstance(x, dict):
        return {k: _back(names, v) for k, v in x.items()}
    if isinstance(x, list):
        return [_back(names, v) for v in x]
    return x


def _need_exam(talk, env):
    if not talk.exam:
        raise Refused(NO_EXAM)
    s = _exam_of(env, talk.exam)
    if s is None:
        raise Refused(GONE)
    return s


def _for_ai(c) -> dict:
    """the checks as the AI is shown them: never the reason of the points it cannot see"""
    return dict(errors=[dict(text=e) for e in c.get("errors") or []], warnings=[dict(text=w) for w in c.get("warnings") or []],
                unchecked=[dict(text=c["unchecked"])] if c.get("unchecked") else [],
                hidden=[dict(text=HIDDEN)] if c.get("hidden") else [])


def _checks(talk, env, seen):
    """the app's check of the exam now, with its own sys lines (the same text not twice in a row for one answer)"""
    s = _exam_of(env, talk.exam) if talk.exam else None
    if s is None:
        return None
    c = _facts.checks(s, env.pub(), env.cal(), env.settings())
    with talk.lock:
        for key, text in (("hidden", _hidden_line(c["hidden"]) if c.get("hidden") else ""), ("unchecked", c.get("unchecked") or "")):
            if text and seen.get(key) != text:
                talk.add("sys", text)
            seen[key] = text
    return c


def _handle(talk, env, name, args, quick, seen):
    if name == "read_exam":
        s = _need_exam(talk, env)
        pub, cal, xset = env.pub(), env.cal(), env.settings()
        last = _facts.last_values(s, env.all_saved())
        lines = [dict(key=l["key"], title=l["title"], state=l["state"], text=l["text"])
                 for l in _facts.checklist(s, pub, cal, xset, last)]
        return dict(exam=_facts.overview(s, pub, cal, xset), checklist=lines)
    if name == "read_school":
        pub, xset = env.pub(), env.settings()
        return dict(school=_facts.school(pub, xset), missing=[m["text"] for m in _facts.missing(pub, env.cal(), xset)])
    if name == "read_checks":
        s = _need_exam(talk, env)
        return _for_ai(_facts.checks(s, env.pub(), env.cal(), env.settings()))
    if name == "offer_slots":
        s = _need_exam(talk, env)
        paper = args.get("paper")
        if not isinstance(paper, str):
            return NO_SLOTS
        pub, cal, xset = env.pub(), env.cal(), env.settings()
        found = _facts.slots(s, pub, cal, xset, paper)
        talk.offered[paper] = found
        unchecked = _facts.checks(s, pub, cal, xset).get("unchecked") or ""
        if not found:
            return f"{NO_SLOTS} {unchecked}".strip()
        return dict(paper=paper, offers=found, unchecked=[dict(text=unchecked)] if unchecked else [])
    if name in _ai.ACTIONS:
        action, a, said = _ai.args_of(name, args)
        step = _steps.run(env, talk, action, _back(talk.names, a), said)
        with talk.lock:
            talk.steps[step["id"]] = step
            talk.add("did", talk.names.back(step["text"]), step=step["id"], undo=bool(step.get("can_undo")))
        out = dict(text=step["text"])
        if action in CHANGES:
            try:                                        # the step is done: a fault in its checks never hides that from the AI
                c = _checks(talk, env, seen)
                if c is not None:
                    checked = dict(out, checks=_for_ai(c))
                    talk.names.scrub(checked, "app")
                    out = checked
            except Exception as e:
                _fault(e)
        return out
    if name == "offer_answers":
        got = args.get("answers")
        quick[:] = [x.strip()[:QUICK_LEN] for x in (got if isinstance(got, list) else []) if isinstance(x, str) and x.strip()][:QUICK]
        return SHOWN
    if name == "accept_list":
        from plan import listjob
        return listjob.accept(talk, env, args, seen)
    if name == "correct_list":
        from plan import listjob
        return listjob.correct(talk, env, args)
    return _ai.NO_SUCH


# ---------------------------------------------------------------- the person's own actions
def undo(talk, env, step_id):
    """take a step of this talk back; the AI is told at the top of the next message"""
    with talk.lock:
        if talk.working or talk.busy:
            raise Refused(WAIT_UNDO)
        step = talk.steps.get(step_id) if isinstance(step_id, str) else None
        if step is None:
            raise Refused(NO_STEP)
        talk.busy = True
    try:
        line = _steps.undo(env, step, talk)
        with talk.lock:
            text = talk.names.back(line["text"])
            talk.add("did", text, undo=False)
            talk.notes.append(f"The person took a step back on the page. {text}")
            talk.used = _now()
        if step.get("action") in CHANGES:
            _checks(talk, env, {})
        return line
    finally:
        with talk.lock:
            talk.busy = False


def paste(talk, env, text=None, filename=None, data=None, call=None):
    """the agreed list of papers, pasted (text) or given as a file (filename, data): its job starts on its own thread and
    paste returns at once (plan/listjob.py). Refused with a sentence when it cannot start"""
    from plan import listjob
    listjob.paste(talk, env, text=text, filename=filename, data=data, call=call)


def confirm_list(talk, env, list_id, yes):
    """the person's Yes, all (yes) or Not now to the list that waits"""
    from plan import listjob
    listjob.confirm(talk, env, list_id, yes)


def view(talk, env, after=0) -> dict:
    """what the page draws: the lines after n, whether an answer runs and its progress, the exam, the checklist, what is
    missing, what may be done now and the highest n"""
    ex = talk.exam                                      # read once: the answer's thread may start the exam meanwhile
    s = _exam_of(env, ex) if ex else None
    with talk.lock:
        if ex and s is None and not talk.gone_said:
            talk.gone_said = True
            talk.add("sys", GONE)
        after = after if isinstance(after, int) and not isinstance(after, bool) else 0
        lines = [copy.deepcopy(l) if l["kind"] == "list" else dict(l, quick=list(l["quick"]), buttons=list(l["buttons"]))
                 for l in talk.lines if l["n"] > after]
        for l in lines:
            st = talk.steps.get(l["step"]) if l["step"] else None
            if st is not None:
                l["undo"] = True if st.get("can_undo") and not st.get("undone") else False if st.get("undone") else None   # None: no Take it back, and never "Taken back"
        working, progress, last = talk.working, talk.progress if talk.working else "", talk._n
        reading, waiting = talk.reading, talk.waiting
        long = sum(l["kind"] == "me" for l in talk.lines) >= LIMITS["messages"]
    pub, cal, xset = env.pub(), env.cal(), env.settings()
    exam, checklist = None, []
    try:
        today = env.today()
        if s is not None:
            exam = dict(id=s.get("id"), name=s.get("name"), status=_approval.label(s, today), link=f"/exams/{s.get('id')}")
        key = (s.get("id"), _schedules.rev_of(s)) if s is not None else None
        key = (key, _make.published_at(pub or {}), (xset or {}).get("saved_at"), str(today))
        with talk.lock:
            kept = talk.checked
        if kept is not None and kept[0] == key:         # the full check is run again only when what it reads changed
            checklist = copy.deepcopy(kept[1])
        else:
            checklist = _facts.checklist(s, pub, cal, xset, _facts.last_values(s, env.all_saved()))
            with talk.lock:
                talk.checked = (key, copy.deepcopy(checklist))
    except _facts.ODD:
        checklist = []
    why = READING if working and reading else WORKING if working else LONG if long else ""
    can = dict(say=not why, list=not why and not waiting, stop=working, why=why or (WAIT_LIST if waiting else ""))
    return dict(lines=lines, working=working, progress=progress, exam=exam, checklist=checklist,
                missing=_facts.missing(pub, cal, xset), can=can, last=last)

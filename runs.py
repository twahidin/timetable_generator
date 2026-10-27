"""Generation runs: one at a time, in a background thread, with an event log the committee's chat shows.
A run works on its own copy of the setup; the committee's saved setup only changes if they choose to keep the
AI's changes."""
import copy, json, os, queue, threading, time, uuid
from store import RUNS, now, write_json, read_json
import timetabler

class Run:
    def __init__(self, rid, ai, spec=None):
        self.id, self.ai = rid, ai
        self.dir = os.path.join(RUNS, rid); os.makedirs(self.dir, exist_ok=True)
        self.spec, self.original = spec, copy.deepcopy(spec)
        self.events, self.history, self.changes, self.inbox = [], [], [], []
        self.lock = threading.RLock(); self.answers = queue.Queue(); self.stop = threading.Event()
        self.state, self.busy, self.finished, self.waiting = "starting", False, False, None
        self.progress, self.solved, self.solves, self.started, self.error = "", None, 0, now(), None

    # ---- log
    def emit(self, type_, **kw):
        with self.lock:
            e = dict(n=len(self.events) + 1, t=time.strftime("%H:%M"), type=type_, **kw)
            self.events.append(e)
            with open(os.path.join(self.dir, "events.jsonl"), "a", encoding="utf-8") as f: f.write(json.dumps(e, ensure_ascii=False) + "\n")
            return e

    def save(self):
        with self.lock:
            write_json(os.path.join(self.dir, "state.json"), dict(id=self.id, ai=self.ai, started=self.started, solved=self.solved, solves=self.solves,
                                                                   changes=self.changes, finished=self.finished))
            write_json(os.path.join(self.dir, "work.json"), self.spec)
            write_json(os.path.join(self.dir, "history.json"), self.history)

    def snapshot(self, after=0):
        with self.lock:
            s = self.solved
            return dict(id=self.id, ai=self.ai, state=self.state, busy=self.busy, started=self.started, progress=self.progress,
                        waiting=self.waiting is not None, changes=len(self.changes), finished=self.finished,
                        solved={k: v for k, v in s.items() if k not in ("setup", "timetable", "placements")} if s else None,
                        events=[e for e in self.events if e["n"] > after])

    # ---- questions and messages
    def ask(self, question, options):
        e = self.emit("question", text=question, options=options)
        with self.lock: self.waiting, self.state = e["n"], "waiting"
        while True:
            try: ans = self.answers.get(timeout=1)
            except queue.Empty:
                if self.stop.is_set(): ans = None
                else: continue
            break
        with self.lock: self.waiting, self.state = None, "running"
        return ans

    def drain_inbox(self):
        with self.lock:
            msgs, self.inbox = self.inbox, []
            return msgs


_current = None
_lock = threading.Lock()

def current():
    global _current
    with _lock:
        if _current is None: _current = _load_last()
        return _current

def _load_last():
    """after a restart: show the last run read-only (its timetables can still be previewed and published)"""
    try: ids = sorted((d for d in os.listdir(RUNS) if os.path.isdir(os.path.join(RUNS, d))), key=lambda d: os.path.getmtime(os.path.join(RUNS, d)))
    except OSError: return None
    if not ids: return None
    rid = ids[-1]; st = read_json(os.path.join(RUNS, rid, "state.json"), {})
    r = Run(rid, st.get("ai", False), read_json(os.path.join(RUNS, rid, "work.json")))
    r.started, r.solved, r.solves, r.changes, r.finished = st.get("started", ""), st.get("solved"), st.get("solves", 0), st.get("changes", []), st.get("finished", False)
    r.history = read_json(os.path.join(RUNS, rid, "history.json"), []) or []
    try:
        with open(os.path.join(r.dir, "events.jsonl"), encoding="utf-8") as f: r.events = [json.loads(x) for x in f if x.strip()]
    except OSError: pass
    r.state = "done"
    if r.events and r.events[-1]["type"] not in ("summary", "published", "stopped"):
        r.emit("stopped", text="The server restarted, so this run stopped. Its last timetable (if any) can still be previewed and published.")
    return r

def _thread(run, target, *args):
    def body():
        with run.lock: run.busy, run.state = True, "running"
        try: target(run, *args)
        except Exception as e:
            run.error = str(e); run.emit("error", text=f"Something went wrong: {e}")
        finally:
            with run.lock:
                run.busy = False; run.state = "stopped" if run.stop.is_set() else "done"
            run.save()
    t = threading.Thread(target=body, daemon=True); t.start()

def start(spec, use_ai):
    global _current
    import ai
    with _lock:
        if _current is not None and _current.busy: raise RuntimeError("A run is still going. Stop it first.")
        rid = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:4]
        run = Run(rid, use_ai, spec); _current = run
    from ttgen.reader import derive
    derive(run.spec); run.save()
    run.emit("status", text=f"Started {'with the AI timetabler' if use_ai else 'without AI'} from the setup saved at {now()}.")
    if use_ai: _thread(run, ai.run_agent, None)
    else: _thread(run, lambda r: timetabler.plain_flow(r))
    return run

def message(text):
    """a committee message: answers a waiting question, joins a busy run, or starts a new round of AI work"""
    import ai
    run = current()
    if run is None: raise RuntimeError("Nothing has been generated yet.")
    if not run.ai: raise RuntimeError("This run was made without AI, so there is no one to answer. Generate with AI to use the chat.")
    run.emit("user", text=text)
    with run.lock:
        if run.waiting is not None: run.answers.put(text); return run
        if run.busy: run.inbox.append(text); return run
        run.stop.clear(); run.finished = False
    _thread(run, ai.run_agent, text)
    return run

def stop():
    run = current()
    if run and run.busy:
        run.stop.set(); run.answers.put(None)
        run.emit("stopped", text="Stopped by the committee. The best timetable found so far (if any) is kept.")
    return run

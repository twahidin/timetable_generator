"""The draft: the timetable the committee uploaded, kept on the server beside the saved setup. It is checked against the
setup as it is now (ttgen.verify), each difference is decided on (change step 5, leave it, or still open), and the
draft is published when the committee is ready. Files and decisions live in DATA_DIR/draft."""
import os, re, shutil, threading
from ttgen.export import model_from_files
from ttgen.spec import typed_rules
from ttgen import choices, verify
import store, sync

DIR = os.path.join(store.DATA, "draft")
ANSWERS = ("step5", "left", "open")
_lock = threading.RLock()   # always taken before store's locks, never inside them

def _p(name): return os.path.join(DIR, name)
def exists(): return os.path.exists(_p("meta.json"))

def paths():
    """(setup workbook or None, timetable file) of the draft"""
    tp = next(os.path.join(DIR, f) for f in sorted(os.listdir(DIR)) if f.startswith("timetable."))
    return (_p("setup.xlsx") if os.path.exists(_p("setup.xlsx")) else None), tp

def model(spec): return model_from_files(*paths(), spec=spec)

def save(setup_path, timetable_path, source, spec):
    """replace the draft with these files, read against the setup spec first (so a file that cannot be read never replaces a
    good draft); returns the model, for info(model=). The 'left' decisions carry over (info drops the ones whose warning is gone)."""
    with _lock:
        new, old = DIR + ".new", DIR + ".old"
        shutil.rmtree(new, ignore_errors=True); os.makedirs(new)
        if setup_path: shutil.copy(setup_path, os.path.join(new, "setup.xlsx"))
        shutil.copy(timetable_path, os.path.join(new, "timetable" + os.path.splitext(timetable_path)[1]))
        try: m = model_from_files(os.path.join(new, "setup.xlsx") if setup_path else None, [os.path.join(new, f) for f in os.listdir(new) if f.startswith("timetable.")][0], spec=spec)
        except Exception as e:
            shutil.rmtree(new, ignore_errors=True); raise ValueError(f"Could not read the files: {e}")
        if not m["lessons"]: shutil.rmtree(new, ignore_errors=True); raise ValueError("The timetable has no lessons.")
        keep = {k: d for k, d in (store.read_json(_p("decisions.json"), {}) or {}).items() if d.get("answer") == "left"}
        store.write_json(os.path.join(new, "decisions.json"), keep)
        store.write_json(os.path.join(new, "meta.json"), dict(source=source, uploaded_at=store.now(), fixes=[], school=m["file_school"],
                                                              config_id=str(((m["setup"].get("school") or {}).get("config_id")) or "").strip()))
        shutil.rmtree(old, ignore_errors=True)
        if os.path.exists(DIR): os.replace(DIR, old)
        os.replace(new, DIR); shutil.rmtree(old, ignore_errors=True)
        return m

def summary():
    """what /api/status shows of the draft, from meta.json alone (no model is built)"""
    meta = store.read_json(_p("meta.json")) if exists() else None
    return dict(uploaded_at=meta.get("uploaded_at"), source=meta.get("source"), open=meta.get("open")) if meta else None

def _build(m=None, rec=None):
    """the draft checked against the setup as it is now (or rec, a setup record): the fields of info() before decisions are
    laid over them. The files are read under the lock (a new upload swaps the folder); the model is built outside it, or given."""
    rec = rec or store.setup_record(); spec = rec["spec"]
    if not spec: raise LookupError("no setup")
    with _lock:
        meta = store.read_json(_p("meta.json"), {})
        if m is None: args = paths()
    if m is None: m = model_from_files(*args, spec=spec)
    ws = verify.warnings(m); ch = m["checks"]
    cid, ver = meta.get("config_id") or "", rec["v"]; got = re.fullmatch(r"v(\d+)", cid)
    state = ("unknown" if not cid else "unsaved" if cid.endswith("+") else "unknown" if not got else
             "same" if int(got[1]) == ver else "older" if int(got[1]) < ver else "newer")
    ours, theirs = str((spec.get("school") or {}).get("name") or "").strip(), meta.get("school") or ""
    return dict(source=meta.get("source"), uploaded_at=meta.get("uploaded_at"), config_id=cid, setup_version=f"v{ver}", config_state=state,
                school=m["school"]["name"], file_school=theirs, timetable=m["school"]["timetable"], lessons=ch["lessons"], classes=len(m["classes"]), teachers=len(m["teachers"]),
                students=len(m["students"]), after=ch["after_school"][:30], notes=m["notes"][:12], rule_report=m.get("rule_report") or [],
                choices_used=m.get("choices_used") or [], choices=len(spec.get("choices") or []) - len({i for i, _ in choices.problems(spec)}),
                typed=len(typed_rules(spec)), warnings=ws["warnings"], not_checked=ws["not_checked"], fixes=meta.get("fixes") or [],
                other_school=ours if ours and theirs and ours.lower() != theirs.lower() else "")

def _finish(j, change=None):
    """lay the decisions over the warnings and count them. Under the lock the decisions are read again from disk (a decision
    made while the model was being built stays), change = (key, decision or None) is applied, and a decision whose warning is
    gone is dropped, except the step5 ones: they record that step 5 was updated from the timetable."""
    keys = {w["key"] for w in j["warnings"]}
    with _lock:
        decisions = store.read_json(_p("decisions.json"), {}) or {} if exists() else {}
        if change:
            if change[1] is None: decisions.pop(change[0], None)
            else: decisions[change[0]] = change[1]
        decisions = {k: d for k, d in decisions.items() if k in keys or d.get("answer") == "step5"}
        ws = [dict(w, decision=decisions.get(w["key"])) for w in j["warnings"]]
        n = sum(1 for w in ws if not w["decision"] or w["decision"]["answer"] == "left")
        if exists():
            store.write_json(_p("decisions.json"), decisions)
            store.write_json(_p("meta.json"), dict(store.read_json(_p("meta.json"), {}), open=n))
    return dict(j, warnings=ws, open=n, left=sum(1 for w in ws if (w["decision"] or {}).get("answer") == "left"),
                step5=sum(1 for d in decisions.values() if d.get("answer") == "step5"))

def info(model=None, rec=None):
    """the draft checked against the current setup (or rec), or None without a draft. LookupError when no setup is saved."""
    if not exists(): return None
    return _finish(_build(model, rec))

def _applied(op):
    """an op as it is applied: a new row gets its id here, so the checks stay the same from one build to the next"""
    return ["add", op[1], dict(op[2], _id=sync.new_id()), op[3]] if op and op[0] == "add" else op

def decide(key, answer):
    """record what to do with one warning; 'step5' changes the setup to match the timetable. Returns info()."""
    if answer not in ANSWERS: raise ValueError("Choose what to do with the warning.")
    if not exists(): raise ValueError("There is no draft.")
    if answer != "step5":
        j = _build(); w = next((w for w in j["warnings"] if w["key"] == key), None)
        if answer == "open": return _finish(j, (key, None))
        if not w: raise ValueError("That warning is no longer on the list.")
        return _finish(j, (key, dict(answer="left", at=store.now())))
    with _lock:   # from the build to the change: a second click waits, then finds the warning gone (so a row is never added twice)
        j = _build(); w = next((w for w in j["warnings"] if w["key"] == key), None)
        if not w: raise ValueError("That warning is no longer on the list.")
        if w["ops"] is None: raise ValueError("This difference is set on step 3 for the whole level; the app does not change it from here.")
        store.restore_point("Before updating step 5 from the timetable")
        try: store.apply_changes([_applied(op) for op in w["ops"]], client="draft", since=int(j["setup_version"][1:]))
        except store.Refused as e: raise ValueError(str(e))
        except store.Replaced: raise ValueError("The setup was replaced while this was happening. Check the list again.")
        except LookupError: raise ValueError("Save the school's setup first: the timetable is checked against it.")
        return _finish(_build(), (key, dict(answer="step5", at=store.now())))

def publish():
    """make the draft the published timetable, checked against the setup as it is now"""
    with _lock:
        rec = store.setup_record(); j = info(rec=rec)   # one read of the setup: the one checked against is the one published with
        if j is None: raise FileNotFoundError("no draft")
        meta = store.read_json(_p("meta.json"), {}); decisions = store.read_json(_p("decisions.json"), {}) or {}
        left = [w["text"] for w in j["warnings"] if (w["decision"] or {}).get("answer") == "left"]
        sp, tp = paths()
        store.publish(sp, tp, source=meta.get("source"), spec=rec["spec"], log=lambda *x: None,
                      extra=dict(compared_v=j["setup_version"], open=j["open"], left=left, decisions={k: d["answer"] for k, d in decisions.items()}, fixes=[]))
        return dict(j, published=True)

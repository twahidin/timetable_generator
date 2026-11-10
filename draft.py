"""The draft: the timetable the committee uploaded, kept on the server beside the saved setup. It is checked against the
setup as it is now (ttgen.verify), each difference is decided on (change step 5, leave it, or still open), and the
draft is published when the committee is ready. Files and decisions live in DATA_DIR/draft."""
import copy, json, os, re, shutil, threading
from ttgen.export import ENTIRE, model_from_files
from ttgen.database import write_db
from ttgen.spec import typed_rules
from ttgen import choices, verify
import store, sync, fixes

DIR = os.path.join(store.DATA, "draft")
ANSWERS = ("step5", "left", "open", "met")
_lock = threading.RLock()   # always taken before store's locks, never inside them
class NoDraft(Exception): pass
class UnpublishedFixes(Exception):
    """the draft has fixes that were never published; count: how many"""
    def __init__(self, count): super().__init__("The draft has fixes that were never published."); self.count = count
_cache = {}                 # one entry: the model of the draft with its fixes applied, (key, model, fx); one worker, so a dict under _lock

def _p(name): return os.path.join(DIR, name)
def exists(): return os.path.exists(_p("meta.json"))

def paths():
    """(setup workbook or None, timetable file) of the draft"""
    tp = next(os.path.join(DIR, f) for f in sorted(os.listdir(DIR)) if f.startswith("timetable."))
    return (_p("setup.xlsx") if os.path.exists(_p("setup.xlsx")) else None), tp

def model(spec): return model_from_files(*paths(), spec=spec)

def save(setup_path, timetable_path, source, spec, replace=False):
    """replace the draft with these files, read against the setup spec first (so a file that cannot be read never replaces a
    good draft); returns the model, for info(model=). UnpublishedFixes unless replace, when the draft has fixes that were never published. The 'left' decisions carry over (info drops the ones whose warning is gone)."""
    with _lock:
        meta = store.read_json(_p("meta.json"), {}) or {} if exists() else {}; fl = meta.get("fixes") or []
        if len(fl) > meta.get("published_fixes", 0) and not replace: raise UnpublishedFixes(len(fl))
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
        os.replace(new, DIR); shutil.rmtree(old, ignore_errors=True); _cache.clear()
        return m

def summary():
    """what /api/status shows of the draft, from meta.json alone (no model is built)"""
    meta = store.read_json(_p("meta.json")) if exists() else None
    return dict(uploaded_at=meta.get("uploaded_at"), source=meta.get("source"), open=meta.get("open")) if meta else None

def model_now(rec=None):
    """(model, setup record, fx) of the draft with its fixes applied, checked against the setup record (default: as it is now).
    fx = dict(texts, problems, touched, was) from fixes.apply. One model is kept, for the same upload, setup version and fixes; it is
    shared between requests, so nothing may change it."""
    rec = rec or store.setup_record(); spec = rec["spec"]
    if not spec: raise LookupError("no setup")
    with _lock:
        meta = store.read_json(_p("meta.json"), {}); fl = meta.get("fixes") or []
        key = (meta.get("uploaded_at"), rec["v"], json.dumps(fl, sort_keys=True))
        if _cache.get("key") == key: return _cache["m"], rec, _cache["fx"]
        args = paths()
    fx = {}; m = model_from_files(None, args[1], spec=spec, edit=fixes.editor(fl, fx))   # no re-read of the setup workbook: the spec is given
    if meta.get("config_id"): m["setup"].setdefault("school", {})["config_id"] = meta["config_id"]
    with _lock: _cache.clear(); _cache.update(key=key, m=m, fx=fx)
    return m, rec, fx

def _build(m=None, rec=None):
    """the draft with its fixes applied, checked against the setup as it is now (or rec, a setup record): the fields of info()
    before decisions are laid over them. m: a model already built (by save, with no fixes yet)."""
    if m is None: m, rec, fx = model_now(rec)
    else:
        rec = rec or store.setup_record(); fx = dict(texts=[], problems=[], touched=set(), was=[])
        if not rec["spec"]: raise LookupError("no setup")
    spec = rec["spec"]
    with _lock: meta = store.read_json(_p("meta.json"), {})
    ws = verify.warnings(m, touched=fx["touched"], was=fx.get("was") or ()); ch = m["checks"]
    cid, ver = meta.get("config_id") or "", rec["v"]; got = re.fullmatch(r"v(\d+)", cid)
    state = ("unknown" if not cid else "unsaved" if cid.endswith("+") else "unknown" if not got else
             "same" if int(got[1]) == ver else "older" if int(got[1]) < ver else "newer")
    ours, theirs = str((spec.get("school") or {}).get("name") or "").strip(), meta.get("school") or ""
    return dict(source=meta.get("source"), uploaded_at=meta.get("uploaded_at"), config_id=cid, setup_version=f"v{ver}", config_state=state,
                school=m["school"]["name"], file_school=theirs, timetable=m["school"]["timetable"], lessons=ch["lessons"], classes=len(m["classes"]), teachers=len(m["teachers"]),
                students=len(m["students"]), after=ch["after_school"][:30], notes=m["notes"][:12], rule_report=m.get("rule_report") or [],
                choices_used=m.get("choices_used") or [], choices=len(spec.get("choices") or []) - len({i for i, _ in choices.problems(spec)}),
                typed=len(typed_rules(spec)), warnings=ws["warnings"], not_checked=ws["not_checked"], fixes=[dict(text=f.get("text"), at=f.get("at"), kind=f.get("kind")) for f in meta.get("fixes") or []], fix_problems=fx["problems"],
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
        n = sum(1 for w in ws if not w["decision"] or w["decision"]["answer"] == "left")   # "met" and "step5" settle a warning
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
    if answer == "met" and not key.endswith(":again"): raise ValueError("That answer is only for a rule to check again.")
    if not exists(): raise ValueError("There is no draft.")
    if answer != "step5":
        j = _build(); w = next((w for w in j["warnings"] if w["key"] == key), None)
        if answer == "open": return _finish(j, (key, None))
        if not w: raise ValueError("That warning is no longer on the list.")
        return _finish(j, (key, dict(answer=answer, at=store.now())))
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
    """make the draft the published timetable, with its fixes applied, checked against the setup as it is now"""
    with _lock:
        rec = store.setup_record(); j = info(rec=rec)   # one read of the setup: the one checked against is the one published with
        if j is None: raise FileNotFoundError("no draft")
        meta = store.read_json(_p("meta.json"), {}); decisions = store.read_json(_p("decisions.json"), {}) or {}
        left = [w["text"] for w in j["warnings"] if (w["decision"] or {}).get("answer") == "left"]
        fl = meta.get("fixes") or []; texts = model_now(rec)[2]["texts"]
        sp, tp = paths()
        store.publish(sp, tp, source=meta.get("source"), spec=rec["spec"], log=lambda *x: None, edit=fixes.editor(fl, {}),
                      extra=dict(compared_v=j["setup_version"], open=j["open"], left=left, decisions={k: d["answer"] for k, d in decisions.items()}, fixes=list(texts)))
        store.write_json(_p("meta.json"), dict(store.read_json(_p("meta.json"), {}), published_fixes=len(fl)))
        return dict(j, published=True)

# ------------------------------------------------------------------------------------------------ the grid and the fixes

NOT_FOUND = "There is no class or teacher of that name on the timetable."
FIELDS = dict(move=("id", "d", "p"), swap=("a", "b"), teacher=("key", "teachers"), room=("id", "group", "room"), add=("key", "d", "p", "n"), delete=("id",))

def _now():
    if not exists(): raise NoDraft("There is no draft.")
    return model_now()

def grid(view, name):
    """one class's or teacher's week with its lessons, for the grid -> dict(view, name, days, NP, times, codes, lessons, classes, teachers, short)"""
    m, rec, fx = _now(); cls = view == "class"
    if view not in ("class", "teacher") or name not in (m["class_ix"] if cls else m["teacher_ix"]): raise ValueError(NOT_FOUND)
    if cls: codes = m["cgrid"].get(name) or m["grid"].get(m["class_ix"][name]["level"]) or ["." * m["NP"]] * len(m["days"])
    else: codes = ["".join("L" if any(g[d][p] in "LA" for g in m["grid"].values()) else "." for p in range(m["NP"])) for d in range(len(m["days"]))]
    rows = [x for x in m["lessons"] if name in x["classes" if cls else "teachers"]]
    keep = lambda e: name in e["classes"]
    return dict(view=view, name=name, days=list(m["days"]), NP=m["NP"], times=m["times"], codes=list(codes),
                lessons=[dict(id=x["id"], group=x["group"], subject=x["subject"], classes=list(x["classes"]), teachers=list(x["teachers"]), room=x["room"], d=x["d"], p=x["p"], n=x["n"],
                              block=x["block"], what=fixes.what(x),
                              short=(m["subjects"].get(x["subject"]) or {}).get("short") or x["subject"], tshorts=[(m["teacher_ix"].get(t) or {}).get("short") or t for t in x["teachers"]]) for x in rows],
                classes=[c["name"] for c in m["classes"]], teachers=[t["name"] for t in m["teachers"]],
                short=[s for s in fixes.short(m, m["checked_setup"]) if cls and keep(verify.planned_rows(m["checked_setup"])[tuple(s["key"].split(":", 2 if s["key"].startswith("C:") else 1))])])

def options(lesson_id=None, group=None, add=None, n=None):
    """what the committee can do with one lesson (every slot, teacher, room, the delete, judged), or where a lesson of step 5 can be added"""
    m, rec, fx = _now(); spec, days = m["checked_setup"], m["days"]
    if add is not None:
        try: n = int(n)
        except (TypeError, ValueError): raise ValueError("Say how many periods the lesson is.")
        return dict(slots=fixes.add_slots(m, spec, days, add, n))
    try: lid = int(lesson_id)
    except (TypeError, ValueError): raise ValueError("There is no lesson with that id on the timetable.")
    rows = fixes._rows(m["lessons"], lid); row = rows[0] if group is None else next((x for x in rows if x["group"] == group), None)
    if row is None: raise ValueError(f"There is no row of {group} in that lesson.")
    key = verify._kstr(fixes._row_key(row)); g = row["group"]
    return dict(key=key, slots=fixes.slots(m, spec, days, lid), teachers=fixes.teacher_options(m, spec, days, key), rooms=fixes.room_options(m, spec, days, lid, g),
                delete=fixes.can_delete(m, spec, days, lid, group))

def _whole(f):
    """a fix as the page posted it, cut to its kind's fields (the server adds at and text), or ValueError(sentence)"""
    if not isinstance(f, dict) or f.get("kind") not in FIELDS: raise ValueError("This kind of fix is not known.")
    k = f["kind"]; out = dict(kind=k, **{x: f[x] for x in FIELDS[k] if x in f})
    if len(out) != len(FIELDS[k]) + 1: raise ValueError("The fix is not complete.")
    if k == "add": out["room"] = f.get("room")
    if k == "delete" and f.get("group") is not None: out["group"] = f["group"]
    if k == "teacher" and not (isinstance(out["teachers"], list) and all(isinstance(t, str) for t in out["teachers"])): raise ValueError("The fix is not complete.")
    return out

def fix(move):
    """make one fix: judged against the draft as it is now, and kept only when the timetable allows it. Returns info()."""
    f = _whole(move)
    with _lock:   # from the judgement to the write: two clicks cannot both pass the judgement on the same state
        m, rec, fx = _now(); spec, days = m["checked_setup"], m["days"]
        if f["kind"] == "add" and not f["room"]: f["room"] = fixes.add_room(m, spec, f["key"], f["d"], f["p"], f["n"]) if isinstance(f["n"], int) and isinstance(f["d"], int) and isinstance(f["p"], int) else ""
        j = fixes.judge(m, spec, days, f)
        if j["state"] in ("no", "na"): raise ValueError(j["why"])
        text = fixes.apply_one(copy.deepcopy(m["lessons"]), f, spec, days)   # the sentence of the fix as it is made
        meta = store.read_json(_p("meta.json"), {})
        store.write_json(_p("meta.json"), dict(meta, fixes=(meta.get("fixes") or []) + [dict(f, at=store.now(), text=text)]))
        return info()

def undo():
    """drop the last fix. Returns info()."""
    with _lock:
        if not exists(): raise NoDraft("There is no draft.")
        meta = store.read_json(_p("meta.json"), {}); fl = list(meta.get("fixes") or [])
        if not fl: raise ValueError("There is nothing to undo.")
        fl.pop(); store.write_json(_p("meta.json"), dict(meta, fixes=fl, published_fixes=min(meta.get("published_fixes", 0), len(fl))))
        return info()

def database(path):
    """the draft with its fixes as a timetable database at path"""
    write_db(_now()[0], path)

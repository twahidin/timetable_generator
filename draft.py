"""The draft: the timetable the committee uploaded, kept on the server beside the saved setup. It is checked against the
setup as it is now (ttgen.verify), each difference is decided on (change step 5, or still open), and the
draft is published when the committee is ready. Files and decisions live in DATA_DIR/draft."""
import copy, json, os, re, secrets, shutil, threading, uuid
from ttgen.export import ENTIRE, PALETTE, model_from_files
from ttgen.database import write_db
from ttgen.spec import typed_rules
from ttgen import choices, verify
import store, sync, fixes, helper, typed

DIR = os.path.join(store.DATA, "draft")
ANSWERS = ("step5", "open", "met")
_lock = threading.RLock()   # always taken before store's locks, never inside them
class NoDraft(Exception): pass
class Critical(Exception):
    """the draft has critical mistakes, so it cannot be published; count: how many"""
    def __init__(self, count): super().__init__(critical_text(count)); self.count = count
def critical_text(n):
    """the sentence that says why Publish is refused"""
    return ("1 critical mistake" if n == 1 else f"{n} critical mistakes") + " must be settled on step 8 before the timetable can be published."
class UnpublishedFixes(Exception):
    """the draft has fixes that were never published; count: how many; waiting: how many lessons are in Not placed"""
    def __init__(self, count, waiting=0):
        super().__init__("The draft has changes that were never published." + (f" {waiting} lesson is waiting in Not placed." if waiting == 1 else f" {waiting} lessons are waiting in Not placed." if waiting else ""))
        self.count = count
def not_placed_text(n):
    """the sentence that says why the printouts and the download are refused"""
    return "1 lesson is not placed. Place it or delete it on step 8 first." if n == 1 else f"{n} lessons are not placed. Place them or delete them on step 8 first."
class NotPlaced(Exception):
    """lessons wait in Not placed, so nothing can be printed or downloaded; count: how many lessons"""
    def __init__(self, count): super().__init__(not_placed_text(count)); self.count = count
def _count(pool): return len({x["id"] for x in pool})
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
    good draft); returns the model, for info(model=). UnpublishedFixes unless replace, when the draft has fixes that were never published. A new upload starts with no decisions."""
    with _lock:
        meta = store.read_json(_p("meta.json"), {}) or {} if exists() else {}; fl = meta.get("fixes") or []
        if len(fl) > meta.get("published_fixes", 0) and not replace: raise UnpublishedFixes(len(fl), _waiting())
        new, old = DIR + ".new", DIR + ".old"
        shutil.rmtree(new, ignore_errors=True); os.makedirs(new)
        if setup_path: shutil.copy(setup_path, os.path.join(new, "setup.xlsx"))
        shutil.copy(timetable_path, os.path.join(new, "timetable" + os.path.splitext(timetable_path)[1]))
        try: m = model_from_files(os.path.join(new, "setup.xlsx") if setup_path else None, [os.path.join(new, f) for f in os.listdir(new) if f.startswith("timetable.")][0], spec=spec)
        except Exception as e:
            shutil.rmtree(new, ignore_errors=True); raise ValueError(f"Could not read the files: {e}")
        if not m["lessons"]: shutil.rmtree(new, ignore_errors=True); raise ValueError("The timetable has no lessons.")
        store.write_json(os.path.join(new, "decisions.json"), {})
        store.write_json(os.path.join(new, "meta.json"), dict(source=source, uploaded_at=store.now(), upload_id=uuid.uuid4().hex, fixes=[], school=m["file_school"],
                                                              config_id=str(((m["setup"].get("school") or {}).get("config_id")) or "").strip()))
        shutil.rmtree(old, ignore_errors=True)
        if os.path.exists(DIR): os.replace(DIR, old)
        os.replace(new, DIR); shutil.rmtree(old, ignore_errors=True); _cache.clear()
        return m

def _waiting():
    """how many lessons wait in Not placed in the draft now; 0 when it cannot be worked out (the sentence is then the shorter one)"""
    try: return _count(model_now()[2]["pool"])
    except Exception: return 0

def summary():
    """what /api/status shows of the draft, from meta.json alone (no model is built)"""
    meta = store.read_json(_p("meta.json")) if exists() else None
    return dict(uploaded_at=meta.get("uploaded_at"), upload_id=meta.get("upload_id"), source=meta.get("source"), open=meta.get("open"), critical=meta.get("critical"), fixes=len(meta.get("fixes") or [])) if meta else None

def model_now(rec=None):
    """(model, setup record, fx) of the draft with its fixes applied, checked against the setup record (default: as it is now).
    fx = dict(texts, problems, touched, was, pool) from fixes.apply; pool is the rows of the lessons not placed, which the model also carries
    as m["pool"] for the helper and the typed request (they judge with it). One model is kept, for the same upload, setup version and fixes; it is
    shared between requests, so nothing may change it."""
    rec = rec or store.setup_record(); spec = rec["spec"]
    if not spec: raise LookupError("no setup")
    with _lock:
        meta = store.read_json(_p("meta.json"), {}); fl = meta.get("fixes") or []
        key = (meta.get("uploaded_at"), meta.get("upload_id"), rec["v"], json.dumps(fl, sort_keys=True))
        if _cache.get("key") == key: return _cache["m"], rec, _cache["fx"]
        args = paths()
    fx = {}; m = model_from_files(None, args[1], spec=spec, edit=fixes.editor(fl, fx))   # no re-read of the setup workbook: the spec is given
    if meta.get("config_id"): m["setup"].setdefault("school", {})["config_id"] = meta["config_id"]
    fx.setdefault("pool", []); m["pool"] = fx["pool"]
    with _lock: _cache.clear(); _cache.update(key=key, m=m, fx=fx)
    return m, rec, fx

def _unique(ws):
    """the warnings with a key repeated made unique as verify.warnings does (#2, #3)"""
    seen = {}
    for w in ws:
        seen[w["key"]] = n = seen.get(w["key"], 0) + 1
        if n > 1: w["key"] += f"#{n}"
    return ws

def _own_warnings(m, pool):
    """the warnings the draft makes itself: one critical "Not placed" for each lesson in the pool, and one "No room" (a warning, not critical)
    for each lesson row on the timetable with no room"""
    out, first = [], lambda x: (x["classes"] or [""])[0]
    by = {}
    for x in pool: by.setdefault(x["id"], []).append(x)
    for i, rows in by.items():
        c = first(rows[0]); out.append(verify.warning(f"clash:notplaced:{i}", "clash", f"Not placed: {fixes.what(rows[0])}.", group=c or "School", where=dict(cls=c, id=i), crit="notplaced"))
    for x in m["lessons"]:
        if fixes._no_room(x["room"]):
            c = first(x); out.append(verify.warning(f"room:none:{x['id']}:{x['group']}", "room", f"No room: {fixes.what(x)} on {m['days'][x['d']]} period {x['p']}.", strength="Prefer",
                                                    group=c or "School", where=dict(cls=c, day=m["days"][x["d"]], period=x["p"], id=x["id"], row=x["group"])))
    busy, by, pairs = fixes.Busy(m), {}, {}   # two bands on one class at once, one of them taking every student of the class: one line for the two bands and the day
    for x in m["lessons"]: by.setdefault(x["id"], []).append(x)
    for i, rows in by.items():
        a = rows[0]; hit = busy.band_clash(rows, a["d"], a["p"], a["n"], ignore=(i,))
        if not hit: continue
        mine = next(x for x in rows if x["block"] and hit[0] in x["classes"]); y = hit[1]; k = (tuple(sorted((mine["block"], y["block"]))), a["d"])
        e = pairs.setdefault(k, dict(p=max(a["p"], y["p"]), classes=set(), id=i, row=mine["group"], level={mine["block"]: mine["level"], y["block"]: y["level"]}))
        e["classes"] |= set(mine["classes"]) & set(y["classes"])
    for (names, d), e in sorted(pairs.items(), key=lambda kv: (kv[0][1], kv[1]["p"], kv[0][0])):
        cs = sorted(e["classes"]); a, b = (fixes.block_label(n, e["level"][n]) for n in names)
        out.append(verify.warning(f"clash:bands:{d}:{names[0]}:{names[1]}", "clash", f"Two bands at the same time: {a} and {b} on {m['days'][d]} period {e['p']}. Every student of {', '.join(cs)} is in both, so one of the two has to move.",
                                  group=cs[0] if cs else "School", where=dict(cls=cs[0] if cs else "", day=m["days"][d], period=e["p"], id=e["id"], row=e["row"]), crit="class"))
    # two bands that every student takes, sharing a period for a class with only some groups of each meeting: perhaps different students, so a warning to check and not a mistake
    occ, beside = {}, {}
    for x in m["lessons"]:
        if x["block"] in busy.every and x["group"] != ENTIRE:
            for c in x["classes"]:
                for q in range(x["p"], x["p"] + x["n"]): occ.setdefault((c, x["d"], q), {}).setdefault(x["block"], {})[x["group"]] = x
    for (c, d, q), bands in sorted(occ.items(), key=lambda kv: (kv[0][1], kv[0][2], kv[0][0])):
        names = sorted(bands)
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                if ((a, b), d) in pairs: continue
                x = next(iter(bands[a].values())); e = beside.setdefault(((a, b), d), dict(p=q, classes=set(), id=x["id"], row=x["group"], level={a: x["level"], b: next(iter(bands[b].values()))["level"]}, n={a: (0, 0), b: (0, 0)}))
                e["classes"].add(c)
                for k in (a, b): e["n"][k] = max(e["n"][k], (len(bands[k]), len(busy.bgroups[k, c])))
    for (names, d), e in beside.items():
        cs = sorted(e["classes"]); part = lambda k: f"{fixes.block_label(k, e['level'][k])} ({e['n'][k][0]} of its {e['n'][k][1]} groups)"
        out.append(verify.warning(f"bands:beside:{d}:{names[0]}:{names[1]}", "clash", f"Two bands share a period: {part(names[0])} and {part(names[1])} on {m['days'][d]} period {e['p']}, for {', '.join(cs)}. A student in a group of both would have two lessons then: check that the groups' students are different.",
                                  strength="Prefer", group=cs[0], where=dict(cls=cs[0], day=m["days"][d], period=e["p"], id=e["id"], row=e["row"])))
    return _unique(out)

WAITING = " A lesson of it is waiting in Not placed."
WAITING_REFUSED = "A lesson of it is waiting in Not placed. Place it or delete it first."
def _withhold(ws, pool):
    """a difference from step 5 about a lesson a pooled lesson belongs to is not offered as "update step 5": the timetable will change when it is placed"""
    keys = {verify._kstr(k) for x in pool for k in helper._keys_of(x)}   # every key verify.placed would give its rows: one per class of a whole-class row, the group's
    for w in ws:
        k = re.fullmatch(r"dep:(.+):(?:missing|periods)(?:#\d+)?", w["key"])
        if k and k[1] in keys: w["ops"] = None; w["text"] += WAITING

def _no_teacher(ws):
    """a difference from step 5 about a lesson with no teacher on the timetable says so, not "is taught by  on" with an empty name"""
    for w in ws:
        if re.fullmatch(r"dep:.+:teachers(?:#\d+)?", w["key"]) and (w.get("sides") or {}).get("timetable") == "":
            w["text"] = w["text"].replace(" is taught by  on the timetable;", " has no teacher on the timetable;", 1)

def _build(m=None, rec=None, fx=None):
    """the draft with its fixes applied, checked against the setup as it is now (or rec, a setup record): the fields of info()
    before decisions are laid over them. m: a model already built (by save, with no fixes yet, or with its rec and fx from model_now)."""
    if m is None: m, rec, fx = model_now(rec)
    else:
        rec = rec or store.setup_record(); fx = fx or dict(texts=[], problems=[], touched=set(), was=[], pool=[])
        if not rec["spec"]: raise LookupError("no setup")
    spec = rec["spec"]
    with _lock: meta = store.read_json(_p("meta.json"), {})
    ws = verify.warnings(m, touched=fx["touched"], was=fx.get("was") or ()); ch = m["checks"]; pool = fx.get("pool") or []
    ws["warnings"] = ws["warnings"] + _own_warnings(m, pool); _withhold(ws["warnings"], pool); _no_teacher(ws["warnings"])
    cid, ver = meta.get("config_id") or "", rec["v"]; got = re.fullmatch(r"v(\d+)", cid)
    state = ("unknown" if not cid else "unsaved" if cid.endswith("+") else "unknown" if not got else
             "same" if int(got[1]) == ver else "older" if int(got[1]) < ver else "newer")
    ours, theirs = str((spec.get("school") or {}).get("name") or "").strip(), meta.get("school") or ""
    return dict(source=meta.get("source"), uploaded_at=meta.get("uploaded_at"), upload_id=meta.get("upload_id"), config_id=cid, setup_version=f"v{ver}", config_state=state,
                school=m["school"]["name"], file_school=theirs, timetable=m["school"]["timetable"], lessons=ch["lessons"], classes=len(m["classes"]), teachers=len(m["teachers"]),
                students=len(m["students"]), after=ch["after_school"][:30], notes=m["notes"][:12], rule_report=m.get("rule_report") or [],
                choices_used=m.get("choices_used") or [], choices=len(spec.get("choices") or []) - len({i for i, _ in choices.problems(spec)}),
                typed=len(typed_rules(spec)), warnings=ws["warnings"], not_checked=ws["not_checked"], fixes=[dict(text=f.get("text"), at=f.get("at"), kind=f.get("kind"), batch=f.get("batch")) for f in meta.get("fixes") or []], fix_problems=fx["problems"], unplaced=_count(pool),
                other_school=ours if ours and theirs and ours.lower() != theirs.lower() else "")

def _finish(j, change=None):
    """lay the decisions over the warnings and count them. Under the lock the decisions are read again from disk (a decision
    made while the model was being built stays), change = (key, decision or None) is applied, and a decision whose warning is
    gone is dropped, except the step5 ones: they record that step 5 was updated from the timetable. A decision that says "left"
    (from a draft kept before that answer went) is dropped too: its warning is open again."""
    keys = {w["key"] for w in j["warnings"]}
    with _lock:
        decisions = store.read_json(_p("decisions.json"), {}) or {} if exists() else {}
        if change:
            if change[1] is None: decisions.pop(change[0], None)
            else: decisions[change[0]] = change[1]
        decisions = {k: d for k, d in decisions.items() if d.get("answer") != "left" and (k in keys or d.get("answer") == "step5")}
        ws = [dict(w, decision=decisions.get(w["key"])) for w in j["warnings"]]
        n = sum(1 for w in ws if not w["decision"])   # "met" and "step5" settle a warning
        crit = sum(1 for w in ws if w.get("crit"))
        if exists():
            store.write_json(_p("decisions.json"), decisions)
            store.write_json(_p("meta.json"), dict(store.read_json(_p("meta.json"), {}), open=n, critical=crit))
    return dict(j, warnings=ws, open=n, critical=crit,
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
        if w["ops"] is None:
            if w["kind"] != "deployment": raise ValueError("This warning cannot be settled by updating step 5.")
            raise ValueError(WAITING_REFUSED if w["text"].endswith(WAITING) else "This difference is set on step 3 for the whole level; the app does not change it from here.")
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
        if j["critical"]: raise Critical(j["critical"])   # judged and written under this one lock: none can arrive in between
        left = [w["text"] for w in j["warnings"] if not w["decision"]]   # the warnings open at publishing
        fl = meta.get("fixes") or []; fx = model_now(rec)[2]; texts = fx["texts"]
        if fx["pool"]: raise NotPlaced(_count(fx["pool"]))   # a second guard: the critical count refuses first, but a lesson waiting is never published without
        sp, tp = paths()
        store.publish(sp, tp, source=meta.get("source"), spec=rec["spec"], log=lambda *x: None, edit=fixes.editor(fl, {}),
                      extra=dict(compared_v=j["setup_version"], open=j["open"], left=left, decisions={k: d["answer"] for k, d in decisions.items()}, fixes=list(texts)))
        store.write_json(_p("meta.json"), dict(store.read_json(_p("meta.json"), {}), published_fixes=len(fl)))
        return dict(j, published=True)

def printouts(out_dir, individual):
    """the printouts of the draft with its fixes applied, checked against the setup as it is now, written under out_dir by
    ttgen.export.export_all -> (model, base name of the folder made in out_dir). The model is built for this call, as publish builds
    its own: export_all may change what it is given, so the shared cached one is never used. NotPlaced while a lesson waits in Not placed."""
    from ttgen.export import export_all, safe_name
    if not exists(): raise NoDraft("There is no draft.")
    rec = store.setup_record()
    if not rec["spec"]: raise LookupError("no setup")
    with _lock:
        meta = store.read_json(_p("meta.json"), {}); fl = meta.get("fixes") or []; sp, tp = paths()
    fx = {}; m = model_from_files(sp, tp, spec=rec["spec"], edit=fixes.editor(fl, fx)); m["fixes"] = fx.get("texts") or []
    if fx.get("pool"): raise NotPlaced(_count(fx["pool"]))
    base = safe_name(f"{m['school']['name']} {m['school']['timetable']}")
    export_all(m, os.path.join(out_dir, base), individual=individual, zip_individual=False, log=lambda *x: None)
    return m, base

def preview_page():
    """the draft as the published timetable page would show it, as HTML: ttgen.export.render_html on the draft's model as it is now (a lesson
    waiting in Not placed is not on it), for the committee, with no link to the published files and a banner that says it is a preview and
    what still stands in the way of publishing. Nothing is published or stored. NoDraft without a draft."""
    from ttgen.export import render_html
    if not exists(): raise NoDraft("There is no draft.")
    m, rec, fx = model_now(); j = info(m, rec) or {}; waiting, crit = _count(fx["pool"]), j.get("critical") or 0
    banner = "Preview: this is the draft as it stands, not the published timetable."
    if waiting: banner += " 1 lesson waiting in Not placed is not on it." if waiting == 1 else f" {waiting} lessons waiting in Not placed are not on it."
    if crit: banner += " " + critical_text(crit)
    app = dict(mode="committee", tabs=None, pdf=False, files=[], home="/", homeLabel="Back to the committee page", banner=banner)
    return render_html(m, "full", app=app, title=f"Preview · {m['school']['name']} · {m['school']['timetable']}")

# ------------------------------------------------------------------------------------------------ the grid and the fixes

NOT_FOUND = "There is no class or teacher of that name on the timetable."
FIELDS = dict(move=("id", "d", "p"), swap=("a", "b"), teacher=("key", "teachers"), room=("id", "group", "room"), add=("key", "d", "p", "n"), delete=("id",), lift=("id",), place=("id", "d", "p"))
FORCED = ("move", "place", "add", "delete", "teacher", "room")   # the kinds a request from the board may force
PUSHED = ("move", "place", "add")             # the kinds a request from the board may push other lessons out for

def _now():
    if not exists(): raise NoDraft("There is no draft.")
    return model_now()

def _planned(spec, key):
    """the step 5 row (verify.planned_rows) of a key as the page and fixes.short spell it"""
    return verify.planned_rows(spec)[tuple(key.split(":", 2 if key.startswith("C:") else 1))]

def _payload(m, view, name, short=True, pool=()):
    """one class's or teacher's week with its lessons, from a model (or a dict(m, lessons=...)) -> dict(view, name, days, NP, times, codes, lessons, classes, teachers, short); short=False leaves short empty"""
    cls = view == "class"
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
                short=[s for s in fixes.short(m, m["checked_setup"], pool) if cls and keep(_planned(m["checked_setup"], s["key"]))] if short else [])

def grid(view, name):
    """one class's or teacher's week with its lessons, for the grid"""
    m, rec, fx = _now(); return _payload(m, view, name, pool=fx["pool"])

def options(lesson_id=None, group=None, add=None, n=None):
    """what the committee can do with one lesson (every slot, teacher, room, the delete, judged), or where a lesson of step 5 can be added"""
    m, rec, fx = _now(); spec, days = m["checked_setup"], m["days"]   # a lesson in the pool is the board's alone: draft.options never lists it
    if add is not None:
        try: n = int(n)
        except (TypeError, ValueError): n = None
        return dict(slots=fixes.add_slots(m, spec, days, add, _length(n, m), fx["pool"]))
    try: lid = int(lesson_id)
    except (TypeError, ValueError): raise ValueError("There is no lesson with that id on the timetable.")
    rows = fixes._rows(m["lessons"], lid); row = rows[0] if group is None else next((x for x in rows if x["group"] == group), None)
    if row is None: raise ValueError(f"There is no row of {group} in that lesson.")
    key = verify._kstr(fixes._row_key(row)); g = row["group"]
    return dict(key=key, slots=fixes.slots(m, spec, days, lid, fx["pool"], extras=False), teachers=fixes.teacher_options(m, spec, days, key, fx["pool"]), rooms=fixes.room_options(m, spec, days, lid, g, fx["pool"]),
                delete=fixes.can_delete(m, spec, days, lid, group, fx["pool"]))

NOT_IN_SETUP = "Not in the setup"
NOT_FOUND_LESSON = "There is no lesson with that id on the timetable."

def _teacher_groups(m, pool, tshort):
    """the setup's teachers by home department, in the setup's order (those with none last, dept ""), then a teacher only a lesson names, under NOT_IN_SETUP
    -> [dict(dept, teachers=[dict(name, short)])]"""
    team = list({t["name"]: t for t in m["checked_setup"].get("teachers") or [] if isinstance(t, dict) and t.get("name")}.values())
    dept = lambda t: str(t.get("dept") or "").strip()   # the home one only, even for a teacher with a second
    groups = {d: [dict(name=t["name"], short=(m["teacher_ix"].get(t["name"]) or {}).get("short") or t["name"]) for t in team if dept(t) == d] for d in dict.fromkeys(map(dept, team))}
    out = [dict(dept=d, teachers=v) for d, v in groups.items() if d] + ([dict(dept="", teachers=groups[""])] if groups.get("") else [])
    named = {t["name"] for t in team}
    extra = [dict(name=t, short=tshort.get(t) or t) for t in dict.fromkeys(t for x in m["lessons"] + pool for t in x["teachers"]) if t not in named]
    return out + ([dict(dept=NOT_IN_SETUP, teachers=extra)] if extra else [])

def _room_groups(m, pool):
    """the setup's venues by kind, in the setup's order (no kind is "classroom"), then a room only a lesson names, under NOT_IN_SETUP -> [dict(kind, rooms=[name])]"""
    venues = list({str(v["room"]): v for v in m["checked_setup"].get("venues") or [] if isinstance(v, dict) and v.get("room")}.values()); groups = {}
    for v in venues: groups.setdefault(v.get("kind") or "classroom", []).append(str(v["room"]))
    named = {str(v["room"]) for v in venues}
    extra = [r for r in dict.fromkeys(x["room"] for x in m["lessons"] + pool) if not fixes._no_room(r) and r not in named]
    return [dict(kind=k, rooms=v) for k, v in groups.items()] + ([dict(kind=NOT_IN_SETUP, rooms=extra)] if extra else [])

def lesson(lesson_id, group=None):
    """who and which room could take one lesson row (on the timetable or in the pool), judged against the draft as it is now: fixes.choices"""
    m, rec, fx = _now()
    try: lid = int(lesson_id)
    except (TypeError, ValueError): raise ValueError(NOT_FOUND_LESSON)
    return fixes.choices(m, m["checked_setup"], m["days"], lid, group, fx["pool"])

def board():
    """the whole draft as cards for the board -> dict(days, NP, times, levels, codes, subjects, palette, cards, unplaced, short); one card per lesson id, with every row
    and class of it. Every card has marks (fixes.marks) and why (the reason Busy.clash gives for it at its own place, or ""); unplaced is the cards of the lessons
    in the pool (d and p None, was the place they left, marks ["notplaced"]), by first class then id; short is fixes.short for the whole school, each with the
    classes of its step 5 row"""
    m, rec, fx = _now(); pool = fx["pool"]; NP, nd = m["NP"], len(m["days"]); in_setup = {str(c["class"]) for c in m["checked_setup"]["classes"]}
    level_of = {c["name"]: c["level"] for c in m["classes"] if c["name"] in in_setup}   # the model also lists a class only a lesson names
    by_id, waiting = {}, {}
    for x in m["lessons"]: by_id.setdefault(x["id"], []).append(x)
    for x in pool: waiting.setdefault(x["id"], []).append(x)
    levels = [dict(level=lv, classes=[c for c, l in level_of.items() if l == lv]) for lv in m["levels"]]
    placed = {c for lv in levels for c in lv["classes"]}
    extra = [c["name"] for c in m["classes"] if c["name"] not in placed]   # not in the setup, or on a level the model does not have
    extra += [c for c in dict.fromkeys(c for x in pool for c in x["classes"]) if c not in placed and c not in extra]   # a class only a lesson not placed names
    if extra: levels.append(dict(level=NOT_IN_SETUP, classes=extra))
    codes = {}
    for lv in levels:
        for c in lv["classes"]: codes[c] = list(m["cgrid"].get(c) or m["grid"].get(level_of.get(c)) or ["." * NP] * nd)
    short = lambda s: (m["subjects"].get(s) or {}).get("short") or s
    tshort = {t: (m["teacher_ix"].get(t) or {}).get("short") or t for x in m["lessons"] + pool for t in x["teachers"]}
    busy = fixes.Busy(m)

    def card(i, rows):
        a = rows[0]; band = fixes.band(rows, short)
        return dict(id=i, d=a["d"], p=a["p"], n=a["n"], classes=list(dict.fromkeys(c for x in rows for c in x["classes"])), band=band, what=fixes.what(a),
                    rows=[dict(group=x["group"], subject=x["subject"], teachers=list(x["teachers"]), tshorts=[tshort[t] for t in x["teachers"]], room=x["room"], key=verify._kstr(fixes._row_key(x))) for x in rows])
    cards = []
    for i in sorted(by_id):
        rows = by_id[i]; a = rows[0]
        mk = fixes.marks(busy, rows)
        cards.append(dict(card(i, rows), marks=mk, why=busy.clash(rows, a["d"], a["p"], a["n"], ignore=(i,)) or "", **({"out": True} if "break" in mk and busy.outside(rows, a["d"], a["p"], a["n"]) else {})))
    unplaced = [dict(card(i, rows), d=None, p=None, was=dict(d=rows[0]["d"], p=rows[0]["p"]), marks=fixes.marks(busy, rows, pool=True), why="") for i, rows in waiting.items()]
    unplaced.sort(key=lambda x: ((x["classes"] or [""])[0], x["id"]))
    return dict(days=list(m["days"]), NP=NP, times=m["times"], levels=levels, codes=codes,
                subjects={k: [v.get("short") or k, v.get("color"), v.get("dept") or ""] for k, v in m["subjects"].items()},
                palette=[list(c) for c in PALETTE], cards=cards, unplaced=unplaced, teachers=_teacher_groups(m, pool, tshort), rooms=_room_groups(m, pool),
                day=["".join("L" if any(g[d][p] in "LA" for g in m["grid"].values()) else "." for p in range(NP)) for d in range(nd)],
                short=[dict(s, classes=list(_planned(m["checked_setup"], s["key"])["classes"])) for s in fixes.short(m, m["checked_setup"], pool)])

def slots(lesson_id):
    """where one lesson may go (on the timetable or waiting in Not placed): fixes.slots on the draft as it is now, saying who is at each place but
    not judging a push or a place beside (see place) -> dict(id, slots, delete); delete is the judgement of deleting the whole lesson, dict(state, why)"""
    m, rec, fx = _now()
    try: lid = int(lesson_id)
    except (TypeError, ValueError): raise ValueError("There is no lesson with that id on the timetable.")
    spec, days, c = m["checked_setup"], m["days"], fixes._ctx(m)   # one index for the slots and the delete
    return dict(id=lid, slots=fixes.slots(m, spec, days, lid, fx["pool"], extras="who", ctx=c), delete=fixes.can_delete(m, spec, days, lid, pool=fx["pool"], ctx=c))

def place(lesson_id, d, p):
    """one place the lesson may be dropped on, judged with a push out and a place beside where other lessons of its classes are: fixes.place -> dict(d, p, state, why, swap, also, push, beside)"""
    m, rec, fx = _now()
    try: lid = int(lesson_id)
    except (TypeError, ValueError): raise ValueError(NOT_FOUND_LESSON)
    return fixes.place(m, m["checked_setup"], m["days"], lid, d, p, fx["pool"])

def _length(n, m):
    """an add's n, a whole number from 1 to the periods in a day, or ValueError(sentence)"""
    if not (isinstance(n, int) and not isinstance(n, bool) and 1 <= n <= m["NP"]): raise ValueError("Say how many periods the lesson is.")
    return n

def _whole(f, forcing=False):
    """a fix as the page posted it, cut to its kind's fields (the server adds at and text), or ValueError(sentence). forcing (the board's
    request only): force (only when exactly True) is kept on a move, place, add, delete, teacher and room with why (the sentence the page showed for
    the place, when it is text), push on a move, place and add, all on a room (a change of room for every lesson of the group, which is never forced: see _room_all)"""
    if not isinstance(f, dict) or f.get("kind") not in FIELDS: raise ValueError("This kind of fix is not known.")
    k = f["kind"]; out = dict(kind=k, **{x: f[x] for x in FIELDS[k] if x in f})
    if len(out) != len(FIELDS[k]) + 1: raise ValueError("The fix is not complete.")
    if k == "add": out["room"] = f.get("room")
    if k == "delete" and f.get("group") is not None: out["group"] = f["group"]
    if k == "teacher" and not (isinstance(out["teachers"], list) and all(isinstance(t, str) for t in out["teachers"])): raise ValueError("The fix is not complete.")
    if forcing:
        if k in FORCED and f.get("force") is True:
            out["force"] = True
            if isinstance(f.get("why"), str): out["why"] = f["why"]
        if k in PUSHED and f.get("push") is True: out["push"] = True
        if k == "room" and f.get("all") is True: out["all"] = True
    return out

def _pushed(m, spec, f, pool):
    """the ids of the lessons a move, a place or an add with push would push out, from the draft as it is now, in ascending order: every lesson other
    than the fix's own with a row that shares a class with the lesson's rows (an add: the classes of its step 5 row) and a period with the target"""
    d, p = f.get("d"), f.get("p")
    if not all(isinstance(v, int) and not isinstance(v, bool) for v in (d, p)): return []
    if f["kind"] == "add":
        try: e = verify.planned_rows(spec).get(fixes._key(f["key"]))
        except ValueError: return []
        own, classes, n = None, set((e or {}).get("classes") or ()), f["n"]
    else:
        rows = [x for x in (pool if f["kind"] == "place" else m["lessons"]) if x["id"] == f["id"]]
        own, classes, n = f["id"], {c for x in rows for c in x["classes"]}, rows[0]["n"] if rows else 0
    if not classes or not isinstance(n, int): return []
    return sorted({x["id"] for x in m["lessons"] if x["id"] != own and x["d"] == d and set(x["classes"]) & classes and x["p"] < p + n and p < x["p"] + x["n"]})

def fix(move):
    """make one fix: judged against the draft as it is now. na is refused with its sentence; no is refused with its sentence too, unless the request
    has force (a move, place, add, delete, teacher or room from the board; never a room for all the group's lessons) and why, the sentence the page showed for that place, is the judgement's sentence now
    (a place that went wrong for another reason since is refused, with the reason as it now is); with push the lessons of the same classes in the
    way are worked out here, under the lock, and kept on the fix as out (none of push, force and why is kept). A lift needs no force. Returns info()."""
    f = _whole(move, forcing=True); force, push, why, all_ = f.pop("force", False), f.pop("push", False), f.pop("why", None), f.pop("all", False)
    with _lock:   # from the judgement to the write: two clicks cannot both pass the judgement on the same state
        m, rec, fx = _now(); spec, days, pool = m["checked_setup"], m["days"], fx["pool"]
        if f["kind"] == "add":
            _length(f["n"], m)
            if not f["room"]: f["room"] = fixes.add_room(m, spec, f["key"], f["d"], f["p"], f["n"]) if isinstance(f["d"], int) and isinstance(f["p"], int) else ""
        if push and f["kind"] in PUSHED:
            out = _pushed(m, spec, f, pool)
            if out: f["out"] = out
        if f["kind"] == "room" and all_:
            return _room_all(m, spec, days, pool, f)   # never forced: force and why are not passed on
        if f["kind"] == "room" and _has_room(next((y for y in m["lessons"] + pool if y["id"] == f["id"] and y["group"] == f["group"]), None), f["room"]): raise ValueError(NOTHING)
        j = fixes.judge(m, spec, days, f, pool=pool)
        if j["state"] == "na" or (j["state"] == "no" and not (force and why == j["why"])): raise ValueError(j["why"])
        text = fixes.apply_one(copy.deepcopy(m["lessons"]), f, spec, days, pool=copy.deepcopy(pool))   # the sentence of the fix as it is made
        meta = store.read_json(_p("meta.json"), {})
        store.write_json(_p("meta.json"), dict(meta, fixes=(meta.get("fixes") or []) + [dict(f, at=store.now(), text=text)]))
        return info()

NOTHING = "That changes nothing."

def _has_room(x, room):
    """whether the lesson row x (None: there is none) already has the room (a row with no room has "" or TBC, which is the same as none)"""
    return x is not None and (x["room"] == room or (fixes._no_room(x["room"]) and fixes._no_room(room)))

def _room_all(m, spec, days, pool, f):
    """a room fix for every lesson id of the row's key that has a row of the fix's group and is not in that room yet (on the timetable and in the pool; "That changes
    nothing." when none is left), in ascending id order, each judged
    on the timetable the earlier ones leave and all kept with one batch id (so one undo takes them back), or none. It is never forced: any "no" and every
    "na" refuses the whole with its sentence, whatever force and why the request had (the person was asked about one lesson only). Called under the lock. Returns info()."""
    rows = [y for y in m["lessons"] + pool if y["id"] == f["id"]]
    if not rows: raise ValueError(NOT_FOUND_LESSON)
    x = next((y for y in rows if y["group"] == f["group"]), None)
    if x is None: raise ValueError(f"There is no row of {f['group']} in that lesson.")
    k = fixes._row_key(x); rows = [y for y in fixes.rows_of_key(m["lessons"] + pool, k) if y["group"] == f["group"]]
    ids = sorted({y["id"] for y in rows if not _has_room(y, f["room"])})   # the lessons already in that room are left as they are
    if not ids: raise ValueError(NOTHING)
    lessons, pl, texts, fl = copy.deepcopy(m["lessons"]), copy.deepcopy(pool), [], []
    for i in ids:
        one = dict(kind="room", id=i, group=f["group"], room=f["room"]); j = fixes.judge(dict(m, lessons=lessons), spec, days, one, pool=pl)
        if j["state"] in ("na", "no"): raise ValueError(j["why"])
        texts.append(fixes.apply_one(lessons, one, spec, days, pool=pl)); fl.append(one)
    batch, at = secrets.token_hex(4), store.now(); meta = store.read_json(_p("meta.json"), {})
    store.write_json(_p("meta.json"), dict(meta, fixes=(meta.get("fixes") or []) + [dict(g, at=at, text=t, batch=batch) for g, t in zip(fl, texts)]))
    return info()

def _fixes_of(moves, m, spec, days):
    """a list of one or two fixes as the page posted them, each whole (an add with no room gets the one that fits on the timetable the earlier fixes leave), or ValueError(sentence)"""
    if not isinstance(moves, list) or not 1 <= len(moves) <= 2: raise ValueError("Send one or two fixes.")
    out = []
    for f in map(_whole, moves):   # never forcing, and never a lesson that is not placed: a batch makes only clean changes
        if f["kind"] in ("lift", "place"): raise ValueError("This kind of fix is not known.")
        if f["kind"] == "add":
            _length(f["n"], m)
            if not f["room"]: f["room"] = fixes.add_room(dict(m, lessons=helper.chain(m, spec, days, out)["lessons"]), spec, f["key"], f["d"], f["p"], f["n"]) if isinstance(f["d"], int) and isinstance(f["p"], int) else ""
        out.append(f)
    return out

def fix_many(moves):
    """make one or two fixes together: each judged on the timetable the earlier ones leave, all kept (with one batch id) or none. Returns info()."""
    with _lock:   # from the judgement to the write, as fix does
        m, rec, fx = _now(); spec, days = m["checked_setup"], m["days"]; fl = _fixes_of(moves, m, spec, days)
        c = helper.chain(m, spec, days, fl)
        if c["state"] in ("no", "na"): raise ValueError(c["why"])
        if len(c["texts"]) != len(fl): raise ValueError("That fix could not be made. Check the list again.")
        batch, at = secrets.token_hex(4), store.now(); meta = store.read_json(_p("meta.json"), {})
        store.write_json(_p("meta.json"), dict(meta, fixes=(meta.get("fixes") or []) + [dict(f, at=at, text=t, batch=batch) for f, t in zip(fl, c["texts"])]))
        return info()

def suggest(key):
    """ways to settle the warning with that key, as the draft is now -> helper.suggest's dict(suggestions, none, blocked)"""
    m, rec, fx = _now(); w = next((w for w in _build(m, rec, fx)["warnings"] if w["key"] == key), None)
    if not w: raise ValueError("That warning is no longer on the list.")
    return helper.suggest(m, m["checked_setup"], m["days"], w)

def preview(moves):
    """what the fixes would do, written nowhere -> dict(state, why, texts, classes, gone). classes: the week of every class a changed lesson is of, before or
    after, as grid gives it, each lesson with mark (moved, changed, new or '') and, when moved, was = dict(d, p); gone: the lessons deleted. A list that is
    refused shows the timetable up to the fix refused."""
    m, rec, fx = _now(); spec, days = m["checked_setup"], m["days"]; fl = _fixes_of(moves, m, spec, days)
    c = helper.chain(m, spec, days, fl)
    if c["state"] in ("no", "na"): c = dict(helper.chain(m, spec, days, fl[:len(c["steps"]) - 1]), state=c["state"], why=c["why"])
    L, was, touched = c["lessons"], c["was"], c["touched"]; first, last = {}, {}
    for x in was: first.setdefault((x["id"], x["group"]), x); last[(x["id"], x["group"])] = x
    names = {n for x in was for n in x["classes"]} | {n for x in L if x["id"] in touched for n in x["classes"]}
    def mark(x):
        w = first.get((x["id"], x["group"]))   # a row is judged by its own row as it was; a sibling row of a changed lesson that was not changed has none
        if x["id"] not in touched: return dict(mark="")
        if w is None: return dict(mark="" if any(k[0] == x["id"] for k in first) else "new")
        if (x["d"], x["p"]) != (w["d"], w["p"]): return dict(mark="moved", was=dict(d=w["d"], p=w["p"]))
        return dict(mark="changed" if x["teachers"] != w["teachers"] or x["room"] != w["room"] else "")
    marks, mi, out = {(x["id"], x["group"]): mark(x) for x in L}, dict(m, lessons=L), []
    for n in (c_["name"] for c_ in m["classes"] if c_["name"] in names):
        g = _payload(mi, "class", n, short=False); g["lessons"] = [dict(r, **marks[(r["id"], r["group"])]) for r in g["lessons"]]; out.append(g)
    now = {(x["id"], x["group"]) for x in L}
    return dict(state=c["state"], why=c["why"], texts=c["texts"], classes=out,
                gone=[dict(cls=n, what=fixes.what(x), d=x["d"], p=x["p"]) for k, x in last.items() if k not in now for n in x["classes"]])

def _pick_ok(p): return isinstance(p, dict) and len(p) <= 10 and all(isinstance(k, str) and isinstance(v, str) and len(k) <= 250 and len(v) <= 250 for k, v in p.items())

def ask(words, pick=None, ask=None):
    """the typed request answered on the draft as it is now -> dict(ok=False, error) or dict(ok=True, ask, **typed.answer). Without ask the words are read by the
    model (typed.read, outside every lock: it can take up to about 25 seconds); with ask (sent back with pick to settle a choice) the model is not called again. Nothing is kept."""
    if not exists(): raise NoDraft("There is no draft.")
    if ask is None:
        r = typed.read(words)
        if not r["ok"]: return r
        ask = r["ask"]
    elif not typed.check(ask): return dict(ok=False, error=typed.FAILED)
    m, rec, fx = _now()
    return dict(ok=True, ask=ask, **typed.answer(m, m["checked_setup"], m["days"], ask, pick if _pick_ok(pick) else None))

def undo():
    """drop the last fix, and the fixes made together with it (the same batch). Returns info()."""
    with _lock:
        if not exists(): raise NoDraft("There is no draft.")
        meta = store.read_json(_p("meta.json"), {}); fl = list(meta.get("fixes") or [])
        if not fl: raise ValueError("There is nothing to undo.")
        b = fl.pop().get("batch")
        while b and fl and fl[-1].get("batch") == b: fl.pop()
        store.write_json(_p("meta.json"), dict(meta, fixes=fl, published_fixes=min(meta.get("published_fixes", 0), len(fl))))
        return info()

def database(path):
    """the draft with its fixes as a timetable database at path, its setup labelled with the setup's version now (on a copy:
    the cached model is shared). NotPlaced while a lesson waits in Not placed."""
    m, rec, fx = _now()
    if fx["pool"]: raise NotPlaced(_count(fx["pool"]))
    setup = dict(m["setup"]); setup["school"] = dict(setup.get("school") or {}, config_id=f"v{rec['v']}")
    write_db(m, path, spec=setup)

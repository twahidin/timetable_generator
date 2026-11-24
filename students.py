"""A saved student follows onto the published timetable: after a save names student rows, those students' records on
the published timetable are brought up to date at once, and nothing else in it changes. Students are matched by
student ID (the published records have no row id). A student who cannot follow is left as the published timetable
has them, with the reason in words."""
import collections, copy, hashlib, json, math, sys, threading, time
import history, store
from ttgen import export as E

KIND = "students-published"
FILES_WAIT = 60   # seconds with no student change before the files to download are made again (a test lowers it)
_files = dict(last=0.0, pending=False, running=False)   # the last change, a remake wanted, the one thread alive
_files_lock = threading.Lock()

def key(row):
    return str(row.get("id") or row.get("name") or "").strip()

def record(row):
    """what a full publish makes of one setup row (ttgen/export.py _model)"""
    return dict(id=str(row.get("id") or row.get("name")), name=str(row.get("name") or row.get("id")), cls=str(row.get("class") or ""),
                level=str(row.get("level") or ""), groups=[str(g) for g in row.get("groups") or []])

def why_not(row, model, counts):
    """why this setup row cannot follow onto the published model, or None when it can"""
    k = key(row)
    if not k: return "no student ID or name"
    if counts.get(k, 0) > 1: return "this ID is on the list twice"
    cls = str(row.get("class") or "")
    if not cls.strip(): return "no class"
    if cls not in model["class_ix"]: return f"class {cls} is not on the published timetable"
    have = {L["group"] for L in model["lessons"]}
    missing = [str(g) for g in row.get("groups") or [] if str(g) not in have]
    if len(missing) == 1: return f"group {missing[0]} is not on the published timetable"
    if missing: return f"groups {', '.join(missing)} are not on the published timetable"
    return None

def touched(pairs):
    """(keys of every row after the save, keys that may be removed, the keys of a save that deleted several rows: held back)"""
    keys = [key(a) for b, a in pairs if a is not None]
    gone = [b for b, a in pairs if a is None and b is not None]
    may_remove = {key(b) for b, a in pairs if b is not None and a is not None and key(b) != key(a)}
    if len(gone) == 1: may_remove.add(key(gone[0]))
    return keys, may_remove, ({key(b) for b in gone} if len(gone) > 1 else set())

def _text(updated, removed, left, held):
    out = []
    if len(updated) == 1: out.append(f"Published timetable updated for {updated[0]['name']} ({updated[0]['id']}).")
    elif updated: out.append(f"Published timetable updated for {len(updated)} students.")
    if len(removed) == 1: out.append(f"{removed[0]['name']} ({removed[0]['id']}) removed from the published timetable.")
    elif removed: out.append(f"{len(removed)} students removed from the published timetable.")
    if len(left) == 1: out.append(f"Published timetable not changed for {left[0]['name']} ({left[0]['id']}): {left[0]['why']}.")
    elif left: out.append(f"Published timetable not changed for {len(left)} students: their groups or classes are not on it.")
    if held == 1: out.append("1 student stays on the published timetable until Update the published timetable is pressed.")
    elif held: out.append(f"{held} students stay on the published timetable until Update the published timetable is pressed.")
    return " ".join(out)

def _setup_copy(setup, changed, rows_now):
    """a shallow copy of a setup whose student rows for the changed keys are the setup's rows now (none when removed)"""
    out = dict(setup); rows, done = [], set()
    for r in setup.get("students") or []:
        k = key(r) if isinstance(r, dict) else None
        if k not in changed: rows.append(r); continue
        if k not in done: rows.extend(copy.deepcopy(rows_now.get(k, []))); done.add(k)
    for k in changed:
        if k not in done: rows.extend(copy.deepcopy(rows_now.get(k, []))); done.add(k)
    out["students"] = rows
    return out

def _commit(model, new_students, updated, added, removed, rows_now):
    """put a new model (the old one is not changed) in the published folder when any student was updated, added or removed:
    its setup rows kept in step, the checks worked out again, one swap_model (the caller holds store._publishing)"""
    if not (updated or added or removed): return
    changed = {str(s["id"]).strip() for s in updated + added + removed}
    new = dict(model); new["students"] = new_students
    if isinstance(model.get("setup"), dict): new["setup"] = _setup_copy(model["setup"], changed, rows_now)
    if isinstance(model.get("checked_setup"), dict):
        new["checked_setup"] = new["setup"] if model["checked_setup"] is model.get("setup") else _setup_copy(model["checked_setup"], changed, rows_now)
    checks = E.check_model(new)
    if new.get("choice_problems"): checks["problems"] = list(checks["problems"]) + list(new["choice_problems"])
    checks["ok"] = not checks["problems"]
    new["checks"] = checks
    store.swap_model(new, students=len(new["students"]), ok=checks["ok"], problems=checks["problems"][:20], students_at=store.now(), files_behind=True)
    try: schedule_files()
    except Exception as e: print("warning: the files to download could not be scheduled (" + type(e).__name__ + ")", file=sys.stderr)   # the update is made

def _rows_by_key(setup_rows):
    """the setup's student rows by key (blank rows left out) and how many rows each key has"""
    rows = [r for r in setup_rows or [] if isinstance(r, dict) and key(r)]
    rows_now = collections.defaultdict(list)
    for r in rows: rows_now[key(r)].append(r)
    return rows_now, collections.Counter(key(r) for r in rows)

def _at(model):
    return {str(s["id"]).strip(): i for i, s in enumerate(model["students"])}

def _bring(model, waiting, extra=()):
    """the model's students with the waiting records put in (updated in place or added at the end) and the extra
    published indexes taken out: (new students, updated, added, removed); the model is not changed"""
    new_students, updated, added = list(model["students"]), [], []
    for k, r, rec, i in waiting:
        if i is None: new_students.append(rec); added.append(rec)
        else: new_students[i] = rec; updated.append(rec)
    removed = [model["students"][i] for i in extra]
    if removed:
        gone = {id(s) for s in removed}
        new_students = [s for s in new_students if id(s) not in gone]
    return new_students, updated, added, removed

def _write(model, new_students, updated, added, removed, rows_now, text, by, batch):
    """the new model in the published folder (when anything changed) and its History line (when there are words)"""
    _commit(model, new_students, updated, added, removed, rows_now)
    if text:
        try: history.add(dict(kind=KIND, text=text, where="Students", of=batch, **by))
        except Exception as e: store._warn(e)   # the update is made: a history failure never undoes it

def _result(updated, added, removed, left, held, text):
    return dict(updated=[s["id"] for s in updated], added=[s["id"] for s in added], removed=[s["id"] for s in removed],
                left=left, held=held, text=text)

def _files_run():
    """the one background thread: waits until FILES_WAIT seconds have passed since the last change, remakes the files,
    and goes again while a change arrived meanwhile; an error is told by its type alone and the thread stops"""
    try:
        while True:
            with _files_lock:
                if not _files["pending"]: _files["running"] = False; return
            while time.time() - _files["last"] < FILES_WAIT: time.sleep(0.2)   # FILES_WAIT read on every poll
            with _files_lock: _files["pending"] = False
            pub = store.published()
            if pub is None or not pub["meta"].get("files_behind"): continue   # a publish made fresh files meanwhile
            if store.remake_files() is False:
                with _files_lock: _files["pending"] = True
    except BaseException as e:
        print("warning: the files to download could not be made (" + type(e).__name__ + ")", file=sys.stderr)
    with _files_lock: _files["running"] = False

def schedule_files():
    """a student change was written: the files to download are made again once no change has come for FILES_WAIT seconds"""
    with _files_lock:
        _files["last"] = time.time(); _files["pending"] = True
        if _files["running"]: return
        _files["running"] = True
    try: threading.Thread(target=_files_run, name="files-to-download", daemon=True).start()
    except BaseException:
        with _files_lock: _files["running"] = False
        raise

def files_now():
    """remake the files to download at once (for tests): store.remake_files()"""
    return store.remake_files()

def resume_files():
    """at start: the files are made again when the published timetable says they are behind"""
    pub = store.published()
    if pub and pub["meta"].get("files_behind"): schedule_files()

def follow(pairs, by, batch=None):
    """bring the students these (before, after) rows name up to date on the published timetable, reading the setup as
    it is now; None when nothing is published"""
    keys, may_remove, gone_keys = touched(pairs)
    renamed = {key(b): key(a) for b, a in pairs if b is not None and a is not None and key(b) != key(a)}
    gone = [key(b) for b, a in pairs if a is None and b is not None]
    single_gone = set(gone) if len(gone) == 1 else set()
    with store._publishing:
        pub = store.published()
        if pub is None: return None
        model = pub["model"]
        rows_now, counts = _rows_by_key(store.setup_record()["spec"].get("students"))
        at = _at(model)
        held = sum(1 for k in gone_keys if k and k in at and k not in rows_now)   # held back: still published and off the list
        new_students = list(model["students"])
        updated, added, removed, left, made = [], [], [], [], set()
        order = [k for k in list(dict.fromkeys(keys)) + sorted(may_remove - set(keys)) if k]   # the rows after the save first, then the old keys; a blank row is ignored
        for k in order:
            if k in rows_now:
                row = rows_now[k][0]; why = why_not(row, model, counts)
                if why: left.append(_left(k, row, why)); continue
                rec = record(row); made.add(k)   # it follows: an old ID renamed to it may go, even when its record was already equal
                if k not in at: at[k] = len(new_students); new_students.append(rec); added.append(rec)
                elif new_students[at[k]] != rec: new_students[at[k]] = rec; updated.append(rec)
            elif k in may_remove and k in at and (k in single_gone or renamed.get(k) in made):   # a re-numbered row whose new ID did not follow stays
                removed.append(new_students[at[k]])
        if removed:
            out = {id(s) for s in removed}
            new_students = [s for s in new_students if id(s) not in out]
        text = _text(updated + added, removed, left, held)
        _write(model, new_students, updated, added, removed, rows_now, text, by, batch)
        return _result(updated, added, removed, left, held, text)

def _compare(model, setup_rows):
    """the setup's student rows set against the published model: (rows_now by key, left, waiting, extra)
    where left is [(key, row, why)], waiting [(key, row, record, published index or None)], extra [published index];
    blank rows are ignored and a repeated ID counts once"""
    rows_now, counts = _rows_by_key(setup_rows)
    at = _at(model)
    left, waiting = [], []
    for k, rs in rows_now.items():
        why = why_not(rs[0], model, counts)
        if why: left.append((k, rs[0], why)); continue
        rec = record(rs[0])
        if k not in at or model["students"][at[k]] != rec: waiting.append((k, rs[0], rec, at.get(k)))
    extra = [i for k, i in at.items() if k not in rows_now]
    return rows_now, left, waiting, extra

def _setup_students():
    """the setup's student rows, or None when no setup is saved at all (not the same as an empty list)"""
    spec = (store.setup_record() or {}).get("spec")
    return None if spec is None else spec.get("students") or []

def _left(k, row, why):
    return dict(id=k, name=str(row.get("name") or ""), why=why)

def _counts(waiting, extra):
    return dict(change=sum(1 for w in waiting if w[3] is not None), add=sum(1 for w in waiting if w[3] is None), remove=len(extra))

NO_COUNTS = dict(change=0, add=0, remove=0)

def status():
    """the whole list against the published timetable; writes nothing, and takes no lock: it reads the published
    timetable and the setup once each, so it never waits for a publish"""
    pub = store.published()
    if pub is None: return dict(published=False)
    setup_rows = _setup_students()
    model = pub["model"]; stamp_ = stamp(pub)
    if setup_rows is None:
        return dict(published=True, at=pub["meta"].get("published_at"), stamp=stamp_, students=len(model["students"]), listed=0, same=0, differ=[], differ_n=0,
                    counts=dict(NO_COUNTS), can_update=False, files_behind=bool(pub["meta"].get("files_behind")), no_setup=True)
    rows_now, left, waiting, extra = _compare(model, setup_rows)
    differ = ([dict(_left(k, r, w), kind="left") for k, r, w in left]
              + [dict(id=k, name=str(r.get("name") or ""), why="not updated yet", kind="waiting") for k, r, rec, i in waiting]
              + [dict(id=str(model["students"][i]["id"]), name=str(model["students"][i]["name"]), why="on the published timetable but not on this list", kind="extra") for i in extra])
    counts = _counts(waiting, extra)
    return dict(published=True, at=pub["meta"].get("published_at"), stamp=stamp_, students=len(model["students"]), listed=len(rows_now),
                same=len(rows_now) - len(left) - len(waiting), differ=differ[:10], differ_n=len(differ), counts=counts,
                can_update=any(counts.values()), files_behind=bool(pub["meta"].get("files_behind")))

def update_all(by, expect=None):
    """bring the whole list into step with the published timetable: students who can follow are updated or added,
    published students not on the list are removed, students who cannot follow are left; None when nothing is published.
    expect: the counts {change, add, remove} the member was asked about; when the counts now differ nothing is written
    and the answer is {"changed": True}"""
    with store._publishing:
        pub = store.published()
        if pub is None: return None
        model = pub["model"]
        setup_rows = _setup_students()
        if setup_rows is None:   # no setup saved: nothing to compare with
            return dict(changed=True) if expect is not None and expect != NO_COUNTS else _result([], [], [], [], 0, "")
        rows_now, left, waiting, extra = _compare(model, setup_rows)
        if expect is not None and expect != _counts(waiting, extra): return dict(changed=True)
        new_students, updated, added, removed = _bring(model, waiting, extra)
        text = ""
        if updated or added or removed:
            text = f"Published timetable brought into step with the list: {len(updated)} changed, {len(added)} added, {len(removed)} removed."
        _write(model, new_students, updated, added, removed, rows_now, text, by, None)   # no "of": no save made this line
        return _result(updated, added, removed, [_left(k, r, w) for k, r, w in left], 0, text)

def catch_up(by=None):
    """after a full publish: every listed student who can follow and whose published record differs or is absent is put
    on it (a save that landed while the publish was being made, which the publish read too early); nobody is removed
    and nothing is written when all agree; by the app when by is None; None when nothing is published"""
    with store._publishing:
        pub = store.published()
        if pub is None: return None
        setup_rows = _setup_students()
        if setup_rows is None: return _result([], [], [], [], 0, "")
        model = pub["model"]
        rows_now, left, waiting, extra = _compare(model, setup_rows)
        new_students, updated, added, _ = _bring(model, waiting)
        text = _text(updated + added, [], [], 0)
        _write(model, new_students, updated, added, [], rows_now, text, by or history.by_of(None, "app"), None)
        return _result(updated, added, [], [_left(k, r, w) for k, r, w in left], 0, text)

def people_stamp(pub):
    """names the published students (ID, name, class, groups): a short hash that moves with any student change; "" when
    nothing is published"""
    if not pub: return ""
    rows = sorted([str(s.get("id")), str(s.get("name")), str(s.get("cls")), sorted(str(g) for g in s.get("groups") or [])] for s in (pub.get("model") or {}).get("students") or [])
    return hashlib.sha1(json.dumps(rows).encode()).hexdigest()[:12]

def stamp(pub):
    """names this publish's lessons: the published time, then a short hash of the lessons (the time is only to the minute);
    a student change leaves it as it is"""
    keys = ("id", "d", "p", "n", "group", "room", "subject", "teachers", "classes")
    rows = [[L.get(k) for k in keys] for L in pub["model"]["lessons"]]
    h = hashlib.sha1(json.dumps(rows, sort_keys=True, default=str).encode()).hexdigest()[:10]
    return f"{pub['meta'].get('published_at')}|{h}"

def _seats(rooms, capacities):
    """the one room's capacity as a whole number above 0, else None"""
    if len(rooms) != 1: return None
    cap = capacities.get(rooms[0])
    try: x = float(str(cap).strip())
    except (TypeError, ValueError): return None
    if not math.isfinite(x): return None   # "inf", "1e400", "nan"
    return int(x) if x > 0 and x == int(x) else None

def skeleton():
    """the published timetable's shape for the student screen: days, periods, each class's whole-class lessons and each
    teaching group's lessons; no student in it; None when nothing is published"""
    pub = store.published()
    if pub is None: return None
    m = pub["model"]; caps = {r["name"]: r.get("capacity") for r in m.get("rooms") or []}
    whole = {c["name"]: set() for c in m["classes"]}
    gs = collections.OrderedDict()
    for L in m["lessons"]:
        if L["group"] == E.ENTIRE:
            for cn in L["classes"]:
                if cn in whole: whole[cn].add((L["d"], L["p"], L["n"], E.abbrev(L["subject"]), L["room"]))
            continue
        g = gs.setdefault(L["group"], dict(subject=L["subject"], band=L.get("block") or "", classes=set(), teachers={}, rooms={}, slots=set()))
        g["classes"].update(L["classes"]); g["slots"].add((L["d"], L["p"], L["n"]))
        for tn in L["teachers"]:
            if str(tn).strip(): g["teachers"][tn] = 1
        if str(L["room"] or "").strip(): g["rooms"][L["room"]] = 1
    classes = {}
    for c in m["classes"]:
        classes[c["name"]] = dict(level=c["level"], codes=m["cgrid"].get(c["name"]) or E._codes_for(m, [c["level"]]),
                                  whole=[list(x) for x in sorted(whole[c["name"]], key=lambda x: (x[0], x[1], x[2]))])
    groups = {}
    for code, g in gs.items():
        rooms = list(g["rooms"])
        groups[code] = dict(subject=g["subject"], short=E.abbrev(g["subject"]), band=g["band"], classes=sorted(g["classes"]), teachers=list(g["teachers"]),
                            rooms=rooms, seats=_seats(rooms, caps), slots=[list(x) for x in sorted(g["slots"])])
    return dict(stamp=stamp(pub), days=m["days"], NP=m["NP"], times=m["times"], classes=classes, groups=groups)

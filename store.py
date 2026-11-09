"""Where things live: the committee's saved setup, its earlier copies and the published timetable, all under DATA_DIR
(a Railway volume, so they survive redeploys)."""
import collections, copy, csv, datetime, io, json, os, pickle, shutil, threading, time
from ttgen.export import model_from_files, export_all
import sync
from access import personal_code, personal_codes_on, norm

HERE = os.path.dirname(os.path.abspath(__file__))

def _data_dir():
    d = os.environ.get("DATA_DIR") or os.environ.get("RAILWAY_VOLUME_MOUNT_PATH") or os.path.join(HERE, "data")
    os.makedirs(d, exist_ok=True)
    return d

DATA = _data_dir()
PUB = os.path.join(DATA, "published")
RUNS = os.path.join(DATA, "runs")
HIST = os.path.join(DATA, "setup_history")   # earlier saves of the setup, to restore from
os.makedirs(RUNS, exist_ok=True)
KEEP_SAVES = 48
_lock = threading.Lock()
_publishing = threading.Lock()   # one publish at a time: each writes the same folder before swapping it in

def now():
    return datetime.datetime.now().astimezone().strftime("%d %b %Y, %H:%M")

def on_railway():
    """Railway documents RAILWAY_ENVIRONMENT_NAME and _ID; RAILWAY_ENVIRONMENT is the older name"""
    return any(os.environ.get(k) for k in ("RAILWAY_ENVIRONMENT_NAME", "RAILWAY_ENVIRONMENT_ID", "RAILWAY_ENVIRONMENT"))

def on_volume():
    """False when running on Railway without a volume (everything is lost on the next deploy)"""
    return not (on_railway() and not (os.environ.get("RAILWAY_VOLUME_MOUNT_PATH") or os.environ.get("DATA_DIR")))

def write_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f: json.dump(obj, f, ensure_ascii=False)
    os.replace(tmp, path)

def read_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as f: return json.load(f)
    except (OSError, ValueError): return default

# ------------------------------------------------------------------------------------------------ the shared setup
# One setup, one version number, one change log, all in this process (one gunicorn worker) and guarded by _setup_lock.
# setup.json holds saved_at, ts, v, replaced_v and the spec; the log is lost on a restart, which makes every browser
# fetch the setup again.
_setup_lock = threading.RLock()
_setup = {}                                   # the cached record; empty = not loaded (or no setup yet)
_log = collections.deque(maxlen=400)          # dict(v, client, ops), contiguous versions ending at _setup["v"]
_present = {}                                 # client -> when it was last seen
_last_point = [0.0]                           # when the newest restore point was taken
POINT_EVERY = 600                             # seconds between restore points while people work
BIG_DELETE = 20                               # rows deleted in one change that earn a restore point
SETUP_FILE = os.path.join(DATA, "setup.json")

def _write_setup():
    write_json(SETUP_FILE, {k: _setup[k] for k in ("saved_at", "ts", "v", "replaced_v", "spec")})

def _stamp():
    _setup.update(saved_at=now(), ts=datetime.datetime.now().timestamp())

def _load():
    """the cached record, read from disk the first time. Rows saved before versions get an _id and a first version."""
    if _setup: return _setup
    x = read_json(SETUP_FILE)
    if not x or not x.get("spec"): return _setup
    _setup.update(spec=x["spec"], saved_at=x.get("saved_at"), ts=x.get("ts") or 0, v=x.get("v") or 0, replaced_v=x.get("replaced_v") or 0)
    if not _setup["v"] or sync.ensure_ids(_setup["spec"]):
        _setup["v"] += 1
        _write_setup()
    _log.clear()
    return _setup

def _points():
    return sorted((f for f in os.listdir(HIST) if f.endswith(".json")), key=lambda f: int(f[:-5]) if f[:-5].isdigit() else 0) if os.path.isdir(HIST) else []

def restore_point(why):
    """keep a copy of the setup as it is now, to go back to (the last KEEP_SAVES of them)"""
    with _setup_lock:
        cur = _load()
        if not cur: return
        os.makedirs(HIST, exist_ok=True)
        t = datetime.datetime.now().timestamp(); name = int(t * 1000)
        while os.path.exists(os.path.join(HIST, f"{name}.json")): name += 1
        write_json(os.path.join(HIST, f"{name}.json"), dict(what=why, saved_at=now(), ts=t, v=cur["v"], spec=cur["spec"]))
        _last_point[0] = t
        for f in _points()[:-KEEP_SAVES]: os.remove(os.path.join(HIST, f))

def _copy(rec):
    return dict(spec=copy.deepcopy(rec.get("spec")), saved_at=rec.get("saved_at"), ts=rec.get("ts") or 0, v=rec.get("v") or 0)

def setup_record():
    with _setup_lock: return _copy(_load())

def load_setup():
    r = setup_record()
    return (r["spec"], r["saved_at"]) if r["spec"] else (None, None)

def replace_setup(spec, why):
    """the whole setup replaced (a save of everything, an imported workbook, a restore): everyone fetches it again"""
    with _setup_lock:
        if _load(): restore_point("Before: " + why)
        sync.ensure_ids(spec)
        _setup.update(spec=spec, v=_setup.get("v", 0) + 1)
        _setup["replaced_v"] = _setup["v"]
        _stamp(); _log.clear(); _write_setup()
        return dict(v=_setup["v"], saved_at=_setup["saved_at"])

def save_setup(spec):
    return replace_setup(spec, "Saved")

def _risky(ops):
    dels = [o for o in ops if isinstance(o, list) and o and o[0] == "del"]
    return len(dels) > BIG_DELETE or any(len(o) > 1 and o[1] == "teachers" for o in dels)

class Refused(Exception):
    """a change the caller's check turned down; the message is a sentence for the person"""

class Replaced(Exception):
    """the whole setup was replaced after the version the change was made on: it is not applied"""

def apply_changes(ops, client, check=None, since=None, filter=None):
    """apply a change to the current setup; returns (the new version, refused).
    check(spec, ops) runs on the setup held under the lock: a sentence back raises Refused and nothing is applied.
    filter(spec, ops) -> (allowed, refused) also runs under the lock: only the allowed operations are applied (one
    version, one log entry holding just them; none when nothing is allowed) and refused, [(index in ops, sentence)], is
    handed back for the caller to report.
    since: the version the change was made on; when the setup was replaced after it, Replaced is raised and nothing
    is applied (the change belongs to a setup that is gone)"""
    with _setup_lock:
        cur = _load()
        if not cur: raise LookupError("no setup")
        if since is not None and since < cur.get("replaced_v", 0): raise Replaced()
        if check:
            why = check(cur["spec"], ops)
            if why: raise Refused(why)
        refused = []
        if filter: ops, refused = filter(cur["spec"], ops)
        if not ops: return cur["v"], refused
        if datetime.datetime.now().timestamp() - _last_point[0] > POINT_EVERY or _risky(ops): restore_point("While working")
        sync.apply(cur["spec"], ops)
        cur["v"] += 1
        _stamp(); _write_setup()
        _log.append(dict(v=cur["v"], client=client, ops=ops))
        return cur["v"], refused

def changes_since(since, client, upto=None):
    """what other clients changed after version since; a reset when the log no longer reaches back that far.
    upto stops at a version (the caller's own change), so nothing after it is skipped later."""
    with _setup_lock:
        cur = _load(); v = cur.get("v", 0) if upto is None else upto
        if since >= v and since <= cur.get("v", 0): return dict(v=v, patches=[])
        if since > cur.get("v", 0) or not _log or _log[0]["v"] > since + 1:
            return dict(v=v, reset=True, replaced=cur.get("replaced_v", 0) > since)
        return dict(v=v, patches=[dict(v=e["v"], ops=e["ops"]) for e in _log if since < e["v"] <= v and e["client"] != client])

def copies():
    """the restore points, newest first (the copies themselves stay on disk)"""
    with _setup_lock:
        out = []
        for f in reversed(_points()):
            x = read_json(os.path.join(HIST, f)) or {}
            if x.get("spec"): out.append(dict(id=f"save-{f[:-5]}", what=x.get("what") or "Saved", when=x.get("saved_at")))
        return out

def restore(copy_id):
    with _setup_lock:
        f = os.path.join(HIST, copy_id[5:] + ".json") if copy_id.startswith("save-") and copy_id[5:].isdigit() else None
        x = read_json(f) if f else None
        if not x or not x.get("spec"): raise KeyError(copy_id)
        return replace_setup(x["spec"], "Restored " + (x.get("saved_at") or "an earlier copy"))

def seen(client):
    """note this client as here now; how many others were seen in the last 20 seconds"""
    with _setup_lock:
        t = time.time()
        for k in [k for k, w in _present.items() if t - w > 20]: del _present[k]
        _present[client] = t
        return len(_present) - 1

def past_setups():
    """earlier copies of the setup, newest first: the restore points kept in HIST, and the copies an earlier version of
    the app kept with each Generate run (RUNS is no longer written)"""
    out = []
    for f in _points():
        x = read_json(os.path.join(HIST, f)) or {}
        if x.get("spec"): out.append(dict(id=f"save-{f[:-5]}", what=x.get("what") or "Saved", when=x.get("saved_at"), ts=x.get("ts") or 0, spec=x["spec"]))
    for d in os.listdir(RUNS):
        w, st = os.path.join(RUNS, d, "work.json"), read_json(os.path.join(RUNS, d, "state.json")) or {}
        spec = read_json(w) if os.path.exists(w) else None
        if spec and spec.get("school"): out.append(dict(id=f"run-{d}", what="Generate", when=st.get("started"), ts=os.path.getmtime(w), spec=spec))
    return sorted(out, key=lambda x: -x["ts"])

_cache = dict(stamp=None, value=None)

def published():
    """the published timetable: dict(meta, model, codes {normalised code: student id}) or None"""
    meta_path = os.path.join(PUB, "meta.json")
    if not os.path.exists(meta_path): return None
    stamp = os.path.getmtime(meta_path)
    with _lock:
        if _cache["stamp"] != stamp:
            with open(os.path.join(PUB, "model.pkl"), "rb") as f: model = pickle.load(f)
            meta = read_json(meta_path, {})
            codes = {norm(personal_code(s["id"])): s["id"] for s in model["students"]} if personal_codes_on() else {}
            _cache.update(stamp=stamp, value=dict(meta=meta, model=model, codes=codes, views={}))
        return _cache["value"]

def publish(setup_xlsx, timetable_path, run_id=None, source=None, log=print):
    """export everything into a fresh folder, then swap it in so viewers never see a half-written timetable. The
    timetable is a workbook with a Lessons sheet or a timetable database; setup_xlsx may be None for a database this app
    or the skill made (it holds its setup). source names a timetable made outside the app (the file it came from)."""
    with _publishing:
        tmp, old = PUB + ".new", PUB + ".old"
        shutil.rmtree(tmp, ignore_errors=True); os.makedirs(tmp)
        m = model_from_files(setup_xlsx, timetable_path)
        log("Making the Excel workbook, the timetable finder, the PDFs and the timetable database...")
        out = export_all(m, tmp, log=lambda *a: None)
        if setup_xlsx: shutil.copy(setup_xlsx, os.path.join(tmp, "setup.xlsx"))
        shutil.copy(timetable_path, os.path.join(tmp, "timetable" + os.path.splitext(timetable_path)[1]))
        shutil.rmtree(os.path.join(tmp, "PDF", "Classes"), ignore_errors=True)   # single PDFs are in the zip and made on demand
        for k in ("Teachers", "Rooms", "Students"): shutil.rmtree(os.path.join(tmp, "PDF", k), ignore_errors=True)
        with open(os.path.join(tmp, "model.pkl"), "wb") as f: pickle.dump(m, f)
        files = dict(excel=os.path.basename(out["excel"]), html=os.path.basename(out["html"]), zip=os.path.basename(out["pdf_zip"]), db=os.path.basename(out["db"]),
                     books={os.path.basename(p).split(" - ")[0].lower(): os.path.relpath(p, tmp) for p in out["pdf_books"]})
        ch = m["checks"]
        write_json(os.path.join(tmp, "meta.json"), dict(published_at=now(), run=run_id, source=source, school=m["school"]["name"], timetable=m["school"]["timetable"],
                                                         ok=ch["ok"], problems=ch["problems"][:20], after_school=ch["after_school"],
                                                         classes=len(m["classes"]), students=len(m["students"]), lessons=ch["lessons"], files=files))
        with _lock:
            shutil.rmtree(old, ignore_errors=True)
            if os.path.exists(PUB): os.replace(PUB, old)
            os.replace(tmp, PUB)
            shutil.rmtree(old, ignore_errors=True)
            _cache.update(stamp=None, value=None)
        return m

def codes_csv(model):
    buf = io.StringIO(); w = csv.writer(buf)
    w.writerow(["Class", "Student ID", "Name", "Personal code"])
    order = {c["name"]: i for i, c in enumerate(model["classes"])}
    for s in sorted(model["students"], key=lambda s: (order.get(s["cls"], 999), s["id"])):
        w.writerow([s["cls"], s["id"], s["name"], personal_code(s["id"])])
    return "﻿" + buf.getvalue()

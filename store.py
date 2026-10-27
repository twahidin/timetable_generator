"""Where things live: the committee's saved setup, generation runs and the published timetable, all under DATA_DIR
(a Railway volume, so they survive redeploys)."""
import csv, datetime, io, json, os, pickle, shutil, threading
from ttgen.export import model_from_files, export_all
from access import personal_code, norm

HERE = os.path.dirname(os.path.abspath(__file__))

def _data_dir():
    d = os.environ.get("DATA_DIR") or os.environ.get("RAILWAY_VOLUME_MOUNT_PATH") or os.path.join(HERE, "data")
    os.makedirs(d, exist_ok=True)
    return d

DATA = _data_dir()
PUB = os.path.join(DATA, "published")
RUNS = os.path.join(DATA, "runs")
os.makedirs(RUNS, exist_ok=True)
_lock = threading.Lock()

def now():
    return datetime.datetime.now().astimezone().strftime("%d %b %Y, %H:%M")

def on_volume():
    """False when running on Railway without a volume (everything is lost on the next deploy)"""
    return not (os.environ.get("RAILWAY_ENVIRONMENT") and not (os.environ.get("RAILWAY_VOLUME_MOUNT_PATH") or os.environ.get("DATA_DIR")))

def write_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f: json.dump(obj, f, ensure_ascii=False)
    os.replace(tmp, path)

def read_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as f: return json.load(f)
    except (OSError, ValueError): return default

def save_setup(spec):
    write_json(os.path.join(DATA, "setup.json"), dict(saved_at=now(), spec=spec))

def load_setup():
    x = read_json(os.path.join(DATA, "setup.json"))
    return (x["spec"], x.get("saved_at")) if x else (None, None)

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
            codes = {norm(personal_code(s["id"])): s["id"] for s in model["students"]}
            _cache.update(stamp=stamp, value=dict(meta=meta, model=model, codes=codes, views={}))
        return _cache["value"]

def publish(setup_xlsx, timetable_xlsx, run_id=None, log=print):
    """export everything into a fresh folder, then swap it in so viewers never see a half-written timetable"""
    tmp, old = PUB + ".new", PUB + ".old"
    shutil.rmtree(tmp, ignore_errors=True); os.makedirs(tmp)
    m = model_from_files(setup_xlsx, timetable_xlsx)
    log("Making the Excel workbook, the timetable finder and the PDFs...")
    out = export_all(m, tmp, log=lambda *a: None)
    shutil.copy(setup_xlsx, os.path.join(tmp, "setup.xlsx")); shutil.copy(timetable_xlsx, os.path.join(tmp, "timetable.xlsx"))
    shutil.rmtree(os.path.join(tmp, "PDF", "Classes"), ignore_errors=True)   # single PDFs are in the zip and made on demand
    for k in ("Teachers", "Rooms", "Students"): shutil.rmtree(os.path.join(tmp, "PDF", k), ignore_errors=True)
    with open(os.path.join(tmp, "model.pkl"), "wb") as f: pickle.dump(m, f)
    files = dict(excel=os.path.basename(out["excel"]), html=os.path.basename(out["html"]), zip=os.path.basename(out["pdf_zip"]),
                 books={os.path.basename(p).split(" - ")[0].lower(): os.path.relpath(p, tmp) for p in out["pdf_books"]})
    ch = m["checks"]
    write_json(os.path.join(tmp, "meta.json"), dict(published_at=now(), run=run_id, school=m["school"]["name"], timetable=m["school"]["timetable"],
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

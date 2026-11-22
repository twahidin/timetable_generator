"""Saved versions of the step 8 draft: named copies of the draft folder in DATA_DIR/draft_versions/<id>/, each with a version.json.
Saved by hand (kind "saved") or kept by the app before something replaces the draft ("upload", "open"; "refit" is for the re-fit).
Nothing here publishes anything. Every function takes draft._lock (an RLock), so a caller may already hold it."""
import os, re, secrets, shutil, sys, time
import store, draft

VDIR = os.path.join(store.DATA, "draft_versions")
AUTO_KEEP = 10      # versions of an automatic kind kept; the oldest is dropped when one more comes
MAX_SAVED = 30      # versions saved by hand
NAME_MAX = 80
KINDS = ("saved", "upload", "open", "refit")
_ID = re.compile(r"[0-9a-f]{12}\Z")
_JSON = "version.json"

def identity(meta):
    """[upload id, number of fixes, the newest fix's "at" or None]: two drafts with the same identity are the same draft"""
    fl = meta.get("fixes") or []
    return [meta.get("upload_id"), len(fl), (fl[-1].get("at") if fl else None)]

def _dir(vid): return os.path.join(VDIR, vid)
def _read(vid):
    """the version.json of a folder, or None when it is missing, not JSON, not an object, or has no kind or no identity list (such a folder is not a version)"""
    v = store.read_json(os.path.join(_dir(vid), _JSON), None)
    return v if isinstance(v, dict) and isinstance(v.get("kind"), str) and isinstance(v.get("identity"), list) and len(v["identity"]) == 3 else None

def _all():
    """every readable version's version.json (with its id taken from its folder), newest first"""
    vs = []
    for i in (os.listdir(VDIR) if os.path.isdir(VDIR) else []):
        v = _read(i) if _ID.match(i) else None
        if v: vs.append(dict(v, id=i))
    return sorted(vs, key=lambda v: v.get("t", 0), reverse=True)

def count(): return len(_all())

def _make(kind, by, name):
    if not draft.exists(): raise ValueError("There is no draft.")
    meta = store.read_json(draft._p("meta.json"), {}) or {}
    saved_at = store.now(); source = meta.get("source") or ""
    if name is None:
        name = ((os.path.splitext(source)[0] or "Draft") + " · " + " ".join(saved_at.split()[:2]))[:NAME_MAX]
    vid = secrets.token_hex(6); tmp = _dir(vid) + ".new"
    os.makedirs(VDIR, exist_ok=True); shutil.rmtree(tmp, ignore_errors=True)
    shutil.copytree(draft.DIR, tmp)
    v = dict(id=vid, name=name, kind=kind, saved_at=saved_at, by=by, source=source, identity=identity(meta), checked=None, t=time.time_ns())
    store.write_json(os.path.join(tmp, _JSON), v)
    os.replace(tmp, _dir(vid))
    return v

def _trim(protect=None):
    """drop the oldest versions of an automatic kind beyond AUTO_KEEP (never one saved by hand, never the protect one, which is being opened)"""
    auto = [v for v in _all() if v["kind"] != "saved"]
    for v in [v for v in reversed(auto) if v["id"] != protect][:max(0, len(auto) - AUTO_KEEP)]: shutil.rmtree(_dir(v["id"]), ignore_errors=True)

def keep(kind, by, name=None, protect=None):
    """copy the draft into a new version; None when there is no draft or a version of this very draft (same identity) exists.
    protect: the id of a version the trim must leave alone (open_version is about to copy it)"""
    if kind not in KINDS: raise ValueError("There is no such kind of version.")
    with draft._lock:
        if not draft.exists(): return None
        if identity(store.read_json(draft._p("meta.json"), {}) or {}) in [v["identity"] for v in _all()]: return None
        v = _make(kind, by, name); _trim(protect); return v

def save(name, by):
    """a version saved by hand"""
    name = (name or "").strip()
    if not name: raise ValueError("Give the version a name.")
    if len(name) > NAME_MAX: raise ValueError(f"A version name is at most {NAME_MAX} characters.")
    with draft._lock:
        if not draft.exists(): raise ValueError("There is no draft.")
        if sum(1 for v in _all() if v["kind"] == "saved") >= MAX_SAVED: raise ValueError(f"There are {MAX_SAVED} saved versions: delete one first.")
        return _make("saved", by, name)

def listing(rec=None, counts=True):
    """the versions, newest first: dict(id, name, kind, saved_at, by, source, fixes, critical, warnings). With counts=False no model is built and
    critical and warnings are None. Counts are kept in version.json with the setup version they were worked out against and redone when it changes.
    The lock is held to read the list and to write a cache, never while a model is built; a version that cannot be read has None counts and is reported on stderr."""
    with draft._lock: vs = _all()
    rec = (rec or store.setup_record()) if counts else rec
    out = []
    for v in vs:
        e = dict(id=v["id"], name=v.get("name"), kind=v["kind"], saved_at=v.get("saved_at"), by=v.get("by"), source=v.get("source"), fixes=v["identity"][1], critical=None, warnings=None)
        if counts:
            ck = v.get("checked")
            if not (isinstance(ck, dict) and ck.get("v") == rec["v"] and "critical" in ck and "warnings" in ck):
                try: ck = dict(v=rec["v"], **draft.checked_in(_dir(v["id"]), rec))
                except Exception as x:
                    print(f"versions: cannot count version {v['id']}: {type(x).__name__}: {x}", file=sys.stderr); ck = None
                if ck:
                    with draft._lock:
                        if os.path.isfile(os.path.join(_dir(v["id"]), _JSON)): store.write_json(os.path.join(_dir(v["id"]), _JSON), dict(_read(v["id"]) or v, checked=ck))   # not if it was deleted meanwhile
            if ck: e.update(critical=ck["critical"], warnings=ck["warnings"])
        out.append(e)
    return out

def folder(vid):
    """the folder of a version; ValueError unless vid is 12 lowercase hex characters and the folder is there"""
    if not isinstance(vid, str) or not _ID.match(vid) or _read(vid) is None: raise ValueError("There is no such version.")
    return _dir(vid)

def open_version(vid, by):
    """make a version the draft: the draft as it is now is kept first (kind "open"); returns dict(kept, opened)"""
    with draft._lock:
        src = folder(vid); opened = _read(vid)
        try:
            if not draft.model_in(src)[0]["lessons"]: raise ValueError("no lessons")
        except Exception: raise ValueError("That version cannot be opened: its files could not be read.")   # a version that does not read never replaces the draft, and nothing is kept
        kept = keep("open", by, protect=vid)
        new, old = draft.DIR + ".new", draft.DIR + ".old"
        shutil.rmtree(new, ignore_errors=True)
        shutil.copytree(src, new, ignore=shutil.ignore_patterns(_JSON))
        shutil.rmtree(old, ignore_errors=True)
        if os.path.exists(draft.DIR): os.replace(draft.DIR, old)
        os.replace(new, draft.DIR); shutil.rmtree(old, ignore_errors=True); draft._cache.clear()
        return dict(kept=kept, opened=opened)

def delete(vid):
    """remove a version; returns it"""
    with draft._lock:
        f = folder(vid); v = _read(vid); shutil.rmtree(f); return v

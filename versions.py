"""Saved versions of the step 8 draft: named copies of the draft folder in DATA_DIR/draft_versions/<id>/, each with a version.json.
Saved by hand (kind "saved") or kept by the app before something replaces the draft ("upload", "open"; "refit" is for the re-fit).
Nothing here publishes anything. Every function takes draft._lock (an RLock), so a caller may already hold it."""
import datetime, hashlib, json, os, re, secrets, shutil, sys, time
import store, draft

VDIR = os.path.join(store.DATA, "draft_versions")
AUTO_KEEP = 10      # versions of an automatic kind kept; the oldest is dropped when one more comes
MAX_SAVED = 30      # versions saved by hand
NAME_MAX = 80
KINDS = ("saved", "upload", "open", "refit")
_ID = re.compile(r"[0-9a-f]{12}\Z")
_JSON = "version.json"
CHECKS = max(os.stat(f).st_mtime_ns for f in (draft.__file__, draft.fixes.__file__, draft.helper.__file__, draft.verify.__file__, __file__))   # the newest of the modules the counts come from: a deploy that changes one has the counts worked out again

def identity(meta, decisions):
    """[upload id, number of fixes, a hash of the fixes and of the decisions ("left" is no decision)]: two drafts with the same identity are the same draft. Every field of
    every fix and decision is in the hash, so a draft that differs in anything is told apart (a copy too many is kept rather than one too few)"""
    fl = meta.get("fixes") or []
    live = {k: d for k, d in (decisions or {}).items() if not (isinstance(d, dict) and d.get("answer") == "left")}
    return [meta.get("upload_id"), len(fl), hashlib.sha1(json.dumps([fl, live], sort_keys=True).encode()).hexdigest()]

def _identity_in(folder):
    """the identity of a draft folder"""
    read = lambda f: store.read_json(os.path.join(folder, f), {}) or {}
    return identity(read("meta.json"), read("decisions.json"))

def when(text):
    """a time as store.now writes it ("22 Nov 2026, 13:12") as a person reads it ("22 Nov 2026, 1.12 pm"); any other text as it is, "" for none"""
    try: t = datetime.datetime.strptime(text, "%d %b %Y, %H:%M")
    except (TypeError, ValueError): return text if isinstance(text, str) else ""
    return f"{text.split(',')[0]}, {t.hour % 12 or 12}.{t.minute:02d} {'am' if t.hour < 12 else 'pm'}"

def label(v):
    """a version's name with its date and time, so two of one name are told apart"""
    name, at = v.get("name") or "Version", when(v.get("saved_at"))
    return f"{name} ({at})" if at else name

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
    os.makedirs(VDIR, exist_ok=True)
    try:
        shutil.copytree(draft.DIR, tmp)
        v = dict(id=vid, name=name, kind=kind, saved_at=saved_at, by=by, source=source, identity=_identity_in(tmp), checked=None, t=time.time_ns())   # of the copy itself, so it never says more than the copy holds
        store.write_json(os.path.join(tmp, _JSON), v)
        os.replace(tmp, _dir(vid))
    finally: shutil.rmtree(tmp, ignore_errors=True)   # nothing is left of a copy that failed
    return v

def _trim(*protect):
    """drop the oldest versions of an automatic kind beyond AUTO_KEEP (never one saved by hand, never one of protect: the one just kept, the one being opened)"""
    auto = [v for v in _all() if v["kind"] != "saved"]
    for v in [v for v in reversed(auto) if v["id"] not in protect][:max(0, len(auto) - AUTO_KEEP)]: shutil.rmtree(_dir(v["id"]), ignore_errors=True)

def keep(kind, by, name=None, protect=None):
    """copy the draft into a new version; None when there is no draft or a version of this very draft (same identity) exists.
    protect: the id of a version the trim must leave alone (open_version is about to copy it)"""
    if kind not in KINDS: raise ValueError("There is no such kind of version.")
    with draft._lock:
        if not draft.exists(): return None
        i = _identity_in(draft.DIR)
        if i[0] and i in [v["identity"] for v in _all()]: return None   # a draft with no upload id (kept from before uploads had one) cannot be told from another, so it is always kept
        v = _make(kind, by, name); _trim(v["id"], protect); return v

def save(name, by):
    """a version saved by hand"""
    name = " ".join(name.split()) if isinstance(name, str) else ""   # one line
    if not name: raise ValueError("Give the version a name.")
    if len(name) > NAME_MAX: raise ValueError(f"A version name is at most {NAME_MAX} characters.")
    with draft._lock:
        if not draft.exists(): raise ValueError("There is no draft.")
        if sum(1 for v in _all() if v["kind"] == "saved") >= MAX_SAVED: raise ValueError(f"There are {MAX_SAVED} saved versions: delete one first.")
        return _make("saved", by, name)

def listing(rec=None, counts=True):
    """the versions, newest first: dict(id, name, kind, saved_at, by, source, fixes, critical, warnings). With counts=False no model is built and
    critical and warnings are None. Counts are kept in version.json with the setup version they were worked out against and the checking code's age (CHECKS), and redone when either changes.
    The lock is held to read the list and to write a cache, never while a model is built; a version that cannot be read has None counts and is reported on stderr."""
    with draft._lock: vs = _all()
    rec = (rec or store.setup_record()) if counts else rec
    out = []
    for v in vs:
        e = dict(id=v["id"], name=v.get("name"), kind=v["kind"], saved_at=v.get("saved_at"), by=v.get("by"), source=v.get("source"), fixes=v["identity"][1], critical=None, warnings=None)
        if counts:
            ck = v.get("checked")
            if not (isinstance(ck, dict) and ck.get("v") == rec["v"] and ck.get("code") == CHECKS and "critical" in ck and "warnings" in ck):
                try: ck = dict(v=rec["v"], code=CHECKS, **draft.checked_in(_dir(v["id"]), rec))
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
        new = draft.DIR + ".new"
        shutil.rmtree(new, ignore_errors=True)
        try:
            shutil.copytree(src, new, ignore=shutil.ignore_patterns(_JSON))
            draft.swap_in(new)
        finally: shutil.rmtree(new, ignore_errors=True)   # nothing is left of a copy that failed
        return dict(kept=kept, opened=opened)

def delete(vid):
    """remove a version; returns it"""
    with draft._lock:
        f = folder(vid); v = _read(vid); shutil.rmtree(f); return v

"""Work files a teacher leaves for a relief teacher: DATA/relief/files/<absence id>/<file id><ext>. The original name lives in the record only."""
import os, re, secrets

import store

DIR = os.path.join(store.DATA, "relief", "files")
KINDS = (".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx", ".png", ".jpg", ".jpeg")
MAX = 10 * 1024 * 1024
PER_LESSON = 5
WRONG_KIND = "Send a PDF, Word, PowerPoint, Excel or picture file."
TOO_BIG = "A file can be at most 10 MB."


def fit(name, ext=None):
    """name with the extension ext (its own when None) in place of its own, at most 100 characters: the part before the
    extension is cut, never the extension"""
    base, own = os.path.splitext(name)
    ext = own if ext is None else ext
    return base[:100 - len(ext)] + ext if len(ext) < 100 else (base + ext)[:100]


def clean_name(name):
    """letters, digits, spaces and . - _ ( ) only; at most 100 characters, the extension kept"""
    name = os.path.basename(str(name or "").replace("\\", "/"))
    name = re.sub(r"[^\w .\-()]", "", name, flags=re.ASCII).strip()
    return fit(name) or "file"


def _folder(absence_id):
    absence_id = str(absence_id)
    if not absence_id.isalnum(): raise ValueError(WRONG_KIND)
    return os.path.join(DIR, absence_id)


def check(filename, size):
    """refuses a file by its name and its size in bytes (None: not known yet) -> its extension"""
    ext = os.path.splitext(str(filename or ""))[1].lower()
    if ext not in KINDS or size == 0: raise ValueError(WRONG_KIND)
    if size is not None and size > MAX: raise ValueError(TOO_BIG)
    return ext


def save(absence_id, filename, data) -> dict:
    if not isinstance(data, (bytes, bytearray)): raise ValueError(WRONG_KIND)
    ext = check(filename, len(data))
    folder = _folder(absence_id)
    file_id = secrets.token_hex(6)
    os.makedirs(folder, exist_ok=True)
    target = os.path.join(folder, file_id + ext)
    with open(target + ".tmp", "wb") as f: f.write(data)
    os.replace(target + ".tmp", target)
    return dict(id=file_id, name=clean_name(filename), size=len(data))


def path(absence_id, file_id):
    """where the file is stored, or None"""
    file_id = str(file_id)
    if not file_id.isalnum(): return None
    try: folder = _folder(absence_id)
    except ValueError: return None
    if not os.path.isdir(folder): return None
    for f in os.listdir(folder):
        if os.path.splitext(f)[0] == file_id and not f.endswith(".tmp"): return os.path.join(folder, f)
    return None


def delete(absence_id, file_id):
    p = path(absence_id, file_id)
    if p:
        try: os.remove(p)
        except OSError: pass

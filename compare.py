"""Compare two timetables of step 8: the draft, a saved version ("v:<id>") or the published one. Lessons are matched by what they are (the planned key of
step 5), never by lesson id, because two uploads number their lessons differently. Reads only: nothing here changes a draft, a version or the published
timetable, and no model it is given (the draft's cached one is shared) is modified. Periods are shown as the board numbers them: the model's own, from 0."""
import collections, io, os, shutil, tempfile
import openpyxl
import draft, fixes, helper, store, versions
from ttgen.database import write_db
from ttgen.export import model_from_files

NO_DRAFT = "There is no draft."
NO_PUB = "Nothing is published yet."
NO_VERSION = "There is no such version."
NO_NAME = "Pick a class, teacher or room on both timetables."
UNREADABLE = "The published timetable could not be read."
KINDS = ("time", "teacher", "room", "only_a", "only_b")

_counts_cache = {}   # published_counts: {key: (meta.json mtime, setup version), value}

def label(src):
    if src == "draft": return "The draft on step 8"
    if src == "published": return "Published timetable"
    if isinstance(src, str) and src.startswith("v:"):
        versions.folder(src[2:]); return versions._read(src[2:])["name"]
    raise ValueError("There is no such timetable.")

def _published_model(rec):
    pub = store.published()
    if not pub: raise ValueError(NO_PUB)
    work = tempfile.mkdtemp()
    try:
        try:
            path = os.path.join(work, "published.sqlite"); write_db(pub["model"], path, spec=rec["spec"])
            return model_from_files(None, path, spec=rec["spec"])
        except Exception: raise ValueError(UNREADABLE)
    finally: shutil.rmtree(work, ignore_errors=True)

def _load(src, rec):
    """(model, counts) of a source, checked against the setup record rec (default: the setup as it is now)"""
    rec = rec or store.setup_record()
    if not rec.get("spec"): raise LookupError("no setup")
    if src == "draft":
        if not draft.exists(): raise ValueError(NO_DRAFT)
        m = draft.model_now(rec)[0]; j = draft.info(rec=rec)
        return m, dict(critical=j["critical"], warnings=sum(1 for w in j["warnings"] if not w.get("decision") and not w.get("crit")))
    if src == "published":
        m = _published_model(rec); return m, draft.counts(m, rec)
    if isinstance(src, str) and src.startswith("v:"):
        f = versions.folder(src[2:]); m, rec, fx = draft.model_in(f, rec)
        return m, draft.counts(m, rec, fx, store.read_json(os.path.join(f, "decisions.json"), {}) or {})
    raise ValueError("There is no such timetable.")

def model_of(src, rec):
    """the timetable of a source with its fixes applied"""
    return _load(src, rec)[0]

def published_counts(rec=None):
    """dict(published_at, critical, warnings) of the published timetable against the current setup, or None when nothing is published"""
    pub = store.published()
    if not pub: return None
    rec = rec or store.setup_record()
    try: stamp = os.path.getmtime(os.path.join(store.PUB, "meta.json"))
    except OSError: stamp = None
    key = (stamp, rec["v"]); hit = _counts_cache.get("key") == key and _counts_cache.get("value")
    if hit: return dict(hit)
    at = (pub.get("meta") or {}).get("published_at")
    try: out = dict(published_at=at, **draft.counts(_published_model(rec), rec))
    except ValueError as e:
        if str(e) != UNREADABLE: raise
        out = dict(published_at=at, critical=None, warnings=None, error=UNREADABLE)
    _counts_cache.update(key=key, value=out); return dict(out)

def rows(m):
    """one dict per lesson row and planned key (a whole-class row taught to two classes gives two)"""
    out = []
    for x in m["lessons"]:
        for k in helper._keys_of(x):
            whole = k[0] == "C"
            out.append(dict(key=":".join(k), id=x["id"], d=x["d"], p=x["p"], n=x["n"], teachers=sorted(x["teachers"]), room=x["room"] or "", subject=x["subject"],
                            classes=[k[1]] if whole else list(x["classes"]), group=x["group"], block=x["block"], what=fixes.what(x)))
    return out

def pair(a, b):
    """per key: rows at the same (d, p) pair first, the rest pair in (d, p) order, leftovers with None. Deterministic."""
    sk = lambda r: (r["d"], r["p"], r["room"], r["id"] if isinstance(r["id"], (int, float)) else 0, str(r["id"]))
    ga, gb = collections.defaultdict(list), collections.defaultdict(list)
    for r in a: ga[r["key"]].append(r)
    for r in b: gb[r["key"]].append(r)
    out = []
    for k in sorted(set(ga) | set(gb)):
        A, B = sorted(ga.get(k, []), key=sk), sorted(gb.get(k, []), key=sk)
        done = []; ra, rb = [], []
        for at in sorted({(r["d"], r["p"]) for r in A} & {(r["d"], r["p"]) for r in B}):
            xa = [r for r in A if (r["d"], r["p"]) == at]; xb = [r for r in B if (r["d"], r["p"]) == at]
            done += list(zip(xa, xb)); ra += xa[:len(xb)]; rb += xb[:len(xa)]
        ia, ib = {id(r) for r in ra}, {id(r) for r in rb}
        resta = [r for r in A if id(r) not in ia]; restb = [r for r in B if id(r) not in ib]
        for i in range(max(len(resta), len(restb))):
            done.append((resta[i] if i < len(resta) else None, restb[i] if i < len(restb) else None))
        out += done
    return out

def _kinds(x, y):
    if x is None: return ["only_b"]
    if y is None: return ["only_a"]
    k = []
    if (x["d"], x["p"], x["n"]) != (y["d"], y["p"], y["n"]): k.append("time")   # a change of length is a change of time
    if x["teachers"] != y["teachers"]: k.append("teacher")
    if x["room"] != y["room"]: k.append("room")
    return k

def _longest(m):
    per = {(t, x["d"], x["id"]): x["n"] for x in m["lessons"] for t in x["teachers"]}
    day = collections.Counter()
    for (t, d, _), n in per.items(): day[(t, d)] += n
    return max(day.values(), default=0)

def diff(src_a, src_b, rec=None):
    rec = rec or store.setup_record()
    ma, ca = _load(src_a, rec); mb, cb = _load(src_b, rec)
    ra, rb = rows(ma), rows(mb)
    items = [dict(a=x, b=y, kinds=k) for x, y in pair(ra, rb) if (k := _kinds(x, y))]
    ids = lambda kind: len({i["b"]["id"] for i in items if kind in i["kinds"] and i["b"]})
    totals = dict(lessons=len({r["id"] for r in rb}), moved=len({i["b"]["id"] for i in items if i["a"] and i["b"] and (i["a"]["d"], i["a"]["p"]) != (i["b"]["d"], i["b"]["p"])}), teacher=ids("teacher"), room=ids("room"),
                  critical=[ca["critical"], cb["critical"]], warnings=[ca["warnings"], cb["warnings"]], longest=[_longest(ma), _longest(mb)])
    order = lambda key: list(dict.fromkeys([c["name"] for c in ma[key]] + [c["name"] for c in mb[key]]))
    rooms = sorted({r["room"] for r in ra + rb if r["room"]})
    return dict(totals=totals, items=items, names=dict(classes=order("classes"), teachers=order("teachers"), rooms=rooms), days=list(mb["days"]))

def line(item, days):
    a, b = item.get("a"), item.get("b")
    at = lambda r: f"{days[r['d']]} {r['p']}"
    per = lambda r: f" ({r['n']} period{'' if r['n'] == 1 else 's'})"
    if a is None: return f"{b['subject']}: only in B ({at(b)})"
    if b is None: return f"{a['subject']}: only in A ({at(a)})"
    parts = []
    if "time" in item["kinds"]: longer = a.get("n") != b.get("n"); parts.append(f"{at(a)}{per(a) if longer else ''} → {at(b)}{per(b) if longer else ''}")
    if "teacher" in item["kinds"]: parts.append("teacher " + (" & ".join(a["teachers"]) or "none") + " → " + (" & ".join(b["teachers"]) or "none"))
    if "room" in item["kinds"]: parts.append("room " + (a["room"] or "none") + " → " + (b["room"] or "none"))
    return f"{b['subject']}: " + ", ".join(parts)

def week(m, view, name):
    """one class's, teacher's or room's week -> dict(days, NP, times, cells)"""
    if view == "class": ok = name in m["class_ix"]
    elif view == "teacher": ok = name in m["teacher_ix"]
    elif view == "room": ok = any(x["room"] == name for x in m["lessons"]) and bool(name)
    else: ok = False
    if not ok: raise ValueError(NO_NAME)
    short = lambda s: (m["subjects"].get(s) or {}).get("short") or s
    mine = {"class": lambda r: name in r["classes"], "teacher": lambda r: name in r["teachers"], "room": lambda r: r["room"] == name}[view]
    cells = [dict(d=r["d"], p=r["p"], n=r["n"], short=short(r["subject"]), what=r["what"], teachers=r["teachers"], room=r["room"], block=r["block"], key=r["key"]) for r in rows(m) if mine(r)]
    return dict(days=list(m["days"]), NP=m["NP"], times=m["times"], cells=cells)

def xlsx(src_a, src_b, rec=None):
    """the differences as one sheet: Class, Lesson, A, B; one row per item per class of the row, classes in setup order"""
    d = diff(src_a, src_b, rec); days = d["days"]; rank = {c: i for i, c in enumerate(d["names"]["classes"])}
    text = lambda r: "" if r is None else ", ".join(x for x in (f"{days[r['d']]} {r['p']}", " & ".join(r["teachers"]), r["room"]) if x)
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Differences"; ws.append(["Class", "Lesson", "A", "B"])
    for i in d["items"]:
        r = i["b"] or i["a"]
        for c in sorted(r["classes"], key=lambda c: (rank.get(c, len(rank)), c)) or [""]: ws.append([c, r["what"], text(i["a"]), text(i["b"])])
    buf = io.BytesIO(); wb.save(buf); return buf.getvalue()

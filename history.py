"""The history: an append-only log of every change, one JSON line per entry, a file per month under DATA/history.
Setup changes, sign-ins and admin changes write here; the history page reads. Never records a password or code:
FORBIDDEN keys are dropped at any depth before an entry is written.

The row a setup entry is about is `row` (the entry's own `id` is its place in the log)."""
import copy
import datetime
import json
import os
import threading
import time

import store
import sync
from ttgen.spec import teacher_depts

DIR = os.path.join(store.DATA, "history")
KEEP_MONTHS = 24
FORBIDDEN = {"password", "pw", "code", "once", "token", "secret"}
WHERE = {"venues": "Step 1 · Venues", "classes": "Step 2 · Classes", "subjects": "Step 3 · Subjects",
         "teachers": "Step 4 · Teachers", "roles": "Step 4 · Teachers", "lessons": "Step 5 · Department map",
         "blocks": "Step 5 · Groups and bands", "rules": "Step 6 · Configuration & constraints",
         "students": "Students", "combinations": "Students", "choices": "Students"}
_SCHOOL_DAY = "School & day"
_NAME_FIELD = {"venues": "room", "classes": "class", "subjects": "subject", "teachers": "name", "blocks": "block",
               "roles": "role", "students": "name", "combinations": "code"}
_lock = threading.Lock()
_last = [0, -1]   # ms and counter of the last id given out


def by_of(who, via, shared=None):
    return {"who": who, "as": who or shared or "Unknown", "via": via}


def _clean(x):
    if isinstance(x, dict):
        return {k: _clean(v) for k, v in x.items() if k not in FORBIDDEN}
    if isinstance(x, list):
        return [_clean(v) for v in x]
    return x


def _new_id():
    ms = int(time.time() * 1000)
    if ms <= _last[0]:
        ms = _last[0]
        _last[1] += 1
        if _last[1] > 999:
            ms += 1
            _last[1] = 0
    else:
        _last[1] = 0
    _last[0] = ms
    return "h%013d%03d" % (ms, _last[1])


def _make(entry):
    e = _clean(entry)
    ts = e["ts"] if isinstance(e.get("ts"), (int, float)) else time.time()
    e["id"] = _new_id()
    e["ts"] = float(ts)
    e["at"] = datetime.datetime.fromtimestamp(ts).astimezone().isoformat(timespec="seconds")
    return e


def _write(entries):
    os.makedirs(DIR, exist_ok=True)
    by_file = {}
    for e in entries:
        by_file.setdefault(os.path.join(DIR, e["at"][:7] + ".jsonl"), []).append(e)
    for path, es in by_file.items():
        data = "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in es)
        with open(path, "ab+") as f:
            f.seek(0, os.SEEK_END)
            if f.tell():
                f.seek(-1, os.SEEK_END)
                if f.read(1) != b"\n":
                    data = "\n" + data
            f.write(data.encode("utf-8"))


def add_many(entries):
    with _lock:
        made = [_make(e) for e in entries]
        if made:
            _write(made)
        return made


def add(entry):
    return add_many([entry])[0]


def _files():
    try:
        names = [n for n in os.listdir(DIR) if len(n) == 13 and n.endswith(".jsonl") and n[:4].isdigit()]
    except OSError:
        return []
    return sorted(names, reverse=True)


def _lines(name):
    try:
        with open(os.path.join(DIR, name), encoding="utf-8", errors="replace") as f:
            return f.read().splitlines()
    except OSError:
        return []


def read(who=None, where=None, dept=None, kinds=None, since=None, until=None, signins=False, before=None, limit=200):
    out = []
    for name in _files():
        for line in reversed(_lines(name)):
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if not isinstance(e, dict) or not isinstance(e.get("id"), str):
                continue
            if before is not None and e["id"] >= before:
                continue
            if e.get("kind") == "signin" and not signins and not (kinds and "signin" in kinds):
                continue
            ts = e.get("ts") or 0
            if (who is not None and e.get("who") != who) or (where is not None and e.get("where") != where) \
                    or (kinds and e.get("kind") not in kinds) or (since is not None and ts < since) \
                    or (until is not None and ts > until) or (dept is not None and dept not in (e.get("depts") or [])):
                continue
            out.append(e)
            if len(out) >= limit:
                return out
    return out


def prune(today=None):
    today = today or datetime.date.today()
    oldest = today.year * 12 + today.month - KEEP_MONTHS
    gone = 0
    for name in _files():
        if int(name[:4]) * 12 + int(name[5:7]) < oldest:
            try:
                os.remove(os.path.join(DIR, name))
                gone += 1
            except OSError:
                pass
    return gone


def uses(days=7, **match):
    since = time.time() - days * 86400
    return sum(1 for e in read(since=since, signins=True, limit=10 ** 9)
               if all(e.get(k) == v for k, v in match.items()))


# ---------------------------------------------------------------------------------------------- setup changes in words
def _cut(s, n=80):
    return s if len(s) <= n else s[:n - 1] + "…"


def _show(v):
    if v is None:
        return "(none)"
    if isinstance(v, list):
        return _cut(", ".join(i if isinstance(i, str) else _show(i) for i in v) or "(none)")
    if isinstance(v, dict):
        return _cut(json.dumps(v, ensure_ascii=False))
    return _cut(str(v))


def row_label(section, row):
    if not isinstance(row, dict):
        return "(gone)"
    if section == "lessons":
        parts = [str(row.get("level") or "").strip(), str(row.get("subject") or "").strip(),
                 "".join(str(c) for c in row.get("classes") or [])]
        return " ".join(p for p in parts if p) or "(lesson)"
    if section == "rules":
        parts = [str(row.get("target") or "").strip(), str(row.get("rule") or row.get("text") or "").strip()]
        return _cut(" · ".join(p for p in parts if p) or "(rule)")
    if section == "choices":
        return _cut(str(row.get("student") or row.get("name") or row.get("kind") or "(choice)"))
    return str(row.get(_NAME_FIELD.get(section, "name")) or "").strip() or "(unnamed)"


def _depts(spec, section, row):
    """The departments a row belongs to: a lesson's by its subject, a band's by its lessons, a teacher's own."""
    if not isinstance(row, dict):
        return []
    if section == "lessons":
        d = sync.lesson_dept(spec, row)
        return [d] if d else []
    if section == "teachers":
        return teacher_depts(row)
    if section == "blocks":
        out = []
        for L in sync._rows(spec, "lessons"):
            if isinstance(L, dict) and L.get("block") == row.get("block"):
                d = sync.lesson_dept(spec, L)
                if d and d not in out:
                    out.append(d)
        return out
    return []


def _row_entry(work, op):
    """(entry, finish): what a row operation is about, judged on `work` before it applies; finish(entry) completes the
    entry once the operation has been applied to `work`."""
    name, section = op[0], op[1]
    rid = op[2].get("_id") if name == "add" and isinstance(op[2], dict) else op[2]
    field = op[3] if name in ("set", "merge") else None
    was_row = copy.deepcopy(None if name == "add" else sync._find(work, section, rid))
    d0 = _depts(work, section, was_row)
    was = was_row if name == "del" else (was_row.get(field) if was_row and field else None)

    def finish(e):
        r = sync._find(work, section, rid)
        lab = row_label(section, r if r is not None else was_row)
        e["label"] = lab
        e["depts"] = d0 + [d for d in _depts(work, section, r) if d not in d0]
        if name == "add":
            e["now"] = copy.deepcopy(r)
            e["text"] = f"Added {lab}"
        elif name == "del":
            e["now"] = None
            e["text"] = f"Deleted {lab}"
        else:
            e["now"] = copy.deepcopy(r.get(field)) if r else None
            if name == "set":
                e["text"] = _cut(f"{lab}: {field} {_show(e['was'])} → {_show(e['now'])}")
            else:
                e["text"] = _cut(f"{lab}: {field} + {_show(op[4])} − {_show(op[5])}")
    return dict(section=section, row=rid, field=field, was=copy.deepcopy(was), where=WHERE.get(section, "Setup")), finish


def _plain_entry(work, op):
    """(entry, finish) for school, day and top operations."""
    name = op[0]
    if name == "school":
        sec, field, label, now = "school", op[1], op[1], op[2]
        was = (work.get("school") or {}).get(op[1]) if isinstance(work.get("school"), dict) else None
    elif name == "day":
        days = work.get("day_structure") if isinstance(work.get("day_structure"), dict) else {}
        lv = days.get(op[1]) if isinstance(days.get(op[1]), dict) else {}
        sec, field, label, now, was = "day_structure", op[2], f"{op[1]} {op[2]}", op[3], lv.get(op[2])
    else:
        sec, field, label, now, was = "top", op[1], op[1], op[2], work.get(op[1])
    e = dict(section=sec, row=None, field=field, was=copy.deepcopy(was), now=copy.deepcopy(now), label=label, depts=[],
             where=_SCHOOL_DAY, text=_cut(f"{label}: {_show(was)} → {_show(now)}"))
    return e, None


def setup_entries(spec_before, ops, by, batch, v):
    """One kind-"setup" entry per operation, each judged on a working copy as the operations before it leave it."""
    work = copy.deepcopy(spec_before)
    out = []
    for op in ops:
        if not isinstance(op, list) or not op or not isinstance(op[0], str):
            continue
        try:
            if op[0] in ("set", "merge", "add", "del"):
                if op[1] not in sync.LISTS:
                    continue
                e, finish = _row_entry(work, op)
            elif op[0] in ("school", "day", "top"):
                e, finish = _plain_entry(work, op)
            else:
                continue
        except (IndexError, TypeError, AttributeError):
            continue
        sync.apply(work, [copy.deepcopy(op)])
        if finish:
            finish(e)
        out.append(dict(kind="setup", batch=batch, v=v, op=op[0], **by, **e))
    return out

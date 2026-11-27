"""The history: an append-only log of every change, one JSON line per entry, a file per month under DATA/history.
Setup changes, sign-ins and admin changes write here; the history page reads. Never records a password or code:
FORBIDDEN keys are dropped at any depth before an entry is written.

The row a setup entry is about is `row` (the entry's own `id` is its place in the log)."""
import copy
import datetime
import json
import math
import os
import re
import threading
import time

import store
import sync
from ttgen.spec import teacher_depts

DIR = os.path.join(store.DATA, "history")
KEEP_MONTHS = 24
FORBIDDEN = {"password", "pw", "code", "once", "token", "secret"}
WHERE = {"venues": "Step 1 · Venues", "classes": "Step 2 · Classes", "subjects": "Step 3 · Subjects",
         "teachers": "Step 4 · Teachers", "roles": "Step 4 · Teachers", "lessons": "Step 5 · Teacher Deployment Editor",
         "blocks": "Step 5 · Banding & TG Group Editor", "rules": "Step 6 · Configuration & constraints", "staff_periods": "Step 6 · Configuration & constraints",
         "students": "Students", "combinations": "Students", "choices": "Students"}
_SCHOOL_DAY = "School & day"
_NAME_FIELD = {"venues": "room", "classes": "class", "subjects": "subject", "teachers": "name", "blocks": "block",
               "roles": "role", "students": "name"}
_FIELD_WORDS = {"earlier_names": "Earlier names"}   # a field whose key is not a word on the page
def _word(field): return _FIELD_WORDS.get(field, field) if isinstance(field, str) else field
SCHOOL_TZ = datetime.timezone(datetime.timedelta(hours=8))   # school time, whatever the server's clock zone
_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
_DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
_lock = threading.Lock()
_last = [0, -1]   # ms and counter of the last id given out


def by_of(who, via, shared=None):
    """who an entry is by: a person's name, else the shared code's label, else "The app" for what the app does by
    itself, else "Unknown"
    """
    return {"who": who, "as": who or shared or ("The app" if via == "app" else "Unknown"), "via": via}


# the school's own setup rows keep their group `code` in these fields of these kinds (ruling R6)
_KEEP_KINDS = {"setup", "setup-refused", "app"}
_KEEP_FIELDS = {"was", "now", "op"}


def _clean(x):
    if isinstance(x, dict):
        return {k: _clean(v) for k, v in x.items() if k not in FORBIDDEN}
    if isinstance(x, list):
        return [_clean(v) for v in x]
    return x


def _clean_entry(entry):
    keep = entry.get("kind") in _KEEP_KINDS
    return {k: (copy.deepcopy(v) if keep and k in _KEEP_FIELDS else _clean(v))
            for k, v in entry.items() if k not in FORBIDDEN}


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
    e = _clean_entry(entry)
    ts = e["ts"] if isinstance(e.get("ts"), (int, float)) else time.time()
    e["id"] = _new_id()
    e["ts"] = float(ts)
    e["at"] = datetime.datetime.fromtimestamp(ts, SCHOOL_TZ).isoformat(timespec="seconds")
    return e


def ts_of(e):
    """an entry's time as a number of seconds, or None when its line has none that can be read (cut short, hand-edited)"""
    ts = e.get("ts") if isinstance(e, dict) else None
    return float(ts) if isinstance(ts, (int, float)) and not isinstance(ts, bool) and math.isfinite(ts) else None


def day_start(text):
    """the timestamp of 00:00 school time on a day written YYYY-MM-DD; None when it cannot be read"""
    try: return datetime.datetime.strptime(text, "%Y-%m-%d").replace(tzinfo=SCHOOL_TZ).timestamp()
    except (ValueError, TypeError): return None


def _clock(d):
    h = d.hour % 12 or 12
    return f"{d.day} {_MONTHS[d.month - 1]}, {h}:{d.minute:02d} {'am' if d.hour < 12 else 'pm'}"


def when_text(ts):
    """"Tuesday 18 Nov, 4:12 pm": school time"""
    d = datetime.datetime.fromtimestamp(ts, SCHOOL_TZ)
    return f"{_DAYS[d.weekday()]} {_clock(d)}"


def short_when(ts):
    """"19 Nov, 10:02 am": school time"""
    return _clock(datetime.datetime.fromtimestamp(ts, SCHOOL_TZ))


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
    for e in entries:
        if not isinstance(e, dict):
            raise TypeError("a history entry must be a dict")
    with _lock:
        made = [_make(e) for e in entries]
        if made:
            _write(made)
        return made


def add(entry):
    if not isinstance(entry, dict):
        raise TypeError("a history entry must be a dict")
    return add_many([entry])[0]


_MONTH_FILE = re.compile(r"^\d{4}-\d{2}\.jsonl$")
# the page's Where choices that are kinds of entry: entries written before they carried a `where` are found by their kind
_WHERE_KIND = {"Admin": "account", "Sign-in": "signin"}


def _files():
    try:
        names = [n for n in os.listdir(DIR) if _MONTH_FILE.match(n)]
    except OSError:
        return []
    return sorted(names, reverse=True)


def _lines(name):
    try:
        with open(os.path.join(DIR, name), encoding="utf-8", errors="replace") as f:
            return f.read().split("\n")     # not splitlines: a text may hold a line separator (U+2028, U+0085) of its own
    except OSError:
        return []


# files written before school time (stage 1) are named by the server's UTC clock, so the first hours of a school month (up to
# 08:00) are in the file before: nine hours of slack (UTC+08:00 is 8 hours away at most) so no entry at a month's edge is skipped
UTC_FILE_SLACK = 9 * 3600


def _month_end(name):
    """the first instant after the month a file holds, in school time"""
    y, m = int(name[:4]), int(name[5:7])
    y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return datetime.datetime(y, m, 1, tzinfo=SCHOOL_TZ).timestamp()


def read(who=None, where=None, dept=None, kinds=None, since=None, until=None, signins=False, before=None, limit=200,
         who_contains=None, allow=None, raw=None):
    """the entries, newest first, that match every filter given. where "Sign-in" shows the sign-ins without signins;
    where "Admin" or "Sign-in" also finds the account or sign-in entries that carry no `where`.
    allow(entry) -> bool is applied after every other filter (sign-ins too); month files wholly before `since` are not opened.
    raw: a piece of text that must be in the stored line (a name as the line holds it): the lines without it are not read further.
    A line whose ts is not a number counts as written at 0, one whose depts is not a list as of no department"""
    out = []
    needle = who_contains.strip().lower() if isinstance(who_contains, str) and who_contains.strip() else None
    where_kind = _WHERE_KIND.get(where)
    this_month = datetime.datetime.now(SCHOOL_TZ).strftime("%Y-%m") + ".jsonl"
    for name in _files():
        if since is not None and name != this_month and _month_end(name) + UTC_FILE_SLACK <= since:
            break   # newest first: every later file is older still
        for line in reversed(_lines(name)):
            if needle and needle not in line.lower():   # cheap: the name is in the raw line or the entry cannot match
                continue
            if raw is not None and raw not in line:
                continue
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if not isinstance(e, dict) or not isinstance(e.get("id"), str):
                continue
            if before is not None and e["id"] >= before:
                continue
            if needle and needle not in str(e.get("as") or "").lower():
                continue
            if e.get("kind") == "signin" and not signins and not (kinds and "signin" in kinds) and where_kind != "signin":
                continue
            ts = ts_of(e) or 0
            depts = e.get("depts") if isinstance(e.get("depts"), list) else []
            if where is not None and e.get("where") != where and not (where_kind and not e.get("where") and e.get("kind") == where_kind):
                continue
            if (who is not None and e.get("who") != who) \
                    or (kinds and (not isinstance(e.get("kind"), str) or e.get("kind") not in kinds)) or (since is not None and ts < since) \
                    or (until is not None and ts > until) or (dept is not None and dept not in depts):
                continue
            if allow is not None and not allow(e):
                continue
            out.append(e)
            if len(out) >= limit:
                return out
    return out


CHANGE_KINDS = ("setup", "setup-replaced", "draft", "relief", "exams", "account")   # not sign-ins, refusals or the app's follow-ups


def summary(since, allow, me, top=8):
    """what changed since `since` for the home page's "Since you last signed in": n (changes allow lets through), people
    (distinct names), rows [(who, where, count)] most first (who is "Your own changes" for `me`; at most `top`), more (rows
    left out) and published (the newest publish time, whatever allow says, or None). One read, so one month file for a recent `since`"""
    def is_publish(e): return e.get("kind") == "draft" and e.get("what") == "publish"
    ok = (lambda e: True) if allow is None else allow
    found = read(since=since, kinds=CHANGE_KINDS, allow=lambda e: is_publish(e) or bool(ok(e)), limit=10 ** 6)
    published, counts, people = None, {}, set()
    for e in found:
        ts = e.get("ts")
        if is_publish(e) and isinstance(ts, (int, float)) and (published is None or ts > published): published = float(ts)
        if not ok(e): continue
        name = str(e.get("as") or e.get("who") or "Someone")
        people.add(name)
        who = "Your own changes" if me is not None and e.get("who") == me else name
        key = (who, str(e.get("where") or ""))
        counts[key] = counts.get(key, 0) + 1
    rows = sorted(((w, wh, n) for (w, wh), n in counts.items()), key=lambda r: (-r[2], r[0], r[1]))
    return dict(n=sum(counts.values()), people=len(people), rows=rows[:top], more=max(0, len(rows) - top), published=published)


def find(entry_id):
    """the entry with this id (sign-ins too), or None. Ids grow in the order entries are written, so the newest files and
    lines are read first and the search stops once it reads an id older than the one it looks for"""
    if not isinstance(entry_id, str) or not entry_id:
        return None
    for name in _files():
        for line in reversed(_lines(name)):
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if not isinstance(e, dict) or not isinstance(e.get("id"), str):
                continue
            if e["id"] == entry_id:
                return e
            if e["id"] < entry_id:
                return None
    return None


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
    if section == "staff_periods":
        return str(row.get("name") or "").strip() or "a teacher-only period"
    if section == "combinations":   # a combination has a name and a code: the name, else the code
        return str(row.get("name") or row.get("code") or "").strip() or "(unnamed)"
    if section == "choices":   # kind setting (key), rule (its rule id) or recess (level)
        kind = str(row.get("kind") or "choice")
        what = row.get("key") or row.get("level") or row.get("rule_id") or ""
        return _cut(f"{kind} {what}".strip())
    return str(row.get(_NAME_FIELD.get(section, "name")) or "").strip() or "(unnamed)"


def _depts(spec, section, row):
    """The departments a row belongs to: a lesson's by its subject, a band's by its lessons, a teacher's and a subject's own."""
    if not isinstance(row, dict):
        return []
    if section == "subjects":
        d = str(row.get("dept") or "").strip()
        return [d] if d else []
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
    if name == "add" and not (isinstance(op[2], dict) and op[2].get("_id")):
        raise TypeError("an add needs a row with an _id")
    rid = op[2].get("_id") if name == "add" and isinstance(op[2], dict) else op[2]
    field = op[3] if name in ("set", "merge") else None
    was_row = copy.deepcopy(None if name == "add" else sync._find(work, section, rid))
    d0 = _depts(work, section, was_row)
    was = was_row if name == "del" else (was_row.get(field) if was_row and field else None)
    extra = {}
    if name == "del":   # the row before it, so a put back can set it where it was ("" when it was first)
        rows = sync._rows(work, section)
        i = next((n for n, r in enumerate(rows) if isinstance(r, dict) and r.get("_id") == rid), None)
        if i is not None:
            extra["after"] = (rows[i - 1].get("_id") or "") if i and isinstance(rows[i - 1], dict) else ""

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
                e["text"] = _cut(f"{lab}: {_word(field)} {_show(e['was'])} → {_show(e['now'])}")
            else:
                e["text"] = _cut(f"{lab}: {_word(field)} + {_show(op[4])} − {_show(op[5])}")
    return dict(section=section, row=rid, field=field, was=copy.deepcopy(was), where=WHERE.get(section, "Setup"), **extra), finish


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
    if name == "day":
        e["level"] = op[1]
    return e, None


def setup_entries(spec_before, ops, by, batch, v):
    """One kind-"setup" entry per operation that changed something, each judged on a working copy as the operations
    before it leave it. An operation apply skips (a row added that is there already, one deleted that is gone, a field no
    one may set) and a value set to what it was give no entry: a save the page sends again records nothing new."""
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
            if sync.apply(work, [copy.deepcopy(op)]):
                continue
            if finish:
                finish(e)
            if op[0] not in ("add", "del") and sync._canon(e["was"]) == sync._canon(e["now"]):
                continue
            out.append(dict(kind="setup", batch=batch, v=v, op=op[0], **by, **e))
        except Exception as x:   # a malformed operation gives no entry, said in one line; the save path must never fail here
            store._warn(x)
            continue
    return out


def refused_about(spec, op):
    """label, depts, text and where of an operation that was refused, judged on the setup as it was (it was never
    applied): the row it named, and the departments of that row both as it is and as the operation would leave it, so
    the page names the row and the department filter finds it"""
    try:
        name = op[0]
        if name in ("set", "merge", "add", "del") and isinstance(op[1], str) and op[1] in sync.LISTS:
            section = op[1]
            row = op[2] if name == "add" else sync._find(spec, section, op[2])
            lab = row_label(section, row)
            depts = _depts(spec, section, row)
            if name == "set" and isinstance(row, dict) and isinstance(op[3], str):
                after = dict(row)
                after[op[3]] = op[4]
                depts += [d for d in _depts(spec, section, after) if d not in depts]
            if name == "add":
                text = f"Add {lab}"
            elif name == "del":
                text = f"Delete {lab}"
            elif name == "set":
                text = f"{lab}: {_word(op[3])} → {_show(op[4])}"
            else:
                text = f"{lab}: {_word(op[3])} + {_show(op[4])} − {_show(op[5])}"
            return dict(label=lab, depts=depts, text=_cut("Refused: " + text), where=WHERE.get(section, "Setup"))
        if name in ("school", "day", "top"):
            e, _ = _plain_entry(spec, op)
            return dict(label=e["label"], depts=[], text=_cut("Refused: " + e["text"]), where=_SCHOOL_DAY)
    except Exception as x:   # a malformed operation: the refusal is still recorded, with what is known
        store._warn(x)
    return dict(label=None, depts=[], text="Refused", where="Setup")

"""Fixes to the draft: each is one change the committee made to the timetable they uploaded, kept as a small record and
applied again, in order, to the lessons read from the file. Nothing here touches files or the setup."""
import collections, copy
from ttgen.export import ENTIRE, _split_list
from ttgen import verify

KINDS = ("move", "swap", "teacher", "room", "add", "delete")

def what(x):
    """a lesson row in words: '{subject} for {class}' for an entire-class lesson, 'group {code}' otherwise"""
    return f"{x['subject']} for {', '.join(x['classes'])}" if x["group"] == ENTIRE else f"group {x['group']}"

def when(days, d, p): return f"{days[d]} period {p}"

def _rows(lessons, i):
    rows = [x for x in lessons if x["id"] == i]
    if not rows: raise ValueError("There is no lesson with that id on the timetable.")
    return rows

def _key(s):
    """'C:{class}:{subject}' or 'G:{code}' -> the key verify.planned_rows uses"""
    k = tuple(s.split(":", 2)) if isinstance(s, str) and s.startswith("C:") else tuple(s.split(":", 1)) if isinstance(s, str) and s.startswith("G:") else ()
    if len(k) != (3 if k[:1] == ("C",) else 2) or not all(k): raise ValueError("That is not a lesson of step 5.")
    return k

def _names(names): return ", ".join(names) if names else "nobody"

def _slot(spec, days, d, p, n):
    """the lesson, n periods long from period p on day d, must be inside the day"""
    if not all(isinstance(v, int) and not isinstance(v, bool) for v in (d, p, n)) or not 0 <= d < len(days) or p < 0 or n < 1 or p + n > int(spec["school"]["periods_per_day"]): raise ValueError("That is outside the day.")

def apply_one(lessons, fix, spec, days, new_id=None, touched=None):
    """change lessons (a list the caller owns) in place and return the sentence for the committee; ValueError(sentence) when the
    fix cannot apply (every kind checks before it changes anything). new_id: the id an add takes (default 1 + the highest in
    lessons); touched: a set the ids of lessons changed or added are put into."""
    if not isinstance(fix, dict): raise ValueError("it is not complete.")
    kind = fix.get("kind"); touched = set() if touched is None else touched
    if kind == "move":
        rows = _rows(lessons, fix["id"]); _slot(spec, days, fix["d"], fix["p"], rows[0]["n"]); a = rows[0]; text = f"Moved {what(a)} from {when(days, a['d'], a['p'])} to {when(days, fix['d'], fix['p'])}."
        for x in rows: x["d"], x["p"] = fix["d"], fix["p"]
        touched.add(fix["id"]); return text
    if kind == "swap":
        ra, rb = _rows(lessons, fix["a"]), _rows(lessons, fix["b"]); a, b = ra[0], rb[0]
        if a["n"] != b["n"]: raise ValueError(f"{what(a)} and {what(b)} are not the same length, so they cannot swap places.")
        text = f"Swapped {what(a)} ({when(days, a['d'], a['p'])}) with {what(b)} ({when(days, b['d'], b['p'])})."
        (da, pa), (db, pb) = (a["d"], a["p"]), (b["d"], b["p"])
        for x in ra: x["d"], x["p"] = db, pb
        for x in rb: x["d"], x["p"] = da, pa
        touched |= {fix["a"], fix["b"]}; return text
    if kind == "teacher":
        key = _key(fix["key"]); name = verify._name(key); known = {x["name"] for x in spec.get("teachers") or []}
        rows = [x for x in lessons if (x["group"] == ENTIRE and key[0] == "C" and key[1] in x["classes"] and x["subject"] == key[2]) or (key[0] == "G" and x["group"] == key[1])]
        if not rows: raise ValueError(f"There is no lesson of {name} on the timetable.")
        bad = [x for x in fix["teachers"] if x not in known]
        if bad: raise ValueError(f"{', '.join(bad)} {'is' if len(bad) == 1 else 'are'} not on the setup's list of teachers.")
        old = list(dict.fromkeys(t for x in rows for t in x["teachers"]))
        for x in rows: x["teachers"] = list(fix["teachers"])
        touched |= {x["id"] for x in rows}
        return f"{name} is now taught by {_names(fix['teachers'])}, not {_names(old)}."
    if kind == "room":
        x = next((x for x in _rows(lessons, fix["id"]) if x["group"] == fix["group"]), None)
        if x is None: raise ValueError(f"There is no row of {fix['group']} in that lesson.")
        if fix["room"] and fix["room"] not in {v["room"] for v in spec.get("venues") or []}: raise ValueError(f"{fix['room']} is not on the setup's list of rooms.")
        text = f"{what(x)} on {when(days, x['d'], x['p'])} is now in {fix['room'] or 'no room'}, not {x['room'] or 'no room'}."
        x["room"] = fix["room"]; touched.add(x["id"])
        return text
    if kind == "add":
        key = _key(fix["key"]); e = verify.planned_rows(spec).get(key)
        if not e: raise ValueError(f"Step 5 has no lesson for {verify._name(key) if len(key) in (2, 3) else fix['key']}.")
        _slot(spec, days, fix["d"], fix["p"], fix["n"])
        if fix["room"] and fix["room"] not in {v["room"] for v in spec.get("venues") or []}: raise ValueError(f"{fix['room']} is not on the setup's list of rooms.")
        x = dict(id=new_id if new_id is not None else 1 + max([y["id"] for y in lessons], default=0), d=fix["d"], p=fix["p"], n=fix["n"], level=e["level"] or "", block=str(e["rows"][0].get("block") or ""),
                 classes=list(e["classes"]), subject=e["subject"], group=ENTIRE if key[0] == "C" else key[1],
                 teachers=list(dict.fromkeys(t for r in e["rows"] for t in r.get("teachers") or [])), room=fix["room"], ext=False, rain="")
        lessons.append(x); touched.add(x["id"])
        return f"Added {what(x)} on {when(days, x['d'], x['p'])} ({x['n']} periods) {'in ' + x['room'] if x['room'] else 'with no room'}."
    if kind == "delete":
        rows = [x for x in _rows(lessons, fix["id"]) if fix.get("group") is None or x["group"] == fix["group"]]
        if not rows: raise ValueError(f"There is no row of {fix['group']} in that lesson.")
        a = rows[0]; text = f"Deleted {what(a)} on {when(days, a['d'], a['p'])}."
        lessons[:] = [x for x in lessons if not any(x is r for r in rows)]
        if not any(x["id"] == fix["id"] for x in lessons): touched.discard(fix["id"])
        return text
    raise ValueError("This kind of fix is not known.")

def apply(lessons, fixes, spec, days):
    """a copy of lessons with every fix applied in order -> dict(lessons, texts, problems, touched). A fix that cannot apply
    (the file or the setup changed since, or it is malformed) is skipped and named in problems; touched is the ids of lessons
    a fix changed or added. An add takes 1 + the highest id as read from the file, plus one per add before it."""
    L, texts, problems, touched = copy.deepcopy(lessons), [], [], set()
    nxt = 1 + max([x["id"] for x in L], default=0)
    for f in fixes:
        try: texts.append(apply_one(L, f, spec, days, new_id=nxt, touched=touched))
        except Exception as e: problems.append(f"A fix could not be applied: {e if isinstance(e, ValueError) else 'it is not complete.'}"); continue
        if isinstance(f, dict) and f.get("kind") == "add": nxt += 1
    return dict(lessons=L, texts=texts, problems=problems, touched=touched)

def editor(fixes, out):
    """the edit function for model_from_files: applies the fixes to the lessons read from the file and leaves texts, problems and touched in out"""
    def edit(lessons, spec, days):
        r = apply(lessons, fixes, spec, days); out.update(texts=r["texts"], problems=r["problems"], touched=r["touched"]); return r["lessons"]
    return edit


# ----------------------------------------------------------------------------------------------- judging a fix
def _span(x): return range(x["p"], x["p"] + x["n"])
def _no_room(r): return not r or r == "TBC"
def _classes(rows): return list(dict.fromkeys(c for x in rows for c in x["classes"]))
def _block(rows): return len(rows) > 1 or any(x["block"] for x in rows)

class Busy:
    """who and what is in use in each period, built once per request: teachers, classes, whole-class lessons, groups,
    rooms and rain rooms by (kind, name, day, period), each lesson's rows by id, and which groups share students"""
    def __init__(self, m, lessons=None, base=None):
        self.m, self.at, self.ids, self.by = m, collections.defaultdict(list), collections.defaultdict(list), collections.defaultdict(set)
        for x in m["lessons"] if lessons is None else lessons:
            self.ids[x["id"]].append(x); dept = m["subjects"].get(x["subject"], {}).get("dept")
            for k in [("t", t) for t in x["teachers"]] + [("c", c) for c in x["classes"]] + [("s", x["subject"])] + ([("dept", dept)] if dept else []) + ([("g", x["group"])] if x["group"] != ENTIRE else []):
                self.by[k].add(x["id"])
            for q in _span(x):
                for t in x["teachers"]: self.at["t", t, x["d"], q].append(x)
                for c in x["classes"]:
                    self.at["c", c, x["d"], q].append(x)
                    if x["group"] == ENTIRE: self.at["w", c, x["d"], q].append(x)
                if x["group"] != ENTIRE: self.at["g", x["group"], x["d"], q].append(x)
                if not _no_room(x["room"]): self.at["r", x["room"], x["d"], q].append(x)
                for h in _split_list(x.get("rain")):
                    if h != "TBC": self.at["h", h, x["d"], q].append(x)
        if base: self.share, self.gcls, self.cgroups = base.share, base.gcls, base.cgroups; return
        self.share, self.gcls, self.cgroups = (collections.defaultdict(collections.Counter) for _ in range(3))   # group -> {group: students in both}; group -> {class: its students}; class -> {group: its students}
        for st in m["students"]:
            gs = list(dict.fromkeys(st["groups"]))
            for g in gs:
                self.gcls[g][st["cls"]] += 1; self.cgroups[st["cls"]][g] += 1
                for g2 in gs:
                    if g2 != g: self.share[g][g2] += 1

    def _first(self, key, ignore): return next((y for y in self.at.get(key, ()) if y["id"] not in ignore), None)

    def clash(self, rows, d, p, n, ignore=()):
        """the first reason these rows cannot be in periods p .. p+n-1 of day d, the lessons with ids in ignore set aside, or None"""
        ignore, Q, f = set(ignore), range(p, p + n), self._first
        for x in rows:
            for t in x["teachers"]:
                for q in Q:
                    if y := f(("t", t, d, q), ignore): return f"{t} is teaching {what(y)} then."
        for x in rows:
            for c in x["classes"]:
                for q in Q:
                    if y := f(("c" if x["group"] == ENTIRE else "w", c, d, q), ignore): return f"{c} has {what(y)} then."
        for x in rows:
            pairs = [(c, g, k) for c in x["classes"] for g, k in self.cgroups.get(c, {}).items()] if x["group"] == ENTIRE else \
                [(x["group"], g, k) for g, k in self.share.get(x["group"], {}).items()]
            for q in Q:
                for who, g, k in pairs:
                    if y := f(("g", g, d, q), ignore): return f"{k} students of {who} have {what(y)} then."
                if x["group"] != ENTIRE:
                    for c, k in self.gcls.get(x["group"], {}).items():
                        if y := f(("w", c, d, q), ignore): return f"{k} students of {x['group']} have {what(y)} then."
        mine = collections.Counter(x["room"] for x in rows if not _no_room(x["room"]))
        for room, k in mine.items():
            for q in Q:
                if sum(y["id"] not in ignore for y in self.at.get(("r", room, d, q), ())) + k > self.m["room_cap"].get(room, 1) or f(("h", room, d, q), ignore): return f"{room} is in use then."
        for x in rows:
            for h in _split_list(x.get("rain")):
                if h != "TBC" and (h in mine or any(f(("r", h, d, q), ignore) for q in Q)): return f"{h} is in use then."
        return None

    def lesson_time(self, rows, d, p, n):
        """'That is not lesson time for {class}.' when a period is not L or A for a class of the rows (its level's day and its
        own recess), or the lesson runs past the day; else None"""
        m = self.m; k = m["keep"].get(m["days"][d]) if 0 <= d < len(m["days"]) else None
        for x in rows:
            for c in x["classes"] or [""]:
                levels = {lv for lv in (x["level"], m["class_ix"].get(c, {}).get("level")) if lv in m["grid"]}
                if not 0 <= d < len(m["days"]) or p < 0 or p + n > m["NP"] or (k is not None and p + n > k) \
                        or any(m["grid"][lv][d][q] not in "LA" for lv in levels for q in range(p, p + n)) \
                        or (c in m["cgrid"] and any(m["cgrid"][c][d][q] == "R" for q in range(p, p + n))):
                    return f"That is not lesson time for {c or x['level'] or what(x)}."
        return None

def _near(b, rows):
    """the ids of the lessons sharing a teacher, a class, the subject, the subject's department or the group code with any of rows"""
    out = {x["id"] for x in rows}
    for x in rows:
        dept = b.m["subjects"].get(x["subject"], {}).get("dept")
        for k in [("t", t) for t in x["teachers"]] + [("c", c) for c in x["classes"]] + [("s", x["subject"])] + ([("dept", dept)] if dept else []) + ([("g", x["group"])] if x["group"] != ENTIRE else []):
            out |= b.by.get(k, set())
    return out

def neighbours(m, ids, busy=None):
    """the lessons that can interact with the lessons of those ids under any rule (themselves included): every lesson sharing a
    teacher, a class, the subject, the subject's department or the group code with one of them"""
    b = busy or Busy(m); near = _near(b, [x for i in ids for x in b.ids.get(i, ())])
    return [x for x in m["lessons"] if x["id"] in near]

def _rule_ws(m, spec, lessons): return verify.rules(dict(m, lessons=lessons), spec)[0]
def _count(ws): return collections.Counter((w["key"].split(":", 2)[1], w["strength"]) for w in ws)

def rule_counts(m, spec, lessons):
    """{(rule id, strength): warnings} from the standard rules on these lessons only"""
    return _count(_rule_ws(m, spec, lessons))

def _bears(m, spec, r, x):
    """whether rule row r can see lesson row x at all, wherever it sits: a change to lessons it cannot see leaves its warnings as they were"""
    rule, sc, tg = r.get("rule"), r.get("scope"), r.get("target")
    if rule == "Keep free together": return any(m["teacher_ix"].get(t, {}).get("dept") == tg for t in x["teachers"]) or any(m["class_ix"].get(c, {}).get("level") == tg for c in x["classes"])
    if rule == "Not on the same day as":
        dept = m["subjects"].get(x["subject"], {}).get("dept"); return verify.subject_test(tg)(x["subject"], dept) or verify.subject_test(r.get("subject"))(x["subject"], dept)
    if rule in ("At least one recess a day", "Max periods in a row"): return sc != "Teacher" or tg in x["teachers"]
    if rule == "Once a day per group": return True   # it counts every lesson of a group to know how often it may meet
    test = verify.in_scope(m, spec, r); return test is None or test(x)

WIDE = ("At most N at once", "Same time across classes")   # rules that compare lessons of different classes and teachers at once

def _ctx(m, ctx=None):
    if ctx is not None and ctx.get("m") is m: return ctx
    b = Busy(m); load = collections.Counter()
    for i, rows in b.ids.items():
        for t in {t for x in rows for t in x["teachers"]}: load[t] += rows[0]["n"]
    return dict(m=m, busy=b, memo={}, load=load, next_id=1 + max(b.ids, default=0), placed={k: v["periods"] for k, v in verify.placed(m).items()})

def _keys(rows):
    """{key: periods} the rows add to the counts of step 3 (a lesson id once per key)"""
    out, seen = collections.Counter(), set()
    for x in rows:
        for k in ([("C", c, x["subject"]) for c in x["classes"]] if x["group"] == ENTIRE else [("G", x["group"])]):
            if (x["id"], k) not in seen: seen.add((x["id"], k)); out[k] += x["n"]
    return out

def _allowance(v):
    try: return float(str(v))
    except ValueError: return None

def judge(m, spec, days, fix, ctx=None):
    """how a fix would leave the timetable -> dict(state, why, must, prefer): "na" it cannot go there, "no" a clash, a period
    count away from the plan or a Must rule broken anew, "prefer" only a Prefer rule or a teacher's allowance gives, else "ok".
    ctx: the shared index of one request (slots and the option lists pass it)"""
    c = _ctx(m, ctx); b = c["busy"]
    res = lambda state, why="", must=(), prefer=(): dict(state=state, why=why, must=list(must), prefer=list(prefer))
    if not isinstance(fix, dict): return res("na", "That fix is not complete.")
    kind = fix.get("kind")
    try:
        if kind == "teacher":
            key = _key(fix["key"]); ids = {x["id"] for x in m["lessons"] if (x["group"] == ENTIRE and key[0] == "C" and key[1] in x["classes"] and x["subject"] == key[2]) or (key[0] == "G" and x["group"] == key[1])}
        else: ids = {fix[k] for k in {"swap": ("a", "b")}.get(kind, ("id",) if kind in ("move", "room", "delete") else ())}
        old = [x for i in ids for x in b.ids.get(i, ())]; new = [dict(x, teachers=list(x["teachers"]), classes=list(x["classes"])) for x in old]
        apply_one(new, fix, spec, days, new_id=c["next_id"])
    except ValueError as e: return res("na", str(e))
    except (KeyError, TypeError): return res("na", "That fix is not complete.")
    if kind == "swap":
        ra, rb = b.ids[fix["a"]], b.ids[fix["b"]]
        if set(_classes(ra)) != set(_classes(rb)) and (_block(ra) or _block(rb)): return res("na", "A block lesson can only swap with a lesson of the same classes.")
    before, after = collections.defaultdict(list), collections.defaultdict(list)
    for x in old: before[x["id"]].append(x)
    for x in new: after[x["id"]].append(x)
    changed = set(before) | set(after)
    moved = {i for i, r in after.items() if i not in before or (r[0]["d"], r[0]["p"]) != (before[i][0]["d"], before[i][0]["p"])}
    for i in moved:
        x = after[i][0]
        if why := b.lesson_time(after[i], x["d"], x["p"], x["n"]): return res("na", why)
    if kind != "delete":
        for i, rows in after.items():
            if i in moved: cand = rows
            else:   # in place: only a teacher who was not there and a room that changed can clash
                had = {t for y in before[i] for t in y["teachers"]}; rooms = {y["room"] for y, z in zip(rows, before[i]) if y["room"] != z["room"]}
                cand = [dict(y, teachers=[t for t in y["teachers"] if t not in had], classes=[], group=ENTIRE, rain="", room=y["room"] if y["room"] in rooms else "") for y in rows]
            x = rows[0]; why = b.clash(cand, x["d"], x["p"], x["n"], ignore=changed)
            if not why and len(after) > 1: why = Busy(m, [y for j, r in after.items() if j != i for y in r], base=b).clash(cand, x["d"], x["p"], x["n"])
            if why: return res("no", why)
    if kind in ("add", "delete"):
        ko, kn = _keys(old), _keys(new)
        for k in sorted(set(ko) | set(kn)):
            was = c["placed"].get(k, 0); now, want = was - ko[k] + kn[k], m["planned"].get(k, 0)
            if now != was and not (was < now <= want or want <= now < was): return res("no", f"That would leave {verify._name(k)} with {now} periods; step 3 plans {want}.")
    rules = spec.get("rules") or []; seen = old + new
    keep = tuple(i for i, r in enumerate(rules) if r.get("rule") != "In words" and any(_bears(m, spec, r, x) for x in seen))
    near = _near(b, old) | _near(b, new)
    for i in keep:
        if rules[i].get("rule") in WIDE and (test := verify.in_scope(m, spec, rules[i])):
            near |= c["memo"].setdefault(("wide", id(spec), i), {x["id"] for x in m["lessons"] if test(x)})
    must, prefer = [], []
    if keep:
        sp = dict(spec, rules=[r if i in keep else {"rule": "In words"} for i, r in enumerate(rules)])
        mk = (id(spec), keep, frozenset(near))
        if mk not in c["memo"]:
            L0 = [x for x in m["lessons"] if x["id"] in near]; c["memo"][mk] = (L0, _rule_ws(m, sp, L0))
        L0, w0 = c["memo"][mk]; w1 = _rule_ws(m, sp, [x for x in L0 if x["id"] not in changed] + new)
        c0, c1, texts = _count(w0), _count(w1), {w["text"] for w in w0}
        for k in [k for k in c1 if c1[k] > c0.get(k, 0)]:
            ws = [w for w in w1 if (w["key"].split(":", 2)[1], w["strength"]) == k]
            (must if k[1] == "Must" else prefer).extend([w["text"] for w in ws if w["text"] not in texts] or [ws[0]["text"]])
    if kind in ("teacher", "add", "delete"):
        for t in sorted({t for x in seen for t in x["teachers"]}):
            has = lambda rows: sum(r[0]["n"] for r in rows.values() if any(t in y["teachers"] for y in r))
            was = c["load"][t]; now = was - has(before) + has(after); cap = _allowance(m["teacher_ix"].get(t, {}).get("allowance"))
            if cap is not None and now > cap and now > was: prefer.append(f"{t} would have {now} periods, {now - cap:g} over the allowance.")
    if must: return res("no", must[0], must, prefer)
    if prefer: return res("prefer", prefer[0], must, prefer)
    return res("ok")

def _pick(j, *keys): return {k: j[k] for k in ("state", "why") + keys}

def slots(m, spec, days, lesson_id):
    """every (d, p) of the week(s) but the lesson's own, judged: an empty stretch of its classes as a move, a stretch where
    exactly one other lesson of the same length starts as a swap, anything else occupied "na" -> [dict(d, p, state, why, swap, also)]"""
    c = _ctx(m); b = c["busy"]; rows = _rows(m["lessons"], lesson_id); a = rows[0]; n, cls = a["n"], _classes(rows); out = []
    for d in range(len(days)):
        for p in range(m["NP"]):
            if (d, p) == (a["d"], a["p"]): continue
            there = {y["id"]: y for k in cls for q in range(p, min(p + n, m["NP"])) for y in b.at.get(("c", k, d, q), ()) if y["id"] != lesson_id}
            if not there:
                out.append(dict(d=d, p=p, **_pick(judge(m, spec, days, dict(kind="move", id=lesson_id, d=d, p=p), c)), swap=None, also=[])); continue
            y = next(iter(there.values()))
            if len(there) == 1 and (y["d"], y["p"], y["n"]) == (d, p, n):
                also = [f"This also moves {what(y)} to {when(days, a['d'], a['p'])}."] if set(_classes(b.ids[y["id"]])) != set(cls) else []
                out.append(dict(d=d, p=p, **_pick(judge(m, spec, days, dict(kind="swap", a=lesson_id, b=y["id"]), c)), swap=y["id"], also=also))
            else: out.append(dict(d=d, p=p, state="na", why="Another lesson is there.", swap=None, also=[]))
    return out

def teacher_options(m, spec, days, key):
    """each teacher whose can_teach names the key's subject, and step 5's teachers of the key, judged as a teacher fix (the
    current teachers left out) -> [dict(teachers, state, why)]"""
    k = _key(key); e = verify.planned_rows(spec).get(k); c = _ctx(m)
    rows = [x for x in m["lessons"] if (x["group"] == ENTIRE and k[0] == "C" and k[1] in x["classes"] and x["subject"] == k[2]) or (k[0] == "G" and x["group"] == k[1])]
    subject = e["subject"] if e else k[2] if k[0] == "C" else rows[0]["subject"] if rows else ""
    now = {t for x in rows for t in x["teachers"]}
    names = lambda v: [str(x.get("subject") if isinstance(x, dict) else x) for x in v] if isinstance(v, list) else verify.names_list(v)
    opts = ([sorted(e["teachers"])] if e and e["teachers"] else []) + [[t["name"]] for t in spec.get("teachers") or [] if subject in names(t.get("can_teach"))]
    opts = [o for o in dict.fromkeys(map(tuple, opts)) if set(o) != now and not (len(o) == 1 and o[0] in now)]
    return [dict(teachers=list(o), **_pick(judge(m, spec, days, dict(kind="teacher", key=key, teachers=list(o)), c))) for o in opts]

def _row_key(x): return ("C", x["classes"][0], x["subject"]) if x["group"] == ENTIRE and x["classes"] else ("G", x["group"])

def room_options(m, spec, days, lesson_id, group):
    """the rooms of the row's kind (step 5's, else the current room's) and its class's home room, judged as a room fix (the
    current room left out) -> [dict(room, state, why)]"""
    x = next((x for x in _rows(m["lessons"], lesson_id) if x["group"] == group), None)
    if x is None: raise ValueError(f"There is no row of {group} in that lesson.")
    e = verify.planned_rows(spec).get(_row_key(x)); kind = (e or {}).get("room_kind") or m["room_ix"].get(x["room"], {}).get("kind")
    rooms = [str(v["room"]) for v in spec.get("venues") or [] if kind and (v.get("kind") or "classroom") == kind] + [m["class_ix"].get(k, {}).get("home") for k in x["classes"]]
    c = _ctx(m)
    return [dict(room=r, **_pick(judge(m, spec, days, dict(kind="room", id=lesson_id, group=group, room=r), c))) for r in dict.fromkeys(rooms) if r and r != x["room"]]

def add_slots(m, spec, days, key, n):
    """every (d, p) judged as an add of an n-period lesson of the key, in the class's home room for a classroom lesson, else
    the first free room of the kind, else no room -> [dict(d, p, state, why)]"""
    k = _key(key); e = verify.planned_rows(spec).get(k)
    if not e: raise ValueError(f"Step 5 has no lesson for {verify._name(k)}.")
    c = _ctx(m); b = c["busy"]; kind = e["room_kind"] or "classroom"; home = m["class_ix"].get((e["classes"] or [""])[0], {}).get("home") or ""
    kinds = [str(v["room"]) for v in spec.get("venues") or [] if (v.get("kind") or "classroom") == kind]
    free = lambda r, d, p: b.clash([dict(id=None, teachers=[], classes=[], group=ENTIRE, room=r, rain="")], d, p, n) is None
    out = []
    for d in range(len(days)):
        for p in range(m["NP"]):
            room = home if kind == "classroom" and home else next((r for r in kinds if free(r, d, p)), "")
            out.append(dict(d=d, p=p, **_pick(judge(m, spec, days, dict(kind="add", key=key, d=d, p=p, n=n, room=room), c))))
    return out

def can_delete(m, spec, days, lesson_id, group=None):
    """a delete of the lesson (or its row of group) judged -> dict(state, why)"""
    return _pick(judge(m, spec, days, dict(kind="delete", id=lesson_id, group=group)))

def short(m, spec):
    """the keys timetabled below plan, for the Add list -> [dict(key, name, have, want, n)]; n is step 5's usual lesson
    length, at most what is missing"""
    got = verify.placed(m); out = []
    for k, e in verify.planned_rows(spec).items():
        have = got[k]["periods"] if k in got else 0
        if have < e["periods"]:
            out.append(dict(key=verify._kstr(k), name=verify._name(k), have=have, want=e["periods"], n=min(int(e["rows"][0].get("length") or 1), e["periods"] - have)))
    return out

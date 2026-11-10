"""The helper: for one warning, up to three ways to settle it, each one or more fixes already judged by fixes.judge, each
saying what moves and what it disturbs. Nothing here changes the model it is given or touches files or the setup."""
import collections, re
from itertools import zip_longest
import fixes
from fixes import what, when
from ttgen import verify
from ttgen.export import ENTIRE

NOTHING = "The app has no suggestion for this one. Select a lesson on the grid to see where it can go."
NONE_PASS = "Nothing settles this without breaking a rule or a clash."
OK = ("ok", "prefer")
MAX_LESSONS = 8      # involved lessons whose slots are tried
MAX_BLOCKED = 60     # refused fixes tried for the blocked list

def _base(key): return re.sub(r"#\d+$", "", key or "")   # verify.warnings makes repeated keys unique with #2, #3
def _first(lessons, i): return next((x for x in lessons if x["id"] == i), None)
def _keys_of(x): return [("C", c, x["subject"]) for c in x["classes"]] if x["group"] == ENTIRE else [("G", x["group"])]

def _of_key(lessons, k):
    return [x for x in lessons if (x["group"] == ENTIRE and k[0] == "C" and k[1] in x["classes"] and x["subject"] == k[2]) or (k[0] == "G" and x["group"] == k[1])]

def _dep_parts(key):
    """'dep:{key string}:{what}' -> (key, what), or (None, None)"""
    k = _base(key)
    if not k.startswith("dep:"): return None, None
    ks, _, part = k[4:].rpartition(":")
    try: return fixes._key(ks), part
    except ValueError: return None, None

def _load(lessons):
    """teacher -> periods taught (a lesson id once)"""
    by, out = collections.defaultdict(list), collections.Counter()
    for x in lessons: by[x["id"]].append(x)
    for rows in by.values():
        for t in {t for x in rows for t in x["teachers"]}: out[t] += rows[0]["n"]
    return out


# ----------------------------------------------------------------------------------------------- applying without copying everything
def _own(L, f):
    """replace in L (the caller's list) the rows fix f may change with copies, so the rows of the model are never touched"""
    kind = f.get("kind")
    if kind == "teacher": ids = {x["id"] for x in _of_key(L, fixes._key(f["key"]))}
    elif kind == "swap": ids = {f["a"], f["b"]}
    elif kind in ("move", "room"): ids = {f["id"]}
    else: return   # an add appends a new row; a delete builds a new list
    L[:] = [dict(x, teachers=list(x["teachers"]), classes=list(x["classes"])) if x["id"] in ids else x for x in L]

def _apply(lessons, fx, spec, days):
    """fixes.apply on a shallow copy: only the rows a fix changes are copied -> the same dict(lessons, texts, problems, touched, was)"""
    L, texts, problems, touched, was = list(lessons), [], [], set(), []
    nxt = 1 + max([x["id"] for x in L], default=0)
    for f in fx:
        try: _own(L, f); texts.append(fixes.apply_one(L, f, spec, days, new_id=nxt, touched=touched, was=was))
        except Exception as e: problems.append(f"A fix could not be applied: {e if isinstance(e, ValueError) else 'it is not complete.'}")
        if isinstance(f, dict) and f.get("kind") == "add": nxt += 1
    return dict(lessons=L, texts=texts, problems=problems, touched=touched, was=was)


# ----------------------------------------------------------------------------------------------- words
def say(m, spec, days, fix):
    """the fix as an instruction for the committee"""
    L, kind = m["lessons"], fix.get("kind")
    if kind == "move": return f"Move {what(_first(L, fix['id']))} to {when(days, fix['d'], fix['p'])}."
    if kind == "swap": b = _first(L, fix["b"]); return f"Swap {what(_first(L, fix['a']))} with {what(b)} ({when(days, b['d'], b['p'])})."
    if kind == "teacher": return f"Give {verify._name(fixes._key(fix['key']))} to {fixes._names(fix['teachers'])}."
    if kind == "room":
        x = next(x for x in fixes._rows(L, fix["id"]) if x["group"] == fix["group"]); return f"Put {what(x)} in {fix['room'] or 'no room'}."
    if kind == "add":
        n = fix["n"]; return f"Add {verify._name(fixes._key(fix['key']))} on {when(days, fix['d'], fix['p'])} ({n} period{'' if n == 1 else 's'})."
    if kind == "delete":
        x = next(x for x in fixes._rows(L, fix["id"]) if fix.get("group") is None or x["group"] == fix["group"]); return f"Delete {what(x)} on {when(days, x['d'], x['p'])}."
    raise ValueError("This kind of fix is not known.")

def disturbs(m, spec, days, fx, steps):
    """what else a suggestion changes or gives, in sentences: a swap's other lesson, the Prefer rules and allowances it gives,
    a teacher change's loads; ["Nothing else moves."] when there is nothing"""
    out, L = [], m["lessons"]
    for f in fx:
        kind = f.get("kind"); after = _apply(L, [f], spec, days)["lessons"]
        if kind == "swap":
            a, b = _first(L, f["a"]), _first(L, f["b"])
            if a and b: out.append(f"{what(b)} moves to {when(days, a['d'], a['p'])}.")
        elif kind == "teacher":
            had = list(dict.fromkeys(t for x in _of_key(L, fixes._key(f["key"])) for t in x["teachers"])); load = _load(after)
            olds, news = [t for t in had if t not in f["teachers"]], [t for t in f["teachers"] if t not in had]
            for o, w in zip_longest(olds, news):
                out.append(f"{o} drops to {load[o]} periods, {w} rises to {load[w]}." if o and w else f"{o} drops to {load[o]} periods." if o else f"{w} rises to {load[w]} periods.")
        L = after
    for j in steps:
        for s in j.get("prefer") or []:
            if s not in out: out.append(s)
    return out or ["Nothing else moves."]


# ----------------------------------------------------------------------------------------------- judging a list of fixes
def chain(m, spec, days, fx, ctx=None):
    """each fix judged in order on the timetable the earlier ones leave -> dict(state, why, steps, lessons, texts, touched, was).
    A "na" or "no" step stops the judging with its why; lessons, texts, touched and was are for the whole list.
    ctx: a fixes._ctx of m to share across calls (the first step is judged on m)"""
    steps, state, why = [], "ok", ""
    for i, f in enumerate(fx):
        j = fixes.judge(m, spec, days, f, fixes._ctx(m, ctx)) if i == 0 else fixes.judge(dict(m, lessons=_apply(m["lessons"], fx[:i], spec, days)["lessons"]), spec, days, f)
        steps.append(j)
        if j["state"] not in OK: state, why = j["state"], j["why"]; break
        if j["state"] == "prefer" and state == "ok": state, why = "prefer", j["why"]
    r = _apply(m["lessons"], fx, spec, days)
    return dict(state=state, why=why, steps=steps, lessons=r["lessons"], texts=r["texts"], touched=r["touched"], was=r["was"])


# ----------------------------------------------------------------------------------------------- what a warning is about, and when it is gone
def _clash_who(w):
    wh = w.get("where") or {}
    return (wh["teacher"], True) if wh.get("teacher") else (wh["cls"], False) if wh.get("cls") else (None, None)

def _overlaps(lessons, who, teacher):
    """(d, q) -> ids where the teacher (or class, with a whole-class lesson among them) has more than one lesson, as export.check_model counts"""
    ids, whole = collections.defaultdict(set), set()
    for x in lessons:
        if who not in (x["teachers"] if teacher else x["classes"]): continue
        for q in range(x["p"], x["p"] + x["n"]):
            ids[x["d"], q].add(x["id"])
            if x["group"] == ENTIRE: whole.add((x["d"], q))
    return {s: v for s, v in ids.items() if len(v) > 1 and (teacher or s in whole)}

def _clash_slots(m, w, who):
    """the (d, q) a clash sentence names ('... on {day} period {q} (...)' or '... on {day} {times} (periods a-b)'), or None"""
    rest = _base(w["key"]).partition(f"{who} on ")[2]
    d = max((d for d, name in enumerate(m["days"]) if rest.startswith(name + " ")), key=lambda d: len(m["days"][d]), default=None)
    if d is None: return None
    if g := re.search(r"\(periods (\d+)-(\d+)\)", rest): return {(d, q) for q in range(int(g.group(1)), int(g.group(2)) + 1)}
    if g := re.match(r"period (\d+)", rest[len(m["days"][d]) + 1:]): return {(d, int(g.group(1)))}
    return None

def _rule_row(spec, key):
    rid = _base(key).split(":", 2)[1]; rules = spec.get("rules") or []
    return next(((i, r) for i, r in enumerate(rules) if str(r.get("_id") or i) == rid), (None, None))

def involved(m, w):
    """the lesson ids a warning is about (see the plan): its lesson, a deployment key's lessons, a teacher's or class's
    lessons on the day of a day-level rule, the overlapping lessons of a clash's teacher or class; else []"""
    L, kind, key, wh = m["lessons"], w.get("kind"), _base(w.get("key")), w.get("where") or {}
    ids = lambda rows: list(dict.fromkeys(x["id"] for x in rows))
    if kind == "deployment":   # before where: a deployment warning's where is only the key's first lesson
        k, _ = _dep_parts(key); return ids(_of_key(L, k)) if k else []
    if wh.get("id") is not None: return [wh["id"]] if _first(L, wh["id"]) else []
    if kind == "rule":
        who, _, d = key.split(":", 2)[2].rpartition("|") if key.count(":") >= 2 else ("", "", "")
        if not who or not d.isdigit(): return []
        d = int(d)
        if who in m["teacher_ix"]: return ids(x for x in L if x["d"] == d and who in x["teachers"])
        if who in m["class_ix"]: return ids(x for x in L if x["d"] == d and who in x["classes"])
        try: return ids(x for x in _of_key(L, fixes._key(who)) if x["d"] == d)
        except ValueError: return []
    if kind == "clash":
        who, teacher = _clash_who(w)
        if who is None: return []
        over = _overlaps(L, who, teacher); named = _clash_slots(m, w, who) or set()
        first = [i for s in sorted(over) if s in named for i in sorted(over[s])]
        return list(dict.fromkeys(first + [i for s in sorted(over) for i in sorted(over[s])]))
    return []

def _dep_keys(m, spec, lessons, K):
    """the deployment warning keys for the lesson keys K only: the setup rows and lessons that make up those keys, checked alone"""
    def row_keys(r):
        if not r.get("periods") or not r.get("classes"): return []
        return [("C", c, r["subject"]) for c in r["classes"]] if r.get("code") == ENTIRE else [("G", r.get("code"))]
    sp = dict(spec, lessons=[r for r in spec["lessons"] if any(k in K for k in row_keys(r))])
    L = [x for x in lessons if any(k in K for k in _keys_of(x))]
    return [w["key"] for w in verify.deployment(dict(m, lessons=L), sp) if _dep_parts(w["key"])[0] in K]

def settles(m, spec, days, w, lessons):
    """with lessons in place of the timetable's: is the warning gone, and has the count of deployment warnings not risen?
    Only the checks the warning needs are run (its rule row, its teacher's or class's overlaps, the keys the change reaches)."""
    kind, key = w.get("kind"), _base(w.get("key"))
    mine, theirs = {id(x) for x in m["lessons"]}, {id(x) for x in lessons}
    changed = [x for x in m["lessons"] if id(x) not in theirs] + [x for x in lessons if id(x) not in mine]
    K = {k for x in changed for k in _keys_of(x)}; dk = _dep_parts(key)[0] if kind == "deployment" else None
    if dk: K.add(dk)
    if kind == "rule":
        i, r = _rule_row(spec, key)
        if i is None: return False
        sp = dict(spec, rules=[r if j == i else {"rule": "In words"} for j, r in enumerate(spec.get("rules") or [])])
        ws, s = verify.rules(dict(m, lessons=lessons), sp)[0], fixes._subject(w)
        if any((fixes._subject(v) == s) if isinstance(s, tuple) else v["key"] == key for v in ws): return False
    elif kind == "clash":
        who, teacher = _clash_who(w)
        if who is None: return False
        over, named = _overlaps(lessons, who, teacher), _clash_slots(m, w, who)
        if (named & set(over)) if named else over: return False
    elif not dk: return False
    if not K: return True
    before, after = _dep_keys(m, spec, m["lessons"], K), _dep_keys(m, spec, lessons, K)
    return (not dk or key not in after) and len(after) <= len(before)


# ----------------------------------------------------------------------------------------------- what to try
def _rule_who(spec, w):
    """the teacher or class a rule warning is about: the day-level key's name, else the rule row's target"""
    if not (w.get("where") or {}).get("id") and (who := _base(w.get("key")).split(":", 2)[-1].rpartition("|")[0]): return who
    return (_rule_row(spec, w.get("key"))[1] or {}).get("target")

def _about_teacher(m, spec, w):
    if w.get("kind") == "clash": return _clash_who(w)[1] is True
    r = _rule_row(spec, w.get("key"))[1]
    return (r is not None and r.get("scope") == "Teacher") or _rule_who(spec, w) in m["teacher_ix"]

def _options(m, spec, days, w, ctx=None):
    """(the fixes worth trying, the fixes already refused as [(fixes, why)]) for the warning"""
    good, bad = [], []
    def put(fx, j):
        if j["state"] in OK: good.append(fx)
        elif j["state"] == "no": bad.append((fx, j["why"]))
    kind, wh = w.get("kind"), w.get("where") or {}
    try:
        if kind == "deployment":
            k, part = _dep_parts(w.get("key")); e = verify.planned_rows(spec).get(k) if k else None
            if k is None: return [], []
            ks, rows = verify._kstr(k), _of_key(m["lessons"], k)
            have, want = sum({x["id"]: x["n"] for x in rows}.values()), (e or {}).get("periods", 0)
            if part == "teachers" and e: good.append([dict(kind="teacher", key=ks, teachers=sorted(e["teachers"]))])
            elif part in ("periods", "missing") and e and have < want:
                n = next((x["n"] for x in fixes.short(m, spec) if x["key"] == ks), 1); c = fixes._ctx(m, ctx)
                for s in fixes.add_slots(m, spec, days, ks, n):
                    if s["state"] != "na": put([dict(kind="add", key=ks, d=s["d"], p=s["p"], n=n, room=fixes.add_room(m, spec, ks, s["d"], s["p"], n, c))], s)
            elif part == "extra" or (part == "periods" and have > want):
                for i in dict.fromkeys(x["id"] for x in rows):
                    many = len(fixes._rows(m["lessons"], i)) > 1; good.append([dict(kind="delete", id=i, **({"group": ENTIRE if k[0] == "C" else k[1]} if many else {}))])
            elif part == "venue" and e:   # the rows in a room of another kind (where names only the key's first lesson), as verify.deployment finds them
                kind_of = lambda x: m["room_ix"].get(x["room"], {}).get("kind") if x["room"] and x["room"] != "TBC" else None
                wrong = [x for x in rows if kind_of(x) and kind_of(x) != e["room_kind"] and not (kind_of(x) == "classroom" and verify._other_week(m["days"][x["d"]], e["room_weeks"]))]
                for x in wrong:
                    for o in fixes.room_options(m, spec, days, x["id"], x["group"]): put([dict(kind="room", id=x["id"], group=x["group"], room=o["room"])], o)
        elif kind in ("rule", "clash"):
            ids, keys = involved(m, w)[:MAX_LESSONS], []
            for i in ids:
                for s in fixes.slots(m, spec, days, i): put([dict(kind="swap", a=i, b=s["swap"]) if s["swap"] else dict(kind="move", id=i, d=s["d"], p=s["p"])], s)
                rows = fixes._rows(m["lessons"], i); who = _clash_who(w)[0] if kind == "clash" else _rule_who(spec, w)
                keys += [verify._kstr(fixes._row_key(x)) for x in rows if who in x["teachers"]] or [verify._kstr(fixes._row_key(rows[0]))]
            if _about_teacher(m, spec, w):
                for ks in dict.fromkeys(keys):
                    for o in fixes.teacher_options(m, spec, days, ks): put([dict(kind="teacher", key=ks, teachers=o["teachers"])], o)
    except ValueError: return [], []   # the warning names a lesson or key the timetable no longer has
    return good, bad

def candidates(m, spec, days, w):
    """the single fixes worth trying for the warning, each as a list of one fix"""
    return _options(m, spec, days, w)[0]

def rank(m, spec, days, s):
    """the sort key of a suggestion: fewer fixes, fewer lessons moved, ok before prefer, a teacher change's lower load against
    the allowance, the same day before another, the earlier day and period"""
    fx, L = s["fixes"], m["lessons"]; f = fx[-1]; kind = f.get("kind"); load, other, d, p = 0.0, 0, 0, 0
    if kind == "teacher":
        ids = {x["id"] for x in _of_key(L, fixes._key(f["key"]))}; now = _load([x for x in L if x["id"] not in ids])
        add = sum({x["id"]: x["n"] for x in L if x["id"] in ids}.values())
        for t in f["teachers"]:
            cap = fixes._allowance(m["teacher_ix"].get(t, {}).get("allowance")); k = now[t] + add
            load = max(load, k / cap if cap else float(k))
    elif kind in ("move", "swap"):
        a = _first(L, f["id"] if kind == "move" else f["a"]); b = _first(L, f["b"]) if kind == "swap" else None
        d, p = (f["d"], f["p"]) if kind == "move" else (b["d"], b["p"]) if b else (0, 0); other = int(bool(a) and a["d"] != d)
    elif kind == "add": d, p = f["d"], f["p"]
    elif kind in ("room", "delete") and (x := _first(L, f["id"])): d, p = x["d"], x["p"]
    return (len(fx), s["moved"], 0 if s["state"] == "ok" else 1, load, other, d, p)

def _suggestion(m, spec, days, fx, c):
    return dict(fixes=fx, text=" Then ".join(say(m, spec, days, f) for f in fx), disturbs=disturbs(m, spec, days, fx, c["steps"]),
                state=c["state"], moved=len(c["touched"] | {x["id"] for x in c["was"]}))

def suggest(m, spec, days, w, limit=3):
    """up to limit ways to settle the warning -> dict(suggestions, none, blocked): suggestions dict(fixes, text, disturbs, state,
    moved), ranked; none a sentence when there are none; blocked, when there are none, up to three fixes that would settle it
    if they were allowed, as dict(text, why)"""
    ctx = fixes._ctx(m); good, bad = _options(m, spec, days, w, ctx)
    if not good and not bad: return dict(suggestions=[], none=NOTHING, blocked=[])
    out, seen = [], set()
    for fx in good:
        if repr(fx) in seen: continue
        seen.add(repr(fx)); c = chain(m, spec, days, fx, ctx)
        if c["state"] in OK:
            if settles(m, spec, days, w, c["lessons"]): out.append(_suggestion(m, spec, days, fx, c))
        elif c["state"] == "no": bad.append((fx, c["why"]))
    out.sort(key=lambda s: rank(m, spec, days, s))
    if out: return dict(suggestions=out[:limit], none=None, blocked=[])
    blocked, tried = [], set()
    bad.sort(key=lambda b: rank(m, spec, days, dict(fixes=b[0], moved=0, state="ok")))   # the nearest first
    for fx, why in bad[:MAX_BLOCKED]:
        if repr(fx) in tried: continue
        tried.add(repr(fx)); r = _apply(m["lessons"], fx, spec, days)
        if not r["problems"] and settles(m, spec, days, w, r["lessons"]):
            blocked.append(dict(text=" Then ".join(say(m, spec, days, f) for f in fx), why=why))
            if len(blocked) == 3: break
    return dict(suggestions=[], none=NONE_PASS, blocked=blocked)

"""Look-ups about one lesson of the draft: what it can swap with, where it can go, who else could teach it, which rooms it could use.
Every option is judged by fixes.judge (or helper.chain, for two fixes) and worded by helper.say, helper.disturbs and typed.STEP5, so it
reads and behaves as the helper's suggestions do. Read-only: nothing here changes the model it is given or touches files or the setup.
m["pool"] is the pool given (draft.model_now sets both); this module does not import draft."""
import collections, fixes, helper, typed
from ttgen import spec as spec_mod, verify

QUESTIONS = ("here", "swaps", "moves", "teachers", "trades", "rooms", "fill", "free")   # what draft.about answers
TRADES = 40             # trades judged for one lesson before it stops and says so
MOST = 8                # options an answer holds before it counts the rest in more
BUSY = 4                # busy teachers added after the free ones
USED = 4                # rooms in use added after the free ones
NOT_FOUND = "There is no lesson with that id on the timetable."
POINT = "Point at a lesson for this."
EMPTY = "Point at an empty period for this."
ANYWAY = ("move", "place", "add", "teacher", "room")   # the kinds draft.FORCED lets a request force that a look-up offers (a delete is never an option)

def _int(v): return isinstance(v, int) and not isinstance(v, bool)
def _rows_of(m, pool, i): return [x for x in m["lessons"] if x["id"] == i] or [x for x in pool if x["id"] == i]
def _short(m): return lambda s: (m["subjects"].get(s) or {}).get("short") or s

# ----------------------------------------------------------------------------------------------- the subject of a question
def subject(m, pool, raw):
    """a subject as the page sends it, cleaned -> dict(kind="lesson", id, group, teacher) or dict(kind="place", by, name, d, p); ValueError(sentence)"""
    raw = raw if isinstance(raw, dict) else {}
    if raw.get("kind") == "lesson":
        i, g, t = raw.get("id"), raw.get("group"), raw.get("teacher"); rows = _rows_of(m, pool, i) if _int(i) else []
        if not rows: raise ValueError(NOT_FOUND)
        g = None if g is None else str(g)
        if g is not None and not any(x["group"] == g for x in rows): raise ValueError(f"There is no row of {g} in that lesson.")
        return dict(kind="lesson", id=i, group=g, teacher=None if t is None else str(t))
    if raw.get("kind") == "place":
        by, name, d, p = raw.get("by"), raw.get("name"), raw.get("d"), raw.get("p"); index = {"class": m["class_ix"], "teacher": m["teacher_ix"], "room": m["room_ix"]}.get(by)
        if index is None: raise ValueError("Point at a lesson or a place.")
        if not (_int(d) and _int(p) and 0 <= d < len(m["days"]) and 0 <= p < m["NP"]): raise ValueError("That is outside the day.")
        name = "" if name is None else str(name)
        if name == "": raise ValueError(f"Pick a {by}'s row.")
        if name not in index: raise ValueError(f"There is no {by} called {name}.")
        return dict(kind="place", by=by, name=name, d=d, p=p)
    raise ValueError("Point at a lesson or a place.")

# ----------------------------------------------------------------------------------------------- one option
def say(m, spec, days, pool, fix):
    """helper.say, and for a place: "Place {what} on {day} period {p}."; a room fix of a lesson in the pool is worded as helper.say words one"""
    if fix.get("kind") == "place":
        rows = [x for x in pool if x["id"] == fix["id"]]
        if not rows: raise ValueError("That lesson is not waiting to be placed.")
        return f"Place {fixes.what(rows[0])} on {fixes.when(days, fix['d'], fix['p'])}."
    if fix.get("kind") == "room" and not any(x["id"] == fix["id"] for x in m["lessons"]):   # a lesson waiting in the pool: helper.say reads only the timetable
        rows = [x for x in pool if x["id"] == fix["id"] and x["group"] == fix["group"]]
        if rows: return f"Put {fixes.what(rows[0])} in {fix['room'] or 'no room'}."
    return helper.say(m, spec, days, fix)

def check(m, spec, days, pool, fx, ctx=None, extra=()):
    """the fixes judged (one by fixes.judge with the pool, two by helper.chain) -> dict(fixes, text, disturbs, state, why, apply), or None when the
    judgement is na, there are none or more than two, or two hold a place or a lift. apply: "yes" for ok and prefer; "anyway" for a no of one
    move, place, add, teacher or room; else "none". disturbs: helper.disturbs, extra and typed.STEP5 for a step 5 difference the timetable lacked"""
    if not fx or len(fx) > 2 or (len(fx) == 2 and any(f.get("kind") in ("place", "lift") for f in fx)): return None
    ctx = fixes._ctx(m, ctx)
    if len(fx) == 1:
        j = fixes.judge(m, spec, days, fx[0], ctx, pool=pool)
        if j["state"] == "na": return None
        c = dict(state=j["state"], why=j["why"], steps=[j], lessons=helper._apply(m["lessons"], fx, spec, days)["lessons"])
    else:
        c = helper.chain(m, spec, days, fx, ctx)
        if c["state"] == "na": return None
    out, L = [], m["lessons"]
    for f in fx: out.append(say(dict(m, lessons=L), spec, days, pool, f)); L = helper._apply(L, [f], spec, days)["lessons"]
    mine, theirs = {id(x) for x in m["lessons"]}, {id(x) for x in c["lessons"]}
    K = {k for x in [x for x in m["lessons"] if id(x) not in theirs] + [x for x in c["lessons"] if id(x) not in mine] for k in helper._keys_of(x)}
    step5 = ctx.get("step5") or ctx.setdefault("step5", typed._Step5(m, spec))
    lines = list(extra) + ([typed.STEP5] if K and step5(c, K) else [])
    s = typed._plus(dict(disturbs=helper.disturbs(m, spec, days, fx, c["steps"])), lines)
    anyway = c["state"] == "no" and len(fx) == 1 and fx[0].get("kind") in ANYWAY
    return dict(fixes=list(fx), text=" Then ".join(out), disturbs=s["disturbs"], state=c["state"], why=c["why"], apply="yes" if c["state"] in helper.OK else "anyway" if anyway else "none")

# ----------------------------------------------------------------------------------------------- what the page shows above the options
def here(m, spec, days, pool, sub):
    """the lesson or place pointed at -> dict(title, lines): a lesson's "{what} · {day} period {p}" ("periods {p} to {q}"; "Not placed" in the pool),
    a band's by its band's name with a line a group; a place's "{name} · {day} period {p} · empty" """
    if sub["kind"] == "place": return dict(title=f"{sub['name']} · {fixes.when(days, sub['d'], sub['p'])} · empty", lines=[])
    rows = _rows_of(m, pool, sub["id"])
    if not rows: return dict(title=f"Lesson {sub['id']}", lines=[])
    a, name = rows[0], fixes.named(rows, _short(m))
    if not any(x is a for x in m["lessons"]) and any(x is a for x in pool): return dict(title=f"{name} · Not placed", lines=lines_of(rows, name))
    span = f"period {a['p']}" if a["n"] == 1 else f"periods {a['p']} to {a['p'] + a['n'] - 1}"
    return dict(title=f"{name} · {days[a['d']]} {span}", lines=lines_of(rows, name))

def lines_of(rows, name):
    """one line a group for a band: "group {g}: {subject}, {teachers or 'no teacher'}, {room or 'no room'}"; none for a lesson of one row"""
    if not name.startswith("the ") or not name.endswith(" band"): return []
    return [f"group {x['group']}: {x['subject']}, {', '.join(x['teachers']) or 'no teacher'}, {x['room'] if not fixes._no_room(x['room']) else 'no room'}" for x in rows]

def _answer(m, spec, days, pool, sub, text, options=(), more=0):
    return dict(text=text, options=list(options), more=more, stopped=False, **here(m, spec, days, pool, sub))

def _lesson(sub):
    if not isinstance(sub, dict) or sub.get("kind") == "place": raise ValueError(POINT)
    return dict(sub, group=sub.get("group"), teacher=sub.get("teacher"))

def _plural(n, one, many): return f"{n} {one if n == 1 else many}"
# ----------------------------------------------------------------------------------------------- swaps and moves, from one fixes.slots
def swaps(m, spec, days, pool, sub):
    """every place with a lesson it can swap with -> answer; the lessons it clashes with are options too, but not yes: apply "none" (yes before none, then helper.rank)"""
    sub = _lesson(sub); i = sub["id"]; rows = _rows_of(m, pool, i); P = (m, spec, days, pool)
    if not rows: return dict(text=NOT_FOUND, title=f"Lesson {i}", lines=[], options=[], more=0, stopped=False)
    if not any(x["id"] == i for x in m["lessons"]): return _answer(*P, sub, "A lesson that is not placed cannot be swapped. Ask where it can go.")
    ctx = fixes._ctx(m); got = [s for s in fixes.slots(m, spec, days, i, pool, extras=False, ctx=ctx) if s["swap"] and s["state"] != "na"]
    if not got: return _answer(*P, sub, "Nothing can swap with this lesson.")
    n = sum(s["state"] in helper.OK for s in got); bad = len(got) - n
    key = lambda s: (s["state"] not in helper.OK, helper.rank(m, spec, days, dict(fixes=[dict(kind="swap", a=i, b=s["swap"])], moved=2, state=s["state"])))
    text = (f"This lesson can swap with {_plural(n, 'lesson', 'lessons')}." + (f" {bad} more would land with a problem." if bad else "")) if n else f"No swap of this lesson is clean. {bad} would land with a problem."
    out = []
    for s in sorted(got, key=key)[:MOST]:
        o = check(*P, [dict(kind="swap", a=i, b=s["swap"])], ctx)
        if o is None: continue
        said = " ".join(o["disturbs"]); names = {fixes.what(x) for x in _rows_of(m, pool, s["swap"])}
        out.append(typed._plus(o, [a for a in s["also"] if not any(n in said for n in names)]))
    return _answer(*P, sub, text, out, len(got) - len(out))

def moves(m, spec, days, pool, sub):
    """every place it can go to without a swap, judged ok or prefer, as a move (a place for a lesson not placed); when fewer than three, up to three judged
    no after them, nearest day first. Places judged na are never options -> answer"""
    sub = _lesson(sub); i = sub["id"]; rows = _rows_of(m, pool, i); P = (m, spec, days, pool)
    if not rows: return dict(text=NOT_FOUND, title=f"Lesson {i}", lines=[], options=[], more=0, stopped=False)
    ctx = fixes._ctx(m); a = rows[0]; kind = "place" if not any(x["id"] == i for x in m["lessons"]) else "move"
    got = [s for s in fixes.slots(m, spec, days, i, pool, extras=False, ctx=ctx) if not s["swap"]]
    fix = lambda s: dict(kind=kind, id=i, d=s["d"], p=s["p"])
    good = sorted((s for s in got if s["state"] in helper.OK), key=lambda s: helper.rank(m, spec, days, dict(fixes=[fix(s)], moved=1, state=s["state"])))
    bad = sorted((s for s in got if s["state"] == "no"), key=lambda s: (abs(s["d"] - a["d"]), s["d"], abs(s["p"] - a["p"]), s["p"]))[:3] if len(good) < 3 else []
    row = next((x for x in rows if x["group"] == sub["group"]), a); band = typed._band(m, i, [row]); out = []   # the other groups move too; never the one asked about
    for s in good[:MOST] + bad:
        o = check(*P, [fix(s)], ctx, band)
        if o is not None: out.append(o)
    word = "placed in" if kind == "place" else "move to"
    text = f"This lesson can be {word} {_plural(len(good), 'place', 'places')}." if kind == "place" and good else f"This lesson can {word} {_plural(len(good), 'place', 'places')}." if good \
        else "Nowhere is free for this lesson without a clash or a broken rule." + (" These are the nearest places that would break something." if out else "")
    return _answer(*P, sub, text, out, max(0, len(good) - MOST))

# ----------------------------------------------------------------------------------------------- teachers and rooms, from fixes.choices
def _held(m, pool, key):
    """the periods a teacher fix of the key adds to a teacher who is not on it: its lessons once each, on the timetable and in the pool"""
    return sum({x["id"]: x["n"] for x in fixes.rows_of_key(list(m["lessons"]) + list(pool), key)}.values())

def teachers(m, spec, days, pool, sub):
    """who could take the lesson's row (sub["group"], default the first) in place of sub["teacher"] (else its first teacher; none: added) -> answer.
    The free teachers in fixes.choices' order, judged through check until MOST options are made (more: the free teachers not reached), then up to BUSY busy ones"""
    sub = _lesson(sub); i = sub["id"]; rows = _rows_of(m, pool, i); P = (m, spec, days, pool)
    if not rows: return dict(text=NOT_FOUND, title=f"Lesson {i}", lines=[], options=[], more=0, stopped=False)
    ch = fixes.choices(m, spec, days, i, sub["group"], pool); row = next(x for x in rows if x["group"] == ch["group"]); key = fixes._row_key(row); ks = ch["key"]
    ctx = fixes._ctx(m); had = [t for t in row["teachers"] if t == sub["teacher"]] or row["teachers"][:1]; held = _held(m, pool, key); pooled = helper._load(pool)
    team = {t["name"]: t for t in spec.get("teachers") or [] if isinstance(t, dict) and t.get("name")}
    subjects = lambda t: sorted({str(x.get("subject") or "").strip() for x in spec.get("lessons") or [] if isinstance(x, dict) and t in (x.get("teachers") or [])} - {""})
    def one(t):
        name = t["name"]; now = ctx["load"][name] + pooled[name]; cap = fixes._allowance((m["teacher_ix"].get(name) or {}).get("allowance")); depts = spec_mod.teacher_depts(team.get(name, {}))
        who = dict(name=name, depts=depts, subjects=subjects(name), free=t["free"], doing=t["doing"], rank=t["rank"], load=now, after=now + held, allowance=cap)
        extra = [f"{', '.join(depts) or 'No department'} · {now} to {now + held}{f' of {cap:g}' if cap is not None else ''} periods."]
        if ch["n_lessons"] > 1: extra.append(f"It changes all {ch['n_lessons']} lessons of {fixes.what(row)}.")
        if not t["free"]: extra.append(f"{name} is teaching {t['doing']}.")
        o = check(*P, [dict(kind="teacher", key=ks, teachers=[name if x == had[0] else x for x in row["teachers"]] if had else [name])], ctx, extra)
        return None if o is None else dict(o, who=who)
    free = [t for t in ch["teachers"] if t["free"] and t["name"] not in row["teachers"]]; busy = [t for t in ch["teachers"] if not t["free"] and t["name"] not in row["teachers"]][:BUSY]
    out, reached = [], 0
    for t in free:
        if len(out) >= MOST: break
        reached += 1
        if o := one(t): out.append(o)
    out += [o for o in map(one, busy) if o]
    text = f"{_plural(len(free), 'teacher is', 'teachers are')} free to take {fixes.what(row)}." if free else f"No other teacher is free to take {fixes.what(row)}."
    return _answer(*P, sub, text, out, len(free) - reached)

def rooms(m, spec, days, pool, sub):
    """which rooms the lesson's row (sub["group"], default the first) could use, for this one lesson -> answer: the free rooms, right kind first, judged through
    check until MOST options are made (more: the free rooms not reached), then up to USED rooms in use with "It holds {holding} then." in disturbs"""
    sub = _lesson(sub); i = sub["id"]; rows = _rows_of(m, pool, i); P = (m, spec, days, pool)
    if not rows: return dict(text=NOT_FOUND, title=f"Lesson {i}", lines=[], options=[], more=0, stopped=False)
    ch = fixes.choices(m, spec, days, i, sub["group"], pool); row = next(x for x in rows if x["group"] == ch["group"]); ctx = fixes._ctx(m)
    def one(r):
        o = check(*P, [dict(kind="room", id=i, group=row["group"], room=r["room"])], ctx, [] if r["free"] else [f"It holds {r['holding']} then."])
        return o
    free = [r for r in ch["rooms"] if r["free"] and r["room"] != row["room"]]; used = [r for r in ch["rooms"] if not r["free"] and r["room"] != row["room"]][:USED]
    out, reached = [], 0
    for r in free:
        if len(out) >= MOST: break
        reached += 1
        if o := one(r): out.append(o)
    out += [o for o in map(one, used) if o]
    text = f"{_plural(len(free), 'room is', 'rooms are')} free for {fixes.what(row)}." if free else f"No other room is free for {fixes.what(row)}."
    return _answer(*P, sub, text, out, len(free) - reached)

# ----------------------------------------------------------------------------------------------- trades between two teachers
def trades(m, spec, days, pool, sub, other=None):
    """the lesson's row (sub["group"], default the first) and its teacher X (as teachers picks) -> answer: each trade of that key A for a key B of another teacher Y,
    X taking B and Y taking A, judged as one trade fix on the timetable it leaves. Y: step 5's teachers of the subject, teachers on a lesson of the subject or of
    another subject of its step 3 card, then teachers whose departments include the subject's, with B a key of Y of the subject or the card; other: that teacher
    alone, with every key of theirs. ok and prefer are options (apply yes), then those judged no (apply none), at most MOST; none judged after TRADES (stopped)"""
    sub = _lesson(sub); i = sub["id"]; rows = _rows_of(m, pool, i); P = (m, spec, days, pool)
    if not rows: return dict(text=NOT_FOUND, title=f"Lesson {i}", lines=[], options=[], more=0, stopped=False)
    if other is not None and other not in m["teacher_ix"]: raise ValueError(f"There is no teacher called {other}.")
    row = next((x for x in rows if x["group"] == sub["group"]), rows[0]); key = fixes._row_key(row); ka = verify._kstr(key)
    x_ = next((t for t in row["teachers"] if t == sub["teacher"]), row["teachers"][0] if row["teachers"] else None)
    if x_ is None: return _answer(*P, sub, "This lesson has no teacher to trade.")
    e = verify.planned_rows(spec).get(key); subject = (e["subject"] if e else row["subject"]).strip(); on, dept = fixes._on_card(spec, subject)
    team = [t for t in spec.get("teachers") or [] if isinstance(t, dict) and t.get("name")]
    cards = fixes._cards(spec); card = cards.get(subject, ("", "", subject)); of_card = {n for n, v in cards.items() if v == card} | {subject}
    ys = [other] if other else list(dict.fromkeys((sorted(e["teachers"]) if e else []) + [t["name"] for t in team if t["name"] in on] + [t["name"] for t in team if t["name"] not in on and dept and dept in spec_mod.teacher_depts(t)]))
    ys = [y for y in ys if y != x_]; keys = collections.defaultdict(dict)   # Y -> its keys on the timetable, in the timetable's order
    for r in m["lessons"]:
        for y in r["teachers"]:
            if y in ys and (other or r["subject"].strip() in of_card): keys[y].update({k: None for k in helper._keys_of(r)})
    both = list(m["lessons"]) + list(pool); ra = fixes.rows_of_key(both, key); name_a = verify._name(key); ctx = fixes._ctx(m)
    good, bad, count, stopped = [], [], 0, False
    for y in ys:
        if any(y in r["teachers"] for r in ra): continue   # Y already teaches A: refused outright
        for kb in keys[y]:
            if kb == key: continue
            rb = fixes.rows_of_key(both, kb)
            if any(x_ in r["teachers"] for r in rb): continue
            if count >= TRADES: stopped = True; break
            ids = lambda rs, t: len({r["id"] for r in rs if t in r["teachers"]})
            extra = [f"It changes {ids(ra, x_)} {'lesson' if ids(ra, x_) == 1 else 'lessons'} of {name_a} and {ids(rb, y)} of {verify._name(kb)}."]
            o = check(*P, [dict(kind="trade", a=ka, b=verify._kstr(kb), x=x_, y=y)], ctx, extra)
            if o is None: continue
            count += 1; (good if o["state"] in helper.OK else bad).append(o)
        if stopped: break
    out = (good + bad)[:MOST]
    text = f"{_plural(len(good), 'trade is', 'trades are')} possible for {x_}." + (f" {len(bad)} more would land with a problem." if bad else "") if good else \
        f"No trade of this lesson is clean. {len(bad)} would land with a problem." if bad else "No trade of this lesson can be made."
    return dict(_answer(*P, sub, text + (f" Only the first {TRADES} possible trades were checked." if stopped else ""), out, len(good) + len(bad) - len(out)), stopped=stopped)

# ----------------------------------------------------------------------------------------------- what can fill an empty period
def _by_id(rows):
    out = collections.defaultdict(list)
    for x in rows: out[x["id"]].append(x)
    return out

def fill(m, spec, days, pool, sub):
    """an empty period of a class, a teacher or a room (sub, a place) -> answer: the lessons that could go there, judged ok or prefer only: those of the pool as a
    place, the step 5 lessons below plan as an add (room from fixes.add_room), those elsewhere as a move ("Leaves {day} period {p} empty." in disturbs), each by
    helper.rank. By class or teacher a candidate is tried only when its periods are inside the day, lesson time and hold no lesson of its classes; by room: the
    lessons that cover the period with no room or a room of another kind than they ask (or not on the setup's list), as a room fix to this room"""
    if not isinstance(sub, dict) or sub.get("kind") != "place": raise ValueError(EMPTY)
    by, name, d, p = sub["by"], sub["name"], sub["d"], sub["p"]; P = (m, spec, days, pool); ctx = fixes._ctx(m); busy = ctx["busy"]; cand = []   # (fix, what else it disturbs)
    def empty(classes, n, rows, own=None):
        """periods p .. p+n-1 of day d: inside the day, lesson time, and no lesson but its own for any of its classes"""
        return p + n <= m["NP"] and busy.lesson_time(rows, d, p, n) is None and not any(y["id"] != own for c in classes for q in range(p, p + n) for y in busy.at.get(("c", c, d, q), ()))
    if by in ("class", "teacher"):
        mine = (lambda x: name in x["classes"]) if by == "class" else (lambda x: name in x["teachers"])
        for i, rs in _by_id(pool).items():
            if any(map(mine, rs)) and empty({c for x in rs for c in x["classes"]}, rs[0]["n"], rs): cand.append((dict(kind="place", id=i, d=d, p=p), []))
        plan = verify.planned_rows(spec)
        for s in fixes.short(m, spec, pool):
            e = plan.get(fixes._key(s["key"]))
            if e and name in (e["classes"] if by == "class" else e["teachers"]) and empty(e["classes"], s["n"], [dict(level=e["level"], classes=e["classes"], group="", subject="")]):
                cand.append((dict(kind="add", key=s["key"], d=d, p=p, n=s["n"], room=fixes.add_room(m, spec, s["key"], d, p, s["n"], ctx, pool)), []))
        for i, rs in _by_id(m["lessons"]).items():
            a, row = rs[0], next((x for x in rs if mine(x)), None)
            if row and (a["d"], a["p"]) != (d, p) and empty({c for x in rs for c in x["classes"]}, a["n"], rs, own=i):
                cand.append((dict(kind="move", id=i, d=d, p=p), [f"Leaves {fixes.when(days, a['d'], a['p'])} empty."] + typed._band(m, i, [row])))
    elif by == "room":
        mine = (m["room_ix"].get(name) or {}).get("kind")
        for x in m["lessons"]:
            if not (x["d"] == d and x["p"] <= p < x["p"] + x["n"]) or x["room"] == name: continue
            asks = fixes._room_kind(m, spec, x); has = (m["room_ix"].get(x["room"]) or {}).get("kind")
            if (fixes._no_room(x["room"]) or x["room"] not in m["room_ix"] or (asks and has != asks)) and not (asks and mine != asks): cand.append((dict(kind="room", id=x["id"], group=x["group"], room=name), []))
    good = []
    for f, extra in cand:
        o = check(*P, [f], ctx, extra)
        if o is not None and o["state"] in helper.OK: good.append((("place", "add", "move", "room").index(f["kind"]), helper.rank(m, spec, days, dict(fixes=[f], moved=1, state=o["state"])), o))
    good.sort(key=lambda g: g[:2]); out = [g[2] for g in good[:MOST]]
    return _answer(*P, sub, f"{_plural(len(good), 'lesson could', 'lessons could')} go here." if good else "Nothing fits here without a clash or a broken rule.", out, len(good) - len(out))

# ----------------------------------------------------------------------------------------------- who is free
def free(m, spec, days, pool, sub):
    """who is free in the periods of a place, or of a lesson (its day, period and length) -> answer with no options: lines one a department of the teachers
    on no lesson then ("Mathematics: Bala Nair, Chen Wei"), then one a kind of the rooms in use by none (and none a rain room), each in the setup's order"""
    if not isinstance(sub, dict) or sub.get("kind") not in ("lesson", "place"): raise ValueError("Point at a lesson or a place.")
    P = (m, spec, days, pool)
    if sub["kind"] == "place": d, p, n = sub["d"], sub["p"], 1
    else:
        rows = [x for x in m["lessons"] if x["id"] == sub["id"]]
        if not rows: return _answer(*P, sub, "A lesson that is not placed has no time yet.") if _rows_of(m, pool, sub["id"]) else dict(text=NOT_FOUND, title=f"Lesson {sub['id']}", lines=[], options=[], more=0, stopped=False)
        d, p, n = rows[0]["d"], rows[0]["p"], rows[0]["n"]
    b = fixes._ctx(m)["busy"]; Q = range(p, p + n)
    team = list({t["name"]: t for t in spec.get("teachers") or [] if isinstance(t, dict) and t.get("name")}.values()); depts = collections.defaultdict(list); kinds = collections.defaultdict(list)
    for t in team:
        if not any(b.at.get(("t", t["name"], d, q)) for q in Q):
            for dp in spec_mod.teacher_depts(t) or ["No department"]: depts[dp].append(t["name"])
    for v in {str(v["room"]): v for v in spec.get("venues") or [] if isinstance(v, dict) and v.get("room")}.values():
        if all(len({y["id"] for y in b.at.get(("r", r, d, q), ())}) < m["room_cap"].get(r, 1) and not b.at.get(("h", r, d, q)) for r in b.rooms(str(v["room"])) for q in Q):
            kinds[(v.get("kind") or "classroom").capitalize()].append(str(v["room"]))
    when = fixes.when(days, d, p) if n == 1 else f"{days[d]} periods {p} to {p + n - 1}"
    free_t = {t for v in depts.values() for t in v}; lines = [f"{k}: {', '.join(v)}" for k, v in sorted(depts.items())] + [f"{k}: {', '.join(v)}" for k, v in sorted(kinds.items())]
    return _answer(*P, sub, f"{_plural(len(free_t), 'teacher', 'teachers')} and {_plural(sum(map(len, kinds.values())), 'room', 'rooms')} are free on {when}.", [], 0) | dict(lines=lines)

"""Look-ups about one lesson of the draft: what it can swap with, where it can go, who else could teach it, which rooms it could use.
Every option is judged by fixes.judge (or helper.chain, for two fixes) and worded by helper.say, helper.disturbs and typed.STEP5, so it
reads and behaves as the helper's suggestions do. Read-only: nothing here changes the model it is given or touches files or the setup.
m["pool"] is the pool given (draft.model_now sets both); this module does not import draft."""
import fixes, helper, typed
from ttgen.export import ENTIRE
from ttgen import spec as spec_mod

MOST = 8                # options an answer holds before it counts the rest in more
BUSY = 4                # busy teachers added after the free ones
USED = 4                # rooms in use added after the free ones
NOT_FOUND = "There is no lesson with that id on the timetable."
POINT = "Point at a lesson for this."
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
    """helper.say, and for a place: "Place {what} on {day} period {p}." """
    if fix.get("kind") == "place":
        rows = [x for x in pool if x["id"] == fix["id"]]
        if not rows: raise ValueError("That lesson is not waiting to be placed.")
        return f"Place {fixes.what(rows[0])} on {fixes.when(days, fix['d'], fix['p'])}."
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

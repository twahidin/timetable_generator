"""Fixes to the draft: each is one change the committee made to the timetable they uploaded, kept as a small record and
applied again, in order, to the lessons read from the file. Nothing here touches files or the setup."""
import collections, copy, re
from ttgen.export import ENTIRE, _split_list, abbrev, block_label
from ttgen import spec as spec_mod, verify

KINDS = ("move", "swap", "teacher", "trade", "room", "add", "delete", "lift", "place")

def what(x):
    """a lesson row in words: '{subject} for {class}' for an entire-class lesson, 'group {code}' otherwise"""
    return f"{x['subject']} for {', '.join(x['classes'])}" if x["group"] == ENTIRE else f"group {x['group']}"

def band(rows, short=None):
    """the name the board gives a lesson of several rows or a block: its block's label, else its subjects' short names joined
    with " / "; "" for a lesson of one row with no block. short: a subject's short name (default: the model's, abbrev)"""
    short = short or (lambda s: abbrev(s) or s); blocked = next((x for x in rows if x["block"]), None)
    return block_label(blocked["block"], blocked["level"]) if blocked else " / ".join(dict.fromkeys(short(x["subject"]) for x in rows)) if len(rows) > 1 else ""

def named(rows, short=None):
    """a whole lesson (its rows) in words: "the {band} band" for a band, else what() of its row"""
    b = band(rows, short); return f"the {b} band" if b else what(rows[0])

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

def _after(spec, days, rows, d, p, n):
    """whether the lesson (its rows) in periods p .. p+n-1 of day d is in an after-school slot: a period coded A in the day
    structure for a level of the lesson (a row's level, else its classes' levels); a level or day the structure lacks is not"""
    ds = spec.get("day_structure") or {}; cl = {str(c.get("class")): c.get("level") for c in spec.get("classes") or []}
    levels = {lv for x in rows for lv in ([x["level"]] if x.get("level") in ds else [cl.get(c) for c in x["classes"]])}
    codes = [str((ds.get(lv) or {}).get(days[d]) or "") for lv in levels if 0 <= d < len(days)]
    return any(q < len(c) and c[q] == "A" for c in codes for q in range(p, p + n))

def _out(fix, own):
    """the ids a fix pushes out (its out list, [] when it has none); one that names the lesson itself is not complete"""
    out = fix.get("out")
    if out is None: return []
    if not isinstance(out, (list, tuple)) or (own is not None and own in out): raise ValueError("That fix is not complete.")
    return list(out)

def rows_of_key(rows, k):
    """the rows of the key k (a tuple from _key or _row_key): an entire-class row of the subject for a class of the key, or a row of the key's group"""
    return [x for x in rows if (x["group"] == ENTIRE and k[0] == "C" and k[1] in x["classes"] and x["subject"] == k[2]) or (k[0] == "G" and x["group"] == k[1])]

def _room(room, spec):
    """a fix's room as the setup names it (runs of spaces made one, ends trimmed: a fix stored before names were cleaned still
    finds its room); ValueError when it is not on the setup's list of rooms. No room stays as it is"""
    if not room: return room
    r = spec_mod.clean_name(room)
    if r not in {spec_mod.clean_name(v.get("room")) for v in spec.get("venues") or []}: raise ValueError(f"{room} is not on the setup's list of rooms.")
    return r

def apply_one(lessons, fix, spec, days, new_id=None, touched=None, was=None, pool=None):
    """change lessons (a list the caller owns) in place and return the sentence for the committee; ValueError(sentence) when the
    fix cannot apply (every kind checks before it changes anything). new_id: the id an add takes (default 1 + the highest in
    lessons and pool); touched: a set the ids of lessons changed, added, lifted or placed are put into; was: a list that copies
    of the rows as they were just before a fix changed, deleted, lifted or placed them are appended to; pool: a list the caller
    owns holding the rows of the lessons that are not placed (each keeps the d and p it left). A lesson id is wholly in
    lessons or wholly in pool. out (on a move, a place or an add): the ids of lessons lifted into the pool first, in order:
    only those on the timetable with a row that shares a class with the lesson's rows and a period with where it goes (a fix
    replayed after an earlier one was skipped never lifts a lesson that is no longer in the way); the sentence names them."""
    if not isinstance(fix, dict): raise ValueError("it is not complete.")
    kind = fix.get("kind"); touched = set() if touched is None else touched; pool = [] if pool is None else pool
    keep = (lambda rows: None) if was is None else lambda rows: was.extend(copy.deepcopy(list(rows)))   # no copies when nobody reads them
    pooled = lambda i: any(x["id"] == i for x in pool)
    def lift(i):
        rows = [x for x in lessons if x["id"] == i]; keep(rows)
        lessons[:] = [x for x in lessons if x["id"] != i]; pool.extend(rows); touched.add(i); return rows
    def push(out, rows, d, p, n):
        cls = {c for x in rows for c in x["classes"]}
        hit = lambda i: any(x["id"] == i and x["d"] == d and set(x["classes"]) & cls and x["p"] < p + n and p < x["p"] + x["n"] for x in lessons)
        names = [named(lift(i)) for i in dict.fromkeys(out) if hit(i)]
        return f" Pushed out: {', '.join(names)}." if names else ""
    if kind == "move":
        if pooled(fix["id"]): raise ValueError("That lesson is not placed. Place it first.")
        rows = _rows(lessons, fix["id"]); _slot(spec, days, fix["d"], fix["p"], rows[0]["n"]); out = _out(fix, fix["id"]); a = rows[0]
        text = f"Moved {what(a)} from {when(days, a['d'], a['p'])} to {when(days, fix['d'], fix['p'])}." + push(out, rows, fix["d"], fix["p"], a["n"])
        keep(rows)
        ext = _after(spec, days, rows, fix["d"], fix["p"], a["n"])
        for x in rows: x["d"], x["p"], x["ext"] = fix["d"], fix["p"], ext
        touched.add(fix["id"]); return text
    if kind == "swap":
        if pooled(fix["a"]) or pooled(fix["b"]): raise ValueError("That lesson is not placed. Place it first.")
        ra, rb = _rows(lessons, fix["a"]), _rows(lessons, fix["b"]); a, b = ra[0], rb[0]
        if a["n"] != b["n"]: raise ValueError(f"{what(a)} and {what(b)} are not the same length, so they cannot swap places.")
        text = f"Swapped {what(a)} ({when(days, a['d'], a['p'])}) with {what(b)} ({when(days, b['d'], b['p'])})."
        (da, pa), (db, pb) = (a["d"], a["p"]), (b["d"], b["p"])
        keep(ra + rb)
        ea, eb = _after(spec, days, ra, db, pb, a["n"]), _after(spec, days, rb, da, pa, b["n"])
        for x in ra: x["d"], x["p"], x["ext"] = db, pb, ea
        for x in rb: x["d"], x["p"], x["ext"] = da, pa, eb
        touched |= {fix["a"], fix["b"]}; return text
    if kind == "lift":
        rows = _rows(lessons, fix["id"]); a = rows[0]; text = f"Lifted out {what(a)} from {when(days, a['d'], a['p'])}."
        lift(fix["id"]); return text
    if kind == "place":
        rows = [x for x in pool if x["id"] == fix["id"]]
        if not rows: raise ValueError("That lesson is not waiting to be placed.")
        _slot(spec, days, fix["d"], fix["p"], rows[0]["n"]); out = _out(fix, fix["id"])
        text = f"Placed {what(rows[0])} on {when(days, fix['d'], fix['p'])}." + push(out, rows, fix["d"], fix["p"], rows[0]["n"])
        keep(rows); pool[:] = [x for x in pool if x["id"] != fix["id"]]
        ext = _after(spec, days, rows, fix["d"], fix["p"], rows[0]["n"])
        for x in rows: x["d"], x["p"], x["ext"] = fix["d"], fix["p"], ext
        lessons.extend(rows); touched.add(fix["id"]); return text
    if kind == "teacher":
        key = _key(fix["key"]); name = verify._name(key); known = {x["name"] for x in spec.get("teachers") or []}
        rows = rows_of_key(lessons + pool, key)
        if not rows: raise ValueError(f"There is no lesson of {name} on the timetable.")
        bad = [x for x in fix["teachers"] if x not in known]
        if bad: raise ValueError(f"{', '.join(bad)} {'is' if len(bad) == 1 else 'are'} not on the setup's list of teachers.")
        old = list(dict.fromkeys(t for x in rows for t in x["teachers"]))
        keep(rows)
        for x in rows: x["teachers"] = list(fix["teachers"])
        touched |= {x["id"] for x in rows}
        if not fix["teachers"]: return f"{name} now has no teacher; it had {_names(old)}."
        return f"{name} is now taught by {_names(fix['teachers'])}; it had no teacher." if not old else f"{name} is now taught by {_names(fix['teachers'])}, not {_names(old)}."
    if kind == "trade":
        ka, kb = _key(fix["a"]), _key(fix["b"]); na, nb = verify._name(ka), verify._name(kb); x, y = fix["x"], fix["y"]
        if ka == kb or x == y: raise ValueError("That changes nothing.")
        ra, rb = rows_of_key(lessons + pool, ka), rows_of_key(lessons + pool, kb)
        for name, rows in ((na, ra), (nb, rb)):
            if not rows: raise ValueError(f"There is no lesson of {name} on the timetable.")
        known = {v["name"] for v in spec.get("teachers") or []}; bad = [v for v in (x, y) if v not in known]
        if bad: raise ValueError(f"{', '.join(bad)} {'is' if len(bad) == 1 else 'are'} not on the setup's list of teachers.")
        if not any(x in r["teachers"] for r in ra): raise ValueError(f"{x} does not teach {na}.")
        if not any(y in r["teachers"] for r in rb): raise ValueError(f"{y} does not teach {nb}.")
        if any(y in r["teachers"] for r in ra): raise ValueError(f"{y} already teaches {na}.")
        if any(x in r["teachers"] for r in rb): raise ValueError(f"{x} already teaches {nb}.")
        hit = [(r, x, y) for r in ra if x in r["teachers"]] + [(r, y, x) for r in rb if y in r["teachers"]]; keep([r for r, _, _ in hit])
        for r, out_, in_ in hit: r["teachers"] = [in_ if t == out_ else t for t in r["teachers"]]
        touched |= {r["id"] for r, _, _ in hit}; return f"{x} and {y} traded: {x} now teaches {nb}, {y} {na}."
    if kind == "room":
        x = next((x for x in _rows(lessons + pool, fix["id"]) if x["group"] == fix["group"]), None)
        if x is None: raise ValueError(f"There is no row of {fix['group']} in that lesson.")
        room = _room(fix["room"], spec)
        text = f"{what(x)} {'(not placed)' if pooled(fix['id']) else 'on ' + when(days, x['d'], x['p'])} is now in {room or 'no room'}, not {x['room'] or 'no room'}."
        keep([x]); x["room"] = room; touched.add(x["id"])
        return text
    if kind == "add":
        key = _key(fix["key"]); e = verify.planned_rows(spec).get(key)
        if not e: raise ValueError(f"Step 5 has no lesson for {verify._name(key) if len(key) in (2, 3) else fix['key']}.")
        _slot(spec, days, fix["d"], fix["p"], fix["n"])
        room = _room(fix["room"], spec)
        i = new_id if new_id is not None else 1 + max([y["id"] for y in lessons + pool], default=0); out = _out(fix, i)
        x = dict(id=i, d=fix["d"], p=fix["p"], n=fix["n"], level=e["level"] or "", block=str(e["rows"][0].get("block") or ""),
                 classes=list(e["classes"]), subject=e["subject"], group=ENTIRE if key[0] == "C" else key[1],
                 teachers=list(dict.fromkeys(t for r in e["rows"] for t in r.get("teachers") or [])), room=room, ext=False, rain="")
        x["ext"] = _after(spec, days, [x], x["d"], x["p"], x["n"]); pushed = push(out, [x], x["d"], x["p"], x["n"]); lessons.append(x); touched.add(x["id"])
        return f"Added {what(x)} on {when(days, x['d'], x['p'])} ({x['n']} period{'' if x['n'] == 1 else 's'}) {'in ' + x['room'] if x['room'] else 'with no room'}." + pushed
    if kind == "delete":
        side = pool if pooled(fix["id"]) else lessons
        rows = [x for x in _rows(side, fix["id"]) if fix.get("group") is None or x["group"] == fix["group"]]
        if not rows: raise ValueError(f"There is no row of {fix['group']} in that lesson.")
        a = rows[0]; text = f"Deleted {what(a)} (it was not placed)." if side is pool else f"Deleted {what(a)} on {when(days, a['d'], a['p'])}."
        keep(rows); side[:] = [x for x in side if not any(x is r for r in rows)]
        if not any(x["id"] == fix["id"] for x in lessons + pool): touched.discard(fix["id"])
        return text
    raise ValueError("This kind of fix is not known.")

def apply(lessons, fixes, spec, days):
    """a copy of lessons with every fix applied in order -> dict(lessons, texts, problems, touched, was, pool); pool is the rows
    of the lessons not placed after every fix (no id is in both lessons and pool). A fix that cannot apply
    (the file or the setup changed since, or it is malformed) is skipped and named in problems; touched is the ids of lessons
    a fix changed or added; was is the rows as they were just before each fix changed or deleted them (a row changed twice appears twice). An add takes 1 + the highest id as read from the file, plus one per add before it, applied or skipped: an
    add's id depends only on its place among the adds, so a later fix made for "the second add" still finds it."""
    L, texts, problems, touched, was, pool = copy.deepcopy(lessons), [], [], set(), [], []
    nxt = 1 + max([x["id"] for x in L], default=0)
    for f in fixes:
        try: texts.append(apply_one(L, f, spec, days, new_id=nxt, touched=touched, was=was, pool=pool))
        except Exception as e: problems.append(f"A fix could not be applied: {e if isinstance(e, ValueError) else 'it is not complete.'}")
        if isinstance(f, dict) and f.get("kind") == "add": nxt += 1
    return dict(lessons=L, texts=texts, problems=problems, touched=touched, was=was, pool=pool)

def editor(fixes, out):
    """the edit function for model_from_files: applies the fixes to the lessons read from the file and leaves texts, problems,
    touched, was and pool in out"""
    def edit(lessons, spec, days):
        r = apply(lessons, fixes, spec, days); out.update(texts=r["texts"], problems=r["problems"], touched=r["touched"], was=r["was"], pool=r["pool"]); return r["lessons"]
    return edit


# ----------------------------------------------------------------------------------------------- judging a fix
def _span(x): return range(x["p"], x["p"] + x["n"])
def _no_room(r): return not r or r == "TBC"
def _classes(rows): return list(dict.fromkeys(c for x in rows for c in x["classes"]))
def _block(rows): return len(rows) > 1 or any(x["block"] for x in rows)

def _students(k, code, y): return f"1 student of {code} has {what(y)} then." if k == 1 else f"{k} students of {code} have {what(y)} then."

def everyone_bands(m):
    """the names of the bands every student of their classes takes a group of: step 5's "Everyone takes one", which is ticked
    unless the committee unticked it or the band's name says option or elective (as the page reads it)"""
    out = set()
    for b in (m.get("checked_setup") or {}).get("blocks") or []:
        if not isinstance(b, dict) or not str(b.get("block") or "").strip(): continue
        v = b.get("everyone")
        if (not re.search(r"option|elective", str(b["block"]), re.I)) if v is None else (v is True or str(v).strip().lower() in ("true", "yes", "y", "1")): out.add(b["block"])
    return out

class Busy:
    """who and what is in use in each period, built once per request: teachers, classes, whole-class lessons, groups,
    rooms and rain rooms by (kind, name, day, period), each lesson's rows by id, and which groups share students"""
    def __init__(self, m, lessons=None, base=None):
        self.m, self.at, self.ids, self.by = m, collections.defaultdict(list), collections.defaultdict(list), collections.defaultdict(set); self.parts = m.get("room_parts") or {}
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
                if not _no_room(x["room"]):
                    for s in self.rooms(x["room"]): self.at["r", s, x["d"], q].append(x)   # a combined venue is in each of its rooms
                for h in _split_list(x.get("rain")):
                    if h != "TBC":
                        for s in self.rooms(h): self.at["h", s, x["d"], q].append(x)
        self._full(m["lessons"] if lessons is None else lessons)
        if base: self.share, self.gcls, self.cgroups = base.share, base.gcls, base.cgroups; return
        self.share, self.gcls, self.cgroups = (collections.defaultdict(collections.Counter) for _ in range(3))   # group -> {group: students in both}; group -> {class: its students}; class -> {group: its students}
        for st in m["students"]:
            gs = list(dict.fromkeys(st["groups"]))
            for g in gs:
                self.gcls[g][st["cls"]] += 1; self.cgroups[st["cls"]][g] += 1
                for g2 in gs:
                    if g2 != g: self.share[g][g2] += 1

    def rooms(self, room):
        """the single rooms a venue stands for (a combined venue: its rooms; else itself)"""
        return spec_mod.single_rooms(room, self.parts)

    def _full(self, lessons):
        """a band every student of its classes takes a group of ("Everyone takes one" on step 5) keeps a whole class busy while all
        its groups for that class have a lesson: at["f", class, day, period] then holds one row of it. Another band's lesson for
        that class in that period is a clash, with or without a list of students"""
        self.every = every = everyone_bands(self.m); self.bgroups = groups = collections.defaultdict(set); here = collections.defaultdict(dict)
        if not every: return
        for x in lessons:
            if x["block"] in every and x["group"] != ENTIRE:
                for c in x["classes"]:
                    groups[x["block"], c].add(x["group"])
                    for q in _span(x): here[x["block"], c, x["d"], q].setdefault(x["group"], x)
        for (b, c, d, q), got in here.items():
            if len(got) == len(groups[b, c]): self.at["f", c, d, q].append(next(iter(got.values())))

    def band_clash(self, rows, d, p, n, ignore=()):
        """(class, the other lesson's row) when these rows in periods p .. p+n-1 of day d put two bands on one class at once and one
        of the two takes every student of the class then; else None. A band's own groups never clash with each other"""
        ignore = set(ignore)
        for x in rows:
            if x["group"] == ENTIRE or not x["block"]: continue   # a group outside a band (a pull-out) is its own students' business
            for c in x["classes"]:
                whole = x["block"] in self.every and {y["group"] for y in rows if y["block"] == x["block"] and c in y["classes"]} >= self.bgroups.get((x["block"], c), {None})
                for q in range(p, p + n):
                    for y in self.at.get(("f", c, d, q), ()):
                        if y["id"] not in ignore and y["block"] != x["block"]: return c, y
                    if whole:
                        for y in self.at.get(("c", c, d, q), ()):
                            if y["id"] not in ignore and y["group"] != ENTIRE and y["block"] and y["block"] != x["block"]: return c, y
        return None

    def outside(self, rows, d, p, n):
        """whether lesson_time refuses the place because it is outside the day (no school then for a class of the rows, past the
        day's last period or the 'Lessons end by' time) and not because of a recess, a lunch or an assembly"""
        m = self.m
        if not 0 <= d < len(m["days"]) or p < 0 or p + n > m["NP"]: return True
        k = m["keep"].get(m["days"][d])
        if k is not None and p + n > k: return True
        levels = {lv for x in rows for c in x["classes"] or [""] for lv in (x["level"], m["class_ix"].get(c, {}).get("level")) if lv in m["grid"]}
        return any(m["grid"][lv][d][q] == "." for lv in levels for q in range(p, p + n))

    def _first(self, key, ignore): return next((y for y in self.at.get(key, ()) if y["id"] not in ignore), None)

    def _why(self, rows, d, p, n, ignore):
        """(the first reason, the lesson behind it or None for a room), or (None, None)"""
        ignore, Q, f = set(ignore), range(p, p + n), self._first
        for x in rows if d not in (self.m.get("double") or ()) else ():   # a day the setup lets a teacher take two lessons at once
            for t in x["teachers"]:
                for q in Q:
                    if y := f(("t", t, d, q), ignore): return f"{t} is teaching {what(y)} then.", y
        for x in rows:
            for c in x["classes"]:
                for q in Q:
                    if y := f(("c" if x["group"] == ENTIRE else "w", c, d, q), ignore): return f"{c} has {what(y)} then.", y
        if hit := self.band_clash(rows, d, p, n, ignore): return f"{hit[0]} has the {block_label(hit[1]['block'], hit[1]['level'])} band then, and every student of {hit[0]} is in one of the two.", hit[1]
        for x in rows:
            pairs = [(c, g, k) for c in x["classes"] for g, k in self.cgroups.get(c, {}).items()] if x["group"] == ENTIRE else \
                [(x["group"], g, k) for g, k in self.share.get(x["group"], {}).items()]
            for q in Q:
                for who, g, k in pairs:
                    if y := f(("g", g, d, q), ignore): return _students(k, who, y), y
                if x["group"] != ENTIRE:
                    for c, k in self.gcls.get(x["group"], {}).items():
                        if y := f(("w", c, d, q), ignore): return _students(k, x["group"], y), y
        mine = collections.Counter(x["room"] for x in rows if not _no_room(x["room"]))
        own = collections.Counter()   # a single room -> how many of the rows' own rows stand on it (a row in a combined venue stands on each of its rooms, as check_model counts)
        for room, k in mine.items():
            for s in self.rooms(room): own[s] += k
        for room in mine:
            for s in self.rooms(room):
                for q in Q:
                    if sum(y["id"] not in ignore for y in self.at.get(("r", s, d, q), ())) + own[s] > self.m["room_cap"].get(s, 1) or f(("h", s, d, q), ignore): return f"{room} is in use then.", None
        for x in rows:
            for h in _split_list(x.get("rain")):
                if h != "TBC" and any(s in own or any(f(("r", s, d, q), ignore) for q in Q) for s in self.rooms(h)): return f"{h} is in use then.", None
        return None, None

    def clash(self, rows, d, p, n, ignore=()):
        """the first reason these rows cannot be in periods p .. p+n-1 of day d, the lessons with ids in ignore set aside, or None"""
        return self._why(rows, d, p, n, ignore)[0]

    def blocker(self, rows, d, p, n, ignore=()):
        """the id of the lesson behind the reason clash gives for the same arguments; None when there is no clash or the reason is a room"""
        y = self._why(rows, d, p, n, ignore)[1]; return None if y is None else y["id"]

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
def _subject(w):
    """what a rule warning is about: (rule row, lesson id) for a lesson, wherever it sits; the warning's key for a day or a slot (a where without an id)"""
    return (w["key"].split(":", 2)[1], w["where"]["id"]) if (w.get("where") or {}).get("id") is not None else w["key"]

def rule_subjects(m, spec, lessons):
    """{subject: the first warning about it} from the standard rules on these lessons only; a fix is worse where it adds a subject"""
    out = {}
    for w in _rule_ws(m, spec, lessons): out.setdefault(_subject(w), w)
    return out

def _bears(m, spec, r, x, depts):
    """whether rule row r can see lesson row x at all, wherever it sits: a change to lessons it cannot see leaves its warnings as they were"""
    rule, sc, tg = r.get("rule"), r.get("scope"), r.get("target")
    if rule == "Keep free together": return any(tg in depts.get(t, ()) for t in x["teachers"]) or any(m["class_ix"].get(c, {}).get("level") == tg for c in x["classes"])
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

def judge(m, spec, days, fix, ctx=None, pool=()):
    """how a fix would leave the timetable -> dict(state, why, must, prefer): "na" it cannot go there, "no" a clash, a period
    count away from the plan or a Must rule broken anew, "prefer" only a Prefer rule or a teacher's allowance gives, else "ok".
    Broken anew: a rule warning about a subject (rule_subjects) that had none before.
    ctx: the shared index of one request (slots and the option lists pass it); pool: the rows of the lessons not placed now.
    A lift is "ok" when it can apply; a place is judged as a move of the lesson from nowhere (no "changes nothing", no count
    against the plan); the lessons a fix pushes out (out) are off the timetable before and after, so they neither clash with
    it nor count for a rule. For the periods against the plan and a teacher's load a lesson in the pool counts as timetabled,
    pushed out by this fix or waiting already: only a delete takes periods away and only an add brings them"""
    c = _ctx(m, ctx); b = c["busy"]
    res = lambda state, why="", must=(), prefer=(): dict(state=state, why=why, must=list(must), prefer=list(prefer))
    if not isinstance(fix, dict): return res("na", "That fix is not complete.")
    kind = fix.get("kind")
    try:
        if kind == "teacher":
            key = _key(fix["key"]); ids = {x["id"] for x in rows_of_key(m["lessons"], key)} | {x["id"] for x in rows_of_key(pool, key)}
        elif kind == "trade":   # both keys' lessons are changed at once, so each is checked against the other as it is after the change
            ids = {x["id"] for k in (_key(fix["a"]), _key(fix["b"])) for x in rows_of_key(m["lessons"], k) + rows_of_key(pool, k)}
        else: ids = {fix[k] for k in {"swap": ("a", "b")}.get(kind, ("id",) if kind in ("move", "room", "delete", "lift", "place") else ())}
        gone = {i for i in fix.get("out") or () if i in b.ids} - ids if kind in ("move", "place", "add") and isinstance(fix.get("out"), (list, tuple)) else set()
        old = [x for i in ids - gone for x in b.ids.get(i, ())]; new = [dict(x, teachers=list(x["teachers"]), classes=list(x["classes"])) for x in old]
        p0 = [x for x in pool if x["id"] in ids]; p1 = [dict(x, teachers=list(x["teachers"]), classes=list(x["classes"])) for x in p0]   # the pooled rows the fix can reach
        apply_one(new, fix, spec, days, new_id=max([c["next_id"]] + [1 + x["id"] for x in pool]), pool=p1)
    except ValueError as e: return res("na", str(e))
    except (KeyError, TypeError): return res("na", "That fix is not complete.")
    if kind == "lift": return res("ok")
    if (kind == "move" and (old[0]["d"], old[0]["p"]) == (fix["d"], fix["p"])) or (kind == "swap" and fix["a"] == fix["b"]): return res("na", "That changes nothing.")
    if kind == "swap":
        ra, rb = b.ids[fix["a"]], b.ids[fix["b"]]
        if set(_classes(ra)) != set(_classes(rb)) and (_block(ra) or _block(rb)): return res("na", "A block lesson can only swap with a lesson of the same classes.")
    before, after = collections.defaultdict(list), collections.defaultdict(list)
    for x in old: before[x["id"]].append(x)
    for x in new: after[x["id"]].append(x)
    changed = set(before) | set(after) | gone   # pushed out: off the timetable before and after, for clashes and rules
    moved = {i for i, r in after.items() if i not in before or (r[0]["d"], r[0]["p"]) != (before[i][0]["d"], before[i][0]["p"])}
    for i in moved:
        x = after[i][0]
        if kind in ("move", "place"):   # the lesson's own rows: the same answer for every judgement of one place in a context
            lk = ("time", kind, i, x["d"], x["p"])
            if lk not in c["memo"]: c["memo"][lk] = b.lesson_time(after[i], x["d"], x["p"], x["n"])
            why = c["memo"][lk]
        else: why = b.lesson_time(after[i], x["d"], x["p"], x["n"])
        if why: return res("na", why)
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
        ko, kn, kp = _keys(old + p0), _keys(new + p1), _keys(pool)   # a pooled lesson counts as timetabled, before and after
        for k in sorted(set(ko) | set(kn)):
            was = c["placed"].get(k, 0) + kp[k]; now, want = was - ko[k] + kn[k], m["planned"].get(k, 0)
            if now != was and not (was < now <= want or want <= now < was): return res("no", f"{LEAVE}{verify._name(k)} with {now} periods; step 3 plans {want}.")
    rules = spec.get("rules") or []; seen = old + new
    depts = c["memo"].get(("depts", id(spec)))   # worked out on the first judge of a context and setup, not per lesson or per call
    if depts is None: depts = c["memo"][("depts", id(spec))] = verify.teacher_depts(m, spec)
    sk = ("scope", id(spec), kind, fix["id"]) if kind in ("move", "place") else None   # a move or a place changes only where the lesson sits, which no scope reads
    if sk is not None and sk in c["memo"]: keep, near = c["memo"][sk]
    else:
        keep = tuple(i for i, r in enumerate(rules) if r.get("rule") != "In words" and any(_bears(m, spec, r, x, depts) for x in seen))
        near = _near(b, old) | _near(b, new)
        for i in keep:
            if rules[i].get("rule") in WIDE and (test := verify.in_scope(m, spec, rules[i])):
                near |= c["memo"].setdefault(("wide", id(spec), i), {x["id"] for x in m["lessons"] if test(x)})
        if sk is not None: c["memo"][sk] = keep, frozenset(near)
    must, prefer = [], []
    if keep:
        sp = dict(spec, rules=[r if i in keep else {"rule": "In words"} for i, r in enumerate(rules)])
        mk = (id(spec), keep, near if isinstance(near, frozenset) else frozenset(near))
        if mk not in c["memo"]:
            L0 = [x for x in m["lessons"] if x["id"] in near]; c["memo"][mk] = (L0, rule_subjects(m, sp, L0))
        L0, s0 = c["memo"][mk]; L1, put = [], set()
        if gone:
            if (mk, frozenset(gone)) not in c["memo"]: c["memo"][mk, frozenset(gone)] = rule_subjects(m, sp, [x for x in L0 if x["id"] not in gone])
            s0 = c["memo"][mk, frozenset(gone)]
        for x in L0:   # in the timetable's order, as the full check sees it (a day's first lesson names some warnings)
            if x["id"] not in changed: L1.append(x)
            elif x["id"] not in put: put.add(x["id"]); L1 += after.get(x["id"], [])
        L1 += [x for x in new if x["id"] not in put]
        for k, w in rule_subjects(m, sp, L1).items():
            if k not in s0: (must if w["strength"] == "Must" else prefer).append(w["text"])
    if kind in ("teacher", "trade", "add", "delete"):
        by = lambda rows: {i: [x for x in rows if x["id"] == i] for i in dict.fromkeys(x["id"] for x in rows)}
        b0, b1, inpool = by(old + p0), by(new + p1), by(pool)
        for t in sorted({t for x in seen + p0 + p1 for t in x["teachers"]}):
            has = lambda rows: sum(r[0]["n"] for r in rows.values() if any(t in y["teachers"] for y in r))
            was = c["load"][t] + has(inpool); now = was - has(b0) + has(b1); cap = _allowance(m["teacher_ix"].get(t, {}).get("allowance"))
            if cap is not None and now > cap and now > was: prefer.append(f"{t} would have {now} periods, {now - cap:g} over the allowance.")
    if must: return res("no", must[0], must, prefer)
    if prefer: return res("prefer", prefer[0], must, prefer)
    return res("ok")

LEAVE = "That would leave "   # how the sentence of a period count away from step 5's plan starts

def _pick(j, *keys): return {k: j[k] for k in ("state", "why") + keys}

def _placer(m, spec, days, lesson_id, pool, extras, ctx):
    """(the lesson's rows, a function (d, p) -> the slot there) for slots and place; extras: see slots"""
    c = _ctx(m, ctx); b = c["busy"]; mine = [x for x in pool if x["id"] == lesson_id]
    sh = lambda s: (m["subjects"].get(s) or {}).get("short") or s; name = lambda i: named(b.ids[i], sh)
    rows = mine or _rows(m["lessons"], lesson_id); a = rows[0]; n, cls = a["n"], _classes(rows)
    go = dict(kind="place" if mine else "move", id=lesson_id)
    def listed(i): return dict(id=i, what=name(i), classes=_classes(b.ids[i]), groups=len(b.ids[i]))
    def at(d, p):
        there = {y["id"]: y for k in cls for q in range(p, min(p + n, m["NP"])) for y in b.at.get(("c", k, d, q), ()) if y["id"] != lesson_id}
        ids = sorted(there); push = beside = None; judged = lambda **k: _pick(judge(m, spec, days, dict(go, d=d, p=p, **k), c, pool))
        if ids and extras is True: push = dict(**judged(out=ids), out=[listed(i) for i in ids]); beside = judged()
        more = dict(push=push, beside=beside) if extras is True else dict(there=[listed(i) for i in ids] if ids else None) if extras == "who" else {}
        if mine and ids and extras == "who": return dict(d=d, p=p, state="na", why="Another lesson is there.", swap=None, also=[], **more)
        if mine or not there: return dict(d=d, p=p, **(beside or judged()), swap=None, also=[], **more)
        y = next(iter(there.values()))
        if len(there) == 1 and (y["d"], y["p"], y["n"]) == (d, p, n):
            also = [f"This also moves {what(y)} to {when(days, a['d'], a['p'])}."] if set(_classes(b.ids[y["id"]])) != set(cls) else []   # a band swaps only with its own classes, so this names one row
            return dict(d=d, p=p, **_pick(judge(m, spec, days, dict(kind="swap", a=lesson_id, b=y["id"]), c, pool)), swap=y["id"], also=also, **more)
        return dict(d=d, p=p, state="na", why="Another lesson is there.", swap=None, also=[], **more)
    return bool(mine), a, at

def slots(m, spec, days, lesson_id, pool=(), extras=True, ctx=None):
    """every (d, p) of the week(s) judged -> [dict(d, p, state, why, swap, also, push, beside)]. For a lesson on the timetable, every
    (d, p) but its own: an empty stretch of its classes as a move, a stretch where exactly one other lesson of the same length
    starts as a swap, anything else occupied "na". For a lesson in the pool (the rows of the lessons not placed), every (d, p)
    as a place, swap always None. push: where other lessons of its classes are, those lessons (in id order) and how the move
    or place is judged once they are pushed out, dict(state, why, out=[dict(id, what, classes, groups)]): what as named() says
    it (a band by its band's name), classes all its classes, groups how many rows; None where there are none. beside:
    where other lessons of its classes are, how the plain move or place (with them left there) is judged, dict(state, why);
    None where there are none. extras=False (draft.options, the helper, the typed request: they read only state, why, swap and also)
    leaves push and beside out, and their judgements unmade: each slot is dict(d, p, state, why, swap, also). extras="who" (the
    board's): the keys of False and there: None where no other lesson of its classes is, else those lessons as push.out lists them,
    and no push or beside judged (see place); a lesson in the pool is "na" ("Another lesson is there.") where there is one. ctx: see judge"""
    mine, a, at = _placer(m, spec, days, lesson_id, pool, extras, ctx)
    return [at(d, p) for d in range(len(days)) for p in range(m["NP"]) if mine or (d, p) != (a["d"], a["p"])]

def place(m, spec, days, lesson_id, d, p, pool=(), ctx=None):
    """the one slot at (d, p) with everything slots(extras=True) gives it -> dict(d, p, state, why, swap, also, push, beside); push and
    beside are None where no other lesson of the lesson's classes is. ValueError for an unknown lesson, or a place outside the days or periods"""
    if not all(isinstance(v, int) and not isinstance(v, bool) for v in (d, p)) or not 0 <= d < len(days) or not 0 <= p < m["NP"]: raise ValueError("That is outside the day.")
    return _placer(m, spec, days, lesson_id, pool, True, ctx)[2](d, p)

def marks(busy, rows, pool=False):
    """the critical mistakes of one lesson (its rows) as busy sees the timetable, in the order "notplaced", "noteacher", "break",
    "teacher", "class", "room", then "noroom" (a warning): "notplaced" alone for a lesson in the pool (pool true). Only other
    lesson ids clash: a band's own groups sharing a teacher or a room do not, nor do two groups of one class at once; a group
    row clashes with a whole-class lesson of its classes. A place outside the model's days or periods is "break" and nothing
    that needs the index"""
    if pool: return ["notplaced"]
    m, a = busy.m, rows[0]; own, d, Q = a["id"], a["d"], range(a["p"], a["p"] + a["n"]); out = []
    others = lambda key: {y["id"] for y in busy.at.get(key, ()) if y["id"] != own}
    if any(not x["teachers"] for x in rows): out.append("noteacher")
    if busy.lesson_time(rows, d, a["p"], a["n"]): out.append("break")
    if 0 <= d < len(m["days"]) and a["p"] >= 0 and a["p"] + a["n"] <= m["NP"]:
        if d not in (m.get("double") or ()) and any(others(("t", t, d, q)) for x in rows for t in x["teachers"] for q in Q): out.append("teacher")
        if any(others(("c" if x["group"] == ENTIRE else "w", c, d, q)) for x in rows for c in x["classes"] for q in Q) or busy.band_clash(rows, d, a["p"], a["n"], ignore=(own,)): out.append("class")
        rooms = {s for x in rows if not _no_room(x["room"]) for s in busy.rooms(x["room"])}
        if any(len({y["id"] for y in busy.at.get(("r", r, d, q), ())} | {own}) > m["room_cap"].get(r, 1) for r in rooms for q in Q): out.append("room")
    if any(_no_room(x["room"]) for x in rows): out.append("noroom")
    return out

def _cards(spec):
    """step 3's cards, as static/subjectview.js reads them -> {subject name (trimmed): card}, a card being (department, code,
    name) trimmed, the name less its own tag when that tag is one of the school's and the name is the tag alone or ends with a
    space and the tag; rows that are not dicts and tag entries that are not lists are skipped"""
    school = spec.get("school") if isinstance(spec.get("school"), dict) else {}
    entries = school.get("tags") if isinstance(school.get("tags"), (list, tuple)) else []
    tags = {str(e[0]).strip() for e in entries if isinstance(e, (list, tuple)) and e and e[0] is not None} - {"", "-"}
    out = {}
    for r in spec.get("subjects") or []:
        if not isinstance(r, dict) or r.get("subject") is None: continue
        name = str(r["subject"]).strip(); tag = str(r.get("tag") or "").strip()
        if tag in tags and name.endswith(" " + tag): name = name[:len(name) - len(tag)].strip()
        out.setdefault(str(r["subject"]).strip(), (str(r.get("dept") or "").strip(), str(r.get("code") or "").strip(), name))
    return out

def _on_card(spec, subject):
    """(the teachers on a lesson of step 5 of the subject or of another subject of its step 3 card, the card's department)"""
    cards = _cards(spec); card = cards.get(subject, ("", "", subject))
    of_card = {n for n, v in cards.items() if v == card} | {subject}
    return {t for x in spec.get("lessons") or [] if isinstance(x, dict) and str(x.get("subject") or "").strip() in of_card for t in x.get("teachers") or []}, card[0]

def teacher_options(m, spec, days, key, pool=()):
    """who could take the key's lesson, judged as a teacher fix (the current teachers left out) -> [dict(teachers, state, why)]:
    step 5's teachers of the key, then each teacher of the setup's list who is on a lesson row of the subject or of another
    subject of its step 3 card, then each other teacher whose departments include the subject's department; inside the last
    two the teacher list's order"""
    k = _key(key); e = verify.planned_rows(spec).get(k); c = _ctx(m)
    rows = [x for x in m["lessons"] if (x["group"] == ENTIRE and k[0] == "C" and k[1] in x["classes"] and x["subject"] == k[2]) or (k[0] == "G" and x["group"] == k[1])]
    subject = (e["subject"] if e else k[2] if k[0] == "C" else rows[0]["subject"] if rows else "").strip()
    now = {t for x in rows for t in x["teachers"]}
    on, dept = _on_card(spec, subject)
    team = [t for t in spec.get("teachers") or [] if isinstance(t, dict) and t.get("name")]
    opts = ([sorted(e["teachers"])] if e and e["teachers"] else []) + [[t["name"]] for t in team if t["name"] in on] \
        + ([[t["name"]] for t in team if t["name"] not in on and dept in spec_mod.teacher_depts(t)] if dept else [])
    opts = [o for o in dict.fromkeys(map(tuple, opts)) if set(o) != now and not (len(o) == 1 and o[0] in now)]
    return [dict(teachers=list(o), **_pick(judge(m, spec, days, dict(kind="teacher", key=key, teachers=list(o)), c, pool))) for o in opts]

def _row_key(x): return ("C", x["classes"][0], x["subject"]) if x["group"] == ENTIRE and x["classes"] else ("G", x["group"])

def _room_kind(m, spec, x):
    """the kind of room a row asks for: step 5's, else its present room's; None when neither says"""
    e = verify.planned_rows(spec).get(_row_key(x)); return (e or {}).get("room_kind") or m["room_ix"].get(x["room"], {}).get("kind")

def room_options(m, spec, days, lesson_id, group, pool=()):
    """the rooms of the row's kind (step 5's, else the current room's) and its class's home room, judged as a room fix (the
    current room left out) -> [dict(room, state, why)]"""
    x = next((x for x in _rows(m["lessons"], lesson_id) if x["group"] == group), None)
    if x is None: raise ValueError(f"There is no row of {group} in that lesson.")
    kind = _room_kind(m, spec, x)
    rooms = [str(v["room"]) for v in spec.get("venues") or [] if kind and (v.get("kind") or "classroom") == kind] + [m["class_ix"].get(k, {}).get("home") for k in x["classes"]]
    c = _ctx(m)
    return [dict(room=r, **_pick(judge(m, spec, days, dict(kind="room", id=lesson_id, group=group, room=r), c, pool))) for r in dict.fromkeys(rooms) if r and r != x["room"]]

def add_room(m, spec, key, d, p, n, ctx=None, pool=()):
    """the room an add of an n-period lesson of the key at (d, p) takes: the first room free in all its periods among the home
    rooms of its classes, in order (for a classroom lesson: a row with no room kind is one), then the other rooms of its kind;
    else no room ("", which never clashes)"""
    k = _key(key); e = verify.planned_rows(spec).get(k)
    if not e: raise ValueError(f"Step 5 has no lesson for {verify._name(k)}.")
    b = _ctx(m, ctx)["busy"]; kind = e["room_kind"] or "classroom"
    homes = [m["class_ix"].get(c, {}).get("home") or "" for c in e["classes"]] if kind == "classroom" else []
    rooms = [str(r) for r in dict.fromkeys(homes + [v["room"] for v in spec.get("venues") or [] if (v.get("kind") or "classroom") == kind]) if r]
    free = lambda r: b.clash([dict(id=None, teachers=[], classes=[], group=ENTIRE, room=r, rain="")], d, p, n) is None
    return next((r for r in rooms if free(r)), "")

def add_slots(m, spec, days, key, n, pool=()):
    """every (d, p) judged as an add of an n-period lesson of the key, in the room add_room chooses -> [dict(d, p, state, why)]"""
    c = _ctx(m); add_room(m, spec, key, 0, 0, n, c)   # raises for a key step 5 does not have
    return [dict(d=d, p=p, **_pick(judge(m, spec, days, dict(kind="add", key=key, d=d, p=p, n=n, room=add_room(m, spec, key, d, p, n, c)), c, pool)))
            for d in range(len(days)) for p in range(m["NP"])]

def can_delete(m, spec, days, lesson_id, group=None, pool=(), ctx=None):
    """a delete of the lesson (or its row of group) judged -> dict(state, why, plan); plan: the "no" is because step 5's planned
    periods would be missed (a delete checks no clash: any other "no" is a rule). ctx: see judge"""
    j = _pick(judge(m, spec, days, dict(kind="delete", id=lesson_id, group=group), ctx, pool))
    return dict(j, plan=j["state"] == "no" and j["why"].startswith(LEAVE))

def _length(v):
    """a lesson length in any spelling of a whole number ('2', 2.0, '2.0'), else 1"""
    try: f = float(str(v).strip()); return int(f) if f == int(f) and f >= 1 else 1
    except (ValueError, OverflowError): return 1

def short(m, spec, pool=()):
    """the keys timetabled below plan, for the Add list -> [dict(key, name, have, want, n)]; n is step 5's usual lesson
    length, at most what is missing. A lesson in the pool (the rows of the lessons not placed) counts as timetabled"""
    got = verify.placed(dict(m, lessons=list(m["lessons"]) + list(pool))); out = []
    for k, e in verify.planned_rows(spec).items():
        have = got[k]["periods"] if k in got else 0
        if have < e["periods"]:
            out.append(dict(key=verify._kstr(k), name=verify._name(k), have=have, want=e["periods"], n=min(_length(e["rows"][0].get("length")), e["periods"] - have)))
    return out

def choices(m, spec, days, lesson_id, group=None, pool=()):
    """who and which room could take one lesson row, as the board's editor lists them (read-only) -> dict(id, group, key, what, n_lessons,
    teachers, rooms). The row is the lesson's row of group (default its first), on the timetable or in the pool. n_lessons: the lesson ids
    the row's key has on the timetable and in the pool. teachers: every teacher of the setup once, dict(name, short, free, doing, rank), the
    free ones first, each by rank (0 step 5's teachers of the key, 1 on a lesson of the subject or its card, 2 of the subject's department,
    3 anyone) then the setup's order; free: on no row but the key's own on the timetable in any period of any of its lessons (a teacher on another group of the same
    lesson is not free); doing: the first
    lesson they are on then, '{what} on {day} period {p}', else ''. rooms: every venue once, dict(room, kind, right, free, holding): right
    is the kind step 5 asks for or a home room of the row's classes; free: a room fix putting this row there would not be refused for the room
    (Busy._why, this lesson set aside; always free for a lesson in the pool); holding: what of the first lesson in it (or having it as a rain
    room) then, else the judgement's own sentence, '' when free. Ordered free and right, free, then the rest, each in the setup's order"""
    mine = [x for x in pool if x["id"] == lesson_id]; rows = mine or [x for x in m["lessons"] if x["id"] == lesson_id]
    if not rows: raise ValueError("There is no lesson with that id on the timetable.")
    row = rows[0] if group is None else next((x for x in rows if x["group"] == group), None)
    if row is None: raise ValueError(f"There is no row of {group} in that lesson.")
    k = _row_key(row); b = Busy(m); e = verify.planned_rows(spec).get(k)
    held = rows_of_key(m["lessons"], k)
    n_lessons = len({x["id"] for x in rows_of_key(list(m["lessons"]) + list(pool), k)})
    order = sorted({x["id"]: x for x in held}.values(), key=lambda x: (x["d"], x["p"], x["id"]))
    def doing(t):
        for x in order:
            for q in _span(x):
                y = next((y for y in b.at.get(("t", t, x["d"], q), ()) if _row_key(y) != k), None)   # any row but the key's own: another group of the same lesson counts, its teacher is not free then
                if y: return f"{what(y)} on {when(days, y['d'], y['p'])}"
        return ""
    on, dept = _on_card(spec, (e["subject"] if e else row["subject"]).strip()); step5 = set(e["teachers"]) if e else set()
    rank = lambda t: 0 if t["name"] in step5 else 1 if t["name"] in on else 2 if dept and dept in spec_mod.teacher_depts(t) else 3
    team = list({t["name"]: t for t in spec.get("teachers") or [] if isinstance(t, dict) and t.get("name")}.values()); teachers = []
    for t in team:
        d = doing(t["name"]); teachers.append(dict(name=t["name"], short=(m["teacher_ix"].get(t["name"]) or {}).get("short") or t["name"], free=not d, doing=d, rank=rank(t)))
    teachers.sort(key=lambda t: (not t["free"], t["rank"]))   # stable: the setup's order within
    kind = _room_kind(m, spec, row); homes = {str(m["class_ix"].get(c, {}).get("home") or "") for c in row["classes"]} - {""}; rooms = []
    for v in {str(v["room"]): v for v in spec.get("venues") or [] if isinstance(v, dict) and v.get("room")}.values():
        room, vk = str(v["room"]), v.get("kind") or "classroom"; free, holding = True, ""
        if not mine:   # free: a room fix putting this row in the room would not be refused for the room (this lesson set aside)
            why = b._why([dict(row, teachers=[], classes=[], group=ENTIRE, rain="", room=room)], row["d"], row["p"], row["n"], {lesson_id})[0]
            if why:
                held = [y for q in _span(row) for k in ("r", "h") for s in b.rooms(room) for y in b.at.get((k, s, row["d"], q), ()) if y["id"] != lesson_id]
                free, holding = False, what(held[0]) if held else why
        rooms.append(dict(room=room, kind=vk, right=bool(kind and vk == kind) or room in homes, free=free, holding=holding))
    rooms.sort(key=lambda r: 0 if r["free"] and r["right"] else 1 if r["free"] else 2)
    return dict(id=lesson_id, group=row["group"], key=verify._kstr(k), what=what(row), n_lessons=n_lessons, teachers=teachers, rooms=rooms)

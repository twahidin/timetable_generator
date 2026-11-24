"""A saved student follows onto the published timetable: after a save names student rows, those students' records on
the published timetable are brought up to date at once, and nothing else in it changes. Students are matched by
student ID (the published records have no row id). A student who cannot follow is left as the published timetable
has them, with the reason in words."""
import collections, copy
import history, store
from ttgen import export as E

KIND = "students-published"

def key(row):
    return str(row.get("id") or row.get("name") or "").strip()

def record(row):
    """what a full publish makes of one setup row (ttgen/export.py _model)"""
    return dict(id=str(row.get("id") or row.get("name")), name=str(row.get("name") or row.get("id")), cls=str(row.get("class") or ""),
                level=str(row.get("level") or ""), groups=[str(g) for g in row.get("groups") or []])

def why_not(row, model, counts):
    """why this setup row cannot follow onto the published model, or None when it can"""
    k = key(row)
    if not k: return "no student ID or name"
    if counts.get(k, 0) > 1: return "this ID is on the list twice"
    cls = str(row.get("class") or "")
    if cls not in model["class_ix"]: return f"class {cls} is not on the published timetable"
    have = {L["group"] for L in model["lessons"]}
    missing = [str(g) for g in row.get("groups") or [] if str(g) not in have]
    if len(missing) == 1: return f"group {missing[0]} is not on the published timetable"
    if missing: return f"groups {', '.join(missing)} are not on the published timetable"
    return None

def touched(pairs):
    """(keys of every row after the save, keys that may be removed, how many deleted rows are held back)"""
    keys = [key(a) for b, a in pairs if a is not None]
    gone = [b for b, a in pairs if a is None and b is not None]
    may_remove = {key(b) for b, a in pairs if b is not None and a is not None and key(b) != key(a)}
    if len(gone) == 1: may_remove.add(key(gone[0]))
    return keys, may_remove, (len(gone) if len(gone) > 1 else 0)

def _text(updated, removed, left, held):
    out = []
    if len(updated) == 1: out.append(f"Published timetable updated for {updated[0]['name']} ({updated[0]['id']}).")
    elif updated: out.append(f"Published timetable updated for {len(updated)} students.")
    if len(removed) == 1: out.append(f"{removed[0]['name']} ({removed[0]['id']}) removed from the published timetable.")
    elif removed: out.append(f"{len(removed)} students removed from the published timetable.")
    if len(left) == 1: out.append(f"Published timetable not changed for {left[0]['name']} ({left[0]['id']}): {left[0]['why']}.")
    elif left: out.append(f"Published timetable not changed for {len(left)} students: their groups or classes are not on it.")
    if held: out.append(f"{held} students stay on the published timetable until Update the published timetable is pressed.")
    return " ".join(out)

def _setup_copy(setup, changed, rows_now):
    """a shallow copy of a setup whose student rows for the changed keys are the setup's rows now (none when removed)"""
    out = dict(setup); rows, done = [], set()
    for r in setup.get("students") or []:
        k = key(r) if isinstance(r, dict) else None
        if k not in changed: rows.append(r); continue
        if k not in done: rows.extend(copy.deepcopy(rows_now.get(k, []))); done.add(k)
    for k in changed:
        if k not in done: rows.extend(copy.deepcopy(rows_now.get(k, []))); done.add(k)
    out["students"] = rows
    return out

def follow(pairs, by, batch=None):
    """bring the students these (before, after) rows name up to date on the published timetable, reading the setup as
    it is now; None when nothing is published"""
    keys, may_remove, held = touched(pairs)
    renamed = {key(b): key(a) for b, a in pairs if b is not None and a is not None and key(b) != key(a)}
    gone = [key(b) for b, a in pairs if a is None and b is not None]
    single_gone = set(gone) if len(gone) == 1 else set()
    with store._publishing:
        pub = store.published()
        if pub is None: return None
        model = pub["model"]
        rows = [r for r in store.setup_record()["spec"].get("students") or [] if isinstance(r, dict)]
        counts = collections.Counter(key(r) for r in rows)
        rows_now = collections.defaultdict(list)
        for r in rows: rows_now[key(r)].append(r)
        at = {str(s["id"]).strip(): i for i, s in enumerate(model["students"])}
        new_students = list(model["students"])
        updated, added, removed, left, made = [], [], [], [], set()
        order = list(dict.fromkeys(keys)) + sorted(may_remove - set(keys))   # the rows after the save first, then the old keys
        for k in order:
            if k in rows_now:
                row = rows_now[k][0]; why = why_not(row, model, counts)
                if why: left.append(dict(id=k, name=str(row.get("name") or ""), why=why)); continue
                rec = record(row)
                if k not in at: at[k] = len(new_students); new_students.append(rec); added.append(rec); made.add(k)
                elif new_students[at[k]] != rec: new_students[at[k]] = rec; updated.append(rec); made.add(k)
            elif k in may_remove and k in at and (k in single_gone or renamed.get(k) in made):   # a re-numbered row whose new ID did not follow stays
                removed.append(new_students[at[k]])
        if removed:
            out = {id(s) for s in removed}
            new_students = [s for s in new_students if id(s) not in out]
        if updated or added or removed:
            changed = {str(s["id"]).strip() for s in updated + added + removed}
            new = dict(model); new["students"] = new_students
            if isinstance(model.get("setup"), dict): new["setup"] = _setup_copy(model["setup"], changed, rows_now)
            if isinstance(model.get("checked_setup"), dict):
                new["checked_setup"] = new["setup"] if model["checked_setup"] is model.get("setup") else _setup_copy(model["checked_setup"], changed, rows_now)
            checks = E.check_model(new)
            if new.get("choice_problems"): checks["problems"] = list(checks["problems"]) + list(new["choice_problems"])
            checks["ok"] = not checks["problems"]
            new["checks"] = checks
            store.swap_model(new, students=len(new["students"]), ok=checks["ok"], problems=checks["problems"][:20], students_at=store.now(), files_behind=True)
        both = updated + added
        text = _text(both, removed, left, held)
        if text:
            try: history.add(dict(kind=KIND, text=text, where="Students", of=batch, **by))
            except Exception as e: store._warn(e)   # the update is made: a history failure never undoes it
        return dict(updated=[s["id"] for s in updated], added=[s["id"] for s in added], removed=[s["id"] for s in removed],
                    left=left, held=held, text=text)

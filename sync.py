"""The change format: a setup is edited by small operations, so several people
can work on it at once. Same logic as static/sync.js; keep the two in step.

Operations (applied in order):
  ["set", section, id, field, value]            value None removes the field
  ["merge", section, id, field, adds, removes]  list fields merged item by item
  ["add", section, row, after]                  after "" = first, unknown = append
  ["del", section, id]
  ["school", key, value]                        None removes the key
  ["day", level, day, codes]                    None removes the day (and an empty level)
  ["top", key, value]                           any other top-level key
"""
import copy
import json
import secrets
from ttgen import parents
from ttgen.spec import teacher_depts

LISTS = ("venues", "classes", "subjects", "teachers", "blocks", "lessons",
         "rules", "students", "combinations", "roles", "choices")
MERGE = {"teachers": ("can_teach",), "students": ("groups",)}
_ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789"
_RESERVED_TOP = set(LISTS) | {"school", "day_structure"}
_ARITY = {"set": 5, "merge": 6, "add": 4, "del": 3, "school": 3, "day": 4, "top": 3}


def new_id():
    return "".join(secrets.choice(_ALPHABET) for _ in range(10))


def _canon(x):
    return json.dumps(x, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _rows(spec, section):
    rows = spec.get(section)
    return rows if isinstance(rows, list) else []


def _dict_at(parent, key):
    """parent[key] as a dict, replacing anything else (null, text) with {}."""
    if not isinstance(parent.get(key), dict):
        parent[key] = {}
    return parent[key]


def _find(spec, section, rid):
    for row in _rows(spec, section):
        if isinstance(row, dict) and row.get("_id") == rid:
            return row
    return None


def lesson_dept(spec, row):
    """The department of a lesson row: that of its subject on the subjects table (first match by name), trimmed; "" if none."""
    name = row.get("subject") if isinstance(row, dict) else None
    for s in _rows(spec, "subjects"):
        if isinstance(s, dict) and name and s.get("subject") == name:
            return str(s.get("dept") or "").strip()
    return ""


def ensure_ids(spec):
    """Give every list row lacking an `_id` one. True if any was added."""
    added = False
    for section in LISTS:
        rows = _rows(spec, section)
        used = {r.get("_id") for r in rows if isinstance(r, dict)}
        for row in rows:
            if isinstance(row, dict) and not row.get("_id"):
                rid = new_id()
                while rid in used:
                    rid = new_id()
                used.add(rid)
                row["_id"] = rid
                added = True
    rules = _rows(spec, "rules")
    for c in _rows(spec, "choices"):   # a choice about a rule follows the rule by its id, not by its place in the list
        i = c.get("rule") if isinstance(c, dict) else None
        if isinstance(i, int) and not isinstance(i, bool) and not c.get("rule_id"):
            r = rules[i] if 0 <= i < len(rules) else None
            c["rule_id"] = r.get("_id") if isinstance(r, dict) else None
            del c["rule"]
            added = True
    return added


def _clean_row(row):
    """A row as sent in an `add`: no `_` keys but `_id`, no nulls."""
    return {k: v for k, v in row.items()
            if v is not None and (k == "_id" or not k.startswith("_"))}


def _field(row, key):
    return row.get(key)


def _items(row, key):
    v = row.get(key)
    return v if isinstance(v, list) else []


def diff(base, cur):
    ops = []
    for section in LISTS:
        brows = [r for r in _rows(base, section) if isinstance(r, dict) and r.get("_id")]
        crows = [r for r in _rows(cur, section) if isinstance(r, dict) and r.get("_id")]
        bmap = {r["_id"]: r for r in brows}
        cmap = {r["_id"]: r for r in crows}
        for r in brows:
            if r["_id"] not in cmap:
                ops.append(["del", section, r["_id"]])
        prev = ""
        for r in crows:
            if r["_id"] not in bmap:
                ops.append(["add", section, _clean_row(r), prev])
            prev = r["_id"]
        merged = MERGE.get(section, ())
        for r in crows:
            b = bmap.get(r["_id"])
            if b is None:
                continue
            fields = sorted({k for k in list(r) + list(b) if not k.startswith("_")})
            for f in fields:
                if f in merged:
                    bi, ci = _items(b, f), _items(r, f)
                    bk, ck = {_canon(i) for i in bi}, {_canon(i) for i in ci}
                    adds = [i for i in ci if _canon(i) not in bk]
                    removes = [i for i in bi if _canon(i) not in ck]
                    if adds or removes:
                        ops.append(["merge", section, r["_id"], f, adds, removes])
                elif _canon(_field(b, f)) != _canon(_field(r, f)):
                    ops.append(["set", section, r["_id"], f, _field(r, f)])
    bs, cs = base.get("school") or {}, cur.get("school") or {}
    for k in sorted(set(bs) | set(cs)):
        if _canon(bs.get(k)) != _canon(cs.get(k)):
            ops.append(["school", k, cs.get(k)])
    bd, cd = base.get("day_structure") or {}, cur.get("day_structure") or {}
    for level in sorted(set(bd) | set(cd)):
        bl, cl = bd.get(level) or {}, cd.get(level) or {}
        for day in sorted(set(bl) | set(cl)):
            if _canon(bl.get(day)) != _canon(cl.get(day)):
                ops.append(["day", level, day, cl.get(day)])
    keys = {k for k in list(base) + list(cur)
            if k not in _RESERVED_TOP and not k.startswith("_")}
    for k in sorted(keys):
        if _canon(base.get(k)) != _canon(cur.get(k)):
            ops.append(["top", k, cur.get(k)])
    return ops


def _apply_one(spec, op):
    """Apply one operation; False if it was skipped."""
    name = op[0]
    if name in ("set", "merge", "add", "del") and op[1] not in LISTS:
        return False
    if name == "set":
        _, section, rid, field, value = op
        row = _find(spec, section, rid)
        if row is None or field.startswith("_"):
            return False
        if value is None:
            row.pop(field, None)
        else:
            row[field] = copy.deepcopy(value)
    elif name == "merge":
        _, section, rid, field, adds, removes = op
        row = _find(spec, section, rid)
        if row is None or field.startswith("_"):
            return False
        gone = {_canon(i) for i in removes}
        items = [i for i in _items(row, field) if _canon(i) not in gone]
        have = {_canon(i) for i in items}
        for i in adds:
            if _canon(i) not in have:
                have.add(_canon(i))
                items.append(copy.deepcopy(i))
        row[field] = items
    elif name == "add":
        _, section, row, after = op
        if not isinstance(row, dict) or not row.get("_id") or _find(spec, section, row["_id"]):
            return False
        if not isinstance(spec.get(section), list):
            spec[section] = []
        rows = spec[section]
        pos = len(rows)
        if after == "":
            pos = 0
        else:
            for i, r in enumerate(rows):
                if isinstance(r, dict) and r.get("_id") == after:
                    pos = i + 1
                    break
        rows.insert(pos, copy.deepcopy(row))
    elif name == "del":
        row = _find(spec, op[1], op[2])
        if row is None:
            return False
        spec[op[1]] = [r for r in spec[op[1]] if r is not row]
    elif name == "school":
        school = _dict_at(spec, "school")
        if op[2] is None:
            school.pop(op[1], None)
        else:
            school[op[1]] = copy.deepcopy(op[2])
    elif name == "day":
        _, level, day, codes = op
        days = _dict_at(spec, "day_structure")
        if codes is None:
            if isinstance(days.get(level), dict):
                days[level].pop(day, None)
                if not days[level]:
                    del days[level]
        else:
            _dict_at(days, level)[day] = codes
    else:  # top
        key = op[1]
        if key in _RESERVED_TOP or key.startswith("_"):
            return False
        if op[2] is None:
            spec.pop(key, None)
        else:
            spec[key] = copy.deepcopy(op[2])
    return True


def apply(spec, ops):
    """Apply `ops` to `spec` in place; returns how many were skipped."""
    skipped = 0
    for op in ops:
        if not _well_formed(op):
            skipped += 1
        elif not _apply_one(spec, op):
            skipped += 1
    return skipped


# positions that must be strings, per operation (section / id / field / key names)
_STR_ARGS = {"set": (1, 2, 3), "merge": (1, 2, 3), "add": (1,), "del": (1, 2),
             "school": (1,), "day": (1, 2), "top": (1,)}


PARENTS_WHY = "Only the committee can change these lessons: their teachers are the class's form teachers."
_PARENTS_FIELDS = ("teachers", "by_hand", "subject", "block", "code_override", "classes", "level")


def _head_lessons_why(spec, op):
    """The lessons the Class Parents take are the committee's: a head may not change a staffed row's teachers, mark,
    subject, block, code, classes or level, delete it, or make a row staffed that was not (by an add or a set). Judged
    from the row as it is and as the op would leave it. Other changes to lessons stay open."""
    name = op[0]
    if _ARITY.get(name) != len(op) or not all(isinstance(op[i], str) for i in _STR_ARGS[name]):
        return "Department heads cannot send that change."    # malformed: apply would skip it, and the checks below read its positions
    if name == "merge":    # lessons have no merged fields; judged on the row as an empty list in that field would leave it
        row = _find(spec, "lessons", op[2])
        after = dict(row or {}, **{op[3]: []})
        return PARENTS_WHY if row is not None and (parents.staffed(spec, row) or parents.staffed(spec, after)) else "Department heads cannot send that change."
    if name == "add":
        return PARENTS_WHY if len(op) > 2 and isinstance(op[2], dict) and parents.staffed(spec, op[2]) else None
    row = _find(spec, "lessons", op[2]) if len(op) > 2 else None
    if row is None:
        return None
    was = parents.staffed(spec, row)
    if name == "del":
        return PARENTS_WHY if was else None
    if len(op) < 4 or not isinstance(op[3], str):
        return None
    if was and op[3] in _PARENTS_FIELDS:
        return PARENTS_WHY
    if not was and name == "set":
        after = dict(row)
        if op[4] is None:
            after.pop(op[3], None)
        else:
            after[op[3]] = op[4]
        return PARENTS_WHY if parents.staffed(spec, after) else None
    return None


def _head_why(spec, op):
    """None if a head of department may make the one operation `op` on `spec`, else a sentence saying why not."""
    if not isinstance(op, list) or not op or not isinstance(op[0], str):
        return "Department heads cannot send that change."
    name = op[0]
    if name in ("school", "day", "top"):
        return "Department heads cannot change the school details, the day structure or other settings."
    section = op[1] if len(op) > 1 else None
    if section == "lessons":
        return _head_lessons_why(spec, op)
    if section == "blocks":
        return None
    if section != "teachers":
        return f"Department heads cannot change {section if isinstance(section, str) else 'that'}."
    if name == "set" and len(op) > 3 and op[3] == "dept2":
        return "Only the committee gives a teacher a second department."
    if name == "add" and len(op) > 2 and isinstance(op[2], dict):
        return None
    if name in ("set", "del") and len(op) > 2 and (name == "del" or len(op) > 3 and op[3] != "provisional"):
        row = _find(spec, "teachers", op[2])
        # a missing row is skipped by apply; a teacher added earlier in the same batch is not in `spec` yet and is
        # forced provisional, so edits to it are fine
        if row is None or row.get("provisional") == "Yes":
            return None
        return "Department heads can change a teacher's details only while the teacher is provisional."
    return "Department heads can only add a teacher, or edit a provisional teacher."


OTHER_DEPT = "This row is another department's: only its head or the committee can change it."
NO_SUBJECT = "Choose a subject of your department for this row first."
BAND_OTHERS = "This band holds another department's groups: only the committee can rename or delete it."
BAND_NOT_YOURS = "This band holds none of your department's groups."
TEACHER_DEPT = "You can put a new teacher only in your own department."
BAND_NAME_TAKEN = "Another band already has that name."
OTHER_TEACHER = "This teacher is another department's: only its head or the committee can change them."


def _well_formed(op):
    """An operation apply would make: a known name, the right length, names where names go, lists where a merge needs them."""
    return (isinstance(op, list) and bool(op) and isinstance(op[0], str) and _ARITY.get(op[0]) == len(op)
            and all(isinstance(op[i], str) for i in _STR_ARGS[op[0]])
            and not (op[0] == "merge" and not (isinstance(op[4], list) and isinstance(op[5], list))))


def _blank(v):
    return v is None or (isinstance(v, str) and not v.strip())


def _dept_of(v):
    return "" if v is None else str(v).strip()


def _dept_list(depts):
    """A head's departments, trimmed, blanks dropped, in order; None (the shared heads' code: every department) stays None."""
    if depts is None:
        return None
    if isinstance(depts, str):
        depts = [depts]
    out = []
    for d in depts if isinstance(depts, (list, tuple, set, frozenset)) else []:
        d = _dept_of(d)
        if d and d not in out:
            out.append(d)
    return out


def band_lessons(spec, block_row):
    """The lessons of a band: those whose block is the band's name and whose level is the band's level (a band with no
    name holds none)."""
    if not isinstance(block_row, dict) or _blank(block_row.get("block")):
        return []
    name, level = block_row.get("block"), block_row.get("level")
    return [x for x in _rows(spec, "lessons") if isinstance(x, dict) and x.get("block") == name and x.get("level") == level]


def _name_taken(spec, row, but=None):
    """True when another band than `but` on `spec` has the name and level of the band row `row` (a blank name is none)."""
    if not isinstance(row, dict) or _blank(row.get("block")):
        return False
    return any(isinstance(b, dict) and b is not but and b.get("block") == row.get("block") and b.get("level") == row.get("level")
               for b in _rows(spec, "blocks"))


def _band_after(band, op):
    """The band row as the set or merge `op` would leave it."""
    one = {"blocks": [copy.deepcopy(band)]}
    _apply_one(one, op)
    return one["blocks"][0]


def _band_change(spec, op):
    """The band row that `op` renames, deletes or moves to another level (any of which takes the band away from the
    groups in it), or None when `op` is not such a change to a band on `spec`."""
    if not _well_formed(op) or op[1] != "blocks":
        return None
    if op[0] == "del" or (op[0] in ("set", "merge") and op[3] in ("block", "level")):
        return _find(spec, "blocks", op[2])
    return None


def _carry_index(ops):
    """Where the lesson operations are that can carry a band's groups along with a band change: (row id, "block", new
    block) -> indexes of the sets of that row's block to that value (a rename's); (row id, "del") -> indexes of the
    row's delete, of its block emptied, or of its own code set (a delete's: its groups deleted or released)."""
    at = {}
    for j, o in enumerate(ops):
        if not _well_formed(o) or o[1] != "lessons" or o[0] not in ("set", "del"):
            continue
        keys = [(o[2], "del")] if o[0] == "del" or o[3] == "code_override" else []
        if o[0] == "set" and o[3] == "block":
            keys = [(o[2], "block", _canon(o[4]))] + ([(o[2], "del")] if _blank(o[4]) else [])
        for k in keys:
            at.setdefault(k, []).append(j)
    return at


def _carried(ops, i, groups, at, taken):
    """The indexes of the operations after ops[i] (a band change) that carry the band's groups (`groups`) along: for a
    rename, a group's block set to the new name; for a delete, a group deleted or released. Each is carried by one band
    change at most (`taken`). Band changes come in batch order, so what a key of `at` lists is used up here: carried now,
    or never carriable again (at or before i, or taken)."""
    op = ops[i]
    kind = ("block", _canon(op[4])) if op[0] == "set" and op[3] == "block" else ("del",) if op[0] == "del" else None
    out = []
    for x in groups if kind else []:
        found = at.pop((x["_id"],) + kind, None) if isinstance(x.get("_id"), str) else None    # an op names a row by a string
        out.extend(j for j in found or [] if j > i and j not in taken)
    return out


def _dept_cache(spec):
    """lesson_dept(spec, row) remembered by subject name: a head's batch never changes the subjects."""
    seen = {}
    def dept(row):
        name = row.get("subject") if isinstance(row, dict) else None
        try:
            if name not in seen:
                seen[name] = lesson_dept(spec, row)
            return seen[name]
        except TypeError:    # a name that is not a plain value
            return lesson_dept(spec, row)
    return dept


def _dept_why(spec, op, mine, dept):
    """The department rules, after today's (`_head_why` found nothing): None if a head of the departments `mine` may make
    `op` on `spec`, else a sentence (`dept`: lesson_dept for `spec`). A band rename, delete or change of level is judged
    with the groups it carries, in `head_split`."""
    if not _well_formed(op):
        return None    # apply skips it
    name, section = op[0], op[1]
    if section == "lessons":
        if name == "add":
            d = dept(op[2])
            return None if d in mine else OTHER_DEPT if d else NO_SUBJECT
        row = _find(spec, "lessons", op[2])
        if row is None:
            return None    # apply skips it
        after = dict(row)
        if name == "set":
            if op[4] is None:
                after.pop(op[3], None)
            else:
                after[op[3]] = op[4]
        return None if dept(row) in mine and dept(after) in mine else OTHER_DEPT
    if section == "blocks":
        if name == "add":
            return BAND_NAME_TAKEN if _name_taken(spec, op[2]) else None
        row = _find(spec, "blocks", op[2])
        groups = band_lessons(spec, row) if row is not None else []
        return None if not groups or any(dept(x) in mine for x in groups) else BAND_NOT_YOURS
    if section == "teachers":
        def theirs(t):
            return all(d in mine for d in teacher_depts(t))
        if name == "add":
            t = op[2] if isinstance(op[2], dict) else {}
            return None if _dept_of(t.get("dept")) in mine and theirs(t) else TEACHER_DEPT
        row = _find(spec, "teachers", op[2]) if name in ("set", "del") else None
        if row is not None and not theirs(row):
            return OTHER_TEACHER
        if name == "set" and op[3] == "dept" and _dept_of(op[4]) not in mine:
            return TEACHER_DEPT
        if row is not None and name == "set":
            after = dict(row)
            if op[4] is None:
                after.pop(op[3], None)
            else:
                after[op[3]] = op[4]
            if not theirs(after):
                return OTHER_TEACHER
        return None    # theirs; or not on the setup: one added earlier in this batch (in their department, as its add is judged), or none (apply skips it)
    return None


def _head_pass(spec, ops, mine, forced, rest=None):
    """One pass of head_split: (allowed, refused, mixed). `forced`: band change index -> the sentence its whole group is
    refused with; `rest`: the sentence every other band change's whole group is refused with (None: judged as usual);
    `mixed`: the band changes allowed in this pass part of whose group today's rules refused."""
    allowed, refused, mixed = [], [], {}
    work, copied = spec, set()   # each op is judged on the setup as the allowed ones before it in this batch leave it (a row added, then changed, in one batch)
    group, verdict = {}, {}      # op index -> index of the band change it is judged with; band change index -> its sentence (None: allowed)
    at, dept = (_carry_index(ops), _dept_cache(spec)) if mine is not None else (None, None)
    for i, op in enumerate(ops):
        why = _head_why(work, op)    # today's rules first
        if mine is not None and i not in group:
            band = _band_change(work, op)
            if band is not None:
                groups = band_lessons(work, band)
                group[i] = i
                for j in _carried(ops, i, groups, at, group):
                    group[j] = i
                verdict[i] = (forced.get(i) or (None if all(dept(x) in mine for x in groups) else BAND_OTHERS)
                              or (BAND_NAME_TAKEN if op[0] != "del" and _name_taken(work, _band_after(band, op), band) else None)
                              or rest)
        if mine is not None:
            if why is None:
                why = verdict[group[i]] if i in group else _dept_why(work, op, mine, dept)
            elif i in group and verdict[group[i]] is None:
                mixed.setdefault(group[i], why)
        if why:
            refused.append((i, why))
            continue
        allowed.append(op)
        if isinstance(op, list) and len(op) > 1 and op[1] in ("lessons", "blocks"):
            if work is spec:
                work = dict(spec)
            if op[1] not in copied:
                copied.add(op[1])
                work[op[1]] = copy.deepcopy(spec.get(op[1]) if isinstance(spec.get(op[1]), list) else [])
            apply(work, [op])
    return allowed, refused, mixed


_HEAD_RETRIES = 3


def head_split(spec, ops, depts=None):
    """(allowed, refused): the operations in `ops` a head of department may make on `spec`, in order, and the others as
    (index in ops, sentence). Heads may change lessons and blocks, add a teacher, and the details of a teacher who is
    still provisional (or added earlier in the same batch), except a second department, which only the committee gives.

    `depts`: None for the shared heads' code (every department, as above); else the head's own departments, and then,
    after the rules above: a lesson row only when its department is theirs both as it is and as the op leaves it; a band
    when it holds one of their groups (or none), and never under the name of another band at its level; a teacher only
    one of their departments' (as it is and as the op leaves it), a new one only in them. A band's rename or delete is
    judged with the operations carrying its groups along, as one: all of it when every group in the band is theirs,
    else none (and none when today's rules refuse any of it). Everything else is judged one operation at a time."""
    mine, forced, rest = _dept_list(depts), {}, None
    for tries in range(_HEAD_RETRIES + 1):
        # a band change refused whole is judged again from the start, so what follows it sees the setup without it; the
        # last try refuses every band change still open whole (with the sentence that refused the last), so a crafted
        # batch costs a few passes, not one per band change (it is judged under the setup's lock)
        allowed, refused, mixed = _head_pass(spec, ops, mine, forced, rest)
        if not mixed:
            break
        forced.update(mixed)
        if tries == _HEAD_RETRIES - 1:
            rest = next(iter(mixed.values()))
    return allowed, refused


def head_may(spec, ops, depts=None):
    """None if a head of department may make every operation in `ops` on `spec`, else a sentence naming the first they may not."""
    refused = head_split(spec, ops, depts)[1]
    return refused[0][1] if refused else None


def head_prepare(ops, depts=None):
    """A head's batch made ready to judge, in place: a teacher a head adds is provisional until the committee confirms,
    with no second department (the committee gives that); with `depts`, in one of the head's departments (the first,
    when the one sent is not theirs)."""
    mine = _dept_list(depts)
    for op in ops if isinstance(ops, list) else []:
        if isinstance(op, list) and len(op) == 4 and op[0] == "add" and op[1] == "teachers" and isinstance(op[2], dict):
            op[2]["provisional"] = "Yes"
            op[2].pop("dept2", None)
            if mine and _dept_of(op[2].get("dept")) not in mine:
                op[2]["dept"] = mine[0]

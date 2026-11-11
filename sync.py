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
        if (not isinstance(op, list) or not op or not isinstance(op[0], str) or _ARITY.get(op[0]) != len(op)
                or not all(isinstance(op[i], str) for i in _STR_ARGS[op[0]])
                or (op[0] == "merge" and not (isinstance(op[4], list) and isinstance(op[5], list)))):
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
    if name == "merge" and len(op) > 3 and op[3] == "can_teach":
        return None
    if name == "add" and len(op) > 2 and isinstance(op[2], dict):
        return None
    if name in ("set", "del") and len(op) > 2 and (name == "del" or len(op) > 3 and op[3] != "provisional"):
        row = _find(spec, "teachers", op[2])
        # a missing row is skipped by apply; a teacher added earlier in the same batch is not in `spec` yet and is
        # forced provisional, so edits to it are fine
        if row is None or row.get("provisional") == "Yes":
            return None
        return "Department heads can change a teacher's details only while the teacher is provisional."
    return "Department heads can only change who a teacher can teach, add a teacher, or edit a provisional teacher."


def head_split(spec, ops):
    """(allowed, refused): the operations in `ops` a head of department may make on `spec`, in order, and the others as
    (index in ops, sentence). Heads may change lessons and blocks, who a teacher can teach, add a teacher, and the
    details of a teacher who is still provisional (or added earlier in the same batch)."""
    allowed, refused = [], []
    for i, op in enumerate(ops):
        why = _head_why(spec, op)
        if why:
            refused.append((i, why))
        else:
            allowed.append(op)
    return allowed, refused


def head_may(spec, ops):
    """None if a head of department may make every operation in `ops` on `spec`, else a sentence naming the first they may not."""
    refused = head_split(spec, ops)[1]
    return refused[0][1] if refused else None

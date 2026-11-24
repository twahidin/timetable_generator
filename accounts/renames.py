"""A teacher renamed on step 4: the pairs (an old name on the timetable published now, the name its row has now) a publish
asks about, and why a publish with the choices made is refused. Nothing here writes: people.join and people.drop do, inside
a people.update"""
import copy
from accounts import people

OWN = "You cannot remove your own account."
LAST_ADMIN = "{} is the last admin: make another admin first."
NEEDS_ADMIN = "An admin has to publish this one: {new}'s account must follow or be removed."
CHOOSE = "Choose first for {old}, now {new}: the same person, or a different person."
NO_JOIN = "{new} is switched off, so no admin could sign in afterwards: switch {new} on first."
CHOICES = ("same", "different")

def kept(rec, linked):
    """what a cleaned record has that is worth keeping, as words in a fixed order; departments alone and sign-ins are not words"""
    ex, out = rec["extras"], []
    if rec["group"] is not None: out.append(people.LABELS[rec["group"]])
    if ex["timetable"]: out.append("Timetable committee")
    if ex["relief"]: out.append("Relief team")
    if ex["exams"] is not None: out.append("Exams and events")
    if ex["admin"]: out.append("Admin")
    if rec["username"]: out.append("username")
    if rec["pw"]: out.append("password")
    if rec["google"]: out.append("Google sign-in")
    if rec["note"].strip(): out.append("a note")
    if rec["off"]: out.append("switched off")
    if rec["added"]: out.append("added by name")
    if linked: out.append("Telegram")
    return out

def _rows(spec):
    rows = spec.get("teachers") if isinstance(spec, dict) else None
    return [t for t in rows if isinstance(t, dict)] if isinstance(rows, list) else []

def _no_join(data, old, new, admins):
    """why old's account cannot be joined onto new: the join (tried on a copy, data is never changed) would leave no admin who
    can sign in while there is one now; None when it can, or when the trial itself fails (the publish's own join then checks
    the same on the records as they are, inside its update)"""
    if not admins: return None
    d = copy.deepcopy(data)
    try: people.join(d, old, new)
    except Exception: return None
    return None if people.usable_admins(d) else NO_JOIN.format(new=new)

def pairs(old_names, spec, data, linked, me=None):
    """one dict per old name the setup's rows claim in their earlier_names (in the setup's teacher order): only a name on the
    timetable published now (old_names), that no teacher row has now, with something worth keeping; an old name makes one pair,
    for the first row that claims it. A row's name is read stripped, as the people list reads it. earlier_names is anyone's
    setup data: read only as far as that"""
    old_names, linked = set(old_names or ()), set(linked or ())
    rows = _rows(spec)
    now = {t["name"].strip() for t in rows if isinstance(t.get("name"), str)}
    admins = people.usable_admins(data)
    out, seen = [], set()
    for t in rows:
        new = t.get("name")
        if not (isinstance(new, str) and new.strip()): continue
        new = new.strip()
        e = t.get("earlier_names")
        for old in e if isinstance(e, list) else ():
            if not isinstance(old, str) or old in seen or old not in old_names or old in now: continue
            has = kept(people.record(data, old), old in linked)
            if not has: continue
            seen.add(old)
            r = people.record(data, new)
            no_remove = OWN if old == me else LAST_ADMIN.format(old) if admins == [old] else None
            account, joins = any(w != "Telegram" for w in has), not (r["username"] or r["pw"] or r["google"])
            out.append(dict(old=old, new=new, has=has, account=account, telegram=old in linked, joins=joins, no_remove=no_remove,
                            no_join=_no_join(data, old, new, admins) if account and joins else None))
    return out

def read_choices(v):
    """the publish body's renames ([{old, new, choice}, ...]) -> {(old, new): choice}. Anything else is no choice: not a list,
    an item that is not a dict, a value that is not a string, a choice not in CHOICES, and a pair given two different choices"""
    out, bad = {}, set()
    for x in v if isinstance(v, list) else ():
        if not isinstance(x, dict): continue
        o, n, c = x.get("old"), x.get("new"), x.get("choice")
        if not (isinstance(o, str) and isinstance(n, str) and isinstance(c, str)) or c not in CHOICES: continue
        if out.get((o, n), c) != c: bad.add((o, n))
        out[(o, n)] = c
    return {k: c for k, c in out.items() if k not in bad}

def _choice(choices, p):
    v = choices.get((p["old"], p["new"]))
    return v if v in CHOICES else None

def _removes(p, choice):
    """whether this choice removes the old account (a different person; or the same person whose account cannot join the new name's)"""
    return p["account"] and (choice == "different" or (choice == "same" and not p["joins"]))

def refusal(pairs, choices, admin):
    """why a publish with these choices ({(old, new): "same" | "different"}, as read_choices gives them) is refused, the first
    that applies; None when it may go. A choice belongs to the pair: one made for another new name is no choice"""
    choices = choices if isinstance(choices, dict) else {}
    for p in pairs:
        if p["account"] and admin is not True: return NEEDS_ADMIN.format(new=p["new"])
    for p in pairs:
        if _choice(choices, p) is None: return CHOOSE.format(old=p["old"], new=p["new"])
    for p in pairs:
        if p["no_remove"] and _removes(p, _choice(choices, p)): return p["no_remove"]
    for p in pairs:
        if p.get("no_join") and _choice(choices, p) == "same" and p["account"] and p["joins"]: return p["no_join"]
    return None

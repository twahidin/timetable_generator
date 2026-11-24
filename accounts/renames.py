"""A teacher renamed on step 4: the pairs (an old name on the timetable published now, the name its row has now) a publish
asks about, and why a publish with the choices made is refused. Nothing here writes: people.join and people.drop do, inside
a people.update"""
from accounts import people

OWN = "You cannot remove your own account."
LAST_ADMIN = "{} is the last admin: make another admin first."
NEEDS_ADMIN = "An admin has to publish this one: {new}'s account must follow or be removed."
CHOOSE = "Choose first for {old}, now {new}: the same person, or a different person."
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

def pairs(old_names, spec, data, linked, me=None):
    """one dict per old name the setup's rows claim in their earlier_names (in the setup's teacher order): only a name on the
    timetable published now (old_names), that no teacher row has now, with something worth keeping; an old name makes one pair,
    for the first row that claims it. earlier_names is anyone's setup data: read only as far as that"""
    old_names, linked = set(old_names or ()), set(linked or ())
    rows = _rows(spec)
    now = {t["name"] for t in rows if isinstance(t.get("name"), str)}
    admins = people.usable_admins(data)
    out, seen = [], set()
    for t in rows:
        new = t.get("name")
        if not (isinstance(new, str) and new.strip()): continue
        e = t.get("earlier_names")
        for old in e if isinstance(e, list) else ():
            if not isinstance(old, str) or old in seen or old not in old_names or old in now: continue
            has = kept(people.record(data, old), old in linked)
            if not has: continue
            seen.add(old)
            r = people.record(data, new)
            no_remove = OWN if old == me else LAST_ADMIN.format(old) if admins == [old] else None
            out.append(dict(old=old, new=new, has=has, account=any(w != "Telegram" for w in has), telegram=old in linked,
                            joins=not (r["username"] or r["pw"] or r["google"]), no_remove=no_remove))
    return out

def _removes(p, choice):
    """whether this choice removes the old account (a different person; or the same person whose account cannot join the new name's)"""
    return p["account"] and (choice == "different" or (choice == "same" and not p["joins"]))

def refusal(pairs, choices, admin):
    """why a publish with these choices ({old: "same" | "different"}) is refused, the first that applies; None when it may go"""
    choices = choices if isinstance(choices, dict) else {}
    for p in pairs:
        if p["account"] and admin is not True: return NEEDS_ADMIN.format(new=p["new"])
    for p in pairs:
        if choices.get(p["old"]) not in CHOICES: return CHOOSE.format(old=p["old"], new=p["new"])
    for p in pairs:
        if p["no_remove"] and _removes(p, choices[p["old"]]): return p["no_remove"]
    return None

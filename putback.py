"""The rules of Put back: which recorded changes can be put back, and the setup operations that do it.
A save (one batch of setup entries) or one account entry is a unit; a unit is put back whole or not at all. A save's
unit also holds the app's follow-ups to it (kind "app", `follows` its batch: the Class Parents' lessons the app put
right after it): they are put back first, and they too must be untouched since."""
import datetime

import history
import sync

TOUCH_KINDS = {"setup", "app", "setup-replaced", "account"}
PUTTABLE = {"group", "depts", "relief", "exams", "admin", "note", "off"}
_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
_ADMIN = "Can't put back a new person, a username or a password here: change it on the admin page."
_OLD = "Can't put back: this change was recorded before Put back existed. Change it on its step."
_SINCE = "Can't put back: this was changed again since."


def unit_of(e):
    """the unit a history entry belongs to: "b:" + its batch, "a:" + its id for an account change; None for the rest"""
    if not isinstance(e, dict):
        return None
    if e.get("kind") == "setup" and e.get("batch"):
        return "b:" + str(e["batch"])
    if e.get("kind") == "account" and e.get("changes") and e.get("id"):
        return "a:" + str(e["id"])
    return None


def follow_up(e, batch):
    """is e one of the app's follow-ups to the save `batch`?"""
    return isinstance(e, dict) and e.get("kind") == "app" and batch is not None and e.get("follows") == batch


def own(unit_entries):
    """the unit's own entries: the save's or the account change's, without the app's follow-ups"""
    return [e for e in unit_entries if e.get("kind") != "app"]


def _window(ts):
    return history.read(kinds=TOUCH_KINDS, since=ts - 60, until=ts + 60, limit=10 ** 7)


def gather(entry_id):
    """(unit, the unit's entries oldest first, the TOUCH_KINDS entries newer than its newest one, newest first), or None
    when the id is not in the history or its entry has no unit. A save's entries and the app's follow-ups to it are
    written within a second of each other, so they are looked for in a minute around the entry"""
    e = history.find(entry_id)
    unit = unit_of(e)
    if unit is None:
        return None
    ts = e.get("ts") or 0
    if unit.startswith("a:"):
        ents = [e]
    else:
        ents = sorted((x for x in _window(ts) if unit_of(x) == unit or follow_up(x, e.get("batch"))), key=lambda x: x["id"])
    last = ents[-1]["id"]
    since = min(x.get("ts") or 0 for x in ents) - 60
    newer = [x for x in history.read(kinds=TOUCH_KINDS, since=since, limit=10 ** 7) if x["id"] > last]
    return unit, ents, newer


def _touches(e):
    """(what the entry touches, what its put back needs), as sets of keys"""
    kind = e.get("kind")
    if kind == "setup-replaced":
        return set(), set()
    if kind == "account":
        keys = {("a", c.get("name"), c.get("field")) for c in e.get("changes") or [] if isinstance(c, dict)}
        return keys, keys
    op, sec, row, field = e.get("op"), e.get("section"), e.get("row"), e.get("field")
    if op in ("set", "merge"):
        return {("f", sec, row, field), ("r", sec, row)}, {("f", sec, row, field), ("d", sec, row)}
    if op in ("add", "del"):
        return {("r", sec, row), ("d", sec, row)}, {("r", sec, row)}
    if op in ("school", "day", "top"):
        k = ("p", sec, e.get("level"), field)
        return {k}, {k}
    return set(), set()


def _who(e):
    w = str(e.get("as") or "someone")
    return "the app" if w == "The app" else w


def _blocker_sentence(unit, b):
    when = history.short_when(b.get("ts") or 0)
    if b.get("kind") == "setup-replaced":
        return f"Can't put back: the whole setup was replaced on {when}. Use a saved copy on the committee page."
    if b.get("putback") == unit:
        return f"Already put back by {_who(b)} on {when}"
    return f"Can't put back: {_who(b)} changed this again on {when}"


def _iso_day(iso):
    """"14 Nov 2027" for 2027-11-14, the way the pages write a date"""
    try:
        d = datetime.date.fromisoformat(iso)
    except (TypeError, ValueError):
        return str(iso)
    return f"{d.day} {_MONTHS[d.month - 1]} {d.year}"


def why_not(unit_entries, newer, today=None):
    """None when the unit can be put back, else the sentence saying why not. newer: the TOUCH_KINDS entries after the
    unit, newest first; the closest later change is the one named. What the app's follow-ups in the unit touched must be
    untouched too"""
    if not own(unit_entries):
        return _OLD
    first = own(unit_entries)[0]
    account = first.get("kind") == "account"
    if account:
        changes = [c for e in unit_entries for c in e.get("changes") or [] if isinstance(c, dict)]
        if any(c.get("field") not in PUTTABLE for c in changes):
            return _ADMIN
        today = today or datetime.datetime.now(history.SCHOOL_TZ).date()
        for c in changes:
            was = c.get("was")
            if c.get("field") == "exams" and isinstance(was, str) and was < today.isoformat():
                return f"Can't put back: the Exams and events date ({_iso_day(was)}) has passed."
    elif any(e.get("op") == "day" and not e.get("level") for e in unit_entries):
        return _OLD
    unit = unit_of(first)
    mine = {e.get("id") for e in unit_entries}
    batch = None if account else first.get("batch")
    need = set()
    for e in unit_entries:
        need |= _touches(e)[1]
    for b in reversed(newer):   # newest first in, so the oldest end is the first change after the unit
        if b.get("id") in mine or (batch is not None and (b.get("batch") == batch or b.get("follows") == batch)):
            continue
        if b.get("kind") == "setup-replaced":
            if not account:
                return _blocker_sentence(unit, b)
            continue
        if _touches(b)[0] & need:
            return _blocker_sentence(unit, b)
    return None


def reverse(unit_entries):
    """the setup operations that undo the save, newest first"""
    out = []
    for e in reversed(unit_entries):
        op, sec, row, field, was = e.get("op"), e.get("section"), e.get("row"), e.get("field"), e.get("was")
        if op in ("set", "merge"):
            out.append(["set", sec, row, field, was])
        elif op == "add":
            out.append(["del", sec, row])
        elif op == "del":
            out.append(["add", sec, was, e.get("after")])
        elif op == "school":
            out.append(["school", field, was])
        elif op == "day":
            out.append(["day", e.get("level"), field, was])
        elif op == "top":
            out.append(["top", field, was])
    return out


def _canon_eq(a, b):
    return sync._canon(a) == sync._canon(b)


def changed_since(spec, unit_entries):
    """None when every row and field is still as the save and the app's follow-ups to it left it, else the sentence"""
    last = {}
    for e in unit_entries:
        op = e.get("op")
        if e.get("kind") not in ("setup", "app") or op is None:
            continue
        last[(op, e.get("section"), e.get("row"), e.get("level"), e.get("field") if op not in ("add", "del") else None)] = e
    for (op, sec, row, level, field), e in last.items():
        if op in ("set", "merge"):
            r = sync._find(spec, sec, row)
            ok = r is not None and _canon_eq(r.get(field), e.get("now"))
        elif op == "add":
            ok = sync._find(spec, sec, row) is not None
        elif op == "del":
            ok = sync._find(spec, sec, row) is None
        elif op == "school":
            s = spec.get("school")
            ok = _canon_eq(s.get(field) if isinstance(s, dict) else None, e.get("now"))
        elif op == "day":
            d = spec.get("day_structure")
            lv = d.get(level) if isinstance(d, dict) else None
            ok = _canon_eq(lv.get(field) if isinstance(lv, dict) else None, e.get("now"))
        elif op == "top":
            ok = _canon_eq(spec.get(field), e.get("now"))
        else:
            ok = True
        if not ok:
            return _SINCE
    return None


def annotate(shown, newer_all, may):
    """sets e["back"] on each entry of `shown` whose unit may(unit_entries) allows: {"unit", "n", "ok", "why"}, n the
    unit's own entries (not the app's follow-ups). The caller passes in newer_all every TOUCH_KINDS entry from 60
    seconds before the oldest shown entry on, newest first; the unit's entries are collected from newer_all and shown together"""
    pool = {}
    for e in list(newer_all) + list(shown):
        pool.setdefault(e.get("id"), e)
    units = {}
    for e in pool.values():
        u = unit_of(e)
        if u:
            units.setdefault(u, []).append(e)
        elif e.get("kind") == "app" and e.get("follows") is not None:
            units.setdefault("b:" + str(e["follows"]), []).append(e)
    by_key, replaced = {}, []   # newer_all indexed once: by what each entry touches, and the whole-setup replacements
    for x in newer_all:
        if x.get("kind") == "setup-replaced":
            replaced.append(x)
        for k in _touches(x)[0]:
            by_key.setdefault(k, []).append(x)
    done = {}
    for e in shown:
        u = unit_of(e)
        if not u:
            continue
        if u not in done:
            ents = sorted(units[u], key=lambda x: x["id"])
            if not may(ents):
                done[u] = None
            else:
                last = ents[-1]["id"]
                need = set()
                for x in ents:
                    need |= _touches(x)[1]
                hits = {}   # only the entries that could block this unit, newest first: why_not skips all the others anyway
                for x in replaced + [y for k in need for y in by_key.get(k, ())]:
                    if x.get("id") > last:
                        hits[x["id"]] = x
                why = why_not(ents, sorted(hits.values(), key=lambda x: x["id"], reverse=True))
                done[u] = {"unit": u, "n": len(own(ents)), "ok": why is None, "why": why}
        if done[u] is not None:
            e["back"] = dict(done[u])

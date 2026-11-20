"""Relief settings: who is on the team, the rules, the limits, the times, the school calendar. One JSON file under DATA/relief."""
import datetime, os, re, threading

import store
from relief import people as _people

PATH = os.path.join(store.DATA, "relief", "settings.json")
_LOCK = threading.Lock()

DEFAULT_RULES = [
    "Use planned relief first.",
    "Then Flexi Adjunct Teachers: no more than 3 relief periods a day each; match the subject where possible; spread their relief over the week.",
    "Then other teachers, lightest week first (teaching periods plus relief periods this week); if tied, whoever has had less relief this term; spread over the week.",
]
_TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _fat_role(pub):
    for r in (((pub or {}).get("model") or {}).get("setup") or {}).get("roles") or []:
        if "adjunct" in (str(r.get("role") or "") + " " + str(r.get("what") or "")).lower() and str(r.get("role") or ""):
            return str(r["role"])
    return ""


def defaults(pub):
    return dict(management=[], team=[], extra_staff=[], fat_role=_fat_role(pub), rules=list(DEFAULT_RULES),
                limits=dict(fat_per_day=3, other_per_day=None, never=[]),
                times=dict(fill_at="15:00", remind_at="15:00", report_every=15, weekly_day="Fri", weekly_at="15:00"),
                calendar=dict(terms=[], holidays=[]), saved_at=None, saved_by=None)


def _merged(pub, saved):
    d = defaults(pub)
    for k, v in (saved or {}).items():
        if k in ("limits", "times") and isinstance(v, dict): d[k].update(v)
        elif k in d: d[k] = v
    return d


def load(pub):
    d = _merged(pub, store.read_json(PATH, {}))
    known = {p["name"] for p in _people.people(pub, d["extra_staff"])}
    missing = []
    def keep(names):
        out = []
        for n in names:
            if n in known: out.append(n)
            elif n not in missing: missing.append(n)
        return out
    d["management"], d["team"] = keep(d["management"]), keep(d["team"])
    d["limits"]["never"] = keep(d["limits"].get("never") or [])
    d["missing"] = missing
    return d


def _date(s):
    try: return datetime.date.fromisoformat(str(s))
    except ValueError: return None


def _int_in(v, lo, hi):
    return isinstance(v, int) and not isinstance(v, bool) and lo <= v <= hi


def _check(new, pub):
    """-> the clean dict to save; ValueError(one plain sentence) on the first problem"""
    base = defaults(pub)
    extra, seen = [], set()
    teachers = {p["name"] for p in _people.people(pub, [])}
    for x in new.get("extra_staff") or []:
        name = str((x or {}).get("name") or "").strip()
        if not name: raise ValueError("A staff member needs a name.")
        if name in teachers: raise ValueError(f"{name} is already a teacher on the timetable.")
        if name in seen: raise ValueError(f"{name} is on the staff list twice.")
        seen.add(name); extra.append(dict(name=name, note=str((x or {}).get("note") or "").strip()))
    known = {p["name"] for p in _people.people(pub, extra)}
    lists = {}
    for key, names in (("management", new.get("management")), ("team", new.get("team")), ("never", (new.get("limits") or {}).get("never"))):
        out = []
        for n in names or []:
            n = str(n).strip()
            if n not in known: raise ValueError(f"{n} is not on the published timetable or the staff list.")
            if n not in out: out.append(n)
        lists[key] = out
    role = str(new.get("fat_role") or "").strip()
    if role:
        model = (pub or {}).get("model") or {}
        roles = {str(r.get("role") or "") for r in (model.get("setup") or {}).get("roles") or []} | {str(t.get("role") or "") for t in (model.get("setup") or {}).get("teachers") or []}
        if role not in roles: raise ValueError(f"There is no role {role} on step 4.")
    rules = [str(r).strip() for r in (new["rules"] if "rules" in new else base["rules"])]
    if len(rules) > 20 or any(not r or len(r) > 300 for r in rules):
        raise ValueError("Keep each rule under 300 characters, at most 20 rules, none empty.")
    lim = dict(base["limits"]); lim.update(new.get("limits") or {})
    for k in ("fat_per_day", "other_per_day"):
        if lim[k] is not None and not _int_in(lim[k], 1, 20): raise ValueError("A daily limit is a whole number from 1 to 20, or empty.")
    times = dict(base["times"]); times.update(new.get("times") or {})
    for k in ("fill_at", "remind_at", "weekly_at"):
        if not _TIME.match(str(times[k])): raise ValueError(f"{times[k]} is not a time like 15:00.")
    if not _int_in(times["report_every"], 5, 60): raise ValueError("Report every 5 to 60 minutes.")
    if times["weekly_day"] not in ("Mon", "Tue", "Wed", "Thu", "Fri"): raise ValueError("The weekly summary goes out on a weekday.")
    cal = new.get("calendar") or {}
    two = int((((pub or {}).get("model") or {}).get("school") or {}).get("weeks") or 1) == 2
    terms = []
    for tm in cal.get("terms") or []:
        name = str(tm.get("name") or "").strip()
        a, b = _date(tm.get("start")), _date(tm.get("end"))
        if not name or not a or not b or a > b: raise ValueError(f"Check the dates of {name}.")
        terms.append((a, b, name, tm))
    terms.sort(key=lambda x: x[0])
    for i in range(1, len(terms)):
        if terms[i][0] <= terms[i - 1][1]: raise ValueError(f"Check the dates of {terms[i][2]}.")
    clean_terms = []
    for a, b, name, tm in terms:
        if two and tm.get("starts_as") not in ("Odd", "Even"): raise ValueError(f"Say whether {name} starts in an Odd or an Even week.")
        clean_terms.append(dict(name=name, start=a.isoformat(), end=b.isoformat(), starts_as=tm.get("starts_as") if tm.get("starts_as") in ("Odd", "Even") else None))
    holidays = []
    for h in cal.get("holidays") or []:
        name = str(h.get("name") or "").strip()
        a, b = _date(h.get("start")), _date(h.get("end") or h.get("start"))
        if not a or not b or b < a: raise ValueError(f"Check the dates of {name}.")
        holidays.append(dict(start=a.isoformat(), end=b.isoformat(), name=name))
    return dict(management=lists["management"], team=lists["team"], extra_staff=extra, fat_role=role, rules=rules,
                limits=dict(fat_per_day=lim["fat_per_day"], other_per_day=lim["other_per_day"], never=lists["never"]),
                times=dict(fill_at=times["fill_at"], remind_at=times["remind_at"], report_every=times["report_every"], weekly_day=times["weekly_day"], weekly_at=times["weekly_at"]),
                calendar=dict(terms=clean_terms, holidays=holidays))


def save(new, pub, by):
    clean = _check(new or {}, pub)
    clean.update(saved_at=store.now(), saved_by=by)
    with _LOCK:
        os.makedirs(os.path.dirname(PATH), exist_ok=True)
        store.write_json(PATH, clean)
    return load(pub)

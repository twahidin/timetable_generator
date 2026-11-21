"""Relief settings: the rules, the limits, the times, the school calendar. One JSON file under DATA/relief. The lists of who is
on management, on the relief team and on the extra staff moved into the accounts: what the file still holds of them is kept
as it was, for the record, and never read."""
import datetime, os, re, threading

import store
from relief import people as _people
from accounts import people as _accounts

PATH = os.path.join(store.DATA, "relief", "settings.json")
_LOCK = threading.Lock()

DEFAULT_RULES = [
    "Use planned relief first.",
    "Then Flexi Adjunct Teachers: no more than 3 relief periods a day each; match the subject where possible; spread their relief over the week.",
    "Then other teachers, lightest week first (teaching periods plus relief periods this week); if tied, whoever has had less relief this term; spread over the week.",
]
_TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
UNREAD = "The settings could not be read. Reload the page and try again."
NAMELESS = "Give each term and holiday a name."
FORMULA = ("=", "+", "-", "@", "\t", "\r")     # what a spreadsheet reads as the start of a formula


def _fat_role(pub):
    for r in (((pub or {}).get("model") or {}).get("setup") or {}).get("roles") or []:
        name = str(r.get("role") or "").strip()
        if name and "adjunct" in (name + " " + str(r.get("what") or "")).lower(): return name
    return ""


def role_names(pub) -> list:
    """the role names of the published setup (its roles and every teacher's role), stripped, sorted, none empty"""
    setup = (((pub or {}).get("model") or {}).get("setup") or {})
    names = {str(r.get("role") or "").strip() for r in setup.get("roles") or []} | {str(t.get("role") or "").strip() for t in setup.get("teachers") or []}
    return sorted(names - {""})


def defaults(pub) -> dict:
    return dict(fat_role=_fat_role(pub), rules=list(DEFAULT_RULES),
                limits=dict(fat_per_day=3, other_per_day=None, never=[]),
                times=dict(fill_at="15:00", remind_at="15:00", report_every=15, weekly_day="Fri", weekly_at="15:00"),
                calendar=dict(terms=[], holidays=[]), saved_at=None, saved_by=None)


def _merged(pub, saved) -> dict:
    d = defaults(pub)
    if not isinstance(saved, dict): return d   # valid JSON of the wrong shape: start from the defaults
    for k, v in saved.items():
        if k in ("limits", "times") and isinstance(v, dict): d[k].update(v)
        elif k in d: d[k] = v
    return d


KEPT = ("management", "team", "extra_staff")      # the old lists: stored untouched, never read


def load(pub) -> dict:
    d = _merged(pub, store.read_json(PATH, {}))
    for k in KEPT: d.pop(k, None)
    known = {p["name"] for p in _accounts.staff(pub)}
    missing = []
    def keep(names):
        out = []
        for n in names:
            if n in known: out.append(n)
            elif n not in missing: missing.append(n)
        return out
    d["limits"]["never"] = keep(d["limits"].get("never") or [])
    d["missing"] = missing
    return d


def _date(s):
    try: return datetime.date.fromisoformat(str(s))
    except ValueError: return None


def _of(d, key, typ, default):
    """d[key] when it is a typ, default when the key is absent; anything else (None too) is the wrong JSON type"""
    if key not in d: return default
    if not isinstance(d[key], typ): raise ValueError(UNREAD)
    return d[key]


def _text(v):
    """a text value stripped; None is empty; a number, list or object is the wrong JSON type"""
    if v is None: return ""
    if not isinstance(v, str): raise ValueError(UNREAD)
    return v.strip()


def _int_in(v, lo, hi):
    return isinstance(v, int) and not isinstance(v, bool) and lo <= v <= hi


def _check(new, pub):
    """-> the clean dict to save; ValueError(one plain sentence) on the first problem. A key left out takes its default;
    a value of the wrong JSON type (a list where an object belongs, None where a list belongs) is UNREAD"""
    if not isinstance(new, dict): raise ValueError(UNREAD)
    base = defaults(pub)
    known = {p["name"] for p in _accounts.staff(pub)}
    limits = _of(new, "limits", dict, {})
    never = []
    for n in _of(limits, "never", list, []):
        n = _text(n)
        if n not in known: raise ValueError(f"{n} is not on the published timetable or the staff list.")
        if n not in never: never.append(n)
    role = _text(new.get("fat_role"))
    if role and role not in role_names(pub): raise ValueError(f"There is no role {role} on step 4.")
    rules = [_text(r) for r in _of(new, "rules", list, base["rules"])]
    if len(rules) > 20 or any(not r or len(r) > 300 for r in rules):
        raise ValueError("Keep each rule under 300 characters, at most 20 rules, none empty.")
    lim = dict(base["limits"]); lim.update(limits)
    for k in ("fat_per_day", "other_per_day"):
        if lim[k] is not None and not _int_in(lim[k], 1, 20): raise ValueError("A daily limit is a whole number from 1 to 20, or empty.")
    times = dict(base["times"]); times.update(_of(new, "times", dict, {}))
    for k, label in (("fill_at", "Fill open lessons at"), ("remind_at", "Remind the absent teacher at"), ("weekly_at", "Weekly summary at")):
        if times[k] is None or str(times[k]).strip() == "": raise ValueError(f"Give a time for {label}.")
        if not _TIME.match(str(times[k])): raise ValueError(f"{times[k]} is not a time like 15:00.")
    if not _int_in(times["report_every"], 5, 60): raise ValueError("Report every 5 to 60 minutes.")
    if times["weekly_day"] not in ("Mon", "Tue", "Wed", "Thu", "Fri"): raise ValueError("The weekly summary goes out on a weekday.")
    cal = _of(new, "calendar", dict, {})
    two = int((((pub or {}).get("model") or {}).get("school") or {}).get("weeks") or 1) == 2
    terms = []
    for tm in _of(cal, "terms", list, []):
        if not isinstance(tm, dict): raise ValueError(UNREAD)
        name = _text(tm.get("name"))
        if not name: raise ValueError(NAMELESS)
        a, b = _date(tm.get("start")), _date(tm.get("end"))
        if not a or not b or a > b: raise ValueError(f"Check the dates of {name}.")
        terms.append((a, b, name, tm))
    terms.sort(key=lambda x: x[0])
    for i in range(1, len(terms)):
        if terms[i][0] <= terms[i - 1][1]: raise ValueError(f"Check the dates of {terms[i][2]}.")
    clean_terms = []
    for a, b, name, tm in terms:
        if two and tm.get("starts_as") not in ("Odd", "Even"): raise ValueError(f"Say whether {name} starts in an Odd or an Even week.")
        clean_terms.append(dict(name=name, start=a.isoformat(), end=b.isoformat(), starts_as=tm.get("starts_as") if tm.get("starts_as") in ("Odd", "Even") else None))
    holidays = []
    for h in _of(cal, "holidays", list, []):
        if not isinstance(h, dict): raise ValueError(UNREAD)
        name = _text(h.get("name"))
        if not name: raise ValueError(NAMELESS)
        a, b = _date(h.get("start")), _date(h.get("end") or h.get("start"))
        if not a or not b or b < a: raise ValueError(f"Check the dates of {name}.")
        holidays.append(dict(start=a.isoformat(), end=b.isoformat(), name=name))
    return dict(fat_role=role, rules=rules,
                limits=dict(fat_per_day=lim["fat_per_day"], other_per_day=lim["other_per_day"], never=never),
                times=dict(fill_at=times["fill_at"], remind_at=times["remind_at"], report_every=times["report_every"], weekly_day=times["weekly_day"], weekly_at=times["weekly_at"]),
                calendar=dict(terms=clean_terms, holidays=holidays))


def save(new, pub, by):
    clean = _check(new, pub)
    clean.update(saved_at=store.now(), saved_by=by)
    with _LOCK:
        old = store.read_json(PATH, {})
        if isinstance(old, dict):
            for k in KEPT:
                if k in old: clean[k] = old[k]
        os.makedirs(os.path.dirname(PATH), exist_ok=True)
        store.write_json(PATH, clean)
    return load(pub)

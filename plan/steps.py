"""The changes the planning chat makes to an exam draft at once. Each is a Step that can be taken back on its own. No Flask
here and nothing of app.py: the app gives an Env (the tests a fake), whose create, change and remove keep the rules of
do_create, do_change and do_remove below, so the real and the fake Env never differ. Wrong input from the AI answers with a
sentence (Refused), changes nothing and never half-saves."""
import copy
import datetime
import logging
import re
import secrets
import traceback
from typing import Protocol

from exams import approval as _approval
from exams import days as _days
from exams import papers as _papers
from exams import schedules as _schedules
from plan import facts as _facts


log = logging.getLogger("plan")


def _fault(e):
    """the type of a fault and its frames, never its text"""
    frames = "; ".join(f"{f.filename.rsplit('/', 1)[-1]}:{f.lineno} {f.name}" for f in traceback.extract_tb(e.__traceback__))
    log.error("plan.steps fault %s at %s", type(e).__name__, frames)


class Refused(ValueError):
    """a change the app will not make; its text is the sentence that says why"""


WAITING = "This exam is waiting for the timetable committee. Change it on the exam page."
ON_SITE = "This exam is on the main site. Change it on the exam page."
ENDED = "This exam has ended. It can be read and not changed."
GONE = "That exam is not there any more."
SAME = "That is how it is already."
SENT = "Sent since: change it on the exam page."
CHANGED_SINCE = "This exam was changed since: delete it on the exam page."
TAKEN = "That was taken back already."
NOT_UNDOABLE = "That cannot be taken back."
NEED_SAID = "Tell me the date and time in your own words first."
START_FIRST = "Start the exam first."
HAS_EXAM = "This talk already has an exam. Start a new talk for another."
NO_LAST = "There is no earlier exam of this kind."
TOO_LONG = "Keep it under 120 characters."
TOO_MANY = "An exam can hold at most 200 papers here."
AT_ONCE = "Send at most 60 at once."
STUDENTS = "Which students sit is set on the exam page."
NO_TIMES_HERE = "A paper's date and time are put on their own, with the person's words."
NOTHING = "Nothing to change was given."
NOT_OFFERED = "That time was not offered for this paper."
ONCE = "Each paper once."
BAD_DATE = "Give a date such as 2026-10-05."
BAD_TIME = "Give a time such as 08:00."
PART_DAY = "Give the start and the end of part of a day."
WHOLE_DAY_TIMES = "A whole day takes no start or end. Say it is part of a day, or leave the times out."
NO_ACTION = "The app cannot make that change here."
WRONG = _schedules.WRONG
BY = "{name}, with Plan with AI"
MAX_PAPERS, AT_MOST, LONGEST = 200, 60, 120
ACTIONS = ("start", "what", "days", "papers", "times", "suggested", "day_times", "choices", "keep_last", "put_list")
STALE = ("days", "papers", "times", "suggested", "put_list")    # after these (and taking one back) no earlier offer stands
FIELDS = ("name", "levels", "classes", "start", "end", "times", "seating", "supervision", "scripts")
FIELD_WORDS = dict(name="the name", levels="the levels", classes="the classes", start="the first day", end="the last day",
                   times="the report time and breaks", seating="the seating choices", supervision="who supervises",
                   scripts="where scripts go")
ODD = (TypeError, KeyError, AttributeError, IndexError)      # what odd input or an odd stored draft gives


class Env(Protocol):
    """what the app gives the steps (app.py writes the real one; the tests a fake with the same names)"""
    name: str
    def pub(self) -> dict: ...
    def cal(self) -> dict: ...
    def settings(self) -> dict: ...
    def people(self) -> list: ...
    def all_saved(self) -> list: ...
    def today(self) -> datetime.date: ...
    def may(self) -> None: ...                      # raises Refused when the person may not change exams now
    def load(self, id): ...
    def create(self, kind, name, levels, classes, start, end, words) -> dict: ...       # do_create
    def change(self, id, fn, words) -> tuple: ...                                       # do_change: (before, after)
    def remove(self, id, rev, words) -> dict: ...                                       # do_remove


# ---------------------------------------------------------------- what may be changed, and the shared rules of the Env
def editable(sched, today) -> str:
    """"" when the chat may change the exam (draft, sent back included, or withdrawn), else the sentence that says why not"""
    if _approval.label(sched, today) == "Ended":
        return ENDED
    st = sched.get("status") or "draft"
    if st in ("draft", "withdrawn"):
        return ""
    return WAITING if st == "waiting" else ON_SITE


def _exam(env, id):
    s = env.load(id) if isinstance(id, str) and id else None
    if not isinstance(s, dict) or s.get("kind") not in _schedules.KINDS:
        raise Refused(GONE)
    return s


def _words(words, before, after) -> str:
    """the words of a history entry: a text, or a function of (before, after); a fault in them never undoes a save"""
    try:
        return str(words(before, after) if callable(words) else words)
    except Exception:
        return "changed"


def _entry(env, sched, words, before, after) -> dict:
    """the history entry of a step: "{exam}: {words}" by "{name}, with Plan with AI" """
    return dict(text=f"{sched.get('name')}: {_words(words, before, after)}", exam=sched.get("id"), by=BY.format(name=env.name))


def _checked(f):
    """run f; a sentence of the app's check becomes Refused, any other odd input Refused with schedules.WRONG"""
    try:
        return f()
    except Refused:
        raise
    except ValueError as e:
        raise Refused(str(e)) from None
    except ODD:
        raise Refused(WRONG) from None


def _bare(s) -> dict:
    """a draft without the save's own fields, its suggested list cleaned, for "That is how it is already." """
    out = copy.deepcopy({k: v for k, v in s.items() if k not in ("saved_at", "saved_by", "rev")})
    _schedules.clean_suggested(out)
    return out


def do_create(env, kind, name, levels, classes, start, end, words, record) -> dict:
    """Env.create: under the lock, may(), the calendar, a new draft saved by env.name, one history entry (record(entry))"""
    with _schedules.editing():
        env.may()
        if not (env.cal() or {}).get("terms"):
            raise Refused(_schedules.NO_CALENDAR)
        if kind not in _schedules.KINDS:
            raise Refused(WRONG)

        def make():
            s = _schedules.new(kind, name, levels, start, end, env.name, pub=env.pub())
            s["classes"] = list(classes)
            return _schedules.save(s, env.pub(), env.cal(), env.name)
        saved = _checked(make)
        record(_entry(env, saved, words, None, saved))
    return saved


def do_change(env, id, fn, words, record) -> tuple:
    """Env.change: locks, calls may() after the lock, loads, refuses what is not editable, runs fn on a working copy (a
    Refused from it saves nothing), refuses a change that changes nothing, saves with rev raised, records the entry.
    -> (before, after)"""
    with _schedules.editing():
        env.may()
        stored = _exam(env, id)
        why = editable(stored, env.today())
        if why:
            raise Refused(why)
        before, work = copy.deepcopy(stored), copy.deepcopy(stored)

        def apply():
            fn(work)
            _schedules._check(work, env.pub())
            _schedules.clean_suggested(work)
        _checked(apply)
        if _bare(work) == _bare(before):
            raise Refused(SAME)
        after = _checked(lambda: _schedules.save(work, env.pub(), env.cal(), env.name))
        record(_entry(env, after, words, before, after))
    return before, after


def do_remove(env, id, rev, words, record) -> dict:
    """Env.remove: locks, may(), loads, refuses what is not editable or on the main site, refuses when the stored rev is not
    rev, deletes, records. -> the schedule as it was"""
    with _schedules.editing():
        env.may()
        s = _exam(env, id)
        why = editable(s, env.today()) or (ON_SITE if s.get("approved") else "")
        if why:
            raise Refused(why)
        if _schedules.rev_of(s) != rev:
            raise Refused(CHANGED_SINCE)
        _schedules.delete(s["id"])
        record(_entry(env, s, words, s, None))
    return s


# ---------------------------------------------------------------- reading what the AI sent
def _fold(t) -> str:
    return " ".join(str(t).split()).casefold()


def _short(k) -> str:
    return str(k)[:40]


def _keys(d, allowed, need=(), times_here=False) -> dict:
    """d must be a dict of the allowed keys with every needed one"""
    if not isinstance(d, dict):
        raise Refused(WRONG)
    for k in d:
        if k in allowed:
            continue
        if times_here and k in ("date", "start"):
            raise Refused(NO_TIMES_HERE)
        if times_here and k == "students":
            raise Refused(STUDENTS)
        raise Refused(f"{_short(k)} is not a field here.")
    for k in need:
        if k not in d:
            raise Refused(f"{k} is missing.")
    return d


def _items(v, most=AT_MOST, empty_ok=False, too_many=AT_ONCE) -> list:
    if not isinstance(v, list):
        raise Refused(WRONG)
    if len(v) > most:
        raise Refused(too_many)
    if not v and not empty_ok:
        raise Refused(NOTHING)
    return v


def _txt(v, blank_ok=True) -> str:
    if v is None and blank_ok:
        return ""
    if not isinstance(v, str):
        raise Refused(WRONG)
    v = v.strip()
    if len(v) > LONGEST:
        raise Refused(TOO_LONG)
    return v


def _whole(v, lo, sentence) -> int:
    if not isinstance(v, int) or isinstance(v, bool) or v < lo:
        raise Refused(sentence)
    return v


def _date(v, none_ok=False):
    if v is None and none_ok:
        return None
    if not isinstance(v, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v.strip()):
        raise Refused(BAD_DATE)
    try:
        return datetime.date.fromisoformat(v.strip()).isoformat()
    except ValueError:
        raise Refused(BAD_DATE) from None


def _time(v, none_ok=False):
    if v is None and none_ok:
        return None
    if not isinstance(v, str):
        raise Refused(BAD_TIME)
    try:
        return _days.hhmm(_days.minutes(v))
    except ValueError:
        raise Refused(BAD_TIME) from None


def _match(given, options):
    """the option written as given, case and spaces folded; None when there is none"""
    want = _fold(given)
    return next((o for o in options if _fold(o) == want), None)


def _names(v, options, what) -> list:
    """levels or classes as the timetable writes them"""
    if not isinstance(v, list) or len(v) > MAX_PAPERS:
        raise Refused(WRONG)
    out = []
    for x in v:
        got = _match(_txt(x, blank_ok=False), options)
        if got is None:
            raise Refused(f"{_txt(x)} is not a {what} of the published timetable.")
        if got not in out:
            out.append(got)
    return out


def _model(env) -> dict:
    return (env.pub() or {}).get("model") or {}


def _levels(env, v):
    return _names(v, _model(env).get("levels") or [], "level")


def _classes(env, v):
    return _names(v, [c["name"] for c in _model(env).get("classes") or []], "class")


def _paper_ids(s) -> dict:
    return {p["id"]: p for p in s.get("papers") or [] if isinstance(p, dict) and isinstance(p.get("id"), str)}


def _find(s, id):
    """the paper of this exam with that id"""
    got = _paper_ids(s).get(id) if isinstance(id, str) else None
    if got is None:
        if isinstance(id, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,24}", id):
            raise Refused(f"There is no paper {id} in this exam.")
        raise Refused("There is no paper with that id in this exam.")
    return got


def _unmark(s, id):
    if isinstance(s.get("suggested"), list):
        s["suggested"] = [i for i in s["suggested"] if i != id]


def _key3(p):
    return tuple(_fold(p.get(k) or "") for k in ("level", "subject", "paper"))


def _level_subject(s, model, level, subject):
    """(level, subject) as the timetable writes them: a level of this exam, a subject with lessons at that level"""
    lv = _match(level, _days.levels_of(s, model))
    if lv is None:
        raise Refused(f"{level} is not a level of this exam.")
    sb = _match(subject, sorted({l["subject"] for l in model.get("lessons") or [] if l.get("level") == lv}))
    if sb is None:
        raise Refused(f"{lv} has no subject called {subject}.")
    return lv, sb


def _paper_fields(d, out, label):
    """the paper, paper name, minutes, who and together of d, checked, onto out (a paper's own dict)"""
    if "paper" in d:
        out["paper"] = _txt(d["paper"])
    if "minutes" in d:
        out["minutes"] = _whole(d["minutes"], 1, f"Give {label(out)} a length in minutes.")
    if "together" in d:
        out["together"] = _txt(d["together"])
    if d.get("who") is not None:
        if d["who"] == "students" or out.get("who") == "students":
            raise Refused(STUDENTS)
        if d["who"] not in ("level", "groups"):
            raise Refused(WRONG)
        out["who"] = d["who"]


def _no_twins(s, touched):
    seen = {}
    for p in s["papers"]:
        k = _key3(p)
        if k in seen and (p["id"] in touched or seen[k]["id"] in touched):
            raise Refused(f"There are two papers called {_papers.label(p)}.")
        seen.setdefault(k, p)


# ---------------------------------------------------------------- each action: check the shapes now, the rest in fn
def _what(env, st, a, said):
    _keys(a, ("name", "levels", "classes", "start", "end"))
    if not a:
        raise Refused(NOTHING)
    v = {}
    if "name" in a:
        v["name"] = _txt(a["name"], blank_ok=False)
    for k in ("start", "end"):
        if k in a:
            v[k] = _date(a[k])
    if "levels" in a:
        v["levels"] = _levels(env, a["levels"])
    if "classes" in a:
        v["classes"] = _classes(env, a["classes"])
    return lambda s: s.update(copy.deepcopy(v))


def _days_of(env, st, a, said):
    _keys(a, ("days",), ("days",))
    entries = {}
    for d in _items(a["days"], most=31, too_many="An exam can cover at most 31 days."):
        _keys(d, ("date", "levels", "whole", "start", "end"), ("date", "whole"))
        date = _date(d["date"])
        if date in entries:
            raise Refused(f"{_days.nice(date)} is given twice.")
        whole = d["whole"]
        if not isinstance(whole, bool):
            raise Refused(WRONG)
        if whole and (d.get("start") is not None or d.get("end") is not None):
            raise Refused(WHOLE_DAY_TIMES)
        levels = None if d.get("levels") is None else _levels(env, d["levels"])
        f, t = (None, None) if whole else (_time(d.get("start"), True), _time(d.get("end"), True))
        if not whole and not (f and t):
            raise Refused(PART_DAY)
        entries[date] = {"levels": levels, "whole": whole, "from": f, "to": t}

    def fn(s):
        for date, e in entries.items():
            if not (str(s.get("start")) <= date <= str(s.get("end"))):
                raise Refused(f"{_days.nice(date)} is not a date of this exam.")
            s["days"][date] = dict(e)
    return fn


def _papers_of(env, st, a, said):
    _keys(a, ("add", "change", "remove"))
    add = _items(a.get("add", []), empty_ok=True)
    change = _items(a.get("change", []), empty_ok=True)
    remove = _items(a.get("remove", []), most=MAX_PAPERS, empty_ok=True, too_many=TOO_MANY)
    if not (add or change or remove):
        raise Refused(NOTHING)
    fields = ("level", "subject", "paper", "minutes", "who", "together")
    for d in add:
        _keys(d, fields, ("level", "subject"), times_here=True)
    ids = []
    for d in change:
        _keys(d, ("id",) + fields, ("id",), times_here=True)
        if len(d) == 1:
            raise Refused(NOTHING)
        if d["id"] in ids:
            raise Refused(ONCE)
        ids.append(d["id"])

    def fn(s):
        model = _model(env)
        touched = set()
        for d in change:
            p = _find(s, d["id"])
            lv, sb = _level_subject(s, model, _txt(d.get("level", p.get("level"))), _txt(d.get("subject", p.get("subject"))))
            p.update(level=lv, subject=sb)
            _paper_fields(d, p, _papers.label)
            touched.add(p["id"])
        for i in remove:
            _find(s, i)
        s["papers"] = [p for p in s["papers"] if p.get("id") not in remove]
        for d in add:
            lv, sb = _level_subject(s, model, _txt(d["level"], blank_ok=False), _txt(d["subject"], blank_ok=False))
            p = dict(id=secrets.token_hex(4), level=lv, subject=sb, paper="", minutes=None, date=None, start=None, who="groups",
                     students=[], together="")
            _paper_fields(dict(d, minutes=d.get("minutes")), p, _papers.label)
            s["papers"].append(p)
            touched.add(p["id"])
        if add and len(s["papers"]) > MAX_PAPERS:
            raise Refused(TOO_MANY)
        _no_twins(s, touched)
    return fn


def _said_ok(st, said) -> bool:
    """said is at least 3 characters of one text the person sent since the last answer, case and spaces folded: its words
    appear as whole words, in order, in that text (never inside a word: "eas" is not in "please")"""
    s = _fold(said) if isinstance(said, str) else ""
    if len(s) < 3:
        return False
    whole = re.compile(r"(?<!\w)" + r"\s+".join(map(re.escape, s.split())) + r"(?!\w)")
    return any(whole.search(_fold(w)) for w in (getattr(st, "words", None) or []) if isinstance(w, str))


def _times_of(env, st, a, said):
    _keys(a, ("items",), ("items",))
    items = []
    for d in _items(a["items"]):
        _keys(d, ("id", "date", "start"), ("id", "date", "start"))
        if any(d["id"] == i for i, _, _ in items):
            raise Refused(ONCE)
        items.append((d["id"], _date(d["date"], True), _time(d["start"], True)))
    if not _said_ok(st, said):
        raise Refused(NEED_SAID)

    def fn(s):
        for id, date, start in items:
            _find(s, id).update(date=date, start=start)
            _unmark(s, id)
    return fn


def _suggested_of(env, st, a, said):
    _keys(a, ("id", "date", "start"), ("id", "date", "start"))
    id, date, start = a["id"], _date(a["date"]), _time(a["start"])
    offered = (getattr(st, "offered", None) or {}).get(id) if isinstance(id, str) else None
    ok = False
    for o in offered if isinstance(offered, list) else []:
        try:
            ok = ok or (isinstance(o, dict) and o.get("date") == date and _time(o.get("start")) == start)
        except Refused:
            pass
    if not ok:
        raise Refused(NOT_OFFERED)

    def fn(s):
        p = _find(s, id)
        if p.get("date") or p.get("start"):
            raise Refused(f"{_papers.label(p)} has a time already.")
        p.update(date=date, start=start)
        s["suggested"] = [i for i in s.get("suggested") or [] if i != id] + [id]
    return fn


def _day_times_of(env, st, a, said):
    _keys(a, ("report", "min_break", "max_papers"))
    if not a:
        raise Refused(NOTHING)
    v = {}
    if "report" in a:
        v["report"] = _time(a["report"], True)
    if "min_break" in a:
        v["min_break"] = _whole(a["min_break"], 0, "Give a whole number of minutes between two papers.")
    if "max_papers" in a:
        v["max_papers"] = _whole(a["max_papers"], 1, "Give a whole number for the most papers a day.")
    return lambda s: s.__setitem__("times", dict(s.get("times") or {}, **v))


def _choices_of(env, st, a, said):
    _keys(a, tuple(_schedules.SEATING) + ("supervision", "scripts"))
    if not a:
        raise Refused(NOTHING)
    seat = {}
    for k, allowed in _schedules.SEATING.items():
        if k in a:
            if a[k] not in allowed or isinstance(a[k], bool) != (k == "home_rooms"):
                raise Refused(f"{k} can be {' or '.join(str(x).lower() for x in allowed)}.")
            seat[k] = a[k]
    if "supervision" in a and a["supervision"] not in _schedules.SUPERVISION:
        raise Refused(f"supervision can be {' or '.join(_schedules.SUPERVISION)}.")
    scripts = _txt(a["scripts"]) if "scripts" in a else None

    def fn(s):
        s["seating"] = dict(s.get("seating") or {}, **seat)
        if "supervision" in a:
            s["supervision"] = a["supervision"]
        if scripts is not None:
            s["scripts"] = scripts
    return fn


def _keep_last_of(env, st, a, said, ctx):
    _keys(a, ())

    def fn(s):
        last = _facts.last_values(s, env.all_saved())
        if not last:
            raise Refused(NO_LAST)
        for k in ("times", "seating", "supervision", "scripts"):
            if last.get(k) is not None:
                s[k] = copy.deepcopy(last[k])
        ctx["from"] = last.get("name") or "the exam before"
    return fn


def _put_list_of(env, st, a, said):
    _keys(a, ("papers",), ("papers",))
    rows = _items(a["papers"], most=MAX_PAPERS, too_many=TOO_MANY)
    for d in rows:
        _keys(d, ("level", "subject", "paper", "minutes", "date", "start", "who", "together"), ("level", "subject", "minutes"))
        if d.get("who") not in (None, "level", "groups", "students"):
            raise Refused(WRONG)
    when = [(_date(d.get("date"), True), _time(d.get("start"), True)) for d in rows]

    def fn(s):
        model = _model(env)
        got, twice = {}, []
        for d, (date, start) in zip(rows, when):
            lv, sb = _level_subject(s, model, _txt(d["level"], blank_ok=False), _txt(d["subject"], blank_ok=False))
            row = dict(level=lv, subject=sb, paper=_txt(d.get("paper")))
            k = _key3(row)
            if k in got and _papers.label(row) not in twice:
                twice.append(_papers.label(row))
            got[k] = (d, row, date, start)
        if twice:
            raise Refused(f"The list has {_join(twice)} more than once.")
        have = {}
        for p in s["papers"]:
            have.setdefault(_key3(p), p)
        for k, (d, row, date, start) in got.items():
            p = have.get(k)
            if p is None:
                p = dict(id=secrets.token_hex(4), **row, minutes=None, date=None, start=None, who="groups", students=[], together="")
                s["papers"].append(p)
            # a paper there already changes only what the row carries: its length always, its date and start when the row
            # gives a date, its Sits with when the row has one, its who only to the whole level; a paper that students sit
            # keeps its who and its students whatever the row says
            was, said = p.get("who"), d.get("who")
            if said == "students" and was != "students":
                raise Refused(STUDENTS)
            p["minutes"] = _whole(d["minutes"], 1, f"Give {_papers.label(p)} a length in minutes.")
            if date is not None:
                p.update(date=date, start=start)
                _unmark(s, p["id"])
            together = _txt(d.get("together"))
            if together:
                p["together"] = together
            if said == "level" and was != "students":
                p["who"] = "level"
            if p.get("who") != "students":
                p["students"] = []
        if len(s["papers"]) > MAX_PAPERS:
            raise Refused(TOO_MANY)
    return fn


BUILD = dict(what=_what, days=_days_of, papers=_papers_of, times=_times_of, suggested=_suggested_of, day_times=_day_times_of,
             choices=_choices_of, put_list=_put_list_of)


# ---------------------------------------------------------------- the parts of a step and its words
def _value(s, key):
    """the stored value of a part: a field, a day (None: not set), a paper (None: absent), a suggested mark (bool)"""
    kind, _, k = key.partition(":")
    if not k:
        return s.get(key)
    if kind == "day":
        return (s.get("days") if isinstance(s.get("days"), dict) else {}).get(k)
    if kind == "paper":
        return _paper_ids(s).get(k)
    return k in (s.get("suggested") if isinstance(s.get("suggested"), list) else [])


def parts_of(before, after) -> dict:
    """{key: [before, after]} of everything that differs: the fields, day:<date>, paper:<id>, suggested:<id>"""
    out = {k: [copy.deepcopy(before.get(k)), copy.deepcopy(after.get(k))] for k in FIELDS if before.get(k) != after.get(k)}
    days = lambda s: s.get("days") if isinstance(s.get("days"), dict) else {}
    for d in sorted(set(days(before)) | set(days(after))):
        if days(before).get(d) != days(after).get(d):
            out["day:" + d] = [copy.deepcopy(days(before).get(d)), copy.deepcopy(days(after).get(d))]
    bp, ap = _paper_ids(before), _paper_ids(after)
    ids = list(bp) + [i for i in ap if i not in bp]
    for i in ids:
        if bp.get(i) != ap.get(i):
            out["paper:" + i] = [copy.deepcopy(bp.get(i)), copy.deepcopy(ap.get(i))]
    for i in ids:
        b, a = _value(before, "suggested:" + i), _value(after, "suggested:" + i)
        if b != a:
            out["suggested:" + i] = [b, a]
    return out


def _join(xs) -> str:
    xs = list(xs)
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1]


def _n(n, one, many) -> str:
    return f"{n} {one if n == 1 else many}"


def _at(p) -> str:
    return " ".join(x for x in (p.get("start") or "", "on " + _days.nice(p["date"]) if p.get("date") else "") if x)


def _moved(b, a) -> str:
    lb = _papers.label(a)
    if not (a.get("date") or a.get("start")):
        return f"{lb} has no time now"
    if not (b.get("date") or b.get("start")):
        return f"{lb} set for {_at(a)}"
    if b.get("date") == a.get("date") and a.get("date"):
        return f"{lb} moved from {b.get('start') or 'no start'} to {a.get('start') or 'no start'} on {_days.nice(a['date'])}"
    return f"{lb} moved from {_at(b)} to {_at(a)}"


def _text(action, parts, after, ctx) -> str:
    """the plain words of a step (no tick: the page puts it)"""
    fields = [FIELD_WORDS[k] for k in FIELDS if k in parts]
    papers = [(v[0], v[1]) for k, v in parts.items() if k.startswith("paper:")]
    if action == "start":
        return f"Started the {after.get('kind') or 'exam'} {after.get('name')}"
    if action == "days":
        ds = [_days.nice(k[4:]) for k in parts if k.startswith("day:")]
        return ("Set the day " if len(ds) == 1 else "Set the days ") + _join(ds) if len(ds) <= 3 else f"Set {len(ds)} days"
    if action == "papers":
        said = [w + " " + _n(n, "paper", "papers") for w, n in (
            ("added", sum(1 for b, a in papers if b is None)), ("changed", sum(1 for b, a in papers if b and a)),
            ("removed", sum(1 for b, a in papers if a is None))) if n]
        out = _join(said) if said else "changed the papers"
        return out[0].upper() + out[1:]
    if action in ("times", "suggested"):
        if action == "suggested" and papers:
            a = papers[0][1]
            return f"Suggested {a.get('start')} on {_days.nice(a.get('date'))} for {_papers.label(a)}"
        moved = [_moved(b, a) for b, a in papers if b and a]
        if not moved:
            return "Changed the exam"
        return "; ".join(moved[:5] + ([f"and {len(moved) - 5} more"] if len(moved) > 5 else []))
    if action == "put_list":
        return f"Put {_n(sum(1 for b, a in papers if a), 'paper', 'papers')} in the draft"
    if action == "keep_last":
        return f"Took {_join(fields)} from {ctx.get('from')}" if fields else "Took the choices of the exam before"
    return "Changed " + _join(fields) if fields else "Changed the exam"


def _step(action, exam, text, parts, rev, **more) -> dict:
    return dict(id=secrets.token_hex(4), exam=exam, action=action, text=text, parts=parts, rev_after=rev, undone=False,
                can_undo=True, **more)


# ---------------------------------------------------------------- run a step
def run(env, st, action, args, said="") -> dict:
    """make one change to the talk's exam at once -> the Step. st: the talk state (exam, words, offered, last_rev)"""
    if action not in ACTIONS:
        raise Refused(NO_ACTION)
    if not isinstance(args, dict):
        raise Refused(WRONG)
    if action == "start":
        try:
            return _start(env, st, args)
        except ODD:
            raise Refused(WRONG) from None
    if not getattr(st, "exam", None):
        raise Refused(START_FIRST)
    ctx = {}
    try:
        fn = _keep_last_of(env, st, args, said, ctx) if action == "keep_last" else BUILD[action](env, st, args, said)
    except ODD:
        raise Refused(WRONG) from None
    before, after = env.change(st.exam, fn, lambda b, a: _text(action, parts_of(b, a), a, ctx))
    st.last_rev = _schedules.rev_of(after)
    if action in STALE:
        st.offered = {}
    # the draft is saved: a fault from here on is logged and the step said in plain words, never an error
    whole = True
    try:
        parts = parts_of(before, after)
        old = [p.get("id") for p in before.get("papers") or [] if isinstance(p, dict)]
        places = {i: n for n, i in enumerate(old) if isinstance(i, str) and "paper:" + i in parts and parts["paper:" + i][1] is None}
    except Exception as e:
        _fault(e)
        parts, places, whole = {}, {}, False
    try:
        text = _text(action, parts, after, ctx)
    except Exception as e:
        _fault(e)
        text = "Changed the exam"
    step = _step(action, after["id"], text, parts, st.last_rev, places=places)
    step["can_undo"] = whole                    # without its parts a step cannot be taken back
    return step


def _start(env, st, a):
    if getattr(st, "exam", None):
        raise Refused(HAS_EXAM)
    _keys(a, ("kind", "name", "levels", "classes", "start", "end"), ("kind", "name", "start", "end"))
    if a["kind"] not in _schedules.KINDS:
        raise Refused(WRONG)
    name, levels = _txt(a["name"], blank_ok=False), _levels(env, a.get("levels") or [])
    classes, start, end = _classes(env, a.get("classes") or []), _date(a["start"]), _date(a["end"])
    words = lambda b, s: _text("start", {}, s, {})
    saved = env.create(a["kind"], name, levels, classes, start, end, words)
    st.exam, st.last_rev = saved["id"], _schedules.rev_of(saved)
    return _step("start", saved["id"], _text("start", {}, saved, {}), {}, st.last_rev)


# ---------------------------------------------------------------- take a step back
def undo_text(step) -> str:
    """the words of taking a whole step back: the line's text and the history's words"""
    return f"Taken back: {step.get('text')}"


def _units(parts) -> list:
    """the parts put back together or not at all: a paper with its suggested mark, every other part alone"""
    out, seen = [], {}
    for k in parts:
        kind, _, i = k.partition(":")
        u = "p:" + i if kind in ("paper", "suggested") else k
        if u not in seen:
            seen[u] = []
            out.append(seen[u])
        seen[u].append(k)
    return out


def _label(s, unit, parts) -> str:
    k = unit[0]
    kind, _, i = k.partition(":")
    if not i:
        return FIELD_WORDS.get(k, k)
    if kind == "day":
        return _days.nice(i)
    p = _paper_ids(s).get(i) or next((v for kk in unit for v in parts[kk] if isinstance(v, dict)), {"subject": "a paper"})
    return _papers.label(p)


def _stamp(s) -> str:
    """who saved last and when, as the exam pages show a stamp"""
    at = str(s.get("saved_at") or "")
    return f"last saved by {s.get('saved_by') or 'someone'}, " + (f"{_days.nice(at[:10])} {at[11:16]}" if at else "at a time not known")


def _put(s, key, value, places):
    kind, _, i = key.partition(":")
    if not i:
        s[key] = copy.deepcopy(value)
    elif kind == "day":
        if value is None:
            s["days"].pop(i, None)
        else:
            s["days"][i] = copy.deepcopy(value)
    elif kind == "paper":
        at = next((n for n, p in enumerate(s["papers"]) if isinstance(p, dict) and p.get("id") == i), None)
        if value is None:
            if at is not None:
                s["papers"].pop(at)
        elif at is not None:
            s["papers"][at] = copy.deepcopy(value)
        else:
            s["papers"].insert(min(places.get(i, len(s["papers"])), len(s["papers"])), copy.deepcopy(value))
    else:
        marks = [x for x in (s.get("suggested") if isinstance(s.get("suggested"), list) else []) if x != i]
        s["suggested"] = marks + [i] if value else marks


def _sent(f):
    """undo on an exam sent since: the waiting and on-site sentences become "Sent since" """
    try:
        return f()
    except Refused as e:
        if str(e) in (WAITING, ON_SITE):
            raise Refused(SENT) from None
        raise


def undo(env, step, st=None) -> dict:
    """take a step back: the parts whose stored value is still the step's after are put back, the rest stay (and are tried
    again on the next undo). -> the line's Step-like dict (not itself undoable). Marks the step undone when all went back"""
    if not isinstance(step, dict) or not isinstance(step.get("parts"), dict):
        raise Refused(WRONG)
    if step.get("undone"):
        raise Refused(TAKEN)
    if not step.get("can_undo"):
        raise Refused(NOT_UNDOABLE)
    if step.get("action") == "start":
        return _undo_start(env, step, st)
    parts, places = step["parts"], step.get("places") or {}
    units, done = _units(parts), {}

    def fn(s):
        back = [u for u in units if all(_value(s, k) == parts[k][1] for k in u)]
        stay = [u for u in units if u not in back]
        why = f"{_join([_label(s, u, parts) for u in stay])} changed since ({_stamp(s)})" if stay else ""
        if not back:
            raise Refused(f"Nothing was taken back: {why}.")
        order = lambda u: min(places.get(k.partition(":")[2], len(s["papers"])) if k.startswith("paper:") else -1 for k in u)
        for u in sorted(back, key=order):
            for k in u:
                _put(s, k, parts[k][0], places)
        if stay:
            one = len(stay) == 1
            done["text"] = (f"{len(back)} of {len(units)} changes are taken back. {why[0].upper()}{why[1:]}, "
                            f"so {'it stays as it is' if one else 'they stay as they are'}.")
        else:
            done["text"] = undo_text(step)
        done["back"] = [k for u in back for k in u]
    try:
        before, after = _sent(lambda: env.change(step.get("exam"), fn, lambda b, a: done.get("text") or undo_text(step)))
    except ODD:
        raise Refused(WRONG) from None
    rev = _schedules.rev_of(after)
    line_parts = {k: parts[k] for k in done["back"]}
    step["parts"] = {k: v for k, v in parts.items() if k not in line_parts}
    if not step["parts"]:
        step.update(undone=True, can_undo=False)
    if st is not None:
        st.last_rev = rev
        if step.get("action") in STALE:
            st.offered = {}
    return dict(_step("undo", step.get("exam"), done["text"], line_parts, rev, of=step.get("id")), can_undo=False)


def _undo_start(env, step, st):
    last = getattr(st, "last_rev", None) if st is not None else None
    rev = last if last is not None else step.get("rev_after")
    _sent(lambda: env.remove(step.get("exam"), rev, undo_text(step)))
    step.update(undone=True, can_undo=False)
    if st is not None and getattr(st, "exam", None) == step.get("exam"):
        st.exam, st.last_rev = None, None
    return dict(_step("undo", step.get("exam"), undo_text(step), {}, None, of=step.get("id")), can_undo=False)

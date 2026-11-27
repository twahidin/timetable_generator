"""Absence records: a teacher's absence (asked by them or planned by someone else), its lessons, work and relief.
One JSON file each under DATA/relief/absences."""
import copy, datetime, os, secrets, shutil, threading
from zoneinfo import ZoneInfo

import store
from accounts import people as _accounts
from relief import cover as _cover        # cover imports this module too: neither reads the other's names at import
from relief import files as _files
from relief import free as _free
from relief import lessons as _lessons
from relief import settings as _settings

DIR = os.path.join(store.DATA, "relief", "absences")
_LOCK = threading.Lock()
REASONS = ("Medical", "Child sick", "Course", "Other")
CHANGED = "Your timetable has changed since you opened this page. Open it again."
WRONG = "Check the absence and try again."
NOT_YOURS = "You cannot change this absence."
CANCELLED = "This absence was cancelled."
NO_FILES_YET = "Add files after the absence is sent."
SAY_WHY = "Say why in a line."
PAST_LESSON = "This lesson is in the past."
PAST_ABSENCE = "This absence is in the past."
ACKED = "This was acknowledged already."
NO_NEED = "This lesson does not need relief."
APPROVED_ALREADY = "This lesson's relief is approved already: ask the relief team to change it."
IS_SPLIT = "This lesson is split: the relief team chooses for each part."
STARTED = "This lesson has started: ask the relief team to change it."
NO_LESSONS = "There are no lessons to cover in that time."
TOO_MANY = "A lesson can have at most 5 files."
MAX_DATES, MAX_TEXT, MAX_LINK = 20, 2000, 500
COVER = ("relief", "relief_by", "pick", "approved", "sent_out", "ack", "change", "history", "parts")     # a lesson's cover (relief.cover), moved whole


def _path(id):
    id = str(id)
    if not id.isalnum(): raise ValueError(WRONG)
    return os.path.join(DIR, f"{id}.json")


def _now():
    return datetime.datetime.now(ZoneInfo(os.environ.get("SCHOOL_TZ") or "Asia/Singapore")).isoformat(timespec="seconds")


def _say(d):
    return f"{d:%a} {d.day} {d:%b}"


def load(id):
    try: p = _path(id)
    except ValueError: return None
    r = store.read_json(p, None)
    return r if isinstance(r, dict) and r.get("id") else None


def all_records():
    out = []
    if os.path.isdir(DIR):
        for f in os.listdir(DIR):
            if f.endswith(".json"):
                r = store.read_json(os.path.join(DIR, f), None)
                if isinstance(r, dict) and r.get("id"): out.append(r)
    out.sort(key=lambda r: r.get("at") or "", reverse=True)
    return out


def for_teacher(name):
    return [r for r in all_records() if r.get("teacher") == name]


def planned_by(name):
    return [r for r in all_records() if r.get("how") == "planned" and r.get("by") == name]


def _save(r):
    os.makedirs(DIR, exist_ok=True)
    store.write_json(_path(r["id"]), r)


def _pub(pub):
    return pub if pub is not None else store.published()


def _check_work(work, allow_files=False):
    """-> clean dict(text, link, files); files are checked by the caller"""
    work = work if isinstance(work, dict) else {}
    text, link = work.get("text") or "", work.get("link") or ""
    if not isinstance(text, str) or not isinstance(link, str): raise ValueError(WRONG)
    text, link = text.strip(), link.strip()
    if link and (not link.lower().startswith(("http://", "https://")) or len(link) > MAX_LINK):
        raise ValueError("A link starts with http:// or https://.")
    if len(text) > MAX_TEXT: raise ValueError("Keep the work under 2000 characters.")
    files = work.get("files") or []
    if not isinstance(files, list): raise ValueError(WRONG)
    return dict(text=text, link=link, files=files)


def _int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _iso_dates(v, today):
    bad = ValueError("Choose up to 20 school days, today or later.")
    if not isinstance(v, (list, tuple)) or not v or len(v) > MAX_DATES: raise bad
    out = []
    for x in v:
        try: d = x if isinstance(x, datetime.date) else datetime.date.fromisoformat(str(x))
        except ValueError: raise bad
        if not isinstance(x, (str, datetime.date)) or d < today: raise bad
        if d not in out: out.append(d)
    return sorted(out)


def _no_overlap(records, teacher, lessons):
    """refuse when another absence of the teacher, not cancelled, has a needed lesson overlapping one of lessons (dicts with ISO
    dates); a backup (exams) never refuses: the teacher's own absence takes its lessons over (_take_over)"""
    for r in records:
        if r.get("cancelled") or r.get("exams") or r.get("teacher") != teacher: continue
        for old in r["lessons"]:
            if not old.get("needed"): continue
            for x in lessons:
                if x["date"] == old["date"] and _free._overlap(x["p"], x["n"], old["p"], old["n"]):
                    raise ValueError(f"{r['by']} has already sent an absence for {teacher} on {_say(datetime.date.fromisoformat(x['date']))}.")


def as_now(records, x, links):
    """lesson x of a teacher (from lessons.on_date) as it is then: others, its other teachers who are there (with one of them there it
    needs no relief unless it is asked for); stopped, why an approved exam or event stops it, or "" (it is kept as any other, with
    nothing to cover while it is)"""
    return dict(x, others=_free.there_then(records, x["others"], x["date"], x["p"], x["n"], links=links), stopped=_cover.stopped(links, x))


def something_to_cover(teacher, dates, periods, needed_or_stopped, links):
    """refuses an absence with nothing in it: no lesson needed or stopped (needed_or_stopped: whether each is), and no exam or event duty
    of the teacher's in that time"""
    if not any(needed_or_stopped) and not (links is not None and any(links.duties(teacher, d, tuple(periods) if periods else None) for d in dates)):
        raise ValueError(NO_LESSONS)


def new(data, pub, by, how, may_choose=False, links=None) -> dict:
    pub = _pub(pub)
    if how not in ("asked", "planned") or not isinstance(data, dict): raise ValueError(WRONG)
    settings = _settings.load(pub)
    cal = settings["calendar"]
    staff = {p["name"] for p in _accounts.listing(pub)}     # the published teachers and the staff added in the accounts
    teacher = data.get("teacher")
    if not isinstance(teacher, str) or teacher not in staff:
        raise ValueError(f"{teacher if isinstance(teacher, str) and teacher else 'That person'} is not on the published timetable or the staff list.")
    dates = _iso_dates(data.get("dates"), _lessons.today())
    for d in dates: _lessons.on_date(pub, cal, teacher, d)          # a date that is not a school day, or no calendar, raises its sentence
    periods = data.get("periods")
    if periods is not None:
        np = ((pub.get("model") or {}).get("NP"))
        ok = isinstance(periods, (list, tuple)) and len(periods) == 2 and all(_int(x) for x in periods) and 0 <= periods[0] <= periods[1]
        if ok and _int(np) and periods[1] >= np: ok = False
        if not ok: raise ValueError("Choose the periods again.")
        periods = [periods[0], periods[1]]
    reason, text = data.get("reason"), data.get("reason_text") or ""
    if reason not in REASONS or not isinstance(text, str) or len(text.strip()) > 200 or (reason == "Other" and not text.strip()):
        raise ValueError("Choose a reason; for Other, say why in a line.")
    remarks = data.get("remarks") or ""
    if not isinstance(remarks, str) or len(remarks.strip()) > 300: raise ValueError("Keep the remarks under 300 characters.")
    officer = data.get("reporting_officer") or ""
    if how == "asked" and (not isinstance(officer, str) or officer not in staff): raise ValueError("Choose your reporting officer.")
    if not isinstance(officer, str) or (officer and officer not in staff): officer = ""
    asked = data.get("lessons") or []
    if not isinstance(asked, list) or not all(isinstance(x, dict) for x in asked): raise ValueError(WRONG)
    mine = {}
    for d in dates:
        for x in _lessons.on_date(pub, cal, teacher, d, periods=tuple(periods) if periods else None):
            mine[x["key"]] = x
    asks = {}
    for x in asked:
        if x.get("key") not in mine: raise ValueError(CHANGED)
        asks[x["key"]] = x
    with _LOCK:
        records = all_records()
        built = []
        for key, x in mine.items():
            a = asks.get(key, {})
            # a shared lesson needs no relief unless the client says so, but only while one of its other teachers is there:
            # others keeps those not away then, and with none there it is an ordinary lesson (needed unless the client says not).
            # An absence sent earlier that said "{them} is there" is left as it is; this one covers the lesson.
            x = as_now(records, x, links)
            there, stopped = x["others"], x.pop("stopped")
            # A lesson an approved exam or event stops is kept as any other (needed, unless the client or a co-teacher says
            # not): the stop is worked out wherever it matters (cover.stopped) and never written, so a lesson that happens
            # again, the exam withdrawn, still has its relief asked for.
            if there:
                needed = a.get("needed") is True
                not_needed = None if needed else dict(by="app", why=f"{' and '.join(there)} is there")
            else:
                needed = a.get("needed") is not False
                not_needed = None if needed else dict(by=by, why="Not needed")
            built.append(dict(x, date=x["date"].isoformat(), needed=needed, not_needed=not_needed, relief=None, relief_by=None,
                              work=dict(text="", link="", files=[]), _ask=a, _stopped=bool(stopped)))
        something_to_cover(teacher, dates, periods, [x["needed"] or x["_stopped"] for x in built], links)
        _no_overlap(records, teacher, [x for x in built if x["needed"]])
        pending = dict(teacher=teacher, dates=[d.isoformat() for d in dates], periods=periods, cancelled=None, lessons=[])
        if not may_choose and any(x["needed"] and not x["_stopped"] and x["_ask"].get("relief") for x in built):
            raise ValueError("Only management and the relief team choose relief teachers.")     # before free_then: no probing who is free
        moving = _moving(records, teacher, built)
        for o, moved in moving:
            for x in built:
                if x["needed"] and not x["_stopped"] and x["key"] in moved: _may_replace(moved[x["key"]], x, x["_ask"].get("relief"))
        chosen = {}           # {key: the relief teacher chosen in this absence}
        for x in built:
            name = x["_ask"].get("relief")
            if name and x["needed"] and not x["_stopped"]:          # nobody is chosen for a lesson that does not happen (as choose)
                lesson = dict(x, date=datetime.date.fromisoformat(x["date"]))
                free = _free.free_then(pub, settings, records + [pending], lesson, teacher, links=links)
                if name not in [p["name"] for g in free["groups"] for p in g["people"]]:
                    raise ValueError(f"{name} is not free for {' and '.join(x['classes'])} {x['subject']} then.")
                x["relief"], x["relief_by"] = name, by
                chosen[x["key"]] = name
            pending["lessons"].append(x)
        for x in built:      # the work checks come last
            x.pop("_stopped")
            x["work"] = _check_work(x.pop("_ask").get("work"))
            if x["work"]["files"]: raise ValueError(NO_FILES_YET)
        r = dict(id=secrets.token_hex(6), teacher=teacher, dates=pending["dates"], periods=periods, reason=reason, reason_text=text.strip(),
                 remarks=remarks.strip(), reporting_officer=officer, by=by, how=how, at=_now(), acknowledged=None, cancelled=None,
                 lessons=pending["lessons"])
        backups = _take_over(moving, r)
        if how == "planned":      # a head's own choice is approved and sent out at once; one asked by the teacher waits for the team
            for x in r["lessons"]:
                if x["key"] in chosen and x.get("relief") == chosen[x["key"]] and not x.get("approved"): _cover.chose(r, x, x, x["relief"], by, r["at"])
        _save(r)
        for o in backups: _save(o)      # after the absence: a lesson is never left in neither
    return r


def set_via(id, via):
    """how an absence was asked, when not on the page ("telegram": relief/asking.py); one asked on the page has no via"""
    with _LOCK:
        r = load(id)
        if r is None: raise ValueError(WRONG)
        r["via"] = via
        _save(r)
    return r


# ---- backups: the lessons of someone on an exam duty or at an event, sent by exams.relief_links.sync as planned absences
def _copy_files(old_id, new_id, files):
    """the work files of a lesson moving from one absence to another, copied into the new one's folder (the old absence may
    still list them); a file that is not there any more is left out"""
    out = []
    for f in files if isinstance(files, list) else []:
        try:
            src = _files.path(old_id, f.get("id"))
            if not src: continue
            folder = _files._folder(new_id)
            os.makedirs(folder, exist_ok=True)
            shutil.copyfile(src, os.path.join(folder, os.path.basename(src)))
            out.append(dict(f))
        except (OSError, ValueError, AttributeError, TypeError): continue
    return out


def _moved_work(work, old, old_id, new_id):
    """the work of a lesson moving in from another absence: the text and link given here, else the old ones, and the old files"""
    ow = old.get("work") if isinstance(old.get("work"), dict) else {}
    return dict(text=work.get("text") or ow.get("text") or "", link=work.get("link") or ow.get("link") or "",
                files=list(work.get("files") or []) + _copy_files(old_id, new_id, ow.get("files")))


def _dates_and_periods(lessons):
    """a backup's dates (ISO, sorted) and periods ([from, to], 0-based, the span of its lessons)"""
    lessons = [x for x in lessons if isinstance(x, dict)]
    return (sorted({x["date"] for x in lessons}),
            [min(int(x["p"]) for x in lessons), max(int(x["p"]) + int(x.get("n") or 1) - 1 for x in lessons)] if lessons else None)


def _move_cover(o, y, r, x):
    """the cover of the backup o's lesson y becomes that of lesson x of the new absence r: its relief and how far that has
    gone (COVER), with its history. A planner's choice in r replaces a pick still waiting (written down as dropped; new
    refused one against an approved relief of someone else, or a split lesson: _may_replace); a lesson r says needs no relief ends
    the cover, as not_needed does"""
    for c in _cover.covers(y): _cover._settle(o, c)       # a planner's choice gets its pick and history line as o dated it
    chosen = (x["relief"], x["relief_by"]) if x["needed"] and x.get("relief") and not y.get("approved") else None
    x.update({k: copy.deepcopy(y[k]) for k in COVER if k in y})
    if not x["needed"]:
        why = x.get("not_needed") or {}
        _cover.clear(r, x, why.get("by") or r["by"], why.get("why"), r["at"])
    elif chosen:
        if x.get("relief") and x["relief"] != chosen[0]: _cover._log(x, "dropped", x["relief"], r["by"], r["at"])
        x.update(_cover.OPEN)
        x["relief"], x["relief_by"] = chosen


def _moving(records, teacher, lessons):
    """[(backup, {key: its lesson})]: the needed lessons of the teacher's backups that are among lessons (a new absence's)"""
    keys, out = {x["key"] for x in lessons}, []
    for o in records:
        if o.get("cancelled") or not o.get("exams") or o.get("teacher") != teacher: continue
        moved = {y["key"]: y for y in o.get("lessons") or [] if isinstance(y, dict) and y.get("needed") and y.get("key") in keys}
        if moved: out.append((o, moved))
    return out


def _may_replace(y, x, name):
    """what choose refuses on a backup's lesson y is refused of a new absence's lesson x too, naming it: choosing name for a
    lesson the relief team has split, or has approved for someone else"""
    if not name: return
    no = IS_SPLIT if y.get("parts") else APPROVED_ALREADY if y.get("approved") and y.get("relief") != name else ""
    if no: raise ValueError(f"{' and '.join(x['classes'])} {x['subject']}: {no[0].lower()}{no[1:]}")


def _take_over(moving, r):
    """own absence wins (P10): a lesson of the new absence r that is a needed lesson of one of the teacher's backups (moving,
    from _moving) moves in with its whole cover (_move_cover) and its work; the backup drops it, and is cancelled once no
    lesson is left (a lesson marked not needed stays in it, so the next sync does not send it again). Runs inside _LOCK and
    never touches the exams lock. -> the backups changed (to save)"""
    mine = {x["key"]: x for x in r["lessons"]}
    changed = []
    for o, moved in moving:
        for key, y in moved.items():
            x = mine[key]
            _move_cover(o, y, r, x)
            x["work"] = _moved_work(x["work"], y, o["id"], r["id"])
        o["lessons"] = [y for y in o["lessons"] if not (isinstance(y, dict) and y.get("key") in moved)]
        if any(isinstance(y, dict) for y in o["lessons"]):
            o["dates"], o["periods"] = _dates_and_periods(o["lessons"])
        else:
            o["cancelled"] = dict(at=_now(), by="app", why=f"Moved to {r['teacher']}'s own absence.")
        changed.append(o)
    return changed


def _backup_lesson(records, teacher, x, links):
    """one lesson of a backup (x from lessons.on_date): needed unless one of its other teachers is there (there_then, as new
    decides), no relief, no work; None while the teacher is away in an absence of their own (that absence covers it)"""
    iso = _free._iso(x["date"])
    try: away = _free._absent_then([r for r in records if not r.get("exams")], teacher, iso, x["p"], x["n"], links=links)
    except (KeyError, TypeError, ValueError, IndexError): away = False      # a malformed absence never stops a backup
    if away: return None
    there = _free.there_then(records, x.get("others") or [], iso, x["p"], x["n"], links=links)
    return dict(x, date=iso, others=there, needed=not there, not_needed=dict(by="app", why=f"{' and '.join(there)} is there") if there else None,
                relief=None, relief_by=None, work=dict(text="", link="", files=[]))


def from_exams(teacher, lessons, source, by, reason_text, records=None, links=None):
    """a backup (P6): a planned absence of someone on an exam duty or at an event, holding exactly lessons (dicts from
    lessons.on_date, ISO dates; see _backup_lesson), source dict(id, kind) the schedule. -> the record, or None (nothing
    saved) when no lesson is needed. records None: read here, under the lock"""
    with _LOCK:
        records = all_records() if records is None else records
        built = [y for y in (_backup_lesson(records, teacher, x, links) for x in lessons) if y]
        if not any(y["needed"] for y in built): return None
        dates, periods = _dates_and_periods(built)
        r = dict(id=secrets.token_hex(6), teacher=teacher, dates=dates, periods=periods, reason="Other", reason_text=reason_text, remarks="",
                 reporting_officer="", by=by, how="planned", at=_now(), acknowledged=None, cancelled=None, lessons=built,
                 exams=dict(id=source["id"], kind=source["kind"]))
        _save(r)
    return r


def update_exams(id, keep_keys, add_lessons, by, reason_text, today, why="The duty changed.", links=None) -> dict:
    """change a backup in place (never cancel and make again, so what relief did on it stays): every lesson dated today or
    later whose key is not in keep_keys goes (a lesson dated before today always stays: it is history and counts in relief's
    periods), add_lessons come in (as from_exams decides; a key it holds already is left), by and reason_text are brought up
    to date (None: as they are), acknowledged is cleared and changed_at stamped when a lesson came in (the person must look
    again; All Relief Requests shows it new), and dates and periods follow the lessons. A lesson that goes with a relief or a history has
    its cover ended first (relief.cover.clear, why) and is kept, without its work, in the record's gone list (gone: dict(at,
    why)), so its history is not lost. Cancelled (why) only when no lesson at all is left. today: the caller's (one clock).
    -> the record; {} when it is not there; a cancelled one as it is"""
    iso = _free._iso(today)
    keep = set(keep_keys or ())
    with _LOCK:
        r = load(id)
        if r is None: return {}
        if r.get("cancelled"): return r
        before = list(r.get("lessons") or [])
        kept = [x for x in before if not isinstance(x, dict) or str(x.get("date") or "") < iso or x.get("key") in keep]
        have = {x.get("key") for x in kept if isinstance(x, dict)}
        records, added = all_records(), []
        for x in add_lessons or []:
            if x["key"] in have: continue
            y = _backup_lesson(records, r["teacher"], x, links)
            if y:
                added.append(y); have.add(y["key"])
        r["lessons"] = kept + added
        for x in before:
            if isinstance(x, dict) and x not in kept: _gone(r, x, why)
        if by is not None: r["by"] = by
        if reason_text is not None: r["reason_text"] = reason_text
        if added: r["acknowledged"], r["changed_at"] = None, _now()
        if any(isinstance(x, dict) for x in r["lessons"]):
            r["dates"], r["periods"] = _dates_and_periods(r["lessons"])
        else:
            r["cancelled"] = dict(at=_now(), by="app", why=why)
        _save(r)
        still = {f.get("id") for x in r["lessons"] if isinstance(x, dict) for f in (x.get("work") or {}).get("files") or [] if isinstance(f, dict)}
        for x in before:
            if isinstance(x, dict) and x not in kept:
                for f in (x.get("work") or {}).get("files") or []:
                    if isinstance(f, dict) and f.get("id") not in still: _files.delete(id, f.get("id"))
    return r


def _gone(r, x, why):
    """lesson x leaving backup r: its cover ends (the relief written down as dropped), and it is kept in r["gone"] when there
    is anything to keep"""
    if not isinstance(x.get("parts") or [], list): return
    now = _now()
    _cover.clear(r, x, "app", why, now)
    if not any(c.get("history") for c in [x] + list(x.get("parts") or [])): return
    r.setdefault("gone", []).append(dict({k: v for k, v in x.items() if k != "work"}, gone=dict(at=now, why=why)))


def exams_records(source_id) -> list:
    """the backups of one schedule that are not cancelled"""
    return [r for r in all_records() if not r.get("cancelled") and isinstance(r.get("exams"), dict) and r["exams"].get("id") == source_id]


def _editable(id):
    r = load(id)
    if r is None: raise ValueError(WRONG)
    if r.get("cancelled"): raise ValueError(CANCELLED)
    return r


def _lesson(r, key):
    for x in r["lessons"]:
        if x["key"] == key: return x
    raise ValueError(CHANGED)


def _owner(r, by):
    return by == r["teacher"] or (r["how"] == "planned" and by == r["by"])


def _past(x):
    """refuse a change to a lesson dated before today (the school's date)"""
    if datetime.date.fromisoformat(x["date"]) < _lessons.today(): raise ValueError(PAST_LESSON)


def _ids(v):
    """a list of file ids (strings), or WRONG"""
    if not isinstance(v, list) or len(v) > 50 or not all(isinstance(f, str) for f in v): raise ValueError(WRONG)
    return set(v)


def acknowledge(id, by):
    with _LOCK:
        r = _editable(id)
        if by != r["teacher"] or r["how"] != "planned": raise ValueError(f"Only {r['teacher']} can acknowledge this.")
        if r["acknowledged"]: raise ValueError(ACKED)
        r["acknowledged"] = dict(at=_now())
        _save(r)
    return r


def set_work(id, key, work, by):
    """work = {text, link, files: [{id, name}], known: [the file ids on the lesson when the caller's page read it]}; a file on
    the lesson now that is not in known (someone else added it meanwhile) is kept; a file deleted is one the caller knew,
    took off, and no lesson of the absence lists any more"""
    if not isinstance(work, dict) or not isinstance(work.get("files"), list): raise ValueError(WRONG)
    known = _ids(work.get("known"))
    return _change_work(id, key, by, lambda now: (work, known))


def add_file(id, key, f, by):
    """the file f (as files.save gives it) added to the lesson's work as it is by then; refused as set_work refuses"""
    return _change_work(id, key, by, lambda now: (dict(now, files=now["files"] + [f]), {o["id"] for o in now["files"]}))


def _change_work(id, key, by, make):
    """the lesson's work is set to make(what it is now)'s: (the work, the file ids its maker knew)"""
    with _LOCK:
        r = _editable(id)
        if not _owner(r, by): raise ValueError(NOT_YOURS)
        x = _lesson(r, key)
        _past(x)
        work, known = make(x["work"])
        w = _check_work(work)
        if len(w["files"]) > _files.PER_LESSON: raise ValueError(TOO_MANY)
        kept = []
        for f in w["files"]:
            fid = f.get("id") if isinstance(f, dict) else f
            p = _files.path(id, fid)
            if not p: raise ValueError(CHANGED)
            if fid in [k["id"] for k in kept]: continue
            old = next((o for o in x["work"]["files"] if o["id"] == fid), None)
            name = old["name"] if old else _files.clean_name(f.get("name") if isinstance(f, dict) else "")
            ext = os.path.splitext(p)[1]      # the name always ends with the stored file's own extension
            kept.append(dict(id=fid, name=name if name.lower().endswith(ext.lower()) else _files.fit(name, ext), size=os.path.getsize(p)))
        sent = {k["id"] for k in kept}
        kept += [o for o in x["work"]["files"] if o["id"] not in known and o["id"] not in sent]
        if len(kept) > _files.PER_LESSON: raise ValueError(TOO_MANY)
        before = {o["id"] for o in x["work"]["files"]}
        x["work"] = dict(text=w["text"], link=w["link"], files=kept)
        _save(r)
        still = {o["id"] for l in r["lessons"] for o in l["work"]["files"]}
        for fid in before - still: _files.delete(id, fid)
    return r


def _may_change(r, by, team):
    """the absent teacher, its planner, or (team: the caller has relief.team, asked by relief/web.py through has) the relief team"""
    if not _owner(r, by) and not team: raise ValueError(NOT_YOURS)


def not_needed(id, key, why, by, *, team=False):
    why = why.strip() if isinstance(why, str) else ""
    with _LOCK:
        r = _editable(id)
        _may_change(r, by, team)
        x = _lesson(r, key)
        _past(x)
        if not 1 <= len(why) <= 200: raise ValueError(SAY_WHY)
        _cover.clear(r, x, by, why, _now())       # its relief, pick, approval, acknowledgement and request to change end
        x["needed"], x["not_needed"], x["relief"], x["relief_by"] = False, dict(by=by, why=why), None, None
        _save(r)
    return r


def needed_again(id, key, by, *, team=False):
    with _LOCK:
        r = _editable(id)
        _may_change(r, by, team)
        x = _lesson(r, key)
        _past(x)
        _no_overlap([o for o in all_records() if o["id"] != r["id"]], r["teacher"], [x])
        x["needed"], x["not_needed"] = True, None
        _save(r)
    return r


def _started(pub, x, now):
    """the lesson's first period has begun by now (a date-time); never for a lesson of a later day than today (the school's)"""
    from relief import hours as _hours     # hours imports fill, which imports cover and this module: read when called
    return datetime.date.fromisoformat(str(x["date"])) <= _lessons.today() and now >= _hours.starts(pub, x, x)


def _may_choose(r, x, by):
    """the planner may choose for lesson x: while nobody is approved for it, or on a planned absence while it is still by's own
    choice (on a teacher's own absence, which took a head's choice over from a backup, the relief team changes it on Today's Relief Assignments)"""
    return _cover.state(r, x, x) in ("open", "waiting") or (r.get("how") == "planned" and _cover.planned_by(x) == by)


def may_choose_again(r, x, me, pub) -> bool:
    """me may choose (or choose again) the relief teacher of lesson x of record r on the Plan page: one lesson, not split,
    needed, not started, and nobody approved for it yet or it is still me's own choice (choose)"""
    try:
        if r.get("cancelled") or x.get("parts") or not x.get("needed") or not _may_choose(r, x, me): return False
        if datetime.date.fromisoformat(str(x["date"])) < _lessons.today(): return False
        from relief import fill as _fill
        return not _started(pub, x, _fill._when(_now()))
    except (KeyError, TypeError, ValueError): return False


def choose(id, key, relief_name, by, pub, links=None):
    """the planner's choice; relief_name None or "" takes it off; the caller checks the relief.plan right. On a planned absence
    the choice is approved and sent out at once by the planner (cover.chose); on a teacher's own it is a pick waiting for the
    relief team, as before, with no approval, send out, acknowledgement or request to change left on it. Allowed while nobody
    is approved for the lesson, or on a planned absence while it is still by's own choice (cover.planned_by), else
    APPROVED_ALREADY: it is changed on the team's Today's Relief Assignments tab (choosing their own choice again changes
    nothing, so nobody is told twice); refused once the team has split the
    lesson (IS_SPLIT) and once its first period has begun (STARTED). Taking an approved choice off writes it down as dropped
    and the cover goes back to open, for the AI to pick and the team to approve. A lesson an approved exam or event stops
    (links.stopped) gets no relief teacher (taking one off still works)"""
    pub = _pub(pub)
    with _LOCK:
        r = _editable(id)
        x = _lesson(r, key)
        _past(x)
        if not x["needed"]: raise ValueError(NO_NEED)
        if x.get("parts"): raise ValueError(IS_SPLIT)
        if not _may_choose(r, x, by): raise ValueError(APPROVED_ALREADY)
        from relief import fill as _fill
        if _started(pub, x, _fill._when(_now())): raise ValueError(STARTED)
        stopped = links.stopped(x) if links is not None and relief_name else ""
        if stopped: raise ValueError(f"This lesson is not happening: {stopped}.")
        now = _now()
        if not relief_name:
            if x.get("relief"):
                _cover._settle(r, x)
                for gone in _cover.booked(x): _cover._log(x, "dropped", gone, by, now)
            x.update(_cover.OPEN)
        else:
            free = _free.free_then(pub, _settings.load(pub), all_records(), dict(x, date=datetime.date.fromisoformat(x["date"])), r["teacher"], links=links)
            if relief_name not in [p["name"] for g in free["groups"] for p in g["people"]]:
                raise ValueError(f"{relief_name} is not free for {' and '.join(x['classes'])} {x['subject']} then.")
            if r.get("how") == "planned":
                if relief_name == x.get("relief") and _cover.planned_by(x) == by: return r    # chosen already: nothing new to tell
                _cover.chose(r, x, x, relief_name, by, now)
                _save(r)
                return r
            if x.get("relief"):
                _cover._settle(r, x)
                if x["relief"] != relief_name: _cover._log(x, "dropped", x["relief"], by, now)   # the waiting pick it replaces
            pick = dict(who=relief_name, by="planner", reason=_cover.PLANNED.format(by=by, date=_say(datetime.date.fromisoformat(now[:10]))), at=now)
            x.update(_cover.OPEN)            # a waiting pick: no approval, send out, acknowledgement or request to change of another stays on it
            x["relief"], x["relief_by"], x["pick"] = relief_name, by, pick
            _cover._log(x, "pick", relief_name, "planner", now, pick["reason"])
        _save(r)
    return r


def cancel(id, why, by, *, team=False):
    """refused once every date of the absence is before today; an absence with a date still to come is cancelled whole"""
    why = why.strip() if isinstance(why, str) else ""
    with _LOCK:
        r = _editable(id)
        _may_change(r, by, team)
        if all(datetime.date.fromisoformat(d) < _lessons.today() for d in r["dates"]): raise ValueError(PAST_ABSENCE)
        if not 1 <= len(why) <= 200: raise ValueError(SAY_WHY)
        now, today = _now(), _lessons.today()
        r["cancelled"] = dict(at=now, by=by, why=why)
        for x in r["lessons"]:                   # the reliefs still to come end; a lesson before today keeps what it had
            if datetime.date.fromisoformat(x["date"]) >= today: _cover.clear(r, x, by, why, now)
        _save(r)
    return r


def matches_now(record, pub, cal):
    """the record with each lesson marked changed when the teacher no longer has it on the published timetable; a lesson
    dated before today is not read again (changed False): it is history, and All Relief Requests stays quick over a year of records"""
    today, out = _lessons.today(), dict(record)
    out["lessons"] = [dict(x, changed=datetime.date.fromisoformat(x["date"]) >= today and not _lessons.still_there(pub, cal, record["teacher"], x))
                      for x in record["lessons"]]
    return out

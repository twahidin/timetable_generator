"""The school's agreed list of exam papers, read inside a talk. The person pastes the list or gives a file; a job of its own
(a thread, at most 5 minutes, each piece read counting as one answer of the hour) reads it: by itself when the file is in
the app's own layout, else piece by piece through the AI reader with names made codes first. Nothing is put in before
every piece is read. Then the rows whose words are the timetable's own go in at once as one step with Take it back, the
rest wait once in a table "As written / Read as" for a yes, and what could not be matched is listed with the reason.

The raw text lives only in the job's own variables: it is never a line, never in the talk's messages, never logged. The AI
is told the app's result in a note before the person's next message. The talk's working, its slot and its lock are kept
as plan/talk.py keeps them for an answer: working ends and the slot is given back whatever happens."""
import copy
import secrets
import threading
import time

from exams import days as _days
from exams import papers as _papers
from plan import ai as _ai
from plan import listread as _listread
from plan import steps as _steps
from plan import talk as T
from plan.steps import Refused

LINES = 40                                          # lines of one piece read by the AI
STOPPED = "Stopped. Nothing of the list was put in."
TOO_LONG = "Reading the list took too long, so it stopped. Nothing of it was put in."
MOST_SAID = 5                                       # papers named in one "Changed by the list" line, errors in one check line
LIST_SAID = "The person has not said yes to the list in their own words."
NO_SUBJECTS = "Give the subjects the line stands for."
ALREADY = "The papers of the list were in the draft already."
BUTTONS = ("Yes, all", "Not now")
HEAD = ["As written", "Read as", "Date", "Start"]


class _End(Exception):
    """the job ends with this sentence as a sys line"""


def _n(n, one, many) -> str:
    return f"{n} {one if n == 1 else many}"


def _count(text) -> int:
    """the lines of a text that hold anything"""
    return sum(1 for l in text.split("\n") if l.strip())


def _shown(filename) -> str:
    name = str(filename or "").replace("\\", "/").rsplit("/", 1)[-1].strip()
    return name[:120] or "with no name"


# ---------------------------------------------------------------- the person gives a list
def _free(talk):
    """(under the talk's lock) Refused unless a list may start now"""
    if talk.closed:
        raise Refused(T.LOST)
    if talk.working or talk.busy:
        raise Refused(T.READING if talk.reading else T.WORKING)
    if talk.waiting:
        raise Refused(T.WAIT_LIST)
    if sum(l["kind"] == "me" for l in talk.lines) >= T.LIMITS["messages"]:
        raise Refused(T.LONG)


def paste(talk, env, text=None, filename=None, data=None, call=None):
    """a pasted text, or a file (filename, data) -> the job starts on its own thread and paste returns at once. Checked in
    this order: the right, the exam, the talk is free, no list waits, the text's or the file's limits"""
    env.may()
    if not talk.exam:
        raise Refused(T.NEED_EXAM)
    if T._exam_of(env, talk.exam) is None:
        raise Refused(T.GONE)
    with talk.lock:
        _free(talk)
    rows = None
    if data is not None or filename is not None:
        got = _listread.text_of(filename, data)             # its own sentences: a wrong kind, too big, too long
        if got.strip():
            rows = _listread.own_layout(filename, data)     # the app's own layout: read here, no AI and no slot of the AI
        said = f"Gave the file {_shown(filename)}."
    else:
        if not isinstance(text, str) or not text.strip():
            raise Refused(T.EMPTY_LIST)
        if len(text) > T.LIMITS["list"]:
            raise Refused(T.LONG_LIST)
        got, said = text, f"Pasted a list of {_n(_count(text), 'line', 'lines')}."
    if not got.strip():
        raise Refused(T.EMPTY_LIST)
    with talk.lock:
        _free(talk)                                         # again: another tab may have started something meanwhile
        stamp = T._take() if rows is None else None
        halt = threading.Event()
        talk.working, talk.reading, talk.halt = True, True, halt
        talk.progress = f"Reading the list: 0 of {_n(_count(got), 'line', 'lines')}"
        deadline = time.monotonic() + T.LIMITS["list_job"]
        try:
            talk.thread = threading.Thread(target=_job, args=(talk, env, halt, deadline, stamp, [got if rows is None else None, rows], call),
                                           daemon=True)
            talk.thread.start()
        except BaseException:
            talk.working, talk.reading, talk.progress = False, False, ""
            if stamp is not None:
                T._give(stamp, used=False)
            raise
        talk.add("me", said)                                # the list's own text is never a line
        talk.used = T._now()


# ---------------------------------------------------------------- the job
def _more():
    """one more answer of the hour for the next piece, or Refused(BUSY)"""
    with T._server:
        now = T._now()
        while T._starts and now - T._starts[0] >= 3600:
            T._starts.popleft()
        if len(T._starts) >= T.LIMITS["an_hour"]:
            raise Refused(T.BUSY)
        T._starts.append(now)


def _job(talk, env, halt, deadline, stamp, given, call):
    """the thread of one list: read, match, put in; working ends and the slot is given back whatever happens"""
    state = dict(used=True, put=None)
    try:
        try:
            _run(talk, env, halt, deadline, given, call, state)
        except (_End, Refused) as e:
            with talk.lock:
                talk.add("sys", str(e))
                talk.notes.append(f"The person gave a list of papers. {str(e)}")
        except Exception as e:
            T._fault(e)
            n = state["put"]
            with talk.lock:
                if n is None:
                    talk.add("sys", _ai.READ_FAILED)
                    return
                are = "1 paper is in" if n == 1 else f"{n} papers are in"
                talk.add("sys", f"The rest of the list could not be finished. {are}; the other lines were not put in: give them again.")
                talk.notes.append(f"The person gave a list of papers. {_n(n, 'paper', 'papers')} in the timetable's own words "
                                  "went in at once, with Take it back. The rest of the list could not be finished, so its other "
                                  "lines were not put in.")
    finally:
        given.clear()                                       # the raw text and the rows are gone with the job
        try:
            if stamp is not None:
                T._give(stamp, state["used"])
        finally:
            with talk.lock:
                talk.working, talk.reading, talk.progress, talk.used = False, False, "", T._now()


def _over(halt, deadline):
    if halt.is_set():
        raise _End(STOPPED)
    if time.monotonic() >= deadline:
        raise _End(TOO_LONG)


def _run(talk, env, halt, deadline, given, call, state):
    text, rows = given
    s = T._exam_of(env, talk.exam)
    if s is None:
        raise _End(T.GONE)
    levels = [x for x in s.get("levels") or [] if isinstance(x, str)]
    model = (env.pub() or {}).get("model")
    model = model if isinstance(model, dict) else {}
    if rows is None:
        rows = _read(talk, env, halt, deadline, text, s, levels, model, call, state)
    del text
    given[0] = None
    _over(halt, deadline)
    m = _listread.match(rows, model, levels)
    a, changed = _put_plain(talk, env, halt, m["plain"], state)
    groups = _groups(m["other"])
    with talk.lock:
        line = talk.add("list", _summary(a, _lines(groups), len(m["unmatched"])))
        lid = secrets.token_hex(6) if groups else None
        line.update(table=_table(groups), buttons=list(BUTTONS) if groups else [],
                    left=[dict(line=u["line"], text=u["why"]) for u in m["unmatched"]], list=lid)
        if lid:
            talk.lists[lid] = dict(n=line["n"], other=m["other"])
            talk.waiting = lid
        talk.notes.append(" ".join(x for x in (_note(a, groups, m["unmatched"]), changed) if x))


def _read(talk, env, halt, deadline, text, s, levels, model, call, state) -> list:
    """the rows of every piece, names back and lines the list's own; nothing is put in here"""
    names = talk.names
    total = _count(text)
    start = s.get("start") if isinstance(s.get("start"), str) else ""
    facts = names.scrub(dict(levels=levels, subjects={lv: sorted(_listread._subjects(model, lv)) for lv in levels},
                             year=int(start[:4]) if start[:4].isdigit() else None), "app")
    rows, done, first = [], 0, True
    lead = len(text) - len(text.lstrip("\n"))             # pieces leaves out the blank lines before the first: count them
    for k, piece in enumerate(_listread.pieces(text, LINES)):
        _over(halt, deadline)
        here = _count(piece)
        if not here:
            continue
        env.may()                                           # a right that ended sends nothing more
        if not first:
            _more()                                         # each piece is one answer of the hour
        first = False
        try:
            got = _ai.read_piece(names.out(piece, "list"), facts, call=call, stop=halt, deadline=deadline)
        except _ai.ReadFailed as e:
            _over(halt, deadline)
            raise _End(str(e)) from None
        for r in got:
            r = T._back(names, r)
            r["line"] += k * LINES + lead
            rows.append(r)
        done += here
        with talk.lock:
            talk.progress = f"Reading the list: {done} of {_n(total, 'line', 'lines')}"
    if first:
        state["used"] = False                               # nothing was sent to the AI
    return rows


def _put_plain(talk, env, halt, plain, state) -> tuple:
    """the rows in the timetable's own words go in as one step -> (how many papers are in, what the list changed for the AI)"""
    if not plain:
        return 0, ""
    with talk.lock:
        talk.progress = T.FILLING
    _over(halt, deadline=float("inf"))
    try:
        step = _steps.run(env, talk, "put_list", dict(papers=_listread.to_papers(plain)))
    except Refused as e:
        if str(e) == _steps.SAME:
            return len(plain), ""
        raise _End(str(e)) from None
    n = state["put"] = _papers_in(step)
    step["text"] = (f"Put {n} papers in the draft: their words are the timetable's own" if n != 1
                    else "Put 1 paper in the draft: its words are the timetable's own")
    _did(talk, step)
    changed = _changed(talk, step)
    _after_put(talk, env, {})
    return n, changed


def _papers_in(step) -> int:
    return sum(1 for k, v in step["parts"].items() if k.startswith("paper:") and v[1] is not None)


def _did(talk, step):
    with talk.lock:
        talk.steps[step["id"]] = step
        talk.add("did", talk.names.back(step["text"]), step=step["id"], undo=bool(step.get("can_undo")))


def _when(p) -> str:
    m = p.get("minutes")
    length = f"{m} min" if isinstance(m, int) and not isinstance(m, bool) else "no length"
    if p.get("date") and p.get("start"):
        return f"{p['start']} on {_days.nice(p['date'])}, {length}"
    if p.get("date"):
        return f"no start on {_days.nice(p['date'])}, {length}"
    return f"no time, {length}"


def _changed(talk, step) -> str:
    """one sys line naming each paper already there whose date, start or length the list's step changed (at most 5) -> the
    same sentences for the AI's note, "" when none"""
    said = [f"{_papers.label(a)}: was {_when(b)}, now {_when(a)}." for k, (b, a) in step["parts"].items()
            if k.startswith("paper:") and b is not None and a is not None
            and any(b.get(x) != a.get(x) for x in ("date", "start", "minutes"))]
    if not said:
        return ""
    more = [f"and {len(said) - MOST_SAID} more: see the Papers tab."] if len(said) > MOST_SAID else []
    shown = said[:MOST_SAID] + more
    with talk.lock:
        talk.add("sys", talk.names.back("Changed by the list:\n" + "\n".join(shown)))
    return "Changed by the list: " + " ".join(shown)


def _after_put(talk, env, seen):
    """the app's own check lines after the list's step, and its errors (the first 5) -> the checks, or None"""
    try:
        c = T._checks(talk, env, seen)
        errors = [e for e in (c or {}).get("errors") or [] if isinstance(e, str)]
        if errors:
            more = f"\nand {len(errors) - MOST_SAID} more: see the Papers tab." if len(errors) > MOST_SAID else ""
            with talk.lock:
                talk.add("sys", "The app's check says:\n" + "\n".join(errors[:MOST_SAID]) + more)
        return c
    except Exception as e:                                  # the step is done: a fault in its checks never hides that
        T._fault(e)
        return None


# ---------------------------------------------------------------- the list line
def _groups(other) -> list:
    """[(key, [entries])] of the other entries, one per paper as written: key = (line, level, words as written, paper words),
    so a list line that gives two papers (two papers of one subject's words, or one line for two levels) is two groups, each
    with its own date and start. In order"""
    out = {}
    for e in other:
        out.setdefault((e["line"], e["level"], e["written"], _steps._fold(e["paper"])), []).append(e)
    return list(out.items())


def _lines(groups) -> int:
    """how many list lines the groups come from"""
    return len({k[0] for k, _ in groups})


def _read_as(es) -> str:
    return ", ".join(dict.fromkeys(e["subject"] for e in es))


def _written(e) -> str:
    return " ".join(x for x in (e["level"], e["written"], e["paper"]) if x)


def _table(groups):
    if not groups:
        return None
    rows = [[_written(es[0]), _read_as(es), _days.nice(es[0]["date"]) if es[0]["date"] else "", es[0]["start"] or ""]
            for _, es in groups]
    return dict(head=list(HEAD), rows=rows)


def _summary(a, b, c) -> str:
    parts = [x for x in (a and ("1 paper is in." if a == 1 else f"{a} papers are in."),
                         b and ("1 line needs a yes." if b == 1 else f"{b} lines need a yes."),
                         c and ("1 line was not put in." if c == 1 else f"{c} lines were not put in.")) if x]
    return " ".join(parts) or "No paper was found in the list."


def _note(a, groups, unmatched) -> str:
    out = ["The person gave a list of papers and the app read it."]
    if a:
        out.append(f"{_n(a, 'paper', 'papers')} in the timetable's own words went in at once, with Take it back.")
    if groups:
        out.append("These lines wait for the person's Yes, all or Not now in a table: " + "; ".join(
            f'line {k[0]} "{_written(es[0])}" read as {_read_as(es)}' for k, es in groups) + ".")
    if unmatched:
        out.append("These lines were not put in: " + " ".join(
            u["why"] if u["why"].startswith(("Row ", "A row")) else f"Line {u['line']}: {u['why']}" for u in unmatched))
    return " ".join(out)


def _answered(talk, lid):
    """(under the talk's lock) the list waits no more: its buttons go"""
    st = talk.lists.pop(lid, None)
    if talk.waiting == lid:
        talk.waiting = None
    for l in talk.lines:
        if st is not None and l["n"] == st["n"]:
            l["buttons"], l["list"] = [], None
    return st


# ---------------------------------------------------------------- the yes
def _put_waiting(talk, env, seen):
    """the waiting lines go in as one step -> (its text, the checks or None, what it changed for the AI); Refused (and the list still waits) when the
    step is refused"""
    with talk.lock:
        lid = talk.waiting
        if lid is None:
            raise Refused(T.NO_LIST)
        other = copy.deepcopy(talk.lists[lid]["other"])
    try:
        step = _steps.run(env, talk, "put_list", dict(papers=_listread.to_papers(other)))
    except Refused as e:
        if str(e) != _steps.SAME:
            raise
        step = None
    with talk.lock:
        _answered(talk, lid)
        if step is None:
            talk.add("sys", ALREADY)
    if step is None:
        return ALREADY, None, ""
    n = _papers_in(step)
    step["text"] = f"Put {n} papers in the draft, as read above" if n != 1 else "Put 1 paper in the draft, as read above"
    _did(talk, step)
    changed = _changed(talk, step)
    return step["text"], _after_put(talk, env, seen), changed


def confirm(talk, env, list_id, yes):
    """the person's Yes, all (yes True) or Not now (yes False) to the list that waits"""
    env.may()
    with talk.lock:
        if talk.closed:
            raise Refused(T.LOST)
        if talk.working or talk.busy:
            raise Refused(T.READING if talk.reading else T.WORKING)
        if not isinstance(list_id, str) or talk.waiting != list_id:
            raise Refused(T.NOT_WAITING)
        talk.busy = True
    try:
        if yes:
            text, _, changed = _put_waiting(talk, env, {})
            with talk.lock:
                talk.notes.append(" ".join(x for x in (f"The person said Yes, all to the list's table: {text.rstrip('.')}.", changed) if x))
        else:
            with talk.lock:
                st = _answered(talk, list_id)
                k = _lines(_groups(st["other"]))
                talk.add("sys", f"Left out: {_n(k, 'line', 'lines')} of the list.")
                talk.notes.append(f"The person said Not now to the list's table: its {_n(k, 'line was', 'lines were')} not put in.")
        with talk.lock:
            talk.used = T._now()
    finally:
        with talk.lock:
            talk.busy = False


# ---------------------------------------------------------------- the AI's two tools
def accept(talk, env, args, seen):
    """accept_list {said}: what Yes, all does, when the person said yes in their own words"""
    _, _, said = _ai.args_of("accept_list", args)
    with talk.lock:
        waiting = talk.waiting
    if waiting is None:
        return T.NO_LIST
    if not _steps._said_ok(talk, said):
        raise Refused(LIST_SAID)
    text, c, changed = _put_waiting(talk, env, seen)
    out = dict(text=text, changed=changed) if changed else dict(text=text)
    return dict(out, checks=T._for_ai(c)) if c is not None else out


def correct(talk, env, args):
    """correct_list {line, subjects}: what a waiting line (and every waiting line of the same level and words) is read as"""
    line, subjects = (args.get("line"), args.get("subjects")) if isinstance(args, dict) else (None, None)
    if not isinstance(line, int) or isinstance(line, bool) or not isinstance(subjects, list) \
            or not all(isinstance(x, str) for x in subjects):
        raise Refused(_steps.WRONG)
    subjects = [talk.names.back(x).strip() for x in subjects]
    model = (env.pub() or {}).get("model")
    model = model if isinstance(model, dict) else {}
    with talk.lock:
        lid = talk.waiting
        if lid is None:
            return T.NO_LIST
        st = talk.lists[lid]
        groups = _groups(st["other"])
        words = {(k[1], _steps._fold(k[2])) for k, _ in groups if k[0] == line}     # every group of the line: its level and words
        if not words:
            raise Refused(f"Line {line} is not waiting for a yes.")
        if not subjects:
            raise Refused(NO_SUBJECTS)
        meant = {}                                          # level -> the subjects as that level publishes them
        for level in sorted({lv for lv, _ in words}):
            by_fold = {_steps._fold(x): x for x in _listread._subjects(model, level)}
            meant[level] = []
            for x in subjects:
                if _steps._fold(x) not in by_fold:
                    raise Refused(f"{level} has no subject called {_steps._short(x)}.")
                if by_fold[_steps._fold(x)] not in meant[level]:
                    meant[level].append(by_fold[_steps._fold(x)])
        if not any(meant.values()):
            raise Refused(NO_SUBJECTS)
        out, changed = [], []
        for k, es in groups:
            if (k[1], _steps._fold(k[2])) not in words:
                out += es
                continue
            if str(k[0]) not in changed:
                changed.append(str(k[0]))
            mine = meant[k[1]]
            label = _written(es[0])[:_steps.LONGEST].strip() if len(mine) > 1 else ""
            out += [dict(es[0], subject=x, together=label) for x in mine]   # each paper from its own entry: none is lost
        st["other"] = out
        for l in talk.lines:
            if l["n"] == st["n"]:
                l["table"] = _table(_groups(out))
    which = f"Line {changed[0]} is" if len(changed) == 1 else f"Lines {_steps._join(changed)} are"
    return f"{which} now read as {', '.join(next(iter(meant.values())))}."

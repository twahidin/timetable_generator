"""Asking for relief on Telegram: the conversation /relief begins, its questions, and what it sends. relief/bot.py leads here (start,
step, line, stray, cancel, leave, replaced); what is said and called is bot's (reply, _settle, _did ...), and bot imports this only
when it is asked for.

A conversation is one row of the table talks (kind bot.ASK) and nothing else: one a chat, good for MINUTES after its last step, the
newest talk in place of any other. Its data: name, whose it is; step, ask and rows, the question it is at, as it is asked and asked
again ([[label, value, token]] for its buttons); key, new with each question; question, the id of the message that asked it last (None:
Telegram did not say; False: it is not known to have come; a dict: on its way, _on_way); and what was chosen (_EMPTY). Nothing is sent, and nothing of it is kept
anywhere else, before Send: the row goes when the conversation ends, however it does (bot.forget, when nobody comes back).

A button is a row of the table buttons with its token and nothing of what it means: a press counts while its token is one of the
question's the conversation is at, else it is OLD_BUTTON and nothing changes. Pressed, its message loses its buttons and gains the
choice; a tick (several days) changes the buttons of the very message. A line, a file or a photo is the answer where one is asked
for (why, who, work); where only a button is, PRESS_ONE is said and the question asked again, which takes the buttons off the one
before. What is typed is never taken for the answer to a question that is not known to have come, or when it replies to another
message (bot.LAST_ONE); it is never a code. The work question is the one exception: what comes while it is on its way (a text and a
file sent together) is taken for the lesson asked about, as it would be a moment later (at the list, after a Next or Later that
crossed it, PRESS_ONE is said, as a moment later); a press on an older copy takes the buttons off the one asked since; a copy of a question that comes once the
conversation is at another loses its buttons, and the one it is at is asked once more when it came above it (_asked_by), so one
question has buttons, the last. A message changed after it was sent is never an answer; one that says what is held already
(_held) is not answered at all, since a link's preview can come as one. A step is judged as the page judges it, when it is taken: a
refusal is the app's sentence, and the conversation is as it was. One step at a time (bot._pressing), and a step is saved only while
the conversation is what it was judged by (_store), so of two at once, in two copies of the app too, one is taken.

The lessons asked about are those that need relief, as absences.new decides it (_Now.lessons). Of a file or a photo only Telegram's
id and the name are kept, judged by the name and the size Telegram gives (files.check, PER_LESSON). A lesson takes any number of
messages until Next is pressed (_say_work): each line is added to its text, a link alone is its link (one a lesson), each file is
added, and it is asked about again; the files of one album that come later are the same lesson's whatever is pressed meanwhile, with
no second question (its question, or the list, when it is out, is changed). Outside any conversation a file or a photo is said not to
be attached (stray). Same as before is the work of the last lesson before that has any, files that come later too. The question of a
lesson and the list before Send say what is set (_what), never what it says.

Send ends the conversation first, so an absence is sent once whatever happens; refused, it is put back. It is saved by absences.new,
as the page's form does it, and marked (set_via); then, with nothing held, what follows on the page (web.created), the press is
answered, each file is fetched, saved and put on its lessons, and the person is told what was sent and which files could not be. A
failure after the save loses files at most.

The typed reason is in the talk and the absence alone: never said back, logged, in the history or in a message. Failures are logged to
"relief.telegram" by their kind alone."""
import datetime, functools, json, logging, re, secrets

from relief import absences as _absences
from relief import bot
from relief import cover as _cover
from relief import files as _files
from relief import lessons as _lessons
from relief import links, outbox, tell, tg, tgdb
from relief import web as _web
from relief import words
from relief.calendar import school_day

HI = "Hi {name}. Which day are you away?"
TODAY, TOMORROW, SEVERAL, ANOTHER = "Today, {day}", "Tomorrow, {day}", "Several days", "Another day"
WHICH_DAY, WHICH_DAYS, TICK, DONE = "Which day?", "Which days? Tick them, then press Done.", "✓ ", "Done"
TICK_ONE = "Tick at least one day."
NO_DAYS = "There are no school days coming up in the calendar."
WHOLE_OR_SOME, WHOLE, SOME = "Whole day, or some periods?", "Whole day", "Some periods"
FROM, TO = "From which period?", "To which period?"
REASON, OTHER, SAY_WHY = "Reason?", "Other", "Say why in one line."
RIGHT, YES, SOMEONE_ELSE = "Your reporting officer is {name}. Right?", "Yes", "Someone else"
WHO = "Who is your reporting officer? Type part of their name."
WHICH, NOT_HERE = "Who is your reporting officer?", "Not here? Type more of the name."
NOBODY = "Nobody on the staff list matches that. Type part of their name."
WORK = "Work for {lesson} {periods} on {day}{start}? Type it, send a file or a photo, or tap Later."
WORK_SET = "Work for {lesson} {periods} on {day}{start}: {what}. Send more, or press Next."
SAME, LATER, LATER_ALL, NEXT = "Same as before", "Later, in the app", "Later for all the rest", "Next"
LINK_REPLACED = "One link a lesson: this one is in place of the one before."
PRESS_ONE, SEND_ONE = "Please press one of the buttons.", "Send text, a file or a photo."
SEND, START_AGAIN = "Send", "Start again"
SENT = "✅ Sent to the relief team: {n}, {work}.{officer}"            # officer: " " and NOT_TOLD when they are not on Telegram, else nothing
NOT_TOLD = tell.NOT_TOLD
NOT_ATTACHED = "{name} could not be attached: add it in the app."
NOT_TAKEN = "That was not attached to any lesson: add it in the app."
NOT_SENT = "Your request for relief was not sent. Send /relief to start again."
CANCELLED = "Cancelled: nothing was sent."
MINUTES = 30
DAYS, AHEAD = 10, 60                             # the school days offered, and how many days after today they are looked for in
MATCHES, SHOWN = 8, 30                           # the names offered; the lessons listed before Send
TRIES = 5                                        # an album's file, when its talk moves on meanwhile
ALBUMS = 50                                      # albums sent outside any conversation, the last ones (state albums), each said so once
_LINK = re.compile(r"https?://\S+", re.I)
_log = logging.getLogger("relief.telegram")
# what is chosen, as a conversation begins: start, the first period; periods, [from, to] or None for the whole day; lessons, those
# asked about, and at, which of them; work, {lesson's key: dict(text, link, files [[Telegram's id, name]], group: its album, captions
# and typed: the pieces its text is made of, as they came) or dict(same: the key of another)}; photos, how many were sent
_EMPTY = dict(dates=[], ticks=[], start=None, periods=None, reason=None, why="", officer=None, lessons=[], at=0, work={}, photos=0)


class _Now:
    """what the app knows at this moment, each part read when it is first asked for (a step that needs none of it is not refused for
    it); refused in the app's own words when it cannot be had"""
    def __init__(self, me): self.me = me

    @functools.cached_property
    def pub(self):
        pub = bot._published()
        _web._on_staff(pub, self.me)
        return pub

    @functools.cached_property
    def cal(self):
        cal = _web._cal(self.pub)
        if not cal.get("terms"): raise ValueError(_lessons.NO_CALENDAR)
        return cal

    @functools.cached_property
    def days(self):
        """the next school days (ISO), today's too"""
        names, today = (self.pub.get("model") or {}).get("days") or [], _lessons.today()
        ahead = [today + datetime.timedelta(days=i) for i in range(AHEAD + 1)]
        got = [d.isoformat() for d in ahead if school_day(self.cal, names, d) is not None][:DAYS]
        if not got: raise ValueError(NO_DAYS)
        return got

    @functools.cached_property
    def periods(self):
        """every period of the day, dict(p, start, end), as the form has them (without times when the timetable has none)"""
        n = (self.pub.get("model") or {}).get("NP")
        return _web._periods(self.pub) or [dict(p=i, start="", end="") for i in range(n if type(n) is int else 0)]

    @functools.cached_property
    def names(self):
        """everybody on the timetable and the staff list but the person themself"""
        return [p["name"] for p in _web._staff(self.pub) if p["name"] != self.me]

    def lessons(self, dates, periods):
        """their lessons in that time that need relief, in time order, as absences.new decides it; refused as it would refuse them"""
        dates, exams, records = _absences._iso_dates(dates, _lessons.today()), bot._exams(self.pub), _absences.all_records()
        span = tuple(periods) if periods else None
        got = {x["key"]: _absences.as_now(records, x, exams) for d in dates for x in _lessons.on_date(self.pub, self.cal, self.me, d, periods=span)}
        _absences.something_to_cover(self.me, dates, periods, [not x["others"] or x["stopped"] for x in got.values()], exams)
        return [x for x in got.values() if not x["others"] and not x["stopped"]]


# ---- the questions: each gives what the conversation becomes
def _at(step, ask, rows=(), **more):
    """the conversation at that step, asking that, with these rows of (label, value) under it; more: what else becomes of it (says:
    sentences said before it)"""
    return dict(more, step=step, ask=ask[:outbox.LIMIT], rows=[[list(b) for b in row] for row in rows if row])


def _by(n, buttons): return [buttons[i:i + n] for i in range(0, len(buttons), n)]


def _day(w, **more):
    """the first question, with nothing chosen"""
    today = _lessons.today()
    soon = [(TODAY, today.isoformat()), (TOMORROW, (today + datetime.timedelta(days=1)).isoformat())]
    rows = [[(label.format(day=words.day(iso)), iso)] for label, iso in soon if iso in w.days]
    return _at("day", HI.format(name=w.me), rows + [[(SEVERAL, "several")], [(ANOTHER, "another")]], **dict(_EMPTY, name=w.me, **more))


def _ticked(iso, ticks): return (TICK if iso in ticks else "") + words.day(iso)


def _chosen(w, dates):
    """the days are chosen: whole or some, or the day asked again when nothing is to be covered"""
    try: w.lessons(dates, None)
    except ValueError as e: return _day(w, says=_if_nothing(e))
    return _span(dates=dates)


def _if_nothing(e):
    """the one refusal that is said before a question is asked again; any other goes on"""
    if type(e) is not ValueError or str(e) != _absences.NO_LESSONS: raise e
    return [str(e)]


def _span(**more): return _at("span", WHOLE_OR_SOME, [[(WHOLE, "whole"), (SOME, "some")]], **more)


def _from(w): return _at("start", FROM, _by(3, [(_p(x, "start"), x["p"]) for x in w.periods]))


def _p(x, time): return " · ".join(v for v in (f"P{x['p'] + 1}", x[time]) if v)


def _reason(**more): return _at("reason", REASON, _by(2, [(r, r) for r in _absences.REASONS]), **more)


def _officer(w, **more):
    """the officer of the last absence of theirs that has one who can be theirs still, or who it is"""
    for r in _absences.for_teacher(w.me):        # newest first
        name = r.get("reporting_officer")
        if name in w.names: return _at("officer", RIGHT.format(name=name), [[(YES, name), (SOMEONE_ELSE, "")]], **more)
    return _at("who", WHO, **more)


def _works(w, d):
    """the officer is known: the lessons that need relief, and the first one's work"""
    try: got = w.lessons(d["dates"], d["periods"])
    except ValueError as e: return _day(w, says=_if_nothing(e))
    lessons = [dict(key=x["key"], lesson=words.class_group(x), periods=words.periods_text(x), day=words.day(x["date"]), start=tell._from(x["start"])) for x in got]
    return _work(dict(d, lessons=lessons), 0, {}, lessons=lessons, officer=d["officer"])


def _work(d, at, work, **more):
    """the work of lesson at is asked for: while nothing is set for it, with Same as before (when a lesson before has work) and Later;
    once something is, what is set, with Next; after the last one, the list"""
    if at >= len(d["lessons"]): return _list(dict(d, work=work), at=at, work=work, **more)
    x, rest = d["lessons"][at], [(LATER_ALL, "rest")] if len(d["lessons"]) - at >= 2 else []
    got = _work_of(dict(d, work=work), x["key"])
    if _has(got): return _at("work", WORK_SET.format(**x, what=_what(got)), [[(NEXT, "next")], rest], at=at, work=work, **more)
    first = [(SAME, "same")] if _before(d, at, work) else []
    return _at("work", WORK.format(**x), [first + [(LATER, "later")], rest], at=at, work=work, **more)


def _list(d, **more):
    """what Send would send"""
    head = [f"Relief for {words.days(d)} · {words.away(d)}", f"Reason: {d['reason']}", f"Reporting officer: {d['officer']}"]
    lines = ["• {lesson} {periods} on {day}: ".format(**x) + _what(_work_of(d, x["key"])) for x in d["lessons"]]
    shown = lines[:SHOWN]
    while shown and len("\n".join(head + shown)) > outbox.LIMIT - 20: shown.pop()
    rest = [f"and {len(lines) - len(shown)} more"] if len(lines) > len(shown) else []
    return _at("list", "\n".join(head + shown + rest), [[(SEND, "send"), (START_AGAIN, "again")]], **more)


# ---- a lesson's work
def _work_of(d, key):
    """the work of lesson key: dict(text, link, files)"""
    w = d["work"].get(key) or {}
    if "same" in w: w = d["work"].get(w["same"]) or {}
    return dict(text=w.get("text") or "", link=w.get("link") or "", files=w.get("files") or [])


def _has(work): return bool(work["text"] or work["link"] or work["files"])


def _what(work):
    """'work set (text, 1 file)': what is set, never what it says; or 'no work yet'"""
    n = len(work["files"])
    parts = [k for k in ("text", "link") if work[k]] + ([f"{n} file" if n == 1 else f"{n} files"] if n else [])
    return f"work set ({', '.join(parts)})" if parts else "no work yet"


def _before(d, at, work):
    """the key of the last lesson before lesson at that has work of its own (one that is the same as it counts as it), or None"""
    d = dict(d, work=work)
    key = next((x["key"] for x in reversed(d["lessons"][:at]) if _has(_work_of(d, x["key"]))), None)
    return (work[key].get("same") or key) if key else None


def _file(m):
    """the file or the photo (its largest size) of a message: dict(id, name (None: a photo's), size, group, caption), or None"""
    doc, photos = m.get("document"), m.get("photo")
    if isinstance(doc, dict):
        got, name = doc, doc.get("file_name")
        name = _files.fit(" ".join(name.split()) if isinstance(name, str) else "") or "file"
    else:
        area = lambda x: x["width"] * x["height"] if type(x.get("width")) is int and type(x.get("height")) is int else 0
        got, name = max((x for x in (photos if isinstance(photos, list) else []) if isinstance(x, dict)), key=area, default={}), None
    text = lambda v: v if isinstance(v, str) else ""
    if not text(got.get("file_id")): return None
    size = got.get("file_size")
    return dict(id=got["file_id"], name=name, size=size if type(size) is int else None, group=text(m.get("media_group_id")), caption=text(m.get("caption")).strip())


def _add(d, key, file):
    """the file added to lesson key's work, unless it is there, and its caption to the text (its link and what was typed kept) -> what
    becomes of d; refused in the app's words, a file by its name"""
    w = d["work"].get(key) or {}
    files, photos = w.get("files") or [], d["photos"] + (file["name"] is None)
    if any(id == file["id"] for id, _ in files): return dict(photos=d["photos"], work=d["work"])
    name = file["name"] or f"photo {photos}.jpg"
    try:
        _files.check(name, file["size"])
        if len(files) >= _files.PER_LESSON: raise ValueError(_absences.TOO_MANY)
    except ValueError as e: raise ValueError(f"{name}: {e}") from None
    text = _absences._check_work(dict(text="\n".join(v for v in (w.get("text"), file["caption"]) if v)))["text"]
    work = dict(w, text=text, files=files + [[file["id"], name]], group=w.get("group") or file["group"], captions=w.get("captions", []) + [file["caption"]] * bool(file["caption"]))
    return dict(photos=photos, work=dict(d["work"], **{key: work}))


def _held(d, m):
    """the message m says what the conversation holds already: the text or link of a lesson's work, a caption or a typed line in it, or
    the reason typed"""
    held = {v for w in d["work"].values() for v in (w.get("text"), w.get("link"), *w.get("captions", ()), *w.get("typed", ()))}
    said = [v.strip() for v in (m.get("text"), m.get("caption")) if isinstance(v, str) and v.strip()]
    return any(v in held or " ".join(v.split()) == d["why"] for v in said)


def _album(d, file):
    """the key of the lesson the file's album was begun for, or None"""
    return next((k for k, w in d["work"].items() if file["group"] and w.get("group") == file["group"]), None)


# ---- the row
def _conversation(chat, me):
    """me's conversation in the chat, or None; another's there is ended"""
    t = bot._talk(chat)
    if t is None or t["kind"] != bot.ASK: return None
    if t["d"].get("name") == me: return t
    bot._end(chat, t)
    return None


def _store(chat, was, d, noted=None):
    """the conversation is d, for MINUTES from now, and so are its question's buttons -> True; False, nothing changed, when it is not
    was any more (was None: in place of whatever talk there is); noted: a dict given the id of was's question as it is noted now"""
    until = bot._clock() + MINUTES * 60
    with tgdb.db() as c:
        if was is not None:
            if not bot._still(c, chat, was): return False
            q = json.loads(c.execute("SELECT data FROM talks WHERE chat=?", (chat,)).fetchone()["data"])["question"]
            if noted is not None: noted["question"] = q
            if was["d"]["key"] == d["key"]: d = dict(d, question=q)                    # the same question: its id may have been noted meanwhile
        c.execute("DELETE FROM buttons WHERE what=? AND name=?", (bot.ASK, d["name"]))
        c.executemany("INSERT INTO buttons(token, name, what, until) VALUES (?, ?, ?, ?)", [(token, d["name"], bot.ASK, until) for row in d["rows"] for _, _, token in row])
        c.execute("INSERT OR REPLACE INTO talks(chat, kind, data, until) VALUES (?, ?, ?, ?)", (chat, bot.ASK, json.dumps(d), until))
    return True


def _drop(chat):
    """the conversation in the chat is over, whatever it was at -> its data, or None: there was none"""
    with bot._pressing, tgdb.db() as c:
        r = c.execute("SELECT data FROM talks WHERE chat=? AND kind=?", (chat, bot.ASK)).fetchone()
        c.execute("DELETE FROM talks WHERE chat=? AND kind=?", (chat, bot.ASK))
    d = json.loads(r["data"]) if r else None
    return d if isinstance(d, dict) else None


def _current(chat, key):
    """the data of the conversation, while it is at the question of that key, else None"""
    with tgdb.db(read=True) as c: r = c.execute("SELECT data FROM talks WHERE chat=? AND kind=?", (chat, bot.ASK)).fetchone()
    d = json.loads(r["data"]) if r else {}
    return d if d.get("key") == key else None


def _asked_by(chat, key, n):
    """the question of that key was asked by the message n (None: its id is not known; False: it did not surely come) -> (what is to
    be done, the key the conversation is at): "" when it is noted, the conversation being at it; "again", noted, but an older question
    came below it meanwhile (_on_way's below), so it is asked once more; "off", the conversation is at another by now: n loses its
    buttons, and "over", also, the one it is at came above n and is asked once more"""
    with tgdb.db() as c:
        r = c.execute("SELECT data FROM talks WHERE chat=? AND kind=?", (chat, bot.ASK)).fetchone()
        d = json.loads(r["data"]) if r else {}
        q, set_ = d.get("question"), lambda v: c.execute("UPDATE talks SET data=? WHERE chat=?", (json.dumps(dict(d, question=v)), chat))
        if d.get("key") == key:
            set_(n)
            return "again" if type(n) is int and _on_way(q) and q.get("below", 0) > n else "", key
        if type(n) is not int: return "", d.get("key")
        if _on_way(q): set_(dict(q, below=max(q.get("below", 0), n)))         # its own question, when it comes, is asked once more if above n
        return "over" if type(q) is int and q < n else "off", d.get("key")


def _on_way(q):
    """a question that is on its way (_move): {} or dict(below: the last message of an older question that came meanwhile)"""
    return isinstance(q, dict)


# ---- what is said, with nothing held
def _keys(rows): return [[dict(text=label, callback_data="b:" + token) for label, _, token in row] for row in rows]


def _put_question(chat, d):
    """the question, asked (again) -> whether it surely came; if not, what is typed next is not its answer"""
    r = bot.reply(chat, d["ask"], buttons=_keys(d["rows"]), ask=not d["rows"])
    n = r["result"].get("message_id") if r["ok"] and isinstance(r["result"], dict) else None
    try:
        then, now = _asked_by(chat, d["key"], (n if type(n) is int else None) if r["ok"] else False)
        if not r["ok"]: return False
        if then in ("off", "over") and d["rows"]: tg.call("editMessageReplyMarkup", dict(chat_id=chat, message_id=n), timeout=bot.TIMEOUT)
        if then in ("again", "over"): _reask(chat, now, ())
        elif not then: _redraw(chat, d["key"], (d["ask"], d["rows"]))
    except Exception as e: _log.warning("a question could not be noted (%s)", type(e).__name__)
    return r["ok"]


def _off(chat, d):
    """the message that asked the question of d loses its buttons"""
    if d.get("rows") and type(d.get("question")) is int: tg.call("editMessageReplyMarkup", dict(chat_id=chat, message_id=d["question"]), timeout=bot.TIMEOUT)


def _next(chat, d, says, was):
    """the next question, d's, after the sentences; was: the conversation as a line answered it, its question to lose its buttons"""
    if was is not None: _off(chat, was)
    for s in says: bot.reply(chat, s)
    _put_question(chat, d)


def _reask(chat, key, says):
    d = _current(chat, key)
    if d is None: return                         # it has moved on
    for s in says: bot.reply(chat, s)
    if _put_question(chat, d): _off(chat, d)


def _redraw(chat, key, shown, n=None):
    """the question of that key as it is now (its text, the labels of its buttons) on the message n, or the one that asked it last;
    shown: (ask, rows) as it was there; once more when it changed on its way. Not while it is on its way itself (_put_question)"""
    while True:
        d = _current(chat, key)
        if d is None or (d["ask"], d["rows"]) == shown: return
        to = n or d["question"]
        if type(to) is not int: return
        params = dict(chat_id=chat, message_id=to, reply_markup=dict(inline_keyboard=_keys(d["rows"])))
        if d["ask"] == shown[0]: tg.call("editMessageReplyMarkup", params, timeout=bot.TIMEOUT)
        else: tg.call("editMessageText", dict(params, text=d["ask"], disable_web_page_preview=True), timeout=bot.TIMEOUT)
        shown = (d["ask"], d["rows"])


# ---- a step (with bot._pressing held) -> bot._Out
def _move(chat, talk, new, typed=False, same=False, pressed=None):
    """the conversation at its next question (new: as the questions give it), on its way till its message is known -> bot._Out that
    asks it, or None: it moved on meanwhile; same: the same lesson asked about again, its buttons as they were where they are the same,
    so a press of one meanwhile counts; pressed: the message a press was on, the question asked since losing its buttons too"""
    new = dict(new)
    says, was = new.pop("says", ()), talk["d"] if talk else {}
    old = {(label, value): token for row in was.get("rows", ()) for label, value, token in row} if same else {}
    rows = [[[label, value, old.get((label, value)) or secrets.token_urlsafe(12)] for label, value in row] for row in new["rows"]]
    d, noted = dict(was, **dict(new, rows=rows, key=secrets.token_urlsafe(12), question={})), {}
    if not _store(chat, talk, d, noted): return None
    was = dict(was, question=noted.get("question", was.get("question")))     # noted meanwhile, its buttons come off
    off = typed or (pressed is not None and was["question"] != pressed)        # a press on an older copy: the one asked since too
    return bot._Out(then=lambda: _next(chat, d, says, was if off else None))


def _again(chat, d, *says):
    """the same question once more, after the sentences"""
    return bot._Out(then=lambda: _reask(chat, d["key"], says))


def _work_again(chat, talk, *says):
    """the work question, or the list, once more, after the sentences: while it is on its way, as a question of its own (its copy on the
    way loses its buttons when it comes), so one question has them"""
    d = talk["d"]
    if not _on_way(d["question"]): return _again(chat, d, *says)
    return _move(chat, talk, dict(_list(d) if d["step"] == "list" else _work(d, d["at"], d["work"]), says=says), typed=True, same=True)


def _on_day(w, d, v):
    if v == "several": return _at("days", WHICH_DAYS, _by(2, [(_ticked(x, ()), x) for x in w.days]) + [[(DONE, "done")]], ticks=[])
    if v == "another": return _at("another", WHICH_DAY, _by(2, [(words.day(x), x) for x in w.days]))
    return _chosen(w, [v])


def _on_done(w, d, v):
    if not d["ticks"]: raise ValueError(TICK_ONE)
    return _chosen(w, d["ticks"])


def _on_span(w, d, v): return _from(w) if v == "some" else _reason(periods=None)


def _on_start(w, d, v): return _at("end", TO, _by(3, [(_p(x, "end"), x["p"]) for x in w.periods if x["p"] >= v]), start=v)


def _on_end(w, d, v):
    try: w.lessons(d["dates"], [d["start"], v])
    except ValueError as e: return _span(says=_if_nothing(e))
    return _reason(periods=[d["start"], v])


def _on_reason(w, d, v): return _at("why", SAY_WHY, reason=v) if v == OTHER else _officer(w, reason=v)


def _on_officer(w, d, v):
    if not v: return _at("who", WHO)
    _web._on_staff(w.pub, v)
    return _works(w, dict(d, officer=v))


def _on_work(w, d, v):
    """rest: the list; same: this lesson's work is the one before's; later or next: the next lesson"""
    if v == "rest": return _work(d, len(d["lessons"]), d["work"])
    same = _before(d, d["at"], d["work"]) if v == "same" else None
    return _work(d, d["at"] + 1, dict(d["work"], **{d["lessons"][d["at"]]["key"]: dict(same=same)}) if same else d["work"])


PRESSED = dict(day=_on_day, days=_on_done, another=lambda w, d, v: _chosen(w, [v]), span=_on_span, start=_on_start, end=_on_end, reason=_on_reason,
               officer=_on_officer, who=_on_officer, work=_on_work, list=lambda w, d, v: _day(w))


def _by_press(chat, talk, p):
    d = talk["d"] if talk else dict(rows=[])
    label, v = next(((label, v) for row in d["rows"] for label, v, token in row if token == p.button["token"]), (None, None))
    if label is None: raise ValueError(bot.OLD_BUTTON)
    if d["step"] == "days" and v != "done": return _tick(chat, talk, v, p.message["id"])
    if d["step"] == "list" and v == "send": return _send(chat, talk)
    out = _move(chat, talk, PRESSED[d["step"]](_Now(d["name"]), d, v), pressed=p.message["id"])
    if out is None: raise ValueError(bot.OLD_BUTTON)
    return out._replace(line=words.days(dict(dates=d["ticks"])) if d["step"] == "days" else label)


def _tick(chat, talk, v, n):
    d = talk["d"]
    ticks = sorted(set(d["ticks"]) ^ {v})
    rows = [[[label if x == "done" else _ticked(x, ticks), x, token] for label, x, token in row] for row in d["rows"]]
    if not _store(chat, talk, dict(d, ticks=ticks, rows=rows)): raise ValueError(bot.OLD_BUTTON)
    return bot._Out(then=lambda: _redraw(chat, d["key"], (d["ask"], d["rows"]), n))


def _say_why(chat, talk, text, file):
    why = " ".join(text.split())                 # one line, as the page's box gives it
    if not 1 <= len(why) <= bot.WHY_MOST: return _again(chat, talk["d"])
    return _move(chat, talk, _officer(_Now(talk["d"]["name"]), why=why), typed=True)


def _say_who(chat, talk, text, file):
    d, typed = talk["d"], text.casefold().split()
    if not typed: return _again(chat, d, *([PRESS_ONE] if d["rows"] else []))
    got = [n for n in _Now(d["name"]).names if all(v in n.casefold() for v in typed)]
    rows = [[(n, n)] for n in got[:MATCHES]]
    return _move(chat, talk, _at("who", NOBODY if not got else WHICH + ("\n" + NOT_HERE if len(got) > MATCHES else ""), rows), typed=True)


def _say_work(chat, talk, text, file):
    """a file, a link alone or a line added to the lesson asked about, which is asked about again till Next: a link in place of the one
    before, a line to the text on a new line; the rest of its work kept"""
    d = talk["d"]
    key, line, says = d["lessons"][d["at"]]["key"], text.strip(), []
    if not file and not line: return _work_again(chat, talk, SEND_ONE)
    w = d["work"].get(key) or {}
    try:
        if file: got = _add(d, key, file)
        elif _LINK.fullmatch(line):
            link = _absences._check_work(dict(link=line))["link"]
            says = [LINK_REPLACED] if w.get("link") and w["link"] != link else []
            got = dict(work=dict(d["work"], **{key: dict(w, link=link)}))
        else:
            text = _absences._check_work(dict(text="\n".join(v for v in (w.get("text"), line) if v)))["text"]
            got = dict(work=dict(d["work"], **{key: dict(w, text=text, typed=w.get("typed", []) + [line])}))
    except ValueError as e:
        if type(e) is not ValueError: raise
        return _work_again(chat, talk, str(e))
    return _move(chat, talk, dict(_work(d, d["at"], got["work"]), says=says, **got), typed=True, same=True)


SAID = dict(why=_say_why, who=_say_who, work=_say_work)


def _more(chat, talk, key, file):
    """another file of the album begun for lesson key: the same lesson's, with no question (the question that is out says it too, while
    it is that lesson's or the list); refused, its sentence alone"""
    was = talk["d"]
    try: d = dict(was, **_add(was, key, file))
    except ValueError as e:
        if type(e) is not ValueError: raise
        return bot._Out(str(e))
    if d["step"] == "list": d["ask"] = _list(d)["ask"]
    elif d["step"] == "work" and d["lessons"][d["at"]]["key"] == key: d["ask"] = _work(d, d["at"], d["work"])["ask"]   # its rows are Next's already
    return bot._Out(then=lambda: _redraw(chat, d["key"], (was["ask"], was["rows"]))) if _store(chat, talk, d) else None


def _said(chat, talk, text, file, to):
    """a line or a file; None when the conversation moved on meanwhile"""
    d = talk["d"]
    album = _album(d, file) if file else None
    if album is not None: return _more(chat, talk, album, file)
    q = d["question"]
    if _on_way(q) and d["step"] == "work": return _work_again(chat, talk) if to is not None else _say_work(chat, talk, text, file)   # taken as a moment later
    if _on_way(q) and d["step"] == "list": return _work_again(chat, talk, PRESS_ONE)          # Next or Later was pressed first: as a moment later
    if q is False or _on_way(q): return _again(chat, d)                                  # it may not have come
    if to is not None and to != q: return _again(chat, d, bot.LAST_ONE)
    return SAID[d["step"]](chat, talk, text, file) if d["step"] in SAID else _again(chat, d, PRESS_ONE)


def step(chat, me, text="", press=None, file=None, to=None, edit=None):
    """one step of me's conversation in the chat: a press (bot's p), or a line or a file (_file's) that replies to the message to;
    neither: something else was sent; edit: a message changed after it was sent. With bot._pressing held -> bot._Out; None when there
    is no such conversation (not for a press: OLD_BUTTON). A line that lost a race does nothing; a file of an album is put where its
    album is now"""
    talk = _conversation(chat, me)
    if press is not None: return _by_press(chat, talk, press)
    if talk is None: return None
    if edit is not None and _held(talk["d"], edit): return bot._Out()
    out = _said(chat, talk, text, file, to)
    for _ in range(TRIES):
        talk = _conversation(chat, me) if out is None and file else None
        album = _album(talk["d"], file) if talk else None
        if album is None: break
        out = _more(chat, talk, album, file)
    return out or bot._Out()


# ---- what relief/bot.py calls
def _finish(chat, out):
    """what a step that was no press comes to, said -> whether there was one"""
    if out is None: return False
    if out.text: bot.reply(chat, out.text)
    if out.then: out.then()
    return True


def start(chat, me):
    """/relief: a conversation of me's begun in the chat, or why it cannot be"""
    _finish(chat, bot._did(lambda: _move(chat, None, _day(_Now(me)))))


def line(chat, me, m, edit=False):
    """a message (edit: changed after it was sent) while a conversation goes on -> whether it was for it"""
    text = m["text"] if isinstance(m.get("text"), str) else ""
    if edit: return _finish(chat, bot._did(lambda: step(chat, me, edit=m)))
    return _finish(chat, bot._did(lambda: step(chat, me, text=text, file=_file(m), to=bot._replies_to(m))))


def stray(chat, m):
    """a message no conversation takes -> whether it held a file or a photo: it is said not to be attached, an album's once"""
    if _file(m) is None: return False
    if _first_of(chat, m.get("media_group_id")): bot.reply(chat, NOT_TAKEN, buttons=_app())
    return True


def _first_of(chat, group):
    """the album was not said so yet, as far as the last ALBUMS are known; always, for no album"""
    if not isinstance(group, str) or not group: return True
    with tgdb.db() as c:
        r, mine = c.execute("SELECT v FROM state WHERE k='albums'").fetchone(), f"{chat}:{group}"
        known = json.loads(r["v"]) if r else []
        if mine in known: return False
        c.execute("INSERT OR REPLACE INTO state(k, v) VALUES ('albums', ?)", (json.dumps((known + [mine])[-ALBUMS:]),))
    return True


def cancel(chat):
    """/cancel -> whether there was a conversation"""
    d = _drop(chat)
    if d is None: return False
    bot.reply(chat, CANCELLED)
    _off(chat, d)
    return True


def leave(chat, quiet):
    """a command ends the conversation: NOT_SENT (not when quiet, or no day was chosen), to the person whose it was alone"""
    d = _drop(chat)
    if d is None or links.tries.blocked(f"tg:{chat}") or links.name_of(chat) != d.get("name"): return
    first, then = replaced(chat, d)
    if first and not quiet: bot.reply(chat, first)
    then()


def replaced(chat, d):
    """the conversation d ended by another talk in its place -> (what is said first, or None, and what is called then)"""
    return NOT_SENT if d.get("dates") or d.get("ticks") else None, lambda: _off(chat, d)


# ---- Send
def _send(chat, talk):
    d, me, pub = talk["d"], talk["d"]["name"], bot._published()
    if not bot._end(chat, talk): raise ValueError(bot.OLD_BUTTON)                        # over before anything is done in it: sent once
    works = [dict(key=x["key"], work={k: v for k, v in _work_of(d, x["key"]).items() if k != "files"}) for x in d["lessons"]]
    try:
        r = _absences.new(dict(teacher=me, dates=d["dates"], periods=d["periods"], reason=d["reason"], reason_text=d["why"], reporting_officer=d["officer"], lessons=works),
                          pub, me, "asked", may_choose=False, links=bot._exams(pub))
    except ValueError as e:
        if type(e) is ValueError: _back(chat, talk)
        raise
    r = _tried(lambda: _absences.set_via(r["id"], links.VIA), r)
    return bot._Out(line=SEND, after=lambda: _web.created("asked", r, pub, by=(me, links.VIA)), then=lambda: _sent(chat, d, r, pub))


def _back(chat, talk):
    """refused: the conversation is as it was, unless another talk is there by now, or the chat is not that person's any more"""
    with tgdb.db() as c:
        c.execute("INSERT OR IGNORE INTO talks(chat, kind, data, until) SELECT ?, ?, ?, ? WHERE EXISTS (SELECT 1 FROM links WHERE chat=? AND name=?)",
                  (chat, talk["kind"], talk["data"], talk["until"], chat, talk["d"]["name"]))


def _tried(f, other):
    """f(), or other when it fails"""
    try: return f()
    except Exception as e:
        _log.warning("a step of asking for relief failed (%s)", type(e).__name__)
        return other


def _sent(chat, d, r, pub):
    """the absence r is saved: its files, and then what was sent is said"""
    lost = _attach(r["id"], d)
    if lost: bot.reply(chat, "\n".join(NOT_ATTACHED.format(name=n) for n in lost)[:outbox.LIMIT])
    r = _tried(lambda: _absences.load(r["id"]), None) or r
    exams = bot._exams(pub)
    mine = [x for x in r["lessons"] if x["needed"] and not _cover.stopped(exams, x)]
    n, m = len(mine), sum(1 for x in mine if _has(x["work"]))
    told = "" if _tried(lambda: d["officer"] in links.reachable(pub), False) else " " + NOT_TOLD.format(officer=d["officer"])
    bot.reply(chat, SENT.format(n="1 lesson" if n == 1 else f"{n} lessons", work=f"work set for {m}" if m else "no work set yet", officer=told), buttons=_app())


def _app():
    """the button that opens My absences in the app; None without an https address (Telegram takes no other)"""
    base = _tried(lambda: links.connected()["base"], "") or ""
    return [[dict(text=tell.OPEN, url=base + "/relief#mine")]] if base.lower().startswith("https://") else None


def _attach(id, d):
    """each file of each lesson fetched and saved, once however many lessons list it, and put on them -> the names of those that are
    not on every one of theirs"""
    saved, on, lost = {}, set(), {}
    for x in d["lessons"]:
        for tid, name in _work_of(d, x["key"])["files"]:
            if tid not in saved: saved[tid] = _tried(lambda: _fetched(id, tid, name), None)
            if saved[tid] and _tried(lambda: _absences.add_file(id, x["key"], saved[tid], d["name"]), None): on.add(tid)
            else: lost[tid] = name
    for tid, f in saved.items():
        if f and tid not in on: _tried(lambda: _files.delete(id, f["id"]), None)
    return list(lost.values())


def _fetched(id, tid, name):
    data = tg.download(tid, _files.MAX)
    return _files.save(id, name, data) if data is not None else None

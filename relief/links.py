"""Whose a Telegram chat is: one-time codes, linking, who can be reached, and their rights (tables links and codes of
relief/tgdb.py).

A code (new_code, only ever for the person signed in) is 8 letters and digits of access.ALPHABET as XXXX-XXXX, kept as a
SHA-256 hash alone, good once for CODE_MINUTES; a new one replaces that person's earlier one. use takes a code and links the
chat it came from, in one transaction, so a code sent twice at once links once. It is looked up among the link codes only and
never compared with anybody's personal sign-in code, so the bot cannot be used to guess one.

One chat is one person's and one person has one chat (both are unique in the table): link moves a person's link to the new
chat and takes the chat from whoever had it; the chats that lost a link are added to the caller's `lost` list as
dict(name, chat), and a conversation left open in them is dropped (the next person there must not finish it).

A link is not tied to the account's sign-in number: each message and press is judged on the records at that moment. A person
is there while accounts.people.find finds them (or nothing is published: a publish may be swapping folders) and they are not
switched off; while the accounts file cannot be read nobody is. chat_of, name_of, person, rights_of and reachable answer only
for a person who is there; linked lists every link (the settings page unlinks any of them)."""
import hashlib, secrets, time

import access
import store
from accounts import people as _accounts
from accounts import rights as _rights
from relief import absences as _absences
from relief import tg, tgdb

CODE_MINUTES = 15
CODE_LENGTH = 8
VIA = "telegram"                                   # how a person answering on Telegram is signed in (not one of rights.STRONG)
PRACTICE_BOT = "practice_bot"                      # the bot's name in practice mode (tg.call)
tries = access.Limiter(n=5, window=600)            # wrong codes and "not linked" answers, by "tg:" + chat


def _clock(): return time.time()


def connected():
    """the connected bot, dict(username, base, at), or None: no token, not connected, or connected in practice mode while the
    token is a real one now (somebody else's bot may have that name: no code is ever sent there)"""
    if not tg.on(): return None
    b = tgdb.get_state("bot")
    if not isinstance(b, dict) or not b.get("username"): return None
    return None if b["username"] == PRACTICE_BOT and not tg.practice() else b


# ---- one-time codes
def shaped(text):
    """text reads as a code: 8 letters and digits of access.ALPHABET, in any case, with any spaces and dashes"""
    c = access.norm(text)
    return len(c) == CODE_LENGTH and all(x in access.ALPHABET for x in c)


def _hash(code): return hashlib.sha256(access.norm(code).encode()).hexdigest()


def new_code(name):
    """a new code for name: dict(code "XXXX-XXXX", until: epoch seconds)"""
    now = _clock()
    until = now + CODE_MINUTES * 60
    with tgdb.db() as c:
        c.execute("DELETE FROM codes WHERE name=? OR until<=?", (name, now))
        while True:
            raw = "".join(secrets.choice(access.ALPHABET) for _ in range(CODE_LENGTH))
            if c.execute("INSERT OR IGNORE INTO codes(hash, name, until) VALUES (?, ?, ?)", (_hash(raw), name, until)).rowcount == 1: break
    return dict(code=f"{raw[:4]}-{raw[4:]}", until=until)


def use(code, chat, handle, lost=None):
    """link chat to the person whose current code this is -> their name; None when it is no current link code, or its person
    is not there any more (nothing is changed then)"""
    if not shaped(code): return None
    h = _hash(code)
    with tgdb.db(read=True) as c:
        r = c.execute("SELECT name FROM codes WHERE hash=? AND until>?", (h, _clock())).fetchone()
    if r is None or _there(r["name"]) is None: return None
    with tgdb.db() as c:
        if c.execute("DELETE FROM codes WHERE hash=? AND name=? AND until>?", (h, r["name"], _clock())).rowcount != 1: return None    # used meanwhile
        _put(c, r["name"], chat, handle, lost)
    return r["name"]


# ---- links
def _put(c, name, chat, handle, lost=None):
    """-> the chat name's link moved from, or None"""
    old = [dict(r) for r in c.execute("SELECT name, chat FROM links WHERE (name=? OR chat=?) AND NOT (name=? AND chat=?)", (name, chat, name, chat))]
    c.execute("DELETE FROM links WHERE name=? OR chat=?", (name, chat))
    c.execute("INSERT INTO links(name, chat, handle, at) VALUES (?, ?, ?, ?)", (name, chat, handle, _absences._now()))
    for x in old: c.execute("DELETE FROM talks WHERE chat=?", (x["chat"],))
    if lost is not None: lost.extend(old)
    return next((x["chat"] for x in old if x["name"] == name), None)


def link(name, chat, handle, lost=None):
    """link name to chat -> the chat the link moved from, or None"""
    with tgdb.db() as c: return _put(c, name, chat, handle, lost)


def _drop(column, value):
    with tgdb.db() as c:
        r = c.execute(f"SELECT name, chat FROM links WHERE {column}=?", (value,)).fetchone()
        if r is None: return None
        c.execute("DELETE FROM links WHERE name=?", (r["name"],))
        c.execute("DELETE FROM talks WHERE chat=?", (r["chat"],))
        return r


def unlink(name):
    """-> the chat that was name's, or None"""
    r = _drop("name", name)
    return r["chat"] if r else None


def unlink_chat(chat):
    """-> the name the chat was linked to (there or not), or None"""
    r = _drop("chat", chat)
    return r["name"] if r else None


def linked():
    """every link: {name: dict(handle, at)}"""
    with tgdb.db(read=True) as c:
        return {r["name"]: dict(handle=r["handle"], at=r["at"]) for r in c.execute("SELECT name, handle, at FROM links")}


# ---- who is there
def _accounts_now():
    """the accounts, in one read; None while the file cannot be read"""
    data, ok = _accounts._read()
    return data if ok else None


def _stand_in(name, data):
    """app.py's _stand_in: a person while nothing is published, from their record"""
    r = _accounts.record(data, name)
    return dict(name=name, short=name, depts=list(r["depts"]), role="", teaches=False, staff_only=False, group=r["group"] or "teacher",
                extras=r["extras"], username=r["username"], off=r["off"], has_password=bool(r["pw"]), last=max(r["signins"], default=None),
                n=r["n"], must_change=r["must_change"])


def _there(name):
    """the person as app.py's who() gives them (no password hash), or None"""
    data = _accounts_now()
    if data is None: return None
    pub = store.published()
    p = _accounts.find(name, pub, data)
    if p is None and not pub: p = _stand_in(name, data)
    if p is None or p["off"]: return None
    p.pop("pw", None)
    return p


def person(chat):
    with tgdb.db(read=True) as c:
        r = c.execute("SELECT name FROM links WHERE chat=?", (chat,)).fetchone()
    return _there(r["name"]) if r else None


def name_of(chat):
    p = person(chat)
    return p["name"] if p else None


def rights_of(chat):
    """what the chat's person may do now: what their personal code gives (accounts/rights.py), none for nobody"""
    return _rights.rights(person(chat), VIA)


def chat_of(name):
    with tgdb.db(read=True) as c:
        r = c.execute("SELECT chat FROM links WHERE name=?", (name,)).fetchone()
    return r["chat"] if r and _there(name) else None


def reachable(pub=None):
    """{name: chat} of everyone linked who is there, the accounts read once (pub: the published timetable, read when None)"""
    data = _accounts_now()
    if data is None: return {}
    if pub is None: pub = store.published()
    known = {p["name"]: p["off"] for p in _accounts.staff(pub, data)}
    with tgdb.db(read=True) as c:
        got = {r["name"]: r["chat"] for r in c.execute("SELECT name, chat FROM links")}
    off = lambda n: known[n] if n in known else (True if pub else _accounts.record(data, n)["off"])
    return {n: chat for n, chat in got.items() if not off(n)}

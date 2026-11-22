"""The Telegram stage's SQLite file, DATA/relief/telegram.db (standard library sqlite3).

db: a context manager giving one connection per block (never shared between threads): it commits on a normal exit, rolls back
on an exception and is always closed; WAL mode, a 10 second wait for a lock, rows as sqlite3.Row; what is deleted or written over
is not left in the file (secure_delete: a talk holds what a person typed). The tables are made on first
use, and again harmlessly any time. get_state / set_state keep JSON values by key; raise_state is for what is to be done once. first_time: True only the first time an
update id is seen; the table keeps the last KEEP ids by order of arrival (Telegram may restart its ids at any number)."""
import contextlib, json, os, sqlite3, threading

import store

KEEP = 1000
PATH = os.path.join(store.DATA, "relief", "telegram.db")
_made = set()
_mlock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS links(name TEXT PRIMARY KEY, chat INTEGER UNIQUE NOT NULL, handle TEXT, at TEXT);
CREATE TABLE IF NOT EXISTS codes(hash TEXT PRIMARY KEY, name TEXT, until REAL, chat INTEGER);
CREATE TABLE IF NOT EXISTS outbox(key TEXT PRIMARY KEY, name TEXT, chat INTEGER, kind TEXT, text TEXT, buttons TEXT, files TEXT,
    ref TEXT, state TEXT, at TEXT, sent_at TEXT, message_id INTEGER, tries INTEGER DEFAULT 0, next_at REAL,
    claimed REAL, files_failed INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS buttons(token TEXT PRIMARY KEY, name TEXT, what TEXT, id TEXT, ckey TEXT, who TEXT, extra TEXT, until REAL);
CREATE TABLE IF NOT EXISTS talks(chat INTEGER PRIMARY KEY, kind TEXT, data TEXT, until REAL);
CREATE TABLE IF NOT EXISTS updates(n INTEGER PRIMARY KEY AUTOINCREMENT, id INTEGER UNIQUE NOT NULL);
CREATE TABLE IF NOT EXISTS state(k TEXT PRIMARY KEY, v TEXT);
"""


def _ensure():
    if PATH in _made and os.path.exists(PATH): return
    with _mlock:
        os.makedirs(os.path.dirname(PATH), exist_ok=True)
        c = sqlite3.connect(PATH, timeout=10)
        try:
            c.execute("PRAGMA journal_mode=WAL")
            c.executescript(SCHEMA)
            c.commit()
        finally:
            c.close()
        _made.add(PATH)


@contextlib.contextmanager
def db(read=False):
    """one connection for the block. A default block takes the write lock at once (BEGIN IMMEDIATE), waiting up to 10 seconds,
    so reading then writing never fails with "database is locked"; read=True is a plain read block."""
    _ensure()
    c = sqlite3.connect(PATH, timeout=10, isolation_level=None)
    c.row_factory = sqlite3.Row
    try:
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA secure_delete=ON")
        c.execute("BEGIN" if read else "BEGIN IMMEDIATE")
        try:
            yield c
        except BaseException:
            c.execute("ROLLBACK")
            raise
        c.execute("COMMIT")
    finally:
        c.close()


def get_state(k, default=None):
    with db(read=True) as c:
        r = c.execute("SELECT v FROM state WHERE k=?", (k,)).fetchone()
    return default if r is None else json.loads(r["v"])


def set_state(k, v):
    with db() as c:
        c.execute("INSERT OR REPLACE INTO state(k, v) VALUES (?, ?)", (k, json.dumps(v)))


def raise_state(k, n, also=()):
    """k raised to the number n, and each key of also set to n with it, in one block on the store -> True; False, nothing changed,
    when it is as high already (an earlier run, or another copy of the app, was there first)"""
    with db() as c:
        r = c.execute("SELECT v FROM state WHERE k=?", (k,)).fetchone()
        was = json.loads(r["v"]) if r else None
        if isinstance(was, (int, float)) and was >= n: return False
        c.executemany("INSERT OR REPLACE INTO state(k, v) VALUES (?, ?)", [(x, json.dumps(n)) for x in (k, *also)])
    return True


def first_time(update_id):
    """True only the first time this update id is seen"""
    with db() as c:
        new = c.execute("INSERT OR IGNORE INTO updates(id) VALUES (?)", (int(update_id),)).rowcount == 1
        if new:
            c.execute("DELETE FROM updates WHERE n NOT IN (SELECT n FROM updates ORDER BY n DESC LIMIT ?)", (KEEP,))
    return new
